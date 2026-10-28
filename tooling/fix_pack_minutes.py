#!/usr/bin/env python3
"""지표 팩의 m 이 분당 CS 로 기록된 판을 진짜 게임 시간(분)으로 되돌린다(2026-10-10 사장님 지시 「시트 원본도 고쳐줘」).

제보(2026-10-10): 웹 명예의 전당 「분당 데미지(DPM)」에서 일단즐겨 서폿(58판 평균)이 2위 — 실제 서폿 평균은 628.
원인: 2026-09-19·09-22 다섯 판(#8387155519 #8387222960 #8387316403 #8390902575 #8391010034, 50행)의 지표 팩은
m 칸에 게임 시간(분)이 아니라 **분당 CS** 가 들어 있었다. 선수마다 m 이 달랐고(0.86 · 6.6 · 9.45 …) cs÷m 은 판마다
같은 값(26.67 · 24.2 · 31.43 · 37.42 · 35.42)이었다 — 그게 진짜 게임 시간이다.
웹(index.html parseMetrics)과 분석기(_fix_pack_minutes)는 읽을 때 같은 규칙으로 되돌려 쓰고 있다 — 이 도구는 시트 값 자체를 고친다.

판정(보수적으로 — 애매하면 고치지 않고 목록만 남긴다):
  · 후보 = 그 판의 어떤 행이 cs÷m > 14 (분당 CS 는 12.4 를 넘을 수 없다 — 정상 행 14,947개 중 최대).
  · 고치는 조건 = ① 지표가 있는 행이 8개 이상 ② cs ≥ 100 인 행 5개 이상에서 cs÷m 이 ±1% 안에서 같다
    ③ 그 값(=게임 시간 M)이 8~90분 ④ cs < 100 인 행도 M 의 ±3% 안(반올림 오차)이고 ⑤ cs 가 비었거나 0 인 행이 없다.
    하나라도 어긋나면 그 판은 건드리지 않고 「보류」 로 남긴다.
  · 고치는 값 = 그 판 모든 행의 m 을 M 한 값(소수 한 자리, 분석기가 쓰는 서식 m26.7)으로. 팩의 다른 토큰은 그대로, **지표 칸만** 바꾼다.
  · 쓰기 전 칸의 현재 값이 계획과 같은지 다시 확인하고(그 사이 누가 고쳤으면 건너뜀), 쓴 뒤 다시 읽어 검증한다.

기본은 미리보기(dry-run). 실제 수정은 APPLY=1 일 때만. 로그에는 닉네임·PUUID 를 찍지 않는다(공개 저장소 Actions 로그) — 행 번호·게임ID·값만.
되돌릴 때를 위해 BACKUP_JSON 한 줄(행·옛 값·새 값)을 로그와 tooling/fix_pack_minutes_backup.json 에 남긴다.

로컬 점검: python3 tooling/fix_pack_minutes.py --gviz <탭>.json   (gviz 응답 파일 — 시트 접속 없이 미리보기)
           python3 tooling/fix_pack_minutes.py --xlsx 시트.xlsx
"""
import base64, collections, json, os, re, statistics, sys, time

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
TABS = ("CLASSIC_NORMAL", "KIWI_KIWI", "LOL_CLASSIC")
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

CSPM_MAX = 14.0          # 이보다 높은 cs÷m 은 분당 CS 일 수 없다(m 이 분당 CS 로 들어간 행)
MIN_ROWS = 8             # 지표가 있는 행 수 하한(한 판 10명 중)
MIN_CARRY = 5            # cs ≥ 100 인 행 수 하한 — 이 행들의 cs÷m 이 같아야 한다
CARRY_CS = 100
CARRY_BAND = 0.01        # cs ≥ 100 행의 cs÷m 허용 폭(±1%)
LOW_BAND = 0.03          # cs < 100 행의 허용 폭(±3% — m 이 소수 둘째 자리라 반올림 오차가 크다)
M_MIN, M_MAX = 8.0, 90.0


def split_pack(s):
    """'g7631|cs23|m0.86|…' → 토큰 리스트(원문 그대로)."""
    return str(s or "").split("|")


def pack_values(s):
    o = {}
    for t in split_pack(s):
        m = re.match(r"^([a-z]+)(-?\d+(?:\.\d+)?)$", t.strip())
        if m: o[m.group(1)] = float(m.group(2))
    return o


def rewrite_m(s, new_m):
    """m 토큰 하나만 새 값으로 — 나머지 토큰은 원문 그대로."""
    out, hit = [], 0
    for t in split_pack(s):
        if re.match(r"^m-?\d+(?:\.\d+)?$", t.strip()):
            out.append("m%.1f" % new_m); hit += 1
        else:
            out.append(t)
    return "|".join(out) if hit == 1 else None


