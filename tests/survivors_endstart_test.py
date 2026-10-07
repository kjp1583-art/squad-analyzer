# -*- coding: utf-8 -*-
"""♾ 60분 클리어 뒤 '무한 모드로 진입하시겠습니까?' 선택지 — 일반·하드·베리하드 공통, 수락하면 무한으로 이어가고 거절하면 결과 화면.
   사용: python3 tests/survivors_endstart_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:200] if x and not c else ''))
    if not c: FAILS.append(n)
RUN = r"""async (mode)=>{ const x=__p6x; document.getElementById('hardChk').checked=(mode==='hard'); document.getElementById('vhChk').checked=(mode==='vhard');
  x.start(); const S=x.S; S.t=3598; let n=0; while(n<400){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play')break; S.p.hp=S.p.mhp; x.update(0.05); n++; if(S.t>=3601)break }
  const ask=document.getElementById('endAsk').classList.contains('on');
  return {state:x.state,endless:x.S.endless||0,won:!!x.S.won,ask,txt:document.getElementById('endAskTxt').textContent,hard:!!x.S.hard,vh:x.S.vh||0} }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for mode in ('normal', 'hard', 'vhard'):
            ctx, pg, errs = await H.new_page(b, srv.port)
            r = await pg.evaluate(RUN, mode)
            check('[%s] 60분 클리어 뒤 결과 화면 + 무한 선택지가 뜬다' % mode, r['state'] == 'result' and r['won'] and r['ask'] and '무한 모드로 진입하시겠습니까' in r['txt'], r)
            check('[%s] 시작 화면에 무한 시작 체크는 없다' % mode, await pg.evaluate("!document.getElementById('endChk')"))
            # 거절 → 결과 화면 그대로
            await pg.evaluate("document.getElementById('endNo').click()")
            r2 = await pg.evaluate("({state:__p6x.state,ask:document.getElementById('endAsk').classList.contains('on'),endless:__p6x.S.endless||0})")
            check('[%s] 거절하면 결과 화면에 머문다' % mode, r2['state'] == 'result' and not r2['ask'] and r2['endless'] == 0, r2)
            # 다시 시험: 수락
            r3 = await pg.evaluate(RUN, mode)
            await pg.evaluate("document.getElementById('endYes').click()")
            r4 = await pg.evaluate("({state:__p6x.state,ask:document.getElementById('endAsk').classList.contains('on'),endless:__p6x.S.endless||0,hard:!!__p6x.S.hard,vh:__p6x.S.vh||0})")
            check('[%s] 수락하면 무한 모드로 이어간다(난이도 유지)' % mode, r4['state'] == 'play' and r4['endless'] == 1 and not r4['ask'] and r4['hard'] == (mode != 'normal') and (r4['vh'] == 1) == (mode == 'vhard'), r4)
            check('[%s] 스크립트 오류 없음' % mode, not errs, errs)
            await ctx.close()
        # 오늘의 도전은 묻지 않는다
        ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate("""async ()=>{const x=__p6x; x.start({daily:true}); const S=x.S; if(!S.dly)return {skip:1}; S.t=3598; let n=0; while(n<400){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play')break; S.p.hp=S.p.mhp; x.update(0.05); n++; if(S.t>=3601)break }
          return {state:x.state,ask:document.getElementById('endAsk').classList.contains('on')} }""")
        check('오늘의 도전은 무한 선택지를 묻지 않는다', r.get('skip') or (not r['ask']), r)
        await ctx.close(); await b.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
