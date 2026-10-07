#!/usr/bin/env python3
"""「스콰드 생존게임」 원고 구조 전수 점검.  novel_build.py 가 '문법·라벨·도달성'을 본다면, 이 도구는 '이야기가 앞뒤로 맞는지'를 본다.

  python3 tooling/novel_audit.py              # 빠른 점검(정적) — 오류가 있으면 종료코드 1
  python3 tooling/novel_audit.py --reach      # + 상태 탐색으로 '도달 불가 줄'(단서 다 줍기 / 하나도 안 줍기)
  python3 tooling/novel_audit.py --ending-deps  # + 엔딩마다 '없으면 못 가는 단서' (몇 분 걸린다)
  python3 tooling/novel_audit.py --times      # 시각 표기를 전부 뽑아 시각표 원본과 대조한 표
  python3 tooling/novel_audit.py --all        # 위 전부

점검 항목
  1) 플래그·변수: 읽는데 어디서도 안 정함(ERROR) / 정하는데 아무도 안 읽음(INFO)
  2) 단서 id: 조건에서 읽는데 @clue 가 없음(ERROR) / 얻기만 하고 어디에서도 안 씀(INFO) / 같은 id 를 다른 문구로 두 번 등록(ERROR)
  3) 도달 불가 조건: 한 번도 정해지지 않는 플래그를 요구하는 @if·선택지 / 합쳐도 못 채우는 변수 문턱(ERROR)
  4) 고아 라벨: 어떤 @goto·타임아웃·퍼즐 결과도 가리키지 않는 라벨(INFO. 장 첫머리처럼 흐름으로만 들어가는 곳은 제외)
  5) 엔딩 조건 단서 의존: 엔딩으로 가는 길에 걸린 단서·플래그 조건
  6) 시각표 대조(--times): 시각표 방송·시각표에 없는 방송·벽시계 읽기를 구분해 어긋난 곳을 표시

STRICT 규칙: ERROR 가 하나라도 있으면 종료코드 1.
"""
import sys, os, re, json, glob, time, argparse, collections
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'tooling')); sys.path.insert(0, os.path.join(ROOT, 'tests'))
import novel_build as nb

ENGINE_VARS = {'clues', 'assisted'}          # 엔진이 스스로 정하는 값
ENGINE_PREFIX = ('p_',)                      # 퍼즐 결과 기록(p_guide 등)

def load():
    d = os.path.join(ROOT, 'data', 'novel', 'ch')
    files = sorted(glob.glob(os.path.join(d, 'ch_*.txt')), key=nb.file_key)
    story, ctx, per = nb.build(files)
    return story, ctx, files

def cond_reads(cs):
    return [c[0] for c in cs]

def collect(story, ctx):
    """읽는 곳 / 정하는 곳 / 단서 얻는 곳."""
    ops = story['ops']; src = ctx.src
    reads = collections.defaultdict(list)    # name -> [loc]
    sets = collections.defaultdict(list)     # name -> [(loc, kind, value)]
    clue_at = collections.defaultdict(list)  # id -> [(loc, text)]
    def acts(a, loc):
        for x in a:
            if x[0] in ('set', 'add'): sets[x[1]].append((loc, x[0], x[2]))
    for i, op in enumerate(ops):
        loc = src[i]; k = op['o']
        if k == 'jf':
            for c in op['c']: reads[c[0]].append(loc)
        elif k in ('set', 'unset'): sets[op['k']].append((loc, 'set', op.get('v', 0)))
        elif k == 'add': sets[op['k']].append((loc, 'add', op['v']))
        elif k == 'clue': clue_at[op['id']].append((loc, op.get('t', '')))
        elif k == 'choice':
            for o in op['opts']:
                for c in o['c']: reads[c[0]].append(loc)
                acts(o['a'], loc)
        elif k == 'puz':
            d = op['d']
            for key in ('ok', 'fail', 'skip'): acts(d.get(key, []), loc)
            for c in d.get('cands', []): acts(c['do'], loc)
            if d.get('refuse'):
                acts(d['refuse']['do'], loc)
                for c in d['refuse']['c']: reads[c[0]].append(loc)
            for h in d.get('hints', []):
                for c in h['c']: reads[c[0]].append(loc)
                for a in h.get('any', []): reads[a].append(loc)
            if isinstance(d.get('hint'), dict):
                for c in d['hint']['c']: reads[c[0]].append(loc)
    return reads, sets, clue_at

