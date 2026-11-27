# -*- coding: utf-8 -*-
"""⚔ 귀살대 맞라이너 개편 시험 — 상현(6인)을 '같은 포지션(맞라이너)'으로 만난 판만 · 5판↑ / 3판 fallback (2026-11-27 「2로가자」)
합성 시트(가짜 닉네임·PUUID)만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다.

  A 후보 = 최근 90일 상현 맞라이너 5판↑ 만 (탈퇴자·90일 무기록 고인물·3판짜리 제외) · 6명이 차면 fallback 없음
  B 순서 = 최근 90일 맞라이너 승률 내림차순 — 화면에 보이는 %와 순서가 어긋나지 않는다
  C 같은 승률이면 최근 30일 폼이 위, 최근 판이 없으면 아래 (🔥 = 최근 30일 폼)
  D 5판↑ 인원이 6명 미만이면 3판↑ fallback 으로 빈 칸을 채운다
  E 반쪽 카드 = 승률 + 전적(`78%` `14승4패`) + 🔥폼 · KISATSU 원소에 w·g·wr · 부제에 기준 문구
  F 맞라이너만 — 상현이 다른 라인에 있던 판(또는 포지션 기록 없는 판)은 한 판도 세지 않는다
  G 홈 화면에 그대로 그려진다 · 페이지 오류 0

  python3 tests/web_kisatsu_recent_test.py
"""
import asyncio, datetime as dt, os, random, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

COLS = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
CHAMPS = ['가렌', '아리', '이즈리얼', '쓰레쉬', '리신', '제드']
POS = ['탑', '정글', '미드', '원딜', '서폿']
LAST = dt.date(2026, 11, 26)          # 데이터의 마지막 기록일 — 웹의 90일·30일 기준일
SANGHYUN = ['상현%02d#T' % i for i in range(1, 7)]
SH_LANE = {SANGHYUN[i]: POS[i % 5] for i in range(6)}          # 상현01~05 가 5개 라인 전부, 상현06 = 탑
SH_ON = {l: next(n for n in SANGHYUN if SH_LANE[n] == l) for l in POS}
DEPARTED = ['탈퇴자#T']
SUB_WANT = '상현을 맞라이너로 만났을 때 가장 잘 이기는 사냥꾼들'
# (닉, 판수, 승수, 마지막 판이 며칠 전인지, 판 간격(일), 라인)
CAST_A = [                            # 5판↑ 6명 — 이 6명이 칸을 채운다(모든 판이 맞라이너)
    {'n': '최근강자#T', 'g': 8, 'w': 7, 'last': 0, 'step': 1.5, 'lane': '탑'},     # 87.5%
    {'n': '중간#T', 'g': 7, 'w': 5, 'last': 2, 'step': 2.0, 'lane': '정글'},       # 71.4%
    {'n': '동률A#T', 'g': 6, 'w': 4, 'last': 1, 'step': 1.0, 'lane': '미드'},      # 66.7% · 최근 30일 6판 4승(폼 있음)
    {'n': '동률B#T', 'g': 6, 'w': 4, 'last': 40, 'step': 1.0, 'lane': '원딜'},     # 66.7% · 최근 30일 0판(폼 없음)
    {'n': '별로#T', 'g': 9, 'w': 4, 'last': 6, 'step': 1.6, 'lane': '서폿'},       # 44.4%
    {'n': '폼핫#T', 'g': 6, 'w': 2, 'last': 3, 'step': 4.0, 'lane': '탑'},         # 33.3% · 최근 30일 6판 2승
]
HOT, COLD = '동률A#T', '동률B#T'
GHOST = ('고인물#T', 20, 18, 120, 3.0)     # 마지막 판 120일 전 — 비활동(맞라이너지만 90일 밖)
SHORT3 = ('표본3#T', 3, 3, 5, 1.0)         # 3판 — A 에선 제외, D(fallback) 에선 들어온다
CROSS = ('다른라인#T', 12, 12, 1, 1.0)     # 12판 전부 상현이 '다른 라인' → 맞라이너 0판(개편 전이면 12판 100%로 1위)
MIXED = ('혼합#T', 4, 4)                   # 맞라이너 4판 + 다른 라인 8판 → 맞라이너 집계는 4판
FILLERS = ['배경%03d#T' % i for i in range(1, 801)]   # 상현·후보 반대편 채우기 — 한 명이 3판을 못 넘게 돌려 쓴다


