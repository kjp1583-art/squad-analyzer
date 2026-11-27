"""솔랭 SOLO_RANK 갱신 누락 방지 단위 테스트.
   squad_analyzer.py 는 Windows 전용 import 가 많아 필요한 함수만 AST 로 떼어 가짜 requests·가짜 시트로 돌린다.
   외부 접속·실제 시트·실제 Riot 키 없음.   python tests/solo_rank_preserve_test.py

   [2026-11-27 사장님 제보 '천쇄참월#天鎖斬月1 솔랭이 언랭'] 실제로는 다이아2 75LP 인데
   ① fetch_solo_rank_by_riotid 가 429/타임아웃에 바로 None 을 돌려주고
   ② update_solo_ranks 가 조회 실패 인원의 이전 SOLO_RANK 행을 남기지 않고 clear+update 로 통째로 지워서
   카드에 '언랭'으로 떴다. 이 테스트는 그 두 구멍(재시도 · 이전 행 보존)을 고정한다."""
import ast, os, time as _time, types, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("SA_SRC") or os.path.join(ROOT, "desktop", "squad_analyzer.py")
NAMES = {"_riot_get", "_fetch_summoner_profile", "fetch_solo_rank_by_riotid", "_carry_profile_icons",
         "update_solo_ranks", "tnorm"}

HDR = ["닉네임", "티어", "LP", "솔랭승", "솔랭패", "점수", "갱신", "아이콘", "레벨"]


def _source_text():
    with open(SRC, encoding="utf-8") as f:
        return f.read()


class Resp:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._b, self.headers = code, body, headers or {}

    def json(self):
        return self._b


class WS:
    """gspread 워크시트 흉내 — get_all_values 는 문자열로 돌려준다(실제 시트와 같게)."""
    def __init__(self, rows, cols=7):
        self.rows = [list(r) for r in rows]
        self.col_count = max([len(r) for r in self.rows] + [cols])
        self.row_count = 400
        self.cleared = False
        self.updated = None

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def clear(self):
        self.cleared = True
        self.rows = []

    def update(self, out):
        self.updated = [list(r) for r in out]
        self.rows = [list(r) for r in out]

    def add_cols(self, n):
        self.col_count += n

    def add_rows(self, n):
        self.row_count += n


class SS:
    def __init__(self, sheets=None):
        self.sheets = dict(sheets or {})

    def worksheet(self, name):
        if name in self.sheets:
            return self.sheets[name]
        raise Exception("no such worksheet")

    def add_worksheet(self, title, rows=0, cols=0):
        ws = WS([], cols=int(cols or 7))
        self.sheets[title] = ws
        return ws


def build(routes=None, sleeps=None):
    """필요한 함수만 떼어 가짜 requests/time/시트를 붙인 네임스페이스를 만든다."""
    tree = ast.parse(_source_text())
    mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES],
                     type_ignores=[])
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append(url)
        item = None
        for frag, seq in (routes or {}).items():
            if frag in url:
                item = seq.pop(0) if len(seq) > 1 else seq[0]
                break
        if item is None:
            return Resp(404)
        if isinstance(item, Exception):
            raise item
        return item

    sl = sleeps if sleeps is not None else []
    ns = {
        "requests": types.SimpleNamespace(get=get),
        "time": types.SimpleNamespace(sleep=sl.append, strftime=_time.strftime),
        "tnorm": None,
        "_rank_score": lambda t, d, lp: 1000 + int(lp or 0),
    }
    exec(compile(mod, SRC, "exec"), ns)
    ns["_calls"] = calls
    ns["_sleeps"] = sl
    return ns


# ---------------------------------------------------------------- ① 재시도

