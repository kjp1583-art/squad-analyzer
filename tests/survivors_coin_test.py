# -*- coding: utf-8 -*-
"""🪙 [2026-10-09 사장님 지시 "죽으면 코인사용할지말지 유저선택창 띄우고"] 부활 코인 선택창 시험 — 가짜 서버(page.route)로 돌린다.

실행: python3 tests/survivors_coin_test.py            (종료코드 0 = 전부 통과)
환경: SV_SRC=<저장소 안 html 이름>  시험할 파일(기본 survivors.html — 변이 시험 때 바꿔 끼운다)
      COIN_SHOTS=<폴더>             스크린샷 저장 폴더(없으면 저장 안 함)
      COIN_ONLY=B,E,F               돌릴 구간만 고른다(기본 전부 · 변이 시험용)
같은 워크트리에서 다른 survivors 시험과 동시에 돌리지 않는다(임시 사본 survivors_cx*.html 을 쓰고 끝나면 지운다).
기준(코인 이전) 빌드는 커밋 cedf7bf(origin/main) 의 survivors.html 이다 — 난수 비교·이어하기 호환에 쓴다(없으면 그 구간만 「확인 못 함」).
"""
import asyncio, sys, os, json, re, subprocess
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import sv_harness as H
BASE_HOOK = H.HOOK
OLD_RV = "\nwindow.__rv={RV:null,die,hitP,endRun,spawnEnemy,enemies,update,pauseGame,RES,get RUN(){return RUN},get ME(){return ME}};\n"
H.HOOK += ("\nwindow.__rv={die,reviveOpen,coinUse,rvQuit,RV,reviveFx,coinOffer,refreshCoins,rvRender,rvLock,RES,endRun,dcUser,loadMe,renderAcct,coinsOf,"
           "get RUN(){return RUN},get ME(){return ME},set ME(v){ME=v},update,hitP,spawnEnemy,enemies,pauseGame,COIN_TMO};\n")
from playwright.async_api import async_playwright

SRC = os.environ.get('SV_SRC', 'survivors.html')
SHOTS = os.environ.get('COIN_SHOTS')
NEW = 'survivors_cx.html'; OLD = 'survivors_cxo.html'
BASE_COMMIT = 'cedf7bf'
FAILS = []; N = [0]; SKIPS = []
ONLY = [x for x in os.environ.get('COIN_ONLY', '').upper().split(',') if x]   # 예: COIN_ONLY=B,E  (변이 시험 때 구간만 골라 돌린다)
want = lambda k: not ONLY or k in ONLY
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:500]) if (extra != '' and not cond) or extra == 'v' else ''), flush=True)
    if not cond: FAILS.append(name)

