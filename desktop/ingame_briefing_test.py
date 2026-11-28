"""🎙 인게임 뉴럴 TTS 브리핑 시험 (2026-11-27).

squad_analyzer.py 는 Windows 전용 import(winreg 등)가 많아 통째로 import 할 수 없다.
그래서 브리핑 관련 함수만 AST 로 떼어 가짜 환경(라이브 데이터·설정·스레드)에서 돌린다.
TTS 실재생(edge-tts·MCI)은 이 시험에서 하지 않는다 — 여기서는 '무엇을 말할지'와
'언제 한 번만 하는지'를 본다.

확인 항목
  ① 예상 승률(우리 진영 기준) / 진영 미상
  ② 최근 3연승↑·3연패↓ (상대 연승 우선, 게임당 최대 2명)
  ③ 상대 라인 꼬임(시트 주포지션 ↔ 라이브 포지션, 표본 5판↑)
  ④ 플레이 방향성 — AI 코멘트가 있으면 그것, 없으면 조합 규칙 폴백
  ⑤ 길이 상한(10~15초) 안으로 줄이되 방향성 문장은 남긴다
  ⑥ gameId당 1회(_brief_claim·tick 'done') · 설정 OFF면 아무 일도 안 함
  ⑦ 인게임 120초를 넘긴 판은 읽지 않음 · 라이브 응답이 없으면 다음 폴링 재시도
  ⑧ 한국어 클라이언트(championName='아리'·'리 신'·'미스 포츈')에서도 진짜로 브리핑이 나온다
     — 예전엔 한글 이름이 전부 ''로 버려져 챔프 미탑재로 판단 → 브리핑이 아예 실행되지 않았다

    python desktop/ingame_briefing_test.py
"""
import ast
import hashlib
import os
import re
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "squad_analyzer.py")

with open(SRC, encoding="utf-8") as _f:
    SRC_TEXT = _f.read()
TREE = ast.parse(SRC_TEXT)

_DEFS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}

BRIEF_FUNCS = (
    "_brief_base_name", "_brief_sv", "_brief_pos_norm", "_brief_ira", "_brief_live_pos", "_brief_main_pos",
    "_brief_match_live", "_brief_direction_lines", "_brief_trim", "_build_ingame_briefing",
    "_brief_game_key", "_brief_claim", "_ingame_briefing_tick", "_ingame_briefing_worker",
    "_brief_champ_by_id", "_brief_pseudo_live",
)   # _brief_champ_kor·_speak_neural_tts 는 가짜로 바꿔 끼운다(load_one 으로 따로 뺀다)


def _tnorm(s):
    return "".join(str(s or "").split("#")[0].lower().split())


class FakeThreading:
    """스레드를 실제로 돌리지 않고 '띄웠는지'만 기록한다(폴링 루프가 기다리지 않는지 확인용)."""
    def __init__(self):
        self.started = []

    def Thread(self, target=None, args=(), kwargs=None, daemon=None):
        outer = self
        ns = {}

        class _T:
            def __init__(self):
                self.target = target
                self.args = tuple(args or ())
                self.daemon = daemon
                outer.started.append(self)

            def start(self):
                pass

        ns["T"] = _T
        return _T()

    def Lock(self):
        return threading.Lock()


def make_ns(comp_report=None, config=None, live_json=None, threading_mod=None,
            speak_recorder=None, my_side="blue", champ_kor=None):
    ns = {
        "re": re, "os": os, "time": time, "hashlib": hashlib,
        "tnorm": _tnorm,
        "threading": threading_mod or FakeThreading(),
        "_BRIEF_POS_KO": {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드",
                         "BOTTOM": "원딜", "UTILITY": "서폿"},
        "_BRIEF_SIDE_KO": {"blue": "블루 팀", "red": "레드 팀"},
        "_BRIEF_ENG2KOR": {},
        "_BRIEFED_GAMES": set(),
        "_BRIEF_GUARD": threading.Lock(),
        "_BRIEF_STATE": {"pending": False, "last_try": 0.0},
        "_BRIEF_TAG": [0],
        "INGAME_BRIEF_MAX_CHARS": 100,
        "INGAME_BRIEF_MAX_GAMETIME": 120,
        "INGAME_BRIEF_MIN_CHAMPS": 6,
        "APP_CONFIG": dict(config if config is not None else {"ingame_tts_briefing": True}),
        "gui_data": {"blue": [], "red": [], "blue_win_rate": 50, "red_win_rate": 50},
        "gui_lock": threading.Lock(),
        "MY_RIOT_NAME": [""],
        "_comp_report": comp_report or (lambda a, e: {}),
        "_brief_live_json": live_json or (lambda path: None),
        "_brief_my_side": lambda live: my_side,
        "_brief_ai_comment": lambda ctx: "",
        "_speak_neural_tts": speak_recorder or (lambda txt: True),
        "_clan_index": lambda force=False: {},
        "_brief_champ_kor": champ_kor or (lambda eng: str(eng or "")),
        "CHAMP_KOR_TO_ENG": {},
        "global_champ_map": {},
        "GLOBAL_NUMERIC_CHAMP_MAP": {},
        "print": lambda *a, **k: None,
    }
    return ns


def load_one(ns, name):
    node = _DEFS.get(name)
    assert node is not None, f"{name} 를 squad_analyzer.py 에서 찾지 못했습니다"
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), SRC, "exec"), ns)
    return ns


