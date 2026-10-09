# -*- coding: utf-8 -*-
"""레이드 0단계 시험 페이지(raid-test/) 자동 검사 — 2026-10-08
실행: python3 tests/raid/pages_test.py [이름 …] [--jobs N] [--list]    (종료코드 0 = 전부 통과)

· 외부망 없이 닫힌 상태: 로컬 정적 서버 + 가짜 에코 서버(tests/raid/fixtures/fake_echo.py) + page.route / route_web_socket.
· 시간 의존 시험(retry 표시)은 실패하면 한 번만 다시 돌린다. 측정값 옆에 uptime(load) 을 같이 찍는다.
· 실기기(안드로이드 디스코드 내부창)에서 돌려 본 것이 아니다 — 여기서 확인하는 건 "코드가 의도대로 반응하는가" 뿐.
"""
import asyncio, os, sys, re, json, math, time, subprocess, traceback
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
sys.path.insert(0, os.path.join(HERE, 'fixtures'))
from sv_harness import launch, Srv          # noqa: E402
from fake_echo import FakeEcho, EVIL        # noqa: E402
from playwright.async_api import async_playwright   # noqa: E402

import tempfile
SCR = os.environ.get('RP0_SCR') or os.path.join(tempfile.gettempdir(), 'raid_pages_shots')   # 스크린샷 저장 위치(저장소 밖)
os.makedirs(SCR, exist_ok=True)
PAGES_DIR = os.environ.get('RP0_PAGES') or os.path.join(ROOT, 'raid-test')      # 다른 판(예: 고치기 전 복사본)에 같은 시험을 대 보고 싶을 때 RP0_PAGES=폴더

TESTS = []


def test(name, retry=False):
    def deco(fn):
        TESTS.append((name, fn, retry))
        return fn
    return deco


def ok(cond, msg='assert'):
    if not cond:
        raise AssertionError(msg)


def eq(a, b, msg=''):
    if a != b:
        raise AssertionError('%s: %r != %r' % (msg, a, b))


def load():
    try:
        return open('/proc/loadavg').read().split()[0]
    except Exception:
        return '?'


class Env:
    """시험 하나가 쓰는 서버·브라우저 묶음(시험마다 새 가짜 서버 → 서로 영향 없음)"""
    def __init__(self, br, web):
        self.br, self.web, self.fe = br, web, None
        self.ctxs = []

    async def start_fe(self, **kw):
        self.fe = FakeEcho(**kw)
        await self.fe.start()
        return self.fe

    async def stop(self):
        for c in self.ctxs:
            try:
                await c.close()
            except Exception:
                pass
        if self.fe:
            await self.fe.stop()

    def page_url(self, name, query=''):
        return 'http://127.0.0.1:%d/%s%s' % (self.web.port, name, query)

    async def new_page(self, name, query='', w=412, h=915, init=None, clock=False, perms=None, mobile=False, allow=(), setup=None):
        ctx = await self.br.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1,
                                        permissions=perms or [], locale='ko-KR')
        self.ctxs.append(ctx)
        ports = {self.web.port}
        if self.fe:
            ports.add(self.fe.port)

        async def base(route):
            u = route.request.url
            p = urlparse(u)
            if p.hostname == '127.0.0.1' and p.port in ports:
                await route.continue_()
            else:
                await route.abort('failed')       # 바깥 인터넷은 절대 안 나간다
        await ctx.route('**/*', base)
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))

        def on_console(m):
            if m.type == 'error':
                t = m.text
                if any(a in t for a in allow):
                    return
                errs.append('CONSOLE ' + t)
        pg.on('console', on_console)
        if init:
            await pg.add_init_script(init)
        if clock:
            await pg.clock.install()
        if setup:
            await setup(ctx, pg)          # route_web_socket 은 페이지를 열기 전에 걸어야 먹는다
        await pg.goto(self.page_url(name, query))
        return ctx, pg, errs


VIS_INIT = """
(function(){var vs='visible';
 Object.defineProperty(document,'visibilityState',{configurable:true,get:function(){return vs}});
 Object.defineProperty(document,'hidden',{configurable:true,get:function(){return vs==='hidden'}});
 window.__vis=function(s){vs=s;document.dispatchEvent(new Event('visibilitychange'));};
})();
"""


async def poll(pg, expr, timeout=12.0, step=0.1, msg=''):
    """파이썬 쪽에서 표현식을 반복 평가한다(page.clock 이 걸린 페이지에서도 안전)"""
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = await pg.evaluate(expr)
        if last:
            return last
        await asyncio.sleep(step)
    raise AssertionError('시간 초과: %s  (%s) last=%r' % (msg or expr, expr, last))


async def snap(pg):
    return await pg.evaluate('P0SOCK.snap()')


def no_errs(errs, label=''):
    ok(not errs, '콘솔/페이지 오류 %s: %s' % (label, errs[:3]))


LAYOUT_JS = """() => {
  const W = innerWidth, bad = [];
  document.querySelectorAll('body *').forEach(e => {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    const r = e.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const nm = e.tagName + (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '');
    if (r.right > W + 0.5 || r.left < -0.5) bad.push('가로넘침 ' + nm + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + ' / ' + W);
    const own = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (own && parseFloat(cs.fontSize) < 15.99) bad.push('글자작음 ' + nm + ' ' + cs.fontSize);
    if (e.tagName === 'BUTTON' && r.height < 47.9) bad.push('버튼낮음 ' + nm + ' ' + Math.round(r.height));
    if ((e.tagName === 'BUTTON' || e.tagName === 'SUMMARY' || e.tagName === 'A') && e.scrollWidth > e.clientWidth + 1) bad.push('버튼잘림 ' + nm + ' ' + e.scrollWidth + '>' + e.clientWidth);
  });
  return {sw: document.documentElement.scrollWidth, W, bad: bad.slice(0, 12)};
}"""


async def check_layout(pg, label):
    r = await pg.evaluate(LAYOUT_JS)
    ok(r['sw'] <= r['W'] + 1, '%s: 문서 가로 폭 %s > 창 %s' % (label, r['sw'], r['W']))
    ok(not r['bad'], '%s: %s' % (label, r['bad']))


def synth_results(n=12):
    """저장소에 미리 넣어 둘 가짜 결과(화면·복사 시험용)"""
    cards = ['A15', 'A45', 'L15', 'L60', 'L300', 'CALL', 'DC']
    L = []
    t0 = int(time.time() * 1000) - 3600 * 1000
    for i in range(n):
        c = cards[i % 7]
        out = ['alive', 'reco', 'alive', 'fail', 'reco', 'disc'][i % 6]
        r = {'id': 'x%d' % i, 'card': c, 'n': i // 7 + 1, 'sid': 'sidsidsid%d' % i, 'at': t0 + i * 60000, 'hide_at': t0 + i * 60000 + 1000, 'hide_src': 'visibilitychange', 'back_src': 'visibilitychange',
             'away_ms': 15000 + i * 700, 'det': {'ev': True, 'clk': i % 2 == 0}, 'evs': ['hide/hidden', 'blur', 'show/visible', 'focus'], 'rs_pre': 1, 'rs_back': 3 if out == 'reco' else 1,
             'close': {'where': '자리 비운 동안', 'code': 1006, 'clean': False, 'why': ''} if out == 'reco' else None, 'bg': {'sent': True, 'rs': 1, 'src': 'visibilitychange', 'err': ''},
             'out': out, 'first_ms': 800 if out == 'alive' else None, 'reco': {'via': 'return', 'attempts': 1, 'open_ms': 300, 'first_ms': 1500 + i * 10, 'in_away': False} if out == 'reco' else None,
             'gap_ms': 16000, 'tick_gap_ms': 15900, 'tick_skip': 14, 'srv': {'closes': [{'code': '1006', 'why': 'peer-closed', 'by': 'peer', 'conn': '1'}], 'replaced': [{'old_msg_age_ms': 16000, 'old_pong_age_ms': 4000}], 'max_pong_gap_ms': 5000, 'max_msg_gap_ms': 16000, 'bg_total': 3, 'bg_near': True},
             'short': False, 'intr': False, 'wl': [None, None]}
        if out == 'disc':
            r.update({'back_src': '새로 불러옴', 'nav': {'type': 'reload', 'discarded': False, 'hid': True}, 'srv': None})
        L.append(r)
    return L


RES_KEY = 'p0sock_results_v2'
PEND_KEY = 'p0sock_pending_v2'


def seed_init(results, env=''):
    return "try{localStorage.setItem('%s',%s)}catch(e){}" % (RES_KEY + ('_' + env if env else ''), json.dumps(json.dumps(results)))


def pstats(a):
    s = sorted(a)
    n = len(a)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    p95 = s[max(0, math.ceil(0.95 * n) - 1)]
    jit = sum(abs(a[i] - a[i - 1]) for i in range(1, n)) / (n - 1) if n > 1 else None
    return dict(n=n, min=s[0], max=s[-1], median=med, mean=sum(a) / n, p95=p95, jitter=jit)


# =====================================================================================
# 허브
# =====================================================================================
@test('hub_basic')
async def t_hub(env):
    ctx, pg, errs = await env.new_page('index.html', '?srv=https://x.example&ws=wss://y.example/ws', w=360, h=740)
    eq(await pg.get_attribute('meta[name=robots]', 'content'), 'noindex,nofollow')
    eq(await pg.get_attribute('html', 'lang'), 'ko')
    ok('P0-v2' in await pg.inner_text('#ver'), '버전 표기')
    h1 = await pg.get_attribute('#c-ping', 'href')
    h2 = await pg.get_attribute('#c-sock', 'href')
    ok(h1.startswith('ping.html') and 'srv=https' in h1, '핑 링크에 쿼리 전달: ' + h1)
    ok(h2.startswith('sock.html') and 'ws=wss' in h2, '소켓 링크에 쿼리 전달: ' + h2)
    txt = await pg.inner_text('main')
    ok('핑 시험' in txt and '소켓 시험' in txt and '복사' in txt and '붙여' in txt, '안내 글')
    await check_layout(pg, 'hub 360')
    await pg.screenshot(path=os.path.join(SCR, 'hub_360.png'), full_page=True)
    no_errs(errs, 'hub')


# =====================================================================================
# 핑 페이지
# =====================================================================================
@test('ping_stats_exact')
async def t_ping_stats(env):
    ctx, pg, errs = await env.new_page('ping.html', w=360, h=740)
    cases = [
        [50, 40, 60, 45, 55, 100, 48, 52, 47, 53, 51, 49, 150, 46, 54, 50, 50, 44, 56, 58],   # 짝수 20개
        [10, 30, 20, 50, 40],                                                                      # 홀수
        [7.5],                                                                                     # 한 개
        [100, 100, 100, 100],                                                                      # 지터 0
        list(range(1, 101)),                                                                       # p95 = 95
        [30, 10, 90, 10, 30, 20, 80, 5, 60, 25, 25, 25, 25, 25, 25, 25, 25, 25, 25, 1000],        # 튀는 값 1개
    ]
    for a in cases:
        got = await pg.evaluate('(a)=>P0PING.stats(a,2)', a)
        exp = pstats(a)
        for k in ('n', 'min', 'max', 'median', 'mean', 'p95'):
            ok(abs(got[k] - exp[k]) < 1e-9, 'stats %s %s: %r != %r' % (a[:4], k, got[k], exp[k]))
        if exp['jitter'] is None:
            ok(got['jitter'] is None, '한 개짜리 지터는 null')
        else:
            ok(abs(got['jitter'] - exp['jitter']) < 1e-9, '지터 %r != %r' % (got['jitter'], exp['jitter']))
        eq(got['fails'], 2, '실패 횟수는 그대로')
    e = await pg.evaluate('P0PING.stats([],5)')
    ok(e['median'] is None and e['p95'] is None and e['n'] == 0 and e['fails'] == 5, '빈 표본')
    # 순위법: 20개면 p95 = 19번째(정렬 뒤 인덱스 18)
    a = list(range(1, 21))
    eq(await pg.evaluate('(a)=>P0PING.pctRank(a,95)', a), 19, 'p95 순위법(20개)')
    eq(await pg.evaluate('(a)=>P0PING.pctRank(a,95)', a[::-1]), 19, 'p95 정렬 무관')
    no_errs(errs, 'stats')


async def verdict_text(pg, conn, seoul, tokyo, fra=None, bot=None, sf=0):
    await pg.evaluate('()=>{for(const id of ["seoul","tokyo","fra","bot"]) P0PING.setResult(id,[],0); }')
    await pg.click('#b-data' if conn == 'data' else '#b-wifi')
    for id_, v in (('seoul', seoul), ('tokyo', tokyo), ('fra', fra), ('bot', bot)):
        if v is not None:
            await pg.evaluate('([id,v,f])=>P0PING.setResult(id,Array(20).fill(v),f)', [id_, v, sf if id_ == 'seoul' else 0])
    return await pg.inner_text('#verdict')


