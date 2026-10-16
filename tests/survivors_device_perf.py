# -*- coding: utf-8 -*-
"""📱 기기 통일 성능 검증 — 폰 화면(360×800 · DPR2 · 코어 4=LOW)에서 CPU 를 4×·6× 늦추고 후반(30·50분) 한 프레임(update+draw) 비용을 잰다.
   사용: python3 tests/survivors_device_perf.py OLD.html NEW.html [반복=3]   (원본은 건드리지 않고 임시 사본에만 훅을 꽂는다)"""
import asyncio, sys, os, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_device_common as C, sv_harness as H
from playwright.async_api import async_playwright
FF = r"""(a)=>{const x=window.__p6x;let g=0;while(g<4e6){const st=x.state;if(st==='lvup'){x.pick(x.CUR[0]);continue;}if(st!=='play'){x.resume();continue;}
 const S=x.S;if(S.t>=a.until)break;S.p.hp=S.p.mhp;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];x.update(1/20);g++;}return x.S.t;}"""
MEAS = r"""(a)=>{const x=window.__p6x,U=[],D=[];let n=0;while(n<a.n){const st=x.state;if(st==='lvup'){x.pick(x.CUR[0]);continue;}if(st!=='play'){x.resume();continue;}
 const S=x.S;S.p.hp=S.p.mhp;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];
 const t0=performance.now();x.update(1/30);const t1=performance.now();x.draw();const t2=performance.now();U.push(t1-t0);D.push(t2-t1);n++;}
 const m=v=>v.reduce((a,b)=>a+b,0)/v.length,q=(v,p)=>{const s=[...v].sort((a,b)=>a-b);return s[Math.min(s.length-1,Math.floor(s.length*p))];};
 let live=0;for(const e of window.__dv.enemies.a)if(e.on)live++;const T=U.map((u,i)=>u+D[i]);return {upd:m(U),drw:m(D),tot:m(T),p95:q(T,.95),live,t:x.S.t};}"""
async def one(b, port, name, throttle, until_list, n):
    ctx, pg, errs = await C.page(b, port, name, 360, 800, 4, 4242, throttle=None, mobile=True)
    await pg.evaluate("window.__p6x.start()"); out = {}
    for u in until_list:
        c = await ctx.new_cdp_session(pg); await c.send('Emulation.setCPUThrottlingRate', {'rate': 1})
        await pg.evaluate(FF, {'until': u})
        await c.send('Emulation.setCPUThrottlingRate', {'rate': throttle})
        out[u] = await pg.evaluate(MEAS, {'n': n})
    await ctx.close(); return out, errs
async def main():
    files = sys.argv[1:3]; reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    names = ['OLD', 'NEW']; cp = [C.make(f, 'dvf_%d.html' % i) for i, f in enumerate(files)]
    until = [int(x) for x in os.environ.get('PERF_AT', '1800,3000').split(',')]; thr = [int(x) for x in os.environ.get('PERF_THR', '4,6').split(',')]
    srv = H.Srv(); res = {(n, t, u): [] for n in names for t in thr for u in until}
    async with async_playwright() as p:
        b = await H.launch(p)
        for r in range(reps):
            for t in thr:
                for n, f in zip(names, cp):
                    o, errs = await one(b, srv.port, os.path.basename(f), t, until, 300)
                    for u in until: res[(n, t, u)].append(o[u])
                    print('  [%d/%d] %dx %s' % (r + 1, reps, t, n), {u: (round(o[u]['tot'], 1), o[u]['live']) for u in until}, errs[:2], flush=True)
        await b.close()
    srv.close()
    for f in cp: os.remove(f)
    print('폰 360×800@2x · 코어4(LOW) · 프레임당 ms (update / draw / 합 / 95%%) · %d회 중앙값' % reps)
    for t in thr:
        for u in until:
            print(' CPU %d× · 게임시간 %d초' % (t, u))
            for n in names:
                v = res[(n, t, u)]; med = lambda k: statistics.median(x[k] for x in v)
                print('   %-4s update %6.2f  draw %6.2f  합 %6.2f  p95 %6.2f  (살아있는 적 %d)' % (n, med('upd'), med('drw'), med('tot'), med('p95'), med('live')))
asyncio.run(main())
