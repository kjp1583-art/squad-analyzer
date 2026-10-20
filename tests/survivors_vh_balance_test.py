# -*- coding: utf-8 -*-
"""⚖️ 브레스 하향 + 약한 무기 상향 + 베리하드 보정 시험 (2026-10-15 사장님 「브레스는 하향, 다른 무기는 상향해서 평균값으로」 · 「베리하드를 용조련사 말고는 깰 수가 없어」).
사용: python3 tests/survivors_vh_balance_test.py      (종료코드 0 = 전부 통과)
무엇을 지키나
  A 수치표: 바뀐 값(BRT · U3 · W4)이 새 값이고, 손대지 않은 이웃 무기는 옛 값 그대로다. 바뀐 무기의 피해 말고 다른 필드(쿨 · 범위 · 속도 …)도 그대로다.
  B 브레스: 실제 코드로 쏴서 한 번 맞는 피해 = BRT.d × 레벨 배율 × (각성이면 1.2). 각성 사거리 1.4배 · 쿨타임 0.7배는 그대로.
  C 「값에서 읽는다」: 튀김기 · 초밥은 예전에 코드 안에 박혀 있던 숫자였다 — 표 값을 2배로 바꾸면 낸 피해도 2배가 되어야 한다(숨은 옛 상수가 남아 있지 않다).
  D 문구: 브레스 각성 카드의 숫자가 BRT 값과 같다.
  E 난이도 상수: 하드 · 베리하드 상수(HARD · HARD_V)가 기대한 값이다 — 하드·일반은 손대지 않았다.
임시 사본(survivors_x.html)에만 훅을 꽂는다 — 원본은 건드리지 않는다."""
import asyncio, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SV_CSX_OFF', '1')
import sv_harness as H
H.HOOK += r"""
window.__vbt={U3,W4,BRT,get HARD(){return HARD},get HARD_V(){return HARD_V},acc:0};
{const _h=hurt;hurt=function(e,d){const h0=e.hp;_h(e,d);window.__vbt.acc+=h0-e.hp;};}
"""
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)

# 바뀐 값 (표 · 무기 · 필드 · 옛 값 → 새 값) — 피해만 올렸다
UP = [('W4', 'fryer', 'd', 5, 15), ('W4', 'sushi', 'd', 12, 34), ('W4', 'shrimp', 'd', 14, 28), ('W4', 'spk', 'd', 8, 16), ('W4', 'meteor', 'd', 5, 14), ('W4', 'rkt', 'd', 6, 18),
      ('W4', 'frost', 'd', 44, 50), ('W4', 'bell', 'd', 5.5, 7), ('U3', 'cart', 'd', 5, 20), ('U3', 'eom', 'd', 48, 54),
      ('U3', 'sing', 'd', 5.9, 7), ('U3', 'sing', 'db', 1.7, 2), ('U3', 'quill', 'd', 11.5, 16), ('U3', 'heart', 'd', 16, 21), ('U3', 'pcards', 'd', 13, 19.5),
      ('U3', 'slime', 'd', 17, 24), ('U3', 'slime', 'bd', 9.1, 12.8)]
# 브레스 (옛 → 새): 피해만 29 → 11. 나머지(사거리 · 반각 · 쿨 · 각성 배율)는 그대로
BRT_NEW = {'d': 5.5}
BRT_SAME = {'R': 190, 'w': .62, 'cd': .85, 'em': 30}
# 손대지 않은 이웃 (옛 값 그대로 — 평균 이상이거나 평균 근처인 무기)
SAME = [('U3', 'tempo', 'd', 3.2), ('U3', 'fuse', 'd', 30), ('U3', 'jhin', 'd', 7.7), ('U3', 'whop', 'd', 12), ('U3', 'bash', 'd', 36), ('U3', 'snack', 'd', 20),
        ('U3', 'twin', 'd', 15), ('U3', 'stamp', 'd', 40), ('U3', 'chain', 'd', 8), ('U3', 'ram', 'd', 46),
        ('W4', 'pan', 'd', 52), ('W4', 'chick', 'd', 12), ('W4', 'rod', 'd', 60), ('W4', 'lid', 'd', 110), ('W4', 'snipe', 'd', 105), ('W4', 'hole', 'd', 1.3)]
