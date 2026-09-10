#!/usr/bin/env python3
"""bot.py 의 브장신 정적 테이블(진화 단계·스킬·대사·시나리오·아이템·장비·꾸미기)을 index.html 의 const BRJ_* 줄로 뽑는다.
봇 쪽 표가 바뀌면 이걸 다시 돌려 index.html 의 해당 줄을 통째로 교체한다(스프라이트는 export_brj_sprites.py).
사용: python3 tooling/export_brj_tables.py ../squad-naejeon-bot/bot.py index.html
"""
import json, os, re, sys
bot, web = sys.argv[1], sys.argv[2]
s = open(bot, encoding="utf-8").read()
def seg(start, end):
    a = s.index(start); b = s.index(end, a); return s[a:b]
ns = {}
exec(seg("BRJ_STAGES = [", "BRJ_LEGEND_LV ="), ns)
exec(seg("BRJ_SKILLS = {", "BRJ_LINES_RARE ="), ns)
exec(seg("BRJ_LINES_RARE = [", "_BRJ_ANN ="), ns)
exec(seg("BRJ_LINES = [", "\n]\n") + "\n]\n", ns)
exec(seg("BRJ_STATS = {", "\n"), ns)
exec(seg("BRJ_ITEMS = {", "# ---- ⚔ 장비"), ns)                      # BRJ_ITEMS + 뒤이어 붙는 staffcard·tale 까지
exec(seg("BRJ_GEAR = {", "BRJ_SLOT_NM ="), ns)
exec(seg("BRJ_SLOT_NM = {", "\n"), ns)
exec(seg("BRJ_GEAR_FX = {", "\n}\n") + "\n}\n", ns)
ns["_spr_rows"] = lambda d: d
exec(seg("BRJ_COS = {", "\n}\n") + "\n}\n", ns)
# 시나리오: (id, 제목 "N부 N막 — 제목", lv, 조건 lambda, ...) — 조건은 소스 문장을 읽어 사람 말로
camp_src = seg("BRJ_CAMPAIGN = [", "\n]\n")
camp = []
for m in re.finditer(r'^    \("([a-z0-9]+)", "([^"]+)", (\d+), (None|lambda r: [^\n]*?),\n', camp_src, re.M):
    _id, title, lv, cond = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    no, _, t = title.partition(" — ")
    c = ""
    if cond != "None":
        mm = re.search(r'"eat_n".*?>= (\d+)', cond); c = f"먹이 {mm.group(1)}회" if mm else c
        mm = re.search(r'"q_done_n".*?>= (\d+)', cond); c = f"주간 퀘스트 {mm.group(1)}개" if mm else c
        mm = re.search(r'\("wi", "sa", "no"\)\) >= (\d+)', cond); c = f"능력치 총합 {mm.group(1)}" if mm else c
        mm = re.search(r'"shard".*?>= (\d+)', cond); c = f"🧩 트로피 조각 {mm.group(1)}개" if mm else c
        if not c: c = "조건 있음"
    camp.append([no, t, lv, c])
stat_nm = {k: v[1] for k, v in ns["BRJ_STATS"].items()}
def stat_txt(d): return " ".join(f"{stat_nm[k]}{'+' if v > 0 else ''}{v}" for k, v in d.items())
slot = ns["BRJ_SLOT_NM"]; cslot = {"h": "모자", "o": "의상", "a": "장신구"}
out = {
    "BRJ_STAGES": [[xp, em, nm] for xp, em, nm, _l in ns["BRJ_STAGES"]],
    "BRJ_SKILLS": {str(k): [v[0], v[1]] for k, v in ns["BRJ_SKILLS"].items()},
    "BRJ_LINES": list(dict.fromkeys(ns["BRJ_LINES"] + ns["BRJ_LINES_RARE"])),
    "BRJ_CAMP": camp,
    "BRJ_ITEMS": [[v[0], v[1], v[2], v[3]] for v in ns["BRJ_ITEMS"].values()],
    "BRJ_GEAR": [[v[0], v[1], v[2], slot[v[3]], stat_txt(v[4]), ns["BRJ_GEAR_FX"].get(k, v[5])] for k, v in ns["BRJ_GEAR"].items()],
    "BRJ_COS": [[v[0], v[1], v[2], cslot[v[3]], v[5]] for v in ns["BRJ_COS"].values()],
    "BRJ_STAT_NM": stat_nm,
}
h = open(web, encoding="utf-8").read()
for k, v in out.items():
    js = f"const {k}=" + json.dumps(v, ensure_ascii=False, separators=(",", ":")) + ";"
    h, n = re.subn(rf"^const {k}=.*;$", lambda m: js, h, count=1, flags=re.M)
    if n != 1:                                     # 없던 상수는 BRJ_COS 줄 뒤에 추가
        h = h.replace("\nconst BRJ_COS=", "\nconst BRJ_COS=", 1)
        h = re.sub(r"^(const BRJ_COS=.*;)$", lambda m: m.group(1) + "\n" + js, h, count=1, flags=re.M)
    print(f"{k}: {len(v)}")
open(web, "w", encoding="utf-8").write(h)
# 🍘 맛동산 상점(브장신 소개 페이지 brjang.html) — MD_SHOP + BRJ_ITEMS 에서
try:
    exec(seg("MD_UNIT = ", "MD_SHOP_BY ="), ns)          # MD_UNIT(1만원당 개수) + MD_SHOP
    unit = int(ns.get("MD_UNIT") or 1)
    shop = [[ns["BRJ_ITEMS"][ik][0], ns["BRJ_ITEMS"][ik][1], n, pr, bl] for k, pr, ik, n, bl in ns["MD_SHOP"]]
    bp = os.path.join(os.path.dirname(os.path.abspath(web)), "brjang.html")
    b = open(bp, encoding="utf-8").read()
    b2, n2 = re.subn(r"^const BRJ_MDSHOP=.*;$", lambda m: "const BRJ_MDSHOP=" + json.dumps(shop, ensure_ascii=False, separators=(",", ":")) + ";", b, count=1, flags=re.M)
    # 가격표 블록(.items) + 환율 문구 — 봇의 MD_SHOP/MD_UNIT 이 SSOT
    def _won(pr):
        w = pr / unit
        return f"{w:g}만원" if w >= 1 else f"{int(round(w * 10000)):,}원"
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    items = "".join(f'<div class="item"><div class="ic">{ic}</div><div><h4>{esc(nm)}{f" ×{n}" if n > 1 else ""}</h4><p>{esc(bl)}</p><span class="pr">🍘 맛동산 {pr}개 = {_won(pr)}</span></div></div>' for ic, nm, n, pr, bl in shop)
    b2, n3 = re.subn(r'<div class="items">.*?</div></div></div>\n', '<div class="items">' + items + "</div>\n", b2, count=1, flags=re.S)
    b2 = re.sub(r'<div class="amt">1만원<small> = 🍘 맛동산 \d+개</small></div>', f'<div class="amt">1만원<small> = 🍘 맛동산 {unit}개</small></div>', b2, count=1)
    b2 = re.sub(r"1만원 단위로 후원합니다\. 2만원이면 맛동산 \d+개\.", f"1만원 단위로 후원합니다. 2만원이면 맛동산 {unit * 2}개.", b2, count=1)
    if n2: open(bp, "w", encoding="utf-8").write(b2); print(f"BRJ_MDSHOP: {len(shop)} · 가격표 {n3} · 1만원={unit}개 (brjang.html)")
except Exception as e: print("brjang.html 갱신 생략:", e)
