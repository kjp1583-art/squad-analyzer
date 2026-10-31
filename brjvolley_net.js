/* 브장신 배구 온라인 — 락스텝 클라이언트 + 티어 표시 도우미 (DOM 없음, 화면과 시험이 같이 쓴다)
 *
 * 서버는 게임을 돌리지 않는다. 두 브라우저가 같은 시드·같은 입력으로 BrjVolley 를 똑같이 돌리고,
 * 서버는 입력 비트만 중계한다(비트: l=1 r=2 u=4 d=8 hit=16).
 *   프레임 f 의 내 입력은 f−D 번째 프레임을 돌릴 때 정해서 보낸다(입력 지연 D, 기본 6프레임=100ms).
 *   상대 입력이 아직 안 왔으면 그 프레임에서 멈추고(stalled) 오면 이어 간다.
 *   60프레임마다 상태 해시를 서버에 보내 어긋남(desync)을 잡는다.
 *
 * const m = BrjVolleyNet.Match({api, token, room, side, seed, target, ranked, onEnd(info), onLocalOver()});
 * m.start(); 매 프레임 m.tick(sampleBits) (한 프레임 돌았으면 1, 멈췄으면 0) · m.G 가 엔진 · m.status 가 연결 상태
 * m.leave() 기권 · m.claim() 기권승 요청 · m.stop()
 */