# 피해 말고 다른 필드는 옛 값 그대로
OTHER = {('W4', 'rkt'): {'R': 46, 'cd': 1.7, 'sp': 750}, ('W4', 'meteor'): {'bp': .0036, 'R': 70, 'cd': 6.5, 'dl': 1.1}, ('W4', 'frost'): {'R': 110, 'cd': 4.5}, ('W4', 'bell'): {'R': 90, 'iv': .75},
         ('U3', 'cart'): {'cd': 7, 'R': 70, 'life': 5, 'heal': 1.5}, ('U3', 'eom'): {'cd': 4, 'R': 135, 'kd': 55, 'kt': .3},
         ('U3', 'sing'): {'cd': 1.6, 'iv': .24, 'sp': 380, 'life': .8, 'rng': 300}, ('U3', 'quill'): {'cd': 1, 'sp': 520, 'life': .45, 'rng': 270},
         ('U3', 'heart'): {'cd': 1.1, 'life': 2.6, 'stun': .7}, ('U3', 'pcards'): {'cd': 1.7, 'sp': 430, 'life': .7, 'rng': 290},
         ('U3', 'slime'): {'cd': 1.5, 'sp': 310, 'rng': 330, 'R': 40}}

# 한 번 쏴서 맞은 피해 · 사거리 · 쿨타임을 잰다(더미 적 하나 · 무적 · 다른 무기 없음)
BREATH = r"""([L,ev])=>{const X=window.__p6x;X.CH_set('yj');X.start();const S=X.S;
  for(const o of X.enemies.a)o.on=false;
  S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;S.w={breath:L};S.ev=ev?{breath:1}:{};S.tier={};S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};X.tkCalc();X.synCalc();
  const e=X.spawnEnemy(0,1);e.x=S.p.x+90;e.y=S.p.y;e.hp=e.mhp=1e12;e.sp=0;e.r=14;
  S.cd.breath=0;const h0=e.hp;X.update(1/30);
  return {dmg:h0-e.hp,R:S.br.R,cd:S.cd.breath}}"""
# 가만히 선 불사 허수아비 앞에서 무기 하나만 돌려 낸 피해 합 (표 값을 mul 배 한 뒤)
RUN = r"""(a)=>{const x=__p6x,w=window.__vbt,dt=1/30;
 const mb=s=>()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(a.seed);
 const T=w[a.tab][a.w],save=T.d;T.d=save*a.mul;
 x.CH_set('brj');x.newRun();x.state='play';const S=x.S,P=S.p;S.t=300;
 S.w={};S.w[a.w]=a.L;S.ev={};S.tier={};S.cd={};S.cd[a.w]=0;S.ps={};S.pt={};S.tr={};S.rel={};S.sm={};
 x.tkCalc();x.synCalc();
 S.nextBoss=S.nextMini=S.nextSp=S.evT=S.bigT=1e12;S.propT=S.chickT=1e12;S.spawnT=-1e12;S.need=1e12;S.xp=0;
 for(const e of x.enemies.a)e.on=false;x.props.clear();
 const D=[];for(let i=0;i<7;i++){const th=i*0.9,R=70+i*28;const e=x.spawnEnemy(0,1,null,{x:Math.cos(th)*R,y:Math.sin(th)*R});e.hx=e.x=Math.cos(th)*R;e.hy=e.y=Math.sin(th)*R;e.sp=0;e.kb=0;e.hp=e.mhp=1e12;D.push(e);}
 w.acc=0;
 for(let s=0;s<240;s++){P.hp=P.mhp=1e9;P.inv=1e9;S.spawnT=-1e12;S.need=1e12;S.xp=0;for(const e of D){e.on=true;e.x=e.hx;e.y=e.hy;e.hp=e.mhp;e.sp=0;}x.update(dt);}
 T.d=save;return {dmg:w.acc};}"""
LV = lambda L: (1.4 if L >= 3 else 1) * (1.4 if L >= 5 else 1) * (1.5 if L >= 8 else 1)


