# -*- coding: utf-8 -*-
"""🧮 흐접새우 서바이벌 「규칙 불변」 증명 도구 — 두 survivors.html 을 같은 시드·같은 조건에서 정책 봇으로 돌려 결과가 비트까지 같은지 본다.
   「표시만 바꿨다」(화면 글·도우미 함수 정리·시험 훅 등)는 약속을 말이 아니라 숫자로 지키려고 만든다. 규칙·수치·난수를 바꾼 변경에는 당연히 다르게 나온다.

   무엇을 견주나(판 하나마다)
     · 정책 봇 측정기(tests/survivors_charbal_sim.py)의 결과 줄 전체 — 종료 시각 · 처치 · 레벨 · 받은 피해 · 무기/패시브 구성 · 분당 곡선 · 보스 …
     · 판이 끝난 직후의 게임 상태 해시 — S(무기·패시브·거래·유물·피해 비중 …) + 살아 있는 적·경험치 보석·아이템의 좌표·체력을 전정밀도로 이어 붙인 문자열의 해시
     · 그 직후 뽑은 다음 난수 값(난수를 한 번이라도 더/덜 썼으면 여기서 갈린다)
   사용 예
     # 기준 커밋과 지금 작업본: 캐릭터 4명 × 시드 2개 × 240초 × 일반·하드·베리하드
     nice -n 10 python3 tests/survivors_equiv.py --a bfaaf08 --b survivors.html --chars brj,kyo,eom,yj --seeds 1-2 --cap 240 --modes n,h,v
     # 브랜치 둘(합치기 전·후) 견주기:  --a surv-finboss --b merged-branch
   A·B 는 파일 경로이거나 git 리비전(리비전이면 --file 의 파일을 그 시점에서 꺼낸다). 두 판이 같으면 종료코드 0.
   브라우저는 A·B 각각 하나씩(동시에 2개)만 쓴다. 임시 사본은 survivors_cb_<pid>.html(.gitignore 대상) — 끝나면 지운다."""
import argparse, asyncio, json, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
import survivors_charbal_sim as sim
ROOT = H.ROOT
VOLATILE = {'wall_s', 'html', 'sig', 'bot'}      # 실행 시간·파일 해시는 당연히 다르다

DIGEST_JS = r"""()=>{const x=__p6x,S=x.S,p=S.p;const parts=[];
 parts.push(S.t,S.kills,S.lv,S.xp,S.need,S.pendingLv,p.x,p.y,p.hp,p.mhp,p.inv,S.rr,S.ban,S.rg||0,S.shield,S.stillT,S.leechT,S.vk,S.hc,S.sgC);
 for(const e of x.enemies.a){if(!e.on)continue;parts.push('e',e.ki,e.x,e.y,e.hp,e.mhp,e.dmg,e.sp,e.sn,e.boss||0,e.el||0,e.bg||0);}
 for(const g of x.gems.a){if(!g.on)continue;parts.push('g',g.x,g.y,g.v);}
 for(const g of x.items.a){if(!g.on)continue;parts.push('i',g.x,g.y,g.k);}
 parts.push('S',JSON.stringify(S.w),JSON.stringify(S.ps),JSON.stringify(S.ev),JSON.stringify(S.tier),JSON.stringify(S.rel),JSON.stringify(S.tr),JSON.stringify(S.sm),JSON.stringify(S.pt),JSON.stringify(S.dmgBy),JSON.stringify(S.mhpBy||null),S.hard?1:0,S.vh?1:0);
 const f=v=>typeof v==='number'?(Object.is(v,-0)?'-0':String(v)):String(v);
 const str=parts.map(f).join('|');let h=0x811c9dc5;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,0x01000193)>>>0;}
 return {h,len:str.length,rnd:Math.random(),t:S.t,kills:S.kills,hard:!!S.hard,vh:!!S.vh};}"""
# 난이도는 첫 화면 체크박스가 읽는 저장 키(p6_hard · p6_vh)로 고른다 — 판 시작 코드는 그대로 쓴다
MODE_JS = {'n': "try{localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','0');}catch(e){}",
           'h': "try{localStorage.setItem('p6_hard','1');localStorage.setItem('p6_vh','0');}catch(e){}",
           'v': "try{localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','1');}catch(e){}"}
