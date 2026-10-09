# -*- coding: utf-8 -*-
"""📢 엄장신 「엄!」 외침 연출 시험 (2026-10-07 사장님 지시 "엄장신의 엄 이펙트 파괴적인 이펙트로 변경").  사용: python3 tests/survivors_eom_fx_test.py
연출 전용이라는 약속(결정 동등) · 전 레벨 1~8 · 각성 · 마스터 · 메아리 · 품질 단계(자동·2·1·0) · 폰/데스크톱 · 풀 상한 · 누수 · 광과민 · 색 규칙 ·
위험 표시 가림 · 지연 호출(메아리·마지막)의 레벨/각성 값 · 반응형 · 소리 · 초기화.
전투 쪽을 건드렸으니 '장비를 끼워' 돌린다(S.ps 풀세트) — 평범한 캐릭터만 돌리면 장비 효과 코드는 한 줄도 안 밟는다.
이 PC 는 코어가 4개 이하라 게임이 LOW 로 판정한다 → 비LOW 경로는 navigator.hardwareConcurrency 를 8 로 속인 컨텍스트로 돌린다(폰 412 폭은 코어와 무관하게 LOW)."""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(n, c, x=''):
    N[0] += 1
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:600] if x and not c else ''), flush=True)
    if not c: FAILS.append(n)
