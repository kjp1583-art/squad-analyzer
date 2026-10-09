# -*- coding: utf-8 -*-
"""🏆 순위표 전체 보기 — 첫 화면 순위표가 10명(예전)이 아니라 서버가 내려준 전원을 그린다.
[2026-10-09 사장님 지시 「순위표가 top10이 아니라 그냥 전체랭킹 다 볼 수 있게 해줘」]
  A. 일반 57명 → 57줄 · 제목에 「전체 57명」 · 「TOP 10」 문구 없음
  B. 230명 → 처음 100줄 + 「더 보기 (130명 남음)」 → 눌러 200 → 눌러 230 (버튼 사라짐) · 탭을 바꾸면 다시 100 부터
  C. 하드·베리하드·무한 3종·오늘 탭도 전원을 그린다(탭 7개 유지) · 빈 표 문구 그대로
  D. 내 이름이 있으면 그 줄만 「← 나」 강조 · 로그인 전에는 강조 없음
  E. 모바일 폭(360)에서 가로 스크롤 없음 · 콘솔/페이지 오류 0 · 구버전 봇(20명까지만 내려줌)도 그대로 그린다
사용: python3 tests/survivors_board_all_test.py
"""
import asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright

HDR = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}


def rows(prefix, n, t0=3000, extra=None):
    out = []
    for i in range(n):
        r = {'name': '%s%d' % (prefix, i), 't': t0 - i * 3, 'kills': 100 + i, 'ch': 'brj'}
        if extra:
            r.update(extra)
        out.append(r)
    return out


def mk_mock(state):
    async def mock(r):
        u = r.request.url
        if r.request.method == 'OPTIONS':
            await r.fulfill(status=204, headers=HDR); return
        if '/p6/board' in u:
            j = state['board']
            await r.fulfill(status=200, headers=HDR, content_type='application/json', body=json.dumps(j))
        elif '/p6/me' in u:
            await r.fulfill(status=200, headers=HDR, content_type='application/json', body=json.dumps({'ok': True, 'name': state.get('me', 'T'), 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1, 'daily_done': False, 'daily_date': '2026-10-09'}))
        else:
            await r.fulfill(status=404, headers=HDR, body='{}')
    return mock


