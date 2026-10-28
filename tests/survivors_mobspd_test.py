# -*- coding: utf-8 -*-
"""🐢 일반 몹 이동속도 -20% 시험 (사장님 2026-10-17) — 실제 spawnEnemy 를 부른다.
  A. 일반 몹의 속도 = 표 속도 × (1 + 시간 보정) × 0.8 (여러 종류 · 0분/10분)  B. 보스는 그대로(표 속도 × 보스 보정)
  C. MOB_SPD 상수 한 곳 · 값 0.8  D. 콘솔 오류 0"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
EXTRA = "window.__ms={get KIND(){return KIND},get BOSS(){return BOSS},get MOB_SPD(){return MOB_SPD}};"
JS = r"""(()=>{const X=window.__p6x,T=window.__ms;X.CH_set('brj');X.start();const S=X.S;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;
 const out={mob:T.MOB_SPD,rows:[],boss:null};
 for(const t of [0,600]){S.t=t;for(const o of X.enemies.a)o.on=false;
  for(let k=0;k<Math.min(8,T.KIND.length);k++){const e=X.spawnEnemy(k,1);if(!e)continue;
   out.rows.push({t,k,sp:e.sp,want:T.KIND[k].sp*(1+Math.min(.55,t/900))*.8});}}
 S.t=0;for(const o of X.enemies.a)o.on=false;const bk=Object.keys(T.BOSS)[0];const b=T.BOSS[bk];
 const e=X.spawnEnemy(0,1,b);const m=X.S.t/60;out.boss={sp:e.sp,want:b.sp*(1+Math.min(.35,m/120))};
 return out;})()"""
async def main():
    p = H.make_copy('survivors.html', 'survivors_msx.html', extra=EXTRA); srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw); ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page='survivors_msx.html')
        r = await pg.evaluate(JS)
        ok(r['mob'] == .8, 'C MOB_SPD = 0.8 (%s)' % r['mob'])
        bad = [x for x in r['rows'] if abs(x['sp'] - x['want']) > 1e-6]
        ok(len(r['rows']) >= 8 and not bad, 'A 일반 몹 속도 = 표 × 시간 보정 × 0.8 (%d종·0분/10분, 어긋남 %s)' % (len(r['rows']), bad[:2]))
        ok(abs(r['boss']['sp'] - r['boss']['want']) < 1e-6, 'B 보스 속도는 그대로 (%s)' % r['boss'])
        ok(not errs, 'D 콘솔 오류 0 %s' % errs[:2])
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_msx.html'))
    except Exception: pass
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
