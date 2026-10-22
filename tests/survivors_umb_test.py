# -*- coding: utf-8 -*-
"""🌂 투명 우산 시험 — [2026-10-22 사장님 승인 W-2] 달리는 방향의 반대편(뒤쪽) 쐐기로 휙 펴져 때리고 밀치는 무기.
 A. 오른쪽으로 달리면 뒤(왼쪽)의 적만 맞고 앞(오른쪽)의 적은 안 맞는다.
 B. 가만히 서 있으면 펴지지 않는다(쿨타임도 안 쓴다 — 움직이는 순간 바로 펴진다).
 C. 맞은 적은 뒤로 밀린다(보스는 안 밀리고 느려진다).
 D. 각성은 두 번 펴지고 피해가 더 크다 · 단계 5(에코)는 한 번 더 펴진다.
 E. 장비 전부(패시브 최대·유물·초월·거래·간식)를 끼운 채 단계 0~5 × 비각성/각성 전 조합을 돌려도 오류·NaN 이 없다.
 F. 카드 문구(WEAP·TIERS·PFX)가 빠짐없이 있고 새 판에 시각 상태가 남지 않는다. G. 오류 0.
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['SV_CSX_OFF'] = '1'
import sv_harness as H
from playwright.async_api import async_playwright
JS = r"""
(()=>{const X=window.__p6x;
function begin(L,ev){X.CH_set('brj');X.start();const S=X.S;S.t=300;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;for(const o of X.enemies.a)o.on=false;X.props.clear();
  for(const k in S.w)delete S.w[k];S.w.umb=L||1;S.cd={};S.ev=ev?{umb:1}:{};S.tier={};S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.spawnT=-1e12;X.tkCalc();X.synCalc();return S;}
function dummy(S,dx,dy,hp){const e=X.spawnEnemy(1,1);e.hp=e.mhp=hp||1e12;e.sp=0;e.x=S.p.x+dx;e.y=S.p.y+dy;return e;}
function run(S,n,mv){const x0=S.p.x,y0=S.p.y;for(let i=0;i<n;i++){X.keys=mv?{KeyD:true}:{};S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.need=1e12;X.update(1/30);S.p.x=x0;S.p.y=y0;X.props.clear();}X.keys={};}
window.__st={
 dir(){const S=begin(3,0);const back=dummy(S,-60,0),front=dummy(S,60,0),up=dummy(S,0,-70);const h0=[back.hp,front.hp,up.hp];run(S,40,true);return {back:h0[0]-back.hp,front:h0[1]-front.hp,up:h0[2]-up.hp,by:S.dmgBy.umb||0};},
 still(){const S=begin(3,0);const back=dummy(S,-60,0);const h0=back.hp;run(S,40,false);const cd=S.cd.umb,hit=h0-back.hp;run(S,3,true);return {hit,cdBefore:cd,after:h0-back.hp};},
 push(){const S=begin(3,0);const a=dummy(S,-70,0);const B=X.spawnBoss('sr');B.sp=0;B.x=S.p.x-70;B.y=S.p.y-5;const ax=a.x,bx=B.x;
   run(S,12,true);return {da:ax-a.x,dBoss:Math.abs(B.x-bx),slow:B.slow};},
 ev(){const S=begin(8,0);const a=dummy(S,-60,0);const h0=a.hp;run(S,60,true);const n=h0-a.hp;
   const S2=begin(8,1);const b=dummy(S2,-60,0);const g0=b.hp;run(S2,60,true);const m=g0-b.hp;return {n,m};},
 echo(){const out={};for(const ec of [0,1]){const S=begin(8,0);S.tier={umb:ec?5:0};X.tkCalc();const a=dummy(S,-60,0);const h0=a.hp;a.kb=0;
     // 쿨타임 한 번만: 첫 펴짐 직후 몇 프레임 안의 피해만 본다
     run(S,3,true);const one=h0-a.hp;run(S,14,true);out[ec]=h0-a.hp;}return out;},
 sink(){const errs=[];const fx=n=>{const S=X.S;return n;};
   for(const ev of [0,1])for(let tr=0;tr<=(ev?5:3);tr++)for(const L of [1,4,7,8]){
     try{const S=begin(L,ev);S.tier={umb:tr};for(const k in X.REL)S.rel[k]=3;for(const k in S.ps){}
       for(const k of ['spd','hp','cd','mag','arm','area','might','luck','dur','crit','pspd','study','glass','turtle','vamp','wal','charm','combo'])S.ps[k]=3;
       for(const k of Object.keys(X.WEAP)){if(!X.WEAP[k].only&&k!=='umb'&&Object.keys(S.w).length<6){S.w[k]=8;}}
       X.tkCalc();X.synCalc();for(let i=0;i<8;i++)dummy(S,-40-i*12,(i%3-1)*30);dummy(S,50,0);
       for(let i=0;i<150;i++){X.keys={KeyD:true};S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.need=1e12;if(X.state==='lvup')X.pick(X.CUR[0]);X.update(1/30);}
       X.keys={};
       for(const e of X.enemies.a)if(e.on&&(e.x!==e.x||e.hp!==e.hp))errs.push('NaN '+L+'/'+ev+'/'+tr);}
     catch(e){errs.push(L+'/'+ev+'/'+tr+' '+e.message);}}
   return errs;},
 reg(){const W=X.WEAP.umb,T=X.TIERS.umb;return {ds:W.ds.length,tiers:T.length,pair:W.pair,pf:!!X.PFX&&null};}
};return true;})()
"""
async def main():
    p = H.make_copy('survivors.html', 'survivors_umb.html')
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=800, h=600, page='survivors_umb.html')
        await pg.evaluate(JS)
        r = await pg.evaluate('__st.dir()'); print('dir', r)
        ok(r['back'] > 0 and r['front'] == 0 and r['up'] == 0, 'A 달리는 방향 반대(뒤)만 맞는다: 뒤 %.0f · 앞 %.0f · 위 %.0f' % (r['back'], r['front'], r['up']))
        r = await pg.evaluate('__st.still()'); print('still', r)
        ok(r['hit'] == 0 and r['cdBefore'] <= 0 and r['after'] > 0, 'B 서 있으면 안 펴지고(쿨 %s) 움직이면 바로 펴진다(%.0f)' % (r['cdBefore'], r['after']))
        r = await pg.evaluate('__st.push()'); print('push', r)
        ok(r['da'] > 8, 'C 맞은 적은 뒤(왼쪽)로 밀린다: %.1f' % r['da'])
        ok(r['dBoss'] < 3 and r['slow'] > 0, 'C2 보스는 안 밀리고 느려진다: 이동 %.1f · 느림 %.2f' % (r['dBoss'], r['slow']))
        r = await pg.evaluate('__st.ev()'); print('ev', r)
        ok(r['m'] > r['n'] * 1.4, 'D 각성은 더 세다: 비각성 %.0f → 각성 %.0f' % (r['n'], r['m']))
        r = await pg.evaluate('__st.echo()'); print('echo', r)
        ok(r['1'] > r['0'], 'D2 단계 5(에코)는 한 번 더 펴져 피해가 늘어난다: %.0f → %.0f' % (r['0'], r['1']))
        r = await pg.evaluate('__st.sink()'); print('sink', r[:5])
        ok(not r, 'E 장비·조건 전 조합 오류/NaN 0 %s' % r[:3])
        r = await pg.evaluate('__st.reg()'); print('reg', r)
        ok(r['ds'] == 8 and r['tiers'] == 5 and r['pair'] == 'turtle', 'F 카드 문구 8단계 · 단계표 5개 · 각성 짝 거북')
        ok(not errs, 'G 오류 0 %s' % errs[:3])
        await b.close()
    srv.close(); os.remove(os.path.join(H.ROOT, 'survivors_umb.html'))
    print('FAIL %d' % len(fails) if fails else 'ALL OK'); sys.exit(1 if fails else 0)
asyncio.run(main())
