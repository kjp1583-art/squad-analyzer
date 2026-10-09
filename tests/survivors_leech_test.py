# -*- coding: utf-8 -*-
"""🩹 처치 응급처치 상향 — 회복량 Lv1·2·3 = +2·+2·+3, 쉬는 시간 5·4·3.5초(그대로).
카드 문구와 실제 효과가 같은 값을 읽는지, 쉬는 시간 안의 처치는 회복이 없는지, 최대 HP 를 넘지 않는지, 유물이 없으면 회복이 없는지 본다.
사용: python3 tests/survivors_leech_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright

HP = {1: 2, 2: 2, 3: 3}          # 한 번에 회복하는 HP
CD = {1: 5, 2: 4, 3: 3.5}        # 쉬는 시간(초)

RUN = r"""async ()=>{ const x=__p6x; x.CH_set('brj'); x.start(); const S=x.S; S.p.mhp=1000;
  const kill=()=>{const b=S.p.hp;const e=x.spawnEnemy(0,1,null,{x:S.p.x+300,y:S.p.y});if(!e)return null;e.hp=1;x.hurt(e,1e6);return +(S.p.hp-b).toFixed(3);};
  const out={lv:{}};
  for(const lv of [1,2,3]){
    S.rel.leech=lv;S.p.hp=100;S.leechT=0;
    const first=kill();                    // 쉬는 시간이 끝나 있을 때 첫 처치 → 회복
    const t1=S.leechT;                     // 회복 직후 쉬는 시간
    const second=kill();                   // 쉬는 시간 안의 처치 → 회복 없음
    S.leechT=0;const third=kill();         // 쉬는 시간이 끝났다고 보고 처치 → 다시 회복
    S.leechT=0;S.p.hp=S.p.mhp-0.5;const cap=kill();const hpAfterCap=S.p.hp;   // 최대 HP 바로 아래 → 최대 HP 까지만
    const cd=x.cardOf({t:'rl',r:'leech',l:lv-1});
    out.lv[lv]={first,t1,second,third,cap,hpAfterCap,mhp:S.p.mhp,text:x.REL.leech.ds(lv),card:cd.ds};
  }
  S.rel.leech=3;S.leechT=3.5;for(let i=0;i<30;i++)x.relTick(.1);out.cdAfter3s=+S.leechT.toFixed(3);   // 쉬는 시간이 시간에 따라 줄어든다
  delete S.rel.leech;S.p.hp=100;S.leechT=0;out.none=kill();   // 유물이 없으면 회복 없음
  return out; }"""

async def main():
    H.make_copy(); srv = H.Srv(); bad = []
    def check(name, ok, info=''):
        print(('PASS' if ok else 'FAIL'), name, ('' if ok else '  ← ' + str(info)));
        if not ok: bad.append(name)
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port)
        r = await pg.evaluate(RUN); print(r)
        for lv in (1, 2, 3):
            o = r['lv'][str(lv)]
            check('Lv%d 처치하면 HP +%d' % (lv, HP[lv]), abs(o['first'] - HP[lv]) < .01, o)
            check('Lv%d 회복 직후 쉬는 시간 %s초' % (lv, CD[lv]), abs(o['t1'] - CD[lv]) < .01, o)
            check('Lv%d 쉬는 시간 안의 처치는 회복 없음' % lv, o['second'] == 0, o)
            check('Lv%d 쉬는 시간이 끝나면 다시 +%d' % (lv, HP[lv]), abs(o['third'] - HP[lv]) < .01, o)
            check('Lv%d 최대 HP 를 넘지 않는다(0.5 만 회복)' % lv, abs(o['cap'] - .5) < .01 and abs(o['hpAfterCap'] - o['mhp']) < .01, o)
            want = '적을 처치하면 HP +%d (%s초에 한 번)' % (HP[lv], ('%g' % CD[lv]))
            check('Lv%d 유물 문구 「%s」' % (lv, want), o['text'] == want, o['text'])
            check('Lv%d 레벨업 카드 설명에도 같은 문구가 들어간다' % lv, want in o['card'], o['card'])
        check('쉬는 시간이 시간에 따라 줄어든다(3.5초 → 3초 뒤 0.5초)', abs(r['cdAfter3s'] - .5) < .02, r['cdAfter3s'])
        check('유물이 없으면 처치해도 회복 없음', r['none'] == 0, r['none'])
        check('콘솔·페이지 오류 0', not errs, errs)
        await b.close()
    srv.close()
    print('전부 통과' if not bad else '실패 %d건: %s' % (len(bad), bad))
    return 0 if not bad else 1
sys.exit(asyncio.run(main()))
