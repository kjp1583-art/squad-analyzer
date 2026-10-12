# -*- coding: utf-8 -*-
"""⚔ 최종 보스 1:1 난이도 측정기 — 「평범한 빌드가 집중하면 한두 번 실패 끝에 깰 정도」(사장님 지시 2026-10-12)를 대략 재는 도구.

정책 봇(survivors_charbal_bot.js)은 회피를 못 해서 1:1 난이도를 잴 수 없다. 그래서
  ① 신(god) 모드 정책 봇으로 55분 직전까지 돌려 「평범한 빌드」를 얻고(build 서브명령 · 한 번에 3~6분) → JSON 스냅샷으로 저장,
  ② 그 빌드를 새 판(55:00 직전)에 얹어 1:1 만 돌린다(run 서브명령 · 한 판 1분 안팎): 이동은 회피 휴리스틱 봇(survivors_finduel_bot.js), 카드는 정책 봇의 고르기.
한계: 회피 봇은 사람이 아니다(반응 0.3초 · 0.1초마다 방향 · 탐욕 한 걸음). 빌드는 정책 봇이 자기 손으로 만든 것이라 「평범」의 기준이 느슨하다.
        봇이 잘 피하면 쉽게, 못 피하면 어렵게 나온다 — sloppy(헛발질 비율)를 바꿔 가며 「사람 폭」을 본다. 절대 난이도 판정이 아니라 설계가 터무니없지 않은지 보는 용도.
사용
  python3 tests/survivors_finduel_sim.py build --char brj --seed 1 --out /tmp/snap_brj1.json
  python3 tests/survivors_finduel_sim.py run --snap /tmp/snap_brj1.json --seeds 1-6 --modes n,h,v --sloppy 0,0.4
  python3 tests/survivors_finduel_sim.py equiv --a <1:1 이전 리비전> --b survivors.html --char brj --cap 3290   # 55분 직전까지 기준과 비트 동일(신 모드 정책 봇) — 기준은 이 변경의 부모 커밋(origin/main 은 다른 세션이 앞서 갈 수 있다)
  (임시 사본 survivors_fdsim_<pid>.html 은 .gitignore 대상 · 끝나면 지운다 · 브라우저는 한 번에 하나)
"""
import argparse, asyncio, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
import survivors_charbal_sim as sim
from playwright.async_api import async_playwright

ROOT = H.ROOT
BOT = os.path.join(HERE, 'survivors_finduel_bot.js')
FD_HOOK = r"""
window.__fd={get F(){return FIN_DUEL},get D(){return duelBoss()},dzHit,duelBoss,capHit,eshots,get FIN(){return FIN_DUEL},att:[]};
// 「닿은 횟수」 — 막기(냄비뚜껑·방어막)가 막아 준 것도 센다(막기 빌드는 받은 피해만 보면 쉬워 보인다). 무적 중에 닿은 것은 세지 않는다.
{const h0=hitP;hitP=function(d,m){const inv=S.p.inv>0,t=S.t;const r=h0.apply(this,arguments);if(!inv)window.__fd.att.push([+t.toFixed(2),Math.round(d),m||'']);return r;};}
"""
GOD = r"""
{const x=window.__p6x,u0=x.update;x.update=function(dt){if(window.__god&&S&&S.p&&S.p.hp>0)S.p.hp=S.p.mhp;return u0.call(this,dt);};}
"""
MODE_JS = {'n': "try{localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','0');}catch(e){}",
           'h': "try{localStorage.setItem('p6_hard','1');localStorage.setItem('p6_vh','0');}catch(e){}",
           'v': "try{localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','1');}catch(e){}"}
MODE_NAME = {'n': '일반', 'h': '하드', 'v': '베리하드'}

SNAP_JS = """()=>{const X=window.__p6x,S=X.S,p=S.p;const o={};for(const k of ['w','ev','tier','ps','pt','rel','tr','sm','lv','banned'])o[k]=JSON.parse(JSON.stringify(S[k]));o.mhp=p.mhp;o.sp=p.sp;o.ch=X.CH.k;return o}"""

