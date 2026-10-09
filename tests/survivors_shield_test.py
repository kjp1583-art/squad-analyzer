# -*- coding: utf-8 -*-
"""🛡 명상 방어막 주기형 개편 시험 (2026-10-09 사장님 지시 "정지하는 조건자체를 제거하고, 몇초당한번 얻는 방어막으로 변경").  사용: python3 tests/survivors_shield_test.py
  움직이든 서 있든 N초(Lv1 40 · Lv2 30 · Lv3 20)마다 방어막 1겹 — 방어막이 있는 동안은 시간이 안 쌓이고, 막은 뒤부터 다시 센다.
  막기 공통 쿨 1.2초(냄비뚜껑 포함)와 막은 뒤 무적 0.15초는 그대로(2026-10-03 「가만히 서 있어도 무적이 돼 게임이 깨진다」 — 막기가 이어 붙으면 안 된다).
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅(__p6x)을 꽂는다. 종료코드 0 = 전부 통과."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

# 공통 JS 도구 — relTick 을 직접 부른다(update 전체를 돌리면 적이 방어막을 가져가 시간 측정이 흐려진다)
LIB = r"""
window.__fresh=function(lv,hp){const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.p.hp=S.p.mhp=1e9;S.rel={};if(lv)S.rel.still=lv;S.stillT=0;S.shield=0;return S;};
// 방어막이 생긴 시각들 — mv: true=계속 움직임 / false=계속 서 있음 / 'mix'=번갈아
window.__times=function(lv,mv,secs,dt,hit){const x=__p6x,S=__fresh(lv),p=S.p,out=[];let t=0,prev=0;const n=Math.round(secs/dt);
  for(let i=0;i<n;i++){t+=dt;S.t+=dt;p.moving=mv==='mix'?(Math.floor(t/3)%2===0):mv;p.inv=Math.max(0,p.inv-dt);
    x.relTick(dt);
    if(S.shield&&!prev){out.push(+t.toFixed(3));if(hit){S.lastBlock=-9;p.inv=0;x.hitP(1);}}   // hit=true 면 생기는 즉시 맞아서 소모(막은 뒤부터 다시 센다)
    prev=S.shield;if(S.shield>1)out.push('LAYERS');}
  return out;};
