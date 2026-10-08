# -*- coding: utf-8 -*-
"""🧺 고유 무기가 필드 아이템(와드·사료 포대·포로 간식 상자)을 때리는지 — 적이 없을 때도 사거리 안의 아이템을 겨눈다. 사용: python3 tests/survivors_props_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:220] if x and not c else ''))
    if not c: FAILS.append(n)
# 캐릭터 키 → 고유 무기 키(brj quill · jjg tempo · hrb slime · amd heart · ildj jhin · kyo whop · ddmj bash · psg twin · tw ram · yumi snack · eom eom)
CASES = [('brj','quill'),('jjg','tempo'),('hrb','slime'),('amd','heart'),('ildj','jhin'),('kyo','whop'),('ddmj','bash'),('psg','twin'),('tw','ram'),('yumi','snack'),('eom','eom'),('bgb','pcards'),('bbb','sing')]
RUN = r"""async ([ch,w])=>{ const x=__p6x; x.srvUnl&&x.srvUnl(['yumi','eom','bbb']); x.CH_set(ch); x.start(); const S=x.S,p=S.p; S.p.hp=S.p.mhp;
  for(const e of x.enemies.a)e.on=false;
  const L=8; S.w[w]=L; if(x.REL){} 
  // 필드 아이템 하나를 사거리 안에 놓는다(적은 없음) — 오른쪽 90px
  const o=x.props.get?x.props.get():null;
  let q=null; for(const c of x.props.a){ if(!c.on){q=c;break;} } if(!q)return {err:'no prop slot'};
  q.on=true;q.k=1;q.x=p.x+90;q.y=p.y;q.hp=22;q.hit=0;
  const hp0=q.hp; let n=0; while(n<900){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play')break; S.p.hp=S.p.mhp; x.update(0.05); n++; if(!q.on||q.hp<hp0)break }
  return {hit:!q.on||q.hp<hp0,t:n*0.05} }"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for ch, w in CASES:
            ctx, pg, errs = await H.new_page(b, srv.port)
            r = await pg.evaluate(RUN, [ch, w])
            check('%s(%s): 적 없이 필드 아이템을 때린다' % (ch, w), r.get('hit') is True, r)
            check('%s 스크립트 오류 없음' % ch, not errs, errs)
            await ctx.close()
        await b.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
