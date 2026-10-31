#!/usr/bin/env python3
"""brjhunt.html ↔ 실제 봇 코드 통합 시험. 사용: CHROME=... python3.13 tests/brjhunt_realbot_test.py --bot <봇 저장소>/bot.py [--shots 폴더]
가짜 서버 대신 **실제 bot.py 의 브장신 구역(BRJ_IDLE_CAP_H 부터 룰더스카이 구역 앞까지)을 그대로 발췌 실행**하고, 페이지가 부르는 /brj/* 를
그 라우트 함수(BRJ2_ROUTES)에 직접 이어 준다(디스코드·네트워크 없음). 장비·스킬·동료·환생을 채운 기록으로 본다:
 · 실제 응답 모양(stats·field·combat·hunt·skill 전투 수치)을 화면이 제대로 읽는지(NaN·undefined·[object 가 화면에 없는지)
 · 스탯 올리기·장비 강화·스킬 강화가 실제 서버 계산대로 골드를 쓰는지
 · 사냥 보고(/brj/hunt)가 실제 서버 규칙(간격·시간 통장·마릿수 상한)에 걸리지 않고 골드로 쌓이는지 — 너무 빨리 보내면 서버가 거절하는지
 · 도전 던전·보스가 실제 판정대로 연출되는지"""
import asyncio, os, sys, json, time, types, random, hashlib, datetime, tempfile, threading, copy
_here = os.path.dirname(os.path.abspath(__file__))
BOT = sys.argv[sys.argv.index('--bot') + 1] if '--bot' in sys.argv else ''
if not BOT or not os.path.isfile(BOT):
    print('SKIP 봇 코드를 못 찾음: --bot <봇 저장소>/bot.py 를 주세요'); sys.exit(0)
_src = open(os.path.join(_here, 'brjhunt_test.py'), encoding='utf-8').read(); _src = _src[:_src.index('async def main')]
_g = {'__file__': os.path.join(_here, 'brjhunt_test.py'), '__name__': 'brjhunt_base'}
exec(compile(_src, 'brjhunt_test.py', 'exec'), _g)
Server, new_page, noscroll, tab, check, FAILS, SHOTS = (_g[k] for k in ('Server', 'new_page', 'noscroll', 'tab', 'check', 'FAILS', 'SHOTS'))
from playwright.async_api import async_playwright

# ---------- 실제 봇 코드 발췌 실행 ----------
bsrc = open(BOT, encoding='utf-8').read()
A = bsrc.index('BRJ_IDLE_CAP_H = 12'); B = bsrc.index('# 🏪 [2026-09-03 사장님 지시] 룰더스카이식')
TH = [0, 30, 100, 250, 500, 900, 1500, 2500, 4000, 6000, 9000, 13000, 18000]
BRJ = {}; DIRTY = {'v': False}
def _brj_rec(uid, name=None): return BRJ.setdefault(str(uid), {'xp': 0, 'name': name or ''})
def _brj_stage(xp):
    i = 0
    for k, t in enumerate(TH):
        if xp >= t: i = k
    return (i, None)
class _Ctx: pass
KST = datetime.timezone(datetime.timedelta(hours=9)); TMP = tempfile.mkdtemp()
G = dict(threading=threading, json=json, os=os, random=random, hashlib=hashlib, datetime=datetime, KST=KST, BASE=TMP, _P6_CTX=_Ctx(), _p6_client_ip=lambda h: '1', _p6_who=lambda t: None, P6_ORIGIN='x',
         time=time, BRJ=BRJ, _BRJ_DIRTY=DIRTY, save_brj=lambda: None, _brj_rec=_brj_rec, _brj_stage=_brj_stage, _mito_tnorm=lambda s: str(s).lower(), _wk_name=lambda s: s, _wk_date=lambda s: ('', None), _aw_save=lambda p, o: None)
exec(bsrc[A:B], G)
G['BRS_AUTO_REFRESH'] = False; G['BRJ_RL_MAX'] = 10 ** 9
ROUTES = G['BRJ2_ROUTES']

