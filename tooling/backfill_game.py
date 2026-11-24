#!/usr/bin/env python3
"""🩹 누락된 내전·스크림 판을 deeplol 매치 번호로 시트(CLASSIC_NORMAL / KIWI_KIWI)에 채워 넣는다.
봇의 누락경기 복구(`bot.py` `_backfill_build` · `_backfill_apply`)와 같은 행 형식·같은 규칙이다 — 봇 채널에 주소를 올리는 길이 막혔거나
세션에서 바로 넣어야 할 때 GitHub 워크플로(`backfill-games.yml`)로 돌린다.
사용: MATCH_IDS="KR_8472179884 KR_8472158372" [APPLY=1] python3 tooling/backfill_game.py
  · 기본은 미리보기(행만 출력). APPLY=1 일 때만 시트에 append(RAW — USER_ENTERED 는 KDA 가 날짜로 바뀐다).
  · 이미 그 게임ID 가 있으면 건너뛴다 · 우리 클랜 판이 아닌 듯하면(시트에 있는 닉이 4명 미만) 건너뛴다.
⚠️ deeplol 필드명이 뒤집혀 있다 — total_damage_dealt 가 '챔피언에게 준 피해'다."""
import base64, csv, datetime, io, json, os, re, sys, urllib.parse, urllib.request, urllib.error

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
KST = datetime.timezone(datetime.timedelta(hours=9))
BF_POS = {"top": "탑", "jungle": "정글", "middle": "미드", "mid": "미드", "bottom": "원딜", "bot": "원딜",
          "supporter": "서폿", "support": "서폿", "utility": "서폿"}
tn = lambda s: "".join(str(s or "").split("#")[0].lower().split())

def dl_get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Origin": "https://www.deeplol.gg", "Referer": "https://www.deeplol.gg/"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))

def gviz(sheet):
    url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s&headers=1" % (SHEET_ID, urllib.parse.quote(sheet)))
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))
    return rows[0], rows[1:]

def build(mid, cache):
    region = mid.split("_")[0].upper()
    m = dl_get("https://b2c-api-cdn.deeplol.gg/match/match-cached?match_id=%s&platform_id=%s" % (mid, region))
    b, ps = m.get("match_basic_dict") or {}, m.get("participants_list") or []
    if not b or not ps or not b.get("match_id"): return None, None, "경기 데이터를 못 읽었어요"
    if len(ps) < 10: return None, None, "참가자 %d명 — 기록하지 않아요" % len(ps)
    if str(b.get("is_remake")).lower() == "true": return None, None, "다시하기(리메이크) 판"
    ver = str(b.get("game_version") or "")
    rd = dl_get("https://b2c-api-cdn.deeplol.gg/common/riot_data?country_code=ko_KR&version=%s" % (ver or "16.16"))
    ch = {int(v["key"]): v["name"] for v in rd["champion_json"]["data"].values()}
    sp = {int(v["key"]): v["id"] for v in rd["spell_json"]["data"].values()}
    gid = "#" + str(b.get("match_id") or mid).split("_")[-1]
    date = datetime.datetime.fromtimestamp(float(b.get("creation_timestamp") or 0), KST).strftime("%Y-%m-%d %H:%M")
    tab = "KIWI_KIWI" if str(b.get("map_id")) == "12" else "CLASSIC_NORMAL"
    if tab not in cache: cache[tab] = gviz(tab)
    hdr, body = cache[tab]
    ci = {h: i for i, h in enumerate(hdr)}
    known = {tn(r[ci["소환사명"]]) for r in body if len(r) > ci["소환사명"] and r[ci["소환사명"]]}
    pu = {}
    for r in body:
        if len(r) > ci["PUUID"] and r[ci["소환사명"]] and r[ci["PUUID"]]: pu.setdefault(tn(r[ci["소환사명"]]), r[ci["PUUID"]])
    names = ["%s#%s" % (p.get("riot_id_name"), p.get("riot_id_tag_line")) for p in ps]
    hit = sum(1 for n in names if tn(n) in known)
    if hit < 4: return None, None, "우리 클랜 판이 아닌 것 같아요 (시트에 있는 닉 %d명)" % hit
    rows = []
    for p in ps:
        s, it, rn, sd = p.get("final_stat_dict") or {}, p.get("final_item_dict") or {}, p.get("rune_detail_dict") or {}, p.get("spell_id_dict") or {}
        nm = "%s#%s" % (p.get("riot_id_name"), p.get("riot_id_tag_line"))
        ev = "MVP" if p.get("mvp") else ("역적" if p.get("is_runaway") else ("ACE" if p.get("ace") else "평가 없음"))
        items = "|".join(str(it.get("item_%d" % i)) for i in range(7) if it.get("item_%d" % i))
        spells = "|".join(sp.get(int(sd.get(k) or 0), "") for k in ("spell_1", "spell_2") if sd.get(k))
        ind = []
        for key, val in (("g", s.get("total_gold") or p.get("total_gold")), ("cs", s.get("cs")), ("m", s.get("cspm")), ("kp", s.get("kill_point")),
                         ("cw", s.get("vision_wards_bought")), ("wp", s.get("wards_placed")), ("wk", s.get("wards_killed")), ("dt", p.get("total_damage_taken"))):
            if val is not None: ind.append("%s%s" % (key, val))
        kda = "%s/%s/%s" % (s.get("kills", 0), s.get("deaths", 0), s.get("assists", 0))
        vk = ("v" + ver, kda) if tab != "KIWI_KIWI" else (kda, "v" + ver)   # 두 탭의 열 순서가 반대(CLASSIC: 패치·KDA / KIWI: KDA·패치)
        rows.append([gid, date, nm, pu.get(tn(nm), ""), "블루팀" if str(p.get("side")).upper() == "BLUE" else "레드팀",
                     BF_POS.get(str(p.get("position") or "").lower(), ""), ch.get(int(p.get("champion_id") or 0), ""), "",
                     "승리" if p.get("is_win") else "패배", ev, *vk, "", int(p.get("total_damage_dealt") or 0) or "",
                     items, "%s|%s" % (rn.get("perk_0", ""), rn.get("perk_primary_style", "")), str(rn.get("perk_sub_style", "")), spells, "|".join(ind)])
    return tab, rows, "클랜원 %d명 · %s" % (hit, date)

