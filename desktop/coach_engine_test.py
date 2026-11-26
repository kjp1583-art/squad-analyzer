"""고스트밴픽왕 성능향상 2단계 단위 테스트 — 조합 결핍(챔프 태그) · 등장확률 최근성 가중 · 프롬프트 경량화 · 백테스트.

squad_analyzer.py 는 Windows 전용 import 가 많아 필요한 함수만 AST 로 떼어 쓴다(기존 테스트와 같은 방식).
   python3 desktop/coach_engine_test.py
"""
import ast
import importlib.util
import math
import os
import re
import statistics
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "squad_analyzer.py")
TEXT = open(SRC, encoding="utf-8").read()
TREE = ast.parse(TEXT)

FUNCS = ("tnorm", "_sheet_date", "_recency_w", "_recency_score", "_pool_p_show",
         "_champ_tags", "_comp_report", "_comp_lines")
CONSTS = ("_ROLES5", "_REC_W", "_REC_OLD_W", "_BAN_LIMIT", "_CHAMP_TAGS", "_TAG_ORDER", "_TAG_KO")


def load_env():
    body = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in FUNCS]
    assert not (set(FUNCS) - {n.name for n in body}), set(FUNCS) - {n.name for n in body}
    consts = {}
    for n in TREE.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id in CONSTS:
                consts[n.targets[0].id] = ast.literal_eval(n.value)
    ns = dict(consts)
    ns.update({"time": time, "re": re, "math": math})
    exec(compile(ast.Module(body=body, type_ignores=[]), SRC, "exec"), ns)
    return ns


def prompts():
    out = {}
    for n in TREE.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id in ("_DRAFT_RULES", "_DRAFT_BAN_RULES"):
                out[n.targets[0].id] = ast.literal_eval(n.value)
    return out


class T_Tags(unittest.TestCase):
    def test_known_champ_tags(self):
        T = load_env()["_champ_tags"]
        self.assertIn("ap", T("아리"))
        self.assertIn("tank", T("아무무"))
        self.assertIn("hardcc", T("레오나"))
        self.assertIn("poke", T("제라스"))
        self.assertIn("ad", T("진"))

    def test_space_insensitive(self):
        T = load_env()["_champ_tags"]
        self.assertEqual(T("자르반 4세"), T("자르반4세"))
        self.assertIn("tank", T("자르반 4세"))

    def test_unknown_is_neutral(self):
        T = load_env()["_champ_tags"]
        self.assertEqual(T("없는챔피언"), set())
        self.assertEqual(T(""), set())
        self.assertEqual(T(None), set())

    def test_table_covers_clan_meta(self):
        tags = load_env()["_CHAMP_TAGS"]
        for c in ("브라이어", "녹턴", "세주아니", "아리", "진", "쓰레쉬", "아트록스", "사일러스",
                  "오리아나", "럭스", "이즈리얼", "레오나", "뽀삐", "그라가스", "제이스", "카직스"):
            self.assertIn(c, tags, f"{c} 태그 누락")


class T_Comp(unittest.TestCase):
    def test_missing_ap_and_frontline(self):
        R = load_env()["_comp_report"]
        r = R(["가렌", "아트록스", "제드"], ["아리", "제라스", "럭스"])
        self.assertIn("AP 딜 없음", r["gaps"])
        self.assertIn("하드CC 없음", r["gaps"])
        self.assertNotIn("앞라인(탱커) 없음", r["gaps"])          # 가렌·아트록스는 앞라인

    def test_frontline_missing(self):
        R = load_env()["_comp_report"]
        r = R(["제드", "아리", "럭스"], [])
        self.assertIn("앞라인(탱커) 없음", r["gaps"])

    def test_enemy_threats(self):
        R = load_env()["_comp_report"]
        r = R(["가렌", "아트록스"], ["제라스", "럭스", "애니비아"])   # 포킹 3
        self.assertTrue(any("포킹" in t for t in r["threats"]))

    def test_unknown_champs_are_reported_not_counted(self):
        R = load_env()["_comp_report"]
        r = R(["가렌", "없는챔피언"], ["아리"])
        self.assertIn("없는챔피언", r["unknown"])
        self.assertEqual(r["ally"]["ad"], 1)                     # 미등록 챔프는 집계에 안 들어간다

    def test_comp_lines_shape(self):
        L = load_env()["_comp_lines"]
        lines = L(["가렌", "아트록스", "제드"], ["아리", "제라스"])
        self.assertTrue(any(x.startswith("우리 확정 조합:") for x in lines))
        self.assertTrue(any(x.startswith("★결핍:") for x in lines))
        self.assertTrue(any(x.startswith("상대 확정 조합:") for x in lines))

    def test_no_picks_no_gaps(self):
        L = load_env()["_comp_lines"]
        self.assertEqual(L([], []), [])


