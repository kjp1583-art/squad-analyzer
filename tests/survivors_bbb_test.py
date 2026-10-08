# -*- coding: utf-8 -*-
"""🎤 신캐릭터 「플레이브 코스프레 배불배불」(bbb) + 고유 무기 「플레이브 노래부르기」(sing) 검증 (2026-10-08 사장님 지시).
사용: python3 tests/survivors_bbb_test.py      (종료코드 0 = 전부 통과)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅(__p6x · __p6y)을 꽂는다.
구성: A 데이터 · B 박 시간표 · C 겨냥(집중·나선·재겨냥·고음 목표) · D 크레셴도 · E 넋 잃음·울림·끝 울림 · F 각성·단계표 · G 풀 상한·필드 아이템 ·
      H 규칙(새 적 필드 없음·무적 없음·색) · I 화면·해금 · J 패시브 · K 위력(아레나) · L 그리기·소리"""
import asyncio, sys, os, re, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
H.HOOK += "\nwindow.__p6y={U3,F3CAP,AU,PASS,SPX,EX,TK,aim3,liveOk,spawnBoss};\n"   # 이 시험만 쓰는 훅(sv_harness.py 는 고치지 않는다)
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)
def near(a, b, tol): return a is not None and abs(a - b) <= tol

# ── 장면: 가만히 선 적들 앞에서 무기 하나만 돌린다. 새로 생긴 엔티티(음표 nt · 고음 hn)를 시각·각도와 함께 기록한다
SCENE = r"""(a)=>{const x=__p6x,y=__p6y;x.CH_set(a.ch||'brj');x.start();const S=x.S,p=S.p,dt=a.dt||1/60;
 S.w=Object.assign({sing:a.L},a.w||{});S.cd={};S.ev=a.ev?{sing:1}:{};S.tier=a.tier?{sing:a.tier}:{};S.ps=a.ps||{};x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();
 const E=[];for(const o of a.es){const ex=p.x+Math.cos(o.a*Math.PI/180)*o.d,ey=p.y+Math.sin(o.a*Math.PI/180)*o.d;
   let e;if(o.boss){e=y.spawnBoss('mao');}else e=x.spawnEnemy(0,2.5,null,{x:ex,y:ey});
   e.x=ex;e.y=ey;e.sp=0;e.hp=e.mhp=o.hp||1e9;if(o.el)e.el=1;if(o.r)e.r=o.r;E.push({e,x:ex,y:ey,hp:o.hp||1e9,pin:o.pin!==false});}
 if(a.props)for(const o of a.props){let q=null;for(const c of x.props.a)if(!c.on){q=c;break;}q.on=true;q.k=1;q.x=p.x+o.x;q.y=p.y+o.y;q.hp=22;q.hit=0;}
 const log=[],seen=new WeakSet(),vid=new Map(),hits={};let cd0,maxSlow=0,slowLog=[],dm=[],f0=null,prevN=[];const steps=Math.round(a.sec/dt);
 for(let i=0;i<steps;i++){S.p.hp=S.p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys={};
   for(const q of E){if(!q.pin)continue;q.e.x=q.x;q.e.y=q.y;q.e.hp=q.e.mhp=q.hp;if(!a.keepSlow)q.e.slow=0;}
   if(a.kill&&i*dt>=a.kill.t&&E[a.kill.i].e.on){E[a.kill.i].e.on=false;}
   if(a.pre){S.x3.f.length=0;for(let j=0;j<a.pre;j++)S.x3.f.push({k:'sh',x:1e9,y:1e9,R:0,life:50,T:50,big:0});a.pre=0;}
   x.update(dt);
   if(cd0===undefined&&S.cd.sing>0)cd0=S.cd.sing;
   {const cur=new Set(S.x3.f);for(const o of prevN)if(!cur.has(o)&&o.life>0&&o.v&&vid.has(o.v)){const vi=vid.get(o.v);hits[vi]=(hits[vi]||0)+1;}   // 맞고 사라진 음표 수(관통 0 일 때만 정확) — 소절별
    for(const o of S.x3.f)if(o.k==='nt'&&o.v&&!vid.has(o.v))vid.set(o.v,vid.size);prevN=S.x3.f.filter(o=>o.k==='nt');}
   for(const o of S.x3.f){if(seen.has(o))continue;seen.add(o);
     if(o.k==='nt'||o.k==='hn'){let v=-1;if(o.v){if(!vid.has(o.v))vid.set(o.v,vid.size);v=vid.get(o.v);}
       log.push({t:+(i*dt).toFixed(4),k:o.k,deg:Math.atan2(o.vy,o.vx)*180/Math.PI,x:o.x,y:o.y,d:o.d,pc:o.pc,cr:o.cr,R:o.R,bt:o.bt,sl:o.sl,life:o.life,v,fr:o.fr,nd:o.nd,sp:Math.hypot(o.vx,o.vy),n:S.x3.f.length,vk:vid.size-1,hh:hits[vid.size-1]||0});}}
   if(a.slowIdx!==undefined){const q=E[a.slowIdx].e;slowLog.push([+(i*dt).toFixed(3),+q.slow.toFixed(3)]);}
   dm.push(S.dmgBy.sing||0);}
 return {log,cd0,slowLog,dm,dmg:S.dmgBy.sing||0,len:S.x3.f.length,props:x.props.a.filter(o=>o.on).length,invPk:S.invPk};}"""

def mean(v): return sum(v) / len(v)
def cmean(v):
    """각도(도)의 원형 평균 — ±180° 근처에서도 맞다."""
    return math.degrees(math.atan2(sum(math.sin(math.radians(a)) for a in v), sum(math.cos(math.radians(a)) for a in v)))
def groups(log, kind='nt', gap=.06):
    """같은 박(거의 같은 시각)에 생긴 음표끼리 묶는다."""
    out = []
    for e in sorted([e for e in log if e['k'] == kind], key=lambda e: e['t']):
        if out and e['t'] - out[-1][-1]['t'] <= gap: out[-1].append(e)
        else: out.append([e])
    return out
def wrap(d):
    while d > 180: d -= 360
    while d < -180: d += 360
    return d
def angd(a, b): return abs(wrap(a - b))

