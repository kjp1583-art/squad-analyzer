# -*- coding: utf-8 -*-
"""⚡ [v83.86] 분석기 첫 시작 로딩 지연 제거 회귀 테스트.

재는 것
  ① 시작 지터 제거 — lcu_core_backend_loop 이 시작하자마자(pid%25 0~24초 대기 없이) LCU 를 본다.
  ② 시트 연결 비차단 — connect_sheet() 가 느리거나 실패해도 LCU 폴링이 먼저 돌고, 연결은 백그라운드에서 끝난다.
  ③ 재연결 정책 보존 — 동시 실행 가드(중복 스레드 금지)와 실패 백오프(첫 실패 12초 → 90·180…, 인스턴스 지터)가 그대로.
  ④ connect_sheet 내부 병렬화 — LINK_ACCOUNT·CLAN_TIERS·CLAN_POSITIONS 를 gviz 로 병렬로 당기고(직렬 합 시간이 아님),
     gviz 가 실패하면 서비스계정 폴백으로 값이 그대로 들어온다.
  ⑤ HOF 프리로드 — 협곡·칼바람 두 탭 다운로드가 직렬 대기가 아니라 병렬이고, 연결 성공 직후(지터 없이) 시작된다.

   python3 tests/analyzer_startup_fast_test.py        (창·네트워크 없이 실행)
"""
import ast
import os
import sys
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from _analyzer_headless import load_analyzer  # noqa: E402

S = load_analyzer()
SRC_PATH = os.path.join(ROOT, "desktop", "squad_analyzer.py")
SRC = open(SRC_PATH, encoding="utf-8").read()
TREE = ast.parse(SRC)


def _func_src(name):
    """모듈 소스에서 함수 1개의 소스 문자열(데코레이터 제외)."""
    for node in TREE.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = SRC.splitlines()[node.lineno - 1: node.end_lineno]
            return "\n".join(seg)
    raise AssertionError(f"{name} not found")


def _reset_sheet_conn():
    with S._SHEET_CONN_LOCK:
        S._SHEET_CONN.update({"running": False, "attempts": 0, "fail": 0, "next_try": 0.0, "last_ok_ts": 0.0})


class StartupJitterTest(unittest.TestCase):
    """① pid%25 지터가 사라지고 LCU 폴링이 0초에 시작한다."""

    def test_no_pid_jitter_sleep_in_loop_source(self):
        src = _func_src("lcu_core_backend_loop")
        self.assertNotIn("getpid() % 25", src, "시작 지터(time.sleep(pid%25))가 남아 있으면 안 된다")
        self.assertNotIn("pid % 25", src)
        # 주석을 뺀 '실제 코드'로 본다 — 루프 진입 전 connect_sheet() 를 동기로 부르면 LCU 시작이 막힌다.
        code = "\n".join(l.split("#")[0] for l in src.splitlines())
        head = code.split("while True:")[0]
        self.assertNotIn("connect_sheet()", head,
                         "while 루프 진입 전 connect_sheet() 동기 호출이 남아 있으면 LCU 시작이 막힌다")
        self.assertIn('_kick_sheet_connect("start"', head)


