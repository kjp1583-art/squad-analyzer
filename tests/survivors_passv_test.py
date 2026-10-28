# -*- coding: utf-8 -*-
"""⚖ 양날의 검 패시브(광분·거북 등껍질) 균형 — 식·문구가 PASSV 한 곳을 읽고, 같은 계열 초월 짝(근성·깃털 갑옷)에 맞서는지.
사용: python3 tests/survivors_passv_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
RUN = r"""async ()=>{ const x=__p6x; x.CH_set('brj'); x.start(); const S=x.S; const o={}; const P=x.PASSV;
  const set=(ps,pt)=>{S.ps=Object.assign({},ps);S.pt=Object.assign({},pt||{});S.p.hp=S.p.mhp;};
  const base=(set({}),{dm:x.dmgMul(),tk:x.takenMul(),ar:x.armTotal(),mv:x.moveMul()});
  o.P=P; o.base=base; o.txg=x.PASS.glass.ds; o.txt=x.PASS.turtle.ds; o.mg=x.PASS.glass.max; o.mt=x.PASS.turtle.max;
  o.glass=[1,2,3].map(l=>{set({glass:l});return {dm:x.dmgMul()/base.dm,tk:x.takenMul()/base.tk};});
  o.turtle=[1,2,3].map(l=>{set({turtle:l});return {ar:x.armTotal()-base.ar,mv:x.moveMul()-base.mv};});
  set({might:5},{might:2});o.might=x.dmgMul()/base.dm;
  set({arm:5},{arm:2});o.arm=x.armTotal()-base.ar;
  return o; }"""
async def main():
    H.make_copy(dst='survivors_pv.html', extra='\nObject.assign(window.__p6x,{PASSV,PASS,takenMul,armTotal,moveMul,dmgMul});\n'); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port, page='survivors_pv.html')
        r = await pg.evaluate(RUN); print(r)
        P = r['P']; ok = True
        def check(n, c, d=None):
            nonlocal ok; ok &= bool(c); print(('PASS' if c else 'FAIL'), n, '' if c else d)
        rd = lambda v: round(v, 4)
        check('광분: 레벨당 피해 +PASSV.glass.dmg · 받는 피해 +PASSV.glass.tk', all(rd(r['glass'][i]['dm']) == rd(1 + P['glass']['dmg'] * (i + 1)) and rd(r['glass'][i]['tk']) == rd(1 + P['glass']['tk'] * (i + 1)) for i in range(3)), r['glass'])
        check('거북: 레벨당 고정 깎기 PASSV.turtle.arm · 이동속도 -PASSV.turtle.mv', all(rd(r['turtle'][i]['ar']) == rd(P['turtle']['arm'] * (i + 1)) and rd(r['turtle'][i]['mv']) == rd(-P['turtle']['mv'] * (i + 1)) for i in range(3)), r['turtle'])
        check('문구가 값을 읽는다(광분 +%d%% · +%d%% / 거북 -%d · -%d%%)' % (round(P['glass']['dmg'] * 100), round(P['glass']['tk'] * 100), P['turtle']['arm'], round(P['turtle']['mv'] * 100)),
              '+%d%%' % round(P['glass']['dmg'] * 100) in r['txg'] and '+%d%%' % round(P['glass']['tk'] * 100) in r['txg'] and '-%d ' % P['turtle']['arm'] in r['txt'] and '-%d%%' % round(P['turtle']['mv'] * 100) in r['txt'], (r['txg'], r['txt']))
        check('최대 레벨은 그대로 3칸(이어하기 표 모양 불변)', r['mg'] == 3 and r['mt'] == 3)
        check('광분 3칸의 피해 ≥ 근성 5칸 + 초월 2번의 95%% (패널티를 갚는다: %.2f vs %.2f)' % (r['glass'][2]['dm'], r['might']), r['glass'][2]['dm'] >= r['might'] * .95, (r['glass'][2], r['might']))
        check('거북 3칸의 깎기 > 깃털 갑옷 5칸의 깎기 (%.0f vs %.0f)' % (r['turtle'][2]['ar'], r['arm']), r['turtle'][2]['ar'] > r['arm'])
        print('오류', errs); await b.close(); return 0 if ok and not errs else 1
sys.exit(asyncio.run(main()))
