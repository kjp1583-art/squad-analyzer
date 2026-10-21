# -*- coding: utf-8 -*-
"""🏆 흐접새우 서바이벌 「도전 과제」 시험 — 조건별 판정(합성 상태) · 중복 방지 · localStorage 차단/깨짐 · 겹창 · 결과 화면 목록 · 일일 도전/연습 정책 · 폰 레이아웃.
사용: python3.13 tests/survivors_ach_test.py     (임시 사본 survivors_x.html 은 시험이 끝나면 지운다)"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright

EXTRA = "window.__ax={ACH,ACHV,ACHCK,achTick,achEval,achEnd,achHit,achBoss,achLoad,ACHK,cdxStat,endRun,CDX};"
FAILS = []; N = [0]
def check(name, ok, info=''):
    N[0] += 1
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ← ' + str(info)[:500]), flush=True)
    if not ok: FAILS.append(name)

START = "async()=>{const x=__p6x;x.CH_set('brj');x.start();return x.state;}"

async def mk(b, port, init=None, w=390, h=844, mobile=True):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/survivors_x.html' % port)
    await pg.wait_for_function('window.__p6x!==undefined&&window.__ax!==undefined&&window.__ach!==undefined', timeout=20000)
    return ctx, pg, errs

async def main():
    H.make_copy(extra=EXTRA); srv = H.Srv()
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            await run(b, srv.port)
            await b.close()
    finally:
        srv.close()
        try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
        except OSError: pass
    print('\n%d 항목 · 실패 %d' % (N[0], len(FAILS)))
    if FAILS: print('FAILED:', FAILS); sys.exit(1)

async def run(b, port):
    # ── ① 표 점검
    ctx, pg, errs = await mk(b, port)
    t = await pg.evaluate("()=>{const A=__ax.ACHV;return {n:A.length,ids:new Set(A.map(a=>a.id)).size,badF:A.filter(a=>typeof __ax.ACHCK[a.f]!=='function').map(a=>a.id),badG:A.filter(a=>![1,2,3].includes(a.g)).length,cats:[...new Set(A.map(a=>a.c))],catOk:A.every(a=>__ach.cats.some(c=>c[0]===a.c))}}")
    check('과제 30개 · id 중복 없음', t['n'] == 30 and t['ids'] == 30, t)
    check('모든 과제의 조건 함수 이름이 있다', not t['badF'], t)
    check('등급 동/은/금 · 분류 표가 맞는다', t['badG'] == 0 and t['catOk'], t)
    check('첫 화면 버튼에 0/30', (await pg.inner_text('#acN')) == '0/30', await pg.inner_text('#acN'))

    # ── ② 조건별 판정(합성 상태) — 판을 시작하고 값을 직접 만든다
    r = await pg.evaluate("""async()=>{
      const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;
      const got=()=>Object.keys(A.ACH.st.a).sort();
      const out={};
      A.achTick(.01);out.afterStart=got();                       // 시작 직후엔 없다
      S.t=299;A.achEval();out.t299=got();S.t=300;A.achEval();out.t300=got();
      S.t=900;A.achEval();out.t900=got();
      S.kills=999;A.achEval();out.k999=got().includes('k1');S.kills=1000;A.achEval();out.k1000=got().includes('k1');
      S.rel={a:1,b:1};A.achEval();out.rel2=got().includes('r1');S.rel={a:1,b:1,c:1};A.achEval();out.rel3=got().includes('r1');out.rel3notr2=!got().includes('r2');
      S.ev={w:1};A.achEval();out.ev1=got().includes('e1');out.ev1not3=!got().includes('e3');S.ev={w:1,x:1,y:1};A.achEval();out.ev3=got().includes('e3');
      S.synOn=['a','b'];A.achEval();out.syn2=got().includes('s1');S.synOn=['a','b','c'];A.achEval();out.syn3=got().includes('s1');
      A.ACH.mv=49999;A.achEval();out.mv49=got().includes('mv1');A.ACH.mv=50000;A.achEval();out.mv50=got().includes('mv1');
      A.ACH.kite=44;A.achEval();out.kt44=got().includes('kt1');A.ACH.kite=45;A.achEval();out.kt45=got().includes('kt1');
      return out;}""")
    check('시작 직후엔 아무것도 달성 안 됨', r['afterStart'] == [], r['afterStart'])
    check('5분 미만은 t5 없음, 5분이면 t5', 't5' not in r['t299'] and 't5' in r['t300'], r)
    check('15분이면 t10·t15 까지', 't10' in r['t900'] and 't15' in r['t900'] and 't30' not in r['t900'], r['t900'])
    check('처치 999 는 k1 없음 · 1000 이면 k1', not r['k999'] and r['k1000'], r)
    check('유물 2개는 r1 없음 · 3개면 r1, r2 는 아직', not r['rel2'] and r['rel3'] and r['rel3notr2'], r)
    check('각성 1개 e1 · 3개 e3', r['ev1'] and r['ev1not3'] and r['ev3'], r)
    check('시너지 2개는 없음 · 3개면 s1', not r['syn2'] and r['syn3'], r)
    check('이동 거리 49,999 는 없음 · 50,000 이면 mv1', not r['mv49'] and r['mv50'], r)
    check('몰이 44초는 없음 · 45초면 kt1', not r['kt44'] and r['kt45'], r)

    # ── ③ 안 맞기(움직임만 쌓임 · 맞으면 0) · 서 있기는 보상 없음 · 이동 거리
    r = await pg.evaluate("""async()=>{
      const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;S.p.mhp=1e6;S.p.hp=1e6;
      const out={};S.t=299;A.achTick(.01);const base=A.ACH.run;
      S.p.moving=false;for(let i=0;i<200;i++){S.t+=.1;A.achTick(.1);}      // 서 있기 20초
      out.standing=A.ACH.run;
      S.p.moving=true;for(let i=0;i<100;i++){S.t+=.1;S.p.x+=1;A.achTick(.1);}  // 움직이기 10초
      out.moving=+A.ACH.run.toFixed(2);out.mv=+A.ACH.mv.toFixed(1);
      A.achHit();out.afterHit=A.ACH.run;
      A.ACH.run=179;S.p.moving=true;S.t+=.1;A.achTick(1.5);A.achEval();out.nh1=!!A.ACH.st.a.nh1;
      S.p.x+=1e6;A.achTick(.016);out.teleport=A.ACH.mv<1e5;   // 순간이동(끌려감 등)은 거리로 안 센다
      return out;}""")
    check('서 있기 20초는 안 맞기 시간에 안 쌓인다(0)', r['standing'] == 0, r)
    check('움직인 10초는 쌓인다', abs(r['moving'] - 10) < .5, r)
    check('이동 거리가 센다(약 100)', 90 <= r['mv'] <= 110, r)
    check('피해를 받으면 안 맞기 0 으로', r['afterHit'] == 0, r)
    check('179초 + 움직임 1.5초 → nh1 달성', r['nh1'], r)
    check('순간이동은 이동 거리에 안 센다', r['teleport'], r)

    # ── ④ 몹 끌고 돌기 — 반경 200 안 25마리 이상일 때만
    r = await pg.evaluate("""async()=>{
      const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;S.p.hp=S.p.mhp=1e6;
      const out={};
      const put=n=>{for(const e of x.enemies.a)e.on=false;let k=0;for(let i=0;i<n;i++){const e=x.spawnEnemy(0,1,null,{x:S.p.x+100+i*2,y:S.p.y});if(e)k++;}return k;};
      out.k24=put(24);S.p.moving=true;A.ACH.acc=0;A.ACH.kite=0;for(let i=0;i<20;i++)A.achTick(.1);out.kite24=A.ACH.kite;
      out.k30=put(30);A.ACH.kite=0;for(let i=0;i<20;i++)A.achTick(.1);out.kite30=A.ACH.kite;
      S.p.moving=false;A.ACH.kite=0;for(let i=0;i<20;i++)A.achTick(.1);out.kiteStill=A.ACH.kite;
      return out;}""")
    check('24마리는 몰이로 안 센다', r['kite24'] == 0, r)
    check('30마리 + 움직임 2초 → 약 2초', r['k30'] >= 25 and 1.5 <= r['kite30'] <= 2.1, r)
    check('서 있으면 몰이 시간이 안 쌓인다', r['kiteStill'] == 0, r)

    # ── ⑤ 보스(첫 처치 · 미니 무피해 · 피해 받은 미니 · 최종)
    r = await pg.evaluate("""async()=>{
      const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;S.p.hp=S.p.mhp=1e6;S.p.moving=false;A.ACH.st={a:{},c:[]};
      const out={};
      const kill=(key,hitFirst)=>{S.t+=30;S.p.inv=0;const e=x.spawnBoss(key);if(!e)return 'nospawn';A.achTick(.02);if(hitFirst)A.achHit();S.t+=1;e.hp=1;x.hurt(e,1e9);return Object.keys(A.ACH.st.a).sort();};
      const minis=Object.keys(x.BOSS).filter(k=>x.BOSS[k].mini),fins=Object.keys(x.BOSS).filter(k=>x.BOSS[k].fin),norm=Object.keys(x.BOSS).filter(k=>!x.BOSS[k].mini&&!x.BOSS[k].fin);
      out.minis=minis;out.fins=fins;
      out.n1=kill(norm[0]);                       // 일반 보스 — b1 만
      out.m_hit=kill(minis[0],true);              // 미니 — 맞았으니 b2 아님
      out.m_clean=kill(minis[0],false);           // 미니 — 안 맞음
      return out;}""")
    check('보스 처치 → b1 만(b2·b3 없음)', r['n1'] == ['b1'], r)
    check('미니 보스가 나온 뒤 맞았으면 b2 없음', 'b2' not in r['m_hit'], r)
    check('미니 보스를 안 맞고 잡으면 b2', 'b2' in r['m_clean'], r)
    ctx2 = await b.new_context(); await ctx2.close()
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;S.p.hp=S.p.mhp=1e6;
      const k=Object.keys(x.BOSS).find(k=>x.BOSS[k].fin);if(!k)return 'nofin';const e=x.spawnBoss(k);if(!e)return 'nospawn';A.achTick(.02);e.hp=1;e.du=0;x.hurt(e,1e9);return !!A.ACH.st.a.b3;}""")
    check('최종 보스 처치 → b3', r is True, r)
    await ctx.close()

    # ── ⑥ 모드·캐릭터 — endRun(이긴 판)으로 판정
    ctx, pg, errs = await mk(b, port)
    r = await pg.evaluate("""async()=>{
      const x=__p6x,A=__ax;const out={};
      const run=(ch,hard,vh,won,endless)=>{x.CH_set(ch);document.getElementById('hardChk').checked=!!hard;document.getElementById('vhChk').checked=!!vh;x.start();const S=x.S;if(endless)S.endless=1;S.t=endless?10800:3600;A.achTick(.01);x.state='play';A.endRun(won,false);return {...A.ACH.st.a};};
      out.lose=Object.keys(run('brj',0,0,false)).sort();
      out.win=Object.keys(run('brj',0,0,true)).sort();
      out.chars1=[...A.ACH.st.c];
      out.hard=Object.keys(run('brj',1,0,true)).includes('hd');
      out.vh=Object.keys(run('brj',0,1,true)).includes('vh');
      return out;}""")
    check('져도 시간 과제는 받는다(t5~t30·t60 은 S.t 기준) · 클리어 과제는 없다', 'hd' not in r['lose'] and 'vh' not in r['lose'] and 'c3' not in r['lose'], r['lose'])
    check('이기면 t60 + 캐릭터 클리어 기록', 't60' in r['win'] and r['chars1'] == ['brj'], r)
    check('하드 클리어 → hd', r['hard'], r)
    check('베리하드 클리어 → vh', r['vh'], r)
    await ctx.close()

    # ── ⑦ 저장 · 중복 방지 · 새로고침 복원 · 저장 키
    ctx, pg, errs = await mk(b, port)
    await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();x.S.t=300;A.achTick(.3);A.achTick(.3);}""")   # 0.25초 눈금을 넘기도록
    st = await pg.evaluate("()=>JSON.parse(localStorage.getItem('sgg_sv_ach')||'null')")
    check('달성하면 sgg_sv_ach 에 저장된다', bool(st) and 't5' in st['a'], st)
    toasts = await pg.evaluate("""async()=>{const A=__ax;const q0=A.ACH.q.length;A.ACH.q.length=0;A.achEval();A.achEval();const q1=A.ACH.q.length;A.ACH.s=null;return {q0,q1};}""")
    check('이미 깬 과제는 다시 평가해도 알림이 안 쌓인다', toasts['q1'] == 0, toasts)
    await pg.reload(); await pg.wait_for_function('window.__ach!==undefined')
    check('새로고침 뒤 버튼 숫자가 복원된다', (await pg.inner_text('#acN')) == '1/30', await pg.inner_text('#acN'))
    ts0 = (await pg.evaluate("()=>JSON.parse(localStorage.getItem('sgg_sv_ach')).a.t5"))
    await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.newRun(null);x.S.t=600;A.achTick(.3);A.achTick(.3);}""")
    ts1 = (await pg.evaluate("()=>JSON.parse(localStorage.getItem('sgg_sv_ach')).a.t5"))
    check('다시 깨도 첫 달성 시각이 그대로(덮어쓰지 않음)', ts0 == ts1, (ts0, ts1))
    toast = await pg.evaluate("()=>document.getElementById('toast').textContent")
    check('달성 순간 토스트에 「도전 과제 달성」', '도전 과제 달성' in toast, toast)
    await ctx.close()

    # ── ⑧ 저장소 차단 · 깨진 값
    blk = "Storage.prototype.setItem=function(){throw new Error('blocked')};"
    ctx, pg, errs = await mk(b, port, init=blk)
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();x.S.t=300;let e=null;try{A.achTick(.3);A.achTick(.3);x.update(.05);}catch(er){e=String(er);}return {e,mem:__ach.mem,n:__ach.stat().n,state:x.state};}""")
    check('쓰기가 막혀도 판은 계속(예외 없음) · 이번 방문엔 달성이 남는다', r['e'] is None and r['n'] >= 1 and r['state'] == 'play', r)
    check('저장 실패를 mem 으로 알린다', r['mem'] == 1, r)
    await pg.evaluate("()=>{__p6x.show('title');window.__acui.open();}")
    note = await pg.inner_text('#acBody')
    check('겹창이 「저장하지 못해요」 안내를 한다', '저장하지 못해요' in note, note[:200])
    check('콘솔 오류 0(저장 차단)', not errs, errs)
    await ctx.close()
    rd = "Storage.prototype.getItem=function(k){if(k==='sgg_sv_ach')throw new Error('blocked');return null};"
    ctx, pg, errs = await mk(b, port, init=rd)
    n = await pg.evaluate("()=>__ach.stat().n")
    check('읽기가 막혀도 0/30 으로 시작', n == 0 and not errs, errs)
    await ctx.close()
    bad = "try{localStorage.setItem('sgg_sv_ach','{not json')}catch(e){}"
    ctx, pg, errs = await mk(b, port, init=bad)
    r = await pg.evaluate("()=>({n:__ach.stat().n,bad:__ach.bad})")
    check('깨진 저장값은 빈 기록으로 시작 · bad 표시', r['n'] == 0 and r['bad'] == 1 and not errs, (r, errs))
    await ctx.close()
    junk = "try{localStorage.setItem('sgg_sv_ach',JSON.stringify({a:{t5:123,zzz:5,t10:'x',k1:-1},c:['brj','nope',7]}))}catch(e){}"
    ctx, pg, errs = await mk(b, port, init=junk)
    r = await pg.evaluate("()=>({n:__ach.stat().n,c:__ax.ACH.st.c,a:Object.keys(__ax.ACH.st.a)})")
    check('모르는 id·잘못된 값은 버리고 올바른 것만 읽는다', r['a'] == ['t5'] and r['c'] == ['brj'], r)
    await ctx.close()

    # ── ⑨ 겹창 · 결과 화면 · 일일 도전/연습
    for (w, h, mob) in [(320, 568, True), (360, 640, True), (390, 844, True), (844, 390, True), (1280, 800, False)]:
        ctx, pg, errs = await mk(b, port, w=w, h=h, mobile=mob, init="try{localStorage.setItem('sgg_sv_ach',JSON.stringify({a:{t5:1,t10:2,k1:3},c:[]}))}catch(e){}")
        ov = await pg.evaluate("""()=>{const o=document.getElementById('acOpen').getBoundingClientRect(),l=document.querySelector('#title .key .lab').getBoundingClientRect();return {w:o.width,h:o.height,right:o.right,vw:innerWidth,hit:o.left<l.right&&o.top<l.bottom,sw:document.documentElement.scrollWidth}}""")
        check('%dx%d 버튼이 화면 안 · 44px 이상 · 뒤로 가기 링크와 안 겹침 · 가로 넘침 0' % (w, h), ov['right'] <= ov['vw'] and ov['h'] >= 44 and ov['w'] >= 44 and not ov['hit'] and ov['sw'] <= ov['vw'], ov)
        await pg.click('#acOpen')
        o = await pg.evaluate("""()=>{const b=document.getElementById('acBody'),ov=document.getElementById('acOv');return {on:ov.classList.contains('on'),sw:b.scrollWidth,cw:b.clientWidth,rows:b.querySelectorAll('.acrow').length,dn:b.querySelectorAll('.acrow.dn').length,sec:b.querySelectorAll('.acsec').length,docsw:document.documentElement.scrollWidth,vw:innerWidth,scroll:b.scrollHeight>b.clientHeight,txt:b.innerText}}""")
        check('%dx%d 겹창: 30줄 · 달성 3 · 분류 7 · 가로 넘침 0 · 세로 스크롤' % (w, h), o['on'] and o['rows'] == 30 and o['dn'] == 3 and o['sec'] == 7 and o['sw'] <= o['cw'] + 1 and o['docsw'] <= o['vw'] and o['scroll'], o)
        if w == 390:
            check('겹창에 달성 N/30 · 힌트(조건)가 보인다', '3 / 30' in o['txt'] and '한 판에서 15분 생존' in o['txt'], o['txt'][:200])
        await pg.keyboard.press('Escape')
        check('%dx%d Esc 로 닫힌다' % (w, h), not await pg.evaluate("()=>window.__acui.opened"))
        check('%dx%d 콘솔 오류 0' % (w, h), not errs, errs)
        await ctx.close()

    # 결과 화면 목록 + 일일(기록) + 일일 연습
    ctx, pg, errs = await mk(b, port)
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;S.t=900;A.achTick(.3);A.achTick(.3);x.state='play';A.endRun(false,false);
      const el=document.getElementById('rAch');return {hid:el.hidden,txt:el.innerText};}""")
    check('결과 화면에 이번 판 달성 목록(t5·t10·t15)', (not r['hid']) and '첫 고비' in r['txt'] and '버티는 중' in r['txt'] and '아직 팔팔해' in r['txt'], r)
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;A.achTick(.01);x.state='play';A.endRun(false,false);const el=document.getElementById('rAch');return {hid:el.hidden,txt:el.innerText};}""")
    check('새로 달성한 게 없으면 목록 칸이 숨는다', r['hid'], r)
    # 일일 도전: 로그인 없으면 ranked=false(연습) → 기록 안 됨
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;const before=JSON.stringify(A.ACH.st);x.CH_set('brj');x.start({daily:true});const S=x.S;const pr=S.dly&&S.dly.ranked;S.t=1800;A.achTick(.3);A.achTick(.3);
      const out={ranked:!!pr,off:A.ACH.off,same:JSON.stringify(A.ACH.st)===before};x.state='play';A.endRun(false,false);const el=document.getElementById('rAch');out.txt=el.innerText;out.hid=el.hidden;return out;}""")
    check('연습(비로그인) 일일 도전은 과제에 기록되지 않는다', r['ranked'] is False and r['off'] == 1 and r['same'], r)
    check('연습 판 결과에 「기록되지 않아요」 안내', (not r['hid']) and '기록되지 않아요' in r['txt'], r)
    # 기록되는 일일 도전: dly.ranked=true 로 합성
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start({daily:true});const S=x.S;S.dly.ranked=true;A.ACH.s=null;S.t=1800;A.achTick(.3);A.achTick(.3);return {off:A.ACH.off,t30:!!A.ACH.st.a.t30};}""")
    check('기록되는 일일 도전은 달성이 인정된다', r['off'] == 0 and r['t30'], r)
    # 새 난수를 안 쓴다 — 같은 시드의 일일 도전은 같은 결과(과제 훅이 Math.random 을 부르지 않는다)
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;let c=0;const o=Math.random;Math.random=()=>{c++;return o()};S.p.moving=true;for(let i=0;i<50;i++){S.t+=.1;A.achTick(.1);}A.achEval();A.achHit();Math.random=o;return c;}""")
    check('과제 코드는 Math.random 을 부르지 않는다(난수열 불변)', r == 0, r)
    check('콘솔 오류 0', not errs, errs)
    await ctx.close()

    # ── ⑩ 이어하기: 되살린 판에서도 ACH 가 새로 잡히고 오류 없음
    ctx, pg, errs = await mk(b, port)
    r = await pg.evaluate("""async()=>{const x=__p6x,A=__ax;x.CH_set('brj');x.start();const S=x.S;S.p.moving=true;for(let i=0;i<30;i++){S.t+=.1;S.p.x+=3;A.achTick(.1);}const mv1=A.ACH.mv;
      const keep=A.ACH.s;const S2=x.S;A.ACH.s=null;A.achTick(.1);return {mvReset:A.ACH.mv===0&&mv1>0,sameS:A.ACH.s===S2};}""")
    check('S 가 바뀌면(새 판·이어하기) ACH 판 값이 새로 시작한다', r['mvReset'] and r['sameS'], r)
    check('콘솔 오류 0', not errs, errs)
    await ctx.close()

asyncio.run(main())
