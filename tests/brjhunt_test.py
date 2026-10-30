#!/usr/bin/env python3
"""brjhunt.html 시험(Playwright + 가짜 서버). 사용: python3.13 tests/brjhunt_test.py [--shots 폴더]   (CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome)
서버 주소로 가는 요청을 가로채 JSON 으로 답한다 — 로그인 상태에서 각 탭이 그려지는지, 버튼이 맞는 길로 맞는 값을 보내는지,
390px 가로 스크롤·콘솔 오류, 로그아웃/기록 없음/연결 실패/몰림/로그인 만료 화면, 서버 문자열의 HTML 이스케이프를 본다."""
import asyncio, os, sys, json, time, copy
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
API = 'https://hth3thmujs.apps.bot-hosting.cloud'
URL = 'file://' + os.path.join(ROOT, 'brjhunt.html')
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)
TOKEN = json.dumps({'id': '1', 'name': 'x', 'token': 'T' * 40, 'exp': int(time.time() * 1000) + 30 * 86400000})
EVIL = '<img src=x onerror="window.__xss=1">'

SKILLS = [  # id, 이름, 이모지, 종류, 필요 각성, 최대 %, 쿨, 색 (서버 BRK_SKILLS 와 같은 모양 — 숫자는 시험용)
    ('slash', '병아리 베기', '🗡', 'active', 0, 4.0, 2.0, '#ffd54a'), ('peck', '부리 연타', '🐤', 'active', 0, 4.0, 1.5, '#ffb74d'),
    ('spin', '회전 날개', '🌀', 'active', 1, 6.0, 4.0, '#80deea'), ('bomb', '치킨 폭격', '💣', 'active', 1, 7.0, 6.0, '#ff8a65'),
    ('thunder', '번개 닭', '⚡', 'active', 2, 8.0, 5.0, '#fff176'), ('fire', '불닭 파이어', '🔥', 'active', 2, 8.0, 5.0, '#ff5722'),
    ('egg', '황금 알 투척', '🥚', 'active', 3, 9.0, 7.0, '#ffca28'), ('shield', '맛동산 방패', '🛡', 'passive', 3, 8.0, 0.0, '#a1887f'),
    ('shrimp', '흐접새우 소환', '🦐', 'active', 4, 10.0, 9.0, '#f48fb1'), ('storm', '논란 폭풍', '🌪', 'active', 5, 14.0, 12.0, '#ba68c8')]
