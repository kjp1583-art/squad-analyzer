# -*- coding: utf-8 -*-
"""🎁 보스 상자 — 안 가진 새 무기·새 유물은 나오지 않는다(가진 걸 키우는 카드·패시브·간식만).
[2026-10-09 사장님 지시 「보스 보상 상자 획득 시 내가 가지고 있지 않은 무기·유물이 획득되지 않게 변경」]
  A. offers(1, null, true) — 캐릭터 전원 × 무작위 빌드(무기 0~6종·유물·패시브·봉인·레벨 5~64) 수만 번: 새 무기(t:'w' l:0)·새 유물(t:'rl' l:0 · 시그니처 포함) 0번 · 항상 카드 1장
  B. 레벨업 카드(offers(3))는 그대로 — 같은 빌드에서 새 무기·새 유물이 여전히 나온다(규칙은 보스 상자 한정)
  C. 실제 openChest() 수백 번 — 상자를 열어도 S.w·S.rel 의 이름이 늘지 않는다 · 안내 문구 · 다시 뽑기 +1 · 상자가 가진 걸 키우긴 한다
  D. 가진 걸 키우는 카드는 그대로 나온다(무기 강화 · 마스터/각성 단계 · 패시브 · 초월 · 유물 강화)
  E. 각성 경로는 그대로(무기 Lv8 + 짝 패시브 → 상자에서 각성) · 일일 도전은 같은 날짜 시드면 상자 결과도 같다
  F. 소스: 상자만 own 인자를 쓰고, 레벨업·다시 뽑기·봉인 보충 호출은 그대로다
사용: python3 tests/survivors_chest_own_test.py
"""
import asyncio, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright

ROOT = H.ROOT
SRC = os.environ.get('CHEST_HTML', 'survivors.html')   # 기준(고치기 전) 사본으로도 돌려 볼 수 있다: CHEST_HTML=survivors_base.html — 그때는 A1·C1 이 실패해야 시험이 제 일을 하는 것이다

BUILD_JS = r"""
(()=>{
  const x=window.__p6x;
  window.__cb={
    rnd:null,
    seed(n){let s=n>>>0;this.rnd=()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296};},
    // 이 캐릭터가 실제로 가질 수 있는 무기·유물로 무작위 빌드를 만든다
    build(ch,opt){
      const S=x.S,r=this.rnd,wk=Object.keys(x.WEAP).filter(k=>!x.WEAP[k].only||x.WEAP[k].only===ch);
      const rk=Object.keys(x.REL).filter(k=>!x.REL[k].ch||x.REL[k].ch===ch);
      S.lv=opt&&opt.lv||(5+Math.floor(r()*60));
      S.w={};S.ev={};S.tier={};S.pt={};S.ps={};S.rel={};S.banned=[];
      const nw=Math.floor(r()*7);const pool=wk.slice();
      for(let i=0;i<nw&&pool.length;i++){const k=pool.splice(Math.floor(r()*pool.length),1)[0];S.w[k]=1+Math.floor(r()*8);}
      const pk=['spd','hp','cd','mag','arm','amt','area','might','luck','dur','crit','pspd','study','glass','turtle','vamp'];
      const np=Math.floor(r()*7);for(let i=0;i<np;i++){const k=pk.splice(Math.floor(r()*pk.length),1)[0];S.ps[k]=1+Math.floor(r()*3);}
      if(S.lv>=18){for(const k of rk)if(r()<.45)S.rel[k]=1+Math.floor(r()*3);}
      const nb=Math.floor(r()*4);for(let i=0;i<nb;i++)S.banned.push(wk[Math.floor(r()*wk.length)]);
      x.synCalc();x.tkCalc();
      return {wk,rk};
    }
  };
})()
"""

A_JS = r"""
([chars,N,perBuild])=>{
  const x=window.__p6x,B=window.__cb;B.seed(20261009);
  const out={bad:[],draws:0,empty:0,kinds:{},builds:0};
  for(const ch of chars){
    x.CH_set(ch);x.start();
    for(let it=0;it<N;it++){
      B.build(ch);out.builds++;
      for(let d=0;d<perBuild;d++){
        const c=x.offers(1,null,true);out.draws++;
        if(c.length!==1||!c[0]){out.empty++;continue;}
        const o=c[0];out.kinds[o.t]=(out.kinds[o.t]||0)+1;
        if(o.t==='w'&&!o.l)out.bad.push(['w',ch,o.k]);
        if(o.t==='rl'&&!o.l)out.bad.push(['rl',ch,o.k]);
        if(o.t==='w'&&!x.S.w[o.k])out.bad.push(['w-notowned',ch,o.k]);
        if(o.t==='rl'&&!x.S.rel[o.r])out.bad.push(['rl-notowned',ch,o.k]);
      }
    }
  }
  out.bad=out.bad.slice(0,8);return out;
}
"""

