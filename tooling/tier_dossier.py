#!/usr/bin/env python3
"""내부티어 문답용 다축 분석 — QnA 답변의 '재탕' 방지용 근거 생성기.

"내 내부티어 어때?" 질문에 승률·AI점수만으로 답하면 사람만 바뀌고 문장이 똑같아진다.
이 스크립트는 같은 질문에 서로 다른 이야기가 나오도록 7개 축을 계산해 내놓는다.
클랜 문화("내 티어가 너무 높게 잡혔다, 나 그 정도 아니다")를 정면으로 검증하는 ①이 핵심 축.

  ① 맞라이너 티어 대비 성적  — 위 티어 상대로 밀리는가 (억울함의 진위)
  ② 시너지·천적            — 누구와 함께면 강하고 누구를 만나면 지는가
  ③ 시간 추세              — 최근 3개월 vs 그 이전, 월별 궤적
  ④ 피밴율                 — 상대가 얼마나 경계하는가
  ⑤ 게임 양상별            — 장단기전, 이기는 판 굳히기 vs 지는 판 버티기
  ⑥ 십이귀월과의 거리       — 다음 재편에서 뒤집을 수 있는가
  ⑦ 솔랭과 내전의 괴리      — 밖에서의 실력과 안에서의 성적이 어긋나는가

사용:
  python3 tooling/tier_dossier.py sheet.xlsx "닉네임"      # 한 명 상세
  python3 tooling/tier_dossier.py sheet.xlsx --grudge      # 억울지수 랭킹(전원)
"""
import argparse, datetime, json, math, re, sys
from collections import defaultdict

import openpyxl

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from sibguiwol import (TIER_MIN_GAMES, build_identity, compute, load, mean, norm,  # noqa: E402
                       read_tab, tnorm)

TIER_ORDER = ["0", "1上", "1中", "1下", "2上", "2中", "2下", "3上", "3中", "3下"]
TIER_RANK = {t: i for i, t in enumerate(TIER_ORDER)}
MIN_LANE_GAMES = 10      # 맞라인 표본 최소치
RECENT_DAYS = 90


def _date(s):
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(s or ""))
    return datetime.date(int(m[1]), int(m[2]), int(m[3])) if m else None


