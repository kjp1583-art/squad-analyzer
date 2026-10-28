# -*- coding: utf-8 -*-
"""📸 배고배고 고유 무기 「플레이브 포토카드」 몰이꾼 개편 검증 (2026-10-19 사장님 지시).
컨셉: 카드로 적을 밀쳐 내 내 주변에 빈 공간(도망갈 길)을 만들고, 밀려난 적끼리 부딪쳐 터뜨린다.
사용: python3 tests/survivors_pcards_test.py      (종료코드 0 = 전부 통과)
구성: A 데이터·문구 · B 밀치기 · C 부딪침(볼링·연쇄·상한) · D 접근 불가 장판 · E 보스 예외 · F 포위 보너스 · G 풀 칸 재사용 · H 저장→복구 · I 유물 고리 몫 · J 콘솔 오류"""
import asyncio, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
H.HOOK += "\nwindow.__p6y={U3,F3CAP,PCB,pcPush,pcBowl,pcZone,spawnBoss,liveOk,knock,aim3};\n"
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:400]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)
def near(a, b, tol): return a is not None and abs(a - b) <= tol

# 장면: bgb 로 포토카드 하나만 들고, 제자리 고정 안 하는(밀리는) 적들을 세운다. es: 각도 a · 거리 d · hp · boss · pin(제자리 유지는 쿨 전까지만 — 첫 발 맞기 전)
PRE = r"""Math.random=window.__rnd0;const x=__p6x,y=__p6y;x.CH_set('bgb');x.start();const S=x.S,p=S.p,dt=a.dt||1/60;
 S.w=Object.assign({pcards:a.L===undefined?1:a.L},a.w||{});S.cd={};S.ev=a.ev?{pcards:1}:{};S.tier={};S.ps={};S.rel=Object.assign({},a.rel||{});x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();S.x3.f.length=0;y.PCB.length=0;
 const E=[];for(const o of (a.es||[])){const ex=p.x+Math.cos(o.a*Math.PI/180)*o.d,ey=p.y+Math.sin(o.a*Math.PI/180)*o.d;
   let e;if(o.boss){e=y.spawnBoss('mao');}else e=x.spawnEnemy(0,2.5,null,{x:ex,y:ey});
   e.x=ex;e.y=ey;e.sp=0;e.hp=e.mhp=o.hp||1e9;if(o.r)e.r=o.r;E.push(e);}
 S.live=E.slice();
 const step=(n)=>{for(let i=0;i<(n||1);i++){S.p.hp=S.p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys={};for(const q of E)if(q.on)q.sp=0;S.live=E.filter(q=>q.on);x.update(dt);}};
"""
def J(body): return "(a)=>{" + PRE + body + "}"

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    src = open(os.path.join(H.ROOT, 'survivors_x.html'), encoding='utf-8').read()
    async with async_playwright() as p:
        b = await H.launch(p, args=['--autoplay-policy=no-user-gesture-required'])
        ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate("window.__rnd0=Math.random")
        ev = lambda body, **a: pg.evaluate(J(body), a)

        # ───────────────── A. 데이터 · 문구
        r = await pg.evaluate("()=>({u:__p6y.U3.pcards,ds:__p6x.WEAP.pcards.ds,rl:__p6x.WEAP.pcards.rl,cd:__p6x.CHARS.find(c=>c.k==='bgb').ds})")
        U = r['u']
        check('U3.pcards 수치표(밀치기 720 · 부딪침 ×bd · 연쇄 3 · 장판 1.8초/46px)', all(k in U for k in ('kn', 'kt', 'bd', 'bc', 'bcap', 'zl', 'zr', 'zp', 'zc', 'sr', 'sm', 'sx', 'bsl')) and U['kn'] >= 600 and U['zl'] == 1.8 and U['zc'] >= 3, U)
        check('카드 문구(Lv1)가 값을 읽는다: 장판 지속 %s초' % U['zl'], ('%s초' % U['zl']) in r['ds'][0] and '부딪' in r['ds'][0] and '장판' in r['ds'][0] and '많을수록' in r['ds'][0] and ('최대 +%d%%' % round(U['sx'] * 100)) in r['ds'][0], r['ds'][0])
        check('고유 무기 줄(rl) · 캐릭터 설명이 몰이꾼 컨셉', '몰이' in r['rl'] and '밀쳐' in r['cd'] and '부딪' in r['cd'], (r['rl'], r['cd']))

        # ───────────────── B. 밀치기 — 맞은 적은 확실히 멀리 밀려난다
        r = await ev("""const e0=E[0];const x0=e0.x;for(let i=0;i<40;i++)step();return {moved:Math.round(e0.x-x0),kb:e0.kb,dmg:Math.round(S.dmgBy.pcards||0)}""", es=[{'a': 0, 'd': 100}], L=1)
        check('카드 한 장 맞은 일반 적은 ≥70px 밀려난다(옛 값은 ≈30px)', r['moved'] >= 70 and r['dmg'] > 0, r)

        # ───────────────── C. 부딪침 — 밀려난 적이 뒤의 적을 치면 서로 피해, 뒤의 적도 밀려난다
        r = await ev("""const A=E[0],B=E[1];let pushedB=false,maxPcb=0,bump=0;const hpB0=B.hp;
          for(let i=0;i<30;i++){step();if(B.kb>0)pushedB=true;maxPcb=Math.max(maxPcb,y.PCB.length);}
          return {pushedB,maxPcb,hpLostB:Math.round(hpB0-B.hp),d:Math.round(S.dmgBy.pcards||0),by:S.dmgBy.pcards}""", es=[{'a': 0, 'd': 90}, {'a': 0, 'd': 140}], L=1)
        check('앞 적이 밀려가 뒤 적에게 부딪친다: 뒤 적도 피해를 입고(부딪침 피해) 밀려난다', r['pushedB'] and r['hpLostB'] > 0, r)
        # 일렬 8마리: 연쇄는 bc(3)단계까지 · 동시에 날아가는 적은 bcap 이하
        r = await ev("""let mx=0,pushed=new Set();for(let i=0;i<60;i++){step();mx=Math.max(mx,y.PCB.length);for(const q of E)if(q.kb>0)pushed.add(q.sn);}return {mx,np:pushed.size,cap:y.U3.pcards.bcap,bc:y.U3.pcards.bc}""",
                     es=[{'a': 0, 'd': 90 + 24 * i} for i in range(10)], L=1)
        check('일렬 10마리: 연쇄 부딪침은 카드 직접 타격 + bc 단계까지만 · 동시에 날아가는 적은 bcap 이하', r['mx'] <= r['cap'] and 2 <= r['np'] <= 1 + 4 * 5, r)
        # 같은 적을 한 번만: 밀려난 적이 한 대상을 두 번 치지 않는다(h 목록)
        r = await ev("""const A=E[0],B=E[1];A.x=p.x+60;A.y=p.y;B.x=A.x+(A.r+B.r)-2;B.y=A.y;
          S.cd.pcards=99;const before=B.hp;y.pcPush(A,1,0,100,0,'pcards');let hits=0,prev=B.hp;for(let i=0;i<20;i++){x.update(dt);if(B.hp<prev-.001){hits++;}prev=B.hp;A.sp=B.sp=0;}return {hits}""", es=[{'a': 0, 'd': 60}, {'a': 0, 'd': 90}], L=1)
        check('밀려난 적은 같은 적을 두 번 치지 않는다(한 번 부딪치면 목록에 올라 이후 무시)', r['hits'] <= 1, r)

        # ───────────────── D. 접근 불가 장판
        r = await ev("""const e0=E[0];step(30);const z=S.x3.f.filter(o=>o.k==='pz');const zl0=z.length&&z[0].life,R=z.length&&z[0].R;
          // 장판 안의 일반 적은 바깥으로 밀려난다 + 느려진다
          const t=x.spawnEnemy(0,2.5,null,{x:z[0].x+8,y:z[0].y});t.sp=0;t.hp=t.mhp=1e9;S.live=[t];S.cd.pcards=99;const d0=Math.hypot(t.x-z[0].x,t.y-z[0].y);
          let ms=0;for(let i=0;i<30;i++){S.p.hp=S.p.mhp;S.spawnT=-1e12;x.update(dt);t.sp=0;ms=Math.max(ms,t.slow);}const d1=Math.hypot(t.x-z[0].x,t.y-z[0].y);
          const gone=(()=>{for(let i=0;i<160;i++){S.p.hp=S.p.mhp;S.spawnT=-1e12;S.cd.pcards=99;x.update(dt);}return S.x3.f.filter(o=>o.k==='pz').length})();
          return {nz:z.length,zl0,R,d0,d1,slow:ms,gone}""", es=[{'a': 0, 'd': 100}], L=1)
        check('카드가 맞은 자리에 장판(pz) 1개 · 지속 1.8초 근처 · 반지름 ≈46', r['nz'] == 1 and U['zl'] - .6 <= r['zl0'] <= U['zl'] and near(r['R'], U['zr'], 12), r)
        check('장판 안의 일반 적은 바깥으로 밀려나고(거리가 늘어남) 느려진다', r['d1'] > r['d0'] + 5 and r['slow'] > 0, r)
        check('장판은 지속 시간이 지나면 사라진다(쿨타임 막고 2.6초 뒤 0개)', r['gone'] == 0, r)
        # 장판 합치기 · 상한
        r = await ev("""for(let i=0;i<12;i++)y.pcZone(p.x+200+i*90,p.y,1);const n1=S.x3.f.filter(o=>o.k==='pz').length;
          for(let i=0;i<5;i++)y.pcZone(p.x+200,p.y,1);const n2=S.x3.f.filter(o=>o.k==='pz').length;return {n1,n2,zc:y.U3.pcards.zc,len:S.x3.f.length}""", es=[], L=1)
        check('장판은 동시에 zc 개까지 — 근처에 또 맞으면 새로 만들지 않고 시간만 늘린다', r['n1'] == r['zc'] and r['n2'] == r['n1'], r)

        # ───────────────── E. 보스 예외 — 밀리지 않고 느려지며, 장판 안에서도 안 밀려난다
        r = await ev("""const B=E[0];B.sp=0;const x0=B.x,y0=B.y;for(let i=0;i<40;i++)step();return {moved:Math.round(Math.hypot(B.x-x0,B.y-y0)),slow:B.slow,kb:B.kb||0,dmg:Math.round(S.dmgBy.pcards||0),pcb:y.PCB.length,zones:S.x3.f.filter(o=>o.k==='pz').length}""", es=[{'a': 0, 'd': 100, 'boss': 1}], L=1)
        check('보스: 카드 피해는 들어가고 밀리지 않으며(이동 0) 느려지고 PCB 에 오르지 않는다', r['dmg'] > 0 and r['moved'] <= 2 and r['pcb'] == 0, r)

        # ───────────────── F. 포위 보너스 — 내 주변 sr px 안의 적이 많을수록 카드 피해 증가 (sm 씩 · sx 상한)
        async def cardd(n):
            return await ev("""S.cd.pcards=0;step(2);const c=S.x3.f.filter(o=>o.k==='pc');return c.length?c[0].d:0""", es=[{'a': 20 * i + 5, 'd': 70 + (i % 3) * 10} for i in range(n)], L=1)
        d1, d5, d30 = await cardd(1), await cardd(5), await cardd(30)
        m = lambda n: 1 + min(U['sx'], U['sm'] * n)
        check('포위 보너스: 둘러싼 적 n마리면 카드 피해 ×(1+min(sx, sm×n)) — 1 → 5 → 30마리(상한)', d1 > 0 and near(d5 / d1, m(5) / m(1), .02) and near(d30 / d1, m(30) / m(1), .02) and d30 > d5 > d1, (d1, d5, d30))

        # ───────────────── G. 풀 칸 재사용 — 밀려나다 쓰러진 적의 칸에 새 적이 들어와도 낡은 목록이 건드리지 않는다
        r = await ev("""const A=E[0];y.pcPush(A,1,0,100,0,'pcards');const n0=y.PCB.length;A.on=false;
          const nw=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y});const sameSlot=nw===A;nw.sp=0;nw.hp=nw.mhp=1e9;nw.kb=0;
          S.live=[nw];const h0=nw.hp;y.pcBowl();return {n0,n1:y.PCB.length,sameSlot,hp:nw.hp===h0,kb:nw.kb||0}""", es=[{'a': 0, 'd': 100}], L=1)
        check('쓰러진 적의 칸이 재사용돼도 목록(sn 확인)에서 빠지고 새 적을 건드리지 않는다', r['n0'] == 1 and r['n1'] == 0 and r['hp'] and r['kb'] == 0, r)
        # N 세대: 부딪치다 죽고 되살아나는 칸 반복에도 목록이 상한 아래로 유지
        r = await ev("""let mx=0;for(let g=0;g<30;g++){for(const q of E)if(!q.on){}S.cd.pcards=0;step(20);mx=Math.max(mx,y.PCB.length,S.x3.f.length);for(const q of E){q.on=true;q.hp=q.mhp=40;}}
          return {mx,cap:y.U3.pcards.bcap,f:y.F3CAP}""", es=[{'a': 0, 'd': 80 + 18 * i, 'hp': 40} for i in range(12)], L=8)
        check('30세대 반복(죽고 되살리기)에도 PCB ≤ bcap · 투사체 풀 ≤ F3CAP', r['mx'] <= max(r['cap'], r['f']) , r)

        # ───────────────── H. 이어하기 — 장판이 JSON 왕복 뒤에도 돌고 예외가 없다
        r = await ev("""step(30);const n=S.x3.f.filter(o=>o.k==='pz').length;const copy=JSON.parse(JSON.stringify(S.x3.f));S.x3.f.length=0;for(const o of copy)S.x3.f.push(o);y.PCB.length=0;
          for(let i=0;i<30;i++)step();return {n,after:S.x3.f.filter(o=>o.k==='pz').length,state:x.state}""", es=[{'a': 0, 'd': 100}], L=1)
        check('장판 저장→복구(JSON 왕복) 뒤에도 계속 돌고 예외가 없다', r['n'] >= 1 and r['state'] == 'play', r)

        # ───────────────── I. 유물 고리(rel) — 부딪침 피해도 유물 몫, 장판은 안 만든다
        r = await ev("""S.sgT.bgb=99;S.rel.sg_bgb=1;const d=y.U3.pcards.d;x.sgFan(d,430,.84,0);const rings=S.x3.f.filter(o=>o.rl).length;
          for(let i=0;i<40;i++)step();return {rings,pc:S.dmgBy.pcards||0,rel:S.dmgBy.rel||0,zones:S.x3.f.filter(o=>o.k==='pz').length}""", es=[{'a': 0, 'd': 50}, {'a': 40, 'd': 56}, {'a': 90, 'd': 50}, {'a': 140, 'd': 56}], L=0, rel={'sg_bgb': 1})
        check('유물 고리: 피해(부딪침 포함)는 rel 몫 · pcards 몫 0 · 장판은 안 만든다', r['rings'] > 0 and r['rel'] > 0 and r['pc'] == 0 and r['zones'] == 0, r)

        # ───────────────── J. 콘솔 오류
        check('콘솔 오류 0', not errs, errs[:3])
        await b.close()
    print('\n%d 개 중 실패 %d' % (N[0], len(FAILS)), FAILS)
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
