# -*- coding: utf-8 -*-
"""🧲 자석 낚시 검증 (2026-10-22 사장님 승인 W-3).  사용: python3.13 tests/survivors_magn_test.py
데이터(8줄 설명·5단계·각성·짝) → 던진 자석이 가장 몰린 곳에 닿아 주변 적을 한 점으로 모은다(보스는 안 끌려옴) → 터진다(모일수록 아프다) →
마스터 단계(멈춤·여진) → Lv1~8·각성·전 캐릭터·패시브 풀세트 예외 없음 → 이어하기 저장(JSON 왕복)."""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SV_CSX_OFF'] = '1'
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

RUN = r"""(a)=>{const x=__p6x;const dt=1/30,N=Math.round(a.sec/dt);
 for(let i=0;i<N;i++){const st=x.state;if(st==='result')return {res:1};
  if(st==='lvup'){x.pick(x.CUR[0]);continue;} if(st!=='play'){x.resume();continue;}
  const S=x.S;S.p.hp=S.p.mhp;S.p.inv=1e9;S.need=1e12;
  if(a.keep){for(const k in a.keep)if(!(S.w[k]>=a.keep[k]))S.w[k]=a.keep[k];}
  const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
  x.update(dt);if(i%3===0)x.draw();}
 return {n:N,state:x.state};}"""
