#!/usr/bin/env python3
"""라인이 뒤바뀐 채로 기록된 협곡 내전 행의 포지션을 되돌린다(2026-08-03 사장님 제보).

제보: 레오나 장인랭킹에 정글·원딜 레오나가 보인다 — 실제로는 전부 서폿이었다.

원인은 두 갈래다.
  ① 팀 포지션 구성 자체가 깨진 경우(정글 2명·탑 0명 등) — 라이엇 종료데이터의 teamPosition이
     커스텀 게임에서 종종 비거나 겹친다.
  ② 구성은 5개 라인이 다 있는데 사람만 서로 바뀐 경우 — 종료데이터가 비어 로스터 인덱스
     추측값(pos_map)으로 채운 판. 팀 단위로는 멀쩡해 보여서 눈에 안 띈다.
     (예: 2026-07-24 옴팡이 레오나가 '정글', 건빡 볼리베어가 '서폿'으로 뒤바뀜)

고치는 근거는 '그 판에 실제로 남은 기록'이다 — 추측이 아니다.
  · 서폿: 분당 CS가 팀에서 압도적으로 낮다(클랜 실측 중앙값 1.0 vs 라이너 최저 4.6).
  · 정글: 강타를 들었다(클랜 실측 정글 842행 중 798행이 강타, 비정글은 10행뿐).
  · 남은 세 자리(탑·미드·원딜)는 판별 근거가 약하므로 **원래 라벨을 최대한 유지**하고,
    자리가 겹쳐 어쩔 수 없을 때만 클랜 내전에서 그 챔피언이 실제로 간 라인 분포로 채운다.
근거가 약하면 고치지 않고 목록만 남긴다(임의 추측 금지 — 오프라인 픽까지 지워버리면 안 된다).

지표·스펠은 2026-07-13 이후 기록에만 있다. 그 이전 판은 ①(구성이 깨진 팀)만,
챔피언 라인 분포로 명확할 때에 한해 고친다.

기본은 미리보기(dry-run). 실제 수정은 APPLY=1 일 때만.
"""
import base64, collections, itertools, math, os, re, sys, time

ROLES = ("탑", "정글", "미드", "원딜", "서폿")
SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
TAB = "CLASSIC_NORMAL"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# 판정 임계값 — 위 주석의 클랜 실측에서 넉넉히 떨어뜨려 잡았다.
SUP_MAX_CSPM = 3.0       # 서폿 후보의 분당 CS 상한
LANER_MIN_CSPM = 4.0     # 나머지 넷 중 최저가 이보다 높아야 '서폿이 뚜렷하다'고 본다
PRIOR_MIN = 8            # 챔피언 라인 분포를 근거로 쓰기 위한 최소 표본
PRIOR_MARGIN = 1.5       # 후보 배치 1위와 2위의 로그가능도 차 — 이보다 작으면 손대지 않는다
PRIOR_FLOOR = 0.10       # 그 챔피언이 클랜에서 그 라인을 실제로 이만큼은 가봤어야 배정한다.
#   ↑ 사장님 지시("레오나처럼 100% 서포터만 갔으리란 보장은 없어")는 양쪽으로 적용된다:
#     한 번도 안 가본 라인을 계산 편의로 떠넘기지도 말 것. 못 가리면 사람이 보게 남긴다.


def parse_metrics(s):
    out = {}
    for tok in str(s or "").split("|"):
        m = re.match(r"^([a-z]+)(-?\d+(?:\.\d+)?)$", tok.strip())
        if m: out[m.group(1)] = float(m.group(2))
    return out if out.get("m", 0) > 0 else None


def build_prior(teams):
    """구성이 온전한 팀만 모아 만든 {챔피언: {라인: 판수}} — 고칠 대상 자체는 재료에서 뺀다."""
    prior = collections.defaultdict(collections.Counter)
    for rs in teams:
        if len(rs) != 5 or sorted(p for _, p, _, _ in rs) != sorted(ROLES): continue
        for _, pos, champ, _ in rs:
            if champ: prior[champ][pos] += 1
    return prior


