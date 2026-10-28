# -*- coding: utf-8 -*-
"""📚 A-24 서바이벌 '이 기기에 남긴 기록' 큐 — 브라우저(Chromium) 검증.  사용: python3 tests/survivors_unsent_test.py
실패한 판 → 새 판 저장 성공 → 앞 판이 남아 있나 · 다시 저장은 순서대로 · 상한 · 옛 단일 칸 이관 · 429/로그인 만료 보관 · localStorage 불가."""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

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
            codes = st.get('codes')
            c = codes.pop(0) if codes else st.get('code')
            if st.get('rejt') == b.get('t'): c = 'bad_run'   # 이 판은 언제나 거절(영구 거절 재현)
            if c == 'NET': await r.abort(); return
            if c: await js({'ok': False, 'code': c})
            else: await js({'ok': True, 'rank': 3, 'total': 9, 'unlocks': [], 'best_t': b['t']})
        else: await r.fulfill(status=404, headers=hdr, body='{}')
    return mock
LOGIN = "localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))"
EXTRA = "window.__uq={qLoad,qSave,keepUnsent,flushUnsent,setGap(v){FLUSH_GAP=v},get FLUSHING(){return FLUSHING}};"
async def fresh(b, port, st, pre=None, blockls=False):
    ctx, pg, errs = await H.new_page(b, port, 412, 860, mock=mk_mock(st))
    await pg.evaluate(LOGIN)
    if pre: await pg.evaluate(pre)
    if blockls:   # 보관 칸 읽기·쓰기가 막힌 환경(사생활 보호 창 등)
        await pg.add_init_script("(()=>{const g=Storage.prototype.getItem,s=Storage.prototype.setItem;Storage.prototype.getItem=function(k){if(String(k).startsWith('p6_unsent'))throw new Error('blocked');return g.call(this,k)};Storage.prototype.setItem=function(k,v){if(String(k).startsWith('p6_unsent'))throw new Error('blocked');return s.call(this,k,v)};})()")
    await pg.reload(); await pg.wait_for_function('window.__uq!==undefined'); await pg.wait_for_timeout(200)
    await pg.evaluate("__uq.setGap(30)")
    return ctx, pg, errs
RUN = "(t)=>{__p6x.start();__adv(t||40,{god:true});__p6x.endRun(false,true)}"
async def run(pg, t=40):
    await pg.evaluate(RUN, t); await pg.wait_for_timeout(500)
async def q(pg): return json.loads(await pg.evaluate("localStorage.getItem('p6_unsent_q')") or '[]')

