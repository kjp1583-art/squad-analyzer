# -*- coding: utf-8 -*-
"""📜 귀살대 상현 이력 시험 — '그 판 날짜에 상현이던 6인'으로 맞라이너 판정 (2026-11-27 사장님 「2로가자」)
합성 시트(가짜 닉네임·PUUID)와 임시 폴더의 data/sanghyun_history.json 만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다.

  A 이력이 있으면: 그 날짜의 상현과 같은 라인에서 만난 판만 센다
      · 과거스냅샷(A) 시절에 A 와 만난 판 → 센다
      · 중간스냅샷(B) 이후에 A 와 만난 판 → 안 센다(그때 A 는 상현이 아니다)
      · 첫 스냅샷 이전 판 → 지금 상현(CUR)으로 폴백해서 센다
      · B 시절에 B 와 만난 판 → 센다
  B 파일이 없거나 깨져도 페이지가 죽지 않고, 전부 '지금 상현' 기준으로만 집계한다

  python3 tests/web_kisatsu_history_test.py
"""
import asyncio, datetime as dt, json, os, random, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

COLS = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
CHAMPS = ['가렌', '아리', '이즈리얼', '쓰레쉬', '리신', '제드']
POS = ['탑', '정글', '미드', '원딜', '서폿']
NOW = '2026-11-16T10:00:00'
CUR = ['현재0%d#T' % i for i in range(1, 7)]      # 지금 상현(내부티어 0 → 파워랭킹 상위 6)
OLD = ['과거0%d#T' % i for i in range(1, 7)]      # 2026-10-10 스냅샷의 상현
MID = ['중간0%d#T' % i for i in range(1, 7)]      # 2026-11-10 스냅샷의 상현
FILLERS = ['배경%03d#T' % i for i in range(1, 401)]
HIST = [{'date': '2026-10-10', 'members': OLD}, {'date': '2026-11-10', 'members': MID}]
# (닉, 상대 상현 명단, 첫 판 날짜, 판수, 라인)
X = ('과거에만#T', OLD, dt.date(2026, 10, 12), 4, '미드')   # A 스냅샷 시절 → 센다
Y = ('지난상현#T', OLD, dt.date(2026, 11, 12), 4, '미드')   # B 스냅샷 이후 → 안 센다
Z = ('이력이전#T', CUR, dt.date(2026, 9, 5), 4, '미드')     # 첫 스냅샷 이전 → 지금 상현 폴백 → 센다
W = ('중간상현#T', MID, dt.date(2026, 11, 11), 4, '미드')   # B 스냅샷 시절 → 센다


def lane_on(group, lane):
    return next(n for n in group if POS[group.index(n) % 5] == lane)


def build_xlsx(path):
    from openpyxl import Workbook
    rnd = random.Random(7)
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'; ws.append(COLS)
    people = CUR + OLD + MID + [c[0] for c in (X, Y, Z, W)] + FILLERS
    pu = {n: 'pu-%04d' % i for i, n in enumerate(people)}
    gid = [9000]
    fi = [0]

    def filler():
        n = FILLERS[fi[0] % len(FILLERS)]; fi[0] += 1; return n

    def put(g, day, name, side, posv, res):
        ws.append(['#%d' % g, day, name, pu[name], side, posv, rnd.choice(CHAMPS), None, res, None,
                   'v16.20', '2/3/7', 20.0, 20000.0, None, None, None, None, None])

    def game(day, cand, group, lane):
        """상현 명단(group)의 그 라인 멤버가 상대 팀에 선다 — 후보는 늘 이긴다."""
        gid[0] += 1
        d = day.isoformat() + ' 21:00'
        others = [l for l in POS if l != lane]
        enemy = [(lane_on(group, lane), lane)] + [(lane_on(group, l), l) for l in others[:3]]
        enemy.append((filler(), others[3]))
        mine = [(cand, lane)] + [(filler(), l) for l in others]
        for n, p in enemy: put(gid[0], d, n, '레드팀', p, '패배')
        for n, p in mine: put(gid[0], d, n, '블루팀', p, '승리')

    def spar(day, group):
        """상현 명단끼리 한 판 — 파워랭킹이 '최근 30일 5판' 조건을 채우게 하는 활동 기록(후보 집계와 무관)."""
        gid[0] += 1
        d = day.isoformat() + ' 21:00'
        for n in group[:5]:
            put(gid[0], d, n, '레드팀', POS[group.index(n) % 5], '승리')
        for l in POS:
            put(gid[0], d, filler(), '블루팀', l, '패배')

    for cand, group, first, n, lane in (X, Y, Z, W):
        for i in range(n):
            game(first + dt.timedelta(days=i), cand, group, lane)
    for i in range(12):                            # 지금 상현(CUR)은 최근 30일 5판·내전 10판↑ 조건을 채워야 상현으로 뽑힌다
        spar(dt.date(2026, 11, 2) + dt.timedelta(days=i), CUR)
    tiers = [[n.split('#')[0], '0' if n in CUR else '3下' if n in FILLERS else '2中'] for n in CUR + OLD + MID + [c[0] for c in (X, Y, Z, W)]]
    tiers += [[n.split('#')[0], '3下'] for n in FILLERS]
    solo = [[n, 'MASTER I', 300 - i * 10, 20, 20, 2600, '2026-11-15 13:00', 1000 + i, 100] for i, n in enumerate(CUR)]
    for name, rows in (('CLAN_TIERS', [['닉네임', '티어']] + tiers),
                       ('SOLO_RANK', [['닉네임', '티어', 'LP', '솔랭승', '솔랭패', '점수', '갱신', '아이콘', '레벨']] + solo),
                       ('LINK_ACCOUNT', [['본계정', '부계정 롤닉 (#태그 있어도 됨)', '메모 (선택)']]),
                       ('DEPARTED', [['닉네임', '갱신시각']])):
        s = wb.create_sheet(name)
        for r in rows: s.append(r)
    wb.save(path)


