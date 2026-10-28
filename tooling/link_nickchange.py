#!/usr/bin/env python3
"""🎭 닉변 자동 감지 → LINK_ACCOUNT 에 기록 (2026-09-16 사장님 지시)

    "닉변 유저가 생기면 링크어카운트 탭에 자동으로 기록되는 로직 추가해줘"

롤 닉네임(Riot ID)은 바뀌어도 **PUUID 는 안 바뀐다.** 그래서 같은 PUUID 가 서로 다른
소환사명으로 기록돼 있으면 그건 닉변이다. 이걸 LINK_ACCOUNT 에 넣어두지 않으면
그 사람의 기록이 두 사람 몫으로 갈라진다(실제로 '윤 슬' 407판이 '단단묵직' 과 갈라져 있었다).

동작
    CLASSIC_NORMAL·KIWI_KIWI 전량 → PUUID 별 닉 목록 → 가장 최근 닉이 '지금 이름',
    나머지는 '옛 이름' → LINK_ACCOUNT 에 `본계정=지금 이름 / 부계정=옛 이름` 으로 **append**.

원칙 (사람이 손으로 관리하는 표를 건드리는 일이라 보수적으로)
    · **추가만 한다.** 기존 행은 고치지도 지우지도 않는다.
    · 둘 중 **한 이름이라도 이미 LINK_ACCOUNT 에 있으면 통째로 건너뛴다** — 사람이 이미 정한 것이다
      (사장님이 '용조련사' 를 일부러 옛 닉 쪽으로 등록한 것처럼, 방향은 사람의 판단 영역이다).
    · 같은 이름이 **다른 PUUID 로도 쓰인 적 있으면 건너뛴다** — 동명이인이면 합치면 안 된다.
    · 소환사명이 챔피언 이름으로 잘못 들어간 행(알려진 버그)과 태그(#) 없는 행은 증거로 쓰지 않는다.
    · 기본은 미리보기. APPLY=1 일 때만 실제로 쓴다.

메모 칸에 근거(판수·마지막 기록일·PUUID 앞자리)를 남겨 나중에 사람이 되돌릴 수 있게 한다.
"""
import base64, os, re, sys, time
from collections import defaultdict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
TABS = ("CLASSIC_NORMAL", "KIWI_KIWI")
LINK_TAB = "LINK_ACCOUNT"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
MIN_PUUID_GAMES = 5    # 이 PUUID 가 실제로 활동한 사람인지 — 한두 줄짜리 이상 행으로 링크가 생기는 걸 막는다
MIN_OLD_GAMES = 1      # 옛 닉으로 남은 기록 최소 판수. PUUID 가 일치하므로 1판도 증거로 충분하다
#   ⚠ 시트에는 진짜 PUUID 가 아닌 자리표시자가 섞여 있다 — 예: "BOT_FALLBACK_아트록스".
#   이건 사람이 아니라 '챔피언별 대타' 라서 **서로 다른 사람이 같은 값을 공유한다**
#   (BOT_FALLBACK_아트록스 = 쭌 생#kr2 · 쏘금빵#123). 그대로 두면 남남을 한 사람으로 합쳐 버린다.
PUUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _nk(s):
    """롤닉 정규화 — 봇(_nk)·분석기와 같은 규칙: #태그 제거·소문자·공백 제거."""
    return "".join(str(s or "").split("#")[0].lower().split())


