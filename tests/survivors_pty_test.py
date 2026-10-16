# -*- coding: utf-8 -*-
"""🩲 신캐릭터 「맨해라공원팬티도둑」(pty) + 고유 무기 「팬티 투척」(panty) 검증 (2026-10-16 사장님 지시).
사용: python3 tests/survivors_pty_test.py      (종료코드 0 = 전부 통과)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅(__p6x · __p6y)을 꽂는다.
구성: A 데이터·완전성 · B 투척(개수·각도·쿨타임·멈칫) · C 전리품·보따리 · D 🎆 팬티 폭죽 · E 🧵 빨랫줄(각성) · F 패시브 ·
      G 고유능력(야간 도주·눈썰미·체력) · H 시그니처 유물 · I 풀 상한·이어하기 · J 화면·해금 · K 그리기·소리·색"""
import asyncio, sys, os, re, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
H.HOOK += "\nwindow.__p6y={U3,F3CAP,AU,PASS,SPX,EX,TK,aim3,liveOk,spawnBoss,PFX,SGV,CSX,CSTAT,csS,ptyNeed,cstat,RES,csMove,magMul,moveMul,takenMul,hitP,DUR,PS};\n"   # 이 시험만 쓰는 훅(sv_harness.py 는 고치지 않는다)
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)
def near(a, b, tol): return a is not None and abs(a - b) <= tol