class RetryTest(unittest.TestCase):
    SOLO = [Resp(200, [{"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "II",
                        "leaguePoints": 75, "wins": 120, "losses": 98}])]

    def test_429_retry_then_ok(self):
        sl = []
        ns = build({"accounts/by-riot-id": [Resp(429, headers={"Retry-After": "3"}),
                                            Resp(429, headers={"Retry-After": "2"}),
                                            Resp(200, {"puuid": "P"})],
                    "summoners/by-puuid": [Resp(200, {"profileIconId": 4568, "summonerLevel": 312})],
                    "entries/by-puuid": self.SOLO}, sl)
        r = ns["fetch_solo_rank_by_riotid"]("천쇄참월#天鎖斬月1", "K")
        self.assertEqual((r["tier"], r["rank"], r["lp"], r["score"]), ("DIAMOND", "II", 75, 1075))
        self.assertEqual(sl, [3.0, 2.0], "Retry-After 만큼 기다린 뒤 재시도해야 한다")

    def test_429_without_header_waits_default(self):
        sl = []
        ns = build({"accounts/by-riot-id": [Resp(429), Resp(200, {"puuid": "P"})],
                    "entries/by-puuid": self.SOLO}, sl)
        self.assertEqual(ns["fetch_solo_rank_by_riotid"]("a#KR1", "K")["lp"], 75)
        self.assertEqual(sl, [3.0])

    def test_429_exhausted_returns_none(self):
        sl = []
        ns = build({"accounts/by-riot-id": [Resp(429, headers={"Retry-After": "1"})]}, sl)
        self.assertIsNone(ns["fetch_solo_rank_by_riotid"]("a#KR1", "K"))
        self.assertEqual(len(sl), 2, "429 재시도는 최대 2회")
        self.assertGreaterEqual(sl[0], 2.0, "Retry-After 1초여도 최소 2초는 기다린다(연타 방지)")

    def test_404_not_retried(self):
        ns = build({"accounts/by-riot-id": [Resp(404)]})
        self.assertIsNone(ns["fetch_solo_rank_by_riotid"]("없는닉#KR1", "K"))
        self.assertEqual(len(ns["_calls"]), 1)

    def test_timeout_retried_once(self):
        sl = []
        ns = build({"accounts/by-riot-id": [TimeoutError("t"), Resp(200, {"puuid": "P"})],
                    "entries/by-puuid": self.SOLO}, sl)
        self.assertEqual(ns["fetch_solo_rank_by_riotid"]("a#KR1", "K")["lp"], 75)
        self.assertEqual(sl, [1.0])

    def test_timeout_twice_gives_up(self):
        sl = []
        ns = build({"accounts/by-riot-id": [TimeoutError("t"), TimeoutError("t"),
                                            Resp(200, {"puuid": "P"})]}, sl)
        self.assertIsNone(ns["fetch_solo_rank_by_riotid"]("a#KR1", "K"))
        self.assertEqual(len(sl), 1, "타임아웃은 1회만 재시도")

    def test_5xx_retried_once(self):
        sl = []
        ns = build({"accounts/by-riot-id": [Resp(503), Resp(200, {"puuid": "P"})],
                    "entries/by-puuid": self.SOLO}, sl)
        self.assertEqual(ns["fetch_solo_rank_by_riotid"]("a#KR1", "K")["lp"], 75)
        self.assertEqual(sl, [1.5])

    def test_genuine_unranked_contract_kept(self):
        """정상 200 응답에 솔랭이 없을 때만 UNRANKED — 조회 실패(None)와 구분돼야 한다."""
        ns = build({"accounts/by-riot-id": [Resp(200, {"puuid": "P"})],
                    "summoners/by-puuid": [Resp(200, {"profileIconId": 1, "summonerLevel": 9})],
                    "entries/by-puuid": [Resp(200, [])]})
        r = ns["fetch_solo_rank_by_riotid"]("a#KR1", "K")
        self.assertEqual((r["tier"], r["score"], r["icon"]), ("UNRANKED", None, 1))


# ---------------------------------------------------------------- ② 이전 행 보존

PREV = [HDR,
        ["천쇄참월", "DIAMOND II", "75", "120", "98", "2314.5", "2026-11-27 11:07", "4568", "312"],
        ["가나다", "GOLD IV", "10", "40", "39", "1200.1", "2026-11-27 11:07", "11", "90"]]


def solo_sheet(rows=None, cols=7):
    return WS([list(r) for r in (rows if rows is not None else PREV)], cols=cols)


def classic_sheet(names):
    return WS([["소환사명", "날짜"]] + [[n, "2026-11-26 22:00"] for n in names], cols=2)


def make(ns, gstat_names, sol_rows=None, sol_cols=7, aliases=None):
    """update_solo_ranks 를 돌릴 수 있는 전역 스텁을 붙인다."""
    ss = SS({"SOLO_RANK": solo_sheet(sol_rows, sol_cols),
             "CLASSIC_NORMAL": classic_sheet([f"{n}#KR1" for n in gstat_names])})
    gstats = {f"pk{i}": {"name": n} for i, n in enumerate(gstat_names)}
    ns.update({
        "global_spreadsheet": ss,
        "global_alt_map": {},
        "gui_lock": __import__("threading").Lock(),
        "gui_data": {"hof_classic": {"global_stats": {"전체 (ALL)": gstats}, "aliases": dict(aliases or {})}},
        "load_riot_key": lambda: "KEY",
        "tier_of": lambda nm: "GOLD" if nm else None,
        "get_sheet_data_cached": lambda ws, force=False, prefer_service=False: ws.get_all_values(),
        "invalidate_sheet_cache": lambda t: None,
    })
    return ss.sheets["SOLO_RANK"], ss


