# -*- coding: utf-8 -*-
"""🌍 흐접새우 서바이벌 「이어하기: 세계가 통째로 같이 돌아온다」 시험 (2026-10-11 클랜원 제보)
   제보: 「몹이 많은 상태에서 웹 화면을 고의로 종료하고 재접속하면 몹이 싹 사라지고, 바닥에 있는 경험치는 남아서 안전하게 경험치를 얻을 수 있다」
   원칙: 이어한 판은 닫기 직전과 같은 위험(적·엘리트·보스·적 탄·함정)·같은 보상(바닥 보석·아이템)이어야 한다.
         크기·용량·복구 실패로 완전히 못 되살리는 경우에도 「적은 비우고 보석만 남김」 은 없다 — 적과 보석은 같이 돌아오거나 같이 버려진다.
   사용: python3 tests/survivors_resume_world_test.py [--only 가,나,..] [--mutants]
     가  몹 많은 판 복구 전/후 동일 — 데스크톱(적 220칸)·폰(적 140칸) × 캐릭터 × (일시정지 · pagehide · 실제 탭 닫기), 풀을 가득 채운 최악 판 · 저장 크기·시간
     나  세계 장부(census) — 적만 지워진 저장본·보석만 지워진 저장본·아이템만 지워진 저장본은 판 전체가 버려진다(풀이 하나도 안 남는다)
     다  풀 값 검증(유한하지 않은 좌표·터무니없는 보석 값·모르는 아이템) · 저장 한도 초과 · 저장 실패 시 옛 저장본이 남아 되감기가 되지 않는다
     라  옛 저장본(장부 없음) 복구 호환 + 복구 직후 일관성 가드 · 서명(SIG) 불변
     마  두 창: 낡은 창에서 그만두기·홈 버튼이 기록을 올리거나 새 창의 저장본을 지우지 못한다
     바  여러 번 닫았다 열기(저장 → 복구 → 저장 → 복구 …)에도 세계가 같다
   --mutants: 고친 줄을 하나씩 되돌린 사본에서 해당 구간이 빨강이 되는지 본다(시험이 진짜로 잡는지 확인).
   임시 사본 survivors_rw.html / survivors_rwm_*.html (.gitignore 대상 · 끝나면 지운다)."""
import asyncio, sys, os, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright

DST = 'survivors_rw.html'
KEY = 'p6_resume_v1'
BASE_SIG = '1:1164773586:951'          # 이 변경 이전(2bb6eaf)의 저장 서명 — 표 노드를 건드리면 달라진다(옛 저장본 폐기)
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
MUTANTS = '--mutants' in sys.argv
FAILS = []
CURRENT = {'tag': ''}

def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + CURRENT['tag'] + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(CURRENT['tag'] + n)
def want(sec): return ONLY is None or sec in ONLY

