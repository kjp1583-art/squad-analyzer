# -*- coding: utf-8 -*-
"""👗 웹 브장신 키우기 꾸미기(스킨) 맛동산 판매 시험 — 꾸미기 창에서 사고(확인 창) 입고 벗기, 사냥터 병아리·얼굴에 반영, 맛동산이 모자라면 못 산다, 폰 가로 넘침 0.
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
    st = {'md': 2, 'own': set(), 'on': '', 'buys': 0}
    def view():
        v = json.loads(json.dumps(VIEW)); C = v['view']['cos']; C['md'] = st['md']; C['on'] = st['on']
        for s in C['skins']: s['owned'] = s['key'] in st['own']; s['on'] = s['key'] == st['on']
        return v
    pg = await (await b.new_context(viewport=vp)).new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    async def api(route):
        req = route.request; path = req.url.split('bot-hosting.cloud')[1]
        if req.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
        body = view()
        if path == '/brj/cos_buy':
            k = json.loads(req.post_data or '{}').get('key')
            if k in st['own']: res = 'owned'
            elif st['md'] < 1: res = 'short'
            else: st['md'] -= 1; st['own'].add(k); st['on'] = k; st['buys'] += 1; res = 'ok'
            body = view(); body.update({'result': res})
        elif path == '/brj/cos_equip':
            k = json.loads(req.post_data or '{}').get('key') or ''
            if k and k not in st['own']: res = 'not_owned'
            else: st['on'] = k; res = 'ok'
            body = view(); body.update({'result': res})
        await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body, ensure_ascii=False))
    await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
    await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
    await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
    await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("()=>document.querySelector('[data-tab=cos]').click()"); await pg.wait_for_timeout(500)
    ok(await pg.evaluate("()=>document.querySelectorAll('.cos').length") == 7, f'{tag} 꾸미기 창에 스킨 7종')
    ok('맛동산 2개' in await pg.evaluate("()=>document.getElementById('main').textContent"), f'{tag} 내 맛동산 잔액 표시')
    await pg.evaluate("()=>document.querySelector('[data-do=cosbuy][data-key=sg]').click()"); await pg.wait_for_timeout(700)
    ok(st['buys'] == 1 and st['md'] == 1, f'{tag} 사면 맛동산 1개 차감(서버 {st})')
    ok(await pg.evaluate("()=>document.querySelector('.cos.on .cnm')&&document.querySelector('.cos.on .cnm').textContent.includes('별 수호자')"), f'{tag} 산 스킨이 바로 입는 중으로')
    ok(await pg.evaluate("()=>FIELD.debug.E.skinPath==='img/brjang/skins/sg/front.png'"), f'{tag} 사냥터 병아리에 스킨 반영')
    ok('skins/sg/front.png' in (await pg.evaluate("()=>document.getElementById('avImg').getAttribute('src')")), f'{tag} 왼쪽 위 얼굴도 반영')
    await pg.evaluate("()=>document.querySelector('[data-do=cosbuy][data-key=pp]').click()"); await pg.wait_for_timeout(700)
    ok(st['md'] == 0 and 'pp' in st['own'], f'{tag} 두 번째 구매 → 맛동산 0')
    await pg.evaluate("()=>document.querySelector('[data-do=cosbuy][data-key=tf]').click()"); await pg.wait_for_timeout(700)
    ok(st['buys'] == 2 and 'tf' not in st['own'], f'{tag} 맛동산이 없으면 못 산다')
    await pg.evaluate("()=>document.querySelector('[data-do=cosequip][data-key=sg]').click()"); await pg.wait_for_timeout(600)
    ok(st['on'] == 'sg', f'{tag} 가진 스킨으로 갈아입기')
    await pg.evaluate("()=>document.querySelector('[data-do=cosequip][data-key=\"\"]').click()"); await pg.wait_for_timeout(600)
    ok(st['on'] == '' and await pg.evaluate("()=>FIELD.debug.E.skinPath===null"), f'{tag} 원래 모습으로 — 사냥터도 기본 병아리')
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
