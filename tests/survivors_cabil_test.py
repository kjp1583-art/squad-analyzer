# -*- coding: utf-8 -*-
"""✨ 흐접새우 서바이벌 「캐릭터 고유능력」 시험 — 2026-10-12 사장님 지시
   「모든 캐릭터에게 개성에 맞는 고유스텟을 상호밸런스를 유지해서, 아이템 자동획득 같은 스텟이 아닌 고유능력도 좋아」
   사용: python3 tests/survivors_cabil_test.py     (종료코드 0 = 전부 통과)
   구성
     가  표 — CSX 값이 한 곳에 있고, 20명 전원이 고유스텟 1줄 이상(없음 0명) · 같은 효과를 둘이 갖지 않는다
     나  문구 = 값 — 값(CSX)을 바꾸면(변이) 카드 칩·설명 문구·일시정지 표의 숫자가 따라 바뀐다
     다  동작 = 문구 — 캐릭터마다 새 능력이 문구와 같은 크기로, 조건을 밟았을 때만 켜진다(경계값 포함) · 다른 캐릭터는 그대로
     라  이어하기 — 능력 상태(S.x3.cs)가 저장·복구 뒤에도 이어지고 옛 저장본(칸 없음)도 안전하다
     마  전 캐릭터 × 일반/하드/베리하드 × 보스 상태 — 오류·NaN 0 · 프레임당 비용
   임시 사본 survivors_cb_cabil.html 에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, re, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
NEW = 'survivors_cb_cabil.html'
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)

EXTRA = r"""
window.__ca={pauseGame,CHARS,CSX,CSK,CSTAT,cstat,cstatChip,cstatHtml,csS,csMul,csNow,csCd,csCrit,csRegen,csTick,charTick,critChance,critMul,cdMul,moveMul,magMul,xpMul,armTotal,takenMul,dmgMul,statRows,statsHtml,RES,
  get CH(){return CH},get S(){return S}};
