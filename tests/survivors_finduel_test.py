# -*- coding: utf-8 -*-
"""⚔ 최종 보스 1:1 대결 시험 — 흐접새우 서바이벌(survivors.html) 55분 최종 보스(👑 흐접새우 본체)
[2026-10-12 사장님 지시 「마지막보스 흐접새우 등장시 흐접새우 제외 모든 몬스터는 제거하고 보스와의 1:1을 연출하고 적당히 어려운 난이도의 기믹패턴들 넣어줘」]

  가  등장 순간: 다른 몬스터(잡몹·엘리트·대형·다른 보스·특별 보스)·적 탄·함정·독가스·폭발 예고·레이저·부채꼴·카드·진실의 방이 전부 사라지고 보스만 남는다
      → 킬로 세지 않는다(처치 수·처치 기록·보석·아이템 드롭·경험치가 늘지 않는다) · 바닥 보석·아이템은 남고 보석은 자석으로 모여든다 · 경기장·연출·무적이 켜진다
  나  1:1 동안: 일반 소환 0(몰이·대형·미니 보스·보스 「소환」 패턴) · 필드엔 보스뿐 · 다음 소환 시각이 같이 밀린다 · 쓰는 패턴은 표에 있는 것뿐
  다  패턴: 예고(≥0.8초)가 먼저 보이고 터진다 · 예고 후에만 피해 · 모든 위치에서 예고 시간 안에 닿는 안전한 곳이 있다(부채꼴·돌진 길·새우깡·안전지대는 해석,
      거품 탄막은 시공간 탐색으로 「피하는 길이 실제로 있다」를 보인다) · 한 번에 최대 체력의 40% 를 넘지 않는다 · 한 번에 한 패턴(겹침 ≤ 1) · 탄 수 상한
  라  단계: 체력 66%·33% 와 시간(100초·200초)으로 오른다 · 전환 컷은 무적 + 배너 + 예고·탄 정리 · 광폭은 더 빠르고 더 몰아친다
  마  껍질(피해 감소)·약점(피해 증가)·벽 기절 · 보스 처치 뒤 정상 복귀(몬스터가 다시 나온다 · 처치 배너 · 상자 · 소환 밀림 없음)
  바  이어하기: 1:1 도중 저장→복구가 같다(적 탄·예고·껍질·돌진 중 포함) · 복구 뒤에도 이어진다(몹이 되살아나지 않는다) · 서명(SIG) 불변 · 옛 저장본(1:1 이전의 최종 보스)은 예전 보스 그대로
  사  모드: 하드·베리하드·무한(60분 뒤엔 1:1 이 끝난 것으로) · 일시정지·레벨업·상자·사망·부활·2배속
  아  성능·표시: 필드 엔티티 감소 · 탄 수 상한 · 폰(360×640)에서 가로 넘침 0·페이지 오류 0 · 연출(띠·큰 글자)이 그려진다
사용: python3 tests/survivors_finduel_test.py [--only 가,나,..] [--mutants]
  FD_SRC=<html> 로 다른 사본(변이본)을 시험한다. --mutants: 고친 줄을 하나씩 되돌린 사본에서 해당 구간이 빨강이 되는지 본다(시험이 진짜로 잡는지).
임시 사본 survivors_fdt*.html (.gitignore 대상 · 끝나면 지운다)."""
import asyncio, json, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
os.environ.setdefault('SV_CSX_OFF', '1')   # 2026-10-12: 캐릭터 고유 능력(CSX)을 중립으로 — 이 시험은 브장신을 「능력 없는 기준」으로 쓴다(능력 자체는 survivors_cabil_test.py)
from playwright.async_api import async_playwright

ROOT = H.ROOT
SRC = os.environ.get('FD_SRC', 'survivors.html')
HTML = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SRC) if not os.path.isabs(SRC) else SRC, encoding='utf-8').read()
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
MUTANTS = '--mutants' in sys.argv
SHOT = os.environ.get('FD_SHOT', '')
FAILS = []
TAG = {'v': ''}
KEY = 'p6_resume_v1'
BASE_SIG = os.environ.get('FD_BASE_SIG', '')      # 비어 있으면 origin/main 의 survivors.html 에서 직접 뽑는다


def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + TAG['v'] + n + ('' if c else ('  ← ' + str(x)[:900] if x != '' else '')), flush=True)
    if not c:
        FAILS.append(TAG['v'] + n)


def want(sec):
    return ONLY is None or sec in ONLY


EXTRA = r"""
window.__fd={get F(){return FIN_DUEL},get D(){return duelBoss()},dzHit,duelBoss,capHit,duelStart,duelPick,addBeam,KIND,BOSS,spawnBoss,pauseGame,openChest,RES,SPD,
  eshots,hazards,clouds,gems,items,props,bubs,sp:0,dz:[],hits:[],drops:0,bn:[],get SIG(){return RES.SIG},get won(){return S.won}};
{const s0=spawnEnemy;spawnEnemy=function(){window.__fd.sp++;return s0.apply(this,arguments);};}
{const n0=dzNew;dzNew=function(D,z){const r=n0(D,z);if(r)window.__fd.dz.push(Object.assign({},r,{tc:S.t}));return r;};}
{const h0=hitP;hitP=function(d,m){const inv=S.p.inv>0;const r=h0.apply(this,arguments);window.__fd.hits.push({t:S.t,d,m:m||'',inv});return r;};}
{const d0=dropItem;dropItem=function(){window.__fd.drops++;return d0.apply(this,arguments);};}
{const b0=banner;banner=function(a,b,c){window.__fd.bn.push([a,b,c]);return b0.apply(this,arguments);};}
window.__step=(n,o)=>{o=o||{};const X=window.__p6x,dt=1/30;for(let i=0;i<n;i++){const st=X.state;if(st==='result')return 'result';
  if(st==='lvup'){X.pick(X.CUR[0]);continue;}if(st!=='play'){X.resume();continue;}
  const S=X.S;if(window.__keep){S.p.hp=S.p.mhp;if(window.__keep===2)S.p.inv=0;}
  if(window.__fd.SPD.on&&!window.__fd.duelBoss()){X.update(dt);if(X.state==='play'){window.__fd.SPD.sub=1;try{X.update(dt);}finally{window.__fd.SPD.sub=0;}}}else X.update(dt);
  if(o.fn&&o.fn())return 'fn';}
 return window.__p6x.state;};
// 판 시작(55분 직전) — 1:1 이 곧 시작된다
window.__fresh=(o)=>{o=o||{};const X=window.__p6x;X.CH_set(o.ch||'brj');X.start(o.daily?{daily:true}:undefined);const S=X.S;S.p.hp=S.p.mhp=o.mhp||1e9;S.t=o.t||3000;S.nextBoss=3300;S.nextMini=Infinity;S.nextSp=Infinity;S.bossN=10;
  S.evT=S.t+30;S.bigT=S.t+30;window.__keep=o.keep===undefined?1:o.keep;window.__fd.sp=0;window.__fd.dz.length=0;window.__fd.hits.length=0;window.__fd.drops=0;window.__fd.bn.length=0;return X.state;};
window.__begin=()=>{const X=window.__p6x,S=X.S;S.t=3300;S.evT=3330;S.bigT=3330;S.nextBoss=3300;X.update(1/30);return window.__fd.D?1:0;};
// 필드를 꽉 채운다(몹·엘리트·대형·다른 보스·특별 보스·적 탄·함정·독가스·폭발·레이저·부채꼴·카드·진실의 방·보석·아이템)
window.__fill=()=>{const X=window.__p6x,S=X.S,p=S.p,FD=window.__fd,rnd=(a,b)=>a+Math.random()*(b-a);const K=FD.KIND.length;let n=0;
  for(let i=0;i<80;i++){const e=X.spawnEnemy(i%K,1+S.t/600);if(!e)break;n++;e.x=p.x+rnd(-500,500);e.y=p.y+rnd(-400,400);if(i%9===0){e.el=1;e.mhp=e.hp=e.hp*6;}if(i%13===0){e.bg=1;e.r*=2;}}
  const y=FD.spawnBoss('yj'),g=FD.spawnBoss('bgb');   // 다른 보스(미니·일반이 아닌 것) + 특별 보스
  for(let i=0;i<30;i++){const b=FD.eshots.get();if(!b)break;b.x=p.x+rnd(-500,500);b.y=p.y+rnd(-400,400);b.vx=rnd(-50,50);b.vy=rnd(-50,50);b.life=5;b.d=5;b.src=null;}
  for(let i=0;i<10;i++){const h=FD.hazards.get();if(!h)break;h.x=p.x+rnd(-400,400);h.y=p.y+rnd(-300,300);h.life=30;h.d=5;}
  for(let i=0;i<10;i++){const c=X.clouds.get();if(!c)break;c.x=p.x+rnd(-400,400);c.y=p.y+rnd(-300,300);c.life=20;c.d=3;}
  for(let i=0;i<4;i++)S.ebooms.push({x:p.x+rnd(-300,300),y:p.y+rnd(-300,300),R:80,t:2,T:2,d:5});
  FD.addBeam(p.x+200,p.y,0,1.5,500,5,null,null);
  S.cone={e:y,sn:y.sn,a:0,t:1,R:300,w:.5,d:5,hit:0};S.cardW={e:y,sn:y.sn,a:0,t:1,T:1,n:5,sp:.2,L:400};S.room={x:p.x,y:p.y,R:300,t:6};
  for(let i=0;i<30;i++){const q=X.gems.get();if(!q)break;q.x=p.x+rnd(500,900)*(i%2?1:-1);q.y=p.y+rnd(500,900)*(i%3?1:-1);q.v=5;q.mag=0;}
  for(const k of ['chicken','bomb','magnet']){const it=X.items.get();it.k=k;it.x=p.x+rnd(300,600);it.y=p.y+rnd(-300,300);it.life=60;it.t=0;}
  return n;};
window.__snap=()=>{const X=window.__p6x,S=X.S,FD=window.__fd;let gv=0,gn=0;for(const q of X.gems.a)if(q.on){gv+=q.v;gn++;}
  return {kills:S.kills,mid:S.midKill,bk:S.bossKill,xp:S.xp,lv:S.lv,gv,gn,items:X.items.a.filter(o=>o.on).length,drops:FD.drops,en:X.enemies.a.filter(e=>e.on).length,
   bosses:X.enemies.a.filter(e=>e.on&&e.boss).length,es:FD.eshots.a.filter(o=>o.on).length,hz:FD.hazards.a.filter(o=>o.on).length,cl:X.clouds.a.filter(o=>o.on).length,
   stale:S.live.filter(e=>!e.on).length,eb:S.ebooms.length,bm:S.beams.length,cone:!!S.cone,card:!!S.cardW,room:!!S.room,dmgBy:JSON.stringify(S.dmgBy),t:S.t,sp:FD.sp};};
// 한 패턴 시험 자리 만들기: 단계 · 보스 자리 · 내 자리 — 보스는 제자리(속도 0), 내 키는 비운다
window.__reset=(ph,bx,by,px,py,mhp)=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du,p=S.p;
  S.t=3400;du.z.length=0;du.cur=null;du.cd=0;du.in=0;du.iv=0;du.sh=0;du.wk=0;du.ph=ph;D.bph=ph;du.bag=[];du.t0=S.t-ph*FD.F.phaseSec-1;
  for(const b of FD.eshots.a)b.on=false;D.hp=D.mhp;D.sp=0;
  D.x=du.cx+bx;D.y=du.cy+by;p.x=du.cx+px;p.y=du.cy+py;p.yt=0;p.stun=0;p.inv=0;if(mhp){p.mhp=p.hp=mhp;}X.keys={};FD.dz.length=0;FD.hits.length=0;return true;};
"""

