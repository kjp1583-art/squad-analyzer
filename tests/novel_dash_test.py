#!/usr/bin/env python3
"""novel_dash.html 시험(Playwright, /nv/dash 모의). 사용: python3 tests/novel_dash_test.py [--shots DIR]"""
import asyncio, os, sys, json, time, random
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
API = 'https://hth3thmujs.apps.bot-hosting.cloud'
URL = 'file://' + os.path.join(ROOT, 'novel_dash.html')
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)
TOKEN = json.dumps({'id': '1', 'name': 'x', 'token': 'T' * 40, 'exp': int(time.time() * 1000) + 86400000})

def fixture():
    random.seed(7); now = int(time.time()); nch = 8; P = []
    for i in range(45):
        ch = min(nch - 1, int(random.expovariate(0.45))); te = 1 if i % 11 == 0 and ch >= 6 else 0
        end = (['A'] if ch >= 7 and i % 3 else []) + (['T'] if te else [])
        P.append({'k': '%08x' % (i * 99991), 'name': '가상플레이어%02d' % i, 'seen': now - random.randint(30, 9 * 86400), 'first': now - 10 * 86400, 'ch': ch, 'line': ch * 100, 'clues': min(12, ch + random.randint(0, 3)), 'nc': 12,
                  'endings': end, 'te': te, 'play': random.randint(300, 14000), 'old': i == 44, 'cur': {'ch': max(0, ch - random.randint(0, 1)), 'line': 5, 'clues': 3, 'flags': {}, 'ev': 'tick'}})
    cur = [p for p in P if not p['old']]
    funnel = [sum(1 for p in cur if p['ch'] >= i) for i in range(nch)]
    drop = [0] * nch
    for p in cur:
        if not p['endings'] and now - p['seen'] > 3 * 86400: drop[p['ch']] += 1
    fin = sum(1 for p in cur if p['endings'])
    return {'ok': True, 'now': now, 'on': True, 'meta': {'sv': '9:8', 'nch': nch, 'nc': 12},
            'agg': {'players': 45, 'current': 44, 'old': 1, 'active24h': 6, 'finished': fin, 'completion': round(fin / 44, 3), 'true_enders': sum(p['te'] for p in cur), 'avg_play': 6200,
                    'funnel': funnel, 'endings': {'A': 7, 'T': 3}, 'dropout': drop,
                    'choices': [{'pc': 120, 'n': 30, 'opts': [{'i': 0, 'n': 21, 't': '문을 연다'}, {'i': 1, 'n': 9, 't': '창문을 본다 <img src=x onerror=alert(1)>'}]},
                                {'pc': 300, 'n': 12, 'opts': [{'i': 0, 'n': 5, 't': ''}, {'i': 1, 'n': 4, 't': '거절한다'}, {'i': 2, 'n': 3, 't': '따라간다'}]}]},
            'players': P}

async def run(b, w, h, status, body, name, login=True):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, accept_downloads=True); hits = []
    async def route(r):
        u = r.request.url
        if u.startswith(API): hits.append(u); await r.fulfill(status=status, content_type='application/json', body=json.dumps(body)); return
        if u.startswith('file://'): await r.continue_(); return
        await r.abort()
    await ctx.route('**/*', route)
    if login: await ctx.add_init_script("localStorage.setItem('sgg_dc'," + json.dumps(TOKEN) + ")")
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: errs.append('dialog'))
    await pg.goto(URL); await pg.wait_for_timeout(500)
    return ctx, pg, hits, errs

