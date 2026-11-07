# -*- coding: utf-8 -*-
"""👹 필드 엘리트 시험 — HUD 소환 버튼 → 지금 필드에 대형 몬스터(이름표·제한시간) → 처치하면 서버에 보고 → 등급별 득템 연출 카드.
서버는 tests/fixtures/brj_view.json 을 가짜 API 로 돌려준다. 사용: python3.13 tests/brjhunt_elite_field_test.py [등급0~4]  (playwright 필요 · 없으면 SKIP)"""
import os, subprocess, socket, time, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.join(HERE,'..')
import asyncio, json
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
CHROME=next((p for p in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome','/opt/pw-browsers/chromium/chrome-linux/chrome') if os.path.exists(p)),None)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
VIEW=json.load(open(os.path.join(HERE,'fixtures','brj_view.json'),encoding='utf-8'))
PORT=0
RAR=int(sys.argv[1]) if len(sys.argv)>1 else 4
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,headless=True,args=['--no-sandbox'])
        ctx=await b.new_context(viewport={'width':1280,'height':800}); pg=await ctx.new_page(); errs=[]; calls=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        elite={'id':'e1','stage':12,'name':'맵고추 군단','left':180,'ttl':180,'hp_mult':22}
        async def api(route):
            req=route.request; path=req.url.split('bot-hosting.cloud')[1]
            if req.method=='OPTIONS': await route.fulfill(status=204,headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'}); return
            calls.append(path); body=json.loads(json.dumps(VIEW))
            if path=='/brj/elite': body.update({'result':'ok','elite':elite}); body['view']['loot']['elite']=elite
            elif path=='/brj/elite_kill': body.update({'result':'drop','auto':False,'stage':12,'item':{'id':'i9','name':'한강 무기','emoji':'🗡','rar':RAR,'rar_name':['일반','레어','에픽','유니크','레전드'][RAR],'ilv':12,'slot':'weapon','main':['atk',88.5],'subs':[['crit',2.4,91],['hp',210,77]]}}); body['view']['loot']['elite']=None
            await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(body,ensure_ascii=False))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**',api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto('http://127.0.0.1:%d/brjhunt.html'%PORT+''); await pg.wait_for_timeout(2500)
        fails=[]
        def ok(c,m):
            print(('  ok   ' if c else '  FAIL ')+m)
            if not c: fails.append(m)
        vis=await pg.evaluate("()=>getComputedStyle(document.getElementById('eliteBtn')).display"); ok(vis!='none','게이지가 찬 상태면 HUD 에 👹 소환 버튼이 보인다')
        await pg.evaluate("()=>document.getElementById('eliteBtn').click()"); await pg.wait_for_timeout(1500)
        ok(await pg.evaluate("()=>FIELD.hasElite()") and '/brj/elite' in calls,'버튼을 누르면 서버가 게이지를 쓰고 필드에 엘리트(대형 몬스터)가 선다')
        ok(await pg.evaluate("()=>{const m=FIELD.debug.mobs().find(x=>x.big);return !!m&&m.sc>2&&m.max>FIELD.debug.D.mobHp*10;}"),'엘리트는 크고(×2 이상) 체력이 일반 몬스터의 10배 이상')
        # 엘리트 체력을 1로 → 자동 사냥이 처치
        await pg.evaluate("()=>{const m=FIELD.debug.mobs().find(x=>x.big); if(m){m.hp=1; FIELD.debug.setPos(m.x-30,m.y);} return !!m;}")
        for i in range(40):
            await pg.wait_for_timeout(400)
            if await pg.evaluate("()=>document.getElementById('dropFx').classList.contains('show')"): break
        await pg.wait_for_timeout(900)
        cls=await pg.evaluate("()=>document.getElementById('dropFx').className")
        ok(('r%d'%RAR) in cls and 'show' in cls and '/brj/elite_kill' in calls,'처치하면 서버에 보고하고 등급(r%d)에 맞는 득템 카드가 뜬다'%RAR)
        ok(not errs,'페이지 오류 0 %s'%errs[:2]); await b.close()
        print('ALL PASS' if not fails else 'FAIL %d'%len(fails)); return 1 if fails else 0
port=socket.socket(); port.bind(('127.0.0.1',0)); PORT=port.getsockname()[1]; port.close()
srv=subprocess.Popen([sys.executable,'-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: rc=asyncio.run(main())
finally: srv.terminate()
sys.exit(rc)
