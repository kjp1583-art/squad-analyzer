#!/usr/bin/env python3
"""ai-eval-data 브랜치의 sheet_updates.json을 구글 시트에 직접 반영(Actions 전용).

Apps Script 대체 — 사장님이 스크립트를 붙여넣고 sync를 누르지 않아도 시트 편집이 끝나게 한다.
지원 op: create(+header) / append(중복 행 무시) / remove(첫 열 값 일치 행 삭제).
적용된 seq는 sheet_updates_applied.txt에 남겨 재실행 시 건너뛴다(중복 반영 방지).
"""
import base64, json, os, sys

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
STATE = "sheet_updates_applied.txt"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


def _norm(v):
    return "".join(str(v or "").split()).lower()


def main():
    data = json.load(open("sheet_updates.json", encoding="utf-8"))
    seq = int(data.get("seq") or 0)
    last = 0
    if os.path.exists(STATE):
        try: last = int(open(STATE, encoding="utf-8").read().strip() or 0)
        except ValueError: last = 0
    force = os.environ.get("FORCE") == "1"
    if seq <= last and not force:
        print(f"이미 적용됨 (seq {seq} <= {last}) — 변경 없음")
        return 0

    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw:
        print("CREDENTIALS_JSON_B64 시크릿 없음", file=sys.stderr); return 1
    open("creds.json", "wb").write(base64.b64decode(raw))
    ss = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)).open_by_key(SHEET_ID)

    applied = 0
    for op in data.get("ops", []):
        tab = op.get("tab")
        try:
            ws = ss.worksheet(tab)
        except Exception:
            if not op.get("create"):
                print(f"  · {tab}: 탭 없음 — 건너뜀"); continue
            ws = ss.add_worksheet(title=tab, rows="500", cols=str(max(6, len(op.get("header") or []))))
            if op.get("header"): ws.append_row(op["header"], value_input_option="RAW")
            print(f"  · {tab}: 탭 생성")

        vals = ws.get_all_values()
        rows = op.get("append") or []
        if rows:
            seen = {"\x01".join(map(str, r)) for r in vals}
            new = [r for r in rows if "\x01".join(map(str, r)) not in seen]
            if new:
                ws.append_rows(new, value_input_option="RAW")
                applied += len(new)
            print(f"  · {tab}: {len(new)}행 추가 (중복 {len(rows) - len(new)}건 무시)")

        rm = {_norm(v) for v in (op.get("remove") or [])}
        if rm:
            vals = ws.get_all_values()
            hit = [i for i in range(len(vals) - 1, 0, -1) if vals[i] and _norm(vals[i][0]) in rm]
            for i in hit:
                ws.delete_rows(i + 1)   # 아래에서부터 삭제 — 인덱스 밀림 방지
            applied += len(hit)
            print(f"  · {tab}: {len(hit)}행 삭제")

    open(STATE, "w", encoding="utf-8").write(str(seq))
    print(f"완료 — seq {seq}, 총 {applied}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
