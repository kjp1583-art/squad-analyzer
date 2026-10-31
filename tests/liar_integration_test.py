#!/usr/bin/env python3
"""라이어 게임 통합 시험 — 실제 서버 코드(봇의 _lg_* 구역을 발췌 실행한 로컬 서버)에 브라우저 5개를 붙여 끝까지 돌린다.
사용: LG_BOT=<bot.py 경로> LG_SERVER=<lg_local_server.py 경로> CHROME=... python3.13 tests/liar_integration_test.py
(서버 시계는 /__lg/clock 으로 앞당겨 30초 제한 등을 기다리지 않는다)"""
import asyncio, json, os, subprocess, sys, time, urllib.request
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
BOT = os.environ['LG_BOT']; SERVER = os.environ['LG_SERVER']; PORT = int(os.environ.get('LG_PORT', '8791'))
BASE = f'http://127.0.0.1:{PORT}'; URL = f'{BASE}/liar.html?api={BASE}'
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {info}'))
    if not cond: fails.append(name)
def post(path, obj=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(obj or {}).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
def peek(): return json.load(urllib.request.urlopen(BASE + '/__lg/state'))
NAMES = ['가나', '다라', '마바', '사아', '자차']
async def mk(br, name):
    ctx = await br.new_context(viewport={'width': 1100, 'height': 800}, reduced_motion='reduce')
    await ctx.add_init_script(f"try{{localStorage.setItem('sgg_dc',JSON.stringify({{id:'u_{name}',name:'{name}',token:'tok_{name}',exp:Date.now()+6*86400000}}));localStorage.setItem('lg_mute','1');}}catch(e){{}}")
    pg = await ctx.new_page(); pg._errs = []
    pg.on('pageerror', lambda e: pg._errs.append(str(e)))
    pg.on('console', lambda m: pg._errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto(URL); return ctx, pg
async def phase(pg): return (await pg.inner_text('#phName')) if await pg.locator('#room').is_visible() else ''

async def main():
    srv = subprocess.Popen(['/usr/bin/python3', SERVER, '--bot', BOT, '--port', str(PORT), '--web', ROOT], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try: post('/__lg/reset'); break
            except Exception: time.sleep(.2)
        async with async_playwright() as p:
            br = await p.chromium.launch(executable_path=CHROME)
            ctxs = {}; pgs = {}
            for n in NAMES: ctxs[n], pgs[n] = await mk(br, n)
            H = pgs[NAMES[0]]
            await H.wait_for_selector('#createBtn')
            await H.fill('#cName', '통합방'); await H.click('#createBtn'); await H.wait_for_selector('#room:not([hidden])')
            code = (await H.inner_text('#rcode')).strip()
            check('방 만들기→대기실(코드 4자리)', len(code) == 4)
            for n in NAMES[1:]:
                pg = pgs[n]; await pg.wait_for_selector(f'#roomList [data-code={code}]', timeout=9000)
                await pg.click(f'#roomList [data-code={code}]'); await pg.wait_for_selector('#room:not([hidden])')
            await H.wait_for_function("document.querySelectorAll('#bPlayers .pc').length===5", timeout=8000)
            check('5명 모두 입장·대기실에 5명 표시', True)
            # 옵션: 1바퀴, 토론 30초
            await H.select_option('#o_rounds', '1'); await H.select_option('#o_discuss_s', '30'); await H.wait_for_timeout(1500)
            check('옵션 변경이 서버에 반영', peek()['rooms'][code]['state'] == 'lobby' and await H.input_value('#o_rounds') == '1' and await H.input_value('#o_discuss_s') == '30')
            # 채팅(대기실)
            await pgs[NAMES[1]].fill('#chatIn', '다들 모였나요?'); await pgs[NAMES[1]].click('#chatBtn')
            ok = True
            try: await pgs[NAMES[2]].wait_for_function("document.getElementById('msgs').innerText.includes('다들 모였나요?')", timeout=5000)
            except Exception: ok = False
            check('대기실 채팅이 다른 사람에게 보인다', ok)
            await H.click('[data-a=start]')
            # ---- 게임 진행 드라이버 ----
            word_seen_by_liar = False; liar = None; word = None; seen_states = set(); chatted = False; reloaded = False; stuck = 0
            t_end = time.time() + 150
            while time.time() < t_end:
                room = peek()['rooms'].get(code); st = room['state']; seen_states.add(st)
                sec = room['secret']
                if sec and not liar: liar = sec['liars'][0]; word = sec['word']
                if liar:
                    ln = liar[2:]
                    body = await pgs[ln].inner_text('body') if st != 'result' else ''
                    if st not in ('result', 'over') and word and word in body: word_seen_by_liar = True
                acted = False
                if st in ('hints', 'discuss', 'vote') and not reloaded:
                    reloaded = True; n = NAMES[3]; await pgs[n].reload(); await pgs[n].wait_for_selector('#room:not([hidden])', timeout=6000)
                    await pgs[n].wait_for_selector('#rcard .rc', timeout=6000)
                    check('게임 중 새로고침해도 같은 방으로 복귀(역할 카드도 다시 보임)', (await pgs[n].inner_text('#rcode')).strip() == code)
                if st == 'hints':
                    for n in NAMES:
                        if await pgs[n].locator('#hintForm').is_visible():
                            await pgs[n].fill('#hintIn', f'{n}의 힌트'); await pgs[n].press('#hintIn', 'Enter'); acted = True; await pgs[n].wait_for_timeout(300); break
                elif st == 'discuss':
                    if not chatted:
                        chatted = True; await pgs[NAMES[2]].fill('#chatIn', '라이어 같은 사람이 있어요'); await pgs[NAMES[2]].click('#chatBtn'); await pgs[NAMES[2]].wait_for_timeout(1500); acted = True
                    post('/__lg/clock', {'add': 31}); post('/__lg/tick'); acted = True
                elif st in ('vote', 'revote'):
                    for n in NAMES:
                        targ = liar if ('u_' + n) != liar else 'u_' + NAMES[0 if n != NAMES[0] else 1]
                        if (await pgs[n].locator('#bMain button.pc:not([disabled])').count()) and not await pgs[n].locator('#bMain button.pc.sel').count():
                            await pgs[n].locator(f'#bMain button.pc[data-uid="{targ}"]').click(); acted = True; await pgs[n].wait_for_timeout(250)
                    if not acted: post('/__lg/clock', {'add': 31}); post('/__lg/tick'); acted = True
                elif st == 'guess':
                    ln = liar[2:]
                    if await pgs[ln].locator('#guessForm').is_visible():
                        await pgs[ln].fill('#guessIn', '못 맞히는 단어'); await pgs[ln].click('#guessBtn'); acted = True
                elif st in ('result', 'over'): break
                elif st == 'reveal': post('/__lg/clock', {'add': 11}); post('/__lg/tick'); acted = True
                if not acted:
                    stuck += 1
                    if stuck % 4 == 0: post('/__lg/clock', {'add': 31}); post('/__lg/tick')
                await asyncio.sleep(.5)
            check('판이 결과 단계까지 끝난다', peek()['rooms'][code]['state'] == 'result', peek()['rooms'][code]['state'])
            check('단계가 순서대로 거쳐졌다(역할 공개·설명·토론·투표)', {'reveal', 'hints', 'discuss', 'vote'} <= seen_states, seen_states)
            check('진행 내내 라이어 화면에 제시어가 한 번도 없었다', not word_seen_by_liar)
            await asyncio.sleep(2)
            for n in NAMES:
                t = await pgs[n].inner_text('#bMain')
                if not ('승리' in t and word in t): check(f'결과 화면({n})', False, t[:120]); break
            else: check('결과 화면: 5명 모두에게 승패·제시어 공개', True)
            check('결과 화면: 방장에게만 다음 판 버튼', await H.locator('[data-a=next]').count() == 1 and await pgs[NAMES[1]].locator('[data-a=next]').count() == 0)
            check('결과의 전체 기록에 힌트와 토론 채팅이 있다', 'details' in (await H.inner_html('#bMain')) and await H.locator('#bMain .log li').count() >= 5)
            # 다음 판
            await H.click('[data-a=next]'); await H.wait_for_function("document.getElementById('phName').textContent==='역할 공개'", timeout=8000)
            check('다음 판: 다시 역할 공개로', True)
            # 이탈: 한 명 폴링 중단(탭 닫기) → 서버가 제외
            gone = NAMES[4]; await ctxs[gone].close()
            for _ in range(8):
                post('/__lg/clock', {'add': 40}); post('/__lg/tick'); await asyncio.sleep(.6)
                if len(peek()['rooms'].get(code, {}).get('players', [])) < 5: break
            check('폴링을 멈춘 사람은 서버가 방에서 제외한다', len(peek()['rooms'].get(code, {}).get('players', [])) <= 4)
            await asyncio.sleep(2)
            check('남은 화면은 계속 동작(참가자 줄어듦)', await H.locator('#bPlayers .pc').count() <= 4 or await H.locator('#room').is_visible())
            for n in NAMES[:4]:
                check(f'콘솔 오류 0 ({n})', not pgs[n]._errs, pgs[n]._errs[:3])
            await br.close()
    finally:
        srv.terminate()
    print('\n' + ('ALL PASS' if not fails else f'FAILED {len(fails)}: {fails}'))
    sys.exit(1 if fails else 0)
asyncio.run(main())
