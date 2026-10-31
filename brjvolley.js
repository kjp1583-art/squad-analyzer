/* 브장신 배구 — 물리·규칙·CPU (DOM 없음, 화면과 시험이 같이 쓴다)
 * 병아리 둘이 네트를 사이에 두고 공을 주고받는다. 공이 자기 쪽 땅에 닿으면 상대 점수. 먼저 target(기본 15)점.
 * 이 파일은 직접 짠 것이다 — 원작(피카츄 배구)의 그림·소리·코드를 쓰지 않는다.
 *
 * const g = BrjVolley.create({seed:1, level:'normal'|'easy'|'hard'|null, target:15, p2cpu:true});
 * g.step(in1, in2)   in = {l,r,u,d,hit}  (hit 는 누른 순간 한 번만 먹는다 — 엔진이 가장자리를 본다)
 * g.s                상태: {ball:{x,y,vx,vy,spin}, p:[{x,y,vy,side,pose,...},{...}], score:[a,b], phase, server, winner, t, ev:[...]}
 * g.hash()           상태 해시(정수 32비트) · g.dump() 정수 배열 — 온라인 락스텝이 어긋남을 잡는 데 쓴다. 시뮬레이션 경로에는 Math.random·Date·삼각함수가 없다(CPU AI 는 예외, 온라인에서는 안 쓴다)
 * g.cpuInput(i[,level])  i 번 선수(0|1)의 CPU 입력(level 로 난이도를 따로 줄 수 있다)
 * 이벤트(g.s.ev, 매 step 마다 비워짐): 'hit' 'spike' 'dig' 'wall' 'net' 'bounce' 'point'{side} 'serve' 'win'{side}
 */
