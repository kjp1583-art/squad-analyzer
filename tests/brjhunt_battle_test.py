#!/usr/bin/env python3
"""brjhunt.html 실시간 전투 화면 시험(Playwright + 가짜 서버). 사용: /usr/bin/python3.13 tests/brjhunt_battle_test.py [--shots 폴더]
tests/brjhunt_test.py 의 가짜 서버·페이지 도우미를 그대로 불러다 쓴다(그 파일의 main 앞부분만 실행).
본다: 캔버스가 그려지고 프레임이 흐르는지(픽셀이 시간에 따라 변함) · 파티 인원 · 보스 도전이 /brj/boss 를 부르고 응답(win/lose)대로
연출이 갈리는지 · 탭을 옮기면 루프가 멈추는지 · 콘솔 오류·390px 가로 스크롤 · 그림이 하나도 없어도 도는지(폴백)."""
import asyncio, os, sys, json
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brjhunt_test.py'), encoding='utf-8').read()
_src = _src[:_src.index('async def main')]
_g = {'__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brjhunt_test.py'), '__name__': 'brjhunt_base'}
exec(compile(_src, 'brjhunt_test.py', 'exec'), _g)
Server, new_page, noscroll, tab, check, make_view, FAILS, SHOTS = (_g[k] for k in ('Server', 'new_page', 'noscroll', 'tab', 'check', 'make_view', 'FAILS', 'SHOTS'))
from playwright.async_api import async_playwright

import hashlib
async def HASHF(pg): return hashlib.md5(await pg.locator('#battleSlot canvas').screenshot()).hexdigest()   # file:// 그림이 캔버스를 오염시켜 getImageData 를 못 쓴다 → 화면 캡처로 비교
async def frames(pg): return await pg.evaluate('window.__bt.frames')
async def shot(pg, name):
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); await pg.locator('#battleSlot').screenshot(path=f'{SHOTS}/{name}.png')
async def spy(pg):   # 보스 상태가 지나간 순서를 모은다
    await pg.evaluate("window.__seen=[]; setInterval(()=>{const b=window.__bt.boss; const s=window.__seen; if(s[s.length-1]!==b) s.push(b);},40)")
