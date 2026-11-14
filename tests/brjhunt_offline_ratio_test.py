# -*- coding: utf-8 -*-
"""🪙 온라인은 직접 획득 · 오프라인은 일부만 수령(2026-11-14 사장님) — 수령 칸 계산(pendNow)이 서버 비율(off_ratio)을 쓰고,
직접 사냥 중(사냥 보고가 받아들여진 뒤 90초)에는 시간이 흘러도 안 늘어난다. 사용: python3.13 tests/brjhunt_offline_ratio_test.py"""
import asyncio, copy, json, os, socket, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
CHROME = next((p for p in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium/chrome-linux/chrome') if os.path.exists(p)), None)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
V0 = json.load(open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8'))
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
async def main(port):
    V = copy.deepcopy(V0); v = V['view']; v.update(hours=4.0, rate=100, boost=1, cap_h=12, off_ratio=0.5)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width': 900, 'height': 700})).new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route, *_a):
            r = route.request
            if r.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(V))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        r = await pg.evaluate("()=>{V.hours=4;V.rate=100;V.boost=1;V.cap_h=12;V.off_ratio=0.5;FETCHED=Date.now();LAST_OK=0;const a=pendNow();FETCHED=Date.now()-2*3600e3;const off2=pendNow();LAST_OK=Date.now();const on2=pendNow();LAST_OK=0;V.off_ratio=1;FETCHED=Date.now();const full=pendNow();return {a,off2,on2,full};}")
        ok(r['a'] == 300, f'오프라인 4시간 × 50% + 부스트 1시간 = 100×(2+1) = 300 (실제 {r["a"]})')
        ok(r['off2'] == 400, f'오프라인이면 흐른 2시간도 더해진다: 100×((4+2)×0.5+1) = 400 (실제 {r["off2"]})')
        ok(r['on2'] == 300, f'직접 사냥 중(온라인)이면 시간이 흘러도 안 늘어난다 = 300 (실제 {r["on2"]})')
        ok(r['full'] == 500, f'비율 1.0(옛 서버)이면 예전과 같다: 100×(4+1) = 500 (실제 {r["full"]})')
        ok(await pg.evaluate("()=>!document.hidden&&typeof isOnline==='function'&&isOnline()===false"), '보고가 없으면 오프라인')
        txt = await pg.evaluate("()=>{V.off_ratio=0.5;V.hours=4;render();const t=document.querySelector('[data-tab=hunt]');t&&t.click();return document.getElementById('main').textContent}")
        ok('오프라인 동안 쌓인 골드' in txt and '50%' in txt, '사냥 창에 「오프라인 동안 쌓인 골드」와 비율(50%) 안내')
        ok(not errs, f'페이지 오류 0 {errs[:2]}'); await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
