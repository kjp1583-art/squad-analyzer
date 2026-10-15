# -*- coding: utf-8 -*-
"""⏩ 흐접새우 서바이벌 「2배속 on/off」 시험 — 2026-10-11 사장님 지시 "흐접새우 2배속 모드 on/off 토글추가"
   사용: python3 tests/survivors_speed2_test.py [--only 가,나,...] [--equiv] [--mutant nosecond|ignore|norecheck|nolock|noframe]
         python3 tests/survivors_speed2_test.py --mutants      (변이 3종을 돌려 가·나·다 가운데 빨강이 나는지 확인 — 전부 죽어야 종료코드 0)
   구성
     가  끈 상태 불변 — 기준 커밋(2bb6eaf) 빌드와 같은 시드·같은 입력으로 frame 을 직접 구동해 상태 해시가 비트까지 같다(--equiv 는 tests/survivors_equiv.py 도 돌린다)
     나  켠 상태 — 같은 프레임 수에서 update 호출 2배 · S.t 2배(= 호출 수 × dt, 오차 1e-6) · dt 는 키우지 않는다 · 읽는 글(배너)은 실시간 · 실제 rAF 로도 약 2배
     다  전환 — 레벨업·히트스톱·사망/결과로 state 가 play 를 벗어난 프레임에는 두 번째 update 가 안 돈다
     라  토글 — 기본 꺼짐 · 저장(p6_spd2)·새로고침 유지 · 첫 화면↔일시정지 동기 · localStorage 불가여도 메모리로 동작 · 느린 폰 안내(한 번만)
     마  화면 — 첫 화면·일시정지 단추·HUD 칩(켰을 때만) · 폰 폭 320/360/412 가로 넘침 0 · 터치 대상 40px↑
     바  이어하기 — 서명(SIG)·S 키 불변 · 켠 채 저장 → 복구 → 이어서 진행 · 옛 빌드 저장본 호환
     사  페이지 오류 0
     아  구매자만 — 미구매·로그아웃은 잠김(저장값이 켜짐이어도 1배속) · 구매면 2배속 · 판 도중 권한 상실 시 1배속 복귀+안내 · 안내 문구 · 폰 폭
   임시 사본 survivors_sp2.html · survivors_sp2o.html(기준) · survivors_sp2_src.html 을 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
os.environ.setdefault('SV_CSX_OFF', '1')   # 2026-10-12: 캐릭터 고유 능력(CSX)을 중립으로 — 이 시험은 브장신·용조련사를 「능력 없는 기준」으로 쓴다(능력 자체는 survivors_cabil_test.py)
from playwright.async_api import async_playwright
ROOT = H.ROOT
BASE_COMMIT = '2bb6eaf'
NEW, OLD, OLDSRC = 'survivors_sp2.html', 'survivors_sp2o.html', 'survivors_sp2_src.html'
ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
MUT = sys.argv[sys.argv.index('--mutant') + 1] if '--mutant' in sys.argv else None
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
def want(sec): return ONLY is None or sec in ONLY

MUTANTS = {   # (바꿀 글, 바뀐 글) — 시험이 정말 이 실수를 잡는지 본다
    'nosecond': ("SPD.sub=1;try{update(dt);}finally{SPD.sub=0;}", ";"),                   # 두 번째 update 호출 제거
    'ignore': ("pref=v?1:0;try{localStorage.setItem(K,pref?'1':'0');}catch(e){}o.sync();", "pref=0;try{localStorage.setItem(K,'0');}catch(e){}o.sync();"),   # 토글 무시
    'nolock': ("const v=pref&&can()?1:0;", "const v=pref?1:0;"),                                 # 구매 검사 제거
    'lostall': ("const lost=o.on&&pref&&!can();", "const lost=o.on&&!v;"),                   # 직접 끈 것도 권한 상실로 안내
    'noframe': ("if(SPD.on&&!SRVUNL.has('spd2'))SPD.sync();", ""),                        # frame 의 권한 재검사 제거
    'norecheck': ("if(SPD.on&&!duelBoss()&&state==='play'&&EX.hs<=0&&SPD.take()){", "if(SPD.on){"),                  # 상태 전환 재확인 제거
}
EXTRA_NEW = "window.__X={RES,frame,SPD,SRVUNL,buy(on){srvUnl(on?['spd2']:[])},logout(){dcLogout()},pauseGame,get bannerT(){return bannerT},banner,setLast(v){last=v},hookUpdate(){if(window.__uw)return;window.__uw=1;window.__uc=0;const o=update;update=function(d){window.__uc++;const r=o(d);if(window.__hook){const h=window.__hook;window.__hook=null;h();}return r;};},hookToast(){window.__tc=0;const o=toast;toast=function(m){if(String(m).indexOf('폰이 힘들어해요')>=0)window.__tc++;return o(m);};}};\n"
EXTRA_OLD = "window.__X={RES,frame,pauseGame,setLast(v){last=v},hookUpdate(){if(window.__uw)return;window.__uw=1;window.__uc=0;const o=update;update=function(d){window.__uc++;const r=o(d);if(window.__hook){const h=window.__hook;window.__hook=null;h();}return r;};},hookToast(){window.__tc=0;const o=toast;toast=function(m){if(String(m).indexOf('폰이 힘들어해요')>=0)window.__tc++;return o(m);};}};\n"
def prep():
    src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    if MUT:
        a, b = MUTANTS[MUT]; assert src.count(a) == 1, (MUT, src.count(a)); src = src.replace(a, b)
    open(os.path.join(ROOT, OLDSRC), 'w', encoding='utf-8').write(src)
    H.make_copy(src=OLDSRC, dst=NEW, extra=EXTRA_NEW)
    old = subprocess.run(['git', '-C', ROOT, 'show', BASE_COMMIT + ':survivors.html'], capture_output=True, check=True).stdout.decode('utf-8')
    open(os.path.join(ROOT, OLDSRC), 'w', encoding='utf-8').write(old)
    H.make_copy(src=OLDSRC, dst=OLD, extra=EXTRA_OLD)
def cleanup():
    for f in (NEW, OLD, OLDSRC):
        try: os.remove(os.path.join(ROOT, f))
        except Exception: pass

DRIVEN = """(()=>{let s=12345;Math.random=function(){s=(s*1664525+1013904223)>>>0;return s/4294967296;};window.requestAnimationFrame=function(){return 0};})();"""   # rAF 를 막고 시험이 frame 을 직접 부른다 · 난수도 고정
NOLS = """Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}});Object.defineProperty(window,'sessionStorage',{get(){throw new Error('blocked')}});"""
async def mk(b, srv, page, w=412, h=860, init=None, ls=None, mobile=False, buy=True):   # buy: 2배속 구매자로 시작(서버 목록에 spd2) — 잠금 시험은 buy=False
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile)
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    if init: await ctx.add_init_script(init)
    if ls:
        await ctx.add_init_script("try{if(!sessionStorage.getItem('__sp2seed')){sessionStorage.setItem('__sp2seed','1');" + ''.join("localStorage.setItem(%s,%s);" % (json.dumps(k), json.dumps(v)) for k, v in ls.items()) + "}}catch(e){}")
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/%s' % (srv.port, page))
    await pg.wait_for_function('window.__X!==undefined', timeout=30000)
    if buy: await pg.evaluate("()=>{if(window.__X.buy)__X.buy(1)}")
    return ctx, pg, errs

# frame 을 직접 구동 — 레벨업은 첫 카드, 그 밖의 비-play 는 resume. 매번 last 를 합성 시각에 맞춘다. 히트스톱은 사실상 시험이 따로 본다.
DRIVE = r"""(a)=>{const x=__p6x;x.CH_set(a.ch);if(a.daily===false)x.start();else x.start({daily:true});const S=x.S;S.banned.push('rev');
 __X.hookUpdate();window.__uc=0;
 let t=1000;__X.setLast(t);if(a.spd!==undefined&&window.__X.SPD)__X.SPD.set(a.spd);
 let pf=0,fr=0;
 for(let i=0;i<a.n;i++){
  if(x.state==='lvup'){x.pick(x.CUR[0]);__X.setLast(t);}else if(x.state!=='play'){x.resume();__X.setLast(t);}
  if(a.god)S.p.hp=S.p.mhp;if(a.noxp){S.xp=0;S.need=1e9;}
  const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
  if(x.state==='play')pf++;
  t+=a.ms;fr++;__X.frame(t);}
 return {pf,fr,calls:window.__uc,st:S.t,state:x.state,kills:S.kills};}"""
DIGEST = r"""()=>{const x=__p6x,S=x.S,p=S.p;const parts=[S.t,S.kills,S.lv,S.xp,S.need,p.x,p.y,p.hp,p.mhp,p.inv,S.rr,S.ban];
 for(const e of x.enemies.a){if(!e.on)continue;parts.push('e',e.ki,e.x,e.y,e.hp,e.mhp,e.sn);}
 for(const g of x.gems.a){if(!g.on)continue;parts.push('g',g.x,g.y,g.v);}
 parts.push(JSON.stringify(S.w),JSON.stringify(S.ps),JSON.stringify(S.dmgBy));
 const str=parts.map(v=>typeof v==='number'?(Object.is(v,-0)?'-0':String(v)):String(v)).join('|');let h=0x811c9dc5;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,0x01000193)>>>0;}
 return {h,len:str.length,t:S.t,kills:S.kills,rnd:Math.random()};}"""

async def sec_a(b, srv):   # 가 · 끈 상태 불변
    hs = {}
    for ch in ('jjg', 'yj'):   # 2026-10-12 brj → jjg: 브장신의 시작 무기(깃털 산탄) 피해를 올려서 옛 기준 커밋과는 일부러 달라졌다 — 규칙 불변 증명은 시작 무기를 안 건드린 집중겜으로
        out = []
        for page in (OLD, NEW):
            ctx, pg, errs = await mk(b, srv, page, init=DRIVEN)
            r = await pg.evaluate(DRIVE, {'ch': ch, 'n': 900, 'ms': 1000 / 60, 'god': True, 'daily': ch == 'jjg'})
            d = await pg.evaluate(DIGEST)
            out.append((r, d, errs)); await ctx.close()
        (r0, d0, e0), (r1, d1, e1) = out
        check('[가] %s 끈 상태 = 기준 커밋과 비트 동일 (해시 %s, 처치 %s, S.t %.3f)' % (ch, d1['h'], d1['kills'], d1['t']), d0 == d1 and r0['calls'] == r1['calls'], (d0, d1, r0, r1))
        check('[가] %s 끈 상태 update 호출 = 프레임당 1회 (%d)' % (ch, r1['calls']), r1['calls'] == r1['pf'], r1)
        check('[가] %s 오류 0' % ch, not e0 and not e1, (e0, e1))
        hs[ch] = d1['h']
    check('[가] 시험이 캐릭터를 가린다(두 캐릭터 해시가 다르다)', len(set(hs.values())) == 2, hs)
    if '--equiv' in sys.argv:
        p = subprocess.run(['nice', '-n', '10', sys.executable, os.path.join(ROOT, 'tests', 'survivors_equiv.py'), '--a', BASE_COMMIT, '--b', 'survivors.html', '--chars', 'jjg,eom', '--seeds', '1', '--cap', '120', '--modes', 'n,h'], capture_output=True, text=True)
        print(p.stdout[-1500:])
        check('[가] survivors_equiv.py (기준 커밋 vs 지금) 종료코드 0', p.returncode == 0, p.stdout[-600:] + p.stderr[-300:])

async def sec_b(b, srv):   # 나 · 켠 상태
    DT = 1 / 60
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN)
    r1 = await pg.evaluate(DRIVE, {'ch': 'brj', 'n': 300, 'ms': 1000 * DT, 'god': True, 'noxp': True, 'spd': 0})
    await ctx.close()
    ctx, pg, e2 = await mk(b, srv, NEW, init=DRIVEN)
    r2 = await pg.evaluate(DRIVE, {'ch': 'brj', 'n': 300, 'ms': 1000 * DT, 'god': True, 'noxp': True, 'spd': 1})
    chip = await pg.evaluate("()=>getComputedStyle(document.getElementById('spdChip')).display")
    await ctx.close()
    check('[나] 끈 상태: 300프레임 = update 300회 · S.t = 300×dt (%.4f)' % r1['st'], r1['calls'] == 300 and abs(r1['st'] - 300 * DT) < 1e-6, r1)
    check('[나] 켠 상태: 300프레임 = update 600회 (%d)' % r2['calls'], r2['calls'] == 600, r2)
    check('[나] 켠 상태: S.t = 600×dt = %.4f (dt 를 키우지 않았다) · 끈 상태의 정확히 2배' % r2['st'], abs(r2['st'] - 600 * DT) < 1e-6 and abs(r2['st'] / r1['st'] - 2) < 1e-6, (r1, r2))
    check('[나] 켠 상태 HUD 칩이 보인다', chip != 'none', chip)
    check('[나] 오류 0', not errs and not e2, (errs, e2))
    # ⏩ [2026-10-15 사장님] 1.5배속 — 두 프레임에 한 번 두 번째 update (평균 1.5배) · 같은 구매(spd2)로 열린다
    ctx, pg, e3 = await mk(b, srv, NEW, init=DRIVEN)
    r3 = await pg.evaluate(DRIVE, {'ch': 'brj', 'n': 300, 'ms': 1000 * DT, 'god': True, 'noxp': True, 'spd': 1.5})
    st = await pg.evaluate("()=>({on:__X.SPD.on,ls:localStorage.getItem('p6_spd2'),chip:document.getElementById('spdChip').textContent})")
    await ctx.close()
    check('[나] 1.5배속: 300프레임 = update 450회 · S.t = 450×dt (%d회 · %.4f)' % (r3['calls'], r3['st']), r3['calls'] == 450 and abs(r3['st'] - 450 * DT) < 1e-6, r3)
    check('[나] 1.5배속: 저장값 1.5 · HUD 칩 「1.5배속」', st['on'] == 1.5 and st['ls'] == '1.5' and '1.5배속' in st['chip'], st)
    check('[나] 1.5배속 오류 0', not e3, e3)
    ctx, pg, e4 = await mk(b, srv, NEW, init=DRIVEN, buy=False)
    r4 = await pg.evaluate("()=>{__X.SPD.set(1.5);return {on:__X.SPD.on,ls:localStorage.getItem('p6_spd2')}}")
    await ctx.close()
    check('[나] 1.5배속도 미구매자는 못 켠다(같은 구매 필요)', r4['on'] == 0 and r4['ls'] in (None, '0'), r4)
    ctx, pg, e5 = await mk(b, srv, NEW, init=DRIVEN, ls={'p6_spd2': '1'})
    r5 = await pg.evaluate("()=>({on:__X.SPD.on})")
    await ctx.close()
    check('[나] 옛 저장값 p6_spd2=1 은 2배속으로 읽는다', r5['on'] == 2, r5)
    # 읽는 글(배너)은 실시간 — 켜 두고 30프레임(0.5초)을 돌려도 bannerT 는 0.5 만 줄어든다
    for spd in (0, 1):
        ctx, pg, er = await mk(b, srv, NEW, init=DRIVEN)
        r = await pg.evaluate("""(spd)=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});__X.SPD.set(spd);const S=x.S;S.need=1e9;
          __X.banner('시험 배너','',2);let t=1000;__X.setLast(t);t+=1000/60;__X.frame(t);const b0=__X.bannerT;
          for(let i=0;i<30;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}return {b0,b1:__X.bannerT};}""", spd)
        check('[나] 배너는 실시간 (%s): 0.5초 동안 %.3f 줄었다 (0.5 기대)' % ('켬' if spd else '끔', r['b0'] - r['b1']), abs((r['b0'] - r['b1']) - 0.5) < 0.02, r)
        await ctx.close()
    # 실제 rAF — 같은 환경에서 끈/켠 판의 초당 S.t 비율
    rate = {}
    for spd in (0, 1):
        ctx, pg, er = await mk(b, srv, NEW, init=None, ls={'p6_spd2': str(spd)})
        await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();__p6x.S.need=1e9;}")
        await pg.wait_for_timeout(400)
        rate[spd] = await pg.evaluate("""()=>new Promise(res=>{const S=__p6x.S,t0=S.t,w0=performance.now();let n=0;const iv=setInterval(()=>{S.p.hp=S.p.mhp;},100);
          setTimeout(()=>{clearInterval(iv);res({dt:S.t-t0,ms:performance.now()-w0,on:__X.SPD.on});},3000);})""")
        check('[나] 실제 rAF (%s) 오류 0' % ('켬' if spd else '끔'), not er, er); await ctx.close()
    r0, r1_ = rate[0]['dt'] / rate[0]['ms'] * 1000, rate[1]['dt'] / rate[1]['ms'] * 1000
    check('[나] 실제 rAF: 초당 게임 시간 끔 %.2f → 켬 %.2f (비율 %.2f, 1.6~2.4 기대 · 느린 기계면 dt 상한 때문에 낮을 수 있다)' % (r0, r1_, r1_ / max(r0, 1e-9)), rate[1]['on'] == 2 and 1.6 <= r1_ / max(r0, 1e-9) <= 2.4, rate)

async def sec_c(b, srv):   # 다 · 전환
    async def one(name, pre, hook, want_calls, want_state, ms_calls=None):
        ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN)
        r = await pg.evaluate("""(a)=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});__X.SPD.set(1);const S=x.S;S.need=1e9;S.p.hp=S.p.mhp;let t=1000;__X.setLast(t);
          t+=1000/60;__X.frame(t);   // 워밍업 한 프레임
          __X.hookUpdate();window.__uc=0;
          const t0=S.t;eval(a.pre);if(a.hook)window.__hook=new Function('x','S',a.hook).bind(null,x,S);
          t+=1000/60;__X.frame(t);return {calls:window.__uc,state:x.state,dts:S.t-t0,hs:x.EX.hs};}""", {'pre': pre, 'hook': hook})
        check('[다] %s: update %d회 · state=%s (%s)' % (name, want_calls, want_state, r), r['calls'] == want_calls and r['state'] == want_state, r)
        check('[다] %s: 이 프레임에 S.t 는 %d×dt 만 흘렀다' % (name, want_calls), abs(r['dts'] - want_calls / 60) < 1e-6, r)
        check('[다] %s: 오류 0' % name, not errs, errs); await ctx.close()
    await one('평소(대조)', '0', None, 2, 'play')
    await one('레벨업이 첫 update 안에서 열림', 'x.S.pendingLv=1', None, 1, 'lvup')
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN)
    r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});__X.SPD.set(1);const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);t+=1000/60;__X.frame(t);
      __X.hookUpdate();window.__uc=0;
      window.__hook=()=>x.endRun(false);t+=1000/60;__X.frame(t);return {calls:window.__uc,state:x.state};}""")
    check('[다] 첫 update 뒤 사망(endRun) → 두 번째 update 안 돎 (calls=%d, state=%s)' % (r['calls'], r['state']), r['calls'] == 1 and r['state'] != 'play', r)
    await ctx.close()
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN)
    r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});__X.SPD.set(1);const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);t+=1000/60;__X.frame(t);
      __X.hookUpdate();window.__uc=0;
      window.__hook=()=>{x.EX.hs=.07;};t+=1000/60;__X.frame(t);const c1=window.__uc;t+=1000/60;__X.frame(t);t+=1000/60;__X.frame(t);return {c1,c3:window.__uc,hs:x.EX.hs};}""")
    check('[다] 히트스톱: 첫 update 가 걸었으면 두 번째는 안 돈다 (c1=%d) · 걸려 있는 동안 update 없음 (c3=%d)' % (r['c1'], r['c3']), r['c1'] == 1 and r['c3'] == 1, r)
    await ctx.close()
    # 보스 상자 / 일시정지 등 비-play 상태 전환도 같은 규칙(상태 직접 바꿈)
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN)
    r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});__X.SPD.set(1);const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);t+=1000/60;__X.frame(t);
      __X.hookUpdate();window.__uc=0;
      window.__hook=()=>{x.state='chest';};t+=1000/60;__X.frame(t);return {calls:window.__uc,state:x.state};}""")
    check('[다] 상자(chest) 전환 직후 두 번째 update 안 돎 (calls=%d)' % r['calls'], r['calls'] == 1 and r['state'] == 'chest', r)
    await ctx.close()

