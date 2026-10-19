# -*- coding: utf-8 -*-
"""🐲 프싱 재설계(2026-10-16) 검증 — 쌍둥이 이빨 장판이 베기마다 여러 곳에 겹쳐 깔림 · 용 변신 불꽃 오라가 끈기·곱빼기·무기 레벨·유물을 받음 · 🐲 타오르는 비늘.
사용: python3 tests/survivors_psg_redesign_test.py"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

SETUP = """const x=__p6x;x.CH_set('psg');x.start();const S=x.S;S.p.hp=S.p.mhp=1e9;S.w.twin=%d;if(%d)S.ev.twin=1;x.tkCalc();"""
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        # 1. 장판이 여러 곳(앞쪽 부채꼴)에 깔리고 2줄에 머물지 않는다
        r = await pg.evaluate("""()=>{const x=__p6x,o={};
          x.CH_set('psg');x.start();const S=x.S;S.p.hp=S.p.mhp=1e9;S.w.twin=6;x.tkCalc();
          const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e12;e.x=S.p.x+60;e.y=S.p.y;e.sp=0;
          let mx=0;const seen=new Set();
          for(let i=0;i<30*12;i++){if(x.state!=='play')break;S.p.hp=S.p.mhp;e.x=S.p.x+60;e.y=S.p.y;x.update(1/30);
            const fl=S.x3.f.filter(q=>q.k==='fl');mx=Math.max(mx,fl.length);}
          const fl=S.x3.f.filter(q=>q.k==='fl');
          o.max=mx;o.n=fl.length;
          // 장판들의 가로(진행 방향 수직) 퍼짐과 세로 퍼짐
          const xs=fl.map(q=>q.x),ys=fl.map(q=>q.y);o.sx=Math.max(...xs)-Math.min(...xs);o.sy=Math.max(...ys)-Math.min(...ys);
          const pts=fl.map(q=>[Math.round(q.x/20),Math.round(q.y/20)]);o.uniq=new Set(pts.map(q=>q.join(','))).size;
          return o}""")
        check('Lv6 에서 장판이 5개 이상 동시에 깔린다(예전 최대 2~4)', r['max'] >= 5, r)
        check('장판이 한 줄이 아니라 앞뒤·좌우로 퍼진다', r['sx'] > 60 and r['sy'] > 40, (r['sx'], r['sy']))
        # (2026-10-18 곱빼기 패시브 제거 — 아래 amt 칸은 이제 쌍둥이 레벨: Lv4 → Lv8 은 개수 보너스 +2)
        # 2. 상한: 끈기·곱빼기에 따라 최대, 풀 상한 안
        r = await pg.evaluate("""()=>{const x=__p6x,o={};
          for(const [dur,amt,L,ev] of [[0,0,4,1],[5,0,4,1],[0,5,8,1],[5,5,8,1]]){
            x.CH_set('psg');x.start();const S=x.S;S.p.hp=S.p.mhp=1e9;S.w.twin=L;if(ev)S.ev.twin=1;x.tkCalc();S.ps.dur=dur;
            const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e12;e.x=S.p.x+60;e.y=S.p.y;e.sp=0;let mx=0,pool=0;
            for(let i=0;i<30*20;i++){if(x.state!=='play')break;S.p.hp=S.p.mhp;e.x=S.p.x+60;e.y=S.p.y;x.update(1/30);mx=Math.max(mx,S.x3.f.filter(q=>q.k==='fl').length);pool=Math.max(pool,S.x3.f.length);}
            o[dur+'_'+amt]=[mx,pool];}
          return o}""")
        print(r)
        a, bb, c, d = r['0_0'], r['5_0'], r['0_5'], r['5_5']
        check('장판 최대 개수가 끈기·쌍둥이 레벨(개수 보너스)로 늘어난다', bb[0] > a[0] and c[0] > a[0] and d[0] >= max(bb[0], c[0]), (a, bb, c, d))
        check('장판 때문에 엔티티 풀 상한(100)을 넘지 않는다', all(v[1] <= 100 for v in r.values()), r)
        # 3. 불꽃 오라: 쌍둥이 레벨·곱빼기·유물·끈기를 받는다
        r = await pg.evaluate("""()=>{const x=__p6x,o={};
          const aura=(L,rel,amtv,durv)=>{x.CH_set('psg');x.start();const S=x.S;S.p.hp=S.p.mhp=1e9;S.w={};if(L)S.w.twin=L;S.cd.twin=1e9;S.rel.sg_psg=rel;x.tkCalc();
            S.ps.dur=durv;
            S.rg=100;x.update(1/30);const dT=S.dT;
            const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e12;e.x=S.p.x+50;e.y=S.p.y;e.sp=0;S.live=[e];S.dA=0;
            const h=e.hp;S.cd.twin=1e9;x.update(1/30);return {dmg:h-e.hp,dT};};
          o.base=aura(1,0,0,0);o.lv8=aura(8,0,0,0);o.rel3=aura(1,3,0,0);o.dur=aura(1,0,0,4);return o}""")
        print(r)
        check('불꽃 오라 피해가 쌍둥이 이빨 레벨을 따라 는다', r['lv8']['dmg'] > r['base']['dmg'] * 1.5, (r['base'], r['lv8']))
        check('불꽃 오라 피해가 유물 3단계로 는다', r['rel3']['dmg'] > r['base']['dmg'] * 1.4, (r['base'], r['rel3']))
        check('변신 지속이 끈기로 는다', r['dur']['dT'] > r['base']['dT'] * 1.2, (r['base']['dT'], r['dur']['dT']))
        check('유물 3단계는 지속 +3.5초가 그대로', abs((r['rel3']['dT'] - r['base']['dT']) - 3.5) < .1, (r['base']['dT'], r['rel3']['dT']))
        # 4. 문구의 숫자는 SHV/U3 표 값을 읽는다
        r = await pg.evaluate("""()=>{const x=__p6x,o={};const SH=x.SHV;
          o.rel=[1,2,3].map(l=>x.REL.sg_psg.ds(l));o.relExp=[1,2,3].map(l=>[SH.rel[l],Math.round(SH.relD[l]*100),Math.round(SH.relR[l]*100),SH.relN[l]]);
          const pc=x.CHARS.find(c=>c.k==='psg');x.CH_set('psg');x.start();o.cs=x.cstat(pc).rows.map(r=>r.ds).join(' ');o.padN=SH.padN;o.cap=x.U3.twin.cap;return o}""")
        ok = all(all(str(v) in r['rel'][i] for v in r['relExp'][i]) for i in range(3))
        check('타오르는 비늘 문구가 표(SHV.rel·relD·relR·relN) 값과 일치', ok, r['rel'])
        check('프싱 능력 문구에 장판 +padN 이 들어간다', ('장판 +%d' % r['padN']) in r['cs'], r['cs'][:200])
        check('콘솔·페이지 에러 0', not errs, errs[:3])
        await b.close()
    print(f'\n{N[0]-len(FAILS)}/{N[0]} 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