def build_xlsx(path, cast, extras=()):
    from openpyxl import Workbook
    rnd = random.Random(11)
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'; ws.append(COLS)
    people = SANGHYUN + DEPARTED + [c['n'] for c in cast] + [GHOST[0], SHORT3[0], CROSS[0], MIXED[0]] + FILLERS
    pu = {n: 'pu-%04d' % i for i, n in enumerate(people)}
    gid = [7000]
    fi = [0]

    def filler():
        n = FILLERS[fi[0] % len(FILLERS)]; fi[0] += 1; return n

    def put(g, day, name, side, posv, res):
        ws.append(['#%d' % g, day, name, pu.get(name, 'pu-x'), side, posv, rnd.choice(CHAMPS), None, res, None,
                   'v16.20', '2/3/7', 20.0, 20000.0, None, None, None, None, None])

    def game(days_ago, cand, lane, cand_wins, mode='match', cand_pos=None):
        """상현 5명 vs (후보 + 배경 4명) 한 판.
        mode='match'  상대 팀에 후보와 같은 라인 상현이 있다 = 맞라이너
        mode='other'  상현은 상대 팀에 있지만 후보 라인은 비어 있다 = 맞라이너 아님
        mode='nopos'  상대 상현의 포지션 기록이 '선택안함' = 라인을 알 수 없다 (후보 쪽도 cand_pos 로 바꿀 수 있다)
        """
        gid[0] += 1
        day = (LAST - dt.timedelta(days=days_ago)).isoformat() + ' 21:00'
        others = [l for l in POS if l != lane]
        if mode == 'match':
            enemy = [(SH_ON[lane], lane), (SH_ON[others[0]], others[0]), (SH_ON[others[1]], others[1]), (SH_ON[others[2]], others[2])]
            free = others[3]
        elif mode == 'other':
            enemy = [(SH_ON[others[0]], others[0]), (SH_ON[others[1]], others[1]), (SH_ON[others[2]], others[2]), (SH_ON[others[3]], others[3])]
            free = lane
        elif mode == 'nopos':
            enemy = [(SH_ON[lane], '선택안함'), (SH_ON[others[0]], '선택안함'), (SH_ON[others[1]], '선택안함'), (SH_ON[others[2]], '선택안함')]
            free = others[3]
        else:
            raise ValueError(mode)
        enemy.append((filler(), free))
        mine = [(cand, cand_pos or lane)] + [(filler(), l) for l in others]
        for n, p in enemy:
            put(gid[0], day, n, '레드팀', p, '패배' if cand_wins else '승리')
        for n, p in mine:
            put(gid[0], day, n, '블루팀', p, '승리' if cand_wins else '패배')

    def series(c):
        for i in range(c['g']):
            game(c['last'] + round(i * c['step']), c['n'], c['lane'], i < c['w'])

    for c in cast:
        series(c)
    series({'n': GHOST[0], 'g': GHOST[1], 'w': GHOST[2], 'last': GHOST[3], 'step': GHOST[4], 'lane': '미드'})
    series({'n': SHORT3[0], 'g': SHORT3[1], 'w': SHORT3[2], 'last': SHORT3[3], 'step': SHORT3[4], 'lane': '서폿'})
    for i in range(12):                              # 탈퇴자 — 맞라이너 12판 11승
        game(4 + i, DEPARTED[0], '정글', i < 11)
    for i in range(CROSS[1]):                        # 상현이 다른 라인에만 있던 판
        game(1 + i, CROSS[0], '정글', True, mode='other')
    if 'mixed' in extras:                            # 맞라이너 4판 + 다른 라인 8판
        for i in range(MIXED[1]):
            game(1 + i * 2, MIXED[0], '미드', True)
        for i in range(8):
            game(2 + i * 2, MIXED[0], '미드', True, mode='other')

    tiers = [[n.split('#')[0], '0' if n in SANGHYUN else '3下' if n in FILLERS else '2中']
             for n in SANGHYUN + DEPARTED + [c['n'] for c in cast] + [GHOST[0], SHORT3[0], CROSS[0], MIXED[0]]]
    tiers += [[n.split('#')[0], '3下'] for n in FILLERS]
    solo = [['상현%02d#T' % i, 'MASTER I', 400 - i * 20, 40, 30, 2800 + (6 - i) * 10, '2026-11-26 13:00', 1000 + i, 100 + i] for i in range(1, 7)]
    solo += [[c['n'], 'DIAMOND II', 30, 30, 30, 2200, '2026-11-26 13:00', 2000 + i, 200 + i] for i, c in enumerate(cast)]
    for name, rows in (('CLAN_TIERS', [['닉네임', '티어']] + tiers),
                       ('SOLO_RANK', [['닉네임', '티어', 'LP', '솔랭승', '솔랭패', '점수', '갱신', '아이콘', '레벨']] + solo),
                       ('LINK_ACCOUNT', [['본계정', '부계정 롤닉 (#태그 있어도 됨)', '메모 (선택)']]),
                       ('DEPARTED', [['닉네임', '갱신시각'], ['탈퇴자', '2026-11-26 09:00']])):
        w = wb.create_sheet(name)
        for r in rows: w.append(r)
    wb.save(path)


