# -*- coding: utf-8 -*-
"""🖥 기기·화면 무관 젠 시험 (2026-10-16 사장님 「해상도 같은 시점에 의해 몬스터 젠이 변경되는 건 아닌지」)
   같은 시드(오늘의 도전 판)로 PC(1600×900·코어16) · 폰(360×800·코어4=LOW) · 좁은 PC(1024×600·코어4) 에서
   ① 게임플레이 상수(적 수 상한·탄 풀·스폰/정리 거리)가 같고 ② 적을 못 죽이게 해 두고 2초마다 싹 치우며 세는 '시간별 출생 수' 가 똑같고
   ③ 새로 태어난 적이 그 기기의 보이는 화면 밖에서 나타나는지 확인한다.   사용: python3 tests/survivors_device_parity_test.py [OLD.html]  (OLD 를 주면 옛 판의 차이도 출력)"""
import asyncio, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_device_common as C, sv_harness as H
from playwright.async_api import async_playwright
DEV = {'PC': (1600, 900, 16, False), '폰': (360, 800, 4, True), '좁은PC': (1024, 600, 4, False)}
JS = r"""(a)=>{const x=window.__p6x,E=window.__dv,out=[],bad=[];let nextC=2,nextR=a.step,seen=0,minD=1e9,g=0;const dt=1/20;
 while(g<4e6){const st=x.state;if(st==='lvup'){x.pick(x.CUR[0]);continue;}if(st!=='play'){if(st==='result')break;x.resume();continue;}
  const S=x.S;if(S.t>=a.until)break;S.p.hp=S.p.mhp;S.p.x=0;S.p.y=0;x.keys={};
  for(const e of E.enemies.a)if(e.on){e.hp=e.mhp=1e15;}
  x.update(dt);g++;
  const hd=Math.hypot(E.VW,E.VH)/2;
  let bossOn=false;for(const e of E.enemies.a)if(e.on&&e.boss){bossOn=true;break;}
  if(!bossOn)for(const e of E.enemies.a)if(e.on&&e.sn>seen&&!e.boss){const d=Math.hypot(e.x-S.p.x,e.y-S.p.y);if(d<minD)minD=d;if(d<hd+10&&S.t>3)bad.push([Math.round(S.t),Math.round(d),Math.round(hd)]);}
  seen=E.SN;
  if(S.t>=nextC){for(const e of E.enemies.a)if(e.on&&!e.boss)e.on=false;nextC+=2;}
  if(S.t>=nextR){out.push([Math.round(S.t),E.SN]);nextR+=a.step;}}
 return {out,bad:bad.slice(0,3),nbad:bad.length,minD:Math.round(minD)};}"""
async def run(b, port, name, w, h, hwc, mob, until):
    ctx, pg, errs = await C.page(b, port, name, w, h, hwc, 777, mobile=mob)
    await pg.evaluate("window.__p6x.start({daily:true})")
    const = await pg.evaluate("({LOW:window.__p6x.LOW,MAXE:__dv.MAXE,SR:__dv.SPAWN_R,DR:__dv.DESP_R,eshots:__dv.eshots.a.length,shots:__dv.shots.a.length,props:__dv.props.a.length})")
    r = await pg.evaluate(JS, {'until': until, 'step': int(os.environ.get('DV_STEP', '120'))})
    await ctx.close(); return const, r, errs
async def main():
    files = {'NEW': os.path.join(H.ROOT, 'survivors.html')}
    if len(sys.argv) > 1: files['OLD'] = sys.argv[1]
    cp = {t: C.make(f, 'dvp_%s.html' % t) for t, f in files.items()}
    until = int(os.environ.get('DV_UNTIL', '1500')); srv = H.Srv(); fails = []; res = {}
    async with async_playwright() as p:
        b = await H.launch(p)
        for t, f in cp.items():
            for d, (w, h, hwc, mob) in DEV.items():
                const, r, errs = await run(b, srv.port, os.path.basename(f), w, h, hwc, mob, until)
                res[(t, d)] = (const, r); print(t, d, const, '최소 출생거리', r['minD'], '화면안출생', r['nbad'], r['bad'], errs[:2], flush=True)
                if errs and t == 'NEW': fails.append('JS 오류 %s %s' % (d, errs[:2]))
        await b.close()
    srv.close()
    for f in cp.values(): os.remove(f)
    for t in files:
        ref = res[(t, 'PC')]
        for d in ('폰', '좁은PC'):
            c, r = res[(t, d)]
            same_c = {k: v for k, v in c.items() if k != 'LOW'} == {k: v for k, v in ref[0].items() if k != 'LOW'}
            same_s = len(r['out']) == len(ref[1]['out']) and all(abs(a[1] - b2[1]) <= 2 for a, b2 in zip(ref[1]['out'], r['out']))   # 화면 안 적만 겨냥하는 무기 때문에 한 프레임 늦는 ±2 는 허용(합계는 다시 맞아떨어진다)
            print('[%s] PC vs %s  상수 %s · 시간별 출생수 %s' % (t, d, '같음' if same_c else '다름', '같음(±2)' if same_s else '다름'))
            if not same_s:
                df = [(a, b2) for a, b2 in zip(ref[1]['out'], r['out']) if abs(a[1] - b2[1]) > 2]
                print('   처음 다른 곳(PC | %s): %s' % (d, df[:4]), '… 총 %d곳' % len(df))
            if t == 'NEW':
                if not same_c: fails.append('상수 %s %s' % (d, c))
                if not same_s: fails.append('출생 수 %s' % d)
        for d in DEV:
            if t == 'NEW' and res[(t, d)][1]['nbad']: fails.append('화면 안 출생 %s %s' % (d, res[(t, d)][1]['bad']))
    for d in DEV:
        c = res[('NEW', d)][0]
        if (c['MAXE'], c['eshots'], c['shots'], c['SR'], c['DR']) != (220, 140, 220, 905, 1425): fails.append('기준값 %s %s' % (d, c))
    print('FAIL' if fails else 'PASS', fails); sys.exit(1 if fails else 0)
asyncio.run(main())
