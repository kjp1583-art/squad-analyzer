# -*- coding: utf-8 -*-
"""👗 웹 브장신 키우기 꾸미기(파츠) 맛동산 판매 시험 — 꾸미기 창에서 사고(확인 창) 입고 벗기, 움직이는 병아리에 파츠 반영(setParts), 맛동산이 모자라면 못 산다, 폰 가로 넘침 0.
서버는 stateful 가짜 API. 사용: python3.13 tests/brjhunt_cos_shop_test.py  (playwright 없으면 SKIP)"""
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
async def run(b, port, vp, tag):
    st = {'md': 2, 'own': [], 'worn': {}, 'buys': 0}
    SLOT = {'crown': 'head', 'bow': 'head', 'wizard': 'head', 'mohawk': 'head', 'headphones': 'head', 'sunglasses': 'face', 'scarf': 'neck', 'bowtie': 'neck', 'cape': 'back', 'wings': 'back'}
    def view():
        v = json.loads(json.dumps(VIEW)); C = v['view']['cos']; C['md'] = st['md']; C['worn'] = dict(st['worn'])
        for p in C['parts']: p['owned'] = p['key'] in st['own']; p['on'] = st['worn'].get(p['slot']) == p['key']
        return v
    pg = await (await b.new_context(viewport=vp)).new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    async def api(route):
        req = route.request; path = req.url.split('bot-hosting.cloud')[1]
        if req.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
        body = view(); data = json.loads(req.post_data or '{}')
        if path == '/brj/cos_buy':
            k = data.get('key')
            if k in st['own']: res = 'owned'
            elif st['md'] < 1: res = 'short'
            else: st['md'] -= 1; st['own'].append(k); st['worn'][SLOT[k]] = k; st['buys'] += 1; res = 'ok'
            body = view(); body.update({'result': res})
        elif path == '/brj/cos_equip':
            k = data.get('key')
            if k:
                if k not in st['own']: res = 'not_owned'
                else: st['worn'][SLOT[k]] = k; res = 'ok'
            else: st['worn'].pop(data.get('slot'), None); res = 'ok'
            body = view(); body.update({'result': res})
        await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body, ensure_ascii=False))
    await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
    await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
    await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
    await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("()=>document.querySelector('[data-tab=cos]').click()"); await pg.wait_for_timeout(500)
    ok(await pg.evaluate("()=>document.querySelectorAll('.cos').length") == 10, f'{tag} 꾸미기 창에 파츠 10종')
    ok('맛동산 2개' in await pg.evaluate("()=>document.getElementById('main').textContent"), f'{tag} 내 맛동산 잔액 표시')
    ok('보유 효과' in await pg.evaluate("()=>document.getElementById('main').textContent"), f'{tag} 파츠마다 보유 효과(골드) 안내')
    await pg.evaluate("()=>document.querySelector('[data-do=cosbuy][data-key=crown]').click()"); await pg.wait_for_timeout(700)
    ok(st['buys'] == 1 and st['md'] == 1, f'{tag} 사면 맛동산 1개 차감(서버 {st})')
    ok(await pg.evaluate("()=>document.querySelector('.cos.on .cnm')&&document.querySelector('.cos.on .cnm').textContent.includes('왕관')"), f'{tag} 산 파츠가 바로 입는 중으로')
    ok(await pg.evaluate("()=>FIELD.debug.E.parts.map(x=>x.key).join()") == 'crown', f'{tag} 움직이는 병아리에 왕관 파츠 반영')
    await pg.evaluate("()=>document.querySelector('[data-do=cosbuy][data-key=cape]').click()"); await pg.wait_for_timeout(700)
    ok(st['md'] == 0 and await pg.evaluate("()=>FIELD.debug.E.parts.map(x=>x.key).join()") == 'cape,crown', f'{tag} 두 번째 구매 → 슬롯이 다르면 같이 입는다(등+머리)')
    await pg.evaluate("()=>document.querySelector('[data-do=cosbuy][data-key=wizard]').click()"); await pg.wait_for_timeout(700)
    ok(st['buys'] == 2 and 'wizard' not in st['own'], f'{tag} 맛동산이 없으면 못 산다')
    await pg.wait_for_timeout(1200)
    ok(await pg.evaluate("()=>FIELD.debug.E.skinPath===null"), f'{tag} 통짜 스킨은 안 쓴다(파츠는 기본 병아리 위에)')
    await pg.evaluate("()=>document.querySelector('[data-do=cosequip][data-slot=head]').click()"); await pg.wait_for_timeout(600)
    ok('head' not in st['worn'] and await pg.evaluate("()=>FIELD.debug.E.parts.map(x=>x.key).join()") == 'cape', f'{tag} 머리 파츠만 벗기')
    ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,w:innerWidth})")
    ok(ov['sw'] <= ov['w'] + 1, f'{tag} 가로 넘침 없음 {ov}')
    ok(not errs, f'{tag} 페이지 오류 0 {errs[:2]}'); await pg.close()
async def main(port):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        await run(b, port, {'width': 1280, 'height': 800}, 'PC')
        await run(b, port, {'width': 390, 'height': 780}, '폰')
        await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
