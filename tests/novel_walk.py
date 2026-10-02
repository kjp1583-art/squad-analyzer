#!/usr/bin/env python3
"""장편 원고 전 경로 자동 주행(Playwright). 1) novel_sim 이 찾은 경로를 화면 엔진에서 그대로 재생해 6개 엔딩에 모두 닿는지,
2) 무작위 주행으로 막힘·오류가 없는지 확인하고 줄 수·예상 플레이 시간을 출력한다.
사용: python3 tests/novel_walk.py [--random N] [--width 360]"""
import asyncio, subprocess, sys, os, time, random, json
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SIM_ALLCLUE', '1')
import novel_sim as sim
PORT = 8792
NR = int(sys.argv[sys.argv.index('--random') + 1]) if '--random' in sys.argv else 30
W = int(sys.argv[sys.argv.index('--width') + 1]) if '--width' in sys.argv else 360

async def new_page(b):
    ctx = await b.new_context(viewport={'width': W, 'height': 740})
    async def route(r):
        if not r.request.url.startswith('http://localhost:%d/' % PORT): await r.abort()
        else: await r.continue_()
    await ctx.route('**/*', route); pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto('http://localhost:%d/novel.html?fast=1' % PORT)
    await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=15000)
    return ctx, pg, errs

HOOK = """(()=>{window.__dq=[];window.__novel.hook={clue:id=>{const d=window.__dq.shift();window.__log.push(['clue',id,d]);return d===undefined?window.__rnd():!!d}};window.__log=[];window.__lines=0;window.__rnd=()=>Math.random()<.5})()"""

async def play(pg, decisions=None, rnd=None, tmax=240):
    """decisions: sim 의 (kind, pc, dec) 목록(엔진과 같은 자리에서 멈추는지 확인) / rnd: random.Random"""
    await pg.evaluate("__novel.goTitle()"); await pg.evaluate("__novel.newGame()")
    await pg.evaluate(HOOK)
    dq = list(decisions or []); clue_q = [d[2] for d in dq if d[0] == 'clue']
    await pg.evaluate("q=>{window.__dq=q}", clue_q)
    di = [d for d in dq if d[0] != 'clue']; k = 0; lines = 0; npuz = 0; t0 = time.time(); last = None; stuck = 0; trace = []
    while time.time() - t0 < tmax:
        m = await pg.evaluate('__novel.mode()')
        sig = (m['ws'], m['pc'])
        if sig == last: stuck += 1
        else: stuck = 0; last = sig
        if stuck > 400: return {'err': '막힘 ws=%s pc=%s' % sig, 'lines': lines, 'trace': trace[-6:]}
        ws = m['ws']
        if ws == 'line': lines += 1; await pg.evaluate('__novel.advance()')
        elif ws == 'end': return {'end': m['end'], 'lines': lines, 'puz': npuz, 'dec': k}
        elif ws in ('choice', 'puz'):
            if ws == 'puz': npuz += 1
            if decisions is not None:
                if k >= len(di): return {'err': '결정이 모자람 pc=%s' % m['pc'], 'lines': lines}
                kind, pc, dec = di[k]; k += 1
                if pc != m['pc']: return {'err': '경로가 어긋남: 시뮬 pc=%s 화면 pc=%s' % (pc, m['pc']), 'lines': lines}
            else:
                dec = None
            trace.append((ws, m['pc'], dec))
            if ws == 'choice':
                if decisions is not None:
                    if dec[0] == 'timeout':
                        await pg.wait_for_function("__novel.mode().ws!=='choice'||__novel.mode().pc!==%d" % m['pc'], timeout=6000); continue
                    j = m['vis'].index(dec[1]); await pg.evaluate('i=>__novel.choose(i)', j)
                else:
                    await pg.evaluate('i=>__novel.choose(i)', rnd.randrange(len(m['vis'])))
            else:
                if m['ptype'] == 'vote':
                    n = await pg.evaluate("__novel.puzzle.op().d.cands.length+((document.querySelectorAll('.vc.ref').length)?1:0)")
                    i = dec[1] if decisions is not None else rnd.randrange(n)
                    await pg.evaluate('i=>__novel.puzzle.pick(i)', i)
                else:
                    ok = (dec[1] == 'ok') if decisions is not None else rnd.random() < .6
                    if ok: await pg.evaluate('__novel.puzzle.solve()')
                    else:
                        for _ in range(8):
                            await pg.evaluate('__novel.puzzle.wrong()'); await pg.wait_for_timeout(25)
                            if (await pg.evaluate('__novel.mode().ws')) != 'puz': break
                        else:
                            await pg.evaluate('__novel.puzzle.skip()')   # 실패 경로가 없는 퍼즐은 '넘어가기'로
            if ws == 'puz':
                try: await pg.wait_for_function("__novel.mode().ws!=='puz'||__novel.mode().pc!==%d" % m['pc'], timeout=5000)
                except Exception: return {'err': '퍼즐이 안 끝남 pc=%s type=%s' % (m['pc'], m['ptype']), 'lines': lines}
            else: await pg.wait_for_timeout(5)
        else: await pg.wait_for_timeout(8)
    return {'err': '시간 초과', 'lines': lines}

async def main():
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    ok = True
    try:
        story, ctx_ = sim.load()
        found, n, dt = sim.search(story)
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            ctx, pg, errs = await new_page(b)
            print('== 안내 경로(시뮬 경로를 화면 엔진에서 재생) ==')
            res = {}
            for e in story['endings']:
                f = found.get(e['id'])
                if not f: print('엔딩 %s: 시뮬로 도달 못 함' % e['id']); ok = False; continue
                r = await play(pg, decisions=f[0]); res[e['id']] = r
                good = r.get('end') == e['id']; ok &= good
                print('엔딩 %-5s %s  줄(읽은 것) %s · 퍼즐 %s · 결정 %s %s' % (e['id'], 'OK ' if good else 'FAIL', r.get('lines'), r.get('puz'), r.get('dec'), r.get('err', '')))
            print('== 무작위 주행 %d회 ==' % NR)
            seen = {}; lens = []; pz = []
            for i in range(NR):
                r = await play(pg, rnd=random.Random(i)); 
                if 'err' in r: print('  #%d 오류: %s' % (i, r)); ok = False
                else: seen[r['end']] = seen.get(r['end'], 0) + 1; lens.append(r['lines']); pz.append(r['puz'])
            print('무작위로 닿은 엔딩:', seen)
            if lens: print('무작위 주행 줄 수: 최소 %d · 평균 %.0f · 최대 %d' % (min(lens), sum(lens) / len(lens), max(lens)))
            allp = [r for r in res.values() if 'lines' in r and 'err' not in r]
            if allp:
                for k, r in res.items():
                    mins = (r['lines'] * 4 + r['puz'] * 60) / 60
                    print('  엔딩 %-5s 줄 %d, 퍼즐 %d -> 예상 %.0f분' % (k, r['lines'], r['puz'], mins))
            print('콘솔 오류:', errs[:5] if errs else '없음'); ok &= not errs
            await b.close()
    finally: sp.terminate()
    print('\n결과:', '통과' if ok else '실패'); return 0 if ok else 1
sys.exit(asyncio.run(main()))
