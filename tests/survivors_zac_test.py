# -*- coding: utf-8 -*-
"""🟢 원딜 자크 분열 시험 — 자크는 쓰러지면 작은 자크 둘로 갈라지되 「두 세대까지」(원본 1 + 2 + 4 = 최대 7마리)여야 한다.
[2026-10-09 클랜원 제보] 「특정 자크가 죽지 않고 무한 분열하면서 처치 수를 왕창 올릴 수 있다」 — 원인: 적 풀(Pool.get)이 가장 낮은 빈 칸을 주는데,
쓰러진 자크의 칸이 그 칸이면 새끼 자크가 부모 칸을 그대로 다시 쓴다. 그러면 spawnEnemy 가 세대(gen)·반지름·속도를 기본값으로 되돌려 놓아
zacSplit 이 그 뒤에 「부모의 gen+1」 을 읽어도 이미 0 이 된 값이라 세대가 1 에서 멈춰 버린다 → 같은 칸에서 영원히 되살아난다(적이 화면에 꽉 찬 후반에 특히).

시험(전부 실제 게임 코드 — spawnEnemy · hurt · zacSplit — 를 부른다):
  A. 적 칸이 꽉 찬 판: 자크 한 마리를 연속으로 잡아도 「잡을 수 있는 자크 수」가 7 이하이고 세대가 2 를 넘지 않는다(고장 나면 수백 번 계속 나온다).
  B. 빈 칸이 넉넉한 판: 정확히 7마리(1+2+4)가 나오고 세대는 0 1 1 2 2 2 2.
  C. 빈 칸 모양을 무작위로 바꿔 수백 번: 어떤 칸 배치에서도 7 이하 · 세대 ≤ 2 · 처치 수 = 잡은 자크 수.
  D. 새끼의 크기·속도·경험치·공격력이 「부모가 쓰러지기 전의 값」에서 나온다(칸 재사용 여부와 무관하게 같은 값) — 정상 동작은 그대로.
  E. 일반 적(자크 아님)은 쓰러져도 새끼를 만들지 않는다 · 콘솔 오류 0.
사용: python3 tests/survivors_zac_test.py  (끝에 종료코드)
"""
import asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright

EXTRA = "window.__zt={get KIND(){return KIND},get KI(){return KI},zacSplit,get SN(){return SN}};"
SRC = os.environ.get('ZAC_HTML', 'survivors.html')   # 기준(고치기 전) 사본으로도 돌려 볼 수 있다: ZAC_HTML=survivors_base.html

