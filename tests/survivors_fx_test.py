# -*- coding: utf-8 -*-
"""🧩 흐접새우 서바이벌 「패시브 × 무기 구분」 시험 — 2026-10-10 사장님 지시
   「속사같은 패시브스킬에 스킬구분을 명확하게 해서 어떤스킬이 강화되고안되고 헷갈릴 여지를 제거해줘」

   사용: nice -n 10 python3 tests/survivors_fx_test.py [--full] [--only 가,나,...] [--no-mutation]
         (종료코드 0 = 전부 통과 · 기본 약 2~4분 · --full = 표의 모든 칸을 게임으로 다시 잰다, 15분 안팎)
   구성
     가  정적 — 정답표 PFX 가 WEAP 40개와 1:1 · 글자 값 유효 · p 칸마다 쉬운 말 설명(없는 칸엔 설명도 없다) · 채널 표(PFXCH)·패시브 연결 ·
         행운은 가챠 캡슐만 · 금지 문구(「모든 쿨타임」「모든 범위」「투사체」「짝 패시브」「카트 2대」…)가 표 어디에도 없다
     나  숫자 묶기 — 설명문의 숫자는 게임이 쓰는 값(PS()·cdMul()·areaMul()·DUR()·critChance()·critMul() …)을 읽는 시험으로 묶는다
     다  화면 — 18캐릭터 × 대표 빌드로 패시브 카드·무기 카드·보스 상자·일시정지 표·도감 상세를 그려 본다: 쓰인 무기 이름은 모두 실제 이름 ·
         페이지 오류 0 · 폰 폭(320·360·412)에서 가로 넘침 0 · 접이식 표는 기본 접힘 · 요약줄 터치 대상 40px · 글자 대비 4.5 이상 · 도감은 발견한 것만
     라  표류 방지 — 표를 실제 게임으로 증명한다: 한 무기만 든 판을 패시브 끔/켬(3겹)·같은 시드로 돌려(update() 그대로) 차이를 잰다.
         y = 눈에 띄게 세진다 · n = 판 전체가 비트까지 같다(아무것도 안 읽는다) · p = 달라지긴 한다. 기본은 p 칸 전부 + 대표 y/n 칸, --full 은 전 칸
     마  변이 — 표의 한 칸을 일부러 틀리게 한 변형으로 라 단계가 빨갛게 되는지(시험이 이빨이 있는지) 확인
     바  불변 — 새 S 키 0 · 이어하기 서명(RES.SIG)이 기준 커밋과 같다
   임시 사본 survivors_fx_t.html · survivors_fx_tb.html(기준 커밋)에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, subprocess, time, hashlib, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
FULL = '--full' in sys.argv
NOMUT = '--no-mutation' in sys.argv
BASE_COMMIT = os.environ.get('FX_BASE_COMMIT', '6513a72')
NEW, OLD, OLDSRC = 'survivors_fx_t.html', 'survivors_fx_tb.html', 'survivors_fx_tb_src.html'
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:900] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
def want(sec): return ONLY is None or sec in ONLY

EXTRA_NEW = r"""
window.__F={PFX,PFXN,PFXCH,PFXPS,PFXALL,FXSYM,fxState,fxNote,fxWeapons,fxMine,fxPassHtml,fxWeapHtml,fxTableHtml,fxPassRow,fxKeyTail,
  pauseGame,drawCards,openLvup,buildHtml,openChest,cardOf,cdxEntries,cdxView,PASS,PT,TRD,SYN,TIERS,WEAP,CHARS,TCAP,MAXLV,UI3,
  cdMul,areaMul,dmgMul,PS,DUR,LK,critChance,critMul,pv,PTV,trn,RES,setCUR(v){CUR=v},get CUR(){return CUR},get CH(){return CH},get S(){return S},
  CDX,cdxAdd,cdxKeys};