"""

async def main():
    H.make_copy(extra="Object.defineProperties(window.__p6x,{buildHtml:{get(){return buildHtml}}});"); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate(LIB)
        N = [40, 30, 20]

        # ① 움직이는 중에도 N초 뒤 방어막 (레벨별) — 첫 방어막은 정확히 N초(한 프레임 오차)
        for dt in (1/30, 0.05, 1/60):
            for lv in (1, 2, 3):
                r = await pg.evaluate(f"__times({lv},true,{N[lv-1]+3},{dt},false)")
                check(f'① 계속 움직이면서도 Lv{lv} 는 {N[lv-1]}초 뒤 첫 방어막 (dt={dt:.4f})', len(r) == 1 and N[lv-1]-1e-6 <= r[0] <= N[lv-1]+dt+1e-3, r)

        # ② 서 있어도 똑같다 / 번갈아 움직여도 똑같다
        for lv in (1, 2, 3):
            a = await pg.evaluate(f"__times({lv},true,{N[lv-1]+3},0.05,false)")
            s = await pg.evaluate(f"__times({lv},false,{N[lv-1]+3},0.05,false)")
            m = await pg.evaluate(f"__times({lv},'mix',{N[lv-1]+3},0.05,false)")
            check(f'② Lv{lv}: 움직임 = 정지 = 번갈아 (같은 시각)', a == s == m and len(a) == 1, (a, s, m))
        # 예전 규칙(서 있으면 6/5/4초)대로 서 있어도 더 빨리 차지 않는다
        r = await pg.evaluate("__times(3,false,19,0.05,false)")
        check('② 서 있어도 Lv3 는 19초까지 방어막 없음(옛 4초 아님)', r == [], r)

        # ③ 방어막이 있는 동안은 시간이 안 쌓임 · 막은 뒤부터 다시 N초
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(3),p=S.p;const dt=.05;let t=0;
          for(let i=0;i<Math.round(20.2/dt);i++){t+=dt;S.t+=dt;p.moving=false;x.relTick(dt);}
          const has=S.shield;
          let maxT=0;for(let i=0;i<Math.round(60/dt);i++){t+=dt;S.t+=dt;p.moving=i%2===0;x.relTick(dt);maxT=Math.max(maxT,S.stillT);}   // 60초 들고 있는다
          const held={shield:S.shield,stillT:S.stillT,maxT};
          const tBlock=S.t;p.inv=0;S.lastBlock=-9;const hit=x.hitP(5);   // 맞아서 막는다
          const after={hit,shield:S.shield,stillT:S.stillT,inv:p.inv};
          let again=null;for(let i=1;i<=Math.round(30/dt);i++){S.t+=dt;p.inv=Math.max(0,p.inv-dt);x.relTick(dt);if(S.shield&&again===null)again=+(S.t-tBlock).toFixed(3);}
          return {has,held,after,again};}""")
        check('③ 20초에 방어막 생김', r['has'] == 1, r)
        check('③ 방어막을 60초 들고 있어도 쌓이는 시간 0 (한 겹 그대로)', r['held'] == {'shield': 1, 'stillT': 0, 'maxT': 0}, r['held'])
        check('③ 막은 직후 무적은 0.15초 이하(2026-10-03 지시 값 고정 — 0.6 으로 키우면 실패)', r['after']['inv'] <= 0.15 + 1e-9 and r['after']['inv'] > 0, r['after'])
        check('③ 막으면 맞은 피해 0(false) · 방어막 소모', r['after']['hit'] is False and r['after']['shield'] == 0 and r['after']['stillT'] == 0, r['after'])
        check('③ 막은 뒤부터 다시 20초(막은 직후 곧바로 다시 차지 않음)', r['again'] is not None and 19.9 <= r['again'] <= 20.1, r['again'])
        # 맞는 즉시 소모하는 연속 반복: 간격이 정확히 N
        for lv in (1, 2, 3):
            r = await pg.evaluate(f"__times({lv},'mix',{N[lv-1]*4+2},0.05,true)")
            gaps = [round(r[i+1]-r[i], 2) for i in range(len(r)-1)]
            check(f'③ Lv{lv}: 막고 나면 매번 {N[lv-1]}초 간격', len(r) == 4 and all(abs(g-N[lv-1]) < .11 for g in gaps), (r, gaps))

        # ④ 최대 1겹
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(3),p=S.p;let mx=0;for(let i=0;i<4000;i++){S.t+=.05;x.relTick(.05);mx=Math.max(mx,S.shield);}
          S.shield=1;S.stillT=0;const o=x.CHARS;return {mx,sh:S.shield};}""")
        check('④ 200초 지나도 방어막은 최대 1겹', r['mx'] == 1 and r['sh'] == 1, r)
        # 카드 「일회용 방어막」 이 이미 방어막을 줬을 때(=이미 1겹): 쌓인 시간은 0 으로 고정, 막은 뒤 N초
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(3),p=S.p;for(let i=0;i<200;i++){S.t+=.05;x.relTick(.05);}   // 10초 쌓임
          const before=S.stillT;S.shield=1;S.t+=.05;x.relTick(.05);const mid=S.stillT;
          p.inv=0;S.lastBlock=-9;x.hitP(3);let got=null;const t0=S.t;for(let i=0;i<Math.round(25/.05);i++){S.t+=.05;p.inv=Math.max(0,p.inv-.05);x.relTick(.05);if(S.shield&&got===null)got=+(S.t-t0).toFixed(2);}
          return {before:+before.toFixed(2),mid,got};}""")
        check('④ 카드 방어막을 받으면 쌓인 시간 0 · 막은 뒤 다시 20초', r['mid'] == 0 and r['got'] is not None and 19.9 <= r['got'] <= 20.1, r)

        # ⑤ 막기 공통 쿨 1.2초 — 방어막 + 냄비뚜껑 동시, 매 프레임 때리는 최악 장면 (코드 경로: relTick → hitP)
        for lv, lid in ((3, False), (3, True), (1, True)):
            r = await pg.evaluate("""([lv,lid])=>{const x=__p6x,S=__fresh(lv),p=S.p,X=S.x2;const dt=1/60;
              if(lid){S.w.lid=1;X.ln=8;for(let i=0;i<8;i++)X.lr[i]=0;X.lreg=.6;}
              const blocks=[],relic=[];let lastB=S.lastBlock,hits=0;
              for(let i=0;i<Math.round(600/dt);i++){S.t+=dt;p.moving=true;if(p.inv>0)p.inv=Math.max(0,p.inv-dt);
                if(lid)for(let k=0;k<8;k++)if(X.lr[k]>0)X.lr[k]-=dt;
                x.relTick(dt);p.hp=p.mhp;const sh0=S.shield,hp0=p.hp;const r=x.hitP(1);
                if(S.lastBlock!==lastB){lastB=S.lastBlock;blocks.push(S.t);if(sh0&&!S.shield)relic.push(S.t);}else if(r===false&&p.inv<=0){}
                if(p.hp<hp0)hits++;}
              const gap=a=>{let m=1e9;for(let i=1;i<a.length;i++)m=Math.min(m,a[i]-a[i-1]);return m;};
              return {nb:blocks.length,nr:relic.length,gapAll:gap(blocks),gapRelic:gap(relic),hits};}""", [lv, lid])
            n = N[lv-1]
            check(f'⑤ Lv{lv}{" + 냄비뚜껑 8장" if lid else ""}: 600초 연타에도 막기 간격 ≥ 1.2초', r['gapAll'] >= 1.2 - 1e-9 and r['nb'] > 0, r)
            check(f'⑤ Lv{lv}{" + 뚜껑" if lid else ""}: 유물 막기끼리 간격 ≥ {n}초 · 600초 동안 {n}초마다 약 {int(600//(n))}번 이하', r['nr'] > 0 and r['gapRelic'] >= n - 1e-9 and r['nr'] <= 600 // n, r)

        # ⑥ 레벨이 오르면 N 이 즉시 짧아짐 — 쌓인 시간이 새 N 을 넘으면 그 프레임에 1장, 그 뒤는 새 N 간격(이어 붙지 않음)
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(1),p=S.p;const dt=.05;let t=0;
          for(let i=0;i<Math.round(31/dt);i++){t+=dt;S.t+=dt;x.relTick(dt);}
          const pre={sh:S.shield,st:+S.stillT.toFixed(2)};     // Lv1 31초: 40초 전이라 아직 없음
          S.rel.still=2;S.t+=dt;x.relTick(dt);const up={sh:S.shield,st:S.stillT};   // Lv2 (N=30) 로 올림 → 이미 넘었으니 즉시 1장
          p.inv=0;S.lastBlock=-9;x.hitP(1);const tb=S.t;let nx=null;
          S.rel.still=3;for(let i=0;i<Math.round(40/dt);i++){S.t+=dt;p.inv=Math.max(0,p.inv-dt);x.relTick(dt);if(S.shield&&nx===null)nx=+(S.t-tb).toFixed(2);}
          return {pre,up,nx};}""")
        check('⑥ Lv1 31초: 아직 방어막 없음', r['pre']['sh'] == 0 and r['pre']['st'] >= 30.9, r['pre'])
        check('⑥ Lv2 로 오르면 쌓인 시간(31초)이 새 N(30초)을 넘어 즉시 1장만', r['up'] == {'sh': 1, 'st': 0}, r['up'])
        check('⑥ 막은 뒤 Lv3(N=20) 로 다시 20초', r['nx'] is not None and 19.9 <= r['nx'] <= 20.1, r['nx'])
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(1),p=S.p;const dt=.05;   // 연속 레벨업이 막기를 이어 붙이지 않음 (Lv1→2→3 을 10·11초에 올림, 그 사이 맞는 즉시 소모)
          const bl=[];let lastB=S.lastBlock;
          for(let i=0;i<Math.round(200/dt);i++){S.t+=dt;if(Math.abs(S.t-10)<dt/2)S.rel.still=2;if(Math.abs(S.t-11)<dt/2)S.rel.still=3;
            if(p.inv>0)p.inv=Math.max(0,p.inv-dt);x.relTick(dt);p.hp=p.mhp;x.hitP(1);if(S.lastBlock!==lastB){lastB=S.lastBlock;bl.push(+S.t.toFixed(2));}}
          const g=[];for(let i=1;i<bl.length;i++)g.push(+(bl[i]-bl[i-1]).toFixed(2));return {bl,g};}""")
        check('⑥ 연속 레벨업(10초·11초)에도 첫 방어막은 20초 · 이후 간격 ≥ 20초', r['bl'] and 19.9 <= r['bl'][0] <= 20.2 and all(g >= 19.9 for g in r['g']), r)
        # 위험한 경우: 쌓인 시간이 새 N 보다 훨씬 큰 채 레벨 점프
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(1),p=S.p;S.stillT=39.9;S.rel.still=3;S.t+=.05;x.relTick(.05);const a=S.shield;
          p.inv=0;S.lastBlock=-9;x.hitP(1);S.t+=.05;x.relTick(.05);return {a,b:S.shield,st:S.stillT};}""")
        check('⑥ 쌓인 시간 39.9초에서 Lv3 로 점프 → 1장 즉시, 막은 직후엔 다시 안 생김', r['a'] == 1 and r['b'] == 0 and r['st'] < 1, r)

        # ⑦ 유물이 없으면 아무 일도 안 함
        for mv in (True, False):
            r = await pg.evaluate(f"""()=>{{const x=__p6x,S=__fresh(0),p=S.p;for(let i=0;i<2400;i++){{S.t+=.05;p.moving={str(mv).lower()};x.relTick(.05);}}return {{sh:S.shield,st:S.stillT}};}}""")
            check(f'⑦ 유물 없으면 120초 지나도 방어막 0 · 시간 0 (moving={mv})', r == {'sh': 0, 'st': 0}, r)

        # update() 전체 경로 — 키를 누르고 있어도 / 놓고 있어도 N초에 생긴다 (적의 공격은 p.inv 로 막아 방어막을 안 뺏기게)
        for keys in ('move', 'still'):
            r = await pg.evaluate("""(keys)=>{const x=__p6x,S=__fresh(3),p=S.p;const dt=1/30;let first=null;
              for(let i=0;i<Math.round(24/dt);i++){p.inv=99;p.hp=p.mhp;x.keys=keys==='move'?{KeyD:true}:{};
                if(x.state==='lvup'){x.pick(x.CUR[0]);S.rel.still=3;continue;} if(x.state!=='play'){x.resume();continue;}
                x.update(dt);if(S.shield&&first===null)first=+S.t.toFixed(2);}
              return {first,t:+S.t.toFixed(2)};}""", keys)
            check(f'⑦ update 전체 경로({"키 누른 채" if keys=="move" else "키 뗀 채"}): 20초에 방어막', r['first'] is not None and 19.9 <= r['first'] <= 20.2, r)

        # ⑨ 새 판 시작 시 초기화 — 이전 판의 쌓인 시간·방어막·마지막 막기가 새 판으로 새지 않음
        r = await pg.evaluate("""()=>{const x=__p6x,S0=__fresh(3);S0.stillT=17;S0.shield=1;S0.lastBlock=123;S0.rel.still=3;
          x.start();const S=x.S;const init={st:S.stillT,sh:S.shield,lb:S.lastBlock,still:S.rel.still};
          for(let i=0;i<2400;i++){S.t+=.05;x.relTick(.05);}   // 유물이 없는 새 판은 계속 아무 일도 없음
          return {init,after:{sh:S.shield,st:S.stillT}};}""")
        check('⑨ 새 판: stillT 0 · 방어막 0 · lastBlock 없음 · 유물 없음', r['init']['st'] == 0 and r['init']['sh'] == 0 and not r['init']['lb'] and r['init']['still'] is None, r['init'])
        check('⑨ 새 판(유물 없음)은 120초 지나도 방어막 안 생김', r['after'] == {'sh': 0, 'st': 0}, r['after'])
        r = await pg.evaluate("""()=>{const x=__p6x;const S=__fresh(3);for(let i=0;i<300;i++){S.t+=.05;x.relTick(.05);}   // 15초 쌓음
          x.start();const S2=x.S;S2.rel.still=3;let first=null;for(let i=1;i<=500;i++){S2.t+=.05;x.relTick(.05);if(S2.shield&&first===null)first=+(i*.05).toFixed(2);}return first;}""")
        check('⑨ 이전 판에서 15초 쌓다 새 판 → 새 판 유물은 처음부터 20초', r is not None and 19.9 <= r <= 20.1, r)

        # ⑪ 카드 설명 문구
        r = await pg.evaluate("""()=>{const x=__p6x,d=x.REL.still;return {nm:d.nm,ic:d.ic,t:[1,2,3].map(l=>d.ds(l))};}""")
        want = [f'방어막이 없으면 {n}초 뒤 저절로 1겹 생겨 다음 한 방을 막는다(최대 1겹 · 막은 뒤부터 다시 세요 · 막기는 1.2초에 한 번)' for n in (40, 30, 20)]
        check('⑪ 카드 이름 그대로 「명상 방어막」', r['nm'] == '명상 방어막', r['nm'])
        check('⑪ 카드 설명: Lv1 40초 · Lv2 30초 · Lv3 20초 · 「가만히」 없음', r['t'] == want and not any('가만히' in t for t in r['t']), r['t'])
        # 실제 카드 만들기 경로에서도 같은 문구가 나옴
        r = await pg.evaluate("""()=>{const x=__p6x;const S=__fresh(0);const out={};for(const l of [1,2,3]){try{const c=x.cardOf?x.cardOf('rel:still'):null;out.has=!!c;break;}catch(e){out.err=String(e);break;}}return out;}""")
        print('   (참고) cardOf 호출', r)

        # ⑫ 보이는 표시 — 막았을 때 글자에 다음까지 걸리는 초 · 일시정지 유물 줄 · 캐릭터 둘레 고리
        r = await pg.evaluate("""()=>{const x=__p6x,out={};for(const l of [1,2,3]){const S=__fresh(l);S.shield=1;S.p.inv=0;S.lastBlock=-9;S.t=100;x.hitP(5);const t=x.texts.a.filter(q=>q.on&&q.s&&q.s.indexOf('막았다')>=0).pop();out['t'+l]=t?t.s:null;}
          const S=__fresh(2);S.shield=1;const h1=x.buildHtml();S.shield=0;S.stillT=12.3;const h2=x.buildHtml();S.rel={};const h3=x.buildHtml();
          return {...out,has:h1.includes('명상 방어막 Lv2 · 지금 있음'),wait:h2.includes('명상 방어막 Lv2 · 다음까지 약 18초'),none:!h3.includes('다음까지')&&!h3.includes('지금 있음')};}""")
        check('⑫ 막았을 때 글자: 「🛡 막았다! (N초 뒤 다시 생겨요)」 Lv1 40 · Lv2 30 · Lv3 20', r['t1'] == '🛡 막았다! (40초 뒤 다시 생겨요)' and r['t2'] == '🛡 막았다! (30초 뒤 다시 생겨요)' and r['t3'] == '🛡 막았다! (20초 뒤 다시 생겨요)', r)
        check('⑫ 일시정지 유물 줄: 있으면 「지금 있음」 · 없으면 「다음까지 약 N초」 · 유물 없으면 안 붙음', r['has'] and r['wait'] and r['none'], r)
        r = await pg.evaluate("""()=>{const x=__p6x,S=__fresh(3);S.p.hp=S.p.mhp=1e9;const o=CanvasRenderingContext2D.prototype.stroke;let n=0;
          CanvasRenderingContext2D.prototype.stroke=function(){if(/^rgba\\(159, ?208, ?255/.test(this.strokeStyle))n++;return o.apply(this,arguments);};
          const cnt=(sh)=>{S.shield=sh;n=0;for(let i=0;i<5;i++)x.draw();return n;};
          const on=cnt(1),off=cnt(0);CanvasRenderingContext2D.prototype.stroke=o;return {on,off};}""")
        check('⑫ 방어막을 들고 있을 때만 캐릭터 둘레 고리를 그린다', r['on'] > 0 and r['off'] == 0, r)

        # ⑩ 오늘의 도전 난수열 불변 — 유물 효과는 Math.random 도 RN(daily) 도 부르지 않는다
        r = await pg.evaluate("""()=>{const x=__p6x;x.start({daily:true});const S=x.S;S.p.hp=S.p.mhp=1e9;S.rel={still:3};S.stillT=0;S.shield=0;
          const rq0=JSON.stringify(S.dly.rq);let calls=0;const mr=Math.random;Math.random=function(){calls++;return mr();};
          try{for(let i=0;i<4000;i++){S.t+=.05;S.p.moving=i%3===0;x.relTick(.05);if(S.shield&&i%100===99){S.lastBlock=-9;S.p.inv=0;x.hitP(1);}}}finally{Math.random=mr;}
          return {calls,same:rq0===JSON.stringify(S.dly.rq),rq0};}""")
        check('⑩ 오늘의 도전: 방어막 200초 동안 Math.random 호출 0회 · 일일 난수 상태(rq) 불변', r['calls'] == 0 and r['same'], r)
        # 같은 날 두 판: 유물 있음 vs 없음 — 같은 난수 흐름이면 카드 뽑기 난수열이 같아야 한다(공정성)
        r = await pg.evaluate("""()=>{const x=__p6x;const run=(still)=>{x.start({daily:true});const S=x.S;S.rel=still?{still:3}:{};S.p.hp=S.p.mhp=1e9;
            const mr=Math.random;let s=12345;Math.random=function(){s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
            try{for(let i=0;i<1800;i++){S.t+=1/30;S.p.moving=false;S.p.inv=99;x.relTick(1/30);}}finally{Math.random=mr;}
            return [x.RN('card'),x.RN('card'),x.RN('ev'),x.RN('prop'),JSON.stringify(S.dly.rq)];};
          const a=run(false),b=run(true);return {a,b,eq:JSON.stringify(a)===JSON.stringify(b)};}""")
        check('⑩ 같은 날 같은 시드: 유물 있는 판과 없는 판의 난수열(카드·이벤트·소품)이 같음', r['eq'], r)
        check('⑩ 일반 판 시드 없음(S.dly null)에서도 relTick 이 오류 없음', await pg.evaluate("()=>{const x=__p6x;x.start();const S=x.S;S.rel={still:2};for(let i=0;i<900;i++){S.t+=.05;x.relTick(.05);}return S.shield===1}"))
        check('콘솔/페이지 오류 없음(앞 시험 구간)', not errs, errs[:3])
        await ctx.close()

        # ⑧ 이어하기 저장·복원 후에도 타이머 일관 (survivors_resume 와 같은 방식: 같은 페이지에서 저장 → 제목 화면 상태로 만들어 복구)
        H.make_copy(dst='survivors_x.html', extra="window.__RS={RES,get S(){return S},get state(){return state},set state(v){state=v},pauseGame,resume};")
        ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate(LIB)
        r = await pg.evaluate("""()=>{const x=__p6x,R=__RS,S=__fresh(3),p=S.p;const dt=.05;
          for(let i=0;i<Math.round(12/dt);i++){S.t+=dt;p.moving=i%2===0;x.relTick(dt);}   // 12초 쌓음
          const st0=S.stillT,sh0=S.shield,lb0=S.lastBlock;
          if(R.state==='play')R.pauseGame();let saved=null,err=null;try{saved=R.RES.save('shield-test');}catch(e){err=String(e);}
          const text=localStorage.getItem(R.RES.KEY);
          if(!text)return {err:err||'no-save',saved};
          R.state='title';const ok=R.RES.restore(text);const S2=R.S;
          const back={ok,st:S2.stillT,sh:S2.shield,still:S2.rel.still,lb:S2.lastBlock};
          if(R.state!=='play'&&R.state!=='pause')back.state=R.state;
          let first=null;const t0=S2.stillT;for(let i=1;i<=Math.round(15/dt);i++){S2.t+=dt;x.relTick(dt);if(S2.shield&&first===null)first=+(i*dt).toFixed(2);}
          return {st0:+st0.toFixed(3),sh0,back,first,t0:+t0.toFixed(3)};}""")
        print('   (참고) 이어하기', r)
        ok = ('err' not in r) and r['back']['ok'] and abs(r['back']['st'] - r['st0']) < 1e-6 and r['back']['sh'] == 0 and r['back']['still'] == 3
        check('⑧ 저장→복원: 쌓인 시간(12초) · 유물 레벨 · 방어막 없음이 그대로', ok, r)
        check('⑧ 복원 뒤 남은 8초 뒤에 방어막(총 20초)', ok and r['first'] is not None and abs(r['first'] - (20 - r['st0'])) < .11, r)
        r = await pg.evaluate("""()=>{const x=__p6x,R=__RS,S=__fresh(3),p=S.p;const dt=.05;      // 방어막을 든 채 저장 → 복원 후에도 든 채, 쌓인 시간 0
          for(let i=0;i<Math.round(21/dt);i++){S.t+=dt;x.relTick(dt);}
          if(R.state==='play')R.pauseGame();R.RES.save('shield-held');const text=localStorage.getItem(R.RES.KEY);R.state='title';const ok=R.RES.restore(text);const S2=R.S;
          const held={ok,sh:S2.shield,st:S2.stillT};for(let i=0;i<400;i++){S2.t+=dt;x.relTick(dt);}held.st2=S2.stillT;held.sh2=S2.shield;return held;}""")
        check('⑧ 방어막을 든 채 저장→복원: 방어막 1 · 쌓인 시간 0 유지', r['ok'] and r['sh'] == 1 and r['st'] == 0 and r['sh2'] == 1 and r['st2'] == 0, r)
        check('콘솔/페이지 오류 없음(이어하기 구간)', not errs, errs[:3])
        await b.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except OSError: pass
    print('\n실패 %d건' % len(FAILS), FAILS if FAILS else '')
    return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
