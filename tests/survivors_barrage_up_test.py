# -*- coding: utf-8 -*-
"""⚖️ 범위 좁은 탄막형 고유 무기 + 단일 대상 공용 무기 피해 상향 시험 (2026-10-12 사장님 지시 「데미지라도 쎄야」).
사용: python3 tests/survivors_barrage_up_test.py      (종료코드 0 = 전부 통과)
무엇을 지키나
  A 수치표: 올린 값(U3 · W4)이 새 값이고, 손대지 않은 이웃 무기(집중겜·유미·하트·카트·부시 …)는 옛 값 그대로다.
  B 「값에서 읽는다」: 무기 한 자루만 든 판에서 그 무기가 낸 피해 합이 표의 피해 값에 정확히 비례한다(표 값을 2배로 바꾸면 합도 2배) —
     코드 안에 숨은 옛 상수(키보드 난타의 16 같은)가 남아 있으면 여기서 걸린다.
  C 범위·쿨·개수는 그대로: 올린 무기의 d 말고 다른 필드(cd · R · sp · rng · len · life …)가 옛 값 그대로다.
임시 사본(survivors_x.html)에만 훅을 꽂는다 — 원본은 건드리지 않는다."""
import asyncio, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
H.HOOK += r"""
window.__wbt={U3,W4,acc:0};
{const _h=hurt;hurt=function(e,d){const h0=e.hp;_h(e,d);window.__wbt.acc+=h0-e.hp;};}
"""
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)

# 올린 값 (표 · 필드 · 옛 값 → 새 값)
UP = [('U3', 'sing', 'd', 4.5, 5.9), ('U3', 'sing', 'db', 1.3, 1.7), ('U3', 'quill', 'd', 6.5, 11.5), ('U3', 'jhin', 'd', 7, 7.7),
      ('U3', 'slime', 'd', 13, 17), ('U3', 'slime', 'bd', 7, 9.1), ('U3', 'pcards', 'd', 8, 13), ('U3', 'heart', 'd', 14, 18),
      ('W4', 'rod', 'd', 48, 60), ('W4', 'snipe', 'd', 78, 105)]
# 손대지 않은 이웃 (옛 값 그대로여야 한다)
SAME = [('U3', 'tempo', 'd', 3.2), ('U3', 'fuse', 'd', 30), ('U3', 'cart', 'd', 5), ('U3', 'whop', 'd', 12), ('U3', 'bash', 'd', 36),
        ('U3', 'snack', 'd', 11), ('U3', 'twin', 'd', 15), ('U3', 'stamp', 'd', 40), ('U3', 'chain', 'd', 8), ('U3', 'ram', 'd', 46), ('U3', 'eom', 'd', 48),
        ('W4', 'chick', 'd', 12), ('W4', 'pan', 'd', 52), ('W4', 'rkt', 'd', 6), ('W4', 'frost', 'd', 44), ('W4', 'lid', 'd', 110), ('W4', 'meteor', 'd', 5), ('W4', 'hole', 'd', 1.3), ('W4', 'bell', 'd', 5.5)]
# 피해 말고 다른 필드는 옛 값 그대로
OTHER = {('U3', 'sing'): {'cd': 1.6, 'iv': .24, 'sp': 380, 'life': .8, 'rng': 300, 'fan': .22, 'dlt': .06, 'hit': 12, 'bsp': 280, 'blife': .9, 'bR': 44, 'btk': .45, 'm': 2, 'cr': .04, 'crm': .6, 'sl': .45, 'bsl': .9, 'reach': 280},
         ('U3', 'quill'): {'cd': 1, 'sp': 520, 'life': .45, 'rng': 270}, ('U3', 'jhin'): {'iv': .55, 'rl': .6, 'sp': 660, 'rng': 420},
         ('U3', 'slime'): {'cd': 1.5, 'sp': 310, 'rng': 330, 'R': 40}, ('U3', 'pcards'): {'cd': 1.7, 'sp': 430, 'life': .7, 'rng': 290}, ('U3', 'heart'): {'cd': 1.1, 'life': 2.6, 'stun': .7},
         ('W4', 'rod'): {'len': 260, 'cd': 3}, ('W4', 'snipe'): {'bp': .0034, 'cd': 3.4}}

