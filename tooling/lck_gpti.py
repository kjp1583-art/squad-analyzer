#!/usr/bin/env python3
"""LCK 선수들의 GPTI 성향유형을 gol.gg 공개 지표로 산출해 lck_gpti.json 으로 낸다.

[2026-08-03 사장님 지시 — A안] 비교 기준은 **LCK 선수끼리**다. 클랜 내전과 프로 경기는
양상이 달라 같은 자로 재면 프로가 전원 한쪽으로 쏠린다. 백분위를 LCK 풀 안에서 포지션별로
매기고, 웹에서는 '내 유형과 같은 프로'를 유형(네 글자)으로만 이어 붙인다.

축 공식은 웹(index.html computeGPTI)의 리치스탯 4축과 같다. 재료 대응:
  kills=Avg kills · deaths=Avg deaths · kp=KP% · killShare=kills/(kills+assists)
  dmg=DPM · gold=GPM · vs=VSPM        (GPTI는 '받은 딜'을 쓰지 않아 전부 확보된다)

수집 경로(2026-08-03 실측):
  · 선수 목록은 리그·역할 필터가 **먹지 않는다**(POST를 넣어도 전 리그 1138명이 그대로 온다).
    그래서 전체 목록을 받아 player-stats ID로 색인하고,
  · 팀 페이지의 'Role / Player' 표에서 LCK 각 팀의 로스터와 포지션을 얻어 ID로 조인한다.
  · LCK 팀 = 팀 목록의 Region=KR 중 2군(Challengers/Academy/Youth)을 뺀 팀.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

from lxml import html as LH

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
SEASON = os.environ.get("LCK_SEASON", "S16")
REGION = os.environ.get("LCK_REGION", "KR")
TEAM = os.environ.get("LCK_TEAM", "T1")
MIN_GAMES = int(os.environ.get("LCK_MIN_GAMES", "3"))
OUT = os.environ.get("LCK_OUT", "lck_gpti.json")
SECOND = re.compile(r"(challengers|academy|youth)", re.I)      # 2군·아카데미 제외
ROLE_KOR = {"TOP": "탑", "JUNGLE": "정글", "MID": "미드", "BOT": "원딜", "ADC": "원딜", "SUPPORT": "서폿"}
ROLE_ORDER = ["탑", "정글", "미드", "원딜", "서폿"]


def fetch(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read()
        except Exception as e:
            if i == tries - 1:
                print(f"  ! 실패({type(e).__name__}) {url}", flush=True); return None
            time.sleep(3 * (i + 1))


def num(s):
    s = str(s or "").replace("%", "").replace(",", "").strip()
    if not s or s in ("-", "NaN"): return None
    try: return float(s)
    except ValueError: return None


def pid_of(href):
    m = re.search(r"player-stats/(\d+)", str(href or ""))
    return m.group(1) if m else None


def lck_teams(split):
    raw = fetch(f"https://gol.gg/teams/list/season-{SEASON}/split-{split}/tournament-ALL/")
    if not raw: return []
    doc = LH.fromstring(raw)
    heads = [t.text_content().strip() for t in doc.xpath("//table//th")]
    ri = heads.index("Region") if "Region" in heads else -1
    out = []
    for tr in doc.xpath("//table//tr"):
        a = tr.xpath("./td/a[contains(@href,'team-stats')]")
        if not a: continue
        tds = [c.text_content().strip() for c in tr.xpath("./td")]
        if not (0 <= ri < len(tds)) or tds[ri].upper() != REGION.upper(): continue
        name = a[0].text_content().strip()
        if SECOND.search(name): continue
        out.append((name, a[0].get("href").replace("./", "https://gol.gg/teams/")))
    return out


def roster(url):
    """팀 페이지의 'Role / Player' 표 → [(포지션, 선수명, player_id)]"""
    raw = fetch(url)
    if not raw: return []
    doc = LH.fromstring(raw)
    out, seen = [], set()
    for tb in doc.xpath("//table"):
        hs = [x.text_content().strip() for x in tb.xpath(".//th")]
        if "Role" not in hs or "Player" not in hs: continue
        for tr in tb.xpath(".//tr"):
            tds = tr.xpath("./td")
            if len(tds) < 2: continue
            role = ROLE_KOR.get(tds[0].text_content().strip().upper())
            if not role: continue
            a = tr.xpath(".//a[contains(@href,'player-stats')]")
            if not a: continue
            pid = pid_of(a[0].get("href"))
            if not pid or pid in seen: continue
            seen.add(pid)
            out.append((role, tds[1].text_content().strip() or a[0].text_content().strip(), pid))
    return out


def all_player_stats(split):
    """전체 선수 목록(필터가 안 먹으므로 통째로) → {player_id: 지표}"""
    raw = fetch(f"https://gol.gg/players/list/season-{SEASON}/split-{split}/tournament-ALL/")
    if not raw: return {}
    doc = LH.fromstring(raw)
    heads = [t.text_content().strip() for t in doc.xpath("//table//th")]
    ix = {h: i for i, h in enumerate(heads)}
    need = ("Games", "Avg kills", "Avg deaths", "Avg assists", "KP%", "DPM", "GPM", "VSPM")
    if any(k not in ix for k in need):
        print(f"  ! 선수 표 컬럼 부족: {heads}", flush=True); return {}
    out = {}
    for tr in doc.xpath("//table//tr"):
        a = tr.xpath("./td/a[contains(@href,'player-stats')]")
        if not a: continue
        pid = pid_of(a[0].get("href"))
        if not pid: continue
        tds = [c.text_content().strip() for c in tr.xpath("./td")]
        if len(tds) < len(heads): continue
        v = {k: num(tds[ix[k]]) for k in need}
        if any(v[k] is None for k in need): continue
        k, asst = v["Avg kills"], v["Avg assists"]
        out[pid] = {"games": int(v["Games"]), "kills": k, "deaths": v["Avg deaths"], "assists": asst,
                    "kp": v["KP%"], "dmg": v["DPM"], "gold": v["GPM"], "vs": v["VSPM"],
                    "killShare": (k / (k + asst)) if (k + asst) else 0.0,
                    "wr": num(tds[ix["Win rate"]]) if "Win rate" in ix else None,
                    "kda": num(tds[ix["KDA"]]) if "KDA" in ix else None}
    return out


def pctile(arr, v):
    if v is None or len(arr) < 3: return 0.5
    return (sum(1 for x in arr if x < v) + sum(1 for x in arr if x == v) * 0.5) / len(arr)


def build(players):
    """웹 computeGPTI 와 같은 식 — 백분위는 LCK 풀·같은 포지션 안에서."""
    pool = {}
    for p in players:
        d = pool.setdefault(p["pos"], {})
        for m in ("kills", "deaths", "kp", "killShare", "dmg", "gold", "vs"):
            d.setdefault(m, []).append(p[m])
    sgn = lambda x: (x - 0.5) * 2
    conf = lambda v: "뚜렷" if abs(v) >= .5 else ("약간" if abs(v) >= .2 else "중립")
    pick = lambda v, hi, lo: hi if v >= 0 else lo
    for p in players:
        P = lambda m: pctile(pool[p["pos"]][m], p[m])
        od = sgn(0.5 * P("dmg") + 0.5 * P("kills"))
        st = sgn(0.35 * P("gold") + 0.15 * P("killShare") + 0.5 * (1 - P("vs")))
        cl = sgn(P("kp"))
        ia = sgn(0.5 * P("deaths") + 0.5 * (1 - P("vs")))
        p["type"] = pick(od, "O", "D") + pick(st, "S", "T") + pick(cl, "C", "L") + pick(ia, "I", "A")
        p["axes"] = [{"ax": "라인", "v": round(od, 3), "side": pick(od, "공격 O", "수비 D"), "conf": conf(od)},
                     {"ax": "이득", "v": round(st, 3), "side": pick(st, "개인 S", "팀 T"), "conf": conf(st)},
                     {"ax": "팀플", "v": round(cl, 3), "side": pick(cl, "조직 C", "독립 L"), "conf": conf(cl)},
                     {"ax": "전략", "v": round(ia, 3), "side": pick(ia, "본능 I", "계산 A"), "conf": conf(ia)}]
    return players


def main():
    for split in [s.strip() for s in os.environ.get("LCK_SPLITS", "Summer,Spring").split(",") if s.strip()]:
        teams = lck_teams(split)
        print(f"  · {split} {REGION} 1군 팀 {len(teams)}개: {', '.join(n for n, _ in teams)}", flush=True)
        if not teams: continue
        stats = all_player_stats(split)
        print(f"  · 전체 선수 지표 {len(stats)}명", flush=True)
        players, missed = [], []
        for tname, turl in teams:
            rs = roster(turl)
            print(f"     {tname}: 로스터 {len(rs)}명", flush=True)
            for pos, name, pid in rs:
                s = stats.get(pid)
                if not s or s["games"] < MIN_GAMES: missed.append(f"{tname}/{name}"); continue
                players.append(dict(s, pos=pos, name=name, team=tname, pid=pid))
            time.sleep(1)
        if len(players) >= 20:
            if missed: print(f"  · 지표 없음/표본 미달 {len(missed)}명: {', '.join(missed[:12])}", flush=True)
            break
        print(f"  · {split}: 표본 부족({len(players)}명) — 이전 스플릿으로", flush=True)
    else:
        print("LCK 선수 데이터를 못 받았다 — 파일을 쓰지 않는다.", file=sys.stderr); return 1

    build(players)
    players.sort(key=lambda p: (p["team"].upper() != TEAM.upper(), ROLE_ORDER.index(p["pos"]), -p["games"]))
    data = {"updated": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "source": "gol.gg",
            "season": SEASON, "split": split, "region": REGION, "team": TEAM,
            "minGames": MIN_GAMES, "n": len(players),
            "teams": sorted({p["team"] for p in players}), "players": players}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{split} 스플릿 · LCK {len(players)}명 → {OUT}")
    for p in players[:12]:
        print(f"   {p['pos']:<3} {p['name']:<12} {p['team']:<20} {p['type']}  {p['games']}판")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
