#!/usr/bin/env python3
"""한 판의 승패·진영이 뒤바뀌어 적힌 기록을 바로잡는다(2026-11-20 사장님 제보 「인게임은 승리했는데 결과가 반대」 · #8464934822).

하는 일(기본은 미리보기, APPLY=1 일 때만 시트를 바꾼다):
  1) SRC_TAB 에서 그 판의 행을 모은다(기본 LOL_CLASSIC — 롤 클래식으로 잘못 옮겨진 판).
  2) 같은 사람이 두 번 적힌 행은 한 번만 남긴다(KDA 가 채워진 쪽 우선).
  3) WINNER_NAME(소환사명 일부)의 팀이 이긴 것으로 승패를 맞춘다. SWAP_SIDES=1 이면 진영(블루↔레드)도 뒤집는다.
  4) DST_TAB(기본 CLASSIC_NORMAL)의 날짜 순서 자리에 끼워 넣고 SRC_TAB 에서 지운다(DST_TAB=SRC_TAB 이면 제자리 수정).
환경변수: GID(예 #8464934822) · WINNER_NAME · SWAP_SIDES(0/1) · SRC_TAB · DST_TAB · APPLY(0/1) · CREDENTIALS_JSON_B64
"""
import base64, os, sys, time

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


def _retry(label, fn, tries=5):
    for i in range(tries):
        try: return fn()
        except Exception as e:
            if i == tries - 1: raise
            wait = 20 * (2 ** i); print(f"  ! {label} 실패({type(e).__name__}) — {wait}s 후 재시도", flush=True); time.sleep(wait)


def plan(rows, idx, winner_name, swap_sides):
    """순수 함수 — rows(그 판의 행들) → (새 행들, 설명 줄들). 시트를 건드리지 않는다."""
    c_pu, c_nm, c_side, c_res, c_kda = idx.get("PUUID"), idx["소환사명"], idx["진영"], idx["결과"], idx.get("KDA")
    pick, order = {}, []
    for r in rows:
        r = list(r) + [""] * (len(idx) - len(r))
        key = (str(r[c_pu]).strip().lower() if c_pu is not None and str(r[c_pu]).strip() else str(r[c_nm]).strip().lower())
        filled = c_kda is not None and str(r[c_kda]).strip() not in ("", "-", "기록 대기")
        if key not in pick: pick[key] = r; order.append(key)
        elif filled and not (c_kda is not None and str(pick[key][c_kda]).strip() not in ("", "-", "기록 대기")): pick[key] = r
    out = [pick[k] for k in order]
    notes = [f"행 {len(rows)} → 중복 제거 후 {len(out)}"]
    me = [r for r in out if winner_name and winner_name.lower() in str(r[c_nm]).lower()]
    if not me: raise SystemExit(f"WINNER_NAME '{winner_name}' 와 맞는 행이 없어요")
    win_side = str(me[0][c_side]).strip()          # 이긴 팀의 (현재) 진영 라벨
    for r in out:
        r[c_res] = "승리" if str(r[c_side]).strip() == win_side else "패배"
    if swap_sides:
        for r in out:
            s = str(r[c_side]).strip(); r[c_side] = "레드팀" if s == "블루팀" else ("블루팀" if s == "레드팀" else s)
    notes.append(f"이긴 팀(원래 라벨) = {win_side} · 진영 뒤집기 = {bool(swap_sides)}")
    return out, notes


def main():
    gid = os.environ.get("GID", "").strip(); win = os.environ.get("WINNER_NAME", "").strip()
    if not gid.startswith("#") or not win: print("GID(#...)·WINNER_NAME 필요", file=sys.stderr); return 1
    swap = os.environ.get("SWAP_SIDES") == "1"; apply = os.environ.get("APPLY") == "1"
    src_t, dst_t = os.environ.get("SRC_TAB", "LOL_CLASSIC"), os.environ.get("DST_TAB", "CLASSIC_NORMAL")
    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw: print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
    open("creds.json", "wb").write(base64.b64decode(raw))
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
    ss = _retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))
    src = _retry(f"{src_t} 열기", lambda: ss.worksheet(src_t))
    vals = _retry("행 읽기", src.get_all_values); head = vals[0]; idx = {c: i for i, c in enumerate(head)}
    nums = [i + 1 for i in range(1, len(vals)) if len(vals[i]) > idx["게임ID"] and vals[i][idx["게임ID"]].strip() == gid]
    if not nums: print(f"{src_t} 에 {gid} 없음"); return 1
    rows = [vals[n - 1] for n in nums]
    new, notes = plan(rows, idx, win, swap)
    print(f"{gid} ({new[0][idx['날짜']]}) — {src_t} {len(nums)}행"); [print("  ·", x) for x in notes]
    for r in new: print("   ", [r[idx[k]] for k in ("소환사명", "진영", "포지션", "챔피언", "결과", "매치평가", "KDA")])
    if not apply: print("미리보기만 했습니다(APPLY=1 이어야 실제 수정)."); return 0
    if src_t == dst_t:
        raise SystemExit("제자리 수정은 아직 지원하지 않아요(DST_TAB 를 다르게)")
    dst = _retry(f"{dst_t} 열기", lambda: ss.worksheet(dst_t)); dv = _retry(f"{dst_t} 읽기", dst.get_all_values)
    if any(len(r) > idx["게임ID"] and r[idx["게임ID"]].strip() == gid for r in dv[1:]):
        print(f"{dst_t} 에 이미 {gid} 가 있어요 — 중단"); return 1
    dh = {c: i for i, c in enumerate(dv[0])}
    if dh != idx: print("두 탭의 열 순서가 달라요 — 중단", file=sys.stderr); return 1
    date = new[0][idx["날짜"]]; ins = len(dv) + 1          # 기본: 맨 끝
    for i in range(1, len(dv)):
        d = dv[i][idx["날짜"]] if len(dv[i]) > idx["날짜"] else ""
        if d and d > date: ins = i + 1; break
    _retry("행 끼워넣기", lambda: dst.insert_rows(new, row=ins, value_input_option="RAW"))
    print(f"{dst_t} {ins}행 자리에 {len(new)}행 삽입")
    for a, b in reversed([(nums[0], nums[-1])] if nums == list(range(nums[0], nums[-1] + 1)) else [(n, n) for n in nums]):
        _retry(f"{a}~{b}행 삭제", lambda a=a, b=b: src.delete_rows(a, b)); time.sleep(1.2)
    print(f"{src_t} 에서 {len(nums)}행 제거 — 완료"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
