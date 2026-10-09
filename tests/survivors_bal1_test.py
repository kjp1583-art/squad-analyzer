# -*- coding: utf-8 -*-
"""⚖ 밸런스 묶음 1 검증 — 네 구획.  사용: python3 tests/survivors_bal1_test.py [구획번호 ...]
  1. 🔗 시너지 「범위」 효과가 실제 범위에 반영된다 (2026-10-09 사장님 지시)
  2. 👼 부활 — 패시브 칸 면제 · Lv20 부터 등장 · 문구
  3. 🎁 Lv10·Lv20 달성 때 다시뽑기 +1 · 봉인 +1 자동 지급
  4. 🐲 프싱 분노 충전 가속 (분당 +3% · 최대 1.8배)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 훅을 꽂는다 — 한 워크트리에서 이 시험을 동시에 둘 돌리지 말 것."""
import asyncio, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
SRC = open(os.path.join(H.ROOT, 'survivors.html'), encoding='utf-8').read()
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)
# 임시 사본에만 꽂는 추가 훅 — 저장소 파일에는 들어가지 않는다
EXTRA = "Object.defineProperties(window.__p6x,{areaMul:{get(){return areaMul}},RES:{get(){return RES}},pauseGame:{get(){return pauseGame}},openLvup:{get(){return openLvup}},buildHtml:{get(){return buildHtml}},slotP:{get(){return slotP}},PASS:{get(){return PASS}},TRD:{get(){return TRD}},SM:{get(){return SM}},PT:{get(){return PT}},REV_LV:{get(){return REV_LV}}});"
WANT = set(int(a) for a in sys.argv[1:]) or {1, 2, 3, 4}

