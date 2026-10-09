# -*- coding: utf-8 -*-
"""📢 엄! 외침 연출 눈으로 보기(회귀 밖) — 게임 자체 프레임 루프를 멈추고 update/draw 를 직접 돌려 '정확한 시각'에 화면을 찍는다.
사용: python3 tests/survivors_eom_fx_shots.py 출력폴더 접두 [옵션]
  --vp phone|phone430|desk   폰 412x860@2x(LOW) · 폰 430x932@2x · 데스크톱 1280x800@1x (기본 phone)
  --L 1~8 --ev 0|1 --tier 0~5   엄! 외침 레벨 · 각성(개엄!) · 마스터 단계(4↑ + 각성이면 메아리)
  --n 30            주변 적 수(범위 안에 흩어 놓는다) · --t0 5   게임 시간(구역: 0~600 아군 정글 · 600~1200 강가 · 1200~2100 적 정글 · 2100~3000 적 본진 · 3000~ 넥서스)
  --q -1|0|1|2      연출 품질 강제(-1 자동) · --cores 8   navigator.hardwareConcurrency 를 속여 데스크톱을 비LOW 로
  --danger 1        적의 위험 표시(붉은 예고 원)를 머리 위에 깔아 둔다 — 글자가 옅어지고 표시가 비치는지 보려고
  --times 0,.05,.15,.3,.6   시전 뒤 찍을 시각(초) · --root DIR  survivors.html 이 든 폴더(기본 저장소) · --off 1  연출 끔(옛 판 비교용 아님)
임시 사본은 시스템 임시 폴더에 만든다(저장소의 survivors_x.html 은 건드리지 않는다)."""
import asyncio, argparse, os, sys, re, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
VP = {'phone': (412, 860, True), 'phone430': (430, 932, True), 'desk': (1280, 800, False)}
SETUP = r"""(a)=>{const x=__p6x;x.srvUnl&&x.srvUnl(['yumi','eom']);x.CH_set('eom');x.start();const S=x.S,p=S.p;S.t=a.t0;S.w.eom=a.L;if(a.ev)S.ev.eom=1;S.tier={eom:a.tier||0};
  if(a.full){S.ps={amt:3,area:5,might:5,cd:5,pspd:5,glass:3,luck:5,dur:5};x.synCalc&&x.synCalc();}x.tkCalc();
  S.nextBoss=S.nextMini=1e9;if(a.q>=0)x.EX.qo=a.q;if(a.off)x.EX.eomOff=1;
  const nt=(a.L>=2)+(a.L>=4)+(a.L>=6)+(a.L>=8),R=150*Math.pow(1.15,nt)*(a.ev?1.3:1);
  for(const e of x.enemies.a)e.on=false;
  let k=0,s=a.seed||7;const rnd=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};
  while(k<a.n){const r0=Math.max(36,R*Math.sqrt(rnd())*.97),an=rnd()*6.2832;
    const e=x.spawnEnemy(k%5===4?1:0,1,null,{x:p.x+Math.cos(an)*r0,y:p.y+Math.sin(an)*r0});if(!e)break;e.hp=e.mhp=99999;e.dmg=0;k++;}
  S.cd.eom=.25;p.inv=99;p.hp=p.mhp;
  if(a.danger){S.ebooms.push({x:p.x-40,y:p.y-70,R:80,t:9,T:9,d:1,m:'',g:'💔'});S.ebooms.push({x:p.x+90,y:p.y-110,R:60,t:9,T:9,d:1,m:'',g:'⏰'});}   // 예고 원(진홍 점선)
  for(let i=0;i<3;i++){x.update(1/60);x.draw();}
  return {R,k,low:x.LOW};}"""
