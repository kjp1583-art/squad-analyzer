# -*- coding: utf-8 -*-
"""LINK 사슬 솔랭 시험 — 합성 시트(가짜 닉네임·PUUID)로 실제 웹을 재생해 「사슬 인물의 솔랭이 언랭이 아니다」를 판정하고,
같은 시트에서 툴링(sibguiwol.py)·분석기(_load_solo_ranks)가 웹과 같은 값을 내는지도 대조한다.

  python3 tests/web_replay/chain_test.py                  (WEB_SRC=<다른 index.html> 로 옛 웹에도 돌려 볼 수 있다)

[2026-10-09 사장님 제보 "카무사리 웹에서 언랭으로 뜨는 이유"] 3단 사슬(계정 이전 + 닉변)·2단(행이 부계에만)·본계에 행·피크만·사슬+피크만 을 한 번에 본다.
"""
import asyncio
import datetime as dt
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "desktop"))
sys.path.insert(0, os.path.join(ROOT, "tooling"))
import replay  # noqa: E402
import synth   # noqa: E402
import sibguiwol  # noqa: E402
import parity  # noqa: E402

WEB_SRC = os.environ.get("WEB_SRC") or os.path.join(ROOT, "index.html")
# 합성 시트에 없는 탭 — 하네스가 빈 표로 답한다(웹은 이 탭들이 비어도 뜬다). 이 밖의 탭을 웹이 더 읽으면 시험이 알려 준다(합성 시트에 넣을 것).
EXPECTED_MISSING = {"CAREER", "AI_EVAL", "TIER_HISTORY", "GPTI_STATS", "MITO", "MBTI", "GHOST", "TITLES", "MYEOL", "PERKS", "NOBAN", "GRUDGE",
                    "MITO_GAMES", "MITO_CODES", "LCK_PRED", "BRJANG", "UNIQ_MARKET", "CLAN_POSITIONS", "PREDICTIONS", "SCRIM_LIVE", "COMMENTS"}
C = synth.CAST


def tn(s):
    return sibguiwol.tnorm(s)


def run_web(xlsx):
    return asyncio.run(replay.replay(WEB_SRC, xlsx=xlsx, now=synth.NOW, cats=("rift",), shots=False, quiet=True))


def solo_snapshot(d):
    return {k: (round(v["score"], 4), v["wins"], v["losses"]) for k, v in d.items()}


class ChainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="chain_")
        cls.xlsx = synth.make_xlsx(os.path.join(cls.tmp, "synth.xlsx"))
        cls.xlsx2 = synth.make_xlsx(os.path.join(cls.tmp, "synth_shuffled.xlsx"), shuffle_links=True)   # 같은 데이터, LINK 행 순서만 다르다
        cls.web = run_web(cls.xlsx)
        cls.web2 = run_web(cls.xlsx2)
        cls.players = {tn(p["name"]): p for p in cls.web["rift"]["players"]}
        cls.tabs = synth.build_tabs()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------- 하네스 자체 ----------
    def test_harness_loaded_everything(self):
        log = self.web["meta"]["log"]
        self.assertEqual(log["pageerror"], [], "웹이 예외를 던졌다")
        self.assertEqual(log["unknown"], [], "하네스가 알아보지 못한 시트 요청이 있다")
        missing = set(log["missing"]) - {"MASTER_TIER (--master 로 주지 않아 빈 표로 답함)"}
        self.assertLessEqual(missing, EXPECTED_MISSING, "합성 시트에 없는 탭을 웹이 더 읽는다: %s" % sorted(missing - EXPECTED_MISSING))
        self.assertEqual(self.web["rift"]["meta"]["players"], synth.PLAIN_N + len(C), "평가가 나온 인원 = 일반 24 + 구조별 5")
        for tab in ("CLASSIC_NORMAL", "CLAN_TIERS", "SOLO_RANK", "PEAK_SEASONS", "LINK_ACCOUNT", "DEPARTED"):
            self.assertIn(tab, log["served"], tab)

    # ---------- 사슬 인물 ----------
    def test_chain3_is_not_unranked(self):
        c = C["chain3"]; p = self.players[tn(c["now"])]
        self.assertNotEqual(p["soloCell"], "언랭", "사슬 인물의 솔랭이 언랭으로 뜬다")
        self.assertEqual(p["soloCell"], "마스터 600LP")                      # 행은 옛 닉(옛#Old)에만 있다
        self.assertEqual(p["soloCur"], 3400)                                 # score_of(MASTER I, 600)
        self.assertEqual(p["solo"], 3250)                                    # (3400 + 옛 닉 피크 3100) / 2
        self.assertEqual(p["soloTxt"], "마스터 600LP")

    def test_pair_with_row_only_on_sub(self):
        c = C["pair"]; p = self.players[tn(c["main"])]
        self.assertEqual(p["soloCell"], "다이아 2 50LP")
        self.assertEqual(p["soloCur"], 2650)
        self.assertEqual(p["solo"], 2775)                                    # (2650 + 본계 피크 2900) / 2 — 부계 행은 자기 피크가 없어 그룹 최고 피크

    def test_main_row_is_unchanged(self):
        c = C["mainrow"]; p = self.players[tn(c["main"])]
        self.assertEqual(p["soloCell"], "에메랄드 1 30LP")
        self.assertEqual(p["solo"], 2515)                                    # (2330 + 2700) / 2 — 본계 자기 행·자기 피크 그대로

    # ---------- 현시즌이 없는 사람은 그대로 언랭 ----------
    def test_peak_only_stays_unranked(self):
        p = self.players[tn(C["peakonly"]["name"])]
        self.assertEqual(p["soloCell"], "언랭")
        self.assertIsNone(p["soloCur"]); self.assertEqual(p["solo"], 2800)

    def test_chain_without_current_season_stays_unranked(self):
        c = C["chainpk"]; p = self.players[tn(c["now"])]
        self.assertEqual(p["soloCell"], "언랭")
        self.assertIsNone(p["soloCur"])
        self.assertEqual(p["solo"], 3000)                                    # 그룹 최고 피크(옛 계정) — 분석기 v82.50 과 같은 공유 규칙

    # ---------- 사슬이 아닌 사람은 불변 ----------
    def test_plain_players_follow_the_plain_formula(self):
        solo_rows = {tn(r[0]): r for r in self.tabs["SOLO_RANK"][1:]}
        peak_rows = {tn(r[0]): r[4] for r in self.tabs["PEAK_SEASONS"][1:]}
        n = 0
        for nm in synth.plain_names():
            p = self.players[tn(nm)]
            r = solo_rows.get(tn(nm)); pk = peak_rows.get(tn(nm))
            if r:
                self.assertAlmostEqual(p["solo"], round((r[5] + pk) / 2.0), delta=1, msg=nm)
                self.assertEqual(p["soloCur"], r[5], nm); self.assertNotEqual(p["soloCell"], "언랭", nm)
            else:
                self.assertEqual(p["soloCell"], "언랭", nm); self.assertEqual(p["solo"], round(pk), nm)
            n += 1
        self.assertEqual(n, synth.PLAIN_N)

    # ---------- 웹 = 툴링 = 분석기 ----------
    def _web_solo(self, web=None):
        return {k: (round(v["score"], 4), v["wins"], v["losses"]) for k, v in (web or self.web)["rift"]["solo"].items()}

    def test_web_solo_map_equals_tooling(self):
        solo = sibguiwol.load(self.xlsx)[3]
        self.assertEqual(solo_snapshot(solo), self._web_solo())

    def test_web_solo_map_equals_analyzer(self):
        self.assertEqual(solo_snapshot(parity.analyzer_solo_map(self.xlsx)), self._web_solo())

    def test_web_roster_equals_tooling(self):
        roster = sibguiwol.compute(self.xlsx, today=dt.date(2026, 10, 9))
        self.assertEqual(parity.diff_roster(roster, self.web["rift"]["roster"]), [])
        self.assertTrue(roster, "명단이 비었다")

    # ---------- LINK 행 순서 ----------
    def test_link_row_order_does_not_matter(self):
        self.assertEqual(self._web_solo(self.web2), self._web_solo())
        self.assertEqual(solo_snapshot(sibguiwol.load(self.xlsx2)[3]), solo_snapshot(sibguiwol.load(self.xlsx)[3]))
        p2 = {tn(p["name"]): p for p in self.web2["rift"]["players"]}
        self.assertEqual(p2[tn(C["chain3"]["now"])]["soloCell"], "마스터 600LP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
