# -*- coding: utf-8 -*-
"""🌌 세계 확장 시험 — 30스테이지가 한 바퀴, 바퀴마다 색 테마(황혼·네온·설원·심연·황금·혈월)로 배경·몬스터가 달라진다. 사용: python3.13 tests/brjhunt_ring_test.py (playwright 없으면 SKIP)"""
import asyncio, copy, io, json, os, socket, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
try:
    from playwright.async_api import async_playwright
    from PIL import Image
except Exception:
    print('SKIP playwright/PIL 없음'); sys.exit(0)
CHROME = next((p for p in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium/chrome-linux/chrome') if os.path.exists(p)), None)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
V0 = json.load(open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8'))
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def avg(png):
    im = Image.open(io.BytesIO(png)).convert('RGB').resize((1, 1), Image.BOX); return im.getpixel((0, 0))
async def main(port):
    THEMES = {3: ('', 0), 33: ('황혼', 1), 63: ('네온', 2), 93: ('설원', 3), 123: ('심연', 4), 153: ('황금', 5), 183: ('혈월', 6), 213: ('황혼', 7)}
    cols = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        for st, (th, ring) in THEMES.items():
            pg = await (await b.new_context(viewport={'width': 760, 'height': 520})).new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            V = copy.deepcopy(V0); V['view']['stage'] = st; V['view']['region'] = ''
            def mk(V):
              async def api(route, *_a):
                r = route.request
                if r.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
                await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(V))
              return api
            await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', mk(V))
            await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
            await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
            await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(3500)
            info = await pg.evaluate("FIELD.ringInfo()")
            ok(info['theme'] == th and info['ring'] == (st - 1) // 30, f'스테이지 {st}: 바퀴 {info["ring"]} · 테마 「{info["theme"]}」')
            cols[st] = avg(await pg.screenshot(clip={'x': 0, 'y': 120, 'width': 560, 'height': 200}))
            ok(not errs, f'스테이지 {st}: 페이지 오류 0 {errs[:1]}'); await pg.close()
        await b.close()
    d = lambda a, c: sum(abs(x - y) for x, y in zip(a, c))
    for st in (33, 63, 93, 123, 153, 183):
        ok(d(cols[st], cols[3]) > 25, f'스테이지 {st} 배경 색이 첫 바퀴와 눈에 띄게 다르다(차이 {d(cols[st], cols[3])})')
    ok(d(cols[33], cols[63]) > 25 and d(cols[63], cols[123]) > 25, '바퀴 테마끼리도 서로 다르다')
    ok(d(cols[213], cols[33]) < 40, '7번째 바퀴는 첫 테마(황혼)로 되돌아온다(6테마 순환)')
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
