# -*- coding: utf-8 -*-
"""웹(index.html)을 구글 시트 스냅샷으로 재생한다 — 실제 사이트와 같은 코드가 같은 데이터를 읽게 해서
선수별 평가(솔랭 칸 글자·power·십이귀월)와 화면을 꺼낸다.

  python3 tests/web_replay/replay.py --xlsx <시트.xlsx> --src index.html --out <폴더> [--focus 닉네임 …]

구글 시트로 가는 모든 요청(gviz fetch · JSONP <script> · responseHandler 콜백 · gid= / sheet= 두 방식)을 브라우저
안에서 가로채 스냅샷으로 답한다. 스냅샷은 저장소에 없다(경로로 받는다). 스냅샷에 없는 탭은 빈 표로 답하고 meta.json 의 missing 에,
알아볼 수 없는 요청(모르는 문서·gid)은 unknown 에 남으며 표준 오류에도 경고로 찍힌다 — 조용히 실패하지 않는다.
"""
import argparse
import asyncio
import json
import mimetypes
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gviz  # noqa: E402

ORIGIN = "http://127.0.0.1:8765"
CHROME = os.environ.get("PW_CHROME") or next((p for p in [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome"] if os.path.exists(p)), None)

# index.html 상수에서 읽는 탭 연결 — gid -> 탭 이름. 카테고리 key 는 웹 CATEGORIES 와 같다.
CAT_TABS = {"rift": "CLASSIC_NORMAL", "aram": "KIWI_KIWI", "classic": "LOL_CLASSIC"}

DUMP_JS = r"""
() => {
  const strip = h => String(h==null?'':h).replace(/<[^>]*>/g,'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim();
  const players = [];
  for (const [name, a] of ASSESSMENTS) {
    const d = a.detail || null;
    let soloCell = null;
    if (d && d.solo != null) { try { soloCell = strip(soloCellParts(name, d, () => '', '').v); } catch (e) { soloCell = 'ERR ' + e.message; } }
    players.push({
      name, tier: a.tier, label: a.label, games: a.games, title: a.title || null,
      power: a.power == null ? null : a.power, score: d ? d.score : null,
      solo: d ? d.solo : null, soloCur: d ? d.soloCur : null, soloTxt: d ? d.soloTxt : null, soloWR: d ? d.soloWR : null,
      soloCell, implTier: a.implTier || null, implPct: a.implPct == null ? null : a.implPct,
    });
  }
  const ord = t => { const m = /^(상현|하현)\s*(\d+)/.exec(t || ''); return m ? (m[1] === '상현' ? 0 : 10) + (+m[2]) : 99; };
  const roster = players.filter(p => p.title).sort((x, y) => ord(x.title) - ord(y.title));
  const solo = {}; for (const k in SOLO_RANKS) { const s = SOLO_RANKS[k]; solo[k] = {score: s.score, cur: s.cur === undefined ? null : s.cur, wins: s.wins, losses: s.losses, wr: s.wr, tier: s.tier || '', lp: s.lp == null || isNaN(s.lp) ? null : s.lp}; }
  const icons = {}; for (const k in PROFILE_ICONS) icons[k] = PROFILE_ICONS[k];
  const meta = {
    buildId: (typeof BUILD_ID !== 'undefined') ? BUILD_ID : null, cat: CURRENT_CAT,
    players: players.length, playersAll: PLAYERS_ALL.size, soloRanks: Object.keys(SOLO_RANKS).length,
    altToMain: ALT_TO_MAIN.size, departed: DEPARTED_SET.size, status: document.querySelector('#status') ? document.querySelector('#status').textContent : null,
  };
  return {players, roster, solo, icons, meta};
}
"""

# 프로필/카드 화면에 실제로 그려진 글자 — 솔랭 칸이 DOM 에서도 같은지 확인용
CELLS_JS = r"""
() => [...document.querySelectorAll('.cmp')].map(e => ({k: (e.querySelector('.cmp-k')||{}).textContent || '', v: (e.querySelector('.cmp-v')||{}).textContent || '', r: (e.querySelector('.cmp-r')||{}).textContent || '', tip: e.getAttribute('title') || ''}))
"""


def _read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Sheets:
    """시트 응답 공급원 — xlsx(기본) 또는 실제 gviz 응답 폴더."""

    def __init__(self, xlsx=None, gviz_dir=None, master=None, sheet_id=None, master_id=None, gid_tab=None):
        self.sheet_id, self.master_id, self.gid_tab = sheet_id, master_id, gid_tab or {}
        self.raw = {}          # 탭 -> (rows, fmts)  (xlsx)
        self.ready = {}        # 탭 -> 이미 만들어진 gviz dict (폴더)
        if xlsx: self.raw = gviz.load_xlsx(xlsx)
        if gviz_dir: self.ready = gviz.load_gviz_dir(gviz_dir)
        self.master = gviz.parse_response_text(_read_text(master)) if master else None
        self._cache = {}

    def tabs(self):
        return sorted(set(self.raw) | set(self.ready))

    def table(self, tab, headers=1):
        key = (tab, headers)
        if key in self._cache: return self._cache[key]
        if headers == 1 and tab in self.ready: out = self.ready[tab]
        elif tab in self.raw:
            rows, fmts = self.raw[tab]
            out = gviz.table_from_rows(rows, fmts, headers=headers)
        else: out = None
        self._cache[key] = out
        return out


def _consts_from_src(src_text):
    """index.html 에서 시트 id · 카테고리 gid · 개별 gid 상수를 읽는다 — 하네스가 웹과 어긋나지 않게."""
    sid = re.search(r'const SHEET_ID\s*=\s*"([^"]+)"', src_text)
    mid = re.search(r'const MASTER_TIER_SHEET_ID\s*=\s*"([^"]+)"', src_text)
    gid_tab = {}
    for key, tab in CAT_TABS.items():
        m = re.search(r'key:"%s"[^}]*?gid:"(\d+)"' % key, src_text)
        if m: gid_tab[m.group(1)] = tab
    for const, tab in (("TIER_HISTORY_GID", "TIER_HISTORY"), ("CLAN_TIERS_GID", "CLAN_TIERS")):
        m = re.search(r'const %s\s*=\s*"(\d+)"' % const, src_text)
        if m: gid_tab[m.group(1)] = tab
    mg = re.search(r'const MASTER_TIER_GID\s*=\s*"(\d+)"', src_text)
    return (sid.group(1) if sid else None, mid.group(1) if mid else None, gid_tab, mg.group(1) if mg else "0")


async def replay(src, xlsx=None, gviz_dir=None, master=None, now=None, out=None, focus=(), shots=True,
                 cats=("rift",), viewport=(430, 960), timeout_s=240, chrome=None, quiet=False, evals=(), after=None):
    """웹을 열어 평가를 꺼낸다. 반환 dict: {rift:{players,roster,solo,icons,meta,focus}, aram:{…}, evals:[…], meta:{…}}
    evals: 로딩이 끝난 뒤 협곡 상태에서 평가해 볼 JS 식(전역 let/const 에 접근 가능) — 결과는 result["evals"] 에 JSON 으로.
    after: 로딩·evals 가 끝난 뒤 브라우저를 닫기 전에 `await after(page)` 를 한 번 부른다(스크린샷·클릭 같은 화면 작업용) — 반환값은 result["after"]."""
    from playwright.async_api import async_playwright
    src = os.path.abspath(src)
    root = os.path.dirname(src)
    src_text = _read_text(src)
    sid, mid, gid_tab, master_gid = _consts_from_src(src_text)
    sheets = Sheets(xlsx, gviz_dir, master, sid, mid, gid_tab)
    if out: os.makedirs(out, exist_ok=True)
    log = {"served": [], "blocked": [], "missing": [], "unknown": [], "console": [], "pageerror": []}

    def note(kind, what):
        if what not in log[kind]: log[kind].append(what)

    async def on_route(route):
        req = route.request
        url = req.url
        u = urllib.parse.urlparse(url)
        # ---- 이 사이트 자체(index.html 과 data/·img/ …) ----
        if url.startswith(ORIGIN + "/") or url == ORIGIN:
            path = urllib.parse.unquote(u.path.lstrip("/")) or "index.html"
            f = src if path == "index.html" else os.path.join(root, path)
            if os.path.isfile(f):
                ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
                with open(f, "rb") as fh: body = fh.read()
                await route.fulfill(status=200, body=body, headers={"content-type": ctype + ("; charset=utf-8" if ctype.startswith("text") or "javascript" in ctype or "json" in ctype else ""), "cache-control": "no-store"})
            else:
                await route.fulfill(status=404, body="")
            return
        # ---- 구글 시트 gviz ----
        m = re.match(r"^/spreadsheets/d/([^/]+)/gviz/tq$", u.path) if u.netloc == "docs.google.com" else None
        if m:
            q = urllib.parse.parse_qs(u.query)
            doc = m.group(1)
            tqx = (q.get("tqx") or [""])[0]
            cb = None
            mc = re.search(r"responseHandler:([\w$.]+)", tqx)
            if mc: cb = mc.group(1)
            headers = int((q.get("headers") or ["1"])[0] or 1)
            gid = (q.get("gid") or [None])[0]
            sheet = (q.get("sheet") or [None])[0]
            if doc == sheets.master_id:
                resp = sheets.master or gviz.empty_table()
                if not sheets.master: note("missing", "MASTER_TIER (--master 로 주지 않아 빈 표로 답함)")
                else: note("served", "MASTER_TIER gid=%s" % gid)
            elif doc != sheets.sheet_id:
                resp = gviz.error_table("모르는 문서 " + doc)
                note("unknown", "모르는 시트 문서 %s" % doc)
            else:
                tab = sheet if sheet else sheets.gid_tab.get(str(gid))
                if tab is None:
                    note("unknown", "모르는 gid=%s" % gid)
                    resp = gviz.error_table("모르는 gid")
                else:
                    resp = sheets.table(tab, headers)
                    if resp is None:
                        # 스냅샷에 없는 탭 — 실제 시트에도 없을 수 있는 탭(PREV_SEASON 등). 빈 표로 답하고 기록한다.
                        note("missing", tab)
                        resp = gviz.empty_table()
                    else:
                        note("served", "%s%s" % (tab, "" if headers == 1 else " (headers=0)"))
            body = gviz.render(resp, cb)
            await route.fulfill(status=200, body=body, headers={"content-type": "text/javascript; charset=utf-8", "access-control-allow-origin": "*", "cache-control": "no-store"})
            return
        if u.netloc == "raw.githubusercontent.com" and u.path.endswith("/version.txt"):
            await route.fulfill(status=200, body="0.0.0", headers={"content-type": "text/plain", "access-control-allow-origin": "*"})
            return
        # 그 밖(이미지·폰트·디스코드·앱스스크립트·ddragon…)은 막는다 — 무엇을 막았는지는 남긴다
        note("blocked", "%s%s" % (u.netloc, u.path[:60]))
        await route.abort()

    result = {}
    async with async_playwright() as pw:
        br = await pw.chromium.launch(executable_path=chrome or CHROME, headless=True, args=["--no-sandbox"])
        ctx = await br.new_context(viewport={"width": viewport[0], "height": viewport[1]}, device_scale_factor=2 if shots else 1,
                                   is_mobile=viewport[0] < 700, has_touch=viewport[0] < 700)
        await ctx.route("**/*", on_route)
        if now:
            # 시계 고정 — Date.now()/new Date() 만 now 로 맞춘다(타이머는 그대로). 시험이 날짜에 안 흔들리게.
            await ctx.add_init_script("""(()=>{const RD=Date,off=%d-RD.now();
              class FD extends RD{constructor(...a){if(a.length===0)super(RD.now()+off);else super(...a);}static now(){return RD.now()+off;}}
              window.Date=FD;})();""" % _ms(now))
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: log["pageerror"].append(str(e)[:300]))
        pg.on("console", lambda m: log["console"].append(m.text[:300]) if m.type == "error" and "Failed to load resource" not in m.text else None)
        await pg.goto(ORIGIN + "/index.html")
        ready = "(()=>{const s=document.querySelector('#status'); return !!s && /플레이어 \\d+명|불러오기 실패/.test(s.textContent);})()"
        await pg.wait_for_function(ready, timeout=timeout_s * 1000)
        await pg.wait_for_timeout(800)
        st = await pg.evaluate("document.querySelector('#status').textContent")
        if "실패" in st: raise RuntimeError("웹 로딩 실패: " + st)

        async def dump(cat):
            d = await pg.evaluate(DUMP_JS)
            d["focus"] = {}
            for fname in focus:
                hit = await pg.evaluate("""(f)=>{const k=tnorm(f); for(const [n] of ASSESSMENTS) if(tnorm(n)===k) return n; for(const [n] of PLAYERS_ALL) if(tnorm(n)===k) return n; return null;}""", fname)
                info = {"name": hit}
                if hit:
                    info["player"] = next((p for p in d["players"] if p["name"] == hit), None)
                    if shots and out and cat == "rift":
                        safe = re.sub(r"[^\w가-힣]+", "_", fname)
                        await pg.evaluate("(n)=>go('player', n)", hit)
                        await pg.wait_for_timeout(700)
                        info["profileCells"] = await pg.evaluate(CELLS_JS)
                        await pg.evaluate("window.scrollTo(0,0)")
                        info["profileShot"] = os.path.join(out, "focus_%s_profile.png" % safe)
                        await pg.screenshot(path=info["profileShot"], full_page=False)
                        info["profileStatsShot"] = await _shot_stats(pg, os.path.join(out, "focus_%s_profile_stats.png" % safe))
                        await pg.evaluate("(n)=>openPlayerCard(n)", hit)
                        await pg.wait_for_timeout(500)
                        info["cardCells"] = await pg.evaluate(CELLS_JS)
                        info["cardShot"] = os.path.join(out, "focus_%s_card.png" % safe)
                        await pg.screenshot(path=info["cardShot"], full_page=False)
                        info["cardStatsShot"] = await _shot_stats(pg, os.path.join(out, "focus_%s_card_stats.png" % safe))
                        await pg.evaluate("closePlayerCard()")
                d["focus"][fname] = info
            return d

        result["rift"] = await dump("rift")
        result["evals"] = [await pg.evaluate(js) for js in evals]
        if after: result["after"] = await after(pg)
        for cat in cats:
            if cat == "rift": continue
            await pg.evaluate("(c)=>{loadCategory(c)}", cat)
            label = {"aram": "칼바람", "classic": "클래식"}.get(cat, cat)
            await pg.wait_for_function("(l)=>{const s=document.querySelector('#status'); return !!s && s.textContent.startsWith(l+' —') && /플레이어 \\d+명/.test(s.textContent);}", arg=label, timeout=timeout_s * 1000)
            await pg.wait_for_timeout(800)
            result[cat] = await dump(cat)
        await br.close()
    result["meta"] = {"src": src, "xlsx": xlsx, "gvizDir": gviz_dir, "master": master, "now": now, "log": log}
    if out:
        for cat, d in result.items():
            if cat in ("meta", "evals"): continue
            with open(os.path.join(out, "%s.json" % cat), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(result["meta"], f, ensure_ascii=False, indent=1)
        if evals:
            with open(os.path.join(out, "evals.json"), "w", encoding="utf-8") as f:
                json.dump(result["evals"], f, ensure_ascii=False, indent=1)
    if not quiet:
        for k in ("unknown", "missing", "pageerror", "console"):
            for x in log[k]: print("[%s] %s" % (k, x), file=sys.stderr)
    return result


async def _shot_stats(pg, path):
    """🏅솔랭 칸이 든 지표 칸 묶음(프로필 · 카드 팝업 공통)만 찍는다. 칸이 없으면 None."""
    h = await pg.evaluate_handle("() => { const c=[...document.querySelectorAll('.cmp')].find(e=>/솔랭/.test(e.textContent)); return c? c.parentElement : null; }")
    el = h.as_element()
    if not el: return None
    await el.scroll_into_view_if_needed()
    await el.screenshot(path=path)
    return path


def _ms(iso):
    import datetime as dt
    d = dt.datetime.fromisoformat(iso)
    if d.tzinfo is None: d = d.replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))   # 날짜는 한국 시각으로 읽는다
    return int(d.timestamp() * 1000)


def print_roster(res, cat="rift", file=sys.stdout):
    for p in res[cat]["roster"]:
        print("%-8s %-24s power=%+.3f solo=%s soloCell=%s tier=%s" % (p["title"], p["name"], p["power"] if p["power"] is not None else float("nan"), p["solo"], p["soloCell"], p["tier"]), file=file)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", help="전체 시트 xlsx 스냅샷")
    ap.add_argument("--gviz-dir", help="실제 gviz 응답을 <탭>.txt 로 저장한 폴더(있으면 xlsx 보다 우선)")
    ap.add_argument("--master", help="마스터 티어표(별도 시트) gviz 응답 글자 파일 — 없으면 빈 표")
    ap.add_argument("--src", default="index.html", help="재생할 index.html (기본: 현재 폴더)")
    ap.add_argument("--out", required=True, help="결과 폴더(JSON·PNG)")
    ap.add_argument("--focus", nargs="*", default=[], help="화면을 찍을 선수 닉네임(태그 없이)")
    ap.add_argument("--cats", default="rift,aram", help="읽을 카테고리(rift,aram,classic)")
    ap.add_argument("--now", help="시계 고정(예: 2026-10-09T15:00:00, 한국 시각)")
    ap.add_argument("--eval", nargs="*", default=[], dest="evals", help="로딩 뒤 평가해 볼 JS 식(결과는 evals.json)")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--width", type=int, default=430)
    a = ap.parse_args()
    if not (a.xlsx or a.gviz_dir): ap.error("--xlsx 또는 --gviz-dir 가 필요합니다")
    res = asyncio.run(replay(a.src, a.xlsx, a.gviz_dir, a.master, a.now, a.out, a.focus, not a.no_shots,
                             tuple(a.cats.split(",")), (a.width, 960), evals=tuple(a.evals)))
    print_roster(res)
    print("-- 결과 폴더:", a.out)


if __name__ == "__main__":
    main()
