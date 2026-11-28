"""🛡️ [v83.89] 밴픽 빌드 카드 이름표 조회(_lolps_champ_name) 회귀 시험.

2026-11-29 사장님 제보 — "챔피언이름이 파이크인데 챔피언555 이렇게 뜬다".
원인: `_lolps_champ_name` 이 LCU 폴링 루프의 **지역 변수** `champ_map` 을 전역처럼 읽어
NameError 로 죽었고, 카드는 이름 없이 `챔피언 555` 로 그려졌다.

squad_analyzer.py 는 Windows 전용 import(winreg 등)가 많아 통째로 import 할 수 없다.
ingame_briefing_test.py 와 같은 방식으로 그 함수만 AST 로 떼어 가짜 전역 환경에서 돌린다.

  python3 desktop/lolps_champ_name_test.py
"""
import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "squad_analyzer.py")

with open(SRC, encoding="utf-8") as _f:
    SRC_TEXT = _f.read()
TREE = ast.parse(SRC_TEXT)
_DEFS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}


def load(ns):
    """_lolps_champ_name 만 그대로 exec 해 넣는다(전역 맵은 ns 에서 해석)."""
    node = _DEFS.get("_lolps_champ_name")
    assert node is not None, "_lolps_champ_name 을 squad_analyzer.py 에서 찾지 못했습니다"
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 SRC, "exec"), ns)
    return ns["_lolps_champ_name"]


def ns_with(global_map=None, numeric_map=None, **extra):
    ns = {"global_champ_map": dict(global_map or {}),
          "GLOBAL_NUMERIC_CHAMP_MAP": dict(numeric_map or {})}
    ns.update(extra)
    return ns


class LolpsChampNameTest(unittest.TestCase):
    def test_pyke_korean_name(self):
        """제보 그대로 — 555 는 파이크다."""
        fn = load(ns_with({555: {"kor": "파이크", "eng": "Pyke"}}, {555: "파이크"}))
        self.assertEqual(fn(555), "파이크")

    def test_never_reads_lcu_local_champ_map(self):
        """지역 변수 champ_map 을 읽으면 여기서 NameError 로 죽는다(원래 버그)."""
        fn = load(ns_with({555: {"kor": "파이크", "eng": "Pyke"}}))     # champ_map 없음
        self.assertEqual(fn(555), "파이크")
        # 폴링 루프 지역변수와 같은 이름이 전역에 있어도 그 값에 기대지 않는다
        fn2 = load(ns_with({555: {"kor": "파이크", "eng": "Pyke"}}, champ_map={555: {"kor": "엉뚱"}}))
        self.assertEqual(fn2(555), "파이크")

    def test_numeric_map_only(self):
        """global_champ_map 이 비어도 GLOBAL_NUMERIC_CHAMP_MAP 로 이름을 준다."""
        fn = load(ns_with({}, {555: "파이크"}))
        self.assertEqual(fn(555), "파이크")

    def test_global_map_keeps_official_spacing(self):
        """정식 표기(띄어쓰기)를 우선한다 — 숫자맵은 공백을 지운 사본이다."""
        fn = load(ns_with({21: {"kor": "미스 포츈", "eng": "MissFortune"}}, {21: "미스포츈"}))
        self.assertEqual(fn(21), "미스 포츈")

    def test_unknown_and_bad_input_is_empty(self):
        fn = load(ns_with({555: {"kor": "파이크"}}, {555: "파이크"}))
        for bad in (0, -1, None, "", "abc", 12345, [], {}):
            self.assertEqual(fn(bad), "", repr(bad))
        self.assertEqual(load(ns_with())(555), "")        # 맵이 통째로 비어도 예외 없이 ""
        self.assertEqual(load(ns_with({555: {"kor": ""}}))(555), "")   # 빈 값은 빈 값

    def test_wired_to_build_card(self):
        """카드 쪽에 이 함수가 그대로 연결돼 있어야 한다(연결이 빠지면 이름이 또 빈다)."""
        self.assertIn("lolps_build.configure(DDRAGON_VERSION, _lolps_champ_name", SRC_TEXT)
        self.assertNotIn("for _m in (champ_map, GLOBAL_NUMERIC_CHAMP_MAP)", SRC_TEXT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
