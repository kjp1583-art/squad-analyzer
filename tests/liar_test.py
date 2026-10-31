#!/usr/bin/env python3
"""라이어 게임 화면 시험 (liar.html) — 가짜 서버(tests/liar_fake_server.py)로 화면 각 단계·누출·이스케이프·카운트다운.
사용: CHROME=... python3.13 tests/liar_test.py"""
import asyncio, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import liar_fake_server as FS
from playwright.async_api import async_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
srv = FS.serve(0); PORT = srv.server_address[1]
BASE = f'http://127.0.0.1:{PORT}'
URL = 'file://' + os.path.join(ROOT, 'liar.html') + f'?api={BASE}'
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {info}'))
    if not cond: fails.append(name)
def post(path, obj=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(obj or {}).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
def getlog(): return json.load(urllib.request.urlopen(BASE + '/__log'))

XSS = '<img src=x onerror="window.__xss=1">'
XSS2 = '"><script>window.__xss=2</script>'
WORD = '김치찌개'
U = ['a1', 'b2', 'c3', 'd4', 'e5']
NAMES = {'a1': '호스트' + XSS, 'b2': '시민둘', 'c3': '시민셋' + XSS2, 'd4': '라이어님', 'e5': '아주아주아주아주긴이름아주아주아주아주긴이름아주아주아주'}
def players(voted=(), hinted=(), away=()):
    return [{'uid': u, 'name': NAMES[u], 'online': u not in away, 'away': u in away, 'host': u == 'a1', 'score': i, 'voted': u in voted, 'hinted': u in hinted} for i, u in enumerate(U)]
def view(uid, state, **kw):
    liar = uid == 'd4'
    base = {'state': state, 'host': 'a1', 'deadline': time.time() + 30 + FS.S['skew'], 'turn': None, 'round': 1, 'rounds': 2, 'opts': {'rounds': 2, 'discuss_s': 90, 'mode': 'normal', 'category': '', 'liars': 1, 'max': 8},
            'players': players(), 'my': {'role': None, 'category': None, 'word': None, 'fool': False}, 'hints': [], 'msgs': [], 'votes': None, 'result': None}
    if state in ('reveal', 'hints', 'discuss', 'vote', 'revote', 'guess'):
        base['my'] = {'role': 'liar', 'category': '음식', 'word': None, 'fool': False} if liar else {'role': 'citizen', 'category': '음식', 'word': WORD, 'fool': False}
    base.update(kw); return base
def setroom(code, state, **kw):
    kws = kw.pop('per', {})
    views = {u: view(u, state, **dict(kw, **kws.get(u, {}))) for u in U}
    return post('/__set', {'code': code, 'views': views})

async def mkctx(br, uid, w=1100, h=800):
    ctx = await br.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce')
    await ctx.add_init_script(f"try{{localStorage.setItem('sgg_dc',JSON.stringify({{id:'{uid}',name:'{uid}',token:'tok-{uid}',exp:Date.now()+86400000}}));localStorage.setItem('lg_mute','1');}}catch(e){{}}")
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text and 'Failed to load resource' not in m.text else None)
    pg._errs = errs; return ctx, pg