HOOK = r"""
window.__W={RES,get S(){return S},set S(v){S=v},get state(){return state},set state(v){state=v},get CUR(){return CUR},get RUN(){return RUN},
 pools:{enemies,shots,gems,items,props,texts,hazards,eshots,rangs,rkts,pets,hooks,frs,holes,snps,bolts,waves,puds,clouds,allies,cans,bubs},
 CHARS,KIND,BOSS,PICK,SRVUNL,getProg,setProg,start,update,resume,pauseGame,pick,openLvup,openChest,endRun,spawnEnemy,spawnBoss,
 CH_set(k){CH=CHARS.find(c=>c.k===k)},get CH(){return CH},get LOW(){return LOW},get MAXE(){return MAXE},synCalc,tkCalc,seedOf,get keys(){return keys},set keys(v){keys=v}};
const COS=new Set(['texts','bubs','bolts','snps']);
window.__forge=(sp)=>{const x=__W;try{localStorage.removeItem('p6_resume_v1')}catch(e){}
 x.CH_set(sp.ch);x.SRVUNL.add(sp.ch);const g=x.getProg();g.bk[sp.ch]=1;x.setProg(g);
 x.start();const S=x.S;if(sp.w)S.w=Object.assign({},sp.w);S.lv=sp.lv||10;S.need=1e9;
 const t0=sp.t0||1500;S.t=t0;S.evT=t0+5;S.bigT=t0+8;S.bossN=Math.floor(t0/300);S.nextBoss=t0>=3300?Infinity:(S.bossN+1)*300;
 S.miniN=Math.floor((t0-150)/300)+1;S.nextMini=150+300*S.miniN;if(S.nextMini>3200)S.nextMini=Infinity;S.nextSp=t0>2280?2280+3600:2280;
 x.synCalc();x.tkCalc();S.p.mhp=S.p.hp=1e8;return x.state;};
window.__adv=(sec)=>{const x=__W;const n=Math.round(sec*30);for(let i=0;i<n;i++){const st=x.state;if(st==='result')return 'result';
  if(st==='lvup'){x.pick(x.CUR[0]);continue;}if(st!=='play'){x.resume();continue;}
  const S=x.S;S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];x.update(1/30);}return x.state;};
// 판을 꽉 채운다 — 엘리트·보스·보석 200·아이템 30·적 탄 가득·함정 가득(최악의 세계)
window.__stuff=(opt)=>{const x=__W,P=x.pools,S=x.S,p=S.p,rnd=(a,b)=>a+Math.random()*(b-a);
 let n=0;
 for(let i=0;i<P.enemies.a.length&&n<500;i++){const e=x.spawnEnemy(Math.floor(Math.random()*Math.min(6,x.KIND.length)),1+S.t/600);if(!e)break;n++;if(Math.random()<.12){e.el=1;e.mhp=e.hp=e.hp*6;e.r*=1.5;e.xp*=5;}}
 if(opt&&opt.boss){const ks=Object.keys(x.BOSS).filter(k=>x.BOSS[k].hp);for(let i=0;i<2&&i<ks.length;i++)x.spawnBoss(ks[i]);}
 for(let i=0;i<P.gems.a.length;i++){const g=P.gems.get();if(!g)break;g.x=p.x+rnd(-700,700);g.y=p.y+rnd(-700,700);g.v=1+Math.floor(Math.random()*40);g.mag=Math.random()<.1?1:0;}
 const ik=Object.keys(x.PICK).filter(k=>k!=='chest');for(let i=0;i<P.items.a.length;i++){const o=P.items.get();if(!o)break;o.x=p.x+rnd(-500,500);o.y=p.y+rnd(-500,500);o.k=ik[i%ik.length];o.life=60;o.t=0;}
 for(let i=0;i<P.eshots.a.length;i++){const o=P.eshots.get();if(!o)break;o.x=p.x+rnd(-600,600);o.y=p.y+rnd(-600,600);o.vx=rnd(-80,80);o.vy=rnd(-80,80);o.life=5;o.d=8;}
 for(let i=0;i<P.hazards.a.length;i++){const o=P.hazards.get();if(!o)break;o.x=p.x+rnd(-600,600);o.y=p.y+rnd(-600,600);o.life=60;}
 for(let i=0;i<P.shots.a.length;i++){const o=P.shots.get();if(!o)break;o.x=p.x+rnd(-300,300);o.y=p.y+rnd(-300,300);o.vx=rnd(-200,200);o.vy=rnd(-200,200);o.life=3;o.dmg=5;}
 for(let i=0;i<P.clouds.a.length;i++){const o=P.clouds.get();if(!o)break;o.x=p.x+rnd(-500,500);o.y=p.y+rnd(-500,500);o.life=20;}
 for(let i=0;i<P.props.a.length;i++){const o=P.props.get();if(!o)break;o.x=p.x+rnd(-900,900);o.y=p.y+rnd(-900,900);o.k=0;o.hp=3;}
 return true;};
// 닫기 직전 세계의 전부(적·보석·아이템·적 탄·함정 …) — 풀 칸 번호까지 그대로. 풀 칸끼리의 참조는 {$p:[풀,번호]} 로 적는다.
window.__world=()=>{const x=__W,P=x.pools,slot=new Map();for(const n in P)P[n].a.forEach((o,i)=>slot.set(o,n+':'+i));
 const w=(v,d)=>{if(v===null)return null;const t=typeof v;if(t==='number')return Number.isFinite(v)?v:String(v);if(t==='string'||t==='boolean')return v;if(t==='undefined')return '$u';if(t==='function')return '$fn';
  if(slot.has(v))return {$p:slot.get(v)};if(d>6)return '$deep';if(Array.isArray(v))return v.map(q=>w(q,d+1));const o={};for(const k of Object.keys(v).sort())o[k]=w(v[k],d+1);return o;};
 const out={};for(const n in P){if(COS.has(n))continue;out[n]=[];P[n].a.forEach((o,i)=>{if(o.on){const e={};for(const k of Object.keys(o).sort())e[k]=w(o[k],0);out[n].push([i,e]);}});}
 const E=P.enemies.a.filter(e=>e.on),G=P.gems.a.filter(g=>g.on);
 return {pools:out,sum:{e:E.length,boss:E.filter(e=>e.boss).length,el:E.filter(e=>e.el).length,g:G.length,gv:G.reduce((a,g)=>a+g.v,0),i:P.items.a.filter(o=>o.on).length,es:P.eshots.a.filter(o=>o.on).length,hz:P.hazards.a.filter(o=>o.on).length,kinds:E.map(e=>e.boss?'B:'+e.boss:'k'+e.ki).sort().join(',')},
   S:{t:x.S.t,lv:x.S.lv,xp:x.S.xp,kills:x.S.kills,hp:x.S.p.hp,px:x.S.p.x,py:x.S.p.y}};};
window.__empty=()=>{const P=__W.pools;let n=0;for(const k in P){if(COS.has(k))continue;for(const o of P[k].a)if(o.on)n++;}return n;};
"""

