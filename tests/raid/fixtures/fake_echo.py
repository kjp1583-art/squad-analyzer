# -*- coding: utf-8 -*-
"""가짜 에코 서버 — 레이드 0단계 시험 페이지(raid-test/)용. 2026-10-08

시험실에서 사람이 폰으로 부딪힐 "진짜 에코 서버"가 지킬 통신 규약을 그대로 흉내 낸다(aiohttp).
  GET /health /ping /log?sid= /bench /          (JSON, no-store, CORS *)
  GET /ws?sid=  (별칭 /wstest)                   hello/tick/ack, 프로토콜 ping 5초, 무응답 10초 → 1001 no-response,
                                                 앱 메시지 900초 없으면 닫음, 수명 1시간, 같은 sid 새 연결 → 옛 연결 4001 replaced
  GET /raw                                       공용 에코 흉내(hello 없음, 받은 글자를 그대로 돌려줌)
  GET /rawdrop?after=3                           echo.websocket.org 흉내(인사말 → 무입력 N초 뒤 비정상 끊김)
  GET /hang?s=30                                 업그레이드를 안 해 주고 매달아 둔다(열림 시간초과 시험)
  GET /ctl?cmd=...                               시험이 일부러 만드는 상황
      cmd=silence&on=1[&sid=]    소켓은 열어 둔 채 tick/ack 를 멈춘다(침묵)
      cmd=close&code=1011[&sid=] 지금 열린 소켓을 닫는다(sid 없으면 전부)
      cmd=delay&ms=300           ack 를 늦춘다
      cmd=evil&on=1              hello/prev/closes 에 HTML·스크립트 문자열을 섞는다
      cmd=hellokill&code=1008    hello 를 보낸 직후 그 코드로 닫는다(0 이면 끔)
      cmd=idle&s=2 / cmd=lifetime&s=5  (규약의 15분·1시간을 짧게 — 시험 편의)
      cmd=reset                  기록을 전부 지운다
쓰는 법: 시험에서는 `async with FakeEcho() as srv:` 로 띄우고 srv.port 를 쓴다. 혼자 띄우려면 `python fake_echo.py --port 8765`.
"""
import asyncio, json, re, time, argparse, random, string
from aiohttp import web, WSMsgType

SID_RE = re.compile(r'^[A-Za-z0-9_-]{6,40}$')
EVIL = ['<img src=x onerror="window.__pwn=1">', '"><script>window.__pwn=2</script>', "'><svg onload=window.__pwn=3>", '</textarea><script>window.__pwn=4</script>']


def now_ms():
    return int(time.time() * 1000)


class Sess:
    def __init__(self, sid):
        self.sid = sid
        self.conns = 0
        self.opened = 0
        self.closed = 0
        self.events = []
        self.closes = []
        self.replaced = []
        self.bg_hints = []
        self.max_msg_gap = 0
        self.max_pong_gap = 0
        self.last_msg_ms = None
        self.last_pong_ms = None
        self.cur = None          # 지금 열린 Conn
        self.last_close = None   # {close_ms, code, why}

    def ev(self, name, **kw):
        d = {'ts': now_ms(), 'ev': name}
        d.update(kw)
        self.events.append(d)
        if len(self.events) > 500:
            del self.events[:100]

    def summary(self):
        return {'conns': self.conns, 'opened': self.opened, 'closed': self.closed, 'last_msg_ms': self.last_msg_ms, 'last_pong_ms': self.last_pong_ms,
                'max_msg_gap_ms': self.max_msg_gap, 'max_pong_gap_ms': self.max_pong_gap, 'bg_hints': list(self.bg_hints[-50:]),
                'closes': list(self.closes[-30:]), 'replaced': list(self.replaced[-30:])}


class Conn:
    def __init__(self, ws, sess, n):
        self.ws = ws
        self.sess = sess
        self.n = n
        t = now_ms()
        self.opened = t
        self.last_msg = t
        self.last_pong = t
        self.tick_n = 0
        self.closing_by = None   # 'server' | None
        self.tasks = []


