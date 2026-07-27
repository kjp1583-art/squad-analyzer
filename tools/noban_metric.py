# -*- coding: utf-8 -*-
"""노밴 추천 지표 — 주간평 파이프라인용. 추가 입력 없이 기존 밴 데이터만 사용.

로컬룰: 팀당 노밴 1개. 선언하면 상대가 그 챔프를 1페이즈에 밴 못 한다.
        2페이즈엔 밴 가능하고, 상대가 그 챔프를 '픽'하는 건 못 막는다.

출력: noban.json = { 닉네임: {best: {...}, champs: [...]} }
사용: py noban_metric.py noban.json
"""
import urllib.request, urllib.parse, json, re, sys, collections, math
sys.stdout.reconfigure(encoding='utf-8')

SID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU'
UA = {'User-Agent': 'Mozilla/5.0'}
MIN_CHAMP_GAMES = 4
MIN_PRESENT = 8
MIN_ABSENT = 20


def gviz(tq):
    url = ('https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:json&sheet=CLASSIC_NORMAL&headers=1&tq=%s'
           % (SID, urllib.parse.quote(tq)))
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read().decode('utf-8')
    return json.loads(re.search(r'setResponse\((.*)\)', raw, re.S).group(1))


rows = [[(x or {}).get('v') if x else None for x in r['c']]
        for r in gviz('select A,C,E,G,H,I limit 30000')['table']['rows']]
# 0게임ID 1이름 2진영 3챔피언 4밴 5결과
seen, R = set(), []
for r in rows:
    k = (r[0], r[1])
    if k in seen:
        continue
    seen.add(k); R.append(r)

bygame = collections.defaultdict(list)
for r in R:
    bygame[r[0]].append(r)
bygame = {g: v for g, v in bygame.items() if len(v) >= 8}

ginfo = {}
for gid, g in bygame.items():
    bans = collections.defaultdict(set)
    ok = False
    for x in g:
        if x[4] and x[4] != '밴 없음':
            bans[x[2]].add(x[4])
            ok = True
    if ok:
        ginfo[gid] = {'bans': bans, 'side': {x[1]: x[2] for x in g}}

pickcnt = collections.Counter()
for g in bygame.values():
    for c in set(x[3] for x in g):
        pickcnt[c] += 1
TOTG = len(bygame)

pc = collections.defaultdict(lambda: [0, 0])
for r in R:
    pc[(r[1], r[3])][0] += 1
    pc[(r[1], r[3])][1] += 1 if r[5] == '승리' else 0

players = set(r[1] for r in R)
out = {}
for me in players:
    mains = [(c, n, w) for (p, c), (n, w) in pc.items() if p == me and n >= MIN_CHAMP_GAMES]
    if not mains:
        continue
    mains.sort(key=lambda x: -x[1])
    res = []
    for champ, n, w in mains[:6]:
        inn = ino = outn = 0
        outo = 0.0
        for gid, gi in ginfo.items():
            allb = set()
            for s in gi['bans'].values():
                allb |= s
            if me in gi['side']:
                opp = '레드팀' if gi['side'][me] == '블루팀' else '블루팀'
                inn += 1
                ino += 1 if champ in gi['bans'].get(opp, set()) else 0
            else:
                outn += 1
                outo += (1 if champ in allb else 0) * 0.5   # 한 팀 기준으로 환산
        if inn < MIN_PRESENT or outn < MIN_ABSENT:
            continue
        a, b = ino / inn, outo / outn
        se = math.sqrt(max(a * (1 - a), 1e-6) / inn + max(b * (1 - b), 1e-6) / outn)
        res.append({'champ': champ, 'games': n, 'wr': round(100 * w / n),
                    'ban_present': round(100 * a), 'ban_absent': round(100 * b),
                    'targeted': round(100 * (a - b)), 'z': round((a - b) / se, 1),
                    'steal_risk': round(100 * pickcnt[champ] / TOTG)})
    if not res:
        continue
    res.sort(key=lambda x: -x['targeted'])
    cand = [x for x in res if x['z'] > 1.5]
    best = None
    if cand:
        best = sorted(cand, key=lambda x: -(x['targeted'] * (x['wr'] / 50.0) - x['steal_risk'] * 0.5))[0]
    out[me] = {'best': best, 'champs': res,
               'note': None if best else '뚜렷하게 견제받는 챔프 없음 — 노밴은 팀원에게 양보하는 게 이득'}

path = sys.argv[1] if len(sys.argv) > 1 else 'noban.json'
json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
n_best = sum(1 for v in out.values() if v['best'])
print('선수 %d명 | 노밴 추천 가능 %d명 | 추천 대상 없음 %d명' % (len(out), n_best, len(out) - n_best))
print('저장:', path)
top = sorted([(v['best']['targeted'], k, v['best']) for k, v in out.items() if v['best']], reverse=True)[:8]
print('\n견제 압력 상위 — 노밴 1순위')
for t, k, b in top:
    print('  %-22s %-8s +%2d%%p  승률 %2d%%  탈취위험 %2d%%' % (k[:22], b['champ'], t, b['wr'], b['steal_risk']))
