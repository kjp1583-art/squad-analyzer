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
    "_brief_base_name", "_brief_sv", "_brief_pos_norm", "_brief_live_pos", "_brief_main_pos",
    "_brief_match_live", "_brief_direction_lines", "_brief_trim", "_build_ingame_briefing",
    "_brief_game_key", "_brief_claim", "_ingame_briefing_tick", "_ingame_briefing_worker",
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
        "INGAME_BRIEF_MAX_CHARS": 110,
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


def P(name, puuid, pos="TOP"):
    return {"name": name, "puuid": puuid, "chosen_pos_icon": pos}


def S(streak=0, games=20, wr=0.5):
    return {"streak_val": streak, "games": games, "overall_wr": wr}


class BriefingTest(unittest.TestCase):
    # ── ① 예상 승률 ────────────────────────────────────────────────
    def test_win_rate_blue_side(self):
        ns = load(make_ns())
        out = ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 54})
        self.assertIn("우리 팀 예상 승률 54퍼센트입니다.", out[0])

    def test_win_rate_red_side_flips(self):
        ns = load(make_ns())
        out = ns["_build_ingame_briefing"]({"my_side": "red", "blue_wr": 54})
        # 레드 입장에선 46% — '우리 팀' 기준으로 뒤집혀야 한다
        self.assertIn("46퍼센트", out[0])
        self.assertNotIn("54퍼센트", out[0])

    def test_win_rate_favoured_and_behind(self):
        ns = load(make_ns())
        self.assertIn("유리", ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 72})[0])
        self.assertIn("상대가 앞섭니다", ns["_build_ingame_briefing"]({"my_side": "blue", "blue_wr": 30})[0])

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
        self.assertIn("상대 상대정글님이 6연승", text)
        self.assertIn("우리 팀 아군원딜님이 4연승", text)
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
        self.assertIn("우리 팀 연패중님이 5연패 중입니다", " ".join(ns["_build_ingame_briefing"](ctx)))

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
        self.assertIn("상대 원딜 상대원딜님은 주라인 탑, 라인 꼬임입니다.", text)

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
        self.assertIn("상대 정글 상대정글님은 주라인 탑", " ".join(ns["_build_ingame_briefing"](ctx)))

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
        self.assertIn("앞라인이 없으니 받아치는 싸움을 하세요.",
                      ns["_build_ingame_briefing"](ctx)[-1])

    def test_direction_from_threat_when_no_gap(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": [], "threats": ["스케일링 2+ — …"]}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]}}
        self.assertIn("상대 스케일링이 좋으니 초반에 굴리세요.", ns["_build_ingame_briefing"](ctx)[-1])

    def test_direction_neutral_when_comp_unknown(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": [], "threats": []}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]}}
        self.assertIn("조합은 무난하니", ns["_build_ingame_briefing"](ctx)[-1])

    def test_ai_comment_replaces_rule_direction(self):
        ns = load(make_ns(comp_report=lambda a, e: {"gaps": ["앞라인(탱커) 없음"], "threats": []}))
        ctx = {"my_side": "blue", "blue_wr": 50, "champs": {"blue": ["진"], "red": ["가렌"]},
               "ai_comment": "초반 2레벨 갱으로 탑을 풀어주세요."}
        out = ns["_build_ingame_briefing"](ctx)
        self.assertEqual(out[-1], "초반 2레벨 갱으로 탑을 풀어주세요.")
        self.assertNotIn("앞라인이 없으니", " ".join(out))

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
        ns["INGAME_TTS_RATE"] = "+10%"
        ns["INGAME_TTS_PITCH"] = "+6Hz"
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

    # ── 소스 연결 확인 ─────────────────────────────────────────────
    def test_trigger_wired_in_polling_loop(self):
        src = SRC_TEXT
        self.assertIn("_ingame_briefing_tick(session_game_id, temp_blue, temp_red, game_seq)", src)
        self.assertIn('current_phase == "InProgress" and is_valid_game and (temp_blue or temp_red)', src)
        # 설정 키 기본값·저장
        self.assertIn('"ingame_tts_briefing": True', src)
        self.assertIn('APP_CONFIG["ingame_tts_briefing"] = bool(self.var_itt.get())', src)

    def test_tts_uses_mci_without_ffmpeg(self):
        src = SRC_TEXT
        self.assertIn("mciSendStringW", src)
        self.assertIn('type mpegvideo alias', src)
        self.assertNotIn("ffmpeg", src.split("def _speak_neural_tts")[1].split("def _ingame_briefing_worker")[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