class Ctx:
    def __init__(self, b, port, w=1280, h=720, hc=8, scr=None, seed=None, mock=None):
        self.b, self.port, self.w, self.h, self.hc, self.scr, self.seed, self.mock = b, port, w, h, hc, scr, seed, mock
        self.errs = []; self.net = []
    async def open(self):
        kw = dict(viewport={'width': self.w, 'height': self.h}, screen={'width': (self.scr or (self.w, self.h))[0], 'height': (self.scr or (self.w, self.h))[1]})
        if self.w < 600: kw.update(is_mobile=True, has_touch=True, device_scale_factor=2)
        self.ctx = await self.b.new_context(**kw)
        async def route(r):
            u = r.request.url
            if u.startswith('http://127.0.0.1:%d/' % self.port): await r.continue_(); return
            if 'bot-hosting.cloud' in u:
                self.net.append((r.request.method, u))
                await r.fulfill(status=200, content_type='application/json', body='{"ok":false,"code":"mock"}', headers={'access-control-allow-origin': '*'}); return
            await r.abort()
        await self.ctx.route('**/*', route)
        await self.ctx.add_init_script("Object.defineProperty(Navigator.prototype,'hardwareConcurrency',{get:()=>%d});" % self.hc)
        await self.ctx.add_init_script("window.requestAnimationFrame=function(){return 0};window.AudioContext=window.webkitAudioContext=undefined;")   # 그리기 루프·소리 끔 — 시험이 update 만 구동한다(세계가 시험 도중 혼자 변하지 않게)
        return self
    async def page(self, url=None):
        pg = await self.ctx.new_page()
        pg.on('pageerror', lambda e: self.errs.append('PAGEERR ' + str(e)))
        pg.on('console', lambda m: self.errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        await pg.goto(url or 'http://127.0.0.1:%d/%s' % (self.port, DST))
        await pg.wait_for_function('window.__W!==undefined', timeout=20000)
        return pg
    async def close(self): await self.ctx.close()

def sp_of(ch, w, t0=1500, lv=10): return dict(ch=ch, w={w: 5}, t0=t0, lv=lv)

async def make_world(pg, ch, t0=1500, stuff=True, boss=True, adv=12):
    w = await pg.evaluate("(k)=>__W.CHARS.find(c=>c.k===k).w", ch)
    await pg.evaluate("(s)=>__forge(s)", sp_of(ch, w, t0))
    await pg.evaluate("(s)=>__adv(s)", adv)
    if stuff: await pg.evaluate("(o)=>__stuff(o)", {'boss': boss})
    return w

async def reopen(C, blob, click=True, wait_state=True):
    """저장본을 새 페이지의 저장소에 넣고 다시 열어(새로 연 페이지 = 모듈 상태 없음) 이어하기를 누른다"""
    B = await C.page()
    if blob is not None: await B.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", blob)
    await B.reload(); await B.wait_for_function('window.__W!==undefined')
    if click:
        await B.click('#resGo')
        if wait_state:
            try: await B.wait_for_function("__W.state!=='title'", timeout=6000)
            except Exception: pass
    return B

def same_world(a, b):
    return json.dumps(a['pools'], sort_keys=True) == json.dumps(b['pools'], sort_keys=True)

def first_diff(a, b):
    for n in a['pools']:
        if json.dumps(a['pools'][n], sort_keys=True) != json.dumps(b['pools'].get(n), sort_keys=True):
            la, lb = a['pools'][n], b['pools'].get(n) or []
            if len(la) != len(lb): return '%s: %d칸 → %d칸' % (n, len(la), len(lb))
            for x, y in zip(la, lb):
                if json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True):
                    return '%s[%s]: %s ≠ %s' % (n, x[0], json.dumps(x[1], sort_keys=True)[:160], json.dumps(y[1], sort_keys=True)[:160])
    return ''

