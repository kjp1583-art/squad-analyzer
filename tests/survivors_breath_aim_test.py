# -*- coding: utf-8 -*-
"""🔥 용조련사 드래곤 브레스 자동 조준 — 가까운 적 방향으로 나가고, 적이 없으면 움직이는 방향. 사용: python3 tests/survivors_breath_aim_test.py"""
import asyncio, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:200] if x and not c else ''))
    if not c: FAILS.append(n)
RUN = r"""async (mode)=>{ const x=__p6x; x.CH_set('yj'); x.start(); const S=x.S,p=S.p; S.p.hp=S.p.mhp;
  for(const e of x.enemies.a)e.on=false; p.mdx=1;p.mdy=0;   // 오른쪽으로 움직이는 중
  let tgt=null; if(mode==='enemy'){ tgt=x.spawnEnemy(0,1,null,{x:p.x-120,y:p.y+0}); tgt.hp=tgt.mhp=1e9; }   // 왼쪽에 적 하나
  S.cd.breath=0; S.br.t=0; x.update(0.02);
  return {a:S.br.a,t:S.br.t,hp:tgt?tgt.hp<tgt.mhp:null,mdx:p.mdx}; }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for mode in ('enemy', 'none'):
            ctx, pg, errs = await H.new_page(b, srv.port)
            r = await pg.evaluate(RUN, mode)
            if mode == 'enemy':
                check('적이 왼쪽이면 움직이는 방향(오른쪽)이 아니라 왼쪽으로 쏜다', r['t'] > 0 and abs(abs(r['a']) - math.pi) < 0.3, r)
                check('그 적이 실제로 맞는다', r['hp'] is True, r)
            else:
                check('적이 없으면 움직이는 방향(오른쪽)으로', r['t'] > 0 and abs(r['a']) < 0.3, r)
            check('스크립트 오류 없음(%s)' % mode, not errs, errs)
            await ctx.close()
        await b.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
