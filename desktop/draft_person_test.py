"""고스트밴픽왕 성능향상 1단계 단위 테스트 — 사람(LINK) 단위·최근성 가중·포지션 확률·사전 스코어링.

squad_analyzer.py 는 Windows 전용 import 가 많아, 필요한 함수만 AST 로 떼어 가짜 시트로 실행한다
(기존 clan_line_ep_test.py · solo_link_chain_test.py 와 같은 방식). 외부 접속·실제 시트 없음.
   python3 desktop/draft_person_test.py
"""
import ast
import math
import os
import re
import time
import unittest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py")
TEXT = open(SRC, encoding="utf-8").read()
TREE = ast.parse(TEXT)

FUNCS = ("tnorm", "_sheet_date", "_recency_w", "_recency_score", "_person_alias_map",
         "_idx_pu", "_idx_ent", "_clan_members", "_pos_prob", "_pos_label",
         "_ban_candidates", "_ban_board_lines",
         "_dep_link_groups", "_clan_index", "_clan_line", "_pool_rows", "_pool_by_puuid", "_my_champ_pool",
         "_rows_by_puuid",   # 🪶 v83.75 사람별 행 묶음(_pool_rows 가 쓴다 — 이 함수가 빠지면 NameError)
         "_enemy_rows", "_enemy_ban_pool", "_pool_p_show")
CONSTS = ("_ROLES5", "_REC_W", "_REC_OLD_W", "_BAN_LIMIT", "_POOLROWS_CACHE", "_BU_PU_CACHE")


def load_env():
    body = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in FUNCS]
    missing = set(FUNCS) - {n.name for n in body}
    assert not missing, f"함수를 못 찾음: {missing}"
    consts = {}
    for n in TREE.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id in CONSTS:
                consts[n.targets[0].id] = ast.literal_eval(n.value)
    ns = dict(consts)
    ns.update({
        "time": time, "re": re, "math": math,
        "_CLAN_IDX": {"ts": 0.0, "by_pu": {}, "h2h": {}, "syn": {}, "nm2pu": {}},
        "_DRAFT_POOL_CACHE": {},
        "_POOLROWS_CACHE": {"ts": {}, "data": {}},
        "global_spreadsheet": None,
        "global_alt_map": {},
        "get_sheet_data_cached": lambda tab: tab.rows,
        "tier_of": lambda name: ("1中" if "본계" in str(name) else ""),   # 본계만 내부티어가 있다
        "_fix_pack_minutes": lambda o: o,
    })
    exec(compile(ast.Module(body=body, type_ignores=[]), SRC, "exec"), ns)
    return ns


class _WS:
    def __init__(self, title, rows):
        self.title = title
        self.rows = rows


class _SS:
    def __init__(self, tabs):
        self.tabs = tabs

    def worksheet(self, name):
        if name not in self.tabs:
            raise KeyError(name)
        return self.tabs[name]


HDR = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "KDA", "매치평가", "패치버전", "점수", "지표"]


def days_ago(n):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - n * 86400))


def row(game, pu, name, champ, pos, team, res, date, ban=""):
    return [game, date, name, pu, team, pos, champ, ban, res, "5/2/7", "MVP", "15.22", "6.5", ""]


