"""고스트밴픽왕 맵 제한 단위 테스트 — squad_analyzer.py 는 Windows 전용 import 가 많아 필요한 함수만 AST 로
   떼어 가짜 gui_data 와 함께 실행한다. 가짜 데이터만 쓴다(외부 접속·실제 롤 클라이언트 없음).
   python desktop/coach_map_test.py"""
import ast, io, os, re, threading, unittest
from contextlib import redirect_stdout

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py")
TEXT = open(SRC, encoding="utf-8").read()
FUNCS = {"_coach_map_int", "coach_map_ok", "_coach_map_gate"}
VARS = {"COACH_MAP_ID", "_COACH_MAP_GATE"}


def load():
    tree = ast.parse(TEXT)
    body = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in FUNCS)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in VARS for t in n.targets))]
    ns = {"gui_lock": threading.Lock(), "gui_data": {"draft_advice": "📌 이전 추천", "draft_advice_ts": 123.0}}
    exec(compile(ast.Module(body=body, type_ignores=[]), SRC, "exec"), ns)
    return ns


class T(unittest.TestCase):
    def test_truth_table(self):
        ok = load()["coach_map_ok"]
        for m in (11, "11"):
            self.assertTrue(ok(True, m), m)
            self.assertFalse(ok(False, m), "비커스텀")
        for m in (12, 14, 21, 22, 30, 33, 0, -1):
            self.assertFalse(ok(True, m), m)
            self.assertFalse(ok(False, m), m)

    def test_silent_defaults_to_rift(self):
        ok = load()["coach_map_ok"]
        self.assertTrue(ok(True, None))
        self.assertTrue(ok(True, None, None))
        self.assertTrue(ok(True, "", "abc"))        # 읽을 수 없는 값 = 침묵
        self.assertFalse(ok(False, None))           # 비커스텀은 여전히 막힘

    def test_source_conflict_blocks(self):
        ok = load()["coach_map_ok"]
        self.assertFalse(ok(True, 11, 12))
        self.assertFalse(ok(True, 12, 11))
        self.assertFalse(ok(True, 11, 30))
        self.assertFalse(ok(True, None, 12))        # 한쪽만 말해도 11 이 아니면 막음
        self.assertFalse(ok(True, 14, None))
        self.assertTrue(ok(True, 11, 11))
        self.assertTrue(ok(True, 11, None))
        self.assertTrue(ok(True, None, 11))

    def test_gate_logs_once_and_clears_card(self):
        ns = load(); gate = ns["_coach_map_gate"]; gd = ns["gui_data"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            for _ in range(20): self.assertFalse(gate(True, 12, 12))
        self.assertEqual(buf.getvalue().count("[coach-map]"), 1, buf.getvalue())
        self.assertEqual((gd["draft_advice"], gd["draft_advice_ts"]), ("", 0))
        gd["draft_advice"] = "새 카드"                 # 같은 상태가 이어지는 동안엔 다시 건드리지 않는다
        with redirect_stdout(io.StringIO()): gate(True, 12, 12)
        self.assertEqual(gd["draft_advice"], "새 카드")
        buf = io.StringIO()
        with redirect_stdout(buf):                     # 상태가 바뀌면(다른 맵) 다시 한 번
            gate(True, 30, None); gate(True, 30, None)
        self.assertEqual(buf.getvalue().count("[coach-map]"), 1)

    def test_gate_ok_and_noncustom_are_silent(self):
        ns = load(); gate = ns["_coach_map_gate"]; gd = ns["gui_data"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(gate(True, 11, 11)); self.assertTrue(gate(True, None))
            self.assertFalse(gate(False, 12)); self.assertFalse(gate(False, 11))
        self.assertEqual(buf.getvalue(), "")
        self.assertEqual(gd["draft_advice"], "📌 이전 추천")   # 막힌 게 아니면 카드 안 건드림
        with redirect_stdout(io.StringIO()): gate(True, 12)    # 막힘 → 협곡으로 돌아오면 다시 로그 가능
        with redirect_stdout(io.StringIO()): self.assertTrue(gate(True, 11))
        buf = io.StringIO()
        with redirect_stdout(buf): gate(True, 12)
        self.assertEqual(buf.getvalue().count("[coach-map]"), 1)

    def test_call_site_uses_gate(self):
        self.assertNotIn("map_id != 12", TEXT, "옛 조건이 남아 있다")
        calls = re.findall(r"^\s*(?:try:\s*)?_draft_coach_tick\(", TEXT, re.M)
        self.assertEqual(len(calls), 1, "진입점 호출은 한 곳이어야 한다")
        i = TEXT.rindex("_draft_coach_tick(s_json, headers, base_url)")
        self.assertIn("if _coach_map_gate(is_custom_game_flag, gd_map_raw, gd_qmap_raw):", TEXT[i - 400:i])
        self.assertEqual(TEXT.count("_draft_coach_tick("), 2)   # 정의 1 + 호출 1


if __name__ == "__main__":
    unittest.main()