class LoopStartsBeforeSheetTest(unittest.TestCase):
    """② LCU 폴링은 시트 연결을 기다리지 않는다(연결이 3초 걸려도 첫 LCU 조회는 곧바로)."""

    CONNECT_DELAY = 1.5

    def setUp(self):
        _reset_sheet_conn()
        self._orig = (S.connect_sheet, S.get_lcu_credentials, S.load_bot_token, S.update_hof_stats)

    def tearDown(self):
        S.connect_sheet, S.get_lcu_credentials, S.load_bot_token, S.update_hof_stats = self._orig
        _reset_sheet_conn()

    def test_first_lcu_poll_does_not_wait_for_sheet(self):
        t0 = [0.0]
        connect_done = [0.0]
        polled = []

        def slow_connect():
            time.sleep(self.CONNECT_DELAY)
            connect_done[0] = time.time()
            return False

        def fake_creds():
            if not polled:
                polled.append(time.time())
            if len(polled) >= 1:
                raise SystemExit  # 루프 종료(스레드 안에서 조용히 끝난다)
            return "", ""

        S.connect_sheet = slow_connect
        S.get_lcu_credentials = fake_creds
        S.load_bot_token = lambda: None
        S.update_hof_stats = lambda *a, **k: None

        t0[0] = time.time()
        th = threading.Thread(target=S.lcu_core_backend_loop, daemon=True)
        th.start()
        th.join(10)

        self.assertTrue(polled, "LCU 폴링이 한 번도 돌지 않았다")
        first_poll_delay = polled[0] - t0[0]
        self.assertLess(first_poll_delay, 1.0,
                        f"첫 LCU 조회가 {first_poll_delay:.2f}s — 시트 연결을 기다린 것으로 보인다")
        # 그 시점에 시트 연결은 아직 '진행 중'이어야 한다(동시 진행 = 비차단)
        self.assertFalse(connect_done[0] and connect_done[0] < polled[0],
                         "시트 연결이 끝난 뒤에야 LCU 가 돌았다(직렬)")

    def test_slow_connect_still_completes_in_background(self):
        """연결이 루프와 별개 스레드에서 끝나고, 성공하면 상태 문구가 갱신된다."""
        S.connect_sheet = lambda: True
        S.load_bot_token = lambda: None
        S.update_hof_stats = lambda *a, **k: None
        S._kick_sheet_connect("reconnect", force=True)
        deadline = time.time() + 5
        while time.time() < deadline and S._SHEET_CONN["running"]:
            time.sleep(0.02)
        self.assertFalse(S._SHEET_CONN["running"])
        self.assertEqual(S._SHEET_CONN["fail"], 0)
        self.assertAlmostEqual(S._SHEET_CONN["next_try"], 0.0)

    def test_host_hof_preload_starts_immediately_after_connect(self):
        """연결 성공 → 지터 없이 바로 update_hof_stats 시작."""
        t_conn, t_hof = [0.0], [0.0]

        def connect():
            time.sleep(0.2)
            t_conn[0] = time.time()
            return True

        def hof(*a, **k):
            t_hof[0] = time.time()

        S.connect_sheet = connect
        S.load_bot_token = lambda: "tok"      # 호스트
        S.update_hof_stats = hof
        S._kick_sheet_connect("start", force=True)
        deadline = time.time() + 5
        while time.time() < deadline and not t_hof[0]:
            time.sleep(0.02)
        self.assertTrue(t_conn[0] and t_hof[0], "연결 후 HOF 프리로드가 시작되지 않았다")
        self.assertLess(t_hof[0] - t_conn[0], 0.5, "연결 완료 뒤 지터/직렬 대기가 남아 있다")


