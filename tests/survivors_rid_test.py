# -*- coding: utf-8 -*-
"""🔑 B-11 서바이벌 기록 멱등 키(rid) · busy 코드 — 브라우저(Chromium) 검증.  사용: python3 tests/survivors_rid_test.py
판마다 rid 가 실림 · 재시도 때 같은 rid · 서버가 dup 이면 성공처럼 치움 · busy 는 보관 · rate 는 예전대로 폐기 · 이어하기 뒤에도 같은 rid ·
60분 뒤 무한 이어가기는 다른 rid · 본문 4096바이트 · localStorage 불가."""
import asyncio, sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)
RIDRE = re.compile(r'^[A-Za-z0-9_-]{8,40}$')
POSTS = []
def mk_mock(st):
    async def mock(r):
        u = r.request.url; hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
        if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
        js = lambda o: r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps(o))
        if '/p6/board' in u: await js({'board': [], 'hard': [], 'vhard': [], 'endless': [], 'daily': [], 'daily_date': '2026-10-11'})
        elif '/p6/me' in u: await js({'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': [], 'rank': 1})
        elif '/p6/run' in u:
            b = json.loads(r.request.post_data or '{}'); POSTS.append(b)
            codes = st.get('codes'); c = codes.pop(0) if codes else st.get('code')
            if c == 'NET': await r.abort(); return          # 서버엔 저장됐을 수도 있는 「응답만 못 받음」
            if c == 'dup': await js({'ok': True, 'dup': True}); return
            if c: await js({'ok': False, 'code': c})
            else: await js({'ok': True, 'rank': 3, 'total': 9, 'unlocks': [], 'best_t': b['t']})
        else: await r.fulfill(status=404, headers=hdr, body='{}')
    return mock
LOGIN = "localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))"
EXTRA = "window.__uq={CDX,cdxAttach,qLoad,keepUnsent,flushUnsent,runRid,RES,pauseGame,contEndless,setGap(v){FLUSH_GAP=v},get RUN(){return RUN}};"
async def fresh(b, port, st, pre=None, blockls=False):
    ctx, pg, errs = await H.new_page(b, port, 412, 860, mock=mk_mock(st))
    await pg.evaluate(LOGIN)
    if pre: await pg.evaluate(pre)
    if blockls:
        await pg.add_init_script("(()=>{const g=Storage.prototype.getItem,s=Storage.prototype.setItem;Storage.prototype.getItem=function(k){if(String(k).startsWith('p6_unsent'))throw new Error('blocked');return g.call(this,k)};Storage.prototype.setItem=function(k,v){if(String(k).startsWith('p6_unsent'))throw new Error('blocked');return s.call(this,k,v)}})()")
    await pg.reload(); await pg.wait_for_function('window.__uq!==undefined'); await pg.wait_for_timeout(200)
    await pg.evaluate("__uq.setGap(30)")
    return ctx, pg, errs
RUNJS = "(t)=>{__p6x.start();__adv(t||40,{god:true});__p6x.endRun(false,true)}"
async def run(pg, t=40):
    await pg.evaluate(RUNJS, t); await pg.wait_for_timeout(500)
async def q(pg): return json.loads(await pg.evaluate("localStorage.getItem('p6_unsent_q')") or '[]')
async def retry(pg):
    await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(500)

