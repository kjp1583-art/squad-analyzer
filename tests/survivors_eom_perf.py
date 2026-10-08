# -*- coding: utf-8 -*-
"""📢 엄! 외침 연출 비용(경고용 — 회귀 목록 밖). 같은 장면에서 '외침 직후 1초'(60프레임)의 프레임당 update+draw+캔버스 래스터 비우기(getImageData) ms 를
[변경 전 main] 과 [새 판 · 연출 끔 / 켬] 으로 번갈아 잰다(소음을 줄이려고 교차 2바퀴 · 중앙값).  사용: python3 tests/survivors_eom_perf.py BASE.html NEW.html [반복=3] [first]   (first = 첫 외침 비용만)
 · 폰 412x860@2x · CPU 4배 제한(게임이 LOW 로 판정) · 데스크톱 1280x800@1x(코어 8 로 속여 비LOW) · 데스크톱 LOW(이 PC 그대로)
 · 장면: 적 30마리(보통) / 140마리(빽빽) × 엄! Lv1 비각성 / Lv8 각성 + 메아리(3연타)
캔버스는 그리기 명령을 모아 두었다가 나중에 래스터하므로 getImageData 로 비우지 않으면 draw 시간이 명령 기록만 잰다(10배 이상 낮게 나온다)."""
import asyncio, sys, os, re, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
SETUP = r"""(a)=>{const x=__p6x;x.srvUnl&&x.srvUnl(['yumi','eom']);x.CH_set('eom');x.start();const S=x.S,p=S.p;S.t=a.t;S.w.eom=a.L;if(a.ev)S.ev.eom=1;S.tier={eom:a.tier};
  if(a.full){S.ps={amt:3,area:5,might:5,cd:5,pspd:5,glass:3,luck:5,dur:5};x.synCalc&&x.synCalc();}x.tkCalc();S.nextBoss=S.nextMini=1e9;
  const nt=(a.L>=2)+(a.L>=4)+(a.L>=6)+(a.L>=8),R=150*Math.pow(1.15,nt)*(a.ev?1.3:1);
  for(const e of x.enemies.a)e.on=false;let n=0,s=5;const rnd=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};
  while(n<a.n){const r0=Math.max(36,R*Math.sqrt(rnd())*.97),an=rnd()*6.2832;const e=x.spawnEnemy(0,1,null,{x:p.x+Math.cos(an)*r0,y:p.y+Math.sin(an)*r0});if(!e)break;e.sp=0;e.hp=e.mhp=1e9;e.dmg=0;n++;}
  S.cd.eom=1e9;p.hp=p.mhp;p.inv=99;window.__cv=document.getElementById('cv').getContext('2d');return {n,low:x.LOW}}"""
MEAS = r"""(a)=>{const x=__p6x,S=x.S,p=S.p,EX=x.EX,cv=window.__cv;
  const one=(cast,n)=>{const v=[];for(let i=0;i<n;i++){p.hp=p.mhp;S.cd.eom=(cast&&i===0)?0:1e9;if(EX.hs>0)EX.hs=0;   // 히트스톱은 건너뛴다(측정은 매 프레임 같은 일을 시킨다)
      const t0=performance.now();x.update(1/60);x.draw();cv.getImageData(0,0,1,1);v.push(performance.now()-t0);}return v;};
  const settle=()=>{S.cd.eom=1e9;if(EX.reset)EX.reset();for(let i=0;i<90;i++){if(EX.hs>0)EX.hs=0;x.update(1/60);x.draw();if(i%10===9)cv.getImageData(0,0,1,1);}cv.getImageData(0,0,1,1);if(window.gc)gc();};   // 모아 둔 그리기 명령을 미리 래스터로 비우고(안 비우면 측정 첫 프레임에 한꺼번에 몰린다) 쓰레기 수거도 끝내 둔다
  for(let i=0;i<60;i++){x.update(1/60);x.draw();}settle();one(true,60);   // 굽기 캐시를 데운다(첫 외침의 스프라이트 만들기는 따로 잰다)
  settle();const idle=one(false,120),cast=[];
  for(let k=0;k<a.reps;k++){settle();if(a.off)EX.eomOff=1;cast.push(one(true,60));EX.eomOff=0;}
  return {idle,cast}}"""
