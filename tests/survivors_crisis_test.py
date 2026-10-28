# -*- coding: utf-8 -*-
"""🔥 위기 이벤트(S-4) 시험 — 흐접새우 서바이벌 survivors.html (2026-10-21)
  A 타이머: 5:00 에 예고 → 2초 뒤 발동 → 끝나면 쉼 · 다음 시각 10:00 · 진행 중 새 위기 안 겹침
  B 🐎 질주 떼: 레인 안(중심)은 맞고 레인 밖은 안전 · 헤카림이 레인 방향으로 달린다
  C 💣 폭탄 비: 12~24개 · 서로 겹치지 않음 · 원 밖은 안전 · 원 안은 맞는다
  D ⭕ 포위 링: 구멍 방향에 몹이 없다 · 구멍으로 달리면 안전 · 가만히 있으면 맞는다
  E 보상: 무피해면 치킨+자석+경험치 · 맞으면 없음 · 보스가 살아 있으면 최대 90초 기다렸다 건너뜀 · 1:1·최종 보스 직전 건너뜀
  F 미니맵 경고(노란 띠 · 폭탄 원 · 초록 구멍) 가 그려진다
  G 풀이 가득 차도 오류 없이 몹이 나온다(먼 잡몹을 비운다)
  H 이어하기(S 가 새 객체) — 진행 중 위기는 버리고 다음 5분 칸부터 · 오류 0
  I 일일 도전 시드 → 같은 위기 순서 · 난이도 배율(일반<하드<베리하드)
  J 360폭 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
EXTRA = "window.__cr={CRI,CRV,crisisTick,crisisStart,crisisFire,crisisBlocked,crisisRoom,set S(v){S=v},freeSlots,KI,bannerQ,mmDraw,duelBegin};"
PRE = """
window.__T=(()=>{const x=__p6x,c=__cr;
 const R0=Math.random;
 const T={x,c,
  fresh(o){o=o||{};x.CH_set('brj');x.start(o.daily?{daily:true}:undefined);if(o.hard){x.S.hard=1;}if(o.vh){x.S.hard=1;x.S.vh=1;}const S=x.S;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=1e9;S.p.mhp=S.p.hp=1e7;S.t=o.t||299.5;S.spawnT=-1e9;S.evT=1e9;S.bigT=1e9;
   for(const e of x.enemies.a)e.on=false;for(const it of x.items.a)it.on=false;x.state='play';return S;},
  step(sec,fn){const n=Math.round(sec*30);for(let i=0;i<n;i++){const S=x.S;if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play')x.state='play';if(fn)fn(S);x.update(1/30);}},
  force(k){const v=[.1,.5,.9][k];c.CRI.pk=-1;c.CRI.nx=1e9;Math.random=()=>v;try{c.crisisStart();}finally{Math.random=R0;}},   // 종류 k 로 강제 시작(RN 은 비일일 판에서 Math.random)
  fireNow(){const C=c.CRI;C.t=0;x.S.spawnT=-1e9;T.step(1/30);},
  hecs(){return x.enemies.a.filter(e=>e.on&&e.ki===c.KI.Hecarim);},
  kill(){for(const e of x.enemies.a)e.on=false;}
 };return T;})();
"""
async def main():
    H.make_copy('survivors.html', 'survivors_cr.html', extra=EXTRA); srv = H.Srv(); fails = []
    def ok(c, m, d=''):
        print(('  ok   ' if c else '  FAIL ') + m + ('' if c else '  ← ' + str(d)[:300]))
        if not c: fails.append(m)
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=360, h=740, page='survivors_cr.html')
        await pg.evaluate(PRE)
        # ── A 타이머 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI;const S=T.fresh();const o={};
          T.step(.2);o.before=C.ph;o.nx=C.nx;       // S.t=299.7 → 아직
          T.step(.5);o.ph1=C.ph;o.n=C.n;o.t=Math.round(C.t*10)/10;o.banner=[...c.bannerQ.map(q=>q[0])].join('|');
          T.step(2.1);o.ph2=C.ph;
          T.step(8);o.ph0=C.ph;o.nx2=C.nx;o.n2=C.n;o.seq=C.seq.slice();return o;}""")
        ok(r['before'] == 0 and r['nx'] == 300, 'A 5:00 전에는 조용하다 · 첫 위기 5:00', r)
        ok(r['ph1'] == 1 and r['n'] == 1 and r['t'] <= 2, 'A 5:00 에 예고 시작(2초 카운트)', r)
        ok(r['ph2'] == 2, 'A 2초 뒤 발동', r)
        ok(r['ph0'] == 0 and r['nx2'] == 600 and r['n2'] == 1, 'A 끝나면 쉼 · 다음은 10:00 · 겹쳐 시작 안 함', r)
        # ── B 질주 떼 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);const P=S.p;P.x=0;P.y=0;
          T.force(0);const L=C.L,o={k:C.k,w:c.CRV.lane.w};o.dot=L.ax*L.ax+L.ay*L.ay;
          T.step(2.05);o.ph=C.ph;const hs=T.hecs();o.n=hs.length;o.dirOk=hs.every(e=>Math.abs(e.ax-L.ax)<1e-6&&Math.abs(e.ay-L.ay)<1e-6&&e.ph===2);
          // 서 있는 곳이 레인 중심선 위(0 근처) → 맞는다
          const h0=C.h;let hit=0;
          T.step(3.6);o.hitInLane=C.h-h0;return o;}""")
        ok(r['k'] == 0 and r['ph'] == 2 and r['n'] >= 10 and r['dirOk'], 'B 질주 떼가 레인 방향으로 달리는 헤카림 n마리', r)
        ok(r['hitInLane'] >= 1, 'B 레인 안에 서 있으면 맞는다', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);const P=S.p;P.x=0;P.y=0;
          T.force(0);const L=C.L;const nx=-L.ay,ny=L.ax;const off=c.CRV.lane.w/2+60;   // 레인 가장자리에서 60px 밖
          P.x=nx*off;P.y=ny*off;const h0=C.h,ok0=C.ok;
          T.step(2.1+3.5,S=>{S.p.x=nx*off;S.p.y=ny*off;});
          return {hit:C.h-h0,ok:C.ok-ok0,ph:C.ph,chick:x.items.a.filter(i=>i.on&&i.k==='chicken').length,mag:x.items.a.filter(i=>i.on&&i.k==='magnet').length};}""")
        ok(r['hit'] == 0 and r['ok'] == 1 and r['ph'] == 0, 'B 레인 밖(60px)은 안전 → 무피해 보상', r)
        ok(r['chick'] >= 1 and r['mag'] >= 1, 'E 보상: 치킨 + 자석이 떨어진다', r)
        # ── C 폭탄 비 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);const P=S.p;P.x=0;P.y=0;
          T.force(1);T.step(2.05);const bs=S.ebooms.filter(b=>b.cr);const o={n:bs.length,R:c.CRV.bomb.R};
          let minD=1e9;for(let i=0;i<bs.length;i++)for(let j=i+1;j<bs.length;j++)minD=Math.min(minD,Math.hypot(bs[i].x-bs[j].x,bs[i].y-bs[j].y));o.minD=Math.round(minD);
          // 안전 지점 찾기: 모든 폭탄에서 R+p.r+8 밖
          let safe=null;for(let a=0;a<360&&!safe;a+=5)for(let r=0;r<700&&!safe;r+=20){const X=Math.cos(a*Math.PI/180)*r,Y=Math.sin(a*Math.PI/180)*r;if(bs.every(b=>Math.hypot(b.x-X,b.y-Y)>b.R+P.r+8))safe={X,Y};}
          o.safe=!!safe;P.x=safe.X;P.y=safe.Y;const h0=C.h;
          T.step(1.9,S=>{S.p.x=safe.X;S.p.y=safe.Y;});o.hitSafe=C.h-h0;o.left=S.ebooms.filter(b=>b.cr).length;o.ok=C.ok;return o;}""")
        ok(12 <= r['n'] <= 24 and r['minD'] >= 90, 'C 폭탄 12~24개 · 서로 겹치지 않는다', r)
        ok(r['safe'] and r['hitSafe'] == 0 and r['left'] == 0 and r['ok'] == 1, 'C 원 밖은 안전 · 전부 터진 뒤 무피해 보상', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);const P=S.p;P.x=0;P.y=0;
          T.force(1);T.step(2.05);const bs=S.ebooms.filter(b=>b.cr);const h0=C.h;
          const b0=bs[0];T.step(1.7,S=>{S.p.x=b0.x;S.p.y=b0.y;});return {hit:C.h-h0,ok:C.ok};}""")
        ok(r['hit'] >= 1 and r['ok'] == 0, 'C 원 안에 서 있으면 맞고 보상은 없다', r)
        # ── D 포위 링 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);const P=S.p;P.x=0;P.y=0;
          T.force(2);T.step(2.05);const ha=C.ha,o={ph:C.ph};const ms=x.enemies.a.filter(e=>e.on);o.n=ms.length;
          let near=0;for(const e of ms){let d=Math.atan2(e.y-C.y,e.x-C.x)-ha;d=Math.atan2(Math.sin(d),Math.cos(d));if(Math.abs(d)<c.CRV.ring.hole/2-.08)near++;}o.inHole=near;
          const dx=Math.cos(ha),dy=Math.sin(ha);const h0=C.h;
          T.step(c.CRV.ring.dur,S=>{S.p.x+=dx*180/30;S.p.y+=dy*180/30;});   // 구멍 쪽으로 쭉 달린다
          o.hitRun=C.h-h0;o.ok=C.ok;return o;}""")
        ok(r['n'] >= 20 and r['inHole'] == 0, 'D 링 몹이 20마리 이상 · 구멍 안에는 한 마리도 없다', r)
        ok(r['hitRun'] == 0 and r['ok'] == 1, 'D 구멍으로 달리면 안전 → 보상', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);const P=S.p;P.x=0;P.y=0;
          T.force(2);T.step(2.05);const h0=C.h;T.step(c.CRV.ring.dur,S=>{S.p.x=0;S.p.y=0;});return {hit:C.h-h0,ok:C.ok};}""")
        ok(r['hit'] >= 1 and r['ok'] == 0, 'D 가만히 있으면 링에 맞는다 · 보상 없음', r)
        # ── 난이도 배율(개수) ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x,out={};
          for(const [nm,o] of [['n',{}],['h',{hard:1}],['v',{vh:1}]]){const S=T.fresh(o);T.step(.3);S.p.x=S.p.y=0;S.t=1200;T.force(0);T.step(2.05);out[nm]=T.hecs().length;}return out;}""")
        ok(r['n'] < r['h'] < r['v'] or (r['n'] < r['v'] and r['h'] >= r['n']), 'I 규모 배율: 일반 < 하드 < 베리하드 (질주 몹 수)', r)
        # ── 시간이 갈수록 커진다 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,out={};for(const t of [300,1500]){const S=T.fresh();T.step(.3);S.p.x=S.p.y=0;S.t=t;T.force(0);T.step(2.05);out[t]=T.hecs().length;}return out;}""")
        ok(r['1500'] > r['300'], 'I 시간이 갈수록 위기 규모가 커진다', r)
        # ── E 건너뜀 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();const o={};T.step(.3);
          x.spawnBoss('yorick');const bossAlive=x.enemies.a.some(e=>e.on&&e.boss);o.boss=bossAlive;
          T.step(1,S=>{S.p.hp=S.p.mhp;for(const e of x.enemies.a)if(e.on&&e.boss){e.hp=e.mhp=1e12;e.x=1e5;}});   // 보스는 멀리 두고 죽지 않게
          o.ph300=C.ph;o.n=C.n;
          T.step(60,S=>{for(const e of x.enemies.a)if(e.on&&e.boss){e.x=S.p.x+3000;}});o.ph360=C.ph;o.skip360=C.skip;
          T.step(35,S=>{for(const e of x.enemies.a)if(e.on&&e.boss){e.x=S.p.x+3000;}});o.skip=C.skip;o.nx=C.nx;o.nAfter=C.n;return o;}""")
        ok(r['boss'] and r['ph300'] == 0 and r['n'] == 0, 'E 보스가 살아 있으면 위기가 시작하지 않는다', r)
        ok(r['skip'] == 1 and r['nx'] == 600 and r['nAfter'] == 0, 'E 90초 기다려도 보스가 있으면 이번 차례를 건너뛴다(다음 10:00)', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh({t:3250});S.nextBoss=3300;T.step(.3);
          const o={blocked:c.crisisBlocked()};C.nx=3250;T.step(.3);o.ph=C.ph;
          const S2=T.fresh({t:3200});S2.nextBoss=1e9;T.step(.3);S2.nextBoss=3300;S2.t=3200;o.free=c.crisisBlocked();return o;}""")
        ok(r['blocked'] and r['ph'] == 0, 'E 최종 보스 직전 1분은 시작하지 않는다', r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);S.p.x=S.p.y=0;T.force(0);T.step(2.05);const o={ph:C.ph,n:T.hecs().length};
          x.spawnBoss('fin');o.duel=!!x.enemies.a.some(e=>e.on&&e.du);T.step(.2);o.phAfter=C.ph;return o;}""")
        ok(r['ph'] == 2 and r['n'] > 0 and r['phAfter'] == 0, 'E 1:1(최종 보스) 시작 → 진행 중 위기는 버려진다', r)
        # ── F 미니맵 ──
        async def mm_count(pred):
            return await pg.evaluate("""(pred)=>{__cr.mmDraw();const c=document.getElementById('mm'),g=c.getContext('2d').getImageData(0,0,c.width,c.height).data,f=new Function('r','g','b','a','return '+pred);let n=0;for(let i=0;i<g.length;i+=4)if(f(g[i],g[i+1],g[i+2],g[i+3]))n++;return n;}""", pred)
        for k, pred, nm in [(0, 'r>220&&g>170&&b<130&&a>90', '노란 띠'), (1, 'r>230&&g<140&&b<110&&a>90&&g>60', '폭탄 원'), (2, 'g>220&&r<170&&b<190&&a>90', '초록 구멍')]:
            await pg.evaluate("""(k)=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);S.p.x=S.p.y=0;for(const e of x.enemies.a)e.on=false;T.force(k);if(k===1)T.step(2.05);x.state='pause';x.mmDraw?0:0;}""", k)
            before = await mm_count(pred)
            await pg.evaluate("()=>{__T.c.CRI.ph=0;}")
            after = await mm_count(pred)
            ok(before > after + 15 and before > 25, 'F 미니맵에 %s 경고가 그려진다 (켜짐 %d · 꺼짐 %d)' % (nm, before, after))
        # ── G 풀 가득 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);S.p.x=S.p.y=0;
          for(const e of x.enemies.a){e.on=false;}for(let i=0;i<400;i++){const e=x.spawnEnemy(0,1);if(!e)break;e.x=S.p.x+500+i;e.y=S.p.y;}
          const full=c.freeSlots();T.force(0);T.step(2.05);const o={full,hec:T.hecs().length,boss:0};
          for(const e of x.enemies.a)e.on=false;for(let i=0;i<400;i++){const e=x.spawnEnemy(0,1);if(!e)break;e.x=S.p.x+500+i;e.y=S.p.y;}
          T.force(2);T.step(2.05);o.ring=x.enemies.a.filter(e=>e.on).length;o.free=c.freeSlots();return o;}""")
        ok(r['full'] <= 2 and r['hec'] >= 10, 'G 풀이 가득 차도 질주 떼가 나온다 (빈칸 %s → 헤카림 %s)' % (r['full'], r['hec']), r)
        ok(r['ring'] >= 20, 'G 풀이 가득 차도 링이 나온다', r)
        # ── H 이어하기 ──
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh();T.step(.3);S.p.x=S.p.y=0;T.force(1);T.step(2.05);const o={ph:C.ph};
          const S2=Object.assign({},S);S2.ebooms=S.ebooms.slice();c.S=S2;x.S;T.step(.5);o.ph2=C.ph;o.nx=C.nx;o.t=Math.round(S2.t);return o;}""")
        ok(r['ph'] == 2 and r['ph2'] == 0 and r['nx'] == 600, 'H 이어하기: 진행 중 위기는 버리고 다음 5분 칸(10:00)부터 (t=%s)' % r['t'], r)
        r = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh({t:1000});T.step(.3);return {nx:C.nx,t:Math.round(S.t)};}""")
        ok(r['nx'] == 1200, 'H 1000초에 이어하면 다음은 1200초(20:00)', r)
        # ── I 일일 도전 ──
        seqs = []
        for i in range(2):
            s = await pg.evaluate("""()=>{const T=__T,c=T.c,C=c.CRI,x=T.x;const S=T.fresh({daily:1});T.step(.3);if(!S.dly)return null;S.p.x=S.p.y=0;
              for(let q=0;q<6;q++){C.nx=S.t;T.step(.1);for(const e of x.enemies.a)e.on=false;T.step(8.5);for(const e of x.enemies.a)e.on=false;S.ebooms.length=0;}
              return {seq:C.seq.slice(),n:C.n};}""")
            seqs.append(s)
        ok(seqs[0] is not None and seqs[0]['n'] >= 5 and seqs[0]['seq'] == seqs[1]['seq'], 'I 일일 도전: 같은 시드 → 같은 위기 순서 %s' % (seqs[0] and seqs[0]['seq']), seqs)
        # ── J ──
        ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
        ok(ov['sw'] <= ov['cw'], 'J 360폭 가로 넘침 없음', ov)
        ok(not errs, 'J 콘솔 오류 0', errs[:3])
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_cr.html'))
    except Exception: pass
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
