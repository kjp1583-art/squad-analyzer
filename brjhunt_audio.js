/* brjhunt_audio.js — 브장신 사냥터 효과음 + BGM (전부 Web Audio 합성 · 외부 음원/샘플 없음)
 *
 * 전역 BrjAudio = { unlock, sfx, bgm, setMaster, setSfx, setBgm, muted, state, onChange, ... }
 *   unlock()            첫 터치/클릭에서 호출(안 불러도 첫 제스처에 스스로 건다). 그 전에는 AudioContext 도 만들지 않고 소리도 안 낸다.
 *   sfx(name,{vol,rate}) 효과음 한 번. 이름은 sfxNames() 참고. 모르는 이름·잠금 전·음소거·탭 숨김이면 조용히 false.
 *   bgm(track|null)      BGM 트랙(field1~6 · boss · menu) 바꾸기 / null 이면 끄기. 잠금 전에 불러도 기억했다가 해제되면 시작.
 *   setMaster/setSfx/setBgm(0~1)  볼륨. 저장됨.
 *   muted()             지금 음소거 여부(bool). muted(true|false) 로 설정, muted('toggle') 로 뒤집기. toggleMuted() 도 있다.
 *   state()             {master,sfx,bgm,muted, unlocked, track}   onChange(cb) → 해제 함수
 *
 * 설계 메모
 *  - 소리 길: 효과음/BGM 버스 → 컴프레서 → 고역통과(직류 제거) → 마스터 → tanh 소프트 리미터(최대 0.92) → 출력. 마스터를 1 로 올려도 클리핑 없음.
 *  - 효과음 동시 발음: 우선순위별 상한(일반 10 · 스킬 16 · 중요 24) + 같은 이름 최소 간격. 넘치면 새 소리를 버린다.
 *  - 탭 숨김/음소거: AudioContext 를 suspend → BGM 스케줄러도 멈춘다. 돌아오면 이어서.
 *  - 설정은 localStorage('brjhunt_audio_v1') — 막혀 있어도(try/catch) 기본값으로 동작.
 *  - _render() 는 시험용: OfflineAudioContext 로 같은 합성 코드를 돌려 파형을 돌려준다.
 */
