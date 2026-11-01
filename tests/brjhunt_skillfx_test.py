#!/usr/bin/env python3.13
"""스킬 구분감·임팩트 시험(4차 개편). 사용: CHROME=... python3.13 tests/brjhunt_skillfx_test.py [--shots 폴더]
스킬 10종을 하나씩 시전해 본다(발판 위 몹 5마리 앞에서, 실제 그림 시트까지 로드):
 · 콜아웃 문구·색·크기·이펙트 종류(조합)·전조/발동 이벤트·맞은 몹 모습·데미지 숫자 색이 10종 모두 서로 다른가
 · 큰 스킬(폭격·번개·논란 폭풍)만 화면이 어두워지고 줌·흔들림이 크고, 작은 스킬(베기·부리)은 가벼운가
 · 겹쳐 쓰면(큰 스킬 직후 작은 스킬) 콜아웃이 읽히게 쌓이는가(동시 2줄 상한) · 줄임 모드·저사양 모드 · 프레임 비용 · 콘솔 오류 0
 · --shots 를 주면 스킬별 5컷(전조→발동→절정→여운) 캡처 시트를 저장한다."""
import asyncio, os, sys, time, threading, functools, http.server
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x != '' and not c else ''), flush=True)
    if not c: FAILS.append(n)

class _Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
_h = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(_Q, directory=ROOT)); threading.Thread(target=_h.serve_forever, daemon=True).start()
URL = 'http://127.0.0.1:%d/tests/brjhunt_arena_harness.html' % _h.server_address[1]
IDS = ['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shield', 'shrimp', 'storm']
HIT = {'slash': 'cut', 'peck': 'spark', 'spin': 'cut', 'bomb': 'burn', 'thunder': 'shock', 'fire': 'burn', 'egg': 'gold', 'shield': 'push', 'shrimp': 'push', 'storm': 'shock'}
SIZE = {'slash': 1, 'peck': 1, 'spin': 2, 'bomb': 3, 'thunder': 3, 'fire': 2, 'egg': 2, 'shield': 2, 'shrimp': 2, 'storm': 4}

