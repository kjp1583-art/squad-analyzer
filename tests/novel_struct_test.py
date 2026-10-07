#!/usr/bin/env python3
"""「스콰드 생존게임」 구조·접근성·저장 복귀 시험 (Playwright).

  python3 tests/novel_struct_test.py            # 전부(진짜 원고 시험 포함 — 몇 분 걸린다)
  python3 tests/novel_struct_test.py --resume-only  # 진짜 원고의 저장 복귀(슬롯·이어하기)만 — 약 2분 (전체는 5분 넘게 걸려 도구 시간 제한에 끊기기 쉽다)
  python3 tests/novel_struct_test.py --quick    # 가짜 이야기(tests/novel_struct_story.txt)로 하는 안전망·접근성 시험만

1) 막힘 안전망 — 기회를 다 쓴 '뒤에만' 도움 단계가 열린다. 처음 몇 번의 시도에는 영향이 없다.
   · pick3·code·guide·cctv(순서/다른 모양)·무한 재시도 코드 퍼즐을 각각 끝까지 막혀 본다.
   · 도움 3단계까지 써서 푼 경우 / 도움을 끄고 막힌 경우 / '이대로 진행'(실패 분기) 로 끝까지 가는 경우.
2) 접근성 — 글자 크기 4단계, OS 의 '동작 줄이기', 터치 영역, 키보드(숫자·방향키·Enter)로 퍼즐 풀기.
3) 진짜 원고 — 엔딩 7종 전부 도달, 퍼즐 '실패' 분기를 하나씩 강제로 밟아 엔딩까지, 저장 슬롯·이어하기 뒤 복귀.
환경변수 CHROME 으로 크로미움 실행 파일을 고를 수 있다."""
import asyncio, subprocess, time, sys, os, shutil, json, re
try: sys.stdout.reconfigure(line_buffering=True)   # 파이프로 받아도 진행 줄이 바로 보이게(시간 제한에 끊겨도 어디까지 갔는지 남는다)
except Exception: pass
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SIM_ALLCLUE', '1')
import novel_sim as sim
import novel_walk as walk
PORT = 8793
walk.PORT = PORT
QUICK = '--quick' in sys.argv
RESUME_ONLY = '--resume-only' in sys.argv      # 진짜 원고에서 '저장 복귀'(슬롯·이어하기)만 — 실패 분기 12개 순회(수 분)를 건너뛴다
FAILS = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(extra) if extra and not cond else ''))
    if not cond: FAILS.append(name)

def build():
    shutil.copy(os.path.join(ROOT, 'novel.html'), os.path.join(ROOT, 'novel_struct.html'))
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tooling/novel_build.py'), '--src', os.path.join(ROOT, 'tests/novel_struct_story.txt'),
                        '--out', os.path.join(ROOT, 'novel_struct.html')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

async def ctx_page(b, w=360, h=740, rm=False, touch=False, store=None, page='novel_struct.html?fast=1'):
    kw = dict(viewport={'width': w, 'height': h}, reduced_motion='reduce' if rm else 'no-preference', storage_state=store)
    if touch: kw.update(has_touch=True, is_mobile=True)
    ctx = await b.new_context(**kw)
    async def route(r):
        if not r.request.url.startswith('http://localhost:%d/' % PORT): await r.abort(); return
        await r.continue_()
    await ctx.route('**/*', route)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto('http://localhost:%d/%s' % (PORT, page))
    await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=15000)
    return ctx, pg, errs

async def close_menus(pg):
    for _ in range(2): await pg.keyboard.press('Escape')
    await pg.wait_for_timeout(30)
async def goto_label(pg, label):
    await pg.evaluate("l=>{__novel.ST().pc=__novel.STORY.labels[l];__novel.run()}", label)
    await pg.wait_for_function("__novel.mode().ws==='puz'", timeout=4000)
async def new_game(pg):
    await pg.click('#tNew'); await pg.wait_for_function("__novel.mode().ws==='line'", timeout=5000)
async def V(pg, k): return await pg.evaluate("k=>__novel.ST().V[k]|0", k)
async def rescue(pg): return await pg.evaluate("__novel.puzzle.rescue()")
async def wait_rescue(pg, t=3000):
    await pg.wait_for_function("(__novel.puzzle.rescue()||{}).open===true", timeout=t)
async def wait_done(pg, flag, t=4000):
    """퍼즐이 끝나고 결과 플래그(ok_/fail_/skip_)가 서길 기다린다 — 다음 퍼즐이 바로 열려서 ws 만으로는 구분이 안 된다"""
    await pg.wait_for_function("k=>__novel.ST().V[k]>0", arg=flag, timeout=t)