def targets(story):
    """어떤 라벨이 가리켜지는가(goto·선택지·퍼즐 결과·타임아웃)."""
    ref = collections.Counter()
    def acts(a):
        for x in a:
            if x[0] == 'goto': ref[x[1]] += 1
    for op in story['ops']:
        k = op['o']
        if k == 'goto': ref[op['l']] += 1
        elif k == 'choice':
            for o in op['opts']: acts(o['a'])
            if op.get('to'): ref[op['to']] += 1
        elif k == 'puz':
            d = op['d']
            for key in ('ok', 'fail', 'skip'): acts(d.get(key, []))
            for c in d.get('cands', []): acts(c['do'])
            if d.get('refuse'): acts(d['refuse']['do'])
    return ref

class Rep:
    def __init__(self): self.err = []; self.info = []
    def E(self, m): self.err.append(m)
    def I(self, m): self.info.append(m)

def static_audit(story, ctx, rep, files):
    ops = story['ops']; src = ctx.src
    reads, sets, clue_at = collect(story, ctx)
    clue_ids = set(clue_at)
    # 1) 플래그·변수
    for n, locs in sorted(reads.items()):
        if n in ENGINE_VARS or n.startswith(ENGINE_PREFIX) or n in clue_ids: continue
        if n not in sets: rep.E('읽기만 하는 이름 "%s" (정하는 곳 없음) — %s' % (n, locs[0]))
    never_read = sorted(n for n in sets if n not in reads and n not in clue_ids)
    rep.I('정하기만 하고 아무도 읽지 않는 이름 %d개: %s' % (len(never_read), ' '.join(never_read)))
    # 2) 단서
    for n in sorted(reads):
        if n in clue_ids or n in sets or n in ENGINE_VARS or n.startswith(ENGINE_PREFIX): continue
    for cid, lst in sorted(clue_at.items()):
        texts = {t for _, t in lst}
        if len(texts) > 1: rep.E('단서 "%s" 가 서로 다른 문구로 %d번 등록됨 — %s' % (cid, len(lst), ' / '.join('%s' % l for l, _ in lst)))
        if cid not in reads: rep.I('단서 "%s" 는 얻기만 하고 조건·힌트로 쓰이지 않음(수첩 기록용)' % cid)
    for cid, ts in story['clues'].items():
        if cid not in clue_at: rep.E('단서 목록에 있는데 @clue 줄이 없음: %s' % cid)
    # 3) 도달 불가 조건
    # 되돌아가는 @goto 사이(= 반복될 수 있는 구간)에 있는 @add 는 횟수가 정해지지 않는다 → 상한 없음
    loops = []
    def back(a, i):
        for x in a:
            if x[0] == 'goto' and story['labels'].get(x[1], 1 << 30) <= i: loops.append((story['labels'][x[1]], i))
    for i, op in enumerate(ops):
        if op['o'] == 'goto' and story['labels'].get(op['l'], 1 << 30) <= i: loops.append((story['labels'][op['l']], i))
        elif op['o'] == 'choice':
            for o in op['opts']: back(o['a'], i)
        elif op['o'] == 'puz':
            d = op['d']
            for key in ('ok', 'fail', 'skip'): back(d.get(key, []), i)
            for c in d.get('cands', []): back(c['do'], i)
    pc_of = {}
    for i, op in enumerate(ops): pc_of[src[i]] = i
    mx = collections.defaultdict(int)
    for n, lst in sets.items():
        tot = 0
        for loc, kind, v in lst:
            if isinstance(v, str): v = 1   # @rec 글자 값은 '정해졌다'로 센다(비교는 아래 check_cs 에서 값 단위로)
            i = pc_of.get(loc, -1); rep_ = any(a <= i <= b for a, b in loops)
            if kind == 'add': tot += (10 ** 6 if rep_ and v > 0 else max(v, 0))
            else: tot += max(v, 0)
        mx[n] = tot
    def check_cs(cs, loc):
        for n, op, x, neg in cs:
            if n in ENGINE_VARS or n.startswith(ENGINE_PREFIX): continue
            if n == 'clues':
                if op in ('>=', '>') and x >= len(clue_ids) + (op == '>'): rep.E('조건 clues%s%d 인데 단서는 전부 %d종 — %s' % (op, x, len(clue_ids), loc))
                continue
            if n in clue_ids: continue
            if n not in sets:
                if not neg and op == 'flag': rep.E('한 번도 정해지지 않는 "%s" 를 요구하는 분기(영영 안 열림) — %s' % (n, loc))
                continue
            if isinstance(x, str):
                if op == '==' and x not in {v for _, _, v in sets[n]}: rep.E('@rec %s 가 "%s" 로 기록되는 곳이 없는데 그 값을 요구 — %s' % (n, x, loc))
                continue
            if op in ('>=', '>'):
                need = x + (1 if op == '>' else 0)
                if mx[n] < need: rep.E('변수 %s 는 모두 더해도 최대 %d 인데 %s%d 를 요구 — %s' % (n, mx[n], op, x, loc))
            if op == 'flag' and not neg and mx[n] <= 0: rep.E('플래그 "%s" 는 0 보다 큰 값으로 정해지는 곳이 없음 — %s' % (n, loc))
    for i, op in enumerate(ops):
        if op['o'] == 'jf': check_cs(op['c'], src[i])
        elif op['o'] == 'choice':
            for o in op['opts']: check_cs(o['c'], src[i])
        elif op['o'] == 'puz':
            for h in op['d'].get('hints', []): check_cs(h['c'], src[i])
    # 4) 고아 라벨
    ref = targets(story); chap_pc = {c['pc'] for c in story['chapters']}
    orphan = []
    for l, pc in story['labels'].items():
        if ref[l] or pc in chap_pc: continue
        # 장 제목(##) 바로 앞 라벨은 흐름으로 들어간다
        if pc < len(ops) and ops[pc]['o'] == 'chap': continue
        orphan.append('%s(%s)' % (l, ctx.label_loc.get(l, '?')))
    rep.I('어디서도 가리키지 않는 라벨 %d개(흐름으로만 들어가면 정상): %s' % (len(orphan), ' '.join(orphan)))
    # 엔딩 선언 vs 사용
    for e in story['endings']:
        if not any(o['o'] == 'end' and o['id'] == e['id'] for o in ops): rep.E('엔딩 "%s" 선언은 있는데 끝내는 줄이 없음' % e['id'])
    return reads, sets, clue_at