MODE_NAME = {'n': '일반', 'h': '하드', 'v': '베리하드'}

async def run_one(browser, srv, page_name, conf, char, seed, policy, say=None):
    """sim.run_one 과 같되, 끝난 직후의 게임 상태 해시·다음 난수를 붙인다."""
    t0 = time.time()
    ctx = await browser.new_context(viewport={'width': conf.view[0], 'height': conf.view[1]}, screen={'width': conf.view[0], 'height': conf.view[1]})
    errs, row = [], {'char': char, 'seed': seed, 'policy': policy}
    try:
        await ctx.add_init_script(sim.INIT_JS % {'seed': 0x5eed0000 ^ seed, 'hc': 4 if conf.low else 8})
        base = 'http://127.0.0.1:%d/' % srv.port
        async def route(r):
            if r.request.url.startswith(base): await r.continue_()
            else: await r.abort()
        await ctx.route('**/*', route)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        await pg.goto(base + page_name)
        await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined', polling=50, timeout=60000)
        await pg.add_script_tag(content=open(sim.BOT_JS, encoding='utf-8').read())
        # 판이 끝나는 바로 그 호출 안에서 상태 해시·다음 난수를 잰다 — 사망 뒤 결과 화면이 띄우는 비동기 일(네트워크 실패 처리 등)이 난수를 더 쓰기 전에
        await pg.evaluate('(()=>{const DIG=' + DIGEST_JS + ';const o=window.__cb.run;window.__cb.run=function(a){const r=o.call(this,a);if(r&&r.done&&!r.digest)r.digest=DIG();return r;};})()')
        row['info'] = await pg.evaluate('c=>__cb.init(c)', {'char': char, 'seed': seed, 'policy': policy, 'cap': conf.cap, 'dt': conf.dt, 'params': conf.params, 'trace': conf.trace})
        while True:
            r = await pg.evaluate('()=>__cb.run({maxMs:3000})')
            if r['done']:
                row.update(r['row']); row['digest'] = r.get('digest'); break
            if time.time() - t0 > 3600: raise RuntimeError('한 판이 60분을 넘김')
    except Exception as e:
        row['error'] = str(e)[:400]
    finally:
        try: await ctx.close()
        except Exception: pass
    row['errs'] = errs; row['wall_s'] = round(time.time() - t0, 1)
    return row

