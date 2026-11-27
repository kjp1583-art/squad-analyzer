/* 브장신 배구 온라인 — 락스텝 클라이언트 + WebRTC 직결 + 티어 표시 도우미 (DOM 없음, 화면과 시험이 같이 쓴다)
 *
 * 서버는 게임을 돌리지 않는다. 두 브라우저가 같은 시드·같은 입력으로 BrjVolley 를 똑같이 돌리고,
 * 서버는 입력 비트만 중계한다(비트: l=1 r=2 u=4 d=8 hit=16).
 *   프레임 f 의 내 입력은 f−D 번째 프레임을 돌릴 때 정해서 보낸다(입력 지연 D).
 *   상대 입력이 아직 안 왔으면 그 프레임에서 멈추고(stalled) 오면 이어 간다.
 *   60프레임마다 상태 해시를 서버에 보내 어긋남(desync)을 잡는다.
 *
 * 두 길로 상대에게 입력을 보낸다.
 *   ① WebRTC 직결(RTCDataChannel): 경기 시작 전에 /vb/sync 의 sig 칸으로 SDP·ICE 를 주고받아 연결하고,
 *      열리면 입력을 매 프레임(60Hz) 상대에게 직접 보낸다. 해외 중계 서버 왕복(300~600ms)을 건너뛴다.
 *   ② 서버 중계(HTTP /vb/sync): 직결이 안 되면(방화벽·NAT) 이 길로만 간다. 요청을 2개까지 겹쳐 보내
 *      (파이프라인) 직렬 대기로 인한 멈춤을 줄이고, 재어 둔 지연에 맞춰 입력 지연 D 를 늘린다.
 *   직결 중에도 /vb/sync 는 1초에 한 번만 돈다 — 입력 백업(서버 재생·결과 판정용)·해시 검증·생존 확인.
 *   도중에 직결이 끊기면 자동으로 서버 중계로 돌아간다.
 *
 * const m = BrjVolleyNet.Match({api, token, room, side, seed, target, ranked, onEnd(info), onLocalOver()});
 * m.start(); 매 프레임 m.tick(sampleBits) (한 프레임 돌았으면 1, 멈췄으면 0) · m.G 가 엔진 · m.status 가 연결 상태
 * m.status.p2p = 'off' | 'try' | 'on' | 'lost' · m.status.p2pRtt = 직결 왕복(ms)
 * m.leave() 기권 · m.claim() 기권승 요청 · m.stop()
 */