async def sec_d(b, srv):   # 라 · 토글 저장·유지·불가
    ctx, pg, errs = await mk(b, srv, NEW)
    r = await pg.evaluate("()=>({on:__X.SPD.on,ls:localStorage.getItem('p6_spd2'),chk:(document.getElementById('spdChk').value==='2'),chip:getComputedStyle(document.getElementById('spdChip')).display})")
    check('[라] 기본값: 꺼짐 · 저장값 없음 · 체크 해제 · 칩 숨김', r['on'] == 0 and r['ls'] is None and r['chk'] is False and r['chip'] == 'none', r)
    await pg.select_option('#spdChk','2')
    r = await pg.evaluate("()=>({on:__X.SPD.on,ls:localStorage.getItem('p6_spd2')})")
    check('[라] 첫 화면 체크 → 켜짐 · p6_spd2=2 저장', r['on'] == 2 and r['ls'] == '2', r)
    await pg.reload(); await pg.wait_for_function('window.__X!==undefined'); await pg.evaluate('()=>__X.buy(1)')   # 구매 목록은 메모리 — 새로고침 뒤 서버가 다시 내려준 셈
    r = await pg.evaluate("()=>({on:__X.SPD.on,chk:(document.getElementById('spdChk').value==='2')})")
    check('[라] 새로고침 뒤에도 켜짐 유지', r['on'] == 2 and r['chk'] is True, r)
    # 판 시작 → 다음 판에도 유지, 일시정지 토글과 동기
    await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();__X.pauseGame();}")
    r = await pg.evaluate("()=>({state:__p6x.state,chk:[...document.querySelectorAll('#pause select[data-spd]')].map(e=>e.value==='2')})")
    check('[라] 일시정지 화면 토글이 켜진 상태로 보인다', r['state'] == 'pause' and r['chk'] == [True], r)
    await pg.select_option('#pause select[data-spd]','0')
    r = await pg.evaluate("()=>({on:__X.SPD.on,ls:localStorage.getItem('p6_spd2'),title:(document.getElementById('spdChk').value==='2'),chip:getComputedStyle(document.getElementById('spdChip')).display})")
    check('[라] 일시정지에서 끔 → 즉시 꺼짐 · 저장 0 · 첫 화면 단추와 동기 · 칩 숨김', r['on'] == 0 and r['ls'] == '0' and r['title'] is False and r['chip'] == 'none', r)
    await pg.select_option('#pause select[data-spd]','2')
    r = await pg.evaluate("()=>{__p6x.resume();const S=__p6x.S;return {on:__X.SPD.on,state:__p6x.state,chip:getComputedStyle(document.getElementById('spdChip')).display}}")
    check('[라] 일시정지에서 켜고 계속하기 → 켜짐 · 칩 보임', r['on'] == 2 and r['state'] == 'play' and r['chip'] != 'none', r)
    await pg.evaluate("()=>{__p6x.endRun(false);}")
    await pg.evaluate("()=>{__p6x.start();}")
    r = await pg.evaluate("()=>({on:__X.SPD.on,state:__p6x.state})")
    check('[라] 다음 판에도 켜짐 유지', r['on'] == 2 and r['state'] == 'play', r)
    check('[라] 오류 0', not errs, errs); await ctx.close()
    # 일반·하드·베리하드·오늘의 도전·무한 — 켜 둔 채 모두 시작·진행
    for nm, ls in [('일반', {'p6_hard': '0', 'p6_vh': '0'}), ('하드', {'p6_hard': '1', 'p6_vh': '0'}), ('베리하드', {'p6_hard': '0', 'p6_vh': '1'}), ('오늘의 도전', {}), ('무한', {})]:
        ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN, ls=dict(ls, p6_spd2='1'))
        r = await pg.evaluate("""(nm)=>{const x=__p6x;x.CH_set('brj');
          if(nm==='오늘의 도전')x.start({daily:true});else x.start();
          if(nm==='무한'){x.S.won=1;x.S.t=3599;x.endRun(true);}
          const S=x.S;if(nm==='무한'){x.contEndless();}
          let t=1000;__X.setLast(t);S.need=1e9;const t0=S.t;for(let i=0;i<120;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}
          return {on:__X.SPD.on,state:x.state,dt:S.t-t0,hard:!!S.hard,vh:!!S.vh,dly:!!S.dly,endless:!!S.endless};}""", nm)
        okm = (nm != '하드' or r['hard']) and (nm != '베리하드' or r['vh']) and (nm != '오늘의 도전' or r['dly']) and (nm != '무한' or r['endless'])
        check('[라] %s 모드 + 2배속: 120프레임에 게임 시간 %.3f초 (=4.0 · 모드 적용 %s)' % (nm, r['dt'], okm), okm and r['on'] == 2 and abs(r['dt'] - 4.0) < 0.01 and r['state'] == 'play', r)
        check('[라] %s 오류 0' % nm, not errs, errs); await ctx.close()
    # localStorage 불가
    ctx, pg, errs = await mk(b, srv, NEW, init=NOLS)
    r = await pg.evaluate("()=>({on:__X.SPD.on})")
    await pg.select_option('#spdChk','2')
    r2 = await pg.evaluate("()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);window.__n=0;const t0=S.t;for(let i=0;i<60;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}return {on:__X.SPD.on,dt:S.t-t0}}")
    check('[라] localStorage 불가: 기본 꺼짐 → 켜면 메모리로 동작 (게임 시간 %.3f초 ≈ 2.0) · 오류 0' % r2['dt'], r['on'] == 0 and r2['on'] == 2 and abs(r2['dt'] - 2.0) < 0.01 and not errs, (r, r2, errs)); await ctx.close()
    # 느린 폰 안내
    for nm, ms, spd, exp in [('느린 폰(40ms) · 켬', 40, 1, 1), ('빠른 폰(16.7ms) · 켬', 1000 / 60, 1, 0), ('느린 폰(40ms) · 끔', 40, 0, 0)]:
        ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN)
        r = await pg.evaluate("""(a)=>{const x=__p6x;x.CH_set('brj');x.start();__X.SPD.set(a.spd);const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);__X.hookToast();
          for(let i=0;i<Math.ceil(20000/a.ms);i++){S.p.hp=S.p.mhp;t+=a.ms;__X.frame(t);}return {tc:window.__tc,warned:__X.SPD.warned,txt:document.getElementById('toast').textContent};}""", {'ms': ms, 'spd': spd})
        check('[라] 느린 폰 안내 — %s: 안내 %d번 (기대 %d · 20초 돌려도 한 번만)' % (nm, r['tc'], exp), r['tc'] == exp, r)
        check('[라] 느린 폰 안내 %s 오류 0' % nm, not errs, errs); await ctx.close()

