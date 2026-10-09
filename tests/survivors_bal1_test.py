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
EXTRA = "Object.defineProperties(window.__p6x,{areaMul:{get(){return areaMul}},RES:{get(){return RES}},pauseGame:{get(){return pauseGame}},openLvup:{get(){return openLvup}},buildHtml:{get(){return buildHtml}},slotP:{get(){return slotP}},PASS:{get(){return PASS}},charTick:{get(){return charTick}},rgMul:{get(){return rgMul}},shvEnd:{get(){return shvEnd}},TRD:{get(){return TRD}},SM:{get(){return SM}},PT:{get(){return PT}},REV_LV:{get(){return REV_LV}}});"
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


async def sec3(pg, errs):
    print('── 3. Lv10·Lv20 보너스')
    # 3-a. 레벨마다 한 레벨씩 올리며 다시 뽑기·봉인 변화를 잰다 — 10·20 에서만 +1/+1
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;const d={};
      for(let lv=2;lv<=45;lv++){const a=[S.rr,S.ban];x.gainXp(S.need);d[S.lv]=[S.rr-a[0],S.ban-a[1]];S.pendingLv=0;}
      o.d=d;o.rr=S.rr;o.ban=S.ban;return o}""")
    bonus = {k: v for k, v in r['d'].items() if v != [0, 0]}
    check('Lv2~45 한 레벨씩: +1/+1 은 Lv10·Lv20 에서만', bonus == {'10': [1, 1], '20': [1, 1]}, bonus)
    check('시작 3+3 에 두 번 받아 5·5', r['rr'] == 5 and r['ban'] == 5, (r['rr'], r['ban']))
    # 3-b. 한 번에 여러 레벨이 올라도(경험치 폭식) 10·20 을 건너뛰지 않는다
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');
      const jump=(from,xp)=>{x.start();const S=x.S;S.lv=from;S.need=1;S.xp=0;x.gainXp(xp);return {lv:S.lv,rr:S.rr-3,ban:S.ban-3,pend:S.pendingLv};};
      o.j8_25=jump(8,3000);o.j9_10=jump(9,3000);return o}""")
    # 경험치 3000 을 한 번에 넣어 Lv30 대까지 올린다 — 올라간 구간 안의 보너스 레벨 수만큼 받았는지 센다
    cnt = lambda a, b: sum(1 for v in (10, 20) if a < v <= b)
    exp25 = cnt(8, r['j8_25']['lv']); exp10 = cnt(9, r['j9_10']['lv'])
    check('Lv8 → Lv%d 한 번에: 지나간 보너스 레벨 %d개 → +%d/+%d' % (r['j8_25']['lv'], exp25, exp25, exp25), exp25 >= 1 and r['j8_25']['rr'] == exp25 and r['j8_25']['ban'] == exp25 and r['j8_25']['pend'] == r['j8_25']['lv'] - 8, r['j8_25'])
    check('Lv9 → Lv%d 한 번에도 같은 규칙' % r['j9_10']['lv'], r['j9_10']['rr'] == exp10 and r['j9_10']['ban'] == exp10, r['j9_10'])
    # 작게 맞춘 한 번에 3레벨 (9→12, 18→21) — 10·20 이 중간에 끼는 경우를 정확히
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');
      const go=(from,n)=>{x.start();const S=x.S;S.lv=from;S.xp=0;let tot=0;let need=S.need;for(let i=0;i<n;i++){tot+=need;need=Math.floor(5+(from+i+1)*3.2+Math.pow(from+i+1,1.35)+Math.max(0,from+i+1-25)**2*.5);}
        S.need=Math.floor(5+from*3.2+Math.pow(from,1.35)+Math.max(0,from-25)**2*.5);tot=0;let nd=S.need;for(let i=0;i<n;i++){tot+=nd;nd=Math.floor(5+(from+i+1)*3.2+Math.pow(from+i+1,1.35)+Math.max(0,from+i+1-25)**2*.5);}
        x.gainXp(tot+.5);return {lv:S.lv,rr:S.rr-3,ban:S.ban-3,pend:S.pendingLv};};
      o.a=go(9,3);o.b=go(18,4);o.c=go(11,8);return o}""")
    check('Lv9 → 12 한 번에: 10 을 지나며 +1/+1 한 번', r['a']['lv'] == 12 and r['a']['rr'] == 1 and r['a']['ban'] == 1, r['a'])
    check('Lv18 → 22 한 번에: 20 을 지나며 +1/+1 한 번', r['b']['lv'] == 22 and r['b']['rr'] == 1 and r['b']['ban'] == 1, r['b'])
    check('Lv11 → 19 한 번에: 보너스 없음', r['c']['lv'] == 19 and r['c']['rr'] == 0 and r['c']['ban'] == 0, r['c'])
    # 3-c. 카드를 열기 전에 준다 — 레벨업 카드 화면에서 바로 쓸 수 있다(0 이었어도 버튼이 켜진다) · 힌트에 알림
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;S.lv=9;S.rr=0;S.ban=0;S.p.hp=S.p.mhp;
      x.gainXp(S.need);o.lv=S.lv;o.state0=x.state;o.rr0=S.rr;o.ban0=S.ban;o.toast=document.getElementById('toast').textContent;
      x.update(1/30);o.state1=x.state;const rb=document.getElementById('rrBtn'),bb=document.getElementById('banBtn');
      o.rrTxt=rb.textContent;o.rrDis=rb.disabled;o.banTxt=bb.textContent;o.banDis=bb.disabled;o.hint=document.getElementById('lvHint').textContent;
      const before=x.CUR.map(c=>c.k).join('|');rb.click();o.rrAfter=S.rr;o.re=x.CUR.length;o.changed=before!==x.CUR.map(c=>c.k).join('|');
      document.getElementById('banBtn').click();o.mode=S.banMode;
      return o}""")
    check('Lv10 달성 순간(카드 열기 전): 다시뽑기 +1 · 봉인 +1 · 토스트', r['lv'] == 10 and r['state0'] == 'play' and r['rr0'] == 1 and r['ban0'] == 1 and '보너스' in r['toast'] and '다시 뽑기 +1' in r['toast'] and '봉인 +1' in r['toast'], r)
    check('카드 화면: 다시뽑기 (1) · 봉인 (1) 버튼이 켜져 있다', r['state1'] == 'lvup' and not r['rrDis'] and not r['banDis'] and '(1)' in r['rrTxt'] and '(1)' in r['banTxt'], (r['rrTxt'], r['banTxt'], r['rrDis'], r['banDis']))
    check('카드 화면 한 줄 알림: 「Lv10 보너스 — 다시 뽑기 +1 · 봉인 +1 받았어요」', 'Lv10 보너스' in r['hint'] and '받았어요' in r['hint'], r['hint'])
    check('받자마자 다시 뽑기를 쓸 수 있다(0 번 남음 · 카드 3장)', r['rrAfter'] == 0 and r['re'] == 3 and r['changed'], (r['rrAfter'], r['re'], r['changed']))
    check('같은 화면에서 봉인 모드도 켜진다', r['mode'] is True)
    # 3-d. 힌트는 보너스 레벨의 카드에만(여러 레벨이 쌓인 때는 순서대로 — 9, 10, 11 중 10 번째 카드에서만)
    r = await pg.evaluate("""()=>{const x=__p6x,o=[];x.CH_set('brj');x.start();const S=x.S;S.lv=8;S.p.hp=S.p.mhp;
      for(let i=0;i<3;i++){S.pendingLv++;S.lv++;if(S.lv===10||S.lv===20){S.rr++;S.ban++;}}   // 세 레벨이 쌓인 상태를 만든다(보너스 지급은 gainXp 가 하므로 값만 맞춘다)
      x.openLvup();for(let i=0;i<3;i++){o.push({lv:S.lv,pend:S.pendingLv,hint:document.getElementById('lvHint').textContent.includes('보너스')});x.pick(x.CUR[0]);if(x.state!=='lvup')break;}
      return o}""")
    check('9·10·11 이 쌓였을 때 알림은 두 번째 카드(Lv10)에만', [v['hint'] for v in r] == [False, True, False], r)
    # 3-e. 모든 모드: 일반·하드·베리하드·오늘의 도전·무한 — 같은 규칙
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');
      const run=(mode)=>{document.getElementById('hardChk').checked=mode==='hard';document.getElementById('vhChk').checked=mode==='vh';
        x.start(mode==='daily'?{daily:true}:undefined);const S=x.S;if(mode==='endless')S.endless=true;const a=[S.rr,S.ban];
        for(let i=0;i<22;i++){x.gainXp(S.need);S.pendingLv=0;}
        return {lv:S.lv,rr:S.rr-a[0],ban:S.ban-a[1],hard:!!S.hard,vh:!!S.vh,dly:!!S.dly};};
      for(const m of ['normal','hard','vh','daily','endless'])o[m]=run(m);
      document.getElementById('hardChk').checked=false;document.getElementById('vhChk').checked=false;return o}""")
    check('모드 5종 모두 Lv23 까지 +2/+2', all(v['rr'] == 2 and v['ban'] == 2 for v in r.values()), r)
    check('(모드 확인) 하드·베리하드·오늘의 도전 플래그가 실제로 켜졌다', r['hard']['hard'] and r['vh']['vh'] and r['daily']['dly'] and not r['normal']['hard'], {k: (v['hard'], v['vh'], v['dly']) for k, v in r.items()})
    # 3-f. 이어하기: 보너스 카드 화면에서 저장 → 복구해도 다시 주지 않는다 · 복구 뒤 다음 보너스(Lv20)는 한 번만
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;S.lv=9;S.p.hp=S.p.mhp;x.gainXp(S.need);x.update(1/30);
      o.st=x.state;o.pre=[S.rr,S.ban,S.lv,S.pendingLv];const text=localStorage.getItem(x.RES.KEY);o.saved=!!text;
      x.state='title';o.ok=x.RES.restore(text);const T=x.S;o.post=[T.rr,T.ban,T.lv,T.pendingLv];o.st2=x.state;o.hint=document.getElementById('lvHint').textContent;
      x.pick(x.CUR[0]);o.afterPick=[T.rr,T.ban,T.lv,T.pendingLv,x.state];
      for(let i=0;i<10;i++){x.gainXp(T.need);T.pendingLv=0;}   // 10 → 20
      o.at20=[T.lv,T.rr,T.ban];
      // 일시정지 저장도 같은 값
      x.pauseGame();const t2=localStorage.getItem(x.RES.KEY);x.state='title';x.RES.restore(t2);o.afterPause=[x.S.rr,x.S.ban,x.S.lv];return o}""")
    check('보너스 카드 화면에서 저장 → 복구: rr·ban·lv·쌓인 레벨 그대로(중복 지급 없음)', r['saved'] and r['ok'] is not False and r['st'] == 'lvup' and r['st2'] == 'lvup' and r['pre'] == r['post'], (r['pre'], r['post']))
    check('복구한 카드 화면에도 보너스 알림이 그대로', 'Lv10 보너스' in r['hint'], r['hint'])
    check('복구한 뒤 카드를 고르고 Lv20 까지 가면 그 한 번만 더(총 5·5)', r['at20'][0] == 20 and r['at20'][1] == r['pre'][0] + 1 and r['at20'][2] == r['pre'][1] + 1, (r['pre'], r['at20']))
    check('일시정지 저장·복구도 같은 값', r['afterPause'] == [r['at20'][1], r['at20'][2], 20], r['afterPause'])
    # 3-g. 오늘의 도전 카드 난수열: 보너스 지급은 카드 난수를 한 번도 안 쓴다
    r = await pg.evaluate("""()=>{const x=__p6x,o={};
      const play=(n,rerollAt)=>{x.CH_set('brj');x.start({daily:true});const S=x.S;S.p.hp=S.p.mhp;const seq=[];
        for(let i=0;i<n;i++){x.gainXp(S.need);x.openLvup();seq.push(x.CUR.map(c=>c.k).join('|'));x.pick(x.CUR[0]);if(x.state==='lvup')x.resume();S.pendingLv=0;}
        return {seq,next:[x.RN('card'),x.RN('chest'),x.RN('ev'),x.RN('prop'),x.RN('spawn')],lv:S.lv,rr:S.rr,ban:S.ban};};
      const a=play(30),b=play(30);
      x.start({daily:true});const fresh=[];for(let i=0;i<90;i++)fresh.push(x.RN('card'));const f91=x.RN('card');
      x.start({daily:true});const fr2=[x.RN('card'),x.RN('chest'),x.RN('ev'),x.RN('prop'),x.RN('spawn')];
      return {same:JSON.stringify(a.seq)===JSON.stringify(b.seq),nextSame:JSON.stringify(a.next)===JSON.stringify(b.next),a1:a.next[0],f91,lv:a.lv,rr:a.rr,ban:a.ban,restSame:a.next.slice(1).every((v,i)=>v===fr2[i+1]),n:a.seq.length}}""")
    check('오늘의 도전: 30번 레벨업(Lv10·20 보너스 포함) — 같은 시드·같은 선택이면 카드 제안 30번이 똑같다', r['same'] and r['n'] == 30, r['n'])
    check('카드 난수는 제안 30번 × 3장 = 90번만 썼다(보너스가 난수를 안 썼다)', abs(r['a1'] - r['f91']) < 1e-12, (r['a1'], r['f91']))
    check('상자·각성·소품·스폰 난수 줄기는 한 번도 안 건드렸다', r['restSame'])
    check('(확인) 이 30번 동안 보너스 2번이 실제로 지급됐다 — rr %d · ban %d' % (r['rr'], r['ban']), r['lv'] >= 30 and r['rr'] >= 5 and r['ban'] >= 5, r)
    check('3구획 콘솔·페이지 에러 0', not errs, errs[:3])


