# -*- coding: utf-8 -*-
"""📸 신규 보스 배고배고(bgb) + 플레이어블 검증 (2026-10-07 사장님 지시).  사용: python3 tests/survivors_bgb_test.py
① 38분(2280초)에 등장 → '플레이브 한번 잡숴봐' 외침·예고(0.8초) → 카드 부채꼴이 날아가 맞으면 피해 / 레인 사이에 서 있으면 안 맞는다
② 처치하면 해금 목록(로컬)에 bgb ③ 해금된 계정에서 bgb 선택 · 시작 무기 pcards · Lv8 에러 없음 · 피해 · 넉백
④ 기존 보스(BOSS_ROT·MINI_ROT) 출현 시각·순서가 main 과 같다(스냅샷 비교) ⑤ 콘솔 에러 0
임시 사본은 survivors_bgb_x.html(추적 안 함) — 끝나면 지운다."""
import asyncio, sys, os, subprocess, shutil, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' — ' + str(x)[:300]) if x != '' else ''), flush=True)
    if not c: FAILS.append(n)

# 보스 출현 기록 — 새로 나온 보스를 (키, 시각)으로 적고 바로 치운다(살아 있는 보스가 미니 보스를 막는 영향을 없애 순서가 결정적이 된다)
TRACE = r"""(a)=>{const x=__p6x;x.srvUnl([]);x.CH_set('brj');x.start();const S=x.S,out=[];let last=0;const dt=a.dt;
 while(S.t<a.until){ if(x.state==='lvup'){x.pick(x.CUR[0]);continue} if(x.state!=='play'){x.resume();continue}
   S.p.mhp=S.p.hp=1e9;S.p.inv=9;x.update(dt);
   for(const e of x.enemies.a)if(e.on&&e.boss&&e.sn>last){last=Math.max(last,e.sn);out.push([e.boss,Math.round(S.t)]);e.on=false;if(S.bossRef===e)S.bossRef=null;}
   if(x.state==='result')break; }
 return out}"""

