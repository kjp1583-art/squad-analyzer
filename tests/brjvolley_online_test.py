#!/usr/bin/env python3
"""브장신 배구 온라인 시험 — 가짜 서버(tests/vb_fake_server.py, 명세 §6 JSON 만 구현)와 두 브라우저 컨텍스트를 붙여
실제 락스텝으로 한 판을 끝까지 돌린다: 양쪽 점수·상태 해시 일치, 입력 지연·패킷 손실, 어긋남·기권·타임아웃 안내,
로그인 전/후 화면, 전적·순위표, 친선방, 폰 폭 가로 스크롤 없음, 콘솔 오류 0.
사용: CHROME=... python3.13 tests/brjvolley_online_test.py
      REAL=http://127.0.0.1:8099 python3.13 tests/brjvolley_online_test.py real   ← 봇 쪽 _vb_* 라우트를 붙인 로컬 서버로 같은 시험(통합)"""
import asyncio, os, sys, json, random, time
from urllib.parse import urlparse
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_fake_server import Fake

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
URL = 'file://' + os.path.join(ROOT, 'brjvolley.html')
API = 'https://hth3thmujs.apps.bot-hosting.cloud'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'content-type', 'Access-Control-Allow-Methods': 'POST, OPTIONS'}
fails = []; errs_all = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {info}'))
    if not cond: fails.append(name)

BOT = '''
window.__mkbot=(seed)=>(f,side)=>{ const m=__vbnet.match; if(!m) return 0; const s=m.G.s, p=s.p[side], b=s.ball; let r=((f*2654435761+seed*97+side*40503)>>>0);
  const rnd=()=>{r=(Math.imul(r,1664525)+1013904223)>>>0;return r/4294967296;};
  let bits=0; const mine=side===0?b.x<216:b.x>216; const fw=side?-1:1;
  const tx=mine?b.x-fw*(14+((f>>6)%3)*8):(side?324:108);
  if(tx-p.x>5) bits|=2; else if(tx-p.x<-5) bits|=1;
  if(mine&&Math.abs(b.x-p.x)<50&&b.y<190&&b.y>50&&rnd()<.5) bits|=4;
  const near=Math.hypot(b.x-p.x,b.y-(p.y-24))<52;
  if(mine&&near&&rnd()<.6){ bits|=16; if(p.y<238){ bits|=8; bits|=(side?1:2);} }
  return bits; };
window.__idle=(f,side)=>((f%200<100)?2:1);   // 이리저리 돌아다니기만 하는 쪽(공을 안 쳐서 진다)
'''

