# -*- coding: utf-8 -*-
"""기기 무관 젠 검증 공용 — 임시 사본에 훅을 꽂고, 뷰포트·hardwareConcurrency·CPU 스로틀을 바꿔 같은 시드로 돌린다."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
EXTRA = "window.__dv={get SN(){return SN},get MAXE(){return MAXE},get SPAWN_R(){return SPAWN_R},get DESP_R(){return DESP_R},get VW(){return VW},get VH(){return VH},get SC(){return SC},eshots,shots,props,enemies};"
# Math.random 을 시드 고정(mulberry32) — 같은 시드면 두 뷰포트가 같은 난수열을 쓴다
SEED_JS = "(function(){let a=%d>>>0;Math.random=function(){a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};})();"
def hwc_js(n): return "Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>%d});" % n
def make(src_path, dst_name):
    s = open(src_path, encoding='utf-8').read()
    m = re.search(r"window\.__p6=\{[^\n]*\};", s); assert m
    s = s.replace(m.group(0), m.group(0) + '\n' + H.HOOK + EXTRA).replace('const INV_CAP=.80;', 'let INV_CAP=.80;')
    p = os.path.join(H.ROOT, dst_name); open(p, 'w', encoding='utf-8').write(s); return p
async def page(b, port, name, w, h, hwc, seed, throttle=None, mobile=False):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    await ctx.add_init_script(hwc_js(hwc)); await ctx.add_init_script(SEED_JS % seed)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    await pg.goto('http://127.0.0.1:%d/%s' % (port, name)); await pg.wait_for_function('window.__dv!==undefined', timeout=20000)
    if throttle:
        c = await ctx.new_cdp_session(pg); await c.send('Emulation.setCPUThrottlingRate', {'rate': throttle})
    return ctx, pg, errs
# 무적 봇이 사각형으로 돌며 카드 첫 장을 고른다. sample 초마다 (시간, 살아있는 적, 출생번호 SN) 기록
JS_RUN = r"""(a)=>{const x=window.__p6x,out=[];let next=a.step;const dt=1/20;let g=0;
 while(g<4e6){const st=x.state;if(st==='lvup'){x.pick(x.CUR[0]);continue;}if(st==='chest'||st==='pause'||st==='revive'){x.resume();continue;}if(st==='result')break;if(st!=='play'){x.resume();continue;}
  const S=x.S;if(S.t>=a.until)break;S.p.hp=S.p.mhp;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];x.update(dt);g++;
  if(S.t>=next){let n=0;for(const e of x.enemies.a)if(e.on)n++;out.push([Math.round(S.t),n,window.__dv.SN,S.kills||S.k||0]);next+=a.step;}}
 return out;}"""
