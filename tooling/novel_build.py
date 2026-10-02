#!/usr/bin/env python3
"""「스콰드」 장편판 시나리오 변환기.

시나리오 텍스트(ch_*.txt) -> novel.html 의 STORY 데이터(/*STORY:BEGIN*/ ~ /*STORY:END*/ 사이)로 바꾼다.

사용:
  python3 tooling/novel_build.py                # data/novel/ch/ch_*.txt (없으면 data/novel/fallback_short.txt) -> novel.html 갱신
  python3 tooling/novel_build.py --src DIR      # 다른 폴더/파일
  python3 tooling/novel_build.py --check        # 검사만(파일 안 씀). 오류 있으면 종료코드 1
  python3 tooling/novel_build.py --json out.json  # STORY 를 JSON 으로도 저장
  python3 tooling/novel_build.py --strict       # 경고(도달 불가 라벨 등)도 오류로
  python3 tooling/novel_build.py --import DIR   # 작가 폴더의 ch_*.txt 를 가져와(통합 수정 포함) 바로 빌드 — 원고가 바뀔 때 이 한 줄이면 됨

줄 형식(요약)
  ## 장 제목                  장 시작(자동 저장·장 선택 지점)
  @card 제목|부제   @bg id   @show id1,id2:f   @fx flicker|blackout|shake|off   @sfx knock|door|thud|fall|chime|keys|heartbeat|drone
  @mood none|calm|tense|dark   @wait 밀리초
  @clue id|문구   @if 조건 / @else / @end   @set 플래그|이름=값   @unset 이름   @add 변수 n
  @choice [timer=N] [default=K] [timeout=라벨]   그 아래  - 텍스트 => @set x; @add trust 1; @goto 라벨
        선택지 앞에 [조건] 을 붙이면 조건이 맞을 때만 보인다:  - [clues>=9] 텍스트 => ...
  @label 이름   @goto 이름   @puzzle 종류 {json}   @ending id|제목
  이름: 대사    * 지문    (이름) 속마음    // 주석
조건: 플래그 / !플래그 / 변수>=n (>,<,<=,==,!=) , 여러 개는 && / and / , 로 AND.  clues = 모은 단서 수.
퍼즐 json 공통: ok / fail / skip = "라벨" 또는 "@set x; @goto 라벨" (없으면 다음 줄로).
"""
import sys, os, re, json, glob, argparse

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BGS = {'white','prologue','forest','lobby','door','dining','dark','archive','broadcast','final','morning','ledger'}
FX = {'flicker','blackout','shake','off','clear','lights','flicker-off','blackout-off'}
SFX = {'knock','door','thud','fall','chime','keys','heartbeat','drone'}
MOODS = {'none','calm','tense','dark'}
PUZ = {'pick3','code','vote','guide','cctv'}
CHARS = ['seungwoo','myeongtae','ttokku','sinrin','hungry','pman','yumi','arin','squirrel','ugeoji','leivy','mongip',
         'usjeul','jelly','hallabong','taeyong','snake','gaeul','anjin','ongaeng','weiho','yeri','parrot','geunyang','kater']
BUILTIN_VARS = {'clues'}
# 작가마다 달리 쓴 같은 뜻의 플래그 -> 하나로 취급(왼쪽이 원고에서 읽히면 오른쪽 이름으로 바뀐다)
ALIAS = {'betrayed': 'e_betray', 'searched': 'early_seven'}
SFX_ALIAS = {'buzz': 'thud', 'heart': 'heartbeat', 'drop': 'thud'}
# 퍼즐 후보 id -> 초상화 id
FACE_ALIAS = {'gnyang': 'geunyang', 'seung': 'seungwoo', 'myeong': 'myeongtae'}
def canon(n): return ALIAS.get(n, n)
RESERVED_LABELS = set()

class Err(Exception): pass

class Ctx:
    def __init__(self):
        self.errors = []; self.warns = []
    def err(self, loc, msg): self.errors.append('%s: %s' % (loc, msg))
    def warn(self, loc, msg): self.warns.append('%s: %s' % (loc, msg))

def file_key(path):
    b = os.path.basename(path)
    m = re.match(r'ch_(P|p)', b)
    if m: return (0, b)
    m = re.match(r'ch_(\d+)', b)
    if m: return (int(m.group(1)), b)
    return (10**9, b)

CMP = re.compile(r'^([^\s<>=!]+)\s*(>=|<=|==|!=|>|<|=)\s*(-?\d+)$')

def parse_cond(s, ctx, loc):
    """조건 문자열 -> [[name, op, n, neg], ...] (AND)"""
    out = []
    for part in re.split(r'\s*(?:&&|&|,|\band\b)\s*', s.strip()):
        part = part.strip()
        if not part: continue
        m = CMP.match(part)
        if m:
            op = '==' if m.group(2) == '=' else m.group(2)
            out.append([canon(m.group(1)), op, int(m.group(3)), 0]); continue
        neg = 0
        if part.startswith('!'): neg = 1; part = part[1:].strip()
        if not re.match(r'^[^\s<>=!&,;|]+$', part):
            ctx.err(loc, '조건을 읽을 수 없음: "%s"' % part); continue
        out.append([canon(part), 'flag', 1, neg])
    if not out: ctx.err(loc, '조건이 비어 있음')
    return out

