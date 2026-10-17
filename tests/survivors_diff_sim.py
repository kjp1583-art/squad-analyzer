# -*- coding: utf-8 -*-
"""📈 난이도 곡선 측정기 — 흐접새우 서바이벌의 「시간에 따른 위험」을 분 단위로 잰다.
[2026-10-16 사장님 전달] 「첫 무기 각성 전까지의 난이도가 너무 높으니 낮추고, 중반 난이도가 높아지게 — 곡선이 우상향으로 체감되게」

charbal 측정기(survivors_charbal_sim.py)의 정책 봇·시드 난수·훅을 그대로 쓰되, 판마다 분 단위 기록을 붙인다:
  분별 받은 피해 · 분별 최저 HP · 분별 동시 적 수 · 분별 처치 · 레벨 · 첫 무기 각성 시각 · 사망 시각.
난이도(일반/하드/베리하드)는 시작 화면의 체크박스를 켜서 고른다(start 가 읽는 그 값).

사용 예
  nice -n 10 python3 tests/survivors_diff_sim.py run --out /tmp/df --seeds 1-4 --modes n,h,v --procs 2
  python3 tests/survivors_diff_sim.py report --out /tmp/df [--tag 이름]   # 분별 위험 곡선 표
  --html 로 다른 사본을 잴 수 있다(결과 줄에 html 해시 + --tag 가 남아 섞이지 않는다).
"""
import argparse, asyncio, glob, hashlib, json, math, os, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
import survivors_charbal_sim as C

TOOL = 1
ROOT = H.ROOT
MODES = {'n': '일반', 'h': '하드', 'v': '베리하드'}

# update 를 감싸 분 단위 기록을 쌓는다(게임 로직은 안 바꾼다).
TEL_JS = r"""
(()=>{const X=window.__p6x,XX=window.__cbx;const T=window.__tel={rows:[],ev1:null,evN:0,lv1:null};
 let cur=null;const u0=X.update;
 const mk=m=>({m,d0:XX.dmg.taken,minhp:1,ne:0,nes:0,n:0,k0:X.S.kills,nb:0,big:0});
 X.update=function(dt){u0(dt);const S=X.S;if(!S||!S.p)return;
  if(!cur)cur=mk(0);
  const m=Math.floor(S.t/60);
  if(m>cur.m){const r=cur;r.dmg=+(XX.dmg.taken-r.d0).toFixed(1);r.kills=S.kills-r.k0;r.lv=S.lv;r.ne=+(r.ne/Math.max(1,r.n)).toFixed(1);r.mhp=Math.round(S.p.mhp);r.ev=Object.keys(S.ev).length;delete r.d0;delete r.k0;delete r.n;delete r.nes;T.rows.push(r);cur=mk(m);}
  const q=S.p.hp/S.p.mhp;if(q<cur.minhp)cur.minhp=q;cur.ne+=S.ne||0;cur.n++;
  const evn=Object.keys(S.ev).length;if(evn>0&&T.ev1===null){T.ev1=+S.t.toFixed(2);}
  T.evN=evn;};
 window.__telFlush=()=>{const S=X.S;if(!cur)return;const r=cur;r.dmg=+(XX.dmg.taken-r.d0).toFixed(1);r.kills=S.kills-r.k0;r.lv=S.lv;r.ne=+(r.ne/Math.max(1,r.n)).toFixed(1);r.mhp=Math.round(S.p.mhp);r.ev=Object.keys(S.ev).length;r.part=1;delete r.d0;delete r.k0;delete r.n;delete r.nes;T.rows.push(r);cur=null;};
})();
"""


def job_key(mode, char, seed, sig):
    return '%s|%s|%d|%s' % (mode, char, seed, sig)


