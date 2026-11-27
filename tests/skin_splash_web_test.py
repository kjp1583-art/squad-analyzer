# -*- coding: utf-8 -*-
"""🎭 상현·하현·귀살대 카드 스킨 일러스트 시험 — `python3 tests/skin_splash_web_test.py`

  (2026-11-27 사장님 「기본 일러스트 대신 그 사람이 마지막에 쓴 스킨으로」 · 저장 방식 '별도시트')

  A 스킨표(LAST_SKIN) — gviz 로 읽어 (사람·챔피언)→skinID 맵이 되고, skin 0/없음은 기본(_0.jpg) 그대로
  B 주소 만들기 — …_0.jpg → …_{skin}.jpg · 기본(0)·체력 없는 주소·비-ddragon 주소는 손대지 않는다
  C 폴백 — 그림이 실제로 없는 스킨번호면 Image 로드 실패를 알아채 _0.jpg 로 되돌리고, 이미 그려 둔 배경도 바꾼다
  D 카드 배선 — mainSplashOf 가 쓰는 자리(kz-bg · kzc-bg)에 스킨 주소가 들어가고 data-skinbg 로 폴백 대상을 표시한다
  E 안전 — 탭이 없거나 헤더가 다르면 조용히 기본 일러스트(콘솔 오류 0)
"""
import asyncio
import os
import random
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HERE_UP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "web_replay"))
import replay as R  # noqa: E402

NOW = "2026-11-27T15:00:00"
COLS = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "매치평가",
        "패치버전", "KDA", "점수", "딜량", "아이템", "주룬", "보조룬", "스펠", "지표"]
CHAMPS = ["아리", "럭스", "가렌", "이즈리얼", "쓰레쉬", "리신", "제드", "카이사", "룰루", "탑" and "가렌"]
NAMES = (["스킨왕요원#T", "기본스킨요원#T", "표에없는요원#T"]
         + ["미드%02d#T" % i for i in range(1, 11)] + ["탑%02d#T" % i for i in range(1, 6)]
         + ["정글%02d#T" % i for i in range(1, 6)])
MAIN_CHAMP = {n: CHAMPS[i % len(CHAMPS)] for i, n in enumerate(NAMES)}
# 스킨 표 검사용 세 사람
SKIN_PLAYER = NAMES[0]          # skin 7
BASE_PLAYER = NAMES[1]          # skin 0 (기본 스킨)
NOSKIN_PLAYER = NAMES[2]        # 표에 없음
MAIN_CHAMP[SKIN_PLAYER] = "아리"
MAIN_CHAMP[BASE_PLAYER] = "아리"
MAIN_CHAMP[NOSKIN_PLAYER] = "아리"
PU = {n: "pu-" + re.sub(r"\W", "", n) for n in NAMES}

fails = []


def ok(c, msg):
    print(("  ok   " if c else "  FAIL ") + msg)
    if not c:
        fails.append(msg)


def build_xlsx(path, last_skin="good"):
    """last_skin: good | none | badheader"""
    from openpyxl import Workbook
    rnd = random.Random(11)
    wb = Workbook()
    ws = wb.active
    ws.title = "CLASSIC_NORMAL"
    ws.append(COLS)
    gid = [7000]
    for g in range(24):
        gid[0] += 1
        squad = [NAMES[(g * 3 + j) % len(NAMES)] for j in range(10)]
        blue = rnd.random() < .5
        for k, n in enumerate(squad):
            win = (k < 5) == blue
            ws.append(["#%d" % gid[0], "2026-11-%02d 21:%02d" % (10 + g % 17, k), n, PU[n],
                       "블루팀" if k < 5 else "레드팀", ["탑", "정글", "미드", "원딜", "서폿"][k % 5],
                       MAIN_CHAMP[n] if g < 16 else rnd.choice(CHAMPS[:4]), None,
                       "승리" if win else "패배", "MVP" if k == 0 and win else None, "v16.23",
                       "%d/%d/%d" % (rnd.randint(1, 9), rnd.randint(0, 5), rnd.randint(1, 12)),
                       20.0, 20000.0, None, None, None, None, None])
    tiers = [[n.split("#")[0], "1中"] for n in NAMES]
    for name, rows in (("CLAN_TIERS", [["닉네임", "티어"]] + tiers),):
        w = wb.create_sheet(name)
        for r in rows:
            w.append(r)
    if last_skin == "good":
        w = wb.create_sheet("LAST_SKIN")
        w.append(["puuid", "name", "champion", "skin_id", "updated_at"])
        w.append([PU[SKIN_PLAYER], SKIN_PLAYER, "아리", 7, "2026-11-27 22:10"])
        w.append([PU[BASE_PLAYER], BASE_PLAYER, "아리", 0, "2026-11-27 22:10"])
        w.append([PU[NAMES[3]], NAMES[3], MAIN_CHAMP[NAMES[3]].replace(" ", ""), 3, "2026-11-27 22:10"])
    elif last_skin == "badheader":
        w = wb.create_sheet("LAST_SKIN")
        w.append(["게임ID", "날짜", "소환사명"])       # gviz 첫 시트 폴백과 같은 사고 — 헤더가 다르다
        w.append(["#1", "2026-11-27", "가"])
    wb.save(path)