class Net:
    """가짜 서버(또는 실제 로컬 서버)를 두 컨텍스트에 연결하고 지연·손실·단절을 주입한다."""
    def __init__(self, fake=None, real=None):
        self.fake = fake; self.real = real; self.ctl = {}; self.rng = random.Random(11); self.beacons = []
    def c(self, token):
        return self.ctl.setdefault(token, dict(lo=0.0, hi=0.0, pb=0.0, pa=0.0, down=False))
    async def handler(self, route, request):
        if request.method == 'OPTIONS':
            await route.fulfill(status=204, headers=CORS); return
        path = urlparse(request.url).path
        try: body = json.loads(request.post_data or '{}')
        except Exception: body = {}
        c = self.c(body.get('token'))
        if path.endswith('/leave') and 'beacon' in (request.headers.get('x-test') or ''): pass
        if c['down']: await route.abort('failed'); return
        if self.rng.random() < c['pb']: await route.abort('failed'); return
        d = self.rng.uniform(c['lo'], c['hi'])
        if d: await asyncio.sleep(d)
        if self.real:
            import urllib.request
            def go():
                rq = urllib.request.Request(self.real + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                try: return json.loads(urllib.request.urlopen(rq, timeout=8).read())
                except Exception as e:
                    try: return json.loads(e.read())
                    except Exception: return {'ok': False, 'code': 'http'}
            resp = await asyncio.get_event_loop().run_in_executor(None, go)
        else:
            resp = self.fake.handle(path, body)
        if self.rng.random() < c['pa']: await route.abort('failed'); return    # 서버는 처리했는데 응답이 사라짐
        await route.fulfill(status=200, headers=dict(CORS, **{'Content-Type': 'application/json'}), body=json.dumps(resp))

async def mkctx(br, net, token, uid, name, viewport=None, login=True):
    kw = dict(viewport=viewport or {'width': 1000, 'height': 760})
    if viewport and viewport['width'] < 600: kw.update(has_touch=True, is_mobile=True)
    ctx = await br.new_context(**kw)
    await ctx.route(API + '/**', net.handler)
    if login:
        await ctx.add_init_script(f"if(!localStorage.getItem('sgg_dc')) localStorage.setItem('sgg_dc', JSON.stringify({{id:'{uid}',name:'{name}',avatar:'',token:'{token}',exp:Date.now()+1e9}}));")
    await ctx.add_init_script(BOT)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror ' + str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text and 'ERR_FAILED' not in m.text and 'Failed to load resource' not in m.text else None)
    errs_all.append(errs)
    await pg.goto(URL); await pg.wait_for_timeout(300)
    return ctx, pg, errs

async def open_online(pg):
    if await pg.is_visible('#onl'): return
    await pg.click('#goOnline'); await pg.wait_for_selector('#onl .me-card, #onl .oc h3', timeout=5000)

async def wait_for(pg, js, timeout=60000, every=200):
    t = time.time()
    while (time.time() - t) * 1000 < timeout:
        try:
            if await pg.evaluate(js): return True
        except Exception: pass
        await pg.wait_for_timeout(every)
    return False

async def start_ranked(a, b):
    await open_online(a); await open_online(b)
    await a.click('[data-on=rank]'); await b.click('[data-on=rank]')
    ok = await asyncio.gather(*[wait_for(p, "__vbnet.match!==null", 20000) for p in (a, b)])
    return all(ok)

async def set_bots(a, b, ka='bot', kb='bot'):
    for pg, k, sd in ((a, ka, 1), (b, kb, 2)):
        await pg.evaluate("(__vbnet.inject=" + ("window.__idle" if k == 'idle' else f"window.__mkbot({sd})") + ", 0)")

async def wait_end(pgs, timeout=150000):
    return await asyncio.gather(*[wait_for(p, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", timeout) for p in pgs])

async def snap(pg):
    return await pg.evaluate("(()=>{const m=__vbnet.match; if(!m) return null; return {score:m.G.s.score.slice(), t:m.G.s.t, phase:m.G.s.phase, winner:m.G.s.winner, hashes:m.hashes.slice(), stalls:m.status.stallCount, reqs:m.reqCount, rtt:m.status.rtt}})()")

def same_hashes(a, b):
    n = min(len(a['hashes']), len(b['hashes']))
    return n > 0 and a['hashes'][:n] == b['hashes'][:n], n

async def main():
    real = os.environ.get('REAL') if 'real' in sys.argv else None
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=['--allow-file-access-from-files', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'])

        def mk(rA=1040, rB=1055):
            f = Fake(target=5); f.add_user('tokA', 'A', '알파', rA); f.add_user('tokB', 'B', '베타', rB); n = Net(f, real); return f, n

        # ===== 0. 엔진 결정론 (브라우저 안에서 두 번 돌려 해시가 같고, 입력이 다르면 달라진다) =====
        f, n = mk(); ctx, pg, errs = await mkctx(br, n, 'tokA', 'A', '알파')
        r = await pg.evaluate('''(()=>{ const BV=window.BrjVolley; const run=(seed,bump)=>{ const g=BV.create({seed,target:15}); g.reset(); let r=seed*31+7; const rnd=()=>{r=(Math.imul(r,1103515245)+12345)&0x7fffffff;return r/0x7fffffff;}; const hs=[];
          for(let i=0;i<6000;i++){ const a={l:rnd()<.4,r:rnd()<.4,u:rnd()<.12,d:rnd()<.3,hit:rnd()<.2}, b={l:rnd()<.4,r:rnd()<.4,u:rnd()<.12,d:rnd()<.3,hit:rnd()<.2}; if(bump&&i===3000) a.l=!a.l; g.step(a,b); if(i%60===59) hs.push(g.hash()); } return hs; };
          const A=run(5,false), B=run(5,false), C=run(5,true); return {same:JSON.stringify(A)===JSON.stringify(B), diff:JSON.stringify(A)!==JSON.stringify(C), n:A.length}; })()''')
        check('엔진: 같은 시드·같은 입력이면 상태 해시가 매 60프레임 같고, 입력이 한 번 달라지면 달라진다', r['same'] and r['diff'], r)
        src = open(os.path.join(ROOT, 'brjvolley.js'), encoding='utf-8').read()
        import re
        sim = src[:src.index('// ---------- CPU ----------')]
        sim = re.sub(r'/\*.*?\*/', '', sim, flags=re.S); sim = re.sub(r'//[^\n]*', '', sim)
        bad = [m for m in re.findall(r'Math\.(?:sin|cos|tan|atan2?|asin|acos|exp|log|pow|random|hypot)|Date\.|performance\.|setTimeout|requestAnimationFrame', sim)]
        check('엔진: 시뮬레이션 코드에 삼각함수·Math.random·Date 가 없다(CPU AI 구역 제외)', not bad, bad)
        await ctx.close()

        # ===== 1. 로그인 전 / 서버 꺼짐 / 로그인 후 화면 =====
        f, n = mk()
        ctx, pg, errs = await mkctx(br, n, 'tokA', 'A', '알파', login=False)
        await open_online(pg); t = await pg.inner_text('#onl')
        check('로그인 전: 온라인 메뉴가 디스코드 로그인 버튼을 보여 준다', '로그인' in t and await pg.is_visible('[data-on=login]') and 'CPU' in t, t[:120])
        await ctx.close()
        f, n = mk(); n.c('tokA')['down'] = True
        ctx, pg, errs = await mkctx(br, n, 'tokA', 'A', '알파'); await open_online(pg); await pg.wait_for_timeout(4800)
        t = await pg.inner_text('#onl'); check('서버가 꺼졌으면 안내 문구만 보이고 1·2인 대전은 그대로', '쓸 수 없어요' in t and not await pg.is_visible('[data-on=rank]'), t[:150])
        await pg.click('[data-on=close]'); await pg.wait_for_timeout(200)
        check('안내 뒤 ← 메뉴 로 돌아오면 기존 메뉴 정상', await pg.is_visible('#ovMenu') and await pg.is_visible('[data-level=normal]'))
        await pg.click('[data-level=normal]'); await pg.wait_for_timeout(500); check('서버가 꺼져도 CPU 대전은 정상 시작', await pg.evaluate("__vb.mode==='play'"))
        await ctx.close()
        f, n = mk(1040)
        ctx, pg, errs = await mkctx(br, n, 'tokA', 'A', '알파'); await open_online(pg); await pg.wait_for_timeout(400)
        t = await pg.inner_text('#onl')
        check('로그인 후: 내 카드(이름·레이팅·티어 배지·전적)와 접속/대기 인원', '알파' in t and '1,040' in t and '아기새' in t and '접속 중' in t and await pg.is_visible('[data-on=rank]'), t[:200])
        await ctx.close()

        # ===== 2. 랭크 한 판 (깨끗한 망) · 승급/강등 연출 =====
        f, n = mk(1040, 1055)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        ok = await start_ranked(A, B)
        check('랭크 찾기 → 두 사람이 매칭돼 방에 들어간다', ok)
        await set_bots(A, B, 'bot', 'idle')
        await A.wait_for_timeout(300)
        names = (await A.inner_text('#n0'), await A.inner_text('#n1'), await B.inner_text('#n0'), await B.inner_text('#n1'))
        check('화면 위에 두 사람 이름·티어, 내 쪽 표시', '알파' in names[0] and '나' in names[0] and '베타' in names[1] and '알파' in names[2] and '베타' in names[3] and '나' in names[3], names)
        cd = await wait_for(A, "__vbnet.cd.phase==='count'", 8000); check('3·2·1 카운트가 돈다', cd)
        t0 = time.time(); res = await wait_end([A, B]); dt = time.time() - t0
        check('한 판이 끝까지 간다(양쪽 결과 창)', all(res), res)
        sA, sB = await snap(A), await snap(B)
        sh, nh = same_hashes(sA, sB)
        check(f'양쪽 최종 점수·프레임 수·승자가 같다 ({sA["score"]} {sA["t"]}프레임, {dt:.0f}초)', sA['score'] == sB['score'] and sA['t'] == sB['t'] and sA['winner'] == sB['winner'] and sA['phase'] == 'over', (sA, sB))
        check(f'60프레임마다의 상태 해시 {nh}개가 두 브라우저에서 모두 일치', sh and nh >= 3, (nh,))
        tA, tB = await A.inner_text('#ovOn'), await B.inner_text('#ovOn')
        aw = sA['winner'] == 0
        check('결과 창: 승자 문구·점수·레이팅 +16/−16', ('승리' in (tA if aw else tB)) and ('패배' in (tB if aw else tA)) and '+16' in (tA if aw else tB) and '-16' in (tB if aw else tA), (tA, tB))
        check('서버 기록 반영: 레이팅 ±16, 승패 1', f.rec['A']['rating'] == (1056 if aw else 1024) and f.rec['B']['rating'] == (1039 if aw else 1071) and f.rec['A']['w' if aw else 'l'] == 1)
        if aw: check('티어 변화 연출: 알파 승급(아기새→병아리), 베타 강등', '승급' in tA and '병아리' in tA and '강등' in tB and '아기새' in tB, (tA, tB))
        else: check('티어 변화 문구 없음(같은 티어 유지)', '승급' not in tB and '강등' not in tA, (tA, tB))
        check('결과 창에 「한 판 더(재매칭)」 버튼', await A.is_visible('#onAgain') and await B.is_visible('#onAgain'))
        # 전적·순위표 탭
        await A.click('#onMenu'); await A.wait_for_selector('[data-tab=rec]'); await A.click('[data-tab=rec]'); await A.wait_for_selector('#onl .tbl', timeout=4000)
        t = await A.inner_text('#onl'); check('전적 탭: 최근 판(상대 이름·점수·결과·레이팅 변화)과 상대별 전적', '베타' in t and ('승' in t) and ('상대별 전적' in t) and ('+16' in t or '-16' in t), t[:300])
        await A.click('[data-tab=rank]'); await A.wait_for_selector('#onl .tbl', timeout=4000); t = await A.inner_text('#onl')
        check('순위표 탭: 배치를 끝낸 사람이 레이팅 순으로 (티어 배지 포함)', t.index('알파') != t.index('베타') and ('병아리' in t or '아기새' in t or '🐥' in t or '🐣' in t) and '레이팅' in t, t[:300])
        check('콘솔·페이지 오류 없음(1~2)', not any(eA) and not any(eB), (eA, eB))
        await ctxA.close(); await ctxB.close()

        # ===== 3. 입력 지연·패킷 손실·응답 손실 주입 =====
        f, n = mk(1100, 1100)
        for tk, (lo, hi) in (('tokA', (0.03, 0.14)), ('tokB', (0.05, 0.20))):
            c = n.c(tk); c.update(lo=lo, hi=hi, pb=0.10, pa=0.06)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        ok = await start_ranked(A, B); await set_bots(A, B, 'bot', 'bot')
        check('(손실 망) 매칭 성립', ok)
        res = await wait_end([A, B], 240000); check('(손실 망) 지연 30~200ms · 요청 10% 유실 · 응답 6% 유실에서도 한 판이 끝난다', all(res), res)
        sA, sB = await snap(A), await snap(B); sh, nh = same_hashes(sA, sB)
        check(f'(손실 망) 점수·프레임·해시 {nh}개 일치 · 멈춤(연결 대기) {sA["stalls"]}/{sB["stalls"]}회', sA['score'] == sB['score'] and sA['t'] == sB['t'] and sh, (sA['score'], sB['score'], sA['t'], sB['t']))
        check('(손실 망) 서버 기록도 한 번만 반영(레이팅 합 보존)', f.rec['A']['rating'] + f.rec['B']['rating'] == 2200 and f.rec['A']['matches'] == 1 and f.rec['B']['matches'] == 1, (f.rec['A']['rating'], f.rec['B']['rating']))
        check('(손실 망) 지연이 상태 표시줄에 나왔다', sA['rtt'] > 20, sA['rtt'])
        await ctxA.close(); await ctxB.close()

        # ===== 4. 어긋남(desync) =====
        f, n = mk(1100, 1100)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        ok = await start_ranked(A, B); await set_bots(A, B)
        await wait_for(A, "__vbnet.match.G.s.t>200", 20000); await A.evaluate('__vbnet.sabotage()')
        res = await wait_end([A, B], 30000); tA, tB = await A.inner_text('#ovOn'), await B.inner_text('#ovOn')
        check('해시가 어긋나면 판이 무효 → 양쪽에 안내, 기록 반영 없음', all(res) and '어긋나' in tA and '어긋나' in tB and f.rec['A']['matches'] == 0 and f.rec['A']['rating'] == 1100, (tA, tB))
        await ctxA.close(); await ctxB.close()

        # ===== 5. 기권승 요청(8초) · 자동 기권(20초) · 재연결 불가 안내 =====
        f, n = mk(1100, 1100)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        ok = await start_ranked(A, B); await set_bots(A, B)
        await wait_for(A, "__vbnet.match.G.s.t>150", 20000)
        await B.evaluate("BrjVolleyNet.NET.GIVEUP_AFTER=3000")
        n.c('tokB')['down'] = True                                    # 베타의 네트워크가 끊긴다
        stalled = await wait_for(A, "__vbnet.status.stalled>600", 8000); check('상대 입력이 끊기면 그 프레임에서 멈추고 「연결 대기…」가 보인다', stalled and '대기' in await A.inner_text('#nbState'), await A.inner_text('#nbState'))
        t1 = await A.evaluate('__vbnet.match.G.s.t'); await A.wait_for_timeout(500); t2 = await A.evaluate('__vbnet.match.G.s.t'); check('멈춘 동안 프레임이 늘지 않는다', t1 == t2, (t1, t2))
        check('8초가 되기 전에는 기권승 요청 버튼이 없다', not await A.is_visible('#nbClaim'))
        await wait_for(A, "__vbnet.status.canClaim", 12000); f.skew += 9.0       # 클라이언트는 실제 8초를 기다리고, 서버 시계도 9초 앞으로
        check('상대가 오래 멈추면 「기권승 요청」 버튼이 나온다', await A.is_visible('#nbClaim'))
        await A.click('#nbClaim'); res = await wait_for(A, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 8000)
        tA = await A.inner_text('#ovOn'); check('기권승 요청 → 서버가 기권승 확정 → 「기권승」 + 레이팅 반영', res and '기권승' in tA and f.rec['A']['rating'] == 1116 and f.rec['B']['rating'] == 1084, (tA, f.rec['A']['rating']))
        # 끊겼던 베타: 20초 이상 못 닿으면 포기 안내(시험용으로 3초로 낮춤)
        res = await wait_for(B, "document.getElementById('ovOn').classList.contains('show')", 12000); tB = await B.inner_text('#ovOn')
        check('연결이 끊긴 쪽: 오래 못 닿으면 「연결이 끊겼어요… 이어서 할 수 없어요」 안내', res and '연결이 끊겼' in tB and '이어서 할 수는 없어요' in tB, tB)
        await ctxA.close(); await ctxB.close()

        # 자동 기권패(20초): 서버가 알아서 확정 → 돌아온 쪽은 「기권패」
        f, n = mk(1100, 1100)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        ok = await start_ranked(A, B); await set_bots(A, B); await wait_for(A, "__vbnet.match.G.s.t>150", 20000)
        n.c('tokB')['down'] = True; await A.wait_for_timeout(700); f.skew += 21.0; await A.wait_for_timeout(900)   # A 가 한 번 더 부르면 서버가 B 의 20초 침묵을 본다
        res = await wait_for(A, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 8000); tA = await A.inner_text('#ovOn')
        n.c('tokB')['down'] = False
        check('20초 침묵 → 서버가 자동 기권패 확정, 남은 쪽은 기권승', res and '기권승' in tA, tA)
        res = await wait_for(B, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 10000); tB = await B.inner_text('#ovOn')
        check('돌아온 쪽은 「기권패」를 본다(이어 할 수 없다는 안내 포함)', res and '기권패' in tB, tB)
        await ctxA.close(); await ctxB.close()

        # ===== 6. 나가기(기권) · 창 닫기 beacon =====
        f, n = mk(1100, 1100)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        ok = await start_ranked(A, B); await set_bots(A, B); await wait_for(A, "__vbnet.match.G.s.t>120", 20000)
        await B.evaluate("window.__bc=[]; navigator.sendBeacon=(u,d)=>{window.__bc.push(u); return true;}; 0")
        await B.evaluate("window.dispatchEvent(new Event('pagehide'))"); bc = await B.evaluate('window.__bc')
        check('창을 닫을 때(pagehide) /vb/leave 를 beacon 으로 보낸다', any(u.endswith('/vb/leave') for u in bc), bc)
        await B.click('#menuBtn'); await B.wait_for_timeout(200)
        check('경기 중 ☰ 는 「정말 나갈까요? 기권패」 확인 창', await B.is_visible('#ovWait') and '기권' in await B.inner_text('#ovWait'))
        await B.click('#waitBack'); await B.wait_for_timeout(200); check('「돌아가기」를 누르면 계속', not await B.is_visible('#ovWait') and await B.evaluate('__vbnet.match!==null'))
        await B.click('#menuBtn'); await B.click('#waitCancel'); await B.wait_for_timeout(600)
        res = await wait_for(A, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 8000); tA = await A.inner_text('#ovOn')
        check('나가면 상대에게 기권승, 나간 쪽 레이팅은 내려간다', res and '기권승' in tA and f.rec['B']['rating'] == 1084 and await B.is_visible('#onl'), (tA, f.rec['B']['rating']))
        await ctxA.close(); await ctxB.close()

        # ===== 7. 친선방 =====
        f, n = mk(1100, 1100)
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        await open_online(A); await open_online(B)
        await A.click('[data-on=create]'); await A.wait_for_selector('#waitCode:not([hidden])', timeout=5000); code = (await A.inner_text('#waitCode')).strip()
        check('친선방 만들기 → 4글자 코드가 보인다', len(code) == 4 and code.isalpha(), code)
        await B.fill('#codeIn', code.lower()); v = await B.input_value('#codeIn'); check('코드 입력은 대문자로 정리된다', v == code, v)
        await B.click('[data-on=join]')
        ok = await asyncio.gather(*[wait_for(p, "__vbnet.cd.phase==='count'||__vbnet.cd.phase==='run'", 15000) for p in (A, B)])
        check('코드로 입장하면 두 쪽이 시작한다(대기창 닫힘)', all(ok) and not await A.is_visible('#ovWait'))
        names = (await A.inner_text('#n1'), await B.inner_text('#n0'))
        check('친선: 상대 이름이 서로 보인다', '베타' in names[0] and '알파' in names[1], names)
        await set_bots(A, B, 'bot', 'idle'); res = await wait_end([A, B], 120000); tA, tB = await A.inner_text('#ovOn'), await B.inner_text('#ovOn')
        check('친선 결과: 레이팅 변화 없음 안내, 서버 레이팅 그대로, 「한 판 더」는 없음', all(res) and '친선' in tA and '친선' in tB and f.rec['A']['rating'] == 1100 and not await A.is_visible('#onAgain'), (tA, tB))
        sA, sB = await snap(A), await snap(B); sh, nh = same_hashes(sA, sB); check('친선 한 판도 해시 일치', sh and sA['score'] == sB['score'], (sA['score'], sB['score']))
        await A.click('#onMenu'); await A.click('[data-tab=rec]'); await A.wait_for_selector('#onl .tbl'); t = await A.inner_text('#onl'); check('전적에 친선 표시', '친선' in t, t[:200])
        await B.click('#onMenu'); await B.fill('#codeIn', 'ZZZZ'); await B.click('[data-on=join]'); await B.wait_for_timeout(600)
        check('없는 코드는 안내 문구', '찾을 수 없어요' in await B.inner_text('#onl'))
        await ctxA.close(); await ctxB.close()

        # ===== 8. 배치 중 표시 · 재매칭 =====
        f, n = mk(1000, 1000); f.rec['A']['placed'] = 0; f.rec['B']['placed'] = 0
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파'); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타')
        await open_online(A); t = await A.inner_text('#onl'); check('배치 전: 내 카드에 「배치 중 (0/5)」', '배치 중 (0/5)' in t, t[:120])
        ok = await start_ranked(A, B); await set_bots(A, B, 'bot', 'idle'); res = await wait_end([A, B], 120000)
        tA = await A.inner_text('#ovOn'); check('배치 판 결과: 「배치 중 (1/5)」 안내', all(res) and '배치 중' in tA and '1/5' in tA, tA)
        await A.click('#onAgain'); await A.wait_for_timeout(500); check('「한 판 더」→ 바로 다시 상대 찾기 상태', 'queue' in ''.join(x[1] for x in f.log if x[0] == 'A') and (await A.evaluate('__vbnet.on.searching')))
        await ctxA.close(); await ctxB.close()

        # ===== 9. 폰 폭: 가로 스크롤 없음 · 결과 창이 상자 안 · 콘솔 오류 0 =====
        f, n = mk(1040, 1055)
        vp = {'width': 390, 'height': 780}
        ctxA, A, eA = await mkctx(br, n, 'tokA', 'A', '알파', viewport=vp); ctxB, B, eB = await mkctx(br, n, 'tokB', 'B', '베타', viewport=vp)
        await open_online(A); await A.wait_for_timeout(300)
        no_h = lambda pg: pg.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1 && document.getElementById("onl").scrollWidth<=document.getElementById("onl").clientWidth+1')
        check('폰: 온라인 메뉴 가로 스크롤 없음', await no_h(A))
        for tab in ('rec', 'rank'):
            await A.click(f'[data-tab={tab}]'); await A.wait_for_timeout(400)
            check(f'폰: {tab} 탭 가로 스크롤 없음', await no_h(A))
        await A.click('[data-tab=play]')
        ok = await start_ranked(A, B); await set_bots(A, B, 'bot', 'idle'); await wait_for(A, "__vbnet.cd.phase==='run'", 15000)
        check('폰: 경기 화면 가로 스크롤 없음 · 터치 버튼 보임', await A.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1') and await A.is_visible('#bh'))
        check('폰: 점수판(이름+배지+점수)이 화면 폭 안', await A.evaluate("(()=>{const r=document.getElementById('scoreBar').getBoundingClientRect(); return r.left>=0&&r.right<=innerWidth+1 && document.getElementById('scoreBar').scrollWidth<=document.getElementById('scoreBar').clientWidth+1})()"))
        res = await wait_end([A, B], 120000)
        geo = await A.evaluate("(()=>{const b=document.getElementById('box').getBoundingClientRect(), x=document.getElementById('onBody').getBoundingClientRect(), y=document.getElementById('onBtns').getBoundingClientRect(); return {bt:b.top,bb:b.bottom,xt:x.top,yb:y.bottom,hw:document.documentElement.scrollWidth<=innerWidth+1}})()")
        check('폰: 결과 창(제목·점수·레이팅·티어·버튼)이 경기 상자 안에 들어간다', all(res) and geo['xt'] >= geo['bt'] - 1 and geo['yb'] <= geo['bb'] + 1 and geo['hw'], geo)
        check('콘솔·페이지 오류 없음(전체)', not any(any(e) for e in errs_all), [e for e in errs_all if e][:3])
        await ctxA.close(); await ctxB.close()
        await br.close()
    print('\n전부 통과' if not fails else f'\n실패 {len(fails)}건: ' + ', '.join(fails)); sys.exit(1 if fails else 0)
if __name__ == "__main__":
    asyncio.run(main())