def parse_actions(s, ctx, loc):
    """'@set x; @add trust 1; @goto 라벨' 또는 '라벨' -> [['set',k,v],['add',k,n],['goto',label]]"""
    s = (s or '').strip()
    if not s: return []
    if not s.startswith('@') and re.match(r'^[^\s;]+$', s): return [['goto', s]]
    acts = []
    for part in s.split(';'):
        part = part.strip()
        if not part: continue
        part = part.lstrip('@')
        w = part.split(None, 1); d = w[0]; rest = w[1].strip() if len(w) > 1 else ''
        if d == 'set':
            m = re.match(r'^([^\s=]+)\s*=\s*(-?\d+)$', rest) or re.match(r'^([^\s=]+)\s+(-?\d+)$', rest)
            if m: acts.append(['set', canon(m.group(1)), int(m.group(2))])
            elif re.match(r'^[^\s=]+$', rest): acts.append(['set', canon(rest), 1])
            else: ctx.err(loc, '@set 형식 오류: "%s"' % part)
        elif d == 'unset' and re.match(r'^[^\s=]+$', rest): acts.append(['set', canon(rest), 0])
        elif d == 'add':
            m = re.match(r'^([^\s=]+)\s+(-?\d+)$', rest)
            if m: acts.append(['add', canon(m.group(1)), int(m.group(2))])
            else: ctx.err(loc, '@add 형식 오류(변수 숫자): "%s"' % part)
        elif d == 'goto' and re.match(r'^[^\s]+$', rest): acts.append(['goto', rest])
        else: ctx.err(loc, '알 수 없는 동작: "%s" (set/unset/add/goto 만 가능)' % part)
    return acts

def balanced(s):
    depth = 0; ins = False; esc = False
    for ch in s:
        if ins:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': ins = False
        else:
            if ch == '"': ins = True
            elif ch in '{[': depth += 1
            elif ch in '}]': depth -= 1
    return depth <= 0 and not ins