# 고정된 장면: 플레이어 곁 오른쪽에 허수아비 무리(불사) — 한 번 던지게 하고 N프레임 돌린다
SCENE = r"""(a)=>{const x=__p6x;x.CH_set('brj');x.newRun();x.state='play';const S=x.S,p=S.p,dt=1/30;
 S.t=200;S.w={magn:a.L};S.cd={magn:0};S.ev=a.ev?{magn:1}:{};S.tier={};S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};if(a.tier)S.tier={magn:a.tier};x.tkCalc();x.synCalc();
 S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;S.spawnT=-1e12;
 for(const e of x.enemies.a)e.on=false;x.props.clear();x.keys={};
 const cx=p.x+a.dx,cy=p.y,E=[];
 for(let i=0;i<a.n;i++){const g=i*2.4,r=12+i*4,e=x.spawnEnemy(0,1,null,{x:cx+Math.cos(g)*r,y:cy+Math.sin(g)*r});if(e){e.hp=e.mhp=1e12;e.sp=0;E.push(e);}}
 // 무리에서 멀찍이 떨어진 한 마리(끌려와야 한다)
 const far=x.spawnEnemy(0,1,null,{x:cx+110,y:cy});if(far){far.hp=far.mhp=1e12;far.sp=0;}
 let B=null;if(a.boss){B=x.spawnBoss('sr');B.sp=0;B.x=cx-70;B.y=cy;B.hp=B.mhp=1e12;}
 const d0=E.map(e=>Math.hypot(e.x-cx,e.y-cy)),f0=far?Math.hypot(far.x-cx,far.y-cy):0,b0=B?Math.hypot(B.x-cx,B.y-cy):0;
 S.dmgBy={};let pulled=0,seenMg=0,maxF=0;
 for(let s=0;s<a.frames;s++){p.hp=p.mhp;p.inv=1e9;S.need=1e12;S.spawnT=-1e12;for(const e of E){e.hp=e.mhp;e.sp=0;}if(far){far.hp=far.mhp;far.sp=0;}if(B){B.hp=B.mhp;B.sp=0;}
   x.update(dt);for(const e of x.enemies.a)if(e.on&&e.sp!==0&&!e.boss&&!E.includes(e)&&e!==far)e.on=false;
   const mg=S.x3.f.filter(o=>o.k==='mg');if(mg.length)seenMg++;maxF=Math.max(maxF,S.x3.f.length);
   if(mg.length&&mg[0].ph===1)pulled=Math.max(pulled,0);}
 const mgAfter=S.x3.f.filter(o=>o.k==='mg').length;
 const d1=E.map(e=>Math.hypot(e.x-cx,e.y-cy)),f1=far?Math.hypot(far.x-cx,far.y-cy):0,b1=B?Math.hypot(B.x-cx,B.y-cy):0;
 return {dmg:S.dmgBy.magn||0,seenMg,mgAfter,d0:d0.reduce((a,b)=>a+b,0)/d0.length,d1:d1.reduce((a,b)=>a+b,0)/d1.length,f0,f1,b0,b1,json:JSON.stringify(S.x3).length};}"""

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate("""()=>{const x=__p6x,d=x.WEAP.magn,T=x.TIERS.magn;return {ds:d.ds.length,T:T&&T.length,ev:!!(d.ev&&d.ev.nm),pair:d.pair,nw:d.nw,ic:d.ic,nm:d.nm,u3:!!x.U3.magn}}""")
        check('자석 낚시: 8레벨 설명·5단계·각성·짝 패시브·신규 표시', r['ds'] == 8 and r['T'] == 5 and r['ev'] and r['pair'] == 'mag' and r['nw'] == 1 and r['u3'], r)
        # 1. 던지기 → 끌어오기 → 터지기
        a = dict(L=8, ev=0, dx=260, n=14, frames=60, boss=0)
        r = await pg.evaluate(SCENE, a)
        check('Lv8: 자석이 날아가 닿고(개체가 생김) 피해를 냄', r['seenMg'] > 0 and r['dmg'] > 0, r)
        check('떨어져 있던 적이 무리 쪽으로 끌려온다(거리가 절반 아래로)', r['f1'] < r['f0'] * 0.5, (round(r['f0']), round(r['f1'])))
        r2 = await pg.evaluate(SCENE, dict(a, frames=120))
        check('터진 뒤 개체가 모두 정리됨(2초 뒤 개수 0)', r2['mgAfter'] == 0 and r2['dmg'] >= r['dmg'] * 0.9, (r['dmg'], r2['dmg']))
        # 보스는 안 끌려온다
        rb = await pg.evaluate(SCENE, dict(a, boss=1, frames=45))
        check('보스는 끌려오지 않는다(거리 변화 거의 없음)', abs(rb['b1'] - rb['b0']) < 25, (round(rb['b0']), round(rb['b1'])))
        # 모일수록 아프다: 같은 장면에서 적 수가 많으면 한 번 터질 때 피해(적 한 마리 몫이 아니라 총피해)가 늘어난다
        few = await pg.evaluate(SCENE, dict(a, n=3, frames=40))
        many = await pg.evaluate(SCENE, dict(a, n=24, frames=40))
        check('적이 많이 모일수록 총피해가 크다', many['dmg'] > few['dmg'] * 2, (round(few['dmg']), round(many['dmg'])))
        # 마스터 단계: 멈춤(4)·여진(5) — 단계 5 면 여진까지 더해 피해가 늘어남
        t0 = await pg.evaluate(SCENE, dict(a, frames=90, tier=0))
        t5 = await pg.evaluate(SCENE, dict(a, frames=90, tier=5))
        check('마스터 5단계(피해+범위+쿨+멈춤+여진): 피해가 늘어남', t5['dmg'] > t0['dmg'], (round(t0['dmg']), round(t5['dmg'])))
        # 각성: 자석 2개(Lv8 이면 3개) · 피해 증가
        ev = await pg.evaluate(SCENE, dict(a, ev=1, frames=90))
        check('각성(초강력 전자석): 일반 Lv8 보다 피해가 큼', ev['dmg'] > t0['dmg'], (round(t0['dmg']), round(ev['dmg'])))
        # 2. 이어하기: 저장 상태가 JSON 왕복 가능(함수·순환 없음) · 던진 자석이 날아가는 중에 직렬화해도 복구 가능
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S;const mid=JSON.parse(JSON.stringify(S.x3));const f=mid.f.filter(o=>o.k==='mg');return {ok:true,n:f.length}}""")
        check('S.x3 JSON 왕복', r['ok'])
        # 3. 전 캐릭터 × 레벨 × 각성 × 패시브 풀세트 — 예외 없음
        chars = await pg.evaluate("()=>__p6x.CHARS.map(c=>c.k)")
        bad = []
        for ck in chars:
            for L, ev, ps in ((1, 0, 0), (5, 0, 1), (8, 1, 1)):
                r = await pg.evaluate("""a=>{const x=__p6x;try{x.srvUnl&&x.srvUnl(x.CHARS.map(c=>c.k));x.CH_set(a.ck);x.start();const S=x.S;S.t=300;S.nextBoss=S.nextMini=1e12;S.w[a.ck==='x'?'':'magn']=a.L;S.cd.magn=0;S.ev=a.ev?{magn:1}:{};
                  S.ps=a.ps?{area:5,might:5,cd:5,pspd:5,glass:3,luck:5,dur:5,mag:5}:{};S.tier=a.ps?{magn:5}:{};x.tkCalc();x.synCalc();
                  return (%s)({sec:14,keep:{magn:a.L}});}catch(e){return {err:String(e)}}}""" % RUN, dict(ck=ck, L=L, ev=ev, ps=ps))
                if r.get('err'): bad.append((ck, L, r['err']))
        check('전 캐릭터 × (Lv1 · Lv5+패시브 · 각성+풀세트) 14초 예외 없음', not bad, bad[:3])
        # 4. 풀 부담: 적이 많아도 개체 수가 상한(F3CAP) 안
        r = await pg.evaluate(SCENE, dict(a, ev=1, n=40, frames=240))
        check('자석 개체가 쌓이지 않음(상한 안)', r['mgAfter'] <= 3, r)
        check('콘솔·페이지 오류 0', not errs, errs[:3])
        await b.close()
    print('\n%d checks, %d FAIL' % (N[0], len(FAILS)))
    if FAILS: print(FAILS); sys.exit(1)
asyncio.run(main())
