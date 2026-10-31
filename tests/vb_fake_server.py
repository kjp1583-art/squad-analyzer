"""브장신 배구 온라인 — 웹 시험용 가짜 서버 (명세 SPEC_VB §6 의 JSON 만 구현한다).
서버 코드가 아니다: 입력을 중계하고, 해시를 맞춰 보고, 레이팅을 아주 단순하게 계산할 뿐이다.
시험이 시계(skew)를 앞으로 돌려 8초/20초 규칙을 빨리 확인할 수 있다."""
import random, time

TIERS = [('알', 0), ('아기새', 900), ('병아리', 1050), ('중닭', 1200), ('닭', 1350), ('치킨', 1500), ('치킨왕', 1700)]


def tier_of(r):
    idx = 0
    for i, (_, lo) in enumerate(TIERS):
        if r >= lo: idx = i
    step = 0
    if idx < len(TIERS) - 1:
        lo, hi = TIERS[idx][1], TIERS[idx + 1][1]
        step = min(3, 1 + int((r - lo) // ((hi - lo) / 3)))
    return TIERS[idx][0], step


class Fake:
    def __init__(self, target=5, peer_in_sync=True):
        self.users = {}            # token -> uid
        self.names = {}
        self.rec = {}
        self.rooms = {}
        self.queue = []            # uid, 들어온 순서
        self.matched = {}          # uid -> room id
        self.user_room = {}
        self.skew = 0.0
        self.target = target
        self.peer_in_sync = peer_in_sync
        self.log = []              # (uid, path)
        self.n = 0
        self.rng = random.Random(7)
        self.down = set()          # 응답하지 않는 uid(시험용 — 네트워크 단절)
        self.not_member = set()

    def now(self): return time.time() + self.skew

    def add_user(self, token, uid, name, rating=1000, placed=5):
        self.users[token] = uid; self.names[uid] = name
        t = tier_of(rating)
        self.rec[uid] = dict(name=name, rating=rating, peak=rating, placed=placed, w=0, l=0, streak=0, best_streak=0, pf=0, pa=0, matches=0, hist=[], by_opp={}, friendly={'w': 0, 'l': 0}, last_t=self.now())

    def key(self, rating):
        n, st = tier_of(rating); return [t for t, _ in TIERS].index(n) * 3 + max(0, st - 1)

    def label(self, r):
        if r['placed'] < 5: return '🎯 배치 중 (%d/5)' % r['placed']
        n, st = tier_of(r['rating']); return '%s %s' % (n, ['', 'I', 'II', 'III'][st])

    def me(self, uid):
        r = self.rec[uid]; tn, st = tier_of(r['rating'])
        return dict(name=r['name'], rating=r['rating'], peak=r['peak'], tier=tn, tier_name=tn, tier_step=st if r['placed'] >= 5 else 0, placed=r['placed'], w=r['w'], l=r['l'], streak=r['streak'], best_streak=r['best_streak'], pf=r['pf'], pa=r['pa'], matches=r['matches'], friendly=r['friendly'])

    # ---- 진입점 ----
    def handle(self, path, body):
        tok = body.get('token'); uid = self.users.get(tok)
        if not uid: return {'ok': False, 'code': 'auth'}
        self.log.append((uid, path))
        fn = getattr(self, 'r_' + path.strip('/').split('/')[-1], None)
        if not fn: return {'ok': False, 'code': 'not_found'}
        if uid in self.not_member and path.endswith(('queue',)): return {'ok': False, 'code': 'not_member'}
        return fn(uid, body)

    def r_status(self, uid, b):
        return dict(ok=True, online=len(self.users), waiting=len(self.queue), me=self.me(uid))

    def _mk_room(self, p, ranked, code=None):
        self.n += 1; rid = 'r%d' % self.n
        room = dict(id=rid, seed=self.rng.randint(1, 2**31 - 1), p=list(p), ranked=ranked, state='wait' if len(p) < 2 or True else 'play', inputs=[[], []], last_seen=[0, 0], created=self.now(),
                    hashes=[{}, {}], reports={}, result=None, forfeit=None, void=None, code=code, ready=[False, False], done_for={})
        self.rooms[rid] = room
        for u in p: self.user_room[u] = rid
        return room

    def _opp_info(self, uid):
        t = tier_of(self.rec[uid]['rating'])
        return dict(name=self.names[uid], rating=self.rec[uid]['rating'], tier=t[0], tier_name=t[0])

    def r_queue(self, uid, b):
        a = b.get('action')
        if a == 'join':
            if uid in self.user_room and self.rooms.get(self.user_room[uid], {}).get('state') in ('wait', 'play'):
                return {'ok': False, 'code': 'busy'}
            if uid not in self.queue: self.queue.append(uid)
            self._try_match(); return self._qstate(uid)
        if a == 'leave':
            if uid in self.queue: self.queue.remove(uid)
            return {'ok': True, 'state': 'idle'}
        return self._qstate(uid)

    def _try_match(self):
        if len(self.queue) >= 2:
            a, c = self.queue.pop(0), self.queue.pop(0)
            room = self._mk_room([a, c], True); self.matched[a] = room['id']; self.matched[c] = room['id']

    def _qstate(self, uid):
        if uid in self.matched:
            room = self.rooms[self.matched.pop(uid)]; side = room['p'].index(uid)
            return dict(ok=True, state='matched', room=room['id'], side=side, seed=room['seed'], opp=self._opp_info(room['p'][1 - side]), target=self.target, waited_s=0)
        if uid in self.queue: return dict(ok=True, state='waiting', waited_s=1, target=self.target)
        return dict(ok=True, state='idle')

    def r_room(self, uid, b):
        if b.get('action') == 'create':
            code = ''.join(self.rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(4))
            room = self._mk_room([uid], False, code)
            return dict(ok=True, code=code, room=room['id'], side=0, seed=room['seed'], target=self.target)
        code = str(b.get('code', '')).upper()
        for room in self.rooms.values():
            if room['code'] == code and room['state'] in ('wait',) and len(room['p']) == 1:
                if room['p'][0] == uid: return {'ok': False, 'code': 'bad'}
                room['p'].append(uid); self.user_room[uid] = room['id']
                return dict(ok=True, code=code, room=room['id'], side=1, seed=room['seed'], target=self.target, opp=self._opp_info(room['p'][0]))
        return {'ok': False, 'code': 'not_found'}

    # ---- 끝내기 ----
    def _timeouts(self, room):
        if room['state'] != 'play': return
        t = self.now()
        for i in (0, 1):
            if room['last_seen'][i] and t - room['last_seen'][i] >= 20 and room['last_seen'][1 - i] and t - room['last_seen'][1 - i] < 10:
                self._forfeit(room, i)

    def _forfeit(self, room, loser_i):
        if room['state'] in ('done', 'void'): return
        room['state'] = 'done'; room['forfeit'] = loser_i
        self._apply(room, winner_i=1 - loser_i, score=None)

    def _apply(self, room, winner_i, score):
        room['state'] = 'done'; res = {}
        for i, u in enumerate(room['p']):
            r = self.rec[u]; win = (i == winner_i); d = 0; before = r['rating']; pl0 = r['placed']; lab0 = self.label(r)
            if room['ranked']:
                d = 16 if win else -16
                r['rating'] = max(0, r['rating'] + d); r['peak'] = max(r['peak'], r['rating']); r['placed'] += 1
                r['w' if win else 'l'] += 1; r['streak'] = r['streak'] + 1 if win else 0; r['best_streak'] = max(r['best_streak'], r['streak']); r['matches'] += 1
            else:
                r['friendly']['w' if win else 'l'] += 1
            ps, os_ = (score[i], score[1 - i]) if score else (self.target if win else 0, 0 if win else self.target)
            if room['ranked']: r['pf'] += ps; r['pa'] += os_
            opp = room['p'][1 - i]
            r['hist'].insert(0, dict(t=int(self.now()), opp=self.names[opp], opp_uid=opp, opp_rating=self.rec[opp]['rating'], ps=ps, os=os_, win=win, delta=d, ranked=room['ranked'], dur=60))
            r['hist'] = r['hist'][:30]
            bo = r['by_opp'].setdefault(opp, {'w': 0, 'l': 0}); bo['w' if win else 'l'] += 1
            r['last_t'] = self.now()
            tn, st = tier_of(r['rating'])
            lab1 = self.label(r); prom = 0
            if pl0 >= 5 and r['placed'] >= 5: prom = 0
            k0, k1 = self.key(before), self.key(r['rating'])
            if pl0 >= 5 and r['placed'] >= 5: prom = (k1 > k0) - (k1 < k0)
            res[u] = dict(applied=True, win=win, delta=d, rating=r['rating'], rating_before=before, tier_before=lab0, tier_after=lab1, tier=tn, tier_name=tn if r['placed'] >= 5 else '배치 중', tier_step=st if r['placed'] >= 5 else 0, placing=r['placed'] < 5, placed=r['placed'], promoted=prom, ranked=room['ranked'], forfeit=room['forfeit'] is not None, capped=False)
            self.user_room.pop(u, None)
        room['result'] = res

    def r_result(self, uid, b):
        room = self.rooms.get(b.get('room'))
        if not room or uid not in room['p']: return {'ok': False, 'code': 'not_found'}
        if room['state'] == 'done': return dict(ok=True, **room['result'][uid])
        if room['state'] == 'void': return {'ok': False, 'code': 'bad', 'void': room['void']}
        sc = b.get('score'); i = room['p'].index(uid)
        room['reports'][i] = [int(sc[0]), int(sc[1])]
        if len(room['reports']) == 2:
            a, c = room['reports'][0], room['reports'][1]
            if a != [c[1], c[0]]: room['state'] = 'void'; room['void'] = 'mismatch'; return {'ok': True, 'applied': False, 'void': 'mismatch'}
            self._apply(room, 0 if a[0] > a[1] else 1, a)
            return dict(ok=True, **room['result'][uid])
        return dict(ok=True, pending=True)

    def r_leave(self, uid, b):
        room = self.rooms.get(b.get('room'))
        if not room or uid not in room['p']: return {'ok': False, 'code': 'not_found'}
        if room['state'] == 'play': self._forfeit(room, room['p'].index(uid))
        elif room['state'] == 'wait':
            room['state'] = 'void'; room['void'] = 'left'; [self.user_room.pop(u, None) for u in room['p']]
        return {'ok': True}

    def r_sync(self, uid, b):
        room = self.rooms.get(b.get('room'))
        if not room or uid not in room['p']: return {'ok': False, 'code': 'not_found'}
        i = room['p'].index(uid); o = 1 - i
        frm, ins, ack = b.get('from'), b.get('inputs'), b.get('ack')
        if not (isinstance(frm, int) and frm >= 0 and isinstance(ins, list) and len(ins) <= 120 and isinstance(ack, int) and ack >= 0): return {'ok': False, 'code': 'bad'}
        if any((not isinstance(v, int)) or v < 0 or v > 31 for v in ins): return {'ok': False, 'code': 'bad'}
        room['last_seen'][i] = self.now(); room['ready'][i] = True
        self._timeouts(room)
        if room['state'] == 'wait' and len(room['p']) == 2 and all(room['ready']): room['state'] = 'play'
        if room['state'] == 'play':
            have = len(room['inputs'][i])
            if frm > have: return {'ok': False, 'code': 'bad'}
            for k, v in enumerate(ins):
                if frm + k >= have: room['inputs'][i].append(v)
            h = b.get('hash')
            if h:
                room['hashes'][i][h['f']] = h['h']
                oh = room['hashes'][o].get(h['f'])
                if oh is not None and oh != h['h']: room['state'] = 'void'; room['void'] = 'desync'
        if room['state'] == 'play' and not room.get('start_at'): room['start_at'] = self.now() + 3.0
        resp = dict(ok=True, state=room['state'], opp=room['inputs'][o][ack:ack + 120] if room['state'] == 'play' else [], opp_next=len(room['inputs'][o]), got=len(room['inputs'][i]),
                    start_in=round(max(0.0, room.get('start_at', 0) - self.now()), 2) if room['state'] == 'play' else 0)
        if self.peer_in_sync and len(room['p']) == 2: resp['peer'] = self._opp_info(room['p'][o])
        if room['state'] == 'void': resp['void'] = room['void']
        if room['state'] == 'done':
            resp['forfeit'] = None if room['forfeit'] is None else ('me' if room['forfeit'] == i else 'opp')
            resp['result'] = room['result'][uid]
        return resp

    def r_claim(self, uid, b):
        room = self.rooms.get(b.get('room'))
        if not room or uid not in room['p']: return {'ok': False, 'code': 'not_found'}
        i = room['p'].index(uid); o = 1 - i
        if room['state'] != 'play': return {'ok': False, 'code': 'bad'}
        if self.now() - room['last_seen'][o] < 8: return {'ok': False, 'code': 'too_soon'}
        self._forfeit(room, o)
        return dict(ok=True, state='done', forfeit='opp', result=room['result'][uid])

    def r_me(self, uid, b):
        r = self.rec[uid]
        return dict(ok=True, record=self.me(uid), hist=r['hist'][:20], by_opp=[dict(uid=k, name=self.names.get(k, '?'), **v) for k, v in r['by_opp'].items()])

    def r_ranks(self, uid, b):
        rows = []
        for u, r in self.rec.items():
            if r['placed'] >= 5:
                tn, st = tier_of(r['rating']); rows.append(dict(uid=u, name=r['name'], rating=r['rating'], tier=tn, tier_name=tn, tier_step=st, w=r['w'], l=r['l'], streak=r['streak']))
        rows.sort(key=lambda x: -x['rating'])
        for k, x in enumerate(rows): x['rank'] = k + 1
        return dict(ok=True, rows=rows, total=len(rows))
