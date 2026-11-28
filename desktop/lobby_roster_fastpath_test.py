"""🚀 로비 인원 체크 고속화 시험 (v83.87)

제보(2026-11-29): "사람 차있는 방에서 분석기 키면 인원체크하는데 한참걸리네"

squad_analyzer.py 는 Windows 전용 import(winreg 등)가 많아 통째로 import 할 수 없다.
그래서 이번에 새로 만든 모듈 함수들만 AST 로 떼어 가짜 LCU·가짜 gviz 에서 돌린다.

확인 항목
  ① parse_team 이 10명 이름·랭크를 **병렬**로 묻는다 (직렬이면 3.0초 걸릴 20회가 1초 안)
  ② 같은 방을 다시 파싱하면 LCU 를 **한 번도 다시 묻지 않는다**(TTL 캐시) · TTL 이 지나면 다시 묻는다
  ③ summonerId 만 있는 사람(토너먼트 드래프트) → puuid 이름 해석 후 그 puuid 로 랭크까지
  ④ 봇(BOT_)은 LCU 조회 없이 "🤖 OO 봇" · UNRANKED 도 캐시된다(언랭 방에서 매 폴링 재조회 금지)
  ⑤ 이름·puuid 폴백("알 수 없는 유저"·TEMP_ID) 과 포지션 폴백·정렬 규칙이 예전과 같다
  ⑥ 시트 연결 전에는 last_lobby_fingerprint 를 찍지 않는다(연결되면 즉시 재계산) · 실패 시 4초 재시도
  ⑦ worksheet() 는 워크시트 객체를 캐시해 매 폴링 부르지 않는다(재연결 시 자동 무효)
  ⑧ _crunch_from_aggregate 가 STAT_* 6탭을 **병렬**로 받고, 표본 판정·필수 탭 실패 폴백은 그대로

    python desktop/lobby_roster_fastpath_test.py
"""
import ast
import concurrent.futures
import os
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "squad_analyzer.py")
SRC_TEXT = open(SRC, encoding="utf-8").read()
TREE = ast.parse(SRC_TEXT)
_DEFS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}

FAILED = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILED.append(msg)
    return bool(cond)


def load(ns, *names):
    for n in names:
        node = _DEFS.get(n)
        assert node is not None, "%s 를 squad_analyzer.py 에서 찾지 못했습니다" % n
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     SRC, "exec"), ns)


# ────────────────────────── 가짜 LCU ──────────────────────────
class FakeResp:
    def __init__(self, code, data):
        self.status_code = code
        self._data = data

    def json(self):
        return self._data


class FakeLCU:
    """LCU 대역 — 경로별 응답 · 호출 기록 · 지연(직렬이면 눈에 띄게 느리다)."""

    def __init__(self, delay=0.15):
        self.base = "https://127.0.0.1:1234"
        self.delay = delay
        self.calls = []
        self.summ_by_sid = {}
        self.summ_by_puuid = {}
        self.rank_by_puuid = {}
        self.rank_missing = set()
        self._lock = threading.Lock()

    def Session(self):          # requests.Session() 대역
        return self

    def get(self, url, headers=None, verify=None, timeout=None):
        with self._lock:
            self.calls.append(url)
        if self.delay:
            time.sleep(self.delay)
        path = url[len(self.base):]
        if path.startswith("/lol-summoner/v1/summoners/"):
            d = self.summ_by_sid.get(int(path.rsplit("/", 1)[-1]))
            return FakeResp(200, d) if d else FakeResp(404, {})
        if path.startswith("/lol-summoner/v2/summoners/puuid/"):
            d = self.summ_by_puuid.get(path.rsplit("/", 1)[-1])
            return FakeResp(200, d) if d else FakeResp(404, {})
        if path.startswith("/lol-ranked/v1/ranked-stats/"):
            uid = path.rsplit("/", 1)[-1]
            if uid in self.rank_missing:
                return FakeResp(404, {})
            return FakeResp(200, self.rank_by_puuid.get(uid, {"queues": []}))
        return FakeResp(404, {})

    def count(self, needle=""):
        return len([u for u in self.calls if needle in u])

    def reset(self):
        self.calls = []


