# -*- coding: utf-8 -*-
"""⚔ 보스전 측정기 — 흐접새우 서바이벌(survivors.html)에서 한 캐릭터가 보스 한 마리를 혼자 상대하는 시간·피해를 같은 정책 봇·같은 시드로 잰다.
[2026-10-17 태웅 「씩씩 박치기」 개편] charbal 은 잡몹전(처치@5/10/15분·생존)을 재고, 이 도구는 보스전을 잰다. 둘을 같이 봐야 한 지표에 속지 않는다.

- 틀은 survivors_charbal_sim.py 를 그대로 쓴다(임시 사본 · 시드 난수 · 정책 봇 decide). 카드는 안 고른다 — 시작 무기를 정해 둔 레벨(--lv)·각성(--ev)으로 쥐여 준다.
- 잡몹 스폰·보스 졸개 소환은 끈다. S.t 를 --t0(기본 300초)로 맞춰 보스 체력·공격력이 그 시각 값이 되게 한다.
- 끝 = 보스 처치 · 내 사망 · --cap 초(기본 240) 시간 초과. 시간 초과는 처치 시간을 cap 으로 치고 남은 체력 비율을 같이 본다.

사용 예
  nice -n 10 python3 tests/survivors_bossduel_sim.py run --out /tmp/bd --chars tw,brj,jjg --seeds 1-8 --lv 5 --boss sr --procs 2
  python3 tests/survivors_bossduel_sim.py report --out /tmp/bd --focus tw          # 캐릭터별 중앙값 · tw 대 로스터 중앙값
  python3 tests/survivors_bossduel_sim.py run ... --html /tmp/survivors_new.html   # 상향안 사본(결과 줄에 html 해시)
"""
import argparse, asyncio, glob, hashlib, json, os, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
import survivors_charbal_sim as CB

DUEL_JS = os.path.join(HERE, 'survivors_bossduel_bot.js')
TOOL_VERSION = 1
HOOK = CB.EXTRA_HOOK + r"""
{const ws=waveSpawn;waveSpawn=function(dt){if(window.__duelQuiet)return;return ws.apply(this,arguments);};}
"""


def sig_of(a):
    return CB.md5('|'.join(map(str, [TOOL_VERSION, a.t0, a.cap, a.lv, a.ev, a.boss, a.hpmul, a.summon, '%.6f' % a.dt, CB.md5(os.path.join(CB.ROOT, a.html)), CB.md5(CB.BOT_JS), CB.md5(DUEL_JS), CB.SIM_MODE])), text=True)


async def run_one(browser, srv, page, a, char, seed):
    t0 = time.time()
    ctx = await browser.new_context(viewport={'width': 1280, 'height': 720}, screen={'width': 1280, 'height': 720})
    errs = []
    row = {'char': char, 'seed': seed}
    try:
        await ctx.add_init_script(CB.INIT_JS % {'seed': 0x5eed0000 ^ seed, 'hc': 8})
        base = 'http://127.0.0.1:%d/' % srv.port

        async def route(r):
            await (r.continue_() if r.request.url.startswith(base) else r.abort())
        await ctx.route('**/*', route)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        await pg.goto(base + page)
        await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined', polling=50, timeout=20000)
        await pg.add_script_tag(content=open(CB.BOT_JS, encoding='utf-8').read())
        await pg.add_script_tag(content=open(DUEL_JS, encoding='utf-8').read())
        cfg = {'char': char, 'seed': seed, 't0': a.t0, 'cap': a.cap, 'lv': a.lv, 'ev': a.ev, 'boss': a.boss, 'dt': a.dt, 'summon': a.summon, 'hpMul': a.hpmul}
        row['info'] = await pg.evaluate('c=>__bd.init(c)', cfg)
        while True:
            r = await pg.evaluate('()=>__bd.run({maxMs:3000})')
            if r['done']:
                row.update(r['row'])
                break
            if time.time() - t0 > 900:
                raise RuntimeError('한 판이 15분을 넘김')
    except Exception as e:
        row['error'] = str(e)[:400]
    finally:
        try:
            await ctx.close()
        except Exception:
            pass
    row['errs'] = errs
    row['wall_s'] = round(time.time() - t0, 1)
    return row


