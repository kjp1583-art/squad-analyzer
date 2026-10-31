/* brjhunt_audio.js v2 — 브장신 사냥터 효과음 + BGM (전부 Web Audio 합성 · 외부 음원/샘플 없음)
 *
 * 전역 BrjAudio = { unlock, sfx, bgm, setMaster, setSfx, setBgm, muted, state, onChange, setIntensity, ... }
 *   unlock()             첫 터치/클릭에서 호출(안 불러도 첫 제스처에 스스로 건다). 그 전에는 AudioContext 도 만들지 않고 소리도 안 낸다.
 *   sfx(name,opts)       효과음 한 번. opts = { vol 0~2, rate 음높이배수, pan -1~1, x -1~1(화면 위치→패닝), dist 0~1(멀리 → 작고 둔탁하게) }.
 *                        모르는 이름·잠금 전·음소거·탭 숨김이면 조용히 false. 이름 목록은 sfxNames() · 쓰는 법은 sfx_names.md.
 *   skillSfx(id,phase)   스킬 id + 'charge'(전조)|'cast'(발동)|'tail'(여운) → 효과음 이름. 스킬 효과음을 직접 호출해도 된다.
 *   bgm(track|null)      BGM(field1~6 · boss · menu) 바꾸기 / null 이면 끄기. 잠금 전에 불러도 기억했다가 해제되면 시작.
 *   setIntensity(0~1)    전투 강도: 낮으면 패드·베이스만, 올릴수록 하이햇 → 킥·스네어 → 아르페지오 → 리드 → 심벌·라이저 순으로 켜진다.
 *   setMaster/setSfx/setBgm(0~1)  볼륨. 저장됨.
 *   muted()              지금 음소거 여부(bool). muted(true|false) 로 설정, muted('toggle') 로 뒤집기.
 *   state()              {master,sfx,bgm,muted, unlocked, track, intensity}   onChange(cb) → 해제 함수
 *
 * 설계 메모
 *  - 소리 길: 효과음/BGM 버스 + 리버브(합성 임펄스 컨볼버) → 컴프레서 → 고역통과(직류 제거) → 마스터 → 리미터 → tanh 소프트 클립(최대 0.95) → 스테레오 출력.
 *    마스터를 1 로 올려도 클리핑 없음.
 *  - 효과음 한 번 = 여러 층(저음 쿵 + 노이즈 크랙 + 몸통 + 반짝/잔향). 같은 이름을 부를 때마다 변형(라운드 로빈)·음높이·음량·좌우가 조금씩 달라진다.
 *  - 효과음 동시 발음: 우선순위별 상한(일반 10 · 스킬 16 · 중요 24) + 같은 이름 최소 간격. 넘치면 새 소리를 버린다.
 *  - BGM: 16마디(인트로 2 + A 4 + B 4 + A′ 4 + 되돌림 2). 한 바퀴 돈 뒤에는 인트로를 건너뛰고 A 로 돌아온다(박자 예약이 끊김 없이 이어진다).
 *  - 탭 숨김/음소거: AudioContext 를 suspend → BGM 스케줄러도 멈춘다. 돌아오면 이어서.
 *  - 설정은 localStorage('brjhunt_audio_v1') — 막혀 있어도(try/catch) 기본값으로 동작.
 *  - _render() 는 시험용: OfflineAudioContext 로 같은 합성 코드를 돌려 파형을 돌려준다.
 */