# 적 배치: A 0° 120px(가장 가까움) · B 100° 150px · C 250°(=-110°) 180px(가장 센 적)
ES3 = [{'a': 0, 'd': 120}, {'a': 100, 'd': 150}, {'a': 250, 'd': 180, 'hp': 5e9}]
DL = math.degrees(.06)   # 집중 때 2·3박 비껴 쏘는 각(3.44°)

ARENA = r"""(a)=>{const x=__p6x;let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 x.CH_set('brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w={sing:a.L};S.cd={};S.ev=a.ev?{sing:1}:{};S.tier=a.tier?{sing:a.tier}:{};S.ps={};x.tkCalc();x.synCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 const fill=()=>{let c=0;for(const q of x.enemies.a)if(q.on)c++;for(;c<45;c++){const g=Math.random()*6.2832,r=140+Math.random()*280;if(!x.spawnEnemy((Math.random()*3)|0,2.5,null,{x:p.x+Math.cos(g)*r,y:p.y+Math.sin(g)*r}))break;}};
 const step=()=>{if(x.state==='lvup'){x.pick(x.CUR[0]);return;}if(x.state!=='play'){x.resume();return;}
   S.p.hp=S.p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];fill();x.update(dt);x.props.clear();};
 const W=Math.round((3+8*Math.random())/dt);for(let i=0;i<W;i++)step();S.dmgBy={};for(let i=0;i<300;i++)step();
 return {d:S.dmgBy.sing||0,state:x.state};}"""
# 아레나 기준표(10초 누적 피해 · 무기만 · 시드 평균) — 설계 시제품 실측. 기존 고유 무기 15종(카트 제외) 중앙값은 ref15
BASE = {'L1': 359, 'L2': 427, 'L3': 541, 'L4': 612, 'L5': 776, 'L6': 1036, 'L7': 1121, 'L8': 1554, 'M3': 1882, 'EV': 2906, 'EV5': 3826}
REF15 = {'L1': 389, 'L2': 425, 'L3': 508, 'L4': 566, 'L5': 709, 'L6': 929, 'L7': 1106, 'L8': 1451, 'M3': 1974, 'EV': 2525, 'EV5': 4057}

def hue_bad(r, g, b):
    """위험색(빨강·주황·자홍·금색) 대역인가 — 채도·밝기가 낮은 색(흰색·연한 파스텔)은 통과."""
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 100 or mx == 0: return False
    sat = (mx - mn) / mx
    if sat < .28: return False
    if mx == r: h = (60 * ((g - b) / (mx - mn)) + 360) % 360
    elif mx == g: h = 60 * ((b - r) / (mx - mn)) + 120
    else: h = 60 * ((r - g) / (mx - mn)) + 240
    return h <= 70 or h >= 290
