#!/usr/bin/env python3
"""라이어 게임 화면 시험용 가짜 서버 — /lg/* 를 흉내만 낸다(규칙은 없다).
시험이 /__set 으로 사람별 화면(view)을 직접 정해 주고, 화면이 보낸 요청은 /__log 로 읽는다.
  POST /__set    {"code":"ABCD","views":{"<uid>":{...}}}   방 화면 지정(v 는 자동으로 올라감)
  POST /__lobby  {...}                                     /lg/lobby 응답 지정
  POST /__fail   {"path":"/lg/vote","code":"locked"|null}  그 길을 실패시킴(null 이면 해제)
  POST /__skew   {"s":12.5}                                서버 시계를 이만큼 어긋나게
  POST /__drop   {"on":true}                               모든 /lg/ 요청에 연결 끊김(500)
  POST /__reset  · GET /__log
토큰은 'tok-<uid>' 꼴이어야 통과한다.
"""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

S = {}
LOCK = threading.Lock()
def reset():
    S.clear(); S.update(rooms={}, lobby={'ok': True, 'rooms': [], 'online': 0}, fail={}, skew=0.0, drop=False, log=[], hits={})
reset()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj, status=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in (('Access-Control-Allow-Origin', '*'), ('Access-Control-Allow-Headers', 'Content-Type'), ('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')): self.send_header(k, v)
        self.end_headers()
    def do_GET(self):
        if self.path == '/__log':
            with LOCK: return self._send({'log': S['log'], 'hits': S['hits']})
        self._send({'ok': False, 'code': 'not_found'}, 404)
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try: body = json.loads(self.rfile.read(n) or b'{}')
        except Exception: body = {}
        p = self.path
        with LOCK:
            if p == '/__reset': reset(); return self._send({'ok': True})
            if p == '/__set':
                r = S['rooms'].setdefault(body['code'], {'v': 0, 'views': {}})
                r['v'] += 1; r['views'] = body['views']; return self._send({'ok': True, 'v': r['v']})
            if p == '/__lobby': S['lobby'] = body; return self._send({'ok': True})
            if p == '/__fail':
                if body.get('code'): S['fail'][body['path']] = body['code']
                else: S['fail'].pop(body['path'], None)
                return self._send({'ok': True})
            if p == '/__skew': S['skew'] = float(body.get('s', 0)); return self._send({'ok': True})
            if p == '/__drop': S['drop'] = bool(body.get('on')); return self._send({'ok': True})
            if not p.startswith('/lg/'): return self._send({'ok': False, 'code': 'not_found'}, 404)
            S['hits'][p] = S['hits'].get(p, 0) + 1
            if S['drop']: return self._send({'ok': False, 'code': 'error'}, 500)
            tok = str(body.get('token', ''))
            if not tok.startswith('tok-'): return self._send({'ok': False, 'code': 'auth'}, 401)
            uid = tok[4:]
            if p != '/lg/state': S['log'].append({'path': p, 'uid': uid, 'body': {k: v for k, v in body.items() if k != 'token'}})
            if p in S['fail']: return self._send({'ok': False, 'code': S['fail'][p]})
            now = time.time() + S['skew']
            if p == '/lg/lobby': return self._send(dict(S['lobby'], now=now))
            if p == '/lg/state':
                r = S['rooms'].get(str(body.get('code', '')).upper())
                if not r: return self._send({'ok': False, 'code': 'not_found'})
                view = r['views'].get(uid)
                if view is None: return self._send({'ok': False, 'code': 'not_found'})
                if body.get('since') == r['v']: return self._send({'ok': True, 'same': True, 'now': now})
                out = dict(view); out.update(ok=True, v=r['v'], now=now, me=uid, code=str(body['code']).upper())
                sm = int(body.get('since_msg') or 0)
                out['msgs'] = [m for m in view.get('msgs', []) if m['id'] > sm]
                return self._send(out)
            if p == '/lg/create': return self._send({'ok': True, 'code': S.get('create_code', 'NEWR')})
            return self._send({'ok': True})

def serve(port=0):
    srv = ThreadingHTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

if __name__ == '__main__':
    s = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
    print('fake lg server on', s.server_address[1], flush=True)
    while True: time.sleep(3600)
