#!/usr/bin/env python3
"""novel.html 로그인 게이트·진행도 기록 시험(Playwright, 봇 응답은 모의). 사용: python3 tests/novel_gate_test.py"""
import asyncio, os, sys, json, time
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
HTML = open(os.path.join(ROOT, 'novel.html'), 'rb').read()
PROD = 'https://kjp1583-art.github.io/squad-analyzer/novel.html'
API = 'https://hth3thmujs.apps.bot-hosting.cloud'
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)
TOKEN = {'id': '1', 'name': '테스트', 'token': 'T' * 40, 'exp': int(time.time() * 1000) + 5 * 86400 * 1000}

async def page(b, url, login, me=(200, {'ok': True, 'member': True, 'name': '테스트'}), served=None, offline=False):
    ctx = await b.new_context(viewport={'width': 390, 'height': 800})
    calls = []
    async def route(r):
        u = r.request.url
        if u.startswith(API):
            calls.append((r.request.method, u.split('?')[0].replace(API, ''), r.request.post_data))
            if offline: await r.abort(); return
            if '/nv/me' in u: await r.fulfill(status=me[0], content_type='application/json', body=json.dumps(me[1])); return
            await r.fulfill(status=200, content_type='application/json', body='{"ok":true}'); return
        if u.startswith('https://kjp1583-art.github.io') and u.split('?')[0].endswith('novel.html'):
            await r.fulfill(status=200, content_type='text/html; charset=utf-8', body=HTML); return
        if u.startswith('file://'): await r.continue_(); return
        await r.fulfill(status=404, body='')
    await ctx.route('**/*', route)
    if login:
        await ctx.add_init_script("try{localStorage.setItem('sgg_dc'," + json.dumps(json.dumps(TOKEN)) + ")}catch(e){}")
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(url); await pg.wait_for_function('window.__novel')
    return ctx, pg, calls, errs

