"""P-5 프로필 아이콘·레벨 수집 단위 테스트 — squad_analyzer.py 는 Windows 전용 import 가 많아
   필요한 함수만 AST 로 떼어 가짜 requests 와 함께 실행한다.  python desktop/profile_icon_test.py"""
import ast, os, types, unittest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py")
NAMES = {"_fetch_summoner_profile", "fetch_solo_rank_by_riotid", "_carry_profile_icons"}


class Resp:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._b, self.headers = code, body, headers or {}
    def json(self): return self._b


def load(routes, sleeps):
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES], type_ignores=[])
    calls = []
    def get(url, headers=None, timeout=None):
        calls.append(url)
        for frag, seq in routes.items():
            if frag in url: return seq.pop(0) if len(seq) > 1 else seq[0]
        return Resp(404)
    ns = {"requests": types.SimpleNamespace(get=get), "time": types.SimpleNamespace(sleep=sleeps.append),
          "tnorm": lambda s: str(s).replace(" ", "").lower()}
    ns.setdefault("_rank_score", lambda t, d, lp: 1000)
    exec(compile(mod, SRC, "exec"), ns)
    return ns, calls


ACC = {"accounts/by-riot-id": [Resp(200, {"puuid": "P"})]}
SOLO = [Resp(200, [{"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "II", "leaguePoints": 10, "wins": 5, "losses": 4}])]


class T(unittest.TestCase):
    def test_icon_and_level(self):
        ns, calls = load({**ACC, "summoners/by-puuid": [Resp(200, {"profileIconId": 4568, "summonerLevel": 312, "id": "S"})],
                          "entries/by-puuid": SOLO}, [])
        r = ns["fetch_solo_rank_by_riotid"]("a b#KR1", "k")
        self.assertEqual((r["tier"], r["icon"], r["level"]), ("GOLD", 4568, 312))

    def test_429_retry_then_ok(self):
        sl = []
        ns, _ = load({**ACC, "summoners/by-puuid": [Resp(429, headers={"Retry-After": "3"}), Resp(200, {"profileIconId": 7, "summonerLevel": 30})],
                      "entries/by-puuid": SOLO}, sl)
        r = ns["fetch_solo_rank_by_riotid"]("x#KR1", "k")
        self.assertEqual((r["icon"], sl), (7, [3.0]))

    def test_summoner_fail_keeps_rank(self):
        ns, _ = load({**ACC, "summoners/by-puuid": [Resp(500)], "entries/by-puuid": SOLO}, [])
        r = ns["fetch_solo_rank_by_riotid"]("x#KR1", "k")
        self.assertEqual(r["tier"], "GOLD"); self.assertNotIn("icon", r)

    def test_unranked_has_icon(self):
        ns, _ = load({**ACC, "summoners/by-puuid": [Resp(200, {"profileIconId": 1, "summonerLevel": 9})],
                      "entries/by-puuid": [Resp(200, [])]}, [])
        r = ns["fetch_solo_rank_by_riotid"]("x#KR1", "k")
        self.assertEqual((r["score"], r["icon"]), (None, 1))

    def test_carry_previous(self):
        ns, _ = load({}, [])
        out = [["닉네임","티어","LP","솔랭승","솔랭패","점수","갱신","아이콘","레벨"],
               ["가", "GOLD II", 1, 1, 1, 1, "t", "", ""], ["나", "GOLD II", 1, 1, 1, 1, "t", 9, 99]]
        prev = [["닉네임","티어","LP","솔랭승","솔랭패","점수","갱신","아이콘","레벨"], ["가","","","","","","",123,45], ["나","","","","","","",1,1]]
        ns["_carry_profile_icons"](out, prev)
        self.assertEqual(out[1][7:], [123, 45]); self.assertEqual(out[2][7:], [9, 99])
        ns["_carry_profile_icons"](out, [["닉네임","티어"]])   # 옛 7열 시트 — 아무 일 없음


if __name__ == "__main__":
    unittest.main()