async def sec_e(b, srv):   # 마 · 화면
    for (w, h) in [(320, 640), (360, 740), (412, 860)]:
        ctx, pg, errs = await mk(b, srv, NEW, w=w, h=h, mobile=True, ls={'p6_spd2': '1'})
        r = await pg.evaluate("""()=>{const l=document.getElementById('spdChk').closest('label'),R=l.getBoundingClientRect(),d=document.documentElement;
          const bx=document.querySelector('#title .box');return {h:R.height,w:R.width,l:R.left,r:R.right,sw:d.scrollWidth,cw:d.clientWidth,bsw:bx.scrollWidth,bcw:bx.clientWidth,vw:innerWidth,txt:l.textContent.replace(/\\s+/g,' ')}}""")
        check('[마] 첫 화면 %dpx: 2배속 단추 높이 %.0fpx(≥40) · 화면 안 · 가로 넘침 0' % (w, r['h']), r['h'] >= 40 and r['l'] >= 0 and r['r'] <= r['vw'] and r['sw'] <= r['cw'] and r['bsw'] <= r['bcw'], r)
        check('[마] 첫 화면 %dpx: 설명 글 「더 빨리」' % w, '더 빨리' in r['txt'], r['txt'])
        await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();}")
        c = await pg.evaluate("""()=>{const c=document.getElementById('spdChip'),R=c.getBoundingClientRect(),hp=document.getElementById('hpb').getBoundingClientRect(),d=document.documentElement;
          return {disp:getComputedStyle(c).display,l:R.left,r:R.right,t:R.top,b:R.bottom,hpb:hp.bottom,vw:innerWidth,sw:d.scrollWidth,cw:d.clientWidth,txt:c.textContent,pe:getComputedStyle(c).pointerEvents}}""")
        check('[마] HUD 칩 %dpx: 켰을 때 보인다 「%s」 · 화면 안 · HP 막대 아래 · 가로 넘침 0' % (w, c['txt']), c['disp'] != 'none' and c['l'] >= 0 and c['r'] <= c['vw'] and c['t'] >= c['hpb'] - 1 and c['sw'] <= c['cw'] and '2배속' in c['txt'], c)
        await pg.evaluate("()=>{__X.pauseGame();}")
        p = await pg.evaluate("""()=>{const l=document.querySelector('#pause label.spdl'),R=l.getBoundingClientRect(),d=document.documentElement,bx=document.querySelector('#pause .box');
          return {h:R.height,l:R.left,r:R.right,vw:innerWidth,sw:d.scrollWidth,cw:d.clientWidth,bsw:bx.scrollWidth,bcw:bx.clientWidth,vis:getComputedStyle(document.getElementById('pause')).display}}""")
        check('[마] 일시정지 %dpx: 2배속 칸 높이 %.0fpx(≥40) · 화면 안 · 가로 넘침 0' % (w, p['h']), p['h'] >= 40 and p['l'] >= 0 and p['r'] <= p['vw'] and p['sw'] <= p['cw'] and p['bsw'] <= p['bcw'], p)
        await pg.select_option('#pause select[data-spd]','0')
        await pg.evaluate("()=>__p6x.resume()")
        c = await pg.evaluate("()=>getComputedStyle(document.getElementById('spdChip')).display")
        check('[마] HUD 칩 %dpx: 끄면 사라진다' % w, c == 'none', c)
        check('[마] %dpx 오류 0' % w, not errs, errs); await ctx.close()