async def run_one(b, port, page, w, h, mob, thr, cores, a, off):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mob, has_touch=mob, device_scale_factor=2 if mob else 1)
    if cores: await ctx.add_init_script("Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>%d})" % cores)
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto('http://127.0.0.1:%d/%s' % (port, page)); await pg.wait_for_function('window.__p6x!==undefined', timeout=15000)
    if thr > 1:
        c = await ctx.new_cdp_session(pg); await c.send('Emulation.setCPUThrottlingRate', {'rate': thr})
    await pg.evaluate("window.requestAnimationFrame=()=>0"); await pg.wait_for_timeout(150)
    info = await pg.evaluate(SETUP, {'t': 120, 'L': a['L'], 'ev': a['ev'], 'tier': a['tier'], 'n': a['n'], 'full': a['L'] == 8})
    R = await pg.evaluate(MEAS, {'reps': a['reps'], 'off': off})
    await ctx.close(); R['low'] = info['low']; R['errs'] = errs[:2]; return R
async def first_cast(b, port, page, w, h, mob, thr, cores, a, warm):
    """새로 연 페이지의 첫 외침 40프레임 비용 — warm 프레임 동안 먼저 그려(미리 굽기가 한 프레임에 하나씩 진행) 두었다가 시전한다(0 이면 곧바로 시전 = 최악)"""
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mob, has_touch=mob, device_scale_factor=2 if mob else 1)
    if cores: await ctx.add_init_script("Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>%d})" % cores)
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page(); await pg.goto('http://127.0.0.1:%d/%s' % (port, page)); await pg.wait_for_function('window.__p6x!==undefined', timeout=15000)
    if thr > 1:
        c = await ctx.new_cdp_session(pg); await c.send('Emulation.setCPUThrottlingRate', {'rate': thr})
    await pg.evaluate("window.requestAnimationFrame=()=>0"); await pg.wait_for_timeout(150)
    await pg.evaluate(SETUP, {'t': 120, 'L': a['L'], 'ev': a['ev'], 'tier': a['tier'], 'n': a['n'], 'full': a['L'] == 8})
    v = await pg.evaluate("""(warm)=>{const x=__p6x,S=x.S,cv=window.__cv,EX=x.EX,o=[];for(let i=0;i<warm;i++){S.p.hp=S.p.mhp;S.cd.eom=1e9;x.update(1/60);x.draw();cv.getImageData(0,0,1,1);}
      S.cd.eom=0;for(let i=0;i<40;i++){S.p.hp=S.p.mhp;if(i>0)S.cd.eom=1e9;if(EX.hs>0)EX.hs=0;const t0=performance.now();x.update(1/60);x.draw();cv.getImageData(0,0,1,1);o.push(performance.now()-t0);}return o}""", warm)
    await ctx.close(); return v