def sample_record(now):
    return {'xp': 2500, 'name': '실제봇 시험', 'idle': {'t': now - 5400, 'stage': 12, 'gold': 18450, 'boost': 2, 'total': 96000, 'stone': 14, 'feast': 22, 'ticket': 3,
            'growth': {'ax': {'atk': 8, 'hp': 7, 'def': 5, 'crit': 3, 'critdmg': 2, 'acc': 5}, 'gear': {'weapon': {'lv': 3, 'pity': 0}, 'armor': {'lv': 2, 'pity': 0}, 'acc': {'lv': 1, 'pity': 0}}},
            'prestige': {'up': {'gold': 2, 'cap': 1, 'start': 1}, 'points': 4, 'n': 2},
            'skill': {'aw': 3, 'lv': {'slash': 6, 'peck': 5, 'spin': 4, 'bomb': 3, 'thunder': 2, 'fire': 2, 'egg': 1, 'shield': 2, 'shrimp': 0, 'storm': 0}, 'eq': {'a': ['slash', 'peck', 'spin', 'thunder'], 'p': 'shield'}},
            'summon': {'cards': {'c1': {'n': '샘플A', 'gr': 'epic', 'sh': 3, 'f': []}, 'c2': {'n': '샘플B', 'gr': 'rare', 'sh': 1, 'f': []}}, 'party': ['c1', 'c2'], 'pulls': 30, 'pity': {'epic': 4, 'unique': 30, 'legend': 30}}}}

class RealServer(Server):
    """페이지가 부르는 길을 실제 봇의 라우트 함수에 이어 준다."""
    def __init__(self):
        Server.__init__(self); BRJ.clear(); BRJ['1'] = sample_record(time.time()); self.lock = threading.Lock(); self.answers = []
    def handle(self, path, body):
        self.hits.append((path, body))
        fn = ROUTES.get(path)
        if not fn: return 404, {'ok': False, 'code': 'not_found'}
        with self.lock:
            code, obj = fn('1', '실제봇 시험', BRJ['1'], body)
        self.answers.append((path, code, obj)); return code, json.loads(json.dumps(obj))