def parse_files(files, ctx):
    ops = []; labels = {}; label_loc = {}; chapters = []; clues = {}; endings = []
    ifstack = []   # [{'jf':idx,'jmp':None|idx,'loc':loc}]
    pending_choice = None
    src = []       # op 인덱스 -> 'file:line'
    def emit(op, loc):
        ops.append(op); src.append(loc); return len(ops) - 1
    for path in files:
        base = os.path.basename(path)
        with open(path, encoding='utf-8') as f: lines = f.read().replace('\r\n', '\n').split('\n')
        if lines and lines[0].startswith('﻿'): lines[0] = lines[0][1:]
        i = 0
        while i < len(lines):
            raw = lines[i]; ln = i + 1; i += 1
            loc = '%s:%d' % (base, ln)
            line = raw.strip()
            if not line or line.startswith('//'): continue
            # 선택지 옵션
            if pending_choice is not None:
                if line.startswith('- ') or line == '-':
                    body = line[1:].strip()
                    text, _, act = body.partition('=>')
                    text = text.strip(); cond = []
                    m = re.match(r'^\[([^\]]+)\]\s*(.*)$', text)
                    if m: cond = parse_cond(m.group(1), ctx, loc); text = m.group(2).strip()
                    if not text: ctx.err(loc, '선택지 텍스트가 비어 있음')
                    pending_choice['opts'].append({'t': text, 'c': cond, 'a': parse_actions(act, ctx, loc), '_loc': loc})
                    continue
                else:
                    if not pending_choice['opts']: ctx.err(pending_choice['_loc'], '@choice 아래에 "- 텍스트 => ..." 선택지가 없음')
                    pending_choice = None
            if line.startswith('##'):
                title = line.lstrip('#').strip()
                if not title: ctx.err(loc, '장 제목이 비어 있음')
                chapters.append({'n': len(chapters), 't': title, 'pc': len(ops), 'card': False})
                emit({'o': 'chap', 't': title, 'n': len(chapters) - 1}, loc); continue
            if line.startswith('@'):
                w = line[1:].split(None, 1); d = w[0].lower(); rest = w[1].strip() if len(w) > 1 else ''
                if d == 'card':
                    t, _, s = rest.partition('|')
                    if not t.strip(): ctx.err(loc, '@card 제목이 비어 있음')
                    if chapters and len(ops) - chapters[-1]['pc'] <= 3: chapters[-1]['card'] = True
                    emit({'o': 'card', 't': t.strip(), 's': s.strip()}, loc)
                elif d == 'bg':
                    if rest not in BGS: ctx.err(loc, '알 수 없는 배경 id "%s" (가능: %s)' % (rest, ', '.join(sorted(BGS))))
                    emit({'o': 'bg', 'id': rest}, loc)
                elif d == 'show':
                    lst = []
                    for tok in [x.strip() for x in rest.split(',') if x.strip()]:
                        cid, _, suf = tok.partition(':')
                        if cid not in CHARS: ctx.err(loc, '알 수 없는 초상화 id "%s"' % cid)
                        if suf not in ('', 'f'): ctx.err(loc, '초상화 접미사는 :f 만 가능: "%s"' % tok)
                        lst.append({'id': cid, 'f': 1 if suf == 'f' else 0})
                    if len(lst) > 4: ctx.warn(loc, '@show 가 4명을 넘음(화면엔 앞 4명만)')
                    emit({'o': 'show', 'ids': lst[:4]}, loc)
                elif d == 'fx':
                    v = rest.split()[0].lower() if rest else ''
                    if v not in FX: ctx.err(loc, '알 수 없는 @fx "%s" (flicker|blackout|shake|off)' % rest)
                    emit({'o': 'fx', 'v': {'clear': 'off', 'lights': 'off', 'flicker-off': 'off', 'blackout-off': 'off'}.get(v, v)}, loc)
                elif d == 'sfx':
                    v = SFX_ALIAS.get(rest.lower(), rest.lower())
                    if v not in SFX: ctx.err(loc, '알 수 없는 @sfx "%s" (%s)' % (rest, '|'.join(sorted(SFX))))
                    emit({'o': 'sfx', 'v': v}, loc)
                elif d == 'mood':
                    if rest not in MOODS: ctx.err(loc, '알 수 없는 @mood "%s"' % rest)
                    emit({'o': 'mood', 'v': rest}, loc)
                elif d == 'wait':
                    if not rest.isdigit(): ctx.err(loc, '@wait 는 밀리초 숫자')
                    emit({'o': 'wait', 'ms': int(rest) if rest.isdigit() else 0}, loc)
                elif d == 'clue':
                    cid, _, txt = rest.partition('|')
                    cid = cid.strip(); txt = txt.strip()
                    if not cid or not txt: ctx.err(loc, '@clue 는 "id|문구" 형식')
                    if cid in clues and clues[cid] != txt: ctx.warn(loc, '단서 %s 의 문구가 앞과 다름(앞 것을 씀)' % cid)
                    clues.setdefault(cid, txt)
                    emit({'o': 'clue', 'id': cid}, loc)
                elif d == 'if':
                    cond = parse_cond(rest, ctx, loc)
                    idx = emit({'o': 'jf', 'c': cond, 'to': -1}, loc)
                    ifstack.append({'jf': idx, 'jmp': None, 'loc': loc})
                elif d == 'else':
                    if not ifstack: ctx.err(loc, '@else 가 짝이 되는 @if 없이 나옴'); continue
                    top = ifstack[-1]
                    if top['jmp'] is not None: ctx.err(loc, '@else 가 두 번 나옴(@if 는 %s)' % top['loc']); continue
                    top['jmp'] = emit({'o': 'jmp', 'to': -1}, loc)
                    ops[top['jf']]['to'] = len(ops)
                elif d == 'end':
                    if not ifstack: ctx.err(loc, '@end 가 짝이 되는 @if 없이 나옴'); continue
                    top = ifstack.pop()
                    if top['jmp'] is not None: ops[top['jmp']]['to'] = len(ops)
                    else: ops[top['jf']]['to'] = len(ops)
                elif d in ('set', 'unset', 'add'):
                    a = parse_actions('@' + line[1:], ctx, loc)
                    for x in a: emit({'o': x[0], 'k': x[1], 'v': x[2]}, loc)
                elif d == 'choice':
                    opts = {'timer': 0, 'default': 0, 'timeout': ''}
                    for tok in rest.replace('[', ' ').replace(']', ' ').split():
                        m = re.match(r'^(timer|default|timeout)=(.+)$', tok)
                        if not m: ctx.err(loc, '@choice 옵션 오류 "%s" (timer=N default=K timeout=라벨)' % tok); continue
                        if m.group(1) == 'timeout': opts['timeout'] = m.group(2)
                        elif m.group(2).isdigit(): opts[m.group(1)] = int(m.group(2))
                        else: ctx.err(loc, '@choice %s 는 숫자' % m.group(1))
                    op = {'o': 'choice', 'timer': opts['timer'], 'def': opts['default'], 'to': opts['timeout'], 'opts': [], '_loc': loc}
                    emit(op, loc); pending_choice = op
                elif d == 'label':
                    if not re.match(r'^[^\s]+$', rest): ctx.err(loc, '@label 이름 오류: "%s"' % rest); continue
                    if rest in labels: ctx.err(loc, '라벨 "%s" 가 중복됨(앞: %s)' % (rest, label_loc[rest])); continue
                    labels[rest] = len(ops); label_loc[rest] = loc
                elif d == 'goto':
                    if not re.match(r'^[^\s]+$', rest): ctx.err(loc, '@goto 이름 오류: "%s"' % rest); continue
                    emit({'o': 'goto', 'l': rest}, loc)
                elif d == 'puzzle':
                    m = re.match(r'^(\S+)\s*(.*)$', rest, re.S)
                    ptype = m.group(1) if m else ''; js = m.group(2) if m else ''
                    if ptype not in PUZ: ctx.err(loc, '알 수 없는 퍼즐 종류 "%s" (%s)' % (ptype, '|'.join(sorted(PUZ)))); ptype = None
                    while not balanced(js) and i < len(lines):
                        js += '\n' + lines[i]; i += 1
                    try: data = json.loads(js) if js.strip() else {}
                    except Exception as e:
                        ctx.err(loc, '퍼즐 JSON 오류: %s' % e); data = {}
                    if ptype: emit({'o': 'puz', 'type': ptype, 'd': data}, loc)
                elif d == 'ending':
                    eid, _, t = rest.partition('|')
                    eid = eid.strip(); t = t.strip() or eid
                    if not eid: ctx.err(loc, '@ending id|제목 형식')
                    if eid not in [e['id'] for e in endings]: endings.append({'id': eid, 't': t})
                    emit({'o': 'end', 'id': eid, 't': t}, loc)
                else:
                    ctx.err(loc, '알 수 없는 지시어 "@%s"' % d)
                continue
            # 지문 / 속마음 / 대사
            if line.startswith('*'):
                emit({'o': 'nar', 't': line[1:].strip()}, loc); continue
            m = re.match(r'^\(([^()]{1,24})\)\s*(.+)$', line)
            if m:
                emit({'o': 'tho', 's': m.group(1).strip(), 't': m.group(2).strip()}, loc); continue
            m = re.match(r'^([^:：@*(\-#/][^:：]{0,23})[:：]\s*(.+)$', line)
            if m:
                emit({'o': 'say', 's': m.group(1).strip(), 't': m.group(2).strip()}, loc); continue
            ctx.err(loc, '해석할 수 없는 줄: "%s"' % (line[:40]))
        if pending_choice is not None:
            if not pending_choice['opts']: ctx.err(pending_choice['_loc'], '@choice 아래에 선택지가 없음')
            pending_choice = None
        if ifstack:
            for t in ifstack: ctx.err(t['loc'], '@if 가 @end 로 닫히지 않음')
            ifstack = []
    return ops, labels, label_loc, chapters, clues, endings, src

