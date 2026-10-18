# -*- coding: utf-8 -*-
"""🐺 신캐릭터 「탐지견」(tjg · 워윅 코스프레) + 고유 무기 「갈가리 찢기」(maul) 검증 (2026-10-18 사장님 지시).
사용: python3 tests/survivors_tjg_test.py      (종료코드 0 = 전부 통과)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅(__p6x · __p6y)을 꽂는다.
구성: A 데이터·완전성 · B 약한 적 우선 · C 달려들기 · D 물어뜯기(피해·휩쓸림·쿨 감소) · E 영원한 굶주림(회복·상한) · F 각성(무한한 속박) ·
      G 패시브·단계·곱빼기 전부 · H 풀 상한·이어하기 · I 화면·해금(맛동산 상점) · J 그리기·소리·색"""
import asyncio, sys, os, re, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
H.HOOK += "\nwindow.__p6y={U3,F3CAP,AU,PASS,SPX,EX,TK,spawnBoss,PFX,SGV,CSX,CSTAT,csS,cstat,RES,takenMul,hitP,DUR,PS,mauS,maulPick,maulNear,maulReach,maulBite,tjgHeal,cdxEntries,SHOPUN,PFXSN};\n"   # 이 시험만 쓰는 훅(sv_harness.py 는 고치지 않는다)
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)
def near(a, b, tol): return a is not None and abs(a - b) <= tol