# ───────────── 가. 몹 많은 판 복구 전/후 동일 ─────────────
async def sec_fidelity(b, srv):
    print('\n── 가. 몹 많은 판: 닫기 직전 ↔ 복구 직후(적·엘리트·보스·보석·아이템·적 탄·함정을 칸 번호째) ──', flush=True)
    for label, kw in (('데스크톱 220칸', dict(w=1280, h=720, hc=8)), ('폰 140칸', dict(w=412, h=860, hc=4))):
        C = await Ctx(b, srv.port, **kw).open()
        A = await C.page()
        chs = await A.evaluate("__W.CHARS.map(c=>c.k)")
        cap = await A.evaluate("__W.MAXE")
        check('[%s] 적 풀 크기 %d' % (label, cap), cap == (140 if kw['hc'] == 4 else 220), cap)
        sample = chs if kw['hc'] == 8 else chs[:6]
        worst = None
        for ci, ch in enumerate(sample):
            t0 = [900, 1500, 2400, 3300][ci % 4]
            await make_world(A, ch, t0=t0, stuff=True, boss=(ci % 2 == 0))
            await A.evaluate("()=>{__W.pauseGame()}")
            pre = await A.evaluate("()=>__world()")
            info = await A.evaluate("()=>({...__W.RES.info,rep:null})")
            blob = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
            ok_save = bool(blob) and info['saves'] >= 1
            B = await reopen(C, blob)
            post = await B.evaluate("()=>__world()")
            st = await B.evaluate("()=>__W.state")
            ok = same_world(pre, post) and st == 'pause'
            check('[%s/%s/%ds] 일시정지 저장 → 새 페이지 복구: 적 %d(엘리트 %d·보스 %d)·보석 %d(값 %d)·아이템 %d·적 탄 %d·함정 %d 가 칸 번호째 그대로' % (label, ch, t0, pre['sum']['e'], pre['sum']['el'], pre['sum']['boss'], pre['sum']['g'], pre['sum']['gv'], pre['sum']['i'], pre['sum']['es'], pre['sum']['hz']),
                  ok_save and ok and pre['sum']['e'] > 0 and pre['sum']['g'] > 0, dict(save=ok_save, st=st, diff=first_diff(pre, post), why=info['why']))
            if worst is None or len(blob or '') > worst[0]: worst = (len(blob or ''), ch)
            await B.close()
            await A.evaluate("()=>localStorage.removeItem('p6_resume_v1')")
        # 풀 가득 채운 최악 판 — 크기·시간
        await make_world(A, chs[0], t0=3000, stuff=True, boss=True)
        full = await A.evaluate("()=>{const P=__W.pools;const r={};for(const n of ['enemies','gems','items','eshots','hazards','shots','clouds','props'])r[n]=[P[n].a.filter(o=>o.on).length,P[n].a.length];return r}")
        ms = []
        for i in range(5):
            r = await A.evaluate("()=>{const t=performance.now();const b=__W.RES.build();return [performance.now()-t,b.text?b.text.length:-1,b.why||'']}")
            ms.append(r)
        mx = max(m[0] for m in ms); ln = ms[0][1]
        print('   · 최악 판(%s): 칸 %s → 저장 %d자 · 저장 %.1f~%.1fms' % (label, json.dumps(full), ln, min(m[0] for m in ms), mx), flush=True)
        check('[%s] 최악 판(적·보석·아이템·적 탄·함정·투사체 풀이 가득)도 저장된다 · 크기 ≤ 700000자 · 저장 시간 ≤ 150ms(부하 높은 기계 기준)' % label, ln > 0 and ln <= 700000 and mx <= 150, (ms, full))
        check('[%s] 최악 판이 저장 한도(2,500,000자)에 한참 못 미친다(한도에 걸려 일부만 빠지는 일이 없다)' % label, 0 < ln <= 700000 and ln < 0.3 * 2500000, ln)
        # pagehide(고의 종료) — 판 도중(play)에 이벤트가 오면 일시정지 + 저장 → 복구하면 같은 세계
        await make_world(A, chs[1], t0=1800, stuff=True, boss=True)
        st0 = await A.evaluate("()=>__W.state"); await A.evaluate("()=>localStorage.removeItem('p6_resume_v1')")
        await A.evaluate("()=>{dispatchEvent(new Event('pagehide'))}")
        pre = await A.evaluate("()=>__world()"); blob = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
        B = await reopen(C, blob); post = await B.evaluate("()=>__world()")
        check('[%s] 판 도중(play) pagehide → 일시정지·저장 → 복구하면 닫기 직전과 같은 세계(적 %d · 보석 %d)' % (label, pre['sum']['e'], pre['sum']['g']),
              st0 == 'play' and bool(blob) and same_world(pre, post) and pre['sum']['e'] > 0, dict(st0=st0, diff=first_diff(pre, post)))
        await B.close()
        # visibilitychange(숨김) 도 같다
        await make_world(A, chs[2], t0=2100, stuff=True, boss=False)
        await A.evaluate("()=>localStorage.removeItem('p6_resume_v1')")
        await A.evaluate("()=>{Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));}")
        pre = await A.evaluate("()=>__world()"); blob = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
        B = await reopen(C, blob); post = await B.evaluate("()=>__world()")
        check('[%s] 앱을 숨기면(visibilitychange) 저장 → 복구하면 같은 세계' % label, bool(blob) and same_world(pre, post) and pre['sum']['e'] > 0, first_diff(pre, post))
        await B.close()
        check('[%s] 스크립트 오류 없음' % label, not C.errs, C.errs[:4])
        await C.close()
    # 실제로 탭을 닫기(run_before_unload) — pagehide 가 진짜로 오는 길
    C = await Ctx(b, srv.port, w=1280, h=720, hc=8).open(); A = await C.page()
    chs = await A.evaluate("__W.CHARS.map(c=>c.k)")
    await make_world(A, chs[3], t0=2000, stuff=True, boss=True)
    await A.evaluate("()=>localStorage.removeItem('p6_resume_v1')")
    pre = None
    # 닫기 직전 세계를 잡아 둔다 — 닫는 순간 일시정지로 바뀌는 것 말고 세계는 안 변한다(그리기 루프가 꺼져 있다)
    pre = await A.evaluate("()=>__world()")
    await A.close(run_before_unload=True)
    B = await reopen(C, None); post = await B.evaluate("()=>__world()")
    st = await B.evaluate("()=>__W.state")
    check('실제 탭 닫기(pagehide) → 새 탭에서 이어하기: 닫기 직전의 적 %d · 엘리트 %d · 보스 %d · 보석 %d · 아이템 %d 가 그대로' % (pre['sum']['e'], pre['sum']['el'], pre['sum']['boss'], pre['sum']['g'], pre['sum']['i']),
          st == 'pause' and same_world(pre, post) and pre['sum']['e'] > 0, dict(st=st, diff=first_diff(pre, post)))
    # 계속하기를 누르면 같은 위험이 이어진다 — 적이 갑자기 사라지지 않는다(1초 뒤에도 적이 있다)
    await B.evaluate("()=>__W.resume()")
    sm = await B.evaluate("()=>{const a=__world().sum;__adv(1);const b=__world().sum;return [a.e,b.e,a.g,b.g,__W.state]}")
    check('계속하기 1초 뒤에도 적이 그대로 많다(%s → %s) · 판이 진행 중' % (sm[0], sm[1]), sm[4] == 'play' and sm[1] >= 0.5 * sm[0] and sm[1] > 0, sm)
    await C.close()

# ───────────── 나·다 공용: 저장본을 손으로 고치는 도구 ─────────────
CRAFT = r"""([blob,expr])=>{const R=__W;const i=blob.indexOf('\n');const h=JSON.parse(blob.slice(0,i)),x=JSON.parse(blob.slice(i+1));
 (new Function('x','h',expr))(x,h);const body=JSON.stringify(x);h.len=body.length;h.ck=R.seedOf(body);return JSON.stringify(h)+'\n'+body;}"""

async def fresh_blob(C, ch=None, boss=True, t0=1500):
    A = await C.page()
    chs = await A.evaluate("__W.CHARS.map(c=>c.k)")
    await make_world(A, ch or chs[0], t0=t0, stuff=True, boss=boss)
    await A.evaluate("()=>__W.pauseGame()")
    pre = await A.evaluate("()=>__world()")
    blob = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
    return A, blob, pre

