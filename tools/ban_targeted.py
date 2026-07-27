# -*- coding: utf-8 -*-
"""견제율의 교란 제거 — '내가 있어서 밴한 것'과 '원래 자주 밴되는 챔프'를 분리.

대조: 내 주력 챔프가
   (a) 내가 그 게임에 있을 때 밴되는 비율
   (b) 내가 없는 게임에서 밴되는 비율
차이(a-b)가 '나 때문에 밴한' 순수 견제 압력이다.
"""
import urllib.request, urllib.parse, json, re, sys, collections, math
sys.stdout.reconfigure(encoding='utf-8')

SID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU'
UA = {'User-Agent': 'Mozilla/5.0'}


def gviz(tq):
    url = ('https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:json&sheet=CLASSIC_NORMAL&headers=1&tq=%s'
           % (SID, urllib.parse.quote(tq)))
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read().decode('utf-8')
    return json.loads(re.search(r'setResponse\((.*)\)', raw, re.S).group(1))


rows = [[(x or {}).get('v') if x else None for x in r['c']]
        for r in gviz('select A,B,C,E,G,H limit 30000')['table']['rows']]
seen, R = set(), []
for r in rows:
    k = (r[0], r[2])
    if k in seen:
        continue
    seen.add(k); R.append(r)

bygame = collections.defaultdict(list)
for r in R:
    bygame[r[0]].append(r)
bygame = {g: v for g, v in bygame.items() if len(v) >= 8}

champs = collections.defaultdict(collections.Counter)
for r in R:
    champs[r[2]][r[4]] += 1
main = {n: set(c for c, k in cc.most_common(4) if k >= 3) for n, cc in champs.items()}

# 게임별: 밴 집합(양팀), 참가자
ginfo = {}
for gid, g in bygame.items():
    bans = set(x[5] for x in g if x[5] and x[5] != '밴 없음')
    if not bans:
        continue
    ginfo[gid] = (bans, set(x[2] for x in g))

print('밴 보유 게임:', len(ginfo))
out = []
for n, mc in main.items():
    if not mc:
        continue
    inn = ino = outn = outo = 0
    for gid, (bans, players) in ginfo.items():
        hit = 1 if (bans & mc) else 0
        if n in players:
            inn += 1; ino += hit
        else:
            outn += 1; outo += hit
    if inn < 15 or outn < 30:
        continue
    a, b = ino / inn, outo / outn
    # 이항 표준오차로 z
    se = math.sqrt(a * (1 - a) / inn + b * (1 - b) / outn) or 1e-9
    out.append((a - b, n, a, b, inn, (a - b) / se))

out.sort(reverse=True)
print('\n■ 순수 견제 압력 = (내가 있을 때 밴율) − (내가 없을 때 밴율)')
print('   %-22s %7s %7s %7s %5s %6s' % ('이름', '있을때', '없을때', '차이', '판수', 'z'))
for d, n, a, b, inn, z in out[:12]:
    print('   %-22s %6.0f%% %6.0f%% %+6.0f%%p %5d %+6.1f %s'
          % (n[:22], 100 * a, 100 * b, 100 * d, inn, z, '★' if z > 2 else ''))
print('   ...')
for d, n, a, b, inn, z in out[-5:]:
    print('   %-22s %6.0f%% %6.0f%% %+6.0f%%p %5d %+6.1f' % (n[:22], 100 * a, 100 * b, 100 * d, inn, z))

sig = [x for x in out if x[5] > 2]
print('\n통계적으로 뚜렷한 견제 대상: %d명 / 검정 %d명' % (len(sig), len(out)))
me = [x for x in out if '맛동산' in x[1]]
if me:
    d, n, a, b, inn, z = me[0]
    print('맛동산장인 유미: 있을때 %.0f%% vs 없을때 %.0f%% → %+.0f%%p (z=%+.1f), 순위 %d/%d'
          % (100 * a, 100 * b, 100 * d, z, [x[1] for x in out].index(n) + 1, len(out)))