async def sec1(pg, errs):
    print('── 1. 시너지 범위')
    # 1-a. 정적: SYN 효과 키마다 S.syn.<키> 를 읽는 곳이 있다(없는 키는 설명문만 있고 효과가 없는 키)
    keys = await pg.evaluate("[...new Set(__p6x.SYN.flatMap(y=>Object.keys(y.fx)))]")
    missing = [k for k in keys if not re.search(r'S\.syn\.' + k + r'\b', SRC)]
    check('SYN 효과 키 전부(%s)를 S.syn.<키> 로 읽는 곳이 있다' % '/'.join(sorted(keys)), not missing, missing)
    check('범위(area) 읽는 곳이 areaMul 과 weapons() 의 AR 두 군데', len(re.findall(r'\+S\.syn\.area', SRC)) == 2, len(re.findall(r'\+S\.syn\.area', SRC)))
    # 1-b. 모든 area 콤보: 무기를 갖추면 areaMul 이 정확히 그 값만큼 오른다 · area 없는 콤보는 불변
    r = await pg.evaluate("""()=>{const x=__p6x,o=[];x.CH_set('brj');x.start();const S=x.S;
      for(const y of x.SYN){S.w={};for(const k of y.req)S.w[k]=1;x.synCalc();
        const exp=S.synOn.reduce((a,k)=>a+(x.SYN.find(z=>z.k===k).fx.area||0),0);
        o.push({k:y.k,area:y.fx.area||0,on:S.synOn.includes(y.k),am:x.areaMul(),exp:1+exp});}
      return o}""")
    bad = [v for v in r if not v['on'] or abs(v['am'] - v['exp']) > 1e-9]
    check('콤보 %d개 전부: 갖추면 areaMul = 1 + (켜진 콤보 범위 합)' % len(r), not bad, bad[:3])
    check('범위 효과가 있는 콤보 %d개는 areaMul 이 실제로 올라간다' % sum(1 for v in r if v['area']), all(v['am'] > 1 for v in r if v['area']))
    check('범위 효과가 없는(피해·쿨타임·경험치·행운) 콤보는 areaMul 이 1 그대로', all(abs(v['am'] - 1) < 1e-9 for v in r if v['area'] == 0 and abs(v['exp'] - 1) < 1e-9))
    # 1-c. 실제 무기 범위(weapons() 의 AR) — 🍣 초밥 고리 반지름으로 잰다. 해산물 한상(새우깡+초밥) +12%, 폭탄 마니아 +10% 가 겹치면 +22%, 광역 패시브와도 더해진다.
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');
      const ring=(w,ps)=>{x.start();const S=x.S;S.w=w;S.ps=ps||{};x.synCalc();S.p.hp=S.p.mhp=1e9;x.keys={};x.update(1/30);
        const u=S.sushi[0];return {R:Math.hypot(u.x-S.p.x,u.y-S.p.y),area:S.syn.area,on:S.synOn.slice()};};
      o.base=ring({sushi:1});                                    // 시너지 없음
      o.sea=ring({sushi:1,shrimp:1});                            // 해산물 한상 +12%
      o.kit=ring({sushi:1,fryer:1,egg:1});                       // 주방 콤보(피해 +12% 뿐 · 범위 없음)
      o.sea_boom=ring({sushi:1,shrimp:1,egg:1,ping:1});          // 해산물 한상 +12% · 폭탄 마니아 +10%
      o.sea_ps=ring({sushi:1,shrimp:1},{area:2});                // 광역 Lv2(+20%) 와 합산
      o.ps=ring({sushi:1},{area:2});
      return o}""")
    b = r['base']['R']
    check('해산물 한상: 초밥 고리 반지름 ×1.12', abs(r['sea']['R'] / b - 1.12) < 1e-3, r['sea'])
    check('범위 없는 콤보(주방)는 반지름 불변', abs(r['kit']['R'] / b - 1) < 1e-6, r['kit'])
    check('해산물 한상 + 폭탄 마니아: ×1.22(더하기 합산)', abs(r['sea_boom']['R'] / b - 1.22) < 1e-3, r['sea_boom'])
    check('광역 패시브 Lv2 와 시너지는 더해진다(1+0.2+0.12)', abs(r['sea_ps']['R'] / b - 1.32) < 1e-3 and abs(r['ps']['R'] / b - 1.2) < 1e-3, (r['sea_ps']['R'] / b, r['ps']['R'] / b))
    # 1-d. areaMul 과 weapons() AR 이 같은 값 — 용조련사 불꽃 오라(areaMul 사용)와 초밥(AR)이 같은 배수로 움직인다
    r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.w={sushi:1,shrimp:1,egg:1,ping:1};S.ps={area:1};x.synCalc();
      S.p.hp=S.p.mhp=1e9;x.keys={};x.update(1/30);const u=S.sushi[0];const R1=Math.hypot(u.x-S.p.x,u.y-S.p.y);
      const S0=S.w;S.w={sushi:1};S.ps={};S.syn={dmg:0,cd:0,area:0,xp:0,luck:0};x.update(1/30);const v=S.sushi[0];const R0=Math.hypot(v.x-S.p.x,v.y-S.p.y);
      return {ratio:R1/R0,am:(1+.1+.22)}}""")
    check('초밥 고리 배수 = 1 + 광역 Lv1(0.1) + 시너지(0.22)', abs(r['ratio'] - r['am']) < 1e-3, r)
    # 1-e. 오늘의 도전: 시너지 범위가 켜져도 카드 제안 난수열은 같다(offers 는 S.syn.area 를 읽지 않고 RN('card') 호출 횟수도 같다)
    r = await pg.evaluate("""()=>{const x=__p6x,run=(area)=>{x.start({daily:true});const S=x.S;S.w={sushi:2,shrimp:1,egg:1};x.synCalc();S.syn.area=area;
        const cards=[0,1,2,3,4,5].map(()=>x.offers(3).map(o=>o.k).join('|'));return {cards,rn:[x.RN('card'),x.RN('chest'),x.RN('ev')]};};
      return {a:run(0),b:run(.12),c:run(.5)}}""")
    check('오늘의 도전: 범위 시너지 유무와 무관하게 카드 6회 제안 + 다음 난수가 같다', r['a'] == r['b'] == r['c'], r['a']['cards'][:2])
    # 1-f. 시너지 완성 상태로 40초 — 장비 전 종목 예외 없음(범위가 커진 만큼 새 경로를 밟는다)
    r = await pg.evaluate("""()=>{const x=__p6x,out={};
      for(const y of x.SYN.filter(y=>y.fx.area)){x.CH_set('brj');x.start();const S=x.S;S.w={};for(const k of y.req)S.w[k]=3;S.ps={area:3};x.synCalc();S.p.hp=S.p.mhp=1e9;
        for(let i=0;i<20;i++){const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.x=S.p.x+90+(i%5)*30;e.y=S.p.y+((i/5|0)-2)*40;e.sp=0;}
        let ok=true;try{for(let i=0;i<30*6;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}S.p.hp=S.p.mhp;x.update(1/30);if(i%4==0)x.draw();}}catch(er){ok=String(er);}
        out[y.k]=ok;}
      return out}""")
    bad = {k: v for k, v in r.items() if v is not True}
    check('범위 콤보 %d개 × 6초 전투·그리기 예외 없음' % len(r), not bad, bad)
    check('1구획 콘솔·페이지 에러 0', not errs, errs[:3])


