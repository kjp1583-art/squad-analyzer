#!/usr/bin/env python3
"""라이어 게임 화면 캡처(눈으로 확인용) — 가짜 서버로 각 단계를 PC 4해상도 + 폰으로 찍는다.
사용: SHOTS=<폴더> CHROME=... python3.13 tests/liar_shots.py [해상도목록 예 1280x720,390x800] [인원수]"""
import asyncio, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import liar_fake_server as FS
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
OUT = os.environ.get('SHOTS', '/tmp/lgshots'); os.makedirs(OUT, exist_ok=True)
srv = FS.serve(0); BASE = f'http://127.0.0.1:{srv.server_address[1]}'
URL = 'file://' + os.path.join(ROOT, 'liar.html') + f'?api={BASE}'
def post(path, obj=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(obj or {}).encode(), headers={'Content-Type': 'application/json'}); return json.load(urllib.request.urlopen(r))
SIZES = [tuple(map(int, x.split('x'))) for x in (sys.argv[1] if len(sys.argv) > 1 else '1280x720,1366x768,1920x1080,2560x1440,390x800').split(',')]
NP = int(sys.argv[2]) if len(sys.argv) > 2 else 8
NAMES = ['호스트', '시민둘', '시민셋', '라이어님', '다섯째', '여섯째사람', '일곱째', '여덟째', '아홉째', '열째이름이길다']
U = [f'u{i}' for i in range(1, NP + 1)]
LIAR = 'u4' if NP >= 4 else 'u2'
WORD = '김치찌개'
def players(voted=(), hinted=()): return [{'uid': u, 'name': NAMES[i], 'online': True, 'away': False, 'host': i == 0, 'score': i, 'voted': u in voted, 'hinted': u in hinted} for i, u in enumerate(U)]
def view(uid, state, **kw):
    base = {'state': state, 'host': 'u1', 'deadline': time.time() + 30, 'turn': None, 'round': 1, 'rounds': 2, 'opts': {'rounds': 2, 'discuss_s': 90, 'mode': 'normal', 'category': '', 'liars': 1, 'max': 10},
            'players': players(), 'my': {'role': None, 'category': None, 'word': None, 'fool': False}, 'hints': [], 'msgs': [], 'votes': None, 'result': None}
    if state in ('reveal', 'hints', 'discuss', 'vote', 'revote', 'guess'):
        base['my'] = {'role': 'liar', 'category': '음식', 'word': None, 'fool': False} if uid == LIAR else {'role': 'citizen', 'category': '음식', 'word': WORD, 'fool': False}
    base.update(kw); return base
def setroom(code, state, **kw): return post('/__set', {'code': code, 'views': {u: view(u, state, **kw) for u in U}})
async def mk(br, uid, w, h, rm=False):
    ctx = await br.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce' if rm else 'no-preference')
    await ctx.add_init_script(f"try{{localStorage.setItem('sgg_dc',JSON.stringify({{id:'{uid}',name:'{uid}',token:'tok-{uid}',exp:Date.now()+86400000}}));localStorage.setItem('lg_mute','1');}}catch(e){{}}")
    pg = await ctx.new_page(); pg._errs = []; pg.on('pageerror', lambda e: pg._errs.append(str(e))); return ctx, pg
