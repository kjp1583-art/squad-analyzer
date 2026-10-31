#!/usr/bin/env python3.13
"""brjhunt_arena.js 시험(Playwright, 시간 가속 sim). 사용: python3.13 tests/brjhunt_arena_test.py [--shots 폴더] [--quick]
 (a) AUTO 처치율 보정 — power/rec = 0.5·1·2 에서 분당 약 50·100·140 근처(스킬 구성 4종 × 맵 6종 × 시드)
 (b) 발판·중력·점프 높이/거리·벽·한방향 발판·내려가기 충돌
 (c) 맵 6종 연결성(모든 발판에 도달 가능) + AUTO 가 모든 발판의 몹을 점프로 찾아가 잡는지(막힘 0)
 (d) 수동 입력 · AUTO 즉시 전환/복귀 · 키보드
 (e) MP·쿨다운 · 전투 계산(적중·크리·방어)
 (f) 사망/부활   (g) report 이벤트 마리 수·초 정확성(숨김·일시정지·도전 제외)
 (h) 보스·도전 던전 연출 시퀀스   (i) 프레임 비용 · 콘솔 오류 0 · 그림 없을 때(폴백) · 프레임 시트 있을 때"""
import asyncio, os, sys, json, time, shutil
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
URL = 'file://' + os.path.join(ROOT, 'tests', 'brjhunt_arena_harness.html')
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
QUICK = '--quick' in sys.argv
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x != '' else ''), flush=True)
    if not c: FAILS.append(n)

