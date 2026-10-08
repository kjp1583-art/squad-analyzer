# -*- coding: utf-8 -*-
"""🗞 흐접새우 서바이벌 첫 화면 「패치노트」 대시보드 — data/patch_notes.json 의 game:"sv" 항목만 모아 보여 주는 겹창.
   실제 데이터 + 가짜 JSON(page.route) 으로 확인한다: 항목 분류·요약 칩·필터·날짜 묶음·펼침·배지·닫기·XSS·오류 문구·저장소 차단·모바일 가로 넘침·판 시작.
   사용: python3 tests/survivors_patchdash_test.py        (스크린샷: PN_SHOTS=<폴더> python3 tests/survivors_patchdash_test.py)
   임시 사본 survivors_x.html 을 만들므로 시험 뒤 `git checkout -- survivors_x.html` 로 되돌릴 것(커밋하지 않는다)."""
import asyncio, sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:300] if x and not c else ''))
    if not c: FAILS.append(n)
TAGS = ['신규', '개편', '변경', '밸런스', '수정']
NOTES = json.load(open(os.path.join(H.ROOT, 'data', 'patch_notes.json'), encoding='utf-8'))['notes']
SV = [n for n in NOTES if n.get('game') == 'sv']
SHOTS = os.environ.get('PN_SHOTS')
def kst_today(): return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
def days_ago(n): return (kst_today() - datetime.timedelta(days=n)).isoformat()
def note(i, **kw):
    d = dict(id='t%d' % i, date=days_ago(i), tag='신규', area='squad', game='sv', title='제목 %d' % i, how='쓰는 법 %d' % i, lines=['본문 %d' % i]); d.update(kw); return d
def body_of(notes): return json.dumps({'notes': notes}, ensure_ascii=False)