def first(d, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ''): return d[k]
    return default

def do_from(c, ctx, loc):
    """후보/선택 하나의 동작 -> 액션 리스트. do/to/goto + set + add 를 모두 받는다."""
    acts = []
    if c.get('set'):
        for x in str(c['set']).split(','): acts += parse_actions('@set ' + x.strip(), ctx, loc)
    if c.get('add'): acts += parse_actions('@add ' + str(c['add']), ctx, loc)
    d = first(c, 'do', 'to', 'goto', default='')
    if d: acts += parse_actions(d, ctx, loc)
    return acts

def check_puzzles(ops, src, ctx):
    NAME2ID = {'승우': 'seungwoo', '간장맛명태소환사': 'myeongtae', '또꾸': 'ttokku', '신린': 'sinrin', '허기허기': 'hungry', '포만포만': 'pman',
               '맛동산장인 유미': 'yumi', '아린': 'arin', '용맹한다람쥐': 'squirrel', '듀우쿠키': 'ugeoji', '레이비': 'leivy', '브론즈장인 우르곳': 'mongip',
               '우선즐겨': 'usjeul', '대한제일젤리': 'jelly', '헤롱우': 'hallabong', '태용': 'taeyong', '뱀조련사': 'snake', '가을': 'gaeul',
               '안진': 'anjin', '앙앵모르콩': 'ongaeng', 'weiho': 'weiho', '예리야': 'yeri', '탑위치생각해요': 'parrot', '그냥혀': 'geunyang', 'kater': 'kater'}
    for idx, op in enumerate(ops):
        if op['o'] != 'puz': continue
        loc = src[idx]; t = op['type']; raw = op['d']; d = {}
        if not isinstance(raw, dict): ctx.err(loc, '퍼즐 json 은 {...} 객체여야 함'); continue
        # 공통: 결과 동작
        for key, names in (('ok', ('ok', 'on_success', 'success', 'pass')), ('fail', ('fail', 'on_fail', 'failure')), ('skip', ('skip', 'on_skip'))):
            v = first(raw, *names)
            if v is not None:
                if isinstance(v, str): d[key] = parse_actions(v, ctx, loc)
                else: ctx.err(loc, '퍼즐 %s 는 문자열("라벨" 또는 "@set x; @goto 라벨")' % names[0])
        d['q'] = str(first(raw, 'q', 'prompt', 'title', 'task', default=''))
        d['note'] = str(first(raw, 'note', 'intro', default='') or '')
        d['wrong'] = str(first(raw, 'on_wrong', 'wrong', default='') or '')
        if t == 'pick3':
            items = first(raw, 'items', 'options', 'choices')
            if not isinstance(items, list) or len(items) < 3: ctx.err(loc, 'pick3 는 options(items)가 3개 이상 필요'); continue
            d['items'] = [({'id': str(k), 't': x, 'sub': ''} if isinstance(x, str) else {'id': str(x.get('id', k)), 't': x.get('t', x.get('label', x.get('name', ''))), 'sub': x.get('sub', '')}) for k, x in enumerate(items)]
            n = int(first(raw, 'pick', default=3)); d['pick'] = n
            ids = [x['id'] for x in d['items']]; texts = [x['t'] for x in d['items']]
            ans = first(raw, 'answer', 'correct')
            if not isinstance(ans, list) or len(ans) != n: ctx.err(loc, 'pick3 correct(answer) 는 길이 %d 배열' % n); continue
            norm = []
            for a in ans:
                if isinstance(a, int) and 0 <= a < len(ids): norm.append(ids[a])      # 숫자 = 0부터 세는 번호
                elif str(a) in ids: norm.append(str(a))
                elif a in texts: norm.append(ids[texts.index(a)])
                else: ctx.err(loc, 'pick3 정답 "%s" 가 보기에 없음' % a)
            d['answer'] = norm; d['hint'] = str(raw.get('hint', '')); d['tries'] = int(first(raw, 'tries', 'max_tries', default=3))
            if len(set(ids)) != len(ids): ctx.err(loc, 'pick3 보기 id 중복')
        elif t == 'code':
            a = str(raw.get('answer', ''))
            if not a.isdigit(): ctx.err(loc, 'code answer 는 숫자 문자열'); continue
            d['answer'] = a; d['digits'] = int(raw.get('digits', len(a)))
            if d['digits'] != len(a): ctx.err(loc, 'code digits(%d) 와 answer 길이(%d) 불일치' % (d['digits'], len(a)))
            d['tries'] = int(first(raw, 'tries', 'max_tries', default=3)); d['hints'] = []
            ht = raw.get('hint', '')
            hi = first(raw, 'hint_if', 'hint_when')
            if ht:
                if raw.get('hint_force') or not hi: d['hints'].append({'c': [], 'any': [], 'min': 0, 't': str(ht)})
                elif isinstance(hi, dict):
                    ids = [canon(x) for x in hi.get('anyOf', hi.get('any', []))]
                    d['hints'].append({'c': [], 'any': ids, 'min': int(hi.get('min', 1)), 't': str(ht)})
                elif isinstance(hi, str): d['hints'].append({'c': parse_cond(hi, ctx, loc), 'any': [], 'min': 0, 't': str(ht)})
            for h in raw.get('hints', []) or []:
                if isinstance(h, str): d['hints'].append({'c': [], 'any': [], 'min': 0, 't': h})
                else:
                    cs = first(h, 'if', 'when', 'need', default='')
                    d['hints'].append({'c': parse_cond(cs, ctx, loc) if cs else [], 'any': [], 'min': 0, 't': h.get('t', h.get('text', ''))})
            d['none'] = str(raw.get('hint_none', ''))
        elif t == 'vote':
            res = raw.get('results') or {}
            cands = first(raw, 'cands', 'candidates', 'options')
            if not isinstance(cands, list) or len(cands) < 2: ctx.err(loc, 'vote 는 candidates(options)가 2명 이상 필요'); continue
            out = []
            for c in cands:
                if isinstance(c, str): c = {'id': c, 'name': c}
                cid = str(c.get('id', ''))
                face = FACE_ALIAS.get(cid, cid)
                acts = do_from(c, ctx, loc)
                if cid in res and isinstance(res[cid], str): acts += parse_actions(res[cid], ctx, loc)
                out.append({'id': cid, 'face': face if face in CHARS else '', 'name': str(first(c, 'name', 'label', 't', default=cid)), 'sub': str(c.get('sub', '')), 'sus': str(c.get('sus', '')), 'do': acts})
            d['cands'] = out
            r = raw.get('refuse')
            if r:
                if isinstance(r, str): r = {'label': r}
                ra = do_from(r, ctx, loc)
                if isinstance(res.get('refuse'), str): ra += parse_actions(res['refuse'], ctx, loc)
                cs = first(r, 'show_if', 'if', 'when', default='')
                d['refuse'] = {'t': str(first(r, 'label', 't', default='투표를 거부한다')), 'c': parse_cond(cs, ctx, loc) if cs else [], 'do': ra}
        elif t == 'guide':
            turns = raw.get('turns')
            if not isinstance(turns, list) or not turns: ctx.err(loc, 'guide 는 turns 가 필요'); continue
            outt = []
            for k, tr in enumerate(turns):
                dirs = first(tr, 'dirs', 'options', default=['앞', '왼쪽', '오른쪽'])
                a = tr.get('answer')
                if isinstance(a, str) and a in dirs: a = dirs.index(a)
                if not isinstance(a, int) or not (0 <= a < len(dirs)): ctx.err(loc, 'guide turns[%d].answer 는 보기의 번호/이름' % k); continue
                outt.append({'see': str(first(tr, 'see', 'say', 'text', default='')), 'dirs': dirs, 'answer': a,
                             'good': str(first(tr, 'say_correct', 'good', default='')), 'bad': str(first(tr, 'say_wrong', 'bad', 'hint', default=''))})
            d['turns'] = outt; d['who'] = str(first(raw, 'viewpoint', 'who', default=''))
            d['timer'] = int(first(raw, 'timer_sec', 'timer', default=0)); d['maxfail'] = int(first(raw, 'maxfail', default=3))
            if 'miss_rule' in raw: d['rule'] = str(raw['miss_rule'])
        elif t == 'cctv':
            order = raw.get('order'); cells = raw.get('cells')
            if order:
                if not isinstance(cells, list): ctx.err(loc, 'cctv order 가 있으면 cells(이름 목록)도 필요'); continue
                for o in order:
                    if o not in cells: ctx.err(loc, 'cctv order "%s" 가 cells 에 없음' % o)
                d['mode'] = 'seq'; d['cells'] = [{'t': c, 'face': NAME2ID.get(c, '')} for c in cells]
                d['order'] = [cells.index(o) if o in cells else -1 for o in order]
                d['guide'] = str(first(raw, 'guide', 'task', 'instruction', default='')); 
                if d['q'] == d['guide']: d['q'] = ''
                d['extra'] = str(raw.get('extra_empty_cell', ''))
                hk = [k for k in raw if k.startswith('hint_if')]
                if hk:
                    cs = hk[0][len('hint_if'):].lstrip('_')
                    d['hint'] = {'c': parse_cond(cs, ctx, loc) if cs else [], 't': str(raw.get('hint_text') or ('순서: ' + ' → '.join(order)))}
                d['lives'] = int(raw.get('lives', 3))
            else:
                d['mode'] = 'odd'; d['rounds'] = int(raw.get('rounds', 3)); d['lives'] = int(raw.get('lives', 3))
        op['d'] = d