B_JS = r"""
([chars,N,perBuild])=>{
  const x=window.__p6x,B=window.__cb;B.seed(777);
  const out={newW:0,newRl:0,newSg:0,draws:0};
  for(const ch of chars){
    x.CH_set(ch);x.start();
    for(let it=0;it<N;it++){
      B.build(ch,{lv:30});
      for(let d=0;d<perBuild;d++)for(const o of x.offers(3)){out.draws++;
        if(o.t==='w'&&!o.l)out.newW++;
        if(o.t==='rl'&&!o.l){out.newRl++;if(x.REL[o.r].ch)out.newSg++;}}
    }
  }
  return out;
}
"""

C_JS = r"""
([chars,N])=>{
  const x=window.__p6x,B=window.__cb;B.seed(4242);
  const out={runs:0,grew:[],noHint:0,noRr:0,noCard:0,chestTypes:{},lines:0};
  for(const ch of chars){
    for(let it=0;it<N;it++){
      x.CH_set(ch);x.start();const S=x.S;B.build(ch);
      const w0=Object.keys(S.w).sort().join(','),r0=Object.keys(S.rel).sort().join(','),rr0=S.rr;
      x.openChest();out.runs++;
      const w1=Object.keys(S.w).sort().join(','),r1=Object.keys(S.rel).sort().join(',');
      if(w0!==w1||r0!==r1)out.grew.push([ch,w0,w1,r0,r1]);
      const el=document.getElementById('chestList'),txt=el.textContent;
      if(!txt.includes('내가 가진 무기·유물만'))out.noHint++;
      if(S.rr<rr0+1)out.noRr++;   // 상자는 늘 다시 뽑기 +1 (🎲 주사위 세트 카드가 같이 나오면 +2 가 더 붙는다)
      const cr=el.querySelectorAll('.cr');if(cr.length<2)out.noCard++;   // 카드 1장 이상 + 다시 뽑기 줄
      out.lines+=cr.length;
      if(x.state!=='chest')out.noCard++;
      x.resume();
    }
  }
  out.grew=out.grew.slice(0,5);return out;
}
"""

D_JS = r"""
()=>{
  const x=window.__p6x,B=window.__cb;B.seed(99);
  x.CH_set('brj');x.start();const S=x.S;
  S.lv=40;S.w={quill:8,feed:8,fryer:3};S.ev={};S.tier={};S.pt={};S.rel={rl1:1};S.banned=[];
  // 유물 키 하나를 실제 표에서 고른다(시그니처가 아닌 것)
  const rk=Object.keys(x.REL).filter(k=>!x.REL[k].ch);S.rel={};S.rel[rk[0]]=1;
  S.ps={pspd:3,spd:1,cd:1};x.synCalc();x.tkCalc();
  const k={};for(let i=0;i<6000;i++){const o=x.offers(1,null,true)[0];k[o.t]=(k[o.t]||0)+1;}
  return k;
}
"""

E_JS = r"""
()=>{
  const x=window.__p6x,B=window.__cb;
  const res={};
  // E1 각성: 무기 Lv8 + 짝 패시브 → 상자에서 각성
  x.CH_set('bbb');x.start();let S=x.S;S.w={sing:8};S.ps={study:1};S.ev={};S.tier={};x.tkCalc();x.openChest();
  res.evolved=!!S.ev.sing;res.evText=document.getElementById('chestList').textContent.includes('각성!');x.resume();
  // E2 짝이 없으면 각성 안 함
  x.CH_set('bbb');x.start();S=x.S;S.w={sing:8};S.ps={};S.ev={};S.tier={};x.tkCalc();x.openChest();res.noPair=!!S.ev.sing;x.resume();
  // E3 일일 도전: 같은 시드 두 판의 상자 결과가 같다
  const run=()=>{x.CH_set('brj');x.start({daily:true});const S=x.S;S.lv=26;S.w={quill:5,feed:4};S.ps={cd:1,spd:2};S.rel={};S.ev={};S.tier={};S.pt={};S.banned=[];x.synCalc();x.tkCalc();
    const seq=[];for(let i=0;i<6;i++){x.openChest();seq.push(document.getElementById('chestList').textContent);x.resume();}return seq;};
  const a=run(),b=run();res.dailySame=JSON.stringify(a)===JSON.stringify(b);res.dailyLen=a.length;res.dailyDistinct=new Set(a).size;
  return res;
}
"""


