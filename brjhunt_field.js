/* brjhunt_field.js — 브장신 키우기 사냥터 「넓은 필드」 전투 연출 엔진
 *
 * 전역 BrjField = { create(canvas, opts) → inst }
 * inst = { setState(st), start(), stop(), resize(), destroy(), on(name, cb) → off(), ... }
 *
 * 화면 전투는 연출이다. 골드·보상·스킬 효과 수치는 서버가 정한다.
 * 이 엔진은 st.kpm(기본 100) 마리/분 에 맞춰 처치 속도를 스스로 보정한다(몹 체력 배율 · 처치 연쇄).
 *
 * st = {stage, region, power, rate, party:[{id,n,gr}],
 *       skills:{active:[{id,lv,cd_s,power_pct,fx_color}|null x4], passive:id|null},
 *       boss:null|{img,name,hp[,res:'win'|'lose']}, kpm:100}
 * 이벤트: 'kill'{n,gold_view} 'hit'{crit} 'skill'{id} 'coin' 'boss'{phase:'in'|'win'|'lose'} 'levelup'
 *
 * 덧붙인 것(시험·연동용):
 *   inst.tick(dt)            한 번 갱신+그리기(시간 가속·외부 구동)   inst.sim(sec, dt)  그리지 않고 빠르게 돌린다
 *   inst.stats()             {kills,t,kpm,...}                          inst.cast(id)      스킬 강제 시전(시연)
 *   inst.bossResult('win'|'lose')   서버 판정이 오면 알린다(st.boss.res 로도 된다)
 *   opts: {base:'이미지 경로 앞부분', seed:숫자, manual:true(rAF 안 씀), timeScale:1, aspect:0.62, hudKpm:false}
 */
