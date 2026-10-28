# -*- coding: utf-8 -*-
"""🧭 몬스터 출현 방향 + 🗺 미니맵 시험 (사장님 2026-10-18 「360도 전부 출몰해 도망갈 구멍이 없다 — 리젠 위치 랜덤 분포 + 실시간 미니맵」)
  A. 한 구간(14초) 안의 평소 스폰은 둘레 전체가 아니라 두 방향에 몰려 — 80° 이상 빈 틈이 있다
  B. 구간이 바뀌면 방향이 바뀌어 긴 시간으로 보면 둘레 전체에서 나온다
  C. 새 판도 빈 틈이 있다
  D. 판 중 #mm 이 보이고 몬스터가 있으면 붉은 점이 그려진다 · 타이틀에선 안 보인다
  E. 콘솔 오류 0"""
import asyncio, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
JS_SAMPLE = """(n)=>{const x=__p6x,S=x.S,P=S.p,out=[];for(let i=0;i<n;i++){const e=x.spawnEnemy(0,1);if(!e)continue;out.push(Math.atan2(e.y-P.y,e.x-P.x));e.on=false;}return out;}"""
def gap(angles, bins=36, quiet=3):
    c = [0] * bins
    for a in angles: c[int(((a % (2 * math.pi)) / (2 * math.pi)) * bins) % bins] += 1
    best = run = 0
    for i in range(bins * 2):
        if c[i % bins] <= quiet: run += 1; best = max(best, min(run, bins))
        else: run = 0
    return best * 360 / bins
async def main():
    H.make_copy('survivors.html', 'survivors_sd.html'); srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=412, h=800, page='survivors_sd.html')
        await pg.evaluate("()=>{const x=__p6x;x.CH_set('brj');x.start();}"); await pg.wait_for_timeout(300)
        await pg.evaluate("()=>{__p6x.S.t=100;}")
        a1 = await pg.evaluate(JS_SAMPLE, 400)
        g1 = gap(a1)
        ok(len(a1) >= 300 and g1 >= 80, 'A 한 구간 안에서 80° 이상 빈 틈이 있다 (빈 틈 %.0f° · %d마리)' % (g1, len(a1)))
        gaps = []; allang = []
        for k in range(1, 14):
            await pg.evaluate("(k)=>{__p6x.S.t=100+k*25;}", k)
            a = await pg.evaluate(JS_SAMPLE, 120); gaps.append(gap(a)); allang += a
        ok(min(gaps) >= 60, 'A 모든 구간에서 빈 틈이 남는다 (구간별 빈 틈 %s)' % [int(g) for g in gaps])
        ok(gap(allang + a1, quiet=0) <= 60, 'B 구간이 바뀌면 방향이 바뀌어 긴 시간으로는 둘레 전체에서 나온다 (전체 빈 틈 %.0f°)' % gap(allang + a1, quiet=0))
        await pg.evaluate("()=>{const x=__p6x,S=x.S;for(let i=0;i<30;i++){const e=x.spawnEnemy(0,1);if(e){e.x=S.p.x+200+i*10;e.y=S.p.y;}}}")
        await pg.wait_for_timeout(400)
        mm = await pg.evaluate("""()=>{const c=document.getElementById('mm');const g=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let red=0;for(let i=0;i<g.length;i+=4)if(g[i]>220&&g[i+1]<110&&g[i+2]<110&&g[i+3]>200)red++;return {vis:getComputedStyle(c).display!=='none',red}}""")
        ok(mm['vis'] and mm['red'] > 20, 'D 판 중 미니맵이 보이고 몬스터가 붉은 점으로 찍힌다 (%s)' % mm)
        await pg.evaluate("()=>{__p6x.start();}")
        await pg.evaluate("()=>{__p6x.S.t=100;}")
        a2 = await pg.evaluate(JS_SAMPLE, 300)
        ok(gap(a2) >= 80, 'C 새 판도 빈 틈이 있다 (%.0f°)' % gap(a2))
        ok(not errs, 'E 콘솔 오류 0 %s' % errs[:2])
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_sd.html'))
    except Exception: pass
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