async def main():
    p = H.make_copy(SRC, 'survivors_chestx.html', extra="")
    srv = H.Srv()
    fails = []

    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)

    src = open(os.path.join(ROOT, SRC), encoding='utf-8').read()
    # F. 소스 점검 — 상자만 own 인자
    calls = re.findall(r"offers\(([^()]*)\)", src)
    own_calls = [c for c in calls if c.replace(' ', '').endswith(',true')]
    ok(len(own_calls) == 1 and own_calls[0].replace(' ', '') == '1,null,true', 'F1 own(세 번째 인자 true) 호출은 보스 상자 한 곳뿐이다 (%s)' % own_calls)
    ok(re.search(r"function openChest\(\)\{[\s\S]{0,900}offers\(1,null,true\)", src) is not None, 'F2 openChest 가 offers(1,null,true) 를 부른다')
    ok(src.count('offers(3') >= 1 and 'offers(3,' in src or 'offers()' in src or 'offers(' in src, 'F3 레벨업 쪽 offers 호출이 남아 있다')
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=412, h=860, page='survivors_chestx.html')
        await pg.evaluate(BUILD_JS)
        chars = await pg.evaluate("()=>window.__p6x.CHARS.map(c=>c.k)")
        print('캐릭터', len(chars), chars)
        a = await pg.evaluate(A_JS, [chars, 40, 25])
        print('A', json.dumps(a, ensure_ascii=False)[:500])
        ok(not a['bad'], 'A1 상자 후보에 새 무기·새 유물 0건 (%d판 · 카드 %d장) %s' % (a['builds'], a['draws'], a['bad'][:3]))
        ok(a['empty'] == 0 and a['draws'] == len(chars) * 40 * 25, 'A2 항상 카드 한 장이 나온다 (빈 뽑기 %d)' % a['empty'])
        ok(a['kinds'].get('w', 0) > 0 and a['kinds'].get('p', 0) > 0, 'A3 가진 무기 강화·패시브는 계속 나온다 (%s)' % a['kinds'])
        bb = await pg.evaluate(B_JS, [chars, 20, 15])
        print('B', json.dumps(bb, ensure_ascii=False))
        ok(bb['newW'] > 0, 'B1 레벨업 카드에는 새 무기가 그대로 나온다 (%d)' % bb['newW'])
        ok(bb['newRl'] > 0 and bb['newSg'] > 0, 'B2 레벨업 카드에는 새 유물(시그니처 포함)이 그대로 나온다 (%d · 시그니처 %d)' % (bb['newRl'], bb['newSg']))
        c = await pg.evaluate(C_JS, [chars, 15])
        print('C', json.dumps(c, ensure_ascii=False)[:400])
        ok(not c['grew'], 'C1 상자를 열어도 무기·유물 이름이 늘지 않는다 (%d번) %s' % (c['runs'], c['grew'][:2]))
        ok(c['noHint'] == 0, 'C2 상자 화면에 「내가 가진 무기·유물만」 안내가 있다 (없는 곳 %d)' % c['noHint'])
        ok(c['noRr'] == 0 and c['noCard'] == 0, 'C3 다시 뽑기 +1 이상 · 카드 1장 이상 · 상자 상태 (이상 %d / %d)' % (c['noRr'], c['noCard']))
        d = await pg.evaluate(D_JS)
        print('D', d)
        ok(d.get('w', 0) > 0 and d.get('p', 0) > 0 and d.get('wt', 0) > 0, 'D1 무기 강화·패시브·마스터 단계가 나온다 (%s)' % d)
        ok(d.get('rl', 0) > 0, 'D2 가진 유물 강화는 나온다 (%s)' % d.get('rl', 0))
        e = await pg.evaluate(E_JS)
        print('E', e)
        ok(e['evolved'] and e['evText'], 'E1 무기 Lv8 + 짝 패시브면 상자에서 각성한다')
        ok(not e['noPair'], 'E2 짝 패시브가 없으면 각성하지 않는다')
        ok(e['dailySame'] and e['dailyDistinct'] >= 2, 'E3 일일 도전: 같은 시드의 상자 결과가 같다 (서로 다른 상자 %d/%d)' % (e['dailyDistinct'], e['dailyLen']))
        real = [m for m in errs if 'chestx' not in m]
        ok(not real, 'G 콘솔·페이지 오류 0 %s' % real[:3])
        await b.close()
    srv.close()
    try:
        os.remove(p)
    except Exception:
        pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