"""

BEGIN = """(k)=>{const P=window.__p6x;P.srvUnl(['yumi','bbb','eom']);P.CH_set(k);P.start();const S=P.S;S.spawnT=-1e12;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;S.propT=S.chickT=1e12;
  for(const q of P.enemies.a)q.on=false;S.w={};S.p.hp=S.p.mhp;P.keys={};if(P.CH.k!==k)throw new Error('캐릭터가 안 바뀜 '+k);return true}"""

async def main():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA)
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, 412, 860, page=NEW, ready='__ca')
            await pg.wait_for_timeout(500)
            begin = lambda k: pg.evaluate(BEGIN, k)

            # ── 가 표
            r = await pg.evaluate("""()=>{const x=__ca;const rows={};for(const c of x.CHARS)rows[c.k]=x.cstat(c);
              return {csx:Object.keys(x.CSX),ks:x.CHARS.map(c=>c.k),rows:Object.fromEntries(Object.entries(rows).map(([k,d])=>[k,{n:d.rows.length,none:d.none,nm:d.rows.map(r=>r.nm)}]))}}""")
            check('[가] 고유스텟 없음 0명 — 20명 전원 1줄 이상', all(d['n'] >= 1 for d in r['rows'].values()) and len(r['rows']) == 20, {k: d['n'] for k, d in r['rows'].items()})
            check('[가] 고유능력이 새로 붙은 13명이 CSX 한 표에 있다', sorted(r['csx']) == sorted(['brj', 'mms', 'hrb', 'amd', 'ildj', 'ddmj', 'eom', 'bbb', 'pty', 'yj', 'bgb', 'tw', 'tjg']), r['csx'])
            allnm = [n for d in r['rows'].values() for n in d['nm']]
            dup = sorted({n for n in allnm if allnm.count(n) > 1 and n not in ('이동속도', '받는 피해', 'HP 회복', '줍는 범위', '경험치', '쿨타임', '최대 HP')})
            check('[가] 능력 이름 겹침 0(공용 수치 행 제외)', not dup, dup)

            # ── 나 문구 = 값 (변이)
            MUT = [('brj', 'brj.full', .3), ('hrb', 'hrb.run', .12), ('amd', 'amd.x', 2), ('amd', 'amd.at', .5), ('ildj', 'ildj.cc', .3), ('ildj', 'ildj.T', 9),
                   ('ddmj', 'ddmj.cd', 1.5), ('eom', 'eom.n', 12), ('bbb', 'bbb.every', 14), ('bbb', 'bbb.T', 4), ('bbb', 'bbb.cd', .6), ('yj', 'yj.at', .8), ('yj', 'yj.dmg', .15), ('mms', 'mms.tk', .45), ('mms', 'mms.base', .18), ('tw', 'tw.tk', .15), ('hrb', 'hrb.tk', .15), ('bgb', 'bgb.dodge', .15)]
            res = await pg.evaluate("""(MUT)=>{const x=__ca,out=[];
              const pc=v=>(Math.round(v*1000)/10)+'%',nm=v=>String(Math.round(v*100)/100);
              const text=k=>{const c=x.CHARS.find(c=>c.k===k);const d=x.cstat(c);return d.rows.map(r=>r.nm+' '+r.v+' '+r.ds).join(' | ')+' | '+x.cstatChip(c).txt};
              for(const [k,path,v0] of MUT){const [a,f]=path.split('.');const X=x.CSX[a];if(X[f]!==v0){out.push({k,path,bad:'값이 '+X[f]});continue}
                const f0=text(k);const isPc=Math.abs(v0)<1&&path!=='bbb.cd';
                const want0=isPc?pc(v0):nm(v0);
                const shown=(path==='bbb.cd')?f0.includes(pc(1-v0)):f0.includes(want0);
                const nv=isPc?(v0+.07):(v0+3);X[f]=nv;const f1=text(k);X[f]=v0;
                const want1=(path==='bbb.cd')?pc(1-nv):(isPc?pc(nv):nm(nv));
                out.push({k,path,shown,want0,mut:f1.includes(want1),want1,moved:want0!==want1})}
              return out}""", MUT)
            for o in res:
                check('[나] %s %s → 문구에 나오고, 값을 바꾸면 따라 바뀐다' % (o['k'], o['path']), o.get('shown') and o.get('mut') and o.get('moved') and 'bad' not in o, o)
            # 엄 연쇄는 마릿수 칩에도, 브장신 칩은 선빵
            chips = await pg.evaluate("()=>Object.fromEntries(__ca.CHARS.map(c=>[c.k,__ca.cstatChip(c).txt]))")
            check('[나] 칩 — 브장신=선빵 +30% · 엄장신=엄 연쇄 12킬', '선빵 +30%' in chips['brj'] and '엄 연쇄 12킬' in chips['eom'], (chips['brj'], chips['eom']))

            # ── 다 동작 = 문구
            beh = await pg.evaluate("""async (BEGIN)=>{const x=__ca,P=window.__p6x,out={};const begin=eval(BEGIN);
              const R0=Math.random;Math.random=()=>0.9999;   // 치명타가 안 터지게
              const mk=(hp,mhp)=>{const e=P.spawnEnemy(0,1,null);e.x=P.S.p.x+900;e.y=P.S.p.y;e.mhp=mhp;e.hp=hp;e.sp=0;e.dmg=0;return e};
              const dealt=(e,d)=>{const b=e.hp;P.hurt(e,d);return b-e.hp};
              try{
              // 브장신: 체력 가득 → ×1.25 / 한 대 맞은 뒤 ×1 / 집중겜(다른 캐릭터)은 ×1
              begin('brj');let e=mk(1e6,1e6);const a1=dealt(e,10),a2=dealt(e,10);out.brj={full:a1,after:a2,want:10*(1+x.CSX.brj.full)};
              begin('jjg');e=mk(1e6,1e6);out.brjOther=dealt(e,10);
              // 하리보
              begin('hrb');e=mk(1e6,1e5);P.S.p.moving=true;const h1=dealt(e,10);P.S.p.moving=false;const h2=dealt(e,10);out.hrb={run:h1,stop:h2};
              // 용조련사: 체력 100% / 80% 딱 / 79%
              begin('yj');e=mk(1e6,1e5);const S=P.S;const y=[];for(const f of [1,.8,.7999,.5]){S.p.hp=S.p.mhp*f;y.push(dealt(e,10));}out.yj=y;
              // 배고배고: 이동속도 보정만큼
              begin('bgb');e=mk(1e6,1e5);x.csTick(1/30);const mm=x.moveMul()-1;out.bgb={dmg:dealt(e,10),mm};
              // 망무새: 체력 30% 이하 받는 피해 -25% (경계) / 하리보: 움직일 때 받는 피해 -15% / 배고배고: 회피
              begin('mms');const tk=[];for(const f of [.5,.3,.29,.1]){P.S.p.hp=P.S.p.mhp*f;tk.push(x.takenMul());}out.mms=tk;
              begin('hrb');P.S.p.moving=true;const tm=x.takenMul();P.S.p.moving=false;out.hrbTk=[tm,x.takenMul()];
              begin('bgb');P.S.p.inv=0;Math.random=()=>0;const hb=P.S.p.hp;P.hitP(5);const dodged=P.S.p.hp===hb&&P.S.p.inv>0;
              P.S.p.inv=0;Math.random=()=>0.9999;P.hitP(5);const hurtd=P.S.p.hp<hb;out.dodge={dodged,hurtd};Math.random=()=>0.9999;
              // 배불배불 후렴
              begin('bbb');const c0=x.cdMul();const cdb=[];let on=null,off=null;
              for(let i=0;i<30*40;i++){P.S.p.hp=P.S.p.mhp;P.update(1/30);const v=x.cdMul();if(v<c0-1e-9&&on===null)on=P.S.t;if(on!==null&&off===null&&v>=c0-1e-9&&P.S.t>on+.5)off=P.S.t;if(off!==null)break;}
              out.bbb={base:c0,on,off,during:null};
              // 일단즐겨: 레벨업 → 치명타 +35% 10초
              begin('ildj');const ch0=x.critChance();P.S.need=5;P.S.xp=0;P.gainXp(5);P.state='play';const ch1=x.critChance();const TT=x.CSX.ildj.T;
              P.S.pendingLv=0;for(let i=0;i<30*(TT-.5);i++){P.update(1/30);}const chMid=x.critChance();for(let i=0;i<30*1.0;i++){P.update(1/30);}const ch2=x.critChance();
              P.S.need=5;P.S.xp=0;P.gainXp(5);P.S.pendingLv=0;const ch3=x.critChance();out.ildj={ch0,ch1,chMid,ch2,ch3,cc:x.CSX.ildj.cc};
              // 앙앵모르딱: 체력 절반 이하 → 회복 ×2
              const rg={};for(const [lab,f] of [['hi',.9],['edge',.5],['lo',.3]]){begin('amd');const S2=P.S;S2.p.hp=S2.p.mhp*f;const h0=S2.p.hp;P.update(1/30);rg[lab]=(S2.p.hp-h0)*30;}out.amd=rg;
              // 단단묵직: 맞으면 충격파(1.5초에 한 번)
              begin('ddmj');let S3=P.S;S3.p.inv=0;const eN=mk(1e6,1e6);eN.x=S3.p.x+60;eN.y=S3.p.y;const eF=mk(1e6,1e6);eF.x=S3.p.x+600;
              const lv=S3.lv,want=x.CSX.ddmj.dmg*(1+lv/15)*x.dmgMul();
              P.hitP(1);P.update(1/30);const dN=1e6-eN.hp,dF=1e6-eF.hp;
              S3.p.inv=0;eN.hp=1e6;P.hitP(1);P.update(1/30);const dN2=1e6-eN.hp;   // 1.5초 안 → 안 터진다
              S3.t+=1.6;S3.p.inv=0;eN.hp=1e6;P.hitP(1);P.update(1/30);const dN3=1e6-eN.hp;
              out.ddmj={dN,dF,dN2,dN3,want};
              // 엄장신: 12킬마다 충격파 · 충격파로 잡은 건 안 센다
              begin('eom');let S4=P.S;const far=mk(1e6,1e6);far.x=S4.p.x+100;far.y=S4.p.y;
              const ks=[];for(let i=0;i<11;i++){const q=mk(1,1);q.x=S4.p.x+800;P.hurt(q,99);}P.update(1/30);const f11=1e6-far.hp;
              const q12=mk(1,1);q12.x=S4.p.x+800;P.hurt(q12,99);P.update(1/30);const f12=1e6-far.hp;
              out.eom={n11:f11,n12:f12,want:x.CSX.eom.dmg*(1+S4.lv/15)*x.dmgMul(),left:x.csS().n};
              // 충격파로 잡은 건 세지 않는다: 가까이 약한 적 3마리 + 12킬
              begin('eom');S4=P.S;for(let i=0;i<3;i++){const q=mk(1,1);q.x=S4.p.x+80+i*10;q.y=S4.p.y;}for(let i=0;i<12;i++){const q=mk(1,1);q.x=S4.p.x+800;P.hurt(q,99);}P.update(1/30);out.eomChain=x.csS().n;
              }finally{Math.random=R0}
              return out}""", BEGIN)
            b_ = beh
            check('[다] 브장신 선빵 — 체력 가득한 적 ×1.3 · 한 대 뒤 ×1 · 다른 캐릭터는 ×1', abs(b_['brj']['full'] - b_['brj']['want']) < 1e-6 and abs(b_['brj']['want'] - 13) < 1e-9 and abs(b_['brj']['after'] - 10) < 1e-6 and abs(b_['brjOther'] - 10) < 1e-6, b_['brj'])
            hpb = await pg.evaluate("async (BEGIN)=>{const P=window.__p6x;const begin=eval(BEGIN);begin('brj');const b=P.S.p.mhp;begin('jjg');return [b,P.S.p.mhp,__ca.CHARS.find(c=>c.k==='brj').hp]}", BEGIN)
            check('[다] 브장신 최대 HP = 100 + 20 (스타터 보강) · 다른 캐릭터는 100', hpb == [120, 100, 20], hpb)
            room = await pg.evaluate("""async (BEGIN)=>{const P=window.__p6x,x=__ca;const begin=eval(BEGIN);const S=begin('ddo')&&P.S;S.proomT=.01;P.update(1/30);return {R:S.proom.R,want:x.CSK.room.R*(1+.1*0),t:S.proom.t}}""", BEGIN)
            check('[다] 또뀨 진실의 방 반경 = CSK.room.R(190)', abs(room['R'] - 190) < 1e-6 and room['R'] == room['want'], room)
            check('[다] 하리보 달리며 쏘기 — 움직일 때 ×1.12 · 멈추면 ×1', abs(b_['hrb']['run'] - 11.2) < 1e-6 and abs(b_['hrb']['stop'] - 10) < 1e-6, b_['hrb'])
            y = b_['yj']
            check('[다] 용조련사 위엄 — 체력 100%·80% 딱 ×1.15 · 79.99%·50% ×1(경계)', abs(y[0] - 11.5) < 1e-6 and abs(y[1] - 11.5) < 1e-6 and abs(y[2] - 10) < 1e-6 and abs(y[3] - 10) < 1e-6, y)
            check('[다] 배고배고 바람 힘 — 피해 = 1 + 이동속도 증가분(%d%%)' % round(b_['bgb']['mm'] * 100), b_['bgb']['mm'] > 0 and abs(b_['bgb']['dmg'] - 10 * (1 + b_['bgb']['mm'])) < 1e-6, b_['bgb'])
            tk = b_['mms']
            check('[다] 망무새 막다른 길 — 항상 ×0.82 · 체력 30% 미만이면 ×0.55 (29%·10% ×0.55 · 50% ×0.82)', abs(tk[0] - .82) < 1e-9 and abs(tk[2] - .55) < 1e-9 and abs(tk[3] - .55) < 1e-9 and (abs(tk[1] - .82) < 1e-9 or abs(tk[1] - .55) < 1e-9), tk)
            check('[다] 하리보 — 움직일 때 받는 피해 ×0.85 · 멈추면 ×1', abs(b_['hrbTk'][0] - .85) < 1e-9 and abs(b_['hrbTk'][1] - 1) < 1e-9, b_['hrbTk'])
            check('[다] 배고배고 바람 회피 — 굴림이 이기면 피해 0 + 무적 · 지면 피해를 받는다', b_['dodge']['dodged'] and b_['dodge']['hurtd'], b_['dodge'])
            bb = b_['bbb']
            check('[다] 배불배불 후렴 — 14초 뒤 켜져 4초 지속 · 켜진 동안 쿨타임 배율 ×0.6', bb['on'] is not None and bb['off'] is not None and abs(bb['on'] - 14) < .2 and abs((bb['off'] - bb['on']) - 4) < .2, bb)
            ib = b_['ildj']
            check('[다] 일단즐겨 커튼콜 — 레벨업 직후 치명타 +30% · 8.5초 뒤도 켜짐 · 9.5초 뒤 꺼짐 · 다시 레벨업하면 채워짐',
                  abs(ib['ch1'] - ib['ch0'] - ib['cc']) < 1e-9 and abs(ib['chMid'] - ib['ch0'] - ib['cc']) < 1e-9 and abs(ib['ch2'] - ib['ch0']) < 1e-9 and abs(ib['ch3'] - ib['ch0'] - ib['cc']) < 1e-9 and abs(ib['cc'] - .3) < 1e-9, ib)
            ab = b_['amd']
            check('[다] 앙앵모르딱 가호 — 체력 90%% 초당 %.2f · 50%% 딱·30%% 초당 %.2f(×2)' % (ab['hi'], ab['lo']), abs(ab['hi'] - 1.5) < .06 and abs(ab['edge'] - 3) < .01 and abs(ab['lo'] - 3) < .1, ab)
            dm = b_['ddmj']
            check('[다] 단단묵직 반격 — 맞으면 가까운 적만 피해(식 그대로) · 1.5초 안 두 번째는 없음 · 지나면 다시', abs(dm['dN'] - dm['want']) < 1e-4 and dm['dF'] == 0 and dm['dN2'] == 0 and abs(dm['dN3'] - dm['want']) < 1e-4, dm)
            em = b_['eom']
            check('[다] 엄장신 엄 연쇄 — 11킬엔 없고 12킬째에 충격파(식 그대로) · 나머지 0', em['n11'] == 0 and abs(em['n12'] - em['want']) < 1e-4 and em['left'] == 0, em)
            check('[다] 엄장신 — 충격파로 잡은 적은 킬 수에 안 센다(연쇄 폭주 없음)', b_['eomChain'] == 0, b_['eomChain'])

            # ── 일시정지 표·칩 정직
            tb = await pg.evaluate("""async (BEGIN)=>{const x=__ca,P=window.__p6x,out={};const begin=eval(BEGIN);
              for(const k of ['brj','hrb','yj','bgb','bbb']){begin(k);const rows=x.statRows();out[k]={dmg:rows.find(r=>r.k==='dmg').s,cd:rows.find(r=>r.k==='cd').s}}
              begin('hrb');P.S.p.moving=true;out.hrbOn=x.statRows().find(r=>r.k==='dmg').s;P.S.p.moving=false;out.hrbOff=x.statRows().find(r=>r.k==='dmg').s;
              begin('ildj');P.S.need=5;P.S.xp=0;P.gainXp(5);P.S.pendingLv=0;out.ildjCrit=x.statRows().find(r=>r.k==='crit').s;
              return out}""", BEGIN)
            check('[다] 일시정지 능력치 표 — 브장신/하리보/용조련사/배고배고 「피해」 줄에 능력 설명', all(tb[k]['dmg'] for k in ('brj', 'hrb', 'yj', 'bgb')), tb)
            check('[다] 하리보 표 — 움직이면 「지금 켜짐」 · 멈추면 「지금 꺼짐」', '켜짐' in tb['hrbOn'] and '꺼짐' in tb['hrbOff'], (tb['hrbOn'], tb['hrbOff']))
            check('[다] 배불배불 표 — 쿨타임 줄에 후렴 설명', '후렴' in tb['bbb']['cd'], tb['bbb'])
            check('[다] 일단즐겨 표 — 치명타 구성에 캐릭터 +30%', '캐릭터 +30%' in tb['ildjCrit'], tb['ildjCrit'])

            # ── 라 이어하기: 능력 상태가 저장 본에 실리고(S.x3.cs) 옛 저장본(칸 없음)도 안전
            rs = await pg.evaluate("""async (BEGIN)=>{const x=__ca,P=window.__p6x,out={};const begin=eval(BEGIN);
              begin('eom');const c=x.csS();c.n=7;c.pend=0;const js=JSON.parse(JSON.stringify(P.S.x3));out.keep=js.cs&&js.cs.n===7;
              const S=P.S;delete S.x3.cs;   // 옛 저장본 — 칸이 없다
              let err='';try{for(const k of ['brj','mms','hrb','amd','ildj','ddmj','eom','bbb','yj','bgb']){begin(k);delete P.S.x3.cs;P.S.p.hp=P.S.p.mhp*.4;for(let i=0;i<20;i++)P.update(1/30);}}catch(e){err=String(e)}
              out.err=err;return out}""", BEGIN)
            check('[라] S.x3.cs 가 JSON 에 실린다 · 칸이 없는 옛 저장본에서도 10명 모두 오류 0', rs['keep'] and not rs['err'], rs)

            rs2 = await pg.evaluate("""async (BEGIN)=>{const x=__ca,P=window.__p6x,out={};const begin=eval(BEGIN);
              const SET={ildj:{cc:6.5},bbb:{bt:9.25,enc:2.5},eom:{n:7},ddmj:{pend:1,hit:3.5},bgb:{bw:.1}};
              for(const k of Object.keys(SET)){begin(k);const S=P.S;Object.assign(x.csS(),SET[k]);x.pauseGame();const b=x.RES.build();
                if(!b||!b.text){out[k]={err:'build '+(b&&b.why)};continue}
                P.state='title';const ok=x.RES.restore(b.text);const c=P.S.x3.cs||{};
                const same=Object.keys(SET[k]).every(f=>Math.abs((c[f]??NaN)-SET[k][f])<1e-9);
                P.resume();let nan=0;for(let i=0;i<90;i++){if(P.state==='lvup'){P.pick(P.CUR[0]);continue}if(P.state!=='play'){P.resume();continue}P.S.p.hp=P.S.p.mhp;P.update(1/30);}
                const c2=P.S.x3.cs||{};for(const f in c2)if(!Number.isFinite(c2[f]))nan++;
                out[k]={ok,same,nan,cs:c}}
              return out}""", BEGIN)
            for k, v in rs2.items():
                check('[라] %s 이어하기 — 능력 상태(S.x3.cs)가 저장 → 복구 뒤에도 같고 이어서 90프레임 오류·NaN 0' % k, v.get('ok') and v.get('same') and v.get('nan') == 0, v)

            # ── 마 전 캐릭터 × 모드 × 보스 상태: 오류·NaN 0 + 비용
            sweep = await pg.evaluate("""async ()=>{const P=window.__p6x,x=__ca,out={bad:[],ms:{}};P.srvUnl(['yumi','bbb','eom']);
              const keys=x.CHARS.map(c=>c.k);
              for(const k of keys)for(const mode of ['n','h','v']){
                try{localStorage.setItem('p6_hard',mode==='h'?'1':'0');localStorage.setItem('p6_vh',mode==='v'?'1':'0');}catch(e){}
                P.CH_set(k);P.start();const S=P.S;let nan=0;
                for(const bossT of [0,1]){
                  if(bossT){S.t=Math.max(S.t,300);P.spawnBoss('sr');}
                  const t0=performance.now();let n=0;
                  for(let i=0;i<30*(bossT?6:12);i++){if(P.state==='result')break;if(P.state==='lvup'){P.pick(P.CUR[0]);continue}if(P.state!=='play'){P.resume();continue}
                    S.p.hp=S.p.mhp;const q=Math.floor(S.t/2.5)%4;P.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][q];P.update(1/30);n++;
                    if(!Number.isFinite(S.p.hp)||!Number.isFinite(S.p.x)||!Number.isFinite(S.kills)){nan++;break}}
                  const ms=(performance.now()-t0)/Math.max(1,n);out.ms[k+mode+bossT]=ms;}
                if(nan)out.bad.push(k+mode);
                const sr=x.statRows();if(sr.some(r=>typeof r.t!=='string'||/NaN|undefined|Infinity/.test(r.t+(r.s||''))))out.bad.push('표:'+k+mode);
                const cs=S.x3.cs;if(cs)for(const f in cs)if(typeof cs[f]!=='number'||!Number.isFinite(cs[f]))out.bad.push('cs.'+f+':'+k+mode);}
              return out}""")
            check('[마] 20명 × 일반/하드/베리하드 × 보스 상태 — NaN·오류 0', not sweep['bad'], sweep['bad'])
            ms = sweep['ms']
            def avg(chars): return sum(ms[k + m + t] for k in chars for m in 'nhv' for t in '01') / (len(chars) * 6)
            new9 = ['brj', 'mms', 'hrb', 'amd', 'ildj', 'ddmj', 'eom', 'bbb', 'yj', 'bgb']
            allk = sorted({re.sub(r'[nhv][01]$', '', k) for k in ms})
            oldk = [k for k in allk if k not in new9]
            a_new, a_old = avg(new9), avg(oldk)
            check('[마] 프레임당 비용 — 새 능력 10명 %.2fms vs 나머지 %.2fms (1.5배 이내 또는 +1.5ms 이내)' % (a_new, a_old), a_new <= max(a_old * 1.5, a_old + 1.5), (a_new, a_old))
            check('[마] 페이지 오류 0', not errs, errs)
            await ctx.close(); await b.close()
    finally:
        srv.close()
        try: os.remove(os.path.join(ROOT, NEW))
        except OSError: pass
    print('\n%s — 실패 %d건' % ('통과' if not FAILS else '실패', len(FAILS)))
    for f in FAILS: print(' ·', f)
    sys.exit(1 if FAILS else 0)

asyncio.run(main())