KS_JS = """(()=>{
  const k=KISATSU.map(x=>({name:x.name,g:x.g,w:x.w,wr:+x.wr.toFixed(1),f30g:x.f30g,f30w:x.f30w,
    ok:typeof x.w==='number'&&typeof x.g==='number'&&typeof x.wr==='number'&&Math.abs(x.w/x.g*100-x.wr)<1e-9}));
  const halves=[...document.querySelectorAll('.ksd-half:not(.empty)')].map(e=>e.textContent.replace(/\\\\s+/g,' ').trim());
  const hotMark=document.querySelectorAll('.ksd-hot').length;
  const sub=(document.querySelector('.kz-corps-sub')||{}).textContent||'';
  const names=k.map(x=>x.name);
  const idxOf=n=>names.findIndex(v=>String(v).indexOf(n)===0);
  return {n:k.length, k, halves, sub, hotMark,
    hasHot:idxOf('동률A'), hasCold:idxOf('동률B'), hasGhost:idxOf('고인물'), hasShort:idxOf('표본3'), hasGone:idxOf('탈퇴자'),
    hasCross:idxOf('다른라인'), hasMixed:idxOf('혼합'),
    wrs:k.map(x=>x.wr), desc:k.every((x,i)=>i===0||k[i-1].wr>=x.wr),
    dup:(()=>{const c={};names.forEach(n=>{const p=personKeyOf(n);c[p]=(c[p]||0)+1});return Object.values(c).filter(v=>v>1).length})(),
    overlap:(()=>{const t=new Set([...ASSESSMENTS.entries()].filter(([,a])=>a&&/^상현/.test(a.title||'')).map(([n])=>personKeyOf(n)));
      return names.filter(n=>t.has(personKeyOf(n))).length})(),
    kisatsu:KISATSU.map(x=>x.name), pref:typeof KISATSU_PREF_GAMES!=='undefined'?KISATSU_PREF_GAMES:null,
    min:typeof KISATSU_MIN_GAMES!=='undefined'?KISATSU_MIN_GAMES:null,
    lastDay:dataLastDay(), cd90:_cutBehind(90), cd30:_cutBehind(30)};
})()"""

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def run(cast, label, extras=()):
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, cast, extras)
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, evals=(KS_JS,), timeout_s=300)
    o = res['evals'][0]; log = res['meta']['log']
    ok(not log['pageerror'], label + ' · 페이지 오류 0 ' + str(log['pageerror'][:1]))
    return o


