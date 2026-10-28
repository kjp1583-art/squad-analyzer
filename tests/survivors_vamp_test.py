# -*- coding: utf-8 -*-
"""🥩 고기 반찬 하향 — 40마리 처치마다 HP +1.5(레벨당). 사용: python3 tests/survivors_vamp_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
RUN = r"""async ()=>{ const x=__p6x; x.CH_set('brj'); x.start(); const S=x.S; S.ps.vamp=2; S.p.mhp=1000; S.p.hp=100;
  const hp0=S.p.hp; let heals=[];
  for(let k=1;k<=80;k++){ const before=S.p.hp; const e=x.spawnEnemy(0,1,null,{x:S.p.x+300,y:S.p.y}); if(!e)continue; e.hp=1; x.hurt(e,1e6); if(S.p.hp>before)heals.push([k,+(S.p.hp-before).toFixed(2)]); }
  return {heals,ps:S.ps.vamp}; }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate(RUN); print(r)
        ok = len(r['heals']) == 2 and all(abs(h[1] - 3.0) < .05 for h in r['heals']) and r['heals'][0][0] in (39, 40, 41)
        print(('PASS' if ok else 'FAIL'), '40마리마다 +3(고기 반찬 Lv2 = 1.5×2), 80마리에 2번'); print('오류', errs)
        await b.close(); return 0 if ok and not errs else 1
sys.exit(asyncio.run(main()))