def build_sheet():
    """본계(main1) ↔ 부계(alt1) 가 LINK_ACCOUNT 로 이어진 한 사람 + 상대 4명. 날짜는 '며칠 전'으로 만든다."""
    rows = [HDR]
    # 본계: 브라이어 정글 12판(최근 5일) · 녹턴 정글 8판(최근 60일) · 옛 카직스 12판(400일 전)
    for i in range(12):
        rows.append(row(f"g-main-a{i}", "main1", "본계#KR1", "브라이어", "정글", "블루팀",
                        "승리" if i % 3 else "패배", days_ago(5), "브라이어"))
    for i in range(8):
        rows.append(row(f"g-main-b{i}", "main1", "본계#KR1", "녹턴", "정글", "블루팀",
                        "승리" if i % 2 else "패배", days_ago(60)))
    for i in range(12):
        rows.append(row(f"g-main-c{i}", "main1", "본계#KR1", "카직스", "정글", "블루팀",
                        "승리" if i % 4 else "패배", days_ago(400)))
    # 부계: 세주아니 정글 5판(최근 3일) — 같은 사람이므로 챔프폭에 합산돼야 한다
    for i in range(5):
        rows.append(row(f"g-alt-a{i}", "alt1", "부계#KR1", "세주아니", "정글", "레드팀",
                        "승리" if i % 2 else "패배", days_ago(3)))
    # 상대: 둘째(미드 아리 20판 최근), 셋째(원딜 12판), 넷째(서폿 6판), 다섯째(탑 6판)
    for i in range(20):
        rows.append(row(f"g-p2-{i}", "p2", "둘째#KR1", "아리", "미드", "레드팀",
                        "승리" if i % 2 else "패배", days_ago(10)))
    for i in range(12):
        rows.append(row(f"g-p3-{i}", "p3", "셋째#KR1", "진", "원딜", "레드팀",
                        "승리" if i % 3 else "패배", days_ago(20)))
    for i in range(6):
        rows.append(row(f"g-p4-{i}", "p4", "넷째#KR1", "쓰레쉬", "서폿", "레드팀",
                        "승리" if i % 2 else "패배", days_ago(30)))
    for i in range(6):
        rows.append(row(f"g-p5-{i}", "p5", "다섯째#KR1", "아트록스", "탑", "레드팀",
                        "승리" if i % 2 else "패배", days_ago(40)))
    # 맞대결(h2h): 본계와 둘째가 같은 판에 서로 다른 팀 → 사람 단위 키로 잡혀야 한다
    rows.append(row("g-h2h-1", "main1", "본계#KR1", "브라이어", "정글", "블루팀", "패배", days_ago(7)))
    rows.append(row("g-h2h-1", "p2", "둘째#KR1", "아리", "미드", "레드팀", "승리", days_ago(7)))
    return rows


LINK_ROWS = [["본계정", "부계정"], ["본계#KR1", "부계정#KR1"], ["본계#KR1", "부계#KR1"]]


def make_env():
    ns = load_env()
    ns["global_spreadsheet"] = _SS({
        "CLASSIC_NORMAL": _WS("CLASSIC_NORMAL", build_sheet()),
        "LINK_ACCOUNT": _WS("LINK_ACCOUNT", LINK_ROWS),
    })
    ns["global_alt_map"] = {"부계": "본계#KR1"}
    return ns


class T_Person(unittest.TestCase):
    """② LINK_ACCOUNT 연결 요소 = 한 사람."""

    def test_alias_map_merges_chain(self):
        M = load_env()["_person_alias_map"]
        pu2, grp, names = M({"a": "본계#KR1", "b": "부계#KR1", "c": "삼계#KR1", "d": "남#KR1"},
                            {"부계": {"부계", "본계", "삼계"}, "삼계": {"삼계", "본계"}})
        self.assertEqual(pu2["a"], pu2["b"])          # 사슬 A←B, B←C 전체가 한 그룹
        self.assertEqual(pu2["a"], pu2["c"])
        self.assertNotEqual(pu2["a"], pu2["d"])       # 남은 따로
        self.assertEqual(grp[pu2["a"]], {"a", "b", "c"})
        self.assertIn("삼계", names[pu2["a"]])

    def test_alias_map_same_nick_only_when_full_nick_equal(self):
        M = load_env()["_person_alias_map"]
        # 태그만 다른 동명이인은 합치지 않는다(남의 챔프폭이 섞이면 밴 후보가 통째로 틀어진다)
        pu2, _g, _n = M({"x": "동명#1111", "y": "동명#2222"}, {})
        self.assertNotEqual(pu2["x"], pu2["y"])
        # 전체 닉이 같으면(계정 이전) 잇는다
        pu2b, _g2, _n2 = M({"x": "같은#1111", "y": "같은#1111"}, {})
        self.assertEqual(pu2b["x"], pu2b["y"])

    def test_clan_index_sums_group(self):
        ns = make_env()
        idx = ns["_clan_index"](True)
        e = ns["_idx_ent"](idx, "alt1")
        self.assertTrue(e, "부계 puuid 가 사람 항목으로 해석돼야 한다")
        self.assertEqual(e["g"], 12 + 8 + 12 + 5 + 1)          # 본계 32판 + 부계 5판 + 맞대결 판 1 = 38
        self.assertIn("브라이어", e["champs"])
        self.assertIn("세주아니", e["champs"])                 # 부계 챔프가 같은 사람 챔프폭에 합산
        self.assertEqual(ns["_idx_pu"](idx, "alt1"), ns["_idx_pu"](idx, "main1"))
        self.assertEqual(str(e["name"]), "본계#KR1")           # 대표닉 = 내부티어가 있는 본계
        self.assertNotEqual(ns["_idx_pu"](idx, "alt1"), ns["_idx_pu"](idx, "p2"))

    def test_clan_line_and_pairs_use_group(self):
        ns = make_env()
        idx = ns["_clan_index"](True)
        line = ns["_clan_line"]("alt1", idx)
        self.assertIn("본계", line)
        self.assertIn("38판", line)
        self.assertIn("세주아니", line)                        # 부계 픽도 이 사람 것으로 보인다
        # h2h 도 사람 단위 키로 저장 → 부계 puuid 로 물어도 같은 사람 전적이 나온다
        h = ns["_clan_index"]()["h2h"]
        self.assertTrue(any(ns["_idx_pu"](idx, "alt1") in k for k in h), "h2h 키가 사람키여야 한다")
        self.assertTrue(all(ns["_idx_pu"](idx, "p2") in k for k in h))


