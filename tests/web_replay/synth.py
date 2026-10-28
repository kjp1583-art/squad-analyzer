# -*- coding: utf-8 -*-
"""합성 시트(가짜 닉네임·PUUID) — 실제 클랜 데이터를 저장소에 올리지 않고 같은 구조(3단 사슬·2단·사슬 없음·본계에 행)를 재현한다.

make_xlsx(path) 로 xlsx 를 쓰고, CAST 가 시험이 기대하는 값(누가 어떤 구조인지)을 말해 준다.
탭: CLASSIC_NORMAL · CLAN_TIERS · SOLO_RANK · PEAK_SEASONS · LINK_ACCOUNT · DEPARTED (그 밖의 탭은 없다 — 하네스가 빈 표로 답한다).
"""
import datetime as dt
import random

NOW = "2026-10-09T15:00:00"        # 시험에서 웹의 시계를 여기에 고정한다(한국 시각)
TIER_BASE = {"IRON": 0, "BRONZE": 400, "SILVER": 800, "GOLD": 1200, "PLATINUM": 1600, "EMERALD": 2000, "DIAMOND": 2400}
DIV = {"I": 3, "II": 2, "III": 1, "IV": 0}


def score_of(tier, lp):
    """분석기 _rank_score 와 같은 척도 — 마스터+ = 2800+LP, 그 아래 = 기준점 + 디비전×100 + LP"""
    t, *d = tier.split()
    if t in ("MASTER", "GRANDMASTER", "CHALLENGER"): return 2800 + lp
    return TIER_BASE[t] + DIV[d[0]] * 100 + lp


# 구조별 구성원. name = 게임 기록에 찍히는 닉(#태그 포함). games = 그 닉으로 뛴 판 수 비중.
#  chain3   : 계정 이전 + 닉변 사슬. 행 A「본계 중간#Mid ← 부계 옛#Old」 + 행 B「본계 현재#Now ← 부계 중간#Mid」. SOLO 행은 옛 닉에만.
#  pair     : 2단. 「본계 ← 부계」 인데 SOLO 행은 부계에만.
#  mainrow  : 2단인데 SOLO 행이 본계에 있다(예전부터 잘 되던 모양 — 불변이어야 한다).
#  peakonly : 사슬도 행도 없고 PEAK 만 있다(솔랭 안 돌림).
#  chainpk  : 사슬인데 어느 계정에도 현시즌 행이 없다(PEAK 만).
CAST = {
    "chain3": {"now": "체인현#Now", "mid": "체인중#Mid", "old": "체인옛#Old", "tier": "1中",
               "solo_row": ("체인옛#Old", "MASTER I", 600, 90, 60), "peak": {"체인현#Now": 2900, "체인중#Mid": 2900, "체인옛#Old": 3100}},
    "pair": {"main": "이단본#Main", "sub": "이단부#Sub", "tier": "2上",
             "solo_row": ("이단부#Sub", "DIAMOND II", 50, 40, 38), "peak": {"이단본#Main": 2900}},
    "mainrow": {"main": "본행#Main", "sub": "본행부#Sub", "tier": "1下",
                "solo_row": ("본행#Main", "EMERALD I", 30, 60, 50), "peak": {"본행#Main": 2700}},
    "peakonly": {"name": "피크만#Solo", "tier": "2中", "peak": {"피크만#Solo": 2800}},
    "chainpk": {"now": "체인피크현#Now", "mid": "체인피크중#Mid", "old": "체인피크옛#Old", "tier": "2下",
                "peak": {"체인피크현#Now": 2700, "체인피크중#Mid": 2700, "체인피크옛#Old": 3000}},
}
PLAIN_N = 24
TIERS = ["0", "1上", "1中", "1下", "2上", "2中", "2下", "3上", "3中", "3下"]
SOLO_TIERS = [("MASTER I", 400), ("MASTER I", 120), ("DIAMOND I", 60), ("DIAMOND II", 20), ("DIAMOND IV", 70),
              ("EMERALD II", 40), ("EMERALD IV", 10), ("PLATINUM I", 80), ("PLATINUM III", 30), ("GOLD II", 55)]


def plain_names():
    return ["가상%02d#TST" % i for i in range(1, PLAIN_N + 1)]


