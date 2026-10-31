#!/usr/bin/env python3
"""통합 시험 — 봇 쪽 실제 /vb/* 라우트(bot.py 의 BRVB:ONLINE 구역)를 그대로 붙인 로컬 서버(vb_local_server.py)와 웹 두 브라우저를 붙여 본다.
사용: VB_SERVER=<vb_local_server.py 경로> VB_BOT=<bot.py 경로> CHROME=... python3.13 tests/brjvolley_online_real_test.py [포트]
(서버는 이 스크립트가 /usr/bin/python3 로 띄우고 끝나면 내린다. 디스코드·봇 없이 토큰 `dev:<uid>:<이름>`.)"""
import asyncio, os, sys, json, time, subprocess, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brjvolley_online_test as T
from playwright.async_api import async_playwright

SERVER = os.environ.get('VB_SERVER', '/tmp/claude-0/-home-user/b757afb2-56c9-521e-b304-0eb87dddca0b/scratchpad/bj3/vb_local_server.py')
BOT = os.environ.get('VB_BOT', '/tmp/claude-0/-home-user/b757afb2-56c9-521e-b304-0eb87dddca0b/scratchpad/wt3/vbsrv/bot.py')
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
BASE = f'http://127.0.0.1:{PORT}'
TA, TB = 'dev:1:알파', 'dev:2:베타'

def post(path, body=None):
    rq = urllib.request.Request(BASE + path, data=json.dumps(body or {}).encode(), headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(rq, timeout=8).read())
def state():
    return json.loads(urllib.request.urlopen(BASE + '/__vb/state', timeout=8).read())
def reset(ra=1040, rb=1055, placed=10):
    post('/__vb/reset'); post('/__vb/seed', dict(uid='1', name='알파', rating=ra, placed=placed)); post('/__vb/seed', dict(uid='2', name='베타', rating=rb, placed=placed))
check = T.check

async def pair(br, net):
    ca, A, ea = await T.mkctx(br, net, TA, '1', '알파'); cb, B, eb = await T.mkctx(br, net, TB, '2', '베타')
    return (ca, cb), A, B