@test('ping_verdict_branches')
async def t_ping_verdict(env):
    ctx, pg, errs = await env.new_page('ping.html', w=360, h=740)
    t = await verdict_text(pg, 'data', 40, 70, 250, 220)
    ok('✅ 서울 서버로 가도 좋아요' in t and '제안 기준' in t, '서울 40 → 통과: ' + t)
    ok('서울−도쿄' in t and '서울−독일(봇)' in t, '차이 줄: ' + t)
    ok('−30ms' in t and '서울이 빠름' in t, '서울−도쿄 = −30ms: ' + t)
    t = await verdict_text(pg, 'data', 60, 70)
    ok('✅' in t, '경계 60 은 통과: ' + t)
    t = await verdict_text(pg, 'data', 80, 60, 200, 230)
    ok('도쿄가 더 빨라요' in t and '✅' not in t and '제안 기준' in t, '서울 80·도쿄 60 → 도쿄: ' + t)
    t = await verdict_text(pg, 'data', 90, 90)
    ok('의논이 필요해요' in t and '✅' not in t and '도쿄가 더' not in t, '둘 다 90 → 의논: ' + t)
    t = await verdict_text(pg, 'data', 80, 70)
    ok('의논이 필요해요' in t, '서울 80·도쿄 70 (둘 다 60 초과) → 의논: ' + t)
    t = await verdict_text(pg, 'data', 61, 50)
    ok('도쿄가 더 빨라요' in t, '서울 61·도쿄 50 → 도쿄: ' + t)
    t = await verdict_text(pg, 'data', 90, None)
    ok('의논이 필요해요' in t and '도쿄 값 없음' in t, '도쿄 값 없으면 의논: ' + t)
    t = await verdict_text(pg, 'wifi', 20, 20, 100, 100)
    ok('참고만' in t and '데이터' in t and '✅' not in t, '와이파이면 참고만: ' + t)
    t = await verdict_text(pg, 'data', 40, 70, sf=8)
    ok('✅' in t and '흔들릴 수' in t, '실패 많으면 경고 덧붙임: ' + t)
    # 서울 값이 하나도 없을 때
    await pg.evaluate('()=>{P0PING.setResult("seoul",[],20)}')
    t = await pg.inner_text('#verdict')
    ok('서울 값을 못 쟀어요' in t and '✅' not in t, '서울 전부 실패: ' + t)
    # 연결 안 고른 채로는 시작 못 함
    ctx2, pg2, errs2 = await env.new_page('ping.html', w=360, h=740)
    ok(await pg2.is_disabled('#b-start'), '연결 고르기 전엔 [시작] 비활성')
    ok('먼저' in await pg2.inner_text('#hint'), '안내 문구')
    await pg2.click('#b-data')
    ok(not await pg2.is_disabled('#b-start'), '고른 뒤엔 활성')
    no_errs(errs, 'verdict')
    no_errs(errs2, 'verdict2')


@test('ping_parse_srv')
async def t_ping_srv(env):
    ctx, pg, errs = await env.new_page('ping.html', w=360, h=740)
    bad = ['http://echo.example', 'javascript:alert(1)', 'ftp://x.example', 'https://', 'https:///x', 'wss://x.example/ws', 'data:text/html,<b>', '//x.example', 'x.example', 'https://u:p@x.example',
           'HTTP://x.example', 'https://"><img src=x onerror=window.__pwn=1>.example']
    for b in bad:
        r = await pg.evaluate('(s)=>P0PING.parseSrv(s)', b)
        ok(r.get('err'), 'srv 거부돼야 함: %r → %r' % (b, r))
    r = await pg.evaluate('(s)=>P0PING.parseSrv(s)', 'https://echo.example:8443/path?x=1#y')
    eq(r.get('origin'), 'https://echo.example:8443', 'origin 만 남김')
    r = await pg.evaluate('(s)=>P0PING.parseSrv(s)', None)
    ok(r.get('none'), '없으면 none')
    # 화면: 나쁜 srv 는 쓰지 않고 이유를 보여 준다, 대상 카드는 4개
    for q in ('?srv=http://echo.example', '?srv=javascript:alert(1)'):
        ctx2, pg2, errs2 = await env.new_page('ping.html', q, w=360, h=740)
        eq(await pg2.locator('#list .t').count(), 4, q + ' 카드 수')
        ok('https://' in await pg2.inner_text('#srvmsg'), '거부 이유 표시')
        no_errs(errs2, q)
    ctx3, pg3, errs3 = await env.new_page('ping.html', '?srv=https://echo.test', w=360, h=740)
    eq(await pg3.locator('#list .t').count(), 6, 'https srv → 카드 6개')
    txt = await pg3.inner_text('#list')
    ok('HTTP (/ping)' in txt and 'WebSocket' in txt, '두 줄 추가')
    # 악성 호스트가 화면 DOM 으로 들어가지 않는다
    ctx4, pg4, errs4 = await env.new_page('ping.html', '?srv=' + 'https://%22%3E%3Cimg%20src=x%20onerror=window.__pwn=1%3E.example', w=360, h=740)
    ok(await pg4.evaluate('window.__pwn===undefined && document.querySelectorAll("main img").length===0'), '악성 srv 가 실행되지 않음')
    no_errs(errs, 'srv'), no_errs(errs3, 'srv3'), no_errs(errs4, 'srv4')


VULTR = {'sel-kor-ping.vultr.com': 'seoul', 'hnd-jp-ping.vultr.com': 'tokyo', 'fra-de-ping.vultr.com': 'fra', 'hth3thmujs.apps.bot-hosting.cloud': 'bot'}
CORS = {'access-control-allow-origin': '*'}


async def install_ping_routes(ctx, delays, head_ok, log, quick=()):
    async def h(route):
        req = route.request
        key = VULTR[urlparse(req.url).hostname]
        log[key].append((req.method, req.url, dict(await req.all_headers())))
        d = delays.get(key, 0) / 1000.0
        if d:
            await asyncio.sleep(d)
        try:
            if req.method == 'HEAD':
                if head_ok:
                    await route.fulfill(status=200, headers=dict(CORS, **{'content-type': 'text/html'}), body='')
                else:
                    await route.abort('failed')                  # HEAD 거절(CORS 막힘·메서드 거절) → 브라우저 쪽에선 같은 TypeError
            else:
                if key == 'bot' and head_ok:
                    await route.fulfill(status=200, headers=dict(CORS, **{'content-type': 'application/json'}), body='{"ok":true}')
                else:
                    await route.fulfill(status=200, headers={'content-type': 'text/html'}, body='<html>' + 'x' * 1200 + '</html>')   # no-cors 라 본문은 못 읽는다
        except Exception:
            pass
    for host in VULTR:
        await ctx.route('https://%s/**' % host, h)


async def install_srv_routes(ctx, pg, ws_delay=0.02):
    async def http(route):
        await asyncio.sleep(0.02)
        await route.fulfill(status=200, headers=dict(CORS, **{'content-type': 'application/json', 'cache-control': 'no-store'}), body='{"t":1}')
    await ctx.route('https://echo.test/ping**', http)

    def on_ws(ws):
        def onm(m):
            try:
                j = json.loads(m)
            except Exception:
                return
            ack = json.dumps({'t': 'ack', 'k': 'hb', 'n': j.get('n'), 'c': j.get('c'), 'srv_ms': int(time.time() * 1000)})
            asyncio.get_event_loop().call_later(ws_delay, lambda: ws.send(ack))
        ws.on_message(onm)
    await pg.route_web_socket(re.compile(r'wss://echo\.test/ws.*'), on_ws)


async def card_stats(pg):
    """화면 카드 → {id: {text}}"""
    return await pg.evaluate("""()=>{const o={};document.querySelectorAll('#list .t').forEach(d=>{o[d.getAttribute('data-id')]=d.innerText});return o}""")


@test('ping_e2e_head_and_get_fallback', retry=True)
async def t_ping_e2e(env):
    log_a = {k: [] for k in VULTR.values()}
    log_b = {k: [] for k in VULTR.values()}
    delays = {'seoul': 20, 'tokyo': 60, 'fra': 100, 'bot': 140}
    fetch_spy = "window.__fl=[];(function(){var f=window.fetch;window.fetch=function(u,i){window.__fl.push([String(u),i&&i.cache,i&&i.method,i&&i.mode,i&&i.credentials]);return f.apply(this,arguments)}})();"
    async def setupA(c, p):
        await install_srv_routes(c, p)
    ctxA, pgA, errsA = await env.new_page('ping.html', '?srv=https://echo.test', w=360, h=740, init=fetch_spy, allow=('ERR_FAILED', 'CORS', 'Failed to load'), setup=setupA)
    ctxB, pgB, errsB = await env.new_page('ping.html', '', w=360, h=740, allow=('ERR_FAILED', 'CORS', 'Failed to load'))
    await install_ping_routes(ctxA, delays, True, log_a)
    await install_ping_routes(ctxB, delays, False, log_b)
    load0 = load()
    for pg in (pgA, pgB):
        await pg.click('#b-data')
        await pg.click('#b-start')
    t0 = time.time()
    await asyncio.gather(poll(pgA, "document.querySelector('#prog').innerText.startsWith('끝났어요')", 90, msg='A 끝'),
                         poll(pgB, "document.querySelector('#prog').innerText.startsWith('끝났어요')", 90, msg='B 끝'))
    el = time.time() - t0
    # --- A: HEAD 허용 ---
    for k in VULTR.values():
        eq(len(log_a[k]), 23, 'A %s 요청 수(데우기 3 + 측정 20)' % k)
        ok(all(m == 'HEAD' for m, _, _ in log_a[k]), 'A %s 는 HEAD 만 썼다' % k)
        cbs = [re.search(r'cb=([^&]+)', u).group(1) for _, u, _ in log_a[k]]
        eq(len(set(cbs)), len(cbs), 'A %s 캐시 우회 쿼리 cb 가 매번 다르다' % k)
    cs = await card_stats(pgA)
    ok(set(cs.keys()) == {'seoul', 'tokyo', 'fra', 'bot', 'srvhttp', 'srvws'}, '카드 6개: ' + str(list(cs)))
    meds = {}
    for k in cs:
        m = re.search(r'(\d+) ms', cs[k])
        ok(m, k + ' 중앙값 표시: ' + cs[k])
        meds[k] = int(m.group(1))
        ok('실패\n0/20' in cs[k], '%s 실패 0/20: %r' % (k, cs[k]))
    exp = {'seoul': 20, 'tokyo': 60, 'fra': 100, 'bot': 140}
    for k, d in exp.items():
        ok(d - 2 <= meds[k] <= d + 150, '%s 중앙값 %s ms (지연 %s 주입, load %s)' % (k, meds[k], d, load0))
    ok(meds['seoul'] < meds['tokyo'] < meds['fra'] < meds['bot'], '순서 보존 %s' % meds)
    ok(meds['srvhttp'] >= 18 and meds['srvws'] >= 18, 'srv 두 줄도 잼 %s' % meds)
    fl = await pgA.evaluate('window.__fl')
    ok(len(fl) >= 92 and all(x[1] == 'no-store' and x[3] == 'cors' and x[2] == 'HEAD' and x[4] == 'omit' for x in fl), 'fetch 옵션(no-store·cors·HEAD·omit): %s' % fl[:2])
    # 복사 글
    out = await pgA.input_value('#out')
    ok(out.startswith('[핑시험 P0-v2]') and '날짜(KST)' in out and '데이터(LTE·5G)' in out, '복사 글 머리: ' + out[:120])
    ok(re.search(r'① 서울 \(Vultr\): 중앙 \d+ · p95 \d+ · 지터 [\d.]+ · 최소 \d+ · 최대 \d+ · 실패 0/20', out), '서울 줄: ' + out)
    ok('판정:' in out and '제안 기준' in out, '판정 줄')
    # --- B: HEAD 거절 → GET(no-cors) 로 물러남 ---
    for k in VULTR.values():
        methods = [m for m, _, _ in log_b[k]]
        eq(methods.count('HEAD'), 1, 'B %s HEAD 는 처음 한 번만 시도' % k)
        eq(methods.count('GET'), 23, 'B %s GET 23번' % k)
    csb = await card_stats(pgB)
    for k in VULTR.values():
        ok('GET' in csb[k] and '실패\n0/20' in csb[k], 'B %s: GET 으로 쟀다는 표시와 실패 0: %r' % (k, csb[k]))
        m = re.search(r'(\d+) ms', csb[k])
        ok(m and exp[k] - 2 <= int(m.group(1)) <= exp[k] + 150, 'B %s 중앙값 %s' % (k, m and m.group(1)))
    outb = await pgB.input_value('#out')
    ok('(GET)' in outb, '복사 글에 GET 표시')
    no_errs(errsA, 'A'), no_errs(errsB, 'B')
    print('      · ping e2e 두 페이지 병행 %.1fs, uptime load %s → %s' % (el, load0, load()))


