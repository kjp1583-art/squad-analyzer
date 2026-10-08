# -*- coding: utf-8 -*-
"""🔗 고유 무기 × 공용 무기 콤보 17개 — 각 콤보 재료가 실제 무기 키이고(공용 무기는 전용 무기가 아님), 둘 다 있으면 켜지고 하나만 있으면 안 켜지는지. 사용: python3 tests/survivors_unique_combo_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:220] if x and not c else ''))
    if not c: FAILS.append(n)
RUN = r"""async ()=>{ const x=__p6x; x.start(); const S=x.S; const out=[]; const syn=[...document.querySelectorAll('x')]; 
  const SYN=x.SYN; const res=[];
  for(const y of SYN.filter(y=>y.k.startsWith('u_'))){
    const [u,c]=y.req; const okKeys=!!x.WEAP[u]&&!!x.WEAP[c]&&x.WEAP[u].only&&!x.WEAP[c].only;
    S.w={}; S.w[u]=1; S.w[c]=1; x.synCalc(); const both=S.synOn.includes(y.k);
    S.w={}; S.w[u]=1; x.synCalc(); const one=S.synOn.includes(y.k);
    res.push({k:y.k,u,c,okKeys,both,one,fx:y.fx,ch:x.WEAP[u].only});}
  S.w={}; x.synCalc(); return res; }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate(RUN)
        check('콤보 17개', len(r) == 17, len(r))
        for y in r:
            check('%s: 재료가 실제 무기(고유 + 공용)' % y['k'], y['okKeys'], y)
            check('%s: 둘 다 있으면 켜지고 하나면 안 켜진다' % y['k'], y['both'] and not y['one'], y)
        check('고유 무기 17종이 각자 콤보 1개씩(용조련사 제외)', len({y['u'] for y in r}) == 17, [y['u'] for y in r])
        check('스크립트 오류 없음', not errs, errs); await b.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