async def panel(pg): return await pg.locator('.rescue').count()

async def pick_wrong_attempt(pg):
    """pick3: 정답(0·2·4번)이 아닌 세 개 — 지워진 보기는 건너뛰고, 모자라면 정답 하나를 섞어서(그래도 오답이 되게) 확인"""
    chosen = []
    for i in (1, 3, 5, 6, 7):
        if len(chosen) < 3 and await pg.locator('.pk').nth(i).is_enabled(): chosen.append(i)
    for i in (0, 2):
        if len(chosen) < 3: chosen.append(i)
    for i in chosen: await pg.locator('.pk').nth(i).click()
    await pg.locator('.pzbtn.go').click(); await pg.wait_for_timeout(30)

# ---------------------------------------------------------------- 1) 막힘 안전망
async def rescue_pick3(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_pick')
    check('안전망 pick3: 처음엔 도움 패널 없음', await panel(pg) == 0)
    await pick_wrong_attempt(pg); await pick_wrong_attempt(pg)
    check('안전망 pick3: 2번 틀려도(기회 남음) 패널 없음 — 처음 시도 난이도 그대로', await panel(pg) == 0 and not (await rescue(pg))['open'])
    check('안전망 pick3: 2번 틀리면 넘어가기만(기존 도움)', await pg.locator('#pzSkip').is_visible())
    check('안전망 pick3: 보기 지워짐 없음(소진 전)', await pg.locator('.pk.off').count() == 0 and await pg.locator('.pk.ans').count() == 0)
    await pick_wrong_attempt(pg); await wait_rescue(pg)
    check('안전망 pick3: 기회 소진 뒤 패널이 열림', await panel(pg) == 1 and await pg.locator('#rsNext').is_visible() and await pg.locator('#rsEnd').is_visible())
    check('안전망 pick3: 패널이 열려 있는 동안 퍼즐 본체는 숨김', not await pg.locator('.pk').first.is_visible())
    await pg.locator('#rsNext').click()
    off1 = await pg.locator('.pk.off').count()
    check('안전망 pick3: 1단계 — 오답 일부가 지워짐', 0 < off1 < 5 and await pg.locator('.pk.ans').count() == 0, off1)
    check('안전망 pick3: 1단계 — 패널 닫히고 기회 2번', await panel(pg) == 0 and '남은 기회 2' in await pg.inner_text('.pzs[aria-live]'), await pg.inner_text('.pzs[aria-live]'))
    await pick_wrong_attempt(pg); await pick_wrong_attempt(pg); await wait_rescue(pg)
    check('안전망 pick3: 다시 막히면 2단계 제안', (await rescue(pg))['rs'] == 1 and '2단계' in await pg.inner_text('#rsNext'))
    await pg.locator('#rsNext').click()
    off2 = await pg.locator('.pk.off').count()
    check('안전망 pick3: 2단계 — 더 많이 지워짐(오답 한 개만 남음)', off2 > off1 and off2 == 4, (off1, off2))
    await pick_wrong_attempt(pg); await pick_wrong_attempt(pg); await wait_rescue(pg)
    await pg.locator('#rsNext').click()
    check('안전망 pick3: 3단계 — 정답 3개 표시', await pg.locator('.pk.ans').count() == 3)
    for k in '135': await pg.keyboard.press(k)          # 키보드: 숫자 1·3·5 = 사과·포도·감
    check('안전망 pick3: 키보드 숫자로 고름', await pg.locator('.pk[aria-pressed=true]').count() == 3)
    await pg.keyboard.press('Enter'); await wait_done(pg, 'ok_pick')
    check('안전망 pick3: 도움으로 풀면 성공 분기 + 도움 기록', await V(pg, 'ok_pick') == 1 and await V(pg, 'assisted') >= 1 and await V(pg, 'fail_pick') == 0)
    check('안전망 pick3: 콘솔 오류 없음', not errs, errs); await ctx.close()

async def rescue_pick3_giveup(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_pick')
    for _ in range(3): await pick_wrong_attempt(pg)
    await wait_rescue(pg); await pg.locator('#rsEnd').click(); await wait_done(pg, 'fail_pick')
    check('안전망 pick3: 이대로 진행 → 실패 분기로 이야기가 이어짐', await V(pg, 'fail_pick') == 1 and await V(pg, 'ok_pick') == 0 and await V(pg, 'assisted') == 0)
    await pg.wait_for_function("__novel.mode().ws==='puz'||__novel.mode().ws==='line'"); await ctx.close()
    # 도움을 끈 사람: 패널 없이 곧장 실패 분기
    ctx, pg, errs = await ctx_page(b); await new_game(pg)
    await pg.evaluate("__novel.SET.assist=false"); await goto_label(pg, 's_pick')
    for _ in range(3): await pick_wrong_attempt(pg)
    await wait_done(pg, 'fail_pick')
    check('안전망: 도움을 끄면 패널 없이 실패 분기', await V(pg, 'fail_pick') == 1 and await panel(pg) == 0)
    await ctx.close()

async def pick3_keyboard_plain(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_pick')
    for k in '135': await pg.keyboard.press(k)
    await pg.keyboard.press('Enter'); await wait_done(pg, 'ok_pick')
    check('키보드: pick3 숫자 + Enter 로 풀림(도움 기록 없음)', await V(pg, 'ok_pick') == 1 and await V(pg, 'assisted') == 0)
    check('키보드: pick3 안내 문구가 보임(마우스 기기)', 'Enter' in await pg.evaluate("(document.querySelector('.kh')||{}).textContent||''"))
    await ctx.close()

async def type_code(pg, s):
    for ch in s: await pg.keyboard.press(ch)
    await pg.keyboard.press('Enter'); await pg.wait_for_timeout(30)

async def rescue_code(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_code')
    await type_code(pg, '1111'); await type_code(pg, '2222')
    check('안전망 code: 소진 전엔 패널·정답 힌트 없음', await panel(pg) == 0 and not await pg.locator('.hints.rv').is_visible())
    await type_code(pg, '3333'); await wait_rescue(pg)
    check('안전망 code: 기회 소진 뒤 패널', await pg.locator('#rsNext').is_visible())
    await pg.locator('#rsNext').click()
    check('안전망 code: 1단계 — 첫 자리만 알려 줌', '2○○○' in await pg.inner_text('.hints.rv'), await pg.inner_text('.hints.rv'))
    await type_code(pg, '1111'); await type_code(pg, '2222'); await wait_rescue(pg); await pg.locator('#rsNext').click()
    check('안전망 code: 2단계 — 앞 절반', '25○○' in await pg.inner_text('.hints.rv'), await pg.inner_text('.hints.rv'))
    await type_code(pg, '1111'); await type_code(pg, '2222'); await wait_rescue(pg); await pg.locator('#rsNext').click()
    check('안전망 code: 3단계 — 정답 전부', '2526' in await pg.inner_text('.hints.rv'))
    await type_code(pg, '2526'); await wait_done(pg, 'ok_code')
    check('안전망 code: 도움으로 풀면 성공 분기 + 도움 기록', await V(pg, 'ok_code') == 1 and await V(pg, 'assisted') >= 1)
    check('안전망 code: 콘솔 오류 없음', not errs, errs); await ctx.close()
    # 처음 시도 한 번에 풀기 = 키보드만으로
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_code')
    await pg.keyboard.press('2'); await pg.keyboard.press('5'); await pg.keyboard.press('Backspace'); await type_code(pg, '526'); await wait_done(pg, 'ok_code')
    check('키보드: code 숫자·Backspace·Enter', await V(pg, 'ok_code') == 1 and await V(pg, 'assisted') == 0)
    await ctx.close()

async def rescue_guide(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_guide')
    async def wrong():
        await pg.wait_for_function("document.querySelectorAll('.dir').length===3&&!document.querySelector('.dir.busy')")
        await pg.wait_for_timeout(60); await pg.locator('.dir').nth(1).click(); await pg.wait_for_timeout(80)
    await wrong(); await wrong()
    check('안전망 guide: 소진 전엔 패널 없음', await panel(pg) == 0)
    await wrong(); await wait_rescue(pg)
    check('안전망 guide: 기회 소진 뒤 패널', await pg.locator('#rsNext').is_visible() and '1단계' in await pg.locator('#rsNext').inner_text())
    await pg.locator('#rsNext').click()
    check('안전망 guide: 1단계 — 제한시간 막대 사라짐', await pg.evaluate("getComputedStyle(document.querySelector('.pzbar')).display==='none'"))
    await pg.wait_for_function("document.querySelectorAll('.dir').length===3"); await pg.wait_for_timeout(60)
    await wrong(); await wrong(); await wrong(); await wait_rescue(pg); await pg.locator('#rsNext').click()
    await pg.wait_for_function("document.querySelectorAll('.dir').length===3"); await pg.wait_for_timeout(60)
    check('안전망 guide: 2단계 — 맞는 방향 표시', await pg.locator('.dir.ans').count() == 1 and 'ans' in (await pg.locator('.dir').nth(0).get_attribute('class')))
    await wrong(); await wrong(); await wrong(); await wait_rescue(pg)
    await pg.locator('#rsNext').click(); await wait_done(pg, 'skip_guide')
    check('안전망 guide: 3단계 — 도움으로 통과 기록', await V(pg, 'skip_guide') == 1 and await V(pg, 'assisted') >= 1 and await V(pg, 'fail_guide') == 0)
    await ctx.close()
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_guide')
    await pg.wait_for_function("document.querySelectorAll('.dir').length===3"); await pg.wait_for_timeout(60)
    await pg.keyboard.press('ArrowUp'); await pg.wait_for_timeout(120)
    await pg.wait_for_function("/오른쪽에 흔적/.test(document.querySelector('.voice').textContent)"); await pg.wait_for_timeout(60)
    await pg.keyboard.press('3'); await wait_done(pg, 'ok_guide')
    check('키보드: guide 방향키·숫자로 풀림', await V(pg, 'ok_guide') == 1 and await V(pg, 'assisted') == 0)
    await ctx.close()
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_guide')
    await pg.wait_for_function("document.querySelectorAll('.dir').length===3"); await pg.wait_for_timeout(60)
    for _ in range(3): await wrong_dir(pg)
    await wait_rescue(pg); await pg.locator('#rsEnd').click(); await wait_done(pg, 'fail_guide')
    check('안전망 guide: 이대로 진행 → 실패 분기', await V(pg, 'fail_guide') == 1)
    await ctx.close()

async def wrong_dir(pg):
    await pg.wait_for_function("document.querySelectorAll('.dir').length===3"); await pg.wait_for_timeout(70)
    await pg.locator('.dir').nth(1).click(); await pg.wait_for_timeout(90)

async def rescue_cctv(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_cctv')
    async def wrong():
        await pg.wait_for_function("!document.querySelector('.cc.miss')"); await pg.wait_for_timeout(30)
        await pg.locator('.cc.nm').nth(0).click(); await pg.wait_for_timeout(40)
    await wrong(); await wrong(); check('안전망 cctv(순서): 소진 전엔 패널 없음', await panel(pg) == 0)
    await wrong(); await wait_rescue(pg)
    await pg.locator('#rsNext').click()
    check('안전망 cctv(순서): 1단계 — 기회 3번 다시, 표시는 아직 없음', await pg.locator('.cc.nx').count() == 0 and '남은 기회 3' in await pg.inner_text('.pzs[aria-live], .pzs'))
    await wrong(); await wrong(); await wrong(); await wait_rescue(pg); await pg.locator('#rsNext').click()
    check('안전망 cctv(순서): 2단계 — 눌러야 할 칸(kater) 표시', await pg.locator('.cc.nx').count() == 1 and 'kater' in await pg.locator('.cc.nx').inner_text())
    await pg.locator('.cc.nx').click(); await pg.wait_for_timeout(30)
    check('안전망 cctv(순서): 다음 칸으로 표시가 옮겨 감', await pg.locator('.cc.nx').count() == 1 and '허기허기' in await pg.locator('.cc.nx').inner_text())
    await wrong(); await wrong(); await wrong(); await wait_rescue(pg); await pg.locator('#rsNext').click(); await wait_done(pg, 'skip_cctv')
    check('안전망 cctv(순서): 3단계 — 도움으로 통과', await V(pg, 'skip_cctv') == 1 and await V(pg, 'assisted') >= 1)
    await ctx.close()
    # 방향키로 칸 이동
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_cctv')
    await pg.locator('.cc').first.focus(); await pg.keyboard.press('ArrowRight'); await pg.keyboard.press('ArrowDown')
    idx = await pg.evaluate("[...document.querySelectorAll('#pzBody .cc')].indexOf(document.activeElement)")
    check('키보드: cctv 방향키로 칸 이동(오른쪽·아래 = 6번째)', idx == 6, idx)
    await ctx.close()

async def rescue_odd(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_odd')
    ODD = "(()=>{const t={};[...document.querySelectorAll('.cc')].forEach(b=>{const k=b.firstChild.textContent;t[k]=(t[k]||0)+1});return Object.keys(t).find(k=>t[k]===1)})()"
    async def wrong():
        odd = await pg.evaluate(ODD)
        await pg.locator('.cc:not(.miss)').filter(has_not_text=odd).first.click(); await pg.wait_for_timeout(40)
    await wrong(); await wrong(); check('안전망 cctv(다른 모양): 소진 전엔 패널 없음', await panel(pg) == 0)
    await wrong(); await wait_rescue(pg); await pg.locator('#rsNext').click(); await pg.wait_for_timeout(30)
    await wrong(); await wrong(); await wrong(); await wait_rescue(pg); await pg.locator('#rsNext').click(); await pg.wait_for_timeout(30)
    check('안전망 cctv(다른 모양): 2단계 — 다른 칸 한 개 표시', await pg.locator('.cc.nx').count() == 1)
    odd = await pg.evaluate(ODD)
    check('안전망 cctv(다른 모양): 표시된 칸이 정말 다른 모양', odd in await pg.locator('.cc.nx').inner_text())
    await pg.locator('.cc.nx').click(); await pg.wait_for_timeout(40)
    await pg.wait_for_function("document.querySelectorAll('.cc').length===25&&!document.querySelector('.cc.hit')"); await pg.wait_for_timeout(30)
    await wrong(); await wrong(); await wrong(); await wait_rescue(pg); await pg.locator('#rsNext').click(); await wait_done(pg, 'skip_odd')
    check('안전망 cctv(다른 모양): 3단계 — 통과', await V(pg, 'skip_odd') == 1)
    await ctx.close()

async def rescue_inf(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await goto_label(pg, 's_inf')
    for _ in range(5): await type_code(pg, '1111')
    check('안전망 무한 코드: 5번까지는 패널 없음', await panel(pg) == 0)
    await type_code(pg, '1111'); await wait_rescue(pg)
    r = await rescue(pg)
    check('안전망 무한 코드: 6번째 막힘에 패널(계속 풀기 있음)', r['open'] and r['inf'] and await pg.locator('#rsKeep').is_visible())
    await pg.locator('#rsKeep').click()
    check('안전망 무한 코드: 계속 풀어 보기 → 패널 닫힘 + 넘어가기도 보임', await panel(pg) == 0 and await pg.locator('#pzSkip').is_visible())
    await type_code(pg, '0630'); await wait_done(pg, 'ok_inf')
    check('안전망 무한 코드: 풀리면 성공', await V(pg, 'ok_inf') == 1)
    await ctx.close()
    # 도움을 꺼 둬도 무한 퍼즐은 6번 막히면 넘어가기가 나온다 — 끝까지 갈 수 있는 최종 경로
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await pg.evaluate("__novel.SET.assist=false"); await goto_label(pg, 's_inf')
    for _ in range(5): await type_code(pg, '1111')
    check('최종 경로: 도움 끔 · 5번 → 넘어가기 숨김', not await pg.locator('#pzSkip').is_visible())
    await type_code(pg, '1111')
    check('최종 경로: 도움 끔 · 6번 → 넘어가기 보임(패널 없이)', await pg.locator('#pzSkip').is_visible() and await panel(pg) == 0)
    await pg.locator('#pzSkip').click(); await wait_done(pg, 'skip_inf')
    check('최종 경로: 넘어가기로 이야기가 이어짐', await V(pg, 'skip_inf') == 1)
    await ctx.close()

async def vote_keyboard(b):
    ctx, pg, errs = await ctx_page(b); await new_game(pg)
    await pg.evaluate("__novel.ST().pc=__novel.STORY.labels.s_end;__novel.run()"); await pg.wait_for_function("__novel.mode().ptype==='vote'")
    await pg.keyboard.press('2')
    check('키보드: vote 숫자로 고름', await pg.locator('.vc[aria-pressed=true]').count() == 1)
    await pg.keyboard.press('Enter'); await pg.wait_for_function("__novel.mode().ws!=='puz'")
    check('키보드: vote Enter 로 확정', True); await ctx.close()

# ---------------------------------------------------------------- 2) 접근성
async def a11y(b):
    # 글자 크기
    ctx, pg, errs = await ctx_page(b, page='novel_struct.html?fast=1'); await new_game(pg)
    size = lambda: pg.evaluate("parseFloat(getComputedStyle(document.getElementById('box')).fontSize)")
    s1 = await size()
    await pg.click('#bMenu'); await pg.click('#mSet')
    check('글자 크기: 설정에 버튼이 있고 기본은 보통', (await pg.inner_text('#sFs')) == '보통')
    await pg.click('#sFs'); await close_menus(pg); s2 = await size()
    check('글자 크기: 크게 → 대사 글자가 커짐(약 1.2배)', 1.15 < s2 / s1 < 1.25, (s1, s2))
    await pg.click('#bMenu'); await pg.click('#mSet'); await pg.click('#sFs'); await close_menus(pg); s3 = await size()
    check('글자 크기: 아주 크게 → 약 1.45배', 1.4 < s3 / s1 < 1.5, (s1, s3))
    check('글자 크기: 아주 크게에서도 가로 넘침 없음', await pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    fits = await pg.evaluate("(()=>{const r=document.getElementById('box').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight+1})()")
    check('글자 크기: 아주 크게에서도 대사 상자가 화면 안', fits)
    st = await ctx.storage_state(); await ctx.close()
    ctx, pg, errs = await ctx_page(b, store=st)
    check('글자 크기: 새로 열어도 기억함', await pg.evaluate("__novel.SET.fs")==3)
    await pg.click('#tSet'); check('글자 크기: 설정 표시도 복원', (await pg.inner_text('#sFs')) == '아주 크게')
    await ctx.close()
    # 글자 크기에서 퍼즐 화면도 넘치지 않는지(360폭)
    ctx, pg, errs = await ctx_page(b); await new_game(pg); await pg.evaluate("__novel.SET.fs=3;document.getElementById('app').style.setProperty('--fs',1.45)")
    for lab in ('s_pick', 's_code', 's_cctv'):
        await goto_label(pg, lab)
        check('글자 크기 아주 크게 + 퍼즐(%s): 가로 넘침 없음' % lab, await pg.evaluate("document.documentElement.scrollWidth<=innerWidth&&document.getElementById('puz').scrollWidth<=document.getElementById('puz').clientWidth+1"))
    await ctx.close()
    # 동작 줄이기(OS)
    ctx, pg, errs = await ctx_page(b, rm=True, page='novel_struct.html?fast=1'); await new_game(pg)
    check('동작 줄이기: OS 설정을 따름(켜짐)', await pg.evaluate("document.getElementById('app').classList.contains('rm')&&document.documentElement.dataset.rm==='on'"))
    anim = await pg.evaluate("(()=>{const f=document.getElementById('fxFlick');f.classList.add('on');const a=getComputedStyle(f).animationName;f.classList.remove('on');const s=document.getElementById('stage');s.classList.add('shake');const b=getComputedStyle(s).animationName;s.classList.remove('shake');return [a,b]})()")
    check('동작 줄이기: 붉은 명멸·화면 흔들림 애니메이션 없음', anim == ['none', 'none'], anim)
    await pg.click('#bMenu'); await pg.click('#mSet'); await pg.click('#sRm')
    anim = await pg.evaluate("(()=>{const f=document.getElementById('fxFlick');f.classList.add('on');const a=getComputedStyle(f).animationName;f.classList.remove('on');return a})()")
    check('동작 줄이기: 사용자가 직접 끄면 OS 설정보다 우선', anim != 'none' and await pg.evaluate("document.documentElement.dataset.rm")=='off', anim)
    await ctx.close()
    ctx, pg, errs = await ctx_page(b); 
    check('동작 줄이기: OS 가 안 켰으면 꺼짐', await pg.evaluate("document.documentElement.dataset.rm")=='off')
    await pg.emulate_media(reduced_motion='reduce'); await pg.wait_for_timeout(80)
    check('동작 줄이기: 실행 중 OS 설정이 바뀌면 따라감', await pg.evaluate("document.documentElement.dataset.rm")=='on' and await pg.evaluate("__novel.SET.rm"))
    await ctx.close()
    # 터치 영역
    ctx, pg, errs = await ctx_page(b, touch=True); await new_game(pg)
    small = await pg.evaluate("""(()=>{const bad=[];document.querySelectorAll('#hud .hb').forEach(b=>{const r=b.getBoundingClientRect();if(!r.width)return;
       const pts=[[r.left+r.width/2,r.top-5],[r.left+r.width/2,r.bottom+5]]; const ok=pts.every(p=>document.elementFromPoint(p[0],p[1])===b);
       if(!ok||r.height<36)bad.push([b.id,Math.round(r.height),ok])});return bad})()""")
    check('터치: HUD 버튼 반응 영역이 눈에 보이는 높이보다 위·아래로 넓음(44px 이상)', not small, small)
    for lab in ('s_pick', 's_code', 's_guide', 's_cctv', 's_odd'):
        await goto_label(pg, lab); await pg.wait_for_timeout(50)
        bad = await pg.evaluate("""[...document.querySelectorAll('#pzBody button')].filter(b=>b.offsetParent&&!b.disabled).map(b=>{const r=b.getBoundingClientRect();return [b.className||b.id,Math.round(r.width),Math.round(r.height)]}).filter(x=>x[2]<44||x[1]<44)""")
        check('터치: 퍼즐(%s) 버튼은 모두 44px 이상' % lab, not bad, bad[:4])
    await ctx.close()

# ---------------------------------------------------------------- 3) 진짜 원고
def find_forced(story, pc_t, tmax=120):
    """퍼즐 pc_t 를 '실패'로 지나 엔딩에 닿는 결정 목록 (단서는 모두 줍는다)."""
    RV, CID = sim.relevant(story); seen = set(); t0 = time.time()
    def skey(pc, V, clues, passed): return (pc, passed, tuple(sorted((a, min(b, 9)) for a, b in V.items() if a in RV)), tuple(sorted(c for c in clues if c in RV)), len(clues) if 'clues' in RV else 0)
    st = {'lines': 0}; V0, c0 = {}, set(); k, pc, pl = sim.advance(story, 0, V0, c0, st)
    stack = [(k, pc, pl, V0, c0, [], False)]
    while stack and time.time() - t0 < tmax:
        k, pc, pl, V, clues, path, passed = stack.pop()
        if k == 'end':
            if passed: return path
            continue
        if k in ('loop', 'fall'): continue
        key = skey(pc, V, clues, passed)
        if key in seen: continue
        seen.add(key)
        opts = sim.options(story, k, pc, pl, V, clues)
        hit = (k == 'puz' and pc == pc_t)
        if hit: opts = [('p', 'fail')]
        for dec in reversed(opts):
            V2 = dict(V); c2 = set(clues); npc = sim.apply(story, k, pc, pl, dec, V2, c2)
            st = {'lines': 0}; k2, pc2, pl2 = sim.advance(story, npc, V2, c2, st)
            stack.append((k2, pc2, pl2, V2, c2, path + [(k, pc, dec if not isinstance(dec, tuple) else list(dec))], passed or hit))
    return None

async def real_pages(b, store=None):
    ctx = await b.new_context(viewport={'width': 360, 'height': 740}, storage_state=store)
    async def route(r):
        if not r.request.url.startswith('http://localhost:%d/' % PORT): await r.abort(); return
        await r.continue_()
    await ctx.route('**/*', route); pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto('http://localhost:%d/novel.html?fast=1' % PORT)
    await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=20000)
    return ctx, pg, errs

async def real_story(b):
    story, ctx_ = sim.load()
    found, n, dt = sim.search(story)
    ends = [e['id'] for e in story['endings']]
    print('-- 진짜 원고: 시뮬 경로 %d/%d 엔딩 (%.0f초)' % (len(found), len(ends), dt))
    ctx, pg, errs = await real_pages(b); reached = {}
    for e in ends:
        f = found.get(e)
        if not f: check('엔딩 %s 시뮬 경로' % e, False); continue
        r = await walk.play(pg, decisions=f[0]); reached[e] = r.get('end')
        check('엔딩 %s 도달(기본 경로)' % e, r.get('end') == e, r)
    # 퍼즐 '실패' 분기를 하나씩 강제로 밟는다
    fails = [(pc, op) for pc, op in enumerate(story['ops']) if op['o'] == 'puz' and op['type'] != 'vote' and 'fail' in op['d']]
    if RESUME_ONLY: fails = []
    print('-- 실패 분기가 있는 퍼즐 %d개를 하나씩 실패시켜 엔딩까지 간다' % len(fails))
    ended = set(); skipped = []
    for pc, op in fails:
        path = find_forced(story, pc)
        if not path: skipped.append(pc); continue
        labels = [a[1] for a in op['d']['fail'] if a[0] == 'goto']
        tgt = story['labels'][labels[0]] if labels else None
        pcs = set(); r = await walk.play(pg, decisions=path, pcs=pcs)
        hit = tgt is None or any(tgt <= x < tgt + 12 for x in pcs)
        ended.add(r.get('end'))
        check('퍼즐 pc=%d(%s) 실패 분기 → 엔딩 %s 까지' % (pc, op['d'].get('q', '')[:18], r.get('end')), 'end' in r and hit, (r, 'fail 목적지 안 지남' if not hit else ''))
    if not RESUME_ONLY: check('실패 분기로 닿은 엔딩이 하나 이상', len(ended) >= 1, ended)
    if skipped: print('   (도달 못 해 건너뛴 퍼즐 pc: %s — 단서 전부 줍기 조건에서 갈 수 없는 자리)' % skipped)
    check('진짜 원고 콘솔 오류 없음', not errs, errs[:3]); await ctx.close()
    return story, found

async def resume_real(b, story, found):
    f = found.get('true'); 
    if not f: check('저장 복귀: true 경로', False); return
    path = f[0]; di = [d for d in path if d[0] != 'clue']
    ks_choice = [k for k, d in enumerate(di) if d[0] == 'choice']; ks_puz = [k for k, d in enumerate(di) if d[0] == 'puz']
    k1 = ks_choice[len(ks_choice) // 2]
    # (a) 슬롯에 저장 → 새 브라우저에서 슬롯 불러오기
    ctx, pg, errs = await real_pages(b)
    r = await walk.play(pg, decisions=path, pause_k=k1)
    check('저장 복귀(슬롯): 중간 선택지에서 멈춤', r.get('paused') and r['ws'] == 'choice', r)
    await pg.click('#bMenu'); await pg.click('#mSave'); await pg.locator('#slList .slot').nth(0).click()
    store = await ctx.storage_state(); await ctx.close()
    ctx, pg, errs = await real_pages(b, store)
    check('저장 복귀(슬롯): 새로 열어도 슬롯 1 에 저장 표시', await pg.evaluate("(JSON.parse(localStorage.getItem('sq_novel2_slots')||'[]')[0]||{}).pc>=0"))
    await pg.click('#tLoad'); await pg.locator('#slList .slot').nth(0).click()
    await pg.wait_for_function("__novel.mode().ws==='choice'", timeout=5000)
    m = await pg.evaluate('__novel.mode()')
    check('저장 복귀(슬롯): 같은 선택지 자리로 돌아옴', m['pc'] == r['pc'], (m['pc'], r['pc']))
    r2 = await walk.play(pg, decisions=path, resume_k=k1, resume_clues=r['clues'], cmap=r['cmap'])
    check('저장 복귀(슬롯): 이어서 같은 엔딩(true)', r2.get('end') == 'true', r2)
    check('저장 복귀(슬롯): 콘솔 오류 없음', not errs, errs[:3]); await ctx.close()
    # (b) 이어하기(자동 저장) — 10장 이후 첫 퍼즐 앞에서 닫았다 열기
    late = [k for k in ks_puz if di[k][1] > story['chapters'][-8]['pc']]
    k2 = late[0] if late else ks_puz[-1]
    ctx, pg, errs = await real_pages(b)
    r = await walk.play(pg, decisions=path, pause_k=k2)
    check('저장 복귀(이어하기): 후반 퍼즐 앞에서 멈춤', r.get('paused') and r['ws'] == 'puz', r)
    store = await ctx.storage_state(); await ctx.close()
    ctx, pg, errs = await real_pages(b, store)
    check('저장 복귀(이어하기): 이어하기 버튼이 켜져 있음', not await pg.locator('#tCont').is_disabled())
    await pg.click('#tCont'); await pg.wait_for_function("__novel.mode().ws!=='title'", timeout=5000)
    r2 = await walk.play(pg, decisions=path, resume_k=k2, resume_clues=r['clues'], cmap=r['cmap'])
    check('저장 복귀(이어하기): 이어서 같은 엔딩(true)', r2.get('end') == 'true', r2)
    check('저장 복귀(이어하기): 콘솔 오류 없음', not errs, errs[:3]); await ctx.close()

async def main():
    build()
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            kw = {'executable_path': os.environ.get('CHROME') or '/opt/pw-browsers/chromium'}
            b = await p.chromium.launch(**kw)
            only = sys.argv[sys.argv.index('--only') + 1].split(',') if '--only' in sys.argv else None
            for fn in () if RESUME_ONLY else (rescue_pick3, rescue_pick3_giveup, pick3_keyboard_plain, rescue_code, rescue_guide, rescue_cctv, rescue_odd, rescue_inf, vote_keyboard, a11y):
                if only and fn.__name__ not in only: continue
                print('== %s' % fn.__name__)
                try: await fn(b)
                except Exception as e: check('%s 예외 없이 끝남' % fn.__name__, False, repr(e)[:900])
            if not QUICK or RESUME_ONLY:
                print('== real_story')
                try:
                    story, found = await real_story(b)
                    print('== resume_real'); await resume_real(b, story, found)
                except Exception as e: check('진짜 원고 시험 예외 없음', False, repr(e)[:400])
            await b.close()
    finally:
        sp.terminate()
        try: os.remove(os.path.join(ROOT, 'novel_struct.html'))
        except OSError: pass
    print('\n실패 %d건' % len(FAILS), FAILS); return 1 if FAILS else 0
if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