DIAMOND = {"tier": "DIAMOND", "rank": "II", "lp": 80, "wins": 121, "losses": 98, "score": 2080, "icon": 4568, "level": 313}


class PreserveTest(unittest.TestCase):
    def test_failed_lookup_keeps_prev_row(self):
        ns = build()
        ws, _ = make(ns, ["천쇄참월", "가나다"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: None if "천쇄" in rid else DIAMOND
        ns["update_solo_ranks"]()
        rows = {r[0]: r for r in ws.updated[1:]}
        self.assertEqual(rows["천쇄참월"], PREV[1], "조회 실패 인원은 이전 행(티어·LP·승패·점수·아이콘·레벨)을 그대로 보존")
        self.assertEqual(rows["가나다"][1], "DIAMOND II", "정상 조회 인원은 새 값으로 갱신")
        self.assertEqual(len(ws.updated), 3)

    def test_prev_row_padded_to_nine_columns(self):
        ns = build()
        old = [HDR[:7], ["천쇄참월", "DIAMOND II", "75", "120", "98", "2314.5", "2026-11-27 11:07"]]
        ws, _ = make(ns, ["천쇄참월"], sol_rows=old, sol_cols=7)
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: None
        ns["update_solo_ranks"]()
        self.assertEqual(ws.updated[1], old[1] + ["", ""], "옛 7열 행도 9열로 맞춰 보존")

    def test_genuine_unranked_replaces_prev_row(self):
        ns = build()
        ws, _ = make(ns, ["천쇄참월"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: {"tier": "UNRANKED", "score": None, "icon": 7, "level": 300}
        ns["update_solo_ranks"]()
        # 점수 있는 행이 하나도 없으면 기존 가드(수집 0건)로 덮어쓰기를 취소한다 — 그건 기존 동작 유지
        self.assertFalse(ws.cleared)

    def test_unranked_and_ranked_together(self):
        ns = build()
        ws, _ = make(ns, ["천쇄참월", "가나다"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: ({"tier": "UNRANKED", "score": None, "icon": 7, "level": 300}
                                                           if "천쇄" in rid else DIAMOND)
        ns["update_solo_ranks"]()
        rows = {r[0]: r for r in ws.updated[1:]}
        self.assertEqual(rows["천쇄참월"][1], "UNRANKED", "실제 UNRANKED 응답은 이전 티어를 살리지 않는다")
        self.assertEqual(rows["천쇄참월"][5], "")
        self.assertEqual(rows["가나다"][1], "DIAMOND II")

    def test_unranked_without_icon_still_row(self):
        ns = build()
        ws, _ = make(ns, ["천쇄참월", "가나다"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: ({"tier": "UNRANKED", "score": None}
                                                           if "천쇄" in rid else DIAMOND)
        ns["update_solo_ranks"]()
        self.assertIn("천쇄참월", [r[0] for r in ws.updated[1:]], "언랭이면 아이콘을 못 받아도 행은 남는다")

    def test_no_prev_row_is_not_invented(self):
        ns = build()
        ws, _ = make(ns, ["새사람", "가나다"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: None if "새사람" in rid else DIAMOND
        ns["update_solo_ranks"]()
        self.assertNotIn("새사람", [r[0] for r in ws.updated[1:]], "이전 행이 없으면 지어내지 않는다")
        self.assertIn("가나다", [r[0] for r in ws.updated[1:]])

    def test_all_failed_keeps_whole_sheet(self):
        ns = build()
        ws, _ = make(ns, ["천쇄참월", "가나다"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: None
        ns["update_solo_ranks"]()
        self.assertEqual(sorted(r[0] for r in ws.updated[1:]), sorted(["천쇄참월", "가나다"]))
        for r in ws.updated[1:]:
            self.assertEqual(len(r), 9)

    def test_prev_read_from_sheet_before_clear(self):
        """ws.clear() 뒤에 읽으면 전부 사라진다 — 루프 전에 받아 둔 스냅샷으로 살려야 한다."""
        ns = build()
        ws, _ = make(ns, ["천쇄참월"])
        ns["fetch_solo_rank_by_riotid"] = lambda rid, key: None
        ns["update_solo_ranks"]()
        self.assertTrue(ws.cleared and ws.updated.count(PREV[1]) == 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
