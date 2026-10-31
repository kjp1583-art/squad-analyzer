#!/usr/bin/env python3
"""라이어 게임 통합 시험 2 — 서버 재시작 복원 · 동률 재투표 · 마지막 기회(맞히기) · 바보 라이어 · 라이어 2명을 브라우저로 본다.
사용: LG_BOT=<bot.py> LG_SERVER=<lg_local_server.py> CHROME=... python3.13 tests/liar_integration2_test.py"""
import asyncio, json, os, subprocess, sys, time, urllib.request
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
BOT = os.environ['LG_BOT']; SERVER = os.environ['LG_SERVER']; PORT = int(os.environ.get('LG_PORT', '8792'))
BASE = f'http://127.0.0.1:{PORT}'; URL = f'{BASE}/liar.html?api={BASE}'
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {info}'))
    if not cond: fails.append(name)
def post(path, obj=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(obj or {}).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
def api(n, path, **kw): return post('/lg/' + path, dict(token='tok_' + n, **kw))
def peek(code):
    j = json.load(urllib.request.urlopen(BASE + '/__lg/state'))
    if code not in j['rooms']: raise SystemExit('방 %s 사라짐: 남은 방 %s errs=%s' % (code, list(j['rooms']), j.get('errs')))
    return j['rooms'][code]
N = ['가나', '다라', '마바', '사아', '자차', '카타', '파하', '거너']
async def mk(br, name):
    ctx = await br.new_context(viewport={'width': 1100, 'height': 800})
    await ctx.add_init_script(f"try{{localStorage.setItem('sgg_dc',JSON.stringify({{id:'u_{name}',name:'{name}',token:'tok_{name}',exp:Date.now()+6*86400000}}));localStorage.setItem('lg_mute','1');}}catch(e){{}}")
    pg = await ctx.new_page(); pg._errs = []
    pg.on('pageerror', lambda e: pg._errs.append(str(e)))
    pg.on('console', lambda m: pg._errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto(URL); return ctx, pg
def newroom(names, opts):
    post('/__lg/reset')
    code = api(names[0], 'create', name='시험방', max=10, public=True, opts=opts)['code']
    for n in names[1:]: assert api(n, 'join', code=code)['ok']
    return code
def skip(sec):
    # 시계를 한꺼번에 90초 넘게 밀면 브라우저가 폴링할 틈이 없어 「이탈」로 오해받는다 — 15초씩 밀고 폴링을 기다린다
    while sec > 0:
        d = min(sec, 15); sec -= d; post('/__lg/clock', {'add': d}); post('/__lg/tick')
        if sec > 0: time.sleep(1.3)
async def until(fn, t=10):
    end = time.time() + t
    while time.time() < end:
        if fn(): return True
        await asyncio.sleep(.3)
    return False
async def phase(pg): return (await pg.inner_text('#phName')) if await pg.locator('#room').is_visible() else ''
async def waitphase(pg, txt, t=8):
    end = time.time() + t
    while time.time() < end:
        if txt in await phase(pg): return True
        await asyncio.sleep(.3)
    return False
def to_vote(code):
    skip(11)
    for _ in range(60):
        r = peek(code); 
        if r['state'] == 'hints':
            ok = False
            for n in N:
                time.sleep(.12)
                if api(n, 'state', code=code).get('turn') == 'u_' + n:
                    api(n, 'hint', code=code, text='힌트'); ok = True; break
            if not ok: skip(31)
        elif r['state'] == 'discuss': skip(10)
        elif r['state'] in ('vote', 'revote'): return
        elif r['state'] == 'reveal': skip(11)
        else: raise SystemExit('to_vote: 예상 밖 단계 ' + r['state'])

async def main():
    srv = subprocess.Popen(['/usr/bin/python3', SERVER, '--bot', BOT, '--port', str(PORT), '--web', ROOT, '--no-tick'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try: post('/__lg/reset'); break
            except Exception: time.sleep(.2)
        async with async_playwright() as p:
            br = await p.chromium.launch(executable_path=CHROME)
            names = N[:4]; pg = {}; cx = {}
            for n in names: cx[n], pg[n] = await mk(br, n)
            # --- A. 서버 재시작 복원 (설명 중)
            code = newroom(names, dict(rounds=2, discuss_s=30))
            api(names[0], 'start', code=code)
            for n in names: await pg[n].reload()
            for n in names: await pg[n].wait_for_selector('#room:not([hidden])', timeout=8000)
            skip(11)
            check('A 설명 단계 도착', await waitphase(pg[names[0]], '설명') or peek(code)['state'] == 'hints', peek(code)['state'])
            r0 = peek(code); liar0 = r0['secret']['liars'][0]; word0 = r0['secret']['word']
            post('/__lg/restart')
            await asyncio.sleep(2.5)
            r1 = peek(code)
            check('A 재시작 뒤 같은 방·같은 단계·같은 라이어·같은 제시어', r1['state'] == r0['state'] and r1['secret']['liars'] == [liar0] and r1['secret']['word'] == word0, (r0['state'], r1['state']))
            ln = liar0[2:]
            body = await pg[ln].inner_text('body')
            check('A 재시작 뒤에도 라이어 화면에 제시어 없음', word0 not in body)
            cit = [n for n in names if n != ln][0]
            check('A 재시작 뒤 시민 화면엔 제시어가 있다', word0 in await pg[cit].inner_text('body'))
            # 진행 계속
            to_vote(code)
            check('A 재시작 뒤 투표 단계까지 이어진다', peek(code)['state'] in ('vote', 'revote'))
            # --- B. 동률 → 재투표 → 그래도 동률 → 라이어 승
            code = newroom(names, dict(rounds=1, discuss_s=30)); api(names[0], 'start', code=code)
            for n in names: await pg[n].reload(); await pg[n].wait_for_selector('#room:not([hidden])', timeout=8000)
            to_vote(code)
            check('B 투표 단계 화면', await waitphase(pg[names[0]], '투표'), await phase(pg[names[0]]))
            a, b = 'u_' + names[0], 'u_' + names[1]
            api(names[0], 'vote', code=code, target=b); api(names[1], 'vote', code=code, target=a)
            api(names[2], 'vote', code=code, target=a); api(names[3], 'vote', code=code, target=b)
            skip(4)   # 전원이 투표했으니 서버가 마감을 3초 뒤로 당긴다
            check('B 동률이면 재투표로 간다', await waitphase(pg[names[2]], '재투표') or peek(code)['state'] == 'revote', await phase(pg[names[2]]))
            txt = await pg[names[2]].inner_text('#bMain')
            check('B 재투표 화면에 동률 후보 안내', '동률' in txt or '후보' in txt, txt[:100])
            api(names[0], 'vote', code=code, target=b); api(names[1], 'vote', code=code, target=a)
            api(names[2], 'vote', code=code, target=a); api(names[3], 'vote', code=code, target=b)
            skip(4)
            check('B 또 동률이면 결과로(라이어 승)', await waitphase(pg[names[0]], '결과', 8) and peek(code)['state'] == 'result', peek(code)['state'])
            t = await pg[names[0]].inner_text('#bMain')
            check('B 결과 화면: 라이어 승 표시', '라이어' in t and ('라이어 승' in t or '라이어가 이겼' in t or '승리' in t), t[:150])
            # --- C. 라이어 지목 → 마지막 기회 → 맞힘 → 라이어 뒤집기
            code = newroom(names, dict(rounds=1, discuss_s=30)); api(names[0], 'start', code=code)
            for n in names: await pg[n].reload(); await pg[n].wait_for_selector('#room:not([hidden])', timeout=8000)
            to_vote(code)
            r = peek(code); L = r['secret']['liars'][0]; W = r['secret']['word']
            for n in names: api(n, 'vote', code=code, target=L if 'u_' + n != L else 'u_' + names[0] if L != 'u_' + names[0] else 'u_' + names[1])
            skip(4)
            ln = L[2:]
            check('C 지목되면 마지막 기회 단계', await waitphase(pg[ln], '마지막') or peek(code)['state'] == 'guess', peek(code)['state'])
            await pg[ln].wait_for_selector('#guessForm', state='visible', timeout=6000)
            check('C 다른 사람에겐 입력창이 없다', not [n for n in names if n != ln and await pg[n].locator('#guessForm').is_visible()])
            await pg[ln].fill('#guessIn', W); await pg[ln].click('#guessBtn')
            check('C 맞히면 결과 단계', await until(lambda: peek(code)['state'] == 'result', 8), peek(code)['state'])
            await asyncio.sleep(1.5)
            t = await pg[names[0]].inner_text('#bMain')
            check('C 결과: 라이어가 제시어를 맞혀 뒤집었다고 보인다', W in t and '라이어' in t, t[:160])
            # 틀린 경우
            code = newroom(names, dict(rounds=1, discuss_s=30)); api(names[0], 'start', code=code)
            for n in names: await pg[n].reload(); await pg[n].wait_for_selector('#room:not([hidden])', timeout=8000)
            to_vote(code)
            r = peek(code); L = r['secret']['liars'][0]
            for n in names: api(n, 'vote', code=code, target=L if 'u_' + n != L else 'u_' + (names[0] if L != 'u_' + names[0] else names[1]))
            skip(4); ln = L[2:]
            await pg[ln].wait_for_selector('#guessForm', state='visible', timeout=6000)
            await pg[ln].fill('#guessIn', '엉뚱한말'); await pg[ln].press('#guessIn', 'Enter')
            check('C 틀리면 결과(시민 승)', await until(lambda: peek(code)['state'] == 'result', 8))
            await asyncio.sleep(1.5)
            t = await pg[[n for n in names if n != ln][0]].inner_text('#bMain')
            check('C 시민 화면에 시민 승 문구', '시민' in t, t[:120])
            # --- D. 바보 라이어
            code = newroom(names, dict(rounds=1, discuss_s=30, mode='fool')); api(names[0], 'start', code=code)
            for n in names: await pg[n].reload(); await pg[n].wait_for_selector('#room:not([hidden])', timeout=8000)
            await asyncio.sleep(1.5)
            r = peek(code); L = r['secret']['liars'][0]; ln = L[2:]
            fb = await pg[ln].inner_text('#rcard')
            check('D 바보 라이어 화면에는 「라이어」라는 말이 없다', '라이어입니다' not in fb and '당신은 라이어' not in fb, fb[:100])
            # --- E. 라이어 2명(8명)
            names8 = N[:8]
            for n in names8[4:]: cx[n], pg[n] = await mk(br, n)
            code = newroom(names8, dict(rounds=1, discuss_s=30, liars=2)); api(names8[0], 'start', code=code)
            for n in names8: await pg[n].reload(); await pg[n].wait_for_selector('#room:not([hidden])', timeout=8000)
            await asyncio.sleep(1.5)
            r = peek(code); Ls = r['secret']['liars']
            check('E 라이어 2명으로 시작', len(Ls) == 2, Ls)
            leak = [n for n in names8 if ('u_' + n) in Ls and r['secret']['word'] in await pg[n].inner_text('body')]
            check('E 라이어 두 명 화면 모두 제시어 없음', not leak, leak)
            to_vote(code)
            for n in names8: api(n, 'vote', code=code, target=Ls[0] if 'u_' + n != Ls[0] else Ls[1])
            skip(4)
            check('E 8명판이 결과/마지막 기회까지 간다', peek(code)['state'] in ('guess', 'result'), peek(code)['state'])
            for n in names8: check(f'콘솔 오류 0 ({n})', not pg[n]._errs, pg[n]._errs[:2])
            await br.close()
    finally:
        srv.terminate()
    print('\n' + ('ALL PASS' if not fails else f'FAILED {len(fails)}: {fails}'))
    sys.exit(1 if fails else 0)
asyncio.run(main())