# ------------------------------------------------------------------ 상태 탐색
def explore(story, mode, budget_states=700000, tlimit=240):
    """mode: 'all' = 단서를 전부 줍는다 / 'none' = 하나도 안 줍는다. 지나간 pc 와 도달한 엔딩을 돌려준다."""
    import novel_sim as sim
    RV, CID = sim.relevant(story)
    ends = set(); pcs = set(); seen = set(); t0 = time.time()
    st = {'lines': 0, 'pcs': pcs}
    V0, c0 = {}, set()
    k, pc, pl = sim.advance(story, 0, V0, c0, st)
    stack = [(k, pc, pl, V0, c0)]
    def skey(pc, V, clues):
        return (pc, tuple(sorted((a, min(b, 9)) for a, b in V.items() if a in RV)), tuple(sorted(c for c in clues if c in RV)), len(clues) if 'clues' in RV else 0)
    truncated = False
    while stack:
        if len(seen) > budget_states or time.time() - t0 > tlimit: truncated = True; break
        k, pc, pl, V, clues = stack.pop()
        if k == 'end': ends.add(pl); continue
        if k in ('loop', 'fall'): continue
        key = skey(pc, V, clues)
        if key in seen: continue
        seen.add(key)
        if k == 'clue': opts = [mode == 'all']
        else: opts = sim.options(story, k, pc, pl, V, clues)
        for dec in opts:
            V2 = dict(V); c2 = set(clues); npc = sim.apply(story, k, pc, pl, dec, V2, c2)
            k2, pc2, pl2 = sim.advance(story, npc, V2, c2, st)
            stack.append((k2, pc2, pl2, V2, c2))
    return pcs, ends, len(seen), truncated, time.time() - t0

