# -*- coding: utf-8 -*-
"""📊 캐릭터 성능 측정기 — 흐접새우 서바이벌(survivors.html)의 모든 캐릭터를 같은 조건·같은 정책 봇으로 돌려 상대 비교한다.
[2026-10-09 사장님 지시 "엄장신 너무 구리다는의견이 나왔는데 검증"] 클랜원 의견이 맞는지 숫자로 가리기 위한 도구.

- 실제 게임 코드(update(dt) · pick · start)를 그대로 부른다(draw 는 안 부른다). tests/sv_harness.py 의 임시 사본 방식을 쓴다.
- 정책 봇(tests/survivors_charbal_bot.js)이 페이지 안에서 이동·카드 선택을 한다. 사람이 아니므로 절대 수치는 약하다 — 캐릭터끼리의 상대 비교용이다.
- 같은 시드 = 같은 결과(페이지가 뜨기 전에 Math.random 을 시드 난수로 갈아 끼운다). 실행 사본 이름에 pid 가 들어가 프로세스를 동시에 돌려도 안 겹친다.
- 죽는 판이다(HP 를 채워 주지 않는다). 판 끝 = 사망 또는 --cap 초 도달(기본 900초 = 15분).

사용 예
  # 전 캐릭터 × 시드 1~8 × 일반 정책, 프로세스 3개로 (중단 후 같은 명령으로 이어서 돈다)
  nice -n 10 python3 tests/survivors_charbal_sim.py run --out /tmp/cb --seeds 1-8 --procs 3
  # 시작 무기 하나의 성장만 보는 정책, 일부 캐릭터만
  python3 tests/survivors_charbal_sim.py run --out /tmp/cb --chars eom,brj,yumi --seeds 1-4 --policy sigonly
  # 집계: 캐릭터별 중앙값·사분위, 지표별 순위표, 엄장신 대 로스터 중앙값 차이의 부트스트랩 신뢰구간
  python3 tests/survivors_charbal_sim.py report --out /tmp/cb --focus eom
  # 틀 점검: 전 캐릭터 한 판씩(시드 1, 5분) 에러 없이 도는가 / 같은 시드 두 번이 같은가
  python3 tests/survivors_charbal_sim.py smoke
  python3 tests/survivors_charbal_sim.py determinism

조건(기본): 일반 모드 · dt=1/30 · 창 1280x720(PC · LOW 꺼짐: 적 상한 220) · 소리·화면 효과 끔 · 이어하기 저장 끔 · 정책 full.
  --view 412x860 --low 로 폰 조건(적 상한 140)도 잴 수 있다. --html 로 다른 survivors 사본(상향안)을 재면 결과 줄에 html 해시가 남아 섞이지 않는다.
"""
import argparse, asyncio, atexit, glob, hashlib, json, math, os, random, re, shutil, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H

TOOL_VERSION = 1
ROOT = H.ROOT
BOT_JS = os.path.join(HERE, 'survivors_charbal_bot.js')
POLICIES = ('full', 'sigonly')

# 페이지 스크립트 범위 안에 꽂는 훅(임시 사본에만). 게임 로직은 안 바꾼다 — hitP 를 감싸 「받은 피해」를 정확히 센다.
EXTRA_HOOK = r"""
window.__cbx={get SPAWN_R(){return SPAWN_R},get VW(){return VW},get VH(){return VH},get SC(){return SC},
 PASS,PT,TRD,SM,CO,PICK,PROP,KIND,evReady,evLeft,MAXEV,MAXLV,SLOTW,SLOTP,REV_LV,pv,slotP,cardLv,wOk,TCAP,RES,pmax,
 dmg:{taken:0,hits:0,t5:0,by:{},n:{},log:[],logOn:false}};
{const h0=hitP;hitP=function(d,msg){const p=S.p,b=p.hp,r0=S.revUsed;const r=h0(d,msg);let dm=b-p.hp;if(S.revUsed>r0)dm=b;
  if(dm>0){const D=window.__cbx.dmg;D.taken+=dm;D.hits++;if(S.t<300)D.t5+=dm;
    let src=msg===undefined?'':msg===''?'shot':msg;   // 몸 박치기는 msg 가 없다 → 가장 가까운 적으로 이름을 붙인다
    if(msg===undefined){let bd=1e9,bk='?';for(const e of enemies.a){if(!e.on)continue;const dd=Math.hypot(e.x-p.x,e.y-p.y)-e.r-p.r;if(dd<bd){bd=dd;bk=e.boss?'B:'+e.boss:(KIND[e.ki]&&KIND[e.ki].id)||'?';}}src='c:'+bk;}
    D.by[src]=(D.by[src]||0)+dm;D.n[src]=(D.n[src]||0)+1;if(D.logOn&&D.log.length<600)D.log.push([+S.t.toFixed(2),+dm.toFixed(1),src,+(p.hp/p.mhp).toFixed(2)]);}
  return r;};}
"""
# 페이지가 뜨기 전에 실행: 시드 난수 · 애니메이션 루프 정지(게임 루프를 우리가 돌린다) · 소리 없음 · 화면 효과 끔 · CPU 코어 수 고정(LOW 판정)
INIT_JS = r"""(()=>{
 const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(%(seed)d);
 window.requestAnimationFrame=()=>0;window.cancelAnimationFrame=()=>{};
 window.AudioContext=undefined;window.webkitAudioContext=undefined;
 Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>%(hc)d});
 try{localStorage.setItem('p6_fx','0');}catch(e){}
})();"""


