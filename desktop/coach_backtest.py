"""고스트밴픽왕 오프라인 백테스트 — '기존 방식'과 '개선 방식'의 밴 추천을 **같은 판**에서 재서 비교한다.

  python3 desktop/coach_backtest.py                      # 합성 200판(기본) · 시드 11
  python3 desktop/coach_backtest.py --trials 400 --seed 7
  python3 desktop/coach_backtest.py --phases 2           # 2페이즈(확정 픽 3↑)만
  python3 desktop/coach_backtest.py --xlsx tmp/sheet_snap/sheet.xlsx   # 실제 시트 스냅샷이 있으면 그걸로
  python3 desktop/coach_backtest.py --out docs/coach_backtest_report.md

⚠️ 이 스크립트는 네트워크를 쓰지 않는다. squad_analyzer.py 는 Windows 전용 import 가 많아
   점수 계산 함수만 AST 로 떼어 쓴다(기존 desktop/*_test.py 와 같은 방식).

무엇을 재나
  · 기존: 바뀌기 전 데이터 계층 그대로 — 포지션 미확정 상대에게는 **전 챔프폭**을 90일 판수순으로 주고,
    위협도 가중 없이 '판수·점유 순'. (프롬프트가 '밥줄 챔프'를 고르던 상황의 하한)
  · 개선: 지금 코드 — 사람 단위 집계 · 최근성 가중 · 포지션 확률 · 등장확률×위협도(`_ban_candidates`).
  · 정답: 그 판에 상대가 **실제로 픽한 챔프**. 밴 후보 top-k 안에 있으면 적중.
  · 오추천: 상대가 그 자리에서 꺼낼 수 없는 챔프(이미 찬 자리 전용·이미 픽 끝난 선수의 챔프)를 후보에 올린 비율.
"""
import argparse
import ast
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "squad_analyzer.py")

LOAD_FUNCS = ("tnorm", "_sheet_date", "_recency_w", "_recency_score", "_pos_prob",
              "_pool_p_show", "_ban_candidates", "_ban_board_lines")
LOAD_CONSTS = ("_ROLES5", "_REC_W", "_REC_OLD_W", "_BAN_LIMIT")


def build_engine(src=SRC):
    """squad_analyzer.py 에서 **점수 계산 함수만** 떼어 실행 가능한 네임스페이스로 만든다."""
    text = open(src, encoding="utf-8").read()
    tree = ast.parse(text)
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in LOAD_FUNCS]
    have = {n.name for n in body}
    missing = set(LOAD_FUNCS) - have
    if missing:
        raise SystemExit(f"squad_analyzer.py 에서 함수를 못 찾음: {sorted(missing)}")
    consts = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id in LOAD_CONSTS:
                consts[n.targets[0].id] = ast.literal_eval(n.value)
    ns = dict(consts)
    ns.update({"time": time, "re": __import__("re"), "math": __import__("math")})
    exec(compile(ast.Module(body=body, type_ignores=[]), src, "exec"), ns)
    return ns


# ── 합성 판 ────────────────────────────────────────────────────────────────
#   포지션별 챔프 풀(클랜에서 실제로 도는 픽들). 챔프는 한 포지션에만 둔다 — '다른 자리 전용 픽'을
#   오추천으로 셀 수 있어야 하기 때문.
POOL = {
    "탑": ["아트록스", "레넥톤", "그라가스", "제이스", "뽀삐", "케넨"],
    "정글": ["브라이어", "녹턴", "세주아니", "리신", "카직스", "바이"],
    "미드": ["아리", "사일러스", "오리아나", "럭스", "제라스", "트위스티드 페이트"],
    "원딜": ["진", "이즈리얼", "카이사", "애쉬", "시비르", "제리"],
    "서폿": ["쓰레쉬", "레오나", "룰루", "노틸러스", "바드", "카르마"],
}
ROLES = ("탑", "정글", "미드", "원딜", "서폿")


def day_str(days):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - days * 86400))