LOAD_JS = """(snap)=>{const X=window.__p6x;X.CH_set(snap.ch);X.start();const S=X.S;
  for(const k of ['w','ev','tier','ps','pt','rel','tr','sm'])S[k]=JSON.parse(JSON.stringify(snap[k]));
  S.lv=snap.lv;S.banned=snap.banned||[];S.p.mhp=snap.mhp;S.p.hp=snap.mhp;X.tkCalc();X.synCalc();S.x2.lt=S.w.lid?S.tk.lid:null;
  S.t=3299.4;S.nextBoss=3300;S.nextMini=Infinity;S.nextSp=Infinity;S.bossN=10;S.midKill=1;
  return {mhp:S.p.mhp,sp:S.p.sp,lv:S.lv,hard:!!S.hard,vh:!!S.vh}}"""

# 1:1 한 판 — 회피 봇이 움직이고 카드는 정책 봇이 고른다. 끝: 보스 처치 · 사망 · 60:00 · 제한 시간
RUN_JS = """(o)=>{const X=window.__p6x,FD=window.__fd,S=X.S,t0=performance.now();const R=window.__run=window.__run||{log:[],hit:[],ph:[0,0,0],tk:null,dead:false,start:null,steps:0};
  window.__fbot.CFG.sloppy=o.sloppy;
  for(;;){const st=X.state;
    if(st==='result'){R.res=S.won?'won':'dead';return {done:true,R};}
    if(st==='lvup'){X.pick(window.__cb.chooseCard(X.CUR));continue;}
    if(st!=='play'){X.resume();continue;}
    if(performance.now()-t0>o.maxMs)return {done:false};
    const D=FD.D;
    if(D&&R.start===null){R.start=S.t;}
    if(!D&&R.start!==null){R.res='killed';R.kill_t=S.t-R.start;return {done:true,R};}
    if(S.t>=R.start+o.limit&&R.start!==null){R.res='timeout';return {done:true,R};}
    if(D&&o.hpf<1)D.hp=Math.min(D.hp,D.mhp*o.hpf);   // 단계 고정 측정: 보스 체력을 이 비율 아래로 눌러 둔다(0.5 → 2단계 · 0.2 → 3단계)
    window.__fbot.step();
    const b=D&&D.du?D.du.ph:0;R.ph[b]+=o.dt;
    X.update(o.dt);R.steps++;
    if(R.steps%30===0&&D)R.log.push([+(S.t-R.start).toFixed(0),+(D.hp/D.mhp).toFixed(3),+(S.p.hp/S.p.mhp).toFixed(2)]);}}"""


async def new_page(b, srv, name, mode, cap_js=''):
    ctx = await b.new_context(viewport={'width': 1280, 'height': 720}, screen={'width': 1280, 'height': 720})
    base = 'http://127.0.0.1:%d/' % srv.port
    async def route(r):
        if r.request.url.startswith(base): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    return ctx, pg, errs, base


async def cmd_build(a):
    name = 'survivors_fdsim_%d.html' % os.getpid()
    path = H.make_copy(a.html, name, extra='\n' + sim.EXTRA_HOOK + FD_HOOK + GOD)
    srv = H.Srv(); t0 = time.time()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs, base = await new_page(b, srv, name, 'n')
            await ctx.add_init_script(sim.INIT_JS % {'seed': 0x5eed0000 ^ a.seed, 'hc': 8})
            await pg.goto(base + name)
            await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined', polling=50, timeout=20000)
            await pg.add_script_tag(content=open(sim.BOT_JS, encoding='utf-8').read())
            await pg.evaluate('()=>{window.__god=1}')
            await pg.evaluate('c=>__cb.init(c)', {'char': a.char, 'seed': a.seed, 'policy': 'full', 'cap': a.cap, 'dt': 1 / 30, 'params': {}, 'trace': False})
            while True:
                r = await pg.evaluate('()=>__cb.run({maxMs:3000})')
                if r['done']: break
                print('  %s %.0f초 · 처치 %d · Lv%d (%.0f초 경과)' % (a.char, r['prog']['t'], r['prog']['k'], r['prog']['lv'], time.time() - t0), flush=True)
            row = r['row']
            print('  55분 직전 요약: 처치 %s · 레벨 %s · 최대 체력 %s · 총 준 피해 %s · 보스 %s' % (row.get('kills'), row.get('lv'), row.get('mhp'), row.get('dealt'), [(x['k'], x['fate'], x['t0'], x['t1'], x['mhp']) for x in row.get('bosses', [])]))
            snap = await pg.evaluate(SNAP_JS)
            json.dump(snap, open(a.out, 'w'), ensure_ascii=False)
            print('저장:', a.out, '· mhp', snap['mhp'], '· Lv', snap['lv'], '· 무기', snap['w'], '· 오류', errs[:2])
            await b.close()
    finally:
        srv.close()
        try: os.remove(path)
        except Exception: pass


