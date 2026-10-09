# -*- coding: utf-8 -*-
"""실제 구글 시트의 gviz 응답을 탭마다 <탭>.txt 로 저장한다 — fidelity.py(xlsx 재현이 실제 응답과 같은지)와
replay.py --gviz-dir(실제 응답으로 재생)의 재료. 저장 폴더는 저장소 밖에 둘 것(닉네임·PUUID 가 들어 있다).

  python3 tests/web_replay/fetch_gviz.py <폴더> [탭 …]      (탭을 안 주면 웹이 부팅 때 읽는 탭 전부)
"""
import os
import sys
import urllib.parse
import urllib.request

SHEET_ID = "10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU"
BOOT_TABS = ["SOLO_RANK", "PEAK_SEASONS", "LINK_ACCOUNT", "CLAN_TIERS", "DEPARTED", "CLAN_POSITIONS", "PREDICTIONS", "CAREER", "AI_EVAL",
             "TIER_HISTORY", "GPTI_STATS", "MITO", "MBTI", "GHOST", "TITLES", "MYEOL", "NOBAN", "GRUDGE", "MITO_GAMES", "MITO_CODES",
             "LCK_PRED", "PERKS", "BRJANG", "BRJ_MARKET", "UNIQ_MARKET", "SCRIM_LIVE", "KIWI_KIWI", "LOL_CLASSIC", "CLASSIC_NORMAL"]


def fetch(tab, headers=1):
    q = urllib.parse.urlencode({"sheet": tab, "headers": headers, "tqx": "out:json"})
    req = urllib.request.Request("https://docs.google.com/spreadsheets/d/%s/gviz/tq?%s" % (SHEET_ID, q), headers={"User-Agent": "squad-replay"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode("utf-8")


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for tab in (sys.argv[2:] or BOOT_TABS):
        text = fetch(tab)
        with open(os.path.join(out, tab + ".txt"), "w", encoding="utf-8") as f: f.write(text)
        print("%-16s %9d 글자" % (tab, len(text)))


if __name__ == "__main__":
    main()
