#!/usr/bin/env python3
"""브장신 배구 온라인 — WebRTC 직결(P2P) 시험.
가짜 서버(tests/vb_fake_server.py)에 두 브라우저를 붙이고, 브라우저의 RTCPeerConnection 만 가짜로 바꿔
(이 환경은 UDP 가 막혀 실제 ICE 가 안 된다 — FakePC 가 SDP·ICE 를 진짜 신호 경로로 주고받고 데이터만 파이썬으로 건넨다)
· 신호(offer/answer/ICE)가 /vb/sync 의 sig 칸으로 상대에게 가는지
· 채널이 열리면 입력이 직결로 다니고 서버 중계는 1초에 한 번으로 줄어드는지
· 해외 서버 왕복이 300~600ms 여도 판이 멈추지 않고 끝까지 가는지
· 직결이 안 되거나(막힌 망) 도중에 끊기면 서버 중계로 되돌아가 판이 이어지는지
를 본다. 사용: CHROME=... python3 tests/brjvolley_p2p_test.py
"""
import asyncio, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brjvolley_online_test as T
from playwright.async_api import async_playwright
check = T.check

FAKE = r'''
(function(){
  var seq=0;
  function Ch(){
    var self=this; this.readyState='connecting'; this.onmessage=null; this.onopen=null; this.onclose=null; this.sent=0;
    this.send=function(s){ if(self.readyState==='open'){ self.sent++; window.p2pSend(String(s)); } };
    this.close=function(){ if(self.readyState==='closed') return; self.readyState='closed'; try{ if(self.onclose) self.onclose({}); }catch(e){} };
    this._recv=function(s){ try{ if(self.onmessage) self.onmessage({data:s}); }catch(e){} };
    this._open=function(){ if(self.readyState!=='connecting') return; self.readyState='open'; window.__ch=self; try{ if(self.onopen) self.onopen({}); }catch(e){} };
  }
  function FakePC(cfg){
    var self=this; this.id='pc'+(++seq); this.localDescription=null; this.remoteDescription=null;
    this.connectionState='new'; this.iceConnectionState='new';
    this.onicecandidate=null; this.ondatachannel=null; this.onconnectionstatechange=null; this.oniceconnectionstatechange=null;
    this._ch=null; this.remoteIce=0; this.cands=0;
  }
  FakePC.prototype.createDataChannel=function(n){ this._ch=new Ch(); return this._ch; };
  FakePC.prototype.createOffer=function(){ return Promise.resolve({type:'offer', sdp:'FAKE-OFFER:'+this.id}); };
  FakePC.prototype.createAnswer=function(){ return Promise.resolve({type:'answer', sdp:'FAKE-ANSWER:'+this.id}); };
  FakePC.prototype.setLocalDescription=function(d){ var self=this;
    this.localDescription={type:(d&&d.type)||'offer', sdp:(d&&d.sdp)||''};
    this.cands++;
    if(this.onicecandidate) this.onicecandidate({candidate:{candidate:'candidate:1 1 udp 1 10.0.0.1 5000 typ host', sdpMid:'0', sdpMLineIndex:0}});
    this._maybe(); return Promise.resolve(); };
  FakePC.prototype.setRemoteDescription=function(d){ var self=this;
    this.remoteDescription={type:(d&&d.type)||'', sdp:(d&&d.sdp)||''};
    (window.__sigLog=window.__sigLog||[]).push(this.remoteDescription.type);
    this._maybe(); return Promise.resolve(); };
  FakePC.prototype.addIceCandidate=function(c){ this.remoteIce++; return Promise.resolve(); };
  FakePC.prototype.close=function(){ this.connectionState='closed'; };
  FakePC.prototype._maybe=function(){ var self=this;
    if(!this.localDescription||!this.remoteDescription) return;
    if(this.connectionState==='connected') return;
    if(window.__p2pMode==='never') return;
    this.connectionState='connected'; this.iceConnectionState='connected';
    if(this.remoteDescription.type==='offer'){ if(this.ondatachannel){ this._ch=new Ch(); try{ this.ondatachannel({channel:this._ch}); }catch(e){} this._ch._open(); } }
    else if(this._ch) this._ch._open();
    try{ if(this.onconnectionstatechange) this.onconnectionstatechange({}); }catch(e){} };
  window.__p2pRecv=function(s){ if(window.__ch) window.__ch._recv(s); };
  window.__realRTC=window.RTCPeerConnection;
  window.RTCPeerConnection=FakePC;
  window.__p2pMode='ok';
})();
'''