async def one(b, srv, name, base, snap, mode, seed, sloppy, god, limit, hpf=1.0):
    ctx, pg, errs, base = await new_page(b, srv, name, mode)
    row = {'mode': mode, 'seed': seed, 'sloppy': sloppy, 'god': god}
    try:
        await ctx.add_init_script(sim.INIT_JS % {'seed': 0x5eed0000 ^ seed, 'hc': 8} + MODE_JS[mode])
        await pg.goto(base + name)
        await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined&&window.__fd!==undefined', polling=50, timeout=20000)
        await pg.add_script_tag(content=open(sim.BOT_JS, encoding='utf-8').read())
        await pg.add_script_tag(content=open(BOT, encoding='utf-8').read())
        await pg.evaluate('()=>{__cb.init({char:"brj",seed:%d,policy:"full",cap:99999,dt:1/30,params:{},trace:false})}' % seed)   # 카드 고르기만 쓴다
        row['info'] = await pg.evaluate(LOAD_JS, snap)
        await pg.evaluate('()=>{window.__god=%d;window.__cbx.dmg.taken=0;window.__cbx.dmg.hits=0;window.__cbx.dmg.by={};window.__cbx.dmg.n={}}' % (1 if god else 0))
        while True:
            r = await pg.evaluate(RUN_JS, {'sloppy': sloppy, 'maxMs': 3000, 'dt': 1 / 30, 'limit': limit, 'hpf': hpf})
            if r['done']:
                R = r['R']; break
        d = await pg.evaluate('()=>window.__cbx.dmg')
        att = await pg.evaluate('()=>window.__fd.att')
        row['att'] = len(att); row['att_dmg'] = round(sum(x[1] for x in att)); row['att_by'] = {}
        for x in att: row['att_by'][x[2] or '탄'] = row['att_by'].get(x[2] or '탄', 0) + 1
        row.update({'res': R['res'], 'kill_t': R.get('kill_t'), 'taken': round(d['taken']), 'hits': d['hits'], 'by': d['by'], 'n': d['n'], 'ph': [round(x) for x in R['ph']], 'log': R['log'][::10]})
        row['hp_end'] = R['log'][-1] if R['log'] else None
    except Exception as e:
        row['error'] = str(e)[:300]
    row['errs'] = errs
    try: await ctx.close()
    except Exception: pass
    return row


async def cmd_run(a):
    name = 'survivors_fdsim_%d.html' % os.getpid()
    path = H.make_copy(a.html, name, extra='\n' + sim.EXTRA_HOOK + FD_HOOK + GOD)
    srv = H.Srv(); snap = json.load(open(a.snap))
    seeds = [int(x) for x in a.seeds.split(',')] if ',' in a.seeds or '-' not in a.seeds else list(range(int(a.seeds.split('-')[0]), int(a.seeds.split('-')[1]) + 1))
    rows = []
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            for mode in a.modes.split(','):
                for sl in [float(x) for x in a.sloppy.split(',')]:
                    for sd in seeds:
                        r = await one(b, srv, name, '', snap, mode, sd, sl, a.god, a.limit, a.hpf)
                        rows.append(r)
                        print('%s sloppy %.1f s%d → %s · 처치까지 %s초 · 받은 피해 %s (%d번) · 닿은 %s번(%s) · 단계별 초 %s · 오류 %s' % (MODE_NAME[mode], sl, sd, r.get('res') or r.get('error'), r.get('kill_t') and round(r['kill_t']), r.get('taken'), r.get('hits', 0), r.get('att'), r.get('att_by'), r.get('ph'), r.get('errs')), flush=True)
            await b.close()
    finally:
        srv.close()
        try: os.remove(path)
        except Exception: pass
    if a.out:
        json.dump(rows, open(a.out, 'w'), ensure_ascii=False)
    return rows


