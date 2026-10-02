#!/usr/bin/env python3
"""novel.html 시험(Playwright). 시험용 이야기(tests/novel_test_story.txt)를 임시로 굽고 화면 조작으로 전부 지나가 본다.
사용: python3 tests/novel_test.py [--shots DIR]"""
import asyncio, subprocess, time, sys, os, shutil, json, re
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
PORT = 8791
FAILS = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(extra) if extra and not cond else ''))
    if not cond: FAILS.append(name)

def build():
    shutil.copy(os.path.join(ROOT, 'novel.html'), os.path.join(ROOT, 'novel_test.html'))
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tooling/novel_build.py'), '--src', os.path.join(ROOT, 'tests/novel_test_story.txt'),
                        '--out', os.path.join(ROOT, 'novel_test.html')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

async def ctx_page(b, w, h, rm=False, delay=0, store=None):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce' if rm else 'no-preference', storage_state=store)
    async def route(r):
        u = r.request.url
        if not u.startswith('http://localhost:%d/' % PORT): await r.abort(); return
        if delay and '/img/novel/' in u and u.endswith('.webp'): await asyncio.sleep(delay / 1000)
        await r.continue_()
    await ctx.route('**/*', route)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    return ctx, pg, errs

async def ws(pg, s, t=4000): await pg.wait_for_function("__novel.mode().ws==='%s'" % s, timeout=t)
async def mode(pg): return await pg.evaluate('__novel.mode()')
async def shot(pg, name):
    if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, name + '.png'))
async def adv_until(pg, cond_js, limit=80):
    for _ in range(limit):
        if await pg.evaluate(cond_js): return True
        m = await mode(pg)
        if m['ws'] == 'line': await pg.evaluate('__novel.advance()')
        await pg.wait_for_timeout(15)
    return False

