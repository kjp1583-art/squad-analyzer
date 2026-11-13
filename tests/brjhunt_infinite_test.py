# -*- coding: utf-8 -*-
"""♾ 브장신 키우기 「무한 성장」 화면 시험 — 환생 UI 는 없고, 이정표·무한 단련·내전 상자·시즌 순위가 한 창에 있다.
  tests/fixtures/brj_view.json 을 바탕으로 가짜 API 를 돌려준다(요청 길·본문을 기록). 사용: python3 tests/brjhunt_infinite_test.py
  (playwright 가 있는 파이썬 · 크롬은 /opt/pw-browsers 것. 없으면 SKIP)"""
import asyncio, json, os, subprocess, sys, time, socket, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
CHROME = os.environ.get('CHROME') or next((p for p in ("/opt/pw-browsers/chromium-1243/chrome-linux64/chrome", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome") if os.path.exists(p)), None)
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
BASE = json.load(open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8'))
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
def make(stage=12, best=12, unlocked=False, pending=1, legacy=False, name='<img src=x onerror=window.__xss=1>'):
    j = copy.deepcopy(BASE); v = j['view']; v['stage'] = stage; v['max_stage'] = 9999; v['name'] = '유저1'
    v['inf']['season']['no'] = 1; inf = v['inf']; inf['best'] = best; inf['stage'] = stage; inf['ms']['pending'] = pending; inf['ms']['next_at'] = (best // 10 + 1) * 10
    inf['train'].update(unlocked=unlocked, afford=unlocked, lv=7 if unlocked else 0, cost=123456789012345678)
    inf['legacy'] = {'pct': 17.2 if legacy else 0.0, 'had': legacy}
    return j
async def run(vp, tag, port, scenario):
    calls = []
    j = scenario
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': vp[0], 'height': vp[1]}, has_touch=(vp[0] < 700)); pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            req = route.request
            if req.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            path = req.url.split('.cloud', 1)[1].split('?')[0]
            body = json.loads(req.post_data or '{}') if req.post_data else {}
            calls.append((path, body))
            out = copy.deepcopy(j)
            if path == '/brj/inf_claim': out.update(n=1, got={'feast': 5, 'stone': 3, 'ticket': 0})
            if path == '/brj/inf_train': out.update(bought=body.get('n', 1), spent=1, lv=8)
            if path == '/brj/rank': out = {'ok': True, 'season': 1, 'days_left': 20, 'total': 2, 'me': 2, 'rows': [{'rank': 1, 'name': '<b>x</b>', 'ms': 3, 'best_stage': 40, 'me': False}, {'rank': 2, 'name': '유저1', 'ms': 1, 'best_stage': 12, 'me': True}]}
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(out, ensure_ascii=False))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        nav = await pg.evaluate("()=>[...document.querySelectorAll('#nav button')].map(b=>b.dataset.tab+':'+b.textContent.trim())")
        ok(any(x.startswith('inf:') and '무한' in x for x in nav) and not any('pres' in x or '환생' in x for x in nav), f'{tag}: 메뉴에 「무한」이 있고 「환생」은 없다 {nav}')
        if vp[0] < 700: await pg.keyboard.press('Escape')
        await pg.locator('#nav button[data-tab="inf"]').click(); await pg.wait_for_timeout(500)
        t = (await pg.inner_text('#main')).replace('\n', ' ')
        ok('이정표' in t and '무한 단련' in t and '시즌 1' in t and '끝없는 성장' in t and '환생하기' not in t, f'{tag}: 이정표·무한 단련·시즌이 보이고 「환생하기」는 없다')
        ok(await pg.locator('[data-do=prestige],[data-do=prestigeask],[data-do=prestigebuy]').count() == 0, f'{tag}: 환생 버튼 0개')
        ok(await pg.locator('#main img[src=x]').count() == 0 and await pg.evaluate('window.__xss') is None, f'{tag}: 서버 문자열 XSS 없음')
        ok(not await pg.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+2"), f'{tag}: 가로 스크롤 없음')
        tr_dis = await pg.locator('[data-do=infbuy]').first.is_disabled()
        unl = j['view']['inf']['train']['unlocked']
        ok(tr_dis == (not unl), f'{tag}: 단련 버튼은 스테이지 30 전엔 꺼지고 그 뒤엔 켜진다 (잠김={not unl})')
        pend = j['view']['inf']['ms']['pending']
        ok(await pg.locator('[data-do=infclaim]').is_disabled() == (pend <= 0), f'{tag}: 이정표 버튼은 받을 게 있을 때만 켜진다 (대기 {pend})')
        if pend > 0:
            n0 = len(calls); await pg.locator('[data-do=infclaim]').click(); await pg.wait_for_timeout(500)
            ok(len(calls) > n0 and calls[-1][0] in ('/brj/inf_claim', '/brj/idle') or any(c[0] == '/brj/inf_claim' for c in calls[n0:]), f'{tag}: 이정표 받기 → /brj/inf_claim')
        if unl:
            await pg.locator('[data-do=infbuy][data-n="10"]').click(); await pg.wait_for_timeout(500)
            hit = [c for c in calls if c[0] == '/brj/inf_train']
            ok(hit and hit[-1][1].get('n') == 10, f'{tag}: 단련 10레벨 → n=10 {hit[-1:] }')
        await pg.locator('[data-do=rank]').click(); await pg.wait_for_timeout(400)
        t2 = await pg.inner_text('#main')
        ok('이정표' in t2 and '환생하기' not in t2 and '<b>x</b>' in t2 and '최고 스테이지' in t2, f'{tag}: 순위표는 이정표·최고 스테이지 열(서버 이름은 글자 그대로)')
        ok(not errs, f'{tag}: 페이지 오류 0 {errs[:2]}')
        await b.close()
async def main():
    port = free_port(); srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        await run((1280, 800), 'PC·초반', port, make())
        await run((390, 800), '폰·초반', port, make())
        await run((390, 800), '폰·스테이지 30+·옛 환생', port, make(stage=34, best=34, unlocked=True, pending=3, legacy=True))
        await run((390, 800), '폰·깊은 곳(5000)', port, make(stage=5000, best=5000, unlocked=True, pending=500))
    finally: srv.terminate()
    print('ALL PASS' if not fails else f'FAIL {len(fails)}'); return 1 if fails else 0
sys.exit(asyncio.run(main()))