(function (root) {
  'use strict';
  var API = 'https://hth3thmujs.apps.bot-hosting.cloud';
  var NET = {
    D: 4,                 // 입력 지연 시작값(프레임) — 직결이면 이대로(67ms), 서버 중계면 잰 지연만큼 늘린다(내 쪽만). 줄이지는 않는다
    D_MAX: 20,            // 서버 중계 때 상한(333ms) — 핑이 커도 멈추지 않게 지연을 늘린다
    P2P_D_MAX: 8,         // 직결 때 상한 — 왕복이 짧아 조금만 늦추면 된다
    PERIOD: 50,           // 서버 중계 중 /vb/sync 간격(ms) = 20Hz
    IDLE_PERIOD: 250,     // 경기 전·후 간격
    SIG_PERIOD: 150,      // WebRTC 신호(offer/answer/ICE)를 주고받는 동안의 간격
    P2P_PERIOD: 1000,     // 직결 중 /vb/sync 간격 — 입력 백업·해시·생존 확인만(경기 지연과 무관)
    PIPE: 2,              // 서버 중계 때 동시에 띄우는 요청 수(하나가 막혀도 다음이 나간다)
    PIPE_GAP: 250,        // 앞 요청이 이만큼 오래 붙들려 있을 때만 하나 더 내보낸다(정상일 땐 늘 한 개)
    MIN_GAP: 34,          // 요청 사이 최소 간격 — 서버 한도(초당 30) 아래로
    OVERLAP: 12,          // 내 입력을 이만큼 겹쳐 다시 보낸다(손실 대비)
    MAX_FRAMES: 120,      // 요청 하나에 실을 프레임 상한(서버 상한과 같게)
    TIMEOUT: 3500,        // 요청 하나의 제한 시간
    KICK_GAP: 40,         // 멈춰 있을 때 앞당겨 부르는 최소 간격(ms) — 서버 한도 초당 30 아래
    P2P_KICK_GAP: 120,    // 직결 중 빠진 프레임을 다시 달라고 조르는 간격(ms)
    CLAIM_AFTER: 8000,    // 상대가 이만큼 멈춰 있으면 「기권승 요청」 버튼
    GIVEUP_AFTER: 20000,  // 서버와 이만큼 못 닿으면 포기하고 안내
    RESULT_WAIT: 20000,   // 결과가 반영되길 기다리는 한계
    P2P: true,            // WebRTC 직결을 시도한다
    P2P_TIMEOUT: 8000,    // 이만큼 안 열리면 포기하고 서버 중계로만 간다
    P2P_PING: 500,        // 직결 왕복을 재는 간격(ms)
    P2P_SILENT: 2000,     // 직결로 이만큼 아무것도 안 오면 죽은 줄 알고 서버 중계로 되돌린다
    SIG_BATCH: 8,         // 요청 하나에 실을 신호 수
    SIG_KEEP: 24,         // 아직 못 보낸 신호를 들고 있는 수
    STUN: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302']
  };
  function now() { return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now(); }
  function dec(b) { return { l: !!(b & 1), r: !!(b & 2), u: !!(b & 4), d: !!(b & 8), hit: !!(b & 16) }; }
  function enc(i) { return (i.l ? 1 : 0) | (i.r ? 2 : 0) | (i.u ? 4 : 0) | (i.d ? 8 : 0) | (i.hit ? 16 : 0); }
  function pcCtor() {                       // 시험은 NET.RTCPC 로 가짜 연결을 끼워 넣는다
    if (NET.RTCPC) return NET.RTCPC;
    return (typeof RTCPeerConnection !== 'undefined') ? RTCPeerConnection : null;
  }

  // ---------- 티어 (서버가 주는 값을 우선 쓰고, 없으면 레이팅으로 계산) ----------
  var TIERS = [
    { k: 'egg', n: '알', e: '🥚', min: 0, c: '#a89878' }, { k: 'baby', n: '아기새', e: '🐣', min: 900, c: '#d9a21b' },
    { k: 'chick', n: '병아리', e: '🐥', min: 1050, c: '#e68a00' }, { k: 'mid', n: '중닭', e: '🐤', min: 1200, c: '#e0622c' },
    { k: 'hen', n: '닭', e: '🐔', min: 1350, c: '#d63e6b' }, { k: 'chicken', n: '치킨', e: '🍗', min: 1500, c: '#b8431f' },
    { k: 'king', n: '치킨왕', e: '👑', min: 1700, c: '#7b3fe0' }
  ];
  var BYLEN = TIERS.slice().sort(function (a, b) { return b.n.length - a.n.length; });   // '치킨왕' 이 '치킨'·'닭' 보다 먼저 맞게
  var ROMAN = { I: 1, II: 2, III: 3, '1': 1, '2': 2, '3': 3 };
  function stepOf(v) { if (v == null) return 0; if (typeof v === 'number') return v >= 1 && v <= 3 ? v | 0 : 0; var t = String(v).trim().toUpperCase(); return ROMAN[t] || 0; }
  var OPEN_STEP = 100;   // 서버 BRV_OPEN_STEP — 치킨왕 안의 I·II·III 폭
  function tierByRating(r) {
    r = Number(r); if (!isFinite(r)) return { idx: -1, step: 0 };
    var idx = 0; for (var i = 0; i < TIERS.length; i++) if (r >= TIERS[i].min) idx = i;
    var lo = TIERS[idx].min, hi = idx < TIERS.length - 1 ? TIERS[idx + 1].min : lo + 3 * OPEN_STEP; var step = Math.min(3, 1 + Math.floor((r - lo) / ((hi - lo) / 3)));
    return { idx: idx, step: step };
  }
  // o: {rating, tier, tier_name, tier_step, placed} → {idx, step, e, n, c, step_s, key(비교용 숫자), placing}
  function tierInfo(o) {
    o = o || {}; var idx = -1, step = stepOf(o.tier_step);
    if (o.placing === true || /배치/.test(String(o.tier_name || '') + String(o.tier_label || ''))) return { idx: -1, step: 0, e: '🎯', n: '배치 중', c: '#7c8aa8', step_s: '', key: -1, placing: true };
    var names = [o.tier_name, o.tier];
    for (var j = 0; j < names.length && idx < 0; j++) {
      var nm = names[j]; if (nm == null) continue;
      if (typeof nm === 'number' && nm >= 0 && nm < TIERS.length && j === 1) { idx = nm | 0; break; }
      nm = String(nm);
      for (var i = 0; i < BYLEN.length; i++) if (nm.indexOf(BYLEN[i].n) >= 0 || nm.indexOf(BYLEN[i].e) >= 0 || nm === BYLEN[i].k) { idx = TIERS.indexOf(BYLEN[i]); break; }
    }
    if (idx < 0 && o.rating != null) { var t = tierByRating(o.rating); idx = t.idx; if (!step) step = t.step; }
    var placing = o.placed != null && Number(o.placed) < 5;
    if (idx < 0) return { idx: -1, step: 0, e: '❔', n: '배치 중', c: '#7c8aa8', step_s: '', key: -1, placing: true };
    var T = TIERS[idx];
    return { idx: idx, step: step, e: o.tier_icon || T.e, n: T.n, c: T.c, step_s: step ? ['', 'I', 'II', 'III'][step] : '', key: idx * 3 + Math.max(0, (step || 1) - 1), placing: placing };
  }

  // ---------- 서버 호출 ----------
  function call(path, body, o) {
    o = o || {}; var f = o.fetch || (typeof fetch !== 'undefined' ? fetch : null);
    if (!f) return Promise.resolve({ ok: false, code: 'nofetch' });
    var ctl = (typeof AbortController !== 'undefined') ? new AbortController() : null, to = null;
    if (ctl) to = setTimeout(function () { try { ctl.abort(); } catch (e) { } }, o.timeout || NET.TIMEOUT);
    return f((o.api || API) + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl ? ctl.signal : undefined, keepalive: !!o.keepalive })
      .then(function (r) { return r.json().then(function (j) { return j || { ok: false, code: 'http' }; }, function () { return { ok: false, code: 'http', status: r.status }; }); })
      .catch(function () { return { ok: false, code: 'net' }; })
      .then(function (j) { if (to) clearTimeout(to); return j; });
  }
  function beaconLeave(api, token, room) {       // 창을 닫는 순간 기권을 알린다 — 응답은 못 받는다
    var body = JSON.stringify({ token: token, room: room });
    try { if (navigator.sendBeacon && navigator.sendBeacon((api || API) + '/vb/leave', new Blob([body], { type: 'text/plain;charset=UTF-8' }))) return true; } catch (e) { }
    try { fetch((api || API) + '/vb/leave', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body, keepalive: true }); return true; } catch (e) { }
    return false;
  }

  // ---------- 한 판 ----------
  function Match(o) {
    if (!(this instanceof Match)) return new Match(o);
    var BV = root.BrjVolley; this.o = o; this.api = o.api || API; this.token = o.token; this.room = o.room; this.side = o.side ? 1 : 0;
    this.D = o.D || NET.D; this.ranked = !!o.ranked; this.fetch = o.fetch;
    this.G = BV.create({ seed: o.seed, target: o.target || 15 }); this.G.reset();
    this.myIn = []; this.opIn = []; for (var i = 0; i < this.D; i++) this.myIn.push(0);   // 처음 D 프레임은 모두 0 (서로 같은 규칙)
    this.ack = 0; this.srvHave = 0; this.hq = []; this.hsent = 0; this.hashes = [];
    this.stalledSince = 0; this.rtt = 0; this.failSince = 0; this.lastOk = now();
    this.localOver = false; this.resultSent = false; this.resultTries = 0; this.resultResp = null; this.resultAt = 0;
    this.overAt = 0; this.resultReadyAt = 0;
    this.ended = null; this.finished = false; this.stopped = false; this.playing = false; this.timer = null; this.inflight = 0; this.sentCount = 0; this.reqCount = 0;
    this.p2p = { state: 'off', rtt: 0, since: 0, opened: 0, tries: 0 };
    this.pc = null; this.dc = null; this.dcNext = 0; this.sigQ = []; this.sigFly = []; this.sigN = 0; this.reqAt = 0; this.pingTimer = null; this.pingSeq = 0; this.dcLastAt = 0;
    this.iceQ = []; this.farSdp = null; this.sigMax = 4500;   // 원격 설명 전에 온 ICE 는 모아 두었다가 나중에 넣는다
    this.status = { state: 'wait', rtt: 0, stalled: 0, canClaim: false, fails: 0, peer: null, startIn: null, forfeit: null, stallCount: 0, p2p: 'off', p2pRtt: 0 };
  }
  var P = Match.prototype;
  P.begin = function () {                                    // 카운트다운이 끝나 프레임을 돌려도 된다
    var want;
    if (this.p2p.state === 'on') want = Math.max(this.D, Math.min(NET.P2P_D_MAX, Math.ceil(((this.p2p.rtt || 30) * 0.5 + 25) / 16.7)));   // 직결: 왕복이 짧으니 조금만 늦춘다(바닥은 시작값)
    else want = Math.max(this.D, Math.min(NET.D_MAX, Math.ceil(((this.rtt || 0) * 0.5 + NET.PERIOD + 20) / 16.7)));                 // 서버 중계: 잰 지연만큼 늘려 멈춤을 줄인다
    // D 는 줄이지 않는다 — 처음 D 프레임의 0 입력은 이미 상대에게 갔고, 그 칸을 나중에 바꾸면 두 화면이 어긋난다.
    for (var i = this.D; i < want; i++) this.myIn.push(0);    // 늘어난 만큼 0 입력으로 메운다(아직 한 프레임도 안 돌렸다)
    this.D = want; this.playing = true;
    if (this.p2p.state !== 'on') this._p2pStart();            // 카운트다운 동안 못 붙었으면 여기서 한 번 더 시도
  };
  P.tick = function (sample) {
    if (this.ended || this.localOver || !this.playing) return 0;
    var G = this.G, f = G.s.t;
    this._timers();
    if (this.opIn[f] === undefined) {                          // 상대 입력 대기
      if (!this.stalledSince) { this.stalledSince = now(); this.status.stallCount++; }
      this.status.stalled = now() - this.stalledSince; this.status.canClaim = this.status.stalled >= NET.CLAIM_AFTER;
      this._kick(); this._grow();
      return 0;
    }
    this.stalledSince = 0; this.status.stalled = 0; this.status.canClaim = false;
    this.myIn[f + this.D] = sample() & 31;
    var mine = dec(this.myIn[f]), op = dec(this.opIn[f]);
    if (this.side === 0) G.step(mine, op); else G.step(op, mine);
    this._dcFlush();                                           // 직결이면 방금 정한 입력을 곧바로 상대에게
    if (G.s.t % 60 === 0) { var h = { f: G.s.t, h: G.hash() }; this.hq.push(h); this.hashes.push(h); }
    if (G.s.phase === 'over') { this.localOver = true; this.overAt = now(); if (this.o.onLocalOver) this.o.onLocalOver(this); }
    return 1;
  };
  P.start = function () { this._p2pStart(); this._pump(); };
  P.stop = function () {
    this.stopped = true; if (this.timer) clearTimeout(this.timer); this.timer = null;
    this._p2pClose();
  };
  P._slow = function () { return this.p2p.state === 'on'; };
  P._pipe = function () { return this._slow() ? 1 : NET.PIPE; };
  P._needFlush = function () { return this.localOver && !this.resultSent && this.srvHave < this.G.s.t; };
  P._period = function () {
    if (this.finished) return NET.PERIOD;
    if (this.localOver) return this._needFlush() ? 120 : 300;          // 끝나면 남은 입력을 서버로 밀어 넣는다
    if (this.playing) return this._slow() ? NET.P2P_PERIOD : NET.PERIOD;
    return this.p2p.state === 'try' ? NET.SIG_PERIOD : NET.IDLE_PERIOD;
  };
  P._arm = function (ms, onlyIfNone) {
    if (this.stopped) return;
    if (onlyIfNone && this.timer) return;
    if (this.timer) clearTimeout(this.timer);
    var self = this;
    this.timer = setTimeout(function () { self.timer = null; self._pump(); }, Math.max(0, ms));
  };
  P._pump = function () {
    var self = this; if (self.stopped) return;
    if (self.inflight >= self._pipe()) { self._arm(40); return; }   // 자리가 없다 — 응답이 오면 그때 다시 건다
    var gap = now() - (self.lastSend || 0);
    if (gap < NET.MIN_GAP) { self._arm(NET.MIN_GAP - gap); return; }  // 서버 한도(초당 30) 아래로
    // 파이프라인은 「앞 요청이 오래 붙들려 있을 때」만 — 정상 속도면 늘 한 개만 나간다(중복 전송으로 대역·한도를 낭비하지 않게)
    if (self.inflight > 0 && gap < NET.PIPE_GAP) { self._arm(Math.min(NET.PIPE_GAP - gap, 60)); return; }
    var t0 = now(); self.inflight++; self.lastSend = t0;
    self._sync().then(function (extra) {
      self.inflight = Math.max(0, self.inflight - 1);
      if (self.stopped) return;
      self._arm(Math.max(0, self._period() - (now() - t0)) + (extra || 0), true);
    });
    if (self._pipe() > 1) self._arm(NET.PIPE_GAP, true);            // 앞 요청이 막혀 있으면 그때 한 개 더
  };
  // 상대 입력을 기다리며 멈춰 있으면 다음 정기 호출을 기다리지 않고 바로 한 번 더 부른다(서버 한도 초당 30 아래로: 40ms 간격)
  P._kick = function () {
    if (this.stopped || this.finished) return;
    var t = now();
    if (this.p2p.state === 'on') {                             // 직결: 빠진 프레임만 다시 달라고 한다
      if (t - (this.reqAt || 0) < NET.P2P_KICK_GAP) return;
      this.reqAt = t; this._dcSend({ t: 'r', f: this.G.s.t });
      return;
    }
    if (this.inflight >= this._pipe()) return;
    if (t - (this.lastSend || 0) < NET.KICK_GAP) return;
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    this._pump();
  };
  P._grow = function () {                                      // 계속 멈추면 입력 지연을 늘린다(멈춤이 입력 밀림보다 나쁘다)
    var cap = this.p2p.state === 'on' ? NET.P2P_D_MAX : NET.D_MAX;
    if (this.D >= cap || this.status.stalled < 400) return;
    var nd = Math.min(cap, this.D + (this.p2p.state === 'on' ? 1 : 2));
    if (nd === this.D) return;
    while (this.myIn.length < this.G.s.t + nd) this.myIn.push(0);   // 이번 프레임이 고를 nd 번째 입력까지만 — 그 뒤는 아직 안 정한 값이다
    this.D = nd;
  };
  P._body = function () {
    var end = this.myIn.length;
    var anchor = this.hasGot ? Math.min(this.srvHave, end) : Math.max(0, end - NET.MAX_FRAMES);
    var from = Math.max(0, anchor - (this.hasGot ? NET.OVERLAP : 0));
    if (end - from > NET.MAX_FRAMES) from = anchor;      // 밀린 입력이 많으면 겹침을 포기하고 「서버가 받은 지점」부터 — 빈 곳(유실)을 만들지 않는다
    var b = { token: this.token, room: this.room, from: from, inputs: this.myIn.slice(from, end), ack: this.ack };
    var hs = null;
    if (this.hsent < this.hq.length) { b.hash = this.hq[this.hsent]; hs = this.hsent; }
    if (this.sigQ.length) { var q = this.sigQ.splice(0, NET.SIG_BATCH); this.sigFly.push(q); b.sig = q; }
    b.sig_n = this.sigN;
    return { body: b, end: end, hashed: !!b.hash, hashAt: hs, sig: this.sigFly.length ? this.sigFly[this.sigFly.length - 1] : null };
  };
  P._sync = function () {
    var self = this;
    if (self.finished) return Promise.resolve();
    var q = self._body(), t0 = now(); self.reqCount++;
    return call('/vb/sync', q.body, { api: self.api, fetch: self.fetch }).then(function (r) {
      var rt = now() - t0;
      if (self.stopped) return 0;
      if (!r || r.ok === false) { self._sigReturn(q, r); return self._fail(r); }
      self.failSince = 0; self.lastOk = now(); self.status.fails = 0; self.rtt = self.rtt ? self.rtt * 0.8 + rt * 0.2 : rt; self.status.rtt = Math.round(self.rtt);
      if (typeof r.got === 'number') { self.hasGot = true; self.srvHave = Math.min(q.end, Math.max(0, r.got)); }   // 서버가 실제로 받은 내 프레임 수
      else if (q.end > self.srvHave) self.srvHave = q.end;
      if (q.hashed && q.hashAt != null) self.hsent = Math.max(self.hsent, q.hashAt + 1);
      self._sigDone(q);
      if (Array.isArray(r.sig)) { for (var k = 0; k < r.sig.length; k++) self._sigIn(r.sig[k]); }
      if (typeof r.sig_next === 'number' && isFinite(r.sig_next)) self.sigN = r.sig_next;
      var opp = r.opp; if (Array.isArray(opp)) { var base = (typeof r.opp_from === 'number') ? r.opp_from : q.body.ack; self._fillOp(base, opp); }
      if (r.peer && typeof r.peer === 'object') self.status.peer = r.peer; else if (Array.isArray(r.names)) self.status.peer = { name: r.names[self.side ? 0 : 1] };
      if (typeof r.start_in === 'number') self.status.startIn = r.start_in;
      self.status.state = r.state || self.status.state;
      if (r.forfeit) self.status.forfeit = r.forfeit;
      if (r.state === 'void' || r.void) return self._end({ kind: 'void', reason: r.void || 'void', r: r });
      if (r.state === 'done' || r.result || r.forfeit) return self._end({ kind: 'done', forfeit: r.forfeit || null, result: r.result || null, r: r });
      if (self.localOver && !self.resultSent) {
        if (!self._needFlush()) { if (!self.resultReadyAt) self.resultReadyAt = now() + 400; if (now() >= self.resultReadyAt || now() - self.overAt > 5000) self._maybeResult(); }
      }
      return 0;
    });
  };
  P._fillOp = function (base, arr) {
    if (typeof base !== 'number' || !isFinite(base) || base < 0 || !arr) return;
    for (var i = 0; i < arr.length; i++) {
      var v = arr[i] | 0; if (v < 0 || v > 31) continue;
      var k = base + i; if (this.opIn[k] === undefined) this.opIn[k] = v;
    }
    while (this.opIn[this.ack] !== undefined) this.ack++;
  };
  P._fail = function (r) {
    var code = r && r.code, st = this.status;
    if (code === 'auth') return this._end({ kind: 'error', code: 'auth' });
    if (code === 'not_found' || code === 'closed' || code === 'not_member') return this._end({ kind: 'closed', code: code });
    if (!this.failSince) this.failSince = now();
    if (code !== 'busy') st.fails++;                        // 초당 한도에 걸린 것은 연결 문제가 아니다
    if (now() - this.failSince > NET.GIVEUP_AFTER) return this._end({ kind: 'lost' });
    return code === 'busy' ? 250 : 0;
  };
  P._end = function (info) {              // 끝은 한 번만 — 화면이 info.kind 로 안내를 고른다
    if (this.finished) return 0;
    this.finished = true; this.ended = info; this.stop();
    if (this.o.onEnd) { try { this.o.onEnd(info, this); } catch (e) { if (typeof console !== 'undefined') console.error(e); } }
    return 0;
  };
  // 로컬에서 15점이 나면 결과를 올린다(실패하면 다시). 양쪽 보고가 일치해야 서버가 기록에 반영한다.
  // 직결·묶음 전송에서는 판이 끝난 순간 서버가 아직 내 마지막 입력을 못 받았을 수 있다 — 남은 입력을 다 올린 뒤에 보고한다.
  P._maybeResult = function (force) {
    var self = this; if (!self.localOver || self.resultSent || self.finished) return;
    if (!force && self.srvHave < self.G.s.t && now() - self.overAt < 5000) return;
    self.resultSent = true; self.resultTries++;
    var s = self.G.s, me = s.score[self.side], op = s.score[self.side ? 0 : 1];
    call('/vb/result', { token: self.token, room: self.room, score: [me, op], frames: s.t }, { api: self.api, fetch: self.fetch }).then(function (r) {
      if (self.finished) return;
      if (!r || (r.ok === false && (r.code === 'net' || r.code === 'http' || r.code === 'busy' || r.code === 'bad'))) {
        if (self.resultTries < 10) setTimeout(function () { self.resultSent = false; }, 800); return;
      }
      self.resultResp = r; self.resultAt = now();
      if (r.ok === false) return self._end({ kind: 'void', reason: r.code || 'bad', r: r });
      if (r.void) return self._end({ kind: 'void', reason: r.void, r: r });
      if (r.applied || r.ranked === false || r.friendly) return self._end({ kind: 'done', result: r, forfeit: null });
      // pending — 상대 보고가 오면 sync 가 done 을 가져온다. 한계가 지나면 화면이 /vb/me 로 확인한다.
    });
  };
  P.waitedForResult = function () { return this.resultResp && this.resultResp.pending && now() - this.resultAt > NET.RESULT_WAIT; };
  P.claim = function () {                                     // 상대가 8초 넘게 조용할 때 기권승 요청(/vb/claim)
    var self = this; if (self.claiming || self.finished) return; self.claiming = true; self.claimMsg = '';
    call('/vb/claim', { token: self.token, room: self.room }, { api: self.api, fetch: self.fetch }).then(function (r) {
      self.claiming = false;
      if (r && r.ok && (r.state === 'done' || r.result)) self._end({ kind: 'done', forfeit: r.forfeit || 'opp', result: r.result || null, r: r });
      else self.claimMsg = (r && r.code) || 'fail';
    });
  };
  P.leave = function () { var self = this; self.stop(); return call('/vb/leave', { token: self.token, room: self.room }, { api: self.api, fetch: self.fetch }); };

  // ---------- WebRTC 직결 ----------
  // 신호(offer/answer/ICE)는 이미 도는 /vb/sync 의 sig 칸으로 오간다 — 새 엔드포인트도, 새 연결도 필요 없다.
  P._sig = function (t, obj) {
    if (this.stopped || this.finished) return;
    var d = (typeof obj === 'string') ? obj : JSON.stringify(obj);
    this.sigQ.push({ t: t, d: d });
    if (this.sigQ.length > NET.SIG_KEEP) this.sigQ.shift();
    if (this.p2p.state === 'try' || this.p2p.state === 'on') this._kick();     // 신호는 빨리 나가야 한다
  };
  P._sigDone = function (q) {                                // 성공한 요청이 실어 간 신호는 큐에서 뺀다
    if (!q || !q.sig) return;
    var k = this.sigFly.indexOf(q.sig); if (k >= 0) this.sigFly.splice(k, 1);
  };
  P._sigReturn = function (q, r) {                           // 못 나간 신호는 돌려 놓고 다음 요청에 다시 싣는다
    this._sigDone(q);
    if (!q || !q.sig) return;
    var miss = q.sig.filter(function (m) { return this.sigQ.indexOf(m) < 0; }, this);
    this.sigQ = miss.concat(this.sigQ);
    if (this.sigQ.length > NET.SIG_KEEP) this.sigQ = this.sigQ.slice(-NET.SIG_KEEP);
  };
  P._p2pStart = function () {
    if (this.pc || this.stopped || this.finished || !NET.P2P) return;
    var Ctor = pcCtor(); if (!Ctor) { this.p2p.state = 'off'; return; }
    var self = this, pc;
    try { pc = new Ctor({ iceServers: NET.STUN.map(function (u) { return { urls: u }; }) }); } catch (e) { this.p2p.state = 'off'; return; }
    this.pc = pc; this.p2p.state = 'try'; this.p2p.since = now(); this.p2p.tries++; this.status.p2p = 'try';
    pc.onicecandidate = function (e) { if (e && e.candidate) self._sig('c', { c: e.candidate.candidate, m: e.candidate.sdpMid, i: e.candidate.sdpMLineIndex }); };
    pc.onconnectionstatechange = function () { self._pcState(); };
    pc.oniceconnectionstatechange = function () { self._pcState(); };
    if (this.side === 0) {                                   // side 0 이 제안한다
      try { this.dc = pc.createDataChannel('vb', { ordered: true }); } catch (e) { try { this.dc = pc.createDataChannel('vb'); } catch (e2) { } }
      this._wireDc();
      pc.createOffer().then(function (o) { return pc.setLocalDescription(o); }).then(function () {
        var ld = pc.localDescription || {};
        if (String(ld.sdp || '').length > self.sigMax) return self._p2pGive('sdp');     // 신호 한 칸(5KB)을 넘으면 직결을 접는다
        self._sig('o', { type: ld.type || 'offer', sdp: ld.sdp || '' });
      }).catch(function () { self._p2pGive('offer'); });
    } else {
      pc.ondatachannel = function (e) { self.dc = e.channel; self._wireDc(); };
    }
    this._pingStart();
  };
  P._wireDc = function () {
    var self = this, dc = this.dc; if (!dc) return;
    dc.onopen = function () { self._p2pOn(); };
    dc.onclose = function () { self._p2pLost('close'); };
    dc.onmessage = function (e) { self._dcMsg(e && e.data); };
  };
  P._dcSend = function (o) {
    try { if (this.dc && this.dc.readyState === 'open') { this.dc.send(JSON.stringify(o)); return true; } } catch (e) { }
    return false;
  };
  P._iceFlush = function () {                                 // 모아 둔 후보를 원격 설명이 선 뒤에 넣는다
    var pc = this.pc, q = this.iceQ; this.iceQ = [];
    if (!pc) return;
    for (var i = 0; i < q.length; i++) { try { var r = pc.addIceCandidate(q[i]); if (r && r.catch) r.catch(function () { }); } catch (e) { } }
  };
  P._p2pOn = function () {
    if (this.p2p.state === 'on' || this.finished) return;
    this.p2p.state = 'on'; this.status.p2p = 'on'; this.p2p.opened = now(); this.dcLastAt = now(); this.status.p2pRtt = Math.round(this.p2p.rtt || 0);
    this._dcCatchup(); this._pingStart(); this._arm(0);        // 이제 서버 중계는 1초에 한 번으로
  };
  P._dcCatchup = function () {                                // 직결 전까지 쌓인 입력을 한 번에 밀어 준다
    var end = this.myIn.length, f = 0;
    if (end > 480) f = end - 480;
    while (f < end) { var n = Math.min(240, end - f); if (!this._dcSend({ t: 'i', f: f, b: this.myIn.slice(f, f + n) })) return; f += n; }
    this.dcNext = end;
  };
  P._dcFlush = function () {                                  // 아직 안 보낸 내 입력을 보낸다(보통 1프레임)
    if (this.p2p.state !== 'on') return;
    var end = this.myIn.length; if (end <= this.dcNext) return;
    var f = this.dcNext, n = Math.min(120, end - f), arr = this.myIn.slice(f, f + n);
    while (arr.length && arr[arr.length - 1] === undefined) arr.pop();
    if (!arr.length) return;
    if (this._dcSend({ t: 'i', f: f, b: arr })) this.dcNext = f + arr.length;
  };
  P._dcMsg = function (data) {
    var m; try { m = JSON.parse(String(data)); } catch (e) { return; }
    if (!m || typeof m !== 'object') return;
    this.dcLastAt = now();
    if (m.t === 'i') this._fillOp(m.f | 0, m.b);
    else if (m.t === 'r') { var f = m.f | 0; if (f >= 0 && this.myIn[f] !== undefined) this._dcSend({ t: 'i', f: f, b: [this.myIn[f]] }); }
    else if (m.t === 'p') this._dcSend({ t: 'q', v: m.v });
    else if (m.t === 'q') {
      var rt = now() - m.v; if (rt >= 0 && rt < 5000) { this.p2p.rtt = this.p2p.rtt ? this.p2p.rtt * 0.7 + rt * 0.3 : rt; this.status.p2pRtt = Math.round(this.p2p.rtt); }
    }
  };
  P._pingStart = function () {
    if (this.pingTimer || this.stopped) return;
    var self = this;
    this.pingTimer = setInterval(function () {
      if (self.finished || self.p2p.state !== 'on') return;
      self._dcSend({ t: 'p', v: now() });
    }, NET.P2P_PING);
  };
  P._pcState = function () {
    var pc = this.pc; if (!pc) return;
    var st = pc.connectionState || pc.iceConnectionState;
    if (st === 'failed') { if (this.p2p.state === 'try' && this.p2p.tries < 2 && this.side === 0) this._p2pRetry(); else this._p2pLost('failed'); }
    else if (st === 'closed') this._p2pLost('closed');
  };
  P._p2pRetry = function () {                                 // 한 번만 다시 제안해 본다(첫 제안이 ICMP 등으로 막힌 경우)
    this._p2pClose(); this.p2p.state = 'off'; this.status.p2p = 'off';
    var self = this; setTimeout(function () { if (!self.stopped && !self.finished && self.p2p.state !== 'on') self._p2pStart(); }, 500);
  };
  P._p2pGive = function (why) {                               // 연결이 안 되면 포기하고 서버 중계로만 간다
    if (this.p2p.state === 'on') return;
    this.p2p.state = 'off'; this.status.p2p = 'off'; this.p2p.why = why; this._p2pClose();
  };
  P._p2pLost = function (why) {                               // 도중에 끊겼다 → 서버 중계로 자동 복귀
    if (this.p2p.state !== 'on' && this.p2p.state !== 'try') return;
    this.p2p.state = 'lost'; this.status.p2p = 'lost'; this.p2p.why = why; this._p2pClose();
    this._arm(0);                                             // 곧바로 서버 중계(50ms)로
  };
  P._p2pClose = function () {
    if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
    var dc = this.dc, pc = this.pc; this.dc = null; this.pc = null; this.dcNext = 0; this.iceQ = []; this.farSdp = null;
    try { if (dc) dc.close(); } catch (e) { }
    try { if (pc) pc.close(); } catch (e) { }
  };
  P._timers = function () {                                   // tick 마다: 직결 시도가 너무 길어지면 접는다
    if (this.p2p.state === 'try' && now() - this.p2p.since > NET.P2P_TIMEOUT) this._p2pGive('timeout');
    if (this.p2p.state === 'on') {
      if (now() - (this.dcLastAt || 0) > NET.P2P_SILENT) { this._p2pLost('silent'); return; }   // 상대 쪽이 죽었다 — 서버 중계로
      this._dcFlush();
    }
  };
  P._sigIn = function (m) {
    var pc = this.pc; if (!pc || !m || typeof m !== 'object') return;
    var self = this, d;
    try { d = (typeof m.d === 'string') ? JSON.parse(m.d) : m.d; } catch (e) { return; }
    if (m.t === 'o') {
      if (this.side === 0 || !d || !d.sdp) return;
      if (this.farSdp === d.sdp) return;                     // 같은 offer 가 또 와도 한 번만(응답 유실 뒤 재전송)
      this.farSdp = d.sdp;
      var pr = null;
      try { pr = pc.setRemoteDescription({ type: 'offer', sdp: d.sdp }); } catch (e) { return; }
      Promise.resolve(pr).then(function () { self._iceFlush(); return pc.createAnswer(); }).then(function (a) { return pc.setLocalDescription(a); }).then(function () {
        var ld = pc.localDescription || {};
        if (String(ld.sdp || '').length > self.sigMax) return self._p2pGive('sdp');
        self._sig('a', { type: ld.type || 'answer', sdp: ld.sdp || '' });
      }).catch(function () { self._p2pGive('answer'); });
    } else if (m.t === 'a') {
      if (this.side !== 0 || !d || !d.sdp) return;
      if (this.farSdp === d.sdp) return;                      // 같은 설명이 두 번 와도(응답 유실 뒤 재전송) 한 번만
      this.farSdp = d.sdp;
      try {
        Promise.resolve(pc.setRemoteDescription({ type: 'answer', sdp: d.sdp })).then(function () { self._iceFlush(); }).catch(function () { self._p2pGive('answer'); });
      } catch (e) { this._p2pGive('answer'); }
    } else if (m.t === 'c') {
      if (!d) return;
      var cand = { candidate: d.c, sdpMid: d.m == null ? '0' : d.m, sdpMLineIndex: d.i == null ? 0 : d.i };
      if (!pc.remoteDescription) { if (this.iceQ.length < 60) this.iceQ.push(cand); return; }   // 설명이 오기 전 후보는 모아 둔다
      try { var r = pc.addIceCandidate(cand); if (r && r.catch) r.catch(function () { }); } catch (e) { }
    }
  };

  root.BrjVolleyNet = { Match: Match, NET: NET, API: API, call: call, beaconLeave: beaconLeave, TIERS: TIERS, tierInfo: tierInfo, tierByRating: tierByRating, enc: enc, dec: dec };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.BrjVolleyNet;
})(typeof window !== 'undefined' ? window : globalThis);