class T_Recency(unittest.TestCase):
    """① 최근성 가중."""

    def test_recency_weight_order(self):
        w = load_env()["_recency_w"]
        self.assertGreater(w(3), w(20))
        self.assertGreater(w(20), w(60))
        self.assertGreater(w(60), w(300))
        self.assertGreater(w(300), 0)

    def test_sheet_date_variants(self):
        d = load_env()["_sheet_date"]
        self.assertIsNotNone(d("2026-11-01 21:33"))
        self.assertIsNotNone(d("2026. 11. 1."))
        self.assertIsNotNone(d("2026/11/01"))
        self.assertIsNone(d("결과 대기"))

    def test_pool_prefers_recent_hot_pick(self):
        ns = make_env()
        pool = ns["_pool_by_puuid"]("main1", limit=5)
        names = [p[0] for p in pool]
        self.assertEqual(names[0], "브라이어")                 # 최근 12판
        self.assertLess(names.index("브라이어"), names.index("녹턴"))
        self.assertLess(names.index("녹턴"), names.index("카직스"))   # 12판이라도 400일 전이면 아래
        self.assertEqual(pool[0][4] >= 12, True)              # 최근90일 판수도 함께 온다
        self.assertTrue(all(len(p) == 8 for p in pool))

    def test_my_pool_recency(self):
        ns = make_env()
        ns["_DRAFT_POOL_CACHE"] = {}
        pool = ns["_my_champ_pool"]("본계", limit=5)
        self.assertEqual(pool[0][0], "브라이어")
        self.assertEqual(pool[0][3] > pool[-1][3], True)      # 가중판수 내림차순
        self.assertIn("세주아니", [p[0] for p in pool])        # 부계 닉으로 남은 내 기록도 합산


class T_PosProb(unittest.TestCase):
    """③ 미확정 포지션 확률 추론."""

    def test_two_players_take_their_own_slot(self):
        P = load_env()["_pos_prob"]
        out = P(["정글", "서폿"], [("a", {"정글": 40, "서폿": 2}), ("b", {"정글": 3, "서폿": 30})])
        self.assertGreater(out["a"]["정글"], 0.7)
        self.assertGreater(out["b"]["서폿"], 0.7)
        self.assertAlmostEqual(sum(out["a"].values()), 1.0, places=2)

    def test_filled_slot_excluded_and_unknown_is_prior(self):
        P = load_env()["_pos_prob"]
        out = P(["탑"], [("x", {}), ("y", {})])
        self.assertEqual(set(out["x"].keys()), {"탑"})
        self.assertAlmostEqual(out["x"]["탑"] + out["y"]["탑"], 1.0, places=2)   # 한 자리는 한 명

    def test_empty_input(self):
        self.assertEqual(load_env()["_pos_prob"]([], [("x", {"미드": 3})]), {})
        self.assertEqual(load_env()["_pos_prob"](["미드"], []), {})


