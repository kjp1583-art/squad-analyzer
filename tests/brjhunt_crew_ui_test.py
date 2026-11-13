# -*- coding: utf-8 -*-
"""🐥 동료 창(tabCrew) 시험 — 카드·파티 칸에 SD 그림, 고유 액티브·패시브 설명, 필드에 파티 동료가 나온다.
  가짜 서버 = tests/fixtures/brj_view.json(카드마다 sk 포함). 사용: python3.13 tests/brjhunt_crew_ui_test.py"""
import asyncio, json, os, subprocess, sys, time, socket
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
CHROME = next((p for p in ("/opt/pw-browsers/chromium-1243/chrome-linux64/chrome", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome") if os.path.exists(p)), None)
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
VIEW = open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8').read()
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
async def run(vp, tag, port, shot=None):
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
        await pg.evaluate("()=>document.querySelector('#nav button[data-tab=\"crew\"]').click()"); await pg.wait_for_timeout(600)
        m = await pg.evaluate("""()=>{const w=document.getElementById('main');const cards=[...w.querySelectorAll('button.cd')];
          return {cards:cards.length, sd:cards.filter(c=>c.querySelector('svg.sd')).length, act:cards.filter(c=>/⚡/.test(c.textContent)).length, pas:cards.filter(c=>/🔰/.test(c.textContent)).length,
                  slots:[...w.querySelectorAll('.slot')].filter(s=>s.querySelector('svg.sd')).length, rows:w.querySelectorAll('.crewrow').length,
                  overflow:w.scrollWidth>w.clientWidth+2, txt:w.textContent.includes('파티 고유 스킬')&&w.textContent.includes('패시브 합계')}}""")
        ok(m['cards'] >= 4 and m['sd'] == m['cards'], f'{tag}: 동료 카드마다 SD 그림 ({m["sd"]}/{m["cards"]})')
        ok(m['act'] == m['cards'] and m['pas'] == m['cards'], f'{tag}: 카드마다 고유 액티브(⚡)·패시브(🔰) 설명')
        ok(m['slots'] == 3 and m['rows'] == 3 and m['txt'], f'{tag}: 파티 칸 3개에 SD 그림 · 파티 고유 스킬 목록 3줄 · 패시브 합계')
        ok(not m['overflow'], f'{tag}: 가로로 넘치지 않음')
        f = await pg.evaluate("()=>{const s=window.__bt?window.__bt.party:-1;return s}")
        ok(f == 3, f'{tag}: 필드 파티 동료 3명 ({f})')
        if shot: await pg.screenshot(path=shot)
        ok(not errs, f'{tag}: 페이지 오류 0 {errs[:2]}')
        await b.close()
async def main():
    port = free_port(); srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        await run((1280, 800), 'PC', port, '/tmp/claude-0/crew_pc.png'); await run((390, 800), '폰', port, '/tmp/claude-0/crew_phone.png')
    finally: srv.terminate()
    print('ALL PASS' if not fails else f'FAIL {len(fails)}'); return 1 if fails else 0
sys.exit(asyncio.run(main()))
