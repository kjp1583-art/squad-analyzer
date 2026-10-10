"""지표 팩 m(게임 시간) 되돌림 단위 테스트 — squad_analyzer.py 는 Windows 전용 import 가 많아 _fix_pack_minutes 만 AST 로 떼어 실행한다.
   python desktop/metrics_minutes_test.py          (SA_SRC=<다른 squad_analyzer.py> 로 옛 소스에도 돌려 볼 수 있다)

   [2026-10-10 사장님 제보 「일단즐겨 서포터 웹 명예의 전당 DPM 이 이상하다」] 2026-09-19·22 다섯 판의 지표 팩은 m 칸에 분당 CS 가 들어 있었다.
   웹 parseMetrics(tests/web_hof_metrics_test.py)와 같은 규칙인지 같은 입력으로 견준다. 가짜 숫자만 쓴다(외부 접속·실제 시트 없음)."""
import ast, os, re, unittest

SRC = os.environ.get("SA_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py")
TEXT = open(SRC, encoding="utf-8").read()
TREE = ast.parse(TEXT)


def load():
    body = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "_fix_pack_minutes"]
    assert body, "_fix_pack_minutes 를 못 찾음"
    ns = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), SRC, "exec"), ns)
    return ns["_fix_pack_minutes"]


def parse(s):
    o = {}
    for tok in str(s).split("|"):
        m = re.match(r"([a-z]+)(-?[\d.]+)$", tok.strip())
        if m: o[m.group(1)] = float(m.group(2))
    return o


class T(unittest.TestCase):
    def setUp(self): self.fix = load()

    def m(self, s): return round(self.fix(parse(s)).get("m", 0), 2)

    def test_repair(self):
        self.assertAlmostEqual(self.m("g7631|cs23|m0.86|kp55.0|cw10|wp35|wk10|dt22169"), 26.74, places=2)
        self.assertAlmostEqual(self.m("g15918|cs252|m9.45|kp71.43|cw0|wp5|wk4|dt16745"), 26.67, places=2)
        self.assertAlmostEqual(self.m("g5424|cs17|m0.7|kp50.0|cw6|wp31|wk5|dt14330"), 24.29, places=2)

    def test_untouched(self):
        self.assertEqual(self.m("g12468|cs51|m28.9|kp71|vs99|cw12|wp37|wk13|op0|tk2|dt18742"), 28.9)
        self.assertEqual(self.m("g8610|cs150|m26.5|kp30.0|cw2|wp4|wk4|dt33385"), 26.5)   # vs 없는 옛 서식이어도 정상 행은 그대로(9/8 사고)
        self.assertEqual(self.m("g17000|cs330|m27.0|kp50|vs20|dt20000"), 27.0)
        self.assertEqual(self.m("g9000|cs196|m14.0|kp50|vs20|dt20000"), 14.0)             # 경계(분당 CS 14.0)는 그대로
        self.assertEqual(self.m("m0.5|kp50"), 0.5)                                        # cs 없음 — 건드리지 않음

    def test_drop(self):
        self.assertEqual(self.m("g9000|cs100|m1.0|kp50|vs20|dt20000"), 0.0)               # 되돌린 값 100분 → 버림
        self.assertEqual(self.m("g9000|cs100|m5.0|kp50|vs20|dt20000"), 20.0)              # 20분 → 되돌림

    def test_never_raises(self):
        self.assertEqual(self.fix({}), {})
        self.assertEqual(self.fix({"cs": 0.0, "m": 3.0}), {"cs": 0.0, "m": 3.0})
        self.assertEqual(self.fix({"cs": 10.0}), {"cs": 10.0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
