# -*- coding: utf-8 -*-
"""🎬 클랜영상(#영상신청) 재생기 시험 — `python3.13 tests/web_clip_player_test.py`
2026-11-27 사장님 「모바일로 영상시청 테스트해보니까 영상이 중간에 멈춘 상태로 보이는데 사운드는 진행되는 현상」

  A 영상 상자는 넣는 순간 CSS 로 정해진다 — 메타데이터가 와도 크기가 안 바뀐다(재생 중 크기 변화 = 안드로이드 화면 굳음 원인)
    · <video> 에 playsinline 과 webkit-playsinline 이 같이 있다 · 부모(.cl-player)가 16:9 상자다
  B 같은 클립으로 다시 그려도 재생기는 그대로다(엘리먼트 교체 없음) — 댓글만 새로 그린다
  C 새 클립이 올라오면 그때만 새로 그린다
  D 탭을 옮기면 숨은 채로 소리만 흐르지 않는다(일시정지)
  E 화면만 멈추면(재생 위치는 흐르는데 그려진 프레임 수가 그대로) 한 번 자동으로 다시 붙이고,
    두 번 그래도 멈추면 자동 재시도를 그만두고 「원본 내려받기」 안내만 남긴다
  F 콘솔 오류 0 · 가로 넘침 0

  실제 봇 서버·디스코드 CDN 은 부르지 않는다(외부 요청은 전부 막고, 주소만 진짜 모양으로 쓴다).
"""
import asyncio, os, sys, threading, http.server, socketserver

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHROME = os.environ.get("PW_CHROME") or next((p for p in [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome"] if os.path.exists(p)), None)

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c:
        fails.append(m)

FIX = {"id": "1575175253603254453",
       "url": "https://cdn.discordapp.com/attachments/1/2/encoded_DOR_2026-11-26_00-41-09.mp4?ex=1&is=2&hm=3&",
       "filename": "encoded_DOR.mp4", "caption": "알리스타", "author": "맛동산장인 유미/94",
       "created_at": "2026-11-25T15:44:05.800000+00:00"}

SETUP = r"""(f)=>{
  document.body.insertAdjacentHTML('beforeend','<div class="wrap" id="host" style="padding:0 12px"><div id="ytHomePane"></div></div>');
  CLIP_HOME.clip=clipNorm(f); CLIP_HOME.comments=[]; CLIP_HOME.err=false;
  ytHomePaint();
  return true;
}"""

# A: 상자 크기·속성
A_JS = r"""()=>{
  const v=document.getElementById('clVideo'), p=document.getElementById('clPlayer');
  const r=p.getBoundingClientRect(), cs=getComputedStyle(v), rv=v.getBoundingClientRect();
  const box0={w:Math.round(r.width),h:Math.round(r.height)};
  try{ Object.defineProperty(v,'videoWidth',{get:()=>1280}); Object.defineProperty(v,'videoHeight',{get:()=>720}); }catch(e){}
  v.dispatchEvent(new Event('loadedmetadata'));
  const r2=p.getBoundingClientRect();
  return {box0, box1:{w:Math.round(r2.width),h:Math.round(r2.height)},
    ar:getComputedStyle(p).aspectRatio, inline:v.getAttribute('playsinline'), wk:v.getAttribute('webkit-playsinline'),
    preload:v.getAttribute('preload'), vmax:cs.maxHeight, vw:Math.round(rv.width), vh:Math.round(rv.height), cvw:cs.width, cvh:cs.height, ratio:+(r.width/r.height).toFixed(3)};
}"""

# B: 같은 클립 재그리기
B_JS = r"""()=>{const v0=document.getElementById('clVideo');
  CLIP_HOME.comments=[{author:'테스터',text:'안녕',ts:1795735464}]; ytHomePaint();
  return {same:v0===document.getElementById('clVideo'), cnt:document.getElementById('clCmtCnt').textContent,
          rows:document.querySelectorAll('#clCmtList .cl-row').length};}"""

# C: 다른 클립
C_JS = r"""(f)=>{const v0=document.getElementById('clVideo');
  CLIP_HOME.clip=clipNorm(Object.assign({},f,{id:'1575175253603254999'})); ytHomePaint();
  const v1=document.getElementById('clVideo');
  return {same:v0===v1, cid:v1&&v1.getAttribute('data-cid')};}"""

# D: 탭 전환 = 일시정지
D_JS = r"""()=>{const v=document.getElementById('clVideo'); window.__paused=0;
  Object.defineProperty(v,'paused',{get:()=>false,configurable:true});
  v.pause=()=>{window.__paused=1;};
  clipSetTab('yt');
  return {paused:window.__paused, clipHidden:document.getElementById('clPanelClip').style.display==='none'};}"""

# E: 화면 멈춤 감지 → 자동 재붙임, 두 번이면 포기
E_JS = r"""()=>{const v=document.getElementById('clVideo');
  v._clRetry=0; v._clStuck=0; v._clSeen=0;
  const t0=performance.now();
  let frames=1000; window.__loads=0;
  Object.defineProperty(v,'currentTime',{get:()=>(performance.now()-t0)/1000,configurable:true});
  Object.defineProperty(v,'paused',{get:()=>false,configurable:true});
  Object.defineProperty(v,'ended',{get:()=>false,configurable:true});
  Object.defineProperty(v,'seeking',{get:()=>false,configurable:true});
  Object.defineProperty(v,'readyState',{get:()=>4,configurable:true});
  Object.defineProperty(v,'getVideoPlaybackQuality',{value:()=>({totalVideoFrames:frames,droppedVideoFrames:0}),configurable:true});
  v.load=()=>{window.__loads++;};   // 표면 새로 만들기 = load() : 세기만 한다
  return true;}"""

E_READ = r"""()=>({loads:window.__loads||0, hidden:document.getElementById('clFix').hidden,
  tx:(document.getElementById('clFixTx')||{}).textContent||'', bad:document.getElementById('clFix').classList.contains('bad')})"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=REPO, **k)
        def log_message(self, *a):
            pass
    class S(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
    s = S(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]


async def main():
    from playwright.async_api import async_playwright
    srv, port = serve()
    base = "http://127.0.0.1:%d" % port
    async with async_playwright() as pw:
        br = await pw.chromium.launch(executable_path=CHROME) if CHROME else await pw.chromium.launch()
        ctx = await br.new_context(viewport={"width": 360, "height": 800}, is_mobile=True, has_touch=True,
                                   user_agent="Mozilla/5.0 (Linux; Android 14; SM-S921N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Mobile Safari/537.36")
        pg = await ctx.new_page()
        errs, msgs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: msgs.append(m.text) if m.type == "error" else None)

        async def route(r):
            if r.request.url.startswith(base):
                await r.continue_()
            else:
                await r.abort()
        await pg.route("**/*", route)
        await pg.goto(base + "/index.html", wait_until="domcontentloaded")
        await pg.wait_for_timeout(1200)
        errs.clear(); msgs.clear()          # 부팅 중 막아 버린 외부 요청 소음은 세지 않는다

        ok(await pg.evaluate("()=>typeof clipBodyHtml==='function'&&typeof ytHomePaint==='function'"), "부팅: 클립 재생 코드가 올라와 있다")
        await pg.evaluate(SETUP, FIX)
        await pg.wait_for_timeout(200)

        a = await pg.evaluate(A_JS)
        ok(a["box0"] == a["box1"], "A 메타데이터가 와도 상자 크기가 그대로 %s → %s" % (a["box0"], a["box1"]))
        ok(1.75 < a["ratio"] < 1.81, "A 상자가 16:9 비율이다 %s (%s)" % (a["ratio"], a["ar"]))
        ok(a["inline"] == "" and a["wk"] == "", "A playsinline·webkit-playsinline 둘 다 있다 (%r, %r)" % (a["inline"], a["wk"]))
        ok(a["preload"] == "metadata", "A preload=metadata")
        ok(a["vmax"] == "none" and abs(a["vw"] - a["box0"]["w"]) <= 1 and abs(a["vh"] - a["box0"]["h"]) <= 1,
           "A <video> 가 상자를 그대로 채운다(max-height 는 상자에만) %s %s %s" % (a["vmax"], (a["vw"], a["vh"]), (a["cvw"], a["cvh"])))

        b = await pg.evaluate(B_JS)
        ok(b["same"], "B 같은 클립 재그리기 = 재생기 그대로")
        ok(b["cnt"] == "1" and b["rows"] == 1, "B 댓글만 새로 그려진다 %s" % b)

        c = await pg.evaluate(C_JS, FIX)
        ok(not c["same"] and c["cid"] == "1575175253603254999", "C 새 클립이면 새로 그린다 %s" % c)

        d = await pg.evaluate(D_JS)
        ok(d["paused"] == 1 and d["clipHidden"], "D 탭을 옮기면 일시정지하고 패널이 숨는다 %s" % d)
        await pg.evaluate("()=>clipSetTab('clip')")

        await pg.evaluate(E_JS)
        await pg.wait_for_timeout(4200)
        e1 = await pg.evaluate(E_READ)
        ok(e1["loads"] == 1 and not e1["hidden"], "E 화면 멈춤 감지 → 자동으로 한 번 다시 붙인다 %s" % e1)
        ok("다시" in e1["tx"], "E 안내 문구가 보인다 %r" % e1["tx"])
        await pg.wait_for_timeout(5000)
        e2 = await pg.evaluate(E_READ)
        ok(e2["loads"] == 2, "E 두 번째까지는 자동 재시도 %s" % e2)
        ok(e2["bad"] and "내려받" in e2["tx"], "E 두 번 멈추면 자동 재시도를 멈추고 원본 내려받기를 안내 %r" % e2["tx"])

        ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
        ok(ov["sw"] <= ov["cw"] + 1, "F 가로 넘침 0 %s" % ov)
        ok(not errs, "F 콘솔 오류 0 %s" % (errs[:2],))
        netonly = [m for m in msgs if "Failed to load resource" not in m]
        ok(not netonly, "F 콘솔 error 0 %s" % (netonly[:2],))

        await ctx.close(); await br.close()
    srv.shutdown()
    print("\n전부 통과" if not fails else "\n실패 %d건" % len(fails))
    sys.exit(1 if fails else 0)


asyncio.run(main())
