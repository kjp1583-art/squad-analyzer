#!/usr/bin/env python3
"""소환사명 자리에 챔피언 이름이 들어간 행을 실제 닉네임으로 되돌린다(2026-07-29 사장님 제보).

라이브 로스터가 덜 로드된 순간에 기록되면 소환사명이 챔피언 이름으로 채워지는 경우가 있다.
PUUID는 정상이므로, 같은 PUUID의 정상 행(닉#태그)에서 이름을 가져와 덮어쓴다.
정상 이름을 못 찾은 행은 건드리지 않고 목록만 알린다(임의 추측 금지).

기본은 미리보기(dry-run). 실제 수정은 APPLY=1 일 때만.
"""
import base64, os, sys, time
from collections import Counter, defaultdict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
TABS = ("CLASSIC_NORMAL", "KIWI_KIWI")
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


def _retry(label, fn, tries=5):
    for i in range(tries):
        try: return fn()
        except Exception as e:
            if i == tries - 1: raise
            wait = 30 * (2 ** i)
            print(f"  ! {label} 실패({type(e).__name__}) — {wait}s 후 재시도", flush=True)
            time.sleep(wait)


def main():
    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw:
        print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
    open("creds.json", "wb").write(base64.b64decode(raw))
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
    ss = _retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))

    # 1단계 — 두 탭 전체에서 PUUID → 정상 닉네임(가장 많이 쓰인 것) 사전을 만든다.
    sheets, name_of = {}, defaultdict(Counter)
    for tab in TABS:
        try: ws = _retry(f"{tab} 열기", lambda tab=tab: ss.worksheet(tab))
        except Exception:
            print(f"  · {tab}: 탭 없음 — 건너뜀"); continue
        vals = _retry(f"{tab} 읽기", ws.get_all_values)
        idx = {c: i for i, c in enumerate(vals[0])}
        if "소환사명" not in idx or "PUUID" not in idx:
            print(f"  · {tab}: 필요한 열 없음 — 건너뜀"); continue
        sheets[tab] = (ws, vals, idx)
        for r in vals[1:]:
            if len(r) <= max(idx["소환사명"], idx["PUUID"]): continue
            nm, pu = r[idx["소환사명"]].strip(), r[idx["PUUID"]].strip().lower()
            if pu and "#" in nm: name_of[pu][nm] += 1

    total, unknown = 0, []
    for tab, (ws, vals, idx) in sheets.items():
        cells = []
        for i, r in enumerate(vals[1:], start=2):
            if len(r) <= max(idx["소환사명"], idx["PUUID"]): continue
            nm, pu = r[idx["소환사명"]].strip(), r[idx["PUUID"]].strip().lower()
            if not nm or "#" in nm: continue           # 정상 행
            good = name_of.get(pu)
            if not good:
                unknown.append((tab, i, nm, pu)); continue
            real = good.most_common(1)[0][0]
            cells.append(gspread.Cell(row=i, col=idx["소환사명"] + 1, value=real))
            print(f"  · {tab} {i}행: {nm} → {real}")
        if not cells: continue
        total += len(cells)
        if os.environ.get("APPLY") == "1":
            _retry(f"{tab} 이름 수정", lambda ws=ws, cells=cells: ws.update_cells(cells, value_input_option="RAW"))

    for tab, i, nm, pu in unknown:
        print(f"  ? {tab} {i}행: '{nm}'({pu[:8]}…) — 이 PUUID의 정상 이름을 못 찾아 건드리지 않음")

    if not total:
        print("고칠 행 없음."); return 0
    print(f"\n{'수정 완료' if os.environ.get('APPLY') == '1' else '수정 대상'} — {total}행"
          + ("" if os.environ.get("APPLY") == "1" else " (APPLY=1 이어야 실제 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