async def main():
    base, new = sys.argv[1], sys.argv[2]; reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3; only_first = len(sys.argv) > 4 and sys.argv[4] == 'first'
    pages = []
    for i, f in enumerate([base, new]):
        s = open(f, encoding='utf-8').read(); m = re.search(r"window\.__p6=\{[^\n]*\};", s); assert m
        s = s.replace(m.group(0), m.group(0) + '\n' + H.HOOK).replace('const INV_CAP=.80;', 'let INV_CAP=.80;')
        s = s.replace('const blink=p.inv>0&&((S.t*20|0)%2);', 'const blink=false;')
        dst = os.path.join(H.ROOT, 'perfx_%d.html' % i); open(dst, 'w', encoding='utf-8').write(s); pages.append(os.path.basename(dst))
    srv = H.Srv(); med = statistics.median
    def summ(r):   # 프레임 번호마다 표본들의 중앙값을 구하고(소음 튐 제거) 그 평균·최대를 낸다
        pf = [med(col) for col in zip(*r['cast'])]; return med(r['idle']), sum(pf) / len(pf), max(pf), pf
    async with async_playwright() as p:
        b = await H.launch(p)
        for tag, thr, w, h, mob, cores in [('폰 412x860@2x · CPU 4배 제한(LOW)', 4, 412, 860, True, 0), ('데스크톱 1280x800 · 비LOW(코어 8)', 1, 1280, 800, False, 8), ('데스크톱 1280x800 · LOW(코어 4)', 1, 1280, 800, False, 0)]:
            print('==', tag, flush=True)
            for (L, ev, tier, name, n) in ([] if only_first else [(1, 0, 0, 'Lv1 비각성', 30), (8, 1, 5, 'Lv8 각성+메아리', 30), (8, 1, 5, 'Lv8 각성+메아리', 140)]):
                a = {'L': L, 'ev': ev, 'tier': tier, 'n': n, 'reps': reps}; rows = {}
                for rnd in range(2):   # 교차 2바퀴(옛 → 새끔 → 새켬)
                    for key, page, off in [('옛 연출', pages[0], False), ('새 연출 끔', pages[1], True), ('새 연출 켬', pages[1], False)]:
                        R = await run_one(b, srv.port, page, w, h, mob, thr, cores, a, off)
                        r = rows.setdefault(key, {'idle': [], 'cast': [], 'low': R['low'], 'errs': []})
                        r['idle'] += R['idle']; r['cast'] += R['cast']; r['errs'] += R['errs']
                print('  %-16s 적 %3d  LOW=%s  (프레임마다 %d 표본의 중앙값)' % (name, n, rows['옛 연출']['low'], len(rows['옛 연출']['cast'])), flush=True)
                S = {}
                for key in ('옛 연출', '새 연출 끔', '새 연출 켬'):
                    S[key] = summ(rows[key]); i0, av, mx, pf = S[key]
                    print('    %-10s 평소(중앙값) %6.2f ms · 외침 뒤 1초: 평균 %6.2f ms · 최대 프레임 %6.1f ms · 20프레임 이후 평균 %6.2f ms  %s' % (key, i0, av, mx, sum(pf[20:]) / len(pf[20:]), rows[key]['errs'] or ''), flush=True)
                print('    → 외침 증가분(평균): 옛 연출 %+.2f ms(평소 대비) · 새 연출 %+.2f ms(끔 대비) · 새 켬 − 옛 %+.2f ms' % (S['옛 연출'][1] - S['옛 연출'][0], S['새 연출 켬'][1] - S['새 연출 끔'][1], S['새 연출 켬'][1] - S['옛 연출'][1]), flush=True)
            fa = {'L': 8, 'ev': 1, 'tier': 5, 'n': 30}; fo = []; fn = []; fw = []
            for k in range(3):   # 새로 연 페이지의 첫 외침(각성 3연타) — 예열 없이 곧바로(최악) / 게임 시작 뒤 30프레임 그리고 나서(실전: 미리 굽기가 끝난 뒤)
                fo.append(await first_cast(b, srv.port, pages[0], w, h, mob, thr, cores, fa, 30)); fn.append(await first_cast(b, srv.port, pages[1], w, h, mob, thr, cores, fa, 0)); fw.append(await first_cast(b, srv.port, pages[1], w, h, mob, thr, cores, fa, 30))
            print('  첫 외침(각성 3연타) 40프레임 중 최대 프레임 중앙값: 옛 %.1f ms · 새(예열 30프레임 뒤) %.1f ms · 새(예열 없이 곧바로 · 최악) %.1f ms' % (med([max(v) for v in fo]), med([max(v) for v in fw]), med([max(v) for v in fn])), flush=True)
        await b.close()
    srv.close()
    for pgname in pages: os.remove(os.path.join(H.ROOT, pgname))
asyncio.run(main())