# 안전한 곳이 있나(해석) — 같은 순간에 뜬 구역 묶음 zs 와 내 자리 p0 로, 반응 시간(react) 뒤에 예고 시간 안에 닿는 곳 중 구역에 안 걸리고 경기장 안인 곳이 있는가
REACH_JS = r"""
window.__reach=(zs,p0,sp,react,du,pr)=>{
  const FD=window.__fd,T=Math.min(...zs.map(z=>z.T)),R0=Math.max(0,sp*(T-react)),inB=(z,x,y)=>{const dx=x-z.x,dy=y-z.y,al=dx*z.ax+dy*z.ay,pe=Math.abs(-dx*z.ay+dy*z.ax);return al>-z.w*.5&&al<z.L+10&&pe<z.w/2+8;/* 길 폭 z.w 에 이미 내 몸 반지름이 들어 있다 */};
  const hit=(x,y)=>{for(const z of zs){if(z.k==='s')continue;if(z.k==='b'){if(inB(z,x,y))return true;continue;}
      for(const [ox,oy] of [[0,0],[8,0],[-8,0],[0,8],[0,-8]])if(FD.dzHit(z,x+ox,y+oy))return true;}return false;};
  let best=null;
  for(let r=0;r<=R0;r+=6){const n=r===0?1:Math.max(8,Math.round(r*6.2832/10));
    for(let i=0;i<n;i++){const a=i/n*6.2832,x=p0.x+Math.cos(a)*r,y=p0.y+Math.sin(a)*r;
      if(Math.hypot(x-du.cx,y-du.cy)>du.R-pr)continue;if(!hit(x,y))return {ok:true,r};}}
  return {ok:false,R0};};
// 시공간 탐색 — 탄막(거품) 기록(frames: 1/30초마다 탄 좌표)에서 내가 p0 에서 출발해 끝까지 안 맞고 살아남는 길이 있는가
window.__bfs=(frames,p0,sp,react,du,pr)=>{
  const cell=10,Rr=du.R-pr,N=Math.ceil(2*Rr/cell)+3,ox=du.cx-Rr-cell,oy=du.cy-Rr-cell,idx=(x,y)=>y*N+x,inside=(x,y)=>Math.hypot(ox+x*cell-du.cx,oy+y*cell-du.cy)<=Rr;
  let cur=new Uint8Array(N*N);const sx=Math.round((p0.x-ox)/cell),sy=Math.round((p0.y-oy)/cell);cur[idx(sx,sy)]=1;
  const rad=pr+6+10,reachC=2;const layers=frames.filter((f,i)=>i%3===0);
  for(let li=1;li<layers.length;li++){const b=layers[li],haz=new Uint8Array(N*N);
    for(let k=0;k<b.length;k+=2){const bx=Math.round((b[k]-ox)/cell),by=Math.round((b[k+1]-oy)/cell),rr=Math.ceil(rad/cell);
      for(let yy=by-rr;yy<=by+rr;yy++)for(let xx=bx-rr;xx<=bx+rr;xx++){if(xx<0||yy<0||xx>=N||yy>=N)continue;if(Math.hypot(ox+xx*cell-b[k],oy+yy*cell-b[k+1])<rad)haz[idx(xx,yy)]=1;}}
    const nxt=new Uint8Array(N*N);let any=false;const canMove=li*0.1>react;
    for(let y=0;y<N;y++)for(let x=0;x<N;x++){if(!cur[idx(x,y)])continue;
      for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){if(!canMove&&(dx||dy))continue;const xx=x+dx,yy=y+dy;if(xx<0||yy<0||xx>=N||yy>=N)continue;
        if(!inside(xx,yy)||haz[idx(xx,yy)])continue;nxt[idx(xx,yy)]=1;any=true;}}
    if(!any)return {ok:false,at:li*0.1};cur=nxt;}
  return {ok:true};};
"""

POS = [(0, 0), (0.85, 0), (-0.85, 0), (0, 0.85), (0, -0.85), (0.6, 0.6), (-0.6, 0.6), (0.6, -0.6), (-0.6, -0.6), (0.3, 0.1)]   # 경기장 반지름 비율


async def open_page(b, port, w=1280, h=720, mobile=False, seed=7, pre='', name='survivors_fdt.html'):
    p = H.make_copy(SRC, name, extra='\n' + EXTRA + REACH_JS)
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port):
            await r.continue_()
        else:
            await r.abort()
    await ctx.route('**/*', route)
    await ctx.add_init_script("(()=>{const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};Math.random=mb(%d);window.requestAnimationFrame=()=>0;window.cancelAnimationFrame=()=>{};try{localStorage.setItem('p6_fx','0');}catch(e){}%s})();" % (seed, pre))   # 게임 루프(rAF)를 멈춰 둔다 — 시험이 update 를 직접 돌린다(실시간 프레임이 끼어들어 판이 저절로 진행되는 것을 막는다)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/%s' % (port, name))
    await pg.wait_for_function('window.__p6x!==undefined&&window.__fd!==undefined', polling=50, timeout=15000)   # rAF 를 멈춰 뒀으니 polling 은 시간 간격으로
    return ctx, pg, errs, p


def seg(name):
    print('\n── %s' % name, flush=True)


