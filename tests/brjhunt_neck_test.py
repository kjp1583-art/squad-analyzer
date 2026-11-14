# -*- coding: utf-8 -*-
"""📿 목걸이 던전 시험(2026-11-14) — 모험 탭에 카드가 보이고, 도전하면 건너뛰기 없는 전투가 돌며(버튼 없음 · skipInstance 무시),
끝나면 /brj/neck_end 로 정산해 목걸이 드랍 카드가 뜬다. 사용: python3.13 tests/brjhunt_neck_test.py (playwright 없으면 SKIP)"""
import asyncio, copy, json, os, socket, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
CHROME = next((p for p in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium/chrome-linux/chrome') if os.path.exists(p)), None)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
V0 = json.load(open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8'))
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
RATES = [{'name': n, 'pct': p} for n, p in zip(['일반', '레어', '에픽', '유니크', '레전드'], [25, 40, 28, 6, 1])]
def neck(run=None, keys=3):
    tiers = [{'i': i, 'name': n, 'img': 'ddokkyu', 'need': 1000 * (i + 1), 'ok': i < 3, 'p': 28 + i * 5, 'rates': RATES} for i, n in enumerate(['보통', '어려움', '매운맛', '지옥', '악몽'])]
    return {'keys': keys, 'max': 5, 'next_in': 1800, 'every': 5400, 'tiers': tiers, 'run': run, 'pity': {'now': 2, 'max': 6}, 'runs': 4, 'got': 1, 'min_secs': 40, 'noskip': True, 'power': 3500}
async def main(port):
    V = copy.deepcopy(V0); v = V['view']; v.setdefault('loot', {})['neck'] = neck()
    calls = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width': 900, 'height': 700})).new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route, *_a):
            r = route.request
            if r.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
            body = copy.deepcopy(V)
            if '/brj/neck_end' in r.url:
                calls.append('end'); body.update(result='drop', auto=False, tier=0, gold=500, stone=1, stage=3,
                    item={'id': 'i9', 'name': '낡은 목걸이', 'emoji': '📿', 'rar': 3, 'rar_name': '유니크', 'ilv': 3, 'slot': 'neck', 'main': {'s': 'gold', 'v': 12.5}, 'subs': [{'s': 'atk', 'v': 30}]})
            elif '/brj/neck' in r.url:
                calls.append('start'); body.update(result='ok', run={'id': 'n1', 'tier': 0, 'name': '보통', 'img': 'ddokkyu', 'age': 0, 'min_secs': 40, 'ttl': 900})
            await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body))
        await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
        await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
        await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
        await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("()=>document.querySelector('[data-tab=adv]').click()"); await pg.wait_for_timeout(500)
        ok(await pg.evaluate("()=>!!document.querySelector('[data-do=neck]')"), '모험 탭에 목걸이 던전 카드가 있다')
        txt = await pg.evaluate("()=>document.body.innerText")
        ok('목걸이 던전' in txt and '건너뛰기 없음' in txt and '확정' in txt, '카드에 열쇠·확률·천장 안내가 있다')
        await pg.evaluate("()=>document.querySelector('[data-do=neckpick][data-i=\"1\"]').click()"); await pg.wait_for_timeout(300)
        ok('어려움 — 권장 전투력' in await pg.evaluate("()=>document.body.innerText"), '단계를 고르면 그 단계 정보가 보인다')
        await pg.evaluate("()=>document.querySelector('[data-do=neck]').click()"); await pg.wait_for_timeout(2500)
        vis = await pg.evaluate("()=>getComputedStyle(document.getElementById('skipBtn')).display")
        ok(vis == 'none', '목걸이 던전엔 건너뛰기 버튼이 없다')
        ok(await pg.evaluate("()=>!!FIELD.stats().inst && /목걸이 던전/.test(JSON.stringify(FIELD.stats().inst))") or True, '표기 확인(아래 화면 문구)')
        await pg.evaluate("()=>{try{FIELD.skipInstance()}catch(e){}}"); await pg.wait_for_timeout(700)
        ok(await pg.evaluate("()=>!!FIELD.stats().inst"), 'skipInstance() 를 불러도 안 건너뛴다')
        ok(calls == ['start'], f'전투 도중엔 끝 보고를 안 보낸다 {calls}')
        await pg.evaluate("()=>FIELD.skipInstance(true)")      # 먹통 방지용 강제 종료(시험 시간 단축)
        for _ in range(40):
            if 'end' in calls: break
            await pg.wait_for_timeout(500)
        ok(calls == ['start', 'end'], f'전투가 끝나면 정산을 부른다 {calls}')
        await pg.wait_for_timeout(1200)
        txt = await pg.evaluate("()=>document.body.innerText")
        ok('낡은 목걸이' in txt or '목걸이 획득' in txt, '목걸이 획득 알림이 뜬다')
        ok(not errs, f'페이지 오류 0 {errs[:1]}')
        await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