def reach_audit(story, ctx, rep):
    ops = story['ops']; src = ctx.src
    os.environ.pop('SIM_ALLCLUE', None)
    res = {}
    for mode in ('all', 'none'):
        res[mode] = explore(story, mode)
        pcs, ends, n, tr, dt = res[mode]
        rep.I('탐색[%s] 상태 %d개 · %.0f초%s · 엔딩 %s' % ('단서 전부 줍기' if mode == 'all' else '단서 하나도 안 줍기', n, dt, ' · 한도에서 중단(결과가 불완전)' if tr else '', ' '.join(sorted(ends)) or '없음'))
    union = res['all'][0] | res['none'][0]
    trunc = res['all'][3] or res['none'][3]
    dead = [i for i, op in enumerate(ops) if i not in union and op['o'] in ('say', 'nar', 'tho', 'puz', 'choice', 'end')]
    # 연속 구간으로 묶는다
    groups = []
    for i in dead:
        if groups and i - groups[-1][1] <= 3: groups[-1][1] = i
        else: groups.append([i, i])
    for a, b in groups:
        n = sum(1 for i in range(a, b + 1) if ops[i]['o'] in ('say', 'nar', 'tho'))
        msg = '탐색으로 도달 못 하는 구간 %s ~ %s (대사·지문 %d줄)' % (src[a], src[b], n)
        (rep.I if trunc else rep.E)(msg)
    if not groups: rep.I('탐색으로 도달 못 하는 줄 없음(두 탐색의 합집합)')
    allends = {e['id'] for e in story['endings']}
    miss = allends - res['all'][1] - res['none'][1]
    if miss and not trunc: rep.E('두 탐색 어디에서도 못 닿는 엔딩: %s' % ' '.join(sorted(miss)))
    return res

def ending_deps(story, ctx, rep, reads):
    """엔딩 E 마다, 단서 c 를 안 줍는 모든 경로로는 E 에 못 가는가(= c 가 필수)."""
    import novel_sim as sim
    RV, CID = sim.relevant(story)
    rel = sorted(c for c in CID if c in RV)
    rep.I('분기·힌트 조건에 쓰이는 단서 %d종: %s' % (len(rel), ' '.join(rel)))
    base = explore_excl(story, set())
    rep.I('(기준) 단서 전부 주울 때 닿는 엔딩: %s' % ' '.join(sorted(base)))
    need = {e: [] for e in base}
    for c in rel:
        got = explore_excl(story, {c})
        for e in base - got: need[e].append(c)
    for e in sorted(need): rep.I('엔딩 %-5s 필수 단서: %s' % (e, ' '.join(need[e]) or '없음(다른 단서로 대체 가능)'))
    none = explore(story, 'none')[1]
    rep.I('단서를 하나도 안 주우면 닿는 엔딩: %s' % (' '.join(sorted(none)) or '없음'))
    rep.I('단서 없이 못 닿는 엔딩: %s' % (' '.join(sorted(base - none)) or '없음'))

def explore_excl(story, excl, tlimit=240):
    import novel_sim as sim
    RV, CID = sim.relevant(story); ends = set(); seen = set(); st = {'lines': 0}; t0 = time.time()
    V0, c0 = {}, set(); k, pc, pl = sim.advance(story, 0, V0, c0, st); stack = [(k, pc, pl, V0, c0)]
    def skey(pc, V, clues): return (pc, tuple(sorted((a, min(b, 9)) for a, b in V.items() if a in RV)), tuple(sorted(c for c in clues if c in RV)), len(clues) if 'clues' in RV else 0)
    while stack and time.time() - t0 < tlimit:
        k, pc, pl, V, clues = stack.pop()
        if k == 'end': ends.add(pl); continue
        if k in ('loop', 'fall'): continue
        key = skey(pc, V, clues)
        if key in seen: continue
        seen.add(key)
        opts = [pl not in excl] if k == 'clue' else sim.options(story, k, pc, pl, V, clues)
        for dec in opts:
            V2 = dict(V); c2 = set(clues); npc = sim.apply(story, k, pc, pl, dec, V2, c2)
            k2, pc2, pl2 = sim.advance(story, npc, V2, c2, st); stack.append((k2, pc2, pl2, V2, c2))
    return ends

