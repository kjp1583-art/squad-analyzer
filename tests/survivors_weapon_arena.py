# -*- coding: utf-8 -*-
"""⚔️ 무기별 실전 세기 측정기 — 같은 아레나(적 45마리가 계속 채워지는 곳 · 달리는 플레이어)에서 무기 한 자루만 들고 10초 동안 낸 피해를 잰다.
[2026-10-15 사장님 「드래곤브레스가 너무 세다 — 브레스 하향, 다른 무기는 상향해서 평균값으로」] 무기 40여 종을 같은 틀로 견주는 도구.
  · 상태 4가지: Lv1 · Lv5 · Lv8 · 각성(Lv8 + ev). 시드 N개 평균. 캐릭터 고유능력(CSX)은 끈다.
  · 허수아비 밭(--field): 움직이지 않는 불사 허수아비 7마리 앞에서 같은 시간 낸 피해 — 범위/관통이 유리한 무기가 얼마나 앞서는지.
사용  nice -n 10 python3 tests/survivors_weapon_arena.py --seeds 8 --out /tmp/wa.json [--html survivors.html] [--only breath,feed]"""
import asyncio, json, os, sys, argparse, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SV_CSX_OFF'] = '1'
import sv_harness as H
from playwright.async_api import async_playwright

ARENA = r"""(a)=>{const x=__p6x;let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 x.CH_set(a.ch);x.start();const S=x.S,p=S.p,dt=1/30;
 S.w={};S.w[a.w]=a.L;S.cd={};S.ev=a.ev?{[a.w]:1}:{};S.tier={};S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};x.tkCalc();x.synCalc();
 S.t=a.t||90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 const fill=()=>{let c=0;for(const q of x.enemies.a)if(q.on)c++;for(;c<45;c++){const g=Math.random()*6.2832,r=140+Math.random()*280;if(!x.spawnEnemy((Math.random()*3)|0,a.hm||2.5,null,{x:p.x+Math.cos(g)*r,y:p.y+Math.sin(g)*r}))break;}};
 const step=()=>{if(x.state==='lvup'){x.pick(x.CUR[0]);return;}if(x.state!=='play'){x.resume();return;}
   S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];fill();x.update(dt);x.props.clear();};
 const W=Math.round((3+8*Math.random())/dt);for(let i=0;i<W;i++)step();S.dmgBy={};for(let i=0;i<300;i++)step();
 let tot=0;for(const k in S.dmgBy)tot+=S.dmgBy[k];
 return {d:S.dmgBy[a.w]||0,tot,state:x.state};}"""
FIELD = r"""(a)=>{const x=__p6x,dt=1/30;
 const mb=s=>()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(a.seed);
 x.CH_set(a.ch);x.newRun();x.state='play';const S=x.S,P=S.p;S.t=300;
 S.w={};S.w[a.w]=a.L;S.ev=a.ev?{[a.w]:1}:{};S.tier={};S.cd={};S.cd[a.w]=0;S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};x.tkCalc();x.synCalc();
 S.nextBoss=S.nextMini=S.nextSp=S.evT=S.bigT=1e12;S.propT=S.chickT=1e12;S.spawnT=-1e12;S.need=1e12;S.xp=0;
 for(const e of x.enemies.a)e.on=false;x.props.clear();
 const D=[];for(let i=0;i<7;i++){const th=i*0.9,R=70+i*28;const e=x.spawnEnemy(0,1,null,{x:Math.cos(th)*R,y:Math.sin(th)*R});e.hx=e.x=Math.cos(th)*R;e.hy=e.y=Math.sin(th)*R;e.sp=0;e.kb=0;e.hp=e.mhp=1e12;D.push(e);}
 S.dmgBy={};
 for(let s=0;s<300;s++){P.hp=P.mhp=1e9;P.inv=1e9;S.spawnT=-1e12;S.need=1e12;S.xp=0;for(const e of D){e.on=true;e.x=e.hx;e.y=e.hy;e.hp=e.mhp;e.sp=0;}x.update(dt);}
 return {d:S.dmgBy[a.w]||0};}"""
BOSSJS = r"""(a)=>{const x=__p6x,dt=1/30;
 const mb=s=>()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(a.seed);
 x.CH_set(a.ch);x.start();const S=x.S,P=S.p;
 S.w={};S.w[a.w]=a.L;S.cd={};S.ev=a.ev?{[a.w]:1}:{};S.tier={};S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};x.tkCalc();x.synCalc();
 S.t=1500;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;S.spawnT=-1e12;
 for(const e of x.enemies.a)e.on=false;x.props.clear();
 const B=x.spawnBoss('sr');B.sp=0;B.x=P.x+140;B.y=P.y;const m=B.mhp;
 S.dmgBy={};
 for(let s=0;s<300;s++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}P.hp=P.mhp;P.inv=1e9;S.spawnT=-1e12;S.need=1e12;S.xp=0;for(const e of x.enemies.a)if(e.on&&e!==B)e.on=false;B.on=true;B.hp=B.mhp;B.sp=0;B.x=P.x+140;B.y=P.y;x.update(dt);x.props.clear();}
 return {d:S.dmgBy[a.w]||0,m};}"""
STATES = [('L1', 1, 0), ('L5', 5, 0), ('L8', 8, 0), ('EV', 8, 1)]

async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--html', default='survivors.html'); ap.add_argument('--seeds', type=int, default=8)
    ap.add_argument('--out', required=True); ap.add_argument('--only', default=''); ap.add_argument('--field', action='store_true'); ap.add_argument('--boss', action='store_true'); ap.add_argument('--hm', type=float, default=2.5, help='아레나 적 체력 배율(기본 2.5 = 초반 · 14 = 10분차 · 33 = 20분차). 약하면 한 방에 다 죽어 세기가 포화된다'); ap.add_argument('--t', type=int, default=90, help='아레나 시계(초) — 클수록 적 체력이 크다(90초 = 초반 · 1200초 = 20분차 적)')
    a = ap.parse_args()
    H.make_copy(a.html, 'survivors_wa_%d.html' % os.getpid()); srv = H.Srv()
    name = 'survivors_wa_%d.html' % os.getpid()
    res = {}
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page=name)
        ws = await pg.evaluate("()=>Object.keys(__p6x.WEAP).map(k=>({k,only:__p6x.WEAP[k].only||null,pair:__p6x.WEAP[k].pair||null}))")
        only = [s for s in a.only.split(',') if s]
        for w in ws:
            k = w['k']
            if only and k not in only: continue
            ch = w['only'] or 'brj'
            r = {}
            for sn, L, ev in STATES:
                v = []
                for sd in range(1, a.seeds + 1):
                    o = await pg.evaluate(ARENA, dict(w=k, L=L, ev=ev, seed=sd, ch=ch, t=a.t, hm=a.hm)); v.append(o['d'])
                r[sn] = statistics.mean(v)
                if a.field:
                    f = [(await pg.evaluate(FIELD, dict(w=k, L=L, ev=ev, seed=sd, ch=ch)))['d'] for sd in range(1, 3)]
                    r['F' + sn] = statistics.mean(f)
            if a.boss:
                for sn, L, ev in STATES[2:]:
                    f = [(await pg.evaluate(BOSSJS, dict(w=k, L=L, ev=ev, seed=sd, ch=ch)))['d'] for sd in range(1, 4)]
                    r['B' + sn] = statistics.mean(f)
            res[k] = r; print(k, ch, {x: round(y) for x, y in r.items()}, flush=True)
        print('errs', errs[:3])
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, name))
    except Exception: pass
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)

asyncio.run(main())