async def text(pg, sel): return await pg.inner_text(sel)
async def wait_for(pg, js, ms=6000):
    try: await pg.wait_for_function(js, timeout=ms); return True
    except Exception: return False

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME)
        # ---- 로그인 안 함 ----
        ctx0 = await br.new_context(viewport={'width': 390, 'height': 800}); pg0 = await ctx0.new_page()
        await pg0.goto(URL); await pg0.wait_for_timeout(300)
        check('로그인 안 했으면 안내와 로그인 버튼만', await pg0.locator('[data-a=login]').count() == 1 and await pg0.locator('#room').is_hidden())
        await ctx0.close()

        # ---- 로비 ----
        post('/__reset')
        post('/__lobby', {'ok': True, 'online': 7, 'me': {'stats': {'games': 5, 'liar_games': 2, 'liar_wins': 1, 'citizen_wins': 2, 'points': 9}},
            'rooms': [{'code': 'ROOM', 'name': XSS, 'host': XSS2, 'players': 3, 'max': 8, 'state': 'lobby', 'mode': 'normal'},
                      {'code': 'FULL', 'name': '꽉참', 'host': 'x', 'players': 8, 'max': 8, 'state': 'lobby', 'mode': 'fool'},
                      {'code': 'PLAY', 'name': '진행중', 'host': 'x', 'players': 4, 'max': 8, 'state': 'hints', 'mode': 'normal'}]})
        ctx, pg = await mkctx(br, 'a1', 390, 800)
        await pg.goto(URL); ok = await wait_for(pg, "document.querySelectorAll('#roomList .room').length===3")
        check('로비: 공개 방 3개·접속자·전적 표시', ok and '접속 7명' in await text(pg, '#lbHead') and '라이어 1/2승' in await text(pg, '#lbHead'))
        check('로비: 방 이름·방장의 HTML 이 글자로만 나온다(XSS 없음)', await pg.evaluate('window.__xss') is None and '<img' in await text(pg, '#roomList'))
        check('로비: 꽉 찬 방·진행 중인 방은 입장 버튼이 없다', await pg.locator('#roomList [data-a=joinroom]').count() == 1)
        check('로비: 폰 폭에서 가로 스크롤 없음', await pg.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'))
        # 방 만들기
        setroom('NEWR', 'lobby', players=players()[:1], turn=None)
        await pg.fill('#cName', '내방'); await pg.select_option('#cMax', '6'); await pg.uncheck('#cPub'); await pg.select_option('#cMode', 'fool')
        await pg.click('#createBtn'); ok = await wait_for(pg, "!document.getElementById('room').hidden")
        lg = getlog()['log']; cr = [x for x in lg if x['path'] == '/lg/create']
        check('방 만들기: /lg/create 에 이름·인원·비공개·방식이 실려 간다', ok and cr and cr[0]['body']['name'] == '내방' and cr[0]['body']['max'] == 6 and cr[0]['body']['public'] is False and cr[0]['body']['opts']['mode'] == 'fool', cr)
        check('방 만들기: 이어서 방에 들어간다(코드 표시·주소 #NEWR)', await text(pg, '#rcode') == 'NEWR' and (await pg.evaluate('location.hash')) == '#NEWR')
        await ctx.close()

        # ---- 대기실: 방장 / 일반 참가자 ----
        post('/__reset'); setroom('ABCD', 'lobby', deadline=0, players=players(), msgs=[{'id': 1, 'uid': 'b2', 'name': '시민둘', 'text': '안녕' + XSS, 'sys': False, 't': 1}, {'id': 2, 'uid': None, 'name': '', 'text': '시민셋 님이 들어왔어요', 'sys': True, 't': 2}])
        ctxH, H = await mkctx(br, 'a1'); await H.goto(URL + '#ABCD')
        ok = await wait_for(H, "document.querySelectorAll('#bPlayers .pc').length===5")
        check('대기실(방장): 참가자 5명·시작 버튼·강퇴 버튼·옵션 선택 가능', ok and await H.locator('[data-a=start]:not([disabled])').count() == 1 and await H.locator('[data-a=kick]').count() == 4 and await H.locator('#o_rounds:not([disabled])').count() == 1)
        check('대기실: 이름·채팅의 HTML 이 글자로만 나온다', await H.evaluate('window.__xss') is None and await H.locator('#msgs img, #bPlayers img[onerror], #bPlayers script').count() == 0 and '안녕<img' in await text(H, '#msgs'))
        check('대기실: 채팅 두 줄(시스템 줄 포함)', await H.locator('#msgs .m').count() == 2 and await H.locator('#msgs .m.sys').count() == 1)
        await H.select_option('#o_rounds', '3'); await H.wait_for_timeout(300)
        lg = [x for x in getlog()['log'] if x['path'] == '/lg/opts']
        check('옵션 변경: /lg/opts 로 전체 옵션이 간다', lg and lg[-1]['body']['opts']['rounds'] == 3 and lg[-1]['body']['code'] == 'ABCD', lg)
        await H.click('[data-a=start]'); await H.wait_for_timeout(200)
        check('시작 버튼: /lg/start', any(x['path'] == '/lg/start' and x['uid'] == 'a1' for x in getlog()['log']))
        ctxG, G = await mkctx(br, 'b2'); await G.goto(URL + '#ABCD'); await wait_for(G, "document.querySelectorAll('#bPlayers .pc').length===5")
        check('대기실(참가자): 시작·강퇴 버튼 없음, 옵션 잠김', await G.locator('[data-a=start]').count() == 0 and await G.locator('[data-a=kick]').count() == 0 and await G.locator('#o_rounds[disabled]').count() == 1)
        # 채팅 전송 / 잠금 오류
        await G.fill('#chatIn', '반가워요'); await G.click('#chatBtn'); await G.wait_for_timeout(300)
        check('채팅 전송: /lg/chat 호출 후 입력칸 비움', any(x['path'] == '/lg/chat' and x['body']['text'] == '반가워요' for x in getlog()['log']) and await G.input_value('#chatIn') == '')
        post('/__fail', {'path': '/lg/chat', 'code': 'locked'}); await G.fill('#chatIn', '막힘'); await G.click('#chatBtn'); await G.wait_for_timeout(1700)
        check('채팅 잠김 응답: 안내가 뜨고 입력은 남는다', '할 수 없어요' in await text(G, '#toast') and await G.input_value('#chatIn') == '막힘')
        post('/__fail', {'path': '/lg/chat', 'code': None})
        # 새로고침 복귀
        await G.goto(URL); ok = await wait_for(G, "!document.getElementById('room').hidden && document.getElementById('rcode').textContent==='ABCD'")
        check('새로고침: 같은 로그인으로 방에 돌아온다', ok)
        await ctxG.close(); await ctxH.close()

        # ---- 게임 단계 × 역할 ----
        def hint(u, t, r=1, i=0): return {'uid': u, 'name': NAMES[u], 'round': r, 'text': t, 't': i}
        hs = [hint('b2', '빨갛고 매워요' + XSS, 1, 1), hint('c3', '겨울에 먹어요', 1, 2)]
        stages = {
            'reveal': dict(),
            'hints': dict(turn='a1', hints=hs, players=players(hinted=('b2', 'c3'))),
            'discuss': dict(hints=hs),
            'vote': dict(players=players(voted=('b2',))),
            'revote': dict(players=players(voted=())),
            'guess': dict(turn='d4', accused='d4'),
        }
        leaks = []
        cc = {}
        for uid in ('a1', 'd4'):
            cc[uid] = await mkctx(br, uid)
        post('/__reset')
        for st, kw in stages.items():
            setroom('GAME', st, **kw)
            for uid, (c, pg) in cc.items():
                if st == 'reveal': await pg.goto(URL + '#GAME')
                await wait_for(pg, f"document.getElementById('phName').textContent==='{ {'reveal':'역할 공개','hints':'설명 라운드','discuss':'자유 토론','vote':'투표','revote':'재투표','guess':'마지막 기회'}[st] }'")
                await pg.wait_for_timeout(120)
                body = await pg.inner_text('body'); html = await pg.content()
                if uid == 'd4' and (WORD in body or WORD in html): leaks.append((st, 'liar sees word'))
                if uid == 'a1' and '라이어 정체' in body: leaks.append((st, 'x'))
                if st != 'guess' and uid == 'a1' and 'liar' in (await pg.inner_html('#rcard')).lower().replace('class="rc cit"', ''): leaks.append((st, 'citizen sees liar card'))
                if await pg.evaluate('window.__xss') is not None: leaks.append((st, 'xss'))
                if not await pg.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'): leaks.append((st, 'hscroll'))
        check('전 단계×시민/라이어: 라이어 화면에 제시어 없음·XSS 없음·가로 스크롤 없음(PC)', not leaks, leaks)
        a, d = cc['a1'][1], cc['d4'][1]
        setroom('GAME', 'reveal'); await a.wait_for_timeout(1300)
        check('역할 공개: 시민은 제시어, 라이어는 라이어 카드', WORD in await text(a, '#rcard') and '라이어' in await text(d, '#rcard') and WORD not in await text(d, '#rcard'))
        setroom('GAME', 'hints', turn='a1', hints=hs, players=players(hinted=('b2', 'c3'))); await a.wait_for_timeout(1300)
        check('설명: 내 차례면 힌트 입력창이 열리고 채팅은 잠긴다', await a.locator('#hintForm').is_visible() and await a.locator('#chatIn[disabled]').count() == 1 and not await d.locator('#hintForm').is_visible())
        check('설명: 힌트 타임라인에 이스케이프된 힌트·현재 차례 강조', '빨갛고 매워요<img' in await text(a, '#bMain') and await a.locator('#bPlayers .pc.turn').count() == 1)
        await a.fill('#hintIn', '국물이 있어요'); await a.press('#hintIn', 'Enter'); await a.wait_for_timeout(300)
        check('힌트 전송: Enter 로 /lg/hint', any(x['path'] == '/lg/hint' and x['body']['text'] == '국물이 있어요' for x in getlog()['log']))
        setroom('GAME', 'discuss', hints=hs); await a.wait_for_timeout(1300)
        check('토론: 채팅이 열리고 힌트 입력창은 닫힌다', await a.locator('#chatIn:not([disabled])').count() == 1 and not await a.locator('#hintForm').is_visible())
        setroom('GAME', 'vote', players=players(voted=('b2',))); await a.wait_for_timeout(1300)
        check('투표: 후보 카드 5장·자기 자신은 비활성·완료 인원 표시', await a.locator('#bMain button.pc').count() == 5 and await a.locator('#bMain button.pc[disabled]').count() == 1 and '투표 완료 1/5' in await text(a, '#bMain'))
        await a.locator('#bMain button.pc[data-uid=d4]').click(); await a.wait_for_timeout(300)
        check('투표: 누르면 /lg/vote 와 "내 선택" 표시', any(x['path'] == '/lg/vote' and x['body']['target'] == 'd4' for x in getlog()['log']) and '내 선택' in await text(a, '#bMain'))
        await a.locator('#bMain [data-a=vote][data-uid=""]').click(); await a.wait_for_timeout(300)
        check('투표: 기권은 target null', [x for x in getlog()['log'] if x['path'] == '/lg/vote'][-1]['body']['target'] is None)
        post('/__fail', {'path': '/lg/vote', 'code': 'locked'}); await a.locator('#bMain button.pc[data-uid=c3]').click(); await a.wait_for_timeout(300)
        check('투표 마감 후 거절되면 선택 표시를 되돌리고 안내', '내 선택' not in await text(a, '#bMain') and await a.locator('#toast:not([hidden])').count() == 1)
        post('/__fail', {'path': '/lg/vote', 'code': None})
        setroom('GAME', 'guess', turn='d4', accused='d4'); await d.wait_for_timeout(1300)
        check('마지막 기회: 라이어에게만 추측 입력창', await d.locator('#guessForm').is_visible() and not await a.locator('#guessForm').is_visible())
        await d.fill('#guessIn', '김치찌개'); await d.click('#guessBtn'); await d.wait_for_timeout(300)
        check('추측 전송: /lg/guess', any(x['path'] == '/lg/guess' and x['uid'] == 'd4' for x in getlog()['log']))
        # ---- 결과 ----
        res = {'liar_uids': ['d4'], 'word': WORD + XSS, 'category': '음식', 'votes': {'a1': 'd4', 'b2': 'd4', 'c3': 'a1', 'd4': None, 'e5': 'd4'}, 'tally': {'d4': 3, 'a1': 1}, 'accused': 'd4', 'caught': True,
               'liar_guess': '떡볶이' + XSS2, 'liar_guess_ok': False, 'winner': 'citizen', 'points': {'a1': 2, 'b2': 2, 'c3': 1, 'e5': 2}, 'log': ['라이어는 ' + XSS, {'name': '시민둘', 'text': '빨갛고 매워요'}]}
        setroom('GAME', 'result', result=res, deadline=0); await a.wait_for_timeout(1500)
        t = await text(a, '#bMain')
        check('결과: 시민 승리·라이어 이름·득표 막대·점수표·전체 기록', '시민 승리' in t and await a.locator('.bars .br').count() == 2 and await a.locator('.pts tbody tr').count() == 5 and await a.locator('.log li').count() >= 4 and '3표' in t)
        check('결과: 서버 문자열 이스케이프(XSS 없음)', await a.evaluate('window.__xss') is None and await a.locator('#bMain img').count() == 0 and '<img' in t)
        check('결과: 방장은 다음 판 버튼, 라이어(참가자)는 없음', await a.locator('[data-a=next]').count() == 1 and await d.locator('[data-a=next]').count() == 0)
        # 결과 화면에서 라이어가 나가도(참가자·채팅에 없음) 서버가 준 result.names 로 이름이 보여야 한다
        res2 = dict(res, names={u: NAMES[u] for u in U})
        left = [p for p in players() if p['uid'] not in ('d4',)]
        setroom('GAME', 'result', result=res2, deadline=0, players=left); await a.wait_for_timeout(1500)
        t2 = await text(a, '#bMain')
        check('결과: 나간 라이어도 이름이 보임("(나간 사람)" 아님)', '라이어님' in t2 and '(나간 사람)' not in t2, t2[:200])
        setroom('GAME', 'result', result=res, deadline=0); await a.wait_for_timeout(1200)
        await a.click('[data-a=next]'); await a.wait_for_timeout(200)
        check('다음 판: /lg/next', any(x['path'] == '/lg/next' for x in getlog()['log']))
        await a.click('#leaveBtn'); await a.wait_for_timeout(500)
        check('나가기: /lg/leave 후 로비로', any(x['path'] == '/lg/leave' for x in getlog()['log']) and await a.locator('#scrLobby').is_visible())
        for uid in cc:
            errs = cc[uid][1]._errs
            check(f'콘솔 오류 0 ({uid})', not errs, errs[:3])
        for c, _ in cc.values(): await c.close()

        # ---- 카운트다운(서버 시각 보정) ----
        post('/__reset'); post('/__skew', {'s': 100})
        setroom('TIME', 'discuss', deadline=time.time() + 100 + 20)
        ctxT, T = await mkctx(br, 'b2'); await T.goto(URL + '#TIME'); await wait_for(T, "document.getElementById('tnum').textContent!==''")
        v = int((await text(T, '#tnum')).replace('초', '') or 0)
        check('카운트다운: 내 시계가 100초 어긋나도 서버 기준 약 20초', 17 <= v <= 20, v)
        await T.wait_for_timeout(2200); v2 = int((await text(T, '#tnum')).replace('초', ''))
        check('카운트다운: 시간이 줄어든다', v2 <= v - 1, (v, v2))
        # since 최적화: 같은 v 로는 메시지가 중복되지 않는다
        post('/__skew', {'s': 0}); post('/__reset')
        setroom('SINC', 'discuss', msgs=[{'id': 1, 'uid': 'a1', 'name': 'a', 'text': 'one', 'sys': False, 't': 1}])
        await T.goto('about:blank'); post('/__reset'); setroom('SINC', 'discuss', msgs=[{'id': 1, 'uid': 'a1', 'name': 'a', 'text': 'one', 'sys': False, 't': 1}]); await T.goto(URL + '#SINC'); await wait_for(T, "document.querySelectorAll('#msgs .m').length===1"); await T.wait_for_timeout(3300)
        hh = getlog()['hits'].get('/lg/state', 0); nm = await T.locator('#msgs .m').count(); check('폴링: 같은 버전이면 same 으로 오고 채팅이 중복되지 않는다', nm == 1 and hh >= 3, (nm, hh))
        # 연결 끊김 / 복구
        post('/__drop', {'on': True}); ok = await wait_for(T, "!document.getElementById('conn').hidden", 9000)
        check('서버가 끊기면 「연결 끊김」 표시', ok)
        post('/__drop', {'on': False}); ok = await wait_for(T, "document.getElementById('conn').hidden", 9000)
        check('서버가 돌아오면 표시가 사라진다(자동 복구)', ok)
        # 방이 사라지면 로비로
        post('/__reset'); ok = await wait_for(T, "document.getElementById('room').hidden", 5000)
        check('방이 없어지면 로비로 돌아간다', ok)
        check('콘솔 오류 0 (타이머 시험)', not T._errs, T._errs[:3])
        await ctxT.close()

        # ---- 폰 세로 + 긴 이름 + 결과/투표 가로 스크롤 ----
        post('/__reset'); setroom('PHON', 'vote', players=players(voted=('b2',)))
        ctxP, P = await mkctx(br, 'e5', 390, 800); await P.goto(URL + '#PHON'); await wait_for(P, "document.querySelectorAll('#bMain button.pc').length===5")
        check('폰 390px: 투표 화면 가로 스크롤 없음', await P.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'))
        setroom('PHON', 'result', result=res, deadline=0); await P.wait_for_timeout(1500)
        check('폰 390px: 결과 화면 가로 스크롤 없음', await P.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'))
        setroom('PHON', 'hints', turn='e5', hints=hs); await P.wait_for_timeout(1300)
        check('폰 390px: 설명 화면 가로 스크롤 없음·입력창 보임', await P.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth') and await P.locator('#hintForm').is_visible())
        # 음소거 버튼
        await P.click('#muteBtn'); check('음소거 버튼: 켜기/끄기 기억', await P.evaluate("localStorage.getItem('lg_mute')") == '0')
        check('콘솔 오류 0 (폰)', not P._errs, P._errs[:3])
        await ctxP.close(); await br.close()
    print('\n' + ('ALL PASS' if not fails else f'FAILED {len(fails)}: {fails}'))
    sys.exit(1 if fails else 0)
asyncio.run(main())