# ------------------------------------------------------------------ 시각 대조
# 시각표 원본(10장 방송 박스 화면 · ch_1011_end.txt 의 '@label ch10_sched_open' 바로 아래 줄)과 같아야 한다.
TIMETABLE = ['21:00:00', '21:00:20', '22:00:00', '22:05:30', '22:30:00', '02:00:00', '02:03:30', '03:00:00', '03:50:00', '04:00:00', '06:00:00', '06:30:00']
# 시각표에 없는(= 사람이 눌렀다고 풀이되는) 방송. 투표 갈림에 따라 04시대 둘 중 하나가 나온다.
HUMAN = {'22:58:04': '승우의 말 4초 뒤', '00:41:09': '듀우쿠키가 소리친 4초 뒤', '04:41:37': '투표 개표 뒤', '04:47:12': '투표 거부 뒤'}
# 장면 시각(벽시계 읽기·약속) 중 이야기 속 사실로 못박힌 것. (시각, 뜻)
FACTS = {'22:06': '또꾸 외출', '22:16': '또꾸 복귀', '22:08': '바퀴 소리', '02:20': '신린·유미·탑위치 외출', '02:31': '복귀', '04:47': '또꾸·신린·안진 외출',
         '04:56': '복귀', '02:22': '유미 수첩 모터', '02:23': '바퀴', '02:25': '탑위치 목격', '03:53': '보관실 닫힘', '22:04': '삼 분 끝', '22:01': '삼 분 시작(방송 아님)'}
# 단서 문구·카드와 본문의 산술이 맞아야 하는 곳: (시작, 끝, 본문이 말한 간격 초)
DURATIONS = [('05:25:00', '06:30:00', 65 * 60, '10장 태용 "한 시간 오 분"'), ('06:05:00', '06:30:00', 25 * 60, '11장 "이십오 분"'),
             ('23:41:00', '06:30:00', (6 * 60 + 49) * 60, '4장 "여섯 시간 49분"'), ('03:11:00', '03:53:00', 42 * 60, '7장 "사십이 분"'),
             ('02:03:30', '02:19:12', 15 * 60 + 42, '6장 "십오 분 사십이 초"'), ('22:06:00', '22:16:00', 600, '3장 "십 분"'),
             ('04:00:00', '06:30:00', 150 * 60, '8장 "두 시간 반"'), ('21:00:40', '22:00:00', 59 * 60 + 20, '2장 "59분 20초"')]
TIME_RE = re.compile(r'(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])|(\d{1,2})\s*시(?:\s*(정각)|\s*(\d{1,2})\s*분(?:\s*(\d{1,2})\s*초)?|(?=[^\d분]))')
KO_NUM = {'한': 1, '두': 2, '세': 3, '네': 4}

def sec(hms):
    h, m, s = [int(x) for x in hms.split(':')]; return h * 3600 + m * 60 + s

def norm(m):
    if m.group(1) is not None: return '%02d:%s:%s' % (int(m.group(1)), m.group(2), m.group(3) or '00'), m.group(3) is not None
    h = int(m.group(4)); mi = int(m.group(6) or 0); s = int(m.group(7) or 0)
    return '%02d:%02d:%02d' % (h, mi, s), (m.group(7) is not None)

