#!/usr/bin/env python3
"""「스콰드 생존게임」 계정 동기화 시험(Playwright) — 두 개의 브라우저 컨텍스트 = 두 기기.

  python3 tests/novel_sync_test.py

봇(/nv/me · /nv/save)은 같은 규칙(uid 는 토큰에서만 · rev/409 · 64KB · 허용 필드만)을 지킨 가짜 서버로 대신한다(진짜 봇 코드는 봇 저장소 tests/nv_save_test.py).
시험 모드가 아닌 운영 경로를 타려고 ?nvgate=1 을 붙이고, 디스코드 로그인 값(sgg_dc)은 init script 로 넣는다.
기기 A 에서 저장 → 기기 B 에서 불러오기 · 병합 · 충돌 선택 · 오프라인 재시도 · 원고 버전 변경 마이그레이션 · 계정 전환을 확인한다."""
import asyncio, subprocess, time, sys, os, json
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PORT = 8796
API = 'https://hth3thmujs.apps.bot-hosting.cloud'
FAILS = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(extra)[:300] if extra and not cond else ''))
    if not cond: FAILS.append(name)

KEYS = ('fmt', 'ts', 'last', 'lastTs', 'chap', 'slots', 'end', 'meta', 'read', 'set', 'setTs', 'clues')
class Bot:
    """봇 /nv/* 의 규칙만 흉내 낸 가짜 — 토큰 'tok-<uid>-…' → uid."""
    def __init__(s): s.saves = {}; s.down = False; s.log = []; s.conflict_once = None
    def uid(s, tok):
        return tok.split('-')[1] if tok.startswith('tok-') else None
    def handle(s, method, path, q, body):
        if s.down: return None
        tok = (body or {}).get('token') if method == 'POST' else (q.get('token') or [''])[0]
        uid = s.uid(tok or '')
        if not uid: return 401, {'ok': False, 'code': 'auth'}
        if path == '/nv/me': return 200, {'ok': True, 'member': True, 'name': 'tester' + uid, 'on': True, 'prog': {}}
        if path == '/nv/prog': return 200, {'ok': True}
        if path == '/nv/save' and method == 'GET':
            s.log.append(('GET', uid)); r = s.saves.get(uid)
            return 200, ({'ok': True, 'rev': r['rev'], 'ver': r['ver'], 'ts': r['ts'], 'data': r['data']} if r else {'ok': True, 'rev': 0, 'ver': '', 'ts': 0, 'data': None})
        if path == '/nv/save' and method == 'POST':
            data = body.get('data'); ver = str(body.get('ver') or '')
            if not isinstance(data, dict) or not ver: return 400, {'ok': False, 'code': 'bad'}
            data = {k: data[k] for k in KEYS if k in data}
            if len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()) > 64 * 1024: return 413, {'ok': False, 'code': 'big'}
            cur = s.saves.get(uid)
            if s.conflict_once and cur:    # 다른 기기가 막 올린 것처럼 rev 를 올려 둔다
                cur['rev'] += 1; s.conflict_once = None
            if cur and cur['rev'] != body.get('base'):
                return 409, {'ok': False, 'code': 'conflict', 'rev': cur['rev'], 'ver': cur['ver'], 'ts': cur['ts'], 'data': cur['data']}
            rev = (cur['rev'] if cur else 0) + 1
            s.saves[uid] = {'rev': rev, 'ver': ver, 'ts': int(time.time()), 'data': data}; s.log.append(('PUT', uid, rev))
            return 200, {'ok': True, 'rev': rev, 'ts': int(time.time())}
        return 404, {'ok': False}

CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'}
async def new_ctx(b, bot, uid='1001', store=None, nvgate=True, page_q='fast=1'):
    ctx = await b.new_context(viewport={'width': 400, 'height': 800}, storage_state=store)
    async def route(r):
        u = r.request.url
        if u.startswith(API):
            from urllib.parse import urlparse, parse_qs
            if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=CORS); return
            pu = urlparse(u); body = None
            if r.request.method == 'POST':
                try: body = json.loads(r.request.post_data or '{}')
                except Exception: body = {}
            res = bot.handle(r.request.method, pu.path.rstrip('/'), parse_qs(pu.query), body)
            if res is None: await r.abort(); return
            await r.fulfill(status=res[0], headers=CORS, content_type='application/json', body=json.dumps(res[1]))
            return
        if not u.startswith('http://localhost:%d/' % PORT): await r.abort(); return
        await r.continue_()
    await ctx.route('**/*', route)
    if uid:
        await ctx.add_init_script("""(()=>{try{const u=%s; if(!localStorage.getItem('sgg_dc')||JSON.parse(localStorage.getItem('sgg_dc')).id!==u.id)localStorage.setItem('sgg_dc',JSON.stringify(u))}catch(e){}})()"""
                                  % json.dumps({'id': uid, 'token': 'tok-%s-' % uid + 'x' * 20, 'exp': int(time.time() * 1000) + 86400000, 'name': 'u' + uid}))
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto('http://localhost:%d/novel.html?%s%s' % (PORT, page_q, '&nvgate=1' if nvgate else ''))
    await pg.wait_for_function("window.__novel&&!document.getElementById('tNew').hidden", timeout=20000)
    return ctx, pg, errs

async def wait_sync(pg, st='ok', t=8000):
    await pg.wait_for_function("(st)=>window.__novel.sy.st()===st&&window.__novel.sy.pulled()&&!window.__novel.sy.dirty()" if st == 'ok' else "(st)=>window.__novel.sy.st()===st", arg=st, timeout=t)
async def ready(pg):
    await pg.wait_for_function("__novel.sy.ready()&&!document.getElementById('tNew').disabled", timeout=20000)
async def badge(pg): return await pg.evaluate("document.getElementById('syBadge').textContent")
async def ls(pg, k): return await pg.evaluate("k=>JSON.parse(localStorage.getItem(k)||'null')", k)
async def goto_pc(pg, pc):
    await pg.evaluate("p=>{__novel.ST().pc=p;__novel.run()}", pc)
async def to_chapter(pg, n):
    """n 번째 장의 시작을 실제로 지나게 한다(onChap → 이어하기·장 기록 저장)."""
    await goto_pc(pg, await pg.evaluate("n=>__novel.STORY.chapters[n].pc", n)); await pg.wait_for_timeout(60)