async def try_restore(C, blob, b=None, srv=None):
    # 같은 저장소(LIVEK 에 이미 세대 표가 남아 있으면 같은 저장본은 '낡은 것' 으로 거절된다)를 피하려고 매번 새 브라우저 컨텍스트에서 연다
    if b is not None:
        C = await Ctx(b, srv.port, w=C.w, h=C.h, hc=C.hc).open()
    B = await C.page(); await B.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", blob)
    await B.reload(); await B.wait_for_function('window.__W!==undefined')
    logs = []
    B.on('console', lambda m: logs.append(m.text))
    await B.click('#resGo'); await B.wait_for_timeout(600)
    r = await B.evaluate("()=>({st:__W.state,empty:__empty(),key:localStorage.getItem('p6_resume_v1'),S:!!__W.S,card:!document.getElementById('resCard').hidden,why:__W.RES.info.why,msg:document.getElementById('resMsg').textContent})")
    r['logs'] = [l for l in logs if '이어하기' in l]
    return B, r

# ───────────── 나. 세계 장부 ─────────────
async def sec_census(b, srv):
    print('\n── 나. 세계 장부 — 적만 빠지거나 보석만 남은 저장본은 판 전체가 버려진다 ──', flush=True)
    C = await Ctx(b, srv.port).open()
    A, blob, pre = await fresh_blob(C)
    h = json.loads(blob[:blob.index('\n')]); body = json.loads(blob[blob.index('\n') + 1:])
    check('(기준) 새 저장본 본문에 세계 장부(cn)가 있다 — 적 %s · 보스 %s · 보석 %s(값 %s)' % (body.get('cn', {}).get('enemies'), body.get('cn', {}).get('boss'), body.get('cn', {}).get('gems'), body.get('cn', {}).get('gv')),
          'cn' in body and body['cn']['enemies'] == pre['sum']['e'] and body['cn']['gems'] == pre['sum']['g'] and abs(body['cn']['gv'] - pre['sum']['gv']) < 1e-6, body.get('cn'))
    C1 = await Ctx(b, srv.port).open(); B = await reopen(C1, blob); post = await B.evaluate("()=>__world()")
    check('(기준) 손대지 않은 저장본 복구 = 같은 세계', same_world(pre, post), first_diff(pre, post)); await B.close(); await C1.close()
    cases = {
        '적 풀만 비움(보석 남음 — 제보 증상)': "x.pools.enemies=[]",
        '적 한 마리만 빠짐': "x.pools.enemies.pop()",
        '엘리트만 빠짐': "x.pools.enemies=x.pools.enemies.filter(e=>!e[1].el)",
        '보스만 빠짐': "x.pools.enemies=x.pools.enemies.filter(e=>!e[1].boss)",
        '보석 한 개 빠짐': "x.pools.gems.pop()",
        '보석 값만 바뀜': "x.pools.gems[0][1].v=(x.pools.gems[0][1].v||1)+5",
        '아이템만 빠짐': "x.pools.items=[]",
        '적 탄만 빠짐': "x.pools.eshots=[]",
        '적 체력만 바뀜': "x.pools.enemies[0][1].hp=(x.pools.enemies[0][1].hp||1)*0.5",
    }
    for name, expr in cases.items():
        crafted = await A.evaluate(CRAFT, [blob, expr])
        B2, r = await try_restore(C, crafted, b, srv)
        check('[%s] 복구가 거절되고 풀이 하나도 안 남는다(적만 비고 보석만 남는 판 없음) · 저장본도 버려진다 · 제목 화면' % name,
              r['st'] == 'title' and r['empty'] == 0 and r['key'] is None and not r['S'], r)
        check('[%s] 이유가 로그·안내에 남는다' % name, any('census' in l for l in r['logs']) or 'census' in (r['why'] or ''), r)
        await B2.context.close()
    # 장부만 지우면(옛 형식) 같은 변조는 못 잡지만 복구 직후 가드(라 구간)가 따로 잡는다 — 여기선 '옛 저장본은 그대로 열린다' 만
    check('스크립트 오류 없음(거절은 콘솔 경고뿐)', not [e for e in C.errs if 'PAGEERR' in e], C.errs[:3])
    await C.close()