def make_ns(lcu):
    ns = {
        "requests": lcu,
        "concurrent": concurrent,
        "threading": threading,
        "time": time,
        "print": lambda *a, **k: None,
        "GLOBAL_NUMERIC_CHAMP_MAP": {1: "애니"},
        "_LCU_TTL_NAME": 600.0,
        "_LCU_TTL_RANK": 300.0,
        "_LCU_CACHE_MAX": 600,
        "_LCU_CACHE": {},
        "_LCU_CACHE_LOCK": threading.Lock(),
        "_LCU_TL": threading.local(),
        "_LCU_POS_FALLBACK": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"],
        "_CRUNCH_RETRY_SEC": 4.0,
        "_WS_TTL": 600.0,
        "_WS_CACHE": {},
        "_WS_CACHE_LOCK": threading.Lock(),
    }
    load(ns, "_lcu_session", "_lcu_get", "_lcu_get_many", "_lcu_cache_get", "_lcu_cache_put",
         "_lcu_riot_id", "_lcu_rank_of", "_parse_team", "_lobby_stat_decision",
         "_ws_cache_put", "get_worksheet_cached")
    return ns


GOLD = {"queues": [{"queueType": "RANKED_SOLO_5x5", "tier": "gold", "leaguePoints": 30}]}


def roster(n=10, prefix="pu"):
    return [{"puuid": "%s%d" % (prefix, i), "summonerId": 0, "summonerName": "",
             "gameName": "", "assignedPosition": ""} for i in range(n)]


# ────────────────────── ① 병렬 · ② 캐시 ──────────────────────
def test_parallel_and_cache(ns, lcu):
    print("\n[1] 로비 10명 이름·랭크 병렬 조회")
    lcu.summ_by_puuid = {"pu%d" % i: {"gameName": "선수%d" % i, "tagLine": "KR1"} for i in range(10)}
    lcu.rank_by_puuid = {"pu%d" % i: GOLD for i in range(10)}
    lcu.reset()
    t0 = time.time()
    out = ns["_parse_team"](roster(10), lcu.base, {"Authorization": "x"}, {})
    dt = time.time() - t0
    ok(len(out) == 10, "10명 모두 파싱 (%d명)" % len(out))
    ok(lcu.count("/lol-summoner/v2/summoners/puuid/") == 10 and lcu.count("/lol-ranked/") == 10,
       "이름 10회·랭크 10회 조회 (%d회)" % len(lcu.calls))
    ok(dt < 1.2, "20회 조회를 병렬로 — %.2fs (직렬이면 20×0.15=3.0s)" % dt)
    names = sorted(p["name"] for p in out)
    ok(names[0] == "선수0#KR1", "닉네임 표기 '게임이름#태그' 유지 (%s)" % names[0])
    ok(all(p["tier_icon"] == "GOLD" and p["lp"] == 30 for p in out), "솔로 티어·LP 유지 (GOLD 30)")

    print("\n[2] 같은 방 재파싱 — LCU 재조회 0회")
    lcu.reset()
    t0 = time.time()
    out2 = ns["_parse_team"](roster(10), lcu.base, {"Authorization": "x"}, {})
    dt2 = time.time() - t0
    ok(len(lcu.calls) == 0, "캐시 적중으로 LCU 요청 0회 (%d회)" % len(lcu.calls))
    ok(dt2 < 0.05, "재파싱 %.3fs" % dt2)
    ok([p["name"] for p in out2] == [p["name"] for p in out], "결과 동일")

    print("\n[2-1] TTL 이 지나면 다시 조회")
    for _k, _v in list(ns["_LCU_CACHE"].items()):        # 캐시 항목을 1000초 과거로 밀어 만료시킨다
        ns["_LCU_CACHE"][_k] = (_v[0] - 1000.0, _v[1] - 1000.0, _v[2])
    lcu.reset()
    ns["_parse_team"](roster(10), lcu.base, {"Authorization": "x"}, {})
    ok(len(lcu.calls) == 20, "만료 뒤 20회 재조회 (%d회)" % len(lcu.calls))