JS = """(()=>({hist:(typeof SANGHYUN_HISTORY!=='undefined')?SANGHYUN_HISTORY.map(e=>e.date):null,
  kids:KISATSU.map(x=>({n:x.name,g:x.g,w:x.w})), lastDay:dataLastDay()}))()"""

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def run(history):
    """history=None 이면 data/sanghyun_history.json 이 없는 사이트."""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(HERE, '..', 'index.html')
        shutil.copy2(src, os.path.join(td, 'index.html'))
        if history is not None:
            os.makedirs(os.path.join(td, 'data'), exist_ok=True)
            with open(os.path.join(td, 'data', 'sanghyun_history.json'), 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False)
        x = os.path.join(td, 's.xlsx'); build_xlsx(x)
        res = await R.replay(os.path.join(td, 'index.html'), xlsx=x, now=NOW, cats=('rift',), shots=False, quiet=True,
                             evals=(JS,), timeout_s=300)
    o = res['evals'][0]; log = res['meta']['log']
    ok(not log['pageerror'], '페이지 오류 0 ' + str(log['pageerror'][:1]))
    return o


async def main():
    A = await run(HIST)
    print('  이력:', A['hist'], '· 기준일', A['lastDay'])
    g = {x['n'].split('#')[0]: x['g'] for x in A['kids']}
    print('  집계:', g)
    ok(A['hist'] == ['2026-10-10', '2026-11-10'], 'A 스냅샷 두 개를 날짜순으로 읽는다 %s' % (A['hist'],))
    ok(g.get('과거에만') == 4, 'A 스냅샷 시절(A)에 만난 판은 센다 (과거에만 %s판)' % g.get('과거에만'))
    ok(g.get('중간상현') == 4, 'A B 스냅샷 시절(B)에 만난 판은 센다 (중간상현 %s판)' % g.get('중간상현'))
    ok(g.get('지난상현') is None, 'A B 이후에 옛 상현(A)과 만난 판은 세지 않는다 (지난상현 %s)' % g.get('지난상현'))
    ok(g.get('이력이전') == 4, 'A 첫 스냅샷 이전 판은 지금 상현으로 폴백해 센다 (이력이전 %s판)' % g.get('이력이전'))

    B = await run(None)
    g2 = {x['n'].split('#')[0]: x['g'] for x in B['kids']}
    print('  이력 없음 집계:', g2)
    ok(B['hist'] == [], 'B 파일이 없으면 이력은 빈 배열')
    ok(g2.get('이력이전') == 4, 'B 이력이 없어도 지금 상현과의 맞라이너는 센다 (이력이전 %s판)' % g2.get('이력이전'))
    ok(g2.get('과거에만') is None and g2.get('지난상현') is None,
       'B 이력이 없으면 옛 상현(A)은 상현으로 보지 않는다')

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)


asyncio.run(main())
