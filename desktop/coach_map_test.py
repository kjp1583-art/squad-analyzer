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
        for m in (12, 14, 21, 22, 30, 33):
            self.assertFalse(ok(True, m), m)
            self.assertFalse(ok(False, m), m)
        for m in (0, -1, "0"):                      # 0 이하는 「모름」 — 협곡 내전이 꺼지지 않게 침묵으로 본다
            self.assertTrue(ok(True, m), m)
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

    def test_zero_is_silent_not_a_block(self):       # 검증 지적: queue.mapId=0 이 협곡 내전을 꺼 버렸다
        ok = load()["coach_map_ok"]
        self.assertTrue(ok(True, 11, 0))
        self.assertTrue(ok(True, None, 0))
        self.assertTrue(ok(True, 0, 0, 0, 0))
        self.assertFalse(ok(True, 12, 0))
        self.assertFalse(ok(True, 0, 12))
        self.assertFalse(ok(True, 11, 11, 0, 12))    # 로비 값 하나만 12 여도 막는다

    def test_four_sources(self):
        ok = load()["coach_map_ok"]
        self.assertTrue(ok(True, 11, 11, 11, 11))
        self.assertTrue(ok(True, 11, None, None, 11))
        self.assertFalse(ok(True, None, None, None, 30))   # 로비 값만 있어도 아레나는 막힘
        self.assertFalse(ok(True, 30, None, None, None))   # 세션 최상위 map 만 있어도 막힘

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
        self.assertEqual(buf.getvalue().count("[coach-map] 통과"), 2, buf.getvalue())   # 통과도 상태(값)가 바뀔 때만 한 번씩 기록
        self.assertNotIn("건너뜀", buf.getvalue())
        self.assertIn("session.map=11", buf.getvalue())
        buf = io.StringIO()
        with redirect_stdout(buf): gate(True, 11); gate(True, 11)    # 같은 상태가 이어지면 다시 안 찍는다
        self.assertEqual(buf.getvalue().count("[coach-map]"), 1)
        self.assertEqual(gd["draft_advice"], "📌 이전 추천")   # 막힌 게 아니면 카드 안 건드림
        with redirect_stdout(io.StringIO()): gate(True, 12)    # 막힘 → 협곡으로 돌아오면 다시 로그 가능
        with redirect_stdout(io.StringIO()): self.assertTrue(gate(True, 11))
        buf = io.StringIO()
        with redirect_stdout(buf): gate(True, 12)
        self.assertEqual(buf.getvalue().count("[coach-map]"), 1)

    def test_gate_label_names_real_fields(self):
        ns = load(); buf = io.StringIO()
        with redirect_stdout(buf): ns["_coach_map_gate"](True, 30, None, 0, 11)
        self.assertIn("session.map=30 gameData.map=None queue.mapId=None lobby.mapId=11", buf.getvalue())

    def test_call_site_uses_gate(self):
        self.assertNotIn("map_id != 12", TEXT, "옛 조건이 남아 있다")
        calls = re.findall(r"^\s*(?:try:\s*)?_draft_coach_tick\(", TEXT, re.M)
        self.assertEqual(len(calls), 1, "진입점 호출은 한 곳이어야 한다")
        i = TEXT.rindex("_draft_coach_tick(s_json, headers, base_url)")
        self.assertIn("if _coach_map_gate(is_custom_game_flag, top_map_raw, gd_map_raw, gd_qmap_raw, coach_lobby_map[0]):", TEXT[i - 400:i])
        self.assertEqual(TEXT.count("_draft_coach_tick("), 2)   # 정의 1 + 호출 1

    def test_lobby_latch_and_gate_reset_wiring(self):   # 슬라이스 밖(로비 읽기·단계 전환)의 연결은 문자열로 확인
        self.assertEqual(TEXT.count("coach_lobby_map[0] = gc.get('mapId')"), 1)
        self.assertEqual(TEXT.count("coach_lobby_map[0] = None"), 1)
        self.assertEqual(TEXT.count("coach_lobby_map = [None]"), 1)
        self.assertIn('if current_phase != "ChampSelect": _COACH_MAP_GATE[0] = None', TEXT)

    # ---- 폴링 루프 구간을 글자 그대로 잘라 가짜 LCU 응답으로 실행 (LCU JSON → 맵 원값 → 관문 연결 검사) ----
    @staticmethod
    def _run_loop(gameflow, lobby_map_latch=None, status=200):
        a = TEXT.index('            c100, c200, multi_id = [], [], ""')
        i = TEXT.rindex("_draft_coach_tick(s_json, headers, base_url)")
        j = TEXT.index("\n", TEXT.index("except Exception: pass", i)) + 1      # 호출 바로 뒤 except 줄까지
        code = "def run():\n" + TEXT[a:j] + "            except Exception: pass\n            return called\n"
        ns = load(); called = []
        class R:
            def __init__(s, code, js): s.status_code, s._j = code, js
            def json(s): return s._j
        class Req:
            @staticmethod
            def get(url, **kw):
                if url.endswith("/lol-gameflow/v1/session"): return R(status, gameflow)
                if url.endswith("/lol-champ-select/v1/session"): return R(200, {"localPlayerCellId": 0})
                return R(404, {})
        ns.update(requests=Req, base_url="https://x", headers={}, current_phase="ChampSelect",
                  _cs_fresh=False, coach_lobby_map=[lobby_map_latch],
                  _draft_coach_tick=lambda *a: called.append(1))
        ns["called"] = called
        exec(compile(code, "loop_slice", "exec"), ns)
        with redirect_stdout(io.StringIO()):
            ns["run"]()
        return bool(called)

    def test_loop_reads_session_top_level_map(self):
        run = self._run_loop
        gf = lambda top=None, q=None, gdm=None, custom=True: {
            "phase": "ChampSelect", "map": ({"id": top} if top is not None else None),
            "gameData": {"isCustomGame": custom, "queue": ({"mapId": q} if q is not None else {}),
                         **({"map": {"id": gdm}} if gdm is not None else {})}}
        self.assertTrue(run(gf(top=11, q=11)))           # 협곡 내전
        self.assertTrue(run(gf(top=11, q=0)))            # queue.mapId=0 이어도 협곡 내전은 산다
        self.assertTrue(run(gf(top=11)))                 # queue 에 mapId 없음
        self.assertTrue(run(gf()))                       # 맵 정보 전부 침묵 → 종전 동작
        self.assertFalse(run(gf(top=12, q=0)))           # 칼바람 — 최상위 map 만으로 막힘
        self.assertFalse(run(gf(top=14)))                # 푸주한의 다리
        self.assertFalse(run(gf(top=30)))                # 아레나 — queue 객체가 비어 있어도 막힘
        self.assertFalse(run(gf(q=30)))                  # queue.mapId 만 와도 막힘
        self.assertFalse(run(gf(gdm=12)))                # 옛 형태 gameData.map 도 막힘
        self.assertFalse(run(gf(top=11, custom=False)))  # 커스텀이 아니면 막힘
        self.assertFalse(run(gf(top=11), status=500))    # 세션을 못 읽으면 커스텀 여부를 모른다 → 막힘
        self.assertTrue(run(gf(top=11), lobby_map_latch=11))
        self.assertFalse(run(gf(), lobby_map_latch=30))  # 세션이 침묵해도 로비에서 본 아레나는 막힘
        self.assertTrue(run(gf(top=11), lobby_map_latch=0))


if __name__ == "__main__":
    unittest.main()
