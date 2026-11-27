# -*- coding: utf-8 -*-
# 📣 '호출자초대' 단위 테스트 — 봇 /called 조회 → LCU 로비 초대 — `python desktop/called_invite_test.py`
#   실제 함수 소스를 잘라 exec 하고, LCU·HTTP 는 가짜로 바꿔 끼운다(롤 클라이언트 없이 돈다).
import os, sys, json
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py"), encoding="utf-8").read()
i = SRC.index("def _invite_called_members():")
j = SRC.index("def ping_called_at_gamestart")
RES = []
def check(n, c, info=""):
    RES.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (("  — " + str(info)) if info else ""), flush=True)

class _Resp:
    def __init__(s, code=200, obj=None): s.status_code = code; s.ok = code < 400; s._o = obj or {}
    def json(s): return s._o
class _Req:
    def __init__(s, called=None, post_code=200, get_fail=False):
        s.called = called or []; s.post_code = post_code; s.get_fail = get_fail; s.posts = []; s.oks = []
    def get(s, url, timeout=0, **k):
        if s.get_fail: raise RuntimeError("boom")
        s.oks.append(url); return _Resp(200, {"called": s.called, "count": len(s.called)})
    def post(s, url, data=None, headers=None, verify=False, timeout=0, **k):
        s.posts.append(json.loads(data)); return _Resp(s.post_code, {})

def build(called=None, ids=None, me="나#KR1", lcu=True, post_code=200, get_fail=False):
    R = _Req(called, post_code, get_fail)
    ids = ids or {}
    gg = {
        "requests": R, "json": json, "print": lambda *a, **k: None,
        "CALLED_BRIDGE_URL": "https://bot.test/called",
        "_inv_lcu_creds": (lambda: ("https://127.0.0.1:1", {})) if lcu else (lambda: None),
        "_inv_current_riot_id": lambda b, h: me,
        "_inv_resolve_summoner_id": lambda b, h, rid: ids.get(rid),
        "_inv_norm": lambda s_: (s_ or "").replace(" ", "").strip().lower(),
    }
    exec(SRC[i:j], gg)
    return gg["_invite_called_members"], R

# ① 롤 클라이언트 없음
f, _ = build(lcu=False)
ok, msg = f()
check("롤 클라이언트 없으면 안내", ok is False and "League" in msg, msg)

# ② 봇 조회 실패
f, _ = build(get_fail=True)
ok, msg = f()
check("봇 조회 실패 안내", ok is False and "실패" in msg, msg)

# ③ 호출자 없음
f, _ = build(called=[])
ok, msg = f()
check("호출자 없으면 안내", ok is False and "부를 사람이 없" in msg, msg)

# ④ 정상 — 2명 초대
called = [{"riot": "가렌장인#KR1", "name": "가렌장인#KR1"}, {"riot": "리신장인#Teana", "name": "리신장인#Teana"}]
f, R = build(called=called, ids={"가렌장인#KR1": 11, "리신장인#Teana": 22})
ok, msg = f()
check("2명 초대 성공", ok is True and "2명" in msg, msg)
check("LCU 초대 본문 = toSummonerId 2개", R.posts and len(R.posts[0]) == 2
      and {x["toSummonerId"] for x in R.posts[0]} == {11, 22}, R.posts)

# ⑤ 본인은 빼고 초대 / 중복 제거
dup = [{"riot": "나#KR1"}, {"riot": "가렌장인#KR1"}, {"riot": "가렌장인#KR1"}]
f, R = build(called=dup, ids={"나#KR1": 9, "가렌장인#KR1": 11})
ok, msg = f()
check("본인 제외·중복 제거", ok is True and R.posts == [[{"toSummonerId": 11}]], (ok, R.posts))

# ⑥ 일부 미연동 — 성공 + 빠진 사람 안내
f, R = build(called=called, ids={"가렌장인#KR1": 11})
ok, msg = f()
check("일부만 찾으면 성공 + 미발견 안내", ok is True and "1명" in msg and "리신장인" in msg, msg)

# ⑦ 전부 미연동 → 실패 안내(초대 안 보냄)
f, R = build(called=called, ids={})
ok, msg = f()
check("전부 미연동이면 실패 안내·초대 없음", ok is False and not R.posts and "찾지 못했" in msg, msg)

# ⑧ 롤이 초대 거부(로비 없음 등)
f, R = build(called=called, ids={"가렌장인#KR1": 11, "리신장인#Teana": 22}, post_code=400)
ok, msg = f()
check("HTTP 400 → 거부 안내", ok is False and "400" in msg and "로비" in msg, msg)

# ⑨ riot 없는 항목은 조용히 무시
f, R = build(called=[{"riot": ""}, {"name": "x"}], ids={})
ok, msg = f()
check("riot 비면 호출자 없음으로 처리", ok is False, msg)

print()
print(f"{sum(RES)}/{len(RES)} 통과")
sys.exit(0 if all(RES) and len(RES) >= 9 else 1)