class Dossier:
    def __init__(self, path):
        self.raw, self.tier_raw, self.alt, self.solo = load(path)
        self.canon_of_row, self.aliases, _ = build_identity(self.raw, self.alt)

        seen, self.games = set(), defaultdict(list)
        for r in self.raw:
            gid = r.get("게임ID")
            if not gid: continue
            key = (gid, r.get("PUUID") or r.get("소환사명"), r.get("챔피언"), r.get("포지션"), r.get("진영"))
            if key in seen: continue
            seen.add(key)
            r["_canon"] = self.canon_of_row(r)
            self.games[gid].append(r)

        self.rows_of = defaultdict(list)
        for rows in self.games.values():
            for r in rows: self.rows_of[r["_canon"]].append(r)

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        self.wb = wb

    def tier_of(self, name):
        t = self.tier_raw.get(tnorm(name))
        if t: return t
        for a in self.aliases.get(name, ()):
            t = self.tier_raw.get(tnorm(a))
            if t: return t
        return None

    def resolve(self, query):
        """입력 닉 → 대표닉. 부분 일치도 허용."""
        q = tnorm(query)
        for nm in self.rows_of:
            if tnorm(nm) == q: return nm
        for nm in self.rows_of:
            if q and q in tnorm(nm): return nm
        for nm in self.rows_of:
            if any(q == tnorm(a) for a in self.aliases.get(nm, ())): return nm
        return None

    # ---------- ① 맞라이너 티어 대비 성적 ----------
    def lane_vs_tier(self, name=None):
        """포지션이 같고 진영이 다른 2인을 맞라이너로 보고, 상대 티어 등급별 승패를 센다."""
        stat = defaultdict(lambda: {"up_w": 0, "up_n": 0, "dn_w": 0, "dn_n": 0, "ev_w": 0, "ev_n": 0,
                                    "beat_up": [], "lost_dn": []})
        for gid, rows in self.games.items():
            by_pos = defaultdict(list)
            for r in rows:
                p, s = str(r.get("포지션") or ""), str(r.get("진영") or "")
                if p and s: by_pos[p].append(r)
            for pos, ps in by_pos.items():
                if len(ps) != 2: continue
                a, b = ps
                if str(a.get("진영")) == str(b.get("진영")): continue
                for me, opp in ((a, b), (b, a)):
                    mt, ot = self.tier_of(me["_canon"]), self.tier_of(opp["_canon"])
                    if mt not in TIER_RANK or ot not in TIER_RANK: continue
                    res = str(me.get("결과") or "")
                    if res not in ("승리", "패배"): continue
                    k = me["_canon"]
                    if name and k != name: continue
                    d = stat[k]; w = 1 if res == "승리" else 0
                    if TIER_RANK[ot] < TIER_RANK[mt]:        # 상대가 더 높은 티어
                        d["up_w"] += w; d["up_n"] += 1
                        if w: d["beat_up"].append((opp["_canon"], ot, pos, me.get("날짜")))
                    elif TIER_RANK[ot] > TIER_RANK[mt]:      # 상대가 더 낮은 티어
                        d["dn_w"] += w; d["dn_n"] += 1
                        if not w: d["lost_dn"].append((opp["_canon"], ot, pos, me.get("날짜")))
                    else:
                        d["ev_w"] += w; d["ev_n"] += 1
        return stat

    def grudge(self):
        """억울지수 = 하위티어 맞라인 승률 − 상위티어 맞라인 승률.
           클랜에서 '억울하다'는 말은 "내 티어가 실제보다 높게 잡혔다"는 뜻이므로,
           아래 티어는 잡는데 위 티어에서 밀리는 사람이 억울한 쪽 = 지수가 높다."""
        out = []
        for k, d in self.lane_vs_tier().items():
            if d["up_n"] < MIN_LANE_GAMES or d["dn_n"] < MIN_LANE_GAMES: continue
            up = d["up_w"] / d["up_n"] * 100
            dn = d["dn_w"] / d["dn_n"] * 100
            out.append({"name": k, "tier": self.tier_of(k), "up": up, "dn": dn,
                        "up_n": d["up_n"], "dn_n": d["dn_n"], "score": dn - up})
        out.sort(key=lambda x: -x["score"])
        return out

    # ---------- ② 시너지·천적 ----------
    def partners(self, name, min_games=8):
        same, against = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
        for rows in self.games.values():
            me = next((r for r in rows if r["_canon"] == name), None)
            if not me: continue
            res = str(me.get("결과") or "")
            if res not in ("승리", "패배"): continue
            w = 1 if res == "승리" else 0
            for r in rows:
                if r["_canon"] == name: continue
                tgt = same if str(r.get("진영")) == str(me.get("진영")) else against
                tgt[r["_canon"]][0] += w; tgt[r["_canon"]][1] += 1
        def top(d, best=True):
            xs = [(v[0] / v[1] * 100, v[1], k) for k, v in d.items() if v[1] >= min_games]
            xs.sort(reverse=best)
            return xs
        return top(same), top(same, False), top(against), top(against, False)

    # ---------- ③ 시간 추세 ----------
    def trend(self, name):
        by_month, recent, older = defaultdict(lambda: [0, 0]), [0, 0], [0, 0]
        cut = datetime.date.today() - datetime.timedelta(days=RECENT_DAYS)
        for r in self.rows_of[name]:
            res = str(r.get("결과") or "")
            if res not in ("승리", "패배"): continue
            d = _date(r.get("날짜"))
            if not d: continue
            w = 1 if res == "승리" else 0
            m = f"{d.year}-{d.month:02d}"
            by_month[m][0] += w; by_month[m][1] += 1
            tgt = recent if d >= cut else older
            tgt[0] += w; tgt[1] += 1
        return dict(sorted(by_month.items())), recent, older

    # ---------- ④ 피밴율 ----------
    def banned_against(self, name, top_n=5):
        """이 사람의 주력 챔프가 그가 참가한 게임에서 얼마나 밴됐나."""
        played = defaultdict(int)
        for r in self.rows_of[name]:
            c = str(r.get("챔피언") or "").strip()
            if c: played[c] += 1
        mains = [c for c, _ in sorted(played.items(), key=lambda x: -x[1])[:top_n]]
        my_gids = {r.get("게임ID") for r in self.rows_of[name]}
        banned = defaultdict(int)
        for gid in my_gids:
            bans = set()
            for r in self.games.get(gid, []):
                for b in re.split(r"[,/|]", str(r.get("밴") or "")):
                    b = b.strip()
                    if b and b not in ("승리", "패배"): bans.add(b)
            for c in mains:
                if c in bans: banned[c] += 1
        return [(c, played[c], banned.get(c, 0), len(my_gids)) for c in mains]

    # ---------- ⑤ 게임 양상별 ----------
    def shape(self, name):
        """이기는 판 기여(MVP) vs 지는 판 버티기(ACE), 그리고 지표 표본."""
        w = l = mvp = ace = troll = 0
        kda, dpm = [], []
        for r in self.rows_of[name]:
            res = str(r.get("결과") or "")
            if res == "승리": w += 1
            elif res == "패배": l += 1
            e = str(r.get("매치평가") or "")
            if e == "MVP": mvp += 1
            elif e == "ACE": ace += 1
            elif e == "역적": troll += 1
            m = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", str(r.get("KDA") or ""))
            if m:
                k, d_, a = int(m[1]), int(m[2]), int(m[3])
                kda.append((k + a) / max(d_, 1))
        return {"w": w, "l": l, "mvp": mvp, "ace": ace, "troll": troll,
                "mvp_rate": mvp / w * 100 if w else None,
                "ace_rate": ace / l * 100 if l else None,
                "kda": mean(kda)}

    # ---------- ⑥ 십이귀월과의 거리 ----------
    def kizuki_gap(self, path, name):
        roster = compute(path)
        me = next((r for r in roster if r["name"] == name), None)
        league = "서부" if str(self.tier_of(name) or "")[:1] in ("0", "1") else "동부"
        pool = [r for r in roster if r["league"] == league]
        if me: return {"in": True, "title": me["title"], "power": me["power"],
                       "cut": pool[-1]["power"] if pool else None}
        return {"in": False, "league": league,
                "cut": pool[-1]["power"] if pool else None, "cut_name": pool[-1]["name"] if pool else None}

    # ---------- ⑦ 솔랭 괴리 ----------
    def solo_gap(self, name):
        cands = [self.solo.get(tnorm(name))] + [self.solo.get(tnorm(a)) for a in self.aliases.get(name, ())]
        cands = [c for c in cands if c]
        sr = next((c for c in cands if c.get("wr") is not None), cands[0] if cands else None)
        if not sr: return None
        peers = [(self.solo.get(tnorm(n)) or {}).get("score") for n in self.rows_of
                 if self.tier_of(n) == self.tier_of(name)]
        peers = [p for p in peers if p is not None]
        return {"score": sr["score"], "wr": sr.get("wr"),
                "tier_avg": mean(peers), "tier_n": len(peers)}