async def sec_f(b, srv):   # 바 · 이어하기
    ctx, pg, errs = await mk(b, srv, NEW)
    await pg.evaluate("()=>{__X.RES.buildStatic();}"); sn = await pg.evaluate("()=>({sig:__X.RES.SIG,keys:(__p6x.CH_set('brj'),__p6x.start(),Object.keys(__p6x.S).sort())})")
    await ctx.close()
    ctx, pg, e0 = await mk(b, srv, OLD)
    await pg.evaluate("()=>{__X.RES.buildStatic();}"); so = await pg.evaluate("()=>({sig:__X.RES.SIG,keys:(__p6x.CH_set('brj'),__p6x.start(),Object.keys(__p6x.S).sort())})")
    await ctx.close()
    check('[바] 이어하기 서명(SIG) 불변: %s' % sn['sig'], sn['sig'] == so['sig'], (sn['sig'], so['sig']))
    check('[바] S 키 불변 (새 키 0 · %d개)' % len(sn['keys']), sn['keys'] == so['keys'], set(sn['keys']) ^ set(so['keys']))
    # 켠 채 저장 → 새 페이지에서 복구 → 이어서 진행(2배속 유지)
    BUILD = r"""(a)=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.need=1e9;if(window.__X.SPD)__X.SPD.set(a.spd);let t=1000;__X.setLast(t);
      for(let i=0;i<120;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}__X.pauseGame();
      return {blob:localStorage.getItem('p6_resume_v1'),t:S.t,kills:S.kills,state:x.state}}"""
    for (page, spd, nm) in [(NEW, 1, '새 빌드(2배속 켠 채)'), (OLD, 0, '기준 커밋 빌드로 저장한 옛 저장본')]:
        ctx, pg, errs = await mk(b, srv, page)
        pre = await pg.evaluate(BUILD, {'spd': spd})
        check('[바] %s: 저장됨(일시정지, S.t=%.2f)' % (nm, pre['t']), pre['blob'] is not None and pre['state'] == 'pause', pre['state'])
        await ctx.close()
        ctx, pg, errs = await mk(b, srv, NEW, ls={'p6_spd2': '1'})
        await pg.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", pre['blob'])
        await pg.reload(); await pg.wait_for_function('window.__X!==undefined'); await pg.evaluate('()=>__X.buy(1)')
        ok = await pg.evaluate("()=>__X.RES.restore()")
        s1 = await pg.evaluate("()=>({state:__p6x.state,t:__p6x.S.t,on:__X.SPD.on})")
        check('[바] %s → 새 빌드(2배속 켠 채) 복구됨 · 일시정지 · S.t 같음' % nm, ok is True and s1['state'] == 'pause' and abs(s1['t'] - pre['t']) < 1e-6 and s1['on'] == 2, (ok, s1, pre['t']))
        r = await pg.evaluate("""()=>{const x=__p6x;x.resume();const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);const t0=S.t;for(let i=0;i<60;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}return {st:x.state,dt:S.t-t0}}""")
        check('[바] %s: 복구 뒤 계속하기 → 60프레임에 게임 시간 %.3f초(≈2.0)' % (nm, r['dt']), r['st'] == 'play' and abs(r['dt'] - 2.0) < 0.01, r)
        check('[바] %s 오류 0' % nm, not errs, errs); await ctx.close()