async def equiv_one(b, srv, name, char, seed, cap, mode):
    ctx, pg, errs, base = await new_page(b, srv, name, mode)
    row = {}
    await ctx.add_init_script(sim.INIT_JS % {'seed': 0x5eed0000 ^ seed, 'hc': 8} + MODE_JS[mode])
    await pg.goto(base + name)
    await pg.wait_for_function('window.__p6x!==undefined&&window.__cbx!==undefined', polling=50, timeout=20000)
    await pg.add_script_tag(content=open(sim.BOT_JS, encoding='utf-8').read())
    await pg.evaluate('()=>{window.__god=1}')
    await pg.evaluate('c=>__cb.init(c)', {'char': char, 'seed': seed, 'policy': 'full', 'cap': cap, 'dt': 1 / 30, 'params': {}, 'trace': False})
    dig = None
    while True:
        r = await pg.evaluate('()=>__cb.run({maxMs:3000})')
        if r['done']: break
    import survivors_equiv as eq
    dig = await pg.evaluate('(' + eq.DIGEST_JS + ')')
    row = {k: v for k, v in r['row'].items() if k not in eq.VOLATILE}
    row['digest'] = dig
    await ctx.close()
    return row, errs


async def cmd_equiv(a):
    """신(god) 모드 정책 봇으로 55분 직전(cap)까지 돌려 기준(--a)과 지금(--b)의 판 끝 상태 해시가 비트까지 같은지 본다 — 최종 보스 등장 전 구간 불변 증명(survivors_equiv.py 는 사망하는 판이라 55분까지 못 간다)"""
    import subprocess, tempfile
    tmp = tempfile.mkdtemp(prefix='fdeq_')
    paths = {}
    for tag, spec in (('A', a.a), ('B', a.b)):
        name = 'survivors_fdsim_%d_%s.html' % (os.getpid(), tag)
        if os.path.isfile(spec) or os.path.isfile(os.path.join(ROOT, spec)):
            src = open(spec if os.path.isfile(spec) else os.path.join(ROOT, spec), encoding='utf-8').read()
        else:
            src = subprocess.run(['git', '-C', ROOT, 'show', spec + ':survivors.html'], capture_output=True, check=True).stdout.decode('utf-8')
        import re
        m = re.search(r"window\.__p6=\{[^\n]*\};", src)
        src = src.replace(m.group(0), m.group(0) + '\n' + H.HOOK + '\n' + sim.EXTRA_HOOK + GOD).replace('const INV_CAP=.80;', 'let INV_CAP=.80;')
        open(os.path.join(ROOT, name), 'w', encoding='utf-8').write(src); paths[tag] = name
    srv = H.Srv(); rows = {}
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            for mode in a.modes.split(','):
                for tag in ('A', 'B'):
                    t0 = time.time()
                    rows[tag], errs = await equiv_one(b, srv, paths[tag], a.char, a.seed, a.cap, mode)
                    print('  %s [%s] %s 시드%d %.0f초 · 처치 %s · 해시 %s · 오류 %s (%.0f초 걸림)' % (tag, MODE_NAME[mode], a.char, a.seed, rows[tag].get('end_t', 0), rows[tag].get('kills'), rows[tag]['digest']['h'], errs[:1], time.time() - t0), flush=True)
                same = rows['A'] == rows['B']
                print('%s [%s] %s 시드%d — 55분 직전까지 기준과 %s' % ('✔' if same else '✗', MODE_NAME[mode], a.char, a.seed, '비트까지 같다' if same else '다르다: ' + str([k for k in rows['A'] if rows['A'].get(k) != rows['B'].get(k)])), flush=True)
                if not same:
                    sys.exit(1)
            await b.close()
    finally:
        srv.close()
        for n in paths.values():
            try: os.remove(os.path.join(ROOT, n))
            except Exception: pass


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    e = sp.add_parser('equiv'); e.add_argument('--a', default='HEAD'); e.add_argument('--b', default='survivors.html'); e.add_argument('--char', default='brj'); e.add_argument('--seed', type=int, default=1); e.add_argument('--cap', type=float, default=3290); e.add_argument('--modes', default='n')
    b = sp.add_parser('build'); b.add_argument('--char', default='brj'); b.add_argument('--seed', type=int, default=1); b.add_argument('--cap', type=float, default=3290); b.add_argument('--out', required=True); b.add_argument('--html', default='survivors.html')
    r = sp.add_parser('run'); r.add_argument('--snap', required=True); r.add_argument('--seeds', default='1-4'); r.add_argument('--modes', default='n'); r.add_argument('--sloppy', default='0'); r.add_argument('--god', action='store_true'); r.add_argument('--limit', type=float, default=300); r.add_argument('--hpf', type=float, default=1.0); r.add_argument('--out', default=''); r.add_argument('--html', default='survivors.html')
    a = ap.parse_args()
    asyncio.run(cmd_build(a) if a.cmd == 'build' else cmd_equiv(a) if a.cmd == 'equiv' else cmd_run(a))


if __name__ == '__main__':
    main()