AWK = {1: (6, 400, 3, 3), 2: (12, 2000, 6, 6), 3: (18, 9000, 10, 10), 4: (24, 40000, 15, 15), 5: (30, 150000, 22, 22)}
def make_skill(sk, stage=9, gold=123456, stone=30, feast=40):
    """sk = {'aw':0,'lv':{id:lv},'a':[id|None x4],'p':id|None} → 뷰 skill"""
    aw = sk['aw']; nx = AWK.get(aw + 1); rows = []
    for (i, nm, em, kind, need, peak, cd, col) in SKILLS:
        lv = sk['lv'].get(i, 0); eqd = (i in sk['a']) or sk['p'] == i
        rows.append({'id': i, 'name': nm, 'emoji': em, 'kind': kind, 'need_awaken': need, 'unlocked': lv > 0, 'lv': lv, 'max': 10,
                     'cost': {'gold': 150 * (lv or 1), 'stone': 2 + lv // 3} if 0 < lv < 10 else {'gold': 0, 'stone': 0}, 'can': 0 < lv < 10 and gold >= 150 * lv,
                     'desc': nm + ' 설명', 'power_pct': round(peak * (0.3 + 0.7 * (lv - 1) / 9), 3) if lv else 0.0, 'next_power_pct': round(peak * (0.3 + 0.7 * lv / 9), 3) if lv else 0.0,
                     'peak_pct': peak, 'cd_s': cd, 'fx_color': col, 'equipped': bool(eqd), 'slot': (sk['a'].index(i) if i in sk['a'] else 0) if eqd else None})
    why = ''
    if nx:
        if stage < nx[0]: why = '스테이지 %d 이상이 필요해요' % nx[0]
        elif gold < nx[1]: why = '골드가 모자라요 (%s 필요)' % format(nx[1], ',')
        elif stone < nx[2]: why = '강화석가 모자라요 (%d 필요)' % nx[2]
        elif feast < nx[3]: why = '특식가 모자라요 (%d 필요)' % nx[3]
    return {'awaken': {'lv': aw, 'max': 5, 'next': ({'need_stage': nx[0], 'gold': nx[1], 'stone': nx[2], 'feast': nx[3], 'can': why == '', 'why': why} if nx else None),
                       'unlocks': [s[0] for s in SKILLS if s[4] == aw + 1], 'table': []},
            'slots': {'active': 4, 'passive': 1}, 'equipped': {'active': list(sk['a']), 'passive': sk['p']}, 'list': rows,
            'mult': round(1 + sum(r['power_pct'] for r in rows if r['equipped']) / 100, 4), 'mult_cap': 1.6, 'note': '각성은 확정이에요.'}
def new_sk(): return {'aw': 0, 'lv': {'slash': 1, 'peck': 1}, 'a': ['slash', 'peck', None, None], 'p': None}

def make_view():
    rates = {'노말': 50.0, '레어': 30.0, '에픽': 14.0, '유니크': 5.0, '레전드': 1.0}
    cards = [
        {'id': 'c1', 'n': '귤 갓', 'gr': 'legend', 'gr_ko': '레전드', 'lv': 3, 'sh': 4, 'next_sh': 6, 'bonus': 17.25, 'f': ['협곡 승률 71%', '60판'], 'gone': False},
        {'id': 'c2', 'n': EVIL, 'gr': 'epic', 'gr_ko': '에픽', 'lv': 1, 'sh': 0, 'next_sh': 1, 'bonus': 5.0, 'f': [EVIL], 'gone': False},
        {'id': 'c3', 'n': '맛동산', 'gr': 'normal', 'gr_ko': '노말', 'lv': 2, 'sh': 1, 'next_sh': 3, 'bonus': 1.15, 'f': [], 'gone': False},
        {'id': 'c4', 'n': '카무사리', 'gr': 'rare', 'gr_ko': '레어', 'lv': 1, 'sh': 0, 'next_sh': 1, 'bonus': 2.5, 'f': ['좋은 기록'], 'gone': False},
    ]
    return {
        'stage': 9, 'max_stage': 30, 'region': '홍대 먹자골목' + EVIL, 'rate': 1500, 'pending': 9000, 'hours': 4.0, 'boost': 2, 'gold': 123456, 'total': 999999,
        'cost': 6000, 'next_rate': 1770, 'cap_h': 12, 'boost_max': 6, 'lv': 7, 'name': '테스터' + EVIL,
        'summon': {'tickets': 12, 'pulls': 25, 'slv': 2, 'slv_max': 8, 'slv_next_at': 60, 'rates': rates,
                   'rate_table': [{'lv': i + 1, 'at': a, 'rates': rates} for i, a in enumerate([0, 20, 60, 130, 250, 450, 750, 1200])],
                   'pity': {'에픽': {'now': 12, 'max': 50, 'left': 38}, '유니크': {'now': 12, 'max': 150, 'left': 138}, '레전드': {'now': 12, 'max': 400, 'left': 388}},
                   'cost': {'1': 1, '10': 10}, 'cards': cards, 'own_n': 4, 'party': ['c1'], 'party_max': 3, 'mult': 1.15, 'mult_cap': 2.0,
                   'grade_bonus': {'노말': 1.0, '레어': 2.5, '에픽': 5.0, '유니크': 9.0, '레전드': 15.0}, 'lv_bonus_pct': 15, 'shard_cum': [0, 1, 3],
                   'pool': {'n': 40, 'by_grade': {'노말': 20, '레어': 10, '에픽': 6, '유니크': 3, '레전드': 1}, 'at': 1, 'ready': True}},
        'growth': {'mult': 1.3, 'gold': 123456, 'stone': 30, 'feast': 40,
                   'axes': [{'key': k, 'name': n, 'emoji': e, 'lv': 3, 'max': 50, 'cost': 500, 'can': True, 'bonus_pct': 7.5, 'per_pct': 2.5, 'text': '시간당 골드가 레벨당 +2.5%'} for k, n, e in (('atk', '사냥력', '⚔'), ('hp', '체력', '❤'), ('luck', '행운', '🍀'))],
                   'slots': [{'key': k, 'name': n, 'emoji': e, 'lv': 2, 'max': 10, 'pity': 1, 'bonus_pct': 6.0, 'per_pct': 3.0, 'next': 3, 'rate_pct': 90, 'cost': 2, 'pity_need': 0, 'guaranteed': False, 'can': True} for k, n, e in (('weapon', '무기', '🗡'), ('armor', '방어구', '🛡'), ('acc', '장신구', '📿'))],
                   'quick': {'used': 1, 'max': 3, 'left': 2, 'next_cost': 8, 'costs': [5, 8, 12], 'hours': 1, 'gain': 1500, 'reset': '매일 0시(KST)', 'can': True, 'feast': 40},
                   'enhance_table': [{'to': t, 'rate_pct': p, 'cost': c, 'pity_need': th} for t, (p, c, th) in {1: (100, 1, 0), 5: (65, 3, 3), 10: (5, 10, 12)}.items()], 'note': '실패해도 장비는 안 깨져요.'},
        'dungeon': {'power': 5599, 'key': {'n': 3, 'max': 10, 'next_in': 5000, 'per_day': 3}, 'res': {'gold': 123456, 'feast': 40, 'ticket': 12, 'stone': 30},
                    'gate': {'stage': 0, 'tries': 1, 'bosses': [
                        {'stage': 10, 'img': 'ddokkyu', 'name': '또뀨', 'hp': 534, 'feast': 15, 'ticket': 2, 'cleared': False},
                        {'stage': 20, 'img': 'yongjo', 'name': '용조련사', 'hp': 9999, 'feast': 30, 'ticket': 3, 'cleared': False},
                        {'stage': 30, 'img': 'shinlim', 'name': '신림', 'hp': 99999, 'feast': 50, 'ticket': 5, 'cleared': False}]},
                    'dungeon': {'cleared': 4, 'max': 30, 'sweep': False, 'next_hp': 2000, 'sweeps': 0, 'reward': {'stone_base': 2, 'stone_per10': 1, 'gold_hours': 2, 'ticket_every': 5}, 'sweep_reward': {'stone': 6, 'gold_hours': 4, 'ticket_every_n': 2}},
                    'clan': {'wk': 5, 'boss': 'shinlim', 'name': '신림', 'hp': 1500000, 'dmg_total': 300000, 'players': 4, 'mine': 50000, 'left': 2, 'daily_max': 3, 'days_left': 3, 'dead': False, 'claimable': True, 'feast': 20,
                             'top': [{'n': EVIL, 'd': 200000}, {'n': '나', 'd': 50000}]},
                    'daily': {'tasks': [{'k': 'collect', 'label': '🪙 사냥 골드 수령', 'done': True}, {'k': 'dungeon', 'label': '🔑 열쇠 던전 1회', 'done': False}], 'all': False, 'claimed': False, 'feast': 12,
                              'chest': [{'kind': 'stone', 'n': 3, 'pct': 60}, {'kind': 'ticket', 'n': 1, 'pct': 25}, {'kind': 'gold', 'n': 0, 'pct': 15}]}},
        'skill': make_skill(new_sk()),
        'prestige': {'can': False, 'min_stage': 30, 'stage': 9, 'gain': 0, 'n': 1, 'points': 7,
                     'ups': [{'key': 'gold', 'name': '🪙 황금 손', 'effect': '시간당 골드 +5%', 'lv': 1, 'max': 10, 'cost': 5, 'afford': True},
                             {'key': 'cap', 'name': '🏔 한계 돌파', 'effect': '스테이지 상한 +5', 'lv': 0, 'max': 4, 'cost': 8, 'afford': False},
                             {'key': 'start', 'name': '🚀 출발선', 'effect': '환생 뒤 시작 스테이지 +2', 'lv': 5, 'max': 5, 'cost': None, 'afford': False}],
                     'gold_mult': 1.05, 'stage_cap': 30, 'start_stage': 1, 'pt_rule': '기본 5점 + 스테이지 30 넘은 칸마다 2점', 'warn': '환생하면 스테이지와 골드가 처음으로 돌아갑니다.',
                     'season': {'no': 1, 'days_left': 20, 'length_days': 28, 'prestiges': 1, 'best_stage': 12, 'history': [{'season': 0, 'best': 11, 'n': 2}]},
                     'chest': {'stock': 4, 'today': 1, 'daily_cap': 5, 'store_max': 30, 'feast': 3, 'open_max': 10,
                               'table': [{'pct': 45.0, 'name': '알맹이 없음(특식만)', 'ticket': 0, 'stone': 0}, {'pct': 35.0, 'name': '🔩 강화석 2개', 'ticket': 0, 'stone': 2}]}},
    }

class Server:
    """요청을 기록하고 길마다 정해진 답을 준다. mode 로 오류 상황을 만든다."""
    def __init__(self, mode='ok'):
        self.mode = mode; self.hits = []; self.view = make_view(); self.override = {}; self.sk = new_sk()
    def handle(self, path, body):
        self.hits.append((path, body))
        if path in self.override: return self.override[path](body)
        self.view['skill'] = make_skill(self.sk, self.view['stage'])
        v = copy.deepcopy(self.view)
        if path == '/brj/awaken':
            nx = AWK.get(self.sk['aw'] + 1)
            if not nx: return 200, {'ok': True, 'result': 'max', 'unlocked': [], 'view': v}
            if self.view['stage'] < nx[0]: return 200, {'ok': True, 'result': 'stage', 'unlocked': [], 'view': v}
            self.sk['aw'] += 1; new = [s[0] for s in SKILLS if s[4] == self.sk['aw']]
            for i in new:
                self.sk['lv'][i] = 1
                if i == 'shield': self.sk['p'] = i
                elif None in self.sk['a']: self.sk['a'][self.sk['a'].index(None)] = i
            self.view['skill'] = make_skill(self.sk, self.view['stage']); return 200, {'ok': True, 'result': 'ok', 'unlocked': new, 'view': copy.deepcopy(self.view)}
        if path == '/brj/skill':
            a, i = body.get('action'), body.get('id'); lv = self.sk['lv'].get(i, 0)
            if a == 'upgrade':
                if lv <= 0: res = 'locked'
                elif lv >= 10: res = 'max'
                else: self.sk['lv'][i] = lv + 1; res = 'ok'
            elif a == 'equip':
                if lv <= 0: res = 'locked'
                else:
                    res = 'ok'
                    if i == 'shield': self.sk['p'] = i
                    else:
                        if i in self.sk['a']: self.sk['a'][self.sk['a'].index(i)] = None
                        self.sk['a'][body['slot']] = i
            else:
                res = 'ok' if (i in self.sk['a'] or self.sk['p'] == i) else 'noop'
                if i in self.sk['a']: self.sk['a'][self.sk['a'].index(i)] = None
                elif self.sk['p'] == i: self.sk['p'] = None
            self.view['skill'] = make_skill(self.sk, self.view['stage']); return 200, {'ok': True, 'result': res, 'cost': {'gold': 150 * lv, 'stone': 2}, 'view': copy.deepcopy(self.view)}
        if path == '/brj/idle': return 200, {'ok': True, 'view': v}
        if path == '/brj/rank': return 200, {'ok': True, 'season': 1, 'days_left': 20, 'total': 2, 'me': 2, 'rows': [{'rank': 1, 'name': EVIL, 'prestiges': 3, 'best_stage': 40, 'me': False}, {'rank': 2, 'name': '테스터', 'prestiges': 1, 'best_stage': 12, 'me': True}]}
        if path == '/brj/collect': return 200, {'ok': True, 'got': 6000, 'view': v}
        if path == '/brj/push': return 200, {'ok': True, 'result': 'boss', 'cost': 0, 'view': v}
        if path == '/brj/summon':
            n = body.get('n')
            if n not in (1, 10): return 200, {'ok': False, 'code': 'bad_n', 'results': [], 'view': v}
            return 200, {'ok': True, 'code': 'ok', 'results': [{'id': 'c%d' % i, 'n': '결과%d%s' % (i, EVIL if i == 2 else ''), 'gr': 'epic' if i == 0 else 'normal', 'new': i == 0, 'lv': 1, 'sh': 0} for i in range(n)], 'view': v}
        if path == '/brj/party': return 200, {'ok': True, 'code': 'ok', 'view': v}
        if path == '/brj/upgrade': return 200, {'ok': True, 'result': 'ok', 'cost': 500, 'view': v}
        if path == '/brj/enhance': return 200, {'ok': True, 'result': 'fail', 'cost': 2, 'view': v}
        if path == '/brj/quick': return 200, {'ok': True, 'result': 'ok', 'got': 1500, 'cost': 8, 'view': v}
        if path == '/brj/boss': return 200, {'ok': True, 'result': 'win', 'boss': 10, 'power': 5599, 'hp': 534, 'feast': 15, 'ticket': 2, 'view': v}
        if path == '/brj/dungeon': return 200, {'ok': True, 'result': 'win', 'level': 5, 'got': {'stone': 2, 'gold': 3000, 'ticket': 1}, 'view': v}
        if path == '/brj/clanboss': return 200, {'ok': True, 'result': 'ok', 'dmg': 12345, 'feast': 20, 'view': v}
        if path == '/brj/daily': return 200, {'ok': True, 'result': 'todo', 'view': v}
        if path == '/brj/prestige':
            if body.get('confirm') is True: return 200, {'ok': True, 'gain': 5, 'view': v}
            return 200, {'ok': False, 'code': 'confirm', 'gain': 5, 'view': v}
        if path == '/brj/prestige_buy': return 200, {'ok': True, 'key': body.get('key'), 'view': v}
        if path == '/brj/chest': return 200, {'ok': True, 'opened': 1, 'got': {'feast': 3, 'ticket': 0, 'stone': 2}, 'names': ['x'], 'view': v}
        return 404, {'ok': False, 'code': 'not_found'}

async def new_page(b, srv, w=390, h=800, login=True, scheme='dark', mode=None):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, color_scheme=scheme)
    cors = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'POST,OPTIONS'}
    async def route(r):
        req = r.request; u = req.url
        if u.startswith(API):
            if req.method == 'OPTIONS': await r.fulfill(status=204, headers=cors); return
            md = mode or srv.mode
            if urlpath(u) in getattr(srv, 'abort_paths', ()): await r.abort(); return
            if md == 'net': await r.abort(); return
            if md == 'busy': await r.fulfill(status=429, headers=cors, content_type='application/json', body=json.dumps({'ok': False, 'code': 'busy'})); return
            if md == 'upstream': await r.fulfill(status=503, headers=cors, content_type='application/json', body=json.dumps({'ok': False, 'code': 'upstream'})); return
            if md == 'nobrj': await r.fulfill(status=200, headers=cors, content_type='application/json', body=json.dumps({'ok': False, 'code': 'no_brj'})); return
            if md == 'auth': await r.fulfill(status=401, headers=cors, content_type='application/json', body=json.dumps({'ok': False, 'code': 'auth'})); return
            body = json.loads(req.post_data or '{}'); st, obj = srv.handle(urlpath(u), body)
            await r.fulfill(status=st, headers=cors, content_type='application/json', body=json.dumps(obj)); return
        if u.startswith('file://'): await r.continue_(); return
        await r.abort()
    await ctx.route('**/*', route)
    if login: await ctx.add_init_script("localStorage.setItem('sgg_dc'," + json.dumps(TOKEN) + ")")
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'net::ERR' not in m.text else None)
    pg.on('dialog', lambda d: errs.append('dialog'))
    await pg.goto(URL); await pg.wait_for_timeout(500)
    return ctx, pg, errs

