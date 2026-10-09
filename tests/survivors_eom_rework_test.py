# -*- coding: utf-8 -*-
"""📢 엄장신 개편 시험 — 2026-10-09 사장님 지시 "각성하면 범위·공포 때문에 일반몹이 접근도 못 하는 사기 유틸인데 데미지는 끝내주게 약하다 →
데미지 상향 · 공포 대신 짧은 넉백 · 범위 적당히 하향 · 각성 엄엄엄! → 개엄!".   사용: python3 tests/survivors_eom_rework_test.py   (종료코드 0 = 전부 통과)
  A 소스·문구   공포 흔적 없음 · 각성 글자 「개엄!」 · 카드 문구의 숫자 = U3.eom 값
  B 값          레벨 1~8 피해·범위·쿨타임이 식과 같다 · 범위 경계(밖은 안 맞고 안은 맞는다)
  C 밀치기      보통·엘리트·대형 거리(kd × KB) · 마스터·각성 배율 · 프레임 길이와 무관 · 보스는 안 밀리고 느려지기만
  D 각성        한 방에 큰 「개엄!」(단계 2) · 피해 ×2 · 메아리는 그대로 + 0.4초 뒤 60%
  E 균형 안전선 아레나(잡몹 45마리·10초): Lv1 에서 처치가 나오고(초반이 비지 않는다) · 각성+마스터에서도 서 있는 표적이 접촉을 피해 가 버리지 않는다(예전: 접촉 0)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 훅을 꽂는다 — 한 워크트리에서 이 시험을 동시에 둘 돌리지 말 것."""
import asyncio, sys, os, re, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:400]) if (extra != '' and not cond) else ''), flush=True)
    if not cond: FAILS.append(name)
SRC = open(os.path.join(H.ROOT, 'survivors.html'), encoding='utf-8').read()

SETUP = r"""(a)=>{const x=__p6x;x.srvUnl&&x.srvUnl(['eom']);x.CH_set('eom');x.start();const S=x.S,p=S.p;S.t=a.t||120;S.w={eom:a.L};S.cd={};S.ev=a.ev?{eom:1}:{};S.tier={eom:a.tier||0};S.ps=a.ps||{};x.tkCalc();x.synCalc();
  S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;p.inv=99;p.hp=p.mhp=1e9;
  for(const e of x.enemies.a)e.on=false;x.props.clear();return {R:x.U3.eom.R}}"""