async def main():
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=os.environ.get('CHROME') or '/opt/pw-browsers/chromium')
            bot = Bot()
            # ---------- 0) 시험 모드(운영 도메인 아님)는 서버를 부르지 않는다
            ctx0, pg0, e0 = await new_ctx(b, bot, nvgate=False); await pg0.wait_for_timeout(500)
            check('시험 모드: 서버 저장 호출 없음', not bot.log and await badge(pg0) == '', bot.log); await ctx0.close()

            # ---------- 1) 기기 A: 저장 → 서버에 올라간다
            ctxA, A, eA = await new_ctx(b, bot); await ready(A)
            check('A: 처음엔 서버가 비어 있어도 시작 가능(이어하기 없음)', await A.locator('#tCont').is_disabled() and not await A.locator('#tNew').is_disabled())
            await A.click('#tNew'); await A.wait_for_function("__novel.mode().ws==='line'", timeout=5000)
            await to_chapter(A, 2)
            m = await A.evaluate("__novel.mode()")
            await A.click('#bMenu'); await A.click('#mSave'); await A.locator('#slList .slot').nth(0).click()          # 슬롯 1 저장
            await A.click('#bMenu'); await A.click('#mSet'); await A.click('#sFs'); await A.click('#sFs'); await A.keyboard.press('Escape'); await A.keyboard.press('Escape')   # 글자 크기 보통→크게→아주 크게
            fsA = await A.evaluate("__novel.SET.fs")
            await wait_sync(A); u = bot.saves.get('1001')
            check('A: 서버에 세이브가 올라감(rev≥1)', u and u['rev'] >= 1, bot.log)
            check('A: 스토리 버전(ver)이 같이 올라감', u and u['ver'] == await A.evaluate("__novel.sy.SV"), u and u['ver'])
            d = u['data']
            check('A: 이어하기·장 기록·슬롯·설정이 들어 있음', d['last'] and d['last']['ch'] == 2 and '2' in d['chap'] and d['slots'][0] and d['set']['fs'] == fsA, {k: bool(d.get(k)) for k in KEYS})
            check('A: 허용 필드만(생년·닉네임 없음)', set(d) <= set(KEYS) and 'tester1001' not in json.dumps(d) and 'birth' not in json.dumps(d))
            check('A: 크기 64KB 이하', len(json.dumps(d, ensure_ascii=False).encode()) < 64 * 1024, len(json.dumps(d)))
            check('A: 배지 "☁ 동기화됨"', '동기화됨' in await badge(A), await badge(A))
            keyA = {'pc': d['last']['pc'], 'ch': d['last']['ch']}

            # ---------- 2) 기기 B(새 브라우저): 같은 계정으로 열면 같은 진행도
            ctxB, B, eB = await new_ctx(b, bot); await ready(B)
            check('B: 로컬이 비어 있었는데 서버본을 받아 이어하기가 켜짐', not await B.locator('#tCont').is_disabled())
            l = await ls(B, 'sq_novel2_last'); check('B: 이어하기 지점이 A 와 같음', l and l['pc'] == keyA['pc'] and l['ch'] == 2, l)
            check('B: 슬롯 1 이 채워짐', (await ls(B, 'sq_novel2_slots') or [None])[0] is not None)
            check('B: 설정(글자 크기)이 A 와 같음', await B.evaluate("__novel.SET.fs") == fsA and (await ls(B, 'sq_novel_set_v1'))['fs'] == fsA)
            check('B: 배지 "☁ 동기화됨"', '동기화됨' in await badge(B), await badge(B))
            await B.click('#tCont'); await B.wait_for_function("__novel.mode().ws!=='title'", timeout=5000)
            check('B: 이어하기를 누르면 같은 자리에서 시작', (await B.evaluate("__novel.ST().pc")) >= keyA['pc'] and (await B.evaluate("__novel.mode().ch")) == 2)

            # ---------- 3) B 가 엔딩을 보고 장을 더 진행 → A 가 다시 열면 합집합·최신
            ep = await B.evaluate("__novel.STORY.ops.findIndex(o=>o.o==='end')"); eid = await B.evaluate("p=>__novel.STORY.ops[p].id", ep)
            await to_chapter(B, 4); await goto_pc(B, ep); await B.wait_for_function("__novel.mode().ws==='end'", timeout=5000)
            await B.evaluate("__novel.goTitle()"); await wait_sync(B)
            check('B: 엔딩을 보면 이어하기는 지워진 채로 서버에 반영', 'last' in bot.saves['1001']['data'] and bot.saves['1001']['data']['last'] is None and eid in bot.saves['1001']['data']['end'], bot.saves['1001']['data'].get('last'))
            await A.reload(); await A.wait_for_function("window.__novel", timeout=20000); await ready(A)
            check('A 재접속: B 에서 본 엔딩이 도감에 합쳐짐', eid in (await ls(A, 'sq_novel2_end') or {}))
            check('A 재접속: 엔딩 뒤라 이어하기는 비활성(최신 쪽 = 삭제)', await A.locator('#tCont').is_disabled())
            check('A 재접속: 장 기록(장 선택) 합집합 — 4장까지 열림', '4' in (await ls(A, 'sq_novel2_chap') or {}) and '2' in (await ls(A, 'sq_novel2_chap')))
            check('A 재접속: 슬롯 1 은 그대로', (await ls(A, 'sq_novel2_slots') or [None])[0] is not None)

            # ---------- 4) 서버 실패/오프라인: 로컬 유지 → 복구되면 자동 재시도
            await A.click('#tNew'); await A.wait_for_function("__novel.mode().ws==='line'", timeout=5000); await to_chapter(A, 1); await wait_sync(A)
            bot.down = True
            await to_chapter(A, 3)
            await A.wait_for_function("__novel.sy.st()==='offline'", timeout=8000)
            check('오프라인: 배지 "오프라인"', '오프라인' in await badge(A), await badge(A))
            last = await ls(A, 'sq_novel2_last'); check('오프라인: 로컬 이어하기는 그대로 저장됨', last and last['ch'] == 3)
            check('오프라인: 서버는 옛 상태', bot.saves['1001']['data']['last'] is None or bot.saves['1001']['data']['last']['ch'] != 3)
            bot.down = False
            await A.wait_for_function("__novel.sy.st()==='ok'&&!__novel.sy.dirty()", timeout=8000)
            check('복구: 자동 재시도로 올라감 · 배지 "동기화됨"', bot.saves['1001']['data']['last']['ch'] == 3 and '동기화됨' in await badge(A))

            # ---------- 5) 동시성: 다른 기기가 먼저 올린 뒤(409) → 합쳐서 다시 올림
            bot.conflict_once = True; bot.saves['1001']['data']['end']['ZZ'] = {'t': 'x', 'ts': 5, 'play': 1}
            await to_chapter(A, 5); await wait_sync(A)
            sv = bot.saves['1001']['data']
            check('409: 서버에 있던 다른 기기의 엔딩을 잃지 않고 합쳐 올림', 'ZZ' in sv['end'] and eid in sv['end'] and sv['last']['ch'] == 5, [k for k in sv['end']])
            check('409: 로컬에도 합쳐짐', 'ZZ' in (await ls(A, 'sq_novel2_end')))
            check('A·B 콘솔 오류 없음', not eA and not eB, (eA + eB)[:3])
            await ctxA.close()

            # ---------- 6) 충돌 선택: 이 기기는 덜 진행·더 최근, 서버는 더 진행·덜 최근
            snapTpl = await B.evaluate("__novel.snap()")
            def mk(ch, pc, ts): s = dict(snapTpl); s.update(ch=ch, pc=pc, ts=ts, clues=[]); return s
            ch1pc = await B.evaluate("__novel.STORY.chapters[1].pc"); ch6pc = await B.evaluate("__novel.STORY.chapters[6].pc")
            bot2 = Bot(); now = int(time.time() * 1000)
            bot2.saves['2002'] = {'rev': 3, 'ver': snapTpl['sv'], 'ts': 1, 'data': {'fmt': 1, 'last': mk(6, ch6pc, now - 100000), 'lastTs': now - 100000, 'chap': {}, 'slots': [None, None, None], 'end': {}, 'meta': {'play': 900}, 'read': {'sv': snapTpl['sv'], 'r': [[0, 50]]}, 'set': {}, 'setTs': 0, 'clues': []}}
            await ctxB.close()
            ctxC, C, eC = await new_ctx(b, bot2, uid='2002', page_q='fast=1')
            # C 는 처음 열어서 로컬이 없다 → 충돌 없음. 로컬에 '더 최근·덜 진행' 기록을 심고 다시 연다.
            await C.evaluate("([s,t])=>{localStorage.setItem('sq_novel2_last',JSON.stringify(s));localStorage.setItem('sq_novel2_sync',JSON.stringify({uid:'2002',lastTs:t}))}", [mk(1, ch1pc, now), now])
            bot2.log.clear(); await C.reload(); await C.wait_for_function("window.__novel", timeout=20000); await ready(C)
            await C.wait_for_function("document.getElementById('ovSync').classList.contains('on')", timeout=5000)
            check('충돌: 선택 화면이 뜸(이 기기 vs 계정)', 'on' in (await C.evaluate("document.getElementById('ovSync').className")) and '계정' in await C.evaluate("document.getElementById('syRem').textContent"))
            check('충돌: 아무것도 안 고르면 최신(이 기기) 쪽', (await ls(C, 'sq_novel2_last'))['ch'] == 1)
            await C.click('#syRem'); await wait_sync(C)
            check('충돌: 계정 쪽을 고르면 로컬·서버 모두 그쪽', (await ls(C, 'sq_novel2_last'))['ch'] == 6 and bot2.saves['2002']['data']['last']['ch'] == 6)
            check('병합: 읽은 대사·누적 시간은 큰 쪽/합집합', bot2.saves['2002']['data']['meta']['play'] >= 900 and (await C.evaluate("__novel.READ.size")) >= 51)
            await ctxC.close()

            # ---------- 7) 원고 버전이 다르면 옛 이어하기는 버리고 도감·설정만 유지(마이그레이션)
            bot3 = Bot(); old = dict(snapTpl); old.update(sv='1:1', ch=3, pc=10, ts=now)
            bot3.saves['3003'] = {'rev': 2, 'ver': '1:1', 'ts': 1, 'data': {'fmt': 1, 'last': old, 'lastTs': now, 'chap': {'3': old}, 'slots': [old, None, None], 'end': {'old_end': {'t': '옛 엔딩', 'ts': 7, 'play': 3}},
                                                                            'meta': {'play': 1234}, 'read': {'sv': '1:1', 'r': [[0, 99]]}, 'set': {'fs': 3, 'speed': 2}, 'setTs': now, 'clues': ['no_such_clue']}}
            ctxD, D, eD = await new_ctx(b, bot3, uid='3003'); await ready(D)
            await wait_sync(D)
            check('마이그레이션: 옛 이어하기 버려짐(이어하기 비활성)', await D.locator('#tCont').is_disabled() and await ls(D, 'sq_novel2_last') is None)
            check('마이그레이션: 옛 슬롯·장 기록 버려짐', not any(await ls(D, 'sq_novel2_slots') or []) and not (await ls(D, 'sq_novel2_chap') or {}))
            check('마이그레이션: 엔딩 도감·설정·누적 시간은 유지', 'old_end' in (await ls(D, 'sq_novel2_end') or {}) and await D.evaluate("__novel.SET.fs") == 3 and (await ls(D, 'sq_novel2_meta'))['play'] >= 1234)
            check('마이그레이션: 서버본이 새 ver 로 갱신됨', bot3.saves['3003']['ver'] == snapTpl['sv'] and bot3.saves['3003']['data']['last'] is None and 'old_end' in bot3.saves['3003']['data']['end'])
            check('마이그레이션: 옛 읽은 대사·없는 단서 id 는 버려짐', bot3.saves['3003']['data']['read']['r'] == [] and bot3.saves['3003']['data']['clues'] == [], bot3.saves['3003']['data']['read'])
            # 변환기 훅: 등록하면 그것이 우선
            hook = await D.evaluate("""(()=>{const sv=__novel.sy.SV; __novel.sy.mig['9:9']=b=>Object.assign({},b,{last:null,lastTs:0,chap:{},slots:[null,null,null],end:Object.assign({},b.end,{hooked:{t:'h',ts:1,play:0}})}); return Object.keys(__novel.sy.migrate({end:{}},'9:9').end)})()""")
            check('마이그레이션 훅(SY_MIG)이 기본 규칙보다 먼저 적용됨', hook == ['hooked'], hook)
            await ctxD.close()

            # ---------- 8) 계정 전환: 같은 브라우저에 다른 계정이 로그인하면 섞지 않는다
            bot4 = Bot(); ctxE, E, eE = await new_ctx(b, bot4, uid='4004'); await ready(E)
            await E.click('#tNew'); await E.wait_for_function("__novel.mode().ws==='line'", timeout=5000); await to_chapter(E, 2); await E.evaluate("__novel.goTitle()"); await wait_sync(E)
            store = await ctxE.storage_state(); await ctxE.close()
            store['origins'][0]['localStorage'] = [x for x in store['origins'][0]['localStorage'] if x['name'] != 'sgg_dc']
            ctxF, F, eF = await new_ctx(b, bot4, uid='5005', store=store); await ready(F); await wait_sync(F)
            check('계정 전환: 다른 계정의 이어하기가 새 계정에 올라가지 않음', '5005' not in bot4.saves or bot4.saves['5005']['data'].get('last') is None, bot4.saves.get('5005'))
            check('계정 전환: 이전 계정 기록은 따로 보관됨', (await ls(F, 'sq_novel2_bak') or {}).get('uid') == '4004')
            check('계정 전환: 4004 의 서버 세이브는 그대로', bot4.saves['4004']['data']['last']['ch'] == 2)
            await ctxF.close()

            # ---------- 9) 인증이 거절되면 동기화를 끄고 플레이는 로컬로 계속
            await b.close()
    finally:
        sp.terminate()
    print('\n실패 %d건' % len(FAILS), FAILS); return 1 if FAILS else 0
if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