def _pct(x): return f"{x:.1f}%" if x is not None else "—"


def report(d, path, name):
    print(f"\n{'='*66}\n  {name}   내부티어 {d.tier_of(name) or '—'}   내전 {len(d.rows_of[name])}판\n{'='*66}")

    st = d.lane_vs_tier(name).get(name)
    print("\n① 맞라이너 티어 대비")
    if st and (st["up_n"] or st["dn_n"]):
        up = st["up_w"] / st["up_n"] * 100 if st["up_n"] else None
        dn = st["dn_w"] / st["dn_n"] * 100 if st["dn_n"] else None
        ev = st["ev_w"] / st["ev_n"] * 100 if st["ev_n"] else None
        print(f"   상위 티어 상대 {_pct(up)} ({st['up_n']}판) · 동급 {_pct(ev)} ({st['ev_n']}판) · 하위 {_pct(dn)} ({st['dn_n']}판)")
        if up is not None and dn is not None:
            print(f"   억울지수 {dn-up:+.1f}%p  " +
                  ("← 아래는 잡는데 위에서 밀림(티어가 높게 잡혔다는 근거)" if dn - up > 5 else
                   "← 위 티어 상대로도 버팀(지금 티어가 오히려 낮을 수도)" if dn - up < -5 else "← 상대 티어를 크게 타지 않음"))
        for who, t, pos, dt in st["beat_up"][-3:]:
            print(f"     · {str(dt)[:10]} {pos} — {who}({t}) 상대 승")
    else:
        print("   표본 부족")

    print("\n② 시너지·천적")
    best, worst, nemw, nemb = d.partners(name)
    if best: print("   같은 팀 강함: " + ", ".join(f"{k.split('#')[0]} {w:.0f}%({n})" for w, n, k in best[:3]))
    if worst: print("   같은 팀 약함: " + ", ".join(f"{k.split('#')[0]} {w:.0f}%({n})" for w, n, k in worst[:3]))
    if nemb: print("   천적(만나면 짐): " + ", ".join(f"{k.split('#')[0]} {w:.0f}%({n})" for w, n, k in nemb[:3]))
    if nemw: print("   먹잇감(만나면 이김): " + ", ".join(f"{k.split('#')[0]} {w:.0f}%({n})" for w, n, k in nemw[:3]))

    print("\n③ 시간 추세")
    months, recent, older = d.trend(name)
    if recent[1] and older[1]:
        print(f"   최근 90일 {recent[0]/recent[1]*100:.1f}% ({recent[1]}판) ↔ 그 이전 {older[0]/older[1]*100:.1f}% ({older[1]}판)")
    tail = list(months.items())[-6:]
    if tail: print("   월별: " + "  ".join(f"{m} {w/n*100:.0f}%({n})" for m, (w, n) in tail))

    print("\n④ 피밴율")
    for c, pl, bn, tot in d.banned_against(name):
        print(f"   {c:10} 플레이 {pl}판 · 내가 낀 게임에서 밴 {bn}/{tot} ({bn/tot*100:.0f}%)")

    print("\n⑤ 게임 양상")
    s = d.shape(name)
    print(f"   {s['w']}승 {s['l']}패 · 이긴 판 MVP {_pct(s['mvp_rate'])} · 진 판 ACE {_pct(s['ace_rate'])} · 역적 {s['troll']}회 · 평균 KDA {s['kda']:.2f}"
          if s["kda"] else f"   {s['w']}승 {s['l']}패 · MVP {s['mvp']} ACE {s['ace']} 역적 {s['troll']}")

    print("\n⑥ 십이귀월")
    kg = d.kizuki_gap(path, name)
    if kg["in"]: print(f"   현재 {kg['title']} (파워 {kg['power']:+.3f}, 컷 {kg['cut']:+.3f})")
    elif kg["cut"] is not None: print(f"   미편성 · {kg['league']} 막차({kg['cut_name'].split('#')[0]}) 파워 {kg['cut']:+.3f}")

    print("\n⑦ 솔랭 괴리")
    sg = d.solo_gap(name)
    if sg and sg["tier_avg"]:
        print(f"   솔랭점수 {sg['score']:.0f} · 같은 티어 평균 {sg['tier_avg']:.0f} ({sg['tier_n']}명) → {sg['score']-sg['tier_avg']:+.0f}")
    elif sg: print(f"   솔랭점수 {sg['score']:.0f}")
    else: print("   솔랭 기록 없음")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("name", nargs="?")
    ap.add_argument("--grudge", action="store_true", help="억울지수 랭킹 출력")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--push", action="store_true", help="억울지수를 GRUDGE 탭에 기록")
    a = ap.parse_args()

    if a.push:
        push_grudge(a.xlsx); return
    d = Dossier(a.xlsx)
    if a.grudge:
        g = d.grudge()
        if a.json: print(json.dumps(g, ensure_ascii=False, indent=1)); return
        print(f"\n  억울지수 랭킹 — 하위티어 맞라인 승률 − 상위티어 맞라인 승률 (각 {MIN_LANE_GAMES}판 이상)")
        print(f"  높을수록 '아래는 잡는데 위에서 밀린다' = 내 티어가 높게 잡혔다는 근거\n")
        for i, x in enumerate(g[:20], 1):
            print(f"  {i:>2}. {x['name'].split('#')[0]:<18} {x['tier']:<3} {x['score']:+6.1f}%p"
                  f"   (아래 {x['dn']:.0f}%/{x['dn_n']}판 · 위 {x['up']:.0f}%/{x['up_n']}판)")
        print(f"\n  분석 대상 {len(g)}명\n")
        return
    if not a.name: sys.exit("닉네임을 입력하거나 --grudge 를 쓰세요")
    nm = d.resolve(a.name)
    if not nm: sys.exit(f"'{a.name}' 을(를) 찾지 못했습니다")
    report(d, a.xlsx, nm)