class T_RecencyShare(unittest.TestCase):
    def test_recent_games_outweigh_old_games(self):
        """등장확률의 점유율은 최근성 가중 — '어제 5판'이 '1년 전 30판'보다 무겁다."""
        E = load_env()
        now = time.time()
        recent = time.strftime("%Y-%m-%d", time.localtime(now - 5 * 86400))
        old = time.strftime("%Y-%m-%d", time.localtime(now - 365 * 86400))
        w_recent = E["_recency_score"]([(recent, 5)])[0]
        w_old = E["_recency_score"]([(old, 30)])[0]
        rows = [
            {"champ": "브라이어", "g": 5, "w": 3, "wscore": w_recent, "n90": 5, "n14": 5, "last": "",
             "posg": {"정글": [5, 3]}, "posw": {"정글": w_recent}},
            {"champ": "카직스", "g": 30, "w": 15, "wscore": w_old, "n90": 0, "n14": 0, "last": "",
             "posg": {"정글": [30, 15]}, "posw": {"정글": w_old}},
        ]
        out = E["_pool_p_show"](rows, probs={"정글": 1.0})
        self.assertEqual(out[0]["champ"], "브라이어")
        self.assertGreater(out[0]["p_show"], out[1]["p_show"])
        self.assertAlmostEqual(sum(x["p_show"] for x in out), 1.0, places=2)

    def test_known_position_uses_only_that_lane(self):
        E = load_env()
        rows = [{"champ": "아리", "g": 9, "w": 5, "wscore": 9.0, "n90": 9, "n14": 9, "last": "",
                 "posg": {"미드": [9, 5]}, "posw": {"미드": 9.0}},
                {"champ": "쓰레쉬", "g": 20, "w": 10, "wscore": 20.0, "n90": 20, "n14": 0, "last": "",
                 "posg": {"서폿": [20, 10]}, "posw": {"서폿": 20.0}}]
        out = E["_pool_p_show"](rows, ep="서폿")
        self.assertEqual([x["champ"] for x in out], ["쓰레쉬"])


class T_Prompts(unittest.TestCase):
    def test_prompt_shrank(self):
        p = prompts()
        # 경량화 전: _DRAFT_RULES 4,612자 · _DRAFT_BAN_RULES 4,102자
        self.assertLess(len(p["_DRAFT_RULES"]), 2100, "픽 프롬프트가 아직 길다")
        self.assertLess(len(p["_DRAFT_BAN_RULES"]), 1300, "밴 프롬프트가 아직 길다")

    def test_essential_rules_survived(self):
        p = prompts()
        for k in ("_DRAFT_RULES", "_DRAFT_BAN_RULES"):
            self.assertIn("=====근거=====", p[k])          # 근거 구분줄(파서가 의존)
        for kw in ("이미 밴·픽된 챔프", "포지션을 지어내지 마라", "솔랭", "내 라인", "클랜 내전 데이터"):
            self.assertIn(kw, p["_DRAFT_RULES"])
        for kw in ("사전 스코어링", "아군(나·팀원) 챔프 밴 금지", "견제압력", "표본 5판"):
            self.assertIn(kw, p["_DRAFT_BAN_RULES"])

    def test_old_verbosity_gone(self):
        p = prompts()
        # 사전 스코어링·조합 결핍이 대신 계산하는 장황한 설명은 프롬프트에서 사라졌다
        self.assertNotIn("점유 P%", p["_DRAFT_BAN_RULES"])
        self.assertNotIn("조합 아키타입: ①한타", p["_DRAFT_RULES"])


class T_Backtest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("coach_backtest", os.path.join(HERE, "coach_backtest.py"))
        cls.bt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.bt)
        cls.eng = cls.bt.build_engine()

    def test_engine_loads_from_source(self):
        for f in ("_ban_candidates", "_pos_prob", "_pool_p_show", "_recency_score"):
            self.assertIn(f, self.eng)

    def test_new_beats_old_on_synthetic(self):
        rows = self.bt.run_synthetic(self.eng, trials=60, seed=5)
        old = statistics.fmean(r["old_hit5"] for r in rows)
        new = statistics.fmean(r["new_hit5"] for r in rows)
        self.assertGreaterEqual(new, old - 0.02, f"적중@5 퇴행: 기존 {old:.2f} → 개선 {new:.2f}")
        waste_old = statistics.fmean(r["old_waste5"] for r in rows)
        waste_new = statistics.fmean(r["new_waste5"] for r in rows)
        self.assertLess(waste_new, waste_old, "오추천률이 줄지 않았다")
        self.assertGreater(statistics.fmean(r["lift"] for r in rows), 1.0, "등장확률이 무변별")

    def test_report_writes(self):
        rows = self.bt.run_synthetic(self.eng, trials=10, seed=1, phases=(1, 2))
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(0.0 <= r["new_hit1"] <= 1.0 for r in rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