async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME)
        for (w, h) in SIZES:
            tag = f'{w}x{h}_n{NP}'; print('==', tag)
            for who, uid in ((('cit', 'u2'),) if os.environ.get('QUICK') else (('cit', 'u2'), ('liar', LIAR))):
                post('/__reset'); ctx, pg = await mk(br, uid, w, h)
                hs = [{'uid': 'u2', 'name': NAMES[1], 'round': 1, 'text': '빨갛고 매워요', 't': 1}, {'uid': 'u3', 'name': NAMES[2], 'round': 1, 'text': '겨울에 먹으면 따뜻해요', 't': 2}]
                async def S(n): await pg.screenshot(path=f'{OUT}/{tag}_{who}_{n}.png')
                setroom('ROOM', 'lobby', deadline=0); await pg.goto(URL + '#ROOM'); await pg.wait_for_timeout(2600); await S('1lobby')
                if who == 'cit' or True:
                    setroom('ROOM', 'reveal'); await pg.wait_for_timeout(700); await S('2reveal_dark'); await pg.wait_for_timeout(2200); await S('2reveal_card')
                    setroom('ROOM', 'hints', turn='u3', hints=hs[:1], players=players(hinted=('u2',))); await pg.wait_for_timeout(1500)
                    setroom('ROOM', 'hints', turn='u3', hints=hs, players=players(hinted=('u2', 'u3')), round=1); await pg.wait_for_timeout(1500); await S('3hints')
                    if uid == 'u2':
                        setroom('ROOM', 'hints', turn='u2', hints=hs[:1]); await pg.wait_for_timeout(1500); await S('3hints_myturn')
                    setroom('ROOM', 'discuss', hints=hs); await pg.wait_for_timeout(800)
                    ms = [{'id': i + 1, 'uid': f'u{(i % NP) + 1}', 'name': NAMES[i % NP], 'text': t, 'sys': False, 't': i} for i, t in enumerate(['저는 처음부터 이상했어요', '힌트가 너무 애매하지 않나요?', '아니에요 저 시민이에요!', '라이어님이 제일 수상해요'])]
                    setroom('ROOM', 'discuss', hints=hs, msgs=ms); await pg.wait_for_timeout(1400); await S('4discuss')
                    setroom('ROOM', 'vote', deadline=time.time() + 9, players=players(voted=('u2', 'u3'))); await pg.wait_for_timeout(1500)
                    sel = 'button.pc[data-uid=u3]' if uid != 'u3' else 'button.pc[data-uid=u2]'
                    await pg.locator('#bMain ' + sel).click(); await pg.wait_for_timeout(900); await S('5vote_pointing')
                    await pg.wait_for_timeout(3500); await S('5vote_tense')
                    setroom('ROOM', 'guess', turn=LIAR, accused=LIAR); await pg.wait_for_timeout(1500); await S('6guess')
                    votes = {u: (LIAR if u != LIAR else 'u2') for u in U}; votes['u2'] = LIAR; votes['u3'] = 'u1'
                    res = {'liar_uids': [LIAR], 'word': WORD, 'category': '음식', 'votes': votes, 'tally': {LIAR: sum(1 for v in votes.values() if v == LIAR), 'u1': 1, 'u2': 1}, 'accused': LIAR, 'caught': True, 'liar_guess': '떡볶이', 'liar_guess_ok': False, 'winner': 'citizen', 'points': {u: 2 for u in U if u != LIAR}, 'log': ['x'], 'names': {u: NAMES[i] for i, u in enumerate(U)}}
                    setroom('ROOM', 'result', result=res, deadline=0); t0 = time.time()
                    TL = ((2.0, '7res_point'), (5.9, '7ann_typing'), (10.6, '7ann_slam'), (17.4, '7res_verdict'), (24, '7res_done')) if os.environ.get('QUICK') else ((2.0, '7res_point'), (4.2, '7res_accuse'), (5.9, '7ann_typing'), (7.4, '7ann_dots'), (9.6, '7ann_word'), (10.6, '7ann_slam'), (12.6, '7res_liar'), (14.6, '7res_guess'), (17.4, '7res_verdict'), (26, '7res_done'))
                    for k, name in TL:
                        await pg.wait_for_timeout(max(0, int((k - (time.time() - t0)) * 1000))); await S(name)
                    if os.environ.get('QUICK'): print(tag, who, 'errs', pg._errs[:3]); await ctx.close(); continue
                    res2 = dict(res, winner='liar', caught=False, accused='u2', liar_guess=None, points={LIAR: 3})
                    setroom('ROOM', 'reveal'); await pg.wait_for_timeout(1500); setroom('ROOM', 'result', result=res2, deadline=0); await pg.wait_for_timeout(9000); await S('8liarwin_ann'); await pg.wait_for_timeout(5000); await S('8liarwin_reveal'); await pg.wait_for_timeout(4000); await S('8liarwin')
                print(tag, who, 'errs', pg._errs[:3]); await ctx.close()
        await br.close()
asyncio.run(main())
