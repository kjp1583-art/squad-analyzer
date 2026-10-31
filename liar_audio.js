/* liar_audio.js — 라이어 게임 BGM + 효과음 (전부 Web Audio 합성 · 외부 음원 없음)
 *
 * 전역 LiarAudio:
 *   unlock()           첫 터치/클릭에서 부른다(그 전에는 AudioContext 도 만들지 않는다). 잠금 전의 bgm() 요청은 기억했다가 시작한다.
 *   bgm(name|null)     lobby · reveal · hints · discuss · vote · guess · result · win · lose. 바꾸면 1.6초 크로스페이드.
 *   tension(0..1)      긴장도 — discuss 는 현이 밝아지고, vote 는 심장 박동이 빨라지고 노이즈가 차오른다.
 *   sfx(name)          chair flip point thud bell tick flicker silence stingCit stingLiar hitLiar win liarWin points ding
 *   voice(name,text)   발표 음성 한 조각(seg1 「그는 라이어가」 · yes 「맞습니다」 · no 「아닙니다」). audio/liar_<name>.ogg 를 쓰고, 파일이 없으면
 *                      브라우저 음성(speechSynthesis, 낮은 음정·느리게)+합성 저음으로 대신한다. 길이(초)를 돌려준다.
 *   voiceDur(name)     그 조각의 길이(초) — 파일이 있으면 실제 길이, 없으면 기본값. voiceMode() = 'file'|'speech'|'synth'
 *   setVolume(0..1) · setMuted(bool) · volume() · muted() · state()
 *   _render(spec)      시험용: OfflineAudioContext 로 같은 합성 코드를 돌려 파형(Float32Array)을 돌려준다.
 * 소리 길: (BGM 버스 → 덕킹) + 효과음 버스 → 리버브 보내기 → 컴프레서 → 고역통과(직류 제거) → 마스터 → tanh 소프트 리미터 → 출력.
 * 탭이 숨겨지면 AudioContext 를 멈춘다(스케줄러도 같이 멈춘다).
 */
