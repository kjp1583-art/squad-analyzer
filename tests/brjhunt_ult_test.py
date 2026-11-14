# -*- coding: utf-8 -*-
"""💥 동료 필살기(컷씬) 시험 — 효과 10종 × 컷씬 6종이 실제 사냥터에서 에러 없이 돌고, 컷씬 동안 시간이 멈췄다가 끝나면 효과가 나가며(몹이 맞는다),
컷씬 끄기·보스전 제외·쿨 간격이 지켜지고, 서버가 모르는 값(kind/cut)을 보내도 안전한 기본으로 돈다. 사용: python3.13 tests/brjhunt_ult_test.py (playwright 없으면 SKIP)"""
import asyncio, json, os, socket, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
CHROME = next((p for p in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium/chrome-linux/chrome') if os.path.exists(p)), None)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
VIEW = json.load(open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8'))
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
KINDS = ['nova', 'rain', 'slash', 'bind', 'drain', 'rally', 'meteor', 'gather', 'chain', 'execute']
CUTS = ['slash', 'zoom', 'rise', 'spot', 'glitch', 'aura']
async def main(port):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width': 900, 'height': 640})).new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            r = route.request
            if r.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(VIEW))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(3000)
        ok(await pg.evaluate("FIELD.debug.allies().length") >= 1 and await pg.evaluate("!!FIELD.debug.allies()[0].pr.ult"), '동료에게 서버가 준 필살기(ult)가 실려 있다')
        for i, kind in enumerate(KINDS):
            cut = CUTS[i % 6]
            await pg.evaluate("FIELD.debug.E.hitstop=0"); await pg.evaluate("()=>{FIELD.debug.clearMobs();for(let k=0;k<8;k++)FIELD.debug.spawnMob(FIELD.debug.P.x+60+k*34)}")
            n0 = await pg.evaluate("FIELD.debug.mobs().length"); hp0 = await pg.evaluate("FIELD.debug.mobs().reduce((s,m)=>s+m.hp,0)")
            started = await pg.evaluate("FIELD.debug.ultNow('%s','%s')" % (kind, cut))
            t0 = await pg.evaluate("FIELD.debug.E.t"); await pg.wait_for_timeout(500)
            frozen = await pg.evaluate("!!FIELD.debug.E.cut")
            await pg.wait_for_timeout(2600)
            n1 = await pg.evaluate("FIELD.debug.mobs().length"); hp1 = await pg.evaluate("FIELD.debug.mobs().reduce((s,m)=>s+(m.st==='dying'?0:m.hp),0)")
            ended = await pg.evaluate("!FIELD.debug.E.cut")
            hit = (n1 < n0) or hp1 < hp0 or kind in ('rally',)
            ok(started and frozen and ended and hit, f'{kind}/{cut}: 컷씬 시작→끝, 효과가 몹에 닿음(몹 {n0}→{n1}, 체력합 {hp0:.0f}→{hp1:.0f})' if kind != 'rally' else f'{kind}/{cut}: 컷씬 시작→끝(사기 버프)')
        # 컷씬 끄기 → 자동 발동 안 함
        await pg.evaluate("FIELD.setCutscene(false)"); await pg.evaluate("()=>{FIELD.debug.E.cutGap=0;for(const a of FIELD.debug.allies())a.ucd=0}"); await pg.wait_for_timeout(1500)
        ok(await pg.evaluate("!FIELD.debug.E.cut"), '컷씬 끄기 → 자동 발동 안 함'); await pg.evaluate("FIELD.setCutscene(true)")
        # 쿨 간격: 컷씬 하나가 끝난 직후엔 다른 동료가 바로 이어 쓰지 않는다
        await pg.evaluate("()=>{FIELD.debug.E.cut=null;FIELD.debug.E.cutGap=13;for(const a of FIELD.debug.allies())a.ucd=0;FIELD.debug.spawnPause(true)}"); await pg.wait_for_timeout(800)
        ok(await pg.evaluate("!FIELD.debug.E.cut"), '컷씬 간격(13초) 안에는 새 컷씬이 안 뜬다')
        # 알 수 없는 값은 안전한 기본(정규화)
        ok(await pg.evaluate("FIELD.debug.ultNow('zzz','qqq')") is False, '모르는 효과 종류(kind)는 필살기 없음으로 처리 — 에러 없이 건너뜀')
        # 🐲 보스전: 싸움이 시작되면 한 판에 최대 2번 컷씬 + 보스에게 연출 · 보스전은 끝까지 정상 진행(결과 곡선은 그대로)
        for kind in KINDS:
            await pg.evaluate("()=>{FIELD.debug.clearMobs()}")
            await pg.evaluate("(k)=>{FIELD.startChallenge({img:'taewoong',name:'테스트 보스',hp:1000,res:'win'}); window.__cuts=0; window.__ev=[]; (window.__offs||[]).forEach(f=>f()); window.__offs=[FIELD.on('ult',()=>window.__cuts++), FIELD.on('boss',e=>window.__ev.push(e.phase))]; const a=FIELD.debug.allies()[0]; a.pr.ult={nm:'시험',kind:k,quote:'보스에게',desc:'',col:'#ffd23c',cut:'zoom',cd:30,mult:200,hits:3,em:''}; for(const x of FIELD.debug.allies()) if(x!==a) x.pr.ult=null;}", kind)
            await pg.evaluate("()=>{FIELD.debug.E.cutGap=0}")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await pg.evaluate("window.__ev.includes('win')"): break
            cuts = await pg.evaluate("window.__cuts"); done = await pg.evaluate("window.__ev.includes('win')")
            ok(1 <= cuts <= 2 and done, f'보스전 {kind}: 컷씬 {cuts}번(1~2) · 보스전 정상 종료(win={done})')
            for _ in range(30):
                if not await pg.evaluate("!!FIELD.stats().boss"): break
                await pg.wait_for_timeout(500)
        ok(not errs, f'페이지 오류 0 {errs[:3]}')
        await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
