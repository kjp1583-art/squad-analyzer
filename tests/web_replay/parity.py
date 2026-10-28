# -*- coding: utf-8 -*-
"""웹 ↔ 툴링 ↔ 분석기 동일성 점검 — 같은 시트 스냅샷(xlsx)으로 세 구현이 같은 값을 내는지 본다.

  python3 tests/web_replay/parity.py --xlsx <시트.xlsx> [--src index.html] [--master <마스터티어표.txt>] [--now 2026-10-09T15:00:00]

  ① 솔랭 지도(SOLO_RANKS) — 웹 blendSoloRanks 결과 = 툴링 sibguiwol.load 의 solo = 분석기 _load_solo_ranks 결과 (닉 키마다 점수·승·패)
  ② 십이귀월 명단 — 웹(협곡) 상현6·하현6 = 툴링 compute (이름·순서 같아야 하고 power 는 0.02 안)
산식·분모(elig)·솔랭 후보 규칙은 CLAUDE.md 「십이귀월은 세 군데가 같이 움직인다」 — 어긋나면 이 점검이 먼저 알려 준다. 종료코드 0 = 일치.
"""
import argparse
import asyncio
import csv
import datetime as dt
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for p in (HERE, os.path.join(ROOT, "desktop"), os.path.join(ROOT, "tooling")):
    if p not in sys.path: sys.path.insert(0, p)
import gviz  # noqa: E402
import replay  # noqa: E402
import sibguiwol  # noqa: E402
import solo_link_chain_test as slc  # noqa: E402


def _s(v):
    """gspread get_all_values 처럼 칸 값을 보이는 글자로"""
    if v is None: return ""
    if isinstance(v, float) and v == int(v): return str(int(v))
    return str(v)


def snap(d):
    """{키: 엔트리} -> {키(.0 뗌): (점수 4자리, 승, 패)}  — xlsx 에서 숫자만으로 된 닉이 '12345.0' 꼴로 읽히는 툴링 쪽 별개 문제는 비교에서 뗀다"""
    return {re.sub(r"\.0$", "", k): (round(v["score"], 4), v["wins"], v["losses"]) for k, v in d.items()}


def analyzer_solo_map(xlsx):
    """분석기 _load_solo_ranks 를 가짜 시트로 돌린다 — SOLO_RANK·PEAK_SEASONS·LINK_ACCOUNT 만 필요"""
    tabs = gviz.load_xlsx(xlsx, only={"SOLO_RANK", "PEAK_SEASONS", "LINK_ACCOUNT"})
    rows = lambda n: [[_s(c) for c in r] for r in tabs.get(n, ([], []))[0]]
    ns = slc.load_ns()
    ns["global_spreadsheet"] = slc._SS(rows("SOLO_RANK"))
    buf = io.StringIO(); wr = csv.writer(buf)
    for r in rows("PEAK_SEASONS"): wr.writerow(r)
    ns["_fetch_public_csv"] = lambda *a, **k: buf.getvalue()
    ns["_PEAK_SEASONS_CACHE"] = None
    ns["global_alt_map"] = {}
    for r in rows("LINK_ACCOUNT")[1:]:                     # 분석기 부팅과 같은 방식·같은 순서
        if len(r) >= 2 and r[0].strip() and r[1].strip(): ns["global_alt_map"][r[1].strip().split("#")[0].lower()] = r[0].strip()
    return ns["_load_solo_ranks"]()


def diff_maps(a, b, an="A", bn="B"):
    out = {}
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k): out[k] = {an: a.get(k), bn: b.get(k)}
    return out


def diff_roster(tool, web, tol=0.02):
    out = []
    t = [(r["title"], r["name"]) for r in tool]; w = [(r["title"], r["name"]) for r in web]
    if t != w: out.append({"툴링": t, "웹": w})
    for a, b in zip(tool, web):
        if a["name"] == b["name"] and abs(a["power"] - b["power"]) > tol: out.append({"power 차이": (a["name"], a["power"], b["power"])})
    return out


def check(xlsx, src, master=None, now=None, today=None, quiet=True):
    """세 구현을 같은 xlsx 로 돌려 불일치를 모아 돌려준다."""
    web = asyncio.run(replay.replay(src, xlsx=xlsx, master=master, now=now, cats=("rift",), shots=False, quiet=quiet))
    web_solo = snap(web["rift"]["solo"])
    tool_solo = snap(sibguiwol.load(xlsx)[3])
    an_solo = snap(analyzer_solo_map(xlsx))
    tool_roster = sibguiwol.compute(xlsx, today=today)
    rep = {"솔랭 웹≠툴링": diff_maps(web_solo, tool_solo, "웹", "툴링"),
           "솔랭 웹≠분석기": diff_maps(web_solo, an_solo, "웹", "분석기"),
           "명단 웹≠툴링": diff_roster(tool_roster, web["rift"]["roster"]),
           "키 수": (len(web_solo), len(tool_solo), len(an_solo))}
    return rep, web


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--src", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--master")
    ap.add_argument("--now", help="웹 시계 고정(한국 시각, 예 2026-10-09T15:00:00) — 툴링의 today 도 같은 날로")
    a = ap.parse_args()
    today = dt.datetime.fromisoformat(a.now).date() if a.now else None
    rep, web = check(a.xlsx, a.src, a.master, a.now, today, quiet=False)
    bad = 0
    print("솔랭 지도 키 수 (웹/툴링/분석기):", rep["키 수"])
    for k in ("솔랭 웹≠툴링", "솔랭 웹≠분석기", "명단 웹≠툴링"):
        v = rep[k]
        print("%-14s %s" % (k, "일치" if not v else "불일치 %d건: %s" % (len(v), v)))
        bad += bool(v)
    replay.print_roster(web)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
