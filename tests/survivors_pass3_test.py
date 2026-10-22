# -*- coding: utf-8 -*-
"""🪙 동전 지갑 · 🧿 부적 · 🔗 연쇄 시험 — [2026-10-22 사장님 승인 패시브 P-2 · P-4 · P-5]
 A. 🪙 한 번 고를 때마다 경험치 구슬 +10% · 최대 HP -3%(출처 표 mhpSrc 에 「🪙 동전 지갑」으로 잡혀 ⚠기타가 0) · 60 아래로는 안 내려간다 · 카드에 최대 체력 변화가 적힌다.
 B. 🧿 치명적인 한 방은 통째로 막고(HP 그대로) 쿨타임(180초) 동안은 다시 안 막는다 · 치명적이지 않은 피해는 부적을 안 쓴다 · 쿨이 지나면 다시 준비 · 👼 부활보다 먼저 쓰인다.
 C. 🔗 gap(2초) 안에 이어서 10마리를 쓰러뜨리면 5초 동안 피해 +15% · 9마리에서 멈추면 없다 · 간격이 벌어지면 처음부터 · 버프는 5초 뒤 꺼진다 · 버프 중 다시 채우면 갱신.
 D. 세 패시브 카드가 문구와 함께 나오고(cardOf) 후보 풀(offers)에 들어온다 · 다 쌓은 장비로 오류 0.  E. 오류 0.
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['SV_CSX_OFF'] = '1'
import sv_harness as H
from playwright.async_api import async_playwright
EX = "window.__pp={xpMul,mhpSrc,takenMul,comboOn,charmReady,WALV,CHARMV,COMBOV,pv,PASS,RES,get S(){return S},set S(v){S=v},get state(){return state},set state(v){state=v}};"
JS = r"""
(()=>{const X=window.__p6x,P=window.__pp;
function begin(){X.CH_set('brj');X.start();const S=X.S;S.t=300;S.p.hp=S.p.mhp;S.p.inv=0;for(const o of X.enemies.a)o.on=false;X.props.clear();
  for(const k in S.w)delete S.w[k];S.w.feed=1;S.ps={};S.cd={};S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.spawnT=-1e12;X.tkCalc();X.synCalc();return S;}
function weak(S,i){const e=X.spawnEnemy(1,1);e.hp=e.mhp=1;e.sp=0;e.x=S.p.x+500+i*3;e.y=S.p.y;return e;}
function kill(S,n,dt){for(let i=0;i<n;i++){const e=weak(S,i);X.hurt(e,100);S.t+=dt;}}
window.__st={
 wal(){const S=begin();const x0=P.xpMul(),m0=S.p.mhp;X.applyUp({t:'p',k:'wal',l:0});const x1=P.xpMul(),m1=S.p.mhp;X.applyUp({t:'p',k:'wal',l:1});const x2=P.xpMul(),m2=S.p.mhp;
   const src=P.mhpSrc();const tag=X.cardOf({t:'p',k:'wal',l:2}).ds;
   const S2=begin();S2.p.mhp=S2.p.hp=62;X.applyUp({t:'p',k:'wal',l:0});X.applyUp({t:'p',k:'wal',l:1});
   return {dx1:x1-x0,dx2:x2-x1,m0,m1,m2,etc:src.etc,rows:src.rows,tag,floor:S2.p.mhp,hpOk:S2.p.hp<=S2.p.mhp};},
 charm(){const S=begin();S.ps.charm=1;S.ps.rev=1;S.p.hp=20;const r={};
   r.ready0=P.charmReady();
   r.small=X.hitP(5,'');r.hpSmall=S.p.hp;r.readyAfterSmall=P.charmReady();S.p.inv=0;
   r.lethal=X.hitP(500,'');r.hpLethal=S.p.hp;r.ready1=P.charmReady();r.state=X.state;r.inv=S.p.inv>0;
   S.p.inv=0;S.t+=100;r.ready2=P.charmReady();S.t+=81;r.ready3=P.charmReady();
   S.ps.charm=3;S.t+=1;r.cd3=P.CHARMV.cd[2];
   S.p.inv=0;S.p.hp=10;r.again=X.hitP(500,'');r.hpAgain=S.p.hp;
   return r;},
 combo(){const S=begin();S.ps.combo=1;const r={};const d0=X.dmgMul();
   kill(S,9,.1);r.on9=P.comboOn();kill(S,1,.1);r.on10=P.comboOn();r.ratio=X.dmgMul()/d0;
   S.t+=4.5;r.stillOn=P.comboOn();S.t+=1;r.off=P.comboOn();
   kill(S,6,.1);S.t+=2.5;kill(S,4,.1);r.afterGap=P.comboOn();   // 6 + (2.5초 쉼) + 4 = 이어지지 않는다
   kill(S,6,.1);r.refill=P.comboOn();S.t+=3;kill(S,10,.05);S.t+=3;r.refreshed=P.comboOn();   // 켜진 채 다시 10마리 → 끝이 뒤로 밀린다
   S.ps.combo=3;const c=S.x3.cc;c.n=0;c.u=-1;kill(S,7,.1);r.lv3at7=P.comboOn();kill(S,1,.1);r.lv3at8=P.comboOn();r.ratio3=X.dmgMul()/d0;
   return r;},
 cards(){const S=begin();const out={};for(const k of ['wal','charm','combo']){const c=X.cardOf({t:'p',k,l:0});out[k]={nm:c.nm,ds:c.ds.length>10,ic:c.ic};}
   let seen=new Set();for(let i=0;i<300;i++){S.lv=30;for(const o of X.offers(3))if(o.t==='p')seen.add(o.k);}
   return {out,seen:['wal','charm','combo'].filter(k=>seen.has(k)),max:['wal','charm','combo'].map(k=>P.PASS[k].max)};},
 resume(){const S=begin();S.ps.combo=2;S.ps.charm=2;S.ps.wal=1;X.applyUp({t:'p',k:'wal',l:1});S.p.hp=30;X.hitP(900,'');kill(S,4,.1);const before=JSON.stringify([S.x3.cg,S.x3.cc,S.p.mhp,S.ps]);
   P.RES.save('t');const text=localStorage.getItem(P.RES.KEY);P.state='title';const ok=P.RES.restore(text);const S2=P.S;
   return {ok,same:JSON.stringify([S2.x3.cg,S2.x3.cc,S2.p.mhp,S2.ps])===before,cg:S2.x3.cg,cc:S2.x3.cc,ready:P.charmReady()};},
 sink(){const errs=[];
   for(const k of ['wal','charm','combo'])for(let l=1;l<=3;l++){try{const S=begin();for(const kk in X.REL)S.rel[kk]=3;
       for(const kk of Object.keys(P.PASS))S.ps[kk]=Math.min(3,P.PASS[kk].max||3);S.ps[k]=l;
       for(const w of Object.keys(X.WEAP)){if(!X.WEAP[w].only&&Object.keys(S.w).length<6)S.w[w]=8;}X.tkCalc();X.synCalc();
       for(let i=0;i<10;i++){const e=X.spawnEnemy(1,2);e.sp=40;e.x=S.p.x+80+i*10;e.y=S.p.y+(i%3-1)*30;}
       for(let i=0;i<300;i++){X.keys={KeyD:true};S.p.hp=Math.max(S.p.hp,1);S.spawnT=-1e12;S.need=1e12;if(X.state==='lvup')X.pick(X.CUR[0]);if(X.state==='result')break;X.update(1/30);if(i%50===0)X.hitP(30,'');}
       X.keys={};if(S.p.hp!==S.p.hp||S.p.mhp!==S.p.mhp)errs.push('NaN hp '+k+l);}
     catch(e){errs.push(k+l+' '+e.message);}}
   return errs;}
};return true;})()
"""
async def main():
    p = H.make_copy('survivors.html', 'survivors_pass3.html', extra=EX)
    srv = H.Srv(); fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=800, h=600, page='survivors_pass3.html')
        await pg.evaluate(JS)
        r = await pg.evaluate('__st.wal()'); print('wal', r)
        ok(abs(r['dx1'] - .10) < 1e-9 and abs(r['dx2'] - .10) < 1e-9, 'A 경험치 구슬 +10%/Lv')
        ok(r['m1'] == r['m0'] - round(r['m0'] * .03) and r['m2'] < r['m1'], 'A2 최대 HP -3%%/Lv: %s → %s → %s' % (r['m0'], r['m1'], r['m2']))
        ok(r['etc'] == 0 and any(k == 'wal' for k, v in r['rows']), 'A3 출처 표에 🪙 동전 지갑 · ⚠기타 0 (%s)' % r['rows'])
        ok(r['floor'] >= 60 and r['hpOk'], 'A4 60 아래로는 안 내려간다: %s' % r['floor'])
        ok('최대 체력' in r['tag'], 'A5 카드에 최대 체력 변화가 적힌다')
        r = await pg.evaluate('__st.charm()'); print('charm', r)
        ok(r['ready0'] and r['small'] is False and r['hpSmall'] < 20 and r['readyAfterSmall'], 'B 치명적이지 않은 피해는 부적을 안 쓴다 (HP %.1f)' % r['hpSmall'])
        ok(r['lethal'] is False and r['hpLethal'] == r['hpSmall'] and not r['ready1'] and r['state'] == 'play' and r['inv'], 'B2 치명적인 한 방은 막힌다 — HP 그대로 · 쿨 시작 · 짧은 무적 (%s)' % r['state'])
        ok(not r['ready2'] and r['ready3'], 'B3 쿨타임 180초: 100초 뒤엔 아직, 181초 뒤엔 준비')
        ok(r['cd3'] == 120, 'B4 Lv3 쿨타임 120초')
        r = await pg.evaluate('__st.combo()'); print('combo', r)
        ok(not r['on9'] and r['on10'] and abs(r['ratio'] - 1.15) < 1e-6, 'C 9마리는 안 되고 10마리째에 켜진다 · 피해 ×%.3f' % r['ratio'])
        ok(r['stillOn'] and not r['off'], 'C2 버프는 5초: 4.5초 뒤엔 켜져 있고 5.5초 뒤엔 꺼진다')
        ok(not r['afterGap'], 'C3 간격이 2초 넘게 벌어지면 처음부터 센다')
        ok(r['refill'] and r['refreshed'], 'C4 버프 중 다시 채우면 갱신된다')
        ok(not r['lv3at7'] and r['lv3at8'] and abs(r['ratio3'] - 1.21) < 1e-6, 'C5 Lv3 은 8마리 · 피해 ×%.3f' % r['ratio3'])
        r = await pg.evaluate('__st.cards()'); print('cards', r)
        ok(all(v['ds'] for v in r['out'].values()) and r['seen'] == ['wal', 'charm', 'combo'] and r['max'] == [3, 3, 3], 'D 카드 문구 · 후보 풀 등장 · 최대 Lv3 (%s)' % r['seen'])
        r = await pg.evaluate('__st.resume()'); print('resume', r)
        ok(r['ok'] and r['same'] and not r['ready'] and r['cc']['n'] == 4, 'D3 이어하기 왕복에서 부적 사용 시각 · 연쇄 개수 · 최대 HP · 패시브가 그대로다')
        r = await pg.evaluate('__st.sink()'); print('sink', r[:4])
        ok(not r, 'D2 장비 전부 끼운 채 오류 0 %s' % r[:3])
        ok(not errs, 'E 오류 0 %s' % errs[:3])
        await b.close()
    srv.close(); os.remove(os.path.join(H.ROOT, 'survivors_pass3.html'))
    print('FAIL %d' % len(fails) if fails else 'ALL OK'); sys.exit(1 if fails else 0)
asyncio.run(main())
