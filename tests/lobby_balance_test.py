#!/usr/bin/env python3
"""P-12 대기실 전력차·1:1 맞바꾸기 순수 함수 시험. 분석기는 윈도우 전용 모듈(winreg 등)을 불러와 리눅스에서 import 가
안 되므로, 소스에서 해당 블록만 잘라 실행한다. 사용: python3 tests/lobby_balance_test.py"""
import os, re, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = open(os.path.join(ROOT, 'desktop', 'squad_analyzer.py'), encoding='utf-8').read()
a = SRC.index("# ===== ⚖️ [2026-10-03 사장님 승인 P-12]")
b = SRC.index("\ndef _pos_recommend(A, B, idx):")
blk = SRC[a:b]
def grab(name):   # 최상위 def 하나를 통째로
    m = re.search(r"^def %s\(.*?(?=^\S)" % name, SRC, re.S | re.M)
    return m.group(0)
TIERS = {}
ns = {"TIERS": TIERS}
exec("import re\n" + grab("tnorm") + "\n" + grab("_unified_tier_score") + grab("_unified_power_one")
     + "\n_UT_RK = {'上': 3, '中': 2, '下': 1}\ndef tier_of(n): return TIERS.get(tnorm(n), '')\n"
     + "def _captain_power(p, s): return _unified_power_one((p or {}).get('name') or '', s or {})\n"
     + "def _captain_main_pos(p, c): return str((p or {}).get('pos') or '')\n" + blk, ns)
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)
def team(prefix, pws, poss=("탑", "정글", "미드", "원딜", "서폿")):
    return [{'nm': f"{prefix}{i}#KR1", 'pw': pw, 'pos': poss[i]} for i, pw in enumerate(pws)]
ev, lines, wr = ns['_lobby_balance_eval'], ns['_lobby_balance_lines'], ns['_lobby_wr_from_diff']