# 첫 외침이 터지는 프레임(쿨타임이 4초 안팎으로 되감기는 순간)까지만 진행한다 — 옛 판·새 판 모두 같은 방법
CAST = r"""()=>{const x=__p6x,S=x.S;let n=0;while(n<600){S.p.inv=99;S.p.hp=S.p.mhp;x.update(1/60);n++;if(S.cd.eom>1.5)break;}x.draw();return {n,t:+S.t.toFixed(3),c:x.EX.stats().c||null}}"""
STEP = r"""(n)=>{const x=__p6x,S=x.S;for(let i=0;i<n;i++){S.p.inv=99;S.p.hp=S.p.mhp;x.update(1/60);}x.draw();return {t:+S.t.toFixed(3),st:x.EX.stats()}}"""
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('prefix')
    ap.add_argument('--vp', default='phone'); ap.add_argument('--L', type=int, default=1); ap.add_argument('--ev', type=int, default=0)
    ap.add_argument('--tier', type=int, default=0); ap.add_argument('--n', type=int, default=30); ap.add_argument('--t0', type=float, default=5)
    ap.add_argument('--q', type=int, default=-1); ap.add_argument('--cores', type=int, default=0); ap.add_argument('--full', type=int, default=0)
    ap.add_argument('--times', default='0,.05,.15,.3,.6'); ap.add_argument('--root', default=H.ROOT); ap.add_argument('--off', type=int, default=0)
    ap.add_argument('--seed', type=int, default=7); ap.add_argument('--danger', type=int, default=0); ap.add_argument('--crop', type=int, default=0, help='플레이어 중심 장치 px 반폭(0=전체 화면)')
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='eomfx_')
    for f in os.listdir(a.root):   # 에셋은 심볼릭 링크로(게임 파일만 사본)
        if f in ('survivors.html', 'survivors_x.html') or f.startswith('.'): continue
        p = os.path.join(a.root, f)
        if os.path.isdir(p) or f.endswith('.mp3'): os.symlink(os.path.realpath(p), os.path.join(tmp, f))
    s = open(os.path.join(a.root, 'survivors.html'), encoding='utf-8').read()
    m = re.search(r"window\.__p6=\{[^\n]*\};", s); assert m
    s = s.replace(m.group(0), m.group(0) + '\n' + H.HOOK).replace('const INV_CAP=.80;', 'let INV_CAP=.80;')
    s = s.replace('const blink=p.inv>0&&((S.t*20|0)%2);', 'const blink=false;')   # 시험은 무적(p.inv)이라 내 몸이 깜빡여 사라져 보이는 것을 막는다(임시 사본만)
    open(os.path.join(tmp, 'survivors_x.html'), 'w', encoding='utf-8').write(s)
    srv = H.Srv(root=tmp); w, h, mob = VP[a.vp]
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mob, has_touch=mob, device_scale_factor=2 if mob else 1)
        if a.cores: await ctx.add_init_script("Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>%d})" % a.cores)
        errs = []
        async def route(r):
            if r.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_()
            else: await r.abort()
        await ctx.route('**/*', route)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        await pg.goto('http://127.0.0.1:%d/survivors_x.html' % srv.port)
        await pg.wait_for_function('window.__p6x!==undefined', timeout=15000)
        await pg.evaluate("window.requestAnimationFrame=()=>0"); await pg.wait_for_timeout(150)
        info = await pg.evaluate(SETUP, {'t0': a.t0, 'L': a.L, 'ev': a.ev, 'tier': a.tier, 'n': a.n, 'q': a.q, 'off': a.off, 'full': a.full, 'seed': a.seed, 'danger': a.danger})
        await pg.wait_for_timeout(900)   # 내 캐릭터 그림은 비동기로 불러온다 — 뜬 뒤에 찍어야 첫 프레임에 이모지 동그라미가 안 보인다
        await pg.evaluate("()=>{const x=__p6x;for(let i=0;i<2;i++){x.S.cd.eom=Math.max(x.S.cd.eom,.2);x.draw();}}")
        c = await pg.evaluate(CAST)
        print('장면', info, '시전', c)
        cur = 0.0; files = []
        for t in [float(v) for v in a.times.split(',')]:
            steps = round((t - cur) * 60); cur = t
            r = await asyncio.wait_for(pg.evaluate(STEP, steps), 40) if steps > 0 else None
            await pg.wait_for_timeout(40)
            fn = os.path.join(a.out, '%s_%s.png' % (a.prefix, ('%.2f' % t).replace('.', '_')))
            for tr in range(3):   # 헤드리스 브라우저가 가끔 화면 캡처에서 멈춘다 — 시간 제한을 두고 다시 시도한다
                try: await asyncio.wait_for(pg.screenshot(path=fn), 20); break
                except asyncio.TimeoutError: print('  (캡처 지연 — 다시 시도 %d)' % (tr + 1), flush=True)
            files.append((t, fn))
            print('  t=%.2f 저장 %s' % (t, os.path.basename(fn)), r and r['st'], flush=True)
        print('끝', await pg.evaluate("JSON.stringify(__p6x.EX.stats?__p6x.EX.stats():{})"), '오류', errs[:5])
        await b.close()
    srv.close(); shutil.rmtree(tmp, ignore_errors=True)
    # 이어 붙인 시트(플레이어 중심 잘라 내기)
    try:
        from PIL import Image, ImageDraw
        ims = [(t, Image.open(f).convert('RGB')) for t, f in files]
        W0, H0 = ims[0][1].size; hw = a.crop or min(W0, H0) // 2
        cells = []
        for t, im in ims:
            cx0, cy0 = W0 // 2, H0 // 2; c2 = im.crop((max(0, cx0 - hw), max(0, cy0 - hw), min(W0, cx0 + hw), min(H0, cy0 + hw)))
            d = ImageDraw.Draw(c2); d.rectangle((0, 0, 92, 22), fill=(0, 0, 0)); d.text((6, 4), 't=%.2fs' % t, fill=(255, 255, 255)); cells.append(c2)
        cw, chh = cells[0].size; cols = min(3, len(cells)); rows = (len(cells) + cols - 1) // cols
        sheet = Image.new('RGB', (cw * cols, chh * rows), (0, 0, 0))
        for i, c2 in enumerate(cells): sheet.paste(c2, ((i % cols) * cw, (i // cols) * chh))
        sheet.save(os.path.join(a.out, '%s_sheet.png' % a.prefix)); print('시트', os.path.join(a.out, '%s_sheet.png' % a.prefix), sheet.size)
    except Exception as e: print('시트 실패', e)
asyncio.run(main())