def _retry(label, fn, tries=5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1: raise
            wait = 30 * (2 ** i)
            print(f"  ! {label} 실패({type(e).__name__}) — {wait}s 후 재시도", flush=True)
            time.sleep(wait)


def _open(ss, tab):
    """탭 열기 — **없는 탭이면 즉시 None.** 여기서 _retry 를 쓰면 있지도 않은 탭에
       30·60·120·240초 백오프를 그대로 태워 7분 넘게 멈춘다(KIWI_KIWI 가 없는 시트에서 실제로 걸린다).
       일시적 오류(429·네트워크)일 때만 재시도한다."""
    try:
        return ss.worksheet(tab)
    except Exception as e:
        if "notfound" in type(e).__name__.lower() or "not found" in str(e).lower(): return None
        return _retry(f"{tab} 열기", lambda: ss.worksheet(tab))


def collect(ss):
    """두 탭 전량 → puuid → {정규화닉: [판수, 마지막날짜, 표시용 원본닉]} · 정규화닉 → {puuid} """
    per = defaultdict(lambda: defaultdict(lambda: [0, "", ""]))
    owners = defaultdict(set)
    for tab in TABS:
        ws = _open(ss, tab)
        if ws is None:
            print(f"  · {tab}: 탭 없음 — 건너뜀"); continue
        vals = _retry(f"{tab} 읽기", ws.get_all_values)
        if not vals: continue
        idx = {c: i for i, c in enumerate(vals[0])}
        need = ("소환사명", "PUUID", "날짜")
        if any(c not in idx for c in need):
            print(f"  · {tab}: 필요한 열 없음 — 건너뜀"); continue
        ni, pi, di = idx["소환사명"], idx["PUUID"], idx["날짜"]
        ci = idx.get("챔피언", -1)
        for r in vals[1:]:
            if len(r) <= max(ni, pi, di): continue
            nm, pu, d = r[ni].strip(), r[pi].strip().lower(), r[di].strip()[:10]
            if not PUUID_RE.match(pu): continue                        # 🤖 BOT_FALLBACK_* 같은 자리표시자는 사람이 아니다
            if "#" not in nm: continue                                 # 태그 없는 이름은 증거로 안 쓴다
            if ci >= 0 and len(r) > ci and nm.replace(" ", "") == r[ci].strip().replace(" ", ""):
                continue                                               # 🐛 소환사명 칸에 챔피언이 들어간 알려진 버그 행
            k = _nk(nm)
            if not k: continue
            e = per[pu][k]; e[0] += 1
            if d >= e[1]: e[1], e[2] = d, nm                           # 표시용은 그 닉의 가장 최근 표기(태그 포함)
            owners[k].add(pu)
        print(f"  · {tab}: {len(vals) - 1}행 읽음")
    return per, owners


def existing_links(ss):
    """LINK_ACCOUNT 에 이미 등장하는 모든 이름(본계정·부계정 양쪽) — 정규화 집합."""
    ws = _open(ss, LINK_TAB)
    if ws is None:
        print(f"  ! {LINK_TAB} 탭이 없습니다 — 중단"); return None, set(), []
    vals = _retry(f"{LINK_TAB} 읽기", ws.get_all_values)
    seen, rows = set(), vals[1:] if vals else []
    for r in rows:
        for c in r[:2]:
            k = _nk(c)
            if k: seen.add(k)
    return ws, seen, rows


def main():
    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw:
        print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
    open("creds.json", "wb").write(base64.b64decode(raw))
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
    ss = _retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))
    apply = os.environ.get("APPLY", "0") == "1"

    print("▶ 전적 탭 읽는 중…")
    per, owners = collect(ss)
    print(f"▶ {LINK_TAB} 읽는 중…")
    ws, seen, cur_rows = existing_links(ss)
    if ws is None: return 1
    print(f"  · 기존 {len(cur_rows)}행 · 등장 이름 {len(seen)}개\n")

    today = time.strftime("%Y-%m-%d")
    add, skip = [], []
    #   🐛 '이미 사람이 정했나'(seen, 시트에서 읽은 값) 와 '이번 실행에서 이미 부계정으로 넣었나'(added_alt) 는
    #   따로 둬야 한다. 하나로 합치면 닉을 세 번 바꾼 사람의 **두 번째 옛 닉이 통째로 누락된다**
    #   (1대→3대 를 넣으면서 '3대' 가 seen 에 들어가고, 2대 차례에 '현재 닉이 이미 있음' 으로 잘못 걸린다).
    #   본계정은 여러 번 나와도 된다 — 실제 시트에도 '언 진' 이 두 행의 본계정으로 있다.
    added_alt = set()
    for pu, names in per.items():
        if len(names) < 2: continue
        if sum(v[0] for v in names.values()) < MIN_PUUID_GAMES:
            skip.append((f"PUUID {pu[:8]}…", "-", f"이 PUUID 총 판수 < {MIN_PUUID_GAMES}")); continue
        order = sorted(names.items(), key=lambda kv: (kv[1][1], kv[1][0]))   # 마지막 기록일 → 판수
        cur_k, (cur_n, cur_d, cur_disp) = order[-1]
        for old_k, (old_n, old_d, old_disp) in order[:-1]:
            if old_n < MIN_OLD_GAMES:
                skip.append((old_disp, cur_disp, f"옛 닉 판수 < {MIN_OLD_GAMES}")); continue
            if old_k in seen or cur_k in seen:
                #   ⚠ [2026-09-17] 현재 닉이 **부계정 열**에, 옛 닉이 본계정 열에 있으면(귤 갓#Gyul ← 카무사리#귤 갓) 방향이
                #      규약(본계=지금 이름)과 반대다. 사람의 판단이라 고치진 않지만, 조용히 넘기면 웹 칼바람 탭이 이 사람을
                #      옛 닉(옛 티어·피크 전용 솔랭)으로 부르고 탈퇴 판정도 어긋난다 — 요약에 크게 남긴다.
                _rev = [r for r in cur_rows if len(r) >= 2 and _nk(r[1]) == cur_k and _nk(r[0]) == old_k]
                if _rev:
                    skip.append((old_disp, cur_disp, f"⚠ 방향 역전 — LINK_ACCOUNT 에 본계정={_rev[0][0]} / 부계정={_rev[0][1]} 로 있음. 지금 이름은 {cur_disp}. 본계정을 지금 이름으로 바꿔 주세요")); continue
                skip.append((old_disp, cur_disp, "이미 LINK_ACCOUNT 에 있음(사람이 정한 것)")); continue
            if old_k in added_alt:
                skip.append((old_disp, cur_disp, "이번 실행에서 이미 부계정으로 넣음")); continue
            if len(owners.get(old_k, ())) > 1 or len(owners.get(cur_k, ())) > 1:
                skip.append((old_disp, cur_disp, "같은 이름을 쓴 PUUID 가 둘 이상 — 동명이인 위험")); continue
            memo = (f"닉변 자동 감지 ({today}) — 같은 PUUID {pu[:8]}… · "
                    f"옛 닉 {old_n}판(마지막 {old_d}) → 현재 닉 {cur_n}판(최근 {cur_d})")
            add.append([cur_disp, old_disp, memo])
            added_alt.add(old_k)                      # 부계정은 한 번만(봇이 부계정 키로 dict 를 만든다)

    print(f"➕ 추가 대상 {len(add)}건")
    for m, a, memo in add:
        print(f"   본계정 {m}  ←  부계정 {a}")
        print(f"      {memo}")
    print(f"\n⏭ 건너뛴 것 {len(skip)}건")
    for a, m, why in skip:
        print(f"   {a} → {m} : {why}")

    if not add:
        print("\n새로 넣을 닉변이 없습니다.")
    elif not apply:
        print("\n(미리보기 — 실제로 쓰려면 APPLY=1)")
    else:
        _retry("LINK_ACCOUNT 추가", lambda: ws.append_rows(add, value_input_option="RAW"))
        print(f"\n✅ {LINK_TAB} 에 {len(add)}행 추가했습니다.")

    # GitHub Actions 요약(있으면)
    sm = os.environ.get("GITHUB_STEP_SUMMARY")
    if sm:
        with open(sm, "a", encoding="utf-8") as f:
            f.write(f"## 🎭 닉변 감지 — {'기록함' if (apply and add) else '미리보기'}\n\n")
            if add:
                f.write("| 본계정(현재 닉) | 부계정(옛 닉) | 근거 |\n|---|---|---|\n")
                for m, a, memo in add:
                    f.write(f"| {m} | {a} | {memo} |\n")
            else:
                f.write("새로 감지된 닉변이 없습니다.\n")
            if skip:
                f.write(f"\n<details><summary>건너뛴 {len(skip)}건</summary>\n\n")
                for a, m, why in skip: f.write(f"- `{a}` → `{m}` — {why}\n")
                f.write("\n</details>\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try: os.remove("creds.json")
        except Exception: pass