def _add(pool, ch, pos, g, days, wr):
    w = int(round(g * wr))
    cur = pool.get(ch)
    if cur:                     # 같은 챔프가 두 자리 기록을 갖는 경우(플렉스) — 판수를 합친다
        cur["g"] += g
        cur["w"] += w
        cur["days"] = min(cur["days"], days)
        if pos != cur["pos"]:
            cur.setdefault("alt", {})[pos] = cur.get("alt", {}).get(pos, 0) + g
        return
    pool[ch] = {"pos": pos, "g": g, "w": w, "days": days}


def make_player(rng, name, truepos):
    """한 선수의 챔프폭 — 실제 클랜 시트에서 흔한 모양을 흉내낸다.

    · 요즘 밥줄(최근 2~25일, 소수 판) — 이번 판에 실제로 나올 픽
    · 주력(20~110일) · 중간(10~70일)
    · **자리 변경(약 30%의 선수)**: 예전 포지션에 25~70판(25~170일)이 남아 있어, 포지션을 모르면
      '예전 자리 챔프'가 챔프폭의 대부분을 차지한다 — 기존 방식이 여기에 끌리던 실제 사고의 뿌리.
    · **휴면(약 25%의 선수)**: 최근 90일 기록이 5판 미만 → 기존 방식은 통산 판수로 되돌아가
      옛 챔프를 밴 후보로 올린다.
    """
    pool = {}
    mine = list(POOL[truepos])
    rng.shuffle(mine)
    dormant = rng.random() < 0.25
    if dormant:
        _add(pool, mine[0], truepos, rng.randint(2, 4), rng.randint(60, 220), rng.uniform(0.45, 0.65))
        _add(pool, mine[1], truepos, rng.randint(8, 20), rng.randint(90, 320), rng.uniform(0.40, 0.60))
    else:
        _add(pool, mine[0], truepos, rng.randint(3, 9), rng.randint(2, 25), rng.uniform(0.55, 0.75))
        _add(pool, mine[1], truepos, rng.randint(10, 35), rng.randint(20, 110), rng.uniform(0.45, 0.62))
    _add(pool, mine[2], truepos, rng.randint(5, 15), rng.randint(10, 70), rng.uniform(0.40, 0.60))
    others = [r for r in ROLES if r != truepos]
    rng.shuffle(others)
    if rng.random() < 0.30:                      # 자리를 바꾼 선수
        former = others[0]
        _add(pool, rng.choice(POOL[former]), former, rng.randint(25, 70), rng.randint(25, 170), rng.uniform(0.40, 0.60))
        if rng.random() < 0.5:
            _add(pool, rng.choice(POOL[former]), former, rng.randint(8, 25), rng.randint(60, 250), rng.uniform(0.35, 0.55))
    else:                                        # 잡픽 몇 판
        op = others[0]
        _add(pool, rng.choice(POOL[op]), op, rng.randint(3, 10), rng.randint(60, 400), rng.uniform(0.35, 0.55))
    return {"name": name, "pos": truepos, "pool": pool, "dormant": dormant}


def pos_dist(engine, p):
    """그 선수의 포지션별 **최근성 가중** 판수 분포 — 포지션 확률 추론 입력(엔진과 같은 규칙)."""
    d = {}
    for _c, s in p["pool"].items():
        wsc = engine["_recency_score"]([(day_str(s["days"]), s["g"])])[0]
        d[s["pos"]] = d.get(s["pos"], 0) + wsc
        for ap, ag in (s.get("alt") or {}).items():
            d[ap] = d.get(ap, 0) + ag * engine["_REC_OLD_W"]   # 옛 기록(자리만 남은 경우)은 낮은 무게
    return d