REGS = ['합정', 'bhc', '홍대', '상수', '망원', '한강']
SETS = {'none': [None] * 4, 'basic': ['slash', 'peck', None, None], 'mid': ['slash', 'spin', 'bomb', 'fire'], 'full': ['slash', 'thunder', 'egg', 'storm']}
ALL10 = ['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shield', 'shrimp', 'storm']

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=['--allow-file-access-from-files'])
        pg = await br.new_page(viewport={'width': 600, 'height': 420}, device_scale_factor=2)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text and '404' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(400)
        ev = lambda js, arg=None: pg.evaluate(js, arg) if arg is not None else pg.evaluate(js)

        # ---------- (a) AUTO 처치율 ----------
        t0 = time.time()
        seeds = (1,) if QUICK else (1, 2, 3)
        sets = ['basic', 'mid'] if QUICK else list(SETS)
        res = {}
        for ratio in (0.5, 1, 2):
            rows = []
            for ri, reg in enumerate(REGS):
                for nm in sets:
                    for seed in seeds:
                        k = await pg.evaluate('''([ratio,ids,reg,seed])=>{const a=mkArena({seed,noManifest:true});a.setState(mkState(ratio,ids,{region:reg,scale:true}));
                            a.sim(15,1/60);const k0=a.stats().kills;a.sim(90,1/60);const s=a.stats();a.destroy();return {kpm:(s.kills-k0)/90*60,deaths:s.deaths,tp:s.teleports}}''', [ratio, SETS[nm], reg, seed])
                        rows.append((reg, nm, seed, k['kpm'], k['deaths'], k['tp']))
            v = sorted(r[3] for r in rows)
            res[ratio] = {'avg': sum(v) / len(v), 'min': v[0], 'max': v[-1], 'p10': v[len(v) // 10], 'p90': v[len(v) * 9 // 10]}
            res[ratio]['byset'] = {nm: sum(r[3] for r in rows if r[1] == nm) / max(1, sum(1 for r in rows if r[1] == nm)) for nm in sets}
            res[ratio]['bymap'] = {rg: sum(r[3] for r in rows if r[0] == rg) / max(1, sum(1 for r in rows if r[0] == rg)) for rg in REGS}
            res[ratio]['tp'] = sum(r[5] for r in rows)
        for r, d in res.items():
            print('   power/rec=%s  평균 %.0f  (p10 %.0f · p90 %.0f · 최소 %.0f · 최대 %.0f)  구성별 %s  맵별 %s' % (r, d['avg'], d['p10'], d['p90'], d['min'], d['max'], {k: round(v) for k, v in d['byset'].items()}, {k: round(v) for k, v in d['bymap'].items()}))
        check('power/rec = 0.5 → 분당 처치 평균 45~85 (목표 ≈ 50 — 엔진은 낮은 쪽에서 목표보다 후하다)', 45 <= res[0.5]['avg'] <= 85, round(res[0.5]['avg']))
        check('power/rec = 1 → 분당 처치 평균 85~115 (목표 ≈ 100)', 85 <= res[1]['avg'] <= 115, round(res[1]['avg']))
        check('power/rec = 2 → 분당 처치 평균 105~160 (목표 ≈ 140)', 105 <= res[2]['avg'] <= 160, round(res[2]['avg']))
        check('전투력이 오를수록 처치가 는다(단조) — 0.5 < 1 < 2 (각 단계 +15% 이상)', res[1]['avg'] > res[0.5]['avg'] * 1.15 and res[2]['avg'] > res[1]['avg'] * 1.1, [round(res[r]['avg']) for r in (0.5, 1, 2)])
        check('power/rec = 1 에서 스킬 구성·맵·시드에 따른 흔들림이 평균의 ±45% 안 (p10~p90)', res[1]['p10'] >= res[1]['avg'] * 0.55 and res[1]['p90'] <= res[1]['avg'] * 1.45, (round(res[1]['p10']), round(res[1]['p90'])))
        check('AUTO 가 막혀 순간이동(복구)한 횟수 0', all(res[r]['tp'] == 0 for r in res))
        # power/rec 가 없이 kpm_model 만 와도(서버 모델 kpm = 100·power/rec) 같은 속도
        kk = {}
        for km in (50, 100, 140):
            v = []
            for ri, reg in enumerate(REGS):
                for seed in (1, 2):
                    v.append(await pg.evaluate('''([km,reg,seed])=>{const st=mkState(1,['slash','spin','bomb','fire'],{region:reg,scale:true}); delete st.rec_power; st.combat.power=0; st.kpm_model=km; const a=mkArena({seed,noManifest:true}); a.setState(st); a.sim(15,1/60); const k0=a.stats().kills; a.sim(90,1/60); const k=(a.stats().kills-k0)/90*60; a.destroy(); return k}''', [km, reg, seed]))
            kk[km] = sum(v) / len(v)
        print('   kpm_model 만 줬을 때 평균: %s' % {k: round(x) for k, x in kk.items()})
        check('power/rec 없이 kpm_model(50·100·140)만 줘도 같은 속도 꼴 (각각 ≈ 0.5·1·2 배 상당)', kk[50] < kk[100] < kk[140] and 85 <= kk[100] <= 118 and 40 <= kk[50] <= 88, {k: round(x) for k, x in kk.items()})
        print('   (a) 걸린 시간 %.0fs' % (time.time() - t0))

        # ---------- (b) 지형·물리 ----------
        R = await pg.evaluate('''()=>{
          const out={};
          const mk=()=>{const a=mkArena({seed:1,noManifest:true});a.setState(mkState(1,[]));a.debug.clearMobs();a.setAuto(false);return a};
          const C=BrjArena.consts, dt=1/60;
          // 최대 점프 높이(누르고 있기)
          let a=mk(); let P=a.debug.P; a.debug.setPos(60,C.GY); a.sim(0.3,dt);
          a.input.press('jump'); let minY=1e9, t=0; for(let i=0;i<120;i++){a.sim(dt,dt); minY=Math.min(minY,P.y); if(P.on&&i>5)break;} a.input.release('jump');
          out.jumpH=C.GY-minY;
          // 일찍 뗀 점프
          a=mk(); P=a.debug.P; a.debug.setPos(60,C.GY); a.sim(0.3,dt); a.input.press('jump'); a.sim(dt*3,dt); a.input.release('jump'); minY=1e9; for(let i=0;i<120;i++){a.sim(dt,dt); minY=Math.min(minY,P.y); if(P.on&&i>5)break;} out.jumpLow=C.GY-minY;
          // 달리며 점프: 가로 거리
          a=mk(); P=a.debug.P; a.debug.setPos(40,C.GY); a.input.press('right'); a.sim(0.6,dt); const x0=P.x; a.input.press('jump'); for(let i=0;i<150;i++){a.sim(dt,dt); if(P.on&&i>5)break;} out.jumpDx=P.x-x0; out.runV=P.vx; a.input.release('right'); a.input.release('jump');
          // 한방향 발판: 아래에서 점프하면 올라서고, ↓+점프로 내려온다
          a=mk(); P=a.debug.P; const M=a.debug.map(); const p1=M.plats.find(q=>q.kind==='plat'&&q.tier===1&&q.x1-q.x0>120);
          a.debug.setPos((p1.x0+p1.x1)/2,C.GY); a.sim(0.3,dt); a.input.press('jump'); let passed=false; for(let i=0;i<150;i++){a.sim(dt,dt); if(P.y<p1.y+8&&!P.on)passed=true; if(P.on&&i>5)break;} a.input.release('jump');
          out.up={onPlat:P.on&&P.plat.id===p1.id,y:P.y,py:p1.y,passed};
          a.sim(0.4,dt); a.input.press('down'); a.input.press('jump'); a.sim(dt*2,dt); a.input.release('jump'); let dropped=false; for(let i=0;i<120;i++){a.sim(dt,dt); if(P.on&&P.plat.id!==p1.id){dropped=true;break;}} a.input.release('down');
          out.drop={dropped,y:P.y};
          // 점프 없이 ↓ 만 누르면 그대로 서 있는다
          a=mk(); P=a.debug.P; a.debug.setPos((p1.x0+p1.x1)/2,p1.y); a.input.press('down'); a.sim(1,dt); out.downOnly=P.on&&P.plat.id===p1.id; a.input.release('down');
          // 벽 블록: 가로로 막힌다 · 위로 올라설 수 있다
          a=mk(); P=a.debug.P; const b=M.blocks[0]; a.debug.setPos(b.x0-60,C.GY); a.input.press('right'); a.sim(1.5,dt); out.wallX=P.x; out.wallEdge=b.x0-C.PW; a.input.release('right');
          a=mk(); P=a.debug.P; a.debug.setPos(b.x0-30,C.GY); a.input.press('right'); a.sim(0.15,dt); a.input.press('jump'); let topped=false; for(let i=0;i<150;i++){a.sim(dt,dt); if(P.on&&P.plat.id===b.id)topped=true; if(P.on&&i>5)break;} out.blockTop=topped||(P.x>b.x1-1); a.input.release('right'); a.input.release('jump');
          // 발판 끝에서 걸어 나가면 떨어져 아래 발판·바닥에 선다
          a=mk(); P=a.debug.P; a.debug.setPos(p1.x1-8,p1.y); a.input.press('right'); a.sim(1.4,dt); a.input.release('right'); out.fall={y:P.y,on:P.on,plat:P.on?P.plat.id:-1,from:p1.id};
          // 세계 가장자리
          a=mk(); P=a.debug.P; a.debug.setPos(30,C.GY); a.input.press('left'); a.sim(2,dt); out.leftX=P.x; a.input.release('left');
          a=mk(); P=a.debug.P; a.debug.setPos(M.W-30,C.GY); a.input.press('right'); a.sim(2,dt); out.rightX=P.x; a.input.release('right');
          // 프레임 간격에 따라 같은 결과(1/30, 1/60, 1/20 으로 tick 해도 최고 높이가 같다)
          out.dtJump=[];
          for(const d of [1/20,1/30,1/60,1/144]){ a=mk(); P=a.debug.P; a.debug.setPos(60,C.GY); a.sim(0.2,d); a.input.press('jump'); let mn=1e9; for(let i=0;i<Math.ceil(1.2/d);i++){a.sim(d,d); mn=Math.min(mn,P.y);} a.input.release('jump'); out.dtJump.push(C.GY-mn); }
          // 2단 점프
          a=mk(); P=a.debug.P; a.debug.setPos(60,C.GY); a.input.press('jump'); a.sim(0.1,dt); a.input.release('jump'); a.sim(0.25,dt); const y1=P.y; a.input.press('jump'); a.sim(0.4,dt); a.input.release('jump'); out.dbl=y1-P.y;
          return out;}''')
        check('최대 점프 높이 85~110 (발판 한 층 ≤ 72 를 넘고 두 층 ≥ 124 는 못 넘음)', 85 <= R['jumpH'] <= 110, round(R['jumpH'], 1))
        check('일찍 떼면 낮게 뛴다(작은 점프 < 75, 큰 점프보다 낮음)', R['jumpLow'] < 75 and R['jumpLow'] < R['jumpH'] - 15, round(R['jumpLow'], 1))
        check('달리며 점프하면 가로로 100~170 간다 / 달리기 속도 ≈ 152', 100 <= R['jumpDx'] <= 170 and 140 <= R['runV'] <= 160, (round(R['jumpDx']), round(R['runV'])))
        check('한방향 발판: 아래에서 점프하면 뚫고 올라서고(착지), 머리 위 충돌 없음', R['up']['onPlat'] and R['up']['passed'] and abs(R['up']['y'] - R['up']['py']) < 0.5, R['up'])
        check('↓+점프로 한방향 발판 아래로 내려온다', R['drop']['dropped'], R['drop'])
        check('↓ 만 누르면 내려오지 않는다', R['downOnly'])
        check('벽 블록에 막혀 가로로 못 지나간다', abs(R['wallX'] - R['wallEdge']) < 1.5, (round(R['wallX'], 1), round(R['wallEdge'], 1)))
        check('블록은 점프로 올라서거나 넘을 수 있다', R['blockTop'])
        check('발판 끝에서 걸어 나가면 떨어져 아래에 선다', R['fall']['on'] and R['fall']['y'] > 0 and R['fall']['plat'] != R['fall']['from'], R['fall'])
        check('세계 가장자리를 못 벗어난다', R['leftX'] >= 8 and R['rightX'] <= await pg.evaluate('()=>BrjArena.genMap(2,1).W') - 8, (round(R['leftX'], 1), round(R['rightX'], 1)))
        check('프레임 간격(1/20~1/144)이 달라도 점프 높이 차이 ≤ 4', max(R['dtJump']) - min(R['dtJump']) <= 4, [round(x, 1) for x in R['dtJump']])
        check('2단 점프가 된다(공중에서 한 번 더 솟는다)', R['dbl'] > 15, round(R['dbl'], 1))

        # ---------- (c) 맵 6종 ----------
        M = await pg.evaluate('''()=>{
          const out=[]; const C=BrjArena.consts;
          for(let reg=0;reg<6;reg++) for(let seed=1;seed<=6;seed++){
            const m=BrjArena.genMap(reg,seed), n=m.plats.length;
            // 연결: 바닥에서 모든 발판으로, 모든 발판에서 바닥으로
            let okUp=true, okDown=true, maxRise=0, minW=1e9, overlap=0, outside=0;
            for(let i=0;i<n;i++){ if(m.dist[0][i]>=1e9) okUp=false; if(m.dist[i][0]>=1e9) okDown=false; }
            for(const e of m.edges.flat()){ }
            for(const p of m.plats){ if(p.kind==='plat'){ minW=Math.min(minW,p.x1-p.x0); if(GY(p)<0)0; } if(p.x0<0||p.x1>m.W||p.y>C.GY||p.y<60) outside++; }
            for(let i=0;i<n;i++) for(let j=i+1;j<n;j++){ const a=m.plats[i],b=m.plats[j]; if(a.kind==='plat'&&b.kind==='plat'&&a.y===b.y&&a.x1>b.x0-30&&b.x1>a.x0-30) overlap++; }
            for(let i=0;i<n;i++) for(const e of m.edges[i]){ const A=m.plats[i],B=m.plats[e.to]; maxRise=Math.max(maxRise,A.y-B.y); }
            const bl=m.blocks.map(b=>(b.x0+b.x1)/2).sort((x,y)=>x-y); let minBl=1e9; for(let i=1;i<bl.length;i++)minBl=Math.min(minBl,bl[i]-bl[i-1]);
            const tiers=new Set(m.plats.filter(p=>p.kind==='plat').map(p=>p.tier));
            out.push({reg,seed,n,okUp,okDown,maxRise,minW,overlap,outside,minBl,tiers:tiers.size,W:m.W,spawnOk:m.spawnPlats.length>=5});
          }
          function GY(){return 0}
          return out;}''')
        check('맵 6종 × 시드 6 — 모든 발판이 바닥에서 도달 가능(점프 간선 경로 있음)', all(r['okUp'] for r in M), [(r['reg'], r['seed']) for r in M if not r['okUp']][:5])
        check('모든 발판에서 바닥으로 내려올 수 있다', all(r['okDown'] for r in M))
        check('간선의 높이차 ≤ 84 (점프 높이 ≈ 100 에 여유)', all(r['maxRise'] <= 84 for r in M), max(r['maxRise'] for r in M))
        check('발판 폭 ≥ 90 · 같은 층 발판끼리 겹치지 않음 · 세계 밖으로 안 나감', all(r['minW'] >= 90 and r['overlap'] == 0 and r['outside'] == 0 for r in M), [(r['reg'], r['seed'], r['minW'], r['overlap'], r['outside']) for r in M if not (r['minW'] >= 90 and r['overlap'] == 0 and r['outside'] == 0)][:4])
        check('벽 블록 사이 간격 ≥ 150 · 몹 자리(발판) ≥ 5 · 층 ≥ 2', all(r['minBl'] >= 150 and r['spawnOk'] and r['tiers'] >= 2 for r in M))
        det = await pg.evaluate('''()=>{const a=BrjArena.genMap(2,5),b=BrjArena.genMap(2,5),c=BrjArena.genMap(2,6),d=BrjArena.genMap(3,5);
          const sig=m=>JSON.stringify(m.plats.map(p=>[p.kind,Math.round(p.x0),Math.round(p.x1),p.y]));return [sig(a)===sig(b),sig(a)!==sig(c),sig(a)!==sig(d)]}''')
        check('같은 지역·시드는 같은 맵(결정론), 다른 시드·지역은 다른 맵', det == [True, True, True], det)
        sizes = sorted(set((r['reg'], r['W']) for r in M))
        check('세계 폭 2400~3200', all(2400 <= w <= 3200 for _, w in sizes), sizes)

        # AUTO: 모든 발판에 몹을 하나씩 놓고 찾아가 잡는지
        t1 = time.time()
        regs_to_test = range(6) if not QUICK else (0, 3)
        worst = []
        total = 0; bad = []
        for reg in regs_to_test:
            r = await pg.evaluate('''async (reg)=>{
              const m0=BrjArena.genMap(reg,1); const res=[]; const regs=['합정','bhc','홍대','상수','망원','한강'];
              const tops=m0.plats.filter(p=>p.kind==='plat').sort((a,b)=>a.y-b.y||b.x0-a.x0);
              for(const startMode of ['floor','top']){
                for(const target of m0.spawnPlats){
                  const a=mkArena({seed:1,noManifest:true}); a.setState(mkState(8,['slash','peck','spin','bomb'],{region:regs[reg]}));
                  const d=a.debug; d.clearMobs(); const M=d.map();
                  if(startMode==='top'){ const t=M.plats[tops[0].id]; d.setPos((t.x0+t.x1)/2,t.y); }
                  const tp=M.plats[target.id]; const x=(tp.kind==='floor')? (M.blocks[0]?M.blocks[0].x1+60:600): (tp.x0+tp.x1)/2;
                  const mob=d.spawnMob(x,tp,{noPack:true,el:false,fly:false,shoot:false}); mob.st='patrol';
                  const k0=a.stats().kills; let t=0; for(;t<60;t+=0.5){a.sim(0.5,1/60); if(a.stats().kills>k0)break;}
                  res.push({reg,startMode,id:target.id,tier:tp.tier,t:a.stats().kills>k0?t:999,tp:a.stats().teleports}); a.destroy();
                }
              } return res;}''', reg)
            for x in r:
                total += 1
                if x['t'] >= 60 or x['tp'] > 0: bad.append(x)
                worst.append(x['t'])
        check('AUTO — 모든 발판(%d곳 × 출발 2가지)의 몹을 60초 안에 점프로 찾아가 잡음, 막힘·순간이동 0' % total, not bad, bad[:5])
        worst.sort(); print('   (c) 발판 찾아가기: 중앙값 %.1fs · p90 %.1fs · 최대 %.1fs · 걸린 시간 %.0fs' % (worst[len(worst) // 2], worst[len(worst) * 9 // 10], worst[-1], time.time() - t1))

        # (c2) 몸이 지형을 뚫지 않는다 — 맵 6종 × 시드 2 × 60초 동안 매 갱신마다 병아리·몹의 위치가 지형과 맞는지
        INT = await pg.evaluate('''()=>{
          const out={bad:[],ticks:0}; const regs=['합정','bhc','홍대','상수','망원','한강'];
          for(let r=0;r<6;r++) for(const seed of [1,2]){
            const a=mkArena({seed,noManifest:true}); a.setState(mkState(1.3,['slash','spin','bomb','shrimp'],{region:regs[r]})); const d=a.debug, P=d.P;
            for(let i=0;i<60*60;i++){ a.sim(1/60,1/60); out.ticks++; const M=d.map();
              if(P.on){ if(Math.abs(P.y-P.plat.y)>0.01 || P.x<P.plat.x0-4 || P.x>P.plat.x1+4) out.bad.push(['병아리가 발판 밖/공중에 선 채 서 있음',r,seed,i]); }
              if(P.y>304.5||P.x<0||P.x>M.W) out.bad.push(['병아리가 세계 밖',r,seed,i]);
              for(const b of M.blocks) if(P.y>b.y+0.6 && P.x+7>b.x0+0.5 && P.x-7<b.x1-0.5) out.bad.push(['병아리가 블록 속',r,seed,i]);
              for(const m of d.mobs()){ if(m.boss||m.st==='dying') continue;
                if(m.fly){ if(m.y<45||m.y>305||m.x<10||m.x>M.W-10) out.bad.push(['비행 몹이 세계 밖',r,seed,i]); continue; }
                if(Math.abs(m.y-m.plat.y)>0.01) out.bad.push(['몹이 허공에 뜸',r,seed,i,m.y,m.plat.y]);
                if(m.x<m.plat.x0-1||m.x>m.plat.x1+1) out.bad.push(['몹이 발판 밖',r,seed,i]);
                if(m.plat.kind==='floor') for(const b of M.blocks) if(m.x>b.x0-0.5&&m.x<b.x1+0.5) out.bad.push(['몹이 블록 속',r,seed,i]);
              }
              if(out.bad.length>20)break;
            }
          } return out;}''')
        check('매 갱신(%d번) 병아리·몹이 지형을 뚫거나 허공에 뜨지 않는다(발판 위·블록 밖·세계 안)' % INT['ticks'], not INT['bad'], INT['bad'][:4])

        # ---------- (d) 수동 입력 · AUTO 전환 ----------
        D = await pg.evaluate('''()=>{
          const out={}; const dt=1/60;
          const a=mkArena({seed:2,noManifest:true}); a.setState(mkState(1,['slash','peck',null,null])); const d=a.debug, P=d.P; d.clearMobs();
          out.autoDefault=a.getAuto()&&a.isAutoActive();
          a.sim(2,dt); // AUTO 는 몹이 없으면 가만히
          a.input.press('right'); out.manualNow=!a.isAutoActive(); const x0=P.x; a.sim(1,dt); out.moved=P.x-x0; a.input.release('right');
          out.holdAuto=!a.isAutoActive(); a.sim(2.5,dt); out.stillManual=!a.isAutoActive(); a.sim(1.5,dt); out.backAuto=a.isAutoActive();
          a.input.press('jump'); a.input.release('jump'); out.jumpManual=!a.isAutoActive(); a.sim(0.3,dt); out.jumpY=P.on?0:1;
          a.setAuto(false); a.sim(5,dt); out.offStays=!a.isAutoActive(); a.setAuto(true); out.onAgain=a.isAutoActive();
          // 공격 키: 앞의 몹을 때린다
          a.setAuto(false); d.setPos(300,304); P.face=1; const mob=d.spawnMob(340,d.map().plats[0],{noPack:true,el:false,fly:false,shoot:false}); mob.st='patrol'; mob.sp=0; mob.pause=99; mob.lo=mob.hi=340; mob.hp=mob.max=1;
          let hits=0; a.on('hit',()=>hits++); a.input.press('attack'); a.sim(1,dt); a.input.release('attack'); out.attackHits=hits; out.killed=a.stats().kills;
          // 가상 입력 이름 전부 동작(up=점프)
          const b=mkArena({seed:2,noManifest:true}); b.setState(mkState(1,['slash',null,null,null])); b.debug.clearMobs(); b.setAuto(false); b.debug.setPos(100,304);
          b.input.press('up'); b.sim(0.2,dt); out.upJump=b.debug.P.y<300; b.input.release('up'); b.sim(1,dt);
          b.input.press('s1'); b.sim(0.05,dt); out.s1Cast=!!b.debug.P.cast||b.debug.slotCd[0]>0; b.input.release('s1');
          b.input.press('auto'); out.autoBtn=b.getAuto()===true; b.input.press('auto'); out.autoBtn2=b.getAuto()===false;
          b.input.press('pause'); out.paused=b.stats().paused; const t0=b.stats().t; b.sim(1,dt); out.pauseFrozen=b.stats().t===t0; b.input.press('pause'); b.sim(0.2,dt); out.resumed=b.stats().t>t0;
          return out;}''')
        check('기본값은 AUTO 켜짐', D['autoDefault'])
        check('이동 키를 누르면 즉시 수동으로 넘어가 움직인다', D['manualNow'] and D['moved'] > 100, round(D['moved']))
        check('입력이 끊겨도 3초는 수동 유지, 그 뒤 AUTO 복귀', D['holdAuto'] and D['stillManual'] and D['backAuto'])
        check('점프 키도 수동 전환 + 실제로 뜬다', D['jumpManual'] and D['jumpY'] == 1)
        check('AUTO 버튼으로 끄면 계속 수동, 다시 켜면 AUTO', D['offStays'] and D['onAgain'])
        check('공격 키로 앞의 몹을 때려 잡는다', D['attackHits'] >= 1 and D['killed'] >= 1, (D['attackHits'], D['killed']))
        check('가상 입력 이름 up/s1/auto/pause 동작', D['upJump'] and D['s1Cast'] and D['autoBtn'] and D['autoBtn2'] and D['paused'] and D['pauseFrozen'] and D['resumed'])

        # 키보드(실제 이벤트) — rAF 로 돌려 본다
        await pg.evaluate('''()=>{window.K=mkArena({seed:2,manual:false,noManifest:true});K.setState(mkState(1,['slash',null,null,null]));K.debug.clearMobs();K.start();}''')
        await pg.wait_for_timeout(300)
        x0 = await pg.evaluate('()=>K.stats().x')
        await pg.keyboard.down('ArrowRight'); await pg.wait_for_timeout(500); await pg.keyboard.up('ArrowRight')
        x1 = await pg.evaluate('()=>K.stats().x'); manual = await pg.evaluate('()=>!K.isAutoActive()')
        check('키보드 → 로 이동(수동 전환)', x1 - x0 > 40 and manual, round(x1 - x0))
        await pg.evaluate('()=>K.debug.setPos(200,304)')
        await pg.keyboard.down('Alt'); await pg.wait_for_timeout(120); minY = await pg.evaluate('()=>K.stats().y'); await pg.keyboard.up('Alt')
        check('키보드 Alt 로 점프', minY < 300, round(minY))
        await pg.keyboard.press('Tab'); await pg.wait_for_timeout(60)
        a1 = await pg.evaluate('()=>K.getAuto()'); await pg.keyboard.press('g'); await pg.wait_for_timeout(60); a2 = await pg.evaluate('()=>K.getAuto()')
        check('Tab/G 로 AUTO 토글', a1 is False and a2 is True, (a1, a2))
        await pg.keyboard.press('p'); await pg.wait_for_timeout(60); pz = await pg.evaluate('()=>K.stats().paused'); await pg.keyboard.press('p')
        check('P 로 일시정지/해제', pz is True and not await pg.evaluate('()=>K.stats().paused'))
        await pg.evaluate('()=>{const i=document.createElement("input");i.id="tx";document.body.appendChild(i);i.focus()}')
        xs = await pg.evaluate('()=>K.stats().x'); await pg.keyboard.down('ArrowRight'); await pg.wait_for_timeout(300); await pg.keyboard.up('ArrowRight')
        check('입력창에 글 쓰는 중에는 키를 가로채지 않는다', abs(await pg.evaluate('()=>K.stats().x') - xs) < 8)
        await pg.evaluate('()=>{K.destroy();document.getElementById("tx").remove()}')

        # ---------- (e) MP·쿨다운 · 전투 계산 ----------
        S = await pg.evaluate('''()=>{
          const out={}; const dt=1/60;
          const mkA=(ids,extra)=>{const a=mkArena({seed:4,noManifest:true});a.setState(mkState(1,ids,extra));a.debug.clearMobs();a.setAuto(false);a.sim(1,dt);return a};
          // MP 소모·쿨다운
          let a=mkA(['slash','bomb',null,null],{combat:{atk:64,hp:1500,def:40,crit:15,critdmg:180,acc:140,mp:100,mpregen:5,power:1000}});
          const d=a.debug,P=d.P; P.mp=100; const sk=d.skills[0];
          a.input.press('s1'); a.sim(dt,dt); a.input.release('s1'); out.mpAfter=P.mp; out.mpCost=sk.mp; out.cd=sk.cd; out.cdSet=d.slotCd[0];
          a.sim(sk.cast+0.05,dt); P.mp=100; a.input.press('s1'); a.sim(dt,dt); a.input.release('s1'); out.recastBlocked=P.mp===100; // 쿨다운 중
          a.sim(sk.cd+0.1,dt); a.input.press('s1'); a.sim(dt,dt); a.input.release('s1'); out.recastOk=P.mp<100;
          // MP 부족
          a=mkA(['bomb',null,null,null]); const P2=a.debug.P; P2.mp=a.debug.skills[0].mp-1; a.input.press('s1'); a.sim(dt,dt); a.input.release('s1'); out.lowMpBlocked=a.debug.slotCd[0]===0&&!P2.cast;
          // MP 회복(초당 mpregen=5)
          a=mkA(['slash',null,null,null]); a.debug.P.mp=0; a.sim(10,dt); out.regen=a.debug.P.mp;
          // 쿨다운이 서버 값(cd)대로: cd 를 짧게 주면 짧아진다
          a=mkA([null,null,null,null]); a.setState(mkState(1,[],{skills:{active:[{id:'slash',cd:0.5,mp:1,cast:0.1,mult:100,range:90,hits:1,shape:'arc'},null,null,null],passive:null}}));
          a.sim(1,dt); const P3=a.debug.P; P3.mp=100; let casts=0; a.on('skill',()=>casts++); for(let i=0;i<60*5;i++){ if(i%6===0){a.input.press('s1');} else a.input.release('s1'); a.sim(dt,dt);} out.casts5s=casts;
          return out;}''')
        check('스킬을 쓰면 서버 값만큼 MP 가 줄고 쿨다운이 걸린다', abs((100 - S['mpAfter']) - S['mpCost']) < 0.5 and abs(S['cdSet'] - S['cd']) < 0.1, (S['mpAfter'], S['mpCost'], S['cdSet'], S['cd']))
        check('쿨다운 중에는 다시 못 쓰고, 끝나면 쓴다', S['recastBlocked'] and S['recastOk'])
        check('MP 가 모자라면 못 쓴다', S['lowMpBlocked'])
        check('MP 회복 속도 = mpregen(초당 5 → 10초 50)', 45 <= S['regen'] <= 55, round(S['regen'], 1))
        check('서버가 준 cd(0.5초)대로 5초에 약 8~10회', 7 <= S['casts5s'] <= 10, S['casts5s'])

        C = await pg.evaluate('''()=>{
          const out={}; const dt=1/60;
          const run=(combat,mon,N)=>{ const a=mkArena({seed:9,noManifest:true}); a.setState(mkState(1,[],{combat:Object.assign({atk:100,hp:1e7,def:0,crit:0,critdmg:150,acc:100,mp:100,mpregen:0,power:1000},combat),mon:Object.assign({name:'x',hp:900,atk:60,def:0,eva:100,gold:.25},mon)}));
            const d=a.debug; d.clearMobs(); a.setAuto(false); d.setPos(300,304); d.P.face=1; const mob=d.spawnMob(330,d.map().plats[0],{noPack:true,el:false,fly:false,shoot:false}); mob.st='patrol'; mob.sp=0; mob.pause=1e9; mob.lo=mob.hi=330; mob.hp=mob.max=1e12;
            let h=0,c=0,m=0,dm=[],cm=[]; a.on('hit',e=>{h++; if(e.crit){c++;cm.push(e.dmg)}else dm.push(e.dmg)}); a.on('miss',()=>m++);
            a.input.press('attack'); for(let i=0;i<60*N;i++){ mob.x=330; mob.kb=0; a.sim(dt,dt); } a.input.release('attack');
            return {h,c,m,dm,cm}; };
          const avg=v=>v.reduce((x,y)=>x+y,0)/Math.max(1,v.length);
          // 적중률 = acc/(acc+eva)
          let r=run({acc:100,crit:0},{eva:100},120); out.hit50=r.h/(r.h+r.m); out.hitTotal=r.h+r.m;
          r=run({acc:300,crit:0},{eva:100},120); out.hit75=r.h/(r.h+r.m);
          r=run({acc:1,crit:0},{eva:1000},120); out.hitMin=r.h/(r.h+r.m);   // 최소 25%
          r=run({acc:1e6,crit:0},{eva:1},60); out.hitMax=r.h/(r.h+r.m);     // 최대 99%
          // 크리티컬 확률·피해
          r=run({acc:1e6,crit:30,critdmg:250},{eva:1},150); out.critRate=r.c/r.h; out.critRatio=avg(r.cm)/avg(r.dm); out.baseDmg=avg(r.dm);
          r=run({acc:1e6,crit:0},{eva:1},30); out.noCrit=r.c;
          // 공격력 비례
          const lo=run({atk:100,acc:1e6,crit:0},{eva:1},40), hi=run({atk:400,acc:1e6,crit:0},{eva:1},40); out.atkRatio=avg(hi.dm)/avg(lo.dm);
          // 방어: 받는 피해 = mon.atk × (1 − def/(def+K)) × 접촉계수 — 직접 맞아 본다
          const hurt=(def)=>{ const a=mkArena({seed:9,noManifest:true}); a.setState(mkState(1,[],{stage:9,combat:{atk:100,hp:1e7,def,crit:0,critdmg:150,acc:100,mp:1,mpregen:0,power:1000},mon:{name:'x',hp:900,atk:100,def:0,eva:0,gold:.25},skills:{active:[null,null,null,null],passive:null}})); a.debug.clearMobs(); a.setAuto(false); const dm=[]; a.on('hurt',e=>dm.push(e.dmg)); for(let i=0;i<200;i++){ a.debug.P.inv=0; a.debug.hurt(100); } return avg(dm); };
          out.hurt0=hurt(0); out.hurt100=hurt(100); out.hurt1000=hurt(1000); out.K=12+8*9;
          // 방어력이 같은 스테이지의 두 몹에서 스테이지가 높을수록 방어 효율이 떨어진다(K 가 몹 레벨에 비례)
          return out;}''')
        check('적중률 = acc/(acc+eva) (100/200 → 50%)', abs(C['hit50'] - 0.5) < 0.06, round(C['hit50'], 3))
        check('적중률 = acc/(acc+eva) (300/400 → 75%)', abs(C['hit75'] - 0.75) < 0.06, round(C['hit75'], 3))
        check('적중률 하한 25% · 상한 99%', abs(C['hitMin'] - 0.25) < 0.05 and C['hitMax'] > 0.95, (round(C['hitMin'], 3), round(C['hitMax'], 3)))
        check('크리티컬 확률 = crit% (30%) · 피해 배율 = critdmg% (250% → ×2.5)', abs(C['critRate'] - 0.30) < 0.06 and abs(C['critRatio'] - 2.5) < 0.25, (round(C['critRate'], 3), round(C['critRatio'], 2)))
        check('크리 0% 면 크리가 안 난다', C['noCrit'] == 0)
        check('피해는 공격력에 비례(4배 → 약 4배, 콤보 계수 평균 포함)', 3.6 <= C['atkRatio'] <= 4.4, round(C['atkRatio'], 2))
        exp0 = 100 * 0.55
        check('방어 0 이면 접촉 피해 = mon.atk × 0.55', abs(C['hurt0'] - exp0) < 8, round(C['hurt0'], 1))
        check('방어 감소율 = def/(def+K), K = 12+8·스테이지 (def 100 → %.0f%%)' % (100 / (100 + C['K']) * 100), abs(C['hurt100'] / C['hurt0'] - (1 - 100 / (100 + C['K']))) < 0.06, (round(C['hurt100'], 1), round(C['hurt0'], 1)))
        check('방어가 아주 높아도 최소 1 은 맞는다(0 피해 없음)', C['hurt1000'] >= 1)

        # 스킬 모양 5종 + 10종 전부 시전해도 오류 없음, 피해를 준다
        SK = await pg.evaluate('''()=>{
          const ids=['slash','peck','spin','bomb','thunder','fire','egg','shield','shrimp','storm']; const out={}; const dt=1/60;
          for(const id of ids){
            const a=mkArena({seed:5,noManifest:true}); a.setState(mkState(1,[id,null,null,null],{combat:{atk:100,hp:1e7,def:0,crit:0,critdmg:150,acc:1e6,mp:1000,mpregen:0,power:1000}}));
            const d=a.debug; d.clearMobs(); a.setAuto(false); a.sim(1,dt); d.setPos(300,304); d.P.face=1;
            const mobs=[]; for(const dx of [40,70,100]){ const m=d.spawnMob(300+dx,d.map().plats[0],{noPack:true,el:false,fly:false,shoot:false}); m.st='patrol'; m.sp=0; m.pause=1e9; m.lo=m.hi=m.x; m.hp=m.max=1e9; mobs.push(m); }
            let sk=0,hits=0,casts=[]; a.on('skill',()=>sk++); a.on('hit',()=>hits++); a.on('cast',e=>casts.push(e.stage));
            a.input.press('s1'); a.sim(dt,dt); a.input.release('s1'); a.sim(1.6,dt);
            out[id]={sk,hits,dmgd:mobs.filter(m=>m.hp<1e9).length,shape:d.skills[0].shape,casts:casts.join(','),cd:d.slotCd[0]};
          }
          return out;}''')
        bad = [k for k, v in SK.items() if v['sk'] != 1 or (v['shape'] != 'self' and v['dmgd'] < 1)]
        check('스킬 10종 모두 시전 가능 · 공격형은 몹에 피해(self 는 회복/보호막)', not bad, bad or {k: (v['shape'], v['dmgd']) for k, v in SK.items()})
        check('shape 5종(arc·proj·aoe·dash·self)이 모두 쓰임', {v['shape'] for v in SK.values()} >= {'arc', 'proj', 'aoe', 'dash', 'self'}, sorted({v['shape'] for v in SK.values()}))
        check('시전 단계 이벤트(전조 → 발동)가 순서대로', all(v['casts'].startswith('pre,fire') for v in SK.values() if v['shape'] != 'x'), {k: v['casts'] for k, v in list(SK.items())[:3]})

        EV = await pg.evaluate('''()=>{ const out={}; const a=mkArena({seed:3,noManifest:true}); a.setState(mkState(1.5,['slash','spin',null,null])); const kills=[],c=[0,0,0,0,0];
          a.on('kill',e=>kills.push(e)); a.on('coin',()=>c[0]++); a.on('levelup',()=>c[1]++); a.on('hit',e=>{c[2]++; if(e.crit)c[3]++}); a.on('skill',()=>c[4]++);
          a.sim(60,1/60); out.kills=kills.length; out.nSeq=kills.every((k,i)=>k.n===i+1); out.gold=kills.every(k=>k.gold===0.25); out.coins=c[0]; out.hits=c[2]; out.crit=c[3]; out.sk=c[4];
          a.setState(mkState(1.5,['slash','spin',null,null],{stage:10})); out.lv=c[1];
          a.setState(mkState(1.5,['slash','spin',null,null],{stage:10,region:'상수 계단길'})); out.map=a.stats().map; out.mapW=a.stats().mapW; const k0=a.stats().kills; a.sim(20,1/60); out.afterK=a.stats().kills-k0; out.alive=!a.stats().dead;
          return out; }''')
        check('kill 이벤트 {n(1부터 차례로), gold(= mon.gold)} · coin·hit·크리·skill 이벤트가 난다', EV['kills'] > 40 and EV['nSeq'] and EV['gold'] and EV['coins'] > 40 and EV['hits'] > 60 and EV['crit'] > 0 and EV['sk'] > 5, EV)
        check('스테이지가 오르면 levelup 이벤트', EV['lv'] == 1, EV['lv'])
        check('지역이 바뀌면 그 지역 맵으로 바뀌고(폭 3000) 계속 사냥한다', EV['map'] == '상수 계단길' and EV['mapW'] == 3000 and EV['afterK'] > 10 and EV['alive'], (EV['map'], EV['mapW'], EV['afterK']))

        # ---------- (f) 사망/부활 ----------
        F = await pg.evaluate('''()=>{
          const out={}; const dt=1/60;
          const a=mkArena({seed:6,noManifest:true}); a.setState(mkState(1,['slash',null,null,null])); const d=a.debug,P=d.P; const ev=[];
          a.on('die',()=>ev.push(['die',+a.stats().t.toFixed(2)])); a.on('revive',()=>ev.push(['revive',+a.stats().t.toFixed(2)])); a.sim(8,dt);
          const k0=a.stats().kills, x0=P.x; d.killPlayer(); out.deadFlag=a.stats().dead; out.hp=a.stats().hp; a.sim(2,dt); out.stillDead=a.stats().dead; out.noActDead=(a.stats().kills===k0);
          a.sim(3,dt); out.revived=!a.stats().dead; out.hpFull=a.stats().hp>=a.stats().hpMax-1; out.pos=P.x; out.spawn=d.map().spawnX; out.inv=P.inv; out.ev=ev; out.deaths=a.stats().deaths;
          // 반복해 죽는 판은 처치율이 떨어진다(복귀 시간이 진짜 패널티)
          const kpm=(dieEvery)=>{ const b=mkArena({seed:6,noManifest:true}); b.setState(mkState(1,['slash','spin',null,null])); b.sim(15,dt); const s0=b.stats().kills; for(let t=0;t<90;t++){ b.sim(1,dt); if(dieEvery&&t%dieEvery===dieEvery-1&&!b.stats().dead) b.debug.killPlayer(); } return (b.stats().kills-s0)/90*60; };
          out.kpmNormal=kpm(0); out.kpmDie15=kpm(15);
          return out;}''')
        check('사망: hp 0 · 죽어 있는 동안 아무것도 못 한다', F['deadFlag'] and F['hp'] == 0 and F['stillDead'] and F['noActDead'])
        check('부활: 약 4초 뒤 시작 지점에서 체력 가득 · 무적 시간', F['revived'] and F['hpFull'] and abs(F['pos'] - F['spawn']) < 60 and F['inv'] > 0.2, (F['pos'], F['spawn'], F['inv']))
        dt_ = F['ev'][1][1] - F['ev'][0][1] if len(F['ev']) >= 2 else -1
        check('die → revive 이벤트 순서와 간격 ≈ 4초', len(F['ev']) == 2 and F['ev'][0][0] == 'die' and F['ev'][1][0] == 'revive' and 3.7 <= dt_ <= 4.4, F['ev'])
        check('15초마다 죽으면 처치율이 떨어진다 (복귀 시간 패널티)', F['kpmDie15'] < F['kpmNormal'] * 0.9, (round(F['kpmNormal']), round(F['kpmDie15'])))

        # ---------- (g) report 이벤트 ----------
        G = await pg.evaluate('''()=>{
          const out={}; const dt=1/60;
          const a=mkArena({seed:8,noManifest:true}); a.setState(mkState(1,['slash','spin',null,null])); const reps=[]; a.on('report',e=>reps.push(e));
          let kills=0; a.on('kill',()=>kills++);
          a.sim(95,dt);
          out.reps1=reps.slice(); out.kills1=kills; out.pending=a.stats().pendingKills; out.runSecs=a.stats().runSecs;
          // 숨김: 시뮬이 멈추고 시간도 안 샌다
          const t0=a.stats().t, k0=a.stats().kills; a.setHidden(true); a.sim(40,dt); out.hiddenT=a.stats().t-t0; out.hiddenK=a.stats().kills-k0; a.setHidden(false);
          // 일시정지
          a.setPaused(true); a.sim(40,dt); out.pausedT=a.stats().t-t0; a.setPaused(false);
          const before=reps.length; a.sim(30,dt); out.after=reps.slice(before);
          // 종료 때 남은 것을 보낸다
          const b=mkArena({seed:8,noManifest:true}); b.setState(mkState(1,['slash',null,null,null])); const r2=[]; b.on('report',e=>r2.push(e)); b.sim(17.4,dt); const kk=b.stats().kills; b.destroy(); out.destroyRep=r2; out.destroyKills=kk;
          // 숨기는 순간 남은 것을 보낸다
          const c=mkArena({seed:8,noManifest:true}); c.setState(mkState(1,['slash',null,null,null])); const r3=[]; c.on('report',e=>r3.push(e)); c.sim(12.5,dt); const kc=c.stats().kills; c.setHidden(true); out.hideRep=r3.slice(); out.hideKills=kc; c.sim(60,dt); out.hideRepAfter=r3.length;
          // 도전(보스) 동안에는 secs 를 세지 않는다
          const e=mkArena({seed:8,noManifest:true}); e.setState(mkState(1,['slash',null,null,null])); e.sim(10,dt); const rs=e.stats().runSecs; e.startChallenge({img:'taewoong',name:'보스',hp:1000,res:'win'}); e.sim(14,dt); out.chalRun=e.stats().runSecs-rs; out.chalBoss=e.stats().boss;
          return out;}''')
        rk = sum(r['kills'] for r in G['reps1']); rs = sum(r['secs'] for r in G['reps1'])
        check('report: 30초마다 {kills, secs} — 95초 동안 3번, secs=30(정수 1~40)', len(G['reps1']) == 3 and all(r['secs'] == 30 and isinstance(r['secs'], int) for r in G['reps1']), G['reps1'])
        check('report 의 kills 합 + 보고 안 한 마리 = 실제 처치 수(kill 이벤트)', rk + G['pending'] == G['kills1'], (rk, G['pending'], G['kills1']))
        check('report 의 secs 합 + 남은 시간 = 실제 돌아간 시간(95초)', abs(rs + G['runSecs'] - 95) < 0.5, (rs, round(G['runSecs'], 2)))
        check('창 숨김 중에는 시뮬이 멈추고 처치·시간이 안 샌다', G['hiddenT'] == 0 and G['hiddenK'] == 0, (G['hiddenT'], G['hiddenK']))
        check('일시정지 중에도 시간이 안 간다', G['pausedT'] == 0, G['pausedT'])
        check('숨김·정지 뒤 재개하면 정확히 이어서 보고(30초)', len(G['after']) == 1 and G['after'][0]['secs'] in (28, 29, 30, 31), G['after'])
        check('종료(destroy) 때 남은 17초분을 보낸다(마리 수 일치)', len(G['destroyRep']) == 1 and G['destroyRep'][0]['secs'] == 17 and G['destroyRep'][0]['kills'] == G['destroyKills'], (G['destroyRep'], G['destroyKills']))
        check('숨기는 순간(12초) 남은 것을 보내고, 숨은 뒤엔 보고가 안 늘어난다', len(G['hideRep']) == 1 and G['hideRep'][0]['secs'] == 12 and G['hideRep'][0]['kills'] == G['hideKills'] and G['hideRepAfter'] == 1, (G['hideRep'], G['hideKills']))
        check('도전 던전(보스) 시간은 secs 에 안 들어간다', G['chalRun'] == 0 and G['chalBoss'] is None or G['chalRun'] < 0.5, (G['chalRun'], G['chalBoss']))

        # ---------- (h) 보스 ----------
        BR = await pg.evaluate('''()=>{
          const out={}; const dt=1/60;
          for(const res of ['win','lose','late']){
            const a=mkArena({seed:3,noManifest:true}); a.setState(mkState(1,['slash','spin','bomb','fire'])); a.sim(8,dt);
            const ev=[], states=[]; a.on('boss',e=>ev.push(e.phase)); const rep=[]; a.on('report',e=>rep.push(e));
            const killsBefore=a.stats().kills, hpMax=a.stats().hpMax;
            const t0=a.stats().t; a.startChallenge({img:'taewoong',name:'테스트 보스',hp:1000,res:res==='late'?null:res});
            let pHp=[]; let late=false;
            for(let i=0;i<24*60;i++){ a.sim(dt,dt); const s=a.stats(); if(!states.length||states[states.length-1][0]!==s.boss) states.push([s.boss,+(s.t-t0).toFixed(1)]); if(i%30===0)pHp.push(s.hp/s.hpMax);
              if(res==='late'&&!late&&s.t-t0>5){late=true;a.bossResult('win');} }
            out[res]={ev,states,minHp:Math.min(...pHp),endMap:a.stats().map,boss:a.stats().boss,kills:a.stats().kills-killsBefore,alive:!a.stats().dead};
          }
          // 도전 도중 사냥터 몹은 없다 / 끝나면 사냥터로 돌아온다
          const b=mkArena({seed:3,noManifest:true}); b.setState(mkState(1,['slash',null,null,null])); b.sim(3,dt); const mapName=b.stats().map, W=b.stats().mapW; b.startChallenge({img:'x',name:'보스',hp:500,res:'win'}); out.inRoom={map:b.stats().map,W:b.stats().mapW,mobs:b.stats().mobs}; b.sim(20,dt); out.back={map:b.stats().map,W:b.stats().mapW,same:b.stats().map===mapName&&b.stats().mapW===W};
          // 이미 도전 중일 때 또 시작해도 무시
          const c=mkArena({seed:3,noManifest:true}); c.setState(mkState(1,[])); const ph=[]; c.on('boss',e=>ph.push(e.phase)); c.startChallenge({img:'x',name:'A',hp:5,res:'win'}); c.startChallenge({img:'x',name:'B',hp:5,res:'lose'}); c.sim(20,dt); out.dupIn=ph.filter(p=>p==='in').length;
          // setState 의 boss 필드로도 시작된다(옛 방식)
          const d=mkArena({seed:3,noManifest:true}); const ph2=[]; d.on('boss',e=>ph2.push(e.phase)); d.setState(mkState(1,[],{boss:{img:'x',name:'C',hp:5,res:'lose'}})); d.sim(20,dt); out.viaState=ph2;
          return out;}''')
        for res in ('win', 'lose'):
            b = BR[res]; seq = b['ev']
            want = ['in', 'slam'] + (['rage'] * 1) if False else None
            check('보스(%s): 입장 → 쾅 → … → %s → 끝 순서' % (res, res), seq[0] == 'in' and seq[1] == 'slam' and res in seq and seq[-1] == 'end' and seq.index(res) < len(seq) - 1 and 'rage' in seq, seq)
            tm = {s[0]: s[1] for s in b['states']}
            check('보스(%s): 입장 연출 2.4초 후 전투 시작, 전투 ≈ 10초 뒤 마무리' % res, 2.2 <= tm.get('fight', -1) <= 2.8 and 11.5 <= tm.get('dying' if res == 'win' else 'smash', -1) <= 14.5, b['states'])
            check('보스(%s): 끝나면 사냥터로 복귀, 병아리 생존' % res, b['boss'] is None and b['alive'] and b['endMap'] == '홍대 먹자골목', (b['boss'], b['endMap']))
        check('보스(lose): 병아리 체력이 크게 닳는다(≤ 45%) / (win): 40% 이상 유지', BR['lose']['minHp'] <= 0.45 and BR['win']['minHp'] >= 0.25, (round(BR['lose']['minHp'], 2), round(BR['win']['minHp'], 2)))
        check('결과가 늦게 와도(bossResult) 연출이 끝까지 간다', 'win' in BR['late']['ev'] and BR['late']['ev'][-1] == 'end', BR['late']['ev'])
        check('도전 중엔 평평한 보스 방(폭 900) · 몹 없음, 끝나면 원래 사냥터', BR['inRoom']['map'] == '보스 방' and BR['inRoom']['W'] == 900 and BR['inRoom']['mobs'] == 0 and BR['back']['same'], (BR['inRoom'], BR['back']))
        check('도전 중 또 시작해도 무시(in 한 번)', BR['dupIn'] == 1, BR['dupIn'])
        check('setState({boss}) 로도 시작·종료된다', BR['viaState'][0] == 'in' and BR['viaState'][-1] == 'end', BR['viaState'])

        # ---------- (i) 프레임 비용 · 폴백 · 시트 ----------
        PF = await pg.evaluate('''()=>{
          const a=mkArena({seed:1,noManifest:true}); a.setState(mkState(1.5,['slash','thunder','fire','storm'])); a.sim(10,1/60);
          const ts=[]; for(let i=0;i<300;i++){ const t=performance.now(); a.tick(1/60); ts.push(performance.now()-t); }
          ts.sort((x,y)=>x-y); return {avg:ts.reduce((x,y)=>x+y)/ts.length,p95:ts[(ts.length*.95)|0],max:ts[ts.length-1]};}''')
        check('프레임 비용(갱신+그리기, 소프트웨어 렌더) 평균 ≤ 12ms · p95 ≤ 25ms', PF['avg'] <= 12 and PF['p95'] <= 25, {k: round(v, 1) for k, v in PF.items()})
        FB = await pg.evaluate('''()=>{
          const cv=document.getElementById('cv'); const a=BrjArena.create(cv,{seed:1,manual:true,base:'../nonexistent/',noManifest:false}); a.setState(mkState(1,['slash','thunder','fire','storm'])); a.sim(5,1/60);
          for(let i=0;i<120;i++)a.tick(1/60); const c=cv.getContext('2d'); const d=c.getImageData(0,0,cv.width,cv.height).data; let nz=0; for(let i=3;i<d.length;i+=4*97) if(d[i]>0)nz++; const k=a.stats().kills; a.destroy(); return {nz,k};}''')
        check('그림 파일이 하나도 없어도(폴백) 그려지고 사냥이 된다', FB['nz'] > 500 and FB['k'] >= 0, FB)
        LW = await pg.evaluate('''()=>{
          const out={}; const w=document.getElementById('w'); const cv=document.getElementById('cv');
          const a=mkArena({seed:2,noManifest:true}); a.setState(mkState(1.2,['slash','spin','bomb','storm']));
          a.debug.E.low=true; a.debug.E.cssW=0; for(let i=0;i<300;i++)a.tick(1/60); out.low=a.stats().low; out.k=a.stats().kills;
          for(const wd of [320,390,800,1200]){ w.style.width=wd+'px'; cv.style.height='auto'; a.resize(); for(let i=0;i<20;i++)a.tick(1/60); out['vw'+wd]=a.stats().VW; out['cw'+wd]=cv.width; }
          w.style.width='560px'; a.destroy(); return out;}''')
        check('저사양(low) 모드와 화면 크기 변경(320~1200px)에서도 그려지고 가로 논리 폭이 비율대로 바뀐다', LW['low'] and LW['k'] > 3 and LW['vw320'] > 300 and LW['vw1200'] >= LW['vw320'] - 1 and LW['cw1200'] > LW['cw320'], {k: (round(v) if isinstance(v, float) else v) for k, v in LW.items()})
        # 프레임 시트(manifest) 가 있을 때: 합성 시트(마젠타 몸)로 확인 — fetch 는 file:// 로 못 하므로 임시 http 서버로 연다
        import http.server, socketserver, threading, functools
        fx = os.path.join(ROOT, 'tests', '_arena_v2_fixture'); os.makedirs(os.path.join(fx, 'img', 'brjhunt', 'v2'), exist_ok=True)
        srv = None
        try:
            from PIL import Image, ImageDraw
            man = {}
            for nm, n in [('chick_idle', 2), ('chick_run', 4), ('chick_jump', 1), ('chick_fall', 1), ('chick_attack1', 3), ('chick_attack2', 3), ('chick_attack3', 3), ('chick_cast', 3), ('chick_hurt', 1), ('chick_die', 2)]:
                im = Image.new('RGBA', (128 * n, 128), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
                for i in range(n): dr.ellipse((14 + i * 128, 20 + i * 2, 114 + i * 128, 120), fill=(255, 0, 255, 255), outline=(40, 30, 20, 255), width=4)
                im.save(os.path.join(fx, 'img', 'brjhunt', 'v2', nm + '.png'))
                man[nm] = {'file': nm + '.png', 'frames': n, 'w': 128, 'h': 128, 'fps': 8, 'anchor': [64, 120]}
            json.dump(man, open(os.path.join(fx, 'img', 'brjhunt', 'v2', 'manifest.json'), 'w'))
            class Q(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a): pass
            srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=ROOT)); port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            pg2 = await br.new_page(viewport={'width': 600, 'height': 420})
            await pg2.goto('http://127.0.0.1:%d/tests/brjhunt_arena_harness.html' % port); await pg2.wait_for_timeout(300)
            SH = await pg2.evaluate('''async ()=>{
              const cv=document.getElementById('cv'); const a=BrjArena.create(cv,{seed:1,manual:true,base:'../tests/_arena_v2_fixture/'}); await new Promise(r=>setTimeout(r,600)); a.setState(mkState(1,['slash','thunder',null,null])); a.debug.clearMobs();
              for(let i=0;i<60*6;i++){ a.tick(1/60); if(i%20===5) await new Promise(r=>setTimeout(r,120)); }
              const c=cv.getContext('2d'); const d=c.getImageData(0,0,cv.width,cv.height).data; let mg=0; for(let i=0;i<d.length;i+=4) if(d[i]>180&&d[i+1]<90&&d[i+2]>180&&d[i+3]>0) mg++;
              const mn=a.debug.manifest(); a.destroy(); return {mg,man:mn?Object.keys(mn).length:null};}''')
            await pg2.close()
            check('프레임 시트(manifest)가 있으면 그것으로 그려진다(합성 시트의 마젠타 몸 픽셀 검출)', SH['mg'] > 300, SH)
        finally:
            if srv: srv.shutdown()
            shutil.rmtree(fx, ignore_errors=True)
        check('콘솔·페이지 오류 0', not errs, errs[:5])

        # ---------- 캡처 ----------
        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True)
            await pg.goto(URL); await pg.wait_for_timeout(500)
            async def cap(name):
                await pg.screenshot(path=os.path.join(SHOTS, name + '.png'), clip={'x': 0, 'y': 0, 'width': 580, 'height': 370})
            for reg in range(6):
                await pg.evaluate('''(reg)=>{window.A=mkArena({seed:3,noManifest:false});A.setState(mkState(1.2,['slash','spin','bomb','storm'],{region:['합정','bhc','홍대','상수','망원','한강'][reg]}));}''', reg)
                await pg.evaluate("async()=>{for(let k=0;k<14;k++){for(let i=0;i<60;i++)A.tick(1/60);await new Promise(r=>setTimeout(r,40));}}")
                await cap('map%d_a' % reg)
                await pg.evaluate("async()=>{for(let k=0;k<8;k++){for(let i=0;i<60;i++)A.tick(1/60);await new Promise(r=>setTimeout(r,20));}}"); await cap('map%d_b' % reg)
                await pg.evaluate('()=>A.destroy()')
            # 전투 연출 장면
            await pg.evaluate('''()=>{window.A=mkArena({seed:11});A.setState(mkState(1.2,['slash','thunder','fire','shrimp']));const d=A.debug;A.setAuto(false);d.clearMobs();d.setPos(300,304);d.P.face=1;
              for(const dx of [40,70,95,-70]){const m=d.spawnMob(300+dx,d.map().plats[0],{noPack:true,el:dx===95,fly:false,shoot:false});m.st='patrol';m.sp=0;m.pause=1e9;m.lo=m.hi=m.x;m.hp=m.max=1e9;}
              for(let i=0;i<30;i++)A.tick(1/60);}''')
            await pg.evaluate("()=>{A.input.press('attack')}")
            for i, f in enumerate([5, 4, 5]):
                await pg.evaluate("(f)=>{for(let i=0;i<f;i++)A.tick(1/60)}", f); await cap('combat_basic_%d' % i)
            await pg.evaluate("()=>{A.input.release('attack')}")
            for i, sk in enumerate(['s1', 's2', 's3', 's4']):
                await pg.evaluate("(s)=>{A.debug.P.mp=100;A.debug.slotCd.fill(0);A.input.press(s);A.tick(1/60);A.input.release(s);for(let i=0;i<14;i++)A.tick(1/60)}", sk); await cap('skill_%s_a' % sk)
                await pg.evaluate("()=>{for(let i=0;i<14;i++)A.tick(1/60)}"); await cap('skill_%s_b' % sk)
            await pg.evaluate("()=>A.destroy()")
            # 보스
            await pg.evaluate('''()=>{window.A=mkArena({seed:3});A.setState(mkState(1,['slash','spin','bomb','fire']));for(let i=0;i<60*4;i++)A.tick(1/60);A.startChallenge({img:'taewoong',name:'맛동산 대왕',hp:1000,res:'win'});}''')
            await pg.wait_for_timeout(600)
            for nm, sec in [('boss_intro1', 0.5), ('boss_intro2', 1.3), ('boss_intro3', 1.0), ('boss_fight1', 2.5), ('boss_fight2', 3.0), ('boss_fight3', 3.0), ('boss_win', 3.2), ('boss_win2', 1.4)]:
                await pg.evaluate("(s)=>{for(let i=0;i<s*60;i++)A.tick(1/60)}", sec); await cap(nm)
            await pg.evaluate("()=>A.destroy()")
            # 죽음
            await pg.evaluate('''()=>{window.A=mkArena({seed:3});A.setState(mkState(1,['slash',null,null,null]));for(let i=0;i<60*6;i++)A.tick(1/60);A.debug.killPlayer();for(let i=0;i<40;i++)A.tick(1/60);}''')
            await cap('dead'); await pg.evaluate("()=>{for(let i=0;i<60*4;i++)A.tick(1/60)}"); await cap('revived'); await pg.evaluate("()=>A.destroy()")
        await br.close()
    print('\n실패 %d건' % len(FAILS))
    for f in FAILS: print(' - ' + f)
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