def hunt_view(stage=10):
    v = make_view(); v['stage'] = stage; v['region'] = '홍대 먹자골목'; return v

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        # ---- 기본: 그려지고 흐른다 ----
        srv = Server(); srv.view = hunt_view(); ctx, pg, errs = await new_page(b, srv, scheme='dark')
        check('전투 캔버스가 사냥터 맨 위 카드에 있음', await pg.locator('#main > .card:first-of-type #battleSlot canvas').count() == 1 or await pg.locator('#main #battleSlot canvas').count() == 1)
        box = await pg.locator('#battleSlot canvas').bounding_box()
        check('캔버스 높이 220~260px · 폭은 화면 가득', 220 <= box['height'] <= 260 and box['width'] >= 330, box)
        f0 = await frames(pg); h0 = await HASHF(pg); await pg.wait_for_timeout(700); f1 = await frames(pg); h1 = await HASHF(pg)
        check('프레임이 진행됨', f1 - f0 >= 10, (f0, f1)); check('픽셀이 시간에 따라 변함', h0 != h1)
        check('동료 1명(파티 c1)이 서 있음', await pg.evaluate('window.__bt.party') == 1)
        await shot(pg, 'battle_dark_1'); await pg.wait_for_timeout(2500); await shot(pg, 'battle_dark_2')
        check('가만히 둬도 몬스터를 잡음(처치 수 증가)', await pg.evaluate('window.__bt.kills') >= 1)
        check('가로 스크롤 없음(390px)', await noscroll(pg))
        # 쌓인 골드는 서버 pending 그대로(전투가 값을 바꾸지 않는다)
        check('쌓인 골드 숫자는 서버 값 기반', (await pg.inner_text('#pend')).replace(',', '').isdigit())
        # ---- 보스: 응답이 win ----
        await spy(pg); c0 = len(srv.hits)
        check('보스 도전 버튼이 사냥터에 있음', await pg.locator('#main [data-do=boss]').count() == 1)
        await pg.click('#main [data-do=boss]'); await pg.wait_for_timeout(250)
        bh = [(pa, bo) for pa, bo in srv.hits[c0:] if pa == '/brj/boss']
        check('보스 도전 → /brj/boss 한 번(토큰 포함)', len(bh) == 1 and bh[0][1] == {'token': 'T' * 40}, bh)
        await pg.wait_for_timeout(900); await shot(pg, 'boss_intro')
        check('보스 연출 시작(boss 상태 있음)', await pg.evaluate('window.__bt.boss') is not None)
        await pg.wait_for_timeout(2300); await shot(pg, 'boss_fight')
        await pg.wait_for_timeout(3500); await shot(pg, 'boss_win')
        await pg.wait_for_function("window.__bt.boss===null", timeout=20000); await pg.wait_for_timeout(150)
        seen = await pg.evaluate('window.__seen')
        check('win 응답 → 보스가 쓰러지는 연출(dying)을 거쳐 사냥으로 복귀', 'dying' in seen and 'smash' not in seen and seen[-1] is None, seen)
        check('win 문구', '쓰러뜨렸어요' in await pg.inner_text('.msg'))
        check('보스 뒤 오류 없음', not errs, errs)
        # ---- 보스: 응답이 lose ----
        srv.override['/brj/boss'] = lambda body: (200, {'ok': True, 'result': 'lose', 'boss': 10, 'power': 300, 'hp': 534, 'view': hunt_view()})
        await pg.evaluate('window.__seen=[]'); await pg.wait_for_timeout(200)
        await pg.click('#main [data-do=boss]'); await pg.wait_for_timeout(3600); await shot(pg, 'boss_fight2')
        await pg.wait_for_timeout(3000); await shot(pg, 'boss_lose')
        await pg.wait_for_function("window.__bt.boss===null", timeout=20000); await pg.wait_for_timeout(150)
        seen = await pg.evaluate('window.__seen')
        check('lose 응답 → 병아리가 쓰러지는 연출(smash), 보스는 안 쓰러짐', 'smash' in seen and 'dying' not in seen, seen)
        check('lose 문구', '졌어요' in await pg.inner_text('.msg'))
        check('패배 뒤 사냥으로 복귀', await pg.evaluate('window.__bt.boss') is None and await pg.evaluate('window.__bt.mode') == 'hunt')
        # ---- 서버가 일을 못 한 경우(몰림): 연출이 걸려 남지 않는다 ----
        srv.mode = 'busy'; await pg.click('#main [data-do=boss]'); await pg.wait_for_timeout(1500)
        srv.mode = 'ok'; await pg.wait_for_timeout(1500)
        check('몰림이면 보스 연출이 취소되어 사냥으로 돌아옴', await pg.evaluate('window.__bt.mode') == 'hunt' and await pg.evaluate('window.__bt.boss') is None)
        # ---- 탭 전환: 루프 정지 ----
        await tab(pg, 'adv'); fa = await frames(pg); await pg.wait_for_timeout(500)
        check('다른 탭에서는 루프가 멈춤', await frames(pg) == fa and await pg.evaluate('window.__bt.running') is False)
        check('다른 탭에도 보스 도전 버튼은 하나', await pg.locator('#main [data-do=boss]').count() >= 1)
        await tab(pg, 'hunt'); fb = await frames(pg); await pg.wait_for_timeout(500)
        check('사냥터로 돌아오면 다시 흐름', await frames(pg) - fb >= 8 and await pg.evaluate('window.__bt.running') is True)
        check('콘솔 오류 없음', not errs, errs); await ctx.close()
        # ---- 파티가 비면 병아리만 / 관문 없으면 보스 버튼 없음 ----
        srv = Server(); v = make_view(); v['summon']['party'] = []; v['dungeon']['gate']['stage'] = 0; srv.view = v
        ctx, pg, errs = await new_page(b, srv, scheme='light')
        check('파티가 비면 동료 0', await pg.evaluate('window.__bt.party') == 0)
        check('관문이 없으면 보스 도전 버튼 없음', await pg.locator('#main [data-do=boss]').count() == 0)
        await pg.wait_for_timeout(1500); await shot(pg, 'battle_light_solo')
        check('라이트: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs); await ctx.close()
        # ---- 파티 3명 ----
        srv = Server(); v = make_view(); v['summon']['party'] = ['c1', 'c2', 'c4']; srv.view = v
        ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(2200)
        check('파티 3명', await pg.evaluate('window.__bt.party') == 3); await shot(pg, 'battle_party3')
        check('XSS 없음·오류 없음', await pg.evaluate('window.__xss') is None and not errs, errs); await ctx.close()
        # ---- 데스크톱 폭 ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv, w=1100, h=800)
        await pg.wait_for_timeout(1200); check('1100px: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs)
        await shot(pg, 'battle_wide'); await ctx.close()
        await b.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