LOGIN = json.dumps({'id': '1', 'name': '시험', 'token': 't', 'exp': 4102444800000})   # 로그인한 척(서버는 막혀 있다)
LOCK_CLICK = "()=>{const e=document.querySelector('#spdChk');e.value='2';e.dispatchEvent(new Event('change',{bubbles:true}));}"
async def sec_g(b, srv):   # 아 · 구매자만
    DT = 1 / 60
    RUN = """(a)=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});if(a.set)__X.SPD.set(1);const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);__X.hookUpdate();window.__uc=0;const t0=S.t;
      for(let i=0;i<a.n;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}return {calls:window.__uc,dt:S.t-t0,on:__X.SPD.on}}"""
    ST = "()=>({on:__X.SPD.on,ls:localStorage.getItem('p6_spd2'),chk:(document.getElementById('spdChk').value==='2'),ad:document.getElementById('spdChk').getAttribute('aria-disabled'),sm:document.querySelector('#title [data-spdsm]').textContent,v:document.querySelector('#pause [data-spdv]').textContent,chip:getComputedStyle(document.getElementById('spdChip')).display,toast:document.getElementById('toast').textContent})"
    # 1) 로그아웃 — 저장값이 켜짐이어도 잠김·1배속
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN, ls={'p6_spd2': '1'}, buy=False)
    r = await pg.evaluate(ST)
    check('[아] 로그아웃: 저장값이 켜짐이어도 꺼짐 · 체크 해제 · 🔒 · 칩 숨김', r['on'] == 0 and r['chk'] is False and r['ad'] == 'true' and r['v'] == '🔒' and r['chip'] == 'none', r)
    check('[아] 로그아웃 안내 「디스코드 로그인 필요」', '디스코드 로그인 필요' in r['sm'], r['sm'])
    await pg.evaluate(LOCK_CLICK)
    r2 = await pg.evaluate(ST)
    check('[아] 로그아웃: 눌러도 안 켜진다 · 저장값 그대로(1) · 안내 토스트', r2['on'] == 0 and r2['chk'] is False and r2['ls'] == '1' and '로그인' in r2['toast'], r2)
    run = await pg.evaluate(RUN, {'n': 300, 'set': True})
    check('[아] 로그아웃: 300프레임 = update 300회 · S.t = 300×dt (1배속) — 저장값 켜짐·SPD.set(1) 시도에도', run['calls'] == 300 and abs(run['dt'] - 300 * DT) < 1e-6 and run['on'] == 0, run)
    check('[아] 로그아웃 오류 0', not errs, errs); await ctx.close()
    # 2) 로그인했지만 미구매 — 목록 받기 전엔 「확인 중」, 받은 뒤엔 상점 안내
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN, ls={'p6_spd2': '1', 'sgg_dc': LOGIN}, buy=False)
    r = await pg.evaluate("()=>{const a=__X.SPD.lockMsg();__X.buy(0);return {pre:a,post:__X.SPD.lockMsg(),on:__X.SPD.on,sm:document.querySelector('#title [data-spdsm]').textContent}}")
    check('[아] 로그인·목록 전: 「확인 중」 (%s)' % r['pre'], '확인 중' in r['pre'], r)
    check('[아] 로그인·미구매: 「맛동산상점에서 3맛동산으로 사면 열려요」 (%s)' % r['post'], '맛동산상점' in r['post'] and '3맛동산' in r['post'] and '사면 열려요' in r['post'] and r['sm'] == r['post'], r)
    run = await pg.evaluate(RUN, {'n': 300, 'set': False})
    check('[아] 로그인·미구매: 저장값 켜짐인데도 300프레임 = update 300회 (1배속)', run['calls'] == 300 and abs(run['dt'] - 300 * DT) < 1e-6 and run['on'] == 0, run)
    check('[아] 로그인·미구매 오류 0', not errs, errs); await ctx.close()
    # 3) 구매자 — 지금처럼 켜지고 2배속, 저장·유지
    ctx, pg, errs = await mk(b, srv, NEW, init=DRIVEN, ls={'sgg_dc': LOGIN}, buy=False)
    await pg.evaluate("()=>__X.buy(1)")
    r = await pg.evaluate(ST)
    check('[아] 구매자: 기본 꺼짐 · 안내는 원래 설명 · 🔒 없음', r['on'] == 0 and r['ad'] == 'false' and '더 빨리' in r['sm'] and r['v'] == '1배속', r)
    await pg.evaluate(LOCK_CLICK)
    r = await pg.evaluate(ST)
    check('[아] 구매자: 체크 → 켜짐 · 저장 1 · 칩 보임', r['on'] == 2 and r['ls'] == '2' and r['chip'] != 'none', r)
    # 구매자가 직접 끄면 「권한 잃음」 안내가 뜨면 안 된다
    r = await pg.evaluate("()=>{document.getElementById('toast').textContent='';const e=document.querySelector('#spdChk');e.value='0';e.dispatchEvent(new Event('change',{bubbles:true}));return {on:__X.SPD.on,ls:localStorage.getItem('p6_spd2'),toast:document.getElementById('toast').textContent}}")
    check('[아] 구매자가 직접 끄면: 꺼짐 · 저장 0 · 토스트에 「돌아왔어요」 없음', r['on'] == 0 and r['ls'] == '0' and '돌아왔어요' not in r['toast'], r)
    await pg.evaluate(LOCK_CLICK)
    run = await pg.evaluate(RUN, {'n': 300, 'set': False})
    check('[아] 구매자: 300프레임 = update 600회 · S.t = 600×dt', run['calls'] == 600 and abs(run['dt'] - 600 * DT) < 1e-6, run)
    # 4) 판 도중 권한 상실 — 서버 목록 갱신(srvUnl) · 목록에서 직접 빠짐(frame 재검사) · 로그아웃, 모두 그 프레임부터 1배속 + 안내 한 번
    for how, js in [('서버 목록이 spd2 없이 갱신', "__X.buy(0)"), ('목록에서 spd2 만 빠짐(frame 재검사)', "__X.SRVUNL.delete('spd2')"), ('로그아웃', "__X.logout()")]:
        ctx2, pg2, e2 = await mk(b, srv, NEW, init=DRIVEN, ls={'sgg_dc': LOGIN, 'p6_spd2': '1'}, buy=True)
        r = await pg2.evaluate("""(js)=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});const S=x.S;S.need=1e9;let t=1000;__X.setLast(t);__X.hookUpdate();__X.hookToast2=0;
          const lost=[];const o=toast;
          window.__uc=0;const on0=__X.SPD.on;for(let i=0;i<30;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);}const c1=window.__uc;
          window.__tx=[];const tt=document.getElementById('toast');
          eval(js);window.__uc=0;const t0=S.t;for(let i=0;i<100;i++){S.p.hp=S.p.mhp;t+=1000/60;__X.frame(t);if(i===0)window.__tx.push(tt.textContent);}
          return {on0,c1,c2:window.__uc,dt:S.t-t0,on:__X.SPD.on,tx:window.__tx[0],ls:localStorage.getItem('p6_spd2')}}""", js)
        check('[아] 구매 후 권한 상실 (%s): 상실 전 2배속(30프레임=update %d회) → 상실 뒤 100프레임 = update 100회 · 1배속' % (how, r['c1']), r['on0'] == 2 and r['c1'] == 60 and r['c2'] == 100 and abs(r['dt'] - 100 * DT) < 1e-6 and r['on'] == 0, r)
        check('[아] 권한 상실 안내 (%s): 「1배속으로 돌아왔어요」 (%s)' % (how, r['tx']), '1배속으로 돌아왔어요' in (r['tx'] or ''), r)
        check('[아] 권한 상실 (%s) 오류 0' % how, not e2, e2); await ctx2.close()
    # 상실 뒤 다시 구매 목록이 오면(저장값 1) 되살아난다
    r = await pg.evaluate("()=>{__X.buy(0);const a=__X.SPD.on;__X.buy(1);return {a,b:__X.SPD.on}}")
    check('[아] 목록이 사라졌다 돌아오면 저장값대로 다시 켜진다', r['a'] == 0 and r['b'] == 2, r)
    check('[아] 구매자 오류 0', not errs, errs); await ctx.close()
    # 5) 폰 폭 — 잠긴 안내 문구(가장 긴 쪽)가 넘치지 않는다
    for (w, h) in [(320, 640), (360, 740), (412, 860)]:
        ctx, pg, errs = await mk(b, srv, NEW, w=w, h=h, mobile=True, ls={'sgg_dc': LOGIN}, buy=False)
        await pg.evaluate("()=>__X.buy(0)")
        r = await pg.evaluate("""()=>{const l=document.getElementById('spdChk').closest('label'),R=l.getBoundingClientRect(),d=document.documentElement,bx=document.querySelector('#title .box');
          return {h:R.height,l:R.left,r:R.right,vw:innerWidth,sw:d.scrollWidth,cw:d.clientWidth,bsw:bx.scrollWidth,bcw:bx.clientWidth,txt:l.textContent.replace(/\\s+/g,' ')}}""")
        check('[아] 잠긴 첫 화면 %dpx: 높이 %.0fpx(≥40) · 화면 안 · 가로 넘침 0 · 안내 보임' % (w, r['h']), r['h'] >= 40 and r['l'] >= 0 and r['r'] <= r['vw'] and r['sw'] <= r['cw'] and r['bsw'] <= r['bcw'] and '맛동산상점' in r['txt'], r)
        await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();__X.pauseGame();}")
        p = await pg.evaluate("""()=>{const l=document.querySelector('#pause label.spdl'),R=l.getBoundingClientRect(),d=document.documentElement,bx=document.querySelector('#pause .box');
          return {h:R.height,l:R.left,r:R.right,vw:innerWidth,sw:d.scrollWidth,cw:d.clientWidth,bsw:bx.scrollWidth,bcw:bx.clientWidth,txt:l.textContent.replace(/\\s+/g,' ')}}""")
        check('[아] 잠긴 일시정지 %dpx: 높이 %.0fpx(≥40) · 화면 안 · 가로 넘침 0 · 안내 보임' % (w, p['h']), p['h'] >= 40 and p['l'] >= 0 and p['r'] <= p['vw'] and p['sw'] <= p['cw'] and p['bsw'] <= p['bcw'] and '맛동산상점' in p['txt'], p)
        check('[아] 잠긴 %dpx 오류 0' % w, not errs, errs); await ctx.close()

async def main():
    prep()
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            try:
                for sec, fn in [('가', sec_a), ('나', sec_b), ('다', sec_c), ('라', sec_d), ('마', sec_e), ('바', sec_f), ('아', sec_g)]:
                    if want(sec):
                        print('── %s ──' % sec, flush=True)
                        await fn(b, srv)
            finally:
                await b.close()
    finally:
        srv.close(); cleanup()
    print('\n실패 %d건' % len(FAILS)); [print('  - ' + f) for f in FAILS]
    sys.exit(1 if FAILS else 0)

if __name__ == '__main__':
    if '--mutants' in sys.argv:
        bad = 0
        for m in MUTANTS:
            p = subprocess.run(['nice', '-n', '10', sys.executable, os.path.abspath(__file__), '--mutant', m, '--only', '나,다,라,아'], capture_output=True, text=True)
            fails = [l for l in p.stdout.splitlines() if l.startswith('FAIL')]
            print('변이 %-10s → 빨강 %d건 %s' % (m, len(fails), '(잡았다)' if fails else '(★ 못 잡았다)')); bad += 0 if fails else 1
        sys.exit(1 if bad else 0)
    try:
        asyncio.run(main())
    finally:
        cleanup()