async def mk(b, port, w=390, h=844, mobile=True, init=None, pn=None):
    """harness.new_page 와 같은 규약 — 다만 patch_notes 라우트·초기 스크립트를 이동 전에 꽂는다."""
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    errs, reqs = [], []
    async def gen(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', gen)
    if pn: await ctx.route('**/data/patch_notes.json*', pn)
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    pg.on('request', lambda r: reqs.append(r.url) if 'patch_notes.json' in r.url else None)
    await pg.goto('http://127.0.0.1:%d/survivors_x.html' % port)
    await pg.wait_for_function('window.__p6x!==undefined&&window.__pn!==undefined', timeout=20000)
    return ctx, pg, errs, reqs
def fake(text, status=200, delay=0, ctype='application/json'):
    async def h(r):
        if delay: await asyncio.sleep(delay)
        await r.fulfill(status=status, body=text, content_type=ctype)
    return h
async def ready(pg, st='ok'): await pg.wait_for_function("__pn.st==='%s'" % st, timeout=20000)
async def is_open(pg): return await pg.evaluate("document.getElementById('pnOv').classList.contains('on')")
async def titles(pg): return await pg.evaluate("[...document.querySelectorAll('#pnList .pnt')].map(e=>e.textContent)")
async def body_text(pg): return await pg.evaluate("document.getElementById('pnBody').innerText")
async def shot(pg, name):
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); await pg.screenshot(path=os.path.join(SHOTS, name))

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)

        # ── 0. 분류 데이터 자체 점검 ─────────────────────────────────────────────
        check('패치노트 파일: game:"sv" 항목이 있다', len(SV) >= 30, len(SV))
        check('패치노트 파일: id 중복 없음', len({n['id'] for n in NOTES}) == len(NOTES))
        check('패치노트 파일: 날짜 내림차순 유지', [n['date'] for n in NOTES] == sorted([n['date'] for n in NOTES], reverse=True))
        check('패치노트 파일: game 값은 sv 뿐', {n.get('game') for n in NOTES} <= {None, 'sv'})
        check('패치노트 파일: sv 항목의 tag 는 5종 안', all(n['tag'] in TAGS for n in SV))
        check('패치노트 파일: 이번 기능 항목이 맨 앞(game sv · area squad)', NOTES[0]['id'] == '2026-10-08-sv-patch-dash' and NOTES[0]['game'] == 'sv' and NOTES[0]['area'] == 'squad')
        check('패치노트 파일: 스콰드 생존게임(노벨)·분석기 항목은 sv 가 아니다', not any('novel' in n['id'] or 'analyzer' in n['id'] for n in SV))

        # ── 1. 필터 함수 단위 ──────────────────────────────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port)
        r = await pg.evaluate("""()=>{const f=isSvPatch;return [f({game:'sv'}),f({game:'sv',area:'brj'}),f({how:'흐접새우 서바이벌 · 신림'}),f({title:'🦐 흐접새우 서바이벌: 새 무기'}),
          f({area:'brj',how:'흐접새우 서바이벌에서 무기 카드로 확인'}),f({area:'squad',how:'웹 프로필'}),f({}),f(null),f('x'),f({game:'brj',how:'흐접새우 서바이벌'}),f({game:'',how:'흐접새우 서바이벌'}),f({title:'흐접새우의 증바람하실분 장비'})]}""")
        check('isSvPatch: game:"sv" 참(area brj 라도)', r[0] and r[1])
        check('isSvPatch: game 없으면 how·title 의 「흐접새우 서바이벌」만 참', r[2] and r[3])
        check('isSvPatch: game 없는 brj 항목은 거짓', not r[4])
        check('isSvPatch: 무관·빈값·null·문자열은 거짓', not (r[5] or r[6] or r[7] or r[8]))
        check('isSvPatch: 다른 game 값이 명시되면 거짓 · 빈 문자열 game 은 안전망으로', not r[9] and r[10] and not r[11])
        # 실제 데이터 123건 전부 — 명시 필드와 일치
        mism = await pg.evaluate("async ()=>{const j=await (await fetch('data/patch_notes.json')).json();return j.notes.filter(n=>isSvPatch(n)!==(n.game==='sv')).map(n=>n.id)}")
        check('실제 데이터: 모든 항목이 명시 필드(game)대로 가려진다', not mism, mism)
        await ctx.close()

        # ── 2. 첫 화면 버튼 · 실제 데이터로 열기 ─────────────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port)
        await ready(pg)
        bt = await pg.evaluate("(()=>{const r=document.getElementById('pnOpen').getBoundingClientRect(),s=document.getElementById('startBtn').getBoundingClientRect();return {w:r.width,h:r.height,l:r.left,rt:r.right,t:r.top,b:r.bottom,sh:s.height,sb:s.bottom,vh:innerHeight,vw:innerWidth,txt:document.getElementById('pnOpen').textContent}})()")
        check('첫 화면에 「🗞 패치노트」 버튼이 있다', '패치노트' in bt['txt'] and bt['w'] > 0, bt)
        check('버튼 터치 영역 44px 이상', bt['h'] >= 44 and bt['w'] >= 44, bt)
        check('버튼이 화면 안에 있고 시작 버튼은 그대로 보인다', 0 <= bt['l'] and bt['rt'] <= bt['vw'] and bt['sb'] <= bt['vh'] and bt['sh'] >= 40, bt)
        badge = await pg.evaluate("(()=>{const e=document.getElementById('pnBadge');return {hid:e.hidden,txt:e.textContent,al:document.getElementById('pnOpen').getAttribute('aria-label')}})()")
        check('처음 방문: 안 본 새 소식이 있어 배지가 보인다(9+)', not badge['hid'] and badge['txt'] == '9+' and '새 소식' in badge['al'], badge)
        await shot(pg, '1_title_badge_390x844.png')
        await pg.click('#pnOpen')
        check('열면 겹창이 뜬다(role=dialog · aria-modal · aria-label)', await is_open(pg) and await pg.evaluate("(()=>{const d=document.querySelector('#pnOv [role=dialog]');return d.getAttribute('aria-modal')==='true'&&!!d.getAttribute('aria-label')})()"))
        check('열면 포커스가 겹창 안(✕)으로 간다', await pg.evaluate("document.activeElement.id==='pnX'"))
        check('겹창이 열려 있어도 게임 상태는 title', await pg.evaluate("__p6x.state") == 'title')
        got = await titles(pg)
        want = [n['title'] for n in SV]
        check('항목 수 = game:"sv" 개수(%d)' % len(SV), len(got) == len(SV), (len(got), len(SV)))
        check('항목 제목이 game:"sv" 항목과 정확히 같다(순서 포함)', got == want, [x for x in got if x not in want][:3])
        others = {n['title'] for n in NOTES if n.get('game') != 'sv'}
        check('brj·내전·분석기·노벨 항목이 하나도 섞이지 않는다', not (set(got) & others), list(set(got) & others)[:3])
        check('brj 인데 서바이벌 내용인 항목(리듬 게임 너프)은 포함된다', any('리듬 게임 너프' in x for x in got))
        check('「흐접새우의 증바람하실분」(브장신 장비)은 빠진다', not any('증바람' in x and '장비' in x for x in got) and '2026-09-16-gear-balance' not in [n['id'] for n in SV])
        # 요약 칩
        today = kst_today()
        exp = [sum(1 for n in SV if n['tag'] == t and (today - datetime.date.fromisoformat(n['date'])).days < 30) for t in TAGS]
        chips = await pg.evaluate("[...document.querySelectorAll('.pnchip')].map(c=>({k:c.dataset.k,n:+c.querySelector('b').textContent,l:c.querySelector('span').textContent,p:c.getAttribute('aria-pressed'),h:c.getBoundingClientRect().height}))")
        check('요약 칩 5개(신규·개편·변경·밸런스·수정) 순서', [c['l'] for c in chips] == TAGS, chips)
        check('요약 칩 숫자 = 최근 30일 건수(KST 오늘 기준) %s' % exp, [c['n'] for c in chips] == exp, chips)
        check('요약 칩 터치 높이 44px 이상', all(c['h'] >= 44 for c in chips), chips)
        info = await pg.evaluate("document.getElementById('pnInfo').textContent")
        last = SV[0]['date'][5:].replace('-', '/')
        check('요약 줄: 「전체 N건 · 마지막 업데이트 MM/DD」', ('전체 %d건' % len(SV)) in info and ('마지막 업데이트 ' + last) in info, info)
        # 날짜 묶음 · 최신순
        grp = await pg.evaluate("[...document.querySelectorAll('.pnday')].map(s=>({h:s.querySelector('h3').textContent,n:s.querySelectorAll('.pncard').length}))")
        dates = sorted({n['date'] for n in SV}, reverse=True)
        wd = '월화수목금토일'
        fmt = lambda d: '%d월 %d일 (%s)' % (int(d[5:7]), int(d[8:]), wd[datetime.date.fromisoformat(d).weekday()]) if d[:4] == str(today.year) else '%s년 ' % d[:4] + '%d월 %d일 (%s)' % (int(d[5:7]), int(d[8:]), wd[datetime.date.fromisoformat(d).weekday()])
        check('날짜별로 묶이고 최신 날짜부터(헤더 %d개)' % len(dates), [g['h'] for g in grp] == [fmt(d) for d in dates], [g['h'] for g in grp][:4])
        check('날짜 묶음마다 그날의 항목 수가 맞다', [g['n'] for g in grp] == [sum(1 for n in SV if n['date'] == d) for d in dates])
        # 펼침
        st = await pg.evaluate("[...document.querySelectorAll('.pncard')].map(c=>c.classList.contains('on'))")
        check('가장 최신 1건만 처음부터 펼쳐져 있다', st[0] and sum(st) == 1, st[:5])
        vis = await pg.evaluate("(()=>{const c=document.querySelectorAll('.pncard');return [c[0].querySelector('.pnbd').offsetHeight>0,c[1].querySelector('.pnbd').offsetHeight>0]})()")
        check('펼친 카드만 본문이 보인다', vis == [True, False], vis)
        cards = pg.locator('.pncard')
        await cards.nth(1).locator('.pnh').click()
        check('다른 카드를 누르면 펼쳐진다(aria-expanded)', await cards.nth(1).get_attribute('class') and 'on' in (await cards.nth(1).get_attribute('class')) and await cards.nth(1).locator('.pnh').get_attribute('aria-expanded') == 'true')
        check('펼친 카드는 본문 줄 수가 데이터와 같다', await cards.nth(1).locator('li').count() == len(SV[1]['lines']))
        await cards.nth(1).locator('.pnh').click()
        check('다시 누르면 접힌다', 'on' not in (await cards.nth(1).get_attribute('class')) and await cards.nth(1).locator('.pnh').get_attribute('aria-expanded') == 'false')
        await cards.nth(0).locator('.pnh').click()
        check('최신 카드도 접을 수 있다', 'on' not in (await cards.nth(0).get_attribute('class')))
        await cards.nth(0).locator('.pnh').click()
        # 필터
        k = next(i for i, c in enumerate(chips) if c['n'] > 0)
        tot = sum(1 for n in SV if n['tag'] == TAGS[k])
        await pg.locator('.pnchip').nth(k).click()
        cnt = await pg.locator('.pncard').count(); tg = await pg.evaluate("[...document.querySelectorAll('.pncard .pntag')].map(e=>e.textContent)")
        check('칩을 누르면 그 종류만 걸러진다(%s %d건)' % (TAGS[k], tot), cnt == tot and set(tg) == {TAGS[k]}, (cnt, set(tg)))
        check('눌린 칩은 aria-pressed=true · 나머지 false', await pg.evaluate("[...document.querySelectorAll('.pnchip')].map(c=>c.getAttribute('aria-pressed'))") == ['true' if i == k else 'false' for i in range(5)])
        inf = await pg.evaluate("document.getElementById('pnInfo').textContent")
        check('필터 중 안내 줄에 종류·건수가 나온다', TAGS[k] in inf and ('%d건' % tot) in inf, inf)
        check('필터 후에도 보이는 것 중 최신 1건이 펼쳐져 있다', await pg.evaluate("document.querySelectorAll('.pncard.on').length==1&&document.querySelector('.pncard').classList.contains('on')"))
        await shot(pg, '3_filtered_390x844.png')
        # 다른 칩으로 바꾸기, 같은 칩 다시 누르면 해제
        k2 = (k + 1) % 5
        await pg.locator('.pnchip').nth(k2).click()
        tot2 = sum(1 for n in SV if n['tag'] == TAGS[k2])
        if tot2: check('다른 칩을 누르면 그 종류로 바뀐다', await pg.locator('.pncard').count() == tot2)
        else: check('항목이 없는 종류는 안내 문구', '아직 없어요' in await body_text(pg))
        await pg.locator('.pnchip').nth(k2).click()
        check('같은 칩을 다시 누르면 해제되어 전체로', await pg.locator('.pncard').count() == len(SV) and ('전체 %d건' % len(SV)) in await pg.evaluate("document.getElementById('pnInfo').textContent"))
        # 시작 화면 로딩에 영향 없음: 요청은 한 번뿐
        check('patch_notes 요청은 1번(미리 읽기 + 열기 재요청 없음)', len(reqs) == 1 and 'cb=' in reqs[0], reqs)
        # 닫기 3가지
        await pg.click('#pnX')
        check('✕ 로 닫힌다', not await is_open(pg))
        check('닫으면 포커스가 「패치노트」 버튼으로 돌아온다', await pg.evaluate("document.activeElement.id==='pnOpen'"))
        await pg.click('#pnOpen'); check('다시 열린다', await is_open(pg))
        await pg.mouse.click(4, 4)
        check('바깥(어두운 배경) 탭으로 닫힌다', not await is_open(pg))
        await pg.click('#pnOpen'); await pg.keyboard.press('Escape')
        check('Esc 로 닫힌다', not await is_open(pg))
        check('Esc 가 게임(일시정지 등)에 새지 않는다 — 상태는 title', await pg.evaluate("__p6x.state") == 'title')
        await pg.click('#pnOpen')
        await pg.mouse.click(195, 400)   # 겹창 안쪽은 닫히지 않는다
        check('겹창 안쪽을 눌러도 닫히지 않는다', await is_open(pg))
        # 탭 포커스 순환
        await pg.keyboard.press('Tab'); await pg.keyboard.press('Shift+Tab'); await pg.keyboard.press('Shift+Tab')
        check('Tab 으로 겹창 밖으로 포커스가 나가지 않는다', await pg.evaluate("document.getElementById('pnOv').contains(document.activeElement)"))
        # blur/visibility 와 무관
        await pg.evaluate("dispatchEvent(new Event('blur'))")
        check('열린 채 blur 가 와도 상태·겹창 유지', await pg.evaluate("__p6x.state") == 'title' and await is_open(pg))
        # 열린 채 게임 시작(프로그램) → 겹창이 닫힌다
        await pg.evaluate("__p6x.start()")
        await pg.wait_for_timeout(100)
        check('게임이 시작되면 겹창이 닫힌다', not await is_open(pg) and await pg.evaluate("__p6x.state") == 'play')
        check('[실제 데이터] 스크립트·콘솔 오류 없음', not errs, errs)
        await ctx.close()

        # ── 3. 시작 버튼으로 판이 정상 시작(열었다 닫은 뒤) ─────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port)
        await ready(pg)
        await pg.click('#pnOpen'); await pg.click('#pnX')
        await pg.click('#startBtn'); await pg.wait_for_timeout(200)
        s = await pg.evaluate("({st:__p6x.state,hud:getComputedStyle(document.getElementById('hud')).display,title:document.getElementById('title').classList.contains('on')})")
        check('열었다 닫은 뒤 「시작하기」로 판이 정상 시작', s['st'] == 'play' and s['hud'] == 'block' and not s['title'], s)
        await pg.evaluate("__p6x.update(0.05);__p6x.update(0.05)")
        check('판이 정상 진행(시간이 흐름)', await pg.evaluate("__p6x.S.t") > 0.05)
        # 처음으로 돌아오면 다시 열 수 있고 배지는 이미 본 상태
        await pg.evaluate("__p6x.endRun&&__p6x.endRun(false)")
        await pg.wait_for_timeout(100)
        await pg.evaluate("document.getElementById('homeBtn').click()")
        await pg.wait_for_timeout(100)
        check('처음으로 돌아와 다시 열 수 있다', await pg.evaluate("document.getElementById('title').classList.contains('on')"))
        await pg.click('#pnOpen'); check('돌아온 첫 화면에서도 열린다', await is_open(pg) and await pg.locator('.pncard').count() == len(SV))
        check('[시작 흐름] 오류 없음', not errs, errs)
        await ctx.close()

        # ── 4. 배지: 본 것 기록 · 새 항목 · NEW ───────────────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port)
        await ready(pg)
        await pg.click('#pnOpen')
        seen = await pg.evaluate("localStorage.getItem('p6_pn_seen')")
        check('열면 p6_pn_seen 에 가장 최신 id 가 기록된다', seen == SV[0]['id'], seen)
        check('열면 배지가 사라진다', await pg.evaluate("document.getElementById('pnBadge').hidden"))
        check('처음 방문엔 NEW 표시가 줄줄이 달리지 않는다', await pg.locator('.pnnew').count() == 0)
        await pg.click('#pnX')
        await pg.reload(); await pg.wait_for_function('window.__pn!==undefined'); await ready(pg)
        check('다음 방문엔 배지가 없다', await pg.evaluate("document.getElementById('pnBadge').hidden") and await pg.evaluate("document.getElementById('pnOpen').getAttribute('aria-label')") == '패치노트 열기')
        await ctx.close()
        # 3번째 항목까지 본 사람 → 새 소식 2건
        seed = "try{if(!sessionStorage.getItem('__s')){localStorage.setItem('p6_pn_seen',%s);sessionStorage.setItem('__s','1')}}catch(e){}" % json.dumps(SV[2]['id'])
        ctx, pg, errs, reqs = await mk(b, srv.port, init=seed)
        await ready(pg)
        bd = await pg.evaluate("({h:document.getElementById('pnBadge').hidden,t:document.getElementById('pnBadge').textContent})")
        check('안 본 새 항목 2건 → 배지 숫자 2', not bd['h'] and bd['t'] == '2', bd)
        await pg.click('#pnOpen')
        newc = await pg.evaluate("[...document.querySelectorAll('.pncard')].map(c=>!!c.querySelector('.pnnew'))")
        check('새 항목 2건에만 NEW 표시', newc[:4] == [True, True, False, False] and sum(newc) == 2, newc[:5])
        check('열면 기록이 최신으로 갱신 · 배지 사라짐', await pg.evaluate("localStorage.getItem('p6_pn_seen')") == SV[0]['id'] and await pg.evaluate("document.getElementById('pnBadge').hidden"))
        await ctx.close()
        # 기록 id 가 파일에 없어도(깨진 값) 오류 없이 전부 새 것으로
        seed2 = "try{localStorage.setItem('p6_pn_seen','없는-id')}catch(e){}"
        ctx, pg, errs, reqs = await mk(b, srv.port, init=seed2)
        await ready(pg)
        check('알 수 없는 기록값이어도 배지 9+ · 오류 없음', await pg.evaluate("document.getElementById('pnBadge').textContent") == '9+' and not errs, errs)
        await ctx.close()

        # ── 5. 가짜 JSON: XSS · 서식 ────────────────────────────────────────────
        xss = [
            note(0, id='x0', title='<script>window.__xss=1</script>제목', how='<img src=x onerror="window.__xss=2">쓰는 법', lines=['"><svg onload="window.__xss=3">', '<b onmouseover=window.__xss=4>굵게?</b>', "'; window.__xss=5; //"]),
            note(1, id='x1', tag='<img src=x onerror=window.__xss=6>', title='**굵은 제목** 과 `코드`', how='`<i>how</i>` 입니다', lines=['**굵게** 와 `코드` 와 보통 글자', '`**코드 안은 굵게 안 됨**`', '짝 없는 `백틱 하나', '**짝 없는 별표', '<style>body{display:none}</style>']),
            note(2, id='"><script>window.__xss=7</script>', date='<img src=x onerror=window.__xss=8>', title='날짜가 이상한 항목', lines=['본문']),
            note(3, id='x3', tag='변경', title='A' * 300, how='B' * 300, lines=['C' * 400, 'https://example.com/' + 'd' * 300]),
            dict(id='nosv', date=days_ago(1), tag='신규', area='brj', title='브장신 항목은 안 보임', how='', lines=['x']),
            dict(id='old', date=days_ago(5), tag='수정', area='squad', title='옛 항목 안전망', how='흐접새우 서바이벌 · 옛 항목', lines=['game 없어도 how 로 잡힌다']),
            None, 'str', 7, {'game': 'sv'},
        ]
        ctx, pg, errs, reqs = await mk(b, srv.port, w=360, h=640, pn=fake(body_of(xss)))
        await ready(pg)
        await pg.click('#pnOpen')
        await pg.evaluate("document.querySelectorAll('.pnh').forEach(h=>{if(h.getAttribute('aria-expanded')!=='true')h.click()})")
        await pg.wait_for_timeout(150)
        r = await pg.evaluate("""({xss:window.__xss,bad:document.querySelectorAll('#pnBody script,#pnBody img,#pnBody svg,#pnBody style,#pnBody i,#pnBody [onerror],#pnBody [onload],#pnBody [onmouseover]').length,
           bodyVis:getComputedStyle(document.body).display,cards:document.querySelectorAll('.pncard').length,txt:document.getElementById('pnBody').innerText,
           bold:[...document.querySelectorAll('#pnBody b')].map(b=>b.textContent),code:[...document.querySelectorAll('#pnBody code')].map(b=>b.textContent),
           hs:[...document.querySelectorAll('.pnday h3')].map(h=>h.textContent)})""")
        check('XSS: 스크립트·onerror·onload 가 실행되지 않는다', r['xss'] is None, r['xss'])
        check('XSS: 주입된 img/svg/script/style/i 요소가 없다', r['bad'] == 0, r['bad'])
        check('XSS: 글자 그대로 보인다(<script>·<img·<svg)', '<script>window.__xss=1</script>' in r['txt'] and '<img src=x onerror="window.__xss=2">' in r['txt'] and '"><svg onload="window.__xss=3">' in r['txt'], r['txt'][:200])
        check('XSS: <style> 문자열도 글자일 뿐 화면이 안 사라진다', r['bodyVis'] != 'none' and '<style>body{display:none}</style>' in r['txt'])
        check('XSS: 종류(tag)·날짜·id 의 주입도 글자일 뿐', '<img src=x onerror=window.__xss=6>' in r['txt'] and '날짜 미상' in r['hs'] and r['xss'] is None)
        check('서식: **굵게** 만 굵게', '굵은 제목' in r['bold'] and '굵게' in r['bold'] and not any('<' in x for x in r['bold']), r['bold'])
        check('서식: `코드` 만 코드(안쪽 ** 는 글자 그대로)', '코드' in r['code'] and '**코드 안은 굵게 안 됨**' in r['code'] and '<i>how</i>' in r['code'], r['code'])
        check('서식: 짝 없는 백틱·별표는 글자 그대로', '짝 없는 `백틱 하나' in r['txt'] and '**짝 없는 별표' in r['txt'])
        # sv 5건 + 옛 항목 1 + {'game':'sv'}(빈 항목) = 6 + x0..x3 중 → 계산: x0,x1,x2,x3,old,{'game':'sv'} = 6
        check('가짜 데이터 분류: sv 4건 + 옛 항목 안전망 1건 + 빈 game:sv 1건, brj·null·문자열·숫자 제외 = 6', r['cards'] == 6, r['cards'])
        ov = await pg.evaluate("(()=>{const bx=document.querySelector('.pnbox'),bd=document.getElementById('pnBody');return {bx:bx.scrollWidth<=bx.clientWidth,bd:bd.scrollWidth<=bd.clientWidth+1,doc:document.documentElement.scrollWidth<=innerWidth,cards:[...document.querySelectorAll('.pncard')].every(c=>c.getBoundingClientRect().right<=bx.getBoundingClientRect().right+1)}})()")
        check('360×640 + 긴 글자(띄어쓰기 없는 300자)에도 가로 넘침 없음', all(ov.values()), ov)
        check('[가짜 XSS 데이터] 스크립트·콘솔 오류 없음', not errs, errs)
        await ctx.close()

        # ── 6. 빈 목록 · 404 · 잘못된 JSON · 형식 이상 · 느린 응답 · 다시 불러오기 ────────
        async def one(label, handler, expect, wait_state='ok', tid=None):
            ctx, pg, errs, reqs = await mk(b, srv.port, pn=handler)
            await pg.wait_for_function("__pn.st!=='loading'&&__pn.st!=='idle'", timeout=20000)
            await pg.click('#pnOpen'); await pg.wait_for_timeout(120)
            t = await body_text(pg)
            check(label, expect in t and await is_open(pg), t[:120])
            check(label + ' — 배지는 달리지 않는다', await pg.evaluate("document.getElementById('pnBadge').hidden"))
            check(label + ' — 오류 없음', not errs, errs)
            await ctx.close()
        await one('빈 목록 → 안내 문구', fake(body_of([])), '아직 올라온 패치노트가 없어요')
        await one('서바이벌 항목이 하나도 없으면 같은 안내', fake(body_of([dict(id='a', date=days_ago(1), tag='신규', area='brj', title='브장신', how='', lines=['x'])])), '아직 올라온 패치노트가 없어요')
        await one('404 → 못 불러왔어요 안내', fake('not found', status=404, ctype='text/plain'), '패치노트를 못 불러왔어요 — 잠시 뒤 다시 눌러 주세요', 'err')
        await one('잘못된 JSON → 못 불러왔어요 안내', fake('{not json', ctype='application/json'), '패치노트를 못 불러왔어요', 'err')
        await one('notes 가 배열이 아니면 → 못 불러왔어요 안내', fake('{"notes":{"a":1}}'), '패치노트를 못 불러왔어요', 'err')
        await one('JSON 이 null 이어도 → 못 불러왔어요 안내', fake('null'), '패치노트를 못 불러왔어요', 'err')
        # 네트워크 끊김
        async def boom(r): await r.abort()
        await one('네트워크 실패 → 못 불러왔어요 안내', boom, '패치노트를 못 불러왔어요', 'err')
        # 실패 → 다시 불러오기 성공
        state = {'ok': False}
        async def flaky(r):
            if state['ok']: await r.fulfill(status=200, body=body_of([note(1)]), content_type='application/json')
            else: await r.fulfill(status=500, body='x', content_type='text/plain')
        ctx, pg, errs, reqs = await mk(b, srv.port, w=360, h=640, pn=flaky)
        await pg.wait_for_function("__pn.st==='err'", timeout=20000)
        await pg.click('#pnOpen'); await pg.wait_for_timeout(100)
        check('실패 상태에서 열면 안내와 「다시 불러오기」 버튼', '못 불러왔어요' in await body_text(pg) and await pg.locator('#pnRetry').count() == 1)
        rb = await pg.evaluate("document.getElementById('pnRetry').getBoundingClientRect().height")
        check('다시 불러오기 버튼 높이 44px 이상', rb >= 44, rb)
        await shot(pg, '5_error_360x640.png')
        state['ok'] = True
        await pg.click('#pnRetry'); await pg.wait_for_selector('.pncard', timeout=8000)
        check('다시 불러오기를 누르면 목록이 뜬다', await pg.locator('.pncard').count() == 1 and '제목 1' in await body_text(pg))
        n_before = len(reqs); await pg.click('#pnX'); await pg.click('#pnOpen'); await pg.wait_for_timeout(100)
        check('성공 결과는 메모리에 둔다(다시 열어도 요청 안 함)', len(reqs) == n_before and await pg.locator('.pncard').count() == 1, (n_before, len(reqs)))
        await ctx.close()
        # 느린 응답
        ctx, pg, errs, reqs = await mk(b, srv.port, pn=fake(body_of([note(1), note(2)]), delay=2.0))
        await pg.click('#pnOpen'); await pg.wait_for_timeout(250)
        check('느린 응답: 불러오는 중 문구가 먼저 보인다', '불러오는 중' in await body_text(pg) and await is_open(pg))
        await shot(pg, '6_loading_390x844.png')
        await pg.wait_for_selector('.pncard', timeout=10000)
        check('느린 응답: 도착하면 목록으로 바뀐다', await pg.locator('.pncard').count() == 2)
        check('느린 응답에서도 요청은 1번(미리 읽기와 합쳐짐)', len(reqs) == 1, reqs)
        check('느린 응답: 오류 없음', not errs, errs)
        await ctx.close()
        # 느린 응답 중에 닫았다가 도착 → 닫힌 채 유지
        ctx, pg, errs, reqs = await mk(b, srv.port, pn=fake(body_of([note(1)]), delay=1.2))
        await pg.click('#pnOpen'); await pg.click('#pnX'); await pg.wait_for_timeout(1800)
        check('응답이 오기 전에 닫으면 도착해도 겹창이 다시 열리지 않는다', not await is_open(pg))
        check('그래도 배지는 계산된다', not await pg.evaluate("document.getElementById('pnBadge').hidden"))
        await ctx.close()

        # ── 7. 저장소 차단 환경 ────────────────────────────────────────────────
        block = """(function(){const th=function(){throw new DOMException('blocked','SecurityError')};
          try{Object.defineProperty(window,'localStorage',{get:th,configurable:true});}catch(e){}
          try{Object.defineProperty(window,'sessionStorage',{get:th,configurable:true});}catch(e){}})();"""
        ctx, pg, errs, reqs = await mk(b, srv.port, init=block)
        await ready(pg)
        check('저장소 차단: (환경 확인) localStorage 접근이 실제로 예외를 낸다', await pg.evaluate("(()=>{try{localStorage.getItem('x');return false}catch(e){return true}})()"))
        check('저장소 차단: 배지가 뜬다', not await pg.evaluate("document.getElementById('pnBadge').hidden"))
        await pg.click('#pnOpen')
        check('저장소 차단: 열린다 · 항목 수 맞음', await is_open(pg) and await pg.locator('.pncard').count() == len(SV))
        check('저장소 차단: 연 뒤 배지는(메모리로) 사라진다', await pg.evaluate("document.getElementById('pnBadge').hidden"))
        await pg.click('#pnX'); await pg.click('#startBtn'); await pg.wait_for_timeout(150)
        check('저장소 차단: 판 시작도 정상', await pg.evaluate("__p6x.state") == 'play')
        check('저장소 차단: 오류 없음', not errs, errs)
        await ctx.close()

        # ── 8. 모바일 360×640 · 가로 844×390 (실제 데이터) ──────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port, w=360, h=640)
        await ready(pg)
        await shot(pg, '2_title_360x640.png')
        await pg.click('#pnOpen')
        m = await pg.evaluate("""(()=>{const bx=document.querySelector('.pnbox').getBoundingClientRect(),bd=document.getElementById('pnBody');return {l:bx.left,r:bx.right,t:bx.top,b:bx.bottom,vw:innerWidth,vh:innerHeight,sw:bd.scrollWidth,cw:bd.clientWidth,sh:bd.scrollHeight,ch:bd.clientHeight,doc:document.documentElement.scrollWidth}})()""")
        check('360×640: 겹창이 화면 안에 들어오고 가로 넘침 없음', m['l'] >= 0 and m['r'] <= m['vw'] and m['t'] >= 0 and m['b'] <= m['vh'] and m['sw'] <= m['cw'] + 1 and m['doc'] <= m['vw'], m)
        check('360×640: 목록이 안에서 스크롤된다(내용 > 보이는 높이)', m['sh'] > m['ch'], m)
        await pg.evaluate("document.getElementById('pnBody').scrollTop=600")
        check('스크롤하면 위치가 바뀐다', await pg.evaluate("document.getElementById('pnBody').scrollTop") > 100)
        sticky = await pg.evaluate("document.querySelector('.pnsum').getBoundingClientRect().top-document.getElementById('pnBody').getBoundingClientRect().top")
        check('스크롤해도 요약 칩 줄은 위에 붙어 있다(세로)', abs(sticky) < 2, sticky)
        await pg.evaluate("document.getElementById('pnBody').scrollTop=0")
        chipk = next(i for i, e in enumerate(exp) if e > 0) if any(exp) else 0
        await pg.locator('.pnchip').nth(chipk).click()
        await shot(pg, '3_filtered_360x640.png')
        await pg.click('.pnchip >> nth=%d' % chipk)
        await pg.click('#pnX')
        check('[360×640] 오류 없음', not errs, errs)
        await ctx.close()
        # 터치(탭)로도 동작
        ctx, pg, errs, reqs = await mk(b, srv.port, w=390, h=844)
        await ready(pg)
        await pg.tap('#pnOpen'); check('터치: 탭으로 열린다', await is_open(pg))
        await pg.locator('.pncard').nth(2).locator('.pnh').tap()
        check('터치: 카드 탭으로 펼쳐진다', 'on' in (await pg.locator('.pncard').nth(2).get_attribute('class')))
        await shot(pg, '4_open_390x844.png')
        await pg.tap('#pnX'); check('터치: ✕ 탭으로 닫힌다', not await is_open(pg))
        await ctx.close()
        ctx, pg, errs, reqs = await mk(b, srv.port, w=844, h=390)
        await ready(pg)
        await pg.click('#pnOpen')
        m = await pg.evaluate("""(()=>{const bx=document.querySelector('.pnbox').getBoundingClientRect(),bd=document.getElementById('pnBody').getBoundingClientRect();return {t:bx.top,b:bx.bottom,vh:innerHeight,bodyH:bd.height,doc:document.documentElement.scrollWidth,vw:innerWidth}})()""")
        check('가로 844×390: 겹창이 화면 안 · 목록 영역이 150px 이상', m['t'] >= 0 and m['b'] <= m['vh'] and m['bodyH'] >= 150 and m['doc'] <= m['vw'], m)
        await shot(pg, '7_landscape_844x390.png')
        await pg.keyboard.press('Escape')
        check('[가로] 오류 없음', not errs, errs)
        await ctx.close()

        # ── 9. 데스크톱 폭 ──────────────────────────────────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port, w=1280, h=800, mobile=False)
        await ready(pg)
        await pg.click('#pnOpen')
        bw = await pg.evaluate("document.querySelector('.pnbox').getBoundingClientRect().width")
        check('데스크톱: 겹창 폭이 520px 이하로 유지', 300 < bw <= 520, bw)
        await shot(pg, '8_desktop_1280x800.png')
        check('[데스크톱] 오류 없음', not errs, errs)
        await ctx.close()
        await b.close()
    srv.close()
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