# 한 마리를 거리 d 에 세워 두고(제자리) 한 번 외치게 해 피해·밀린 거리를 잰다
SHOUT = r"""(a)=>{const x=__p6x,S=x.S,p=S.p;const out=[];
  for(const d of a.ds){for(const e of x.enemies.a)e.on=false;
    const e=x.spawnEnemy(a.kind||0,1,null,{x:p.x+d,y:p.y});if(!e){out.push(null);continue;}
    e.hp=e.mhp=1e12;e.sp=0;e.kb=0;e.kr=0;e.x=p.x+d;e.y=p.y;if(a.el)e.el=1;if(a.bg)e.bg=1;
    S.dmgBy={};S.cd.eom=0;const x0=e.x,y0=e.y,h0=e.hp;
    for(let i=0;i<Math.round((a.sec||.8)/a.dt);i++){p.inv=99;x.update(a.dt);}
    out.push({d,dmg:h0-e.hp,mv:Math.hypot(e.x-x0,e.y-y0),r:e.r});}
  return out}"""

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port)
        U = await pg.evaluate("()=>JSON.parse(JSON.stringify(__p6x.U3.eom))")
        # ── A. 소스·문구
        print('── A. 소스·문구')
        check('A1 소스에 공포(fear) 흔적 없음 — e.fear·SPX.fear·「공포」「겁먹」 글자', not re.search(r'\.fear\b|o\.fear|fear0|공포|겁먹', re.sub(r'//[^\n]*', '', SRC)), re.findall(r'[^\n]{0,40}(?:\.fear\b|fear0|공포|겁먹)[^\n]{0,20}', SRC)[:2])
        r = await pg.evaluate("()=>{const x=__p6x,W=x.WEAP.eom,C=x.CHARS.find(c=>c.k==='eom'),T=x.TIERS.eom;return {ds:W.ds,ev:W.ev,rl:W.rl,cds:C.ds,tiers:T.map(t=>[t[0],t[1]])}}")
        check('A2 각성 이름 「개엄!」 · 옛 이름 「엄엄엄」 없음', r['ev']['nm'] == '개엄!' and '엄엄엄' not in json.dumps(r, ensure_ascii=False) and "'개엄!'" in SRC, r['ev'])
        check('A3 마지막 외침 글자 LBL[2] = 「개엄!」', re.search(r"const LBL=\['엄!','엄엄!','개엄!'\]", SRC) is not None)
        want_pct = lambda v: '+%d%%' % round((v - 1) * 100)
        check('A4 카드 문구의 범위·피해·쿨타임 숫자 = U3 값 (범위 %s · 피해 %s/%s/%s · 쿨타임 -10%%)' % (want_pct(U['Rg']), want_pct(U['dg'][0]), want_pct(U['dg'][1]), want_pct(U['dg'][2])),
              r['ds'][1] == '범위 %s' % want_pct(U['Rg']) and r['ds'][2] == '피해 %s · 쿨타임 -10%%' % want_pct(U['dg'][0]) and r['ds'][4] == '피해 %s · 쿨타임 -10%%' % want_pct(U['dg'][1])
              and r['ds'][7] == '범위 %s · 피해 %s' % (want_pct(U['Rg']), want_pct(U['dg'][2])) and r['ds'][6] == '쿨타임 -10%', r['ds'])
        check('A5 Lv1 문구의 주기 = cd(%s초) · 밀려난다는 설명 · 보스 설명' % U['cd'], ('%g초마다' % U['cd']) in r['ds'][0] and '밀려난다' in r['ds'][0] and '보스는 안 밀리고' in r['ds'][0], r['ds'][0])
        check('A6 각성 문구의 배율 = U3 (범위 %g배 · 밀치는 힘 %g배 · 피해 %g배)' % (U['evR'], U['evK'], U['evD']), ('범위 %g배' % U['evR']) in r['ev']['ds'] and ('밀치는 힘 %g배' % U['evK']) in r['ev']['ds'] and ('피해 %g배' % U['evD']) in r['ev']['ds'], r['ev']['ds'])
        t3, t5 = r['tiers'][2], r['tiers'][4]
        check('A7 마스터 단계: 3번째 「피해 +12%」(d .12) · 5번째 「밀치는 힘 +25% · 범위 +7%」(life .5 · a .07)', t3[0] == '피해 +12%' and t3[1] == {'d': .12} and t5[0] == '밀치는 힘 +25% · 범위 +7%' and t5[1] == {'life': .5, 'a': .07}, r['tiers'])
        check('A8 캐릭터 카드 문구가 밀치기를 말한다 · 겁먹음 없음', '밀려난다' in r['cds'] and '겁먹' not in r['cds'] and '특별한 능력 없이' in r['cds'], r['cds'])
        # ── B. 값
        print('── B. 레벨별 값')
        dt = 1 / 60
        for L in range(1, 9):
            await pg.evaluate(SETUP, {'L': L})
            exp_d = U['d'] * math.prod(m for lv, m in ((3, U['dg'][0]), (5, U['dg'][1]), (8, U['dg'][2])) if L >= lv)
            exp_R = U['R'] * (U['Rg'] ** sum(1 for lv in (2, 4, 6, 8) if L >= lv))
            o = await pg.evaluate(SHOUT, {'ds': [exp_R - 8, exp_R + 40], 'dt': dt, 'kind': 0})
            ok_in = o[0] is not None and o[0]['dmg'] > 0 and abs(o[0]['dmg'] - exp_d) <= exp_d * .02
            ok_out = o[1] is not None and o[1]['dmg'] == 0 and o[1]['mv'] < .5
            check('B%d Lv%d 피해 %.1f(식) · 반지름 %.0f 안은 맞고 밖(+40)은 안 맞는다 — 잰 피해 %s' % (L, L, exp_d, exp_R, round(o[0]['dmg'], 1) if o[0] else None), ok_in and ok_out, o)
        for L, want in ((1, U['cd']), (3, U['cd'] * .9), (5, U['cd'] * .81), (7, U['cd'] * .729)):
            await pg.evaluate(SETUP, {'L': L})
            cdv = await pg.evaluate("()=>{const x=__p6x,S=x.S,p=S.p;const e=x.spawnEnemy(0,1,null,{x:p.x+40,y:p.y});e.hp=e.mhp=1e12;e.sp=0;S.cd.eom=0;p.inv=99;x.update(1/60);return S.cd.eom}")
            check('B 쿨타임 Lv%d = %.3f초(식)' % (L, want), abs(cdv - want) < .05, cdv)
        # ── C. 밀치기
        print('── C. 밀치기')
        kd = U['kd']
        await pg.evaluate(SETUP, {'L': 4})
        o = await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0}); mv0 = o[0]['mv']
        check('C1 보통 적: 밀린 거리 ≈ kd(%g) ±8%% — 잰 %.1f' % (kd, mv0), abs(mv0 - kd) <= kd * .08, o)
        o = await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0, 'el': 1}); mvE = o[0]['mv']
        o = await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0, 'bg': 1}); mvB = o[0]['mv']
        check('C2 엘리트 ×0.6 · 대형 ×0.25 만큼만 밀린다 — %.1f · %.1f' % (mvE, mvB), abs(mvE - kd * .6) <= kd * .06 and abs(mvB - kd * .25) <= kd * .05, (mvE, mvB))
        await pg.evaluate(SETUP, {'L': 8, 'tier': 5})
        o = await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0, 'sec': .35}); mv5 = o[0]['mv']   # 마스터 4단계의 메아리(0.4초 뒤 60%)가 닿기 전 — 첫 외침이 민 거리만
        check('C3 마스터 5단계(밀치는 힘 +25%%): 첫 외침 %.1f ≈ kd×1.25 = %.1f' % (mv5, kd * 1.25), abs(mv5 - kd * 1.25) <= kd * 1.25 * .08, o)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1})
        o = await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0}); mvV = o[0]['mv']
        check('C4 각성(밀치는 힘 ×%g): %.1f ≈ kd×%g = %.1f' % (U['evK'], mvV, U['evK'], kd * U['evK']), abs(mvV - kd * U['evK']) <= kd * U['evK'] * .08, o)
        mvs = {}
        for f in (30, 60, 120):
            await pg.evaluate(SETUP, {'L': 4})
            o = await pg.evaluate(SHOUT, {'ds': [60], 'dt': 1 / f, 'kind': 0}); mvs[f] = round(o[0]['mv'], 1)
        check('C5 프레임 길이(30·60·120fps)와 상관없이 같은 거리 — %s' % mvs, max(mvs.values()) - min(mvs.values()) <= kd * .08, mvs)
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p,E3=x.U3.eom;for(const e of x.enemies.a)e.on=false;
          const mk=(mini)=>{const b=x.spawnBoss('sr');b.x=p.x+60;b.y=p.y;b.hp=b.mhp=1e12;b.sp=0;if(mini){b.b=Object.assign({},b.b,{mini:1});}return b;};
          const b1=mk(false);S.cd.eom=0;x.update(1/60);const s1=b1.slow,m1=Math.hypot(b1.x-(p.x+60),b1.y-p.y);b1.on=false;
          const b2=mk(true);S.cd.eom=0;x.update(1/60);const s2=b2.slow,m2=Math.hypot(b2.x-(p.x+60),b2.y-p.y);
          return {s1,m1,s2,m2,bs:E3.bs}}""")
        check('C6 보스는 안 밀리고(좌표 그대로) bs(%g초)만큼, 미니 보스는 절반만 느려진다 — %s' % (U['bs'], {k: round(v, 3) for k, v in r.items()}), r['m1'] < .5 and r['m2'] < .5 and abs(r['s1'] - U['bs']) < .05 and abs(r['s2'] - U['bs'] * .5) < .05, r)
        # ── D. 각성
        print('── D. 각성')
        await pg.evaluate(SETUP, {'L': 8})
        d0 = (await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0}))[0]['dmg']
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1})
        d1 = (await pg.evaluate(SHOUT, {'ds': [60], 'dt': dt, 'kind': 0}))[0]['dmg']
        check('D1 각성하면 한 번 외침의 피해가 ×%g — %.1f → %.1f' % (U['evD'], d0, d1), abs(d1 / d0 - U['evD']) < .03, (d0, d1))
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p,EX=x.EX;const log=[];const orig=EX.eom;EX.eom=function(px,py,R,st,ev,L){log.push([+S.t.toFixed(2),st,ev]);return orig.apply(this,arguments);};
          for(const e of x.enemies.a)e.on=false;const e=x.spawnEnemy(0,1,null,{x:p.x+50,y:p.y});e.hp=e.mhp=1e12;e.sp=0;S.cd.eom=0;const t0=S.t;
          for(let i=0;i<60;i++){p.inv=99;if(i>1&&S.cd.eom<1)S.cd.eom=1e9;x.update(1/60);}
          EX.eom=orig;return log.map(v=>[+(v[0]-t0).toFixed(2),v[1],v[2]])}""")
        check('D2 각성(메아리 없음): 외침은 한 번 · 단계 2(큰 「개엄!」) — %s' % r, len(r) == 1 and r[0][1] == 2 and r[0][2] == 1, r)
        await pg.evaluate(SETUP, {'L': 8, 'ev': 1, 'tier': 4})
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p,EX=x.EX;const log=[];const orig=EX.eom;EX.eom=function(px,py,R,st,ev,L){log.push([+S.t.toFixed(2),st,ev]);return orig.apply(this,arguments);};
          for(const e of x.enemies.a)e.on=false;const e=x.spawnEnemy(0,1,null,{x:p.x+50,y:p.y});e.hp=e.mhp=1e12;e.sp=0;S.cd.eom=0;const t0=S.t;
          for(let i=0;i<60;i++){p.inv=99;if(i>1&&S.cd.eom<1)S.cd.eom=1e9;x.update(1/60);}
          EX.eom=orig;return log.map(v=>[+(v[0]-t0).toFixed(2),v[1],v[2]])}""")
        check('D3 각성 + 메아리(마스터 4): 「개엄!」 뒤 0.4초에 메아리(단계 1) 한 번 — %s' % r, len(r) == 2 and r[0][1] == 2 and r[1][1] == 1 and abs(r[1][0] - r[0][0] - .4) < .05, r)
        # ── E. 균형 안전선 (아레나)
        print('── E. 아레나 안전선')
        ARENA = r"""(a)=>{const x=__p6x;let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
          x.srvUnl(['eom']);x.CH_set('eom');x.start();const S=x.S,p=S.p,dt=1/30;S.w={eom:a.L};S.cd={};S.ev=a.ev?{eom:1}:{};S.tier=a.tier||{};S.ps={};x.tkCalc();x.synCalc();
          S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;for(const q of x.enemies.a)q.on=false;x.props.clear();
          const N=a.N||45;const fill=()=>{let c=0;for(const q of x.enemies.a)if(q.on)c++;for(;c<N;c++){const g=Math.random()*6.2832,r=a.r0+Math.random()*a.r1;if(!x.spawnEnemy((Math.random()*3)|0,a.hpx||2.5,null,{x:p.x+Math.cos(g)*r,y:p.y+Math.sin(g)*r}))break;}};
          let contact=0,fr=0,lost=0;p.mhp=p.hp=1e9;
          const step=(rec)=>{if(x.state==='lvup'){x.pick(x.CUR[0]);return;}if(x.state!=='play'){x.resume();return;}S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys=a.still?{}:[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][Math.floor(S.t/2.5)%4];
            if(a.chase)for(const q of x.enemies.a)if(q.on){q.hp=q.mhp=1e12;}
            fill();const h0=p.hp;x.update(dt);if(rec){fr++;let c=0;for(const q of x.enemies.a)if(q.on&&Math.hypot(q.x-p.x,q.y-p.y)<q.r+p.r+4)c++;if(c)contact++;lost+=Math.max(0,h0-p.hp);}x.props.clear();};
          for(let i=0;i<Math.round((a.warm||3+8*Math.random())/dt);i++)step(false);S.dmgBy={};const k0=S.kills;for(let i=0;i<Math.round((a.sec||10)/dt);i++)step(true);
          return {k:S.kills-k0,d:Object.values(S.dmgBy).reduce((u,v)=>u+v,0),contact:contact/fr,lost}}"""
        def mean(v): return sum(v) / len(v)
        rs = [await pg.evaluate(ARENA, {'L': 1, 'seed': s, 'r0': 140, 'r1': 280}) for s in range(1, 13)]
        k1 = mean([x['k'] for x in rs])
        check('E1 Lv1 아레나(잡몹 45 · 10초): 처치 평균 %.1f ≥ 4 — 초반이 비지 않는다(예전 0.0)' % k1, k1 >= 4, rs[:2])
        CONTACT = r"""(a)=>{const x=__p6x;let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
          x.srvUnl(['eom']);x.CH_set('eom');x.start();const S=x.S,p=S.p,dt=1/30;S.w=a.L?{eom:a.L}:{};S.cd={};S.ev=a.ev?{eom:1}:{};S.tier=a.tier||{};S.ps={};x.tkCalc();x.synCalc();
          S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;p.mhp=p.hp=1e9;for(const q of x.enemies.a)q.on=false;x.props.clear();
          const E=[];for(let i=0;i<a.N;i++){const g=Math.random()*6.2832,r=300+Math.random()*150;const e=x.spawnEnemy([0,1,3][i%3],2.5,null,{x:p.x+Math.cos(g)*r,y:p.y+Math.sin(g)*r});e.hp=e.mhp=1e12;E.push(e);}
          let contact=0,fr=0,hpPrev=p.hp,lost=0;
          const step=(rec)=>{p.hp=Math.min(p.hp,1e9);S.spawnT=-1e12;S.need=1e12;S.xp=0;x.keys={};for(const e of E)e.hp=e.mhp=1e12;const h0=p.hp;x.update(dt);
            if(rec){fr++;let c=0;for(const e of E)if(Math.hypot(e.x-p.x,e.y-p.y)<e.r+p.r+4)c++;if(c)contact++;lost+=Math.max(0,h0-p.hp);}};
          for(let i=0;i<Math.round(8/dt);i++)step(false);for(let i=0;i<Math.round(40/dt);i++)step(true);
          return {contact:contact/fr,lost}}"""
        rs = [await pg.evaluate(CONTACT, {'L': 8, 'ev': 1, 'tier': {'eom': 5}, 'seed': s, 'N': 8}) for s in range(1, 7)]
        rs0 = [await pg.evaluate(CONTACT, {'L': 0, 'seed': s, 'N': 8}) for s in range(1, 7)]
        c8 = mean([x['contact'] for x in rs]); l8 = mean([x['lost'] for x in rs]); l0 = mean([x['lost'] for x in rs0])
        check('E2 각성+마스터5 · 제자리 · 쫓아오는 죽지 않는 적 8마리 40초: 접촉한 시간 비율 %.2f ≥ 0.25 · 입은 피해 %.0f (무기 없음 %.0f) — 아예 접근 못 하게 막지는 않는다(예전: 접촉 0 · 피해 0)' % (c8, l8, l0), c8 >= .25 and l8 >= l0 * .15, (rs[:2], rs0[:2]))
        check('콘솔·페이지 오류 0', not errs, errs[:3])
        await b.close()
    srv.close()
    print('\n' + ('전부 통과 (%d)' % N[0] if not FAILS else '실패 %d건: %s' % (len(FAILS), FAILS)))
    return 0 if not FAILS else 1
sys.exit(asyncio.run(main()))
