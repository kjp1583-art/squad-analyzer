# -*- coding: utf-8 -*-
"""survivors.html 브라우저 검증 공용 도구 — Chromium(Playwright) · 임시 사본에만 __p6x 훅을 꽂는다(원본 파일은 건드리지 않는다)."""
import os, re, sys, shutil, subprocess, time, json, threading, http.server, socketserver, functools
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('PW_CHROME') or next((p for p in [
    '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium/chrome-linux/chrome'] if os.path.exists(p)), None)
HOOK = r"""window.__p6x={get S(){return S},get state(){return state},set state(v){state=v},get CUR(){return CUR},get keys(){return keys},set keys(v){keys=v},
update,draw,pick,resume,offers,newRun,start,REL,CHARS,WEAP,TIERS,tkCalc,synCalc,SRVUNL,srvUnl,canPick,CH_set(k){CH=CHARS.find(c=>c.k===k)},get CH(){return CH},invGrant,hitP,hpMul,atkMul,bossMul,MIN,endRun,contEndless,
openChest,SYN,RN,seedOf,kstDate,applyUp,cardOf,get RSEED(){return RSEED},enemies,gems,props,items,shots,eshots,hazards,texts,RIFT_CACHE,gainXp,hurt,spawnEnemy,dailyGet,show,
LOW,sgThorns,sgTick,relTick,mapTick,WIN_T,END_T,INV_CAP,renderBoard,renderDaily,loadBoard,renderRoster,getProg,setProg,hardBest,
LINCFG:typeof LINCFG==='object'?LINCFG:null,sgFan:typeof sgFan==='function'?sgFan:null,cstat:typeof cstat==='function'?cstat:null,SGV:typeof SGV==='object'?SGV:null,U3,DL3,PS,dmgMul,   // sgFan 은 시그니처 유물 「한 장씩 줄게」 — 유물이 없는 기준선(main 사본)에서도 훅이 깨지지 않게 typeof 로 받는다
EX,FX,AU,SPX,inV,drawChamp,spawnBoss,BOSS,clouds,SHV,rgAdd,shvStart,setCap(v){INV_CAP=v},get BTAB(){return BTAB},set BTAB(v){BTAB=v},get ME(){return ME},set ME(v){ME=v}};
window.__adv=function(sec,opt){opt=opt||{};const x=window.__p6x,dt=opt.dt||1/30,n=Math.round(sec/dt);let nc=0;
 for(let i=0;i<n;i++){const st=x.state;
  if(st==='result')return 'result';
  if(st==='lvup'){x.pick(x.CUR[(opt.pickIdx||0)%x.CUR.length]);continue;}
  if(st!=='play'){x.resume();continue;}
  const S=x.S;if(opt.god){S.p.hp=S.p.mhp;}
  if(opt.move!==false){const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];}
  x.update(dt);}
 return x.state;};
"""
# 캐릭터 고유 능력(CSX · 2026-10-12)이 없던 때와 똑같은 판을 만들고 싶은 옛 시험용 — 환경변수 SV_CSX_OFF=1 이면 사본에서 능력 값을 중립으로 돌린다
#   (브장신 선빵·하리보·망무새·용조련사·배고배고 피해 몫/방어, 일단즐겨 커튼콜, 단단묵직 반격, 엄장신 연쇄, 배불배불 후렴, 앙앵 가호, 브장신 HP +20, 태웅 씩씩 상한, 또뀨 방 반경).
#   옛 시험은 브장신을 「아무 능력 없는 기준 캐릭터」로 쓰는 것이 많다 — 그 시험이 보려던 다른 규칙을 계속 지키게 한다. 능력 자체는 survivors_cabil_test.py 가 켠 채로 시험한다.
CSX_OFF_JS = r"""
(function(){if(typeof CSX==='undefined')return;
 CSX.brj.full=0;CSX.mms.tk=0;CSX.mms.base=0;CSX.tw.tk=0;CSK.dash.cd=5;CSX.hrb.run=0;CSX.hrb.tk=0;CSX.amd.x=1;CSX.ildj.cc=0;CSX.ddmj.cd=1e9;CSX.eom.n=1e9;CSX.bbb.every=1e9;CSX.yj.dmg=0;CSX.bgb.k=0;CSX.bgb.dodge=0;
 const b=CHARS.find(c=>c.k==='brj');delete b.hp;CHARS.find(c=>c.k==='tw').rage=.6;CSK.room.R=160;})();
"""
def make_copy(src='survivors.html', dst='survivors_x.html', root=ROOT, extra=''):
    s = open(os.path.join(root, src), encoding='utf-8').read()
    m = re.search(r"window\.__p6=\{[^\n]*\};", s)
    assert m, '기존 __p6 훅을 못 찾음'
    s = s.replace(m.group(0), m.group(0) + '\n' + HOOK + (CSX_OFF_JS if os.environ.get('SV_CSX_OFF') == '1' else '') + extra).replace('const INV_CAP=.80;', 'let INV_CAP=.80;')   # 임시 사본에서만 상한을 바꿔 볼 수 있게
    p = os.path.join(root, dst); open(p, 'w', encoding='utf-8').write(s); return p
class Srv:
    def __init__(self, root=ROOT, port=0):
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
        class Q(h.func):
            def log_message(self, *a): pass
        self.httpd = socketserver.ThreadingTCPServer(('127.0.0.1', port), functools.partial(Q, directory=root)); self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
    def close(self): self.httpd.shutdown()
def launch(pw, headless=True, args=None):
    return pw.chromium.launch(executable_path=CHROME, headless=headless, args=['--no-sandbox', '--enable-precise-memory-info', '--js-flags=--expose-gc'] + (args or []))
async def new_page(b, port, w=412, h=860, mock=None, page='survivors_x.html', mobile=False, throttle=None, ready='__p6x'):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    errs = []
    async def route(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:%d/' % port): await r.continue_(); return
        if mock and 'bot-hosting.cloud' in u:
            await mock(r); return
        await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/%s' % (port, page))
    await pg.wait_for_function('window.%s!==undefined' % ready, timeout=15000)
    if throttle:
        c = await ctx.new_cdp_session(pg); await c.send('Emulation.setCPUThrottlingRate', {'rate': throttle})
    return ctx, pg, errs
