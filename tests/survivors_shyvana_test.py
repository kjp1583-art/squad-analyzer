# -*- coding: utf-8 -*-
"""🐲 프싱 「쉬바나 코스프레」 검증 — 분노 게이지 · 용 변신 · 🔥 쌍둥이 이빨.  사용: python3 tests/survivors_shyvana_test.py
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 훅을 꽂는다."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port)
        # ── 1. 시작 상태 · 게이지가 피해·처치로 오른다
        r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('psg');x.start();const S=x.S;
          o.init={shv:x.CH.shv,w:Object.keys(S.w),rg:S.rg,dT:S.dT,camp:x.CH.camp};
          const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.x=S.p.x+500;e.y=S.p.y;
          S.rgB=2.5;x.hurt(e,5);o.hit=S.rg;
          for(let i=0;i<50;i++)x.hurt(e,5);o.burst=S.rg;   // 한꺼번에 때려도 버킷이 막는다
          S.rg=0;S.rgB=2.5;const k=x.spawnEnemy(0,1);k.hp=1;k.x=S.p.x+500;k.y=S.p.y;x.hurt(k,50);o.kill=S.rg;
          return o}""")
        check('시작: 쉬바나 패시브(shv) · camp 없음 · 시작 무기 twin · 게이지 0', r['init']['shv'] == 1 and not r['init']['camp'] and r['init']['w'] == ['twin'] and r['init']['rg'] == 0 and r['init']['dT'] == 0, r['init'])
        check('피해를 주면 게이지가 오른다', r['hit'] > 0, r['hit'])
        check('한꺼번에 때려도 흡수량 상한(버킷)이 있다', r['burst'] <= 2.6, r['burst'])
        check('처치하면 게이지가 오른다(처치 +1 이상)', r['kill'] >= 1, r['kill'])
        # ── 2. 가득 차면 변신 · 크기 · 이동속도 · 화염 오라 · 받는 피해 감소
        r = await pg.evaluate("""()=>{const x=__p6x,o={};x.CH_set('psg');x.start();const S=x.S;S.w={};S.p.hp=S.p.mhp=1e6;
          const walk=sec=>{const x0=S.p.x;x.keys={KeyD:true};for(let i=0;i<Math.round(sec*30);i++)x.update(1/30);x.keys={};return S.p.x-x0;};
          o.walk0=walk(.5);
          const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.x=S.p.x+60;e.y=S.p.y;e.sp=0;S.live=[e];
          const h0=S.p.hp;S.p.inv=0;x.hitP(100,'');o.dmg0=h0-S.p.hp;S.p.inv=0;
          S.rg=100;x.update(1/30);o.on=S.dT;o.dN=S.dN;
          e.x=S.p.x+60;e.y=S.p.y;const eh=e.hp;for(let i=0;i<40;i++){x.update(1/30);e.x=S.p.x+60;e.y=S.p.y;}o.aura=eh-e.hp;
          o.size=S.dS;o.walk1=walk(.5);
          S.p.inv=0;const h1=S.p.hp;x.hitP(100,'');o.dmg1=h1-S.p.hp;
          S.rg=0;const g0=S.rg;S.rgB=2.5;x.hurt(e,5);o.gainOn=S.rg-g0;   // 변신 중엔 게이지가 더 차지 않는다
          let t=0;while(S.dT>0&&t<20*30){x.update(1/30);t++;}o.dur=t/30;
          for(let i=0;i<60;i++)x.update(1/30);o.after={rg:S.rg,dT:S.dT,dS:S.dS};
          return o}""")
        check('가득 차면 변신 시작(지속 약 11초)', r['on'] > 10 and r['dN'] == 1, (r['on'], r['dN']))
        check('변신 중 몸이 커진다(1.0 → 1.4 이상)', r['size'] > 1.4, r['size'])
        check('변신 중 이동속도 증가(+20% 안팎)', 1.12 < r['walk1'] / r['walk0'] < 1.3, (r['walk0'], r['walk1']))
        check('화염 오라가 곁의 적에게 지속 피해', r['aura'] > 20, r['aura'])
        check('받는 피해 -30%', abs(r['dmg1'] / r['dmg0'] - .7) < .02, (r['dmg0'], r['dmg1']))
        check('변신 중엔 게이지가 오르지 않는다', r['gainOn'] == 0, r['gainOn'])
        check('지속시간 뒤 변신이 꺼지고 게이지 0 · 크기 원상', 9.0 < r['dur'] < 9.6 and r['after']['rg'] < 5 and r['after']['dT'] <= 0 and r['after']['dS'] < 1.05, (r['dur'], r['after']))
        # ── 3. 쌍둥이 이빨 Lv1~8 · 각성 · 마스터 · 변신 중/평상시 — 예외 없음 · 피해를 낸다
        r = await pg.evaluate("""()=>{const x=__p6x,o={};const res={};
          for(const ev of [0,1])for(const drg of [0,1])for(let L=1;L<=8;L++){
            x.CH_set('psg');x.start();const S=x.S;S.w.twin=L;if(ev)S.ev.twin=1;S.tier.twin=5;x.tkCalc();S.p.hp=S.p.mhp=1e9;S.dmgBy={};
            if(drg){S.rg=100;}
            for(let i=0;i<40;i++){const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.x=S.p.x+60+(i%8)*18;e.y=S.p.y+((i/8|0)-2)*30;e.sp=0;}
            let ok=true;try{for(let i=0;i<30*8;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}S.p.hp=S.p.mhp;x.update(1/30);if(i%3==0)x.draw();}}catch(er){ok=String(er);}
            res[ev+'_'+drg+'_'+L]={ok,dmg:S.dmgBy.twin||0,drg:S.dT>0||S.dN>0};}
          return res}""")
        bad = {k: v for k, v in r.items() if v['ok'] is not True}
        check('쌍둥이 이빨 Lv1~8 × 각성 유무 × 변신 유무 예외 없음', not bad, bad)
        check('모든 조합에서 쌍둥이 이빨이 피해를 낸다', all(v['dmg'] > 0 for v in r.values()), [k for k, v in r.items() if v['dmg'] <= 0])
        check('변신 조합은 실제로 변신했다', all(v['drg'] for k, v in r.items() if k.split('_')[1] == '1'))
        check('콘솔·페이지 에러 0', not errs, errs[:3])
        await b.close()
    print(f'\n{N[0]-len(FAILS)}/{N[0]} 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
