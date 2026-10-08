# -*- coding: utf-8 -*-
"""📸 신규 보스 배고배고(bgb) + 플레이어블 검증 (2026-10-07 사장님 지시).  사용: python3 tests/survivors_bgb_test.py
① 38분(2280초)에 등장 → '플레이브 한번 잡숴봐' 외침·예고(0.8초) → 카드 부채꼴이 날아가 맞으면 피해 / 레인 사이에 서 있으면 안 맞는다
② 처치하면 해금 목록(로컬)에 bgb ③ 해금된 계정에서 bgb 선택 · 시작 무기 pcards · Lv8 에러 없음 · 피해 · 넉백
④ 기존 보스(BOSS_ROT·MINI_ROT) 출현 시각·순서가 main 과 같다(스냅샷 비교) ⑤ 콘솔 에러 0
⑥ ⭐ 시그니처 유물 「한 장씩 줄게」(sg_bgb) — 데이터·후보 노출·N번째 던지기에 카드 고리·귀속(rel)·보스·상한·재시작·시드 불변·전부 끼우고 전투
임시 사본은 survivors_bgb_x.html(추적 안 함) — 끝나면 지운다."""
import asyncio, sys, os, subprocess, shutil, tempfile, json, math
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
        r_old = [v for v in r_old if v[0] != 'bgb']   # 기준선(origin/main)에 이미 배고배고가 들어 있어도 비교는 '기존 보스'끼리만
        check('기존 보스·미니 보스 출현 순서·시각이 main 과 같다', new_wo == r_old and len(r_old) >= 20, {'old': r_old if new_wo != r_old else len(r_old), 'diff': [(a, b) for a, b in zip(new_wo, r_old) if a != b][:4]})
        bg = [v for v in r_new if v[0] == 'bgb']
        check('배고배고는 2280초에 한 번만', len(bg) == 1 and bg[0][1] == 2280, bg)
        print('   출현표(새):', r_new)
        check('콘솔 에러 없음(두 페이지)', not errs and not errs0, (errs + errs0)[:5])

        # ── ⑥ ⭐ 시그니처 유물 「한 장씩 줄게」 — 포토카드를 N번 던질 때마다, 적이 가까이 있으면 카드 8/12/16장을 사방으로(고리)
        ctx6, pg6, errs6 = await H.new_page(b, srv.port, page='survivors_bgb_x.html')
        SETUP6 = r"""(a)=>{const x=__p6x;x.srvUnl([]);x.CH_set('bgb');x.start();const S=x.S,p=S.p;
          S.t=a.t||600;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=1e9;S.spawnT=-1e9;S.evT=1e9;S.bigT=1e9;S.w.pcards=8;S.cd.pcards=a.cd===undefined?99:a.cd;p.hp=p.mhp=1e9;p.inv=99;x.keys={};
          for(const e of x.enemies.a)e.on=false;if(a.L)S.rel.sg_bgb=a.L;S.live.length=0;return true}"""
        r = await pg6.evaluate("""()=>{const x=__p6x,R=x.REL.sg_bgb;return {ch:R.ch,ic:R.ic,nm:R.nm,ds:[1,2,3].map(l=>R.ds(l)),non:x.CHARS.filter(c=>!c.shop).map(c=>c.k),rel:Object.keys(x.REL).filter(k=>x.REL[k].ch).map(k=>x.REL[k].ch),
          icons:x.CHARS.filter(c=>!c.shop).every(c=>x.REL['sg_'+c.k]&&x.REL['sg_'+c.k].ic===c.e)}}""")
        check('⑥ REL.sg_bgb: ch bgb · 이름 「한 장씩 줄게」 · 아이콘 = 캐릭터 이모지 🌪', r['ch'] == 'bgb' and r['nm'] == '한 장씩 줄게' and r['ic'] == '🌪' and r['icons'], r)
        check('⑥ ds 3줄: 던진 횟수 7/6/5 · 카드 8/12/16장 · 사방', all((['7번', '6번', '5번'][i] in r['ds'][i]) and (['8장', '12장', '16장'][i] in r['ds'][i]) and '사방' in r['ds'][i] and '포토카드' in r['ds'][i] for i in range(3)), r['ds'])
        check('⑥ 상점 캐릭터를 뺀 캐릭터 15종 = 시그니처 유물 15종', len(r['non']) == 15 and len(r['rel']) == 15 and set(r['non']) == set(r['rel']), (len(r['non']), len(r['rel'])))
        r = await pg6.evaluate("""()=>{const x=__p6x;x.CH_set('bgb');x.start();const S=x.S;S.lv=40;let own=0,other=0,ty='';
          for(let i=0;i<400;i++)for(const o of x.offers(3))if(o.t==='rl'&&x.REL[o.r].ch){if(x.REL[o.r].ch==='bgb'){own++;ty=x.cardOf(o).ty;}else other++;}
          S.lv=10;let early=0;for(let i=0;i<200;i++)for(const o of x.offers(3))if(o.t==='rl'&&x.REL[o.r].ch)early++;
          S.lv=40;S.rel.sg_bgb=3;let l3=0;for(let i=0;i<300;i++)for(const o of x.offers(3))if(o.k==='rl:sg_bgb')l3++;
          S.rel.sg_bgb=1;let up=null;for(let i=0;i<300&&!up;i++)for(const o of x.offers(3))if(o.k==='rl:sg_bgb')up=o;
          const c=up&&x.cardOf(up);if(up)x.applyUp(up);
          x.CH_set('brj');x.start();x.S.lv=40;let leak=0;for(let i=0;i<600;i++)for(const o of x.offers(3))if(o.k==='rl:sg_bgb')leak++;
          return {own,other,ty,early,l3,lv2:S.rel.sg_bgb,cardTy:c&&c.ty,leak}}""")
        check('⑥ bgb Lv40: 자기 시그니처만 후보(타 캐릭터 0) · 카드 라벨에 시그니처 · Lv24 전엔 안 나옴', r['own'] > 0 and r['other'] == 0 and '시그니처' in r['ty'] and r['early'] == 0, r)
        check('⑥ 3단계면 더 안 나옴 · 강화 카드 1→2 · 브장신은 600번 뽑아도 못 봄', r['l3'] == 0 and r['lv2'] == 2 and '강화' in (r['cardTy'] or '') and r['leak'] == 0, r)
        for L in (1, 2, 3):
            await pg6.evaluate(SETUP6, {'L': L, 'cd': 0})
            r = await pg6.evaluate("""(L)=>{const x=__p6x,S=x.S,p=S.p;const N=[7,6,5][L-1];
              const e=x.spawnEnemy(1,1);e.sp=0;e.hp=e.mhp=1e12;
              let vol=0,prev=S.cd.pcards;const ev=[],lines=[];let sample=null;
              for(let i=0;i<30*40&&vol<2*N+2;i++){e.x=p.x+100;e.y=p.y;e.kb=0;e.hp=e.mhp;S.spawnT=-1e9;
                x.update(1/30);const v=S.cd.pcards>prev+.5;prev=S.cd.pcards;
                if(v){vol++;const ring=S.x3.f.filter(o=>o.k==='pc'&&o.rl);ev.push([vol,ring.length]);if(ring.length){const tx=x.texts.a.filter(t=>t.on&&String(t.s).startsWith('📸')).sort((a,b)=>b.life-a.life)[0];lines.push(tx?tx.s:'');}
                  if(ring.length&&!sample){const fan=S.x3.f.filter(o=>o.k==='pc'&&!o.rl);const ang=ring.map(o=>Math.atan2(o.vy,o.vx)).sort((a,b)=>a-b);const df=[];for(let k=1;k<ang.length;k++)df.push(ang[k]-ang[k-1]);
                    sample={n:ring.length,d:ring[0].d,fd:fan.length?fan[0].d:null,pc:ring[0].pc,pop:ring[0].pop,life:ring[0].life,flife:fan.length?fan[0].life:null,sp:Math.hypot(ring[0].vx,ring[0].vy),fsp:fan.length?Math.hypot(fan[0].vx,fan[0].vy):null,
                      stepMin:Math.min(...df),stepMax:Math.max(...df),aimOff:Math.min(...ring.map(o=>Math.abs(Math.atan2(Math.sin(Math.atan2(o.vy,o.vx)),Math.cos(Math.atan2(o.vy,o.vx))))))};}}}
              return {ev,lines,sample,cnt:S.sgT.bgb,fired:S.sgT.bgbN}}""", L)
            n = [8, 12, 16][L - 1]; NN = [7, 6, 5][L - 1]
            rings = [v for v, c in r['ev'] if c > 0]
            check(f'⑥ L{L}: {NN}번째·{2*NN}번째 던지기에 정확히 카드 {n}장 고리(그 사이엔 없음)', rings == [NN, 2 * NN] and all(c == n for v, c in r['ev'] if c > 0), r['ev'])
            s = r['sample']
            check(f'⑥ L{L}: 외침 대사가 돌아가며 나온다(첫 번째는 스킬 대사 · 두 번째는 「한 장씩 줄게!」)', len(r['lines']) >= 2 and '플레이브 한번 잡숴봐!!' in r['lines'][0] and '한 장씩 줄게!' in r['lines'][1], r['lines'])
            check(f'⑥ L{L}: 고리 카드 피해 = 부채꼴 카드와 같음 · 관통 1 · pop 0 · 수명 0.6배 · 속도 같음', s and abs(s['d'] - s['fd']) < 1e-9 and s['pc'] == 1 and s['pop'] == 0 and abs((s['life'] + 1 / 30) / (s['flife'] + 1 / 30) - .6) < 1e-6 and abs(s['sp'] - s['fsp']) < 1e-6, s)
            check(f'⑥ L{L}: 각도 {n}등분 균등 · 조준선에서 반 칸 비켜 시작', s and abs(s['stepMin'] - 2 * math.pi / n) < 1e-4 and abs(s['stepMax'] - 2 * math.pi / n) < 1e-4 and abs(s['aimOff'] - math.pi / n) < 1e-4, s)
        for up in (False, True):
            await pg6.evaluate(SETUP6, {'L': 1, 'cd': 0})
            r = await pg6.evaluate("""(up)=>{const x=__p6x,S=x.S,p=S.p;const e=x.spawnEnemy(1,1);e.sp=0;e.hp=e.mhp=1e12;S.sgT.bgb=5;if(up)S.rel.sg_bgb=2;
              let vol=0,prev=S.cd.pcards,n=0;for(let i=0;i<30*3&&vol<1;i++){e.x=p.x+100;e.y=p.y;e.kb=0;x.update(1/30);if(S.cd.pcards>prev+.5)vol++;prev=S.cd.pcards;n=Math.max(n,S.x3.f.filter(o=>o.rl).length);}
              return {vol,n,cnt:S.sgT.bgb}}""", up)
            check('⑥ ' + ('단계가 오르면(1→2) N 이 바로 6 으로 바뀌고 카운터(5)는 유지 → 다음 던지기에 터진다' if up else '1단계(N=7)에서 카운터 5 + 1 = 6 은 아직 안 터진다'), (r['n'] == 12 and r['cnt'] == 0) if up else (r['n'] == 0 and r['cnt'] == 6), r)
        await pg6.evaluate(SETUP6, {'L': 1, 'cd': 0})
        r = await pg6.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;const e=x.spawnEnemy(1,1);e.sp=0;e.hp=e.mhp=1e12;let vol=0,prev=S.cd.pcards,rings0=0;
          for(let i=0;i<30*16;i++){e.x=p.x+250;e.y=p.y;e.kb=0;x.update(1/30);const v=S.cd.pcards>prev+.5;prev=S.cd.pcards;if(v)vol++;rings0=Math.max(rings0,S.x3.f.filter(o=>o.rl).length);}
          const cnt0=S.sgT.bgb,n0=S.sgT.bgbN||0;let first=-1,rings1=0;
          for(let i=0;i<30*4;i++){e.x=p.x+100;e.y=p.y;e.kb=0;x.update(1/30);const c=S.x3.f.filter(o=>o.rl).length;if(c>0&&first<0)first=i/30;rings1=Math.max(rings1,c);}
          return {vol,rings0,cnt0,n0,first,rings1,cnt1:S.sgT.bgb,N1:S.sgT.bgbN}}""")
        check('⑥ 적이 250px 에 있으면 8+번 던져도 고리 0(카운터만 쌓임) → 100px 로 붙이면 곧바로 터지고 카운터 0', r['vol'] >= 8 and r['rings0'] == 0 and r['cnt0'] >= 8 and r['n0'] == 0 and 0 <= r['first'] <= 1.6 and r['rings1'] == 8 and r['cnt1'] < 3 and r['N1'] == 1, r)
        await pg6.evaluate(SETUP6, {'L': 3, 'cd': 99})
        r = await pg6.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;S.rel.tenth=3;S.hc=0;S.sgC=0;
          const es=[];for(let i=0;i<10;i++){const e=x.spawnEnemy(1,1);e.x=p.x+40+i*3;e.y=p.y+(i%3-1)*8;e.sp=0;e.hp=e.mhp=1e9;es.push(e);}
          S.sgT.bgb=4;const d=x.U3.pcards.d*x.DL3(8)*x.dmgMul(),sp=x.U3.pcards.sp*x.PS();
          S.live.length=0;for(const e of es)S.live.push(e);const inv0=p.inv,pk0=S.invPk;x.sgFan(d,sp,.84,0);const invOk=p.inv===inv0&&S.invPk===pk0;const n=S.x3.f.filter(o=>o.rl).length;
          for(let i=0;i<30;i++){x.update(1/30);for(const e of es){e.sp=0;}S.cd.pcards=99;}
          return {n,rel:S.dmgBy.rel||0,pc:S.dmgBy.pcards||0,hc:S.hc,sgC:S.sgC,inv:invOk}}""")
        check('⑥ 고리 피해는 유물 몫(rel) · 포토카드 몫 안 늘고 · 열 번째 타격(hc)·한 방 장전(sgC) 카운터 불변 · 무적 불변', r['n'] == 16 and r['rel'] > 0 and r['pc'] == 0 and r['hc'] == 0 and r['sgC'] == 0 and r['inv'], r)
        await pg6.evaluate(SETUP6, {'L': 0, 'cd': 0})
        r = await pg6.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;S.rel.tenth=3;S.hc=0;
          const e=x.spawnEnemy(1,1);e.x=p.x+80;e.y=p.y;e.sp=0;e.hp=e.mhp=1e9;e.kr=0;
          for(let i=0;i<20;i++){x.update(1/30);e.sp=0;e.x=p.x+80;}
          return {pc:S.dmgBy.pcards||0,rel:S.dmgBy.rel||0,hc:S.hc}}""")
        check('⑥ 유물 없이: 일반 포토카드는 pcards 몫 · 열 번째 타격 카운트 그대로', r['pc'] > 0 and r['rel'] == 0 and r['hc'] > 0, r)
        await pg6.evaluate(SETUP6, {'L': 3, 'cd': 99})
        r = await pg6.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;const B={key:'t',nm:'t',r:30,sp:0,d:1,hp:1e9,xp:1,atk:[]};const e=x.spawnEnemy(1,1,B);e.x=p.x+60;e.y=p.y;e.sp=0;e.hp=e.mhp=1e9;e.slow=0;
          const m=x.spawnEnemy(1,1);m.x=p.x-70;m.y=p.y;m.sp=0;m.hp=m.mhp=1e9;m.kr=0;
          const x0=e.x,m0=m.x;S.sgT.bgb=4;S.live.length=0;S.live.push(e,m);const d=x.U3.pcards.d*x.DL3(8)*x.dmgMul(),sp=x.U3.pcards.sp*x.PS();x.sgFan(d,sp,.84,0);
          let kbSeen=0;for(let i=0;i<20;i++){x.update(1/30);e.sp=0;m.sp=0;if(m.kb>0)kbSeen++;S.cd.pcards=99;}
          return {bossDx:e.x-x0,hurt:e.mhp-e.hp,boss:!!e.boss,mobPush:m.x-m0,kbSeen}}""")
        check('⑥ 보스: 안 밀리고 피해는 들어간다 · 잡몹은 바깥으로 밀린다', r['boss'] and abs(r['bossDx']) < 1.5 and r['hurt'] > 0 and r['mobPush'] < -3 and r['kbSeen'] > 0, r)
        await pg6.evaluate(SETUP6, {'L': 3, 'cd': 99})
        r = await pg6.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;for(let i=0;i<100;i++)S.x3.f.push({k:'sh',x:9999,y:9999,R:1,life:9,T:9,big:0});S.sgT.bgb=4;const e=x.spawnEnemy(1,1);e.x=p.x+50;e.y=p.y;S.live.push(e);let err=null;try{x.sgFan(1,430,.84,0)}catch(q){err=q.message}
          const full=S.x3.f.length;S.x3.f.length=95;S.sgT.bgb=4;try{x.sgFan(1,430,.84,0)}catch(q){err=q.message}return {full,part:S.x3.f.length,err}}""")
        check('⑥ f3 풀이 가득 차도 예외 없음 · 100 초과 없음(부분 발사)', r['err'] is None and r['full'] == 100 and r['part'] == 100, r)
        r = await pg6.evaluate("""()=>{const x=__p6x;x.start();return {sgT:Object.keys(x.S.sgT).length,rel:Object.keys(x.S.rel).length,pc:x.S.x3.f.length}}""")
        check('⑥ 다시 시작하면 sgT·rel·카드 모두 비어 있다', r == {'sgT': 0, 'rel': 0, 'pc': 0}, r)
        await pg6.evaluate(SETUP6, {'L': 2, 'cd': 0})
        r = await pg6.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;const e=x.spawnEnemy(1,1);e.sp=0;e.hp=e.mhp=1e12;e.x=p.x+100;e.y=p.y;for(let i=0;i<40;i++){e.x=p.x+100;e.y=p.y;x.update(1/30);}
          const o={c0:S.sgT.bgb||0,n0:S.sgT.bgbN||0};x.state='pause';return o}""")
        await pg6.wait_for_timeout(500)
        r2 = await pg6.evaluate("""()=>{const x=__p6x,S=x.S;const o={c:S.sgT.bgb||0,n:S.sgT.bgbN||0,st:x.state};x.state='play';return o}""")
        check('⑥ 일시정지 중엔 카운터·발동 횟수가 그대로', r2['c'] == r['c0'] and r2['n'] == r['n0'] and r2['st'] == 'pause', (r, r2))
        r = await pg6.evaluate("""()=>{const x=__p6x;const run=(L)=>{x.srvUnl([]);x.CH_set('bgb');x.start({daily:true});const S=x.S;if(L){S.rel.sg_bgb=L;S.sgT.bgb=99;}S.need=1e12;S.p.hp=S.p.mhp=1e9;S.p.inv=99;
            const e=x.spawnEnemy(1,1);e.x=S.p.x+80;e.y=S.p.y;e.sp=0;e.hp=e.mhp=1e12;
            for(let i=0;i<90;i++){e.x=S.p.x+80;e.y=S.p.y;x.update(1/30);}
            return {ring:S.sgT.bgbN||0,rn:[x.RN('card'),x.RN('card'),x.RN('card')]}};
          const a=run(0),b=run(3);return {a,b}}""")
        check('⑥ 일일 도전: 유물이 터져도 카드 난수 흐름 같음(시드 불변)', r['a']['rn'] == r['b']['rn'] and r['b']['ring'] >= 1 and r['a']['ring'] == 0, r)
        r = await pg6.evaluate("""()=>{const x=__p6x;x.srvUnl([]);x.CH_set('brj');x.start();const S=x.S;S.rel.sg_bgb=3;S.p.hp=S.p.mhp=1e9;let err=null;try{for(let i=0;i<600;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue}if(x.state!=='play'){x.resume();continue}x.update(1/30);}}catch(q){err=q.message}
          return {err,rings:S.sgT.bgbN||0}}""")
        check('⑥ 포토카드가 없는 판에 유물이 억지로 있어도 무해(발동 0)', r['err'] is None and r['rings'] == 0, r)
        r = await pg6.evaluate("""()=>{const x=__p6x,errs=[];let rings=0,mxf=0;
          for(const L of [1,2,3])for(const boss of [0,1])for(const evm of [0,1]){try{x.srvUnl([]);x.CH_set('bgb');x.start();const S=x.S;
            for(const k in x.REL)if(!x.REL[k].ch)S.rel[k]=3;S.rel.sg_bgb=L;S.w.pcards=8;for(const k of ['wifi','egg','fryer','pan','potion'])S.w[k]=5;
            if(evm){S.ev.pcards=1;S.tier={pcards:5};x.tkCalc();}
            S.t=boss?2262:600;if(!boss){S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=1e9;}
            let bad=0;const dt=1/30;for(let i=0;i<30*30;i++){if(x.state==='result')break;if(x.state==='lvup'){x.pick(x.CUR[i%x.CUR.length]);continue}if(x.state!=='play'){x.resume();continue}
              S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];x.update(dt);if(i%3===0)x.draw();
              mxf=Math.max(mxf,S.x3.f.length);if(S.x3.f.length>100)bad=1;if(!isFinite(S.p.x)||!isFinite(S.p.hp))bad=2;for(const e of x.enemies.a)if(e.on&&(!isFinite(e.x)||!isFinite(e.y)||!isFinite(e.hp))){bad=3;break;}}
            rings+=S.sgT.bgbN||0;if(bad)errs.push('L'+L+(boss?'B':'')+(evm?'E':'')+':bad'+bad);}catch(e){errs.push('L'+L+(boss?'B':'')+(evm?'E':'')+':'+e.message)}}
          return {errs,rings,mxf}}""")
        check('⑥ Lv1~3 × (일반 · 38분 보스전) × (평범 · 각성+마스터5) × 일반 유물 전부 3단계 — 30초씩 예외·NaN 없음 · f3 ≤ 100', r['errs'] == [] and r['rings'] > 0 and r['mxf'] <= 100, r)
        check('⑥ 콘솔·페이지 오류 0', errs6 == [], errs6[:5])
        await ctx6.close()
        await b.close()
    srv.close(); srv0.close()
    for f in ('survivors_bgb_x.html',):
        try: os.remove(os.path.join(H.ROOT, f))
        except Exception: pass
    shutil.rmtree(base, ignore_errors=True)
    print('\n실패 %d: %s' % (len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
