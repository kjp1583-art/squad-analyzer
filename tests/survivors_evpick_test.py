# -*- coding: utf-8 -*-
"""✨ 각성 선택창 시험 — [2026-10-12 사장님] 「각성할 때 내가 원하는 스킬을 선택해서 각성할 수 있게 선택창」
 A. 각성 가능한 무기가 2개 이상이면 상자를 열 때 선택창(evpick)이 뜨고 고를 때까지 상자·각성이 일어나지 않는다.
 B. 버튼으로 고른 무기만 각성하고 나머지는 그대로 · 이어서 상자 화면(chest)이 열리고 「좋아!」로 판이 이어진다.
 C. 후보가 1개면 선택창 없이 그대로 각성(예전과 같다).  D. 후보가 0개면 각성 없음.
 E. 각성 3개를 다 썼으면 후보가 없다 · 선택창에서 resume() 가 불리면(시험 봇) 첫 후보로 각성한다 · 선택창은 이어하기 저장 대상이 아니다.
 F. 폰 폭 320/360 에서 버튼이 넘치지 않는다 · 오류 0.
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright

JS = r"""
(()=>{const X=window.__p6x;
function begin(ws){X.CH_set('brj');X.start();const S=X.S;S.t=300;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;for(const o of X.enemies.a)o.on=false;
  for(const k in S.w)delete S.w[k];for(const k in S.ev)delete S.ev[k];
  for(const k of ws){S.w[k]=8;S.ps[X.WEAP[k].pair]=1;}return S;}
const ready=()=>Object.keys(X.S.w).filter(k=>!X.S.ev[k]&&X.S.w[k]>=8&&(X.S.ps[X.WEAP[k].pair]||0)>0);
window.__et={
 keys(){return Object.keys(X.WEAP).filter(k=>X.WEAP[k].pair&&X.WEAP[k].ev).slice(0,6);},
 A(ws){const S=begin(ws);X.openChest();const st=X.state;const btns=[...document.querySelectorAll('#evpickList .evb')].map(b=>b.dataset.k);
   return {st,btns,ev:Object.keys(S.ev),ovOn:document.getElementById('evpick').classList.contains('on')};},
 B(pickIdx){const bs=[...document.querySelectorAll('#evpickList .evb')];const k=bs[pickIdx].dataset.k;bs[pickIdx].click();const S=X.S;
   const r={st:X.state,ev:Object.keys(S.ev),k,chestOn:document.getElementById('chest').classList.contains('on')};
   document.getElementById('chestOk').click();r.after=X.state;return r;},
 C(w){const S=begin([w]);X.openChest();return {st:X.state,ev:Object.keys(S.ev),nbtn:document.querySelectorAll('#evpickList .evb').length};},
 D(){const S=begin([]);X.openChest();return {st:X.state,ev:Object.keys(S.ev)};},
 E1(ws){const S=begin(ws);S.ev.fakeA=1;S.ev.fakeB=1;S.ev.fakeC=1;X.openChest();return {st:X.state,evn:Object.keys(S.ev).length};},
 E2(ws){const S=begin(ws);X.openChest();const st0=X.state;X.resume();return {st0,st:X.state,ev:Object.keys(S.ev)};},
 F(ws){const S=begin(ws);X.openChest();const b=document.querySelector('#evpick .box');const r=b.getBoundingClientRect();
   return {w:r.width,sw:document.documentElement.scrollWidth,iw:window.innerWidth,over:[...document.querySelectorAll('#evpickList .evb')].some(x=>x.scrollWidth>x.clientWidth+1)};}
};return true;})()
"""

async def main():
    p = H.make_copy('survivors.html', 'survivors_evpick.html')
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        for w in (360, 320):
            ctx, pg, errs = await H.new_page(b, srv.port, w=w, h=740, page='survivors_evpick.html')
            await pg.evaluate(JS)
            ks = await pg.evaluate('__et.keys()')
            k1, k2, k3 = ks[0], ks[1], ks[2]
            if w == 360:
                A = await pg.evaluate('__et.A(%r)' % [k1, k2, k3]); print('A', A)
                ok(A['st'] == 'evpick' and A['ovOn'] and set(A['btns']) == {k1, k2, k3} and not A['ev'], 'A 후보 3개 → 선택창이 뜨고 아직 각성 없음')
                B = await pg.evaluate('__et.B(1)'); print('B', B)
                ok(B['st'] == 'chest' and B['ev'] == [B['k']] and B['chestOn'] and B['after'] == 'play', 'B 고른 무기만 각성 · 상자 화면 → 판 이어짐')
                C = await pg.evaluate('__et.C(%r)' % k1); print('C', C)
                ok(C['st'] == 'chest' and C['ev'] == [k1], 'C 후보 1개는 선택창 없이 각성')
                D = await pg.evaluate('__et.D()'); ok(D['st'] == 'chest' and not D['ev'], 'D 후보 0개는 각성 없음')
                E1 = await pg.evaluate('__et.E1(%r)' % [k1, k2]); ok(E1['st'] == 'chest' and E1['evn'] == 3, 'E1 각성 3개를 다 썼으면 선택창 없음')
                E2 = await pg.evaluate('__et.E2(%r)' % [k1, k2]); print('E2', E2)
                ok(E2['st0'] == 'evpick' and E2['st'] == 'chest' and len(E2['ev']) == 1, 'E2 선택창에서 resume() → 첫 후보로 각성')
            F = await pg.evaluate('__et.F(%r)' % [k1, k2, k3]); print('F', w, F)
            ok(F['sw'] <= F['iw'] + 1 and not F['over'], 'F 폭 %d 넘침 없음' % w)
            ok(not errs, '오류 0 (%d) %s' % (w, errs[:3]))
            await ctx.close()
        await b.close()
    srv.close()
    try: os.remove(p)
    except Exception: pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0
if __name__ == '__main__': sys.exit(asyncio.run(main()))