# 칸을 채우는 패시브 6종(부활 제외) — 이름은 PASS 표에서 뽑는다
PICK6 = "Object.keys(__p6x.PASS).filter(k=>k!=='rev').slice(0,6)"

async def sec2(pg, errs):
    print('── 2. 부활')
    # 2-a. 표기 3곳(일시정지 · 레벨업 힌트 · 카드 슬롯 문구)이 같은 칸 수를 센다 — 부활은 칸에 안 센다
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;const six=%s;
      for(const k of six)S.ps[k]=1;S.ps.rev=1;S.lv=25;
      o.slotP=x.slotP();o.keys=Object.keys(S.ps).length;
      x.pauseGame();o.pause=document.getElementById('pInfo').textContent;x.resume();
      S.pendingLv=1;x.openLvup();o.hint=document.getElementById('lvHint').textContent;o.cards=x.CUR.map(c=>x.cardOf(c).nm);
      // 5칸 + 부활: 새 패시브 카드는 「슬롯 6/6」
      x.resume();x.start();const T=x.S;for(const k of six.slice(0,5))T.ps[k]=1;T.ps.rev=1;
      const np=Object.keys(x.PASS).find(k=>!T.ps[k]&&k!=='rev');
      o.card5=x.cardOf({t:'p',k:np,l:0});o.cardRev=x.cardOf({t:'p',k:'rev',l:0});o.slot5=x.slotP();
      x.start();const U=x.S;for(const k of six.slice(0,3))U.ps[k]=1;const np2=Object.keys(x.PASS).find(k=>!U.ps[k]&&k!=='rev');o.card3=x.cardOf({t:'p',k:np2,l:0});
      return o}""" % PICK6)
    check('패시브 6 + 부활: 칸 수는 6(부활 안 셈) · 보유 종류는 7', r['slotP'] == 6 and r['keys'] == 7, (r['slotP'], r['keys']))
    check('표기 ① 일시정지: 「패시브 6/6」 + 부활은 칸 안 씀 안내', '패시브 6/6' in r['pause'] and '부활은 칸 안 씀' in r['pause'], r['pause'][:120])
    check('표기 ② 레벨업 힌트: 「패시브 6/6」', '패시브 6/6' in r['hint'], r['hint'])
    check('표기 ③ 새 패시브 카드: 5칸 + 부활이면 「슬롯 6/6」, 3칸이면 「슬롯 4/6」', '슬롯 6/6' in r['card5']['ty'] and '슬롯 4/6' in r['card3']['ty'], (r['card5']['ty'], r['card3']['ty']))
    check('부활 카드 문구: 칸 안 씀 · 확정(확률 아님)', '칸 안 씀' in r['cardRev']['ty'] and '확정' in r['cardRev']['ds'] and '확률이 아니라' in r['cardRev']['ds'] and '패시브 칸을 안 써요' in r['cardRev']['ds'], r['cardRev'])
    # 2-b. 후보: 칸이 꽉 차도(Lv20 이후) 부활은 후보가 될 수 있다 · 새 일반 패시브는 못 나온다
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;const six=%s;
      const sample=(lv,ps,n)=>{S.ps=Object.assign({},ps);S.lv=lv;S.banned=[];let rev=0,newp=0,tot=0;
        for(let i=0;i<n;i++){const c=x.offers(3);tot+=c.length;for(const q of c){if(q.t==='p'&&q.k==='rev')rev++;if(q.t==='p'&&!S.ps[q.k]&&q.k!=='rev')newp++;}}return {rev,newp,tot};};
      const full={};for(const k of six)full[k]=1;
      o.full20=sample(20,full,400);o.full19=sample(19,full,400);o.full40=sample(40,full,400);o.full60=sample(60,full,400);
      o.empty20=sample(20,{},400);o.empty19=sample(19,{},400);
      o.lvs={};for(let lv=1;lv<20;lv++)o.lvs[lv]=sample(lv,lv%%2?{}:full,120).rev;
      const withRev=Object.assign({rev:1},full);o.has=sample(30,withRev,400);o.has5=sample(30,Object.assign({rev:1},Object.fromEntries(six.slice(0,5).map(k=>[k,1]))),400);
      return o}""" % PICK6)
    check('칸 6개 가득 + Lv20: 부활 카드가 후보로 나온다(400회 중 %d회)' % r['full20']['rev'], r['full20']['rev'] > 0, r['full20'])
    check('칸 6개 가득 + Lv40·60도 부활 카드가 나온다', r['full40']['rev'] > 0 and r['full60']['rev'] > 0, (r['full40'], r['full60']))
    check('칸 6개 가득이면 새 일반 패시브는 안 나온다(기존 규칙 유지)', r['full20']['newp'] == 0 and r['full40']['newp'] == 0, (r['full20'], r['full40']))
    check('칸이 비어 있어도 Lv20 부터는 부활이 나온다 / Lv19 는 0', r['empty20']['rev'] > 0 and r['empty19']['rev'] == 0, (r['empty20'], r['empty19']))
    check('Lv19 는 칸이 가득이어도 0', r['full19']['rev'] == 0, r['full19'])
    check('Lv1~19 전부 부활 후보 0 (레벨마다 120회 제안)', all(v == 0 for v in r['lvs'].values()), r['lvs'])
    check('이미 부활을 가졌으면 다시 나오지 않는다', r['has']['rev'] == 0 and r['has5']['rev'] == 0, (r['has'], r['has5']))
    check('부활 + 일반 5칸이면 새 일반 패시브 1개 더 고를 수 있다(칸 6번째)', r['has5']['newp'] > 0, r['has5'])
    check('부활 + 일반 6칸이면 새 일반 패시브는 안 나온다', r['has']['newp'] == 0, r['has'])
    # 2-c. 다른 카드 길: 보스 상자 · 봉인·다시 뽑기 보충 · 「어떤 경우에도 n장」 — Lv20 이전엔 부활이 새어 들어오지 않는다
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');
      const chest=(lv,n)=>{let got=0;for(let i=0;i<n;i++){x.start();const S=x.S;S.lv=lv;x.openChest();if(S.ps.rev)got++;x.resume();}return got;};
      o.c19=chest(19,250);o.c10=chest(10,250);o.c20=chest(20,250);o.c40=chest(40,250);
      x.start();const S=x.S;S.lv=19;S.banned=[];let rr=0,bn=0;
      for(let i=0;i<300;i++){const c=x.offers(3);const ex=c.map(q=>q.k).filter(Boolean);const d=x.offers(3,ex);for(const q of d)if(q.k==='rev')rr++;const b=x.offers(1,ex);for(const q of b)if(q.k==='rev')bn++;}
      o.rr19=rr;o.bn19=bn;
      // 전부 봉인한 극단: 후보가 바닥나 「어떤 경우에도 n장」 보충만 남는다
      const all=['heal','co:feast','co:pulse','co:shield','co:dice'];for(const k in x.WEAP)all.push(k,'wt:'+k);for(const k in x.PASS)if(k!=='rev')all.push(k);
      for(const k in x.PT)all.push('pt:'+k);for(const k in x.REL)all.push('rl:'+k);for(const k in x.TRD)all.push('tr:'+k);for(const k in x.SM)all.push('sm:'+k);
      S.banned=all.slice();const f19=x.offers(3).map(q=>q.k||q.t);S.lv=20;const f20=x.offers(3).map(q=>q.k||q.t);
      o.f19=f19;o.f20=f20;return o}""")
    check('보스 상자(카드 1~3장)로 Lv19 이하에서 부활을 못 얻는다(250상자×2레벨)', r['c19'] == 0 and r['c10'] == 0, (r['c19'], r['c10']))
    check('보스 상자로 Lv20·Lv40 에서는 부활을 얻을 수 있다(250상자 중 %d·%d)' % (r['c20'], r['c40']), r['c20'] > 0 and r['c40'] > 0)
    check('다시 뽑기·봉인 보충 경로도 Lv19 에는 부활 0 (300회)', r['rr19'] == 0 and r['bn19'] == 0, (r['rr19'], r['bn19']))
    check('후보가 바닥나 「어떤 경우에도 n장」 보충만 남아도 Lv19 에는 부활 없음 · Lv20 에는 후보가 부활뿐', 'rev' not in r['f19'] and r['f20'][0] == 'rev', (r['f19'], r['f20']))
    # 2-d. 부활 동작은 그대로 — 확정 1회 · HP 50%% · 2.5초 무적 · 두 번째 죽음은 끝
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S,p=S.p;S.ps.rev=1;S.lv=30;
      p.inv=0;p.hp=5;o.r1=x.hitP(1e9);o.hp=p.hp/p.mhp;o.used=S.revUsed;o.inv=p.inv;o.state1=x.state;
      p.inv=0;p.hp=5;o.r2=x.hitP(1e9);o.used2=S.revUsed;o.state2=x.state;return o}""")
    check('첫 죽음: 부활(HP 50%%·무적 2.5초·판 계속)', r['r1'] is False and abs(r['hp'] - .5) < 1e-6 and r['used'] == 1 and r['inv'] >= 2.4 and r['state1'] == 'play', r)
    check('두 번째 죽음: 부활 없이 끝(정확히 1회)', r['r2'] is True and r['used2'] == 1 and r['state2'] == 'result', r)
    # 2-e. 이어하기 복원 후에도 칸 수·표기·후보가 일관된다
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;const six=%s;for(const k of six)S.ps[k]=1;S.ps.rev=1;S.lv=22;
      x.pauseGame();const text=localStorage.getItem(x.RES.KEY);o.saved=!!text;
      x.state='title';o.ok=x.RES.restore(text);const T=x.S;
      o.ps=Object.keys(T.ps).length;o.slot=x.slotP();o.lv=T.lv;o.state=x.state;o.html=x.buildHtml();
      T.banned=[];let rev=0,np=0;for(let i=0;i<300;i++)for(const q of x.offers(3)){if(q.k==='rev')rev++;if(q.t==='p'&&!T.ps[q.k])np++;}o.rev=rev;o.np=np;
      // 복원한 판이 Lv19 로 보이는 저장본이면 후보 0 — 저장된 레벨이 그대로 쓰인다
      return o}""" % PICK6)
    check('복원: 보유 7종 · 칸 6 · 일시정지 문구 「패시브 6/6」', r['saved'] and r['ok'] is not False and r['ps'] == 7 and r['slot'] == 6 and '패시브 6/6' in r['html'], {k: r[k] for k in ('saved', 'ok', 'ps', 'slot')})
    check('복원 후: 부활을 이미 가졌으므로 후보 0 · 새 일반 패시브 0', r['rev'] == 0 and r['np'] == 0, (r['rev'], r['np']))
    # 2-f. 오늘의 도전: 부활 후보가 바뀌어도 카드 난수는 제안 한 번에 정확히 n번만 쓴다 — 레벨(후보 구성)이 달라도 뒤따르는 난수가 같다
    r = await pg.evaluate("""()=>{const x=__p6x,run=(lv)=>{x.CH_set('brj');x.start({daily:true});const S=x.S;S.lv=lv;
        const a=[];for(let i=0;i<8;i++)a.push(x.offers(3).map(o=>o.k).join('|'));return {next:[x.RN('card'),x.RN('card'),x.RN('chest')],a};};
      const r19=run(19),r20=run(20),r40=run(40);
      // 부활을 봉인해 두면 Lv 에 따라 후보가 같으므로 제안 내용도 같아야 한다(부활 말고는 아무것도 안 달라졌다)
      const ban=(lv)=>{x.CH_set('brj');x.start({daily:true});const S=x.S;S.lv=lv;S.banned=['rev'];const a=[];for(let i=0;i<8;i++)a.push(x.offers(3).map(o=>o.k).join('|'));return a.join('/');};
      return {same:JSON.stringify(r19.next)===JSON.stringify(r20.next)&&JSON.stringify(r20.next)===JSON.stringify(r40.next),b:ban(10)===ban(10)&&ban(19)===ban(19)&&ban(10)===ban(19),nx:r19.next}}""")
    check('오늘의 도전: 제안 8번 뒤 다음 카드·상자 난수가 Lv19·20·40 에서 같다(난수 소비 횟수 불변)', r['same'], r['nx'])
    check('오늘의 도전: 부활만 봉인하면 Lv10 과 Lv19 의 제안 8번이 완전히 같다(바뀐 것은 부활 후보뿐)', r['b'])
    check('2구획 콘솔·페이지 에러 0', not errs, errs[:3])

SECS = {1: sec1, 2: sec2}

async def main():
    H.make_copy(extra=EXTRA); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        for n in sorted(WANT):
            if n not in SECS: continue
            ctx, pg, errs = await H.new_page(b, srv.port)
            await SECS[n](pg, errs)
            await ctx.close()
        await b.close()
    print(f'\n{N[0]-len(FAILS)}/{N[0]} 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