# ===== 억울지수 시트 기록 (Actions에서 호출) =====
def push_grudge(path):
    """GRUDGE 탭 재작성 — 웹 억울지수 랭킹의 데이터 소스.

    시트 API는 분당 읽기/쓰기 쿼터가 따로 있고 둘 다 429가 흔하다.
    연결·조회·쓰기를 각각 지수 백오프로 재시도하고, 끝까지 실패하면 탭을 건드리지 않고 종료한다
    (반쯤 지워진 탭이 남는 것이 제일 나쁘므로 clear+update는 한 재시도 단위로 묶는다)."""
    import base64, os, time as _t
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
    raw = os.environ.get("CREDENTIALS_JSON_B64", "")
    if not raw: sys.exit("CREDENTIALS_JSON_B64 없음")
    open("creds.json", "wb").write(base64.b64decode(raw))
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    def retry(label, fn, tries=5):
        for i in range(tries):
            try: return fn()
            except Exception as e:
                if i == tries - 1: raise
                wait = 30 * (2 ** i)          # 30 / 60 / 120 / 240초 — 분당 쿼터가 풀릴 만큼
                print(f"[grudge] {label} 실패({type(e).__name__}) — {wait}s 후 재시도", flush=True)
                _t.sleep(wait)

    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    ss = retry("시트 연결", lambda: gspread.authorize(creds).open_by_key(SHEET_ID))

    rows = [["닉네임", "티어", "억울지수", "상위승률", "상위판수", "하위승률", "하위판수", "갱신"]]
    stamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    for x in Dossier(path).grudge():
        rows.append([x["name"], x["tier"], round(x["score"], 1), round(x["up"], 1), x["up_n"],
                     round(x["dn"], 1), x["dn_n"], stamp])
    if len(rows) < 2:
        print("[grudge] 산출 0건 — 기존 탭 보존"); return

    def write():
        try: ws = ss.worksheet("GRUDGE")
        except Exception: ws = ss.add_worksheet(title="GRUDGE", rows="300", cols="8")
        ws.clear()
        ws.update(values=rows, range_name="A1")
        return ws
    retry("GRUDGE 쓰기", write)
    print(f"[grudge] GRUDGE 탭 갱신 — {len(rows)-1}명 (1위 {rows[1][0]} {rows[1][2]}%p)")


if __name__ == "__main__":
    main()