def pick_true(engine, rng, p):
    """그 판에 이 선수가 실제로 꺼낸 챔프 — 자기 자리 챔프 중 '최근성 가중 판수 × 승률'로 뽑는다."""
    opts, weights = [], []
    for c, s in p["pool"].items():
        if s["pos"] != p["pos"]:
            continue
        wsc, _n90, _n14 = engine["_recency_score"]([(day_str(s["days"]), s["g"])])
        opts.append(c)
        weights.append(max(0.01, wsc * (0.4 + s["w"] / max(1, s["g"]))))
    return rng.choices(opts, weights=weights, k=1)[0] if opts else ""


# ── 두 방식의 밴 후보 ───────────────────────────────────────────────────────
def old_board(players, remaining, ep_by_pu, dead):
    """바뀌기 전 방식 — 포지션을 모르면 전 챔프폭을 90일 판수순으로, 위협도 가중 없이 점유순."""
    cand, order = {}, []
    for p in remaining:
        ep = ep_by_pu.get(p["name"], "")
        rows = []
        for c, s in p["pool"].items():
            if c in dead:
                continue
            if ep and s["pos"] != ep:
                continue
            rows.append((s["g"] if s["days"] <= 90 else 0, s["g"], c))
        if not rows:
            continue
        t90 = sum(r[0] for r in rows)
        tg = sum(r[1] for r in rows)
        base = t90 if t90 >= 5 else tg
        keep = []
        for g90, g, c in rows:
            share = ((g90 if t90 >= 5 else g) / base * 100) if base else 0
            if share >= 10 and g >= 2:
                keep.append((share, g90, g, c))
        if not keep:
            keep = [(0.0, g90, g, c) for g90, g, c in sorted(rows, reverse=True)[:2]]
        keep.sort(key=lambda x: (-x[1], -x[2]))
        for share, g90, g, c in keep[:6]:
            if c not in cand:
                cand[c] = (share, g90)
                order.append(c)
    order.sort(key=lambda c: (-cand[c][0], -cand[c][1]))
    return order


def new_board(engine, remaining, ep_by_pu, open_pos, dead):
    """지금 코드 — 포지션 확률 + 최근성 가중 + 등장확률×위협도."""
    dists = [(p["name"], pos_dist(engine, p)) for p in remaining if not ep_by_pu.get(p["name"])]
    probs = engine["_pos_prob"](open_pos, dists) if dists else {}
    rows_all = []
    for p in remaining:
        nm = p["name"]
        ep = ep_by_pu.get(nm, "")
        prows = []
        for c, s in p["pool"].items():
            if c in dead:
                continue
            wsc, n90, n14 = engine["_recency_score"]([(day_str(s["days"]), s["g"])])
            prows.append({"champ": c, "g": s["g"], "w": s["w"], "wscore": wsc, "n90": n90, "n14": n14,
                          "last": "", "posg": {s["pos"]: [s["g"], s["w"]]}, "posw": {s["pos"]: wsc}})
        for r in engine["_pool_p_show"](prows, ep=ep, probs=probs.get(nm), limit=12):
            r["name"] = nm
            rows_all.append(r)
    cands = engine["_ban_candidates"](rows_all, ally_champs=[], dead=dead, limit=max(10, engine.get("_BAN_LIMIT", 10)))
    return [c["champ"] for c in cands], cands


def evaluate(board, remaining, true_pick, dead):
    """적중(그 판 실제 픽이 후보 top-k에 있나) · 커버리지 · 오추천(그 자리에서 나올 수 없는 챔프)."""
    poss = {p["name"]: {c for c, s in p["pool"].items() if s["pos"] == p["pos"] and c not in dead}
            for p in remaining}
    all_poss = set().union(*poss.values()) if poss else set()
    picks = {true_pick[p["name"]] for p in remaining if true_pick.get(p["name"])}
    out = {}
    for k in (1, 3, 5):
        out[f"hit{k}"] = 1.0 if any(c in picks for c in board[:k]) else 0.0
    out["cov10"] = (sum(1 for p in remaining if true_pick.get(p["name"]) in board[:10]) / len(remaining)) if remaining else 0.0
    top5 = board[:5]
    out["picked5"] = (sum(1 for c in top5 if c in picks) / len(top5)) if top5 else 0.0
    out["waste5"] = (sum(1 for c in top5 if c not in all_poss) / len(top5)) if top5 else 0.0
    off = set()
    for p in remaining:
        for c, s in p["pool"].items():
            if s["pos"] != p["pos"]:
                off.add(c)
    out["offpos5"] = (sum(1 for c in top5 if c in off and c not in all_poss) / len(top5)) if top5 else 0.0
    return out


