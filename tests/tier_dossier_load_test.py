# -*- coding: utf-8 -*-
"""억울지수(tooling/tier_dossier.py) — sibguiwol.load() 의 반환 값 개수가 바뀌어도 Dossier 가 죽지 않는다 (루프 A-36: 2026-09-17 load() 가 5값이 됐는데
Dossier 가 4값만 받아 grudge.yml 이 5주 연속 ValueError 로 실패).
  A. 합성 시트로 Dossier(path) 가 만들어지고 grudge() 가 돈다  B. DEPARTED(현재닉·별칭·LINK 그룹)는 순위에서 빠진다  C. 재직자는 남는다"""
import os, sys, tempfile, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'tooling'))
import openpyxl
import tier_dossier as td
td.MIN_DUELS = 1; td.MIN_LANE_GAMES = 1   # 합성 표본이 작아서 문턱을 낮춘다(순위가 비면 제외 규칙을 못 본다)
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
H = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '점수']
names = ['탑가#K', '탑나#K', '탑다#K', '탑라#K', '탑마#K', '탑옛#K']   # 같은 라인 맞라인
tiers = {'탑가': '1中', '탑나': '2上', '탑다': '2中', '탑라': '3上', '탑마': '3中', '탑옛': '1下'}
wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'; ws.append(H)
d0 = datetime.date.today() - datetime.timedelta(days=5)
gid = 100
for g in range(60):
    gid += 1
    a, b = names[g % 6], names[(g + 1 + (g % 2)) % 6]
    if a == b: b = names[(g + 2) % 6]
    wa = g % 3 != 0
    for nm, side, win in ((a, '블루팀', wa), (b, '레드팀', not wa)):
        ws.append(['#%d' % gid, (d0 - datetime.timedelta(days=g % 20)).isoformat() + ' 20:00', nm, 'pu-' + nm.split('#')[0], side, '탑', '가렌', None, '승리' if win else '패배', None, float(20 + (g * 7 + len(nm) * 3) % 17 + (5 if win else 0))])
for nm, rows in (('CLAN_TIERS', [['닉네임', '티어']] + [[k, v] for k, v in tiers.items()]),
                 ('DEPARTED', [['닉네임', '갱신시각'], ['탑옛', 'x']]),
                 ('LINK_ACCOUNT', [['본계정', '부계정 롤닉', '메모'], ['탑가#K', '탑가부#K', '']]),
                 ('SOLO_RANK', [['닉네임', '티어', 'LP', '솔랭승', '솔랭패', '점수', '갱신'], ['탑가#K', 'GOLD I', 1, 10, 10, 2000, 'x']]),
                 ('PEAK_SEASONS', [['닉네임', '차트닉', '최고티어', '최고시즌', '점수', '상세', '측정일'], ['탑가#K', '탑가', 'gold 1', 'S15', 2100, '', 'x']])):
    w2 = wb.create_sheet(nm)
    for r in rows: w2.append(r)
path = os.path.join(tempfile.mkdtemp(prefix='dos_'), 'sheet.xlsx'); wb.save(path)
try:
    D = td.Dossier(path); built = True
except Exception as e:
    built = False; print('   ', type(e).__name__, e)
ok(built, 'A Dossier(path) 가 만들어진다(load() 반환 값 개수가 맞다)')
if built:
    ok(isinstance(D.departed, set) and len(D.departed) == 1, 'A departed 집합을 들고 있다 %s' % sorted(D.departed))
    try: res = D.grudge(); ok(len(res) >= 3, 'A grudge() 가 돈다 (%d명)' % len(res))
    except Exception as e: res = []; ok(False, 'A grudge() 예외 %s' % e)
    old = next((k for k in D.rows_of if k.startswith('탑옛')), None)
    ok(old is not None and D.is_departed(old), 'B 탈퇴자(탑옛)는 탈퇴로 판정된다')
    ok(all(not D.is_departed(k) for k in D.rows_of if not k.startswith('탑옛')), 'C 재직자는 탈퇴로 안 찍힌다')
    ok(all(not x['name'].startswith('탑옛') for x in res), 'B 탈퇴자는 억울지수 순위에 없다')
print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