(function (root) {
  'use strict';

  // ---------- 상수 ----------
  const LH = 260;                 // 논리 높이(세로). 가로는 캔버스 비율대로.
  const WW = 5000;                // 세계 폭
  const HORIZON = 150;            // 하늘/땅 경계
  const Y0 = 180, Y1 = 242;       // 몬스터·병아리 발 높이 범위(앞뒤 깊이)
  const MAX_MOBS = 30;
  const FONT = '"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif';
  const REG_KEY = ['합정 골목', 'bhc', '홍대', '상수', '망원', '한강'];
  const HUE = [205, 28, 345, 262, 140, 190];
  const MON_EMOJI = ['🦐', '🥒', '💬', '🛵', '🐟', '🦆'];
  const GR_COL = { normal: '#98a2b8', rare: '#4aa3ff', epic: '#b678ff', unique: '#ffa23a', legend: '#ff5c7a' };
  const CHICK_HK = { atk1: 1.18, hit: 1.18, skill: 0.945 };   // 그림마다 몸 크기가 달라 보이는 키를 맞춘다
  const SKILL_IDS = ['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shield', 'shrimp', 'storm'];
  const SK = {   // 시연·폴백 값(서버가 power_pct·cd_s 를 주면 그걸 쓴다)
    slash: { col: '#ffffff', cd: 2.2, pct: 140 }, peck: { col: '#ffe27a', cd: 2.0, pct: 90 },
    spin: { col: '#8fe3ff', cd: 3.6, pct: 120 }, bomb: { col: '#ff9a3c', cd: 5, pct: 200 },
    thunder: { col: '#fff27a', cd: 5, pct: 220 }, fire: { col: '#ff6a2c', cd: 4.6, pct: 200 },
    egg: { col: '#ffd23c', cd: 6, pct: 260 }, shield: { col: '#6fd6ff', cd: 5, pct: 60, passive: true },
    shrimp: { col: '#ff8aa0', cd: 8, pct: 300 }, storm: { col: '#c78bff', cd: 14, pct: 500 }
  };

  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const N = v => { v = +v; return isFinite(v) ? v : 0; };
  function fmtNum(v) {
    v = Math.max(0, Math.round(v));
    if (v < 10000) return String(v);
    if (v < 100000000) { const m = v / 10000; return (m < 100 ? m.toFixed(1) : Math.round(m)) + '만'; }
    return (v / 100000000).toFixed(1) + '억';
  }
  function mulberry(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const hash = n => { n = Math.imul(n ^ 61, 0x45d9f3b); n = Math.imul(n ^ (n >>> 16), 0x45d9f3b); return ((n ^ (n >>> 16)) >>> 0) % 10000 / 10000; };

  function create(canvas, opts) {
    opts = opts || {};
    const rnd = opts.seed != null ? mulberry(opts.seed | 0) : Math.random;
    const base = opts.base || '';
    const manual = !!opts.manual;
    const hasDoc = typeof document !== 'undefined';
    const ctx = canvas.getContext('2d');

    // ---------- 상태 ----------
    const E = { // 엔진 전역
      t: 0, frames: 0, running: false, raf: 0, last: 0, destroyed: false, vis: true,
      cssW: 0, cssH: 0, dpr: 1, VW: 390, scale: 1, low: false, dtAvg: 0.016, lowN: 0,
      timeScale: opts.timeScale || 1, cam: 0, camLook: 0, shake: 0, flash: 0, flashCol: '#fff', tint: 0, tintCol: '#c78bff',
      kills: 0, ctl: 1, ctlT: 0, killLog: [], combo: 0, comboT: 0, comboPunch: 0, comboMax: 0,
      uid: 1, coinT: 0, levelT: 0, chainQ: [], pending: 0
    };
    const st = { stage: 1, region: '', power: 100, rate: 0, party: [], skills: { active: [null, null, null, null], passive: null }, boss: null, kpm: 100 };
    const D = { reg: 0, unit: 20, kpm: 100 };
    const listeners = {};
    const emit = (n, p) => { const a = listeners[n]; if (a) for (let i = 0; i < a.length; i++) { try { a[i](p || {}); } catch (e) { } } };

    // ---------- 그림 ----------
    const cache = {};
    function ld(src) {
      let c = cache[src];
      if (!c) {
        if (typeof Image === 'undefined') return null;
        c = cache[src] = { im: new Image(), ok: false };
        c.im.onload = () => { c.ok = true; }; c.im.onerror = () => { c.ok = false; c.bad = true; };
        c.im.src = base + src;
      }
      return c.ok ? c.im : null;
    }
    const art = n => ld('img/brjhunt/' + n + '.webp');
    const fxImg = id => ld('img/brjhunt/fx/fx_' + id + '.webp');
    function preload() {
      ['idle', 'atk1', 'atk2', 'hit', 'skill'].forEach(p => art('chick_' + p));
      art('m' + (D.reg + 1) + '_idle'); art('m' + (D.reg + 1) + '_hit'); art('bg' + (D.reg + 1));
      st.skills.active.forEach(s => { if (s && s.id) fxImg(s.id); });
      if (st.skills.passive) fxImg(st.skills.passive);
    }
    const ec = {};
    function emo(ch, px) {   // 이모지는 한 번만 그려 둔다(그림이 없을 때 폴백)
      const k = ch + px; let c = ec[k];
      if (!c) {
        if (!hasDoc) return null;
        const sz = Math.ceil(px * 1.4 * 2); c = document.createElement('canvas'); c.width = c.height = sz;
        const x = c.getContext('2d'); x.font = Math.round(px * 2) + 'px ' + FONT; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(ch, sz / 2, sz / 2);
        c.dw = sz / 2; ec[k] = c;
      }
      return c;
    }

    // ---------- 세계 ----------
    const spots = [];
    for (let i = 0; i < 9; i++) spots.push({ x: 380 + i * ((WW - 760) / 8) + (rnd() - 0.5) * 160, stock: 20 + (rnd() * 10 | 0), cool: 0, visit: -99, n: 0 });
    const chick = { ty: 2, x: spots[1].x - 80, y: 212, vx: 0, face: 1, pose: 'idle', poseT: 0, lunge: 0, atkT: 0.3, alt: 0, hitIn: 0, hurt: 0, kbx: 0, cast: 0, spot: spots[1], spotT: 0, tx: 0, ty2: 212, target: null, retarget: 0, dust: 0, run: 0, down: 0, aura: 0 };
    spots[1].visit = 0;
    let mobs = [];
    const allies = [];
    let boss = null;
    const props = [];
    let propsReg = -1;
    const slotCd = [0, 0, 0, 0];
    let castLock = 0;
    let auraT = 2.5;

    // 풀: 입자 · 숫자 · 이펙트
    const PMAX = 170, TMAX = 40, FMAX = 40;
    const parts = [], texts = [], fxs = [];
    for (let i = 0; i < PMAX; i++) parts.push({ on: false, k: '', x: 0, y: 0, vx: 0, vy: 0, t: 0, life: 1, r: 2, c: '#fff', rot: 0, vr: 0, b: 0 });
    for (let i = 0; i < TMAX; i++) texts.push({ on: false, s: '', x: 0, y: 0, vy: 0, t: 0, life: 1, size: 14, col: '#fff', crit: false });
    for (let i = 0; i < FMAX; i++) fxs.push({ on: false });
    let pCur = 0;
    function newPart(k, x, y, vx, vy, life, r, c) {
      const lim = E.low ? PMAX * 0.45 : PMAX;
      let p = null;
      for (let n = 0; n < lim; n++) { const q = parts[(pCur + n) % lim]; if (!q.on) { p = q; pCur = (pCur + n + 1) % lim; break; } }
      if (!p) { if (k !== 'coin' && k !== 'ring') return null; p = parts[pCur = (pCur + 1) % lim]; }   // 꽉 찼으면 코인·고리만 하나 뺏어 온다
      p.on = true; p.k = k; p.x = x; p.y = y; p.vx = vx; p.vy = vy; p.t = 0; p.life = life; p.r = r; p.c = c; p.rot = rnd() * 6.28; p.vr = (rnd() - 0.5) * 12; p.b = 0;
      return p;
    }
    function say(s, x, y, size, col, crit) {
      let t = null, oldest = null;
      for (let i = 0; i < TMAX; i++) { const q = texts[i]; if (!q.on) { t = q; break; } if (!oldest || q.t > oldest.t) oldest = q; }
      if (!t) { if (!crit) return; t = oldest; }
      // 같은 자리에 겹치지 않게 살짝 어긋나게
      let k = 0; for (let i = 0; i < TMAX; i++) { const q = texts[i]; if (q.on && q.t < 0.35 && Math.abs(q.x - x) < 30 && Math.abs(q.y - y) < 16) k++; }
      t.on = true; t.s = s; t.x = x + (k ? (k % 2 ? 1 : -1) * 14 : 0); t.y = y - Math.min(k, 4) * 13; t.vy = -46; t.t = 0; t.life = crit ? 1.05 : 0.8; t.size = size; t.col = col; t.crit = !!crit;
    }
    function addFx(o) {
      for (let i = 0; i < FMAX; i++) if (!fxs[i].on) { const f = fxs[i]; for (const k in f) delete f[k]; Object.assign(f, o); f.on = true; f.t = f.t || 0; f.uid = E.uid++; return f; }
      return null;
    }
    const poof = (x, y, c, n, sp) => { for (let i = 0; i < n; i++) { const a = rnd() * 6.28, s = (sp || 70) * (0.4 + rnd()); newPart('dot', x, y, Math.cos(a) * s, Math.sin(a) * s - 30, 0.4 + rnd() * 0.2, 1.6 + rnd() * 2, c); } };
    const ring = (x, y, c, r, life) => newPart('ring', x, y, 0, 0, life || 0.4, r || 40, c);

    // ---------- 파생 ----------
    function derive() {
      D.unit = Math.max(1, Math.round(Math.max(5, st.power) * 0.22));
      D.kpm = clamp(N(st.kpm) || 100, 10, 300);
      const rg = String(st.region || '').toLowerCase(); let ri = -1;
      for (let i = 0; i < 6; i++) if (rg.indexOf(REG_KEY[i]) >= 0) { ri = i; break; }
      if (ri < 0) ri = Math.floor((Math.max(1, st.stage) - 1) / 5) % 6;
      const changed = ri !== D.reg;
      D.reg = ri;
      if (changed || propsReg !== ri) buildProps();
      preload();
    }

    // ---------- 소품 (그림 없이 도형으로 한 번만 그려 둔다) ----------
    const propArt = {};
    function mk(w, h, fn) { if (!hasDoc) return null; const c = document.createElement('canvas'); c.width = w * 2; c.height = h * 2; c.dw = w; c.dh = h; const x = c.getContext('2d'); x.scale(2, 2); fn(x); return c; }
    function blob(x, cx, cy, r, col) { x.fillStyle = col; x.beginPath(); x.arc(cx, cy, r, 0, 6.3); x.fill(); }
    function buildProps() {
      propsReg = D.reg; const h = HUE[D.reg];
      const gh = 95 + (h % 50);   // 풀색은 초록 계열 안에서만 지역별로 살짝 다르게
      const dark = 'hsl(' + gh + ',38%,22%)', mid = 'hsl(' + gh + ',45%,34%)', lite = 'hsl(' + (gh + 8) + ',50%,46%)';
      propArt.bush = mk(70, 40, x => { blob(x, 20, 28, 15, dark); blob(x, 46, 27, 17, dark); blob(x, 33, 20, 17, mid); blob(x, 20, 26, 12, mid); blob(x, 48, 25, 13, mid); blob(x, 28, 15, 8, lite); blob(x, 42, 19, 6, lite); });
      propArt.rock = mk(44, 28, x => { x.fillStyle = '#6b7088'; x.beginPath(); x.moveTo(3, 26); x.quadraticCurveTo(2, 8, 18, 5); x.quadraticCurveTo(38, 2, 41, 26); x.closePath(); x.fill(); x.fillStyle = '#8c92aa'; x.beginPath(); x.moveTo(10, 14); x.quadraticCurveTo(18, 7, 30, 9); x.quadraticCurveTo(22, 14, 10, 14); x.fill(); x.strokeStyle = 'rgba(0,0,0,.35)'; x.lineWidth = 1.2; x.beginPath(); x.moveTo(3, 26); x.quadraticCurveTo(2, 8, 18, 5); x.quadraticCurveTo(38, 2, 41, 26); x.stroke(); });
      propArt.crate = mk(40, 40, x => { x.fillStyle = '#b57a3c'; x.fillRect(4, 6, 32, 32); x.strokeStyle = '#7a4a1f'; x.lineWidth = 2.4; x.strokeRect(4, 6, 32, 32); x.beginPath(); x.moveTo(4, 6); x.lineTo(36, 38); x.moveTo(36, 6); x.lineTo(4, 38); x.stroke(); x.fillStyle = 'rgba(255,255,255,.18)'; x.fillRect(5, 7, 30, 5); });
      propArt.lamp = mk(26, 96, x => { x.fillStyle = '#2d3142'; x.fillRect(11, 14, 4, 80); x.fillRect(7, 90, 12, 6); x.beginPath(); x.moveTo(5, 14); x.lineTo(21, 14); x.lineTo(18, 4); x.lineTo(8, 4); x.closePath(); x.fill(); const g = x.createRadialGradient(13, 10, 1, 13, 10, 14); g.addColorStop(0, 'rgba(255,240,170,.95)'); g.addColorStop(1, 'rgba(255,200,80,0)'); x.fillStyle = g; x.fillRect(-2, -6, 30, 32); });
      propArt.sign = mk(54, 62, x => { x.fillStyle = '#5a4630'; x.fillRect(25, 24, 5, 36); x.fillStyle = '#fff3d1'; x.strokeStyle = '#7a5a30'; x.lineWidth = 2.2; x.beginPath(); x.roundRect ? x.roundRect(4, 3, 46, 26, 5) : x.rect(4, 3, 46, 26); x.fill(); x.stroke(); x.fillStyle = '#ef5a6f'; x.fillRect(10, 10, 34, 4); x.fillStyle = '#e9b24a'; x.fillRect(10, 18, 24, 3); });
      propArt.flower = mk(44, 28, x => { for (let i = 0; i < 6; i++) { const fx = 6 + i * 6.4, fy = 22 - (i % 3) * 3; x.strokeStyle = '#3f8f4a'; x.lineWidth = 1.5; x.beginPath(); x.moveTo(fx, 27); x.lineTo(fx, fy); x.stroke(); blob(x, fx, fy - 1, 3.2, ['#ff7a9c', '#ffd23c', '#fff', '#b678ff', '#ff9a3c', '#4aa3ff'][i]); blob(x, fx, fy - 1, 1.2, '#fff6c0'); } });
      propArt.tuft = mk(26, 16, x => { x.strokeStyle = 'hsl(' + gh + ',50%,40%)'; x.lineWidth = 2; x.lineCap = 'round'; for (let i = 0; i < 5; i++) { x.beginPath(); x.moveTo(4 + i * 4.5, 15); x.quadraticCurveTo(5 + i * 4.5 + (i - 2) * 2, 8, 3 + i * 5 + (i - 2) * 3, 2 + (i % 2) * 3); x.stroke(); } });
      propArt.fg = mk(120, 40, x => { x.fillStyle = 'hsl(' + gh + ',40%,14%)'; for (let i = 0; i < 6; i++) { x.beginPath(); x.arc(10 + i * 20, 40, 18 + (i % 3) * 5, Math.PI, 0); x.fill(); } x.fillStyle = 'hsl(' + gh + ',40%,22%)'; for (let i = 0; i < 5; i++) { x.beginPath(); x.arc(20 + i * 20, 40, 11 + (i % 2) * 5, Math.PI, 0); x.fill(); } });
      props.length = 0;
      const names = ['bush', 'rock', 'crate', 'lamp', 'sign', 'flower', 'tuft', 'tuft', 'bush', 'flower'];
      const S0 = D.reg * 131;
      for (let i = 0; i < 90; i++) {
        const nm = names[(hash(i + S0) * names.length) | 0];
        const back = hash(i * 7 + 3 + S0) < 0.62;
        const sc = nm === 'tuft' ? 1 : 0.85 + hash(i * 13 + S0) * 0.4;
        props.push({ ty: 0, nm, x: 40 + hash(i * 5 + 11 + S0) * (WW - 80), y: back ? HORIZON + 8 + hash(i * 3 + S0) * 12 : Y1 + 12 + hash(i * 3 + S0) * 8, sc: sc * (nm === 'lamp' ? 1.2 : 1), flip: hash(i + 99) < 0.5 });
      }
      props.sort((a, b) => a.x - b.x);
      // 땅의 얼룩(자갈·무늬) — 세계 좌표
      groundMarks.length = 0;
      for (let i = 0; i < 120; i++) groundMarks.push({ x: hash(i * 17 + S0) * WW, y: HORIZON + 14 + hash(i * 29 + S0) * (LH - HORIZON - 20), w: 6 + hash(i * 7) * 22, a: 0.06 + hash(i * 3) * 0.08 });
    }
    const groundMarks = [];

    // ---------- 몬스터 ----------
    function pickSpot() {
      let tot = 0; const w = [];
      for (let i = 0; i < spots.length; i++) { const s = spots[i]; let v = 0; if (s.stock > 0 && s.n < 7) v = 1 / (1 + Math.abs(s.x - chick.x) / 500); w.push(v); tot += v; }
      if (tot <= 0) return null;
      let r = rnd() * tot; for (let i = 0; i < spots.length; i++) { r -= w[i]; if (r <= 0) return spots[i]; }
      return spots[0];
    }
    function spawnMob(spot, near) {
      const el = rnd() < 0.07;
      const x = clamp(spot.x + (rnd() - 0.5) * 300, 40, WW - 40);
      const m = {
        ty: 1, id: E.uid++, x, y: Y0 + rnd() * (Y1 - Y0), vx: 0, face: 1, hp: 1, max: 1, hit: 0, kb: 0, dead: -1, ph: rnd() * 6, sp: 46 + rnd() * 34,
        atk: 1 + rnd() * 1.5, lunge: 0, el, sc: (el ? 1.3 : 0.88 + rnd() * 0.26), spawnT: 0.35, spot, lane: (rnd() - 0.5) * 70, dvx: 0, dvy: 0, drot: 0, mark: 0, wander: rnd() * 6, wx: x
      };
      m.max = m.hp = Math.max(1, D.unit * 2.2 * E.ctl * (el ? 2.6 : 1) * (0.85 + rnd() * 0.3));
      spot.n++; spot.stock--;
      if (spot.stock <= 0) spot.cool = 9 + rnd() * 3;
      mobs.push(m);
      if (!E.low || rnd() < 0.5) poof(m.x, m.y - 20, 'rgba(255,255,255,.9)', 3, 40);
    }
    function aliveMobs() { let n = 0; for (let i = 0; i < mobs.length; i++) if (mobs[i].dead < 0) n++; return n; }

    // ---------- 피해 ----------
    function bossHurt(frac, crit, col, x) {
      const B = boss; if (!B || B.state !== 'fight') return;
      const was = B.hp; B.hp = Math.max(B.target, B.hp - B.hpMax * frac);
      B.hit = 0.14; B.kb = crit ? 9 : 5;
      const d = Math.max(1, Math.round(D.unit * (frac / 0.012) * (0.9 + rnd() * 0.2)));
      say(fmtNum(d) + (crit ? '!' : ''), B.x + (rnd() - 0.5) * 50, B.y - 130, crit ? 24 : 16, crit ? '#ffd23c' : (col || '#fff'), crit);
      poof(B.x - 20, B.y - 60, crit ? '#ffd23c' : '#fff', crit ? 5 : 2);
      if (crit) E.shake = Math.max(E.shake, 3);
      if (B.hp <= B.target) {
        if (B.res === 'win') { B.state = 'dying'; B.t = 0; E.shake = 9; E.flash = 0.5; for (let i = 0; i < 14; i++) coin(B.x + (rnd() - 0.5) * 60, B.y - 50); poof(B.x, B.y - 70, '#fff6c0', 18, 140); emit('boss', { phase: 'win' }); }
        else if (B.res === 'lose') { B.state = 'smash'; B.t = 0; }
      }
    }
    function coin(x, y) { newPart('coin', x, y, (rnd() - 0.5) * 120, -150 - rnd() * 90, 3.2, 4.2, '#ffd23c'); }
    function hurtMob(m, amt, crit, col, srcX, kn, noText) {
      if (m.dead >= 0 || m.spawnT > 0) return false;
      m.hp -= amt; m.hit = 0.16; m.kb += (m.x >= srcX ? 1 : -1) * (kn == null ? (crit ? 12 : 7) : kn);
      if (!noText) say(fmtNum(amt) + (crit ? '!' : ''), m.x + (rnd() - 0.5) * 16, m.y - 52 * m.sc, crit ? 22 : (amt > D.unit * 1.5 ? 18 : 15), crit ? '#ffd23c' : (col || '#fff'), crit);
      if (m.hp <= 0) { killMob(m, srcX); return true; }
      return false;
    }
    function killMob(m, srcX) {
      m.dead = 0; m.dvx = (m.x >= srcX ? 1 : -1) * (90 + rnd() * 90); m.dvy = -170 - rnd() * 90; m.drot = (rnd() < 0.5 ? -1 : 1) * (2 + rnd() * 4);
      if (m.spot) m.spot.n = Math.max(0, m.spot.n - 1);
      E.kills++; E.killLog.push(E.t); if (E.killLog.length > 600) E.killLog.shift();
      E.combo++; E.comboT = 2.6; E.comboPunch = 1; if (E.combo > E.comboMax) E.comboMax = E.combo;
      const nc = m.el ? 6 : (E.low ? 1 : 2);
      for (let i = 0; i < nc; i++) coin(m.x, m.y - 24);
      poof(m.x, m.y - 30 * m.sc, m.el ? '#ffd23c' : '#fff6c0', m.el ? 12 : 5, 90);
      if (m.el) { ring(m.x, m.y - 20, '#ffd23c', 50, 0.5); E.shake = Math.max(E.shake, 2); }
      if (E.chainQ.length < 10 && rnd() < 0.55) E.chainQ.push({ x: m.x, y: m.y, t: 0.07 });   // 처치 연쇄
      emit('kill', { n: E.kills, gold_view: N(st.rate) / (D.kpm * 60) });
    }
    function rangeMobs(x, y, rx, ry, out) {
      out.length = 0;
      for (let i = 0; i < mobs.length; i++) { const m = mobs[i]; if (m.dead >= 0 || m.spawnT > 0) continue; const dx = (m.x - x) / rx, dy = (m.y - y) / ry; if (dx * dx + dy * dy <= 1) out.push(m); }
      return out;
    }
    const tmpA = [];
    function aoe(x, y, rx, ry, dmg, col, o) {
      o = o || {}; let n = 0;
      const arr = rangeMobs(x, y, rx, ry, tmpA);
      if (o.max && arr.length > o.max) arr.sort((a, b) => Math.abs(a.x - x) - Math.abs(b.x - x));
      for (let i = 0; i < arr.length && (!o.max || i < o.max); i++) {
        const m = arr[i], crit = rnd() < (o.crit == null ? 0.25 : o.crit);
        hurtMob(m, Math.max(1, Math.round(dmg * (0.88 + rnd() * 0.24) * (crit ? 1.8 : 1))), crit, col, x, o.kn); n++;
      }
      if (boss && boss.state === 'fight' && Math.abs(boss.x - x) < rx + 60) bossHurt(o.bossFrac || 0.012 * (dmg / D.unit), true, col, x);
      return n;
    }

    // ---------- 병아리 AI ----------
    function nearestSpot(from) { let b = null, bd = 1e9; for (const s of spots) { const d = Math.abs(s.x - from); if (d < bd) { bd = d; b = s; } } return b; }
    function nextSpot() {
      let best = null, bs = 1e9;
      for (const s of spots) {
        if (s === chick.spot) continue;
        const sc = Math.abs(s.x - chick.x) + Math.max(0, 40 - (E.t - s.visit)) * 40 + (s.stock <= 0 ? 900 : 0) + rnd() * 260;
        if (sc < bs) { bs = sc; best = s; }
      }
      return best || chick.spot;
    }
    function pickTarget() {
      if (boss && boss.state !== 'dying' && boss.state !== 'leave') { chick.target = boss; return; }
      let best = null, bs = 1e9;
      for (let i = 0; i < mobs.length; i++) {
        const m = mobs[i]; if (m.dead >= 0 || m.spawnT > 0.15) continue;
        let nb = 0; for (let j = 0; j < mobs.length; j++) { const o = mobs[j]; if (o.dead < 0 && Math.abs(o.x - m.x) < 120) nb++; }
        const sc = Math.abs(m.x - chick.x) + Math.abs(m.y - chick.y) * 1.5 - nb * 26;
        if (sc < bs) { bs = sc; best = m; }
      }
      chick.target = best;
    }
    function updateChick(dt) {
      const c = chick;
      c.spotT += dt;
      if (c.spotT > 15 || (c.spot.stock <= 0 && c.spot.n <= 1 && c.spotT > 2)) { c.spot = nextSpot(); c.spotT = 0; c.spot.visit = E.t; }
      c.retarget -= dt; if (c.retarget <= 0 || (c.target && c.target.ty === 1 && c.target.dead >= 0)) { c.retarget = 0.22; pickTarget(); }
      c.hurt = Math.max(0, c.hurt - dt); c.kbx *= Math.exp(-dt * 10); c.lunge = Math.max(0, c.lunge - dt * 5); c.cast = Math.max(0, c.cast - dt);
      c.poseT -= dt; if (c.poseT <= 0 && c.pose !== 'down') c.pose = 'idle';
      let gx, gy, speed = 250;
      const T = c.target;
      if (c.down) { gx = c.x; gy = c.y; speed = 0; }
      else if (T) {
        const side = c.x < T.x ? -1 : 1;
        const stand = T.ty === 4 ? 100 : 46;
        gx = T.x + side * stand; gy = T.y + (T.ty === 4 ? 6 : 0);
        if (Math.abs(T.x - c.x) < 120 && T.ty === 1) speed = 150;   // 가까우면 살짝 내려서 붙는다
      } else {
        // 사냥터로 달려가 순찰한다
        const sp = c.spot; gx = sp.x + Math.sin(E.t * 0.7 + sp.x) * 150; gy = 190 + (Math.sin(E.t * 0.9) * 0.5 + 0.5) * 40;
      }
      const dx = gx - c.x; let want = Math.abs(dx) > 8 ? Math.sign(dx) * Math.min(speed, Math.abs(dx) * 7) : 0;
      c.vx += (want - c.vx) * Math.min(1, dt * 9);
      c.x = clamp(c.x + c.vx * dt, 30, WW - 30);
      c.y += (clamp(gy, Y0 - 4, Y1) - c.y) * Math.min(1, dt * 6);
      c.run = Math.abs(c.vx);
      // 바라보는 쪽: 대상이 있으면 대상, 없으면 달리는 쪽
      if (T && !c.down) { const d = T.x - c.x; if (Math.abs(d) > 10) c.face = d > 0 ? 1 : -1; } else if (Math.abs(c.vx) > 30) c.face = c.vx > 0 ? 1 : -1;
      // 달릴 때 흙먼지
      c.dust -= dt; if (c.run > 120 && c.dust <= 0) { c.dust = 0.09; newPart('dust', c.x - c.face * 14, c.y + 2, -c.face * (20 + rnd() * 20), -12 - rnd() * 10, 0.45, 3 + rnd() * 2, 'rgba(255,240,210,.6)'); }
      // 공격
      let inRange = null;
      if (!c.down) {
        if (boss && boss.state === 'fight') { if (Math.abs(boss.x - c.x) < 150 && Math.abs(boss.y - c.y) < 40) inRange = boss; }
        else {
          let bd = 1e9;
          for (let i = 0; i < mobs.length; i++) { const m = mobs[i]; if (m.dead >= 0 || m.spawnT > 0) continue; const dx2 = (m.x - c.x) * c.face, dy2 = m.y - c.y; if (dx2 > -14 && dx2 < 92 && Math.abs(dy2) < 34) { const d = Math.abs(dx2); if (d < bd) { bd = d; inRange = m; } } }
        }
      }
      c.atkT -= dt;
      if (inRange && c.atkT <= 0 && c.cast <= 0) {
        c.atkT = 0.3 + (c.run > 100 ? 0.04 : 0); c.alt ^= 1; c.pose = c.alt ? 'atk2' : 'atk1'; c.poseT = 0.24; c.lunge = 1; c.hitIn = 0.09;
      }
      if (c.hitIn > 0) { c.hitIn -= dt; if (c.hitIn <= 0) chickHit(); }
    }
    function chickHit() {
      const c = chick, crit = rnd() < 0.2;
      emit('hit', { crit });
      if (boss && boss.state === 'fight') { bossHurt(0.007 * (crit ? 1.8 : 1), crit, '#fff', c.x); newPart('slashfx', c.x + c.face * 56, c.y - 34, 0, 0, 0.16, 28, '#fff').vr = c.face; return; }
      const arr = rangeMobs(c.x + c.face * 22, c.y, 82, 40, tmpA);
      arr.sort((a, b) => Math.abs(a.x - c.x) - Math.abs(b.x - c.x));
      for (let i = 0; i < arr.length && i < 4; i++) hurtMob(arr[i], Math.max(1, Math.round(D.unit * (0.88 + rnd() * 0.24) * (crit ? 2 : 1))), crit, '#fff', c.x);
      const p = newPart('slashfx', c.x + c.face * 52, c.y - 34, 0, 0, 0.16, crit ? 36 : 28, crit ? '#ffd23c' : '#fff'); if (p) p.vr = c.face;
      if (crit) E.shake = Math.max(E.shake, 2);
    }

    // ---------- 몬스터 갱신 ----------
    function updateMobs(dt) {
      const c = chick;
      // 보충
      E.spawnT = (E.spawnT || 0) - dt;
      for (const s of spots) if (s.stock <= 0 && s.n <= 0) { s.cool -= dt; if (s.cool <= 0) { s.stock = 20 + (rnd() * 10 | 0); s.cool = 0; } }
      let al = aliveMobs();
      if (al >= MAX_MOBS - 4) {   // 멀리 남은 몹은 조용히 거둬 새 몹이 가까이에서 나오게 한다
        let far = null, fd = 1500;
        for (const m of mobs) if (m.dead < 0) { const d = Math.abs(m.x - c.x); if (d > fd) { fd = d; far = m; } }
        if (far) { far.dead = 0.5; far.dvx = 0; far.dvy = 0; far.drot = 0; far.quiet = true; if (far.spot) far.spot.n = Math.max(0, far.spot.n - 1); al--; }
      }
      if (!boss && E.spawnT <= 0 && al < Math.min(MAX_MOBS, opts.maxMobs || MAX_MOBS)) {
        const sp = pickSpot();
        if (sp) { const n = 1 + (rnd() < 0.5 ? 1 : 0); for (let i = 0; i < n && aliveMobs() < MAX_MOBS; i++) spawnMob(sp); }
        E.spawnT = al < 14 ? 0.12 : 0.3;
      }
      for (let i = mobs.length - 1; i >= 0; i--) {
        const m = mobs[i];
        if (m.dead >= 0) { m.dead += dt; m.x += m.dvx * dt; m.y += 0; m.dvy += 520 * dt; m.dy = (m.dy || 0) + m.dvy * dt; if (m.dead > 0.55) mobs.splice(i, 1); continue; }
        if (m.spawnT > 0) m.spawnT -= dt;
        m.hit = Math.max(0, m.hit - dt); m.kb *= Math.exp(-dt * 11); m.lunge = Math.max(0, m.lunge - dt * 4);
        // 달려드는 몹: 병아리가 가까우면 모여든다
        const dx = c.x - m.x, adx = Math.abs(dx);
        if (adx < 360 && !boss && !c.down) {
          const tx = c.x - Math.sign(dx) * (28 + (m.lane > 0 ? 16 : 0)), ty = clamp(c.y + m.lane * 0.6, Y0, Y1);
          const ddx = tx - m.x; if (Math.abs(ddx) > 6) m.x += Math.sign(ddx) * Math.min(m.sp, Math.abs(ddx) * 6) * dt;
          m.y += (ty - m.y) * Math.min(1, dt * 2.2);
          if (adx < 56) { m.atk -= dt; if (m.atk <= 0) { m.atk = 1.8 + rnd() * 1.4; m.lunge = 1; if (c.cast <= 0 && c.pose === 'idle' && rnd() < 0.5) { c.pose = 'hit'; c.poseT = 0.2; } c.hurt = 0.2; } }
          m.face = dx > 0 ? 1 : -1;
        } else if (!boss) {
          m.wander -= dt; if (m.wander <= 0) { m.wander = 2 + rnd() * 3; m.wx = clamp(m.spot ? m.spot.x + (rnd() - 0.5) * 360 : m.x, 40, WW - 40); }
          const ddx = m.wx - m.x; if (Math.abs(ddx) > 5) { m.x += Math.sign(ddx) * 18 * dt; m.face = ddx > 0 ? 1 : -1; }
        }
        m.x += m.kb * dt * 6; m.x = clamp(m.x, 20, WW - 20);
      }
      // 겹침 풀기(x)
      for (let i = 0; i < mobs.length; i++) { const a = mobs[i]; if (a.dead >= 0) continue; for (let j = i + 1; j < mobs.length; j++) { const b = mobs[j]; if (b.dead >= 0) continue; const dx = b.x - a.x; if (Math.abs(dx) < 20 && Math.abs(b.y - a.y) < 14) { const p = (20 - Math.abs(dx)) * 0.5 * Math.min(1, dt * 8) * (dx >= 0 ? 1 : -1); a.x -= p; b.x += p; } } }
    }

    // ---------- 스킬 ----------
    function nearestMobs(x, n, range, out) {
      out = out || []; out.length = 0;
      for (let i = 0; i < mobs.length; i++) { const m = mobs[i]; if (m.dead < 0 && m.spawnT <= 0 && Math.abs(m.x - x) < range) out.push(m); }
      out.sort((a, b) => Math.abs(a.x - x) - Math.abs(b.x - x));
      if (out.length > n) out.length = n;
      return out;
    }
    function denseCenter(range) {   // 몰려 있는 곳 중심
      let best = null, bn = -1;
      for (const m of mobs) { if (m.dead >= 0 || Math.abs(m.x - chick.x) > range) continue; let n = 0; for (const o of mobs) if (o.dead < 0 && Math.abs(o.x - m.x) < 90) n++; if (n > bn) { bn = n; best = m; } }
      return best;
    }
    function anyTargetNear(range) {
      if (boss && boss.state === 'fight') return Math.abs(boss.x - chick.x) < range + 100;
      for (const m of mobs) if (m.dead < 0 && m.spawnT <= 0 && Math.abs(m.x - chick.x) < range) return true;
      return false;
    }
    function cast(sl, silent) {
      const id = sl.id, cfg = SK[id]; if (!cfg || cfg.passive) return;
      const c = chick, f = c.face;
      const d = D.unit * (N(sl.power_pct) || cfg.pct) / 100;
      const col = sl.fx_color || cfg.col;
      c.cast = 0.45; castLock = 0.38; c.pose = 'skill'; c.poseT = 0.45; c.atkT = Math.max(c.atkT, 0.3);
      emit('skill', { id });
      const o = { k: id, x: c.x, y: c.y, face: f, d, col, t: 0 };
      switch (id) {
        case 'slash': o.life = 0.32; o.hitAt = 0.08; addFx(o); break;
        case 'peck': o.life = 0.7; o.n = 0; addFx(o); break;
        case 'spin': o.life = 0.62; o.hitAt = 0.12; o.hit2 = 0.38; addFx(o); break;
        case 'bomb': {
          const cand = nearestMobs(c.x, 12, 420, []); const pts = [];
          for (let i = 0; i < 3; i++) { const m = cand.length ? cand[(rnd() * cand.length) | 0] : null; pts.push(m ? { x: m.x + (rnd() - 0.5) * 30, y: m.y } : { x: c.x + f * (110 + i * 60), y: c.y }); }
          pts.forEach((p, i) => addFx({ k: 'bomb', x: p.x, y: p.y, d, col, t: -i * 0.14, life: 0.8, hitAt: 0.34 }));
          break; }
        case 'thunder': {
          const cand = nearestMobs(c.x, 8, 460, []); const n = Math.min(5, Math.max(cand.length, 1));
          for (let i = 0; i < n; i++) { const m = cand[i]; addFx({ k: 'thunder', x: m ? m.x : c.x + f * (100 + i * 70), y: m ? m.y : c.y, d, col, t: -i * 0.09, life: 0.5, hitAt: 0.04 }); }
          E.flash = 0.18; E.flashCol = '#fff8c0';
          break; }
        case 'fire': o.life = 0.95; o.x = c.x + f * 40; o.y = c.y - 20; addFx(o); break;
        case 'egg': {
          const m = denseCenter(420); const tx = m ? m.x : c.x + f * 220, ty = m ? m.y : c.y;
          o.life = 0.95; o.x0 = c.x + f * 20; o.y0 = c.y - 50; o.tx = tx; o.ty = ty; o.landed = false; addFx(o); break; }
        case 'shrimp': o.life = 0.9; o.x = c.x - f * 40; o.y = c.y; o.x0 = o.x; o.span = f * 560; addFx(o); break;
        case 'storm': o.life = 1.6; o.x0 = c.x + f * 120; o.span = f * 380; o.tick = 0; o.x = o.x0; E.tint = 1.2; E.tintCol = col; E.shake = Math.max(E.shake, 4); E.flash = 0.15; E.flashCol = '#e7d4ff'; addFx(o); break;
      }
      ring(c.x, c.y - 10, col, 36, 0.35);
      for (let i = 0; i < (E.low ? 4 : 9); i++) newPart('star', c.x + (rnd() - 0.5) * 50, c.y - 20 - rnd() * 50, (rnd() - 0.5) * 80, -40 - rnd() * 60, 0.6, 3 + rnd() * 2, col);
    }
    function updateSkills(dt) {
      castLock = Math.max(0, castLock - dt);
      const act = st.skills.active;
      for (let i = 0; i < 4; i++) {
        const sl = act[i]; if (!sl || !sl.id || (SK[sl.id] && SK[sl.id].passive)) continue;
        slotCd[i] -= dt;
        if (slotCd[i] <= 0 && castLock <= 0 && !chick.down && anyTargetNear(380)) {
          cast(sl); slotCd[i] = clamp(N(sl.cd_s) || SK[sl.id].cd, 1.0, 90);
        }
      }
      // 패시브 오라: 주기적으로 펄스 — 근처 몹을 밀어낸다
      const ps = st.skills.passive;
      if (ps) { auraT -= dt; if (auraT <= 0) { auraT = 3.2; const cfg = SK[ps] || SK.shield; ring(chick.x, chick.y - 24, cfg.col, 120, 0.55); aoe(chick.x, chick.y, 120, 60, D.unit * 0.35, cfg.col, { crit: 0.05, kn: 14, max: 8, bossFrac: 0.004 }); } }
      chick.aura = ps ? Math.min(1, chick.aura + dt * 3) : Math.max(0, chick.aura - dt * 3);
      // 이펙트
      for (let i = 0; i < FMAX; i++) {
        const f = fxs[i]; if (!f.on) continue;
        f.t += dt;
        if (f.t < 0) continue;
        const k = f.k, c = chick;
        switch (k) {
          case 'slash':
            f.x = c.x; f.y = c.y; f.face = c.face;
            if (!f.done && f.t >= f.hitAt) { f.done = true; aoe(c.x + c.face * 70, c.y, 100, 50, f.d, f.col, { max: 6, kn: 12 }); E.shake = Math.max(E.shake, 2); }
            break;
          case 'peck':
            while (f.n < 6 && f.t >= f.n * 0.09) {
              f.n++; const arr = nearestMobs(c.x, 1, 300, tmpA); const m = arr[0];
              if (m) { hurtMob(m, Math.max(1, Math.round(f.d * (0.9 + rnd() * 0.2))), false, f.col, c.x, 3); newPart('star', m.x, m.y - 40, (rnd() - 0.5) * 100, -40 - rnd() * 40, 0.3, 3, f.col); f['px' + f.n] = m.x; f['py' + f.n] = m.y; }
              else if (boss && boss.state === 'fight') bossHurt(0.006, false, f.col, c.x);
            }
            break;
          case 'spin':
            f.x = c.x; f.y = c.y;
            if (!f.done && f.t >= f.hitAt) { f.done = true; aoe(c.x, c.y, 125, 62, f.d, f.col, { max: 10 }); }
            if (!f.done2 && f.t >= f.hit2) { f.done2 = true; aoe(c.x, c.y, 125, 62, f.d, f.col, { max: 10 }); E.shake = Math.max(E.shake, 2); }
            break;
          case 'bomb':
            if (!f.done && f.t >= f.hitAt) { f.done = true; aoe(f.x, f.y, 82, 50, f.d, f.col, { max: 8, kn: 16 }); E.shake = Math.max(E.shake, 3); poof(f.x, f.y - 20, '#ffcf6a', 8, 120); ring(f.x, f.y - 10, f.col, 70, 0.4); }
            break;
          case 'thunder':
            if (!f.done && f.t >= f.hitAt) { f.done = true; aoe(f.x, f.y, 52, 44, f.d, f.col, { max: 4, kn: 6 }); poof(f.x, f.y - 10, '#fff7a8', 6, 110); }
            break;
          case 'fire': {
            const q = f.t / f.life; f.x += c.face * 0 + f.face * 470 * dt; f.px = f.x;
            const arr = rangeMobs(f.x, f.y + 20, 70, 48, tmpA);
            for (let j = 0; j < arr.length; j++) { const m = arr[j]; if (m.mark !== f.uid) { m.mark = f.uid; hurtMob(m, Math.max(1, Math.round(f.d * (0.9 + rnd() * 0.2))), rnd() < 0.2, f.col, f.x - f.face * 10, 9); } }
            if (boss && boss.state === 'fight' && !f.bh && Math.abs(boss.x - f.x) < 80) { f.bh = true; bossHurt(0.03, true, f.col, f.x); }
            if (rnd() < 0.8) newPart('dot', f.x - f.face * 20, f.y + (rnd() - 0.5) * 24, -f.face * 30, -30 - rnd() * 30, 0.4, 3 + rnd() * 3, rnd() < 0.5 ? '#ffb347' : '#ff5a2c');
            void q; break; }
          case 'egg': {
            const q = Math.min(1, f.t / 0.5);
            if (!f.landed && q >= 1) { f.landed = true; f.tl = f.t; aoe(f.tx, f.ty, 100, 60, f.d, f.col, { max: 10, kn: 14 }); E.shake = Math.max(E.shake, 4); for (let j = 0; j < (E.low ? 5 : 10); j++) coin(f.tx + (rnd() - 0.5) * 50, f.ty - 20); ring(f.tx, f.ty - 8, f.col, 100, 0.45); poof(f.tx, f.ty - 20, '#ffe680', 10, 130); }
            break; }
          case 'shrimp': {
            const q = clamp(f.t / 0.7, 0, 1); const nx = f.x0 + f.span * q; const px = f.sx == null ? f.x0 : f.sx; f.sx = nx;
            const lo = Math.min(px, nx) - 30, hi = Math.max(px, nx) + 30;
            for (let j = 0; j < mobs.length; j++) { const m = mobs[j]; if (m.dead >= 0 || m.spawnT > 0 || m.mark === f.uid) continue; if (m.x > lo && m.x < hi && Math.abs(m.y - f.y) < 70) { m.mark = f.uid; hurtMob(m, Math.max(1, Math.round(f.d * (0.9 + rnd() * 0.2))), rnd() < 0.3, f.col, nx - f.face * 20, 14); } }
            if (boss && boss.state === 'fight' && !f.bh && Math.abs(boss.x - nx) < 70) { f.bh = true; bossHurt(0.04, true, f.col, nx); }
            if (q < 1 && rnd() < 0.7) newPart('dot', nx - f.face * 20, f.y - 14 + (rnd() - 0.5) * 20, -f.face * 40, -10, 0.35, 3, f.col);
            break; }
          case 'storm': {
            const q = clamp(f.t / f.life, 0, 1); f.x = f.x0 + f.span * q; f.tick -= dt;
            if (f.tick <= 0 && f.t < f.life - 0.2) { f.tick = 0.2; aoe(f.x, f.y, 250, 90, f.d, f.col, { max: 14, kn: 16, crit: 0.35 }); E.shake = Math.max(E.shake, 3); }
            if (rnd() < 0.8) newPart('dot', f.x + (rnd() - 0.5) * 220, f.y - rnd() * 90, (rnd() - 0.5) * 200, -60 - rnd() * 60, 0.5, 2 + rnd() * 3, rnd() < 0.5 ? f.col : '#fff');
            break; }
        }
        if (f.t >= f.life) f.on = false;
      }
    }

    // ---------- 보스 ----------
    function bossStart(b) {
      if (boss || !b) return;
      const key = /^[a-z0-9_]{1,30}$/.test(String(b.img || '')) ? String(b.img) : '';
      const bx = clamp(chick.x + 400, 300, WW - 140);
      boss = { ty: 4, name: String(b.name || '보스'), img: key, x: bx + 260, y: 214, stop: bx, hp: N(b.hp) || 1000, hpMax: N(b.hp) || 1000, target: 0, res: null, state: 'in', t: 0, hit: 0, kb: 0 };
      if (key) ld('img/brjang/boss/' + key + '/front.png');
      for (const m of mobs) if (m.dead < 0) { m.dead = 0.35; m.dvx = 0; m.dvy = -60; m.drot = 0; if (m.spot) m.spot.n = Math.max(0, m.spot.n - 1); }
      for (const s of spots) s.n = 0;
      E.shake = 5; chick.target = boss; emit('boss', { phase: 'in' });
    }
    function bossResult(r) {
      const B = boss; if (!B || B.res || (r !== 'win' && r !== 'lose')) return;
      B.res = r; B.target = r === 'win' ? 0 : B.hpMax * 0.16;
    }
    function updateBoss(dt) {
      const B = boss; if (!B) return;
      B.t += dt; B.hit = Math.max(0, B.hit - dt); B.kb *= Math.exp(-dt * 12);
      if (st.boss && st.boss.res && !B.res) bossResult(st.boss.res);
      if (B.state === 'in') { B.x = Math.max(B.stop, B.x - 170 * dt); if (B.x <= B.stop) { B.state = 'fight'; B.t = 0; E.shake = 6; } }
      else if (B.state === 'fight') {
        // 판정이 오기 전엔 체력이 바닥(남은 20%)까지만 닳는다
        if (!B.res) { if (B.hp < B.hpMax * 0.2) B.hp = B.hpMax * 0.2; }
        else if (B.hp > B.target) {   // 판정이 오면 남은 체력을 시원하게 깎아 마무리한다(스킬 피해가 없어도 2초 안에)
          B.hp = Math.max(B.target, B.hp - B.hpMax * 0.4 * dt);
          if (B.hp <= B.target) { B.hp = B.target; if (B.res === 'win') { B.state = 'dying'; B.t = 0; E.shake = 9; E.flash = 0.5; for (let i = 0; i < 14; i++) coin(B.x + (rnd() - 0.5) * 60, B.y - 50); poof(B.x, B.y - 70, '#fff6c0', 18, 140); emit('boss', { phase: 'win' }); } else { B.state = 'smash'; B.t = 0; } }
        }
        if (B.t > 40 && !B.res) { B.state = 'leave'; B.t = 0; }
      }
      else if (B.state === 'dying') { if (B.t > 2.6) finishBoss(); }
      else if (B.state === 'smash') {
        if (B.t > 0.35 && !chick.down) { chick.down = 1; chick.pose = 'down'; E.shake = 8; poof(chick.x, chick.y - 30, '#ff5c7a', 12, 140); emit('boss', { phase: 'lose' }); }
        if (B.t > 2.6) { chick.down = 0; chick.pose = 'idle'; B.state = 'leave'; B.t = 0; }
      } else if (B.state === 'leave') { if (B.t > 0.8) finishBoss(); }
    }
    function finishBoss() { boss = null; chick.target = null; chick.down = 0; chick.pose = 'idle'; E.spawnT = 0.5; }

    // ---------- 동료 ----------
    function syncParty() {
      const ids = (st.party || []).slice(0, 3);
      const key = ids.map(p => p && p.id).join(',');
      if (key === E.pkey) return; E.pkey = key;
      allies.length = 0;
      ids.forEach((p, i) => { if (p) allies.push({ ty: 3, ini: Array.from(String(p.n || '?'))[0] || '?', gr: p.gr && GR_COL[p.gr] ? p.gr : 'normal', x: chick.x - 40 * (i + 1), y: chick.y, t: 0.5 + i * 0.4, hop: 0, i }); });
    }
    function updateAllies(dt) {
      for (const a of allies) {
        const c = chick, tx = c.x - c.face * (46 + a.i * 34), ty = clamp(c.y + (a.i - 1) * 16, Y0 - 4, Y1);
        a.x += (tx - a.x) * Math.min(1, dt * 4.5); a.y += (ty - a.y) * Math.min(1, dt * 4.5); a.hop = Math.max(0, a.hop - dt);
        a.t -= dt;
        if (a.t <= 0 && !c.down) {
          const tgt = (boss && boss.state === 'fight') ? boss : nearestMobs(a.x, 1, 320, tmpA)[0];
          if (tgt) { a.t = 1.1 + a.i * 0.25 + rnd() * 0.3; a.hop = 0.25; const p = newPart('proj', a.x, a.y - 24, 0, 0, 1.2, 4, GR_COL[a.gr]); if (p) { p.tgt = tgt; p.vx = 0; } } else a.t = 0.4;
        }
        a.face = c.face;
      }
    }

    // ---------- 갱신 ----------
    const rec = [];
    function controller(dt) {
      E.ctlT += dt; if (E.ctlT < 1) return; E.ctlT = 0;
      // 최근 최대 30초 동안의 처치율과 목표를 견주어 몹 체력 배율을 조금씩 고친다
      const win = Math.min(20, E.t); if (win < 5) return;
      let n = 0; for (let i = E.killLog.length - 1; i >= 0 && E.killLog[i] > E.t - win; i--) n++;
      const rate = n / win * 60, err = clamp((D.kpm - rate) / D.kpm, -1, 1);
      E.ctl = clamp(E.ctl * Math.exp(-0.12 * err), 0.12, 8);
    }
    function step(dt) {
      E.t += dt;
      E.shake = Math.max(0, E.shake - dt * 14); E.flash = Math.max(0, E.flash - dt * 2.6); E.tint = Math.max(0, E.tint - dt);
      E.comboT -= dt; if (E.comboT <= 0 && E.combo) { E.combo = 0; } E.comboPunch = Math.max(0, E.comboPunch - dt * 6);
      E.levelT = Math.max(0, E.levelT - dt);
      controller(dt);
      updateBoss(dt);
      updateChick(dt);
      updateMobs(dt);
      updateAllies(dt);
      updateSkills(dt);
      // 처치 연쇄: 쓰러진 몹이 폭발해 이웃에게 피해
      for (let i = E.chainQ.length - 1; i >= 0; i--) { const q = E.chainQ[i]; q.t -= dt; if (q.t <= 0) { E.chainQ.splice(i, 1); ring(q.x, q.y - 22, '#ffd9a0', 40, 0.3); aoe(q.x, q.y, 62, 38, D.unit * 0.6, '#ffd9a0', { crit: 0.1, max: 4, kn: 10 }); } }
      // 입자
      const lim = E.low ? PMAX * 0.45 : PMAX;
      for (let i = 0; i < lim; i++) {
        const p = parts[i]; if (!p.on) continue;
        p.t += dt;
        if (p.k === 'proj') {
          const T = p.tgt; if (!T || (T.ty === 1 && T.dead >= 0) || p.t > 1.4) { p.on = false; continue; }
          const dx = T.x - p.x, dy = (T.y - 30) - p.y, d = Math.hypot(dx, dy) || 1, sp = 420;
          p.x += dx / d * sp * dt; p.y += dy / d * sp * dt;
          if (d < 14) { p.on = false; if (T.ty === 4) bossHurt(0.003, false, '#bfe0ff', p.x); else hurtMob(T, Math.max(1, Math.round(D.unit * 0.35 * (0.8 + rnd() * 0.4))), false, '#bfe0ff', p.x - 8, 4); }
          continue;
        }
        if (p.t >= p.life) { p.on = false; continue; }
        if (p.k === 'coin') {
          if (p.t < 0.55) { p.vy += 560 * dt; p.x += p.vx * dt; p.y += p.vy * dt; if (p.y > chick.y + 8 && p.vy > 0 && p.b < 2) { p.y = chick.y + 8; p.vy *= -0.4; p.vx *= 0.6; p.b++; } }
          else {   // 병아리가 주워 간다
            const dx = chick.x - p.x, dy = (chick.y - 24) - p.y, d = Math.hypot(dx, dy) || 1, sp = 260 + (p.t - 0.55) * 900;
            p.x += dx / d * sp * dt; p.y += dy / d * sp * dt;
            if (d < 16) { p.on = false; E.coinT -= 0; if (E.t - (E.lastCoin || -1) > 0.1) { E.lastCoin = E.t; emit('coin'); } }
          }
        } else if (p.k === 'slashfx' || p.k === 'ring') { /* 그릴 때 시간으로 */ }
        else { p.x += p.vx * dt; p.y += p.vy * dt; if (p.k === 'dot' || p.k === 'star') p.vy += 160 * dt; }
      }
      for (let i = 0; i < TMAX; i++) { const t = texts[i]; if (!t.on) continue; t.t += dt; t.y += t.vy * dt; t.vy *= Math.exp(-dt * 2.6); if (t.t >= t.life) t.on = false; }
      // 카메라
      const VW = E.VW;
      const want = clamp(chick.x + chick.face * VW * 0.1 - VW * 0.5, 0, Math.max(0, WW - VW));
      E.cam += (want - E.cam) * Math.min(1, dt * 3.2);
      E.cam = clamp(E.cam, 0, Math.max(0, WW - VW));
    }

    // ---------- 그리기 ----------
    function spr(im, x, fy, h, o) {
      o = o || {};
      ctx.save(); ctx.translate(x, fy);
      if (o.rot) ctx.rotate(o.rot);
      if (o.a != null) ctx.globalAlpha = o.a;
      ctx.scale((o.sx || 1) * (o.flip ? -1 : 1), o.sy || 1);
      if (im.dw) ctx.drawImage(im, -im.dw / 2, -h / 2 - im.dw / 2, im.dw, im.dw);
      else { const w = h * im.width / im.height; ctx.drawImage(im, -w / 2, -h, w, h); }
      ctx.restore();
    }
    function shadow(x, y, rx, a) { ctx.fillStyle = 'rgba(0,0,0,' + (a || 0.28) + ')'; ctx.beginPath(); ctx.ellipse(x, y + 3, rx, rx * 0.22, 0, 0, 6.3); ctx.fill(); }
    function outText(s, x, y, size, col, al, sw) {
      ctx.font = '900 ' + size + 'px ' + FONT; ctx.textAlign = al || 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
      ctx.lineWidth = sw || Math.max(2.5, size / 4.5); ctx.strokeStyle = 'rgba(14,10,24,.9)'; ctx.strokeText(s, x, y); ctx.fillStyle = col; ctx.fillText(s, x, y);
    }

    function drawBg() {
      const cam = E.cam, VW = E.VW, im = art('bg' + (D.reg + 1)), h = HUE[D.reg];
      // 하늘 + 먼 건물 (시차 0.3)
      if (im) {
        const sh = 0.77, srcH = im.height * sh, s = HORIZON / srcH, w = im.width * s, off = cam * 0.3;
        const k0 = Math.floor(off / w);
        for (let k = k0; k * w - off < VW; k++) {
          const x0 = k * w - off;
          if (((k % 2) + 2) % 2) { ctx.save(); ctx.translate(x0 + w, 0); ctx.scale(-1, 1); ctx.drawImage(im, 0, 0, im.width, srcH, 0, 0, w + 1, HORIZON); ctx.restore(); }
          else ctx.drawImage(im, 0, 0, im.width, srcH, x0, 0, w + 1, HORIZON);
        }
        // 땅: 그림의 길바닥 띠를 세계 좌표(시차 1.0)로 깔아 발이 미끄러지지 않게 한다
        const gy0 = im.height * 0.80, gh = im.height * 0.13, gs = (LH - HORIZON) / gh, gw = im.width * gs, goff = cam;
        const g0 = Math.floor(goff / gw);
        for (let k = g0; k * gw - goff < VW; k++) {
          const x0 = k * gw - goff;
          if (((k % 2) + 2) % 2) { ctx.save(); ctx.translate(x0 + gw, 0); ctx.scale(-1, 1); ctx.drawImage(im, 0, gy0, im.width, gh, 0, HORIZON, gw + 1, LH - HORIZON); ctx.restore(); }
          else ctx.drawImage(im, 0, gy0, im.width, gh, x0, HORIZON, gw + 1, LH - HORIZON);
        }
      } else {
        const g = ctx.createLinearGradient(0, 0, 0, HORIZON); g.addColorStop(0, 'hsl(' + h + ',60%,68%)'); g.addColorStop(1, 'hsl(' + ((h + 20) % 360) + ',70%,86%)');
        ctx.fillStyle = g; ctx.fillRect(0, 0, VW, HORIZON);
        [[0.18, 70, 'hsl(' + h + ',30%,62%)', 90], [0.4, 56, 'hsl(' + h + ',28%,48%)', 70]].forEach(([f, sp, col, mh], li) => {
          const wx = cam * f, b0 = Math.floor(wx / sp) - 1; ctx.fillStyle = col;
          for (let b = b0; b < b0 + Math.ceil(VW / sp) + 3; b++) { const bw = sp * (0.6 + hash(b + li * 77) * 0.4), bh = 30 + hash(b + 99 + li * 31) * mh; ctx.fillRect(b * sp - wx, HORIZON - bh, bw, bh); }
        });
        const gg = ctx.createLinearGradient(0, HORIZON, 0, LH); gg.addColorStop(0, 'hsl(' + h + ',25%,44%)'); gg.addColorStop(1, 'hsl(' + h + ',25%,28%)'); ctx.fillStyle = gg; ctx.fillRect(0, HORIZON, VW, LH - HORIZON);
      }
      // 연석선 + 땅 음영/얼룩으로 깊이감
      ctx.fillStyle = 'rgba(30,24,40,.35)'; ctx.fillRect(0, HORIZON - 1, VW, 2.5);
      const gs = ctx.createLinearGradient(0, HORIZON, 0, LH); gs.addColorStop(0, 'rgba(20,14,34,.22)'); gs.addColorStop(0.35, 'rgba(20,14,34,0)'); gs.addColorStop(1, 'rgba(10,8,24,.38)');
      ctx.fillStyle = gs; ctx.fillRect(0, HORIZON, VW, LH - HORIZON);
      ctx.fillStyle = '#000';
      for (let i = 0; i < groundMarks.length; i++) { const m = groundMarks[i], sx = m.x - cam; if (sx < -30 || sx > VW + 30) continue; ctx.globalAlpha = m.a; ctx.beginPath(); ctx.ellipse(sx, m.y, m.w, m.w * 0.18, 0, 0, 6.3); ctx.fill(); }
      ctx.globalAlpha = 1;
    }
    function drawProp(p) {
      const im = propArt[p.nm]; if (!im) return; const sx = p.x - E.cam;
      ctx.save(); ctx.translate(sx, p.y); ctx.scale(p.sc * (p.flip ? -1 : 1), p.sc);
      ctx.drawImage(im, -im.dw / 2, -im.dh, im.dw, im.dh); ctx.restore();
    }
    function drawChick() {
      const c = chick, p = c.pose;
      const running = c.run > 60 && !c.cast;
      const bob = running ? Math.abs(Math.sin(E.t * 16)) * 4 : Math.sin(E.t * 3) * 1;
      const x = c.x - E.cam + c.face * c.lunge * 16 + c.kbx, y = c.y - bob;
      const sc = 0.92 + (c.y - Y0) / (Y1 - Y0) * 0.16;
      shadow(c.x - E.cam, c.y, 21 * sc, 0.3);
      // 패시브 오라
      if (c.aura > 0.01) {
        const col = (SK[st.skills.passive] || SK.shield).col, r = 52 + Math.sin(E.t * 4) * 2;
        ctx.save(); ctx.globalAlpha = 0.5 * c.aura; ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(x, y - 28, r, r * 1.1, 0, 0, 6.3); ctx.stroke();
        ctx.globalAlpha = 0.1 * c.aura; ctx.fillStyle = col; ctx.fill(); ctx.globalAlpha = 0.4 * c.aura; ctx.setLineDash([6, 10]); ctx.lineDashOffset = -E.t * 30; ctx.beginPath(); ctx.ellipse(x, y - 28, r + 6, (r + 6) * 1.1, 0, 0, 6.3); ctx.stroke(); ctx.restore();
        const si = fxImg(st.skills.passive || 'shield');
        if (si) { ctx.save(); ctx.globalAlpha = 0.35 * c.aura; ctx.globalCompositeOperation = 'lighter'; ctx.translate(x, y - 28); ctx.rotate(E.t * 0.8); ctx.drawImage(si, -r, -r, r * 2, r * 2); ctx.restore(); }
      }
      let im = art('chick_' + (p === 'down' ? 'hit' : p)); const has = !!im;
      if (!im) im = art('chick_idle'); if (!im) im = ld('img/brjang/parts/body_chick/front.png'); if (!im) im = emo('🐥', 74);
      const o = { flip: c.face < 0 }; let hk = 1;
      if (has) {
        hk = CHICK_HK[p] || 1;
        if (p === 'atk1' || p === 'atk2') { o.sx = 1 + 0.09 * c.lunge; o.sy = 1 - 0.07 * c.lunge; o.rot = (p === 'atk1' ? 1 : -1) * 0.07 * c.lunge * c.face; }
        else if (p === 'skill') { o.sy = 1 + Math.sin(E.t * 30) * 0.025; o.sx = 1.04; }
        else if (running) { o.rot = c.face * 0.1; o.sy = 1 - Math.abs(Math.sin(E.t * 16)) * 0.04; }
      } else { if (p === 'atk1' || p === 'atk2') { o.rot = 0.12 * c.face; o.sx = 1.08; } }
      let yy = y; if (p === 'down') { o.rot = -1.4 * c.face; o.a = 0.9; yy += 8; }
      if (c.hurt > 0 && ((E.t * 30) | 0) % 2 === 0) o.a = 0.5;
      if (c.cast > 0 && !E.low) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createRadialGradient(x, yy - 40, 4, x, yy - 40, 64); g.addColorStop(0, 'rgba(255,220,90,.7)'); g.addColorStop(1, 'rgba(255,140,40,0)'); ctx.fillStyle = g; ctx.fillRect(x - 70, yy - 110, 140, 140); ctx.restore(); }
      spr(im, x, yy + 4, 66 * hk * sc, o);
    }
    function drawAlly(a) {
      const x = a.x - E.cam, bob = Math.sin(E.t * 6 + a.i) * (chick.run > 60 ? 2.2 : 0.8), hop = a.hop > 0 ? -Math.sin((1 - a.hop / 0.25) * Math.PI) * 8 : 0, fy = a.y + bob + hop, col = GR_COL[a.gr] || '#98a2b8';
      shadow(a.x - E.cam, a.y, 12, 0.25);
      ctx.strokeStyle = col; ctx.globalAlpha = 0.55; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(x, a.y + 3, 14, 4.5, 0, 0, 6.3); ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, fy - 12, 9, 12, 0, 0, 6.3); ctx.fill();
      ctx.fillStyle = '#ffe3b8'; ctx.strokeStyle = 'rgba(10,12,20,.7)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, fy - 30, 8, 0, 6.3); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#222'; ctx.fillRect(x - 4 + a.face, fy - 31, 2, 3); ctx.fillRect(x + 2 + a.face, fy - 31, 2, 3);
      ctx.fillStyle = '#14171f'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, fy - 12, 6.5, 0, 6.3); ctx.fill(); ctx.stroke();
      outText(a.ini, x, fy - 11.5, 9, '#fff', 'center', 0.1);
    }
    function drawMob(m) {
      const k = D.reg + 1, dying = m.dead >= 0, hit = m.hit > 0;
      let im = (hit && art('m' + k + '_hit')) || art('m' + k + '_idle'); const fb = !im; if (!im) im = emo(MON_EMOJI[D.reg], 58);
      const near = Math.abs(m.x - chick.x) < 380;
      const bob = Math.abs(Math.sin(E.t * 8 + m.ph)) * (near ? 5 : 1.5);
      const dep = 0.9 + (m.y - Y0) / (Y1 - Y0) * 0.2, sc = m.sc * dep;
      let x = m.x - E.cam + m.kb - m.lunge * 14 * (m.face), y = m.y - bob + (dying ? (m.dy || 0) : 0);
      const o = { flip: m.face > 0 };   // 그림은 왼쪽을 보고 있다 → 병아리가 오른쪽에 있으면 뒤집는다
      let h = 58 * sc;
      if (m.spawnT > 0) { const q = 1 - m.spawnT / 0.35; o.a = q; h *= 0.4 + q * 0.6; }
      if (dying) { const q = m.dead / 0.55; o.a = Math.max(0, 1 - q * q); o.rot = m.drot * q; o.sx = 1 + q * 0.2; }
      else { if (hit && fb && ((E.t * 40) | 0) % 2 === 0) o.a = 0.4; if (hit) { o.sx = 1.08; o.sy = 0.92; } }
      if (!dying) {
        shadow(m.x - E.cam, m.y, 19 * sc, 0.28);
        if (m.el) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createRadialGradient(x, y - 36 * sc, 6, x, y - 36 * sc, 56 * sc); g.addColorStop(0, 'rgba(255,214,80,.55)'); g.addColorStop(1, 'rgba(255,160,40,0)'); ctx.fillStyle = g; ctx.fillRect(x - 60, y - 100, 120, 110); ctx.restore(); }
      }
      spr(im, x, y + 3, h, o);
      if (!dying && m.hp < m.max && m.spawnT <= 0) { const w = 30 * sc; ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillRect(x - w / 2 - 1, y - 64 * sc, w + 2, 5); ctx.fillStyle = m.el ? '#ffb23c' : '#ef5a6f'; ctx.fillRect(x - w / 2, y - 63 * sc, w * clamp(m.hp / m.max, 0, 1), 3); }
    }
    function drawBoss() {
      const B = boss; let im = B.img ? ld('img/brjang/boss/' + B.img + '/front.png') : null; if (!im) im = emo('🐲', 120);
      let a = 1, rot = 0, x = B.x - E.cam + B.kb, y = B.y + 6, sy = 1;
      if (B.state === 'dying') { const q = Math.min(1, B.t / 1.2); a = 1 - q; rot = q * 0.9; y += q * 18; }
      if (B.state === 'leave') a = 1 - Math.min(1, B.t / 0.8);
      if (B.state === 'smash' && B.t < 0.5) x -= Math.sin(Math.min(1, B.t / 0.35) * Math.PI) * 60 * (chick.x < B.x ? 1 : -1);
      if (B.state === 'in' || (B.state === 'fight' && B.t < 1)) sy = 1 + Math.sin(E.t * 4) * 0.015;
      shadow(B.x - E.cam, B.y, 56, 0.3);
      const o = { a, rot, sy, flip: false }; if (B.hit > 0 && ((E.t * 40) | 0) % 2 === 0) o.a = a * 0.5;
      spr(im, x, y, 132, o);
    }
    function drawFxList() {
      for (let i = 0; i < FMAX; i++) {
        const f = fxs[i]; if (!f.on || f.t < 0) continue;
        const q = clamp(f.t / f.life, 0, 1), fi = fxImg(f.k), cam = E.cam, c = ctx;
        c.save(); c.globalCompositeOperation = 'lighter';
        switch (f.k) {
          case 'slash': {
            const x = f.x - cam + f.face * 74, y = f.y - 38, s = 120 + q * 60;
            c.globalAlpha = 1 - q * q; c.translate(x, y); c.scale(f.face, 1); c.rotate(-0.5 + q * 1.0);
            if (fi) c.drawImage(fi, -s / 2, -s / 2, s, s); else { c.strokeStyle = f.col; c.lineWidth = 9 * (1 - q); c.lineCap = 'round'; c.beginPath(); c.arc(-30, 0, 78, -1.0, 1.0); c.stroke(); c.lineWidth = 3; c.strokeStyle = '#fff'; c.beginPath(); c.arc(-30, 0, 78, -0.9, 0.9); c.stroke(); }
            break; }
          case 'peck':
            for (let n = 1; n <= f.n; n++) { const px = f['px' + n]; if (px == null) continue; const age = f.t - (n - 1) * 0.09; if (age > 0.25) continue; const s = 50 + age * 80; c.globalAlpha = 1 - age / 0.25; if (fi) c.drawImage(fi, px - cam - s / 2, f['py' + n] - 40 - s / 2, s, s); else { c.strokeStyle = f.col; c.lineWidth = 2; for (let r = 0; r < 6; r++) { const a = r * 1.05 + n; c.beginPath(); c.moveTo(px - cam + Math.cos(a) * 6, f['py' + n] - 40 + Math.sin(a) * 6); c.lineTo(px - cam + Math.cos(a) * (14 + age * 40), f['py' + n] - 40 + Math.sin(a) * (14 + age * 40)); c.stroke(); } } }
            break;
          case 'spin': {
            const x = f.x - cam, y = f.y - 34, s = 230 * (0.7 + Math.min(1, q * 3) * 0.3);
            c.globalAlpha = q < 0.8 ? 0.95 : (1 - q) * 5; c.translate(x, y); c.scale(1, 0.55); c.rotate(f.t * 18);
            if (fi) c.drawImage(fi, -s / 2, -s / 2, s, s); else { c.strokeStyle = f.col; c.lineWidth = 8; c.lineCap = 'round'; for (let r = 0; r < 3; r++) { c.beginPath(); c.arc(0, 0, 100, r * 2.1, r * 2.1 + 1.2); c.stroke(); } }
            break; }
          case 'bomb': {
            const x = f.x - cam;
            if (f.t < f.hitAt) { const qq = f.t / f.hitAt, by = f.y - 200 * (1 - qq * qq); c.globalCompositeOperation = 'source-over'; c.fillStyle = '#222'; c.beginPath(); c.arc(x, by - 20, 9, 0, 6.3); c.fill(); c.fillStyle = '#ff9a3c'; c.fillRect(x - 1, by - 34, 2, 7); c.globalAlpha = 0.25; c.fillStyle = '#000'; c.beginPath(); c.ellipse(x, f.y + 2, 8 + qq * 20, 3 + qq * 6, 0, 0, 6.3); c.fill(); }
            else { const e = (f.t - f.hitAt) / (f.life - f.hitAt), s = 90 + e * 120; c.globalAlpha = 1 - e; if (fi) c.drawImage(fi, x - s / 2, f.y - 30 - s / 2, s, s); else { const g = c.createRadialGradient(x, f.y - 30, 4, x, f.y - 30, s / 2); g.addColorStop(0, '#fff'); g.addColorStop(0.3, f.col); g.addColorStop(1, 'rgba(255,80,20,0)'); c.fillStyle = g; c.fillRect(x - s / 2, f.y - 30 - s / 2, s, s); } }
            break; }
          case 'thunder': {
            const x = f.x - cam, top = 0, bot = f.y - 10; c.globalAlpha = q < 0.6 ? 1 : (1 - q) / 0.4;
            if (fi) { const w = 90, h = bot - top; c.drawImage(fi, x - w / 2, top, w, h); }
            else { c.strokeStyle = '#fff'; c.lineWidth = 4; c.shadowColor = f.col; c.shadowBlur = 12; c.lineJoin = 'round'; c.beginPath(); let yy = top, xx = x; c.moveTo(xx, yy); const seed = f.uid * 7; while (yy < bot) { yy += 22; xx = x + (hash(seed + (yy | 0)) - 0.5) * 34; c.lineTo(xx, Math.min(yy, bot)); } c.stroke(); c.shadowBlur = 0; }
            const g = c.createRadialGradient(x, f.y - 14, 2, x, f.y - 14, 56); g.addColorStop(0, 'rgba(255,250,170,.9)'); g.addColorStop(1, 'rgba(255,240,100,0)'); c.fillStyle = g; c.fillRect(x - 56, f.y - 70, 112, 112);
            break; }
          case 'fire': {
            const x = f.x - cam, y = f.y, s = 140; c.globalAlpha = q > 0.8 ? (1 - q) * 5 : 1; c.translate(x, y); c.scale(f.face, 1);
            if (fi) c.drawImage(fi, -s / 2, -s / 2, s, s); else { const g = c.createRadialGradient(0, 0, 4, 0, 0, 52); g.addColorStop(0, '#fff6c0'); g.addColorStop(0.4, '#ff9a3c'); g.addColorStop(1, 'rgba(255,60,20,0)'); c.fillStyle = g; c.fillRect(-60, -60, 120, 120); }
            break; }
          case 'egg': {
            const e = Math.min(1, f.t / 0.5);
            if (e < 1) { const x = f.x0 + (f.tx - f.x0) * e - cam, y = f.y0 + (f.ty - 30 - f.y0) * e - Math.sin(e * Math.PI) * 90; c.globalCompositeOperation = 'source-over'; c.translate(x, y); c.rotate(e * 12); c.fillStyle = '#ffd23c'; c.strokeStyle = '#a8741a'; c.lineWidth = 2; c.beginPath(); c.ellipse(0, 0, 8, 11, 0, 0, 6.3); c.fill(); c.stroke(); c.fillStyle = 'rgba(255,255,255,.6)'; c.beginPath(); c.ellipse(-2, -3, 2.4, 4, 0, 0, 6.3); c.fill(); }
            else { const a = (f.t - 0.5) / (f.life - 0.5), s = 120 + a * 100; c.globalAlpha = 1 - a; const x = f.tx - cam, y = f.ty - 26; if (fi) c.drawImage(fi, x - s / 2, y - s / 2, s, s); else { const g = c.createRadialGradient(x, y, 4, x, y, s / 2); g.addColorStop(0, '#fff'); g.addColorStop(0.35, '#ffd23c'); g.addColorStop(1, 'rgba(255,190,40,0)'); c.fillStyle = g; c.fillRect(x - s / 2, y - s / 2, s, s); } }
            break; }
          case 'shrimp': {
            const e = clamp(f.t / 0.7, 0, 1), x = f.x0 + f.span * e - cam, y = f.y - 12 - Math.sin(e * Math.PI) * 10; c.globalAlpha = e > 0.9 ? (1 - e) * 10 : 1; c.globalCompositeOperation = 'source-over';
            if (!fi && !art('m1_idle')) { c.font = '46px ' + FONT; c.textAlign = 'center'; c.fillText('🦐', x, y); }
            else { const im = fi || art('m1_idle'); c.translate(x, y); c.scale(f.face > 0 ? -1 : 1, 1); c.rotate(Math.sin(f.t * 30) * 0.12); const w = 76 * im.width / im.height; c.drawImage(im, -w / 2, -76, w, 76); }
            break; }
          case 'storm': {
            const x = f.x - cam, y = f.y - 54, s = 340 * (0.6 + Math.min(1, f.t * 3) * 0.4); c.globalAlpha = q > 0.85 ? (1 - q) / 0.15 : 0.95; c.translate(x, y); c.scale(1, 0.8); c.rotate(f.t * 9);
            if (fi) c.drawImage(fi, -s / 2, -s / 2, s, s); else { c.strokeStyle = f.col; c.lineWidth = 8; c.lineCap = 'round'; for (let r = 0; r < 4; r++) { c.globalAlpha = 0.8 - r * 0.15; c.beginPath(); c.arc(0, 0, 50 + r * 38, r * 1.6, r * 1.6 + 3.4); c.stroke(); } }
            break; }
        }
        c.restore();
      }
    }
    function drawParts() {
      const lim = E.low ? PMAX * 0.45 : PMAX, cam = E.cam, c = ctx;
      for (let i = 0; i < lim; i++) {
        const p = parts[i]; if (!p.on) continue; const q = p.t / p.life, x = p.x - cam;
        if (x < -40 || x > E.VW + 40) continue;
        switch (p.k) {
          case 'coin': {
            const sq = Math.abs(Math.cos(p.t * 10 + p.rot)); c.fillStyle = '#c98a14'; c.beginPath(); c.ellipse(x, p.y, 4.2 * sq + 0.8, 4.4, 0, 0, 6.3); c.fill(); c.fillStyle = '#ffd23c'; c.beginPath(); c.ellipse(x - 0.3, p.y - 0.3, 3.2 * sq + 0.5, 3.4, 0, 0, 6.3); c.fill(); break; }
          case 'dot': case 'dust': c.globalAlpha = Math.max(0, 1 - q); c.fillStyle = p.c; c.beginPath(); c.arc(x, p.y, p.r * (p.k === 'dust' ? 1 + q : 1), 0, 6.3); c.fill(); c.globalAlpha = 1; break;
          case 'star': c.globalAlpha = Math.max(0, 1 - q); c.fillStyle = p.c; c.save(); c.translate(x, p.y); c.rotate(p.rot + p.t * p.vr); const r = p.r; c.beginPath(); c.moveTo(0, -r * 1.8); c.lineTo(r * 0.5, -r * 0.5); c.lineTo(r * 1.8, 0); c.lineTo(r * 0.5, r * 0.5); c.lineTo(0, r * 1.8); c.lineTo(-r * 0.5, r * 0.5); c.lineTo(-r * 1.8, 0); c.lineTo(-r * 0.5, -r * 0.5); c.closePath(); c.fill(); c.restore(); c.globalAlpha = 1; break;
          case 'ring': c.globalAlpha = Math.max(0, 1 - q); c.strokeStyle = p.c; c.lineWidth = 3 * (1 - q) + 0.5; c.beginPath(); c.ellipse(x, p.y, p.r * (0.3 + q * 0.7), p.r * (0.3 + q * 0.7) * 0.5, 0, 0, 6.3); c.stroke(); c.globalAlpha = 1; break;
          case 'slashfx': { c.globalAlpha = Math.max(0, 1 - q); c.strokeStyle = p.c; c.lineWidth = 4 * (1 - q) + 1; c.lineCap = 'round'; const f = p.vr || 1; c.beginPath(); c.arc(x - f * 10, p.y, p.r, -0.9 * f - (f < 0 ? 2.2 : 0) + (f < 0 ? 0 : 0), 0.9 * f + (f < 0 ? 0 : 0), f < 0); c.stroke(); c.globalAlpha = 1; break; }
          case 'proj': c.fillStyle = p.c; c.beginPath(); c.arc(x, p.y, 4, 0, 6.3); c.fill(); c.globalAlpha = 0.4; c.beginPath(); c.arc(x - 6, p.y, 3, 0, 6.3); c.fill(); c.globalAlpha = 1; break;
        }
      }
    }
    function drawTexts() {
      const cam = E.cam;
      for (let i = 0; i < TMAX; i++) {
        const t = texts[i]; if (!t.on) continue; const q = t.t / t.life; const x = t.x - cam; if (x < -40 || x > E.VW + 40) continue;
        ctx.globalAlpha = q < 0.7 ? 1 : (1 - q) / 0.3;
        const pop = t.t < 0.12 ? 1 + (1 - t.t / 0.12) * 0.5 : 1;
        outText(t.s, x, t.y, t.size * pop, t.col, 'center');
      }
      ctx.globalAlpha = 1;
    }
    function drawHud() {
      const VW = E.VW;
      // 콤보
      if (E.combo >= 3) {
        const n = E.combo, col = n >= 100 ? '#ff5cf0' : n >= 60 ? '#ff5c7a' : n >= 30 ? '#ff9a3c' : n >= 10 ? '#ffd23c' : '#fff';
        const pu = 1 + E.comboPunch * 0.35, a = E.comboT < 0.5 ? E.comboT / 0.5 : 1;
        ctx.globalAlpha = a; ctx.save(); ctx.translate(VW - 14, 56); ctx.scale(pu, pu);
        outText(String(n), 0, 0, 34, col, 'right', 6); outText('COMBO', 0, 22, 12, '#fff', 'right', 3);
        // 남은 시간 막대
        ctx.fillStyle = 'rgba(0,0,0,.45)'; ctx.fillRect(-70, 33, 70, 4); ctx.fillStyle = col; ctx.fillRect(-70, 33, 70 * clamp(E.comboT / 2.6, 0, 1), 4);
        ctx.restore(); ctx.globalAlpha = 1;
      }
      if (E.levelT > 0) {
        const q = 1 - E.levelT / 2.0, x = chick.x - E.cam;
        ctx.save(); ctx.globalAlpha = Math.min(1, E.levelT * 1.5) * 0.7; ctx.globalCompositeOperation = 'lighter';
        const g = ctx.createLinearGradient(0, 0, 0, chick.y); g.addColorStop(0, 'rgba(255,230,120,0)'); g.addColorStop(1, 'rgba(255,230,120,.9)'); ctx.fillStyle = g; ctx.fillRect(x - 26, 0, 52, chick.y); ctx.restore();
        ctx.globalAlpha = Math.min(1, E.levelT * 2); outText('LEVEL UP!', x, chick.y - 120 - q * 30, 24, '#ffe14a', 'center', 5); ctx.globalAlpha = 1;
      }
      if (boss && boss.state !== 'dying' && boss.state !== 'leave') {
        const w = Math.min(260, VW - 40), x = VW / 2 - w / 2;
        ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillRect(x - 2, 10, w + 4, 14); ctx.fillStyle = '#ef3c5a'; ctx.fillRect(x, 12, w * clamp(boss.hp / boss.hpMax, 0, 1), 10);
        ctx.fillStyle = 'rgba(255,255,255,.25)'; ctx.fillRect(x, 12, w * clamp(boss.hp / boss.hpMax, 0, 1), 3);
        outText(boss.name, VW / 2, 36, 13, '#fff', 'center', 3);
      }
      if (opts.hudKpm) { const s = statsNow(); outText('분당 ' + s.kpm.toFixed(0) + '마리', 8, 14, 12, '#fff', 'left', 3); }
    }
    function draw() {
      const VW = E.VW, c = ctx;
      c.setTransform(E.scale, 0, 0, E.scale, 0, 0);
      c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
      const sh = E.shake > 0 && !E.rm ? E.shake : 0;
      c.save(); if (sh) c.translate((rnd() - 0.5) * sh, (rnd() - 0.5) * sh);
      drawBg();
      // 깊이 정렬: 소품·몬스터·병아리·동료·보스
      const dr = drawBuf; dr.length = 0; const cam = E.cam;
      for (let i = 0; i < props.length; i++) { const p = props[i]; if (p.x > cam - 60 && p.x < cam + VW + 60) dr.push(p); }
      for (let i = 0; i < mobs.length; i++) { const m = mobs[i]; if (m.x > cam - 80 && m.x < cam + VW + 80) dr.push(m); }
      dr.push(chick); for (let i = 0; i < allies.length; i++) dr.push(allies[i]); if (boss) dr.push(boss);
      dr.sort(byY);
      for (let i = 0; i < dr.length; i++) { const o = dr[i]; switch (o.ty) { case 0: drawProp(o); break; case 1: drawMob(o); break; case 2: drawChick(); break; case 3: drawAlly(o); break; case 4: drawBoss(); break; } }
      drawFxList(); drawParts(); drawTexts();
      // 앞쪽 덤불(시차 1.3) — 깊이감
      const fg = propArt.fg;
      if (fg) { c.globalAlpha = 0.95; const w = fg.dw * 1.3, off = cam * 1.3; for (let k = Math.floor(off / (w * 1.6)); k * w * 1.6 - off < VW; k++) { const x = k * w * 1.6 - off + hash(k + 5) * 40; c.drawImage(fg, x, LH - 20, w, fg.dh * 1.3 * 0.7); } c.globalAlpha = 1; }
      c.restore();
      // 화면 전체 효과
      if (E.tint > 0) { c.globalAlpha = Math.min(0.22, E.tint * 0.2); c.fillStyle = E.tintCol; c.fillRect(0, 0, VW, LH); c.globalAlpha = 1; }
      if (E.flash > 0) { c.globalAlpha = Math.min(0.5, E.flash); c.fillStyle = E.flashCol; c.fillRect(0, 0, VW, LH); c.globalAlpha = 1; }
      if (vig) { c.fillStyle = vig; c.fillRect(0, 0, VW, LH); }
      drawHud();
    }
    const drawBuf = [];
    const byY = (a, b) => a.y - b.y;
    let vig = null;
    function buildVig() { const VW = E.VW; const g = ctx.createRadialGradient(VW / 2, LH * 0.55, LH * 0.45, VW / 2, LH * 0.55, Math.max(VW, LH) * 0.75); g.addColorStop(0, 'rgba(8,6,20,0)'); g.addColorStop(1, 'rgba(8,6,20,.38)'); vig = g; }

    // ---------- 크기 ----------
    function measure() {
      let cw = canvas.clientWidth || (canvas.parentNode && canvas.parentNode.clientWidth) || 360;
      let ch = canvas.clientHeight;
      if (!canvas.style.height || canvas.style.height === 'auto') { ch = Math.round(cw * (opts.aspect || 0.62)); canvas.style.height = ch + 'px'; }
      ch = ch || Math.round(cw * 0.62);
      const dpr = Math.min(E.low ? 1.25 : 2, (typeof window !== 'undefined' && window.devicePixelRatio) || 1);
      if (cw === E.cssW && ch === E.cssH && dpr === E.dpr) return;
      E.cssW = cw; E.cssH = ch; E.dpr = dpr;
      canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
      E.scale = canvas.height / LH; E.VW = canvas.width / E.scale;
      buildVig();
      E.cam = clamp(E.cam, 0, Math.max(0, WW - E.VW));
    }

    // ---------- 구동 ----------
    function frame(dt) {
      let left = dt * E.timeScale;
      while (left > 1e-6) { const s = Math.min(left, 1 / 30); step(s); left -= s; }
    }
    function loop(ts) {
      E.raf = 0; if (!E.running || E.destroyed) return;
      const dt = Math.min(0.05, Math.max(0.001, (ts - E.last) / 1000 || 0.016)); E.last = ts;
      E.dtAvg = E.dtAvg * 0.95 + dt * 0.05;
      if (!E.low && E.dtAvg > 0.034) { if (++E.lowN > 90) { E.low = true; E.cssW = 0; } } else if (E.lowN > 0) E.lowN--;
      if ((E.frames & 31) === 0) measure();
      frame(dt); draw(); E.frames++;
      E.raf = requestAnimationFrame(loop);
    }
    function start() {
      if (E.running || E.destroyed || manual) return;
      if (hasDoc && document.hidden) return;
      E.running = true; E.last = performance.now(); E.raf = requestAnimationFrame(loop);
    }
    function stop() { E.running = false; if (E.raf) cancelAnimationFrame(E.raf); E.raf = 0; }
    function onVis() { if (document.hidden) stop(); else if (E.vis) start(); }
    let io = null, onResize = null;
    if (hasDoc) {
      document.addEventListener('visibilitychange', onVis);
      if (typeof window !== 'undefined') { onResize = () => { E.cssW = 0; measure(); }; window.addEventListener('resize', onResize); }
      try { io = new IntersectionObserver(es => { E.vis = es[es.length - 1].isIntersecting; if (E.vis) start(); else stop(); }); io.observe(canvas); } catch (e) { }
    }

    function setState(s) {
      s = s || {};
      const prevStage = st.stage, prevReg = D.reg;
      st.stage = N(s.stage) || 1; st.region = String(s.region || ''); st.power = Math.max(5, N(s.power)); st.rate = N(s.rate); st.kpm = N(s.kpm) || 100;
      st.party = Array.isArray(s.party) ? s.party : [];
      const sk = s.skills || {}, act = Array.isArray(sk.active) ? sk.active : [];
      for (let i = 0; i < 4; i++) {
        const n = act[i] && SK[act[i].id] ? act[i] : null, o = st.skills.active[i];
        if (n && (!o || o.id !== n.id)) slotCd[i] = 0.4 + i * 0.7;
        st.skills.active[i] = n;
      }
      st.skills.passive = sk.passive && SK[sk.passive] ? sk.passive : null;
      derive(); syncParty();
      if (E.inited && st.stage > prevStage) { E.levelT = 2.0; ring(chick.x, chick.y - 10, '#ffe14a', 90, 0.7); poof(chick.x, chick.y - 40, '#ffe14a', 14, 130); emit('levelup', {}); }
      E.inited = true;
      if (s.boss && !boss && !st.boss) bossStart(s.boss);   // 새로 나타날 때만(끝난 뒤 같은 값이 남아 있어도 다시 시작하지 않는다)
      st.boss = s.boss || null;
      if (!s.boss && boss && boss.state === 'in') { boss.state = 'leave'; boss.t = 0; }
      void prevReg;
    }
    function statsNow() {
      const win = Math.min(60, Math.max(10, E.t)); let n = 0;
      for (let i = E.killLog.length - 1; i >= 0 && E.killLog[i] > E.t - win; i--) n++;
      return { kills: E.kills, t: E.t, kpm: n / win * 60, kpmTotal: E.t > 0 ? E.kills / E.t * 60 : 0, ctl: E.ctl, alive: aliveMobs(), combo: E.combo, comboMax: E.comboMax, cam: E.cam, chickX: chick.x, low: E.low, boss: boss ? boss.state : null, spot: spots.indexOf(chick.spot), VW: E.VW };
    }
    // 첫 상태 없이도 돌아가게
    derive(); buildProps(); measure(); buildVig();
    // 시작 위치: 첫 사냥터 근처에 몹을 미리 깔아 둔다(첫 화면이 비어 보이지 않게)
    for (let i = 0; i < 8; i++) spawnMob(spots[1]);
    for (const m of mobs) m.spawnT = 0;

    const inst = {
      setState, start, stop, resize() { E.cssW = 0; measure(); }, destroy() {
        E.destroyed = true; stop();
        if (hasDoc) { document.removeEventListener('visibilitychange', onVis); if (onResize) window.removeEventListener('resize', onResize); }
        if (io) try { io.disconnect(); } catch (e) { }
        for (const k in listeners) delete listeners[k];
      },
      on(name, cb) { (listeners[name] = listeners[name] || []).push(cb); return () => { const a = listeners[name]; if (a) { const i = a.indexOf(cb); if (i >= 0) a.splice(i, 1); } }; },
      tick(dt) { frame(dt); draw(); E.frames++; },
      sim(sec, dt) { dt = dt || 1 / 30; for (let t = 0; t < sec - 1e-9; t += dt) step(dt); },
      stats: statsNow, cast(id) { if (SK[id]) cast({ id, power_pct: 0 }); }, bossResult,
      setTimeScale(v) { E.timeScale = v; }
    };
    return inst;
  }

  const BrjField = { create, version: 1 };
  root.BrjField = BrjField;
  if (typeof module !== 'undefined' && module.exports) module.exports = BrjField;
})(typeof window !== 'undefined' ? window : globalThis);
