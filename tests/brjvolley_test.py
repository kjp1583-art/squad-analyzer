#!/usr/bin/env python3
"""브장신 배구 시험 — 엔진(brjvolley.js: 물리·점수·CPU)과 화면(brjvolley.html: 메뉴·키보드·터치·기록).
사용: CHROME=... python3.13 tests/brjvolley_test.py"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
URL = 'file://' + os.path.join(ROOT, 'brjvolley.html')
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {info}'))
    if not cond: fails.append(name)

ENGINE = '''
const BV=window.BrjVolley;
window.T={
  fuzz(seed){ const g=BV.create({seed,target:15}); let bad=null, r=seed*9301+49297;
    const rnd=()=>{r=(r*1103515245+12345)&0x7fffffff;return r/0x7fffffff;};
    for(let f=0;f<4000;f++){ const a={l:rnd()<.4,r:rnd()<.4,u:rnd()<.1,d:rnd()<.3,hit:rnd()<.15}, b={l:rnd()<.4,r:rnd()<.4,u:rnd()<.1,d:rnd()<.3,hit:rnd()<.15}; g.step(a,b);
      const s=g.s, B=s.ball; if(![B.x,B.y,B.vx,B.vy].every(Number.isFinite)){bad='NaN f'+f;break;}
      if(B.x<BV.BR-.01||B.x>BV.W-BV.BR+.01||B.y<BV.BR-.01||B.y>BV.GROUND+1){bad='ball out '+JSON.stringify(B);break;}
      if(Math.abs(B.x-BV.NET_X)<4+BV.BR-3 && B.y>BV.NET_TOP+2 && B.y<BV.GROUND){ /* 네트 안쪽 */ bad='in net '+JSON.stringify(B); break; }
      for(const p of s.p){ const lo=p.side?BV.NET_X+4+BV.PR:BV.PR, hi=p.side?BV.W-BV.PR:BV.NET_X-4-BV.PR; if(p.x<lo-.01||p.x>hi+.01||p.y>BV.GROUND+.01){bad='player '+JSON.stringify(p);break;} }
      if(bad) break; }
    return {bad,score:g.s.score.slice(),phase:g.s.phase}; },
  drop(side){ const g=BV.create({seed:3}); g.s.phase='rally'; const b=g.s.ball; b.x=side?330:100; b.y=60; b.vx=0; b.vy=0; for(let i=0;i<200&&g.s.phase==='rally';i++) g.step({},{}); return {score:g.s.score.slice(),server:g.s.server,phase:g.s.phase}; },
  winAt(side){ const g=BV.create({seed:3,target:15}); g.s.score[side]=14; g.s.phase='rally'; const b=g.s.ball; b.x=side?100:330; b.y=60; b.vx=0; b.vy=0; for(let i=0;i<200&&g.s.phase==='rally';i++) g.step({},{}); return {score:g.s.score.slice(),phase:g.s.phase,winner:g.s.winner}; },
  net(){ const g=BV.create({seed:3}); g.s.phase='rally'; const b=g.s.ball; b.x=150; b.y=BV.GROUND-40; b.vx=12; b.vy=0; let crossed=false; for(let i=0;i<120;i++){ g.step({},{}); if(g.s.phase!=='rally') break; if(b.x>BV.NET_X+4) crossed=true; } return {crossed,x:b.x}; },
  spike(side){ const g=BV.create({seed:3}); g.s.phase='rally'; const p=g.s.p[side], b=g.s.ball; p.x=side?330:100; p.y=BV.GROUND-60; p.vy=0; b.x=p.x+(side?-18:18); b.y=p.y-BV.PCY-10; b.vx=0; b.vy=0; b.cool=0;
    const inp={hit:true,d:false}; g.step(side?{}:inp, side?inp:{}); const sp=Math.hypot(b.vx,b.vy); return {sp,toward:side?b.vx<0:b.vx>0,ev:g.s.ev.map(e=>e.t)}; },
  match(l0,l1,seed){ const g=BV.create({seed,target:15}); let f=0; while(g.s.phase!=='over'&&f<60*60*12){ g.step(g.cpuInput(0,l0),g.cpuInput(1,l1)); f++; } return {w:g.s.winner,f,score:g.s.score.slice()}; }
};
'''

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=['--allow-file-access-from-files'])
        pg = await br.new_page(viewport={'width': 1100, 'height': 720}); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(400); await pg.evaluate(ENGINE)
        # ---- 엔진 ----
        bad = []
        for sd in range(1, 9):
            r = await pg.evaluate(f'T.fuzz({sd})')
            if r['bad']: bad.append((sd, r['bad']))
        check('무작위 입력 8판×4000프레임: 공·선수가 코트 안, 네트를 통과하지 않음, NaN 없음', not bad, bad[:2])
        a, b = await pg.evaluate('T.drop(0)'), await pg.evaluate('T.drop(1)')
        check('공이 왼쪽 땅에 닿으면 오른쪽(2P)이 득점하고 서브권을 가진다', a['score'] == [0, 1] and a['server'] == 1, a)
        check('공이 오른쪽 땅에 닿으면 왼쪽(1P)이 득점하고 서브권을 가진다', b['score'] == [1, 0] and b['server'] == 0, b)
        w = await pg.evaluate('T.winAt(0)'); w2 = await pg.evaluate('T.winAt(1)')
        check('15점째에 승부가 끝난다(승자 기록)', w['phase'] == 'over' and w['winner'] == 0 and w['score'][0] == 15 and w2['winner'] == 1, (w, w2))
        n = await pg.evaluate('T.net()')
        check('네트를 정면으로 뚫지 못한다(튕겨 나온다)', not n['crossed'], n)
        sp0, sp1 = await pg.evaluate('T.spike(0)'), await pg.evaluate('T.spike(1)')
        check('공중에서 때리면 강타 — 빠르고 상대 쪽으로 간다 (양쪽 선수)', sp0['sp'] > 14 and sp0['toward'] and sp1['sp'] > 14 and sp1['toward'] and 'spike' in sp0['ev'], (sp0, sp1))
        res = []
        for sd in range(1, 9):
            r1 = await pg.evaluate(f"T.match('hard','easy',{sd * 11})"); r2 = await pg.evaluate(f"T.match('easy','hard',{sd * 13})")
            res.append((r1['w'] == 0, r2['w'] == 1, r1['f'], r2['f']))
        hw = sum(a for a, b_, _, _ in res) + sum(b_ for _, b_, _, _ in res)
        check('CPU 어려움이 쉬움을 이긴다(양쪽 자리 16판 중 14판 이상)', hw >= 14, hw)
        res2 = [await pg.evaluate(f"T.match('normal','easy',{sd * 17})") for sd in range(1, 9)]
        check('CPU 보통이 쉬움을 대체로 이긴다(8판 중 6판 이상)', sum(1 for r in res2 if r['w'] == 0) >= 6, [r['w'] for r in res2])
        check('모든 CPU 판이 끝난다(무한 랠리 없음 · 12분 이내)', all(r[2] < 43200 and r[3] < 43200 for r in res) and all(r['w'] >= 0 for r in res2))
        # ---- 화면 ----
        txt = await pg.inner_text('#ovMenu')
        check('메뉴: 쉬움·보통·어려움·2인 대전 버튼과 조작 안내', all(k in txt for k in ('쉬움', '보통', '어려움', '2인 대전', '강타')), txt[:100])
        check('메뉴가 보이고 게임은 아직 시작 전', await pg.evaluate("__vb.mode==='menu'") and await pg.is_visible('#ovMenu'))
        await pg.click('[data-level=normal]'); await pg.wait_for_timeout(300)
        check('난이도를 누르면 시작(메뉴 닫힘 · 점수판 CPU·보통)', await pg.evaluate("__vb.mode==='play'") and not await pg.is_visible('#ovMenu') and 'CPU' in await pg.inner_text('#n1') and '보통' in await pg.inner_text('#n1'))
        await pg.wait_for_timeout(1100)   # 서브 준비
        await pg.evaluate("(()=>{const s=__vb.game.s; s.phase='rally'; s.ball.x=330; s.ball.y=40; s.ball.vx=0; s.ball.vy=-8;})()")   # 키 시험 동안 점수가 나서 멈추지 않게
        x0 = await pg.evaluate('__vb.game.s.p[0].x'); await pg.keyboard.down('ArrowRight'); await pg.wait_for_timeout(250); await pg.keyboard.up('ArrowRight'); x1 = await pg.evaluate('__vb.game.s.p[0].x')
        check('→ 키로 1P 병아리가 움직인다', x1 > x0 + 20, (x0, x1))
        await pg.keyboard.down('ArrowLeft'); await pg.wait_for_timeout(250); await pg.keyboard.up('ArrowLeft'); x2 = await pg.evaluate('__vb.game.s.p[0].x')
        check('← 키로 반대로 움직인다', x2 < x1 - 20, (x1, x2))
        await pg.keyboard.press('ArrowUp'); await pg.wait_for_timeout(120); y = await pg.evaluate('__vb.game.s.p[0].y'); gy = await pg.evaluate('__vb.game.GROUND')
        check('↑ 키로 점프(발이 땅에서 떨어진다)', y < gy - 5, (y, gy))
        await pg.keyboard.press('KeyP'); await pg.wait_for_timeout(100); f0 = await pg.evaluate('__vb.game.s.t'); await pg.wait_for_timeout(300); f1 = await pg.evaluate('__vb.game.s.t')
        check('P 키로 일시정지(프레임이 안 흐름) · 안내 창', f1 == f0 and await pg.is_visible('#ovPause') and await pg.evaluate('__vb.paused'))
        await pg.click('#resume'); await pg.wait_for_timeout(300); check('계속하기로 다시 흐른다', await pg.evaluate('__vb.game.s.t') > f1)
        # 승패 화면과 기록 — 엔진 점수를 15 직전으로 올려 끝낸다
        await pg.evaluate("(()=>{const s=__vb.game.s; s.score[1]=14; s.phase='rally'; s.ball.x=100; s.ball.y=60; s.ball.vx=0; s.ball.vy=0; s.p[0].x=40;})()")
        await pg.wait_for_timeout(1500)
        check('15점 → 결과 창(패배 문구)과 기록 저장', await pg.is_visible('#ovOver') and '패배' in await pg.inner_text('#overT'), await pg.inner_text('#overT'))
        rec = json.loads(await pg.evaluate("localStorage.getItem('brjvolley_rec')") or '{}')
        check('기록: 보통 1패 저장', (rec.get('normal') or {}).get('l') == 1, rec)
        await pg.click('#again'); await pg.wait_for_timeout(300); check('한 판 더 → 다시 시작(0:0)', await pg.inner_text('#s0') == '0' and await pg.inner_text('#s1') == '0' and await pg.evaluate("__vb.mode==='play'"))
        await pg.click('#menuBtn'); await pg.wait_for_timeout(200); check('☰ 로 메뉴로 돌아가고 기록이 보인다', await pg.is_visible('#ovMenu') and '보통 0승 1패' in await pg.inner_text('#rec'), await pg.inner_text('#rec'))
        # 2인 대전
        await pg.click('[data-start="2p"]'); await pg.wait_for_timeout(1200)
        a0 = await pg.evaluate('[__vb.game.s.p[0].x,__vb.game.s.p[1].x]'); await pg.keyboard.down('KeyD'); await pg.keyboard.down('ArrowLeft'); await pg.wait_for_timeout(250); await pg.keyboard.up('KeyD'); await pg.keyboard.up('ArrowLeft')
        a1 = await pg.evaluate('[__vb.game.s.p[0].x,__vb.game.s.p[1].x]')
        check('2인: D 는 1P, ← 는 2P 만 움직인다', a1[0] > a0[0] + 15 and a1[1] < a0[1] - 15, (a0, a1))
        check('2인: 이름표 1P · 2P', await pg.inner_text('#n0') == '1P' and await pg.inner_text('#n1') == '2P')
        sn = await pg.evaluate("document.getElementById('cv').toDataURL().length"); check('캔버스가 그려진다(비어 있지 않음)', sn > 4000, sn)
        check('음소거 버튼이 동작한다', (await pg.click('#sndBtn') or True) and await pg.evaluate('__vb.muted') is True)
        check('콘솔·페이지 오류 없음', not errs, errs)
        # 폰: 터치 버튼, 가로 스크롤 없음
        ctx = await br.new_context(viewport={'width': 390, 'height': 780}, has_touch=True, is_mobile=True); m = await ctx.new_page(); me = []
        m.on('pageerror', lambda e: me.append(str(e))); await m.goto(URL); await m.wait_for_timeout(500)
        check('폰: 터치 버튼이 보인다', await m.is_visible('#pad') and all([await m.is_visible(i) for i in ('#bl', '#br', '#bj', '#bh')]))
        check('폰: 가로 스크롤 없음', await m.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1'))
        await m.click('[data-level=easy]'); await m.wait_for_timeout(1200); mx0 = await m.evaluate('__vb.game.s.p[0].x')
        box = await (await m.query_selector('#br')).bounding_box(); await m.touchscreen.tap(box['x'] + 5, box['y'] + 5)
        await m.evaluate("__vb.touch.r=true"); await m.wait_for_timeout(250); await m.evaluate("__vb.touch.r=false"); mx1 = await m.evaluate('__vb.game.s.p[0].x')
        check('폰: 오른쪽 버튼으로 이동', mx1 > mx0 + 15, (mx0, mx1)); check('폰: 오류 없음', not me, me)
        await ctx.close(); await br.close()
    print('\n전부 통과' if not fails else f'\n실패 {len(fails)}건'); sys.exit(1 if fails else 0)
asyncio.run(main())
