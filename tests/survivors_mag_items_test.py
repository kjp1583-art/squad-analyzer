# -*- coding: utf-8 -*-
"""🧲 흐접새우 서바이벌 「획득 범위가 아이템까지」 시험 (2026-10-18 사장님 지시)

사장님 진단: 「다이아(💎)가 경험치를 다 끌어모으니 획득 범위는 가치가 없다 — 치킨·폭탄까지 범위가 늘어야 가치가 있다」.
  · 치킨(🍗)·다이아(💎)·폭탄(💣)도 내 획득 범위 안에 들어오면 끌려와서 주워진다: 반경 = (p.r+14) + K×70×(magMul−1)
  · 획득 범위가 없으면(magMul=1) 옛 동작과 완전히 같다 · 상자(🎁)는 제외(일부러 가서 연다)
  · 초월 2단계: 20초마다 2.5초 동안 화면의 치킨·폭탄·다이아를 끌어온다(예전: 경험치 보석 전부 — 다이아와 겹쳐서 교체) · 보석은 더 안 끌어온다
  · 끌려온 폭탄은 기존 usePick('bomb') 그대로(내 자리에서 터짐) — 내가 다치지 않는다

시험(실제 게임 코드 — mapTick · usePick · update — 를 부른다):
  A  옛 동작과 같다(magMul=1): 아이템이 안 움직이고 몸이 닿아야만 주워진다 — 옛 규칙의 직접 구현(오라클)과 프레임마다 비교
  B  늘어난 만큼 끌린다: 획득 범위 Lv1~5 × 치킨·다이아·폭탄 — 반경 안은 끌려오고(속도 일정) 밖은 그대로
  C  상자는 어떤 경우에도 안 끌린다(범위 최대·초월 20초 끌어오기 중에도)
  D  초월 20초: 화면 안 아이템만 · 2.5초 동안만 · 20초마다 · 보석은 안 끌어온다(예전 동작 제거) · 초월 1단계(+40%)는 범위 배율에만
  E  끌려온 폭탄은 내 자리에서 터지고 나는 안 다친다 · 치킨은 한 번만 주워진다
  F  캐릭터 고유 줍기 보너스(김야옹 mag)도 아이템 끌어오기에 쓰인다
  G  전체 판이 옛 코드와 비트까지 같다(획득 범위·초월 없는 빌드): 같은 시드·같은 조작 → 같은 지문 (BASE_REV 의 survivors.html 과 비교)
  H  카드 문구가 값을 읽는다(PASS.mag · PT.mag) · 옛 「보석을 전부 빨아들인다」 문구 없음
  I  캐릭터 전부 × 획득 범위 Lv1~5 × 초월: 아이템을 뿌려 놓고 20초 — 오류·NaN 없음
  --mutants: 고친 줄을 하나씩 되돌린 사본에서 시험이 빨강이 되는지 본다
사용: python3 tests/survivors_mag_items_test.py [--only A,B,..] [--mutants]
"""
import asyncio, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ['SV_CSX_OFF'] = '1'
import sv_harness as H
from playwright.async_api import async_playwright

SRC = os.environ.get('MI_HTML', 'survivors.html')
BASE_REV = 'ef2950c9ceac34b13858ec0324b31727391cb3c0'   # 이 작업을 시작할 때의 main — 옛 동작 기준
ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
MUTANTS = '--mutants' in sys.argv

EXTRA = r"""window.__ms={MAGV,magMul,items,gems,dropItem,usePick,PICK,PT,PASS,mapTick,relTick,pv,PTV,CHARS,
  get W(){return W},get H(){return H},get SC(){return SC},get picks(){return window.__mp},resetP(){window.__mp=[]}};
window.__mp=[];{const up=usePick;usePick=function(k){window.__mp.push(k);return up.apply(this,arguments);};}
"""