# ───────────── 다. 풀 값 검증 · 한도 · 저장 실패 ─────────────
async def sec_limits(b, srv):
    print('\n── 다. 풀 값 검증 · 저장 한도 · 저장 실패(옛 저장본이 남아 되감기가 되지 않는다) ──', flush=True)
    C = await Ctx(b, srv.port).open()
    A, blob, pre = await fresh_blob(C, boss=False)
    def nocn(expr): return expr + ";delete x.cn"           # 장부를 지워 장부 검사가 아니라 값 검사가 잡는지 본다
    cases = {
        '보석 값이 터무니없다(1e12)': nocn("x.pools.gems[0][1].v=1e12"),
        '보석 좌표가 NaN': nocn("x.pools.gems[0][1].x={$n:'NaN'}"),
        '보석 값이 0 이하': nocn("x.pools.gems[0][1].v=-5"),
        '적 좌표가 무한대': nocn("x.pools.enemies[0][1].x={$n:'Inf'}"),
        '적 체력이 NaN': nocn("x.pools.enemies[0][1].hp={$n:'NaN'}"),
        '적 반지름이 터무니없다': nocn("x.pools.enemies[0][1].r=99999"),
        '모르는 아이템 종류': nocn("x.pools.items[0][1].k='hacked'"),
        '적 탄 좌표가 NaN': nocn("x.pools.eshots[0][1].x={$n:'NaN'}"),
    }
    for name, expr in cases.items():
        crafted = await A.evaluate(CRAFT, [blob, expr])
        B2, r = await try_restore(C, crafted, b, srv)
        check('[%s] 복구 거절 · 풀 0칸 · 저장본 버림' % name, r['st'] == 'title' and r['empty'] == 0 and r['key'] is None and not r['S'], r)
        await B2.context.close()
    # 저장 한도 초과: 본문이 한도(2,500,000자)를 넘으면 통째로 저장하지 않는다 — 이 지점의 옛 저장본도 남기지 않는다
    A.on('console', lambda m: None)
    await A.evaluate("()=>{__W.resume();__adv(1);}")
    pre_key = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
    check('(기준) 계속하기를 누르면 저장본은 소모된다', pre_key is None, (pre_key or '')[:80])
    await A.evaluate("()=>{__W.pauseGame()}"); k1 = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
    check('(기준) 일시정지에서 다시 저장된다', bool(k1))
    await A.evaluate("()=>{__W.resume();__adv(1);__W.S.junk='x'.repeat(2600000);__W.pauseGame()}")
    r = await A.evaluate("(k)=>({key:localStorage.getItem(k),why:__W.RES.info.why,state:__W.state,hint:!!document.getElementById('resFailHint')})", KEY)
    check('저장 한도를 넘으면 저장하지 않고(why=too-big) 저장본이 하나도 남지 않는다 · 일시정지 화면에 경고 · 게임은 멀쩡', r['key'] is None and r['why'] == 'too-big' and r['state'] == 'pause' and r['hint'], r)
    B2 = await reopen(C, None, click=False)
    card = await B2.evaluate("()=>!document.getElementById('resCard').hidden")
    check('한도 초과 뒤 새 페이지에는 이어하기 카드가 없다(옛 저장본으로 되돌아가지 않는다)', not card); await B2.close()
    # 저장소 쓰기 실패(용량 초과) — 같은 판의 옛 저장본이 남아 되감기가 되지 않는다
    A2 = await C.page(); chs = await A2.evaluate("__W.CHARS.map(c=>c.k)")
    await make_world(A2, chs[4], t0=1800, stuff=True, boss=False)
    await A2.evaluate("()=>__W.pauseGame()"); k1 = await A2.evaluate("(k)=>localStorage.getItem(k)", KEY)
    await A2.evaluate("""()=>{const s=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k)==='p6_resume_v1')throw new DOMException('quota','QuotaExceededError');return s.call(this,k,v);};
      __W.S.xp+=1;__W.RES.save('again');}""")
    k2 = await A2.evaluate("(k)=>localStorage.getItem(k)", KEY); fails = await A2.evaluate("()=>__W.RES.info.fails")
    check('저장소 용량 초과로 두 번째 저장이 실패하면 첫 번째 저장본도 지워진다(되감기 불가) · 실패가 기록된다', bool(k1) and k2 is None and fails >= 1, dict(k1=bool(k1), k2=k2 and k2[:60], fails=fails))
    await C.close()

# ───────────── 라. 옛 저장본 호환 · 복구 직후 가드 · SIG ─────────────
async def sec_compat(b, srv):
    print('\n── 라. 옛 저장본(장부 없음) 호환 · 복구 직후 일관성 가드 · 저장 서명 불변 ──', flush=True)
    C = await Ctx(b, srv.port).open()
    A, blob, pre = await fresh_blob(C)
    sig = await A.evaluate("()=>__W.RES.SIG")
    check('저장 서명(SIG)이 변경 이전과 같다(옛 저장본이 폐기되지 않는다) %s' % sig, sig == BASE_SIG, sig)
    h = json.loads(blob[:blob.index('\n')])
    check('저장본 머리의 서명이 현재 서명과 같다', h['sig'] == sig)
    old = await A.evaluate(CRAFT, [blob, "delete x.cn"])
    C1 = await Ctx(b, srv.port).open(); B = await reopen(C1, old); post = await B.evaluate("()=>__world()"); st = await B.evaluate("()=>__W.state")
    check('옛 형식(장부 없음) 저장본이 그대로 복구된다 · 세계 동일(적 %d · 보석 %d)' % (pre['sum']['e'], pre['sum']['g']), st == 'pause' and same_world(pre, post), dict(st=st, diff=first_diff(pre, post)))
    await B.evaluate("()=>__W.resume()")
    sm = await B.evaluate("()=>{__adv(2);return [__W.state,__world().sum.e]}")
    check('옛 형식 판도 계속하기 → 2초 진행 정상', sm[0] == 'play' and sm[1] > 0, sm)
    await B.close(); await C1.close()
    # 복구 직후 가드: 옛 형식 저장본이라도, 복구한 뒤 계속하기 전에 세계가 어긋나면(적만 지워진 경우) 계속하지 않고 닫는다
    C1 = await Ctx(b, srv.port).open(); B = await reopen(C1, old)
    await B.evaluate("()=>{for(const e of __W.pools.enemies.a)e.on=false;}")      # 일시정지 중에 적만 사라진 판(보석은 남음)
    left = await B.evaluate("()=>__world().sum.g")
    await B.evaluate("()=>__W.resume()")
    r = await B.evaluate("(k)=>({st:__W.state,empty:__empty(),key:localStorage.getItem(k),S:!!__W.S})", KEY)
    check('복구 직후(시간이 안 흐른 일시정지) 적만 사라지고 보석 %d개가 남은 판은 계속하기가 막히고 닫힌다(풀 0칸 · 저장본 없음)' % left, left > 0 and r['st'] == 'title' and r['empty'] == 0 and r['key'] is None and not r['S'], r)
    await B.close(); await C1.close()
    # 정상 복구는 가드에 걸리지 않는다
    C1 = await Ctx(b, srv.port).open(); B = await reopen(C1, blob); await B.evaluate("()=>__W.resume()")
    st = await B.evaluate("()=>__W.state")
    check('(기준) 손대지 않은 복구는 계속하기가 정상 동작한다', st == 'play', st)
    await B.close(); await C1.close()
    # 새 저장본 → 계속하기 → 일시정지 → 다시 저장: 가드는 진행된 판을 건드리지 않는다
    C1 = await Ctx(b, srv.port).open(); B = await reopen(C1, blob); await B.evaluate("()=>{__W.resume();__adv(3);__W.pauseGame();for(let i=0;i<5;i++){const e=__W.pools.enemies.a.find(o=>o.on);if(e)e.on=false;}__W.resume();}")
    st = await B.evaluate("()=>__W.state")
    check('이미 진행한 판(시간이 흐른 뒤)에서 적이 줄어든 것은 정상이다 — 가드가 닫지 않는다', st == 'play', st)
    await B.close(); await C1.close(); await C.close()