def sim_trial(engine, rng, phase):
    """한 판: 상대 5명 · 포지션 배정 · (2페이즈면) 일부 확정 픽 → 두 방식의 밴 후보를 같은 조건으로 만든다."""
    roles = list(ROLES)
    rng.shuffle(roles)
    players = [make_player(rng, f"P{i + 1}", roles[i]) for i in range(5)]
    picked_n = rng.randint(2, 3) if phase == 2 else 0
    picked = rng.sample(players, picked_n) if picked_n else []
    ep_by_pu, dead = {}, set()
    for p in picked:
        ch = pick_true(engine, rng, p)
        ep_by_pu[p["name"]] = p["pos"]          # 확정 픽 = 그 자리가 찼다
        dead.add(ch)
    remaining = [p for p in players if p["name"] not in ep_by_pu]
    open_pos = [r for r in ROLES if r not in {p["pos"] for p in picked}]
    true_pick = {p["name"]: pick_true(engine, rng, p) for p in remaining}
    old = old_board(players, remaining, ep_by_pu, dead)
    new, cands = new_board(engine, remaining, ep_by_pu, open_pos, dead)
    # 🎯 등장확률의 '변별력' — 실제 픽에 준 확률이 전체 후보 평균보다 몇 배인가(lift). 1.0 이면 동전던지기.
    ps = {c["champ"]: c["p_show"] for c in cands}
    _tp = [ps[c] for c in true_pick.values() if c in ps]
    _ap = list(ps.values())
    lift = (statistics.fmean(_tp) / statistics.fmean(_ap)) if _tp and _ap and statistics.fmean(_ap) else 0.0
    return {"old": evaluate(old, remaining, true_pick, dead),
            "new": evaluate(new, remaining, true_pick, dead),
            "lift": lift,
            "old_board": old[:5], "new_board": new[:5], "cands": cands}


METRICS = (("picked5", "밴 정밀도@5 (%)"), ("hit1", "적중@1 (%)"), ("hit3", "적중@3 (%)"),
           ("hit5", "적중@5 (%)"), ("cov10", "커버리지@10 (%)"), ("waste5", "오추천@5 (%)"))


def _summ(rows, key):
    vals = [r[key] for r in rows]
    m = statistics.fmean(vals) * 100
    sd = statistics.pstdev(vals) * 100 if len(vals) > 1 else 0.0
    return m, sd


def report_table(rows):
    lines = [f"{'지표':<18}{'기존':>10}{'개선':>10}{'차이':>10}"]
    lines.append("-" * 48)
    for k, lab in METRICS:
        om, osd = _summ(rows, "old_" + k)
        nm, nsd = _summ(rows, "new_" + k)
        lines.append(f"{lab:<18}{om:>9.1f}{nm:>10.1f}{nm - om:>+10.1f}   (±{osd:.1f}/±{nsd:.1f})")
    return lines


def run_synthetic(engine, trials=200, seed=11, phases=(1, 2)):
    rng = random.Random(seed)
    rows = []
    for i in range(trials):
        ph = phases[i % len(phases)]
        r = sim_trial(engine, rng, ph)
        row = {"phase": ph, "lift": r["lift"]}
        for side in ("old", "new"):
            for k, _lab in METRICS:
                row[f"{side}_{k}"] = r[side][k]
        rows.append(row)
    return rows