def load(ns):
    """ns 에 브리핑 함수들을 AST 노드 그대로 exec 해 넣는다(기본값·상수 참조는 ns 에서 해결)."""
    for name in BRIEF_FUNCS:
        node = _DEFS.get(name)
        assert node is not None, f"{name} 를 squad_analyzer.py 에서 찾지 못했습니다"
        mod = ast.Module(body=[node], type_ignores=[])
        exec(compile(ast.fix_missing_locations(mod), SRC, "exec"), ns)
    return ns


# 한국어 클라이언트(liveclientdata) championName — ddragon ko_KR 표기 그대로.
# CHAMP_KOR_TO_ENG 은 앱에서 정식 표기('리 신')와 공백 제거 키('리신')를 둘 다 넣고,
# global_champ_map 은 정식 표기를 kor 로 갖는다(아래는 그 구조를 그대로 옮긴 시험용 사본).
KOR_TO_ENG_FIXTURE = {
    "아리": "Ahri", "리 신": "LeeSin", "리신": "LeeSin",
    "미스 포츈": "MissFortune", "미스포츈": "MissFortune",
    "카이사": "Kaisa", "진": "Jhin", "가렌": "Garen",
    "누누와 윌럼프": "Nunu", "누누와윌럼프": "Nunu",
    "자르반 4세": "JarvanIV", "자르반4세": "JarvanIV",
}
NUMERIC_FIXTURE = {
    1: {"kor": "아리", "eng": "Ahri"}, 64: {"kor": "리 신", "eng": "LeeSin"},
    21: {"kor": "미스 포츈", "eng": "MissFortune"}, 145: {"kor": "카이사", "eng": "Kaisa"},
    222: {"kor": "진", "eng": "Jhin"}, 86: {"kor": "가렌", "eng": "Garen"},
    20: {"kor": "누누와 윌럼프", "eng": "Nunu"},
}


def real_champ_ns(**kw):
    """가짜 _brief_champ_kor 대신 squad_analyzer.py 의 진짜 함수를 넣은 환경."""
    ns = make_ns(**kw)
    ns["CHAMP_KOR_TO_ENG"] = dict(KOR_TO_ENG_FIXTURE)
    ns["global_champ_map"] = {k: dict(v) for k, v in NUMERIC_FIXTURE.items()}
    ns["_BRIEF_ENG2KOR"] = {}
    load_one(ns, "_brief_champ_kor")
    return ns


def P(name, puuid, pos="TOP"):
    return {"name": name, "puuid": puuid, "chosen_pos_icon": pos}


def S(streak=0, games=20, wr=0.5):
    return {"streak_val": streak, "games": games, "overall_wr": wr}