# 수요 무한대(매 프레임 rgAdd 로 큰 값) — 변신이 끝난 뒤 다음 변신 시작까지 걸린 시간(초) 목록을 돌려주는 브라우저 쪽 함수
WAITS_JS = """([t0,relLv,cycles,freeze])=>{const x=__p6x;x.CH_set('psg');x.start();const S=x.S;S.rel={};if(relLv)S.rel.sg_psg=relLv;S.t=t0;S.p.hp=S.p.mhp=1e9;S.rg=0;S.rgB=2.5;
  const dt=1/30,starts=[],ends=[],durs=[];let was=false,sT=0,clk=0;
  for(let i=0;i<30*400&&ends.length<cycles+1;i++){if(freeze)S.t=t0;else S.t+=dt;clk+=dt;x.rgAdd(1e9);x.charTick(dt);
    if(S.dT>0&&!was){starts.push(clk);sT=clk;}
    if(S.dT<=0&&was){ends.push(clk);durs.push(clk-sT);}
    was=S.dT>0;}
  const waits=[];for(let i=0;i<ends.length&&i+1<starts.length;i++)waits.push(starts[i+1]-ends[i]);
  return {waits,durs,starts:starts.length,mul:x.rgMul()};}"""

async def sec4(pg, errs):
    print('── 4. 프싱 충전 가속')
    # 4-a. 상수와 배율표
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('psg');x.start();const S=x.S;const SH=x.SHV;
      o.c={cap:SH.cap,kgE:SH.kgE,kgB:SH.kgB,acc:SH.acc,accMax:SH.accMax,max:SH.max,dur:SH.dur,hit:SH.hit,kill:SH.kill};
      o.m={};for(const mn of [0,1,5,10,15,20,26,27,28,30,50,60]){S.t=mn*60;o.m[mn]=x.rgMul();}
      return o}""")
    check('상수: cap 3.5 · kgE 4 · kgB 15 · 변신 11초 · 한 대 .25 · 처치 1 은 그대로, 가속은 분당 +3% 최대 1.8배', r['c'] == {'cap': 3.5, 'kgE': 4, 'kgB': 15, 'acc': .03, 'accMax': 1.8, 'max': 100, 'dur': 11, 'hit': .25, 'kill': 1}, r['c'])
    m = r['m']
    check('배율: 0분 1.00 · 5분 1.15 · 10분 1.30 · 20분 1.60 · 27분부터 1.80(상한)', abs(m['0'] - 1) < 1e-9 and abs(m['5'] - 1.15) < 1e-9 and abs(m['10'] - 1.3) < 1e-9 and abs(m['20'] - 1.6) < 1e-9 and abs(m['27'] - 1.8) < 1e-9 and m['60'] == 1.8 and abs(m['26'] - 1.78) < 1e-9, m)
    # 4-b. 변신 사이 대기시간(수요 무한대): 지금(0분 근처) 27.9초 → 5분 24.3 / 10분 21.5 / 20분 17.4 / 27분 이후 15.5 (±1초)
    exp = {0: 27.9, 5: 24.3, 10: 21.5, 20: 17.4, 27: 15.5, 40: 15.5, 58: 15.5}
    got = {}
    for mn, e in exp.items():
        w = await pg.evaluate(WAITS_JS, [mn * 60, 0, 3, True])   # 그 시각의 배율로 고정해 잰다(시간이 흐르며 배율이 오르는 효과를 뺀 표)
        got[mn] = w
        ws = w['waits']
        check('수요 무한대 %d분(배율 고정): 변신 사이 대기 %.1f초 ±1 (측정 %s)' % (mn, e, ', '.join('%.2f' % v for v in ws)), len(ws) >= 3 and all(abs(v - e) <= 1.0 for v in ws[:3]), w)
    # 시간이 실제로 흐르는 경우(배율이 오르며): 첫 변신 직후 대기는 그 시각의 정적 값보다 약간 짧다 — 참고로 같이 기록
    nat = {}
    for mn in (5, 10, 20):
        w = await pg.evaluate(WAITS_JS, [mn * 60, 0, 3, False]); nat[mn] = [round(v, 2) for v in w['waits']]
    print('   (참고) 시간이 흐르는 실측 대기:', nat)
    check('시간이 흐를 때도 대기는 오래 갈수록 짧아진다(5분 > 10분 > 20분 평균)', sum(nat[5]) / 3 > sum(nat[10]) / 3 > sum(nat[20]) / 3, nat)
    # 4-c. 가동률(변신 11초 기준): 식과 측정이 일치한다 + 타오르는 비늘(sg_psg) 겹침
    rows = []
    for lv in (0, 1, 2, 3):
        for mn in (5, 10, 20, 30):
            w = await pg.evaluate(WAITS_JS, [mn * 60, lv, 3, True])
            wait = sum(w['waits'][:3]) / 3; dur = sum(w['durs'][:3]) / 3
            rows.append((lv, mn, round(wait, 2), round(dur, 2), round(dur / (wait + dur) * 100, 1)))
    print('   가동률 표(비늘 레벨, 분, 평균 대기, 평균 변신, 가동률%):')
    for row in rows: print('   ', row)
    d0 = {(a, b): c for a, b, c, d, e in rows}
    dur = {(a, b): d for a, b, c, d, e in rows}
    check('변신 시간: 비늘 없음 11초 · Lv1 12.5 · Lv2 13.5 · Lv3 14.5', all(abs(dur[(l, 10)] - (11 + [0, 1.5, 2.5, 3.5][l])) < .1 for l in range(4)), {l: dur[(l, 10)] for l in range(4)})
    check('가동률이 시간이 갈수록 오르고 27분 이후 41~42%(비늘 없음)', rows[0][4] < rows[1][4] < rows[2][4] <= rows[3][4] + .01 and 40.5 <= rows[3][4] <= 42.5, [r_[4] for r_ in rows[:4]])
    # 4-d. 낮은 수요(약한 판)에도 같은 배율 — 초당 1.5 수요(상한 3.5 아래)에서 게이지 증가 속도가 배율대로
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('psg');
      const rate=(t0)=>{x.start();const S=x.S;S.t=t0;S.rg=0;S.rgB=2.5;S.p.hp=S.p.mhp=1e9;const dt=1/30;let g=0;
        for(let i=0;i<30*8;i++){S.t+=dt;x.rgAdd(.05);x.charTick(dt);}return S.rg/8;};
      o.r0=rate(0);o.r10=rate(600);o.r30=rate(1800);o.r50=rate(3000);return o}""")
    check('낮은 수요에서도 충전 속도가 배율만큼: 10분 ×1.30 · 30분 ×1.8 · 50분 ×1.8', abs(r['r10'] / r['r0'] - 1.3) < .02 and abs(r['r30'] / r['r0'] - 1.8) < .02 and abs(r['r50'] / r['r0'] - 1.8) < .02, r)
    # 4-e. 한꺼번에 때려도 버킷(2.5)이 막는다 — 배율 안에서만 (0분 ≤2.5 · 상한 시점 ≤2.5×1.8)
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('psg');
      const burst=(t0)=>{x.start();const S=x.S;S.t=t0;S.rg=0;S.rgB=2.5;for(let i=0;i<50;i++)x.rgAdd(5);return S.rg;};
      o.b0=burst(0);o.b50=burst(3000);o.bucket=(()=>{x.start();const S=x.S;S.rgB=0;for(let i=0;i<300;i++)x.charTick(1/30);return S.rgB;})();return o}""")
    check('버킷 상한 2.5 는 그대로(한꺼번에 때리면 0분 2.5 · 50분 4.5 까지만)', abs(r['b0'] - 2.5) < 1e-9 and abs(r['b50'] - 4.5) < 1e-9 and abs(r['bucket'] - 2.5) < 1e-9, r)
    # 4-f. 다른 캐릭터는 영향 없음 · 변신 중에는 충전 없음 · 설명 문구
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('brj');x.start();const S=x.S;S.t=3000;S.rg=0;x.rgAdd(1);o.other=S.rg;
      x.CH_set('psg');x.start();const T=x.S;T.t=3000;T.rg=0;T.dT=5;x.rgAdd(1);o.drg=T.rg;
      o.ds=x.CHARS.find(c=>c.k==='psg').ds;return o}""")
    check('프싱이 아닌 캐릭터는 분노가 안 찬다 · 변신 중에도 안 찬다', r['other'] == 0 and r['drg'] == 0, r)
    check('프싱 설명에 한 줄: 「오래 버틸수록 분노가 빨리 찬다」(분당 +3%, 최대 1.8배)', '오래 버틸수록 분노가 빨리 찬다' in r['ds'] and '분당 +3%' in r['ds'] and '최대 1.8배' in r['ds'], r['ds'][:160])
    # 4-g. 실제 전투 루프(update)에서도 예외 없이 돌고 변신이 일어난다 — 장비 전부 낀 프싱으로 10초(5분·30분 시점)
    r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('psg');
      for(const t0 of [300,1800]){x.start();const S=x.S;S.t=t0;S.p.hp=S.p.mhp=1e9;S.w.twin=8;S.ev.twin=1;S.tier.twin=5;S.rel.sg_psg=3;S.rg=99.9;x.tkCalc();
        for(let i=0;i<40;i++){const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.x=S.p.x+60+(i%8)*18;e.y=S.p.y+((i/8|0)-2)*30;e.sp=0;}
        let ok=true;try{for(let i=0;i<30*10;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}S.p.hp=S.p.mhp;x.update(1/30);if(i%3==0)x.draw();}}catch(er){ok=String(er);}
        o[t0]={ok,dN:S.dN,rg:S.rg};}
      return o}""")
    check('실전 루프 10초(5분·30분 시점, 비늘 Lv3·쌍둥이 각성): 예외 없음 + 변신 발생', all(v['ok'] is True and v['dN'] >= 1 for v in r.values()), r)
    check('4구획 콘솔·페이지 에러 0', not errs, errs[:3])

SECS = {1: sec1, 2: sec2, 3: sec3, 4: sec4}

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