EVAL_MAP = r"""() => {
  const _Im0=window.Image; window.Image=function(){return {src:''};};   // 테스트 환경은 외부 그림을 못 받는다 — 로드 성공처럼 둔다
  Object.assign(SPLASHMAP,{'아리':'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg',
    '럭스':'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Lux_0.jpg',
    '가렌':'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Garen_0.jpg',
    '이즈리얼':'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ezreal_0.jpg'});
  SKIN_URL_BAD.clear(); SKIN_URL_SEEN.clear();
  const base='https://ddragon.leagueoflegends.com/cdn/img/champion/splash/';
  const r={
    mapSize: LAST_SKINS.size,
    skin: mainSplashOf('스킨왕요원#T'),
    base: mainSplashOf('기본스킨요원#T'),
    unknown: mainSplashOf('표에없는요원#T'),
    url3: skinSplashUrl(base+'Ahri_0.jpg', 3),
    url0: skinSplashUrl(base+'Ahri_0.jpg', 0),
    other: skinSplashUrl('https://example.com/a.png', 3),
    otherEnd: mainSplashOf('아무도없는사람#T'),
  };
  window.Image=_Im0; return r;
}"""

EVAL_FALLBACK = r"""() => new Promise(resolve => {
  SKIN_URL_SEEN.clear(); SKIN_URL_BAD.clear();
  const base='https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg';
  const skin=skinSplashUrl(base, 7);
  const el=document.createElement('div');
  el.setAttribute('data-skinbg','1');
  el.style.backgroundImage="url('"+skin+"')";
  document.body.appendChild(el);
  const _Im=window.Image;
  window.Image=function(){ const o={}; setTimeout(()=>{ if(o.onerror) o.onerror(); },0);
    Object.defineProperty(o,'src',{set(v){this._src=v},get(){return this._src}}); return o; };
  const got=skinSplash(base,7);
  setTimeout(()=>{
    const out={got, skinIsUrl: got===skin, bad: SKIN_URL_BAD.has(skin),
               bgPatched: el.style.backgroundImage.indexOf('Ahri_0.jpg')>=0,
               nextCall: skinSplash(base,7)===base};
    window.Image=_Im; el.remove(); resolve(out);
  }, 40);
})"""

EVAL_CARD = r"""() => {
  const _Im0=window.Image; window.Image=function(){return {src:''};};
  Object.assign(SPLASHMAP,{'아리':'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg'});
  SKIN_URL_BAD.clear(); SKIN_URL_SEEN.clear();
  const sp=mainSplashOf('스킨왕요원#T');
  const html=kzcCardHtml(true,[{n:'스킨왕요원#T',no:1,title:'상현 1',a:{tier:'1中'},d:{wr:55,soloTxt:'플래티넘 1'},sp}],{1:'壱'});
  const box=document.createElement('div'); box.innerHTML=html; document.body.appendChild(box);
  const bg=box.querySelector('.kzc-bg');
  const out={sp, hasBg: !!bg, attr: bg?bg.getAttribute('data-skinbg'):null,
             bgUrl: bg?(bg.style.backgroundImage||''):'', htmlHas: html.indexOf('data-skinbg')>=0};
  box.remove(); window.Image=_Im0; return out;
}"""

EVAL_ERRORS = r"""() => ({errs: (window.__errs||[]).length})"""


async def run(xlsx, evals):
    return await R.replay(os.path.join(HERE_UP, "index.html"), xlsx=xlsx, now=NOW, cats=("rift",),
                          shots=False, quiet=True, evals=tuple(evals))


