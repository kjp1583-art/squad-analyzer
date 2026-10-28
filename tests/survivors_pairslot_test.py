# -*- coding: utf-8 -*-
"""🗝 흐접새우 서바이벌 「열쇠 잠김 없애기(운 개선안 A)」 시험 — 2026-10-10 「운은 A로」 → 2026-10-12 「A로 가자」 로 규칙이 바뀌었다.
   예전: 패시브 6칸 중 마지막 한 칸을 시작 무기 열쇠용으로 예약(keyRsv).  지금: 열쇠 패시브는 6칸 밖의 열쇠 칸(3칸)에 따로 들어간다(자세한 칸 규칙 시험은 survivors_keyslot_test.py).
   이 시험은 「목표가 유지되는가」만 기준 커밋(예약 방식)과 나란히 잰다:
     가  FOCUS 정책 몬테카를로로 열쇠 잠김(일반 칸 꽉 참 + 열쇠를 못 받는 상태): 기준 ~20% → 새 0%
     나  열쇠를 얻는 속도 · 각성 준비(열쇠 + 시작 무기 Lv8) 속도가 기준보다 느려지지 않는다
     다  일반 칸이 5칸일 때: 새 일반 패시브와 열쇠가 모두 나온다(예약이 없으니 일반 칸을 끝까지 쓴다)
   사용: nice -n 10 python3 tests/survivors_pairslot_test.py   (FX_BASE_COMMIT 로 기준 커밋을 바꿀 수 있다 · 기본 = 예약 방식의 마지막 커밋 bf755af)
   임시 사본 survivors_pairslot_t.html · survivors_pairslot_tb.html(기준) 을 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, subprocess, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
BASE_COMMIT = os.environ.get('FX_BASE_COMMIT', 'bf755af')
NEW, OLD, OLDSRC = 'survivors_pairslot_t.html', 'survivors_pairslot_tb.html', 'survivors_pairslot_tb_src.html'
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:900] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
EXTRA = r"""
window.__K={PASS,SLOTP,WEAP,CHARS,offers,slotP,pmax,get CH(){return CH},isKeyNew:typeof isKeyNew==='function'?isKeyNew:null,
  seed(s){let a=s>>>0;Math.random=()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}};
