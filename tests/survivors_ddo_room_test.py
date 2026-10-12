# -*- coding: utf-8 -*-
"""☠ 또뀨 「진실의 방」 시험 — [2026-10-12 사장님] 「하드 30분 또뀨 진실의 방은 컨트롤로 못 넘는다 · 파훼 가능한 기믹으로」
 A. 예고(pre) 동안은 벽이 없다 — 밖으로 걸어 나갈 수 있다.
 B. 벽이 선 뒤 문이 아닌 쪽으로는 못 나간다(예전 규칙 유지).
 C. 벽에 문(초록)이 있고, 문 쪽으로 걸어가면 방이 풀린다.
 D. 아무것도 안 해도 방은 끝난다(지속 6초) · 반지름 최소 140.
 E. 보스가 방을 열 때 예고·문 값이 실려 있다 · 콘솔 오류 0.
"""
import asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright

JS = r"""
(()=>{const X=window.__p6x;
function begin(){X.CH_set('brj');X.start();const S=X.S;S.t=800;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;for(const o of X.enemies.a)o.on=false;return S;}
function step(n){for(let i=0;i<n;i++)X.update(1/30);}
const dirKeys=(ang)=>{const c=Math.cos(ang),s=Math.sin(ang),k={};if(c>.38)k.KeyD=true;if(c<-.38)k.KeyA=true;if(s>.38)k.KeyS=true;if(s<-.38)k.KeyW=true;return k;};
window.__rt={
 A(){const S=begin();const p=S.p;S.room={x:p.x,y:p.y,R:300,t:6,pre:1.3,g:0,gw:1};p.x+=285;X.keys={KeyD:true};step(25);const d=p.x-S.room.x;return {d,R:300,r:p.r,pre:S.room.pre};},
 B(){const S=begin();const p=S.p;S.room={x:p.x,y:p.y,R:300,t:6,pre:0,g:0,gw:1};p.x-=250;let maxd=0;for(let i=0;i<90&&S.room;i++){X.keys={KeyA:true};step(1);maxd=Math.max(maxd,Math.hypot(p.x-S.room.x,p.y-S.room.y));}return {maxd,alive:!!S.room};},
 C(){const S=begin();const p=S.p;S.room={x:p.x,y:p.y,R:300,t:6,pre:0,g:0,gw:1};p.x+=250;let n=0;for(;n<150&&S.room;n++){const R=S.room;X.keys=dirKeys(R.g);step(1);}return {gone:!S.room,frames:n};},
 D(){const S=begin();const p=S.p;S.room={x:p.x,y:p.y,R:300,t:6,pre:1.3,g:0,gw:1};X.keys={};let minR=999,n=0;for(;n<400&&S.room;n++){step(1);if(S.room)minR=Math.min(minR,S.room.R);}return {gone:!S.room,sec:n/30,minR};},
 E(){const S=begin();const p=S.p;const e=X.spawnEnemy(X.BOSS?Object.values(X.BOSS)[0]:null,1);return {};}
};return true;})()
"""

async def main():
    p = H.make_copy('survivors.html', 'survivors_ddoroom.html')
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page='survivors_ddoroom.html')
        await pg.evaluate(JS)
        A = await pg.evaluate('__rt.A()'); print('A', A)
        ok(A['d'] > A['R'] - A['r'] + 5 and A['pre'] < 0.5, 'A 예고 동안은 벽이 없다 — 걸어 나갈 수 있다')
        B = await pg.evaluate('__rt.B()'); print('B', B)
        ok(B['maxd'] <= 300 + 1, 'B 문이 아닌 쪽 벽은 못 넘는다 (최대 거리 %.1f)' % B['maxd'])
        C = await pg.evaluate('__rt.C()'); print('C', C)
        ok(C['gone'], 'C 문 쪽으로 걸어가면 방이 풀린다 (%d프레임)' % C['frames'])
        D = await pg.evaluate('__rt.D()'); print('D', D)
        ok(D['gone'] and 6.5 < D['sec'] < 8.2 and D['minR'] >= 139, 'D 가만히 있어도 방은 끝난다 (%.1f초 · 최소 반지름 %.0f)' % (D['sec'], D['minR']))
        src = open(os.path.join(H.ROOT, 'survivors.html'), encoding='utf-8').read()
        ok("pre:1.3,g:Math.random()*6.283,gw:1.0" in src and "🚪 문" in src, 'E 보스가 방을 열 때 예고·문 값이 실린다 · 문이 그려진다')
        ok(not errs, '콘솔 오류 0 %s' % errs[:3])
        await b.close()
    srv.close()
    try: os.remove(p)
    except Exception: pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0
if __name__ == '__main__': sys.exit(asyncio.run(main()))