async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        tab = await pg.evaluate("()=>{const w=window.__vbt;return {U3:JSON.parse(JSON.stringify(w.U3)),W4:JSON.parse(JSON.stringify(w.W4)),BRT:JSON.parse(JSON.stringify(w.BRT)),HARD:w.HARD,HARD_V:w.HARD_V}}")
        # ───────────────── A. 수치표
        bad = [(t, k, f, tab[t][k][f], new) for t, k, f, old, new in UP if abs(tab[t][k][f] - new) > 1e-9]
        check('A1 올린 무기 17개 값이 새 값이다(튀김기 · 초밥 · 새우깡 · 스피커 · 운석 · 폭죽 · 얼음땡 · 리듬 · 카트 · 엄! 외침 · 노래부르기 · 깃털 · 하트 · 포토카드 · 슬라임)', not bad, bad)
        check('A2 올린 값은 전부 옛 값보다 크다(올리기만 했다)', all(new > old for t, k, f, old, new in UP))
        bad = {k: tab['BRT'].get(k) for k, v in BRT_NEW.items() if abs(tab['BRT'].get(k, -9) - v) > 1e-9}
        check('A3 브레스 BRT.d = 5.5', not bad, bad)
        check('A4 브레스는 내렸다(d 29 → 11)', tab['BRT']['d'] < 29)
        bad = {k: tab['BRT'].get(k) for k, v in BRT_SAME.items() if abs(tab['BRT'].get(k, -9) - v) > 1e-9}
        if sorted(tab['BRT']) != sorted(list(BRT_SAME) + list(BRT_NEW)): bad['keys'] = sorted(tab['BRT'])
        check('A5 브레스의 사거리 · 반각 · 쿨타임 · 몸 주변 반경은 그대로(새 필드도 없다)', not bad, bad)
        bad = [(t, k, f, tab[t][k][f], old) for t, k, f, old in SAME if abs(tab[t][k][f] - old) > 1e-9]
        check('A6 손대지 않은 이웃 무기(노래 · 깃털 · 집중겜 · 하트 · 프라이팬 · 병아리 …)의 피해는 옛 값 그대로', not bad, bad)
        bad = [(t, k, f, tab[t][k].get(f), v) for (t, k), fs in OTHER.items() for f, v in fs.items() if tab[t][k].get(f) != v]
        check('A7 바뀐 무기의 피해 말고 다른 필드(쿨 · 사거리 · 범위 · 보스 비율 …)는 옛 값 그대로', not bad, bad)
        check('A8 튀김기 · 초밥 · 새우깡 · 스피커 표에는 피해(d)만 있다(새 필드를 끼워 넣지 않았다)', all(list(tab['W4'][k]) == ['d'] for k in ('fryer', 'sushi', 'shrimp', 'spk')))
        # ───────────────── B. 브레스
        for L, ev in ((2, False), (3, False), (5, False), (8, False), (8, True)):
            r = await pg.evaluate(BREATH, [L, ev])
            want = 5.5 * LV(L) * (1.2 if ev else 1)
            check('B Lv%d%s 한 번 맞는 피해 %.3f (기대 %.3f)' % (L, ' 🌙각성' if ev else '', r['dmg'], want), r['dmg'] > 0 and abs(r['dmg'] - want) < 1e-5 * max(1, want) + 1e-6, r)
        a = await pg.evaluate(BREATH, [8, False]); c = await pg.evaluate(BREATH, [8, True])
        check('B 각성 사거리 비율 1.4배 그대로 (%.4f)' % (c['R'] / a['R']), abs(c['R'] / a['R'] - 1.4) < 1e-6, (a, c))
        check('B 각성 쿨타임 비율 0.7배 그대로 (%.4f)' % (c['cd'] / a['cd']), abs(c['cd'] / a['cd'] - .7) < 1e-6, (a, c))
        # ───────────────── C. 값에서 읽는다 (표 ×2 → 피해 합 ×2)
        for tabn, w in (('W4', 'fryer'), ('W4', 'sushi'), ('W4', 'shrimp'), ('W4', 'spk'), ('W4', 'meteor')):
            for L in (1, 8):
                a = dict(w=w, L=L, tab=tabn, seed=7)
                r1 = await pg.evaluate(RUN, dict(a, mul=1)); r2 = await pg.evaluate(RUN, dict(a, mul=2))
                ratio = r2['dmg'] / r1['dmg'] if r1['dmg'] > 0 else 0
                check('C %s Lv%d: 무기가 실제로 피해를 냈다(%.0f)' % (w, L, r1['dmg']), r1['dmg'] > 0)
                check('C %s Lv%d: 표 피해 ×2 → 낸 피해 합 ×2.000 (%.4f)' % (w, L, ratio), abs(ratio - 2) < 2e-3, ratio)
        # ───────────────── D. 문구(브레스 각성 배율은 안 바꿨다 — 문구도 그대로)
        ds = await pg.evaluate("()=>__p6x.WEAP.breath.ev.ds")
        check('D1 브레스 각성 카드 문구(사거리 1.4배 · 피해 1.2배)가 실제 배율과 같다', '사거리 1.4배' in ds and '피해 1.2배' in ds, ds)
        # ───────────────── E. 난이도 상수
        check('E1 하드 상수는 그대로(HARD)', tab['HARD'] == {'hp': 2, 'bhp': 1.5, 'atk': 1.25, 'rate': 1.15, 'chk': .15}, tab['HARD'])
        check('E2 베리하드 상수(HARD_V)가 기대한 값', tab['HARD_V'] == VH_EXPECT, tab['HARD_V'])
        check('시험 중 스크립트 오류 없음', not errs, errs[:3])
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('\n%d 개 중 실패 %d: %s' % (N[0], len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)

VH_EXPECT = {'hp': 3.6, 'bhp': 2.1, 'atk': 1.55, 'rate': 1.3, 'chk': .08, 'ev': .72}   # 베리하드를 조정하면 여기도 같이 고친다
asyncio.run(main())