(function (root) {
  'use strict';
  var W = 432, H = 264, GROUND = 244, NET_X = 216, NET_HW = 4, NET_TOP = GROUND - 96;
  var BR = 16, PR = 22, PCY = 24, SUB = 3;                       // 공 반지름 · 선수 머리 원 반지름 · 발에서 원 중심까지
  var G_BALL = 0.24, G_P = 0.5, JUMP = 9.4, SPEED = 3.7, VMAX = 9.2, SPIKE_V = 9.0, DIG_V = 8.2;   // 원작 느낌: 공이 천천히 떠 있다 떨어진다(1프레임 = 1/60초)
  var POINT_T = 75, READY_T = 45;
  // 때리기 각도 표 [cos, sin] — 지상 −60° · 강타 위 −34° · 앞 12° · 아래 40° · 아래+앞 50° · 아래+뒤 32°. (옛 Math.cos/sin 값을 그대로 옮긴 것: 동작은 같다)
  var SPK = { g: [0.5000000000000001, -0.8660254037844386], u: [0.8290375725550416, -0.5591929034707469], f: [0.9781476007338057, 0.20791169081775931], d: [0.766044443118978, 0.6427876096865393], df: [0.6427876096865394, 0.766044443118978], bk: [0.848048096156426, 0.5299192642332049] };
  var PHASE = { ready: 1, rally: 2, point: 3, over: 4 };
  var LV = { easy: { delay: 16, err: 44, spd: 0.72, jump: 0.55, spike: 0.35 }, normal: { delay: 8, err: 24, spd: 0.88, jump: 0.8, spike: 0.6 }, hard: { delay: 3, err: 9, spd: 1.0, jump: 1.0, spike: 0.9 } };

  function rng(seed) { var a = (seed >>> 0) || 1; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  function create(o) {
    o = o || {};
    var R = rng(o.seed || 1), target = o.target || 15;
    var s = {
      ball: { x: 108, y: 70, vx: 0, vy: 0, spin: 0, cool: 0 },
      p: [mk(0), mk(1)], score: [0, 0], phase: 'ready', timer: READY_T, server: 0, winner: -1, t: 0, ev: [], rally: 0, target: target, lastHit: -1, shake: 0
    };
    function mk(side) { return { side: side, x: side ? 324 : 108, y: GROUND, vy: 0, vx: 0, pose: 'idle', poseT: 0, hitLock: 0, prevHit: false, face: side ? -1 : 1 }; }
    var ai = [{ tx: 108, ct: 0, hist: [] }, { tx: 324, ct: 0, hist: [] }];
    var g = { s: s, W: W, H: H, GROUND: GROUND, NET_X: NET_X, NET_TOP: NET_TOP, BR: BR, PR: PR, PCY: PCY };

    function emit(t, d) { var e = { t: t }; if (d) for (var k in d) e[k] = d[k]; s.ev.push(e); }
    function serveSetup() {
      var b = s.ball, sx = s.server ? 324 : 108;
      b.x = sx; b.y = 80; b.vx = 0; b.vy = 0; b.spin = 0; b.cool = 0; s.rally = 0; s.lastHit = -1;
      s.p[0].x = 108; s.p[1].x = 324; s.p[0].y = s.p[1].y = GROUND; s.p[0].vy = s.p[1].vy = 0;
    }
    g.reset = function () { s.score[0] = s.score[1] = 0; s.winner = -1; s.server = 0; s.phase = 'ready'; s.timer = READY_T; s.t = 0; serveSetup(); };

    // ---------- 선수 ----------
    function movePlayer(p, inp) {
      var lo = p.side ? NET_X + NET_HW + PR : PR, hi = p.side ? W - PR : NET_X - NET_HW - PR;
      var dir = (inp.r ? 1 : 0) - (inp.l ? 1 : 0), sp = SPEED * (inp.spd || 1);
      p.vx = dir * sp; p.x = clamp(p.x + p.vx, lo, hi);
      if (dir) p.face = dir;
      if (p.y >= GROUND && inp.u && p.vy === 0) { p.vy = -JUMP; }
      if (p.y < GROUND || p.vy < 0) { p.vy += G_P; p.y += p.vy; if (p.y >= GROUND) { p.y = GROUND; p.vy = 0; } }
      p.poseT = Math.max(0, p.poseT - 1); if (!p.poseT) p.pose = p.y < GROUND ? 'jump' : 'idle';
      p.hitLock = Math.max(0, p.hitLock - 1);
    }
    // ---------- 공 ↔ 선수 ----------
    function hitCheck(p, inp, idx) {                               // 때리기 버튼(강타·받아치기) — 누른 순간 한 번
      var b = s.ball, cx = p.x, cy = p.y - PCY, dx = b.x - cx, dy = b.y - cy, d = Math.sqrt(dx * dx + dy * dy), R = PR + BR;
      var wantHit = inp.hit && !p.prevHit && p.hitLock === 0; p.prevHit = !!inp.hit;
      if (!(wantHit && d < R + 12 && b.cool === 0)) return;
      var fwd = p.side ? -1 : 1, air = p.y < GROUND - 6, k;        // 앞쪽 기준 각도(위가 −) — 삼각함수 대신 상수 표(엔진마다 결과가 다를 수 있어서)
      if (air) { k = inp.d ? 'd' : inp.u ? 'u' : 'f'; if (inp.d && (p.side ? inp.l : inp.r)) k = 'df'; else if (inp.d && (p.side ? inp.r : inp.l)) k = 'bk'; }
      else k = 'g';
      var v = air ? SPIKE_V : DIG_V, cs = SPK[k];
      b.vx = cs[0] * v * fwd; b.vy = cs[1] * v;
      if (!air && !(inp.l || inp.r)) b.vx *= 0.8;
      b.spin = fwd * 0.3; b.cool = 8; p.hitLock = 16; p.pose = 'hit'; p.poseT = 12; s.lastHit = idx; s.rally++; s.shake = air ? 6 : 2;
      var sd = d > 0.01 ? d : 1, push = R - sd; if (push > 0) { b.x += dx / sd * push; b.y += dy / sd * push; }
      emit(air ? 'spike' : 'dig', { x: b.x, y: b.y, side: p.side });
    }
    function resolve(p, idx) {                                     // 몸(머리 원)과의 물리 충돌 — 서브스텝마다
      var b = s.ball, cx = p.x, cy = p.y - PCY, dx = b.x - cx, dy = b.y - cy, d = Math.sqrt(dx * dx + dy * dy), R = PR + BR;
      if (d >= R || d < 0.0001) return;
      var nx = dx / d, ny = dy / d, rvx = b.vx - p.vx, rvy = b.vy - p.vy, vn = rvx * nx + rvy * ny;
      b.x = cx + nx * R; b.y = cy + ny * R;
      if (vn < 0 && b.cool === 0) {                                // 상대속도의 법선 성분을 반사(반발 0.9) — 선수 속도가 공에 실린다
        b.vx = p.vx + (rvx - 1.9 * vn * nx); b.vy = p.vy + (rvy - 1.9 * vn * ny);
        if (ny < -0.3 && b.vy > -3.6) b.vy = -3.6 + Math.min(0, p.vy * 0.3);   // 머리로 받으면 살짝 뜬다
        if (s.lastHit !== idx) s.rally++;
        s.lastHit = idx; b.cool = 3; emit('hit', { x: b.x, y: b.y, side: p.side }); p.pose = 'hit'; p.poseT = 8;
      }
    }
    // ---------- 공 ----------
    function moveBall() {
      var b = s.ball; if (b.cool > 0) b.cool--;
      b.vy += G_BALL; var sp = Math.sqrt(b.vx * b.vx + b.vy * b.vy); if (sp > VMAX) { b.vx *= VMAX / sp; b.vy *= VMAX / sp; }
      b.spin = b.spin * 0.99 + b.vx * 0.01;
    }
    function integrate() { var b = s.ball; b.x += b.vx / SUB; b.y += b.vy / SUB; bounds(); }
    function bounds() {
      var b = s.ball;
      if (b.x < BR) { b.x = BR; b.vx = Math.abs(b.vx) * 0.9; emit('wall'); }
      if (b.x > W - BR) { b.x = W - BR; b.vx = -Math.abs(b.vx) * 0.9; emit('wall'); }
      if (b.y < BR) { b.y = BR; b.vy = Math.abs(b.vy) * 0.8; }
      // 네트(막대): 가장 가까운 점과의 거리
      var nx0 = NET_X - NET_HW, nx1 = NET_X + NET_HW, cx = clamp(b.x, nx0, nx1), cy = clamp(b.y, NET_TOP, GROUND), dx = b.x - cx, dy = b.y - cy, d2 = dx * dx + dy * dy;
      if (d2 < BR * BR) {
        var d = Math.sqrt(d2);
        if (d < 0.001) { dx = b.x < NET_X ? -1 : 1; dy = 0; d = 1; }
        var nx = dx / d, ny = dy / d; b.x = cx + nx * BR; b.y = cy + ny * BR;
        var vn = b.vx * nx + b.vy * ny; if (vn < 0) { b.vx -= 1.8 * vn * nx; b.vy -= 1.8 * vn * ny; b.vx *= 0.85; emit('net'); }
      }
      var sp = Math.sqrt(b.vx * b.vx + b.vy * b.vy); if (sp > VMAX) { b.vx *= VMAX / sp; b.vy *= VMAX / sp; }
    }
    function pointFor(side) {
      s.score[side]++; s.server = side; s.phase = 'point'; s.timer = POINT_T; emit('point', { side: side, x: s.ball.x });
      if (s.score[side] >= s.target) { s.winner = side; s.phase = 'over'; emit('win', { side: side }); }
    }
    function noHit(i) { return { l: i.l, r: i.r, u: i.u, d: i.d, hit: false }; }
    g.step = function (in1, in2) {
      in1 = in1 || {}; in2 = in2 || {}; s.t++; s.ev.length = 0; s.shake = Math.max(0, s.shake - 0.5);
      if (s.phase === 'over') { movePlayer(s.p[0], {}); movePlayer(s.p[1], {}); return s; }
      if (s.phase === 'point') {
        moveBall(); for (var q = 0; q < SUB; q++) integrate(); var b = s.ball; if (b.y > GROUND - BR) { b.y = GROUND - BR; b.vy = -Math.abs(b.vy) * 0.4; b.vx *= 0.9; }
        movePlayer(s.p[0], noHit(in1)); movePlayer(s.p[1], noHit(in2));
        if (--s.timer <= 0) { s.phase = 'ready'; s.timer = READY_T; serveSetup(); emit('serve', { side: s.server }); }
        return s;
      }
      if (s.phase === 'ready') {
        movePlayer(s.p[0], in1); movePlayer(s.p[1], in2);
        if (--s.timer <= 0) s.phase = 'rally';
        return s;
      }
      movePlayer(s.p[0], in1); movePlayer(s.p[1], in2);
      hitCheck(s.p[0], in1, 0); hitCheck(s.p[1], in2, 1);
      moveBall();
      for (var q = 0; q < SUB; q++) { integrate(); resolve(s.p[0], 0); resolve(s.p[1], 1); bounds(); }   // 서브스텝: 빠른 공도 몸·네트를 뚫지 않는다
      var b2 = s.ball;
      if (b2.y + BR >= GROUND) {                                   // 땅에 닿았다 → 닿은 쪽의 상대 점수
        b2.y = GROUND - BR; b2.vy = -Math.abs(b2.vy) * 0.5; emit('bounce', { x: b2.x });
        pointFor(b2.x < NET_X ? 1 : 0);
      }
      return s;
    };

    // ---------- CPU ----------
    function landing(b) {                                           // 공이 선수 머리 높이(땅 − 60)에 올 때의 x, 걸리는 프레임
      var x = b.x, y = b.y, vx = b.vx, vy = b.vy, t = 0, ty = GROUND - 48;
      for (var i = 0; i < 240; i++) {
        vy += G_BALL; x += vx; y += vy; t++;
        if (x < BR) { x = BR; vx = Math.abs(vx) * 0.9; } if (x > W - BR) { x = W - BR; vx = -Math.abs(vx) * 0.9; }
        if (Math.abs(x - NET_X) < NET_HW + BR && y > NET_TOP - 4) { vx = -vx * 0.7; x += vx; }
        if (y >= ty && vy > 0) return { x: x, t: t };
      }
      return { x: x, t: t };
    }
    g.cpuInput = function (i, lvl) {
      lvl = lvl || o.level; var p = s.p[i], a = ai[i], lvn = lvl && LV[lvl] ? LV[lvl] : LV.normal, out = { l: false, r: false, u: false, d: false, hit: false, spd: lvn.spd };
      var rb = s.ball; a.hist.push({ x: rb.x, y: rb.y, vx: rb.vx, vy: rb.vy }); if (a.hist.length > 40) a.hist.shift();
      var b = a.hist[Math.max(0, a.hist.length - 1 - lvn.delay)];     // 반응 지연: 몇 프레임 전의 공을 본다
      var mine = p.side ? 1 : 0, ownSide = function (x) { return mine ? x > NET_X : x < NET_X; };
      var home = p.side ? 324 : 108;
      if (s.phase === 'ready' && s.server === i) { out.u = s.timer < 10 && R() < 0.5; a.tx = s.ball.x; }
      else if (s.phase === 'point' || s.phase === 'over') a.tx = home;
      else {
        var L = landing(b), comingMine = ownSide(L.x) || ownSide(b.x);
        if (--a.ct <= 0) { a.ct = 6; var err = (R() - 0.5) * 2 * lvn.err; a.tx = comingMine ? L.x + (mine ? 20 : -20) * (b.vy > 0 ? 1 : 0.4) + err : home + (R() - 0.5) * 30; }
        // 점프·강타
        var dx = rb.x - p.x, dy = (p.y - PCY) - rb.y;
        if (comingMine && Math.abs(dx) < 40 && rb.y < GROUND - 52 && rb.y > 40 && p.y >= GROUND && L.t < 34 && R() < lvn.jump * 0.9) out.u = true;
        if (comingMine && p.y < GROUND - 4 && Math.hypot(dx, rb.y - (p.y - PCY)) < PR + BR + 8 && p.hitLock === 0 && R() < lvn.spike) {
          // 네트를 넘기는 각도 중 가장 가파른 것을(어려울수록) 고른다 — 넘기지 못하는 강타는 안 친다
          var fw = mine ? -1 : 1, opts = [[{ u: true }, -38], [{}, 14], [{ d: true }, 42], [{ d: true, fw: true }, 52], [{ d: true, bk: true }, 34]], ok = [];
          for (var k = 0; k < opts.length; k++) { var ang = opts[k][1] * Math.PI / 180, vx = Math.cos(ang) * SPIKE_V * fw, vy = Math.sin(ang) * SPIKE_V; var tt = (NET_X - rb.x) / vx; if (tt <= 0) continue; var yy = rb.y + vy * tt + 0.5 * G_BALL * tt * tt; if (yy < NET_TOP - BR - 4) ok.push(opts[k]); }
          if (ok.length) {
            var pick = ok[0]; for (var q = 1; q < ok.length; q++) if (ok[q][1] > pick[1] && R() < 0.35 + 0.65 * lvn.spike) pick = ok[q];
            out.hit = true; var f = pick[0]; out.u = !!f.u; out.d = !!f.d; if (f.fw) { if (mine) out.l = true; else out.r = true; } if (f.bk) { if (mine) out.r = true; else out.l = true; }
          }
        }
        else if (comingMine && p.y >= GROUND && Math.hypot(dx, rb.y - (p.y - PCY)) < PR + BR + 6 && rb.y > GROUND - 70 && R() < lvn.spike * 0.8) out.hit = true;
      }
      if (a.tx - p.x > 6) out.r = true; else if (a.tx - p.x < -6) out.l = true;
      return out;
    };
    // ---------- 상태 해시(온라인 어긋남 감지) ----------
    // 시뮬레이션 값을 정수로 바꿔(×1024 반올림) 섞는다. 온라인에서는 두 브라우저가 같은 프레임에서 같은 값을 내야 한다.
    g.dump = function () {
      var b = s.ball, q = function (v) { return Math.round(v * 1024) | 0; }, a = [q(b.x), q(b.y), q(b.vx), q(b.vy), q(b.spin), b.cool | 0];
      for (var i = 0; i < 2; i++) { var p = s.p[i]; a.push(q(p.x), q(p.y), q(p.vy), q(p.vx), p.hitLock | 0, p.poseT | 0, p.face | 0, p.prevHit ? 1 : 0); }
      a.push(s.score[0], s.score[1], PHASE[s.phase] | 0, s.timer | 0, s.server | 0, s.t | 0, s.rally | 0, s.lastHit | 0, s.winner | 0);
      return a;
    };
    g.hash = function () { var a = g.dump(), h = 0x811c9dc5; for (var i = 0; i < a.length; i++) h = Math.imul(h ^ (a[i] | 0), 16777619) >>> 0; return h; };
    g.serveBall = function () { };
    serveSetup();
    return g;
  }
  root.BrjVolley = { create: create, BR: BR, PR: PR, PCY: PCY, W: W, H: H, GROUND: GROUND, NET_X: NET_X, NET_TOP: NET_TOP, LEVELS: Object.keys(LV) };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.BrjVolley;
})(typeof window !== 'undefined' ? window : globalThis);
