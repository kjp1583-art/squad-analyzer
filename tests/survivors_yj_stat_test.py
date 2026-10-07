# -*- coding: utf-8 -*-
"""🐲 용조련사 기본 스탯 하향 — HP +40 · 받는 피해 -2. 사용: python3 tests/survivors_yj_stat_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
R = r"""async ()=>{const x=__p6x; x.CH_set('yj'); x.start(); const S=x.S; const c=x.CHARS.find(c=>c.k==='yj'); return {hp:c.hp,arm:c.arm,spd:c.spd,mhp:S.p.mhp,ds:c.ds.slice(0,40)}}"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate(R); print(r)
        ok = r['hp'] == 40 and r['arm'] == 2 and abs(r['spd'] + .1) < 1e-9 and '+40' in r['ds'] and '-2' in r['ds'] and not errs
        print(('PASS' if ok else 'FAIL'), '용조련사 HP +40 · 받는 피해 -2 · 이동속도 -10%'); await b.close(); return 0 if ok else 1
sys.exit(asyncio.run(main()))