def md5(path_or_text, text=False):
    h = hashlib.md5()
    if text:
        h.update(path_or_text.encode('utf-8'))
    else:
        with open(path_or_text, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()[:8]


def list_chars(html='survivors.html'):
    """CHARS 배열에서 캐릭터 키를 순서대로 뽑는다(브라우저 없이)."""
    s = open(os.path.join(ROOT, html), encoding='utf-8').read()
    i = s.index('const CHARS=[')
    j = s.index('\n];', i)
    return re.findall(r"^\s*\{k:'([a-z0-9_]+)'", s[i:j], re.M)


def parse_chars(spec, html):
    allc = list_chars(html)
    if spec in (None, '', 'all'):
        return allc
    out = []
    for k in spec.split(','):
        k = k.strip()
        if not k:
            continue
        if k not in allc:
            sys.exit('없는 캐릭터 「%s」 — 가능: %s' % (k, ','.join(allc)))
        out.append(k)
    return out


def parse_seeds(spec):
    out = []
    for part in str(spec).split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


class Conf:
    """한 번의 측정 조건 — 이 값이 같아야 같은 조건이다(결과 줄에 서명으로 남는다)."""
    def __init__(self, a):
        self.cap = float(a.cap)
        self.dt = float(a.dt)
        w, h = a.view.lower().split('x')
        self.view = (int(w), int(h))
        self.low = bool(a.low)
        self.html = a.html
        self.params = {}
        for kv in (getattr(a, 'param', None) or []):
            k, v = kv.split('=', 1)
            self.params[k.strip()] = float(v)
        self.trace = bool(getattr(a, 'trace', False))
        self.html_hash = md5(os.path.join(ROOT, a.html))
        self.bot_hash = md5(BOT_JS)
        self.sig = md5('|'.join(map(str, [TOOL_VERSION, self.cap, '%.6f' % self.dt, self.view, self.low, self.html_hash, self.bot_hash, sorted(self.params.items())])), text=True)

    def public(self):
        o = {'tool': TOOL_VERSION, 'cap': self.cap, 'dt': round(self.dt, 6), 'view': '%dx%d' % self.view, 'low': self.low,
             'html': self.html_hash, 'bot': self.bot_hash, 'sig': self.sig}
        if self.params:
            o['params'] = self.params
        return o


def job_key(char, seed, policy, sig):
    return '%s|%d|%s|%s' % (char, seed, policy, sig)


# ---------------------------------------------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------------------------------------------
async def run_one(browser, srv, page_name, conf, char, seed, policy, say=None):
    """판 하나. 결과 줄(dict)을 돌려준다. 페이지 오류가 있으면 errs 에 담는다."""
    t0 = time.time()
    ctx = await browser.new_context(viewport={'width': conf.view[0], 'height': conf.view[1]}, screen={'width': conf.view[0], 'height': conf.view[1]})
    errs = []
    row = {'char': char, 'seed': seed, 'policy': policy}
    try:
        await ctx.add_init_script(INIT_JS % {'seed': 0x5eed0000 ^ seed, 'hc': 4 if conf.low else 8})
        base = 'http://127.0.0.1:%d/' % srv.port

        async def route(r):
            if r.request.url.startswith(base):
                await r.continue_()
            else:
                await r.abort()
        await ctx.route('**/*', route)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        await pg.goto(base + page_name)
        await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined', polling=50, timeout=20000)   # rAF 를 멈춰 뒀으니 기본 polling(raf)을 쓰면 안 된다
        await pg.add_script_tag(content=open(BOT_JS, encoding='utf-8').read())
        info = await pg.evaluate('c=>__cb.init(c)', {'char': char, 'seed': seed, 'policy': policy, 'cap': conf.cap, 'dt': conf.dt, 'params': conf.params, 'trace': conf.trace})
        row['info'] = info
        last_print = -1
        while True:
            r = await pg.evaluate('()=>__cb.run({maxMs:3000})')
            if r['done']:
                row.update(r['row'])
                break
            if say:
                m = int(r['prog']['t'] // 180)
                if m != last_print:
                    last_print = m
                    say('    … %s s%d %s  %4.0f초 · 처치 %d · Lv%d · HP %d%%' % (char, seed, policy, r['prog']['t'], r['prog']['k'], r['prog']['lv'], round(r['prog']['hp'] * 100)))
            if time.time() - t0 > 1800:
                raise RuntimeError('한 판이 30분을 넘김')
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
    for fn in sorted(glob.glob(os.path.join(out, '*.jsonl'))):
        with open(fn, encoding='utf-8') as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    return rows


async def worker_main(a, conf, jobs, wid):
    """프로세스 하나의 일꾼 — 자기 사본·서버·브라우저를 갖고 일감을 하나씩 집어(claims 폴더 mkdir) 돌린다."""
    from playwright.async_api import async_playwright
    pid = os.getpid()
    name = 'survivors_cb_%d.html' % pid
    path = H.make_copy(src=conf.html, dst=name, extra='\n' + EXTRA_HOOK)
    atexit.register(lambda: os.path.exists(path) and os.remove(path))
    srv = H.Srv()
    srv.httpd.handle_error = lambda *x: None      # 브라우저가 먼저 닫혀 끊긴 요청의 트레이스백을 찍지 않는다
    claims = os.path.join(a.out, '.claims')
    os.makedirs(claims, exist_ok=True)
    outf = os.path.join(a.out, 'runs.%d.jsonl' % pid)
    done_n = 0
    say = (lambda s: print(s, flush=True)) if not a.quiet else None
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            for (idx, total, char, seed, policy) in jobs:
                key = job_key(char, seed, policy, conf.sig)
                try:
                    os.mkdir(os.path.join(claims, hashlib.md5(key.encode()).hexdigest()))
                except FileExistsError:
                    continue
                print('[w%d] 시작 %d/%d  %s 시드%d %s' % (wid, idx, total, char, seed, policy), flush=True)
                row = await run_one(b, srv, name, conf, char, seed, policy, say)
                row.update(conf.public())
                with open(outf, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                done_n += 1
                if 'error' in row:
                    print('[w%d] ✗ 오류 %s 시드%d %s: %s' % (wid, char, seed, policy, row['error']), flush=True)
                else:
                    print('[w%d] 완료 %d/%d  %-5s 시드%-3d %-7s  %s %5.0f초 · 처치 %5d · Lv%-3d · 한 판 %.1f초%s' % (
                        wid, idx, total, char, seed, policy, '사망' if row['dead'] else '생존', row['end_t'], row['kills'], row['lv'], row['wall_s'],
                        '  ⚠ 페이지 오류 %d건' % len(row['errs']) if row['errs'] else ''), flush=True)
            await b.close()
    finally:
        srv.close()
        try:
            os.remove(path)
        except Exception:
            pass
    return done_n


def build_jobs(a, conf):
    chars = parse_chars(a.chars, conf.html)
    seeds = parse_seeds(a.seeds)
    pols = list(POLICIES) if a.policy == 'both' else [a.policy]
    done = set()
    for r in load_rows(a.out):
        if r.get('sig') == conf.sig and 'error' not in r:
            done.add(job_key(r['char'], r['seed'], r['policy'], r['sig']))
    jobs = []
    for s in seeds:                 # 시드 우선 — 중간에 멈춰도 캐릭터 사이가 균형 잡힌다
        for pol in pols:
            for c in chars:
                if job_key(c, s, pol, conf.sig) not in done:
                    jobs.append((c, s, pol))
    return jobs, len(chars) * len(seeds) * len(pols)


def cmd_run(a):
    os.makedirs(a.out, exist_ok=True)
    conf = Conf(a)
    jobs, total = build_jobs(a, conf)
    claims = os.path.join(a.out, '.claims')
    shutil.rmtree(claims, ignore_errors=True)
    print('측정 조건 %s  (이미 끝난 %d건 건너뜀 · 할 일 %d건 · 프로세스 %d개)' % (json.dumps(conf.public(), ensure_ascii=False), total - len(jobs), len(jobs), a.procs), flush=True)
    if not jobs:
        print('할 일이 없다.')
        return 0
    numbered = [(i + 1, len(jobs), c, s, p) for i, (c, s, p) in enumerate(jobs)]
    t0 = time.time()
    if a.procs <= 1:
        n = asyncio.run(worker_main(a, conf, numbered, 0))
    else:
        os.makedirs(claims, exist_ok=True)
        base = [sys.executable, os.path.abspath(__file__), 'run', '--out', a.out, '--chars', a.chars, '--seeds', a.seeds, '--policy', a.policy, '--cap', str(a.cap),
                '--dt', str(a.dt), '--view', a.view, '--html', a.html, '--procs', '1', '--worker-of', str(a.procs), '--no-clear']
        if a.low:
            base.append('--low')
        if a.quiet:
            base.append('--quiet')
        if a.trace:
            base.append('--trace')
        for kv in a.param:
            base += ['--param', kv]
        ps = [subprocess.Popen(base + ['--wid', str(i)], cwd=ROOT) for i in range(a.procs)]
        rc = [p.wait() for p in ps]
        n = len(load_rows(a.out))
        if any(rc):
            print('일꾼 종료 코드', rc)
    print('끝: %.0f초' % (time.time() - t0), flush=True)
    return 0


def cmd_worker(a):
    """--procs>1 일 때 부모가 띄우는 일꾼(claims 로 일감을 나눠 갖는다)."""
    conf = Conf(a)
    jobs, total = build_jobs(a, conf)
    numbered = [(i + 1, len(jobs), c, s, p) for i, (c, s, p) in enumerate(jobs)]
    asyncio.run(worker_main(a, conf, numbered, a.wid))
    return 0


# ---------------------------------------------------------------------------------------------------------------
# 집계
# ---------------------------------------------------------------------------------------------------------------
INF = 1e9


def quant(v, q):
    v = sorted(v)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    pos = (len(v) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def med(v):
    return quant(v, .5)


def at_min(row, m, fld):
    """m분 시점 값. 그 전에 죽었으면 마지막 값을 이어 쓴다(처치·레벨은 멈추고 HP 는 0). 상한(cap)이 m분보다 짧으면 None."""
    v = row.get('%s%d' % (fld, m))
    if v is not None:
        return v
    if row.get('dead') and row['end_t'] < m * 60:
        return {'k': row['kills'], 'lv': row['lv'], 'hp': 0.0}[fld]
    return None


# (키, 이름, 높을수록 좋은가, 값 함수)
METRICS = [
    ('surv', '생존 시간(초)', True, lambda r: r['end_t']),
    ('k5', '처치 @5분', True, lambda r: at_min(r, 5, 'k')),
    ('k10', '처치 @10분', True, lambda r: at_min(r, 10, 'k')),
    ('k15', '처치 @15분', True, lambda r: at_min(r, 15, 'k')),
    ('lv10', '레벨 @10분', True, lambda r: at_min(r, 10, 'lv')),
    ('lvend', '마지막 레벨', True, lambda r: r['lv']),
    ('hp10', '남은 HP비율 @10분', True, lambda r: at_min(r, 10, 'hp')),
    ('t_lv5', 'Lv5 도달(초)', False, lambda r: (r['t_lv5'] if r.get('t_lv5') is not None else INF)),
    ('t_lv10', 'Lv10 도달(초)', False, lambda r: (r['t_lv10'] if r.get('t_lv10') is not None else INF)),
    ('dmg5', '첫 5분 받은 피해', False, lambda r: r['dmg5']),
    ('min_hp', '최저 HP비율', True, lambda r: r['min_hp']),
    ('dealt', '준 피해 합(유효)', True, lambda r: r['dealt']),
]


def fmtv(x, key=None):
    if x is None:
        return '-'
    if x >= INF / 2:
        return '못 감'
    if key in ('hp10', 'min_hp'):
        return '%.2f' % x
    if abs(x) >= 100:
        return '%.0f' % x
    return '%.1f' % x


def pick_group(rows, a):
    """여러 조건이 섞여 있으면 가장 줄이 많은 (조건 서명, 정책) 묶음을 쓴다."""
    rows = [r for r in rows if 'error' not in r]
    if a.sig:
        rows = [r for r in rows if r.get('sig') == a.sig]
    if a.policy and a.policy != 'any':
        rows = [r for r in rows if r.get('policy') == a.policy]
    groups = {}
    for r in rows:
        groups.setdefault((r.get('sig'), r.get('policy')), []).append(r)
    if not groups:
        return [], None, {}
    best = max(groups, key=lambda k: len(groups[k]))
    return groups[best], best, {k: len(v) for k, v in groups.items()}


def aggregate(rows, chars_order):
    by = {}
    for r in rows:
        by.setdefault(r['char'], {})[r['seed']] = r        # 같은 (캐릭터, 시드)가 둘이면 나중 것
    chars = [c for c in chars_order if c in by] + [c for c in by if c not in chars_order]
    return by, chars


def bootstrap_diff(by, chars, focus, metric_fn, B, rng):
    """focus 중앙값 − 나머지 캐릭터 중앙값들의 중앙값(로스터 중앙값). 시드를 짝지어 다시 뽑는다."""
    vals = {c: {s: metric_fn(r) for s, r in by[c].items()} for c in chars}
    for c in chars:
        vals[c] = {s: v for s, v in vals[c].items() if v is not None}
    others = [c for c in chars if c != focus and vals[c]]
    if focus not in vals or not vals[focus] or not others:
        return None
    common = sorted(set.intersection(*[set(vals[c]) for c in [focus] + others]))
    paired = len(common) >= 3
    pt = med(list(vals[focus].values())) - med([med(list(vals[c].values())) for c in others])
    diffs = []
    for _ in range(B):
        if paired:
            idx = [common[rng.randrange(len(common))] for _ in common]
            fm = med([vals[focus][s] for s in idx])
            om = med([med([vals[c][s] for s in idx]) for c in others])
        else:
            fv = list(vals[focus].values())
            fm = med([fv[rng.randrange(len(fv))] for _ in fv])
            om = []
            for c in others:
                cv = list(vals[c].values())
                om.append(med([cv[rng.randrange(len(cv))] for _ in cv]))
            om = med(om)
        diffs.append(fm - om)
    diffs.sort()
    return {'diff': pt, 'lo': quant(diffs, .025), 'hi': quant(diffs, .975), 'p_below': sum(1 for d in diffs if d < 0) / len(diffs), 'paired': paired, 'n_seeds': len(common) if paired else None}


def cmd_report(a):
    rows_all = load_rows(a.out)
    rows, grp, groups = pick_group(rows_all, a)
    if not rows:
        print('집계할 줄이 없다(--out %s).' % a.out)
        return 1
    chars_order = list_chars(a.html)
    by, chars = aggregate(rows, chars_order)
    err_rows = [r for r in rows_all if 'error' in r]
    out = []
    P = out.append
    P('=== 캐릭터 성능 측정 집계 ===')
    P('조건 서명 %s · 정책 %s · 줄 %d개 (다른 묶음: %s)' % (grp[0], grp[1], len(rows), ', '.join('%s/%s=%d' % (k[0], k[1], v) for k, v in groups.items() if k != grp) or '없음'))
    sample = rows[0]
    P('cap %s초 · dt %s · 창 %s · LOW %s · html %s · 봇 %s' % (sample.get('cap'), sample.get('dt'), sample.get('view'), sample.get('low'), sample.get('html'), sample.get('bot')))
    P('캐릭터 %d명 · 시드 %s' % (len(chars), sorted({s for c in chars for s in by[c]})))
    if err_rows:
        P('⚠ 오류로 끝난 줄 %d개(집계 제외)' % len(err_rows))
    pe = [r for r in rows if r.get('errs')]
    if pe:
        P('⚠ 페이지 오류가 있는 줄 %d개: %s' % (len(pe), '; '.join('%s s%d %s' % (r['char'], r['seed'], r['errs'][0][:80]) for r in pe[:3])))
    P('')
    # --- 캐릭터별 표
    P('[캐릭터별 중앙값 (사분위 Q1~Q3)]  생존율 = 상한(cap)까지 안 죽은 비율. 죽기 전에 끝난 판의 처치·레벨은 마지막 값을 이어 쓴다.')
    hdr = ['캐릭터', 'n', '생존율', '생존 시간(초)', '처치@5', '처치@10', '처치@15', 'Lv@10', '마지막Lv', 'Lv5(초)', 'Lv10(초)', '첫5분 피해', '최저HP']
    P('  ' + ' | '.join(hdr))
    keys = ['surv', 'k5', 'k10', 'k15', 'lv10', 'lvend', 't_lv5', 't_lv10', 'dmg5', 'min_hp']
    table = {}
    for c in chars:
        rs = list(by[c].values())
        surv = sum(1 for r in rs if not r['dead']) / len(rs)
        cells = {}
        for key, nm, hib, fn in METRICS:
            v = [fn(r) for r in rs]
            v = [x for x in v if x is not None]
            cells[key] = {'n': len(v), 'med': med(v), 'q1': quant(v, .25), 'q3': quant(v, .75), 'mean': (sum(v) / len(v) if v and all(x < INF / 2 for x in v) else None)}
        table[c] = {'n': len(rs), 'survive_rate': surv, 'metrics': cells}
        def cell(k):
            m = cells[k]
            if m['med'] is None:
                return '-'
            return '%s (%s~%s)' % (fmtv(m['med'], k), fmtv(m['q1'], k), fmtv(m['q3'], k))
        P('  %-5s | %d | %3.0f%% | %s' % (c, len(rs), surv * 100, ' | '.join(cell(k) for k in ['surv', 'k5', 'k10', 'k15', 'lv10', 'lvend', 't_lv5', 't_lv10', 'dmg5', 'min_hp'])))
    P('')
    # --- 지표별 순위표
    P('[지표별 순위표]  (중앙값 기준 · 1위가 좋은 쪽 · ◀ = %s)' % (a.focus or '-'))
    ranks = {}
    for key, nm, hib, fn in METRICS:
        items = [(c, table[c]['metrics'][key]['med']) for c in chars if table[c]['metrics'][key]['med'] is not None]
        items.sort(key=lambda x: (-x[1] if hib else x[1], x[0]))
        ranks[key] = {c: i + 1 for i, (c, _) in enumerate(items)}
        P('  %-16s ' % nm + ' > '.join('%s %s%s' % (c, fmtv(v, key), '◀' if c == a.focus else '') for c, v in items))
    P('')
    # --- 포커스 대 로스터
    result = {'group': {'sig': grp[0], 'policy': grp[1]}, 'per_char': table, 'ranks': ranks}
    if a.focus:
        if a.focus not in by:
            P('(--focus %s 의 줄이 없다)' % a.focus)
        else:
            rng = random.Random(20261009)
            P('[%s 대 로스터 중앙값 차이]  로스터 중앙값 = 나머지 캐릭터들 각자의 중앙값의 중앙값. 부트스트랩 %d회(시드를 짝지어 다시 뽑기) · 95%% 신뢰구간.' % (a.focus, a.boot))
            P('  지표              | %s 중앙값 | 로스터 중앙값 | 차이 [95%% 신뢰구간]            | 순위 | 차이<0 확률' % a.focus)
            fvs = {}
            for key, nm, hib, fn in METRICS:
                bd = bootstrap_diff(by, chars, a.focus, fn, a.boot, rng)
                if not bd:
                    continue
                fm = table[a.focus]['metrics'][key]['med']
                others = [table[c]['metrics'][key]['med'] for c in chars if c != a.focus and table[c]['metrics'][key]['med'] is not None]
                rm = med(others)
                good = (bd['lo'] > 0 and hib) or (bd['hi'] < 0 and not hib)
                bad = (bd['hi'] < 0 and hib) or (bd['lo'] > 0 and not hib)
                verdict = '유의하게 좋음' if good else '유의하게 나쁨' if bad else '차이 불확실'
                P('  %-16s | %9s | %12s | %s [%s ~ %s] | %2d/%d | %.2f  %s' % (nm, fmtv(fm, key), fmtv(rm, key), fmtv(bd['diff'], key), fmtv(bd['lo'], key), fmtv(bd['hi'], key),
                                                                         ranks[key].get(a.focus, 0), len(ranks[key]), bd['p_below'], verdict))
                fvs[key] = {'focus_med': fm, 'roster_med': rm, 'diff': bd['diff'], 'lo': bd['lo'], 'hi': bd['hi'], 'rank': ranks[key].get(a.focus), 'of': len(ranks[key]), 'verdict': verdict, 'paired': bd['paired']}
            result['focus'] = {'char': a.focus, 'vs_roster': fvs}
    txt = '\n'.join(out)
    print(txt)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print('JSON 저장:', a.json)
    return 0


# ---------------------------------------------------------------------------------------------------------------
# 점검: smoke · determinism
# ---------------------------------------------------------------------------------------------------------------
async def _one_off(conf, jobs, say=None):
    from playwright.async_api import async_playwright
    pid = os.getpid()
    name = 'survivors_cb_%d.html' % pid
    path = H.make_copy(src=conf.html, dst=name, extra='\n' + EXTRA_HOOK)
    srv = H.Srv()
    srv.httpd.handle_error = lambda *x: None
    rows = []
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            for (c, s, pol) in jobs:
                r = await run_one(b, srv, name, conf, c, s, pol, say)
                r.update(conf.public())
                rows.append(r)
                if say:
                    say('  %-5s 시드%d %s: %s %.0f초 · 처치 %s · Lv%s · %.1f초%s' % (c, s, pol, 'ERROR ' + r['error'] if 'error' in r else ('사망' if r['dead'] else '생존'), r.get('end_t', 0), r.get('kills'), r.get('lv'), r['wall_s'], ' · 페이지오류 %s' % r['errs'][:1] if r['errs'] else ''))
            await b.close()
    finally:
        srv.close()
        try:
            os.remove(path)
        except Exception:
            pass
    return rows


def cmd_smoke(a):
    a.cap = a.cap if a.cap is not None else 300
    conf = Conf(a)
    chars = parse_chars(a.chars, conf.html)
    print('smoke: %d명 × 시드 %d × %s초' % (len(chars), a.seed, conf.cap), flush=True)
    rows = asyncio.run(_one_off(conf, [(c, a.seed, a.policy) for c in chars], lambda s: print(s, flush=True)))
    bad = [r for r in rows if 'error' in r or r['errs']]
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, 'smoke.jsonl'), 'w', encoding='utf-8') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('smoke 결과: %d/%d 에러 없이 끝남' % (len(rows) - len(bad), len(rows)))
    return 0 if not bad else 1


def cmd_determinism(a):
    a.cap = a.cap if a.cap is not None else 180
    conf = Conf(a)
    c = a.char
    jobs = [(c, 1, a.policy), (c, 1, a.policy), (c, 2, a.policy)]
    rows = asyncio.run(_one_off(conf, jobs, lambda s: print(s, flush=True)))
    keyf = lambda r: json.dumps({k: r.get(k) for k in ('end_t', 'kills', 'lv', 'hits', 'dmg_taken', 'dealt', 'k3', 'weapons', 'series')}, sort_keys=True)
    same = keyf(rows[0]) == keyf(rows[1])
    diff = keyf(rows[0]) != keyf(rows[2])
    print('같은 시드 두 번 동일: %s · 다른 시드는 다름: %s' % (same, diff))
    if not same:
        print(keyf(rows[0])[:400]); print(keyf(rows[1])[:400])
    return 0 if (same and diff) else 1


def cmd_selftest(a):
    """집계 로직 점검 — 합성 데이터로 (1) 중앙값·사분위 (2) 이어 쓰기 규칙 (3) 부트스트랩 신뢰구간이 맞게 나오는지. 브라우저 안 씀."""
    rng = random.Random(7)
    ok_all = True

    def check(name, ok, info=''):
        nonlocal ok_all
        print(('PASS' if ok else 'FAIL'), name, ('' if ok else ' ← ' + str(info)))
        ok_all = ok_all and ok

    def mk(char, seed, surv, k5):
        dead = surv < 900
        r = {'char': char, 'seed': seed, 'policy': 'full', 'end_t': float(surv), 'dead': dead, 'kills': int(k5 * surv / 300), 'lv': int(surv / 12), 'cap': 900.0,
             'k5': int(k5) if surv >= 300 else None, 'k10': None, 'k15': None, 'k3': None, 'lv5': None, 'lv10': None, 'lv15': None, 'lv3': None,
             'hp3': None, 'hp5': None, 'hp10': None, 'hp15': None, 't_lv5': 45.0, 't_lv10': 95.0, 'dmg5': 100.0, 'min_hp': 0.0, 'dealt': 1000}
        return r
    chars = ['a', 'b', 'c', 'd', 'e', 'f']

    def build(offset):
        rows = []
        for c in chars:
            for sd in range(1, 41):
                base = 600 + rng.gauss(0, 120)
                if c == 'a':
                    base += offset
                rows.append(mk(c, sd, max(60, min(900, base)), 1000 + rng.gauss(0, 100)))
        return rows
    for label, off, want in (('같은 분포', 0, 'include0'), ('a 가 150초 나쁨', -150, 'neg'), ('a 가 150초 좋음', 150, 'pos')):
        rows = build(off)
        by, ch = aggregate(rows, chars)
        fn = [m for m in METRICS if m[0] == 'surv'][0][3]
        bd = bootstrap_diff(by, ch, 'a', fn, 600, random.Random(1))
        if want == 'include0':
            check('[%s] 신뢰구간이 0을 품는다 (%.0f [%.0f~%.0f])' % (label, bd['diff'], bd['lo'], bd['hi']), bd['lo'] < 0 < bd['hi'], bd)
        elif want == 'neg':
            check('[%s] 차이가 음수이고 구간이 0 아래 (%.0f [%.0f~%.0f])' % (label, bd['diff'], bd['lo'], bd['hi']), bd['hi'] < 0 and -250 < bd['diff'] < -60, bd)
        else:
            check('[%s] 차이가 양수이고 구간이 0 위 (%.0f [%.0f~%.0f])' % (label, bd['diff'], bd['lo'], bd['hi']), bd['lo'] > 0 and 60 < bd['diff'] < 250, bd)
    # 이어 쓰기 규칙: 5분 전에 죽으면 처치 = 마지막 처치, 상한이 짧으면 None
    r = {'dead': True, 'end_t': 200.0, 'kills': 77, 'lv': 9, 'k5': None, 'lv5': None, 'hp5': None}
    check('5분 전에 죽으면 처치@5 = 마지막 처치', at_min(r, 5, 'k') == 77 and at_min(r, 5, 'lv') == 9 and at_min(r, 5, 'hp') == 0.0, at_min(r, 5, 'k'))
    r2 = {'dead': False, 'end_t': 120.0, 'kills': 30, 'lv': 4, 'k5': None}
    check('상한이 5분보다 짧으면 처치@5 = None', at_min(r2, 5, 'k') is None)
    check('분위수', quant([1, 2, 3, 4, 5], .25) == 2 and med([1, 2, 3, 4]) == 2.5 and med([]) is None)
    print('selftest', '통과' if ok_all else '실패')
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser(description='흐접새우 서바이벌 캐릭터 성능 측정기')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--cap', type=float, default=None, help='판 상한(초). 기본 900 = 15분')
        p.add_argument('--dt', type=float, default=1 / 30, help='update 한 번의 시간(초). 기본 1/30')
        p.add_argument('--view', default='1280x720', help='창 크기. 기본 1280x720(PC)')
        p.add_argument('--low', action='store_true', help='폰/약한 기기 조건(LOW: 적 상한 140)')
        p.add_argument('--html', default='survivors.html', help='측정할 survivors 파일(저장소 루트 기준). 기본 survivors.html')
        p.add_argument('--policy', default='full', help='full | sigonly (run 은 both 도 가능)')
        p.add_argument('--quiet', action='store_true', help='진행 줄을 줄인다')
        p.add_argument('--param', action='append', default=[], metavar='KEY=VAL', help='정책 상수 덮어쓰기(민감도 점검). 예: --param MOVE.nearMargin=60 --param CARD.passive.arm=90')
        p.add_argument('--trace', action='store_true', help='결과 줄에 2초마다 궤적·피격 기록을 붙인다(디버깅용 · 줄이 커진다)')

    r = sub.add_parser('run', help='측정 돌리기(중단 후 이어서 가능)')
    common(r)
    r.add_argument('--out', required=True, help='결과 폴더(runs.*.jsonl 이 쌓인다)')
    r.add_argument('--chars', default='all', help='all 또는 쉼표 목록(예: eom,brj)')
    r.add_argument('--seeds', default='1-4', help='예: 1-8 또는 1,2,5')
    r.add_argument('--procs', type=int, default=1, help='프로세스 수 1~3')
    r.add_argument('--wid', type=int, default=0, help=argparse.SUPPRESS)
    r.add_argument('--worker-of', type=int, default=0, help=argparse.SUPPRESS)
    r.add_argument('--no-clear', action='store_true', help=argparse.SUPPRESS)

    rp = sub.add_parser('report', help='집계')
    rp.add_argument('--out', required=True)
    rp.add_argument('--focus', default='eom', help='로스터와 비교할 캐릭터. 기본 eom')
    rp.add_argument('--policy', default='full', help='집계할 정책(any 면 가장 많은 묶음)')
    rp.add_argument('--sig', default=None, help='조건 서명(여러 조건이 섞여 있을 때)')
    rp.add_argument('--boot', type=int, default=2000, help='부트스트랩 횟수')
    rp.add_argument('--json', default=None, help='집계를 JSON 으로도 저장')
    rp.add_argument('--html', default='survivors.html')

    s = sub.add_parser('smoke', help='전 캐릭터 한 판씩(기본 시드1, 300초) 에러 없이 도는지')
    common(s)
    s.add_argument('--chars', default='all')
    s.add_argument('--seed', type=int, default=1)
    s.add_argument('--out', default=None)

    sub.add_parser('selftest', help='집계 로직 점검(합성 데이터 · 브라우저 안 씀)')

    d = sub.add_parser('determinism', help='같은 시드 두 번 동일 · 다른 시드는 다름')
    common(d)
    d.add_argument('--char', default='brj')

    a = ap.parse_args()
    if a.cmd == 'run':
        if a.cap is None:
            a.cap = 900
        a.procs = max(1, min(3, a.procs))
        if a.policy not in POLICIES + ('both',):
            sys.exit('--policy 는 full | sigonly | both')
        if a.worker_of:
            return cmd_worker(a)
        return cmd_run(a)
    if a.cmd == 'report':
        return cmd_report(a)
    if a.cmd == 'selftest':
        return cmd_selftest(a)
    if a.cmd == 'smoke':
        return cmd_smoke(a)
    return cmd_determinism(a)


if __name__ == '__main__':
    sys.exit(main())