async def main():
    # 기준선 = origin/main 의 survivors.html (보스 표를 건드리지 않았는지 비교)
    base = tempfile.mkdtemp(prefix='svbase_')
    src = subprocess.run(['git', 'show', 'origin/main:survivors.html'], cwd=H.ROOT, capture_output=True).stdout
    open(os.path.join(base, 'survivors.html'), 'wb').write(src)
    os.symlink(os.path.join(H.ROOT, 'img'), os.path.join(base, 'img'))
    for f in os.listdir(H.ROOT):
        if f.endswith('.js') or f.endswith('.json') or f.endswith('.css'):
            try: os.symlink(os.path.join(H.ROOT, f), os.path.join(base, f))
            except Exception: pass
    H.make_copy('survivors.html', 'survivors_bgb_x.html'); srv = H.Srv()
    H.make_copy('survivors.html', 'survivors_x.html', root=base); srv0 = H.Srv(root=base)
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await H.new_page(b, srv.port, page='survivors_bgb_x.html')
        # ── 0. 데이터
        r = await pg.evaluate("""()=>{const x=__p6x,c=x.CHARS.find(c=>c.k==='bgb'),w=x.WEAP.pcards;
          return {c:c&&{boss:c.boss,w:c.w,spd:c.spd,mag:c.mag,un:c.un.t},w:w&&{only:w.only,ds:w.ds.length,ev:w.ev.nm,pair:w.pair},T:x.TIERS.pcards&&x.TIERS.pcards.length,syn:x.SYN.find(s=>s.k==='u_pcards')}}""")
        check('CHARS bgb(보스 캐릭터)·WEAP pcards(only bgb · 8줄 · 각성 · 짝)·TIERS 5단계·콤보', r['c'] and r['c']['boss'] and r['c']['w'] == 'pcards' and r['w']['only'] == 'bgb' and r['w']['ds'] == 8 and r['w']['ev'] == '팬싸인회' and r['T'] == 5 and r['syn'] and r['syn']['req'] == ['pcards', 'spk'], r)
        check('해금 문구가 보스 처치', '처치' in r['c']['un'], r['c']['un'])
        # ── ① 보스 등장 · 예고 · 카드
        r = await pg.evaluate("""()=>{const x=__p6x;x.srvUnl([]);x.CH_set('brj');x.start();const S=x.S;const o={};
          for(const e of x.enemies.a)e.on=false;S.nextBoss=1e9;S.nextMini=1e9;S.t=2279;
          let fired=0;for(let i=0;i<60&&!fired;i++){x.update(1/30);for(const e of x.enemies.a)if(e.on&&e.boss==='bgb')fired=e;}
          o.t=+S.t.toFixed(2);o.found=!!fired;if(!fired)return o;const e=fired;o.hp=Math.round(e.mhp);o.name=e.b.nm;o.mult=x.bossMul(x.MIN());o.base=e.b.hp;o.dmg=+e.dmg.toFixed(1);
          o.sr={hp:Math.round(1100*o.mult),ddo:Math.round(1300*o.mult),tw:Math.round(1500*o.mult)};
          return o}""")
        check('2280초(38:00)에 배고배고 등장', r['found'] and 2279.9 <= r['t'] <= 2281, r)
        print('   체력/공격', r.get('hp'), r.get('dmg'), '신림 기준', r.get('sr'), 'base', r.get('base'), 'mult', r.get('mult'))
        LANE = r"""(a)=>{const x=__p6x;x.srvUnl([]);x.CH_set('brj');x.start();const S=x.S,p=S.p;const o={};
          for(const e of x.enemies.a)e.on=false;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=0;
          x.update(1/30);let e=null;for(const q of x.enemies.a)if(q.on&&q.boss==='bgb')e=q;if(!e)return {err:'no boss'};
          for(const q of x.enemies.a)if(q.on&&q!==e)q.on=false;
          p.x=0;p.y=0;e.x=-300;e.y=0;e.sp=0;e.at.pull=99;e.at.cards=0;e.hp=e.mhp=1e9;p.hp=p.mhp=500;p.inv=0;x.keys={};p.moving=false;
          // 예고 전: 플레이어를 레인 위(a.lane=true) 또는 레인 사이에 세운다 — 보스는 (-300,0)에서 +x 쪽으로 쏜다. 카드 5장 · 간격 .26rad
          x.update(1/30);o.cardW=!!S.cardW;o.txt=x.texts.a.some(t=>t.on&&String(t.s).includes('플레이브 한번 잡숴봐'));o.n=S.cardW&&S.cardW.n;o.T=S.cardW&&S.cardW.T;
          const ang=S.cardW?S.cardW.a:0;const off=a.lane?0:.13;const dist=300;   // 보스 기준 각도(0 = 한가운데 레인 · .13 = 레인 사이)
          p.x=e.x+Math.cos(ang+off)*dist;p.y=e.y+Math.sin(ang+off)*dist;
          let t=0,cards=0,fireT=-1;const hp0=p.hp;
          for(let i=0;i<150;i++){p.x=e.x+Math.cos(ang+off)*dist;p.y=e.y+Math.sin(ang+off)*dist;p.hp=Math.min(p.mhp,p.hp);x.update(1/30);t+=1/30;
            let c=0;for(const b of x.eshots.a)if(b.on&&b.k===3)c++;if(c>cards)cards=c;if(c&&fireT<0)fireT=t;S.p.inv=0;}
          o.fireT=+fireT.toFixed(2);o.cards=cards;o.lost=Math.round(hp0-p.hp);o.dmgOne=+(e.dmg*.55).toFixed(1);return o}"""
        r1 = await pg.evaluate(LANE, {'lane': True})
        check('외침 말풍선("플레이브 한번 잡숴봐!!") + 예고 0.8초', r1.get('cardW') and r1.get('txt') and abs(r1.get('T', 0) - .8) < .01 and .7 <= r1.get('fireT', 0) <= 1.0, r1)
        check('카드가 부채꼴로 날아감(5장) · 맞으면 피해', r1.get('cards') == 5 and r1.get('lost', 0) > 0, r1)
        r2 = await pg.evaluate(LANE, {'lane': False})
        check('레인 사이에 서 있으면 피할 수 있다(피해 0)', r2.get('cards') == 5 and r2.get('lost') == 0, r2)
        # 페이즈: 체력이 낮으면 카드 수 증가
        r = await pg.evaluate("""()=>{const x=__p6x;x.srvUnl([]);x.CH_set('brj');x.start();const S=x.S,p=S.p;for(const e of x.enemies.a)e.on=false;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=0;x.update(1/30);
          let e=null;for(const q of x.enemies.a)if(q.on&&q.boss==='bgb')e=q;const out=[];
          for(const f of [1,.6,.3]){S.cardW=null;e.at.cards=0;e.at.pull=99;e.hp=e.mhp*f;e.x=-300;e.y=0;p.x=0;p.y=0;p.hp=p.mhp;for(let i=0;i<3;i++){x.update(1/30);}out.push(S.cardW?S.cardW.n:-1);}
          return out}""")
        check('체력이 낮아지면 카드 수 증가(5→7→9)', r == [5, 7, 9], r)
        # ── ② 처치 → 해금(로컬)
        r = await pg.evaluate("""()=>{const x=__p6x;try{localStorage.clear()}catch(e){}x.srvUnl([]);x.CH_set('brj');x.start();const S=x.S;for(const e of x.enemies.a)e.on=false;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=0;x.update(1/30);
          let e=null;for(const q of x.enemies.a)if(q.on&&q.boss==='bgb')e=q;const c=x.CHARS.find(c=>c.k==='bgb'),pg0=x.getProg();const before=x.canPick(c,pg0);
          x.hurt(e,1e12);for(let i=0;i<5;i++)x.update(1/30);
          const pg1=x.getProg();return {before,after:x.canPick(c,pg1),bk:!!pg1.bk.bgb,unl:JSON.parse(localStorage.getItem('p6_unl_v1')||'[]'),newU:S.newU,alive:!!e.on}}""")
        check('처치하면 bgb 해금(로컬 진행 + 해금 목록 + 이번 판 새 해금)', (not r['before']) and r['after'] and r['bk'] and 'bgb' in r['unl'] and 'bgb' in r['newU'], r)
        # ── ③ 플레이어블
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('bgb');x.start();const S=x.S,p=S.p;return {ch:x.CH.k,w:Object.assign({},S.w),spd:x.CH.spd}}""")
        check('해금된 계정에서 bgb 선택 · 시작 무기 pcards Lv1', r['ch'] == 'bgb' and r['w'] == {'pcards': 1}, r)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('bgb');x.start();const S=x.S,p=S.p;S.p.hp=S.p.mhp;for(const e of x.enemies.a)e.on=false;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=1e9;S.t=60;
          const es=[];for(let i=0;i<3;i++){const e=x.spawnEnemy(0,1,null,{x:p.x+90+i*14,y:p.y+(i-1)*14});e.sp=0;e.hp=e.mhp=1e6;es.push(e);}
          const x0=es.map(e=>e.x);S.cd.pcards=0;let kb=0,hurtN=0;
          for(let i=0;i<40;i++){S.p.hp=S.p.mhp;x.update(1/30);for(const e of es)if(e.kb>0)kb++;}
          const moved=es.map((e,i)=>e.x-x0[i]);return {kb,moved:moved.map(v=>Math.round(v)),dmg:Math.round(S.dmgBy.pcards||0)}}""")
        check('pcards: 적에게 피해 + 넉백(밀려남)', r['dmg'] > 0 and r['kb'] > 0 and max(r['moved']) > 5, r)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('bgb');x.start();const S=x.S,out=[];S.t=90;
          for(let L=1;L<=8;L++){S.w.pcards=L;S.cd.pcards=0;S.dmgBy={};
            for(let i=0;i<300;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue}if(x.state!=='play'){x.resume();continue}S.p.hp=S.p.mhp;x.keys={KeyD:true};x.update(1/30);if(i%3==0)x.draw();}
            out.push(Math.round(S.dmgBy.pcards||0));}
          S.w.pcards=8;S.ev.pcards=1;S.tier={pcards:5};x.tkCalc();S.dmgBy={};S.cd.pcards=0;for(let i=0;i<400;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue}if(x.state!=='play'){x.resume();continue}S.p.hp=S.p.mhp;x.update(1/30);if(i%3==0)x.draw();}
          out.push(Math.round(S.dmgBy.pcards||0));return out}""")
        check('Lv1~8 + 각성·마스터 5단계 — 에러 없이 모두 피해', len(r) == 9 and all(v > 0 for v in r), r)
        # 콤보
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('bgb');x.start();const S=x.S;S.w.spk=1;x.synCalc();const a=S.synOn.includes('u_pcards'),f=Object.assign({},S.syn);S.w.spk=0;delete S.w.spk;x.synCalc();return {a,f,off:!S.synOn.includes('u_pcards')}}""")
        check('콤보 u_pcards(pcards+spk) 발동·해제', r['a'] and r['off'] and abs(r['f']['dmg'] - .06) < 1e-9, r)
        # 보스 + 40분대 수치로도 에러 없이(무기 전 단계 × 보스 앞에서)
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('bgb');x.start();const S=x.S;S.t=2270;S.w.pcards=8;let n=0;for(let i=0;i<2400;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue}if(x.state!=='play'){x.resume();continue}S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];x.update(1/30);if(i%3==0)x.draw();n++}
          return {n,boss:x.enemies.a.some(e=>e.on&&e.boss==='bgb')}}""")
        check('bgb 로 38분 보스전 80초 에러 없음(그림 포함)', r['n'] > 2000, r)
        check('페이지 오류·콘솔 에러 없음', not errs, errs[:5])
        # ── ④ 기존 보스 스냅샷
        r_new = await pg.evaluate(TRACE, {'dt': .25, 'until': 3400})
        ctx0, pg0, errs0 = await H.new_page(b, srv0.port)
        r_old = await pg0.evaluate(TRACE, {'dt': .25, 'until': 3400})
        new_wo = [v for v in r_new if v[0] != 'bgb']
        check('기존 보스·미니 보스 출현 순서·시각이 main 과 같다', new_wo == r_old and len(r_old) >= 20, {'old': r_old if new_wo != r_old else len(r_old), 'diff': [(a, b) for a, b in zip(new_wo, r_old) if a != b][:4]})
        bg = [v for v in r_new if v[0] == 'bgb']
        check('배고배고는 2280초에 한 번만', len(bg) == 1 and bg[0][1] == 2280, bg)
        print('   출현표(새):', r_new)
        check('콘솔 에러 없음(두 페이지)', not errs and not errs0, (errs + errs0)[:5])
        await b.close()
    srv.close(); srv0.close()
    for f in ('survivors_bgb_x.html',):
        try: os.remove(os.path.join(H.ROOT, f))
        except Exception: pass
    shutil.rmtree(base, ignore_errors=True)
    print('\n실패 %d: %s' % (len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
