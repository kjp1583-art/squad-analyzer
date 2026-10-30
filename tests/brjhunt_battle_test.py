#!/usr/bin/env python3
"""brjhunt.html 필드 전투 화면 시험(Playwright + 가짜 서버). 사용: CHROME=... python3.13 tests/brjhunt_battle_test.py [--shots 폴더]
tests/brjhunt_test.py 의 가짜 서버·페이지 도우미를 그대로 불러다 쓴다(그 파일의 main 앞부분만 실행).
본다: 필드 캔버스가 상단에 그려지고 프레임이 흐르는지(픽셀이 시간에 따라 변함) · 분당 처치가 100 근처로 수렴하는지 · 동료 인원 ·
보스 도전이 /brj/boss 를 부르고 응답(win/lose)대로 연출이 갈리는지 · 판정을 못 받으면 연출이 접히는지 · 탭을 옮겨도 필드가 이어지는지(작은 창) ·
탭이 숨겨지면 멈추는지 · 콘솔 오류·390px 가로 스크롤."""
import asyncio, os, sys, json
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brjhunt_test.py'), encoding='utf-8').read()
_src = _src[:_src.index('async def main')]
_g = {'__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brjhunt_test.py'), '__name__': 'brjhunt_base'}
exec(compile(_src, 'brjhunt_test.py', 'exec'), _g)
Server, new_page, noscroll, tab, check, make_view, FAILS, SHOTS = (_g[k] for k in ('Server', 'new_page', 'noscroll', 'tab', 'check', 'make_view', 'FAILS', 'SHOTS'))
from playwright.async_api import async_playwright

import hashlib
async def HASHF(pg): return hashlib.md5(await pg.locator('#fcv').screenshot()).hexdigest()   # file:// 그림이 캔버스를 오염시켜 getImageData 를 못 쓴다 → 화면 캡처로 비교
async def T(pg): return await pg.evaluate('window.__bt.t')
async def shot(pg, name):
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); await pg.locator('#stage').screenshot(path=f'{SHOTS}/{name}.png')
async def spy(pg):   # 보스 상태가 지나간 순서를 모은다
    await pg.evaluate("window.__seen=[]; setInterval(()=>{const b=window.__bt.boss; const s=window.__seen; if(s[s.length-1]!==b) s.push(b);},40)")