JS = r"""
(()=>{
const X=window.__p6x,T=window.__zt;
const KI=T.KI,Z=KI.Zac,N=KI.Nautilus;
const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
function begin(seed){Math.random=mb(seed);X.CH_set('brj');X.start();const S=X.S;S.t=800;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;
  for(const o of X.enemies.a)o.on=false;return S;}
function fillAllBut(freeSet){const E=X.enemies.a;for(const o of E)o.on=false;
  // 모든 칸을 먼저 채운 뒤 freeSet 칸만 비운다(칸 번호가 정확히 맞는다)
  let n=0;while(X.spawnEnemy(N,1))n++;for(const i of freeSet)E[i].on=false;return n;}
function liveZacs(){return X.enemies.a.filter(o=>o.on&&o.id==='Zac');}
// 판 위에 있는 자크를 잡을 수 있는 자크가 없어질 때까지(최대 cap 번) 오래된 것부터 연달아 잡는다
function chain(cap){const S=X.S;const gens=[],kills0=S.kills;let kz=0,maxGen=0,saw=[];
  for(let n=0;n<cap;n++){const zs=liveZacs();if(!zs.length)break;
    zs.sort((a,b)=>a.sn-b.sn);const v=zs[0];gens.push(v.gen);maxGen=Math.max(maxGen,v.gen);saw.push({gen:v.gen,r:+v.r.toFixed(2),sp:+v.sp.toFixed(1),xp:+v.xp.toFixed(2),dmg:+v.dmg.toFixed(2),mhp:+v.mhp.toFixed(2)});
    X.hurt(v,1e12);kz++;}
  return {kz,maxGen,gens,kills:S.kills-kills0,alive:liveZacs().length,saw};}
window.__zt2={
  A(){   // 꽉 찬 칸: 비어 있는 칸은 자크 하나가 쓸 칸 하나뿐
    const S=begin(11);fillAllBut([]);const E=X.enemies.a;E[E.length-1].on=false;   // 마지막 칸만 비움
    const e=X.spawnEnemy(Z,1);const r=chain(400);r.freeAtStart=1;r.firstIdx=X.enemies.a.indexOf(e);return r;},
  B(){   // 빈 칸이 넉넉
    const S=begin(12);const e=X.spawnEnemy(Z,1);const r=chain(400);return r;},
  C(trials){   // 빈 칸 배치 무작위
    const out={bad:[],max:0,maxGen:0,n:0};
    for(let t=0;t<trials;t++){const S=begin(1000+t);const E=X.enemies.a;const R=mb(7000+t);
      const nfree=1+Math.floor(R()*5);const free=new Set();while(free.size<nfree)free.add(Math.floor(R()*E.length));
      fillAllBut([...free]);
      const e=X.spawnEnemy(Z,1);if(!e)continue;
      const r=chain(60);out.n++;out.max=Math.max(out.max,r.kz);out.maxGen=Math.max(out.maxGen,r.maxGen);
      if(r.kz>7||r.maxGen>2||r.kills!==r.kz)out.bad.push({t,free:[...free],kz:r.kz,maxGen:r.maxGen,kills:r.kills});}
    return out;},
  D(){   // 새끼 값: 부모 쓰러지기 전 값에서 계산한 기대값과 같은가(꽉 찬 칸 / 넉넉한 칸 둘 다)
    const res=[];
    for(const mode of ['full','roomy']){
      const S=begin(21);if(mode==='full'){fillAllBut([]);X.enemies.a[X.enemies.a.length-1].on=false;}
      const e=X.spawnEnemy(Z,1.5);e.r=20;e.sp=60;e.xp=4;e.dmg=10;e.el=0;
      const K=T.KIND[Z],pre={gen:e.gen,r:e.r,sp:e.sp,xp:e.xp,dmg:e.dmg,mhp:e.mhp};
      const before=new Set(X.enemies.a.filter(o=>o.on).map(o=>o.sn));
      X.hurt(e,1e12);
      const kids=X.enemies.a.filter(o=>o.on&&o.id==='Zac'&&!before.has(o.sn));
      res.push({mode,pre,kids:kids.map(k=>({gen:k.gen,r:+k.r.toFixed(3),sp:+k.sp.toFixed(3),xp:+k.xp.toFixed(3),dmg:+k.dmg.toFixed(3),mhp:+k.mhp.toFixed(3)})),
        want:{gen:pre.gen+1,r:+(pre.r*.72).toFixed(3),sp:+(pre.sp*1.15).toFixed(3),xp:+Math.max(.5,pre.xp*.5).toFixed(3),dmg:+(pre.dmg*.75).toFixed(3),mhp:+(pre.mhp*.35).toFixed(3)}});}
    return res;},
  F(){   // 쓰러진 자크가 남기는 경험치 보석은 「부모 값」 — 새끼가 부모 칸을 덮어쓰면 보석 값이 새끼 값(작은 경험치)으로 줄던 것도 막는다
    const res=[];
    for(const mode of ['full','roomy']){
      const S=begin(41);if(mode==='full'){fillAllBut([]);X.enemies.a[X.enemies.a.length-1].on=false;}
      for(const g of X.gems.a)g.on=false;
      const e=X.spawnEnemy(Z,1);e.xp=4;e.gold=1;e.bg=1;
      X.hurt(e,1e12);
      const live=X.gems.a.filter(g=>g.on);
      res.push({mode,xp:4,gold:'×2',want:8,gemV:live.length===1?live[0].v:-1});}
    return res;},
  E(){   // 일반 적은 새끼를 안 만든다
    const S=begin(31);const e=X.spawnEnemy(N,1);const n0=X.enemies.a.filter(o=>o.on).length;X.hurt(e,1e12);return {before:n0,after:X.enemies.a.filter(o=>o.on).length};}
};
return true;})()
"""


