#!/usr/bin/env python3
"""통합 시험 2 — 진짜 서버 코드(vb_local_server.py) + 두 브라우저. 큰 지연(100~300ms)·손실, 실제 키보드 입력(오른쪽 자리 포함),
한쪽 창 닫기(기권), 한쪽 이탈 뒤 재접속, 재매칭, 순위·전적 숫자 검산.
사용: CHROME=... python3.13 tests/brjvolley_online_real2_test.py [포트]"""
import asyncio, os, sys, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brjvolley_online_test as T
import brjvolley_online_real_test as R
from playwright.async_api import async_playwright
check = T.check
post, state, reset = R.post, R.state, R.reset
TA, TB = R.TA, R.TB

async def main():
    srv = subprocess.Popen(['/usr/bin/python3', R.SERVER, '--bot', R.BOT, '--port', str(R.PORT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try: state(); break
            except Exception: time.sleep(0.2)
        async with async_playwright() as p:
            br = await p.chromium.launch(executable_path=T.CHROME, args=['--allow-file-access-from-files', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'])
            # ---- 1. 큰 지연(100~300ms) + 손실 ----
            reset(1100, 1100); net = T.Net(None, R.BASE)
            for tk, (lo, hi) in ((TA, (0.10, 0.30)), (TB, (0.12, 0.28))): net.c(tk).update(lo=lo, hi=hi, pb=0.04, pa=0.03)
            cs, A, B = await R.pair_net(br, net)
            ok = await T.start_ranked(A, B); check('큰 지연: 매칭 성립', ok)
            await T.set_bots(A, B, 'bot', 'bot')
            res = await T.wait_end([A, B], 600000); sA, sB = await T.snap(A), await T.snap(B); sh, nh = T.same_hashes(sA, sB)
            check(f'큰 지연(100~300ms·손실 3~4%): 한 판 완주 · 점수 {sA["score"]} · 해시 {nh}개 일치 · 멈춤 {sA["stalls"]}회', all(res) and sA['score'] == sB['score'] and sA['t'] == sB['t'] and sh, (res, sA['score'], sB['score']))
            rec = state()['records']; check('큰 지연: 기록 1회 · 레이팅 합 보존 · 전적 합 2판', rec['1']['matches'] == 1 and rec['2']['matches'] == 1 and rec['1']['rating'] + rec['2']['rating'] == 2200, (rec['1']['rating'], rec['2']['rating']))
            w = 1 if sA['score'][0] > sA['score'][1] else 2
            check('큰 지연: 이긴 사람 w=1, 진 사람 l=1', rec[str(w)]['w'] == 1 and rec[str(3 - w)]['l'] == 1, (rec['1']['w'], rec['2']['w']))
            tA, tB = await A.inner_text('#ovOn'), await B.inner_text('#ovOn'); print('   결과창 A:', tA.replace('\n', ' | ')[:120]); print('   결과창 B:', tB.replace('\n', ' | ')[:120])
            # ---- 2. 재매칭 ----
            await T.set_bots(A, B, 'bot', 'bot')
            await A.click('#onAgain'); await B.click('#onAgain')
            ok = await asyncio.gather(*[T.wait_for(p_, "__vbnet.match!==null && __vbnet.match.G.s.t<200", 25000) for p_ in (A, B)])
            check('재매칭: 「한 판 더」 두 쪽이 누르면 새 판이 시작된다', all(ok))
            for c in cs: await c.close()
            # ---- 3. 실제 키보드 입력 : 오른쪽 자리(side 1) 사람이 → ← 로 움직인다 ----
            reset(1100, 1100); net = T.Net(None, R.BASE); cs, A, B = await R.pair_net(br, net)
            ok = await T.start_ranked(A, B); await T.set_bots(A, B, 'idle', 'idle')
            sides = await asyncio.gather(A.evaluate('__vbnet.match.side'), B.evaluate('__vbnet.match.side')); print('   side A/B =', sides)
            await T.wait_for(A, "__vbnet.cd.phase==='run' && __vbnet.match.G.s.t>30", 20000)
            await A.evaluate('(__vbnet.inject=null,0)'); await B.evaluate('(__vbnet.inject=null,0)')
            xs0 = await asyncio.gather(*[p_.evaluate('__vbnet.match.G.s.p.map(q=>q.x)') for p_ in (A, B)])
            xs0 = await asyncio.gather(*[p_.evaluate('__vbnet.match.G.s.p.map(q=>q.x)') for p_ in (A, B)])
            await B.keyboard.down('ArrowLeft'); await A.keyboard.down('ArrowLeft')
            await B.wait_for_timeout(450)
            xs1 = await asyncio.gather(*[p_.evaluate('__vbnet.match.G.s.p.map(q=>[q.x,q.side])') for p_ in (A, B)])
            await B.keyboard.up('ArrowLeft'); await A.keyboard.up('ArrowLeft')
            print('   x 전:', xs0, ' 후:', xs1)
            sa, sb = await T.snap(A), await T.snap(B); sh, nh = T.same_hashes(sa, sb)
            lo = min(range(2), key=lambda i: xs1[0][i][1])
            # (두 화면의 샘플 시각이 달라 위치 비교는 하지 않고, 아래 해시 일치와 움직임으로 본다)
            check(f'실제 키보드: 해시 {nh}개 일치', sh)
            moved = [abs(xs1[0][i][0] - xs0[0][i]) for i in range(2)]; print('   움직임', moved)
            check('실제 키보드: 양쪽 선수가 모두 실제로 움직였다(왼쪽 자리·오른쪽 자리)', all(m > 20 for m in moved), moved)
            # ---- 4. 창 닫기(기권) : B 가 컨텍스트를 닫는다 ----
            await T.wait_for(A, "__vbnet.match.G.s.t>400", 20000)
            await T.set_bots(A, B, 'bot', 'bot')
            await B.wait_for_timeout(500)
            t0 = time.time()
            # 창을 닫을 때 pagehide 가 부르는 것과 같은 beacon(실제 sendBeacon · text/plain)을 보낸다. (시험 브라우저는 닫는 순간의 요청을 가로채지 못해 직접 부른다)
            await B.evaluate("BrjVolleyNet.beaconLeave(BrjVolleyNet.API, JSON.parse(localStorage.sgg_dc).token, __vbnet.match.room)")
            await B.wait_for_timeout(1200); await cs[1].close()      # (닫는 순간 요청은 시험 도구가 못 가로채서 잠깐 기다린 뒤 닫는다)
            ok = await T.wait_for(A, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 40000)
            tA = await A.inner_text('#ovOn') if ok else ''
            print('   A 결과창:', tA.replace('\n', ' | ')[:140], f'({time.time()-t0:.1f}s)')
            rec = state()['records']
            check('창 닫기: 남은 사람에게 승리(기권승)로 끝난다', ok and ('승리' in tA or '기권승' in tA), tA)
            check('창 닫기: beacon 은 8초 안에 처리된다(20초 자동 기권을 기다리지 않음)', time.time() - t0 < 8, time.time() - t0)
            check('창 닫기: 서버 기록 — 나간 사람 패·남은 사람 승, 레이팅 합 보존', rec['2']['l'] == 1 and rec['1']['w'] == 1 and rec['1']['rating'] + rec['2']['rating'] == 2200, (rec['1'], rec['2']))
            # 나간 사람이 다시 열면
            cb, B2, _ = await T.mkctx(br, net, TB, '2', '베타'); await T.open_online(B2)
            t = await B2.inner_text('#onl'); check('나갔다 돌아온 사람: 온라인 메뉴가 정상(방 안 갇힘 없음)', await B2.is_visible('[data-on=rank]'), t[:150])
            await B2.click('[data-tab=rec]'); await B2.wait_for_selector('#onl .tbl', timeout=5000); t = await B2.inner_text('#onl'); check('나갔다 돌아온 사람: 전적에 방금 패배가 남아 있다', '알파' in t, t[:200])
            await cb.close(); await cs[0].close()
            # ---- 5. 이탈 후 결과 보고 없이 20초 침묵(자동 기권패) ----
            reset(1100, 1100); net = T.Net(None, R.BASE); cs, A, B = await R.pair_net(br, net)
            await T.start_ranked(A, B); await T.set_bots(A, B, 'bot', 'bot'); await T.wait_for(A, "__vbnet.match.G.s.t>400", 40000)
            net.c(TB)['down'] = True; await A.wait_for_timeout(1500)
            for _ in range(5): post('/__vb/clock', {'add': 5}); await A.wait_for_timeout(600)      # 시계를 한 번에 25초 밀면 A 도 같이 조용했던 것이 되므로 조금씩
            ok = await T.wait_for(A, "document.getElementById('ovOn').classList.contains('show') && !document.querySelector('#onBody .spin')", 20000)
            tA = await A.inner_text('#ovOn') if ok else ''; check('20초 침묵: 서버가 자동 기권 처리 → 남은 사람 결과창', ok and ('승리' in tA or '기권' in tA), tA)
            for c in cs: await c.close()
            await br.close()
    finally:
        srv.terminate()
    print('\n전부 통과' if not T.fails else f'\n실패 {len(T.fails)}건: ' + ', '.join(T.fails)); sys.exit(1 if T.fails else 0)

if __name__ == '__main__':
    asyncio.run(main())