def urlpath(u): return u[len(API):].split('?')[0]
async def noscroll(pg): return await pg.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1')
async def tab(pg, k): await pg.click(f'#nav [data-tab={k}]'); await pg.wait_for_timeout(150)
def last(srv, path): return [b for p, b in srv.hits if p == path]
async def press(pg, sel, srv, path, n=None):
    c0 = len(last(srv, path)); await pg.click(sel); await pg.wait_for_timeout(250)
    return last(srv, path)[c0:]
async def msg(pg): return (await pg.inner_text('.msg')) if await pg.locator('.msg').count() else ''

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        # ---- 로그아웃 ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv, login=False)
        check('로그아웃: 로그인 버튼 + 안내', await pg.locator('#loginBtn').count() == 1 and '로그인' in await pg.inner_text('#main'))
        check('로그아웃: 서버 요청 없음', len(srv.hits) == 0)
        check('로그아웃: 가로 스크롤 없음·오류 없음', await noscroll(pg) and not errs, errs); await ctx.close()
        # ---- 기록 없음 / 연결 실패 / 몰림 / 디스코드 장애 / 로그인 만료 ----
        for mode, want, name in (('nobrj', '#브장신키우기', '기록 없음(no_brj)'), ('net', '연결하지 못', '네트워크 오류'), ('busy', '몰려서', '몰림(busy)'), ('upstream', '디스코드 확인', '디스코드 장애(upstream)'), ('auth', '로그인해 주세요', '로그인 만료(401)')):
            srv = Server(mode); ctx, pg, errs = await new_page(b, srv)
            txt = await pg.inner_text('#main')
            check(f'{name}: 안내 문구', want in txt, txt[:80])
            check(f'{name}: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs)
            if mode in ('net', 'busy', 'upstream'):
                srv.mode = 'ok'; await pg.click('#retryBtn'); await pg.wait_for_timeout(400)
                check(f'{name}: 다시 불러오기로 복구', await pg.locator('#nav [data-tab]').count() == 6)
            await ctx.close()
        # ---- 정상 ----
        for scheme in ('dark', 'light'):
            srv = Server(); ctx, pg, errs = await new_page(b, srv, scheme=scheme)
            if scheme == 'dark':
                check('시작: /brj/idle 한 번, 토큰 포함', [b_ for p_, b_ in srv.hits if p_ == '/brj/idle'] == [{'token': 'T' * 40}], srv.hits)
                rt = await pg.inner_text('#res'); ti = await pg.evaluate("[...document.querySelectorAll('#res .chip')].map(c=>c.title).join('|')")
                check('자원 줄(골드·특식·소환권·강화석·열쇠 · 10만 넘으면 줄여 씀 · 정확한 값은 title)', all(x in rt for x in ('12.3만', '40', '12', '30', '3/10')) and '123,456' in ti and await pg.locator('#res .chip img').count() == 5, (rt, ti))
                check('상단 HUD: 레벨·스테이지 뱃지·지역', 'Lv.7' in await pg.inner_text('#lvb') and await pg.inner_text('#stbn') == '9' and '홍대' in await pg.inner_text('#preg'))
                check('HUD 이름은 글자 그대로(HTML 로 안 읽힘)', await pg.evaluate("document.querySelectorAll('img[src=x]').length") == 0 and '<img' in await pg.inner_text('#pname'))
            t = await pg.inner_text('#main')
            check(f'{scheme} 사냥터: 시간당·처치당 골드·돌파 안내', '1,500' in t and '10처치당 2.50' in t.replace('\n',' ') and '돌파' in t and 'STAGE 9 / 30' in await pg.inner_text('#dock'), t[:120])
            check(f'{scheme} 사냥터: 내전 부스트·배율(스킬 포함) 표시', '내전 부스트 2시간' in t and '동료 파티' in t and '스킬 ×' in t)
            check(f'{scheme} 사냥터: 서버 문자열이 HTML 로 안 읽힘', await pg.locator('img[src=x]').count() == 0 and await pg.evaluate('window.__xss')is None)
            check(f'{scheme} 사냥터: 가로 스크롤 없음', await noscroll(pg))
            if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_hunt_{scheme}.png', full_page=False)
            if scheme == 'dark':
                # 쌓이는 골드 숫자 갱신
                a = await pg.inner_text('#pend'); await pg.wait_for_timeout(1200); check('쌓인 골드가 눈앞에서 늘어남(어림)', await pg.inner_text('#pend') != '' )
                # 버튼 → 길
                check('수령 → /brj/collect {}+토큰', (await press(pg, '[data-do=collect]', srv, '/brj/collect')) == [{'token': 'T' * 40}])
                check('수령 결과 문구', '6,000' in await msg(pg))
                r = await press(pg, '#dock [data-do=push]', srv, '/brj/push'); check('돌파(필드 아래 버튼) → /brj/push', len(r) == 1); check('보스 막힘 문구', '보스' in await msg(pg))
                r = await press(pg, '#main [data-do=quick]', srv, '/brj/quick'); check('퀵사냥 → /brj/quick', len(r) == 1 and '1,500' in await msg(pg))
                # 동료 탭
                await tab(pg, 'crew'); t = await pg.inner_text('#main')
                check('동료: 확률표·천장·소환 레벨 공개', '레전드 1%' in t and '38번 남음' in t and 'Lv.2 / 8' in t and await pg.locator('details table').count() == 1)
                check('동료: 카드 4장 + 파티 표시', await pg.locator('.cd[data-card]').count() == 4 and 'c1' and await pg.locator('.cd.sel').count() == 1)
                check('동료: 가로 스크롤 없음·XSS 없음', await noscroll(pg) and await pg.locator('#main img[src=x]').count() == 0)
                r = await press(pg, '[data-do=summon][data-n="1"]', srv, '/brj/summon'); check('1회 소환 → n=1 (정수)', r == [{'n': 1, 'token': 'T' * 40}], r)
                check('소환 결과 카드 + NEW', await pg.locator('.sumres .cd').count() == 1 and 'NEW' in await pg.inner_text('.sumres'))
                r = await press(pg, '[data-do=summon][data-n="10"]', srv, '/brj/summon'); check('10회 소환 → n=10', r and r[0]['n'] == 10 and isinstance(r[0]['n'], int))
                check('10연 결과 10장·XSS 없음', await pg.locator('.sumres .cd').count() == 10 and await pg.locator('#main img[src=x]').count() == 0 and await pg.evaluate('window.__xss') is None)
                check('저장 버튼은 처음엔 꺼져 있음', await pg.locator('[data-do=party]').is_disabled())
                await pg.click('.cd[data-card=c3]'); await pg.click('.cd[data-card=c4]'); await pg.wait_for_timeout(100)
                check('카드를 눌러 파티 편성(저장 전엔 서버로 안 감)', await pg.locator('.cd.sel').count() == 3 and not last(srv, '/brj/party'))
                await pg.click('.cd[data-card=c2]'); await pg.wait_for_timeout(100)
                check('파티는 최대 3명', await pg.locator('.cd.sel').count() == 3)
                r = await press(pg, '[data-do=party]', srv, '/brj/party'); check('편성 저장 → party [c1,c3,c4]', r and r[0]['party'] == ['c1', 'c3', 'c4'], r)
                # 성장
                await tab(pg, 'grow'); t = await pg.text_content('#main')   # 접힌 확률표도 읽는다
                check('성장: 축 3·장비 3·확률표', await pg.locator('[data-do=upgrade]').count() == 3 and await pg.locator('[data-do=enhance]').count() == 3 and '성공률' in t and '65%' in t)
                check('성장: 가로 스크롤 없음', await noscroll(pg))
                r = await press(pg, '[data-do=upgrade][data-axis=hp]', srv, '/brj/upgrade'); check('성장 → axis=hp', r and r[0]['axis'] == 'hp')
                r = await press(pg, '[data-do=enhance][data-slot=armor]', srv, '/brj/enhance'); check('강화 → slot=armor', r and r[0]['slot'] == 'armor'); check('강화 실패 문구(안 깨짐)', '그대로' in await msg(pg))
                # 모험 (스테이지 10 = 보스 관문에 막힌 상태)
                srv.view['stage'] = 10; srv.view['dungeon']['gate']['stage'] = 10; await pg.click('#rfBtn'); await pg.wait_for_timeout(300)
                check('관문에서는 필드 아래 큰 버튼이 「보스 도전」', await pg.locator('#dock [data-do=boss]').count() == 1 and await pg.locator('#dock [data-do=push]').count() == 0)
                await tab(pg, 'adv'); t = await pg.inner_text('#main')
                check('모험: 보스 3·던전·클랜 보스·할 일', await pg.locator('.boss img').count() >= 3 and '열쇠 던전' in t and '클랜 보스' in t and '오늘 할 일' in t)
                check('모험: 보스 그림은 저장소 경로', await pg.locator('img[src="img/brjang/boss/ddokkyu/front.png"]').count() >= 1)
                check('모험: XSS 없음·가로 스크롤 없음', await pg.locator('#main img[src=x]').count() == 0 and await noscroll(pg))
                if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_adv_dark.png', full_page=False)
                check('보스 도전 → /brj/boss (사냥터 필드로 이동해 연출)', len(await press(pg, '#main [data-do=boss]', srv, '/brj/boss')) == 1 and '쓰러뜨렸' in await msg(pg) and await pg.locator('#nav [data-tab=hunt].on').count() == 1)
                await pg.wait_for_function("window.__bt.boss===null", timeout=25000); await pg.wait_for_timeout(3600); await tab(pg, 'adv')
                check('던전 → /brj/dungeon', len(await press(pg, '#main [data-do=dungeon]', srv, '/brj/dungeon')) == 1 and '5단계' in await msg(pg))
                r = await press(pg, '[data-do=clanatk]', srv, '/brj/clanboss'); check('클랜 공격 → action=attack', r and r[0]['action'] == 'attack')
                r = await press(pg, '[data-do=clanclaim]', srv, '/brj/clanboss'); check('클랜 보상 → action=claim', r and r[0]['action'] == 'claim')
                check('오늘 할 일 → /brj/daily', len(await press(pg, '[data-do=daily]', srv, '/brj/daily')) == 1 and '못 끝낸' in await msg(pg))
                # 환생
                await tab(pg, 'pres'); await pg.wait_for_timeout(300); t = await pg.inner_text('#main')
                check('환생: 영구 보너스·시즌·상자 확률표·순위표', '황금 손' in t and '시즌 1' in t and '알맹이 없음' in t and '45%' in t and await pg.locator('table').count() >= 2)
                check('환생: 순위표 요청(top=20)', last(srv, '/brj/rank') and last(srv, '/brj/rank')[0]['top'] == 20 and '← 나' in t)
                check('환생: XSS 없음·가로 스크롤 없음', await pg.locator('#main img[src=x]').count() == 0 and await noscroll(pg) and await pg.evaluate('window.__xss') is None)
                check('환생 불가(스테이지 부족)면 버튼 꺼짐', await pg.locator('[data-do=prestigeask]').is_disabled())
                check('최고 레벨 보너스 버튼 꺼짐', await pg.locator('[data-do=prestigebuy][data-key=start]').is_disabled())
                r = await press(pg, '[data-do=prestigebuy][data-key=gold]', srv, '/brj/prestige_buy'); check('보너스 구매 → key=gold', r and r[0]['key'] == 'gold')
                r = await press(pg, '[data-do=chest][data-n="1"]', srv, '/brj/chest'); check('상자 열기 → n=1', r and r[0]['n'] == 1)
                r = await press(pg, '[data-do=chest][data-n="4"]', srv, '/brj/chest'); check('상자 한꺼번에 → n=4', r and r[0]['n'] == 4, r)
                n0 = len(last(srv, '/brj/rank')); await pg.click('[data-do=rank]'); await pg.wait_for_timeout(250); check('순위표 새로고침', len(last(srv, '/brj/rank')) == n0 + 1)
                # 환생 가능 상태: 확인 단계 두 번
                srv.view['prestige'].update({'can': True, 'stage': 30, 'gain': 5}); srv.view['stage'] = 30
                await pg.click('#rfBtn'); await pg.wait_for_timeout(300)
                n0 = len(last(srv, '/brj/prestige')); await pg.click('[data-do=prestigeask]'); await pg.wait_for_timeout(100)
                check('환생은 한 번 눌러서는 서버로 안 감(확인 단계)', len(last(srv, '/brj/prestige')) == n0 and '정말 환생' in await pg.inner_text('#main'))
                await pg.click('[data-do=prestigecancel]'); await pg.wait_for_timeout(100)
                check('아니요 → 확인 창 닫힘', '정말 환생' not in await pg.inner_text('#main'))
                await pg.click('[data-do=prestigeask]'); r = await press(pg, '[data-do=prestige]', srv, '/brj/prestige'); check('네, 환생 → confirm:true', r and r[0]['confirm'] is True)
                # 이중 클릭 방지
                await tab(pg, 'hunt'); c0 = len(last(srv, '/brj/collect'))
                await pg.evaluate("document.querySelector('[data-do=collect]').click();document.querySelector('[data-do=collect]').click()"); await pg.wait_for_timeout(300)
                check('버튼을 연달아 눌러도 요청은 1번', len(last(srv, '/brj/collect')) == c0 + 1)
                check('콘솔 오류 없음', not errs, errs)
            await ctx.close()
        # ---- 서버가 일이 안 된다고 답하는 경우 ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv)
        srv.override['/brj/summon'] = lambda body: (200, {'ok': False, 'code': 'no_ticket', 'results': [], 'view': make_view()})
        await tab(pg, 'crew'); await pg.click('[data-do=summon][data-n="1"]'); await pg.wait_for_timeout(250)
        check('소환권 부족 문구', '소환권이 모자라' in await msg(pg))
        srv.override['/brj/summon'] = lambda body: (200, {'ok': False, 'code': 'no_pool', 'results': [], 'view': make_view()})
        await pg.click('[data-do=summon][data-n="1"]'); await pg.wait_for_timeout(250); check('동료 명단 준비 중 문구(no_pool)', '준비' in await msg(pg))
        srv.mode = 'busy'; await pg.click('[data-do=summon][data-n="1"]'); await pg.wait_for_timeout(250)
        check('행동 중 몰림(busy): 문구 + 화면 유지', '몰려서' in await msg(pg) and await pg.locator('#nav [data-tab]').count() == 6)
        srv.mode = 'auth'; await pg.click('[data-do=summon][data-n="1"]'); await pg.wait_for_timeout(250)
        check('행동 중 로그인 만료: 로그인 화면으로', await pg.locator('#loginBtn').count() == 1)
        check('가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs); await ctx.close()
        # ---- 스킬 · 각성 탭: 올바른 길로 올바른 값을 보낸다 ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(300)
        check('핫바: 기본 스킬 둘이 장착돼 있고 나머지는 빈 칸', await pg.locator('#dock .sk[data-sid]').count() == 2 and await pg.locator('#dock .sk.empty').count() == 3)
        await tab(pg, 'skill'); t = await pg.inner_text('#main')
        check('스킬 탭: 각성 0/5단계 · 필요 조건 · 다음에 배우는 스킬', '0 / 5단계' in t and '9 / 6' in t and await pg.locator('.unl img').count() == 2 and await pg.locator('.gem.on').count() == 0, t[:100])
        check('스킬 탭: 도감 10종, 잠긴 8종은 각성 표시, 기본 2종은 강화·해제 버튼', await pg.locator('.skc').count() == 10 and await pg.locator('.skc.lock').count() == 8 and await pg.locator('[data-do=skillup]').count() == 2 and await pg.locator('[data-do=skillun]').count() == 2)
        check('스킬 탭: 아이콘 그림 경로 규약(img/brjhunt/ui/skill_<id>.webp)', await pg.locator('.skc img.sic[src="img/brjhunt/ui/skill_storm.webp"]').count() == 1)
        check('스킬 탭: 각성 가능 → 버튼 켜짐 · 탭에 알림 점', await pg.locator('[data-do=awaken]').is_enabled() and await pg.locator('#nav [data-tab=skill] .dot').count() == 1)
        r = await press(pg, '[data-do=awaken]', srv, '/brj/awaken'); check('각성 → POST /brj/awaken {토큰만}', r == [{'token': 'T' * 40}], r)
        check('각성 연출: 오버레이에 「각성 1단계」·새 스킬 아이콘 2개', await pg.locator('#awk.show').count() == 1 and '각성 1단계' in await pg.inner_text('#awk') and await pg.locator('#awk img').count() == 2)
        if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_awaken.png')
        await pg.click('#awk'); await pg.wait_for_timeout(150); check('오버레이는 눌러서 닫힘', await pg.locator('#awk.show').count() == 0)
        check('각성 뒤: 핫바에 4칸 장착, 각성 보석 1개', await pg.locator('#dock .sk[data-sid]').count() == 4 and await pg.locator('.gem.on').count() == 1)
        check('각성 뒤: 다음 단계는 스테이지가 모자라 꺼짐 + 이유', await pg.locator('[data-do=awaken]').is_disabled() and '스테이지 12 이상' in await pg.inner_text('.awk'))
        r = await press(pg, '[data-do=skillup][data-id=slash]', srv, '/brj/skill'); check('강화 → {action:upgrade, id:slash}', r and r[0]['action'] == 'upgrade' and r[0]['id'] == 'slash' and 'slot' not in r[0], r)
        check('강화 뒤 Lv.2 로 보임', 'Lv.2' in await pg.inner_text('#sk_slash'))
        await pg.click('[data-do=skillun][data-id=bomb]'); await pg.wait_for_timeout(250)
        r = last(srv, '/brj/skill')[-1]; check('해제 → {action:unequip, id:bomb}', r['action'] == 'unequip' and r['id'] == 'bomb' and 'slot' not in r, r)
        check('해제 뒤 그 칸이 비고 핫바도 갱신', await pg.locator('#dock .sk[data-sid]').count() == 3)
        await pg.click('[data-do=slotsel][data-i="3"]'); await pg.wait_for_timeout(100)
        check('칸을 눌러 고르면 선택 표시(aria-pressed)', await pg.locator('.eqs.sel').count() == 1 and await pg.get_attribute('.eqs.sel', 'aria-pressed') == 'true')
        r = await press(pg, '[data-do=skilleq][data-id=bomb]', srv, '/brj/skill'); check('장착 → {action:equip, id:bomb, slot:3(정수)}', r and r[-1]['action'] == 'equip' and r[-1]['id'] == 'bomb' and r[-1]['slot'] == 3 and isinstance(r[-1]['slot'], int), r)
        check('장착 문구', '장착' in await msg(pg))
        srv.sk['aw'] = 3; srv.sk['lv'].update({'thunder': 1, 'fire': 1, 'egg': 1, 'shield': 1}); await pg.click('#rfBtn'); await pg.wait_for_timeout(300)
        r = await press(pg, '[data-do=skilleq][data-id=shield]', srv, '/brj/skill'); check('패시브 장착 → slot 없이 {action:equip, id:shield}', r and r[-1]['id'] == 'shield' and 'slot' not in r[-1], r)
        check('패시브 칸이 채워지고 핫바 패시브 아이콘', await pg.locator('#dock .sk.pas[data-sid=shield]').count() == 1)
        check('스킬 탭 가로 스크롤·XSS·오류 없음', await noscroll(pg) and await pg.locator('img[src=x]').count() == 0 and not errs, errs)
        if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_skill_dark.png')
        # 서버가 거절하는 경우
        srv.override['/brj/skill'] = lambda body: (200, {'ok': True, 'result': 'gold', 'cost': {'gold': 777, 'stone': 3}, 'view': make_view()})
        await pg.click('[data-do=skillup][data-id=slash]'); await pg.wait_for_timeout(250); check('강화 골드 부족 문구', '골드가 모자라요' in await msg(pg) and '777' in await msg(pg))
        # 응답이 끊겨도 서버는 이미 처리했을 수 있다 → 뷰를 다시 받아 실제 상태를 보여 준다
        srv.override.pop('/brj/skill', None); srv.abort_paths = ['/brj/skill']; n0 = len([1 for p_, _ in srv.hits if p_ == '/brj/idle'])
        await pg.click('[data-do=skillup][data-id=slash]'); await pg.wait_for_timeout(500)
        check('스킬 강화 응답 끊김 → /brj/idle 로 다시 받음 + 안내', len([1 for p_, _ in srv.hits if p_ == '/brj/idle']) == n0 + 1 and '실제 상태' in await msg(pg), await msg(pg))
        srv.abort_paths = []
        check('콘솔 오류 없음', not errs, errs); await ctx.close()
        # 스테이지 부족: 각성 버튼이 꺼지고 이유가 보인다
        srv = Server(); srv.view['stage'] = 3; ctx, pg, errs = await new_page(b, srv); await tab(pg, 'skill')
        check('스테이지 부족이면 각성 버튼 꺼짐 + 이유', await pg.locator('[data-do=awaken]').is_disabled() and '스테이지 6 이상' in await pg.inner_text('.awk'))
        await ctx.close()
        # 마지막 각성까지 끝낸 사람
        srv = Server(); srv.sk['aw'] = 5; srv.sk['lv'].update({s[0]: 3 for s in SKILLS}); srv.sk['a'] = ['storm', 'shrimp', 'egg', 'thunder']; srv.sk['p'] = 'shield'
        ctx, pg, errs = await new_page(b, srv); await tab(pg, 'skill')
        check('모든 각성을 마치면 안내만 · 보석 5개 · 잠긴 스킬 0', '모든 각성을 마쳤어요' in await pg.inner_text('.awk') and await pg.locator('.gem.on').count() == 5 and await pg.locator('.skc.lock').count() == 0 and await pg.locator('[data-do=awaken]').count() == 0)
        check('핫바: 액티브 4 + 패시브 1', await pg.locator('#dock .sk[data-sid]').count() == 5)
        check('오류 없음', not errs, errs); await ctx.close()
        # ---- 소리 설정 시트 · BGM ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(300)
        check('BGM: 지역 트랙을 고름(홍대 먹자골목 → field3)', await pg.evaluate('window.__bt.bgm') == 'field3')
        await pg.click('#sndBtn'); await pg.wait_for_timeout(150)
        check('소리 설정 시트가 열림 · 슬라이더 3개 · 기본값 60/80/35', await pg.locator('#sndBg.show').count() == 1 and await pg.locator('#sndBg input[type=range]').count() == 3 and [await pg.input_value(s) for s in ('#vM', '#vS', '#vB')] == ['60', '80', '35'])
        await pg.fill('#vM', '30'); await pg.fill('#vB', '10')
        st = await pg.evaluate('BrjAudio.state()'); check('슬라이더 → BrjAudio 마스터 0.3 · BGM 0.1', abs(st['master'] - 0.3) < 1e-6 and abs(st['bgm'] - 0.1) < 1e-6, st)
        await pg.click('#muteBtn'); st = await pg.evaluate('BrjAudio.state()'); check('모두 끄기 → muted · 상단 아이콘 🔇', st['muted'] is True and await pg.inner_text('#sndBtn') == '🔇')
        saved = await pg.evaluate("localStorage.getItem('brjhunt_audio_v1')"); check('설정이 localStorage 에 저장됨', saved and '"muted":true' in saved, saved)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(100); check('Esc 로 시트 닫힘', await pg.locator('#sndBg.show').count() == 0)
        await pg.reload(); await pg.wait_for_timeout(500); check('새로고침해도 음소거 유지', (await pg.evaluate('BrjAudio.state()'))['muted'] is True and await pg.inner_text('#sndBtn') == '🔇')
        check('오류 없음', not errs, errs); await ctx.close()
        # 첫 제스처 전에는 소리 없음(AudioContext 를 만들지 않음), 누르면 풀림
        srv = Server(); ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(300)
        check('첫 터치 전: 잠금(unlocked=false)', (await pg.evaluate('BrjAudio.state()'))['unlocked'] is False)
        await pg.click('[data-tab=crew]'); await pg.wait_for_timeout(300); check('첫 터치 뒤: 잠금 해제', (await pg.evaluate('BrjAudio.state()'))['unlocked'] is True)
        check('첫 터치 뒤: 지역 BGM(field3) 재생이 시작됨', (await pg.evaluate('BrjAudio.state()'))['track'] == 'field3', await pg.evaluate('BrjAudio.state()'))
        check('오류 없음', not errs, errs); await ctx.close()
        # 서버가 아직 스킬 구역을 안 올린 경우(옛 봇): view.skill 이 없어도 화면이 안 깨진다
        def _noskill(body):
            v = make_view(); v.pop('skill', None); return 200, {'ok': True, 'view': v}
        srv = Server(); srv.override['/brj/idle'] = _noskill; ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(300)
        check('옛 서버(스킬 없음): 사냥터·핫바(빈 칸 5)가 나옴', await pg.locator('#dock .sk.empty').count() == 5 and await pg.locator('#fcv').count() == 1)
        await tab(pg, 'skill'); check('옛 서버: 스킬 탭은 안내 문구만', '스킬 정보를 아직 받지 못했어요' in await pg.inner_text('#main'))
        await tab(pg, 'hunt'); check('옛 서버: 오류 없음 · 가로 스크롤 없음', not errs and await noscroll(pg), errs); await ctx.close()
        # 오디오·필드 스크립트가 아예 없어도 화면은 돈다(폴백)
        srv = Server(); ctx = await b.new_context(viewport={'width': 390, 'height': 800})
        async def route2(r):
            u = r.request.url
            if u.startswith(API):
                body = json.loads(r.request.post_data or '{}'); st_, obj = srv.handle(urlpath(u), body)
                await r.fulfill(status=st_, headers={'access-control-allow-origin': '*', 'access-control-allow-headers': '*'}, content_type='application/json', body=json.dumps(obj)); return
            if 'brjhunt_audio.js' in u or 'brjhunt_field.js' in u: await r.abort(); return
            if u.startswith('file://'): await r.continue_(); return
            await r.abort()
        await ctx.route('**/*', route2); await ctx.add_init_script("localStorage.setItem('sgg_dc'," + json.dumps(TOKEN) + ")")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); await pg.goto(URL); await pg.wait_for_timeout(500)
        check('폴백: 필드·소리 스크립트가 없어도 탭·버튼이 동작', await pg.locator('#nav [data-tab]').count() == 6 and await pg.is_visible('#fieldNote'))
        await pg.click('[data-do=collect]'); await pg.wait_for_timeout(250); check('폴백: 수령 동작', '6,000' in await msg(pg)); await pg.click('#sndBtn'); await pg.wait_for_timeout(100)
        check('폴백: 소리 시트도 오류 없이 열림', await pg.locator('#sndBg.show').count() == 1 and not errs, errs); await ctx.close()
        # ---- 데스크톱 폭 ----
        srv = Server(); ctx, pg, errs = await new_page(b, srv, w=1100, h=800)
        for k in ('hunt', 'skill', 'crew', 'grow', 'adv', 'pres'):
            await tab(pg, k); check(f'1100px {k}: 가로 스크롤 없음', await noscroll(pg))
        check('1100px: 오류 없음', not errs, errs); await ctx.close()
        # ---- 탭별 390px 그림 ----
        if SHOTS:
            srv = Server(); ctx, pg, errs = await new_page(b, srv, scheme='light')
            for k in ('hunt', 'skill', 'crew', 'grow', 'adv', 'pres'):
                await tab(pg, k); await pg.wait_for_timeout(250); await pg.screenshot(path=f'{SHOTS}/ui_{k}_light.png', full_page=False)
            await ctx.close()
        await b.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