JS = r"""
(()=>{
const X=window.__p6x,T=window.__ms;
const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
function scene(o){o=o||{};Math.random=mb(o.seed||5);X.CH_set(o.ch||'brj');X.start();const S=X.S;
  S.ps=Object.assign({},o.ps||{});S.pt=Object.assign({},o.pt||{});S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.spawnT=-1e12;S.need=1e12;S.xp=0;S.pendingLv=0;
  S.p.mhp=1000;S.p.hp=500;S.p.inv=0;/* HP 50% — 치킨은 HP 가 낮을 때만 끌려온다 */S.magT=o.magT===undefined?5:o.magT;for(const q of X.enemies.a)q.on=false;X.props.clear();for(const g of X.gems.a)g.on=false;for(const it of X.items.a)it.on=false;T.resetP();return S;}
function put(S,k,dx,dy){T.dropItem(k,S.p.x+dx,S.p.y+(dy||0));const it=X.items.a.filter(o=>o.on).pop();it.life=1e6;return it;}
const DT=1/30;
function steps(S,n){for(let i=0;i<n;i++)X.mapTick(DT);}
window.__mt={
  A(){const out=[];for(const ch of ['brj','jjg','hrb','ssu']){const S=scene({ch});const p=S.p,R0=p.r+14;const mg=T.magMul();
      const its=[];for(const k of ['chicken','magnet','bomb','chest'])for(const d of (k==='chest'?[R0+4,R0*2,R0*4,300]:[R0-4,R0+4,R0*2,R0*4,300])){its.push({k,d,it:put(S,k,d,0)});}
      // 옛 규칙: 움직이지 않고 p.r+14 안이면 주워진다 — 프레임마다 직접 계산해 비교
      let bad=[],picked=0,hp0=S.p.hp;const old=new Map(its.map(o=>[o.it,{on:true,x:o.it.x,y:o.it.y}]));
      for(let f=0;f<30;f++){const wasOn=its.map(o=>o.it.on);const exp=its.map(o=>wasOn[its.indexOf(o)]&&((o.it.x-p.x)**2+(o.it.y-p.y)**2<R0**2));
        X.mapTick(DT);
        its.forEach((o,i)=>{if(!wasOn[i])return;if(o.it.x!==old.get(o.it).x||o.it.y!==old.get(o.it).y)bad.push({ch,k:o.k,d:o.d,f,why:'moved'});
          if(exp[i]===o.it.on)bad.push({ch,k:o.k,d:o.d,f,why:'pickup mismatch',exp:exp[i],on:o.it.on});});
        S.p.hp=S.p.mhp;}
      out.push({ch,mg,bad:bad.slice(0,3),n:bad.length,picks:T.picks.length});}
    return out;},
  B(){const out=[];for(let L=1;L<=5;L++)for(const k of ['chicken','magnet','bomb']){
      const S=scene({ps:{mag:L}});const p=S.p,mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);
      const a=put(S,k,R-6,0),b=put(S,k,-(R+8),0);const ax=a.x,bx=b.x;X.mapTick(DT);S.p.hp=S.p.mhp;
      const step=T.MAGV.spd*DT;out.push({L,k,mg:+mg.toFixed(3),R:+R.toFixed(2),pulled:+(ax-a.x).toFixed(4)||(a.on?0:'picked'),want:+step.toFixed(4),outsideMoved:b.x!==bx||b.y!==p.y});}
    return out;},
  Bspeed(){const S=scene({ps:{mag:5}});const p=S.p,mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);const it=put(S,'chicken',R-2,0);let f=0;const d0=it.x-p.x;
    S.p.hp=1;const hp0=S.p.hp;while(it.on&&f<600){X.mapTick(DT);f++;}
    return {R:+R.toFixed(1),frames:f,want:Math.ceil((R-2-(p.r+14))/(T.MAGV.spd*DT))+1,picked:T.picks.length,hpUp:S.p.hp>hp0};},
  C(){const out={};for(const mode of ['maxmag','transcend']){const S=scene({ps:{mag:5},pt:mode==='transcend'?{mag:2}:{},magT:mode==='transcend'?0:5});
      const p=S.p,mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);const c1=put(S,'chest',R*.5,0),c2=put(S,'chest',R+30,0);const x1=c1.x,x2=c2.x;
      for(let i=0;i<12;i++){X.mapTick(DT);}   // 0.4초
      out[mode]={moved1:c1.x!==x1,moved2:c2.x!==x2,on1:c1.on,on2:c2.on};}
    return out;},
  D(){const o={};const S=scene({ps:{mag:5},pt:{mag:2},magT:0});const p=S.p;const hw=T.W/2/T.SC+40,hh=T.H/2/T.SC+40;
    const mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);o.R=+R.toFixed(1);o.hw=+hw.toFixed(0);
    const inS=put(S,'chicken',R+Math.min(220,hw-R-30),0),far=put(S,'chicken',hw+300,0),bm=put(S,'bomb',0,R+Math.min(150,hh-R-30)),mag=put(S,'magnet',-(R+Math.min(200,hw-R-30)),0);
    const g=T.gems.get();g.x=p.x+(70*mg+90);g.y=p.y;g.v=1;g.mag=0;   // 보석: 범위(70×배율) 밖 → 초월이어도 안 끌려와야 한다
    const x0=inS.x,fx=far.x,by=bm.y,mx=mag.x;X.mapTick(DT);o.trigger={magT:+S.magT.toFixed(3),inMoved:inS.x!==x0,bmMoved:bm.y!==by,magMoved:mag.x!==mx,farMoved:far.x!==fx};
    o.gemPulled=!!g.mag;
    // 창(2.5초)이 열려 있는 동안은 계속 끌려와 결국 주워진다
    let f=0;while((inS.on||bm.on||mag.on)&&f<200){X.mapTick(DT);f++;}
    o.pickedAll=!inS.on&&!bm.on&&!mag.on;o.frames=f;o.farStill=far.x===fx&&far.on;o.picks=T.picks.slice();
    // 창이 닫힌 뒤(2.5초 이후)에 새로 놓은 아이템은 다음 20초 전까지 안 끌려온다
    const S2=scene({ps:{mag:1},pt:{mag:2},magT:0});const hw2=T.W/2/T.SC+40;X.mapTick(DT);for(let i=0;i<Math.ceil(T.MAGV.tpT/DT)+3;i++){S2.magT-=DT;X.mapTick(DT);}
    const late=put(S2,'chicken',Math.min(260,hw2-40),0);const lx=late.x;for(let i=0;i<10;i++)X.mapTick(DT);o.lateMoved=late.x!==lx;o.magT2=+S2.magT.toFixed(2);
    // 다시 20초가 지나면 또 열린다
    const S3=scene({ps:{mag:1},pt:{mag:2},magT:0});X.mapTick(DT);const m1=S3.magT;for(let i=0;i<Math.round(20/DT)+2;i++){S3.magT-=DT;}   // 시계만 20초 흘림(relTick 이 하는 일)
    const again=put(S3,'chicken',Math.min(260,T.W/2/T.SC),0);const ax=again.x;X.mapTick(DT);o.again={reset:S3.magT>19,moved:again.x!==ax||!again.on};
    // 초월 1단계는 20초 끌어오기가 없다
    const S4=scene({ps:{mag:5},pt:{mag:1},magT:0});const f4=put(S4,'chicken',T.W/2/T.SC-60,0);const fx4=f4.x;X.mapTick(DT);o.pt1={magT:S4.magT,moved:f4.x!==fx4};
    o.mag1={pt0:(()=>{const a=scene({ps:{mag:5}});const m0=T.magMul();const b=scene({ps:{mag:5},pt:{mag:1}});return +(T.magMul()-m0).toFixed(3);})()};
    {const S5=scene({ps:{mag:5},pt:{mag:2},magT:0});S5.spawnT=-1e12;const g5=T.gems.get();g5.x=S5.p.x+400;g5.y=S5.p.y;g5.v=1;g5.mag=0;const gx=g5.x;   // 진짜 update 로 — 범위(약 203) 밖 보석은 초월 20초 창에도 그대로
      for(let i=0;i<12;i++){S5.p.hp=S5.p.mhp;X.update(DT);}o.gemUpd={mag:!!g5.mag,moved:g5.x!==gx,magT:+S5.magT.toFixed(2)};}
    return o;},
  E(){const o={};{const S=scene({ps:{mag:5}});S.p.hp=S.p.mhp=1000;for(const q of X.enemies.a)q.on=false;const p=S.p,mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);
      const bomb=put(S,'bomb',R-4,0);const n0=X.enemies.a.filter(e=>e.on).length;let f=0;while(bomb.on&&f<300){X.mapTick(DT);f++;}
      o.bomb={picked:T.picks.filter(k=>k==='bomb').length,hp:S.p.hp,state:X.state,frames:f};}
    {const S=scene({ps:{mag:5}});S.p.hp=100;S.p.mhp=1000;const p=S.p,mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);const ch=put(S,'chicken',R-4,0);let f=0;while(ch.on&&f<300){X.mapTick(DT);f++;}
      for(let i=0;i<30;i++)X.mapTick(DT);o.chicken={picked:T.picks.filter(k=>k==='chicken').length,hp:S.p.hp,heal:Math.round(1000*0.2)};}
    return o;},
  F(){const out={};for(const ch of ['kyo','brj']){const S=scene({ch});const p=S.p,mg=T.magMul(),R=p.r+14+T.MAGV.K*70*(mg-1);const it=put(S,'chicken',38,0);/* 몸이 닿는 거리(30) 밖 · 김야옹 반경(40.5) 안 */const x0=it.x;X.mapTick(DT);
      out[ch]={mg:+mg.toFixed(3),R:+R.toFixed(1),moved:it.x!==x0||!it.on};}
    return out;},
  fp(ch,secs,ban){Math.random=mb(321);X.CH_set(ch);X.start();const S=X.S;S.banned=ban||[];const out=[];let lastLv=0;
    for(let i=0;i<Math.round(secs*30);i++){const st=X.state;if(st==='lvup'){X.pick(X.CUR[0]);continue;}if(st!=='play'){X.resume();continue;}
      const k=Math.floor(S.t/2.5)%4;X.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];X.update(1/30);
      if(i%150===0)out.push([+S.t.toFixed(2),S.kills,S.lv,+S.p.hp.toFixed(3),+S.p.x.toFixed(2),+S.p.y.toFixed(2),X.items.a.filter(o=>o.on).length,X.gems.a.filter(o=>o.on).length,T.picks.length]);}
    return {out,end:[S.kills,S.lv,S.t,S.p.hp,S.p.x,S.p.y],mg:T.magMul(),ps:S.ps,pt:S.pt};},
  J(){const o={};const V=T.MAGV;for(const [nm,hpf] of [['full',1],['edgeLow',V.chk],['low',.3],['justAbove',V.chk+.02]]){const S=scene({ps:{mag:5}});S.p.mhp=1000;S.p.hp=Math.round(1000*hpf);const p=S.p,mg=T.magMul(),R=p.r+14+V.K*70*(mg-1);
      const c=put(S,'chicken',R-4,0),b=put(S,'bomb',-(R-4),0);const cx=c.x,bx=b.x;X.mapTick(DT);o[nm]={chickenMoved:c.x!==cx||!c.on,bombMoved:b.x!==bx||!b.on,hp:S.p.hp};}
    o.chk=V.chk;return o;},
  H(){return {mag:T.PASS.mag.ds,pt:T.PT.mag,K:T.MAGV.K,spd:T.MAGV.spd,tpT:T.MAGV.tpT};},
  I(chars,Ls,pts){const o={n:0,bad:[]};for(const ch of chars)for(const L of Ls)for(const pt of pts){
      const S=scene({ch,ps:{mag:L},pt:pt?{mag:pt}:{},lv:20,seed:3,magT:0});S.p.hp=S.p.mhp=300;
      let err='';try{for(let t=0;t<600;t++){const st=X.state;if(st==='lvup'){X.pick(X.CUR[0]);continue;}if(st!=='play'){X.resume();continue;}
          S.p.hp=Math.max(S.p.hp,1);if(t%30===0){for(const k of ['chicken','magnet','bomb','chest'])T.dropItem(k,S.p.x+(Math.random()-.5)*900,S.p.y+(Math.random()-.5)*600);}
          S.spawnT=0;X.update(1/30);}}catch(e){err=String(e&&e.stack||e).slice(0,160);}
      const fin=[S.p.hp,S.p.x,S.p.y,S.magT].every(Number.isFinite)&&X.items.a.every(i=>!i.on||(Number.isFinite(i.x)&&Number.isFinite(i.y)));
      o.n++;if(err||!fin)o.bad.push({ch,L,pt,err,fin});}
    return o;}
};
return true;})()
"""


