# -*- coding: utf-8 -*-
"""🏺 흐접새우 시그니처 유물·캐릭터 고유능력 감사 시험 — 2026-10-16 (클랜원 제보 「유물 3개 다 먹어도 변신 3.5초 늘어나는데 효과가 너무 미미하다」 외 일반화)
   사용: python3 tests/survivors_relic_audit_test.py     (종료코드 0 = 전부 통과)
   구성
     가  문구 = 값 — 유물 문구(REL.ds)가 SGV 의 숫자를 그대로 읽는다(값을 바꾸면 문구가 따라 바뀐다)
     나  스케일링 — 📏 광역(areaMul)·⏳ 끈기(DUR)·⏱ 공격속도(cdMul)·💥 피해가 캐릭터 능력·유물에 빠짐없이 적용된다
     다  유물 동작 — 새 값으로 문구와 같은 크기로 동작한다(경계값 포함)
     라  변이 — 코드를 옛 식으로 되돌린 사본에서는 위 시험이 반드시 빨갛게 된다(시험이 진짜로 막고 있다는 증명)
     마  연기 — 13명 × 유물 1·2·3단계 × 일반/하드, 오류·NaN 0
   임시 사본 survivors_cb_relic*.html 에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)

EXTRA = r"""
window.__ra={SGV,REL,CSK,CSX,CHARS,areaMul,DUR,cdMul,dmgMul,critMul,csShock,csPc,csNum,rageMul,rageCap,allies,get CH(){return CH},get S(){return S}};
"""
BEGIN = """(k)=>{const P=window.__p6x;P.srvUnl&&P.srvUnl(['yumi','bbb','eom']);P.CH_set(k);P.start();const S=P.S;S.spawnT=-1e12;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;S.propT=S.chickT=1e12;
  for(const q of P.enemies.a)q.on=false;S.w={};S.p.hp=S.p.mhp;P.keys={};if(P.CH.k!==k)throw new Error('캐릭터가 안 바뀜 '+k);return true}"""

# 한 번에 도는 탐침 — 값은 전부 페이지 안의 SGV·CSK·CSX 에서 읽는다(시험이 숫자를 따로 갖지 않는다)
PROBES = {
 'text': """()=>{const x=__ra,S=x.SGV,pc=x.csPc,nm=x.csNum;const out=[];const want={
   sg_brj:l=>[pc(S.brj.p[l-1])],sg_jjg:l=>[S.jjg.n[l-1],pc(S.jjg.f)],sg_mms:l=>[pc(S.mms.hp),S.mms.t[l-1],pc(S.mms.f[l-1])],
   sg_hrb:l=>[S.hrb.t[l-1],S.hrb.r[l-1],S.hrb.sl],sg_ssu:l=>[S.ssu.t[l-1],pc(S.ssu.f[l-1])],sg_amd:l=>[S.amd.r[l-1],S.amd.t],
   sg_ildj:l=>[pc(S.ildj.p[l-1])],sg_kyo:l=>[pc(S.kyo.f[l-1]),pc(S.kyo.e[l-1]),S.kyo.ecd],sg_ddmj:l=>[pc(S.ddmj.k[l-1]),S.ddmj.r,S.ddmj.n],
   sg_sr:l=>[S.sr.d[l-1],S.sr.e[l-1]],sg_ddo:l=>[pc(S.ddo.R[l-1]),pc(S.ddo.d[l-1])],sg_tw:l=>[nm(1+S.tw.sl[l-1]),pc(S.tw.cap[l-1])],
   sg_bgb:l=>[S.bgb.n[l-1],S.bgb.m[l-1]]};
   for(const k in want)for(const l of [1,2,3]){const t=x.REL[k].ds(l);for(const w of want[k](l))if(!t.includes(String(w)))out.push(k+' Lv'+l+' 문구에 '+w+' 없음: '+t);}
   return {out,keys:Object.keys(want).length}}""",
 'brj': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('brj')&&P.S;S.rel.sg_brj=3;S.lv=30;S.ps.area=2;S.pt.area=1;S.syn.area=.1;
   const rn=Math.random;Math.random=()=>0;const e=P.spawnEnemy(0,1);e.x=S.p.x+50;e.y=S.p.y;e.hp=1;S.t+=1;const n0=S.booms.length;P.hurt(e,99);Math.random=rn;
   const b=S.booms.filter(b=>b.src==='rel')[0];if(!b)return {none:1};
   return {R:b.R,wantR:x.SGV.brj.R*x.areaMul(),d:b.d,wantD:x.SGV.brj.d*(1+S.lv/x.SGV.brj.lv)*x.dmgMul()*x.SGV.brj.dm[2],area:x.areaMul()}}""",
 'hrb': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('hrb')&&P.S;S.rel.sg_hrb=3;const V=x.SGV.hrb;
   const mk=(d)=>{const e=P.spawnEnemy(0,1);e.x=S.p.x+d;e.y=S.p.y;e.hp=e.mhp=1e9;e.sp=0;e.slow=0;return e};
   const run=(ps)=>{S.ps.area=ps.area||0;S.ps.dur=ps.dur||0;S.sgT.hrb=0;S.p.moving=true;const es=[mk(60),mk(V.r[2]-30),mk(V.r[2]+40),mk(V.r[2]*1.5)];const B=P.spawnEnemy(0,1,{key:'t',nm:'t',r:20,sp:0,d:1,hp:1e9,xp:1});B.x=S.p.x+80;B.y=S.p.y;B.hp=B.mhp=1e9;B.slow=0;
     S.live=es.concat([B]);P.sgTick(.01);const r={sl:es.map(e=>e.slow>0),boss:B.slow>0,t:es[0].slow,dur:x.DUR()};B.on=false;return r};
   const a=run({}),b=run({area:3,dur:3});S.p.moving=false;S.sgT.hrb=0;const es=[mk(60)];S.live=es;P.sgTick(1);
   return {a,b,still:es[0].slow>0,V}}""",
 'mms': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('mms')&&P.S;S.rel.sg_mms=3;const V=x.SGV.mms;
   const go=(frac)=>{const E=P.spawnEnemy(0,1);E.x=S.p.x+60;E.y=S.p.y;E.hp=E.mhp=1000;E.sp=0;S.live=[E];S.p.hp=S.p.mhp*frac;S.sgT.mms=undefined;for(let i=0;i<Math.ceil(V.t[2]*10)+2;i++){S.p.hp=S.p.mhp*frac;P.sgTick(.1);}return 1000-E.hp};
   return {low:go(V.hp-.02),edge:go(V.hp+.02),V}}""",
 'kyo': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('kyo')&&P.S;S.rel.sg_kyo=3;const V=x.SGV.kyo;
   const el=()=>{const e=P.spawnEnemy(0,1);e.x=S.p.x+50;e.y=S.p.y;e.el=1;e.hp=e.mhp=1;return e};
   S.p.hp=10;let e=el();P.hurt(e,5);const h1=S.p.hp-10;e=el();const h0=S.p.hp;P.hurt(e,5);const h2=S.p.hp-h0;
   S.t+=V.ecd+.1;e=el();const h3b=S.p.hp;P.hurt(e,5);const h3=S.p.hp-h3b;
   const n=P.spawnEnemy(0,1);n.x=S.p.x+50;n.y=S.p.y;n.hp=n.mhp=1;const h4b=S.p.hp;S.t+=.01;P.hurt(n,5);const h4=S.p.hp-h4b;   // 보통 몹은 회복 없음
   return {h1,h2,h3,h4,want:Math.round(S.p.mhp*V.e[2]),mhp:S.p.mhp}}""",
 'ddmj': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('ddmj')&&P.S;S.rel.sg_ddmj=3;S.lv=30;const V=x.SGV.ddmj;
   const mk=(d)=>{const e=P.spawnEnemy(0,1);e.x=S.p.x+d;e.y=S.p.y;e.hp=e.mhp=1e9;e.sp=0;return e};
   const e0=mk(60),e1=mk(V.r+30),e2=mk(V.r*1.6+30);S.live=[e0,e1,e2];S.p.inv=0;const dm=10;P.sgThorns(dm);const a=[e0,e1,e2].map(e=>e.mhp-e.hp);
   const want=dm*V.k[2]+V.b[2]*(1+S.lv/15)*x.dmgMul();
   for(const e of S.live)e.hp=e.mhp;S.ps.area=3;P.sgThorns(dm);const b=[e0,e1,e2].map(e=>e.mhp-e.hp);return {a,b,want,r:V.r,area:x.areaMul()}}""",
 'tw': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('tw')&&P.S;const V=x.SGV.tw;S.p.hp=S.p.mhp*.5;const m0=x.rageMul(),c0=x.rageCap();
   S.rel.sg_tw=3;const m3=x.rageMul(),c3=x.rageCap();S.p.hp=S.p.mhp*.05;const m5=x.rageMul();return {m0,m3,c0,c3,m5,V,base:x.CH.rage}}""",
 'jjg': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('jjg')&&P.S;S.rel.sg_jjg=3;const cr=x.CH.crit;x.CH.crit=1;const V=x.SGV.jjg;
   const es=[];for(let i=0;i<4;i++){const e=P.spawnEnemy(0,1);e.x=S.p.x+40+i*5;e.y=S.p.y+10;e.hp=e.mhp=1e9;e.sp=0;es.push(e)}
   S.live=[es[1]];const b0=es[0].hp;P.hurt(es[0],10);const one=b0-es[0].hp;for(let i=1;i<V.n[2];i++)P.hurt(es[0],10);
   const ex=es[1].mhp-es[1].hp;x.CH.crit=cr;return {one,ex,c:S.sgC,f:V.f,cm:x.critMul()}}""",
 'bgb': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('bgb')&&P.S;S.rel.sg_bgb=3;const V=x.SGV.bgb;S.p.hp=S.p.mhp=1e9;S.p.inv=99;
   const es=[];for(let k=0;k<6;k++){const q=P.spawnEnemy(0,1);q.sp=0;q.hp=q.mhp=1e12;q.x=S.p.x+80+k;q.y=S.p.y+k*9;es.push(q)}S.live=es;
   const base=Math.PI/3;let fired=[];for(let i=0;i<V.n[2]+1;i++){const b=S.sgT.bgbN||0;P.sgFan(1,100,1,base);fired.push((S.sgT.bgbN||0)>b?1:0)}return {fired,V}}""",
 'sr': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('sr')&&P.S;S.rel.sg_sr=2;S.ps.cd=2;S.ps.dur=4;const V=x.SGV.sr;S.staffT=0;P.update(1/30);
   const cd=S.staffT,want=(x.CSK.staff.every-V.e[1])*x.cdMul(),life=Math.max(...x.allies.a.filter(a=>a.on).map(a=>a.life)),wl=(x.CSK.staff.life+V.d[1])*x.DUR();
   // 범위: 스탭 곁 (e.r+34)×광역 안쪽만 맞는다
   for(const a of x.allies.a)a.on=false;S.ps.area=3;S.ps.cd=0;S.ps.dur=0;S.staffT=1e9;const a=x.allies.get();const t=P.spawnEnemy(0,1);t.hp=t.mhp=1e9;t.sp=0;t.x=S.p.x+200;t.y=S.p.y;
   a.x=t.x-(t.r+8);a.y=t.y;a.life=5;a.cd=0;a.tg=t;a.tsn=t.sn;a.rt=1;a.side=1;a.hit=0;
   const o=P.spawnEnemy(0,1);o.hp=o.mhp=1e9;o.sp=0;o.x=a.x;o.y=a.y+o.r+34*(1+(x.areaMul()-1)/2);   // 광역 없으면 밖 · 있으면 안
   S.live=[t,o];const oh=o.hp;P.update(1/30);return {cd,want,life,wl,out:oh-o.hp,ar:x.areaMul()}}""",
 'ddo': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('ddo')&&P.S;S.rel.sg_ddo=2;S.ps.area=2;S.pt.area=1;S.syn.area=.1;S.ps.dur=4;S.ps.cd=3;const V=x.SGV.ddo;
   const e=P.spawnEnemy(0,1);e.x=S.p.x+100;e.y=S.p.y;e.hp=e.mhp=1e9;e.sp=0;S.live=[e];S.proomT=0;P.update(1/30);
   const o=S.proom,rh=x.CSK.room.hold*x.DUR();return {R:o.R,wantR:x.CSK.room.R*x.areaMul()*(1+V.R[1]),t:o.t,wantT:rh,every:S.proomT,wantE:x.CSK.room.every*x.cdMul(),st:e.st,area:x.areaMul(),T:o.T,rh}}""",
 'shock': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('eom')&&P.S;S.ps.area=2;S.pt.area=1;S.syn.area=.1;const X=x.CSX.eom;S.x3.cs=S.x3.cs||{n:0,cc:0,hit:-9,bt:0,enc:0,bw:0};
   const e=P.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.sp=0;e.kr=0;const Rn=X.R*x.areaMul(),Ro=X.R*(1+.1*2);e.x=S.p.x+Rn+e.r-2;e.y=S.p.y;S.live=[e];S.x3.cs.n=X.n;const h0=e.hp;P.update(1/30);
   return {dmg:h0-e.hp,Rn,Ro,e:e.r}}""",
 'dur2': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);let S=begin('ildj')&&P.S;S.ps.dur=4;S.need=1;S.xp=0;P.gainXp(5);const cc=S.x3.cs.cc,wcc=x.CSX.ildj.T*x.DUR();
   S=begin('bbb')&&P.S;S.ps.dur=4;S.x3.cs=S.x3.cs||{n:0,cc:0,hit:-9,bt:0,enc:0,bw:0};S.x3.cs.bt=x.CSX.bbb.every;P.update(1/30);return {cc,wcc,enc:S.x3.cs.enc,wenc:x.CSX.bbb.T*x.DUR()}}""",
 'ddcd': """(BEGIN)=>{const P=window.__p6x,x=__ra;const begin=eval(BEGIN);const S=begin('ddmj')&&P.S;S.ps.cd=4;S.x3.cs=S.x3.cs||{n:0,cc:0,hit:-9,bt:0,enc:0,bw:0};S.t=50;S.x3.cs.hit=S.t-x.CSX.ddmj.cd*.8;S.p.inv=0;S.p.hp=S.p.mhp;
   const ok=x.cdMul()*x.CSX.ddmj.cd<x.CSX.ddmj.cd*.8;P.hitP(1,'');return {pend:S.x3.cs.pend,ok,cd:x.cdMul()}}""",
}

def judge(R):
    """탐침 결과 → 검사. 이름 앞의 [라벨]은 변이 시험이 어느 검사가 빨개져야 하는지 가리키는 데 쓴다."""
    res = []
    def c(n, ok, x=''): res.append((n, bool(ok), x))
    t = R['text']; c('[문구] 13개 유물 × 3단계의 문구가 SGV 숫자를 그대로 담는다', t['keys'] == 13 and not t['out'], t['out'][:4])
    b = R['brj']; c('[브장신 점화] 폭발 반경이 광역(초월·시너지 포함)을 받고 피해가 레벨·피해 배율을 따라 자란다', 'R' in b and abs(b['R'] - b['wantR']) < 1e-6 and abs(b['d'] - b['wantD']) < 1e-6 and b['area'] > 1.3, b)
    h = R['hrb']; V = h['V']
    c('[하리보 발자국] 반경 안의 적은 전부 느려지고(보스·밖은 제외) 이동 중에만 켜진다', h['a']['sl'] == [True, True, False, False] and not h['a']['boss'] and not h['still'], h['a'])
    c('[하리보 발자국] 반경이 광역을 받는다', h['b']['sl'] == [True, True, True, False] and not h['b']['boss'], h['b'])
    c('[하리보 발자국] 느려지는 시간이 끈기를 받는다', abs(h['a']['t'] - V['sl']) < 1e-6 and abs(h['b']['t'] - V['sl'] * h['b']['dur']) < 1e-6 and h['b']['dur'] > 1.4, (h['a']['t'], h['b']['t'], h['b']['dur']))
    m = R['mms']; c('[망무새 파동] HP 절반 이하에서만 펄스(경계 안 −2%p는 켜지고 +2%p는 꺼진다)', m['low'] > 0 and m['edge'] == 0, m)
    k = R['kyo']; c('[김야옹 쿠폰] 정예 처치도 회복 · 쿨 안에선 회복 없음 · 쿨 뒤 다시 · 보통 몹은 없음', k['h1'] == k['want'] and k['h2'] == 0 and k['h3'] == k['want'] and k['h4'] == 0, k)
    d = R['ddmj']; w = d['want']
    c('[가시 방패] 받은 피해 몫 + 레벨·피해 배율을 따라 자라는 가시를 돌려준다', abs(d['a'][0] / w - 1) < .01 and w > 10 * .1, d)
    c('[가시 방패] 반경이 광역을 받는다(기본 반경 밖의 적은 광역이 있을 때만 맞는다)', d['a'][1] == 0 and d['a'][2] == 0 and d['b'][1] > 0 and d['b'][2] == 0, d)
    t = R['tw']; c('[집착의 불꽃] 잃은 체력 1%당 피해 기울기와 상한이 함께 오른다', t['m0'] < t['m3'] and abs(t['m0'] - 1.5) < 1e-9 and abs(t['m3'] - (1 + min(t['c3'], .5 * (1 + t['V']['sl'][2])))) < 1e-9 and abs(t['c3'] - t['c0'] - t['V']['cap'][2]) < 1e-9 and abs(t['m5'] - (1 + t['c3'])) < 1e-9, t)
    j = R['jjg']; c('[한 방 장전] n번째 치명타에 다른 적 하나가 방금 치명타 피해의 f 배를 맞고 카운터 리셋', j['c'] == 0 and abs(j['ex'] / j['one'] - j['f'] * j['cm']) < 1e-6, j)
    g = R['bgb']; c('[한 장씩 줄게] n번째 던짐에서 사방 카드 · 그 사이엔 조용', sum(g['fired']) == 1 and g['fired'][g['V']['n'][2] - 1] == 1, g)
    s = R['sr']
    c('[스탭 임명] 주기가 공격속도를, 지속이 끈기를 받는다', abs(s['cd'] - s['want']) < 1e-6 and abs(s['life'] - s['wl']) < .05, s)
    c('[스탭 임명] 후려치는 범위가 광역을 받는다', s['out'] > 0 and s['ar'] > 1.2, s)
    o = R['ddo']
    c('[진실의 방] 범위가 광역(초월·시너지 포함)을, 시간이 끈기를, 주기가 공격속도를 받는다', abs(o['R'] - o['wantR']) < 1e-6 and abs(o['t'] - (o['wantT'] - 1 / 30)) < 1e-6 and abs(o['every'] - o['wantE']) < 1e-6 and o['area'] > 1.3, o)
    c('[진실의 방] 묶는 시간이 끈기로 늘어난 시간과 같다', abs(o['st'] - o['rh']) < .05, o)
    z = R['shock']; c('[충격파] 엄장신 연쇄 반경이 광역(초월·시너지 포함)을 받는다', z['dmg'] > 0 and z['Rn'] > z['Ro'], z)
    u = R['dur2']; c('[끈기] 커튼콜·후렴 시간이 끈기를 받는다', abs(u['cc'] - u['wcc']) < 1e-6 and abs(u['enc'] - u['wenc']) < 1e-6 and u['wcc'] > 12, u)
    q = R['ddcd']; c('[반격 쿨] 단단묵직 반격 쿨이 공격속도를 받는다', q['ok'] and q['pend'] == 1, q)
    return res

# 변이 — 옛 식으로 되돌린 사본. (옛 조각, 새 조각 → 되돌릴 때 옛 조각을 넣는다) 기대: 이름에 라벨이 든 검사가 빨개져야 한다.
MUTANTS = [
 ('충격파 반경을 옛 식(패시브 단계만)으로', "SRC='char';R*=areaMul();", "SRC='char';R*=1+.1*pv('area');", '[충격파]'),
 ('진실의 방 시간에서 끈기 제거', "const rh=CSK.room.hold*DUR();", "const rh=CSK.room.hold;", '[진실의 방]'),
 ('진실의 방 반경을 옛 식으로', "o.R=CSK.room.R*areaMul()*", "o.R=CSK.room.R*(1+.1*pv('area'))*", '[진실의 방]'),
 ('스탭 주기에서 공격속도 제거', "S.staffT=(CSK.staff.every-(SGN('sg_sr')?SGV.sr.e[SGN('sg_sr')-1]:0))*cdMul();", "S.staffT=(CSK.staff.every-(SGN('sg_sr')?SGV.sr.e[SGN('sg_sr')-1]:0));", '[스탭 임명]'),
 ('스탭 지속에서 끈기 제거', "a.life=(CSK.staff.life+(SGN('sg_sr')?SGV.sr.d[SGN('sg_sr')-1]:0))*DUR();", "a.life=(CSK.staff.life+(SGN('sg_sr')?SGV.sr.d[SGN('sg_sr')-1]:0));", '[스탭 임명]'),
 ('스탭 범위에서 광역 제거', "<(e.r+34*ar)**2)hurt(e,dmg);", "<(e.r+34)**2)hurt(e,dmg);", '[스탭 임명]'),
 ('하리보 반경에서 광역 제거', "const rr=SGV.hrb.r[R.sg_hrb-1]*areaMul(),", "const rr=SGV.hrb.r[R.sg_hrb-1],", '[하리보 발자국]'),
 ('하리보 느려짐에서 끈기 제거', ",sl=SGV.hrb.sl*DUR();", ",sl=SGV.hrb.sl;", '[하리보 발자국]'),
 ('커튼콜에서 끈기 제거', "csS().cc=CSX.ildj.T*DUR();", "csS().cc=CSX.ildj.T;", '[끈기]'),
 ('후렴에서 끈기 제거', "c.enc=X.T*DUR();", "c.enc=X.T;", '[끈기]'),
 ('반격 쿨에서 공격속도 제거', "S.t-c.hit>=CSX.ddmj.cd*cdMul()", "S.t-c.hit>=CSX.ddmj.cd", '[반격 쿨]'),
 ('가시 반경에서 광역 제거', "rr=SGV.ddmj.r*areaMul();let n=0;", "rr=SGV.ddmj.r;let n=0;", '[가시 방패]'),
 ('가시 피해에서 고정 몫 제거', "const d=dm*k+SGV.ddmj.b[L]*(1+S.lv/15)*dmgMul();", "const d=dm*k;", '[가시 방패]'),
 ('점화 반경을 옛 식으로', "R:SGV.brj.R*areaMul(),", "R:SGV.brj.R*(1+.1*pv('area')),", '[브장신 점화]'),
 ('망무새 문턱을 30%로', "p.hp<=p.mhp*SGV.mms.hp", "p.hp<=p.mhp*.3", '[망무새 파동]'),
 ('정예 회복 제거', "(e.el||e.bg)&&S.t-(S.sgT.kyo===undefined?-9:S.sgT.kyo)>=SGV.kyo.ecd", "false&&(e.el||e.bg)&&S.t-(S.sgT.kyo===undefined?-9:S.sgT.kyo)>=SGV.kyo.ecd", '[김야옹 쿠폰]'),
 ('태웅 기울기 제거', "Math.max(0,1-S.p.hp/S.p.mhp)*(1+(SGN('sg_tw')?SGV.tw.sl[SGN('sg_tw')-1]:0))", "Math.max(0,1-S.p.hp/S.p.mhp)", '[집착의 불꽃]'),
]

async def run_probes(pg):
    out = {}
    for k, js in PROBES.items():
        out[k] = await (pg.evaluate(js) if k == 'text' else pg.evaluate(js, BEGIN))
    return out

async def main():
    H.make_copy(src='survivors.html', dst='survivors_cb_relic.html', extra=EXTRA)
    srv = H.Srv()
    muts = []
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, 1280, 720, page='survivors_cb_relic.html', ready='__ra')
            await pg.wait_for_timeout(400)
            R = await run_probes(pg)
            base = judge(R)
            for n, ok, x in base: check(n, ok, x)
            check('페이지 오류 0', not errs, errs[:3])
            # 마 연기 — 13명 × 유물 3단계 × 일반/하드
            r = await pg.evaluate("""async ()=>{const P=window.__p6x,x=__ra;const RK={brj:'sg_brj',jjg:'sg_jjg',mms:'sg_mms',hrb:'sg_hrb',ssu:'sg_ssu',amd:'sg_amd',ildj:'sg_ildj',kyo:'sg_kyo',ddmj:'sg_ddmj',sr:'sg_sr',ddo:'sg_ddo',tw:'sg_tw',bgb:'sg_bgb'};const bad=[];let runs=0;
              for(const ch in RK)for(let L=1;L<=3;L++)for(const hard of [0,1]){
                P.srvUnl&&P.srvUnl(['yumi','bbb','eom']);P.CH_set(ch);P.start();const S=P.S;S.rel[RK[ch]]=L;S.p.mhp=S.p.hp=Math.max(S.p.mhp,200);S.ps.area=2;S.ps.dur=2;S.ps.cd=2;S.ps.amt=1;if(hard)S.t=900;runs++;
                try{for(let i=0;i<30*30;i++){if(P.state==='lvup'){P.pick(P.CUR[0]);continue;}if(P.state!=='play'){P.resume();continue;}if(i%7==0)S.p.hp=Math.max(S.p.hp,S.p.mhp*(i%3?.25:.9));P.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][(i/60|0)%4];P.update(1/30);
                  if(!Number.isFinite(S.p.hp)||!Number.isFinite(S.p.x)){bad.push(ch+L+' NaN');break;}}}catch(e){bad.push(ch+L+' '+e)}}
              return {bad,runs}}""")
            check('[연기] 13명 × 유물 1·2·3단계 × 시작/후반 시각(%d판) — 오류·NaN 0' % r['runs'], not r['bad'] and r['runs'] == 78, r)
            # 라 변이
            src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
            for nm, new, old, label in MUTANTS:
                if src.count(new) != 1:
                    check('[변이] 고칠 조각을 찾지 못함: ' + nm, False, (src.count(new), new[:60])); continue
                open(os.path.join(ROOT, 'survivors_cb_relic_m.html'), 'w', encoding='utf-8').write(src.replace(new, old))
                H.make_copy(src='survivors_cb_relic_m.html', dst='survivors_cb_relic_mx.html', extra=EXTRA)
                ctx2, pg2, errs2 = await H.new_page(b, srv.port, 1280, 720, page='survivors_cb_relic_mx.html', ready='__ra')
                try:
                    R2 = await run_probes(pg2)
                    red = [n for n, ok, x in judge(R2) if not ok]
                except Exception as e:
                    red = ['예외 ' + str(e)[:80]]
                await ctx2.close()
                check('[변이] %s → %s 가 빨개진다' % (nm, label), any(label in n for n in red) or any(n.startswith('예외') for n in red), red[:4])
    finally:
        srv.close()
        for f in ('survivors_cb_relic.html', 'survivors_cb_relic_m.html', 'survivors_cb_relic_mx.html'):
            try: os.remove(os.path.join(ROOT, f))
            except Exception: pass
    print('\n%d개 실패' % len(FAILS) if FAILS else '\n전부 통과')
    return 1 if FAILS else 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
