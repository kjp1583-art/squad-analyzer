# -*- coding: utf-8 -*-
"""🧪 쿨타임 물약 웹 시험 — 물약 버튼·단축키(H/J)·서버 허락 뒤 회복·쿨타임(두 번째는 막힘)·개수 감소·수령 창에서 구매·AUTO 자동 사용. 가짜 서버(stateful). python3.13 tests/brjhunt_potion_test.py"""
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
async def main(port):
    st = {'hp': 3, 'mp': 1, 't': {'hp': 0, 'mp': 0}, 'gold': 1000, 'uses': 0, 'buys': 0}
    def view():
        v = json.loads(json.dumps(VIEW)); P = v['view']['potion']; now = time.time()
        for k in ('hp', 'mp'): P['kinds'][k]['n'] = st[k]; P['kinds'][k]['cd_left'] = round(max(0, 10 - (now - st['t'][k])), 1)
        return v
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width': 1280, 'height': 800})).new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            req = route.request; path = req.url.split('bot-hosting.cloud')[1]
            if req.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            body = view(); data = json.loads(req.post_data or '{}')
            if path == '/brj/potion_use':
                k = data.get('kind'); now = time.time()
                if st[k] <= 0: res = 'none'; extra = {}
                elif now - st['t'][k] < 10: res = 'cooldown'; extra = {'wait': round(10 - (now - st['t'][k]), 1)}
                else: st[k] -= 1; st['t'][k] = now; st['uses'] += 1; res = 'ok'; extra = {'kind': k, 'pct': 0.35 if k == 'hp' else 0.4}
                body = view(); body.update(dict({'result': res}, **extra))
            elif path == '/brj/potion_buy':
                k = data.get('kind'); n = data.get('n'); cost = 12 * n
                if st['gold'] < cost: res = 'gold'
                else: st['gold'] -= cost; st[k] += n; st['buys'] += 1; res = 'ok'
                body = view(); body.update({'result': res})
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body, ensure_ascii=False))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("()=>{FIELD.setAuto(false)}")
        ok(await pg.evaluate("()=>document.querySelectorAll('#dock .pot').length") == 2, '하단 HUD 에 물약 버튼 둘(회복·마나)')
        ok(await pg.evaluate("()=>document.querySelector('#dock .pot[data-pot=hp] .pn').textContent") == '3', '회복 물약 3개 표시')
        await pg.evaluate("()=>{const P=FIELD.debug.P; P.hp=Math.floor(P.hpMax*0.2); window.__hp0=P.hp;}")
        await pg.keyboard.press('KeyH'); await pg.wait_for_timeout(700)
        h1 = await pg.evaluate("()=>FIELD.debug.P.hp"); h0 = await pg.evaluate("()=>window.__hp0")
        ok(st['uses'] == 1 and st['hp'] == 2 and h1 > h0 + 100, f'H 키: 서버 허락 뒤 체력 회복 ({h0}→{h1}) · 개수 3→2')
        ok(await pg.evaluate("()=>document.querySelector('#dock .pot[data-pot=hp]').classList.contains('cool')"), '사용 직후 쿨타임 표시')
        await pg.keyboard.press('KeyH'); await pg.wait_for_timeout(500)
        ok(st['uses'] == 1 and st['hp'] == 2, '쿨타임 중에는 다시 못 쓴다(서버에 요청도 안 감)')
        await pg.evaluate("()=>{FIELD.debug.P.mp=1}"); await pg.evaluate("()=>document.querySelector('#dock .pot[data-pot=mp]').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))"); await pg.wait_for_timeout(700)
        ok(st['mp'] == 0 and await pg.evaluate("()=>FIELD.debug.P.mp") > 20, '마나 물약 버튼 클릭: 마나 회복 · 쿨타임은 종류별로 따로')
        await pg.evaluate("()=>{document.querySelector('[data-tab=hunt]').click()}"); await pg.wait_for_timeout(600)
        await pg.evaluate("()=>document.querySelector('[data-do=potbuy][data-kind=hp][data-n=\"10\"]').click()"); await pg.wait_for_timeout(700)
        ok(st['buys'] == 1 and st['hp'] == 12 and st['gold'] == 1000 - 120, f'수령 창에서 10개 구매(골드 차감) {st}')
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
        st['t']['hp'] = 0; st['t']['mp'] = 0; await pg.evaluate("()=>{ POT_CD.hp=0; POT_CD.mp=0; }")
        await pg.evaluate("()=>{FIELD.setAuto(true); const P=FIELD.debug.P; P.hp=Math.floor(P.hpMax*0.2);}"); await pg.wait_for_timeout(1500)
        ok(st['uses'] >= 3, f'AUTO 일 때 체력이 35% 미만이면 알아서 마신다 (사용 {st["uses"]}회)')
        ok(not errs, f'페이지 오류 0 {errs[:2]}'); await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
