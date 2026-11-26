"""스펠체크 음성팩 시험 — 피클 보이스팩(voice_pickle) 추가분.
squad_analyzer.py 는 Windows 전용 import 가 많아 _spell_say 만 AST 로 떼어 가짜 winsound 로 돌린다.
확인: 설정 'tts'/'pickle'/'dub'(·키 없음) 에 따라 찾는 폴더 우선순위가 맞는지,
      고른 팩에 파일이 없으면 기본 음성(voice)으로 대체하는지, 어디에도 없으면 비프음인지,
      desktop/voice_pickle/ 에 10개 wav 가 다 있는지.      python desktop/spell_voice_pack_test.py
"""
import ast
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "squad_analyzer.py")
PY = "탑_noflash.wav"

with open(SRC, encoding="utf-8") as _f:
    TREE = ast.parse(_f.read())


def load_spell_say():
    """_spell_say 함수 하나만 떼어 가짜 환경에서 돌릴 수 있게 만든다."""
    body = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "_spell_say"]
    assert body, "_spell_say 를 찾지 못했습니다"
    return body


class FakeWinsound(types.ModuleType):
    def __init__(self):
        super().__init__("winsound")
        self.played = []
        self.beeps = []

    def PlaySound(self, path, flags=0):
        self.played.append(path)

    def MessageBeep(self, kind=0):
        self.beeps.append(kind)


FakeWinsound.SND_FILENAME = 0x00020000
FakeWinsound.SND_ASYNC = 0x0001
FakeWinsound.SND_NODEFAULT = 0x0002


class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = os.path.join(self.tmp.name, "squad_analyzer.py")
        with open(self.app, "w", encoding="utf-8"):
            pass
        self.ws = FakeWinsound()
        self.config = {}
        self.ns = {
            "os": os,
            "sys": types.SimpleNamespace(frozen=False, executable=sys.executable),
            "APP_CONFIG": self.config,
            "resource_path": lambda p: os.path.join(self.tmp.name, "_bundled", p),
            "winsound": self.ws,
            "__file__": self.app,
        }
        # 네임스페이스에 import winsound 가 실제로 걸리도록 sys.modules 를 잠깐 바꿔 준다
        self._old_ws = sys.modules.get("winsound")
        sys.modules["winsound"] = self.ws
        exec(compile(ast.Module(body=load_spell_say(), type_ignores=[]), SRC, "exec"), self.ns)
        self.say = self.ns["_spell_say"]

    def tearDown(self):
        if self._old_ws is None:
            sys.modules.pop("winsound", None)
        else:
            sys.modules["winsound"] = self._old_ws
        self.tmp.cleanup()

    def put(self, folder):
        d = os.path.join(self.tmp.name, folder)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, PY), "wb") as f:
            f.write(b"RIFF")

    def last(self):
        self.assertTrue(self.ws.played, "아무 음성도 재생하지 않았습니다")
        return os.path.relpath(self.ws.played[-1], self.tmp.name).replace(os.sep, "/")

    def test_default_is_tts(self):
        self.put("voice")
        self.put("voice_pickle")
        self.say("탑", "noflash")
        self.assertEqual(self.last(), "voice/" + PY, "설정이 없으면(기본 tts) 내장 AI 음성")

    def test_tts_ignores_other_packs(self):
        for d in ("voice_pickle", "voice_dub"):
            self.put(d)
        self.say("탑", "noflash")
        self.assertEqual(self.ws.beeps, [0x40], "tts 인데 voice 에 파일이 없으면 비프음")

    def test_pickle_first(self):
        self.put("voice")
        self.put("voice_pickle")
        self.put("voice_dub")
        self.config["spell_voice_pack"] = "pickle"
        self.say("탑", "noflash")
        self.assertEqual(self.last(), "voice_pickle/" + PY, "pickle 은 voice_pickle 을 먼저")

    def test_pickle_falls_back_to_tts(self):
        self.put("voice")
        self.put("voice_dub")
        self.config["spell_voice_pack"] = "pickle"
        self.say("탑", "noflash")
        self.assertEqual(self.last(), "voice/" + PY, "피클 파일이 없으면 기본 음성으로 대체")

    def test_dub_first(self):
        self.put("voice")
        self.put("voice_pickle")
        self.put("voice_dub")
        self.config["spell_voice_pack"] = "dub"
        self.say("탑", "noflash")
        self.assertEqual(self.last(), "voice_dub/" + PY, "dub 은 voice_dub 을 먼저(기존 동작 유지)")

    def test_dub_falls_back_to_tts(self):
        self.put("voice")
        self.put("voice_pickle")
        self.config["spell_voice_pack"] = "dub"
        self.say("탑", "noflash")
        self.assertEqual(self.last(), "voice/" + PY, "더빙 파일이 없으면 기본 음성으로 대체")

    def test_pickle_kind_missing_uses_voice(self):
        self.put("voice_pickle")
        os.remove(os.path.join(self.tmp.name, "voice_pickle", PY))
        self.put("voice")
        self.config["spell_voice_pack"] = "pickle"
        self.say("탑", "noflash")
        self.assertEqual(self.last(), "voice/" + PY, "그 포지션 파일만 없으면 그때만 기본 음성")

    def test_nothing_anywhere_beeps(self):
        self.config["spell_voice_pack"] = "pickle"
        self.say("탑", "noflash")
        self.assertEqual(self.ws.played, [])
        self.assertEqual(self.ws.beeps, [0x40], "어디에도 없으면 종전 비프음")

    def test_all_ten_wavs_committed(self):
        d = os.path.join(HERE, "voice_pickle")
        want = {f"{p}_{k}.wav" for p in ("탑", "정글", "미드", "원딜", "서폿") for k in ("noflash", "flashon")}
        self.assertTrue(os.path.isdir(d), "desktop/voice_pickle 폴더가 없습니다")
        have = {f for f in os.listdir(d) if f.lower().endswith(".wav")}
        self.assertEqual(have, want, "voice_pickle 에는 10개 wav 가 정확히 있어야 합니다")
        for f in want:
            self.assertGreater(os.path.getsize(os.path.join(d, f)), 1000, f"{f} 가 비어 있습니다")


if __name__ == "__main__":
    unittest.main()