@test('ping_timeout_fail_warmup_stop', retry=True)
async def t_ping_timeout(env):
    cnt = {'seoul': 0, 'tokyo': 0}
    log = {k: [] for k in VULTR.values()}
    ctx, pg, errs = await env.new_page('ping.html', '', w=360, h=740, allow=('ERR_FAILED', 'CORS', 'Failed to load', 'net::'))
    await install_ping_routes(ctx, {'seoul': 5, 'tokyo': 5, 'fra': 5, 'bot': 5}, True, log)

    async def special(route):
        host = urlparse(route.request.url).hostname
        key = VULTR[host]
        if key == 'seoul':
            cnt['seoul'] += 1
            if cnt['seoul'] == 9:                       # 데우기 3 다음 6번째 측정 요청 = 한 번만 4초를 넘겨 늦게 준다
                await asyncio.sleep(4.8)
                try:
                    await route.fulfill(status=200, headers=CORS, body='')
                except Exception:
                    pass
                return
        if key == 'tokyo':
            cnt['tokyo'] += 1
            if cnt['tokyo'] == 1:                       # 데우기 첫 요청은 일부러 망가뜨린다 → 결과에 안 세어야 함
                await route.abort('failed')
                return
        if key == 'fra':
            await route.abort('failed')                 # 프랑크푸르트는 전부 실패
            return
        await route.fallback()
    for host in ('sel-kor-ping.vultr.com', 'hnd-jp-ping.vultr.com', 'fra-de-ping.vultr.com'):
        await ctx.route('https://%s/**' % host, special)
    await pg.click('#b-data')
    await pg.click('#b-start')
    await poll(pg, "document.querySelector('#prog').innerText.startsWith('끝났어요')", 90, msg='끝')
    cs = await card_stats(pg)
    ok('실패\n1/20' in cs['seoul'] and '(19회)' not in cs['seoul'], '서울: 시간 초과 한 번이 실패로 셈: ' + cs['seoul'])
    s = await pg.evaluate('P0PING.state.targets.map(t=>[t.id,t.stats.n,t.stats.fails])')
    d = {a: (b, c) for a, b, c in s}
    eq(d['seoul'], (19, 1), '서울 n/fails')
    eq(d['tokyo'], (20, 0), '도쿄: 데우기 실패는 제외')
    eq(d['fra'], (0, 20), '프랑크푸르트 전부 실패')
    ok('실패\n20/20' in cs['fra'] and 'ms' not in cs['fra'] and 'GET' not in cs['fra'], 'fra 카드: ' + cs['fra'])
    out = await pg.input_value('#out')
    ok('③ 프랑크푸르트·독일 (Vultr, 비교용): 값 없음' in out, '복사 글의 값 없음 줄: ' + out)
    ok('✅' in await pg.inner_text('#verdict'), '서울 19회 중앙값 통과')
    # 멈춤·다시
    await pg.click('#b-again')
    ok(await pg.evaluate('P0PING.state.targets.every(t=>!t.ran)'), '[다시] 로 비움')
    ok(not await pg.is_disabled('#b-start'), '다시 시작 가능')
    await pg.click('#b-start')
    await poll(pg, "P0PING.state.targets[0].samples.length>=2", 10, msg='진행')
    await pg.click('#b-stop')
    await poll(pg, "!P0PING.state.running", 6, msg='멈춤')
    n_at_stop = await pg.evaluate('P0PING.state.targets[0].samples.length')
    ok(n_at_stop < 20, '멈추면 중간에서 끝: %d' % n_at_stop)
    await asyncio.sleep(0.6)
    eq(await pg.evaluate('P0PING.state.targets[0].samples.length'), n_at_stop, '멈춘 뒤엔 더 안 늘어남')
    ok('이어서' in await pg.inner_text('#b-start'), '[이어서 시작] 표시')
    ok('끝났어요' not in await pg.inner_text('#prog'), '멈춤인데 끝났다고 하지 않음')
    no_errs(errs, 'timeout')


@test('ping_copy_fallbacks')
async def t_ping_copy(env):
    init = """window.__copied=[];
    Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true});
    document.execCommand=function(c){var a=document.activeElement;window.__copied.push({c:c,id:a&&a.id,sel:a&&a.value&&a.value.substring(a.selectionStart,a.selectionEnd)});return window.__execOk!==false;};"""
    ctx, pg, errs = await env.new_page('ping.html', w=360, h=740, init=init)
    await pg.click('#b-copy')
    ok('아직 복사할' in await pg.inner_text('#copymsg'), '결과 없을 때 안내')
    await pg.click('#b-data')
    await pg.evaluate('()=>{P0PING.setResult("seoul",[30,31,32,33,34,35,36,37,38,39,40],0)}')
    txt = await pg.input_value('#out')
    ok(txt.startswith('[핑시험 P0-v2]'), '글 표식')
    await pg.click('#b-copy')
    cp = await pg.evaluate('window.__copied')
    eq(len(cp), 1, 'execCommand 한 번')
    eq(cp[0]['c'], 'copy')
    eq(cp[0]['id'], 'out', '글상자가 선택된 채로 복사')
    eq(cp[0]['sel'], txt, '전체가 선택됨')
    ok('복사했어요' in await pg.inner_text('#copymsg'), '성공 안내')
    await pg.evaluate('window.__execOk=false')
    await pg.click('#b-copy')
    ok('길게 눌러' in await pg.inner_text('#copymsg'), '실패하면 길게 눌러 복사 안내')
    ok(await pg.get_attribute('#out', 'readonly') is not None, 'readonly 복원')
    # clipboard.writeText 가 거절돼도 폴백
    ctx2, pg2, errs2 = await env.new_page('ping.html', w=360, h=740, init="window.__copied=[];Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('denied'))},configurable:true});document.execCommand=function(c){window.__copied.push(c);return true};")
    await pg2.click('#b-data')
    await pg2.evaluate('()=>{P0PING.setResult("seoul",[30,31,32,33,34,35,36,37,38,39,40],0)}')
    await pg2.click('#b-copy')
    eq(await pg2.evaluate('window.__copied'), ['copy'], '거절 → execCommand 폴백')
    # 진짜 클립보드(권한 허용)
    ctx3, pg3, errs3 = await env.new_page('ping.html', w=360, h=740, perms=['clipboard-read', 'clipboard-write'])
    await pg3.click('#b-data')
    await pg3.evaluate('()=>{P0PING.setResult("seoul",[30,31,32,33,34,35,36,37,38,39,40],0)}')
    await pg3.click('#b-copy')
    got = await pg3.evaluate('navigator.clipboard.readText()')
    eq(got, await pg3.input_value('#out'), '실제 클립보드 내용')
    no_errs(errs, 'c1'), no_errs(errs2, 'c2'), no_errs(errs3, 'c3')


@test('ping_layout_360')
async def t_ping_layout(env):
    for (w, h) in ((360, 740), (412, 915)):
        ctx, pg, errs = await env.new_page('ping.html', '?srv=https://echo.test', w=w, h=h)
        await check_layout(pg, 'ping 빈 화면 %d' % w)
        await pg.click('#b-data')
        await pg.evaluate('()=>{const L=[["seoul",[41,43,39,60,44]],["tokyo",[88,90,85,120,99]],["fra",[200,210,205]],["bot",[260,250]],["srvhttp",[45,47]],["srvws",[44,46]]];L.forEach(([i,a])=>P0PING.setResult(i,a.concat(Array(20-a.length).fill(50)),2))}')
        await check_layout(pg, 'ping 결과 %d' % w)
        if w == 360:
            await pg.screenshot(path=os.path.join(SCR, 'ping_360.png'), full_page=True)
        no_errs(errs, 'ping layout')
    ctx, pg, errs = await env.new_page('ping.html', '', w=844, h=390)
    await pg.click('#b-wifi')
    await pg.evaluate('()=>{P0PING.setResult("seoul",[41,43,39,60,44],1)}')
    await check_layout(pg, 'ping 가로 844')
    # 다크 모드에서도 읽히는지(대비) — 배경/글자색 계산
    ctx, pg, errs = await env.new_page('ping.html', '', w=360, h=740)
    await pg.emulate_media(color_scheme='dark')
    await pg.click('#b-data')
    await pg.evaluate('()=>{P0PING.setResult("seoul",[41,43,39,60,44],1)}')
    await pg.screenshot(path=os.path.join(SCR, 'ping_dark_360.png'), full_page=True)
    bad = await pg.evaluate("""()=>{
      function lum(c){const m=c.match(/[\\d.]+/g).map(Number);const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(m[0])+.7152*f(m[1])+.0722*f(m[2])}
      function bg(e){while(e){const c=getComputedStyle(e).backgroundColor;const m=c.match(/[\\d.]+/g).map(Number);if(m.length<4||m[3]>0.5)return c;e=e.parentElement}return 'rgb(255,255,255)'}
      const out=[];document.querySelectorAll('main *').forEach(e=>{const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());if(!own)return;const r=e.getBoundingClientRect();if(!r.width)return;
        const a=lum(getComputedStyle(e).color),b=lum(bg(e));const cr=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);if(cr<4.5&&!e.disabled)out.push(e.tagName+'#'+e.id+' '+cr.toFixed(2))});return out.slice(0,8)}""")
    ok(not bad, '다크 대비 4.5 미만: %s' % bad)


# =====================================================================================
# 소켓 페이지
# =====================================================================================
async def srv_page(env, query_extra='', init=None, clock=False, **kw):
    fe = env.fe
    q = '?ws=' + fe.ws_url('/ws') + query_extra
    return await env.new_page('sock.html', q, init=(VIS_INIT + (init or '')), clock=clock, **kw)


async def wait_connected(pg, timeout=8):
    await poll(pg, "(()=>{const s=P0SOCK.snap();return s.C.rs===1&&s.rtts.length>0})()", timeout, msg='연결+RTT')


@test('sock_connect_tick_hb')
async def t_sock_connect(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, w=412, h=915)
    await wait_connected(pg)
    await asyncio.sleep(2.2)
    s = await snap(pg)
    eq(s['hello']['conn'], 1)
    ok(re.match(r'^[a-z0-9]{12}-[a-z0-9]{4}$', s['sid']), 'sid = 기본 12자 + 창 4자: ' + s['sid'])
    ok(s['srvOff'] is not None, '서버 시각 오프셋')
    ok(len(s['rtts']) >= 2 and all(0 <= r < 500 for r in s['rtts']), 'hb RTT: %s' % s['rtts'])
    st = await pg.inner_text('#status')
    ok('🟢 연결' in st, '상태 표시: ' + st)
    ok(re.search(r'\d{2}:\d{2}:\d{2} KST', st), '서버 시각: ' + st)
    mode = await pg.inner_text('#mode')
    ok('내 서버 모드' in mode, mode)
    ok(s['C']['id'] == 1, '재접속 없이 1번 연결 유지')
    # 서버가 hb 를 받았고 sid 로 기록이 남는다
    j = fe.sessions[s['sid']].summary()
    ok(j['last_msg_ms'] and j['opened'] == 1, '서버 기록')
    # 마지막 수신이 계속 갱신(1초 안쪽)
    last = float(re.search(r'([\d.]+)초 전', st).group(1))
    ok(last < 2.0, '마지막 수신 %s초 전' % last)
    no_errs(errs, 'connect')


@test('sock_silence_auto_reconnect', retry=True)
async def t_sock_silence(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, w=412, h=915)
    await wait_connected(pg)
    sid = (await snap(pg))['sid']
    t0 = time.time()
    fe.set_silence(True, sid)
    await poll(pg, "P0SOCK.snap().C.id>=2", 12, msg='3.5초 무수신 → 재접속')
    dt = time.time() - t0
    ok(3.0 <= dt <= 7.5, '무수신 재접속까지 %.1fs (load %s)' % (dt, load()))
    await poll(pg, "(()=>{const c=P0SOCK.snap().conns;return c.length>=2&&c[1].firstRecvAt>0})()", 6, msg='새 연결 첫 수신')
    s = await snap(pg)
    cs = s['conns']
    eq(cs[1]['reason'], 'silence', '재접속 이유')
    ok(any(e['k'] == 'silence' for e in s['log']), '로그에 silence')
    ok(cs[1]['openAt'] > 0 and cs[1]['firstRecvAt'] >= cs[1]['openAt'], '열림·첫 수신 시각 기록(침묵 중에도 hello 는 옴)')
    sm = fe.sessions[sid].summary()
    eq(sm['opened'], 2, '서버: 같은 sid 로 연결이 두 번 열림')
    ok(any(c['conn'] == 1 for c in sm['closes']), '서버: 옛 연결 닫힘 기록 %s' % sm['closes'])
    fe.set_silence(False, sid)
    await asyncio.sleep(2.5)
    c2 = (await snap(pg))['C']['id']
    await asyncio.sleep(2.5)
    eq((await snap(pg))['C']['id'], c2, '침묵을 풀면 재접속이 멈춤')
    ok('🟢' in await pg.inner_text('#s-state'), '다시 🟢')
    # 백오프: 서버가 연결 자체를 못 받으면 0 → 0.5 → 1 → 2 → 4 초 간격
    await fe.close_conns(1011, sid)
    await poll(pg, "P0SOCK.snap().C.id>=" + str(c2 + 1), 6, msg='서버가 닫으면 바로 재접속')
    no_errs(errs, 'silence')


def hide_flow_expr():
    return "document.querySelector('[data-start=A15]')"


@test('sock_hide_return_socket_alive', retry=True)
async def t_sock_alive(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg)
    await pg.click('[data-start=A15]')
    ok(not await pg.is_visible('#arm.hide'), '안내 상자가 뜸')
    arm_txt = await pg.inner_text('#arm')
    ok('준비됐어요' in arm_txt and '지금부터' in arm_txt and '15초' in arm_txt and '시간은 자동으로' in arm_txt, '큰 안내 글: ' + arm_txt)
    ok(await pg.evaluate("[...document.querySelectorAll('[data-start]')].every(b=>b.disabled)"), '한 번에 한 카드만: 다른 [시작] 비활성')
    await pg.evaluate("__vis('hidden')")
    await pg.clock.fast_forward(15000)
    await asyncio.sleep(0.8)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 12, msg='결과 한 줄')
    r = (await snap(pg))['results'][0]
    eq(r['card'], 'A15'), eq(r['out'], 'alive', '소켓이 그대로 살아 있음')
    ok(14500 <= r['away_ms'] <= 20000, '비운 시간(Date.now 차이) %s' % r['away_ms'])
    ok(r['det']['ev'] is True and r['det']['clk'] is True, '이벤트·시계 둘 다 감지: %s' % r['det'])
    eq((r['rs_pre'], r['rs_back']), (1, 1), 'readyState 숨기기 직전/복귀 직후')
    ok(r['bg'] and r['bg']['sent'] is True, 'bg 힌트 보냄')
    eq(r['hide_src'], 'visibilitychange')
    ok(r['first_ms'] is not None and r['first_ms'] < 3000, '복귀 뒤 첫 수신 %s' % r['first_ms'])
    ok(r['close'] is None, '닫힘 없음')
    ok(r['srv'] and not r['srv'].get('err'), '서버 기록 붙음: %s' % r['srv'])
    ok(r['srv']['bg_total'] >= 1, '서버가 bg 힌트를 받음(대조): %s' % r['srv'])
    ok(r['srv']['bg_near'] is True, 'bg 힌트가 숨김 시각 근처')
    ok(r['srv']['closes'] == [] and r['srv']['replaced'] == [], '서버: 끊김·대체 없음')
    ok('visibilitychange' in ' '.join(r['evs']) or 'hide/hidden' in r['evs'] or any('hide' in e for e in r['evs']), '이벤트 목록 %s' % r['evs'])
    # 카드 집계와 결과 줄
    card = await pg.inner_text('[data-card=A15]')
    ok('1번 중' in card and '그대로 1' in card and '다시 붙음 0' in card, '집계: ' + card)
    ok(not await pg.is_disabled('[data-start=A15]'), '끝나면 다시 시작 가능')
    ok('그대로 열려 있음' in await pg.inner_text('#results'), '결과 줄')
    # 요약 글
    summ = await pg.evaluate('P0SOCK.summaryText()')
    ok(summ.startswith('[소켓시험 P0-v2] 요약') and 'A15 다른 앱 15초: 1번 중' in summ and '이벤트로 알아챔 1 · 시계 끊김으로 알아챔 1' in summ, summ)
    no_errs(errs, 'alive')


