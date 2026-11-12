# -*- coding: utf-8 -*-
"""🎮 브장신 키우기 인게임 UI 시험 — 필드가 화면 전체를 쓰고, 8개 아이콘 메뉴가 필드 위 게임 창으로 열린다(우측 별개 탭 없음).
  서버 응답은 tests/fixtures/brj_view.json(봇 코드로 만든 실제 모양)을 가짜 API 로 돌려준다. 사용: python3.13 tests/brjhunt_ingame_ui_test.py
  (playwright 가 있는 파이썬 · 크롬은 /opt/pw-browsers 것을 쓴다. 없으면 SKIP)"""
import asyncio, json, os, subprocess, sys, time, socket
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
CHROME = next((p for p in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome") if os.path.exists(p)), None)
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
VIEW = open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8').read()
TABS = ['hunt', 'skill', 'crew', 'grow', 'gear', 'adv', 'pres', 'rank']
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
async def run(vp, tag, port):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': vp[0], 'height': vp[1]}, has_touch=(vp[0] < 700)); pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            if route.request.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=VIEW)
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        g = await pg.evaluate("()=>{const f=document.getElementById('fieldBox').getBoundingClientRect(),a=document.getElementById('app').getBoundingClientRect(),s=getComputedStyle(document.getElementById('sheet')).display;return {fh:f.height,ah:a.height,fw:f.width,aw:a.width,sheet:s,nav:document.querySelectorAll('#nav button').length,wopen:document.body.classList.contains('wopen')};}")
        ok(g['nav'] == 9 and g['sheet'] == 'none' and not g['wopen'], f'{tag}: 처음엔 창이 닫혀 있고 아이콘 메뉴 9개(꾸미기 포함)')
        ok(g['fw'] >= g['aw'] - 2 and g['fh'] > g['ah'] * 0.55, f'{tag}: 필드가 화면 가로 전체·세로 절반 넘게 사용 ({int(g["fw"])}x{int(g["fh"])} / {int(g["aw"])}x{int(g["ah"])})')
        for k in TABS:
            if vp[0] < 700: await pg.keyboard.press('Escape'); await pg.wait_for_timeout(150)
            await pg.locator(f'#nav button[data-tab="{k}"]').click(); await pg.wait_for_timeout(350)
            m = await pg.evaluate("()=>{const s=document.getElementById('sheet').getBoundingClientRect(),a=document.getElementById('app').getBoundingClientRect(),m=document.getElementById('main');return {inside:s.left>=-1&&s.right<=a.right+1&&s.top>=-1&&s.bottom<=a.bottom+1,over:m.scrollWidth>m.clientWidth+1,wopen:document.body.classList.contains('wopen'),txt:m.innerText.length,title:document.getElementById('wname').innerText};}")
            ok(m['wopen'] and m['inside'] and not m['over'] and m['txt'] > 20, f"{tag}: [{m['title']}] 창이 화면 안에 열리고 가로로 안 넘침 · 내용 {m['txt']}자")
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)
        ok(not await pg.evaluate("()=>document.body.classList.contains('wopen')"), f'{tag}: Esc 로 창 닫힘')
        await pg.locator('#nav button[data-tab="skill"]').click(); await pg.wait_for_timeout(200)
        await pg.locator('#wclose').click(); await pg.wait_for_timeout(200)
        ok(not await pg.evaluate("()=>document.body.classList.contains('wopen')"), f'{tag}: ✕ 버튼으로 닫힘')
        ok(not errs, f'{tag}: 페이지 오류 0 {errs[:2]}')
        await b.close()
async def main():
    port = free_port(); srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        await run((1280, 800), 'PC', port); await run((390, 800), '폰', port)
    finally: srv.terminate()
    print('ALL PASS' if not fails else f'FAIL {len(fails)}'); return 1 if fails else 0
sys.exit(asyncio.run(main()))