def plan_tab(vals):
    """시트 값 배열(첫 행 = 머리글) → (fixes, held, 판수)
    fixes: [{'game','date','m','rows':[{'row','old','new'}…]}]   held: [(game, date, 이유)]"""
    if not vals: return [], [], 0
    idx = {c: i for i, c in enumerate(vals[0])}
    if "게임ID" not in idx or "지표" not in idx: return [], [], 0
    gI, pI, dI = idx["게임ID"], idx["지표"], idx.get("날짜", -1)
    games = collections.OrderedDict()
    for rn, r in enumerate(vals[1:], start=2):
        pack = r[pI] if pI < len(r) else ""
        if not pack or pack == "기록 대기": continue
        gid = str(r[gI]).strip() if gI < len(r) else ""
        if not gid: continue
        games.setdefault(gid, []).append((rn, str(pack), (str(r[dI])[:16] if 0 <= dI < len(r) else "")))
    fixes, held = [], []
    for gid, rs in games.items():
        parsed = [(rn, pack, date, pack_values(pack)) for rn, pack, date in rs]
        bad = [p for p in parsed if p[3].get("cs", 0) > 0 and p[3].get("m", 0) > 0 and p[3]["cs"] / p[3]["m"] > CSPM_MAX]
        if not bad: continue
        date = parsed[0][2]
        if len(parsed) < MIN_ROWS:
            held.append((gid, date, "지표가 있는 행이 %d개뿐" % len(parsed))); continue
        if any(not (p[3].get("cs", 0) > 0 and p[3].get("m", 0) > 0) for p in parsed):
            held.append((gid, date, "cs 나 m 이 비었거나 0 인 행이 있음")); continue
        ratios = [p[3]["cs"] / p[3]["m"] for p in parsed if p[3]["cs"] >= CARRY_CS]
        if len(ratios) < MIN_CARRY:
            held.append((gid, date, "cs≥%d 행이 %d개뿐" % (CARRY_CS, len(ratios)))); continue
        M = statistics.median(ratios)
        if max(ratios) / min(ratios) - 1 > 2 * CARRY_BAND or any(abs(x / M - 1) > CARRY_BAND for x in ratios):
            held.append((gid, date, "cs÷m 이 행마다 같지 않음(%.2f~%.2f)" % (min(ratios), max(ratios)))); continue
        if not (M_MIN <= M <= M_MAX):
            held.append((gid, date, "되돌린 게임 시간 %.1f분이 정상 범위 밖" % M)); continue
        off = [p for p in parsed if abs(p[3]["cs"] / p[3]["m"] / M - 1) > (CARRY_BAND if p[3]["cs"] >= CARRY_CS else LOW_BAND)]
        if off:
            held.append((gid, date, "게임 시간과 안 맞는 행 %d개(cs÷m %s)" % (len(off), ",".join("%.1f" % (p[3]["cs"] / p[3]["m"]) for p in off[:3])))); continue
        rows = []
        for rn, pack, _d, _v in parsed:
            new = rewrite_m(pack, M)
            if new is None:
                held.append((gid, date, "%d행 m 토큰을 못 찾음" % rn)); rows = None; break
            rows.append({"row": rn, "old": pack, "new": new})
        if rows is None: continue
        fixes.append({"game": gid, "date": date, "m": round(M, 1), "rows": rows, "ratio": (min(ratios), max(ratios))})
    return fixes, held, len(games)


def _retry(label, fn, tries=5):
    for i in range(tries):
        try: return fn()
        except Exception:
            if i == tries - 1: raise
            wait = 30 * (2 ** i)
            print(f"  ! {label} 실패 — {wait}s 후 재시도", flush=True)
            time.sleep(wait)


def load_local(argv):
    """--gviz 파일(들) 또는 --xlsx → {탭: 값 배열}"""
    tabs = {}
    if "--xlsx" in argv:
        import openpyxl
        wb = openpyxl.load_workbook(argv[argv.index("--xlsx") + 1], read_only=True, data_only=True)
        for t in TABS:
            if t in wb.sheetnames:
                tabs[t] = [[("" if c is None else c) for c in r] for r in wb[t].values]
    if "--gviz" in argv:
        for path in argv[argv.index("--gviz") + 1:]:
            if path.startswith("--"): break
            txt = open(path, encoding="utf-8").read()
            d = json.loads(txt[txt.index("(") + 1: txt.rindex(")")])
            cols = [c["label"] for c in d["table"]["cols"]]
            rows = [cols] + [[("" if (cell is None or cell.get("v") is None) else cell["v"]) for cell in r["c"]] for r in d["table"]["rows"]]
            tabs[os.path.basename(path).split(".")[0]] = rows
    return tabs


