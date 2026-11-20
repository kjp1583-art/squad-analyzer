#!/usr/bin/env python3
"""🔁 자동 개선 루프 — 신호 수집. 매 회차 맨 처음에 돌린다(LOOP.md 2단계).

사용:
  python3 tooling/improve/signals.py --since <지난 회차 epoch> \
      --bot-src /home/user/squad-naejeon-bot/bot.py --version-file version.txt

보는 것:
  1. 봇 /health — 살아 있나 · 돌고 있는 bot.py 해시가 main 의 bot.py 와 같나(배포가 실제로 올라왔나) · since 이후 오류
  2. 시트(공개 gviz CSV · 인증 불필요) — 결과 대기 고착(3시간↑) · KDA 가 날짜로 바뀐 칸 · 같은 판 같은 PUUID 중복행 ·
     10명이 아닌 판(최근 7일)
  3. VERSIONS — 최근 3일 실행한 분석기 버전 분포(최신 version.txt 대비 뒤처진 PC)

출력: 사람이 읽는 요약 여러 줄 + 마지막 한 줄 `SIGNALS_JSON {...}`(기계용). 네트워크 실패는 그 항목만 '확인 불가'로 둔다.
"""
import argparse, csv, datetime, hashlib, io, json, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
BOT_HEALTH = "https://hth3thmujs.apps.bot-hosting.cloud/health"
KST = datetime.timezone(datetime.timedelta(hours=9))


RELAY_USED = []   # 직접 접속이 막혀 relay-data 사본으로 읽은 항목(2026-10-01)


