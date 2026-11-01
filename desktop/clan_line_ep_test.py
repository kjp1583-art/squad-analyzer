"""고스트밴픽왕: 상대 클랜 챔프폭 줄이 「이번 판 포지션」 기준인지 — 2026-11-01 제보(정글 Donk 를 「미드 로크 21판」이라 말함).
squad_analyzer.py 는 Windows 전용 import 가 많아 _clan_line 만 AST 로 떼어 가짜 데이터로 실행한다.   python desktop/clan_line_ep_test.py"""
import ast, os, unittest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py")
TEXT = open(SRC, encoding="utf-8").read()

def load():
    tree = ast.parse(TEXT)
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_clan_line"]
    ns = {"tier_of": lambda name: ""}
    exec(compile(ast.Module(body=body, type_ignores=[]), SRC, "exec"), ns)
    return ns["_clan_line"]

# 실제 시트 집계에서 가져온 모양(2026-11-01): Donk 는 주포지션 미드(트페 11판 …, 로크 미드 3판), 허거덩은 주포지션 원딜인데 이번 판은 미드(로크 미드 21판)
IDX = {"by_pu": {
    "donk": {"name": "Donk#3576", "g": 81, "w": 40, "pos": {"미드": 60, "정글": 6, "서폿": 7, "원딜": 6},
             "champs": {"트위스티드 페이트": [11, 6], "제라스": [5, 1], "로크": [3, 1], "오공": [3, 2]},
             "chpos": {"트위스티드 페이트": {"미드": 11}, "제라스": {"미드": 5}, "로크": {"미드": 3}, "오공": {"정글": 3}}},
    "hugd": {"name": "허거덩#최대4강", "g": 334, "w": 180, "pos": {"원딜": 120, "미드": 70, "정글": 60, "탑": 20},
             "champs": {"유나라": [28, 15], "징크스": [22, 13], "로크": [21, 11], "오로라": [18, 10], "아칼리": [11, 8], "릴리아": [16, 10]},
             "chpos": {"유나라": {"원딜": 28}, "징크스": {"원딜": 22}, "로크": {"미드": 21}, "오로라": {"미드": 18}, "아칼리": {"미드": 11}, "릴리아": {"정글": 16}}},
}}

class T(unittest.TestCase):
    def test_old_line_is_the_trap(self):
        L = load()
        d, h = L("donk", IDX), L("hugd", IDX)
        self.assertIn("Donk(미드)", d); self.assertIn("허거덩(원딜)", h)     # ep 없으면 예전 표기 그대로(다른 호출부 호환)
    def test_enemy_line_uses_this_game_position(self):
        L = load()
        d, h = L("donk", IDX, ep="정글"), L("hugd", IDX, ep="미드")
        self.assertIn("[이번 판 포지션:정글]", d); self.assertNotIn("(미드)", d)
        self.assertIn("[이번 판 포지션:미드]", h); self.assertNotIn("(원딜)", h)
        self.assertIn("로크 21판", h); self.assertIn("오로라 18판", h); self.assertIn("아칼리 11판", h)
        self.assertNotIn("유나라", h); self.assertNotIn("릴리아", h)            # 다른 포지션에서 쓴 챔프는 안 싣는다
        self.assertNotIn("로크", d); self.assertNotIn("21판", d)                 # Donk 줄에는 허거덩의 로크가 없다
    def test_no_record_at_position(self):
        L = load(); d = L("donk", IDX, ep="탑")
        self.assertIn("탑 전적 없음", d); self.assertNotIn("트위스티드", d)    # 그 자리 전적이 없으면 다른 자리 주력을 싣지 않는다
        j = L("donk", IDX, ep="정글"); self.assertIn("오공 3판", j); self.assertNotIn("트위스티드", j)
    def test_unknown_position_falls_back(self):
        L = load(); self.assertIn("(미드)", L("donk", IDX, ep="")); self.assertIn("(미드)", L("donk", IDX, ep="선택안함"))

if __name__ == "__main__": unittest.main()
