# -*- coding: utf-8 -*-
"""⚔ 귀살대 개편 시험 — 탈퇴자·비활동자 제외 / 고인물 박제 방지 / 칩에 전적·최근 폼 표시 (2026-11-27)
합성 시트(가짜 닉네임·PUUID)만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다.

  A 후보 = 최근 90일 상현 상대 15판↑ 만 (탈퇴자·90일 무기록 고인물·10판짜리 제외) · 6명이 차면 fallback 없음
  B 순서 = 최근 90일 승률 내림차순 — 화면에 보이는 %와 순서가 어긋나지 않는다
  C 같은 승률이면 최근 30일 폼이 위, 최근 판이 없으면 아래 (🔥 = 최근 30일 폼)
  D 15판↑ 인원이 6명 미만이면 10판↑ fallback 으로 빈 칸을 채운다
  E 칩 = 승률 + 전적(`78% · 14승4패`) + 🔥폼 · KISATSU 원소에 w·g·wr · 부제에 기준 문구
  F 홈 화면에 그대로 그려진다 · 페이지 오류 0

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
DEPARTED = ['탈퇴자#T']
# (닉, 판수, 승수, 마지막 판이 며칠 전인지, 판 간격(일))
CAST_A = [                            # 15판↑ 6명 — great시 이 6명이 칸을 채운다
    ('최근강자#T', 18, 14, 0, 1.4),   # 77.8%
    ('중간#T', 16, 11, 2, 2.0),       # 68.8%
    ('동률A#T', 16, 10, 1, 1.2),      # 62.5% · 최근 30일 8판 7승(폼 있음)
    ('동률B#T', 16, 10, 70, 1.0),     # 62.5% · 최근 30일 0판(폼 없음)
    ('별로#T', 19, 8, 6, 1.6),        # 42.1%
    ('폼핫#T', 16, 6, 3, 4.0),        # 37.5% · 최근 30일 8판 6승(폼은 뜨겁다)
]
HOT, COLD = '동률A#T', '동률B#T'
GHOST = ('고인물#T', 20, 18, 120, 3.0)   # 마지막 판 120일 전 — 비활동
SHORT = ('표본10#T', 10, 9, 35, 1.0)     # 15판 미만 — A 에선 제외, D(fallback) 에선 들어온다
FILLERS = ['배경%03d#T' % i for i in range(1, 121)]   # 상현 반대편 채우기 — 한 명이 10판을 못 넘게 돌려 쓴다


def build_xlsx(path, cast):
    from openpyxl import Workbook
    rnd = random.Random(11)
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'; ws.append(COLS)
    people = SANGHYUN + DEPARTED + [c[0] for c in cast] + [GHOST[0], SHORT[0]] + FILLERS
    pu = {n: 'pu-%04d' % i for i, n in enumerate(people)}
    pos = {n: POS[i % 5] for i, n in enumerate(people)}
    gid = [7000]
    fill_i = [0]

    def game(days_ago, cand, cand_wins):
        """상현 5명 vs (후보 + 배경 4명) 한 판 — 상현 쪽에만 상현이 있어 배경은 후보로 세지지 않는다."""
        gid[0] += 1
        day = (LAST - dt.timedelta(days=days_ago)).isoformat() + ' 21:00'
        pick = [SANGHYUN[(days_ago + k) % 6] for k in range(5)]
        side_a = list(dict.fromkeys(pick))
        while len(side_a) < 5:
            side_a.append(FILLERS[(fill_i[0] + len(side_a)) % len(FILLERS)])
        for _ in range(4):
            fill_i[0] += 1
        side_b = [cand] + [FILLERS[(fill_i[0] + k) % len(FILLERS)] for k in range(4)]
        for n in side_a:
            ws.append(['#%d' % gid[0], day, n, pu[n], '레드팀', pos[n], rnd.choice(CHAMPS), None,
                       '패배' if cand_wins else '승리', None, 'v16.20', '2/3/7', 20.0, 20000.0, None, None, None, None, None])
        for n in side_b:
            ws.append(['#%d' % gid[0], day, n, pu[n], '블루팀', pos[n], rnd.choice(CHAMPS), None,
                       '승리' if cand_wins else '패배', None, 'v16.20', '2/3/7', 20.0, 20000.0, None, None, None, None, None])

    def series(nick, n, w, last_day, step):
        for i in range(n):
            game(last_day + round(i * step), nick, i < w)      # i=0 이 가장 최근

    for c in cast:
        series(c[0], c[1], c[2], c[3], c[4])
    series(GHOST[0], GHOST[1], GHOST[2], GHOST[3], GHOST[4])
    series(SHORT[0], SHORT[1], SHORT[2], SHORT[3], SHORT[4])
    series(DEPARTED[0], 20, 18, 4, 1.2)
    tiers = [[n.split('#')[0], '0' if n in SANGHYUN else '2中'] for n in SANGHYUN + DEPARTED + [c[0] for c in cast] + [GHOST[0], SHORT[0]]]
    tiers += [[n.split('#')[0], '3下'] for n in FILLERS]
    solo = [['상현%02d#T' % i, 'MASTER I', 400 - i * 20, 40, 30, 2800 + (6 - i) * 10, '2026-11-26 13:00', 1000 + i, 100 + i] for i in range(1, 7)]
    solo += [[c[0], 'DIAMOND II', 30, 30, 30, 2200, '2026-11-26 13:00', 2000 + i, 200 + i] for i, c in enumerate(cast)]
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
  const chips=[...document.querySelectorAll('.kz-corps-chip')].map(e=>e.textContent.replace(/\\s+/g,' ').trim());
  const hotMark=document.querySelectorAll('.kz-corps-hot').length;
  const sub=(document.querySelector('.kz-corps-sub')||{}).textContent||'';
  const names=k.map(x=>x.name);
  const idxOf=n=>names.findIndex(v=>String(v).indexOf(n)===0);
  return {n:k.length, k, chips, sub, hotMark,
    hasHot:idxOf('동률A'), hasCold:idxOf('동률B'), hasGhost:idxOf('고인물'), hasShort:idxOf('표본10'), hasGone:idxOf('탈퇴자'),
    wrs:k.map(x=>x.wr), desc:k.every((x,i)=>i===0||k[i-1].wr>=x.wr),
    dup:(()=>{const c={};names.forEach(n=>{const p=personKeyOf(n);c[p]=(c[p]||0)+1});return Object.values(c).filter(v=>v>1).length})(),
    overlap:(()=>{const t=new Set([...ASSESSMENTS.entries()].filter(([,a])=>a&&/^상현/.test(a.title||'')).map(([n])=>personKeyOf(n)));
      return names.filter(n=>t.has(personKeyOf(n))).length})(),
    lastDay:dataLastDay(), cd90:_cutBehind(90), cd30:_cutBehind(30)};
})()"""

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def run(cast, label):
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, cast)
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, evals=(KS_JS,), timeout_s=300)
    o = res['evals'][0]; log = res['meta']['log']
    ok(not log['pageerror'], label + ' · 페이지 오류 0 ' + str(log['pageerror'][:1]))
    return o