class FakeEcho:
    def __init__(self, host='127.0.0.1', port=0, tick_ms=1000, ping_s=5.0, pong_to_s=10.0, idle_s=900.0, lifetime_s=3600.0):
        self.host, self.port_req = host, port
        self.tick_ms, self.ping_s, self.pong_to_s, self.idle_s, self.lifetime_s = tick_ms, ping_s, pong_to_s, idle_s, lifetime_s
        self.sessions = {}
        self.silence_all = False
        self.silence_sid = set()
        self.ack_delay_ms = 0
        self.evil = False
        self.hello_close = 0     # 0 이 아니면 hello 를 보낸 직후 그 코드로 닫는다(재접속 폭주 시험: 1008·1011·1013)
        self.bench = None
        self.started = time.time()
        self.peak = 0
        self.live = set()
        self.runner = None
        self.port = None
        self.log_hits = 0

    # ---- 수명 ----
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *a):
        await self.stop()

    async def start(self):
        app = web.Application()
        app.router.add_get('/', self.h_root)
        app.router.add_get('/health', self.h_health)
        app.router.add_get('/ping', self.h_ping)
        app.router.add_get('/log', self.h_log)
        app.router.add_get('/bench', self.h_bench)
        app.router.add_get('/ctl', self.h_ctl)
        app.router.add_get('/ws', self.h_ws)
        app.router.add_get('/wstest', self.h_ws)
        app.router.add_get('/raw', self.h_raw)
        app.router.add_get('/rawdrop', self.h_rawdrop)
        app.router.add_get('/hang', self.h_hang)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port_req)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        for c in list(self.live):
            try:
                await c.ws.close(code=1001, message=b'server-stop')
            except Exception:
                pass
        if self.runner:
            await self.runner.cleanup()

    def url(self, path=''):
        return 'http://%s:%d%s' % (self.host, self.port, path)

    def ws_url(self, path='/ws'):
        return 'ws://%s:%d%s' % (self.host, self.port, path)

    # ---- 제어(시험에서 직접 부른다) ----
    def set_silence(self, on=True, sid=None):
        if sid is None:
            self.silence_all = bool(on)
        elif on:
            self.silence_sid.add(sid)
        else:
            self.silence_sid.discard(sid)

    async def close_conns(self, code=1011, sid=None, why='ctl-close'):
        n = 0
        for c in list(self.live):
            if sid is None or c.sess.sid == sid:
                c.closing_by = 'server'
                self._note_close(c, code, why, 'server')
                try:
                    await c.ws.close(code=code, message=why.encode())
                except Exception:
                    pass
                n += 1
        return n

    def reset(self):
        self.sessions.clear()
        self.silence_all = False
        self.silence_sid.clear()
        self.ack_delay_ms = 0
        self.evil = False
        self.hello_close = 0

    def sess(self, sid):
        s = self.sessions.get(sid)
        if not s:
            s = self.sessions[sid] = Sess(sid)
        return s

    def is_silent(self, sid):
        return self.silence_all or sid in self.silence_sid

    # ---- HTTP ----
    def _json(self, obj, status=200):
        return web.json_response(obj, status=status, headers={'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*'})

    async def h_root(self, req):
        return web.Response(text='레이드 시험용 가짜 에코 서버입니다. /health /ping /log?sid= /ws\n', headers={'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*'}, content_type='text/plain', charset='utf-8')

    async def h_health(self, req):
        return self._json({'ok': True, 'v': 1, 'now': now_ms(), 'up_s': int(time.time() - self.started), 'conns': len(self.live), 'peak': self.peak})

    async def h_ping(self, req):
        return self._json({'t': now_ms()})

    async def h_bench(self, req):
        return self._json(self.bench or {'found': False})

    async def h_log(self, req):
        self.log_hits += 1
        sid = req.query.get('sid', '')
        s = self.sessions.get(sid)
        if not s:
            return self._json({'sid': sid, 'found': False, 'now': now_ms(), 'summary': {}, 'events': []})
        sm = s.summary()
        if self.evil:
            sm['closes'] = sm['closes'] + [{'ms': now_ms(), 'code': 1006, 'why': EVIL[1], 'by': 'peer', 'conn': 1}]
        return self._json({'sid': sid, 'found': True, 'now': now_ms(), 'summary': sm, 'events': s.events[-100:]})

    async def h_ctl(self, req):
        q = req.query
        cmd = q.get('cmd', '')
        sid = q.get('sid') or None
        on = q.get('on', '1') not in ('0', 'false', '')
        res = {'ok': True, 'cmd': cmd}
        if cmd == 'silence':
            self.set_silence(on, sid)
        elif cmd == 'close':
            res['closed'] = await self.close_conns(int(q.get('code', '1011')), sid, q.get('why', 'ctl-close'))
        elif cmd == 'delay':
            self.ack_delay_ms = int(q.get('ms', '0'))
        elif cmd == 'evil':
            self.evil = on
        elif cmd == 'hellokill':
            self.hello_close = int(q.get('code', '0'))
        elif cmd == 'idle':
            self.idle_s = float(q.get('s', '900'))
        elif cmd == 'lifetime':
            self.lifetime_s = float(q.get('s', '3600'))
        elif cmd == 'reset':
            self.reset()
        else:
            res = {'ok': False, 'err': 'unknown cmd'}
        return self._json(res)

    # ---- 기록 ----
    def _note_close(self, c, code, why, by):
        if getattr(c, 'noted', False):
            return
        c.noted = True
        s = c.sess
        t = now_ms()
        s.closed += 1
        s.closes.append({'ms': t, 'code': code, 'why': why, 'by': by, 'conn': c.n})
        s.ev('close', code=code, why=why, by=by, conn=c.n)
        s.last_close = {'close_ms': t, 'code': code, 'why': why}
        s.max_msg_gap = max(s.max_msg_gap, t - c.last_msg)
        s.max_pong_gap = max(s.max_pong_gap, t - c.last_pong)

    # ---- WebSocket(규약) ----
    async def h_ws(self, req):
        sid = req.query.get('sid', '')
        gen = False
        if not SID_RE.match(sid):
            sid = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))
            gen = True
        ws = web.WebSocketResponse(autoping=False, heartbeat=None, max_msg_size=64 * 1024)
        await ws.prepare(req)
        s = self.sess(sid)
        s.conns += 1
        s.opened += 1
        c = Conn(ws, s, s.conns)
        t = now_ms()
        # 같은 sid 의 옛 연결 대체
        old = s.cur
        if old is not None and not old.ws.closed:
            old.closing_by = 'server'
            s.replaced.append({'ms': t, 'old_msg_age_ms': t - old.last_msg, 'old_pong_age_ms': t - old.last_pong})
            s.ev('replaced', old_conn=old.n, old_msg_age_ms=t - old.last_msg, old_pong_age_ms=t - old.last_pong)
            self._note_close(old, 4001, 'replaced', 'server')
            try:
                await old.ws.close(code=4001, message=b'replaced')
            except Exception:
                pass
        s.cur = c
        self.live.add(c)
        self.peak = max(self.peak, len(self.live))
        s.ev('open', conn=c.n, gen=gen)
        prev = None
        if s.last_close:
            prev = {'close_ms': s.last_close['close_ms'], 'code': s.last_close['code'], 'why': s.last_close['why'], 'gap_ms': t - s.last_close['close_ms']}
        hello = {'t': 'hello', 'v': 1, 'sid': sid, 'srv_ms': t, 'conn': c.n, 'prev': prev, 'tick_ms': self.tick_ms, 'ping_s': int(self.ping_s), 'pong_to_s': int(self.pong_to_s)}
        if self.evil:
            hello['sid'] = EVIL[0]
            hello['prev'] = {'close_ms': t, 'code': EVIL[2], 'why': EVIL[1], 'gap_ms': EVIL[3]}
        try:
            await ws.send_str(json.dumps(hello))
        except Exception:
            pass
        if self.hello_close:
            code = int(self.hello_close)
            self._note_close(c, code, 'hello-kill', 'server')
            try:
                await ws.close(code=code, message=b'hello-kill')
            except Exception:
                pass
        c.tasks = [asyncio.ensure_future(self._tick_loop(c)), asyncio.ensure_future(self._watch_loop(c))]
        try:
            async for msg in ws:
                tt = now_ms()
                if msg.type == WSMsgType.PING:
                    c.last_pong = tt
                    s.last_pong_ms = tt
                    await ws.pong(msg.data)
                elif msg.type == WSMsgType.PONG:
                    s.max_pong_gap = max(s.max_pong_gap, tt - c.last_pong)
                    c.last_pong = tt
                    s.last_pong_ms = tt
                elif msg.type == WSMsgType.TEXT:
                    s.max_msg_gap = max(s.max_msg_gap, tt - c.last_msg)
                    c.last_msg = tt
                    s.last_msg_ms = tt
                    if self.is_silent(sid):
                        continue
                    asyncio.ensure_future(self._on_text(c, msg.data))
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR):
                    break
        except Exception:
            pass
        finally:
            for t_ in c.tasks:
                t_.cancel()
            # 다른 작업이 ws.close() 를 하는 중이면 닫기 프레임이 나갈 때까지 기다린다(안 그러면 브라우저가 1006 으로 본다)
            for _ in range(100):
                if ws.closed or ws.close_code is not None:
                    break
                await asyncio.sleep(0.02)
            self.live.discard(c)
            if not getattr(c, 'noted', False):
                code = ws.close_code if ws.close_code else (1005 if ws.close_code == 0 else 1006)
                self._note_close(c, code, 'peer-closed', 'peer')
            if s.cur is c:
                s.cur = None
        return ws

    async def _on_text(self, c, data):
        try:
            m = json.loads(data)
        except Exception:
            m = None
        if self.ack_delay_ms:
            await asyncio.sleep(self.ack_delay_ms / 1000.0)
        if c.ws.closed or self.is_silent(c.sess.sid):
            return
        if isinstance(m, dict) and m.get('t') in ('hb', 'bg'):
            k = m['t']
            if k == 'bg':
                c.sess.bg_hints.append(now_ms())
                c.sess.ev('bg', conn=c.n)
            ack = {'t': 'ack', 'k': k, 'n': m.get('n'), 'c': m.get('c'), 'srv_ms': now_ms()}
        else:
            ack = {'t': 'ack', 'k': 'echo', 'n': (m or {}).get('n') if isinstance(m, dict) else None, 'c': (m or {}).get('c') if isinstance(m, dict) else None, 'srv_ms': now_ms()}
        try:
            await c.ws.send_str(json.dumps(ack))
        except Exception:
            pass

    async def _tick_loop(self, c):
        try:
            while not c.ws.closed:
                await asyncio.sleep(self.tick_ms / 1000.0)
                if c.ws.closed:
                    break
                if self.is_silent(c.sess.sid):
                    continue
                c.tick_n += 1
                await c.ws.send_str(json.dumps({'t': 'tick', 'n': c.tick_n, 'srv_ms': now_ms()}))
        except (asyncio.CancelledError, Exception):
            pass

    async def _watch_loop(self, c):
        """프로토콜 ping · 무응답/무메시지/수명 규칙"""
        last_ping = time.time()
        try:
            while not c.ws.closed:
                await asyncio.sleep(min(0.5, self.ping_s / 4))
                t = time.time()
                if t - last_ping >= self.ping_s:
                    last_ping = t
                    try:
                        await c.ws.ping()
                    except Exception:
                        break
                tm = now_ms()
                if tm - max(c.last_msg, c.last_pong) > self.pong_to_s * 1000:
                    await self._server_close(c, 1001, 'no-response')
                    break
                if tm - c.last_msg > self.idle_s * 1000:
                    await self._server_close(c, 1000, 'idle')
                    break
                if tm - c.opened > self.lifetime_s * 1000:
                    await self._server_close(c, 1000, 'lifetime')
                    break
        except (asyncio.CancelledError, Exception):
            pass

    async def _server_close(self, c, code, why):
        c.closing_by = 'server'
        self._note_close(c, code, why, 'server')
        try:
            await c.ws.close(code=code, message=why.encode())
        except Exception:
            pass

    # ---- 공용 에코 흉내 ----
    async def h_raw(self, req):
        ws = web.WebSocketResponse(autoping=True)
        await ws.prepare(req)
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await ws.send_str(msg.data)
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
        return ws

    async def h_rawdrop(self, req):
        after = float(req.query.get('after', '3'))
        ws = web.WebSocketResponse(autoping=True)
        await ws.prepare(req)
        await ws.send_str('Request served by fake-echo-0000')
        last = time.time()

        async def killer():
            while True:
                await asyncio.sleep(0.2)
                if time.time() - last > after:
                    req.transport.abort()     # close 프레임 없이 끊기 → 브라우저는 1006
                    return
        k = asyncio.ensure_future(killer())
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    last = time.time()
                    await ws.send_str(msg.data)
        finally:
            k.cancel()
        return ws

    async def h_hang(self, req):
        await asyncio.sleep(float(req.query.get('s', '30')))
        return web.Response(text='late')


async def _main(port):
    async with FakeEcho(port=port) as srv:
        print('fake echo on', srv.url())
        await asyncio.Event().wait()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    try:
        asyncio.run(_main(a.port))
    except KeyboardInterrupt:
        pass
