# -*- coding: utf-8 -*-
"""🔁 흐접새우 서바이벌 '이어하기' 시험 — 하던 판을 저장했다가 새로 연 페이지에서 되살린다 (2026-10-08 사장님 지시)
   사용: python3 tests/survivors_resume_test.py [--full] [--only 가,나,...]
     기본(표준) 약 5~8분 · --full 은 무기 전 종류·유물 전 종류·3분 더 진행까지 전부(수십 분)
   구성
     가  직렬화기 단위(순환 참조·Map/Set·typed array·id 참조 보존·함수/DOM 제외 보고)  · 일일 도전 난수(RN) 수열 동일
     나  복구 충실도: 캐릭터(상점·보스 포함) × 모드 × 시점 × 장비 → 저장 → 새 페이지(같은 브라우저 컨텍스트) → 복구 →
         저장 직후 상태 동일 + 같은 난수로 이어간 판과 매 30프레임 상태 동일 + 더 진행 + 콘솔/페이지 오류 0
     다  레벨업(다시 뽑기 쓴 뒤 포함)·보스 상자·일시정지 복구 — 같은 카드·같은 문구, 무료 리롤·보상 중복 없음
     라  소모·삭제·만료·손상·버전/표 서명 불일치·저사양(풀 크기) 불일치
     마  저장소 차단(쓰기 거부·읽기 거부·용량 초과)에서도 게임이 평소처럼 돈다 + 제목 화면 안내
     바  미래 보호: 상태에 함수·DOM·Image 가 새로 생기면 저장을 거부한다 · 풀/최상위 let 분류표(새 상태는 분류를 정해야 한다)
     사  두 창 · 저장 시점 · 저장 시간 · 비밀(토큰)이 저장본에 없음 · 오늘의 도전 · 제목 화면 UI(360×640 · 412×860)·내장 브라우저 안내
   임시 사본 survivors_rx.html 에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
DST = 'survivors_rx.html'
FULL = '--full' in sys.argv
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:600] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
def want(sec): return ONLY is None or sec in ONLY
def load_avg():
    try: return os.getloadavg()[0]
    except Exception: return -1

HOOK_R = r"""
window.__R={RES,get S(){return S},set S(v){S=v},get state(){return state},set state(v){state=v},get CUR(){return CUR},get RUN(){return RUN},
 pools:{enemies,shots,gems,items,props,texts,hazards,eshots,rangs,rkts,pets,hooks,frs,holes,snps,bolts,waves,puds,clouds,allies,cans,bubs},
 CHARS,WEAP,PASS,REL,TRD,SM,KIND,BOSS,TIERS,PT,WIN_T,END_T,SRVUNL,getProg,setProg,
 synCalc,tkCalc,update,resume,pauseGame,pick,openLvup,openChest,endRun,contEndless,start,show,draw,offers,reroll,banCard,drawCards,cardOf,dailyGet,dailySet,
 CH_set(k){CH=CHARS.find(c=>c.k===k)},get CH(){return CH},get SN(){return SN},set SN(v){SN=v},RN,seedOf,mulberry,kstDate,get LOW(){return LOW},get bannerQ(){return bannerQ},get keys(){return keys},set keys(v){keys=v}};
const COS=new Set(['texts','bubs','bolts','snps']);   // 눈요기 풀(시험이 따로 정해 둔다 — 저장 코드의 분류가 틀려도 시험은 흔들리지 않게)
window.__mod=()=>({SN,gemMT,bannerT,bannerS,bannerS2,bannerA,bannerQ:bannerQ.map(q=>q.slice())});
window.__step=function(dt){const R=__R,st=R.state;if(st==='result')return 0;
  if(st==='lvup'){R.pick(R.CUR[0]);return 1;} if(st!=='play'){R.resume();return 1;}
  const S=R.S;S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;R.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];R.update(dt);return 1;};
window.__run=function(sec,cp){const n=Math.round(sec/(1/30)),out=[];for(let i=1;i<=n;i++){__step(1/30);if(cp&&i%cp===0)out.push(JSON.stringify(__digest()));if(__R.state==='result')break;}return out;};
window.__digest=function(){
  const POOLS=__R.pools,skipP=new Set(['texts','bubs','bolts','snps']),slot=new Map();for(const n in POOLS)POOLS[n].a.forEach((o,i)=>slot.set(o,n+':'+i));
  const ids=new Map();let nid=0;
  function w(v){if(v===null)return null;const t=typeof v;
    if(t==='number')return (v!==v)?'NaN':(v===Infinity)?'Inf':(v===-Infinity)?'-Inf':Object.is(v,-0)?'-0':v;
    if(t==='string'||t==='boolean')return v;if(t==='undefined')return '$undef';if(t==='function')return '$fn';
    if(slot.has(v))return {$p:slot.get(v)};if(ids.has(v))return {$r:ids.get(v)};ids.set(v,nid++);
    if(Array.isArray(v))return v.map(w);if(v instanceof Map)return {$m:[...v].map(([k,x])=>[w(k),w(x)])};if(v instanceof Set)return {$s:[...v].map(w)};
    if(ArrayBuffer.isView(v))return {$t:Array.from(v)};if(typeof Node!=='undefined'&&v instanceof Node)return '$dom';
    const o={};for(const k of Object.keys(v).sort())o[k]=w(v[k]);return o;}
  const S=__R.S,so={};for(const k of Object.keys(S).sort()){if(['live','dq','sushi','auraR','kc','ne','lite'].includes(k))continue;so[k]=w(S[k]);}
  const out={S:so,pools:{},mod:w(__mod())};
  for(const n in POOLS){if(skipP.has(n))continue;out.pools[n]={};POOLS[n].a.forEach((o,i)=>{if(o.on){const e={};for(const k of Object.keys(o).sort())e[k]=w(o[k]);out.pools[n][i]=e;}});}
  for(const i in out.pools.hooks){const o=out.pools.hooks[i];if(o.cs&&Array.isArray(o.cs)){const n=__R.pools.hooks.a[i].n;o.cs=o.cs.map((v,j)=>j<n?v:0);}}
  return out;};
window.__core=function(){const R=__R,S=R.S;
  const bs=R.pools.enemies.a.filter(e=>e.on&&e.boss).map(e=>[e.boss,e.hp,e.mhp,e.bph,e.sn]);
  return {t:S.t,lv:S.lv,xp:S.xp,kills:S.kills,hp:S.p.hp,mhp:S.p.mhp,w:S.w,ps:S.ps,ev:S.ev,rel:S.rel,tr:S.tr,sm:S.sm,tier:S.tier,pt:S.pt,rr:S.rr,ban:S.ban,bs,ch:R.CH.k,hard:S.hard,vh:S.vh,endless:S.endless,won:S.won,
    dly:S.dly?{date:S.dly.date,ranked:S.dly.ranked}:null,nE:R.pools.enemies.a.filter(e=>e.on).length};};
window.__norm=function(){const R=__R;for(const n in R.pools){const P=R.pools[n];for(const s of P.a){if(s.on&&!COS.has(n))continue;for(const k of Object.keys(s))delete s[k];Object.assign(s,P.mk());s.on=false;}}const dq=R.S.dq.length;R.S.dq.length=0;return dq;};
window.__inplace=function(){   // 같은 페이지에서 저장 → 복구(제목 화면 상태로 만들어 restore) → 저장 직후 상태와 비교(판 도중 잠깐 떠 있는 풀 — 갈고리·로켓·장판 — 을 놓치지 않으려고)
  const R=__R;if(R.state==='play')R.pauseGame();const text=localStorage.getItem(R.RES.KEY);if(!text)return {same:false,why:'no-save'};
  __norm();const d0=JSON.stringify(__digest());R.state='title';const ok=R.RES.restore(text);const d1=JSON.stringify(__digest());
  return {same:ok&&d0===d1,ok,d0:d0===d1?'':d0,d1:d0===d1?'':d1};};
window.__sweep=function(sec,covered){const R=__R,N=Math.round(sec/(1/30)),bad=[],names=Object.keys(R.pools).filter(n=>!COS.has(n));let n_=0;
  for(let i=0;i<N;i++){__step(1/30);if(R.state==='result')break;if(R.state!=='play')continue;
    const fresh=names.filter(n=>!covered[n]&&R.pools[n].a.some(o=>o.on));if(!fresh.length)continue;
    const r=__inplace();for(const n of fresh){covered[n]=1;n_++;}                       // 그 순간 켜져 있던 풀은 한 번의 왕복 비교(모든 풀 포함)로 함께 확인된다
    if(!r.same)bad.push([fresh.join('+'),r.why||'',r.d0,r.d1]);R.resume();}
  return {covered,bad,n:n_};};
window.__META=function(){const x=__R;return {chars:x.CHARS.map(c=>({k:c.k,w:c.w,boss:!!c.boss,shop:!!c.shop})),weap:Object.fromEntries(Object.keys(x.WEAP).map(k=>[k,{only:x.WEAP[k].only||'',pair:x.WEAP[k].pair}])),
 pass:Object.fromEntries(Object.keys(x.PASS).map(k=>[k,x.PASS[k].max||5])),rel:Object.fromEntries(Object.keys(x.REL).map(k=>[k,x.REL[k].ch||''])),trd:Object.fromEntries(Object.keys(x.TRD).map(k=>[k,x.TRD[k].cap||3])),
 sm:Object.fromEntries(Object.keys(x.SM).map(k=>[k,x.SM[k].cap])),tiers:Object.keys(x.TIERS),pt:Object.fromEntries(Object.keys(x.PT).map(k=>[k,x.PT[k].length])),tierLen:Object.fromEntries(Object.keys(x.TIERS).map(k=>[k,x.TIERS[k].length]))};};
