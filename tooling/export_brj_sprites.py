#!/usr/bin/env python3
"""bot.py 의 브장신 스프라이트(팔레트·스테이지·꾸미기 오버레이·상태 표식)를 index.html 의 BRJ_SPR 로 뽑는다.
봇 쪽 스프라이트가 바뀌면 이걸 다시 돌려 index.html 의 `const BRJ_SPR=...;` 한 줄을 교체한다.
사용: python3 tooling/export_brj_sprites.py ../squad-naejeon-bot/bot.py index.html
"""
import json, random, re, sys
bot, web = sys.argv[1], sys.argv[2]
s = open(bot, encoding="utf-8").read()
a = s.index("SPR_PAL = {"); b = s.index("def _brj_sprite_rows")
ns = {"random": random, "BRJ_ITEMS": {}, "BRJ_ITEM_BY_NAME": {}}
exec(s[a:b], ns)
rows = lambda rs: [("" if set(r) == {"."} else r) for r in rs]
rgb = lambda v: f"rgb({v[0]},{v[1]},{v[2]})"
emb = {"pal": {k: rgb(v) for k, v in ns["SPR_PAL"].items()},
       "stage": {str(k): {"r": rows(v[0]), "g": (rgb(v[1]) if v[1] else None)} for k, v in ns["SPR_STAGE"].items()},
       "cos": {k: {"n": v[1], "e": v[0], "s": v[3], "r": rows(v[4])} for k, v in ns["BRJ_COS"].items()},
       "state": {k: rows(ns[n]) for k, n in (("work", "SPR_WORK"), ("staff", "SPR_STAFF"), ("stun", "SPR_STUN"))}}
js = "const BRJ_SPR=" + json.dumps(emb, ensure_ascii=False, separators=(",", ":")) + ";"
h = open(web, encoding="utf-8").read()
h2, n = re.subn(r"^const BRJ_SPR=.*;$", lambda m: js, h, count=1, flags=re.M)
assert n == 1, "index.html 에 const BRJ_SPR= 줄이 없다"
open(web, "w", encoding="utf-8").write(h2)
print(f"BRJ_SPR 갱신 — 스테이지 {len(emb['stage'])} · 꾸미기 {len(emb['cos'])} · 상태 {len(emb['state'])} · {len(js):,}자")
