# -*- coding: utf-8 -*-
"""🛡 멸망전 팀 페이지 시험 — 합성 시트 + 가짜 AUC.GG 응답(제10회 2팀)으로 팀 페이지를 열어 본다.
  A 선수 카드 5장 · 팀 정보 · 경기 일정 칸이 그려진다  B 없는 팀은 안내  C 제9회(내장) 팀도 열린다  D 주소 #team/<회차>/<팀장> 이 붙고 붙여 넣으면 열린다  E 페이지 오류 0
  python3 tests/web_team_test.py"""
import asyncio, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
try:
    import replay as R, synth
    import openpyxl
except Exception as e:
    print('SKIP  playwright/openpyxl 없음 (%s)' % e); sys.exit(0)
names = [n.split('#')[0] for n in synth.plain_names()]
CAPA, CAPB = names[0], names[1]
mkp = lambda n, pos, pr: {'nickname': n, 'position': pos, 'tier': '마스터', 'price': pr, 'pick': None}
D = {'id': 30, 'name': '제 10회 멸망전', 'mode': 'AUCTION', 'finishedAt': '2026-01-01T10:00:00.000Z', 'stages': [], 'teams': [
    {'id': 1, 'name': 'A', 'captain': CAPA, 'players': [mkp(names[2], 'TOP', 300), mkp(names[3], 'JGL', 200), mkp(names[4], 'MID', 100), mkp(names[5], 'BOT', 50)]},
    {'id': 2, 'name': 'B', 'captain': CAPB, 'players': [mkp(names[6], 'TOP', 10), mkp(names[7], 'JGL', 20), mkp(names[8], 'MID', 30), mkp(names[9], 'BOT', 40)]}]}
L = {'tournaments': [{'id': 30, 'name': '제 10회 멸망전', 'mode': 'AUCTION', 'createdAt': '2025-12-25T00:00:00.000Z', 'finishedAt': '2026-01-01T10:00:00.000Z', 'teamCount': 2, 'champion': None}]}
fails = 0
def ok(c, m):
    global fails; print(('  ok   ' if c else '  FAIL ') + m); fails += (not c)

async def after(pg):
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    async def h(route):
        u = route.request.url
        body = json.dumps(L if u.endswith('/tournaments') else D)
        await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=body)
    await pg.route('**/auc-gg.up.railway.app/**', h)
    await pg.evaluate("localStorage.removeItem('aucgg_v1'); AUCGG.state='idle'; AUCGG.t=0; _aucLastTry=0;")
    await pg.evaluate("go('team','10|%s')" % CAPA)
    for _ in range(40):
        await pg.wait_for_timeout(200)
        if await pg.evaluate("document.querySelectorAll('.tp-pc').length") >= 5: break
    o = await pg.evaluate("""()=>({cards:document.querySelectorAll('.tp-pc').length,cap:document.querySelectorAll('.tp-pc.cap').length,h1:(document.querySelector('.tp-hero h1')||{}).textContent,
      info:!!document.querySelector('.tp-info'),sched:!!document.querySelector('.tp-mw'),hash:location.hash,emb:!!document.querySelector('.tp-emb svg'),edit:!!document.querySelector('.tp-edit')})""")
    ok(o['cards'] == 5 and o['cap'] == 1, 'A 선수 카드 5장(팀장 1)')
    ok(o['h1'] == CAPA and o['info'] and o['sched'] and o['emb'] and o['edit'], 'A 제목·팀 정보·경기 일정·엠블럼·꾸미기 버튼')
    ok(o['hash'].startswith('#team/10/'), 'D 주소에 #team/10/<팀장> 이 붙는다 (%s)' % o['hash'][:30])
    await pg.evaluate("go('team','10|없는팀')"); await pg.wait_for_timeout(400)
    ok('없어요' in await pg.evaluate("(document.querySelector('.tp-root')||{innerText:''}).innerText"), 'B 없는 팀은 안내 문구')
    await pg.evaluate("go('team','9|수직낙하하는중')"); await pg.wait_for_timeout(600)
    n9 = await pg.evaluate("document.querySelectorAll('.tp-pc').length")
    ok(n9 == 5, 'C 제9회(내장) 팀 페이지도 선수 카드 5장 (%d)' % n9)
    t = await pg.evaluate("document.querySelector('.tp-info').innerText")
    ok('우승' in t, 'C 제9회 우승팀 역대 기록에 「우승」 (수직낙하하는중)')
    await pg.evaluate("location.hash='#team/10/%s'" % CAPB)
    for _ in range(30):
        await pg.wait_for_timeout(200)
        if await pg.evaluate("(document.querySelector('.tp-hero h1')||{}).textContent") == CAPB: break
    ok(await pg.evaluate("(document.querySelector('.tp-hero h1')||{}).textContent") == CAPB, 'D 주소창에 #team/10/<팀장> 을 붙여 넣으면 그 팀이 열린다')
    ok(not errs, 'E 페이지 오류 0 %s' % errs[:2])

async def main():
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); wb = openpyxl.Workbook(); wb.remove(wb.active)
        for n, rs in synth.build_tabs().items():
            ws = wb.create_sheet(n)
            for r in rs: ws.append(r)
        wb.save(x)
        await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, out=td, focus=(), shots=False, viewport=(1100, 900), after=after, quiet=True)
asyncio.run(main())
print('전부 통과' if not fails else '실패 %d건' % fails); sys.exit(1 if fails else 0)
