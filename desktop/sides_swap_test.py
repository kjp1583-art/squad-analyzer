"""진영 라벨 뒤바뀜 감지 시험(2026-11-20 #8464934822) — squad_analyzer.py 에서 순수 함수만 AST 로 뽑아 돌린다."""
import ast, os, sys
src = open(os.path.join(os.path.dirname(__file__), "squad_analyzer.py"), encoding="utf-8").read()
want = {"_side_tid", "_eog_puuid_team", "_sides_swapped"}
nodes = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name in want]
ns = {}; exec(compile(ast.Module(body=nodes, type_ignores=[]), "x", "exec"), ns)
ok = lambda c, m: (print(("PASS " if c else "FAIL ") + m), c or sys.exit(1))
T, SW = ns["_eog_puuid_team"], ns["_sides_swapped"]
# LCU eog 형식(teams[].players[])
eog = {"teams": [{"teamId": 100, "players": [{"puuid": f"P{i}"} for i in range(5)]}, {"teamId": 200, "players": [{"puuid": f"Q{i}"} for i in range(5)]}]}
pt = T(eog); ok(len(pt) == 10 and pt["p0"] == 100 and pt["q4"] == 200, "eog teams.players → puuid:teamId")
# Match-V5 형식(participants[].puuid/teamId)
v5 = {"participants": [{"puuid": f"P{i}", "teamId": 100} for i in range(5)] + [{"puuid": f"Q{i}", "teamId": 200} for i in range(5)]}
ok(T(v5)["Q2"] == 200 if "Q2" in T(v5) else T(v5)["q2"] == 200, "Match-V5 participants")
# participantIdentities 형식
ident = {"participants": [{"participantId": i + 1, "teamId": 100 if i < 5 else 200} for i in range(10)], "participantIdentities": [{"participantId": i + 1, "player": {"puuid": f"U{i}"}} for i in range(10)]}
ok(T(ident)["u7"] == 200 and T(ident)["u0"] == 100, "participantIdentities")
ok(T(None) == {} and T({"participants": "x"}) == {}, "깨진 입력은 빈 dict")
# 뒤바뀜 판정
right = [("블루팀", f"P{i}") for i in range(5)] + [("레드팀", f"Q{i}") for i in range(5)]
flip = [("레드팀", f"P{i}") for i in range(5)] + [("블루팀", f"Q{i}") for i in range(5)]
ok(not SW(right, pt), "라벨이 맞으면 False")
ok(SW(flip, pt), "전부 반대면 True (#8464934822 형태)")
ok(not SW(flip[:2], pt), "근거 2명뿐이면 건드리지 않는다")
mixed = flip[:4] + right[4:]
ok(not SW(mixed, pt), "섞여 있으면(일부만 틀림) 건드리지 않는다")
ok(not SW([("블루팀", "zzz")] * 5, pt) and not SW(flip, {}), "PUUID 를 모르면 건드리지 않는다")
print("ALL PASS")