# ── 실제 시트 스냅샷(있으면) ────────────────────────────────────────────────
def load_sheet_games(path):
    """CLASSIC_NORMAL 스냅샷(xlsx) → [{'gid','rows':[...]}] . openpyxl 없거나 형식이 다르면 None."""
    try:
        import openpyxl
    except Exception:
        print("[backtest] openpyxl 이 없어 실측 모드를 건너뜁니다(합성으로 진행)", flush=True)
        return None
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb["CLASSIC_NORMAL"] if "CLASSIC_NORMAL" in wb.sheetnames else wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        hdr = [str(x or "") for x in next(it)]
        need = {"게임ID", "PUUID", "소환사명", "진영", "포지션", "챔피언", "결과", "날짜"}
        if not need <= set(hdr):
            print(f"[backtest] 시트에 필요한 열이 없습니다: {sorted(need - set(hdr))}", flush=True)
            return None
        rows = [dict(zip(hdr, r)) for r in it]
        return rows
    except Exception as e:
        print(f"[backtest] 스냅샷 읽기 실패(무시): {e}", flush=True)
        return None


def run_sheet(engine, rows, limit=None):
    """실측 모드 — 판마다 한쪽 팀을 '상대'로 두고, 그 판의 실제 픽을 정답으로 밴 후보를 잰다.

    ⚠️ 챔프폭은 그 판 자체를 포함한 전 기간 기록에서 만든다(leave-one-out 없음) — 두 방식에 똑같이
       유리하게 작용하므로 **방식 간 비교**에는 쓰고, 절대 적중률로 인용하지 말 것.
    """
    by_gid = {}
    for r in rows:
        if not r.get("게임ID"):
            continue
        by_gid.setdefault(str(r["게임ID"]), []).append(r)
    games = [g for g in by_gid.values() if len(g) >= 8]
    if limit:
        games = games[:limit]
    # 선수(사람)별 챔프폭 — puuid 기준
    pool_by_pu = {}
    for r in rows:
        pu = str(r.get("PUUID") or "").strip().lower()
        ch = str(r.get("챔피언") or "").strip()
        ps = str(r.get("포지션") or "").strip()
        if not pu or not ch or ps not in ROLES:
            continue
        try:
            ds = engine["_sheet_date"](r.get("날짜"))
        except Exception:
            ds = None
        days = max(0.0, (time.time() - ds) / 86400.0) if ds else 400.0
        win = 1 if str(r.get("결과") or "").strip() == "승리" else 0
        pool = pool_by_pu.setdefault(pu, {})
        cur = pool.get(ch)
        if cur:
            cur["g"] += 1; cur["w"] += win; cur["days"] = min(cur["days"], days)
            if ps != cur["pos"]:
                cur.setdefault("alt", {})[ps] = cur.get("alt", {}).get(ps, 0) + 1
        else:
            pool[ch] = {"pos": ps, "g": 1, "w": win, "days": days}
    out = []
    for g in games:
        if len(out) >= (limit or len(games)):
            break
        blues = [r for r in g if str(r.get("진영") or "").strip() == "블루팀"]
        reds = [r for r in g if str(r.get("진영") or "").strip() == "레드팀"]
        if len(blues) < 4 or len(reds) < 4:
            continue
        enemies = reds
        players = []
        for r in enemies:
            pu = str(r.get("PUUID") or "").strip().lower()
            ps = str(r.get("포지션") or "").strip()
            if pu not in pool_by_pu:
                continue
            players.append({"name": pu, "pos": ps, "pool": pool_by_pu[pu]})
        if len(players) < 4:
            continue
        true_pick = {str(r.get("PUUID") or "").strip().lower(): str(r.get("챔피언") or "").strip() for r in enemies}
        dead = {str(r.get("챔피언") or "").strip() for r in g if str(r.get("챔피언") or "").strip()}
        for p in players:
            dead.discard(true_pick.get(p["name"], "")) if False else None
        true_set = set(true_pick.values())
        dead -= true_set            # 그 판 픽은 '이미 나온' 것이지만 정답이므로 후보에서 빼지 않는다
        open_pos = [r for r in ROLES if r not in {p["pos"] for p in players}]
        old = old_board(players, players, {}, dead)
        new, _ = new_board(engine, players, {}, open_pos or list(ROLES), dead)
        row = {"phase": 0}
        eo = evaluate(old, players, true_pick, dead)
        en = evaluate(new, players, true_pick, dead)
        for k, _lab in METRICS:
            row["old_" + k] = eo[k]
            row["new_" + k] = en[k]
        out.append(row)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="고스트밴픽왕 밴 추천 백테스트(오프라인)")
    ap.add_argument("--trials", type=int, default=200, help="합성 판 수(기본 200)")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--phases", type=str, default="12", help="1 / 2 / 12 (기본 둘 다)")
    ap.add_argument("--xlsx", type=str, default="", help="시트 스냅샷 경로(있으면 실측 모드도 함께)")
    ap.add_argument("--out", type=str, default="", help="리포트를 쓸 markdown 경로")
    args = ap.parse_args(argv)

    eng = build_engine()
    phases = tuple(int(x) for x in str(args.phases) if x in "12") or (1, 2)
    t0 = time.time()
    rows = run_synthetic(eng, trials=args.trials, seed=args.seed, phases=phases)
    print(f"\n=== 고스트밴픽왕 밴 추천 백테스트 · 합성 {args.trials}판 · 시드 {args.seed} · 페이즈 {phases} ===")
    for ln in report_table(rows):
        print(ln)
    _lifts = [r["lift"] for r in rows if r.get("lift")]
    if _lifts:
        print(f"{'등장확률 lift':<18}{'':>10}{statistics.fmean(_lifts):>10.2f}"
              f"   (실제 픽에 준 확률 ÷ 전체 후보 평균 — 1.0 이면 무변별)")
    for ph in phases:
        sub = [r for r in rows if r["phase"] == ph]
        if sub:
            print(f"\n[{ph}페이즈] {len(sub)}판")
            for ln in report_table(sub):
                print("  " + ln)

    sheet_rows = None
    if args.xlsx:
        data = load_sheet_games(args.xlsx)
        if data:
            sheet_rows = run_sheet(eng, data)
            if sheet_rows:
                print(f"\n=== 실측 모드(시트 스냅샷) · {len(sheet_rows)}판 — 챔프폭에 그 판이 포함됨(방식 비교용) ===")
                for ln in report_table(sheet_rows):
                    print(ln)
    print(f"\n(계산 {time.time() - t0:.1f}s)")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("# 고스트밴픽왕 밴 추천 백테스트\n\n")
            f.write(f"- 합성 {args.trials}판 · 시드 {args.seed} · 페이즈 {phases} · 생성 {time.strftime('%Y-%m-%d %H:%M')}\n")
            f.write("- '기존' = 포지션 미확정 상대에게 전 챔프폭을 90일 판수순으로 주던 방식, "
                    "'개선' = 사람 단위·최근성 가중·포지션 확률·등장확률×위협도.\n")
            f.write("- 정답 = 그 판에 상대가 실제로 픽한 챔프. 오추천 = 그 자리에서 나올 수 없는 챔프를 후보에 올린 비율.\n\n")
            _l = [r["lift"] for r in rows if r.get("lift")]
            f.write("## 전체\n\n```\n" + "\n".join(report_table(rows))
                    + (f"\n등장확률 lift  {statistics.fmean(_l):.2f}" if _l else "") + "\n```\n")
            for ph in phases:
                sub = [r for r in rows if r["phase"] == ph]
                if sub:
                    f.write(f"\n## {ph}페이즈 ({len(sub)}판)\n\n```\n" + "\n".join(report_table(sub)) + "\n```\n")
            if sheet_rows:
                f.write("\n## 실측 모드(시트 스냅샷)\n\n```\n" + "\n".join(report_table(sheet_rows)) + "\n```\n")
        print(f"[backtest] 리포트 저장 — {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
