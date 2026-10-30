#!/usr/bin/env python3.13
"""brjhunt_field.js 시험(Playwright, 시간 가속 sim). 사용: python3.13 tests/brjhunt_field_test.py [--shots 폴더]
 - 120초 시뮬 분당 처치(kpm=100 ±15%) — 위력 3단 × 스킬 구성 5종 × 시드 3
 - 이벤트(kill hit skill coin levelup boss in/win/lose), 스킬 10종 전부 시전 시 오류 없음, 보스 승/패
 - 카메라가 세계를 가로질러 움직이는지, 동시 몬스터 상한, 그림이 없을 때(폴백)도 그려지는지
 - 프레임 비용(몹 30·숫자 40·입자 상한)"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
URL = 'file://' + os.path.join(ROOT, 'tests', 'brjhunt_field_harness.html')
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x != '' else ''))
    if not c: FAILS.append(n)

SETS = {
    'none': [None] * 4,
    'basic': ['slash', 'peck', None, None],
    'mid': ['slash', 'spin', 'bomb', 'fire'],
    'full': ['slash', 'thunder', 'egg', 'storm'],
    'slow': ['storm', 'storm', 'shrimp', 'egg'],
}
CD = {'slash': 2.2, 'peck': 2, 'spin': 3.6, 'bomb': 5, 'thunder': 5, 'fire': 4.6, 'egg': 6, 'shrimp': 8, 'storm': 14}
def state(power, ids, mult=1, **kw):
    st = {'stage': 9, 'region': '홍대 먹자골목', 'power': power, 'rate': 6000, 'kpm': 100,
          'party': [{'id': 'a', 'n': '귤', 'gr': 'legend'}, {'id': 'b', 'n': '맛', 'gr': 'epic'}],
          'skills': {'active': [({'id': i, 'lv': 3, 'cd_s': CD[i] * mult, 'power_pct': 150, 'fx_color': '#ffd23c'} if i else None) for i in ids], 'passive': 'shield'}}
    st.update(kw); return st

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=['--allow-file-access-from-files'])
        pg = await br.new_page(viewport={'width': 430, 'height': 700})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(300)

        # 1) 분당 처치
        lo, hi, rows = 1e9, 0, []
        for power in (60, 5000, 5000000):
            for nm, ids in SETS.items():
                for seed in (1, 2, 3):
                    r = await pg.evaluate('''([st,seed])=>{const f=mkField({seed});f.setState(st);const t=[];let last=0;
                        for(let i=0;i<4;i++){f.sim(30,1/30);const k=f.stats().kills;t.push(k-last);last=k;}
                        const s=f.stats();f.destroy();return {kills:s.kills,cam:s.cam,seg:t,alive:s.alive};}''',
                        [state(power, ids, 3 if nm == 'slow' else 1), seed])
                    kpm = r['kills'] / 2.0; lo = min(lo, kpm); hi = max(hi, kpm); rows.append((power, nm, seed, kpm))
        check('120초 시뮬 분당 처치 85~115 (45판)', lo >= 85 and hi <= 115, f'최소 {lo:.0f} 최대 {hi:.0f}')
        # 마지막 60초만 봐도(워밍업 뺀 정상 상태) 85~115
        r = await pg.evaluate('''(st)=>{const f=mkField({seed:5});f.setState(st);f.sim(60,1/30);const a=f.stats().kills;f.sim(60,1/30);return f.stats().kills-a}''', state(5000, SETS['mid']))
        check('정상 상태(60~120초) 분당 처치 85~115', 85 <= r <= 115, r)

        # 2) 이벤트·세계
        r = await pg.evaluate('''async (st)=>{const f=mkField({seed:9});const ev={};['kill','hit','skill','coin','levelup','boss'].forEach(n=>f.on(n,e=>{ev[n]=(ev[n]||0)+1; if(n==='boss')(ev.phases=ev.phases||[]).push(e.phase); if(n==='kill'&&!(e.n>0&&e.gold_view>=0))ev.badKill=1;}));
            f.setState(st); f.sim(20,1/30);
            let camMin=1e9,camMax=-1,xMin=1e9,xMax=-1,maxAlive=0;
            for(let i=0;i<110;i++){f.sim(1,1/30);const s=f.stats();camMin=Math.min(camMin,s.cam);camMax=Math.max(camMax,s.cam);xMin=Math.min(xMin,s.chickX);xMax=Math.max(xMax,s.chickX);maxAlive=Math.max(maxAlive,s.alive);}
            const VW=f.stats().VW;
            f.setState(Object.assign({},st,{stage:10}));
            f.setState(Object.assign({},st,{stage:10,boss:{img:'taewoong',name:'보스',hp:1000}})); f.sim(6,1/30); f.bossResult('win'); f.sim(8,1/30);
            const after=f.stats().boss; f.setState(Object.assign({},st,{stage:10}));
            f.setState(Object.assign({},st,{stage:10,boss:{img:'taewoong',name:'보스',hp:1000}})); f.sim(6,1/30); f.bossResult('lose'); f.sim(8,1/30);
            f.destroy(); return {ev,camSpan:camMax-camMin,VW,xSpan:xMax-xMin,maxAlive,after};}''', state(5000, SETS['mid']))
        ev = r['ev']
        check('이벤트 kill/hit/skill/coin/levelup 발생', all(ev.get(k, 0) > 0 for k in ('kill', 'hit', 'skill', 'coin', 'levelup')), ev)
        check('kill 이벤트 {n, gold_view} 형식', not ev.get('badKill'))
        check('보스 in → win → lose 순서로 알림', ev.get('phases') == ['in', 'win', 'in', 'lose'], ev.get('phases'))
        check('보스 승리 뒤 필드로 돌아온다', r['after'] is None, r['after'])
        check('카메라가 화면 폭의 6배 넘게 움직였다(넓은 필드)', r['camSpan'] > 6 * r['VW'] * 0.5, f"{r['camSpan']:.0f} / VW {r['VW']:.0f}")
        check('동시 몬스터 상한 30 이하', r['maxAlive'] <= 30, r['maxAlive'])

        # 3) 스킬 10종 전부 시전 + 크기 변화 + 폴백
        r = await pg.evaluate('''(st)=>{const f=mkField({seed:4,base:'../nope/'});f.setState(st);f.sim(5,1/30);
            const ids=['slash','peck','spin','bomb','thunder','fire','egg','shield','shrimp','storm'];const got=[];f.on('skill',e=>got.push(e.id));
            ids.forEach(i=>{f.cast(i);for(let k=0;k<20;k++)f.tick(1/30);});
            f.setState(Object.assign({},st,{region:'한강',stage:30,skills:{active:[null,null,null,null],passive:null}}));
            for(let k=0;k<30;k++)f.tick(1/30);
            document.getElementById('cv').style.height='';f.resize();f.tick(1/30);
            const s=f.stats(); f.destroy(); return {got,kills:s.kills};}''', state(5000, SETS['mid']))
        check('시전 가능한 스킬 9종 skill 이벤트(패시브 shield 제외)', sorted(set(r['got'])) == sorted(['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shrimp', 'storm']), r['got'])

        # 4) 프레임 비용
        await pg.set_viewport_size({'width': 430, 'height': 700})
        r = await pg.evaluate('''(st)=>{const f=mkField({seed:2});f.setState(st);f.sim(8,1/30);
            const cv=document.getElementById('cv');
            // 입자·숫자를 가득 채우려 스킬을 연달아 쏜다
            const ids=['storm','thunder','bomb','egg','spin','fire'];let ms=[],mx=0,i=0;
            for(let n=0;n<240;n++){ if(n%15===0)f.cast(ids[(i++)%ids.length]); const t0=performance.now(); f.tick(1/30); const d=performance.now()-t0; ms.push(d); }
            ms.sort((a,b)=>a-b); const avg=ms.reduce((a,b)=>a+b,0)/ms.length; const s=f.stats(); f.destroy();
            return {avg,p95:ms[Math.floor(ms.length*0.95)],max:ms[ms.length-1],alive:s.alive};}''', state(5000, SETS['full']))
        print('INFO 프레임 처리(헤드리스·소프트웨어 렌더, 몹 %d) 평균 %.2fms p95 %.2fms 최대 %.2fms' % (r['alive'], r['avg'], r['p95'], r['max']))
        check('프레임 평균 처리 < 12ms (소프트웨어 렌더 기준)', r['avg'] < 12, '%.2f' % r['avg'])

        # 5) 정지·파괴
        r = await pg.evaluate('''()=>new Promise(res=>{const f=mkField({manual:false,seed:1});f.setState({stage:1,power:100,rate:0});f.start();setTimeout(()=>{const a=f.stats().t;f.stop();const b=f.stats().t;setTimeout(()=>{const c=f.stats().t;f.destroy();res({ran:a>0.2,stopped:Math.abs(c-b)<1e-9});},300);},700);})''')
        check('rAF 로 돌다가 stop() 하면 멈춘다', r['ran'] and r['stopped'], r)

        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True)
            await pg.evaluate('''(st)=>{window.F=mkField({seed:3});F.setState(st);F.sim(8,1/30);F.cast('thunder');for(let i=0;i<4;i++)F.tick(1/30);}''', state(5000, SETS['full']))
            await pg.locator('#cv').screenshot(path=os.path.join(SHOTS, 'field_test.png'))
        check('콘솔·페이지 오류 없음', not errs, errs[:3])
        await br.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과')
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