# ────────────── ③ summonerId 익명 · ④ 봇 · ⑤ 폴백/정렬 ──────────────
def test_edge_rules(ns, lcu):
    print("\n[3] summonerId 만 있는 사람(토너먼트 드래프트)")
    lcu.summ_by_sid = {777: {"gameName": "닉네임", "tagLine": "KR1", "puuid": "uid777"}}
    lcu.rank_by_puuid = {"uid777": GOLD}
    raw = [{"puuid": "", "summonerId": 777, "summonerName": "", "gameName": "", "assignedPosition": "TOP"}]
    out = ns["_parse_team"](raw, lcu.base, {"Authorization": "x"}, {})
    ok(len(out) == 1 and out[0]["name"] == "닉네임#KR1" and out[0]["puuid"] == "uid777",
       "summonerId 로 이름·puuid 해석 (%s / %s)" % (out[0]["name"], out[0]["puuid"]))
    ok(out[0]["tier_icon"] == "GOLD", "그 puuid 로 랭크까지 (GOLD)")

    print("\n[4] 봇은 LCU 를 묻지 않는다")
    lcu.reset()
    raw = [{"puuid": "BOT_1", "botChampionId": 1, "summonerId": 0, "assignedPosition": "MIDDLE"}]
    out = ns["_parse_team"](raw, lcu.base, {"Authorization": "x"}, {1: {"kor": "애니"}})
    ok(out and out[0]["name"] == "🤖 애니 봇" and out[0]["puuid"] == "BOT_1",
       "봇 표시 유지 (%s / %s)" % (out[0]["name"], out[0]["puuid"]))
    ok(out[0]["tier_icon"] == "UNRANKED" and out[0]["lp"] == 0, "봇은 UNRANKED")
    ok(len(lcu.calls) == 0, "봇에게 LCU 요청 없음 (%d회)" % len(lcu.calls))

    print("\n[5] 이름·puuid 폴백")
    lcu.summ_by_puuid, lcu.rank_by_puuid = {}, {}
    raw = [{"puuid": "ghost", "summonerId": 0, "summonerName": "", "gameName": "", "assignedPosition": "TOP"},
           {"puuid": "", "summonerId": 0, "summonerName": "", "gameName": "", "assignedPosition": "JUNGLE"}]
    out = ns["_parse_team"](raw, lcu.base, {"Authorization": "x"}, {})
    names = sorted(p["name"] for p in out)
    ok("알 수 없는 유저" in names, "이름 못 찾으면 '알 수 없는 유저'")
    ok(any(str(p["puuid"]).startswith("TEMP_ID_0_") for p in out), "puuid 없으면 TEMP_ID 폴백")

    print("\n[6] 포지션 폴백·정렬 규칙")
    raw = [{"puuid": "a", "summonerName": "미드맨", "assignedPosition": "MIDDLE"},
           {"puuid": "b", "summonerName": "빈칸맨", "assignedPosition": ""},
           {"puuid": "c", "summonerName": "서폿맨", "assignedPosition": "UTILITY"},
           {"puuid": "d", "summonerName": "유령맨", "assignedPosition": "UNSELECTED",
            "firstPositionPreference": "BOTTOM"}]
    lcu.summ_by_puuid = {"a": {"gameName": "미드맨", "tagLine": ""}, "b": {"gameName": "빈칸맨", "tagLine": ""},
                         "c": {"gameName": "서폿맨", "tagLine": ""}, "d": {"gameName": "유령맨", "tagLine": ""}}
    out = ns["_parse_team"](raw, lcu.base, {"Authorization": "x"}, {})
    order = [p["name"] for p in out]
    ok(order == ["빈칸맨", "미드맨", "유령맨", "서폿맨"], "포지션 순 정렬 + 인덱스 폴백 (JUNGLE·BOTTOM) — %s" % order)
    ok(out[0]["chosen_pos_icon"] == "JUNGLE" and out[2]["chosen_pos_icon"] == "BOTTOM",
       "빈칸=인덱스 폴백 · UNSELECTED=firstPositionPreference")

    print("\n[6-1] UNRANKED 도 캐시된다(언랭 방에서 매 폴링 재조회 금지)")
    lcu.summ_by_puuid = {"x1": {"gameName": "언랭맨", "tagLine": ""}}
    lcu.rank_by_puuid = {"x1": {"queues": []}}
    raw = [{"puuid": "x1", "summonerName": "", "gameName": "", "assignedPosition": "TOP"}]
    o1 = ns["_parse_team"](raw, lcu.base, {"Authorization": "x"}, {})
    lcu.reset()
    o2 = ns["_parse_team"](raw, lcu.base, {"Authorization": "x"}, {})
    ok(o1[0]["tier_icon"] == "UNRANKED" and o2[0]["tier_icon"] == "UNRANKED", "UNRANKED 판정 유지")
    ok(len(lcu.calls) == 0, "언랭도 캐시 — 재조회 0회 (%d회)" % len(lcu.calls))


