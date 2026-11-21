"""인게임 조회 줄이기 시험 — squad_analyzer.py 에서 _live_poll_skip 만 AST 로 뽑아 돌린다."""
import ast, os, sys
src = open(os.path.join(os.path.dirname(__file__), "squad_analyzer.py"), encoding="utf-8").read()
n = [x for x in ast.parse(src).body if isinstance(x, ast.FunctionDef) and x.name == "_live_poll_skip"]
ns = {}; exec(compile(ast.Module(body=n, type_ignores=[]), "x", "exec"), ns); f = ns["_live_poll_skip"]
ok = lambda c, m: (print(("PASS " if c else "FAIL ") + m), c or sys.exit(1))
ok(not f(None, "", set(), 0, 100), "기록 전(활성 기록 없음·처음 본 판)엔 매초 조회")
ok(not f(None, "g1", set(), 99.5, 100), "게임ID 는 봤지만 아직 기록 안 됐으면 매초 조회")
ok(f("g1", "g1", {"g1"}, 95, 100), "기록 확정 뒤 5초 지났으면 건너뜀")
ok(not f("g1", "g1", {"g1"}, 84, 100), "기록 확정 뒤 16초 지났으면 조회")
ok(f(None, "g2", {"g2"}, 99, 100), "봇 판처럼 기록 마킹만 된 판도 건너뜀")
ok(not f(None, "g3", {"g2"}, 99, 100), "새 게임ID(기록 안 됨)는 바로 조회")
print("ALL PASS")