(function (global) {
  'use strict';
  var KEY = 'brjhunt_audio_v1';
  var DEF = { master: 0.6, sfx: 0.8, bgm: 0.35, muted: false };
  var S = { master: DEF.master, sfx: DEF.sfx, bgm: DEF.bgm, muted: DEF.muted };
  var listeners = [];
  var rnd = Math.random;

  /* ---------- 설정 저장 ---------- */
  function num01(v, d) { v = Number(v); if (!isFinite(v)) return d; return v < 0 ? 0 : v > 1 ? 1 : v; }
  function loadSettings() {
    try {
      var j = JSON.parse(global.localStorage.getItem(KEY) || 'null');
      if (j && typeof j === 'object') {
        S.master = num01(j.master, DEF.master); S.sfx = num01(j.sfx, DEF.sfx); S.bgm = num01(j.bgm, DEF.bgm);
        S.muted = j.muted === true;
      }
    } catch (e) { /* 저장소 막힘/깨진 값 → 기본값 */ }
  }
  function saveSettings() { try { global.localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* 무시 */ } }
  function mulberry(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function mtof(m) { return 440 * Math.pow(2, (m - 69) / 12); }

  /* ---------- 엔진(컨텍스트 하나에 붙는 소리 길) ---------- */
  var LIMIT = (function () {
    var n = 2049, c = new Float32Array(n);
    for (var i = 0; i < n; i++) { var u = i / (n - 1) * 2 - 1; c[i] = 0.95 * Math.tanh(2 * u / 0.95); }
    return c;
  })();

  function makeEngine(ctx) {
    var e = { ctx: ctx, active: [], last: {}, played: 0, dropped: 0 };
    e.sfxBus = ctx.createGain(); e.bgmBus = ctx.createGain();
    e.comp = ctx.createDynamicsCompressor();
    try {
      e.comp.threshold.value = -16; e.comp.knee.value = 14; e.comp.ratio.value = 4;
      e.comp.attack.value = 0.004; e.comp.release.value = 0.16;
    } catch (x) { /* 구형 */ }
    e.hp = ctx.createBiquadFilter(); e.hp.type = 'highpass'; e.hp.frequency.value = 28; e.hp.Q.value = 0.5;
    e.master = ctx.createGain();
    e.pre = ctx.createGain(); e.pre.gain.value = 0.5;
    e.shaper = ctx.createWaveShaper(); e.shaper.curve = LIMIT;
    e.sfxBus.connect(e.comp); e.bgmBus.connect(e.comp);
    e.comp.connect(e.hp); e.hp.connect(e.master); e.master.connect(e.pre); e.pre.connect(e.shaper); e.shaper.connect(ctx.destination);
    var sr = ctx.sampleRate, nb = ctx.createBuffer(1, sr, sr), d = nb.getChannelData(0);
    for (var i = 0; i < sr; i++) d[i] = rnd() * 2 - 1;
    e.noise = nb;
    return e;
  }
  function applyLevels(e, lv, smooth) {
    var t = e.ctx.currentTime, tc = 0.03;
    function set(p, v) { if (smooth) { try { p.setTargetAtTime(v, t, tc); return; } catch (x) { /* 폴백 */ } } p.value = v; }
    set(e.master.gain, lv.muted ? 0 : lv.master);
    set(e.sfxBus.gain, lv.sfx * SFX_GAIN); // 효과음 버스 보정: 합성음 피크가 낮아 BGM 에 묻히지 않게
    set(e.bgmBus.gain, lv.bgm);
  }

  /* 소리 조각 도우미: 시작 t0, 음량 배수 v, 음높이 배수 r, 도착 dest */
  function H(e, dest, t0, v, r) {
    var c = e.ctx, nyq = c.sampleRate * 0.45;
    function cf(f) { return Math.min(Math.max(f, 20), nyq); }
    return {
      tone: function (at, o) {
        var t = t0 + at, dur = o.dur, a = Math.min(o.a || 0.004, dur * 0.5), vol = (o.vol || 0.3) * v;
        var osc = c.createOscillator(), g = c.createGain(), out = osc;
        osc.type = o.type || 'sine';
        osc.frequency.setValueAtTime(cf(o.f * r), t);
        if (o.f2) osc.frequency.exponentialRampToValueAtTime(cf(o.f2 * r), t + dur * (o.sw || 1));
        if (o.det) osc.detune.value = o.det;
        if (o.lp) { var fl = c.createBiquadFilter(); fl.type = 'lowpass'; fl.frequency.value = cf(o.lp); osc.connect(fl); out = fl; }
        g.gain.setValueAtTime(0.0001, t);
        g.gain.linearRampToValueAtTime(vol, t + a);
        if (o.hold) g.gain.setValueAtTime(vol, t + a + Math.min(o.hold, dur - a - 0.01));
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        out.connect(g); g.connect(dest);
        osc.start(t); osc.stop(t + dur + 0.03);
      },
      noise: function (at, o) {
        var t = t0 + at, dur = o.dur, a = Math.min(o.a || 0.003, dur * 0.8), vol = (o.vol || 0.3) * v;
        var s = c.createBufferSource(), fl = c.createBiquadFilter(), g = c.createGain();
        s.buffer = e.noise; s.loop = true;
        fl.type = o.type || 'bandpass'; fl.Q.value = o.q || 0.8;
        fl.frequency.setValueAtTime(cf(o.f * r), t);
        if (o.f2) fl.frequency.exponentialRampToValueAtTime(cf(o.f2 * r), t + dur);
        g.gain.setValueAtTime(0.0001, t);
        g.gain.linearRampToValueAtTime(vol, t + a);
        if (o.hold) g.gain.setValueAtTime(vol, t + a + Math.min(o.hold, dur - a - 0.01));
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        s.connect(fl); fl.connect(g); g.connect(dest);
        s.start(t, rnd() * 0.8); s.stop(t + dur + 0.03);
      }
    };
  }

  /* ---------- 효과음 ---------- */
  // d: 길이(초) · p: 우선순위(0 일반 · 1 스킬 · 2 중요) · gap: 같은 이름 최소 간격 · jit: 음높이 무작위 폭
  var SFX = {
    hit: { d: 0.12, p: 0, gap: 0.04, jit: 0.08, fn: function (h) {
      h.noise(0, { dur: 0.07, type: 'bandpass', f: 2400, f2: 900, q: 1.1, vol: 0.5 });
      h.tone(0, { type: 'triangle', f: 240, f2: 100, dur: 0.09, vol: 0.55 }); } },
    crit: { d: 0.3, p: 1, gap: 0.05, jit: 0.04, fn: function (h) {
      h.noise(0, { dur: 0.13, type: 'highpass', f: 2800, vol: 0.35 });
      h.tone(0, { type: 'triangle', f: 300, f2: 80, dur: 0.15, vol: 0.6 });
      h.tone(0.02, { type: 'square', f: 1200, f2: 1900, dur: 0.16, vol: 0.2, lp: 6000 });
      h.tone(0.06, { type: 'sine', f: 2637, dur: 0.22, vol: 0.22 }); } },
    kill: { d: 0.2, p: 0, gap: 0.04, jit: 0.1, fn: function (h) {
      h.tone(0, { type: 'sine', f: 760, f2: 170, dur: 0.14, vol: 0.55 });
      h.noise(0, { dur: 0.1, type: 'bandpass', f: 1500, f2: 500, q: 0.9, vol: 0.35 });
      h.tone(0.05, { type: 'triangle', f: 1568, dur: 0.09, vol: 0.18 }); } },
    coin: { d: 0.36, p: 0, gap: 0.05, jit: 0.03, fn: function (h) {
      h.tone(0, { type: 'square', f: 1318, dur: 0.1, vol: 0.18, lp: 5000 });
      h.tone(0.07, { type: 'square', f: 1760, dur: 0.28, vol: 0.18, hold: 0.04, lp: 6000 });
      h.tone(0.07, { type: 'sine', f: 3520, dur: 0.2, vol: 0.12 }); } },
    levelup: { d: 1.1, p: 2, gap: 0.3, fn: function (h) {
      [72, 76, 79, 84, 88].forEach(function (n, i) {
        h.tone(i * 0.075, { type: 'triangle', f: mtof(n), dur: 0.22, vol: 0.3 });
        h.tone(i * 0.075, { type: 'square', f: mtof(n), dur: 0.18, vol: 0.09, lp: 4000 });
      });
      [84, 88, 91].forEach(function (n) { h.tone(0.4, { type: 'triangle', f: mtof(n), dur: 0.7, vol: 0.17, hold: 0.15 }); });
      h.noise(0.3, { dur: 0.4, type: 'highpass', f: 6000, vol: 0.1 }); } },
    boss_in: { d: 1.9, p: 2, gap: 0.5, fn: function (h) {
      h.tone(0, { type: 'sine', f: 90, f2: 35, dur: 0.9, vol: 0.7 });
      h.tone(0, { type: 'sawtooth', f: 70, f2: 48, dur: 1.4, vol: 0.4, lp: 400, a: 0.05, hold: 0.3 });
      h.tone(0.1, { type: 'sawtooth', f: 110, dur: 0.6, vol: 0.28, lp: 900, a: 0.08 });
      h.tone(0.7, { type: 'sawtooth', f: 98, f2: 92, dur: 1.1, vol: 0.28, lp: 800, a: 0.08, hold: 0.3 });
      h.noise(0, { dur: 1.6, type: 'lowpass', f: 220, q: 0.5, vol: 0.5, a: 0.25 }); } },
    boss_win: { d: 2.0, p: 2, gap: 0.5, fn: function (h) {
      [67, 72, 76, 79].forEach(function (n, i) {
        h.tone(i * 0.13, { type: 'square', f: mtof(n), dur: 0.35, vol: 0.14, lp: 3000 });
        h.tone(i * 0.13, { type: 'sawtooth', f: mtof(n), dur: 0.35, vol: 0.1, lp: 2500 });
      });
      [72, 76, 79, 84].forEach(function (n) { h.tone(0.55, { type: 'sawtooth', f: mtof(n), dur: 1.3, vol: 0.12, lp: 2500, hold: 0.5 }); });
      h.tone(0.55, { type: 'sine', f: 100, f2: 45, dur: 0.5, vol: 0.6 });
      h.noise(0.55, { dur: 0.9, type: 'highpass', f: 5500, vol: 0.12 }); } },
    boss_lose: { d: 2.0, p: 2, gap: 0.5, fn: function (h) {
      [64, 62, 60, 57].forEach(function (n, i) {
        h.tone(i * 0.22, { type: 'triangle', f: mtof(n), dur: 0.45, vol: 0.3 });
        h.tone(i * 0.22, { type: 'sawtooth', f: mtof(n), dur: 0.45, vol: 0.08, lp: 900 });
      });
      h.tone(0.66, { type: 'sine', f: 110, f2: 55, dur: 1.2, vol: 0.5 });
      h.noise(0.66, { dur: 1.0, type: 'lowpass', f: 700, f2: 120, vol: 0.3 }); } },
    click: { d: 0.06, p: 0, gap: 0.03, fn: function (h) {
      h.tone(0, { type: 'square', f: 1500, f2: 900, dur: 0.03, vol: 0.22, lp: 5000 });
      h.noise(0, { dur: 0.02, type: 'highpass', f: 4000, vol: 0.15 }); } },
    tab: { d: 0.1, p: 0, gap: 0.04, fn: function (h) {
      h.tone(0, { type: 'triangle', f: 520, f2: 780, dur: 0.07, vol: 0.3 });
      h.tone(0.02, { type: 'sine', f: 1040, dur: 0.06, vol: 0.1 }); } },
    error: { d: 0.32, p: 2, gap: 0.15, fn: function (h) {
      h.tone(0, { type: 'square', f: 180, f2: 150, dur: 0.12, vol: 0.25, lp: 1200 });
      h.tone(0.14, { type: 'square', f: 150, f2: 120, dur: 0.16, vol: 0.25, lp: 1000 }); } },
    summon: { d: 1.4, p: 2, gap: 0.3, fn: function (h) {
      h.tone(0, { type: 'sine', f: 300, f2: 1500, dur: 0.8, vol: 0.3, a: 0.1 });
      h.tone(0, { type: 'triangle', f: 600, f2: 3000, dur: 0.8, vol: 0.12 });
      h.noise(0, { dur: 0.8, type: 'bandpass', f: 800, f2: 5000, q: 3, vol: 0.25, a: 0.3 });
      h.tone(0.8, { type: 'sine', f: 1568, dur: 0.4, vol: 0.3, hold: 0.1 });
      h.tone(0.82, { type: 'sine', f: 2093, dur: 0.5, vol: 0.2 }); } },
    summon_rare: { d: 3.0, p: 2, gap: 0.3, fn: function (h) {
      h.tone(0, { type: 'sine', f: 250, f2: 1800, dur: 1.1, vol: 0.3, a: 0.2 });
      h.tone(0, { type: 'sawtooth', f: 120, f2: 480, dur: 1.1, vol: 0.12, lp: 900, a: 0.3 });
      h.noise(0, { dur: 1.1, type: 'bandpass', f: 600, f2: 6500, q: 3, vol: 0.3, a: 0.5 });
      h.tone(1.1, { type: 'sine', f: 100, f2: 40, dur: 0.6, vol: 0.6 });
      [76, 79, 83, 88, 91].forEach(function (n, i) { h.tone(1.1 + i * 0.06, { type: 'triangle', f: mtof(n), dur: 0.5, vol: 0.2 }); });
      [79, 84, 88, 95].forEach(function (n) { h.tone(1.4, { type: 'sine', f: mtof(n), dur: 1.6, vol: 0.15, hold: 0.3 }); });
      h.tone(1.4, { type: 'sine', f: 3136, dur: 1.4, vol: 0.1 });
      h.noise(1.1, { dur: 1.0, type: 'highpass', f: 6000, vol: 0.12 }); } },
    enhance_ok: { d: 1.0, p: 2, gap: 0.2, fn: function (h) {
      h.noise(0, { dur: 0.06, type: 'bandpass', f: 3000, q: 2, vol: 0.5 });
      h.tone(0, { type: 'triangle', f: 180, f2: 90, dur: 0.12, vol: 0.5 });
      [1240, 1860, 2790].forEach(function (f, i) { h.tone(0, { type: 'sine', f: f, dur: 0.5 - i * 0.1, vol: 0.14 - i * 0.03 }); });
      h.tone(0.15, { type: 'sine', f: 1047, dur: 0.4, vol: 0.22 });
      h.tone(0.25, { type: 'sine', f: 1568, dur: 0.7, vol: 0.25, hold: 0.1 });
      h.noise(0.25, { dur: 0.5, type: 'highpass', f: 6500, vol: 0.08 }); } },
    enhance_fail: { d: 0.9, p: 2, gap: 0.2, fn: function (h) {
      h.tone(0, { type: 'sine', f: 120, f2: 40, dur: 0.3, vol: 0.55 });
      h.tone(0, { type: 'sawtooth', f: 220, f2: 55, dur: 0.6, vol: 0.3, lp: 800 });
      h.tone(0.05, { type: 'square', f: 110, f2: 40, dur: 0.5, vol: 0.12, lp: 500 });
      h.noise(0, { dur: 0.5, type: 'lowpass', f: 900, f2: 150, vol: 0.4 }); } },
    awaken: { d: 3.0, p: 2, gap: 1.0, fn: function (h) {
      h.noise(0, { dur: 1.2, type: 'bandpass', f: 200, f2: 6000, q: 2, vol: 0.4, a: 0.8 });
      h.tone(0, { type: 'sawtooth', f: 80, f2: 320, dur: 1.3, vol: 0.28, lp: 1200, a: 0.6 });
      h.tone(0, { type: 'sine', f: 60, f2: 120, dur: 1.3, vol: 0.3, a: 0.5 });
      h.tone(1.2, { type: 'sine', f: 110, f2: 30, dur: 1.2, vol: 0.7 });
      [60, 67, 72, 76, 79, 84].forEach(function (n) {
        h.tone(1.2, { type: 'triangle', f: mtof(n), dur: 1.7, vol: 0.12, hold: 0.5 });
        h.tone(1.2, { type: 'sawtooth', f: mtof(n), dur: 1.5, vol: 0.05, lp: 3000, hold: 0.4 });
      });
      h.tone(1.25, { type: 'sine', f: 2093, dur: 1.4, vol: 0.14 });
      h.noise(1.2, { dur: 1.0, type: 'highpass', f: 5000, vol: 0.14 }); } },
    skill_slash: { d: 0.3, p: 1, gap: 0.06, jit: 0.05, fn: function (h) {
      h.noise(0, { dur: 0.16, type: 'bandpass', f: 1800, f2: 7000, q: 1.5, vol: 0.5, a: 0.02 });
      h.tone(0, { type: 'sine', f: 900, f2: 2200, dur: 0.1, vol: 0.14 });
      h.noise(0.08, { dur: 0.06, type: 'highpass', f: 3000, vol: 0.3 }); } },
    skill_peck: { d: 0.3, p: 1, gap: 0.08, jit: 0.05, fn: function (h) {
      for (var i = 0; i < 4; i++) {
        h.tone(i * 0.05, { type: 'triangle', f: 1400, f2: 700, dur: 0.035, vol: 0.3 });
        h.noise(i * 0.05, { dur: 0.02, type: 'bandpass', f: 3000, q: 1, vol: 0.2 });
      } } },
    skill_spin: { d: 0.7, p: 1, gap: 0.1, fn: function (h) {
      h.noise(0, { dur: 0.3, type: 'bandpass', f: 400, f2: 2500, q: 2.5, vol: 0.5, a: 0.1 });
      h.noise(0.3, { dur: 0.3, type: 'bandpass', f: 2500, f2: 500, q: 2.5, vol: 0.45, a: 0.02 });
      h.tone(0, { type: 'sine', f: 300, f2: 600, dur: 0.3, vol: 0.12 });
      h.tone(0.3, { type: 'sine', f: 600, f2: 250, dur: 0.3, vol: 0.12 }); } },
    skill_bomb: { d: 1.1, p: 1, gap: 0.15, fn: function (h) {
      h.tone(0, { type: 'sine', f: 1400, f2: 350, dur: 0.3, vol: 0.16 });
      h.noise(0.3, { dur: 0.7, type: 'lowpass', f: 3000, f2: 120, q: 0.7, vol: 0.7 });
      h.tone(0.3, { type: 'sine', f: 140, f2: 35, dur: 0.6, vol: 0.7 });
      h.noise(0.3, { dur: 0.2, type: 'highpass', f: 2000, vol: 0.3 }); } },
    skill_thunder: { d: 1.1, p: 1, gap: 0.15, fn: function (h) {
      h.noise(0, { dur: 0.1, type: 'highpass', f: 1500, vol: 0.6 });
      [2200, 1400, 2600, 900].forEach(function (f, i) { h.tone(i * 0.025, { type: 'square', f: f, dur: 0.03, vol: 0.14, lp: 5000 }); });
      h.noise(0.06, { dur: 0.9, type: 'lowpass', f: 300, f2: 80, q: 0.5, vol: 0.6, a: 0.05 });
      h.tone(0.06, { type: 'sine', f: 70, f2: 40, dur: 0.8, vol: 0.4 }); } },
    skill_fire: { d: 0.8, p: 1, gap: 0.12, fn: function (h) {
      h.noise(0, { dur: 0.55, type: 'bandpass', f: 300, f2: 2500, q: 1, vol: 0.5, a: 0.15 });
      for (var i = 0; i < 9; i++) h.noise(0.05 + rnd() * 0.5, { dur: 0.015, type: 'highpass', f: 3000, vol: 0.22 });
      h.tone(0, { type: 'sawtooth', f: 120, f2: 300, dur: 0.5, vol: 0.14, lp: 600 }); } },
    skill_egg: { d: 0.7, p: 1, gap: 0.12, fn: function (h) {
      h.noise(0, { dur: 0.15, type: 'bandpass', f: 900, f2: 2500, vol: 0.25 });
      h.noise(0.15, { dur: 0.05, type: 'bandpass', f: 2500, q: 1, vol: 0.3 });
      h.tone(0.15, { type: 'sine', f: 1760, dur: 0.25, vol: 0.28, hold: 0.03 });
      h.tone(0.2, { type: 'sine', f: 2349, dur: 0.3, vol: 0.2 }); } },
    skill_shield: { d: 0.7, p: 1, gap: 0.2, fn: function (h) {
      h.tone(0, { type: 'sine', f: 330, f2: 495, dur: 0.5, vol: 0.22, a: 0.08 });
      h.tone(0, { type: 'sine', f: 660, f2: 990, dur: 0.5, vol: 0.12, a: 0.08 });
      h.tone(0, { type: 'triangle', f: 220, dur: 0.5, vol: 0.15, det: 8, a: 0.06 });
      h.noise(0.05, { dur: 0.3, type: 'highpass', f: 6000, vol: 0.1, a: 0.1 }); } },
    skill_shrimp: { d: 0.6, p: 1, gap: 0.15, fn: function (h) {
      [1, 1.25, 1.5].forEach(function (m, i) {
        h.tone(i * 0.08, { type: 'sine', f: 400 * m, f2: 900 * m, dur: 0.09, vol: 0.3 });
        h.noise(i * 0.08, { dur: 0.06, type: 'bandpass', f: 1000, f2: 2000, q: 4, vol: 0.15 });
      });
      h.tone(0.26, { type: 'square', f: 1760, dur: 0.12, vol: 0.1, lp: 4000 }); } },
    skill_storm: { d: 1.7, p: 1, gap: 0.3, fn: function (h) {
      h.noise(0, { dur: 1.2, type: 'bandpass', f: 300, f2: 2200, q: 1.2, vol: 0.55, a: 0.5 });
      h.tone(0, { type: 'sawtooth', f: 200, f2: 700, dur: 1.2, vol: 0.14, lp: 900, a: 0.5 });
      h.noise(0.5, { dur: 0.1, type: 'highpass', f: 1500, vol: 0.5 });
      h.noise(0.5, { dur: 1.0, type: 'lowpass', f: 400, f2: 80, q: 0.5, vol: 0.6 });
      h.tone(0.5, { type: 'sine', f: 80, f2: 35, dur: 1.0, vol: 0.55 });
      h.noise(0.5, { dur: 0.5, type: 'highpass', f: 4000, vol: 0.18 }); } }
  };
  var SKILL_IDS = ['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shield', 'shrimp', 'storm'];
  var SFX_NAMES = ['hit', 'crit', 'kill', 'coin', 'levelup', 'boss_in', 'boss_win', 'boss_lose', 'click', 'tab', 'error',
    'summon', 'summon_rare', 'enhance_ok', 'enhance_fail', 'awaken'].concat(SKILL_IDS.map(function (s) { return 'skill_' + s; }));
  var CAP = [10, 16, 24];
  var SFX_GAIN = 1.6;

  function clampN(v, lo, hi, d) { v = Number(v); if (!isFinite(v)) return d; return v < lo ? lo : v > hi ? hi : v; }
  function playSfx(e, name, o, when) {
    var d = SFX.hasOwnProperty(name) ? SFX[name] : null;
    if (!d) return false;
    if (when - (e.last[name] === undefined ? -9 : e.last[name]) < d.gap) { e.dropped++; return false; }
    var a = e.active, k = 0, i;
    for (i = 0; i < a.length; i++) if (a[i] > when) a[k++] = a[i];
    a.length = k;
    if (a.length >= CAP[d.p]) { e.dropped++; return false; }
    e.last[name] = when; a.push(when + d.d);
    var vol = clampN(o && o.vol, 0, 2, 1), rate = clampN(o && o.rate, 0.25, 4, 1);
    if (d.jit) rate *= 1 + (rnd() * 2 - 1) * d.jit;
    d.fn(H(e, e.sfxBus, when, vol, rate));
    e.played++;
    return true;
  }

  /* ---------- BGM ---------- */
  var SC = {
    maj: [0, 2, 4, 5, 7, 9, 11], min: [0, 2, 3, 5, 7, 8, 10], dor: [0, 2, 3, 5, 7, 9, 10],
    mix: [0, 2, 4, 5, 7, 9, 10], phr: [0, 1, 3, 5, 7, 8, 10], lyd: [0, 2, 4, 6, 7, 9, 11]
  };
  // 한 마디(16칸) 리듬 틀: [시작칸, 길이칸]
  var RH = [
    [[0, 4], [4, 2], [6, 2], [8, 4], [12, 4]],
    [[0, 2], [2, 2], [4, 4], [8, 2], [10, 2], [12, 4]],
    [[0, 3], [3, 3], [6, 2], [8, 3], [11, 3], [14, 2]],
    [[0, 6], [6, 2], [8, 2], [10, 2], [12, 4]],
    [[0, 2], [2, 2], [4, 2], [6, 2], [8, 2], [10, 2], [12, 2], [14, 2]],
    [[0, 1], [1, 1], [2, 2], [4, 1], [5, 1], [6, 2], [8, 1], [9, 1], [10, 2], [12, 4]],
    [[0, 8], [8, 4], [12, 4]]
  ];
  var NODRUM = '................';
  var TRACKS = {
    // 지역별 — 템포·조·음색을 다르게
    field1: { bpm: 108, root: 36, sc: 'maj', prog: [0, 4, 5, 3, 0, 4, 3, 4], seed: 11,
      k: 'x.......x.......', s: '....x.......x...', h: 'x.o.x.o.x.o.x.o.', bass: 'x.......x.x.....', bw: 'triangle', bl: 900,
      pw: 'triangle', pv: 0.1, arp: { step: 2, seq: [0, 1, 2, 3, 2, 1], vol: 0.08, type: 'triangle' },
      lw: 'square', ll: 3200, lv: 0.12, rh: [0, 1, 3], dly: 0.3, swing: 0 },
    field2: { bpm: 120, root: 43, sc: 'mix', prog: [0, 6, 3, 0, 0, 6, 4, 0], seed: 22,
      k: 'x.....x.x.......', s: '....x.......x...', h: 'o.x.o.x.o.x.o.x.', bass: 'x..x..x.x..x..x.', bw: 'sawtooth', bl: 700,
      pw: 'triangle', pv: 0.09, arp: { step: 2, seq: [0, 2, 1, 3], vol: 0.07, type: 'square' },
      lw: 'sawtooth', ll: 2800, lv: 0.1, rh: [1, 2, 4], dly: 0.28, swing: 0.1 },
    field3: { bpm: 100, root: 45, sc: 'min', prog: [0, 5, 2, 6, 0, 3, 4, 4], seed: 33,
      k: 'x...........x...', s: '........x.......', h: '..o...o...o...o.', bass: 'x.......x.......', bw: 'triangle', bl: 800,
      pw: 'sawtooth', pv: 0.07, pl: 900, arp: { step: 2, seq: [0, 1, 2, 3, 2, 1, 2, 1], vol: 0.09, type: 'triangle' },
      lw: 'triangle', ll: 4000, lv: 0.18, rh: [3, 6, 0], dly: 0.42, swing: 0 },
    field4: { bpm: 128, root: 38, sc: 'dor', prog: [0, 3, 0, 4, 0, 3, 6, 4], seed: 44,
      k: 'x...x...x...x...', s: '....x.......x...', h: '..x...x...x...x.', bass: 'x.x.x.x.x.x.x.x.', bw: 'sawtooth', bl: 650,
      pw: 'sawtooth', pv: 0.05, pl: 1200, arp: { step: 1, seq: [0, 2, 1, 3], vol: 0.06, type: 'square' },
      lw: 'square', ll: 3500, lv: 0.11, rh: [2, 4, 5], dly: 0.25, swing: 0 },
    field5: { bpm: 124, root: 41, sc: 'lyd', prog: [0, 1, 4, 0, 0, 1, 5, 4], seed: 55,
      k: 'x.......x...x...', s: '....x.......x...', h: 'x.xox.xox.xox.xo', bass: 'x..x....x..x....', bw: 'triangle', bl: 1000,
      pw: 'triangle', pv: 0.1, arp: { step: 1, seq: [0, 1, 2, 3, 2, 1, 0, 1], vol: 0.06, type: 'sine' },
      lw: 'sine', ll: 5000, lv: 0.2, rh: [0, 2, 3], dly: 0.4, swing: 0, lvib: true },
    field6: { bpm: 140, root: 40, sc: 'min', prog: [0, 5, 2, 6, 0, 5, 3, 4], seed: 66,
      k: 'x.....x.x...x...', s: '....x.......x..x', h: 'x.x.x.x.x.x.x.xx', bass: 'x.xxx.xxx.xxx.xx', bw: 'sawtooth', bl: 600, fill: true,
      pw: 'sawtooth', pv: 0.06, pl: 1000, arp: { step: 2, seq: [0, 2, 3, 2], vol: 0.06, type: 'square' },
      lw: 'sawtooth', ll: 3000, lv: 0.12, rh: [1, 5, 4], dly: 0.3, swing: 0 },
    boss: { bpm: 156, root: 37, sc: 'phr', prog: [0, 0, 1, 0, 0, 5, 1, 0], seed: 77,
      k: 'x..x..x.x..x..x.', s: '....x.......x...', h: 'xoxoxoxoxoxoxoxo', bass: 'xxOxxxOxxxOxxxOx', bw: 'sawtooth', bl: 550, fill: true, riser: true,
      pw: 'sawtooth', pv: 0.06, pl: 700, arp: { step: 1, seq: [0, 0, 2, 0, 3, 0, 2, 0], vol: 0.05, type: 'square' },
      lw: 'sawtooth', ll: 2600, lv: 0.12, rh: [5, 1, 2], dly: 0.2, swing: 0, dv: 1.05 },
    menu: { bpm: 84, root: 41, sc: 'maj', prog: [0, 5, 3, 4, 0, 5, 1, 4], seed: 88,
      k: NODRUM, s: NODRUM, h: 'o...o...o...o...', dv: 0.45, bass: 'x.......x.......', bw: 'triangle', bl: 700,
      pw: 'triangle', pv: 0.11, arp: { step: 2, seq: [0, 1, 2, 3, 2, 1, 2, 1], vol: 0.07, type: 'sine' },
      lw: 'sine', ll: 5000, lv: 0.18, rh: [3, 6, 0], dly: 0.45, swing: 0, lvib: true }
  };
  var TRACK_NAMES = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'boss', 'menu'];
  var LOOP = 128; // 8마디 × 16칸

  function scNote(tr, i) {
    var o = Math.floor(i / 7), k = ((i % 7) + 7) % 7;
    return tr.root + SC[tr.sc][k] + 12 * o;
  }
  function genMotif(R, idxs) {
    var rh = RH[idxs[(R() * idxs.length) | 0]], cur = [0, 2, 4][(R() * 3) | 0], out = [];
    rh.forEach(function (p) {
      var strong = p[0] % 4 === 0, c;
      if (strong && R() < 0.65) c = [0, 2, 4, 7][(R() * 4) | 0];
      else c = cur + [-1, 1, 1, 2, -2][(R() * 5) | 0];
      c = Math.max(-2, Math.min(9, c)); cur = c;
      out.push({ s: p[0], len: p[1], c: c });
    });
    return out;
  }
  function compile(tr) {
    if (tr._ev) return tr._ev;
    var R = mulberry(tr.seed), ev = [], s, b;
    for (s = 0; s < LOOP; s++) ev.push({ k: 0, s: 0, h: 0, b: null, pad: null, arp: null, lead: null, riser: 0 });
    function vel(ch) { return ch === 'x' ? 1 : ch === 'o' ? 0.5 : 0; }
    for (b = 0; b < 8; b++) {
      var deg = tr.prog[b], base = b * 16;
      for (s = 0; s < 16; s++) {
        var e = ev[base + s];
        e.k = vel(tr.k[s]); e.s = vel(tr.s[s]); e.h = vel(tr.h[s]);
        if (tr.fill && b === 7 && s >= 12) { e.s = 0.55 + (s - 12) * 0.15; e.k = 0; }
        if (tr.fill && b % 4 === 3 && s === 14) e.s = Math.max(e.s, 0.6);
      }
      // 베이스: 'x' 소리, 'O' 한 옥타브 위
      var hits = [];
      for (s = 0; s < 16; s++) if (tr.bass[s] === 'x' || tr.bass[s] === 'O') hits.push(s);
      hits.forEach(function (st, j) {
        var nx = j + 1 < hits.length ? hits[j + 1] : 16;
        var idx = deg + (tr.bass[st] === 'O' ? 7 : 0);
        ev[base + st].b = { m: scNote(tr, idx), len: Math.max(1, nx - st) };
      });
      // 패드
      ev[base].pad = [scNote(tr, deg + 7), scNote(tr, deg + 9), scNote(tr, deg + 11)];
      // 아르페지오
      if (tr.arp) {
        var k = 0, tones = [0, 2, 4, 7];
        for (s = 0; s < 16; s += tr.arp.step) { ev[base + s].arp = scNote(tr, deg + 14 + tones[tr.arp.seq[k % tr.arp.seq.length]]); k++; }
      }
      if (tr.riser && b % 4 === 3) ev[base].riser = 1;
    }
    // 멜로디: A A' B A'' 구조(2마디 단위)
    var A0 = genMotif(R, tr.rh), A1 = genMotif(R, tr.rh), B0 = genMotif(R, tr.rh), B1 = genMotif(R, tr.rh);
    function withEnd(m, c, stretch) {
      var o = m.map(function (n) { return { s: n.s, len: n.len, c: n.c }; }), l = o[o.length - 1];
      l.c = c; if (stretch) l.len = Math.max(l.len, 16 - l.s);
      return o;
    }
    var bars = [A0, A1, A0, withEnd(A1, 2, false), B0, B1, A0, withEnd(A1, 0, true)];
    for (b = 0; b < 8; b++) {
      bars[b].forEach(function (n) {
        var idx = tr.prog[b] + 14 + n.c, m = scNote(tr, idx);
        while (m > 86) { idx -= 7; m = scNote(tr, idx); }
        while (m < 58) { idx += 7; m = scNote(tr, idx); }
        ev[b * 16 + n.s].lead = { m: m, len: n.len };
      });
    }
    tr._ev = ev;
    return ev;
  }

  // 오래 울리는 음(포락선: 어택 → 유지 → 릴리즈)
  function note(e, dest, t, dur, o) {
    var c = e.ctx, osc = c.createOscillator(), g = c.createGain(), out = osc, a = o.a || 0.005, r = o.r || 0.05, end = t + dur;
    osc.type = o.type; osc.frequency.value = Math.min(o.f, c.sampleRate * 0.45);
    if (o.det) osc.detune.value = o.det;
    if (o.vib) { // 가벼운 떨림
      var lfo = c.createOscillator(), lg = c.createGain();
      lfo.frequency.value = 5.2; lg.gain.value = 9; lfo.connect(lg); lg.connect(osc.detune);
      lfo.start(t + 0.12); lfo.stop(end + r + 0.02);
    }
    if (o.lp) { var fl = c.createBiquadFilter(); fl.type = 'lowpass'; fl.frequency.value = o.lp; osc.connect(fl); out = fl; }
    var sus = o.vol;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(o.vol, t + a);
    if (o.pluck) {
      sus = Math.max(0.0002, o.vol * o.pluck);
      g.gain.exponentialRampToValueAtTime(sus, Math.min(end, t + a + (o.dec || 0.15)));
    }
    g.gain.setValueAtTime(sus, end);
    g.gain.exponentialRampToValueAtTime(0.0001, end + r);
    out.connect(g); g.connect(dest);
    osc.start(t); osc.stop(end + r + 0.03);
  }

  function startTrack(e, name, fadeIn) {
    var tr = TRACKS[name], c = e.ctx;
    if (!tr) return null;
    var now = c.currentTime, sd = 60 / tr.bpm / 4;
    var inst = { name: name, tr: tr, ev: compile(tr), sd: sd, step: 0, next: now + 0.06 };
    inst.gain = c.createGain(); inst.lead = c.createGain();
    inst.gain.gain.setValueAtTime(0.0001, now);
    inst.gain.gain.linearRampToValueAtTime(1, now + (fadeIn || 0.05));
    inst.gain.connect(e.bgmBus);
    // 멜로디 메아리(점8분)
    var dl = c.createDelay(2), fb = c.createGain(), wet = c.createGain(), lpf = c.createBiquadFilter();
    dl.delayTime.value = sd * 3; fb.gain.value = 0.3; wet.gain.value = tr.dly || 0.3;
    lpf.type = 'lowpass'; lpf.frequency.value = 2600;
    inst.lead.connect(inst.gain); inst.lead.connect(dl);
    dl.connect(lpf); lpf.connect(fb); fb.connect(dl); lpf.connect(wet); wet.connect(inst.gain);
    return inst;
  }
  function playStep(e, inst, s, t) {
    var tr = inst.tr, ev = inst.ev[s], sd = inst.sd, dv = tr.dv == null ? 1 : tr.dv, h;
    if (ev.k || ev.s || ev.h) {
      h = H(e, inst.gain, t, dv, 1);
      if (ev.k) {
        h.tone(0, { type: 'sine', f: 170, f2: 44, dur: 0.26, sw: 0.4, vol: 0.95 * ev.k, a: 0.002 });
        h.noise(0, { dur: 0.015, type: 'highpass', f: 2000, vol: 0.15 * ev.k });
      }
      if (ev.s) {
        h.noise(0, { dur: 0.17, type: 'bandpass', f: 1900, q: 0.6, vol: 0.42 * ev.s });
        h.tone(0, { type: 'triangle', f: 210, f2: 130, dur: 0.1, vol: 0.28 * ev.s });
      }
      if (ev.h) h.noise(0, { dur: 0.04, type: 'highpass', f: 7500, vol: 0.13 * ev.h });
    }
    if (ev.b) {
      var bd = ev.b.len * sd * 0.92, f = mtof(ev.b.m);
      note(e, inst.gain, t, bd, { type: tr.bw, f: f, vol: 0.3, a: 0.006, r: 0.05, lp: tr.bl });
      note(e, inst.gain, t, bd, { type: 'triangle', f: f * 2, vol: 0.1, a: 0.006, r: 0.05 });
    }
    if (ev.pad) {
      ev.pad.forEach(function (m, i) {
        note(e, inst.gain, t, 16 * sd * 0.98, { type: tr.pw, f: mtof(m), vol: tr.pv, a: 0.3, r: 0.4, lp: tr.pl || 3000, det: (i - 1) * 6 });
      });
    }
    if (ev.arp) note(e, inst.gain, t, sd * 1.4, { type: tr.arp.type, f: mtof(ev.arp), vol: tr.arp.vol, a: 0.003, r: 0.05, pluck: 0.25, dec: 0.08, lp: 3200 });
    if (ev.lead) {
      var ld = Math.max(0.05, ev.lead.len * sd * 0.9), lf = mtof(ev.lead.m);
      note(e, inst.lead, t, ld, { type: tr.lw, f: lf, vol: tr.lv, a: 0.012, r: 0.12, lp: tr.ll, vib: tr.lvib, pluck: 0.7, dec: 0.2 });
      if (tr.lw === 'sawtooth' || tr.lw === 'square') note(e, inst.lead, t, ld, { type: tr.lw, f: lf, vol: tr.lv * 0.5, a: 0.012, r: 0.12, lp: tr.ll, det: 9 });
    }
    if (ev.riser) {
      var bar = 16 * sd;
      H(e, inst.gain, t, 1, 1).noise(0, { dur: bar, type: 'bandpass', f: 400, f2: 5000, q: 2, vol: 0.12, a: bar * 0.8 });
    }
  }
  // inst.next 가 until 보다 앞인 동안 한 칸씩 예약
  function pump(e, inst, until) {
    var sd = inst.sd;
    while (inst.next < until) {
      var s = inst.step % LOOP, sw = (inst.step % 2) ? inst.tr.swing * sd : 0;
      playStep(e, inst, s, inst.next + sw);
      inst.step++; inst.next += sd;
    }
  }

  /* ---------- 라이브 상태 ---------- */
  var ctx = null, eng = null, unlocked = false, cur = null, wantTrack = null, timer = null, hiddenForced = null;
  var gestureOn = false, ctxCount = 0, fading = [];
  var EVS = ['pointerdown', 'touchend', 'mousedown', 'keydown', 'click'];

  function isHidden() { if (hiddenForced !== null) return hiddenForced; try { return !!global.document.hidden; } catch (x) { return false; } }
  function running() { return !!(ctx && ctx.state === 'running'); }
  function canSound() { return unlocked && running() && !S.muted && !isHidden(); }
  function emit() {
    var st = state();
    listeners.slice().forEach(function (cb) { try { cb(st); } catch (x) { /* 구독자 오류는 무시 */ } });
  }
  function state() { return { master: S.master, sfx: S.sfx, bgm: S.bgm, muted: S.muted, unlocked: unlocked, track: cur ? cur.name : null }; }

  function stopTimer() { if (timer) { clearInterval(timer); timer = null; } }
  function tick() {
    if (!cur || !running()) return;
    var now = ctx.currentTime;
    while (cur.next < now - 0.05) { cur.step++; cur.next += cur.sd; } // 밀렸으면 박자만 맞춰 건너뜀
    pump(eng, cur, now + 0.45);
  }
  function startTimer() { if (!timer) timer = setInterval(tick, 110); }
  function wireStatus() {
    syncBgm();
    if (running() && !S.muted && !isHidden()) startTimer();
  }
  function fadeOut(inst) {
    var t = ctx.currentTime;
    try { inst.gain.gain.cancelScheduledValues(t); inst.gain.gain.setTargetAtTime(0, t, 0.12); } catch (x) { /* 무시 */ }
    fading.push(inst);
    setTimeout(function () {
      try { inst.gain.disconnect(); inst.lead.disconnect(); } catch (x) { /* 무시 */ }
      var i = fading.indexOf(inst); if (i >= 0) fading.splice(i, 1);
    }, 1400);
  }
  function syncBgm() {
    if (!ctx || !eng) return;
    if (!canSound()) return;
    var want = wantTrack;
    if (cur && cur.name === want) return;
    if (cur) { fadeOut(cur); cur = null; }
    if (want) { cur = startTrack(eng, want, 0.8); if (cur) { startTimer(); tick(); } }
  }
  function syncRun() {
    if (!ctx) return;
    var should = unlocked && !S.muted && !isHidden();
    applyLevels(eng, S, true);
    if (should) {
      if (ctx.state !== 'running') {
        try { ctx.resume().then(wireStatus, function () { /* 제스처 필요 → 다음 제스처에서 재시도 */ }); } catch (x) { /* 무시 */ }
      } else wireStatus();
    } else {
      stopTimer();
      if (ctx.state === 'running') { try { ctx.suspend(); } catch (x) { /* 무시 */ } }
    }
  }

  function unlock() {
    try {
      if (!ctx) {
        var AC = global.AudioContext || global.webkitAudioContext;
        if (!AC) return false;
        ctx = new AC({ latencyHint: 'interactive' }); ctxCount++;
        eng = makeEngine(ctx);
        applyLevels(eng, S, false);
        try { ctx.onstatechange = function () { if (running()) { wireStatus(); detachGesture(); } }; } catch (x) { /* 무시 */ }
        // iOS: 제스처 안에서 무음 버퍼 한 번 재생해야 풀린다
        var b = ctx.createBuffer(1, 1, 22050), s = ctx.createBufferSource();
        s.buffer = b; s.connect(ctx.destination); s.start(0);
      }
      unlocked = true;
      syncRun();
      return true;
    } catch (x) { return false; }
  }
  function onGesture() { unlock(); if (running()) detachGesture(); }
  function attachGesture() {
    if (gestureOn || !global.document) return;
    gestureOn = true;
    EVS.forEach(function (n) { try { global.document.addEventListener(n, onGesture, { capture: true, passive: true }); } catch (x) { /* 무시 */ } });
  }
  function detachGesture() {
    if (!gestureOn) return;
    gestureOn = false;
    EVS.forEach(function (n) { try { global.document.removeEventListener(n, onGesture, { capture: true }); } catch (x) { /* 무시 */ } });
  }

  function sfx(name, o) {
    try {
      if (!canSound()) return false;
      return playSfx(eng, name, o || {}, ctx.currentTime + 0.005);
    } catch (x) { return false; }
  }
  function bgm(name) {
    if (name == null || name === '' || name === false) wantTrack = null;
    else if (TRACKS.hasOwnProperty(name)) wantTrack = name;
    else { try { console.warn('BrjAudio: 모르는 BGM 트랙', name); } catch (x) { /* 무시 */ } return; }
    if (!unlocked || !eng) return; // 잠금 전엔 기억만 — 해제되면 시작
    if (!wantTrack && cur) { fadeOut(cur); cur = null; stopTimer(); return; }
    syncBgm();
  }
  function setLevel(k, v) {
    S[k] = num01(v, S[k]); saveSettings();
    if (eng) applyLevels(eng, S, true);
    emit();
  }
  function muted(v) {
    if (v === undefined) return S.muted;
    var nv = v === 'toggle' ? !S.muted : !!v;
    if (nv !== S.muted) { S.muted = nv; saveSettings(); syncRun(); emit(); }
    return S.muted;
  }
  function onVis() { syncRun(); }

  /* ---------- 시험용: 오프라인 렌더 ---------- */
  function render(opt) {
    var OC = global.OfflineAudioContext || global.webkitOfflineAudioContext;
    var sr = opt.sampleRate || 44100, secs = opt.seconds || 2;
    var oc = new OC(1, Math.ceil(sr * secs), sr), keep = rnd;
    rnd = mulberry(opt.seed || 1);
    var e, inst;
    try {
      e = makeEngine(oc);
      applyLevels(e, opt.levels || S, false);
      (opt.sfx || []).forEach(function (ev) { playSfx(e, ev.name, { vol: ev.vol, rate: ev.rate }, ev.at == null ? 0.02 : ev.at); });
      if (opt.bgm) { inst = startTrack(e, opt.bgm, 0.03); if (inst) pump(e, inst, secs + 0.1); }
    } finally { rnd = keep; }
    return oc.startRendering().then(function (buf) {
      return { data: buf.getChannelData(0), played: e.played, dropped: e.dropped, sampleRate: sr };
    });
  }

  /* ---------- 공개 ---------- */
  loadSettings();
  if (global.document) {
    attachGesture();
    try { global.document.addEventListener('visibilitychange', onVis); } catch (x) { /* 무시 */ }
  }
  global.BrjAudio = {
    unlock: unlock, sfx: sfx, bgm: bgm,
    setMaster: function (v) { setLevel('master', v); },
    setSfx: function (v) { setLevel('sfx', v); },
    setBgm: function (v) { setLevel('bgm', v); },
    muted: muted, toggleMuted: function () { return muted('toggle'); },
    state: state,
    onChange: function (cb) {
      if (typeof cb !== 'function') return function () {};
      listeners.push(cb);
      return function () { var i = listeners.indexOf(cb); if (i >= 0) listeners.splice(i, 1); };
    },
    sfxNames: function () { return SFX_NAMES.slice(); },
    trackNames: function () { return TRACK_NAMES.slice(); },
    version: 1,
    // 시험용
    _render: render,
    _sfxDur: function (n) { return SFX[n] ? SFX[n].d : 0; },
    _forceHidden: function (v) { hiddenForced = v === null ? null : !!v; syncRun(); },
    _debug: function () {
      return { unlocked: unlocked, ctxState: ctx ? ctx.state : null, ctxCount: ctxCount, track: cur ? cur.name : null, step: cur ? cur.step : 0,
        want: wantTrack, timer: !!timer, played: eng ? eng.played : 0, dropped: eng ? eng.dropped : 0,
        active: eng ? eng.active.filter(function (x) { return x > ctx.currentTime; }).length : 0,
        masterGain: eng ? eng.master.gain.value : null, time: ctx ? ctx.currentTime : 0 };
    }
  };
})(typeof window !== 'undefined' ? window : this);
