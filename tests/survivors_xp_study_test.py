# -*- coding: utf-8 -*-
"""📚 흐접새우 서바이벌 「공부 깨달음」 시험 (2026-10-18 사장님 지시 — 경험치 패시브가 슬롯만 먹고 체감이 없다)

공부 패시브는 경험치 +8%/단계에 더해 「레벨업할 때마다 깨달음」이 터진다:
  Lv1 지혜의 파동(주변 적 피해 + 살짝 밀침) · Lv2 파동 범위↑·피해가 내 레벨에 비례 · Lv3 3초간 피해 +12% 공속 +8%(겹치지 않고 갱신만)
  Lv4 파동 한 번 더 + HP 8% 회복 · Lv5 레벨업의 15%로 카드 한 장 더(20초에 한 번)
  파동 피해는 상한이 있고 보스에게는 50% · 한 프레임에 파동은 최대 3번 · 상태는 전부 S.x3.lw 숫자(이어하기에 저장된다)

시험(실제 게임 코드 — gainXp · studyWave · studyFlush · studyTick · update · RES — 를 부른다):
  A  단계별 효과 문(Lv0~5): 파동 대기·버프·HP 회복·두 번째 파동·추가 카드가 정확히 그 단계부터
  B  파동 모양: 반경 안/밖 · Lv1 반경 < Lv2 반경 · 피해 = 식 값 · 밀침 · 보스는 50%·밀침 없음 · 정예는 보통 적과 같다
  C  피해 상한(cap) · 내 레벨에 비례(Lv2~) · Lv1 은 레벨과 무관
  D  깨달음 버프: 피해 ×1.12 · 쿨타임 ×0.92 · 겹치지 않고 갱신 · 3초 뒤 꺼짐 · Lv2 이하는 안 켜진다
  E  한 프레임 파동 상한 3 · 두 번째 파동 상한 3 · 경험치 큰 보석으로 레벨이 우르르 올라도 안 폭주
  F  추가 카드: Lv5 에서만 · 확률 15%(난수 고정) · 쿨 20초 · 쿨 끝나면 다시
  G  이어하기: S.x3.lw 가 저장→복구에서 그대로 · 옛 저장본(lw 없음)도 안전 · 서명(SIG) 불변
  H  실제 update 루프: 보석을 먹어 레벨업 → 파동이 나가 적에게 피해(dmgBy.study) · 오류 0
  I  장비 전 종목: 무기 전부 × 각성 유무 × 공부 Lv1/5 × 캐릭터 전부 — 오류·NaN 없이 돈다
  --mutants: 고친 줄을 하나씩 되돌린 사본에서 시험이 빨강이 되는지 본다(시험이 진짜로 잡는지)
사용: python3 tests/survivors_xp_study_test.py [--only A,B,..] [--mutants]
"""
import asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ['SV_CSX_OFF'] = '1'     # 브장신 선빵 같은 캐릭터 고유 피해 몫을 꺼서 식 값과 정확히 비교한다
import sv_harness as H
from playwright.async_api import async_playwright

SRC = os.environ.get('XS_HTML', 'survivors.html')
ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
MUTANTS = '--mutants' in sys.argv

EXTRA = r"""window.__xs={studyLv,studyWave,studyFlush,studyTick,LW,STUDYV,MAGV,xpMul,cdMul,dmgMul,magMul,areaMul,knock,RES,relTick,mapTick,dropItem,usePick,PICK,items,gems,
  get SIG(){return RES.SIG},WEAP,PASS,PT,MAXLV,MAXPASS,get waves(){return window.__xw},resetW(){window.__xw=0}};
window.__xw=0;{const sw=studyWave;studyWave=function(){window.__xw++;return sw.apply(this,arguments);};}
"""

