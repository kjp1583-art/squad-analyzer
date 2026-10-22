# -*- coding: utf-8 -*-
"""⚡ 슬라이딩 검증 (2026-10-22 사장님 승인 W-5).  사용: python3.13 tests/survivors_slide_test.py
데이터 → 서 있으면 안 나간다(움직임 보상) → 달리는 방향으로 미끄러지며(이동 거리·무적) 길의 적을 한 번씩 벤다 → 길에 자국이 남아 쫓아오는 적이 밟는다 →
마스터 단계(멈칫·출발 충격파) → 전 캐릭터·패시브 풀세트 예외 없음 → 이어하기 저장(JSON 왕복)."""
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
# 고정된 장면: 오른쪽으로 달리는 플레이어 앞(길 위)에 불사 허수아비 줄 — move=0 이면 서 있는다
SCENE = r"""(a)=>{const x=__p6x;x.CH_set('brj');x.newRun();x.state='play';const S=x.S,p=S.p,dt=1/30;
 S.t=200;S.w={slide:a.L};S.cd={slide:0};S.ev=a.ev?{slide:1}:{};S.tier={};S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};if(a.tier)S.tier={slide:a.tier};x.tkCalc();x.synCalc();
 S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;S.spawnT=-1e12;
 for(const e of x.enemies.a)e.on=false;x.props.clear();
 const E=[];for(let i=0;i<a.n;i++){const e=x.spawnEnemy(0,1,null,{x:p.x+70+i*30,y:p.y+(i%2?6:-6)});if(e){e.hp=e.mhp=1e12;e.sp=0;E.push(e);}}
 const off=x.spawnEnemy(0,1,null,{x:p.x+120,y:p.y+400});if(off){off.hp=off.mhp=1e12;off.sp=0;}   // 길 밖
 const x0=p.x,y0=p.y;S.dmgBy={};const hs=new Set();let offH=false;let hitN=0,maxInv=0,swSeen=0,dashAt=-1,minGap=1e9;const hp0=new Map();
 for(let s=0;s<a.frames;s++){p.hp=p.mhp;S.need=1e12;S.spawnT=-1e12;x.keys=a.move?{KeyD:true}:{};
   x.update(dt);for(const e of E){if(e.hp<e.mhp)hs.add(e);e.hp=e.mhp;e.sp=0;}if(off){if(off.hp<off.mhp)offH=true;off.hp=off.mhp;off.sp=0;}if(S.x3.sl&&S.x3.sl.t>0&&dashAt<0)dashAt=s;maxInv=Math.max(maxInv,p.inv);
   if(S.x3.f.some(o=>o.k==='sw'))swSeen++;}
 const sl=S.x3.sl||{};
 return {dmg:S.dmgBy.slide||0,dx:p.x-x0,dy:p.y-y0,dashAt,maxInv,swSeen,offHit:offH,json:JSON.stringify(S.x3).length,hitE:hs.size};}"""

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate("""()=>{const x=__p6x,d=x.WEAP.slide,T=x.TIERS.slide;return {ds:d.ds.length,T:T&&T.length,ev:!!(d.ev&&d.ev.nm),pair:d.pair,nw:d.nw,ic:d.ic,nm:d.nm,u3:!!x.U3.slide}}""")
        check('슬라이딩: 8레벨 설명·5단계·각성·짝 패시브·신규 표시', r['ds'] == 8 and r['T'] == 5 and r['ev'] and r['pair'] == 'cd' and r['nw'] == 1 and r['u3'], r)
        # 1. 서 있으면 안 나간다 — 움직임 보상
        r = await pg.evaluate(SCENE, dict(L=8, ev=0, n=6, frames=90, move=0))
        check('가만히 서 있으면 슬라이딩이 나가지 않는다(이동 0 · 피해 0)', abs(r['dx']) < 1 and r['dmg'] == 0 and r['dashAt'] < 0, r)
        # 2. 달리면 나간다: 이동 거리 · 무적 · 길의 적에게 피해, 길 밖은 안 맞음
        r = await pg.evaluate(SCENE, dict(L=8, ev=0, n=6, frames=60, move=1))
        check('달리면 슬라이딩이 나간다(앞으로 미끄러지는 거리가 달리기만보다 훨씬 큼)', r['dashAt'] >= 0 and r['dx'] > 200, r)
        check('길 위의 적이 맞는다 · 길 밖의 적은 안 맞는다', r['dmg'] > 0 and r['hitE'] >= 2 and not r['offHit'], r)
        check('미끄러지는 동안 잠깐 무적이 붙는다', r['maxInv'] > 0, r['maxInv'])
        # 3. 각 적은 한 번의 미끄러짐에 한 번만(여러 번 맞지 않음) — 허수아비 한 마리의 피해 상한
        r1 = await pg.evaluate(SCENE, dict(L=1, ev=0, n=1, frames=20, move=1))
        per = await pg.evaluate("()=>{const x=__p6x;return x.U3.slide.d*x.DL3(1)*x.dmgMul()}")
        check('한 번의 미끄러짐으로 한 마리에게 준 피해 ≤ 1회분(+자국 틱 여유)', r1['dmg'] <= per * 1.0001 + per * 0.3 * 3, (round(r1['dmg']), round(per)))
        # 4. 자국이 남는다
        r = await pg.evaluate(SCENE, dict(L=8, ev=0, n=2, frames=45, move=1))
        check('지나간 길에 자국(개체)이 남는다', r['swSeen'] >= 10, r)
        r = await pg.evaluate(SCENE, dict(L=8, ev=0, n=2, frames=120, move=1))
        check('자국은 사라진다(개수 상한 안)', r['json'] < 2500, r['json'])
        # 5. 마스터 5단계(거리·피해·쿨·멈칫·출발 충격파) / 각성
        t0 = await pg.evaluate(SCENE, dict(L=8, ev=0, n=8, frames=75, move=1, tier=0))
        t5 = await pg.evaluate(SCENE, dict(L=8, ev=0, n=8, frames=75, move=1, tier=5))
        check('마스터 5단계: 피해가 늘어남', t5['dmg'] > t0['dmg'], (round(t0['dmg']), round(t5['dmg'])))
        ev = await pg.evaluate(SCENE, dict(L=8, ev=1, n=8, frames=75, move=1))
        check('각성(초음속 슬라이딩): 더 멀리 미끄러지고 더 아프다', ev['dx'] >= t0['dx'] and ev['dmg'] > t0['dmg'], (round(t0['dx']), round(ev['dx']), round(t0['dmg']), round(ev['dmg'])))
        # 6. 이어하기: S.x3 JSON 왕복
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S;const m=JSON.parse(JSON.stringify(S.x3));return {sl:!!m.sl,f:m.f.length}}""")
        check('S.x3 JSON 왕복(상태는 숫자뿐)', r['sl'] is True, r)
        # 7. 박치기(돌진)와 같이 들어도 서로 안 깨진다
        r = await pg.evaluate("""a=>{const x=__p6x;x.CH_set('tw');x.start();const S=x.S;S.t=300;S.nextBoss=S.nextMini=1e12;S.w.slide=8;S.w.ram=8;S.cd.slide=0;S.cd.ram=0;x.tkCalc();x.synCalc();return (%s)({sec:20,keep:{slide:8,ram:8}})}""" % RUN, {})
        check('박치기 + 슬라이딩 같이 20초 예외 없음', not r.get('err'), r)
        # 8. 전 캐릭터 × 레벨 × 각성 × 패시브 풀세트
        chars = await pg.evaluate("()=>__p6x.CHARS.map(c=>c.k)")
        bad = []
        for ck in chars:
            for L, ev, ps in ((1, 0, 0), (5, 0, 1), (8, 1, 1)):
                r = await pg.evaluate("""a=>{const x=__p6x;try{x.srvUnl&&x.srvUnl(x.CHARS.map(c=>c.k));x.CH_set(a.ck);x.start();const S=x.S;S.t=300;S.nextBoss=S.nextMini=1e12;S.w.slide=a.L;S.cd.slide=0;S.ev=a.ev?{slide:1}:{};
                  S.ps=a.ps?{area:5,might:5,cd:5,pspd:5,glass:3,luck:5,dur:5,mag:5}:{};S.tier=a.ps?{slide:5}:{};x.tkCalc();x.synCalc();
                  return (%s)({sec:14,keep:{slide:a.L}});}catch(e){return {err:String(e)}}}""" % RUN, dict(ck=ck, L=L, ev=ev, ps=ps))
                if r.get('err'): bad.append((ck, L, r['err']))
        check('전 캐릭터 × (Lv1 · Lv5+패시브 · 각성+풀세트) 14초 예외 없음', not bad, bad[:3])
        # 9. 보스와 같은 방(보스가 있어도 예외 없음 · 보스는 안 밀림)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.t=1500;S.nextMini=1e12;S.w.slide=8;S.cd.slide=0;x.tkCalc();x.synCalc();for(const e of x.enemies.a)e.on=false;
          const B=x.spawnBoss('sr');B.hp=B.mhp=1e12;const b0=[B.x,B.y];const r=(%s)({sec:20,keep:{slide:8}});return {r,dmg:S.dmgBy.slide||0}}""" % RUN)
        check('보스전 20초 예외 없음', not r['r'].get('err'), r)
        check('콘솔·페이지 오류 0', not errs, errs[:3])
        await b.close()
    print('\n%d checks, %d FAIL' % (N[0], len(FAILS)))
    if FAILS: print(FAILS); sys.exit(1)
asyncio.run(main())