# 승률 식 = 게임 시작 화면(50+차×4, 15~85, 반올림)
check("wr 0", wr(0) == 50); check("wr +1.5", wr(1.5) == 56); check("wr -1.5", wr(-1.5) == 44)
check("wr 반올림 .125→", wr(0.125) == 51 and wr(0.12) == 50); check("wr 상한", wr(99) == 85 and wr(-99) == 15)
# 팽팽
e = ev(team("b", [5] * 5), team("r", [5] * 5)); check("동률 팽팽", lines(e) == ["⚖️ 팽팽해요 👍"] and e['swap'] is None)
e = ev(team("b", [5, 5, 5, 5, 6]), team("r", [5] * 5)); check("차 1.0 팽팽", lines(e) == ["⚖️ 팽팽해요 👍"])
# 1.0~1.5 사이: 한 줄만, 제안 없음
e = ev(team("b", [5, 5, 5, 5, 6.3]), team("r", [5] * 5))
check("차 1.3 한 줄·제안없음", e['swap'] is None and len(lines(e)) == 1 and "전력차 1.3" in lines(e)[0], lines(e))
# 기운 판: 블루가 강함 → 블루 높은 %
e = ev(team("b", [7, 6, 6, 6, 6]), team("r", [5.5, 5, 5, 5, 5]))   # 차 = 31-25.5 = 5.5
check("블루 강세 방향", e['bw'] > 50 and e['rw'] < 50 and e['bw'] + e['rw'] == 100, e)
check("문구 형식", lines(e)[0] == f"⚖️ 예상 승률 블루 {e['bw']}% : 레드 {e['rw']}% · 전력차 5.5", lines(e))
e2 = ev(team("b", [5.5, 5, 5, 5, 5]), team("r", [7, 6, 6, 6, 6]))
check("레드 강세 방향", e2['bw'] < 50 and e2['bw'] == 100 - e['bw'])
# 맞바꾸기: 차를 실제로 줄이고 같은 포지션 우선
B = team("b", [6, 6, 5, 5, 5]); R = team("r", [5, 5, 5, 5, 5])   # 차 2 — 6↔5 한 쌍이면 0
e = ev(B, R); sw = e['swap']
check("제안 있음", sw is not None)
check("같은 주포지션(탑·탑) 우선", sw['b']['nm'] == "b0#KR1" and sw['r']['nm'] == "r0#KR1" and sw['same_pos'], sw)
check("맞바꾼 뒤 50:50", (sw['bw'], sw['rw']) == (50, 50) and abs(e['gap'] - 2) < 1e-9, sw)
l = lines(e); check("교환 문구", l[1] == "🔄 b0(블루·탑) ↔ r0(레드·탑) 바꾸면 50% : 50%", l)
B = team("b", [8, 5, 5, 5, 5]); R = team("r", [5, 5, 5, 5, 5])    # 차 3 — 어떤 1:1 도 못 줄임(8↔5 = −3)
check("줄일 수 없으면 제안 없음", ev(B, R)['swap'] is None and len(lines(ev(B, R))) == 1)
B = team("b", [5, 5, 5, 5, 5]); R = team("r", [5, 5, 5, 5, 5])
for c in B: c['pw'] = 6.0
for c in R: c['pw'] = 5.0           # 균일 +1 → 한 쌍 교환은 차를 못 바꾼다(0) → 제안 없음이 맞다
e = ev(B, R); check("균일 격차: 한 쌍 교환으로 줄어든다", e['swap'] is not None and e['swap']['bw'] < e['bw'])
# 포지션 비어 있음: 같은 포지션 취급 안 함, 문구에 포지션 생략
B = team("b", [6, 6, 5, 5, 5], poss=("", "", "", "", "")); R = team("r", [5] * 5, poss=("", "", "", "", ""))
e = ev(B, R); l = lines(e)
check("포지션 없음 안전", e['swap'] and not e['swap']['same_pos'] and "(블루)" in l[1] and "(레드)" in l[1], l)
# 영어 포지션 값 → 한글
B = team("b", [6, 6, 5, 5, 5], poss=("JUNGLE", "TOP", "MIDDLE", "BOTTOM", "UTILITY")); R = team("r", [5] * 5, poss=("JUNGLE", "TOP", "MIDDLE", "BOTTOM", "UTILITY"))
check("영문 포지션 한글화", "(블루·정글)" in lines(ev(B, R))[1])
# 10명 미만/초과·중복
check("9명 None", ev(team("b", [5] * 5), team("r", [5] * 4)) is None and lines(None) == [])
check("빈 로비", ev([], []) is None)
dupe = team("r", [5] * 5); dupe[0]['nm'] = "B0#KR1"
check("같은 사람 중복(대소문자 무시) None", ev(team("b", [5] * 5), dupe) is None)
blank = team("r", [5] * 5); blank[1]['nm'] = ""
check("이름 빈 선수 None", ev(team("b", [5] * 5), blank) is None)
# 개인 점수 비노출
e = ev(team("b", [8.123, 5, 5, 5, 5]), team("r", [5.456, 5, 5, 5, 5])); txt = " ".join(lines(e))
check("개인 점수 미표시", "8.123" not in txt and "5.456" not in txt and "8.1" not in txt, txt)
# 시작 전 예상 한 줄
f = ns['_pre_game_report_line']
check("리포트 레드 승", f(44, 200) == "⚖️ 시작 전 예상 44:56 → 레드 승")
check("리포트 블루 승", f(60, 100) == "⚖️ 시작 전 예상 60:40 → 블루 승")
check("승자 모름/예상 없음", f(44, 0) == "" and f(None, 100) == "" and f("x", 100) == "")
# 실제 전력 함수 통합: 기록·티어 없는 선수(기본값)도 계산되고, 같은 산식과 일치
TIERS.update({"강자": "1上", "약자": "3下"})
def ent(nm, g=None, wr_=0.5, pos=""): return ({'name': nm, 'pos': pos}, ({'games': g, 'overall_wr': wr_} if g is not None else {}))
bl = [ent("강자#1", 50, 0.7, "탑")] + [ent(f"신입{i}#1") for i in range(4)]
rd = [ent("약자#1", 50, 0.3, "탑")] + [ent(f"뉴비{i}#1") for i in range(4)]
exp = ns['_unified_power_one']("강자#1", {'games': 50, 'overall_wr': 0.7}) - ns['_unified_power_one']("약자#1", {'games': 50, 'overall_wr': 0.3})
t = ns['_lobby_balance_text'](bl, rd)
check("통합: 기본값 선수 포함 계산", t.startswith(f"⚖️ 예상 승률 블루 {wr(exp)}%") and "🔄" in t, t)
check("통합: 10명 아님 빈 문자열", ns['_lobby_balance_text'](bl[:4], rd) == "")
print("\nFAILED: %s" % FAILS if FAILS else "\nALL PASS")
sys.exit(1 if FAILS else 0)