# ────────────── ⑦ 시트 연결 전 fingerprint 미고정 ──────────────
def test_stat_gate(ns):
    print("\n[7] 로비 전적 재계산 게이트")
    g = ns["_lobby_stat_decision"]
    ok(g("A", "", True, None, 0, 100) == "no-sheet",
       "시트 연결 전에는 fingerprint 를 찍지 않는다(연결되면 바로 채움)")
    ok(g("A", "", True, "ws", 0, 100) == "calc", "시트가 붙은 같은 로비는 바로 계산")
    ok(g("A", "A", True, "ws", 0, 100) == "skip", "이미 채운 로비는 다시 계산하지 않는다")
    ok(g("A", "", True, "ws", 200, 150) == "retry-later", "직전 실패 4초 안에는 다시 읽지 않는다")
    ok(g("A", "", False, "ws", 0, 100) == "skip", "새 로스터가 아니면 아무것도 안 한다")

    # 소스 가드 — fingerprint 대입이 'calc' 가지 안에만 있어야 한다(전에는 밖에 있어 버그였다)
    lines = SRC_TEXT.splitlines()
    i_calc = next(i for i, l in enumerate(lines) if l.strip() == 'if _stat_dec == "calc":')
    i_fp = next(i for i, l in enumerate(lines) if l.strip() == "last_lobby_fingerprint = lobby_fingerprint")
    ok(i_fp > i_calc and len(lines[i_fp]) - len(lines[i_fp].lstrip()) > len(lines[i_calc]) - len(lines[i_calc].lstrip()),
       "last_lobby_fingerprint 는 calc 분기 안에서만 찍힌다 (line %d > %d)" % (i_fp + 1, i_calc + 1))


# ────────────── ⑧ 워크시트 객체 캐시 ──────────────
class FakeSpreadsheet:
    def __init__(self, raise_it=False):
        self.n = 0
        self.raise_it = raise_it
        self.sheets = {}

    def worksheet(self, name):
        self.n += 1
        if self.raise_it:
            raise RuntimeError("boom")
        if name not in self.sheets:
            self.sheets[name] = types.SimpleNamespace(title=name)
        return self.sheets[name]


def test_worksheet_cache(ns):
    print("\n[8] worksheet() 메타데이터 GET 제거")
    ss = FakeSpreadsheet()
    objs = [ns["get_worksheet_cached"](ss, "CLASSIC_NORMAL") for _ in range(5)]
    ok(ss.n == 1, "1.2초 폴링 5회에 worksheet() 1회만 (%d회)" % ss.n)
    ok(len({id(o) for o in objs}) == 1, "같은 워크시트 객체를 재사용")
    ok(ns["get_worksheet_cached"](ss, "KIWI_KIWI").title == "KIWI_KIWI", "다른 탭은 따로 조회")

    ss2 = FakeSpreadsheet()
    ns["get_worksheet_cached"](ss2, "CLASSIC_NORMAL")
    ok(ss2.n == 1, "재연결(새 스프레드시트 객체)이면 새로 조회")

    ns["_WS_TTL"] = 0.0
    ns["get_worksheet_cached"](ss, "CLASSIC_NORMAL")
    ok(ss.n == 3, "TTL(10분) 지나면 다시 조회 (%d회)" % ss.n)
    ns["_WS_TTL"] = 600.0

    ok(ns["get_worksheet_cached"](FakeSpreadsheet(raise_it=True), "X") is None,
       "조회 실패는 None → 호출부 기존 폴백 유지")


# ────────────── ⑨ 집계 탭 병렬 로드 ──────────────
def _tables():
    P = [["키", "소환사명", "총판수", "총승", "블루판", "블루승", "레드판", "레드승", "연승", "첫기록"]]
    for i in range(25):
        P.append(["pu%d" % i, "선수%d#KR1" % i, "20", "12", "10", "6", "10", "6", "0", "2026-01-01"])
    C = [["키", "챔피언", "포지션", "판수", "승"]]
    for i in range(25):
        for ch, pos in (("아리", "미드"), ("가렌", "탑"), ("애니", "서폿")):
            C.append(["pu%d" % i, ch, pos, "5", "4"])
    SYN = [["키A", "키B", "진영", "판수", "같은팀승"], ["pu0", "pu1", "블루팀", "12", "4"]]
    NEM = [["키A", "키B", "판수", "A측승"]]
    BAN = [["키", "챔피언", "밴판수", "밴판승"]]
    BANP = [["키", "챔피언", "포지션", "밴판수", "밴판승"]]
    return {"STAT_PLAYER": P, "STAT_CHAMP": C, "STAT_SYNERGY": SYN,
            "STAT_NEMESIS": NEM, "STAT_BAN": BAN, "STAT_BAN_POS": BANP}


