# -*- coding: utf-8 -*-
"""🔢 킬 수 공급 측정기 — 화력(피해 배율)·난이도·모드에 따라 60분 처치 수가 어떻게 변하는지 잰다(무적 봇, 카드는 첫 장).
사용: python3 tests/survivors_kills_sim.py [--end 20] [--dmg 0,5,50,1e5] [--mode n,h,v] [--html survivors.html] [--regen 0|1]
  결과 줄: 분 단위 체크포인트의 처치 · 살아 있는 적 · 스폰 시도/실패(풀 가득) · 보스 소환 마릿수 · 프레임 비용(ms)
"""
import asyncio, sys, os, json, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ap = argparse.ArgumentParser()
ap.add_argument('--end', type=float, default=20); ap.add_argument('--dmg', default='0,5,50,1e5'); ap.add_argument('--mode', default='n')
ap.add_argument('--html', default='survivors.html'); ap.add_argument('--char', default='brj'); ap.add_argument('--dt', type=float, default=0.05)
ap.add_argument('--every', type=float, default=5); ap.add_argument('--bossdelay', type=float, default=0, help='보스를 안 잡고 N초 버티는 시험: 보스 체력을 이 배수로')
ap.add_argument('--boss', default='', help='imm: 보스를 절대 안 잡는다 / kill: 나오는 즉시 잡는다'); ap.add_argument('--low', action='store_true'); ap.add_argument('--seed', type=int, default=1)
A = ap.parse_args()
MODE_JS = {'n': "localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','0');", 'h': "localStorage.setItem('p6_hard','1');localStorage.setItem('p6_vh','0');", 'v': "localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','1');"}
EXTRA = r"""
window.__ks={rg:()=>typeof RGN==="undefined"?1:RGN.m,att:0,fail:0,bossSum:0,spawn:0,killB:0};
{const s0=spawnEnemy;spawnEnemy=function(kind,mult,boss,at){const e=s0(kind,mult,boss,at);if(!boss){__ks.att++;if(!e)__ks.fail++;else __ks.spawn++;}return e;};}
"""
INIT = r"""(()=>{const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};Math.random=mb(%d);
 window.requestAnimationFrame=()=>0;window.cancelAnimationFrame=()=>{};window.AudioContext=undefined;window.webkitAudioContext=undefined;
 Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>%d});try{localStorage.setItem('p6_fx','0');%s}catch(e){}})();"""
STEP = r"""(args)=>{const x=__p6x;const {untilT,dt,dmg,boss}=args;let n=0;const t0=performance.now();
 while(n<400000){const st=x.state;
  if(st==='result'){return {done:'result'};}
  if(st==='lvup'){x.pick(x.CUR[0]);continue;} if(st!=='play'){x.resume();continue;}
  const S=x.S;if(S.t>=untilT)break;S.p.hp=S.p.mhp;S.syn.dmg=dmg;
  if(boss){for(const e of x.enemies.a)if(e.on&&e.boss&&e.boss!=='bgb'){if(boss==='imm'){if(e.mhp<1e17)e.mhp=e.hp=1e18;}else if(boss==='kill')x.hurt(e,1e15);}}
  const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
  x.update(dt);n++;}
 return {n,ms:performance.now()-t0,state:x.state};}"""
async def run(mode, dmg):
    name = 'survivors_ks_%d.html' % os.getpid()
    path = H.make_copy(src=A.html, dst=name, extra='\n' + EXTRA)
    srv = H.Srv()
    out = []
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            ctx = await b.new_context(viewport={'width': 1280, 'height': 720}, screen={'width': 1280, 'height': 720})
            await ctx.add_init_script(INIT % (0x5eed0000 ^ A.seed, 4 if A.low else 8, MODE_JS[mode]))
            base = 'http://127.0.0.1:%d/' % srv.port
            async def route(r):
                await (r.continue_() if r.request.url.startswith(base) else r.abort())
            await ctx.route('**/*', route)
            pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
            await pg.goto(base + name)
            await pg.wait_for_function('window.__p6x!==undefined', polling=50, timeout=20000)
            await pg.evaluate("c=>{const x=__p6x;x.SRVUNL.add(c);const g=x.getProg();g.bk[c]=1;x.setProg(g);x.CH_set(c);x.start();}", A.char)
            m = A.every
            while m <= A.end + 1e-9:
                r = await pg.evaluate(STEP, {'untilT': m * 60, 'dt': A.dt, 'dmg': dmg, 'boss': A.boss})
                if r.get('done'): out.append({'result_at': m}); break
                s = await pg.evaluate("""()=>{const x=__p6x,S=x.S;let live=0,bo=0;for(const e of x.enemies.a)if(e.on){live++;if(e.boss)bo++;}
                  return {t:Math.floor(S.t),k:S.kills,lv:S.lv,m:+__ks.rg().toFixed(2),live,bo,att:__ks.att,fail:__ks.fail,hard:!!S.hard,vh:!!S.vh,nb:S.bossN,sp:+S.spawnT.toFixed(1)}}""")
                s['ms'] = round(r['ms'] / max(1, r['n']), 3); out.append(s)
                print(mode, 'dmg', dmg, json.dumps(s), flush=True)
                m += A.every
            if errs: print('ERRS', errs[:3])
            await b.close()
    finally:
        srv.close()
        try: os.remove(path)
        except Exception: pass
    return out
async def main():
    res = {}
    for mode in A.mode.split(','):
        for d in A.dmg.split(','):
            res['%s/%s' % (mode, d)] = await run(mode, float(d))
    os.makedirs('/tmp/claude-0/kills', exist_ok=True); json.dump(res, open('/tmp/claude-0/kills/last.json', 'w'))
asyncio.run(main())