def check_graph(ops, labels, label_loc, src, ctx, strict):
    n = len(ops)
    def tgt(l, loc):
        if l not in labels: ctx.err(loc, '@goto/라벨 "%s" 가 없음' % l); return None
        return labels[l]
    # 모든 라벨 참조 검증
    refs = {}   # idx -> list of target pcs
    for idx, op in enumerate(ops):
        loc = src[idx]; out = []
        def addact(acts):
            for a in acts:
                if a[0] == 'goto':
                    t = tgt(a[1], loc)
                    if t is not None: out.append(t)
        k = op['o']
        if k == 'goto':
            t = tgt(op['l'], loc); refs[idx] = [t] if t is not None else []; continue
        if k == 'choice':
            for o in op['opts']: addact(o['a'])
            if op['to']:
                t = tgt(op['to'], loc)
                if t is not None: out.append(t)
            if op['def'] and not (1 <= op['def'] <= len(op['opts'])): ctx.err(loc, '@choice default=%d 가 선택지 수(%d)를 벗어남' % (op['def'], len(op['opts'])))
            if op['timer'] and not op['opts']: pass
            hasfall = any(not o['c'] for o in op['opts'])
            if op['opts'] and not hasfall: ctx.warn(loc, '@choice 의 모든 선택지에 조건이 붙음(조건이 다 틀리면 멈춤)')
            refs[idx] = out; continue
        if k == 'puz':
            for key in ('ok', 'fail', 'skip'): addact(op['d'].get(key, []))
            for c in op['d'].get('cands', []): addact(c['do'])
            if op['d'].get('refuse'): addact(op['d']['refuse']['do'])
            refs[idx] = out; continue
    # 도달성 BFS
    seen = [False] * n; stack = [0] if n else []
    while stack:
        p = stack.pop()
        if p < 0 or p >= n or seen[p]: continue
        seen[p] = True; op = ops[p]; k = op['o']
        if k == 'end': continue
        if k == 'goto': stack.extend(refs.get(p, [])); continue
        if k == 'jmp': stack.append(op['to']); continue
        if k == 'jf': stack.append(op['to']); stack.append(p + 1); continue
        if k == 'choice':
            stack.extend(refs.get(p, []))
            # 선택지가 goto 없이 끝나면 선택 다음 줄로 이어짐
            if any(not any(a[0] == 'goto' for a in o['a']) for o in op['opts']): stack.append(p + 1)
            continue
        if k == 'puz':
            d = op['d']; stack.extend(refs.get(p, []))
            # ok/fail/skip/cands 중 goto 없는 경로가 있으면 다음 줄로 이어짐
            paths = []
            if op['type'] == 'vote':
                paths = [c['do'] for c in d['cands']] + ([d['refuse']['do']] if d.get('refuse') else [])
            else:
                paths = [d.get('ok', []), d.get('fail', [])] + ([d['skip']] if 'skip' in d else [])
            if any(not any(a[0] == 'goto' for a in pa) for pa in paths): stack.append(p + 1)
            continue
        stack.append(p + 1)
    inv = {}
    for l, p in labels.items(): inv.setdefault(p, []).append(l)
    for l, p in labels.items():
        if p >= n: ctx.err(label_loc[l], '라벨 "%s" 가 파일 끝에 있어 이어지는 내용이 없음' % l)
        elif not seen[p]: (ctx.err if strict else ctx.warn)(label_loc[l], '도달할 수 없는 라벨 "%s" (어떤 @goto 도·흐름도 여기로 오지 않음)' % l)
    # 끝이 막힘
    if n and not seen[n - 1] is False and ops[-1]['o'] not in ('end', 'goto', 'jmp'):
        ctx.err(src[-1], '이야기가 엔딩/@goto 없이 끝남(마지막 줄 뒤로 이어질 곳이 없음)')
    for p in range(n):
        if seen[p] and ops[p]['o'] in ('say', 'nar', 'tho') and p + 1 >= n:
            ctx.err(src[p], '마지막 줄이 대사/지문임 — @ending 이 필요')
    # 죽은 줄(앞 줄이 엔딩/goto 인데 라벨도 없는 줄들)
    p = 0
    while p < n:
        if not seen[p]:
            q = p
            while q < n and not seen[q]: q += 1
            lines = sum(1 for z in range(p, q) if ops[z]['o'] in ('say', 'nar', 'tho'))
            if lines: (ctx.err if strict else ctx.warn)(src[p], '도달할 수 없는 구간(대사·지문 %d줄, ~%s). 앞의 @goto/@ending 뒤에 @label 이 빠졌는지 확인' % (lines, src[q - 1]))
            p = q
        else: p += 1
    # 엔딩 도달
    return seen