async def noscroll(pg): return await pg.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        fx = fixture()
        for w, h in ((1280, 900), (360, 780)):
            ctx, pg, hits, errs = await run(b, w, h, 200, fx, 'ok')
            check(f'{w}px: 요약 카드 5개·표 45행', await pg.locator('#cards .panel').count() == 5 and await pg.locator('#tbl tbody tr').count() == 45)
            check(f'{w}px: 페이지 가로 스크롤 없음', await noscroll(pg))
            check(f'{w}px: 장별 막대·엔딩·갈림길 표시', await pg.locator('#funnel li').count() == 8 and await pg.locator('#ends li').count() == 2 and await pg.locator('#choices .q').count() == 2)
            check(f'{w}px: 어디서 그만두나 문구', '사이에서 가장 많이 빠져요' in await pg.inner_text('#quit'))
            check(f'{w}px: 값이 HTML 로 해석되지 않는다', await pg.locator('#choices img').count() == 0 and not errs, errs)
            if SHOTS: await pg.screenshot(path=f'{SHOTS}/dash_{w}.png', full_page=True)
            if w == 1280:
                await pg.fill('#q', '플레이어07'); check('검색', await pg.locator('#tbl tbody tr').count() == 1)
                await pg.fill('#q', '')
                await pg.click('th button[data-k=play]'); a = await pg.evaluate("[...document.querySelectorAll('#tbl tbody tr td:nth-child(6)')].map(e=>e.textContent)")
                await pg.click('th button[data-k=name]'); first = await pg.inner_text('#tbl tbody tr:first-child td:first-child')
                check('정렬(이름 오름차순)', first.startswith('가상플레이어00'), first)
                await pg.click('th button[data-k=ch]'); await pg.click('th button[data-k=ch]')
                check('정렬 표시(aria-sort)', await pg.locator('th[aria-sort]').count() == 1)
                n0 = len(hits); await pg.click('#bRef'); await pg.wait_for_timeout(300); check('수동 새로고침', len(hits) == n0 + 1)
                async with pg.expect_download() as d: await pg.click('#bCsv')
                dl = await d.value; path = await dl.path(); txt = open(path, encoding='utf-8-sig').read().splitlines()
                check('CSV: 머리글+45행·UTF-8 BOM', len(txt) == 46 and txt[0].startswith('이름,'), len(txt))
                try:
                    await pg.clock.install(); await pg.reload(); await pg.wait_for_timeout(300); n0 = len(hits); await pg.clock.fast_forward(61000); await pg.wait_for_timeout(300)
                    check('60초 자동 새로고침', len(hits) > n0)
                except Exception as e: check('60초 자동 새로고침', False, e)
            await ctx.close()
        # 403
        ctx, pg, hits, errs = await run(b, 360, 700, 403, {'ok': False, 'code': 'owner_only'}, '403')
        t = await pg.inner_text('#state'); check('403: 운영진 전용 안내·본문 숨김', '운영진 전용' in t and await pg.locator('#main').is_hidden())
        if SHOTS: await pg.screenshot(path=f'{SHOTS}/dash_403_360.png')
        await ctx.close()
        # 로그인 없음 / 장애
        ctx, pg, hits, errs = await run(b, 360, 700, 200, {}, 'nologin', login=False)
        check('미로그인: 로그인 버튼·봇 호출 없음', await pg.locator('#state button.dc').count() == 1 and not hits)
        await ctx.close()
        ctx, pg, hits, errs = await run(b, 360, 700, 503, {'ok': False}, '503')
        check('장애: 다시 시도 버튼', await pg.locator('#state button').count() == 1 and '불러오지 못했어요' in await pg.inner_text('#state'))
        await ctx.close()
        # 빈 데이터
        empty = {'ok': True, 'now': int(time.time()), 'on': True, 'meta': {'sv': '', 'nch': 0, 'nc': 0}, 'agg': {'players': 0, 'current': 0, 'old': 0, 'active24h': 0, 'finished': 0, 'completion': 0, 'true_enders': 0, 'avg_play': 0, 'funnel': [0], 'endings': {}, 'dropout': [0], 'choices': []}, 'players': []}
        ctx, pg, hits, errs = await run(b, 360, 700, 200, empty, 'empty')
        check('빈 데이터에도 오류 없음', not errs and await pg.locator('#main').is_visible(), errs)
        await ctx.close(); await b.close()
asyncio.run(main())
print('\n실패 %d건' % len(FAILS)); sys.exit(1 if FAILS else 0)
