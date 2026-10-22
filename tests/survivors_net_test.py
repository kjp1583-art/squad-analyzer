# -*- coding: utf-8 -*-
"""🕸 부메랑 그물 시험 — [2026-10-22 사장님 승인 W-6] 던졌다 돌아오는 그물: 닿은 적을 느리게(피해는 낮다).
 A. 가장 가까운 적 쪽으로 날아가 사거리 끝에서 돌아서 내게 돌아오고 사라진다. 사거리 밖에 적만 있으면 던지지 않는다.
 B. 맞은 적은 느려진다(slow > 0) — 보스도(더 짧게). 같은 적은 0.35초 안에 두 번 맞지 않는다.
 C. Lv8 은 그물 2장, 각성은 앞뒤 3장 · 단계 5(돌아오는 길 ×1.6) 가 그물에 실린다.
 D. 장비 전부를 끼운 채 단계 0~5 × 비각성/각성 × 레벨 전 조합 오류/NaN 0.
 E. 새 판을 시작하면 날아다니던 그물이 지워진다. F. 카드 문구 8단계 · 단계표 5개 · 각성 짝 끈기. G. 오류 0.
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['SV_CSX_OFF'] = '1'
import sv_harness as H
from playwright.async_api import async_playwright
EX = "window.__nt={get nets(){return nets},get W4(){return W4},RES,get S(){return S},set S(v){S=v},get state(){return state},set state(v){state=v}};"
JS = r"""
(()=>{const X=window.__p6x;
function begin(L,ev,tier){X.CH_set('brj');X.start();const S=X.S;S.t=300;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;for(const o of X.enemies.a)o.on=false;X.props.clear();
  for(const k in S.w)delete S.w[k];S.w.net=L||1;S.cd={};S.ev=ev?{net:1}:{};S.tier=tier?{net:tier}:{};S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.spawnT=-1e12;X.tkCalc();X.synCalc();return S;}
function dummy(S,dx,dy,hp){const e=X.spawnEnemy(1,1);e.hp=e.mhp=hp||1e12;e.sp=0;e.x=S.p.x+dx;e.y=S.p.y+dy;return e;}
function step(S,n){for(let i=0;i<n;i++){S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.need=1e12;X.update(1/30);X.props.clear();}}
window.__st={
 flight(){const S=begin(3,0,0);const e=dummy(S,120,0);const px=S.p.x,py=S.p.y;let maxd=0,sawOut=false,back=false,gone=false,n0=0,phs=new Set();
   for(let i=0;i<120;i++){step(S,1);for(const n of window.__nt.nets.a)if(n.on){n0++;phs.add(n.ph);maxd=Math.max(maxd,Math.hypot(n.x-px,n.y-py));}if(i>5&&!window.__nt.nets.a.some(n=>n.on)){gone=true;break;}}
   return {maxd,phases:[...phs],gone,len:window.__nt.W4.net.len};},
 far(){const S=begin(3,0,0);dummy(S,900,0);step(S,60);return {on:window.__nt.nets.a.filter(n=>n.on).length,cd:S.cd.net};},
 slow(){const S=begin(3,0,0);const e=dummy(S,100,0),B=X.spawnBoss('sr');B.sp=0;B.x=S.p.x;B.y=S.p.y+200;let es=0,bs=0;
   const e2=dummy(S,0,-100);
   for(let i=0;i<40;i++){step(S,1);es=Math.max(es,e.slow);}
   // 보스 쪽: 가장 가까운 적이 보스일 때
   const S2=begin(3,0,0);const B2=X.spawnBoss('sr');B2.sp=0;B2.x=S2.p.x+110;B2.y=S2.p.y;for(let i=0;i<40;i++){step(S2,1);bs=Math.max(bs,B2.slow);}
   return {es,bs};},
 gap(){const S=begin(3,0,0);const e=dummy(S,100,0);let hits=0,last=e.hp,ts=[];for(let i=0;i<90;i++){step(S,1);if(e.hp<last){hits++;ts.push(+(S.t).toFixed(2));last=e.hp;}}
   let minGap=9;for(let i=1;i<ts.length;i++)minGap=Math.min(minGap,ts[i]-ts[i-1]);return {hits,minGap,ts};},
 count(){const out={};for(const [L,ev,tier,k] of [[3,0,0,'a'],[8,0,0,'b'],[8,1,0,'c'],[8,1,5,'d']]){const S=begin(L,ev,tier);dummy(S,100,0);let mx=0,rt=0;for(let i=0;i<30;i++){step(S,1);const on=window.__nt.nets.a.filter(n=>n.on);mx=Math.max(mx,on.length);for(const n of on)rt=Math.max(rt,n.rt);}out[k]={n:mx,rt};}return out;},
 sink(){const errs=[];
   for(const ev of [0,1])for(let tr=0;tr<=(ev?5:3);tr++)for(const L of [1,4,7,8]){
     try{const S=begin(L,ev,tr);for(const k in X.REL)S.rel[k]=3;
       for(const k of ['spd','hp','cd','mag','arm','area','might','luck','dur','crit','pspd','study','glass','turtle','vamp','wal','charm','combo'])S.ps[k]=3;
       for(const k of Object.keys(X.WEAP)){if(!X.WEAP[k].only&&k!=='net'&&Object.keys(S.w).length<6){S.w[k]=8;}}
       X.tkCalc();X.synCalc();for(let i=0;i<10;i++)dummy(S,60+i*14,(i%3-1)*40);
       for(let i=0;i<150;i++){X.keys={KeyA:true};S.p.hp=S.p.mhp;S.p.inv=1e9;S.spawnT=-1e12;S.need=1e12;if(X.state==='lvup')X.pick(X.CUR[0]);X.update(1/30);}
       X.keys={};
       for(const n of window.__nt.nets.a)if(n.on&&(n.x!==n.x||n.y!==n.y))errs.push('NaN net '+L+'/'+ev+'/'+tr);
       for(const e of X.enemies.a)if(e.on&&(e.x!==e.x||e.hp!==e.hp))errs.push('NaN '+L+'/'+ev+'/'+tr);}
     catch(e){errs.push(L+'/'+ev+'/'+tr+' '+e.message);}}
   return errs;},
 clear(){const S=begin(3,0,0);dummy(S,100,0);step(S,6);const a=window.__nt.nets.a.filter(n=>n.on).length;X.newRun();return {a,b:window.__nt.nets.a.filter(n=>n.on).length};},
 resume(){const S=begin(8,1,5);dummy(S,100,0);step(S,12);const A=window.__nt;const dig=()=>JSON.stringify(A.nets.a.filter(n=>n.on).map(n=>[n.x,n.y,n.ux,n.uy,n.d,n.ph,n.len,n.dmg,n.R,n.sl,n.id,n.ev,n.rt]));
   const d0=dig(),n0=A.nets.a.filter(n=>n.on).length;X.pauseGame&&0;A.RES.save('t');const text=localStorage.getItem(A.RES.KEY);
   for(const n of A.nets.a)n.on=false;A.state='title';const ok=A.RES.restore(text);return {ok,n0,n1:A.nets.a.filter(n=>n.on).length,same:dig()===d0};},
 reg(){const W=X.WEAP.net,T=X.TIERS.net;return {ds:W.ds.length,tiers:T.length,pair:W.pair};}
};return true;})()
"""
async def main():
    p = H.make_copy('survivors.html', 'survivors_net.html', extra=EX)
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=800, h=600, page='survivors_net.html')
        await pg.evaluate(JS)
        r = await pg.evaluate('__st.flight()'); print('flight', r)
        ok(abs(r['maxd'] - r['len']) < 20 and r['phases'] == [0, 1] and r['gone'], 'A 사거리(%d) 끝까지 날아갔다 돌아와 사라진다: 최대 %.0f · 단계 %s' % (r['len'], r['maxd'], r['phases']))
        r = await pg.evaluate('__st.far()'); print('far', r)
        ok(r['on'] == 0, 'A2 사거리 밖 적만 있으면 던지지 않는다')
        r = await pg.evaluate('__st.slow()'); print('slow', r)
        ok(r['es'] > 1 and 0 < r['bs'] < r['es'], 'B 맞은 적은 느려진다(%.2f초) — 보스는 더 짧게(%.2f초)' % (r['es'], r['bs']))
        r = await pg.evaluate('__st.gap()'); print('gap', r)
        ok(r['hits'] >= 2 and r['minGap'] >= 0.3, 'B2 같은 적은 0.35초 안에 두 번 맞지 않는다: %d번 · 최소 간격 %.2f' % (r['hits'], r['minGap']))
        r = await pg.evaluate('__st.count()'); print('count', r)
        ok(r['a']['n'] == 1 and r['b']['n'] == 2 and r['c']['n'] == 3 and r['a']['rt'] == 1 and r['d']['rt'] == 1.6, 'C 그물 수(1/2/3) · 돌아오는 길 배수(1→1.6)')
        r = await pg.evaluate('__st.sink()'); print('sink', r[:4])
        ok(not r, 'D 장비·조건 전 조합 오류/NaN 0 %s' % r[:3])
        r = await pg.evaluate('__st.clear()'); print('clear', r)
        ok(r['a'] > 0 and r['b'] == 0, 'E 새 판이면 날던 그물이 지워진다 (%s)' % r)
        r = await pg.evaluate('__st.resume()'); print('resume', r)
        ok(r['ok'] and r['n0'] >= 3 and r['n1'] == r['n0'] and r['same'], 'H 이어하기 왕복에서 날던 그물이 그대로 돌아온다 (%s)' % r)
        r = await pg.evaluate('__st.reg()'); print('reg', r)
        ok(r['ds'] == 8 and r['tiers'] == 5 and r['pair'] == 'dur', 'F 카드 문구 8단계 · 단계표 5개 · 각성 짝 끈기')
        ok(not errs, 'G 오류 0 %s' % errs[:3])
        await b.close()
    srv.close(); os.remove(os.path.join(H.ROOT, 'survivors_net.html'))
    print('FAIL %d' % len(fails) if fails else 'ALL OK'); sys.exit(1 if fails else 0)
asyncio.run(main())