EXTRA_BASE = r"""window.__mp=[];{const up=usePick;usePick=function(k){window.__mp.push(k);return up.apply(this,arguments);};}
window.__ms={magMul,get picks(){return window.__mp},resetP(){window.__mp=[]}};
"""


def base_html():
    out = subprocess.run(['git', 'show', BASE_REV + ':survivors.html'], cwd=H.ROOT, capture_output=True)
    if out.returncode != 0:
        return None
    p = os.path.join(H.ROOT, 'survivors_msbase.html')
    open(p, 'wb').write(out.stdout)
    return 'survivors_msbase.html'


async def run_suite(src, tag=''):
    dst = 'survivors_ms%s.html' % tag
    p = H.make_copy(src, dst, extra=EXTRA)
    srv = H.Srv()
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg, flush=True)
        if not c:
            fails.append(msg)
    def want(s): return ONLY is None or s in ONLY
    near = lambda a, c, t=1e-6: abs(a - c) <= t * max(1, abs(c))
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page=dst)
            await pg.evaluate(JS)
            ev = lambda e: pg.evaluate(e)
            M = await ev('({K:__ms.MAGV.K,spd:__ms.MAGV.spd,tpT:__ms.MAGV.tpT})')
            if want('A'):
                A = await ev('__mt.A()')
                print('A', json.dumps(A), flush=True)
                for a in A:
                    ok(abs(a['mg'] - 1) < 1e-12 and a['n'] == 0 and a['picks'] > 0, 'A %s 획득 범위 없음(배율 %s): 아이템은 안 움직이고 몸이 닿아야만 주워진다 — 어긋남 %d건 %s · 주운 수 %d' % (a['ch'], a['mg'], a['n'], a['bad'], a['picks']))
            if want('B'):
                B = await ev('__mt.B()')
                print('B', json.dumps(B), flush=True)
                bad = [r for r in B if not (r['pulled'] == 'picked' or near(r['pulled'], r['want'], 1e-3)) or r['outsideMoved']]
                ok(len(B) == 15 and not bad, 'B 획득 범위 Lv1~5 × 치킨·다이아·폭탄 15가지: 반경 안은 한 프레임에 %.2f칸씩 끌려오고 반경 밖은 그대로 (이상 %s)' % (M['spd'] / 30, bad[:3]))
                ok(B[0]['R'] < B[4]['R'], 'B 단계가 오를수록 반경이 넓어진다 (Lv1 %s → Lv5 %s)' % (B[0]['R'], B[12 + 0]['R']))
                bs = await ev('__mt.Bspeed()')
                print('B속도', json.dumps(bs), flush=True)
                ok(bs['picked'] == 1 and bs['frames'] <= bs['want'] + 2 and bs['frames'] >= bs['want'] - 3, 'B 반경 가장자리의 치킨이 약 %d프레임 안에 도착해 한 번 주워진다 (%d프레임)' % (bs['want'], bs['frames']))
            if want('C'):
                C = await ev('__mt.C()')
                print('C', json.dumps(C), flush=True)
                ok(all(not v['moved1'] and not v['moved2'] and v['on1'] and v['on2'] for v in C.values()), 'C 상자는 범위 최대·초월 20초 중에도 안 끌려온다 %s' % C)
            if want('D'):
                D = await ev('__mt.D()')
                print('D', json.dumps(D), flush=True)
                t = D['trigger']
                ok(t['magT'] > 19 and t['inMoved'] and t['bmMoved'] and t['magMoved'], 'D 초월 2단계: 20초 시계가 돌고 화면 안 치킨·폭탄·다이아가 끌려온다 (%s)' % t)
                ok(not t['farMoved'] and D['farStill'], 'D 화면 밖 아이템은 안 끌려온다')
                ok(not D['gemPulled'] and not D['gemUpd']['mag'] and not D['gemUpd']['moved'] and D['gemUpd']['magT'] > 17, 'D 경험치 보석은 더 이상 통째로 끌어오지 않는다(범위 밖 보석 그대로 · 실제 update 로도) %s' % D['gemUpd'])
                ok(D['pickedAll'] and sorted(set(D['picks'])) == ['bomb', 'chicken', 'magnet'], 'D 끌려온 아이템은 결국 전부 주워진다 (%d프레임 · %s)' % (D['frames'], D['picks']))
                ok(not D['lateMoved'] and D['magT2'] < 20 - M['tpT'], 'D 창(%s초)이 닫힌 뒤에는 범위 밖 아이템이 안 끌려온다 (시계 %s)' % (M['tpT'], D['magT2']))
                ok(D['again']['reset'] and D['again']['moved'], 'D 20초가 지나면 다시 열린다 %s' % D['again'])
                ok(D['pt1']['magT'] <= 0 and not D['pt1']['moved'], 'D 초월 1단계는 20초 끌어오기가 없다 %s' % D['pt1'])
                ok(near(D['mag1']['pt0'], .4, 1e-6), 'D 초월 1단계의 획득 범위 +40%% 는 그대로 (배율 +%s)' % D['mag1']['pt0'])
            if want('E'):
                E = await ev('__mt.E()')
                print('E', json.dumps(E), flush=True)
                ok(E['bomb']['picked'] == 1 and E['bomb']['hp'] == 1000 and E['bomb']['state'] == 'play', 'E 끌려온 폭탄은 한 번 터지고 나는 안 다친다 (HP %s · 상태 %s)' % (E['bomb']['hp'], E['bomb']['state']))
                ok(E['chicken']['picked'] == 1 and E['chicken']['hp'] == 100 + E['chicken']['heal'], 'E 치킨은 한 번만 주워져 20%% 회복 (HP %s)' % E['chicken']['hp'])
            if want('F'):
                F = await ev('__mt.F()')
                print('F', json.dumps(F), flush=True)
                ok(F['kyo']['mg'] > 1 and F['kyo']['moved'] and (F['brj']['mg'] == 1 and not F['brj']['moved']), 'F 김야옹(고유 줍기 +50%%)은 패시브 없이도 아이템이 끌려온다 · 브장신은 안 끌린다 %s' % F)
            if want('J'):
                J = await ev('__mt.J()')
                print('J', json.dumps(J), flush=True)
                ok(not J['full']['chickenMoved'] and J['full']['bombMoved'], 'J HP 가득이면 치킨은 안 끌려오고(낭비 방지) 폭탄은 끌려온다 %s' % J['full'])
                ok(J['edgeLow']['chickenMoved'] and J['low']['chickenMoved'] and not J['justAbove']['chickenMoved'], 'J HP %d%% 이하부터 치킨이 끌려온다 (경계 %s · 낮음 %s · 바로 위 %s)' % (J['chk'] * 100, J['edgeLow']['chickenMoved'], J['low']['chickenMoved'], J['justAbove']['chickenMoved']))
            if want('H'):
                Hh = await ev('__mt.H()')
                print('H', json.dumps(Hh, ensure_ascii=False), flush=True)
                ok('치킨' in Hh['mag'] and '폭탄' in Hh['mag'] and '상자' in Hh['mag'], 'H 획득 범위 카드 문구가 아이템·상자 제외를 알린다')
                ok('치킨' in Hh['pt'][1] and '다이아' in Hh['pt'][1] and '보석' not in Hh['pt'][1] and '20초' in Hh['pt'][1], 'H 초월 2단계 문구: 20초마다 치킨·폭탄·다이아 (옛 「보석을 빨아들인다」 없음)')
            if want('I'):
                chars = await ev('__ms.CHARS.map(c=>c.k)')
                I = await pg.evaluate('([c,L,p])=>__mt.I(c,L,p)', [chars, [1, 3, 5], [0, 2]])
                print('I', I['n'], '판 · 이상', len(I['bad']), flush=True)
                ok(I['n'] >= 100 and not I['bad'], 'I 캐릭터 %d명 × 획득 범위 Lv1/3/5 × 초월 0/2 — %d판 20초 오류·NaN 없음 %s' % (len(chars), I['n'], I['bad'][:2]))
            real = [e for e in errs if 'survivors_ms' not in e]
            ok(not real, '콘솔·페이지 오류 0 %s' % real[:3])
            await b.close()
        if want('G') and src == 'survivors.html':
            bh = base_html()
            if not bh:
                print('  (G: 기준 사본을 git 에서 못 꺼내 건너뜀)')
            else:
                async with async_playwright() as pw:
                    b = await H.launch(pw)
                    res = {}
                    for nm, s in (('new', 'survivors_ms.html'), ('base', bh)):
                        d2 = 'survivors_msg_%s.html' % nm
                        H.make_copy(s if nm == 'base' else src, d2, extra=EXTRA_BASE)
                        res[nm] = {}
                        for ch in ['brj', 'jjg', 'hrb', 'ssu', 'eom', 'ildj']:   # 판마다 새 페이지 — 한 페이지에서 이어 돌리면 앞 판이 남긴 전역 상태가 섞인다
                            ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page=d2)
                            await pg.evaluate(JS)
                            res[nm][ch] = await pg.evaluate('([c,s,b])=>__mt.fp(c,s,b)', [ch, 150, ['mag', 'study']])
                            await ctx.close()
                        try: os.remove(os.path.join(H.ROOT, d2))
                        except Exception: pass
                    await b.close()
                for ch in res['new']:
                    a, c = res['new'][ch], res['base'][ch]
                    same = json.dumps(a['out']) == json.dumps(c['out']) and a['end'] == c['end']
                    if not same:
                        di = next((i for i, (x, y) in enumerate(zip(a['out'], c['out'])) if x != y), None)
                        print('   · %s 첫 차이 표본 %s: 새 %s / 옛 %s · 끝 %s / %s' % (ch, di, a['out'][di] if di is not None else '-', c['out'][di] if di is not None else '-', a['end'], c['end']))
                    ok(same and a['mg'] == 1 and not a['ps'].get('mag') and not a['ps'].get('study'), 'G %s 150초 판이 옛 코드와 비트까지 같다 (처치 %s · Lv%s · 배율 %s)' % (ch, a['end'][0], a['end'][1], a['mg']))
                try: os.remove(os.path.join(H.ROOT, bh))
                except Exception: pass
    finally:
        srv.close()
        try: os.remove(p)
        except Exception: pass
    return fails


