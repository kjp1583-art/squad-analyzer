#!/usr/bin/env python3
"""CG 가 뜬 뒤 2초 동안은 탭·Enter 로 안 넘어간다(막 누르다 지나치는 것 방지). 사용: python3 tests/novel_cglock_test.py"""
import asyncio, subprocess, sys, os, time
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PORT = 8798; FAILS = []
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium')
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:200] if x and not c else ''))
    if not c: FAILS.append(n)
async def main():
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=CHROME)
            ctx = await b.new_context(viewport={'width': 412, 'height': 860}); pg = await ctx.new_page()
            await pg.goto('http://localhost:%d/novel.html' % PORT)   # ?fast 없음 — 잠금이 켜진 실제 모드
            await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=20000)
            await pg.fill('#nickIn', '민준'); await pg.click('#tNew'); await pg.wait_for_function("__novel.mode().ws!=='title'")
            for _ in range(4000):
                m = await pg.evaluate("__novel.mode()")
                if m['ws'] == 'cg': break
                if m['ws'] == 'line': await pg.evaluate("__novel.advance()")
                elif m['ws'] == 'choice': await pg.evaluate("__novel.choose(0)")
                await pg.wait_for_timeout(1)
            ws = lambda: pg.evaluate("__novel.mode().ws")
            check('CG 가 나옴', await ws() == 'cg')
            tap = "()=>{const b=document.getElementById('cg');const ev=(t)=>b.dispatchEvent(new PointerEvent(t,{pointerId:7,clientX:200,clientY:300,bubbles:true,pointerType:'touch'}));ev('pointerdown');ev('pointerup')}"
            for _ in range(5): await pg.evaluate(tap); await pg.wait_for_timeout(120)
            await pg.keyboard.press('Enter'); await pg.keyboard.press(' ')
            await pg.wait_for_timeout(700)
            check('뜬 직후 막 눌러도 안 넘어감', await ws() == 'cg')
            check('안내 문구', '살펴' in await pg.evaluate("document.getElementById('cgHint').textContent"))
            await pg.wait_for_timeout(1600)
            check('2초 뒤 문구가 원래대로', '살펴' not in await pg.evaluate("document.getElementById('cgHint').textContent"))
            await pg.evaluate(tap); await pg.wait_for_timeout(1200)
            check('2초 뒤에는 탭으로 넘어감', await ws() != 'cg', await ws())
            await b.close()
    finally:
        sp.terminate()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
