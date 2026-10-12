# -*- coding: utf-8 -*-
"""🍘 맛동산 투척 「관통 스틱 + 맞을 때마다 튀는 부스러기」 시험 — 2026-10-12 사장님 지시
   「맛동산장인유미의 1차투사체가 관통능력을 가지게끔, 1차투사체가 맞으면서 2차투사체가 왕창 튀어나오는 구조 (디아블로2 라이트닝 퓨리 같은)」
사용: python3 tests/survivors_snack_fury_test.py [--mutants] [--only 가,나,..]
  가  관통 — 일렬로 선 적: 스틱은 U3.snack.pierce 마리를 꿰뚫고 같은 적을 두 번 때리지 않는다 · 각성은 무제한
  나  방사 — 스틱이 맞을 때마다 부스러기가 정확히 K발(레벨·마스터·곱빼기·각성별 기대값) · 부스러기는 다시 튀지 않는다(1세대만) · 덩치 큰 적도 부스러기에 맞는다
  다  상한 — 최악의 판(각성·만렙·마스터·곱빼기·적 수백)에서도 떠 있는 부스러기 ≤ cap · 한 프레임 새로 만드는 수 ≤ frame · 풀(F3CAP)이 꽉 차도 안전
  라  숫자 묶기 — 설명문(WEAP.snack)의 숫자·마스터 문구가 U3 값과 맞고, 스틱 피해가 DLS 사다리를 따른다
  마  패시브 — 곱빼기=부스러기 +1/겹 · 속사=스틱·부스러기 속도 · 끈기=부스러기 수명 · 광역=부스러기 크기 (게임이 실제로 읽는 값)
  바  이어하기 — 날아가는 스틱·부스러기가 있는 판 저장→복구가 같다
  사  성능 — 최악 빌드의 프레임당 ms
  아  페이지 오류 0
  --mutants: 관통 제거 · 중복 방지 제거 · 상한 제거 ·  → 해당 단계가 빨갛게 되는지"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright

ROOT = H.ROOT
FAILS = []
ONLY = None
if '--only' in sys.argv: ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
MUT = '--mutants' in sys.argv
PERF = {}
def want(s): return ONLY is None or s in ONLY
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:700]) if (extra != '' and not cond) else ''), flush=True)
    if not cond: FAILS.append(name)

EXTRA = r"""
window.__sf={RES,F3CAP,DLS,DUR,AR_(){return 1+.1*pv('area')+.06*PTV('area')+.1*trn('wide')-.05*trn('gale')+S.syn.area},hl:null};
{const _h=hurt;hurt=function(e,d){if(window.__sf.hl)window.__sf.hl.push([SRC,d,e.sn]);return _h(e,d);};}
"""
SEED = r"""let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};"""
STAGE = r"""const x=__p6x,F=__sf;""" + SEED + r"""
 x.CH_set('brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w={snack:a.L};S.cd={};S.ev=a.ev?{snack:1}:{};S.tier=a.tier?{snack:a.tier}:{};S.ps=a.ps||{};x.tkCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();
 const U=x.U3.snack;
 const mk=(dx,dy,r)=>{const e=x.spawnEnemy(0,2.5,null,{x:p.x+dx,y:p.y+dy})||{};e.hp=e.mhp=1e12;e.sp=0;if(r)e.r=r;return e;};   // 풀이 꽉 차면 빈 객체(자리 채우기)
 const crumbs=()=>S.x3.f.filter(o=>o.k==='b'&&o.src==='snack');
"""

# 일렬 적(또는 몇 마리)을 향해 한 번 던지고 모든 피해·부스러기를 센다
LINE_JS = r"""(a)=>{""" + STAGE + r"""
 const es=[];for(let i=0;i<a.N;i++)es.push(mk(a.gap*(i+1)+(a.off||0),0,a.r||14));
 F.hl=[];let created=0,maxNew=0,thrown=0,sticks0=0;
 for(let i=0;i<a.frames;i++){for(const e of es){e.hp=e.mhp=1e12;}
   const before=new Set(S.x3.f);x.update(dt);S.p.hp=S.p.mhp;
   const nw=S.x3.f.filter(o=>!before.has(o));const nc=nw.filter(o=>o.k==='b'&&o.src==='snack').length;created+=nc;maxNew=Math.max(maxNew,nc);
   const sn=nw.filter(o=>o.k==='sn');if(sn.length&&!thrown){thrown=1;sticks0=sn.length;
     if(a.one){const v=Math.hypot(sn[0].vx,sn[0].vy);sn[0].vx=v;sn[0].vy=0;for(const q of sn.slice(1))S.x3.f.splice(S.x3.f.indexOf(q),1);}}   // a.one: 스틱 하나만 정면으로(여러 개면 부채꼴로 벌어진다)
   if(thrown&&!S.x3.f.some(o=>o.k==='sn')&&i>5)break;}
 const hits={};let stick=0;for(const h of F.hl){if(h[0]!=='snack')continue;if(Math.abs(h[1]-a.sd)<a.sd*.02){stick++;hits[h[2]]=(hits[h[2]]||0)+1;}}
 F.hl=null;
 return {sticks:sticks0,stickHits:stick,distinct:Object.keys(hits).length,maxPer:Math.max(0,...Object.values(hits)),created,maxNew};}"""

NOREPOP_JS = r"""(a)=>{""" + STAGE + r"""
 const e=mk(70,0,14);
 for(let i=0;i<40;i++){e.hp=e.mhp=1e12;x.update(dt);S.p.hp=S.p.mhp;}
 for(let i=0;i<30;i++){e.hp=e.mhp=1e12;e.x=1e6;x.update(dt);S.p.hp=S.p.mhp;}   // 적을 멀리 치우고 이미 던진 것들이 다 끝나게
 const sticks=S.x3.f.filter(o=>o.k==='sn').length;
 S.cd.snack=1e9;let nb=0;for(let i=0;i<30;i++){const n0=new Set(S.x3.f);x.update(dt);S.p.hp=S.p.mhp;nb+=S.x3.f.filter(o=>!n0.has(o)&&o.k==='b').length;}
 return {sticks,newAfter:nb};}"""

BOSS_JS = r"""(a)=>{""" + STAGE + r"""
 const e=mk(a.dist,0,a.r);F.hl=[];
 for(let i=0;i<36;i++){e.hp=e.mhp=1e12;x.update(dt);S.p.hp=S.p.mhp;}
 const sd=U.d,cr=U.d*U.kd;let stick=0,crumb=0;for(const h of F.hl){if(h[0]!=='snack')continue;if(Math.abs(h[1]-sd)<.2)stick++;else if(Math.abs(h[1]-cr)<.2)crumb++;}
 F.hl=null;return {stick,crumb};}"""

WORST_JS = r"""(a)=>{""" + STAGE + r"""
 const es=[];for(let i=0;i<a.N;i++){const g=Math.random()*6.2832,r=60+Math.random()*300;es.push(mk(Math.cos(g)*r,Math.sin(g)*r,12));}
 let maxAlive=0,maxNew=0,maxF3=0,total=0,err=null;
 if(a.fill)for(let i=0;i<a.fill;i++)S.x3.f.push({k:'tw',life:1e9,x:p.x+9999,y:p.y,len:0,ux:1,uy:0,T:1e9,side:0});
 try{for(let i=0;i<a.frames;i++){for(const e of es){e.hp=e.mhp=1e12;e.sp=0;}
   const before=new Set(S.x3.f);x.update(dt);S.p.hp=S.p.mhp;
   const nc=S.x3.f.filter(o=>!before.has(o)&&o.k==='b'&&o.src==='snack').length;total+=nc;maxNew=Math.max(maxNew,nc);
   maxAlive=Math.max(maxAlive,crumbs().length);maxF3=Math.max(maxF3,S.x3.f.length);}}catch(e){err=String(e);}
 return {maxAlive,maxNew,maxF3,total,err,cap:U.cap,frame:U.frame,F3CAP:F.F3CAP};}"""

FIRST_D_JS = r"""(a)=>{""" + STAGE + r"""
 const e=mk(90,0,14);F.hl=[];for(let i=0;i<40;i++){e.hp=e.mhp=1e12;x.update(dt);S.p.hp=S.p.mhp;}
 const first=F.hl.find(h=>h[0]==='snack');F.hl=null;return {d:first&&first[1]};}"""

PASSIVE_JS = r"""(a)=>{""" + STAGE + r"""
 S.cd.snack=0;const e=mk(110,0,16);const b0=new Set(S.x3.f);x.update(dt);const st=S.x3.f.filter(o=>!b0.has(o)&&o.k==='sn')[0];
 const out={ps:null,cs:null,cr:null,cl:null,K:null};
 if(st){out.ps=Math.hypot(st.vx,st.vy);out.cs=st.cs;out.cl=st.cl;out.cr=st.cr;out.K=st.m;}
 out.PS=x.PS();out.DUR=F.DUR();out.AR=F.AR_();return out;}"""

RESUME_JS = r"""(a)=>{""" + STAGE + r"""
 const es=[];for(let i=0;i<40;i++){const g=Math.random()*6.2832,r=70+Math.random()*250;es.push(mk(Math.cos(g)*r,Math.sin(g)*r,12));}
 for(let i=0;i<14;i++){for(const e of es){e.hp=e.mhp=1e12;e.sp=0;}x.update(dt);S.p.hp=S.p.mhp;}
 const snapOf=(Sx)=>{const idx=new Map();x.enemies.a.forEach((e,i)=>idx.set(e,i));
   return JSON.stringify(Sx.x3.f.filter(o=>o.k==='sn'||(o.k==='b'&&o.src==='snack')).map(o=>{const r={};for(const k of Object.keys(o).sort()){const v=o[k];r[k]=Array.isArray(v)?v.map(q=>idx.has(q)?'E'+idx.get(q):q):v;}return r;}));};
 const nS=S.x3.f.filter(o=>o.k==='sn').length,nB=S.x3.f.filter(o=>o.k==='b'&&o.src==='snack').length;
 const before=snapOf(S);
 const r=F.RES.build();if(!r.text)return {err:'build '+r.why,bad:r.bad};
 x.state='title';const ok=F.RES.restore(r.text);
 if(!ok)return {err:'restore false',why:F.RES.info.why};
 const after=snapOf(x.S);
 return {nS,nB,same:before===after,len:before.length};}"""

PERF_JS = r"""(a)=>{""" + STAGE + r"""
 const es=[];for(let i=0;i<a.N;i++){const g=Math.random()*6.2832,r=60+Math.random()*320;es.push(mk(Math.cos(g)*r,Math.sin(g)*r,12));}
 for(let i=0;i<a.warm;i++){for(const e of es){e.hp=e.mhp=1e12;e.sp=0;}x.update(dt);S.p.hp=S.p.mhp;}
 const U_=[],D_=[];for(let i=0;i<a.frames;i++){for(const e of es){e.hp=e.mhp=1e12;e.sp=0;}const t0=performance.now();x.update(dt);const t1=performance.now();x.draw();const t2=performance.now();U_.push(t1-t0);D_.push(t2-t1);S.p.hp=S.p.mhp;}
 const m=v=>v.reduce((a,b)=>a+b,0)/v.length,q=(v,p)=>{const s=[...v].sort((a,b)=>a-b);return s[Math.floor(s.length*p)];};
 return {upd:m(U_),drw:m(D_),p95:q(U_.map((u,i)=>u+D_[i]),.95),max:Math.max(...U_.map((u,i)=>u+D_[i]))};}"""

def dls(L): return (1.2 if L >= 3 else 1) * (1.2 if L >= 5 else 1) * (1.5 if L >= 8 else 1)

async def run_core(pg, U, tag=''):
    d0 = U['d']
    if want('가'):
        # 스틱이 1개인 Lv1 로 — 정면으로 날아간다
        o = await pg.evaluate(LINE_JS, {'L': 1, 'N': 6, 'gap': 60, 'r': 14, 'seed': 3, 'frames': 90, 'sd': d0})
        check(tag + '가 Lv1 일렬 6마리: 서로 다른 적 %d마리를 한 번씩 꿰뚫는다 (직접 피해 %d번 · 같은 적 최대 %d번)' % (U['pierce'], o['stickHits'], o['maxPer']),
              o['distinct'] == U['pierce'] and o['stickHits'] == U['pierce'] and o['maxPer'] == 1, o)
        o = await pg.evaluate(LINE_JS, {'L': 1, 'N': 3, 'gap': 60, 'r': 14, 'seed': 3, 'frames': 90, 'sd': d0})
        check(tag + '가 Lv1 일렬 3마리: 3마리 모두 한 번씩', o['distinct'] == 3 and o['stickHits'] == 3 and o['maxPer'] == 1, o)
        o = await pg.evaluate(LINE_JS, {'L': 1, 'ev': 1, 'one': 1, 'off': 60, 'N': 9, 'gap': 36, 'r': 14, 'seed': 3, 'frames': 90, 'sd': d0 * U['evD']})
        check(tag + '가 각성은 관통 무제한: 촘촘한 9마리 전부 한 번씩 (서로 다른 적 %d · 같은 적 최대 %d번)' % (o['distinct'], o['maxPer']), o['distinct'] == 9 and o['maxPer'] == 1, o)
    if want('나'):
        cases = [(L, 0, 0, {}) for L in range(1, 9)] + [(8, 0, 5, {}), (1, 0, 1, {}), (1, 0, 0, {'amt': 2}), (1, 1, 0, {}), (4, 0, 3, {'amt': 1})]
        for (L, ev, tier, ps) in cases:
            K = U['kL'][L - 1] + (1 if tier >= 1 else 0) + ps.get('amt', 0) + (U['evK'] if ev else 0)
            sd = d0 * dls(L) * (U['evD'] if ev else 1) * (1 + (.12 if tier >= 2 else 0))
            o = await pg.evaluate(LINE_JS, {'L': L, 'ev': ev, 'tier': tier, 'ps': ps, 'N': 3, 'gap': 70, 'r': 14, 'seed': 5, 'frames': 90, 'sd': sd})
            if tier >= 5 or ev:   # 끝에서 한 번 더 크게 — 맞을 때마다 K 에 끝 터짐이 더해진다(상한 안에서)
                ok = o['stickHits'] >= 1 and o['created'] >= o['stickHits'] * K and o['maxNew'] <= U['frame']
            else:
                ok = o['stickHits'] >= 1 and o['created'] == o['stickHits'] * K and o['maxNew'] <= U['frame']
            check(tag + '나 Lv%d%s%s%s: 맞을 때마다 부스러기 %d발 (맞은 수 %d → 만든 수 %d)' % (L, ' 각성' if ev else '', (' 마스터%d' % tier) if tier else '', (' 곱빼기%d' % ps['amt']) if ps.get('amt') else '', K, o['stickHits'], o['created']), ok, o)
        o = await pg.evaluate(NOREPOP_JS, {'L': 8, 'ev': 1, 'seed': 9})
        check(tag + '나 부스러기는 다시 튀지 않는다 (스틱이 다 끝난 뒤 새 부스러기 %d · 남은 스틱 %d)' % (o['newAfter'], o['sticks']), o['newAfter'] == 0 and o['sticks'] == 0, o)
        # 덩치 큰 적(보스 · 반지름 ≥ U3.big) 한 마리: 스틱은 한 번 · 속에서 터진 부스러기 K발이 모두 그 적을 때린다(관통 이득은 없어도 부스러기는 보스에게 맞는다) · 작은 적 한 마리는 K발을 넘지 않는다
        o = await pg.evaluate(BOSS_JS, {'L': 1, 'seed': 4, 'dist': 120, 'r': 50})
        check(tag + '나 덩치 큰 적 한 마리(반지름 50): 스틱 1번 · 부스러기 %d발 전부 맞는다 (스틱 %d · 부스러기 %d)' % (U['kL'][0], o['stick'], o['crumb']), o['stick'] == 1 and o['crumb'] == U['kL'][0], o)
        o = await pg.evaluate(BOSS_JS, {'L': 1, 'seed': 4, 'dist': 120, 'r': 14})
        check(tag + '나 작은 적 한 마리(반지름 14): 스틱 1번 · 부스러기는 K발 이하 (스틱 %d · 부스러기 %d)' % (o['stick'], o['crumb']), o['stick'] == 1 and o['crumb'] <= U['kL'][0], o)
    if want('다'):
        o = await pg.evaluate(WORST_JS, {'L': 8, 'ev': 1, 'tier': 5, 'ps': {'amt': 5, 'dur': 3, 'pspd': 3}, 'N': 200, 'seed': 2, 'frames': 240})
        check(tag + '다 최악 빌드(각성·Lv8·마스터5·곱빼기5·적 250마리 8초): 떠 있는 부스러기 최대 %d ≤ 상한 %d · 한 프레임 새로 %d ≤ %d · 오류 없음' % (o['maxAlive'], o['cap'], o['maxNew'], o['frame']),
              o['maxAlive'] <= o['cap'] and o['maxNew'] <= o['frame'] and not o['err'] and o['total'] > 100, o)
        o = await pg.evaluate(WORST_JS, {'L': 8, 'ev': 1, 'tier': 5, 'ps': {'amt': 5}, 'N': 200, 'seed': 2, 'frames': 120, 'fill': 70})
        check(tag + '다 풀에 다른 것 70개: 전체 %d ≤ F3CAP %d · 오류 없음' % (o['maxF3'], o['F3CAP']), o['maxF3'] <= o['F3CAP'] and not o['err'], o)
        o = await pg.evaluate(WORST_JS, {'L': 8, 'ev': 1, 'tier': 5, 'ps': {'amt': 5}, 'N': 200, 'seed': 2, 'frames': 120, 'fill': 100})
        check(tag + '다 풀이 꽉 참(100/100): 던지기·부스러기 생성이 조용히 실패하고 오류 없음', o['maxF3'] <= o['F3CAP'] and not o['err'], o)

async def main():
    H.make_copy(extra=EXTRA)
    srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        U = await pg.evaluate("()=>__p6x.U3.snack")
        print('U3.snack =', json.dumps(U))
        await run_core(pg, U)
        ws = await pg.evaluate("()=>__p6x.WEAP.snack"); tiers = await pg.evaluate("()=>__p6x.TIERS.snack")
        if want('라'):
            ds = ws['ds']
            check('라 설명문 8줄 · 마스터 5칸 (표 모양 불변)', len(ds) == 8 and len(tiers) == 5, (len(ds), len(tiers)))
            check('라 ds[0]: 관통 %d마리 · 부스러기 %d개가 U3 값' % (U['pierce'], U['kL'][0]), ('%d마리' % U['pierce']) in ds[0] and ('부스러기 %d개' % U['kL'][0]) in ds[0], ds[0])
            inc = [i for i in range(1, 8) if U['kL'][i] > U['kL'][i - 1]]
            check('라 부스러기 +1 이 오르는 레벨(%s)과 설명문 ds 가 같다' % [i + 1 for i in inc],
                  all(U['kL'][i] - U['kL'][i - 1] == 1 for i in inc) and set(i for i in range(1, 8) if '부스러기 +1' in ds[i]) == set(inc), [(i, ds[i]) for i in range(1, 8)])
            check('라 Lv1 %d발 → Lv8 %d발, 각성 덤 +%d 가 각성 설명에 적혀 있다' % (U['kL'][0], U['kL'][7], U['evK']), ('부스러기 +%d' % U['evK']) in ws['ev']['ds'], (U['kL'], ws['ev']['ds']))
            check('라 각성 설명: 관통 무제한 · 끝에서 크게 터진다 · 피해 %s배' % U['evD'], '관통 무제한' in ws['ev']['ds'] and '끝에서' in ws['ev']['ds'] and ('피해 %s배' % U['evD']) in ws['ev']['ds'] and ('부스러기 피해 %s배' % U['evKd']) in ws['ev']['ds'], ws['ev']['ds'])
            check('라 마스터 문구: 맞을 때마다 부스러기 +1 · 부스러기 관통 +1 · 끝에서 한 번 더 크게', '맞을 때마다' in tiers[0][0] and '관통' in tiers[3][0] and '끝에서' in tiers[4][0], [t[0] for t in tiers])
            check('라 역할 라벨이 새 구조(관통)를 말한다', '관통' in ws['rl'] and '유도' not in ws['rl'], ws['rl'])
            for L in (1, 3, 5, 8):
                o = await pg.evaluate(FIRST_D_JS, {'L': L, 'seed': 6})
                want_d = U['d'] * dls(L)
                check('라 Lv%d 스틱 직접 피해 %.2f = U3.d × 사다리 (%.2f)' % (L, o['d'] or -1, want_d), o['d'] is not None and abs(o['d'] - want_d) < want_d * .02, o)
        if want('마'):
            base = await pg.evaluate(PASSIVE_JS, {'L': 3, 'seed': 8})
            check('마 패시브 없음: 스틱 속도 %.0f=U3.sp(%d) · 부스러기 속도 %.0f · 수명 %.2f · 반지름 %.1f 가 U3 기본' % (base['ps'], U['sp'], base['cs'], base['cl'], base['cr']),
                  abs(base['ps'] - U['sp']) < 1 and abs(base['cs'] - U['cs']) < .5 and abs(base['cl'] - U['cl']) < .001 and abs(base['cr'] - U['cr']) < .001, base)
            amt = await pg.evaluate(PASSIVE_JS, {'L': 3, 'seed': 8, 'ps': {'amt': 3}})
            check('마 곱빼기 3겹: 맞을 때마다 부스러기 +3 (%d → %d)' % (base['K'], amt['K']), amt['K'] == base['K'] + 3, amt)
            sp = await pg.evaluate(PASSIVE_JS, {'L': 3, 'seed': 8, 'ps': {'pspd': 3}})
            check('마 속사 3겹: 스틱 속도 ×PS() · 부스러기 속도 ×PS() (PS=%.2f)' % sp['PS'], abs(sp['ps'] / base['ps'] - sp['PS']) < .01 and abs(sp['cs'] / base['cs'] - sp['PS']) < .01 and sp['PS'] > 1.3, sp)
            du = await pg.evaluate(PASSIVE_JS, {'L': 3, 'seed': 8, 'ps': {'dur': 3}})
            check('마 끈기 3겹: 부스러기 수명 ×DUR() (DUR=%.2f)' % du['DUR'], abs(du['cl'] / base['cl'] - du['DUR']) < .01 and du['DUR'] > 1.3, du)
            ar = await pg.evaluate(PASSIVE_JS, {'L': 3, 'seed': 8, 'ps': {'area': 3}})
            check('마 광역 3겹: 부스러기 반지름 ×AR (AR=%.2f)' % ar['AR'], abs(ar['cr'] / base['cr'] - ar['AR']) < .01 and ar['AR'] > 1.2, ar)
        if want('바'):
            for (L, ev, tier) in [(3, 0, 0), (8, 1, 5)]:
                o = await pg.evaluate(RESUME_JS, {'L': L, 'ev': ev, 'tier': tier, 'seed': 12})
                check('바 이어하기: 날아가는 스틱 %s · 부스러기 %s 가 저장→복구 뒤 똑같다 (Lv%d%s)' % (o.get('nS'), o.get('nB'), L, ' 각성' if ev else ''),
                      not o.get('err') and o['same'] and o['nS'] >= 1 and o['nB'] >= 1, o)
        if want('사'):
            for (name, cfg) in [('Lv8 각성 마스터5 곱빼기3 적 220', {'L': 8, 'ev': 1, 'tier': 5, 'ps': {'amt': 3}, 'N': 220}), ('Lv1 적 220', {'L': 1, 'N': 220})]:
                cfg.update({'seed': 21, 'warm': 60, 'frames': 240})
                o = await pg.evaluate(PERF_JS, cfg)
                print('  성능 %s: update %.2f ms + draw %.2f ms (합 p95 %.2f · 최대 %.2f)' % (name, o['upd'], o['drw'], o['p95'], o['max']))
        check('아 페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        await b.close()
    srv.close()

async def mutants():
    global ONLY
    src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    M = [('관통 제거', "o.ps=(o.ps===undefined?1:o.ps)-1;if(o.ps<=0){end=true;break;}", "end=true;break;", {'가'}),
         ('중복 방지 제거', "||hs.includes(e.sn))continue;", ")continue;", {'가'}),
         ('상한 제거', "const room=Math.min(U.cap-SNK.n,U.frame-SNK.f);", "const room=1e9;", {'다'}),
         ('맞을 때마다 두 번 튄다(방사 횟수 오류)', "snkPop(o,o.x,o.y,1);o.fl=.12;", "snkPop(o,o.x,o.y,1);snkPop(o,o.x,o.y,1);o.fl=.12;", {'나'})]
    srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for name, old, new, secs in M:
            assert src.count(old) == 1, (name, src.count(old))
            open(os.path.join(ROOT, 'survivors_sfm_src.html'), 'w', encoding='utf-8').write(src.replace(old, new))
            H.make_copy(src='survivors_sfm_src.html', dst='survivors_sfm.html', extra=EXTRA)
            ctx, pg, errs = await H.new_page(b, srv.port, page='survivors_sfm.html')
            U = await pg.evaluate("()=>__p6x.U3.snack")
            n0 = len(FAILS); ONLY = secs
            await run_core(pg, U, tag='[변이:%s] ' % name)
            red = len(FAILS) - n0
            del FAILS[n0:]
            check('변이 「%s」 가 시험을 빨갛게 한다 (빨강 %d개)' % (name, red), red > 0)
            await ctx.close()
        await b.close()
    srv.close()
    for f in ('survivors_sfm_src.html', 'survivors_sfm.html'):
        try: os.remove(os.path.join(ROOT, f))
        except OSError: pass

if __name__ == '__main__':
    asyncio.run(mutants() if MUT else main())
    print('\n%s' % ('실패 %d: %s' % (len(FAILS), FAILS) if FAILS else '전부 통과'))
    sys.exit(1 if FAILS else 0)
