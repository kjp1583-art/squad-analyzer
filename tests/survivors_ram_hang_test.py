# -*- coding: utf-8 -*-
"""🥊 태웅 「씩씩 박치기」 보스전 개편 A — 돌진 후 매달려 연타 (2026-10-17 사장님 「A 진행」)
   사용: python3 tests/survivors_ram_hang_test.py     (종료코드 0 = 전부 통과)
   구성
     가  순서 — 돌진(D) → 매달리기(H) → 뒤로 튕김(K) · 연타 횟수 = U3.ram.hg.n(각성 evN) · 간격 일정 · 시간 = hg.t(각성 ×evT)
         · 한 번에 박치기 피해의 hg.p 배 · Lv6 부터 마지막 한 방만 ×hg.last · 매달린 동안 이동 입력 무시(적을 따라간다) · 끝나면 hg.bk 만큼 멀어진다
     나  대상 — 보스·정예(e.el)·대형(e.bg) 에만 매달린다 · 잡몹은 예전 그대로(기준 커밋 판과 비트 동일: 위치·체력·처치 수·타격 기록)
     다  받는 피해 — 매달린 동안 takenMul ×(1-red)(무적 아님: 0 이 아니다) · 끝나면 원래대로
     라  Lv8 연속 두 번 돌진 — 첫 매달리기 중에 온 두 번째 돌진은 튕겨 난 뒤로 미뤄져 두 번째도 매달린다(eq) · 이어하기 왕복
         (매달리기 도중 저장→복구해도 같은 횟수·같은 결과) · 매달린 적이 쓰러지면 바로 풀린다
     마  문구 = 값 — 카드 문구의 숫자(시간·횟수·절반·마지막 한 방·각성 배수)가 U3.ram.hg 값과 같다 · 변이(값을 바꾸면 동작이 따라 바뀐다)
     바  전수 — 레벨 1~8 × 각성 × 일반/하드/베리하드 × (맨몸/패시브·유물 가득) × 보스/정예/대형: 오류·NaN 0 · 매달리기가 반드시 끝난다
   임시 사본 survivors_ramhang.html 에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, re, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
NEW = 'survivors_ramhang.html'
OLD = 'survivors_ramhang_old.html'
BASE_COMMIT = '3460c09'   # 개편 전 survivors.html 이 들어 있는 커밋(작업 지시 커밋)
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)

EXTRA = r"""
window.__rh={ramGo,hitP,takenMul,pauseGame,resume,RES,U3,WEAP,CHARS,PASS,REL,get S(){return S},get state(){return state},set state(v){state=v},get keys(){return keys},set keys(v){keys=v},update,spawnBoss,spawnEnemy,enemies,pick};
window.__hl=null;
{const h=hurt;hurt=function(e,d){if(window.__hl&&e.on)window.__hl.push([+S.t.toFixed(4),d,SRC,e.sn]);return h.apply(this,arguments);};}
"""
JS = r"""
(()=>{const X=window.__rh,P=window.__p6x;
const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
function begin(L,ev,o){o=o||{};Math.random=o.seed?mb(o.seed):()=>.99;   // .99 = 치명타·흩뿌리기 없는 고정 난수
  P.CH_set('tw');P.start();const S=P.S;S.spawnT=-1e12;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;S.propT=S.chickT=1e12;
  for(const q of P.enemies.a)q.on=false;S.w={ram:L};S.ev={};if(ev)S.ev.ram=1;S.p.hp=S.p.mhp=o.hp||1e9;S.t=300;P.keys={};S.cd.ram=1e9;
  if(o.hard){S.hard=1;S.vh=o.hard>1?1:0;}
  if(o.full){for(const k of Object.keys(X.PASS))S.ps[k]=3;for(const k of Object.keys(X.REL))S.rel[k]=1;if(P.synCalc)P.synCalc();P.tkCalc&&P.tkCalc();}
  return S;}
function target(kind,dist){const S=P.S;let e;
  if(kind==='boss'){e=X.spawnBoss('sr');e.atk=[];}
  else{e=X.spawnEnemy(1,1);if(kind==='el')e.el=1;else e.bg=1;}
  e.hp=e.mhp=1e9;e.sp=0;e.x=S.p.x+dist;e.y=S.p.y;e.dmg=0;return e;}
window.__rt={
 // 한 번 돌진시켜 프레임별 단계를 기록한다
 duel(L,ev,kind,o){o=o||{};const S=begin(L,ev,o);const e=target(kind||'boss',o.dist||200);const R=S.x3.ram;window.__hl=[];
   if(o.moveBoss)e.sp=0;
   const ok=X.ramGo();const ph=[],px=[],ds=[];let sawH=0,prevH=false,firstH=-1,lastH=-1;
   for(let i=0;i<(o.frames||120);i++){
     if(o.keys)P.keys={KeyD:true};
     if(o.moveBoss&&R.hg>0)e.x+=3;
     const x0=S.p.x;X.update(1/30);
     const c=R.hg>0?'H':R.t>0?'D':S.p.yt>0?'K':'-';ph.push(c);
     if(R.hg>0){if(firstH<0)firstH=i;lastH=i;}
     ds.push(Math.hypot(S.p.x-e.x,S.p.y-e.y));
     if(o.stop&&o.stop(S,e,R))break;}
   const hits=window.__hl.filter(h=>h[2]==='ram'&&h[3]===e.sn).map(h=>[h[0],h[1]]);window.__hl=null;
   return {ok,ph:ph.join(''),hits,ds,er:e.r,pr:S.p.r,bossAlive:e.on,R:Object.assign({},R),offs:[S.p.x-e.x,S.p.y-e.y]};},
 // 잡몹만 있는 판 — 위치·체력·처치 수를 매 프레임 기록(기준 판과 비교)
 mobs(L,ev,seed){const S=begin(L,ev,{seed});const R=S.x3.ram;for(let i=0;i<9;i++){const e=X.spawnEnemy(i%3,1);e.x=S.p.x+(i-4)*55;e.y=S.p.y+60+(i%3)*30;e.sp=20;}
   const tr=[];S.cd.ram=0;let hang=0;
   for(let i=0;i<420;i++){X.update(1/30);if(R.hg>0)hang++;
     if(i%7===0){let hs=0,n=0;for(const q of P.enemies.a)if(q.on){hs+=q.hp+q.x*.001+q.y*.002;n++;}tr.push([+S.p.x.toFixed(4),+S.p.y.toFixed(4),+hs.toFixed(3),n,S.kills]);}}
   return {tr,hang,kills:S.kills};},
 // 받는 피해
 taken(L,ev){const S=begin(L,ev,{hp:1000});const e=target('boss',200);const R=S.x3.ram;S.p.mhp=S.p.hp=1000;
   const t0=X.takenMul();S.p.inv=0;let h0=S.p.hp;X.hitP(100);const base=h0-S.p.hp;
   for(let i=0;i<30;i++)X.update(1/30);e.x=S.p.x+200;e.y=S.p.y;S.p.inv=0;S.p.hp=1000;X.ramGo();let mid=-1,tm=-1,hang=false;
   for(let i=0;i<60;i++){X.update(1/30);if(R.hg>0){hang=true;S.p.inv=0;tm=X.takenMul();const hh=S.p.hp;X.hitP(100);mid=hh-S.p.hp;break;}}
   let after=-1,ta=-1;for(let i=0;i<120;i++){X.update(1/30);if(!(R.hg>0)&&R.t<=0&&hang){S.p.inv=0;ta=X.takenMul();const hh=S.p.hp;X.hitP(100);after=hh-S.p.hp;break;}}
   return {t0,base,tm,mid,ta,after,hang};},
 // Lv8 연속 두 번 돌진 — 메인 루프가 돌진을 부르게 한다
 echo(L,ev,kind){const S=begin(L,ev,{});const e=target(kind||'boss',(kind||'boss')==='boss'?200:110);const R=S.x3.ram;S.cd.ram=0;window.__hl=[];
   let starts=0,prev=false,eqMax=0;const ph=[];
   for(let i=0;i<(ev?100:80);i++){X.update(1/30);const h=R.hg>0;if(h&&!prev)starts++;prev=h;eqMax=Math.max(eqMax,R.eq);ph.push(h?'H':R.t>0?'D':S.p.yt>0?'K':'-');}
   window.__hl=null;return {starts,eqMax,eqEnd:R.eq,ph:ph.join('')};},
 // 이어하기: 매달리기 도중 저장→복구
 resume(L,ev,cut){
   function world(){const S=begin(L,ev,{});const e=target('boss',200);window.__hl=[];X.ramGo();return {S,e};}
   const run=(w,n)=>{for(let i=0;i<n;i++){if(P.state!=='play')P.resume();X.update(1/30);}};
   // 기준: 끊김 없이
   let w=world();run(w,140);const A={hp:w.e.hp,px:w.S.p.x,py:w.S.p.y,hits:window.__hl.filter(h=>h[2]==='ram').length,hg:w.S.x3.ram.hg};window.__hl=null;
   // 도중 저장→복구
   w=world();run(w,cut);const R0=Object.assign({},w.S.x3.ram);const wasH=R0.hg>0;
   X.pauseGame();const text=localStorage.getItem(X.RES.KEY);P.state='title';const ok=text?X.RES.restore(text):false;
   const S2=P.S;const R1=Object.assign({},S2.x3.ram);let e2=null;for(const q of P.enemies.a)if(q.on&&q.sn===R1.hs)e2=q;
   window.__hl=[];if(P.state!=='play')P.resume();run({},140-cut);
   const B={hp:(e2||{hp:-1}).hp,px:S2.p.x,py:S2.p.y,hits:window.__hl.filter(h=>h[2]==='ram').length,hg:S2.x3.ram.hg};window.__hl=null;
   return {ok,wasH,R0,R1,A,B,e2:!!e2};},
 // 매달린 적이 쓰러지면 바로 풀린다
 kill(L,ev){const S=begin(L,ev,{});const e=target('boss',200);const R=S.x3.ram;e.hp=e.mhp=1;X.ramGo();let hang=0;
   for(let i=0;i<60;i++){X.update(1/30);if(R.hg>0)hang++;}
   return {hang,hg:R.hg,hk:R.hk,hn:R.hn,alive:e.on,yt:S.p.yt};},
 // 변이: 값을 바꾸면 동작이 따라 바뀐다
 mut(){const H=X.U3.ram.hg,save=Object.assign({},H);const out={};
   H.n=7;H.p=.3;H.t=1.4;const r=window.__rt.duel(5,0,'boss');out.n7=r;Object.assign(H,save);
   H.red=.8;const r2=window.__rt.taken(5,0);out.red8=r2;Object.assign(H,save);
   H.bk=300;H.bkT=.3;const r3=window.__rt.duel(5,0,'boss',{frames:140});out.bk=r3;Object.assign(H,save);
   return out;},
 // 전수
 sweep(){const res=[];const mk=(L,ev,mode,full,kind)=>{try{const S=begin(L,ev,{hard:mode,full:full});const e=target(kind,kind==='boss'?200:110);const R=S.x3.ram;S.cd.ram=0;S.p.hp=S.p.mhp=1e9;
     let hang=0,bad=0,maxHang=0,cur=0;
     for(let i=0;i<260;i++){if(P.state==='lvup')P.pick(P.CUR[0]);else if(P.state!=='play')P.resume();X.update(1/30);
       if(R.hg>0){hang++;cur++;maxHang=Math.max(maxHang,cur);}else cur=0;
       if(!isFinite(S.p.x)||!isFinite(S.p.y)||!isFinite(e.hp)||!isFinite(S.p.hp)||!isFinite(R.hg))bad++;}
     return {L,ev,mode,full,kind,hang,bad,maxHang,hgEnd:R.hg,ok:true};}catch(er){return {L,ev,mode,full,kind,err:String(er&&er.stack||er).slice(0,200)};}};
   for(const kind of['boss','el','bg'])for(const mode of[0,1,2])for(const full of[0,1])for(let L=1;L<=8;L++)for(const ev of[0,1])res.push(mk(L,ev,mode,full,kind));
   return res;}
};return true;})()
"""

def fr(x): return round(x, 4)

async def fetch_old():
    try:
        out = subprocess.run(['git', 'show', BASE_COMMIT + ':survivors.html'], cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
        return out
    except Exception:
        return None

async def main():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA)
    old = await fetch_old()
    if old:
        open(os.path.join(ROOT, 'survivors_ramhang_src.html'), 'w', encoding='utf-8').write(old)
        H.make_copy(src='survivors_ramhang_src.html', dst=OLD, extra=EXTRA)
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, 800, 600, page=NEW, ready='__rh')
            await pg.wait_for_timeout(400)
            await pg.evaluate(JS)
            U = await pg.evaluate('JSON.parse(JSON.stringify(__rh.U3.ram))')
            Hg = U['hg']
            print('U3.ram', U)

            # ── 가 순서·횟수·시간·배율
            for L, ev in [(5, 0), (8, 0), (8, 1), (2, 0)]:
                r = await pg.evaluate('([L,ev])=>__rt.duel(L,ev,"boss")', [L, ev])
                tag = '[가] Lv%d%s 보스' % (L, ' 각성' if ev else '')
                m = re.match(r'^D*H+K+', r['ph'])
                check(tag + ' 순서 돌진→매달리기→튕김 (%s…)' % r['ph'][:34], bool(m) and r['ok'] and 'H' in r['ph'] and 'D' in r['ph'], r['ph'])
                hits = r['hits']
                # 첫 줄 = 닿는 순간 한 대(d) · 둘째 = 도착 충격파(d*.5) · 그 뒤가 매달려 때린 것
                d0 = hits[0][1]
                hang = hits[2:] if len(hits) > 2 else []
                nexp = Hg['evN'] if ev else Hg['n']
                check(tag + ' 연타 %d번' % nexp, len(hang) == nexp, (len(hits), [h[1] for h in hits]))
                if len(hang) == nexp:
                    base = d0 * Hg['p']
                    body = hang[:-1] if L >= 6 else hang
                    check(tag + ' 한 번에 박치기 피해의 %d%%' % round(Hg['p'] * 100), all(abs(h[1] - base) < base * 1e-6 for h in body), [h[1] for h in hang])
                    if L >= 6:
                        check(tag + ' 마지막 한 방 ×%.1f' % Hg['last'], abs(hang[-1][1] - base * Hg['last']) < base * 1e-6, [h[1] for h in hang])
                    else:
                        check(tag + ' (Lv6 전) 마지막 한 방도 똑같다', abs(hang[-1][1] - base) < base * 1e-6, [h[1] for h in hang])
                    gaps = [hang[i + 1][0] - hang[i][0] for i in range(len(hang) - 1)]
                    check(tag + ' 연타 간격 일정(%.2f초)' % (gaps[0] if gaps else 0), all(abs(g - gaps[0]) < 1 / 30 + 1e-6 for g in gaps), gaps)
                hn = r['ph'].count('H')
                texp = Hg['t'] * (Hg['evT'] if ev else 1)
                check(tag + ' 매달린 시간 %.2f초(±2프레임)' % texp, abs(hn / 30 - texp) <= 2 / 30 + 1e-6, hn / 30)
                # 튕김: 매달리기가 끝난 뒤 거리가 bk 만큼 벌어진다
                ih = r['ph'].rfind('H')
                dist_end = r['ds'][ih]; dist_after = max(r['ds'][ih + 1:ih + 12] or [0])
                check(tag + ' 끝나면 뒤로 %d 튕겨 난다(+%.0f)' % (Hg['bk'], dist_after - dist_end), abs((dist_after - dist_end) - Hg['bk']) < 6, (dist_end, dist_after))

            # 이동 입력 무시 · 움직이는 보스를 따라간다
            r = await pg.evaluate('()=>__rt.duel(5,0,"boss",{keys:1,moveBoss:1,frames:40})')
            hs = [i for i, c in enumerate(r['ph']) if c == 'H']
            check('[가] 매달린 동안 이동 입력(→)을 무시하고 움직이는 보스를 따라간다(간격 일정)', bool(hs) and max(r['ds'][i] for i in hs) - min(r['ds'][i] for i in hs) < .5, [r['ds'][i] for i in hs][:6])

            # ── 나 대상
            for kind, nm in [('el', '정예'), ('bg', '대형')]:
                r = await pg.evaluate('([k])=>__rt.duel(5,0,k,{dist:110})', [kind])
                check('[나] %s 에도 매달린다' % nm, bool(re.match(r'^D*H+K+', r['ph'])) and len([h for h in r['hits'][2:]]) == max(1, round(Hg['n'] * Hg['sm'])), r['ph'][:30])
                check('[나] %s 는 보스의 %d%% 만큼만 매달린다(시간 %.2f초)' % (nm, round(Hg['sm'] * 100), Hg['t'] * Hg['sm']), abs(r['ph'].count('H') / 30 - Hg['t'] * Hg['sm']) <= 2 / 30 + 1e-6, r['ph'])
            r = await pg.evaluate('()=>{const S=(()=>{return null})();return 0}')
            # 잡몹 — 기준 커밋 판과 비트 동일
            new = []
            for sd in (11, 22, 33):
                for L, ev in [(2, 0), (5, 0), (8, 0), (8, 1)]:
                    new.append(await pg.evaluate('([L,ev,sd])=>__rt.mobs(L,ev,sd)', [L, ev, sd]))
            check('[나] 잡몹만 있는 판은 매달리기가 한 번도 안 켜진다', all(x['hang'] == 0 for x in new), [x['hang'] for x in new])
            check('[나] 잡몹이 실제로 쓰러졌다(시험이 헛돌지 않음)', sum(x['kills'] for x in new) > 0, [x['kills'] for x in new])
            if old:
                ctx2, pg2, errs2 = await H.new_page(b, srv.port, 800, 600, page=OLD, ready='__rh')
                await pg2.wait_for_timeout(400)
                await pg2.evaluate(JS)
                oldr = []
                for sd in (11, 22, 33):
                    for L, ev in [(2, 0), (5, 0), (8, 0), (8, 1)]:
                        oldr.append(await pg2.evaluate('([L,ev,sd])=>__rt.mobs(L,ev,sd)', [L, ev, sd]))
                same = [json.dumps(a['tr']) == json.dumps(c['tr']) and a['kills'] == c['kills'] for a, c in zip(new, oldr)]
                check('[나] 잡몹전은 개편 전(%s)과 비트 동일 — 12판(Lv2/5/8/각성 × 시드 3)' % BASE_COMMIT, all(same), [i for i, s in enumerate(same) if not s])
                await ctx2.close()
            else:
                print('SKIP [나] 비트 동일 비교 — 기준 커밋 %s 가 이 저장소에 없다(얕은 저장소)' % BASE_COMMIT)

            # ── 다 받는 피해
            for L, ev in [(5, 0), (8, 1)]:
                r = await pg.evaluate('([L,ev])=>__rt.taken(L,ev)', [L, ev])
                tag = '[다] Lv%d%s' % (L, ' 각성' if ev else '')
                check(tag + ' 매달린 동안 받는 피해 ×%.2f (평소 %.1f → %.1f)' % (1 - Hg['red'], r['base'], r['mid']), r['hang'] and r['mid'] > 0 and abs(r['mid'] / r['base'] - (1 - Hg['red'])) < .02, r)
                check(tag + ' 무적이 아니다(0 보다 크다) · 끝나면 원래대로(%.1f)' % r['after'], r['mid'] > 0 and abs(r['after'] - r['base']) < .01, r)

            # ── 라 Lv8 두 번째 돌진 · 이어하기 · 쓰러짐
            r = await pg.evaluate('()=>__rt.echo(5,0)')
            check('[라] Lv5 한 사이클에 매달리기 1번', r['starts'] == 1, r)
            r = await pg.evaluate('()=>__rt.echo(8,0)')
            check('[라] Lv8 연속 두 번 돌진 — 두 번째도 매달린다(매달리기 2번 · 미룬 돌진 eq 가 쓰였다)', r['starts'] == 2 and r['eqMax'] >= 1 and r['eqEnd'] == 0, r)
            r = await pg.evaluate('()=>__rt.echo(8,1)')
            check('[라] 각성은 항상 두 번 — 매달리기 2번 이상', r['starts'] >= 2 and r['eqEnd'] == 0, r)
            for kind in ('el', 'bg'):
                r = await pg.evaluate('([k])=>__rt.echo(8,0,k)', [kind])
                check('[라] Lv8 %s 도 두 번 매달린다' % kind, r['starts'] == 2, r)
            for cut in (14, 20, 30):
                r = await pg.evaluate('([c])=>__rt.resume(5,0,c)', [cut])
                A, B = r['A'], r['B']
                check('[라] 이어하기(%d프레임째 저장→복구) — 복구 성공 · 매달리기 상태 그대로(hg %.2f→%.2f)' % (cut, r['R0']['hg'], r['R1']['hg']),
                      r['ok'] and r['e2'] and r['wasH'] and abs(r['R0']['hg'] - r['R1']['hg']) < 1e-6 and r['R0']['hk'] == r['R1']['hk'] and r['R0']['hs'] == r['R1']['hs'], r)
                check('[라] 이어하기 뒤 끝까지 같은 결과(보스 체력·내 자리·남은 타격 수)', abs(A['hp'] - B['hp']) < 1e-3 and abs(A['px'] - B['px']) < 1e-3 and abs(A['py'] - B['py']) < 1e-3, (A, B))
            r = await pg.evaluate('()=>__rt.resume(8,1,24)')
            check('[라] 이어하기 — Lv8 각성(미룬 돌진·6연타)도 같은 결과', r['ok'] and abs(r['A']['hp'] - r['B']['hp']) < 1e-3 and abs(r['A']['px'] - r['B']['px']) < 1e-3, r)
            r = await pg.evaluate('()=>__rt.kill(5,0)')
            check('[라] 매달린 적이 쓰러지면 바로 풀린다(hg=0 · 튕김 없음)', r['hg'] == 0 and not r['alive'] and r['hang'] <= 2 and r['yt'] <= 0, r)

            # ── 마 문구 = 값
            tx = await pg.evaluate("()=>({ds:__rh.WEAP.ram.ds,ev:__rh.WEAP.ram.ev.ds})")
            def num(s, pat):
                m = re.search(pat, s); return float(m.group(1)) if m else None
            d0, d5, d7, evd = tx['ds'][0], tx['ds'][5], tx['ds'][7], tx['ev']
            check('[마] Lv1 문구 — 시간 %s초' % Hg['t'], num(d0, r'([\d.]+)초 매달려') == Hg['t'], d0)
            check('[마] Lv1 문구 — 연타 %d번' % Hg['n'], num(d0, r'(\d+)번 연타') == Hg['n'], d0)
            check('[마] Lv1 문구 — 받는 피해 %s' % ('절반' if abs(Hg['red'] - .5) < 1e-9 else Hg['red']), ('절반' in d0) == (abs(Hg['red'] - .5) < 1e-9), d0)
            check('[마] Lv6 문구 — 마지막 한 방 +%d%%' % round((Hg['last'] - 1) * 100), num(d5, r'마지막 한 방 \+(\d+)%') == round((Hg['last'] - 1) * 100), d5)
            check('[마] Lv8 문구 — 두 번째도 매달린다', '두 번째도 매달린다' in d7, d7)
            check('[마] 각성 문구 — 매달리기 %.1f배 · 연타 %d번' % (Hg['evT'], Hg['evN']), num(evd, r'매달리기 ([\d.]+)배') == Hg['evT'] and num(evd, r'연타 (\d+)번') == Hg['evN'], evd)
            m = await pg.evaluate('()=>__rt.mut()')
            n7 = m['n7']; hang7 = n7['hits'][2:]
            check('[마] 변이 — 연타 횟수를 7 로 바꾸면 7번 때린다(p=.3 · 시간 1.4)', len(hang7) == 7 and abs(hang7[0][1] / n7['hits'][0][1] - .3) < 1e-6 and abs(n7['ph'].count('H') / 30 - 1.4) <= 2 / 30 + 1e-6, (len(hang7), n7['ph'][:40]))
            check('[마] 변이 — 받는 피해 감소를 80%% 로 바꾸면 ×0.2 (%.1f/%.1f)' % (m['red8']['mid'], m['red8']['base']), abs(m['red8']['mid'] / m['red8']['base'] - .2) < .02, m['red8'])
            bk = m['bk']; ih = bk['ph'].rfind('H')
            check('[마] 변이 — 튕김 거리를 300 으로 바꾸면 그만큼 벌어진다', abs((max(bk['ds'][ih + 1:ih + 14]) - bk['ds'][ih]) - 300) < 8, (bk['ds'][ih], max(bk['ds'][ih + 1:ih + 14])))

            # ── 바 전수
            res = await pg.evaluate('()=>__rt.sweep()')
            errs_ = [x for x in res if 'err' in x]
            nanb = [x for x in res if x.get('bad')]
            noh = [x for x in res if 'err' not in x and x['hang'] == 0 and x['L'] >= 1]
            stuck = [x for x in res if 'err' not in x and (x['maxHang'] > (Hg['t'] * Hg['evT'] * 30 + 3))]
            check('[바] 전수 %d판(Lv1~8 × 각성 × 3모드 × 맨몸/가득 × 보스·정예·대형) 오류 0' % len(res), not errs_, errs_[:2])
            check('[바] NaN·무한대 0', not nanb, nanb[:2])
            check('[바] 모든 판에서 매달리기가 켜졌다 · 한 번이 최대 시간을 넘지 않는다(안 풀리는 판 0)', not noh and not stuck, (noh[:2], stuck[:2]))
            check('[바] 매달리기가 판 끝에 풀려 있다(hg=0 또는 진행 중 ≤ 최대 시간)', all(x['hgEnd'] <= Hg['t'] * Hg['evT'] + 1e-6 for x in res if 'err' not in x))
            check('[바] 페이지 오류 0', not errs, errs[:3])
            await b.close()
    finally:
        srv.close()
        for f in (NEW, OLD, 'survivors_ramhang_src.html'):
            try: os.remove(os.path.join(ROOT, f))
            except Exception: pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not FAILS else '실패', len(FAILS)))
    return 1 if FAILS else 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