# 가만히 선 불사 허수아비 한 마리 앞에서 무기 하나만 돌려, 그 무기가 낸 피해 합을 잰다. mul 이 있으면 표 값을 그만큼 곱한 뒤 잰다.
RUN = r"""(a)=>{const x=__p6x,w=window.__wbt,dt=1/30;
 const mb=s=>()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(a.seed);
 const T=w[a.tab][a.w],save={};for(const k of a.fields){save[k]=T[k];T[k]=save[k]*a.mul;}
 x.CH_set(a.ch);x.newRun();x.state='play';const S=x.S,P=S.p;S.t=300;
 S.w={};S.w[a.w]=a.L;S.ev={};S.tier={};S.cd={};S.cd[a.w]=0;S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};
 x.tkCalc();x.synCalc();
 S.nextBoss=S.nextMini=S.nextSp=S.evT=S.bigT=1e12;S.propT=S.chickT=1e12;S.spawnT=-1e12;S.need=1e12;S.xp=0;
 for(const e of x.enemies.a)e.on=false;x.props.clear();
 const D=[];for(let i=0;i<7;i++){const th=i*0.9,R=70+i*28;const e=x.spawnEnemy(0,1,null,{x:Math.cos(th)*R,y:Math.sin(th)*R});e.hx=e.x=Math.cos(th)*R;e.hy=e.y=Math.sin(th)*R;e.sp=0;e.kb=0;e.hp=e.mhp=1e12;D.push(e);}
 w.acc=0;
 for(let s=0;s<a.N;s++){P.hp=P.mhp=1e9;P.inv=1e9;S.spawnT=-1e12;S.need=1e12;S.xp=0;for(const e of D){e.on=true;e.x=e.hx;e.y=e.hy;e.hp=e.mhp;e.sp=0;}x.update(dt);}
 for(const k of a.fields)T[k]=save[k];
 return {dmg:w.acc,errs:0};}"""
CH = {'sing': 'bbb', 'quill': 'brj', 'jhin': 'ildj', 'slime': 'hrb', 'pcards': 'bgb', 'heart': 'amd', 'rod': 'brj', 'snipe': 'brj'}

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        # ───────────────── A. 수치표
        tab = await pg.evaluate("()=>{const w=window.__wbt;return {U3:JSON.parse(JSON.stringify(w.U3)),W4:JSON.parse(JSON.stringify(w.W4))}}")
        bad = [(t, k, f, tab[t][k][f], new) for t, k, f, old, new in UP if abs(tab[t][k][f] - new) > 1e-9]
        check('올린 값 10개가 새 값이다(노래부르기 d·db · 깃털 · 4발 사격 · 슬라임 d·bd · 포토카드 · 하트 · 낚싯대 · 망원경)', not bad, bad)
        check('모두 옛 값보다 크다(올리기만 했다)', all(new > old for t, k, f, old, new in UP))
        bad = [(t, k, f, tab[t][k][f], old) for t, k, f, old in SAME if abs(tab[t][k][f] - old) > 1e-9]
        check('손대지 않은 이웃 무기의 피해 값은 옛 값 그대로(집중겜 · 유미 · 카트 …  키보드 난타·사료·병아리는 일부러 안 올렸다)', not bad, bad)
        bad = [(t, k, f, tab[t][k].get(f), v) for (t, k), fs in OTHER.items() for f, v in fs.items() if tab[t][k].get(f) != v]
        check('올린 무기의 피해 말고 다른 필드(쿨 · 사거리 · 속도 · 수명 · 범위 · 보스 비율)는 옛 값 그대로', not bad, bad)
        # ───────────────── B. 값에서 읽는다 (표 ×2 → 피해 합 ×2)
        for w in ['sing', 'quill', 'jhin', 'slime', 'pcards', 'heart', 'rod', 'snipe']:
            tabn = 'W4' if w in ('rod', 'snipe') else 'U3'
            fields = [f for t, k, f, o, n in UP if k == w]
            for L in (1, 8):
                a = dict(w=w, L=L, tab=tabn, fields=fields, ch=CH[w], N=240, seed=7)
                r1 = await pg.evaluate(RUN, dict(a, mul=1)); r2 = await pg.evaluate(RUN, dict(a, mul=2))
                ratio = r2['dmg'] / r1['dmg'] if r1['dmg'] > 0 else 0
                check('%s Lv%d: 무기가 실제로 피해를 냈다(%.0f)' % (w, L, r1['dmg']), r1['dmg'] > 0)
                check('%s Lv%d: 표 피해 ×2 → 낸 피해 합 ×2.000 (%.4f)' % (w, L, ratio), abs(ratio - 2) < 2e-4, ratio)
        check('시험 중 스크립트 오류 없음', not errs, errs[:3])
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('\n%d 개 중 실패 %d: %s' % (N[0], len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