class BriefingTest(unittest.TestCase):
    # ── ① 예상 승률 ────────────────────────────────────────────────
    def test_win_rate_blue_side(self):
        ns = load(make_ns())
        out = ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 54})
        self.assertIn("우리 팀 예상 승률 54퍼센트, 팽팽한 판이에요.", out[0])

    def test_win_rate_red_side_flips(self):
        ns = load(make_ns())
        out = ns["_build_ingame_briefing"]({"my_side": "red", "blue_wr": 54})
        # 레드 입장에선 46% — '우리 팀' 기준으로 뒤집혀야 한다
        self.assertIn("46퍼센트", out[0])
        self.assertNotIn("54퍼센트", out[0])

    def test_win_rate_favoured_and_behind(self):
        ns = load(make_ns())
        self.assertIn("유리", ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 72})[0])
        self.assertIn("상대가 좀 앞서요", ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 30})[0])

    def test_win_rate_clamped(self):
        ns = load(make_ns())
        out = ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 99})
        self.assertIn("85퍼센트", out[0])

    def test_win_rate_without_side(self):
        ns = load(make_ns())
        out = ns["_build_ingame_briefing"]({"my_side": "", "blue_wr": 44})
        self.assertIn("블루 44퍼센트", out[0])
        self.assertIn("레드 56퍼센트", out[0])

    # ── ② 연승·연패 ────────────────────────────────────────────────
    def test_streaks_enemy_first_then_ally(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "blue": [(P("아군원딜#KR1", "a1"), S(4)), (P("아군서폿#KR1", "a2"), S(0))],
               "red": [(P("상대정글#KR1", "b1"), S(6)), (P("상대탑#KR1", "b2"), S(-3))]}
        text = " ".join(ns["_build_ingame_briefing"](ctx))
        self.assertIn("상대 상대정글님 6연승", text)
        self.assertIn("우리 팀 아군원딜님 4연승", text)
        self.assertLess(text.index("상대정글"), text.index("아군원딜"))   # 상대 연승이 먼저
        self.assertNotIn("상대탑", text)                                # 3명째는 10~15초 때문에 생략

    def test_streak_below_three_ignored(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "blue": [(P("아군#KR1", "a1"), S(2))], "red": [(P("상대#KR1", "b1"), S(-2))]}
        text = " ".join(ns["_build_ingame_briefing"](ctx))
        self.assertNotIn("연승", text)
        self.assertNotIn("연패", text)

    def test_streak_ally_slump_wording(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "blue": [(P("연패중#KR1", "a1"), S(-5))], "red": []}
        self.assertIn("우리 팀 연패중님은 5연패 중이라", " ".join(ns["_build_ingame_briefing"](ctx)))

    # ── ③ 상대 라인 꼬임 ──────────────────────────────────────────
    def _cidx(self, pos_counts):
        return {"by_pu": {"b1": {"name": "상대원딜#KR1", "pos": pos_counts}}, "nm2pu": {}}

    def test_line_twist_detected(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "red": [(P("상대원딜#KR1", "b1"), S(0))],
               "live": [{"riotIdGameName": "상대원딜", "riotIdTagLine": "KR1", "team": "CHAOS",
                         "position": "BOTTOM", "championName": "Jinx"}],
               "cidx": self._cidx({"TOP": 8, "MIDDLE": 2})}
        text = " ".join(ns["_build_ingame_briefing"](ctx))
        self.assertIn("상대 원딜 상대원딜님, 주라인이 탑이라 라인이 꼬였어요.", text)

    def test_line_twist_needs_five_games(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "red": [(P("상대원딜#KR1", "b1"), S(0))],
               "live": [{"riotName": "x", "riotIdGameName": "상대원딜", "team": "CHAOS",
                         "position": "BOTTOM"}],
               "cidx": self._cidx({"TOP": 3, "MIDDLE": 1})}      # 표본 4판 — 판단 보류
        self.assertNotIn("라인 꼬임", " ".join(ns["_build_ingame_briefing"](ctx)))

    def test_no_twist_when_position_matches(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "red": [(P("상대원딜#KR1", "b1"), S(0))],
               "live": [{"riotIdGameName": "상대원딜", "team": "CHAOS", "position": "BOTTOM"}],
               "cidx": self._cidx({"BOTTOM": 9})}
        self.assertNotIn("라인 꼬임", " ".join(ns["_build_ingame_briefing"](ctx)))

    def test_smite_infers_jungle(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "red": [(P("상대정글#KR1", "b1"), S(0))],
               "live": [{"riotIdGameName": "상대정글", "team": "CHAOS", "position": "",
                         "summonerSpells": {"summonerSpellOne": {"rawDisplayName": "SummonerSmite"},
                                            "summonerSpellTwo": {"rawDisplayName": "SummonerFlash"}}}],
               "cidx": {"by_pu": {"b1": {"pos": {"TOP": 7}}}, "nm2pu": {}}}
        # 주라인 탑인데 이번 판은 강타(정글) → 꼬임
        self.assertIn("상대 정글 상대정글님, 주라인이 탑이라", " ".join(ns["_build_ingame_briefing"](ctx)))

    def test_twist_only_for_enemy_side(self):
        ns = load(make_ns())
        ctx = {"my_side": "blue", "blue_wr": 50,
               "blue": [(P("우리원딜#KR1", "b1"), S(0))],
               "live": [{"riotIdGameName": "우리원딜", "team": "ORDER", "position": "BOTTOM"}],
               "cidx": {"by_pu": {"b1": {"pos": {"TOP": 9}}}, "nm2pu": {}}}
        self.assertNotIn("라인 꼬임", " ".join(ns["_build_ingame_briefing"](ctx)))

    # ── ④ 플레이 방향성 ───────────────────────────────────────────
    def test_direction_from_comp_gap(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": ["앞라인(탱커) 없음"], "threats": []}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]}}
        self.assertIn("앞라인이 없으니까, 받아치는 싸움을 하세요.",
                      ns["_build_ingame_briefing"](ctx)[-1])

    def test_direction_from_threat_when_no_gap(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": [], "threats": ["스케일링 2+ — …"]}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]}}
        self.assertIn("상대 스케일링이 좋으니까, 초반에 굴리세요.", ns["_build_ingame_briefing"](ctx)[-1])

    def test_direction_neutral_when_comp_unknown(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": [], "threats": []}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]}}
        self.assertIn("조합은 무난하니까", ns["_build_ingame_briefing"](ctx)[-1])

    def test_ai_comment_replaces_rule_direction(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": ["앞라인(탱커) 없음"], "threats": []}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]},
               "ai_comment": "초반 2레벨 갱으로 탑을 풀어주세요."}
        out = ns["_build_ingame_briefing"](ctx)
        self.assertEqual(out[-1], "초반 2레벨 갱으로 탑을 풀어주세요.")
        self.assertNotIn("앞라인이 없으니까", " ".join(out))

    # ── ⑤ 길이 상한 ────────────────────────────────────────────────
    def test_length_capped_but_direction_kept(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": ["앞라인(탱커) 없음"], "threats": []}))
        hot = [(P(f"상대{i}번째닉네임#KR1", f"b{i}"), S(9)) for i in range(5)]
        ally = [(P(f"아군{i}번째닉네임#KR1", f"a{i}"), S(-7)) for i in range(5)]
        ctx = {"my_side": "blue", "blue_wr": 50, "blue": ally, "red": hot,
               "champs": {"blue": ["진", "리신", "아리", "레오나", "그웬"], "red": ["가렌"] * 5}}
        out = ns["_build_ingame_briefing"](ctx)
        text = " ".join(out)
        self.assertLessEqual(len(text), ns["INGAME_BRIEF_MAX_CHARS"])
        self.assertIn("받아치는", text)                      # 방향성은 잘리지 않는다

    # ── ⑥ gameId당 1회 · 설정 OFF ────────────────────────────────
    def test_game_key_uses_game_id(self):
        ns = load(make_ns())
        k1 = ns["_brief_game_key"](12345, [], [], 1)
        k2 = ns["_brief_game_key"]("12345", [P("a", "p1")], [], 2)
        self.assertEqual(k1, k2)
        self.assertEqual(k1, "id:12345")

    def test_custom_game_key_differs_per_game_seq(self):
        ns = load(make_ns())
        blue = [P("a#KR1", "p1")]
        self.assertNotEqual(ns["_brief_game_key"](0, blue, [], 1),
                            ns["_brief_game_key"](0, blue, [], 2))
        self.assertTrue(ns["_brief_game_key"](0, blue, [], 1).startswith("roster:"))

    def test_claim_once_per_game(self):
        ns = load(make_ns())
        self.assertTrue(ns["_brief_claim"]("id:1"))
        self.assertFalse(ns["_brief_claim"]("id:1"))
        self.assertTrue(ns["_brief_claim"]("id:2"))
        self.assertFalse(ns["_brief_claim"](""))

    def test_tick_off_when_setting_disabled(self):
        th = FakeThreading()
        ns = load(make_ns(config={"ingame_tts_briefing": False}, threading_mod=th))
        self.assertEqual(ns["_ingame_briefing_tick"](1, [P("a", "p1")], [], 1), "off")
        self.assertEqual(th.started, [])          # 스레드조차 안 띄운다

    def test_tick_starts_one_thread_then_busy_then_done(self):
        th = FakeThreading()
        ns = load(make_ns(threading_mod=th))
        b = [P("a#KR1", "p1")]
        self.assertEqual(ns["_ingame_briefing_tick"](777, b, [], 1), "started")
        self.assertEqual(len(th.started), 1)
        self.assertEqual(ns["_ingame_briefing_tick"](777, b, [], 1), "busy")
        # 작업이 끝났다고 가정 → 5초 스로틀도 지났다 → 이미 처리한 판이므로 'done'
        ns["_BRIEF_STATE"]["pending"] = False
        ns["_BRIEF_STATE"]["last_try"] = time.time() - 10
        ns["_BRIEFED_GAMES"].add("id:777")
        self.assertEqual(ns["_ingame_briefing_tick"](777, b, [], 1), "done")
        self.assertEqual(len(th.started), 1)      # 같은 판은 두 번 읽지 않는다

    # ── ⑦ worker ─────────────────────────────────────────────────
    def _worker_ns(self, live, gametime, spoken):
        def _live_json(path):
            if path == "playerlist":
                return live
            if path == "gamestats":
                return {"gameTime": gametime}
            return None
        ns = load(make_ns(live_json=_live_json, speak_recorder=lambda t: spoken.append(t),
                          champ_kor=lambda eng: {"Jinx": "진", "Garen": "가렌"}.get(eng, "")))
        ns["gui_data"]["blue"] = [(P("우리#KR1", "a1"), S(5, 20, 0.6))]
        ns["gui_data"]["red"] = [(P("상대#KR1", "b1"), S(4, 20, 0.6))]
        ns["gui_data"]["blue_win_rate"] = 58
        return ns

    def _live_players(self, n=10, side_team="CHAOS"):
        live = [{"riotIdGameName": "우리", "team": "ORDER", "position": "TOP", "championName": "Jinx"}]
        for i in range(n - 1):
            live.append({"riotIdGameName": f"상대{i}", "team": side_team,
                         "position": "BOTTOM", "championName": "Garen"})
        return live

    def test_worker_speaks_once(self):
        spoken = []
        ns = self._worker_ns(self._live_players(), 6, spoken)
        ns["_ingame_briefing_worker"]("id:5", [], [])
        self.assertEqual(len(spoken), 1)
        self.assertIn("예상 승률", spoken[0])
        # 같은 판 두 번째 호출 — 이미 claim 됨 → 다시 읽지 않는다
        ns["_ingame_briefing_worker"]("id:5", [], [])
        self.assertEqual(len(spoken), 1)

    def test_worker_skips_late_game(self):
        spoken = []
        ns = self._worker_ns(self._live_players(), 200, spoken)
        ns["_ingame_briefing_worker"]("id:9", [], [])
        self.assertEqual(spoken, [])
        self.assertIn("id:9", ns["_BRIEFED_GAMES"])       # 재시도도 멈춘다

    def test_worker_waits_when_live_missing(self):
        spoken = []
        ns = self._worker_ns(None, 0, spoken)
        ns["_ingame_briefing_worker"]("id:10", [], [])
        self.assertEqual(spoken, [])
        self.assertNotIn("id:10", ns["_BRIEFED_GAMES"])   # 다음 폴링에서 다시 시도
        self.assertFalse(ns["_BRIEF_STATE"]["pending"])   # 잠금은 반드시 풀린다

    def test_worker_waits_while_champs_loading(self):
        spoken = []
        live = [{"riotIdGameName": "우리", "team": "ORDER", "position": "TOP", "championName": ""}
                for _ in range(10)]
        # championName 이 비면 _brief_champ_kor 는 '' → 챔프가 덜 찬 상태로 보고 미룬다
        ns = load(make_ns(live_json=lambda p: live if p == "playerlist" else {"gameTime": 1},
                          speak_recorder=lambda t: spoken.append(t),
                          champ_kor=lambda eng: ""))
        ns["_ingame_briefing_worker"]("id:11", [], [])
        self.assertEqual(spoken, [])
        self.assertNotIn("id:11", ns["_BRIEFED_GAMES"])

    # ── TTS 실패 경로(크래시 금지) ────────────────────────────────
    def test_speak_returns_false_off_windows(self):
        ns = load_one(load(make_ns()), "_speak_neural_tts")
        self.assertFalse(ns["_speak_neural_tts"]("테스트 문장입니다."))

    def test_speak_survives_missing_edge_tts(self):
        import sys, types
        ns = load_one(load(make_ns()), "_speak_neural_tts")
        ns["os"] = types.SimpleNamespace(name="nt", path=os.path, remove=os.remove, getpid=os.getpid)
        ns["tempfile"] = __import__("tempfile")
        ns["INGAME_TTS_VOICE"] = "ko-KR-SunHiNeural"
        ns["INGAME_TTS_RATE"] = "-8%"
        ns["INGAME_TTS_PITCH"] = "+1Hz"
        saved = sys.modules.get("edge_tts")
        sys.modules["edge_tts"] = None          # 'import edge_tts' → ImportError (미설치 재현)
        try:
            self.assertFalse(ns["_speak_neural_tts"]("테스트 문장입니다."))
        finally:
            if saved is None: sys.modules.pop("edge_tts", None)
            else: sys.modules["edge_tts"] = saved

    def test_speak_empty_text_noop(self):
        ns = load_one(load(make_ns()), "_speak_neural_tts")
        self.assertFalse(ns["_speak_neural_tts"](""))

    # ── ⑩ 전화 톤·말속도 (v83.85) ────────────────────────────────
    def test_tts_slower_calmer_constants(self):
        # 2026-11-29 사장님 피드백 "전화하는 톤으로, 말속도가 너무 빨라" — 값이 되돌아가지 않게 고정한다
        self.assertIn('INGAME_TTS_VOICE = "ko-KR-SunHiNeural"', SRC_TEXT)
        self.assertIn('INGAME_TTS_RATE = "-8%"', SRC_TEXT)
        self.assertIn('INGAME_TTS_PITCH = "+1Hz"', SRC_TEXT)
        m = re.search(r"^INGAME_BRIEF_MAX_CHARS = (\d+)", SRC_TEXT, re.M)
        self.assertIsNotNone(m)
        cap = int(m.group(1))
        self.assertGreaterEqual(cap, 95)     # 느려진 만큼 길이도 조여야 한다
        self.assertLessEqual(cap, 105)

    def test_briefing_reads_in_phone_haeyo_style(self):
        # 안내문체(~입니다/~합니다/~합니다체)는 하나도 남지 않아야 한다 — 전화로 귀띔하듯 해요체만
        ns = load(make_ns())
        cases = [
            {"my_side": "blue", "blue_wr": 72},
            {"my_side": "blue", "blue_wr": 54},
            {"my_side": "red", "blue_wr": 30},
            {"my_side": "", "blue_wr": 44},
            {"my_side": "blue", "blue_wr": 50,
             "blue": [(P("아군원딜#KR1", "a1"), S(4)), (P("아군탑#KR1", "a2"), S(-3))],
             "red": [(P("상대정글#KR1", "b1"), S(6)), (P("상대서폿#KR1", "b2"), S(-4))]},
        ]
        for ctx in cases:
            with self.subTest(ctx=ctx):
                text = " ".join(ns["_build_ingame_briefing"](ctx))
                self.assertTrue(text)
                for stiff in ("입니다", "합니다", "습니다", "하십시오"):
                    self.assertNotIn(stiff, text)

    def test_phone_tone_phrasing_examples(self):
        # 사장님이 요청한 예문 그대로(쉼표 호흡까지)
        ns = load(make_ns())
        self.assertEqual(ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 72})[0],
                         "우리 팀 예상 승률 72퍼센트, 우리 쪽이 좀 유리해요.")
        self.assertEqual(ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 38})[0],
                         "우리 팀 예상 승률 38퍼센트, 상대가 좀 앞서요.")
        self.assertEqual(ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 50})[0],
                         "우리 팀 예상 승률 50퍼센트, 팽팽한 판이에요.")
        self.assertEqual(ns["_build_ingame_briefing"]({"my_side": "", "blue_wr": 52})[0],
                         "예상 승률은 블루 52퍼센트, 레드 48퍼센트예요.")

    def test_ai_comment_prompt_asks_for_phone_tone(self):
        self.assertIn("전화 통화로 팀원에게 귀띔하듯", SRC_TEXT)
        self.assertIn("쉼표를 넣어 천천히 말하기 좋게", SRC_TEXT)

    # ── 소스 연결 확인 ─────────────────────────────────────────────
    def test_trigger_wired_in_polling_loop(self):
        src = SRC_TEXT
        # [v83.83] 로딩창(GameStart)에서도 브리핑을 띄운다 — 2999 라이브 API 는 로딩이 끝나야 응답한다
        self.assertIn('current_phase in ("GameStart", "InProgress") and is_valid_game and (temp_blue or temp_red)', src)
        self.assertIn("_ingame_briefing_tick(session_game_id, temp_blue, temp_red, game_seq,", src)
        self.assertIn("phase=current_phase, my_puuid=global_my_puuid, lock_champs=_brief_lock", src)
        self.assertIn('playerChampionSelections', src)      # 늦게 켜도 확정 픽을 LCU 세션에서 채운다
        # 설정 키 기본값·저장
        self.assertIn('"ingame_tts_briefing": True', src)
        self.assertIn('APP_CONFIG["ingame_tts_briefing"] = bool(self.var_itt.get())', src)

    def test_tts_uses_mci_without_ffmpeg(self):
        src = SRC_TEXT
        self.assertIn("mciSendStringW", src)
        self.assertIn('type mpegvideo alias', src)
        self.assertNotIn("ffmpeg", src.split("def _speak_neural_tts")[1].split("def _ingame_briefing_worker")[0])


