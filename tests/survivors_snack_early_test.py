# -*- coding: utf-8 -*-
"""🍘 맛동산 투척 초반(Lv1~4) 상향 시험 — 2026-10-07 사장님 지시 "맛동산장인 유미의 맛동산 고유무기 1레벨구간 상향".
사용: python3 tests/survivors_snack_early_test.py
 ① 단계표: Lv1~8 의 스틱 수·부스러기 수·스틱 피해·쿨타임이 설명문(WEAP.snack.ds)과 맞고, 부스러기가 정말 그 수만큼 튄다
 ② 아레나(적 밀집 · 고정 시드 · 여러 번 평균 · 10초 누적 피해): Lv1~4 는 예전보다 뚜렷이 세졌고(하한) · 레벨이 오를수록 세지며(단조) ·
    Lv5 이후와 각성은 예전 그대로(±6%) — 후반 폭주 방지
 ③ 적이 없어도 필드 아이템에 맞으면 부스러기가 튄다(기존 동작)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 훅을 꽂는다. 수치를 일부러 바꿀 때는 아래 LADDER · OLD 를 같이 고친다."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright

FAILS = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

# 레벨 → (스틱 수, 부스러기 수, 스틱 피해, 쿨타임 초) — 설명문(ds)이 말하는 단계표 그대로
LADDER = {1: (1, 6, 11.0, 1.3), 2: (1, 7, 11.0, 1.3), 3: (2, 7, 13.2, 1.3), 4: (2, 7, 13.2, 1.105),
          5: (2, 7, 15.84, 1.105), 6: (3, 7, 15.84, 1.105), 7: (3, 8, 15.84, 0.93925), 8: (3, 8, 23.76, 0.93925)}
# 설명문 8줄에 꼭 들어 있어야 하는 말
DS_TOKENS = {0: ['부스러기 6개'], 1: ['부스러기 +1'], 2: ['피해 +20%', '스틱 +1'], 3: ['쿨타임 -15%'], 4: ['피해 +20%'], 5: ['스틱 +1'],
             6: ['부스러기 +1', '쿨타임 -15%'], 7: ['피해 +50%']}
# 상향 전(2026-10-07 이전) 아레나 10초 누적 피해 — 같은 아레나 · 같은 시드 24개 평균 (Lv1~8 · 각성)
OLD = {1: 165.3, 2: 184.0, 3: 412.3, 4: 507.6, 5: 620.0, 6: 924.8, 7: 1172.1, 8: 1577.0, 'ev': 3230.5}
# 초반은 예전의 몇 배 이상이어야 하고(하한), Lv5 이후·각성은 예전의 ±6% 안이어야 한다
EARLY_MIN = {1: 1.30, 2: 1.25, 3: 1.10, 4: 1.05}
LATE_BAND = 0.06
SEEDS = 24

SEED = r"""let s=(a.seed*2654435761)>>>0;Math.random=()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};"""

# ── ① 단계표: 샌드백 하나(안 움직이고 안 죽음)에게 한 번 던지게 해서 스틱·부스러기를 센다
LADDER_JS = r"""(a)=>{const x=__p6x;""" + SEED + r"""
 x.CH_set('brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w={snack:a.L};S.cd={};S.ev={};S.tier={};S.ps={};x.tkCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();
 const e=x.spawnEnemy(0,2.5,null,{x:p.x+150,y:p.y});e.hp=e.mhp=1e9;e.sp=0;
 const o={n:0,d:0,m:0,sdr:0,cd:0,crumbs:0,bursts:0,dmgFirst:0};let prev=0,first=true;
 for(let i=0;i<75;i++){S.p.hp=S.p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;x.keys={};e.x=p.x+150;e.y=p.y;e.hp=e.mhp=1e9;
   x.update(dt);const f=S.x3.f,sn=f.filter(q=>q.k==='sn');
   if(first){if(sn.length){first=false;o.n=sn.length;o.d=sn[0].d;o.m=sn[0].m;o.sdr=sn[0].sd/sn[0].d;o.cd=S.cd.snack;prev=sn.length;}continue;}   // 던진 프레임: 스틱·쿨타임을 읽는다
   const b=prev-sn.length;if(b>0){if(!o.bursts)o.dmgFirst=S.dmgBy.snack||0;o.bursts+=b;}prev=sn.length;   // 부서진 스틱 수 · 처음 부서질 때까지 넣은 피해
   o.crumbs+=f.filter(q=>q.k==='b'&&q.src==='snack'&&q.life===.4).length;   // 이번 프레임에 막 생긴 부스러기(아직 한 번도 안 움직인 것 = 수명이 처음 값 그대로)
   if(!sn.length)break;}   // 첫 던짐의 스틱이 다 부서지면 끝(쿨타임 전에 다음 던짐이 섞이지 않게)
 return o;}"""

# ── ② 아레나: 체력 100% 잡몹 45마리를 계속 채움(자연 스폰 없음) · 무기 하나만 · 불사 · 같은 봇이 사각형으로 움직임 · 예열(3~11초 무작위) 뒤 10초
ARENA_JS = r"""(a)=>{const x=__p6x;""" + SEED + r"""
 x.CH_set('brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w={snack:a.L};S.cd={};S.ev=a.ev?{snack:1}:{};S.tier={};S.ps={};x.tkCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 const fill=()=>{let c=0;for(const q of x.enemies.a)if(q.on)c++;
   for(;c<45;c++){const g=Math.random()*6.2832,r=140+Math.random()*280;
     if(!x.spawnEnemy((Math.random()*3)|0,2.5,null,{x:p.x+Math.cos(g)*r,y:p.y+Math.sin(g)*r}))break;}};
 const step=()=>{if(x.state==='lvup'){x.pick(x.CUR[0]);return;}if(x.state!=='play'){x.resume();return;}
   S.p.hp=S.p.mhp;S.spawnT=-1e12;S.xp=0;S.need=1e12;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
   fill();x.update(dt);x.props.clear();};
 const W=Math.round((3+8*Math.random())/dt);for(let i=0;i<W;i++)step();
 S.dmgBy={};for(let i=0;i<300;i++)step();
 return {d:S.dmgBy.snack||0,state:x.state};}"""

# ── ③ 적이 없고 필드 아이템(와드)만 있을 때: 스틱이 아이템에 맞아 부스러기가 튄다
PROP_JS = r"""(a)=>{const x=__p6x;""" + SEED + r"""
 x.CH_set('brj');x.start();const S=x.S,p=S.p,dt=1/30;
 S.w={snack:a.L};S.cd={};S.ev={};S.tier={};S.ps={};x.tkCalc();
 S.t=90;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
 for(const q of x.enemies.a)q.on=false;x.props.clear();
 let q=null;for(const c of x.props.a)if(!c.on){q=c;break;}
 q.on=true;q.k=1;q.x=p.x+120;q.y=p.y;q.hp=22;q.hit=0;const hp0=q.hp;let crumbs=0,broke=false;
 for(let i=0;i<60;i++){S.p.hp=S.p.mhp;S.spawnT=-1e12;S.need=1e12;x.keys={};x.update(dt);
   crumbs+=S.x3.f.filter(o=>o.k==='b'&&o.src==='snack'&&o.life===.4).length;if(!q.on||q.hp<hp0)broke=true;}
 return {hit:broke,crumbs};}"""

def mean(v): return sum(v) / len(v)

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)

        # ── ① 단계표 · 설명문
        ds = await pg.evaluate("()=>__p6x.WEAP.snack.ds")
        check('설명문(ds) 8줄', len(ds) == 8, len(ds))
        for i, toks in DS_TOKENS.items():
            check('ds[%d](Lv%d) 문구: %s' % (i, i + 1, ' · '.join(toks)), all(t in ds[i] for t in toks), ds[i])
        got = {}
        for L in range(1, 9):
            o = await pg.evaluate(LADDER_JS, {'L': L, 'seed': 7})
            got[L] = o
            n, m, d, cd = LADDER[L]
            ok = (o['n'] == n and o['m'] == m and abs(o['d'] - d) < d * .005 and abs(o['cd'] - cd) < cd * .005
                  and abs(o['sdr'] - .55) < .001 and o['bursts'] == n and o['crumbs'] == n * m)
            check('Lv%d 단계표: 스틱 %d · 부스러기 %d · 피해 %.2f · 쿨 %.3f초 (부스러기가 실제로 %d개 튐)' % (L, n, m, d, cd, n * m), ok, o)
            k = o['dmgFirst'] / d
            check('Lv%d 스틱이 처음 맞을 때 넣는 피해 = 스틱 피해(%.2f)의 정수배(같은 프레임에 맞은 스틱 수)' % (L, d), abs(k - round(k)) < .01 and 1 <= round(k) <= n, o['dmgFirst'])
        # 설명문이 말하는 단계 폭 — 앞 레벨과의 비율
        r = lambda L, k: got[L][k] / got[L - 1][k]
        check('Lv3: 피해 +20% · 스틱 +1', abs(r(3, 'd') - 1.2) < .005 and got[3]['n'] == got[2]['n'] + 1, (r(3, 'd'), got[3]['n']))
        check('Lv4: 쿨타임 -15% (부스러기는 그대로)', abs(r(4, 'cd') - .85) < .005 and got[4]['m'] == got[3]['m'], (r(4, 'cd'), got[4]['m']))
        check('Lv5: 피해 +20%', abs(r(5, 'd') - 1.2) < .005, r(5, 'd'))
        check('Lv7: 부스러기 +1 · 쿨타임 -15%', got[7]['m'] == got[6]['m'] + 1 and abs(r(7, 'cd') - .85) < .005, (got[7]['m'], r(7, 'cd')))
        check('Lv8: 피해 +50%', abs(r(8, 'd') - 1.5) < .005, r(8, 'd'))
        check('시작(Lv1)부터 예전(스틱 피해 8 · 부스러기 5)보다 세다', got[1]['d'] >= 10.5 and got[1]['m'] >= 6, (got[1]['d'], got[1]['m']))

        # ── ② 아레나
        res = {}
        for key in list(range(1, 9)) + ['ev']:
            L = 8 if key == 'ev' else key
            v = []
            for sd in range(1, SEEDS + 1):
                o = await pg.evaluate(ARENA_JS, {'L': L, 'seed': sd, 'ev': key == 'ev'})
                v.append(o['d'])
                if o['state'] != 'play': check('아레나 도중 판이 끝나지 않음', False, (key, sd, o))
            res[key] = mean(v)
        print('\n아레나 10초 누적 피해(시드 %d개 평균):' % SEEDS)
        for key in res: print('  %-3s 지금 %7.1f   예전 %7.1f   (%+.0f%%)' % (key, res[key], OLD[key], 100 * (res[key] / OLD[key] - 1)))
        for L, mn in EARLY_MIN.items():
            check('Lv%d 는 예전의 %.2f배 이상 (%.0f → %.0f)' % (L, mn, OLD[L], res[L]), res[L] >= OLD[L] * mn, '%.1f / %.1f = %.2f배' % (res[L], OLD[L], res[L] / OLD[L]))
        check('레벨이 오를수록 세진다 (Lv1<Lv2<…<Lv8)', all(res[L] < res[L + 1] for L in range(1, 8)), [round(res[L]) for L in range(1, 9)])
        for key in (5, 6, 7, 8, 'ev'):
            lo, hi = OLD[key] * (1 - LATE_BAND), OLD[key] * (1 + LATE_BAND)
            check('%s 은 예전 그대로(±%d%%): %.0f ~ %.0f' % ('Lv%d' % key if key != 'ev' else 'Lv8 각성', LATE_BAND * 100, lo, hi), lo <= res[key] <= hi, round(res[key], 1))
        check('각성(Lv8)은 일반 Lv8 보다 강하다', res['ev'] > res[8] * 1.5, (round(res['ev']), round(res[8])))

        # ── ③ 필드 아이템
        for L in (1, 2, 6, 8):   # 스틱이 1·3개인 레벨 — 가운데 스틱이 정면으로 날아간다(2개면 좌우로 벌어져 아이템 옆을 지날 수 있다)
            o = await pg.evaluate(PROP_JS, {'L': L, 'seed': 11})
            check('Lv%d: 적이 없어도 필드 아이템에 맞고 부스러기가 튄다' % L, o['hit'] and o['crumbs'] >= LADDER[L][1], o)

        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        await b.close()
    srv.close()
    print('\n%s' % ('실패 %d: %s' % (len(FAILS), FAILS) if FAILS else '전부 통과'))
    return 1 if FAILS else 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