class T_BanScore(unittest.TestCase):
    """① 후보 사전 스코어링."""

    def _rows(self):
        return [
            {"champ": "아리", "name": "둘째", "p_show": 0.62, "g": 20, "w": 13},
            {"champ": "브라이어", "name": "본계", "p_show": 0.55, "g": 12, "w": 8},
            {"champ": "진", "name": "셋째", "p_show": 0.48, "g": 12, "w": 4},
            {"champ": "카직스", "name": "본계", "p_show": 0.05, "g": 12, "w": 9},
            {"champ": "쓰레쉬", "name": "넷째", "p_show": 0.40, "g": 6, "w": 3},
        ]

    def test_scores_are_exposure_times_threat(self):
        B = load_env()["_ban_candidates"]
        out = B(self._rows(), limit=10)
        self.assertAlmostEqual(out[0]["score"], out[0]["p_show"] * out[0]["threat"], places=2)
        self.assertEqual([c["score"] for c in out], sorted([c["score"] for c in out], reverse=True))
        # 등장 5%짜리 옛 픽이 등장 55%짜리 밥줄보다 위로 오면 안 된다
        names = [c["champ"] for c in out]
        self.assertGreater(names.index("브라이어"), names.index("카직스") - 10)
        self.assertLess(names.index("브라이어"), names.index("카직스"))

    def test_ally_and_dead_excluded(self):
        B = load_env()["_ban_candidates"]
        out = B(self._rows(), ally_champs=[("아리", "미드")], dead=["진"], limit=10)
        names = [c["champ"] for c in out]
        self.assertNotIn("아리", names)
        self.assertNotIn("진", names)

    def test_multi_player_coverage_boosts(self):
        B = load_env()["_ban_candidates"]
        rows = [{"champ": "아리", "name": "a", "p_show": 0.4, "g": 10, "w": 5},
                {"champ": "아리", "name": "b", "p_show": 0.4, "g": 10, "w": 5},
                {"champ": "진", "name": "c", "p_show": 0.4, "g": 10, "w": 5}]
        out = B(rows, limit=5)
        self.assertEqual(out[0]["champ"], "아리")
        self.assertAlmostEqual(out[0]["p_show"], 0.64, places=2)     # 1-(0.6*0.6)

    def test_board_lines_keep_numbers(self):
        ns = load_env()
        out = ns["_ban_candidates"](self._rows(), limit=3)
        lines = ns["_ban_board_lines"](out, quiz={"아리": 4}, bp={"브라이어": 18})
        self.assertTrue(lines[0].startswith("1. "))
        self.assertIn("등장", lines[0])
        self.assertTrue(any("견제 +18%p" in x for x in lines))


class T_EnemyPool(unittest.TestCase):
    """상대 챔프폭이 포지션 확률을 반영하는지."""

    def test_unknown_position_uses_probability(self):
        ns = make_env()
        ns["_clan_index"](True)
        nm, rows = ns["_enemy_rows"]("p2", probs={"미드": 0.9, "탑": 0.1})
        self.assertEqual(nm.split("#")[0], "둘째")
        self.assertEqual(rows[0]["champ"], "아리")
        self.assertAlmostEqual(rows[0]["p_show"], 0.9, places=2)
        hdr, lines = ns["_enemy_ban_pool"]("p2", "", None, probs={"미드": 0.9, "탑": 0.1})
        self.assertIn("예상 포지션", hdr)
        self.assertIn("미드 90%", hdr)
        self.assertIn("아리", lines[0])

    def test_known_position_filters_other_lane(self):
        ns = make_env()
        ns["_clan_index"](True)
        hdr, lines = ns["_enemy_ban_pool"]("p2", "서폿", ns["_clan_index"]())
        self.assertIn("이번 판 포지션: 서폿", hdr)
        self.assertTrue("전적 0판" in lines[0])                  # 아리(미드)를 서폿 저격으로 올리지 않는다


if __name__ == "__main__":
    unittest.main(verbosity=2)