MUT = [
    ('상자도 끌려옴', "&&it.k!=='chest'&&(it.k!=='chicken'", "&&(it.k!=='chicken'"),
    ('반경 식 K 무시', "const ex=mg>1?MAGV.K*70*(mg-1):0,", "const ex=mg>1?70*(mg-1):0,"),
    ('항상 끌려옴(배율 1 에서도)', "const ex=mg>1?MAGV.K*70*(mg-1):0,", "const ex=mg>=1?MAGV.K*70*(mg-1)+40:0,"),
    ('초월 창 항상 열림', "pa=PTV('mag')>=2&&S.magT>20-MAGV.tpT", "pa=PTV('mag')>=2"),
    ('초월 1단계도 20초', ("pa0=S.magT<=0&&PTV('mag')>=2;", "pa=PTV('mag')>=2&&S.magT>20-MAGV.tpT"), ("pa0=S.magT<=0&&PTV('mag')>=1;", "pa=PTV('mag')>=1&&S.magT>20-MAGV.tpT")),
    ('화면 밖도 끌어옴', "(pa&&Math.abs(dx)<phw&&Math.abs(dy)<phh)", "(pa)"),
    ('보석 통째 끌어오기 부활', "if(d2<mag)g.mag=1;", "if(d2<mag||(S.magT>20-MAGV.tpT&&PTV('mag')>=2))g.mag=1;"),
    ('끌림 속도 2배', "st=Math.min(MAGV.spd*dt,d);", "st=Math.min(MAGV.spd*dt*2,d);"),
    ('20초 시계 안 돌림', "const mg=magMul(),pa0=S.magT<=0&&PTV('mag')>=2;if(pa0)S.magT=20;", "const mg=magMul(),pa0=false;"),
    ('치킨만(폭탄 제외)', "&&it.k!=='chest'&&(it.k!=='chicken'", "&&it.k!=='chest'&&it.k!=='bomb'&&(it.k!=='chicken'"),
    ('치킨 HP 조건 제거', "&&(it.k!=='chicken'||p.hp<=p.mhp*MAGV.chk)", ""),
    ('캐릭터 보너스 무시', "const mg=magMul(),pa0", "const mg=1+.3*pv('mag')+.4*(PTV('mag')?1:0),pa0"),
]