JS = r"""
(()=>{
const X=window.__p6x,T=window.__xs;
const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
const NOCRIT=()=>.999;
function scene(o){o=o||{};Math.random=mb(o.seed||7);X.CH_set(o.ch||'brj');X.start();const S=X.S;
  S.ps=Object.assign({},o.ps||{});S.pt=Object.assign({},o.pt||{});
  S.t=o.t||90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.spawnT=-1e12;
  S.lv=o.lv||10;S.xp=0;S.need=o.need===undefined?1e12:o.need;S.pendingLv=0;
  for(const q of X.enemies.a)q.on=false;X.props.clear();for(const g of X.gems.a)g.on=false;for(const it of X.items.a)it.on=false;
  const w=S.x3.lw;w.bT=w.xc=w.w2=w.p2=w.pw=0;T.resetW();S.p.hp=S.p.mhp=o.hp||1000;S.p.inv=0;
  return S;}
function foe(S,d,o){o=o||{};let e;if(o.boss)e=X.spawnBoss('mao');else e=X.spawnEnemy(0,2.5,null,{x:S.p.x+d,y:S.p.y});
  e.x=S.p.x+d;e.y=S.p.y;e.sp=0;e.hp=e.mhp=1e12;e.sh=0;e.kb=0;e.kr=0;if(o.el)e.el=1;return e;}
const lvOnce=S=>{S.need=10;S.xp=0;X.gainXp(10);};   // 정확히 한 레벨
window.__xt={
  A(){const out=[];for(let L=0;L<=5;L++){const S=scene({ps:L?{study:L}:{}});Math.random=()=>0;   // 난수 0 → 15% 굴림은 늘 성공
      S.p.hp=Math.round(S.p.mhp*.5);const hp0=S.p.hp;lvOnce(S);const w=S.x3.lw;
      out.push({L,pw:w.pw,bT:w.bT,p2:w.p2,w2:+w.w2.toFixed(3),heal:S.p.hp-hp0,want:Math.round(S.p.mhp*T.STUDYV.heal),pend:S.pendingLv,xc:w.xc,xp:+T.xpMul().toFixed(3)});}
    return out;},
  B(){const R=[];
    for(const L of [1,2]){const S=scene({ps:{study:L},lv:10});Math.random=NOCRIT;const V=T.STUDYV,r=V.R[L>=2?1:0]*T.areaMul();
      const E=[foe(S,r-8,{}),foe(S,r+60,{}),foe(S,V.R[0]+30,{}),foe(S,0.01+30,{el:1})];   // 안 · 밖 · Lv1 반경 밖/Lv2 반경 안(→ 아래에서 판단) · 정예
      const near=E[0],far=E[1],mid=E[2],el=E[3];near.y=far.y=mid.y=S.p.y;
      const d0=near.hp;T.studyWave();
      const dn=d0-near.hp,df=d0-far.hp,dm=d0-mid.hp,de=d0-el.hp;
      const want=(L>=2?Math.min(V.cap,V.d0+V.dLv*S.lv):V.d0)*T.dmgMul();
      R.push({L,r:+r.toFixed(1),dn:+dn.toFixed(3),want:+want.toFixed(3),far:df,mid:dm,midIn:(V.R[0]+30)<(r+mid.r),el:+de.toFixed(3),knock:near.kb>0,farKnock:far.kb>0});}
    return R;},
  Bboss(){const S=scene({ps:{study:2},lv:10});Math.random=NOCRIT;const V=T.STUDYV;const b=foe(S,60,{boss:1}),n=foe(S,-60,{});b.x=S.p.x+60;b.y=S.p.y;b.hp=b.mhp=1e12;
    const hb=b.hp,hn=n.hp;T.studyWave();return {boss:hb-b.hp,norm:hn-n.hp,ratio:(hb-b.hp)/(hn-n.hp),bossKb:b.kb||0,want:V.boss};},
  C(){const V=T.STUDYV,out={};
    for(const lv of [1,10,20,40,1000]){for(const L of [1,2]){const S=scene({ps:{study:L},lv});Math.random=NOCRIT;const e=foe(S,30,{});const h=e.hp;T.studyWave();out[L+':'+lv]=h-e.hp;}}
    out.cap=V.cap;out.dm=(()=>{const S=scene({ps:{study:2}});return T.dmgMul();})();out.d0=V.d0;out.dLv=V.dLv;return out;},
  D(){const r={};for(const L of [2,3]){const S=scene({ps:{study:L}});const d0=T.dmgMul(),c0=T.cdMul();lvOnce(S);const on=S.x3.lw.bT>0;
      r[L]={on,dRatio:T.dmgMul()/d0,cRatio:T.cdMul()/c0,bT:S.x3.lw.bT};
      if(L===3){lvOnce(S);r.again=S.x3.lw.bT;T.studyTick(1);r.after1=+S.x3.lw.bT.toFixed(3);lvOnce(S);r.refresh=S.x3.lw.bT;T.studyTick(2.9);r.t29=T.dmgMul()/d0;T.studyTick(.2);r.off=T.dmgMul()/d0;r.offC=T.cdMul()/c0;}}
    r.V=T.STUDYV;return r;},
  E(){const o={};
    {const S=scene({ps:{study:1},need:10});S.xp=0;X.gainXp(1e6);o.lv1={lv:S.lv,pw:S.x3.lw.pw};T.resetW();T.studyFlush();o.lv1.flushed=T.waves;T.resetW();T.studyFlush();o.lv1.again=T.waves;}
    {const S=scene({ps:{study:4},need:10});S.xp=0;X.gainXp(1e6);o.lv4={pw:S.x3.lw.pw,p2:S.x3.lw.p2};T.resetW();T.studyFlush();o.lv4.flushed=T.waves;T.resetW();T.studyTick(.34);o.lv4.early=T.waves;T.studyTick(.02);o.lv4.second=T.waves;T.studyTick(1);o.lv4.after=T.waves;}
    {const S=scene({ps:{study:4},need:10});S.xp=0;const lv0=S.lv;lvOnce(S);T.resetW();T.studyFlush();const a=T.waves;T.studyTick(.34);const b=T.waves;T.studyTick(.02);o.single={first:a,early:b,second:T.waves};}
    return o;},
  F(){const o={};
    {const S=scene({ps:{study:5}});Math.random=()=>.01;lvOnce(S);o.first=S.pendingLv;o.xc=S.x3.lw.xc;lvOnce(S);o.second=S.pendingLv;T.studyTick(19.9);lvOnce(S);o.stillCd=S.pendingLv;T.studyTick(.2);lvOnce(S);o.afterCd=S.pendingLv;}
    {const S=scene({ps:{study:5}});Math.random=()=>.9;for(let i=0;i<5;i++)lvOnce(S);o.noRoll=S.pendingLv;}
    {const S=scene({ps:{study:4}});Math.random=()=>.01;lvOnce(S);o.lv4=S.pendingLv;}
    {const S=scene({ps:{study:5}});Math.random=()=>.149;lvOnce(S);o.edgeIn=S.pendingLv;const S2=scene({ps:{study:5}});Math.random=()=>.151;lvOnce(S2);o.edgeOut=S2.pendingLv;}
    o.P=T.STUDYV.xcP;return o;},
  async G(){const o={};
    const S=scene({ps:{study:5},lv:12});const w=S.x3.lw;w.bT=2.1;w.xc=13;w.w2=.2;w.p2=2;w.pw=1;o.sig0=T.RES.SIG;
    S.t=130;const b=T.RES.build();o.built=!!b.text;o.why=b.why||'';
    X.state='title';const okr=T.RES.restore(b.text);const S2=X.S;o.restored=okr;o.lw=S2&&S2.x3.lw?{...S2.x3.lw}:null;o.sig1=T.RES.SIG;o.ps=S2&&S2.ps.study;
    // 옛 저장본(lw 없음): 지운 채로 저장 → 복구 → 판이 계속 돈다
    const S3=scene({ps:{study:5},lv:12});delete S3.x3.lw;const b3=T.RES.build();o.oldBuilt=!!b3.text;X.state='title';o.oldRestored=T.RES.restore(b3.text);
    const S4=X.S;o.oldHasLw=!!(S4&&S4.x3.lw);if(S4)delete S4.x3.lw;   // 복구가 기본값을 채워 줘도 「lw 가 아예 없는 판」으로 되돌려 방어 코드를 직접 밟는다
    let err='';try{if(S4){X.state='play';for(let i=0;i<30;i++)X.update(1/30);T.studyLv();T.studyFlush();T.studyTick(1);}}catch(e){err=String(e);}o.oldErr=err;o.oldLwAfter=!!(S4&&S4.x3.lw);
    return o;},
  H(){const S=scene({ps:{study:5},lv:5,need:6});Math.random=mb(99);const w=S.x3.lw;const e=[];for(let i=0;i<10;i++){const q=foe(S,40+i*12,{});q.hp=q.mhp=1e12;e.push(q);}
    for(let i=0;i<40;i++){const g=X.gems.get();if(g){g.x=S.p.x+5+i;g.y=S.p.y;g.v=3;g.mag=1;}}
    const lv0=S.lv;let lvups=0;for(let i=0;i<90;i++){const st=X.state;if(st==='lvup'){X.pick(X.CUR[0]);lvups++;continue;}if(st!=='play'){X.resume();continue;}
      S.p.hp=S.p.mhp;for(const q of e){q.hp=q.mhp=1e12;}X.update(1/30);}
    return {lv0,lv:S.lv,lvups,waves:window.__xw,study:S.dmgBy.study||0,bT:w.bT,state:X.state};},
  I(chars,L,ev,wk){const o={n:0,bad:[]};
    const keys=wk||Object.keys(T.WEAP);
    for(const ch of chars){for(const k of keys){
      const S=scene({ch,ps:{study:L},lv:30,seed:11});S.w={[k]:T.MAXLV};S.cd={};if(ev)S.ev={[k]:1};else S.ev={};X.tkCalc();X.synCalc();
      for(let i=0;i<14;i++){const q=foe(S,60+i*25,{});q.hp=q.mhp=2000;q.sp=60;}
      let err='';try{for(let t=0;t<150;t++){const st=X.state;if(st==='lvup'){X.pick(X.CUR[0]);continue;}if(st!=='play'){X.resume();continue;}
          S.p.hp=S.p.mhp;if(t%15===0){S.need=3;X.gainXp(1e3);}X.update(1/30);}}catch(e){err=String(e&&e.stack||e).slice(0,160);}
      const fin=[S.p.hp,S.p.mhp,S.lv,S.kills,S.x3.lw.bT,S.x3.lw.xc,S.x3.lw.w2,S.x3.lw.pw,S.x3.lw.p2].every(Number.isFinite);
      o.n++;if(err||!fin)o.bad.push({ch,k,L,ev,err,fin});}}
    return o;}
};
return true;})()
"""