def check_vars(ops, ctx, src):
    setv = set(BUILTIN_VARS); readv = {}
    def see_set(acts):
        for a in acts:
            if a[0] in ('set', 'add'): setv.add(a[1])
    for idx, op in enumerate(ops):
        k = op['o']
        if k in ('set', 'add', 'unset'): setv.add(op['k'])
        elif k == 'jf':
            for c in op['c']: readv.setdefault(c[0], src[idx])
        elif k == 'choice':
            for o in op['opts']:
                see_set(o['a'])
                for c in o['c']: readv.setdefault(c[0], src[idx])
        elif k == 'puz':
            d = op['d']
            for key in ('ok', 'fail', 'skip'): see_set(d.get(key, []))
            for c in d.get('cands', []): see_set(c['do'])
            if d.get('refuse'): see_set(d['refuse']['do'])
            for h in d.get('hints', []):
                for c in h['c']: readv.setdefault(c[0], src[idx])
    # 단서 id 도 조건에 쓸 수 있다(수첩 보유 여부)
    clue_ids = {op['id'] for op in ops if op['o'] == 'clue'}
    for name, loc in readv.items():
        if name not in setv and name not in clue_ids:
            ctx.warn(loc, '조건에서 읽는 "%s" 를 어디서도 @set/@add/@clue 하지 않음(오타?)' % name)

