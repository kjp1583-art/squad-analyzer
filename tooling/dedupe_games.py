#!/usr/bin/env python3
"""CLASSIC_NORMAL에서 같은 판이 두 번 기록된 행을 정리한다(2026-07-29 사장님 지시).

두 분석기가 같은 판을 각각 append 하면 한 게임에 20행이 남고, 포지션 판정까지
서로 달라 웹에서 20명·중복 카드로 보였다. 웹은 표시 단계에서 막았지만 원본에도
남아 있어 지운다.

어느 벌을 남기나 — 같은 (게임ID, PUUID) 가 여러 행이면:
  ① 팀별 포지션이 탑·정글·미드·원딜·서폿 하나씩으로 온전한 벌을 우선 남긴다.
  ② 둘 다 온전하거나 둘 다 아니면 먼저 기록된 행(위쪽)을 남긴다.
지우는 건 그 외의 행뿐이고, 게임ID가 하나뿐인 행은 건드리지 않는다.

기본은 미리보기(dry-run). 실제 삭제는 APPLY=1 일 때만.
"""
import base64, os, sys
from collections import defaultdict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
TAB = "CLASSIC_NORMAL"
ROLES = {"탑", "정글", "미드", "원딜", "서폿"}
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


def _complete(rows, idx):
    """이 벌이 양 팀 다 5역할을 하나씩 채우는가."""
    by_side = defaultdict(list)
    for r in rows:
        by_side[r[idx["진영"]]].append(r[idx["포지션"]])
    if len(by_side) != 2: return False
    return all(set(v) == ROLES and len(v) == 5 for v in by_side.values())


def main():
    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw:
        print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
    open("creds.json", "wb").write(base64.b64decode(raw))
    ws = gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
    ).open_by_key(SHEET_ID).worksheet(TAB)

    vals = ws.get_all_values()
    head = vals[0]
    idx = {c: i for i, c in enumerate(head)}
    for need in ("게임ID", "PUUID", "진영", "포지션"):
        if need not in idx:
            print(f"'{need}' 열 없음 — 중단", file=sys.stderr); return 1

    # 게임ID → 행번호(1-based) 목록
    by_game = defaultdict(list)
    for i in range(1, len(vals)):
        gid = vals[i][idx["게임ID"]] if idx["게임ID"] < len(vals[i]) else ""
        if gid: by_game[gid].append(i + 1)

    doomed = []
    for gid, rownums in by_game.items():
        seen_people = defaultdict(list)
        for rn in rownums:
            r = vals[rn - 1]
            pu = (r[idx["PUUID"]] if idx["PUUID"] < len(r) else "") or ""
            seen_people[pu.strip().lower()].append(rn)
        if not any(len(v) > 1 for v in seen_people.values()):
            continue                                    # 중복 없음

        # 벌 나누기 — 앞의 10행 / 뒤의 10행(append 단위)
        half = len(rownums) // 2
        first, second = rownums[:half], rownums[half:]
        rows1 = [vals[r - 1] for r in first]
        rows2 = [vals[r - 1] for r in second]
        keep_first = True
        if _complete(rows2, idx) and not _complete(rows1, idx):
            keep_first = False
        drop = second if keep_first else first
        doomed.extend(drop)
        print(f"  · {gid}: {len(rownums)}행 → {len(drop)}행 삭제 "
              f"({'앞' if keep_first else '뒤'} 벌 유지"
              f"{', 포지션 온전' if _complete(rows1 if keep_first else rows2, idx) else ''})")

    if not doomed:
        print("중복 없음 — 변경할 것 없습니다."); return 0
    print(f"\n삭제 대상 {len(doomed)}행")
    if os.environ.get("APPLY") != "1":
        print("미리보기만 했습니다(APPLY=1 이어야 실제 삭제)."); return 0

    for rn in sorted(doomed, reverse=True):             # 아래에서부터 — 인덱스 밀림 방지
        ws.delete_rows(rn)
    print(f"삭제 완료 — {len(doomed)}행")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