# ── ⑧ 한국어 클라이언트 실전 시나리오 ─────────────────────────────────
class KoreanChampTest(unittest.TestCase):
    """한국어 롤 클라이언트는 championName 을 한글로 준다 — 그 이름이 버려지면 브리핑이 통째로 멈춘다."""

    def kor(self, name):
        return real_champ_ns()["_brief_champ_kor"](name)

    def test_live_korean_names_recognized(self):
        # 2026-11-27 버그: 이 세 이름이 전부 '' 였다 → with_champ=0 → 브리핑 미실행
        for name, want in (("아리", "아리"), ("리 신", "리 신"), ("미스 포츈", "미스 포츈"),
                           ("카이사", "카이사"), ("자르반 4세", "자르반 4세")):
            with self.subTest(name=name):
                self.assertEqual(self.kor(name), want)
                self.assertTrue(self.kor(name))          # 빈 문자열이면 안 된다

    def test_korean_matches_english_official_spelling(self):
        for eng, kor in (("Ahri", "아리"), ("LeeSin", "리 신"), ("MissFortune", "미스 포츈"),
                         ("Kai'Sa", "카이사"), ("Nunu", "누누와 윌럼프")):
            with self.subTest(eng=eng):
                self.assertEqual(self.kor(kor), self.kor(eng))

    def test_korean_without_space_gets_official_spelling(self):
        self.assertEqual(self.kor("리신"), "리 신")
        self.assertEqual(self.kor("미스포츈"), "미스 포츈")
        self.assertEqual(self.kor("누누와윌럼프"), "누누와 윌럼프")
        self.assertEqual(self.kor("자르반4세"), "자르반 4세")

    def test_double_space_and_padding_normalized(self):
        self.assertEqual(self.kor("  리   신 "), "리 신")

    def test_unlisted_korean_returned_as_is(self):
        # ddragon 표에 없는 신챔·표기 차이도 버리지 않는다(브리핑이 로딩으로 오인해 멈추지 않게)
        self.assertEqual(self.kor("신규챔피언"), "신규챔피언")
        self.assertEqual(self.kor("  신규 챔피언 "), "신규 챔피언")

    def test_english_still_works(self):
        self.assertEqual(self.kor("Ahri"), "아리")
        self.assertEqual(self.kor("LeeSin"), "리 신")
        self.assertEqual(self.kor("Kai'Sa"), "카이사")
        self.assertEqual(self.kor("Miss Fortune"), "미스 포츈")

    def test_english_cache_filled(self):
        ns = real_champ_ns()
        ns["_brief_champ_kor"]("Ahri")
        self.assertEqual(ns["_BRIEF_ENG2KOR"].get("ahri"), "아리")

    def test_empty_and_symbol_only(self):
        for v in ("", None, "   ", "???"):
            with self.subTest(v=v):
                self.assertEqual(self.kor(v), "")

    def test_unknown_english_still_empty(self):
        self.assertEqual(self.kor("SomeNewChamp"), "")

    # ── 실전: 한국어 playerlist 로 워커가 실제로 말하는지 ────────────────
    def _korean_live(self):
        our = ["아리", "리 신", "가렌", "진", "미스 포츈"]
        enemy = ["카이사", "누누와 윌럼프", "자르반 4세", "가렌", "진"]
        live = [{"riotIdGameName": "우리", "team": "ORDER", "position": "MIDDLE",
                 "championName": ch} for ch in our]
        for i, ch in enumerate(enemy):
            live.append({"riotIdGameName": f"상대{i}", "team": "CHAOS",
                         "position": "BOTTOM", "championName": ch})
        return live

    def test_worker_speaks_on_korean_client(self):
        seen = {}
        def _comp(ally, enemy):
            seen["ally"], seen["enemy"] = list(ally), list(enemy)
            return {"gaps": ["앞라인(탱커) 없음"], "threats": []}
        spoken = []
        live = self._korean_live()
        ns = real_champ_ns(live_json=lambda p: live if p == "playerlist" else {"gameTime": 5},
                           speak_recorder=lambda t: spoken.append(t))
        ns["_comp_report"] = _comp
        load(ns)
        ns["gui_data"]["blue"] = [(P("우리#KR1", "a1"), S(5, 20, 0.6))]
        ns["gui_data"]["red"] = [(P("상대#KR1", "b1"), S(4, 20, 0.6))]
        ns["gui_data"]["blue_win_rate"] = 58
        ns["_ingame_briefing_worker"]("id:81", [], [])
        self.assertEqual(len(spoken), 1, f"한국어 클라이언트에서 브리핑이 나오지 않음: {spoken}")
        self.assertIn("예상 승률", spoken[0])
        # 한글 챔프가 조합 분석까지 전달돼야 방향성 문장이 나온다
        self.assertEqual(seen.get("ally"), ["아리", "리 신", "가렌", "진", "미스 포츈"])
        self.assertIn("누누와 윌럼프", seen.get("enemy") or [])
        self.assertIn("앞라인이 없으니까", spoken[0])

    def test_worker_waits_when_korean_unknown_champs_missing(self):
        # 챔프가 아직 안 뜨는 로딩 상태(championName='')는 계속 미룬다
        spoken = []
        live = [{"riotIdGameName": f"p{i}", "team": "ORDER" if i < 5 else "CHAOS",
                 "championName": ("아리" if i == 0 else "")} for i in range(10)]
        ns = real_champ_ns(live_json=lambda p: live if p == "playerlist" else {"gameTime": 1},
                           speak_recorder=lambda t: spoken.append(t))
        load(ns)
        ns["_ingame_briefing_worker"]("id:82", [], [])
        self.assertEqual(spoken, [])
        self.assertNotIn("id:82", ns["_BRIEFED_GAMES"])

    def test_champ_wait_logged_once(self):
        prints = []
        live = [{"riotIdGameName": f"p{i}", "team": "ORDER" if i < 5 else "CHAOS",
                 "championName": ("아리" if i == 0 else "")} for i in range(10)]
        ns = real_champ_ns(live_json=lambda p: live if p == "playerlist" else {"gameTime": 1})
        load(ns)
        ns["print"] = lambda *a, **k: prints.append(" ".join(str(x) for x in a))
        ns["_ingame_briefing_worker"]("id:83", [], [])
        ns["_ingame_briefing_worker"]("id:83", [], [])      # 같은 상태 — 다시 안 찍는다
        wait = [p for p in prints if "챔프" in p]
        self.assertEqual(len(wait), 1, prints)
        self.assertIn("1/10명", wait[0])
        # 인원이 바뀌면 한 줄 더(원인 추적용)
        live[1]["championName"] = "리 신"
        ns["_ingame_briefing_worker"]("id:83", [], [])
        self.assertEqual(len([p for p in prints if "챔프" in p]), 2)
        self.assertIn("2/10명", prints[-1])