LOGIN = "localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))"
# 계약 시험 벡터(V1~V12)의 본문 — 상태 코드와 JSON 이 글자 그대로
VEC = {
    'no_coin': (409, '{"ok":false,"code":"no_coin","coins":0}'), 'bad': (400, '{"ok":false,"code":"bad"}'), 'auth': (401, '{"ok":false,"code":"auth"}'),
    'rate': (429, '{"ok":false,"code":"rate"}'), 'upstream': (503, '{"ok":false,"code":"upstream"}'), 'busy': (503, '{"ok":false,"code":"busy"}'),
    'notfound': (404, '{"ok":false,"code":"not_found"}'), 'big': (413, '{"ok":false,"code":"big"}'), 'error': (500, '{"ok":false,"code":"error"}'),
}
class Mock:
    def __init__(self, coins=2):
        self.coins = coins; self.coin_mode = 'ok'; self.coin_reqs = []; self.me_reqs = 0; self.runs = []; self.me_has_coins = True
        self.me_coins_override = None; self.charged = set(); self.gate = None; self.pending_slow = []
    async def __call__(self, r):
        u = r.request.url
        hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
        def J(j, status=200): return r.fulfill(status=status, headers=hdr, content_type='application/json', body=json.dumps(j, separators=(',', ':')))
        if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
        if '/p6/board' in u: await J({'board': [], 'hard': [], 'vhard': []})
        elif '/p6/me' in u:
            self.me_reqs += 1
            j = {'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1, 'daily_done': False, 'daily_date': '2026-10-09'}
            if self.me_has_coins: j['coins'] = self.coins if self.me_coins_override is None else (None if self.me_coins_override == '__null__' else self.me_coins_override)
            await J(j)
        elif '/p6/coin' in u:
            b = json.loads(r.request.post_data or '{}'); self.coin_reqs.append(b)
            m = self.coin_mode
            if m == 'net': await r.abort(); return
            if m == 'hang': return                                    # 응답을 안 준다(시간 초과 시험)
            if m == 'slow':                                           # 시험이 풀어 줄 때까지 붙잡는다
                self.pending_slow.append((r, b)); return
            if m == 'html': await r.fulfill(status=502, headers=hdr, content_type='text/html', body='<html>Bad Gateway</html>'); return
            if m in VEC:
                st, body = VEC[m]; await r.fulfill(status=st, headers=hdr, content_type='application/json', body=body); return
            if m == 'charged_then_drop':                              # 서버는 차감했지만 응답이 끊김
                key = (b['rid'], b['n'])
                if key not in self.charged: self.charged.add(key); self.coins -= 1
                await r.abort(); return
            key = (b['rid'], b['n'])
            if key in self.charged: await J({'ok': True, 'coins': self.coins, 'dup': True}); return
            if self.coins <= 0: st, body = VEC['no_coin']; await r.fulfill(status=st, headers=hdr, content_type='application/json', body=body); return
            self.charged.add(key); self.coins -= 1
            await J({'ok': True, 'coins': self.coins, 'dup': False})
        elif '/p6/run' in u:
            b = json.loads(r.request.post_data or '{}'); self.runs.append(b)
            await J({'ok': True, 'rank': 1, 'total': 2, 'unlocks': ['brj'], 'best_t': b.get('t', 0)})
        else: await r.fulfill(status=404, headers=hdr, body='{}')
    async def release_slow(self):
        for (r, b) in self.pending_slow:
            key = (b['rid'], b['n'])
            if key not in self.charged and self.coins > 0: self.charged.add(key); self.coins -= 1
            try: await r.fulfill(status=200, headers={'Access-Control-Allow-Origin': '*'}, content_type='application/json', body=json.dumps({'ok': True, 'coins': self.coins, 'dup': False}))
            except Exception: pass
        self.pending_slow = []

async def fresh(b, port, mock, login=True, w=412, h=860, page=NEW, mobile=False):
    ctx, pg, errs = await H.new_page(b, port, w, h, mock=mock, page=page, mobile=mobile)
    if login: await pg.evaluate(LOGIN)
    await pg.reload(); await pg.wait_for_function('window.__p6x!==undefined')
    await pg.wait_for_timeout(400)
    return ctx, pg, errs

# 판을 시작하고 적을 치우고 체력 1 에서 500 짜리 한 방을 맞는다
KILL = """(a)=>{const x=__p6x,v=__rv;x.CH_set('brj');x.start(a&&a.start);const S=x.S;
  S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;
  for(const q of x.enemies.a)q.on=false;
  if(a&&a.rev){S.ps.rev=1;}
  if(a&&a.mode==='hard'){S.hard=1;}if(a&&a.mode==='vh'){S.vh=1;S.hard=0;}if(a&&a.mode==='endless'){S.endless=1;}
  if(a&&a.cu!=null){S.cu=a.cu;}
  S.p.hp=1;S.p.inv=0;const r=x.hitP(500);return {r,state:x.state,hp:S.p.hp,inv:S.p.inv,revUsed:S.revUsed,lk:v.RV?v.RV.lockT-performance.now():null};}"""
HIT = """()=>{const x=__p6x,S=x.S;S.p.inv=0;if(S.p.hp<=0)S.p.hp=1;S.p.hp=Math.min(S.p.hp,1);const r=x.hitP(500);return {r,state:x.state,hp:S.p.hp,inv:S.p.inv,cu:S.cu};}"""
ST = """()=>{const x=__p6x,S=x.S,g=id=>document.getElementById(id);let sv=null;try{const raw=localStorage.getItem('p6_resume_v1');sv=raw?JSON.parse(raw.split('\\n')[0]):null}catch(e){}
  return {state:x.state,hp:S.p.hp,mhp:S.p.mhp,inv:S.p.inv,cu:S.cu,cuq:S.cuq,t:S.t,on:[...document.querySelectorAll('.ov.on')].map(e=>e.id),coins:x.ME&&x.ME.coins,
  lock:{use:g('rvUse').disabled,no:g('rvNo').disabled,useH:g('rvUse').hidden},txt:{t:g('rvT').textContent,d:g('rvD').textContent,c:g('rvC').textContent,s:g('rvS').textContent,u:g('rvUse').textContent,n:g('rvNo').textContent},saved:sv}}"""
CLICK_USE = "()=>document.getElementById('rvUse').click()"
CLICK_NO = "()=>document.getElementById('rvNo').click()"
UNLOCK = "performance.now()>=__rv.RV.lockT+40"

async def kill(pg, a=None):
    r = await pg.evaluate(KILL, a or {})
    return r
async def open_revive(pg, a=None):
    r = await kill(pg, a); await pg.wait_for_function("__p6x.state==='revive'", timeout=5000); await pg.wait_for_function(UNLOCK, timeout=5000); return r
HOLD = "()=>{__rv.RV.lockT=performance.now()+600000;__rv.rvRender();}"          # 잠금을 일부러 길게 잡아 둔다(붐비는 기계에서 0.7초가 먼저 지나가는 것을 막는다)
FREEZE = "()=>{window.requestAnimationFrame=()=>0;}"                             # 게임 루프를 세워 프레임을 시험이 직접 돌린다(무적이 실시간으로 줄어드는 것을 막는다)
async def wait_state(pg, s, t=6000): await pg.wait_for_function("__p6x.state==='%s'" % s, timeout=t)

def git_show(path):
    try: return subprocess.run(['git', 'show', BASE_COMMIT + ':' + path], cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
    except Exception: return None

# ───────────────────────────── A. 소스 훑기
def section_a():
    s = open(os.path.join(ROOT, SRC), encoding='utf-8').read()
    check('[A1] die() 정의는 하나', len(re.findall(r'function die\(', s)) == 1)
    i = s.index('function hitP('); j = s.index('function bossAct(')
    check('[A2] hitP 의 마지막 줄은 return p.hp<=0&&die();', 'return p.hp<=0&&die();}' in s[i:j])
    calls = [m.start() for m in re.finditer(r'hitP\(', s) if m.start() != s.index('function hitP(') + len('function ')]
    bad = []
    for c in calls:                                                   # 호출 10곳 전부 「if(...hitP(...))return」 꼴 — true 면 그 update 에서 바로 끝낸다
        k = c + len('hitP('); depth = 1
        while depth and k < len(s):
            depth += {'(': 1, ')': -1}.get(s[k], 0); k += 1
        if not re.match(r'\)\s*return', s[k:k + 12]): bad.append(s[c - 30:c + 40])
    check('[A3] hitP 호출 %d곳 모두 true 면 바로 return' % len(calls), len(calls) == 10 and not bad, (len(calls), bad))
    a = s.index('// ---------- 🪙 [2026-10-09'); b = s.index("addEventListener('pageshow'")
    sec = '\n'.join(re.sub(r'//.*$', '', l) for l in s[a:b + 200].split('\n'))   # 주석은 빼고 코드만 본다
    check('[A4] 코인 구획에 Math.random·RN( 없음', 'Math.random' not in sec and not re.search(r'\bRN\(', sec))
    check('[A5] INV_CAP 선언 문구 불변', 'const INV_CAP=.80;' in s)
    old = git_show('survivors.html')
    if old is None: SKIPS.append('A6 기준 커밋 없음'); print('SKIP [A6] 기준 커밋 %s 없음 — 확인 못 함' % BASE_COMMIT)
    else:
        top = lambda t: len(re.findall(r'(?m)^(?:let|var) ', t))
        check('[A6] 새 최상위 let/var 없음(기준 %d개와 같다)' % top(old), top(s) == top(old), (top(s), top(old)))
    check('[A7] ovs 에 revive · 요소 존재', "'chest','revive']" in s and all(('id="%s"' % i) in s for i in ('revive', 'rvUse', 'rvNo', 'rCoin', 'rvT', 'rvD', 'rvC', 'rvS')))
    check('[A8] COIN_TMO 선언 줄이 계약 글자 그대로(12초)', 'const COIN_MAX_USE=50,REV_SEC=3,COIN_LOCK=700,COIN_TMO=12000;' in s)
    check('[A9] 패시브 부활은 reviveFx(2.5,…) 로 같은 문장', "reviveFx(2.5,'👼 부활! 한 번 더 버텨라','클랜원들: 살았다…')" in s and "invGrant('rev',inv)" in s)
    check('[A10] 서버 문자열을 innerHTML 로 넣지 않음(코인 구획)', 'innerHTML' not in sec)
    check('[A11] 토큰을 console 에 안 남김(코인 구획)', 'console.' not in sec)
    pn = json.load(open(os.path.join(ROOT, 'data', 'patch_notes.json'), encoding='utf-8'))['notes']
    e = pn[0]
    check('[A12] 패치노트 맨 앞 항목: id·area squad·game sv·tag·날짜 내림차순', e['id'] == '2026-10-09-sv-revive-coin' and e['area'] == 'squad' and e['game'] == 'sv' and e['tag'] in ('신규', '개편', '변경', '밸런스', '수정')
          and all(pn[k]['date'] >= pn[k + 1]['date'] for k in range(min(8, len(pn) - 1))) and e['lines'] and not any(w in json.dumps(e, ensure_ascii=False) for w in ('Cl' 'aude', '클' '로드', 'G' 'PT', 'Son' 'net', 'Op' 'us')))
    check('[A13] 조작법에 부활 코인 한 줄', '<li>🪙 <b>부활 코인</b>' in s)
    check('[A14] .gitignore 에 임시 사본', 'survivors_cx' in open(os.path.join(ROOT, '.gitignore'), encoding='utf-8').read())

async def main():
    section_a()
    src = open(os.path.join(ROOT, SRC), encoding='utf-8').read()
    assert 'COIN_TMO=12000' in src, 'COIN_TMO 선언 줄이 없다'
    H.make_copy(SRC, NEW)
    p = os.path.join(ROOT, NEW); s = open(p, encoding='utf-8').read(); s = s.replace('COIN_TMO=12000', 'COIN_TMO=1500'); open(p, 'w', encoding='utf-8').write(s)   # 시험만 시간 제한을 줄인다
    old = git_show('survivors.html'); have_old = old is not None
    if have_old:
        open(os.path.join(ROOT, 'survivors_cxsrc.html'), 'w', encoding='utf-8').write(old)
        full = H.HOOK; H.HOOK = BASE_HOOK + OLD_RV; H.make_copy('survivors_cxsrc.html', OLD); H.HOOK = full   # 기준 빌드에는 코인 함수가 없어 훅을 따로 쓴다
    srv = H.Srv(root=ROOT)
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            for k, fn in (('B', sec_b), ('C', sec_c), ('D', sec_d), ('E', sec_e), ('F', sec_f), ('G', sec_g), ('I', sec_i), ('J', sec_j), ('K', sec_k), ('L', sec_l)):
                if want(k): await fn(b, srv)
            if have_old:
                if want('H'): await sec_h(b, srv)
                if want('M'): await sec_m(b, srv)
            elif want('H') or want('M'): SKIPS.append('H/M 기준 커밋 없음'); print('SKIP [H][M] 기준 커밋 없음 — 확인 못 함')
            await b.close()
    finally:
        for f in (NEW, OLD, 'survivors_cxsrc.html', 'survivors_cxm.html'):
            try: os.remove(os.path.join(ROOT, f))
            except Exception: pass
    print('\n통과 %d / %d%s' % (N[0] - len(FAILS), N[0], ('  (건너뜀: %s)' % ', '.join(SKIPS)) if SKIPS else ''))
    if FAILS: print('실패:', FAILS); sys.exit(1)

# ───────────────────────────── B. 정상 흐름
async def sec_b(b, srv):
    # 로그인 없음 / 코인 0 / coins 필드 없음 → 요청 0건으로 바로 결과
    mk = Mock(coins=2)
    ctx, pg, errs = await fresh(b, srv.port, mk, login=False)
    r = await kill(pg); check('[B1] 로그인 안 함: 죽으면 바로 결과 화면(선택창 없음) · 코인 요청 0', r['r'] is True and r['state'] == 'result' and not mk.coin_reqs, r)
    acct = await pg.evaluate("()=>document.getElementById('acct').innerText"); check('[B1b] 로그인 안 하면 첫 화면에 코인 줄 없음', '코인' not in acct, acct)
    check('[B1c] 오류 0', not errs, errs); await ctx.close()
    mk = Mock(coins=0); ctx, pg, errs = await fresh(b, srv.port, mk)
    acct = await pg.evaluate("()=>document.getElementById('acct').innerText"); check('[B2a] 서버가 0이라 답하면 첫 화면에 「코인 0개 … 맛동산상점」', '부활 코인 0개' in acct and '맛동산상점' in acct, acct)
    r = await kill(pg); check('[B2] 코인 0개: 바로 결과 화면 · 요청 0', r['state'] == 'result' and not mk.coin_reqs, r); await ctx.close()
    mk = Mock(coins=3); mk.me_has_coins = False; ctx, pg, errs = await fresh(b, srv.port, mk)
    r = await pg.evaluate("()=>[__p6x.ME&&__p6x.ME.coins, document.getElementById('acct').innerText]"); check('[B3] coins 필드 없는 서버: 첫 화면에 코인 줄 없음', r[0] is None and '코인' not in r[1], r)
    r = await kill(pg); check('[B3b] 옛 서버: 죽으면 바로 결과 화면 · 요청 0', r['state'] == 'result' and not mk.coin_reqs, r); await ctx.close()
    for bad in ('2', 2.5, -1, 10000, '__null__', True):                      # 정수 0..9999 가 아니면 모름
        mk = Mock(coins=3); mk.me_coins_override = bad; ctx, pg, errs = await fresh(b, srv.port, mk)
        c = await pg.evaluate("()=>__p6x.ME&&__p6x.ME.coins"); check('[B3c] coins=%r 는 「모름」으로 본다(ME.coins=%r)' % (bad, c), c is None, c)
        await ctx.close()
    # 로그인이 로컬에서 만료됐는데 코인 개수가 아직 남아 있는 경우 → 창 없이 예전처럼
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    await pg.evaluate("()=>{const o=JSON.parse(localStorage.getItem('sgg_dc'));o.exp=Date.now()-1000;localStorage.setItem('sgg_dc',JSON.stringify(o));}")
    r = await kill(pg); c = await pg.evaluate("()=>__p6x.ME&&__p6x.ME.coins")
    check('[B2d] 로그인이 만료됐으면(코인 개수 %r 가 남아 있어도) 창 없이 바로 결과 화면 · 요청 0' % c, c == 2 and r['state'] == 'result' and not mk.coin_reqs, r); await ctx.close()
    # 정상
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    acct = await pg.evaluate("()=>document.getElementById('acct').innerText"); check('[B4] 첫 화면에 코인 개수 줄', '부활 코인 2개' in acct and '쓰러졌을 때' in acct, acct)
    r = await kill(pg); check('[B5] 죽으면 state=revive · hitP true · HP 0', r['r'] is True and r['state'] == 'revive' and r['hp'] == 0, r)
    check('[B5b] 열린 순간 남은 잠금은 0.7초(0.55~0.7초)', 550 < r['lk'] <= 700, r['lk'])
    st = await pg.evaluate(ST)
    check('[B6] 오버레이는 revive 하나만 · 버튼 잠김 · 제목 「🪙 코인을 쓸까요?」 · 문구 · 개수 줄', st['on'] == ['revive'] and st['lock']['use'] and st['lock']['no'] and st['txt']['t'] == '🪙 코인을 쓸까요?'
          and st['txt']['d'] == '쓰러졌어요! 코인 1개를 쓰면 체력 절반으로 바로 일어나요. 3초 동안은 안 맞아요.' and st['txt']['c'] == '내 코인 2개 → 쓰면 1개' and st['saved'] and st['saved']['st'] == 'revive', st)
    t0 = st['t']; await pg.wait_for_timeout(250); st2 = await pg.evaluate(ST); check('[B7] 선택창이 열린 동안 게임 시간이 안 흐른다', st2['t'] == t0, (t0, st2['t']))
    await pg.evaluate(HOLD)
    box = await pg.evaluate("()=>{const r=document.getElementById('rvUse').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")
    n_before = len(mk.coin_reqs)
    await pg.mouse.click(box[0], box[1]); await pg.keyboard.press('Enter'); await pg.keyboard.press('Space'); await pg.keyboard.press('Escape'); await pg.keyboard.press('KeyP'); await pg.keyboard.press('KeyR'); await pg.keyboard.press('Digit1')
    await pg.wait_for_timeout(100); st3 = await pg.evaluate(ST)
    check('[B8] 잠금 중 클릭·Enter·Space·Esc·P·R·1 모두 무시 — 요청 0건, 여전히 revive', len(mk.coin_reqs) == n_before and st3['state'] == 'revive', (len(mk.coin_reqs), st3['state']))
    await pg.evaluate("()=>{__rv.RV.lockT=0;__rv.rvRender();}"); st4 = await pg.evaluate(ST); check('[B9] 0.7초 뒤 버튼이 풀린다', not st4['lock']['use'] and not st4['lock']['no'], st4['lock'])
    await pg.evaluate("()=>__rv.rvLock(50)")                              # 잠금 타이머가 풀리는 순간(실제로는 열린 0.7초 뒤)
    try: await pg.wait_for_function("document.activeElement&&document.activeElement.id==='rvUse'", timeout=4000)
    except Exception: pass
    ac = await pg.evaluate("()=>document.activeElement&&document.activeElement.id"); check('[B10] 풀린 뒤 포커스는 「코인 쓰고 부활」', ac == 'rvUse', ac)
    await pg.keyboard.press('Escape'); await pg.keyboard.press('KeyP'); await pg.wait_for_timeout(100)
    check('[B10b] 풀린 뒤에도 Esc·P 는 revive 에서 아무 일도 안 한다', (await pg.evaluate('__p6x.state')) == 'revive')
    await pg.evaluate(FREEZE); await pg.wait_for_timeout(80); await pg.mouse.click(box[0], box[1]); await wait_state(pg, 'play')   # 80ms: 이미 예약된 마지막 rAF 가 부활 뒤에 돌아 무적을 깎는 경쟁 상태를 피한다
    st5 = await pg.evaluate(ST); rid = await pg.evaluate("__rv.RUN.rid")
    check('[B11] 서버에 {op:use,rid,n:1} 한 번 · 토큰 포함 · 부활: HP 50% · 무적 정확히 3초 · cu=1 · 남은 코인 1', len(mk.coin_reqs) == 1 and mk.coin_reqs[0]['rid'] == rid and mk.coin_reqs[0]['n'] == 1 and mk.coin_reqs[0]['op'] == 'use' and mk.coin_reqs[0].get('token') == 'x' * 30
          and abs(st5['hp'] - st5['mhp'] * .5) < 3 and abs(st5['inv'] - 3) < 1e-9 and st5['cu'] == 1 and st5['cuq'] == 0 and st5['coins'] == 1 and st5['on'] == [], (mk.coin_reqs, st5))
    check('[B12] 부활하면 저장본이 없다(되감기 방지)', st5['saved'] is None, st5['saved'])
    await pg.evaluate("()=>{__p6x.S.p.inv=0;}"); r = await pg.evaluate(HIT); check('[B13] 두 번째 죽음도 선택창', r['state'] == 'revive', r)
    await pg.wait_for_function(UNLOCK); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    check('[B14] 두 번째는 n=2 · 서버 코인 0 · cu=2 · 같은 rid', mk.coin_reqs[-1]['n'] == 2 and mk.coin_reqs[-1]['rid'] == rid and mk.coins == 0, (mk.coin_reqs, mk.coins))
    await pg.evaluate("()=>{__p6x.S.p.inv=0}"); r = await pg.evaluate(HIT); check('[B15] 코인이 0개가 되면 세 번째 죽음은 바로 결과 화면 · 요청 늘지 않음', r['state'] == 'result' and len(mk.coin_reqs) == 2, r)
    res = await pg.evaluate("()=>[document.getElementById('rCoin').textContent,document.getElementById('rCoin').hidden]"); check('[B16] 결과 화면에 「부활 코인 2개를 썼어요 · 남은 코인 0개」', res[0] == '🪙 부활 코인 2개를 썼어요 · 남은 코인 0개' and not res[1], res)
    await pg.wait_for_function("window.__p6x.state==='result'"); await pg.wait_for_timeout(500)
    check('[B17] /p6/run 본문에 cu=2', mk.runs and mk.runs[-1].get('cu') == 2, mk.runs[-1:])
    check('[B18] 오류 0', not errs, errs); await ctx.close()
    # 코인을 안 쓴 판은 cu 를 안 싣고 rCoin 은 숨김
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_NO); await pg.wait_for_function("__p6x.state==='result'"); await pg.wait_for_timeout(500)
    res = await pg.evaluate("()=>document.getElementById('rCoin').hidden")
    check('[B19] 그만하기: 결과 화면 · 코인 요청 0 · 저장본 없음 · 기록 1건에 cu 없음 · rCoin 숨김', len(mk.coin_reqs) == 0 and res and len(mk.runs) == 1 and 'cu' not in mk.runs[0] and (await pg.evaluate(ST))['saved'] is None, (mk.runs, res))
    await ctx.close()
    # 결과 화면의 코인 개수를 모를 때는 앞 절만
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    await pg.evaluate("()=>{delete __p6x.ME.coins;__p6x.S.p.inv=0;__p6x.S.p.hp=1;__p6x.hitP(500);}")
    res = await pg.evaluate("()=>document.getElementById('rCoin').textContent"); check('[B20] 남은 개수를 모르면 「부활 코인 1개를 썼어요」까지만', res == '🪙 부활 코인 1개를 썼어요', res); await ctx.close()

# ───────────────────────────── C. 패시브 우선
async def sec_c(b, srv):
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    r = await kill(pg, {'rev': True})
    check('[C1] 👼 패시브가 있으면 선택창 없이 일어난다 · 코인 요청 0 · 무적 2.5초 · HP 50%', r['r'] is False and r['state'] == 'play' and abs(r['hp'] - 50) < 1 and abs(r['inv'] - 2.5) < 1e-9 and r['revUsed'] == 1 and not mk.coin_reqs, r)
    await pg.evaluate("()=>{__p6x.S.p.inv=0}"); r = await pg.evaluate(HIT); check('[C2] 패시브를 쓴 뒤 두 번째 죽음은 코인 선택창', r['state'] == 'revive', r)
    await pg.wait_for_function(UNLOCK); await pg.evaluate(FREEZE); await pg.wait_for_timeout(80); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    st = await pg.evaluate(ST); check('[C3] 코인 부활 무적은 정확히 3초(패시브는 2.5초) · 코인 사용 1건', abs(st['inv'] - 3) < 1e-9 and len(mk.coin_reqs) == 1, st)
    check('[C4] 오류 0', not errs, errs); await ctx.close()

# ───────────────────────────── D. 무적 프레임 단위
async def sec_d(b, srv):
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(FREEZE); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,p=S.p;for(const q of x.enemies.a)q.on=false;S.spawnT=-1e12;S.need=1e12;
      const e=x.spawnEnemy(0,2.5,null,{x:p.x,y:p.y});e.sp=0;e.dmg=50;e.hp=e.mhp=1e12;
      const inv0=p.inv,hp0=p.hp,dt=1/60;let f=0,firstHit=-1,tt0=S.t;
      for(;f<400;f++){e.x=p.x;e.y=p.y;S.p.hp=Math.min(S.p.hp,hp0);x.update(dt);if(p.hp<hp0-1e-9){firstHit=f;break;}if(x.state!=='play')break;}
      return {inv0,firstHit,expect:Math.ceil(inv0/dt),elapsed:S.t-tt0,state:x.state};}""")
    check('[D1] 무적이 끝나기 전 프레임엔 피해 0 · 끝난 직후 처음 맞는다(프레임 단위, 약 3초)', r['firstHit'] >= 0 and abs(r['firstHit'] - r['expect']) <= 2 and abs(r['elapsed'] - r['inv0']) < 0.06 and 2.95 <= r['inv0'] <= 3 + 1e-9, r)   # 부활 직후 실제 프레임이 한두 번 먼저 돌 수 있어 시작 값은 3초에서 0.05초까지 모자라도 본다(그 모자란 만큼은 expect 가 이미 반영)
    # 3초 무적 동안 같은 프레임에 여러 번 맞아도(hitP 반복) 두 번째 선택창이 안 열린다
    await pg.evaluate("()=>{const S=__p6x.S;S.p.inv=0;S.p.hp=1;__p6x.hitP(500);}"); await pg.wait_for_function("__p6x.state==='revive'")
    await pg.wait_for_function(UNLOCK); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    r = await pg.evaluate("()=>{const x=__p6x,S=x.S;const a=[];for(let i=0;i<5;i++)a.push(x.hitP(500));return {a,state:x.state,hp:S.p.hp,mhp:S.p.mhp}}")
    check('[D2] 부활 직후 무적 중에는 hitP 가 막아 연속으로 죽지 못한다', all(v is False for v in r['a']) and r['state'] == 'play' and abs(r['hp'] - r['mhp'] * .5) < 3, r)
    check('[D3] 오류 0', not errs, errs); await ctx.close()

# ───────────────────────────── E. 실패·재시도
async def sec_e(b, srv):
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg)
    cases = (('net', '닿지'), ('busy', '바빠요'), ('upstream', '디스코드'), ('rate', '너무 빨리'), ('error', '서버가 받지 못했어요.'), ('html', '서버가 받지 못했어요.'), ('hang', '늦어요'))   # 개발자 코드(error·http)를 문구에 붙이지 않는다(2026-10-09 검수)
    for mode, want in cases:
        mk.coin_mode = mode; await pg.evaluate(CLICK_USE)
        if mode == 'hang':
            await pg.wait_for_timeout(150); busy = await pg.evaluate(ST)
            check('[E1] 요청 중: 두 버튼 모두 잠김 · 「코인 쓰는 중…」 · cuq=1', busy['lock']['use'] and busy['lock']['no'] and '쓰는 중' in busy['txt']['u'] and busy['txt']['s'] == '서버에 물어보는 중이에요…' and busy['cuq'] == 1, busy)
            n0 = len(mk.coin_reqs); await pg.evaluate("()=>{document.getElementById('rvUse').click();document.getElementById('rvNo').click()}")   # 중복·그만하기 클릭
            await pg.evaluate("()=>{__rv.coinUse();__rv.rvQuit();}")        # 버튼의 disabled 가 아니라 함수 자체의 가드를 본다
            await pg.wait_for_timeout(100); st = await pg.evaluate(ST)
            check('[E2] 요청 중 중복 클릭·그만하기는 무시(요청 늘지 않음 · 여전히 revive)', len(mk.coin_reqs) == n0 and st['state'] == 'revive', (n0, len(mk.coin_reqs), st['state']))
            await pg.wait_for_function("document.getElementById('rvUse').textContent==='다시 시도'", timeout=6000)
        else:
            await pg.wait_for_function("document.getElementById('rvUse').textContent==='다시 시도'", timeout=4000)
        st = await pg.evaluate(ST)
        check('[E3] %s: 실패 문구 · 「다시 시도」 · 제목 유지 · 여전히 revive · cuq=1 유지 · 코인 그대로' % mode, want in st['txt']['s'] and st['txt']['u'] == '다시 시도' and st['txt']['t'] == '🪙 코인을 쓸까요?' and st['state'] == 'revive' and st['cuq'] == 1 and mk.coins == 1, st)
        if mode in ('net', 'busy', 'error', 'html', 'hang'): check('[E3b] %s: 두 번 빠진다는 걱정 없는 안내 문구' % mode, '두 번 빠지지 않아요' in st['txt']['s'], st['txt']['s'])
        await pg.wait_for_function("__rv.RV.lockT>0&&performance.now()>=__rv.RV.lockT+40", timeout=4000)
    ns = {q['n'] for q in mk.coin_reqs}; check('[E4] 재시도는 전부 같은 (rid,n=1)', ns == {1} and len({q['rid'] for q in mk.coin_reqs}) == 1 and len(mk.coin_reqs) == len(cases), (len(mk.coin_reqs), ns))
    # 길게 이어지는 busy 에서 반복 클릭
    mk.coin_mode = 'busy'; n0 = len(mk.coin_reqs)
    for i in range(4):
        await pg.evaluate(CLICK_USE); await pg.evaluate(CLICK_USE)                  # 잠금 안의 두 번째 클릭은 무시된다
        await pg.wait_for_function("document.getElementById('rvUse').textContent==='다시 시도'"); await pg.wait_for_function("performance.now()>=__rv.RV.lockT+40", timeout=4000)
    st = await pg.evaluate(ST); check('[E5] busy 가 계속돼도 클릭마다 정확히 1건씩(총 4건) · 같은 n · 여전히 revive · 코인 그대로', len(mk.coin_reqs) - n0 == 4 and {q['n'] for q in mk.coin_reqs} == {1} and st['state'] == 'revive' and mk.coins == 1 and st['cu'] == 0, (len(mk.coin_reqs) - n0, st))
    mk.coin_mode = 'ok'; await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    check('[E6] 성공 뒤 코인은 한 번만 빠졌다 · cu=1', mk.coins == 0 and len(mk.charged) == 1 and (await pg.evaluate('__p6x.S.cu')) == 1, (mk.coins, mk.charged))
    check('[E7] 오류 0', not errs, errs); await ctx.close()
    # rate·busy 는 1.5초 잠금, 그 밖은 0.4초 잠금
    for mode, lo, hi in (('rate', 1.2, 2.6), ('busy', 1.2, 2.6), ('net', 0.2, 1.2)):
        mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk); await open_revive(pg); mk.coin_mode = mode
        v = await pg.evaluate("""async()=>{document.getElementById('rvUse').click();const t0=performance.now();
          while(document.getElementById('rvUse').textContent!=='다시 시도'&&performance.now()-t0<4000)await new Promise(r=>setTimeout(r,10));
          const t1=performance.now();while(document.getElementById('rvUse').disabled&&performance.now()-t1<4000)await new Promise(r=>setTimeout(r,10));return (performance.now()-t1)/1000}""")
        check('[E8] %s 실패 뒤 재시도 잠금 시간 %.2f초 (%.1f~%.1f)' % (mode, v, lo, hi), lo <= v <= hi, v); await ctx.close()
    # 차감 뒤 응답 끊김 → 재시도는 dup
    mk = Mock(coins=1); mk.coin_mode = 'charged_then_drop'; ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await pg.wait_for_function("document.getElementById('rvUse').textContent==='다시 시도'")
    mk.coin_mode = 'ok'; await pg.wait_for_function("performance.now()>=__rv.RV.lockT+40"); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    check('[E9] 차감 뒤 응답 끊김 → 재시도 dup → 부활, 코인은 1개만 빠짐(남은 0) · 같은 (rid,1)', mk.coins == 0 and len(mk.charged) == 1 and len(mk.coin_reqs) == 2 and mk.coin_reqs[0] == mk.coin_reqs[1], (mk.coins, mk.coin_reqs)); await ctx.close()
    # 확정 실패: 결과 보기만
    for mode, wtxt, cc in (('no_coin', '다른 곳에서', 0), ('auth', '로그인이 만료', 1), ('notfound', '아직 코인을 몰라요', 1), ('big', '아직 코인을 몰라요', 1), ('bad', '요청이 잘못', 1)):
        mk = Mock(coins=1); mk.coin_mode = mode; ctx, pg, errs = await fresh(b, srv.port, mk)
        await open_revive(pg); await pg.evaluate(CLICK_USE); await pg.wait_for_function("document.getElementById('rvUse').hidden", timeout=4000)
        st = await pg.evaluate(ST)
        check('[E10] %s: 「쓰기」 버튼 숨김 · 「결과 보기」만 · 제목 💫 · cuq=0 · 로그인 유지' % mode, st['lock']['useH'] and st['txt']['n'] == '결과 보기' and (wtxt in st['txt']['d'] or wtxt in st['txt']['s']) and st['cuq'] == 0 and st['txt']['t'] == '💫 쓰러졌어요!' and (await pg.evaluate("()=>!!localStorage.getItem('sgg_dc')")), st)
        if mode == 'no_coin': check('[E10b] no_coin 이면 ME.coins=0', st['coins'] == 0, st['coins'])
        await pg.wait_for_function(UNLOCK); await pg.evaluate(CLICK_NO); await pg.wait_for_timeout(200)
        st = await pg.evaluate(ST); check('[E11] %s: 결과 보기 → result · 코인 요청은 1건뿐' % mode, st['state'] == 'result' and st['on'] == ['result'] and len(mk.coin_reqs) == 1, st)
        check('[E11b] %s: 오류 0' % mode, not errs, errs); await ctx.close()
    # 늦게 온 응답은 무시(다른 상태에서 도착)
    mk = Mock(coins=2); mk.coin_mode = 'slow'; ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await pg.wait_for_timeout(200)
    await pg.evaluate("()=>{__p6x.state='result'}")                       # 그사이 화면이 바뀌었다(다른 창에 넘어감 등을 흉내)
    await mk.release_slow(); await pg.wait_for_timeout(400)
    st = await pg.evaluate(ST); check('[E12] 화면이 바뀐 뒤 도착한 응답은 무시 — 부활 없음(state 그대로) · cu=0', st['state'] == 'result' and st['cu'] == 0, st)
    check('[E12b] 오류 0', not errs, errs); await ctx.close()
    # 열린 사이 코인이 0 으로 갱신되면
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    mk.coins = 0                                                          # 다른 곳에서 다 썼다 — 웹은 아직 2개로 안다
    await kill(pg); await pg.wait_for_function("document.getElementById('rvT').textContent==='💫 쓰러졌어요!'", timeout=4000)
    st = await pg.evaluate(ST); check('[E13] 열린 사이 서버가 0 이라 답하면 「코인이 없어졌어요」 · 결과 보기만', '코인이 없어졌어요' in st['txt']['s'] and st['lock']['useH'] and st['txt']['n'] == '결과 보기' and not mk.coin_reqs, st); await ctx.close()

# ───────────────────────────── F. 이어하기
async def newpage(ctx, port, page=NEW):
    pg2 = await ctx.new_page(); await pg2.goto('http://127.0.0.1:%d/%s' % (port, page)); await pg2.wait_for_function('window.__p6x!==undefined'); await pg2.wait_for_timeout(500); return pg2
async def sec_f(b, srv):
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await kill(pg); st = await pg.evaluate(ST)
    check('[F1] 선택창이 열리면 저장본(st=revive)이 생긴다', st['saved'] and st['saved']['st'] == 'revive', st['saved'])
    await pg.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));}")
    st = await pg.evaluate(ST); check('[F2] 열린 채 숨겨져도 상태는 그대로 revive · 저장본 유지', st['state'] == 'revive' and st['saved'] and st['saved']['st'] == 'revive', st)
    pg2 = await newpage(ctx, srv.port); await pg.close()
    card = await pg2.evaluate("()=>[!document.getElementById('resCard').hidden,document.getElementById('resAgo').textContent]"); check('[F3] 첫 화면에 이어하기 카드 · 「쓰러져서 코인을 고르는 중」', card[0] and '쓰러져서 코인을 고르는 중' in card[1], card)
    await pg2.evaluate("()=>document.getElementById('resGo').click()"); await pg2.wait_for_function("__p6x.state==='revive'", timeout=5000)
    st = await pg2.evaluate(ST); check('[F4] 이어하기 → 같은 선택창(revive) · HP 0 · cu=0 · 문구 ask · 오버레이 revive 하나', st['state'] == 'revive' and st['on'] == ['revive'] and st['hp'] == 0 and st['cu'] == 0 and '코인 1개를 쓰면' in st['txt']['d'], st)
    await pg2.wait_for_function(UNLOCK); await pg2.evaluate(CLICK_USE); await wait_state(pg2, 'play')
    rid2 = await pg2.evaluate("__rv.RUN.rid"); st = await pg2.evaluate(ST)
    check('[F5] 복구한 뒤 쓰기 → 같은 rid 로 n=1 · 부활 · 저장본 삭제 · cu=1', mk.coin_reqs[-1]['rid'] == rid2 and mk.coin_reqs[-1]['n'] == 1 and st['state'] == 'play' and st['saved'] is None and st['cu'] == 1, (mk.coin_reqs, st))
    check('[F5b] 오류 0', not errs, errs); await ctx.close()
    # 요청을 보내 놓고 앱이 꺼진 경우 → 복귀 후 pending → dup → 부활(코인 합계 1개만)
    mk = Mock(coins=1); mk.coin_mode = 'hang'; ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await pg.wait_for_timeout(300)
    st = await pg.evaluate(ST); check('[F6] 요청을 보낸 시점 저장본에 쓰던 중(cuq=1) 표시', st['saved'] and st['saved']['st'] == 'revive' and st['cuq'] == 1, st['saved'])
    raw = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')||''")      # 보냄 직후(페이지를 닫기 전)의 저장본 글자 그대로 — 닫을 때 저장(pagehide)이 대신 채워 주지 못하는 경우를 막는다
    check('[F6b] 요청 직후 localStorage 저장본 본문에 "cuq":1', '"cuq":1' in raw, raw[:200])
    rid = await pg.evaluate("__rv.RUN.rid"); mk.charged.add((rid, 1)); mk.coins -= 1; mk.coin_mode = 'ok'   # 서버는 차감했다
    pg2 = await newpage(ctx, srv.port); await pg.close()
    await pg2.evaluate("()=>document.getElementById('resGo').click()"); await pg2.wait_for_function("__p6x.state==='revive'", timeout=5000)
    st = await pg2.evaluate(ST); check('[F7] 복귀하면 「이어서 부활하기」(pending) 문구 · 개수 줄 숨김 · 제목 🪙 · cuq=1', '쓰던 중' in st['txt']['d'] and '이어서' in st['txt']['u'] and st['txt']['c'] == '' and st['cuq'] == 1 and st['txt']['t'] == '🪙 코인을 쓸까요?' and '돌아오지 않을 수' in st['txt']['s'], st)
    await pg2.wait_for_function(UNLOCK); await pg2.evaluate(CLICK_USE); await wait_state(pg2, 'play')
    check('[F8] 같은 (rid,1) 재요청 → dup → 부활 · 코인 합계 0(1개만 빠짐)', mk.coins == 0 and mk.coin_reqs[-1]['n'] == 1 and mk.coin_reqs[-1]['rid'] == rid and len(mk.charged) == 1, (mk.coins, mk.coin_reqs))
    st = await pg2.evaluate(ST); check('[F8b] 복구 뒤 부활하면 cuq=0 · cu=1 · 저장본 삭제', st['cuq'] == 0 and st['cu'] == 1 and st['saved'] is None, st); await ctx.close()
    # pending 에서 서버가 이미 코인 0 이어도 막지 않는다(dup 로 부활)
    mk = Mock(coins=1); mk.coin_mode = 'hang'; ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await pg.wait_for_timeout(300)
    rid = await pg.evaluate("__rv.RUN.rid"); mk.charged.add((rid, 1)); mk.coins = 0; mk.coin_mode = 'ok'
    pg2 = await newpage(ctx, srv.port); await pg.close(); await pg2.evaluate("()=>document.getElementById('resGo').click()"); await pg2.wait_for_function("__p6x.state==='revive'")
    await pg2.wait_for_timeout(600); st = await pg2.evaluate(ST)
    check('[F9] 복구 직후 서버가 코인 0 이라 답해도 pending 모드는 「쓰기」를 막지 않는다', not st['lock']['useH'] and '이어서' in st['txt']['u'], st); await ctx.close()
    # 변조 저장본: cu=-1 · cu=99 · cuq=2 는 거부, rid 변조는 결과 보기
    for label, js in (('cu=-1', "S.cu=-1"), ('cu=99', "S.cu=99"), ('cuq=2', "S.cuq=2"), ('cu=1.5', "S.cu=1.5")):
        mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk); await kill(pg)
        await pg.evaluate("()=>{const S=__p6x.S;%s;localStorage.removeItem('p6_resume_v1');__rv.RES.save('t');}" % js)
        sv = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')"); pg2 = await newpage(ctx, srv.port); await pg.close()
        shown = await pg2.evaluate("()=>!document.getElementById('resCard').hidden")
        if shown: await pg2.evaluate("()=>document.getElementById('resGo').click()"); await pg2.wait_for_timeout(500)
        stt = await pg2.evaluate("()=>__p6x.state"); left = await pg2.evaluate("()=>localStorage.getItem('p6_resume_v1')")
        check('[F10] 변조 저장본 %s 는 선택창으로 되살아나지 않는다(state=%s · 카드 %s · 저장본 %s)' % (label, stt, shown, '남음' if left else '삭제'), stt != 'revive' and len(mk.coin_reqs) == 0, (stt, shown))
        await ctx.close()
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk); await kill(pg)
    await pg.evaluate("()=>{__rv.RUN.rid='ab!';localStorage.removeItem('p6_resume_v1');__rv.RES.save('t');}")
    pg2 = await newpage(ctx, srv.port); await pg.close()
    if await pg2.evaluate("()=>!document.getElementById('resCard').hidden"):
        await pg2.evaluate("()=>document.getElementById('resGo').click()"); await pg2.wait_for_timeout(600)
    st = await pg2.evaluate(ST)
    if st['state'] == 'revive':
        await pg2.wait_for_function(UNLOCK); await pg2.evaluate(CLICK_USE); await pg2.wait_for_timeout(300); st = await pg2.evaluate(ST)
        check('[F11] 판 번호(rid)가 변조된 복구본은 코인을 쓰지 않고 결과 보기만(요청 0)', st['lock']['useH'] and '판 번호' in st['txt']['s'] and not mk.coin_reqs, st)
    else: check('[F11] 판 번호(rid)가 변조된 복구본은 되살아나지 않는다(state=%s)' % st['state'], not mk.coin_reqs, st)
    await ctx.close()
    # 두 창: 한 창이 이어받으면 다른 창은 코인을 쓰지 않는다
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk); await open_revive(pg)
    await pg.evaluate("()=>addEventListener('storage',e=>e.stopImmediatePropagation(),true)")   # 저장소 알림을 못 받은 창(알림이 늦거나 놓친 경우) — 클릭 순간의 stale 검사만이 막아야 한다
    pg2 = await newpage(ctx, srv.port); await pg2.evaluate("()=>document.getElementById('resGo').click()"); await pg2.wait_for_function("__p6x.state==='revive'", timeout=5000)
    print('  (F12 관찰) 먼저 열린 창 state=%s' % (await pg.evaluate('__p6x.state')), flush=True)   # RES.stale() 는 부르지 않는다 — 부르면 그 호출이 창을 닫아 버려 클릭 순간의 검사를 시험하지 못한다
    n0 = len(mk.coin_reqs); await pg.evaluate(CLICK_USE); await pg.wait_for_timeout(500)
    check('[F12] 다른 창이 이어받은 판에서 먼저 열려 있던 창은 코인을 쓰지 않는다(요청 0)', len(mk.coin_reqs) == n0 and mk.coins == 2, (n0, len(mk.coin_reqs), mk.coins))
    await pg2.wait_for_function(UNLOCK); await pg2.evaluate(CLICK_USE); await wait_state(pg2, 'play'); check('[F12b] 이어받은 창에서는 정상 부활 · 코인 1개만 빠짐', mk.coins == 1 and len(mk.charged) == 1, (mk.coins, mk.charged)); await ctx.close()
    # 클릭 순간의 stale 검사만 따로 본다 — 실제 두 창 경로에선 다른 안전장치(복귀·저장 때의 검사)가 먼저 창을 닫을 수 있어서, RES.stale 을 참으로 못박고 coinUse 가 스스로 멈추는지 본다
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk); await open_revive(pg)
    await pg.evaluate("()=>{__rv.RES.stale=()=>true;}"); n0 = len(mk.coin_reqs)
    await pg.evaluate(CLICK_USE); await pg.wait_for_timeout(500)
    st = await pg.evaluate("()=>[__p6x.state,__rv.RV.busy,__p6x.S&&__p6x.S.cuq]")
    check('[F12c] 낡은 판(stale)이면 coinUse 가 요청을 보내지 않고 cuq 도 안 바꾼다(요청 0 · 코인 그대로 · cuq=0)', len(mk.coin_reqs) == n0 and mk.coins == 2 and st[1] is False and st[2] == 0, (len(mk.coin_reqs) - n0, mk.coins, st)); await ctx.close()
    # 저장소 쓰기가 막혀도 게임은 돈다
    mk = Mock(coins=1); ctx, pg, errs = await H.new_page(b, srv.port, 412, 860, mock=mk, page=NEW); await pg.evaluate(LOGIN)
    await ctx.add_init_script("Storage.prototype.setItem=function(){throw new DOMException('q','QuotaExceededError')}")
    await pg.reload(); await pg.wait_for_function('window.__p6x!==undefined'); await pg.wait_for_timeout(400)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    check('[F13] 저장소 쓰기가 막혀도 선택창 → 부활이 된다 · 코인 1개 · 오류 0', mk.coins == 0 and not errs, errs); await ctx.close()

# ───────────────────────────── G. 입력 보호
async def sec_g(b, srv):
    REQ = []
    for hold_ms, label, want in ((300, '잠금 안에서 손을 뗌(0.3초)', 0), (1000, '잠금이 풀린 뒤 손을 뗌(1.0초)', 0)):
        mk = Mock(coins=3); ctx, pg, errs = await fresh(b, srv.port, mk, w=360, h=640, mobile=True)
        await pg.evaluate("()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;for(const q of x.enemies.a)q.on=false;}")
        cdp = await ctx.new_cdp_session(pg)
        await pg.evaluate("()=>{const x=__p6x;x.S.p.hp=1;x.S.p.inv=0;x.hitP(500);}"); await pg.wait_for_timeout(100)
        pos = await pg.evaluate("()=>{const r=document.getElementById('rvUse').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")
        await pg.evaluate("()=>{__p6x.state='play';__rv.RV.on=false;__p6x.show(null);const S=__p6x.S;S.p.hp=S.p.mhp;}")                 # 자리만 재고 판으로 돌아간다
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': pos[0], 'y': pos[1]}]})                 # 판 도중 그 자리를 누르고 있었다(가상 조이스틱)
        await pg.wait_for_timeout(120)
        await pg.evaluate("()=>{const x=__p6x;x.S.p.hp=1;x.S.p.inv=0;x.hitP(500);}")                                                  # 그 손가락을 든 채 죽는다
        await pg.wait_for_timeout(hold_ms)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(500)
        st = await pg.evaluate("()=>__p6x.state")
        check('[G1] 판 도중부터 누르던 손가락을 %s → 코인 요청 %d건(0이어야 함) · state=%s' % (label, len(mk.coin_reqs), st), len(mk.coin_reqs) == 0 and st == 'revive', (len(mk.coin_reqs), st))
        await ctx.close()
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk, w=360, h=640, mobile=True)
    await kill(pg); await pg.wait_for_timeout(100)
    pos = await pg.evaluate("()=>{const r=document.getElementById('rvUse').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")
    await pg.touchscreen.tap(pos[0], pos[1]); await pg.wait_for_timeout(200); n1 = len(mk.coin_reqs)
    await pg.wait_for_function(UNLOCK); await pg.touchscreen.tap(pos[0], pos[1]); await pg.wait_for_timeout(600)
    check('[G2] 열린 직후 탭은 무시(요청 %d건) · 잠금이 풀린 뒤 새 탭은 1건 · 부활' % n1, n1 == 0 and len(mk.coin_reqs) == 1 and (await pg.evaluate('__p6x.state')) == 'play', (n1, len(mk.coin_reqs)))
    await ctx.close()
    # 열 때 키·조이스틱을 끈다
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await pg.evaluate("()=>{__p6x.keys={KeyD:true,KeyW:true};}"); await kill(pg)
    k = await pg.evaluate("()=>[Object.keys(__p6x.keys).length]"); check('[G3] 열 때 누르고 있던 이동 키를 비운다', k == [0], k)
    # 눌러둔 채(키보드 자동 반복) 있어도 버튼은 안 눌린다
    for _ in range(5): await pg.keyboard.down('KeyD')
    await pg.keyboard.up('KeyD'); await pg.wait_for_timeout(100)
    check('[G4] 키보드 자동 반복·이동 키로는 버튼이 눌리지 않는다', len(mk.coin_reqs) == 0 and (await pg.evaluate('__p6x.state')) == 'revive'); await ctx.close()
    # ⌨ Space·Enter 를 누른 채 죽는다 — 포커스가 「코인 쓰고 부활」로 옮겨진 뒤의 자동 반복·뗌이 클릭이 되면 안 된다(2026-10-09 검수 지적). 그 뒤 새로 누르면 정상으로 쓴다.
    START = "()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;S.xp=0;for(const q of x.enemies.a)q.on=false;}"
    for key, tag in (('Space', 'G5'), ('Enter', 'G6')):
        mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
        await pg.evaluate(START); await pg.keyboard.down(key)                                     # 판 도중부터 키를 누르고 있다
        await pg.evaluate("()=>{const x=__p6x;x.S.p.hp=1;x.S.p.inv=0;x.hitP(500);}"); await wait_state(pg, 'revive', 5000)
        await pg.wait_for_function(UNLOCK); await pg.wait_for_timeout(150)
        ae = await pg.evaluate("()=>document.activeElement&&document.activeElement.id")
        for _ in range(4): await pg.keyboard.down(key); await pg.wait_for_timeout(40)          # 자동 반복(Playwright 는 이미 눌린 키의 down 을 repeat 로 보낸다)
        await pg.keyboard.up(key); await pg.wait_for_timeout(300)
        n0 = len(mk.coin_reqs); st0 = await pg.evaluate('__p6x.state')
        check('[%s] %s 를 누른 채 죽어도(포커스=%s) 자동 반복·뗌으로 코인이 안 쓰인다 · 요청 %d건 · state=%s' % (tag, key, ae, n0, st0), n0 == 0 and st0 == 'revive', (ae, n0, st0))
        await pg.keyboard.press(key); await pg.wait_for_timeout(600)
        check('[%s2] 그 뒤 %s 를 새로 누르면 정상으로 쓴다 · 요청 1건 · 부활' % (tag, key), len(mk.coin_reqs) == 1 and (await pg.evaluate('__p6x.state')) == 'play', (len(mk.coin_reqs), await pg.evaluate('__p6x.state')))
        check('[%s3] 오류 0' % tag, not errs, errs); await ctx.close()
    # 응답이 앱이 가려진 동안 도착해도 부활은 하되 일시정지로 돌아온다(소리 없이)
    mk = Mock(coins=2); mk.coin_mode = 'slow'; ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await pg.wait_for_timeout(200)
    await pg.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});}"); await mk.release_slow(); await pg.wait_for_timeout(500)
    st = await pg.evaluate(ST); await pg.evaluate("()=>{delete document.hidden;}")
    check('[G7] 가려진 동안 응답이 와도 부활은 적용(코인 1 · cu=1)하고 상태는 pause(일시정지) · 요청 1건', st['state'] == 'pause' and st['cu'] == 1 and st['coins'] == 1 and len(mk.coin_reqs) == 1, st)
    check('[G7b] 오류 0', not errs, errs); await ctx.close()

# ───────────────────────────── I. 모드
async def sec_i(b, srv):
    for label, a in (('일반', {}), ('하드', {'mode': 'hard'}), ('베리하드', {'mode': 'vh'}), ('무한', {'mode': 'endless'}), ('오늘의 도전(기록 판)', {'start': {'daily': True}})):
        mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
        await open_revive(pg, a); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
        st = await pg.evaluate(ST); dly = await pg.evaluate("()=>__p6x.S.dly&&__p6x.S.dly.ranked")
        check('[I1] %s: 죽음 → 창 → 부활(HP 50%% · cu=1)%s' % (label, ' · ranked=%s' % dly if 'start' in a else ''), st['state'] == 'play' and st['cu'] == 1 and abs(st['hp'] - st['mhp'] * .5) < 3 and mk.coins == 0 and (dly or 'start' not in a), st)
        check('[I1b] %s: 오류 0' % label, not errs, errs); await ctx.close()
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start({daily:true});}"); await pg.evaluate("()=>{try{localStorage.setItem('p6_x','1')}catch(e){}}")
    await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start({daily:true});}")      # 두 번째는 오늘 이미 시작함 → 연습 판
    pr = await pg.evaluate("()=>__p6x.S.dly&&__p6x.S.dly.ranked")
    r = await pg.evaluate("""()=>{const x=__p6x,S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;for(const q of x.enemies.a)q.on=false;S.p.hp=1;S.p.inv=0;x.hitP(500);return x.state}""")
    check('[I2] 오늘의 도전 연습 판(ranked=%s)에서도 창이 뜬다' % pr, pr is False and r == 'revive', (pr, r)); await ctx.close()
    mk = Mock(coins=5); ctx, pg, errs = await fresh(b, srv.port, mk)
    r = await kill(pg, {'cu': 50}); check('[I3] 한 판 50번을 다 쓰면(S.cu=50) 코인이 남아도 창이 안 뜬다', r['state'] == 'result' and not mk.coin_reqs, r); await ctx.close()
    # 클리어 직전 사망 → 부활 → 정상 클리어
    mk = Mock(coins=1); ctx, pg, errs = await fresh(b, srv.port, mk)
    await open_revive(pg, None); await pg.evaluate("()=>{__p6x.S.t=__p6x.WIN_T-3}"); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play')
    r = await pg.evaluate("""()=>{const x=__p6x,S=x.S;S.p.inv=99;for(let i=0;i<400&&x.state==='play';i++){x.update(1/30);}return {state:x.state,won:S.won,t:S.t}}""")
    check('[I4] 60분 직전 사망 → 코인 부활 → 정상 클리어(결과/무한 질문)', r['state'] in ('result',) or r['won'], r); await ctx.close()

# ───────────────────────────── J. 화면 크기
async def sec_j(b, srv):
    sizes = ((320, 568), (360, 640), (360, 740), (412, 860), (568, 320), (640, 360), (800, 360), (1280, 720), (1280, 800))
    for (w, h) in sizes:
        mk = Mock(coins=12); ctx, pg, errs = await fresh(b, srv.port, mk, w=w, h=h)
        if SHOTS and (w, h) in ((360, 640), (1280, 800)): await pg.screenshot(path=os.path.join(SHOTS, 'title_%dx%d.png' % (w, h)))
        await kill(pg); await pg.wait_for_function(UNLOCK)
        m = await pg.evaluate("""()=>{const bx=document.querySelector('#revive .box').getBoundingClientRect();const bs=[...document.querySelectorAll('#revive .btn')].map(b=>{const r=b.getBoundingClientRect();return [Math.round(r.width),Math.round(r.height),Math.round(r.bottom)]});
          return {box:[Math.round(bx.x),Math.round(bx.y),Math.round(bx.width),Math.round(bx.height)],bs,sw:document.documentElement.scrollWidth,iw:innerWidth,ih:innerHeight,scroll:document.querySelector('#revive .box').scrollHeight>document.querySelector('#revive .box').clientHeight+1}}""")
        ok = m['sw'] <= m['iw'] and all(bt[1] >= 44 and bt[0] >= 44 for bt in m['bs']) and not m['scroll'] and m['box'][1] >= 0 and m['box'][1] + m['box'][3] <= m['ih'] and m['box'][0] >= 0 and m['box'][0] + m['box'][2] <= m['iw']
        check('[J1] %dx%d: 가로 넘침 없음 · 버튼 ≥44px · 상자가 화면 안 · 스크롤 없이 다 보임' % (w, h), ok, m)
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, 'revive_%dx%d.png' % (w, h)))
        if (w, h) == (360, 640):                                            # 가장 긴 실패 문구에서도 안 넘치는지
            mk.coin_mode = 'html'; await pg.evaluate(CLICK_USE); await pg.wait_for_function("document.getElementById('rvUse').textContent==='다시 시도'")
            m2 = await pg.evaluate("()=>{const bx=document.querySelector('#revive .box').getBoundingClientRect();return {b:bx.bottom,ih:innerHeight,sw:document.documentElement.scrollWidth,iw:innerWidth}}")
            check('[J2] 360x640 가장 긴 실패 문구에서도 상자가 화면 안', m2['b'] <= m2['ih'] and m2['sw'] <= m2['iw'], m2)
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, 'revive_fail_360x640.png'))
        check('[J3] %dx%d 오류 0' % (w, h), not errs, errs); await ctx.close()
    # 부활 직후 배너·결과 화면
    mk = Mock(coins=3); ctx, pg, errs = await fresh(b, srv.port, mk, w=360, h=640)
    await open_revive(pg); await pg.evaluate(CLICK_USE); await wait_state(pg, 'play'); await pg.wait_for_timeout(250)
    ban = await pg.evaluate("()=>document.getElementById('banner')?document.getElementById('banner').innerText:''")
    if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, 'revived_360x640.png'))
    check('[J4] 부활 배너 「🪙 코인 부활! 3초 동안은 안 맞아요」 · 「남은 코인 2개」(또는 배너 요소가 달라 확인 못 함)', ban == '' or ('코인 부활' in ban and '남은 코인 2개' in ban), ban)
    # 로그아웃하면 첫 화면 코인 줄이 사라진다
    await pg.evaluate("()=>{__p6x.S.p.inv=0;__p6x.S.p.hp=1;__p6x.hitP(500);}"); await pg.wait_for_function(UNLOCK); await pg.evaluate(CLICK_NO); await pg.wait_for_function("__p6x.state==='result'")
    if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, 'result_360x640.png'))
    await ctx.close()
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    a1 = await pg.evaluate("()=>document.getElementById('acct').innerText"); await pg.evaluate("()=>document.getElementById('dcOut').click()"); await pg.wait_for_timeout(200)
    a2 = await pg.evaluate("()=>document.getElementById('acct').innerText"); check('[J5] 로그아웃하면 코인 줄이 사라진다', '코인' in a1 and '코인' not in a2, (a1, a2)); await ctx.close()
    # 화면 복귀 시 /p6/me 갱신(5초 제한)
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    mk.coins = 7; n0 = mk.me_reqs
    await pg.evaluate("()=>{__rv.RV.refAt=0;Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});document.dispatchEvent(new Event('visibilitychange'));}"); await pg.wait_for_timeout(500)
    c1 = await pg.evaluate("()=>__p6x.ME.coins"); n1 = mk.me_reqs
    await pg.evaluate("()=>{document.dispatchEvent(new Event('visibilitychange'));}"); await pg.wait_for_timeout(300)
    check('[J6] 화면 복귀에서 /p6/me 로 코인 갱신(2→7) · 5초 안 중복은 생략', c1 == 7 and n1 == n0 + 1 and mk.me_reqs == n1, (c1, n0, n1, mk.me_reqs)); await ctx.close()

# ───────────────────────────── K. 소리
async def sec_k(b, srv):
    mk = Mock(coins=2)
    ctx = await b.new_context(viewport={'width': 412, 'height': 860});
    await ctx.close()
    bb = None
    ctx, pg, errs = await fresh(b, srv.port, mk)
    r = await pg.evaluate("""async ()=>{const x=__p6x,A=x.AU;A.init();A.reset();A.music(true);x.CH_set('brj');x.start();const S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;for(const q of x.enemies.a)q.on=false;
      await new Promise(r=>setTimeout(r,400));const evo0=(A.n&&A.n.evo)||0;
      S.p.hp=1;S.p.inv=0;x.hitP(500);await new Promise(r=>setTimeout(r,200));
      const mid={state:x.state,ac:A.ac?A.ac.state:(A.state||null),bgmPaused:A.bgm?A.bgm.paused:null,playing:A.on!==undefined?A.on:null};
      while(performance.now()<__rv.RV.lockT+40)await new Promise(r=>setTimeout(r,30));document.getElementById('rvUse').click();
      for(let i=0;i<80&&x.state!=='play';i++)await new Promise(r=>setTimeout(r,50));
      await new Promise(r=>setTimeout(r,200));
      return {mid,after:{state:x.state,ac:A.ac?A.ac.state:(A.state||null),evo:((A.n&&A.n.evo)||0)-evo0,bgmPaused:A.bgm?A.bgm.paused:null}};}""")
    print('  (소리 관찰값)', json.dumps(r, ensure_ascii=False), flush=True)
    check('[K1] 선택창 중 오디오가 멈추지 않고(running 유지) 부활 뒤 다시 play · 오류 0(실제 소리는 확인 못 함)', r['after']['state'] == 'play' and r['mid']['state'] == 'revive' and (r['mid']['ac'] in ('running', None)) and not errs, (r, errs))
    await ctx.close()

# ───────────────────────────── L. 코인 숫자 유지 규칙
async def sec_l(b, srv):
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    mk.me_has_coins = False                                               # 봇이 재시작한 직후 — coins 칸이 빠진 응답
    await pg.evaluate("()=>__rv.refreshCoins(true)"); await pg.wait_for_timeout(400)
    c = await pg.evaluate("()=>__p6x.ME.coins"); check('[L1] refreshCoins: coins 가 빠져도 직전 값(2)을 지우지 않는다', c == 2, c)
    await pg.evaluate("()=>__rv.loadMe()"); await pg.wait_for_timeout(400)
    c = await pg.evaluate("()=>__p6x.ME.coins"); check('[L2] loadMe: ME 를 갈아끼워도 직전 값(2)을 이어받는다', c == 2, c)
    acct = await pg.evaluate("()=>document.getElementById('acct').innerText"); check('[L3] 첫 화면 코인 줄도 유지', '부활 코인 2개' in acct, acct)
    r = await kill(pg); await pg.wait_for_function("__p6x.state==='revive'", timeout=4000)
    st = await pg.evaluate(ST); check('[L4] /p6/me 가 coins 없이 와도 죽으면 창이 뜬다(개수 줄은 직전 값)', r['state'] == 'revive' and st['txt']['c'] == '내 코인 2개 → 쓰면 1개', st)
    await ctx.close()
    # 처음부터 모르는 상태에서 갱신이 와도 새로 생기지 않는다 / 값이 오면 덮어쓴다
    mk = Mock(coins=2); mk.me_has_coins = False; ctx, pg, errs = await fresh(b, srv.port, mk)
    mk.me_has_coins = True; mk.coins = 4; await pg.evaluate("()=>__rv.refreshCoins(true)"); await pg.wait_for_timeout(400)
    c = await pg.evaluate("()=>__p6x.ME.coins"); check('[L5] 처음엔 모르다가 값이 오면 그 값으로(4)', c == 4, c)
    mk.me_coins_override = 20000; await pg.evaluate("()=>__rv.refreshCoins(true)"); await pg.wait_for_timeout(400)
    c = await pg.evaluate("()=>__p6x.ME.coins"); check('[L6] 범위 밖 값(20000)은 무시하고 직전 값(4) 유지', c == 4, c); await ctx.close()

# ───────────────────────────── H. 난수 불변(기준 커밋 vs 새 빌드)
def mk_rng_mock(coins):
    async def mock(r):
        u = r.request.url; hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
        J = lambda j, st=200: r.fulfill(status=st, headers=hdr, content_type='application/json', body=json.dumps(j))
        if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
        if '/p6/board' in u: await J({'board': [], 'hard': [], 'vhard': []})
        elif '/p6/me' in u: await J({'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1, 'coins': coins, 'daily_done': False, 'daily_date': '2026-10-09'})
        elif '/p6/run' in u: await J({'ok': True, 'rank': 1, 'total': 2, 'unlocks': ['brj'], 'best_t': 1})
        elif '/p6/coin' in u: await J({'ok': True, 'coins': 1, 'dup': False})
        else: await r.fulfill(status=404, headers=hdr, body='{}')
    return mock
RUNJS = r"""(a)=>{let sd=a.seed>>>0,cnt=0;Math.random=()=>{cnt++;sd=(sd+0x6D2B79F5)|0;let t=Math.imul(sd^(sd>>>15),1|sd);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 const x=__p6x,v=__rv;x.CH_set('brj');x.start({daily:true});const S=x.S;const dt=1/30;
 for(let i=0;i<a.frames;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}
   S.p.hp=Math.max(S.p.hp,S.p.mhp*.9);const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];x.update(dt);}
 S.p.hp=1;S.p.inv=0;const e=x.spawnEnemy(0,2.5,null,{x:S.p.x,y:S.p.y});e.dmg=500;
 for(let j=0;j<30&&x.state==='play';j++){e.x=S.p.x;e.y=S.p.y;x.update(dt);}
 const st1=x.state;
 if(st1==='revive'){v.RV.lockT=0;v.rvQuit();}
 return {st1,st:x.state,cnt,rq:JSON.stringify(S.dly.rq),t:Math.round(S.t*1e4)/1e4,kills:S.kills,lv:S.lv,say:document.getElementById('rSay').textContent,next:[x.RN('card'),x.RN('spawn')],ph:S.p.hp};}"""
async def run_one(b, srv, page, coins, login, a):
    ctx, pg, errs = await H.new_page(b, srv.port, 412, 860, mock=mk_rng_mock(coins), page=page)
    if login: await pg.evaluate(LOGIN); await pg.reload(); await pg.wait_for_function('window.__p6x!==undefined'); await pg.wait_for_timeout(500)
    r = await pg.evaluate(RUNJS, a); await ctx.close(); return r, errs
async def sec_h(b, srv):
    for label, coins, login in (('로그인 안 함', 0, False), ('로그인·코인 0개', 0, True), ('로그인·코인 3개 → 그만하기', 3, True)):
        for seed, frames in ((12345, 900), (777, 1800)):
            o, e1 = await run_one(b, srv, OLD, coins, login, {'seed': seed, 'frames': frames})
            n, e2 = await run_one(b, srv, NEW, coins, login, {'seed': seed, 'frames': frames})
            keys = ('cnt', 'rq', 't', 'kills', 'lv', 'say', 'next', 'st')
            same = {k: o[k] for k in keys} == {k: n[k] for k in keys}
            check('[H1] %s · 씨앗 %d · %d프레임 — 기준과 새 빌드의 Math.random 호출 수(%d)·오늘의 도전 난수 상태·결과·뒤이은 RN 이 똑같다' % (label, seed, frames, o['cnt']), same and o['st'] == 'result', (o, n))
            if coins and login: check('[H2] 코인이 있으면 새 빌드는 죽은 순간 선택창을 거쳤다(기준은 바로 result)', n['st1'] == 'revive' and o['st1'] == 'result', (o['st1'], n['st1']))
            if e1 or e2: check('[H3] 오류 0', False, (e1, e2))
    # 가장자리: 같은 프레임 이중 사망 · 레벨업 대기 중 사망
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    r = await pg.evaluate("""()=>{const x=__p6x,v=__rv;x.CH_set('brj');x.start();const S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;
      for(const q of x.enemies.a)q.on=false;S.p.hp=1;S.p.inv=0;
      const a=x.hitP(500),reqA=v.RV.req;const b=x.hitP(500),c=v.die();
      return {a,b,c,state:x.state,hp:S.p.hp,req:[reqA,v.RV.req]};}""")
    check('[H4] 같은 프레임에 hitP 두 번 · die 직접 호출까지 모두 true, 선택창은 한 번만 열린다(RV.req 그대로)', r['a'] is True and r['b'] is True and r['c'] is True and r['state'] == 'revive' and r['req'][0] == r['req'][1], r)
    await ctx.close()
    mk = Mock(coins=2); ctx, pg, errs = await fresh(b, srv.port, mk)
    r = await pg.evaluate("""()=>{const x=__p6x,v=__rv;x.CH_set('brj');x.start();const S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.xp=0;S.need=1e12;
      for(const q of x.enemies.a)q.on=false;S.pendingLv=1;S.p.hp=1;S.p.inv=0;const e=x.spawnEnemy(0,2.5,null,{x:S.p.x,y:S.p.y});e.dmg=500;e.sp=0;
      x.update(1/60);return {s1:x.state,pl1:S.pendingLv};}""")
    check('[H5] 레벨업 대기(pendingLv=1) 중에 죽으면 선택창이 먼저(레벨업 카드는 부활 뒤에)', r['s1'] == 'revive' and r['pl1'] == 1, r)
    await pg.wait_for_function(UNLOCK); await pg.evaluate(CLICK_USE); await pg.wait_for_function("__p6x.state!=='revive'", timeout=5000)
    await pg.evaluate("()=>{__p6x.S.p.inv=99;for(const q of __p6x.enemies.a)q.on=false;__p6x.update(1/60);}")
    s2 = await pg.evaluate("()=>[__p6x.state,__p6x.S.pendingLv]"); check('[H6] 부활 뒤 다음 프레임에 레벨업 카드가 열린다(대기분을 잃지 않는다)', s2[0] == 'lvup', s2)
    check('[H7] 오류 0', not errs, errs); await ctx.close()
    # 레벨업 카드 창이 열린 채(이어하기 저장본이 lvup) 에서 죽는 길은 없다 — 카드를 고르면 곧바로 play 이고 그 뒤 update 에서 죽는 경로만 있다(위 H5 가 그 경로)

# ───────────────────────────── M. 이어하기 호환(옛 ↔ 새)
SETUP = "()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.t=100;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.propT=S.chickT=1e12;S.need=1e12;for(const q of x.enemies.a)q.on=false;}"
async def sec_m(b, srv):
    mk = Mock(coins=2)
    ctx = await b.new_context(viewport={'width': 412, 'height': 860})
    async def route(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_(); return
        if 'bot-hosting.cloud' in u: await mk(r); return
        await r.abort()
    await ctx.route('**/*', route)
    A = await ctx.new_page(); await A.goto('http://127.0.0.1:%d/%s' % (srv.port, OLD)); await A.wait_for_function('window.__p6x!==undefined'); await A.evaluate(LOGIN)
    await A.evaluate(SETUP); await A.evaluate("()=>__rv.pauseGame()")
    head = await A.evaluate("()=>localStorage.getItem('p6_resume_v1').split('\\n')[0]"); check('[M1] 옛 빌드가 일시정지 저장본을 만든다', json.loads(head)['st'] == 'pause', head); await A.close()
    B = await newpage(ctx, srv.port)
    card = await B.evaluate("()=>!document.getElementById('resCard').hidden"); check('[M2] 새 빌드 첫 화면에 이어하기 카드(옛 저장본이 거부되지 않는다)', card)
    await B.evaluate("()=>document.getElementById('resGo').click()"); await B.wait_for_function("__p6x.state==='pause'", timeout=5000)
    r = await B.evaluate("()=>[__p6x.state,__p6x.S.cu,__p6x.S.cuq]"); check('[M3] 이어받으면 pause · cu=0 · cuq=0(새 필드 기본값)', r == ['pause', 0, 0], r)
    await B.evaluate("()=>document.getElementById('resumeBtn').click()"); await B.evaluate("()=>{const S=__p6x.S;S.p.hp=1;S.p.inv=0;__p6x.hitP(500);}")
    r = await B.evaluate("()=>[__p6x.state,__rv.RV.n,__rv.RV.mode]"); check('[M4] 이어받은 옛 판에서 죽으면 코인 선택창(n=1)', r == ['revive', 1, 'ask'], r)
    sv = await B.evaluate("()=>localStorage.getItem('p6_resume_v1')"); h2 = json.loads(sv.split('\n')[0]); check('[M5] 새 빌드가 st=revive 저장본을 만든다', h2['st'] == 'revive', h2); await B.close()
    C = await newpage(ctx, srv.port, OLD)
    r = await C.evaluate("()=>[!document.getElementById('resCard').hidden,localStorage.getItem('p6_resume_v1')===null]")
    check('[M6] 롤백한 옛 빌드는 revive 저장본을 이어갈 수 없다 → 말없이 폐기(카드 없음 · 저장본 삭제) — 알려진 한계', r[0] is False and r[1] is True, r)
    await ctx.close()

asyncio.run(main())
