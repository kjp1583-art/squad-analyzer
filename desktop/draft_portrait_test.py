"""고스트밴픽왕 카드 초상화 시험 — squad_analyzer.py 는 Windows 전용 import 가 많아 필요한 함수만 AST 로 뽑아 돌린다.
확인: 이름 정리 · 초상화 없으면 None(이름 글자 폴백) · 받는 중 중복 요청 안 함 · 받기 실패 후 재시도 폭주 없음 · Pillow 없으면 None."""
import ast, os, re, sys, threading, time
src = open(os.path.join(os.path.dirname(__file__), "squad_analyzer.py"), encoding="utf-8").read()
tree = ast.parse(src); want = {"_draft_champ_key", "_draft_portrait"}; nodes = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in want: nodes.append(n)
    if isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("_DRAFT_PORT_SZ", "_DRAFT_PORT_TK", "_DRAFT_PORT_FETCHING") for t in n.targets): nodes.append(n)
calls = []
def _prefetch(k): calls.append(k); time.sleep(0.05); ns["_SPELL_IMG_RAW"][k] = None   # 못 받은 경우
ns = {"re": re, "threading": threading, "PILLOW_INSTALLED": True, "_SPELL_IMG_RAW": {}, "_DRAFT_OVL": {"shown": "x"}, "_spell_prefetch_img": _prefetch, "BytesIO": None, "Image": None, "ImageTk": None}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "x", "exec"), ns)
ok = lambda c, m: (print(("PASS " if c else "FAIL ") + m), c or sys.exit(1))
K = ns["_draft_champ_key"]
ok(K("*리 신*") == "리 신" and K("아리 (미드)") == "아리" and K(" 아트록스 ") == "아트록스", "이름 정리(강조표시·괄호 제거)")
P = ns["_draft_portrait"]
ok(P("아리") is None, "처음엔 None → 이름 글자 폴백")
time.sleep(0.2)
ok(calls == ["아리"] and P("아리") is None, "받기 실패 기록 뒤엔 재요청 안 함")
ns["PILLOW_INSTALLED"] = False
ok(P("가렌") is None and calls == ["아리"], "Pillow 없으면 None · 요청도 안 함")
ns["PILLOW_INSTALLED"] = True
ns["_DRAFT_PORT_FETCHING"].add("진"); ok(P("진") is None and "진" not in calls, "받는 중이면 중복 요청 없음")
print("ALL PASS")