@test('sock_hide_closed_while_away_reconnect', retry=True)
async def t_sock_closed_away(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg)
    sid = (await snap(pg))['sid']
    await pg.click('[data-start=A45]')
    await pg.evaluate("__vis('hidden')")
    await fe.close_conns(1011, sid, 'test-close')
    await poll(pg, "P0SOCK.snap().C.rs===3", 6, msg='숨은 동안 onclose 도착')
    await asyncio.sleep(0.6)
    s = await snap(pg)
    eq(s['C']['id'], 1, '자리 비운 동안엔 다시 붙지 않는다')
    await pg.clock.fast_forward(46000)
    await asyncio.sleep(0.4)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 12, msg='결과')
    r = (await snap(pg))['results'][0]
    eq(r['out'], 'reco')
    eq(r['rs_back'], 3, '복귀 직후 readyState 3 = 죽어 있었다')
    ok(r['close'] and r['close']['where'] == '자리 비운 동안' and r['close']['code'] == 1011 and r['close']['clean'] in (True, False), '닫기 코드: %s' % r['close'])
    ok(r['reco']['via'] == 'return' and r['reco']['attempts'] == 1 and r['reco']['in_away'] is False, '재접속 정보: %s' % r['reco'])
    ok(r['reco']['first_ms'] < 3000 and r['reco']['open_ms'] <= r['reco']['first_ms'], '재접속 소요 %s' % r['reco'])
    ok(r['away_ms'] >= 45000, '45초 카드: %s' % r['away_ms'])
    ok(r['short'] is False)
    ok(any('1011' in str(c) for c in r['srv']['closes']), '서버 기록에 닫힘: %s' % r['srv'])
    ok(r['srv']['replaced'] == [], '이미 닫혔으니 대체는 없음')
    # 새 연결 hello 의 prev 가 화면에 나온다
    ok('1011' in await pg.inner_text('#s-prev'), '서버가 기억하는 이전 연결 표시: ' + await pg.inner_text('#s-prev'))
    card = await pg.inner_text('[data-card=A45]')
    ok('다시 붙음 1' in card and '재접속 중앙값' in card and '초' in card, card)
    no_errs(errs, 'closed-away')


@test('sock_return_dead_socket_silence_rule', retry=True)
async def t_sock_dead(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg)
    sid = (await snap(pg))['sid']
    await pg.click('[data-start=L15]')
    await pg.evaluate("__vis('hidden')")
    fe.set_silence(True, sid)                    # 소켓은 열려 보이지만 서버 응답이 없다(= 죽은 소켓)
    await pg.clock.fast_forward(16000)
    await asyncio.sleep(0.4)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 14, msg='결과')
    r = (await snap(pg))['results'][0]
    eq(r['out'], 'reco')
    eq(r['rs_back'], 1, '복귀 직후엔 열려 보였다')
    eq(r['reco']['via'], 'silence', '3.5초 무수신 규칙으로 닫고 재접속')
    ok(3300 <= r['reco']['first_ms'] <= 8000, '복귀→새 연결 첫 수신 %s ms' % r['reco']['first_ms'])
    ok(r['reco']['open_ms'] >= 3300, '열림까지 %s' % r['reco']['open_ms'])
    ok(r['srv'] and not r['srv'].get('err') and r['srv']['conns'] == 2, '서버 기록: 연결 두 번 %s' % r['srv'])
    ok(any(str(c['conn']) == '1' for c in r['srv']['closes']), '서버 기록: 옛 연결이 닫힘(클라가 닫음) %s' % r['srv'])
    fe.set_silence(False, sid)
    no_errs(errs, 'dead')


@test('sock_clock_gap_only_detection', retry=True)
async def t_sock_clock_only(env):
    fe = await env.start_fe()
    init = ""
    ctx, pg, errs = await env.new_page('sock.html', '?ws=' + fe.ws_url('/ws'), clock=True, w=412, h=915)   # 숨김 이벤트 흉내 없음
    await wait_connected(pg)
    await pg.click('[data-start=L60]')
    await pg.clock.fast_forward(61000)
    await poll(pg, "P0SOCK.snap().results.length>=1", 14, msg='결과')
    r = (await snap(pg))['results'][0]
    eq(r['hide_src'], 'clock', '숨김을 이벤트로 못 봤다')
    ok(r['det']['ev'] is False and r['det']['clk'] is True, '시계 끊김으로만 감지: %s' % r['det'])
    ok(r['away_ms'] >= 60000, '비운 시간 %s' % r['away_ms'])
    eq(r['bg']['sent'], False)
    ok('이벤트 없음' in r['bg']['err'], 'bg 못 보낸 이유')
    ok(r['out'] in ('alive', 'reco'), r['out'])
    # 이벤트 없이는 요약의 감지 합계가 따로 나온다
    summ = await pg.evaluate('P0SOCK.summaryText()')
    ok('이벤트로 알아챔 0 · 시계 끊김으로 알아챔 1' in summ, summ)
    # 시험을 안 건 상태의 시계 끊김은 결과를 만들지 않는다
    await pg.clock.fast_forward(30000)
    await asyncio.sleep(1.0)
    eq(len((await snap(pg))['results']), 1, '카드를 안 눌렀으면 기록 없음')
    no_errs(errs, 'clock-only')


@test('sock_freeze_resume_cdp', retry=True)
async def t_sock_freeze(env):
    """CDP Page.setWebLifecycleState 로 얼려 본다. 이 헤드리스 크로미움은 "보이는" 탭을 얼리지 않아(아래에서 확인) 효과가 없으면
    freeze/resume 이벤트를 직접 발생시키고 시계를 건너뛰어 같은 경로를 확인한다 — 어느 쪽으로 검사했는지 출력한다."""
    fe = await env.start_fe()
    ctx, pg, errs = await env.new_page('sock.html', '?ws=' + fe.ws_url('/ws'), clock=True, w=412, h=915, init=VIS_INIT)
    await wait_connected(pg)
    await pg.click('[data-start=A15]')
    cdp = await ctx.new_cdp_session(pg)
    await cdp.send('Page.setWebLifecycleState', {'state': 'frozen'})
    await asyncio.sleep(3.0)
    await cdp.send('Page.setWebLifecycleState', {'state': 'active'})
    await asyncio.sleep(0.8)
    log0 = ' '.join(e['k'] + ':' + e['d'] for e in (await snap(pg))['log'])
    via = 'CDP'
    if 'hide freeze' not in log0:
        via = '합성 freeze/resume 이벤트 + 시계 건너뛰기(CDP 동결은 이 환경에서 적용 안 됨)'
        await pg.evaluate("document.dispatchEvent(new Event('freeze'))")        # 실제로는 숨겨진 뒤에 얼려진다
        await pg.evaluate("__vis('hidden')")
        await pg.clock.fast_forward(15000)
        await asyncio.sleep(0.5)
        await pg.evaluate("document.dispatchEvent(new Event('resume'))")
        await pg.evaluate("__vis('visible')")
    print('      · freeze 검사 방식: ' + via)
    await poll(pg, "P0SOCK.snap().results.length>=1", 14, msg='결과')
    s = await snap(pg)
    r = s['results'][0]
    log = ' '.join(e['k'] + ':' + e['d'] for e in s['log'])
    # 실제로 얼렸다 깨우면(화면은 계속 보임) resume 이 곧 복귀. 합성 경로에서는 resume 이 숨김 중에 오므로 복귀로 안 치고 visibilitychange 가 복귀다.
    ok('hide freeze' in log and ('show resume' in log or 'ignored/resume' in log), 'freeze/resume 이벤트를 받았다: ' + log[-300:])
    ok(r['hide_src'] == 'freeze' and r['back_src'] in ('resume', 'visibilitychange') and r['det']['ev'] is True, '%s/%s' % (r['hide_src'], r['back_src']))
    ok(r['away_ms'] >= 2800, '얼어 있던 시간 %s' % r['away_ms'])
    ok(r['det']['clk'] is True, '2초 넘는 정지는 시계 끊김도 감지: %s' % r['det'])
    ok(r['out'] in ('alive', 'reco'), r['out'])
    no_errs(errs, 'freeze')


@test('sock_reload_closes_pending_as_discarded')
async def t_sock_reload(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, w=412, h=915)
    await wait_connected(pg)
    sid0 = (await snap(pg))['sid']
    await pg.click('[data-start=A15]')
    await pg.evaluate("__vis('hidden')")
    ok(await pg.evaluate("localStorage.getItem('p0sock_pending_v2')") is not None, '숨기기 직전 진행 중 기록이 저장됨')
    p = json.loads(await pg.evaluate("localStorage.getItem('p0sock_pending_v2')"))
    ok(p['card'] == 'A15' and p['sid'] == sid0 and p['n'] == 1 and p['hideAt'], 'pending 내용 %s' % p)
    await asyncio.sleep(1.2)
    await pg.reload()
    await pg.wait_for_function('window.P0SOCK!==undefined')
    s = await snap(pg)
    eq(len(s['results']), 1)
    r = s['results'][0]
    eq((r['card'], r['n'], r['out']), ('A15', 1, 'disc'))
    eq(r['nav']['type'], 'reload')
    ok(r['nav']['discarded'] is False and r['nav']['hid'] is True, 'nav %s' % r['nav'])
    ok(1000 <= r['away_ms'] <= 15000, '경과 %s' % r['away_ms'])
    eq(s['sid'], sid0, '새로 불러와도 sid 는 유지')
    eq(await pg.evaluate("localStorage.getItem('p0sock_pending_v2')"), None, '마감 뒤 pending 삭제')
    card = await pg.inner_text('[data-card=A15]')
    ok('새로 불러옴 1' in card, card)
    ok('창이 새로 불러와짐' in await pg.inner_text('#results'))
    ok(not await pg.is_disabled('[data-start=A15]'), '이어서 사용 가능')
    ok(s['trial'] is None)
    # 두 번째: 숨김 이벤트를 못 본 채 지워진 경우(armed 만 저장돼 있음)
    await pg.evaluate("localStorage.setItem('p0sock_pending_v2', JSON.stringify({card:'A45',n:1,sid:'zzzzzzzz',armedAt:Date.now()-5000,hideAt:null,fin:false}))")
    await pg.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws')))
    await pg.wait_for_function('window.P0SOCK!==undefined')
    s = await snap(pg)
    eq(len(s['results']), 2)
    r2 = s['results'][1]
    eq((r2['card'], r2['out']), ('A45', 'disc'))
    eq(r2['nav']['hid'], False, '숨김 이벤트 못 봄 표시')
    ok(r2['nav']['type'] in ('navigate', 'reload'), r2['nav'])
    ok('숨김이벤트 못 봄' in await pg.evaluate('P0SOCK.detailText()'), '자세히 글에 표시')
    # 결과는 저장돼서 다음에도 남는다
    await pg.reload()
    await pg.wait_for_function('window.P0SOCK!==undefined')
    eq(len((await snap(pg))['results']), 2, '결과가 저장소에 누적')
    no_errs(errs, 'reload')


@test('sock_storage_blocked')
async def t_sock_nostore(env):
    fe = await env.start_fe()
    init = "Object.defineProperty(window,'localStorage',{configurable:true,get:function(){throw new DOMException('denied','SecurityError')}});"
    ctx, pg, errs = await srv_page(env, init=init, clock=True, w=412, h=915)
    await wait_connected(pg)
    ok(await pg.is_visible('#nostore'), '저장 공간 없음 안내')
    ok('저장 공간이 없어요' in await pg.inner_text('#nostore'))
    s = await snap(pg)
    eq(s['store'], False)
    ok('막힘' in await pg.text_content('#env'), '환경 블록에 localStorage 막힘')
    await pg.click('[data-start=A15]')
    await pg.evaluate("__vis('hidden')")
    await pg.clock.fast_forward(15500)
    await asyncio.sleep(0.5)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 12, msg='메모리로 동작')
    r = (await snap(pg))['results'][0]
    ok(r['out'] in ('alive', 'reco'))
    ok('1번 중' in await pg.inner_text('[data-card=A15]'))
    await pg.click('#b-sum')
    ok('A15' in await pg.input_value('#out'))
    no_errs(errs, 'nostore')


