# -*- coding: utf-8 -*-
"""🛼 롤러 자국(roll) 검증 (2026-10-22 신규 무기 — 기획안 SV-weapons-passives-2026-10-22.md W-1).
사용: python3 tests/survivors_roll_test.py      (종료코드 0 = 전부 통과)
구성: A 데이터·완전성(표 6곳) · B 서 있으면 자국이 안 남고 달리면 거리에 비례해 남는다 · C 밟은 적 피해(roll 몫) · 각성 감속 · D 수명·풀 상한·모든 캐릭터 · E 이어하기
원본 survivors.html 은 건드리지 않고 임시 사본에만 검증용 훅(__p6y)을 꽂는다."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SV_CSX_OFF', '1')
import sv_harness as H
H.HOOK += "\nwindow.__p6y={W4,trls,PFX,PFXSN,LINEAGE,RES,PASS,TK};\n"
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if not cond and extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

# 한 판 준비: 무기 roll 하나만 · 적 없음 · 자연 스폰 없음. a: ch L ev tier ps
PRE = r"""const x=__p6x,y=__p6y;let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 x.CH_set(a.ch||'brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w=Object.assign({roll:a.L},a.w||{});S.cd={};S.ev=a.ev?{roll:1}:{};S.tier=a.tier?{roll:a.tier}:{};S.ps=a.ps||{};S.pt={};S.tr={};S.rel={};S.sm={};x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();
 const dots=()=>y.trls.a.filter(d=>d.on).length;
 const step=(k)=>{if(x.state==='lvup'){x.pick(x.CUR[0]);return;}if(x.state!=='play'){x.resume();return;}S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys=k||{};x.update(dt);};
"""
def J(body): return "(a)=>{" + PRE + body + "}"

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720)
        ev = lambda body, **a: pg.evaluate(J(body), dict(seed=7, **a))

        # ── A. 데이터 · 완전성
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y,w=x.WEAP.roll;return {w:w&&{ds:w.ds.length,pair:w.pair,pairOk:!!y.PASS[w.pair],evnm:w.ev&&w.ev.nm,nw:w.nw,only:w.only||null},
          tier:x.TIERS.roll&&x.TIERS.roll.length,pfx:y.PFX.roll,sn:y.PFXSN.roll,lin:y.LINEAGE.roll,w4:y.W4.roll,pool:y.trls.a.length,
          cards:(()=>{x.CH_set('brj');x.start();const S=x.S;S.lv=3;const o=x.offers?x.offers():null;return !!o||true})()}}""")
        check('WEAP.roll: 설명 8줄 · 각성 짝 = 이동속도(spd) · 공용(only 없음) · 각성 이름', r['w'] and r['w']['ds'] == 8 and r['w']['pair'] == 'spd' and r['w']['pairOk'] and r['w']['evnm'] and r['w']['only'] is None, r['w'])
        check('단계표(TIERS.roll) 5칸 · 패시브 표(PFX) · 짧은 이름 · 계열 · 수치 표(W4.roll) · 풀 칸 수', r['tier'] == 5 and r['pfx'] and r['sn'] and r['lin'] and r['w4'] and r['pool'] >= 100, r)

        # ── B. 서 있으면 안 늘고, 달리면 거리에 비례해 남는다
        r = await ev("for(let i=0;i<150;i++)step({});const still=dots();"
                     "for(let i=0;i<90;i++)step({KeyD:true});const d1=dots(),dist=p.x;"
                     "return {still,d1,dist,step:y.W4.roll.step}", L=1)
        check('5초 가만히 서 있으면 자국이 하나도 안 남는다(서 있는 보상 없음)', r['still'] == 0, r)
        check('3초 달리면 달린 거리 ÷ 간격 만큼 남는다(±2)', abs(r['d1'] - r['dist'] / r['step']) <= 2.5 and r['d1'] >= 5, r)
        a0 = (await ev("for(let i=0;i<90;i++)step({KeyD:true});return {n:dots(),x:p.x}", L=8))
        a5 = (await ev("for(let i=0;i<90;i++)step({KeyD:true});return {n:dots(),x:p.x}", L=8, ps={'spd': 5}))
        check('이동속도 패시브로 더 멀리 달리면 자국도 그만큼 더 남는다(거리에 비례)', a5['x'] > a0['x'] * 1.1 and a5['n'] > a0['n'], (a0, a5))

        # ── C. 밟은 적은 roll 몫으로 피해를 받는다 · 각성은 느려진다
        for L, evf in ((1, 0), (8, 0), (8, 1)):
            r = await ev("for(let i=0;i<60;i++)step({KeyD:true});const d=y.trls.a.find(q=>q.on);const e=x.spawnEnemy(0,2.5,null,{x:d.x,y:d.y});e.sp=0;e.hp=e.mhp=1e9;e.kb=0;S.dmgBy={};"
                         "let sl=0;for(let i=0;i<60;i++){e.x=d.x;e.y=d.y;S.p.hp=S.p.mhp;S.p.inv=1e9;x.keys={};x.update(dt);if(!d.on)break;sl=Math.max(sl,e.slow||0);}"
                         "return {dm:S.dmgBy.roll||0,sl,on:d.on}", L=L, ev=evf)
            check('Lv%d%s: 자국 위에 선 적이 roll 몫으로 피해(>0)%s' % (L, ' 각성' if evf else '', ' · 감속' if evf else ''), r['dm'] > 0 and (not evf or r['sl'] > 0), r)
        # ── D. 수명 · 풀 상한 · 모든 캐릭터(조건부 경로: 각성·단계 5·패시브) 예외 없음
        r = await ev("for(let i=0;i<150;i++)step({KeyD:true});const mx=dots();for(let i=0;i<500;i++)step({});return {mx,after:dots()}", L=8, ev=1, tier=5, ps={'dur': 5, 'area': 5, 'spd': 5})
        check('멈춘 뒤 자국은 수명이 다하면 모두 사라진다 · 풀 상한(110) 이하', r['after'] == 0 and 0 < r['mx'] <= 110, r)
        chars = await pg.evaluate("()=>__p6x.CHARS.map(c=>c.k)")
        bad = []
        for ch in chars:
            r = await ev("let err=0;for(let i=0;i<900;i++){try{step({[['KeyD','KeyS','KeyA','KeyW'][Math.floor(S.t/2.5)%4]]:true});}catch(e){err++;if(err<2)return {err:String(e)}}}return {err,mx:dots()}", ch=ch, L=8, ev=1, tier=5, ps={'dur': 3, 'area': 3, 'cd': 3})
            if r.get('err'): bad.append((ch, r))
        check('모든 캐릭터(%d명) × Lv8 각성 단계 5 · 30초 · 예외 없음' % len(chars), not bad, bad[:2])
        # ── E. 이어하기
        r = await ev("for(let i=0;i<120;i++)step({KeyD:true});const n0=dots(),rx=S.x2.rx;let bt;try{bt=y.RES.build();}catch(e){return {err:'build '+e}}"
                     "if(!bt||!bt.text)return {err:'no text'};x.state='title';let ok;try{ok=y.RES.restore(bt.text);}catch(e){return {err:'restore '+e}}"
                     "const n1=y.trls.a.filter(d=>d.on).length;let er=0;for(let i=0;i<120;i++){try{x.S.p.hp=x.S.p.mhp;x.keys={KeyD:true};x.update(dt);}catch(e){er++;}}return {ok:!!ok,n0,n1,er}", L=8)
        check('이어하기: 저장→복구 뒤 자국이 그대로 · 복구한 판이 계속 돈다', r.get('ok') and r['n0'] == r['n1'] and r['n0'] > 0 and r['er'] == 0, r)
        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        await b.close()
    srv.close()
    print('\n통과 %d / %d' % (N[0] - len(FAILS), N[0]))
    if FAILS:
        print('실패:'); [print(' -', f) for f in FAILS]
        sys.exit(1)
asyncio.run(main())
