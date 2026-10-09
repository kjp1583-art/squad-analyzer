# -*- coding: utf-8 -*-
"""🧩 밸런스 묶음 1 — 다섯 변경이 서로 간섭하지 않는지 보는 통합 시험 (2026-10-09 사장님 「3ok」「4ok」「5권장」「6 바로수정」 + 명상 방어막 주기형).  사용: python3 tests/survivors_pack1_test.py
  ① 프싱 용 변신 × 명상 방어막   ② 부활 × 방어막 × 막기 쿨(1.2초)   ③ Lv10/20 지급 × 레벨업 카드 순서 × 부활 후보(Lv20)
  ④ 시너지 범위 × 광역 패시브 × 프싱 충전 배율(서로 다른 식이라 겹쳐도 각자 값)   ⑤ 매 프레임 때리는 연타에서도 막기가 이어 붙지 않는다
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅(__p6x)을 꽂는다. 종료코드 0 = 전부 통과."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

LIB = r"""
window.__fresh=function(ch,lv){const x=__p6x;x.CH_set(ch);x.start();const S=x.S;S.p.hp=S.p.mhp=1e6;S.rel={};if(lv)S.rel.still=lv;S.stillT=0;S.shield=0;S.p.inv=0;S.lastBlock=-9;return S;};
window.__relRun=function(S,secs,dt){const x=__p6x;let first=null;const t0=S.t;for(let i=0;i<Math.round(secs/dt);i++){S.t+=dt;S.p.inv=Math.max(0,S.p.inv-dt);x.relTick(dt);if(S.shield&&first===null)first=+(S.t-t0).toFixed(3);}return first;};
0;   // 마지막 식이 함수면 evaluate 가 그 함수를 호출해 버린다 — 0 으로 끝낸다
"""

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate(LIB)

        # ① 프싱 용 변신 × 명상 방어막
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh('psg',3);const a=__relRun(S,20.1,1/30);const s1=S.shield;
          x.shvStart();const keep=S.shield,dT=S.dT;               // 변신 시작이 방어막을 먹거나 시간을 건드리지 않는다
          const hp0=S.p.hp;S.t+=2;const r1=x.hitP(100);const blocked=(S.p.hp===hp0&&S.shield===0&&r1===false);   // 변신 중에도 방어막이 막는다
          S.p.inv=0;S.t+=1.3;x.hitP(100);const dmg=hp0-S.p.hp;      // 방어막이 없으면 변신 감면(-30%)만 적용
          const next=__relRun(S,40,1/30);
          return {a,s1,keep,dT,blocked,dmg,next};}""")
        check('① 프싱 Lv3 방어막: 20초 뒤 1겹', r['s1'] == 1 and 19.9 <= r['a'] <= 20.1, r)
        check('① 용 변신을 시작해도 방어막은 그대로(변신이 방어막을 안 먹는다)', r['keep'] == 1 and r['dT'] > 0, r)
        check('① 변신 중 첫 타격은 방어막이 막는다', r['blocked'], r)
        check('① 방어막 없을 때 변신 중 피해는 정확히 70%(100→70)', abs(r['dmg'] - 70) < 1e-6, r['dmg'])
        check('① 막은 뒤 다음 방어막은 20초 뒤(변신 중에도 시간은 같이 흐른다)', r['next'] is not None and 19.9 <= r['next'] <= 20.3, r['next'])

        # ② 부활 × 방어막 × 막기 쿨
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh('brj',3);S.ps.rev=1;S.revUsed=0;S.t=100;
          S.p.hp=1;const r0=x.hitP(50);const rev={ret:r0,hp:S.p.hp,mhp:S.p.mhp,inv:S.p.inv,used:S.revUsed};     // 방어막 없이 죽을 타격 → 부활
          S.shield=1;const hp1=S.p.hp;x.hitP(500);const dur={sh:S.shield,same:S.p.hp===hp1};                  // 부활 무적 2.5초 동안은 방어막이 소모되지 않는다
          S.p.inv=0;S.lastBlock=S.t-.5;x.hitP(30);const cool={sh:S.shield,lost:S.p.hp<hp1};                    // 0.5초 전에 막았으면 방어막이 있어도 못 막는다
          S.p.inv=0;S.t+=2;S.lastBlock=S.t-1.3;const hp2=S.p.hp;S.shield=1;x.hitP(30);const after={sh:S.shield,same:S.p.hp===hp2};   // 1.2초 지나면 막는다
          S.p.inv=0;S.p.hp=1;S.lastBlock=-9;S.shield=0;const st=x.state;x.hitP(50);                          // 두 번째 죽음은 부활 없음
          return {rev,dur,cool,after,second:{used:S.revUsed,st:x.state,hp:S.p.hp}};}""")
        check('② 부활: HP 50% · 확정 1회 · 무적 2.5초', r['rev']['ret'] is False and r['rev']['hp'] == r['rev']['mhp'] * .5 and abs(r['rev']['inv'] - 2.5) < 1e-9 and r['rev']['used'] == 1, r['rev'])
        check('② 부활 무적 중에는 방어막이 소모되지 않는다', r['dur']['sh'] == 1 and r['dur']['same'], r['dur'])
        check('② 막기 쿨(1.2초) 안에는 방어막이 있어도 못 막는다', r['cool']['sh'] == 1 and r['cool']['lost'], r['cool'])
        check('② 쿨이 지나면 방어막이 막는다', r['after']['sh'] == 0 and r['after']['same'], r['after'])
        check('② 두 번째 죽음은 끝(부활 1회뿐)', r['second']['used'] == 1 and (r['second']['hp'] <= 0 or r['second']['st'] != 'play'), r['second'])

        # ③ Lv10/20 지급 × 카드 열기 순서 × 부활 후보
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh('brj');const rr=S.rr,ban=S.ban;S.lv=8;S.xp=0;S.need=1;S.pendingLv=0;x.gainXp(1e9);
          return {lv:S.lv,rr:S.rr-rr,ban:S.ban-ban,pend:S.pendingLv,state:x.state};}""")
        check('③ 한꺼번에 Lv8→%d: 10·20 을 건너뛰지 않고 각각 한 번 (다시뽑기 +2 · 봉인 +2)' % r['lv'], r['lv'] > 20 and r['rr'] == 2 and r['ban'] == 2 and r['pend'] == r['lv'] - 8, r)
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh('brj');const rr=S.rr;S.lv=9;S.xp=0;S.need=1;S.pendingLv=0;x.gainXp(1);   // 딱 Lv10
          const a=S.rr-rr;S.xp=0;S.need=1;x.gainXp(1);const b=S.rr-rr;return {lv:S.lv,a,b};}""")
        check('③ Lv10 에서 +1 (Lv11 에서 또 주지 않는다)', r['a'] == 1 and r['b'] == 1, r)
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh('brj');let n19=0,n20=0,full=0;
          S.lv=19;for(let i=0;i<400;i++)for(const o of x.offers(3))if(o.k==='rev')n19++;
          S.lv=20;for(let i=0;i<400;i++)for(const o of x.offers(3))if(o.k==='rev')n20++;
          // 패시브 칸 6개를 다른 것으로 가득 채워도 부활은 후보
          S.ps={};for(const k of ['spd','hp','cd','mag','arm','amt'])S.ps[k]=1;   // 부활 아닌 패시브 6종 = 칸 6/6
          for(let i=0;i<600;i++)for(const o of x.offers(3))if(o.k==='rev')full++;
          return {n19,n20,full,keys:Object.keys(S.ps).length};}""")
        check('③ Lv19 에는 부활 카드가 한 번도 안 나온다', r['n19'] == 0, r)
        check('③ Lv20 에는 나온다', r['n20'] > 0, r)
        check('③ 패시브 칸이 꽉 차도(%d칸) Lv20 부활 후보는 남는다' % r['keys'], r['full'] > 0, r)

        # ④ 시너지 범위 · 프싱 충전 배율은 서로 다른 값 — 겹쳐도 각자 값
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh('psg');const f0=x.SHV.accMax;
          S.t=0;const m0=(()=>{const r=S.rg;S.rg=0;S.rgB=2.5;x.rgAdd(1);const g=S.rg;S.rg=r;return g;})();
          S.t=600;const m10=(()=>{S.rg=0;S.rgB=2.5;x.rgAdd(1);return S.rg;})();
          S.t=3000;const m50=(()=>{S.rg=0;S.rgB=2.5;x.rgAdd(1);return S.rg;})();
          return {m0,m10,m50,f0};}""")
        check('④ 프싱 충전 배율: 0분 x1.0 · 10분 x1.3 · 50분 x1.8(상한)', abs(r['m0'] - 1) < 1e-9 and abs(r['m10'] - 1.3) < 1e-9 and abs(r['m50'] - 1.8) < 1e-9, r)

        # ⑤ 매 프레임(1/60초) 때리는 연타 600초 — 프싱 · 방어막 Lv1~3 · 부활 보유 · 용 변신 유무
        for lv, N in ((1, 40), (2, 30), (3, 20)):
            for drag in (False, True):
                r = await pg.evaluate("""([lv,drag])=>{const x=__p6x,S=__fresh('psg',lv);S.rel.sprint=3;S.ps.rev=1;S.revUsed=0;const dt=1/60;
                  let last=null,minGap=1e9,n=0,maxInv=0;if(drag)x.shvStart();
                  for(let i=0;i<600*60;i++){S.t+=dt;S.p.inv=Math.max(0,S.p.inv-dt);x.relTick(dt);if(drag&&S.dT<5)S.dT=9;
                    const lb=S.lastBlock;x.hitP(10);maxInv=Math.max(maxInv,S.p.inv);
                    if(S.lastBlock!==lb){n++;if(last!==null)minGap=Math.min(minGap,S.t-last);last=S.t;}}
                  return {n,minGap,maxInv,used:S.revUsed};}""", [lv, drag])
                check(f'⑤ 연타 600초 Lv{lv}{" +용 변신" if drag else ""}: 막기 간격 ≥ {N}초 · 무적 ≤ 0.8 · 부활 안 씀', r['n'] >= 600 // (N + 1) - 1 and r['minGap'] >= N - 1e-6 and r['maxInv'] <= 0.8 + 1e-9 and r['used'] == 0, r)

        check('콘솔/페이지 오류 없음', not errs, errs[:3])
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except OSError: pass
    print('\n실패 %d건' % len(FAILS), FAILS if FAILS else '')
    return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