(function (root) {
  'use strict';
  var API = 'https://hth3thmujs.apps.bot-hosting.cloud';
  var NET = {
    D: 6,                 // 입력 지연(프레임) — 가정값. 시작 전에 잰 지연이 크면 D_MAX 까지 늘린다(내 쪽만)
    D_MAX: 12,
    PERIOD: 50,           // 경기 중 /vb/sync 간격(ms) = 20Hz
    IDLE_PERIOD: 250,     // 경기 전·후 간격
    OVERLAP: 12,          // 내 입력을 이만큼 겹쳐 다시 보낸다(손실 대비)
    MAX_FRAMES: 120,      // 요청 하나에 실을 프레임 상한(서버 상한과 같게)
    TIMEOUT: 3500,        // 요청 하나의 제한 시간
    KICK_GAP: 40,         // 멈춰 있을 때 앞당겨 부르는 최소 간격(ms)
    CLAIM_AFTER: 8000,    // 상대가 이만큼 멈춰 있으면 「기권승 요청」 버튼
    GIVEUP_AFTER: 20000,  // 서버와 이만큼 못 닿으면 포기하고 안내
    RESULT_WAIT: 20000    // 결과가 반영되길 기다리는 한계
  };
  function now() { return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now(); }
  function dec(b) { return { l: !!(b & 1), r: !!(b & 2), u: !!(b & 4), d: !!(b & 8), hit: !!(b & 16) }; }
  function enc(i) { return (i.l ? 1 : 0) | (i.r ? 2 : 0) | (i.u ? 4 : 0) | (i.d ? 8 : 0) | (i.hit ? 16 : 0); }

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
    this.ended = null; this.finished = false; this.stopped = false; this.playing = false; this.timer = null; this.inflight = false; this.sentCount = 0; this.reqCount = 0;
    this.status = { state: 'wait', rtt: 0, stalled: 0, canClaim: false, fails: 0, peer: null, startIn: null, forfeit: null, stallCount: 0 };
  }
  var P = Match.prototype;
  P.begin = function () {                                    // 카운트다운이 끝나 프레임을 돌려도 된다
    var want = Math.max(this.D, Math.min(NET.D_MAX, Math.ceil(((this.rtt || 0) * 0.5 + NET.PERIOD + 30) / 16.7)));   // 지연이 큰 망이면 입력 지연을 늘려 멈춤을 줄인다
    for (var i = this.D; i < want; i++) this.myIn.push(0);    // 늘어난 만큼 0 입력으로 메운다(아직 한 프레임도 안 돌렸다)
    this.D = want; this.playing = true;
  };
  P.tick = function (sample) {
    if (this.ended || this.localOver || !this.playing) return 0;
    var G = this.G, f = G.s.t;
    if (this.opIn[f] === undefined) {                          // 상대 입력 대기
      if (!this.stalledSince) { this.stalledSince = now(); this.status.stallCount++; }
      this.status.stalled = now() - this.stalledSince; this.status.canClaim = this.status.stalled >= NET.CLAIM_AFTER;
      this._kick();
      return 0;
    }
    this.stalledSince = 0; this.status.stalled = 0; this.status.canClaim = false;
    this.myIn[f + this.D] = sample() & 31;
    var mine = dec(this.myIn[f]), op = dec(this.opIn[f]);
    if (this.side === 0) G.step(mine, op); else G.step(op, mine);
    if (G.s.t % 60 === 0) { var h = { f: G.s.t, h: G.hash() }; this.hq.push(h); this.hashes.push(h); }
    if (G.s.phase === 'over') { this.localOver = true; if (this.o.onLocalOver) this.o.onLocalOver(this); }
    return 1;
  };
  P.start = function () { this._pump(); };
  P.stop = function () { this.stopped = true; if (this.timer) clearTimeout(this.timer); };
  P._period = function () { return (this.playing && !this.localOver) ? NET.PERIOD : NET.IDLE_PERIOD; };
  P._pump = function () {
    var self = this; if (self.stopped || self.inflight) return;
    var t0 = now(); self.inflight = true; self.lastSend = t0;
    self._sync().then(function (extra) {
      self.inflight = false;
      if (self.stopped) return;
      var wait = Math.max(0, self._period() - (now() - t0)) + (extra || 0);
      self.timer = setTimeout(function () { self._pump(); }, wait);
    });
  };
  // 상대 입력을 기다리며 멈춰 있으면 다음 정기 호출을 기다리지 않고 바로 한 번 더 부른다(서버 한도 초당 30 아래로: 40ms 간격)
  P._kick = function () {
    if (this.inflight || this.stopped || this.finished) return;
    if (now() - (this.lastSend || 0) < NET.KICK_GAP) return;
    if (this.timer) clearTimeout(this.timer); this._pump();
  };
  P._body = function () {
    var end = this.myIn.length, from = Math.max(0, Math.min(this.srvHave, end) - (this.hasGot ? 0 : NET.OVERLAP));
    if (end - from > NET.MAX_FRAMES) from = end - NET.MAX_FRAMES;
    var b = { token: this.token, room: this.room, from: from, inputs: this.myIn.slice(from, end), ack: this.ack };
    if (this.hsent < this.hq.length) b.hash = this.hq[this.hsent];
    return { body: b, end: end, hashed: !!b.hash };
  };
  P._sync = function () {
    var self = this;
    if (self.finished) return Promise.resolve();
    var q = self._body(), t0 = now(); self.reqCount++;
    return call('/vb/sync', q.body, { api: self.api, fetch: self.fetch }).then(function (r) {
      var rt = now() - t0;
      if (self.stopped) return 0;
      if (!r || r.ok === false) return self._fail(r);
      self.failSince = 0; self.lastOk = now(); self.status.fails = 0; self.rtt = self.rtt ? self.rtt * 0.8 + rt * 0.2 : rt; self.status.rtt = Math.round(self.rtt);
      if (typeof r.got === 'number') { self.hasGot = true; self.srvHave = Math.min(q.end, Math.max(0, r.got)); }   // 서버가 실제로 받은 내 프레임 수
      else if (q.end > self.srvHave) self.srvHave = q.end;
      if (q.hashed) self.hsent++;
      var opp = r.opp; if (Array.isArray(opp)) { var base = (typeof r.opp_from === 'number') ? r.opp_from : q.body.ack; for (var i = 0; i < opp.length; i++) { var v = opp[i] | 0; if (v >= 0 && v < 32 && self.opIn[base + i] === undefined) self.opIn[base + i] = v; } }
      while (self.opIn[self.ack] !== undefined) self.ack++;
      if (r.peer && typeof r.peer === 'object') self.status.peer = r.peer; else if (Array.isArray(r.names)) self.status.peer = { name: r.names[self.side ? 0 : 1] };
      if (typeof r.start_in === 'number') self.status.startIn = r.start_in;
      self.status.state = r.state || self.status.state;
      if (r.forfeit) self.status.forfeit = r.forfeit;
      if (r.state === 'void' || r.void) return self._end({ kind: 'void', reason: r.void || 'void', r: r });
      if (r.state === 'done' || r.result || r.forfeit) return self._end({ kind: 'done', forfeit: r.forfeit || null, result: r.result || null, r: r });
      self._maybeResult();
      return 0;
    });
  };
  P._fail = function (r) {
    var code = r && r.code, st = this.status;
    if (code === 'auth') return this._end({ kind: 'error', code: 'auth' });
    if (code === 'not_found' || code === 'closed' || code === 'not_member') return this._end({ kind: 'closed', code: code });
    if (!this.failSince) this.failSince = now();
    st.fails++;
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
  P._maybeResult = function () {
    var self = this; if (!self.localOver || self.resultSent || self.finished) return;
    self.resultSent = true; self.resultTries++;
    var s = self.G.s, me = s.score[self.side], op = s.score[self.side ? 0 : 1];
    call('/vb/result', { token: self.token, room: self.room, score: [me, op], frames: s.t }, { api: self.api, fetch: self.fetch }).then(function (r) {
      if (self.finished) return;
      if (!r || (r.ok === false && (r.code === 'net' || r.code === 'http' || r.code === 'busy'))) { if (self.resultTries < 8) setTimeout(function () { self.resultSent = false; }, 600); return; }
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

  root.BrjVolleyNet = { Match: Match, NET: NET, API: API, call: call, beaconLeave: beaconLeave, TIERS: TIERS, tierInfo: tierInfo, tierByRating: tierByRating, enc: enc, dec: dec };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.BrjVolleyNet;
})(typeof window !== 'undefined' ? window : globalThis);