def _prior_lp(prior, champ, role):
    c = prior.get(champ)
    n = sum(c.values()) if c else 0
    if n < PRIOR_MIN: return None
    if c.get(role, 0) / n < PRIOR_FLOOR: return None      # 가본 적 없다시피 한 라인은 후보에서 제외
    return math.log((c.get(role, 0) + 0.5) / (n + 0.5 * len(ROLES)))


def repair_team(rs, prior):
    """rs = [(row_no, 포지션, 챔피언, {지표·스펠}), …] 5명 → {row_no: 새 포지션} (없으면 빈 dict).

    반환 두 번째 값은 사람이 읽을 판정 근거. 세 번째는 '고쳐야 하는데 근거가 모자란' 사유.
    """
    pos = [x[1] for x in rs]
    valid = sorted(pos) == sorted(ROLES)
    mets = [x[3].get("met") for x in rs]
    have_met = all(m for m in mets)

    fixed, why, scrambled = {}, [], False
    if have_met:
        cspm = [m["cs"] / m["m"] for m in mets]
        order = sorted(range(5), key=lambda i: cspm[i])
        if cspm[order[0]] < SUP_MAX_CSPM and cspm[order[1]] > LANER_MIN_CSPM:
            fixed[order[0]] = "서폿"
            why.append(f"서폿={rs[order[0]][2]}(분당CS {cspm[order[0]]:.1f})")
        smite = [i for i, x in enumerate(rs) if "Smite" in str(x[3].get("spell") or "")]
        if len(smite) == 1 and smite[0] not in fixed:
            fixed[smite[0]] = "정글"
            why.append(f"정글={rs[smite[0]][2]}(강타)")

    scrambled = any(pos[i] != r for i, r in fixed.items())
    if not fixed and valid:
        return {}, [], ""                    # 구성도 멀쩡하고 강한 근거도 없다 → 남의 오프라인 픽일 수 있다
    if not have_met:
        why.append("지표 없음 — 챔피언 라인 분포로만 판정")

    # 남은 자리 배정.
    #  · 강한 근거가 기록된 라벨과 **어긋난 팀**은 라벨이 통째로 섞인 판이다(로스터 인덱스로 채운 판).
    #    이때는 남은 라벨도 못 믿으므로 전부 챔피언 라인 분포로 다시 배정한다.
    #  · 그렇지 않은 팀(구성만 깨진 팀)은 원래 라벨을 최대한 살리되, **겹친 라벨은 아무도 선점하지 못하게**
    #    한다. 행 순서대로 먼저 온 사람이 자리를 차지하게 두면 근거 없이 승패가 갈린다
    #    (서폿 카밀/서폿 레오나가 겹친 판에서 레오나가 탑으로 밀려나던 실수 — 2026-08-03 검증 중 발견).
    left_idx = [i for i in range(5) if i not in fixed]
    left_role = [r for r in ROLES if r not in fixed.values()]
    dup = {r for r, n in collections.Counter(pos[i] for i in left_idx).items() if n > 1}
    keep = {} if scrambled else {i: pos[i] for i in left_idx if pos[i] in left_role and pos[i] not in dup}
    rest_idx = [i for i in left_idx if i not in keep]
    rest_role = [r for r in left_role if r not in keep.values()]
    if rest_idx:
        best, second = None, None
        for perm in itertools.permutations(rest_role):
            lps = [_prior_lp(prior, rs[i][2], r) for i, r in zip(rest_idx, perm)]
            if any(v is None for v in lps): continue
            s = sum(lps)
            if best is None or s > best[0]: best, second = (s, perm), best
            elif second is None or s > second[0]: second = (s, perm)
        if best is None:
            return {}, why, f"{','.join(rs[i][2] for i in rest_idx)} — 라인 분포 표본 부족"
        if second is not None and best[0] - second[0] < PRIOR_MARGIN:
            return {}, why, f"{','.join(rs[i][2] for i in rest_idx)} — 어느 배치인지 가리기 어려움"
        for i, r in zip(rest_idx, best[1]): keep[i] = r
        why.append("나머지=" + "·".join(f"{rs[i][2]}→{keep[i]}" for i in rest_idx))
    out = dict(fixed); out.update(keep)
    return ({rs[i][0]: out[i] for i in range(5) if out[i] != pos[i]}, why, "")


