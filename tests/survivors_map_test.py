# -*- coding: utf-8 -*-
"""🗺 맵 3종 시험 (2026-10-21 사장님 「흐접새우 컨텐츠 추가요소」 S-2)  사용: python3 tests/survivors_map_test.py [--base <커밋>]
   A  숲은 옛 판과 비트 동일 — BASE(이 작업 직전 커밋)와 같은 판을 18캐릭터 × 150초 돌려 지문 비교
   B  용암 — 균열 예고(피해 없음) → 장판(내가 피해) → 소멸 · 적도 장판에서 피해 · 보스는 덜 · 장판 상한 12
   C  얼음 — 가속·감속 수치(놓으면 미끄러진다 · 숲은 바로 선다) · 최고 속도는 그대로 · 방향 전환 지연
   D  선택 UI — 3택 버튼 · localStorage 기억 · 시작하면 그 맵 · 일일 도전은 숲
   E  연습 판 — 용암·얼음은 순위표 전송 안 함(안내 한 줄) · 기기 최고 기록 안 바뀜 · 숲은 그대로 전송 경로
   F  이어하기 왕복 — 용암 판 저장 → 복구해도 용암(장판은 비움) · 숲 판은 head 에 mp 가 없다
   G  폰(360폭) 가로 넘침 0 · 콘솔 오류 0
   임시 사본 survivors_mt_*.html 을 쓴다(끝나면 지운다)."""
import asyncio, sys, os, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
BASE = 'c5e91c4'
if '--base' in sys.argv: BASE = sys.argv[sys.argv.index('--base') + 1]
ROOT = H.ROOT
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:500] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
HOOK = r"""
window.__M={MAPS:typeof MAPS==='object'?MAPS:null,MAPV:typeof MAPV==='object'?MAPV:null,RES,submitRun,endRun,lsGet:typeof lsGet==='function'?lsGet:null,get BEST(){return localStorage.getItem(BK)}};
window.__fp=function(){const x=__p6x,S=x.S;let ex=0,ey=0,eh=0,n=0;for(const e of x.enemies.a)if(e.on){n++;ex+=e.x;ey+=e.y;eh+=e.hp;}
 let sh=0;for(const s of x.shots.a)if(s.on)sh++;
 return JSON.stringify([+S.t.toFixed(4),S.kills,S.lv,+S.xp.toFixed(3),+S.p.x.toFixed(3),+S.p.y.toFixed(3),+S.p.hp.toFixed(3),n,+ex.toFixed(2),+ey.toFixed(2),+eh.toFixed(2),sh]);};
window.__go=function(n,dt){dt=dt||1/30;const x=__p6x;for(let i=0;i<n;i++){const st=x.state;if(st==='result')break;
  if(st==='lvup'){x.pick(x.CUR[0]);continue;} if(st!=='play'){x.resume();continue;}
  const S=x.S;S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];x.update(dt);}return x.state;};
"""
SEEDJS = """(()=>{const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(%d);window.requestAnimationFrame=()=>0;window.cancelAnimationFrame=()=>{};window.AudioContext=undefined;window.webkitAudioContext=undefined;
 try{localStorage.setItem('p6_fx','0');}catch(e){}})();"""
async def page(b, port, name, seed=7, w=1000, h=700, seeded=True):
    ctx = await b.new_context(viewport={'width': w, 'height': h})
    await ctx.add_init_script(SEEDJS % (0x5eed0000 ^ seed) if seeded else "window.requestAnimationFrame=()=>0;window.AudioContext=undefined;")
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/%s' % (port, name))
    await pg.wait_for_function('window.__M!==undefined&&window.__p6x!==undefined', polling=50, timeout=20000)
    return ctx, pg, errs
def mk(dst, src='survivors.html', root=ROOT):
    return H.make_copy(src=src, dst=dst, root=root, extra='\n' + HOOK)