@test('sock_copy_fallbacks_and_chunks')
async def t_sock_copy(env):
    fe = await env.start_fe()
    res = synth_results(60)
    init = seed_init(res) + """window.__copied=[];
    Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true});
    document.execCommand=function(c){var a=document.activeElement;window.__copied.push({c:c,id:a&&a.id,sel:a&&a.value&&a.value.substring(a.selectionStart,a.selectionEnd)});return window.__execOk!==false;};"""
    ctx, pg, errs = await srv_page(env, init=init, w=412, h=915)
    await wait_connected(pg)
    eq(len((await snap(pg))['results']), 60, '저장소의 결과를 불러옴')
    await pg.click('#b-sum')
    txt = await pg.input_value('#out')
    cp = await pg.evaluate('window.__copied')
    eq(len(cp), 1)
    eq(cp[0]['sel'], txt, '요약 전체 선택→복사')
    ok(txt.startswith('[소켓시험 P0-v2] 요약'), txt[:60])
    ok(len(txt) <= 2000, '요약은 디스코드 한 메시지(2000자) 안: %d' % len(txt))
    ok('합격 기준(G5' in txt, 'G5 줄')
    ok('복사했어요' in await pg.inner_text('#copymsg'))
    # 자세히: 2000자를 넘으면 나눠진 버튼이 생긴다
    await asyncio.sleep(0.2)
    btns = await pg.locator('#det-btns button').count()
    ok(btns >= 2, '자세히 복사 버튼이 나눠짐: %d' % btns)
    parts = await pg.evaluate('P0SOCK.chunk(P0SOCK.detailText(),1900)')
    ok(all(len(p) <= 1900 for p in parts) and len(parts) == btns, '조각 길이 %s, 버튼 %d' % ([len(p) for p in parts], btns))
    ok(parts[0].startswith('[소켓시험 P0-v2] 자세히'), '맨 위 표식')
    joined = '\n'.join(parts)
    ok('--- 환경 ---' in joined and '--- 최근 이벤트 40개 ---' in joined and '--- 시도별' in joined, '세 구역')
    await pg.evaluate('window.__copied.length=0')
    await pg.locator('#det-btns button').nth(1).click()
    cp = await pg.evaluate('window.__copied')
    eq(len(cp), 1)
    eq(cp[0]['sel'], parts[1], '두 번째 조각이 복사됨')
    ok('길게 눌러' not in await pg.inner_text('#copymsg'))
    await pg.evaluate('window.__execOk=false')
    await pg.click('#b-sum')
    ok('길게 눌러' in await pg.inner_text('#copymsg'), '폴백도 실패하면 안내')
    # 요약 속 숫자가 저장소 값과 맞는지(A15 줄)
    a15 = [r for r in res if r['card'] == 'A15']
    exp_n = len(a15)
    ok(re.search(r'A15 다른 앱 15초: %d번 중' % exp_n, txt), 'A15 n=%d: %s' % (exp_n, txt))
    # 실제 클립보드
    ctx2, pg2, errs2 = await srv_page(env, init=seed_init(res), perms=['clipboard-read', 'clipboard-write'], w=412, h=915)
    await wait_connected(pg2)
    await pg2.click('#b-sum')
    got = await pg2.evaluate('navigator.clipboard.readText()')
    ok(got.startswith('[소켓시험 P0-v2] 요약'), '실제 클립보드 내용')
    no_errs(errs, 'copy'), no_errs(errs2, 'copy2')


@test('sock_public_echo_mode', retry=True)
async def t_sock_pub(env):
    fe = await env.start_fe()
    raw = fe.ws_url('/raw')
    ctx, pg, errs = await env.new_page('sock.html', '?pub=' + raw, init=VIS_INIT, w=412, h=915)
    await poll(pg, "(()=>{const s=P0SOCK.snap();return s.C.rs===1&&s.rtts.length>0})()", 8, msg='에코 hb 왕복')
    mode = await pg.inner_text('#mode')
    ok('공용 에코 모드' in mode and '구분이 안 돼요' in mode and '서버 쪽 기록이 없고' in mode, '경고: ' + mode)
    st = await pg.inner_text('#status')
    ok('없음(공용 에코)' in st and '🟢' in st, st)
    s = await snap(pg)
    eq(s['hello'], None, 'hello 없음')
    # 에코 모드에서도 시도가 돈다(서버 기록 없음)
    await pg.click('[data-start=A15]')
    await pg.evaluate("__vis('hidden')")
    await asyncio.sleep(0.8)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 8, msg='결과')
    r = (await snap(pg))['results'][0]
    eq(r['out'], 'alive')
    eq(r['srv'], None, '공용 에코는 서버 기록 없음')
    ok(r['short'] is True, '15초 시험인데 1초만 비웠으니 짧음 표시')
    ok('목표(15초)보다 짧아서 집계에서 뺌' in await pg.inner_text('#results'))
    ok(fe.log_hits == 0, '공용 모드에선 /log 를 부르지 않는다')
    # 첫 주소가 안 열리면 두 번째 주소로 물러난다(즉시 거절)
    ctx2, pg2, errs2 = await env.new_page('sock.html', '?pub=ws://127.0.0.1:1/raw&pub2=' + raw, w=412, h=915, allow=('WebSocket connection', 'ERR_'))
    await poll(pg2, "(()=>{const s=P0SOCK.snap();return s.C.rs===1&&s.rtts.length>0})()", 10, msg='두 번째 주소로 물러남')
    s2 = await snap(pg2)
    eq(s2['C']['urlIdx'], 1)
    ok(raw in await pg2.inner_text('#mode'), '배너가 지금 쓰는 주소를 보여 줌')
    # 열림이 매달리면(6초 대신 ?t_open=1500) 시간 초과 후 물러난다
    ctx3, pg3, errs3 = await env.new_page('sock.html', '?pub=' + fe.ws_url('/hang?s=4') + '&pub2=' + raw + '&t_open=1500', w=412, h=915, allow=('WebSocket connection', 'ERR_'))
    await poll(pg3, "(()=>{const s=P0SOCK.snap();return s.C.rs===1&&s.rtts.length>0})()", 12, msg='열림 시간초과 뒤 물러남')
    ok(any(e['k'] == 'ws-open-timeout' for e in (await snap(pg3))['log']), '시간초과 기록')
    # 기본(바깥 주소)은 postman 먼저 — 바깥은 막혀 있으니 연결은 안 되지만 배너는 맞아야 한다
    ctx4, pg4, errs4 = await env.new_page('sock.html', '', w=412, h=915, allow=('WebSocket connection', 'ERR_'))
    ok('wss://ws.postman-echo.com/raw' in await pg4.inner_text('#mode'), '기본은 postman 먼저')
    # 잘못된 ?ws= 는 공용 모드로 시작하고 이유를 보여 준다(값은 DOM 에 넣지 않는다)
    ctx5, pg5, errs5 = await env.new_page('sock.html', '?ws=http://evil.example/x', w=412, h=915, allow=('WebSocket connection', 'ERR_'))
    m5 = await pg5.inner_text('#mode')
    ok('공용 에코 모드' in m5 and '올바르지 않아' in m5 and 'evil.example' not in m5, m5)
    eq(await pg5.evaluate('P0SOCK.okWs("ws://evil.example/x")'), False, 'ws:// 은 로컬만')
    eq(await pg5.evaluate('P0SOCK.okWs("ws://localhost:5/x")'), True)
    eq(await pg5.evaluate('P0SOCK.okWs("wss://a.example/ws")'), True)
    eq(await pg5.evaluate('P0SOCK.okWs("https://a.example/ws")'), False)
    for e_ in (errs, errs2, errs3, errs4, errs5):
        no_errs(e_, 'pub')


@test('sock_public_echo_server_drop_1006', retry=True)
async def t_sock_pub_drop(env):
    fe = await env.start_fe()
    ctx, pg, errs = await env.new_page('sock.html', '?pub=' + fe.ws_url('/rawdrop?after=2.5'), init=VIS_INIT, w=412, h=915, allow=('WebSocket connection',))
    await poll(pg, "(()=>{const s=P0SOCK.snap();return s.C.rs===1&&s.rtts.length>0})()", 8, msg='연결')
    await pg.click('[data-start=A15]')
    await pg.evaluate("__vis('hidden')")           # hb 가 끊기면 서버가 무입력으로 비정상 끊김(echo.websocket.org 흉내)
    await poll(pg, "P0SOCK.snap().C.rs===3", 8, msg='서버가 소리 없이 끊음')
    await asyncio.sleep(0.5)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 10, msg='결과')
    r = (await snap(pg))['results'][0]
    eq(r['out'], 'reco')
    eq(r['rs_back'], 3)
    ok(r['close'] and r['close']['code'] == 1006 and r['close']['clean'] is False, '1006/비정상: %s' % r['close'])
    no_errs(errs, 'pub-drop')


@test('sock_xss_strings_inert')
async def t_sock_xss(env):
    fe = await env.start_fe()
    fe.evil = True
    ctx, pg, errs = await srv_page(env, w=412, h=915, clock=True)
    await wait_connected(pg)
    sid = (await snap(pg))['sid']
    await fe.close_conns(1011, sid, EVIL[1])             # 닫는 이유에도 악성 글
    await poll(pg, "P0SOCK.snap().C.id>=2", 8, msg='재접속')
    await pg.click('[data-start=A15]')
    await pg.evaluate("__vis('hidden')")
    await pg.clock.fast_forward(15500)
    await asyncio.sleep(0.4)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 12, msg='결과')
    await pg.click('#raw summary')
    await pg.click('[data-det="0"]')
    await asyncio.sleep(3.2)                              # 3초 주기 갱신이 지나도록
    clean = await pg.evaluate("""()=>({pwn:window.__pwn===undefined,imgs:document.querySelectorAll('img').length,scripts:document.querySelectorAll('main script, body > script ~ script').length,
        svg:document.querySelectorAll('svg').length,onerr:document.querySelectorAll('[onerror],[onload]').length})""")
    ok(clean['pwn'] and clean['imgs'] == 0 and clean['svg'] == 0 and clean['onerr'] == 0 and clean['scripts'] == 0, '악성 글이 실행/삽입됨: %s' % clean)
    ptxt = await pg.inner_text('#s-prev')
    ok('<img' in ptxt or 'script' in ptxt or 'onerror' in ptxt, '글자 그대로 화면에 보임(실행은 안 됨): ' + ptxt)
    det = await pg.input_value('#out')
    ok('[소켓시험 P0-v2] 자세히' in det, '자세히 글 생성')
    logtxt = await pg.inner_text('#logpre')
    ok('onerror' in logtxt or 'script' in logtxt, '원시 로그에도 글자로만')
    # 핑 페이지 쪽도: 악성 srv/쿼리는 DOM 으로 안 들어간다
    ctx2, pg2, errs2 = await env.new_page('ping.html', '?srv=https://a.example%22%3E%3Cscript%3Ewindow.__pwn=9%3C/script%3E&x=%3Cimg%20src=x%20onerror=window.__pwn=8%3E', w=360, h=740)
    ok(await pg2.evaluate('window.__pwn===undefined && document.querySelectorAll("main img, main script").length===0'))
    no_errs(errs, 'xss'), no_errs(errs2, 'xss2')


@test('sock_repeat_aggregation', retry=True)
async def t_sock_repeat(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg)
    sid = (await snap(pg))['sid']
    # 1번째: 그대로
    await pg.click('[data-start=A15]')
    # 취소해 보기
    await pg.click('#b-cancel')
    ok(await pg.is_visible('#arm.hide') or 'hide' in (await pg.get_attribute('#arm', 'class')), '취소하면 안내 상자 닫힘')
    eq(await pg.evaluate("localStorage.getItem('p0sock_pending_v2')"), None)
    eq(len((await snap(pg))['results']), 0, '취소는 결과에 안 쌓임')
    for i in range(3):
        await pg.click('[data-start=A15]')
        await pg.evaluate("__vis('hidden')")
        if i == 1:
            await fe.close_conns(1011, sid)
            await poll(pg, "P0SOCK.snap().C.rs===3", 6, msg='닫힘')
        await pg.clock.fast_forward(15500)
        await asyncio.sleep(0.4)
        await pg.evaluate("__vis('visible')")
        await poll(pg, "P0SOCK.snap().results.length>=%d" % (i + 1), 14, msg='결과 %d' % (i + 1))
        await poll(pg, "P0SOCK.snap().trial===null", 5)
    s = await snap(pg)
    eq([r['n'] for r in s['results']], [1, 2, 3], '시도 번호가 쌓임')
    eq([r['out'] for r in s['results']], ['alive', 'reco', 'alive'])
    card = await pg.inner_text('[data-card=A15]')
    ok('3번 중' in card and '그대로 2' in card and '다시 붙음 1' in card and '못 붙음 0' in card and '새로 불러옴 0' in card, card)
    ok('아직 3/10번이라 판정하지 않아요' in card, 'G5 줄: ' + card)
    ok('성공 3/3' in card, 'G5 성공 수: ' + card)
    ok('재접속 중앙값' in card, card)
    # 다른 카드는 영향 없음
    ok('아직 안 했어요' in await pg.inner_text('[data-card=A45]'))
    no_errs(errs, 'repeat')


