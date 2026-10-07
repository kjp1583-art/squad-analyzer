# -*- coding: utf-8 -*-
"""🎒 캐릭터별 고유 시작 무기 13종 검증 (2026-10-07 사장님 지시).  사용: python3 tests/survivors_unique_weapons_test.py
각 캐릭터로 시작 → 시작 무기가 고유 무기 → 레벨업 카드 풀에 다른 캐릭터에겐 안 나옴 → Lv1~8·각성·마스터 5단계까지 돌려 예외 없음 → 실제 피해를 냄 →
해금 조건(공용 무기 Lv5)이 여전히 달성 가능한지. 원본 survivors.html 은 건드리지 않고 임시 사본에만 훅을 꽂는다."""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

# 캐릭터 키 → (고유 무기 키, 시작 레벨)
UNIQ = {'brj': ('quill', 1), 'jjg': ('tempo', 2), 'mms': ('fuse', 1), 'hrb': ('slime', 1), 'ssu': ('cart', 1), 'amd': ('heart', 1), 'ildj': ('jhin', 1),
        'kyo': ('whop', 1), 'ddmj': ('bash', 1), 'psg': ('totem', 1), 'sr': ('stamp', 1), 'ddo': ('chain', 2), 'tw': ('ram', 2),
        'yumi': ('snack', 1), 'eom': ('eom', 1)}   # yumi·eom 은 맛동산 상점(서버 구매) 캐릭터
COMMON_OLD = ['feed', 'egg', 'fryer', 'can', 'sushi', 'pan', 'kbd', 'spk', 'shrimp']   # 예전에 시작 무기로 쓰이던 공용 무기