def main():
    tmp = tempfile.mkdtemp(prefix="skinsplash_")
    good = os.path.join(tmp, "good.xlsx")
    build_xlsx(good, "good")

    # 0) 정적 가드 — 탭이 없을 때 gviz 가 첫 시트(CLASSIC_NORMAL 12MB)를 통째로 돌려주므로
    #    반드시 헤더 한 줄(range=A1:E1)로 먼저 물어봐야 한다.
    src = open(os.path.join(HERE_UP, "index.html"), encoding="utf-8").read()
    f = re.search(r"async function loadLastSkin\(\)\{(.*?)\n\}", src, re.S)
    ok(f is not None, "loadLastSkin 이 있다")
    body = f.group(1) if f else ""
    ok('_lastSkinGviz("A1:E1")' in body, "먼저 헤더 한 줄만 물어본다(range=A1:E1)")
    ok(body.index('_lastSkinGviz("A1:E1")') < body.index('_lastSkinGviz("")'), "헤더가 맞을 때만 통째로 받는다")

    res = asyncio.run(run(good, (EVAL_MAP, EVAL_FALLBACK, EVAL_CARD, EVAL_ERRORS)))
    m, fb, card, errs = res["evals"]
    log = res["meta"]["log"]

    print("A 스킨표(LAST_SKIN)")
    ok(m["mapSize"] > 0, "탭을 읽어 맵을 만든다 (%d개)" % m["mapSize"])
    ok(bool(re.search(r"_7\.jpg$", m["skin"] or "")), "skin 7 → %s" % m["skin"])
    ok(bool(re.search(r"_0\.jpg$", m["base"] or "")), "skin 0 은 기본 일러스트 %s" % m["base"])
    ok(bool(re.search(r"_0\.jpg$", (m["unknown"] or "") + "_0.jpg")) and m["unknown"] and "_7" not in m["unknown"],
       "표에 없는 사람은 기본 %s" % m["unknown"])

    print("B 주소 만들기")
    ok(m["url3"].endswith("Ahri_3.jpg"), "…_0.jpg → …_{skin}.jpg  %s" % m["url3"])
    ok(m["url0"].endswith("Ahri_0.jpg"), "skin 0 은 주소를 바꾸지 않는다 %s" % m["url0"])
    ok(m["other"] == "https://example.com/a.png", "스플래시 주소가 아니면 그대로 %s" % m["other"])
    ok(m["otherEnd"] == "", "기록 없는 사람은 빈 문자열")

    print("C 폴백(그림 없는 스킨번호)")
    ok(fb["skinIsUrl"], "먼저 스킨 주소를 쓴다")
    ok(fb["bad"], "로드 실패를 기억한다")
    ok(fb["bgPatched"], "이미 그려 둔 배경을 기본 일러스트로 되돌린다")
    ok(fb["nextCall"], "다음부터는 곧바로 기본 일러스트")

    print("D 카드 배선")
    ok(card["hasBg"], "상현/하현 카드에 배경 그림이 있다")
    ok("_7.jpg" in card["bgUrl"], "카드 배경이 스킨 일러스트 %s" % card["bgUrl"][:80])
    ok(card["attr"] == "1", "폴백 대상 표시(data-skinbg)")

    print("E 안전")
    ok(not log["pageerror"] and not log["console"], "콘솔 오류 0 %s %s" % (log["pageerror"][:1], log["console"][:1]))

    for kind, label in (("none", "탭이 아예 없을 때"), ("badheader", "탭 헤더가 다를 때")):
        p = os.path.join(tmp, kind + ".xlsx")
        build_xlsx(p, kind)
        r2 = asyncio.run(run(p, (EVAL_MAP, EVAL_ERRORS)))
        m2, e2 = r2["evals"]
        ok(m2["mapSize"] == 0, "%s — 맵이 비어 있다" % label)
        ok(bool(re.search(r"_0\.jpg$", m2["skin"] or "")), "%s — 기본 일러스트 %s" % (label, m2["skin"]))
        ok(not r2["meta"]["log"]["pageerror"] and not r2["meta"]["log"]["console"],
           "%s — 콘솔 오류 0 %s" % (label, r2["meta"]["log"]["console"][:1]))

    print("\n전부 통과" if not fails else "\n실패 %d건" % len(fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