@test('sock_wakelock_toggle')
async def t_sock_wl(env):
    fe = await env.start_fe()
    init = """(function(){var W={request:function(t){if(window.__wlDeny)return Promise.reject(new DOMException('no','NotAllowedError'));var l={released:false,release:function(){this.released=true;(l._h||[]).forEach(function(f){f()});return Promise.resolve()},addEventListener:function(n,f){(l._h=l._h||[]).push(f)}};window.__lock=l;return Promise.resolve(l)}};Object.defineProperty(navigator,'wakeLock',{value:W,configurable:true});})();"""
    ctx, pg, errs = await srv_page(env, init=init, w=412, h=915)
    await wait_connected(pg)
    ok('꺼져 있어요' in await pg.text_content('#wlst'), '기본 꺼짐')
    await pg.evaluate("document.getElementById('envd').open=true")          # 환경 정보는 접혀 있다
    await pg.check('#wl')
    await poll(pg, "P0SOCK.snap().wl==='held'", 4, msg='받음')
    ok('held' in await pg.text_content('#wlst'))
    await pg.evaluate('window.__lock.release()')
    await poll(pg, "P0SOCK.snap().wl==='released'", 4, msg='release 이벤트')
    await pg.uncheck('#wl')
    await pg.evaluate('window.__wlDeny=true')
    await pg.check('#wl')
    await poll(pg, "P0SOCK.snap().wl.startsWith('거절')", 4, msg='거절')
    ks = [e['k'] + ':' + e['d'] for e in (await snap(pg))['log'] if e['k'] == 'wakelock']
    ok(len(ks) >= 3, '로그에 wakelock 기록 %s' % ks)
    no_errs(errs, 'wl')


@test('sock_env_block')
async def t_sock_env(env):
    fe = await env.start_fe()
    ua = 'Mozilla/5.0 (Linux; Android 14; SM-S911N Build/UP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 Mobile Safari/537.36'
    ctx = await env.br.new_context(viewport={'width': 412, 'height': 915}, user_agent=ua)
    env.ctxs.append(ctx)
    pg = await ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws')))
    await wait_connected(pg)
    t = await pg.text_content('#env')
    ok('Android 14' in t and 'Chrome 126' in t, t)
    ok('wv' in t and '추정' in t and ua in t, 'UA 전체와 wv 추정: ' + t)
    ok('connection:' in t and 'localStorage: 쓸 수 있음' in t and 'WakeLock' in t and '화면 ' in t and 'KST' in t, t)
    d = await pg.evaluate('P0SOCK.detailText()')
    ok('--- 환경 ---' in d and ua in d, '자세히 글에 UA 전체')
    no_errs(errs, 'env')


@test('sock_layout_and_screens', retry=True)
async def t_sock_layout(env):
    fe = await env.start_fe()
    res = synth_results(14)
    for (w, h, tag) in ((360, 740, '360'), (412, 915, '412'), (844, 390, '844')):
        ctx, pg, errs = await srv_page(env, init=seed_init(res), w=w, h=h, mobile=True)
        await wait_connected(pg)
        await check_layout(pg, 'sock 기본 %s' % tag)
        await pg.click('[data-start=A15]')
        await asyncio.sleep(0.3)
        await check_layout(pg, 'sock 안내 상자 %s' % tag)
        await pg.screenshot(path=os.path.join(SCR, 'sock_%s_armed.png' % tag), full_page=False)
        await pg.click('#b-cancel')
        await pg.click('#raw summary')
        await pg.click('#b-sum')
        await asyncio.sleep(0.3)
        await check_layout(pg, 'sock 로그 열림 %s' % tag)
        await pg.screenshot(path=os.path.join(SCR, 'sock_%s_full.png' % tag), full_page=True)
        no_errs(errs, 'layout ' + tag)
    # 공용 모드 배너와 다크
    ctx, pg, errs = await env.new_page('sock.html', '?pub=' + fe.ws_url('/raw'), w=360, h=740, mobile=True)
    await pg.emulate_media(color_scheme='dark')
    await asyncio.sleep(1.5)
    await check_layout(pg, 'sock 공용 360')
    await pg.screenshot(path=os.path.join(SCR, 'sock_pub_dark_360.png'), full_page=False)
    bad = await pg.evaluate("""()=>{
      function lum(c){const m=c.match(/[\\d.]+/g).map(Number);const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(m[0])+.7152*f(m[1])+.0722*f(m[2])}
      function bg(e){while(e){const c=getComputedStyle(e).backgroundColor;const m=c.match(/[\\d.]+/g).map(Number);if(m.length<4||m[3]>0.5)return c;e=e.parentElement}return 'rgb(0,0,0)'}
      const out=[];document.querySelectorAll('main *').forEach(e=>{const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());if(!own)return;const r=e.getBoundingClientRect();if(!r.width)return;
        const a=lum(getComputedStyle(e).color),b=lum(bg(e));const cr=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);if(cr<4.5&&!e.disabled)out.push(e.tagName+'#'+e.id+' '+cr.toFixed(2))});return out.slice(0,8)}""")
    ok(not bad, '다크 대비 4.5 미만: %s' % bad)
    no_errs(errs, 'layout pub')


@test('sock_no_errors_on_idle_and_junk_params')
async def t_sock_junk(env):
    fe = await env.start_fe()
    junk = ['?ws=', '?ws=%00', '?ws=wss://', '?pub=zzz&pub2=yyy', '?t_open=abc', '?ws=ws://127.0.0.1:1/ws']
    for q in junk:
        ctx, pg, errs = await env.new_page('sock.html', q, w=412, h=915, allow=('WebSocket connection', 'ERR_'))
        await asyncio.sleep(0.8)
        ok(await pg.evaluate('window.P0SOCK!==undefined'), q + ' 로 열려야 함')
        no_errs(errs, q)
        await ctx.close()


# =====================================================================================
# 2026-10-09 검증 지적 보완 — 회귀 시험
# =====================================================================================
def a15rec(i, out='alive', ms=800, inv=None, long_=False, via='return', away=16000, card='A15'):
    r = synth_results(1)[0]
    r.update({'id': 'g%d' % i, 'card': card, 'n': i + 1, 'at': 1700000000000 + i * 1000, 'out': out, 'away_ms': away, 'inv': inv, 'long': long_, 'short': inv == 'short',
              'first_ms': ms if out == 'alive' else None,
              'reco': {'via': via, 'attempts': 1, 'open_ms': 300, 'first_ms': ms, 'in_away': False} if out == 'reco' else None,
              'close': None, 'srv': None})
    if out == 'disc':
        r.update({'back_src': '새로 불러옴', 'nav': {'type': 'reload', 'discarded': False, 'hid': True}})
    return r


async def g5_card(env, fe, results):
    ctx, pg, errs = await srv_page(env, init=seed_init(results), w=412, h=915)
    await wait_connected(pg)
    card = await pg.inner_text('[data-card=A15]')
    g = await pg.evaluate('P0SOCK.g5()')
    summ = await pg.evaluate('P0SOCK.summaryText()')
    no_errs(errs, 'g5')
    await ctx.close()
    return card, g, summ


@test('sock_g5_uses_last10_not_absolute_count')
async def t_sock_g5(env):
    fe = await env.start_fe()
    good = lambda n, off=0: [a15rec(off + i) for i in range(n)]
    bad = lambda n, off=0: [a15rec(off + i, out='fail') for i in range(n)]
    # a) 9번만 했으면 판정하지 않는다
    card, g, _ = await g5_card(env, fe, good(9))
    ok('아직 9/10번이라 판정하지 않아요' in card and '→ 통과' not in card and g['verdict'] is None, 'a: ' + card)
    # b) 10번 중 9번 성공(그대로 8 + 다시 붙음 1) → 통과
    r = good(8) + [a15rec(8, out='reco', ms=1500)] + bad(1, 9)
    card, g, _ = await g5_card(env, fe, r)
    ok('최근 10번 중 성공 9/10' in card and '→ 통과' in card and g['verdict'] == 'pass', 'b: ' + card)
    # c) 10번 중 8번 → 기준 밖
    card, g, _ = await g5_card(env, fe, good(8) + bad(2, 8))
    ok('성공 8/10' in card and '→ 기준 밖' in card and '→ 통과' not in card, 'c: ' + card)
    # d) 20번: 앞 10번 전부 성공 + 최근 10번 중 8번 성공 → 통과하면 안 된다(전체 18/20 이지만 최근 10번이 기준)
    r = good(10) + good(8, 10) + bad(2, 18)
    card, g, _ = await g5_card(env, fe, r)
    ok('성공 8/10' in card and '→ 기준 밖' in card and '→ 통과' not in card and '전체 20번 중 마지막 10번만' in card, 'd: ' + card)
    # e) 20번: 앞 10번 실패 + 최근 10번 전부 성공 → 통과(옛 시도에 발목 잡히지 않는다)
    card, g, _ = await g5_card(env, fe, bad(10) + good(10, 10))
    ok('성공 10/10' in card and '→ 통과' in card, 'e: ' + card)
    # f) 검증자 재현: 20번 중 9번 성공(최근 10번엔 1번뿐) 이 예전엔 「성공 9/20 → 통과」
    r = good(8) + bad(11, 8) + [a15rec(19)]
    card, g, _ = await g5_card(env, fe, r)
    ok('→ 통과' not in card and '→ 기준 밖' in card, 'f: ' + card)
    # g) 저장 상한 200번 중 9번 성공
    r = good(9) + bad(191, 9)
    card, g, summ = await g5_card(env, fe, r)
    ok('→ 통과' not in card and '→ 통과' not in summ and g['total'] == 200 and g['ok'] == 0, 'g: ' + card)
    # h) 성공 9번이어도 속도(중앙값 3초 초과)가 느리면 기준 밖
    card, g, _ = await g5_card(env, fe, [a15rec(i, ms=4000) for i in range(9)] + bad(1, 9))
    ok('→ 통과' not in card and '성공 수는 통과, 속도' in card and '→ 성공 수는 통과' in card, 'h: ' + card)
    # i) 제외(inv)·너무 긴(long) 시도는 분모에서 빠진다
    r = good(10) + [a15rec(10 + i, out='fail', inv='short', away=400) for i in range(5)] + [a15rec(15 + i, out='fail', long_=True, away=70000) for i in range(3)]
    card, g, _ = await g5_card(env, fe, r)
    ok('성공 10/10' in card and '→ 통과' in card and '제외 5번(너무 짧음 5)' in card and g['total'] == 10, 'i: ' + card)
    # j) 11번째가 실패여도 최근 10번 안의 9번이면 통과 / 새로 불러옴(disc)은 실패로 센다
    r = bad(1) + good(9, 1) + [a15rec(10, out='disc')]
    card, g, _ = await g5_card(env, fe, r)
    ok('성공 9/10' in card and '→ 통과' in card and g['disc'] == 1, 'j: ' + card)
    # k) 요약에도 같은 줄
    _, _, summ = await g5_card(env, fe, good(10))
    ok('합격 기준(G5' in summ and '→ 통과' in summ, 'k: ' + summ)


async def opened_total(fe):
    return sum(s.opened for s in fe.sessions.values())


@test('sock_reconnect_storm_guards', retry=True)
async def t_sock_storm(env):
    fe = await env.start_fe()
    # (a) 같은 프로필의 두 창: 창마다 이름표가 달라 서로 쫓아내지 않는다
    ctx, pg, errs = await srv_page(env, w=412, h=915)
    await wait_connected(pg)
    pg2 = await ctx.new_page()
    errs2 = []
    pg2.on('pageerror', lambda e: errs2.append(str(e)))
    await pg2.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws')))
    await wait_connected(pg2)
    await asyncio.sleep(6)
    s1, s2 = await snap(pg), await snap(pg2)
    ok(s1['sid'] != s2['sid'] and s1['sid'].split('-')[0] == s2['sid'].split('-')[0], '같은 폰 기본 이름표 + 창마다 다른 끝 4자: %s / %s' % (s1['sid'], s2['sid']))
    n_open = await opened_total(fe)
    n_repl = sum(len(x.replaced) for x in fe.sessions.values())
    ok(n_open <= 3 and n_repl == 0, '두 창 6초: 연결 %d번 · 서로 쫓아냄 %d번 (예전엔 초당 30번+)' % (n_open, n_repl))
    ok(s1['C']['id'] == 1 and s2['C']['id'] == 1, '재접속 없이 유지')
    # (a2) 그래도 같은 이름표가 되면(탭 복제 등): 4001 을 받은 창은 자동 재접속을 멈추고 버튼만 보인다
    fe.reset()
    same = "try{sessionStorage.setItem('p0sock_win_v2','abcd')}catch(e){}"
    ctxs = await env.br.new_context(viewport={'width': 412, 'height': 915}, locale='ko-KR')
    env.ctxs.append(ctxs)
    await ctxs.add_init_script(same)
    pa = await ctxs.new_page()
    await pa.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws')))
    await wait_connected(pa)
    pb = await ctxs.new_page()
    await pb.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws')))
    await wait_connected(pb)
    sa, sb = await snap(pa), await snap(pb)
    eq(sa['sid'], sb['sid'], '일부러 같은 이름표')
    await asyncio.sleep(5)
    n_open = await opened_total(fe)
    ok(n_open <= 3, '같은 이름표 두 창 5초: 연결 %d번 (예전엔 초당 39번)' % n_open)
    ok(await pa.is_visible('#halt') and '4001' in await pa.inner_text('#halt'), '쫓겨난 창에 안내와 버튼')
    ok('멈춤' in await pa.inner_text('#s-state'), '상태 표시: ' + await pa.inner_text('#s-state'))
    ok(any(e['k'] == 'halt' for e in (await snap(pa))['log']), '멈춤 로그')
    await pa.click('#b-halt')
    await wait_connected(pa)
    await asyncio.sleep(0.8)
    ok(not await pa.is_visible('#halt'), '버튼을 누르면 이 창에서 계속')
    ok(await pb.is_visible('#halt'), '이번엔 다른 창이 멈춤')
    ok(await opened_total(fe) <= 4, '버튼 한 번에 연결 한 번')
    await ctxs.close(); await ctx.close()
    # (b) hello 직후 1008: 한 번 붙고 멈춘다
    fe.reset()
    fe.hello_close = 1008
    ctx3, pg3, errs3 = await srv_page(env, w=412, h=915)
    await asyncio.sleep(5)
    n_open = await opened_total(fe)
    eq(n_open, 1, '1008 은 다시 붙지 않는다(예전엔 5초에 162번)')
    ok(await pg3.is_visible('#halt') and '1008' in await pg3.inner_text('#halt'), '1008 안내')
    fe.hello_close = 0
    await pg3.click('#b-halt')
    await wait_connected(pg3)
    ok(not await pg3.is_visible('#halt'), '서버가 풀리면 버튼으로 다시 붙음')
    await ctx3.close()
    # (c) hello 직후 1011(멈춤 코드가 아님): 백오프가 늘어난다
    fe.reset()
    fe.hello_close = 1011
    ctx4, pg4, errs4 = await srv_page(env, w=412, h=915)
    await asyncio.sleep(6)
    n_open = await opened_total(fe)
    ok(3 <= n_open <= 8, '받자마자 닫는 서버에 6초 동안 %d번 (백오프 0→0.5→1→2→4초; 예전엔 초당 30번) load %s' % (n_open, load()))
    fe.hello_close = 0
    await ctx4.close()
    # (d) 1013: 최소 5초 쉬었다 붙는다
    fe.reset()
    fe.hello_close = 1013
    ctx5, pg5, errs5 = await srv_page(env, w=412, h=915)
    await asyncio.sleep(3.5)
    eq(await opened_total(fe), 1, '1013 뒤 3.5초 안엔 다시 안 붙음')
    fe.hello_close = 0
    await poll(pg5, "P0SOCK.snap().C.id>=2", 8, msg='5초쯤 뒤 다시 붙음')
    await ctx5.close()
    # (e) 분당 30번 상한
    fe.reset()
    ctx6, pg6, errs6 = await srv_page(env, w=412, h=915)
    await wait_connected(pg6)
    await pg6.evaluate("for(var i=0;i<40;i++) P0SOCK.connect('burst')")
    await asyncio.sleep(1.0)
    n_open = await opened_total(fe)
    ok(n_open <= 30, '1분 상한 30번: %d' % n_open)
    ok(any(e['k'] == 'rate-cap' for e in (await snap(pg6))['log']), 'rate-cap 로그')
    for e_, nm in ((errs, 'a'), (errs2, 'a2'), (errs3, 'b'), (errs4, 'c'), (errs5, 'd'), (errs6, 'e')):
        no_errs(e_, 'storm ' + nm)


