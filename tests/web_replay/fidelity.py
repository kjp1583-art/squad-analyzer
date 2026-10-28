# -*- coding: utf-8 -*-
"""xlsx 스냅샷에서 만든 gviz 응답이 실제 구글 응답(fetch_gviz.py 로 받은 폴더)과 칸 단위로 같은지 대조한다.

  python3 tests/web_replay/fidelity.py --xlsx <시트.xlsx> --gviz-dir <실제응답폴더>

두 스냅샷 사이에 시트가 바뀐 칸(예: PERKS·UNIQ_MARKET 의 갱신 시각 JSON)은 차이로 나온다 — 변환 오류와 구분해 볼 것.
종료코드 0 = 모든 탭에서 열 종류·행 수·칸 값이 같다(시각이 흐르며 바뀌는 탭 제외는 사람이 판단).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gviz  # noqa: E402


def norm_cell(c):
    if c is None: return None
    v = c.get("v")
    return None if v is None or v == "" else (v, c.get("f"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", required=True); ap.add_argument("--gviz-dir", required=True)
    a = ap.parse_args()
    tabs = gviz.load_xlsx(a.xlsx)
    real = gviz.load_gviz_dir(a.gviz_dir)
    bad = 0
    for name, r in sorted(real.items()):
        if name not in tabs: print("%-16s xlsx 에 없음" % name); bad += 1; continue
        rows, fmts = tabs[name]
        mine = gviz.table_from_rows(rows, fmts)
        rc, mc = r["table"]["cols"], mine["table"]["cols"]
        colerr = [(x.get("label"), x["type"], y["type"]) for x, y in zip(rc, mc) if (x["type"], x.get("label")) != (y["type"], y.get("label"))]
        rr, mr = r["table"]["rows"], mine["table"]["rows"]
        diffs, ex = 0, []
        for i in range(min(len(rr), len(mr))):
            for j in range(min(len(rc), len(mc))):
                x = norm_cell(rr[i]["c"][j] if j < len(rr[i]["c"]) else None); y = norm_cell(mr[i]["c"][j] if j < len(mr[i]["c"]) else None)
                if x != y:
                    diffs += 1
                    if len(ex) < 2: ex.append((i, rc[j]["label"], str(x)[:60], str(y)[:60]))
        ok = not colerr and len(rc) == len(mc) and len(rr) == len(mr) and diffs == 0
        bad += not ok
        print("%-16s %s  열 %d/%d · 행 %d/%d · 다른 칸 %d %s %s" % (name, "일치" if ok else "차이", len(rc), len(mc), len(rr), len(mr), diffs, colerr[:2], ex))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