async def pair_p2p(br, net, mode='ok'):
    """두 브라우저 + 가짜 RTCPeerConnection + 파이썬 다리(두 페이지 사이 데이터 전달)"""
    A = B = None
    async def mk(tok, uid, name):
        ctx, pg, errs = await T.mkctx(br, net, tok, uid, name)
        await pg.evaluate(FAKE)
        await pg.evaluate(f"window.__p2pMode={mode!r}")
        return ctx, pg, errs
    ctxA, A, eA = await mk('tokA', 'A', '알파')
    ctxB, B, eB = await mk('tokB', 'B', '베타')

    async def to_b(s):
        try: await B.evaluate("s=>window.__p2pRecv(s)", s)
        except Exception: pass
    async def to_a(s):
        try: await A.evaluate("s=>window.__p2pRecv(s)", s)
        except Exception: pass
    await A.expose_function('p2pSend', to_b)
    await B.expose_function('p2pSend', to_a)
    return (ctxA, ctxB), A, B, (eA, eB)


async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=T.CHROME, args=['--allow-file-access-from-files', '--disable-background-timer-throttling',
                                                                    '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'])

        def mk(rA=1040, rB=1055, target=5):
            f = T.Fake(target=target); f.add_user('tokA', 'A', '알파', rA); f.add_user('tokB', 'B', '베타', rB); return f, T.Net(f)

        # ===== 1. 직결: 해외 서버 왕복 300~600ms 에서도 멈추지 않고 한 판 =====
        f, n = mk()
        for tk in ('tokA', 'tokB'):
            n.c(tk).update(lo=0.15, hi=0.30)                        # 편도 150~300ms = 왕복 300~600ms
        ctxs, A, B, errs = await pair_p2p(br, n)
        ok = await T.start_ranked(A, B)
        check('직결: 매칭 성립(느린 망에서도)', ok)
        await T.set_bots(A, B, 'bot', 'idle')
        got = await asyncio.gather(*[T.wait_for(p_, "__vbnet.status.p2p==='on'", 20000) for p_ in (A, B)])
        check('직결: 두 브라우저가 WebRTC 채널을 열어 P2P 로 붙는다', all(got), [await p_.evaluate('__vbnet.status.p2p') for p_ in (A, B)])
        sigs = await A.evaluate('window.__sigLog||[]'); sigb = await B.evaluate('window.__sigLog||[]')
        check('직결: 신호가 서버(/vb/sync sig)를 거쳐 상대에게 간다 — 제안한 쪽은 answer 를, 받은 쪽은 offer 를 받는다',
              'answer' in sigs and 'offer' in sigb, (sigs, sigb))
        cands = await A.evaluate("(()=>{const m=__vbnet.match; return {rtt:m.status.p2pRtt, ice:m.p2p&&m.p2p.state};})()")
        await T.wait_for(A, "__vbnet.cd.phase==='run'", 15000)
        await A.wait_for_timeout(2500)
        r1 = await A.evaluate('__vbnet.match.reqCount'); t1 = time.time()
        await A.wait_for_timeout(2000)
        r2 = await A.evaluate('__vbnet.match.reqCount'); rate = (r2 - r1) / max(0.001, time.time() - t1)
        check(f'직결: 경기 중 서버 중계는 1초에 한 번 수준(실측 {rate:.1f}회/초) — 해외 RTT 가 경기에서 빠진다', rate <= 3.0, rate)
        check('직결: 상태 표시줄이 P2P 와 직결 지연을 보여 준다',
              'P2P' in await A.inner_text('#nbState') and '지연' in await A.inner_text('#nbPing'), (await A.inner_text('#nbState'), await A.inner_text('#nbPing')))
        res = await T.wait_end([A, B], 240000)
        sA, sB = await T.snap(A), await T.snap(B); sh, nh = T.same_hashes(sA, sB)
        check(f'직결: 한 판이 끝까지 간다 · 점수 {sA["score"]} · 해시 {nh}개 일치', all(res) and sA['score'] == sB['score'] and sA['t'] == sB['t'] and sh, (res, sA['score'], sB['score']))
        check(f'직결: 멈춤(연결 대기) {sA["stalls"]}회 안쪽 — 300~600ms 중계에서도 락스텝이 끊기지 않는다', sA['stalls'] <= 3, sA)
        check('직결: 서버 기록 반영(레이팅 합 보존·1판)', f.rec['A']['rating'] + f.rec['B']['rating'] == 2095 and f.rec['A']['matches'] == 1, (f.rec['A']['rating'], f.rec['B']['rating']))
        check('직결: 콘솔·페이지 오류 없음', not any(errs[0]) and not any(errs[1]), (errs[0][:2], errs[1][:2]))
        for c in ctxs: await c.close()

        # ===== 2. 직결 실패(막힌 망) → 서버 중계로 그대로 진행 =====
        f, n = mk(1100, 1100)
        ctxs, A, B, errs = await pair_p2p(br, n, mode='never')
        await A.evaluate('BrjVolleyNet.NET.P2P_TIMEOUT=2500'); await B.evaluate('BrjVolleyNet.NET.P2P_TIMEOUT=2500')
        ok = await T.start_ranked(A, B); check('폴백: 매칭 성립', ok)
        await T.set_bots(A, B, 'bot', 'idle')
        timed = await T.wait_for(A, "__vbnet.status.p2p==='off'", 15000)
        check('폴백: 채널이 안 열리면 정해 둔 시간 뒤 직결을 포기하고 서버 중계로만 간다', timed, await A.evaluate('__vbnet.status.p2p'))
        res = await T.wait_end([A, B], 180000); sA, sB = await T.snap(A), await T.snap(B)
        check('폴백: 서버 중계로 한 판이 끝까지 간다(점수 일치)', all(res) and sA['score'] == sB['score'] and f.rec['A']['matches'] == 1, (res, sA['score'], sB['score']))
        check('폴백: 상태 표시줄이 P2P 가 아님을 보여 준다', 'P2P' not in await A.inner_text('#nbState'), await A.inner_text('#nbState'))
        for c in ctxs: await c.close()

        # ===== 3. 경기 도중 직결이 끊기면 서버 중계로 복귀 =====
        f, n = mk(1100, 1100)
        ctxs, A, B, errs = await pair_p2p(br, n)
        ok = await T.start_ranked(A, B); check('중단: 매칭 성립', ok)
        await T.set_bots(A, B, 'bot', 'bot')
        on = await asyncio.gather(*[T.wait_for(p_, "__vbnet.status.p2p==='on'", 20000) for p_ in (A, B)])
        check('중단: 직결로 시작', all(on), [await p_.evaluate('__vbnet.status.p2p') for p_ in (A, B)])
        await T.wait_for(A, "__vbnet.match.G.s.t>90", 20000)
        await B.evaluate("window.__ch.close()")                     # 베타 쪽 채널만 끊긴다 — 알파 쪽은 반쯤 열린 채(한쪽만 close)
        back = await T.wait_for(A, "__vbnet.status.p2p!=='on'", 8000)
        check('중단: 끊기면 서버 중계로 되돌아간다(판은 계속)', back, await A.evaluate('__vbnet.status.p2p'))
        res = await T.wait_end([A, B], 240000); sA, sB = await T.snap(A), await T.snap(B); sh, nh = T.same_hashes(sA, sB)
        check(f'중단: 끊긴 뒤에도 한 판이 끝까지 간다 · 점수 {sA["score"]} · 해시 일치', all(res) and sA['score'] == sB['score'] and sh, (res, sA['score'], sB['score']))
        for c in ctxs: await c.close()

        await br.close()
    print('\n전부 통과' if not T.fails else f'\n실패 {len(T.fails)}건: ' + ', '.join(T.fails))
    sys.exit(1 if T.fails else 0)


if __name__ == '__main__':
    asyncio.run(main())