def build_tabs(seed=7, shuffle_links=False):
    rnd = random.Random(seed)
    people = []   # (PUUID, 기록 닉 함수(game_idx)->닉, 비중)
    plain = plain_names()
    for i, nm in enumerate(plain): people.append(("pu-plain-%02d" % i, (lambda g, nm=nm: nm)))
    c = CAST["chain3"]
    people.append(("pu-chain-now", lambda g, c=c: c["mid"] if g < 8 else c["now"]))      # 같은 계정 — 앞 8판은 옛 닉(중간), 뒤는 새 닉
    people.append(("pu-chain-old", lambda g, c=c: c["old"]))                              # 계정 이전 전의 다른 계정
    c = CAST["pair"]; people += [("pu-pair-main", lambda g, c=c: c["main"]), ("pu-pair-sub", lambda g, c=c: c["sub"])]
    c = CAST["mainrow"]; people.append(("pu-mainrow", lambda g, c=c: c["main"]))
    c = CAST["peakonly"]; people.append(("pu-peakonly", lambda g, c=c: c["name"]))
    c = CAST["chainpk"]; people += [("pu-chainpk-now", lambda g, c=c: c["mid"] if g < 8 else c["now"]), ("pu-chainpk-old", lambda g, c=c: c["old"])]
    # ---- 게임 ----
    start = dt.datetime(2026, 9, 14, 20, 0)
    N_GAMES = 72
    deck, rows = [], []
    for g in range(N_GAMES):
        picked = []
        while len(picked) < 10:
            if not deck:
                deck = list(range(len(people))); rnd.shuffle(deck)
            x = deck.pop()
            if x in picked: continue
            picked.append(x)
        when = start + dt.timedelta(hours=g * 8)
        blue_wins = rnd.random() < 0.5
        for slot, x in enumerate(picked):
            pu, namef = people[x]
            win = (slot < 5) == blue_wins
            ev = rnd.choice(["", "", "", "MVP", "ACE", "역적"]) if rnd.random() < 0.7 else ""
            rows.append(["#%d" % (5000 + g), when.strftime("%Y-%m-%d %H:%M"), namef(g), pu, "블루팀" if slot < 5 else "레드팀",
                         ["탑", "정글", "미드", "원딜", "서폿"][slot % 5], rnd.choice(["아리", "가렌", "럭스", "이즈리얼", "쓰레쉬", "리신", "제이스", "카이사"]),
                         "", "승리" if win else "패배", ev, "v16.20", "%d/%d/%d" % (rnd.randint(0, 12), rnd.randint(0, 9), rnd.randint(0, 15)),
                         round(rnd.uniform(8, 42), 1), rnd.randint(8000, 32000), "", "", "", "", ""])
    game_hdr = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "매치평가", "패치버전", "KDA", "점수", "딜량", "아이템", "주룬", "보조룬", "스펠", "지표"]
    # ---- 내부티어 / 솔랭 / 피크 ----
    tiers, solo, peak = [], [], []
    for i, nm in enumerate(plain):
        base = nm.split("#")[0]
        tiers.append([base, TIERS[i * len(TIERS) // PLAIN_N]])
        if i % 6 != 5:                                       # 4명 중 1명은 솔랭 행 없음(PEAK 만)
            t, lp = SOLO_TIERS[(i * 7) % len(SOLO_TIERS)]
            w = 30 + (i * 13) % 90; l = 25 + (i * 17) % 80
            solo.append([nm, t, lp, w, l, score_of(t, lp), "2026-10-09 13:00", 1000 + i, 100 + i])
        sc = score_of(*SOLO_TIERS[(i * 7) % len(SOLO_TIERS)])
        peak.append([nm, base, "master 1", "S14-2", float(sc + rnd.choice([-80, 0, 40, 150, 260])), "", "2026-09-01"])
    def peakrow(nm, sc):
        peak.append([nm, nm.split("#")[0], "master 1", "S14-2", float(sc), "", "2026-09-01"])
    links = []
    c = CAST["chain3"]; tiers.append([c["now"].split("#")[0], c["tier"]])
    t, lp, w, l = c["solo_row"][1], c["solo_row"][2], c["solo_row"][3], c["solo_row"][4]
    solo.append([c["solo_row"][0], t, lp, w, l, score_of(t, lp), "2026-10-09 13:00", 6026, 97])
    for nm, sc in c["peak"].items(): peakrow(nm, sc)
    links += [[c["mid"], c["old"], "계정 이전 통합"], [c["now"], c["mid"], "닉변 통합"]]            # 사슬 — 행 순서가 옛것 → 새것
    c = CAST["pair"]; tiers.append([c["main"].split("#")[0], c["tier"]])
    solo.append([c["solo_row"][0], c["solo_row"][1], c["solo_row"][2], c["solo_row"][3], c["solo_row"][4], score_of(c["solo_row"][1], c["solo_row"][2]), "2026-10-09 13:00", 4001, 55])
    for nm, sc in c["peak"].items(): peakrow(nm, sc)
    links.append([c["main"], c["sub"], ""])
    c = CAST["mainrow"]; tiers.append([c["main"].split("#")[0], c["tier"]])
    solo.append([c["solo_row"][0], c["solo_row"][1], c["solo_row"][2], c["solo_row"][3], c["solo_row"][4], score_of(c["solo_row"][1], c["solo_row"][2]), "2026-10-09 13:00", 4002, 66])
    for nm, sc in c["peak"].items(): peakrow(nm, sc)
    links.append([c["main"], c["sub"], ""])
    c = CAST["peakonly"]; tiers.append([c["name"].split("#")[0], c["tier"]])
    for nm, sc in c["peak"].items(): peakrow(nm, sc)
    c = CAST["chainpk"]; tiers.append([c["now"].split("#")[0], c["tier"]])
    for nm, sc in c["peak"].items(): peakrow(nm, sc)
    links += [[c["mid"], c["old"], "계정 이전 통합"], [c["now"], c["mid"], "닉변 통합"]]
    if shuffle_links: rnd.shuffle(links)
    return {
        "CLASSIC_NORMAL": [game_hdr] + rows,
        "CLAN_TIERS": [["닉네임", "티어"]] + tiers,
        "SOLO_RANK": [["닉네임", "티어", "LP", "솔랭승", "솔랭패", "점수", "갱신", "아이콘", "레벨"]] + solo,
        "PEAK_SEASONS": [["닉네임", "차트닉", "최고티어", "최고시즌", "점수", "상세", "측정일"]] + peak,
        "LINK_ACCOUNT": [["본계정", "부계정 롤닉 (#태그 있어도 됨)", "메모 (선택)"]] + links,
        "DEPARTED": [["닉네임", "갱신시각"]],
    }


def make_xlsx(path, seed=7, shuffle_links=False):
    import openpyxl
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for name, rows in build_tabs(seed, shuffle_links).items():
        ws = wb.create_sheet(name)
        for r in rows: ws.append(r)
    wb.save(path)
    return path


if __name__ == "__main__":
    import sys
    print(make_xlsx(sys.argv[1] if len(sys.argv) > 1 else "synth.xlsx"))