def child(a):
    """한쪽 사본만 돌려 결과 줄을 파일에 쓴다(부모가 A·B 를 동시에 하나씩 띄운다)."""
    sim.INIT_JS = sim.INIT_JS.replace("try{localStorage.setItem('p6_fx','0');}catch(e){}", "try{localStorage.setItem('p6_fx','0');}catch(e){}" + MODE_JS[a.mode])
    assert MODE_JS[a.mode] in sim.INIT_JS, '측정기의 초기화 스크립트가 바뀌었다 — 난이도 주입 자리를 못 찾음'
    sim.run_one = run_one
    ns = argparse.Namespace(cap=a.cap, dt=1 / 30, view=a.view, low=False, html=a.html, policy='full', param=[], trace=False)
    conf = sim.Conf(ns)
    chars, seeds = sim.parse_chars(a.chars, a.html), sim.parse_seeds(a.seeds)
    jobs = [(c, s, 'full') for s in seeds for c in chars]
    rows = asyncio.run(sim._one_off(conf, jobs, None))
    with open(a.out, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n')
    return 0

def materialize(spec, fname, d, tag):
    """파일 경로면 그대로, 아니면 git 리비전으로 보고 그 시점의 fname 을 d 안에 꺼낸다."""
    if os.path.isfile(spec): return os.path.abspath(spec)
    if os.path.isfile(os.path.join(ROOT, spec)): return os.path.join(ROOT, spec)
    out = subprocess.run(['git', '-C', ROOT, 'show', '%s:%s' % (spec, fname)], capture_output=True)
    if out.returncode: sys.exit('「%s」는 파일도 git 리비전도 아니다: %s' % (spec, out.stderr.decode('utf-8', 'replace')[:200]))
    p = os.path.join(d, 'survivors_equiv_%s.html' % tag); open(p, 'wb').write(out.stdout); return p

def load(p):
    d = {}
    for ln in open(p, encoding='utf-8'):
        ln = ln.strip()
        if ln:
            r = json.loads(ln); d[(r['char'], r['seed'])] = r
    return d

def main():
    ap = argparse.ArgumentParser(description='두 survivors.html 이 같은 시드에서 비트까지 같은 판을 내는지(규칙 불변 증명)')
    ap.add_argument('--a'); ap.add_argument('--b')
    ap.add_argument('--file', default='survivors.html', help='리비전일 때 꺼낼 파일')
    ap.add_argument('--chars', default='brj,kyo,eom,yj'); ap.add_argument('--seeds', default='1-2')
    ap.add_argument('--cap', type=float, default=240); ap.add_argument('--modes', default='n,h,v', help='n 일반 · h 하드 · v 베리하드(쉼표)')
    ap.add_argument('--view', default='1280x720')
    ap.add_argument('--child', action='store_true', help=argparse.SUPPRESS); ap.add_argument('--html'); ap.add_argument('--mode', default='n'); ap.add_argument('--out')
    a = ap.parse_args()
    if a.child: return child(a)
    if not (a.a and a.b): ap.error('--a 와 --b 가 필요하다')
    modes = [m for m in a.modes.split(',') if m]
    tmp = tempfile.mkdtemp(prefix='svequiv_')
    pa, pb = materialize(a.a, a.file, tmp, 'A'), materialize(a.b, a.file, tmp, 'B')
    print('A = %s\nB = %s' % (pa, pb), flush=True)
    tot = same = 0
    try:
        for m in modes:
            outs, ps = {}, {}
            for tag, path in (('A', pa), ('B', pb)):
                outs[tag] = os.path.join(tmp, '%s_%s.jsonl' % (tag, m))
                ps[tag] = subprocess.Popen([sys.executable, os.path.abspath(__file__), '--child', '--html', path, '--mode', m, '--chars', a.chars, '--seeds', a.seeds, '--cap', str(a.cap), '--view', a.view, '--out', outs[tag]],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            rc = {t: p.wait() for t, p in ps.items()}
            if any(rc.values()):
                print('✗ [%s] 한쪽이 비정상 종료: %s\n%s' % (MODE_NAME[m], rc, ' / '.join(p.stderr.read().decode('utf-8', 'replace')[-400:] for p in ps.values())), flush=True)
                tot += 1; continue
            ra, rb = load(outs['A']), load(outs['B'])
            for k in sorted(set(ra) | set(rb)):
                tot += 1
                if k not in ra or k not in rb: print('✗ [%s] %s 시드%d: 한쪽에만 결과가 있다' % (MODE_NAME[m], k[0], k[1]), flush=True); continue
                xa = {f: v for f, v in ra[k].items() if f not in VOLATILE}; xb = {f: v for f, v in rb[k].items() if f not in VOLATILE}
                if xa == xb and 'error' not in xa and not xa.get('errs'):
                    same += 1; d = xa.get('digest') or {}
                    print('✔ [%s] %-5s 시드%-2d 같다 — %6.1f초 %s · 처치 %5d · Lv%-3d · 받은 피해 횟수 %4d · 상태 해시 %08x(%d자) · 다음 난수 %.17g' % (
                        MODE_NAME[m], k[0], k[1], xa.get('end_t', 0), '사망' if xa.get('dead') else '생존', xa.get('kills', 0), xa.get('lv', 0), xa.get('hits', 0), d.get('h', 0), d.get('len', 0), d.get('rnd', 0)), flush=True)
                else:
                    diff = [f for f in sorted(set(xa) | set(xb)) if xa.get(f) != xb.get(f)]
                    print('✗ [%s] %s 시드%d 다르다 — 다른 칸: %s · 오류 A=%s B=%s' % (MODE_NAME[m], k[0], k[1], diff[:10], (xa.get('errs') or xa.get('error')), (xb.get('errs') or xb.get('error'))), flush=True)
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
    print('\n합계 %d판 중 같음 %d' % (tot, same), flush=True)
    return 0 if tot and tot == same else 1

if __name__ == '__main__':
    sys.exit(main())