def time_audit(files, rep, show=True):
    rows = []; bad = []
    tt = set(TIMETABLE); hu = set(HUMAN)
    for f in files:
        base = os.path.basename(f)
        for ln, line in enumerate(open(f, encoding='utf-8'), 1):
            if line.lstrip().startswith('//'): continue            # 작가 메모는 제외
            for m in TIME_RE.finditer(line):
                t, has_s = norm(m)
                if t.startswith('00:00') and not has_s and ':' in m.group(0) and m.group(0).count(':') == 1 and int(m.group(1)) < 10 and len(m.group(1)) == 1: continue   # 천장 카운트다운 0:30 따위
                if m.group(1) is not None and len(m.group(1)) == 1 and ':' in m.group(0) and not m.group(3): continue   # M:SS 카운트다운(5:00)
                if re.match(r'\d{1,2}:\d{2}:\d{2}\.', line[m.start():m.start() + 12]): pass
                short = t[:5]
                kind = 'TT' if t in tt else ('HUMAN' if t in hu else ('FACT' if short in FACTS and t.endswith(':00') else '·'))
                rows.append((base, ln, m.group(0), t, kind, line.strip()[:90]))
    # 시각표에 있다고 말하는 줄: 줄 안의 시각이 모두 시각표 ∪ (사람이 누른 방송이 아니라고 말한 것) 이어야 한다
    claim = re.compile(r'시각표에 있는|시각표에 있으면|시각표대로|시각표 방송은|다 시각표에|앞의 (?:넷|셋)|시각표에 있는 시각|이것도 시각표에 있')
    notclaim = re.compile(r'시각표에 없|일정표에 없|표에 없')
    by_line = collections.defaultdict(list)
    for r in rows: by_line[(r[0], r[1])].append(r)
    for f in files:                                   # "앞의 넷은 다 시각표에 있는 방송이에요" — 바로 앞 줄이 나열한 시각을 본다
        b = os.path.basename(f)
        for ln, line in enumerate(open(f, encoding='utf-8'), 1):
            if re.search(r'앞의 (?:둘|셋|넷|다섯)[^.]*시각표', line) and (b, ln - 1) in by_line:
                for r in by_line[(b, ln - 1)]:
                    if r[3] not in tt and r[3] not in hu: bad.append('%s:%d "%s" 는 시각표에 없는데 뒷줄(%d)이 "앞의 …은 시각표에 있다"고 묶음' % (b, ln - 1, r[2], ln))
    for (b, ln), rs in by_line.items():
        text = rs[0][5]
        if claim.search(text) and not notclaim.search(text):
            for r in rs:
                if r[3] not in tt and r[4] != 'TT': bad.append('%s:%d "%s" 는 시각표에 없는데 시각표 방송처럼 말함 — %s' % (b, ln, r[2], text))
    # 방송 줄(방송: …)의 시각 라벨: "NN시 NN분입니다." 는 시각표나 사람이 누른 목록에 있어야 한다
    for f in files:
        base = os.path.basename(f)
        for ln, line in enumerate(open(f, encoding='utf-8'), 1):
            m = re.match(r'^방송:\s*(.*)$', line)
            if not m: continue
            lead = re.match(r'^((?:\d{1,2}\s*시[^.]{0,12}?))(?:입니다|정각입니다)', m.group(1))
            for mm in ([TIME_RE.match(lead.group(1))] if lead and TIME_RE.match(lead.group(1)) else []):
                t, _ = norm(mm)
                if t not in tt and t not in hu: bad.append('%s:%d 방송 대사의 시각 "%s" 가 시각표에 없음 — %s' % (base, ln, mm.group(0), line.strip()[:80]))
    # 정각: 같은 줄의 시각이 :00:00 이어야 한다 (방송 줄·정각 약속)
    for f in files:
        base = os.path.basename(f)
        for ln, line in enumerate(open(f, encoding='utf-8'), 1):
            if line.lstrip().startswith('//'): continue
            for m in re.finditer(r'(\d{1,2})\s*시\s*(?:(\d{1,2})\s*분\s*)?(?:(\d{1,2})\s*초\s*)?정각', line):
                if m.group(2) not in (None, '0', '00') or m.group(3) not in (None, '0', '00'): bad.append('%s:%d "정각" 인데 분·초가 있음: "%s"' % (base, ln, m.group(0)))
    # 산술
    for a, b, want, tag in DURATIONS:
        d = sec(b) - sec(a)
        if d < 0: d += 86400
        if d != want: bad.append('산술 불일치(%s): %s→%s = %d초, 본문 %d초' % (tag, a, b, d, want))
    # 시각표 원본이 본문(10장 박스 화면)과 같은가
    src = open(os.path.join(ROOT, 'data/novel/ch/ch_1011_end.txt'), encoding='utf-8').read()
    m = re.search(r'@label ch10_sched_open.*?\n\* ((?:\d\d:\d\d:\d\d(?: · )?)+)\n', src, re.S)
    boxed = re.findall(r'\d\d:\d\d:\d\d', m.group(1)) if m else []
    if boxed + ['06:30:00'] != TIMETABLE: bad.append('10장 시각표 화면 %s 가 도구의 시각표 원본과 다름' % ' '.join(boxed))
    # 장 카드의 시각은 앞 장에서 이미 읽힌 벽시계 시각보다 늦어야 한다
    def night(t):
        h, m = int(t[:2]), int(t[3:5]); return (h + 24 if h < 12 else h) * 60 + m
    texts = []
    for f in sorted(files, key=nb.file_key): texts.append(open(f, encoding='utf-8').read())
    regions = []; cur = None
    for line in '\n'.join(texts).split('\n'):
        if line.startswith('## '): cur = {'t': line[3:].strip(), 'card': None, 'seen': []}; regions.append(cur); continue
        if cur is None: continue
        m = re.match(r'^@card\s+[^|]*\|[^|]*?(\d\d):(\d\d)\s*$', line)
        if m: cur['card'] = '%s:%s' % m.groups(); continue
        if line.startswith('//') or not line.startswith('* '): continue
        if re.search(r'까지|뒤|남', line): continue
        mm = re.match(r'^\* (?:벽시계는 |시계는 )?(\d\d)시 (\d\d)분', line) or re.search(r'벽시계(?:는|가)\s*(\d\d)시 (\d\d)분', line)
        if mm: cur['seen'].append('%s:%s' % mm.groups())
    for k in range(1, len(regions)):
        a, b = regions[k - 1], regions[k]
        if b['card'] and a['seen']:
            last = max(a['seen'], key=night)
            if night(b['card']) < night(last): bad.append('장 카드 시각 %s(%s) 가 앞 장(%s)에서 이미 읽힌 시각 %s 보다 이름' % (b['card'], b['t'], a['t'], last))
    if show:
        print('%-14s %-22s %-9s %-6s %s' % ('위치', '표기', '정규화', '분류', '줄'))
        for r in rows: print('%-14s %-22s %-9s %-6s %s' % ('%s:%d' % (r[0], r[1]), r[2], r[3], r[4], r[5]))
        print('분류: TT=시각표 방송 · HUMAN=시각표에 없는 방송 · FACT=정해 둔 장면 시각 · ·=그 밖(벽시계·잡담·일정)')
        print('\n시각표 원본: ' + ' · '.join(TIMETABLE))
        print('시각표에 없는 방송: ' + ' · '.join('%s(%s)' % kv for kv in HUMAN.items()))
        print('\n산술 대조 %d건' % len(DURATIONS))
        for a, b, want, tag in DURATIONS: print('  %-34s %s→%s %s' % (tag, a, b, 'OK'))
    for x in bad: rep.E(x)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reach', action='store_true'); ap.add_argument('--ending-deps', action='store_true')
    ap.add_argument('--times', action='store_true'); ap.add_argument('--all', action='store_true'); ap.add_argument('-q', action='store_true')
    a = ap.parse_args()
    story, ctx, files = load()
    rep = Rep()
    for e in ctx.errors: rep.E('빌드: ' + e)
    reads, sets, clue_at = static_audit(story, ctx, rep, files)
    if a.reach or a.all: reach_audit(story, ctx, rep)
    if a.ending_deps or a.all: ending_deps(story, ctx, rep, reads)
    if os.path.exists(os.path.join(ROOT, 'data/novel/ch/ch_1011_end.txt')): time_audit(files, rep, show=(a.times or a.all) and not a.q)   # 옛 원고의 시각표 대조 — 새 원고(2026-10)에는 시각표가 없다
    if not a.q:
        for m in rep.info: print('정보 ' + m)
    for m in rep.err: print('오류 ' + m)
    print('\n구조 점검: 오류 %d · 정보 %d' % (len(rep.err), len(rep.info)))
    return 1 if rep.err else 0

if __name__ == '__main__':
    sys.exit(main())
