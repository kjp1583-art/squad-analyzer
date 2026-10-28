# -*- coding: utf-8 -*-
"""🥊 태웅 씩씩 박치기 × 보스 — [2026-10-15 사장님] 「씩씩 박치기는 쓸 때 무조건 맞아서 보스전이 불가능」
 A. 보스 쪽으로 돌진하면 몸통 안에 박히지 않고 닿는 거리 밖에서 멈춘다(착지 직후 몸 박치기를 안 맞는다) — 박치기 피해는 보스에게 들어간다.
 B. 보스 코앞에서도 제자리 박치기가 나간다(피해는 들어간다). C. 일반 적에게는 예전처럼 돌진(길이 그대로).
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
EX = "window.__rb={ramGo,get S(){return S}};"
JS = r"""
(()=>{const X=window.__p6x;
function begin(){X.CH_set('tw');X.start();const S=X.S;S.t=300;S.p.hp=S.p.mhp=1e9;for(const o of X.enemies.a)o.on=false;S.w.ram=8;return S;}
window.__rt={
 boss(dist){const S=begin();const b=X.spawnBoss('sr');b.hp=b.mhp=1e12;b.sp=0;b.x=S.p.x+dist;b.y=S.p.y;b.atk=[];
   const h0=b.hp;S.cd.ram=0;const ok=window.__rb.ramGo();let minD=1e9;const hp0=S.p.hp;for(let i=0;i<8;i++){X.update(1/30);minD=Math.min(minD,Math.hypot(b.x-S.p.x,b.y-S.p.y));}
   return {ok,minD,gap:minD-(b.r+S.p.r),dealt:h0-b.hp,br:b.r,pr:S.p.r};},
 grunt(dist){const S=begin();const e=X.spawnEnemy(1,1);e.hp=e.mhp=1e9;e.sp=0;e.x=S.p.x+dist;e.y=S.p.y;S.cd.ram=0;const x0=S.p.x;const ok=window.__rb.ramGo();for(let i=0;i<8;i++)X.update(1/30);return {ok,moved:S.p.x-x0};}
};return true;})()
"""
async def main():
    p = H.make_copy('survivors.html', 'survivors_ramb.html', extra=EX)
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=800, h=600, page='survivors_ramb.html')
        await pg.evaluate(JS)
        A = await pg.evaluate('__rt.boss(200)'); print('A', A)
        ok(A['ok'] and A['gap'] > 2 and A['dealt'] > 0, 'A 보스 몸통에 박히지 않고(간격 %.1f) 피해는 들어간다(%.0f)' % (A['gap'], A['dealt']))
        B = await pg.evaluate('__rt.boss(60)'); print('B', B)
        ok(B['ok'] and B['dealt'] > 0, 'B 보스 코앞에서도 제자리 박치기 피해가 들어간다(%.0f)' % B['dealt'])
        C = await pg.evaluate('__rt.grunt(200)'); print('C', C)
        ok(C['ok'] and C['moved'] > 100, 'C 일반 적에게는 예전처럼 돌진한다(%.0f)' % C['moved'])
        ok(not errs, '오류 0 %s' % errs[:3])
        await b.close()
    srv.close()
    try: os.remove(p)
    except Exception: pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0
if __name__ == '__main__': sys.exit(asyncio.run(main()))
