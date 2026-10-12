# -*- coding: utf-8 -*-
"""🏛 흐접새우 서바이벌 「명예의 전당」 대시보드 + 순위표 시즌 머리말·클리어 수·메달·총랭킹 — 가짜 JSON(page.route)으로 확인한다.
   시즌 전환·표 렌더·1위 강조·404/빈 응답 안내·esc(스크립트 주입)·폰 320/360/412 가로 넘침·옛 서버 응답(season/clears 없음)·메달 순위·총랭킹.
   사용: python3 tests/survivors_hall_test.py        (임시 사본 survivors_x.html 을 만든다 — 커밋하지 않는다)"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:300] if x and not c else ''), flush=True)
    if not c: FAILS.append(n)

XSS = '<img src=x onerror="window.__xss=1">'
XSS2 = '</script><script>window.__xss=2</script>'
LONG = 'ㅁ' * 30 + 'A' * 40
def rows(n, base=3000, name=lambda i: 'u%d' % i, clears=True):
    out = []
    for i in range(n):
        r = {'name': name(i), 't': base - i * 7, 'kills': 900 - i, 'lv': 30 - i % 20, 'ch': 'bbb' if i % 2 else 'zzzz'}
        if clears: r['clears'] = i % 4
        out.append(r)
    return out
def season(n, **kw):
    d = {'season': n, 'start': '2026-09-01', 'end': '2026-09-30', 'normal': rows(120), 'hard': rows(5, 2000), 'vhard': rows(3, 900),
         'endless': rows(4, 5000, clears=False), 'endless_h': [], 'endless_v': [],
         'total': [{'name': 'T%d' % i, 'pts': 6000 - i * 100, 't_n': 3000 - i * 10, 't_h': 2000, 't_v': 1000 - i * 90, 'kills': 100, 'clears': 5 - i} for i in range(5)],
         'medals': {'normal': [{'rank': 1, 'name': 'u0'}, {'rank': 2, 'name': 'u1'}, {'rank': 3, 'name': 'u2'}],
                    'hard': [{'rank': 1, 'name': 'u0'}, {'rank': 2, 'name': 'u1'}, {'rank': 3, 'name': 'u2'}],
                    'vhard': [{'rank': 1, 'name': 'u1'}, {'rank': 2, 'name': 'u0'}]}}
    d.update(kw); return d
IDX = {'seasons': [{'season': 1, 'start': '2026-01-01', 'end': '2026-10-11'}]}

def js(o): return json.dumps(o, ensure_ascii=False)
async def mk(b, port, files, board=None, w=390, h=844, me=None):
    """files: {'index.json': text|(status,text)} · board: /p6/board 응답 dict(없으면 옛 서버처럼 기본 칸만)"""
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=False, has_touch=w < 600, device_scale_factor=1)
    errs, reqs = [], []
    async def gen(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:%d/data/sv_seasons/' % port):
            reqs.append(u)
            name = u.split('/data/sv_seasons/')[1].split('?')[0]
            v = files.get(name)
            if v is None: await r.fulfill(status=404, body='not found', content_type='text/plain'); return
            st, body = (v if isinstance(v, tuple) else (200, v))
            await r.fulfill(status=st, body=body, content_type='application/json'); return
        if u.startswith('http://127.0.0.1:%d/' % port): await r.continue_(); return
        hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
        if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
        if '/p6/board' in u:
            await r.fulfill(status=200, headers=hdr, content_type='application/json', body=js(board if board is not None else {'board': rows(3, 800, clears=False), 'hard': [], 'vhard': []})); return
        if '/p6/me' in u:
            await r.fulfill(status=200, headers=hdr, content_type='application/json', body=js(me or {'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1, 'daily_done': False})); return
        await r.abort()
    await ctx.route('**/*', gen)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/survivors_x.html' % port)
    await pg.wait_for_function('window.__p6x!==undefined&&window.__hall!==undefined', timeout=20000)
    await pg.wait_for_timeout(250)
    return ctx, pg, errs, reqs
async def opn(pg):
    await pg.evaluate("document.getElementById('hallOpen').click()")
    await pg.wait_for_function("__hall.st!=='loading'&&__hall.st!=='idle'", timeout=20000)
    await pg.wait_for_timeout(250)
async def settle(pg): await pg.wait_for_timeout(300)
async def txt(pg): return await pg.evaluate("document.getElementById('hlBody').innerText")
async def overflow(pg):
    return await pg.evaluate("""()=>{const o=[],bd=document.getElementById('hlBody'),bx=document.querySelector('.hlbox');
      if(document.documentElement.scrollWidth>innerWidth+1)o.push('page '+document.documentElement.scrollWidth);
      if(bd.scrollWidth>bd.clientWidth+1)o.push('body '+bd.scrollWidth+'>'+bd.clientWidth);
      const r=bx.getBoundingClientRect();if(r.left<-1||r.right>innerWidth+1)o.push('box');
      for(const e of bd.querySelectorAll('*')){const q=e.getBoundingClientRect();if(q.width&&(q.right>r.right+1||q.left<r.left-1)){o.push(e.className+':'+Math.round(q.right)+'>'+Math.round(r.right));break;}}
      return o;}""")
async def board_overflow(pg):
    return await pg.evaluate("""()=>{const o=[],bd=document.getElementById('board'),r=bd.getBoundingClientRect();
      if(document.documentElement.scrollWidth>innerWidth+1)o.push('page '+document.documentElement.scrollWidth);
      for(const e of bd.querySelectorAll('*')){const q=e.getBoundingClientRect();if(q.width&&(q.right>innerWidth+1||q.left<-1)){o.push(e.tagName+'.'+e.className+':'+Math.round(q.right));break;}}
      return o;}""")

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)

        # ── 1. 아직 아무것도 없을 때(index.json 404) ─────────────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port, {})
        check('첫 화면에 「🏛 명예의 전당」 버튼', await pg.evaluate("/명예의 전당/.test(document.getElementById('hallOpen').textContent)"))
        await opn(pg)
        t = await txt(pg)
        check('index 404 → 「시즌1 기록 준비 중」 안내', '시즌1 기록 준비 중' in t, t)
        check('규칙 안내 문구(매달 1일 마감 · 1~3위 메달)', '매달 1일 마감' in t and '1~3위' in t and '🥇🥈🥉' in t, t)
        check('404 에서 예외 없음', errs == [], errs)
        await pg.keyboard.press('Escape')
        check('Esc 로 닫힘', not await pg.evaluate("__hall.opened"))
        await ctx.close()

        # index 가 있는데 비었거나 모양이 틀림 → 같은 안내
        for name, body in [('빈 seasons', js({'seasons': []})), ('모양이 틀림', '"x"'), ('깨진 JSON', '{not json')]:
            ctx, pg, errs, reqs = await mk(b, srv.port, {'index.json': body})
            await opn(pg)
            check('index %s → 준비 중 안내(예외 없음)' % name, '준비 중' in await txt(pg) and errs == [], (await txt(pg), errs))
            await ctx.close()
        # 서버 오류(500) → 다시 불러오기 버튼, 누르면 복구
        state = {'n': 0}
        ctx, pg, errs, reqs = await mk(b, srv.port, {'index.json': (500, 'err')})
        await opn(pg)
        check('index 500 → 오류 안내 + 다시 불러오기', '못 불러왔어요' in await txt(pg) and await pg.evaluate("!!document.getElementById('hlRetry')"))
        await ctx.close()

        # ── 2. 시즌 1 보관본 표시 ────────────────────────────────────────────────
        s1 = season(1)
        s1['normal'][0]['name'] = XSS; s1['normal'][1]['name'] = XSS2; s1['normal'][2]['name'] = LONG
        s1['medals']['normal'][0]['name'] = XSS; s1['medals']['normal'][1]['name'] = XSS2; s1['medals']['normal'][2]['name'] = LONG
        files = {'index.json': js(IDX), 'season1.json': js(s1)}
        ctx, pg, errs, reqs = await mk(b, srv.port, files, board={'board': rows(3, 800), 'hard': [], 'vhard': [], 'season': 2, 'season_start': '2026-10-12', 'season_end': '2026-10-31', 'days_left': 19})
        await opn(pg)
        t = await txt(pg)
        check('시즌 칩: 진행 중 시즌 2 와 마감된 시즌 1 (최신부터)', await pg.evaluate("[...document.querySelectorAll('#hlBody [data-s]')].map(e=>e.textContent)") == ['시즌 2 · 진행 중', '시즌 1'], t)
        check('처음엔 가장 최근에 마감된 시즌(시즌 1) 표가 보인다', await pg.evaluate("__hall.sel") == 1 and '시즌 1' in t and '전체 120명' in t, t[:200])
        check('XSS 이름이 태그로 실행되지 않고 글자로 보인다', await pg.evaluate("!window.__xss&&!document.querySelector('#hlBody img[onerror]')&&document.getElementById('hlBody').innerHTML.indexOf('<img src=x')<0") and 'onerror' in t)
        check('script 닫기 주입도 글자로만', await pg.evaluate("!window.__xss&&document.querySelectorAll('#hlBody script').length===0") and '</script>' in t)
        pods = await pg.evaluate("[...document.querySelectorAll('.hlpl')].map(e=>e.className+'|'+e.innerText.replace(/\\n/g,' '))")
        check('모드별 챔피언 칸: 일반 3명·하드 3명·베리하드 2명', len(pods) == 8, pods)
        check('🥇 1위가 크게(r1) · 시간·킬·클리어수 표기', any('r1' in x and '🥇' in x and '클리어' in x and '킬' in x for x in pods), pods)
        check('표 1위 줄이 강조(top1) · 2·3위는 메달 이모지', await pg.evaluate("document.querySelectorAll('.hlr.top1').length===1&&[...document.querySelectorAll('.hlk')].slice(0,3).map(e=>e.textContent).join('')==='🥇🥈🥉'"))
        check('각 줄에 「클리어 N」', await pg.evaluate("document.querySelectorAll('.hlr .hlc').length===50") , await pg.evaluate("document.querySelectorAll('.hlr .hlc').length"))
        check('50줄만 먼저 · 더 보기', await pg.evaluate("document.querySelectorAll('.hlr').length")==50 and await pg.evaluate("!!document.getElementById('hlMore')"))
        await pg.evaluate("document.getElementById('hlMore').click()"); await settle(pg)
        check('더 보기 → 100줄', await pg.evaluate("document.querySelectorAll('.hlr').length")==100)
        await pg.evaluate("document.getElementById('hlMore').click()"); await settle(pg)
        check('다시 더 보기 → 120줄 · 버튼 사라짐', await pg.evaluate("document.querySelectorAll('.hlr').length")==120 and await pg.evaluate("!document.getElementById('hlMore')"))
        # 모드 전환
        await pg.evaluate("document.querySelector('[data-m=hard]').click()"); await settle(pg)
        check('하드 표 5명', await pg.evaluate("document.querySelectorAll('.hlr').length")==5)
        await pg.evaluate("document.querySelector('[data-m=endless]').click()"); await settle(pg)
        check('무한 표: 클리어 칸 없음(서버가 안 줌) — 줄은 나온다', await pg.evaluate("document.querySelectorAll('.hlr').length")==4 and await pg.evaluate("document.querySelectorAll('.hlr .hlc').length")==0)
        await pg.evaluate("document.querySelector('[data-m=endless_h]').click()"); await settle(pg)
        check('빈 표 → 「기록이 없어요」', '기록이 없어요' in await txt(pg))
        await pg.evaluate("document.querySelector('[data-m=total]').click()"); await settle(pg)
        t = await txt(pg)
        check('총랭킹 표: 총점·난이도별 시간·클리어', '일반 ' in t and '하드 ' in t and '베리 ' in t and '클리어 5' in t and '100:00' in t, t[:300])
        # 진행 중 시즌
        await pg.evaluate("document.querySelector('[data-s=\"2\"]').click()"); await settle(pg)
        t = await txt(pg)
        check('진행 중 시즌 칩 → 「진행 중 — 순위표 탭 참고」', '진행 중 — 순위표 탭 참고' in t, t)
        await pg.evaluate("document.getElementById('hlGo').click()"); await settle(pg)
        check('「순위표 보러 가기」 → 닫힘', not await pg.evaluate("__hall.opened"))
        await pg.evaluate("document.getElementById('hallOpen').click()"); await settle(pg)
        check('다시 열어도 예외 없음', errs == [], errs)
        # 요청에 캐시 우회 쿼리
        check('캐시 우회 쿼리(?cb=)로 읽는다', all('?cb=' in u for u in reqs) and len(reqs) >= 2, reqs)
        await ctx.close()

        # ── 3. 시즌 파일 404(시즌1 준비 중)·여러 시즌 전환 ─────────────────────
        files = {'index.json': js({'seasons': [{'season': 2}, {'season': 1}]}), 'season1.json': js(season(1)), 'season2.json': (404, 'no')}
        ctx, pg, errs, reqs = await mk(b, srv.port, files)
        await opn(pg)
        t = await txt(pg)
        check('가장 최신 시즌 파일이 아직 없으면 그 시즌만 「준비 중」', '시즌 2 기록 준비 중' in t, t[:200])
        await pg.evaluate("document.querySelector('[data-s=\"1\"]').click()"); await settle(pg)
        check('시즌 전환 → 시즌 1 표', '전체 120명' in await txt(pg))
        check('전환해도 예외 없음', errs == [], errs)
        await ctx.close()

        # ── 4. 메달 순위 ─────────────────────────────────────────────────────────
        s2 = season(2, medals={'normal': [{'rank': 1, 'name': 'u1'}, {'rank': 2, 'name': 'u0'}, {'rank': 3, 'name': 'u2'}], 'hard': [{'rank': 1, 'name': 'u1'}], 'vhard': []})
        files = {'index.json': js({'seasons': [{'season': 2}, {'season': 1}, {'season': 3}]}), 'season1.json': js(season(1)), 'season2.json': js(s2), 'season3.json': (404, 'x')}
        ctx, pg, errs, reqs = await mk(b, srv.port, files)
        await opn(pg)
        await pg.evaluate("document.querySelector('.hltab[data-t=m]').click()")
        await pg.wait_for_function("document.querySelectorAll('#hlBody .hlmb').length>0", timeout=10000)
        names = await pg.evaluate("[...document.querySelectorAll('.hlmb')].map(e=>e.innerText.replace(/\\s+/g,' ').trim())")
        # u0: 시즌1 normal🥇 hard🥇 vhard🥈, 시즌2 normal🥈 → 금2 은2 / u1: 시즌1 normal🥈 hard🥈 vhard🥇, 시즌2 normal🥇 hard🥇 → 금3 은2 / u2: 동2(시즌1 normal·hard)+시즌2 동1 = 동3
        check('메달 순위: 금→은→동 순 (u1 금3 은2 → u0 금2 은2 → u2 동3)', names[:3] == ['u1 🥇3 🥈2 🥉0', 'u0 🥇2 🥈2 🥉0', 'u2 🥇0 🥈0 🥉3'], names)
        check('메달 순위 1위 줄 강조', await pg.evaluate("document.querySelectorAll('.hlr.top1').length===1"))
        await pg.evaluate("document.querySelector('.hlmb').click()"); await settle(pg)
        t = await txt(pg)
        check('이름을 누르면 시즌별 수상 내역이 펼쳐진다', '시즌 2 · 일반 🥇' in t and '시즌 1 · 베리하드 🥇' in t, t[:400])
        check('메달 합산 안내(이름 기준 한계)', '이름별로' in t)
        check('메달 순위 예외 없음', errs == [], errs)
        await ctx.close()

        # 메달 목록이 없는 보관본은 표 1~3위로 다시 계산
        s9 = season(1); del s9['medals']
        ctx, pg, errs, reqs = await mk(b, srv.port, {'index.json': js(IDX), 'season1.json': js(s9)})
        await opn(pg)
        await pg.evaluate("document.querySelector('.hltab[data-t=m]').click()")
        await pg.wait_for_function("document.querySelectorAll('#hlBody .hlmb').length>0", timeout=10000)
        names = await pg.evaluate("[...document.querySelectorAll('.hlmb')].map(e=>e.innerText.replace(/\\s+/g,' ').trim())")
        check('medals 없는 보관본: 일반·하드·베리하드 상위 3명으로 계산', names[:1] == ['u0 🥇3 🥈0 🥉0'] and len(names) == 3, names)
        await ctx.close()

        # ── 5. 폰 폭 가로 넘침 ───────────────────────────────────────────────────
        sw = season(1); sw['normal'][0]['name'] = LONG; sw['normal'][1]['name'] = 'W' * 80
        sw['medals']['normal'][0]['name'] = LONG; sw['medals']['normal'][1]['name'] = 'W' * 80
        sw['total'][0]['name'] = LONG
        for w in (320, 360, 412):
            ctx, pg, errs, reqs = await mk(b, srv.port, {'index.json': js({'seasons': [{'season': 1}, {'season': 2}]}), 'season1.json': js(sw), 'season2.json': js(sw)}, w=w)
            await opn(pg)
            o = await overflow(pg); check('폭 %d 시즌 표: 가로 넘침 없음' % w, not o, o)
            await pg.evaluate("document.querySelector('[data-m=total]').click()"); await settle(pg)
            o = await overflow(pg); check('폭 %d 총랭킹 표: 가로 넘침 없음' % w, not o, o)
            await pg.evaluate("document.querySelector('.hltab[data-t=m]').click()")
            await pg.wait_for_function("document.querySelectorAll('#hlBody .hlmb').length>0", timeout=10000); await settle(pg)
            o = await overflow(pg); check('폭 %d 메달 순위: 가로 넘침 없음' % w, not o, o)
            bt = await pg.evaluate("(()=>{const r=document.getElementById('hlX').getBoundingClientRect();return [r.width,r.height]})()")
            check('폭 %d 닫기 버튼 터치 영역 44px' % w, bt[0] >= 44 and bt[1] >= 44, bt)
            await ctx.close()

        # ── 6. 순위표: 시즌 머리말 · 클리어 · 메달 · 총랭킹 ──────────────────────
        bd = {'board': [dict(r, medals={'g': 2, 's': 1, 'b': 0}) if i == 0 else r for i, r in enumerate(rows(4, 3000))] ,
              'hard': rows(2, 1000), 'vhard': [], 'season': 2, 'season_start': '2026-10-12', 'season_end': '2026-10-31', 'days_left': 19,
              'total': [{'name': 'T0', 'pts': 7000, 't_n': 3000, 't_h': 2500, 't_v': 1500, 'clears': 6, 'medals': {'g': 1, 's': 0, 'b': 0}}, {'name': 'T1', 'pts': 100, 't_n': 100, 't_h': 0, 't_v': 0, 'clears': 0}]}
        bd['board'][1]['name'] = XSS
        for w in (320, 360, 412):
            ctx, pg, errs, reqs = await mk(b, srv.port, {}, board=bd, w=w)
            hd = await pg.evaluate("(document.getElementById('seasHd')||{}).textContent||''")
            check('폭 %d 순위표 머리말 「🏆 시즌 2 · 10/31까지 19일」' % w, hd.strip() == '🏆 시즌 2 · 10/31까지 19일', hd)
            t = await pg.evaluate("document.getElementById('board').innerText")
            check('폭 %d 줄마다 「클리어 N」 · 이름 옆 메달 「🥇2 🥈1」' % w, t.count('클리어') == 4 and '🥇2 🥈1' in t, t)
            check('폭 %d 순위표 XSS 안전' % w, await pg.evaluate("!window.__xss&&!document.querySelector('#board img[onerror]')"))
            o = await board_overflow(pg); check('폭 %d 순위표(일반) 가로 넘침 없음' % w, not o, o)
            await pg.evaluate("document.querySelector('#board [data-bt=\"7\"]').click()")
            t = await pg.evaluate("document.getElementById('board').innerText")
            check('폭 %d 총랭킹 탭: 총점·난이도별 시간·클리어 합·메달' % w, '116:40' in t and '일반 50:00' in t and '하드 41:40' in t and '베리 25:00' in t and '클리어 6' in t and '🥇1' in t, t)
            order = await pg.evaluate("[...document.querySelectorAll('#board li')].map(e=>e.innerText.split('\\n')[0].replace(/\\s+/g,' '))")
            check('폭 %d 총랭킹 높은 점수가 먼저(서버 순서 그대로)' % w, order[0].startswith('T0') and order[1].startswith('T1'), order)
            o = await board_overflow(pg); check('폭 %d 순위표(총랭킹) 가로 넘침 없음' % w, not o, o)
            check('폭 %d 순위표 예외 없음' % w, errs == [], errs)
            await ctx.close()

        # ── 7. 옛 서버 응답: season/clears/medals/total 이 없다 ────────────────────
        ctx, pg, errs, reqs = await mk(b, srv.port, {})
        t = await pg.evaluate("document.getElementById('board').innerText")
        check('옛 서버: 머리말·클리어·메달 없이 정상 표시', '시즌' not in t and '클리어' not in t and '🥇' not in t and 'u0' in t, t)
        await pg.evaluate("document.querySelector('#board [data-bt=\"7\"]').click()")
        t = await pg.evaluate("document.getElementById('board').innerText")
        check('옛 서버: 총랭킹 탭은 「준비 중」', '총랭킹 준비 중' in t, t)
        check('옛 서버: 예외 없음', errs == [], errs)
        # 열어도 진행 중 칩 없음(서버가 시즌을 모르면 현재 시즌을 안다고 하지 않는다)
        await opn(pg)
        check('옛 서버: 명예의 전당은 준비 중 안내', '준비 중' in await txt(pg))
        await ctx.close()

        # 잘못된 season 값(문자열·음수·소수)은 무시
        ctx, pg, errs, reqs = await mk(b, srv.port, {}, board={'board': rows(2), 'hard': [], 'vhard': [], 'season': '<b>x</b>', 'season_end': 'x', 'days_left': 'many', 'total': 'nope'})
        t = await pg.evaluate("document.getElementById('board').innerText")
        check('이상한 season 값 → 머리말 생략·예외 없음', '시즌' not in t and errs == [], (t, errs))
        await ctx.close()

        # ── 8. 판 끝 결과 문구: 서버가 season 을 주면 「시즌 N 기준」 ─────────────
        LOGIN = "localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))"
        for withseason in (True, False):
            ws = withseason
            ctx = await b.new_context(viewport={'width': 390, 'height': 844})
            errs = []
            async def gen(r):
                u = r.request.url; hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
                if u.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_(); return
                if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
                if '/p6/board' in u: await r.fulfill(status=200, headers=hdr, content_type='application/json', body=js({'board': [], 'hard': [], 'vhard': []})); return
                if '/p6/me' in u: await r.fulfill(status=200, headers=hdr, content_type='application/json', body=js({'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1})); return
                if '/p6/run' in u:
                    j = {'ok': True, 'rank': 3, 'total': 9, 'unlocks': ['brj'], 'best_t': 50}
                    if ws: j.update({'season': 2, 'total_rank': 4})
                    await r.fulfill(status=200, headers=hdr, content_type='application/json', body=js(j)); return
                await r.abort()
            await ctx.route('**/*', gen)
            pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://127.0.0.1:%d/survivors_x.html' % srv.port)
            await pg.wait_for_function('window.__p6x!==undefined'); await pg.evaluate(LOGIN); await pg.reload(); await pg.wait_for_function('window.__p6x!==undefined')
            await pg.evaluate("__p6x.start();__adv(30,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(600)
            t = await pg.evaluate("document.getElementById('rAcct').textContent")
            if withseason: check('결과 문구: 「시즌 2 기준」 · 총랭킹 순위', '기록 저장' in t and '3위' in t and '시즌 2 기준' in t and '총랭킹 4위' in t, t)
            else: check('옛 서버 결과 문구: 시즌 말 없이 그대로', '기록 저장' in t and '3위' in t and '시즌' not in t and not errs, (t, errs))
            await ctx.close()
        await b.close()
    srv.close()
    print('\nFAILS:', FAILS if FAILS else 'none')
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