@test('sock_invalid_attempts_excluded', retry=True)
async def t_sock_invalid(env):
    fe = await env.start_fe()
    # (a) 0.4초 숨김 3번: 15초 카드의 성공으로 안 센다 + 같은 카드를 다시 준비
    ctx, pg, errs = await srv_page(env, w=412, h=915)
    await wait_connected(pg)
    for i in range(3):
        await pg.click('[data-start=A15]')
        await pg.evaluate("__vis('hidden')")
        await asyncio.sleep(0.4)
        await pg.evaluate("__vis('visible')")
        await poll(pg, "P0SOCK.snap().results.length>=%d" % (i + 1), 10, msg='결과 %d' % (i + 1))
        await poll(pg, "P0SOCK.snap().trial!==null&&P0SOCK.snap().trial.phase==='armed'", 5, msg='자동으로 다시 준비')
        ok('집계에서 뺐어요' in await pg.inner_text('#lastmsg') and '다시 준비해 뒀어요' in await pg.inner_text('#lastmsg'), '안내: ' + await pg.inner_text('#lastmsg'))
        await pg.click('#b-cancel')
        await asyncio.sleep(0.2)
    s = await snap(pg)
    ok(all(r['inv'] == 'short' for r in s['results']), '세 번 모두 제외(짧음): %s' % [r['inv'] for r in s['results']])
    card = await pg.inner_text('[data-card=A15]')
    ok('집계할 시도 없음' in card and '제외 3번(너무 짧음 3)' in card, '카드: ' + card)
    ok('→ 통과' not in card and '성공 3' not in card, 'G5 에 안 들어감: ' + card)
    g = await pg.evaluate('P0SOCK.g5()')
    eq((g['total'], g['ok'], g['verdict']), (0, 0, None), 'G5 에 안 들어감')
    ok('목표(15초)보다 짧아서 집계에서 뺌' in await pg.inner_text('#results'), '결과 줄')
    ok('제외 3' in await pg.evaluate('P0SOCK.summaryText()'), '요약에도 제외 표시')
    # (b) 복귀 직후(결과 나오기 전) 다시 나가면 「못 붙음」이 아니라 제외
    ctx2, pg2, errs2 = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg2)
    sid = (await snap(pg2))['sid']
    await pg2.click('[data-start=A15]')
    await pg2.evaluate("__vis('hidden')")
    fe.set_silence(True, sid)
    await pg2.clock.fast_forward(15500)
    await asyncio.sleep(0.3)
    await pg2.evaluate("__vis('visible')")
    await asyncio.sleep(0.5)
    await pg2.evaluate("__vis('hidden')")
    await poll(pg2, "P0SOCK.snap().results.length>=1", 8, msg='재이탈 결과')
    r = (await snap(pg2))['results'][0]
    eq((r['inv'], r['out'], r['intr']), ('intr', 'fail', True), '재이탈은 제외: %s' % r)
    fe.set_silence(False, sid)
    await pg2.evaluate("__vis('visible')")
    card = await pg2.inner_text('[data-card=A15]')
    ok('못 붙음 0' in card or '집계할 시도 없음' in card, card)
    ok('제외 1번(재이탈 1)' in card, card)
    # (c) 연결이 🟢 이 아니면 [시작]이 안 눌리고 arm 도 거절
    ctx3, pg3, errs3 = await env.new_page('sock.html', '?ws=ws://127.0.0.1:1/ws', init=VIS_INIT, w=412, h=915, allow=('WebSocket connection', 'ERR_'))
    await asyncio.sleep(1.2)
    ok(await pg3.evaluate("[...document.querySelectorAll('[data-start]')].every(b=>b.disabled)"), '연결이 안 되면 [시작] 전부 비활성')
    eq(await pg3.evaluate("P0SOCK.arm('A15')"), False)
    ok('🟢' in await pg3.inner_text('#lastmsg'), '안내: ' + await pg3.inner_text('#lastmsg'))
    eq((await snap(pg3))['trial'], None)
    # (d) 목표의 3배 넘게 길면 카드엔 세되 G5 에선 뺀다
    ctx4, pg4, errs4 = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg4)
    await pg4.click('[data-start=A15]')
    await pg4.evaluate("__vis('hidden')")
    await pg4.clock.fast_forward(60000)
    await asyncio.sleep(0.4)
    await pg4.evaluate("__vis('visible')")
    await poll(pg4, "P0SOCK.snap().results.length>=1", 14, msg='결과')
    r = (await snap(pg4))['results'][0]
    ok(r['long'] is True and r['inv'] is None, '길다: %s' % r)
    g = await pg4.evaluate('P0SOCK.g5()')
    eq(g['total'], 0, 'G5 에선 뺌')
    ok('1번 중' in await pg4.inner_text('[data-card=A15]'), '카드 집계엔 들어감')
    # (e) 복귀 화면에 비운 시간이 크게 나온다
    ctx5, pg5, errs5 = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg5)
    sid5 = (await snap(pg5))['sid']
    await pg5.click('[data-start=A15]')
    await pg5.evaluate("__vis('hidden')")
    fe.set_silence(True, sid5)
    await pg5.clock.fast_forward(15500)
    await asyncio.sleep(0.3)
    await pg5.evaluate("__vis('visible')")
    await asyncio.sleep(0.9)
    arm = await pg5.inner_text('#arm')
    ok('돌아왔어요' in arm and '비운 시간 15' in arm and '충분해요' in arm and '최대' in arm, '복귀 화면: ' + arm)
    fe.set_silence(False, sid5)
    for e_, nm in ((errs, 'a'), (errs2, 'b'), (errs3, 'c'), (errs4, 'd'), (errs5, 'e')):
        no_errs(e_, 'invalid ' + nm)


@test('sock_resume_while_hidden_is_not_return')
async def t_sock_resume_hidden(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg)
    await pg.click('[data-start=L60]')
    await pg.evaluate("document.dispatchEvent(new Event('freeze'))")
    await pg.evaluate("__vis('hidden')")
    await pg.clock.fast_forward(2000)
    await pg.evaluate("document.dispatchEvent(new Event('resume'))")        # 아직 숨겨진 채 resume
    await pg.evaluate("window.dispatchEvent(new Event('pageshow'))")         # pageshow 도 마찬가지
    await asyncio.sleep(0.4)
    s = await snap(pg)
    eq(s['trial']['phase'], 'away', 'resume 만으로는 복귀가 아님')
    ok(s['away'] is not None)
    ign = [e['d'] for e in s['log'] if e['k'] == 'ev' and e['d'].startswith('ignored/')]
    ok(len(ign) >= 2, '무시 로그 2건: %s' % ign)
    await pg.clock.fast_forward(5000)
    await asyncio.sleep(0.3)
    await pg.evaluate("__vis('visible')")
    await poll(pg, "P0SOCK.snap().results.length>=1", 14, msg='결과')
    r = (await snap(pg))['results'][0]
    eq(r['back_src'], 'visibilitychange', '복귀는 화면이 보이게 된 순간')
    ok(r['away_ms'] >= 6900, '비운 시간은 숨은 내내(검증자 재현에선 2.1초로 잘렸다): %s' % r['away_ms'])
    # 반대로 보이는 상태에서의 resume 은 복귀로 센다(실제로 얼렸다 깨운 경우)
    ctx2, pg2, errs2 = await srv_page(env, clock=True, w=412, h=915)
    await wait_connected(pg2)
    await pg2.click('[data-start=L15]')
    await pg2.evaluate("document.dispatchEvent(new Event('freeze'))")
    await pg2.clock.fast_forward(16000)
    await pg2.evaluate("document.dispatchEvent(new Event('resume'))")
    await poll(pg2, "P0SOCK.snap().results.length>=1", 14, msg='결과')
    ok((await snap(pg2))['results'][0]['back_src'] in ('resume', 'clock'), '보이는 상태의 resume/시계 끊김은 복귀로 센다')
    no_errs(errs, 'resume-hidden'), no_errs(errs2, 'resume-visible')


@test('sock_reset_needs_confirm_and_layout_order')
async def t_sock_reset(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, init=seed_init(synth_results(7)), w=360, h=740, mobile=True)
    await wait_connected(pg)
    eq(len((await snap(pg))['results']), 7)
    ok(not await pg.is_visible('#b-reset'), '초기화 버튼은 접힌 「고급」 안에 있다')
    top = await pg.evaluate("({sum:document.getElementById('b-sum').getBoundingClientRect().top+scrollY, adv:document.getElementById('adv').getBoundingClientRect().top+scrollY, res:document.getElementById('results').getBoundingClientRect().top+scrollY, env:document.getElementById('envd').getBoundingClientRect().top+scrollY})")
    ok(top['res'] < top['sum'] < top['env'] < top['adv'], '순서: 결과 → 복사 → 환경 → 고급: %s' % top)
    await pg.evaluate("document.getElementById('adv').open=true")
    dialogs = []
    pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.dismiss())))
    sid0 = (await snap(pg))['sid']
    await pg.click('#b-reset')
    eq(len((await snap(pg))['results']), 7, '한 번 눌러서는 안 지워진다')
    ok(await pg.is_visible('#cfm') and '정말 지울까요' in await pg.inner_text('#cfm'), '화면 안 확인 상자(인앱 창에서 막힐 수 있는 confirm() 안 씀)')
    await pg.click('#b-reset-no')
    eq(len((await snap(pg))['results']), 7)
    ok(not await pg.is_visible('#cfm'))
    await pg.click('#b-reset')
    await pg.click('#b-reset-yes')
    await asyncio.sleep(0.3)
    s = await snap(pg)
    eq(len(s['results']), 0, '확인하면 지워짐')
    ok(s['sid'] != sid0, '새 이름표')
    eq(dialogs, [], 'confirm() 같은 브라우저 대화상자를 안 썼다')
    no_errs(errs, 'reset')


