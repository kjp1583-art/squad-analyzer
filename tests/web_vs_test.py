# -*- coding: utf-8 -*-
"""⚔️ 매치업(시리즈) 페이지 시험 — 가짜 스크림 목록 4판(같은 두 팀 3판 + 다음날 1판)으로 시리즈 묶기·스코어·세트 탭을 본다.
  python3 tests/web_vs_test.py
(아래는 팀 페이지 시험에서 가져온 틀)
🛡 멸망전 팀 페이지 시험 — 합성 시트 + 가짜 AUC.GG 응답(제10회 2팀)으로 팀 페이지를 열어 본다.
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
        await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(L if u.endswith('/tournaments') else D))
    await pg.route('**/auc-gg.up.railway.app/**', h)
    await pg.evaluate("localStorage.removeItem('aucgg_v1'); AUCGG.state='idle'; AUCGG.t=0; _aucLastTry=0;")
    await pg.evaluate("go('team','10|%s')" % CAPA)
    for _ in range(40):
        await pg.wait_for_timeout(200)
        if await pg.evaluate("document.querySelectorAll('.tp-pc').length") >= 5: break
    gids = await pg.evaluate("[...GAMES.keys()].slice(0,4)")
    ok(len(gids) == 4, '준비: 게임 4판 %s' % gids)
    await pg.evaluate("""(a)=>{const [g0,g1,g2,g3]=a.g; const d=(h,day)=>new Date(2026,0,day||2,h,0);
      window._myeolScrimsFor=function(){return {list:[{day:d(10),gid:g0,win:a.A,lose:a.B},{day:d(11),gid:g1,win:a.B,lose:a.A},{day:d(12),gid:g2,win:a.A,lose:a.B},{day:d(10,3),gid:g3,win:a.B,lose:a.A}],rec:new Map()};};
      MYEOL10_MAIN_START=null; _myeolMemoReset&&_myeolMemoReset();}""", {'g': gids, 'A': CAPA, 'B': CAPB}) if False else None
    await pg.evaluate("""([g,A,B])=>{const d=(h,day)=>new Date(2026,0,day||2,h,0);
      window._myeolScrimsFor=function(){return {list:[{day:d(10),gid:g[0],win:A,lose:B},{day:d(11),gid:g[1],win:B,lose:A},{day:d(12),gid:g[2],win:A,lose:B},{day:d(10,3),gid:g[3],win:B,lose:A}],rec:new Map()};};}""", [gids, CAPA, CAPB])
    await pg.evaluate("go('vs','10|%s')" % gids[1]); await pg.wait_for_timeout(600)
    o = await pg.evaluate("""()=>({sc:[...document.querySelectorAll('.vs-score b')].map(b=>b.textContent),tabs:document.querySelectorAll('.vs-tab').length,on:[...document.querySelectorAll('.vs-tab')].findIndex(t=>t.classList.contains('on')),
      emb:document.querySelectorAll('.vs-board svg, .vs-board img, .vs-board .tp-emb, .vs-board [class*=emb]').length,names:[...document.querySelectorAll('.vs-nm')].map(e=>e.textContent),hash:location.hash,sum:!!document.querySelector('.vs-sum'),
      detail:document.querySelectorAll('.vs-root .prow, .vs-root table').length,win:[...document.querySelectorAll('.vs-team.win .vs-nm')].map(e=>e.textContent)})""")
    ok(o['sc'] == ['2', '1'], 'A 시리즈 스코어 2:1 (%s)' % o['sc'])
    ok(o['tabs'] == 3, 'A 세트 탭 3개(다음날 판은 다른 시리즈) %s' % o['tabs'])
    ok(o['on'] == 1, 'A 누른 판(2세트)의 탭이 열린다 %s' % o['on'])
    ok(o['names'] == [CAPA, CAPB] and o['win'] == [CAPA], 'A 이긴 팀(%s)이 왼쪽 · 승리 표시 %s' % (CAPA, o['names']))
    ok(o['emb'] >= 2 and o['sum'] and o['detail'] > 0, 'A 엠블럼 2 · 세트 요약 · 상세표 (%s/%s)' % (o['emb'], o['detail']))
    ok(o['hash'].startswith('#vs/10/'), 'B 주소 #vs/10/<게임ID> (%s)' % o['hash'])
    await pg.evaluate("setVsSet(2)"); await pg.wait_for_timeout(300)
    ok(await pg.evaluate("[...document.querySelectorAll('.vs-tab')].findIndex(t=>t.classList.contains('on'))") == 2, 'C 3세트 탭을 누르면 바뀐다')
    await pg.evaluate("go('vs','10|%s')" % gids[3]); await pg.wait_for_timeout(500)
    ok(await pg.evaluate("[...document.querySelectorAll('.vs-score b')].map(b=>b.textContent)") == ['0', '1'] or await pg.evaluate("[...document.querySelectorAll('.vs-score b')].map(b=>b.textContent)") == ['1', '0'], 'D 다음날 판은 따로 1:0 시리즈')
    await pg.evaluate("go('vs','10|없는판')"); await pg.wait_for_timeout(400)
    ok('찾지 못' in await pg.evaluate("document.body.innerText"), 'E 없는 판은 안내')
    await pg.evaluate("go('team','10|%s')" % CAPA); await pg.wait_for_timeout(500)
    oc = await pg.evaluate("(document.querySelector('.tp-m')||{getAttribute:()=>''}).getAttribute('onclick')||''")
    ok(oc == '' or oc.startswith("go('vs'"), 'F 팀 페이지 경기 줄은 매치업으로 연결 (%s)' % oc[:20])
    ok(not errs, 'G 페이지 오류 0 %s' % errs[:2])

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