"""
# ───────── 측정 훅(게임 클로저 안) — 측정만 한다, 게임은 안 바꾼다. 에뮬레이터: 같은 시드 · 얼어붙은 불멸 허수아비 72+3 · 한 무기만 든 플레이어 ─────────
HOOK_JS = r""";window.__fxm=(()=>{
const POOLS={shots,rangs,bolts,waves,puds,clouds,cans,rkts,pets,hooks,frs,holes,snps,allies};
const mkr=seed=>{let s=seed>>>0;return()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};};
let ra=mkr(1),rb=mkr(2),inH=0;
Math.random=()=>inH?rb():ra();      // 게임용 난수 흐름(A)과 hurt() 안(치명타 굴림·보스 대사)의 흐름(B)을 나눈다 — 치명타 확률이 달라도 게임 진행 난수는 안 밀린다
let LOG=null;const r4=v=>typeof v==='number'&&isFinite(v)?Math.round(v*10000)/10000:v;
const _hurt=hurt,_bang=bang;
hurt=function(e,d){if(!LOG)return _hurt(e,d);const src=SRC;inH++;try{_hurt(e,d);}finally{inH--;}LOG.h.push([LOG.step,src,r4(d),e.fxi===undefined?-1:e.fxi]);};
bang=function(x,y,R,d,src,style,ev,bm){if(LOG)LOG.b.push([LOG.step,src,r4(R),r4(d),style,ev?1:0,bm||0]);return _bang(x,y,R,d,src,style,ev,bm);};
const NEWQ=[];let QON=false;for(const nm in POOLS)POOLS[nm].__nm=nm;
const _pget=Pool.prototype.get;Pool.prototype.get=function(){const o=_pget.call(this);if(o&&QON&&this.__nm)NEWQ.push([this.__nm,o]);return o;};
const _f3=f3;f3=function(o){const r=_f3(o);if(r&&QON)NEWQ.push(['x3:'+o.k,o]);return r;};
const DROP=new Set(['x','y','vx','vy','x1','y1','x2','y2','sx','sy','nx','ny','lx','ly','ux','uy','a','ax','ay','rot','ph','id','sn','tsn','osn','fa','c','h','rt','hit','vid','tg','e','src','own','last','on']);
const snap=o=>{const f={};for(const k of Object.keys(o)){if(DROP.has(k))continue;const v=o[k];if(typeof v==='number'){if(isFinite(v))f[k]=r4(v);}else if(typeof v==='boolean')f[k]=v?1:0;}
  if(typeof o.vx==='number'&&typeof o.vy==='number')f.sp=r4(Math.hypot(o.vx,o.vy));return f;};
return {run(cfg){
  const x=window.__p6x,dt=cfg.dt||1/30,N=cfg.N||210,k=cfg.w;
  ra=mkr((cfg.seed||1)*2654435761);rb=mkr((cfg.seed||1)*40503+99991);
  for(const pool of Pool.all)for(let i=0;i<pool.a.length;i++){const o=pool.mk();o.on=false;pool.a[i]=o;}
  x.CH_set(cfg.ch||'brj');x.newRun();x.state='play';
  const S_=x.S,P=S_.p;S_.t=120;
  S_.w={};S_.w[k]=cfg.L||8;S_.ev={};if(cfg.ev)S_.ev[k]=1;S_.tier={};if(cfg.tier)S_.tier[k]=cfg.tier;S_.cd={};S_.cd[k]=0;
  S_.ps=Object.assign({},cfg.ps||{});S_.pt={};S_.tr={};S_.rel={};S_.sm={};S_.ramen=0;
  x.tkCalc();x.synCalc();
  S_.nextBoss=S_.nextMini=S_.nextSp=S_.evT=S_.bigT=1e12;S_.propT=S_.chickT=1e12;S_.spawnT=-1e12;S_.need=1e12;S_.xp=0;
  if(cfg.drg){S_.dT=1e9;S_.dS=1.5;}
  for(const e of x.enemies.a)e.on=false;x.props.clear();
  const DUM=[];let fxi=0;
  const mkd=(kind,hx,hy,cls)=>{const e=x.spawnEnemy(kind,1,null,{x:hx,y:hy});if(!e)return null;e.x=e.hx=hx;e.y=e.hy=hy;e.sp=0;e.kb=0;e.hp=e.mhp=1e12+fxi;e.fxi=fxi++;e.fxc=cls;
    if(cls==='e'){e.el=1;e.r*=1.5;}else if(cls==='g'){e.bg=1;e.r*=2.2;}DUM.push(e);return e;};
  if(cfg.arena==='rays'){for(let a=0;a<6;a++)for(let i=0;i<24;i++){const th=a*Math.PI/3;mkd(0,Math.cos(th)*(40+i*24),Math.sin(th)*(40+i*24),'n');}}   // 여섯 줄 × 24마리 — 연쇄가 줄을 따라 길게 이어질 수 있게
  else if(cfg.arena==='hop'){for(let i=0;i<5;i++)mkd(0,60+i*160,0,'n');}   // 160px 간격 한 줄 — 연쇄(키보드 난타)가 이어질 수 있느냐는 건너뛰는 반경에 달렸다
  else{
  const RAD=[42,64,88,114,142,172,205,240,280,325,375,430];let c=0;
  for(let a=0;a<6;a++)for(const R of RAD){const th=a*Math.PI/3;mkd(c++%3,Math.cos(th)*R,Math.sin(th)*R,'n');}
  mkd(0,Math.cos(Math.PI/6)*200,Math.sin(Math.PI/6)*200,'e');mkd(1,Math.cos(Math.PI*7/6)*330,Math.sin(Math.PI*7/6)*330,'g');
  const B=Object.assign({key:'sr'},x.BOSS.sr,{atk:[],hit:null,dead:null});
  const b=x.spawnEnemy(0,1,B);b.x=b.hx=Math.cos(Math.PI*11/6)*260;b.y=b.hy=Math.sin(Math.PI*11/6)*260;b.sp=0;b.kb=0;b.hp=b.mhp=5e7;b.fxi=fxi++;b.fxc='b';DUM.push(b);}
  LOG={step:0,h:[],b:[]};const BIR=[],LIVE=[],SEEN=new WeakSet();
  const arrs=[['mines',S_.mines],['booms',S_.booms]];const CM={};let srad=null,cds=0;
  const cnt=()=>{const c={sushi:S_.sushi.length,mines:S_.mines.length,lid:S_.x2?S_.x2.ln|0:0};for(const nm in POOLS){let n=0;for(const o of POOLS[nm].a)if(o.on)n++;c[nm]=n;}
    for(const o of S_.x3.f)c['x3:'+o.k]=(c['x3:'+o.k]||0)+1;for(const k in c)if(!(CM[k]>=c[k]))CM[k]=c[k];};
  for(let step=1;step<=N;step++){
    P.hp=P.mhp=1e9;P.inv=1e9;S_.spawnT=-1e12;S_.need=1e12;S_.xp=0;S_.propT=S_.chickT=1e12;
    for(const e of DUM){e.on=true;e.x=e.hx;e.y=e.hy;e.hp=e.mhp;e.sp=0;}
    LOG.step=step;
    if(cfg.probe&&step===cfg.probe){P.inv=0;x.hitP(1,'probe');P.inv=1e9;}   // 냄비뚜껑: 한 대 맞아 「깨졌다 돌아오는」 시간을 재게 한다
    QON=true;x.update(dt);QON=false;
    for(let i=0;i<NEWQ.length;i++){if(BIR.length<900){const f=snap(NEWQ[i][1]);f.spm=f.sp||0;BIR.push([NEWQ[i][0],step,f]);LIVE.push([NEWQ[i][1],BIR.length-1,step+30]);}}
    NEWQ.length=0;
    for(const [nm,arr] of arrs)for(const o of arr)if(!SEEN.has(o)){SEEN.add(o);if(BIR.length<900){BIR.push([nm,step,snap(o)]);}}   // 쌓아 두는 배열(지뢰·폭발)의 새 항목도 「태어남」으로 센다
    cds+=S_.cd[k]||0;if(step%10===0)cnt();if(step===3&&S_.sushi.length)srad=r4(S_.sushi.reduce((a,u)=>a+Math.hypot(u.x-P.x,u.y-P.y),0)/S_.sushi.length);
    for(let i=LIVE.length-1;i>=0;i--){const l=LIVE[i],o=l[0];if(step>l[2]){LIVE.splice(i,1);continue;}if(typeof o.vx==='number'){const s=Math.hypot(o.vx,o.vy);if(s>BIR[l[1]][2].spm)BIR[l[1]][2].spm=r4(s);}}}   // 태어난 뒤 1초 동안의 최고 속도(폭죽처럼 가속하는 탄도 속사 배율이 그대로 보이게)
  const out={h:LOG.h,b:LOG.b,bir:BIR,cmax:CM,srad,cdmean:r4(cds/N)};LOG=null;return out;}};
})();
"""

# ───────── 정적 기대 ─────────
BAD_WORDS = ['모든 쿨타임', '모든 범위', '투사체', '짝 패시브', '각성 짝', '카트 2대', '사료 사거리']
CHAN = ['cd', 'cnt', 'spd', 'dur', 'area', 'luck']
NONWEAPON = {'spd', 'hp', 'mag', 'arm', 'study', 'vamp', 'turtle', 'rev'}   # 무기를 직접 강하게 하지 않는 패시브(각성 열쇠로만 쓰인다)

# 표류 방지 — 어느 칸을 재나(w, 채널, 폼). 기본은 p 칸 전부 + 아래 대표 y/n 칸.
REP_Y = [('feed', 'cd', 'b'), ('egg', 'cnt', 'b'), ('kbd', 'cnt', 'b'), ('shrimp', 'cnt', 'e'), ('can', 'spd', 'b'), ('rkt', 'spd', 'b'), ('tempo', 'spd', 'e'),
         ('potion', 'dur', 'b'), ('hole', 'dur', 'b'), ('ping', 'dur', 'e'), ('pan', 'area', 'b'), ('egg', 'area', 'b'), ('gacha', 'luck', 'b'), ('feed', 'spd', 'b'),
         ('bash', 'cd', 'e'), ('spk', 'area', 'e'), ('quill', 'spd', 'e')]
REP_N = [('feed', 'spd', 'e'), ('feed', 'area', 'b'), ('feed', 'dur', 'b'), ('shrimp', 'cd', 'e'), ('shrimp', 'spd', 'e'), ('cart', 'dur', 'e'), ('tempo', 'cnt', 'b'),
         ('jhin', 'cnt', 'b'), ('snack', 'cnt', 'b'), ('slime', 'cnt', 'b'), ('heart', 'cnt', 'b'), ('whop', 'cnt', 'b'), ('quill', 'area', 'b'), ('tempo', 'area', 'b'),
         ('potion', 'luck', 'b'), ('whop', 'luck', 'b'), ('pcards', 'luck', 'e'), ('snack', 'spd', 'b'), ('chick', 'spd', 'b'), ('sushi', 'spd', 'b'), ('fryer', 'dur', 'b'),
         ('chick', 'area', 'b'), ('snipe', 'area', 'b'), ('gacha', 'cnt', 'b'), ('kbd', 'spd', 'b')]
# 칸마다 특별한 장면이 필요한 경우(칸 설명에 적힌 조건): 용 변신 · 마스터 단계 · 한 대 맞기
OVERRIDE = {('kbd', 'cnt', 'e'): dict(arena='rays'), ('kbd', 'cnt', 'b'): dict(arena='rays'),
            ('kbd', 'area', 'b'): dict(arena='hop'), ('kbd', 'area', 'e'): dict(arena='hop'), 
            ('twin', 'spd', 'b'): dict(ch='psg', drg=1), ('twin', 'spd', 'e'): dict(ch='psg', drg=1), ('chick', 'area', 'e'): dict(tier=4), ('snipe', 'area', 'e'): dict(tier=5),
            ('heart', 'area', 'e'): dict(tier=5), ('pcards', 'area', 'e'): dict(tier=5), ('fryer', 'cd', 'e'): dict(tier=4), ('lid', 'cd', 'b'): dict(probe=10), ('lid', 'cd', 'e'): dict(probe=10)}
STACK = {'cd': 'cd', 'cnt': 'amt', 'spd': 'pspd', 'dur': 'dur', 'area': 'area', 'luck': 'luck'}
STACKN = {'cd': 3, 'cnt': 3, 'spd': 3, 'dur': 3, 'area': 3, 'luck': 40}
THR = {'cd': 1.05, 'cnt': 1.15, 'spd': 1.15, 'dur': 1.20, 'area': 1.05}   # 3겹 기대값: 1.28 · +3 · 1.36 · 1.45 · 1.30 — 넉넉히 아래
GEOM = ('ex', 'R', 'bR', 'len', 'hw', 'rng', 'r')

def nsteps(w, ch):
    return 420 if (w == 'gacha' and ch == 'luck') or ch in ('cd', 'dur') else 210   # 쿨타임·지속시간은 몇 번 쏘았나로 재니 14초 · 가챠는 캡슐이 느리고 냄비뚜껑은 깨졌다 돌아오는 데 8~10초 걸린다
def digest(run):
    return hashlib.md5(json.dumps([run['h'], run['b'], [[b[0], b[1], b[2]] for b in run['bir']], run['cmax'], run['srad']], sort_keys=True).encode()).hexdigest()   # 치명타 결과를 담은 dmgBy 는 뺀다 — 행운이 치명타 확률을 올려도 「게임 진행」은 그대로여야 한다
def med(a): return statistics.median(a) if a else None
def metrics(off, on, ch):
    """채널별로 「패시브를 켜면 얼마나 세지나」 — 켠 쪽 / 끈 쪽 배율 (잴 수 없으면 None)"""
    nh = (len(on['h']) / len(off['h'])) if off['h'] else None
    if ch == 'cd':
        r = [x for x in (nh, (off['cdmean'] / on['cdmean']) if on.get('cdmean') and off.get('cdmean') else None) if x is not None]   # 다시 재우는 시간(S.cd)의 평균이 얼마나 짧아졌나 — 프레임에 걸려 쏘는 횟수가 안 변해도 쿨타임 자체가 줄었는지 본다
        return max(r) if r else None
    def kinds(run, fld):
        d = {}
        for kind, st, f in run['bir']:
            v = f.get(fld)
            if isinstance(v, (int, float)) and v > 0: d.setdefault(kind, []).append(v)
        return d
    if ch == 'cnt':
        a = sum(1 for _ in off['bir']); b = sum(1 for _ in on['bir'])
        r = [x for x in (b / a if a else None, nh) if x is not None]
        r += [on['cmax'][k] / off['cmax'][k] for k in off['cmax'] if off['cmax'][k] and k in on['cmax']]   # 동시에 떠 있는 개수(초밥 고리·달걀·궤도 새우깡 …)
        return max(r) if r else None
    if ch in ('spd', 'dur'):
        fld = 'spm' if ch == 'spd' else 'life'
        A, B = kinds(off, fld), kinds(on, fld)
        rs = [med(B[k]) / med(A[k]) for k in A if k in B and med(A[k])]
        return max(rs) if rs else None
    if ch == 'area':
        rs = []
        for fld in GEOM:
            A, B = kinds(off, fld), kinds(on, fld)
            rs += [med(B[k]) / med(A[k]) for k in A if k in B and med(A[k])]
        sA, sB = {}, {}
        for b in off['b']: sA.setdefault(b[1], []).append(b[2])
        for b in on['b']: sB.setdefault(b[1], []).append(b[2])
        rs += [med(sB[k]) / med(sA[k]) for k in sA if k in sB and med(sA[k])]
        if nh is not None: rs.append(nh)
        if off.get('srad') and on.get('srad'): rs.append(on['srad'] / off['srad'])   # 초밥 고리 반지름            # 순간 공격(프라이팬 휘두름·달걀 폭발)은 범위가 넓어지면 맞는 적이 늘어난다
        return max(rs) if rs else None
    return None

def judge(state, ch, off, on):
    """한 칸의 표 글자(y/p/n)가 측정과 맞나 → (통과, 설명)"""
    same = digest(off) == digest(on)
    m = metrics(off, on, ch)
    if state == 'n': return same, 'n 인데 판이 달라졌다(%s)' % (m,)
    if state == 'p': return (not same), 'p 인데 판이 전혀 안 달라졌다(아무것도 안 읽는다 = n)'
    if state == 'y':
        if ch == 'luck': return (not same), 'y 인데 판이 안 달라졌다'
        return (m is not None and m >= THR[ch]), 'y 인데 세짐이 %s (기준 ≥ %s)' % (None if m is None else round(m, 3), THR[ch])
    return False, '알 수 없는 글자 ' + str(state)

def cell_list(fx):
    cells = []
    for w, row in fx.items():
        for ch in CHAN:
            for fi, form in enumerate('be'):
                cells.append((w, ch, form, row[ch][fi]))
    return cells
def pick_cells(fx):
    allc = cell_list(fx)
    if FULL: return [c for c in allc]
    sel = {(w, ch, f) for (w, ch, f, s) in allc if s == 'p'} | set(REP_Y) | set(REP_N)
    return [c for c in allc if (c[0], c[1], c[2]) in sel]

async def measure(pg, cells):
    """cells → {(w,ch,form): (off_run, on_run)}  (같은 무기·폼의 끈 쪽은 한 번만 돌리고, 결정론 확인을 위해 한 번 더 돌려 견준다)"""
    base = {}; res = {}; det = []
    async def run(w, form, ch, extra):
        cfg = dict(w=w, L=8, tier=(0 if form == 'e' else 3), ev=(form == 'e'), N=nsteps(w, ch), seed=1, ps={})
        cfg.update(extra)
        return await pg.evaluate('(c)=>window.__fxm.run(c)', cfg)
    for (w, ch, form, st) in cells:
        ov = OVERRIDE.get((w, ch, form), {})
        bk = (w, form, json.dumps(ov, sort_keys=True), nsteps(w, ch))
        if bk not in base:
            base[bk] = await run(w, form, ch, ov)
            if len(det) < 6:                       # 결정론 자체 시험: 같은 설정을 두 번 돌리면 비트까지 같아야 한다
                again = await run(w, form, ch, ov); det.append((w, form, digest(base[bk]) == digest(again)))
        on = await run(w, form, ch, dict(ov, ps={STACK[ch]: STACKN[ch]}))
        res[(w, ch, form)] = (base[bk], on)
    return res, det

def verdicts(fx, res):
    bad = []
    for (w, ch, form), (off, on) in res.items():
        st = fx[w][ch][0 if form == 'b' else 1]
        ok, why = judge(st, ch, off, on)
        if not ok: bad.append((w, ch, form, st, why))
    return bad

def contrast(c1, c2):
    def lum(c):
        r = []
        for v in c:
            v /= 255; r.append(v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4)
        return .2126 * r[0] + .7152 * r[1] + .0722 * r[2]
    a, b = lum(c1), lum(c2)
    if a < b: a, b = b, a
    return (a + .05) / (b + .05)

async def main():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA_NEW + HOOK_JS)
    # 기준 커밋(비교용)
    old_src = subprocess.run(['git', 'show', BASE_COMMIT + ':survivors.html'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout
    open(os.path.join(ROOT, OLDSRC), 'w', encoding='utf-8').write(old_src)
    H.make_copy(src=OLDSRC, dst=OLD, extra='window.__X={RES,pauseGame,get S(){return S},get state(){return state}};')
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=800, page=NEW)   # 재는 판은 가로 화면에서 — 화면 안에 있는 적만 겨누는 무기(키보드 난타 …)가 허수아비를 다 보게
            F = await pg.evaluate("""()=>{const F=window.__F;return {PFX:F.PFX,PFXN:F.PFXN,PFXCH:F.PFXCH,PFXPS:F.PFXPS,PFXALL:F.PFXALL,wk:Object.keys(F.WEAP),
                pass:Object.keys(F.PASS),pair:Object.fromEntries(Object.entries(F.WEAP).map(([k,v])=>[k,v.pair])),
                wnm:Object.fromEntries(Object.entries(F.WEAP).map(([k,v])=>[k,[v.ic,v.nm,v.ev&&v.ev.ic,v.ev&&v.ev.nm]])),chars:F.CHARS.map(c=>[c.k,c.w,c.nm])}}""")
            PFX, PFXN, PFXCH = F['PFX'], F['PFXN'], F['PFXCH']
            WK = F['wk']

            # ───── 가 정적 ─────
            if want('가'):
                print('── 가 정적 ──')
                check('PFX 의 무기 = WEAP 의 무기(40개 · 같은 순서)', list(PFX.keys()) == WK and len(WK) == 40, (set(PFX) ^ set(WK)))
                okv = all(set(r.keys()) == set(CHAN) and all(re.fullmatch('[ypn]{2}', r[c]) for c in CHAN) for r in PFX.values())
                check('칸마다 여섯 채널(cd cnt spd dur area luck) · 두 글자(기본·각성) · y/p/n 만', okv)
                miss, extra = [], []
                for w, r in PFX.items():
                    for c in CHAN:
                        n = PFXN.get(w + '.' + c)
                        for fi in (0, 1):
                            t = (n if isinstance(n, str) else (n[fi] if n else '')) if n else ''
                            if r[c][fi] == 'p' and not t: miss.append((w, c, fi))
                            if r[c][fi] != 'p' and t: extra.append((w, c, fi))
                check('p 칸마다 설명이 있다', not miss, miss)
                check('p 가 아닌 칸에는 설명이 없다(남는 설명 0)', not extra, extra)
                check('설명 키는 모두 실제 「무기.채널」', all(k.split('.')[0] in PFX and k.split('.')[1] in CHAN for k in PFXN), [k for k in PFXN if k.split('.')[0] not in PFX])
                notes = []
                for n in PFXN.values(): notes += [n] if isinstance(n, str) else [x for x in n if x]
                check('p 설명은 짧다(30자 이하) · 한글/기호만 · 영어 약어 없음', all(len(t) <= 30 and not re.search('[A-Za-z]{3,}', t) for t in notes), [t for t in notes if len(t) > 30])
                check('행운 채널은 가챠 캡슐만 받는다(y/p) — 나머지 39개는 nn', all((PFX[w]['luck'] == 'nn') == (w != 'gacha') for w in PFX) and PFX['gacha']['luck'] == 'yp', PFX['gacha']['luck'])
                check('채널 표 PFXCH 여섯 줄 · 패시브 연결이 실제 패시브', [c['k'] for c in PFXCH] == CHAN and all(c['ps'] in F['pass'] for c in PFXCH), PFXCH)
                check('근성·광분·급소는 전 무기(PFXALL) · 채널 패시브와 겹치지 않는다', set(F['PFXALL']) == {'might', 'glass', 'crit'} and not (set(F['PFXALL']) & set(F['PFXPS'])))
                ps_all = set(F['PFXPS']) | set(F['PFXALL']) | NONWEAPON
                check('모든 패시브가 「채널 · 전 무기 · 무기 강화 아님」 셋 중 하나로 분류된다', ps_all == set(F['pass']), set(F['pass']) ^ ps_all)
                bad = await pg.evaluate("""(B)=>{const F=window.__F,out=[];const txt=[];
                  for(const k in F.PASS)txt.push(['PASS.'+k,F.PASS[k].ds]);for(const k in F.TRD)txt.push(['TRD.'+k,F.TRD[k].ds]);
                  for(const y of F.SYN)txt.push(['SYN.'+y.k,y.ds,y.nm]);for(const k in F.PT)F.PT[k].forEach((s,i)=>txt.push(['PT.'+k+i,s]));
                  for(const k in F.TIERS)F.TIERS[k].forEach((s,i)=>txt.push(['TIERS.'+k+i,s[0]]));
                  for(const k in F.WEAP){const d=F.WEAP[k];txt.push(['WEAP.'+k,d.ev.ds,d.rl||'']);d.ds.forEach((s,i)=>txt.push(['WEAP.'+k+'.'+i,s]));}
                  for(const c of F.CHARS)txt.push(['CHARS.'+c.k,c.ds]);
                  for(const [id,...ss] of txt)for(const s of ss)for(const w of B)if(String(s).includes(w))out.push([id,w]);return out;}""", BAD_WORDS)
                check('금지 문구 0건 — 「모든 쿨타임·범위」「투사체」「짝 패시브」「각성 짝」「카트 2대」「사료 사거리」', not bad, bad[:8])
                tails = await pg.evaluate("""()=>{const F=window.__F;return Object.keys(F.WEAP).map(k=>[k,F.WEAP[k].rl,F.WEAP[k].ev.ds])}""")
                d = {t[0]: t for t in tails}
                check('틀린 설명문 바로잡기: 병아리 「단일 · 아군」 · 운석 「보스 킬러 · 광역」 · 기내식 카트 3대 · 사료 폭풍 속사 안 받음 · 새우깡 대회전 쿨타임 없음',
                      d['chick'][1] == '단일 · 아군' and d['meteor'][1] == '보스 킬러 · 광역' and '카트 3대' in d['cart'][2] and '속사 효과 없음' in d['feed'][2] and '쿨타임이 없어서' in d['shrimp'][2], [d['chick'][1], d['meteor'][1]])
                nm = await pg.evaluate("""()=>{const F=window.__F;return F.SYN.find(y=>y.k==='u_quill').nm+'|'+F.PASS.cd.ds+'|'+F.PASS.pspd.ds+'|'+F.PASS.amt.ds}""")
                check('시너지 이름이 곱빼기 패시브와 안 겹친다(엄 모이 한 상)', nm.split('|')[0] == '엄 모이 한 상', nm)
                helps = await pg.evaluate("[...document.querySelectorAll('#title li')].map(x=>x.textContent).join('\\n')")
                check('도움말: 고유 무기 캐릭터 18명 중 누락 없음(유미 🍘 · 엄장신 📢 · 배고배고 📸 추가) · 각성 열쇠 안내', all(s in helps for s in ['유미 🍘', '엄장신 📢', '배고배고 📸', '🗝 각성 열쇠']) and '짝 패시브' not in helps, helps.count('짝 패시브'))

            # ───── 나 숫자 묶기 ─────
            if want('나'):
                print('── 나 숫자 묶기(설명문의 숫자 = 게임이 쓰는 값) ──')
                r = await pg.evaluate("""()=>{const x=window.__p6x,F=window.__F;x.CH_set('brj');x.newRun();const S=x.S;S.state='play';const o={};
                  const set=(ps,pt,tr,syn)=>{S.ps=Object.assign({},ps||{});S.pt=Object.assign({},pt||{});S.tr=Object.assign({},tr||{});S.syn={dmg:0,cd:0,area:0,xp:0,luck:0};if(syn)Object.assign(S.syn,syn);S.p.moving=false;};
                  set();o.cd0=F.cdMul();o.ar0=F.areaMul();o.ps0=F.PS();o.du0=F.DUR();o.cc0=F.critChance();o.cm0=F.critMul();
                  set({cd:1});o.cd1=F.cdMul();set({area:1});o.ar1=F.areaMul();set({pspd:1});o.ps1=F.PS();set({dur:1});o.du1=F.DUR();set({crit:1});o.cc_c=F.critChance();o.cm_c=F.critMul();
                  set({crit:5});o.cm_c5=F.critMul();set({luck:1});o.cc_l=F.critChance();set({might:1});o.dm1=F.dmgMul();set({glass:1});o.dm_g=F.dmgMul();
                  set({},{cd:1});o.cd_pt=F.cdMul();set({},{cd:2});o.cd_pt2=F.cdMul();set({},{area:1});o.ar_pt=F.areaMul();set({},{pspd:1});o.ps_pt=F.PS();
                  set({spd:5},{spd:2});S.p.moving=true;o.cd_mv=F.cdMul();S.p.moving=false;set({},{},{wide:1});o.cd_wide=F.cdMul();o.ar_wide=F.areaMul();set({},{},{gale:1});o.ar_gale=F.areaMul();
                  set({},{},{swift:1});o.cd_sw=F.cdMul();o.dm_sw=F.dmgMul();set();o.tx={cd:F.PASS.cd.ds,amt:F.PASS.amt.ds,pspd:F.PASS.pspd.ds,dur:F.PASS.dur.ds,area:F.PASS.area.ds,luck:F.PASS.luck.ds,crit:F.PASS.crit.ds,might:F.PASS.might.ds,glass:F.PASS.glass.ds,
                    ptcd:F.PT.cd,ptarea:F.PT.area,ptpspd:F.PT.pspd,ptspd:F.PT.spd,wide:F.TRD.wide.ds,gale:F.TRD.gale.ds,swift:F.TRD.swift.ds,bbb:F.CHARS.find(c=>c.k==='bbb').ds,bbbcdr:F.CHARS.find(c=>c.k==='bbb').cdr,
                    bell:F.TIERS.bell[4][0],syn:F.SYN.map(y=>[y.k,y.ds,y.fx])};
                  o.glassMax=F.PASS.glass.max;return o;}""")
                tx = r['tx']; rd = lambda v: round(v, 4)
                check('속사 「+12%」= PS() 계수 (Lv1 → ×1.12) · 초월 「+8% 더」= PS() +0.08', '+12%' in tx['pspd'] and rd(r['ps1'] - r['ps0']) == .12 and '+8% 더' in tx['ptpspd'][0] and rd(r['ps_pt'] - r['ps0']) == .08, (r['ps1'], r['ps_pt']))
                check('공격속도 「-8%」= cdMul() ×0.92 · 초월 「-4% 더」 = ×0.96 (2단계도 ×0.96) · 박자 감각 「-8%」', '-8%' in tx['cd'] and rd(r['cd1']) == .92 and all('-4% 더' in s for s in tx['ptcd']) and rd(r['cd_pt']) == .96 and rd(r['cd_pt2']) == rd(.96 ** 2) and '-8%' in tx['bbb'] and tx['bbbcdr'] == .08, (r['cd1'], r['cd_pt'], r['cd_pt2']))
                check('이동속도 초월 2단계 「이동 중 쿨타임 -4%」= 실제 ×0.96 (옛 문구 -6% 는 틀렸다)', '-4%' in tx['ptspd'][1] and '-6%' not in tx['ptspd'][1] and rd(r['cd_mv']) == .96, r['cd_mv'])
                check('광역 「+10%」= areaMul() +0.1 · 초월 「+6% 더」= +0.06', '+10%' in tx['area'] and rd(r['ar1'] - r['ar0']) == .1 and '+6% 더' in tx['ptarea'][0] and rd(r['ar_pt'] - r['ar0']) == .06, (r['ar1'], r['ar_pt']))
                check('끈기 「+15%」= DUR() ×1.15', '+15%' in tx['dur'] and rd(r['du1'] / r['du0']) == 1.15, r['du1'])
                check('급소 「+5% · +0.2배」= critChance +0.05 · critMul +0.2 (Lv5 3배) · 행운 「+3%」= critChance +0.03', '+5%' in tx['crit'] and '+0.2배' in tx['crit'] and rd(r['cc_c'] - r['cc0']) == .05 and rd(r['cm_c'] - r['cm0']) == .2 and rd(r['cm_c5']) == 3 and '+3%' in tx['luck'] and rd(r['cc_l'] - r['cc0']) == .03, (r['cc_c'], r['cm_c'], r['cm_c5'], r['cc_l']))
                check('근성 「+10%」= dmgMul ×1.1 · 광분 「+15%」= ×1.15', '+10%' in tx['might'] and rd(r['dm1']) == 1.1 and '+15%' in tx['glass'] and rd(r['dm_g']) == 1.15, (r['dm1'], r['dm_g']))
                check('광역 확장 「범위 +10% · 쿨타임 5% 느려짐」= 실제 areaMul +0.1 · cdMul ×1.05 · 질풍 「-5%」· 속전속결 「-7% · 피해 -4%」', '+10%' in tx['wide'] and '5% 느려짐' in tx['wide'] and rd(r['ar_wide'] - r['ar0']) == .1 and rd(r['cd_wide']) == 1.05 and '-5%' in tx['gale'] and rd(r['ar_gale'] - r['ar0']) == -.05 and '-7%' in tx['swift'] and '-4%' in tx['swift'] and rd(r['cd_sw']) == .93 and rd(r['dm_sw']) == .96, r)
                bad = []
                for k, ds, fx in tx['syn']:
                    if fx.get('cd') and ('쿨타임 -%d%%' % round(fx['cd'] * 100)) not in ds: bad.append((k, ds, fx))
                    if fx.get('area') and ('범위 +%d%%' % round(fx['area'] * 100)) not in ds: bad.append((k, ds, fx))
                    if (fx.get('cd') or fx.get('area')) and '모든 쿨타임' in ds + '모든 범위': bad.append((k, ds))
                check('시너지 설명의 쿨타임·범위 숫자 = fx 값 (전 %d개)' % len(tx['syn']), not bad, bad[:4])
                check('리듬 게임 5단계 「강화 중 쿨타임 -8%」는 「모든」이 아니라 공격속도와 같은 규칙', '-8%' in tx['bell'] and '모든' not in tx['bell'], tx['bell'])
                # 기내식 카트 각성은 정말 3대 — 코드가 만드는 최대 수(nmax) 를 직접 센다
                cart = await pg.evaluate("""()=>{const x=window.__p6x;const out={};for(const ev of [0,1]){const o=window.__fxm.run({w:'cart',L:8,ev:!!ev,tier:ev?0:3,N:420,seed:1,ps:{}});let m=0;const by={};for(const b of o.bir)if(b[0]==='x3:c'){by[b[1]]=(by[b[1]]||0)+1;}
                  out[ev]=Object.values(by).reduce((a,b)=>a+b,0);}return out;}""")
                check('기내식 카트: 각성 폼이 깐 카트 수(14초) > 기본 폼 · 각성 3대 (nmax = 1 + (Lv≥7) + 각성)', cart['1'] >= 3, cart)

            # ───── 다 화면 ─────
            if want('다'):
                print('── 다 화면(18캐릭터 × 대표 빌드 · 폰 폭) ──')
                lay = []
                for (w, h) in [(320, 568), (360, 740), (412, 915)]:
                    ctx2, pg2, errs2 = await H.new_page(b, srv.port, w=w, h=h, page=NEW, mobile=True)
                    R = await pg2.evaluate("""()=>{
                      const x=window.__p6x,F=window.__F,out={chars:[],bad:[],over:[],names:new Set()};
                      const known=new Set();for(const k in F.WEAP){const d=F.WEAP[k];known.add(d.ic+' '+d.nm);}
                      const chNames=new Set(F.PFXCH.map(c=>c.ic+c.nm));
                      const scan=(root,tag)=>{for(const el of root.querySelectorAll('.fxi')){const t=el.textContent.replace(/✨$/,'').trim();if(!known.has(t)&&!chNames.has(t)&&!/[✔◐✖]/.test(t)&&!/→/.test(t))out.bad.push([tag,t]);}
                        const txt=root.textContent;for(const s of ['undefined','NaN','[object','null'])if(txt.includes(s))out.bad.push([tag,s]);};
                      const wide=tag=>{const d=document.documentElement;if(d.scrollWidth>d.clientWidth+1)out.over.push([tag,d.scrollWidth,d.clientWidth]);
                        for(const el of document.querySelectorAll('#lvup .box *,#pause .box *,#chest .box *')){const r=el.getBoundingClientRect();if(r.width&&r.right>innerWidth+1&&getComputedStyle(el).position!=='fixed'){out.over.push([tag,el.className||el.tagName,Math.round(r.right)]);break;}}};
                      const BUILDS=[['feed','amt','pspd'],['fryer','cd','area'],['shrimp','dur','spd'],['gacha','luck','area'],['twin','dur','cd']];
                      let i=0;
                      for(const c of F.CHARS){x.CH_set(c.k);x.newRun();x.state='play';const S=x.S;const bd=BUILDS[i++%BUILDS.length];
                        S.w={};if(c.w)S.w[c.w]=2;S.w[bd[0]]=3;S.w.egg=2;S.w.can=1;S.ps={};S.ps[bd[1]]=2;S.ps[bd[2]]=1;S.ps.hp=1;S.ps.might=1;S.ps.luck=1;
                        if(i%3===0){const k=Object.keys(S.w)[0];S.ev[k]=1;}
                        try{F.openLvup();}catch(e){out.bad.push([c.k,'openLvup '+e]);}
                        const lv=document.getElementById('choices');scan(lv,c.k+'/lvup');wide(c.k+'/lvup');
                        // 모든 패시브·무기 카드를 한 번씩 그려 본다
                        const cards=[];for(const k in F.PASS)cards.push(x.cardOf({t:'p',k,l:S.ps[k]||0}));for(const k in F.WEAP)cards.push(x.cardOf({t:'w',k,l:S.w[k]||0}));
                        const tmp=document.createElement('div');tmp.innerHTML=cards.map(c=>c.ds).join('');scan(tmp,c.k+'/cards');
                        F.pauseGame();const pb=document.getElementById('pInfo');scan(pb,c.k+'/pause');wide(c.k+'/pause');
                        {const rb=document.getElementById('resumeBtn').getBoundingClientRect(),qb=document.getElementById('quitBtn').getBoundingClientRect();   // 계속하기는 늘 화면 안(끈끈이) · 난이도 줄은 맨 위 그대로
                          if(rb.height<40||rb.bottom>innerHeight+1||rb.top<0)out.bad.push([c.k,'계속하기 버튼이 화면 밖/작다',Math.round(rb.top),Math.round(rb.bottom),Math.round(rb.height)]);
                          const df=document.getElementById('pDiff').getBoundingClientRect();if(df.top<0||df.top>innerHeight/2)out.bad.push([c.k,'난이도 줄이 밀렸다',Math.round(df.top)]);}
                        const det=document.getElementById('fxTab');if(!det)out.bad.push([c.k,'#fxTab 없음']);
                        else{if(det.open)out.bad.push([c.k,'접이식이 기본으로 열려 있다']);det.open=true;wide(c.k+'/pause-open');
                          const rows=det.querySelectorAll('tbody tr').length;if(rows!==Object.keys(S.w).length)out.bad.push([c.k,'표 행 수',rows,Object.keys(S.w).length]);
                          const sm=det.querySelector('summary').getBoundingClientRect();if(sm.height<40)out.bad.push([c.k,'요약줄 높이',sm.height]);det.open=false;F.UI3.xOpen=false;}
                        x.resume();
                        out.chars.push(c.k);}
                      return {chars:out.chars.length,bad:out.bad.slice(0,12),over:out.over.slice(0,8)};}""")
                    lay.append((w, R, errs2))
                    await ctx2.close()
                for (w, R, e2) in lay:
                    check('[%d px] 18캐릭터 × 레벨업·카드 전부·일시정지 — 이름 전부 실제 이름 · 이상한 글자 0 · 표 행 수 · 접이식 기본 접힘 · 요약줄 ≥ 40px' % w, R['chars'] == len(F['chars']) and not R['bad'], R['bad'])
                    check('[%d px] 가로 넘침 0' % w, not R['over'], R['over'])
                    check('[%d px] 페이지 오류·콘솔 오류 0' % w, not e2, e2[:3])
                # 레벨업 카드 3장(광역·공격속도 패시브 + 사료 투척 Lv3, 무기 6·패시브 8)이 작은 폰 한 화면에 들어오고, ✔/✖ 는 「받는 강화」에만 쓴다
                for (w, h) in [(320, 568), (360, 640)]:
                    ctx3, pg3, e3 = await H.new_page(b, srv.port, w=w, h=h, page=NEW, mobile=True)
                    R3 = await pg3.evaluate("""()=>{const x=window.__p6x,F=window.__F;x.CH_set('brj');x.newRun();x.state='play';const S=x.S;
                      S.w={feed:3,shrimp:2,pan:2,sushi:2,egg:2,can:1};S.ps={area:1,cd:1,amt:1,pspd:1,dur:1,hp:1,might:1,luck:1};
                      const o=[{t:'p',k:'area',l:1},{t:'p',k:'cd',l:1},{t:'w',k:'feed',l:3}];
                      F.state='lvup';const box=document.getElementById('choices');
                      box.innerHTML=o.map(q=>{const c=x.cardOf(q);return '<button class="ch"><span class="ic">'+c.ic+'</span><span><small class="ty">'+c.ty+'</small><b>'+c.nm+'</b><small>'+c.ds+'</small></span><span class="lv">'+c.lv+'</span></button>';}).join('');
                      document.getElementById('lvup').classList.remove('hidden');document.getElementById('lvup').style.display='flex';
                      const bs=[...box.querySelectorAll('button')].map(b=>Math.round(b.getBoundingClientRect().height));
                      const key=x.cardOf({t:'w',k:'feed',l:3}).ds.replace(/<[^>]+>/g,'');
                      return {bs,tot:bs.reduce((a,b)=>a+b,0),key};}""")
                    keyline = [t for t in R3['key'].split('🔧')[0].split('🗝')[1:]]
                    check('[%d x %d] 레벨업 카드 3장 높이 합이 화면 높이 이내' % (w, h), R3['tot'] <= h - 40, R3)
                    check('[%d] 각성 열쇠 줄은 ✔/✖ 대신 (보유)/(아직 없음)' % w, keyline and not re.search('[✔✖]', keyline[0].split('🔧')[0]) and '(보유)' in R3['key'] or '(아직 없음)' in R3['key'], R3['key'])
                    await ctx3.close()
                # 문구 규칙 몇 개를 구체 빌드로
                r = await pg.evaluate("""()=>{const x=window.__p6x,F=window.__F;x.CH_set('brj');x.newRun();x.state='play';const S=x.S;const o={};
                  S.w={feed:5,shrimp:3,pan:2,sushi:8};S.ps={pspd:2,amt:1,area:1,hp:1,luck:1};
                  o.pspd=x.cardOf({t:'p',k:'pspd',l:2}).ds;o.hp=x.cardOf({t:'p',k:'hp',l:1}).ds;o.might=x.cardOf({t:'p',k:'might',l:0}).ds;o.luck=x.cardOf({t:'p',k:'luck',l:1}).ds;
                  S.w={pan:2,fryer:3};S.ps={pspd:1};o.warn=x.cardOf({t:'p',k:'pspd',l:1}).ds;
                  S.w={feed:5};o.feedc=x.cardOf({t:'w',k:'feed',l:5}).ds;S.ev.feed=1;o.feedev=x.cardOf({t:'w',k:'feed',l:5}).ds;delete S.ev.feed;
                  o.shrimp=x.cardOf({t:'w',k:'shrimp',l:0}).ds;o.sushi=x.cardOf({t:'w',k:'sushi',l:0}).ds;o.rkt=x.cardOf({t:'w',k:'rkt',l:0}).ds;
                  S.w={feed:8};S.ps={amt:1};x.openChest&&0;return o;}""")
                strip = lambda s: re.sub('<[^>]+>', '', s)
                check('속사 카드: 한 줄 개수 요약 「✔ 내 무기 1개 · ◐ 일부만 1개 · ✖ 영향 없음 2개」 (이름 목록은 일시정지 표로)', '✔ 내 무기 1개 · ◐ 일부만 1개 · ✖ 영향 없음 2개' in strip(r['pspd']) and '새우깡' not in strip(r['pspd']), strip(r['pspd']))
                check('받는 무기가 하나도 없으면 눈에 띄는 경고 「⚠ 지금 가진 무기엔 효과가 없어요」', '⚠ 지금 가진 무기엔 효과가 없어요' in strip(r['warn']) and 'fxl w' in r['warn'], strip(r['warn']))
                check('무기를 강하게 하지 않는 패시브(최대 HP)는 그렇다고 적는다 · 근성은 「모든 무기에 적용돼요」', '무기를 직접 강하게 하지는 않아요' in strip(r['hp']) and '모든 무기에 적용돼요' in strip(r['might']), (strip(r['hp']), strip(r['might'])))
                check('행운 카드: 「모든 무기: 치명타 확률 +3%」 + 가챠 캡슐이 없으면 등급 확률은 해당 없다고 적는다', '모든 무기: 치명타 확률 +3%' in strip(r['luck']) and '가챠 캡슐만' in strip(r['luck']), strip(r['luck']))
                check('무기 카드(사료 투척): 「받는 강화」 한 줄 + 각성하면 속사 ✔→✖ 를 미리 알려 준다', '받는 강화' in strip(r['feedc']) and '각성하면: ' in strip(r['feedc']) and '속사 ✔→✖' in strip(r['feedc']), strip(r['feedc']))
                check('각성한 사료 폭풍 카드는 지금 폼(속사 ✖)을 따르고 「각성하면」 줄은 없다', '✖ ' in strip(r['feedev']) and '각성하면: ' not in strip(r['feedev']) and re.search('✖[^✔◐]*🏹속사', strip(r['feedev'])), strip(r['feedev']))
                check('새우깡 카드: 열쇠(이동속도)는 강화가 아니라고 적는다 · 각성하면 ⏱·🏹 ✔→✖', '열쇠일 뿐 이 무기를 강하게 하진 않아요' in strip(r['shrimp']) and '⏱공격속도 ✔→✖' in strip(r['shrimp']), strip(r['shrimp']))
                check('폭죽 카드: 열쇠(속사)가 실제로 강화하니 꼬리말 없음 · 초밥 카드: 열쇠(공격속도)가 일부만 도움 → 안내', '열쇠일 뿐' not in strip(r['rkt']) and '일부만 도움돼요' in strip(r['sushi']), (strip(r['rkt'])[-200:], strip(r['sushi'])[-200:]))
                # 일시정지 표 — 구체 빌드
                r = await pg.evaluate("""()=>{const x=window.__p6x,F=window.__F;x.CH_set('brj');x.newRun();x.state='play';const S=x.S;
                  S.w={shrimp:3,pan:2,feed:5,lid:4};S.ps={pspd:2,dur:1,cd:1};F.pauseGame();const h=document.getElementById('pInfo').innerHTML;const det=document.getElementById('fxTab');
                  const t=det.textContent;const rows=[...det.querySelectorAll('tbody tr')].map(r=>[...r.children].map(c=>c.textContent.trim()));x.resume();return {open:det.open,rows,t,h,passrows:[...document.querySelectorAll('#pInfo .bw')].map(e=>e.textContent)};}""")
                check('일시정지: 「🧩 내 무기 × 패시브」 기본 접힘 · 행 = 내 무기 4개 · 열 = 가진 영향 패시브 3개(⏱ 🏹 ⏳)', not r['open'] and len(r['rows']) == 4 and all(len(x) == 4 for x in r['rows']), r['rows'])
                check('표 칸: 사료 투척 = ✔(공격속도) ✔(속사) ✖(끈기) · 새우깡 = ✔ ◐ ✖ · 프라이팬 = ✔ ✖ ✖', ['✔', '✔', '✖'] == r['rows'][2][1:] and ['✔', '◐', '✖'] == r['rows'][0][1:] and ['✔', '✖', '✖'] == r['rows'][1][1:], r['rows'])
                check('◐ 설명 목록(새우깡 — 속사: 던질 때만 · 냄비뚜껑 — 공격속도: 복구 시간만 줄어요)', '던질 때만' in r['t'] and '복구 시간만' in r['t'], r['t'][-300:])
                check('패시브 줄: 효과 한 줄 + 「내 무기 N개 적용」/「⚠ 지금 무기엔 효과 없음」', any('내 무기 3개 적용' in p for p in r['passrows']) or any('내 무기 2개 적용' in p for p in r['passrows']), r['passrows'])
                check('일시정지 무기 줄이 「각성 열쇠」로 바뀌었다(「각성:」 옛 문구 0)', '🗝 각성 열쇠: Lv' in r['h'] and '<small>각성: Lv' not in r['h'], '')
                # 글자 대비 4.5
                cc = await pg.evaluate("""()=>{const cs=getComputedStyle(document.documentElement);const mk=(cls,bg)=>{const d=document.createElement('div');d.className=cls;d.style.cssText='position:fixed;left:-999px';d.textContent='x';document.body.appendChild(d);const c=getComputedStyle(d).color;d.remove();return c;};
                  return {y:mk('fxl y'),p:mk('fxl p'),n:mk('fxl n'),w:mk('fxl w'),bg:getComputedStyle(document.body).getPropertyValue('--card2')||'#1e2442'}}""")
                def rgb(s):
                    m = re.findall(r'\d+', s)[:3]; return tuple(int(v) for v in m)
                bg = (0x1e, 0x24, 0x42)
                cs = {k: contrast(rgb(cc[k]), bg) for k in 'ypnw'}
                check('글자 대비 4.5 이상(카드 바탕 #1e2442 위 ✔ 초록 · ◐ 노랑 · ✖ 회색 · ⚠ 분홍)', all(v >= 4.5 for v in cs.values()), cs)

                # 도감
                print('  ·· 도감')
                ctx3, pg3, errs3 = await H.new_page(b, srv.port, w=360, h=740, page=NEW, mobile=True)
                r = await pg3.evaluate("""()=>{const F=window.__F,C=window.__cdx;const o={};
                  const ents=F.cdxEntries();const w=ents.find(e=>e.key==='w:feed'),p=ents.find(e=>e.key==='p:pspd'),pa=ents.find(e=>e.key==='p:might'),ph=ents.find(e=>e.key==='p:hp');
                  o.w=w.fx.map(x=>[x.key,x.b,x.e]);o.p=p.fx.ws.length;o.pall=pa.fx;o.pnone=ph.fx;
                  // 아무것도 발견 못 한 상태 → 잠긴 칸만, 누출 0
                  const v0=F.cdxView();o.locked=v0.every(e=>e.locked);o.leak=JSON.stringify(v0).includes('속사')||JSON.stringify(v0).includes('fx');
                  return o;}""")
                check('도감 데이터: 사료 투척의 받는 강화 5줄(행운은 가챠만이라 빠진다) · 속사 패시브의 받는 무기 목록 · 근성=전 무기 · 최대 HP=무기 강화 아님', len(r['w']) == 5 and r['p'] >= 8 and r['pall'] == {'all': 1} and r['pnone'] == {'none': 1}, r)
                check('도감: 하나도 발견 못 했으면 모든 칸이 잠겨 있고 받는 강화 정보가 새지 않는다', r['locked'] and not r['leak'], r)
                # 발견 규칙: 사료 투척·속사만 발견 → 속사 상세는 사료 투척 이름 + 나머지는 ❓ ×N
                r = await pg3.evaluate("""async ()=>{const F=window.__F;const out={};
                  F.cdxAdd(['w:feed','p:pspd','p:cd','w:shrimp']);
                  const v=F.cdxView();const p=v.find(e=>e.key==='p:pspd'),w=v.find(e=>e.key==='w:feed'),w2=v.find(e=>e.key==='w:shrimp');
                  out.pseen=p.fx.seen.map(x=>x.key).sort();out.pEvHidden=p.fx.seen.every(x=>x.e===null&&x.ne==='');out.phid=p.fx.hid;
                  out.wnames=w.fx.filter(x=>!x.hid).map(x=>x.nm).sort();out.whid=w.fx.filter(x=>x.hid).length;out.whidLeak=w.fx.filter(x=>x.hid).some(x=>x.nm||x.ic||x.key);
                  out.w2e=w2.fx.every(x=>x.e===null);return out;}""")
                check('도감 발견 규칙: 속사 상세 = 발견한 무기(사료 투척·새우깡)만 이름으로 · 나머지는 ❓ 개수만 · 각성 형태를 못 본 무기는 각성 뒤 모습을 안 준다',
                      r['pseen'] == ['w:feed', 'w:shrimp'] and r['phid'] >= 6 and r['pEvHidden'] and r['w2e'], r)
                check('도감 발견 규칙: 사료 투척 상세 = 발견한 패시브(공격속도·속사) 이름만 · 나머지 ❓ 는 이름·아이콘·키가 없다', r['wnames'] == ['공격속도', '속사'] and r['whid'] == 3 and not r['whidLeak'], r)
                # 화면: 상세 열기
                await pg3.click('#cxOpen'); await pg3.wait_for_function("document.getElementById('cxOv').classList.contains('on')")
                await pg3.click('#cxTab_p')
                idx = await pg3.evaluate("[...document.querySelectorAll('#cxPanel .cxt')].map((e,i)=>[i,e.classList.contains('lock'),e.textContent.trim()])")
                pi = [i for i, lock, t in idx if not lock and '속사' in t]
                await pg3.locator('#cxPanel .cxt').nth(pi[0]).click()
                d = await pg3.evaluate("document.getElementById('cxD').textContent")
                check('도감 화면(패시브 속사): 「받는 무기」에 사료 투척 ✔ · 새우깡(던질 때만) ◐ · ❓ ×N · 각성 열쇠 안내', '받는 무기' in d and '✔ 🌾 사료 투척' in d and '◐ 🍤 새우깡 부메랑' in d and '던질 때만' in d and '❓ ×' in d and '각성 열쇠로 쓰이는 무기' in d, d[:400])
                await pg3.click('#cxTab_w')
                idx = await pg3.evaluate("[...document.querySelectorAll('#cxPanel .cxt')].map((e,i)=>[i,e.classList.contains('lock'),e.textContent.trim()])")
                wi = [i for i, lock, t in idx if not lock and '사료' in t]
                await pg3.locator('#cxPanel .cxt').nth(wi[0]).click()
                d = await pg3.evaluate("document.getElementById('cxD').textContent")
                check('도감 화면(무기 사료 투척): 「받는 강화」 칩 — 발견한 공격속도 이름 + 못 만난 패시브는 ❓ · 곱빼기 이름은 안 샌다', '받는 강화' in d and '⏱ 공격속도' in d and '❓ 못 만난 패시브' in d and '곱빼기' not in d and '각성 열쇠 패시브' in d, d[:500])
                ow = await pg3.evaluate("document.documentElement.scrollWidth<=document.documentElement.clientWidth+1")
                check('도감 상세 가로 넘침 0(360px)', ow)
                check('도감 페이지 오류 0', not errs3, errs3[:3])
                await ctx3.close()

            # ───── 라 표류 방지 ─────
            res = None
            if want('라') or want('마'):
                print('── 라 표류 방지(실제 게임으로 표를 증명 — %s) ──' % ('전 칸' if FULL else '대표 칸'))
                cells = pick_cells(PFX)
                t0 = time.time()
                res, det = await measure(pg, cells)
                ncell = len(res)
                print('  (측정 %d칸 · %.0f초)' % (ncell, time.time() - t0), flush=True)
                check('측정 장치 결정론: 같은 설정 두 번 = 판 전체가 비트까지 같다(%d회)' % len(det), all(d[2] for d in det), det)
                bad = verdicts(PFX, res)
                cnt = {s: sum(1 for (w, ch, f, s2) in cells if s2 == s) for s in 'ypn'}
                check('표 = 게임: 잰 %d칸(y %d · p %d · n %d) 전부 표의 글자와 맞다' % (ncell, cnt['y'], cnt['p'], cnt['n']), not bad, bad[:10])
                if bad:
                    for x in bad[:20]: print('    표류:', x)
                allp = sum(1 for (w, ch, f, s) in cell_list(PFX) if s == 'p')
                check('기본 실행이 p 칸을 빠짐없이 쟀다(p %d칸 전부)' % allp, FULL or cnt['p'] == allp, (cnt['p'], allp))

            # ───── 마 변이 ─────
            if want('마') and not NOMUT and res is not None:
                print('── 마 변이(표의 한 칸을 일부러 틀리게 → 시험이 빨개져야 한다) ──')
                import copy
                muts = [('feed', 'spd', 1, 'y'), ('shrimp', 'cd', 1, 'p'), ('potion', 'luck', 0, 'p'), ('can', 'spd', 0, 'n'), ('ram', 'area', 0, 'n'), ('twin', 'dur', 1, 'y'), ('lid', 'cd', 0, 'n'), ('tempo', 'cnt', 0, 'y')]
                caught = 0; notes = []
                for (w, ch, fi, to) in muts:
                    key = (w, ch, 'be'[fi])
                    if key not in res:
                        # 측정 대상에 없던 칸이면 그 칸만 따로 잰다
                        r1, _ = await measure(pg, [(w, ch, 'be'[fi], PFX[w][ch][fi])]); res.update(r1)
                    fx2 = copy.deepcopy(PFX); s = list(fx2[w][ch]); orig = s[fi]; s[fi] = to; fx2[w][ch] = ''.join(s)
                    bad = verdicts(fx2, {key: res[key]})
                    if orig == to: continue
                    caught += 1 if bad else 0
                    notes.append((w, ch, 'be'[fi], orig + '→' + to, '빨강' if bad else '안 잡힘'))
                check('변이 시험: 틀리게 바꾼 %d칸 중 %d칸을 시험이 잡았다 (n↔y·p↔n 은 반드시, p→y 만 못 잡는 약점 허용)' % (len(muts), caught), caught >= len(muts) - 1, notes)
                for n in notes: print('    ', n)

            # ───── 바 불변 ─────
            if want('바'):
                print('── 바 불변 ──')
                ctxb, pgb, errsb = await H.new_page(b, srv.port, w=412, h=860, page=OLD, ready='__X')
                sig_old = await pgb.evaluate("window.__X.RES.SIG||''")
                sig_new = await pg.evaluate("window.__F.RES.SIG||''")
                check('이어하기 서명(RES.SIG) 기준 커밋과 같다 — 새 표가 서명에 안 들어갔다', sig_old and sig_old == sig_new, (sig_old, sig_new))
                keys_old = await pgb.evaluate("(()=>{window.__p6x.CH_set&&0;return null})()") if False else None
                ko = await pgb.evaluate("""()=>{const x=window.__p6x;x.CH_set('brj');x.newRun();return Object.keys(x.S).sort().join(',')}""")
                kn = await pg.evaluate("""()=>{const x=window.__p6x;x.CH_set('brj');x.newRun();return Object.keys(x.S).sort().join(',')}""")
                check('새 S 키 0 (newRun 직후 S 의 키 집합이 기준 커밋과 같다)', ko == kn, set(ko.split(',')) ^ set(kn.split(',')))
                src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
                tops_new = set(re.findall(r'^(?:let|var) (\w+)', src, re.M)); tops_old = set(re.findall(r'^(?:let|var) (\w+)', old_src, re.M))
                check('새 최상위 let/var 0', tops_new == tops_old, tops_new ^ tops_old)
                # 이어하기 호환: 기준 커밋의 판이 저장한 본을 새 판이 그대로 복구한다(같은 브라우저 저장소를 쓰는 두 페이지)
                await pgb.evaluate("""()=>{const x=window.__p6x;x.CH_set('brj');x.start();const S=x.S;S.w={feed:5,shrimp:3,sushi:8,pan:2};S.ps={pspd:2,amt:1,area:1,hp:1};S.t=420;S.kills=137;S.lv=11;
                  window.__X.pauseGame();}""")
                old_key = await pgb.evaluate("window.__X.RES.KEY")
                raw = await pgb.evaluate("(k)=>localStorage.getItem(k)", old_key)
                check('기준 커밋이 일시정지로 저장한 판이 있다(저장본 %s자)' % (len(raw) if raw else 0), bool(raw) and len(raw) > 500, old_key)
                pgn = await ctxb.new_page(); await pgn.goto('http://127.0.0.1:%d/%s' % (srv.port, NEW)); await pgn.wait_for_function('window.__p6x!==undefined&&window.__F!==undefined', timeout=15000)
                hd = await pgn.evaluate("()=>{const p=window.__F.RES.peek();return p?{st:p.st,t:p.t,lv:p.lv,k:p.k,sig:p.sig}:null}")
                check('새 판이 그 저장본의 머리를 읽는다(서명 같음 · 일시정지 · 시각·레벨·처치 같음)', hd and hd['st'] == 'pause' and hd['lv'] == 11 and hd['k'] == 137 and hd['t'] == 420, hd)
                rr = await pgn.evaluate("""(k)=>{const F=window.__F,x=window.__p6x;const txt=localStorage.getItem(k);const ok=F.RES.restore(txt);const S=x.S;
                  return {ok,w:S&&S.w,ps:S&&S.ps,kills:S&&S.kills,fx:!!document.getElementById('fxTab'),pause:document.getElementById('pInfo').innerHTML.includes('내 무기 × 패시브')};}""", old_key)
                check('새 판이 복구한다 — 무기·패시브·처치가 같고, 일시정지 화면에 새 「🧩 내 무기 × 패시브」 표가 그려진다', rr['ok'] and rr['w'] == {'feed': 5, 'shrimp': 3, 'sushi': 8, 'pan': 2} and rr['ps'] == {'pspd': 2, 'amt': 1, 'area': 1, 'hp': 1} and rr['kills'] == 137 and rr['fx'] and rr['pause'], rr)
                await pgn.close()
                check('페이지 오류 0(주 페이지)', not errs, errs[:3])
                await ctxb.close()
            await b.close()
    finally:
        srv.close()
        for f in (NEW, OLD, OLDSRC):
            try: os.remove(os.path.join(ROOT, f))
            except Exception: pass
    print('\n검사 %d개 · 실패 %d' % (CHECKS[0], len(FAILS)))
    for f in FAILS: print('  ✗', f)
    sys.exit(1 if FAILS else 0)

CHECKS = [0]
_check = check
def check(n, c, x=''):
    CHECKS[0] += 1
    _check(n, c, x)

asyncio.run(main())