@test('sock_env_label_separates_storage')
async def t_sock_env_label(env):
    fe = await env.start_fe()
    ctx = await env.br.new_context(viewport={'width': 412, 'height': 915}, locale='ko-KR')    # 한 프로필(= 같은 localStorage)
    env.ctxs.append(ctx)
    await ctx.add_init_script(VIS_INIT)
    errs = []

    async def open_(q):
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws') + q))
        await wait_connected(pg)
        return pg
    pd = await open_('&env=discord')
    await pd.evaluate("localStorage.setItem('p0sock_results_v2_discord', %s)" % json.dumps(json.dumps(synth_results(5))))
    await pd.reload()
    await wait_connected(pd)
    eq(len((await snap(pd))['results']), 5, '디스코드 창 결과')
    pc = await open_('&env=chrome')
    s = await snap(pc)
    eq(len(s['results']), 0, '같은 프로필의 크롬 표지 창에는 안 섞임')
    sd = await snap(pd)
    ok(s['sid'].split('-')[0] != sd['sid'].split('-')[0], '표지가 다르면 이름표도 다르다: %s / %s' % (s['sid'], sd['sid']))
    ok('디스코드 앱 안의 창' in await pd.evaluate('P0SOCK.summaryText()') and '크롬' in await pc.evaluate('P0SOCK.summaryText()'), '요약에 창 종류')
    ok(not await pd.is_visible('#envbox') and not await pc.is_visible('#envbox'), '표지가 있으면 고르기 상자는 안 보임')
    pn = await open_('')
    ok(await pn.is_visible('#envbox'), '표지가 없으면 한 번 고르게 한다')
    await pn.click('#b-env-d')
    await pn.wait_for_function("location.search.indexOf('env=discord')>=0")
    await wait_connected(pn)
    eq(len((await snap(pn))['results']), 5, '고른 뒤엔 디스코드 칸을 쓴다')
    pe = await open_('&env=chrome')
    await pe.click('[data-start=A15]')
    await pe.evaluate("__vis('hidden')")
    await asyncio.sleep(0.4)
    await pe.evaluate("__vis('visible')")
    await poll(pe, "P0SOCK.snap().results.length>=1", 10)
    eq((await snap(pe))['results'][0]['env'], 'chrome')
    ok('[chrome]' in await pe.evaluate('P0SOCK.detailText()'), '자세히 글에도 표지')
    ok(not errs, 'pageerror %s' % errs)


@test('version_tag_does_not_cover_buttons')
async def t_ver_tag(env):
    fe = await env.start_fe()
    for name, q, wait in (('sock.html', '?ws=' + fe.ws_url('/ws'), True), ('ping.html', '', False), ('index.html', '', False)):
        ctx, pg, errs = await env.new_page(name, q, w=360, h=740, mobile=True)
        if wait:
            await wait_connected(pg)
        pos = await pg.evaluate("getComputedStyle(document.getElementById('ver')).position")
        ok(pos not in ('fixed', 'sticky'), '%s 표지가 화면에 떠 있지 않다: %s' % (name, pos))
        hit = await pg.evaluate("""()=>{const bad=[];document.querySelectorAll('button,a').forEach(b=>{const r=b.getBoundingClientRect();if(!r.width||r.top>innerHeight||r.bottom<0)return;
          const e=document.elementFromPoint(Math.min(innerWidth-1,Math.max(0,r.right-4)),Math.min(innerHeight-1,Math.max(0,r.top+r.height/2)));if(e&&e.id==='ver')bad.push(b.id)});return bad}""")
        eq(hit, [], '%s: 표지가 가린 버튼' % name)
        no_errs(errs, name)


@test('sock_leaving_by_home_link_is_not_a_lost_window')
async def t_sock_home(env):
    fe = await env.start_fe()
    ctx, pg, errs = await srv_page(env, w=412, h=915)
    await wait_connected(pg)
    await pg.click('[data-start=A15]')
    await pg.click('#home')
    await pg.wait_for_url('**/index.html**')
    await asyncio.sleep(0.3)
    await pg.goto(env.page_url('sock.html', '?ws=' + fe.ws_url('/ws')))
    await pg.wait_for_function('window.P0SOCK!==undefined')
    s = await snap(pg)
    eq(s['results'], [], '일부러 나간 건 「새로 불러옴」으로 안 센다')
    eq(await pg.evaluate("localStorage.getItem('p0sock_pending_v2')"), None)
    no_errs(errs, 'home')


@test('sock_stored_results_wrong_shape_do_not_break')
async def t_sock_shape(env):
    fe = await env.start_fe()
    good = a15rec(5)
    weird = [1, None, 'x', [], {'card': 'A15'}, {'card': 'A15', 'out': 'alive', 'srv': {'closes': 'x', 'replaced': 7}, 'reco': 5, 'det': 7, 'evs': 'zz', 'wl': 3},
             {'card': 'A15', 'out': 'reco', 'srv': {}, 'reco': {'first_ms': 'a'}}, {'card': 'A15', 'out': 'alive', 'srv': {'closes': [None, 5, {'code': 1}]}},
             {'card': 'NOPE', 'out': 'alive'}, good]
    ctx, pg, errs = await srv_page(env, init=seed_init(weird), w=412, h=915)
    await wait_connected(pg)
    await asyncio.sleep(3.6)                       # 3초 주기 갱신이 지나도록
    s = await snap(pg)
    eq(len(s['results']), 4, '못 쓰는 기록(out 없음·없는 카드·숫자 따위)은 버리고 4개만 남음')
    ok(await pg.locator('#det-btns button').count() >= 1, '자세히 복사 버튼이 살아 있다')
    await pg.click('#det-btns button >> nth=0')
    ok('복사했어요' in await pg.inner_text('#copymsg') or '길게 눌러' in await pg.inner_text('#copymsg'), '자세히 복사 동작')
    d = await pg.evaluate('P0SOCK.detailText()')
    ok('--- 시도별' in d, d[:80])
    ok(not any(e['k'] == 'render-error' for e in s['log']), '렌더 오류 기록 없음: %s' % [e for e in s['log'] if e['k'] == 'render-error'])
    no_errs(errs, 'shape')


@test('sock_summary_fits_one_message_when_full')
async def t_sock_summary_len(env):
    fe = await env.start_fe()
    cards = ['A15', 'A45', 'L15', 'L60', 'L300', 'CALL', 'DC']
    res = []
    for i in range(200):
        c = cards[i % 7]
        out = ['alive', 'reco', 'fail', 'disc'][i % 4]
        res.append(a15rec(i, out=out, card=c, inv='short' if i % 9 == 0 else None, away=16000))
        res[-1]['close'] = {'where': '자리 비운 동안', 'code': [1006, 1001, 4001][i % 3], 'clean': False, 'why': ''} if out == 'reco' else None
    ctx, pg, errs = await srv_page(env, init=seed_init(res), w=412, h=915)
    await wait_connected(pg)
    summ = await pg.evaluate('P0SOCK.summaryText()')
    print('      · 가득 찬 요약 길이 %d자' % len(summ))
    ok(len(summ) <= 1900, '요약이 디스코드 한 메시지(2000자) 안: %d' % len(summ))
    ok('눈여겨볼 것' in summ and '최근 시도' in summ and '[자세히 복사]' in summ, summ[-400:])
    parts = await pg.evaluate('P0SOCK.chunk(P0SOCK.detailText(),1900)')
    ok(all(len(p) <= 1900 for p in parts), '자세히 조각 길이 %s' % [len(p) for p in parts])
    no_errs(errs, 'summary-len')


# ---- 핑 페이지 ----
@test('ping_verdict_many_failures_wording')
async def t_ping_verdict_fail(env):
    ctx, pg, errs = await env.new_page('ping.html', w=360, h=740)
    r = await pg.evaluate("P0PING.verdict('data',{n:8,fails:12,median:40},null,null)")
    ok('실패가 많아 판정하기 어려워요' in r['text'] and '덜 끝났어요' not in r['text'], '끝났는데 실패가 많음: ' + r['text'])
    r = await pg.evaluate("P0PING.verdict('data',{n:8,fails:3,median:40},null,null)")
    ok('덜 끝났어요' in r['text'], '아직 도는 중: ' + r['text'])
    r = await pg.evaluate("P0PING.verdict('data',{n:20,fails:0,median:40},null,null)")
    ok('✅' in r['text'])
    no_errs(errs, 'verdict-fail')


PING_FAST = {'seoul': 8, 'tokyo': 8, 'fra': 8, 'bot': 8}


@test('ping_hidden_during_measure_discards_samples', retry=True)
async def t_ping_hidden(env):
    log = {k: [] for k in VULTR.values()}
    slow = {'on': False}
    ctx, pg, errs = await env.new_page('ping.html', '', w=360, h=740, init=VIS_INIT, allow=('ERR_FAILED', 'CORS', 'Failed to load'))

    async def h(route):
        req = route.request
        key = VULTR[urlparse(req.url).hostname]
        log[key].append(req.method)
        await asyncio.sleep(1.5 if slow['on'] else 0.008)       # 가려진 사이엔 응답이 늦다(브라우저가 타이머를 늦추는 것의 흉내)
        try:
            await route.fulfill(status=200, headers=dict(CORS, **{'content-type': 'text/html'}), body='')
        except Exception:
            pass
    for host in VULTR:
        await ctx.route('https://%s/**' % host, h)
    await pg.click('#b-data')
    await pg.click('#b-start')
    await poll(pg, "P0PING.state.targets[0].samples.length>=6", 20, msg='서울 6회 잼')
    slow['on'] = True
    await pg.evaluate("__vis('hidden')")
    await asyncio.sleep(2.2)
    ok('가려져서' in await pg.inner_text('#prog'), '숨김 안내: ' + await pg.inner_text('#prog'))
    slow['on'] = False
    await pg.evaluate("__vis('visible')")
    await poll(pg, "document.querySelector('#prog').innerText.startsWith('끝났어요')", 90, msg='끝')
    st = await pg.evaluate("P0PING.state.targets.map(t=>({id:t.id,n:t.stats.n,fails:t.stats.fails,max:t.stats.max,redo:t.hiddenRedo||0}))")
    seoul = [x for x in st if x['id'] == 'seoul'][0]
    ok(seoul['redo'] >= 1, '서울을 다시 쟀다: %s' % st)
    for x in st:
        ok(x['n'] == 20 and x['fails'] == 0, '%s 20회·실패 0: %s' % (x['id'], x))
        ok(x['max'] < 1000, '%s 가려진 사이 값(1.5초)이 안 섞임: max %s' % (x['id'], x['max']))
    no_errs(errs, 'ping-hidden')


@test('ping_stop_right_after_last_sample_keeps_target_done', retry=True)
async def t_ping_stop_last(env):
    spy = """window.__n=0;(function(){var f=window.fetch;window.fetch=function(u){var p=f.apply(this,arguments);
      if(String(u).indexOf('sel-kor-ping')>=0){window.__n++; if(window.__n===23){p.then(function(){setTimeout(function(){document.getElementById('b-stop').click()},30)}).catch(function(){})}}
      return p}})();"""
    ctx, pg, errs = await env.new_page('ping.html', '', w=360, h=740, init=spy, allow=('ERR_FAILED', 'CORS', 'Failed to load'))
    log = {k: [] for k in VULTR.values()}
    await install_ping_routes(ctx, PING_FAST, True, log)
    await pg.click('#b-data')
    await pg.click('#b-start')
    await poll(pg, "document.querySelector('#prog').innerText.startsWith('멈췄어요')", 40, msg='멈춤')
    st = await pg.evaluate("P0PING.state.targets.map(t=>({id:t.id,n:t.stats.n,phase:t.phase}))")
    seoul = [x for x in st if x['id'] == 'seoul'][0]
    eq((seoul['n'], seoul['phase']), (20, 'end'), '20번을 다 쟀으면 끝난 대상으로 남는다(멈춤 표시 아님): %s' % st)
    ok('멈췄어요(여기까지의 값)' not in (await card_stats(pg))['seoul'], '카드에 멈춤 표시가 없다')
    n_before = len(log['seoul'])
    await pg.click('#b-start')
    await poll(pg, "document.querySelector('#prog').innerText.startsWith('끝났어요')", 60, msg='이어서 끝')
    eq(len(log['seoul']), n_before, '이어서 시작해도 서울을 처음부터 다시 재지 않는다')
    ok(all(len(log[k]) == 23 for k in ('tokyo', 'fra', 'bot')), '나머지는 한 번씩: %s' % {k: len(v) for k, v in log.items()})
    no_errs(errs, 'ping-stop-last')


# =====================================================================================
async def run_one(env_factory, name, fn, retry):
    t0 = time.time()
    last = None
    for attempt in range(2 if retry else 1):
        env = await env_factory()
        try:
            await fn(env)
            await env.stop()
            tag = '' if attempt == 0 else ' (재시도 1회 뒤 통과)'
            return (name, True, time.time() - t0, tag)
        except Exception as e:
            last = traceback.format_exc()
            await env.stop()
            if attempt == 0 and retry:
                print('   ~ %s 첫 시도 실패, 한 번 더: %s' % (name, str(e).splitlines()[0][:160]))
    return (name, False, time.time() - t0, last)


async def main(argv):
    names = [a for a in argv if not a.startswith('--')]
    jobs = 1
    for i, a in enumerate(argv):
        if a == '--jobs':
            jobs = int(argv[i + 1])
            names = [n for n in names if n != argv[i + 1]]
    if '--list' in argv:
        for n, _, r in TESTS:
            print(n, '(retry)' if r else '')
        return 0
    sel = [t for t in TESTS if not names or t[0] in names]
    print('uptime load(시작): %s · 시험 %d개 · jobs=%d' % (load(), len(sel), jobs))
    web = Srv(root=PAGES_DIR)
    results = []
    async with async_playwright() as pw:
        br = await launch(pw)

        async def factory():
            return Env(br, web)
        sem = asyncio.Semaphore(jobs)

        async def guarded(t):
            async with sem:
                r = await run_one(factory, *t)
                mark = 'PASS' if r[1] else 'FAIL'
                print('%s  %-46s %6.1fs%s' % (mark, r[0], r[2], r[3] if r[1] else ''))
                if not r[1]:
                    print(r[3])
                return r
        results = await asyncio.gather(*[guarded(t) for t in sel])
        await br.close()
    web.close()
    bad = [r for r in results if not r[1]]
    print('\n결과: %d/%d 통과 · uptime load(끝): %s' % (len(results) - len(bad), len(results), load()))
    if bad:
        print('실패: ' + ', '.join(r[0] for r in bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main(sys.argv[1:])))