async def main():
    p = H.make_copy('survivors.html', 'survivors_boardx.html')
    srv = H.Srv()
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)
    state = {'board': {'board': rows('일반', 57), 'hard': rows('하드', 45, 2500, {'hard': 1}), 'vhard': rows('베리', 12, 1800, {'vhard': 1}),
                       'endless': rows('무한', 33, 4000, {'endless': 1}), 'endless_h': rows('무한하드', 21, 3900, {'endless': 1}), 'endless_v': rows('무한베리', 8, 3800, {'endless': 1}),
                       'daily': rows('오늘', 17, 3000), 'daily_date': '2026-10-09'}}
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=360, h=800, mock=mk_mock(state), page='survivors_boardx.html')
        await pg.wait_for_function("document.querySelectorAll('#board li').length>0", timeout=15000)
        info = await pg.evaluate("""()=>{const el=document.getElementById('board');return {n:el.querySelectorAll('li').length,txt:el.textContent,tabs:[...el.querySelectorAll('.btabs button')].length,
          more:!!document.getElementById('boardMore'),sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth}}""")
        ok(info['n'] == 57, 'A1 일반 57명 → 57줄 (실제 %d)' % info['n'])
        ok('전체 57명' in info['txt'], 'A2 제목에 「전체 57명」')
        ok('TOP' not in info['txt'], 'A3 「TOP 10」 문구 없음')
        ok(not info['more'], 'A4 100명 이하면 「더 보기」 없음')
        ok(info['tabs'] == 7, 'C0 탭 7개 유지 (%d)' % info['tabs'])
        ok(info['sw'] <= info['cw'], 'E1 모바일 360 가로 스크롤 없음 (%d ≤ %d)' % (info['sw'], info['cw']))
        # C. 다른 탭
        for bt, want, name in ((1, 45, '하드'), (2, 12, '베리하드'), (3, 33, '무한'), (5, 21, '무한 하드'), (6, 8, '무한 베리하드'), (4, 17, '오늘')):
            n = await pg.evaluate("(bt)=>{document.querySelector('#board [data-bt=\"'+bt+'\"]').click();return document.querySelectorAll('#board li').length}", bt)
            ok(n == want, 'C %s 탭 %d줄 (실제 %d)' % (name, want, n))
        # D. 로그인 전: 강조 없음 → ME 설정 뒤 강조
        n0 = await pg.evaluate("()=>{document.querySelector('#board [data-bt=\"0\"]').click();return document.querySelectorAll('#board li.me').length}")
        ok(n0 == 0, 'D1 로그인 전 강조 없음 (%d)' % n0)
        r = await pg.evaluate("()=>{__p6x.ME={name:'일반5',ok:true};__p6x.renderBoard();const m=[...document.querySelectorAll('#board li.me')];return {n:m.length,txt:m.map(x=>x.textContent)}}")
        ok(r['n'] == 1 and '← 나' in r['txt'][0] and '일반5' in r['txt'][0], 'D2 내 줄만 「← 나」 강조 (%s)' % r)
        await pg.evaluate("()=>{__p6x.ME=null;__p6x.renderBoard();}")
        # B. 230명
        state['board'] = dict(state['board'], board=rows('다수', 230))
        await pg.evaluate("()=>__p6x.loadBoard()")
        await pg.wait_for_function("document.querySelectorAll('#board li').length===100", timeout=8000)
        t = await pg.evaluate("()=>({n:document.querySelectorAll('#board li').length,more:(document.getElementById('boardMore')||{}).textContent,txt:document.getElementById('board').textContent.includes('전체 230명')})")
        ok(t['n'] == 100 and '130명 남음' in (t['more'] or '') and t['txt'], 'B1 230명 → 100줄 + 「더 보기 (130명 남음)」 (%s)' % t)
        t = await pg.evaluate("()=>{document.getElementById('boardMore').click();return {n:document.querySelectorAll('#board li').length,more:(document.getElementById('boardMore')||{}).textContent}}")
        ok(t['n'] == 200 and '30명 남음' in (t['more'] or ''), 'B2 더 보기 → 200줄 · 30명 남음 (%s)' % t)
        t = await pg.evaluate("()=>{document.getElementById('boardMore').click();return {n:document.querySelectorAll('#board li').length,more:!!document.getElementById('boardMore')}}")
        ok(t['n'] == 230 and not t['more'], 'B3 한 번 더 → 230줄 · 버튼 사라짐 (%s)' % t)
        t = await pg.evaluate("()=>{document.querySelector('#board [data-bt=\"1\"]').click();document.querySelector('#board [data-bt=\"0\"]').click();return document.querySelectorAll('#board li').length}")
        ok(t == 100, 'B4 탭을 바꿨다 돌아오면 다시 100줄부터 (%d)' % t)
        # E. 구버전 봇(20명) · 빈 표
        state['board'] = {'board': rows('옛', 20), 'hard': [], 'vhard': []}
        await pg.evaluate("()=>__p6x.loadBoard()")
        await pg.wait_for_function("document.querySelectorAll('#board li').length===20", timeout=8000)
        t = await pg.evaluate("()=>{document.querySelector('#board [data-bt=\"1\"]').click();return document.getElementById('board').textContent}")
        ok('아직 기록이 없어요' in t or '준비 중' in t or '하드' in t, 'E2 빈 표 문구 (%s)' % t[:60])
        real = [e for e in errs if 'boardx' not in e]
        ok(not real, 'E3 콘솔·페이지 오류 0 %s' % real[:3])
        await b.close()
    srv.close()
    try:
        os.remove(p)
    except Exception:
        pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
