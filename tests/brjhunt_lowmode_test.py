#!/usr/bin/env python3
"""저사양 모드 회귀 시험: CPU 를 6배 느리게 해도 필드가 멎지 않고(페이지 오류 0) 게임 시간이 계속 흐르는지.
(입자 상한이 소수라 parts[소수] 가 undefined 가 되어 저사양 전환 직후 필드가 멎던 사고)
사용: CHROME=... python3.13 tests/brjhunt_lowmode_test.py"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brjhunt_test.py'), encoding='utf-8').read().split('async def main')[0]
exec(compile(src, 'brjhunt_test_helpers', 'exec'))
async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        srv = Server(); ctx, pg, errs = await new_page(b, srv, 390, 800)
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 6})
        await pg.wait_for_function('window.__bt.stats && window.__bt.stats.low===true', timeout=60000)
        t0 = await pg.evaluate('window.__bt.stats.t'); await pg.wait_for_timeout(8000); t1 = await pg.evaluate('window.__bt.stats.t')
        check('저사양 모드로 전환됨', True); check('전환 뒤에도 게임 시간이 흐른다', t1 - t0 > 2, (t0, t1)); check('페이지 오류 없음', not errs, errs)
        await b.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(run())