# 게임의 Math.random 을 시드 고정(전투 난수가 연출 때문에 달라지는지 보려고)
MULB = "(()=>{let a=123456789;Math.random=function(){a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};})();"
CORES8 = "Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>8})"   # 4코어 샌드박스에서도 데스크톱·큰 폰을 비LOW 로
async def ctx_page(b, port, w, h, mobile=False, init=None, reduced=None, cores=0, raf=False):
    kw = dict(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    if reduced: kw['reduced_motion'] = reduced
    ctx = await b.new_context(**kw); errs = []
    if cores: await ctx.add_init_script(CORES8)
    if init: await ctx.add_init_script(init)
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/survivors_x.html' % port)
    await pg.wait_for_function('window.__p6x!==undefined', timeout=15000)
    if not raf: await pg.evaluate("window.requestAnimationFrame=()=>0")   # 게임 자체 프레임 루프를 멈춰 시험이 시간을 쥔다(안 막으면 대기 중에 게임 시간이 몇 초씩 흘러 시각이 틀어진다)
    await pg.wait_for_timeout(120)
    return ctx, pg, errs
SETUP = r"""(a)=>{const x=__p6x;x.srvUnl&&x.srvUnl(['yumi','eom']);x.CH_set('eom');x.start();const S=x.S,p=S.p;S.t=a.t||120;S.w.eom=a.L;
  if(a.ev)S.ev.eom=1;S.tier={eom:a.tier||0};if(a.full){S.ps={amt:3,area:5,might:5,cd:5,pspd:5,glass:3,luck:5,dur:5};x.synCalc&&x.synCalc();}x.tkCalc();
  S.nextBoss=S.nextMini=1e9;   // 시각을 건너뛰어도 보스가 나와 붉은 가장자리가 번지지 않게
  if(a.qo!=null)x.EX.qo=a.qo;if(a.off!=null)x.EX.eomOff=a.off;if(a.lv!=null)x.FX.lv=a.lv;
  for(const e of x.enemies.a)e.on=false;
  let k=0,s=a.seed||7;const rnd=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};
  for(let r0=34;r0<=a.R&&k<a.n;r0+=17){const c0=Math.max(6,Math.floor(r0*.16));for(let i=0;i<c0&&k<a.n;i++){const an=i/c0*6.283+r0*.37+(rnd()-.5)*.2;const e=x.spawnEnemy(a.kind||0,1,null,{x:p.x+Math.cos(an)*r0,y:p.y+Math.sin(an)*r0});if(e){if(a.tough){e.hp=e.mhp=1e9;}k++;}}}
  S.cd.eom=.05;p.inv=99;return {k,low:x.LOW};}"""
# ── T1: 구성 격자 — 쿨타임 0 폭주 시전 · update+draw 매 프레임 · 풀 상한 · 'sh' 엔티티 없음 · 값이 유한
GRID = r"""(a)=>{const x=__p6x,S=x.S,p=S.p,EX=x.EX;let m={p:0,r:0,d:0,w:0,q:0,f3:0,bad:0,sh:0,hs:0,shk:0,la:0,fa:0};
  for(let i=0;i<a.frames;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.state='play';}
    p.inv=99;p.hp=p.mhp;if(!a.noCast&&i%a.every===0)S.cd.eom=0;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];
    x.update(1/30);x.draw();const st=EX.stats();m.p=Math.max(m.p,st.p);m.r=Math.max(m.r,st.r);m.d=Math.max(m.d,st.d);m.w=Math.max(m.w,st.w);m.q=Math.max(m.q,st.q);m.la=Math.max(m.la,st.la);
    m.f3=Math.max(m.f3,S.x3.f.length);for(const o of S.x3.f)if(o.k==='sh')m.sh++;
    if(!isFinite(EX.shk)||!isFinite(EX.hs)||EX.hs>.1||EX.shk>20)m.bad++;m.hs=Math.max(m.hs,EX.hs);m.shk=Math.max(m.shk,EX.shk);
    for(const e of x.enemies.a)if(e.on&&(!isFinite(e.fk)||!isFinite(e.fa)||!isFinite(e.x)))m.fa++;}
  m.c=EX.stats().c;return m;}"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p, args=['--autoplay-policy=no-user-gesture-required'])
        # ── T1: 전 레벨 1~8 · 각성 · 마스터 · 메아리 × 뷰포트 3 × 품질 4
        CFG = [(L, 0, 0) for L in range(1, 8)] + [(8, 0, 3), (8, 0, 4), (8, 1, 0), (8, 1, 3), (8, 1, 5), (4, 1, 5)]   # (레벨, 각성, 마스터 단계) — 4단계 이상이면 메아리(실전엔 각성해야 4단계가 열리지만 (8,0,4)로 '작은 비각성 메아리' 경로도 밟는다)
        VPS = {'폰412(LOW)': (412, 860, True, 0, True), '폰430(비LOW)': (430, 932, True, 8, False), '데스크톱(비LOW)': (1280, 720, False, 8, False)}
        for vp, (w, h, mob, cores, want_low) in VPS.items():
            for q in (None, 2, 1, 0):
                ctx, pg, errs = await ctx_page(b, srv.port, w, h, mob, cores=cores)
                bad = []; low = None
                for (L, ev, tier) in CFG:
                    info = await pg.evaluate(SETUP, {'L': L, 'ev': ev, 'tier': tier, 'n': 140, 'R': 150, 'tough': True, 'qo': q, 'full': (L == 8)})
                    low = info['low']
                    r = await pg.evaluate(GRID, {'frames': 110, 'every': 20})
                    ok = r['p'] <= 300 and r['r'] <= 24 and r['d'] <= 16 and r['w'] <= 3 and r['q'] <= 24 and r['f3'] < 100 and r['sh'] == 0 and r['bad'] == 0 and r['fa'] == 0 and sum(r['c']) > 0
                    if not ok: bad.append(((L, ev, tier), r))
                check('격자 %s 품질=%s: Lv1~8·각성·마스터·메아리 예외·상한·\'sh\' 없음' % (vp, 'auto' if q is None else q), not bad and not errs and low == want_low, (bad[:2], errs[:3], 'LOW=%s' % low))
                await ctx.close()
        # ── T1b: 후반(S.lite = 적 150 초과) · ✨ 배경 효과 줄임(FX.lv 1)·끔(FX.lv 0) — 균열은 FX.lv 2 에서만
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720, cores=8)
        res = {}
        for tag, lv, n in [('lite', 2, 175), ('fx1', 1, 100), ('fx0', 0, 100)]:
            await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': n, 'R': 300, 'tough': True, 'full': True, 'lv': lv})
            res[tag] = await pg.evaluate(GRID, {'frames': 110, 'every': 20})
        await pg.evaluate("__p6x.FX.lv=2")
        ok = all(r['p'] <= 300 and r['r'] <= 24 and r['w'] <= 3 and r['q'] <= 24 and r['bad'] == 0 and r['fa'] == 0 and sum(r['c']) > 0 for r in res.values())
        check('후반(적 175)·배경 효과 줄임/끔: 예외 없이 · 상한 안', ok and not errs, (res, errs[:3]))
        check('배경 효과를 줄이거나 끄면 바닥 균열이 안 생김(d 0)', res['fx1']['d'] == 0 and res['fx0']['d'] == 0 and res['lite']['d'] > 0, {k: v['d'] for k, v in res.items()})
        await ctx.close()
        # ── T13: 단계 호출 수 — 비각성 [n,0,0] · 각성(메아리 없음) [0,0,n] (각성하면 첫 외침이 곧 큰 「개엄!」 · 단계 2) · 각성+메아리 [0,n,n]
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        for (L, ev, tier, want) in [(5, 0, 0, 'a'), (8, 1, 3, 'b'), (8, 1, 5, 'c')]:
            await pg.evaluate(SETUP, {'L': L, 'ev': ev, 'tier': tier, 'n': 30, 'R': 120, 'tough': True})
            await pg.evaluate(GRID, {'frames': 90, 'every': 90})
            await pg.evaluate(GRID, {'frames': 45, 'every': 1, 'noCast': True})   # 마지막 시전의 지연 호출(메아리 .4초 · 마지막 .6초)이 끝날 때까지 새 시전 없이 기다린다
            c = await pg.evaluate("__p6x.EX.stats().c")
            ok = (c[0] >= 1 and c[1] == 0 and c[2] == 0) if want == 'a' else (c[0] == 0 and c[1] == 0 and c[2] >= 1) if want == 'b' else (c[0] == 0 and c[1] == c[2] and c[2] >= 1)
            check('시전 단계 호출 수 L%d 각성%d 단계%d: %s' % (L, ev, tier, c), ok, c)
        await ctx.close()
        # ── T14: 지연 호출(메아리·마지막)은 '시전 순간'의 각성 여부·레벨로 연출한다 — weapons3 의 L·ev 는 다른 무기 블록이 계속 덮어쓰는 공용 변수라서
        #   (고치기 전엔 메아리가 '작은 비각성 메아리'로, 레벨이 틀어져 나왔다). EX.eom 을 가로채 호출 인자를 적는다.
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 30, 'R': 120, 'tough': True, 'full': True})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,EX=x.EX,log=[];const orig=EX.eom;EX.eom=function(px,py,R,st,ev,L){log.push([st,ev,L]);return orig.apply(this,arguments);};
          S.w.pcards=6;S.w.ram=3;S.w.snack=5;S.w.chain=2;S.ev.pcards=0;S.ev.ram=0;   // eom 블록 뒤에 도는 블록들이 L·ev 를 다른 값으로 덮어쓴다
          for(let i=0;i<150;i++){S.p.inv=99;S.p.hp=S.p.mhp;if(i===0)S.cd.eom=0;else if(i>1&&S.cd.eom<1)S.cd.eom=1e9;x.update(1/30);}
          EX.eom=orig;return log}""")
        check('지연 호출 인자: 큰 「개엄!」(2)·메아리(1) 모두 각성 1 · Lv8 — 다른 무기 블록이 덮어쓴 값이 아님', r == [[2, 1, 8], [1, 1, 8]], r)
        check('지연 호출 시험에서 오류 없음', not errs, errs[:3])
        await ctx.close()
        # ── T16: 시전 직후 멀리 달려가도(글자·조각·링·균열이 화면 밖으로 밀려남) 예외 없이 · 풀 상한 안 — 화면 밖 컬링 경로
        ctx, pg, errs = await ctx_page(b, srv.port, 430, 932, True, cores=8)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 80, 'R': 200, 'tough': True, 'full': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;S.cd.eom=0;let m=0;for(let i=0;i<60;i++){p.inv=99;p.hp=p.mhp;if(i===14){p.x+=2500;p.y-=1800;}x.update(1/30);x.draw();const t=x.EX.stats();m=Math.max(m,t.p,t.w,t.q);}return {m,st:x.EX.stats()}}""")
        check('시전 직후 멀리 달려가도 예외 없음 · 풀 상한 안', not errs and r['m'] <= 300, (r, errs[:3]))
        await ctx.close()
        # ── T2: 연출 전용 증명 — 같은 시드·같은 입력의 update 만 600스텝, 연출을 끈 판(eomOff=1)과 켠 판의 결과가 정확히 같다
        SIM = r"""(a)=>{const x=__p6x,S=x.S,p=S.p;for(let i=0;i<a.n;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play')x.state='play';
            p.hp=p.mhp;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];x.update(1/30);}
          let eh=0,ex=0,fear=0,slow=0,on=0;for(const e of x.enemies.a)if(e.on){on++;eh+=e.hp;ex+=e.x+e.y*3;if(e.fear>0)fear++;slow+=e.slow;}
          return JSON.stringify({t:+S.t.toFixed(6),px:+p.x.toFixed(6),py:+p.y.toFixed(6),hp:+p.hp.toFixed(6),k:S.kills,dm:Object.fromEntries(Object.entries(S.dmgBy).map(([k,v])=>[k,+v.toFixed(6)])),on,eh:+eh.toFixed(4),ex:+ex.toFixed(4),fear,slow:+slow.toFixed(4)});}"""
        for (L, ev, tier, tag) in [(8, 1, 5, 'Lv8 각성 5단계'), (1, 0, 0, 'Lv1'), (5, 0, 3, 'Lv5 마스터 3단계')]:
            outs = []
            for off in (1, 0):
                ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720, init=MULB)
                await pg.evaluate(SETUP, {'L': L, 'ev': ev, 'tier': tier, 'n': 60, 'R': 160, 'off': off, 'full': True, 'seed': 11})
                outs.append(await pg.evaluate(SIM, {'n': 600}))
                await ctx.close()
            check('연출 전용 증명(%s): 연출 끈 판 == 켠 판' % tag, outs[0] == outs[1], outs)
        # ── T3: 상한·누수 — 200회 연속 시전 · 600프레임 연속 외침 뒤 JS 힙
        ctx, pg, errs = await ctx_page(b, srv.port, 412, 860, True)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 140, 'R': 160, 'tough': True, 'qo': 2})
        r = await pg.evaluate(GRID, {'frames': 200, 'every': 1})
        check('200회 연속 시전: 풀 상한', r['p'] <= 300 and r['r'] <= 24 and r['d'] <= 16 and r['w'] <= 3 and r['q'] <= 24 and r['f3'] < 100, r)
        heap = await pg.evaluate("""()=>{const x=__p6x;gc();const a=performance.memory.usedJSHeapSize;x.EX.qo=2;const S=x.S;for(let i=0;i<600;i++){S.p.inv=99;S.p.hp=S.p.mhp;S.cd.eom=0;x.update(1/30);x.draw();}gc();return (performance.memory.usedJSHeapSize-a)/1048576}""")
        check('600프레임 연속 외침 뒤 JS 힙 증가 3MB 이하(%.2fMB)' % heap, heap < 3, heap)
        await ctx.close()
        # ── T4: 광과민 — 전체 화면 번쩍(S.flash) 상한·간격 · 히트스톱 합 · 모션 줄이기
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720, cores=8)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 100, 'R': 150, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,EX=x.EX;let prev=0,mx=0,edges=[],t=0;const hs=[];
          for(let i=0;i<30*20;i++){S.p.inv=99;S.p.hp=S.p.mhp;EX.hs=0;x.update(1/30);t+=1/30;if(S.flash>prev+.05)edges.push(t);prev=S.flash;mx=Math.max(mx,S.flash);if(EX.hs>0)hs.push([t,EX.hs]);x.draw();}
          let worst=0;for(const e of edges){worst=Math.max(worst,edges.filter(u=>u>=e&&u<e+1).length);}
          let hw=0;for(const [t0] of hs){hw=Math.max(hw,hs.filter(([u])=>u>=t0&&u<t0+1).reduce((a,[,v])=>a+v,0));}
          return {mx,edges:edges.length,worst,hw,hsmax:Math.max(0,...hs.map(h=>h[1]))}}""")
        check('광과민: 전체 화면 번쩍 최대 알파 .35 이하(설계 .14)', r['mx'] <= .35, r)
        check('광과민: 어떤 1초 창에서도 번쩍 상승 3회 이하', r['worst'] <= 3 and r['edges'] >= 2, r)
        check('히트스톱: 한 번 .1초 이하 · 1초 창 합 .2초 이하', r['hsmax'] <= .1 and r['hw'] <= .2, r)
        await ctx.close()
        ctx, pg, errs = await ctx_page(b, srv.port, 412, 860, True)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 60, 'R': 150, 'tough': True, 'qo': 1})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,EX=x.EX;let mf=0;for(let i=0;i<150;i++){S.p.inv=99;S.p.hp=S.p.mhp;EX.hs=0;if(i%30===0)S.cd.eom=0;x.update(1/30);x.draw();mf=Math.max(mf,S.flash);}return {mf}}""")
        check('품질 1(폰·LOW): 전체 화면 번쩍 없음', r['mf'] <= .05, r)
        await ctx.close()
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720, reduced='reduce', cores=8)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 60, 'R': 150, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,EX=x.EX;let mf=0,mh=0,ms=0;for(let i=0;i<150;i++){S.p.inv=99;S.p.hp=S.p.mhp;EX.hs=0;if(i%30===0)S.cd.eom=0;x.update(1/30);x.draw();mf=Math.max(mf,S.flash);mh=Math.max(mh,EX.hs);ms=Math.max(ms,EX.shk);}return {mf,mh,ms}}""")
        check('모션 줄이기(prefers-reduced-motion): 번쩍 0 · 히트스톱 0 · 흔들림 3 이하', r['mf'] <= .05 and r['mh'] == 0 and r['ms'] <= 3, r)
        await ctx.close()
        # ── T5: 색 규칙 — 새 스프라이트에 빨강·주황·노랑·자홍(채도·명도 높은 것)이 없다
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 20, 'R': 100, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.SPX;const cvs={a:S.crackE(0,0,400),b:S.crackE(0,1,400),c:S.crackE(1,0,400),d:S.crackE(1,1,400),e:S.eomT(0,124,0),f:S.eomT(0,124,1),g:S.eomT(1,140,0),h:S.eomT(2,160,1),i:S.eomT(2,160,0)};
          const out={};for(const [k,c] of Object.entries(cvs)){const g=c.getContext('2d'),d=g.getImageData(0,0,c.width,c.height).data;let bad=0,n=0;
            for(let i=0;i<d.length;i+=4){const a=d[i+3];if(a<=40)continue;n++;const r=d[i]/255,gg=d[i+1]/255,b=d[i+2]/255,mx=Math.max(r,gg,b),mn=Math.min(r,gg,b),v=mx,s=mx?(mx-mn)/mx:0;if(s<=.35||v<=.25)continue;
              let h=0;const dd=mx-mn;if(mx===r)h=60*(((gg-b)/dd)%6);else if(mx===gg)h=60*((b-r)/dd+2);else h=60*((r-gg)/dd+4);if(h<0)h+=360;if(h>=290||h<75)bad++;}
            out[k]=[n,bad];}return out}""")
        check('색 규칙: 균열·글자 스프라이트에 빨강·주황·노랑·자홍 없음', all(v[1] <= max(3, v[0] * .002) for v in r.values()), r)
        await ctx.close()
        # ── T6: 위험 표시 가림 — danger 헬퍼 + 글자 알파 상한
        ctx, pg, errs = await ctx_page(b, srv.port, 412, 860, True)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 0, 'tier': 0, 'n': 40, 'R': 100, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,EX=x.EX,p=S.p;const res={};S.cd.eom=1e9;x.update(1/60);   // S.live 를 새로 만든다
          res.none=EX.danger();S.ebooms.push({x:p.x,y:p.y-90,R:60,t:.5,T:.9,d:1,m:'',g:'💔'});res.eb=EX.danger();S.ebooms.length=0;
          S.cone={e:{on:true,sn:0},sn:0,a:0,w:.5,R:300,t:.5,d:1};res.cone=EX.danger();S.cone=null;S.room={x:p.x,y:p.y,R:200,t:3};res.room=EX.danger();S.room=null;
          const e0=x.enemies.a.find(e=>e.on);e0.ph=1;res.ph=EX.danger();e0.ph=0;
          const cl=x.clouds.get();cl.x=p.x;cl.y=p.y;cl.life=3;cl.d=1;cl.own=null;cl.osn=0;res.cloud=EX.danger();cl.on=false;
          S.cd.eom=0;x.update(1/30);for(let i=0;i<3;i++)x.draw();const la0=EX.stats().la;
          S.ebooms.push({x:p.x,y:p.y-90,R:60,t:.9,T:.9,d:1,m:'',g:'💔'});x.draw();const la1=EX.stats().la;S.ebooms.length=0;
          return {res,la0,la1}}""")
        rs = r['res']
        check('위험 표시 검사: 없으면 false · 예고 원·부채꼴·방·독가스·ph1 적이 있으면 true', rs['none'] is False and rs['eb'] and rs['cone'] and rs['room'] and rs['ph'] and rs['cloud'], r)
        check('위험 표시가 있으면 글자 알파 .6 이하 (없을 땐 .8 이상)', r['la0'] >= .8 and 0 < r['la1'] <= .6, r)
        await ctx.close()
        # ── T10: 적 반응은 그리는 동안만 — 논리 좌표·hit·kb·kr 불변, 보스는 움찔 없음
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        await pg.evaluate(SETUP, {'L': 5, 'ev': 0, 'tier': 0, 'n': 50, 'R': 130, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p,EX=x.EX;const bo=x.spawnBoss('sr');bo.x=p.x+60;bo.y=p.y;bo.hp=bo.mhp=1e9;
          S.cd.eom=0;x.update(1/60);const snap=()=>x.enemies.a.filter(e=>e.on).map(e=>[e.x,e.y,e.hit,e.kb,e.kr,e.fear,e.slow].join(','));
          let diff=0,flinch=0;
          for(let i=0;i<20;i++){const a=snap();x.draw();const b=snap();if(a.join('|')!==b.join('|'))diff++;
            for(const e of x.enemies.a)if(e.on&&!e.boss&&e.fa>0&&S.t-e.fk>=0&&S.t-e.fk<.22)flinch++;x.update(1/60);}
          const boss=x.enemies.a.find(e=>e.on&&e.boss);return {diff,flinch,bossFa:boss?boss.fa:-1,kr:Math.max(...x.enemies.a.filter(e=>e.on).map(e=>e.kr))}}""")
        check('적 반응: draw 가 논리 상태(x·y·hit·kb·kr·fear·slow)를 안 바꾼다', r['diff'] == 0, r)
        check('적 반응: 움찔 대상이 있고 · 보스는 없고 · 넉백 저항(kr)은 외침 자신의 밀치기(.3)보다 안 쌓임(그리기가 knock 을 안 부름)', r['flinch'] > 0 and r['bossFa'] == 0 and r['kr'] <= .31, r)
        await ctx.close()
        # ── T11: 밀치기(공포 대신) — 범위 안 일반 적은 모두 나에게서 kd·KB 만큼 밀리고, 범위 밖은 그대로, 보스는 안 밀리고 느려지기만 한다 (2026-10-09 사장님 지시)
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        await pg.evaluate(SETUP, {'L': 5, 'ev': 0, 'tier': 0, 'n': 60, 'R': 150, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p,E3=x.U3.eom;S.cd.eom=1e9;x.update(1/60);   // 시전은 시험이 정한다
          for(const e of x.enemies.a)if(e.on)e.sp=0;   // 적이 스스로 움직이지 않게 해야 밀린 거리만 남는다
          const bo=x.spawnBoss('sr');bo.x=p.x+70;bo.y=p.y;bo.hp=bo.mhp=1e12;bo.sp=0;
          const R=E3.R*1.1*1.1*(x.AR?x.AR():1);
          const pos=x.enemies.a.filter(e=>e.on&&!e.boss).map(e=>({e,x0:e.x,y0:e.y,d0:Math.hypot(e.x-p.x,e.y-p.y)}));
          S.cd.eom=0;x.update(1/60);const slow0=bo.slow;for(let i=0;i<40;i++)x.update(1/60);   // 느려짐은 시전 직후에 읽는다(.5초라 곧 풀린다)
          const inn=pos.filter(o=>o.d0<R-5),out=pos.filter(o=>o.d0>R+40);
          const mv=o=>Math.hypot(o.e.x-o.x0,o.e.y-o.y0),away=o=>Math.hypot(o.e.x-p.x,o.e.y-p.y)-o.d0;
          const kdo=inn.filter(o=>!o.e.bg&&!o.e.el).map(mv);
          return {nIn:inn.length,nOut:out.length,kdMean:kdo.reduce((a,b)=>a+b,0)/Math.max(1,kdo.length),minAway:Math.min(...inn.filter(o=>!o.e.bg&&!o.e.el).map(away)),outMax:Math.max(0,...out.map(mv)),kd:E3.kd,R,
            bossMoved:Math.hypot(bo.x-(p.x+70),bo.y-p.y),bossSlow:slow0}}""")
        check('밀치기: 범위 안 일반 적은 모두 나에게서 멀어진다 · 평균 밀린 거리가 kd(%s)와 같다(±12%%) — %s' % (55, r), r['nIn'] >= 10 and r['minAway'] > 20 and abs(r['kdMean'] - r['kd']) <= r['kd'] * .12, r)
        check('밀치기: 범위 밖 적은 안 밀린다 · 보스는 안 밀리고(좌표 그대로) 느려지기만 한다', r['nOut'] >= 3 and r['outMax'] < 1 and r['bossMoved'] < 1 and r['bossSlow'] > 0, r)
        await ctx.close()
        # ── T11b: 프레임 길이와 상관없이 같은 거리만큼 밀린다(knock 은 프레임마다 ×.9 로 줄어 힘을 맞춰 준다) + 외침으로 접촉 피해가 면제되지 않는다
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        out = {}
        for dtn in (60, 30, 120):
            await pg.evaluate(SETUP, {'L': 3, 'ev': 0, 'tier': 0, 'n': 20, 'R': 100, 'tough': True, 'qo': 2})
            out[dtn] = await pg.evaluate("""(f)=>{const x=__p6x,S=x.S,p=S.p;S.cd.eom=1e9;x.update(1/60);for(const e of x.enemies.a)if(e.on)e.sp=0;
              const es=x.enemies.a.filter(e=>e.on&&!e.boss&&!e.bg&&!e.el&&Math.hypot(e.x-p.x,e.y-p.y)<120).map(e=>({e,x0:e.x,y0:e.y}));S.cd.eom=0;
              for(let i=0;i<Math.round(f*.8);i++){S.p.inv=99;x.update(1/f);}
              return {n:es.length,mv:es.reduce((a,o)=>a+Math.hypot(o.e.x-o.x0,o.e.y-o.y0),0)/Math.max(1,es.length)}}""", dtn)
        mvs = [v['mv'] for v in out.values()]
        check('밀치기 거리는 프레임(30·60·120fps)과 상관없이 같다 — %s' % {k: round(v['mv'], 1) for k, v in out.items()}, all(v['n'] >= 5 for v in out.values()) and max(mvs) - min(mvs) <= .08 * max(mvs), out)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 0, 'tier': 0, 'n': 1, 'R': 40, 'tough': True, 'qo': 2})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;const e=x.enemies.a.find(e=>e.on);e.x=p.x+20;e.y=p.y;e.sp=0;e.kb=0;S.cd.eom=1e9;p.inv=0;p.hp=p.mhp=1e9;x.update(1/60);const h0=p.hp;
          // 밀쳐지기 전 접촉: 같은 프레임에 닿아 있으면 맞는다(공포 때문에 접촉 피해가 면제되던 규칙은 없다)
          e.kb=0;e.kx=e.ky=0;e.x=p.x+20;e.y=p.y;p.inv=0;x.update(1/60);return {dmg:h0-p.hp,fear:e.fear}}""")
        check('외침이 접촉 피해를 면제하지 않는다(공포 규칙 삭제) — %s' % r, r['dmg'] > 0 and r.get('fear') is None, r)
        await ctx.close()
        # ── T12: 초기화·반응형 — start() 뒤 전부 0 · 좁은 화면(360)에서도 격자 통과
        ctx, pg, errs = await ctx_page(b, srv.port, 360, 740, True)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 100, 'R': 150, 'tough': True, 'qo': 1})
        await pg.evaluate(GRID, {'frames': 60, 'every': 10})
        await pg.evaluate("()=>{const x=__p6x;x.start();x.draw();}")
        z = await pg.evaluate("()=>JSON.stringify(__p6x.EX.stats())")
        st = json.loads(z)
        check('새 판(start) 뒤 연출 풀이 전부 0', st['p'] == 0 and st['r'] == 0 and st['d'] == 0 and st['w'] == 0 and st['q'] == 0 and st['c'] == [0, 0, 0], z)
        check('좁은 화면(360)에서 예외 없음', not errs, errs[:3])
        await ctx.close()
        # ── T15: 게임 자체 프레임 루프(requestAnimationFrame)로 몇 초 — 히트스톱(update 건너뛰기)·흔들림·소리가 실제 루프에서 예외 없이 돈다
        ctx, pg, errs = await ctx_page(b, srv.port, 430, 932, True, cores=8, raf=True)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 5, 'n': 60, 'R': 200, 'tough': True, 'full': True})
        await pg.evaluate("""()=>{const x=__p6x,E=x.EX,orig=E.eom;x.AU.init();window.__m={hs:0,shk:0};   // 시전 직후의 히트스톱·흔들림 값을 EX.eom 뒤에서 바로 적는다(타이머로 훑으면 놓칠 수 있다)
          E.eom=function(){const r=orig.apply(this,arguments);window.__m.hs=Math.max(window.__m.hs,E.hs);window.__m.shk=Math.max(window.__m.shk,E.shk);return r;};x.S.p.inv=99;x.S.cd.eom=.05;}""")
        for _ in range(25):   # 쿨타임(약 2.5~3초)을 두 번 넘길 때까지 최대 25초 기다린다(느린 PC 에서도 흔들리지 않게)
            await pg.wait_for_timeout(1000)
            r = await pg.evaluate("()=>({st:__p6x.state,c:__p6x.EX.stats().c,m:window.__m,t:__p6x.S.t})")
            if sum(r['c']) >= 4: break
        check('실제 프레임 루프(최대 25초): 계속 play · 외침이 두 번 이상 · 히트스톱·흔들림이 실제로 일어남 · 오류 없음', r['st'] == 'play' and sum(r['c']) >= 4 and r['m']['hs'] > 0 and r['m']['shk'] > 1 and not errs, (r, errs[:3]))
        await ctx.close()
        # ── 소리 — 모든 변형 예외 없이 · GAP 안쪽 재호출도 예외 없이
        ctx, pg, errs = await ctx_page(b, srv.port, 1280, 720)
        r = await pg.evaluate("""async()=>{const x=__p6x;x.AU.init();await new Promise(r=>setTimeout(r,300));let ok=true;try{for(const a of [0,3,1,4,2]){x.AU.play('eom',a);await new Promise(r=>setTimeout(r,140));}x.AU.play('eom',0);x.AU.play('eom',0);}catch(e){ok=String(e)}return ok}""")
        check('소리: eom 5변형 재생 예외 없음', r is True, r)
        check('페이지 오류·콘솔 에러 없음(소리 포함)', not errs, errs[:3])
        await ctx.close()
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('\n%d 개 중 실패 %d: %s' % (N[0], len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