async def run_suite(src, tag=''):
    p = H.make_copy(src, 'survivors_xs%s.html' % tag, extra=EXTRA)
    srv = H.Srv()
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg, flush=True)
        if not c:
            fails.append(msg)
    def want(s): return (ONLY is None and not (MUTANTS and s == 'I')) or (ONLY is not None and s in ONLY)   # 변이 점검은 느린 I(장비 전 종목)를 건너뛴다
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page='survivors_xs%s.html' % tag)
            await pg.evaluate(JS)
            ev = lambda e: pg.evaluate(e)
            V = await ev('__xs.STUDYV')
            near = lambda a, c, t=1e-6: abs(a - c) <= t * max(1, abs(c))
            if want('A'):
                A = await ev('__xt.A()')
                print('A', json.dumps(A), flush=True)
                for a in A:
                    L = a['L']
                    ok(near(a['xp'], 1 + V['xp'] * L, 1e-3), 'A%d 경험치 배율 = 1 + %.2f×단계 (%s)' % (L, V['xp'], a['xp']))
                    ok((a['pw'] == 1) == (L >= 1), 'A%d 레벨업 한 번에 파동 대기 %s (Lv1부터)' % (L, a['pw']))
                    ok((a['bT'] == V['buffT']) == (L >= 3) and (L >= 3 or a['bT'] == 0), 'A%d 깨달음 버프 %s초 (Lv3부터)' % (L, a['bT']))
                    ok((a['heal'] == a['want']) if L >= 4 else (a['heal'] == 0), 'A%d HP 회복 %s (Lv4부터 %s)' % (L, a['heal'], a['want']))
                    ok((a['p2'] == 1 and abs(a['w2'] - V['w2dt']) < 1e-9) if L >= 4 else (a['p2'] == 0 and a['w2'] == 0), 'A%d 두 번째 파동 예약 p2=%s w2=%s (Lv4부터)' % (L, a['p2'], a['w2']))
                    ok((a['pend'] == 2 and a['xc'] == V['xcCd']) if L >= 5 else (a['pend'] == 1 and a['xc'] == 0), 'A%d 추가 카드 pend=%s xc=%s (Lv5부터)' % (L, a['pend'], a['xc']))
            if want('B'):
                B = await ev('__xt.B()')
                print('B', json.dumps(B), flush=True)
                for r in B:
                    ok(near(r['dn'], r['want'], 1e-4) and r['dn'] > 0, 'B Lv%d 반경 안 적 피해 = 식 값 (%s vs %s)' % (r['L'], r['dn'], r['want']))
                    ok(r['far'] == 0, 'B Lv%d 반경 밖 적은 안 맞는다' % r['L'])
                    ok(r['knock'] and not r['farKnock'], 'B Lv%d 맞은 적은 밀린다 · 밖은 안 밀린다' % r['L'])
                    ok(near(r['el'], r['dn'], 1e-4), 'B Lv%d 정예도 보통 적과 같은 피해 (%s vs %s)' % (r['L'], r['el'], r['dn']))
                    if r['L'] == 1: ok(r['mid'] == 0 and not r['midIn'], 'B Lv1 반경(%.0f) 밖 적(%.0f)은 Lv1 파동에 안 맞는다' % (r['r'], V['R'][0] + 30))
                    if r['L'] == 2: ok(r['mid'] > 0 and r['midIn'], 'B Lv2 는 반경이 넓어져 Lv1 밖 적도 맞는다 (반경 %.0f)' % r['r'])
                ok(V['R'][1] > V['R'][0], 'B Lv2 반경 > Lv1 반경 (%s > %s)' % (V['R'][1], V['R'][0]))
                bb = await ev('__xt.Bboss()')
                print('B보스', json.dumps(bb), flush=True)
                ok(near(bb['ratio'], V['boss'], 1e-4), 'B 보스는 파동 피해 %d%% (비율 %s)' % (V['boss'] * 100, bb['ratio']))
                ok(bb['bossKb'] == 0, 'B 보스는 밀리지 않는다')
            if want('C'):
                C = await ev('__xt.C()')
                print('C', json.dumps(C), flush=True)
                dm = C['dm']
                ok(near(C['1:1'], V['d0'] * dm, 1e-4) and near(C['1:1000'], V['d0'] * dm, 1e-4), 'C Lv1 은 내 레벨과 무관 (%s = %s = d0×배율 %s)' % (C['1:1'], C['1:1000'], V['d0'] * dm))
                ok(near(C['2:10'], (V['d0'] + V['dLv'] * 10) * dm, 1e-4) and near(C['2:20'], (V['d0'] + V['dLv'] * 20) * dm, 1e-4), 'C Lv2 는 내 레벨에 비례 (Lv10 %s · Lv20 %s)' % (C['2:10'], C['2:20']))
                ok(C['2:20'] > C['2:10'] > C['2:1'], 'C Lv2 레벨이 오를수록 세진다')
                ok(near(C['2:1000'], V['cap'] * dm, 1e-4) and near(C['2:40'], min(V['cap'], V['d0'] + V['dLv'] * 40) * dm, 1e-4), 'C 피해 상한 — Lv1000 이어도 상한×배율 (%s vs %s)' % (C['2:1000'], V['cap'] * dm))
            if want('D'):
                D = await ev('__xt.D()')
                print('D', json.dumps(D), flush=True)
                ok(not D['2']['on'] and abs(D['2']['dRatio'] - 1) < 1e-9 and abs(D['2']['cRatio'] - 1) < 1e-9, 'D Lv2 는 깨달음 버프가 안 켜진다')
                ok(D['3']['on'] and near(D['3']['dRatio'], 1 + V['buffD'], 1e-9) and near(D['3']['cRatio'], 1 - V['buffC'], 1e-9), 'D Lv3 버프: 피해 ×%.2f · 쿨타임 ×%.2f (%s · %s)' % (1 + V['buffD'], 1 - V['buffC'], D['3']['dRatio'], D['3']['cRatio']))
                ok(D['again'] == V['buffT'] and D['refresh'] == V['buffT'], 'D 버프는 겹치지 않고 갱신만 (%s · %s)' % (D['again'], D['refresh']))
                ok(abs(D['after1'] - (V['buffT'] - 1)) < 1e-6, 'D 시간이 흐르면 줄어든다 (%s)' % D['after1'])
                ok(near(D['t29'], 1 + V['buffD'], 1e-9) and abs(D['off'] - 1) < 1e-9 and abs(D['offC'] - 1) < 1e-9, 'D %s초가 지나면 꺼진다 (끝 직전 ×%s · 끝 ×%s)' % (V['buffT'], D['t29'], D['off']))
            if want('E'):
                E = await ev('__xt.E()')
                print('E', json.dumps(E), flush=True)
                ok(E['lv1']['lv'] > 25 and E['lv1']['pw'] == V['maxW'] and E['lv1']['flushed'] == V['maxW'] and E['lv1']['again'] == 0, 'E 레벨이 한꺼번에 %d번 올라도 한 프레임 파동은 %d번까지 (%s)' % (E['lv1']['lv'], V['maxW'], E['lv1']))
                ok(E['lv4']['pw'] == V['maxW'] and E['lv4']['p2'] == V['maxW'] and E['lv4']['flushed'] == V['maxW'], 'E Lv4 도 첫 파동 %d · 두 번째 파동 대기 %d 까지 (%s)' % (V['maxW'], V['maxW'], E['lv4']))
                ok(E['lv4']['early'] == 0 and E['lv4']['second'] == V['maxW'] and E['lv4']['after'] == V['maxW'], 'E 두 번째 파동은 %.2f초 뒤에 한 번만 터진다 (%s)' % (V['w2dt'], E['lv4']))
                ok(E['single'] == {'first': 1, 'early': 1, 'second': 2}, 'E 레벨업 한 번이면 파동 1 + 두 번째 1 = 2번 (%s)' % E['single'])
            if want('F'):
                F = await ev('__xt.F()')
                print('F', json.dumps(F), flush=True)
                ok(F['first'] == 2 and F['xc'] == V['xcCd'], 'F Lv5 레벨업 → 추가 카드 1장 (대기 %s · 쿨 %s)' % (F['first'], F['xc']))
                ok(F['second'] == 3 and F['stillCd'] == 4, 'F 쿨 중에는 또 안 나온다 (레벨 +1씩만: %s → %s)' % (F['second'], F['stillCd']))
                ok(F['afterCd'] == 6, 'F 쿨 %s초가 끝나면 다시 나온다 (%s)' % (V['xcCd'], F['afterCd']))
                ok(F['noRoll'] == 5, 'F 15%% 굴림에 지면 없다 (레벨업 5번 → 대기 %s)' % F['noRoll'])
                ok(F['lv4'] == 1, 'F Lv4 는 추가 카드가 없다')
                ok(F['edgeIn'] == 2 and F['edgeOut'] == 1 and F['P'] == 0.15, 'F 확률 경계 15%% (난수 .149 → %s · .151 → %s)' % (F['edgeIn'], F['edgeOut']))
            if want('G'):
                G = await ev('__xt.G()')
                print('G', json.dumps(G), flush=True)
                ok(G['built'] and G['restored'], 'G 저장 → 복구가 된다 (%s)' % G.get('why'))
                ok(G['lw'] == {'bT': 2.1, 'xc': 13, 'w2': .2, 'p2': 2, 'pw': 1} and G['ps'] == 5, 'G 이어하기: 깨달음 상태가 그대로 (%s)' % G['lw'])
                ok(G['sig0'] == G['sig1'] and G['sig0'].startswith('1:'), 'G 저장 서명(SIG) 불변 %s' % G['sig0'])
                ok(G['oldBuilt'] and G['oldRestored'] and not G['oldErr'], 'G 옛 저장본(lw 없음)도 복구되고 판이 돈다 (%s)' % G['oldErr'])
            if want('H'):
                Hh = await ev('__xt.H()')
                print('H', json.dumps(Hh), flush=True)
                ok(Hh['lv'] - Hh['lv0'] >= 3 and Hh['lvups'] >= 3, 'H 보석을 먹어 레벨이 오른다 (Lv%d → Lv%d · 카드 %d번)' % (Hh['lv0'], Hh['lv'], Hh['lvups']))
                ok(Hh['waves'] >= 3 and Hh['study'] > 0, 'H 레벨업마다 파동이 나가 적에게 피해를 준다 (파동 %d번 · 피해 %.0f)' % (Hh['waves'], Hh['study']))
            if want('I'):
                chars = await ev('__p6x.CHARS.map(c=>c.k)')
                weaps = await ev('Object.keys(__xs.WEAP)')
                bad = []; n = 0
                for L in (1, 5):
                    for evf in (0, 1):
                        r = await pg.evaluate('([c,L,e,w])=>__xt.I(c,L,e,w)', [['brj'], L, evf, weaps]); n += r['n']; bad += r['bad']
                for L in (1, 3, 5):
                    r = await pg.evaluate('([c,L,e,w])=>__xt.I(c,L,e,w)', [chars, L, 0, ['pan']]); n += r['n']; bad += r['bad']
                print('I', n, '판 · 이상', len(bad), flush=True)
                ok(n >= 200 and not bad, 'I 무기 %d종 × 각성 유무 × 공부 Lv1/5, 캐릭터 %d명 × Lv1/3/5 — %d판 오류·NaN 없음 (%s)' % (len(weaps), len(chars), n, bad[:2]))
            real = [e for e in errs if 'survivors_xs' not in e]
            ok(not real, '콘솔·페이지 오류 0 %s' % real[:3])
            await b.close()
    finally:
        srv.close()
        try: os.remove(p)
        except Exception: pass
    return fails