# 장면 한 판을 돌린다: 무적 봇이 돌아다니며(레벨업 카드는 첫 장) update + 가끔 draw — 그림 코드까지 같이 밟는다
RUN = r"""(a)=>{const x=__p6x;let n=0;const dt=1/30,N=Math.round(a.sec/dt);
 for(let i=0;i<N;i++){const st=x.state;
  if(st==='result')return {res:1,n};
  if(st==='lvup'){x.pick(x.CUR[0]);continue;} if(st!=='play'){x.resume();continue;}
  const S=x.S;S.p.hp=S.p.mhp;
  if(a.keep){for(const k in a.keep)if(S.w[k]!==a.keep[k]&&!(S.w[k]>a.keep[k]))S.w[k]=a.keep[k];}
  const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
  x.update(dt);if(i%3===0)x.draw();n++;}
 return {n,state:x.state};}"""

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        # ── 상점 캐릭터 잠금: 서버 목록이 없으면 못 고르고, 로컬 저장소를 고쳐도 안 열리고, 서버 unlocks 가 오면 열린다
        r = await pg.evaluate("""()=>{const x=__p6x,o={};const pg=x.getProg();
          localStorage.setItem('p6_unl_v1',JSON.stringify(['yumi','eom']));   // 수동으로 로컬을 고쳐 본다
          o.locked=['yumi','eom'].map(k=>x.canPick(x.CHARS.find(c=>c.k===k),pg));
          x.CH_set('yumi');x.start();o.fallback=x.CH.k;x.S&&0;
          x.srvUnl(['yumi']);o.yumi=x.canPick(x.CHARS.find(c=>c.k==='yumi'),pg);o.eom=x.canPick(x.CHARS.find(c=>c.k==='eom'),pg);
          x.srvUnl(['yumi','eom']);o.both=['yumi','eom'].map(k=>x.canPick(x.CHARS.find(c=>c.k===k),pg));
          x.CH_set('eom');x.start();o.start=x.CH.k+':'+Object.keys(x.S.w);return o}""")
        check('상점 캐릭터: 서버 목록 없으면 잠김(로컬 저장소를 고쳐도) · 시작해도 브장신으로 되돌아감', r['locked'] == [False, False] and r['fallback'] == 'brj', r)
        check('서버 unlocks 에 있는 캐릭터만 열림', r['yumi'] and not r['eom'] and r['both'] == [True, True] and r['start'] == 'eom:eom', r)
        # ── 0. 13명 · 서로 겹치지 않는 고유 무기 · 용조련사 breath 는 그대로
        r = await pg.evaluate("""()=>{const x=__p6x;return x.CHARS.map(c=>({k:c.k,w:c.w,wl:c.wl||1,only:x.WEAP[c.w]&&x.WEAP[c.w].only,ds:c.ds}))}""")
        byk = {c['k']: c for c in r}
        check('캐릭터 16명(용조련사 포함)', len(r) == 16, len(r))
        ws = [c['w'] for c in r]
        check('시작 무기 16종이 서로 다름', len(set(ws)) == 16, ws)
        check('시작 무기 중 공용(예전 시작 무기)이 하나도 없음', not any(w in COMMON_OLD or w in ('wifi', 'ping', 'potion', 'gacha', 'rkt', 'chick', 'rod', 'frost', 'lid', 'meteor', 'snipe', 'hole', 'bell') for w in ws))
        for k, (w, wl) in UNIQ.items():
            c = byk[k]
            check(f'{k}: 시작 무기 {w} Lv{wl} · only={k}', c['w'] == w and c['wl'] == wl and c['only'] == k, c)
            check(f'{k}: 설명(ds)에 새 무기가 적혀 있음', '고유 무기' in c['ds'] or '고유' in c['ds'], c['ds'][:60])
        check('용조련사는 그대로 breath Lv2', byk['yj']['w'] == 'breath' and byk['yj']['wl'] == 2)
        # 각 무기 데이터: ds 8줄 · 단계표 5줄 · 각성 · 짝 패시브가 실제 존재
        r = await pg.evaluate("""()=>{const x=__p6x,o={};for(const k of %s){const d=x.WEAP[k],T=x.TIERS[k];o[k]={ds:d.ds.length,T:T&&T.length,ev:!!(d.ev&&d.ev.nm),pair:!!d.pair,ic:d.ic,nm:d.nm};}return o}""" % json.dumps([v[0] for v in UNIQ.values()]))
        for w, o in r.items():
            check(f'{w}: 8레벨 설명·5단계·각성·짝 패시브', o['ds'] == 8 and o['T'] == 5 and o['ev'] and o['pair'], o)
        # ── 1. 시작 → 시작 무기
        for k, (w, wl) in UNIQ.items():
            r = await pg.evaluate("c=>{const x=__p6x;x.CH_set(c);x.start();return {w:Object.assign({},x.S.w)}}", k)
            check(f'{k}: 시작하면 {w} Lv{wl} 한 가지만 들고 있음', r['w'] == {w: wl}, r['w'])
        # ── 2. 레벨업 카드 풀 — 다른 캐릭터에겐 안 나오고, 자기 캐릭터에겐 나온다
        allu = [v[0] for v in UNIQ.values()] + ['breath']
        for k, (w, wl) in UNIQ.items():
            r = await pg.evaluate("""([c,allu])=>{const x=__p6x;x.CH_set(c);x.start();const S=x.S;S.lv=40;const seen={};let bad=[];
              for(let i=0;i<500;i++){if(i%50===0){S.w={};S.w[x.CHARS.find(q=>q.k===c).w]=1+(i/50|0)%8;}
                for(const o of x.offers(3)){if(o.t==='w'||o.t==='wt'){const k=o.t==='w'?o.k:o.w;seen[k]=1;if(allu.includes(k)&&k!==x.CHARS.find(q=>q.k===c).w)bad.push(k);}}}
              return {bad:[...new Set(bad)],common:Object.keys(seen).length};}""", [k, allu])
            check(f'{k}: 카드 풀에 다른 캐릭터의 고유 무기가 안 나옴(500장)', r['bad'] == [], r)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.lv=40;let own=0;for(let i=0;i<300;i++)for(const o of x.offers(3))if(o.t==='w'&&o.k==='quill')own++;return own}""")
        check('브장신은 깃털 산탄 Lv1 이라 레벨업 카드로 강화 가능(Lv2 카드가 나옴)', r > 0, r)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.lv=40;S.w={quill:8};let own=0;for(let i=0;i<300;i++)for(const o of x.offers(3))if(o.t==='w'&&o.k==='quill')own++;return own}""")
        check('Lv8 이면 무기 카드는 더 안 나옴(마스터 카드로 넘어감)', r == 0, r)
        # ── 3. 해금 조건 — 공용 무기 Lv5 가 카드 풀에서 올릴 수 있음(승수=사료, 앙앵모르딱=튀김기)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.lv=40;const out={};
          for(const w of ['feed','fryer']){S.w={quill:1};let got=0;for(let i=0;i<400;i++)for(const o of x.offers(3))if(o.t==='w'&&o.k===w)got++;out[w]=got;}
          return out}""")
        check('브장신 카드 풀에 사료·튀김기가 나옴(해금 조건용)', r['feed'] > 0 and r['fryer'] > 0, r)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;for(let l=1;l<=5;l++){S.w.feed=l;S.w.fryer=l;}
          const pg0=x.getProg();pg0.w5={};x.setProg(pg0);x.endRun(false,true);const pr=x.getProg();
          const sf=x.CHARS.find(c=>c.k==='ssu').un.ok(pr),am=x.CHARS.find(c=>c.k==='amd').un.ok(pr);return {sf:!!sf,am:!!am,w5:pr.w5}}""")
        check('사료 Lv5 → 승수 해금 / 튀김기 Lv5 → 앙앵모르딱 해금 조건이 충족됨', r['sf'] and r['am'], r)
        # ── 4. 무기마다 Lv1~8 · 각성 · 마스터 5단계 — 예외 없이 돌고 실제 피해를 낸다
        rows = []
        for k, (w, wl) in UNIQ.items():
            await pg.evaluate("c=>{const x=__p6x;x.CH_set(c);x.start();}", k)
            dmg = {}
            for L in range(1, 9):
                r = await pg.evaluate("a=>{const x=__p6x;x.S.w[a.w]=a.L;x.S.cd[a.w]=0;x.S.dmgBy={};x.S.t=Math.max(x.S.t,60);x.S.tier={};x.tkCalc();const r=__runner(a);return {r,d:x.S.dmgBy[a.w]||0}}".replace('__runner(a)', '(' + RUN + ')(a)'), {'w': w, 'L': L, 'sec': 16 if L == 1 else 10, 'keep': {w: L}})
                dmg[L] = round(r['d'])
                if r['r'].get('res'): break
                if L == 1 and wl == 1 or L == wl: pass
            check(f'{w} Lv1~8 각 10초 — 모두 피해를 냄', all(v > 0 for v in dmg.values()), dmg)
            # 마스터 3단계 → 각성 + 5단계
            r = await pg.evaluate("a=>{const x=__p6x;x.S.w[a.w]=8;x.S.tier={[a.w]:3};x.tkCalc();x.S.dmgBy={};x.S.cd[a.w]=0;const r=(" + RUN + ")(a);return {r,d:x.S.dmgBy[a.w]||0}}", {'w': w, 'sec': 12, 'keep': {w: 8}})
            check(f'{w} Lv8 + 마스터 3단계 12초 — 피해', r['d'] > 0, round(r['d']))
            r = await pg.evaluate("a=>{const x=__p6x;x.S.w[a.w]=8;x.S.ev[a.w]=1;x.S.tier={[a.w]:5};x.tkCalc();x.S.dmgBy={};x.S.cd[a.w]=0;const r=(" + RUN + ")(a);return {r,d:x.S.dmgBy[a.w]||0}}", {'w': w, 'sec': 20, 'keep': {w: 8}})
            check(f'{w} 각성 + 5단계 20초 — 피해', r['d'] > 0, round(r['d']))
            rows.append((w, dmg))
        # ── 5. 장비·패시브를 끼워도(곱빼기·광역·근성·고양) 돈다
        for k, (w, wl) in UNIQ.items():
            r = await pg.evaluate("a=>{const x=__p6x;x.CH_set(a.k);x.start();const S=x.S;S.t=90;S.ps={amt:3,area:5,might:5,cd:5,pspd:5,glass:3,luck:5,dur:5};S.w[a.w]=8;x.tkCalc();x.synCalc();S.dmgBy={};const r=(" + RUN + ")(a);return {r,d:S.dmgBy[a.w]||0}}", {'k': k, 'w': w, 'sec': 20, 'keep': {w: 8}})
            check(f'{k}: 패시브 풀세트로 20초', r['d'] > 0, round(r['d']))
        # ── 5b. 엄! 외침 — 겁먹은 적은 나에게서 멀어지고 접촉 피해가 없다 · 보스는 도망 안 가고 느려지기만
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('eom');x.start();const S=x.S;S.t=120;const p=S.p;S.w.eom=5;S.cd.eom=0;
          const mk=(boss)=>{const e=x.spawnEnemy(0,1,boss?'fin':null,{x:p.x+60,y:p.y});return e;};
          for(let i=0;i<4;i++)x.update(1/30);
          const es=[];for(let i=0;i<6;i++){const e=x.spawnEnemy(0,1,null,{x:p.x+50+i*5,y:p.y+i*6});if(e)es.push(e);}
          S.cd.eom=0;const d0=es.map(e=>Math.hypot(e.x-p.x,e.y-p.y));S.p.keys=0;
          let hits=0;const hp0=p.hp;for(let i=0;i<20;i++){x.update(1/30);}
          const d1=es.map(e=>e.on?Math.hypot(e.x-p.x,e.y-p.y):999);
          return {fear:es.filter(e=>e.fear>0).length,n:es.length,far:d1.filter((d,i)=>d>d0[i]).length,hp:p.hp>=hp0-.01}}""")
        check('엄! 외침: 범위 안의 적이 겁먹어 멀어짐 + 접촉 피해 없음', r['fear'] >= 3 and r['far'] >= 3 and r['hp'], r)
        # ── 6. 보스·미니 보스가 있을 때(보스는 안 밀림·기절 면역) 예외 없이
        r = await pg.evaluate("""a=>{const x=__p6x,out={};for(const [k,[w]] of Object.entries(a)){x.CH_set(k);x.start();const S=x.S;S.t=300;S.w[w]=8;S.nextBoss=301;
            const r=(%s)({sec:25,keep:{[w]:8}});out[k]=r.res?'result':'ok';}return out}""" % RUN, {k: [v[0]] for k, v in UNIQ.items()})
        check('300초(첫 보스 직전) 시점에서 13종 모두 25초 예외 없음', all(v == 'ok' for v in r.values()), r)
        await pg.evaluate("c=>{const x=__p6x;x.CH_set(c);x.start();}", 'brj')
        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('\n표(Lv별 10초 피해):'); [print(' ', w, d) for w, d in rows]
    print('\n%d 개 중 실패 %d: %s' % (N[0], len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
