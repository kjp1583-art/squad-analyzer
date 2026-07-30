#!/usr/bin/env python3
"""롤 클래식 판을 협곡 탭(CLASSIC_NORMAL)에서 골라내 LOL_CLASSIC 탭으로 옮긴다.

[2026-07-30 사장님 지시] 롤 클래식이 협곡 탭에 섞여 들어와 지표가 오염된다.
분석기는 게임 시작 시점에 모드를 구분할 근거(큐·맵 ID)를 갖고 있지 않으므로,
기록이 끝난 뒤 이 스크립트가 주기적으로 골라 옮긴다(칼바람처럼 탭을 분리).

판별 근거 — 클래식은 아이템 체계가 통째로 다르다:
  · 협곡 아이템 ID = 3153·6672 같은 4자리
  · 클래식 아이템 ID = 771043·773031 같은 77만번대 6자리   ← 이걸 본다
아이템이 아직 안 붙은 판은 보조 근거로 '한 팀에 같은 포지션이 3명 이상'을 쓴다
(클래식은 포지션 정보가 없어 대부분 '탑'으로 채워진다).

기본은 미리보기(dry-run). 실제 이동은 APPLY=1 일 때만.
"""
import base64, os, re, sys, time
from collections import Counter, defaultdict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
SRC_TAB, DST_TAB = "CLASSIC_NORMAL", "LOL_CLASSIC"
CLASSIC_ITEM = re.compile(r"\b77\d{4}\b")      # 77만번대 6자리 = 클래식 전용 아이템
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


def _is_classic(rows, idx):
    """이 게임이 롤 클래식인가."""
    for r in rows:
        if idx.get("아이템") is not None and idx["아이템"] < len(r) and CLASSIC_ITEM.search(str(r[idx["아이템"]])):
            return "아이템 체계(77만번대)"
    pos = Counter(str(r[idx["포지션"]]).strip() for r in rows if idx["포지션"] < len(r))
    pos.pop("", None); pos.pop("선택안함", None)
    if pos and max(pos.values()) >= 6:         # 한 포지션에 6명 이상 = 포지션 정보 없는 모드
        return "포지션 쏠림"
    return ""


def main():
    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw:
        print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
    open("creds.json", "wb").write(base64.b64decode(raw))
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
    ss = _retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))
    src = _retry(f"{SRC_TAB} 열기", lambda: ss.worksheet(SRC_TAB))

    vals = _retry("행 읽기", src.get_all_values)
    head = vals[0]
    idx = {c: i for i, c in enumerate(head)}
    for need in ("게임ID", "포지션"):
        if need not in idx:
            print(f"'{need}' 열 없음 — 중단", file=sys.stderr); return 1

    games, order = defaultdict(list), []
    for i in range(1, len(vals)):
        gid = vals[i][idx["게임ID"]] if idx["게임ID"] < len(vals[i]) else ""
        if not gid: continue
        if gid not in games: order.append(gid)
        games[gid].append(i + 1)               # 1-based 행번호

    move_rows, move_nums = [], []
    for gid in order:
        rows = [vals[n - 1] for n in games[gid]]
        why = _is_classic(rows, idx)
        if not why: continue
        print(f"  · {gid} ({rows[0][idx.get('날짜', 1)]}) {len(rows)}행 — {why}")
        move_rows.extend(rows); move_nums.extend(games[gid])

    if not move_rows:
        print("옮길 클래식 판 없음."); return 0
    print(f"\n이동 대상 {len(move_rows)}행 / {len({vals[n-1][idx['게임ID']] for n in move_nums})}판")

    # 목적지 탭 — 없으면 만들고 헤더를 원본과 똑같이 맞춘다.
    try:
        dst = ss.worksheet(DST_TAB)      # 탭 부재는 일시 오류가 아니다 — 재시도하면 백오프만 낭비한다
        created = False
    except Exception:
        dst = _retry(f"{DST_TAB} 생성", lambda: ss.add_worksheet(title=DST_TAB, rows="2000", cols=str(max(14, len(head)))))
        _retry("헤더 쓰기", lambda: dst.append_row(head, value_input_option="RAW"))
        created = True
    print(f"{DST_TAB} {'생성' if created else '기존 사용'} — gid={dst.id}")

    if os.environ.get("APPLY") != "1":
        print("미리보기만 했습니다(APPLY=1 이어야 실제 이동)."); return 0

    # 이미 옮겨진 게임은 건너뛴다(중복 이동 방지)
    dvals = _retry(f"{DST_TAB} 읽기", dst.get_all_values)
    have = {r[idx["게임ID"]] for r in dvals[1:] if len(r) > idx["게임ID"]}
    fresh = [r for r in move_rows if r[idx["게임ID"]] not in have]
    if fresh:
        _retry("행 추가", lambda: dst.append_rows(fresh, value_input_option="RAW"))
    print(f"{DST_TAB} 에 {len(fresh)}행 추가 (이미 있던 {len(move_rows) - len(fresh)}행 건너뜀)")

    runs, cur = [], []
    for n in sorted(move_nums):
        if cur and n == cur[-1] + 1: cur.append(n)
        else:
            if cur: runs.append((cur[0], cur[-1]))
            cur = [n]
    if cur: runs.append((cur[0], cur[-1]))
    for a, b in sorted(runs, reverse=True):
        _retry(f"{a}~{b}행 삭제", lambda a=a, b=b: src.delete_rows(a, b))
        time.sleep(1.2)
    print(f"{SRC_TAB} 에서 {len(move_nums)}행 제거 ({len(runs)}구간) — 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
