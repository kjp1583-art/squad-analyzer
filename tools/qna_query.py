# -*- coding: utf-8 -*-
"""스쿼드 Q&A 클랜 데이터 조회 도구 (2026-07-21)

디스코드 Q&A 자동응답 태스크가 호출한다. 스케줄 태스크는 `py ...`로 시작하는
단일 명령만 쓸 수 있으므로, 즉석 분석 대신 이 도구를 통해 조회한다.

사용법:
  py qna_query.py item 월식          누가 그 아이템을 사는가
  py qna_query.py rune 정복자         누가 그 룬을 드는가
  py qna_query.py spell 순간이동       누가 그 스펠을 드는가
  py qna_query.py champ 리신          그 챔프의 클랜 표준 빌드·룬·주요 플레이어
  py qna_query.py player 우거         그 사람의 챔프/룬/아이템 성향
  py qna_query.py h2h 우거 프싱        두 사람 맞대결 전적
  py qna_query.py tier 우거           내부티어 판단용 종합지표(MVP/ACE/역적·점수·KDA·
                                     킬관여·딜량·솔랭피크·견제지수, 클랜 평균 대비)

★ 한계 (답변 시 반드시 반영할 것)
  - 아이템은 '게임 종료 시점 인벤토리'다. 구매 순서가 아니므로
    "1코어/2코어" 같은 빌드 순서 질문에는 답할 수 없다.
  - 아이템·룬 기록은 2026-07-13부터만 존재한다(전체 전적의 약 27%).
    반드시 "최근 기록 기준"임을 밝힐 것.
"""
import urllib.request, urllib.parse, json, re, sys, os, collections, time

sys.stdout.reconfigure(encoding='utf-8')

SID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU'
UA = {'User-Agent': 'Mozilla/5.0'}
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_ddragon_cache.json')
CACHE_TTL = 86400 * 3


