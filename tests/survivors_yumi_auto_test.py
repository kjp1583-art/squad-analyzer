# -*- coding: utf-8 -*-
"""🍘 유미 고유능력 — 5초마다 가장 가까운 소모 아이템 1개 자동 획득(보스 상자 제외) + 경험치 줍는 범위 +40%. 사용: python3 tests/survivors_yumi_auto_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:220] if x and not c else ''))
    if not c: FAILS.append(n)
RUN = r"""async (ch)=>{ const x=__p6x; x.srvUnl&&x.srvUnl(['yumi']); x.CH_set(ch); x.start(); const S=x.S,p=S.p; S.p.hp=S.p.mhp; S.p.hp=1;
  for(const e of x.enemies.a)e.on=false;
  const mk=(k,dx)=>{const it=x.items.get();it.k=k;it.x=p.x+dx;it.y=p.y;it.life=1e9;it.t=0;return it;};
  const far=mk('chicken',900), mid=mk('magnet',600), near=mk('bomb',400), chest=mk('chest',300);   // 상자가 제일 가깝지만 제외돼야 한다
  const log=[]; let t=0; while(t<12.5){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play')break; S.p.hp=Math.max(S.p.hp,1); for(const e of x.enemies.a)e.on=false; x.update(0.05); t+=0.05;
    const st=[near.on,mid.on,far.on,chest.on].map(v=>v?1:0).join(''); if(!log.length||log[log.length-1][1]!==st)log.push([+t.toFixed(1),st]); }
  return {log,mag:(x.CH.mag||0),auto:x.CH.auto||0}; }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port); r = await pg.evaluate(RUN, 'yumi')
        lg = r['log']; print(lg)
        check('유미 설정: 줍는 범위 +40% · 자동 5초', abs(r['mag'] - .4) < 1e-9 and r['auto'] == 5, r)
        # 상태 문자열 = near,mid,far,chest — 5초쯤 첫 획득(폭탄=제일 가까운 소모 아이템), 10초쯤 두 번째(자석)
        t1 = [x for x in lg if x[1][0] == '0']; t2 = [x for x in lg if x[1][:2] == '00']
        check('5초쯤 가장 가까운 소모 아이템(폭탄)을 줍는다', bool(t1) and 4.8 <= t1[0][0] <= 5.4, lg)
        check('10초쯤 다음으로 가까운 것(자석)을 줍는다', bool(t2) and 9.8 <= t2[0][0] <= 10.6, lg)
        check('보스 상자는 자동으로 줍지 않는다', all(x[1][3] == '1' for x in lg), lg)
        check('스크립트 오류 없음', not errs, errs); await ctx.close()
        ctx, pg, errs = await H.new_page(b, srv.port); r = await pg.evaluate(RUN, 'brj')
        check('다른 캐릭터(브장신)는 자동으로 안 줍는다', all(x[1] == '1111' for x in r['log']) or len(r['log']) == 1, r['log'])
        await ctx.close(); await b.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