async def main():
    A = await run(CAST_A, 'A(15판↑ 6명)')
    print('  귀살대:', ', '.join('%s %d판 %d승 %d%%(30일 %d판 %d승)' % (x['name'], x['g'], x['w'], round(x['wr']), x['f30g'], x['f30w']) for x in A['k']))
    ok(A['n'] == 6, 'A 귀살대 6칸 (실제 %d)' % A['n'])
    ok(A['hasGone'] < 0, 'A 탈퇴자(DEPARTED)는 후보에서 빠진다')
    ok(A['hasGhost'] < 0, 'A 마지막 판이 120일 전인 고인물은 빠진다(최근 90일 활동)')
    ok(A['hasShort'] < 0, 'A 15판 미만(10판)은 15판↑가 6명이라 fallback 없이 빠진다')
    ok(all(x['g'] >= 15 for x in A['k']), 'A 남은 후보는 모두 최근 90일 상현 상대 15판↑ %s' % [x['g'] for x in A['k']])
    ok(A['desc'], 'B 순서가 최근 90일 승률 내림차순이다 %s' % A['wrs'])
    ok(A['hasHot'] >= 0 and A['hasCold'] >= 0 and A['hasHot'] < A['hasCold'],
       'C 같은 승률(62.5%%)이면 최근 30일 폼이 있는 쪽이 위 (%d < %d)' % (A['hasHot'], A['hasCold']))
    ok(all(x['f30g'] == 0 for x in A['k'] if x['name'].startswith('동률B')), 'C 동률B 는 최근 30일 판이 0판으로 집계된다')
    ok(A['dup'] == 0 and A['overlap'] == 0, 'A 같은 사람이 두 번 없고 상현(사람)과 겹치지 않는다')
    ok(all(x['ok'] for x in A['k']), 'E KISATSU 원소에 w·g·wr 이 서로 맞게 들어 있다')
    ok(len(A['chips']) == 6 and all(re.search(r'\d+%', c) and re.search(r'·\s*\d+승\d+패', c) for c in A['chips']),
       'E 칩에 승률과 전적이 같이 나온다 %s' % A['chips'][:2])
    ok(A['hotMark'] >= 1 and '🔥' in A['chips'][0], 'E 최근 폼이 있는 칩에는 🔥 최근 30일 승률이 붙는다 %s' % A['chips'][0])
    # 🧹 [2026-11-27 사장님 「최근90일에 관한 내용부터 그 뒷내용 디테일까지는 안보여도될거같으니 내용지워주고 간결화」]
    ok(A['sub'].strip() == '상현이 낀 상대를 만나면 가장 잘 이기는 사냥꾼들',
       'E 부제는 한 문장만 남는다(판수·폼·탈퇴 설명은 칩 툴팁으로) %r' % A['sub'].strip())
    ok(A['lastDay'] == '2026-11-26' and A['cd90'] == '2026-08-28' and A['cd30'] == '2026-10-27',
       '기준일 = 데이터 마지막 기록일(11/26) · 90일 08/28 · 30일 10/27')

    B = await run(CAST_A[:5], 'D(15판↑ 5명)')
    print('  귀살대:', ', '.join('%s %d판' % (x['name'], x['g']) for x in B['k']))
    ok(B['n'] == 6, 'D 15판↑가 5명이면 10판↑ fallback 으로 6칸을 채운다 (실제 %d)' % B['n'])
    ok(B['hasShort'] >= 0, 'D 10판짜리(표본10)가 fallback 으로 들어온다')
    ok(B['hasGhost'] < 0 and B['hasGone'] < 0, 'D fallback 에서도 고인물·탈퇴자는 빠진다')

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':   # 헤더 시험(web_kisatsu_header_test)이 build_xlsx·CAST_A 를 가져다 쓴다
    asyncio.run(main())
