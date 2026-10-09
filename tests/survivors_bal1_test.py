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
EXTRA = "Object.defineProperties(window.__p6x,{areaMul:{get(){return areaMul}}});"
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

SECS = {1: sec1}

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
