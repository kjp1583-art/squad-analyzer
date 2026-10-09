# -*- coding: utf-8 -*-
"""🐲 용조련사 고유 무기 「🔥 드래곤 브레스」 피해 하향 — 기본 피해 36 → 29(약 −20%).
[2026-10-09 사장님 지시 「용조련사 고유무기 데미지가 너무 쎄니까 하향조정」]
실제 게임 코드로 브레스를 쏴서 한 번 맞는 피해를 잰다(더미 적 하나·치명타 없음·다른 무기 없음):
  Lv2(시작) 29 · Lv3 29×1.4 · Lv5 29×1.4×1.4 · Lv8 29×1.4×1.4×1.5 · 🌙 각성 ×1.2 — 올림·내림 없이 상수 BRT.d 에 레벨 배율이 그대로 곱해진다.
사용: python3 tests/survivors_breath_nerf_test.py
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright

EXTRA = "window.__bn={get BRT(){return BRT}};"
JS = r"""
([L,ev])=>{const X=window.__p6x,Z=window.__bn;X.CH_set('yj');X.start();const S=X.S;
  for(const o of X.enemies.a)o.on=false;
  S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;S.w.breath=L;if(ev)S.ev.breath=1;else delete S.ev.breath;
  const e=X.spawnEnemy(0,1);e.x=S.p.x+90;e.y=S.p.y;e.hp=e.mhp=1e12;e.sp=0;e.r=14;
  S.cd.breath=0;const h0=e.hp;X.update(1/30);
  const dmg=h0-e.hp;return {dmg,d:Z.BRT.d,L,ev:!!ev,hit:dmg>0}}
"""
LV = lambda L: (1.4 if L >= 3 else 1) * (1.4 if L >= 5 else 1) * (1.5 if L >= 8 else 1)


async def main():
    p = H.make_copy('survivors.html', 'survivors_bnx.html', extra=EXTRA)
    srv = H.Srv()
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page='survivors_bnx.html')
        r0 = await pg.evaluate(JS, [2, False])
        ok(r0['d'] == 29, 'A1 기본 피해 상수 BRT.d = 29 (실제 %s)' % r0['d'])
        for L, ev in ((1, False), (2, False), (3, False), (4, False), (5, False), (6, False), (7, False), (8, False), (8, True)):
            r = await pg.evaluate(JS, [L, ev])
            want = 29 * LV(L) * (1.2 if ev else 1)
            ok(r['hit'] and abs(r['dmg'] - want) < 1e-6 * max(1, want) + 1e-6, 'B Lv%d%s 한 번 맞는 피해 %.3f (기대 %.3f)' % (L, ' 🌙각성' if ev else '', r['dmg'], want))
        ok(not [e for e in errs if 'bnx' not in e], 'C 콘솔·페이지 오류 0')
        await b.close()
    srv.close()
    try:
        os.remove(p)
    except Exception:
        pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
