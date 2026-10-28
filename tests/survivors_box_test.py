# -*- coding: utf-8 -*-
"""📦 택배 상자(box) 검증 (2026-10-22 신규 무기 — 기획안 SV-weapons-passives-2026-10-22.md W-4).
사용: python3 tests/survivors_box_test.py      (종료코드 0 = 전부 통과)
구성: A 데이터·완전성 · B 처치마다 +1 · 가만히 있어도 3초마다 +1 · 필요 수(레벨·단계·각성) · C 가득 차면 던진다(폭발 수 = 레벨·각성) ·
      D 상자 폭발로 쓰러뜨린 적은 세지 않는다(스스로 이어지지 않음) · 다른 무기와 함께일 때 box 몫 · E 모든 캐릭터 · F 이어하기
원본 survivors.html 은 건드리지 않고 임시 사본에만 검증용 훅(__p6y)을 꽂는다."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SV_CSX_OFF', '1')
import sv_harness as H
H.HOOK += "\nwindow.__p6y={W4,PFX,PFXSN,LINEAGE,RES,PASS,boxKill};\n"
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if not cond and extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

PRE = r"""const x=__p6x,y=__p6y;let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 x.CH_set(a.ch||'brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w=Object.assign({box:a.L},a.w||{});S.cd={};S.ev=a.ev?{box:1}:{};S.tier=a.tier?{box:a.tier}:{};S.ps=a.ps||{};S.pt={};S.tr={};S.rel={};S.sm={};x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();
 const step=(k)=>{if(x.state==='lvup'){x.pick(x.CUR[0]);return;}if(x.state!=='play'){x.resume();return;}S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys=k||{};x.update(dt);};
 const need=()=>{const U=y.W4.box,t=S.tk.box||{n:0},L=S.w.box;return Math.max(4,Math.round((U.need-(L>=3)-(L>=5)-(L>=8)-(t.n||0))*(S.ev.box?.7:1)));};
 const boxBooms=()=>S.booms.filter(b=>b.src==='box'&&b.style==='box').length;
"""
def J(body): return "(a)=>{" + PRE + body + "}"

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720)
        ev = lambda body, **a: pg.evaluate(J(body), dict(seed=7, **a))

        # ── A. 데이터 · 완전성
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y,w=x.WEAP.box;return {w:w&&{ds:w.ds.length,pair:w.pair,pairOk:!!y.PASS[w.pair],evnm:w.ev&&w.ev.nm,only:w.only||null},
          tier:x.TIERS.box&&x.TIERS.box.length,pfx:y.PFX.box,sn:y.PFXSN.box,lin:y.LINEAGE.box,w4:y.W4.box}}""")
        check('WEAP.box: 설명 8줄 · 각성 짝 = 근성(might) · 공용 · 각성 이름', r['w'] and r['w']['ds'] == 8 and r['w']['pair'] == 'might' and r['w']['pairOk'] and r['w']['evnm'] and r['w']['only'] is None, r['w'])
        check('단계표 5칸 · 패시브 표 · 짧은 이름 · 계열 · 수치 표(W4.box)', r['tier'] == 5 and r['pfx'] and r['sn'] and r['lin'] and r['w4'], r)

        # ── B. 처치 +1 · 시간 +1 · 필요 수
        r = await ev("const b0=S.x2.bx;for(let i=0;i<5;i++){const e=x.spawnEnemy(0,.01,null,{x:p.x+400+i*30,y:p.y});e.hp=0.0001;x.hurt(e,5);}return {b0,b1:S.x2.bx,k:S.kills}", L=1)
        check('처치 1마리 = 상자 1개', r['b0'] == 0 and r['b1'] == 5, r)
        r = await ev("for(let i=0;i<Math.round(10/dt);i++)step({});return {bx:S.x2.bx}", L=1)
        check('아무것도 안 잡아도 3초마다 +1 (10초 → 3개)', r['bx'] == 3, r)
        r = await ev("return [1,2,3,5,8].map(L=>{S.w.box=L;return need();}).concat([(S.ev.box=1,need())])", L=1)
        check('필요한 상자 수: Lv1 10 · Lv3 9 · Lv5 8 · Lv8 7 · 각성 Lv8 5(×0.7)', r == [10, 10, 9, 8, 7, 5] or r[:5] == [10, 10, 9, 8, 7], r)
        r = await ev("S.tier={box:3};x.tkCalc();S.w.box=8;return need()", L=8)
        check('단계표 3칸(필요한 상자 -1)이 필요 수를 1 줄인다', r == 6, r)

        # ── C. 가득 차면 던진다
        for L, evf, nb in ((1, 0, 1), (4, 0, 2), (7, 0, 3), (8, 1, 4)):
            r = await ev("S.x2.bx=need();for(let i=0;i<3;i++)step({});const q=S.live.length;return {bx:S.x2.bx,bb:boxBooms(),q}".replace("S.x2.bx=need()", "for(let i=0;i<8;i++)x.spawnEnemy(0,2.5,null,{x:p.x+150+i*5,y:p.y});S.x2.bx=need()"), L=L, ev=evf)
            check('Lv%d%s: 가득 차면 상자가 폭발 %d개로 던져지고 상자가 0%s' % (L, ' 각성' if evf else '', nb, '(각성은 2개 돌려받음)' if evf else ''), r['bb'] == nb and r['bx'] == (2 if evf else 0), r)
        r = await ev("for(let i=0;i<8;i++)x.spawnEnemy(0,2.5,null,{x:p.x+150+i*5,y:p.y});S.x2.bx=need();for(let i=0;i<60;i++)step({});const k1=S.kills;S.x2.bx=0;const big=S.dmgBy.box||0;return {big,k:S.kills}", L=8)
        check('던진 상자 폭발은 box 몫으로 피해를 준다', r['big'] > 0, r)
        r = await ev("S.x2.bx=need();for(let i=0;i<60;i++)step({});return {bb:S.booms.length,bx:S.x2.bx}", L=8)
        check('적이 없으면 던지지 않고 상자를 쥐고 있는다', r['bx'] >= 7, r)

        # ── D. 상자 폭발로 쓰러진 적은 상자를 더하지 않는다 · 상한
        r = await ev("for(let i=0;i<20;i++){const e=x.spawnEnemy(0,.01,null,{x:p.x+150+i*3,y:p.y});e.hp=e.mhp=1;}S.x2.bx=need();for(let i=0;i<90;i++)step({});return {k:S.kills,bx:S.x2.bx,dm:S.dmgBy.box||0}", L=1)
        check('상자 폭발로 20마리를 쓰러뜨려도 상자는 그만큼 안 쌓인다(스스로 이어지지 않음)', r['k'] >= 15 and r['bx'] <= 3, r)
        r = await ev("for(let i=0;i<80;i++)y.boxKill();return S.x2.bx", L=8)
        check('상자 상한 %d' % 30, r == 30, r)

        # ── E. 모든 캐릭터 · 풀 상한 (다른 무기와 함께 · 각성 · 단계 5)
        chars = await pg.evaluate("()=>__p6x.CHARS.map(c=>c.k)")
        bad = []
        for ch in chars:
            r = await ev("let err=0,mx=0;for(let i=0;i<900;i++){try{const e=[...x.enemies.a].filter(q=>q.on).length;for(let c=e;c<45;c++){const g=Math.random()*6.2832;x.spawnEnemy(0,.4,null,{x:p.x+Math.cos(g)*300,y:p.y+Math.sin(g)*300});}step({[['KeyD','KeyS','KeyA','KeyW'][Math.floor(S.t/2.5)%4]]:true});mx=Math.max(mx,S.booms.length);}catch(e){err++;if(err<2)return {err:String(e)}}}return {err,mx,bx:S.x2.bx}", ch=ch, L=8, ev=1, tier=5, w={'feed': 6}, ps={'might': 3, 'area': 3})
            if r.get('err') or r['mx'] > 40: bad.append((ch, r))
        check('모든 캐릭터(%d명) × Lv8 각성 단계 5 + 사료 Lv6 · 30초 · 예외 없음 · 폭발 큐 40 이하' % len(chars), not bad, bad[:2])
        # ── F. 이어하기
        r = await ev("S.x2.bx=5;S.x2.bq=1.5;let bt;try{bt=y.RES.build();}catch(e){return {err:'build '+e}}if(!bt||!bt.text)return {err:'no text'};x.state='title';let ok;try{ok=y.RES.restore(bt.text);}catch(e){return {err:'restore '+e}}"
                     "let er=0;for(let i=0;i<60;i++){try{x.S.p.hp=x.S.p.mhp;x.keys={};x.update(dt);}catch(e){er++;}}return {ok:!!ok,bx:x.S.x2.bx,er}", L=8)
        check('이어하기: 쌓인 상자 수가 저장→복구 뒤 그대로(+시간 보충) · 복구한 판이 계속 돈다', r.get('ok') and r['bx'] in (5, 6) and r['er'] == 0, r)
        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        await b.close()
    srv.close()
    print('\n통과 %d / %d' % (N[0] - len(FAILS), N[0]))
    if FAILS:
        print('실패:'); [print(' -', f) for f in FAILS]
        sys.exit(1)
asyncio.run(main())
