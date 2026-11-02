"""대기실 랜덤 한 줄에 브장신 키우기 얘기가 안 나온다(2026-11-02 사장님 지시)."""
import os, re, random, time, sys
s = open(os.path.join(os.path.dirname(__file__), "squad_analyzer.py"), encoding="utf-8").read()
i = s.index("LOBBY_FUN_MAX = 70"); j = s.index("def _lobby_intro_ready")
g = {"random": random, "time": time, "requests": None}
exec(s[i:j], g)
g["_clanstat_meta"] = lambda: None
g["_weekly_data"] = lambda: {"stats": {"raid": {"n": 5, "w": 3}, "sr": {"games": 10, "players": 20}}, "facts": [], "awards": [{"title": "브장신 왕", "name": "x"}]}
bad = [o for o in {g["_lobby_fun_line"]() for _ in range(3000)} if g["_LOBBY_FUN_BAN"].search(o)]
print("PASS 브장신 관련 문구 없음" if not bad else f"FAIL {bad}"); sys.exit(1 if bad else 0)
