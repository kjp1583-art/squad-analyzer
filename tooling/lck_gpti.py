#!/usr/bin/env python3
"""LCK 선수들의 GPTI 성향유형을 gol.gg 공개 지표로 산출해 lck_gpti.json 으로 낸다.

[2026-08-03 사장님 지시 — A안] 비교 기준은 **LCK 선수끼리**다. 클랜 내전과 프로 경기는
게임 양상이 달라 같은 자로 재면 프로가 전원 한쪽으로 쏠린다. 그래서 백분위를 LCK 풀 안에서
포지션별로 매기고, 웹에서는 '내 유형과 같은 프로'를 유형(네 글자)으로만 이어 붙인다.

축 공식은 웹(index.html computeGPTI)의 리치스탯 4축과 같은 식을 쓴다. 재료 대응:
  kills=Avg kills · deaths=Avg deaths · kp=KP% · killShare=kills/(kills+assists)
  dmg=DPM · gold=GPM · vs=VSPM        (GPTI는 '받은 딜'을 쓰지 않아 전부 확보된다)

gol.gg는 리그 필터가 POST 폼(leagueFilter[])이고 역할은 hidden input(role)이라 역할별로
다섯 번 요청한다. 표에 팀 열이 없어 T1 소속은 팀 페이지 로스터로 따로 붙인다.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

from lxml import html as LH

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
SEASON = os.environ.get("LCK_SEASON", "S16")
LEAGUE = os.environ.get("LCK_LEAGUE", "LCK")
TEAM = os.environ.get("LCK_TEAM", "T1")
MIN_GAMES = int(os.environ.get("LCK_MIN_GAMES", "5"))
OUT = os.environ.get("LCK_OUT", "lck_gpti.json")
ROLES = [("TOP", "탑"), ("JUNGLE", "정글"), ("MID", "미드"), ("BOT", "원딜"), ("SUPPORT", "서폿")]


def fetch(url, data=None, tries=4):
    for i in range(tries):
        try:
            h = dict(UA)
            body = None
            if data is not None:
                h["Content-Type"] = "application/x-www-form-urlencoded"
                body = urllib.parse.urlencode(data, doseq=True).encode()
            return urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=45).read()
        except Exception as e:
            if i == tries - 1:
                print(f"  ! 요청 실패({type(e).__name__}) {url}", flush=True); return None
            time.sleep(3 * (i + 1))


def num(s):
    s = str(s or "").replace("%", "").replace(",", "").strip()
    if not s or s in ("-", "NaN"): return None
    try: return float(s)
    except ValueError: return None


def player_rows(split, role):
    """(선수명 → 지표) — gol.gg 선수 목록을 리그·역할로 걸러서 읽는다."""
    url = f"https://gol.gg/players/list/season-{SEASON}/split-{split}/tournament-ALL/"
    raw = fetch(url, {"cbtournament": "ALL", "role": role, "leaguePost": "true", "leagueFilter[]": [LEAGUE]})
    if not raw: return []
    doc = LH.fromstring(raw)
    heads = [t.text_content().strip() for t in doc.xpath("//table//th")]
    if not heads: return []
    ix = {h: i for i, h in enumerate(heads)}
    need = ("Player", "Games", "Avg kills", "Avg deaths", "Avg assists", "KP%", "DPM", "GPM", "VSPM")
    if any(k not in ix for k in need):
        print(f"  ! 컬럼 부족({role}): {heads}", flush=True); return []
    out = []
    for tr in doc.xpath("//table//tr"):
        a = tr.xpath("./td/a[contains(@href,'player-stats')]")
        if not a: continue
        tds = [c.text_content().strip() for c in tr.xpath("./td")]
        if len(tds) < len(heads): continue
        g = num(tds[ix["Games"]])
        if not g or g < MIN_GAMES: continue
        k, d, asst = num(tds[ix["Avg kills"]]), num(tds[ix["Avg deaths"]]), num(tds[ix["Avg assists"]])
        kp, dpm, gpm, vspm = (num(tds[ix["KP%"]]), num(tds[ix["DPM"]]),
                              num(tds[ix["GPM"]]), num(tds[ix["VSPM"]]))
        if None in (k, d, asst, kp, dpm, gpm, vspm): continue
        out.append({"name": a[0].text_content().strip(), "href": a[0].get("href"), "games": int(g),
                    "kills": k, "deaths": d, "assists": asst, "kp": kp, "dmg": dpm, "gold": gpm, "vs": vspm,
                    "killShare": (k / (k + asst)) if (k + asst) else 0.0,
                    "wr": num(tds[ix["Win rate"]]) if "Win rate" in ix else None,
                    "kda": num(tds[ix["KDA"]]) if "KDA" in ix else None})
    return out


def team_roster(split):
    """팀 이름으로 로스터를 얻는다 — 선수 목록 표엔 팀 열이 없다."""
    raw = fetch(f"https://gol.gg/teams/list/season-{SEASON}/split-{split}/tournament-ALL/")
    if not raw: return set()
    doc = LH.fromstring(raw)
    heads = [t.text_content().strip() for t in doc.xpath("//table//th")]
    ri = heads.index("Region") if "Region" in heads else -1
    href = None
    for tr in doc.xpath("//table//tr"):
        a = tr.xpath("./td/a[contains(@href,'team-stats')]")
        if not a or a[0].text_content().strip().upper() != TEAM.upper(): continue
        tds = [c.text_content().strip() for c in tr.xpath("./td")]
        reg = tds[ri] if 0 <= ri < len(tds) else ""
        href = a[0].get("href")
        if reg.upper() in ("KR", "LCK"): break        # 동명 팀이 있으면 한국 팀 우선
    if not href: return set()
    raw = fetch(href.replace("./", "https://gol.gg/teams/"))
    if not raw: return set()
    t = LH.fromstring(raw)
    return {x.text_content().strip() for x in t.xpath("//a[contains(@href,'player-stats')]")
            if x.text_content().strip()}


def pctile(arr, v):
    if v is None or len(arr) < 3: return 0.5
    below = sum(1 for x in arr if x < v)
    same = sum(1 for x in arr if x == v)
    return (below + same * 0.5) / len(arr)


def build(players):
    """웹 computeGPTI 와 같은 식 — 백분위는 LCK 풀·같은 포지션 안에서."""
    pool = {}
    for p in players:
        d = pool.setdefault(p["pos"], {})
        for m in ("kills", "deaths", "kp", "killShare", "dmg", "gold", "vs"):
            d.setdefault(m, []).append(p[m])
    sgn = lambda x: (x - 0.5) * 2
    conf = lambda v: "뚜렷" if abs(v) >= .5 else ("약간" if abs(v) >= .2 else "중립")
    for p in players:
        P = lambda m: pctile(pool[p["pos"]][m], p[m])
        od = sgn(0.5 * P("dmg") + 0.5 * P("kills"))
        st = sgn(0.35 * P("gold") + 0.15 * P("killShare") + 0.5 * (1 - P("vs")))
        cl = sgn(P("kp"))
        ia = sgn(0.5 * P("deaths") + 0.5 * (1 - P("vs")))
        pick = lambda v, hi, lo: hi if v >= 0 else lo
        p["type"] = pick(od, "O", "D") + pick(st, "S", "T") + pick(cl, "C", "L") + pick(ia, "I", "A")
        p["axes"] = [{"ax": "라인", "v": round(od, 3), "side": pick(od, "공격 O", "수비 D"), "conf": conf(od)},
                     {"ax": "이득", "v": round(st, 3), "side": pick(st, "개인 S", "팀 T"), "conf": conf(st)},
                     {"ax": "팀플", "v": round(cl, 3), "side": pick(cl, "조직 C", "독립 L"), "conf": conf(cl)},
                     {"ax": "전략", "v": round(ia, 3), "side": pick(ia, "본능 I", "계산 A"), "conf": conf(ia)}]
    return players


def main():
    splits = [s for s in os.environ.get("LCK_SPLITS", "Summer,Spring").split(",") if s.strip()]
    players, used = [], None
    for split in splits:
        got = []
        for role, kor in ROLES:
            rows = player_rows(split, role)
            for r in rows: r["pos"] = kor
            got += rows
            print(f"  · {split} {role}: {len(rows)}명", flush=True)
            time.sleep(1)
        if len(got) >= 20:
            players, used = got, split; break
        print(f"  · {split}: 표본 부족({len(got)}명) — 이전 스플릿으로", flush=True)
    if not players:
        print("LCK 선수 데이터를 못 받았다 — 파일을 쓰지 않는다.", file=sys.stderr); return 1

    roster = team_roster(used)
    print(f"  · {TEAM} 로스터: {sorted(roster) if roster else '못 찾음'}", flush=True)
    build(players)
    for p in players:
        p["team"] = TEAM if p["name"] in roster else ""
        p.pop("href", None)
    players.sort(key=lambda p: (p["team"] != TEAM, [k for k, _ in ROLES].index(
        next(r for r, k in ROLES if k == p["pos"])), -p["games"]))

    data = {"updated": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "source": "gol.gg",
            "season": SEASON, "split": used, "league": LEAGUE, "team": TEAM,
            "minGames": MIN_GAMES, "n": len(players), "players": players}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{used} 스플릿 · LCK {len(players)}명 · {TEAM} {sum(1 for p in players if p['team'])}명 → {OUT}")
    for p in players[:8]:
        print(f"   {p['pos']:<3} {p['name']:<14} {p['type']}  {p['games']}판"
              + (f"  [{TEAM}]" if p["team"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
