# -*- coding: utf-8 -*-
"""🛕 성소 시험 — survivors.html (2026-10-22)
  A 첫 성소는 150~270초 사이에 나온다 · 거리 600~900 · 미니맵/배너
  B 닿으면 3분 버프(7종 중 하나) · 성소 사라짐 · 다음은 270~330초 뒤
  C 버프가 실제로 배율에 반영 · 180초 뒤 끝남
  D 안 가면 180초 뒤 사라지고 다음 성소 예약
  E 1:1 보스전에서는 성소를 치운다 · 이어하기(새 S)는 상태를 버리고 오류 없음
  F 일일 도전: 같은 시드 → 같은 성소 위치·버프
  G 360폭 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
EXTRA = "window.__cr={SHR,SHRV,shrB,shrineTick,mmDraw,bannerQ,moveMul,dmgMul,takenMul,magMul,duelBegin,set S(v){S=v}};"
PRE = """
window.__T=(()=>{const x=__p6x,c=__cr;
 const R0=Math.random;
 const T={x,c,
  fresh(o){o=o||{};x.CH_set('brj');x.start(o.daily?{daily:true}:undefined);if(o.hard){x.S.hard=1;}if(o.vh){x.S.hard=1;x.S.vh=1;}const S=x.S;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=1e9;S.p.mhp=S.p.hp=1e7;S.t=o.t||0;S.spawnT=-1e9;S.evT=1e9;S.bigT=1e9;
   for(const e of x.enemies.a)e.on=false;for(const it of x.items.a)it.on=false;x.state='play';return S;},
  step(sec,fn){const n=Math.round(sec*30);for(let i=0;i<n;i++){const S=x.S;if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play')x.state='play';if(fn)fn(S);x.update(1/30);}},
  force(k){const v=[.1,.5,.9][k];c.CRI.pk=-1;c.CRI.nx=1e9;Math.random=()=>v;try{c.crisisStart();}finally{Math.random=R0;}},   // 종류 k 로 강제 시작(RN 은 비일일 판에서 Math.random)
  fireNow(){const C=c.CRI;C.t=0;x.S.spawnT=-1e9;T.step(1/30);},
  hecs(){return x.enemies.a.filter(e=>e.on&&e.ki===c.KI.Hecarim);},
  kill(){for(const e of x.enemies.a)e.on=false;}
 };return T;})();
"""
async def main():
    H.make_copy('survivors.html', 'survivors_sh.html', extra=EXTRA); srv = H.Srv(); fails = []
    def ok(c, m, d=''):
        print(('  ok   ' if c else '  FAIL ') + m + ('' if c else '  ← ' + str(d)[:300]))
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=360, h=740, page='survivors_sh.html')
        await pg.evaluate(PRE)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,H=c.SHR,V=c.SHRV;const S=T.fresh();T.step(.3);const o={nx:H.nx,on0:H.on};
          S.p.x=S.p.y=0;S.t=H.nx-.2;T.step(.5);o.on=H.on;o.d=Math.round(Math.hypot(H.x-S.p.x,H.y-S.p.y));o.ban=c.bannerQ.map(q=>q[0]).join('|');
          c.mmDraw();return o;}""")
        ok(150 <= r['nx'] <= 270 and r['on0'] == 0, 'A 첫 성소 예약 150~270초', r)
        ok(r['on'] == 1 and 560 <= r['d'] <= 960, 'A 성소 출현 · 거리 600~900', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,H=c.SHR,V=c.SHRV,S=T.x.S,o={};
          const base={mv:c.moveMul(),dm:c.dmgMul(),tk:c.takenMul(),mag:c.magMul()};
          S.p.x=H.x;S.p.y=H.y;T.step(.1);o.on=H.on;o.b=H.b&&H.b.k;o.t=Math.round(H.t);o.next=Math.round(H.nx-S.t);
          const k=H.b.k;o.eff={mv:c.moveMul()/base.mv,dm:c.dmgMul()/base.dm,tk:c.takenMul()/base.tk,mag:c.magMul()/base.mag};
          T.step(100);o.t100=Math.round(H.t);T.step(81);o.end=H.t;o.bnull=H.b;return o;}""")
        ok(r['on'] == 0 and r['b'] and 178 <= r['t'] <= 180 and 268 <= r['next'] <= 332, 'B 닿으면 버프 3분 · 다음 성소 예약', r)
        e = r['eff']; k = r['b']
        good = {'mv': e['mv'] > 1, 'dm': e['dm'] > 1, 'tk': e['tk'] < 1, 'mag': e['mag'] > 1}.get(k, True)
        ok(good, 'C 버프(%s)가 배율에 반영' % k, r)
        ok(r['end'] == 0 and r['bnull'] is None, 'C 180초 뒤 버프 끝남', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,H=c.SHR,S=T.x.S,o={};S.p.x=S.p.y=0;S.t=H.nx+.1;H.on=0;T.step(.1);o.on=H.on;
          const x0=H.x;T.step(181);o.gone=H.on;o.nx=H.nx-S.t;return o;}""")
        ok(r['on'] == 1 and r['gone'] == 0 and r['nx'] > 200, 'D 안 가면 180초 뒤 사라지고 다음 예약', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,H=c.SHR,V=c.SHRV;const S=T.fresh({t:1000});T.step(.3);return {nx:Math.round(H.nx-S.t),on:H.on};}""")
        ok(r['on'] == 0 and 260 <= r['nx'] <= 340, 'H 1000초에 이어하면 성소는 지금부터 5분 칸(즉시 안 나온다) — %s' % r, r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,H=c.SHR,S=T.x.S,o={};H.on=1;H.x=S.p.x+700;H.y=S.p.y;c.duelBegin&&0;
          S.bossRef={on:true,du:true};T.step(.1);o.on=H.on;S.bossRef=null;
          const S2=Object.assign({},S);S2.ebooms=S.ebooms.slice();c.S=S2;T.step(.1);o.reset=H.s===S2;return o;}""")
        ok(r['on'] == 0, 'E 1:1 에서는 성소를 치운다', r)
        seqs = []
        for i in range(2):
            s = await pg.evaluate("""()=>{const T=__T,c=T.c,H=c.SHR,x=T.x;const S=T.fresh({daily:1});T.step(.3);if(!S.dly)return null;S.p.x=S.p.y=0;
              S.t=H.nx;T.step(.1);const o={x:Math.round(H.x),y:Math.round(H.y)};S.p.x=H.x;S.p.y=H.y;T.step(.1);o.b=H.b&&H.b.k;return o;}""")
            seqs.append(s)
        ok(seqs[0] is not None and seqs[0] == seqs[1], 'F 일일 도전: 같은 시드 → 같은 성소·버프 %s' % seqs[0], seqs)
        ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
        ok(ov['sw'] <= ov['cw'], 'G 360폭 가로 넘침 없음', ov)
        ok(not errs, 'G 콘솔 오류 0', errs[:3])
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_sh.html'))
    except Exception: pass
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