async def run_one(browser, srv, page_name, a, mode, char, seed, sig_conf):
    t0 = time.time()
    ctx = await browser.new_context(viewport={'width': 1280, 'height': 720}, screen={'width': 1280, 'height': 720})
    errs = []
    row = {'mode': mode, 'char': char, 'seed': seed}
    try:
        await ctx.add_init_script(C.INIT_JS % {'seed': 0x5eed0000 ^ seed, 'hc': 8})
        base = 'http://127.0.0.1:%d/' % srv.port

        async def route(r):
            if r.request.url.startswith(base):
                await r.continue_()
            else:
                await r.abort()
        await ctx.route('**/*', route)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
        await pg.goto(base + page_name)
        await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined', polling=50, timeout=20000)
        await pg.add_script_tag(content=open(C.BOT_JS, encoding='utf-8').read())
        await pg.evaluate("m=>{document.getElementById('hardChk').checked=(m==='h');document.getElementById('vhChk').checked=(m==='v');}", mode)
        info = await pg.evaluate('c=>__cb.init(c)', {'char': char, 'seed': seed, 'policy': 'full', 'cap': a.cap, 'dt': 1 / 30, 'params': {}, 'trace': False})
        row['info'] = info
        await pg.add_script_tag(content=TEL_JS)
        while True:
            r = await pg.evaluate('()=>__cb.run({maxMs:3000})')
            if r['done']:
                fr = r['row']
                for k in ('end_t', 'dead', 'kills', 'lv', 'hp_end', 'min_hp', 'dmg_taken', 'hits', 'hit_src', 'evolved', 'rev_used', 'bosses', 'ended'):
                    row[k] = fr.get(k)
                break
            if time.time() - t0 > 1800:
                raise RuntimeError('한 판이 30분을 넘김')
        await pg.evaluate('()=>window.__telFlush()')
        tel = await pg.evaluate('()=>window.__tel')
        row['tel'] = tel
        row['hard'] = await pg.evaluate('()=>({h:!!__p6x.S.hard,v:!!__p6x.S.vh})')
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


def load_rows(out):
    rows = []
    for fn in sorted(glob.glob(os.path.join(out, 'runs.*.jsonl'))):
        for ln in open(fn, encoding='utf-8'):
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    return rows