def _agg_ns(gviz, tables):
    ns = {
        "concurrent": concurrent,
        "time": time,
        "print": lambda *a, **k: None,
        "gui_data": {},
        "gui_lock": threading.Lock(),
        "FB_POS_ROLES": ("탑", "정글", "미드", "원딜", "서폿"),
        "FB_POS_MIN_GAMES": 10,
        "FB_MIN_BAN_GAMES": 5,
        "FB_MIN_DROP": 0.10,
        "global_alt_map": {},
        "_gviz_tab_csv": gviz,
        "_dedupe_champ_entries": lambda es: [dict(t) for t in {e["name"]: e for e in es}.values()],
        "_fatal_bans_pos_entry": lambda pg, pw, cand: [],
        "_unified_power_one": lambda name, s: 1.0,
    }
    load(ns, "get_main_name")
    load(ns, "_crunch_from_aggregate")
    return ns


def test_crunch_parallel():
    print("\n[9] 집계 탭 6종 병렬 로드")
    tables = _tables()
    calls = []

    def gviz(tab):
        calls.append(tab)
        time.sleep(0.15)
        return tables[tab]

    ns = _agg_ns(gviz, tables)
    blue = [{"puuid": "pu%d" % i, "name": "선수%d#KR1" % i, "chosen_pos_icon": "TOP"} for i in range(5)]
    red = [{"puuid": "pu%d" % i, "name": "선수%d#KR1" % i, "chosen_pos_icon": "BOTTOM"} for i in range(5, 10)]
    t0 = time.time()
    stats, pos, neg, nem = ns["_crunch_from_aggregate"](blue, red)
    dt = time.time() - t0
    ok(sorted(calls) == sorted(tables), "6탭 모두 요청 (%s)" % ",".join(sorted(set(calls))))
    ok(dt < 0.6, "6탭 병렬 로드 %.2fs (직렬이면 6×0.15=0.90s)" % dt)
    ok(len(stats) == 10 and stats["pu0"]["summary"] == "20전 12승 8패 (60.0%)",
       "선수 전적 계산 유지 (%s)" % stats["pu0"]["summary"])
    _most = sorted(e["name"] for e in stats["pu0"]["most_list"])
    ok(_most == sorted(["가렌", "애니", "아리"]), "모스트 챔프 3종 유지 (%s)" % stats["pu0"]["most_list"])
    ok(all(e["count"] == 5 for e in stats["pu0"]["most_list"]), "모스트 판수 집계 유지 (5판)")
    ok(any("❌" not in x and "⚠" in x for x in neg), "같은 팀 승률 낮은 페어 경고 유지 (%s)" % neg[:1])
    ok(ns["gui_data"].get("blue_ban_advice_list") is not None, "밴 추천 목록도 채워진다")

    print("\n[9-1] 필수 탭 실패는 전처럼 예외 → 원본 경로 폴백")
    def gviz_fail(tab):
        if tab == "STAT_PLAYER":
            raise RuntimeError("gviz boom")
        return tables[tab]

    ns2 = _agg_ns(gviz_fail, tables)
    try:
        ns2["_crunch_from_aggregate"](blue, red)
        ok(False, "STAT_PLAYER 실패는 예외로 올라와야 한다")
    except RuntimeError as e:
        ok("boom" in str(e), "STAT_PLAYER 실패 → 예외 전파(폴백) (%s)" % e)

    print("\n[9-2] 표본 부족 판정 유지")
    thin = dict(tables)
    thin["STAT_PLAYER"] = tables["STAT_PLAYER"][:5]     # 4명 → 20명 미만
    ns3 = _agg_ns(lambda tab: (time.sleep(0), thin[tab])[1], thin)
    try:
        ns3["_crunch_from_aggregate"](blue, red)
        ok(False, "표본 부족은 예외여야 한다")
    except RuntimeError as e:
        ok("STAT_PLAYER 표본 부족" in str(e), "표본 20명 미만이면 예외 → 원본 폴백 (%s)" % e)


def main():
    lcu = FakeLCU(delay=0.15)
    ns = make_ns(lcu)
    test_parallel_and_cache(ns, lcu)
    test_edge_rules(ns, lcu)
    test_stat_gate(ns)
    test_worksheet_cache(ns)
    test_crunch_parallel()
    print()
    if FAILED:
        print("FAILED %d건:" % len(FAILED))
        for m in FAILED:
            print("  - " + m)
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
