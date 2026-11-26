# -*- coding: utf-8 -*-
"""🎬 클랜영상(#영상신청) 팝업 재생기 시험 — `python3.13 tests/web_clip_player_test.py`
2026-11-27 사장님 「유저아이디를 누르면 뜨는 그 전적카드 팝업 형식으로 영상을 띄워 달라」
   (앞선 요청) 「모바일로 영상시청 테스트해보니까 영상이 중간에 멈춘 상태로 보이는데 사운드는 진행되는 현상」

  A 홈 카드는 미리보기만 — 홈에 <video> 가 없다(제목·업로더·날짜·댓글 수·재생 아이콘·16:9 그림칸)
  B 카드를 누르면 팝업(#clipModal)이 열리고 그 안에서 재생된다
    · <video> 에 playsinline·webkit-playsinline · 부모(.cl-player)가 16:9 고정 상자
    · 메타데이터가 와도 상자 크기가 안 바뀐다(재생 중 크기 변화 = 안드로이드 화면 굳음 원인)
  C 팝업이 떠 있는 동안 카드를 다시 그려도 재생기는 그대로다(엘리먼트 교체 없음) — 댓글 수만 새로 그린다
  D 팝업에 띄운 클립이 아닌 새 클립이 오면 팝업은 닫힌다(제목·댓글이 어긋나지 않게)
  E 탭을 옮기면 팝업이 닫히고 일시정지된다(숨은 채로 소리만 흐르지 않게)
  F 화면만 멈추면(재생 위치는 흐르는데 그려진 프레임 수가 그대로) 한 번 자동으로 다시 붙이고,
    두 번 그래도 멈추면 자동 재시도를 그만두고 「원본 내려받기」 안내만 남긴다
  G 닫기 — ✕ · 바깥(배경) 누르기 · Esc 셋 다 일시정지 + src 정리 + 본문 스크롤 복구
  H 폰(360)과 PC(1280) 모두 팝업이 화면 밖으로 넘치지 않고 재생기가 16:9 다
  I 콘솔 오류 0 · 가로 넘침 0
  J ▶ 유튜브 최신 카드도 같은 팝업으로 열리고(iframe 은 팝업 안에서만) 닫으면 함께 사라진다

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

# A: 홈 카드는 미리보기만
A_JS = r"""()=>{
  const card=document.getElementById('clCard'), th=card?card.querySelector('.cl-card-th'):null;
  const r=th?th.getBoundingClientRect():{width:0,height:0};
  return {card:!!card, videos:document.querySelectorAll('video').length,
    cid:card&&card.getAttribute('data-cid'), role:card&&card.getAttribute('role'),
    play:!!(card&&card.querySelector('.cl-card-play')), tag:!!(card&&card.querySelector('.cl-card-tag')),
    ttl:(card&&card.querySelector('.yt-ttl')||{}).textContent||'',
    meta:(card&&card.querySelector('.yt-meta')||{}).textContent||'',
    ar:th?getComputedStyle(th).aspectRatio:null, ratio:r.width?(+(r.width/r.height).toFixed(3)):0,
    tab:card&&card.getAttribute('tabindex')};
}"""

# B: 카드 클릭 → 팝업에서 재생
B_JS = r"""()=>{
  const card=document.getElementById('clCard'); card.click();
  const back=document.querySelector('#clipModal .clm-back'), modal=document.querySelector('#clipModal .clm-card');
  const v=document.getElementById('clVideo'), p=document.querySelector('#clipModal .cl-player');
  if(!v||!p) return {open:!!back, video:false};
  const cs=getComputedStyle(v), rv=v.getBoundingClientRect();
  const box0={w:Math.round(p.getBoundingClientRect().width),h:Math.round(p.getBoundingClientRect().height)};
  try{ Object.defineProperty(v,'videoWidth',{get:()=>1280}); Object.defineProperty(v,'videoHeight',{get:()=>720}); }catch(e){}
  v.dispatchEvent(new Event('loadedmetadata'));
  const r2=p.getBoundingClientRect();
  return {open:!!back&&!!modal, video:true, dialog:modal&&modal.getAttribute('role'),
    box0, box1:{w:Math.round(r2.width),h:Math.round(r2.height)},
    ar:getComputedStyle(p).aspectRatio, inline:v.getAttribute('playsinline'), wk:v.getAttribute('webkit-playsinline'),
    preload:v.getAttribute('preload'), vmax:cs.maxHeight,
    vw:Math.round(rv.width), vh:Math.round(rv.height), ratio:+(r2.width/r2.height).toFixed(3),
    overflow:document.body.style.overflow, src:!!v.getAttribute('src'),
    x:!!document.querySelector('#clipModal .clm-x'), fix:!!document.getElementById('clFix'),
    cmt:!!document.getElementById('clCmtList')};
}"""

# C: 같은 클립으로 카드를 다시 그려도 팝업 재생기는 그대로
C_JS = r"""()=>{const v0=document.getElementById('clVideo'), c0=document.getElementById('clCard');
  CLIP_HOME.comments=[{author:'테스터',text:'안녕',ts:1795735464}]; ytHomePaint();
  return {sameVideo:v0===document.getElementById('clVideo'), newCard:c0!==document.getElementById('clCard'),
          cnt:document.getElementById('clCmtCnt').textContent, cardCnt:document.getElementById('clCardCmt').textContent,
          rows:document.querySelectorAll('#clCmtList .cl-row').length};}"""

# D: 다른 클립이 오면 팝업은 닫힌다
D_JS = r"""(f)=>{window.__paused=0;
  const v=document.getElementById('clVideo');
  if(v) v.pause=()=>{window.__paused=1;};
  CLIP_HOME.clip=clipNorm(Object.assign({},f,{id:'1575175253603254999'})); ytHomePaint();
  const card=document.getElementById('clCard');
  return {id:card&&card.getAttribute('data-cid'), modalGone:!document.getElementById('clVideo'),
          cleared:document.getElementById('clipModal').innerHTML==='', paused:window.__paused};}"""

# E: 탭 전환 = 팝업 닫힘 + 일시정지
E_JS = r"""()=>{window.__paused=0;
  const v=document.getElementById('clVideo'); if(v){ Object.defineProperty(v,'paused',{get:()=>false,configurable:true}); v.pause=()=>{window.__paused=1;}; }
  clipSetTab('yt');
  return {paused:window.__paused, modalGone:!document.getElementById('clVideo'),
          clipHidden:document.getElementById('clPanelClip').style.display==='none'};}"""

# F: 화면 멈춤 감지 → 자동 재붙임, 두 번이면 포기
F_JS = r"""()=>{
  CLIP_HOME.clip=clipNorm(clipNorm.__f||{}); }"""
F_ARM = r"""(f)=>{CLIP_HOME.clip=clipNorm(f); CLIP_HOME.comments=[]; ytHomePaint(); clipOpen();
  const v=document.getElementById('clVideo');
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

F_READ = r"""()=>({loads:window.__loads||0, hidden:document.getElementById('clFix').hidden,
  tx:(document.getElementById('clFixTx')||{}).textContent||'', bad:document.getElementById('clFix').classList.contains('bad')})"""

# G: 닫기 세 가지 — ✕ · 배경 · Esc
G_JS = r"""(how)=>{
  const before=document.getElementById('clVideo');
  window.__paused=0; window.__focused=null;
  if(before){ before.pause=()=>{window.__paused=1;}; }
  if(how==='x') document.querySelector('#clipModal .clm-x').click();
  else if(how==='back') document.querySelector('#clipModal .clm-back').click();
  else document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  return {paused:window.__paused, hasSrc:before?before.hasAttribute('src'):null,
    emptied:document.getElementById('clipModal').innerHTML==='', overflow:document.body.style.overflow,
    open:CLIP_MODAL.open, cardFocus:document.activeElement&&document.activeElement.id};}"""

# H: 팝업이 화면 안에 들어오는지
H_JS = r"""()=>{
  if(!document.getElementById('clVideo')) clipOpen();
  const b=document.querySelector('#clipModal .clm-back').getBoundingClientRect();
  const c=document.querySelector('#clipModal .clm-card').getBoundingClientRect();
  const p=document.querySelector('#clipModal .cl-player').getBoundingClientRect();
  const vw=window.innerWidth, vh=window.innerHeight;
  return {vw, vh, left:Math.round(c.left), right:Math.round(c.right), top:Math.round(c.top), bottom:Math.round(c.bottom),
    cw:Math.round(c.width), ch:Math.round(c.height), okBox:c.left>=-1&&c.top>=-1&&c.right<=vw+1&&c.bottom<=vh+1,
    ratio:+(p.width/p.height).toFixed(3), back:c.width<=vw&&c.height<=vh};
}"""


# J: 유튜브 탭 카드도 같은 팝업으로 (iframe 은 팝업 안에서만)
J_JS = r"""()=>{
  clipSetTab('yt');
  const card=document.getElementById('ytCard'); if(!card) return {card:false};
  card.click();
  const ifr=document.querySelector('#clipModal .clm-yt iframe');
  const p=document.querySelector('#clipModal .cl-player').getBoundingClientRect();
  const o={card:true, iframe:!!ifr, src:ifr?ifr.getAttribute('src'):'', ratio:+(p.width/p.height).toFixed(3),
    overflow:document.body.style.overflow, dialog:!!document.querySelector('#clipModal .clm-card[role="dialog"]')};
  clipCloseModal();
  o.after=document.getElementById('clipModal').innerHTML==='';
  o.inlineYt=document.querySelectorAll('#ytHomePane iframe').length;   // 홈 카드 자리에는 iframe 이 없다
  clipSetTab('clip');
  return o;
}"""


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
        br = await pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"]) if CHROME else await pw.chromium.launch(args=["--no-sandbox"])
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

        ok(await pg.evaluate("()=>typeof clipBodyHtml==='function'&&typeof clipOpen==='function'&&typeof ytHomePaint==='function'"),
           "부팅: 클립 카드·팝업 코드가 올라와 있다")
        await pg.evaluate(SETUP, FIX)
        await pg.wait_for_timeout(200)

        a = await pg.evaluate(A_JS)
        ok(a["card"] and a["videos"] == 0, "A 홈 카드는 미리보기만 — <video> %d개 %s" % (a["videos"], a["cid"]))
        ok(a["cid"] == FIX["id"] and a["role"] == "button" and a["tab"] == "0", "A 카드가 버튼 역할·키보드 접근 %s %r" % (a["cid"], a["tab"]))
        ok(a["play"], "A 재생 아이콘 오버레이")
        ok("알리스타" in a["ttl"] and "맛동산장인 유미/94" in a["meta"] and "댓글" not in a["meta"] and "0" in a["meta"],
           "A 제목·업로더·날짜·댓글 수 %r / %r" % (a["ttl"], a["meta"]))
        ok(1.75 < a["ratio"] < 1.81, "A 그림칸이 16:9 %s (%s)" % (a["ratio"], a["ar"]))

        b = await pg.evaluate(B_JS)
        ok(b["open"] and b["video"] and b["dialog"] == "dialog", "B 카드를 누르면 팝업이 열린다 %s" % (b.get("open"),))
        ok(b["box0"] == b["box1"], "B 메타데이터가 와도 상자 크기가 그대로 %s → %s" % (b.get("box0"), b.get("box1")))
        ok(1.75 < b["ratio"] < 1.81, "B 팝업 재생기가 16:9 %s (%s)" % (b["ratio"], b["ar"]))
        ok(b["inline"] == "" and b["wk"] == "", "B playsinline·webkit-playsinline 둘 다 있다 (%r, %r)" % (b["inline"], b["wk"]))
        ok(b["preload"] == "metadata", "B preload=metadata")
        ok(b["vmax"] == "none" and abs(b["vw"] - b["box0"]["w"]) <= 1 and abs(b["vh"] - b["box0"]["h"]) <= 1,
           "B <video> 가 상자를 그대로 채운다(max-height 는 상자에만) %s %s" % (b["vmax"], (b["vw"], b["vh"])))
        ok(b["overflow"] == "hidden" and b["src"], "B 뒤 배경 스크롤 잠금 · src 걸림")
        ok(b["x"] and b["fix"] and b["cmt"], "B 닫기 버튼·다시 연결/내려받기·댓글이 팝업 안에 있다")

        c = await pg.evaluate(C_JS)
        ok(c["sameVideo"], "C 팝업이 떠 있는 동안 카드를 다시 그려도 재생기는 그대로")
        ok(c["newCard"] and c["cnt"] == "1" and c["cardCnt"] == "1" and c["rows"] == 1,
           "C 카드·댓글만 새로 그려진다 %s" % c)

        d = await pg.evaluate(D_JS, FIX)
        ok(d["id"] == "1575175253603254999" and d["modalGone"] and d["cleared"] and d["paused"] == 1,
           "D 새 클립이 오면 카드가 바뀌고 팝업은 닫힌다(일시정지) %s" % d)

        await pg.evaluate("()=>{CLIP_HOME.clip=clipNorm(%s); CLIP_HOME.comments=[]; ytHomePaint();}" %
                          __import__("json").dumps(FIX))
        await pg.evaluate("()=>clipOpen()")
        e = await pg.evaluate(E_JS)
        ok(e["paused"] == 1 and e["modalGone"] and e["clipHidden"], "E 탭을 옮기면 팝업이 닫히고 일시정지 %s" % e)
        await pg.evaluate("()=>clipSetTab('clip')")

        await pg.evaluate(F_ARM, FIX)
        await pg.wait_for_timeout(4200)
        f1 = await pg.evaluate(F_READ)
        ok(f1["loads"] == 1 and not f1["hidden"], "F 화면 멈춤 감지 → 자동으로 한 번 다시 붙인다 %s" % f1)
        ok("다시" in f1["tx"], "F 안내 문구가 보인다 %r" % f1["tx"])
        await pg.wait_for_timeout(5000)
        f2 = await pg.evaluate(F_READ)
        ok(f2["loads"] == 2, "F 두 번째까지는 자동 재시도 %s" % f2)
        ok(f2["bad"] and "내려받" in f2["tx"], "F 두 번 멈추면 자동 재시도를 멈추고 원본 내려받기를 안내 %r" % f2["tx"])

        for how in ("x", "back", "esc"):
            if not await pg.evaluate("()=>!!document.getElementById('clVideo')"):
                await pg.evaluate("()=>clipOpen()")
            g = await pg.evaluate(G_JS, how)
            ok(g["paused"] == 1 and g["hasSrc"] is False and g["emptied"] and g["overflow"] == "" and not g["open"],
               "G %s 로 닫기 — 일시정지·src 정리·스크롤 복구 %s" % (how, g))

        h = await pg.evaluate(H_JS)
        ok(h["okBox"] and 1.75 < h["ratio"] < 1.82, "H 폰(360) 팝업이 화면 안 · 재생기 16:9 %s" % h)
        await pg.evaluate("()=>clipCloseModal()")
        await pg.set_viewport_size({"width": 1280, "height": 800})
        await pg.wait_for_timeout(250)
        h2 = await pg.evaluate(H_JS)
        ok(h2["okBox"] and 1.75 < h2["ratio"] < 1.82, "H PC(1280) 팝업이 화면 안 · 재생기 16:9 %s" % h2)
        ok(560 < h2["cw"] <= 800, "H PC 팝업 폭이 읽기 좋은 범위 %d" % h2["cw"])
        await pg.evaluate("()=>clipCloseModal()")
        await pg.set_viewport_size({"width": 360, "height": 800})
        await pg.wait_for_timeout(200)

        j = await pg.evaluate(J_JS)
        ok(j.get("card") and j.get("iframe") and "/embed/" in j.get("src", "") and 1.75 < j.get("ratio", 0) < 1.82,
           "J 유튜브 카드도 같은 팝업에서 재생 %s" % j)
        ok(j.get("dialog") and j.get("overflow") == "hidden" and j.get("after") and j.get("inlineYt") == 0,
           "J 팝업 닫으면 iframe 도 사라진다 %s" % j)

        ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
        ok(ov["sw"] <= ov["cw"] + 1, "I 가로 넘침 0 %s" % ov)
        ok(not errs, "I 콘솔 오류 0 %s" % (errs[:2],))
        netonly = [m for m in msgs if "Failed to load resource" not in m]
        ok(not netonly, "I 콘솔 error 0 %s" % (netonly[:2],))

        await ctx.close(); await br.close()
    srv.shutdown()
    print("\n전부 통과" if not fails else "\n실패 %d건" % len(fails))
    sys.exit(1 if fails else 0)


asyncio.run(main())