(function (global) {
  'use strict';
  var KEY = 'brjhunt_audio_v1';
  var DEF = { master: 0.6, sfx: 0.8, bgm: 0.35, muted: false };
  var S = { master: DEF.master, sfx: DEF.sfx, bgm: DEF.bgm, muted: DEF.muted };
  var INTENSITY = 0.9;
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
  function saveSettings() {
    try { global.localStorage.setItem(KEY, JSON.stringify({ master: S.master, sfx: S.sfx, bgm: S.bgm, muted: S.muted })); } catch (e) { /* 막힘 */ }
  }

  function mulberry(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function mtof(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  function clampN(v, lo, hi, d) { v = Number(v); if (!isFinite(v)) return d; return v < lo ? lo : v > hi ? hi : v; }

  /* ---------- 엔진(컨텍스트 하나에 붙는 소리 길) ---------- */
  var LIMIT = (function () {
    var n = 2049, c = new Float32Array(n);
    for (var i = 0; i < n; i++) { var u = i / (n - 1) * 2 - 1; c[i] = 0.95 * Math.tanh(2 * u / 0.95); }
    return c;
  })();
  var SFX_GAIN = 2.2, BGM_GAIN = 0.6; // 효과음이 BGM 위로 또렷이 얹히게(BGM 은 층이 많아 합이 크다)

  // 합성 임펄스 응답: 초기 반사 몇 개 + 점점 어두워지며 사라지는 노이즈 (고정 시드 → 재현 가능)
  function makeIR(ctx, secs) {
    var sr = ctx.sampleRate, n = Math.floor(sr * secs), buf = ctx.createBuffer(2, n, sr), R = mulberry(4242);
    for (var ch = 0; ch < 2; ch++) {
      var d = buf.getChannelData(ch), lp = 0, pre = Math.floor(sr * 0.006);
      for (var i = pre; i < n; i++) {
        var t = (i - pre) / (n - pre), env = Math.pow(1 - t, 2.6), k = 0.62 * (1 - t) + 0.05;
        lp += ((R() * 2 - 1) - lp) * k;
        d[i] = lp * env * 1.6;
      }
      [0.011, 0.019, 0.031, 0.047].forEach(function (s, j) {
        var p = Math.floor(sr * (s + (ch ? 0.0023 : 0)));
        if (p < n) d[p] += (ch ? -1 : 1) * 0.5 / (j + 1);
      });
    }
    return buf;
  }

  function makeEngine(ctx) {
    var e = { ctx: ctx, active: [], last: {}, rr: {}, played: 0, dropped: 0 };
    e.sfxBus = ctx.createGain(); e.bgmBus = ctx.createGain();
    e.rvSfx = ctx.createGain(); e.rvBgm = ctx.createGain();
    e.conv = ctx.createConvolver(); e.conv.buffer = makeIR(ctx, 1.5);
    e.rvOut = ctx.createGain(); e.rvOut.gain.value = 0.9;
    e.comp = ctx.createDynamicsCompressor();
    try {
      e.comp.threshold.value = -18; e.comp.knee.value = 12; e.comp.ratio.value = 4;
      e.comp.attack.value = 0.004; e.comp.release.value = 0.16;
    } catch (x) { /* 구형 */ }
    e.lim = ctx.createDynamicsCompressor();
    try {
      e.lim.threshold.value = -4; e.lim.knee.value = 0; e.lim.ratio.value = 20;
      e.lim.attack.value = 0.001; e.lim.release.value = 0.08;
    } catch (x) { /* 구형 */ }
    e.hp = ctx.createBiquadFilter(); e.hp.type = 'highpass'; e.hp.frequency.value = 28; e.hp.Q.value = 0.5;
    e.master = ctx.createGain();
    e.pre = ctx.createGain(); e.pre.gain.value = 0.5;
    e.shaper = ctx.createWaveShaper(); e.shaper.curve = LIMIT;
    e.sfxBus.connect(e.comp); e.bgmBus.connect(e.comp);
    e.rvSfx.connect(e.conv); e.rvBgm.connect(e.conv); e.conv.connect(e.rvOut); e.rvOut.connect(e.comp);
    e.comp.connect(e.lim); e.lim.connect(e.hp); e.hp.connect(e.master); e.master.connect(e.pre); e.pre.connect(e.shaper); e.shaper.connect(ctx.destination);
    var sr = ctx.sampleRate, nb = ctx.createBuffer(1, sr, sr), d = nb.getChannelData(0), R = mulberry(99);
    for (var i = 0; i < sr; i++) d[i] = R() * 2 - 1;
    e.noise = nb;
    return e;
  }
  function applyLevels(e, lv, smooth) {
    var t = e.ctx.currentTime, tc = 0.03;
    function set(p, v) { if (smooth) { try { p.setTargetAtTime(v, t, tc); return; } catch (x) { /* 폴백 */ } } p.value = v; }
    set(e.master.gain, lv.muted ? 0 : lv.master);
    set(e.sfxBus.gain, lv.sfx * SFX_GAIN); set(e.rvSfx.gain, lv.sfx * SFX_GAIN);
    set(e.bgmBus.gain, lv.bgm * BGM_GAIN); set(e.rvBgm.gain, lv.bgm * BGM_GAIN);
  }

  /* ---------- 소리 조각(오실레이터 · 노이즈) ---------- */
  // 오실레이터 한 음. o: type f f2(스윕 끝) sw(스윕 비율) dur vol a(어택) hold dec/sus(감쇠→유지 레벨) r(릴리즈: 있으면 '유지형')
  //   det lp lp2 lpt q(필터) fm{r,i,dec} vib{rate,depth,delay}
  function osc(e, dest, t, dur, o, r, v) {
    var c = e.ctx, nyq = c.sampleRate * 0.45;
    function cf(x) { return Math.min(Math.max(x, 20), nyq); }
    var f = cf(o.f * r), a = Math.max(0.0008, Math.min(o.a == null ? 0.004 : o.a, dur * 0.5)), vol = (o.vol == null ? 0.3 : o.vol) * v;
    var sus = o.r != null, rel = sus ? o.r : 0, endT = t + dur, stopT = endT + rel + 0.04;
    var os = c.createOscillator(), g = c.createGain(), out = os;
    os.type = o.type || 'sine';
    os.frequency.setValueAtTime(f, t);
    if (o.f2) os.frequency.exponentialRampToValueAtTime(cf(o.f2 * r), t + dur * (o.sw || 1));
    if (o.det) os.detune.value = o.det;
    if (o.fm) {
      var m = c.createOscillator(), mg = c.createGain(), dev = f * o.fm.i;
      m.frequency.value = Math.min(f * o.fm.r, nyq);
      mg.gain.setValueAtTime(dev, t);
      mg.gain.exponentialRampToValueAtTime(Math.max(0.01, dev * 0.03), t + Math.max(0.05, o.fm.dec || dur));
      m.connect(mg); mg.connect(os.frequency); m.start(t); m.stop(stopT);
    }
    if (o.vib) {
      var lfo = c.createOscillator(), lg = c.createGain();
      lfo.frequency.value = o.vib.rate || 5.2; lg.gain.value = o.vib.depth || 10; lfo.connect(lg); lg.connect(os.detune);
      lfo.start(t + (o.vib.delay || 0)); lfo.stop(stopT);
    }
    if (o.lp) {
      var fl = c.createBiquadFilter(); fl.type = 'lowpass'; fl.Q.value = o.q || 0.7;
      fl.frequency.setValueAtTime(cf(o.lp), t);
      if (o.lp2) fl.frequency.exponentialRampToValueAtTime(cf(o.lp2), t + (o.lpt || dur));
      os.connect(fl); out = fl;
    }
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(vol, t + a);
    var lvl = vol;
    if (o.dec) {
      lvl = Math.max(0.0002, vol * (o.sus == null ? 0.3 : o.sus));
      var td = Math.min(t + a + o.dec, endT - 0.002);
      if (td > t + a + 0.001) g.gain.exponentialRampToValueAtTime(lvl, td);
    } else if (o.hold) {
      var th = Math.min(t + a + o.hold, endT - 0.01);
      if (th > t + a) g.gain.setValueAtTime(vol, th);
    }
    if (sus) { g.gain.setValueAtTime(lvl, Math.max(endT, t + a + 0.002)); g.gain.exponentialRampToValueAtTime(0.0001, endT + rel); }
    else g.gain.exponentialRampToValueAtTime(0.0001, endT);
    out.connect(g);
    if (o.pan && c.createStereoPanner) { var pn = c.createStereoPanner(); pn.pan.value = o.pan; g.connect(pn); pn.connect(dest); } else g.connect(dest);
    os.start(t); os.stop(stopT);
  }
  // 필터 노이즈 한 번. o: type f f2 q dur vol a hold
  function nz(e, dest, t, dur, o, r, v) {
    var c = e.ctx, nyq = c.sampleRate * 0.45;
    function cf(x) { return Math.min(Math.max(x, 20), nyq); }
    var s = c.createBufferSource(), fl = c.createBiquadFilter(), g = c.createGain();
    var a = Math.max(0.0008, Math.min(o.a == null ? 0.003 : o.a, dur * 0.8)), vol = (o.vol == null ? 0.3 : o.vol) * v;
    s.buffer = e.noise; s.loop = true;
    fl.type = o.type || 'bandpass'; fl.Q.value = o.q || 0.8;
    fl.frequency.setValueAtTime(cf(o.f * r), t);
    if (o.f2) fl.frequency.exponentialRampToValueAtTime(cf(o.f2 * r), t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(vol, t + a);
    if (o.hold) { var th = Math.min(t + a + o.hold, t + dur - 0.01); if (th > t + a) g.gain.setValueAtTime(vol, th); }
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(fl); fl.connect(g); g.connect(dest);
    s.start(t, rnd() * 0.8); s.stop(t + dur + 0.04);
  }
  // 소리 조각 도우미: 시작 t0, 음량 배수 v, 음높이 배수 r, 도착 dest
  function H(e, dest, t0, v, r) {
    return {
      tone: function (at, o) { osc(e, dest, t0 + at, o.dur, o, r, v); },
      noise: function (at, o) { nz(e, dest, t0 + at, o.dur, o, r, v); }
    };
  }

  /* 층 쌓기용 매크로 */
  function thump(h, at, f, f2, dur, vol) { // 저음 쿵
    h.tone(at, { f: f, f2: f2, sw: 0.4, dur: dur, vol: vol, a: 0.002 });
    h.tone(at, { type: 'triangle', f: f * 1.8, f2: f2 * 1.4, sw: 0.3, dur: dur * 0.55, vol: vol * 0.35, a: 0.002 });
  }
  function crack(h, at, vol, dur, f) { // 노이즈 크랙(타격 순간의 딱)
    f = f || 2600;
    h.noise(at, { type: 'highpass', f: f, dur: dur || 0.04, vol: vol, a: 0.0012 });
    h.tone(at, { type: 'square', f: f * 0.7, f2: f * 0.25, dur: 0.012, vol: vol * 0.3, a: 0.0008, lp: 5000 });
  }
  function whoosh(h, at, dur, f, f2, vol, q) { // 휘두름: 필터 스윕 노이즈
    h.noise(at, { type: 'bandpass', f: f, f2: f2, q: q || 1.2, dur: dur, vol: vol, a: dur * 0.45 });
  }
  function bell(h, at, f, dur, vol, ratio, idx) { // 금속 종(FM)
    h.tone(at, { f: f, dur: dur, vol: vol, a: 0.002, fm: { r: ratio || 3.5, i: idx || 1.5, dec: dur * 0.6 } });
  }
  function sparkle(h, at, n, base, spread, span, vol, dur) { // 흩뿌린 반짝
    for (var i = 0; i < n; i++) bell(h, at + rnd() * span, base * (1 + rnd() * spread), dur || 0.3, vol, 3.01, 0.9);
  }
  function pick(v, a) { return a[v % a.length]; }

  /* ---------- 효과음 ---------- */
  // d: 소리가 사라지는 길이(초, 잔향 포함) · p: 우선순위(0 일반 · 1 스킬 · 2 중요) · gap: 같은 이름 최소 간격 · jit: 음높이 무작위 폭
  // wet: 잔향 보내는 양 · n: 변형 개수(부를 때마다 돌아가며)
  var SFX = {}, SFX_NAMES = [];
  function def(name, d, p, gap, jit, wet, fn, n) {
    SFX[name] = { d: d, p: p, gap: gap, jit: jit, wet: wet, fn: fn, n: n || 3 };
    SFX_NAMES.push(name);
  }

  /* -- 휘두름 -- */
  def('swing1', 0.28, 0, 0.06, 0.06, 0.04, function (h, v) {
    var f = pick(v, [900, 1100, 780]);
    whoosh(h, 0, 0.17, f, f * 4, 0.5, 1.3);
    h.tone(0, { type: 'triangle', f: 300, f2: 700, dur: 0.1, vol: 0.07 });
  });
  def('swing2', 0.28, 0, 0.06, 0.06, 0.04, function (h, v) {
    var f = pick(v, [3600, 4200, 3200]);
    whoosh(h, 0, 0.18, f, f / 5, 0.5, 1.2);
    h.tone(0, { type: 'triangle', f: 760, f2: 320, dur: 0.12, vol: 0.07 });
  });
  def('swing3', 0.4, 0, 0.08, 0.05, 0.06, function (h, v) {
    whoosh(h, 0, 0.24, pick(v, [350, 420, 300]), 2400, 0.65, 1.0);
    h.noise(0.1, { type: 'highpass', f: 4000, dur: 0.1, vol: 0.2, a: 0.01 });
    h.tone(0, { type: 'sawtooth', f: 110, f2: 260, dur: 0.22, vol: 0.1, lp: 700, a: 0.08 });
  });
  def('swing_big', 0.6, 1, 0.1, 0.04, 0.08, function (h, v) {
    whoosh(h, 0, 0.34, pick(v, [220, 260, 200]), 3200, 0.8, 0.9);
    h.tone(0, { f: 70, f2: 150, dur: 0.3, vol: 0.3, a: 0.12 });
    h.noise(0.16, { type: 'highpass', f: 3500, dur: 0.18, vol: 0.2, a: 0.02 });
  });

  /* -- 타격 · 몬스터 -- */
  def('hit', 0.32, 0, 0.035, 0.07, 0.12, function (h, v) {
    thump(h, 0, pick(v, [190, 170, 210]), pick(v, [62, 58, 70]), 0.15, 0.75);
    crack(h, 0, 0.55, 0.035, pick(v, [2600, 3100, 2300]));
    h.noise(0, { type: 'bandpass', f: pick(v, [1300, 1000, 1600]), f2: 450, q: 0.9, dur: 0.09, vol: 0.4, a: 0.002 });
    h.tone(0.004, { f: pick(v, [520, 460, 600]), f2: 200, dur: 0.07, vol: 0.25 });
  });
  def('hit_heavy', 0.7, 1, 0.06, 0.05, 0.25, function (h, v) {
    thump(h, 0, pick(v, [130, 120, 145]), 38, 0.32, 1.0);
    crack(h, 0, 0.75, 0.05, 2200);
    h.noise(0, { type: 'lowpass', f: 2400, f2: 200, q: 0.7, dur: 0.22, vol: 0.5, a: 0.002 });
    bell(h, 0.005, 1800, 0.12, 0.08, 2.7, 2);
  });
  def('crit', 0.8, 1, 0.05, 0.04, 0.3, function (h, v) {
    thump(h, 0, pick(v, [150, 140, 165]), 44, 0.28, 0.95);
    crack(h, 0, 0.8, 0.05, 2800);
    bell(h, 0.01, pick(v, [2349, 2093, 2637]), 0.5, 0.22, 2.76, 2.2);
    h.tone(0.02, { type: 'sawtooth', f: 700, f2: 2600, dur: 0.14, vol: 0.14, lp: 6000 });
    h.noise(0.03, { type: 'highpass', f: 6000, dur: 0.25, vol: 0.16, a: 0.01 });
    bell(h, 0.08, 3136, 0.35, 0.1, 3.01, 0.9); bell(h, 0.12, 4186, 0.3, 0.07, 3.01, 0.9);
  });
  def('kill', 0.5, 0, 0.04, 0.1, 0.18, function (h, v) {
    h.tone(0, { f: pick(v, [720, 640, 820]), f2: 150, sw: 0.8, dur: 0.17, vol: 0.5, a: 0.002 });
    thump(h, 0, 150, 50, 0.18, 0.6);
    h.noise(0, { type: 'lowpass', f: 2500, f2: 300, q: 0.7, dur: 0.2, vol: 0.4, a: 0.003 });
    h.noise(0.02, { type: 'highpass', f: 5000, dur: 0.12, vol: 0.14 });
    bell(h, 0.07, pick(v, [1568, 1760, 1397]), 0.2, 0.1);
  });
  def('mon_hurt', 0.25, 0, 0.05, 0.1, 0.06, function (h, v) {
    h.tone(0, { type: 'square', f: pick(v, [520, 600, 460]), f2: pick(v, [300, 340, 260]), dur: 0.09, vol: 0.16, lp: 3000 });
    h.noise(0, { type: 'bandpass', f: 1400, q: 1, dur: 0.05, vol: 0.25 });
  });
  def('mon_die', 0.85, 0, 0.05, 0.08, 0.22, function (h, v) {
    thump(h, 0, pick(v, [200, 180, 220]), 45, 0.3, 0.8);
    h.noise(0, { type: 'lowpass', f: 3000, f2: 150, q: 0.7, dur: 0.35, vol: 0.55, a: 0.003 });
    h.tone(0, { f: 900, f2: 180, dur: 0.22, vol: 0.25 });
    crack(h, 0, 0.4, 0.04, 2400);
    sparkle(h, 0.08, 3, 2000, 0.6, 0.15, 0.06, 0.22);
  });
  def('mon_die_elite', 1.6, 2, 0.15, 0.04, 0.35, function (h) {
    thump(h, 0, 110, 32, 0.6, 1.0);
    h.noise(0, { type: 'lowpass', f: 4000, f2: 100, q: 0.7, dur: 0.7, vol: 0.7, a: 0.003 });
    crack(h, 0, 0.8, 0.08, 2000);
    bell(h, 0.02, 1200, 0.8, 0.2, 2.3, 2.5);
    sparkle(h, 0.15, 6, 2400, 1.2, 0.5, 0.06, 0.4);
    h.tone(0.05, { type: 'sawtooth', f: 400, f2: 60, dur: 0.6, vol: 0.14, lp: 900 });
  }, 1);
  def('elite_spawn', 1.9, 2, 0.4, 0.03, 0.4, function (h) {
    h.tone(0, { type: 'sawtooth', f: 60, f2: 92, dur: 0.9, vol: 0.35, lp: 300, a: 0.3 });
    h.tone(0, { f: 45, f2: 36, dur: 1.0, vol: 0.5, a: 0.2 });
    h.noise(0, { type: 'lowpass', f: 200, dur: 0.9, vol: 0.4, a: 0.4 });
    bell(h, 0.1, 196, 1.3, 0.2, 1.41, 3);
    h.noise(0.5, { type: 'highpass', f: 5000, dur: 0.6, vol: 0.1, a: 0.3 });
  }, 1);

  /* -- 코인 -- */
  def('coin', 0.85, 0, 0.04, 0.03, 0.22, function (h, v) {
    var f = pick(v, [1568, 1661, 1480]);
    h.noise(0, { type: 'highpass', f: 6000, dur: 0.012, vol: 0.12 });
    bell(h, 0, f, 0.35, 0.22, 1.5, 1.2);
    bell(h, 0.06, f * 1.335, 0.55, 0.26, 1.5, 1.2);
    h.tone(0.06, { f: f * 2.67, dur: 0.3, vol: 0.07 });
  });
  def('coin_big', 1.3, 1, 0.08, 0.03, 0.25, function (h, v) {
    [0, 0.05, 0.1, 0.155].forEach(function (t, i) {
      bell(h, t, 1318 * Math.pow(1.122, i * 2 + v), 0.5, 0.2, 1.5, 1.2);
      h.noise(t, { type: 'highpass', f: 6500, dur: 0.02, vol: 0.1 });
    });
    thump(h, 0, 160, 80, 0.1, 0.35);
    sparkle(h, 0.15, 4, 3000, 0.5, 0.3, 0.05, 0.3);
  });
  def('coin_drop', 0.8, 0, 0.06, 0.04, 0.2, function (h, v) {
    var f = pick(v, [1250, 1180, 1330]);
    bell(h, 0, f, 0.3, 0.2, 1.5, 1.0); bell(h, 0.12, f * 0.97, 0.22, 0.12, 1.5, 1.0); bell(h, 0.2, f * 0.95, 0.16, 0.07, 1.5, 1.0);
    h.noise(0, { type: 'bandpass', f: 4500, q: 2, dur: 0.02, vol: 0.12 });
  });
  def('pickup', 0.5, 0, 0.05, 0.05, 0.15, function (h, v) {
    h.tone(0, { f: pick(v, [500, 540, 470]), f2: 900, dur: 0.08, vol: 0.2, a: 0.004 });
    bell(h, 0.03, 1318, 0.25, 0.14);
  });

  /* -- 움직임 -- */
  def('jump', 0.3, 0, 0.08, 0.06, 0.05, function (h, v) {
    whoosh(h, 0, 0.12, 300, 1400, 0.18, 0.8);
    h.tone(0, { f: pick(v, [260, 290, 240]), f2: pick(v, [520, 580, 480]), dur: 0.12, vol: 0.22, a: 0.01 });
    h.noise(0, { type: 'bandpass', f: 1800, q: 1, dur: 0.03, vol: 0.12 });
  });
  def('jump2', 0.45, 0, 0.1, 0.05, 0.1, function (h, v) {
    whoosh(h, 0, 0.14, 600, 4500, 0.22, 0.9);
    h.noise(0.04, { type: 'bandpass', f: 2400, q: 1.4, dur: 0.05, vol: 0.14 });
    h.tone(0, { f: pick(v, [500, 540, 470]), f2: 1200, dur: 0.12, vol: 0.18, a: 0.008 });
    bell(h, 0.05, 2093, 0.25, 0.1, 3.01, 0.8);
  });
  def('land', 0.25, 0, 0.07, 0.06, 0.05, function (h, v) {
    thump(h, 0, pick(v, [110, 100, 120]), pick(v, [55, 50, 60]), 0.1, 0.5);
    h.noise(0, { type: 'lowpass', f: 700, f2: 200, dur: 0.09, vol: 0.35, a: 0.002 });
  });
  def('land_hard', 0.6, 0, 0.12, 0.04, 0.12, function (h) {
    thump(h, 0, 90, 38, 0.22, 0.8);
    h.noise(0, { type: 'lowpass', f: 1500, f2: 200, dur: 0.2, vol: 0.5, a: 0.002 });
    h.noise(0.03, { type: 'highpass', f: 3000, dur: 0.15, vol: 0.12, a: 0.01 });
  }, 2);
  def('step', 0.14, 0, 0.1, 0.1, 0.03, function (h, v) {
    h.noise(0, { type: 'bandpass', f: pick(v, [800, 1000, 700, 900]), q: 1.5, dur: 0.04, vol: 0.22, a: 0.001 });
    h.tone(0, { f: 140, f2: 80, dur: 0.05, vol: 0.2, a: 0.001 });
  }, 4);
  def('drop_down', 0.3, 0, 0.1, 0.05, 0.04, function (h) {
    h.noise(0, { type: 'bandpass', f: 1200, f2: 400, q: 1, dur: 0.14, vol: 0.2, a: 0.02 });
    h.tone(0, { type: 'triangle', f: 420, f2: 200, dur: 0.12, vol: 0.12 });
  }, 1);

  /* -- 플레이어 -- */
  def('hurt', 0.55, 2, 0.12, 0.05, 0.12, function (h, v) {
    thump(h, 0, 170, 60, 0.2, 0.8);
    h.noise(0, { type: 'bandpass', f: 1800, f2: 600, dur: 0.12, vol: 0.45, a: 0.002 });
    h.tone(0, { type: 'sawtooth', f: pick(v, [520, 480, 560]), f2: 200, dur: 0.26, vol: 0.2, lp: 2000, a: 0.005 });
    h.tone(0.02, { f: 320, f2: 150, dur: 0.2, vol: 0.2 });
  });
  def('hurt_heavy', 0.9, 2, 0.2, 0.04, 0.2, function (h) {
    thump(h, 0, 120, 38, 0.4, 1.0);
    crack(h, 0, 0.6, 0.05, 1800);
    h.noise(0, { type: 'lowpass', f: 2000, f2: 150, dur: 0.3, vol: 0.5, a: 0.002 });
    h.tone(0, { type: 'sawtooth', f: 440, f2: 110, dur: 0.4, vol: 0.22, lp: 1600, a: 0.005 });
    h.tone(0.05, { type: 'square', f: 240, f2: 90, dur: 0.35, vol: 0.1, lp: 900 });
  }, 2);
  def('shield_block', 0.9, 1, 0.08, 0.04, 0.3, function (h, v) {
    bell(h, 0, pick(v, [1400, 1300, 1500]), 0.5, 0.35, 2.4, 3.5);
    crack(h, 0, 0.5, 0.04, 3200);
    thump(h, 0, 200, 90, 0.1, 0.5);
    h.noise(0, { type: 'bandpass', f: 3500, q: 1.5, dur: 0.12, vol: 0.2 });
  });
  def('die', 2.0, 2, 0.5, 0.02, 0.35, function () {
    var h = arguments[0];
    h.tone(0, { f: 700, f2: 70, dur: 0.9, vol: 0.3, a: 0.01 });
    thump(h, 0, 140, 40, 0.5, 0.9);
    h.noise(0, { type: 'lowpass', f: 1200, f2: 100, dur: 0.8, vol: 0.35, a: 0.01 });
    h.tone(0, { type: 'sawtooth', f: 300, f2: 60, dur: 0.9, vol: 0.2, lp: 600 });
    bell(h, 0.5, 330, 1.2, 0.12, 2.01, 1.0);
  }, 1);
  def('revive', 2.2, 2, 0.5, 0.02, 0.4, function () {
    var h = arguments[0];
    [67, 72, 76, 79, 84].forEach(function (n, i) { bell(h, i * 0.075, mtof(n), 0.6, 0.2, 2.0, 1.0); });
    [60, 67, 72, 76].forEach(function (n) { h.tone(0.3, { type: 'triangle', f: mtof(n), dur: 1.4, vol: 0.1, a: 0.1, hold: 0.4 }); });
    h.tone(0, { f: 55, f2: 98, dur: 0.4, vol: 0.45, a: 0.05 });
    h.noise(0.2, { type: 'highpass', f: 6000, dur: 0.7, vol: 0.1, a: 0.2 });
    sparkle(h, 0.4, 5, 2600, 0.8, 0.6, 0.06, 0.4);
  }, 1);

  /* -- 성장 -- */
  def('levelup', 2.3, 2, 0.3, 0, 0.35, function () {
    var h = arguments[0];
    [72, 76, 79, 84, 88, 91].forEach(function (n, i) {
      h.tone(i * 0.07, { type: 'triangle', f: mtof(n), dur: 0.4, vol: 0.22 });
      bell(h, i * 0.07, mtof(n + 12), 0.4, 0.1, 2.0, 1.0);
    });
    [72, 79, 84, 88].forEach(function (n) {
      h.tone(0.45, { type: 'triangle', f: mtof(n), dur: 1.2, vol: 0.12, hold: 0.3 });
      h.tone(0.45, { type: 'sawtooth', f: mtof(n), dur: 1.0, vol: 0.04, lp: 2500, hold: 0.2 });
    });
    thump(h, 0, 100, 45, 0.3, 0.6);
    h.noise(0.3, { type: 'highpass', f: 6000, dur: 0.7, vol: 0.12, a: 0.15 });
    sparkle(h, 0.5, 6, 3000, 0.8, 0.8, 0.05, 0.5);
  }, 1);
  def('awaken', 4.2, 2, 1.0, 0, 0.45, function () {
    var h = arguments[0];
    h.noise(0, { type: 'bandpass', f: 150, f2: 7000, q: 1.5, dur: 1.4, vol: 0.5, a: 1.0 });
    h.tone(0, { type: 'sawtooth', f: 70, f2: 280, dur: 1.4, vol: 0.3, lp: 1500, a: 0.9 });
    h.tone(0, { f: 55, f2: 110, dur: 1.4, vol: 0.3, a: 0.8 });
    thump(h, 1.4, 100, 28, 1.2, 1.0);
    crack(h, 1.4, 0.7, 0.1, 2000);
    h.noise(1.4, { type: 'highpass', f: 5000, dur: 2.0, vol: 0.3, a: 0.01 });
    [48, 55, 60, 64, 67, 72].forEach(function (n) {
      h.tone(1.4, { type: 'sawtooth', f: mtof(n), dur: 2.0, vol: 0.05, lp: 2200, det: -7, a: 0.1, hold: 0.6 });
      h.tone(1.4, { type: 'sawtooth', f: mtof(n), dur: 2.0, vol: 0.05, lp: 2200, det: 7, a: 0.1, hold: 0.6 });
      h.tone(1.4, { f: mtof(n + 12), dur: 2.0, vol: 0.06, a: 0.1, hold: 0.6 });
    });
    sparkle(h, 1.4, 9, 3500, 1.0, 1.2, 0.05, 0.6);
  }, 1);
  def('combo_up', 0.35, 0, 0.05, 0.02, 0.1, function (h) {
    bell(h, 0, 1046, 0.18, 0.18, 2, 1.2);
    h.tone(0, { type: 'triangle', f: 1046, f2: 1568, dur: 0.06, vol: 0.14 });
  }, 1);

  /* -- 화면(UI) -- */
  def('click', 0.12, 0, 0.03, 0.03, 0.02, function (h) {
    h.noise(0, { type: 'bandpass', f: 2400, q: 2.5, dur: 0.018, vol: 0.3, a: 0.0008 });
    h.tone(0, { f: 900, f2: 500, dur: 0.03, vol: 0.22, a: 0.001 });
    h.tone(0, { type: 'triangle', f: 1500, dur: 0.015, vol: 0.1, a: 0.001 });
  }, 1);
  def('tab', 0.22, 0, 0.04, 0.03, 0.04, function (h) {
    h.noise(0, { type: 'bandpass', f: 1800, q: 3, dur: 0.02, vol: 0.2, a: 0.001 });
    h.tone(0, { f: 520, f2: 700, dur: 0.08, vol: 0.2 });
    bell(h, 0.02, 1040, 0.1, 0.08, 1.0, 0.5);
  }, 1);
  def('error', 0.6, 2, 0.15, 0.02, 0.1, function (h) {
    thump(h, 0, 120, 70, 0.12, 0.6);
    h.tone(0, { type: 'sawtooth', f: 150, f2: 130, dur: 0.13, vol: 0.22, lp: 900 });
    h.tone(0.15, { type: 'sawtooth', f: 130, f2: 105, dur: 0.2, vol: 0.22, lp: 800 });
    thump(h, 0.15, 100, 60, 0.12, 0.5);
  }, 1);
  def('ui_open', 0.6, 0, 0.1, 0.02, 0.15, function (h) {
    whoosh(h, 0, 0.18, 400, 2500, 0.2, 1);
    bell(h, 0.1, 1318, 0.3, 0.14); h.tone(0.1, { f: 660, dur: 0.2, vol: 0.08 });
  }, 1);
  def('ui_close', 0.5, 0, 0.1, 0.02, 0.12, function (h) {
    whoosh(h, 0, 0.16, 2500, 400, 0.18, 1);
    bell(h, 0.02, 880, 0.25, 0.12);
  }, 1);
  def('auto_on', 0.7, 0, 0.1, 0.02, 0.15, function (h) {
    bell(h, 0, 988, 0.2, 0.2); bell(h, 0.07, 1319, 0.4, 0.22);
    h.noise(0, { type: 'bandpass', f: 3500, q: 2, dur: 0.02, vol: 0.1 });
  }, 1);
  def('auto_off', 0.7, 0, 0.1, 0.02, 0.15, function (h) {
    bell(h, 0, 1319, 0.2, 0.2); bell(h, 0.07, 988, 0.4, 0.2);
    h.noise(0, { type: 'bandpass', f: 2500, q: 2, dur: 0.02, vol: 0.1 });
  }, 1);
  def('equip', 0.55, 1, 0.08, 0.04, 0.2, function (h) {
    bell(h, 0, 2200, 0.25, 0.2, 2.9, 2);
    thump(h, 0, 150, 80, 0.08, 0.5);
    h.noise(0, { type: 'bandpass', f: 4000, q: 1.5, dur: 0.03, vol: 0.15 });
  }, 1);
  def('enhance_ok', 1.7, 2, 0.2, 0.02, 0.35, function (h) {
    thump(h, 0, 120, 55, 0.2, 0.8);
    crack(h, 0, 0.7, 0.05, 2600);
    bell(h, 0, 880, 0.8, 0.3, 2.7, 4);
    [1047, 1319, 1568, 2093].forEach(function (f, i) { bell(h, 0.2 + i * 0.08, f, 0.5, 0.18, 2.0, 1.0); });
    h.noise(0.5, { type: 'highpass', f: 6500, dur: 0.5, vol: 0.1, a: 0.1 });
    sparkle(h, 0.5, 4, 3200, 0.6, 0.4, 0.05, 0.4);
  }, 1);
  def('enhance_fail', 1.4, 2, 0.2, 0.02, 0.3, function (h, v) {
    crack(h, 0, 0.8, 0.08, 1800);
    for (var i = 0; i < 8; i++) bell(h, 0.01 + rnd() * 0.15, 3000 + rnd() * 3500, 0.12, 0.09, 3.01, 0.6);
    thump(h, 0.03, 110, 32, 0.4, 0.9);
    h.noise(0.03, { type: 'lowpass', f: 1000, f2: 100, dur: 0.5, vol: 0.3 });
    h.tone(0.05, { type: 'sawtooth', f: 200, f2: 50, dur: 0.6, vol: 0.2, lp: 700 });
  }, 1);
  def('summon', 2.6, 2, 0.3, 0, 0.4, function (h) {
    h.noise(0, { type: 'bandpass', f: 300, f2: 5000, q: 3, dur: 0.9, vol: 0.3, a: 0.6 });
    h.tone(0, { f: 300, f2: 1500, dur: 0.9, vol: 0.2, a: 0.15 });
    bell(h, 0.2, 880, 0.5, 0.1, 2.0, 1.0); bell(h, 0.5, 1175, 0.5, 0.1, 2.0, 1.0);
    bell(h, 0.9, 1568, 0.9, 0.3, 2.0, 1.2);
    [72, 76, 79].forEach(function (n) { h.tone(0.9, { type: 'triangle', f: mtof(n), dur: 1.0, vol: 0.12, hold: 0.3 }); });
    thump(h, 0.9, 100, 45, 0.3, 0.6);
    sparkle(h, 1.0, 4, 3000, 0.6, 0.5, 0.05, 0.4);
  }, 1);
  def('summon_rare', 4.0, 2, 0.3, 0, 0.45, function (h) {
    h.noise(0, { type: 'bandpass', f: 250, f2: 7000, q: 3, dur: 1.2, vol: 0.35, a: 0.8 });
    h.tone(0, { f: 250, f2: 1800, dur: 1.2, vol: 0.25, a: 0.25 });
    h.tone(0, { type: 'sawtooth', f: 120, f2: 480, dur: 1.2, vol: 0.12, lp: 900, a: 0.4 });
    thump(h, 1.2, 100, 30, 0.8, 1.0);
    crack(h, 1.2, 0.5, 0.08, 2400);
    [76, 79, 83, 88, 91].forEach(function (n, i) { bell(h, 1.2 + i * 0.06, mtof(n), 0.7, 0.2, 2.0, 1.0); });
    [55, 62, 67, 71, 74].forEach(function (n) {
      h.tone(1.4, { type: 'sawtooth', f: mtof(n), dur: 2.0, vol: 0.05, lp: 2200, det: -7, a: 0.1, hold: 0.5 });
      h.tone(1.4, { type: 'sawtooth', f: mtof(n), dur: 2.0, vol: 0.05, lp: 2200, det: 7, a: 0.1, hold: 0.5 });
    });
    h.noise(1.2, { type: 'highpass', f: 6000, dur: 1.4, vol: 0.14, a: 0.01 });
    sparkle(h, 1.3, 8, 3500, 1.0, 1.4, 0.05, 0.5);
  }, 1);
  def('no_mp', 0.35, 1, 0.15, 0.03, 0.04, function (h) {
    h.tone(0, { f: 220, f2: 140, dur: 0.08, vol: 0.35, a: 0.002 });
    h.noise(0, { type: 'lowpass', f: 600, dur: 0.05, vol: 0.2 });
    h.tone(0.09, { f: 180, f2: 120, dur: 0.1, vol: 0.3, a: 0.002 });
  }, 1);
  def('skill_ready', 0.4, 0, 0.2, 0.02, 0.12, function (h) {
    bell(h, 0, 1760, 0.15, 0.12); bell(h, 0.05, 2349, 0.2, 0.08);
  }, 1);

  /* -- 보스 -- */
  def('boss_in', 3.2, 2, 0.5, 0, 0.4, function (h) {
    h.tone(0, { f: 80, f2: 28, dur: 1.6, vol: 0.95, a: 0.004 });
    h.tone(0, { type: 'sawtooth', f: 55, f2: 48, dur: 2.2, vol: 0.35, lp: 300, a: 0.2 });
    [48, 55, 60].forEach(function (n) {
      h.tone(0.5, { type: 'sawtooth', f: mtof(n), dur: 1.2, vol: 0.13, lp: 1200, lp2: 400, a: 0.06, det: -6 });
      h.tone(0.5, { type: 'sawtooth', f: mtof(n), dur: 1.2, vol: 0.13, lp: 1200, lp2: 400, a: 0.06, det: 6 });
    });
    h.noise(0, { type: 'highpass', f: 4000, dur: 2.2, vol: 0.25, a: 1.4 });
    h.noise(0, { type: 'lowpass', f: 180, dur: 2.2, vol: 0.45, a: 0.4 });
    thump(h, 1.4, 90, 30, 0.7, 0.8);
    crack(h, 1.4, 0.5, 0.06, 2000);
    bell(h, 0, 110, 2.5, 0.25, 1.41, 3);
  }, 1);
  def('boss_warn', 1.6, 2, 0.6, 0.02, 0.3, function (h) {
    [0, 0.3].forEach(function (t, i) {
      h.tone(t, { type: 'sawtooth', f: i ? 104 : 110, dur: 0.22, vol: 0.35, lp: 700, a: 0.01 });
      thump(h, t, 100, 45, 0.18, 0.6);
    });
    h.noise(0, { type: 'bandpass', f: 500, f2: 3000, q: 1.5, dur: 0.8, vol: 0.2, a: 0.5 });
  }, 1);
  def('boss_rage', 2.9, 2, 0.8, 0, 0.35, function (h) {
    h.tone(0, { type: 'sawtooth', f: 90, f2: 60, dur: 1.4, vol: 0.4, lp: 800, lp2: 300, a: 0.1 });
    h.tone(0, { type: 'sawtooth', f: 95, f2: 55, dur: 1.4, vol: 0.3, lp: 700, det: 25, a: 0.1 });
    h.noise(0, { type: 'bandpass', f: 600, f2: 300, q: 1.5, dur: 1.4, vol: 0.45, a: 0.2 });
    thump(h, 0.1, 90, 28, 0.6, 0.8);
    for (var i = 0; i < 5; i++) crack(h, 0.2 + i * 0.22, 0.3, 0.05, 1600);
    h.noise(0.9, { type: 'highpass', f: 5000, dur: 1.0, vol: 0.15, a: 0.3 });
  }, 1);
  def('boss_slam', 1.8, 2, 0.3, 0.03, 0.3, function (h) {
    thump(h, 0, 95, 30, 0.55, 1.0);
    crack(h, 0, 0.9, 0.07, 1800);
    h.noise(0, { type: 'lowpass', f: 3500, f2: 120, dur: 0.6, vol: 0.7, a: 0.002 });
    for (var i = 0; i < 5; i++) h.noise(0.1 + rnd() * 0.4, { type: 'highpass', f: 3000, dur: 0.04, vol: 0.15 });
    bell(h, 0, 150, 1.2, 0.2, 1.5, 2);
  }, 1);
  def('boss_win', 3.8, 2, 0.5, 0, 0.4, function (h) {
    [[60, 64, 67], [62, 67, 71], [64, 72, 76], [67, 72, 76, 79, 84]].forEach(function (ch, i) {
      var t = i * 0.22, last = i === 3;
      ch.forEach(function (n) {
        h.tone(t, { type: 'sawtooth', f: mtof(n), dur: last ? 1.9 : 0.4, vol: last ? 0.1 : 0.12, lp: 2400, a: 0.02, det: -6, hold: last ? 0.5 : 0.1 });
        h.tone(t, { type: 'sawtooth', f: mtof(n), dur: last ? 1.9 : 0.4, vol: last ? 0.1 : 0.12, lp: 2400, a: 0.02, det: 6, hold: last ? 0.5 : 0.1 });
      });
      thump(h, t, last ? 110 : 120, last ? 45 : 70, last ? 0.8 : 0.25, last ? 1.0 : 0.7);
    });
    h.noise(0.66, { type: 'highpass', f: 5000, dur: 2.0, vol: 0.3, a: 0.01 });
    sparkle(h, 0.7, 8, 3200, 1.0, 1.2, 0.05, 0.5);
  }, 1);
  def('boss_lose', 3.4, 2, 0.5, 0, 0.4, function (h) {
    [64, 62, 60, 57].forEach(function (n, i) {
      h.tone(i * 0.3, { type: 'triangle', f: mtof(n), dur: 0.6, vol: 0.28 });
      h.tone(i * 0.3, { type: 'sawtooth', f: mtof(n), dur: 0.6, vol: 0.08, lp: 900 });
    });
    [45, 52, 57].forEach(function (n) { h.tone(1.2, { type: 'sawtooth', f: mtof(n), dur: 1.8, vol: 0.12, lp: 700, a: 0.1, det: 5 }); });
    thump(h, 1.2, 90, 30, 0.9, 0.9);
    h.noise(1.2, { type: 'lowpass', f: 800, f2: 100, dur: 1.6, vol: 0.3, a: 0.2 });
  }, 1);
  def('boss_die', 3.2, 2, 0.8, 0, 0.45, function (h) {
    h.tone(0, { f: 800, f2: 60, dur: 1.6, vol: 0.3, a: 0.02 });
    h.noise(0, { type: 'bandpass', f: 8000, f2: 300, q: 1.2, dur: 1.2, vol: 0.3, a: 0.4 });
    thump(h, 0.4, 100, 28, 1.0, 1.0);
    crack(h, 0.4, 0.6, 0.08, 2000);
    for (var i = 0; i < 7; i++) bell(h, 0.45 + rnd() * 0.5, 2500 + rnd() * 3500, 0.3, 0.07, 3.01, 0.6);
    bell(h, 0.4, 220, 1.8, 0.2, 1.41, 3);
  }, 1);

  /* -- 스킬 10종 × (전조 charge · 발동 · 여운 tail) -- */
  var SKILL_IDS = ['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shield', 'shrimp', 'storm'];
  // slash 검 베기
  def('skill_slash_charge', 0.35, 1, 0.1, 0.04, 0.05, function (h) {
    whoosh(h, 0, 0.2, 800, 2400, 0.18, 1.5); bell(h, 0.12, 3000, 0.15, 0.05, 3.5, 1.2);
  }, 1);
  def('skill_slash', 0.8, 1, 0.06, 0.05, 0.2, function (h, v) {
    whoosh(h, 0, 0.14, pick(v, [1500, 1700, 1300]), 8000, 0.55, 1.5);
    bell(h, 0.03, 2400, 0.3, 0.15, 3.5, 1.2);
    thump(h, 0.02, 160, 70, 0.15, 0.55); crack(h, 0.03, 0.5, 0.04, 3000);
    h.noise(0.08, { type: 'highpass', f: 3000, dur: 0.06, vol: 0.3 });
  });
  def('skill_slash_tail', 0.9, 1, 0.1, 0.03, 0.3, function (h) {
    bell(h, 0, 3100, 0.7, 0.1, 1.4, 2); bell(h, 0, 4300, 0.5, 0.06, 1.7, 1.5);
    h.noise(0, { type: 'highpass', f: 7000, dur: 0.4, vol: 0.06, a: 0.05 });
  }, 1);
  // peck 쪼기 연타
  def('skill_peck_charge', 0.3, 1, 0.1, 0.04, 0.03, function (h) {
    for (var i = 0; i < 3; i++) h.tone(i * 0.06, { type: 'triangle', f: 900 + i * 220, f2: 600 + i * 160, dur: 0.03, vol: 0.12 });
  }, 1);
  def('skill_peck', 0.7, 1, 0.08, 0.05, 0.1, function (h, v) {
    for (var i = 0; i < 5; i++) {
      var t = i * 0.055, pf = 1 + (rnd() - 0.5) * 0.12;
      h.tone(t, { f: 1250 * pf, f2: 500 * pf, dur: 0.045, vol: 0.28, a: 0.001 });
      h.noise(t, { type: 'bandpass', f: 3200, q: 1.2, dur: 0.025, vol: 0.22, a: 0.001 });
      thump(h, t, 150, 80, 0.05, 0.25);
    }
  });
  def('skill_peck_tail', 0.6, 1, 0.1, 0.04, 0.12, function (h) {
    h.noise(0, { type: 'highpass', f: 5500, dur: 0.3, vol: 0.07, a: 0.08 });
    h.noise(0.12, { type: 'bandpass', f: 1800, q: 2, dur: 0.05, vol: 0.12 });
  }, 1);
  // spin 회전
  def('skill_spin_charge', 0.5, 1, 0.1, 0.03, 0.05, function (h) {
    whoosh(h, 0, 0.35, 300, 1500, 0.22, 2); h.tone(0, { f: 200, f2: 500, dur: 0.3, vol: 0.08, a: 0.2 });
  }, 1);
  def('skill_spin', 1.0, 1, 0.1, 0.04, 0.12, function () {
    var h = arguments[0];
    h.noise(0, { type: 'bandpass', f: 400, f2: 2500, q: 2.5, dur: 0.3, vol: 0.5, a: 0.1 });
    h.noise(0.3, { type: 'bandpass', f: 2500, f2: 500, q: 2.5, dur: 0.3, vol: 0.45, a: 0.02 });
    h.tone(0, { f: 300, f2: 600, dur: 0.3, vol: 0.12 }); h.tone(0.3, { f: 600, f2: 250, dur: 0.3, vol: 0.12 });
    thump(h, 0.02, 130, 60, 0.15, 0.5); thump(h, 0.32, 130, 60, 0.15, 0.4);
    crack(h, 0.02, 0.3, 0.03, 2500);
  });
  def('skill_spin_tail', 0.9, 1, 0.1, 0.03, 0.2, function (h) {
    h.noise(0, { type: 'lowpass', f: 2000, f2: 400, q: 1.5, dur: 0.6, vol: 0.2, a: 0.05 });
    h.tone(0, { type: 'triangle', f: 500, f2: 230, dur: 0.5, vol: 0.06, vib: { rate: 9, depth: 40 } });
  }, 1);
  // bomb 폭탄
  def('skill_bomb_charge', 0.6, 1, 0.1, 0.03, 0.05, function (h) {
    for (var i = 0; i < 12; i++) h.noise(i * 0.04 + rnd() * 0.02, { type: 'highpass', f: 3500, dur: 0.012, vol: 0.12 + i * 0.01 });
    h.tone(0, { f: 1400, f2: 500, dur: 0.4, vol: 0.08, a: 0.02 });
  }, 1);
  def('skill_bomb', 1.8, 1, 0.15, 0.03, 0.3, function () {
    var h = arguments[0];
    h.tone(0, { f: 140, f2: 32, dur: 0.8, vol: 0.95, a: 0.002 });
    h.noise(0, { type: 'lowpass', f: 4000, f2: 100, q: 0.7, dur: 0.9, vol: 0.7, a: 0.002 });
    crack(h, 0, 0.7, 0.08, 1800);
    h.noise(0.04, { type: 'highpass', f: 2000, dur: 0.3, vol: 0.3 });
    for (var i = 0; i < 6; i++) h.noise(0.1 + rnd() * 0.5, { type: 'highpass', f: 3000, dur: 0.03, vol: 0.13 });
  });
  def('skill_bomb_tail', 1.8, 1, 0.15, 0.02, 0.4, function (h) {
    h.noise(0, { type: 'lowpass', f: 300, f2: 60, dur: 1.2, vol: 0.3, a: 0.05 });
    for (var i = 0; i < 6; i++) bell(h, 0.1 + rnd() * 0.8, 1500 + rnd() * 2500, 0.1, 0.04, 3.01, 0.6);
  }, 1);
  // thunder 번개
  def('skill_thunder_charge', 0.6, 1, 0.1, 0.03, 0.08, function (h) {
    h.noise(0, { type: 'highpass', f: 1500, dur: 0.4, vol: 0.2, a: 0.35 });
    h.tone(0, { type: 'square', f: 80, f2: 120, dur: 0.4, vol: 0.12, lp: 500, a: 0.3 });
  }, 1);
  def('skill_thunder', 1.8, 1, 0.15, 0.03, 0.3, function () {
    var h = arguments[0];
    h.noise(0, { type: 'highpass', f: 1500, dur: 0.1, vol: 0.65 });
    [2200, 1400, 2600, 900, 3000].forEach(function (f, i) { h.tone(i * 0.022, { type: 'sawtooth', f: f, f2: f * 0.3, dur: 0.04, vol: 0.14, lp: 5000 }); });
    h.noise(0.06, { type: 'lowpass', f: 300, f2: 80, q: 0.5, dur: 0.9, vol: 0.6, a: 0.03 });
    thump(h, 0.06, 70, 36, 0.8, 0.6);
    crack(h, 0, 0.6, 0.05, 3500);
  });
  def('skill_thunder_tail', 2.0, 1, 0.15, 0.02, 0.4, function (h) {
    h.noise(0, { type: 'lowpass', f: 400, f2: 70, q: 0.6, dur: 1.5, vol: 0.35, a: 0.2 });
    h.noise(0, { type: 'highpass', f: 6000, dur: 0.4, vol: 0.05, a: 0.02 });
  }, 1);
  // fire 불
  def('skill_fire_charge', 0.5, 1, 0.1, 0.03, 0.06, function (h) {
    h.noise(0, { type: 'bandpass', f: 200, f2: 1200, q: 1, dur: 0.35, vol: 0.25, a: 0.3 });
    h.tone(0, { type: 'sawtooth', f: 70, f2: 130, dur: 0.35, vol: 0.1, lp: 400, a: 0.25 });
  }, 1);
  def('skill_fire', 1.2, 1, 0.12, 0.04, 0.18, function () {
    var h = arguments[0];
    h.noise(0, { type: 'bandpass', f: 300, f2: 3000, q: 1, dur: 0.55, vol: 0.55, a: 0.1 });
    h.tone(0, { type: 'sawtooth', f: 90, f2: 250, dur: 0.5, vol: 0.2, lp: 600, a: 0.05 });
    thump(h, 0, 100, 45, 0.3, 0.6);
    for (var i = 0; i < 9; i++) h.noise(0.05 + rnd() * 0.5, { type: 'highpass', f: 3000, dur: 0.015, vol: 0.22 });
  });
  def('skill_fire_tail', 1.4, 1, 0.12, 0.03, 0.18, function (h) {
    h.noise(0, { type: 'bandpass', f: 500, f2: 250, q: 0.8, dur: 0.9, vol: 0.12, a: 0.1 });
    for (var i = 0; i < 12; i++) h.noise(rnd() * 0.9, { type: 'highpass', f: 3500, dur: 0.012, vol: 0.14 * (1 - i / 14) });
  }, 1);
  // egg 계란
  def('skill_egg_charge', 0.45, 1, 0.1, 0.03, 0.05, function (h) {
    h.tone(0, { f: 300, f2: 700, dur: 0.3, vol: 0.18, a: 0.02, vib: { rate: 11, depth: 90 } });
    h.tone(0.2, { f: 1800, f2: 2400, dur: 0.08, vol: 0.06 });
  }, 1);
  def('skill_egg', 1.0, 1, 0.12, 0.04, 0.12, function () {
    var h = arguments[0];
    whoosh(h, 0, 0.15, 900, 2500, 0.25, 1.2);
    h.noise(0.15, { type: 'lowpass', f: 2200, f2: 300, dur: 0.18, vol: 0.5, a: 0.002 });
    h.tone(0.15, { f: 400, f2: 110, dur: 0.15, vol: 0.4, a: 0.002 });
    h.noise(0.15, { type: 'bandpass', f: 2500, q: 1, dur: 0.05, vol: 0.3 });
    bell(h, 0.18, 1760, 0.25, 0.14, 1.5, 0.8);
  });
  def('skill_egg_tail', 0.9, 1, 0.12, 0.03, 0.1, function (h) {
    [0.05, 0.22, 0.4].forEach(function (t, i) { h.tone(t, { f: 900 - i * 120, f2: 600 - i * 100, dur: 0.07, vol: 0.12 - i * 0.03 }); });
    h.noise(0, { type: 'lowpass', f: 800, dur: 0.3, vol: 0.08 });
  }, 1);
  // shield 방패
  def('skill_shield_charge', 0.55, 1, 0.1, 0.03, 0.15, function (h) {
    [60, 64, 67].forEach(function (n) { h.tone(0, { type: 'triangle', f: mtof(n), dur: 0.4, vol: 0.09, a: 0.3 }); });
  }, 1);
  def('skill_shield', 1.2, 1, 0.2, 0.03, 0.3, function () {
    var h = arguments[0];
    bell(h, 0, 880, 0.8, 0.28, 2.0, 1.2);
    thump(h, 0, 110, 55, 0.25, 0.5);
    h.noise(0.03, { type: 'highpass', f: 6000, dur: 0.4, vol: 0.12, a: 0.1 });
    h.tone(0, { f: 330, f2: 495, dur: 0.5, vol: 0.14, a: 0.06 });
    sparkle(h, 0.1, 3, 3000, 0.5, 0.2, 0.06, 0.3);
  });
  def('skill_shield_tail', 1.4, 1, 0.2, 0.02, 0.35, function (h) {
    h.tone(0, { f: 660, dur: 0.9, vol: 0.09, a: 0.15, vib: { rate: 6, depth: 14 } });
    h.tone(0, { f: 990, dur: 0.9, vol: 0.06, a: 0.15, det: 8, vib: { rate: 5, depth: 14 } });
  }, 1);
  // shrimp 새우
  def('skill_shrimp_charge', 0.4, 1, 0.1, 0.03, 0.06, function (h) {
    for (var i = 0; i < 3; i++) h.tone(i * 0.08, { f: 400 + i * 120, f2: 900 + i * 200, dur: 0.07, vol: 0.12, a: 0.005 });
  }, 1);
  def('skill_shrimp', 0.9, 1, 0.15, 0.04, 0.15, function () {
    var h = arguments[0];
    [1, 1.25, 1.5].forEach(function (m, i) {
      h.tone(i * 0.08, { f: 400 * m, f2: 900 * m, dur: 0.1, vol: 0.28, a: 0.003 });
      h.noise(i * 0.08, { type: 'bandpass', f: 1000, f2: 2200, q: 4, dur: 0.07, vol: 0.18 });
      thump(h, i * 0.08, 140, 70, 0.06, 0.25);
    });
    h.noise(0.26, { type: 'highpass', f: 4000, dur: 0.15, vol: 0.14 });
    bell(h, 0.26, 1760, 0.2, 0.1);
  });
  def('skill_shrimp_tail', 0.8, 1, 0.15, 0.03, 0.2, function (h) {
    for (var i = 0; i < 5; i++) h.tone(0.05 + rnd() * 0.4, { f: 700 + rnd() * 500, f2: 1400 + rnd() * 600, dur: 0.05, vol: 0.07 });
    h.noise(0, { type: 'highpass', f: 5000, dur: 0.25, vol: 0.06, a: 0.04 });
  }, 1);
  // storm 폭풍
  def('skill_storm_charge', 0.9, 1, 0.2, 0.03, 0.1, function (h) {
    h.noise(0, { type: 'bandpass', f: 200, f2: 1800, q: 1.2, dur: 0.7, vol: 0.3, a: 0.6 });
    h.tone(0, { type: 'sawtooth', f: 150, f2: 500, dur: 0.7, vol: 0.08, lp: 700, a: 0.5 });
  }, 1);
  def('skill_storm', 2.4, 1, 0.3, 0.03, 0.35, function () {
    var h = arguments[0];
    h.noise(0, { type: 'bandpass', f: 300, f2: 2200, q: 1.2, dur: 1.2, vol: 0.5, a: 0.4 });
    h.noise(0.5, { type: 'highpass', f: 1500, dur: 0.1, vol: 0.5 });
    h.noise(0.5, { type: 'lowpass', f: 400, f2: 80, q: 0.5, dur: 1.0, vol: 0.6 });
    thump(h, 0.5, 80, 32, 1.0, 0.7);
    h.noise(0.5, { type: 'highpass', f: 4000, dur: 0.6, vol: 0.18 });
    h.tone(0, { type: 'sawtooth', f: 200, f2: 700, dur: 1.2, vol: 0.12, lp: 900, a: 0.5 });
  });
  def('skill_storm_tail', 2.4, 1, 0.3, 0.02, 0.4, function (h) {
    h.noise(0, { type: 'highpass', f: 5000, dur: 1.6, vol: 0.1, a: 0.1 });
    h.noise(0.3, { type: 'lowpass', f: 300, f2: 60, dur: 1.5, vol: 0.25, a: 0.3 });
  }, 1);

  var CAP = [10, 16, 24];
  function skillSfx(id, phase) {
    var n = 'skill_' + id + (phase === 'charge' ? '_charge' : phase === 'tail' ? '_tail' : '');
    return SFX.hasOwnProperty(n) ? n : null;
  }

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
    vol *= 0.92 + rnd() * 0.16; // 음량도 조금씩
    // 라운드 로빈: 직전과 다른 변형
    var last = e.rr[name] === undefined ? -1 : e.rr[name], vi = 0;
    if (d.n > 1) vi = last < 0 ? (rnd() * d.n) | 0 : (last + 1 + ((rnd() * (d.n - 1)) | 0)) % d.n;
    e.rr[name] = vi;
    // 좌우 · 거리
    var pan = 0;
    if (o && o.pan != null) pan = clampN(o.pan, -1, 1, 0);
    else if (o && o.x != null) pan = clampN(o.x, -1, 1, 0) * 0.85;
    else if (d.jit) pan = (rnd() * 2 - 1) * 0.07;
    var dist = clampN(o && o.dist, 0, 1, 0);
    vol *= 1 - 0.55 * dist;
    var out = mkVoice(e, e.sfxBus, e.rvSfx, pan, dist, d.wet);
    d.fn(H(e, out, when, vol, rate), vi);
    e.played++;
    return true;
  }
  // 한 번의 소리가 지나가는 길: (거리 → 고음 깎기) → 패닝 → 버스, 같은 곳에서 잔향 보내기
  function mkVoice(e, bus, rv, pan, dist, wet) {
    var c = e.ctx, out = c.createGain(), last = out;
    if (dist > 0.05) {
      var lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = Math.max(1500, 16000 - dist * 13000);
      last.connect(lp); last = lp;
    }
    if (c.createStereoPanner) {
      var pn = c.createStereoPanner(); pn.pan.value = pan; last.connect(pn); last = pn;
    }
    last.connect(bus);
    if (wet > 0) { var sd = c.createGain(); sd.gain.value = wet * (1 + dist * 1.5); last.connect(sd); sd.connect(rv); }
    return out;
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
    [[0, 8], [8, 4], [12, 4]],
    [[2, 2], [4, 2], [7, 1], [8, 3], [12, 2], [14, 2]]
  ];
  var Z16 = '................';
  // 구성(마디): 인트로 0-1 · A 2-5 · B 6-9 · A′ 10-13 · 되돌림 14-15
  var BARS = 16, SPB = 16, TOTAL = BARS * SPB, LOOP_START = 2 * SPB;
  // 층: 켜지는 강도 문턱
  var LAYERS = { pad: -0.1, bass: -0.1, hat: 0.2, kick: 0.35, arp: 0.5, lead: 0.65, extra: 0.85 };
  var LAYER_NAMES = ['pad', 'bass', 'hat', 'kick', 'arp', 'lead', 'extra'];
  var LAYER_PAN = { pad: 0, bass: 0, hat: 0.25, kick: 0, arp: -0.3, lead: 0.08, extra: 0 };

  var TRACKS = {
    // 합정 골목 — 따뜻한 어쿠스틱 팝, 플루트 리드
    field1: { bpm: 100, root: 36, sc: 'maj', cq: 'add9', swing: 0.06, seed: 11,
      progA: [0, 4, 5, 3], progB: [3, 4, 2, 5], alt: 4, turn: [3, 4],
      kit: { k: 'soft', s: 'rim', h: 'shaker' }, dv: 0.9,
      kA: 'x.......x.x.....', sA: '....x.......x...', hA: 'x.o.x.o.x.o.x.o.',
      kB: 'x.....x.x.x.....', sB: '....x.......x..x', hB: 'xoxoxoxoxoxoxoxo',
      bass: 'sub', bA: 'x.......x.x.....', bB: 'x.....x.x.......',
      pad: 'warm', pv: 0.1, arp: { style: 'pluck', step: 2, seq: [0, 1, 2, 3, 2, 1], vol: 0.09 },
      lead: 'flute', lv: 0.2, lr: [62, 86], rh: [0, 1, 3, 7], dly: 0.3,
      rv: { pad: 0.35, arp: 0.25, lead: 0.3, kick: 0.15, hat: 0.1 } },
    // bhc 치킨 — 펑키, 슬랩 베이스와 짧게 끊는 코드, 밝은 사각파 리드
    field2: { bpm: 118, root: 38, sc: 'mix', cq: 'sev', swing: 0.12, seed: 22,
      progA: [0, 3, 0, 6], progB: [3, 6, 0, 4], alt: 4, turn: [6, 4],
      kit: { k: 'punch', s: 'clap', h: 'tight' }, dv: 1.0,
      kA: 'x.....x.x.......', sA: '....x.......x...', hA: 'x.xxx.xxx.xxx.xx',
      kB: 'x..x..x.x..x..x.', sB: '....x..x....x...', hB: 'xxxxxxxxxxxxxxxx',
      bass: 'pluck', bA: 'x..x..x.x..x..x.', bB: 'x.xx..x.x.xx..xO',
      pad: 'stab', stab: '..x...x...x...x.', pv: 0.07, arp: { style: 'chip', step: 4, seq: [0, 2, 1, 3], vol: 0.06 },
      lead: 'square', lv: 0.14, lr: [64, 88], rh: [1, 2, 5, 7], dly: 0.25,
      rv: { pad: 0.15, arp: 0.2, lead: 0.2, kick: 0.1, hat: 0.05 } },
    // 홍대 — 밤거리 신스웨이브, 네 박 킥, 게이트 아르페지오
    field3: { bpm: 112, root: 33, sc: 'dor', cq: 'tri', swing: 0, seed: 33,
      progA: [0, 3, 0, 4], progB: [5, 4, 3, 4], alt: 6, turn: [4, 4],
      kit: { k: 'punch', s: 'snare', h: 'tight' }, dv: 1.0,
      kA: 'x...x...x...x...', sA: '....x.......x...', hA: '..o...o...o...o.',
      kB: 'x...x...x...x..x', sB: '....x.......x.x.', hB: 'x.o.x.o.x.o.x.oo',
      bass: 'saw', bA: 'x.x.x.x.x.x.x.x.', bB: 'x.xxx.xxx.xxx.xO',
      pad: 'saw', pv: 0.06, arp: { style: 'gate', step: 1, seq: [0, 1, 2, 3, 2, 1, 3, 2], vol: 0.05 },
      lead: 'saw', lv: 0.13, lr: [62, 88], rh: [3, 0, 4, 7], dly: 0.45,
      rv: { pad: 0.35, arp: 0.3, lead: 0.35, kick: 0.3, hat: 0.1 } },
    // 상수 — 로파이 카페, 스윙, 전자피아노 코드와 종소리 리드
    field4: { bpm: 84, root: 41, sc: 'maj', cq: 'sev', swing: 0.22, seed: 44,
      progA: [1, 4, 0, 5], progB: [3, 4, 2, 5], alt: 4, turn: [1, 4],
      kit: { k: 'soft', s: 'rim', h: 'dusty' }, dv: 0.85,
      kA: 'x.....x..x......', sA: '....x.......x...', hA: 'x.x.x.x.x.x.x.x.',
      kB: 'x.....x..x.x....', sB: '....x.......x..x', hB: 'xxxxxxxxxxxxxxxx',
      bass: 'sub', bA: 'x.....x...x.....', bB: 'x..x..x...x..x..',
      pad: 'epiano', ep: 'x..x..x.x.......', pv: 0.09, arp: { style: 'bell', step: 4, seq: [0, 2, 1, 3], vol: 0.05 },
      lead: 'bell', lv: 0.13, lr: [64, 86], rh: [3, 7, 6, 0], dly: 0.4,
      rv: { pad: 0.3, arp: 0.35, lead: 0.4, kick: 0.1, hat: 0.1 } },
    // 망원 — 시장통 스카 리듬, 마림바와 휘파람
    field5: { bpm: 108, root: 43, sc: 'lyd', cq: 'tri', swing: 0.1, seed: 55,
      progA: [0, 1, 4, 0], progB: [3, 4, 1, 0], alt: 4, turn: [1, 4],
      kit: { k: 'punch', s: 'clap', h: 'shaker' }, dv: 0.95,
      kA: 'x.......x.......', sA: '....x.......x...', hA: 'xxxxxxxxxxxxxxxx',
      kB: 'x...x...x...x...', sB: '....x.......x.x.', hB: 'xoxoxoxoxoxoxoxo',
      bass: 'walk', bA: 'x..x..x.x..x..x.', bB: 'x.x.x.x.x.x.x.x.',
      pad: 'stab', stab: '..x...x...x...x.', pv: 0.07, arp: { style: 'marimba', step: 2, seq: [0, 1, 2, 3, 2, 1, 0, 1], vol: 0.09 },
      lead: 'whistle', lv: 0.17, lr: [67, 91], rh: [0, 2, 5, 7], dly: 0.35,
      rv: { pad: 0.15, arp: 0.2, lead: 0.3, kick: 0.1, hat: 0.05 } },
    // 한강 — 밤 강바람, 웅장한 스트링과 달리는 8분 베이스
    field6: { bpm: 126, root: 40, sc: 'min', cq: 'tri', swing: 0, seed: 66,
      progA: [0, 5, 2, 6], progB: [3, 5, 0, 4], alt: 4, turn: [5, 4],
      kit: { k: 'punch', s: 'snare', h: 'tight' }, dv: 1.05,
      kA: 'x.....x.x...x...', sA: '....x.......x..x', hA: 'x.x.x.x.x.x.x.xx',
      kB: 'x..x..x.x..x..x.', sB: '....x.......x.x.', hB: 'xxxxxxxxxxxxxxxx',
      bass: 'drive', bA: 'x.xxx.xxx.xxx.xx', bB: 'xxxxxxxxxxxxxxxO',
      pad: 'string', pv: 0.05, arp: { style: 'chip', step: 2, seq: [0, 2, 3, 2], vol: 0.05 },
      lead: 'saw', lv: 0.13, lr: [60, 86], rh: [1, 5, 4, 7], dly: 0.35,
      rv: { pad: 0.4, arp: 0.25, lead: 0.35, kick: 0.2, hat: 0.1 } },
    // 보스 — 프리지안 단조, 타이코 + 금관, 쉴 틈 없는 16분 베이스
    boss: { bpm: 138, root: 37, sc: 'phr', cq: 'tri', swing: 0, seed: 77, ibias: 0.25,
      progA: [0, 0, 1, 0], progB: [5, 4, 1, 0], alt: 1, turn: [1, 4],
      kit: { k: 'taiko', s: 'snare', h: 'tight' }, dv: 1.1,
      kA: 'x..x..x.x..x..x.', sA: '....x.......x...', hA: 'xoxoxoxoxoxoxoxo',
      kB: 'x.x.x.x.x.x.x.x.', sB: '....x..x....x.x.', hB: 'xxxxxxxxxxxxxxxx',
      tomA: '..............x.', tomB: '...........x.x.x',
      bass: 'drive', bA: 'xxOxxxOxxxOxxxOx', bB: 'xxxxxxxxxxxxxxxx',
      pad: 'string', pv: 0.06, arp: { style: 'gate', step: 1, seq: [0, 0, 2, 0, 3, 0, 2, 0], vol: 0.05 },
      lead: 'brass', lv: 0.11, lr: [58, 84], rh: [5, 1, 4, 7], dly: 0.2,
      rv: { pad: 0.3, arp: 0.2, lead: 0.3, kick: 0.25, hat: 0.05 } },
    // 메뉴 — 잔잔한 오르골과 패드, 드럼 없음
    menu: { bpm: 80, root: 46, sc: 'maj', cq: 'add9', swing: 0, seed: 88,
      progA: [0, 5, 3, 4], progB: [3, 4, 2, 5], alt: 4, turn: [3, 4],
      kit: { k: 'soft', s: 'rim', h: 'shaker' }, dv: 0.5,
      kA: Z16, sA: Z16, hA: 'o...o...o...o...',
      kB: Z16, sB: Z16, hB: 'o.o.o.o.o.o.o.o.',
      bass: 'sub', bA: 'x.......x.......', bB: 'x.......x.....x.',
      pad: 'glass', pv: 0.1, arp: { style: 'bell', step: 4, seq: [0, 1, 2, 3, 2, 1, 2, 1], vol: 0.07 },
      lead: 'bell', lv: 0.14, lr: [66, 88], rh: [3, 6, 0, 7], dly: 0.45,
      rv: { pad: 0.45, arp: 0.4, lead: 0.45, kick: 0.1, hat: 0.1 } }
  };
  var TRACK_NAMES = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'boss', 'menu'];

  function scNote(tr, i) {
    var o = Math.floor(i / 7), k = ((i % 7) + 7) % 7;
    return tr.root + SC[tr.sc][k] + 12 * o;
  }
  function chordIdx(tr) { // 화음 구성음(음계 칸 오프셋)
    return tr.cq === 'sev' ? [0, 2, 4, 6] : tr.cq === 'add9' ? [0, 2, 4, 8] : [0, 2, 4];
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
  function hash01(n) { return (((n * 2654435761) >>> 0) % 1000) / 1000; }

  // 트랙 → 256칸 이벤트표(한 번 만들어 두고 재사용)
  function compile(tr) {
    if (tr._ev) return tr._ev;
    var R = mulberry(tr.seed), ev = [], s, b, i;
    for (s = 0; s < TOTAL; s++) ev.push({ d: [], b: null, p: null, a: null, l: null, x: [], g: s < 2 * SPB ? 0.7 : 1 });
    // 마디별 화음 뿌리 + 구간
    var sec = [], deg = [];
    var pa = tr.progA, pb = tr.progB;
    for (b = 0; b < BARS; b++) {
      if (b < 2) { sec.push('I'); deg.push(pa[b]); }
      else if (b < 6) { sec.push('A'); deg.push(pa[b - 2]); }
      else if (b < 10) { sec.push('B'); deg.push(pb[b - 6]); }
      else if (b < 14) { sec.push('C'); deg.push(b === 13 ? tr.alt : pa[b - 10]); }
      else { sec.push('T'); deg.push(tr.turn[b - 14]); }
    }
    function hit(st, type, vel) { ev[st].d.push([type, vel * (0.88 + 0.12 * hash01(st + 7))]); }
    for (b = 0; b < BARS; b++) {
      var base = b * SPB, S = sec[b], isB = S === 'B' || S === 'C';
      var kp = isB ? tr.kB : tr.kA, sp = isB ? tr.sB : tr.sA, hp = isB ? tr.hB : tr.hA;
      for (s = 0; s < SPB; s++) {
        var st = base + s, vk = kp[s] === 'x' ? 1 : kp[s] === 'o' ? 0.5 : 0, vs = sp[s] === 'x' ? 1 : sp[s] === 'o' ? 0.5 : 0,
          vh = hp[s] === 'x' ? 1 : hp[s] === 'o' ? 0.55 : 0;
        if (S === 'I') { vk = 0; vs = 0; vh *= 0.6; }
        if (S === 'T' && b === 15) { vk = s < 8 ? vk : 0; vs = 0; }
        if (vk) hit(st, 'k', vk);
        if (vs) hit(st, 's', vs);
        if (vh) hit(st, hp[s] === 'o' && tr.kit.h !== 'shaker' ? 'ho' : 'h', vh);
      }
      // 큰 마디 끝 필 / 되돌림 마디의 스네어 롤
      if (b === 5 || b === 9 || b === 13) {
        var tp = b === 9 || b === 13 ? tr.tomB : tr.tomA;
        for (s = 12; s < 16; s++) hit(base + s, tp ? 'tom' : 's', 0.5 + (s - 12) * 0.14);
      }
      if (b === 15) for (s = 8; s < 16; s++) hit(base + s, 's', 0.35 + (s - 8) * 0.09);
      if (tr.tomA && (S === 'A' || S === 'B' || S === 'C')) {
        var tpat = isB ? tr.tomB : tr.tomA;
        for (s = 0; s < SPB; s++) if (tpat[s] === 'x') hit(base + s, 'tom', 0.7);
      }
      // 심벌(구간 첫 박)
      if (b === 2 || b === 6 || b === 10) ev[base].x.push(['crash', 1]);
      if (b === 14) ev[base].x.push(['riser', 2]);
      // 베이스
      var bp = isB ? tr.bB : tr.bA, hits = [];
      for (s = 0; s < SPB; s++) if (bp[s] === 'x' || bp[s] === 'O') hits.push(s);
      for (i = 0; i < hits.length; i++) {
        var nx = i + 1 < hits.length ? hits[i + 1] : 16, o = bp[hits[i]] === 'O' ? 7 : 0;
        if (tr.bass === 'walk') o += [0, 4, 2, 4][i % 4] === 0 ? 0 : [0, 4, 2, 4][i % 4];
        ev[base + hits[i]].b = { m: scNote(tr, deg[b] + o), len: Math.max(1, nx - hits[i]), v: (i % 4 === 0 ? 1 : 0.8) };
      }
      // 화음(패드 · 스탭 · 전자피아노)
      var co = chordIdx(tr), notes = co.map(function (o) { return scNote(tr, deg[b] + 7 + o); });
      if (tr.pad === 'stab') {
        for (s = 0; s < SPB; s++) if (tr.stab[s] === 'x') ev[base + s].p = { n: notes, len: 2 };
      } else if (tr.pad === 'epiano') {
        for (s = 0; s < SPB; s++) if (tr.ep[s] === 'x') ev[base + s].p = { n: notes, len: 5 };
      } else ev[base].p = { n: notes, len: 16 };
      // 아르페지오
      if (tr.arp && S !== 'T' || tr.arp && b === 14) {
        var k = 0, tones = [0, 2, 4, 7];
        for (s = 0; s < SPB; s += tr.arp.step) { ev[base + s].a = { m: scNote(tr, deg[b] + 14 + tones[tr.arp.seq[k % tr.arp.seq.length]]) }; k++; }
      }
    }
    // 멜로디: A = P1 P2 P1 P2′ · B = Q1 Q2 Q1′ Q2″ · A′ = P1 P3 P1 마무리
    var P1 = genMotif(R, tr.rh), P2 = genMotif(R, tr.rh), P3 = genMotif(R, tr.rh), Q1 = genMotif(R, tr.rh), Q2 = genMotif(R, tr.rh);
    function copy(m, up, endc, stretch) {
      var o = m.map(function (n) { return { s: n.s, len: n.len, c: n.c + (up || 0) }; }), l = o[o.length - 1];
      if (endc != null) l.c = endc;
      if (stretch) l.len = Math.max(l.len, 16 - l.s);
      return o;
    }
    var phr = [null, null, copy(P1), copy(P2), copy(P1), copy(P2, 0, 2),
      copy(Q1), copy(Q2), copy(Q1, 1), copy(Q2, 0, 4),
      copy(P1, 0, null), copy(P3), copy(P1, 1), copy(P2, 0, 0, true), null, null];
    for (b = 0; b < BARS; b++) {
      if (!phr[b]) continue;
      phr[b].forEach(function (n) {
        var idx = deg[b] + 14 + n.c, m = scNote(tr, idx);
        while (m > tr.lr[1]) { idx -= 7; m = scNote(tr, idx); }
        while (m < tr.lr[0]) { idx += 7; m = scNote(tr, idx); }
        var skip = (sec[b] === 'A' && n.s % 4 !== 0 && R() < 0.12); // 숨 쉬는 자리
        if (!skip) ev[b * SPB + n.s].l = { m: m, len: n.len, v: n.s % 4 === 0 ? 1 : 0.8 };
      });
    }
    tr._ev = ev;
    return ev;
  }

  /* -- 악기 -- */
  function drum(e, dest, t, type, vel, tr, dv) {
    var h = H(e, dest, t, vel * dv, 1), kit = tr.kit, st;
    if (type === 'k') {
      st = kit.k;
      if (st === 'punch') {
        h.tone(0, { f: 165, f2: 46, sw: 0.35, dur: 0.3, vol: 0.95, a: 0.001 });
        h.noise(0, { type: 'highpass', f: 2500, dur: 0.012, vol: 0.2, a: 0.0008 });
        h.tone(0, { type: 'triangle', f: 95, f2: 50, dur: 0.12, vol: 0.25, a: 0.001 });
      } else if (st === 'soft') {
        h.tone(0, { f: 125, f2: 48, sw: 0.4, dur: 0.34, vol: 0.8, a: 0.002 });
        h.noise(0, { type: 'lowpass', f: 1200, dur: 0.012, vol: 0.15, a: 0.001 });
      } else if (st === 'taiko') {
        h.tone(0, { f: 105, f2: 52, sw: 0.5, dur: 0.55, vol: 1.0, a: 0.002 });
        h.noise(0, { type: 'bandpass', f: 250, q: 1, dur: 0.22, vol: 0.3, a: 0.002 });
        h.tone(0, { type: 'triangle', f: 210, f2: 110, dur: 0.25, vol: 0.15, a: 0.002 });
      } else { h.tone(0, { f: 95, f2: 36, sw: 0.5, dur: 0.65, vol: 0.9, a: 0.002 }); }
    } else if (type === 's') {
      st = kit.s;
      if (st === 'clap') {
        [0, 0.011, 0.023].forEach(function (d) { h.noise(d, { type: 'bandpass', f: 1500, q: 1.1, dur: 0.02, vol: 0.3, a: 0.001 }); });
        h.noise(0.03, { type: 'bandpass', f: 1400, q: 0.9, dur: 0.16, vol: 0.3, a: 0.002 });
      } else if (st === 'rim') {
        h.tone(0, { type: 'square', f: 1700, f2: 1200, dur: 0.02, vol: 0.12, lp: 4000, a: 0.001 });
        h.noise(0, { type: 'bandpass', f: 3000, q: 1.5, dur: 0.03, vol: 0.3, a: 0.001 });
        h.tone(0, { f: 400, f2: 300, dur: 0.05, vol: 0.2, a: 0.001 });
      } else {
        h.noise(0, { type: 'bandpass', f: 1900, q: 0.6, dur: 0.17, vol: 0.42, a: 0.001 });
        h.noise(0, { type: 'highpass', f: 5000, dur: 0.09, vol: 0.2, a: 0.001 });
        h.tone(0, { type: 'triangle', f: 210, f2: 130, dur: 0.1, vol: 0.3, a: 0.001 });
      }
    } else if (type === 'h') {
      st = kit.h;
      if (st === 'shaker') h.noise(0, { type: 'bandpass', f: 7000, q: 1, dur: 0.07, vol: 0.12, a: 0.02 });
      else if (st === 'dusty') h.noise(0, { type: 'highpass', f: 6000, dur: 0.05, vol: 0.09, a: 0.001 });
      else h.noise(0, { type: 'highpass', f: 8000, dur: 0.035, vol: 0.13, a: 0.001 });
    } else if (type === 'ho') {
      h.noise(0, { type: 'highpass', f: 7500, dur: 0.2, vol: 0.1, a: 0.002 });
    } else if (type === 'tom') {
      var f = 90 + 40 * hash01(Math.floor(t * 1000));
      h.tone(0, { f: f * 1.7, f2: f, sw: 0.5, dur: 0.3, vol: 0.6, a: 0.002 });
      h.noise(0, { type: 'bandpass', f: f * 6, q: 1, dur: 0.05, vol: 0.12, a: 0.001 });
    } else if (type === 'crash') {
      h.noise(0, { type: 'highpass', f: 5000, dur: 1.6, vol: 0.2, a: 0.002 });
      h.noise(0, { type: 'bandpass', f: 9000, q: 0.7, dur: 1.2, vol: 0.12, a: 0.002 });
    } else if (type === 'riser') {
      return;
    }
  }
  var DRUM_LAYER = { k: 'kick', s: 'kick', tom: 'kick', h: 'hat', ho: 'hat', crash: 'extra' };

  function bassNote(e, dest, t, dur, m, v, tr) {
    var f = mtof(m), st = tr.bass;
    if (st === 'sub') {
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: 0.4, a: 0.008, r: 0.08, lp: 700 }, 1, v);
      osc(e, dest, t, dur, { type: 'triangle', f: f * 2, vol: 0.17, a: 0.008, r: 0.06, lp: 1400 }, 1, v);
    } else if (st === 'saw') {
      osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: 0.2, a: 0.005, r: 0.05, lp: 1400, lp2: 350, lpt: 0.18, q: 2 }, 1, v);
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: 0.26, a: 0.005, r: 0.05 }, 1, v);
    } else if (st === 'pluck') {
      osc(e, dest, t, dur, { type: 'square', f: f, vol: 0.18, a: 0.002, dec: 0.12, sus: 0.3, r: 0.04, lp: 2400, lp2: 400, lpt: 0.12, q: 3 }, 1, v);
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: 0.3, a: 0.004, r: 0.05 }, 1, v);
    } else if (st === 'drive') {
      osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: 0.2, a: 0.004, r: 0.04, lp: 900, q: 2 }, 1, v);
      osc(e, dest, t, dur, { type: 'square', f: f * 0.5, vol: 0.12, a: 0.004, r: 0.04, lp: 500 }, 1, v);
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: 0.2, a: 0.004, r: 0.04 }, 1, v);
    } else { // walk
      osc(e, dest, t, dur, { type: 'triangle', f: f, vol: 0.34, a: 0.004, dec: 0.25, sus: 0.5, r: 0.06 }, 1, v);
      osc(e, dest, t, dur, { type: 'sine', f: f * 2, vol: 0.06, a: 0.004, r: 0.05 }, 1, v);
    }
  }
  function padChord(e, dest, t, len, sd, notes, v, tr) {
    var st = tr.pad, dur = len * sd * 0.98, pv = tr.pv;
    notes.forEach(function (m, i) {
      var f = mtof(m);
      if (st === 'warm') {
        osc(e, dest, t, dur, { type: 'triangle', f: f, vol: pv, a: 0.3, r: 0.5, lp: 1500, det: -5, pan: -0.55 }, 1, v);
        osc(e, dest, t, dur, { type: 'triangle', f: f, vol: pv, a: 0.3, r: 0.5, lp: 1500, det: 5, pan: 0.55 }, 1, v);
      } else if (st === 'saw') {
        osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: pv, a: 0.4, r: 0.5, lp: 700, lp2: 2200, lpt: 1.2, det: -9, pan: -0.6 }, 1, v);
        osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: pv, a: 0.4, r: 0.5, lp: 700, lp2: 2200, lpt: 1.2, det: 9, pan: 0.6 }, 1, v);
      } else if (st === 'string') {
        [-8, 0, 8].forEach(function (dt) {
          osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: pv * 0.7, a: 0.35, r: 0.6, lp: 2400, det: dt, pan: dt * 0.07, vib: { rate: 5, depth: 8, delay: 0.3 } }, 1, v);
        });
      } else if (st === 'glass') {
        osc(e, dest, t, dur, { type: 'sine', f: f, vol: pv, a: 0.5, r: 0.7, pan: -0.35 }, 1, v);
        osc(e, dest, t, dur, { type: 'sine', f: f * 2, vol: pv * 0.35, a: 0.6, r: 0.7, det: 6, pan: 0.35 }, 1, v);
      } else if (st === 'stab') {
        osc(e, dest, t, dur * 0.6, { type: 'square', f: f, vol: pv * 0.7, a: 0.004, dec: 0.07, sus: 0.25, r: 0.04, lp: 2600, lp2: 900, lpt: 0.1, pan: -0.35 }, 1, v);
        osc(e, dest, t, dur * 0.6, { type: 'sawtooth', f: f, vol: pv * 0.5, a: 0.004, dec: 0.07, sus: 0.25, r: 0.04, lp: 2600, det: 7, pan: 0.35 }, 1, v);
      } else { // epiano
        osc(e, dest, t + i * 0.012, dur, { type: 'sine', f: f, vol: pv, a: 0.004, dec: 0.5, sus: 0.3, r: 0.25, pan: i % 2 ? 0.3 : -0.3, fm: { r: 1, i: 0.5, dec: 0.5 } }, 1, v);
        osc(e, dest, t + i * 0.012, dur, { type: 'triangle', f: f * 2, vol: pv * 0.2, a: 0.004, dec: 0.2, sus: 0.2, r: 0.2 }, 1, v);
      }
    });
  }
  function arpNote(e, dest, t, dur, m, v, tr) {
    var st = tr.arp.style, f = mtof(m), vol = tr.arp.vol;
    if (st === 'pluck') osc(e, dest, t, dur, { type: 'triangle', f: f, vol: vol, a: 0.003, dec: 0.1, sus: 0.15, r: 0.05, lp: 3200 }, 1, v);
    else if (st === 'marimba') {
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: vol * 1.2, a: 0.002, dec: 0.12, sus: 0.1, r: 0.05, fm: { r: 4, i: 0.7, dec: 0.08 } }, 1, v);
    } else if (st === 'gate') osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: vol, a: 0.002, dec: 0.07, sus: 0.3, r: 0.03, lp: 3000, lp2: 700, lpt: 0.09, q: 2 }, 1, v);
    else if (st === 'bell') osc(e, dest, t, dur * 2, { type: 'sine', f: f, vol: vol, a: 0.002, dec: 0.5, sus: 0.08, r: 0.2, fm: { r: 3.5, i: 1.0, dec: 0.4 } }, 1, v);
    else osc(e, dest, t, dur, { type: 'square', f: f, vol: vol, a: 0.002, dec: 0.08, sus: 0.3, r: 0.03, lp: 3500 }, 1, v);
  }
  function leadNote(e, dest, t, dur, m, v, tr) {
    var st = tr.lead, f = mtof(m), vol = tr.lv;
    if (st === 'flute') {
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: vol, a: 0.045, r: 0.15, vib: { rate: 5.2, depth: 12, delay: 0.15 } }, 1, v);
      osc(e, dest, t, dur, { type: 'triangle', f: f * 2, vol: vol * 0.12, a: 0.05, r: 0.15 }, 1, v);
      nz(e, dest, t, 0.09, { type: 'bandpass', f: 3500, q: 1.5, vol: vol * 0.25, a: 0.01 }, 1, v);
    } else if (st === 'square') {
      osc(e, dest, t, dur, { type: 'square', f: f, vol: vol, a: 0.008, dec: 0.15, sus: 0.6, r: 0.08, lp: 3200 }, 1, v);
      osc(e, dest, t, dur, { type: 'square', f: f, vol: vol * 0.5, a: 0.008, r: 0.08, lp: 3200, det: 9, pan: 0.3 }, 1, v);
    } else if (st === 'saw') {
      osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: vol * 0.8, a: 0.012, r: 0.12, lp: 1400, lp2: 3200, lpt: 0.2, det: -8, pan: -0.25, vib: { rate: 5.5, depth: 10, delay: 0.2 } }, 1, v);
      osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: vol * 0.8, a: 0.012, r: 0.12, lp: 1400, lp2: 3200, lpt: 0.2, det: 8, pan: 0.25, vib: { rate: 5.5, depth: 10, delay: 0.2 } }, 1, v);
    } else if (st === 'bell') {
      osc(e, dest, t, dur * 1.5, { type: 'sine', f: f, vol: vol, a: 0.003, dec: 0.5, sus: 0.15, r: 0.25, fm: { r: 3.5, i: 1.3, dec: 0.5 } }, 1, v);
    } else if (st === 'brass') {
      [-6, 6].forEach(function (dt) {
        osc(e, dest, t, dur, { type: 'sawtooth', f: f, vol: vol, a: 0.03, r: 0.1, lp: 500, lp2: 2800, lpt: 0.09, det: dt, pan: dt * 0.05 }, 1, v);
      });
    } else { // whistle
      osc(e, dest, t, dur, { type: 'sine', f: f, vol: vol, a: 0.03, r: 0.12, vib: { rate: 6, depth: 22, delay: 0.1 } }, 1, v);
      osc(e, dest, t, dur, { type: 'triangle', f: f * 2, vol: vol * 0.15, a: 0.03, r: 0.1 }, 1, v);
    }
  }

  function layerGain(I, th) { var g = (I - th + 0.1) / 0.2; return g < 0 ? 0 : g > 1 ? 1 : g; }
  function intensityOf(inst, I) { return Math.min(1, Math.max(0, I + (inst.tr.ibias || 0))); }

  function startTrack(e, name, fadeIn, I, startPos) {
    var tr = TRACKS[name], c = e.ctx;
    if (!tr) return null;
    var now = c.currentTime, sd = 60 / tr.bpm / 4;
    var inst = { name: name, tr: tr, ev: compile(tr), sd: sd, step: 0, pos: startPos || 0, next: now + 0.06, L: {}, I: I };
    inst.gain = c.createGain();
    inst.gain.gain.setValueAtTime(0.0001, now);
    inst.gain.gain.linearRampToValueAtTime(1, now + (fadeIn || 0.05));
    inst.gain.connect(e.bgmBus);
    var ib = intensityOf(inst, I);
    LAYER_NAMES.forEach(function (ln) {
      var g = c.createGain(), last = g, rv = (tr.rv && tr.rv[ln]) || (ln === 'extra' ? 0.3 : 0);
      g.gain.value = layerGain(ib, LAYERS[ln]);
      if (c.createStereoPanner) { var pn = c.createStereoPanner(); pn.pan.value = LAYER_PAN[ln]; g.connect(pn); last = pn; }
      last.connect(inst.gain);
      if (rv > 0) { var sg = c.createGain(); sg.gain.value = rv; last.connect(sg); sg.connect(e.rvBgm); }
      inst.L[ln] = g;
    });
    // 리드 메아리(점8분, 오른쪽으로 살짝)
    var dl = c.createDelay(2), fb = c.createGain(), wet = c.createGain(), lpf = c.createBiquadFilter();
    dl.delayTime.value = sd * 3; fb.gain.value = 0.32; wet.gain.value = tr.dly || 0.3;
    lpf.type = 'lowpass'; lpf.frequency.value = 2600;
    inst.L.lead.connect(dl); dl.connect(lpf); lpf.connect(fb); fb.connect(dl); lpf.connect(wet);
    if (c.createStereoPanner) { var dp = c.createStereoPanner(); dp.pan.value = 0.4; wet.connect(dp); dp.connect(inst.gain); } else wet.connect(inst.gain);
    return inst;
  }
  function setInstIntensity(inst, ctx, I, smooth) {
    inst.I = I;
    var ib = intensityOf(inst, I), t = ctx.currentTime;
    LAYER_NAMES.forEach(function (ln) {
      var g = layerGain(ib, LAYERS[ln]);
      try { if (smooth) inst.L[ln].gain.setTargetAtTime(g, t, 0.25); else inst.L[ln].gain.value = g; } catch (x) { inst.L[ln].gain.value = g; }
    });
  }
  function playStep(e, inst, s, t) {
    var tr = inst.tr, ev = inst.ev[s], sd = inst.sd, dv = tr.dv == null ? 1 : tr.dv, L = inst.L, i;
    for (i = 0; i < ev.d.length; i++) drum(e, L[DRUM_LAYER[ev.d[i][0]]], t, ev.d[i][0], ev.d[i][1], tr, dv);
    for (i = 0; i < ev.x.length; i++) {
      if (ev.x[i][0] === 'crash') drum(e, L.extra, t, 'crash', 1, tr, dv);
      else if (ev.x[i][0] === 'riser') {
        var bar2 = 32 * sd;
        nz(e, L.extra, t, bar2, { type: 'bandpass', f: 400, f2: 7000, q: 2, vol: 0.14, a: bar2 * 0.85 }, 1, 1);
        osc(e, L.extra, t, bar2, { type: 'sawtooth', f: mtof(tr.root + 24), f2: mtof(tr.root + 36), vol: 0.03, a: bar2 * 0.8, lp: 1500 }, 1, 1);
      }
    }
    if (ev.b) bassNote(e, L.bass, t, ev.b.len * sd * 0.92, ev.b.m, ev.b.v * ev.g, tr);
    if (ev.p) padChord(e, L.pad, t, ev.p.len, sd, ev.p.n, ev.g, tr);
    if (ev.a) arpNote(e, L.arp, t, sd * 1.4, ev.a.m, ev.g, tr);
    if (ev.l) leadNote(e, L.lead, t, Math.max(0.05, ev.l.len * sd * 0.9), ev.l.m, ev.l.v, tr);
  }
  // inst.next 가 until 보다 앞인 동안 한 칸씩 예약 (16마디를 한 번 돌고 나면 인트로를 건너뛰고 A 로)
  function pump(e, inst, until) {
    var sd = inst.sd;
    while (inst.next < until) {
      var s = inst.pos, sw = (s % 2) ? inst.tr.swing * sd : 0;
      playStep(e, inst, s, inst.next + sw);
      inst.step++; inst.pos = s + 1 >= TOTAL ? LOOP_START : s + 1; inst.next += sd;
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
  function state() { return { master: S.master, sfx: S.sfx, bgm: S.bgm, muted: S.muted, unlocked: unlocked, track: cur ? cur.name : null, intensity: INTENSITY }; }

  function stopTimer() { if (timer) { clearInterval(timer); timer = null; } }
  function tick() {
    if (!cur || !running()) return;
    var now = ctx.currentTime;
    while (cur.next < now - 0.05) { cur.step++; cur.pos = cur.pos + 1 >= TOTAL ? LOOP_START : cur.pos + 1; cur.next += cur.sd; } // 밀렸으면 박자만 맞춰 건너뜀
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
      try { inst.gain.disconnect(); LAYER_NAMES.forEach(function (ln) { inst.L[ln].disconnect(); }); } catch (x) { /* 무시 */ }
      var i = fading.indexOf(inst); if (i >= 0) fading.splice(i, 1);
    }, 1600);
  }
  function syncBgm() {
    if (!ctx || !eng) return;
    if (!canSound()) return;
    var want = wantTrack;
    if (cur && cur.name === want) return;
    if (cur) { fadeOut(cur); cur = null; }
    if (want) { cur = startTrack(eng, want, 0.8, INTENSITY); if (cur) { startTimer(); tick(); } }
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
  function setIntensity(v) {
    INTENSITY = num01(v, INTENSITY);
    if (cur && ctx) setInstIntensity(cur, ctx, INTENSITY, true);
    emit();
    return INTENSITY;
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
  // opt: seconds sampleRate seed levels sfx[{name,at,vol,rate,pan,x,dist}] bgm intensity bgmPos(시작 칸) stereo(true면 오른쪽 채널도)
  function render(opt) {
    var OC = global.OfflineAudioContext || global.webkitOfflineAudioContext;
    var sr = opt.sampleRate || 44100, secs = opt.seconds || 2;
    var oc = new OC(2, Math.ceil(sr * secs), sr), keep = rnd;
    rnd = mulberry(opt.seed || 1);
    var e, inst;
    try {
      e = makeEngine(oc);
      applyLevels(e, opt.levels || S, false);
      (opt.sfx || []).forEach(function (ev) {
        playSfx(e, ev.name, { vol: ev.vol, rate: ev.rate, pan: ev.pan, x: ev.x, dist: ev.dist }, ev.at == null ? 0.02 : ev.at);
      });
      if (opt.bgm) { inst = startTrack(e, opt.bgm, 0.03, opt.intensity == null ? 1 : opt.intensity, opt.bgmPos || 0); if (inst) pump(e, inst, secs + 0.1); }
    } finally { rnd = keep; }
    return oc.startRendering().then(function (buf) {
      return { data: buf.getChannelData(0), dataR: buf.getChannelData(1), played: e.played, dropped: e.dropped, sampleRate: sr, endPos: inst ? inst.pos : -1, endStep: inst ? inst.step : -1 };
    });
  }

  /* ---------- 공개 ---------- */
  loadSettings();
  if (global.document) {
    attachGesture();
    try { global.document.addEventListener('visibilitychange', onVis); } catch (x) { /* 무시 */ }
  }
  global.BrjAudio = {
    unlock: unlock, sfx: sfx, bgm: bgm, setIntensity: setIntensity,
    intensity: function () { return INTENSITY; },
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
    skillSfx: skillSfx,
    skillIds: function () { return SKILL_IDS.slice(); },
    sfxInfo: function (n) { var d = SFX[n]; return d ? { name: n, dur: d.d, priority: d.p, gap: d.gap, variants: d.n } : null; },
    version: 2,
    // 시험용
    _render: render,
    _sfxDur: function (n) { return SFX[n] ? SFX[n].d : 0; },
    _sfxMeta: function (n) { var d = SFX[n]; return d ? { d: d.d, p: d.p, gap: d.gap, n: d.n, wet: d.wet } : null; },
    _trackInfo: function (n) {
      var t = TRACKS[n]; if (!t) return null;
      return { bpm: t.bpm, bars: BARS, introBars: 2, loopBars: BARS - 2, sd: 60 / t.bpm / 4, barSec: 60 / t.bpm * 4, root: t.root, sc: t.sc, kit: t.kit, pad: t.pad, bass: t.bass, lead: t.lead, arp: t.arp.style, swing: t.swing };
    },
    _forceHidden: function (v) { hiddenForced = v === null ? null : !!v; syncRun(); },
    _debug: function () {
      return { unlocked: unlocked, ctxState: ctx ? ctx.state : null, ctxCount: ctxCount, track: cur ? cur.name : null, step: cur ? cur.step : 0, pos: cur ? cur.pos : 0,
        want: wantTrack, timer: !!timer, played: eng ? eng.played : 0, dropped: eng ? eng.dropped : 0,
        active: eng ? eng.active.filter(function (x) { return x > ctx.currentTime; }).length : 0,
        masterGain: eng ? eng.master.gain.value : null, time: ctx ? ctx.currentTime : 0, intensity: INTENSITY,
        layers: cur ? LAYER_NAMES.map(function (ln) { return cur.L[ln].gain.value; }) : null };
    }
  };
})(typeof window !== 'undefined' ? window : this);