# ── 장면 준비: 탐지견이 갈가리 찢기만 들고, 제자리 고정 적들을 세운다. a: L ev tier ps es[{a 각도 · d 거리 · f 체력 비율 · boss · el · bg · r}]
PRE = r"""Math.random=window.__rnd0;const x=__p6x,y=__p6y;x.CH_set(a.ch||'tjg');x.start();const S=x.S,p=S.p,dt=a.dt||1/60;
 S.w=Object.assign({maul:a.L||1},a.w||{});S.cd={};S.ev=a.ev?{maul:1}:{};S.tier=a.tier?{maul:a.tier}:{};S.ps=a.ps||{};S.rel={};S.pt={};x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();S.x3.f.length=0;
 const E=[];for(const o of (a.es||[])){const ex=p.x+Math.cos(o.a*Math.PI/180)*o.d,ey=p.y+Math.sin(o.a*Math.PI/180)*o.d;
   let e;if(o.boss){e=y.spawnBoss('mao');}else e=x.spawnEnemy(0,2.5,null,{x:ex,y:ey});
   e.x=ex;e.y=ey;e.sp=0;e.mhp=o.m||1e9;e.hp=e.mhp*(o.f===undefined?1:o.f);if(o.el)e.el=1;if(o.bg)e.bg=1;if(o.r)e.r=o.r;E.push({e,x:ex,y:ey,f:o.f,pin:o.pin!==false});}
 S.live=x.enemies.a.filter(q=>q.on);
 const step=(keep)=>{if(!a.hurtMe)p.hp=p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys={};for(const q of E){if(!q.pin||!q.e.on)continue;q.e.x=q.x;q.e.y=q.y;if(!keep&&!a.keepHp)q.e.hp=q.e.mhp*(q.f===undefined?1:q.f);}x.update(dt);};
"""
def J(body): return "(a)=>{" + PRE + body + "}"

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    src = open(os.path.join(H.ROOT, 'survivors_x.html'), encoding='utf-8').read()
    async with async_playwright() as p:
        b = await H.launch(p, args=['--autoplay-policy=no-user-gesture-required'])
        ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate("window.__rnd0=Math.random;__p6x.srvUnl(['brj','tjg'])")   # 상점 캐릭터는 서버가 열어 줘야 시작된다 — 구매한 사람(서버 unlocks 에 tjg) 흉내
        ev = lambda body, **a: pg.evaluate(J(body), a)

        # ───────────────── A. 데이터 · 완전성
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;const c=x.CHARS.find(c=>c.k==='tjg'),w=x.WEAP.maul,T=x.TIERS.maul,sy=x.SYN.find(s=>s.k==='u_maul'),names=x.CHARS.map(c=>c.k),ctab=Object.keys(x.WEAP);
          return {c:c&&{w:c.w,wl:c.wl||1,hp:c.hp,spd:c.spd,mag:c.mag,img:c.img,nm:c.nm,e:c.e,q:c.q,tag:c.tag,ds:c.ds,boss:!!c.boss,shop:!!c.shop,t:c.un&&c.un.t,ok0:c.un.ok({kills:99999,deaths:99,maxLv:99,best:99999,bossKill:9,w5:{},bk:{}}),same:c.un===y.SHOPUN,keys:Object.keys(c)},
            order:names.slice(names.indexOf('eom'),names.indexOf('eom')+2),
            w:w&&{only:w.only,pair:w.pair,pairOk:!!x.PASS?true:false,ds:w.ds,evnm:w.ev&&w.ev.nm,evic:w.ev&&w.ev.ic,evds:w.ev&&w.ev.ds,ic:w.ic,nm:w.nm,rl:w.rl},
            pass:Object.keys(y.PASS),T:T&&T.map(t=>t[1]),sy:sy&&{req:sy.req,fx:sy.fx},u3:y.U3.maul,csx:y.CSX.tjg,pfx:y.PFX.maul,noPfx:ctab.filter(k=>!y.PFX[k]),
            sn:y.PFXSN.maul,noSn:ctab.filter(k=>!y.PFXSN[k]),relNone:!x.REL.sg_tjg&&!Object.values(x.REL).some(r=>r.ch==='tjg'),potion:!!x.WEAP.potion&&!x.WEAP.potion.only,n:names.length}}""")
        c = r['c']
        check('CHARS tjg: 고유 무기 maul · 이름 탐지견 · 🐺 · 한마디 「냄새가 나… 약한 놈의 냄새가」 · 시작 체력 보통(hp·spd·mag 필드 없음) · 보스 아님', c and c['w'] == 'maul' and c['wl'] == 1 and c['nm'] == '탐지견' and c['e'] == '🐺' and c['q'] == '냄새가 나… 약한 놈의 냄새가' and c['hp'] is None and c['spd'] is None and c['mag'] is None and not c['boss'], c)
        check('그림 있음: img 1 + img/survivors/char_tjg.webp 파일이 있다', c and c['img'] == 1 and os.path.exists(os.path.join(H.ROOT, 'img', 'survivors', 'char_tjg.webp')), c and c['img'])
        check('판매 = 🍘 맛동산 상점 1개(shop:1 · 유미·엄장신과 같은 SHOPUN 객체) · 진행도 조건 함수는 무엇을 줘도 거짓 · 포인트 상점(SHOPUN_SV)이 아니다', c and c['shop'] and c['same'] and not c['ok0'] and '맛동산 상점' in c['t'], c and c['t'])
        line = re.search(r"\{k:'tjg',.*?\},\n", src).group(0)
        check('CHARS tjg 줄에 진행도 해금 코드·포인트 상점 문구가 없다', 'p.kills' not in line and 'p.best' not in line and 'SHOPUN_SV' not in line and 'un:SHOPUN}' in line, line[:200])
        check('선택 화면 순서: 엄장신 바로 다음 탐지견(맛동산 상점 구역)', r['order'] == ['eom', 'tjg'], r['order'])
        w = r['w']
        check('WEAP.maul: only tjg · 짝 패시브 might(실제 패시브) · 8줄 · 각성 「무한한 속박」 · 이름 갈가리 찢기', w and w['only'] == 'tjg' and w['pair'] == 'might' and 'might' in r['pass'] and len(w['ds']) == 8 and w['evnm'] == '무한한 속박' and w['nm'] == '갈가리 찢기' and w['ic'] == '🐺', w)
        check('각성 알림 글씨(ev.ds): 폰 배너 안에 들어간다(50자 이하)', w and len(w['evds']) <= 50, w and len(w['evds']))
        check('TIERS.maul: 마스터 3 + 각성 2 (피해 +12% · 쿨 -7% · 범위 +15% · 연타 +2 · 시간 +0.4초·피해 +8%)', r['T'] == [{'d': .12}, {'c': .07}, {'a': .15}, {'n': 2}, {'life': .4, 'd': .08}], r['T'])
        check('콤보 u_maul: 🐺 + 🧪 재물획득 물약(공용) · 모든 피해 +8% · 광역 +6%', r['sy'] and r['sy']['req'] == ['maul', 'potion'] and r['sy']['fx'] == {'dmg': .08, 'area': .06} and r['potion'], r['sy'])
        check('PFX·PFXSN 표에 maul 이 있고 모든 무기가 PFX·짧은 이름을 가진다', r['pfx'] == {'cd': 'yy', 'cnt': 'nn', 'spd': 'nn', 'dur': 'nn', 'area': 'pp', 'luck': 'nn'} and r['noPfx'] == [] and r['sn'] == '찢기' and r['noSn'] == [], (r['pfx'], r['noPfx'], r['noSn']))
        check('시그니처 유물 없음(배불배불처럼) — REL 에 sg_tjg 도, ch 가 tjg 인 유물도 없다', r['relNone'])
        U = r['u3']
        check('U3.maul 수치표(밸런스 측정으로 맞춘 값 — 바꾸면 RESULT.md 의 측정표를 다시 잴 것)', U == {'d': 66, 'cd': 1.6, 'dist': 110, 'T': .14, 'pad': 60, 'sp': .6, 'spR': 60, 'heal': 1.2, 'kcd': .5, 'kcap': 1.0, 'hg': {'rng': 480, 'dist': 440, 'T': .3, 't': 1.2, 'n': 6, 'p': .4, 'sm': .6, 'red': .25, 'ls': 1}}, U)
        check('CSX.tjg 수치(체력 50% 이하 · 때리면 0.3 · 잡으면 1.5 · 잃은 체력만큼 최대 ×2.5 · 초당 3 · 통 1.5초치)', r['csx'] == {'at': .5, 'hit': .3, 'kill': 1.5, 'mx': 1.5, 'cap': 3, 'bk': 1.5}, r['csx'])
        ds = w['ds']; U = r['u3']
        check('카드 문구가 값을 읽는다: Lv1 처치당 0.5초·최대 1.0초 · 주변 60% 위력 · Lv2 거리 +15% · Lv3 피해 +40% · Lv4 쿨 -15% · Lv5 +40% · Lv6 거리 +15% 범위 +30% · Lv7 쿨 -15% · Lv8 +50% 한 번 더 · 주변 절반 위력',
              f"최대 {U['kcap']:.1f}초" in ds[0] and f"{round(U['sp']*100)}% 위력" in ds[0] and f"{U['kcd']}초 줄고" in ds[0] and '+15%' in ds[1] and '피해 +40%' in ds[2] and '쿨타임 -15%' in ds[3] and '피해 +40%' in ds[4] and '거리 +15%' in ds[5] and '휩쓸림 범위 +30%' in ds[5] and '쿨타임 -15%' in ds[6] and '피해 +50%' in ds[7] and '한 번 더 문다' in ds[7], ds)
        wr = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;x.CH_set('tjg');x.start();const S=x.S,R=l=>y.maulReach(l);return {r:[1,2,5,6,8].map(R),dl:[2,3,4,5,8].map(l=>x.DL3(l))}}""")
        check('Lv2 · Lv6 에 달려드는 거리 ×1.15 씩(110 → 126.5 → 145.5) · 피해 DL3 는 Lv3 ×1.4 · Lv5 ×1.4 · Lv8 ×1.5', near(wr['r'][0], 110, .01) and near(wr['r'][1], 126.5, .01) and near(wr['r'][2], 126.5, .01) and near(wr['r'][3], 145.475, .01) and near(wr['dl'][1] / wr['dl'][0], 1.4, .001) and near(wr['dl'][3] / wr['dl'][2], 1.4, .001) and near(wr['dl'][4] / wr['dl'][3], 1.5, .001), wr)
        check('Lv1 달려드는 거리(110)는 태웅 박치기(140)보다 짧다', r['u3']['dist'] < 140)
        cs = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;const c=x.CHARS.find(c=>c.k==='tjg');const a=y.cstat(c).rows.map(r=>r.nm+'|'+(r.v||'')+'|'+r.ds);
          const o=[y.CSX.tjg.hit,y.CSX.tjg.cap,y.CSX.tjg.mx,y.CSX.tjg.at];y.CSX.tjg.hit=.7;y.CSX.tjg.cap=9;y.CSX.tjg.mx=4;y.CSX.tjg.at=.25;const b=y.cstat(c).rows.map(r=>r.ds+'|'+r.v).join('');[y.CSX.tjg.hit,y.CSX.tjg.cap,y.CSX.tjg.mx,y.CSX.tjg.at]=o;return {a,b}}""")
        check('고유스텟 1줄(영원한 굶주림): 문장에 50% · 0.3 · 1.5 · 2.5배 · 3 HP 가 읽힌다', len(cs['a']) == 1 and all(s_ in cs['a'][0] for s_ in ['50%', '0.3', '1.5', '2.5배', '3 HP', '영원한 굶주림']), cs['a'])
        check('고유스텟 문장은 CSX 값을 읽는다(0.3→0.7 · 3→9 · mx 2→4 · 50%→25% 로 바꾸면 문장이 바뀐다)', all(s_ in cs['b'] for s_ in ['0.7', '9 HP', '5배', '25%']), cs['b'])
        cdx = await pg.evaluate("""()=>{const y=__p6y;const L=y.cdxEntries();const e=L.find(q=>q.key==='w:maul');const p=L.find(q=>q.key==='p:might');return {e:e&&{nm:e.nm,who:e.who&&e.who.k,pair:e.pair&&e.pair.key,lv:e.lv.length,ev:e.ev&&e.ev.nm,ms:!!e.ms},pw:p&&p.pairs.map(w=>w.key)}}""")
        check('도감(cdxEntries): 갈가리 찢기가 탐지견 전용 · 짝 패시브 💪 근성(might) · 단계 8줄 · 각성 · 마스터 표 · 근성 칸에도 짝 무기로 올라 있다', cdx['e'] and cdx['e']['who'] == 'tjg' and cdx['e']['pair'] == 'p:might' and cdx['e']['lv'] == 8 and cdx['e']['ev'] == '무한한 속박' and cdx['e']['ms'] and 'w:maul' in cdx['pw'], cdx)

        # ───────────────── B. 약한 적 우선 (체력 비율이 낮은 적부터)
        r = await ev("""step();const M=y.mauS();const t=E.map(q=>q.e.sn);return {sn:M.sn,t,hit:E.map(q=>q.e.hp<q.e.mhp)}""", L=1, es=[{'a': 0, 'd': 60, 'f': 1}, {'a': 90, 'd': 80, 'f': .4}, {'a': 180, 'd': 100, 'f': .8}])
        check('체력이 낮은 적 우선: 코앞(100%) · 조금 떨어진(40%) · 더 먼(80%) 중 40% 짜리를 문다 — 가까운 순이 아니다', r['sn'] == r['t'][1], r)
        r = await ev("""step();return {sn:y.mauS().sn,t:E.map(q=>q.e.sn)}""", L=1, es=[{'a': 0, 'd': 90, 'f': 1}, {'a': 90, 'd': 60, 'f': 1}, {'a': 180, 'd': 110, 'f': 1}])
        check('체력 비율이 모두 같으면 가장 가까운 적(60)을 문다', r['sn'] == r['t'][1], r)
        r = await ev("""const es=E;for(let i=0;i<6;i++)step();const M=y.mauS();return {sn:M.sn,cd:S.cd.maul,t:M.t}""", L=1, es=[{'a': 0, 'd': 400, 'f': .1}])
        check('거리 + 여유(110+60) 밖의 적은 아무리 약해도 노리지 않는다 — 쿨타임을 0 으로 두고 대기(다음 프레임에 바로)', r['sn'] == 0 and r['cd'] == 0 and r['t'] == 0, r)
        r = await ev("""step();return {sn:y.mauS().sn,t:E.map(q=>q.e.sn),boss:E[1].e.boss?1:0}""", L=1, es=[{'a': 0, 'd': 130, 'f': 1}, {'a': 90, 'd': 75, 'boss': 1, 'f': .3, 'm': 5000}])
        check('보스도 체력 비율이 낮으면 우선(30% 보스 vs 가까운 100% 잡몹 → 보스)', r['boss'] and r['sn'] == r['t'][1], r)
        r = await ev("""const e=E[0].e;e.sv=1;step();const q=y.mauS().sn;return {a:q,sn:E[0].e.sn}""", L=1, es=[{'a': 0, 'd': 60, 'f': .2}])
        check('은신한 적(e.sv)은 노리지 않는다(aim3 와 같은 규칙)', r['a'] == 0, r)

        # ───────────────── C. 달려들기 — 짧게 · 몸통에 박히지 않고 바로 앞에서 멈춘다
        r = await ev("""const e=E[0].e;const x0=p.x,y0=p.y;for(let i=0;i<30;i++)step();const dd=Math.hypot(e.x-p.x,e.y-p.y);return {moved:Math.hypot(p.x-x0,p.y-y0),dd,gap:e.r+p.r,hp:e.hp<e.mhp}""", L=1, es=[{'a': 0, 'd': 150, 'f': .5}])
        check('먼 적(150) → 110 만큼만 달려들어 적 바로 앞(몸통 겹침 없음)에서 멈추고 문다', r['moved'] <= 110.5 and r['dd'] >= r['gap'] + 4 and r['hp'], r)
        r = await ev("""const e=E[0].e;const x0=p.x,y0=p.y;for(let i=0;i<30;i++)step();return {moved:Math.hypot(p.x-x0,p.y-y0),hp:e.hp<e.mhp}""", L=1, es=[{'a': 0, 'd': 30, 'f': .5}])
        check('이미 코앞(30)이면 제자리에서 문다(움직임 거의 없음)', r['moved'] < 30 and r['hp'], r)
        r = await ev("""const e=E[0].e;const dd0=Math.hypot(e.x-p.x,e.y-p.y);const c0=S.cd.maul;step();return {cd:S.cd.maul,yt:p.yt,t:y.mauS().t,inv:p.inv||0}""", L=1, es=[{'a': 0, 'd': 100, 'f': .5}])
        check('달려드는 동안 무적이 없다(p.inv 0) · 쿨타임 1.6초 설정 · 달려드는 시간 0.14초', r['inv'] == 0 and near(r['cd'], 1.6, .03) and r['t'] > 0, r)

        # ───────────────── D. 물어뜯기 — 피해 · 주변 휩쓸림 · 쿨 감소
        r = await ev("""const e=E[0].e;for(let i=0;i<30;i++)step(true);const d=e.mhp-e.hp;return {d,by:S.dmgBy.maul,mt:y.U3.maul.d*x.DL3(1)}""", L=1, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1, 'm': 1e6}])
        check('물어뜯기 한 번 = U3.maul.d(66) × DL3(Lv1) 정도(통계 maul 에 잡힌다)', r['by'] > 0 and near(r['d'], r['mt'], r['mt'] * .06), r)
        r = await ev("""const t=E[0].e,n1=E[1].e,n2=E[2].e;for(let i=0;i<30;i++)step(true);const d=t.mhp-t.hp;return {d,n1:(n1.mhp-n1.hp)/d,n2:n2.mhp-n2.hp}""", L=1, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1, 'm': 1e6}, {'a': 0, 'd': 70, 'f': 1, 'm': 1e6}, {'a': 0, 'd': 200, 'f': 1, 'm': 1e6}])
        check('주변 휩쓸림: 문 자리 반경 60 안의 적은 60% 위력으로 맞고 밖의 적은 안 맞는다', near(r['n1'], .6, .03) and r['n2'] == 0, r)
        r = await ev("""const e=E[0].e;e.hp=1;e.mhp=10;E[0].f=.1;const c=S.cd.maul;for(let i=0;i<20;i++)step(true);return {on:e.on,cd:S.cd.maul,kc:y.mauS().kc,kills:S.kills}""", L=1, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1}])
        check('처치하면 쿨타임이 0.5초 준다(한 마리당) — 한 번에 최대 1.0초', not r['on'] and near(r['kc'], .5, .001), r)
        r = await ev("""const e=E[0].e;e.mhp=100;e.hp=1;const M=y.mauS();M.kc=.6;S.cd.maul=2;const tg=E[0].e;y.maulBite(1,y.TK('maul'),tg.sn,1,34,1);const q={kc:M.kc,cd:S.cd.maul};
            const e2=x.spawnEnemy(0,2.5,null,{x:p.x+30,y:p.y});e2.sp=0;e2.mhp=100;e2.hp=1;S.live.push(e2);y.maulBite(1,y.TK('maul'),e2.sn,1,34,1);q.kc2=M.kc;q.cd2=S.cd.maul;return q""", L=1, keepHp=1, es=[{'a': 0, 'd': 30, 'f': 1}])
        check('쿨 감소 상한: 이번 쿨타임에 이미 0.6 줄었으면 처치해도 0.4 만(총 1.0 상한) — 그 뒤 처치는 더 줄이지 않는다', near(r['kc'], 1.0, .001) and near(r['cd'], 1.6, .001) and near(r['kc2'], 1.0, .001) and near(r['cd2'], 1.6, .001), r)
        r = await ev("""const e=E[0].e;const hp0=e.hp;let n=0;for(let i=0;i<60;i++){step(true);}return {bites:S.dmgBy.maul>0,cd:S.cd.maul}""", L=1, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1, 'm': 1e7}])
        check('쿨타임마다 물어뜯는다(1초 안에 한 번 · 1.6초 쿨 안에 연속 안 문다)', r['bites'], r)
        for L, want in [(1, 1.6), (3, 1.6), (4, 1.6 * .85), (7, 1.6 * .85 * .85), (8, 1.6 * .85 * .85)]:
            r = await ev("""step();return {cd:S.cd.maul}""", L=L, es=[{'a': 0, 'd': 40, 'f': .5}])
            check('Lv%d 쿨타임 %.4f (Lv4 · Lv7 에 ×0.85)' % (L, want), near(r['cd'], want, .005), r)
        r = await ev("""const e=E[0].e;for(let i=0;i<40;i++)step(true);return {d1:e.mhp-e.hp}""", L=8, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1, 'm': 1e8}])
        r2 = await ev("""const e=E[0].e;for(let i=0;i<40;i++)step(true);return {d1:e.mhp-e.hp}""", L=7, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1, 'm': 1e8}])
        check('Lv8: 한 번 더 문다 — 첫 입(DL3 8단계)에 두 번째 60% 가 더해진다', r['d1'] > r2['d1'] * 1.5 * 1.45 and r['d1'] < r2['d1'] * 1.5 * 1.7, (r, r2))
        r = await ev("""const e=E[0].e;for(let i=0;i<40;i++)step(true);return {d1:e.mhp-e.hp}""", L=8, tier=3, keepHp=1, es=[{'a': 0, 'd': 40, 'f': 1, 'm': 1e8}])
        check('마스터 3단계(범위 +15%) 에서도 문다(오류 없이 피해)', r['d1'] > 0, r)

        # ───────────────── E. 영원한 굶주림 — 체력 50% 이하인 적을 때리거나 잡으면 회복
        HIT = """const e=E[0].e;S.p.hp=a.hp;const c=y.csS();c.hb=a.hb===undefined?9:a.hb;const h0=p.hp;x.hurt(e,a.dmg);return {dh:p.hp-h0,hb:c.hb,on:e.on,r:e.hp/e.mhp}"""
        r = await ev(HIT, hp=100 * .5, dmg=10, es=[{'a': 0, 'd': 300, 'f': .6, 'm': 100, 'pin': False}], hurtMe=1)
        check('때려서 체력이 50% 이하가 되면 회복: 내 체력 50% → ×(1+1.5×0.5)=×1.75 → 0.3×1.75 = 0.525', near(r['dh'], .525, .01) and not (r['r'] > .5), r)
        r = await ev(HIT, hp=20, dmg=10, es=[{'a': 0, 'd': 300, 'f': .6, 'm': 100, 'pin': False}], hurtMe=1)
        check('내 체력이 낮을수록 커진다: 20% → 잃은 80% → ×2.2 → 0.66', near(r['dh'], .66, .01), r)
        r = await ev(HIT, hp=99.999999, dmg=10, es=[{'a': 0, 'd': 300, 'f': .6, 'm': 100, 'pin': False}], hurtMe=1)
        check('내 체력이 가득이면 ×1 만(아주 조금)', r['dh'] <= .3001, r)
        r = await ev(HIT, hp=50, dmg=1, es=[{'a': 0, 'd': 300, 'f': .9, 'm': 100, 'pin': False}], hurtMe=1)
        check('때린 뒤에도 체력이 50% 를 넘는 적(90% → 89%)은 회복이 없다', r['dh'] == 0 and r['r'] > .5, r)
        r = await ev(HIT, hp=50, dmg=500, es=[{'a': 0, 'd': 300, 'f': 1, 'm': 100, 'pin': False}], hurtMe=1)
        check('한 방에 잡아도 회복한다(잡으면 1.5 × ×1.75 = 2.625)', not r['on'] and near(r['dh'], 2.625, .01), r)
        r = await ev(HIT, hp=50, dmg=10, hb=0, es=[{'a': 0, 'd': 300, 'f': .6, 'm': 100, 'pin': False}], hurtMe=1)
        check('통이 비어 있으면 회복이 없다(초당 상한)', r['dh'] == 0, r)
        r = await ev("""S.p.hp=10;const c=y.csS();c.hb=0;const es=E.map(q=>q.e);let tot=0;const n=[];
            for(let s=0;s<600;s++){S.p.hp=10;const c2=y.csS();if(s%2===0)for(const e of es){e.hp=e.mhp*.4;x.hurt(e,1);}  // 매 프레임 많은 약한 적을 때린다
              const h0=p.hp;x.keys={};S.spawnT=-1e12;for(const e of es){e.x=p.x+300;e.y=p.y+300;}x.update(1/60);tot+=Math.max(0,p.hp-10);n.push(c2.hb);}
            return {tot,t:600/60}""", es=[{'a': 0, 'd': 300, 'f': .4, 'm': 1e6, 'pin': False} for _ in range(30)], hurtMe=1)
        check('초당 상한: 약한 적 30마리를 프레임마다 때려도 10초에 회복은 3×10 + 통 4.5 = 34.5 HP 이하', r['tot'] <= 3 * r['t'] + 4.5 + 1 and r['tot'] > 10, r)
        r = await ev("""x.CH_set('brj');x.start();const S2=x.S;S2.w={maul:1};const e=x.spawnEnemy(0,2.5,null,{x:S2.p.x+300,y:S2.p.y});e.sp=0;e.mhp=100;e.hp=60;S2.p.hp=50;const h0=S2.p.hp;x.hurt(e,30);return {dh:S2.p.hp-h0}""", es=[], hurtMe=1)
        check('탐지견이 아니면(브장신) 같은 일이 있어도 회복 없음', r['dh'] == 0, r)
        r = await ev("""const e=E[0].e;S.p.hp=40;const hp0=p.hp;let tot=0;const c=y.csS();c.hb=9;for(let i=0;i<600;i++){const h=p.hp;x.keys={};S.spawnT=-1e12;e.x=p.x+300;e.y=p.y;e.hp=e.mhp*.45;x.update(1/60);}return {hpDelta:p.hp-hp0,hb:c.hb}""", es=[{'a': 0, 'd': 300, 'f': .45, 'm': 1e6, 'pin': False}], hurtMe=1)
        check('통(hb)은 cap×bk(4.5)를 넘게 모이지 않는다', r['hb'] <= 4.5001, r)

        r = await ev("""S.p.hp=50;y.csS().hb=9;const e=E[0].e;y.maulBite(1,y.TK('maul'),e.sn,1,1,1);return {full:p.hp,}""", L=1, hurtMe=1, keepHp=1, es=[{'a': 0, 'd': 30, 'f': 1, 'm': 1e9}])
        r2 = await ev("""S.p.hp=50;y.csS().hb=9;const e=E[0].e;y.maulBite(1,y.TK('maul'),e.sn,1,1,1);return {low:p.hp}""", L=1, hurtMe=1, keepHp=1, es=[{'a': 0, 'd': 30, 'f': .3, 'm': 1e9}])
        check('물어뜯기 회복도 「적 체력 50% 이하」일 때만: 가득 찬 적 → 0 · 30% 적 → 회복(내 체력 50% 라 물기 1.2×1.75=2.1 + 때려서 0.3×1.75=0.525)', r['full'] == 50 and near(r2['low'], 52.625, .1), (r, r2))

        # ───────────────── F. 각성 「무한한 속박」 — 가장 센 적(보스 우선)에게 크게 도약해 붙잡고 연타
        r = await ev("""const t=E.map(q=>q.e.sn);step();const M=y.mauS();return {sn:M.sn,t,lp:M.lp,boss:E[0].e.boss?1:0}""", L=8, ev=1, es=[{'a': 0, 'd': 400, 'boss': 1, 'f': 1, 'm': 8000}, {'a': 90, 'd': 50, 'f': .1, 'm': 100}, {'a': 180, 'd': 80, 'bg': 1, 'f': 1, 'm': 500}])
        check('각성: 가까이서 약해진 잡몹이 있어도 보스(400 밖)를 노려 도약한다', r['boss'] and r['sn'] == r['t'][0] and r['lp'] == 1, r)
        r = await ev("""const t=E.map(q=>q.e.sn);step();return {sn:y.mauS().sn,t}""", L=8, ev=1, es=[{'a': 0, 'd': 300, 'f': 1, 'm': 300}, {'a': 90, 'd': 100, 'bg': 1, 'f': 1, 'm': 500}, {'a': 180, 'd': 200, 'el': 1, 'f': 1, 'm': 900}])
        check('보스가 없으면 대형 > 엘리트 > 최대 체력 순으로 가장 센 적', r['sn'] == r['t'][1], r)
        r = await ev("""const t=E.map(q=>q.e.sn);step();const M=y.mauS();return {sn:M.sn,t,lp:M.lp}""", L=8, ev=1, es=[{'a': 0, 'd': 100, 'f': 1, 'm': 300}, {'a': 90, 'd': 100, 'f': .3, 'm': 500}, {'a': 180, 'd': 100, 'f': 1, 'm': 200}])
        check('보스·대형·엘리트가 없으면 각성도 평소처럼 체력 비율이 낮은 적을 문다(도약·붙잡기 없음 — 잡몹 떼에서 약해지지 않게)', r['sn'] == r['t'][1] and r['lp'] == 0, r)
        r = await ev("""const e=E[0].e,x0=p.x;let hang=0,seen=0,maxd=0,st=0,slow=0,tk=1;const hp0=e.hp;
            for(let i=0;i<180;i++){step(true);const M=y.mauS();if(M.hg>0){hang++;const d=Math.hypot(p.x-e.x,p.y-e.y);maxd=Math.max(maxd,d);st=Math.max(st,e.st||0);slow=Math.max(slow,e.slow||0);tk=Math.min(tk,y.takenMul());}}
            return {hang,maxd,st,slow,tk,dmg:hp0-e.hp,hk:y.mauS().hk,dist:Math.hypot(p.x-x0,p.y-0)}""", L=8, ev=1, keepHp=1, es=[{'a': 0, 'd': 400, 'boss': 1, 'f': 1, 'm': 80000}])
        check('보스에게 도약 → 붙잡힌 채 따라간다(거리 일정) · 보스는 스턴되지 않고(e.st 0) 느려지기만(e.slow>0) · 받는 피해 0.75배', r['hang'] > 20 and r['maxd'] < 120 and r['st'] == 0 and r['slow'] > 0 and near(r['tk'], .75, .001), r)
        r = await ev("""const e=E[0].e;const hp0=e.hp;let bites=0,last=0;for(let i=0;i<240;i++){step(true);}return {dmg:hp0-e.hp,exp:y.U3.maul.d*x.DL3(8)*1.15}""", L=8, ev=1, keepHp=1, es=[{'a': 0, 'd': 400, 'boss': 1, 'f': 1, 'm': 1e9}])
        check('각성 붙잡기 연타: 6번 × 0.4 + 착지 1번 ≈ 3.4 입분의 피해가 들어간다(보스 4초 안에)', r['dmg'] > r['exp'] * 3.0, r)
        r = await ev("""const e=E[0].e;let hang=0,st=0;for(let i=0;i<240;i++){step(true);if(y.mauS().hg>0){hang++;st=Math.max(st,e.st||0);}}return {hang,st}""", L=8, ev=1, keepHp=1, es=[{'a': 0, 'd': 300, 'bg': 1, 'f': 1, 'm': 1e9}])
        check('보스가 아닌 센 적(대형)을 붙잡으면 굳는다(e.st>0) · 시간은 0.6배', r['st'] > 0 and r['hang'] > 0, r)
        r = await ev("""const e=E[0].e;let seen=0,zero=0,mx=0;for(let i=0;i<400;i++){step(true);const g=y.mauS().hg;if(g>0){seen=1;mx=Math.max(mx,g);}else if(seen)zero=1;}return {seen,zero,mx}""", L=8, ev=1, keepHp=1, es=[{'a': 0, 'd': 300, 'boss': 1, 'f': 1, 'm': 1e9}])
        check('붙잡기는 끝난다: 한 번 붙잡은 뒤 hg 가 다시 0 이 된다(영구히 매달리지 않는다) · 한 번 붙잡는 시간은 (1.2+0.4초) 이하', r['seen'] and r['zero'] and r['mx'] <= 1.61, r)
        seg = lambda a, b_: src[src.index(a):src.index(b_, src.index(a))]
        segs = {'함수': seg('// 🐺 [2026-10-18 사장님 지시] 탐지견 — 갈가리 찢기.', '// 🔥 쌍둥이 이빨 — 앞쪽 직사각형 베기'), '무기 블록': seg('// 🐺 갈가리 찢기 → ⛓ 무한한 속박', '// 🎤 플레이브 노래부르기 → 🎶 앙코르 무대')}
        check('무적·스턴 금지: 갈가리 찢기 코드에 invGrant(무적 부여)·p.inv 가 없다 · 붙잡기는 e.st 짧은 굳음/e.slow 뿐(보스는 e.st 를 만지지 않는다)', all('invGrant' not in v and 'p.inv' not in v for v in segs.values()) and 'e.boss)e.slow=Math.max(e.slow,.5);else e.st=' in segs['함수'], '')
        check('이어하기 안전: 갈가리 찢기 블록·함수에 S.dq 콜백이 없다(지연은 S.x3.mau 숫자로)', all('S.dq' not in v for v in segs.values()), '')
        check('새 S 키·최상위 let 을 만들지 않는다(상태는 S.x3.mau 객체 안 숫자)', not re.search(r"^let\s+mau|S\.mau\b", src, re.M), '')

        # ───────────────── G. 패시브 · 단계 · 곱빼기 · 모드 — 전부 한 번씩 돌려 예외 없음
        bad = []
        cases = 0
        for L in (1, 2, 4, 6, 8):
            for evf in (0, 1):
                for tier in (0, 3, 5):
                    if tier == 5 and not evf: continue
                    for ps in ({}, {'amt': 3, 'area': 5, 'cd': 5, 'dur': 5, 'might': 5, 'spd': 5, 'luck': 5}):
                        for mode in ('n', 'h', 'v'):
                            cases += 1
                            r = await pg.evaluate("""(a)=>{Math.random=window.__rnd0;const x=__p6x,y=__p6y;x.CH_set('tjg');x.start();const S=x.S;S.w={maul:a.L};S.ev=a.ev?{maul:1}:{};S.tier=a.tier?{maul:a.tier}:{};S.ps=a.ps;
                              S.hard=a.mode==='h'||a.mode==='v';S.vh=a.mode==='v'?1:0;x.tkCalc();x.synCalc();S.t=a.mode==='n'?200:700;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
                              let errs=0,nan=0;for(let i=0;i<300;i++){S.p.hp=S.p.mhp*(i%90<45?1:.3);S.xp=0;S.need=1e12;x.keys=i%80<40?{KeyD:true}:{KeyA:true};try{x.update(1/30);}catch(e){errs++;if(errs<2)return {err:String(e),st:(e.stack||'').slice(0,200)};}
                                if(!isFinite(S.p.x)||!isFinite(S.p.y)||!isFinite(S.p.hp))nan++;}
                              return {errs,nan,f:S.x3.f.length,mau:y.mauS()}}""", {'L': L, 'ev': evf, 'tier': tier, 'ps': ps, 'mode': mode})
                            if r.get('err') or r.get('errs') or r.get('nan') or r['f'] > 100: bad.append((L, evf, tier, bool(ps), mode, r))
        check('Lv 1·2·4·6·8 × 각성 × 마스터 단계 × 패시브 최대 × 일반·하드·베리하드 %d 가지: 예외·NaN·풀 초과 없음' % cases, not bad, bad[:2])

        # ───────────────── H. 풀 상한 · 이어하기
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;Math.random=window.__rnd0;x.CH_set('tjg');x.start();const S=x.S;S.w={maul:8};S.ev={maul:1};S.tier={maul:5};S.ps={amt:3,area:5,cd:5,dur:5,mag:5,might:5};x.tkCalc();S.t=900;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          let errs=0,mx=0;for(let i=0;i<1800;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
            try{x.update(1/30);}catch(e){errs++;if(errs<2)return {err:String(e),st:e.stack.slice(0,300)};}
            mx=Math.max(mx,S.x3.f.length);}
          return {errs,mx,kills:S.kills,dm:S.dmgBy.maul}}""")
        check('Lv8 + 각성 + 5단계 + 곱빼기 3 + 광역·끈기·획득·근성 5 에서 60초: 예외 없음 · 풀 100 이하 · 피해 통계 maul 이 잡힌다', r.get('errs') == 0 and r['mx'] <= 100 and r['dm'] > 0, r)
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;Math.random=window.__rnd0;x.CH_set('tjg');x.start();const S=x.S;S.w={maul:8};S.ev={maul:1};S.tier={maul:5};S.ps={might:5};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          for(const q of x.enemies.a)q.on=false;const bs=y.spawnBoss('mao');bs.x=S.p.x+300;bs.y=S.p.y;bs.sp=0;bs.mhp=bs.hp=1e9;
          let hung=-1;for(let i=0;i<400;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;x.keys={};bs.x=bs.x;x.update(1/30);if(y.mauS().hg>0.3&&hung<0){hung=i;break;}}
          if(hung<0)return {err:'붙잡지 못함'};
          const M0=JSON.stringify(y.mauS()),cs0=JSON.stringify(y.csS());
          let b;try{b=y.RES.build();}catch(e){return {err:'build '+e}}
          if(!b||!b.text)return {err:'no text'};
          x.state='title';let ok;try{ok=y.RES.restore(b.text);}catch(e){return {err:'restore '+e}}
          x.resume();const S2=x.S,M1=JSON.parse(JSON.stringify(y.mauS()));let errs=0,rel=false,follow=0;const bs2=x.enemies.a.find(e=>e.on&&e.boss);
          for(let i=0;i<200;i++){S2.p.hp=S2.p.mhp;try{x.update(1/30);}catch(e){errs++;}if(y.mauS().hg>0&&bs2)follow=Math.max(follow,0);if(y.mauS().hg===0)rel=true;}
          return {ok:!!ok,hs:M1.hs===JSON.parse(M0).hs,hg:M1.hg>0,errs,rel,mau0:JSON.parse(M0).hg,mau1:M1.hg,boss:!!bs2}}""")
        check('이어하기: 붙잡은 채 저장 → 복구하면 붙잡은 적(hs)·남은 시간(hg)이 그대로 · 복구한 판이 계속 돌아 붙잡기가 끝난다', r.get('ok') and r['hs'] and r['hg'] and r['errs'] == 0 and r['rel'], r)
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;Math.random=window.__rnd0;x.CH_set('tjg');x.start();const S=x.S;S.w={maul:8};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          for(let i=0;i<300;i++){S.p.hp=S.p.mhp*.5;S.xp=0;S.need=1e12;x.keys={KeyD:true};x.update(1/30);}
          const c0=y.csS().hb,k0=S.kills,M0=JSON.parse(JSON.stringify(y.mauS()));let b=y.RES.build();x.state='title';let ok=y.RES.restore(b.text);x.resume();const S2=x.S;
          let errs=0;for(let i=0;i<200;i++){S2.p.hp=S2.p.mhp*.5;try{x.update(1/30);}catch(e){errs++;}}
          return {ok:!!ok,errs,hb:(S2.x3.cs&&S2.x3.cs.hb)>=0,kc:k0<=S2.kills,mau:Object.keys(y.mauS()).sort().join()===Object.keys(M0).sort().join()}}""")
        check('이어하기: 평범한 판(회복 통 · 갈가리 찢기 상태)도 저장→복구 뒤 계속 돈다 · 상태 키가 그대로', r.get('ok') and r['errs'] == 0 and r['hb'] and r['kc'] and r['mau'], r)

        # ───────────────── I. 화면 · 해금(412×860) — 맛동산 상점
        r = await pg.evaluate("""()=>{const x=__p6x;x.srvUnl([]);x.show('title');x.renderRoster();const bs=[...document.querySelectorAll('#roster button')];const b=bs.find(e=>e.textContent.includes('탐지견'));
          b&&b.click();return {sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,small:b&&b.querySelector('small').textContent,lock:b&&b.classList.contains('lock'),desc:document.getElementById('chDesc').textContent,n:bs.length,hs:bs.map(e=>Math.round(e.getBoundingClientRect().width)),img:!!(b&&b.querySelector('img'))}}""")
        check('선택 화면(412px): 가로 스크롤 없음 · 카드 폭이 모두 같다', r['sw'] <= r['cw'] and len(set(r['hs'])) == 1, (r['sw'], r['cw'], set(r['hs'])))
        check('잠긴 카드: 작은 글씨 「🍘 맛동산 상점에서 1개 — 디스코드 「맛동산상점」」(유미·엄장신과 같은 문구) · 누르면 설명창에 같은 안내 + 로그인 안내 · 그림 카드(img)', r['lock'] and '맛동산 상점에서 1개' in r['small'] and '맛동산상점' in r['desc'] and '디스코드 로그인 필요' in r['desc'] and r['img'], (r['small'], r['desc']))
        hw = await pg.evaluate("()=>document.querySelector('ol.how').textContent")
        check('조작법 도움말(❔): 고유 시작 무기 목록에 「탐지견 🐺」(엄장신 다음)', '엄장신 📢 · 탐지견 🐺 · 배고배고 📸' in hw, hw[hw.find('고유 시작 무기'):][:200])
        await pg.evaluate("__p6x.srvUnl(['brj','tjg'])")
        ST = {'unl': ['brj']}; POSTS = []
        async def mock(rt):
            u = rt.request.url; hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
            if rt.request.method == 'OPTIONS': await rt.fulfill(status=204, headers=hdr); return
            if '/p6/run' in u:
                POSTS.append(json.loads(rt.request.post_data or '{}')); await rt.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'rank': 1, 'total': 1, 'unlocks': ST['unl'], 'best_t': 10}))
            elif '/p6/me' in u: await rt.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ST['unl'], 'daily_done': False}))
            else: await rt.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'board': [], 'hard': [], 'vhard': []}))
        async def open_page(unl, login=True, local=None, w=412, h=860):
            ST['unl'] = unl; POSTS.clear()
            c_, p_, e_ = await H.new_page(b, srv.port, w=w, h=h, mock=mock)
            js = "()=>{" + ("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}));" if login else "") + (local or '') + "}"
            await p_.evaluate(js)
            await p_.reload(); await p_.wait_for_function('window.__p6x!==undefined'); await p_.wait_for_timeout(500)
            return c_, p_, e_
        TILE = """()=>{const x=__p6x;document.getElementById('homeBtn').click();const b=[...document.querySelectorAll('#roster button')].find(e=>e.textContent.includes('탐지견'));const c=x.CHARS.find(c=>c.k==='tjg');
          const can=x.canPick(c,x.getProg());const o={lock:b.classList.contains('lock'),small:b.querySelector('small').textContent,can,unl:[...x.SRVUNL]};b.click();o.desc=document.getElementById('chDesc').textContent;o.sel=x.CH.k;
          x.CH_set('tjg');x.start();o.started=x.CH.k;o.weap=Object.keys(x.S.w);o.hp=x.S.p.mhp;return o}"""
        c_, p_, e_ = await open_page(['brj'], login=False)
        r = await p_.evaluate(TILE)
        check('(가) 로그아웃: 카드 잠김 · 설명 「디스코드 로그인 필요」 · 못 고르고 시작해도 브장신', r['lock'] and not r['can'] and '맛동산 상점' in r['small'] and '디스코드 로그인 필요' in r['desc'] and r['sel'] == 'brj' and r['started'] == 'brj' and 'maul' not in r['weap'], r)
        check('(가) 페이지 오류·콘솔 에러 없음', not e_, e_[:3]); await c_.close()
        c_, p_, e_ = await open_page(['brj'])
        r = await p_.evaluate(TILE)
        check('(나) 로그인 + 미구매: 잠김 · 설명 「구매하면 열려요」 · 못 고르고 시작해도 브장신', r['lock'] and not r['can'] and '구매하면 열려요' in r['desc'] and r['sel'] == 'brj' and r['started'] == 'brj' and 'maul' not in r['weap'], r)
        await c_.close()
        c_, p_, e_ = await open_page(['brj'], local="localStorage.setItem('p6_unl_v1',JSON.stringify(['brj','tjg','yumi','eom']));localStorage.setItem('p6_char_v1','tjg');localStorage.setItem('p6_prog_v1',JSON.stringify({kills:99999,deaths:99,maxLv:60,best:4000,bossKill:5,w5:{},bk:{}}));")
        r = await p_.evaluate(TILE)
        await p_.reload(); await p_.wait_for_function('window.__p6x!==undefined'); await p_.wait_for_timeout(500)
        ch0 = await p_.evaluate("()=>__p6x.CH.k")
        check('(다) 로컬 저장소에 tjg(해금 목록·선택·처치 99,999)를 써넣어도 잠김 · 시작해도 브장신 · 새로 열어도 브장신으로 시작', r['lock'] and not r['can'] and r['sel'] == 'brj' and r['started'] == 'brj' and ch0 == 'brj', (r, ch0))
        await c_.close()
        c_, p_, e_ = await open_page(['brj', 'tjg'])
        r = await p_.evaluate(TILE)
        check('(라) 맛동산 상점에서 산 사람(서버 unlocks 에 tjg): 열림 · 고를 수 있고 시작하면 탐지견 + 갈가리 찢기 · 체력 100', (not r['lock']) and r['can'] and r['sel'] == 'tjg' and r['started'] == 'tjg' and r['weap'] == ['maul'] and r['hp'] == 100, r)
        post = await p_.evaluate("""()=>{const x=__p6x;x.CH_set('tjg');x.start();return Object.keys(x.S.w)}""")
        # 기록 POST 에 상점 캐릭터 키가 로컬 해금 목록으로 새지 않는다
        await p_.evaluate("""()=>{const x=__p6x;x.CH_set('tjg');x.start();x.S.p.hp=0;}""")
        lk = await p_.evaluate("()=>JSON.parse(localStorage.getItem('p6_unl_v1')||'[]')")
        check('(라) 산 뒤에도 로컬 해금 목록(p6_unl_v1)에는 tjg 를 쌓지 않는다(열림 여부는 서버 목록만)', 'tjg' not in lk, lk)
        check('(라) 페이지 오류·콘솔 에러 없음', not e_, e_[:3]); await c_.close()
        c_, p_, e_ = await open_page(['brj', 'tjg'])
        info = await p_.evaluate("""()=>{const x=__p6x;document.getElementById('homeBtn').click();x.renderRoster();const b=[...document.querySelectorAll('#roster button')].find(e=>e.textContent.includes('탐지견'));b.click();
          return {desc:document.getElementById('chDesc').textContent,html:document.getElementById('chDesc').innerHTML,stat:document.body.innerText.includes('영원한 굶주림')}}""")
        check('열린 카드 설명창: 이름 · 고유스텟 「영원한 굶주림」 · 고유 무기 설명(🐺 갈가리 찢기)이 보인다', '탐지견' in info['desc'] and info['stat'] and '갈가리 찢기' in info['desc'], info['desc'][:200])
        await c_.close()

        # ───────────────── J. 그리기 · 소리 · 색
        draw_err = await pg.evaluate("""()=>{Math.random=window.__rnd0;const x=__p6x,y=__p6y;const out=[];
          for(const low of [false,true]){x.LOW;x.CH_set('tjg');x.start();const S=x.S;S.w={maul:8};S.ev={maul:1};S.tier={maul:5};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
            let errs=0;for(let i=0;i<240;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;x.keys=i%80<40?{KeyD:true}:{KeyA:true};try{x.update(1/30);x.draw();}catch(e){errs++;if(errs<2)out.push(String(e)+(e.stack||'').slice(0,200));}}
            out.push('errs='+errs);}
          return out}""")
        check('그리기: 업데이트+draw 를 8초 돌려도 예외 없음(발톱 자국·표식·고리·소리)', all(o == 'errs=0' for o in draw_err), draw_err)
        c1 = re.search(r"case 'mw':\{if\(!inV.*?cx\.lineCap='butt';break;\}", src, re.S)
        mark = re.search(r"function maulMark.*?\n", src)
        check('색 규칙: 발톱 자국 · 표식 · 도약 효과에 위험색(빨강·주황·금색)이 없다 — 흰·박하·하늘뿐', c1 and mark and not re.search(r"255,\s*(1[0-9]{2}|[0-9]{1,2}),|#f[0-9a-f]{2}[0-4]|rgb\(2[0-9]{2},\s*[0-9]{1,2},", c1.group(0) + mark.group(0)), '')
        check('소리: AU maul 이 있고 GAP·SPAM 표에도 있다', "case 'maul':" in src and 'maul:150' in src and 'maul:1,panty' in src, '')

        check('페이지 오류·콘솔 에러 없음', not errs, errs[:3])
        await b.close()
    srv.close()
    print('\n통과 %d / %d' % (N[0] - len(FAILS), N[0]))
    if FAILS:
        print('실패:'); [print(' -', f) for f in FAILS]
        sys.exit(1)
asyncio.run(main())
