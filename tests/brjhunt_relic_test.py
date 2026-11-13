# -*- coding: utf-8 -*-
"""🏺 웹 브장신 키우기 「유물」 창 시험 — 소탭 5개가 그려지고, 버튼이 맞는 경로·몸통으로 서버를 부르고, 응답대로 다시 그려지며, 쿨다운 감소가 스킬 바에 걸리고, 폰에서도 넘치지 않는다.
서버는 가짜 API(요청을 기록). 사용: python3.13 tests/brjhunt_relic_test.py  (playwright 없으면 SKIP)"""
import asyncio, json, os, socket, subprocess, sys, time, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
try:
    from playwright.async_api import async_playwright
except Exception:
    print('SKIP playwright 없음'); sys.exit(0)
CHROME = next((p for p in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', '/opt/pw-browsers/chromium/chrome-linux/chrome') if os.path.exists(p)), None)
if not CHROME: print('SKIP 크롬 없음'); sys.exit(0)
VIEW = json.load(open(os.path.join(HERE, 'fixtures', 'brj_view.json'), encoding='utf-8'))
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def relic_view(st):
    it = lambda i, key, slot, nm, em, rar, lv, stat, sn, kind, val: {'id': i, 'key': key, 'slot': slot, 'slot_name': nm, 'emoji': em, 'name': nm + '템', 'rar': rar, 'rar_name': ['희귀', '영웅', '전설', '신화'][rar], 'lv': lv, 'lock': False, 'stat': stat, 'stat_name': sn, 'kind': kind, 'val': val, 'next_val': val + 1, 'cost': 8, 'scrap': 3}
    relics = [it('r1', 'r_crown1', 'crown', '왕관', '👑', 2, 3, 'atk', '공격력', 'pct', 8.7), it('r2', 'r_amu1', 'amulet', '부적', '📿', 0, 0, 'hp', '체력', 'pct', 2.0)] + [it('m%d' % i, 'r_eye1', 'eye', '눈', '👁', 0, 0, 'acc', '명중', 'pct', 2.0) for i in range(3)]
    slots = [{'slot': s, 'name': n, 'emoji': e, 'stat': 'atk', 'stat_name': '공격력'} for s, n, e in (('crown', '왕관', '👑'), ('amulet', '부적', '📿'), ('shield', '방패', '🛡'), ('eye', '눈', '👁'), ('fang', '송곳니', '🦷'), ('scroll', '두루마리', '📜'))]
    uq = [{'key': k, 'emoji': '🗡', 'name': n, 'desc': '', 'star': s, 'on': k in st['uq_on'], 'fx': 'cd', 'val': 8.0, 'text': '스킬 쿨다운 8% 감소', 'base': {'atk': 6.0}, 'owned': s > 0} for k, n, s in (('g_kraken', '집중겜의 치속크라켄', 2), ('g_chi', '치와와의 경전', 0))]
    line = lambda s, n, v, g: {'stat': s, 'name': n, 'val': v, 'unit': '%', 'grade': g, 'grade_name': ['레어', '에픽', '유니크', '레전드'][g]}
    return {'coin': st['coin'], 'crystal': st['crystal'], 'dust': 50, 'relics': relics, 'cap': 80, 'eq': {'crown': 'r1'}, 'slots': slots, 'rarities': [{'name': '희귀', 'p': 60.0}, {'name': '영웅', 'p': 30.0}],
            'box': {'cost': 20, 'n': 3, 'pity': 3, 'pity_max': 30, 'upity': 3, 'upity_max': 100, 'unique_p': 0.5},
            'abi': {'unlock': 2, 'max': 3, 'lines': [line('atk', '공격력', 5.0, 1), line('gold', '골드 획득', 3.0, 0)], 'lock': [False, False], 'pend': [line('hp', '체력', 7.0, 2), line('gold', '골드 획득', 3.0, 0)] if st['pend'] else None,
                    'cost': 5, 'base': 5, 'rolls': 1, 'unlock_cost': {'2': 40, '3': 120}, 'grades': [{'name': '레어', 'p': 55.0, 'mult': .35}], 'stats': [{'key': 'atk', 'name': '공격력', 'max': 10.0, 'unit': '%'}]},
            'unique': {'slots': 2, 'on': st['uq_on'], 'star_max': 5, 'star_pct': 15, 'elite_p': 0.2, 'list': uq},
            'dun': [{'key': 'relic', 'name': '유물 발굴지', 'emoji': '⛏', 'cur': 'coin', 'cur_name': '유물 주화', 'used': st['dun'], 'max': 3, 'tiers': [{'name': n, 'need': nd, 'ok': nd < 1000, 'reward': r} for n, nd, r in (('쉬움', 100, 6), ('보통', 500, 12), ('어려움', 99999, 24))]}],
            'shop': [{'key': 'box1', 'name': '유물상자 1개', 'emoji': '🎁', 'cur': 'coin', 'price': 20, 'desc': '열면 유물', 'day_left': None, 'week_left': None, 'sold_out': False}],
            'news': [], 'fx': {'cd': 20.0}, 'bonus': {'pct': {'atk': 8.7}, 'add': {}}}
async def run(b, port, vp, tag):
    st = {'coin': 100, 'crystal': 30, 'pend': True, 'uq_on': [], 'dun': 0, 'calls': []}
    def view():
        v = copy.deepcopy(VIEW); v['view']['relic'] = relic_view(st); return v
    pg = await (await b.new_context(viewport=vp)).new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    async def api(route):
        req = route.request; path = req.url.split('bot-hosting.cloud')[1]
        if req.method == 'OPTIONS': await route.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}); return
        body = view(); b_ = json.loads(req.post_data or '{}')
        if path.startswith('/brj/rl_'):
            st['calls'].append((path, {k: v for k, v in b_.items() if k != 'token'}))
            res = 'ok'
            if path == '/brj/rl_dungeon': st['dun'] += 1; st['coin'] += 6; body = view(); body.update({'got': {'coin': 6}}); res = 'win'
            elif path == '/brj/rl_abi' and b_.get('act') in ('apply', 'keep'): st['pend'] = False; body = view()
            elif path == '/brj/rl_unique': st['uq_on'] = b_.get('on', []); body = view()
            elif path == '/brj/rl_shop': st['coin'] -= 20; body = view(); body.update({'got': {'relics': [{'kind': 'relic', 'item': relic_view(st)['relics'][0], 'scrapped': False}], 'unique': [], 'dust': 0}})
            body.update({'result': res})
        await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body, ensure_ascii=False))
    await pg.route('https://hth3thmujs.apps.bot-hosting.cloud/**', api)
    await pg.route(lambda u: not (u.startswith('http://127.0.0.1') or u.startswith('data:')) and 'hth3thmujs' not in u, lambda r: r.abort())
    await pg.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'유저1',avatar:'',token:'t1',exp:Date.now()+86400000}));localStorage.setItem('sgg_dc_auto','0');")
    await pg.goto(f'http://127.0.0.1:{port}/brjhunt.html'); await pg.wait_for_timeout(2500)
    ok(await pg.evaluate("()=>!!document.querySelector('[data-tab=relic]')"), f'{tag} 하단 메뉴에 유물 아이콘')
    ok(await pg.evaluate("()=>FIELD&&FIELD.debug?true:true"), f'{tag} 사냥터 시작')
    cd = await pg.evaluate("()=>{const f=fieldSkills().active.filter(Boolean);return f.length?f[0].cd:null}")
    base = await pg.evaluate("()=>{const k=equippedActives().filter(Boolean)[0];return k?N(k.cd!=null?k.cd:k.cd_s):null}")
    ok(cd is not None and base and abs(cd - max(0.2, base * 0.8)) < 1e-6, f'{tag} 쿨다운 감소 20% 가 스킬에 걸림 ({base} → {cd})')
    await pg.evaluate("()=>document.querySelector('[data-tab=relic]').click()"); await pg.wait_for_timeout(500)
    txt = lambda: pg.evaluate("()=>document.getElementById('main').textContent")
    t = await txt(); ok('유물' in t and '착용 중인 유물' in t and '보관함' in t, f'{tag} 유물 소탭: 착용·보관함')
    ok(await pg.evaluate("()=>document.querySelectorAll('.rl-slot').length") == 6, f'{tag} 유물 칸 6개')
    ok(await pg.evaluate("()=>document.querySelectorAll('.rl-it').length") == 5, f'{tag} 보관함 5개')
    ok('합성' in t, f'{tag} 같은 칸·같은 등급 3개 → 합성 버튼')
    await pg.evaluate("()=>document.querySelector('[data-do=rlsel][data-id=r2]').click()"); await pg.wait_for_timeout(300)
    ok('강화' in await txt() and await pg.evaluate("()=>!!document.querySelector('[data-do=rlenh][data-id=r2]')"), f'{tag} 유물을 고르면 강화·장착 버튼')
    await pg.evaluate("()=>document.querySelector('[data-do=rlenh][data-id=r2]').click()"); await pg.wait_for_timeout(500)
    ok(('/brj/rl_enhance', {'id': 'r2'}) in st['calls'], f'{tag} 강화 요청 {st["calls"][-1:]}')
    await pg.evaluate("()=>document.querySelector('[data-do=rlmerge]').click()"); await pg.wait_for_timeout(500)
    ok(('/brj/rl_merge', {'slot': 'eye', 'rar': 0}) in st['calls'], f'{tag} 합성 요청')
    await pg.evaluate("()=>document.querySelector('[data-do=rlbox]').click()"); await pg.wait_for_timeout(600)
    ok(('/brj/rl_shop', {'key': 'box1'}) in st['calls'] and '방금 얻은 것' in await txt(), f'{tag} 상자 열기 → 결과 표시')
    await pg.evaluate("()=>document.querySelector('[data-do=rlsub][data-sub=abi]').click()"); await pg.wait_for_timeout(300)
    t = await txt(); ok('어빌리티' in t and '새 결과' in t and '공격력' in t, f'{tag} 어빌리티 소탭: 비교 표시')
    await pg.evaluate("()=>document.querySelector('[data-do=rlapply]').click()"); await pg.wait_for_timeout(500)
    ok(('/brj/rl_abi', {'act': 'apply'}) in st['calls'] and await pg.evaluate("()=>!document.querySelector('[data-do=rlapply]')"), f'{tag} 새 결과 적용 → 비교 창 사라짐')
    await pg.evaluate("()=>{const c=document.querySelector('[data-rlock=\"0\"]');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}))}"); await pg.wait_for_timeout(300)
    ok('🔮10' in (await txt()).replace(' ', ''), f'{tag} 한 줄 잠그면 비용 ×2 표시')
    await pg.evaluate("()=>document.querySelector('[data-do=rlroll]').click()"); await pg.wait_for_timeout(500)
    ok(('/brj/rl_abi', {'act': 'roll', 'lock': [True, False]}) in st['calls'], f'{tag} 굴리기에 잠금 배열을 보낸다')
    await pg.evaluate("()=>{[0,1].forEach(i=>{const c=document.querySelector('[data-rlock=\"'+i+'\"]');if(c&&!c.checked){c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}))}})}"); await pg.wait_for_timeout(300)
    ok(await pg.evaluate("()=>document.querySelectorAll('[data-rlock]:checked').length") < 2, f'{tag} 전부 잠글 수는 없다')
    await pg.evaluate("()=>document.querySelector('[data-do=rlsub][data-sub=uq]').click()"); await pg.wait_for_timeout(300)
    t = await txt(); ok('집중겜의 치속크라켄' in t and '치와와의 경전' in t and '쿨다운' in t, f'{tag} 고유 소탭')
    await pg.evaluate("()=>document.querySelector('[data-do=rluq][data-key=g_kraken]').click()"); await pg.wait_for_timeout(500)
    ok(('/brj/rl_unique', {'on': ['g_kraken']}) in st['calls'], f'{tag} 고유 끼기 요청')
    await pg.evaluate("()=>document.querySelector('[data-do=rlsub][data-sub=dun]').click()"); await pg.wait_for_timeout(300)
    ok('유물 발굴지' in await txt() and await pg.evaluate("()=>document.querySelectorAll('[data-do=rldun]').length") == 3, f'{tag} 던전 소탭: 난이도 3개')
    await pg.evaluate("()=>document.querySelector('[data-do=rldun][data-tier=\"0\"]').click()"); await pg.wait_for_timeout(500)
    ok(('/brj/rl_dungeon', {'dun': 'relic', 'tier': 0}) in st['calls'] and st['dun'] == 1, f'{tag} 던전 입장 요청')
    await pg.evaluate("()=>document.querySelector('[data-do=rlsub][data-sub=shop]').click()"); await pg.wait_for_timeout(300)
    ok('유물상자 1개' in await txt(), f'{tag} 상점 소탭')
    ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,w:innerWidth})")
    ok(ov['sw'] <= ov['w'] + 1, f'{tag} 가로 넘침 없음 {ov}')
    await pg.screenshot(path=f'/tmp/relic_{tag}.png')
    ok(not errs, f'{tag} 페이지 오류 0 {errs[:2]}'); await pg.close()
async def main(port):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        await run(b, port, {'width': 1280, 'height': 800}, 'PC')
        await run(b, port, {'width': 390, 'height': 780}, '폰')
        await b.close()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(main(port))
finally: srv.terminate()
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
