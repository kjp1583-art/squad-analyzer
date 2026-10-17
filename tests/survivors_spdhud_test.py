# -*- coding: utf-8 -*-
"""⏩ 인게임 배속 버튼(#spdBtn) 시험 (사장님 2026-10-17 「ESC 를 안 누르고 인게임 화면에서 바로 1.5·2배속을 조정」)
  A. 판이 도는 중 HUD 에 버튼이 보인다 · 처음 라벨 ⏩1x  B. 구매자: 누를 때마다 1x → 1.5x → 2x → 1x, ESC 화면의 선택값·게임 속도가 같이 바뀐다
  C. 눌러도 판이 멈추지 않는다(state=play 유지)  D. 비구매자: 🔒1x · 눌러도 배속이 안 켜지고 안내 문구가 뜬다
  E. 폰 폭(320·360)에서 HUD 줄이 가로로 넘치지 않는다  F. 콘솔 오류 0"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
async def main():
    H.make_copy('survivors.html', 'survivors_shud.html'); srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        for w in (412, 360, 320):
            ctx, pg, errs = await H.new_page(b, srv.port, w=w, h=800, page='survivors_shud.html')
            await pg.evaluate("()=>{const x=__p6x;x.srvUnl(['spd2']);x.CH_set('brj');x.start();}")
            await pg.wait_for_timeout(300)
            st = lambda: pg.evaluate("()=>({t:document.getElementById('spdBtn').textContent,vis:!!document.getElementById('spdBtn').offsetParent,sel:document.getElementById('spdChk').value,state:__p6x.state,so:document.querySelector('.hrow').scrollWidth,co:document.querySelector('.hrow').clientWidth})")
            s0 = await st()
            if w == 412:
                ok(s0['vis'] and s0['t'] == '⏩1x', 'A 판 중 HUD 에 버튼이 보이고 처음엔 ⏩1x (%s)' % s0)
                seq = []
                for _ in range(4):
                    await pg.click('#spdBtn'); await pg.wait_for_timeout(120); seq.append(await st())
                ok([x['t'] for x in seq] == ['⏩1.5x', '⏩2x', '⏩1x', '⏩1.5x'], 'B 누를 때마다 1x→1.5x→2x→1x→1.5x (%s)' % [x['t'] for x in seq])
                ok([x['sel'] for x in seq] == ['1.5', '2', '0', '1.5'], 'B ESC 화면 선택값도 같이 바뀐다 (%s)' % [x['sel'] for x in seq])
                ok(all(x['state'] == 'play' for x in seq), 'C 눌러도 판이 멈추지 않는다')
                fast = await pg.evaluate("()=>{const t0=__p6x.S.t;return new Promise(r=>setTimeout(()=>r(__p6x.S.t-t0),1000));}")
                ok(fast > 1.2, 'B 1.5x 일 때 1초에 게임 시간이 1.2초 넘게 흐른다 (%.2f)' % fast)
            ok(s0['so'] <= s0['co'] + 1, 'E %dpx 에서 HUD 줄이 안 넘친다 (%d ≤ %d)' % (w, s0['so'], s0['co']))
            ok(not errs, 'F 콘솔 오류 0 (%dpx) %s' % (w, errs[:2]))
            await ctx.close()
        ctx, pg, errs = await H.new_page(b, srv.port, w=412, h=800, page='survivors_shud.html')
        await pg.evaluate("()=>{const x=__p6x;x.srvUnl([]);x.CH_set('brj');x.start();}"); await pg.wait_for_timeout(300)
        await pg.click('#spdBtn'); await pg.wait_for_timeout(200)
        s = await pg.evaluate("()=>({t:document.getElementById('spdBtn').textContent,sel:document.getElementById('spdChk').value,state:__p6x.state})")
        ok(s['t'] == '🔒1x' and s['sel'] == '0' and s['state'] == 'play', 'D 비구매자: 🔒1x · 배속 안 켜짐 · 판 계속 (%s)' % s)
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_shud.html'))
    except Exception: pass
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