# ───────────── 마. 낡은 창 ─────────────
async def sec_stale(b, srv):
    print('\n── 마. 두 창 — 낡은 창은 기록을 올리지도, 새 창의 저장본을 지우지도 못한다 ──', flush=True)
    # (실제로는 새 창이 이어받는 순간 저장소 이벤트로 낡은 창이 곧바로 닫힌다 — 시험은 그 이벤트가 닿기 전의 틈을 만든다: 낡은 창이 스스로 '세대 표'를 올려 낡은 창으로 만든다)
    for which in ('quitBtn', 'homeBtn'):
        C = await Ctx(b, srv.port).open()
        A = await C.page()
        await A.evaluate("()=>localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'t',exp:Date.now()+30*864e5,name:'x'}))")
        chs = await A.evaluate("__W.CHARS.map(c=>c.k)")
        await make_world(A, chs[0], t0=1500, stuff=True, boss=False)
        await A.evaluate("()=>__W.pauseGame()")
        # 새 창이 이어받아 저장해 둔 것처럼: 세대 표 + 같은 판의 새 세대 저장본
        await A.evaluate("""(k)=>{const R=__W.RUN;localStorage.setItem('p6_resume_live',JSON.stringify({rid:R.rid,gen:R.gen+1}));
          const t=localStorage.getItem(k),i=t.indexOf('\\n'),h=JSON.parse(t.slice(0,i));h.gen=R.gen+1;localStorage.setItem(k,JSON.stringify(h)+t.slice(i));}""", KEY)
        keyBefore = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
        C.net.clear()
        await A.evaluate("(id)=>document.getElementById(id).click()", which)
        await A.wait_for_timeout(500)
        stA = await A.evaluate("()=>[__W.state,!!__W.S]")
        keyAfter = await A.evaluate("(k)=>localStorage.getItem(k)", KEY)
        runs = [n for n in C.net if '/p6/run' in n[1]]
        check('[%s] 낡은 창에서 누르면 결과 화면으로 가지 않고 닫힌다(%s)' % (which, stA), stA == ['title', False], stA)
        check('[%s] 낡은 창이 서버에 기록을 올리지 않는다(/p6/run 요청 %d건)' % (which, len(runs)), not runs, C.net)
        check('[%s] 새 창의 저장본이 지워지지 않는다' % which, bool(keyBefore) and keyAfter == keyBefore)
        check('[%s] 스크립트 오류 없음' % which, not [e for e in C.errs if 'PAGEERR' in e], C.errs[:3])
        await C.close()
    # 진짜 두 창: 새 창이 이어받으면 낡은 창은 저장소 이벤트로 곧바로 닫히고, 그 뒤 버튼을 눌러도 아무 일도 없다(오류 없음)
    C = await Ctx(b, srv.port).open(); A = await C.page()
    await A.evaluate("()=>localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'t',exp:Date.now()+30*864e5,name:'x'}))")
    chs = await A.evaluate("__W.CHARS.map(c=>c.k)")
    await make_world(A, chs[0], t0=1500, stuff=True, boss=False)
    await A.evaluate("()=>__W.pauseGame()")
    B = await reopen(C, None); stB = await B.evaluate("()=>__W.state"); keyB = await B.evaluate("(k)=>localStorage.getItem(k)", KEY)
    await A.wait_for_timeout(400); C.net.clear()
    await A.evaluate("()=>document.getElementById('quitBtn').click()"); await A.wait_for_timeout(300)
    stA = await A.evaluate("()=>[__W.state,!!__W.S]")
    check('진짜 두 창: 새 창이 이어받았다(%s) · 낡은 창은 닫혀 있고 눌러도 기록·오류가 없다 %s' % (stB, stA), stB == 'pause' and stA == ['title', False] and not [n for n in C.net if '/p6/run' in n[1]] and not [e for e in C.errs if 'PAGEERR' in e] and await B.evaluate("(k)=>localStorage.getItem(k)", KEY) == keyB, (stB, stA, C.net, C.errs[:2]))
    await C.close()