(function (global) {
  'use strict';
  var AC = global.AudioContext || global.webkitAudioContext;
  var OAC = global.OfflineAudioContext || global.webkitOfflineAudioContext;
  var XFADE = 1.6, LOOK = 0.45;
  var vol = 0.7, mutedF = false, rt = null, wanted = null, tens = 0, pumpTimer = 0;

  function mtof(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  function mulberry(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  var LIMIT = (function () { var n = 2049, c = new Float32Array(n); for (var i = 0; i < n; i++) { var u = i / (n - 1) * 2 - 1; c[i] = 0.95 * Math.tanh(2 * u / 0.95); } return c; })();

  /* ---------- 엔진 ---------- */
  function makeEngine(ctx, offline) {
    var e = { ctx: ctx, offline: !!offline, rnd: offline ? mulberry(7) : Math.random, runners: [], cur: null, tension: 0 };
    e.bgmBus = ctx.createGain(); e.sfxBus = ctx.createGain(); e.duck = ctx.createGain();
    e.pre = ctx.createGain(); e.comp = ctx.createDynamicsCompressor();
    try { e.comp.threshold.value = -18; e.comp.knee.value = 14; e.comp.ratio.value = 4; e.comp.attack.value = 0.01; e.comp.release.value = 0.25; } catch (x) { }
    e.hp = ctx.createBiquadFilter(); e.hp.type = 'highpass'; e.hp.frequency.value = 22;
    e.master = ctx.createGain(); e.lim = ctx.createWaveShaper(); e.lim.curve = LIMIT;
    e.rev = ctx.createConvolver(); e.rev.buffer = impulse(ctx, 2.3, e.rnd); e.revIn = ctx.createGain(); e.revOut = ctx.createGain(); e.revIn.gain.value = 0.34; e.revOut.gain.value = 0.8;
    e.bgmBus.connect(e.duck); e.duck.connect(e.pre); e.sfxBus.connect(e.pre);
    e.bgmBus.connect(e.revIn); e.sfxBus.connect(e.revIn); e.revIn.connect(e.rev); e.rev.connect(e.revOut); e.revOut.connect(e.pre);
    e.pre.connect(e.comp); e.comp.connect(e.hp); e.hp.connect(e.master); e.master.connect(e.lim); e.lim.connect(ctx.destination);
    e.bgmBus.gain.value = 0.6; e.sfxBus.gain.value = 1.0; e.master.gain.value = offline ? 0.8 : 0;
    var n = ctx.sampleRate * 2, b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0); for (var i = 0; i < n; i++) d[i] = e.rnd() * 2 - 1; e.nbuf = b;
    return e;
  }
  function impulse(ctx, sec, rnd) {
    var sr = ctx.sampleRate, n = Math.floor(sr * sec), b = ctx.createBuffer(2, n, sr);
    for (var c = 0; c < 2; c++) { var d = b.getChannelData(c); for (var i = 0; i < n; i++) { var k = i / n; d[i] = (rnd() * 2 - 1) * Math.pow(1 - k, 2.6) * (k < 0.004 ? k / 0.004 : 1); } }
    return b;
  }
  /* 기본 도구 */
  function env(g, t, a, peak, dur, floor) { floor = floor || 0.0001; g.gain.setValueAtTime(floor, t); g.gain.exponentialRampToValueAtTime(Math.max(peak, floor * 2), t + a); g.gain.exponentialRampToValueAtTime(floor, t + dur); }
  function osc(e, bus, o) {   // 한 음: {f, t, dur, type, vol, a, lp, f2(끝 주파수), det}
    var c = e.ctx, ov = c.createOscillator(), g = c.createGain(), t = o.t, a = o.a == null ? 0.01 : o.a, dur = o.dur;
    ov.type = o.type || 'sine'; ov.frequency.setValueAtTime(o.f, t); if (o.f2) ov.frequency.exponentialRampToValueAtTime(o.f2, t + dur); if (o.det) ov.detune.value = o.det;
    env(g, t, a, o.vol == null ? 0.1 : o.vol, dur); var out = ov;
    if (o.lp) { var lf = c.createBiquadFilter(); lf.type = 'lowpass'; lf.frequency.value = o.lp; ov.connect(lf); out = lf; }
    out.connect(g); g.connect(bus); ov.start(t); ov.stop(t + dur + 0.05); return ov;
  }
  function nz(e, bus, o) {   // 필터 거친 노이즈: {t, dur, type, f0, f1, q, vol, a}
    var c = e.ctx, s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain(), t = o.t;
    s.buffer = e.nbuf; s.loop = true; f.type = o.type || 'bandpass'; f.Q.value = o.q || 1; f.frequency.setValueAtTime(o.f0, t); if (o.f1) f.frequency.exponentialRampToValueAtTime(o.f1, t + o.dur);
    env(g, t, o.a == null ? 0.005 : o.a, o.vol == null ? 0.1 : o.vol, o.dur); s.connect(f); f.connect(g); g.connect(bus); s.start(t, e.rnd() * 1.5); s.stop(t + o.dur + 0.05);
  }
  function drone(r, f, type, vol, lp, lfoHz, lfoDepth) {   // 계속 울리는 소리(트랙 소유 · 트랙이 끝나면 멈춘다)
    var e = r.e, c = e.ctx, o = c.createOscillator(), g = c.createGain(), t = r.t0; o.type = type; o.frequency.value = f; g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol, t + 2.5);
    var out = o; if (lp) { var lf = c.createBiquadFilter(); lf.type = 'lowpass'; lf.frequency.value = lp; o.connect(lf); out = lf; r.lp = r.lp || []; r.lp.push(lf); }
    out.connect(g); g.connect(r.gain);
    if (lfoHz) { var l = c.createOscillator(), lg = c.createGain(); l.frequency.value = lfoHz; lg.gain.value = vol * (lfoDepth || 0.5); l.connect(lg); lg.connect(g.gain); l.start(t); r.nodes.push(l); }
    o.start(t); r.nodes.push(o); return g;
  }

  /* ---------- 트랙 ---------- */
  var TRACKS = {};
  TRACKS.lobby = {   // 은은하고 어둡고 차분한 앰비언트
    init: function (r) { [110, 164.8, 220, 261.6].forEach(function (f, i) { drone(r, f, i === 3 ? 'triangle' : 'sine', 0.05, 700, 0.045 + i * 0.017, 0.7); }); r.pent = [69, 72, 74, 76, 79, 81]; },
    step: function (r, t) { var e = r.e, m = r.pent[Math.floor(e.rnd() * r.pent.length)]; osc(e, r.gain, { f: mtof(m), t: t, dur: 3.2, vol: 0.05, a: 0.03, lp: 2400 }); osc(e, r.gain, { f: mtof(m - 12), t: t, dur: 2.2, vol: 0.03, a: 0.05, type: 'triangle' }); return 2.6 + e.rnd() * 3; }
  };
  TRACKS.reveal = {   // 저음 드론 + 불길한 떨림
    init: function (r) { drone(r, 36.7 * 2, 'sawtooth', 0.07, 220, 0.3, 0.6); drone(r, 36.7, 'sine', 0.12, 0, 0.12, 0.3); drone(r, 103.8, 'sine', 0.035, 0, 0.2, 0.8); drone(r, 311, 'sine', 0.012, 0, 0.09, 0.9); },
    step: function (r, t) { var e = r.e; nz(e, r.gain, { t: t, dur: 3.4, type: 'bandpass', f0: 500, f1: 1800, q: 4, vol: 0.012, a: 1.5 }); return 3.5; }
  };
  TRACKS.hints = {   // 느린 저음 오스티나토 + 시계 같은 미세 틱
    init: function (r) { drone(r, 36.7, 'sine', 0.05, 0, 0.07, 0.4); r.bass = [38, -1, 38, 41, -1, 33, -1, 36]; },
    step: function (r, t, i) {
      var e = r.e, st = 0.47, m = r.bass[i % 8];
      if (m > 0) { osc(e, r.gain, { f: mtof(m), t: t, dur: 0.55, vol: 0.2, a: 0.012, type: 'triangle', lp: 420 }); osc(e, r.gain, { f: mtof(m), t: t, dur: 0.5, vol: 0.12, a: 0.012 }); }
      if (i % 2 === 0) osc(e, r.gain, { f: i % 8 === 0 ? 3600 : 2900, t: t, dur: 0.03, vol: i % 8 === 0 ? 0.03 : 0.018, a: 0.002 });
      return st;
    }
  };
  TRACKS.discuss = {   // 점점 쌓이는 긴장: 서스펜스 현 느낌 패드 + 저음 맥박
    init: function (r) { r.pads = []; [[146.8, 0], [220, 6], [349.2, -5], [233.1, 4]].forEach(function (p, i) { var g = drone(r, p[0], 'sawtooth', 0.022, 600, 0.05 + i * 0.013, 0.8); r.pads.push(g); if (r.nodes.length) { r.nodes[r.nodes.length - 1].detune.value = p[1]; } }); },
    tune: function (r, tn) { for (var i = 0; i < r.lp.length; i++) r.lp[i].frequency.setTargetAtTime(500 + tn * 1800, r.e.ctx.currentTime, 0.6); },
    step: function (r, t, i) {
      var e = r.e, tn = e.tension, bpm = 66 + tn * 36, st = 60 / bpm / 2;
      if (i % 2 === 0) osc(e, r.gain, { f: mtof(i % 8 === 0 ? 38 : 38), t: t, dur: 0.4, vol: 0.14 + tn * 0.1, a: 0.01, type: 'triangle', lp: 300 });
      if (tn > 0.35 && i % 8 === 4) osc(e, r.gain, { f: mtof(75 + (i % 16 === 4 ? 0 : -1)), t: t, dur: 2.2, vol: 0.02 + 0.03 * tn, a: 0.4, lp: 3000 });   // 반음으로 부딪히는 높은 음
      if (tn > 0.7 && i % 4 === 1) osc(e, r.gain, { f: 3300, t: t, dur: 0.04, vol: 0.02, a: 0.002 });
      return st;
    }
  };
  TRACKS.vote = {   // 심장 박동 + 차오르는 노이즈 · 마감이 다가오면 박동이 빨라진다
    init: function (r) {
      var e = r.e, c = e.ctx, s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain(); s.buffer = e.nbuf; s.loop = true; f.type = 'bandpass'; f.Q.value = 3; f.frequency.value = 400; g.gain.value = 0.0001;
      s.connect(f); f.connect(g); g.connect(r.gain); s.start(r.t0); r.nodes.push(s); r.nf = f; r.ng = g;
      drone(r, 55, 'sine', 0.08, 0, 0.1, 0.4); r.dis = drone(r, 58.3, 'sine', 0.0001, 0, 0.15, 0);
    },
    tune: function (r, tn) { var t = r.e.ctx.currentTime; r.nf.frequency.setTargetAtTime(300 + tn * 3200, t, 0.3); r.ng.gain.setTargetAtTime(0.004 + tn * 0.07, t, 0.3); r.dis.gain.setTargetAtTime(tn * 0.07, t, 0.5); },
    step: function (r, t) {
      var e = r.e, tn = e.tension, per = 0.98 - tn * 0.6;
      osc(e, r.gain, { f: 95, f2: 42, t: t, dur: 0.22, vol: 0.5, a: 0.006 }); osc(e, r.gain, { f: 190, f2: 80, t: t, dur: 0.1, vol: 0.12, a: 0.004, type: 'triangle' });
      osc(e, r.gain, { f: 85, f2: 40, t: t + per * 0.26, dur: 0.18, vol: 0.34, a: 0.006 });
      return per;
    }
  };
  TRACKS.guess = {   // 한 음씩 떨어지는 긴장
    init: function (r) { drone(r, 73.4, 'sine', 0.07, 0, 0.1, 0.5); r.seq = [74, 72, 69, 67, 65, 62]; },
    step: function (r, t, i) {
      var e = r.e, m = r.seq[i % r.seq.length] + 12 - (Math.floor(i / r.seq.length) % 2) * 0;
      osc(e, r.gain, { f: mtof(m), t: t, dur: 3, vol: 0.09, a: 0.01 }); osc(e, r.gain, { f: mtof(m) * 2.76, t: t, dur: 1.2, vol: 0.025, a: 0.005 });
      if (i % r.seq.length === r.seq.length - 1) return 3.6; return 1.9;
    }
  };
  TRACKS.result = {   // 정적에 가까운 낮은 울림
    init: function (r) { drone(r, 55, 'sine', 0.08, 0, 0.08, 0.5); drone(r, 82.4, 'sine', 0.03, 0, 0.11, 0.6); },
    step: function () { return 4; }
  };
  TRACKS.win = {   // 따뜻한 화음 + 반짝이는 소리
    init: function (r) { [130.8, 164.8, 196, 261.6, 329.6].forEach(function (f, i) { drone(r, f, i % 2 ? 'triangle' : 'sine', 0.04, 1200, 0.06 + i * 0.01, 0.4); }); r.pent = [72, 74, 76, 79, 81, 84]; },
    step: function (r, t) { var e = r.e, m = r.pent[Math.floor(e.rnd() * r.pent.length)]; osc(e, r.gain, { f: mtof(m), t: t, dur: 2, vol: 0.05, a: 0.01 }); return 0.7 + e.rnd() * 0.9; }
  };
  TRACKS.lose = {   // 불협: 낮은 클러스터 + 느리게 내려가는 음
    init: function (r) { drone(r, 73.4, 'sawtooth', 0.08, 260, 0.13, 0.5); drone(r, 77.8, 'sawtooth', 0.07, 260, 0.17, 0.5); drone(r, 110, 'sawtooth', 0.04, 300, 0.09, 0.5); r.seq = [66, 65, 62, 61]; },
    step: function (r, t, i) { var e = r.e, m = r.seq[i % 4]; osc(e, r.gain, { f: mtof(m), t: t, dur: 2.6, vol: 0.05, a: 0.05, type: 'triangle', lp: 1500, det: 25 }); return 2.4; }
  };

  function startTrack(e, name, t) {
    var def = TRACKS[name]; if (!def) return null; var c = e.ctx;
    var r = { e: e, name: name, def: def, gain: c.createGain(), nodes: [], t0: t, next: t, i: 0 };
    r.gain.gain.setValueAtTime(0.0001, t); r.gain.gain.linearRampToValueAtTime(1, t + XFADE); r.gain.connect(e.bgmBus);
    def.init(r); e.runners.push(r); return r;
  }
  function stopTrack(e, r, t) {
    r.stopped = true; var g = r.gain.gain; try { g.cancelScheduledValues(t); g.setValueAtTime(g.value > 0 ? Math.max(g.value, 0.0001) : 0.0001, t); } catch (x) { }
    g.linearRampToValueAtTime(0.0001, t + XFADE);
    r.nodes.forEach(function (n) { try { n.stop(t + XFADE + 0.1); } catch (x) { } });
    r.endAt = t + XFADE + 0.3;
  }
  function switchTo(e, name, t) {
    if (e.cur && e.cur.name === name) return; if (e.cur) stopTrack(e, e.cur, t);
    e.cur = name ? startTrack(e, name, t) : null;
  }
  function pump(e, until) {
    for (var k = e.runners.length - 1; k >= 0; k--) {
      var r = e.runners[k];
      if (r.stopped) { if (e.ctx.currentTime > r.endAt && !e.offline) { try { r.gain.disconnect(); } catch (x) { } e.runners.splice(k, 1); } continue; }
      var guard = 0;
      while (r.next < until && guard++ < 400) { var dt = r.def.step(r, r.next, r.i++); r.next += Math.max(0.05, dt); }
      if (r.def.tune && !e.offline) r.def.tune(r, e.tension);
    }
  }

  /* ---------- 효과음 ---------- */
  var SFX = {
    chair: function (e, t) { var b = e.sfxBus; nz(e, b, { t: t, dur: 0.38, type: 'bandpass', f0: 380, f1: 950, q: 5, vol: 0.09, a: 0.08 }); osc(e, b, { f: 150, f2: 105, t: t, dur: 0.3, vol: 0.05, a: 0.05, type: 'triangle', lp: 500 }); nz(e, b, { t: t + 0.32, dur: 0.06, type: 'lowpass', f0: 500, vol: 0.07 }); },
    flip: function (e, t) { var b = e.sfxBus; nz(e, b, { t: t, dur: 0.12, type: 'highpass', f0: 2500, f1: 6000, q: 0.6, vol: 0.07, a: 0.04 }); osc(e, b, { f: 1500, f2: 700, t: t + 0.11, dur: 0.04, vol: 0.06, a: 0.002, type: 'triangle' }); nz(e, b, { t: t + 0.11, dur: 0.05, type: 'lowpass', f0: 1200, vol: 0.06 }); },
    point: function (e, t) { var b = e.sfxBus; nz(e, b, { t: t, dur: 0.26, type: 'bandpass', f0: 500, f1: 3200, q: 1.5, vol: 0.1, a: 0.05 }); osc(e, b, { f: 420, f2: 980, t: t, dur: 0.14, vol: 0.05, a: 0.02, type: 'triangle' }); },
    thud: function (e, t) { var b = e.sfxBus; osc(e, b, { f: 130, f2: 38, t: t, dur: 0.4, vol: 0.5, a: 0.004 }); nz(e, b, { t: t, dur: 0.1, type: 'lowpass', f0: 400, vol: 0.18 }); },
    bell: function (e, t) { var b = e.sfxBus; [[660, 0.12, 1.6], [1650, 0.05, 1.1], [2310, 0.025, 0.8]].forEach(function (p) { osc(e, b, { f: p[0], t: t, dur: p[2], vol: p[1], a: 0.004 }); }); },
    ding: function (e, t) { var b = e.sfxBus; osc(e, b, { f: 880, t: t, dur: 0.9, vol: 0.12, a: 0.006 }); osc(e, b, { f: 1320, t: t + 0.07, dur: 0.9, vol: 0.07, a: 0.006 }); },
    tick: function (e, t) { osc(e, e.sfxBus, { f: 2300, t: t, dur: 0.035, vol: 0.05, a: 0.002 }); },
    flicker: function (e, t) { var b = e.sfxBus; for (var i = 0; i < 5; i++) nz(e, b, { t: t + i * 0.07 + e.rnd() * 0.03, dur: 0.035, type: 'highpass', f0: 1800, q: 0.7, vol: 0.09 }); osc(e, b, { f: 100, t: t, dur: 0.4, vol: 0.03, a: 0.01, type: 'sawtooth', lp: 300 }); },
    silence: function (e, t) { duck(e, t, 1.7); },
    stingCit: function (e, t) { var b = e.sfxBus; osc(e, b, { f: 73.4, t: t, dur: 2.2, vol: 0.2, a: 0.9, type: 'sawtooth', lp: 260 }); nz(e, b, { t: t, dur: 1.4, type: 'bandpass', f0: 400, f1: 4500, q: 2, vol: 0.09, a: 1.2 }); osc(e, b, { f: 55, f2: 36, t: t + 1.4, dur: 0.9, vol: 0.4, a: 0.01 }); osc(e, b, { f: 440, t: t + 1.4, dur: 2.2, vol: 0.05, a: 0.01 }); },
    stingLiar: function (e, t) { var b = e.sfxBus; osc(e, b, { f: 73.4, t: t, dur: 2.4, vol: 0.22, a: 0.9, type: 'sawtooth', lp: 260 }); osc(e, b, { f: 77.8, t: t, dur: 2.4, vol: 0.18, a: 0.9, type: 'sawtooth', lp: 260 }); nz(e, b, { t: t, dur: 1.4, type: 'bandpass', f0: 300, f1: 5200, q: 2, vol: 0.11, a: 1.2 }); osc(e, b, { f: 60, f2: 30, t: t + 1.4, dur: 1.1, vol: 0.5, a: 0.01 }); osc(e, b, { f: 311, t: t + 1.4, dur: 2.4, vol: 0.06, a: 0.01 }); osc(e, b, { f: 329.6, t: t + 1.4, dur: 2.4, vol: 0.05, a: 0.01 }); },
    hitLiar: function (e, t) { var b = e.sfxBus; osc(e, b, { f: 70, f2: 28, t: t, dur: 1.2, vol: 0.6, a: 0.004 }); nz(e, b, { t: t, dur: 0.5, type: 'lowpass', f0: 800, f1: 120, vol: 0.25 }); osc(e, b, { f: 1244, t: t + 0.05, dur: 1.6, vol: 0.04, a: 0.01 }); duck(e, t + 0.15, 1.4); },
    win: function (e, t) { var b = e.sfxBus; [60, 64, 67, 72, 76].forEach(function (m, i) { osc(e, b, { f: mtof(m + 12), t: t + i * 0.1, dur: 1.4, vol: 0.09, a: 0.008, type: 'triangle' }); }); [60, 64, 67, 72].forEach(function (m) { osc(e, b, { f: mtof(m), t: t + 0.5, dur: 2.6, vol: 0.07, a: 0.05 }); }); for (var i = 0; i < 6; i++) osc(e, b, { f: 2400 + e.rnd() * 2400, t: t + 0.5 + i * 0.13, dur: 0.25, vol: 0.025, a: 0.003 }); },
    liarWin: function (e, t) {   // 불협 화음 + 낄낄 웃음 같은 소리
      var b = e.sfxBus; [50, 51, 56, 59].forEach(function (m) { osc(e, b, { f: mtof(m + 12), t: t, dur: 2.2, vol: 0.06, a: 0.02, type: 'sawtooth', lp: 900 }); });
      for (var i = 0; i < 5; i++) { var tt = t + 0.5 + i * 0.16; osc(e, b, { f: 520 - i * 34, f2: 400 - i * 34, t: tt, dur: 0.11, vol: 0.07, a: 0.01, type: 'sawtooth', lp: 1100 }); nz(e, b, { t: tt, dur: 0.1, type: 'bandpass', f0: 1500, q: 3, vol: 0.03 }); }
    },
    annLow: function (e, t, len) { var b = e.sfxBus; len = len || 1; osc(e, b, { f: 82, t: t, dur: len, vol: 0.2, a: 0.25, type: 'sawtooth', lp: 320 }); osc(e, b, { f: 61, t: t, dur: len + 0.3, vol: 0.18, a: 0.2 }); nz(e, b, { t: t, dur: len, type: 'bandpass', f0: 300, f1: 900, q: 6, vol: 0.05, a: 0.3 }); },
    points: function (e, t) { for (var i = 0; i < 3; i++) osc(e, e.sfxBus, { f: 1320 + i * 220, t: t + i * 0.09, dur: 0.22, vol: 0.06, a: 0.003, type: 'triangle' }); }
  };
  function duck(e, t, sec) { var g = e.duck.gain; try { g.cancelScheduledValues(t); g.setValueAtTime(g.value || 1, t); g.linearRampToValueAtTime(0.08, t + 0.15); g.setValueAtTime(0.08, t + sec); g.linearRampToValueAtTime(1, t + sec + 0.9); } catch (x) { } }

  /* ---------- 실시간 ---------- */
  function applyMaster() { if (!rt) return; var g = rt.master.gain, t = rt.ctx.currentTime, v = mutedF ? 0 : Math.pow(vol, 2) * 0.9; g.cancelScheduledValues(t); g.setTargetAtTime(v, t, 0.08); }
  function unlock() {
    try {
      if (!AC) return false;
      if (!rt) { var ctx = new AC(); rt = makeEngine(ctx, false); rt.tension = tens; applyMaster(); pumpTimer = setInterval(function () { if (!rt || rt.ctx.state !== 'running') return; pump(rt, rt.ctx.currentTime + LOOK); }, 110); if (wanted) switchTo(rt, wanted, ctx.currentTime + 0.05); loadVoice(); }
      if (rt.ctx.state === 'suspended' && !global.document.hidden) rt.ctx.resume();
      return true;
    } catch (x) { return false; }
  }
  if (global.document) global.document.addEventListener('visibilitychange', function () { if (!rt) return; if (global.document.hidden) rt.ctx.suspend(); else if (!mutedF) rt.ctx.resume(); });
  function bgm(name) { wanted = name || null; if (!rt) return; switchTo(rt, wanted, rt.ctx.currentTime + 0.02); pump(rt, rt.ctx.currentTime + LOOK); }
  function sfx(name) { var f = SFX[name]; if (!f || !rt || mutedF || rt.ctx.state !== 'running') return false; try { f(rt, rt.ctx.currentTime + 0.01); return true; } catch (x) { return false; } }
  function setMuted(m) { mutedF = !!m; applyMaster(); if (rt) { if (mutedF) setTimeout(function () { if (mutedF && rt) rt.ctx.suspend(); }, 400); else if (!global.document.hidden) rt.ctx.resume(); } }
  function setVolume(v) { v = Number(v); vol = isFinite(v) ? Math.max(0, Math.min(1, v)) : vol; applyMaster(); }
  /* ---------- 발표 음성: 파일(있으면) → 브라우저 음성 → 합성 저음 ---------- */
  var VOICE = { seg1: null, yes: null, no: null }, voiceFiles = false, VDEF = { seg1: 1.9, yes: 1.0, no: 1.0 }, voiceTried = false, vMode = 'synth', VBASE = 'audio/';
  function setVoiceFiles(on) { voiceFiles = !!on; if (voiceFiles && rt) loadVoice(); }   // audio/liar_*.ogg 가 저장소에 있을 때만 켠다(없으면 404 소음이 콘솔에 남는다)
  function setVoiceDefaults(o) { for (var k in o) if (VDEF.hasOwnProperty(k) && isFinite(o[k])) VDEF[k] = +o[k]; }
  function loadVoice() {
    if (voiceTried || !voiceFiles || !rt || typeof global.fetch !== 'function') return; voiceTried = true;
    Object.keys(VOICE).forEach(function (k) {
      try { global.fetch(VBASE + 'liar_' + k + '.ogg').then(function (r) { if (!r.ok) throw 0; return r.arrayBuffer(); })
        .then(function (ab) { return new Promise(function (ok, no) { var p = rt.ctx.decodeAudioData(ab, ok, no); if (p && p.catch) p.catch(no); }); })
        .then(function (buf) { if (buf && buf.duration > 0.1) VOICE[k] = buf; }).catch(function () { }); } catch (x) { }
    });
  }
  function voiceDur(name) { var b = VOICE[name]; return b ? b.duration : (VDEF[name] || 1); }
  function voice(name, text) {
    var d = voiceDur(name); if (mutedF || !rt || rt.ctx.state !== 'running') return d;
    try {
      var b = VOICE[name];
      if (b) { vMode = 'file'; var s = rt.ctx.createBufferSource(), g = rt.ctx.createGain(); s.buffer = b; g.gain.value = 1.15; s.connect(g); g.connect(rt.sfxBus); s.start(rt.ctx.currentTime + 0.02); return d; }
      SFX.annLow(rt, rt.ctx.currentTime + 0.02, name === 'seg1' ? 1.4 : 0.8); vMode = 'synth';
      var ss = global.speechSynthesis; if (ss && text && global.SpeechSynthesisUtterance) {
        var u = new global.SpeechSynthesisUtterance(String(text)); u.lang = 'ko-KR'; u.pitch = 0.1; u.rate = 0.62; u.volume = Math.min(1, vol);
        var vs = ss.getVoices ? ss.getVoices() : []; for (var i = 0; i < vs.length; i++) if (/^ko/i.test(vs[i].lang)) { u.voice = vs[i]; break; }
        if (vs.length) vMode = 'speech'; ss.speak(u);
      }
    } catch (x) { }
    return d;
  }
  function tension(x) { tens = Math.max(0, Math.min(1, Number(x) || 0)); if (rt) rt.tension = tens; }

  /* 시험용 오프라인 렌더: spec = {dur, sr, tracks:[[이름, 시작초]...], tension, sfx:[[이름, 시작초]...]} → {data:Float32Array(모노), sr} */
  function render(spec) {
    var sr = spec.sr || 22050, dur = spec.dur || 6, ctx = new OAC(1, Math.ceil(sr * dur), sr), e = makeEngine(ctx, true);
    e.tension = spec.tension == null ? 0 : spec.tension;
    (spec.tracks || []).forEach(function (p) { switchTo(e, p[0], p[1]); });
    (spec.sfx || []).forEach(function (p) { SFX[p[0]](e, p[1]); });
    pump(e, dur + 1);
    return ctx.startRendering().then(function (buf) { return { data: buf.getChannelData(0), sr: sr }; });
  }
  global.LiarAudio = { setVoiceFiles: setVoiceFiles, voice: voice, voiceDur: voiceDur, setVoiceDefaults: setVoiceDefaults, voiceMode: function () { return vMode; }, voiceLoaded: function () { return Object.keys(VOICE).filter(function (k) { return !!VOICE[k]; }); }, _voiceBase: function (b) { VBASE = b; }, unlock: unlock, bgm: bgm, sfx: sfx, tension: tension, setVolume: setVolume, setMuted: setMuted, volume: function () { return vol; }, muted: function () { return mutedF; },
    state: function () { return { unlocked: !!rt, running: !!rt && rt.ctx.state === 'running', track: wanted, vol: vol, muted: mutedF, tension: tens }; },
    trackNames: function () { return Object.keys(TRACKS); }, sfxNames: function () { return Object.keys(SFX); }, _render: render };
})(typeof window !== 'undefined' ? window : this);