async def main():
    H.make_copy(extra=EXTRA); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        # 1. 실패한 판 → 새 판 저장 성공 → 앞 판이 살아 있다 → 다시 저장
        POSTS.clear(); st = {'codes': ['error']}
        ctx, pg, errs = await fresh(b, srv.port, st)
        await run(pg, 40)
        qa = await q(pg)
        check('실패한 판은 큐에 보관', len(qa) == 1 and qa[0]['t'] >= 30, qa)
        check('보관본에 토큰이 없다', 'token' not in json.dumps(qa))
        ta = qa[0]['t']
        await run(pg, 45)   # 이번엔 성공
        qb = await q(pg)
        check('새 판 저장이 성공해도 앞 판은 지워지지 않는다', len(qb) == 1 and qb[0]['t'] == ta, qb)
        n0 = len(POSTS)
        await pg.evaluate("document.getElementById('rAcct').innerHTML='x<button id=\"rRetry\"></button>'"); await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(500)
        check('다시 저장: 앞 판이 올라가고 큐가 비워진다', len(POSTS) == n0 + 1 and POSTS[-1]['t'] == ta and await q(pg) == [], (len(POSTS), n0))
        check('서버로 가는 본문에 내부 표식(_q·_u)이 없다', all('_q' not in x and '_u' not in x for x in POSTS))
        # 2. 큐 여러 판 → 순서대로, 막히면 멈춘다
        POSTS.clear(); st['codes'] = None; st['code'] = 'error'
        for t in (35, 36, 37): await run(pg, t)
        qs = await q(pg); check('실패 3판 → 큐 3칸(같은 판은 중복 없음)', [x['t'] for x in qs] == sorted(x['t'] for x in qs) and len(qs) == 3, [x['t'] for x in qs])
        POSTS.clear(); await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(500)
        check('계속 거절되면 두 판째에서 멈춘다(서버를 두드리지 않는다)', len(POSTS) == 2 and len(await q(pg)) == 3, len(POSTS))
        st['code'] = None; POSTS.clear(); order = [x['t'] for x in qs]
        await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(900)
        check('성공하면 3판이 보관 순서대로 올라가고 큐가 빈다', [x['t'] for x in POSTS] == order and await q(pg) == [], ([x['t'] for x in POSTS], order))
        check('예외 없음', errs == [], errs); await ctx.close()
        # 3. 상한: 개수 20 · 크기
        ctx, pg, errs = await fresh(b, srv.port, {})
        r = await pg.evaluate("""()=>{const u=__uq;let a=[];for(let i=0;i<27;i++)a.push({t:100+i,kills:1,ts:Date.now(),_q:'q'+i});const n=u.qSave(a).length;const l=u.qLoad();
          const big=[];for(let i=0;i<10;i++)big.push({t:i,ts:Date.now(),_q:'b'+i,pad:'x'.repeat(60000)});const m=u.qSave(big);return {n,first:l[0].t,last:l[l.length-1].t,m:m.length,keptLast:m[m.length-1]._q};}""")
        check('큐 상한 20판 — 넘치면 오래된 것부터', r['n'] == 20 and r['first'] == 107 and r['last'] == 126, r)
        check('큐 크기 상한(약 200KB) — 최신 판은 남는다', r['m'] <= 3 and r['keptLast'] == 'b9', r)
        await ctx.close()
        # 4. 옛 단일 칸 이관
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port, {}, pre="localStorage.setItem('p6_unsent',JSON.stringify({t:77,kills:3,lv:5,ch:'brj',won:false,hard:0,vhard:0,unlocks:[],ts:Date.now()}))")
        await pg.wait_for_timeout(3200)   # 페이지가 2.5초 뒤 스스로 다시 올린다
        old = await pg.evaluate("localStorage.getItem('p6_unsent')")
        check('옛 p6_unsent 는 큐로 옮겨져 올라가고 옛 칸은 비워진다', old is None and [x['t'] for x in POSTS] == [77] and await q(pg) == [], (old, POSTS))
        await ctx.close()
        POSTS.clear(); st = {'code': 'error'}
        ctx, pg, errs = await fresh(b, srv.port, st, pre="localStorage.setItem('p6_unsent',JSON.stringify({t:78,kills:3,lv:5,ch:'brj',won:false,hard:0,vhard:0,unlocks:[],ts:Date.now()}))")
        await pg.wait_for_timeout(3200)
        qq = await q(pg)
        check('이관된 판이 또 실패해도 큐에 한 칸으로 남는다', len(qq) == 1 and qq[0]['t'] == 78 and await pg.evaluate("localStorage.getItem('p6_unsent')") is None, qq)
        await ctx.close()
        # 5. 3일 지난 판 버림
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port, {}, pre="localStorage.setItem('p6_unsent_q',JSON.stringify([{t:50,ts:Date.now()-4*86400000,_q:'o'},{t:51,ts:Date.now(),_q:'n'}]))")
        await pg.wait_for_timeout(3200)
        check('3일 지난 판은 버리고 나머지만 올린다', [x['t'] for x in POSTS] == [51], POSTS); await ctx.close()
        # 6. 429(rate) · 로그인 만료(auth) 는 보관
        for code, label in (('rate', '429'), ('auth', '로그인 만료')):
            POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {'code': code})
            await run(pg, 40)
            txt = await pg.evaluate("document.getElementById('rAcct').textContent")
            relog = await pg.evaluate("!!document.getElementById('rRelog')")
            check('[%s] 판을 버리지 않고 보관 + 다시 저장 버튼' % label, len(await q(pg)) == 1 and '다시 저장' in txt, txt)
            check('[%s] 안내가 쉬운 말' % label, ('남겨 뒀어요' in txt), txt)
            check('[%s] 로그인 만료일 때만 로그인 버튼' % label, relog == (code == 'auth'), relog)
            await ctx.close()
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {'code': 'rate'})
        await run(pg, 10)
        check('[429] 30초도 안 된 연습 판은 예전처럼 버린다', await q(pg) == [], await q(pg)); await ctx.close()
        # 7. 네트워크 끊김
        POSTS.clear(); ctx, pg, errs = await fresh(b, srv.port, {'code': 'NET'}); await run(pg, 40)
        check('서버에 못 닿아도 보관', len(await q(pg)) == 1); await ctx.close()
        # 8. localStorage 불가 — 메모리로 버티고 오류 없음
        POSTS.clear(); st = {'codes': ['error']}
        ctx, pg, errs = await fresh(b, srv.port, st, blockls=True)
        await run(pg, 40)
        has = await pg.evaluate("!!document.getElementById('rRetry')")
        check('[저장소 막힘] 실패해도 오류 없이 다시 저장 버튼', has and errs == [], errs)
        await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(500)
        check('[저장소 막힘] 같은 탭 안에서는 다시 저장이 된다', len(POSTS) == 2 and POSTS[-1]['t'] == POSTS[0]['t'], [x['t'] for x in POSTS]); await ctx.close()
        # 9. 영구 거절 판이 앞에 있어도 뒤 판은 올라간다 · 보관 시각 유지
        POSTS.clear(); st = {'codes': ['bad_run', 'bad_run']}
        ctx, pg, errs = await fresh(b, srv.port, st); await run(pg, 39); await run(pg, 60)
        q0 = await q(pg); T1, T2 = q0[0]['t'], q0[1]['t']; ts0 = q0[0]['ts']; await pg.wait_for_timeout(50)
        st['codes'] = []; st['rejt'] = T1   # 첫 판만 언제나 거절, 뒤 판은 성공
        await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(900)
        qq = await q(pg)
        check('[영구 거절] 앞 판이 거절돼도 뒤 판(40)은 올라간다', T2 in [x['t'] for x in POSTS[2:]] and T1 != T2, [x['t'] for x in POSTS])
        check('[영구 거절] 거절된 판만 남는다', [x['t'] for x in qq] == [T1], [x['t'] for x in qq])
        check('[영구 거절] 실패한 재시도가 보관 시각을 새로 찍지 않는다', qq and qq[0]['ts'] == ts0, (ts0, qq and qq[0]['ts'])); await ctx.close()
        # 10. setItem 만 막힌 환경 — 메모리 보관이 쓰인다
        POSTS.clear(); st = {'codes': ['error']}
        ctx, pg, errs = await fresh(b, srv.port, st)
        await pg.evaluate("(()=>{const s=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).startsWith('p6_unsent'))throw new Error('quota');return s.apply(this,arguments)}})()")
        await run(pg, 39)
        await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(500)
        check('[setItem 만 막힘] 다시 저장이 재전송한다', len(POSTS) == 2 and POSTS[-1]['t'] == POSTS[0]['t'], [x['t'] for x in POSTS])
        check('[setItem 만 막힘] 성공하면 큐에서 빠진다', await pg.evaluate("__uq.qLoad().length") == 0); await ctx.close()
        # 3. [A-31] 공용 PC — 다른 계정으로 보관된 판은 지금 로그인한 계정의 토큰으로 올리지 않는다
        POSTS.clear(); st = {'code': 'error'}
        ctx, pg, errs = await fresh(b, srv.port, st)
        await run(pg, 40)
        qa = await q(pg)
        check('[A-31] 보관본에 올린 사람 표시(_u)가 붙는다 · 토큰은 없다', len(qa) == 1 and qa[0].get('_u') and 'token' not in json.dumps(qa), qa)
        me = qa[0]['_u']
        await pg.evaluate("(me)=>{const now=Date.now();__uq.qSave([{t:61,kills:5,lv:2,ts:now,_q:'qa',_u:'zzz_other'},{t:62,kills:6,lv:2,ts:now,_q:'qb'},{t:63,kills:7,lv:2,ts:now,_q:'qc',_u:me}])}", me)
        st['code'] = None; POSTS.clear()
        await pg.evaluate("document.getElementById('rAcct').innerHTML='x'"); await pg.evaluate("__uq.flushUnsent(true)"); await pg.wait_for_timeout(1500)
        sent = sorted(x['t'] for x in POSTS)
        check('[A-31] 다른 계정 판(t=61)은 올리지 않고, 표시 없는 옛 판(62)·내 판(63)만 올린다', sent == [62, 63] and 61 not in sent, sent)
        left = await q(pg)
        check('[A-31] 다른 계정 판은 큐에 그대로 남는다(그 계정으로 로그인하면 올라감)', [x['t'] for x in left] == [61], left)
        check('[A-31] 서버로 간 본문에 _u 가 없다', all('_u' not in x for x in POSTS))
        await ctx.close()
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('%d/%d' % (N[0] - len(FAILS), N[0])); sys.exit(1 if FAILS else 0)
asyncio.run(main())