async def main():
    srv = subprocess.Popen(['/usr/bin/python3', SERVER, '--bot', BOT, '--port', str(PORT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try: state(); break
            except Exception: time.sleep(0.2)
        async with async_playwright() as p:
            br = await p.chromium.launch(executable_path=T.CHROME, args=['--allow-file-access-from-files', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'])
            net = T.Net(None, BASE)
            # ---- 1. 랭크 한 판(15점) : 알파(봇) 대 베타(떠돌이) ----
            reset(); cs, A, B = await pair(br, net)
            check('실서버: 온라인 메뉴가 열리고 내 카드(1,040)·접속 인원이 보인다', (await T.open_online(A) or True) and '1,040' in await A.inner_text('#onl') and '접속 중' in await A.inner_text('#onl'), await A.inner_text('#onl'))
            await T.open_online(B)
            await A.click('[data-on=rank]'); await B.click('[data-on=rank]')
            ok = await asyncio.gather(*[T.wait_for(p_, "__vbnet.match!==null", 20000) for p_ in (A, B)]); check('실서버: 랭크 매칭 성립', all(ok))
            await T.set_bots(A, B, 'bot', 'idle')
            check('실서버: 서버가 알려 준 시작까지 남은 시간으로 카운트다운', await T.wait_for(A, "__vbnet.cd.phase==='count'", 8000))
            res = await T.wait_end([A, B], 360000); check('실서버: 15점 한 판이 끝까지 간다', all(res), res)
            sA, sB = await T.snap(A), await T.snap(B); sh, nh = T.same_hashes(sA, sB)
            check(f'실서버: 양쪽 점수·프레임 일치 ({sA["score"]}, {sA["t"]}프레임) · 해시 {nh}개 일치', sA['score'] == sB['score'] and sA['t'] == sB['t'] and sh, (sA['score'], sB['score']))
            tA, tB = await A.inner_text('#ovOn'), await B.inner_text('#ovOn'); aw = sA['winner'] == 0
            rec = state()['records']
            check('실서버: 결과 창 승/패·레이팅 변화가 서버 기록과 같다', ('승리' in tA) == aw and rec['1']['rating'] != 1040 and ('%+d' % (rec['1']['rating'] - 1040)) in tA, (tA, rec['1']['rating']))
            pr = rec['1']['last_result']['promoted']; check(f'실서버: 승급/강등 문구가 서버 판정(promoted={pr})과 맞는다', ('승급' in tA) == (pr > 0) and ('강등' in tA) == (pr < 0), tA)
            await A.click('#onMenu'); await A.click('[data-tab=rec]'); await A.wait_for_selector('#onl .tbl', timeout=5000); t = await A.inner_text('#onl')
            check('실서버: 전적 탭(상대·점수·결과)과 상대별 전적', '베타' in t and '상대별 전적' in t, t[:200])
            await A.click('[data-tab=rank]'); await A.wait_for_selector('#onl .tbl', timeout=5000); t = await A.inner_text('#onl'); check('실서버: 순위표 탭에 두 사람', '알파' in t and '베타' in t, t[:200])
            for c in cs: await c.close()
            # ---- 2. 지연·손실 ----
            reset(1100, 1100); net2 = T.Net(None, BASE)
            for tk, (lo, hi) in ((TA, (0.03, 0.12)), (TB, (0.05, 0.18))): net2.c(tk).update(lo=lo, hi=hi, pb=0.08, pa=0.05)
            cs, A, B = await pair_net(br, net2)
            await T.open_online(A); await T.open_online(B); await A.click('[data-on=rank]'); await B.click('[data-on=rank]')
            await asyncio.gather(*[T.wait_for(p_, "__vbnet.match!==null", 20000) for p_ in (A, B)]); await T.set_bots(A, B, 'bot', 'bot')
            res = await T.wait_end([A, B], 420000); sA, sB = await T.snap(A), await T.snap(B); sh, nh = T.same_hashes(sA, sB)
            check(f'실서버+손실 망(지연 30~180ms · 요청 8% / 응답 5% 유실): 한 판 완주 · 점수·해시 {nh}개 일치 · 멈춤 {sA["stalls"]}회', all(res) and sA['score'] == sB['score'] and sh, (res, sA['score'], sB['score']))
            rec = state()['records']; check('실서버+손실 망: 기록은 한 번만 반영(레이팅 합 보존)', rec['1']['rating'] + rec['2']['rating'] == 2200 and rec['1']['matches'] == 1, rec['1'])
            for c in cs: await c.close()
            # ---- 3. 상대 단절 → 기권승 요청 ----
            reset(1100, 1100); net3 = T.Net(None, BASE); cs, A, B = await pair_net(br, net3)
            await T.open_online(A); await T.open_online(B); await A.click('[data-on=rank]'); await B.click('[data-on=rank]')
            await asyncio.gather(*[T.wait_for(p_, "__vbnet.match!==null", 20000) for p_ in (A, B)]); await T.set_bots(A, B, 'bot', 'bot')
            await T.wait_for(A, "__vbnet.match.G.s.t>400", 40000)       # 판정 무효 기준(5초=300프레임)을 넘긴 뒤
            net3.c(TB)['down'] = True
            check('실서버: 상대 입력이 끊기면 「연결 대기」', await T.wait_for(A, "__vbnet.status.stalled>600", 8000))
            check('실서버: 8초 뒤 「기권승 요청」 버튼이 나온다', await T.wait_for(A, "__vbnet.status.canClaim", 14000) and await A.is_visible('#nbClaim'))
            post('/__vb/clock', {'add': 9}); await A.click('#nbClaim')
            ok = await T.wait_for(A, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 10000); tA = await A.inner_text('#ovOn')
            check('실서버: 기권승 요청 → 「기권승」 확정 · 서버 레이팅 반영', ok and '기권승' in tA and state()['records']['1']['rating'] > 1100, tA)
            for c in cs: await c.close()
            # ---- 4. 친선방 ----
            reset(1100, 1100); net4 = T.Net(None, BASE); cs, A, B = await pair_net(br, net4)
            await T.open_online(A); await T.open_online(B)
            await A.click('[data-on=create]'); await A.wait_for_selector('#waitCode:not([hidden])', timeout=5000); code = (await A.inner_text('#waitCode')).strip()
            check('실서버: 친선방 코드', len(code) == 4, code)
            await B.fill('#codeIn', code); await B.click('[data-on=join]')
            ok = await asyncio.gather(*[T.wait_for(p_, "__vbnet.cd.phase==='count'||__vbnet.cd.phase==='run'", 15000) for p_ in (A, B)]); check('실서버: 코드 입장 → 두 쪽 시작', all(ok))
            names = (await A.inner_text('#n1'), await B.inner_text('#n0')); check('실서버: 친선 상대 이름이 서로 보인다(방장은 sync 의 peer 로 알게 됨)', '베타' in names[0] and '알파' in names[1], names)
            # ---- 5. 어긋남 ----
            await T.set_bots(A, B, 'bot', 'bot'); await T.wait_for(A, "__vbnet.match.G.s.t>200", 30000); await A.evaluate('__vbnet.sabotage()')
            res = await T.wait_end([A, B], 30000); tA, tB = await A.inner_text('#ovOn'), await B.inner_text('#ovOn')
            check('실서버: 해시 어긋남 → 양쪽 무효 안내', all(res) and '어긋나' in tA and '어긋나' in tB, (tA, tB))
            for c in cs: await c.close()
            await br.close()
    finally:
        srv.terminate()
    print('\n전부 통과' if not T.fails else f'\n실패 {len(T.fails)}건: ' + ', '.join(T.fails)); sys.exit(1 if T.fails else 0)

async def pair_net(br, net):
    ca, A, _ = await T.mkctx(br, net, TA, '1', '알파'); cb, B, _ = await T.mkctx(br, net, TB, '2', '베타')
    return (ca, cb), A, B

if __name__ == '__main__':
    asyncio.run(main())