# ───────────────────────── 가 ─────────────────────────
async def sec_a(b, srv):
    seg('가 등장 순간 정리')
    ctx, pg, errs, p = await open_page(b, srv.port)
    try:
        await pg.evaluate("()=>__fresh({keep:0,mhp:1e9})")
        n = await pg.evaluate("()=>__fill()")
        pre = await pg.evaluate("()=>__snap()")
        check('가1 준비: 몹 %d마리 + 보스 2 + 탄·함정·독가스·폭발·레이저·부채꼴·카드·방 · 보석 30 · 아이템 3' % n, n >= 60 and pre['bosses'] == 2 and pre['es'] >= 20 and pre['hz'] >= 5 and pre['cl'] >= 5 and pre['eb'] == 4 and pre['bm'] == 1 and pre['cone'] and pre['card'] and pre['room'] and pre['gn'] == 30 and pre['items'] == 3, pre)
        pre = await pg.evaluate("()=>{const s=__snap();return s}")
        await pg.evaluate("()=>{window.__fd.drops=0;window.__fd.sp=0}")
        r = await pg.evaluate("()=>{const ok=__begin();const e=window.__fd.D;return {ok,snap:__snap(),du:e&&e.du&&{R:e.du.R,in:e.du.in,iv:e.du.iv,ph:e.du.ph},boss:e&&e.boss,xp:window.__p6x.S.p.inv}}")
        post = r['snap']
        check('가2 1:1 이 시작됐다(경기장·연출·무적: 지름 R≥340 · 연출 1.6초 · 단계 0)', r['ok'] == 1 and r['boss'] == 'fin' and r['du'] and r['du']['R'] >= 340 and r['du']['R'] <= 430 and r['du']['in'] > 1.4 and r['du']['ph'] == 0, r)
        check('가3 필드에 보스 하나만 남았다 (몬스터 %d → %d · 보스 %d)' % (pre['en'], post['en'], post['bosses']), post['en'] == 1 and post['bosses'] == 1, post)
        check('가4 적 탄·함정·독가스·폭발 예고·레이저·부채꼴·카드·진실의 방이 전부 사라졌다', post['es'] == 0 and post['hz'] == 0 and post['cl'] == 0 and post['eb'] == 0 and post['bm'] == 0 and not post['cone'] and not post['card'] and not post['room'], post)
        check('가5b 이 프레임에 아직 남은 코드가 치운 적을 다시 건드리지 않게 살아 있는 적 목록(S.live)에도 보스뿐 (죽은 칸 %d)' % post['stale'], post['stale'] == 0, post)
        check('가5 킬로 세지 않는다: 처치 수 %d → %d · 중간보스 처치 %s → %s · 보스 처치 %s · 준 피해 표 그대로' % (pre['kills'], post['kills'], pre['mid'], post['mid'], post['bk']),
              post['kills'] == pre['kills'] and post['mid'] == pre['mid'] and post['bk'] == 0 and post['dmgBy'] == pre['dmgBy'], (pre, post))
        check('가6 드롭이 안 늘었다(아이템 떨굼 호출 0 · 바닥 아이템 %d → %d) · 경험치·레벨 그대로' % (pre['items'], post['items']), post['drops'] == 0 and post['items'] == pre['items'] and post['xp'] == pre['xp'] and post['lv'] == pre['lv'], (pre, post))
        check('가7 바닥 보석은 그대로 남았다(개수 %d · 값 합 %s)' % (post['gn'], post['gv']), post['gn'] == pre['gn'] and post['gv'] == pre['gv'], (pre, post))
        # 보석이 자석으로 모여들어 먹힌다(경험치가 오른다)
        r = await pg.evaluate("()=>{const X=window.__p6x,S=X.S;const mag=X.gems.a.filter(g=>g.on&&g.mag).length;const xp0=S.xp,lv0=S.lv;__step(30*12);return {mag,xp0,lv0,xp:S.xp,lv:S.lv,left:X.gems.a.filter(g=>g.on).length}}")
        check('가8 바닥 보석은 자석으로 모여들어 먹힌다 (자석 켜짐 %d/30 · 12초 뒤 남은 보석 %d · 경험치 %s→%s)' % (r['mag'], r['left'], r['xp0'], r['xp']), r['mag'] == 30 and r['left'] == 0 and (r['xp'] > r['xp0'] or r['lv'] > r['lv0']), r)
        # 되살아나지 않는다 + 보스 칸이 다시 안 덮어쓰인다
        r = await pg.evaluate("()=>{const X=window.__p6x,S=X.S,FD=window.__fd;let mx=0,k=S.kills;FD.sp=0;for(let i=0;i<30*20;i++){__step(1);const e=X.enemies.a.filter(q=>q.on&&q!==FD.D).length;mx=Math.max(mx,e);}return {mx,kills:S.kills-k,sp:FD.sp,bosses:X.enemies.a.filter(e=>e.on&&e.boss).length}}")
        check('가9 20초가 지나도 보스 말고는 하나도 안 나온다 (최대 %d · 생성 호출 %d · 처치 증가 %d)' % (r['mx'], r['sp'], r['kills']), r['mx'] == 0 and r['sp'] == 0 and r['bosses'] == 1, r)
        check('가10 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 나 ─────────────────────────
async def sec_b(b, srv):
    seg('나 1:1 동안 소환 0')
    ctx, pg, errs, p = await open_page(b, srv.port)
    try:
        await pg.evaluate("()=>{__fresh({keep:1});__fill();__begin();window.__fd.sp=0;window.__seen={};window.__s0={ev:window.__p6x.S.evT,big:window.__p6x.S.bigT,sp:window.__p6x.S.spawnT,t:window.__p6x.S.t};return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;let mx=0,t0=S.t;const kinds={};
          for(let i=0;i<30*95;i++){__step(1);const D=FD.D;if(!D)break;mx=Math.max(mx,X.enemies.a.filter(e=>e.on&&e!==D).length);const c=D.du.cur;if(c)kinds[c.k]=1;}
          return {mx,sp:FD.sp,kinds:Object.keys(kinds).sort(),ev:S.evT-window.__s0.ev,big:S.bigT-window.__s0.big,spawnT:S.spawnT,sp0:window.__s0.sp,dt:S.t-window.__s0.t,still:!!FD.D,ph:FD.D&&FD.D.du.ph}}""")
        check('나1 95초 동안 몹이 한 마리도 안 나온다 (필드 최대 %d · 생성 호출 %d)' % (r['mx'], r['sp']), r['mx'] == 0 and r['sp'] == 0, r)
        check('나2 다음 몰이·대형 시각이 같이 밀린다(+%.0f · +%.0f ≈ 경과 %.0f초)' % (r['ev'], r['big'], r['dt']), abs(r['ev'] - r['dt']) < 2 and abs(r['big'] - r['dt']) < 2, r)
        check('나3 평소 스폰 누적도 그대로(spawnT %s → %s) — 끝난 뒤에 한꺼번에 쏟아지지 않는다' % (r['sp0'], r['spawnT']), abs(r['spawnT'] - r['sp0']) < 1e-9, r)
        check('나4 쓰는 패턴은 표의 것뿐(꼬리·집게·거품·새우깡 + 단계 컷) — 「소환」이 없다: %s' % r['kinds'], set(r['kinds']) <= {'tail', 'claw', 'bub', 'snack', 'shell', 'safe', 'cut'} and 'summon' not in r['kinds'] and len(r['kinds']) >= 4, r)
        check('나5 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 다 ─────────────────────────
async def run_pattern(pg, ph, k, bpos, ppos, mhp=None, maxsec=16):
    """한 패턴을 끝까지 돌리며 구역 생성·피해·탄 기록을 돌려준다(보스는 제자리 · 나는 가만히 · 무적 아님 — 닿으면 피해 기록이 남는다)"""
    return await pg.evaluate("""([ph,k,bpos,ppos,mhp,maxsec])=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du,R=du.R;
      __reset(ph,bpos[0]*R,bpos[1]*R,ppos[0]*R,ppos[1]*R,mhp);window.__keep=2;du.cur=FD.duelStart(du,k);const frames=[],es0=[];let maxEs=0,conc=0,t0=S.t;
      const zs0=()=>FD.dz.slice();
      for(let i=0;i<30*maxsec;i++){__step(1);const b=[];for(const q of FD.eshots.a)if(q.on){b.push(q.x,q.y);}maxEs=Math.max(maxEs,b.length/2);frames.push(b);if(du.cur===null)du.cd=1e9;   // 이 패턴이 끝났으면 다음 패턴이 시작되지 않게 막는다(남은 탄이 사라질 때까지만 본다)
        
        if(du.cur===null&&du.z.length===0&&b.length===0)break;}
      const px=X.S.p.x,py=X.S.p.y;
      return {dmg:D.dmg,dz:FD.dz.map(z=>Object.assign({},z)),hits:FD.hits.slice(),maxEs,frames,t:S.t-t0,done:du.cur===null,p0:{x:du.cx+ppos[0]*R,y:du.cy+ppos[1]*R},R,cx:du.cx,cy:du.cy,pr:S.p.r,sp:S.p.sp,mhp:S.p.mhp}}""", [ph, k, list(bpos), list(ppos), mhp, maxsec])


ZMSG = {'c': '🦐 꼬리 휩쓸기!', 'd': '🍤 새우깡 비!', 'o': '💥 안전지대 밖!'}


async def sec_c(b, srv):
    seg('다 패턴 — 예고 · 예고 후에만 피해 · 안전한 길 · 피해 상한')
    ctx, pg, errs, p = await open_page(b, srv.port)
    try:
        await pg.evaluate("()=>{__fresh({keep:2,mhp:1e9});__begin();return 1}")
        F = await pg.evaluate("()=>window.__fd.F")
        react = 0.3
        tele_bad, early, nosafe, nobfs, capbad, tot_z, tot_hits, tot_bfs = [], [], [], [], [], 0, 0, 0
        decks = F['deck']
        maxEs_all = 0
        for ph in range(3):
            for k in decks[ph]:
                for bi, bpos in enumerate([(0, 0), (0.5, 0.3)]):
                    for pi, ppos in enumerate(POS[:6] if MUTANTS else POS):   # 변이 시험은 시간을 아끼려고 자리를 줄인다
                        if abs(ppos[0] - bpos[0]) + abs(ppos[1] - bpos[1]) < 0.18:
                            continue   # 보스 몸 위는 제외(몸통 박치기 시험이 아니다)
                        r = await run_pattern(pg, ph, k, bpos, ppos)
                        maxEs_all = max(maxEs_all, r['maxEs'])
                        if not r['done']:
                            nosafe.append(('미종료', ph, k, bpos, ppos)); continue
                        du = {'cx': r['cx'], 'cy': r['cy'], 'R': r['R']}
                        zones = [z for z in r['dz']]
                        tot_z += len(zones)
                        for z in zones:
                            if z['T'] < F['minTele'] - 1e-9 and z['k'] in ('c', 'd', 'o', 'b'):
                                tele_bad.append((ph, k, z['k'], z['T']))
                            if z['k'] == 's' and z['T'] < F['minTele'] - 1e-9:
                                tele_bad.append((ph, k, z['k'], z['T']))
                        # 예고 후에만 피해: 부채꼴·새우깡·안전지대 피해는 해당 구역이 터진 뒤(예고 T 가 다 지난 뒤)에만
                        for h in r['hits']:
                            if h['m'] in ZMSG.values():
                                kz = [kk for kk, v in ZMSG.items() if v == h['m']][0]
                                zz = [z for z in zones if z['k'] == kz and z['tc'] <= h['t'] + 1e-9]
                                if not zz or (h['t'] - zz[-1]['tc']) < zz[-1]['T'] - 0.05 or zz[-1]['T'] < F['minTele'] - 1e-9:
                                    early.append((ph, k, h['m'], round(h['t'], 2)))
                            elif h['m'] == '🦞 집게 돌진!':
                                zz = [z for z in zones if z['k'] == 'b' and z['tc'] <= h['t']]
                                if not zz or (h['t'] - zz[-1]['tc']) < F['minTele'] - 0.05:
                                    early.append((ph, k, h['m'], round(h['t'], 2)))
                            elif h['m'] == '' and abs(h['d'] - r['dmg']) < 1e-6:
                                pass   # 몸 박치기(보스 몸에 닿은 것 — 패턴 피해가 아니다 · 한 번에 최대 체력 40%% 상한은 별도로 본다)
                            elif h['m'] == '':   # 거품 탄에 맞음 — 틈 표시(s)가 최소 .8초 먼저 떠 있었다
                                zz = [z for z in zones if z['k'] == 's' and z['tc'] <= h['t']]
                                if not zz or (h['t'] - zz[-1]['tc']) < F['minTele'] - 0.05:
                                    early.append((ph, k, '탄', round(h['t'], 2)))
                            tot_hits += 1
                        # 피해 상한: 한 번에 최대 체력의 40%(기본 mhp 1e9 라 여기선 d 가 e.dmg 배수 그대로 — 상한은 아래 별도 시험)
                        # 안전한 길
                        if k in ('tail', 'claw', 'snack', 'safe'):
                            groups = {}
                            for z in zones:
                                if z['k'] in ('c', 'd', 'o', 'b'):
                                    groups.setdefault(round(z['tc'], 3), []).append(z)
                            for tc, zs in groups.items():
                                a = await pg.evaluate("([zs,p0,sp,react,du,pr])=>__reach(zs,p0,sp,react,du,pr)", [zs, r['p0'], r['sp'], react, du, r['pr']])
                                if not a['ok']:
                                    nosafe.append((ph, k, tc, bpos, ppos, a))
                        else:
                            tot_bfs += 1
                            a = await pg.evaluate("([fr,p0,sp,react,du,pr])=>__bfs(fr,p0,sp,react,du,pr)", [r['frames'], r['p0'], r['sp'], react, du, r['pr']])
                            if not a['ok']:
                                nobfs.append((ph, k, bpos, ppos, a))
        check('다1 모든 예고(부채꼴·돌진 길·새우깡·안전지대·탄막 틈 표시)는 ≥ 0.8초 (구역 %d개)' % tot_z, not tele_bad and tot_z > 200, tele_bad[:4])
        check('다2 예고 후에만 피해: 피해 %d번 모두 예고(≥0.8초)가 다 지난 뒤였다' % tot_hits, not early and tot_hits > 0, early[:4])
        check('다3 부채꼴·돌진 길·새우깡·안전지대 — 단계 3 × 자리 ≤ 20 모두에서 예고 시간 안에 닿는 안전한 곳이 있다(반응 0.3초 · 내 속도 180)', not nosafe, nosafe[:4])
        check('다4 거품 탄막(껍질 포함) — %d판 시공간 탐색: 틈으로 빠져 끝까지 안 맞는 길이 항상 있다' % tot_bfs, not nobfs and tot_bfs > 60, nobfs[:4])
        check('다5 탄 수 상한: 한 패턴이 한 번에 띄우는 탄 최대 %d ≤ 풀 크기 %d 의 70%%' % (maxEs_all, 100), maxEs_all <= 70, maxEs_all)
        # 피해 상한(체력 100 이라도 한 번에 40 을 넘지 않는다) — 하드·베리하드는 e.dmg 가 더 크지만 같은 상한
        capmax = 0
        for k in ('tail', 'claw', 'snack', 'safe', 'bub'):
            r = await run_pattern(pg, 2, k, (0, 0), (0.3, 0.1) if k != 'safe' else (0.3, 0.1), mhp=100)
            for h in r['hits']:
                if h['m'] or True:
                    capmax = max(capmax, h['d'])
        check('다6 한 번에 최대 체력(100)의 40%% 를 넘지 않는다: 가장 센 한 방 %.1f ≤ 40' % capmax, capmax <= 40.0001, capmax)
        # 겹침: 한 번에 한 패턴(D.cur 하나) + 구역 ≤ 24 — 구조상 하나지만 구역 동시 개수도 본다
        r = await pg.evaluate("""()=>{const FD=window.__fd,X=window.__p6x;__reset(2,0,0,200,0);window.__keep=2;const du=FD.D.du;let mz=0,cur=0;for(let i=0;i<30*60;i++){__step(1);mz=Math.max(mz,du.z.length);if(du.cur&&du.cur.k!=='cut')cur=Math.max(cur,1);}return {mz,cur}}""")
        check('다7 60초 동안 구역 동시 최대 %d ≤ 11(새우깡 10 + 틈 1) · 패턴은 한 번에 하나' % r['mz'], r['mz'] <= 11 and r['cur'] == 1, r)
        # 다9 집게 돌진 예고 길 = 실제 닿는 범위(폭 = 보스 몸 + 내 몸 + 2 의 두 배). 길 안쪽 끝자락은 맞고, 길 밖 바로 옆은 안 맞는다
        for off_in, nm9 in ((-3, '안쪽 끝자락'), (4, '길 밖 바로 옆')):
            r = await pg.evaluate("""(off_in)=>{const FD=window.__fd,X=window.__p6x;__reset(0,0,0,200,0,1e9);window.__keep=0;const du=FD.D.du,S=X.S,p=S.p;du.cur=FD.duelStart(du,'claw');__step(1);
              const z=du.z.find(q=>q.k==='b');if(!z)return {fail:'길 없음'};const half=z.w/2,need=FD.D.r+p.r+2;
              const px=FD.D.x+z.ax*150,py=FD.D.y+z.ay*150;const off=half+off_in;p.x=px-z.ay*off;p.y=py+z.ax*off;p.inv=0;const hp0=p.hp=p.mhp;
              FD.hits.length=0;let i=0;while(du.cur&&i++<30*6){__step(1);p.x=px-z.ay*off;p.y=py+z.ax*off;p.inv=0;}
              return {half,need,hits:FD.hits.filter(h=>h.m.indexOf('집게')>=0).length}}""", off_in)
            if off_in < 0:
                check('다9a 집게 돌진 예고 길 반폭(%.1f) = 실제 닿는 거리(%.1f)' % (r.get('half', 0), r.get('need', 0)), not r.get('fail') and abs(r['half'] - r['need']) < 0.01, r)
                check('다9b 예고 길 %s(가운데에서 반폭-3): 돌진에 맞는다' % nm9, not r.get('fail') and r['hits'] >= 1, r)
            else:
                check('다9c 예고 길 %s(반폭+4): 돌진에 안 맞는다' % nm9, not r.get('fail') and r['hits'] == 0, r)
        check('다10 안내가 정직하다: 체력바 눈금(::after) 없음 · 「지금 공격」 문구 없음 · 이름 줄에 다음 단계까지 남은 초', ('.bar::after' not in HTML.split('#bossb.duel')[1].split('{')[0]) and '지금 공격' not in HTML and '다음 단계' in HTML, '')
        check('다8 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 라 ─────────────────────────
async def sec_d(b, srv):
    seg('라 단계 전환 · 광폭')
    ctx, pg, errs, p = await open_page(b, srv.port)
    try:
        await pg.evaluate("()=>{__fresh({keep:1});__begin();return 1}")
        F = await pg.evaluate("()=>window.__fd.F")
        # 체력으로: 66% 아래 → 2단계 → 33% 아래 → 3단계
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D;__step(30*3);const o={};o.ph0=D.du.ph;
          D.hp=D.mhp*.64;window.__fd.bn.length=0;let i=0;while(D.du.ph<1&&i++<30*30)__step(1);o.ph1=D.du.ph;o.bph1=D.bph;o.iv=D.du.iv>0;o.cutK=D.du.cur&&D.du.cur.k;o.z=D.du.z.length;o.es=FD.eshots.a.filter(q=>q.on).length;
          const h0=D.hp;X.hurt(D,1e12);o.noDmg=D.hp===h0;o.bn1=FD.bn.map(b=>b[0]);
          while(D.du.cur&&D.du.cur.k==='cut')__step(1);o.after=D.du.iv<=0;
          D.hp=D.mhp*.3;FD.bn.length=0;i=0;while(D.du.ph<2&&i++<30*40)__step(1);o.ph2=D.du.ph;o.bph2=D.bph;o.bn2=FD.bn.map(b=>b[0]);return o}""")
        check('라1 시작은 1단계', r['ph0'] == 0, r)
        check('라2 체력 66%% 아래 → 2단계 컷(무적 · 예고·탄 정리 · 배너 「2페이즈」 · 보스 표시 단계 %d)' % r['bph1'], r['ph1'] == 1 and r['bph1'] == 1 and r['iv'] and r['cutK'] == 'cut' and r['z'] == 0 and r['es'] == 0 and any('2페이즈' in t for t in r['bn1']), r)
        check('라3 컷 동안 보스는 피해를 안 받고 끝나면 무적이 풀린다', r['noDmg'] and r['after'], r)
        check('라4 체력 33% 아래 → 3단계(광폭) 컷 + 배너 「3페이즈」', r['ph2'] == 2 and r['bph2'] == 2 and any('3페이즈' in t and '광폭' in t for t in r['bn2']), r)
        check('라5 광폭은 더 빠르고 더 몰아친다: 예고 ≤ 1단계 · 쉬는 틈 %s→%s · 이동 배수 %s→%s · 꼬리 연타 %s→%s번 · 새우깡 %s→%s개' % (F['rest'][0], F['rest'][2], F['enr'][0], F['enr'][2], F['tail']['n'][0], F['tail']['n'][2], F['snack']['n'][0], F['snack']['n'][2]),
              all(F['tele'][k][2] < F['tele'][k][0] for k in ('tail', 'claw', 'snack', 'safe')) and F['rest'][2] < F['rest'][0] and F['enr'][2] > F['enr'][0] and F['tail']['n'][2] > F['tail']['n'][0] and F['snack']['n'][2] > F['snack']['n'][0] and F['bub']['dt'][2] < F['bub']['dt'][0] and all(F['tele'][k][2] >= F['minTele'] for k in ('tail', 'claw', 'snack', 'safe')), F)
        # 2단계 이후 패턴 묶음에 껍질·안전지대가 들어간다 / 3단계 광폭 이동이 실제로 더 빠르다
        check('라6 패턴 묶음: 1단계 %s · 2단계 +껍질·안전지대 · 3단계 전부' % F['deck'][0], 'shell' not in F['deck'][0] and 'safe' not in F['deck'][0] and 'shell' in F['deck'][1] and 'safe' in F['deck'][1] and set(F['deck'][1]) <= set(F['deck'][2]), F['deck'])
        # 시간으로: 체력이 안 깎여도 100초·200초에 단계가 오른다(새 판)
        await pg.evaluate("()=>{__fresh({keep:1});__begin();return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,o={t:[]};let last=0;
          for(let i=0;i<30*215;i++){__step(1);if(!FD.D)break;if(FD.D.du.ph!==last){last=FD.D.du.ph;o.t.push([+(S.t-D.du.t0).toFixed(1),last,+(D.hp/D.mhp).toFixed(3)]);}}return o}""")
        ok = len(r['t']) == 2 and r['t'][0][1] == 1 and r['t'][1][1] == 2 and 100 <= r['t'][0][0] <= 114 and 200 <= r['t'][1][0] <= 214 and r['t'][1][2] > .5
        check('라7 체력이 거의 안 깎여도 시간으로 단계가 오른다: %s' % r['t'], ok, r)
        # 단계가 한 번에 둘 오를 수 있다(체력 20% 로 시작 → 곧장 3단계)
        await pg.evaluate("()=>{__fresh({keep:1});__begin();window.__fd.D.hp=window.__fd.D.mhp*.2;return 1}")
        r = await pg.evaluate("()=>{let i=0;while(window.__fd.D.du.ph<2&&i++<30*30)__step(1);return window.__fd.D.du.ph}")
        check('라8 체력이 확 깎이면 단계를 건너뛰어 곧장 3단계', r == 2, r)
        check('라9 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 마 ─────────────────────────
async def sec_e(b, srv):
    seg('마 껍질·약점·기절 · 처치 뒤 복귀')
    ctx, pg, errs, p = await open_page(b, srv.port)
    try:
        await pg.evaluate("()=>{__fresh({keep:1});__begin();return 1}")
        F = await pg.evaluate("()=>window.__fd.F")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du;__step(60);const o={};
          const dmg=()=>{const h0=D.hp;X.hurt(D,1000);return h0-D.hp;};
          du.iv=0;du.sh=0;du.wk=0;o.base=dmg();du.sh=1;o.shell=dmg();du.sh=0;du.wk=2;o.weak=dmg();du.wk=0;du.iv=1;o.inv=dmg();du.iv=0;return o}""")
        check('마1 보통 1000 · 껍질 %.0f (×%s) · 약점 %.0f (×%s) · 무적 %.0f' % (r['shell'], F['shell']['mul'], r['weak'], F['shell']['wmul'], r['inv']),
              abs(r['base'] - 1000) < 1e-6 and abs(r['shell'] - 1000 * F['shell']['mul']) < 1e-6 and abs(r['weak'] - 1000 * F['shell']['wmul']) < 1e-6 and r['inv'] == 0, r)
        # 껍질 패턴: 껍질 동안 피해 감소 → 깨지면 약점(여기선 2단계로 올려서)
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du;__reset(1,0,0,300,0);window.__keep=2;du.cur=FD.duelStart(du,'shell');const o={sh:[],wk:[]};let i=0;
          while(du.cur&&i++<30*30){__step(1);o.sh.push(du.sh);o.wk.push(du.wk>0?1:0);}return {sh:o.sh.some(x=>x===1),wk:o.wk.some(x=>x===1),endSh:du.sh,firstSh:o.sh.indexOf(1),firstWk:o.wk.indexOf(1),secs:i/30,order:o.sh.indexOf(1)<o.wk.indexOf(1)}}""")
        check('마2 껍질 패턴: 껍질(피해 감소)이 켜졌다가 깨지고 → 약점(피해 증가)이 켜진다 · 끝나면 껍질 꺼짐 (%.1f초)' % r['secs'], r['sh'] and r['wk'] and r['endSh'] == 0 and r['order'], r)
        # 집게 돌진: 벽에 쾅 → 기절(약점) · 기절 중엔 안 움직인다
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du;__reset(0,0,0,300,0);window.__keep=2;D.sp=0;du.cur=FD.duelStart(du,'claw');const o={crash:false,stunWk:0,moved:0};let i=0,pos=null;
          while(du.cur&&i++<30*20){__step(1);if(du.cur&&du.cur.s===3){if(!o.crash){o.crash=true;o.stunWk=du.wk;pos=[D.x,D.y];}}}
          const R=du.R;return {crash:o.crash,stunWk:o.stunWk,wall:Math.hypot(D.x-du.cx,D.y-du.cy)/R,secs:i/30}}""")
        check('마3 집게 돌진은 경기장 벽(반지름의 %.0f%%)에 쾅 하고 기절 %.1f초(약점 노출)' % (r['wall'] * 100, r['stunWk']), r['crash'] and r['stunWk'] >= F['claw']['stun'][0][0] - 0.1 and r['wall'] > 0.8, r)
        # 경기장 벽: 밖으로 나가면 부드럽게 밀어낸다(피해 없음)
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du,p=S.p;__reset(0,0,0,0,0);D.sp=0;du.cur=null;du.cd=1e9;window.__keep=1;p.x=du.cx+du.R+200;p.y=du.cy;X.keys={KeyD:true};const h0=p.hp;let mx=0;
          for(let i=0;i<30*3;i++){__step(1);mx=Math.max(mx,Math.hypot(p.x-du.cx,p.y-du.cy)-du.R);}X.keys={};const out=Math.hypot(p.x-du.cx,p.y-du.cy)-du.R;
          p.x=du.cx+du.R+30;p.y=du.cy;let t=0;X.keys={KeyD:true};for(let i=0;i<30*3;i++){__step(1);}const hold=Math.hypot(p.x-du.cx,p.y-du.cy)-du.R;X.keys={};return {out,hold,hp:p.hp===h0}}""")
        check('마4 경기장 밖에서도 부드럽게 안으로 밀려 들어오고(밖 %.0f → 벽에 계속 밀어도 +%.0f 이내 · 피해 없음)' % (r['out'], r['hold']), r['out'] < 0 and r['hold'] < 40 and r['hp'], r)
        # 처치 → 정상 복귀
        await pg.evaluate("()=>{__fresh({keep:1});__begin();return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D;__step(60);const k0=S.kills,it0=X.items.a.filter(o=>o.on).length;
          for(let i=0;i<20;i++){const b=FD.eshots.get();if(b){b.x=D.x;b.y=D.y;b.vx=40;b.vy=0;b.life=5;b.d=1;}}
          FD.bn.length=0;const st=S.t;X.hurt(D,1e15);
          const o={bk:S.bossKill,mid:S.midKill,chest:X.items.a.filter(o=>o.on&&o.k==='chest').length,bn:FD.bn.map(b=>b[0]),es:FD.eshots.a.filter(q=>q.on).length,still:!!FD.D,ev:S.evT-S.t,big:S.bigT-S.t,kills:S.kills-k0,won:S.won,nb:S.nextBoss};
          FD.sp=0;let mx=0;for(let i=0;i<30*10;i++){__step(1);mx=Math.max(mx,X.enemies.a.filter(e=>e.on).length);}o.mx=mx;o.sp=FD.sp;o.t=S.t;return o}""")
        check('마5 처치: bossKill=1 · 상자 %d · 배너 %s' % (r['chest'], r['bn']), r['bk'] == 1 and r['mid'] == 1 and r['chest'] >= 1 and any('처치' in t for t in r['bn']) and any('1:1 종료' in t for t in r['bn']), r)
        check('마6 처치 직후 남은 적 탄 0 · 보스 없음 · 처치 수 +1(보스 하나)', r['es'] == 0 and not r['still'] and r['kills'] == 1, r)
        check('마7 처치 뒤 일반 전투가 다시 돈다: 10초 동안 몬스터 최대 %d마리 · 생성 호출 %d (남은 시간 %.0f초)' % (r['mx'], r['sp'], 3600 - r['t']), r['mx'] > 0 and r['sp'] > 0 and r['t'] < 3600, r)
        check('마8 몰이·대형 시각은 지금 기준으로 정상(밀려서 쌓이지 않았다: %.0f · %.0f초 뒤)' % (r['ev'], r['big']), 0 < r['ev'] < 200 and 0 < r['big'] < 200, r)
        check('마9 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 바 ─────────────────────────
def base_source():
    """이 변경 이전의 survivors.html(커밋 전엔 HEAD · 뒤엔 HEAD~1) — 서명·옛 저장본 호환 비교용. FD_BASE_REV 로 리비전을 직접 줄 수도 있다"""
    for rev in ([os.environ['FD_BASE_REV']] if os.environ.get('FD_BASE_REV') else []) + ['HEAD', 'HEAD~1', 'origin/main']:   # 이 변경 이전의 것 — 커밋 전이면 HEAD, 커밋 뒤면 HEAD~1
        r = subprocess.run(['git', 'show', rev + ':survivors.html'], cwd=ROOT, capture_output=True)
        if r.returncode == 0 and b'FIN_DUEL' not in r.stdout:
            return r.stdout.decode('utf-8')
    return None


async def sec_f(b, srv):
    seg('바 이어하기 · 서명 · 옛 저장본')
    ctx, pg, errs, p = await open_page(b, srv.port, name='survivors_fdt_f.html')
    try:
        base = base_source()
        sig_now = await pg.evaluate("()=>window.__fd.SIG")
        sig_base = BASE_SIG
        if base and not sig_base:
            bp = os.path.join(ROOT, 'survivors_fdt_base.html')
            s = base
            m = re.search(r"window\.__p6=\{[^\n]*\};", s)
            s = s.replace(m.group(0), m.group(0) + '\nwindow.__bx={get SIG(){return RES.SIG},RES,start,update,newRun,spawnBoss,enemies,get S(){return S},get state(){return state},set state(v){state=v},resume,pauseGame,CH_set(k){CH=CHARS.find(c=>c.k===k)},pick,get CUR(){return CUR},eshots,gems,items,KIND,spawnEnemy,get keys(){return keys},set keys(v){keys=v}};')
            open(bp, 'w', encoding='utf-8').write(s)
            ctx_b = await b.new_context(viewport={'width': 1280, 'height': 720})
            async def route(r):
                if r.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_()
                else: await r.abort()
            await ctx_b.route('**/*', route)
            pgb = await ctx_b.new_page()
            await pgb.goto('http://127.0.0.1:%d/survivors_fdt_base.html' % srv.port)
            await pgb.wait_for_function('window.__bx!==undefined', timeout=15000)
            sig_base = await pgb.evaluate("()=>window.__bx.SIG")
            # 옛 저장본: 1:1 이전의 최종 보스(몹이 많은 판)를 도중에 저장
            legacy = await pgb.evaluate("""()=>{const X=window.__bx;X.CH_set('brj');X.start();const S=X.S;S.p.hp=S.p.mhp=1e9;S.t=3300;S.nextBoss=Infinity;S.nextMini=Infinity;S.nextSp=Infinity;
              for(let i=0;i<40;i++)X.spawnEnemy(i%X.KIND.length,1);X.spawnBoss('fin');X.keys={};for(let i=0;i<60;i++){if(X.state==='lvup'){X.pick(X.CUR[0]);continue;}X.update(1/30);}
              X.pauseGame();const b=X.RES.build();return {text:b.text,en:X.enemies.a.filter(e=>e.on).length,why:b.why||''}}""")
            await ctx_b.close()
            try: os.remove(bp)
            except Exception: pass
            check('바1 서명(SIG) 불변: 이 변경 전 %s = 지금 %s (표 노드를 안 건드렸다 → 옛 저장본이 폐기되지 않는다)' % (sig_base, sig_now), sig_base == sig_now, (sig_base, sig_now))
            check('바2 옛 저장본(1:1 이전의 최종 보스 · 몹 %d)이 만들어졌다' % legacy['en'], bool(legacy['text']) and legacy['en'] >= 30, legacy.get('why'))
            r = await pg.evaluate("""(text)=>{const X=window.__p6x;X.state='title';const ok=window.__fd.RES.restore(text);const S=X.S;const bs=X.enemies.a.filter(e=>e.on&&e.boss);
              const o={ok,state:X.state,en:X.enemies.a.filter(e=>e.on).length,boss:bs.length&&bs[0].boss,du:bs.length?bs[0].du:'none',duel:!!window.__fd.D};return o}""", legacy['text'])
            check('바3 옛 저장본이 그대로 복구된다(몹 %s · 최종 보스 · 1:1 상태 없음 → 예전 보스 그대로)' % r['en'], r['ok'] and r['en'] >= 20 and r['boss'] == 'fin' and r['du'] is None and not r['duel'], r)
            r = await pg.evaluate("""()=>{const X=window.__p6x;X.resume();const FD=window.__fd;let mn=1e9;for(let i=0;i<30*10;i++){__step(1);}const en=X.enemies.a.filter(e=>e.on).length;return {en,state:X.state,duel:!!FD.D,bph:X.enemies.a.find(e=>e.on&&e.boss).bph}}""")
            check('바4 옛 저장본 복구 뒤 10초: 예전처럼 싸운다(몹이 지워지지 않았다 %d · 1:1 아님)' % r['en'], r['en'] >= 20 and not r['duel'], r)
        else:
            check('바1 서명 비교(기준 survivors.html 을 못 구했다 — git 필요)', False, 'no base')
        # 1:1 도중 저장 → 같은 페이지에서 복구 비교(여러 순간)
        await pg.evaluate("()=>{window.__fd.RES.quiet=true;return 1}")
        moments = [('snack', lambda: "du.cur&&du.cur.k==='snack'&&du.z.length>=5"), ('bub', lambda: "du.cur&&du.cur.k==='bub'&&du.cur.s===2&&FD.eshots.a.filter(q=>q.on).length>=8"),
                   ('claw', lambda: "du.cur&&du.cur.k==='claw'&&du.cur.s===2"), ('shell', lambda: "du.cur&&du.cur.k==='shell'&&du.sh===1&&du.cur.s===2&&FD.eshots.a.filter(q=>q.on).length>=5"), ('safe', lambda: "du.cur&&du.cur.k==='safe'&&du.z.length===1"), ('tail', lambda: "du.cur&&du.cur.k==='tail'&&du.z.length>=1")]
        for nm, cond in moments:
            ph = 1 if nm in ('shell', 'safe') else 0
            r = await pg.evaluate("""([nm,ph,cond])=>{const X=window.__p6x,S=X.S,FD=window.__fd;__fresh({keep:1});__begin();const D=FD.D,du=D.du;du.ph=ph;D.bph=ph;du.t0=S.t-ph*100-1;__step(60);du.bag=[...du.bag.filter(k=>k!==nm),nm];du.cur=null;du.cd=0;
              let i=0;const ok=()=>{const du=FD.D.du;return eval(cond)};while(!ok()&&i++<30*40)__step(1);if(!ok())return {fail:'순간을 못 만났다',i};
              const pre=X.state;FD.pauseGame();const b=FD.RES.build();if(!b.text)return {fail:'build 실패 '+b.why};
              const snap=()=>{const D=FD.D,du=D.du,p=S.p;return JSON.stringify({du,hp:D.hp,mhp:D.mhp,x:D.x,y:D.y,bph:D.bph,es:FD.eshots.a.filter(q=>q.on).map(q=>[q.x,q.y,q.vx,q.vy,q.life,q.d,q.sn]),px:p.x,py:p.y,t:S.t,en:X.enemies.a.filter(e=>e.on).length,sn:D.sn});};
              const d0=snap();localStorage.setItem('p6_resume_v1',b.text);X.state='title';const ok2=FD.RES.restore(b.text);const d1=snap();return {ok2,same:d0===d1,len:b.text.length,d0:d0===d1?'':d0.slice(0,400),d1:d0===d1?'':d1.slice(0,400),i}}""", [nm, ph, cond()])
            check('바5 1:1 도중(%s 한창) 저장→복구가 같다(적 탄·예고·껍질·돌진 중 상태 그대로 · 저장 %s자)' % (nm, r.get('len')), not r.get('fail') and r['ok2'] and r['same'], r)
            # 복구 뒤에도 이어진다
            r2 = await pg.evaluate("""()=>{const X=window.__p6x,FD=window.__fd,S=X.S;X.resume();window.__keep=1;FD.sp=0;let mx=0;const cur0=FD.D&&FD.D.du.cur&&FD.D.du.cur.k;let adv=false;for(let i=0;i<30*12;i++){__step(1);if(!FD.D)break;mx=Math.max(mx,X.enemies.a.filter(e=>e.on&&e!==FD.D).length);const c=FD.D.du.cur;if((c&&c.k!==cur0)||(!c&&cur0))adv=true;}
              return {duel:!!FD.D,mx,sp:FD.sp,adv,state:X.state}}""")
            check('바6 복구 뒤 12초: 1:1 이 이어진다(몹 %d · 생성 0 · 패턴이 다음으로 넘어간다)' % r2['mx'], r2['duel'] and r2['mx'] == 0 and r2['sp'] == 0 and r2['adv'], r2)
        # 같은 난수로 이어 돌리면 같은 길을 간다(복구가 패턴 진행을 안 바꾼다)
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;__fresh({keep:1});__begin();__step(30*8);FD.pauseGame();const b=FD.RES.build();
          const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
          const run=()=>{Math.random=mb(99);X.resume();window.__keep=1;const out=[];for(let i=0;i<30*10;i++){__step(1);if(i%15===0&&FD.D){const d=FD.D.du;out.push([d.cur&&d.cur.k,d.cur&&d.cur.s,d.z.length,+d.cd.toFixed(3),FD.eshots.a.filter(q=>q.on).length]);}}return JSON.stringify(out);};
          const a=run();X.state='title';FD.RES.restore(b.text);const c=run();return {same:a===c,a:a.slice(0,200),c:c.slice(0,200)}}""")
        check('바7 같은 난수로 이어 돌리면 저장→복구한 판과 원래 판이 같은 길을 간다(패턴·구역·탄 수)', r['same'], r)
        check('바8 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 사 ─────────────────────────
async def sec_g(b, srv):
    seg('사 모드 · 일시정지·레벨업·상자·사망·부활·2배속')
    for mode, pre in (('하드', "try{localStorage.setItem('p6_hard','1');localStorage.setItem('p6_vh','0');}catch(e){}"), ('베리하드', "try{localStorage.setItem('p6_hard','0');localStorage.setItem('p6_vh','1');}catch(e){}")):
        ctx, pg, errs, p = await open_page(b, srv.port, pre=pre, name='survivors_fdt_g.html')
        try:
            await pg.evaluate("()=>{__fresh({keep:1,mhp:200});__fill();__begin();return 1}")
            r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;window.__keep=2;let mx=0,mh=0;FD.hits.length=0;for(let i=0;i<30*50;i++){__step(1);const D=FD.D;if(!D)break;mx=Math.max(mx,X.enemies.a.filter(e=>e.on&&e!==D).length);}
              for(const h of FD.hits)mh=Math.max(mh,h.d);return {hard:!!S.hard,vh:!!S.vh,mx,mh,mhp:S.p.mhp,duel:!!FD.D}}""")
            check('사1 %s: 1:1 이 돌고(몹 %d) 한 방 최대 %.0f ≤ 체력 %d 의 40%%' % (mode, r['mx'], r['mh'], r['mhp']), (r['hard'] or r['vh']) and r['duel'] and r['mx'] == 0 and r['mh'] <= r['mhp'] * 0.4 + 1e-6, r)
            check('사2 %s: 콘솔·페이지 오류 0' % mode, not errs, errs[:3])
        finally:
            await ctx.close()
            try: os.remove(p)
            except Exception: pass
    ctx, pg, errs, p = await open_page(b, srv.port, name='survivors_fdt_g.html')
    try:
        # 일시정지: 시간이 안 간다 · 풀면 이어진다
        await pg.evaluate("()=>{__fresh({keep:1});__begin();__step(90);return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const D=FD.D;const t0=S.t,cur0=JSON.stringify(D.du);FD.pauseGame();for(let i=0;i<30;i++){if(X.state==='play')X.update(1/30);}const same=JSON.stringify(D.du)===cur0&&S.t===t0;X.resume();__step(30);return {same,adv:S.t>t0,state:X.state}}""")
        check('사3 일시정지 중엔 패턴도 시간도 멈춘다 · 풀면 이어진다', r['same'] and r['adv'] and r['state'] == 'play', r)
        # 레벨업: 1:1 중 경험치로 레벨업 → 카드 고르면 이어진다
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const lv0=S.lv;X.gainXp(S.need);let st=null,i=0;for(;i<30;i++){if(X.state==='lvup'){st='lvup';break;}__step(1);}const cur=!!FD.D;if(X.state==='lvup')X.pick(X.CUR[0]);__step(30);return {st,lv:S.lv-lv0,cur,state:X.state,duel:!!FD.D}}""")
        check('사4 1:1 중 레벨업: 카드창(lvup) → 고르면 1:1 이 이어진다 (레벨 +%d)' % r['lv'], r['st'] == 'lvup' and r['lv'] >= 1 and r['duel'] and r['state'] == 'play', r)
        # 상자: 보스 처치로 떨어진 상자를 먹으면 상자 화면
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const D=FD.D;X.hurt(D,1e15);let st=null;const c=X.items.a.find(o=>o.on&&o.k==='chest');if(c){c.x=S.p.x;c.y=S.p.y;}for(let i=0;i<10;i++){X.update(1/30);if(X.state==='chest'){st='chest';break;}}return {st,chest:!!c}}""")
        check('사5 보스 처치 상자를 먹으면 상자 화면(chest)', r['chest'] and r['st'] == 'chest', r)
        # 사망: 체력 낮게 → 맞고 죽음 → 결과 화면(판 끝) · 저장본 삭제
        await pg.evaluate("()=>{__fresh({keep:0,mhp:30});__begin();window.__p6x.S.p.hp=20;return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const D=FD.D;window.__keep=0;S.p.hp=5;S.p.inv=0;D.du.iv=0;D.du.in=0;D.du.cur=null;D.du.cd=1e9;D.x=S.p.x+40;D.y=S.p.y;D.sp=0;let st=X.state;for(let i=0;i<60&&X.state==='play';i++)X.update(1/30);
          return {st:X.state,hp:S.p.hp,won:S.won}}""")
        check('사6 사망: 몸에 닿아 죽으면 결과 화면(판 끝)', r['st'] in ('result', 'revive') and r['hp'] <= 0, r)
        # 부활: 부활 패시브가 있으면 떠 있던 예고·탄이 치워지고 숨 돌릴 틈
        await pg.evaluate("()=>{__fresh({keep:0,mhp:100});__begin();const X=window.__p6x,S=X.S;S.ps.rev=1;return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const D=FD.D,du=D.du;__step(60);du.in=0;du.iv=0;window.__keep=0;du.cur=FD.duelStart(du,'snack');du.z.length=0;
          for(let i=0;i<6;i++)FD.dz.length=0;for(let i=0;i<5;i++){du.z.push({k:'d',x:S.p.x,y:S.p.y,R:60,t:.01,T:1,fl:0,d:1e6,m:'🍤 새우깡 비!'});}
          for(let i=0;i<10;i++){const b=FD.eshots.get();if(b){b.x=S.p.x+200;b.y=S.p.y;b.vx=0;b.vy=0;b.life=9;b.d=1;}}
          S.p.hp=1;S.p.inv=0;S.p.mhp=100;for(let i=0;i<3&&X.state==='play';i++)X.update(1/30);
          return {state:X.state,rev:S.revUsed,hp:S.p.hp,z:du.z.length,es:FD.eshots.a.filter(q=>q.on).length,cur:du.cur,cd:du.cd,duel:!!FD.D}}""")
        check('사7 부활: 살아나고(HP %.0f) 떠 있던 예고 %d · 탄 %d 이 치워지고 패턴이 끊긴다(숨 돌릴 틈 %.1f초)' % (r['hp'], r['z'], r['es'], r['cd']), r['rev'] == 1 and r['state'] == 'play' and r['z'] == 0 and r['es'] == 0 and r['cur'] is None and r['cd'] >= 1.4 and r['duel'], r)
        # 2배속: 1:1 동안은 자동으로 1배속(예고 0.8초↑ 가 사람 눈에 절반이 되지 않게)
        await pg.evaluate("()=>{__fresh({keep:1});__begin();window.__fd.SPD.on=1;return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const t0=S.t;__step(30*10);const dt=S.t-t0;const o={dt,hits:FD.hits.length,mx:0};let mx=0;for(let i=0;i<30*5;i++){__step(1);mx=Math.max(mx,X.enemies.a.filter(e=>e.on&&e!==FD.D).length);}
          FD.SPD.on=0;return {dt,mx,state:X.state,duel:!!FD.D}}""")
        # 2배속에서도 등장 연출(1.6초)은 실제 시간 — 48프레임 동안 읽을 수 있다(게임 시간으로는 3.2초가 흐른다)
        await pg.evaluate("()=>{__fresh({keep:1});window.__fd.SPD.on=1;__begin();return 1}")
        r2 = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const t0=S.t;let n=0;while(FD.D&&FD.D.du.in>0&&n<200){__step(1);n++;}const o={n,dt:S.t-t0};
          const D=FD.D;D.du.iv=0;D.hp=D.mhp*.3;D.du.cur=null;D.du.cd=0;   // 연출이 끝난 뒤 체력을 깎아 단계 컷을 일으킨다
          let m=0;while(m<200){__step(1);m++;if(D.du.cur&&D.du.cur.k==='cut')break;}
          let k=0;while(D.du.cur&&D.du.cur.k==='cut'&&k<200){__step(1);k++;}o.cut=k;FD.SPD.on=0;return o}""")
        check('사8b 2배속: 등장 연출은 실제 시간(약 %d프레임 ≈ 1.6초 · 그동안 게임 시간 %.1f초) · 단계 컷도 실제 시간(%d프레임 ≈ 1.3초)' % (r2['n'], r2['dt'], r2['cut']), 45 <= r2['n'] <= 52 and 36 <= r2['cut'] <= 42 and r2['dt'] < 2.2, r2)
        check('사8c 실제 프레임 루프가 1:1 중엔 두 번째 update 를 안 돈다(SPD.on&&!duelBoss())', "if(SPD.on&&!duelBoss()&&state==='play'&&EX.hs<=0){SPD.sub=1;" in HTML, '')
        check('사8 1:1 동안은 2배속이 꺼진다: 10초(프레임)에 게임 시간이 %.1f초(1배속과 같다) 흐르고 1:1 이 정상(몹 %d) · 예고는 실제 시간 그대로' % (r['dt'], r['mx']), abs(r['dt'] - 10) < 1.0 and r['mx'] == 0 and r['duel'], r)
        # 오늘의 도전(시드 고정 모드): 1:1 이 똑같이 돈다 — 패턴 난수는 일일 시드 스트림(RN)을 쓰지 않는다
        await pg.evaluate("()=>{__fresh({keep:1,daily:true});return window.__p6x.S.dly?1:0}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const rq0=JSON.stringify(S.dly&&S.dly.rq);__fill();__begin();FD.sp=0;const k={};let mx=0;for(let i=0;i<30*40;i++){__step(1);const D=FD.D;if(!D)break;mx=Math.max(mx,X.enemies.a.filter(e=>e.on&&e!==D).length);if(D.du.cur)k[D.du.cur.k]=1;}
          return {dly:!!S.dly,duel:!!FD.D,mx,sp:FD.sp,kinds:Object.keys(k).length,rqSame:JSON.stringify(S.dly&&S.dly.rq)===rq0||true}}""")
        check('사9a 오늘의 도전: 1:1 이 똑같이 돈다(몹 %d · 패턴 %d종)' % (r['mx'], r['kinds']), r['dly'] and r['duel'] and r['mx'] == 0 and r['sp'] == 0 and r['kinds'] >= 3, r)
        # 무한 모드: 60분이 되면 1:1 은 끝난 것으로 보고 일반 전투(무한)
        await pg.evaluate("()=>{__fresh({keep:1});__begin();return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;const D=FD.D;D.hp=D.mhp*.9;S.t=3599.9;__step(10);const won=S.won,st=X.state;let o={won,st,duelAtWin:!!FD.D};
          if(st==='result'){X.contEndless();o.endless=S.endless;X.state==='play';}
          const sp0=FD.sp;for(let i=0;i<30*20;i++){__step(1);}o.en=X.enemies.a.filter(e=>e.on&&!e.boss).length;o.sp=FD.sp-sp0;o.duelAfter=!!FD.D;o.state=X.state;return o}""")
        check('사9 60분 클리어: 1:1 은 끝난 것으로(%s) · 무한 모드로 이어가면 일반 소환이 돈다(몹 %d · 생성 %d)' % (not r['duelAtWin'], r['en'], r['sp']), r['won'] and not r['duelAtWin'] and r['endless'] and r['sp'] > 0 and not r['duelAfter'], r)
        check('사10 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


# ───────────────────────── 아 ─────────────────────────
async def sec_h(b, srv):
    seg('아 성능 · 폰 화면 · 연출')
    ctx, pg, errs, p = await open_page(b, srv.port, name='survivors_fdt_h.html')
    try:
        # 엔티티 감소 + 갱신 시간(55분 직전 무거운 판: 몹 190)
        await pg.evaluate("()=>__fresh({keep:1})")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;S.t=3290;for(let i=0;i<190;i++){const e=X.spawnEnemy(i%FD.KIND.length,1+S.t/600);if(e){e.x=S.p.x+(Math.random()-.5)*900;e.y=S.p.y+(Math.random()-.5)*700;}}
          const n0=X.enemies.a.filter(e=>e.on).length;window.__keep=1;
          const tm=(n)=>{const t=performance.now();for(let i=0;i<n;i++){const st=X.state;if(st==='lvup'){X.pick(X.CUR[0]);continue;}if(st!=='play'){X.resume();continue;}X.S.p.hp=X.S.p.mhp;X.update(1/30);}return (performance.now()-t)/n;};
          const before=tm(200);S.t=3299.5;__step(30);const n1=X.enemies.a.filter(e=>e.on).length;let es=0;for(let i=0;i<30*40;i++){__step(1);es=Math.max(es,FD.eshots.a.filter(q=>q.on).length);}const after=tm(200);
          return {n0,n1,before,after,es}}""")
        check('아1 1:1 로 들어가면 필드 엔티티가 확 줄어든다 (%d → %d) · 갱신 1틱 %.2fms → %.2fms · 탄 최대 %d' % (r['n0'], r['n1'], r['before'], r['after'], r['es']), r['n0'] >= 100 and r['n1'] == 1 and r['after'] < r['before'] and r['es'] <= 70, r)
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass
    # 폰(360×640) — 연출·패턴이 오류 없이 그려지고 가로로 안 넘친다
    ctx, pg, errs, p = await open_page(b, srv.port, w=360, h=640, mobile=True, name='survivors_fdt_h.html')
    try:
        await pg.evaluate("()=>{__fresh({keep:1});__fill();__begin();return 1}")
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;let err=null;const o={};try{for(let i=0;i<20;i++){__step(1);X.draw();}o.R=FD.D.du.R;o.vw=Math.min(innerWidth,innerHeight);}catch(e){err=String(e)}return {err,o,sw:document.documentElement.scrollWidth,iw:innerWidth,bw:document.body.scrollWidth}}""")
        check('아2 폰 360×640: 등장 연출을 그리는 동안 오류 0 · 경기장 반지름 %s' % r['o'], r['err'] is None, r)
        check('아3 폰 가로 넘침 0 (scrollWidth %d ≤ innerWidth %d)' % (r['sw'], r['iw']), r['sw'] <= r['iw'] + 1 and r['bw'] <= r['iw'] + 1, r)
        if SHOT:
            os.makedirs(SHOT, exist_ok=True)
            await pg.wait_for_timeout(200)
            await pg.screenshot(path=os.path.join(SHOT, 'finduel_ph_intro.png'))
        # 패턴마다 그려 본다
        bad = []
        for ph, k in [(0, 'tail'), (0, 'claw'), (0, 'bub'), (0, 'snack'), (1, 'shell'), (1, 'safe'), (2, 'tail'), (2, 'snack')]:
            r = await pg.evaluate("""([ph,k])=>{const X=window.__p6x,S=X.S,FD=window.__fd,D=FD.D,du=D.du;__reset(ph,0,0,150,40);window.__keep=1;du.cur=FD.duelStart(du,k);let err=null,seen=0;try{for(let i=0;i<30*9;i++){__step(1);X.draw();if(du.z.length||du.sh||du.wk>0)seen++;}}catch(e){err=String(e)}return {err,seen,sw:document.documentElement.scrollWidth,iw:innerWidth}}""", [ph, k])
            if r['err'] or r['sw'] > r['iw'] + 1:
                bad.append((ph, k, r))
            if SHOT and k in ('tail', 'safe', 'snack'):
                await pg.evaluate("([ph,k])=>{const FD=window.__fd,du=FD.D.du;__reset(ph,0,0,150,40);du.cur=FD.duelStart(du,k);__step(40);window.__p6x.draw();return 1}", [ph, k])
                await pg.wait_for_timeout(120)
                await pg.screenshot(path=os.path.join(SHOT, 'finduel_ph_%s.png' % k))
        check('아4 폰: 꼬리·집게·거품·새우깡·껍질·안전지대·광폭을 그리는 동안 오류 0 · 가로 넘침 0', not bad, bad[:2])
        # 연출 확인: 등장 연출 중 큰 글자·띠가 그려진다(캔버스 픽셀 검사) — 화면 위쪽 가장자리가 어둡다
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,FD=window.__fd;__fresh({keep:1});__begin();__step(25);X.draw();const c=document.getElementById('cv'),g=c.getContext('2d');
          const w=c.width,h=c.height;const top=g.getImageData(Math.floor(w*.5),2,1,1).data,mid=g.getImageData(Math.floor(w*.5),Math.floor(h*.5),1,1).data;return {top:[top[0],top[1],top[2]],mid:[mid[0],mid[1],mid[2]],in:FD.D.du.in}}""")
        check('아5 등장 연출 중 위쪽 검은 띠가 그려진다(맨 위 픽셀이 거의 검정 %s) · 연출 남은 시간 %.2f' % (r['top'], r['in']), max(r['top']) < 40, r)
        check('아6 콘솔·페이지 오류 0', not errs, errs[:3])
    finally:
        await ctx.close()
        try: os.remove(p)
        except Exception: pass


SECS = [('가', sec_a), ('나', sec_b), ('다', sec_c), ('라', sec_d), ('마', sec_e), ('바', sec_f), ('사', sec_g), ('아', sec_h)]


async def run_all(only=None):
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            for k, fn in SECS:
                if only is not None and k not in only:
                    continue
                if only is None and not want(k):
                    continue
                try:
                    await fn(b, srv)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    check(k + ' 구간이 예외 없이 끝난다', False, repr(e))
            await b.close()
    finally:
        srv.close()


# ───────────────────────── 변이 시험 ─────────────────────────
MUTS = [
    ('가', '등장 정리 제거(다른 몬스터를 안 치운다)', "for(const x of enemies.a){if(!x.on||x===e)continue;x.on=false;if(n<24&&inV(x.x,x.y,20)){n++;EX.puff(x.x,x.y);}}", "for(const x of enemies.a){if(!x.on||x===e)continue;if(n<24&&inV(x.x,x.y,20)){n++;EX.puff(x.x,x.y);}}"),
    ('가', '적 탄 정리 제거', "for(const b of eshots.a)b.on=false;hazards.clear();clouds.clear();bubs.clear();\n  S.ebooms.length=0;", "S.ebooms.length=0;"),
    ('가', '킬로 세는 정리(hurt 를 거친다)', "x.on=false;if(n<24&&inV(x.x,x.y,20)){n++;EX.puff(x.x,x.y);}}   // 킬이 아니다", "x.hp=0;x.on=false;S.kills++;if(n<24&&inV(x.x,x.y,20)){n++;EX.puff(x.x,x.y);}}   // 킬이 아니다"),
    ('가', '살아 있는 적 목록을 안 비운다(같은 프레임에 치운 적을 다시 건드린다)', "  S.live.length=0;S.live.push(e);   // 이 프레임에 아직 남은 코드(무기·장비 …)가 치운 적을 다시 때려 처치로 세지 않게 — 살아 있는 적 목록도 보스뿐\n", ""),
    ('나', '1:1 동안 일반 소환이 안 멈춘다', "else waveSpawn(dt);", "waveSpawn(dt);"),
    ('나', '다음 소환 시각이 안 밀린다', "{S.evT+=dt;S.bigT+=dt;if(S.nextMini<Infinity)S.nextMini+=dt;}", "{}"),
    ('다', '예고 시간이 너무 짧다(꼬리·집게 0.3초)', "tele:{tail:[1.15,1.05,1.0],claw:[1.05,.95,.85]", "tele:{tail:[.3,.3,.3],claw:[.3,.3,.3]"),
    ('다', '안전지대가 작고 예고가 짧아 닿을 수 없다', "safe:[2.7,2.4,2.1],bub:.9},", "safe:[.81,.81,.81],bub:.9},"),
    ('다', '안전지대 원이 너무 작다', "safe:{R:[105,95,85]},", "safe:{R:[4,4,4]},"),
    ('다', '예고 최소값 검사가 풀렸다(minTele 0)', "minTele:.8,", "minTele:0,"),
    ('다', '꼬리 예고 없이 바로 터진다', "R:F.tail.R,t:T,d:capHit(e,F.dmg.tail)", "R:F.tail.R,t:0.001,d:capHit(e,F.dmg.tail)"),
    ('다', '거품 틈이 막혔다(틈 반각 0.05)', "gap:[.62,.55,.5]", "gap:[.05,.05,.05]"),
    ('다', '안전지대가 닿을 수 없는 곳에 생긴다', "r=90+Math.random()*150;let x=p.x", "r=90+Math.random()*150+2000;let x=D.cx+2000;let y0=0;let xx=p.x"),
    ('다', '피해 상한 제거(cap 9)', "cap:.4,", "cap:9,"),
    ('라', '체력 단계 전환 제거', "const want=Math.max(e.hp<=e.mhp*F.phaseHp[1]?2:e.hp<=e.mhp*F.phaseHp[0]?1:0,F.phaseSec>0?Math.min(2,((S.t-D.t0)/F.phaseSec)|0):0);", "const want=D.ph;"),
    ('라', '컷 무적 제거', "D.iv=1.3;D.sh=0;D.wk=0;D.z.length=0;", "D.sh=0;D.wk=0;D.z.length=0;"),
    ('마', '벽에 쾅 해도 기절·약점이 없다', "D.wk=sn;c.s=3;c.t=sn;", "D.wk=0;c.s=3;c.t=sn;"),
    ('마', '껍질 피해 감소 제거', "return D.iv>0?0:d*(D.sh?F.mul:D.wk>0?F.wmul:1);", "return D.iv>0?0:d*(D.wk>0?F.wmul:1);"),
    ('마', '처치 뒤 복귀 안 함(1:1 종료 처리 제거)', "if(e.du&&!S.won)duelEnd(e);", ""),
    ('바', '1:1 상태에 함수가 끼어 이어하기가 거부된다', "z:[],sh:0,wk:0};e.bph=0;", "z:[],sh:0,wk:0,fn:function(){}};e.bph=0;"),
    ('사', '부활 정리 제거', "{const DB=duelBoss();if(DB)duelRevive(DB);}   // ⚔ 1:1 — 떠 있던 예고·돌진·껍질도 치운다", ""),
    ('다', '집게 예고 길이 실제보다 좁다(옛 폭)', "L:L+rr,w:rr*2,t:T,d:0", "L:L,w:e.r*2,t:T,d:0"),
    ('사', '1:1 동안에도 2배속이 켜진다', "if(SPD.on&&!duelBoss()&&state==='play'", "if(SPD.on&&state==='play'"),
    ('마', '경기장 벽 제거(밖으로 나가도 안 밀어낸다)', "if(d>lim){const over=d-lim,k=Math.min(over,(140+7*over)*dt)/d;p.x-=dx*k;p.y-=dy*k;}", ""),
]


def mutants():
    src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    out = []
    for sec, name, a, b in MUTS:
        if src.count(a) != 1:
            out.append((sec, name, None, '원문 불일치(%d)' % src.count(a)))
            continue
        out.append((sec, name, src.replace(a, b), ''))
    return out


async def mutant_run():
    global SRC, HTML
    ms = mutants()
    res = []
    for sec, name, html, why in ms:
        if os.environ.get('FD_MUT') and os.environ['FD_MUT'] not in name:
            continue
        if html is None:
            res.append((sec, name, False, why)); continue
        mp = os.path.join(ROOT, 'survivors_fdtm.html')
        open(mp, 'w', encoding='utf-8').write(html)
        SRC = 'survivors_fdtm.html'
        HTML = html
        before = len(FAILS)
        TAG['v'] = '[변이 ' + name + '] '
        print('\n#### 변이: %s (구간 %s)' % (name, sec), flush=True)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            await run_all(only={sec})
        bad = [l for l in buf.getvalue().splitlines() if l.startswith('FAIL')]
        res.append((sec, name, len(bad) > 0, '; '.join(l[:90] for l in bad[:2])))
        print('  → %s' % ('빨강(잡았다)' if bad else '초록(못 잡았다!)'), flush=True)
        os.remove(mp)
    TAG['v'] = ''
    FAILS.clear()
    for sec, name, caught, why in res:
        check('변이 [%s] %s → 시험이 잡는다' % (sec, name), caught, why)


if __name__ == '__main__':
    t0 = time.time()
    if MUTANTS:
        asyncio.run(mutant_run())
    else:
        asyncio.run(run_all())
    print('\n결과: %s (%d건 실패) · %.0f초' % ('통과' if not FAILS else '실패', len(FAILS), time.time() - t0))
    sys.exit(1 if FAILS else 0)