async def main():
    H.make_copy(extra=EXTRA); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        # 1. rid 가 실리고, 판마다 다르다
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {})
        await run(pg, 40); await run(pg, 41)
        r1, r2 = POSTS[0].get('rid'), POSTS[1].get('rid')
        check('기록 요청에 rid 가 실린다(8~40자 영숫자·_-)', len(POSTS) == 2 and RIDRE.match(str(r1)) and RIDRE.match(str(r2)), (r1, r2))
        check('판마다 rid 가 다르다', r1 != r2, (r1, r2))
        check('예외 없음', errs == [], errs); await ctx.close()
        # 2. 응답을 못 받은 판(NET) → 보관 → 다시 올릴 때 같은 rid · dup 이면 성공과 같게 치움
        POSTS.clear(); st = {'codes': ['NET']}
        ctx, pg, errs = await fresh(b, srv.port, st)
        await run(pg, 40)
        qa = await q(pg)
        check('보관본에 rid 가 함께 들어간다', len(qa) == 1 and qa[0].get('rid') == POSTS[0]['rid'], qa)
        st['code'] = 'dup'; await retry(pg)
        check('다시 올릴 때 같은 rid', len(POSTS) == 2 and POSTS[1]['rid'] == POSTS[0]['rid'], [x.get('rid') for x in POSTS])
        check('서버가 dup 이면 큐에서 빠진다(성공과 같게)', await q(pg) == [], await q(pg))
        txt = await pg.evaluate("document.getElementById('rAcct').textContent")
        check('dup 안내가 쉬운 말', '이미 올라가 있었어요' in txt, txt)
        check('예외 없음', errs == [], errs); await ctx.close()
        # 3. busy 는 버리지 않고 보관(연습 판 10초도) · rate 는 예전 정책
        for t in (40, 10):
            POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {'code': 'busy'})
            await run(pg, t)
            txt = await pg.evaluate("document.getElementById('rAcct').textContent")
            check('[busy t=%d] 판을 보관 + 다시 저장 버튼' % t, len(await q(pg)) == 1 and '다시 저장' in txt and '몰려' in txt, txt)
            await ctx.close()
        POSTS.clear(); st = {'code': 'busy'}; ctx, pg, errs = await fresh(b, srv.port, st)
        await run(pg, 40); st['code'] = None; await retry(pg)
        check('[busy] 나중에 올리면 같은 rid 로 저장되고 큐가 빈다', len(POSTS) == 2 and POSTS[0]['rid'] == POSTS[1]['rid'] and await q(pg) == [])
        await ctx.close()
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {'code': 'rate'})
        await run(pg, 10)
        check('[rate] 30초도 안 된 연습 판은 예전처럼 폐기', await q(pg) == [])
        await ctx.close()
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {'code': 'rate'})
        await run(pg, 40)
        check('[rate] 긴 판은 예전처럼 보관', len(await q(pg)) == 1); await ctx.close()
        # 4. 옛 봇(rid 무시·dup 모름)에도 정상
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {})
        await run(pg, 40)
        check('[옛 봇] dup 없는 일반 성공 응답은 그대로 저장 안내', '기록 저장' in await pg.evaluate("document.getElementById('rAcct').textContent")); await ctx.close()
        # 5. 이어하기 뒤에도 같은 rid
        POSTS.clear(); st = {'codes': ['NET']}
        ctx, pg, errs = await fresh(b, srv.port, st)
        rid0 = await pg.evaluate("()=>{__p6x.start();__adv(20,{god:true});__uq.pauseGame();return __uq.RUN.rid}")
        blob = await pg.evaluate("localStorage.getItem('p6_resume_v1')")
        if blob:
            await pg.reload(); await pg.wait_for_function('window.__uq!==undefined')
            await pg.click('#resGo'); await pg.wait_for_function("__p6x.state==='pause'", timeout=8000)
            rid1 = await pg.evaluate("__uq.RUN.rid")
            check('이어하기로 되살린 판의 판 번호가 같다', rid0 == rid1, (rid0, rid1))
            await pg.evaluate("()=>{__p6x.endRun(false,true)}"); await pg.wait_for_timeout(500)
            check('되살린 판의 기록 rid 가 판 번호에서 나온다', len(POSTS) == 1 and rid0 in POSTS[0]['rid'], (rid0, POSTS))
        else:
            check('이어하기 저장본이 생긴다', False, 'no blob')
        await ctx.close()
        # 6. 60분 클리어 뒤 무한 이어가기는 같은 판의 두 번째 기록 — 다른 rid
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {})
        await pg.evaluate("()=>{__p6x.start();__adv(20,{god:true});__p6x.S.won=true;__p6x.endRun(true)}"); await pg.wait_for_timeout(500)
        await pg.evaluate("()=>{__uq.contEndless();__adv(10,{god:true});__p6x.endRun(false,true)}"); await pg.wait_for_timeout(500)
        check('[무한 이어가기] 같은 판의 두 기록이 서로 다른 rid', len(POSTS) == 2 and POSTS[0]['rid'] != POSTS[1]['rid'] and POSTS[1].get('endless') == 1, [(x.get('rid'), x.get('endless')) for x in POSTS])
        await ctx.close()
        # 7. 본문 4096바이트 — 도감을 최대로 채워도 rid 포함해 넘지 않는다
        ctx, pg, errs = await fresh(b, srv.port, {})
        big = await pg.evaluate("""()=>{const o={token:'x'.repeat(40),t:99,kills:9,lv:5,ch:'brj',won:false,hard:0,vhard:0,unlocks:Array(30).fill('abcdefgh'),rid:__uq.runRid()};
          for(let i=0;i<600;i++)__uq.CDX.s.add('w:k'+i);__uq.cdxAttach(o);return {n:new TextEncoder().encode(JSON.stringify(o)).length,c:(o.codex||[]).length,rid:o.rid}}""")
        check('[본문 한도] 도감을 가득 채워도 rid 포함 4096바이트 이하', big['n'] <= 4096 and big['c'] > 0 and RIDRE.match(big['rid']), big)
        await ctx.close()
        # 8. localStorage 불가 — 오류 없이 rid 로 재시도
        POSTS.clear(); st = {'codes': ['NET']}
        ctx, pg, errs = await fresh(b, srv.port, st, blockls=True)
        await run(pg, 40); await retry(pg)
        check('[저장소 막힘] 같은 탭에서 재시도해도 같은 rid · 오류 없음', len(POSTS) == 2 and POSTS[0]['rid'] == POSTS[1]['rid'] and errs == [], (errs, [x.get('rid') for x in POSTS]))
        await ctx.close()
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('%d/%d' % (N[0] - len(FAILS), N[0])); sys.exit(1 if FAILS else 0)
asyncio.run(main())