async def worker(a, wid):
    from playwright.async_api import async_playwright
    pid = os.getpid()
    name = 'survivors_df_%d.html' % pid
    path = H.make_copy(src=a.html, dst=name, extra='\n' + C.EXTRA_HOOK)
    srv = H.Srv()
    srv.httpd.handle_error = lambda *x: None
    html_hash = C.md5(os.path.join(ROOT, a.html))
    bot_hash = C.md5(C.BOT_JS)
    sig = C.md5('|'.join(map(str, [TOOL, a.cap, html_hash, bot_hash, a.tag])), text=True)
    chars = C.parse_chars(a.chars, a.html)
    seeds = C.parse_seeds(a.seeds)
    modes = a.modes.split(',')
    done = {job_key(r['mode'], r['char'], r['seed'], r.get('sig')) for r in load_rows(a.out) if 'error' not in r}
    jobs = [(m, c, s) for s in seeds for m in modes for c in chars if job_key(m, c, s, sig) not in done]
    claims = os.path.join(a.out, '.claims_' + sig)
    os.makedirs(claims, exist_ok=True)
    outf = os.path.join(a.out, 'runs.%d.jsonl' % pid)
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            for i, (m, c, s) in enumerate(jobs):
                try:
                    os.mkdir(os.path.join(claims, hashlib.md5(job_key(m, c, s, sig).encode()).hexdigest()))
                except FileExistsError:
                    continue
                row = await run_one(b, srv, name, a, m, c, s, sig)
                row.update({'sig': sig, 'tag': a.tag, 'html': html_hash, 'bot': bot_hash, 'cap': a.cap})
                with open(outf, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                if 'error' in row:
                    print('[w%d] ✗ %s %s s%d: %s' % (wid, m, c, s, row['error']), flush=True)
                else:
                    print('[w%d] %d/%d %s %-5s s%-2d %s %5.0f초 처치 %5d Lv%-3d 각성@%s %.0f초' % (
                        wid, i + 1, len(jobs), m, c, s, '사망' if row['dead'] else '생존', row['end_t'], row['kills'], row['lv'],
                        row['tel'].get('ev1'), row['wall_s']), flush=True)
            await b.close()
    finally:
        srv.close()
        try:
            os.remove(path)
        except Exception:
            pass


def cmd_run(a):
    os.makedirs(a.out, exist_ok=True)
    if a.procs <= 1:
        asyncio.run(worker(a, a.wid))
        return
    base = [sys.executable, os.path.abspath(__file__), 'run', '--out', a.out, '--chars', a.chars, '--seeds', a.seeds, '--modes', a.modes,
            '--cap', str(a.cap), '--html', a.html, '--tag', a.tag, '--procs', '1']
    ps = [subprocess.Popen(base + ['--wid', str(i)], cwd=ROOT) for i in range(a.procs)]
    print('끝 코드', [p.wait() for p in ps])


# ---------------------------------------------------------------- 집계
def cmd_report(a):
    rows = [r for r in load_rows(a.out) if 'error' not in r and r.get('tag') == a.tag]
    if a.sig:
        rows = [r for r in rows if r.get('sig') == a.sig]
    if not rows:
        print('줄이 없다'); return
    sigs = sorted({r['sig'] for r in rows})
    if len(sigs) > 1:
        print('⚠ 조건이 섞임:', sigs, '— --sig 로 고르세요'); return
    print('html %s · 봇 %s · cap %s · 태그 %r · %d판' % (rows[0]['html'], rows[0]['bot'], rows[0]['cap'], a.tag, len(rows)))
    for mode in a.modes.split(','):
        R = [r for r in rows if r['mode'] == mode]
        if not R:
            continue
        print('\n== %s  (%d판 · 캐릭터 %d · 시드 %d) ==' % (MODES[mode], len(R), len({r['char'] for r in R}), len({r['seed'] for r in R})))
        report_mode(R, a)


def report_mode(R, a):
    cap = R[0]['cap']
    maxm = int(cap // 60)
    # 분별 위험(hazard): 그 분에 들어선 판 중 그 분 안에 죽은 비율
    print('분 | 생존판 | 사망 | 위험% | 평균받은피해/최대HP | 최저HP중앙 | 동시적수 | 분당처치')
    cum_dead = 0
    ev_times = [r['tel']['ev1'] for r in R if r['tel'].get('ev1') is not None]
    for m in range(maxm):
        alive = [r for r in R if r['end_t'] >= m * 60 or (not r['dead'] and r['end_t'] >= m * 60)]
        entered = [r for r in R if r['end_t'] > m * 60]
        died = [r for r in entered if r['dead'] and r['end_t'] < (m + 1) * 60]
        if not entered:
            break
        rr = []
        for r in entered:
            for t in r['tel']['rows']:
                if t['m'] == m:
                    rr.append(t)
        dmgr = statistics.mean([t['dmg'] / max(1, t['mhp']) for t in rr]) if rr else 0
        minhp = statistics.median([t['minhp'] for t in rr]) if rr else 0
        ne = statistics.mean([t['ne'] for t in rr]) if rr else 0
        kp = statistics.mean([t['kills'] for t in rr]) if rr else 0
        print('%2d | %4d | %3d | %5.1f | %6.2f | %5.2f | %6.0f | %6.0f' % (m, len(entered), len(died), 100 * len(died) / len(entered), dmgr, minhp, ne, kp))
    # 첫 각성 시각 분포와 「각성 전 사망」
    dead = [r for r in R if r['dead']]
    pre = [r for r in dead if r['tel'].get('ev1') is None or r['end_t'] < r['tel']['ev1']]
    print('판 %d · 사망 %d · 그중 첫 각성 전 사망 %d (%.0f%%)' % (len(R), len(dead), len(pre), 100 * len(pre) / max(1, len(dead))))
    if ev_times:
        q = lambda p: C.quant(ev_times, p)
        print('첫 각성 시각(초) 있는 판 %d/%d : 최소 %.0f · 25%% %.0f · 중앙 %.0f · 75%% %.0f · 최대 %.0f' % (len(ev_times), len(R), min(ev_times), q(.25), q(.5), q(.75), max(ev_times)))
    surv = [r['end_t'] for r in R]
    print('생존시간 중앙 %.0f초 · 평균 %.0f초 · cap(%d초)까지 산 판 %d%% · 사망 첫 5분 %d%% · 5~10분 %d%% · 10~15분 %d%% · 15분~ %d%%' % (
        statistics.median(surv), statistics.mean(surv), cap, 100 * sum(1 for r in R if not r['dead']) / len(R),
        100 * sum(1 for r in dead if r['end_t'] < 300) / len(R), 100 * sum(1 for r in dead if 300 <= r['end_t'] < 600) / len(R),
        100 * sum(1 for r in dead if 600 <= r['end_t'] < 900) / len(R), 100 * sum(1 for r in dead if r['end_t'] >= 900) / len(R)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    for n in ('run', 'report'):
        p = sub.add_parser(n)
        p.add_argument('--out', required=True)
        p.add_argument('--chars', default='all')
        p.add_argument('--seeds', default='1-4')
        p.add_argument('--modes', default='n,h,v')
        p.add_argument('--cap', type=float, default=1500)
        p.add_argument('--html', default='survivors.html')
        p.add_argument('--tag', default='')
        p.add_argument('--procs', type=int, default=1)
        p.add_argument('--wid', type=int, default=0)
        p.add_argument('--sig', default=None)
    a = ap.parse_args()
    {'run': cmd_run, 'report': cmd_report}[a.cmd](a)


if __name__ == '__main__':
    main()
