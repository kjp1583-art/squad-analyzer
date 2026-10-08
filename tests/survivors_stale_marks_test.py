# -*- coding: utf-8 -*-
"""🧹 판을 연달아 해도(새로고침 없이) 풀 칸을 재사용하는 적에게 이전 판의 표식(신림 도장 sg3 · 또뀨 사슬 ch3 · 태웅 박치기 rm · 앙앵 하트 hm)이 남지 않는다.
   표식이 남으면 새 판 S.t 가 0부터라 그 적을 한참 못 노린다 — 사용: python3 tests/survivors_stale_marks_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:220] if x and not c else ''))
    if not c: FAILS.append(n)
# 이전 판이 남긴 표식을 풀 전체에 찍어 놓고 새 판을 시작한다 → 새로 나온 적의 표식은 0 이어야 하고, 신림 도장·또뀨 사슬이 바로 일한다
RUN = r"""async (ch)=>{ const x=__p6x; x.CH_set(ch); x.start(); const S0=x.S;
  for(const e of x.enemies.a){e.sg3=99999;e.ch3=99999;e.rm=7;e.hm=7;}
  x.CH_set(ch); x.start(); const S=x.S, p=S.p; p.hp=p.mhp;
  for(const e of x.enemies.a)e.on=false;
  const es=[]; for(let i=0;i<4;i++){const e=x.spawnEnemy(0,1,null,{x:p.x+60+i*10,y:p.y+10*i}); if(e){e.hp=e.mhp=1e9; es.push(e);}}
  const marks=es.map(e=>[e.sg3,e.ch3,e.rm,e.hm]);
  S.w.stamp=3; S.w.chain=3; let n=0; while(n<200){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play')break; p.hp=p.mhp; x.update(0.05); n++; }
  return {marks, stamp:(S.dmgBy.stamp||0), chain:(S.dmgBy.chain||0), dmg:es.map(e=>e.mhp-e.hp)} }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for ch in ('sr', 'ddo'):
            ctx, pg, errs = await H.new_page(b, srv.port); r = await pg.evaluate(RUN, ch)
            check('[%s] 새 판에서 재사용된 적의 이전 판 표식이 0 으로 지워진다' % ch, r['marks'] and all(m == [0, 0, 0, 0] for m in r['marks']), r['marks'])
            check('[%s] 새 판 10초 안에 도장·사슬이 바로 일한다(표식에 막히지 않음)' % ch, (r['stamp'] if ch == 'sr' else r['chain']) > 0, r)
            check('[%s] 스크립트 오류 없음' % ch, not errs, errs); await ctx.close()
        await b.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