# ── ⑨ 로딩창(GameStart) 즉시 브리핑 ──────────────────────────────────
class GameStartBriefingTest(unittest.TestCase):
    """[v83.83] 밴픽이 끝나고 로딩창에 들어가면 2999 라이브 API 는 아직 응답하지 않는다.
    그래도 LCU 로스터·확정 픽만으로 브리핑을 만들어 '로딩 중'에 읽어야지, 게임이 시작된 뒤에 나오면 못 알아듣는다."""

    POS5 = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
    # puuid → 확정 championId (LCU lock_champs / gameData.playerChampionSelections)
    LOCK = {"a1": 1, "a2": 64, "a3": 86, "a4": 222, "a5": 21,
            "b1": 145, "b2": 20, "b3": 222, "b4": 1, "b5": 86}

    def blue(self):
        return [P(f"블루{i}#KR1", f"a{i + 1}", self.POS5[i]) for i in range(5)]

    def red(self):
        return [P(f"레드{i}#KR1", f"b{i + 1}", self.POS5[i]) for i in range(5)]

    def _ns(self, live_json=None, my_side="", cidx=None):
        spoken, seen = [], {}
        def _comp(a, e):
            seen["a"], seen["e"] = list(a), list(e)
            return {"gaps": ["앞라인(탱커) 없음"], "threats": []}
        ns = real_champ_ns(live_json=live_json or (lambda p: None),
                           speak_recorder=lambda t: spoken.append(t), my_side=my_side)
        ns["_comp_report"] = _comp
        ns["_clan_index"] = lambda force=False: (cidx or {})
        load(ns)
        ns["gui_data"]["blue"] = [(self.blue()[0], S(4))]
        ns["gui_data"]["red"] = [(self.red()[0], S(5))]
        ns["gui_data"]["blue_win_rate"] = 58
        return ns, spoken, seen

    # 로딩창: 라이브 API 자체가 없다(None)
    def test_speaks_at_gamestart_without_live_api(self):
        ns, spoken, seen = self._ns()
        ns["_ingame_briefing_worker"]("roster:x", self.blue(), self.red(),
                                      phase="GameStart", my_puuid="a1", lock_champs=self.LOCK)
        self.assertEqual(len(spoken), 1, f"로딩창에서 브리핑이 나오지 않음: {spoken}")
        self.assertIn("예상 승률", spoken[0])
        self.assertIn("58", spoken[0])                      # my_puuid 로 우리 진영(블루)을 찾아 58%
        self.assertIn("상대 레드0님 5연승", spoken[0])       # 로스터 연승은 밴픽 캐시로 이미 알고 있다
        self.assertIn("앞라인이 없으니까", spoken[0])           # 확정 픽 → 조합 분석까지 로딩창에서
        self.assertEqual(seen["a"], ["아리", "리 신", "가렌", "진", "미스 포츈"])
        self.assertEqual(seen["e"], ["카이사", "누누와 윌럼프", "진", "아리", "가렌"])
        self.assertIn("roster:x", ns["_BRIEFED_GAMES"])

    def test_side_from_my_puuid_red(self):
        ns, spoken, _seen = self._ns()
        ns["_ingame_briefing_worker"]("id:9", self.blue(), self.red(),
                                      phase="GameStart", my_puuid="b1", lock_champs=self.LOCK)
        self.assertIn("42", spoken[0])                      # 레드 입장 = 100-58
        self.assertNotIn("블루 58", spoken[0])

    def test_without_my_puuid_says_both_sides(self):
        ns, spoken, _seen = self._ns()
        ns["_ingame_briefing_worker"]("id:10", self.blue(), self.red(),
                                      phase="GameStart", my_puuid="", lock_champs=self.LOCK)
        self.assertIn("블루 58퍼센트", spoken[0])
        self.assertIn("레드 42퍼센트", spoken[0])

    # 로딩창에서 라이브가 '던졌다 비어 던' 상태(엔트리는 있는데 챔프가 빈 경우) — LCU 확정 픽으로 보강
    def test_fills_champs_from_lcu_when_live_champs_empty(self):
        live = [{"puuid": p, "riotIdGameName": p, "team": "ORDER" if p.startswith("a") else "CHAOS",
                 "position": "", "championName": ""} for p in self.LOCK]
        ns, spoken, seen = self._ns(live_json=lambda path: live if path == "playerlist" else None,
                                    my_side="blue")
        ns["_ingame_briefing_worker"]("id:11", self.blue(), self.red(),
                                      phase="GameStart", my_puuid="a1", lock_champs=self.LOCK)
        self.assertEqual(len(spoken), 1, f"라이브 챔프가 비었을 때 멈춤: {spoken}")
        self.assertEqual(seen["a"], ["아리", "리 신", "가렌", "진", "미스 포츈"])

    # 자료가 정말 없으면(라이브도 확정 픽도 없음) 예전처럼 다음 폴링으로 미룬다
    def test_waits_when_no_live_and_no_champs(self):
        ns, spoken, _seen = self._ns()
        ns["_ingame_briefing_worker"]("id:12", self.blue(), self.red(),
                                      phase="GameStart", my_puuid="a1", lock_champs={})
        self.assertEqual(spoken, [])
        self.assertNotIn("id:12", ns["_BRIEFED_GAMES"])
        self.assertFalse(ns["_BRIEF_STATE"]["pending"])

    # 로스터도 없고 라이브도 없으면 아무것도 안 한다(빈 브리핑 금지)
    def test_no_roster_no_speech(self):
        ns, spoken, _seen = self._ns()
        ns["_ingame_briefing_worker"]("id:13", [], [], phase="GameStart", my_puuid="a1", lock_champs=self.LOCK)
        self.assertEqual(spoken, [])
        self.assertNotIn("id:13", ns["_BRIEFED_GAMES"])

    # 밴픽 확정 포지션으로 상대 라인 꼬임까지 로딩창에서 잡는다
    def test_lane_twist_at_gamestart(self):
        cidx = {"by_pu": {"b1": {"name": "레드0#KR1", "pos": {"MIDDLE": 9}}}, "nm2pu": {}}
        ns, spoken, _seen = self._ns(cidx=cidx)
        ns["_ingame_briefing_worker"]("id:14", self.blue(), self.red(),
                                      phase="GameStart", my_puuid="a1", lock_champs=self.LOCK)
        self.assertIn("상대 탑 레드0님, 주라인이 미드라 라인이 꼬였어요.", spoken[0])

    def test_pseudo_live_shape(self):
        ns = load(real_champ_ns())
        ns["GLOBAL_NUMERIC_CHAMP_MAP"] = {}
        blue = [P("우리탑#KR1", "a1", "TOP"), P("우리봇#KR1", "a2", "NONE")]
        red = [P("상대#KR1", "b1", "MIDDLE")]
        ps = ns["_brief_pseudo_live"](blue, red, {"a2": 222})
        self.assertEqual([x["team"] for x in ps], ["ORDER", "ORDER", "CHAOS"])
        self.assertEqual(ps[0]["position"], "TOP")
        self.assertEqual(ps[1]["position"], "")            # NONE → 라인 꼬임 판정 생략
        self.assertEqual(ps[1]["championName"], "진")      # 확정 픽 → 한글 챔프명
        self.assertEqual(ps[0]["championName"], "")        # 픽 정보 없음
        self.assertEqual(ps[2]["riotIdGameName"], "상대")  # 태그(#KR1)는 떼고 이름만

    def test_champ_by_id(self):
        ns = load(real_champ_ns())
        self.assertEqual(ns["_brief_champ_by_id"](64), "리 신")
        self.assertEqual(ns["_brief_champ_by_id"]("145"), "카이사")
        self.assertEqual(ns["_brief_champ_by_id"](0), "")
        self.assertEqual(ns["_brief_champ_by_id"](99999), "")
        self.assertEqual(ns["_brief_champ_by_id"](None), "")

    # GameStart 에서 처리된 판은 InProgress 로 넘어가도 두 번 읽지 않는다
    def test_no_duplicate_when_phase_moves_to_inprogress(self):
        th = FakeThreading()
        ns, spoken, _seen = self._ns()
        ns["threading"] = th
        blue, red = self.blue(), self.red()
        st = ns["_ingame_briefing_tick"](0, blue, red, 3, phase="GameStart", my_puuid="a1", lock_champs=dict(self.LOCK))
        self.assertEqual(st, "started")
        self.assertEqual(len(th.started), 1)
        th.started[0].target(*th.started[0].args)          # 스레드는 가짜 — 워커를 직접 돈다
        self.assertEqual(len(spoken), 1)
        st2 = ns["_ingame_briefing_tick"](0, blue, red, 3, phase="InProgress", my_puuid="a1", lock_champs=dict(self.LOCK))
        self.assertEqual(st2, "done")
        self.assertEqual(len(th.started), 1)
        self.assertEqual(len(spoken), 1)

    def test_tick_passes_phase_puuid_lock_to_worker(self):
        th = FakeThreading()
        ns, _spoken, _seen = self._ns()
        ns["threading"] = th
        ns["_ingame_briefing_tick"](0, self.blue(), self.red(), 7, phase="GameStart",
                                    my_puuid="a1", lock_champs={"a1": 1})
        _t = th.started[0]
        self.assertEqual(_t.args[3], "GameStart")
        self.assertEqual(_t.args[4], "a1")
        self.assertEqual(_t.args[5], {"a1": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)