def scan(rows, idx):
    """시트 값 배열 → (고칠 것 {행번호: 새 포지션}, 로그 줄, 보류 줄)"""
    def col(r, n):                       # 없는 열(옛 시트의 지표·스펠 등)은 빈 값으로 취급
        i = idx.get(n, -1)
        return r[i] if 0 <= i < len(r) else ""
    teams = collections.defaultdict(list)
    for i, r in enumerate(rows[1:], start=2):
        gid, side = str(col(r, "게임ID")).strip(), str(col(r, "진영")).strip()
        if not gid or not side: continue
        teams[(gid, side)].append((i, str(col(r, "포지션")).strip(), str(col(r, "챔피언")).strip(),
                                  {"met": parse_metrics(col(r, "지표")), "spell": col(r, "스펠"),
                                   "name": str(col(r, "소환사명")).strip(),
                                   "date": str(col(r, "날짜")).strip()}))
    prior = build_prior([v for v in teams.values()])
    fixes, logs, held = {}, [], []
    for (gid, side), rs in sorted(teams.items(), key=lambda kv: kv[1][0][3]["date"]):
        if len(rs) != 5: continue
        ch, why, hold = repair_team(rs, prior)
        if hold:
            held.append(f"  ? {gid} {side} ({rs[0][3]['date'][:16]}) — {hold}")
            continue
        if not ch: continue
        fixes.update(ch)
        logs.append(f"  · {gid} {side} ({rs[0][3]['date'][:16]}) — {' / '.join(why)}")
        for i, pos_, champ, ex in rs:
            if i in ch: logs.append(f"      {i}행 {ex['name']} {champ}: {pos_} → {ch[i]}")
    return fixes, logs, held


def _retry(label, fn, tries=5):
    for i in range(tries):
        try: return fn()
        except Exception:
            if i == tries - 1: raise
            wait = 30 * (2 ** i)
            print(f"  ! {label} 실패 — {wait}s 후 재시도", flush=True)
            time.sleep(wait)


def main():
    # 로컬 점검용: python3 fix_positions.py --xlsx squad_sheet.xlsx (시트 접속 없이 미리보기)
    if "--xlsx" in sys.argv:
        import openpyxl
        wb = openpyxl.load_workbook(sys.argv[sys.argv.index("--xlsx") + 1], read_only=True, data_only=True)
        vals = [[("" if c is None else c) for c in r] for r in wb[TAB].values]
    else:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        raw = os.environ.get("CREDENTIALS_JSON_B64", "")
        if not raw:
            print("CREDENTIALS_JSON_B64 없음", file=sys.stderr); return 1
        open("creds.json", "wb").write(base64.b64decode(raw))
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
        ss = _retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))
        ws = _retry(f"{TAB} 열기", lambda: ss.worksheet(TAB))
        vals = _retry(f"{TAB} 읽기", ws.get_all_values)

    idx = {c: i for i, c in enumerate(vals[0])}
    for need in ("게임ID", "진영", "포지션", "챔피언"):
        if need not in idx:
            print(f"{TAB}: '{need}' 열이 없음", file=sys.stderr); return 1

    fixes, logs, held = scan(vals, idx)
    for ln in logs: print(ln)
    for ln in held: print(ln)
    if not fixes:
        print("\n고칠 행 없음."); return 0

    if "--xlsx" in sys.argv:
        print(f"\n수정 대상 — {len(fixes)}행 (로컬 미리보기라 시트는 건드리지 않음)"); return 0
    if os.environ.get("APPLY") == "1":
        import gspread
        cells = [gspread.Cell(row=i, col=idx["포지션"] + 1, value=v) for i, v in sorted(fixes.items())]
        _retry("포지션 수정", lambda: ws.update_cells(cells, value_input_option="RAW"))
        print(f"\n수정 완료 — {len(fixes)}행")
    else:
        print(f"\n수정 대상 — {len(fixes)}행 (APPLY=1 이어야 실제 반영)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