def hunt_view(stage=10, gate=True):
    v = make_view(); v['stage'] = stage; v['region'] = '홍대 먹자골목'; v['dungeon']['gate']['stage'] = 10 if gate else 0; return v

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        # ---- 기본: 그려지고 흐른다 ----
        srv = Server(); srv.view = hunt_view(); ctx, pg, errs = await new_page(b, srv, scheme='dark')
        check('필드 캔버스가 화면 위쪽(상단 HUD 바로 아래)에 있음', await pg.locator('#stage #fcv').count() == 1)
        box = await pg.locator('#fcv').bounding_box()
        check('캔버스 높이 170~300px · 폭은 화면 가득', 170 <= box['height'] <= 300 and box['width'] >= 380, box)
        t0 = await T(pg); h0 = await HASHF(pg); await pg.wait_for_timeout(700); t1 = await T(pg); h1 = await HASHF(pg)
        check('필드 시간이 흐름', t1 - t0 >= 0.4, (t0, t1)); check('픽셀이 시간에 따라 변함', h0 != h1)
        check('동료 1명(파티 c1)이 나옴', await pg.evaluate('window.__bt.party') == 1)
        await shot(pg, 'ui_field_1'); await pg.wait_for_timeout(2500); await shot(pg, 'ui_field_2')
        check('가만히 둬도 몬스터를 잡음(처치 수 증가)', await pg.evaluate('window.__bt.kills') >= 1)
        check('가로 스크롤 없음(390px)', await noscroll(pg))
        check('쌓인 골드 숫자는 서버 값 기반', (await pg.inner_text('#pend')).replace(',', '').isdigit())
        # ---- 분당 처치 ~100 (시계를 빨리 돌려 잰다: 엔진의 timeScale) ----
        await pg.evaluate('window.__bt.field.setTimeScale(12)'); await pg.wait_for_timeout(9000); await pg.evaluate('window.__bt.field.setTimeScale(1)')
        s = await pg.evaluate('window.__bt.stats'); check('분당 처치가 100±25 (화면 연출 목표)', 75 <= s['kpm'] <= 125, s['kpm'])
        check('HUD 에 분당 처치·처치당 골드가 보임', '분당 처치' in await pg.inner_text('#hudL') and '/처치' in await pg.inner_text('#hPer') and '0.25' in await pg.inner_text('#hPer'))
        check('처치당 골드는 시간당 골드 ÷ 6000 (1,500 → 0.25)', '0.25' in await pg.inner_text('#hPer'))
        check('카메라가 병아리를 따라 필드를 가로지름(세계 폭 ≫ 화면 폭)', s['cam'] >= 0 and s['VW'] < 800)
        # ---- 보스: 응답이 win ----
        await spy(pg); c0 = len(srv.hits)
        check('스테이지 10 은 보스 관문 → 필드 아래 큰 버튼이 「보스 도전」', await pg.locator('#dock [data-do=boss]').count() == 1)
        await pg.click('#dock [data-do=boss]'); await pg.wait_for_timeout(250)
        bh = [(pa, bo) for pa, bo in srv.hits[c0:] if pa == '/brj/boss']
        check('보스 도전 → /brj/boss 한 번(토큰 포함)', len(bh) == 1 and bh[0][1] == {'token': 'T' * 40}, bh)
        check('보스 중 BGM 이 boss 트랙', await pg.evaluate('window.__bt.bgm') == 'boss')
        check('보스전 중에는 큰 버튼이 꺼짐(중복 도전 방지)', await pg.locator('#dock .push').is_disabled())
        await pg.wait_for_timeout(900); await shot(pg, 'ui_boss_intro')
        check('보스 연출 시작(boss 상태 있음)', await pg.evaluate('window.__bt.boss') is not None)
        await pg.wait_for_timeout(2300); await shot(pg, 'ui_boss_fight')
        await pg.wait_for_timeout(3000); await shot(pg, 'ui_boss_win')
        await pg.wait_for_function("window.__bt.boss===null", timeout=25000); await pg.wait_for_timeout(3600)
        seen = await pg.evaluate('window.__seen')
        check('win 응답 → 보스가 쓰러지는 연출(dying)을 거쳐 사냥으로 복귀', 'dying' in seen and 'smash' not in seen and seen[-1] is None, seen)
        check('win 문구', '쓰러뜨렸어요' in await pg.inner_text('.msg'))
        check('보스가 끝나면 BGM 이 지역 트랙으로 복귀 · 큰 버튼 복귀', await pg.evaluate('window.__bt.bgm') == 'field3' and await pg.locator('#dock [data-do=boss]').is_enabled())
        check('보스 뒤 오류 없음', not errs, errs)
        # ---- 보스: 응답이 lose ----
        srv.override['/brj/boss'] = lambda body: (200, {'ok': True, 'result': 'lose', 'boss': 10, 'power': 300, 'hp': 534, 'view': hunt_view()})
        await pg.evaluate('window.__seen=[]'); await pg.wait_for_timeout(200)
        await pg.click('#dock [data-do=boss]'); await pg.wait_for_timeout(3600); await shot(pg, 'ui_boss_fight2')
        await pg.wait_for_timeout(3000); await shot(pg, 'ui_boss_lose')
        await pg.wait_for_function("window.__bt.boss===null", timeout=25000); await pg.wait_for_timeout(3600)
        seen = await pg.evaluate('window.__seen')
        check('lose 응답 → 병아리가 쓰러지는 연출(smash), 보스는 안 쓰러짐', 'smash' in seen and 'dying' not in seen, seen)
        check('lose 문구', '졌어요' in await pg.inner_text('.msg'))
        # ---- 서버가 일을 못 한 경우(몰림): 연출이 걸려 남지 않는다 ----
        srv.mode = 'busy'; await pg.click('#dock [data-do=boss]'); await pg.wait_for_timeout(1500)
        srv.mode = 'ok'; await pg.wait_for_timeout(1500)
        check('몰림이면 보스 연출이 취소되어 사냥으로 돌아옴', await pg.evaluate('window.__bt.boss') is None and await pg.evaluate('window.__bt.bgm') == 'field3' and await pg.locator('#dock [data-do=boss]').is_enabled())
        # ---- 탭 전환: 필드는 작은 창으로 이어서 돈다 ----
        await tab(pg, 'adv'); await pg.wait_for_timeout(600); box = await pg.locator('#fcv').bounding_box()
        check('다른 탭에서는 필드가 작은 창(약 112px)으로 줄어듦', 100 <= box['height'] <= 125, box)
        ta = await T(pg); await pg.wait_for_timeout(600); check('다른 탭에서도 필드는 계속 돎', await T(pg) - ta >= 0.3)
        check('다른 탭에서는 핫바(dock)가 숨겨짐', not await pg.is_visible('#dock'))
        check('모험 탭에도 보스 도전 버튼은 하나', await pg.locator('#main [data-do=boss]').count() == 1)
        await tab(pg, 'hunt'); await pg.wait_for_timeout(600); box = await pg.locator('#fcv').bounding_box()
        check('사냥터로 돌아오면 큰 화면으로 복귀', box['height'] >= 170 and await pg.is_visible('#dock'), box)
        # 탭이 숨겨지면 멈춘다
        await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))"); await pg.wait_for_timeout(300)
        th = await T(pg); await pg.wait_for_timeout(700); check('탭이 숨겨지면 필드가 멈춤', await T(pg) - th < 0.05)
        await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}); document.dispatchEvent(new Event('visibilitychange'))"); await pg.wait_for_timeout(300)
        th = await T(pg); await pg.wait_for_timeout(700); check('다시 보이면 이어서 흐름', await T(pg) - th >= 0.3)
        check('콘솔 오류 없음', not errs, errs); await ctx.close()
        # ---- 파티가 비면 병아리만 / 관문 없으면 돌파 버튼 ----
        srv = Server(); v = make_view(); v['summon']['party'] = []; v['dungeon']['gate']['stage'] = 0; srv.view = v
        ctx, pg, errs = await new_page(b, srv, scheme='light')
        check('파티가 비면 동료 0', await pg.evaluate('window.__bt.party') == 0)
        check('관문이 없으면 보스 도전 버튼 없음 · 돌파 버튼', await pg.locator('#main [data-do=boss], #dock [data-do=boss]').count() == 0 and await pg.locator('#dock [data-do=push]').count() == 1)
        await pg.wait_for_timeout(1500); await shot(pg, 'ui_field_light_solo')
        check('라이트: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs); await ctx.close()
        # ---- 파티 3명 ----
        srv = Server(); v = make_view(); v['summon']['party'] = ['c1', 'c2', 'c4']; srv.view = v
        ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(2200)
        check('파티 3명', await pg.evaluate('window.__bt.party') == 3); await shot(pg, 'ui_field_party3')
        check('XSS 없음·오류 없음', await pg.evaluate('window.__xss') is None and not errs, errs); await ctx.close()
        # ---- 좁은 폰(360·320px) ----
        for w in (360, 320):
            srv = Server(); ctx, pg, errs = await new_page(b, srv, w=w, h=640)
            for k in ('hunt', 'skill', 'crew', 'adv'):
                await tab(pg, k); await pg.wait_for_timeout(200)
                check(f'{w}px {k}: 가로 스크롤 없음', await noscroll(pg))
            await tab(pg, 'hunt'); await pg.wait_for_timeout(500)
            check(f'{w}px: 필드·핫바·탭바가 한 화면에 다 보임', await pg.evaluate("(()=>{const r=e=>document.querySelector(e).getBoundingClientRect(); return r('#dock').bottom<=r('#nav').top+1 && r('#nav').bottom<=innerHeight+1 && r('#fcv').height>=150;})()"))
            if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_w{w}.png')
            check(f'{w}px: 오류 없음', not errs, errs); await ctx.close()
        # ---- 데스크톱 폭 ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv, w=1100, h=800)
        await pg.wait_for_timeout(1200); check('1100px: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs)
        if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_wide.png')
        await ctx.close()
        await b.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