def report(tab, fixes, held, ngames):
    print(f"\n[{tab}] 지표 있는 판 {ngames}개 중 고칠 판 {len(fixes)}개 · 보류 {len(held)}개")
    for f in fixes:
        print(f"  · {f['game']} ({f['date']}) — {len(f['rows'])}행, 게임 시간 {f['m']}분 (cs÷m {f['ratio'][0]:.2f}~{f['ratio'][1]:.2f})")
        for x in f["rows"]:
            om = re.search(r"\|m(-?[\d.]+)", "|" + x["old"]); nm = re.search(r"\|m(-?[\d.]+)", "|" + x["new"])
            print(f"      {x['row']}행 m {om.group(1) if om else '?'} → {nm.group(1) if nm else '?'}")
    for gid, date, why in held:
        print(f"  ? {gid} ({date}) 보류 — {why}")


def main():
    argv = sys.argv[1:]
    local = load_local(argv) if ("--xlsx" in argv or "--gviz" in argv) else None
    ss = None
    if local is None:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        raw = os.environ.get("CREDENTIALS_JSON_B64", "")
        if not raw:
            print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
        open("creds.json", "wb").write(base64.b64decode(raw))
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
        ss = _retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))
    plans, wss = {}, {}
    titles = {} if local is not None else {w.title: w for w in _retry("탭 목록", ss.worksheets)}   # 없는 탭은 재시도 없이 건너뛴다(재시도 대기가 수 분)
    for tab in (local.keys() if local is not None else TABS):
        if local is not None:
            vals = local[tab]
        else:
            if tab not in titles:
                print(f"\n[{tab}] 탭 없음 — 건너뜀"); continue
            wss[tab] = titles[tab]
            vals = _retry(f"{tab} 읽기", wss[tab].get_all_values)
        fixes, held, ng = plan_tab(vals)
        plans[tab] = (fixes, held, vals)
        report(tab, fixes, held, ng)
    total = sum(len(f["rows"]) for fixes, _h, _v in plans.values() for f in fixes)
    nheld = sum(len(h) for _f, h, _v in plans.values())
    backup = [{"tab": tab, "game": f["game"], "row": x["row"], "old": x["old"], "new": x["new"]}
              for tab, (fixes, _h, _v) in plans.items() for f in fixes for x in f["rows"]]
    print("\nBACKUP_JSON " + json.dumps(backup, ensure_ascii=False, separators=(",", ":")))
    if not total:
        print("\n고칠 행 없음."); return 0
    if local is not None:
        print(f"\n수정 대상 — {total}행 (로컬 미리보기라 시트는 건드리지 않음)"); return 0
    if os.environ.get("APPLY") != "1":
        print(f"\n수정 대상 — {total}행 · 보류 {nheld}개 (APPLY=1 이어야 실제 반영)"); return 0
    import gspread
    done = skipped = 0
    for tab, (fixes, _h, vals) in plans.items():
        if not fixes: continue
        ws = wss[tab]
        pI = vals[0].index("지표")
        cur = _retry(f"{tab} 지표 칸 다시 읽기", lambda: ws.col_values(pI + 1))
        cells, expect = [], {}
        for f in fixes:
            for x in f["rows"]:
                now = cur[x["row"] - 1] if x["row"] - 1 < len(cur) else ""
                if now != x["old"]:
                    skipped += 1; print(f"  ! {tab} {x['row']}행({f['game']}) 값이 계획 때와 달라 건너뜀")
                    continue
                cells.append(gspread.Cell(row=x["row"], col=pI + 1, value=x["new"])); expect[x["row"]] = x["new"]
        if not cells: continue
        _retry(f"{tab} 지표 수정", lambda: ws.update_cells(cells, value_input_option="RAW"))
        after = _retry(f"{tab} 지표 칸 검증 읽기", lambda: ws.col_values(pI + 1))
        bad = [r for r, v in expect.items() if (after[r - 1] if r - 1 < len(after) else "") != v]
        if bad:
            print(f"  !! {tab} 검증 실패 {len(bad)}행: {bad[:10]}"); return 2
        done += len(cells)
        print(f"  ✔ {tab} {len(cells)}행 수정·검증 완료")
    print(f"\n수정 완료 — {done}행 (건너뜀 {skipped})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