async def main():
    srv = H.Srv()
    mk('survivors_mt_new.html')
    base_src = subprocess.run(['git', 'show', BASE + ':survivors.html'], cwd=ROOT, capture_output=True).stdout.decode('utf-8')
    open(os.path.join(ROOT, 'survivors_mt_base.html'), 'w', encoding='utf-8').write(base_src)
    mk('survivors_mt_base.html', src='survivors_mt_base.html')
    async with async_playwright() as pw:
        b = await H.launch(pw)
        try:
            # ── A 숲 비트 동일 ───────────────────────────────────────────────────────────────
            chars = None
            fps = {}
            for tag, name in (('new', 'survivors_mt_new.html'), ('base', 'survivors_mt_base.html')):
                ctx, pg, errs = await page(b, srv.port, name)
                if chars is None: chars = await pg.evaluate("()=>__p6x.CHARS.filter(c=>!c.shop).map(c=>c.k)")
                out = []
                for k in chars:
                    r = await pg.evaluate("""(k)=>{const x=__p6x;x.CH_set(k);x.start();const o=[];for(let i=0;i<3;i++){__go(1500);o.push(__fp());if(__p6x.state==='result')break;}
                      if(x.state==='result'){x.show(null);} return o;}""", k)
                    out.append(r)
                    await pg.evaluate("()=>{try{__p6x.endRun(false,true);}catch(e){}}")
                    await pg.evaluate("()=>{__p6x.show('title');}")
                fps[tag] = out
                if tag == 'new': check('A 숲 판에서 콘솔 오류 0', not errs, errs[:2])
                await ctx.close()
            same = [k for k, a, c in zip(chars, fps['new'], fps['base']) if a == c]
            check('A 숲 판이 옛 판과 비트 동일 (%d/%d 캐릭터 · 150초)' % (len(same), len(chars)), len(same) == len(chars),
                  [k for k in chars if k not in same])

            ctx, pg, errs = await page(b, srv.port, 'survivors_mt_new.html')
            # ── B 용암 ────────────────────────────────────────────────────────────────────────
            r = await pg.evaluate("""()=>{const x=__p6x,M=__M.MAPS,V=__M.MAPV.lava;M.pick='lava';x.CH_set('brj');x.start();const S=x.S,p=S.p,o={cur:M.cur};
              M.sync();S.w={};
              o.hp0=p.hp;
              // 균열 하나를 내 발밑에 직접 만든다
              M.z.length=0;M.z.push({x1:p.x-200,y1:p.y,x2:p.x+200,y2:p.y,w:V.w,a:0,tk:0});
              M.nx=1e9;S.t=10;p.inv=0;
              // 예고 동안(a<pre) 피해 없음
              const dt=1/30;let hpPre=p.hp;for(let i=0;i<Math.floor(V.pre*30)-2;i++){p.hp=p.mhp;hpPre=p.hp;x.keys={};x.update(dt);if(p.hp<hpPre)break;}
              o.preHurt=p.hp<hpPre;o.aPre=M.z[0]&&M.z[0].a;
              // 장판이 켜지면 피해
              let hurt=false;for(let i=0;i<30;i++){p.hp=p.mhp;x.keys={};x.update(dt);if(p.hp<p.mhp){hurt=true;break;}}
              o.hurt=hurt;
              // 소멸
              p.x+=0;let n=0;while(M.z.length&&n<600){p.hp=p.mhp;p.inv=1;x.keys={};x.update(dt);n++;}o.gone=!M.z.length;o.life=n/30;
              // 상한
              M.z.length=0;for(let i=0;i<30;i++)M.crack();o.cap=M.z.length;
              return o;}""")
            check('B 용암 맵이 선택됨', r['cur'] == 'lava', r)
            check('B 예고(붉은 선) 동안은 피해가 없다', not r['preHurt'], r)
            check('B 장판이 켜지면 내가 피해를 입는다', r['hurt'], r)
            check('B 장판은 시간이 지나 사라진다 (남은 수명 약 3.6초 안팎)', r['gone'] and 2.5 <= r['life'] <= 4.7, r)
            check('B 장판 상한 12', r['cap'] == 12, r)
            r = await pg.evaluate("""()=>{const x=__p6x,M=__M.MAPS,V=__M.MAPV.lava;const S=x.S,p=S.p;p.x=0;p.y=0;S.w={};M.sync();
              const dt=1/30;M.z.length=0;M.z.push({x1:-300,y1:600,x2:300,y2:600,w:V.w,a:V.pre+.1,tk:0});M.nx=1e9;
              for(const e of x.enemies.a)e.on=false;
              const a=x.spawnEnemy(0,1,null,{x:0,y:600});a.hp=a.mhp=1000;
              S.t=300;const bs=x.spawnBoss('sr');bs.hp=bs.mhp=1000;a.x=-100;a.y=600;bs.x=100;bs.y=600;M.z[0].a=__M.MAPV.lava.pre+.1;M.nx=1e9;
              const far=x.spawnEnemy(0,1,null,{x:0,y:900});far.hp=far.mhp=1000;
              p.hp=p.mhp;p.inv=9;x.keys={};
              for(let i=0;i<30;i++){p.inv=9;x.update(dt);a.x=-100;a.y=600;bs.x=100;bs.y=600;far.y=900;}
              return {a:a.hp,b:bs.hp,far:far.hp,onA:a.on,hit:M.z.length};}""")
            check('B 장판 위의 적도 피해를 입는다 (일반몹)', r['a'] < 1000 * .9, r)
            check('B 보스는 일반몹보다 훨씬 덜 맞는다', r['b'] < 1000 and (1000 - r['b']) < (1000 - r['a']) * .3, r)
            check('B 장판 밖의 적은 멀쩡하다', r['far'] == 1000, r)
            # 150초 용암 판 오류 없이 + 캐릭터별 몇 개
            r = await pg.evaluate("""()=>{const x=__p6x,M=__M.MAPS;M.pick='lava';x.CH_set('brj');x.start();let mx=0,n=0;for(let i=0;i<150;i++){__go(30);mx=Math.max(mx,M.z.length);n+=M.z.length;if(x.state==='result')break;}
              return {mx,t:x.S.t,st:x.state,avg:n/150};}""")
            check('B 용암 150초 판 — 장판이 계속 생기고 12개 이하 (최대 %s)' % r['mx'], 1 <= r['mx'] <= 12 and r['t'] > 100, r)
            # ── C 얼음 ────────────────────────────────────────────────────────────────────────
            r = await pg.evaluate("""()=>{const x=__p6x,M=__M.MAPS;const run=(map)=>{M.pick=map;x.CH_set('brj');x.start();const S=x.S,p=S.p;for(const e of x.enemies.a)e.on=false;
                S.t=10;M.nx=1e9;p.x=0;p.y=0;p.inv=99;const dt=1/30,o={};
                x.keys={KeyD:true};let xs=[];for(let i=0;i<45;i++){p.inv=99;x.update(dt);xs.push(p.x);}
                o.go1=xs[2];o.go30=xs[29]-xs[28];o.full=xs[44]-xs[43];   // 가속 초반 · 최고 속도 근처(프레임당 이동)
                const x0=p.x;x.keys={};let at=null,xs2=[];for(let i=0;i<60;i++){p.inv=99;x.update(dt);xs2.push(p.x);}
                o.slide=p.x-x0;o.slide1=xs2[0]-x0;
                // 방향 전환 — 달리다가 반대로
                x.keys={KeyD:true};for(let i=0;i<45;i++){p.inv=99;x.update(dt);}const y0=p.x;x.keys={KeyA:true};let first=null;for(let i=0;i<8;i++){p.inv=99;const b=p.x;x.update(dt);if(first===null)first=p.x-b;}
                o.turn=first;o.turnPos=p.x-y0;return o;};
              return {forest:run('forest'),ice:run('ice')};}""")
            f, i = r['forest'], r['ice']
            check('C 숲은 키를 떼면 바로 선다', abs(f['slide']) < 1.0, f)
            check('C 얼음은 키를 떼면 미끄러진다 (%.0fpx)' % i['slide'], 40 < i['slide'] < 200, i)
            check('C 얼음은 가속이 느리다 (2프레임째 이동거리가 숲보다 작다)', i['go1'] < f['go1'] * .6, r)
            check('C 얼음의 최고 속도는 숲과 같다', abs(i['full'] - f['full']) / f['full'] < .06, r)
            check('C 얼음에서 방향을 바꾸면 한동안 앞으로 밀려간다 (반대로 달려도 첫 프레임은 아직 앞으로)', i['turn'] > 0 and f['turn'] < 0, r)
            # ── D 선택 UI ─────────────────────────────────────────────────────────────────────
            await pg.evaluate("()=>{__p6x.show('title');}")
            r = await pg.evaluate("""()=>{const o={};const b=[...document.querySelectorAll('#mapSel [data-map]')];o.n=b.length;o.keys=b.map(e=>e.dataset.map).join();
               o.onDefault=document.querySelector('#mapSel .on')&&document.querySelector('#mapSel .on').dataset.map;
               document.querySelector('#mapSel [data-map=lava]').click();o.pick=__M.MAPS.pick;o.ls=localStorage.getItem('p6_map');o.on=document.querySelector('#mapSel .on').dataset.map;
               document.querySelector('#mapSel [data-map=ice]').click();o.pick2=__M.MAPS.pick;
               __p6x.start();o.cur=__M.MAPS.cur;
               __p6x.show('title');__p6x.start({daily:true});o.dlyCur=__M.MAPS.cur;o.dly=!!__p6x.S.dly;
               document.querySelector('#mapSel [data-map=forest]').click();__p6x.start();o.cur3=__M.MAPS.cur;o.ls3=localStorage.getItem('p6_map');return o;}""")
            check('D 맵 3택 버튼(숲·용암·얼음)', r['n'] == 3 and r['keys'] == 'forest,lava,ice', r)
            check('D 기본은 숲', r['onDefault'] == 'forest', r)
            check('D 누르면 고른 맵이 바뀌고 localStorage 에 기억', r['pick'] == 'lava' and r['ls'] == 'lava' and r['on'] == 'lava' and r['pick2'] == 'ice', r)
            check('D 시작하면 고른 맵으로 한다 · 일일 도전은 늘 숲', r['cur'] == 'ice' and r['dlyCur'] == 'forest' and r['dly'] and r['cur3'] == 'forest', r)
            # 새로고침해도 기억
            await pg.evaluate("()=>{localStorage.setItem('p6_map','lava');}")
            await pg.reload(); await pg.wait_for_function('window.__M!==undefined', polling=50, timeout=20000)
            check('D 새로 열어도 기억한 맵이 골라져 있다', await pg.evaluate("()=>__M.MAPS.pick")=='lava')
            await pg.evaluate("()=>{localStorage.removeItem('p6_map');}")
            # ── E 연습 판 ─────────────────────────────────────────────────────────────────────
            r = await pg.evaluate("""async()=>{const x=__p6x,M=__M.MAPS;const res={};
               localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'t',exp:Date.now()+1e9,name:'x'}));
               let calls=0;const oF=window.fetch;window.fetch=function(u,o){if(String(u).indexOf('/p6/run')>=0)calls++;return Promise.resolve(new Response('{"ok":true,"rank":1,"total":1}',{status:200,headers:{'content-type':'application/json'}}));};
               const bestBefore=localStorage.getItem(__M.BEST?'p6_best_ignore':'x');
               for(const map of ['lava','ice','forest']){M.pick=map;x.CH_set('brj');x.start();const S=x.S;S.t=100;S.kills=777;
                  const b0=__M.BEST;x.endRun(false,true);await new Promise(r=>setTimeout(r,80));
                  res[map]={calls,acct:document.getElementById('rAcct').textContent,title:document.getElementById('rTitle').textContent,best:__M.BEST!==b0,bestVal:__M.BEST};x.show('title');}
               window.fetch=oF;return res;}""")
            check('E 용암 판은 서버로 기록을 보내지 않고 안내 한 줄', r['lava']['calls'] == 0 and '순위표에 안 올라가요' in r['lava']['acct'], r['lava'])
            check('E 얼음 판도 같다', r['ice']['calls'] == 0 and '순위표에 안 올라가요' in r['ice']['acct'], r['ice'])
            check('E 연습 판은 기기 최고 기록을 바꾸지 않는다', not r['lava']['best'] and not r['ice']['best'], r)
            check('E 결과 제목에 맵 이름이 붙는다', '용암' in r['lava']['title'] and '얼음' in r['ice']['title'] and '용암' not in r['forest']['title'], r)
            check('E 숲은 옛 경로 그대로(기록 전송 · 최고 기록 갱신)', r['forest']['calls'] >= 1 and r['forest']['best'] and '순위표에 안 올라가요' not in r['forest']['acct'], r['forest'])
            # ── F 이어하기 ────────────────────────────────────────────────────────────────────
            r = await pg.evaluate("""()=>{const x=__p6x,M=__M.MAPS,R=__M.RES;const o={};
               M.pick='lava';x.CH_set('brj');x.start();x.S.t=30;for(let i=0;i<5;i++)M.crack();o.zBefore=M.z.length;
               x.keys={};__go(20);
               const ok=R.save('pause');o.saved=ok;const txt=localStorage.getItem('p6_resume_v1');o.head=txt?JSON.parse(txt.slice(0,txt.indexOf('\\n'))):null;
               x.show('title');x.state='title';M.cur='forest';M.pick='forest';
               const rr=R.restore();o.restored=rr;o.cur=M.cur;o.z=M.z.length;o.card=document.getElementById('resSum')&&document.getElementById('resSum').textContent;
               return o;}""")
            check('F 용암 판 저장본 머리에 맵 종류가 실린다', r['saved'] and r['head'] and r['head'].get('mp') == 'lava', r)
            check('F 복구하면 용암 맵으로 돌아온다 (장판은 비움)', r['restored'] and r['cur'] == 'lava' and r['z'] == 0, r)
            r = await pg.evaluate("""()=>{const x=__p6x,M=__M.MAPS,R=__M.RES;M.pick='forest';x.CH_set('brj');x.start();x.S.t=30;R.save('pause');const txt=localStorage.getItem('p6_resume_v1');
               const h=txt?JSON.parse(txt.slice(0,txt.indexOf('\\n'))):null;x.show('title');x.state='title';M.cur='lava';const rr=R.restore();return {h:h&&('mp' in h),rr,cur:M.cur};}""")
            check('F 숲 판 저장본에는 mp 가 없고 복구하면 숲', r['h'] is False and r['rr'] and r['cur'] == 'forest', r)
            check('G 콘솔 오류 0', not errs, errs[:3])
            await ctx.close()
            # ── G 폰 폭 ──────────────────────────────────────────────────────────────────────
            ctx, pg, errs = await page(b, srv.port, 'survivors_mt_new.html', w=360, h=780)
            r = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,bw:document.body.scrollWidth,mp:[...document.querySelectorAll('#mapSel .mapb')].map(e=>Math.round(e.getBoundingClientRect().right))})")
            check('G 폰 360폭에서 가로 넘침 0', r['sw'] <= 360 and r['bw'] <= 360 and max(r['mp']) <= 360, r)
            await ctx.close()
        finally:
            await b.close()
    for n in ('survivors_mt_new.html', 'survivors_mt_base.html'):
        try: os.remove(os.path.join(ROOT, n))
        except Exception: pass
    print('\n' + ('전부 통과' if not FAILS else 'FAIL %d: %s' % (len(FAILS), FAILS)))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
