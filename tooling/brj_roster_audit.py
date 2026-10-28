#!/usr/bin/env python3
"""🍗 브장신 까메오 명단 점검 — 시트 스냅샷으로 「지금 활동 중인 클랜원」을 뽑고, 봇 bot.py 의 BRJ_CAMEOS 에 나오는 사람이
최근에도 뛰는지 알려 준다(2026-10-28 사장님 「브장신키우기에 등장하는 클랜원명단 최신화」).
사용: python3 tooling/brj_roster_audit.py --xlsx <squad_sheet.xlsx> --bot <bot.py> [--days 30] [--min 3]
  · 낡은 사람(최근 N일 내전 min판 미만이거나 DEPARTED)을 한 줄씩 · 아직 까메오가 없는 활발한 사람 상위 15명을 보여 준다.
  · 스냅샷은 ai-eval-data 브랜치의 squad_sheet.xlsx. 봇 쪽에서 고치는 곳: bot.py `BRJ_CAMEOS` · `_brj_names` 의 base 목록."""
import argparse, collections, datetime, re
import openpyxl
def tn(s): return re.sub(r"\s+", "", str(s or "")).split("#")[0].lower()
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--xlsx", required=True); ap.add_argument("--bot", required=True)
    ap.add_argument("--days", type=int, default=30); ap.add_argument("--min", type=int, default=3); a = ap.parse_args()
    wb = openpyxl.load_workbook(a.xlsx, read_only=True, data_only=True)
    it = wb["CLASSIC_NORMAL"].iter_rows(values_only=True); h = next(it); ix = {k: i for i, k in enumerate(h)}
    rows = [r for r in it if r and r[ix["소환사명"]] and r[ix["날짜"]]]
    last = max(str(r[ix["날짜"]])[:10] for r in rows); today = datetime.date.fromisoformat(last)
    cut = str(today - datetime.timedelta(days=a.days))
    g = collections.Counter(); disp = {}
    for r in rows:
        k = tn(r[ix["소환사명"]]); disp.setdefault(k, str(r[ix["소환사명"]]).split("#")[0].strip())
        if str(r[ix["날짜"]])[:10] >= cut: g[k] += 1
    dep = set()
    try:
        dh = wb["DEPARTED"].iter_rows(values_only=True); next(dh); dep = {tn(r[0]) for r in dh if r and r[0]}
    except Exception: pass
    src = open(a.bot, encoding="utf-8").read(); s0 = src.index("BRJ_CAMEOS = ["); s1 = src.index("\n]\n", s0)
    subs = sorted(set(re.findall(r'^\s*\("([^"]+)",\s*"', src[s0:s1], re.M)))
    npc = {"브장신", "운영진", "카톡방", "QNA봇"}
    have = set(); stale = []
    for nm in subs:
        if nm in npc: continue
        k = tn(nm); cand = [c for c in g.keys() | set(disp) if c == k or (len(k) >= 2 and (c.startswith(k) or k.startswith(c)))]
        best = max(cand, key=lambda c: g[c]) if cand else None
        if best is None: print(f"? {nm} — 시트에서 못 찾음(밈 문구거나 닉변)"); continue
        have.add(best)
        if g[best] < a.min: stale.append(nm); print(f"✗ {nm} — 최근 {a.days}일 {g[best]}판{' · DEPARTED 표에도 있음' if best in dep else ''} → 명단에서 뺄 것")
        elif best in dep: print(f"⚠ {nm} — DEPARTED 표에 같은 이름이 있지만 최근 {a.days}일 {g[best]}판 뜀(재가입·동명이 확인 필요 · 빼지 않음)")
    print(f"\n점검 기준일 {last} · 낡은 까메오 {len(stale)}명")
    print("아직 까메오가 없는 활발한 사람 상위 15:", ", ".join(f"{disp[k]}({n})" for k, n in g.most_common(60) if k not in have and k not in dep)[:600].split(", ")[:15])
if __name__ == "__main__": main()