BAD = ('NaN', 'undefined', '[object', 'Infinity')
async def clean(pg, label):
    t = await pg.evaluate("document.body.innerText")
    bad = [x for x in BAD if x in t]
    check(f'{label}: 화면에 NaN·undefined·[object 가 없음', not bad, bad)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        srv = RealServer(); ctx, pg, errs = await new_page(b, srv, w=1280, h=800); await pg.wait_for_timeout(1500)
        v = [o for pa, c, o in srv.answers if pa == '/brj/idle'][0]['view']
        check('실제 응답에 새 구역이 있음(stats·field·combat·hunt)', all(k in v for k in ('stats', 'field', 'combat', 'hunt')) and len(v['stats']['list']) == 6, sorted(v.keys()))
        for k in ('hunt', 'skill', 'crew', 'grow', 'adv', 'pres', 'rank'):
            await tab(pg, k); await pg.wait_for_timeout(250); await clean(pg, f'실제 응답 · {k} 탭')
        await tab(pg, 'hunt')
        st = await pg.evaluate('window.__bt.stats')
        check('엔진이 실제 스탯으로 돎(체력·MP 가 서버 combat 과 같음)', st['hpMax'] == v['combat']['hp'] and st['mpMax'] == v['combat']['mp'], (st['hpMax'], v['combat']['hp'], st['mpMax'], v['combat']['mp']))
        sk = await pg.evaluate("window.__bt.field.debug.skills.map(s=>s&&({id:s.id,mp:s.mp,cd:s.cd,hits:s.hits,range:s.range,mult:s.mult}))")
        want = [(x['id'], x['mp'], x['cd'], x['hits'], x['mult']) for x in v['skill']['list'] if x['equipped'] and x['kind'] == 'active']
        check('엔진의 스킬 4칸이 서버 수치(mp·쿨·타수·피해 계수)와 같음', [(s['id'], s['mp'], s['cd'], s['hits'], round(s['mult'], 2)) for s in sk if s] == [(a, c, d, e, round(f, 2)) for (a, c, d, e, f) in [(w[0], w[1], w[2], w[3], w[4]) for w in want]], (sk, want))
        # ---- 스탯 올리기 / 장비 강화 / 스킬 강화 ----
        await tab(pg, 'grow'); g0 = v['gold']
        cost = v['stats']['list'][0]['cost']; lv0 = v['stats']['list'][0]['lv']
        await pg.click('[data-do=upgrade][data-axis=atk]'); await pg.wait_for_timeout(300)
        o = [o for pa, c, o in srv.answers if pa == '/brj/upgrade'][-1]
        check('공격력 올리기 → 서버가 골드를 정확히 씀 · 레벨 +1 · 공격력 상승', o['result'] == 'ok' and o['view']['gold'] == g0 - cost and o['view']['stats']['list'][0]['lv'] == lv0 + 1 and o['view']['combat']['atk'] > v['combat']['atk'], (o['result'], o['view']['gold'], g0 - cost))
        await clean(pg, '스탯 올린 뒤')
        r = await pg.evaluate("fetch('https://hth3thmujs.apps.bot-hosting.cloud/brj/upgrade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:JSON.parse(localStorage.getItem('sgg_dc')).token,axis:'luck'})}).then(r=>r.status)")
        check('옛 축(luck)은 서버가 400 으로 거절', r == 400, r)
        await pg.click('[data-do=enhance][data-slot=weapon]'); await pg.wait_for_timeout(300)
        o = [o for pa, c, o in srv.answers if pa == '/brj/enhance'][-1]
        check('장비 강화 → 실제 결과(success/pity/fail)가 문구로 나옴', o['result'] in ('success', 'pity', 'fail') and ('강화' in await pg.inner_text('.msg') or '실패' in await pg.inner_text('.msg')), o['result'])
        await tab(pg, 'skill'); await pg.click('[data-do=skillup][data-id=slash]'); await pg.wait_for_timeout(300)
        o = [o for pa, c, o in srv.answers if pa == '/brj/skill'][-1]
        check('스킬 강화 → 레벨 +1 · 피해 계수가 오름', o['result'] == 'ok' and [x for x in o['view']['skill']['list'] if x['id'] == 'slash'][0]['mult'] > [x for x in v['skill']['list'] if x['id'] == 'slash'][0]['mult'])
        await clean(pg, '스킬 강화 뒤')
        # ---- 사냥 보고 (실제 서버 규칙) ----
        await tab(pg, 'hunt'); await pg.wait_for_timeout(300)
        g1 = BRJ['1']['idle']['gold']; t1 = BRJ['1']['idle']['t']
        # 실제 시간 그대로 돌려(가속 없음) 엔진이 스스로 30초 보고를 보내는지 본다 — 실제 서버의 간격·시간 통장 규칙에 걸리면 안 된다
        k_before = await pg.evaluate('window.__bt.kills')
        for _ in range(100):
            if any(pa == '/brj/hunt' for pa, c, o in srv.answers): break
            await pg.wait_for_timeout(500)
        await pg.wait_for_timeout(300)
        k_after = await pg.evaluate('window.__bt.kills')
        an = [(c, o) for pa, c, o in srv.answers if pa == '/brj/hunt']
        check('엔진이 스스로 보낸 30초 보고를 실제 서버가 받음(ok)', an and an[0][1].get('ok') is True, an[0][1].get('code') if an else None)
        an = an[:1]
        if an and an[-1][1].get('ok'):
            o = an[-1][1]; hb = [bd for pa, bd in srv.hits if pa == '/brj/hunt'][-1]
            check('서버가 인정한 마릿수 ≤ 보낸 마릿수, 상한(cap) 안', 0 <= o['accepted'] <= hb['kills'] and o['accepted'] <= o['cap'], (o['accepted'], hb['kills'], o['cap']))
            check('골드가 몬스터 드랍 × 인정 마릿수만큼 쌓임(소수는 이월)', abs(o['exact'] - o['accepted'] * v['field']['mon']['gold']) < 1e-4 and BRJ['1']['idle']['gold'] >= g1, (o['exact'], o['accepted'], v['field']['mon']['gold']))
            check('방치 시작 시각(idle.t)이 보고한 초만큼 앞으로 밀림(이중 계산 방지)', abs(BRJ['1']['idle']['t'] - (t1 + hb['secs'])) < 1.0, (BRJ['1']['idle']['t'] - t1, hb['secs']))
            check('칩의 골드가 서버 값으로 갱신됨', (await pg.evaluate("document.getElementById('chip_gold').title")).replace(',', '').split()[-1] == str(o['view']['gold']), await pg.evaluate("document.getElementById('chip_gold').title"))
        # 너무 빨리 또 보내면 서버가 막는다 → 페이지는 쌓아 두고 알림 없이 기다린다
        n0 = len([1 for pa, _ in srv.hits if pa == '/brj/hunt'])
        await pg.evaluate('window.__bt.hq.k=20; window.__bt.hq.s=30; window.__bt.hq.min=0; window.__bt.sendHunt()'); await pg.wait_for_timeout(400)
        an = [o for pa, c, o in srv.answers if pa == '/brj/hunt'][-1]
        check('바로 이어 보내면 실제 서버가 too_fast/too_soon 으로 거절', an.get('ok') is False and an.get('code') in ('too_fast', 'too_soon'), an.get('code'))
        q = await pg.evaluate('({k:window.__bt.hq.k,s:window.__bt.hq.s})'); check('거절돼도 마릿수·초를 버리지 않고 쌓아 둠', q['k'] >= 20 and q['s'] >= 30, q)
        check('거절돼도 화면에 오류 토스트가 뜨지 않음', await pg.locator('#toastBox .toast').count() == 0)
        await pg.evaluate('window.__bt.hq.k=0; window.__bt.hq.s=0')
        # ---- 도전 던전 (실제 판정) ----
        await tab(pg, 'hunt'); v2 = [o for pa, c, o in srv.answers][-1]['view']
        BRJ['1']['idle']['growth']['ax'] = {k: 30 for k in ('atk', 'hp', 'def', 'crit', 'critdmg', 'acc')}     # 전투력을 크게 올려 이기는 경우를 만든다
        await pg.click('#rfBtn'); await pg.wait_for_timeout(500)
        await pg.evaluate("window.__seen=[]; setInterval(()=>{const b=window.__bt.boss; const s=window.__seen; if(s[s.length-1]!==b) s.push(b);},40)")
        pre = await pg.evaluate("document.querySelector('#dock [data-do=chal], #dock [data-do=boss]').dataset.do")
        await pg.click('#dock .push'); await pg.wait_for_timeout(600)
        pa_ = 'chal' if pre == 'chal' else 'boss'
        res = [o for pa, c, o in srv.answers if pa in ('/brj/push', '/brj/boss')][-1]
        await pg.wait_for_function('window.__bt.boss===null', timeout=60000); await pg.wait_for_timeout(400)
        seen = await pg.evaluate('window.__seen'); won = res.get('result') in ('ok', 'win')
        check('실제 판정(' + str(res.get('result')) + ')대로 연출이 갈림', ('dying' in seen) == won and (('smash' in seen) == (not won)) and seen[-1] is None, (res.get('result'), seen))
        await clean(pg, '도전 뒤')
        check('콘솔 오류 없음', not errs, errs)
        if SHOTS: await pg.screenshot(path=f'{SHOTS}/realbot_1280.png')
        await ctx.close()
        # 390px 폰 + 터치
        srv = RealServer(); ctx, pg, errs = await new_page(b, srv, w=390, h=800, touch=True); await pg.wait_for_timeout(2000)
        for k in ('hunt', 'skill', 'crew', 'grow', 'adv', 'pres', 'rank'):
            await tab(pg, k); await pg.wait_for_timeout(200); check(f'실제 응답 390px {k}: 가로 스크롤 없음', await noscroll(pg)); await clean(pg, f'390px {k}')
            if SHOTS: await pg.screenshot(path=f'{SHOTS}/realbot_390_{k}.png')
        check('실제 응답 390px: 오류 없음', not errs, errs); await ctx.close()
        await b.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