def _relay_text(path):
    """🛰 relay-data 브랜치(Actions 가 3시간마다 올리는 사본)에서 파일 읽기 — 클로드 세션의 네트워크 정책이 봇·시트를 막을 때의 우회로(GitHub 는 열려 있다)."""
    import os, subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    top = subprocess.run(["git", "-C", here, "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or here
    if not getattr(_relay_text, "fetched", False):
        subprocess.run(["git", "-C", top, "fetch", "-q", "origin", "relay-data"], capture_output=True, text=True, timeout=60)
        _relay_text.fetched = True
    r = subprocess.run(["git", "-C", top, "show", f"origin/relay-data:{path}"], capture_output=True, text=True, timeout=30)
    if r.returncode != 0: raise RuntimeError(f"relay-data 에 {path} 없음")
    return r.stdout


def relay_age_min():
    try: return round((time.time() - json.loads(_relay_text("meta.json")).get("at", 0)) / 60)
    except Exception: return None


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "squad-improve-loop"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as direct_err:
        # 직접 접속이 막힘 → 릴레이 사본(봇 /health · 시트 탭). 사본에 없는 주소면 원래 오류를 그대로 올린다.
        rel = None
        if url.startswith(BOT_HEALTH): rel = "bot_health.json"
        else:
            m = re.search(r"[?&]sheet=([^&]+)", url)
            if m and "docs.google.com" in url: rel = f"sheet_{urllib.parse.unquote(m.group(1))}.csv"
        if not rel: raise
        try:
            txt = _relay_text(rel)
        except Exception:
            raise direct_err
        RELAY_USED.append(rel)
        return txt


def tab(name):
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&headers=1"
           f"&sheet={urllib.parse.quote(name)}")
    rows = list(csv.reader(io.StringIO(_get(url, 90))))
    if not rows: return [], []
    return rows[0], rows[1:]


def when(s):
    """'2026-09-26 23:21' · '2026-08-13 2:18' · '2026-09-26' → KST datetime (못 읽으면 None)."""
    m = re.match(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?", str(s or ""))
    if not m: return None
    y, mo, d, h, mi = (int(x) if x else 0 for x in m.groups())
    try: return datetime.datetime(y, mo, d, h, mi, tzinfo=KST)
    except ValueError: return None


def bot_health(since, bot_src):
    out = {"ok": False}
    try:
        h = json.loads(_get(BOT_HEALTH, 20))
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:200]
        return out
    out.update(ok=True, up_min=round(h.get("up", 0) / 60), ready=h.get("ready"), guild=h.get("guild"),
               latency_ms=h.get("latency_ms"), src=h.get("src"))
    if bot_src:
        try:
            main = hashlib.sha256(open(bot_src, "rb").read()).hexdigest()[:16]
            out["main_src"] = main
            out["deployed"] = (main == h.get("src"))
        except Exception as e:
            out["main_src_error"] = type(e).__name__
    errs = [e for e in (h.get("errors") or []) if e.get("t", 0) > since]
    out["errors_new"] = [e for e in errs if not str(e.get("head", "")).startswith("[·]")]
    out["breadcrumbs_new"] = len(errs) - len(out["errors_new"]) + sum(1 for c in (h.get("crumbs") or []) if c.get("t", 0) > since)   # 2026-09-27~ 빵조각은 crumbs 칸
    out["errors_by_loc"] = Counter((e.get("loc") or e.get("head", "")[:60]) for e in out["errors_new"]).most_common(10)
    out["errors_head"] = {}   # 위치별 대표 한 줄(명령·예외) — 위치만으론 원인을 못 짚는다
    for e in out["errors_new"]: out["errors_head"].setdefault(e.get("loc") or e.get("head", "")[:60], str(e.get("head", ""))[:220])
    return out


def sheet_checks(now):
    res = {}
    for name in ("CLASSIC_NORMAL", "KIWI_KIWI"):
        r = {"ok": False}
        try:
            H, rows = tab(name)
            ci = {h: i for i, h in enumerate(H)}
            need = ["게임ID", "날짜", "PUUID", "결과", "KDA"]
            has_eval = "매치평가" in ci
            if any(n not in ci for n in need):
                r["error"] = f"열 없음: {[n for n in need if n not in ci]}"; res[name] = r; continue
            g = defaultdict(list)
            for row in rows:
                if len(row) > max(ci.values()): g[row[ci["게임ID"]]].append(row)
            stuck, coerced30, coerced_all, dup, odd, n7, contra = [], 0, 0, [], [], 0, []
            for gid, rs in g.items():
                t = when(rs[0][ci["날짜"]])
                age_h = (now - t).total_seconds() / 3600 if t else None
                res_vals = [x[ci["결과"]] for x in rs]
                kc = sum(1 for x in rs if re.match(r"^20\d\d/\d+/\d+$", x[ci["KDA"]].strip()))
                coerced_all += kc
                if age_h is not None and age_h <= 24 * 30: coerced30 += kc
                if age_h is not None and age_h > 3 and any(v == "결과 대기" for v in res_vals):
                    if age_h <= 24 * 14: stuck.append((gid, rs[0][ci["날짜"]]))
                if age_h is not None and age_h <= 24 * 7:
                    n7 += 1
                    pc = Counter(x[ci["PUUID"]].strip().lower() for x in rs if x[ci["PUUID"]].strip())
                    d = sum(c - 1 for c in pc.values() if c > 1)
                    if d: dup.append((gid, d))
                    # [A-45] 진영·결과 뒤바뀜 탐지(11/20 #8464934822 사고): 협곡에서 MVP 는 승리 팀 · ACE 는 패배 팀 몫인데 반대면 결과가 거꾸로 적힌 판
                    if has_eval and name == "CLASSIC_NORMAL":
                        ev = [(x[ci["매치평가"]].strip().upper(), x[ci["결과"]].strip()) for x in rs]
                        if any(e == "MVP" and v == "패배" for e, v in ev) or any(e == "ACE" and v == "승리" for e, v in ev): contra.append(gid)
                    # 칼바람은 4:4(8명)·3:3 판도 정상 — 양 팀 인원이 같고 6명 이상이면 이상으로 보지 않는다(협곡은 10명 고정)
                    ok_size = len(rs) == 10
                    if name == "KIWI_KIWI" and "진영" in ci and len(rs) >= 6:
                        tc = Counter(x[ci["진영"]] for x in rs)
                        ok_size = ok_size or (len(tc) == 2 and len(set(tc.values())) == 1)
                    if not ok_size and not all(v == "무효" for v in res_vals): odd.append((gid, len(rs)))
            r.update(ok=True, games=len(g), games_7d=n7, stuck_results_14d=stuck, kda_date_coerced_30d=coerced30,
                     kda_date_coerced_all=coerced_all, dup_rows_7d=dup, non10_games_7d=odd, eval_contradiction_7d=contra)
        except Exception as e:
            r["error"] = f"{type(e).__name__}: {e}"[:200]
        res[name] = r
    return res


def versions(now, version_file):
    r = {"ok": False}
    try:
        latest = open(version_file, encoding="utf-8-sig").read().strip() if version_file else ""
        H, rows = tab("VERSIONS")
        ci = {h: i for i, h in enumerate(H)}
        recent = []
        for row in rows:
            t = when(row[ci["마지막 실행"]]) if "마지막 실행" in ci else None
            if t and (now - t).total_seconds() <= 3 * 86400: recent.append(row[ci["버전"]].strip())
        dist = Counter(recent)
        r.update(ok=True, latest=latest, active_3d=len(recent), dist=dist.most_common(),
                 behind=sum(c for v, c in dist.items() if latest and v != latest))
    except Exception as e:
        r["error"] = f"{type(e).__name__}: {e}"[:200]
    return r


def actions_check(now):
    """[A-37] 워크플로별 '마지막 성공 시각' 점검. 주 1회짜리 워크플로가 몇 주째 실패해도 '최근 24시간 실패'만 보면 안 보인다(A-36 사고).
    `gh api` 가 있을 때만 돈다(없으면 건너뜀). 워크플로마다 따로 최근 실행 8개를 본다(잦은 워크플로가 주 1회짜리를 100개 창 밖으로 밀어내지 못하게).
    대상: 최근 8회 안에 스케줄(cron) 실행이 있는 워크플로만(수동·일회성 제외). 표시 기준: 마지막 완료 실행이 실패 · 또는 최근 8개에 성공이 없음 · 또는 마지막 성공이 8일 이상 전."""
    if not shutil.which("gh"): return {"ok": False, "error": "gh 없음"}
    def gh(path, jq):
        r = subprocess.run(["gh", "api", path, "--jq", jq], capture_output=True, text=True, timeout=60)
        return r.stdout.splitlines() if r.returncode == 0 else None
    out = {"ok": True, "repos": {}, "flag": []}
    nowu = datetime.datetime.now(datetime.timezone.utc)
    for repo in ("kjp1583-art/squad-analyzer", "kjp1583-art/squad-naejeon-bot"):
        try:
            wfs = gh(f"repos/{repo}/actions/workflows?per_page=100", '.workflows[]|select(.state=="active")|[.id,.name]|@tsv')
            if wfs is None: out["repos"][repo] = {"error": "workflows 조회 실패"}; continue
            res = {}
            for line in wfs:
                wid, nm = line.split("\t", 1)
                rows = gh(f"repos/{repo}/actions/workflows/{wid}/runs?per_page=8", '.workflow_runs[]|[.created_at,.conclusion//"",.event]|@tsv')
                if rows is None: res[nm] = {"error": "runs 조회 실패"}; continue
                allr = [r.split("\t") for r in rows]
                if not any(len(r) > 2 and r[2] == "schedule" for r in allr): continue   # 수동·일회성 워크플로는 점검 대상 아님
                done = [r for r in allr if r[1] in ("success", "failure")]
                last = done[0] if done else None
                ok = next((r[0] for r in done if r[1] == "success"), None)
                ok_age = (nowu - datetime.datetime.fromisoformat(ok.replace("Z", "+00:00"))).total_seconds() / 86400 if ok else None
                res[nm] = {"last": last, "ok_age_d": round(ok_age, 1) if ok_age is not None else None}
                if not done: continue   # 아직 한 번도 안 돈 워크플로는 표시 안 함
                if last[1] == "failure" or ok_age is None or ok_age >= 8:
                    out["flag"].append(f"{repo.split('/')[1]}:{nm} (마지막={last[1]} · 마지막 성공 {'%.1f일 전' % ok_age if ok_age is not None else '최근 8회 안에 없음'})")
            out["repos"][repo] = res
        except Exception as e:
            out["repos"][repo] = {"error": str(e)[:120]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=float, default=time.time() - 86400, help="이 epoch 이후 오류만(기본 24시간)")
    ap.add_argument("--bot-src", default="", help="main 의 bot.py 경로(배포 해시 비교)")
    ap.add_argument("--version-file", default="", help="분석기 최신 version.txt 경로")
    a = ap.parse_args()
    now = datetime.datetime.now(KST)
    out = {"at": now.strftime("%Y-%m-%d %H:%M KST"), "since": int(a.since),
           "bot": bot_health(a.since, a.bot_src), "sheet": sheet_checks(now), "versions": versions(now, a.version_file), "actions": actions_check(now)}

    b = out["bot"]
    print(f"== 신호 {out['at']} (since {datetime.datetime.fromtimestamp(a.since, KST):%m-%d %H:%M})")
    if RELAY_USED:
        age = relay_age_min()
        out["relay"] = {"used": sorted(set(RELAY_USED)), "age_min": age}
        print(f"🛰 직접 접속이 막혀 GitHub 릴레이 사본으로 읽음({', '.join(sorted(set(RELAY_USED)))}) — 사본 나이 {age if age is not None else '?'}분 · 봇 '현재' 상태·배포 일치는 그 시각 기준")
    if b.get("ok"):
        dep = {True: "배포 일치", False: "⚠ 배포 불일치(main 과 다름)", None: "배포 비교 안 함"}[b.get("deployed")]
        print(f"봇: 가동 {b['up_min']}분 · ready={b['ready']} · {dep} · 새 오류 {len(b['errors_new'])}건 · 빵조각 {b['breadcrumbs_new']}건")
        for loc, n in b["errors_by_loc"]: print(f"   - {n}× {loc}  ← {b.get('errors_head', {}).get(loc, '')}")
    else:
        print(f"봇: ⚠ /health 응답 없음 — {b.get('error')}")
    for name, r in out["sheet"].items():
        if not r.get("ok"): print(f"시트 {name}: 확인 불가 — {r.get('error')}"); continue
        print(f"시트 {name}: 최근7일 {r['games_7d']}판 · 결과대기 고착 {len(r['stuck_results_14d'])} · "
              f"KDA 날짜오염 30일 {r['kda_date_coerced_30d']}(전체 {r['kda_date_coerced_all']}) · "
              f"중복행 {len(r['dup_rows_7d'])}판 · 10명아닌판 {len(r['non10_games_7d'])}"
              + (f" · ⚠ MVP/ACE-결과 모순 {len(r['eval_contradiction_7d'])}판 {r['eval_contradiction_7d'][:3]}" if r.get('eval_contradiction_7d') else ""))
    v = out["versions"]
    if v.get("ok"): print(f"분석기: 최신 {v['latest']} · 최근3일 실행 {v['active_3d']}대 · 뒤처짐 {v['behind']}대 · {v['dist'][:5]}")
    else: print(f"분석기 버전: 확인 불가 — {v.get('error')}")
    ac = out["actions"]
    if not ac.get("ok"): print(f"워크플로 점검: 건너뜀 — {ac.get('error')}")
    elif ac["flag"]: print("⚠ 워크플로 주의(마지막 실행 실패 또는 성공 8일↑ 전): " + " · ".join(ac["flag"]))
    else: print(f"워크플로 점검: 이상 없음(저장소 2곳 · 워크플로 {sum(len(r) for r in ac['repos'].values() if 'error' not in r)}개 마지막 실행 모두 성공 · 성공 8일 이내)")
    print("SIGNALS_JSON " + json.dumps(out, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
