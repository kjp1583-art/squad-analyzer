#!/usr/bin/env python3
"""gol.gg 구조 확인용 임시 스크립트 — 결과를 lck_probe.txt 로 남긴다(Actions 로그가 잘려서)."""
import urllib.parse, urllib.request
from lxml import html as LH

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
OUT = []
def say(*a): OUT.append(" ".join(str(x) for x in a))

def fetch(url, data=None):
    h = dict(UA); body = None
    if data is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(data, doseq=True).encode()
    try:
        return urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=45).read()
    except Exception as e:
        say("  실패", type(e).__name__, e); return None

# ① 팀 목록에서 한국(KR) 팀 추리기
raw = fetch("https://gol.gg/teams/list/season-S16/split-Summer/tournament-ALL/")
kr = []
if raw:
    d = LH.fromstring(raw)
    heads = [t.text_content().strip() for t in d.xpath("//table//th")]
    say("=== 팀 표 컬럼:", heads)
    ri = heads.index("Region") if "Region" in heads else -1
    for tr in d.xpath("//table//tr"):
        a = tr.xpath("./td/a[contains(@href,'team-stats')]")
        if not a: continue
        tds = [c.text_content().strip() for c in tr.xpath("./td")]
        reg = tds[ri] if 0 <= ri < len(tds) else ""
        if reg.upper() == "KR": kr.append((a[0].text_content().strip(), a[0].get("href"), tds[:5]))
    say("=== KR 팀 %d개" % len(kr))
    for n, h, t in kr: say("   ", n, h, t)

# ② T1 팀 페이지 구조 — 로스터에 역할이 있는가
t1 = next((h for n, h, _ in kr if n.upper() == "T1"), None)
if t1:
    url = t1.replace("./", "https://gol.gg/teams/")
    say("\n=== T1 팀 페이지:", url)
    raw = fetch(url)
    if raw:
        d = LH.fromstring(raw)
        for i, tb in enumerate(d.xpath("//table")):
            hs = [x.text_content().strip() for x in tb.xpath(".//th")]
            rows = tb.xpath(".//tr")
            say(f"  표{i} 컬럼={hs[:12]} 행={len(rows)}")
            for tr in rows[1:7]:
                say("     ", [c.text_content().strip() for c in tr.xpath('./td')][:10],
                    [a.get('href') for a in tr.xpath('.//a')][:2])

# ③ 선수 목록 POST 필터가 실제로 먹는지 (행 수로 비교)
base = "https://gol.gg/players/list/season-S16/split-Summer/tournament-ALL/"
def count(data):
    raw = fetch(base, data)
    if not raw: return -1, []
    d = LH.fromstring(raw)
    rs = [tr for tr in d.xpath("//table//tr") if tr.xpath("./td/a[contains(@href,'player-stats')]")]
    names = [tr.xpath("./td/a")[0].text_content().strip() for tr in rs[:5]]
    return len(rs), names
say("\n=== 선수 목록 필터 반응")
for label, data in [
    ("무필터(GET)", None),
    ("role=TOP", {"cbtournament": "ALL", "role": "TOP"}),
    ("league=LCK", {"cbtournament": "ALL", "role": "ALL", "leaguePost": "true", "leagueFilter[]": ["LCK"]}),
    ("league=LCK+role=TOP", {"cbtournament": "ALL", "role": "TOP", "leaguePost": "true", "leagueFilter[]": ["LCK"]}),
    ("leagueFilter(단수)", {"cbtournament": "ALL", "role": "TOP", "leaguePost": "true", "leagueFilter": "LCK"}),
    ("leagues[]=1", {"cbtournament": "ALL", "role": "TOP", "leaguePost": "true", "leagues[]": ["1"]}),
]:
    n, nm = count(data)
    say(f"  {label:<22} 행={n} 예시={nm}")

open("lck_probe.txt", "w", encoding="utf-8").write("\n".join(OUT))
print("\n".join(OUT[:40]))