MUT = [
    ('보스 50% 제거', "hurt(e,e.boss?d*V.boss:d);", "hurt(e,d);"),
    ('피해 상한 제거', "Math.min(V.cap,V.d0+V.dLv*S.lv)", "(V.d0+V.dLv*S.lv)"),
    ('프레임 파동 상한 제거', "if(w.pw<V.maxW)w.pw++;", "w.pw++;"),
    ('버프 겹침', "if(L>=3)w.bT=V.buffT;", "if(L>=3)w.bT+=V.buffT;"),
    ('추가 카드 쿨 제거', "if(L>=5&&w.xc<=0&&Math.random()<V.xcP)", "if(L>=5&&Math.random()<V.xcP)"),
    ('두 번째 파동 제거', "if(w.p2<V.maxW)w.p2++;", ""),
    ('HP 회복 제거', "S.p.hp=Math.min(S.p.mhp,S.p.hp+h);if(w.p2", "if(w.p2"),
    ('버프 피해 제거', "*(lwOn()?1+STUDYV.buffD:1)", ""),
    ('버프 공속 제거', "*(lwOn()?1-STUDYV.buffC:1)", ""),
    ('Lv2 반경 제거', "V.R[L>=2?1:0]", "V.R[0]"),
    ('밀침 제거', "if(e.on){const dd=Math.hypot(dx,dy)||1;knock(e,dx/dd,dy/dd,V.kb,.22);}", ""),
    ('Lv2 레벨 비례 제거', "(L>=2?Math.min(V.cap,V.d0+V.dLv*S.lv):V.d0)", "V.d0"),
    ('경험치 배율 제거', "+STUDYV.xp*pv('study')+S.syn.xp;", "+S.syn.xp;"),
    ('정예 보스 취급', "hurt(e,e.boss?d*V.boss:d);", "hurt(e,(e.boss||e.el)?d*V.boss:d);"),
    ('옛 저장본 방어 제거', "function LW(){return S.x3.lw||(S.x3.lw={bT:0,xc:0,w2:0,p2:0,pw:0});}", "function LW(){return S.x3.lw;}"),
]


async def main():
    if not MUTANTS:
        fails = await run_suite(SRC)
        print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
        return 1 if fails else 0
    s = open(os.path.join(H.ROOT, SRC), encoding='utf-8').read()
    miss = []
    for i, (nm, a, c) in enumerate(MUT):
        if s.count(a) != 1:
            print('변이 %s: 원본에서 줄을 못 찾음(%d)' % (nm, s.count(a))); miss.append(nm); continue
        dst = 'survivors_xsm_%d.html' % i
        open(os.path.join(H.ROOT, dst), 'w', encoding='utf-8').write(s.replace(a, c))
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