def colors_in(src):
    out = []
    for m in re.finditer(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", src): out.append(tuple(int(m.group(i)) for i in (1, 2, 3)))
    for m in re.finditer(r"#([0-9a-fA-F]{6})\b", src):
        h = m.group(1); out.append((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
    return out

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()   # SV_SRC: 다른 사본(변형)으로 돌려 보고 싶을 때
    src = open(os.path.join(H.ROOT, 'survivors_x.html'), encoding='utf-8').read()
    async with async_playwright() as p:
        b = await H.launch(p, args=['--autoplay-policy=no-user-gesture-required'])
        ctx, pg, errs = await H.new_page(b, srv.port)
        # ───────────────── A. 데이터
        r = await pg.evaluate("""()=>{const x=__p6x,y=__p6y;const c=x.CHARS.find(c=>c.k==='bbb'),w=x.WEAP.sing,T=x.TIERS.sing,sy=x.SYN.find(s=>s.k==='u_sing'),i=x.CHARS.findIndex(c=>c.k==='bbb');
          const names=x.CHARS.map(c=>c.k);
          return {c:c&&{w:c.w,cdr:c.cdr,img:c.img,sn:c.sn,nm:c.nm,q:c.q,ds:c.ds,tag:c.tag,boss:!!c.boss,shop:!!c.shop,t:c.un&&c.un.t,ok0:c.un.ok({kills:19999}),ok1:c.un.ok({kills:20000}),pr:c.un.pr({kills:4321}),pr2:c.un.pr({kills:99999}),wl:c.wl||1},
            order:names.slice(names.indexOf('psg'),names.indexOf('psg')+3),
            w:w&&{only:w.only,pair:w.pair,pairOk:!!y.PASS[w.pair],ds:w.ds.length,evnm:w.ev&&w.ev.nm,evic:w.ev&&w.ev.ic,ic:w.ic,nm:w.nm,rl:w.rl},
            T:T&&T.map(t=>t[1]),Ttx:T&&T.map(t=>t[0]),sy:sy&&{req:sy.req,fx:sy.fx,nm:sy.nm},
            u3:y.U3.sing,syn:x.SYN.length,uSyn:x.SYN.filter(s=>s.k.startsWith('u_')).length,
            chick:!!x.WEAP.chick&&!x.WEAP.chick.only,sg:x.SYN.filter(s=>s.k==='u_sing').length,
            bbbPair:Object.keys(x.WEAP).filter(k=>x.WEAP[k].pair==='study')}}""")
        c = r['c']
        check('CHARS bbb: 고유 무기 sing · 쿨타임 -8%(cdr) · 그림(img) · 짧은 이름', c and c['w'] == 'sing' and c['wl'] == 1 and c['cdr'] == .08 and c['img'] == 1 and c['sn'] == '배불배불' and c['nm'] == '플레이브 코스프레 배불배불' and not c['boss'] and not c['shop'], c)
        check('CHARS bbb: 설명에 고유 무기 · 한 줄 대사 · 태그', c and '고유 무기' in c['ds'] and '쿨타임 -8%' in c['ds'] and c['q'] and c['tag'], c)
        check('해금: 처치 누적 20,000 — 19,999 거짓 · 20,000 참 · 문구', c and c['ok0'] is False and c['ok1'] is True and c['t'] == '처치 누적 20,000' and '4,321/20,000' in c['pr'] and '20,000/20,000' in c['pr2'], c)
        check('선택 화면 순서: 프싱 다음 배불배불(클랜원 구역)', r['order'][:2] == ['psg', 'bbb'], r['order'])
        w = r['w']
        check('WEAP.sing: only bbb · 짝 패시브 study(실제 패시브) · 8줄 · 각성 「앙코르 무대」', w and w['only'] == 'bbb' and w['pair'] == 'study' and w['pairOk'] and w['ds'] == 8 and w['evnm'] == '앙코르 무대' and w['evic'] == '🎶' and w['ic'] == '🎤' and w['nm'] == '플레이브 노래부르기', w)
        T = r['T']
        check('TIERS.sing: 마스터 3 + 각성 2 (음표 +1 · 피해 +12% · 쿨 -7% · 관통/피해/넋 · 흩어지는 음표)', T == [{'n': 1}, {'d': .12}, {'c': .07}, {'pc': 1, 'd': .08, 'life': .2}, {'frag': 1}], T)
        check('콤보 u_sing: 🎤 + 🐥 병아리 친구들(공용) · 경험치 +10% · 피해 +6%', r['sy'] and r['sy']['req'] == ['sing', 'chick'] and r['sy']['fx'] == {'xp': .1, 'dmg': .06} and r['chick'] and r['sg'] == 1 and r['uSyn'] == 17, r['sy'])
        check('U3.sing 수치표', r['u3'] == {'d': 4.5, 'db': 1.3, 'cd': 1.6, 'iv': .24, 'sp': 380, 'life': .8, 'rng': 300, 'fan': .22, 'dlt': .06, 'hit': 12, 'bsp': 280, 'blife': .9, 'bR': 44, 'btk': .45, 'm': 2, 'cr': .04, 'crm': .6, 'sl': .45, 'bsl': .9, 'reach': 280}, r['u3'])
        check('study 짝 무기: 가챠 · 4발 사격 · 노래부르기', sorted(r['bbbPair']) == ['gacha', 'jhin', 'sing'], r['bbbPair'])

        # ───────────────── B. 박 시간표
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': ES3, 'sec': 3.4})
        L = r['log']; g = groups(L); t0 = g[0][0]['t']
        notes = [x for x in g if len(x)]
        check('Lv1: 첫 프레임에 1박 — 음표 2개(박마다 2개)', len(g[0]) == 2 and near(t0, 1 / 60, .02), (len(g[0]), t0))
        check('Lv1: 2·3박 음표가 박자 간격 .24초 뒤 · .48초 뒤', len(g) >= 3 and near(g[1][0]['t'] - t0, .24, .04) and near(g[2][0]['t'] - t0, .48, .04) and len(g[1]) == 2 and len(g[2]) == 2, [(len(x), round(x[0]['t'] - t0, 3)) for x in g[:4]])
        hn = [e for e in L if e['k'] == 'hn']
        check('Lv1: 4박(.72초)에 고음 ♬ 하나', len(hn) >= 1 and near(hn[0]['t'] - t0, .72, .04), [round(e['t'] - t0, 3) for e in hn])
        check('Lv1: 음표 피해 4.5 · 고음 피해 = 1.3 × 크레셴도 · 수명 .8 · 속도 380', near(g[1][0]['d'], 4.5, .01) and near(hn[0]['d'] / hn[0]['cr'], 1.3, .01) and near(g[1][0]['life'], .8, .02) and near(g[1][0]['sp'], 380, 1) and g[1][0]['pc'] == 0, (g[1][0], hn[0]))
        v1 = [x for x in g if x[0]['t'] - t0 > 1.2]
        check('다음 소절은 쿨타임 1.6초 뒤', len(v1) >= 1 and near(v1[0][0]['t'] - t0, 1.6, .05) and near(r['cd0'], 1.6, .001), (r['cd0'], v1 and v1[0][0]['t'] - t0))
        # 레벨별 박당 음표 수 · 박자 간격 · 쿨타임 · 관통 · 고음 규격
        EXP_M = [2, 3, 3, 3, 3, 3, 4, 4]; EXP_IV = [.24, .24, .24, .204, .204, .204, .204, .204]; EXP_CD = [1.6, 1.6, 1.6, 1.44, 1.44, 1.44, 1.44, 1.296]
        EXP_D = [4.5, 4.5, 6.075, 6.075, 8.2013, 8.2013, 8.2013, 8.2013]; EXP_DB = [1.3, 1.3, 1.755, 1.755, 2.3693, 2.3693, 2.3693, 2.3693]
        for Lv in range(1, 9):
            r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': Lv, 'es': ES3, 'sec': 1.0})
            g = groups(r['log']); t0 = g[0][0]['t']; hn = [e for e in r['log'] if e['k'] == 'hn'][0]
            ok = (len(g[0]) == EXP_M[Lv - 1] and len(g[1]) == EXP_M[Lv - 1] and near(g[1][0]['t'] - t0, EXP_IV[Lv - 1], .04) and near(r['cd0'], EXP_CD[Lv - 1], .002)
                  and near(g[1][0]['d'], EXP_D[Lv - 1], .01) and near(hn['d'] / hn['cr'], EXP_DB[Lv - 1], .01) and g[1][0]['pc'] == (1 if Lv >= 8 else 0)
                  and near(hn['bt'], .2925 if Lv >= 6 else .45, .001) and near(g[1][0]['life'], .92 if Lv >= 6 else .8, .02) and near(g[1][0]['sl'], .75 if Lv >= 8 else .45, .001)
                  and near(hn['R'] / (1 + (hn['cr'] - 1) * .4), 55 if Lv >= 6 else 44, .01))
            check('Lv%d: 박당 음표 %d · 박자 %.3f · 쿨타임 %.3f · ♪ %.3f · ♬ %.3f · 관통 · 울림 간격·반지름·넋 잃음 단계' % (Lv, EXP_M[Lv - 1], EXP_IV[Lv - 1], EXP_CD[Lv - 1], EXP_D[Lv - 1], EXP_DB[Lv - 1]), ok,
                  (len(g[0]), len(g[1]), round(g[1][0]['t'] - t0, 3), r['cd0'], g[1][0]['d'], hn['d'] / hn['cr'], g[1][0]['pc'], hn['bt'], g[1][0]['sl'], hn['R'], hn['cr']))
        # 곱빼기(amt 3) + 마스터 1(음표 +1) → 상한 6 · 곱빼기만 → 5
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': ES3, 'sec': .5, 'ps': {'amt': 3}, 'tier': 1})
        check('음표는 박당 최대 6개(Lv8 + 곱빼기 3 + 마스터 +1)', len(groups(r['log'])[0]) == 6, len(groups(r['log'])[0]))
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': ES3, 'sec': .5, 'ps': {'amt': 3}})
        check('곱빼기 3 → Lv1 박당 5개', len(groups(r['log'])[0]) == 5, len(groups(r['log'])[0]))

        # ───────────────── C. 겨냥
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': ES3, 'sec': 3.4})
        g = groups(r['log']); hn = [e for e in r['log'] if e['k'] == 'hn']
        m = [cmean([e['deg'] for e in x]) for x in g[:3]]
        check('Lv1(집중): 세 박 모두 가장 가까운 적(0°) — 2박 +3.4° · 3박 -3.4°', near(m[0], 0, 1.5) and near(m[1], DL, 1.5) and near(m[2], -DL, 1.5), [round(v, 1) for v in m])
        check('고음 ♬ 은 가장 센 적(250°=-110°) 쪽으로', angd(hn[0]['deg'], -110) < 2.5, hn[0]['deg'])
        v2 = [x for x in g if x[0]['t'] - g[0][0]['t'] > 1.2]
        m2 = [cmean([e['deg'] for e in x]) for x in v2[:3]]
        check('다음 소절은 비껴 쏘는 방향이 반대(2박 -3.4° · 3박 +3.4°)', len(m2) == 3 and near(m2[0], 0, 1.5) and near(m2[1], -DL, 1.5) and near(m2[2], DL, 1.5), [round(v, 1) for v in m2])
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 4, 'es': ES3, 'sec': 3.2})
        g = groups(r['log']); hn = [e for e in r['log'] if e['k'] == 'hn']; t0 = g[0][0]['t']
        m = [cmean([e['deg'] for e in x]) for x in g[:3]]
        check('Lv4(나선) 첫 소절: 가까운 적(0°) → 100° → 250°(-110°) 순서로 돌며 겨냥', near(m[0], 0, 1.5) and near(m[1], 100, 2) and near(wrap(m[2] + 110), 0, 2), [round(v, 1) for v in m])
        v2 = [x for x in g if x[0]['t'] - t0 > 1.2]
        m2 = [cmean([e['deg'] for e in x]) for x in v2[:3]]
        check('Lv4 다음 소절은 반대로 돈다: 0° → 250° → 100°', len(m2) == 3 and near(m2[0], 0, 1.5) and near(wrap(m2[1] + 110), 0, 2) and near(m2[2], 100, 2), [round(v, 1) for v in m2])
        check('Lv4: 박자 간격 .204 · ♬ 은 가장 센 적(-110°)', near(g[1][0]['t'] - t0, .204, .04) and angd(hn[0]['deg'], -110) < 2.5, (g[1][0]['t'] - t0, hn[0]['deg']))
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 4, 'es': ES3[:2], 'sec': 1.0})
        m = [cmean([e['deg'] for e in x]) for x in groups(r['log'])[:3]]
        check('Lv4 적이 둘뿐이면 3박은 가장 가까운 적을 다시(비껴)', near(m[0], 0, 1.5) and near(m[1], 100, 2) and near(m[2], -DL, 1.5), [round(v, 1) for v in m])
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 4, 'es': ES3[:1], 'sec': 1.0})
        m = [cmean([e['deg'] for e in x]) for x in groups(r['log'])[:3]]
        check('Lv4 적이 하나뿐이면 나선 대신 집중(0° · +3.4° · -3.4°)', near(m[0], 0, 1.5) and near(m[1], DL, 1.5) and near(m[2], -DL, 1.5), [round(v, 1) for v in m])
        # 겨눈 적이 박 사이에 죽으면 그 순간 가장 가까운 적으로 바꾼다
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 120}, {'a': 180, 'd': 250}], 'sec': 1.0, 'kill': {'t': .1, 'i': 0}})
        m = [cmean([e['deg'] for e in x]) for x in groups(r['log'])[:3]]
        check('겨눈 적이 죽으면 다음 박은 가장 가까운 적(180°)으로', near(m[0], 0, 1.5) and angd(m[1], 180 + DL) < 2.5 and angd(m[2], 180 - DL) < 2.5, [round(v, 1) for v in m])
        # ♬ 목표: 보스 > 엘리트·대형 > 현재 체력 · 사거리(280) 밖은 제외
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 100, 'hp': 100}, {'a': 90, 'd': 200, 'hp': 50, 'el': 1}, {'a': 200, 'd': 250, 'hp': 1e6}], 'sec': 1.0})
        hn = [e for e in r['log'] if e['k'] == 'hn']
        check('♬ 목표: 엘리트(90°)가 체력 많은 일반 적(200°)보다 먼저', hn and angd(hn[0]['deg'], 90) < 2.5, hn and hn[0]['deg'])
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 100, 'hp': 100}, {'a': 90, 'd': 200, 'hp': 50, 'el': 1}, {'a': 300, 'd': 220, 'boss': 1}], 'sec': 1.0})
        hn = [e for e in r['log'] if e['k'] == 'hn']
        check('♬ 목표: 보스(300°=-60°)가 엘리트보다 먼저', hn and angd(hn[0]['deg'], -60) < 2.5, hn and hn[0]['deg'])
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 100, 'hp': 100}, {'a': 180, 'd': 290, 'hp': 1e9}], 'sec': 1.0})
        hn = [e for e in r['log'] if e['k'] == 'hn']
        check('♬ 목표: 사거리(280) 밖의 센 적은 제외 → 가까운 적(0°)', hn and angd(hn[0]['deg'], 0) < 2.5, hn and hn[0]['deg'])

        # ───────────────── D. 크레셴도(박자 적중 보너스)
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 110}], 'sec': 5.0})
        L = r['log']; hns = [e for e in L if e['k'] == 'hn']
        ok = len(hns) >= 3; ex = []
        for i, h in enumerate(hns[:3]):
            ex.append((h['hh'], round((h['cr'] - 1) / .04, 2)))
            ok = ok and near(h['cr'], 1 + min(.6, .04 * h['hh']), 1e-6) and h['hh'] >= 2
        check('♬ 크레셴도 = 1 + min(0.6, 0.04 × 그 소절에서 맞은 ♪ 수) — 소절마다 새로 센다(앞 소절 것을 이어받지 않는다)', ok, ex)
        check('첫 소절 크레셴도는 4박 때까지 맞은 음표 수(4~6개) × 0.04', 4 <= hns[0]['hh'] <= 6 and near(hns[0]['cr'], 1 + .04 * hns[0]['hh'], 1e-6), (hns[0]['hh'], hns[0]['cr']))
        r8 = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': [{'a': 0, 'd': 110}, {'a': 100, 'd': 120}, {'a': 250, 'd': 130}], 'sec': 6.0, 'ev': 1, 'tier': 5})
        h8 = [e for e in r8['log'] if e['k'] == 'hn']
        check('각성(소절이 겹쳐도) 모든 ♬ 에 크레셴도가 붙는다(소절마다 따로 센다)', len(h8) >= 5 and all(h['cr'] > 1.0 for h in h8), [h['cr'] for h in h8])
        check('크레셴도가 클수록 ♬ 반지름도 커진다(상승분의 40%)', all(near(h['R'], 44 * 1.25 * 1.15 * (1 + (h['cr'] - 1) * .4), .01) for h in h8), [(h['cr'], h['R']) for h in h8[:3]])

        # ───────────────── E. 넋 잃음 · 울림 · 끝 울림 · 보스
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 120}], 'sec': .68, 'keepSlow': True, 'slowIdx': 0})
        ms = max(v for t, v in r['slowLog'])
        check('♪ 에 맞으면 넋 잃음(느려짐) .45초(Lv1)', near(ms, .45, .03), ms)
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': [{'a': 0, 'd': 120}], 'sec': .5, 'keepSlow': True, 'slowIdx': 0})
        ms = max(v for t, v in r['slowLog'])
        check('Lv8 넋 잃음 +0.3초 → .75초', near(ms, .75, .03), ms)
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': [{'a': 0, 'd': 120}], 'sec': .5, 'keepSlow': True, 'slowIdx': 0, 'tier': 4})
        ms = max(v for t, v in r['slowLog'])
        check('마스터 4단계 넋 잃음 +0.2초 → .95초', near(ms, .95, .03), ms)
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 120, 'boss': 1}], 'sec': .68, 'keepSlow': True, 'slowIdx': 0})
        ms = max(v for t, v in r['slowLog'])
        check('보스는 넋 잃음이 절반(.225)', near(ms, .225, .03), ms)
        # 끝 울림 — ♬ 이 가는 끝자리(252px)에 서 있는 적만 끝 울림(반지름 ×1.3 · 피해 ×1.5)에 맞는다
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 250}], 'sec': 1.75})
        dm = r['dm']; dts = [round(dm[i] - dm[i - 1], 3) for i in range(1, len(dm))]
        hn = [e for e in r['log'] if e['k'] == 'hn'][0]
        odd = [(round(i / 60, 2), d) for i, d in enumerate(dts, 1) if d > 0 and not near(d / 4.5, round(d / 4.5), .004)]
        check('끝 울림: ♬ 이 끝(수명 .9초)에서 한 번 — 피해 = 1.3 × 크레셴도 × 1.5(보통 울림은 안 닿는 자리)', len(odd) == 1 and near(odd[0][1], 1.3 * hn['cr'] * 1.5, .01) and near(odd[0][0] - hn['t'], .9, .06), (odd, hn['cr'], hn['t']))
        # 보통 울림 — 가는 길 위(126px 근처)의 적은 .45초 지점 울림에 맞는다
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 130}], 'sec': 1.75})
        dm = r['dm']; dts = [round(dm[i] - dm[i - 1], 3) for i in range(1, len(dm))]
        hn = [e for e in r['log'] if e['k'] == 'hn'][0]
        odd = [(round(i / 60 - hn['t'], 2), d) for i, d in enumerate(dts, 1) if d > 0 and not near(d / 4.5, round(d / 4.5), .004) and i / 60 > hn['t']]
        check('울림은 ♬ 이 0.45초 날아간 자리(≈126px)에서 한 번 — 피해 = 1.3 × 크레셴도', len(odd) >= 1 and near(odd[0][0], .45, .07) and near(odd[0][1], 1.3 * hn['cr'], .01), (odd, hn['cr']))

        # ───────────────── F. 각성 · 단계표 · 앙코르
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': ES3, 'sec': 3.0, 'ev': 1})
        L = r['log']; g = groups(L); hn = [e for e in L if e['k'] == 'hn']; t0 = g[0][0]['t']
        vs = {}
        for e in L:
            if e['k'] == 'nt': vs.setdefault(e['v'], []).append(e)
        order = sorted(vs.values(), key=lambda v: v[0]['t'])
        enc = order[1]
        check('각성: 앙코르 소절이 첫 소절 시작 4박자(.816초) 뒤에 시작', near(enc[0]['t'] - t0, 4 * .204, .05), enc[0]['t'] - t0)
        check('각성: 앙코르 피해는 75% · 첫 소절 ♪ 피해 = 8.2013 × 1.15', near(order[0][0]['d'], 8.2013 * 1.15, .02) and near(enc[0]['d'], 8.2013 * 1.15 * .75, .02), (order[0][0]['d'], enc[0]['d']))
        eg = groups(enc)[:3]
        me = [cmean([e['deg'] for e in x]) for x in eg]
        check('각성: 앙코르 소절은 앞 소절의 반대로 돈다(0° → 250° → 100°)', len(me) == 3 and near(me[0], 0, 2) and near(wrap(me[1] + 110), 0, 2) and near(me[2], 100, 2), [round(v, 1) for v in me])
        check('각성: ♬ 반지름 ×1.15 · 피해 ×1.15 · 쿨타임 ×.9(1.296 × .9 = 1.1664)', near(hn[0]['R'] / (1 + (hn[0]['cr'] - 1) * .4), 55 * 1.15, .02) and near(hn[0]['d'] / hn[0]['cr'], 2.3693 * 1.15, .01) and near(r['cd0'], 1.1664, .002), (hn[0], r['cd0']))
        # 단계표
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': ES3, 'sec': .5, 'tier': 1})
        check('마스터1 음표 +1 → 박당 5개', len(groups(r['log'])[0]) == 5, len(groups(r['log'])[0]))
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': ES3, 'sec': .5, 'tier': 2})
        check('마스터2 피해 +12% (+ 음표 +1 은 이미 있음)', near(groups(r['log'])[1][0]['d'], 8.2013 * 1.12, .02), groups(r['log'])[1][0]['d'])
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': ES3, 'sec': .5, 'tier': 3})
        check('마스터3 쿨타임 -7% → 1.296 × .93', near(r['cd0'], 1.296 * .93, .002), r['cd0'])
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 4, 'es': ES3, 'sec': .5, 'tier': 4, 'ev': 1})
        n4 = groups(r['log'])[1][0]
        check('각성4 음표 관통 +1 · 피해 +8%(마스터2 +12% 와 합쳐 +20%) · 넋 잃음 +0.2초', n4['pc'] == 1 and near(n4['d'], 6.075 * 1.15 * 1.2, .02) and near(n4['sl'], .65, .001), n4)
        # 각성5 — 끝 울림에서 음표 6개(피해 50%)가 사방으로, 크레셴도에는 안 센다
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 250}], 'sec': 1.8, 'ev': 0, 'tier': 5})
        fr = [e for e in r['log'] if e['k'] == 'nt' and e['v'] == -1]
        nd = groups(r['log'])[0][0]['d']
        check('각성5 흩어지는 음표 6개 · 피해 50% · 속도 300 · 수명 .42 · 소절에 안 센다(v 없음)', len(fr) == 6 and all(near(e['d'], nd * .5, .02) and near(e['sp'], 300, 1) for e in fr), (len(fr), fr[:1], nd))
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': [{'a': 0, 'd': 250}], 'sec': 1.8})
        check('각성5 아니면 흩어지는 음표 없음', not [e for e in r['log'] if e['k'] == 'nt' and e['v'] == -1], '')

        # ───────────────── G. 풀 상한 · 필드 아이템
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': ES3, 'sec': .9, 'pre': 95})
        nts = [e for e in r['log'] if e['k'] == 'nt']; hns = [e for e in r['log'] if e['k'] == 'hn']
        check('풀이 95/100 이면 음표는 건너뛰고(앞 8칸은 ♬ 몫) 고음 ♬ 은 나온다', len(nts) == 0 and len(hns) >= 1, (len(nts), len(hns)))
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': ES3 + [{'a': 40, 'd': 90}, {'a': 160, 'd': 100}, {'a': 300, 'd': 110}], 'sec': 12, 'ev': 1, 'tier': 5, 'ps': {'amt': 3, 'cd': 5, 'pspd': 5, 'area': 5}, 'dt': 1 / 30})
        check('Lv8 + 각성 + 5단계 + 곱빼기 3 + 속사 5 + 쿨타임 5 에서도 풀 100 이하 · 예외 없음', r['len'] <= 100 and max(e['n'] for e in r['log']) <= 100, (r['len'], max(e['n'] for e in r['log'])))
        r = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 8, 'es': [], 'props': [{'x': 140, 'y': 0}], 'sec': 6})
        check('적 없이 필드 아이템만 있어도 소절이 나가 깬다(음표 · 고음)', r['props'] == 0, r['props'])

        # ───────────────── H. 규칙
        ctx5, pg5, e5 = await H.new_page(b, srv.port)   # 새 페이지 — 적 풀 객체에 앞 장면이 남긴 필드가 없도록
        r = await pg5.evaluate("""()=>{const x=__p6x;const run=(ch,w)=>{x.CH_set(ch);x.start();const S=x.S;S.w={[w]:8};S.ev={[w]:1};S.tier={[w]:5};x.tkCalc();S.t=200;
            for(let i=0;i<600;i++){S.p.hp=S.p.mhp;if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}x.update(1/30);}
            const ks=new Set();for(const e of x.enemies.a)if(e.ki!==undefined)for(const k of Object.keys(e))ks.add(k);return {keys:[...ks].sort().join(','),kills:S.kills};};
          const a=run('brj','quill'),b=run('bbb','sing');return {same:a.keys===b.keys,a:a.keys,b:b.keys,kills:b.kills}}""")
        check('새 적 필드를 만들지 않는다(20초 판 뒤 적 객체의 키가 기존 무기 판과 같다)', r['same'] and r['kills'] > 0, r)
        rv = await pg5.evaluate(SCENE, {'ch': 'bbb', 'L': 8, 'es': ES3, 'sec': 8, 'ev': 1, 'tier': 5})   # 적이 멀리 서 있어 맞을 일이 없다 → 무적 시간이 생기면 이 무기 탓
        check('무적을 주지 않는다(맞을 일 없는 장면에서 S.invPk = 0)', rv['invPk'] == 0 and rv['dmg'] > 0, (rv['invPk'], rv['dmg']))
        await ctx5.close()
        def seg(a, bb):
            i = src.find(a); j = src.find(bb, i + 1) if i >= 0 else -1
            return src[i:j] if i >= 0 and j > i else ''
        segs = {
            '무기 블록': seg('// 🎤 플레이브 노래부르기 → 🎶 앙코르 무대', '// ── 엔티티 갱신'),
            'singPulse': seg('function singPulse', 'function weapons3'),
            '엔티티 갱신': seg("      case 'nt':{o.x+=o.vx*dt", "      case 'sn':{o.life-=dt;"),
            '그리기': seg("      case 'nt':{if(!inV", "      case 'sn':{if(!inV"),
            'SPX 음표': seg('const noteS=', "  // 🚀 [속도]"),
            'EX 링': seg('o.sing=function', '  // 🎰 전설'),
        }
        check('정적 검사 구간을 모두 찾았다(구현이 달라 못 찾으면 이 시험의 구간 표식을 구현에 맞게 고칠 것)', all(len(v) > 50 for v in segs.values()), {k: len(v) for k, v in segs.items()})
        check('노래 블록·울림·엔티티 갱신에 invGrant(무적 부여)가 없다', all('invGrant' not in segs[k] for k in ('무기 블록', 'singPulse', '엔티티 갱신')), '')
        bad = []
        for k, s in segs.items():
            for cl in colors_in(s):
                if hue_bad(*cl): bad.append((k, cl))
        check('노래 그리기·스프라이트·링의 색에 위험색(빨강·주황·자홍·금색)이 없다', not bad, bad[:6])
        check('위험 표시 팔레트(PAL.dz*)·적 구슬 스프라이트를 안 쓴다', all('PAL.dz' not in s and 'SPX.eo' not in s and 'SPX.dzf' not in s for s in segs.values()), '')

        # ───────────────── J. 패시브 「박자 감각」 쿨타임 -8%
        r1 = await pg.evaluate(SCENE, {'ch': 'bbb', 'L': 1, 'es': ES3, 'sec': .1})
        r0 = await pg.evaluate(SCENE, {'ch': 'brj', 'L': 1, 'es': ES3, 'sec': .1})
        check('bbb 는 노래 쿨타임 1.6 × .92 = 1.472 (브장신은 1.6)', near(r1['cd0'], 1.472, .002) and near(r0['cd0'], 1.6, .002), (r1['cd0'], r0['cd0']))
        r = await pg.evaluate("""()=>{const x=__p6x;const out={};for(const ch of ['bbb','brj']){x.CH_set(ch);x.start();const S=x.S;S.w={feed:1};S.cd={};S.t=60;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
            for(const q of x.enemies.a)q.on=false;x.spawnEnemy(0,2.5,null,{x:S.p.x+80,y:S.p.y});for(let i=0;i<4&&!(S.cd.feed>0.3);i++){S.p.hp=S.p.mhp;x.update(1/60);}out[ch]=S.cd.feed;}return out}""")
        check('패시브는 모든 무기에 적용(사료 투척 쿨 .7 → .644)', near(r['bbb'], .644, .01) and near(r['brj'], .7, .01), r)

        # ───────────────── I. 화면 · 해금(412×860)
        r = await pg.evaluate("""()=>{const x=__p6x;x.show('title');x.renderRoster();const bs=[...document.querySelectorAll('#roster button')];const b=bs.find(e=>e.textContent.includes('배불배불'));
          b&&b.click();return {sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,small:b&&b.querySelector('small').textContent,lock:b&&b.classList.contains('lock'),desc:document.getElementById('chDesc').textContent,n:bs.length,hs:bs.map(e=>Math.round(e.getBoundingClientRect().width))}}""")
        check('선택 화면(412px): 가로 스크롤 없음 · 카드 폭이 모두 같다', r['sw'] <= r['cw'] and len(set(r['hs'])) == 1, (r['sw'], r['cw'], set(r['hs'])))
        check('잠긴 카드: 작은 글씨 「처치 누적 20,000」 · 누르면 해금 문구 + 진행도', r['lock'] and r['small'] == '처치 누적 20,000' and '해금: 처치 누적 20,000' in r['desc'] and '0/20,000' in r['desc'], r)
        hw = await pg.evaluate("()=>document.querySelector('ol.how').textContent")
        check('조작법 도움말(❔): 고유 시작 무기 목록에 「배불배불 🎤」(프싱 다음)', '프싱 🔥 · 배불배불 🎤 · 신림 📋' in hw, hw[hw.find('고유 시작 무기'):][:140])
        r = await pg.evaluate("""()=>{const x=__p6x;const g=x.getProg();g.kills=19990;x.setProg(g);x.CH_set('brj');x.start();x.S.kills=9;x.endRun(false,true);const a={unl:[...JSON.parse(localStorage.getItem('p6_unl_v1')||'[]')],msg:document.getElementById('unlockMsg').textContent};
          const g2=x.getProg();a.kills=g2.kills;x.start();x.S.kills=20;x.endRun(false,true);a.unl2=[...JSON.parse(localStorage.getItem('p6_unl_v1')||'[]')];a.msg2=document.getElementById('unlockMsg').textContent;
          a.can=x.canPick(x.CHARS.find(c=>c.k==='bbb'),x.getProg());return a}""")
        check('19,999 → 처치 누적이 20,000 을 넘으면 결과 화면에 새 캐릭터 해금 문구 + 로컬 해금 목록에 bbb', 'bbb' not in r['unl'] and r['kills'] == 19999 and 'bbb' in r['unl2'] and '플레이브 코스프레 배불배불' in r['msg2'] and r['can'], r)
        # 기록 전송: 판을 bbb 로 마치면 body.ch === 'bbb'
        POSTS = []
        async def mock(rt):
            u = rt.request.url; hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
            if rt.request.method == 'OPTIONS': await rt.fulfill(status=204, headers=hdr); return
            if '/p6/run' in u:
                POSTS.append(json.loads(rt.request.post_data or '{}')); await rt.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'rank': 1, 'total': 1, 'unlocks': ['brj', 'bbb'], 'best_t': 10}))
            else: await rt.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'name': 'T', 'unlocks': ['brj'], 'board': [], 'hard': [], 'vhard': []}))
        ctx2, pg2, errs2 = await H.new_page(b, srv.port, mock=mock)
        await pg2.evaluate("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))")
        await pg2.reload(); await pg2.wait_for_function('window.__p6x!==undefined'); await pg2.wait_for_timeout(300)
        await pg2.evaluate("()=>{const x=__p6x;x.CH_set('bbb');x.start();x.S.t=120;x.S.kills=50;x.endRun(false,true)}"); await pg2.wait_for_timeout(600)
        check('기록 전송 body.ch === "bbb"', len(POSTS) == 1 and POSTS[0].get('ch') == 'bbb', POSTS)
        await ctx2.close()

        # ───────────────── L. 그리기(LOW · 비 LOW) · 소리
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('bbb');x.start();const S=x.S;S.w={sing:8};S.ev={sing:1};S.tier={sing:5};S.ps={amt:3,area:5,cd:5};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          let errs=0,mx=0,hn=0,nt=0;for(let i=0;i<900;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
            try{x.update(1/30);if(i%2===0)x.draw();}catch(e){errs++;if(errs<2)return {err:String(e),st:e.stack.slice(0,300)};}
            mx=Math.max(mx,S.x3.f.length);for(const o of S.x3.f){if(o.k==='hn')hn++;if(o.k==='nt')nt++;}}
          return {errs,mx,hn,nt,LOW:x.LOW}}""")
        check('LOW 모드 그리기 30초: 예외 없음 · 풀 100 이하 · 음표·고음이 실제로 그려지는 장면', r.get('errs') == 0 and r['mx'] <= 100 and r['hn'] > 0 and r['nt'] > 0, r)
        ctx3 = await b.new_context(viewport={'width': 1280, 'height': 800}); await ctx3.add_init_script("Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>8})")
        e3 = []
        async def rt3(rt):
            if rt.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await rt.continue_()
            else: await rt.abort()
        await ctx3.route('**/*', rt3)
        pg3 = await ctx3.new_page(); pg3.on('pageerror', lambda e: e3.append(str(e)))
        await pg3.goto('http://127.0.0.1:%d/survivors_x.html' % srv.port); await pg3.wait_for_function('window.__p6x!==undefined')
        r = await pg3.evaluate("""()=>{const x=__p6x;x.CH_set('bbb');x.start();const S=x.S;S.w={sing:8};S.ev={sing:1};S.tier={sing:5};S.ps={amt:3,area:5,cd:5};x.tkCalc();S.t=300;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;
          let errs=0;for(let i=0;i<600;i++){S.p.hp=S.p.mhp;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];try{x.update(1/30);x.draw();}catch(e){errs++;if(errs<2)return {err:String(e)};}}
          return {errs,LOW:x.LOW}}""")
        check('비 LOW(데스크톱) 모드 그리기 20초: 예외 없음', r.get('errs') == 0 and r['LOW'] is False and not e3, (r, e3[:2]))
        await ctx3.close()
        r = await pg.evaluate("""async()=>{const x=__p6x,y=__p6y,A=y.AU;x.state='title';try{A.init();}catch(e){return {err:String(e)}}await new Promise(r=>setTimeout(r,300));if(A.state!=='running')return {skip:A.state};
          const n0=(A.n.sing||0);let errs=0;for(const a of [0,1,2,3,10,11,12,13,20,21,22,23]){try{A.play('sing',a);}catch(e){errs++;}await new Promise(r=>setTimeout(r,90));}
          return {n:(A.n.sing||0)-n0,errs}}""")
        if r.get('skip'): print('SKIP 소리 시험(오디오 컨텍스트가 running 이 아님: %s)' % r['skip'])
        else: check('효과음 sing: 박 12가지(가락 3 × 박 4) 예외 없이 재생', r.get('errs') == 0 and r.get('n') == 12, r)   # 소리 간격(GAP 60ms)보다 길게 쉬며 부른다
        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])

        # ───────────────── M. 보스 상자 각성 경로(실제 openChest) · 레벨업 카드
        r = await pg.evaluate("""()=>{const x=__p6x;const out={};
          x.CH_set('bbb');x.start();let S=x.S;S.w={sing:8};S.ps={};S.ev={};S.tier={};x.tkCalc();x.openChest();out.noPair=!!S.ev.sing;out.noPairTxt=document.getElementById('chestList').textContent.includes('앙코르 무대');
          x.CH_set('bbb');x.start();S=x.S;S.w={sing:7};S.ps={study:1};S.ev={};S.tier={};x.tkCalc();x.openChest();out.notLv8=!!S.ev.sing;
          x.CH_set('bbb');x.start();S=x.S;S.w={sing:8};S.ps={study:1};S.ev={};S.tier={};x.tkCalc();x.openChest();
          out.ev=S.ev.sing;out.txt=document.getElementById('chestList').textContent;out.st=x.state;
          let seenSing=0;x.CH_set('bbb');x.start();S=x.S;S.lv=10;S.w={sing:3};for(let i=0;i<200;i++)for(const o of x.offers(3))if(o.t==='w'&&o.k==='sing'){seenSing++;}
          return {...out,seenSing}}""")
        check('보스 상자: 노래 Lv8 + 📚 공부 → 🎶 앙코르 무대로 각성(짝 패시브가 없거나 Lv7 이면 각성 안 함)', r['ev'] and r['st'] == 'chest' and '앙코르 무대' in r['txt'] and not r['noPair'] and not r['noPairTxt'] and not r['notLv8'], r)
        check('배불배불은 레벨업 카드에서 노래 강화 카드를 받을 수 있다(고유 무기 주인 · 카드 200번 뽑아 최소 5번)', r['seenSing'] >= 5, r['seenSing'])

        # ───────────────── K. 위력(아레나: 적 45마리 · 무기만 · 시드 평균 · 기존 고유 무기 표와 같은 방식)
        ctx4, pg4, e4 = await H.new_page(b, srv.port)
        res = {}
        modes = [('L%d' % i, i, 0, 0) for i in range(1, 9)] + [('M3', 8, 0, 3), ('EV', 8, 1, 0), ('EV5', 8, 1, 5)]
        for nm, Lv, ev, tier in modes:
            v = []
            for sd in range(1, 21):
                o = await pg4.evaluate(ARENA, {'L': Lv, 'ev': ev, 'tier': tier, 'seed': sd}); v.append(o['d'])
            res[nm] = round(mean(v), 1)
        print('아레나(20시드 평균):', res, flush=True)
        check('아레나 위력: 11개 상태 모두 설계 시제품 실측의 ±15% 안', all(abs(res[k] / BASE[k] - 1) <= .15 for k in BASE), {k: round(res[k] / BASE[k], 2) for k in BASE})
        check('아레나 위력: 기존 고유 무기 15종(카트 제외) 중앙값의 0.80~1.25배', all(.80 <= res[k] / REF15[k] <= 1.25 for k in REF15), {k: round(res[k] / REF15[k], 2) for k in REF15})
        seq = [res['L%d' % i] for i in range(1, 9)]
        check('레벨이 오를수록 세진다(Lv1<Lv2<…<Lv8 · 마스터 > Lv8 · 각성 > 마스터 · 각성5 > 각성)', all(seq[i] < seq[i + 1] for i in range(7)) and res['M3'] > res['L8'] and res['EV'] > res['M3'] and res['EV5'] > res['EV'], res)
        check('아레나 스크립트 오류 없음', not e4, e4[:3])
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('\n%d 개 중 실패 %d: %s' % (N[0], len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