async def worker(a, jobs, wid):
    from playwright.async_api import async_playwright
    pid = os.getpid()
    name = 'survivors_bd_%d.html' % pid
    path = H.make_copy(src=a.html, dst=name, extra='\n' + HOOK)
    srv = H.Srv()
    srv.httpd.handle_error = lambda *x: None
    claims = os.path.join(a.out, '.claims')
    os.makedirs(claims, exist_ok=True)
    outf = os.path.join(a.out, 'runs.%d.jsonl' % pid)
    sg = sig_of(a)
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            for (i, n, char, seed) in jobs:
                key = '%s|%d|%s' % (char, seed, sg)
                try:
                    os.mkdir(os.path.join(claims, hashlib.md5(key.encode()).hexdigest()))
                except FileExistsError:
                    continue
                row = await run_one(b, srv, name, a, char, seed)
                row.update({'sig': sg, 'html': CB.md5(os.path.join(CB.ROOT, a.html)), 'lv': a.lv, 'ev': a.ev, 'boss': a.boss, 't0': a.t0})
                with open(outf, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                if 'error' in row:
                    print('[w%d] ✗ %s 시드%d: %s' % (wid, char, seed, row['error']), flush=True)
                else:
                    print('[w%d] %d/%d %-5s 시드%-3d %-8s %6.1f초 · 보스 남은 %3.0f%% · 받은 피해 %6.0f%s' % (wid, i, n, char, seed, row['how'], row['t'], row['bossHpf'] * 100, row['taken'], '  ⚠ 페이지 오류 %d' % len(row['errs']) if row['errs'] else ''), flush=True)
            await b.close()
    finally:
        srv.close()
        try:
            os.remove(path)
        except Exception:
            pass


def done_keys(a, sg):
    ks = set()
    for fn in glob.glob(os.path.join(a.out, '*.jsonl')):
        for ln in open(fn, encoding='utf-8'):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get('sig') == sg and 'error' not in r:
                ks.add('%s|%d|%s' % (r['char'], r['seed'], sg))
    return ks


def build_jobs(a):
    chars = CB.parse_chars(a.chars, a.html)
    seeds = CB.parse_seeds(a.seeds)
    sg = sig_of(a)
    dk = done_keys(a, sg)
    jobs = [(c, s) for s in seeds for c in chars if '%s|%d|%s' % (c, s, sg) not in dk]
    return [(i + 1, len(jobs), c, s) for i, (c, s) in enumerate(jobs)], len(chars) * len(seeds)


def cmd_run(a):
    os.makedirs(a.out, exist_ok=True)
    jobs, total = build_jobs(a)
    print('보스전 조건 sig=%s lv=%s ev=%s boss=%s t0=%s cap=%s  (끝난 %d건 건너뜀 · 할 일 %d건)' % (sig_of(a), a.lv, a.ev, a.boss, a.t0, a.cap, total - len(jobs), len(jobs)), flush=True)
    if not jobs:
        return 0
    if a.procs <= 1 or a.worker:
        if not a.worker:
            import shutil
            shutil.rmtree(os.path.join(a.out, '.claims'), ignore_errors=True)
        asyncio.run(worker(a, jobs, a.wid))
        return 0
    import shutil
    shutil.rmtree(os.path.join(a.out, '.claims'), ignore_errors=True)
    os.makedirs(os.path.join(a.out, '.claims'), exist_ok=True)
    base = [sys.executable, os.path.abspath(__file__), 'run', '--out', a.out, '--chars', a.chars, '--seeds', a.seeds, '--lv', str(a.lv), '--ev', str(a.ev), '--boss', a.boss,
            '--t0', str(a.t0), '--cap', str(a.cap), '--dt', str(a.dt), '--html', a.html, '--hpmul', str(a.hpmul), '--summon', str(a.summon), '--worker']
    ps = [subprocess.Popen(base + ['--wid', str(i)], cwd=CB.ROOT) for i in range(a.procs)]
    rc = [p.wait() for p in ps]
    if any(rc):
        print('일꾼 종료 코드', rc)
    return 0


def load(a):
    sg = None
    rows = []
    for fn in sorted(glob.glob(os.path.join(a.out, '*.jsonl'))):
        for ln in open(fn, encoding='utf-8'):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if 'error' in r or (sg and r.get('sig') != sg):
                continue
            rows.append(r)
    if a.sig:
        rows = [r for r in rows if r.get('sig') == a.sig]
    if a.cur:   # --lv/--ev/--boss 와 같은 줄만(서명은 일꾼마다 달라질 수 있어 값으로 거른다)
        rows = [r for r in rows if r.get('lv') == a.lv and r.get('ev') == a.ev and r.get('boss') == a.boss]
    if a.html_hash:
        rows = [r for r in rows if r.get('html') == a.html_hash]
    return rows


def eff_t(r, cap):
    """처치 시간 — 처치 못 한 판(사망·시간 초과)은 cap 으로 친다(남은 체력은 따로 본다)."""
    return r['t'] if r['how'] == 'killed' else cap


def cmd_report(a):
    rows = load(a)
    if not rows:
        print('줄이 없다')
        return 1
    groups = {}
    for r in rows:
        groups.setdefault(r['sig'], []).append(r)
    for sg, rs in groups.items():
        r0 = rs[0]
        print('\n== 조건 sig=%s html=%s lv=%s ev=%s boss=%s t0=%s (%d줄) ==' % (sg, r0.get('html'), r0.get('lv'), r0.get('ev'), r0.get('boss'), r0.get('t0'), len(rs)))
        by = {}
        for r in rs:
            by.setdefault(r['char'], []).append(r)
        cap = a.cap
        tab = []
        for c, v in by.items():
            kt = [eff_t(r, cap) for r in v]
            tk = [r['taken'] for r in v]
            tab.append((c, len(v), statistics.median(kt), sum(r['how'] == 'killed' for r in v), sum(r['dead'] for r in v), statistics.median(tk), statistics.median(r['bossHpf'] for r in v), statistics.median(r['mhp'] for r in v)))
        tab.sort(key=lambda x: x[2])
        print('%-6s %3s %9s %7s %5s %9s %9s %6s' % ('캐릭터', '판', '처치시간중앙', '처치수', '사망', '받은피해중앙', '보스남은중앙', 'maxHP'))
        for c, n, mt, nk, nd, mtk, hf, mhp in tab:
            print('%-6s %3d %9.1f %4d/%-2d %5d %9.0f %8.0f%% %6.0f%s' % (c, n, mt, nk, n, nd, mtk, hf * 100, mhp, '  ◀' if c == a.focus else ''))
        others = [t for t in tab if t[0] != a.focus]
        if others:
            print('  로스터(%s 제외) 처치시간 중앙값 %.1f · 받은피해 중앙값 %.0f' % (a.focus or '-', statistics.median(t[2] for t in others), statistics.median(t[5] for t in others)))
        if a.focus and any(t[0] == a.focus for t in tab):
            ft = [t for t in tab if t[0] == a.focus][0]
            rank = [t[0] for t in tab].index(a.focus) + 1
            print('  %s: 처치시간 %.1f초 (%d/%d위, 빠를수록 상위)' % (a.focus, ft[2], rank, len(tab)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    for nm in ('run', 'report'):
        p = sp.add_parser(nm)
        p.add_argument('--out', required=True)
        p.add_argument('--chars', default='all')
        p.add_argument('--seeds', default='1-8')
        p.add_argument('--lv', type=int, default=5)
        p.add_argument('--ev', type=int, default=0)
        p.add_argument('--boss', default='sr')
        p.add_argument('--t0', type=float, default=300)
        p.add_argument('--cap', type=float, default=240)
        p.add_argument('--dt', type=float, default=1 / 30)
        p.add_argument('--html', default='survivors.html')
        p.add_argument('--hpmul', type=float, default=1)
        p.add_argument('--summon', type=int, default=0)
        p.add_argument('--procs', type=int, default=1)
        p.add_argument('--worker', action='store_true')
        p.add_argument('--wid', type=int, default=0)
        p.add_argument('--focus', default='')
        p.add_argument('--sig', default='')
        p.add_argument('--cur', action='store_true', help='report: --lv/--ev/--boss 가 같은 줄만')
        p.add_argument('--html-hash', default='', help='report: 결과 줄의 html 해시가 이 값인 줄만')
    a = ap.parse_args()
    return cmd_run(a) if a.cmd == 'run' else cmd_report(a)


if __name__ == '__main__':
    sys.exit(main())