async def main():
    p = H.make_copy(SRC, 'survivors_zacx.html', extra=EXTRA)
    srv = H.Srv()
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page='survivors_zacx.html')
        await pg.evaluate(JS)
        A = await pg.evaluate('__zt2.A()')
        print('A 꽉 찬 칸:', json.dumps({k: A[k] for k in ('kz', 'maxGen', 'kills', 'alive')}), 'gens', A['gens'][:12])
        ok(A['kz'] <= 7, 'A1 꽉 찬 칸에서 연달아 잡을 수 있는 자크 ≤ 7 (실제 %d)' % A['kz'])
        ok(A['maxGen'] <= 2, 'A2 세대 ≤ 2 (실제 %d)' % A['maxGen'])
        ok(A['kills'] == A['kz'], 'A3 처치 수 = 잡은 자크 수 (%d = %d)' % (A['kills'], A['kz']))
        ok(A['alive'] == 0, 'A4 마지막엔 자크가 안 남는다 (남은 %d)' % A['alive'])
        B = await pg.evaluate('__zt2.B()')
        print('B 넉넉한 칸:', json.dumps({k: B[k] for k in ('kz', 'maxGen', 'kills', 'alive')}), 'gens', B['gens'])
        ok(B['kz'] == 7, 'B1 정확히 7마리(1+2+4) (실제 %d)' % B['kz'])
        ok(sorted(B['gens']) == [0, 1, 1, 2, 2, 2, 2], 'B2 세대 0 1 1 2 2 2 2 (실제 %s)' % sorted(B['gens']))
        C = await pg.evaluate('__zt2.C(300)')
        print('C 무작위 칸 300판:', json.dumps({k: C[k] for k in ('n', 'max', 'maxGen')}), '이상 %d건' % len(C['bad']))
        ok(not C['bad'], 'C1 어떤 칸 배치에서도 ≤ 7마리 · 세대 ≤ 2 · 처치 수 일치 (이상 %d건 %s)' % (len(C['bad']), C['bad'][:3]))
        ok(C['n'] >= 250, 'C2 시험이 실제로 돌았다 (%d판)' % C['n'])
        D = await pg.evaluate('__zt2.D()')
        for d in D:
            print('D', d['mode'], 'pre', d['pre'], '\n   kids', d['kids'], '\n   want', d['want'])
            if d['mode'] == 'full':
                ok(len(d['kids']) == 0, 'D1 칸이 꽉 찼으면(빈 칸 없음) 새끼를 억지로 만들지 않는다 — 부모 칸을 덮어쓰지 않는다 (새끼 %d마리)' % len(d['kids']))
            else:
                good = len(d['kids']) == 2 and all(
                    k['gen'] == d['want']['gen'] and abs(k['r'] - d['want']['r']) < 1e-2 and abs(k['sp'] - d['want']['sp']) < 1e-2
                    and abs(k['xp'] - d['want']['xp']) < 1e-2 and abs(k['dmg'] - d['want']['dmg']) < 1e-2 and abs(k['mhp'] - d['want']['mhp']) < 1e-2
                    for k in d['kids'])
                ok(good, 'D2 빈 칸이 넉넉하면 새끼 둘 · 값이 부모(쓰러지기 전) 값에서 나온다 (새끼 %d마리)' % len(d['kids']))
        F = await pg.evaluate('__zt2.F()')
        for f in F:
            print('F', f)
            ok(f['gemV'] == f['want'], 'F %s 칸: 보석 값 = 부모 값(경험치 %s × 황금 %s) = %s (실제 %s)' % (f['mode'], f['xp'], f['gold'], f['want'], f['gemV']))
        E = await pg.evaluate('__zt2.E()')
        ok(E['after'] == E['before'] - 1, 'E1 일반 적은 새끼를 안 만든다 (%s)' % E)
        real = [e for e in errs if 'zacx' not in e]
        ok(not real, 'E2 콘솔·페이지 오류 0 %s' % real[:3])
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