async def main():
    if not MUTANTS:
        fails = await run_suite(SRC)
        print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
        return 1 if fails else 0
    s = open(os.path.join(H.ROOT, SRC), encoding='utf-8').read()
    miss = []
    for i, (nm, a, c) in enumerate(MUT):
        pairs = list(zip(a, c)) if isinstance(a, tuple) else [(a, c)]
        bad = [x for x, _ in pairs if s.count(x) != 1]
        if bad:
            print('변이 %s: 원본에서 줄을 못 찾음(%s)' % (nm, bad[0][:40])); miss.append(nm); continue
        dst = 'survivors_msm_%d.html' % i
        t = s
        for x, y in pairs: t = t.replace(x, y)
        open(os.path.join(H.ROOT, dst), 'w', encoding='utf-8').write(t)
        try:
            f = await run_suite(dst, 'm%d' % i)
        finally:
            try: os.remove(os.path.join(H.ROOT, dst))
            except Exception: pass
        print('== 변이 [%s]: %s' % (nm, '잡았다(빨강 %d건)' % len(f) if f else '못 잡았다 ✗'), flush=True)
        if not f: miss.append(nm)
    print('\n변이 결과: %d개 중 못 잡은 것 %d개 %s' % (len(MUT), len(miss), miss))
    return 1 if miss else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