# ───────────── 바. 여러 번 닫았다 열기 ─────────────
async def sec_chain(b, srv):
    print('\n── 바. 닫았다 열기를 여러 번(저장 → 복구 → 저장 → 복구 …) ──', flush=True)
    C = await Ctx(b, srv.port).open()
    A = await C.page(); chs = await A.evaluate("__W.CHARS.map(c=>c.k)")
    for ch in chs[:6]:
        await make_world(A, ch, t0=1200 + 300 * (chs.index(ch) % 5), stuff=True, boss=(chs.index(ch) % 2 == 0))
        await A.evaluate("()=>__W.pauseGame()")
        pre = await A.evaluate("()=>__world()"); cur = A; ok = True; why = ''
        for k in range(4):
            blob = await cur.evaluate("(k)=>localStorage.getItem(k)", KEY)
            if not blob: ok = False; why = 'save%d 없음' % k; break
            B = await reopen(C, blob)
            post = await B.evaluate("()=>__world()")
            if not same_world(pre, post): ok = False; why = '%d번째: %s' % (k + 1, first_diff(pre, post)); await B.close(); break
            if cur is not A: await cur.close()
            cur = B
        if cur is not A: await cur.close()
        check('[%s] 4번 연속 닫았다 열어도 적 %d · 보석 %d 가 그대로(매번 일시정지 상태로 저장·복구)' % (ch, pre['sum']['e'], pre['sum']['g']), ok, why)
        await A.evaluate("()=>localStorage.removeItem('p6_resume_v1')")
    await C.close()

SECS = [('가', sec_fidelity), ('나', sec_census), ('다', sec_limits), ('라', sec_compat), ('마', sec_stale), ('바', sec_chain)]

# ───────────── 돌연변이: 고친 줄을 되돌리면 시험이 빨강이 되는가 ─────────────
MUT = {
    'census-load': ("    if(o.cn){const df=censusDiff(o.cn,census());if(df.length)throw new Error('census '+df.slice(0,4).join(','));}", "", {'나'}),
    'validate-pools': ("    validatePools();}\n  function validatePools()", "    }\n  function validatePools()", {'다'}),
    'maxlen': ("    if(body.length>MAXLEN)return {text:null,why:'too-big',rep};", "", {'다'}),
    'resume-guard': ("||RES.shopBad()||RES.broken())return;", "||RES.shopBad())return;", {'라'}),
    'stale-quit': ("$('quitBtn').onclick=()=>{if(RES.stale())return;endRun(false,true);};", "$('quitBtn').onclick=()=>{endRun(false,true);};", {'마'}),
    'stale-home': ("$('homeBtn').onclick=()=>{if(RES.stale())return;state='title';", "$('homeBtn').onclick=()=>{state='title';", {'마'}),
}

async def run_sections(b, srv, secs):
    for name, fn in SECS:
        if name in secs and want(name): await fn(b, srv)

async def main():
    global DST
    t0 = time.time()
    src = open(os.path.join(H.ROOT, 'survivors.html'), encoding='utf-8').read()
    srv = H.Srv()
    made = []
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            if not MUTANTS:
                H.make_copy(dst=DST, extra=HOOK); made.append(DST)
                await run_sections(b, srv, {n for n, _ in SECS})
            else:
                for mname, (old, new, secs) in MUT.items():
                    assert src.count(old) == 1, ('돌연변이 대상 줄을 못 찾음', mname)
                    dst = 'survivors_rwm_%s.html' % mname
                    tmp = os.path.join(H.ROOT, 'survivors_rwm_src.html'); open(tmp, 'w', encoding='utf-8').write(src.replace(old, new)); made.append('survivors_rwm_src.html')
                    H.make_copy(src='survivors_rwm_src.html', dst=dst, extra=HOOK); made.append(dst)
                    DST = dst
                    before = len(FAILS); CURRENT['tag'] = '[돌연변이 %s] ' % mname
                    print('\n★★ 돌연변이 %s — 이 줄을 되돌린 사본에서 구간 %s 가 빨강이어야 한다' % (mname, ','.join(sorted(secs))), flush=True)
                    await run_sections(b, srv, secs)
                    red = len(FAILS) - before
                    CURRENT['tag'] = ''
                    print(('✔ 잡았다' if red else '✘ 못 잡았다(시험이 약하다)') + ' — 돌연변이 %s: 빨강 %d건' % (mname, red), flush=True)
                    if not red: FAILS.append('돌연변이 %s 를 못 잡음' % mname)
            await b.close()
    finally:
        srv.close()
        for f in set(made):
            try: os.remove(os.path.join(H.ROOT, f))
            except OSError: pass
    if MUTANTS:
        # 돌연변이 실행에서는 '빨강이 있어야' 정상 — 위에서 빨강 0건인 돌연변이만 실패로 센다
        real = [f for f in FAILS if f.startswith('돌연변이 ')]
        print('\n돌연변이 시험: %s (걸린 시간 %.0f초)' % ('모두 잡혔다' if not real else '못 잡은 것 %s' % real, time.time() - t0))
        return 1 if real else 0
    print('\n실패 %d · 걸린 시간 %.0f초' % (len(FAILS), time.time() - t0))
    for f in FAILS: print('  -', f)
    return 1 if FAILS else 0

if __name__ == '__main__':
    import socketserver; socketserver.ThreadingTCPServer.handle_error = lambda self, *a: None
    sys.exit(asyncio.run(main()))
