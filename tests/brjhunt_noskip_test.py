# -*- coding: utf-8 -*-
"""🚫 건너뛰기 삭제 시험(2026-11-14 「용조련사도 스킵 삭제」) — 용조련사(yongjo) 보스가 나오는 던전·클랜 보스는 「건너뛰기」 버튼이 없고 눌러도(직접 호출해도) 안 건너뛰며,
다른 보스(또뀨 등)는 예전처럼 건너뛸 수 있다. 사용: python3.13 tests/brjhunt_noskip_test.py (playwright 없으면 SKIP)"""
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
async def one(b, port, cleared, clan_boss, label, expect_skip):
    V = copy.deepcopy(V0); v = V['view']; v['dungeon']['dungeon'].update(cleared=cleared, sweep=False); v['dungeon']['key']['n'] = 3
    v['dungeon']['clan'].update(boss=clan_boss, name='보스')
    pg = await (await b.new_context(viewport={'width': 900, 'height': 700})).new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    async def api(route, *_a):
        r = route.request
        if r.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
        body = copy.deepcopy(V)
        if '/brj/dungeon' in r.url: body.update(result='win', level=cleared + 1, got={'stone': 3, 'gold': 100, 'ticket': 1})
        if '/brj/clanboss' in r.url: body.update(result='ok', dmg=123456)
        await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body))
    await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
    await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
    await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
    await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("()=>document.querySelector('[data-tab=adv]').click()"); await pg.wait_for_timeout(500)
    sel = '[data-do=dungeon]' if label.startswith('던전') else '[data-do=clanatk]'
    await pg.evaluate("(s)=>document.querySelector(s).click()", sel); await pg.wait_for_timeout(2500)
    vis = await pg.evaluate("()=>getComputedStyle(document.getElementById('skipBtn')).display")
    ok((vis != 'none') == expect_skip, f'{label}: 건너뛰기 버튼 {"보임" if vis != "none" else "없음"} (기대: {"보임" if expect_skip else "없음"})')
    await pg.evaluate("()=>{try{FIELD.skipInstance()}catch(e){}}"); await pg.wait_for_timeout(700)
    still = await pg.evaluate("()=>!!FIELD.stats().inst")
    ok(still != expect_skip, f'{label}: skipInstance() 호출 → {"건너뜀" if not still else "안 건너뜀(계속 진행)"} (기대: {"건너뜀" if expect_skip else "안 건너뜀"})')
    ok(not errs, f'{label}: 페이지 오류 0 {errs[:1]}'); await pg.close()
async def main(port):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        await one(b, port, 0, 'ddokkyu', '던전 1단계(또뀨)', True)
        await one(b, port, 2, 'ddokkyu', '던전 3단계(수문장 용조련사)', False)
        await one(b, port, 0, 'yongjo', '클랜 보스(용조련사)', False)
        await one(b, port, 0, 'ddokkyu', '클랜 보스(또뀨)', True)
        await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