class SheetConnectPolicyTest(unittest.TestCase):
    """③ 재연결 정책(중복 금지·백오프·지터) 보존."""

    def setUp(self):
        _reset_sheet_conn()
        self._orig = (S.connect_sheet, S.load_bot_token, S.update_hof_stats)

    def tearDown(self):
        S.connect_sheet, S.load_bot_token, S.update_hof_stats = self._orig
        _reset_sheet_conn()

    def _wait_idle(self, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline and S._SHEET_CONN["running"]:
            time.sleep(0.02)

    def test_single_flight_while_connecting(self):
        S.connect_sheet = lambda: (time.sleep(0.6), True)[1]
        S.load_bot_token = lambda: None
        S.update_hof_stats = lambda *a, **k: None
        self.assertTrue(S._kick_sheet_connect("start", force=True))
        self.assertFalse(S._kick_sheet_connect("reconnect"), "진행 중인데 또 던졌다(중복 실행)")
        self.assertFalse(S._kick_sheet_connect("reconnect", force=True))
        self._wait_idle()
        self.assertEqual(S._SHEET_CONN["attempts"], 1, "연결 시도가 1회를 넘었다")

    def test_failure_sets_backoff_and_blocks_retry(self):
        S.connect_sheet = lambda: False
        S.load_bot_token = lambda: None
        S.update_hof_stats = lambda *a, **k: None
        S._kick_sheet_connect("start", force=True)
        self._wait_idle()
        self.assertEqual(S._SHEET_CONN["fail"], 1)
        wait_left = S._SHEET_CONN["next_try"] - time.time()
        # 첫 실패 특례 12초 + 인스턴스 지터(0~29초)
        self.assertGreaterEqual(wait_left, 5.0, f"첫 실패 백오프가 너무 짧다({wait_left:.1f}s)")
        self.assertLessEqual(wait_left, 45.0)
        self.assertFalse(S._kick_sheet_connect("reconnect"), "백오프 대기 중인데 바로 재시도했다")

    def test_backoff_grows_and_caps(self):
        S.connect_sheet = lambda: False
        S.load_bot_token = lambda: None
        S.update_hof_stats = lambda *a, **k: None
        with S._SHEET_CONN_LOCK:
            S._SHEET_CONN["fail"] = 4
        S._kick_sheet_connect("reconnect", force=True)
        self._wait_idle()
        self.assertEqual(S._SHEET_CONN["fail"], 5)
        wait_left = S._SHEET_CONN["next_try"] - time.time()
        self.assertLessEqual(wait_left, 900 + 30 + 1)

    def test_loop_schedules_reconnect_without_calling_connect(self):
        """루프의 재연결 블록은 connect_sheet() 를 직접 부르지 않는다(백그라운드 킥만)."""
        src = _func_src("lcu_core_backend_loop")
        body = src.split("while True:")[1]
        self.assertNotIn("if connect_sheet()", body)
        self.assertIn("_kick_sheet_connect(\"reconnect\")", body)


class _FakeWS:
    def __init__(self, title, gid, rows=None, fail_svc=False):
        self.title = title
        self.id = gid
        self._rows = rows or []
        self.fail_svc = fail_svc
        self.svc_calls = 0

    def get_all_values(self):
        self.svc_calls += 1
        if self.fail_svc:
            raise RuntimeError("429")
        return self._rows

    def props(self):
        return {"properties": {"title": self.title, "sheetId": self.id}}


class _FakeSheet:
    def __init__(self, tabs):
        self.tabs = tabs
        # open_by_key 가 받아오는 메타데이터 — 이걸로 gid 를 '오프라인'으로 찾아야 API 0회
        self._properties = {"sheets": [{"properties": {"title": t, "sheetId": w.id}}
                                       for t, w in tabs.items()]}
        self.worksheet_calls = []

    def worksheet(self, title):
        self.worksheet_calls.append(title)
        if title not in self.tabs:
            raise KeyError(title)
        return self.tabs[title]

    def worksheets(self):
        return list(self.tabs.values())


class _FakeClient:
    def __init__(self, sheet):
        self.sheet = sheet

    def open_by_key(self, key):
        return self.sheet


class ConnectSheetParallelTest(unittest.TestCase):
    """④ connect_sheet 부가 탭 3종: gviz 병렬 + 서비스계정 폴백."""

    DELAY = 0.6

    def setUp(self):
        self._orig = (S.ServiceAccountCredentials, S.gspread.authorize, S._gviz_rows_by_gid,
                      S.global_spreadsheet)
        self.saved = (dict(S.global_alt_map), dict(S.TIER_OF), dict(S.POSITION_OF))

    def tearDown(self):
        S.ServiceAccountCredentials, S.gspread.authorize, S._gviz_rows_by_gid, \
            S.global_spreadsheet = self._orig
        for d, keep in ((S.global_alt_map, self.saved[0]), (S.TIER_OF, self.saved[1]),
                        (S.POSITION_OF, self.saved[2])):
            d.clear(); d.update(keep)

    def _install(self, sheet, gviz):
        class _Creds:
            @staticmethod
            def from_json_keyfile_name(*a, **k):
                return _Creds()
        S.ServiceAccountCredentials = _Creds
        S.gspread.authorize = lambda creds: _FakeClient(sheet)
        S._gviz_rows_by_gid = gviz

    def _tabs(self, svc_fail=False):
        return {
            "LINK_ACCOUNT": _FakeWS("LINK_ACCOUNT", 11,
                                    [["본계", "부계"], ["맛동산장인유미", "귤갓입니다#KR1"]], svc_fail),
            "CLAN_TIERS": _FakeWS("CLAN_TIERS", 22,
                                  [["닉네임", "티어"], ["맛동산장인유미", "0"], ["귤갓입니다", "1상"]], svc_fail),
            "CLAN_POSITIONS": _FakeWS("CLAN_POSITIONS", 33,
                                      [["닉네임", "", "주포지션", "부포지션"], ["맛동산장인유미", "", "미드", "정글/탑"]],
                                      svc_fail),
        }

    def test_three_tabs_load_in_parallel(self):
        tabs = self._tabs()
        rows_by_gid = {11: tabs["LINK_ACCOUNT"]._rows, 22: tabs["CLAN_TIERS"]._rows,
                       33: tabs["CLAN_POSITIONS"]._rows}
        calls = []

        def gviz(gid, timeout=8):
            calls.append(gid)
            time.sleep(self.DELAY)
            return rows_by_gid.get(gid)

        self._install(_FakeSheet(tabs), gviz)
        t0 = time.time()
        S.connect_sheet()
        elapsed = time.time() - t0

        self.assertLess(elapsed, self.DELAY * 2.2,
                        f"부가 탭 3종이 병렬이 아니다({elapsed:.2f}s — 직렬이면 {self.DELAY * 3:.1f}s)")
        self.assertEqual(sorted(calls), [11, 22, 33], "gviz 는 ws.id(gid)로만 불러야 한다(이름 호출=첫시트 오반환 위험)")
        # 값이 실제로 반영됐는가
        self.assertEqual(S.global_alt_map.get("귤갓입니다"), "맛동산장인유미")
        self.assertEqual(S.TIER_OF.get(S.tnorm("귤갓입니다")), "1상")
        self.assertEqual(S.POSITION_OF.get(S.tnorm("맛동산장인유미")), ("미드", "정글/탑"))
        # gviz 성공 경로에서는 서비스계정 읽기·탭 메타데이터 조회를 하지 않는다(할당량 0 + 추가 지연 없음)
        self.assertEqual(sum(w.svc_calls for w in tabs.values()), 0)
        self.assertEqual(S.global_spreadsheet.worksheet_calls, [], "탭 메타데이터 GET(gspread.worksheet)이 남아 있으면 또 느려진다")

    def test_gviz_failure_falls_back_to_service_account(self):
        tabs = self._tabs()
        self._install(_FakeSheet(tabs), lambda gid, timeout=8: None)
        self.assertTrue(S.connect_sheet())
        self.assertEqual(sum(w.svc_calls for w in tabs.values()), 3, "gviz 실패 시 서비스계정 폴백이 없어졌다")
        self.assertEqual(S.global_alt_map.get("귤갓입니다"), "맛동산장인유미")
        self.assertEqual(S.TIER_OF.get(S.tnorm("귤갓입니다")), "1상")
        self.assertEqual(S.POSITION_OF.get(S.tnorm("맛동산장인유미")), ("미드", "정글/탑"))

    def test_failed_tab_keeps_previous_values(self):
        tabs = self._tabs(svc_fail=True)
        self._install(_FakeSheet(tabs), lambda gid, timeout=8: None)
        before_tier = dict(S.TIER_OF)
        self.assertTrue(S.connect_sheet())          # 연결 자체는 성공(탭 실패는 치명 아님)
        self.assertEqual(S.TIER_OF, before_tier, "실패한 탭에서 기존 티어표를 지웠다")

    def test_missing_tab_does_not_break_connect(self):
        tabs = self._tabs()
        tabs.pop("CLAN_POSITIONS")
        gids = {11: tabs["LINK_ACCOUNT"]._rows, 22: tabs["CLAN_TIERS"]._rows}
        self._install(_FakeSheet(tabs), lambda gid, timeout=8: gids.get(gid))
        self.assertTrue(S.connect_sheet())
        self.assertEqual(S.TIER_OF.get(S.tnorm("귤갓입니다")), "1상")   # 있는 탭은 정상 반영

    def test_offline_gid_lookup_falls_back_to_listing_once(self):
        """메타데이터가 비어 있는 경우(구버전 gspread)에도 동작하고, 목록 질의는 1회만 한다."""
        tabs = self._tabs()
        sheet = _FakeSheet(tabs)
        sheet._properties = {}                      # 메타데이터 없음
        calls = []
        orig_worksheets = sheet.worksheets

        def counting_worksheets():
            calls.append(1)
            return orig_worksheets()

        sheet.worksheets = counting_worksheets
        self._install(sheet, lambda gid, timeout=8: tabs and {11: tabs["LINK_ACCOUNT"]._rows}.get(gid))
        self.assertTrue(S.connect_sheet())
        self.assertEqual(len(calls), 1, "목록 질의가 1회를 넘었다")
        self.assertEqual(S.global_alt_map.get("귤갓입니다"), "맛동산장인유미")


class HofPrefetchParallelTest(unittest.TestCase):
    """⑤ 협곡·칼바람 프리로드가 병렬(직렬 합 아님)."""

    DELAY = 0.7

    def setUp(self):
        self._orig = (S.get_sheet_data_cached, S.load_bot_token, S.global_spreadsheet)

    def tearDown(self):
        S.get_sheet_data_cached, S.load_bot_token, S.global_spreadsheet = self._orig

    def test_both_tabs_download_concurrently(self):
        fetched = []
        lock = threading.Lock()

        def fake_rows(ws, force=False, prefer_service=False):
            with lock:
                first = ws.title not in fetched
                if first:
                    fetched.append(ws.title)
            if first:
                time.sleep(self.DELAY)
                S.global_cache_time[ws.title] = time.time()   # 캐시에 담긴 것처럼
            return [["게임ID"]]                                # 1행 → 파싱 루프는 건너뛴다

        tabs = {"CLASSIC_NORMAL": _FakeWS("CLASSIC_NORMAL", 1), "KIWI_KIWI": _FakeWS("KIWI_KIWI", 2)}
        S.get_sheet_data_cached = fake_rows
        S.load_bot_token = lambda: None
        S.global_spreadsheet = _FakeSheet(tabs)

        t0 = time.time()
        S.update_hof_stats()
        elapsed = time.time() - t0

        self.assertEqual(sorted(fetched), ["CLASSIC_NORMAL", "KIWI_KIWI"])
        self.assertLess(elapsed, self.DELAY * 2.0,
                        f"협곡·칼바람 다운로드가 병렬이 아니다({elapsed:.2f}s — 직렬이면 {self.DELAY * 2:.1f}s)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