def stats(ops, chapters, endings):
    lines = sum(1 for o in ops if o['o'] in ('say', 'nar', 'tho'))
    puz = [o['type'] for o in ops if o['o'] == 'puz']
    per = []
    for k, ch in enumerate(chapters):
        end = chapters[k + 1]['pc'] if k + 1 < len(chapters) else len(ops)
        per.append((ch['t'], sum(1 for o in ops[ch['pc']:end] if o['o'] in ('say', 'nar', 'tho'))))
    return lines, puz, per

def build(files, strict=False):
    ctx = Ctx()
    ops, labels, label_loc, chapters, clues, endings, src = parse_files(files, ctx)
    check_puzzles(ops, src, ctx)
    # 제한시간 초과 목적지: timeout=라벨 > 같은 장 안의 '*timeout*' 라벨(선택지 뒤 가장 가까운 것) > 보이는 선택지 중 마지막 항목(엔진 기본)
    for idx, op in enumerate(ops):
        if op['o'] != 'choice' or not op['timer'] or op['to']: continue
        ci = max([k for k, c in enumerate(chapters) if c['pc'] <= idx] or [0])
        lo = chapters[ci]['pc'] if chapters else 0
        hi = chapters[ci + 1]['pc'] if ci + 1 < len(chapters) else len(ops)
        cand = sorted((p2, l) for l, p2 in labels.items() if lo <= p2 < hi and re.search(r'(^|_)timeout', l))
        if cand:
            after = [c for c in cand if c[0] > idx]
            op['to'] = (after or cand)[0][1]
    # @card 가 없는 장은 엔진이 ## 제목으로 카드를 대신 보여 준다(chap.c=0)
    k = 0
    for op in ops:
        if op['o'] == 'chap': op['c'] = 1 if chapters[k]['card'] else 0; k += 1
    check_vars(ops, ctx, src)
    seen = check_graph(ops, labels, label_loc, src, ctx, strict)
    # 엔딩 도달 여부
    reach_end = {ops[p]['id'] for p in range(len(ops)) if seen[p] and ops[p]['o'] == 'end'}
    for e in endings:
        if e['id'] not in reach_end: (ctx.err if strict else ctx.warn)('엔딩', '엔딩 "%s" 에 도달하는 길이 없음' % e['id'])
    for op in ops:
        op.pop('_loc', None)
        if op['o'] == 'choice':
            for o in op['opts']: o.pop('_loc', None)
    lines, puz, per = stats(ops, chapters, endings)
    story = {
        'v': 2, 'ops': ops, 'labels': labels,
        'chapters': [{'n': c['n'], 't': c['t'], 'pc': c['pc']} for c in chapters],
        'clues': clues, 'endings': endings,
        'meta': {'lines': lines, 'puzzles': puz, 'chapters': len(chapters)}
    }
    return story, ctx, per