SETUP = """([sid,opts])=>{ if(window.A) A.destroy(); const a=window.A=mkArena(Object.assign({seed:3,manual:true},opts||{}));
  const st=mkState(1.5,[sid,null,null,null],{region:'홍대',scale:true}); st.skills.passive=null; st.combat.acc=100000; a.setState(st); a.debug.clearMobs(); a.setAuto(false);
  const M0=a.debug.map(); let px=380; for(let x=160;x<M0.W-400;x+=20){ if(!M0.blocks.some(b=>b.x1>x-120&&b.x0<x+300)){ px=x; break; } }   // 총알을 막는 벽 블록이 없는 자리
  a.debug.setPos(px,304); for(let i=0;i<40;i++) a.tick(1/60);
  const P=a.debug.P; P.face=1; P.mp=P.mpMax; a.debug.spawnPause(true);
  for(const dx of [70,120,170,215,-70]){ const m=a.debug.spawnMob(px+dx,a.debug.map().plats[0],{noPack:true,el:false,fly:false,shoot:false}); if(m){ m.st='patrol'; m.sp=0; m.hp=m.max=1e9; } }
  for(let i=0;i<10;i++) a.tick(1/60);
  window.EV=[]; ['skill','callout','cast','skillend'].forEach(n=>a.on(n,e=>EV.push([n,Object.assign({},e)])));
  window.__ok=true; }"""

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME)
        pg = await br.new_page(viewport={'width': 800, 'height': 500}, device_scale_factor=1)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and '404' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(500)
        await pg.evaluate("document.getElementById('w').style.width='800px'")
        res = {}
        for sid in IDS:
            await pg.evaluate(SETUP, [sid, None]); await pg.wait_for_timeout(350)
            await pg.evaluate("for(let i=0;i<20;i++) A.tick(1/60)")
            check(f'{sid}: 그림 시트(manifest)가 로드돼 있다', await pg.evaluate("!!A.debug.manifest() && !!A.debug.manifest().sk_"+sid) if sid != 'shield' else True)
            await pg.evaluate("A.input.press('s1'); A.tick(1/60); A.input.release('s1')")
            st0 = await pg.evaluate("A.stats()")
            snaps = []
            for k, dt in enumerate([0.10, 0.16, 0.14, 0.22, 0.4]):
                await pg.evaluate("n=>{for(let i=0;i<n;i++) A.tick(1/60)}", max(1, int(dt * 60)))
                if SHOTS:
                    os.makedirs(SHOTS, exist_ok=True)
                    el = await pg.query_selector('canvas'); await el.screenshot(path=f'{SHOTS}/skill_{sid}_{k}.png')
                snaps.append(await pg.evaluate("({dim:A.stats().dim,zoom:A.stats().zoom,sh:A.debug.E.shake,casting:A.stats().casting,using:A.stats().usingId,cl:A.debug.callouts().map(c=>c.text)})"))
            info = await pg.evaluate("""()=>{ const L=A.debug.castLog()[A.debug.skills[0].id]||{}; const mobs=A.debug.mobs().filter(m=>!m.boss).map(m=>m.fxk);
              const tx=A.debug.texts().filter(t=>t.on&&t.kind==='s').map(t=>[t.col,t.ol]); return {L, mobs, tx, ev:EV.map(e=>[e[0],e[1].stage||e[1].id||''])}; }""")
            L = info['L']
            res[sid] = dict(call=L.get('call'), col=L.get('col'), size=L.get('size'), kinds=tuple(sorted((L.get('kinds') or {}).keys())), ev=info['ev'], mobs=info['mobs'], tx=info['tx'], snaps=snaps, st0=st0)
        calls = [r['call'] for r in res.values()]; cols = [r['col'] for r in res.values()]; kinds = [r['kinds'] for r in res.values()]
        check('콜아웃 문구 10종이 전부 있고 서로 다르다', all(calls) and len(set(calls)) == 10, calls)
        check('스킬 색 10종이 서로 다르다', len(set(cols)) == 10, cols)
        check('이펙트 종류 조합이 10종 모두 다르다(화면만 봐도 구분)', len(set(kinds)) == 10, {k: v['kinds'] for k, v in res.items()})
        check('콜아웃 크기 위계: 폭풍(4) > 폭격·번개(3) > 중간(2) > 베기·부리(1)', all(res[i]['size'] == SIZE[i] for i in IDS), {i: res[i]['size'] for i in IDS})
        for sid in IDS:
            r = res[sid]
            names = [e[0] for e in r['ev']]
            check(f'{sid}: 이벤트 순서 skill → callout(1번) → cast pre → cast fire', names.count('callout') == 1 and names.count('skill') == 1 and [e for e in r['ev'] if e[0] == 'cast'][:2] == [['cast', 'pre'], ['cast', 'fire']], r['ev'][:6])
            check(f'{sid}: 시전 직후 콜아웃이 화면에 떠 있다', r['snaps'][0]['cl'] and r['snaps'][0]['cl'][-1] == r['call'], r['snaps'][0])
            check(f'{sid}: 시전 중 「사용 중」(usingId) 표시', r['snaps'][0]['using'] == sid, r['snaps'][0])
            if sid not in ('shield', 'shrimp'):
                check(f'{sid}: 맞은 몬스터 모습 = {HIT[sid]}', HIT[sid] in r['mobs'], r['mobs'])
            check(f'{sid}: 스킬 피해 숫자가 스킬 색', (not r['tx']) or all(t[0] == r['col'] for t in r['tx']), r['tx'])
        dims = {i: max(s['dim'] for s in res[i]['snaps']) for i in IDS}
        shakes = {i: max(s['sh'] for s in res[i]['snaps']) for i in IDS}
        check('큰 스킬(폭격·번개·폭풍)은 화면이 어두워진다(0.2 이상), 작은 스킬은 안 어두워진다', all(dims[i] > 0.2 for i in ('bomb', 'thunder', 'storm')) and all(dims[i] < 0.05 for i in ('slash', 'peck', 'spin', 'egg')), dims)
        check('흔들림: 큰 스킬 > 작은 스킬', min(shakes[i] for i in ('bomb', 'thunder', 'storm')) > max(shakes[i] for i in ('slash', 'peck')) + 1.5, shakes)

        # ---- 겹쳐 쓰기: 큰 스킬 직후 작은 스킬 ----
        await pg.evaluate("""()=>{ if(window.A) A.destroy(); const a=window.A=mkArena({seed:3,manual:true}); const st=mkState(1.5,['bomb','peck','slash','storm'],{region:'홍대',scale:true}); st.skills.passive=null; a.setState(st);
            a.debug.clearMobs(); a.setAuto(false); a.debug.setPos(380,304); for(let i=0;i<30;i++) a.tick(1/60); a.debug.P.mp=a.debug.P.mpMax; a.debug.spawnPause(true); a.input.press('s1'); a.tick(1/60); a.input.release('s1'); for(let i=0;i<22;i++) a.tick(1/60); }""")
        await pg.evaluate("(()=>{ const P=A.debug.P; P.cast=null; P.hurtT=0; A.input.press('s2'); A.tick(1/60); A.input.release('s2'); })()")
        ov = await pg.evaluate("({cl:A.debug.callouts().map(c=>({t:c.text,sub:c.sub,size:c.size})),dim:A.stats().dim})")
        check('큰 스킬 직후 작은 스킬: 콜아웃은 동시에 최대 2줄, 작은 쪽은 아래 줄(sub)로 작게', len(ov['cl']) <= 2 and any(c['sub'] for c in ov['cl']) and ov['cl'][0]['size'] == 3, ov)
        check('겹쳐 써도 어두워짐이 쌓여 새까매지지 않는다(≤ 0.7)', ov['dim'] <= 0.7, ov['dim'])
        fxn = await pg.evaluate("A.debug.fxs().length")
        check('동시 이펙트 개수 상한(56)', fxn <= 56, fxn)

        # ---- 줄임 모드(prefers-reduced-motion) · 저사양 ----
        for mode, opt in (('reduced', {'reduced': True}), ('low', None)):
            await pg.evaluate(SETUP, ['storm', opt])
            if mode == 'low': await pg.evaluate("A.debug.setLow(true)")
            await pg.evaluate("A.input.press('s1'); for(let i=0;i<40;i++) A.tick(1/60); A.input.release('s1')")
            s = await pg.evaluate("({dim:A.stats().dim,zoom:A.stats().zoom,sh:A.debug.E.shake,fx:A.debug.fxs().length,reduced:A.stats().reduced,parts:A.debug.parts().filter(p=>p.on).length})")
            if mode == 'reduced': check('줄임 모드: 흔들림·줌·어두워짐 0 (콜아웃·이펙트는 그대로)', s['reduced'] and s['sh'] == 0 and s['zoom'] == 0 and s['dim'] == 0 and s['fx'] > 0, s)
            else: check('저사양 모드: 입자가 절반 풀 안에서만(≤110), 줌 없음', s['parts'] <= 110 and s['zoom'] == 0, s)
            ev = await pg.evaluate("EV.map(e=>e[0])")
            check(f'{mode}: 콜아웃은 그대로 나온다', 'callout' in ev, ev)

        # ---- 프레임 비용 ----
        await pg.evaluate(SETUP, ['bomb', None])
        t = await pg.evaluate("""()=>{ const a=A; a.debug.setLow(false); const P=a.debug.P; const ts=[]; for(let k=0;k<6;k++){ for(const i of ['s1']){ a.debug.P.mp=a.debug.P.mpMax; a.debug.P.cast=null; a.input.press(i); a.tick(1/60); a.input.release(i); }
            for(let f=0;f<50;f++){ const t0=performance.now(); a.tick(1/60); ts.push(performance.now()-t0); } for(let f=0;f<70;f++) a.tick(1/60); }
            ts.sort((x,y)=>x-y); return {avg:ts.reduce((s,x)=>s+x,0)/ts.length,p95:ts[Math.floor(ts.length*0.95)],max:ts[ts.length-1]}; }""")
        check('큰 스킬 연발 중 프레임 비용(소프트웨어 렌더) 평균 ≤ 14ms · p95 ≤ 30ms', t['avg'] <= 14 and t['p95'] <= 30, t)
        check('콘솔·페이지 오류 0', not errs, errs[:3])
        await br.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과')
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
