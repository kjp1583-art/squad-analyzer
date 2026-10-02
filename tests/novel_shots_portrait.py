#!/usr/bin/env python3
"""초상화 배치 스크린샷. 사용: python3 tests/novel_shots_portrait.py OUTDIR TAG"""
import asyncio, subprocess, sys, os, time, shutil
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT, TAG = sys.argv[1], sys.argv[2]; PORT = 8793
async def main():
    shutil.copy(os.path.join(ROOT, 'novel.html'), os.path.join(ROOT, 'novel_test.html'))
    subprocess.run([sys.executable, os.path.join(ROOT, 'tooling/novel_build.py'), '--src', os.path.join(ROOT, 'tests/novel_test_story.txt'), '--out', os.path.join(ROOT, 'novel_test.html')], capture_output=True)
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            for w, h in ((360, 740), (1280, 800)):
                pg = await (await b.new_context(viewport={'width': w, 'height': h})).new_page()
                await pg.goto('http://localhost:%d/novel_test.html?fast=1' % PORT)
                await pg.wait_for_function("!document.getElementById('tNew').disabled"); await pg.click('#tNew')
                await pg.wait_for_function("__novel.mode().ws==='line'")
                async def go(name, show, text):
                    await pg.evaluate("""([show,text])=>{const S=__novel.ST();S.show=show.map(id=>({id,f:0}));
                      document.getElementById('chars').innerHTML='';
                      const op={o:'say',s:show[0]==='seungwoo'?'승우':'태용',t:text};
                      __novel.STORY.ops.splice(__novel.ST().pc,0,op);__novel.run()}""", [show, text])
                    await pg.wait_for_timeout(700); await pg.screenshot(path=os.path.join(OUT, '%s_%d_%s.png' % (TAG, w, name)))
                short = '짧은 대사입니다.'; long = '긴 대사입니다. ' * 14
                await go('1_short', ['seungwoo'], short); await go('2_long', ['seungwoo', 'taeyong'], long)
                await go('3_short', ['seungwoo', 'taeyong', 'sinrin'], short); await go('3_long', ['taeyong', 'seungwoo', 'sinrin'], long)
            await b.close()
    finally:
        sp.terminate(); os.remove(os.path.join(ROOT, 'novel_test.html'))
asyncio.run(main())
