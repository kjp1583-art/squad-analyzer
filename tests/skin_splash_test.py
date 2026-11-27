# -*- coding: utf-8 -*-
"""🎭 마지막 사용 스킨(LAST_SKIN 탭) 회귀 시험 — `python3 tests/skin_splash_test.py`

  (2026-11-27 사장님 「상현·하현·귀살대 카드 스플래시를 기본 일러스트 대신 그 사람이 마지막에 쓴 스킨으로」)

  A 수집 — 인게임 playerlist 의 skinID 만 뽑는다(0=기본 스킨도 유효 · 봇/관전자 skip · 문자열 숫자 허용)
  B 게임 기록 → 스킨 항목 — 그 판 10명만 · 챔피언 이름은 시트에 적힌 값 · 같은 (puuid,챔피언) 중복 없음 · 오래된 수집값은 안 씀
  C upsert — 새 탭이면 헤더와 함께 만들고 append · 같은 조합은 최신 skinID 로 덮어씀 · 같은 값이면 쓰기 0(멱등)
  D 안전 — 헤더가 다른 탭(엉뚱한 시트 폴백)에는 손대지 않음 · 읽기/쓰기 실패가 예외로 새지 않음 · 한 게임은 한 번만
  E 배선 — 수집이 인게임 playerlist 지점에, 기록이 finalize 지점에 붙어 있고 CLASSIC_NORMAL 열은 건드리지 않는다
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from _analyzer_headless import load_analyzer  # noqa: E402

S = load_analyzer()
SRC = open(os.path.join(ROOT, "desktop", "squad_analyzer.py"), encoding="utf-8").read()


class FakeCell:
    def __init__(self, row, col, value):
        self.row, self.col, self.value = row, col, value


class FakeWS:
    """gspread 워크시트 대역 — 실제로 쓰인 값만 메모리에 남긴다."""

    def __init__(self, rows=None, title="LAST_SKIN", broken=False):
        self.title = title
        self.rows = [list(r) for r in (rows or [])]
        self.row_count = max(len(self.rows), 1) + 10
        self.cells = []
        self.appended = []
        self.deleted = []
        self.broken = broken

    def get_all_values(self):
        if self.broken: raise RuntimeError("sheet down")
        return [list(r) for r in self.rows]

    def append_row(self, r, **k):
        self.appended.append(list(r)); self.rows.append(list(r))

    def append_rows(self, rs, **k):
        for r in rs: self.appended.append(list(r)); self.rows.append(list(r))

    def update_cells(self, cells):
        for c in cells:
            self.cells.append((c.row, c.col, c.value))
            while len(self.rows) < c.row: self.rows.append([])
            row = self.rows[c.row - 1]
            while len(row) < c.col: row.append("")
            row[c.col - 1] = c.value

    def add_rows(self, n):
        self.row_count += n

    def delete_rows(self, i):
        self.deleted.append(i); del self.rows[i - 1]


class FakeSS:
    def __init__(self, tabs=None):
        self.tabs = dict(tabs or {})

    def worksheet(self, name):
        if name not in self.tabs: raise RuntimeError("no tab " + name)
        return self.tabs[name]

    def add_worksheet(self, title, rows=0, cols=0):
        ws = FakeWS([], title=title); self.tabs[title] = ws; return ws


def _with_ss(tabs):
    """global_spreadsheet 를 잠시 갈아 끼운다(테스트 끝나면 원복)."""
    ss = FakeSS(tabs)
    saved = S.global_spreadsheet
    S.global_spreadsheet = ss
    return ss, saved


HEAD = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "챔피언", "결과"]


def _row(gid, name, pu, champ):
    return ["#" + gid, "2026-11-27 21:00", name, pu, "블루팀", champ, "승리"]


class A_Collect(unittest.TestCase):
    def test_skin_int(self):
        self.assertEqual(S._skin_int(0), 0)          # 기본 스킨도 유효한 값
        self.assertEqual(S._skin_int("7"), 7)
        self.assertIsNone(S._skin_int(-1))
        self.assertIsNone(S._skin_int("x"))
        self.assertIsNone(S._skin_int(None))
        self.assertIsNone(S._skin_int(True))         # bool 은 숫자가 아니다

    def test_playerlist(self):
        players = [
            {"puuid": "PU-A", "summonerName": "가", "skinID": 5, "championName": "Ahri"},
            {"puuid": "PU-B", "riotIdGameName": "나", "skinID": "0", "championName": "Lux"},
            {"puuid": "PU-C", "summonerName": "다", "skinID": "이상한값"},
            {"summonerName": "봇", "skinID": 3},      # puuid 없음 → skip
            "not-a-dict",
            {"puuid": "PU-A", "summonerName": "가", "skinID": 9},   # 같은 판에서 다시 보이면 최신값
        ]
        out = S.collect_live_skins(players, out={})
        self.assertEqual(out["pu-a"]["skin_id"], 9)
        self.assertEqual(out["pu-a"]["name"], "가")
        self.assertEqual(out["pu-b"]["skin_id"], 0)
        self.assertIn("pu-b", out)
        self.assertEqual(len(out), 2)


class B_Entries(unittest.TestCase):
    def setUp(self):
        self.now = 1000000.0
        self.skins = {
            "pu-a": {"name": "가", "skin_id": 4, "at": self.now - 60},
            "pu-b": {"name": "나", "skin_id": 0, "at": self.now - 60},
            "pu-old": {"name": "옛날", "skin_id": 7, "at": self.now - 40 * 24 * 3600},
        }

    def test_only_this_game(self):
        rows = [HEAD, _row("1", "가", "PU-A", "아리"), _row("1", "나", "PU-B", "럭스"),
                _row("1", "가", "PU-A", "아리"),          # 중복 행
                _row("2", "가", "PU-A", "아리"),          # 다른 게임
                _row("1", "모름", "PU-X", "아리")]        # 수집값 없음
        ents = S.last_skin_entries_for_game(rows, HEAD, "#1", skins=self.skins, now=self.now)
        self.assertEqual([(e["puuid"], e["champion"], e["skin_id"]) for e in ents],
                         [("pu-a", "아리", 4), ("pu-b", "럭스", 0)])

    def test_champion_from_sheet_and_stale(self):
        rows = [HEAD, _row("1", "옛날", "PU-OLD", "누누와 윌럼프")]
        ents = S.last_skin_entries_for_game(rows, HEAD, "#1", skins=self.skins, now=self.now)
        self.assertEqual(ents, [])                     # 일주일 넘은 수집값은 쓰지 않는다
        self.skins["pu-old"]["at"] = self.now - 60
        ents = S.last_skin_entries_for_game(rows, HEAD, "#1", skins=self.skins, now=self.now)
        self.assertEqual(ents[0]["champion"], "누누와윌럼프")   # 시트 표기(공백 제거) 그대로
        self.assertEqual(ents[0]["skin_id"], 7)

    def test_empty_inputs(self):
        self.assertEqual(S.last_skin_entries_for_game([], HEAD, "#1", skins=self.skins), [])
        self.assertEqual(S.last_skin_entries_for_game([HEAD], HEAD, "#1", skins={}), [])
        self.assertEqual(S.last_skin_entries_for_game([HEAD], ["게임ID"], "#1", skins=self.skins), [])


class C_Upsert(unittest.TestCase):
    def test_creates_tab_and_appends(self):
        ss, saved = _with_ss({})
        try:
            res = S.upsert_last_skins([{"puuid": "PU-A", "name": "가", "champion": "아리", "skin_id": 4},
                                       {"puuid": "PU-B", "name": "나", "champion": "럭스", "skin_id": 0}])
        finally:
            S.global_spreadsheet = saved
        self.assertEqual(res["added"], 2)
        ws = ss.tabs["LAST_SKIN"]
        self.assertEqual(ws.rows[0], S.LAST_SKIN_HEADERS)
        self.assertEqual([r[:4] for r in ws.rows[1:]], [["pu-a", "가", "아리", 4], ["pu-b", "나", "럭스", 0]])
        self.assertGreaterEqual(ws.row_count, len(ws.rows))

    def test_updates_existing_row_only_on_change(self):
        head = list(S.LAST_SKIN_HEADERS)
        ws = FakeWS([head, ["pu-a", "옛이름", "아리", 0, "2026-11-20 21:00"]])
        res = S.upsert_last_skins([{"puuid": "PU-A", "name": "새이름", "champion": "아리", "skin_id": 5}], ws=ws)
        self.assertEqual(res["updated"], 1)
        self.assertEqual(ws.rows[1][3], 5)
        self.assertEqual(ws.rows[1][1], "새이름")
        self.assertEqual(len(ws.appended), 0)
        n_cells = len(ws.cells)
        res2 = S.upsert_last_skins([{"puuid": "PU-A", "name": "새이름", "champion": "아리", "skin_id": 5}], ws=ws)
        self.assertEqual(res2["updated"], 0)
        self.assertEqual(len(ws.cells), n_cells)      # 같은 값이면 쓰기 0(멱등)
        self.assertEqual(res2["added"], 0)

    def test_same_puuid_other_champion_is_new_row(self):
        ws = FakeWS([list(S.LAST_SKIN_HEADERS), ["pu-a", "가", "아리", 3, "2026-11-20 21:00"]])
        res = S.upsert_last_skins([{"puuid": "PU-A", "name": "가", "champion": "럭스", "skin_id": 1},
                                   {"puuid": "PU-A", "name": "가", "champion": "럭스", "skin_id": 1}], ws=ws)
        self.assertEqual(res["added"], 1)             # 같은 판에 중복 항목이 와도 한 줄만


class D_Safety(unittest.TestCase):
    def test_header_mismatch_is_untouched(self):
        ws = FakeWS([["게임ID", "날짜", "소환사명"], ["#1", "2026-11-27", "가"]])
        res = S.upsert_last_skins([{"puuid": "PU-A", "name": "가", "champion": "아리", "skin_id": 4}], ws=ws)
        self.assertEqual(res, {"updated": 0, "added": 0, "skipped": 1})
        self.assertEqual(len(ws.cells), 0)
        self.assertEqual(len(ws.appended), 0)

    def test_read_failure_does_not_raise(self):
        ws = FakeWS([list(S.LAST_SKIN_HEADERS)], broken=True)
        res = S.upsert_last_skins([{"puuid": "PU-A", "name": "가", "champion": "아리", "skin_id": 4}], ws=ws)
        self.assertEqual(res["added"], 0)

    def test_no_spreadsheet(self):
        saved = S.global_spreadsheet
        S.global_spreadsheet = None
        try:
            res = S.upsert_last_skins([{"puuid": "PU-A", "name": "가", "champion": "아리", "skin_id": 4}])
        finally:
            S.global_spreadsheet = saved
        self.assertEqual(res["skipped"], 1)

    def test_record_once_per_game(self):
        ss, saved = _with_ss({})
        S._LAST_SKIN_GIDS.clear()
        S._LIVE_SKINS.clear()
        S.collect_live_skins([{"puuid": "PU-A", "summonerName": "가", "skinID": 4}])
        rows = [HEAD, _row("1", "가", "PU-A", "아리")]
        try:
            a = S.record_last_skins(rows, HEAD, "#1")
            b = S.record_last_skins(rows, HEAD, "#1")      # 같은 게임 두 번째 호출
        finally:
            S.global_spreadsheet = saved
        self.assertEqual(a["added"], 1)
        self.assertEqual(b, {"updated": 0, "added": 0, "skipped": 0})
        self.assertEqual(len(ss.tabs["LAST_SKIN"].rows), 2)


class E_Wiring(unittest.TestCase):
    def test_collect_at_playerlist(self):
        self.assertRegex(SRC, r"isinstance\(lr_json, list\):\s*\n\s*# .*스킨.*\n\s*try: collect_live_skins\(lr_json\)")

    def test_record_at_finalize(self):
        m = re.search(r"threading\.Thread\(target=record_last_skins.*?\)\.start\(\)", SRC, re.S)
        self.assertIsNotNone(m, "finalize 지점에 스킨 기록 스레드가 없다")
        self.assertIn('args=(list(sheet_data_check), headers_ch, _finalize_gid)', m.group(0))

    def test_sheet_columns_untouched(self):
        # CLASSIC_NORMAL 헤더 목록에 skin 관련 열을 추가하지 않았다(별도 탭 방식)
        self.assertNotIn("skin_id", SRC.split("# ═══════ 🎭")[0])
        self.assertIn('LAST_SKIN_TAB = "LAST_SKIN"', SRC)


if __name__ == "__main__":
    unittest.main(verbosity=2)
