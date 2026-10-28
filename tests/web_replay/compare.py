# -*- coding: utf-8 -*-
"""재생 결과 두 벌(replay.py --out 폴더)의 전 선수를 견줘 무엇이 바뀌었는지 보여 준다 — 고치기 전/후 비교용.

  python3 tests/web_replay/compare.py <전 폴더> <후 폴더> [--cat rift]

① 솔랭·십이귀월 칸이 바뀐 선수(이유를 설명할 수 있어야 한다)  ② 그 밖의 power 변화 크기(전체 평균·표준편차가 움직여서 생기는 잔물결)
③ 십이귀월 명단 전/후 표. 설명 못 하는 변화가 있으면 코드 쪽을 의심한다.
"""
import argparse
import json
import os


def load(d, cat):
    with open(os.path.join(d, cat + ".json"), encoding="utf-8") as f:
        return json.load(f)


def compare(b, a):
    B = {p["name"]: p for p in b["players"]}; A = {p["name"]: p for p in a["players"]}
    rep = {"only_before": sorted(set(B) - set(A)), "only_after": sorted(set(A) - set(B)), "visible": [], "ripple": [], "labels": []}
    for n in B:
        if n not in A: continue
        x, y = B[n], A[n]
        d = {k: (x[k], y[k]) for k in ("tier", "title", "solo", "soloCur", "soloTxt", "soloCell") if x[k] != y[k]}
        if d: rep["visible"].append((n, d))
        elif x["power"] is not None and y["power"] is not None and abs(x["power"] - y["power"]) > 1e-9:
            rep["ripple"].append((abs(x["power"] - y["power"]), n))
        if x["label"] != y["label"] or x["implTier"] != y["implTier"]:
            rep["labels"].append((n, x["label"], y["label"], x["implTier"], y["implTier"]))
    rep["ripple"].sort(reverse=True)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before"); ap.add_argument("after"); ap.add_argument("--cat", default="rift")
    a = ap.parse_args()
    b, af = load(a.before, a.cat), load(a.after, a.cat)
    rep = compare(b, af)
    print("== %s — 선수 %d → %d 명 (빠진 %s · 늘어난 %s)" % (a.cat, len(b["players"]), len(af["players"]), rep["only_before"], rep["only_after"]))
    print("-- 솔랭·십이귀월 칸이 바뀐 선수 %d명" % len(rep["visible"]))
    for n, d in rep["visible"]: print("  *", n, d)
    r = rep["ripple"]
    if r: print("-- 그 밖 %d명은 power 만 잔물결(최대 %.4f · 중앙 %.4f)" % (len(r), r[0][0], r[len(r) // 2][0]))
    if rep["labels"]:
        print("-- 평가 라벨·추정티어가 바뀐 선수 %d명" % len(rep["labels"]))
        for x in rep["labels"]: print("  ", x)
    print("-- 십이귀월 명단 (전 → 후)")
    bt = {p["title"]: p for p in b["roster"]}; at = {p["title"]: p for p in af["roster"]}
    for t in [*(f"상현 {i}" for i in range(1, 7)), *(f"하현 {i}" for i in range(1, 7))]:
        x, y = bt.get(t), at.get(t)
        print("  %-6s %-24s → %-24s %s" % (t, x["name"] if x else "-", y["name"] if y else "-", "" if (x and y and x["name"] == y["name"]) else "◀ 바뀜"))


if __name__ == "__main__":
    main()
