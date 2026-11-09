# -*- coding: utf-8 -*-
"""🔁 엘리트 자동 소환 시험 — 자동 버튼을 켜면 게이지가 다 닳을 때까지(3칸) 엘리트를 쓰러뜨릴 때마다 다음 엘리트가 자동으로 소환되고, 다 쓰면 스스로 꺼진다.
서버는 stateful 가짜 API(게이지 3칸). 사용: python3.13 tests/brjhunt_elite_auto_test.py  (playwright 없으면 SKIP)"""
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
    st = {'charges': 3, 'elite': None, 'seq': 0, 'summons': 0, 'kills': 0}
    def view():
        v = json.loads(json.dumps(VIEW)); L = v['view']['loot']; L['gauge']['charges'] = st['charges']; L['gauge']['g'] = st['charges'] * 500; L['elite'] = st['elite']; return v
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width': 1280, 'height': 800})).new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            req = route.request; path = req.url.split('bot-hosting.cloud')[1]
            if req.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            if path == '/brj/elite':
                if st['elite']: body = view(); body.update({'result': 'active', 'elite': st['elite']})
                elif st['charges'] < 1: body = view(); body.update({'result': 'nogauge'})
                else:
                    st['charges'] -= 1; st['seq'] += 1; st['summons'] += 1; st['elite'] = {'id': f"e{st['seq']}", 'stage': 12, 'name': '맵고추 군단', 'left': 180, 'ttl': 180, 'hp_mult': 22}
                    body = view(); body.update({'result': 'ok', 'elite': st['elite']})
            elif path == '/brj/elite_kill':
                st['elite'] = None; st['kills'] += 1; body = view()
                body.update({'result': 'drop', 'auto': False, 'stage': 12, 'item': {'id': 'i9', 'name': '한강 무기', 'emoji': '🗡', 'rar': 1, 'rar_name': '레어', 'ilv': 12, 'slot': 'weapon', 'main': ['atk', 50], 'subs': []}})
            else: body = view()
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body, ensure_ascii=False))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        ok(await pg.evaluate("()=>getComputedStyle(document.getElementById('eliteAuto')).display!=='none'"), '게이지가 있으면 HUD 에 🔁 자동 버튼이 보인다')
        await pg.evaluate("()=>document.getElementById('eliteAuto').click()"); await pg.wait_for_timeout(300)
        ok(await pg.evaluate("()=>document.getElementById('eliteAuto').getAttribute('aria-pressed')==='true'"), '누르면 켜진다(aria-pressed)')
        for n in range(1, 4):
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if st['summons'] >= n and await pg.evaluate("()=>FIELD.hasElite()"): break
            ok(st['summons'] == n, f'{n}번째 엘리트가 자동으로 소환됨(소환 {st["summons"]}회 · 남은 게이지 {st["charges"]}칸)')
            # 이번 엘리트 처치: 체력 1 + 자동 사냥이 처치
            await pg.evaluate("()=>{const m=FIELD.debug.mobs().find(x=>x.big); if(m){m.hp=1; FIELD.debug.setPos(m.x-30,m.y);}}")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if st['kills'] >= n: break
            ok(st['kills'] == n, f'{n}번째 엘리트 처치 보고')
        for _ in range(40):
            await pg.wait_for_timeout(500)
            if not await pg.evaluate("()=>ELITE_AUTO"): break
        await pg.wait_for_timeout(1500)
        ok(st['summons'] == 3, f'게이지가 다 닳으면 더 소환하지 않는다(총 {st["summons"]}회)')
        ok(not await pg.evaluate("()=>ELITE_AUTO"), '게이지를 다 쓰면 자동 소환이 스스로 꺼진다')
        ok(not errs, f'페이지 오류 0 {errs[:2]}'); await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
