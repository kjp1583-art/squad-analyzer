# -*- coding: utf-8 -*-
"""📱 모바일 성능 비교 — 같은 시나리오(무적 봇이 첫 카드를 고르며 돌아다님)를 세 버전에서 4배 CPU 제한 + 폰 화면(412x860 · DPR2)으로 돌려
   update+draw 한 프레임의 CPU 시간(ms)을 잰다. 사용: python3 tests/survivors_perf_cmp.py OLD.html BASE.html NEW.html [반복=3]
   (OLD=258c22f · BASE=이번 변경 직전 main · NEW=이번 변경. 원본은 건드리지 않고 임시 사본에만 최소 훅을 꽂는다)"""
import asyncio, sys, os, re, json, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
MIN_HOOK = "window.__pf={get S(){return S},get state(){return state},set state(v){state=v},offers,set keys(v){keys=v},update,draw,pick,resume,newRun,start};"
JS_FF = r"""(a)=>{const x=__pf;let n=0;while(n<200000){const st=x.state;if(st==='lvup'){x.pick(x.offers(3)[0]);continue;}if(st!=='play'){x.resume();continue;}
  const S=x.S;if(S.t>=a.until)break;S.p.hp=S.p.mhp;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];x.update(a.dt);n++;}return x.S.t;}"""
JS_MEAS = r"""(a)=>{const x=__pf;const U=[],D=[];let n=0;while(n<a.n){const st=x.state;if(st==='lvup'){x.pick(x.offers(3)[0]);continue;}if(st!=='play'){x.resume();continue;}
  const S=x.S;S.p.hp=S.p.mhp;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];
  const t0=performance.now();x.update(a.dt);const t1=performance.now();x.draw();const t2=performance.now();U.push(t1-t0);D.push(t2-t1);n++;}
  const q=(v,p)=>{const s=[...v].sort((a,b)=>a-b);return s[Math.min(s.length-1,Math.floor(s.length*p))];};
  const m=v=>v.reduce((a,b)=>a+b,0)/v.length;let live=0;for(const e of window.__pe.a)if(e.on)live++;
  return {upd:m(U),drw:m(D),tot:m(U)+m(D),p95:q(U.map((u,i)=>u+D[i]),.95),live,t:x.S.t};}"""
async def run_one(b, port, page, until_list, reps_n):
    ctx, pg, errs = await H.new_page(b, port, 412, 860, page=page, mobile=True, throttle=4, ready='__pf')
    out = {}
    await pg.evaluate("__pf.start()")
    for u in until_list:
        await pg.evaluate(JS_FF, {'until': u, 'dt': 1 / 20})
        out[u] = await pg.evaluate(JS_MEAS, {'n': reps_n, 'dt': 1 / 30})
    await ctx.close(); return out, errs
async def main():
    files = sys.argv[1:4]; reps = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    names = ['OLD(258c22f)', 'BASE(변경 전 main)', 'NEW(이번 변경)']
    pages = []
    for i, f in enumerate(files):
        s = open(f, encoding='utf-8').read()
        m = re.search(r"window\.__p6=\{[^\n]*\};", s); assert m
        s = s.replace(m.group(0), m.group(0) + '\n' + MIN_HOOK + "window.__pe=enemies;")
        dst = os.path.join(H.ROOT, 'perf_%d.html' % i); open(dst, 'w', encoding='utf-8').write(s); pages.append(os.path.basename(dst))
    srv = H.Srv()
    until = [int(x) for x in os.environ.get('PERF_AT', '300,900,1800').split(',')]
    res = {n: {u: [] for u in until} for n in names}
    async with async_playwright() as p:
        b = await H.launch(p)
        for r in range(reps):
            for n, pgname in zip(names, pages):
                o, errs = await run_one(b, srv.port, pgname, until, 400)
                for u in until: res[n][u].append(o[u])
                print('  [%d/%d] %s' % (r + 1, reps, n), {u: round(o[u]['tot'], 2) for u in until}, flush=True)
                if errs: print('errs', n, errs[:3])
        await b.close()
    srv.close()
    for pgname in pages: os.remove(os.path.join(H.ROOT, pgname))
    print('4x CPU 제한 · 412x860@2x · 프레임당 ms (update / draw / 합 / 95%%) · %d회 중앙값' % reps)
    for u in until:
        print(' 게임시간 %d초 지점' % u)
        for n in names:
            v = res[n][u]; med = lambda k: statistics.median(x[k] for x in v)
            print('   %-20s update %6.2f  draw %6.2f  합 %6.2f  p95 %6.2f  (살아있는 적 %d)' % (n, med('upd'), med('drw'), med('tot'), med('p95'), med('live')))
asyncio.run(main())