"""
# 판을 '만든다' — 장비·유물·각성·시각을 끼운 판(평범한 캐릭터만 돌리면 조건부 코드를 안 밟는다)
FORGE = r"""(sp)=>{const x=__R;
 x.CH_set(sp.ch);x.SRVUNL.add(sp.ch);const g=x.getProg();g.bk[sp.ch]=1;x.setProg(g);
 document.getElementById('hardChk').checked=!!sp.hard;document.getElementById('vhChk').checked=!!sp.vh;
 x.start({daily:!!sp.daily});const S=x.S;
 if(sp.w)S.w=Object.assign({},sp.w);if(sp.ps)S.ps=Object.assign({},sp.ps);if(sp.ev)S.ev=Object.assign({},sp.ev);if(sp.tier)S.tier=Object.assign({},sp.tier);
 if(sp.pt)S.pt=Object.assign({},sp.pt);if(sp.rel)S.rel=Object.assign({},sp.rel);if(sp.tr)S.tr=Object.assign({},sp.tr);if(sp.sm)S.sm=Object.assign({},sp.sm);
 if(sp.ramen)S.ramen=sp.ramen;
 if(sp.lv){S.lv=sp.lv;S.need=1e9;}
 if(sp.t0){const t0=sp.t0;S.t=t0;S.evT=t0+5;S.bigT=t0+8;
   if(sp.endless){S.endless=1;S.won=true;const k=Math.floor((t0-x.WIN_T)/300)+1;S.bossN=10+k;S.miniN=10+k;S.nextBoss=x.WIN_T+300*k+300;S.nextMini=x.WIN_T+150+300*k;S.nextSp=2280+3600;}
   else{S.bossN=Math.floor(t0/300);S.nextBoss=t0>=3300?Infinity:(S.bossN+1)*300;if(t0>=3300)S.bossN=Math.min(S.bossN,10);
     S.miniN=Math.floor((t0-150)/300)+1;S.nextMini=150+300*S.miniN;if(S.nextMini>3200)S.nextMini=Infinity;S.nextSp=t0>2280?2280+3600:2280;}}
 x.synCalc();x.tkCalc();
 if(sp.mhp){S.p.mhp=sp.mhp;S.p.hp=sp.mhp;}
 return x.state;}"""
SEED_JS = """(()=>{let a=%d>>>0;window.__rg={get s(){return a},set s(v){a=v>>>0}};
 Math.random=function(){a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};})();"""
KEY = 'p6_resume_v1'
RAF_OFF = "window.requestAnimationFrame=function(){return 0};window.AudioContext=window.webkitAudioContext=undefined;"   # 그리기 루프·소리 끔: 소리 합성(noise 버퍼)이 Math.random 을 써서 두 판의 난수 흐름을 어긋내 보이게 한다
CASE = sys.argv[sys.argv.index('--case') + 1] if '--case' in sys.argv else None

class Ctx:
    """브라우저 컨텍스트 하나(= 같은 localStorage) + 오류 수집"""
    def __init__(self, b, port, w=412, h=860, seed=12345, ua=None, hc=0, init=None, mobile=False, raf=True):
        self.b, self.port, self.w, self.h, self.seed, self.ua, self.hc, self.init, self.mobile, self.raf = b, port, w, h, seed, ua, hc, init, mobile, raf
        self.errs = []; self.pages = []
    async def open(self):
        kw = dict(viewport={'width': self.w, 'height': self.h})
        if self.ua: kw['user_agent'] = self.ua
        if self.mobile: kw.update(is_mobile=True, has_touch=True, device_scale_factor=2)
        self.ctx = await self.b.new_context(**kw)
        async def route(r):
            if r.request.url.startswith('http://127.0.0.1:%d/' % self.port): await r.continue_()
            else: await r.abort()
        await self.ctx.route('**/*', route)
        await self.ctx.add_init_script(SEED_JS % self.seed)
        if not self.raf: await self.ctx.add_init_script(RAF_OFF)   # 비교 시험은 update 만 구동한다 — 실제 그리기 루프가 끼어들면(구역 배너 등) 두 판이 어긋나 보인다
        if self.hc: await self.ctx.add_init_script("Object.defineProperty(Navigator.prototype,'hardwareConcurrency',{get:()=>%d});" % self.hc)
        if self.init: await self.ctx.add_init_script(self.init)
        return self
    async def page(self, wait='__R', url=None):
        pg = await self.ctx.new_page()
        pg.on('pageerror', lambda e: self.errs.append('PAGEERR ' + str(e)))
        pg.on('console', lambda m: self.errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        await pg.goto(url or 'http://127.0.0.1:%d/%s' % (self.port, DST))
        await pg.wait_for_function('window.%s!==undefined' % wait, timeout=20000)
        self.pages.append(pg); return pg
    async def close(self): await self.ctx.close()

# ───────────── 장비를 끼운 무작위 판 명세(캐릭터 전원 × 무기 × 유물 × 각성 × 모드) ─────────────
def rand_spec(M, rng, ch, mode='n', t0=None, nw=6, full=False, force_w=None, force_rel=None):
    wk = [k for k, v in M['weap'].items() if (not v['only']) or v['only'] == ch]
    own = next(c['w'] for c in M['chars'] if c['k'] == ch)
    ws = [own] + [k for k in (force_w or []) if k != own]
    others = [k for k in wk if k not in ws]; rng.shuffle(others)
    ws = (ws + others)[:max(nw, len(ws))]
    S_w = {k: (8 if full or rng.random() < .5 else rng.randint(1, 8)) for k in ws}
    pk = list(M['pass']); rng.shuffle(pk); ps = {}
    for k in ws:
        p = M['weap'][k]['pair']
        if p in M['pass'] and len(ps) < 6: ps[p] = M['pass'][p] if (full or rng.random() < .6) else rng.randint(1, M['pass'][p])
    for k in pk:
        if len(ps) >= 6: break
        ps.setdefault(k, rng.randint(1, M['pass'][k]))
    ev = {}
    cand = [k for k in ws if S_w[k] == 8 and ps.get(M['weap'][k]['pair'], 0) > 0]; rng.shuffle(cand)
    for k in cand[:3]: ev[k] = 1
    tier = {}
    for k in ws:
        if S_w[k] >= 8 and k in M['tiers']:
            cap = 5 if k in ev else 3
            tier[k] = min(M['tierLen'][k], rng.randint(0, cap)) if not full else min(M['tierLen'][k], cap)
    pt = {}
    for k, L in M['pt'].items():
        if ps.get(k, 0) >= M['pass'][k] and rng.random() < .6: pt[k] = rng.randint(1, L)
    rel = {}; rk = [k for k, c in M['rel'].items() if not c]; rng.shuffle(rk)
    for k in rk[:3]: rel[k] = rng.randint(1, 3)
    for k, c in M['rel'].items():
        if c == ch: rel[k] = rng.randint(1, 3) if not full else 3      # ⭐ 시그니처 유물
    for k in (force_rel or []): rel[k] = 3
    tr = {k: rng.randint(1, c) for k, c in M['trd'].items() if rng.random() < .4}
    sm = {k: rng.randint(1, c) for k, c in M['sm'].items() if k != 'ramen' and rng.random() < .5}
    sp = dict(ch=ch, w=S_w, ps=ps, ev=ev, tier=tier, pt=pt, rel=rel, tr=tr, sm=sm, ramen=rng.randint(0, 8), lv=rng.randint(20, 50), mhp=rng.choice([100, 160, 260]))
    sp['hard'] = mode == 'h'; sp['vh'] = mode == 'v'; sp['daily'] = mode == 'd'; sp['endless'] = mode == 'e'
    if t0 is not None: sp['t0'] = t0
    return sp

SAVEA = r"""()=>{const R=__R;if(R.state==='play')R.pauseGame();const blob=localStorage.getItem(R.RES.KEY),rep=R.RES.info.rep,ms=R.RES.info.ms;
  const dqN=__norm();return {blob,rg0:__rg.s,d0:JSON.stringify(__digest()),core:JSON.stringify(__core()),dqN,rep,ms,state:R.state};}"""

async def roundtrip(C, A, sp, label, warm=8, cmp_sec=8, more_sec=0, draw=False):
    """A: 판을 만들어 warm 초 진행 → 일시정지·저장 → 계속 진행(기준). B: 새 페이지에서 복구 → 같은 난수로 진행 → 매 30프레임 상태 비교"""
    n0 = len(C.errs)
    await A.evaluate(FORGE, sp)
    st = await A.evaluate("(s)=>{__run(s,0);return __R.state}", warm)
    if st == 'result':
        check('[%s] (판이 일찍 끝나 건너뜀)' % label, True); return None
    r = await A.evaluate(SAVEA)
    if r['state'] != 'pause' or not r['blob']:
        check('[%s] 일시정지 → 저장본이 생긴다' % label, False, (r['state'], r['rep'])); return None
    cpsA = await A.evaluate("(s)=>__run(s,30)", cmp_sec)
    B = await C.page(); await B.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", r['blob'])
    await B.reload(); await B.wait_for_function('window.__R!==undefined')           # 새로 열린 페이지(모듈 상태 없음)
    vis = await B.evaluate("()=>!document.getElementById('resCard').hidden")
    await B.click('#resGo'); await B.wait_for_function("__R.state==='pause'", timeout=8000)
    await B.evaluate("(g)=>{__rg.s=g}", r['rg0'])
    imm = await B.evaluate("()=>[JSON.stringify(__digest()),JSON.stringify(__core())]")
    ok_imm = imm[0] == r['d0']; ok_core = imm[1] == r['core']
    cpsB = await B.evaluate("(s)=>__run(s,30)", cmp_sec)
    first = next((i for i in range(min(len(cpsA), len(cpsB))) if cpsA[i] != cpsB[i]), -1)
    detail = ''
    if not ok_imm: detail = diff_first(r['d0'], imm[0])
    elif first >= 0: detail = 'cp%d ' % first + diff_first(cpsA[first], cpsB[first])
    elif not ok_core: detail = diff_first(r['core'], imm[1])
    extra_ok = True
    if more_sec:
        res = await B.evaluate("(s)=>{__run(s,0);return [__R.state,__R.S.t,__R.S.kills]}", more_sec); extra_ok = res[0] in ('play', 'result', 'pause', 'lvup')
    if draw:
        await B.evaluate("()=>{for(let i=0;i<3;i++)__R.draw();}")
    slot_gone = await B.evaluate("(k)=>localStorage.getItem(k)===null || __R.RES.peek().rid!==undefined", KEY)
    good = vis and ok_imm and ok_core and first < 0 and len(cpsA) == len(cpsB) and extra_ok and len(C.errs) == n0
    check('[%s] 새 페이지에서 복구 → 저장 직후 동일 · 같은 난수로 %ds 이어도 동일%s' % (label, cmp_sec, (' · +%ds 진행' % more_sec) if more_sec else ''), good,
          dict(card=vis, imm=ok_imm, core=ok_core, first=first, n=(len(cpsA), len(cpsB)), more=extra_ok, errs=C.errs[n0:n0 + 3], detail=detail))
    await B.close()
    return r

def diff_first(a, b, path='', lim=3):
    try: A, B = json.loads(a), json.loads(b)
    except Exception: return 'unparsable'
    out = []
    def go(x, y, p):
        if len(out) >= lim: return
        if type(x) != type(y): out.append((p, str(x)[:60], str(y)[:60])); return
        if isinstance(x, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x: out.append((p + '.' + k, '<없음>', str(y[k])[:60]))
                elif k not in y: out.append((p + '.' + k, str(x[k])[:60], '<없음>'))
                else: go(x[k], y[k], p + '.' + k)
                if len(out) >= lim: return
        elif isinstance(x, list):
            if len(x) != len(y): out.append((p + '.length', len(x), len(y)))
            for i in range(min(len(x), len(y))): go(x[i], y[i], p + '[%d]' % i)
        elif x != y: out.append((p, x, y))
    go(A, B, path); return out

async def main():
    t_start = time.time()
    print('부하(1분 평균) 시작 %.1f' % load_avg(), flush=True)
    H.make_copy(dst=DST, extra=HOOK_R)
    mut = os.environ.get('RES_MUTATE')     # 민감도 확인용(개발 때만): 저장에서 일부러 빼 보고 시험이 실패하는지 본다 — 예: RES_MUTATE=S:x3 · RES_MUTATE=POOL:hooks
    if mut:
        pth = os.path.join(H.ROOT, DST); t = open(pth, encoding='utf-8').read(); kind, name = mut.split(':')
        a = "const SKIP_S=new Set([" if kind == 'S' else "const COSMETIC=new Set(["
        assert a in t; open(pth, 'w', encoding='utf-8').write(t.replace(a, a + "'%s'," % name, 1)); print('★ 돌연변이:', mut)
    import socketserver; socketserver.ThreadingTCPServer.handle_error = lambda self, *a: None   # 페이지를 닫을 때 끊기는 연결의 BrokenPipe 소음을 끈다
    srv = H.Srv()
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            if want('가'): await sec_unit(b, srv)
            if want('나'): await sec_fidelity(b, srv)
            if want('다'): await sec_pending(b, srv)
            if want('라'): await sec_invalid(b, srv)
            if want('마'): await sec_blocked(b, srv)
            if want('바'): await sec_future(b, srv)
            if want('사'): await sec_misc(b, srv)
            await b.close()
    finally:
        srv.close()
        try: os.remove(os.path.join(H.ROOT, DST))
        except OSError: pass
    print('부하(1분 평균) 끝 %.1f · 걸린 시간 %.0f초' % (load_avg(), time.time() - t_start))
    print('실패 %d' % len(FAILS))
    for f in FAILS: print('  -', f)
    return 1 if FAILS else 0

# ═════════════ 가. 직렬화기 단위 · 난수 ═════════════
UNIT = r"""()=>{const R=__R.RES,out={};
 const slotA={x:1},slotB={y:2},SL=new Map([[slotA,['p',0]],[slotB,['p',1]]]);
 const E=R.makeEnc(v=>SL.get(v),v=>null);
 const shared={n:1};
 const a={name:'a',shared,self:null,list:[shared,{shared}],m:new Map([[shared,'k'],['z',{shared}]]),s:new Set([shared,3]),f32:new Float32Array([1.5,0.1,-0]),u8:new Uint8Array([1,255]),
   nan:NaN,inf:Infinity,ninf:-Infinity,nz:-0,u:undefined,ref:slotA,refs:[slotA,slotB,slotA],deep:{a:{b:{c:{d:[1,{e:2}]}}}}};
 a.self=a;a.cyc={back:a};
 E.count(a);const enc=E.enc(a,'a'),json=JSON.stringify(enc);
 const D=R.makeDec(sl=>sl[1]===0?slotA:slotB,p=>{throw new Error('no static')});
 const b=D(JSON.parse(json));
 out.cycle=b.self===b&&b.cyc.back===b;
 out.shared=b.shared===b.list[0]&&b.list[1].shared===b.shared&&[...b.m.keys()][0]===b.shared&&b.m.get('z').shared===b.shared&&b.s.has(b.shared);
 out.mapset=b.m instanceof Map&&b.m.size===2&&b.s instanceof Set&&b.s.size===2&&b.s.has(3);
 out.typed=b.f32 instanceof Float32Array&&b.f32[0]===1.5&&b.f32[1]===Math.fround(0.1)&&Object.is(b.f32[2],-0)&&b.u8 instanceof Uint8Array&&b.u8[1]===255;
 out.nums=Number.isNaN(b.nan)&&b.inf===Infinity&&b.ninf===-Infinity&&Object.is(b.nz,-0);
 out.undef='u' in b&&b.u===undefined;
 out.slots=b.ref===slotA&&b.refs[1]===slotB&&b.refs[2]===slotA;
 out.deep=JSON.stringify(b.deep)===JSON.stringify(a.deep);
 out.noSlotCopy=!json.includes('"x":1')&&!json.includes('"y":2');
 // 보고: 함수·DOM·Image·클래스·Date·BigInt·Symbol·정밀하지 않은 typed array
 class Foo{constructor(){this.q=1;}}
 const cv=document.createElement('canvas');
 const bad={cb:()=>1,deep:{list:[()=>2]},el:document.createElement('div'),img:new Image(),cv,ctx:cv.getContext('2d'),cls:new Foo(),date:new Date(),big:BigInt(1),sym:Symbol('s'),b64:new BigInt64Array(1),ok:{n:5},aud:new Audio()};
 const E2=R.makeEnc(()=>null,()=>null);E2.count(bad);const e2=E2.enc(bad,'S'),j2=JSON.stringify(e2);
 out.rep=E2.rep;out.keys=Object.keys(e2);
 out.json2=j2;
 // 같은 입력을 두 번 내보내면 똑같다(25회 멱등)
 let same=true;const E3=R.makeEnc(v=>SL.get(v),v=>null);E3.count(a);const j3=JSON.stringify(E3.enc(a,'a'));for(let i=0;i<25;i++){const Ei=R.makeEnc(v=>SL.get(v),v=>null);Ei.count(a);if(JSON.stringify(Ei.enc(a,'a'))!==j3)same=false;}out.idem=same&&j3===json;
 // 잘못된 입력 거부
 let rej=0;for(const bad of [{$p:['zzz',0]},{$p:['enemies',99999]},{$st:'WEAP.nope.x'},{$r:7},{$t:'Function',d:[]}]){try{R.load({v:R.FMT,lens:{},defs:{},S:{x:bad},pools:{},mod:{}});}catch(e){rej++;}}out.rej=rej;
 return out;}"""
RNTEST = r"""()=>{const R=__R,res=[];
 for(const date of ['2026-10-08','2026-12-31','2027-02-28']){const d={date,seed:R.seedOf('p6-daily-'+date),ranked:false,rq:{}};
   const refs={};let ok=true,mid=null;
   const old=k=>{const g=refs[k]||(refs[k]=R.mulberry((d.seed^R.seedOf(k))>>>0));return g();};
   const S0=R.S;R.S={dly:d};
   for(let i=0;i<20000;i++){const k=['card','chest','spawn','ev','prop'][i%5];const a=old(k),b=R.RN(k);if(a!==b){ok=false;break;}
     if(i===9999)mid=JSON.stringify(d);}                        // 중간에 JSON 으로 저장했다 되살려 이어붙여도 같은 수열
   // 중간 저장본에서 이어붙이기
   const d2=JSON.parse(mid);R.S={dly:d2};const refs2={};const old2=k=>{const g=refs2[k]||(refs2[k]=R.mulberry((d.seed^R.seedOf(k))>>>0));return g();};
   let ok2=true;for(let i=0;i<10000;i++){const k=['card','chest','spawn','ev','prop'][i%5];old2(k);}      // 앞 10000번을 소비
   for(let i=10000;i<20000;i++){const k=['card','chest','spawn','ev','prop'][i%5];if(old2(k)!==R.RN(k)){ok2=false;break;}}
   R.S=S0;res.push([date,ok,ok2]);}
 return res;}"""
async def sec_unit(b, srv):
    print('\n── 가. 직렬화기 단위 · 난수 ──', flush=True)
    C = await Ctx(b, srv.port).open(); A = await C.page()
    u = await A.evaluate(UNIT)
    check('순환 참조(자기 자신·되돌아가는 참조)가 보존된다', u['cycle'])
    check('같은 객체를 가리키던 여러 참조가 복구 뒤에도 같은 객체다(id 참조 · Map 키 · Set)', u['shared'])
    check('Map/Set 이 그대로 복구된다', u['mapset'])
    check('typed array(Float32Array 정밀도 · -0 · Uint8Array)', u['typed'])
    check('NaN · Infinity · -Infinity · -0 이 JSON 을 거쳐도 살아남는다', u['nums'])
    check('undefined 값이 키와 함께 복구된다', u['undef'])
    check('풀 칸 참조는 복사본이 아니라 같은 칸 객체로 복구된다', u['slots'] and u['noSlotCopy'])
    check('깊은 중첩', u['deep'])
    check('같은 입력을 25번 내보내도 바이트까지 같다', u['idem'])
    rep = u['rep']
    check('함수가 보고된다(경로 포함)', set(rep['fn']) == {'S.cb', 'S.deep.list[]'}, rep['fn'])
    check('DOM·Image·Canvas·Audio 가 보고되고 저장본에서 빠진다', set(rep['dom']) == {'S.el', 'S.img', 'S.cv', 'S.ctx', 'S.aud'}, rep['dom'])
    check('클래스 인스턴스·Date·BigInt·Symbol·BigInt64Array 가 보고된다', len(rep['proto']) == 5, rep['proto'])
    check('보고된 값은 출력에 없고 평범한 값만 남는다(배열 안의 함수는 null 자리)', u['keys'] == ['deep', 'ok'] and '"cb"' not in u['json2'] and '"deep":{"list":[null]}' in u['json2'], (u['keys'], u['json2'][:200]))
    check('잘못된 참조(없는 풀·범위 밖 칸·없는 표 경로·앞서지 않은 id·허용되지 않은 typed array)는 전부 거부된다', u['rej'] == 5, u['rej'])
    for date, ok, ok2 in await A.evaluate(RNTEST):
        check('일일 도전 난수 RN %s — 옛 mulberry 와 같은 수열(2만 번) · JSON 으로 중간 저장·복구해 이어도 같음' % date, ok and ok2, (ok, ok2))
    check('스크립트 오류 없음', not C.errs, C.errs); await C.close()

# ═════════════ 나. 복구 충실도 ═════════════
TIMES = [60, 360, 900, 1800, 2700, 3660]
MODES = 'nhvde'
async def sec_fidelity(b, srv):
    print('\n── 나. 복구 충실도 (캐릭터 × 모드 × 시점 × 장비) ──  부하 %.1f' % load_avg(), flush=True)
    rng = random.Random(20261008)
    C = await Ctx(b, srv.port, w=900, h=900, seed=31, raf=False, hc=8).open(); A = await C.page()
    M = await A.evaluate("()=>__META()")
    chars = [c['k'] for c in M['chars']]
    print('   캐릭터 %d명(상점 %d · 보스 %d) · 무기 %d종 · 유물 %d종' % (len(chars), sum(c['shop'] for c in M['chars']), sum(c['boss'] for c in M['chars']), len(M['weap']), len(M['rel'])), flush=True)
    cases = []
    for i, ch in enumerate(chars):                      # 캐릭터 전원 — 모드·시점이 돌아가며
        mode = MODES[i % 5]; t0 = TIMES[i % 6]
        if mode == 'e': t0 = 3660
        if mode != 'e' and t0 >= 3660: t0 = 2700
        cases.append(('%s/%s/%ds' % (ch, mode, t0), rand_spec(M, rng, ch, mode, t0=t0, full=(i % 2 == 0))))
    for t0 in TIMES:                                    # 한 캐릭터로 모든 시점(1·6·15·30·45·61분)
        mode = 'e' if t0 >= 3660 else 'n'
        cases.append(('brj/%s/%ds' % (mode, t0), rand_spec(M, rng, 'brj', mode, t0=t0, full=True)))
    for mode in 'hvd':                                  # 한 시점으로 모든 모드
        cases.append(('sr/%s/900s' % mode, rand_spec(M, rng, 'sr', mode, t0=900, full=True)))
    # 보스 상자·보스 전투 한가운데(보스 시각 직전)
    for t0 in (295, 880, 1495, 2275, 3290):
        for ch in ('brj', 'yj', 'ddo'):
            if ch in chars: cases.append(('boss/%s/%ds' % (ch, t0), rand_spec(M, rng, ch, 'n', t0=t0, full=True)))
    wl = list(M['weap'].items()); rl = list(M['rel'].items())
    if not FULL: wl = wl[::4]; rl = rl[::4]
    for k, v in wl:                                     # 무기 종류별
        ch = v['only'] if v['only'] in chars else rng.choice(chars)
        cases.append(('무기:%s' % k, rand_spec(M, rng, ch, 'n', t0=rng.choice([300, 900, 1800]), nw=3, full=True, force_w=[k])))
    for k, c in rl:                                     # 유물(시그니처 포함) 종류별
        ch = c if c in chars else rng.choice(chars)
        cases.append(('유물:%s' % k, rand_spec(M, rng, ch, 'n', t0=rng.choice([300, 900]), full=True, force_rel=[k])))
    n = 0; t00 = time.time()
    for idx, (label, sp) in enumerate(cases):
        if CASE and CASE not in label: continue
        long = (idx % (3 if FULL else 7) == 0)
        try:
            r = await roundtrip(C, A, sp, label, warm=8 if idx % 3 else 14, cmp_sec=8, more_sec=(180 if FULL else 60) if long else 0, draw=False)
        except Exception as ex:
            check('[%s] 예외 없이 끝남' % label, False, repr(ex)[:300]); continue
        n += 1
        if r and r['dqN']: DQN.append(r['dqN'])
        if r and r['rep']: REPS.append(r['rep'])
    # 풀마다 '그 풀이 채워진 순간'에 저장 → 복구 → 같은 상태인지(갈고리·로켓·병아리·장판 같은 짧게 떠 있는 풀도 빠뜨리지 않는다)
    covered = {}; names = await A.evaluate("()=>Object.keys(__R.pools).filter(n=>!__COS.has(n))"); badp = []
    sweep = [(l, sp) for l, sp in cases if l.startswith('무기:') or l.startswith('유물:')]
    for ch in chars: sweep.insert(0, ('캐릭터:' + ch, rand_spec(M, rng, ch, 'n', t0=rng.choice([600, 1200, 2000]), full=True)))
    for label, sp in sweep:
        if len(covered) == len(names): break
        await A.evaluate(FORGE, sp)
        r = await A.evaluate("([s,c])=>__sweep(s,c)", [30, covered]); covered = r['covered']
        for x in r['bad']: badp.append((label,) + tuple(x[:2]) + (diff_first(x[2], x[3]) if x[2] else '',))
    check('풀 %d종이 채워진 순간마다 저장 → 복구 → 저장 직후와 같다(채워 본 풀 %d/%d%s)' % (len(names), len(covered), len(names), '' if len(covered) == len(names) else ' · 못 채운 것: ' + ','.join(n for n in names if n not in covered)),
          not badp and len(covered) >= len(names) - 3, badp[:3])
    bad = [x for rp in REPS for x in rp['fn'] if x != 'S.dq[].f'] + [x for rp in REPS for x in rp['dom'] + rp['proto']]
    check('실제 판 %d건 전부에서 저장 불가 값은 S.dq[].f(지연 발동 함수) 하나뿐 — 새 함수·DOM·Image 없음' % len(REPS), not bad, bad[:5])
    print('   사례 %d · 지연 큐(dq) 손실이 있던 표본 %d건(허용: 0.3~0.6초 뒤 타격) · 소요 %.0f초 · 부하 %.1f' % (n, len(DQN), time.time() - t00, load_avg()), flush=True)
    # 자연 플레이(장비 없이)로도 한 번 — 그리기까지
    for ch, mode in (('brj', 'n'), ('yj', 'h')):
        sp = dict(ch=ch, hard=mode == 'h', vh=False, daily=False, endless=False)
        await roundtrip(C, A, sp, '자연 플레이/%s' % ch, warm=40, cmp_sec=8, more_sec=20, draw=True)
    check('스크립트 오류 없음(전 구간)', not C.errs, C.errs[:5]); await C.close()
DQN = []; REPS = []

# ═════════════ 다. 대기 중인 선택 상태 ═════════════
async def sec_pending(b, srv):
    print('\n── 다. 레벨업 · 보스 상자 · 일시정지 복구 ──', flush=True)
    rng = random.Random(7)
    C = await Ctx(b, srv.port, w=900, h=900, seed=77, raf=False, hc=8).open(); A = await C.page()
    M = await A.evaluate("()=>__META()")
    for kind, mode, reroll in (('lvup', 'n', False), ('lvup', 'd', False), ('lvup', 'v', True), ('lvup', 'h', 'ban'), ('chest', 'n', False), ('chest', 'h', False), ('pause', 'n', False)):
        ch = rng.choice([c['k'] for c in M['chars']]); sp = rand_spec(M, rng, ch, mode, t0=rng.choice([400, 1000, 1700]), full=False)
        label = '%s/%s/%s%s' % (kind, ch, mode, '/다시뽑기' if reroll is True else '/봉인' if reroll == 'ban' else '')
        n0 = len(C.errs)
        await A.evaluate(FORGE, sp); await A.evaluate("()=>{__run(6,0)}")
        if kind == 'lvup':
            await A.evaluate("()=>{const R=__R;R.S.pendingLv=2;R.S.lv+=2;R.openLvup();}")
            if reroll is True: await A.evaluate("()=>{__R.reroll();}")                  # 다시 뽑기를 이미 쓴 뒤
            if reroll == 'ban': await A.evaluate("()=>{const R=__R;R.S.banMode=true;R.drawCards();R.banCard(0);}")
        elif kind == 'chest': await A.evaluate("()=>{__R.openChest();}")
        else: await A.evaluate("()=>{__R.pauseGame();}")
        pre = await A.evaluate("""()=>{const R=__R,S=R.S;return {state:R.state,cur:JSON.stringify(R.CUR),rr:S.rr,ban:S.ban,banned:S.banned.slice(),pend:S.pendingLv,
            chest:document.getElementById('chestList').innerHTML,chestT:document.getElementById('chestT').textContent,
            ch:document.getElementById('choices').innerText,blob:localStorage.getItem('p6_resume_v1'),rg0:__rg.s,sn:R.SN}}""")
        d0n = await A.evaluate("()=>{__norm();return JSON.stringify(__digest())}")
        check('[%s] 대기 상태에 들어가는 순간 저장본이 생긴다(%s)' % (label, pre['state']), pre['blob'] is not None and pre['state'] == kind, pre['state'])
        idx = 1 if kind == 'lvup' else 0
        # 기준: A 에서 카드를 골라 이어감
        if kind == 'lvup': await A.evaluate("(i)=>{const R=__R;R.pick(R.CUR[i]);}", idx)
        else: await A.evaluate("()=>{__R.resume();}")
        cpsA = await A.evaluate("()=>__run(6,30)")
        # B: 새 페이지 복구
        B = await C.page(); await B.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", pre['blob']); await B.reload(); await B.wait_for_function('window.__R!==undefined')
        await B.click('#resGo'); await B.wait_for_function("__R.state!=='title'", timeout=8000); await B.evaluate("(g)=>{__rg.s=g}", pre['rg0'])
        post = await B.evaluate("""()=>{const R=__R,S=R.S;return {state:R.state,cur:JSON.stringify(R.CUR),rr:S.rr,ban:S.ban,banned:S.banned.slice(),pend:S.pendingLv,
            chest:document.getElementById('chestList').innerHTML,chestT:document.getElementById('chestT').textContent,ch:document.getElementById('choices').innerText,
            on:[...document.querySelectorAll('.ov.on')].map(e=>e.id),pinfo:document.getElementById('pInfo').innerText.slice(0,80),d:JSON.stringify(__digest()),
            slot:localStorage.getItem('p6_resume_v1'),btns:document.querySelectorAll('#choices .ch').length}}""")
        check('[%s] 복구하면 같은 화면(%s)이 뜬다' % (label, kind), post['state'] == kind and post['on'] == [kind], (post['state'], post['on']))
        check('[%s] 저장본은 복구하면 소모된다' % label, post['slot'] is None)
        check('[%s] 복구 직후 판 상태가 저장 직후와 같다' % label, post['d'] == d0n, diff_first(d0n, post['d']))
        if kind == 'lvup':
            check('[%s] 카드 3장이 한 장도 바뀌지 않고 같다(무료 리롤 없음)' % label, post['cur'] == pre['cur'] and post['ch'] == pre['ch'], (pre['cur'][:120], post['cur'][:120]))
            check('[%s] 다시 뽑기·봉인 횟수·봉인 목록·연속 레벨업 수가 그대로' % label, (post['rr'], post['ban'], post['banned'], post['pend']) == (pre['rr'], pre['ban'], pre['banned'], pre['pend']))
            await B.evaluate("(i)=>{const R=__R;R.pick(R.CUR[i]);}", idx)
        elif kind == 'chest':
            check('[%s] 상자 문구가 같다 · 보상(다시 뽑기 +1)이 한 번 더 들어가지 않는다' % label, post['chest'] == pre['chest'] and post['chestT'] == pre['chestT'] and post['rr'] == pre['rr'], (pre['rr'], post['rr']))
            await B.click('#chestOk')
        else:
            check('[%s] 일시정지 화면에 \'불러왔어요\' 안내 · 시간은 흐르지 않는다' % label, '불러왔어요' in post['pinfo'], post['pinfo'])
            await B.click('#resumeBtn')
        cpsB = await B.evaluate("()=>__run(6,30)")
        first = next((i for i in range(min(len(cpsA), len(cpsB))) if cpsA[i] != cpsB[i]), -1)
        check('[%s] 고른 뒤 같은 난수로 이어가면 원래 판과 똑같다' % label, first < 0 and len(cpsA) == len(cpsB), diff_first(cpsA[first], cpsB[first]) if first >= 0 else (len(cpsA), len(cpsB)))
        if kind == 'lvup' and reroll is False:
            # 복구한 레벨업에서 다시 뽑기는 '값을 치르고' 된다(공짜가 아니다)
            await B.evaluate("()=>{const R=__R;R.S.pendingLv=1;R.S.rr=2;R.openLvup();}"); rr0 = await B.evaluate("()=>__R.S.rr")
            await B.evaluate("()=>{__R.reroll();}"); rr1 = await B.evaluate("()=>__R.S.rr")
            check('[%s] 다시 뽑기는 횟수를 쓴다(%d→%d)' % (label, rr0, rr1), rr1 == rr0 - 1)
        check('[%s] 오류 없음' % label, len(C.errs) == n0, C.errs[n0:n0 + 3]); await B.close()
    # 복구본을 두 번 쓸 수 없다
    await A.evaluate(FORGE, dict(ch='brj', t0=300)); await A.evaluate("()=>{__run(3,0);__R.pauseGame();}")
    blob = await A.evaluate("()=>localStorage.getItem('p6_resume_v1')")
    B1 = await C.page(); B2 = await C.page(); await B1.reload(); await B2.reload()
    await B1.wait_for_function('window.__R!==undefined'); await B2.wait_for_function('window.__R!==undefined')
    r1 = await B1.evaluate("()=>{const ok=__R.RES.restore();return [ok,__R.state]}"); r2 = await B2.evaluate("()=>{const ok=__R.RES.restore();return [ok,__R.state]}")
    check('같은 저장본을 두 창이 이어받을 수 없다(먼저 한 창만 성공)', (r1[0], r2[0]) == (True, False), (r1, r2))
    await B1.close(); await B2.close()
    check('스크립트 오류 없음', not C.errs, C.errs[:5]); await C.close()

# ═════════════ 라. 소모 · 삭제 · 만료 · 손상 · 버전 · 저사양 ═════════════
CRAFT = r"""([blob,mode])=>{const R=__R;const i=blob.indexOf('\n');let h=JSON.parse(blob.slice(0,i)),body=blob.slice(i+1);
 const seal=(h,body)=>{h.len=body.length;h.ck=R.seedOf(body);return JSON.stringify(h)+'\n'+body;};
 const o=()=>JSON.parse(body);
 switch(mode){
  case 'trunc': return blob.slice(0,blob.length-1000);
  case 'ck': {const j=body.indexOf('"hp":');const b2=body.slice(0,j+5)+(body[j+5]==='9'?'8':'9')+body.slice(j+6);return JSON.stringify(h)+'\n'+b2;}
  case 'garble': return seal(h,'{"v":1,"lens":{'+body.slice(30,400));
  case 'sig': h.sig='1:0:0';return JSON.stringify(h)+'\n'+body;
  case 'ver': h.f=2;return JSON.stringify(h)+'\n'+body;
  case 'old': h.ts=Date.now()-13*3600*1000;return JSON.stringify(h)+'\n'+body;
  case 'future': h.ts=Date.now()+3600*1000;return JSON.stringify(h)+'\n'+body;
  case 'char': h.ch='nobody';return JSON.stringify(h)+'\n'+body;
  case 'state': h.st='result';return JSON.stringify(h)+'\n'+body;
  case 'weapon': {const x=o();x.S.w.zzz=1;return seal(h,JSON.stringify(x));}
  case 'nan': {const x=o();x.S.p.hp={$n:'NaN'};return seal(h,JSON.stringify(x));}
  case 'neg': {const x=o();x.S.t=-5;return seal(h,JSON.stringify(x));}
  case 'badref': {const x=o();x.S.bossRef={$p:['enemies',99999]};return seal(h,JSON.stringify(x));}
  case 'badstatic': {const x=o();x.S.zz={$st:'WEAP.nope.q'};return seal(h,JSON.stringify(x));}
  case 'badkind': {const x=o();const e=x.pools.enemies[0];if(e)e[1].ki=9999,e[1].boss=0;else throw new Error('no enemy');return seal(h,JSON.stringify(x));}
  case 'dly_old': {const x=o();x.S.dly=Object.assign({date:'2020-01-01',seed:123,ranked:true,rq:{}},{});return seal(h,JSON.stringify(x));}
 } return blob;}"""
async def sec_invalid(b, srv):
    print('\n── 라. 소모 · 삭제 · 만료 · 손상 · 버전 · 저사양 ──', flush=True)
    C = await Ctx(b, srv.port, seed=5, w=900, h=900, hc=8).open(); A = await C.page()
    check('(큰 기기 환경 확인) LOW=false', await A.evaluate("()=>__R.LOW") is False)
    await A.evaluate(FORGE, dict(ch='brj', t0=500, lv=12, hard=False, vh=False, daily=False)); await A.evaluate("()=>{__run(10,0);__R.pauseGame();}")
    blob = await A.evaluate("()=>localStorage.getItem('p6_resume_v1')")
    check('기준 저장본이 있다', blob and blob.count('\n') >= 1)
    nE = await A.evaluate("()=>__R.pools.enemies.a.filter(e=>e.on).length")
    async def fresh(modified):
        pg = await C.page(); await pg.evaluate("([k,v])=>{if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v);}", [KEY, modified])
        await pg.reload(); await pg.wait_for_function('window.__R!==undefined'); return pg
    async def crafted(mode):
        pg = await C.page(); m = await pg.evaluate(CRAFT, [blob, mode]); await pg.close(); return m
    # 1) 소모
    pg = await fresh(blob)
    check('저장본이 있으면 제목 화면에 이어하기 카드가 뜬다', await pg.evaluate("()=>!document.getElementById('resCard').hidden"))
    txt = await pg.evaluate("()=>document.getElementById('resSum').textContent+' | '+document.getElementById('resAgo').textContent")
    check('카드에 캐릭터·시간·Lv·처치와 몇 분 전인지가 쉬운 말로 나온다', 'Lv 12' in txt and re.search(r'\d\d:\d\d', txt) and ('방금' in txt or '분 전' in txt) and '처치' in txt, txt)
    await pg.click('#resGo'); await pg.wait_for_function("__R.state==='pause'")
    check('이어하기 → 일시정지 상태(계속하기를 눌러야 시간이 흐른다)', await pg.evaluate("()=>[__R.state,document.getElementById('pause').classList.contains('on')]") == ['pause', True])
    t_a = await pg.evaluate("()=>__R.S.t"); await pg.wait_for_timeout(600); t_b = await pg.evaluate("()=>__R.S.t")
    check('일시정지에서는 시간이 안 흐른다', t_a == t_b, (t_a, t_b))
    check('복구하면 저장본이 소모된다', await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')")is None)
    pg2 = await C.page()
    check('다른 창을 열어도 카드가 없다(두 번 이어받을 수 없다)', await pg2.evaluate("()=>document.getElementById('resCard').hidden"))
    await pg2.close()
    await pg.reload(); await pg.wait_for_function('window.__R!==undefined')
    check('이어받은 판을 일시정지한 채 떠나면(새로고침) 다시 저장돼 또 이어갈 수 있다 — 다음에 떠날 때 다시 저장', await pg.evaluate("()=>!document.getElementById('resCard').hidden"))
    await pg.close()
    # 2) 삭제 시점
    pg = await fresh(blob); await pg.click('#resGo'); await pg.wait_for_function("__R.state==='pause'")
    await pg.click('#resumeBtn'); await pg.evaluate("()=>__run(2,0)")
    check('판 도중(play)에는 저장본이 없다 — 되감기로 쓸 수 없다', await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is None)
    await pg.evaluate("()=>__R.pauseGame()"); check('일시정지하면 저장된다', await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is not None)
    await pg.click('#resumeBtn'); check('계속하기를 누르면 저장본이 지워진다', await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is None)
    await pg.evaluate("()=>__R.pauseGame()"); await pg.click('#quitBtn')
    check('그만두기(포기하고 결과 보기)하면 지워진다', await pg.evaluate("()=>[__R.state,localStorage.getItem('p6_resume_v1')]") == ['result', None])
    await pg.evaluate("()=>{__R.start();__run(2,0);__R.pauseGame();}"); s1 = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is not None
    await pg.evaluate("()=>{__R.resume();__R.S.p.hp=0;__R.S.p.inv=0;__R.hurt&&0;}")
    await pg.evaluate("()=>{__R.endRun(false,false)}")
    check('사망(endRun)하면 지워진다', s1 and await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is None)
    await pg.evaluate("()=>{__R.start();__run(2,0);__R.pauseGame();}"); await pg.evaluate("()=>{__R.start();}")
    check('새 판을 시작하면 하던 판 저장본이 지워진다', await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is None)
    await pg.evaluate("()=>{__R.endRun(false,true);}"); await pg.click('#homeBtn')
    check('\'처음으로\'를 누른 뒤에도 저장본이 없다', await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is None)
    await pg.close()
    # 3) 60분 클리어는 지운다
    pg = await fresh(None); await pg.evaluate(FORGE, dict(ch='brj', t0=3590)); await pg.evaluate("()=>{__R.pauseGame();}"); has = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is not None
    await pg.evaluate("()=>{__R.resume();__run(15,0)}")
    check('60분 클리어(endRun)하면 지워진다', has and await pg.evaluate("()=>[__R.state,localStorage.getItem('p6_resume_v1')]") == ['result', None], await pg.evaluate("()=>__R.state"))
    await pg.close()
    # 4) 버리기(2단계 확인)
    pg = await fresh(blob)
    await pg.click('#resDel'); mid = await pg.evaluate("()=>[document.getElementById('resDel').textContent,localStorage.getItem('p6_resume_v1')!==null]")
    check('버리기는 한 번에 안 사라진다(\'한 번 더 누르면 사라져요\')', mid[1] and '한 번 더' in mid[0], mid)
    await pg.click('#resDel'); check('한 번 더 누르면 버려진다', await pg.evaluate("()=>[document.getElementById('resCard').hidden,localStorage.getItem('p6_resume_v1')]") == [True, None])
    await pg.close()
    # 5) 손상·만료·버전 불일치
    for mode, silent, label in (('old', True, '12시간 지난 저장본'), ('future', True, '시계가 앞서 간 저장본'), ('sig', True, '표 서명이 다른(배포로 바뀐) 저장본'), ('ver', True, '포맷 번호가 다른 저장본'), ('char', True, '없는 캐릭터'), ('state', True, '결과 화면 상태'),
                                ('trunc', False, '잘린 저장본'), ('ck', False, '검사합이 안 맞는 저장본'), ('garble', False, '깨진 JSON'), ('weapon', False, '없는 무기가 든 저장본'), ('nan', False, 'NaN 체력'), ('neg', False, '음수 시간'),
                                ('badref', False, '없는 칸을 가리키는 참조'), ('badstatic', False, '없는 표 경로'), ('badkind', False, '없는 적 종류')):
        n0 = len(C.errs)
        try: mod = await crafted(mode)
        except Exception as ex:
            check('[%s] 시험용 저장본을 만든다' % label, False, repr(ex)[:200]); continue
        pg = await fresh(mod)
        card = await pg.evaluate("()=>!document.getElementById('resCard').hidden")
        if silent:
            gone = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')") is None
            check('[%s] 조용히 폐기된다(카드 없음 · 저장본 삭제 · 오류 없음)' % label, (not card) and gone and len(C.errs) == n0, (card, gone, C.errs[n0:]))
        else:
            if card:
                await pg.click('#resGo'); await pg.wait_for_timeout(300)
            st = await pg.evaluate("()=>[__R.state,document.getElementById('title').classList.contains('on'),localStorage.getItem('p6_resume_v1'),document.getElementById('resMsg').hidden,document.getElementById('resMsg').textContent]")
            ok = (not card) or (st[0] == 'title' and st[1] and st[2] is None and not st[3] and '실패' in st[4])
            check('[%s] 복구에 실패해도 제목 화면으로 돌아온다(저장본 삭제 · 안내 한 줄)' % label, ok and len(C.errs) == n0, (card, st, C.errs[n0:]))
            # 그다음 새 판은 정상 시작
            await pg.click('#startBtn'); ok2 = await pg.evaluate("()=>{__run(2,0);return __R.state}")
            check('[%s] 실패 뒤 새 판이 정상으로 시작된다' % label, ok2 == 'play' and len(C.errs) == n0, (ok2, C.errs[n0:]))
        await pg.close()
    # 6) 일일 도전 날짜가 이틀 이상 지난 판은 연습으로
    await A.evaluate(FORGE, dict(ch='brj', t0=200, daily=True)); await A.evaluate("()=>{__run(3,0);__R.pauseGame();}")
    dblob = await A.evaluate("()=>localStorage.getItem('p6_resume_v1')")
    m = await (await C.page()).evaluate(CRAFT, [dblob, 'dly_old'])
    pg = await fresh(m); await pg.click('#resGo'); await pg.wait_for_function("__R.state==='pause'")
    check('이틀 지난 오늘의 도전 판은 기록 안 되는 연습으로 이어진다', await pg.evaluate("()=>[__R.S.dly.date,__R.S.dly.ranked]") == ['2020-01-01', False])
    await pg.close()
    # 6-2) 표 서명은 기기 상태(진행도·고른 캐릭터·창 크기)와 상관없이 같다 — 아니면 멀쩡한 저장본이 서명 불일치로 버려진다
    PROG = "(()=>{try{localStorage.setItem('p6_prog_v1',JSON.stringify({deaths:9,kills:99999,midKill:50,bossKill:40,maxLv:99,best:3600,bk:{brj:1,sr:1,yj:1,ddo:1,bgb:1,psg:1},w5:{}}));localStorage.setItem('p6_char_v1','sr');localStorage.setItem('p6_hard','1');}catch(e){}})();"
    sigs = []
    for kw in (dict(), dict(init=PROG), dict(w=360, h=640, mobile=True), dict(hc=2)):
        Cx = await Ctx(b, srv.port, seed=5, **kw).open(); Px = await Cx.page(); sigs.append(await Px.evaluate("()=>__R.RES.SIG")); await Cx.close()
    check('표 서명(SIG)이 진행도·캐릭터·화면 크기·코어 수가 달라도 같다(%s)' % sigs[0], len(set(sigs)) == 1 and re.match(r'^1:\d+:\d+$', sigs[0]), sigs)
    # 7) 저사양(풀 크기 불일치)
    CL = await Ctx(b, srv.port, seed=5, hc=2, w=900, h=900).open(); L = await CL.page()
    check('(저사양 환경 확인) LOW=true', await L.evaluate("()=>__R.LOW") is True)
    await L.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", blob); await L.reload(); await L.wait_for_function('window.__R!==undefined')
    vis = await L.evaluate("()=>!document.getElementById('resCard').hidden")
    if vis: await L.click('#resGo'); await L.wait_for_timeout(300)
    st = await L.evaluate("()=>[__R.state,localStorage.getItem('p6_resume_v1')]")
    check('큰 기기에서 저장한 판을 저사양 환경에서 열면(풀이 작아 칸이 모자람) 안전하게 거부하고 제목으로 돌아온다', st == ['title', None] and not CL.errs, (st, CL.errs))
    await L.click('#startBtn'); check('저사양에서도 새 판은 정상', await L.evaluate("()=>{__run(2,0);return __R.state}") == 'play')
    await CL.close()
    # 반대 방향(저사양 → 큰 기기)은 복구된다
    CL = await Ctx(b, srv.port, seed=5, hc=2, w=900, h=900).open(); L = await CL.page()
    await L.evaluate(FORGE, dict(ch='brj', t0=500)); await L.evaluate("()=>{__run(8,0);__R.pauseGame();}"); lblob = await L.evaluate("()=>localStorage.getItem('p6_resume_v1')")
    await CL.close()
    pg = await fresh(lblob); await pg.click('#resGo'); await pg.wait_for_function("__R.state==='pause'", timeout=5000)
    check('저사양에서 저장한 판은 큰 기기에서 복구된다', await pg.evaluate("()=>__R.state") == 'pause'); await pg.close()
    check('스크립트 오류 없음', not C.errs, C.errs[:5]); await C.close()

# ═════════════ 마. 저장소 차단 ═════════════
BLOCK = {
  'setItem 거부': "Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};",
  'localStorage 접근 거부': "Object.defineProperty(window,'localStorage',{get(){throw new DOMException('denied','SecurityError')},configurable:true});",
  '이어하기 칸만 용량 초과': "(()=>{const s=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).startsWith('p6_resume')&&k!=='p6_resume_probe')throw new DOMException('quota','QuotaExceededError');return s.call(this,k,v);};})();",
}
async def sec_blocked(b, srv):
    print('\n── 마. 저장소 차단 환경 ──', flush=True)
    for name, js in BLOCK.items():
        C = await Ctx(b, srv.port, seed=9, init=js).open(); pg = await C.page()
        # 이어하기 칸만 막힌 경우는 probe(작은 쓰기)가 통과하므로 '저장 실패' 경로를 탄다
        note = await pg.evaluate("()=>[document.getElementById('resNote').hidden,document.getElementById('resNoteTxt').textContent,document.getElementById('resCard').hidden]")
        if name == '이어하기 칸만 용량 초과':
            check('[%s] 제목 화면: 카드 없음' % name, note[2])
        else:
            check('[%s] 제목 화면에 \'저장이 안 돼요\' 안내가 한 줄 뜬다' % name, (not note[0]) and '저장이 안 돼요' in note[1], note)
            check('[%s] 카드는 없다' % name, note[2])
        ok = await pg.evaluate("""()=>{const R=__R;R.CH_set('brj');R.start();__run(20,0);const s1=R.state;R.pauseGame();const s2=R.state;R.resume();
          R.S.pendingLv=1;R.S.lv++;R.openLvup();const s3=R.state;R.pick(R.CUR[0]);__run(5,0);R.openChest();const s4=R.state;R.resume();__run(5,0);
          return [s1,s2,s3,s4,R.state,R.RES.info.ok,R.RES.info.fails,R.RES.info.saves]}""")
        check('[%s] 게임이 평소처럼 돈다(시작 · 일시정지 · 레벨업 · 상자 · 계속)' % name, ok[:5] == ['play', 'pause', 'lvup', 'chest', 'play'], ok)
        if name == '이어하기 칸만 용량 초과':
            pinfo = await pg.evaluate("()=>{__R.pauseGame();return document.getElementById('pInfo').innerText}")
            check('[%s] 저장이 실패한 판의 일시정지 화면에 한 줄 경고' % name, '저장이 막혀' in pinfo and ok[6] >= 1, (ok, pinfo[-80:]))
        else:
            check('[%s] 저장을 시도하지 않는다(info.ok=false)' % name, ok[5] is False and ok[7] == 0, ok)
        # 플레이 도중 숨김 이벤트에도 오류가 없다
        await pg.evaluate("""()=>{__R.resume();Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));dispatchEvent(new Event('pagehide'));}""")
        check('[%s] 숨김·페이지 떠남 이벤트에도 오류 없이 일시정지만 된다' % name, await pg.evaluate("()=>__R.state") in ('pause',) , await pg.evaluate("()=>__R.state"))
        check('[%s] 콘솔/페이지 오류 0' % name, not C.errs, C.errs[:4]); await C.close()

# ═════════════ 바. 미래 보호 ═════════════
INJECT = r"""()=>{const R=__R,out={};
 const run=(label,fn,undo)=>{fn();let b=null,err=null;try{b=R.RES.build();}catch(e){err=String(e);}
   let saved=null;try{saved=R.RES.save('test');}catch(e){err='save:'+e;}
   out[label]={text:!!(b&&b.text),why:b&&b.why,bad:b&&b.bad,err,saved,slot:localStorage.getItem('p6_resume_v1')!==null};undo();};
 R.CH_set('brj');R.start();__run(10,0);R.pauseGame();
 const S=R.S,e0=R.pools.enemies.a.find(e=>e.on);
 localStorage.removeItem('p6_resume_v1');
 out.base={ok:R.RES.build().text!==null};
 run('S.함수',()=>{S.future={cb:()=>1}},()=>{delete S.future;});
 run('S.DOM',()=>{S.el=document.createElement('div')},()=>{delete S.el;});
 run('S.Image',()=>{S.img=new Image()},()=>{delete S.img;});
 run('풀 칸 함수',()=>{e0.onDeath=()=>1},()=>{delete e0.onDeath;});
 run('풀 칸 Image',()=>{e0.pic=new Image()},()=>{delete e0.pic;});
 run('중첩 객체 안 함수',()=>{S.x3.f.push({k:'zz',cb:function(){}})},()=>{S.x3.f.pop();});
 run('클래스 인스턴스',()=>{S.inst=new (class Q{})()},()=>{delete S.inst;});
 run('Map 안 함수',()=>{S.mm=new Map([['a',()=>1]])},()=>{delete S.mm;});
 run('허용: S.dq[].f',()=>{S.dq.push({t:1,f:()=>1})},()=>{S.dq.length=0;});
 run('허용: Map/Set/typed/NaN',()=>{S.ok1=new Map([['a',{x:1}]]);S.ok2=new Set([1,2]);S.ok3=new Float32Array(3);S.ok4=NaN},()=>{delete S.ok1;delete S.ok2;delete S.ok3;delete S.ok4;});
 out.after=R.RES.build().text!==null;out.state=R.state;
 out.poolsOk=R.RES.info.poolsOk;
 // 새 풀이 생기면(분류 안 된 풀) 저장을 끈다
 const P2=new (R.pools.enemies.constructor)(1,()=>({x:0}));R.RES.build();out.poolsOk2=R.RES.info.poolsOk;
 return out;}"""
async def sec_future(b, srv):
    print('\n── 바. 미래 보호(새로 생긴 함수·DOM·Image · 분류 안 된 풀/상태) ──', flush=True)
    C = await Ctx(b, srv.port, seed=3).open(); pg = await C.page()
    o = await pg.evaluate(INJECT)
    check('(기준) 평범한 상태는 저장할 수 있다', o['base']['ok'])
    for k in ('S.함수', 'S.DOM', 'S.Image', '풀 칸 함수', '풀 칸 Image', '중첩 객체 안 함수', '클래스 인스턴스', 'Map 안 함수'):
        r = o[k]
        check('[%s] 상태에 새로 생기면 저장을 거부한다(저장 안 함 · 오류 없음 · 이유가 남음)' % k, (not r['text']) and r['why'] == 'unsupported' and r['bad'] and not r['err'] and r['saved'] is False and not r['slot'], r)
    for k in ('허용: S.dq[].f', '허용: Map/Set/typed/NaN'):
        r = o[k]; check('[%s] 허용된 값은 저장된다' % k, r['text'] and not r['err'], r)
    check('거부한 뒤에도 게임 상태는 멀쩡하다', o['after'] and o['state'] == 'pause')
    check('풀 목록이 분류표와 맞는다(poolsOk)', o['poolsOk'] is True)
    check('분류 안 된 새 풀이 생기면 감지한다(poolsOk=false → 저장을 끈다)', o['poolsOk2'] is False, o)
    check('콘솔 오류는 \'저장 불가\' 경고뿐(시험이 일부러 만든 것)', all('이어하기' in e or 'CONSOLE' in e for e in C.errs), C.errs[:5])
    await C.close()
    # 분류표 — 소스에 새 최상위 let·가변 컨테이너·풀이 생기면 실패한다(새 상태는 저장/재계산/버림 중 어느 것인지 정하게 한다)
    src = open(os.path.join(H.ROOT, 'survivors.html'), encoding='utf-8').read()
    names = scan_toplevel(src)
    known = CLASSIFIED
    unknown = sorted(set(names) - set(known))
    check('최상위 let/가변 컨테이너가 전부 분류돼 있다 — 새로 생긴 것: %s' % (unknown or '없음'), not unknown,
          '새 상태를 만들었으면 저장(RES 가 걸어 줌: S/풀에 넣거나 mod 에 추가) · 재계산 · 버림 중 정해서 CLASSIFIED 에 적으세요: ' + ', '.join(unknown))
    gone = sorted(set(known) - set(names))
    check('분류표에 있지만 소스에서 사라진 이름이 없다(표 정리): %s' % (gone or '없음'), not gone, gone)
    npool = len(re.findall(r'=new Pool\(', src))
    check('new Pool( 개수(%d)가 RES 의 풀 목록(22)과 같다' % npool, npool == 22, npool)

def scan_toplevel(src):
    """IIFE 최상위(줄 맨 앞)에서 선언된 let 이름 + 가변 컨테이너 const(new Map/Set, [], {}) 이름. 문자열·괄호를 아는 간단한 훑개."""
    body = src[src.index('(()=>{\n\'use strict\';'):]
    names = []
    for line in body.split('\n'):
        if not line or line[0] in ' \t/<' : continue
        if not (line.startswith('let ') or line.startswith('const ')):
            # 한 줄에 여러 문장: "const A={};let B=null;" 처럼 뒤에 let 이 따라오는 경우를 본다
            if not re.match(r'^(function|async|window|for|if|\}|\{|\(|[A-Za-z_$][\w$.\[\]]*\s*[=(.])', line): continue
        # 문장 분리(따옴표·괄호 안의 ; 는 무시)
        stmts, cur, depth, q, i = [], '', 0, None, 0
        while i < len(line):
            c = line[i]
            if q:
                cur += c
                if c == '\\': cur += line[i + 1:i + 2]; i += 1
                elif c == q: q = None
            elif c in '\'"`': q = c; cur += c
            elif c == '/' and line[i + 1:i + 2] == '/': break
            elif c in '([{': depth += 1; cur += c
            elif c in ')]}': depth -= 1; cur += c
            elif c == ';' and depth == 0: stmts.append(cur); cur = ''
            else: cur += c
            i += 1
        if cur.strip(): stmts.append(cur)
        for st in stmts:
            st = st.strip()
            m = re.match(r'^(let|const)\s+(.*)$', st)
            if not m: continue
            kind, rest = m.group(1), m.group(2)
            decl, cur, depth, q = [], '', 0, None
            for j, c in enumerate(rest):                                  # 최상위 쉼표로 선언을 나눈다
                if q:
                    cur += c
                    if c == q and rest[j - 1] != '\\': q = None
                    continue
                if c in '\'"`': q = c
                if c in '([{': depth += 1
                if c in ')]}': depth -= 1
                if c == ',' and depth == 0: decl.append(cur); cur = ''
                else: cur += c
            decl.append(cur)
            for d in decl:
                mm = re.match(r'^\s*([A-Za-z_$][\w$]*)\s*(=\s*(.*))?$', d, re.S)
                if not mm: continue
                nm, init = mm.group(1), (mm.group(3) or '').strip()
                if kind == 'let' or re.match(r'^(new (Map|Set|WeakMap|Pool)\b|\[\s*\]|\{\s*\})', init): names.append(nm)
    return names
# 분류: S=판 상태(저장) · MOD=mod 로 저장 · DERIVE=복구 때 다시 계산 · RESET=복구 때 초기화 · UI=판 상태 아님(서버/설정/화면) · CACHE=그림·성능 캐시 · POOL=풀(RES.POOL)
CLASSIFIED = {
 'W': 'DERIVE', 'H': 'DERIVE', 'DPR': 'DERIVE', 'SC': 'DERIVE', 'VW': 'DERIVE', 'VH': 'DERIVE', 'SPAWN_R': 'DERIVE', 'DESP_R': 'DERIVE',
 'D0': 'CACHE', 'ICON': 'CACHE', 'DDV': 'CACHE',
 'RSEED': 'DERIVE', 'ME': 'UI', 'BOARD': 'UI', 'BOARDE': 'UI', 'BOARDEH': 'UI', 'BOARDEV': 'UI', 'BOARDD': 'UI', 'SRV_END': 'UI', 'SRV_DLY': 'UI', 'DLY_DATE': 'UI', 'BOARDH': 'UI', 'BOARDV': 'UI', 'SRV_VH': 'UI', 'BTAB': 'UI',
 'HARD_ON': 'UI', 'VH_ON': 'UI', 'SRVUNL': 'UI', 'BDI': 'CACHE', 'ART': 'CACHE', 'CH': 'MOD',
 'SN': 'MOD', 'gemMT': 'MOD', 'gemGrid': 'RESET', 'toastT': 'RESET', 'S': 'S', 'RUN': 'MOD', 'state': 'MOD', 'keys': 'RESET', 'joy': 'RESET', 'SRC': 'RESET', 'LASTDLY': 'DERIVE',
 'CUR': 'MOD', 'BUMP': 'CACHE', 'BIMG': 'CACHE', 'bannerT': 'MOD', 'bannerS': 'MOD', 'bannerS2': 'MOD', 'bannerA': 'MOD', 'bannerQ': 'MOD',
 'RDEV': 'DERIVE', 'RDEV_S': 'DERIVE', 'RDEV_MAX': 'DERIVE', 'RDEV_BUD': 'DERIVE', 'last': 'RESET', 'RIFT_CACHE': 'DERIVE', 'RIFT_MAX': 'DERIVE', 'RIFT_BUD': 'DERIVE',
 'enemies': 'POOL', 'shots': 'POOL', 'gems': 'POOL', 'texts': 'POOL', 'rangs': 'POOL', 'bolts': 'POOL', 'waves': 'POOL', 'puds': 'POOL', 'clouds': 'POOL', 'cans': 'POOL', 'allies': 'POOL', 'items': 'POOL', 'props': 'POOL', 'bubs': 'POOL', 'hazards': 'POOL', 'eshots': 'POOL',
 'rkts': 'POOL', 'pets': 'POOL', 'hooks': 'POOL', 'frs': 'POOL', 'holes': 'POOL', 'snps': 'POOL',
}

# ═════════════ 사. 두 창 · 저장 시점 · 시간 · 비밀 · 오늘의 도전 · UI ═════════════
async def sec_misc(b, srv):
    print('\n── 사. 두 창 · 저장 시점 · 저장 시간 · 비밀 · 오늘의 도전 · 제목 화면 UI ──', flush=True)
    # 저장 시점
    C = await Ctx(b, srv.port, seed=21).open(); A = await C.page()
    await A.evaluate(FORGE, dict(ch='brj', t0=300)); await A.evaluate("()=>{__run(20,0)}")
    s0 = await A.evaluate("()=>[__R.RES.info.saves,localStorage.getItem('p6_resume_v1')]")
    await A.evaluate("()=>{__run(40,0)}"); s1 = await A.evaluate("()=>[__R.RES.info.saves,localStorage.getItem('p6_resume_v1')]")
    check('판이 도는 동안에는(주기 저장 없음) 저장하지도, 저장본이 남아 있지도 않다', s0[1] is None and s1[1] is None and s1[0] == s0[0], (s0[0], s1[0]))
    EVT = {
      'visibilitychange(숨김)': "()=>{Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));}",
      'pagehide': "()=>{dispatchEvent(new Event('pagehide'));}",
      'freeze': "()=>{document.dispatchEvent(new Event('freeze'));}",
      'blur': "()=>{dispatchEvent(new Event('blur'));}",
      '⏸ 버튼': "()=>{document.getElementById('pauseBtn').click();}",
      'ESC 키': "()=>{dispatchEvent(new KeyboardEvent('keydown',{code:'Escape'}));}",
    }
    for name, js in EVT.items():
        await A.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});}")
        await A.evaluate("()=>{if(__R.state!=='play'){__R.resume();} localStorage.removeItem('p6_resume_v1');}")
        await A.evaluate(js)
        r = await A.evaluate("()=>{const p=__R.RES.peek();return [__R.state,p&&p.st,p&&p.t]}")
        check('[%s] 판 도중에 오면 일시정지 + 저장된다' % name, r[0] == 'pause' and r[1] == 'pause', r)
    await A.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});}")
    # 레벨업·상자에서 숨겨져도 그 상태로 저장
    await A.evaluate("()=>{__R.resume();__R.S.pendingLv=1;__R.S.lv++;__R.openLvup();localStorage.removeItem('p6_resume_v1');Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));}")
    r = await A.evaluate("()=>{const p=__R.RES.peek();return [__R.state,p&&p.st]}"); check('레벨업 카드가 떠 있는 채 숨겨지면 lvup 으로 저장', r == ['lvup', 'lvup'], r)
    await A.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});__R.pick(__R.CUR[0]);__R.openChest();localStorage.removeItem('p6_resume_v1');Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));}")
    r = await A.evaluate("()=>{const p=__R.RES.peek();return [__R.state,p&&p.st]}"); check('상자가 떠 있는 채 숨겨지면 chest 로 저장', r == ['chest', 'chest'], r)
    await A.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});}")
    # 숨김 → 일시정지는 기존 동작 그대로(play 일 때만 pauseGame · 다른 화면에서는 음악만 조용히)
    check('스크립트 오류 없음', not C.errs, C.errs[:4]); await C.close()
    # 두 창
    C = await Ctx(b, srv.port, seed=22).open(); A = await C.page()
    await A.evaluate(FORGE, dict(ch='brj', t0=600)); await A.evaluate("()=>{__run(8,0);__R.pauseGame();}")
    B = await C.page()
    await B.reload(); await B.wait_for_function('window.__R!==undefined')
    check('[두 창] 다른 창에서도 같은 카드가 보인다', await B.evaluate("()=>!document.getElementById('resCard').hidden"))
    await B.click('#resGo'); await B.wait_for_function("__R.state==='pause'")
    gen = await B.evaluate("()=>__R.RUN.gen")
    await A.evaluate("()=>{dispatchEvent(new Event('focus'));}")
    st = await A.evaluate("()=>[__R.state,document.getElementById('title').classList.contains('on'),document.getElementById('resMsg').hidden,document.getElementById('resMsg').textContent]")
    check('[두 창] 한 창이 이어받으면 원래 창의 판은 닫힌다(둘이 같은 판을 이어가지 못함)', st[0] == 'title' and st[1] and not st[2] and '닫혔' in st[3], st)
    A2 = await C.page(); await A2.evaluate(FORGE, dict(ch='brj', t0=300))
    # B 가 계속→일시정지로 진행한 저장본을 낡은 창이 덮어쓰지 못한다
    await B.click('#resumeBtn'); await B.evaluate("()=>{__run(5,0);__R.pauseGame();}")
    hB = await B.evaluate("()=>__R.RES.peek()")
    await A.evaluate("()=>{__R.RES.save('stale')}")
    hB2 = await B.evaluate("()=>__R.RES.peek()")
    check('[두 창] 낡은 창이 새 창의 저장본을 덮어쓰지 못한다', hB2 and hB and hB2['ts'] == hB['ts'] and hB2['rid'] == hB['rid'] and hB2['gen'] == gen, (hB, hB2))
    await A2.close(); await B.close(); await A.close()
    # 더 새 판의 저장본을 오래된 판이 덮어쓰지 않는다
    X = await C.page(); await X.evaluate(FORGE, dict(ch='brj', t0=300)); await X.evaluate("()=>{__run(3,0);__R.pauseGame();}")
    rx = await X.evaluate("()=>__R.RES.peek().rid")
    Y = await C.page()
    await Y.evaluate(FORGE, dict(ch='sr', t0=300)); await Y.evaluate("()=>{__run(3,0);__R.pauseGame();}")
    ry = await Y.evaluate("()=>__R.RES.peek().rid")
    await X.evaluate("()=>{__R.RES.save('older')}"); rz = await X.evaluate("()=>__R.RES.peek().rid")
    check('[두 창] 더 늦게 시작한 판의 저장본을 먼저 시작한 판이 덮어쓰지 않는다', rx != ry and rz == ry, (rx, ry, rz))
    check('[두 창] 오류 없음', not C.errs, C.errs[:4]); await C.close()
    # 비밀·개인정보
    SECRET = "(()=>{try{localStorage.setItem('sgg_dc',JSON.stringify({id:'123456789',name:'홍길동비밀',avatar:'AVATARSECRET',token:'SECRETTOKEN-abc123',exp:Date.now()+30*86400000,birth:'1990-01-01'}));localStorage.setItem('sgg_dc_auto',JSON.stringify({id:'123456789',name:'홍길동비밀',avatar:'x'}));}catch(e){}})();"
    C = await Ctx(b, srv.port, seed=23, init=SECRET).open(); A = await C.page()
    await A.evaluate("()=>localStorage.setItem('p6_unsent',JSON.stringify({t:5,kills:1,ts:Date.now()}))")
    unsent0 = await A.evaluate("()=>localStorage.getItem('p6_unsent')")
    for mode in ('n', 'd'):
        await A.evaluate(FORGE, dict(ch='brj', t0=700, daily=mode == 'd')); await A.evaluate("()=>{__run(10,0);__R.pauseGame();}")
        blob = await A.evaluate("()=>localStorage.getItem('p6_resume_v1')")
        leaks = [w for w in ('SECRETTOKEN', 'sgg_dc', 'token', '홍길동비밀', 'AVATARSECRET', '123456789', '1990-01-01', 'birth') if w in blob]
        check('[비밀/%s] 저장본에 로그인 토큰·이름·아이디·생년이 없다' % mode, not leaks, leaks)
        if mode == 'd':
            dly = await A.evaluate("()=>__R.S.dly")
            check('[오늘의 도전] 로그인한 사람의 판은 기록 판(ranked)이다', dly and dly['ranked'] is True, dly)
            dg = await A.evaluate("()=>localStorage.getItem('p6_daily_v1')")
            B = await C.page(); await B.reload(); await B.wait_for_function('window.__R!==undefined')
            await B.click('#resGo'); await B.wait_for_function("__R.state==='pause'")
            d2 = await B.evaluate("()=>[__R.S.dly.ranked,__R.S.dly.date,__R.dailyGet()]")
            check('[오늘의 도전] 복구해도 기록 판 그대로 · 하루 한 판 기록(p6_daily_v1)은 건드리지 않는다', d2[0] is True and json.dumps(d2[2], sort_keys=True) == json.dumps(json.loads(dg), sort_keys=True), (d2, dg))
            await B.close()
    u1 = json.loads(await A.evaluate("()=>localStorage.getItem('p6_unsent')") or 'null'); u0 = json.loads(unsent0)   # (게임의 flushUnsent 가 2.5초 뒤 ts 를 새로 찍을 수 있어 내용만 본다)
    check('미전송 기록(p6_unsent)은 저장·복구와 무관하게 그대로', u1 and (u1['t'], u1['kills']) == (u0['t'], u0['kills']), (u0, u1))
    check('로그인 정보(sgg_dc)는 이어하기가 지우지 않는다', await A.evaluate("()=>localStorage.getItem('sgg_dc')!==null"))
    check('스크립트 오류 없음', not C.errs, C.errs[:4]); await C.close()
    # 저장 시간(후반 판 · CPU 4배 느리게) — 상대 비교: 업데이트 1스텝과 견준다
    C = await Ctx(b, srv.port, seed=24, w=900, h=900).open(); A = await C.page()
    M = await A.evaluate("()=>__META()"); rng = random.Random(3)
    sp = rand_spec(M, rng, 'brj', 'n', t0=2700, full=True)
    await A.evaluate(FORGE, sp); await A.evaluate("()=>{__run(25,0)}")
    cdp = await C.ctx.new_cdp_session(A); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    best = None
    for attempt in range(2):
        r = await A.evaluate("""()=>{const R=__R;const t0=performance.now();let n=0;for(let i=0;i<20&&R.state==='play';i++){R.update(1/30);n++;}const step=(performance.now()-t0)/Math.max(1,n);
          R.pauseGame();const ms=[];for(let i=0;i<5;i++){localStorage.removeItem('p6_resume_v1');R.RES.info.rep=null;const t=performance.now();R.RES.save('perf'+i);ms.push(performance.now()-t);}
          const len=(localStorage.getItem('p6_resume_v1')||'').length;R.resume();return {step,ms,len,nE:R.pools.enemies.a.filter(e=>e.on).length}}""")
        best = r
        if min(r['ms']) < 200: break
    print('   저장 시간(4배 느리게 · 적 %d마리 · %dKB): 최소 %.0fms 중앙 %.0fms · update 1스텝 %.1fms · 부하 %.1f' % (r['nE'], r['len'] // 1024, min(r['ms']), sorted(r['ms'])[2], r['step'], load_avg()), flush=True)
    check('저장 한 번이 1/10초 안(4배 느린 CPU에서 200ms 미만)에 끝난다 — 이탈 처리를 오래 붙잡지 않는다', min(best['ms']) < 200, best)
    check('저장본 크기가 localStorage 한도(약 5MB)의 5% 안', best['len'] < 250000, best['len'])
    await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1}); await C.close()
    # 제목 화면 UI
    for (w, h) in ((360, 640), (412, 860)):
        C = await Ctx(b, srv.port, w=w, h=h, seed=25, mobile=True).open(); A = await C.page()
        await A.evaluate(FORGE, dict(ch='brj', t0=700)); await A.evaluate("()=>{__run(10,0);__R.pauseGame();}")
        blob = await A.evaluate("()=>localStorage.getItem('p6_resume_v1')")
        B = await C.page(); await B.reload(); await B.wait_for_function('window.__R!==undefined'); await B.wait_for_timeout(300)
        g = await B.evaluate("""()=>{const r=e=>{const b=document.getElementById(e).getBoundingClientRect();return [b.top,b.bottom,b.left,b.right,b.height]};
          const bx=document.querySelector('#title .box');return {card:r('resCard'),go:r('resGo'),del:r('resDel'),start:r('startBtn'),vh:innerHeight,vw:innerWidth,sw:document.documentElement.scrollWidth,boxsw:bx.scrollWidth,boxcw:bx.clientWidth,
            msg:document.getElementById('resMsg').hidden,vis:!document.getElementById('resCard').hidden}}""")
        shots = os.environ.get('RES_SHOTS')          # 화면 캡처를 보고 싶을 때만: RES_SHOTS=/저장/폴더 (기본은 저장 안 함)
        if shots:
            os.makedirs(shots, exist_ok=True)
            try: await B.screenshot(path=os.path.join(shots, 'title_%dx%d.png' % (w, h)))
            except Exception: pass
        check('[%dx%d] 이어하기 카드가 처음 화면(스크롤 없이) 안에 보인다' % (w, h), g['vis'] and g['card'][0] >= 0 and g['card'][1] <= g['vh'], g)
        check('[%dx%d] 버튼이 손가락으로 누를 만한 크기(높이 44px 이상) · 가로로 안 잘린다' % (w, h), g['go'][4] >= 44 and g['del'][4] >= 44 and g['go'][3] <= g['vw'] + 1 and g['del'][3] <= g['vw'] + 1, g)
        check('[%dx%d] 카드와 \'▶ 시작하기\' 버튼이 겹치지 않는다' % (w, h), g['card'][1] <= g['start'][0] or g['start'][0] >= g['vh'] or g['start'][1] <= g['card'][0], g)
        check('[%dx%d] 가로 스크롤이 없다' % (w, h), g['sw'] <= g['vw'] and g['boxsw'] <= g['boxcw'] + 1, g)
        check('[%dx%d] 로드 직후 자동 안내(깜빡이는 카드 + 안내 한 줄)' % (w, h), (not g['msg']) and await B.evaluate("()=>document.getElementById('resCard').classList.contains('flash')"))
        check('[%dx%d] 오류 없음' % (w, h), not C.errs, C.errs[:3]); await C.close()
    # 앱 안의 작은 브라우저 안내(UA 표지가 있는 것만 · 한 번 · 닫으면 다시 안 보임)
    UAK = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 KAKAOTALK 10.4.1'
    UAS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'
    C = await Ctx(b, srv.port, seed=26, ua=UAK, mobile=True, w=390, h=800).open(); A = await C.page()
    t1 = await A.evaluate("()=>[document.getElementById('resNote').hidden,document.getElementById('resNoteTxt').textContent,document.getElementById('resNoteCopy').hidden]")
    check('[카톡 내장 브라우저] 외부 브라우저 안내가 뜬다(링크 복사 버튼 포함)', (not t1[0]) and '다른 브라우저' in t1[1] and not t1[2], t1)
    await A.click('#resNoteX'); check('닫으면 숨는다', await A.evaluate("()=>document.getElementById('resNote').hidden"))
    await A.reload(); await A.wait_for_function('window.__R!==undefined')
    check('닫은 뒤에는 다시 열어도 안 뜬다(한 번만)', await A.evaluate("()=>document.getElementById('resNote').hidden"))
    await A.evaluate("()=>{__R.CH_set('brj');__R.start();}"); check('(안내가 게임 시작을 막지 않는다)', await A.evaluate("()=>__R.state") == 'play')
    await C.close()
    C = await Ctx(b, srv.port, seed=27, ua=UAS, mobile=True, w=390, h=800).open(); A = await C.page()
    check('[일반 사파리] 안내가 안 뜬다', await A.evaluate("()=>document.getElementById('resNote').hidden")); await C.close()
    C = await Ctx(b, srv.port, seed=28, ua=UAK, mobile=True, w=390, h=800).open(); A = await C.page()
    await A.evaluate(FORGE, dict(ch='brj', t0=400)); await A.evaluate("()=>{__run(6,0);__R.pauseGame();}"); B = await C.page(); await B.reload(); await B.wait_for_function('window.__R!==undefined')
    check('[카톡 내장 브라우저] 이어하기 카드가 있는 날은 카드가 우선(안내는 생략)', await B.evaluate("()=>[!document.getElementById('resCard').hidden,document.getElementById('resNote').hidden]") == [True, True]); await C.close()
    # 기존 동작 보존: 숨김 시 일시정지 · 일시정지 중 시간 정지 · 오늘의 도전 · 무한 모드 질문
    C = await Ctx(b, srv.port, seed=29).open(); A = await C.page()
    await A.evaluate(FORGE, dict(ch='brj', t0=3590)); r = await A.evaluate("()=>{__R.resume&&0;__run(15,0);return [__R.state,__R.S.won,document.getElementById('endAsk').classList.contains('on')]}")
    check('60분 클리어 → 결과 화면 + 무한 모드 질문이 그대로 뜬다', r == ['result', True, True], r)
    await A.evaluate("()=>__R.contEndless()"); check('무한 모드로 이어가기 그대로', await A.evaluate("()=>[__R.state,__R.S.endless]") == ['play', 1])
    await A.evaluate("()=>{__run(3,0);__R.pauseGame();}"); eb = await A.evaluate("()=>__R.RES.peek()")
    check('무한 모드 판도 저장된다(모드 표시 e)', eb and eb['m'] == 'e', eb)
    check('스크립트 오류 없음', not C.errs, C.errs[:4]); await C.close()

sys.exit(asyncio.run(main()))