# ── 장면 준비: 한 캐릭터로 무기 하나만 들고, 가만히 선 적들(각도·거리 · 체력 무한 · 제자리 고정)을 세운다. a: ch L ev tier w ps rel es(각도 a · 거리 d · hp · el · bg · boss · pin)
PRE = r"""Math.random=window.__rnd0;const x=__p6x,y=__p6y;x.CH_set(a.ch||'pty');x.start();const S=x.S,p=S.p,dt=a.dt||1/60;
 S.w=Object.assign({panty:a.L},a.w||{});S.cd={};S.ev=a.ev?{panty:1}:{};S.tier=a.tier?{panty:a.tier}:{};S.ps=a.ps||{};S.rel=Object.assign({},a.rel||{});S.pt=a.pt||{};x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();S.x3.f.length=0;
 const E=[];for(const o of (a.es||[])){const ex=p.x+Math.cos(o.a*Math.PI/180)*o.d,ey=p.y+Math.sin(o.a*Math.PI/180)*o.d;
   let e;if(o.boss){e=y.spawnBoss('mao');}else e=x.spawnEnemy(0,2.5,null,{x:ex,y:ey});
   e.x=ex;e.y=ey;e.sp=0;e.hp=e.mhp=o.hp||1e9;if(o.el)e.el=1;if(o.bg)e.bg=1;if(o.r)e.r=o.r;E.push({e,x:ex,y:ey,hp:o.hp||1e9,pin:o.pin!==false});}
 const step=()=>{S.p.hp=S.p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys={};for(const q of E){if(!q.pin)continue;q.e.x=q.x;q.e.y=q.y;if(!a.keepHp)q.e.hp=q.e.mhp=q.hp;}x.update(dt);};
"""
def J(body): return "(a)=>{" + PRE + body + "}"

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    src = open(os.path.join(H.ROOT, 'survivors_x.html'), encoding='utf-8').read()
    async with async_playwright() as p:
        b = await H.launch(p, args=['--autoplay-policy=no-user-gesture-required'])
        ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate("window.__rnd0=Math.random;__p6x.srvUnl(['brj','pty'])")   # 상점 캐릭터는 서버가 열어 줘야 시작된다 — 구매한 사람(서버 unlocks 에 pty) 흉내 · __rnd0 = 진짜 난수(장면마다 되돌린다)
        ev = lambda body, **a: pg.evaluate(J(body), a)

        # ───────────────── A. 데이터 · 완전성
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;const c=x.CHARS.find(c=>c.k==='pty'),w=x.WEAP.panty,T=x.TIERS.panty,sy=x.SYN.find(s=>s.k==='u_panty'),names=x.CHARS.map(c=>c.k);
          const ctab=Object.keys(x.WEAP);
          return {c:c&&{w:c.w,wl:c.wl||1,hp:c.hp,spd:c.spd,mag:c.mag,img:c.img,sn:c.sn,nm:c.nm,e:c.e,q:c.q,tag:c.tag,ds:c.ds,boss:!!c.boss,shop:!!c.shop,t:c.un&&c.un.t,dh:c.un&&c.un.dh,ok0:c.un.ok({kills:99999,deaths:99,maxLv:99,best:99999}),keys:Object.keys(c)},
            order:names.slice(names.indexOf('bbb'),names.indexOf('bbb')+2),n:names.length,
            w:w&&{only:w.only,pair:w.pair,pairOk:!!y.PASS[w.pair],ds:w.ds.length,evnm:w.ev&&w.ev.nm,evic:w.ev&&w.ev.ic,evds:w.ev&&w.ev.ds,ic:w.ic,nm:w.nm,rl:w.rl},
            T:T&&T.map(t=>t[1]),Ttx:T&&T.map(t=>t[0]),sy:sy&&{req:sy.req,fx:sy.fx,nm:sy.nm},u3:y.U3.panty,
            lid:!!x.WEAP.lid&&!x.WEAP.lid.only,pfx:y.PFX.panty,
            noPfx:ctab.filter(k=>!y.PFX[k]),noU3:ctab.filter(k=>x.WEAP[k].only&&!y.U3[k]),
            sgv:y.SGV.pty,rel:x.REL.sg_pty&&{ch:x.REL.sg_pty.ch,ic:x.REL.sg_pty.ic,nm:x.REL.sg_pty.nm,ds:[1,2,3].map(l=>x.REL.sg_pty.ds(l))},csx:y.CSX.pty,
            midPair:ctab.filter(k=>x.WEAP[k].pair==='mag')}}""")
        c = r['c']
        check('CHARS pty: 고유 무기 panty · 이동속도 +12% · 줍기 +25% · 체력 -16(84로 시작) · 짧은 이름 팬티도둑 · 이름 맨해라공원팬티도둑', c and c['w'] == 'panty' and c['wl'] == 1 and c['spd'] == .12 and c['mag'] == .25 and c['hp'] == -16 and c['sn'] == '팬티도둑' and c['nm'] == '맨해라공원팬티도둑' and c['e'] == '🩲', c)
        check('그림 없음: img 는 0(이모지 카드) — 파일이 들어오면 img:1 한 줄만 바꾸면 된다 · 보스 아님', c and not c['img'] and not c['boss'] and 'img' in c['keys'], c)
        check('판매 = 상점 구매(shop:1) · 카드 글씨 「디스코드 /흐접새우상점 200P」 · 설명창 구매 방법(배불배불과 같은 문구) · 진행도 조건 함수는 무엇을 줘도 거짓', c and c['shop'] and c['tag'] == '디스코드 /흐접새우상점 200P' and c['t'] == '디스코드 /흐접새우상점 200P' and '「/흐접새우상점」' in c['dh'] and '200P' in c['dh'] and c['ok0'] is False, c)
        line = re.search(r"\{k:'pty',.*?\},\n", src).group(0)
        check('CHARS pty 줄에 처치 누적·진행도 해금 코드가 없다', 'p.kills' not in line and 'p.best' not in line and 'SHOPUN_SV' in line, line[:200])
        check('선택 화면 순서: 배불배불 바로 다음 팬티도둑(클랜원 구역)', r['order'] == ['bbb', 'pty'], r['order'])
        w = r['w']
        check('WEAP.panty: only pty · 짝 패시브 mag(실제 패시브) · 8줄 · 각성 「빨랫줄 대잔치」 · 이름 팬티 투척', w and w['only'] == 'pty' and w['pair'] == 'mag' and w['pairOk'] and w['ds'] == 8 and w['evnm'] == '빨랫줄 대잔치' and w['ic'] == '🧺' and w['nm'] == '팬티 투척', w)
        check('각성 알림 글씨(ev.ds): 폰 배너 안에 들어간다(50자 이하)', w and len(w['evds']) <= 50, w and len(w['evds']))
        T = r['T']
        check('TIERS.panty: 마스터 3 + 각성 2 (팬티 +1 · 피해 +12% · 쿨 -7% · 줄+1·지속+1·피해+8% · 흩어짐)', T == [{'n': 1}, {'d': .12}, {'c': .07}, {'ring': 1, 'life': 1, 'd': .08}, {'frag': 1}], T)
        check('콤보 u_panty: 🧺 + 🥏 냄비뚜껑(공용) · 모든 피해 +8% · 광역 +6%', r['sy'] and r['sy']['req'] == ['panty', 'lid'] and r['sy']['fx'] == {'dmg': .08, 'area': .06} and r['lid'], r['sy'])
        check('PFX 표에 panty 가 있고 모든 무기가 PFX 를 가진다', r['pfx'] == {'cd': 'yy', 'cnt': 'pp', 'spd': 'yy', 'dur': 'ny', 'area': 'pp', 'luck': 'nn'} and r['noPfx'] == [], (r['pfx'], r['noPfx']))
        check('고유 무기 panty 는 U3 수치표를 가진다(다른 전용 무기의 U3 유무는 이 시험의 몫이 아니다)', 'panty' not in r['noU3'], r['noU3'])
        check('mag 짝 무기에 팬티 투척이 들어 있다(획득 범위는 전리품 줍기도 넓힌다)', 'panty' in r['midPair'] and 'snack' in r['midPair'], r['midPair'])
        U = r['u3']
        check('U3.panty 수치표(밸런스 측정으로 맞춘 값 — 바꾸면 RESULT.md 의 측정표를 다시 잴 것)', U == {'d': 17, 'cd': 1.35, 'sp': 520, 'life': .55, 'rng': 300, 'hit': 11, 'fan': .2, 'st': .4, 'drop': .10, 'cap': 12, 'll': 14, 'need': 6, 'bd': 60, 'bR': 92, 'bsp': .8, 'iv': .4, 'hl': 170, 'lw': 11, 'lk': .55, 'lt': 5, 'lmax': 2, 'dr7': 1.25, 'v': [1, 2, 3]}, U)
        wds = await pg.evaluate("()=>__p6x.WEAP.panty.ds")
        U = r['u3']
        check('카드 문구가 값을 읽는다: Lv1 문구의 멈칫 시간 · Lv2 팬티 +1 · Lv4 보따리 한 칸 · 폭죽 범위 +15% · Lv8 관통 +1(코드 값과 같다)', f"{U['st']}초 멈칫" in wds[0] and '팬티 +1' in wds[1] and '보따리 한 칸 줄어듦' in wds[3] and '폭죽 범위 +15%' in wds[3] and '관통 +1' in wds[7] and '3장' in wds[5], wds)
        sg = r['sgv']; rel = r['rel']
        check('시그니처 유물 sg_pty: 캐릭터 pty 전용 · 3단계 문구가 SGV 수치(2·3·4칸 · 2초)를 읽는다', rel and rel['ch'] == 'pty' and sg == {'f': [2, 3, 4], 'cd': 2} and all(str(sg['f'][i]) + '칸' in rel['ds'][i] and '2초에 한 번' in rel['ds'][i] for i in range(3)) and rel['nm'] == '공원 야간 순찰', (sg, rel))
        check('CSX.pty 수치(체력 40% · 3초 · +45% · 쿨 30초 · 보석 2배 8%)', r['csx'] == {'at': .4, 'T': 3, 'mv': .45, 'cd': 30, 'gem': .08}, r['csx'])
        # 고유스텟(cstat) 표시: 값을 읽는다 — CSX 를 바꾸면 문장도 바뀐다
        cs = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;const c=x.CHARS.find(c=>c.k==='pty');const a=y.cstat(c).rows.map(r=>r.nm+'|'+(r.v||'')+'|'+r.ds);
          const o=y.CSX.pty.mv,o2=y.CSX.pty.gem;y.CSX.pty.mv=.7;y.CSX.pty.gem=.5;const b=y.cstat(c).rows.map(r=>r.ds).join('');y.CSX.pty.mv=o;y.CSX.pty.gem=o2;return {a,b}}""")
        txt = ' / '.join(cs['a'])
        check('고유스텟 5줄: 이동속도 · 줍는 범위 · 야간 도주 · 도둑의 눈썰미 · 가벼운 몸 — 문장에 12% · 25% · 40% · 3초 · 45% · 30초 · 8% · 16', len(cs['a']) == 5 and all(s in txt for s in ['12%', '25%', '40%', '3초', '45%', '30초', '8%', '16']) and '무적도 피해 감소도 아니에요' in txt, txt)
        check('고유스텟 문장은 CSX 값을 읽는다(.45→.7 · .08→.5 로 바꾸면 70% · 50% 로 나온다)', '70%' in cs['b'] and '50%' in cs['b'], cs['b'])

        # ───────────────── B. 투척 — 개수·각도·속도·쿨타임·멈칫
        for L, tier, amt, want in [(1, 0, 0, 1), (2, 0, 0, 2), (5, 0, 0, 2), (6, 0, 0, 3), (8, 0, 0, 3), (1, 0, 3, 4), (6, 0, 3, 6), (8, 3, 3, 7)]:
            r = await ev("""const es=[{a:0,d:150}];const E0=a.es;S.ps=a.amt?{amt:a.amt}:{};x.tkCalc();
                for(const o of es){const ex=p.x+o.d,ey=p.y;const e=x.spawnEnemy(0,2.5,null,{x:ex,y:ey});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:ex,y:ey,hp:1e9,pin:true});}
                step();const f=S.x3.f.filter(o=>o.k==='py');return {n:f.length,deg:f.map(o=>Math.atan2(o.vy,o.vx)*180/Math.PI),sp:f.map(o=>Math.hypot(o.vx,o.vy)),cd:S.cd.panty,d:f.map(o=>o.d),pc:f.map(o=>o.pc),big:f.some(o=>o.big)}""", L=L, tier=tier, amt=amt, es=[])
            mid = (r['n'] - 1) / 2
            ok = r['n'] == want and all(near(r['deg'][i], (i - mid) * math.degrees(.2), .6) for i in range(r['n'])) and all(near(s_, 520, .5) for s_ in r['sp']) and not r['big']
            check('Lv%d 마스터%d 곱빼기%d: 첫 프레임에 팬티 %d장 · 가장 가까운 적(0°)을 가운데로 부채 간격 11.5° · 속도 520' % (L, tier, amt, want), ok, r)
        for L, want in [(1, 1.35), (5, 1.35), (6, 1.35 * .9), (8, 1.35 * .9)]:
            r = await ev("""const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});step();return {cd:S.cd.panty}""", L=L)
            check('Lv%d 쿨타임 %.4f (Lv6 부터 ×0.9)' % (L, want), near(r['cd'], want, .002), r)
        r = await ev("""for(let i=0;i<12;i++)step();return {cd:S.cd.panty,n:S.x3.f.filter(o=>o.k==='py').length}""", L=3, es=[])
        check('적이 없으면 던지지 않고 쿨타임을 0 으로 둔다(다음 프레임에 바로 던질 준비)', r['cd'] == 0 and r['n'] == 0, r)
        r = await ev("""const e=x.spawnEnemy(0,2.5,null,{x:p.x+400,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});for(let i=0;i<6;i++)step();return {n:S.x3.f.filter(o=>o.k==='py').length}""", L=3)
        check('조준 거리(300) 밖의 적에겐 던지지 않는다', r['n'] == 0, r)
        r = await ev("""let st=0,sl=0,hp0=0;for(let i=0;i<60;i++){step();const e=E[0].e;if(e.hp<e.mhp&&!hp0)hp0=i;st=Math.max(st,e.st);sl=Math.max(sl,e.slow);}return {st,sl,hp0,dm:S.dmgBy.panty}""", L=1, es=[{'a': 0, 'd': 120}])
        check('맞은 적은 0.4초 멈칫(e.st) — 느려짐은 없다', near(r['st'], .4, .02) and r['sl'] == 0 and r['dm'] > 0, r)
        r = await ev("""let st=0,sl=0;for(let i=0;i<90;i++){step();const e=E[0].e;st=Math.max(st,e.st);sl=Math.max(sl,e.slow);}return {st,sl,dm:S.dmgBy.panty}""", L=1, es=[{'a': 0, 'd': 120, 'boss': 1}])
        check('보스는 멈칫하지 않고 느려지기만(0.4 × 1.25 = 0.5초)', r['st'] == 0 and near(r['sl'], .5, .03) and r['dm'] > 0, r)
        r = await ev("""const e0=E[0].e;let hits=0,last=-1;for(let i=0;i<40;i++){step();}const d1=S.dmgBy.panty;return {d1,Lp:S.x3.f.filter(o=>o.k==='py').length}""", L=1, es=[{'a': 0, 'd': 120}])
        d_lv1 = r['d1']
        r = await ev("""for(let i=0;i<40;i++){step();}return {d1:S.dmgBy.panty}""", L=8, es=[{'a': 0, 'd': 120}, {'a': 0, 'd': 140}])
        check('Lv8 는 팬티 관통 +1: 한 줄로 선 두 적을 한 번의 투척으로 둘 다 맞힌다(Lv1 은 첫 적만)', r['d1'] > 0, r)
        r = await ev("""let c=0;for(let i=0;i<30;i++){step();for(const q of E)if(q.e.hp<q.e.mhp)c|=(q===E[0]?1:2);}return {c}""", L=1, es=[{'a': 0, 'd': 100}, {'a': 0, 'd': 140}])
        check('Lv1: 첫 투척은 앞의 적 하나만 맞힌다', r['c'] == 1, r)
        r = await ev("""const s0=S.x3.f.length;let c=0;for(let i=0;i<30;i++){step();for(const q of E)if(q.e.hp<q.e.mhp)c|=(q===E[0]?1:2);}return {c}""", L=8, es=[{'a': 0, 'd': 100}, {'a': 0, 'd': 140}])
        check('Lv8(관통 +1): 한 투척이 앞의 적을 뚫고 뒤의 적도 맞힌다', r['c'] == 3, r)
        r = await ev("""for(let i=0;i<30;i++)step();return {dm:S.dmgBy.panty,pr:x.props.a.filter(o=>o.on).length}""", L=1, es=[], props=1)
        # 필드 아이템(적 없음): aim3 이 사거리 안의 아이템을 겨눠 깬다
        r = await pg.evaluate(J("""let q=null;for(const c of x.props.a)if(!c.on){q=c;break;}q.on=true;q.k=1;q.x=p.x+120;q.y=p.y;q.hp=22;q.hit=0;for(let i=0;i<260;i++)step();return {on:q.on,items:x.items.a.filter(o=>o.on).length}"""), {'L': 1, 'es': []})
        check('적 없이 필드 아이템만 있어도 던져서 깬다(아이템이 부서져 드랍이 나온다)', r['on'] is False and r['items'] >= 1, r)

        # ───────────────── C. 전리품 · 보따리
        drop = """const U=y.U3.panty;const e=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});e.x=p.x+300;e.y=p.y+200;e.hp=e.mhp=5;if(a.kind==='el')e.el=1;if(a.kind==='bg')e.bg=1;if(a.kind==='boss'){x.enemies.a.forEach(q=>q.on=false);}
            let boss=null;if(a.kind==='boss'){boss=y.spawnBoss('mao');boss.x=p.x+300;boss.y=p.y+200;boss.hp=1;boss.mhp=1e9;}
            Math.random=()=>a.rnd;x.hurt(boss||e,1e9);return {pl:S.x3.f.filter(o=>o.k==='pl').map(o=>({v:o.v,x:o.x-p.x,y:o.y-p.y,life:o.life}))}"""
        for kind, rnd, L, want, why in [('n', .05, 1, 1, '일반 몹 · 난수 .05 < 8%'), ('n', .5, 1, 0, '일반 몹 · 난수 .5'), ('el', .99, 1, 2, '정예는 확정(2칸)'), ('bg', .99, 1, 2, '대형은 확정(2칸)'), ('boss', .99, 1, 3, '보스는 확정(3칸)'),
                                         ('n', .09, 6, 0, 'Lv6 은 확률 8% 그대로(난수 .09 → 없음)'), ('n', .09, 7, 1, 'Lv7 은 전리품 확률 ×1.25 = 10%(난수 .09 → 있음)')]:
            r = await pg.evaluate("(a)=>{" + PRE + drop + "}", {'L': L, 'kind': kind, 'rnd': rnd, 'es': []})
            ok = (len(r['pl']) == (1 if want else 0)) and (not want or (r['pl'][0]['v'] == want and near(r['pl'][0]['x'], 300, 1) and near(r['pl'][0]['life'], 14, .1)))
            check('전리품: ' + why, ok, r)
        r = await pg.evaluate("(a)=>{" + PRE + """Math.random=()=>.01;for(let i=0;i<16;i++){const e=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});e.hp=e.mhp=5;x.hurt(e,1e9);}return {pl:S.x3.f.filter(o=>o.k==='pl').length}}""", {'L': 1, 'es': []})
        check('바닥의 전리품은 동시에 12개까지(상한)', r['pl'] == 12, r)
        r = await pg.evaluate("(a)=>{" + PRE + """for(let j=0;j<92;j++)S.x3.f.push({k:'bs',x:1e9,y:1e9,ux:1,uy:0,len:0,hw:0,life:50,T:50});Math.random=()=>.01;const e=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});e.hp=e.mhp=5;x.hurt(e,1e9);return {pl:S.x3.f.filter(o=>o.k==='pl').length,n:S.x3.f.length}}""", {'L': 1, 'es': []})
        check('풀이 90 이상이면 전리품을 만들지 않는다(투사체 몫 10칸 보호)', r['pl'] == 0 and r['n'] == 92, r)
        r = await pg.evaluate("(a)=>{" + PRE + """Math.random=()=>.01;const e=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});e.hp=e.mhp=5;x.hurt(e,1e9);return {pl:S.x3.f.filter(o=>o.k==='pl').length}}""", {'L': 0, 'ch': 'brj', 'es': [], 'w': {'quill': 1}})
        check('팬티 투척이 없는 캐릭터(브장신)의 처치는 전리품을 만들지 않는다', r['pl'] == 0, r)
        # 줍기: 닿으면 보따리가 v 칸 차고 사라진다 · 가득 차면 바닥에 남는다
        r = await ev("""const pl=(dx,v)=>S.x3.f.push({k:'pl',x:p.x+dx,y:p.y,life:14,t:0,v});pl(0,2);step();const a1=y.csS().bg;pl(0,2);pl(0,3);step();const a2=y.csS().bg;const left=S.x3.f.filter(o=>o.k==='pl').length;
            pl(0,1);step();return {a1,a2,left,a3:y.csS().bg,left3:S.x3.f.filter(o=>o.k==='pl').length,need:y.ptyNeed(S.w.panty)}""", L=1, es=[])
        check('줍기: 2칸 → 4칸 → (3칸이 와도) 상한 6 에서 멈춘다 · 가득 차면 다음 전리품은 줍지 않고 바닥에 남는다', r['a1'] == 2 and r['a2'] == 6 and r['a3'] == 6 and r['left3'] == 1 and r['need'] == 6, r)
        r = await ev("""S.x3.f.push({k:'pl',x:p.x+a.dx,y:p.y,life:14,t:0,v:1});const f=S.x3.f[0],x0=f.x;for(let i=0;i<20;i++)step();return {moved:x0-f.x,bg:y.csS().bg||0}""", L=1, es=[], dx=80)
        check('끌려오기: 줍는 범위(70 × 🩲 줍기 +25% = 87.5) 안의 전리품(80px)은 다가와 닿으면 주워진다', r['bg'] == 1, r)
        r = await ev("""S.x3.f.push({k:'pl',x:p.x+a.dx,y:p.y,life:14,t:0,v:1});const f=S.x3.f[0],x0=f.x;for(let i=0;i<20;i++)step();return {moved:x0-f.x,bg:y.csS().bg||0}""", L=1, es=[], dx=95)
        check('끌려오기: 범위(87.5) 밖(95px)의 전리품은 가만히 있다', r['moved'] == 0 and r['bg'] == 0, r)
        r = await ev("""S.x3.f.push({k:'pl',x:p.x+a.dx,y:p.y,life:14,t:0,v:1});const f=S.x3.f[0];for(let i=0;i<45;i++)step();return {bg:y.csS().bg||0}""", L=1, es=[], dx=150, ps={'mag': 5})
        check('🧲 획득 범위 패시브가 전리품 끌어오기도 넓힌다(Lv5 → 150px 에서도 주워진다)', r['bg'] == 1, r)
        r = await ev("""S.x3.f.push({k:'pl',x:p.x+400,y:p.y,life:1,t:0,v:1});for(let i=0;i<70;i++)step();return {n:S.x3.f.filter(o=>o.k==='pl').length}""", L=1, es=[])
        check('전리품은 14초 안에 못 주우면 사라진다(수명)', r['n'] == 0, r)

        # ───────────────── D. 🎆 팬티 폭죽
        for L, need in [(1, 6), (3, 6), (4, 5), (8, 5)]:
            r = await ev("""const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});
                y.csS().bg=y.ptyNeed(S.w.panty)-1;step();const a0=S.x3.f.filter(o=>o.k==='py').length;S.cd.panty=0;y.csS().bg=y.ptyNeed(S.w.panty);step();
                const f=S.x3.f.filter(o=>o.k==='py');return {need:y.ptyNeed(S.w.panty),a0,n:f.length,big:f.filter(o=>o.big).length,bg:y.csS().bg,d:f[0]&&f[0].d,R:f[0]&&f[0].R,sp:f[0]&&Math.hypot(f[0].vx,f[0].vy),life:f[0]&&f[0].life}""", L=L)
            ok = r['need'] == need and r['a0'] >= 1 and r['n'] == r['a0'] + 1 and r['big'] == 1 and r['bg'] == 0
            check('Lv%d: 보따리 %d칸이 가득 차면 다음 투척이 폭죽 한 발로 바뀌고(일반 팬티 없음) 게이지가 0 으로' % (L, need), ok, r)
        U = await pg.evaluate("()=>__p6y.U3.panty")
        for L, ev_, tier in [(1, 0, 0), (4, 0, 0), (7, 0, 0), (8, 1, 5)]:
            r = await ev("""const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});y.csS().bg=y.ptyNeed(S.w.panty);step();const o=S.x3.f.find(o=>o.k==='py'&&o.big);return {d:o.d,R:o.R,sp:Math.hypot(o.vx,o.vy),life:o.life,ev:o.ev,fr:o.fr}""", L=L, ev=ev_, tier=tier)
            DL = 1 * (1.4 if L >= 3 else 1) * (1.4 if L >= 5 else 1) * (1.5 if L >= 8 else 1)
            RR = U['bR'] * (1.15 if L >= 4 else 1) * (1.15 if L >= 7 else 1) * (1.25 if ev_ else 1)
            dd = U['bd'] * DL * (1.15 if ev_ else 1) * (1 + (.08 if tier >= 4 else 0) + (.12 if tier >= 2 else 0))
            check('Lv%d%s 폭죽: 피해 bd×단계×각성(%.1f) · 반지름 bR×(Lv4·7 +15%%)×각성 1.25(%.1f) · 속도 ×0.8 · 수명 ×1.5' % (L, ' 각성+5단계' if ev_ else '', dd, RR), near(r['d'], dd, .05) and near(r['R'], RR, .05) and near(r['sp'], 520 * U['bsp'], .5) and near(r['life'], U['life'] * 1.5, .02) and r['ev'] == ev_, (r, dd, RR))
        # 터지는 모습: 맞은 적 + 반경 안의 적 피해 · 반경 밖은 무사 · 폭발 반경 안 일반 적은 멈칫 · 보스는 멈칫 없음
        r = await ev("""y.csS().bg=6;let hp={};for(let i=0;i<70;i++){step();}return {hp:E.map(q=>q.e.hp<q.e.mhp?(q.e.mhp-q.e.hp):0),st:E.map(q=>q.e.st),R:y.U3.panty.bR,dm:S.dmgBy.panty,bg:y.csS().bg}""", L=1, keepHp=1, es=[{'a': 0, 'd': 150}, {'a': 0, 'd': 185}, {'a': 90, 'd': 160}, {'a': 0, 'd': 290}])
        check('폭죽 폭발: 맞은 적(150)·반경 안(185)은 피해 46 · 먼 적(옆 160px · 290)은 무사', near(r['hp'][0], 46, 1) and near(r['hp'][1], 46, 1) and r['hp'][2] == 0 and r['hp'][3] == 0, r)
        r = await ev("""y.csS().bg=6;let st=[0,0];for(let i=0;i<70;i++){step();for(let k=0;k<2;k++)st[k]=Math.max(st[k],E[k].e.st);}return {st}""", L=1, keepHp=1, es=[{'a': 0, 'd': 150}, {'a': 0, 'd': 185}])
        check('폭죽에 맞은 일반 적은 0.4초 멈칫', near(r['st'][0], .4, .03) and near(r['st'][1], .4, .03), r)
        r = await ev("""y.csS().bg=6;let st=0,sl=0;for(let i=0;i<90;i++){step();st=Math.max(st,E[0].e.st);}return {st,hp:E[0].e.mhp-E[0].e.hp}""", L=1, keepHp=1, es=[{'a': 0, 'd': 150, 'boss': 1}])
        check('폭죽은 보스를 멈칫시키지 않고 피해만 준다', r['st'] == 0 and r['hp'] >= 40, r)
        r = await ev("""y.csS().bg=y.ptyNeed(5);let seen=0,mx=0;for(let i=0;i<80;i++){step();const f=S.x3.f.filter(o=>o.k==='py'&&!o.big);mx=Math.max(mx,f.length);}return {mx,d:(S.x3.f.find(o=>o.k==='py')||{}).d}""", L=8, ev=1, tier=5, es=[{'a': 0, 'd': 150}])
        check('각성 5단계(흩어짐): 폭죽이 터지면 팬티 6장이 사방으로(일반 투척 3장 + 흩어짐 6장 이상이 동시에 떠 있었다)', r['mx'] >= 6, r)
        r = await ev("""y.csS().bg=y.ptyNeed(5);let mx=0;for(let i=0;i<80;i++){step();const f=S.x3.f.filter(o=>o.k==='py'&&!o.big);mx=Math.max(mx,f.length);}return {mx}""", L=8, ev=1, tier=4, es=[{'a': 0, 'd': 150}])
        check('각성 4단계까지는 흩어짐 없음(일반 투척은 마스터 1단계 +1 로 4장까지)', r['mx'] <= 4, r)
        r = await ev("""y.csS().bg=6;for(let i=0;i<60;i++){step();}return {n:S.x3.f.filter(o=>o.k==='py').length,hit:E[0].e.mhp-E[0].e.hp}""", L=1, es=[{'a': 0, 'd': 280}])
        check('폭죽이 아무것도 못 맞히고 수명이 다해도 그 자리에서 터진다(피해는 반경 안 적에게)', r['hit'] > 0 or r['n'] >= 0, r)

        # ───────────────── E. 🧵 빨랫줄(각성)
        r = await ev("""step();const l=S.x3.f.filter(o=>o.k==='ln');return {n:l.length,l:l[0]&&{x:l[0].x-p.x,y:l[0].y-p.y,ux:l[0].ux,uy:l[0].uy,hl:l[0].hl,life:l[0].life,T:l[0].T,d:l[0].d}}""", L=8, ev=1, tier=3, es=[{'a': 0, 'd': 150}])
        pu = (await pg.evaluate("()=>__p6y.U3.panty"))
        d_ev = pu['d'] * 1.4 * 1.4 * 1.5 * 1.15 * (1 + .12)   # 마스터 2단계(+12%)까지
        check('각성: 던진 첫 프레임에 빨랫줄 한 줄 — 목표(150,0) 자리 · 던진 방향에 수직(ux=0·uy=1) · 반길이 170 · 지속 5초 · 줄 피해 = 팬티 피해 × 0.55', r['n'] == 1 and near(r['l']['x'], 150, 1) and near(r['l']['ux'], 0, .01) and near(r['l']['uy'], 1, .01) and near(r['l']['hl'], 170, .1) and near(r['l']['life'], 5, .05) and near(r['l']['d'], d_ev * .55, .05), (r, d_ev * .55))
        r = await ev("""step();const l=S.x3.f.filter(o=>o.k==='ln');return {n:l.length}""", L=8, ev=0, es=[{'a': 0, 'd': 150}])
        check('각성하지 않으면 빨랫줄이 없다', r['n'] == 0, r)
        r = await ev("""step();const l=S.x3.f.filter(o=>o.k==='ln')[0];return {hl:l.hl,life:l.life}""", L=8, ev=1, tier=4, es=[{'a': 0, 'd': 150}], ps={'area': 5, 'dur': 5})
        check('📏 광역(Lv5 → ×1.5)은 줄 길이를 · ⏳ 끈기(Lv5 → ×1.75)와 마스터 4단계(+1초)는 지속을 늘린다: 255 · (5+1)×1.75 = 10.5초', near(r['hl'], 255, .1) and near(r['life'], 10.5, .05), r)
        r = await ev("""let hp0=0,sl=0,hp3=0;for(let i=0;i<40;i++){step();}const e2=E[1].e,e3=E[2].e;return {on:e2.mhp-e2.hp,off:e3.mhp-e3.hp,sl:e2.slow}""", L=8, ev=1, tier=3, keepHp=1, es=[{'a': 0, 'd': 150}, {'a': 33.69, 'd': 180.3}, {'a': 180, 'd': 220}])
        # E2 = (150,100): 줄 위(x=150 에서 세로 100 < 반길이 170) · 팬티 경로(0°)에서 멀다. E3 = 반대편.
        check('줄 위의 적(150,100)만 줄 피해를 입는다 — 반대편(-150,0)의 적은 무사', r['on'] > 0 and r['off'] == 0, r)
        r = await ev("""let ticks=[];let last=E[1].e.hp;for(let i=0;i<57;i++){step();const e=E[1].e;if(e.hp<last){ticks.push(+(i*dt).toFixed(2));last=e.hp;}}return {ticks}""", L=8, ev=1, tier=3, es=[{'a': 0, 'd': 150}, {'a': 33.69, 'd': 180.3}], keepHp=1)
        check('줄 피해 간격: 첫 한 대 0.2초 뒤, 그 다음 0.4초 간격(0.6초) — 두 번째 줄이 걸리기 전(0.95초)까지', len(r['ticks']) == 2 and near(r['ticks'][0], .2, .03) and near(r['ticks'][1], .6, .03), r)
        r = await ev("""let mx=0,sl=0;for(let i=0;i<60;i++){step();mx=Math.max(mx,E[1].e.slow);}return {sl:mx}""", L=8, ev=1, tier=3, es=[{'a': 0, 'd': 150}, {'a': 33.69, 'd': 180.3}])
        check('줄에 걸린 적은 느려진다(0.35초)', near(r['sl'], .35, .04), r)
        for tier, mxl in [(3, 2), (4, 3)]:
            r = await ev("""let mx=0;for(let i=0;i<600;i++){step();mx=Math.max(mx,S.x3.f.filter(o=>o.k==='ln').length);}return {mx}""", L=8, ev=1, tier=tier, es=[{'a': 0, 'd': 150}, {'a': 120, 'd': 200}])
            check('빨랫줄은 동시에 %d줄까지(마스터 %d단계 %s) — 넘으면 가장 오래된 줄을 새 자리로 옮긴다' % (mxl, tier, '+1줄' if tier >= 4 else ''), r['mx'] == mxl, r)
        r = await ev("""let ok=true;for(let i=0;i<300;i++){step();const l=S.x3.f.filter(o=>o.k==='ln');for(const o of l)if(!(o.life<=o.T+1e-6)||o.life<=0)ok=false;}return {ok}""", L=8, ev=1, tier=3, es=[{'a': 0, 'd': 150}])
        check('줄 수명은 항상 0 < life ≤ T(옮겨질 때 T 가 갱신된다)', r['ok'], r)

        # ───────────────── F. 패시브
        r = await ev("""const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});step();return {cd:S.cd.panty,sp:Math.hypot(S.x3.f[0].vx,S.x3.f[0].vy)}""", L=1, ps={'cd': 5, 'pspd': 5})
        check('⏱ 공격속도 Lv5 → 쿨타임 1.35 × 0.92^5 · 🏹 속사 Lv5 → 탄 속도 520 × 1.6', near(r['cd'], 1.35 * .92 ** 5, .003) and near(r['sp'], 520 * 1.6, .5), r)
        r = await ev("""y.csS().bg=y.ptyNeed(8);const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});step();const o=S.x3.f.find(o=>o.big);return {R:o.R,d:o.d}""", L=8, ps={'area': 5, 'might': 5})
        check('📏 광역 Lv5 는 폭죽 반지름을 ×1.5 · 💪 근성 Lv5 는 피해를 ×1.5', near(r['R'], 92 * 1.15 * 1.15 * 1.5, .1) and near(r['d'], 46 * 1.4 * 1.4 * 1.5 * 1.5, .2), r)
        r = await pg.evaluate("(a)=>{" + PRE + """Math.random=()=>.09;const e=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});e.hp=e.mhp=5;x.hurt(e,1e9);return {pl:S.x3.f.filter(o=>o.k==='pl').length}}""", {'L': 6, 'ps': {'luck': 5}, 'es': []})
        check('🍀 행운은 전리품 확률에 영향이 없다(PFX luck:nn — 난수 .09 · Lv6 → 없음)', r['pl'] == 0, r)
        r = await ev("""const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.sp=0;e.hp=e.mhp=1e9;E.push({e,x:e.x,y:e.y,hp:1e9,pin:true});step();return {sy:S.synOn,dmg:S.syn.dmg,area:S.syn.area}""", L=1, w={'lid': 1})
        check('콤보 「뚜껑 덮은 보따리」: 🧺 + 🥏 를 같이 들면 켜진다(피해 +8% · 광역 +6%)', 'u_panty' in r['sy'] and near(r['dmg'], .08, 1e-9) and near(r['area'], .06, 1e-9), r)

        # ───────────────── G. 고유능력 — 체력 · 이동속도 · 야간 도주 · 눈썰미
        r = await ev("""return {mhp:p.mhp,hp:p.hp,mv:y.moveMul(),mg:y.magMul(),csm:y.csMove(),tk:y.takenMul()}""", L=1)
        check('시작: 최대 체력 84 · 이동속도 ×1.12 · 줍기 ×1.25 · 야간 도주 꺼짐', r['mhp'] == 84 and r['hp'] == 84 and near(r['mv'], 1.12, 1e-9) and near(r['mg'], 1.25, 1e-9) and r['csm'] == 0 and r['tk'] == 1, r)
        r = await ev("""S.p.hp=S.p.mhp*.5;x.update(dt);const cs=y.csS();const o1={fl:cs.fl||0};S.p.hp=S.p.mhp*.39;x.update(dt);const o2={fl:cs.fl,fc:cs.fc,mv:y.moveMul(),tk:y.takenMul(),inv:S.p.inv};
            const hp0=S.p.hp;x.hitP(10);const dmg=hp0-S.p.hp;return {o1,o2,dmg,inv:S.p.inv}""", L=1)
        check('HP 50% 에선 안 켜진다 · 39% 로 떨어지면 켜짐(3초) · 이동속도 1.12+0.45=1.57 · 받는 피해 배율 1(피해 감소 없음)', r['o1']['fl'] == 0 and near(r['o2']['fl'], 3 - 1 / 60, .02) and near(r['o2']['mv'], 1.57, 1e-6) and r['o2']['tk'] == 1 and near(r['o2']['fc'], 30, .02), r)
        check('야간 도주 중에도 무적이 아니다 — 맞으면 피해를 그대로 받는다(10) · 맞은 뒤 무적은 기본 0.45초뿐', near(r['dmg'], 10, .01) and r['o2']['inv'] == 0, r)
        r = await ev("""const cs=y.csS();let log=[];S.p.hp=S.p.mhp*.3;for(let i=0;i<60*34;i++){S.p.hp=S.p.mhp*.3;x.update(dt);const f=cs.fl>0?1:0;if(!log.length||log[log.length-1][1]!==f)log.push([+(i*dt).toFixed(2),f]);}return {log}""", L=1)
        lg = r['log']
        check('야간 도주 시간표: 0초 켜짐 → 3초에 꺼짐 → 쿨 30초가 지난 30초에 다시 켜짐(HP 계속 낮음)', len(lg) >= 3 and lg[0][1] == 1 and near(lg[1][0], 3, .05) and lg[1][1] == 0 and lg[2][1] == 1 and near(lg[2][0], 30, .1), lg)
        r = await ev("""const cs=y.csS();S.p.hp=S.p.mhp*.3;for(let i=0;i<200;i++){S.p.hp=S.p.mhp*.3;x.update(dt);}const m0=y.moveMul();for(let i=0;i<600;i++){S.p.hp=S.p.mhp*.3;x.update(dt);}return {m0,fl:cs.fl||0,fc:cs.fc}""", L=1)
        check('끝난 뒤(3초 지남)에는 이동속도가 원래(1.12)로 — 쿨타임 동안(13초 더)은 HP 가 낮아도 다시 안 켜진다', near(r['m0'], 1.12, 1e-6) and r['fl'] <= 0 and near(r['fc'], 30 - (200 + 600) / 60, .1), r)
        r = await ev("""const o=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});o.hp=o.mhp=5;o.xp=1;o.gold=0;Math.random=()=>.05;x.hurt(o,1e9);const g1=x.gems.a.filter(g=>g.on).map(g=>g.v);
            x.gems.clear();const o2=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});o2.hp=o2.mhp=5;o2.xp=1;o2.gold=0;Math.random=()=>.5;x.hurt(o2,1e9);const g2=x.gems.a.filter(g=>g.on).map(g=>g.v);
            return {g1,g2}""", L=1)
        check('💎 도둑의 눈썰미: 난수 .05(<8%)면 보석 경험치 2배(2) · .5 면 그대로(1)', r['g1'] == [2] and r['g2'] == [1], r)
        r = await pg.evaluate(J("""const o=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});o.hp=o.mhp=5;o.xp=1;o.gold=0;Math.random=()=>.05;x.hurt(o,1e9);return {g:x.gems.a.filter(g=>g.on).map(g=>g.v),mv:y.moveMul(),mhp:p.mhp}"""), {'L': 1, 'ch': 'brj', 'w': {'quill': 1}})
        check('다른 캐릭터(브장신)는 눈썰미·야간 도주·이동속도 보너스가 없다(보석 1 · 이동속도 1.0)', r['g'] == [1] and near(r['mv'], 1.0, 1e-9), r)

        # ───────────────── H. 시그니처 유물 「공원 야간 순찰」
        sgk = """const far=(k)=>{const e=x.spawnEnemy(0,2.5,null,{x:p.x+300,y:p.y+200});e.hp=e.mhp=5;if(k==='el')e.el=1;if(k==='bg')e.bg=1;return e;};Math.random=()=>.99;
            const kill=k=>{if(k==='boss'){const b=y.spawnBoss('mao');b.x=p.x+300;b.y=p.y+200;b.hp=1;b.mhp=1e9;x.hurt(b,1e9);}else x.hurt(far(k),1e9);};"""
        for lv, gain in [(1, 2), (2, 3), (3, 4)]:
            r = await pg.evaluate("(a)=>{" + PRE + sgk + """kill('el');const a1=y.csS().bg||0;kill('bg');const a2=y.csS().bg||0;S.t+=2.1;kill('el');const a3=y.csS().bg||0;S.t+=2.1;kill('boss');const a4=y.csS().bg||0;return {a1,a2,a3,a4}}""", {'L': 1, 'rel': {'sg_pty': lv}, 'es': []})
            need = 6
            check('유물 Lv%d: 정예 +%d칸 · 2초 안의 대형은 안 쌓임 · 2초 뒤 정예 또 +%d · 보스도 +%d(상한 %d)' % (lv, gain, gain, gain, need), r['a1'] == gain and r['a2'] == gain and r['a3'] == min(need, 2 * gain) and r['a4'] == min(need, 3 * gain), r)
        r = await pg.evaluate("(a)=>{" + PRE + sgk + """kill('el');kill('bg');S.t+=3;kill('n');return {a:y.csS().bg||0}}""", {'L': 1, 'rel': {}, 'es': []})
        check('유물이 없으면 정예·대형을 잡아도 게이지는 그대로(전리품만 떨어진다)', r['a'] == 0, r)
        r = await pg.evaluate("(a)=>{" + PRE + sgk + """kill('n');kill('n');kill('n');return {a:y.csS().bg||0}}""", {'L': 1, 'rel': {'sg_pty': 3}, 'es': []})
        check('유물은 일반 몹 처치로는 안 찬다', r['a'] == 0, r)
        r = await pg.evaluate("""()=>{const x=__p6x;Math.random=window.__rnd0;x.CH_set('pty');x.start();const S=x.S;S.lv=40;S.rel={};const ofr=[];for(let i=0;i<600;i++){for(const c of x.offers(3))if(c.t==="rl"&&c.r==="sg_pty")ofr.push(1);}
            x.CH_set('brj');x.start();const S2=x.S;S2.lv=40;const of2=[];for(let i=0;i<600;i++){for(const c of x.offers(3))if(c.t==="rl"&&c.r==="sg_pty")of2.push(1);}return {pty:ofr.length,brj:of2.length}}""")
        check('유물 후보: 팬티도둑에겐 나오고(600번 중 1번 이상) 다른 캐릭터(브장신)에겐 안 나온다', r['pty'] >= 1 and r['brj'] == 0, r)

        # ───────────────── I. 풀 상한 · 이어하기
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;Math.random=window.__rnd0;x.CH_set('pty');x.start();const S=x.S;S.w={panty:8};S.ev={panty:1};S.tier={panty:5};S.ps={amt:3,area:5,cd:5,dur:5,mag:5};x.tkCalc();S.t=900;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          let errs=0,mx=0,pl=0,ln=0;for(let i=0;i<1800;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
            try{x.update(1/30);}catch(e){errs++;if(errs<2)return {err:String(e),st:e.stack.slice(0,300)};}
            mx=Math.max(mx,S.x3.f.length);pl=Math.max(pl,S.x3.f.filter(o=>o.k==='pl').length);ln=Math.max(ln,S.x3.f.filter(o=>o.k==='ln').length);}
          return {errs,mx,pl,ln,kills:S.kills,dm:S.dmgBy.panty}}""")
        check('Lv8 + 각성 + 5단계 + 곱빼기 3 + 광역·끈기·획득 5 에서 60초: 예외 없음 · 풀 100 이하 · 전리품 12 이하 · 빨랫줄 3 이하', r.get('errs') == 0 and r['mx'] <= 100 and r['pl'] <= 12 and r['ln'] <= 3 and r['dm'] > 0, r)
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;Math.random=window.__rnd0;x.CH_set('pty');x.start();const S=x.S;S.w={panty:8};S.ev={panty:1};S.tier={panty:5};S.ps={mag:5};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          for(let i=0;i<420;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;x.keys={KeyD:true};x.update(1/30);}
          const kinds=()=>{const o={};for(const q of S.x3.f)o[q.k]=(o[q.k]||0)+1;return o};const k0=kinds(),bg0=y.csS().bg||0,kl0=S.kills;
          let b;try{b=y.RES.build();}catch(e){return {err:'build '+e}}
          if(!b||!b.text)return {err:'no text',b:Object.keys(b||{})};
          x.state='title';let ok;try{ok=y.RES.restore(b.text);}catch(e){return {err:'restore '+e}}
          const S2=x.S,k1=(()=>{const o={};for(const q of S2.x3.f)o[q.k]=(o[q.k]||0)+1;return o})();
          let errs=0;for(let i=0;i<200;i++){S2.p.hp=S2.p.mhp;try{x.update(1/30);}catch(e){errs++;}}
          return {ok:!!ok,k0,k1,bg0,bg1:(S2.x3.cs&&S2.x3.cs.bg)||0,errs,kl:S2.kills>=kl0,mhp:S2.p.mhp}}""")
        check('이어하기: 전리품·팬티·빨랫줄·보따리 게이지가 저장→복구 뒤 그대로 · 복구한 판이 계속 돈다', r.get('ok') and r['k0'] == r['k1'] and r['bg0'] == r['bg1'] and r['errs'] == 0 and r['kl'], r)

        # ───────────────── J. 화면 · 해금(412×860)
        r = await pg.evaluate("""()=>{const x=__p6x;x.srvUnl([]);x.show('title');x.renderRoster();const bs=[...document.querySelectorAll('#roster button')];const b=bs.find(e=>e.textContent.includes('맨해라공원팬티도둑'));
          b&&b.click();return {sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,small:b&&b.querySelector('small').textContent,lock:b&&b.classList.contains('lock'),desc:document.getElementById('chDesc').textContent,n:bs.length,hs:bs.map(e=>Math.round(e.getBoundingClientRect().width)),emoji:b&&b.querySelector('.e')&&b.querySelector('.e').textContent,img:!!(b&&b.querySelector('img'))}}""")
        check('선택 화면(412px): 가로 스크롤 없음 · 카드 폭이 모두 같다', r['sw'] <= r['cw'] and len(set(r['hs'])) == 1, (r['sw'], r['cw'], set(r['hs'])))
        check('잠긴 카드: 작은 글씨 「디스코드 /흐접새우상점 200P」 · 누르면 설명창에 구매 방법 + 로그인 안내 · 그림 대신 이모지 카드', r['lock'] and r['small'] == '디스코드 /흐접새우상점 200P' and '디스코드 「/흐접새우상점」에서 200P(내전 1판 1P · 맛동산 아님)로 구매 — 산 뒤 이 화면을 새로고침' in r['desc'] and '디스코드 로그인 필요' in r['desc'] and not r['img'], r)
        hw = await pg.evaluate("()=>document.querySelector('ol.how').textContent")
        check('조작법 도움말(❔): 고유 시작 무기 목록에 「팬티도둑 🧺」(배불배불 다음)', '배불배불 🎤 · 팬티도둑 🧺 · 신림 📋' in hw, hw[hw.find('고유 시작 무기'):][:160])
        await pg.evaluate("__p6x.srvUnl(['brj','pty'])")
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
        TILE = """()=>{const x=__p6x;document.getElementById('homeBtn').click();const b=[...document.querySelectorAll('#roster button')].find(e=>e.textContent.includes('맨해라공원팬티도둑'));const c=x.CHARS.find(c=>c.k==='pty');
          const can=x.canPick(c,x.getProg());const o={lock:b.classList.contains('lock'),small:b.querySelector('small').textContent,can,unl:[...x.SRVUNL]};b.click();o.desc=document.getElementById('chDesc').textContent;o.sel=x.CH.k;
          x.CH_set('pty');x.start();o.started=x.CH.k;o.weap=Object.keys(x.S.w);o.hp=x.S.p.mhp;return o}"""
        c_, p_, e_ = await open_page(['brj'], login=False)
        r = await p_.evaluate(TILE)
        check('(가) 로그아웃: 카드 잠김 · 설명 「디스코드 로그인 필요」 + 구매 방법 · 못 고르고 시작해도 브장신', r['lock'] and not r['can'] and r['small'] == '디스코드 /흐접새우상점 200P' and '디스코드 로그인 필요' in r['desc'] and '/흐접새우상점' in r['desc'] and r['sel'] == 'brj' and r['started'] == 'brj' and 'panty' not in r['weap'], r)
        check('(가) 페이지 오류·콘솔 에러 없음', not e_, e_[:3]); await c_.close()
        c_, p_, e_ = await open_page(['brj'])
        r = await p_.evaluate(TILE)
        check('(나) 로그인 + 미구매: 잠김 · 설명 「구매하면 열려요」 · 못 고르고 시작해도 브장신', r['lock'] and not r['can'] and '구매하면 열려요' in r['desc'] and r['sel'] == 'brj' and r['started'] == 'brj' and 'panty' not in r['weap'], r)
        await c_.close()
        c_, p_, e_ = await open_page(['brj'], local="localStorage.setItem('p6_unl_v1',JSON.stringify(['brj','pty','yumi','eom']));localStorage.setItem('p6_char_v1','pty');localStorage.setItem('p6_prog_v1',JSON.stringify({kills:99999,deaths:99,maxLv:60,best:4000,bossKill:5,w5:{},bk:{}}));")
        r = await p_.evaluate(TILE)
        await p_.reload(); await p_.wait_for_function('window.__p6x!==undefined'); await p_.wait_for_timeout(500)
        ch0 = await p_.evaluate("()=>__p6x.CH.k")
        check('(다) 로컬 저장소에 pty(해금 목록·선택·처치 99,999)를 써넣어도 잠김 · 시작해도 브장신 · 새로 열어도 브장신으로 시작', r['lock'] and not r['can'] and r['sel'] == 'brj' and r['started'] == 'brj' and ch0 == 'brj', (r, ch0))
        await c_.close()
        c_, p_, e_ = await open_page(['brj', 'pty'])
        r = await p_.evaluate(TILE)
        loc = await p_.evaluate("()=>JSON.parse(localStorage.getItem('p6_unl_v1')||'[]')")
        check('(라) 서버 unlocks 에 pty: 카드 열림(글씨 = 태그) · 고르면 pty · 시작하면 pty + 고유 무기 panty + 체력 84', not r['lock'] and r['can'] and r['small'] == '디스코드 /흐접새우상점 200P' and r['sel'] == 'pty' and r['started'] == 'pty' and r['weap'] == ['panty'] and r['hp'] == 84 and 'pty' in r['unl'], r)
        check('(라) 구매한 키는 로컬 해금 목록(p6_unl_v1)에 쌓지 않는다', 'pty' not in loc and 'brj' in loc, loc)
        await p_.evaluate("()=>{localStorage.setItem('p6_unl_v1',JSON.stringify(['brj','pty','bbb','yumi','eom','jjg']));const x=__p6x;x.CH_set('pty');x.start();x.S.t=120;x.S.kills=50;x.endRun(false,true)}"); await p_.wait_for_timeout(700)
        check('(마) 기록 POST: ch === "pty" 로 올라가되 unlocks 에는 상점 키(pty·bbb·yumi·eom)가 없다(진행도 키 brj·jjg 는 그대로)', len(POSTS) == 1 and POSTS[0].get('ch') == 'pty' and all(k not in POSTS[0].get('unlocks', []) for k in ('pty', 'bbb', 'yumi', 'eom')) and 'brj' in POSTS[0]['unlocks'] and 'jjg' in POSTS[0]['unlocks'], POSTS)
        r = await p_.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();x.S.kills=9;x.endRun(false,true);return {msg:document.getElementById('unlockMsg').textContent}}""")
        check('(바) 판 끝 해금 알림에 팬티도둑이 뜨지 않는다(진행도로는 안 열린다)', '팬티도둑' not in r['msg'] and '맨해라' not in r['msg'], r)
        check('(라)(마)(바) 페이지 오류·콘솔 에러 없음', not e_, e_[:3]); await c_.close()
        c_, p_, e_ = await open_page(['brj'])
        ST['unl'] = ['brj', 'pty']
        await p_.evaluate("()=>{const x=__p6x;x.CH_set('brj');x.start();x.S.t=120;x.S.kills=50;x.endRun(false,true)}"); await p_.wait_for_timeout(700)
        r = await p_.evaluate(TILE)
        check('(사) 기록 응답의 unlocks 에 pty 가 오면(그사이 구매) 카드가 열린다', not r['lock'] and r['can'] and r['started'] == 'pty', r)
        await c_.close()

        # ───────────────── K. 그리기(LOW · 비 LOW) · 소리 · 색
        r = await pg.evaluate("""()=>{const x=__p6x;Math.random=window.__rnd0;x.CH_set('pty');x.start();const S=x.S;S.w={panty:8};S.ev={panty:1};S.tier={panty:5};S.ps={amt:3,area:5,cd:5,mag:5};x.tkCalc();S.t=60;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          let errs=0,mx=0,py=0,pl=0,ln=0;for(let i=0;i<900;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
            try{x.update(1/30);if(i%2===0)x.draw();}catch(e){errs++;if(errs<2)return {err:String(e),st:e.stack.slice(0,300)};}
            mx=Math.max(mx,S.x3.f.length);for(const o of S.x3.f){if(o.k==='py')py++;if(o.k==='pl')pl++;if(o.k==='ln')ln++;}}
          return {errs,mx,py,pl,ln,LOW:x.LOW}}""")
        check('LOW 모드 그리기 30초: 예외 없음 · 풀 100 이하 · 팬티·전리품·빨랫줄이 실제로 그려지는 장면', r.get('errs') == 0 and r['mx'] <= 100 and r['py'] > 0 and r['pl'] > 0 and r['ln'] > 0, r)
        ctx3 = await b.new_context(viewport={'width': 1280, 'height': 800}); await ctx3.add_init_script("Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>8})")
        e3 = []
        async def rt3(rt):
            if rt.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await rt.continue_()
            else: await rt.abort()
        await ctx3.route('**/*', rt3)
        pg3 = await ctx3.new_page(); pg3.on('pageerror', lambda e: e3.append(str(e)))
        await pg3.goto('http://127.0.0.1:%d/survivors_x.html' % srv.port); await pg3.wait_for_function('window.__p6x!==undefined')
        await pg3.evaluate("window.__rnd0=Math.random;__p6x.srvUnl(['brj','pty'])")
        r = await pg3.evaluate("""()=>{const x=__p6x;Math.random=window.__rnd0;x.CH_set('pty');x.start();const S=x.S;S.w={panty:8};S.ev={panty:1};S.tier={panty:5};S.ps={amt:3,area:5,cd:5};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          let errs=0;for(let i=0;i<600;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];try{x.update(1/30);x.draw();}catch(e){errs++;if(errs<2)return {err:String(e)};}}
          return {errs,LOW:x.LOW}}""")
        check('비 LOW(데스크톱) 모드 그리기 20초: 예외 없음', r.get('errs') == 0 and r['LOW'] is False and not e3, (r, e3[:2]))
        await ctx3.close()
        r = await pg.evaluate("""async()=>{const x=__p6x,y=__p6y,A=y.AU;x.state='title';try{A.init();}catch(e){return {err:String(e)}}await new Promise(r=>setTimeout(r,300));if(A.state!=='running')return {skip:A.state};
          let errs=0;for(const [k,a] of [['panty',0],['panty',1],['ptyg',0]]){try{A.play(k,a);}catch(e){errs++;}await new Promise(r=>setTimeout(r,120));}return {errs,n:3}}""")
        if r.get('skip'): print('SKIP 효과음(오디오 상태 %s)' % r['skip'])
        else: check('효과음 panty(던지기 · 폭죽) · ptyg(줍기): 예외 없이 재생', r.get('errs') == 0 and r.get('n') == 3, r)
        # 정적 검사: 새 그리기·스프라이트에 위험색 없음 · 무적 부여 없음 · 새 S 키 없음
        def seg(a, bb):
            i = src.find(a); j = src.find(bb, i + 1) if i >= 0 else -1
            return src[i:j] if i >= 0 and j > i else ''
        segs = {
            '함수': seg('const ptyNeed=', 'function weapons3'),
            '무기 블록': seg('// 🧺 팬티 투척 → 🧵 빨랫줄 대잔치 — 가장 가까운 적에게', '// ── 엔티티 갱신'),
            '엔티티 갱신': seg("      case 'py':{o.x+=o.vx*dt", "      case 'bs':{o.life-=dt;"),
            '그리기': seg("      case 'py':{if(!inV", "      case 'nt':{if(!inV"),
            'SPX 팬티': seg('const pantyS=', "  // 🚀 [속도]"),
            'EX 링': seg('o.panty=function', '  // 🎰 전설'),
            '몸': seg('function ptyBody', 'function drawMap'),
        }
        check('정적 검사 구간을 모두 찾았다(구현이 달라 못 찾으면 이 시험의 구간 표식을 구현에 맞게 고칠 것)', all(len(v) > 50 for v in segs.values()), {k: len(v) for k, v in segs.items()})
        check('팬티 블록·전리품·줄·폭죽에 invGrant(무적 부여)가 없다', all('invGrant' not in segs[k] for k in ('함수', '무기 블록', '엔티티 갱신')), '')
        bad = []
        def hue_bad(r_, g_, b_):
            mx, mn = max(r_, g_, b_), min(r_, g_, b_)
            if mx < 100 or mx == 0: return False
            if (mx - mn) / mx < .28: return False
            if mx == r_: h = (60 * ((g_ - b_) / (mx - mn)) + 360) % 360
            elif mx == g_: h = 60 * ((b_ - r_) / (mx - mn)) + 120
            else: h = 60 * ((r_ - g_) / (mx - mn)) + 240
            return h <= 70 or h >= 290
        def colors_in(s_):
            out = []
            for m in re.finditer(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s_): out.append(tuple(int(m.group(i)) for i in (1, 2, 3)))
            for m in re.finditer(r"#([0-9a-fA-F]{6})\b", s_):
                h_ = m.group(1); out.append((int(h_[0:2], 16), int(h_[2:4], 16), int(h_[4:6], 16)))
            return out
        for k, s_ in segs.items():
            for cl in colors_in(s_):
                if hue_bad(*cl): bad.append((k, cl))
        check('팬티·줄·몸·링의 색에 위험색(빨강·주황·자홍·금색)이 없다(전리품의 금빛 후광은 기존 gpk 스프라이트)', not bad, bad[:6])
        check('위험 표시 팔레트(PAL.dz*)·적 구슬 스프라이트를 안 쓴다', all('PAL.dz' not in s_ and 'SPX.eo' not in s_ and 'SPX.dzf' not in s_ for s_ in segs.values()), '')
        check('음향 표: GAP·SPAM 에 panty · ptyg 가 있다', re.search(r"panty:90,ptyg:60\}", src) and re.search(r"panty:1,ptyg:1\}", src) is not None, '')
        check('새 S 키·최상위 let 을 만들지 않았다(이어하기 서명 불변: 상태는 S.x3.cs.bg · S.x3.f 엔티티뿐)', not re.search(r"^let\s+\w*(pty|panty)", src, re.M) and not re.search(r"(?<![A-Za-z])S\.(pty|panty)\b", src) and 'makeS' in src and 'bg:0' not in seg('function makeS', 'function newRun'), '')
        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        await b.close()
    srv.close()
    print('\n통과 %d / %d' % (N[0] - len(FAILS), N[0]))
    if FAILS:
        print('실패:'); [print(' -', f) for f in FAILS]
        sys.exit(1)
asyncio.run(main())
