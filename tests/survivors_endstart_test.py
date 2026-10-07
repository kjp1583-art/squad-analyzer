# -*- coding: utf-8 -*-
"""♾ '무한 모드로 시작' 체크 — 60분을 넘기면 결과 화면에서 멈추지 않고 곧바로 무한으로 이어간다. 체크 안 하면 예전처럼 결과 화면.
   사용: python3 tests/survivors_endstart_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:200] if x and not c else ''))
    if not c: FAILS.append(n)
RUN = r"""async (on)=>{ const x=__p6x; document.getElementById('endChk').checked=on; document.getElementById('hardChk').checked=false; document.getElementById('vhChk').checked=false;
  x.start(); const S=x.S; S.t=3598; let n=0; while(n<400){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play')break; S.p.hp=S.p.mhp; x.update(0.05); n++; if(S.t>=3601)break }
  return {state:x.state,endless:x.S.endless||0,won:!!x.S.won,auto:x.S.autoEnd||0,t:Math.floor(x.S.t)} }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for on in (True, False):
            ctx, pg, errs = await H.new_page(b, srv.port)
            r = await pg.evaluate(RUN, on)
            if on: check('체크하면 60분 뒤 결과 없이 무한으로 이어감', r['state'] == 'play' and r['endless'] == 1 and r['won'], r)
            else: check('체크 안 하면 예전처럼 결과 화면', r['state'] == 'result' and r['endless'] == 0 and r['won'], r)
            check('스크립트 오류 없음(%s)' % on, not errs, errs)
            await ctx.close()
        await b.close()
    srv.stop() if hasattr(srv, 'stop') else None
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