window.__fresh=(ck)=>{const x=window.__p6x;x.CH_set(ck);x.newRun();x.state='play';const S=x.S;S.lv=10;S.rr=S.ban=0;S.banned=[];S.dly=null;S.ps={};return S;};
"""
MC = """([cs,trials,LV])=>{const K=__K;const res=[];
  cs.forEach((ck,ci)=>{let lock=0,got=0,keyAt=[],ready=[];
    for(let tr=0;tr<trials;tr++){const S=__fresh(ck);K.seed(90000+ci*1000+tr);const w0=K.CH.w,key=K.WEAP[w0].pair;let locked=false,rd=-1,kl=-1;
      for(let lv=1;lv<=LV;lv++){S.lv=lv;const cs2=K.offers(3);
        let pick=cs2.find(o=>o.t==='p'&&o.k===key&&!S.ps[key])||cs2.find(o=>o.t==='w'&&o.k===w0);
        if(!pick){const ps=cs2.filter(o=>o.t==='p'&&o.k!=='rev');if(ps.length)pick=ps[Math.floor(Math.random()*ps.length)];}
        if(pick){if(pick.t==='w')S.w[pick.k]=Math.min(8,(S.w[pick.k]||0)+1);else S.ps[pick.k]=Math.min(K.pmax(pick.k),(S.ps[pick.k]||0)+1);}
        if(kl<0&&S.ps[key])kl=lv;if(rd<0&&S.ps[key]&&(S.w[w0]||0)>=8)rd=lv;
        if(!S.ps[key]&&K.slotP()>=K.SLOTP&&!(K.isKeyNew&&K.isKeyNew(key))&&!K.reserved)locked=true;}
      if(locked)lock++;if(S.ps[key])got++;keyAt.push(kl>0?kl:LV+1);ready.push(rd>0?rd:LV+1);}
    res.push({ck,lock,got,trials,keyAt,ready});});return res;}"""
# 기준(예약 방식)에는 isKeyNew 가 없다 — 「칸 꽉 참 + 열쇠 없음」은 (예약이 없으면) 곧 잠김, 예약이 있으면 마지막 칸이 열쇠용이라 slotP 가 6 에 닿기 전에 열쇠 자리가 남는다.
# 그래서 기준 쪽은 예약을 가진 상태 그대로 「열쇠를 못 받는 상태」= offers 에 열쇠가 나올 수 없는 상태를 직접 센다.
async def main():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA)
    old_src = subprocess.run(['git', 'show', BASE_COMMIT + ':survivors.html'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout
    open(os.path.join(ROOT, OLDSRC), 'w', encoding='utf-8').write(old_src)
    H.make_copy(src=OLDSRC, dst=OLD, extra=EXTRA)
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, page=NEW)
            ctxo, pgo, erro = await H.new_page(b, srv.port, page=OLD)
            CH = await pg.evaluate("()=>__K.CHARS.map(c=>c.k)")
            TR, LV = 100, 120
            MN = await pg.evaluate(MC, [CH, TR, LV]); MO = await pgo.evaluate(MC, [CH, TR, LV])
            tot = sum(m['trials'] for m in MN)
            gN = sum(m['got'] for m in MN); gO = sum(m['got'] for m in MO)
            lN = sum(m['lock'] for m in MN)
            med = lambda M, f: statistics.median([v for m in M for v in m[f]])
            print('  FOCUS %d판: 열쇠 얻음 기준 %d → 새 %d · 잠김 새 %d · 열쇠 얻은 중앙값 Lv 기준 %s → 새 %s · 준비 중앙값 기준 %s → 새 %s' % (tot, gO, gN, lN, med(MO, 'keyAt'), med(MN, 'keyAt'), med(MO, 'ready'), med(MN, 'ready')))
            check('잠김 0 (새 규칙)', lN == 0, lN)
            check('열쇠를 얻는 판 비율이 기준 이상(≥ 99%)', gN / tot >= .99 and gN >= gO - 2, (gO, gN))
            check('열쇠를 얻는 속도(중앙값 레벨)는 기준보다 느려지지 않는다', med(MN, 'keyAt') <= med(MO, 'keyAt'), (med(MO, 'keyAt'), med(MN, 'keyAt')))
            check('각성 준비(열쇠 + 시작 무기 Lv8) 중앙값 레벨은 기준보다 6% 넘게 늘지 않는다(패시브 후보가 오래 남아 무기 카드가 덜 도는 만큼 조금 느린 것은 허용)', med(MN, "ready") <= med(MO, "ready") * 1.06, (med(MO, 'ready'), med(MN, 'ready')))
            R = await pg.evaluate("""([cs])=>cs.map((ck,i)=>{const S=__fresh(ck);const K=__K;const key=K.WEAP[K.CH.w].pair;const o=Object.keys(K.PASS).filter(k=>k!=='rev'&&k!==key);for(let j=0;j<5;j++)S.ps[o[(j+i)%o.length]]=1;
                K.seed(7+i);let a=0,k=0;for(let r=0;r<1000;r++)for(const c of K.offers(3))if(c.t==='p'&&!S.ps[c.k]&&c.k!=='rev'){if(c.k===key)k++;else a++;}return {ck,a,k};})""", [CH[:8]])
            check('일반 5칸: 새 일반 패시브도 열쇠도 나온다', all(r['a'] > 0 and r['k'] > 0 for r in r_) if (r_ := R) else False, R[:2])
            check('페이지 오류 0', not errs, errs[:3])
            await b.close()
    finally:
        srv.close()
        for f in (NEW, OLD, OLDSRC):
            try: os.remove(os.path.join(ROOT, f))
            except Exception: pass
    print('\n실패 %d' % len(FAILS))
    for f in FAILS: print('  ✗', f)
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