async def vis(pg, sel): return await pg.evaluate("s=>{const e=document.querySelector(s);return !!e&&!e.hidden&&getComputedStyle(e).display!=='none'}", sel)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        # 1) 시험 모드(운영 도메인이 아님)
        tmp = os.path.join(ROOT, 'novel_gate_tmp.html'); open(tmp, 'wb').write(HTML)
        ctx, pg, calls, errs = await page(b, 'file://' + tmp + '?fast=1', False)
        await pg.wait_for_timeout(600)
        check('시험 모드: 배지 표시', await vis(pg, '#testBadge'))
        check('시험 모드: 게이트 없음·시작 버튼 보임', not await vis(pg, '#gate') and await vis(pg, '#tNew'))
        await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=8000)
        await pg.evaluate('window.__novel.newGame()'); await pg.wait_for_timeout(300)
        check('시험 모드: 새 게임이 시작된다', await pg.evaluate("window.__novel.mode().ws!=='title'"))
        await pg.wait_for_timeout(500)
        check('시험 모드: 봇에 아무것도 보내지 않는다', len(calls) == 0, calls)
        await pg.evaluate("document.getElementById('mSet')&&document.getElementById('mSet').click()"); await pg.evaluate('window.__novel.goTitle()'); await pg.evaluate("document.getElementById('tSet').click()")
        check('시험 모드: 설정 버튼은 시험 모드', (await pg.inner_text('#sNv')) == '시험 모드')
        check('시험 모드: 오류 없음', not errs, errs)
        await ctx.close(); os.remove(tmp)
        # 2) 운영 도메인 · 로그인 없음 (?fast=1 로도 못 건너뛴다)
        ctx, pg, calls, errs = await page(b, PROD + '?fast=1', False)
        await pg.wait_for_timeout(500)
        check('운영: 배지 없음', not await vis(pg, '#testBadge'))
        check('운영·미로그인: 안내문+로그인 버튼, 시작 버튼 숨김', await vis(pg, '#gate') and await vis(pg, '#gLogin') and not await vis(pg, '#tNew') and not await vis(pg, '#tCont'))
        await pg.evaluate('window.__novel.newGame()'); await pg.wait_for_timeout(200)
        check('운영·미로그인: newGame 직접 호출도 막힌다', await pg.evaluate("window.__novel.mode().ws==='title'"))
        check('운영·미로그인: 봇 호출 없음', len(calls) == 0)
        await ctx.close()
        # 3) 로그인 + 멤버
        ctx, pg, calls, errs = await page(b, PROD + '?fast=1', True)
        await pg.wait_for_function("window.__novel.nv.st()==='ok'", timeout=8000)
        check('운영·멤버: /nv/me 호출 후 열림', any(c[1] == '/nv/me' for c in calls) and await vis(pg, '#tNew') and not await vis(pg, '#gate'))
        await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=8000)
        await pg.evaluate('window.__novel.newGame()'); await pg.wait_for_timeout(300)
        check('운영·멤버: 새 게임 시작', await pg.evaluate("window.__novel.mode().ws!=='title'"))
        await pg.wait_for_function("window.__novel.nv.gateOk()")
        # 장 시작 보고(연타해도 간격 지킴)
        await pg.wait_for_timeout(1500)
        posts = [json.loads(c[2]) for c in calls if c[1] == '/nv/prog']
        check('운영·멤버: 장 시작에 진행도 전송', len(posts) >= 1, calls)
        if posts:
            k = posts[0]; keys = set(k)
            check('전송 항목은 정해진 것뿐', keys <= {'token', 'sv', 'ch', 'nch', 'line', 'play', 'nc', 'clues', 'flags', 'endings', 'te', 'choices', 'ev'}, keys)
            check('저장 내용·연락처 같은 칸이 없다', not ({'saves', 'slots', 'email', 'ip', 'read'} & keys))
            check('본문 4KB 이하', len(calls[-1][2] or '') < 4096)
        await pg.evaluate("document.getElementById('sNv').click()")
        txt = await pg.inner_text('#sNv'); check('설정 토글: 끔으로', txt == '끔', txt)
        n0 = len([c for c in calls if c[1] == '/nv/prog']); await pg.evaluate('window.__novel.nv.flush()'); await pg.wait_for_timeout(300)
        check('끄면 더는 보내지 않는다', len([c for c in calls if c[1] == '/nv/prog']) == n0)
        check('운영·멤버: 오류 없음', not errs, errs)
        await ctx.close()
        # 4) 멤버 아님 · 장애 · 만료 · 오프라인 + 재시도
        for name, me, off, want, btn in [('멤버 아님', (403, {'ok': False, 'code': 'not_member'}), False, 'notmember', '#gRetry'),
                                          ('봇 장애 503', (503, {'ok': False, 'code': 'upstream'}), False, 'fail', '#gRetry'),
                                          ('토큰 만료 401', (401, {'ok': False, 'code': 'auth'}), False, 'nologin', '#gLogin'),
                                          ('오프라인', (200, {}), True, 'fail', '#gRetry')]:
            ctx, pg, calls, errs = await page(b, PROD, True, me=me, offline=off)
            await pg.wait_for_function("window.__novel.nv.st()!=='checking'", timeout=12000)
            st = await pg.evaluate('window.__novel.nv.st()')
            check(f'{name}: 상태 {want}·시작 숨김·안내문·재시도/로그인 버튼', st == want and not await vis(pg, '#tNew') and await vis(pg, '#gate') and await vis(pg, btn) and len(await pg.inner_text('#gMsg')) > 10, st)
            await pg.evaluate('window.__novel.newGame()'); await pg.wait_for_timeout(150)
            check(f'{name}: 우회 호출도 막힘', await pg.evaluate("window.__novel.mode().ws==='title'"))
            await ctx.close()
        # 재시도로 열린다
        state = {'me': (403, {'ok': False, 'code': 'not_member'})}
        ctx = await b.new_context(viewport={'width': 390, 'height': 800})
        async def route(r):
            u = r.request.url
            if u.startswith(API): await r.fulfill(status=state['me'][0], content_type='application/json', body=json.dumps(state['me'][1])); return
            if u.startswith('https://kjp1583-art.github.io') and 'novel.html' in u: await r.fulfill(status=200, content_type='text/html; charset=utf-8', body=HTML); return
            await r.fulfill(status=404, body='')
        await ctx.route('**/*', route); await ctx.add_init_script("localStorage.setItem('sgg_dc'," + json.dumps(json.dumps(TOKEN)) + ")")
        pg = await ctx.new_page(); await pg.goto(PROD); await pg.wait_for_function("window.__novel&&window.__novel.nv.st()==='notmember'", timeout=8000)
        state['me'] = (200, {'ok': True, 'member': True, 'name': 'x'}); await pg.click('#gRetry')
        await pg.wait_for_function("window.__novel.nv.st()==='ok'", timeout=8000)
        check('재시도로 게이트가 열린다', await vis(pg, '#tNew') and not await vis(pg, '#gate'))
        await ctx.close(); await b.close()
asyncio.run(main())
print('\n실패 %d건' % len(FAILS)); sys.exit(1 if FAILS else 0)