def render_js(story):
    out = ['const STORY={', ' v:%d,' % story['v']]
    out.append(' meta:%s,' % json.dumps(story['meta'], ensure_ascii=False))
    out.append(' chapters:%s,' % json.dumps(story['chapters'], ensure_ascii=False))
    out.append(' clues:%s,' % json.dumps(story['clues'], ensure_ascii=False))
    out.append(' endings:%s,' % json.dumps(story['endings'], ensure_ascii=False))
    out.append(' labels:%s,' % json.dumps(story['labels'], ensure_ascii=False))
    out.append(' ops:[')
    for op in story['ops']: out.append('  ' + json.dumps(op, ensure_ascii=False, separators=(',', ':')) + ',')
    out.append(' ]', )
    out.append('};')
    return '\n'.join(out)


# --import 로 원고를 가져올 때 자동으로 적용하는 통합 수정(이미 들어 있으면 건너뜀). 산문은 건드리지 않고 분기 지시어만 고친다.
PATCHES = []   # (파일, 찾을 글, 바꿀 글) — 필요할 때만 채운다

def import_dir(srcdir):
    import shutil
    dst = os.path.join(ROOT, 'data', 'novel', 'ch'); os.makedirs(dst, exist_ok=True)
    files = sorted(glob.glob(os.path.join(srcdir, 'ch_*.txt')))
    if not files: print('가져올 ch_*.txt 가 없음: %s' % srcdir); return False
    for f in files: shutil.copy(f, os.path.join(dst, os.path.basename(f)))
    for name, old, new in PATCHES:
        p = os.path.join(dst, name)
        if not os.path.exists(p): continue
        t = open(p, encoding='utf-8').read()
        if new.split('\n')[0] in t: continue
        if old not in t: print('경고 통합 수정 자리를 못 찾음(%s): %s' % (name, old.split('\n')[0])); continue
        open(p, 'w', encoding='utf-8').write(t.replace(old, new, 1)); print('통합 수정 적용: %s' % name)
    print('원고 %d개 가져옴' % len(files)); return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src'); ap.add_argument('--out', default=os.path.join(ROOT, 'novel.html'))
    ap.add_argument('--check', action='store_true'); ap.add_argument('--json'); ap.add_argument('--strict', action='store_true'); ap.add_argument('--import', dest='imp', help='이 폴더의 ch_*.txt 를 data/novel/ch 로 복사(+통합 수정)한 뒤 빌드')
    a = ap.parse_args()
    if a.imp and not import_dir(a.imp): return 1
    src = a.src
    if not src:
        d = os.path.join(ROOT, 'data', 'novel', 'ch')
        src = d if glob.glob(os.path.join(d, 'ch_*.txt')) else os.path.join(ROOT, 'data', 'novel', 'fallback_short.txt')
        print('원본: %s%s' % (os.path.relpath(src, ROOT), ' (장편 원고가 아직 없어 짧은 판을 씀)' if src.endswith('.txt') else ''))
    files = [src] if os.path.isfile(src) else sorted(glob.glob(os.path.join(src, 'ch_*.txt')), key=file_key)
    if not files: print('원본 파일이 없습니다: %s' % src); return 1
    story, ctx, per = build(files, a.strict)
    for w in ctx.warns: print('경고 ' + w)
    for e in ctx.errors: print('오류 ' + e)
    print('파일 %d개 · 장 %d · 대사/지문 %d줄 · 퍼즐 %s · 단서 %d종 · 엔딩 %s' % (len(files), len(per), story['meta']['lines'], story['meta']['puzzles'] or '없음', len(story['clues']), [e['id'] for e in story['endings']]))
    for t, n in per: print('  %-24s %4d줄' % (t, n))
    est = story['meta']['lines'] * 4 + len(story['meta']['puzzles']) * 60
    print('예상 플레이(한 경로가 아니라 전체 합): 약 %d분' % (est // 60))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f: json.dump(story, f, ensure_ascii=False)
    if ctx.errors: print('--> 오류 %d건 때문에 쓰지 않음' % len(ctx.errors)); return 1
    if a.check: return 0
    html = open(a.out, encoding='utf-8').read()
    b, e = '/*STORY:BEGIN*/', '/*STORY:END*/'
    if html.count(b) != 1 or html.count(e) != 1: print('%s 에 STORY 표식이 정확히 한 번씩 있어야 함(지금 %d/%d)' % (a.out, html.count(b), html.count(e))); return 1
    i, j = html.find(b), html.find(e)
    if i < 0 or j < 0: print('%s 에 STORY 표식이 없음' % a.out); return 1
    html = html[:i + len(b)] + '\n' + render_js(story) + '\n' + html[j:]
    open(a.out, 'w', encoding='utf-8').write(html)
    print('작성: %s' % os.path.relpath(a.out, ROOT)); return 0

if __name__ == '__main__':
    sys.exit(main())
