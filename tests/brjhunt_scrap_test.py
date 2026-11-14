# -*- coding: utf-8 -*-
"""🗑 가방 분해 시험 — 「▼ 장착보다 낮은 것 분해」(등급 무관) · 아이템마다 ♻ 분해 · 유니크 이상이 섞이면 확인 창 · 잠금은 빠진다.
사용: python3.13 tests/brjhunt_scrap_test.py  (playwright 없으면 SKIP)"""
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
    inv = VIEW['view']['loot']['inv']
    # 시험용 가방: 낮은 레전드 1개 + 낮은 레어 1개 + 잠긴 낮은 에픽 1개
    inv[0].update(rar=4, diff=-3.0, lock=False); inv[1].update(rar=1, diff=-1.0, lock=False); inv[2].update(rar=3, diff=-2.0, lock=True)
    want_worse = [x for x in inv if not x['on'] and not x['lock'] and x['diff'] < 0]
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width': 900, 'height': 700})).new_page(); errs = []; reqs = []; dialogs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def on_dialog(d): dialogs.append(d.message); await d.accept()
        pg.on('dialog', lambda d: asyncio.ensure_future(on_dialog(d)))
        async def api(route):
            r = route.request
            if r.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            body = dict(VIEW)
            if '/brj/loot_scrap' in r.url: reqs.append(json.loads(r.post_data or '{}')); body = dict(VIEW, result='ok', n=len(want_worse), gold=100, stone=1)
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("()=>document.querySelector('[data-tab=gear]').click()"); await pg.wait_for_timeout(500)
        txt = await pg.evaluate("()=>document.querySelector('[data-do=lootscrap][data-mode=worse]').textContent")
        ok(f'({len(want_worse)}개)' in txt, f'「장착보다 낮은 것 분해」 버튼에 개수 표시: {txt.strip()}')
        ok(await pg.evaluate("()=>document.querySelectorAll('[data-do=lootscrap][data-id]').length") == len([x for x in inv if not x['on'] and not x['lock']]), '잠그지 않은 아이템마다 ♻ 분해 버튼(잠긴 건 없음)')
        await pg.evaluate("()=>document.querySelector('[data-do=lootscrap][data-mode=worse]').click()"); await pg.wait_for_timeout(600)
        ok(reqs and reqs[-1].get('mode') == 'worse', f'요청이 mode=worse 로 간다 {reqs[-1:]}')
        ok(any('유니크 이상' in m for m in dialogs), f'레전드가 섞이면 확인 창이 뜬다 {dialogs[:1]}')
        n_before = len(reqs); dialogs.clear()
        await pg.evaluate("()=>document.querySelector('[data-do=lootscrap][data-rar=\"1\"]').click()"); await pg.wait_for_timeout(500)
        ok(len(reqs) == n_before + 1 and reqs[-1].get('max_rar') == 1, '레어 이하 분해는 기존대로(max_rar=1)')
        rid = want_worse[1]['id']
        await pg.evaluate("(id)=>document.querySelector('[data-do=lootscrap][data-id=\"'+id+'\"]').click()", rid); await pg.wait_for_timeout(500)
        ok(reqs[-1].get('ids') == [rid], '한 개 분해는 ids 로 간다')
        ok(not errs, f'페이지 오류 0 {errs[:2]}')
        await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
