"""고스트밴픽왕 카드 초상화 시험 — squad_analyzer.py 는 Windows 전용 import 가 많아 필요한 함수만 AST 로 뽑아 돌린다.
확인: 이름 정리 · 초상화 없으면 None(이름 글자 폴백) · 받는 중 중복 요청 안 함 · 받기 실패 후 재시도 폭주 없음 · Pillow 없으면 None."""
import ast, os, re, sys, threading, time
src = open(os.path.join(os.path.dirname(__file__), "squad_analyzer.py"), encoding="utf-8").read()
tree = ast.parse(src); want = {"_draft_champ_key", "_draft_portrait", "_draft_loose_row", "_draft_prefetch_all"}; nodes = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in want: nodes.append(n)
    if isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("_DRAFT_PORT_SZ", "_DRAFT_PORT_TK", "_DRAFT_PORT_FETCHING", "_DRAFT_PORT_FAIL", "_DRAFT_PORT_RETRY_SEC", "_DRAFT_PORT_MAX_TRY") for t in n.targets): nodes.append(n)
calls = []
def _fetch(k): calls.append(k); time.sleep(0.05); return ns["_NEXT"].get(k)   # 못 받은 경우 None
def _parse_rec_champs(t): return [re.split(r"[—–\-:]", re.match(r"\s*\d+\s*[.)]\s*(.+)", l.strip()).group(1), 1)[0].strip() for l in t.split("\n") if re.match(r"\s*\d+\s*[.)]\s*(.+)", l.strip())]
ns = {"re": re, "threading": threading, "time": time, "PILLOW_INSTALLED": True, "_SPELL_IMG_RAW": {}, "_DRAFT_OVL": {"shown": "x"}, "_draft_fetch_icon": _fetch, "_NEXT": {},
      "BytesIO": None, "Image": None, "ImageTk": None, "_parse_rec_champs": _parse_rec_champs, "_split_reason": lambda t: (t, ""),
      "_champ_id_of": lambda k: {"아리": 103, "리신": 64, "제라스": 101}.get(str(k).replace(" ", ""), 0), "get_champ_eng_name": lambda k: None}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "x", "exec"), ns)
ok = lambda c, m: (print(("PASS " if c else "FAIL ") + m), c or sys.exit(1))
K = ns["_draft_champ_key"]
ok(K("*리 신*") == "리 신" and K("아리 (미드)") == "아리" and K(" 아트록스 ") == "아트록스", "이름 정리(강조표시·괄호 제거)")
P = ns["_draft_portrait"]
ok(P("아리") is None, "처음엔 None → 이름 글자 폴백")
time.sleep(0.2)
ok(calls == ["아리"] and P("아리") is None, "받기 실패 직후엔(쉬는 동안) 재요청 안 함")
ns["PILLOW_INSTALLED"] = False
ok(P("가렌") is None and calls == ["아리"], "Pillow 없으면 None · 요청도 안 함")
ns["PILLOW_INSTALLED"] = True
ns["_DRAFT_PORT_FETCHING"].add("진"); ok(P("진") is None and "진" not in calls, "받는 중이면 중복 요청 없음")
# ── 새로 고친 부분 ──
ns["_DRAFT_PORT_FAIL"]["아리"][1] -= 25      # 20초가 지났다고 치면
ns["_NEXT"]["아리"] = b"PNGDATA"
P("아리"); time.sleep(0.2)
ok(calls == ["아리", "아리"] and ns["_SPELL_IMG_RAW"].get("아리") == b"PNGDATA", "쉬고 나면 다시 받아 성공하면 저장(예전엔 영영 글자)")
ok("아리" not in ns["_DRAFT_PORT_FAIL"] and ns["_DRAFT_OVL"]["shown"] == "", "성공하면 실패 기록을 지우고 카드를 다시 그리게 한다")
for _ in range(7):
    ns["_DRAFT_PORT_FAIL"]["제라스"] = [ns["_DRAFT_PORT_FAIL"].get("제라스", [0, 0])[0], 0]
    P("제라스"); time.sleep(0.12)
n = calls.count("제라스"); ok(1 <= n <= 6, "계속 실패해도 %d번까지만 시도(무한 반복 없음)" % n)
L = ns["_draft_loose_row"]
ok(L("1. 아리 — 이유") == ("1", ("아리", "이유")), "느슨한 줄: 대시도 읽는다")
ok(L("2. 제라스: 돌진 차단") == ("2", ("제라스", "돌진 차단")), "느슨한 줄: 콜론 구분도 읽는다")
ok(L("3. 리 신") == ("3", ("리 신", "")), "느슨한 줄: 이유 없이 이름만 있어도 읽는다")
ok(L("1) 아리 (미드) — 이유")[1][0] == "아리 (미드)", "느슨한 줄: 괄호 포지션이 붙어도")
ok(L("4. 존재하지않는챔프 — 이유") is None and L("→ 아리") is None and L("🆚 아리") is None, "챔프가 아니거나 번호 줄이 아니면 None")
ns["_DRAFT_PORT_FAIL"].clear(); ns["_SPELL_IMG_RAW"].clear(); ns["_NEXT"]["리신"] = b"X"; calls.clear()
ns["_draft_prefetch_all"]("1. 리신 — 이유\n2. 아리 — 이유"); time.sleep(0.3)
ok(sorted(calls) == ["리신", "아리"] and ns["_SPELL_IMG_RAW"].get("리신") == b"X", "추천이 나오면 챔프들을 미리 받아 둔다")
print("ALL PASS")