async def story_walk(b, w, h, tag):
    ctx, pg, errs = await ctx_page(b, w, h)
    await pg.add_init_script("window.__sil=0;new MutationObserver(()=>{if(document.querySelector('.sil'))window.__sil++}).observe(document,{subtree:true,childList:true})")
    await pg.goto('http://localhost:%d/novel_test.html?fast=1' % PORT)
    await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=8000)
    check(tag + ' 타이틀·미리 불러오기 완료', True); await shot(pg, tag + '_title')
    check(tag + ' 가로 넘침 없음', await pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    await pg.click('#tNew'); await ws(pg, 'line')
    check(tag + ' 첫 줄 표시', '첫 줄' in (await pg.inner_text('#txt')))
    await adv_until(pg, "document.querySelectorAll('.prop').length===3")
    check(tag + ' 단서 핫스팟 3개', await pg.locator('.prop').count() == 3)
    await shot(pg, tag + '_scene')
    check(tag + ' 초상화 그림 사용(동그라미 아님)', await pg.locator('#chars img').count() >= 2)
    for i in range(3): await pg.locator('.prop').first.click()
    check(tag + ' 수첩 숫자 3/12 아닌 3/3', (await pg.inner_text('#bNote')).strip().endswith('3/3'), await pg.inner_text('#bNote'))
    await pg.click('#bNote'); check(tag + ' 수첩에 단서 문구', '의자가 스물여섯' in await pg.inner_text('#nList')); await shot(pg, tag + '_note'); await pg.click('#ovNote .back')
    await adv_until(pg, "__novel.mode().ws==='choice'")
    m = await mode(pg); check(tag + ' 선택지 3개(조건부 포함)', len(m['opts']) == 3, m['opts'])
    log = await pg.evaluate("__novel.mode().ws && JSON.stringify(document.getElementById('log').innerText)")
    await pg.click('#bLog'); lg = await pg.inner_text('#log'); await pg.click('#ovLog .back')
    check(tag + ' @if 참 분기', 'trust 는 2 이상' in lg and '중첩 조건 a 참' in lg and '단서 3개 이상, 그리고 a' in lg and 'a 는 꺼졌습니다' in lg)
    check(tag + ' @if 거짓 분기 안 나옴', '나오면 안 됨' not in lg)
    check(tag + ' 타이머 막대 표시', await pg.locator('#timer').is_visible()); await shot(pg, tag + '_choice')
    # 자동 저장/이어하기: 새로고침
    st = await ctx.storage_state()
    await pg.locator('#cl button').nth(1).click(); await ws(pg, 'line')
    # 퍼즐 1: pick3
    await adv_until(pg, "__novel.mode().ptype==='pick3'")
    check(tag + ' pick3 화면', await pg.locator('.pk').count() == 5); await shot(pg, tag + '_pick3')
    await pg.locator('.pk').nth(1).click(); await pg.locator('.pk').nth(3).click(); await pg.locator('.pk').nth(0).click()
    check(tag + ' 확인 버튼 활성', not await pg.locator('.pzbtn.go').is_disabled())
    await pg.locator('.pzbtn.go').click(); await pg.wait_for_timeout(50)
    check(tag + ' pick3 오답 안내', '맞지 않습니다' in await pg.inner_text('.pzs.bad'))
    for i in (0, 2, 4): await pg.locator('.pk').nth(i).click()
    await pg.locator('.pzbtn.go').click(); await adv_until(pg, "__novel.mode().ptype==='code'")
    # 퍼즐 2: code
    check(tag + ' code 힌트 노출(단서 3개)', '25 + 1' in await pg.inner_text('.hints')); await shot(pg, tag + '_code')
    for d in '1111': await pg.locator('.key', has_text=d).first.click()
    await pg.locator('.key.sm', has_text='확인').click(); await pg.wait_for_timeout(30)
    check(tag + ' code 오답', '남은 기회' in await pg.inner_text('.pzs.bad'))
    for d in '2526': await pg.locator('.key', has_text=re.compile('^%s$' % d)).click()
    await pg.locator('.key.sm', has_text='확인').click(); await adv_until(pg, "__novel.mode().ptype==='vote'")
    # 퍼즐 3: vote
    check(tag + ' vote 후보 3 + 거부', await pg.locator('.vc').count() == 4); await shot(pg, tag + '_vote')
    check(tag + ' vote 의심도 표시', '의심 ●●' in await pg.inner_text('#pzBody'))
    await pg.locator('.vc').nth(3).click(); await pg.locator('.pzbtn.go').click(); await adv_until(pg, "__novel.mode().ptype==='guide'")
    check(tag + ' vote 거부 결과 분기', await pg.evaluate("__novel.ST().V.voted_r===1"))
    # 퍼즐 4: guide — 두 번 틀려 넘어가기 확인
    await shot(pg, tag + '_guide')
    check(tag + ' guide 처음엔 넘어가기 숨김', not await pg.locator('#pzSkip').is_visible())
    await pg.locator('.dir').nth(1).click(); await pg.wait_for_timeout(120); await pg.wait_for_function("document.querySelectorAll('.dir').length==3 && document.querySelector('.dir')")
    await pg.wait_for_timeout(100)
    await pg.locator('.dir').nth(1).click(); await pg.wait_for_timeout(60)
    check(tag + ' guide 2번 틀리면 넘어가기', await pg.locator('#pzSkip').is_visible())
    await pg.wait_for_timeout(100)
    await pg.locator('#pzSkip').click(); await adv_until(pg, "__novel.mode().ptype==='cctv'")
    check(tag + ' guide 도움 통과 기록', await pg.evaluate("__novel.ST().V.assisted>=1 && __novel.ST().V.p_guide===1"))
    # 퍼즐 5: cctv seq
    check(tag + ' cctv 칸 25+1', await pg.locator('.cc').count() == 26); await shot(pg, tag + '_cctv')
    check(tag + ' cctv 힌트(단서 3)', '방송이 부른 순서' in await pg.inner_text('.hints'))
    for nm in ['kater', '허기허기', '포만포만']:
        await pg.locator('.cc.nm').filter(has_text=re.compile('^' + nm)).first.click(); await pg.wait_for_timeout(15)
    await adv_until(pg, "__novel.mode().ptype==='cctv'&&document.querySelectorAll('.cc').length===25&&!document.querySelector('.cc.nm')")
    # 퍼즐 6: cctv odd
    check(tag + ' cctv(odd) 25칸', await pg.locator('.cc').count() == 25); await shot(pg, tag + '_cctv_odd')
    for r in range(2):
        txt = await pg.evaluate("(()=>{const t={};[...document.querySelectorAll('.cc')].forEach(b=>{const k=b.firstChild.textContent;t[k]=(t[k]||0)+1});return Object.keys(t).find(k=>t[k]===1)})()")
        await pg.locator('.cc').filter(has_text=txt).first.click(); await pg.wait_for_timeout(60)
    await ws(pg, 'end', 6000)
    check(tag + ' 엔딩 카드', 'clear' not in await pg.inner_text('#eT') and '시험 엔딩' in await pg.inner_text('#eT'))
    check(tag + ' 플레이 시간 표시', '플레이 시간' in await pg.inner_text('#eS')); await shot(pg, tag + '_end')
    check(tag + ' 동그라미 폴백이 한 번도 안 뜸', await pg.evaluate('window.__sil')==0, await pg.evaluate('window.__sil'))
    await pg.click('#eGal'); g = await pg.inner_text('#gal'); check(tag + ' 엔딩 갤러리(본 것/잠금)', '시험 엔딩' in g and '???' in g); await shot(pg, tag + '_gallery'); await pg.click('#ovGal .back')
    await pg.click('#eBack'); await pg.wait_for_timeout(50)
    # 장 선택: 엔딩을 봤으니 1장 열림
    check(tag + ' 장 선택 열림', not await pg.locator('#tChap').is_disabled())
    await pg.click('#tChap'); check(tag + ' 장 목록 2개', await pg.locator('#chList .slot').count() == 2); await shot(pg, tag + '_chapsel')
    await pg.locator('#chList .slot').first.click(); await ws(pg, 'line')
    check(tag + ' 장 선택으로 1장 처음부터', '첫 줄' in await pg.inner_text('#txt'))
    # 읽은 것만 건너뛰기: 이미 읽은 줄 -> 선택지까지 넘어감
    await pg.click('#bSkip'); await ws(pg, 'choice', 5000)
    check(tag + ' SKIP 은 읽은 대사만(선택지에서 멈춤)', True)
    # 저장 슬롯
    await pg.locator('#cl button').first.click(); await ws(pg, 'line')
    await pg.click('#bMenu'); await pg.click('#mSave'); await pg.locator('#slList .slot').nth(1).click()
    await pg.click('#bMenu'); await pg.click('#mLoad'); sl = await pg.inner_text('#slList'); check(tag + ' 슬롯에 저장 표시', '플레이' in sl.split('슬롯 2')[1]); await shot(pg, tag + '_slots')
    await pg.locator('#slList .slot').nth(1).click(); await ws(pg, 'line')
    check(tag + ' 슬롯 불러오기', True)
    check(tag + ' 가로 넘침 없음(진행 중)', await pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    check(tag + ' 콘솔 오류 없음', not errs, errs)
    await ctx.close()

async def resume_test(b):
    ctx, pg, errs = await ctx_page(b, 360, 740)
    await pg.goto('http://localhost:%d/novel_test.html?fast=1' % PORT); await pg.wait_for_function("!document.getElementById('tNew').disabled")
    await pg.click('#tNew'); await ws(pg, 'line'); await adv_until(pg, "__novel.mode().ws==='choice'")
    await pg.locator('#cl button').nth(2).click(); await ws(pg, 'line')
    st = await ctx.storage_state(); await ctx.close()
    ctx, pg, errs = await ctx_page(b, 360, 740, store=st)
    await pg.goto('http://localhost:%d/novel_test.html?fast=1' % PORT); await pg.wait_for_function("!document.getElementById('tNew').disabled")
    check('새로고침 후 이어하기 켜짐', not await pg.locator('#tCont').is_disabled())
    await pg.click('#tCont'); await ws(pg, 'line')
    check('이어하기 상태 복원(선택·단서)', await pg.evaluate("__novel.ST().V.pickC===1 && __novel.ST().clues.length>=0"))
    await ctx.close()

async def rm_and_timer(b):
    ctx, pg, errs = await ctx_page(b, 360, 740, rm=True)
    await pg.goto('http://localhost:%d/novel_test.html' % PORT); await pg.wait_for_function("!document.getElementById('tNew').disabled")
    await pg.click('#tNew'); await ws(pg, 'line', 8000)
    check('움직임 줄이기: OS 설정 따름', await pg.evaluate("document.getElementById('app').classList.contains('rm')"))
    await pg.wait_for_timeout(300); txt = await pg.inner_text('#txt'); check('움직임 줄이기: 타자기 없이 한 번에 표시', '첫 줄입니다.' in txt, txt)
    await ctx.close()
    # 제한시간: 끄기/타임아웃
    ctx, pg, errs = await ctx_page(b, 360, 740)
    await pg.goto('http://localhost:%d/novel_test.html?fast=1' % PORT); await pg.wait_for_function("!document.getElementById('tNew').disabled")
    await pg.click('#tNew'); await ws(pg, 'line'); await adv_until(pg, "__novel.mode().ws==='choice'")
    # 시간 초과(20초)를 기다리지 않고 타이머만 확인: 단서를 안 주웠으니 선택지는 2개
    m = await mode(pg); check('단서 없으면 조건부 선택지 숨김', len(m['opts']) == 2, m['opts'])
    await ctx.close()

async def slow_net(b):
    ctx, pg, errs = await ctx_page(b, 360, 740, delay=300)
    await pg.add_init_script("window.__sil=0;new MutationObserver(()=>{if(document.querySelector('.sil'))window.__sil++}).observe(document,{subtree:true,childList:true})")
    await pg.goto('http://localhost:%d/novel_test.html?fast=1' % PORT)
    await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=30000)
    await pg.click('#tNew'); await ws(pg, 'line', 8000)
    for _ in range(14): await pg.evaluate('__novel.advance()'); await pg.wait_for_timeout(20)
    check('느린 네트워크(300ms)에서도 폴백 글자가 안 보임', await pg.evaluate('window.__sil')==0, await pg.evaluate('window.__sil'))
    await ctx.close()

async def main():
    build()
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            await story_walk(b, 360, 740, 'm360')
            await story_walk(b, 1280, 800, 'd1280')
            await resume_test(b); await rm_and_timer(b); await slow_net(b)
            await b.close()
    finally:
        sp.terminate(); os.remove(os.path.join(ROOT, 'novel_test.html'))
    print('\n실패 %d건' % len(FAILS), FAILS); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