def main():
    ids = re.findall(r"(KR_?\d{6,})", os.environ.get("MATCH_IDS", ""), re.I)
    ids = [i.upper() if "_" in i else i[:2].upper() + "_" + i[2:] for i in ids]
    if not ids: print("MATCH_IDS 가 비었어요"); sys.exit(1)
    apply_ = os.environ.get("APPLY") == "1"; cache = {}; plan = []
    for mid in ids:
        try: tab, rows, info = build(mid, cache)
        except urllib.error.HTTPError as e: tab, rows, info = None, None, "deeplol HTTP %s" % e.code
        if not rows: print("⏭ %s — %s" % (mid, info)); continue
        hdr, body = cache[tab]
        if rows[0][0] in {r[0] for r in body if r}: print("⏭ %s — 이미 시트에 있어요(%s)" % (mid, rows[0][0])); continue
        print("✅ %s → %s %s · %s" % (mid, tab, rows[0][0], info))
        for r in rows: print("   ", r[4], r[5], r[6], r[2], r[8], r[10 if tab != "KIWI_KIWI" else 11], r[11 if tab != "KIWI_KIWI" else 10])
        plan.append((tab, rows))
    if not plan: print("넣을 판 없음"); return
    if not apply_: print("\n미리보기 — APPLY=1 이어야 시트에 쓴다(%d판 · %d행)" % (len(plan), sum(len(r) for _, r in plan))); return
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    open("creds.json", "wb").write(base64.b64decode(os.environ["CREDENTIALS_JSON_B64"]))
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    ss = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)).open_by_key(SHEET_ID)
    for tab, rows in plan:
        ws = ss.worksheet(tab)
        if rows[0][0] in {str(x).strip() for x in ws.col_values(1)}: print("이미 있음 — 건너뜀", rows[0][0]); continue
        ws.append_rows(rows, value_input_option="RAW")   # RAW 필수 — USER_ENTERED 는 KDA "9/4/3" 을 날짜로 바꾼다
        print("기록 완료", rows[0][0], len(rows), "행")

if __name__ == "__main__":
    main()
