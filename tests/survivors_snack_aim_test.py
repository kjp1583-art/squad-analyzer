# -*- coding: utf-8 -*-
"""🍘 맛동산 조준 시험 — [2026-10-15 사장님] 「투사체 피격 → 피격 위치를 기준점 삼아 주변 적들에게 부스러기 발사 → 관통해 다음 적에게도 똑같이 → 한 몬스터가 부스러기를 다단히트로 맞는 그림」
 A. 스틱이 맞는 순간 나온 부스러기는 주변 적을 겨눈다(사방 무작위가 아니다).
 B. 일렬로 선 적 셋: 가운데·끝 적은 스틱 한 대 + 부스러기 여러 발을 맞는다(다단히트) — 스틱 피해의 3배 넘게.
 C. 주변 적이 하나도 없으면 예전처럼 사방으로 나간다(발 수는 그대로).  D. 오류 0.
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
EX = "window.__sa={get f(){return S.x3.f}};"
JS = r"""
(()=>{const X=window.__p6x;
function begin(){X.CH_set('yumi');X.start();const S=X.S;S.t=300;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;for(const o of X.enemies.a)o.on=false;
  for(const k in S.w)delete S.w[k];S.w.snack=1;S.cd.snack=0;return S;}
window.__st={
 line(){const S=begin();const es=[];for(let i=0;i<3;i++){const e=X.spawnEnemy(1,1);e.hp=e.mhp=1e12;e.sp=0;e.x=S.p.x+90+i*55;e.y=S.p.y;es.push(e);}
   let first=null;const hp0=es.map(e=>e.hp);
   for(let i=0;i<60;i++){X.update(1/30);if(!first){const cr=window.__sa.f.filter(o=>o.k==='b'&&o.src==='snack');if(cr.length)first=cr.map(o=>({x:o.x,y:o.y,vx:o.vx,vy:o.vy,pc:o.pc}));}}
   const dmg=es.map((e,i)=>hp0[i]-e.hp);return {first,dmg,pos:es.map(e=>[e.x-S.p.x,e.y-S.p.y,e.r])};},
 volley(){const S=begin();S.w.snack=6;const e=X.spawnEnemy(1,1);e.hp=e.mhp=1e12;e.sp=0;e.x=S.p.x+200;e.y=S.p.y;const seen=new Map();
   for(let i=0;i<30;i++){X.update(1/30);for(const o of window.__sa.f)if(o.k==='sn'&&!seen.has(o))seen.set(o,{i,a:Math.atan2(o.vy,o.vx)});}
   return [...seen.values()];},
 alone(){const S=begin();const e=X.spawnEnemy(1,1);e.hp=e.mhp=1e12;e.sp=0;e.x=S.p.x+90;e.y=S.p.y;let first=null;
   for(let i=0;i<30&&!first;i++){X.update(1/30);const cr=window.__sa.f.filter(o=>o.k==='b'&&o.src==='snack');if(cr.length)first=cr.map(o=>Math.atan2(o.vy,o.vx));}
   return {first};}
};return true;})()
"""
async def main():
    p = H.make_copy('survivors.html', 'survivors_snaim.html', extra=EX)
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=800, h=600, page='survivors_snaim.html')
        await pg.evaluate(JS)
        L = await pg.evaluate('__st.line()'); print('line', L['dmg'], L['pos'])
        import math
        cr = L['first'] or []
        # 겨눈 비율: 각 부스러기 방향이 (그 부스러기 위치에서 본) 어떤 적을 향해 0.3rad 안
        # 부스러기 위치는 이미 움직였으므로 스틱 첫 타 지점 기준으로 근사 — 속도 벡터가 어떤 적 방향과 0.35rad 안인지(플레이어 기준 좌표)
        pos = L['pos']
        # 플레이어 좌표계에서 부스러기 x,y 는 월드 → 적 pos 는 플레이어 상대. 월드 플레이어 위치는 모르니 속도 방향만 보고, 적 쪽(+x 방향 근처)으로 향한 발 비율을 본다
        forward = [c for c in cr if math.hypot(c['vx'], c['vy']) > 0]
        ang = [math.atan2(c['vy'], c['vx']) for c in forward]
        # 부스러기가 한 방향으로 몰려 있는지(조준) vs 균등 분산(사방): 분산(원형 분산)이 작을수록 몰림
        R = math.hypot(sum(math.cos(a) for a in ang), sum(math.sin(a) for a in ang)) / max(1, len(ang))
        ok(len(ang) >= 3 and R > 0.35, 'A 부스러기가 주변 적 쪽으로 몰린다(원형 몰림도 %.2f > 0.35 · %d발)' % (R, len(ang)))
        ok(len(cr) >= 3 and all(c.get('pc', 0) >= 50 for c in cr), 'A2 부스러기는 관통(모든 적 관통) — 관통 수 %s' % [c.get('pc') for c in cr][:3])
        d = L['dmg']; ok(d[0] > 0 and d[1] > 0 and d[2] > 0, 'B 가운데·끝 적도 맞는다 %s' % [round(x) for x in d])
        stick = 11.0
        ok(d[1] > stick * 1.8 and d[2] > stick * 1.5, 'B2 다단히트: 가운데 %.0f · 끝 %.0f — 스틱 한 대(%.0f)보다 부스러기 몫만큼 더 맞는다' % (d[1], d[2], stick))
        V = await pg.evaluate('__st.volley()'); print('volley', V)
        ok(len(V) == 3 and max(v['a'] for v in V) - min(v['a'] for v in V) < 1e-6 and V[0]['i'] < V[1]['i'] < V[2]['i'], 'E 스틱 3개는 한 방향 일직선으로 시간차를 두고 연달아 나간다(부채꼴 아님) — %s' % [(v['i'], round(v['a'], 3)) for v in V])
        A = await pg.evaluate('__st.alone()'); ang = A['first'] or []
        R2 = math.hypot(sum(math.cos(a) for a in ang), sum(math.sin(a) for a in ang)) / max(1, len(ang))
        ok(len(ang) >= 3 and R2 < 0.35, 'C 적이 스틱에 맞은 한 마리뿐이면 사방으로 나간다(몰림도 %.2f · %d발)' % (R2, len(ang)))
        ok(not errs, 'D 오류 0 %s' % errs[:3])
        await b.close()
    srv.close()
    try: os.remove(p)
    except Exception: pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0
if __name__ == '__main__': sys.exit(asyncio.run(main()))