async def main():
    A = await run(CAST_A, 'A(5판↑ 6명)')
    print('  귀살대:', ', '.join('%s %d판 %d승 %d%%(30일 %d판 %d승)' % (x['name'], x['g'], x['w'], round(x['wr']), x['f30g'], x['f30w']) for x in A['k']))
    ok(A['pref'] == 5 and A['min'] == 3, 'A 기준값 = 5판↑ / fallback 3판↑ (%s / %s)' % (A['pref'], A['min']))
    ok(A['n'] == 6, 'A 귀살대 6칸 (실제 %d)' % A['n'])
    ok(A['hasGone'] < 0, 'A 탈퇴자(DEPARTED)는 후보에서 빠진다')
    ok(A['hasGhost'] < 0, 'A 마지막 판이 120일 전인 고인물은 빠진다(최근 90일 활동)')
    ok(A['hasShort'] < 0, 'A 5판 미만(3판)은 5판↑가 6명이라 fallback 없이 빠진다')
    ok(all(x['g'] >= 5 for x in A['k']), 'A 남은 후보는 모두 최근 90일 상현 맞라이너 5판↑ %s' % [x['g'] for x in A['k']])
    ok(A['desc'], 'B 순서가 최근 90일 맞라이너 승률 내림차순이다 %s' % A['wrs'])
    ok(A['hasHot'] >= 0 and A['hasCold'] >= 0 and A['hasHot'] < A['hasCold'],
       'C 같은 승률(66.7%%)이면 최근 30일 폼이 있는 쪽이 위 (%d < %d)' % (A['hasHot'], A['hasCold']))
    ok(A['hasCross'] < 0, 'F 상현을 다른 라인에서만 만난 사람(12판 100%)은 한 판도 세지 않는다')
    ok(A['dup'] == 0 and A['overlap'] == 0, 'A 같은 사람이 두 번 없고 상현(사람)과 겹치지 않는다')
    ok(all(x['ok'] for x in A['k']), 'E KISATSU 원소에 w·g·wr 이 서로 맞게 들어 있다')
    ok(len(A['halves']) == 6 and all(re.search(r'\d+%', c) and re.search(r'\d+승\d+패', c) for c in A['halves']),
       'E 반쪽마다 승률과 전적이 같이 나온다 %s' % A['halves'][:2])
    ok(A['hotMark'] >= 1 and '🔥' in A['halves'][0], 'E 최근 폼이 있는 반쪽에는 🔥 최근 30일 승률이 붙는다 %s' % A['halves'][0])
    ok(A['sub'].strip() == SUB_WANT, 'E 부제는 맞라이너 기준 한 문장 %r' % A['sub'].strip())
    ok(A['lastDay'] == '2026-11-26' and A['cd90'] == '2026-08-28' and A['cd30'] == '2026-10-27',
       '기준일 = 데이터 마지막 기록일(11/26) · 90일 08/28 · 30일 10/27')

    B = await run(CAST_A[:5], 'D(5판↑ 5명)', extras=('mixed',))
    print('  귀살대:', ', '.join('%s %d판 %d승' % (x['name'], x['g'], x['w']) for x in B['k']))
    ok(B['n'] == 6, 'D 5판↑가 5명이면 3판↑ fallback 으로 6칸을 채운다 (실제 %d)' % B['n'])
    ok(B['hasGhost'] < 0 and B['hasGone'] < 0, 'D fallback 에서도 고인물·탈퇴자는 빠진다')
    mix = [x for x in B['k'] if x['name'].startswith('혼합')]
    ok(bool(mix) and mix[0]['g'] == 4 and mix[0]['w'] == 4,
       'F 맞라이너 4판 + 다른 라인 8판인 사람은 4판 4승으로만 집계된다 %s' % mix)

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':   # 다른 귀살대 시험(header·dual·effect)이 build_xlsx·CAST_A 를 가져다 쓴다
    asyncio.run(main())