def fetch(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode('utf-8')


def gviz(sheet, tq):
    url = ('https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:json&sheet=%s&headers=1&tq=%s'
           % (SID, urllib.parse.quote(sheet), urllib.parse.quote(tq)))
    return json.loads(re.search(r'setResponse\((.*)\)', fetch(url, 240), re.S).group(1))


def cells(resp):
    return [[(x or {}).get('v') if x else None for x in r['c']] for r in resp['table']['rows']]


def ddragon():
    """아이템/룬 ID ↔ 한글명. 3일 캐시."""
    if os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < CACHE_TTL:
        try:
            return json.load(open(CACHE, encoding='utf-8'))
        except Exception:
            pass
    v = json.loads(fetch('https://ddragon.leagueoflegends.com/api/versions.json', 60))[0]
    items = json.loads(fetch('https://ddragon.leagueoflegends.com/cdn/%s/data/ko_KR/item.json' % v, 120))['data']
    runes = json.loads(fetch('https://ddragon.leagueoflegends.com/cdn/%s/data/ko_KR/runesReforged.json' % v, 60))
    rmap = {}
    for tree in runes:
        rmap[str(tree['id'])] = tree['name']
        for s in tree['slots']:
            for r in s['runes']:
                rmap[str(r['id'])] = r['name']
    data = {'ver': v,
            'item': {k: d['name'] for k, d in items.items()},
            'rune': rmap}
    try:
        json.dump(data, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception:
        pass
    return data


SPELL_KO = {
    'SummonerFlash': '점멸', 'SummonerTeleport': '순간이동', 'SummonerDot': '점화',
    'SummonerSmite': '강타', 'SummonerHeal': '회복', 'SummonerBarrier': '방어막',
    'SummonerExhaust': '탈진', 'SummonerBoost': '정화', 'SummonerHaste': '유체화',
    'SummonerMana': '총명', 'SummonerSnowball': '설인 돌진',
}


def norm(s):
    return re.sub(r'\s+', '', str(s or '').split('#')[0]).lower()


NAME_ALIASES = {}  # 대표닉 -> {과거닉/부계닉, ...}
CANON = {}         # 시트 표기 -> 대표닉 (load() 가 채운다. tier 모드가 재사용)


def load():
    """전적 로드 + 중복제거 + 부계·구계정(닉변) 통합.

    ★ 닉변 추적: 같은 PUUID = 같은 사람이므로, PUUID로 묶어 **가장 최근 경기의
    표기**를 대표닉으로 삼는다. LINK_ACCOUNT(부계 등록)만 믿으면 등록 안 된
    옛 계정이 통계에서 누락된다(예: RayB의 옛 계정 '아기빠급이').
    """
    alias = {}
    try:
        for v in cells(gviz('LINK_ACCOUNT', 'select * limit 1000')):
            if v and len(v) >= 2 and v[0] and v[1]:
                alias[str(v[0]).strip()] = str(v[1]).strip()
    except Exception:
        pass
    rows = cells(gviz('CLASSIC_NORMAL', 'select A,B,C,D,E,F,G,I,O,P,Q,R limit 30000'))
    # 0게임ID 1날짜 2이름 3PUUID 4진영 5포지션 6챔프 7결과 8아이템 9주룬 10보조룬 11스펠
    seen, raw = set(), []
    for r in rows:
        k = (r[0], r[2])
        if k in seen:
            continue
        seen.add(k)
        raw.append(r)

    canon = {}
    bypu = collections.defaultdict(list)
    for r in raw:
        pu = str(r[3] or '').strip().lower()
        if pu:
            bypu[pu].append(r)
    for pu, rs in bypu.items():
        rep = str(max(rs, key=lambda x: str(x[1] or ''))[2]).strip()  # 최근 경기 표기
        for x in rs:
            canon[str(x[2]).strip()] = rep
    for sub, main in alias.items():          # 부계 등록분(PUUID 없는 경우 대비)
        canon[sub] = canon.get(main, main)

    NAME_ALIASES.clear()
    CANON.clear()
    CANON.update(canon)
    R = []
    for r in raw:
        n = str(r[2]).strip()
        rep = canon.get(n, n)
        if rep != n:
            NAME_ALIASES.setdefault(rep, set()).add(n)
        r[2] = rep
        del r[3]                              # 이후 인덱스는 PUUID 없던 시절과 동일
        R.append(r)
    return R


def decided(rows):
    """'결과 대기'(미확정) 경기는 승률 집계에서 제외 — 안 빼면 패배로 세어진다."""
    return [r for r in rows if str(r[6] or '').strip() in ('승리', '패배')]


def item_ids(r):
    s = str(r[7] or '')
    if not s or '기록' in s:
        return []
    return [x for x in s.split('|') if x.isdigit()]


def find_all(query, pool):
    """이름 표기 흔들림(예: '리신' vs '리 신')을 모두 모아 반환.
    시트에 같은 챔프/사람이 띄어쓰기 차이로 여러 표기가 섞여 있어서,
    하나만 고르면 통계가 반토막 난다."""
    q = norm(query)
    if not q:
        return set()
    exact = {n for n in pool if norm(n) == q}
    if exact:
        return exact
    return {n for n in pool if q in norm(n)}


def find_name(query, pool):
    """대표 표기 하나(표시용). 집계는 find_all 을 쓸 것."""
    s = find_all(query, pool)
    return sorted(s)[0] if s else None


def find_players(query, pool):
    """사람 조회. 현재닉으로 못 찾으면 **옛 닉/부계닉**으로도 찾아준다."""
    s = find_all(query, pool)
    if s:
        return s
    q = norm(query)
    hit = {rep for rep, al in NAME_ALIASES.items() if any(norm(a) == q for a in al)}
    if not hit:
        hit = {rep for rep, al in NAME_ALIASES.items() if any(q in norm(a) for a in al)}
    return hit


def period(R, key=None):
    ds = [str(r[1])[:10] for r in R if (key is None or key(r))]
    return (min(ds), max(ds)) if ds else ('?', '?')


def wr(w, n):
    return '%d전 %d승 %d패(%.0f%%)' % (n, w, n - w, 100.0 * w / n) if n else '기록 없음'


# ------------------------------------------------------------------ modes
def m_item(R, dd, arg):
    hits = [(k, v) for k, v in dd['item'].items() if arg in v]
    if not hits:
        print('"%s" 이름의 아이템을 못 찾았어요.' % arg); return
    # 같은 이름 여러 ID(1xxxxx 변형) 전부 포함
    names = {v for _, v in hits}
    ids = {k for k, v in dd['item'].items() if v in names}
    sub = [r for r in R if set(item_ids(r)) & ids]
    if not sub:
        print('%s: 최근 기록에서 구매 사례가 없어요.' % list(names)[0]); return
    lo, hi = period(sub)
    who = collections.defaultdict(lambda: [0, 0, 0])   # 구매횟수, 승패확정판, 승
    ch = collections.Counter()
    for r in sub:
        who[r[2]][0] += 1
        if str(r[6] or '').strip() in ('승리', '패배'):
            who[r[2]][1] += 1
            who[r[2]][2] += 1 if r[6] == '승리' else 0
        ch[re.sub(r'\s+','',str(r[5] or ''))] += 1
    print('■ %s — 총 %d회 / %d명 (%s~%s 기록)' % (list(names)[0], len(sub), len(who), lo, hi))
    for n, (c, d, w) in sorted(who.items(), key=lambda kv: -kv[1][0])[:10]:
        print('   %-22s %2d회 %s' % (n, c, wr(w, d)))
    print('   자주 쓰는 챔프: ' + ', '.join('%s %d' % (c, n) for c, n in ch.most_common(5)))
    print('   ※ 아이템은 게임 종료 시점 인벤토리라 구매 순서(1코어 등)는 알 수 없어요.')


def m_rune(R, dd, arg):
    ids = {k for k, v in dd['rune'].items() if arg in v}
    if not ids:
        print('"%s" 이름의 룬을 못 찾았어요.' % arg); return
    nm = dd['rune'][sorted(ids)[0]]
    sub = [r for r in R if str(r[8] or '').split('|')[0] in ids
           or str(r[8] or '') and set(str(r[8]).split('|')) & ids
           or str(r[9] or '') in ids]
    if not sub:
        print('%s: 최근 기록에서 사용 사례가 없어요.' % nm); return
    lo, hi = period(sub)
    who = collections.defaultdict(lambda: [0, 0, 0]); ch = collections.Counter()
    for r in sub:
        who[r[2]][0] += 1
        if str(r[6] or '').strip() in ('승리', '패배'):
            who[r[2]][1] += 1
            who[r[2]][2] += 1 if r[6] == '승리' else 0
        ch[re.sub(r'\s+','',str(r[5] or ''))] += 1
    print('■ 룬 %s — 총 %d회 / %d명 (%s~%s 기록)' % (nm, len(sub), len(who), lo, hi))
    for n, (c, d, w) in sorted(who.items(), key=lambda kv: -kv[1][0])[:10]:
        print('   %-22s %2d회 %s' % (n, c, wr(w, d)))
    print('   자주 쓰는 챔프: ' + ', '.join('%s %d' % (c, n) for c, n in ch.most_common(5)))


def m_spell(R, dd, arg):
    ids = {k for k, v in SPELL_KO.items() if arg in v} or {arg}
    sub = [r for r in R if set(str(r[10] or '').split('|')) & ids]
    if not sub:
        print('"%s" 스펠 기록을 못 찾았어요.' % arg); return
    lo, hi = period(sub)
    who = collections.Counter(r[2] for r in sub)
    ch = collections.Counter(r[5] for r in sub)
    print('■ 스펠 %s — 총 %d회 (%s~%s 기록)' % (arg, len(sub), lo, hi))
    print('   많이 드는 사람: ' + ', '.join('%s %d회' % (n, c) for n, c in who.most_common(8)))
    print('   자주 쓰는 챔프: ' + ', '.join('%s %d' % (c, n) for c, n in ch.most_common(6)))


def m_champ(R, dd, arg):
    pool = {r[5] for r in R if r[5]}
    names = find_all(arg, pool)
    if not names:
        print('"%s" 챔피언 기록을 못 찾았어요.' % arg); return
    nm = sorted(names)[0]
    sub = [r for r in R if r[5] in names]
    dec = decided(sub)
    w = sum(1 for r in dec if r[6] == '승리')
    print('■ %s — 클랜 %s' % (nm, wr(w, len(dec))))
    who = collections.defaultdict(lambda: [0, 0])
    for r in dec:
        who[r[2]][0] += 1
        who[r[2]][1] += 1 if r[6] == '승리' else 0
    print('   주요 플레이어: ' + ', '.join('%s %d판(%.0f%%)' % (n, c, 100.0 * x / c)
                                      for n, (c, x) in sorted(who.items(), key=lambda kv: -kv[1][0])[:6]))
    withit = [r for r in sub if item_ids(r)]
    if withit:
        lo, hi = period(withit)
        cnt = collections.Counter()
        for r in withit:
            for i in set(item_ids(r)):
                nmi = dd['item'].get(i)
                if nmi and not any(k in nmi for k in ('와드', '렌즈', '개조', '물약')):
                    cnt[nmi] += 1
        print('   자주 가는 아이템(%d판 기준, %s~%s): ' % (len(withit), lo, hi)
              + ', '.join('%s %d%%' % (k, round(100.0 * c / len(withit))) for k, c in cnt.most_common(6)))
    withr = [r for r in sub if r[8]]
    if withr:
        key = collections.Counter(dd['rune'].get(str(r[8]).split('|')[0], '?') for r in withr)
        sec = collections.Counter(dd['rune'].get(str(r[9]), '?') for r in withr if r[9])
        sp = collections.Counter('+'.join(SPELL_KO.get(x, x) for x in str(r[10]).split('|')) for r in withr if r[10])
        print('   핵심룬: ' + ', '.join('%s %d회' % (k, c) for k, c in key.most_common(3)))
        print('   보조계열: ' + ', '.join('%s %d회' % (k, c) for k, c in sec.most_common(3)))
        print('   스펠: ' + ', '.join('%s %d회' % (k, c) for k, c in sp.most_common(3)))
    print('   ※ 아이템/룬 기록은 최근 것만 있어요. 구매 순서는 알 수 없어요.')


def m_player(R, dd, arg):
    pool = {r[2] for r in R}
    names = find_players(arg, pool)
    if not names:
        print('"%s" 소환사를 못 찾았어요.' % arg); return
    nm = sorted(names)[0]
    sub = [r for r in R if r[2] in names]
    dec = decided(sub)
    w = sum(1 for r in dec if r[6] == '승리')
    pos = collections.Counter(r[4] for r in dec)
    ch = collections.defaultdict(lambda: [0, 0])
    for r in dec:
        ch[r[5]][0] += 1
        ch[r[5]][1] += 1 if r[6] == '승리' else 0
    print('■ %s — 통산 %s' % (nm, wr(w, len(dec))))
    old = set().union(*[NAME_ALIASES.get(n, set()) for n in names]) if names else set()
    if old:
        print('   합산된 옛닉/부계: ' + ', '.join(sorted(old)))
    if len(sub) - len(dec):
        print('   (결과 대기 %d판은 승률에서 제외)' % (len(sub) - len(dec)))
    print('   포지션: ' + ', '.join('%s %d판' % (p, c) for p, c in pos.most_common()))
    print('   모스트: ' + ', '.join('%s %d판(%.0f%%)' % (c, n, 100.0 * x / n)
                                 for c, (n, x) in sorted(ch.items(), key=lambda kv: -kv[1][0])[:6]))
    withr = [r for r in sub if r[8]]
    if withr:
        lo, hi = period(withr)
        key = collections.Counter(dd['rune'].get(str(r[8]).split('|')[0], '?') for r in withr)
        print('   자주 드는 핵심룬(%s~%s): ' % (lo, hi) + ', '.join('%s %d회' % (k, c) for k, c in key.most_common(4)))
    withit = [r for r in sub if item_ids(r)]
    if withit:
        cnt = collections.Counter()
        for r in withit:
            for i in set(item_ids(r)):
                nmi = dd['item'].get(i)
                if nmi and not any(k in nmi for k in ('와드', '렌즈', '개조', '물약')):
                    cnt[nmi] += 1
        print('   자주 가는 아이템: ' + ', '.join('%s %d회' % (k, c) for k, c in cnt.most_common(6)))


def m_h2h(R, dd, a, b):
    pool = {r[2] for r in R}
    sa, sb = find_players(a, pool), find_players(b, pool)
    if not sa or not sb:
        print('소환사를 못 찾았어요: %s' % (a if not sa else b)); return
    na, nb = sorted(sa)[0], sorted(sb)[0]
    bygame = collections.defaultdict(list)
    for r in R:
        bygame[r[0]].append(r)
    aw = bw = 0
    same = same_w = wait = bad = 0
    for gid, g in bygame.items():
        ra = [r for r in g if r[2] in sa]
        rb = [r for r in g if r[2] in sb]
        if not ra or not rb:
            continue
        ra, rb = ra[0], rb[0]
        # 결과 대기(미확정) 판은 승패 집계에서 제외
        if not decided([ra]) or not decided([rb]):
            wait += 1
            continue
        if ra[3] == rb[3]:          # 3=진영 (PUUID 열은 load 에서 제거됨)
            same += 1
            same_w += 1 if ra[6] == '승리' else 0
            continue
        # 양팀 모두 승리로 기록된 오류 판 제외
        if ra[6] == rb[6]:
            bad += 1
            continue
        if ra[6] == '승리':
            aw += 1
        else:
            bw += 1
    tot = aw + bw
    print('■ %s vs %s 맞대결' % (na, nb))
    if not tot:
        print('   맞붙은 기록이 없어요.' + (' (같은 팀으로 %d판)' % same if same else ''))
        return
    print('   %d전 — %s %d승 / %s %d승 (%s 승률 %.0f%%)' % (tot, na, aw, nb, bw, na, 100.0 * aw / tot))
    if same:
        print('   같은 팀으로 뛴 판: %d판 (%d승 %d패)' % (same, same_w, same - same_w))
    for lbl, c in (('결과 대기', wait), ('양팀 모두 승리로 기록된 오기록', bad)):
        if c:
            print('   ※ %s %d판은 집계에서 제외했어요.' % (lbl, c))


def load_eval():
    """tier 모드용 확장 열. load() 를 먼저 호출해 CANON 이 채워져 있어야 한다."""
    rows = cells(gviz('CLASSIC_NORMAL', 'select A,C,E,G,H,I,J,L,M,N,S limit 30000'))
    # 0게임ID 1이름 2진영 3챔피언 4밴 5결과 6매치평가 7KDA 8점수 9딜량 10지표
    seen, E = set(), []
    for r in rows:
        k = (r[0], r[1])
        if k in seen:
            continue
        seen.add(k)
        n = str(r[1] or '').strip()
        r[1] = CANON.get(n, n)
        E.append(r)
    return E


def _kda_of(s):
    m = re.match(r'\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)', str(s or ''))
    return tuple(int(x) for x in m.groups()) if m else None


def _metric(s, key):
    m = re.search(r'\b%s(-?\d+)' % key, str(s or ''))
    return int(m.group(1)) if m else None


def _rated(r):
    """'평가 대기'·빈칸은 평가 집계에서 제외 — 아직 평가가 안 붙은 판이다."""
    return str(r[6] or '').strip() in ('MVP', 'ACE', '역적', '평가 없음')


def _tier_tabs():
    """CLAN_TIERS / PEAK_SEASONS / TIER_HISTORY. 한 탭이 죽어도 나머지는 살린다."""
    out = {}
    for tab, tq in (('CLAN_TIERS', 'select * limit 1000'),
                    ('PEAK_SEASONS', 'select * limit 1000'),
                    ('TIER_HISTORY', 'select * limit 5000')):
        try:
            out[tab] = cells(gviz(tab, tq))
        except Exception:
            out[tab] = []
    return out


BP_MIN_CHAMP, BP_MIN_PRESENT, BP_MIN_ABSENT = 4, 8, 20


def _pressure(E):
    """견제 압력 — 웹 명예의전당 '견제압력 TOP10'과 **동일한 정의**로 계산한다.

    targeted(%p) = (내가 낀 판에서 상대 진영이 그 챔프를 밴한 비율)
                 − (내가 없는 판에서 그 챔프가 밴된 비율)
    두 번째 항은 양팀 밴을 한 팀 기준으로 맞추려고 0.5를 곱한다(웹과 동일).
    빼기를 하는 이유는 **원래 인기 밴인 챔프의 영향을 제거**하기 위함이다.
    z>1.5 인 챔프만 유효로 보고, 그중 targeted 최대가 그 사람의 대표 견제 챔프.

    ⚠ 밴은 '무섭다'뿐 아니라 '상대하기 짜증난다'에도 걸리므로 실력 지표가 아니다.
    """
    bygame = collections.defaultdict(list)
    seen = set()
    for r in E:                                   # (게임ID, 이름) 중복행 제거 — 안 하면 밴율이 왜곡된다
        k = (r[0], r[1])
        if k in seen:
            continue
        seen.add(k)
        bygame[r[0]].append(r)
    games = [g for g in bygame.values() if len(g) >= 8]
    ginfo = []
    for g in games:
        byside, allb, side = collections.defaultdict(set), set(), {}
        ok = False
        for x in g:
            side[x[1]] = x[2]                     # 1=이름 2=진영
            b = str(x[4] or '').strip()           # 4=밴
            if b and b not in ('밴 없음', '밴 안함'):
                byside[x[2]].add(b)
                allb.add(b)
                ok = True
        if ok:
            ginfo.append((byside, allb, side))

    pc = collections.defaultdict(collections.Counter)
    for g in games:
        for x in g:
            if x[3]:                              # 3=챔피언
                pc[x[1]][x[3]] += 1

    out = {}
    for who, chs in pc.items():
        mains = [(c, n) for c, n in chs.most_common(6) if n >= BP_MIN_CHAMP]
        if not mains:
            continue
        present = [gi for gi in ginfo if who in gi[2]]
        absent = [gi for gi in ginfo if who not in gi[2]]
        if len(present) < BP_MIN_PRESENT or len(absent) < BP_MIN_ABSENT:
            continue
        res = []
        for c, n in mains:
            ino = sum(1 for byside, _, side in present
                      if c in byside.get('레드팀' if side[who] == '블루팀' else '블루팀', set()))
            outo = sum(0.5 for _, allb, _ in absent if c in allb)
            a, b = ino / len(present), outo / len(absent)
            se = (max(a * (1 - a), 1e-6) / len(present) + max(b * (1 - b), 1e-6) / len(absent)) ** 0.5
            res.append({'champ': c, 'games': n, 'present': 100 * a, 'absent': 100 * b,
                        'targeted': 100 * (a - b), 'z': (a - b) / se})
        cand = sorted((x for x in res if x['z'] > 1.5), key=lambda x: -x['targeted'])
        if cand:
            out[who] = cand
    return out


def m_tier(R, E, arg):
    pool = {r[2] for r in R}
    names = find_players(arg, pool)
    if not names:
        print('"%s" 소환사를 못 찾았어요.' % arg); return
    nm = sorted(names)[0]
    sub = [r for r in E if r[1] in names]
    if not sub:
        print('"%s" 기록을 못 찾았어요.' % arg); return

    dec = [r for r in sub if str(r[5] or '').strip() in ('승리', '패배')]
    w = sum(1 for r in dec if r[5] == '승리')
    print('■ %s — 내부티어 판단용 종합지표' % nm)

    tabs = _tier_tabs()
    key = norm(nm)
    cur = next((v[1] for v in tabs['CLAN_TIERS']
                if len(v) >= 2 and norm(v[0]) == key), None)
    print('   내부티어: %s' % (cur if cur else '기록 없음'))
    hist = [v for v in tabs['TIER_HISTORY'] if len(v) >= 4 and norm(v[0]) == key]
    for v in hist[-3:]:
        print('     변동: %s → %s (%s)' % (v[1], v[2], v[3]))
    if not hist:
        print('     변동 이력 없음 (기준 스냅샷 이후 그대로)')

    print('   통산: %s' % wr(w, len(dec)))

    rated = [r for r in sub if _rated(r)]
    allr = [r for r in E if _rated(r)]
    if rated:
        c = collections.Counter(str(r[6]).strip() for r in rated)
        ca = collections.Counter(str(r[6]).strip() for r in allr)
        n, na = len(rated), max(1, len(allr))
        print('   MVP %d회(%.1f%%) · ACE %d회(%.1f%%) · 역적 %d회(%.1f%%)  [%d판 평가 기준]'
              % (c['MVP'], 100.0 * c['MVP'] / n, c['ACE'], 100.0 * c['ACE'] / n,
                 c['역적'], 100.0 * c['역적'] / n, n))
        print('     ↳ 클랜 평균: MVP %.1f%% · ACE %.1f%% · 역적 %.1f%%'
              % (100.0 * ca['MVP'] / na, 100.0 * ca['ACE'] / na, 100.0 * ca['역적'] / na))

    def avg(rows, i):
        v = [float(r[i]) for r in rows if isinstance(r[i], (int, float))]
        return (sum(v) / len(v)) if v else None

    ms, mall = avg(sub, 8), avg(E, 8)
    if ms is not None and mall is not None:
        per = collections.defaultdict(list)
        for r in E:
            if isinstance(r[8], (int, float)):
                per[r[1]].append(float(r[8]))
        board = sorted(((sum(v) / len(v)) for v in per.values() if len(v) >= 10), reverse=True)
        rank = sum(1 for x in board if x > ms) + 1
        print('   평균 점수: %.1f (클랜 평균 %.1f) — 10판 이상 %d명 중 %d위'
              % (ms, mall, len(board), rank))

    k = [_kda_of(r[7]) for r in sub]
    k = [x for x in k if x]
    if k:
        ka, kd, kas = (sum(x[i] for x in k) / len(k) for i in range(3))
        ratio = (ka + kas) / kd if kd else (ka + kas)
        print('   평균 KDA: %.1f / %.1f / %.1f (%.2f)' % (ka, kd, kas, ratio))
    kp = [_metric(r[10], 'kp') for r in sub]
    kp = [x for x in kp if x is not None]
    kpa = [x for x in (_metric(r[10], 'kp') for r in E) if x is not None]
    if kp:
        print('   킬관여: %.0f%% (클랜 평균 %.0f%%)'
              % (sum(kp) / len(kp), (sum(kpa) / len(kpa)) if kpa else 0))
    dm, dma = avg(sub, 9), avg(E, 9)
    if dm and dma:
        print('   평균 딜량: %s (클랜 평균 %s)' % (format(int(dm), ','), format(int(dma), ',')))

    peak = next((v for v in tabs['PEAK_SEASONS']
                 if len(v) >= 5 and (norm(v[0]) == key or norm(str(v[1] or '')) == key)), None)
    if peak:
        print('   솔랭 최고티어: %s (%s, %s점)' % (peak[2], peak[3], peak[4]))
        if len(peak) >= 6 and peak[5]:
            print('     시즌별: %s' % peak[5])
    else:
        print('   솔랭 최고티어: 측정 기록 없음')

    bp = _pressure(E)
    mine = bp.get(nm)
    if mine:
        board = sorted(((n, v[0]['targeted']) for n, v in bp.items()), key=lambda t: -t[1])
        rank = next((i + 1 for i, (n, _) in enumerate(board) if n == nm), None)
        t = mine[0]
        print('   견제 압력: %s +%.0f%%p (낀 판 %.0f%% vs 없는 판 %.0f%% 밴) — 클랜 %d위 / %d명'
              % (t['champ'], t['targeted'], t['present'], t['absent'], rank, len(board)))
        for x in mine[1:3]:
            print('     그 외: %s +%.0f%%p' % (x['champ'], x['targeted']))
    else:
        print('   견제 압력: 뚜렷하게 견제받는 챔프 없음 (상대가 특별히 의식하지 않는 상태)')

    print('   ※ 매치평가(MVP/ACE/역적)·점수·지표는 분석기가 붙인 판만 집계돼요.')


def main():
    if len(sys.argv) < 3:
        print(__doc__); return
    mode, arg = sys.argv[1], sys.argv[2]
    try:
        R = load()
        dd = ddragon()
    except Exception as e:
        print('데이터를 불러오지 못했어요: %s' % e); return
    if mode == 'item':
        m_item(R, dd, arg)
    elif mode == 'rune':
        m_rune(R, dd, arg)
    elif mode == 'spell':
        m_spell(R, dd, arg)
    elif mode == 'champ':
        m_champ(R, dd, arg)
    elif mode == 'player':
        m_player(R, dd, arg)
    elif mode == 'tier':
        try:
            E = load_eval()
        except Exception as e:
            print('평가 데이터를 불러오지 못했어요: %s' % e); return
        m_tier(R, E, arg)
    elif mode == 'h2h':
        if len(sys.argv) < 4:
            print('h2h 는 두 명이 필요해요: py qna_query.py h2h A B'); return
        m_h2h(R, dd, arg, sys.argv[3])
    else:
        print('알 수 없는 조회 종류: %s' % mode); print(__doc__)


if __name__ == '__main__':
    main()
