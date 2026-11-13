/* brjhunt_arena.js — 브장신 키우기 사냥터 「메이플식 발판 아레나」 엔진 (3차 개편)
 *
 * 전역 BrjArena = { create(canvas, opts) → inst }
 *
 *   발판 지형(바닥 + 3층 발판 + 벽 블록) 위에서 병아리를 직접 움직이거나(수동) AI 가 사냥한다(AUTO).
 *   전투 계산은 서버가 준 스탯(combat)·몬스터(mon)·스킬 수치(skills)로 이 엔진이 직접 한다.
 *   서버가 정하는 것: 골드·보상·보스 승패. 엔진이 하는 것: 화면의 처치 마리 수를 세어 report 로 알린다.
 *
 * const a = BrjArena.create(canvas, {base:'', seed:1, manual:false, hud:true, keys:true});
 * a.setState({stage, region, combat:{atk,hp,def,crit,critdmg,acc,mp,mpregen,power}, rec_power,
 *             mon:{name,hp,atk,def,eva,gold}, kpm_model:100,
 *             skills:{active:[{id,key,mp,cd,cast,shape,range,hits,mult,lv,fx_color}|null x4], passive:'shield'|null},
 *             party:[{id,n,gr}], boss:null|{img,name,hp,res?}})
 * a.start() a.stop() a.resize() a.destroy()
 * 이벤트(a.on(name, cb) → off): kill{n,gold} hit{crit,dmg,skill} skill{id} coin boss{phase} levelup die revive report{kills,secs}
 *   효과음용: swing{n} jump land{hard} step hurt miss cast{id,stage} mobdie
 * a.setAuto(b) a.getAuto() a.input.press(name)/release(name)   이름: left right up down jump attack s1 s2 s3 s4 auto pause
 * a.stats() a.tick(dt) a.sim(sec,dt) a.startChallenge({img,name,hp,res}) a.bossResult('win'|'lose')
 * a.setHidden(b)  화면에 안 보임(report 의 secs 에서 뺀다)    a.setPaused(b)  일시정지
 * a.debug  시험용 속살(map, mobs, player ...)
 *
 * [4차 개편] 스킬 구분감: 시전마다 이름 콜아웃(callout 이벤트) · 스킬 고유 색/이펙트/자세 · 화면 연출(어두워짐·줌·흔들림) · 피격 모습(불=화상 · 번개=감전 · 베기=칼자국 …).
 *   이벤트: skill{id,col,size,call,dur,lv} callout{id,text,col,size} skillend{id}
 * [4차 개편] 인스턴스 전투 — 열쇠 던전·클랜 보스·보상 상자를 진짜 전투 장면으로(승패·보상·피해는 서버 값, 엔진은 연출 시간표만 짠다):
 *   a.startInstance({kind:'dungeon'|'clanboss'|'clanclaim', level, img, name, waves, predict, result:null|{...}})  → true/false
 *     result(던전) {result:'win'|'lose'|'sweep'|'nokey', level, got:{stone,gold,ticket}, power, hp}
 *     result(클랜 보스) {result:'ok', dmg, hp, before, after, dead, notes:[줄…]}   (before/after = 클랜 누적 피해, dmg = 이번 내 공격 피해 — 타격들의 합이 dmg 와 정확히 같다)
 *     result(보상) {result:'ok', got:{feast}}
 *   a.instanceResult(result)  결과가 늦게 올 때 나중에 넘긴다 · a.skipInstance() 건너뛰기 · a.abortInstance() 응답 실패 시 연출만 접기
 *   이벤트: instance{phase:'in'|'wave'|'wavedone'|'boss'|'ff'|'locked'|'chest'|'total'|'lose'|'end', ...} reward{kind,n,fx,fy} ihit{dmg,total,crit,left}
 *   (인스턴스 중에는 사냥 보고의 secs·kills 에 안 들어간다 — 도전 던전·보스와 같은 규칙)
 *
 * 몹 체력은 「내 전투력 ÷ 권장 전투력」 비율에서 나온다(상수 CAL_TTK 하나). 처치 속도는 그 결과이며 되먹임으로 맞추지 않는다.
 */
(function (root) {
  'use strict';

  // ---------- 상수 ----------
  const LH = 340;                 // 논리 높이. 가로는 캔버스 비율대로.
  const GY = 304;                 // 바닥 윗면 y
  const GRAV = 1100, JUMP_V = 470, JUMP2_V = 400, RUN_V = 152, ACC_G = 1500, ACC_A = 760, FRIC_G = 1700;
  const FIX = 1 / 60;             // 고정 갱신 간격
  const PW = 7, PH = 30;          // 병아리 판정 상자: 반폭 · 키 (그림보다 작게 — 접촉 판정이 후하지 않도록)
  const CHICK_H = 50;             // 병아리 그림 높이
  const REACH = 66;               // 기본 공격 사거리
  const MAX_MOBS = 36;
  const MOB_BAND = [140, 420];    // 새 몹이 나오는 병아리와의 가로 거리(다른 발판)
  const PACK_P = 0.8;            // 가까운 곳 새 몹이 무리로 나올 확률
  const WAVE_SIZE = 28, WAVE_LOW = 9, WAVE_MAXGAP = 9, WAVE_DELAY = [0.7, 1.1];   // 🌊 [2026-11-13 사장님 「1마리 잡으면 앞에 또 생기는 게 반복돼 기동성이 무의미 · 딜레이를 두고 한 번에 많이」] 몹이 거의 사라지면 잠깐 쉬었다가 맵 곳곳에 한꺼번에 나온다
  const SPAWN_NEAR = 0.7;         // 새 몹 중 병아리가 서 있는 발판에서 나오는 비율
  const BASIC_HPS = 5.6;          // 기본 공격 초당 타수 (콤보 0.15·0.15·0.22초의 평균)
  const AGGRO = 270, CHASE_K = 2.3;   // 몹이 병아리를 알아채는 거리 · 쫓아올 때 걸음 배율
  const SPAWN_GAP = 0.15;         // 몹 보충 간격(초)
  // [보정 표 — 고정값] 엔진의 AUTO 처치율은 몹 체력 비율에 완만하게만 반응한다(걸어 다니는 시간이 있어 분당 약 128마리에서 막힘). 헤드리스로 잰 응답
  // (비율 → 분당 처치) 의 역함수로 「서버 모델이 말하는 분당 처치」가 나오는 비율을 고른다. 런타임 되먹임이 아니라 상수 표다.
  const CAL_RESP = [[0, 0], [0.1, 34], [0.2, 51], [0.3, 61], [0.5, 81], [0.85, 94], [1, 105], [1.3, 119], [2, 130]];   // 2026-11-13 웨이브 리젠 + 넓어진 스킬 범위 뒤 헤드리스로 다시 잰 응답(비율 → 분당 처치)   // 2026-11-13 웨이브 리젠 뒤 헤드리스로 다시 잰 응답(비율 → 분당 처치). 웨이브 방식은 이동·대기 때문에 위쪽 한계가 낮다   // 2026-11-13 웨이브 리젠 뒤 다시 잰 응답(비율 → 분당 처치) — 웨이브 방식은 이동·대기 때문에 위쪽 한계가 낮다
  const CAL_KPM_MAX = 126;        // 엔진이 낼 수 있는 분당 처치의 위쪽 한계(이 위는 서버 모델이 더 후해도 못 따라간다 — 보고에서 서버가 자르는 쪽이 아니라 모자라는 쪽)
  function calRatio(r) {
    const T = Math.min(CAL_KPM_MAX, 100 * r);
    for (let i = 1; i < CAL_RESP.length; i++) {
      const a = CAL_RESP[i - 1], b = CAL_RESP[i];
      if (T <= b[1]) return a[0] + (b[0] - a[0]) * (T - a[1]) / (b[1] - a[1]);
    }
    return CAL_RESP[CAL_RESP.length - 1][0];
  }
  const CAL_TTK = 0.27;           // [보정 상수 하나] 전투력 = 권장 전투력일 때 몹 한 마리를 잡는 데 드는 이론상 시간(초). 시험으로 맞춤.
  const DPS_PER_HP = 0.55;        // rec_power·power 가 없을 때만 쓰는 대체: 이론 초당 피해 ÷ 몹 체력 = 1 이 되는 기준
  const K_DEF_PER_STAGE = 8, K_DEF_BASE = 12;   // 방어 감소 = def/(def + K), K = 12 + 8·스테이지
  const CONTACT_K = 0.55;         // 접촉 피해 계수
  const INVULN = 1.1, REVIVE_T = 4.0, MANUAL_HOLD = 3.0;
  const REPORT_EVERY = 30;
  const BF_INTRO = 2.4, BF_FIGHT = 10;
  const FONT = '"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif';
  const REG_KEY = ['합정', 'bhc', '홍대', '상수', '망원', '한강'];
  const HUE = [205, 28, 345, 262, 140, 190];
  const GR_COL = { normal: '#98a2b8', rare: '#4aa3ff', epic: '#b678ff', unique: '#ffa23a', legend: '#ff5c7a' };
  const SKILL_IDS = ['slash', 'peck', 'spin', 'bomb', 'thunder', 'fire', 'egg', 'shield', 'shrimp', 'storm', 'ice', 'gale', 'meteor', 'phoenix', 'rage', 'blink', 'pull', 'ward'];
  const SKD = {   // 서버가 안 준 칸을 채우는 기본값
    slash: { shape: 'arc', mp: 8, cd: 2.2, cast: 0.28, range: 270, hits: 1, mult: 160, col: '#ffffff' },
    peck: { shape: 'proj', mp: 6, cd: 2.0, cast: 0.22, range: 420, hits: 3, mult: 70, col: '#ffe27a' },
    spin: { shape: 'arc', mp: 14, cd: 3.6, cast: 0.45, range: 300, hits: 3, mult: 80, col: '#8fe3ff', both: true },
    bomb: { shape: 'aoe', mp: 16, cd: 5, cast: 0.3, range: 430, hits: 1, mult: 230, col: '#ff9a3c' },
    thunder: { shape: 'aoe', mp: 20, cd: 5, cast: 0.32, range: 480, hits: 2, mult: 130, col: '#fff27a' },
    fire: { shape: 'proj', mp: 18, cd: 4.6, cast: 0.34, range: 620, hits: 1, mult: 220, col: '#ff6a2c', pierce: true },
    egg: { shape: 'aoe', mp: 22, cd: 6, cast: 0.36, range: 420, hits: 1, mult: 280, col: '#ffd23c' },
    shield: { shape: 'self', mp: 0, cd: 0, cast: 0, range: 0, hits: 1, mult: 60, col: '#6fd6ff', passive: true },
    shrimp: { shape: 'dash', mp: 28, cd: 8, cast: 0.3, range: 420, hits: 2, mult: 200, col: '#ff8aa0' },
    storm: { shape: 'aoe', mp: 40, cd: 14, cast: 0.6, range: 620, hits: 5, mult: 120, col: '#c78bff', both: true },
    ice: { shape: 'aoe', mp: 24, cd: 6, cast: 0.45, range: 470, hits: 2, mult: 120, col: '#7fd8ff', both: true },
    gale: { shape: 'proj', mp: 28, cd: 7, cast: 0.4, range: 1000, hits: 4, mult: 75, col: '#8affc1', pierce: true },
    meteor: { shape: 'aoe', mp: 46, cd: 14, cast: 0.9, range: 900, hits: 6, mult: 170, col: '#ff9248', both: true },
    phoenix: { shape: 'aoe', mp: 70, cd: 24, cast: 1.2, range: 1500, hits: 10, mult: 150, col: '#ff5a3c', both: true },
    rage: { shape: 'buff', mp: 30, cd: 20, cast: 0.35, range: 0, hits: 0, mult: 35, col: '#ff6b6b' },
    blink: { shape: 'blink', mp: 14, cd: 6, cast: 0.15, range: 420, hits: 0, mult: 0, col: '#d9a8ff' },
    pull: { shape: 'pull', mp: 22, cd: 9, cast: 0.45, range: 600, hits: 2, mult: 60, col: '#7fa8ff' },
    ward: { shape: 'self', mp: 26, cd: 15, cast: 0.4, range: 0, hits: 0, mult: 100, col: '#ffe9a8' }
  };

  // 스킬마다 화면만 보고 알 수 있게 — 이름 콜아웃 · 색 · 크기(1 가볍게 ~ 4 화면 전체) · 시전 자세 · 맞은 몬스터 모습 · 화면 연출. 고치는 곳은 여기 한 곳.
  const SKV = {
    slash:   { call: '베기!',        col: '#d8f0ff', dark: '#0b3a66', size: 1, pose: 'lunge',  hit: 'cut',   hsh: '',          zoom: 0.025, shake: 2.4, stop: 0.035, ic: '🗡' },
    peck:    { call: '부리 연타!',   col: '#ffa24a', dark: '#6a2a00', size: 1, pose: 'peck',   hit: 'spark', hsh: 'sk_peck',   zoom: 0.02,  shake: 1.8, stop: 0.02,  ic: '🐤' },
    spin:    { call: '회전베기!',    col: '#6fe8ff', dark: '#06465c', size: 2, pose: 'spin',   hit: 'cut',   hsh: '',          zoom: 0.05,  shake: 3.5, stop: 0.04,  ic: '🌀' },
    bomb:    { call: '폭격!',        col: '#ff6a3a', dark: '#5a1200', size: 3, pose: 'raise',  hit: 'burn',  hsh: '',          zoom: 0.09,  shake: 11,  stop: 0.09,  ic: '💣', dim: 0.6, dimCol: '12,4,2' },
    thunder: { call: '번개!',        col: '#fff25a', dark: '#4a3f00', size: 3, pose: 'sky',    hit: 'shock', hsh: 'sk_thunder', zoom: 0.07, shake: 8,   stop: 0.07,  ic: '⚡', dim: 0.64, dimCol: '4,6,28' },
    fire:    { call: '불닭 파이어!', col: '#ff3d2e', dark: '#5a0a00', size: 2, pose: 'breath', hit: 'burn',  hsh: '',          zoom: 0.05,  shake: 4,   stop: 0.04,  ic: '🔥' },
    egg:     { call: '황금알!',      col: '#ffc01f', dark: '#6b3a00', size: 2, pose: 'throw',  hit: 'gold',  hsh: '',          zoom: 0.05,  shake: 5,   stop: 0.05,  ic: '🥚' },
    shield:  { call: '방패!',        col: '#5fa8ff', dark: '#0b2d6b', size: 2, pose: 'guard',  hit: 'push',  hsh: '',          zoom: 0.03,  shake: 3,   stop: 0.03,  ic: '🛡' },
    shrimp:  { call: '새우 돌격!',   col: '#ff8fb0', dark: '#6b1233', size: 2, pose: 'charge', hit: 'push',  hsh: 'sk_shrimp', zoom: 0.05,  shake: 4.5, stop: 0.04,  ic: '🦐' },
    ice:     { call: '서리 폭풍!',   col: '#9fe8ff', dark: '#0a3a52', size: 2, pose: 'raise',  hit: 'push',  hsh: '',          zoom: 0.05,  shake: 3,   stop: 0.04,  ic: '🧊' },
    gale:    { call: '칼날 돌풍!',   col: '#9affc8', dark: '#0a4a2c', size: 2, pose: 'breath', hit: 'cut',   hsh: '',          zoom: 0.04,  shake: 3.5, stop: 0.03,  ic: '🍃' },
    meteor:  { call: '닭강정 운석!', col: '#ffa254', dark: '#5a2200', size: 3, pose: 'sky',    hit: 'burn',  hsh: '',          zoom: 0.09,  shake: 12,  stop: 0.09,  ic: '☄', dim: 0.6, dimCol: '14,4,2' },
    phoenix: { call: '불사조 강림!', col: '#ff6a44', dark: '#5a0e00', size: 4, pose: 'storm',  hit: 'burn',  hsh: '',          zoom: 0.12,  shake: 14,  stop: 0.11,  ic: '🔥', dim: 0.66, dimCol: '18,2,0', lines: true },
    rage:    { call: '분노의 울음!', col: '#ff7b7b', dark: '#5a0a0a', size: 2, pose: 'raise',  hit: 'push',  hsh: '',          zoom: 0.04,  shake: 4,   stop: 0.03,  ic: '💢' },
    blink:   { call: '순간이동!',    col: '#e0b8ff', dark: '#3a1060', size: 1, pose: 'lunge',  hit: 'push',  hsh: '',          zoom: 0.01,  shake: 0,   stop: 0,     ic: '✨' },
    pull:    { call: '끌어당기기!',  col: '#8fb4ff', dark: '#0f2a6b', size: 2, pose: 'raise',  hit: 'push',  hsh: '',          zoom: 0.05,  shake: 4,   stop: 0.04,  ic: '🧲' },
    ward:    { call: '깃털 방벽!',   col: '#fff0b8', dark: '#6b5a00', size: 2, pose: 'guard',  hit: 'push',  hsh: '',          zoom: 0.03,  shake: 2,   stop: 0.03,  ic: '🪶' },
    storm:   { call: '논란 폭풍!',   col: '#c07bff', dark: '#2c0a5c', size: 4, pose: 'storm',  hit: 'shock', hsh: '',          zoom: 0.11,  shake: 12,  stop: 0.1,   ic: '🌪', dim: 0.6, dimCol: '16,4,34', lines: true }
  };
  const SZ_R = [0, 22, 32, 46, 64];   // 시전 전조 마법진 반지름(크기별)

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

  // =====================================================================
  //  지형 — 지역마다 손으로 짠 틀 + 시드 변형. 결정론적이다(같은 지역·시드 = 같은 맵).
  //  모든 발판은 바닥에서 점프로 올라갈 수 있고(층간 높이 ≤ 72 < 점프 높이 100) 다시 내려올 수 있다.
  // =====================================================================
  const RECIPES = [
    { W: 2400, step: 64, tiers: [{ seg: [170, 300], gap: [44, 76], cover: 0.88 }, { seg: [150, 260], gap: [50, 80], cover: 0.75 }, { seg: [120, 200], gap: [60, 90], cover: 0.55 }], blocks: 2 },   // 합정 골목
    { W: 2600, step: 66, tiers: [{ seg: [240, 420], gap: [44, 70], cover: 0.9 }, { seg: [200, 340], gap: [50, 76], cover: 0.8 }], blocks: 3 },                                              // bhc
    { W: 2800, step: 62, tiers: [{ seg: [90, 150], gap: [46, 86], cover: 0.92 }, { seg: [90, 150], gap: [50, 90], cover: 0.82 }, { seg: [90, 140], gap: [60, 100], cover: 0.7 }], blocks: 4 },     // 홍대(작은 발판 많음)
    { W: 3000, step: 66, stairs: true, blocks: 3 },                                                                                                                                       // 상수(계단)
    { W: 3200, step: 68, tiers: [{ seg: [300, 520], gap: [60, 78], cover: 0.92 }, { seg: [260, 420], gap: [66, 78], cover: 0.75 }], blocks: 2 },                                           // 망원(긴 발판·넓은 틈)
    { W: 2800, step: 64, plateau: true, tiers: [{ seg: [160, 280], gap: [44, 70], cover: 0.75 }], blocks: 4 }                                                                            // 한강(가운데 고원)
  ];
  const MAP_NAMES = ['합정 골목', 'bhc 거리', '홍대 먹자골목', '상수 계단길', '망원 시장', '한강 다리'];

  function hgap(a, b) { return Math.max(a.x0 - b.x1, b.x0 - a.x1, 0); }

  function genMap(reg, seed) {
    reg = ((reg | 0) % 6 + 6) % 6;
    const R = RECIPES[reg];
    for (let attempt = 0; attempt < 8; attempt++) {
      const rr = mulberry(((seed | 0) + attempt * 977) * 7919 + reg * 104729 + 17);
      const rng = (a, b) => a + rr() * (b - a);
      const W = R.W;
      const segs = [];   // {x0,x1,tier}
      if (R.stairs) {
        const pat = [1, 2, 3, 2, 1, 2, 3, 2];
        let x = 150 + rng(0, 40), i = 0;
        while (x < W - 260) { const w = rng(130, 200); segs.push({ x0: x, x1: Math.min(W - 40, x + w), tier: pat[i++ % pat.length] }); x += w + rng(30, 44); }
        // 계단 사이사이 낮은 층에 보조 발판
        let y2 = 330 + rng(0, 60); while (y2 < W - 300) { const w = rng(120, 190); segs.push({ x0: y2, x1: y2 + w, tier: 1 }); y2 += w + rng(160, 260); }
      } else if (R.plateau) {
        const c = W / 2, pw = rng(300, 380);
        segs.push({ x0: c - pw / 2, x1: c + pw / 2, tier: 3 });
        segs.push({ x0: c - pw / 2 - 40 - 190, x1: c - pw / 2 - 40, tier: 2 }); segs.push({ x0: c + pw / 2 + 40, x1: c + pw / 2 + 40 + 190, tier: 2 });
        segs.push({ x0: c - pw / 2 - 90 - 380, x1: c - pw / 2 - 90 - 200, tier: 1 }); segs.push({ x0: c + pw / 2 + 90 + 200, x1: c + pw / 2 + 90 + 380, tier: 1 });
        const T = R.tiers[0]; let x = rng(80, 200);
        while (x < W - 140) { const w = rng(T.seg[0], T.seg[1]); if (rr() < T.cover) segs.push({ x0: x, x1: Math.min(W - 40, x + w), tier: 1 }); x += w + rng(T.gap[0], T.gap[1]); }
      } else {
        R.tiers.forEach((T, k) => {
          let x = rng(40, 200) + k * 50;
          while (x < W - 120) { const w = rng(T.seg[0], T.seg[1]); if (rr() < T.cover) segs.push({ x0: x, x1: Math.min(W - 30, x + w), tier: k + 1 }); x += w + rng(T.gap[0], T.gap[1]); }
        });
      }
      // 같은 층에서 겹치거나 40 이내로 붙으면 앞 것을 줄이고, 너무 짧은 건 버린다
      segs.sort((a, b) => a.tier - b.tier || a.x0 - b.x0);
      const fin = [];
      for (const s of segs) {
        const prev = fin.length ? fin[fin.length - 1] : null;
        if (prev && prev.tier === s.tier && s.x0 < prev.x1 + 36) { if (s.x1 - (prev.x1 + 36) < 90) continue; s.x0 = prev.x1 + 36; }
        if (s.x1 - s.x0 < 90 || s.x0 < 24) continue;
        fin.push(s);
      }
      // 받침 점검: 위층 발판은 한 층 아래 발판과 가로 간격 ≤ 40 (바닥은 늘 받침). 못 받치면 버린다.
      const byTier = [[], [], [], []];
      const ok = [];
      for (const s of fin) {
        if (s.tier > 1) { let sup = false; for (const q of byTier[s.tier - 1]) if (hgap(s, q) <= 40) { sup = true; break; } if (!sup) continue; }
        byTier[s.tier].push(s); ok.push(s);
      }
      const maxTier = R.stairs || R.plateau ? 3 : R.tiers.length;
      const haveTop = ok.some(s => s.tier === maxTier);
      if (ok.length < 8 || !haveTop) continue;
      const plats = [{ id: 0, kind: 'floor', x0: 0, x1: W, y: GY, solid: true, tier: 0 }];
      ok.sort((a, b) => a.tier - b.tier || a.x0 - b.x0);
      for (const s of ok) plats.push({ id: plats.length, kind: 'plat', x0: s.x0, x1: s.x1, y: GY - s.tier * R.step, solid: false, tier: s.tier });
      // 벽 블록(바닥 위 상자): 서로 150 이상 떨어뜨려 놓는다
      const nb = R.blocks, blocks = [];
      for (let i = 0; i < nb; i++) {
        const cx = 300 + (W - 560) * (i + 0.25 + rr() * 0.5) / nb, w = rng(30, 44), h = rng(30, 46);
        if (blocks.some(b => Math.abs((b.x0 + b.x1) / 2 - cx) < 200)) continue;
        const b = { id: plats.length, kind: 'block', x0: cx - w / 2, x1: cx + w / 2, y: GY - h, solid: true, tier: 0, h };
        blocks.push(b); plats.push(b);
      }
      const M = { reg, seed, W, name: MAP_NAMES[reg], step: R.step, plats, blocks, spawnX: 120 };
      buildNav(M);
      return M;
    }
    return genMap(reg, seed + 101);   // 거의 일어나지 않는다
  }

  // 방(보스 방): 평평한 바닥 하나
  function genRoom(W) {
    const plats = [{ id: 0, kind: 'floor', x0: 0, x1: W, y: GY, solid: true, tier: 0 }];
    const M = { reg: -1, seed: 0, W, name: '보스 방', step: 64, plats, blocks: [], spawnX: 150, room: true };
    buildNav(M); return M;
  }

  // 발판 사이 이동 간선: 점프 높이 ≈ 100, 달려 점프하면 가로 ≈ 120 이므로 여유를 두고 잡는다.
  // 바닥 위에서 블록(벽 상자)을 피한 자리: [lo,hi] 에서 블록 앞뒤 pad 를 뺀 가장 긴 구간의 가운데. 없으면 null.
  function freeX(M, lo, hi, pad) {
    let segs = [[lo, hi]];
    for (const b of M.blocks) {
      const a = b.x0 - pad, c = b.x1 + pad, ns = [];
      for (const q of segs) { if (c <= q[0] || a >= q[1]) ns.push(q); else { if (a > q[0]) ns.push([q[0], a]); if (c < q[1]) ns.push([c, q[1]]); } }
      segs = ns;
    }
    let best = null; for (const q of segs) if (q[1] - q[0] >= 8 && (!best || q[1] - q[0] > best[1] - best[0])) best = q;
    return best ? (best[0] + best[1]) / 2 : null;
  }
  function edgeFor(M, A, B) {
    if (A === B) return null;
    const rise = A.y - B.y;                 // 양수면 B 가 더 높다
    if (rise > 84) return null;
    const gap = hgap(A, B);
    const ov0 = Math.max(A.x0, B.x0), ov1 = Math.min(A.x1, B.x1), ov = ov1 - ov0;
    const e = { to: B.id, act: 'jump', jx: 0, lx: 0, dyn: 0, cost: 0 };
    if (B.kind === 'block') {                // 블록 위로: 바닥에서 옆으로 다가가 올라탄다
      if (A.kind !== 'floor' || rise < 0) return null;
      e.dyn = 'toBlock'; e.cost = 50; return e;
    }
    if (A.kind === 'block' && rise < -6) {   // 블록에서 내려가기: 가야 할 쪽 가장자리로 걸어 나간다
      if (B.kind !== 'floor') return null;
      e.dyn = 'fromBlock'; e.act = 'walk'; e.cost = 40; return e;
    }
    if (rise >= -6) {                        // 같은 높이 · 위
      if (gap > (rise > 20 ? 62 : 76)) return null;
      if (ov >= 26) { const fx = A.kind === 'floor' ? freeX(M, ov0 + 8, ov1 - 8, 12) : (ov0 + ov1) / 2; if (fx == null) return null; e.jx = e.lx = fx; e.cost = 55 + Math.max(0, rise); }
      else { const dir = B.x0 >= A.x1 ? 1 : -1; e.jx = dir > 0 ? A.x1 - 6 : A.x0 + 6; e.lx = dir > 0 ? B.x0 + 18 : B.x1 - 18; e.cost = 70 + gap + Math.max(0, rise); }
      return e;
    }
    // 아래로
    if (ov >= 22 && A.kind === 'plat' && B.kind !== 'block') { const fx = B.kind === 'floor' ? freeX(M, ov0 + 8, ov1 - 8, 12) : (ov0 + ov1) / 2; if (fx != null) { e.act = 'drop'; e.jx = e.lx = fx; e.cost = 40; return e; } }
    if (gap > 96) return null;
    const dir = B.x0 >= A.x1 ? 1 : -1;
    e.act = gap <= 22 ? 'walk' : 'jump'; e.jx = dir > 0 ? A.x1 - 4 : A.x0 + 4; e.lx = dir > 0 ? B.x0 + 24 : B.x1 - 24; e.cost = 45 + gap;
    return e;
  }

  function buildNav(M) {
    const P = M.plats, n = P.length;
    M.edges = P.map(() => []);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const e = edgeFor(M, P[i], P[j]); if (e) M.edges[i].push(e); }
    // 모든 쌍의 최단 경로(다음 발판 · 비용)
    M.next = []; M.dist = [];
    for (let s = 0; s < n; s++) {
      const d = new Array(n).fill(1e9), nx = new Array(n).fill(-1), done = new Array(n).fill(false);
      d[s] = 0;
      for (let it = 0; it < n; it++) {
        let u = -1; for (let i = 0; i < n; i++) if (!done[i] && (u < 0 || d[i] < d[u])) u = i;
        if (u < 0 || d[u] >= 1e9) break; done[u] = true;
        for (const e of M.edges[u]) if (d[u] + e.cost < d[e.to]) { d[e.to] = d[u] + e.cost; nx[e.to] = u === s ? e.to : nx[u]; }
      }
      M.next.push(nx); M.dist.push(d);
    }
    M.edgeTo = (a, b) => { for (const e of M.edges[a]) if (e.to === b) return e; return null; };
    // 몹이 서 있을 수 있는 발판 (블록 윗면 제외, 폭 ≥ 90)
    M.spawnPlats = P.filter(p => p.kind !== 'block' && p.x1 - p.x0 >= 90);
  }

  // 바닥에서 몹이 움직일 수 있는 구간 (블록에 막힌 좁은 방)
  function pocket(M, p, x) {
    let lo = p.x0 + 8, hi = p.x1 - 8;
    if (p.kind === 'floor') for (const b of M.blocks) { if (b.x1 <= x && b.x1 + 10 > lo) lo = b.x1 + 10; if (b.x0 >= x && b.x0 - 10 < hi) hi = b.x0 - 10; }
    return [lo, hi];
  }
  function platBelow(M, x, y) {
    let best = null;
    for (const p of M.plats) { if (p.kind === 'block') continue; if (x < p.x0 - 4 || x > p.x1 + 4) continue; if (p.y < y - 4) continue; if (!best || p.y < best.y) best = p; }
    return best || M.plats[0];
  }

  // =====================================================================
  function create(canvas, opts) {
    opts = opts || {};
    const rnd = mulberry(opts.seed != null ? opts.seed | 0 : (Math.random() * 1e9) | 0);
    const base = opts.base || '';
    const manual = !!opts.manual;
    const hasDoc = typeof document !== 'undefined';
    const ctx = canvas.getContext('2d');
    const showHud = opts.hud !== false;
    const listeners = {};
    const emit = (n, p) => { const a = listeners[n]; if (a) for (let i = 0; i < a.length; i++) { try { a[i](p || {}); } catch (e) { } } };

    const E = {
      t: 0, frames: 0, running: false, raf: 0, last: 0, destroyed: false, vis: true, hidden: false, paused: false, acc: 0, timeScale: opts.timeScale || 1,
      cssW: 0, cssH: 0, dpr: 1, VW: 560, scale: 1, low: false, dtAvg: 0.016, lowN: 0, cam: 0, shake: 0, flash: 0, flashCol: '#fff', zoom: 0, hitstop: 0, slow: 0, tint: 0, tintCol: '#ff3050',
      kills: 0, killLog: [], combo: 0, comboT: 0, comboMax: 0, comboPunch: 0, uid: 1, deaths: 0, runAcc: 0, repKills: 0, spawnT: 0.1, levelT: 0,
      manualT: 0, autoWanted: true, cin: 0, inited: false, lastPoseHash: 0, drawT: 0,
      dim: 0, dimGoal: 0, dimHold: 0, dimCol: '0,0,0', lines: 0, linesCol: '#fff', zax: 0, zay: 0, bigUntil: 0, reduced: false, castLog: {}, usingId: null, usingT: 0
    };
    try { E.reduced = opts.reduced != null ? !!opts.reduced : !!(hasDoc && typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { }
    const st = { stage: 1, region: '', rec: 0, kpm: 100, kpmGiven: 0, party: [], boss: null };
    let C = { atk: 40, hp: 400, def: 10, crit: 5, critdmg: 150, acc: 100, mp: 100, mpregen: 4, power: 0 };
    let MON = { name: '몬스터', hp: 900, atk: 60, def: 30, eva: 90, gold: 0.25 };
    const D = { reg: 0, ratio: 1, dpsNom: 1, mobHp: 100, kdef: 80, passive: null };
    const skills = [null, null, null, null];     // 정규화된 스킬 4칸
    const slotCd = [0, 0, 0, 0, 0, 0, 0, 0];
    let map = genMap(0, opts.seed != null ? opts.seed | 0 : 1);
    let hunt = map;                              // 사냥 지형(보스 방에 들어갔다 나올 때 되돌릴 곳)
    let mobs = [], shots = [], boss = null;
    let INS = null;                              // 인스턴스 전투(열쇠 던전·클랜 보스·보상) 상태

    // ---------- 그림(있으면 쓰고 없으면 절차 그림) ----------
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
    let ANCH = null;  // img/brjhunt/v2/chick_anchors.json — 병아리 시트 칸마다 머리 위치(꾸미기 파츠가 따라붙는다)
    let MAN = null;   // img/brjhunt/v2/manifest.json — 없으면 null (절차 애니메이션으로 대체)
    if (!opts.noManifest && typeof fetch !== 'undefined') {
      try {
        fetch(base + 'img/brjhunt/v2/manifest.json').then(r => r.ok ? r.json() : null).then(j => { if (j && typeof j === 'object') MAN = j.sheets && typeof j.sheets === 'object' ? j.sheets : j; }).catch(() => { });
        fetch(base + 'img/brjhunt/v2/chick_anchors.json').then(r => r.ok ? r.json() : null).then(j => { if (j && typeof j === 'object') ANCH = j; }).catch(() => { });
      } catch (e) { }
    }
    // 시트: manifest[name] = {file, frames, w, h, fps, anchor:[x,y], scale?} — 한 줄 가로 시트. 이름 후보를 차례로 찾는다.
    function sheet() {
      if (!MAN) return null;
      for (let i = 0; i < arguments.length; i++) {
        const m = MAN[arguments[i]]; if (!m || !m.file) continue;
        const im = ld('img/brjhunt/v2/' + m.file); if (!im) continue;
        return { im, m, n: Math.max(1, m.frames | 0 || 1), name: arguments[i] };
      }
      return null;
    }
    function drawSheet(sh, fr, x, y, h, o) {
      o = o || {}; const m = sh.m, fw = m.w || sh.im.width / sh.n, fh = m.h || sh.im.height, s = (m.scale ? m.scale * (h / CHICK_H) : h / fh);
      const ax = m.anchor ? m.anchor[0] : fw / 2, ay = m.anchor ? m.anchor[1] : fh * 0.97;
      ctx.save(); ctx.translate(x, y); if (o.rot) ctx.rotate(o.rot); if (o.a != null) ctx.globalAlpha = o.a;
      ctx.scale((o.sx || 1) * (o.flip ? -1 : 1), o.sy || 1);
      const pa = (E.parts && E.parts.length && ANCH && sh.name && ANCH[sh.name]) ? ANCH[sh.name][fr % sh.n] : null;
      const pg = pa ? { x: (pa.cx - ax) * s, y: (pa.cy - ay) * s, R: pa.r * s, ex: (pa.ex - ax) * s, ey: (pa.ey - ay) * s } : null;
      if (pg) { pg.d = (pa.ex - pa.cx) / pa.r > 0.12 ? 1 : (pa.ex - pa.cx) / pa.r < -0.12 ? -1 : 0; drawChickParts(pg, true); }   // 몸 뒤(망토·날개)
      ctx.drawImage(sh.im, (fr % sh.n) * fw, 0, fw, fh, -ax * s, -ay * s, fw * s, fh * s);
      if (pg) drawChickParts(pg, false);                                                                                          // 몸 앞(목·얼굴·머리)
      ctx.restore();
    }
    // 👗 [2026-11-13 사장님 「꾸미기를 기본 브장신 일러스트에 의상·악세사리·헤어 파츠로」] 움직이는 병아리 시트의 머리 위치(ANCH)에 코드로 그린 파츠를 얹는다 — 달리기·공격·점프 모두 같이 움직인다
    const PART_SLOTS = { back: 0, neck: 1, face: 2, head: 3 };
    const PARTS = {   // 키 -> 슬롯 · 그리기(c, 머리중심 x·y, 반지름 R, 눈중심 ex·ey, 보는 방향 d(-1·0·1), 시간 t)
      cape: { slot: 'back', fn(c, x, y, R, ex, ey, d, t) { const sh = -(d || 0) * 0.5 * R, w = Math.sin(t * 6) * 0.12 * R; c.fillStyle = '#c8203a'; c.strokeStyle = '#6a0e1e'; c.lineWidth = R * 0.07; c.beginPath(); c.moveTo(x + sh - 0.5 * R, y + 0.8 * R); c.lineTo(x + sh + 0.5 * R, y + 0.8 * R); c.lineTo(x + sh + 0.8 * R + w, y + 1.85 * R); c.quadraticCurveTo(x + sh, y + 2.0 * R + w, x + sh - 0.8 * R + w, y + 1.85 * R); c.closePath(); c.fill(); c.stroke(); } },
      wings: { slot: 'back', fn(c, x, y, R, ex, ey, d, t) { const fl = Math.sin(t * 7) * 0.2; for (const sd of [-1, 1]) { c.save(); c.translate(x + sd * 0.95 * R, y + 0.85 * R); c.rotate(sd * (0.6 + fl)); c.fillStyle = '#fff'; c.strokeStyle = '#bcc8ff'; c.lineWidth = R * 0.06; c.beginPath(); c.ellipse(0, -0.35 * R, 0.24 * R, 0.62 * R, 0, 0, 6.3); c.fill(); c.stroke(); c.restore(); } } },
      scarf: { slot: 'neck', fn(c, x, y, R, ex, ey, d, t) { const f = d || 1; c.fillStyle = '#e83a4a'; c.strokeStyle = '#7a1020'; c.lineWidth = R * 0.06; c.beginPath(); c.ellipse(x, y + 0.76 * R, 0.6 * R, 0.14 * R, 0, 0, 6.3); c.fill(); c.stroke(); c.fillStyle = '#ffd7a0'; c.fillRect(x - 0.35 * R, y + 0.71 * R, 0.11 * R, 0.11 * R); c.fillRect(x + 0.05 * R, y + 0.72 * R, 0.11 * R, 0.1 * R); const sw = Math.sin(t * 5) * 0.08 * R; c.fillStyle = '#e83a4a'; c.beginPath(); c.moveTo(x - f * 0.4 * R, y + 0.82 * R); c.lineTo(x - f * (0.8 * R + sw), y + 1.25 * R); c.lineTo(x - f * (0.55 * R + sw), y + 1.3 * R); c.lineTo(x - f * 0.25 * R, y + 0.88 * R); c.closePath(); c.fill(); c.stroke(); } },
      bowtie: { slot: 'neck', fn(c, x, y, R) { const yy = y + 0.84 * R; c.fillStyle = '#c01040'; c.strokeStyle = '#5a0820'; c.lineWidth = R * 0.05; for (const sd of [-1, 1]) { c.beginPath(); c.moveTo(x, yy); c.lineTo(x + sd * 0.5 * R, yy - 0.22 * R); c.lineTo(x + sd * 0.5 * R, yy + 0.22 * R); c.closePath(); c.fill(); c.stroke(); } c.beginPath(); c.arc(x, yy, 0.1 * R, 0, 6.3); c.fill(); } },
      sunglasses: { slot: 'face', fn(c, x, y, R, ex, ey) { c.fillStyle = '#10121a'; c.strokeStyle = '#000'; c.lineWidth = R * 0.05; for (const sd of [-1, 1]) { c.beginPath(); c.ellipse(ex + sd * 0.34 * R, ey, 0.3 * R, 0.21 * R, 0, 0, 6.3); c.fill(); c.stroke(); } c.beginPath(); c.moveTo(ex - 0.06 * R, ey); c.lineTo(ex + 0.06 * R, ey); c.stroke(); c.fillStyle = 'rgba(255,255,255,.5)'; c.beginPath(); c.ellipse(ex - 0.42 * R, ey - 0.08 * R, 0.09 * R, 0.05 * R, -0.4, 0, 6.3); c.fill(); } },
      crown: { slot: 'head', fn(c, x, y, R) { c.fillStyle = '#ffd23c'; c.strokeStyle = '#8a5a00'; c.lineWidth = R * 0.06; c.beginPath(); c.moveTo(x - 0.55 * R, y - 0.72 * R); c.lineTo(x - 0.6 * R, y - 1.3 * R); c.lineTo(x - 0.28 * R, y - 1.0 * R); c.lineTo(x, y - 1.42 * R); c.lineTo(x + 0.28 * R, y - 1.0 * R); c.lineTo(x + 0.6 * R, y - 1.3 * R); c.lineTo(x + 0.55 * R, y - 0.72 * R); c.closePath(); c.fill(); c.stroke(); c.fillStyle = '#ff4a5a'; c.beginPath(); c.arc(x, y - 0.92 * R, 0.1 * R, 0, 6.3); c.fill(); } },
      bow: { slot: 'head', fn(c, x, y, R) { const bx = x + 0.55 * R, by = y - 0.82 * R; c.fillStyle = '#ff7ab0'; c.strokeStyle = '#a02a62'; c.lineWidth = R * 0.05; for (const sd of [-1, 1]) { c.beginPath(); c.moveTo(bx, by); c.lineTo(bx + sd * 0.55 * R, by - 0.3 * R); c.lineTo(bx + sd * 0.55 * R, by + 0.3 * R); c.closePath(); c.fill(); c.stroke(); } c.beginPath(); c.arc(bx, by, 0.12 * R, 0, 6.3); c.fill(); c.stroke(); } },
      wizard: { slot: 'head', fn(c, x, y, R, ex, ey, d, t) { const f = d || 1; c.fillStyle = '#6a3fc8'; c.strokeStyle = '#2a1060'; c.lineWidth = R * 0.06; c.beginPath(); c.moveTo(x - 0.62 * R, y - 0.8 * R); c.quadraticCurveTo(x - 0.2 * R, y - 1.6 * R, x + f * 0.5 * R + Math.sin(t * 3) * 0.05 * R, y - 2.15 * R); c.quadraticCurveTo(x + 0.35 * R, y - 1.5 * R, x + 0.62 * R, y - 0.8 * R); c.closePath(); c.fill(); c.stroke(); c.fillStyle = '#4a2a98'; c.beginPath(); c.ellipse(x, y - 0.8 * R, 0.98 * R, 0.2 * R, 0, 0, 6.3); c.fill(); c.stroke(); c.fillStyle = '#ffe27a'; c.beginPath(); c.arc(x - 0.1 * R, y - 1.35 * R, 0.1 * R, 0, 6.3); c.fill(); c.beginPath(); c.arc(x + 0.2 * R, y - 1.65 * R, 0.07 * R, 0, 6.3); c.fill(); } },
      mohawk: { slot: 'head', fn(c, x, y, R, ex, ey, d, t) { c.fillStyle = '#ff3a4a'; c.strokeStyle = '#7a0a18'; c.lineWidth = R * 0.05; for (let i = -2; i <= 2; i++) { const bx = x + i * 0.22 * R, by = y - 0.95 * R + Math.abs(i) * 0.1 * R, sw = Math.sin(t * 4 + i) * 0.03 * R; c.beginPath(); c.moveTo(bx - 0.12 * R, by + 0.05 * R); c.lineTo(bx + i * 0.06 * R + sw, by - (0.6 - Math.abs(i) * 0.1) * R); c.lineTo(bx + 0.12 * R, by + 0.05 * R); c.closePath(); c.fill(); c.stroke(); } } },
      headphones: { slot: 'head', fn(c, x, y, R) { c.strokeStyle = '#2a2d3a'; c.lineWidth = R * 0.14; c.lineCap = 'round'; c.beginPath(); c.arc(x, y, R * 1.02, Math.PI * 1.1, Math.PI * 1.9); c.stroke(); c.fillStyle = '#ff5a8a'; c.strokeStyle = '#7a1a40'; c.lineWidth = R * 0.05; for (const sd of [-1, 1]) { c.beginPath(); c.ellipse(x + sd * 1.0 * R, y + 0.02 * R, 0.22 * R, 0.34 * R, 0, 0, 6.3); c.fill(); c.stroke(); } } }
    };
    function drawChickParts(g, back) {
      for (const it of E.parts) { const pd = PARTS[it.key]; if (!pd || (pd.slot === 'back') !== back) continue; try { pd.fn(ctx, g.x, g.y, g.R, g.ex, g.ey, g.d, E.t); } catch (e) { if (!E.partErr) { E.partErr = String(e); console.warn('parts', e); } } }
    }
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
    const ec = {};
    function emo(ch, px) {
      const k = ch + px; let c = ec[k];
      if (!c) {
        if (!hasDoc) return null;
        const sz = Math.ceil(px * 1.4 * 2); c = document.createElement('canvas'); c.width = c.height = sz;
        const x = c.getContext('2d'); x.font = Math.round(px * 2) + 'px ' + FONT; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(ch, sz / 2, sz / 2);
        c.dw = sz / 2; ec[k] = c;
      }
      return c;
    }
    function shadow(x, y, rx, a) { ctx.fillStyle = 'rgba(0,0,0,' + (a || 0.28) + ')'; ctx.beginPath(); ctx.ellipse(x, y + 1, rx, rx * 0.2, 0, 0, 6.3); ctx.fill(); }
    function outText(s, x, y, size, col, al, sw, ol) {
      ctx.font = '900 ' + size + 'px ' + FONT; ctx.textAlign = al || 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
      ctx.lineWidth = sw || Math.max(2.5, size / 4.5); ctx.strokeStyle = ol || 'rgba(14,10,24,.9)'; ctx.strokeText(s, x, y); ctx.fillStyle = col; ctx.fillText(s, x, y);
    }

    // ---------- 풀: 입자 · 숫자 ----------
    const PMAX = 220, TMAX = 30;
    const PMLOW = Math.floor(PMAX * 0.5);
    const parts = [], texts = [];
    for (let i = 0; i < PMAX; i++) parts.push({ on: false, k: '', x: 0, y: 0, vx: 0, vy: 0, t: 0, life: 1, r: 2, c: '#fff', rot: 0, vr: 0, a: 0, b: 0, d: 1 });
    for (let i = 0; i < TMAX; i++) texts.push({ on: false, s: '', x: 0, y: 0, vy: 0, t: 0, life: 1, size: 14, col: '#fff', kind: 'n' });
    let pCur = 0;
    function newPart(k, x, y, vx, vy, life, r, c) {
      const lim = E.low ? PMLOW : PMAX;
      let p = null;
      for (let n = 0; n < lim; n++) { const q = parts[(pCur + n) % lim]; if (!q.on) { p = q; pCur = (pCur + n + 1) % lim; break; } }
      if (!p) { if (k !== 'coin' && k !== 'ring' && k !== 'star') return null; p = parts[pCur = (pCur + 1) % lim]; }
      p.on = true; p.k = k; p.x = x; p.y = y; p.vx = vx; p.vy = vy; p.t = 0; p.life = life; p.r = r; p.c = c; p.rot = rnd() * 6.28; p.vr = (rnd() - 0.5) * 12; p.a = 0; p.b = 0; p.d = 1;
      return p;
    }
    const TCAP = 14;
    function say(s, x, y, kind, size, col, ol) {
      let t = null, oldest = null, live = 0;
      for (let i = 0; i < TMAX; i++) { const q = texts[i]; if (!q.on) { if (!t) t = q; continue; } live++; if (!oldest || q.t > oldest.t) oldest = q; }
      if (live >= TCAP || !t) { if (kind === 'n' || kind === 'm') return; t = oldest; }
      // 같은 자리에 방금 뜬 숫자가 있으면 한 칸씩 위로 쌓는다(겹쳐 읽기 힘든 것을 막는다)
      let stack = 0; for (let i = 0; i < TMAX; i++) { const q = texts[i]; if (q.on && q !== t && q.t < 0.3 && Math.abs(q.x - x) < 34 && Math.abs(q.y - y) < 40) stack++; }
      y -= Math.min(3, stack) * 11;
      t.on = true; t.s = s; t.kind = kind; t.x = x + (rnd() - 0.5) * 18; t.y = y; t.vy = -(52 + rnd() * 26) * (kind === 'c' ? 1.15 : 1); t.t = 0;
      t.life = kind === 'c' ? 1.1 : kind === 'r' ? 0.95 : 0.8; t.size = size; t.col = col; t.ol = ol || null;
    }
    const poof = (x, y, c, n, sp, up) => { for (let i = 0; i < n; i++) { const a = rnd() * 6.28, s = (sp || 70) * (0.4 + rnd()); newPart('dot', x, y, Math.cos(a) * s, Math.sin(a) * s - (up == null ? 30 : up), 0.35 + rnd() * 0.2, 1.4 + rnd() * 2, c); } };
    const sparks = (x, y, dirx, c, n, sp) => { for (let i = 0; i < n; i++) { const a = (dirx < 0 ? Math.PI : 0) + (rnd() - 0.5) * 1.9, s = (sp || 190) * (0.5 + rnd() * 0.8); newPart('spark', x, y, Math.cos(a) * s, Math.sin(a) * s - 30, 0.18 + rnd() * 0.16, 7 + rnd() * 8, c); } };
    const ring = (x, y, c, r, life) => newPart('ring', x, y, 0, 0, life || 0.4, r || 40, c);
    const dust = (x, y, n, dirx) => { for (let i = 0; i < n; i++) newPart('dust', x + (rnd() - 0.5) * 8, y - 1, (dirx || 0) * (10 + rnd() * 30) + (rnd() - 0.5) * 30, -(8 + rnd() * 24), 0.32 + rnd() * 0.2, 2.6 + rnd() * 2.4, '#e8dcc0'); };

    // ---------- 병아리 ----------
    const P = {
      x: 120, y: GY, vx: 0, vy: 0, face: 1, on: true, plat: map.plats[0], lastPlat: 0, jumps: 0, dropT: 0, hp: 400, hpMax: 400, mp: 100, mpMax: 100,
      inv: 0, dead: false, deadT: 0, hurtT: 0, atkT: 0, atkDur: 0.26, atkIdx: 0, comboT: 0, struck: true, cast: null, dash: null, shieldT: 0, sq: 0, stepT: 0, run: 0,
      afterT: 0, afterCol: '#fff', afterId: '', djT: 0, castFlash: 0, blocked: false, airT: 0, jumpHeld: false, hpFlash: 0, regenT: 0, stuckT: 0, lastX: 120, tele: 0
    };
    function resetPlayerPos(x) {
      P.x = x; P.y = GY; P.vx = P.vy = 0; P.on = true; P.plat = map.plats[0]; P.lastPlat = 0; P.jumps = 0; P.dropT = 0; P.cast = null; P.dash = null; P.atkT = 0; P.hurtT = 0;
    }

    // ---------- 입력 ----------
    const KEYS = { left: 1, right: 1, up: 1, down: 1, jump: 1, attack: 1, s1: 1, s2: 1, s3: 1, s4: 1, s5: 1, s6: 1, s7: 1, s8: 1 };
    const Hh = {}, ED = {};    // 누르고 있는 것 · 이번 갱신에 새로 눌린 것
    for (const k in KEYS) { Hh[k] = false; ED[k] = false; }
    function press(name) {
      if (name === 'auto') { setAuto(!E.autoWanted); return; }
      if (name === 'pause') { setPaused(!E.paused); return; }
      if (name === 'up') name = 'jump';
      if (!KEYS[name]) return;
      if (!Hh[name]) ED[name] = (name.charAt(0) === 's' && name.length === 2) ? 0.16 : true;   // 스킬 키는 쿨다운이 거의 끝난 순간에 눌러도 먹히게 0.16초 동안 기억한다
      Hh[name] = true; humanTouch(name);
    }
    function release(name) { if (name === 'up') name = 'jump'; if (KEYS[name]) Hh[name] = false; }
    function humanTouch(name) {
      if (name === 'down' || name === 'up') return;   // 위/아래만 누른 건 수동 신호로 치지 않는다(↑ 는 점프지만 아래는 아님)
      E.manualT = MANUAL_HOLD;
    }
    const input = { press, release, held: n => !!Hh[n] };
    function setAuto(b) { E.autoWanted = !!b; E.manualT = 0; if (b) { for (const k in KEYS) { Hh[k] = false; } } emit('auto', { on: !!b }); }
    function autoOn() { return E.autoWanted && E.manualT <= 0 && !E.paused; }
    function setPaused(b) { E.paused = !!b; if (!b) { E.last = typeof performance !== 'undefined' ? performance.now() : 0; } }
    let keyDown = null, keyUp = null;
    const KMAP = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'jump', ArrowDown: 'down', ' ': 'jump', Alt: 'jump', Control: 'attack', z: 'attack', Z: 'attack', 1: 's1', 2: 's2', 3: 's3', 4: 's4', 5: 's5', 6: 's6', 7: 's7', 8: 's8', q: 's5', w: 's6', e: 's7', r: 's8', Q: 's5', W: 's6', E: 's7', R: 's8', a: 's1', s: 's2', d: 's3', f: 's4', A: 's1', S: 's2', D: 's3', F: 's4', Tab: 'auto', g: 'auto', G: 'auto', p: 'pause', P: 'pause' };
    const KLETTER = { KeyZ: 'attack', KeyA: 's1', KeyS: 's2', KeyD: 's3', KeyF: 's4', KeyQ: 's5', KeyW: 's6', KeyE: 's7', KeyR: 's8', KeyG: 'auto', KeyP: 'pause' };   // 한글 입력 상태(e.key 가 'ㅋ' 등)에서도 물리 키 위치로 읽는다
    const KCODE = { AltLeft: 'jump', AltRight: 'jump', ControlLeft: 'attack', ControlRight: 'attack', Space: 'jump' };
    function typing(e) { const t = e.target; return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable); }
    function keyOf(e) { return KCODE[e.code] || KMAP[e.key] || KLETTER[e.code]; }
    if (hasDoc && opts.keys !== false) {
      keyDown = e => {
        if (!E.running || !E.vis || E.destroyed || E.keysOff || typing(e) || e.metaKey) return;
        const n = keyOf(e); if (!n) return;
        if (n === 'auto' || n === 'pause') { if (!e.repeat) press(n); e.preventDefault(); return; }
        if (n === 'jump' && e.key === 'ArrowUp' && e.shiftKey) return;
        e.preventDefault(); if (!e.repeat) press(n); else humanTouch(n);
      };
      keyUp = e => { const n = keyOf(e); if (n && n !== 'auto' && n !== 'pause') release(n); };
      window.addEventListener('keydown', keyDown); window.addEventListener('keyup', keyUp);
      window.addEventListener('blur', blurAll);
    }
    function blurAll() { for (const k in KEYS) Hh[k] = false; }

    // ---------- 파생 값 ----------
    function normSkill(s) {
      if (!s || !s.id || !SKD[s.id]) return null;
      const d = SKD[s.id], o = { id: s.id };
      o.buff = N(s.buff_pct); o.key = s.key; o.shape = (d.shape === 'dash' || (s.shape === 'self' && d.shape !== 'self')) ? d.shape : (['arc', 'proj', 'aoe', 'self', 'dash', 'buff', 'blink', 'pull'].indexOf(s.shape) >= 0 ? s.shape : d.shape);   // 돌격(흐접새우)은 서버가 'self' 로 보내도 돌격 — 안 그러면 방어막만 켜져 소환이 먹통처럼 보인다
      o.mp = Math.max(0, s.mp != null ? N(s.mp) : d.mp); o.cd = Math.max(0.2, s.cd != null ? N(s.cd) : d.cd); o.cast = clamp(s.cast != null ? N(s.cast) : d.cast, 0.05, 1.5);
      o.range = clamp(s.range != null ? N(s.range) : d.range, 30, 1500); o.hits = clamp(Math.round(s.hits != null ? N(s.hits) : d.hits) || 1, 1, 12);
      o.mult = Math.max(5, s.mult != null ? N(s.mult) : d.mult); o.lv = N(s.lv) || 1; o.col = SKV[s.id] ? SKV[s.id].col : (/^#[0-9a-f]{3,8}$/i.test(s.fx_color || '') ? s.fx_color : d.col); o.both = !!d.both || !!s.both; o.pierce = !!d.pierce || !!s.pierce;
      return o;
    }
    function nominalDps() {
      // 이론상 초당 피해: 기본 공격 + (MP·쿨다운 안에서 쓸 수 있는 만큼의) 스킬. 크리티컬·적중 반영.
      const crit = clamp(C.crit, 0, 100) / 100, cm = 1 + crit * (C.critdmg / 100 - 1), hit = clamp(C.acc / (C.acc + MON.eva), 0.25, 0.99);
      const per = C.atk * cm * hit;
      let dps = per * 1.23 * BASIC_HPS;     // 기본 공격 평균 계수(1.0·1.1·1.6 의 평균) × 초당 타수
      let rates = [], spend = 0;
      skills.forEach(s => { if (!s || s.shape === 'self') { rates.push(0); return; } const r = 1 / (s.cd + s.cast); rates.push(r); spend += r * s.mp; });
      const k = spend > 0 ? Math.min(1, Math.max(0, C.mpregen) / spend) : 1;
      skills.forEach((s, i) => { if (!s || !rates[i]) return; const tg = s.shape === 'arc' || s.shape === 'aoe' ? 1.5 : 1.15; dps += per * (s.mult / 100) * s.hits * tg * rates[i] * k; });
      return Math.max(1, dps);
    }
    function derive() {
      D.kdef = K_DEF_BASE + K_DEF_PER_STAGE * Math.max(1, st.stage);
      D.dpsNom = nominalDps();
      const power = N(C.power), rec = N(st.rec);
      // 비율: ① 서버의 power ÷ rec_power ② 없으면 kpm_model ÷ 100(서버 모델이 kpm = 100·power/rec 라서) ③ 둘 다 없으면 이론 피해 ÷ 몹 체력
      D.ratio = (power > 0 && rec > 0) ? power / rec : (st.kpmGiven > 0 ? st.kpmGiven / 100 : D.dpsNom / Math.max(1, MON.hp * DPS_PER_HP));
      D.ratio = clamp(D.ratio, 0.05, 40);
      if ((power > 0 && rec > 0) || st.kpmGiven > 0) D.ratio = Math.max(0.03, calRatio(D.ratio));
      D.mobHp = Math.max(1, D.dpsNom * (opts.cal || CAL_TTK) / D.ratio);
      D.passive = skills.passive || null;
      const rg = String(st.region || '').toLowerCase(); let ri = -1;
      for (let i = 0; i < 6; i++) if (rg.indexOf(REG_KEY[i]) >= 0) { ri = i; break; }
      if (ri < 0) ri = Math.floor((Math.max(1, st.stage) - 1) / 5) % 6;
      const changed = ri !== D.reg;
      D.reg = ri;
      if (changed && !boss && !INS) { setMap(genMap(ri, opts.seed != null ? opts.seed | 0 : 1)); }
      art('chick_idle'); art('m' + (D.reg + 1) + '_idle'); art('bg' + (D.reg + 1));
    }
    function setMap(m) {
      map = m; hunt = m; mobs.length = 0; shots.length = 0;
      resetPlayerPos(m.spawnX); E.cam = clamp(P.x - E.VW * 0.4, 0, Math.max(0, m.W - E.VW));
    }
    function applyCombat() {
      const keepFrac = P.hpMax > 0 ? P.hp / P.hpMax : 1;
      P.hpMax = Math.max(1, Math.round(C.hp)); P.mpMax = Math.max(1, C.mp);
      P.hp = E.inited ? Math.min(P.hpMax, Math.max(1, Math.round(P.hpMax * keepFrac))) : P.hpMax; if (!E.inited) P.mp = P.mpMax; P.mp = Math.min(P.mp, P.mpMax);
    }

    // ---------- 판정 도우미 ----------
    function mobBox(m) { const w = 10 * m.sc, h = 24 * m.sc; return { x0: m.x - w, x1: m.x + w, y0: m.y - h - (m.fly ? 0 : 0), y1: m.y }; }
    function overlapBox(m, x0, x1, y0, y1) { const w = 10 * m.sc, h = 24 * m.sc; return m.x + w > x0 && m.x - w < x1 && m.y > y0 && m.y - h < y1; }
    function liveMob(m) { return m.st !== 'dying' && m.st !== 'spawn'; }
    function mobsInBox(x0, x1, y0, y1, max) {
      const out = [];
      for (let i = 0; i < mobs.length; i++) { const m = mobs[i]; if (liveMob(m) && overlapBox(m, x0, x1, y0, y1)) out.push(m); }
      out.sort((a, b) => Math.abs(a.x - P.x) - Math.abs(b.x - P.x));
      if (max && out.length > max) out.length = max;
      return out;
    }
    function reduction(def) { return def / (def + D.kdef); }

    // ---------- 피해 ----------
    function hitMob(m, mult, o) {
      o = o || {};
      if (!liveMob(m)) return false;
      if (m.boss && boss && boss.clan) return clanHit(m, mult, o);
      const pHit = clamp(C.acc / (C.acc + MON.eva), 0.25, 0.99);
      if (!o.sure && rnd() > pHit) { if (!texts.some(t => t.on && t.kind === 'm' && t.t < 0.2 && Math.abs(t.x - m.x) < 40)) say('MISS', m.x, m.y - 30 * m.sc, 'm', 10, '#b9c0d4'); emit('miss'); return false; }
      const crit = rnd() * 100 < clamp(C.crit, 0, 100);
      let d = C.atk * mult / 100 * (0.93 + rnd() * 0.14) * (E.rageT > 0 ? E.rageMul : 1);
      if (crit) d *= C.critdmg / 100;
      d = Math.max(1, Math.round(d));
      m.hp -= d; m.hit = 0.16; m.sqz = 1;
      const dirx = o.fromX != null ? (m.x >= o.fromX ? 1 : -1) : P.face;
      if (!m.boss) m.kb += dirx * (o.kb != null ? o.kb : 55) * (m.big ? 0.1 : m.el ? 0.5 : 1);
      const kind = crit ? 'c' : o.skill ? 's' : 'n';
      const sv = o.skill ? SKV[o.skill] : null;
      say(fmtNum(d) + (crit ? '!' : ''), m.x, m.y - 30 * m.sc, kind, crit ? 23 : o.skill ? 19 : 13, crit ? '#ffd23c' : o.skill ? (o.col || '#fff') : '#fff', sv ? sv.dark : null);
      if (sv && !m.boss) {   // 스킬마다 맞은 몬스터 모습이 다르다: 베기=칼자국 · 불=화상 · 번개=감전 · 방패·돌격=밀려남 · 황금알=금빛
        m.fxk = sv.hit; m.fxt = sv.hit === 'burn' ? 1.5 : sv.hit === 'shock' ? 0.75 : sv.hit === 'gold' ? 0.6 : 0.3; m.fxc = sv.col; m.fxd = dirx; m.fxa = 0;
        if (fxs.length < 40) {
          if (sv.hsh) fxPush({ k: 'sf', sh: sv.hsh, x: m.x, y: m.y - 16 * m.sc, w: sv.hit === 'shock' ? 120 : 58, t: 0, life: 0.3, col: sv.col, fr0: sv.hsh === 'sk_thunder' ? 1 : 0 }, o.skill);
          if (sv.hit === 'cut') fxPush({ k: 'cut', x: m.x, y: m.y - 16 * m.sc, ang: -0.75 + rnd() * 0.3, t: 0, life: 0.24, col: sv.col }, o.skill);
        }
      }
      const hy = m.y - 14 * m.sc;
      sparks(m.x - dirx * 4, hy, dirx, crit ? '#ffe9a0' : (o.col || '#ffffff'), crit ? 10 : 5, crit ? 240 : 170);
      newPart('flash', m.x, hy, 0, 0, 0.12, crit ? 26 : 16, crit ? '#fff2b0' : (o.col || '#ffffff'));
      if (crit) { newPart('star', m.x, hy - 4, 0, -20, 0.38, 22, '#ffd23c'); E.zoom = Math.max(E.zoom, 0.04); E.shake = Math.max(E.shake, 3.2); E.hitstop = Math.max(E.hitstop, 0.05); }
      else if (o.skill) { E.shake = Math.max(E.shake, 1.8); E.hitstop = Math.max(E.hitstop, 0.025); }
      else E.shake = Math.max(E.shake, 0.8);
      E.combo++; E.comboT = 2.0; E.comboPunch = 1; if (E.combo > E.comboMax) E.comboMax = E.combo;
      emit('hit', { crit, dmg: d, skill: o.skill || null });
      if (boss && m.boss) return false;
      if (m.hp <= 0) { killMob(m, o.fromX != null ? o.fromX : P.x); return true; }
      if (m.st === 'patrol') { m.st = 'chase'; m.t = 0; }
      return false;
    }
    function killMob(m, srcX) {
      m.st = 'dying'; m.t = 0; const dir = m.x >= srcX ? 1 : -1;
      m.dvx = dir * (90 + rnd() * 70); m.dvy = -210 - rnd() * 80; m.drot = dir * (3 + rnd() * 4); m.dz = m.y;
      if (m.big) {   // 👹 소환한 엘리트(대형 몬스터) — 일반 처치 수에는 안 세고(골드 보고 부풀기 방지) 크게 터뜨린 뒤 'elitedie' 로 서버에 알린다
        if (E.elite === m) E.elite = null;
        const by = m.y - 16 * m.sc;
        ring(m.x, m.y - 12, '#ff5c7a', 170, 0.75); ring(m.x, m.y - 12, '#ffd23c', 112, 0.55); ring(m.x, m.y - 12, '#fff', 70, 0.4);
        poof(m.x, by, '#ffd23c', 20, 240); poof(m.x, by, '#ff8aa0', 12, 180);
        for (let i = 0; i < 16; i++) newPart('coin', m.x, by, (rnd() - 0.5) * 220, -190 - rnd() * 140, 6, 4.2, '#ffd23c').b = m.y;
        newPart('flash', m.x, by, 0, 0, 0.3, 120, '#fff2b0');
        E.hitstop = Math.max(E.hitstop, 0.14); E.shake = Math.max(E.shake, 10); flashS(0.35, '#fff2b0'); E.slow = Math.max(E.slow, 0.45);
        say('엘리트 처치!', m.x, m.y - 80 * m.sc / 2.6, 'c', 26, '#ffd23c');
        emit('elitedie', { id: m.eid, x: m.x, y: m.y, name: m.name });
        return;
      }
      E.kills++; E.lastKillT = E.t; if (!boss && !INS) E.repKills++;
      E.killLog.push(E.t); if (E.killLog.length > 900) E.killLog.shift();
      const nc = m.el ? 6 : (E.low ? 1 : 2);
      for (let i = 0; i < nc; i++) newPart('coin', m.x, m.y - 14 * m.sc, (rnd() - 0.5) * 120, -150 - rnd() * 90, 6, 4.2, '#ffd23c').b = m.y;
      poof(m.x, m.y - 14 * m.sc, m.el ? '#ffd23c' : '#fff6c0', m.el ? 12 : 6, 100);
      ring(m.x, m.y - 12, m.el ? '#ffd23c' : '#fff6c0', m.el ? 54 : 34, 0.35);
      E.hitstop = Math.max(E.hitstop, m.el ? 0.08 : 0.04); E.shake = Math.max(E.shake, m.el ? 4 : 1.6);
      emit('kill', { n: E.kills, gold: N(MON.gold) * (1) });
      emit('mobdie', { el: !!m.el, x: m.x });
    }
    function hurtPlayer(rawAtk, srcX, o) {
      o = o || {};
      if (P.dead || P.inv > 0 || P.dash) return false;
      let d = rawAtk * (1 - reduction(C.def)) * (o.k || CONTACT_K) * (0.9 + rnd() * 0.2);
      if (P.shieldT > 0) d *= 0.5;
      if (D.passive === 'shield') d *= 0.85;
      d = Math.max(1, Math.round(d));
      P.hp -= d; if (INS && INS.safe) P.hp = Math.max(P.hp, Math.ceil(P.hpMax * 0.22)); P.inv = INVULN; P.hurtT = 0.28; P.hpFlash = 1; P.atkT = 0; P.cast = null; P.struck = true;
      const dir = P.x >= srcX ? 1 : -1;
      P.vx = dir * 150; if (P.on) { P.vy = -190; P.on = false; P.jumps = 1; }
      say('-' + fmtNum(d), P.x, P.y - PH - 8, 'r', 16, '#ff5c7a');
      sparks(P.x, P.y - 16, dir, '#ff8aa0', 6, 150); newPart('flash', P.x, P.y - 16, 0, 0, 0.14, 22, '#ff5c7a');
      E.shake = Math.max(E.shake, 4.5); E.flash = Math.max(E.flash, 0.16); E.flashCol = '#ff3050'; E.hitstop = Math.max(E.hitstop, 0.05);
      E.combo = 0; E.comboT = 0;
      emit('hurt', { dmg: d });
      if (P.hp <= 0) die();
      return true;
    }
    function die() {
      P.hp = 0; P.dead = true; P.deadT = REVIVE_T; P.vx = (P.face > 0 ? -1 : 1) * 60; P.vy = -260; P.on = false; P.cast = null; P.dash = null; P.atkT = 0;
      E.deaths++; E.combo = 0; E.shake = Math.max(E.shake, 8); E.flash = Math.max(E.flash, 0.4); E.flashCol = '#000';
      poof(P.x, P.y - 20, '#ffe27a', 14, 150);
      emit('die', {});
    }
    function revive() {
      P.dead = false; P.hp = P.hpMax; P.mp = P.mpMax; P.inv = 2.2; resetPlayerPos(map.spawnX); P.hurtT = 0;
      E.cam = clamp(P.x - E.VW * 0.4, 0, Math.max(0, map.W - E.VW));
      ring(P.x, P.y - 14, '#ffe14a', 60, 0.6); poof(P.x, P.y - 20, '#ffe14a', 14, 130);
      newPart('beam', P.x, P.y, 0, 0, 0.9, 26, '#ffe14a');
      emit('revive', {});
    }

    // =====================================================================
    //  병아리 움직임·충돌
    // =====================================================================
    function moveBody(p, h) {
      const M = map, px = p.x, py = p.y;
      p.blocked = false;
      p.x += p.vx * h;
      p.x = clamp(p.x, PW + 2, M.W - PW - 2);
      pushBlocks(p, px);
      const wasOn = p.on;
      p.vy = Math.min(900, p.vy + GRAV * h);
      p.y += p.vy * h;
      p.on = false;
      if (p.vy >= 0) {
        let best = null;
        for (let i = 0; i < M.plats.length; i++) {
          const q = M.plats[i];
          if (q.kind === 'plat' && p.dropT > 0) continue;
          if (p.x < q.x0 - 3 || p.x > q.x1 + 3) continue;
          if (py <= q.y + 0.5 && p.y >= q.y && (!best || q.y < best.y)) best = q;
        }
        if (best) {
          const hard = p.vy;
          p.y = best.y; p.vy = 0; p.on = true; p.plat = best; p.lastPlat = best.id; p.jumps = 0;
          if (!wasOn) onLand(hard);
        }
      }
      if (!p.on) pushBlocks(p, px);   // 윗면 모서리를 스치며 내려가다 블록 몸통에 끼면 밀어낸다
      if (p.y > GY + 40) { p.y = GY; p.vy = 0; p.on = true; p.plat = M.plats[0]; p.lastPlat = 0; }
    }
    // 벽 블록(바닥 위 상자): 발이 윗면보다 아래에서 몸이 겹치면 옆으로 밀어낸다
    function pushBlocks(p, px) {
      const bl = map.blocks;
      for (let i = 0; i < bl.length; i++) {
        const b = bl[i];
        if (p.y > b.y + 0.5 && p.x + PW > b.x0 && p.x - PW < b.x1) {
          if (px <= (b.x0 + b.x1) / 2) p.x = b.x0 - PW; else p.x = b.x1 + PW;
          p.vx = 0; p.blocked = true;
        }
      }
    }
    function onLand(vy) {
      P.sq = clamp(vy / 760, 0.1, 0.9);
      if (vy > 260) { dust(P.x - 5, P.y, 3, -1); dust(P.x + 5, P.y, 3, 1); }
      emit('land', { hard: vy > 520 });
    }

    function doJump(Ct) {
      if (P.on) {
        if (Ct.down && P.plat && P.plat.kind === 'plat') { P.dropT = 0.26; P.y += 2; P.on = false; P.vy = 60; return; }
        P.vy = -JUMP_V; P.on = false; P.jumps = 1; P.airT = 0; P.sq = -0.35;
        dust(P.x, P.y, 4, 0); newPart('ring', P.x, P.y, 0, 0, 0.22, 14, '#e8dcc0');
        emit('jump', { n: 1 });
      } else if (P.jumps < 2 && !(P.cast || P.dash)) {
        P.vy = -JUMP2_V; P.jumps = 2; P.sq = -0.25; P.djT = 0.32;
        newPart('ring', P.x, P.y - 6, 0, 0, 0.25, 18, '#fff6c0'); poof(P.x, P.y - 4, '#fff6c0', 4, 60, 0);
        emit('jump', { n: 2 });
      }
    }

    // ---------- 기본 공격 ----------
    const COMBO_MULT = [100, 110, 160], COMBO_DUR = [0.15, 0.15, 0.22], COMBO_KB = [45, 45, 150];
    function startSwing() {
      P.atkIdx = P.comboT > 0 ? (P.atkIdx + 1) % 3 : 0;
      P.atkDur = COMBO_DUR[P.atkIdx]; P.atkT = P.atkDur; P.struck = false; P.comboT = 0;
      fxs.push({ k: 'swing', x: P.x, y: P.y - 18, face: P.face, idx: P.atkIdx, t: 0, life: 0.2, col: '#ffffff' });
      emit('swing', { n: P.atkIdx });
    }
    function frontBox(range, both, tall) {   // tall: 스킬은 위아래로 넓게(핵앤슬래시처럼 쓸어버리는 느낌 — 2026-11-13)
      const f = P.face;
      return [both ? P.x - range : (f > 0 ? P.x - 6 : P.x - range), both ? P.x + range : (f > 0 ? P.x + range : P.x + 6), P.y - (tall ? 120 : 48), P.y + (tall ? 36 : 6)];
    }
    function strike() {
      const bx = frontBox(REACH + (P.atkIdx === 2 ? 8 : 0), false), idx = P.atkIdx;
      const ts = mobsInBox(bx[0], bx[1], bx[2], bx[3], idx === 2 ? 5 : 4);
      let any = false;
      E.nStrike = (E.nStrike || 0) + 1; if (!ts.length) { E.nEmpty = (E.nEmpty || 0) + 1; P.emptyRun = (P.emptyRun || 0) + 1; } else P.emptyRun = 0;
      for (const m of ts) { hitMob(m, COMBO_MULT[idx], { kb: COMBO_KB[idx], fromX: P.x }); any = true; }
      if (any) { P.vx += P.face * (idx === 2 ? 70 : 35); }
      return any;
    }

    // ---------- 연출 도우미 (줄임 모드·저사양에서는 흔들림·줌·번쩍임을 줄인다) ----------
    const fxs = [], later_ = [];
    function later(dt, fn) { later_.push({ t: dt, fn }); }
    const shk = v => { if (!E.reduced) E.shake = Math.max(E.shake, v * (E.low ? 0.7 : 1)); };
    const hs = v => { if (!E.reduced) E.hitstop = Math.max(E.hitstop, v); };
    const flashS = (a, col) => { if (!E.reduced) { E.flash = Math.max(E.flash, a); E.flashCol = col || '#fff'; } };
    function zoomAt(v) { if (E.reduced || E.low) return; if (E.zoom < 0.012) { E.zax = P.x - E.cam; E.zay = P.y - 24; } E.zoom = Math.max(E.zoom, v); }
    function dimTo(a, col, hold) { if (E.reduced || a <= 0) return; E.dimGoal = Math.max(E.dimGoal, a); E.dimCol = col; E.dimHold = Math.max(E.dimHold, hold); }
    function fxPush(f, id) {
      if (fxs.length >= 56) { let k = -1; for (let i = 0; i < fxs.length; i++) if (!fxs[i].big) { k = i; break; } fxs.splice(k < 0 ? 0 : k, 1); }
      fxs.push(f);
      if (id) { const L = E.castLog[id] || (E.castLog[id] = { n: 0, kinds: {}, call: '', col: '', size: 0, fx: 0 }); L.kinds[f.k + (f.sh ? ':' + f.sh : '')] = 1; L.fx++; }
      return f;
    }
    const tc = {};
    function tinted(im, col) {   // 그림 모양 그대로 한 가지 색으로 칠한 사본(불=주황 · 감전=노랑). 같은 그림·색은 한 번만 만든다
      if (!hasDoc || !im || !im.src || !im.width) return null;
      const k = im.src + col; let c = tc[k]; if (c) return c;
      c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const x = c.getContext('2d');
      x.drawImage(im, 0, 0); x.globalCompositeOperation = 'source-atop'; x.fillStyle = col; x.fillRect(0, 0, c.width, c.height);
      return tc[k] = c;
    }

    // ---------- 이름 콜아웃 (스킬 쓰는 순간 화면에 큰 글자로) ----------
    const callouts = [];
    function callout(s) {
      const v = SKV[s.id]; if (!v) return;
      if (INS && INS.phase === 'total') return;   // 클랜 보스 「총 피해」 장면 위로는 스킬 글자를 띄우지 않는다
      let sub = false;
      for (const c of callouts) if (c.size > v.size && c.t < 0.5) sub = true;   // 더 큰 스킬 글자가 아직 떠 있으면 작게 아래 줄로
      if (!sub) for (const c of callouts) { c.life = Math.min(c.life, c.t + 0.12); }
      const k = { id: s.id, text: v.call, col: v.col, dark: v.dark, size: v.size, scale: 1 + Math.min(0.3, Math.max(0, (s.lv || 1) - 1) * 0.03), t: 0, life: 0.5 + v.size * 0.14, sub, max: (s.lv || 1) >= 10 };
      callouts.push(k); while (callouts.length > 2) callouts.shift();
      const L = E.castLog[s.id] || (E.castLog[s.id] = { n: 0, kinds: {}, call: '', col: '', size: 0, fx: 0 }); L.n++; L.call = v.call; L.col = v.col; L.size = v.size;
      emit('callout', { id: s.id, text: v.call, col: v.col, size: v.size });
    }

    // ---------- 스킬 ----------
    function trySkill(i) {
      const s = skills[i];
      if (!s || s.passive) return false;
      if (P.dead || P.cast || P.hurtT > 0 || slotCd[i] > 0 || P.mp < s.mp || (boss && (boss.state === 'intro' || boss.state === 'total')) || (INS && INS.noCtl && !boss)) return false;
      P.mp -= s.mp; slotCd[i] = s.cd; P.cast = { i, s, t: 0, dur: s.cast, fired: false }; P.atkT = 0; P.struck = true;
      if (P.on) P.vx *= 0.25;
      P.castFlash = 1;
      const v = SKV[s.id] || SKV.slash, big = v.size >= 3, quiet = E.t < E.bigUntil && !big;
      callout(s);
      telegraph(s, v, quiet);
      E.usingId = s.id; E.usingT = s.cast + 0.35;
      emit('skill', { id: s.id, col: v.col, size: v.size, call: v.call, dur: s.cast, lv: s.lv });
      emit('cast', { id: s.id, stage: 'pre' });
      return true;
    }
    // 전조: 마법진 · 기를 모으는 빛 · (큰 스킬은) 하늘이 어두워지고 화면이 살짝 멈췄다 당겨진다
    function telegraph(s, v, quiet) {
      const r = SZ_R[v.size] || 22, col = s.col, big = v.size >= 3;
      fxPush({ k: 'circle', id: s.id, x: P.x, y: P.y, r, col, t: 0, life: s.cast + 0.4, big }, s.id);
      ring(P.x, P.y - 4, col, r, s.cast * 0.9);
      newPart('glow', P.x, P.y - 18, 0, 0, s.cast + 0.15, 30 + v.size * 12, col);
      const n = E.low ? 3 : 4 + v.size * 3;
      for (let k = 0; k < n; k++) { const a = rnd() * 6.283, d = r * 1.5 + 18 + rnd() * 14, p = newPart('conv', P.x, P.y - 20, Math.cos(a) * d, Math.sin(a) * d * 0.8, s.cast * 0.85 + 0.05, 2.2 + rnd() * 1.8, col); if (p) { p.a = P.x; p.b = P.y - 20; } }
      if (s.id === 'bomb') { const t = nearestMob(s.range, 60, true), tx = t ? t.x : P.x + P.face * s.range * 0.5; fxPush({ k: 'reticle', x: tx, y: t ? t.y : P.y, r: clamp(s.range * 0.32, 52, 92), col, t: 0, life: s.cast + 0.2 }, s.id); }
      if (!quiet) { if (big) { hs(0.05); zoomAt(v.zoom * 0.55); } if (v.dim) dimTo(v.dim * 0.7, v.dimCol, s.cast + 0.9); }
    }
    function nearestMob(maxDx, maxDy, forward) {
      let best = null, bd = 1e9;
      for (const m of mobs) {
        if (!liveMob(m)) continue; const dx = m.x - P.x; if (Math.abs(dx) > maxDx || Math.abs(m.y - P.y) > maxDy) continue;
        const d = Math.abs(dx) + (forward && dx * P.face < 0 ? 140 : 0); if (d < bd) { bd = d; best = m; }
      }
      return best;
    }
    function fireSkill(s) {
      const f = P.face, col = s.col, v = SKV[s.id] || SKV.slash, big = v.size >= 3, quiet = E.t < E.bigUntil && !big;
      if (big) E.bigUntil = E.t + 0.9;
      P.afterT = 0.34; P.afterCol = col; P.afterId = s.id;
      if (quiet) shk(1.2); else { shk(v.shake * 0.45); zoomAt(v.zoom); if (v.lines && !E.low) { E.lines = 1; E.linesCol = col; } }
      emit('cast', { id: s.id, stage: 'fire' });
      const dmg = (m, extra) => hitMob(m, s.mult, Object.assign({ skill: s.id, col, kb: v.hit === 'push' ? 150 : 90, fromX: P.x }, extra || {}));
      const sf = (name, x, y, w, o) => fxPush(Object.assign({ k: 'sf', sh: name, x, y, w, t: 0, life: 0.4, col, big }, o || {}), s.id);
      if (s.shape === 'arc') {
        if (s.id === 'spin') {
          sf('sk_spin', P.x, P.y - 20, s.range * 3.0, { life: 0.52, spinr: 1, sq: 0.62 });
          fxPush({ k: 'spin', id: s.id, x: P.x, y: P.y - 18, face: f, t: 0, life: 0.5, col, r: s.range, big }, s.id);
          fxPush({ k: 'wind', x: P.x, y: P.y - 18, t: 0, life: 0.55, col, r: s.range, big }, s.id);
          for (let k = 0; k < 4; k++) later(k * 0.09, () => { if (!P.dead) { const g = newPart('ghost', P.x, P.y, 0, 0, 0.2, 0, col); if (g) g.a = (k % 2 ? -1 : 1); } });
        } else {
          sf('sk_slash', P.x + f * s.range * 0.55, P.y - 20, s.range * 2.7, { life: 0.34, rot: f * -0.3, flip: f < 0 });
          fxPush({ k: 'arc', id: s.id, x: P.x, y: P.y - 18, face: f, t: 0, life: s.hits > 1 ? 0.5 : 0.32, col, r: s.range, big }, s.id);
          fxPush({ k: 'glint', x: P.x + f * s.range * 0.5, y: P.y - 22, t: 0, life: 0.26, col }, s.id);
          P.vx += f * 140;
        }
        for (let k = 0; k < s.hits; k++) later(k * 0.09, () => { const b = frontBox(s.range, s.both, true); for (const m of mobsInBox(b[0], b[1], b[2], b[3], 6)) dmg(m); });
      } else if (s.shape === 'proj') {
        if (s.id === 'fire') { sf('sk_fire', P.x + f * s.range * 0.5, P.y - 18, s.range * 1.15, { life: 0.5, flip: f < 0 }); fxPush({ k: 'flash', x: P.x + f * 12, y: P.y - 18, t: 0, life: 0.2, col }, s.id); P.vx -= f * 40; }
        for (let k = 0; k < s.hits; k++) later(k * 0.09, () => {
          if (P.dead) return;
          const sy = P.y - 16 - (k % 2) * 4;
          shots.push({ from: 'p', x: P.x + f * 10, y: sy, vx: f * (s.pierce ? 340 : 440), t: 0, range: s.range, mult: s.mult, col, id: s.id, pierce: s.pierce ? 10 : 3, hit: [], sk: s });
          if (s.id === 'peck') { sf('sk_peck', P.x + f * 16, sy, 46, { life: 0.22 }); P.vx += f * 16; shk(0.8); }
          emit('cast', { id: s.id, stage: 'shot' });
        });
      } else if (s.shape === 'aoe') {
        let cx, cy = P.y, r;
        if (s.both) { cx = P.x; r = Math.max(70, s.range * 0.5); }
        else { const t = nearestMob(s.range, 60, true); cx = t ? t.x : P.x + f * s.range * 0.5; cy = t ? t.y : P.y; r = clamp(s.range * 0.32, 52, 92); }
        if (s.id === 'bomb') fxPush({ k: 'drop', x: cx, y0: cy - 250, y1: cy - 8, col, t: 0, life: 0.16, big }, s.id);
        if (s.id === 'egg') fxPush({ k: 'egg', x0: P.x + f * 8, y0: P.y - 26, x1: cx, y1: cy - 6, t: 0, life: 0.16 }, s.id);
        if (s.id === 'storm') {
          sf('sk_storm', cx, cy - 20, r * 3.2, { life: 1.0, fr0: 0, grow: 1 });
          fxPush({ k: 'tornado', x: cx, y: cy, r, t: 0, life: 1.0, col, big }, s.id);
          if (!quiet) dimTo(v.dim, v.dimCol, 1.1);
        }
        if (s.id === 'thunder' && !quiet) dimTo(v.dim, v.dimCol, 0.55 + s.hits * 0.12);
        if (s.id === 'bomb' && !quiet) dimTo(v.dim, v.dimCol, 0.5);
        for (let k = 0; k < s.hits; k++) later(0.16 + k * 0.11, () => {
          fxPush({ k: 'aoe', id: s.id, x: cx, y: cy, t: 0, life: 0.5, col, r, big }, s.id);
          shk(v.shake * (k === s.hits - 1 ? 0.9 : 0.5)); hs(v.stop * 0.7);
          if (s.id === 'bomb') {
            sf('sk_bomb', cx, cy - 26, r * 4.4, { life: 0.62, fr0: 1 });
            fxPush({ k: 'crack', x: cx, y: cy, w: r * 2.2, t: 0, life: 1.3, col }, s.id);
            ring(cx, cy, col, r * 1.6, 0.5); ring(cx, cy, '#fff0c0', r * 1.0, 0.35); flashS(0.3, '#fff0c8');
            for (let d = 0; d < (E.low ? 6 : 14); d++) { const a = -0.2 - rnd() * 2.7, sp = 120 + rnd() * 200; newPart('spark', cx, cy - 6, Math.cos(a) * sp, Math.sin(a) * sp, 0.4 + rnd() * 0.3, 9 + rnd() * 8, rnd() < 0.5 ? col : '#ffd28a'); }
          } else if (s.id === 'thunder') {
            const nb = E.low ? 1 : 2;
            for (let b = 0; b < nb; b++) { const bx = cx + (b ? (rnd() - 0.5) * r * 1.5 : 0); fxPush({ k: 'bolt', x: bx, y: cy, col, t: 0, life: 0.34, seed: (bx * 7 + k * 31) | 0, big }, s.id); sf('sk_thunder', bx, cy - 40, 170, { life: 0.34 }); }
            flashS(0.32, '#fffbe0'); ring(cx, cy, '#fff', r * 1.1, 0.3);
          } else if (s.id === 'egg') {
            sf('sk_egg', cx, cy - 10, r * 2.8, { life: 0.5, fr0: 2 });
            for (let d = 0; d < (E.low ? 5 : 12); d++) { const a = -rnd() * 3.14, sp = 80 + rnd() * 170; newPart('spark', cx, cy - 10, Math.cos(a) * sp, Math.sin(a) * sp - 40, 0.45 + rnd() * 0.3, 7 + rnd() * 6, rnd() < 0.5 ? '#ffd23c' : '#fff6c0'); }
            for (let d = 0; d < 3; d++) newPart('coin', cx + (rnd() - 0.5) * 30, cy - 12, (rnd() - 0.5) * 150, -170 - rnd() * 80, 6, 4.2, '#ffd23c').b = cy;
            flashS(0.22, '#ffe9a0');
          } else if (s.id === 'storm') {
            ring(cx, cy, col, r * (1.2 + k * 0.1), 0.5); flashS(0.18 + (k === s.hits - 1 ? 0.2 : 0), '#e6c8ff');
            if (!E.low) for (let d = 0; d < 6; d++) { const a = rnd() * 6.28, rr = r * (0.4 + rnd() * 0.8); newPart('spark', cx + Math.cos(a) * rr, cy - 10 + Math.sin(a) * rr * 0.4, Math.cos(a) * 60, -80 - rnd() * 120, 0.35, 10, '#e0b8ff'); }
          }
          if (s.id === 'ice') { ring(cx, cy, col, r * 0.9, 0.5); if (!E.low) for (let d = 0; d < 8; d++) newPart('spark', cx + (rnd() - 0.5) * r, cy - 10 - rnd() * 30, (rnd() - 0.5) * 60, -40 - rnd() * 60, 0.6, 9, '#c8f4ff'); for (const m of mobs) if (liveMob(m) && !m.boss && Math.abs(m.x - cx) <= r && Math.abs(m.y - cy) < 140) m.frz = 2.2; }
          if (s.id === 'meteor' && !E.low) for (let d = 0; d < 7; d++) newPart('flame', cx + (rnd() - 0.5) * r * 0.6, cy - 70 - rnd() * 40, (rnd() - 0.5) * 80, 120 + rnd() * 140, 0.5, 14, '#ff8a3a');
          if (s.id === 'phoenix') { ring(cx, cy, col, r * 0.5 * (1 + k * 0.1), 0.6); flashS(0.2, '#ffd0a0'); }
          for (const m of mobs) if (liveMob(m) && Math.abs(m.x - cx) <= r && Math.abs(m.y - cy) < 140) dmg(m, s.id === 'storm' ? { kb: k === s.hits - 1 ? 170 : -55, fromX: cx } : { kb: 60, fromX: cx });
          emit('cast', { id: s.id, stage: 'hit' });
        });
      } else if (s.shape === 'dash') {
        const dist = Math.min(s.range * 0.8, 520), dur = 0.22;
        P.dash = { t: 0, dur, vx: f * dist / dur, s, hit: [], x0: P.x }; P.inv = Math.max(P.inv, dur + 0.1);
        fxPush({ k: 'dash', id: s.id, x: P.x, y: P.y, face: f, t: 0, life: dur + 0.2, col, r: dist }, s.id);
        sf('sk_shrimp', P.x + f * 22, P.y - 16, 96, { life: 0.28, flip: f < 0 });
      } else if (s.shape === 'buff') {
        E.rageT = 8; E.rageMul = 1 + clamp((s.buff || s.mult || 35), 5, 200) / 100;
        ring(P.x, P.y - 20, col, 70, 0.5); ring(P.x, P.y - 20, '#fff0c0', 40, 0.35); flashS(0.18, '#ffb0b0');
        for (let d = 0; d < (E.low ? 5 : 12); d++) newPart('emo', P.x + (rnd() - 0.5) * 40, P.y - 20 - rnd() * 24, (rnd() - 0.5) * 60, -50 - rnd() * 60, 0.8, 13, '💢');
        say('공격력 UP!', P.x, P.y - PH - 14, 'h', 16, '#ff9a9a');
      } else if (s.shape === 'blink') {
        const dist = Math.min(s.range, 520), tx = P.x + f * dist;
        const lo = P.on ? P.plat.x0 + 10 : 12, hi = P.on ? P.plat.x1 - 10 : map.W - 12;
        for (let k = 0; k < 6; k++) { const g = newPart('ghost', P.x + f * k * dist / 6, P.y, 0, 0, 0.3 + k * 0.03, 0, col); if (g) g.a = f; }
        P.x = clamp(tx, lo, hi); P.inv = Math.max(P.inv, 0.7);
        ring(P.x, P.y - 18, col, 60, 0.4); for (let d = 0; d < (E.low ? 4 : 10); d++) newPart('spark', P.x + (rnd() - 0.5) * 30, P.y - 10 - rnd() * 30, (rnd() - 0.5) * 120, -60 - rnd() * 80, 0.5, 8, col);
      } else if (s.shape === 'pull') {
        ring(P.x, P.y - 20, col, s.range * 0.6, 0.5); ring(P.x, P.y - 20, '#fff', s.range * 0.3, 0.35);
        for (let k = 0; k < s.hits; k++) later(0.12 + k * 0.14, () => {
          for (const m of mobs) if (liveMob(m) && !m.boss && Math.abs(m.x - P.x) <= s.range && Math.abs(m.y - P.y) < 70) {
            m.kb += (P.x > m.x ? 1 : -1) * (m.big ? 120 : 330);
            hitMob(m, s.mult, { skill: s.id, col, kb: 0, fromX: m.x - (P.x > m.x ? 1 : -1) * 10 });
          }
        });
      } else if (s.shape === 'self') {
        const heal = Math.round(P.hpMax * clamp(s.mult / 100 * 0.12, 0.05, 0.5));
        P.hp = Math.min(P.hpMax, P.hp + heal); P.shieldT = 3;
        say('+' + fmtNum(heal), P.x, P.y - PH - 8, 'h', 15, '#7dff9a');
        sf('sk_shield', P.x, P.y - 16, 150, { life: 0.6 });
        fxPush({ k: 'dome', x: P.x, y: P.y, r: 64, t: 0, life: 0.6, col, big }, s.id);
        ring(P.x, P.y - 4, col, 80, 0.5); flashS(0.12, '#bfe0ff');
        for (const m of mobs) if (liveMob(m) && !m.boss && Math.abs(m.x - P.x) < 86 && Math.abs(m.y - P.y) < 60) { m.kb += (m.x >= P.x ? 1 : -1) * 190; m.fxk = 'push'; m.fxt = 0.3; m.fxc = col; m.fxd = m.x >= P.x ? 1 : -1; }
      }
    }

    // ---------- 병아리 갱신 ----------
    function updatePlayer(h, Ct) {
      const p = P;
      p.inv = Math.max(0, p.inv - h); p.shieldT = Math.max(0, p.shieldT - h); p.hpFlash = Math.max(0, p.hpFlash - h * 3); p.castFlash = Math.max(0, p.castFlash - h * 4);
      p.afterT = Math.max(0, p.afterT - h); p.dropT = Math.max(0, p.dropT - h); p.sq *= Math.exp(-h * 11); p.djT = Math.max(0, p.djT - h);
      if (E.rageT > 0) E.rageT = Math.max(0, E.rageT - h);
      E.usingT = Math.max(0, E.usingT - h); if (E.usingT <= 0) E.usingId = null;
      for (let i = 0; i < 8; i++) slotCd[i] = Math.max(0, slotCd[i] - h);
      if (p.dead) {
        p.deadT -= h; p.vx *= Math.exp(-h * 4); moveBody(p, h);
        if (p.deadT <= 0) revive();
        return;
      }
      // 회복: 체력 초당 1.2% · 마나 mpregen
      p.hp = Math.min(p.hpMax, p.hp + p.hpMax * 0.012 * h); p.mp = Math.min(p.mpMax, p.mp + Math.max(0, C.mpregen) * h);
      const frozen = boss && boss.state === 'intro';
      if (frozen) Ct = NOCTL;
      if (p.hurtT > 0) { p.hurtT -= h; Ct = NOCTL; }
      // 스킬 시전 중
      if (p.cast) {
        p.cast.t += h;
        if (!p.cast.fired && p.cast.t >= p.cast.dur * 0.6) { p.cast.fired = true; fireSkill(p.cast.s); }
        if (p.cast.t >= p.cast.dur) { const cid = p.cast.s.id; p.cast = null; emit('skillend', { id: cid }); }
        if (p.on) p.vx *= Math.exp(-h * 14);
        if (p.cast) Ct = NOCTL;
      }
      // 돌진
      if (p.dash) {
        const d = p.dash; d.t += h; p.vx = d.vx; p.vy = Math.min(p.vy, 0) * 0.2;
        const b = [p.x - 16, p.x + 16, p.y - 44, p.y + 6];
        for (const m of mobsInBox(b[0], b[1], b[2], b[3], 8)) if (d.hit.indexOf(m) < 0) { d.hit.push(m); hitMob(m, d.s.mult * d.s.hits, { skill: d.s.id, col: d.s.col, kb: 160, fromX: p.x - p.face * 20 }); }
        if ((d.t % 0.04) < h) { const g = newPart('ghost', p.x, p.y, 0, 0, 0.22, 0, d.s.col); if (g) g.a = p.face; }
        if (d.s.id === 'shrimp' && (d.t % 0.05) < h) newPart('emo', p.x - p.face * 8, p.y - 18 + (rnd() - 0.5) * 22, -p.face * 70, (rnd() - 0.5) * 36, 0.4, 12, '🦐');
        if (d.t >= d.dur || (p.on && (p.x <= p.plat.x0 + 6 && p.face < 0 || p.x >= p.plat.x1 - 6 && p.face > 0))) { p.dash = null; p.vx *= 0.2; }
        moveBody(p, h);
        return;
      }
      const dir = (Ct.right ? 1 : 0) - (Ct.left ? 1 : 0);
      const swinging = p.atkT > 0;
      const maxV = RUN_V * (swinging ? 0.5 : 1);
      if (dir !== 0 && !swinging) p.face = dir;
      const acc = p.on ? ACC_G : ACC_A;
      if (dir !== 0) { const tv = dir * maxV; if (p.vx < tv) p.vx = Math.min(tv, p.vx + acc * h); else if (p.vx > tv) p.vx = Math.max(tv, p.vx - acc * h); }
      else if (p.on) { const f = FRIC_G * h; p.vx = Math.abs(p.vx) <= f ? 0 : p.vx - Math.sign(p.vx) * f; }
      else p.vx *= Math.exp(-h * 0.6);
      // 점프
      if (Ct.jump) doJump(Ct);
      else if (!Ct.jumpHeld && p.vy < -200 && !p.on) p.vy *= 0.55;   // 일찍 떼면 낮게 뛴다
      // 기본 공격 · 스킬
      for (let i = 0; i < 8; i++) if (Ct.s[i]) { if (trySkill(i)) { ED['s' + (i + 1)] = false; break; } }
      if (!p.cast) {
        if (Ct.attack && p.atkT <= 0) startSwing();
      }
      if (p.atkT > 0) {
        p.atkT -= h;
        if (!p.struck && p.atkDur - p.atkT >= p.atkDur * 0.38) { p.struck = true; strike(); }
        if (p.atkT <= 0) p.comboT = 0.5;
      } else if (p.comboT > 0) p.comboT -= h;
      // 달리기 먼지·발소리
      p.run = p.on ? Math.abs(p.vx) : 0;
      if (p.on && p.run > 60) { p.stepT -= h; if (p.stepT <= 0) { p.stepT = 0.2; dust(p.x - p.face * 4, p.y, 1, -p.face); emit('step', {}); } } else p.stepT = Math.min(p.stepT, 0.05);
      if (!p.on) p.airT += h;
      moveBody(p, h);
    }
    const NOCTL = { left: false, right: false, jump: false, jumpHeld: false, down: false, attack: false, s: [false, false, false, false] };

    // =====================================================================
    //  몬스터
    // =====================================================================
    function aliveCount() { let n = 0; for (let i = 0; i < mobs.length; i++) if (mobs[i].st !== 'dying' && !mobs[i].boss) n++; return n; }
    function spawnMob(forceX, forcePlat, o) {
      o = o || {};
      let plat = forcePlat || null, x = forceX;
      if (!plat) {
        for (let tr = 0; tr < 14 && !plat; tr++) {
          const near = o.wave ? rnd() < 0.85 : rnd() < SPAWN_NEAR;   // 일부는 지금 서 있는 발판 위에서 나온다(몰려오는 맛), 나머지는 다른 층·먼 곳
          const dir = rnd() < 0.5 ? -1 : 1;
          let tx, cands;
          if (near) {
            const cp = map.plats[P.on ? P.plat.id : P.lastPlat], hp = cp.kind === 'block' ? map.plats[0] : cp;
            const lo = Math.max(hp.x0 + 14, P.x - 150), hi = Math.min(hp.x1 - 14, P.x + 150);
            // 병아리에게서 55 이상 떨어진, 같은 발판 위의 자리(한쪽이 막혔으면 반대쪽)
            const gap = o.wave ? 110 : 55, sides = []; if (P.x + gap <= hi) sides.push([Math.max(lo, P.x + gap), hi]); if (P.x - gap >= lo) sides.push([lo, Math.min(hi, P.x - gap)]);
            if (!sides.length) continue;
            const sd = sides[(rnd() * sides.length) | 0]; tx = sd[0] + rnd() * (sd[1] - sd[0]); cands = [hp];
            if (hp.kind === 'floor' && blockBetween(P.x, tx)) continue;   // 바로 앞에 블록이 가로막은 곳엔 안 나온다
          } else {
            if (o.wave) { tx = P.x + (rnd() < 0.5 ? -1 : 1) * (120 + rnd() * 380); if (tx < 50 || tx > map.W - 50) continue; }   // 웨이브는 병아리 좌우 넓은 구간에 흩어져 나온다(앞에 딱 붙지 않게)
            else { const dist = MOB_BAND[0] + rnd() * (MOB_BAND[1] - MOB_BAND[0]);
            tx = P.x + dir * dist; if (tx < 40 || tx > map.W - 40) tx = P.x - dir * dist; if (tx < 40 || tx > map.W - 40) continue; }
            cands = map.spawnPlats.filter(q => tx >= q.x0 + 14 && tx <= q.x1 - 14);
          }
          if (!cands.length) continue;
          const q = cands[(rnd() * cands.length) | 0];
          if (q.kind === 'floor') { const pk = pocket(map, q, tx); if (tx < pk[0] + 6 || tx > pk[1] - 6) continue; }
          let clash = false; for (const m of mobs) if (m.st !== 'dying' && Math.abs(m.x - tx) < 28 && Math.abs(m.y - q.y) < 30) { clash = true; break; }
          if (clash) continue;
          plat = q; x = tx;
        }
      }
      if (!plat) return null;
      if (plat.kind === 'floor' && map.blocks.some(b => x > b.x0 - 12 && x < b.x1 + 12)) return null;   // 블록 속에는 안 나온다
      const el = o.el != null ? o.el : rnd() < 0.07;
      const r = rnd();
      const fly = o.fly != null ? o.fly : (!el && r < 0.18), shoot = o.shoot != null ? o.shoot : (!fly && !el && r > 0.86);
      const pk = plat.kind === 'floor' ? pocket(map, plat, x) : [plat.x0 + 8, plat.x1 - 8];
      const m = {
        id: E.uid++, x, y: plat.y, st: 'spawn', t: 0, plat, lo: pk[0], hi: pk[1], dir: rnd() < 0.5 ? -1 : 1, face: 1, hp: 1, max: 1, hit: 0, kb: 0, sqz: 0, ph: rnd() * 6,
        sp: 28 + rnd() * 18, el, sc: el ? 1.35 : 0.9 + rnd() * 0.2, fly, shoot, pause: 0, turnT: 1.5 + rnd() * 3, shootCd: 1.5 + rnd() * 2, charge: 0, boss: false, chaseT: 0,
        dvx: 0, dvy: 0, drot: 0, rot: 0, baseY: plat.y - (22 + rnd() * 24), ax: x, fxk: '', fxt: 0, fxa: 0, fxc: '#fff', fxd: 1
      };
      m.max = m.hp = Math.max(1, D.mobHp * (el ? 2.6 : 1) * (0.9 + rnd() * 0.2));
      if (fly) { m.y = m.baseY; m.lo = Math.max(30, x - 120); m.hi = Math.min(map.W - 30, x + 120); }
      mobs.push(m);
      poof(m.x, m.y - 12 * m.sc, 'rgba(255,255,255,.9)', 3, 40);
      if (!o.noPack && !forceX && !el && (o.wave ? rnd() < 0.45 : plat === (map.plats[P.on ? P.plat.id : P.lastPlat] || plat) && rnd() < PACK_P) && aliveCount() < MAX_MOBS) {
        // 무리: 같은 발판에서 바로 옆에 한두 마리 더
        const n = 2 + (rnd() < 0.6 ? 1 : 0);
        for (let i = 1; i <= n; i++) { const px = x + (rnd() < 0.5 ? -1 : 1) * (13 + rnd() * 7) * i; if (px > pk[0] + 4 && px < pk[1] - 4) { const q = spawnMob(px, plat, { noPack: true, el: false, fly: false, shoot: false }); if (q) { q.sp = m.sp; q.dir = m.dir; } } }
      }
      return m;
    }
    // ====== 👹 엘리트 소환(2026-11-07 사장님 「던전 입장이 아니라 지금 사냥 중인 필드에 대형 몬스터 하나가 소환」) ======
    //   server 가 게이지 한 칸을 쓰고 id 를 주면 여기서 큰 몬스터를 지금 서 있는 곳 옆에 세운다. 쓰러뜨리면 'elitedie', 시간이 지나면 'eliteexpire'.
    function summonElite(o) {
      o = o || {};
      if (boss || INS || (E.elite && E.elite.st !== 'dying')) return false;
      const cp = map.plats[P.on ? P.plat.id : P.lastPlat] || map.plats[0], hp = cp.kind === 'block' ? map.plats[0] : cp;
      let x = P.x + (P.face >= 0 ? 1 : -1) * 150; if (x < hp.x0 + 40 || x > hp.x1 - 40) x = P.x - (P.face >= 0 ? 1 : -1) * 150;
      x = clamp(x, hp.x0 + 40, hp.x1 - 40);
      const m = spawnMob(x, hp, { noPack: true, el: false, fly: false, shoot: false });
      if (!m) return false;
      m.big = true; m.eid = o.id; m.name = String(o.name || '엘리트'); m.sc = 2.7; m.sp *= 0.7; m.pause = 0; m.turnT = 99;
      m.hpMult = N(o.hpMult) > 0 ? N(o.hpMult) : 22; m.max = m.hp = Math.max(1, D.mobHp * m.hpMult);
      m.st = 'spawn'; m.t = -0.5;
      const left = N(o.ttl) > 0 ? N(o.ttl) : 180;
      E.elite = m; m.t0 = E.t; m.ttl = left;
      ring(m.x, m.y - 10, '#ff5c7a', 190, 0.8); ring(m.x, m.y - 10, '#ffd23c', 120, 0.6);
      poof(m.x, m.y - 30, '#ff8aa0', 18, 240); newPart('flash', m.x, m.y - 40, 0, 0, 0.45, 150, '#ff6a8a');
      E.shake = Math.max(E.shake, 9); flashS(0.3, '#ff5c7a'); E.hitstop = Math.max(E.hitstop, 0.1);
      say('엘리트 출현!', m.x, m.y - 100, 'c', 28, '#ff5c7a');
      emit('elitespawn', { id: m.eid, name: m.name });
      return true;
    }
    function expireElite() {
      const m = E.elite; if (!m) return; E.elite = null;
      if (m.st !== 'dying') { m.st = 'dying'; m.t = 0; m.dvx = 0; m.dvy = -60; m.drot = 0; m.dz = m.y; poof(m.x, m.y - 30, '#cfd6ff', 14, 160); say('도망쳤다…', m.x, m.y - 90, 'n', 18, '#cfd6ff'); }
      emit('eliteexpire', { id: m.eid });
    }
    // ✨ 드랍 연출 — 등급이 높을수록 화려하다: 일반=톡 튀어나옴 · 레어=파란 빛 · 에픽=보라 빛기둥 · 유니크=금빛 폭죽+번쩍 · 레전드=무지개 빛기둥·화면 번쩍·슬로모션
    const DROP_COL = ['#d6dcf0', '#6fb6ff', '#c58bff', '#ffb64a', '#ff5f8d'];
    function dropFx(o) {
      o = o || {}; const rar = clamp(o.rar | 0, 0, 4), x = o.x != null ? o.x : P.x, y = o.y != null ? o.y : P.y, col = DROP_COL[rar], by = y - 18;
      const it = newPart('item', x, by - 20, (rnd() - 0.5) * 50, -330 - rar * 30, 3.2 + rar * 0.5, 30 + rar * 8, o.emoji || '🎁');
      if (it) { it.b = y; it.g = col; it.rar = rar; }
      ring(x, y - 6, col, 60 + rar * 30, 0.5);
      if (rar >= 1) { newPart('flash', x, by, 0, 0, 0.4, 70 + rar * 22, col); for (let i = 0; i < 6 + rar * 4; i++) newPart('star', x, by, (rnd() - 0.5) * 260, -80 - rnd() * 200, 0.9 + rnd() * 0.5, 10 + rnd() * 8, col); }
      if (rar >= 2) { const b = newPart('beam', x, y + 2, 0, 0, 1.6, 34 + rar * 10, col); ring(x, y - 6, col, 130, 0.7); E.shake = Math.max(E.shake, 4 + rar); flashS(0.12 + rar * 0.04, col); }
      if (rar >= 3) { newPart('beam', x, y + 2, 0, 0, 2.2, 70, '#fff6c0'); ring(x, y - 6, '#fff', 190, 0.9); ring(x, y - 6, col, 240, 1.0); for (let i = 0; i < 22; i++) newPart('star', x, by, (rnd() - 0.5) * 520, -140 - rnd() * 320, 1.2 + rnd() * 0.8, 9 + rnd() * 10, i % 2 ? '#fff6c0' : col); E.slow = Math.max(E.slow, 0.5); E.hitstop = Math.max(E.hitstop, 0.1); flashS(0.35, '#fff6c0'); E.shake = Math.max(E.shake, 8); }
      if (rar >= 4) {
        const RB = ['#ff5f8d', '#ffb64a', '#fff27a', '#5cf0a0', '#6fb6ff', '#c58bff'];
        for (let i = 0; i < 6; i++) newPart('beam', x + (i - 2.5) * 22, y + 2, 0, 0, 2.6 + i * 0.1, 26, RB[i]);
        for (let k = 0; k < 3; k++) ring(x, y - 6, RB[k * 2], 280 + k * 80, 1.1 + k * 0.25);
        for (let i = 0; i < 44; i++) newPart('star', x, by, (rnd() - 0.5) * 760, -180 - rnd() * 420, 1.4 + rnd() * 1.1, 10 + rnd() * 12, RB[i % 6]);
        newPart('flash', x, by, 0, 0, 0.9, 340, '#ffffff'); E.slow = Math.max(E.slow, 1.0); E.shake = Math.max(E.shake, 12); flashS(0.7, '#ffffff'); E.zoom = Math.max(E.zoom, 0.07);
        say('✨ 레전드 득템!', x, y - 110, 'c', 32, '#ffe27a');
      } else if (rar >= 3) say('유니크 득템!', x, y - 100, 'c', 28, '#ffb64a');
      else if (rar >= 2) say('에픽 득템!', x, y - 90, 'c', 24, '#c58bff');
      emit('dropfx', { rar });
    }
    function updateSpawn(h) {
      if (E.elite && E.t - E.elite.t0 > E.elite.ttl) expireElite();
      if (E.spawnT > 1e8) return;                                   // 시험·연출이 리젠을 멈춘 동안
      const cap = E.low ? Math.min(MAX_MOBS, 9) : MAX_MOBS;
      if (E.waveQ > 0) {                                           // 웨이브 진행 중 — 짧은 간격으로 쏟아져 나온다
        E.spawnT -= h; if (E.spawnT > 0) return;
        E.spawnT = 0.04; E.waveQ--;
        if (aliveCount() < cap) spawnMob(undefined, undefined, { wave: true });
        return;
      }
      const alive = aliveCount();
      if (alive <= WAVE_LOW || (E.t - (E.waveAt || 0) > WAVE_MAXGAP && alive < cap - 6) || (E.t - (E.lastKillT || 0) > 3 && E.t - (E.waveAt || 0) > 4 && alive < cap - 8)) {   // 거의 다 잡았다(또는 너무 오래 안 나왔다) → 잠깐 쉬었다가 한꺼번에
        if (E.waveWait == null || E.waveWait < 0) E.waveWait = (WAVE_DELAY[0] + rnd() * (WAVE_DELAY[1] - WAVE_DELAY[0])) * clamp(1 / Math.sqrt(Math.max(0.3, D.ratio || 1)), 0.4, 1.5);   // 전투력이 세면 웨이브 사이 쉬는 시간이 짧다
        E.waveWait -= h;
        if (E.waveWait <= 0) { E.waveQ = Math.max(1, Math.min(WAVE_SIZE, cap - alive)); E.waveWait = -1; E.spawnT = 0; E.waveAt = E.t; }
      } else E.waveWait = -1;
    }
    function updateMobs(h) {
      const pbx0 = P.x - PW, pbx1 = P.x + PW, pby0 = P.y - PH, pby1 = P.y;
      for (let i = mobs.length - 1; i >= 0; i--) {
        const m = mobs[i];
        m.hit = Math.max(0, m.hit - h); m.sqz *= Math.exp(-h * 9);
        if (m.fxt > 0) {
          m.fxt -= h;
          if (m.fxk === 'burn' && m.st !== 'dying' && (m.fxa += h) > (E.low ? 0.12 : 0.06)) { m.fxa = 0; newPart('flame', m.x + (rnd() - 0.5) * 12 * m.sc, m.y - (6 + rnd() * 20) * m.sc, (rnd() - 0.5) * 20, -42 - rnd() * 40, 0.4 + rnd() * 0.25, 4 + rnd() * 4, rnd() < 0.5 ? '#ff7a2a' : '#ffb03a'); }
          else if (m.fxk === 'gold' && (m.fxa += h) > 0.09) { m.fxa = 0; newPart('star', m.x + (rnd() - 0.5) * 18, m.y - (4 + rnd() * 26) * m.sc, 0, -20, 0.3, 7, '#ffe27a'); }
        }
        if (m.st === 'boss') continue;
        if (m.st === 'dying') {
          m.t += h; m.x += m.dvx * h; m.dvy += GRAV * 0.8 * h; m.y += m.dvy * h; m.rot += m.drot * h;
          if (m.t > 0.75) mobs.splice(i, 1);
          continue;
        }
        if (m.st === 'spawn') { m.t += h; if (m.t >= 0.35) { m.st = 'patrol'; m.t = 0; } continue; }
        // 넉백
        if (Math.abs(m.kb) > 1) { m.x += m.kb * h; m.kb *= Math.exp(-h * 7); } else m.kb = 0;
        if (m.frz > 0) { m.frz -= h; if (!E.low && rnd() < 0.2) newPart('spark', m.x + (rnd() - 0.5) * 14, m.y - rnd() * 24, 0, -20, 0.4, 6, '#c8f4ff'); continue; }   // 🧊 얼면 못 움직이고 못 때린다
        const dx = P.x - m.x, adx = Math.abs(dx);
        if (m.fly) {
          m.ph += h * 3;
          const near = !P.dead && adx < 260 && Math.abs((P.y - 14) - m.y) < 120;
          if (near) { const tx = P.x, ty = P.y - 16 + Math.sin(m.ph) * 8; m.x += clamp(tx - m.x, -1, 1) * 52 * h; m.y += clamp(ty - m.y, -1, 1) * 40 * h; m.face = dx >= 0 ? 1 : -1; m.st = 'chase'; }
          else {
            m.st = 'patrol'; m.x += m.dir * 22 * h; if (m.x < m.lo) m.dir = 1; if (m.x > m.hi) m.dir = -1;
            const ty = m.baseY + Math.sin(m.ph) * 6; m.y += clamp(ty - m.y, -30 * h, 30 * h); m.face = m.dir;
          }
          m.x = clamp(m.x, 20, map.W - 20); m.y = clamp(m.y, 50, GY);
        } else {
          let v = 0;
          const sameLevel = !P.dead && Math.abs(P.y - m.y) < 50 && adx < AGGRO;
          if (m.charge > 0) { m.charge -= h; if (m.charge <= 0) fireShot(m); }
          else if (sameLevel && (m.st === 'chase' || adx < AGGRO - 40)) { m.st = 'chase'; m.chaseT = 1.6; v = Math.sign(dx) * m.sp * CHASE_K; m.face = dx >= 0 ? 1 : -1; if (adx < 8) v = 0; }
          else {
            if (m.st === 'chase') { m.chaseT -= h; if (m.chaseT <= 0) m.st = 'patrol'; }
            if (m.pause > 0) m.pause -= h;
            else { v = m.dir * m.sp; m.turnT -= h; if (m.turnT <= 0) { m.turnT = 2 + rnd() * 3.5; if (rnd() < 0.5) m.dir = -m.dir; else m.pause = 0.6 + rnd() * 1.2; } }
            m.face = m.dir;
          }
          if (m.shoot && m.charge <= 0) {
            m.shootCd -= h;
            if (m.shootCd <= 0 && !P.dead && adx < 270 && Math.abs(P.y - m.y) < 50) { m.charge = 0.55; m.shootCd = 3 + rnd() * 1.6; m.face = dx >= 0 ? 1 : -1; v = 0; }
          }
          m.x += v * h;
          if (m.x < m.lo) { m.x = m.lo; m.dir = 1; } else if (m.x > m.hi) { m.x = m.hi; m.dir = -1; }
          m.walk = (m.walk || 0) + Math.abs(v) * h;
        }
        // 접촉
        if (!P.dead && P.inv <= 0 && overlapBoxP(m, pbx0, pbx1, pby0, pby1)) hurtPlayer(MON.atk * (m.big ? 1.9 : m.el ? 1.3 : 1), m.x);
      }
    }
    function overlapBoxP(m, x0, x1, y0, y1) { const w = 9 * m.sc, hh = 22 * m.sc; return m.x + w > x0 && m.x - w < x1 && m.y > y0 && m.y - hh < y1; }
    function fireShot(m) {
      if (shots.length > 12) return;
      const f = P.x >= m.x ? 1 : -1;
      shots.push({ from: 'e', x: m.x + f * 8, y: m.y - 14 * m.sc, vx: f * 118, t: 0, range: 360, atk: MON.atk * 0.8 });
      newPart('flash', m.x + f * 8, m.y - 14 * m.sc, 0, 0, 0.12, 14, '#ff8a8a');
    }
    function updateShots(h) {
      for (let i = shots.length - 1; i >= 0; i--) {
        const s = shots[i]; s.t += h; s.x += s.vx * h;
        let dead = Math.abs(s.vx) * s.t > s.range || s.x < 0 || s.x > map.W;
        if (!dead) for (const b of map.blocks) if (s.x > b.x0 && s.x < b.x1 && s.y > b.y) { dead = true; break; }
        if (!dead && s.from === 'e') {
          if (!P.dead && Math.abs(s.x - P.x) < PW + 4 && s.y > P.y - PH - 2 && s.y < P.y + 2 && P.inv <= 0 && !P.dash) { hurtPlayer(s.atk, s.x - Math.sign(s.vx) * 10, { k: 0.7 }); dead = true; poof(s.x, s.y, '#ff8a8a', 5, 80); }
        } else if (!dead && s.from === 'p') {
          for (const m of mobs) {
            if (!liveMob(m) || s.hit.indexOf(m) >= 0) continue;
            if (Math.abs(m.x - s.x) < 10 * m.sc + (s.sk ? 22 : 5) && s.y > m.y - 24 * m.sc - (s.sk ? 70 : 4) && s.y < m.y + (s.sk ? 40 : 6)) {
              s.hit.push(m); hitMob(m, s.mult, { skill: s.id, col: s.col, kb: 70, fromX: s.x - Math.sign(s.vx) * 20 });
              if (s.hit.length >= s.pierce) { dead = true; poof(s.x, s.y, s.col, 6, 100); ring(s.x, s.y, s.col, 24, 0.25); break; }
            }
          }
          if (!dead && s.id === 'fire') { if (((s.t * 60) | 0) % 2 === 0) newPart('flame', s.x - Math.sign(s.vx) * 8, s.y + (rnd() - 0.5) * 8, -Math.sign(s.vx) * 24, -14 - rnd() * 24, 0.32, 5 + rnd() * 3, rnd() < 0.5 ? '#ff7a2a' : '#ffb03a'); }
          else if (!dead && ((s.t * 1000) | 0) % 3 === 0) newPart('dot', s.x, s.y + (rnd() - 0.5) * 4, 0, 0, 0.22, 2.4, s.col);
        }
        if (dead) shots.splice(i, 1);
      }
    }

    // =====================================================================
    //  AUTO — 같은 규칙(쿨·MP·점프 거리)으로 발판을 오가며 사냥한다
    // =====================================================================
    const AI = { left: false, right: false, jump: false, jumpHeld: false, down: false, attack: false, s: [false, false, false, false], tgt: null, rethink: 0, hop: null, holdJ: 0, waitT: 0, stuckT: 0, lastX: 0, cd: 0, goalPlat: -1, idleT: 0, teleports: 0, wasAuto: true };
    function mobGoal(m) { return m.fly ? platBelow(map, m.x, m.y).id : m.plat.id; }
    function curPlat() { return P.on ? P.plat.id : P.lastPlat; }
    function pickTarget() {
      const cur = curPlat(); let best = null, bc = 1e9;
      for (const m of mobs) {
        if (!liveMob(m) || m.boss) continue;
        const g = mobGoal(m), dx = Math.abs(m.x - P.x);
        let c;
        if (g === cur) c = dx + Math.abs(m.y - P.y) * 0.6; else { const d = map.dist[cur][g]; if (d >= 1e9) continue; c = d + dx * 0.5 + 100; }
        if (g === cur && P.y > map.plats[0].y - 2 && blockBetween(P.x, m.x)) c += 160;
        if (m === AI.tgt) c *= 0.75;
        if (c < bc) { bc = c; best = m; }
      }
      return best;
    }
    function walkTo(x, tol) {
      let d = 0; if (P.x < x - tol) { AI.right = true; d = 1; } else if (P.x > x + tol) { AI.left = true; d = -1; }
      // 앞에 블록(바닥 상자)이 있으면 부딪히기 전에 뛰어넘는다
      if (d && P.on) for (const b of map.blocks) {
        if (P.y <= b.y + 0.5) continue;
        const gapx = d > 0 ? b.x0 - (P.x + PW) : (P.x - PW) - b.x1;
        if (gapx > -2 && gapx < 14 && (d > 0 ? x > b.x0 : x < b.x1)) { aiJump(true); AI.hop2 = d; break; }
      }
    }
    function blockBetween(x1, x2) { const lo = Math.min(x1, x2), hi = Math.max(x1, x2); for (const b of map.blocks) if (b.x1 > lo && b.x0 < hi && P.y > b.y + 0.5) return true; return false; }
    function aiJump(short) { AI.jump = true; AI.jumpHeld = true; AI.holdJ = short ? 0.09 : 0.5; }
    function aiNavigate(goal, tx) {
      const a = AI, cur = curPlat();
      if (!P.on) {
        if (a.hop) { const d = a.hop.lx - P.x; if (Math.abs(d) > 3) { if (d > 0) a.right = true; else a.left = true; } }
        else { const d = a.hop2 || Math.sign(tx - P.x); if (d > 0) a.right = true; else if (d < 0) a.left = true; }
        return;
      }
      a.hop = null; a.hop2 = 0;
      if (cur === goal) { walkTo(tx, 6); return; }
      const nx = map.next[cur][goal];
      if (nx < 0) { walkTo(tx, 6); return; }
      const e = map.edgeTo(cur, nx), A = map.plats[cur], B = map.plats[nx];
      let jx = e.jx, lx = e.lx, act = e.act, wdir = 0;
      if (e.dyn === 'toBlock') { const left = P.x < (B.x0 + B.x1) / 2; jx = left ? B.x0 - 14 : B.x1 + 14; lx = left ? B.x0 + 10 : B.x1 - 10; if (A.id !== 0 && A.kind !== 'floor') return walkTo(tx, 6); }
      else if (e.dyn === 'fromBlock') { wdir = tx >= (A.x0 + A.x1) / 2 ? 1 : -1; jx = wdir > 0 ? A.x1 - 4 : A.x0 + 4; }
      const dx = jx - P.x;
      if (act === 'walk' || e.dyn === 'fromBlock') {
        const dir = wdir || Math.sign(lx - jx) || 1;
        if (e.dyn === 'fromBlock' || Math.abs(dx) < 3 || (dir > 0 ? P.x > jx : P.x < jx)) { if (dir > 0) a.right = true; else a.left = true; a.hop2 = dir; }
        else walkTo(jx, 2);
        return;
      }
      if (Math.abs(dx) > 3) { walkTo(jx, 2); return; }
      a.hop = { lx, to: nx };
      if (act === 'drop') { a.down = true; a.jump = true; } else aiJump();
    }
    function aiThink(h) {
      const a = AI;
      a.left = a.right = a.jump = a.down = a.attack = false; a.s[0] = a.s[1] = a.s[2] = a.s[3] = false;
      if (a.holdJ > 0) { a.holdJ -= h; a.jumpHeld = a.holdJ > 0; } else a.jumpHeld = false;
      if (P.dead || P.cast || P.hurtT > 0 || P.dash) return;
      if (boss) return aiBoss(h);
      if (P.on) { a.hop = null; a.hop2 = 0; }
      a.rethink -= h;
      if (a.rethink <= 0 || !a.tgt || !liveMob(a.tgt)) { a.tgt = pickTarget(); a.rethink = 0.35; }
      const t = a.tgt;
      // 앞(사거리 안)에 적이 있으면 서서 때린다. 뒤에 있으면 몸부터 돌린다.
      const fb = frontBox(REACH, false), fe = frontBox(REACH + 18, false);
      // 사거리 안에 있거나, 달려오고 있어서 곧 닿을 놈이 있으면 휘두른다(허공 휘두르기를 막으려고 쫓아오는 놈만 미리 본다)
      const inFront = mobsInBox(fb[0], fb[1], fb[2], fb[3], 1).length > 0 || (P.emptyRun || 0) < 2 && mobsInBox(fe[0], fe[1], fe[2], fe[3], 6).some(m => m.st === 'chase' && !m.fly && (P.x - m.x) * P.face < 0 && m.charge <= 0);
      let behind = null;
      if (inFront) { a.attack = true; a.waitT = 0; }
      else { const bb = frontBox(REACH - 6, true); behind = mobsInBox(bb[0], bb[1], bb[2], bb[3], 1)[0] || null; if (behind) { if (behind.x > P.x) a.right = true; else a.left = true; } }
      // 스킬
      if (!P.cast) for (let i = 0; i < 8; i++) { const s = skills[i]; if (s && !s.passive && slotCd[i] <= 0 && P.mp >= s.mp && skillWanted(s)) { a.s[i] = true; break; } }
      if (!inFront && !behind) {
        if (!t) { a.idleT += h; if (a.idleT > 1) walkTo(map.W / 2, 60); }
        else {
          a.idleT = 0;
          const goal = mobGoal(t), cur = curPlat();
          if (P.on && cur === goal) {
            const ok = Math.abs(t.y - P.y) < 40 || t.fly, dxt = t.x - P.x;
            if (!ok) aiNavigate(goal, t.x);
            else if (t.st === 'chase' && Math.abs(dxt) < 85 && P.on && a.waitT < 0.6 && !blockBetween(P.x, t.x)) { a.waitT += h; if (dxt * P.face < 0) { if (dxt > 0) a.right = true; else a.left = true; } }   // 달려오는 놈은 잠깐 기다린다
            else { walkTo(t.x, REACH * 0.55); if (Math.abs(dxt) > 200 || !t.fly && t.st !== 'chase') a.waitT = 0; }
          } else aiNavigate(goal, t.x);
        }
      }
      // 막힘 · 걸림 해소
      const want = a.left || a.right;
      if (a.left && a.right) { a.left = a.right = false; }
      if (want && P.on && Math.abs(P.x - a.lastX) < 0.15) a.stuckT += h; else a.stuckT = Math.max(0, a.stuckT - h * 2);
      a.lastX = P.x;
      if (a.stuckT > 0.3 && P.on && !a.jump) { aiJump(); a.stuckT = 0.1; a.stuckN = (a.stuckN || 0) + 1; if (a.stuckN > 12) { teleportHome(); a.stuckN = 0; } }
      if (!want) a.stuckN = 0;
    }
    function teleportHome() { AI.teleports++; resetPlayerPos(map.spawnX); AI.hop = null; }
    function skillWanted(s) {
      if (boss && boss.state !== 'fight') return false;
      switch (s.shape) {
        case 'arc': { const b = frontBox(s.range, s.both, true); return mobsInBox(b[0], b[1], b[2], b[3], 6).length >= (s.hits > 1 ? 1 : 1); }
        case 'proj': { for (const m of mobs) { if (!liveMob(m)) continue; const dx = (m.x - P.x) * P.face; if (dx > 0 && dx < s.range * 0.8 && m.y > P.y - 110 && m.y - 24 * m.sc < P.y + 36) return true; } return false; }
        case 'aoe': { if (s.both) { let n = 0; for (const m of mobs) if (liveMob(m) && Math.abs(m.x - P.x) < s.range * 0.5 && Math.abs(m.y - P.y) < 130) n++; return n >= 1; } return !!nearestMob(s.range * 0.8, 40, true); }
        case 'dash': { if (!P.on) return false; const dist = Math.min(s.range * 0.8, 520); const room = P.face > 0 ? P.plat.x1 - P.x : P.x - P.plat.x0; if (room < dist * 0.7) return false; for (const m of mobs) { if (!liveMob(m)) continue; const dx = (m.x - P.x) * P.face; if (dx > 20 && dx < dist && Math.abs(m.y - P.y) < 30) return true; } return false; }
        case 'self': return P.hp < P.hpMax * 0.5;
        case 'buff': { if (E.rageT > 0) return false; let n = 0; for (const m of mobs) if (liveMob(m) && Math.abs(m.x - P.x) < 320 && Math.abs(m.y - P.y) < 80) n++; return n >= 3; }
        case 'pull': { let n = 0; for (const m of mobs) if (liveMob(m) && !m.boss && Math.abs(m.x - P.x) < s.range && Math.abs(m.y - P.y) < 70) n++; return n >= 4; }
        case 'blink': return false;
      }
      return false;
    }
    function aiBoss(h) {
      const a = AI, B = boss; if (!B) return;
      if (B.state === 'intro' || B.state === 'dying' || B.state === 'smash' || B.state === 'leave' || B.state === 'total') return;
      const bm = B.m, adx = Math.abs(bm.x - P.x);
      const fb = frontBox(REACH + 14, false);
      if (mobsInBox(fb[0], fb[1], fb[2], fb[3], 1).length) a.attack = true;
      else walkTo(bm.x, 44);
      if (bm.x > P.x && P.face < 0 && adx < 90) a.right = true; else if (bm.x < P.x && P.face > 0 && adx < 90) a.left = true;
      if (!P.cast) for (let i = 0; i < 8; i++) { const s = skills[i]; if (s && !s.passive && slotCd[i] <= 0 && P.mp >= s.mp && adx < Math.max(90, s.range * 0.7) && s.shape !== 'self' && s.shape !== 'blink') { a.s[i] = true; break; } }
      // 공격 예고: 맞아야 하는 판이 아니면 내려치는 순간에 점프로 피한다
      if (B.atk && !B.atk.done && !B.atk.hit && P.on && B.atk.t > B.atk.dur - 0.32) aiJump();
    }

    // =====================================================================
    //  보스 · 도전 던전 (옛 brjhunt_field.js 의 시간표를 새 지형 위로 옮겼다)
    //   입장(2.4초) → 전투(약 10초, 공격 예고·격노) → 마무리(승: 슬로모션·폭발 / 패: 강타). 승패는 서버가 정한다.
    // =====================================================================
    function startChallenge(b) {
      if (boss || INS || !b) return;
      const key = /^[a-z0-9_]{1,30}$/.test(String(b.img || '')) ? String(b.img) : '';
      hunt = map; mobs = []; shots = []; fxs.length = 0; later_.length = 0;
      const room = genRoom(900); map = room;
      resetPlayerPos(150); P.hp = P.hpMax; P.mp = P.mpMax; P.inv = 0; P.dead = false; P.face = 1;
      E.cam = 0;
      const bm = { id: E.uid++, x: 660, y: GY, st: 'boss', boss: true, sc: 3.2, hp: 1e12, max: 1e12, hit: 0, kb: 0, sqz: 0, face: -1, fly: false, plat: room.plats[0], t: 0 };
      mobs.push(bm);
      boss = { name: String(b.name || '보스'), img: key, hp: N(b.hp) || 1000, hpMax: N(b.hp) || 1000, target: 0, res: null, state: 'intro', t: 0, ft: 0, hit: 0, phase: 0, atk: null, atkT: 1.6, land: false, php: 1, z: 150, stage: st.stage, m: bm, startRes: b.res || null };
      if (key) ld('img/brjang/boss/' + key + '/front.png');
      st.boss = b; E.tint = 1; E.tintCol = '#ff3050';
      if (b.res === 'win' || b.res === 'lose') bossResult(b.res);
      emit('boss', { phase: 'in' });
    }
    function bossResult(r) {
      const B = boss; if (!B || B.res || (r !== 'win' && r !== 'lose')) return;
      B.res = r; B.target = r === 'win' ? 0 : B.hpMax * 0.16;
    }
    function bossWant(B) {
      const q = clamp(B.ft / (B.fightT || BF_FIGHT), 0, 1);
      if (!B.res) return Math.max(0.2, 1 - q * 0.8);
      const floor = B.res === 'win' ? 0 : 0.16;
      return 1 - (1 - floor) * (q < 1 ? 1 - Math.pow(1 - q, 1.6) : 1);
    }
    function bossAttack(B, dt) {
      const a = B.atk;
      if (!a) {
        B.atkT -= dt; if (B.atkT > 0 || B.state !== 'fight') return;
        const rain = B.phase >= 1 && rnd() < 0.5;
        const hitIt = B.res === 'lose' ? rnd() < 0.85 : B.res === 'win' ? rnd() < 0.3 : rnd() < 0.5;
        B.atk = { kind: rain ? 'rain' : 'slam', t: 0, dur: rain ? 1.0 : 0.85, hit: hitIt, pts: rain ? [P.x - 70, P.x + 10, P.x + 80].map(x => clamp(x, 40, map.W - 40)) : [P.x] };
        return;
      }
      a.t += dt;
      if (a.t >= a.dur && !a.done) {
        a.done = true; E.shake = 8; E.flash = 0.22; E.flashCol = '#ffd9a0'; emit('boss', { phase: 'slam' });
        let hitMe = false;
        for (const x of a.pts) { ring(x, P.y + 2, '#ffb070', 70, 0.45); poof(x, P.y, '#e8c9a0', 10, 130); if (!autoOn() && Math.abs(P.x - x) < 46 && P.y > GY - 24) hitMe = true; }
        if (autoOn()) hitMe = a.hit;
        if (hitMe) {
          const dmg = B.res === 'lose' ? 0.2 : 0.1; B.php = Math.max(B.res === 'lose' ? 0.05 : 0.3, B.php - dmg);
          P.hurtT = 0.3; P.vx = -P.face * 70; P.inv = 0.6; P.hpFlash = 1; E.combo = 0;
          say('-' + fmtNum(Math.round(MON.atk * 3.2 * (0.9 + rnd() * 0.2))), P.x, P.y - PH - 6, 'r', 18, '#ff5c7a'); emit('hurt', { dmg: 0 });
        } else say('회피!', P.x, P.y - PH - 6, 'm', 14, '#9be7ff');
      }
      if (a.t >= a.dur + 0.5) { B.atk = null; B.atkT = (2.3 - B.phase * 0.5) * (0.85 + rnd() * 0.3); }
    }
    function updateBoss(dt) {
      const B = boss; if (!B) return;
      B.t += dt; B.hit = Math.max(0, B.hit - dt);
      if (st.boss && st.boss.res && !B.res) bossResult(st.boss.res);
      E.cin = clamp((E.cin || 0) + ((B.state === 'intro' && B.t < BF_INTRO - 0.3) || B.state === 'dying' || B.state === 'smash' ? dt * 3.5 : -dt * 3.5), 0, 1);
      const bm = B.m;
      if (B.state === 'intro') {
        if (B.t < 0.9) B.z = 150 * Math.pow(1 - B.t / 0.9, 2);
        else {
          B.z = 0;
          if (!B.land) { B.land = true; E.shake = 11; E.flash = 0.45; E.flashCol = '#fff'; ring(bm.x, bm.y + 4, '#ffd9a0', 120, 0.6); poof(bm.x, bm.y, '#d9c3a0', 20, 180); emit('boss', { phase: 'slam' }); }
        }
        if (B.t >= BF_INTRO) { B.state = 'fight'; B.t = 0; B.ft = 0; E.tint = 0; }
      } else if (B.state === 'fight') {
        B.ft += dt;
        if (B.clan) { clanTick(B, dt); return; }
        const want = bossWant(B) * B.hpMax;
        B.hp += (want - B.hp) * Math.min(1, dt * 5);
        if (B.res !== 'lose') B.php = Math.max(B.php, 0.3);
        if (B.res === 'lose') B.php = Math.max(0.05, Math.min(B.php, 1 - 0.8 * clamp(B.ft / (B.fightT || BF_FIGHT), 0, 1)));
        P.hp = Math.max(1, P.hpMax * B.php);
        const r = B.hp / B.hpMax;
        if (B.phase < 1 && r < 0.66) { B.phase = 1; E.flash = 0.5; E.flashCol = '#ff3050'; E.shake = 10; say('격노!', bm.x, bm.y - 150, 'c', 26, '#ff5c7a'); emit('boss', { phase: 'rage' }); }
        else if (B.phase < 2 && r < 0.33) { B.phase = 2; E.flash = 0.6; E.flashCol = '#ff3050'; E.shake = 12; say('폭주!', bm.x, bm.y - 150, 'c', 30, '#ff3050'); emit('boss', { phase: 'rage' }); }
        bossAttack(B, dt);
        if (B.ft >= (B.fightT || BF_FIGHT) && B.res && Math.abs(B.hp - B.target) < B.hpMax * 0.02) {
          B.hp = B.target; B.atk = null;
          if (B.res === 'win') {
            B.state = 'dying'; B.t = 0; E.slow = 1.1; E.shake = 12; E.flash = 0.8; E.flashCol = '#fff';
            for (let i = 0; i < 26; i++) newPart('coin', bm.x + (rnd() - 0.5) * 80, bm.y - 50, (rnd() - 0.5) * 220, -200 - rnd() * 120, 3.2, 4.2, '#ffd23c').b = GY;
            poof(bm.x, bm.y - 70, '#fff6c0', 30, 180); ring(bm.x, bm.y - 60, '#fff6c0', 150, 0.8); emit('boss', { phase: 'win' });
          } else { B.state = 'smash'; B.t = 0; }
        }
        if (B.ft > 40 && !B.res) { B.state = 'leave'; B.t = 0; }
      } else if (B.state === 'total') {   // 클랜 보스: 총 피해 표시 → (쓰러졌으면 처치 연출) → 끝
        B.hp += (clanRem(INS) - B.hp) * Math.min(1, dt * 6); INS.totalT += dt;
        if (B.t > 3.3) {
          if (INS.dead) {
            B.state = 'dying'; B.t = 0; B.hp = 0; E.slow = 1.1; shk(12); flashS(0.8, '#fff');
            for (let i = 0; i < 26; i++) newPart('coin', bm.x + (rnd() - 0.5) * 80, bm.y - 50, (rnd() - 0.5) * 220, -200 - rnd() * 120, 3.2, 4.2, '#ffd23c').b = GY;
            poof(bm.x, bm.y - 70, '#fff6c0', 30, 180); ring(bm.x, bm.y - 60, '#fff6c0', 150, 0.8); emit('boss', { phase: 'win' });
          } else { B.state = 'leave'; B.t = 0; }
        }
      } else if (B.state === 'dying') { if (B.t > 2.8) finishBoss(); }
      else if (B.state === 'smash') {
        if (B.t > 0.35 && !B.down) { B.down = true; P.hurtT = 1.8; P.hp = 1; E.shake = 12; E.flash = 0.5; E.flashCol = '#ff3050'; ring(P.x, P.y, '#ff5c7a', 100, 0.6); poof(P.x, P.y - 30, '#ff5c7a', 16, 160); emit('boss', { phase: 'lose' }); }
        if (B.t > 2.8) { B.state = 'leave'; B.t = 0; }
      } else if (B.state === 'leave') { if (B.t > 0.8) finishBoss(); }
    }
    function finishBoss() {
      if (boss && boss.inst) { insBossDone(boss.res); return; }
      boss = null; st.boss = null; E.cin = 0; E.tint = 0; E.slow = 0;
      map = hunt; mobs = []; shots = []; fxs.length = 0; later_.length = 0;
      resetPlayerPos(map.spawnX); P.hp = P.hpMax; P.hurtT = 0; P.inv = 1.2; E.cam = 0; E.spawnT = 0.4; E.waveQ = 0; E.waveWait = 0.5;
      emit('boss', { phase: 'end' });
    }

    // =====================================================================
    //  인스턴스 전투 — 열쇠 던전 · 클랜 보스 · 보상 상자.
    //   승패·보상·피해는 서버가 정한다. 엔진은 그 값에 맞춰 연출 시간표를 짠다(결과가 늦으면 입장 연출로 기다린다).
    //   던전: 입장(문 열림) → 웨이브 2~4 → 수문장(슬로모션 처치) → 보상 상자 / 패배 / 소탕(빠른 감기) / 열쇠 없음(문 닫힘)
    //   클랜 보스: 거대 보스에게 병아리(+동료)가 직접 달려들어 때린다. 서버 피해(dmg)를 여러 번의 타격으로 나눠 보여 주되 합이 정확히 dmg.
    // =====================================================================
    const INS_INTRO = 1.8, INS_CLAN_BX = 660;
    function genDungeonRoom(W, theme) {
      const plats = [{ id: 0, kind: 'floor', x0: 0, x1: W, y: GY, solid: true, tier: 0 }];
      const add = (x0, x1, tier) => plats.push({ id: plats.length, kind: 'plat', x0, x1, y: GY - tier * 64, solid: false, tier });
      add(W * 0.14, W * 0.14 + 290, 1); add(W / 2 - 80, W / 2 + 80, 2); add(W * 0.86 - 290, W * 0.86, 1);
      const M = { reg: -1, seed: 0, W, name: theme === 'arena' ? '클랜 보스 방' : '던전', step: 64, plats, blocks: [], spawnX: 100, room: true, theme, hue: theme === 'arena' ? 350 : 262 };
      buildNav(M); return M;
    }
    function startInstance(o) {
      if (boss || INS || !o) return false;
      const kind = o.kind === 'clanboss' || o.kind === 'clanclaim' ? o.kind : 'dungeon';
      const lvl = Math.max(1, Math.floor(N(o.level)) || 1);
      const key = /^[a-z0-9_]{1,30}$/.test(String(o.img || '')) ? String(o.img) : '';
      hunt = map; mobs = []; shots = []; fxs.length = 0; later_.length = 0; callouts.length = 0; E.dim = E.dimGoal = E.dimHold = 0;
      map = genDungeonRoom(1000, kind === 'dungeon' ? 'dungeon' : 'arena');
      resetPlayerPos(kind === 'dungeon' ? 118 : 30); P.hp = P.hpMax; P.mp = P.mpMax; P.inv = 0; P.dead = false; P.face = 1; P.hurtT = 0; E.cam = 0; E.combo = 0; E.comboT = 0;
      const W = o.waves ? clamp(Math.floor(N(o.waves)), 2, 6) : clamp(3 + Math.floor((lvl - 1) / 8), 3, 5);
      INS = { kind, level: lvl, name: String(o.name || ''), img: key, waves: W, wave: 0, phase: 'intro', pt: 0, t: 0, res: '', result: null, predict: String(o.predict || ''), noCtl: true, safe: true,
        queue: 0, spawnT: 0, waveT: 0, crush: false, doorOpen: 0, shake: 0, locked: 0, done: false, spawnFail: 0, eliteDone: false, kills: 0,
        dmg: 0, K: 0, rem: 0, left: 0, total: 0, hits: 0, before: 0, after: 0, hpMax: 1, dead: false, notes: [], totalT: 0, flushT: 0, r0: 1, items: [], chest: null, ffN: 0, ffT: 0, tick: 0 };
      if (key) ld('img/brjang/boss/' + key + '/front.png');
      E.tint = 0;
      emit('instance', { phase: 'in', kind, level: lvl });
      if (o.result) instanceResult(o.result);
      return true;
    }
    function instanceResult(r) {
      const I = INS; if (!I || I.done || !r || I.res) return;
      let res = String(r.result || r.res || '');
      if (I.kind === 'dungeon') { if (['win', 'lose', 'sweep', 'nokey'].indexOf(res) < 0) res = 'abort'; }
      else if (res !== 'ok') res = 'abort';
      I.result = r; I.res = res;
      if (res === 'abort') { insFinish({ aborted: true }); return; }
      if (I.kind === 'clanboss') {
        I.dmg = Math.max(0, Math.floor(N(r.dmg))); I.hpMax = Math.max(1, N(r.hp) || 1); I.before = Math.max(0, N(r.before)); I.after = r.after != null ? Math.max(0, N(r.after)) : I.before + I.dmg;
        I.dead = !!r.dead; I.notes = Array.isArray(r.notes) ? r.notes.slice(0, 3).map(String) : [];
        I.K = I.dmg <= 0 ? 0 : Math.min(I.dmg, clamp(Math.round(20 + Math.log10(I.dmg + 10) * 3), 22, 34)); I.rem = I.dmg; I.left = I.K; I.r0 = clamp(1 - I.before / I.hpMax, 0, 1);
      }
      if (I.kind === 'dungeon' && boss && boss.inst && (res === 'win' || res === 'lose')) bossResult(res);
      if (I.kind === 'dungeon' && res === 'sweep' && I.phase !== 'intro' && I.phase !== 'ff' && I.phase !== 'chest') { mobs = []; shots = []; insSetPhase('ff'); }
    }
    function insSetPhase(ph) { INS.phase = ph; INS.pt = 0; }
    function insFinish(info) {
      const I = INS; if (!I || I.done) return; I.done = true;
      boss = null; st.boss = null; E.cin = 0; E.tint = 0; E.slow = 0; E.dim = E.dimGoal = E.dimHold = 0; E.lines = 0;
      map = hunt; mobs = []; shots = []; fxs.length = 0; later_.length = 0; callouts.length = 0;
      for (let i = 0; i < PMAX; i++) parts[i].on = false;
      if (hunt.reg !== D.reg) { INS = null; setMap(genMap(D.reg, opts.seed != null ? opts.seed | 0 : 1)); INS = I; }
      resetPlayerPos(map.spawnX); P.hp = P.hpMax; P.mp = P.mpMax; P.hurtT = 0; P.inv = 1.2; P.dead = false; E.cam = 0; E.spawnT = 0.4; E.waveQ = 0; E.waveWait = 0.5; E.combo = 0; E.comboT = 0;
      const kind = I.kind, res = I.res; INS = null;
      emit('instance', Object.assign({ phase: 'end', kind, res, total: I.total, dmg: I.dmg }, info || {}));
    }
    function skipInstance() {
      const I = INS; if (!I || I.done) return;
      if (I.kind === 'clanboss') { I.total = I.dmg; I.rem = 0; I.left = 0; }
      insFinish({ skipped: true });
    }
    function abortInstance() { if (INS && !INS.done) insFinish({ aborted: true }); }

    function insToBoss() {
      const I = INS;
      if (!I.res) { insSetPhase('hold'); return; }
      insBeginBoss();
    }
    function insBeginBoss() {
      const I = INS, clan = I.kind === 'clanboss';
      I.phase = 'boss'; I.pt = 0; I.noCtl = false; I.safe = I.res !== 'lose';
      mobs = []; shots = []; later_.length = 0;
      const bx = clan ? INS_CLAN_BX : INS_CLAN_BX + 40;
      const bm = { id: E.uid++, x: bx, y: GY, st: 'boss', boss: true, sc: clan ? 4.0 : 3.2, hp: 1e12, max: 1e12, hit: 0, kb: 0, sqz: 0, face: -1, fly: false, plat: map.plats[0], t: 0, fxk: '', fxt: 0, fxa: 0, fxc: '#fff', fxd: 1 };
      mobs.push(bm);
      if (!clan) resetPlayerPos(bx - 300);
      boss = { name: clan ? (I.name || '클랜 보스') : ('수문장 ' + (I.name || '')).trim(), img: I.img, hp: clan ? I.r0 : 1000, hpMax: clan ? 1 : 1000, target: 0, res: null, state: 'intro', t: 0, ft: 0, hit: 0, phase: 0, atk: null, atkT: 1.6, land: false, php: 1, z: 150, stage: st.stage, m: bm,
        inst: true, clan, fightT: clan ? 99 : 6.5, px: clan ? 190 : 128, tag: clan ? '🐲 이번 주 클랜 보스' : '🗝 던전 ' + I.level + '단계 · 수문장' };
      if (!clan && (I.res === 'win' || I.res === 'lose')) bossResult(I.res);
      E.tint = 1; E.tintCol = '#ff3050';
      emit('instance', { phase: 'boss', kind: I.kind }); emit('boss', { phase: 'in' });
    }
    // 보스(수문장·클랜 보스)가 끝나면 사냥터로 돌아가지 않고 다음 장면(상자·패배·끝)으로
    function insBossDone(res) {
      const I = INS; if (!I) return;
      boss = null; st.boss = null; E.cin = 0; E.tint = 0; E.slow = 0; mobs = []; shots = []; fxs.length = 0; later_.length = 0;
      if (I.kind === 'clanboss') { insFinish({}); return; }
      if (res === 'win') insStartChest();
      else { P.hurtT = 1.8; P.hp = 1; I.noCtl = true; I.phase = 'lose'; I.pt = 0; emit('instance', { phase: 'lose', kind: I.kind }); }
    }
    function insStartChest() {
      const I = INS; I.phase = 'chest'; I.pt = 0; I.noCtl = true; I.safe = true; I.items = [];
      const got = (I.result && I.result.got) || {};
      ['stone', 'gold', 'ticket', 'feast'].forEach(k => { const n = Math.floor(N(got[k])); if (n > 0) I.items.push({ kind: k, n, x: 0, y: 0, t: 0, st: 'wait' }); });
      I.chest = { x: 600, open: 0, y: -90, landed: false, glow: 0, popped: false };
      if (!boss) { mobs = []; }
      P.x = 520; P.face = 1; P.vx = 0; P.y = GY; P.on = true; P.hurtT = 0; P.hp = P.hpMax; P.inv = 0;
      E.cam = clamp(P.x - E.VW * 0.5 + 40, 0, Math.max(0, map.W - E.VW));
      emit('instance', { phase: 'chestin', kind: I.kind });
    }
    function startWave(n) {
      const I = INS; I.wave = n; I.phase = 'wave'; I.pt = 0; I.waveT = 0; I.crush = false; I.noCtl = false; I.spawnFail = 0;
      I.queue = 2 + (n >= I.waves - 1 ? 1 : 0) + (I.level >= 15 ? 1 : 0); I.spawnT = 0.15; I.eliteDone = false;
      emit('instance', { phase: 'wave', n, of: I.waves, kind: I.kind });
    }
    function insSpawn() {
      const I = INS, last = I.wave >= I.waves - 1;
      let m = spawnMob(null, null, last && !I.eliteDone && rnd() < 0.6 ? { el: true } : {});
      if (!m && ++I.spawnFail > 20) { I.spawnFail = 0; m = spawnMob(clamp(P.x + (rnd() < 0.5 ? -1 : 1) * 140, 60, map.W - 60), map.plats[0], { noPack: true }); }
      if (m) { if (m.el) I.eliteDone = true; return true; }
      return false;
    }
    function insGhost() {   // 소탕 연출용: 몹이 나타나자마자 날아가 사라진다(처치 수·보고에는 안 센다)
      const x = clamp(E.cam + 50 + rnd() * (E.VW - 100), 60, map.W - 60), m = spawnMob(x, map.plats[0], { noPack: true, el: false, fly: false, shoot: false }); if (!m) return;
      const dir = rnd() < 0.5 ? -1 : 1; m.st = 'dying'; m.t = 0; m.dvx = dir * (120 + rnd() * 120); m.dvy = -220 - rnd() * 100; m.drot = dir * (3 + rnd() * 4); m.dz = m.y;
      for (let i = 0; i < 2; i++) newPart('coin', m.x, m.y - 14, (rnd() - 0.5) * 140, -160 - rnd() * 80, 6, 4.2, '#ffd23c').b = m.y;
      poof(m.x, m.y - 14, '#fff6c0', 5, 100); ring(m.x, m.y - 12, '#fff6c0', 30, 0.3);
    }
    function updateIns(h) {
      const I = INS; if (!I || I.done) return;
      I.t += h; I.pt += h; I.shake = Math.max(0, I.shake - h * 4);
      const res = I.res || I.predict;
      switch (I.phase) {
        case 'intro': {
          const tgt = I.kind === 'dungeon' && res !== 'nokey' ? 1 : 0;
          I.doorOpen = I.pt < 0.25 ? 0 : tgt > I.doorOpen ? Math.min(tgt, I.doorOpen + h * 1.3) : Math.max(tgt, I.doorOpen - h * 5);
          if (I.kind === 'dungeon') { P.face = 1; }
          else if (I.pt > 0.2 && P.x < (I.kind === 'clanboss' ? 360 : 300)) { P.x += 190 * h; P.run = 190; P.face = 1; if ((I.tick += h) > 0.12) { I.tick = 0; dust(P.x - 6, P.y, 2, -1); } }
          if (I.pt >= INS_INTRO) {
            if (I.kind === 'dungeon') {
              if (res === 'nokey') { if (I.res || I.pt > INS_INTRO + 0.2) { insSetPhase('locked'); } }
              else if (I.res === 'sweep') { insSetPhase('ff'); }
              else { startWave(1); }
            } else if (I.kind === 'clanboss') { if (I.res) insBeginBoss(); }
            else if (I.res) insStartChest();
          }
          break; }
        case 'locked': {
          I.doorOpen = Math.max(0, I.doorOpen - h * 5);
          if (!I.locked && I.pt > 0.15) { I.locked = 1; I.shake = 1.4; shk(5); flashS(0.2, '#ff3050'); emit('instance', { phase: 'locked', kind: I.kind }); }
          if (I.locked === 1 && I.pt > 0.7) { I.locked = 2; I.shake = 1.0; shk(3); }
          if (I.pt > 2.5) insFinish({});
          break; }
        case 'wave': {
          I.waveT += h; I.spawnT -= h;
          if (I.queue > 0 && I.spawnT <= 0 && aliveCount() < 10) { if (insSpawn()) { I.queue--; I.spawnT = 0.28; } }
          const alive = aliveCount();
          if (I.waveT > 6.5 && alive > 0 && !I.crush) { I.crush = true; for (const m of mobs) if (!m.boss && liveMob(m)) m.hp = Math.min(m.hp, 1); say('압도!', P.x, P.y - PH - 14, 'c', 20, '#ffe27a'); }
          if (I.queue <= 0 && alive === 0 && I.waveT > 0.6) { emit('instance', { phase: 'wavedone', n: I.wave, kind: I.kind }); insSetPhase('gap'); }
          break; }
        case 'gap': if (I.pt >= 1.0) { if (I.wave < I.waves - 1) startWave(I.wave + 1); else insToBoss(); } break;
        case 'hold': if (I.res) insToBoss(); break;
        case 'ff': {
          if (I.pt < h * 1.5) { E.lines = 1; emit('instance', { phase: 'ff', kind: I.kind, waves: I.waves }); }
          E.lines = Math.max(E.lines, 0.8); E.linesCol = '#ffe27a';
          I.ffT += h; if (I.ffT > 0.13) { I.ffT = 0; insGhost(); }
          I.ffN = Math.min(I.waves, 1 + Math.floor(I.pt / (2.4 / I.waves)));
          P.x = 520 + Math.sin(I.pt * 7) * 190; P.face = Math.cos(I.pt * 7) >= 0 ? 1 : -1; P.run = 300; P.y = GY; P.on = true;
          if ((I.tick += h) > 0.05) { I.tick = 0; const g = newPart('ghost', P.x, P.y, 0, 0, 0.25, 0, '#ffe27a'); if (g) g.a = P.face; dust(P.x, P.y, 1, -P.face); }
          if (I.pt >= 2.6) { mobs = []; insStartChest(); }
          break; }
        case 'chest': {
          const C = I.chest; if (!C) break;
          const bounce = q => { if (q < 0.7) return -90 + 90 * (q / 0.7) * (q / 0.7) * 1.0; const u = (q - 0.7) / 0.3; return -Math.sin(u * Math.PI) * 14; };
          if (I.pt < 0.6) C.y = bounce(I.pt / 0.6) + (I.pt >= 0.6 ? 0 : 0); else C.y = 0;
          if (!C.landed && I.pt >= 0.42) { C.landed = true; shk(5); dust(C.x - 10, GY, 4, -1); dust(C.x + 10, GY, 4, 1); ring(C.x, GY, '#ffe27a', 50, 0.4); emit('instance', { phase: 'chestland', kind: I.kind }); }
          C.glow = I.pt < 0.7 ? 0 : clamp((I.pt - 0.7) / 0.6, 0, 1);
          if (I.pt >= 0.7 && I.pt < 1.3 && !E.reduced) { C.shakeX = Math.sin(I.pt * 70) * 1.6 * C.glow; } else C.shakeX = 0;
          if (!C.popped && I.pt >= 1.3) {
            C.popped = true; flashS(0.5, '#fff6c0'); shk(6); hs(0.06);
            newPart('beam', C.x, GY - 20, 0, 0, 1.2, 40, '#ffe27a'); ring(C.x, GY - 16, '#fff6c0', 120, 0.6); ring(C.x, GY - 16, '#ffd23c', 80, 0.45); poof(C.x, GY - 26, '#fff6c0', 24, 200, 60);
            I.items.forEach((it, i) => { const n = I.items.length; it.st = 'pop'; it.t = 0; it.x = C.x; it.y = GY - 30; it.tx = C.x + (i - (n - 1) / 2) * 62; it.ty = GY - 96 - (i % 2) * 14; });
            emit('instance', { phase: 'chest', kind: I.kind, items: I.items.map(it => ({ kind: it.kind, n: it.n })) });
          }
          if (C.popped) C.open = Math.min(1, C.open + h * 4);
          const tFly = 1.3 + 1.25;
          I.items.forEach(it => {
            if (it.st === 'pop') { it.t += h; const e = clamp(it.t / 0.5, 0, 1), eo = 1 - Math.pow(1 - e, 3); it.px = lerp(C.x, it.tx, eo); it.py = lerp(GY - 30, it.ty, eo) - Math.sin(e * Math.PI) * 30; if (it.t > 0.6) { it.px = it.tx; it.py = it.ty + Math.sin(I.pt * 5 + it.n) * 3; } }
          });
          if (I.pt >= tFly && !I.rewarded) {
            I.rewarded = true;
            I.items.forEach((it, i) => { it.st = 'fly'; it.t = 0; emit('reward', { kind: it.kind, n: it.n, fx: ((it.px != null ? it.px : C.x) - E.cam) / E.VW, fy: (it.py != null ? it.py : GY - 80) / LH }); });
            if (!I.items.length) I.rewarded = true;
          }
          if (I.rewarded) I.items.forEach(it => { it.t += h; });
          if (I.pt >= tFly + 1.0) insFinish({});
          break; }
        case 'lose': if (I.pt > 2.8) insFinish({}); break;
      }
    }
    // 클랜 보스: 서버가 준 피해 dmg 를 K 번의 타격으로 나눈다. 남은 칸마다 최소 1 을 남기고 마지막 칸이 나머지를 모두 가져가서 합이 정확히 dmg 가 된다.
    function clanHit(m, mult, o) {
      const I = INS, B = boss; if (!I || !B || !B.clan || B.state !== 'fight' || I.left <= 0) return false;
      o = o || {};
      const crit = rnd() < (o.synthetic ? 0.2 : 0.24), sk = o.skill || null, sv = sk ? SKV[sk] : null;
      let d;
      if (I.left === 1) d = I.rem; else d = clamp(Math.round(I.rem / I.left * (crit ? 1.9 : 1) * (sk ? 1.5 : 1) * (0.8 + rnd() * 0.4)), 1, I.rem - (I.left - 1));
      I.rem -= d; I.left--; I.total += d; I.hits++;
      m.hit = 0.12; m.sqz = 1;
      const tx = m.x + (rnd() - 0.5) * 80, ty = m.y - 36 - rnd() * 100, dirx = P.x < m.x ? 1 : -1;
      say(fmtNum(d) + (crit ? '!' : ''), tx, ty, crit ? 'c' : 's', crit ? 26 : sk ? 21 : 16, crit ? '#ffd23c' : sk ? sv.col : '#ffffff', sv ? sv.dark : null);
      sparks(tx - dirx * 6, ty, -dirx, crit ? '#ffe9a0' : (sk ? sv.col : '#ffffff'), crit ? 10 : 5, crit ? 240 : 170);
      newPart('flash', tx, ty, 0, 0, 0.12, crit ? 34 : 20, crit ? '#fff2b0' : (sk ? sv.col : '#ffffff'));
      if (crit) { newPart('star', tx, ty - 4, 0, -20, 0.38, 24, '#ffd23c'); zoomAt(0.03); shk(3.2); hs(0.04); } else { shk(0.9); }
      E.combo++; E.comboT = 2.0; E.comboPunch = 1; if (E.combo > E.comboMax) E.comboMax = E.combo;
      emit('hit', { crit, dmg: d, skill: sk }); emit('ihit', { dmg: d, total: I.total, crit, left: I.left });
      if (I.left <= 0) clanFinish();
      return true;
    }
    function clanFinish() {
      const I = INS, B = boss; if (!B || B.state !== 'fight') return;
      B.state = 'total'; B.t = 0; B.atk = null; I.phase = 'total'; I.pt = 0; I.totalT = 0; callouts.length = 0;
      E.slow = 0.6; shk(8); flashS(0.35, '#fff'); hs(0.08);
      emit('instance', { phase: 'total', kind: I.kind, total: I.total });
    }
    function clanRem(I) { return clamp(1 - (I.before + (I.after - I.before) * (I.dmg > 0 ? I.total / I.dmg : 1)) / Math.max(1, I.hpMax), 0, 1); }
    function clanTick(B, dt) {
      const I = INS, bm = B.m;
      B.hp += (clanRem(I) - B.hp) * Math.min(1, dt * 7);
      B.php = Math.max(B.php, 0.3); P.hp = Math.max(1, P.hpMax * B.php);
      const r = B.hp;
      if (B.phase < 1 && r < 0.66 && I.r0 >= 0.66) { B.phase = 1; flashS(0.35, '#ff3050'); shk(8); say('격노!', bm.x, bm.y - 160, 'c', 26, '#ff5c7a'); emit('boss', { phase: 'rage' }); }
      else if (B.phase < 2 && r < 0.33 && I.r0 >= 0.33) { B.phase = 2; flashS(0.4, '#ff3050'); shk(9); say('폭주!', bm.x, bm.y - 160, 'c', 30, '#ff3050'); emit('boss', { phase: 'rage' }); }
      bossAttack(B, dt);
      if (B.ft > 12 && I.left > 0) { I.flushT -= dt; if (I.flushT <= 0) { I.flushT = 0.07; clanHit(bm, 100, { synthetic: true }); } }
      if (I.K === 0 && B.state === 'fight') clanFinish();
    }

    // ----- 인스턴스 그리기 -----
    function drawThemeBg(VW) {
      const c = ctx, cam = E.cam, arena = map.theme === 'arena';
      const g = c.createLinearGradient(0, 0, 0, GY); g.addColorStop(0, arena ? '#2a0a16' : '#0f0a22'); g.addColorStop(1, arena ? '#4d1626' : '#2a1850'); c.fillStyle = g; c.fillRect(0, 0, VW, LH);
      const off = cam * 0.5, bw = 46, bh = 22; c.strokeStyle = arena ? 'rgba(255,120,140,.12)' : 'rgba(170,140,255,.12)'; c.lineWidth = 1;
      c.beginPath(); for (let r = 0; r * bh < GY; r++) { const sh = (r % 2) * bw / 2; for (let k = Math.floor((off - sh) / bw) - 1; k * bw + sh - off < VW; k++) c.rect(k * bw + sh - off, r * bh, bw, bh); } c.stroke();
      const off2 = cam * 0.7, sp = 300;
      for (let k = Math.floor(off2 / sp) - 1; k * sp - off2 < VW + 60; k++) {
        const x = k * sp - off2 + 110;
        c.fillStyle = arena ? 'rgba(58,12,26,.85)' : 'rgba(28,18,58,.85)'; c.fillRect(x - 16, 16, 32, GY - 16); c.fillStyle = 'rgba(255,255,255,.07)'; c.fillRect(x - 16, 16, 4, GY - 16);
        if (arena) { c.fillStyle = '#7a1830'; c.beginPath(); c.moveTo(x + 120, 24); c.lineTo(x + 170, 24); c.lineTo(x + 170, 120); c.lineTo(x + 145, 104); c.lineTo(x + 120, 120); c.closePath(); c.fill(); c.fillStyle = '#ffd23c'; c.beginPath(); c.arc(x + 145, 58, 9, 0, 6.3); c.fill(); }
        const fl = 0.75 + 0.25 * Math.sin(E.t * 9 + k * 2);
        c.save(); c.globalCompositeOperation = 'lighter'; const gg = c.createRadialGradient(x, 92, 2, x, 92, 82 * fl); gg.addColorStop(0, arena ? 'rgba(255,120,90,.8)' : 'rgba(255,180,70,.8)'); gg.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = gg; c.fillRect(x - 90, 10, 180, 170); c.restore();
        c.fillStyle = '#3a2a1a'; c.fillRect(x - 3, 96, 6, 18); c.fillStyle = '#ffd47a'; c.beginPath(); c.ellipse(x, 90, 5 * fl, 9 * fl, 0, 0, 6.3); c.fill();
      }
    }
    function drawDoor(I) {
      const c = ctx, x = 54 - E.cam, y = GY, w = 74, h = 116, open = I.doorOpen, sk = I.shake > 0 && !E.reduced ? (rnd() - 0.5) * I.shake * 4 : 0;
      if (x < -80 || x > E.VW + 80) return;
      c.save(); c.translate(sk, 0);
      c.fillStyle = '#120c26'; c.strokeStyle = '#8b78c8'; c.lineWidth = 3; c.beginPath(); c.moveTo(x - w / 2 - 6, y); c.lineTo(x - w / 2 - 6, y - h + 30); c.arc(x, y - h + 30, w / 2 + 6, Math.PI, 0); c.lineTo(x + w / 2 + 6, y); c.closePath(); c.fill(); c.stroke();
      if (open > 0.02) { c.save(); c.globalCompositeOperation = 'lighter'; const g = c.createRadialGradient(x, y - 50, 4, x, y - 50, 150 * open + 20); g.addColorStop(0, 'rgba(255,236,170,.95)'); g.addColorStop(0.5, 'rgba(255,170,70,.45)'); g.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = g; c.fillRect(x - 170, y - 190, 340, 200); c.restore(); }
      const lw = (w / 2 + 2) * (1 - open);
      if (lw > 0.5) { c.fillStyle = '#5b3a22'; c.strokeStyle = '#2a170a'; c.lineWidth = 1.5; for (const sd of [-1, 1]) { const x0 = sd < 0 ? x - w / 2 - 2 : x + w / 2 + 2 - lw; c.fillRect(x0, y - h + 30, lw, h - 30); c.strokeRect(x0, y - h + 30, lw, h - 30); c.fillStyle = '#9a9ab0'; c.fillRect(x0, y - h + 52, lw, 4); c.fillRect(x0, y - 22, lw, 4); c.fillStyle = '#5b3a22'; } }
      if ((I.locked > 0 || (I.res || I.predict) === 'nokey') && open < 0.3) { c.strokeStyle = '#b8b8c8'; c.lineWidth = 3; c.beginPath(); c.moveTo(x - w / 2, y - h + 48); c.lineTo(x + w / 2, y - 30); c.moveTo(x + w / 2, y - h + 48); c.lineTo(x - w / 2, y - 30); c.stroke(); outText('🔒', x, y - 62, 26, '#fff', 'center', 0); }
      c.restore();
    }
    function drawChest(x, y, open, glow) {
      const c = ctx; c.save(); c.translate(x, y);
      if (glow > 0) { c.save(); c.globalCompositeOperation = 'lighter'; const g = c.createRadialGradient(0, -22, 4, 0, -22, 40 + 80 * glow); g.addColorStop(0, 'rgba(255,236,150,' + (0.5 + 0.4 * glow) + ')'); g.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = g; c.fillRect(-130, -150, 260, 200); c.restore(); }
      c.lineJoin = 'round'; c.strokeStyle = '#2b1408'; c.lineWidth = 2;
      c.fillStyle = '#7a4219'; c.fillRect(-24, -26, 48, 26); c.strokeRect(-24, -26, 48, 26);
      c.fillStyle = '#ffd23c'; c.fillRect(-24, -26, 6, 26); c.fillRect(18, -26, 6, 26); c.fillRect(-24, -14, 48, 4);
      if (open > 0.05) { c.save(); c.globalCompositeOperation = 'lighter'; const g2 = c.createLinearGradient(0, -26, 0, -60); g2.addColorStop(0, 'rgba(255,246,190,' + open + ')'); g2.addColorStop(1, 'rgba(255,200,60,0)'); c.fillStyle = g2; c.fillRect(-20, -60, 40, 34); c.restore(); }
      c.save(); c.translate(-24, -26); c.rotate(-open * 1.75); c.fillStyle = '#a05a24'; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, -10); c.quadraticCurveTo(24, -24, 48, -10); c.lineTo(48, 0); c.closePath(); c.fill(); c.stroke();
      c.fillStyle = '#ffd23c'; c.fillRect(0, -9, 6, 9); c.fillRect(42, -9, 6, 9); c.fillStyle = '#ffe9a0'; c.fillRect(20, -4, 8, 6); c.restore();
      c.restore();
    }
    function drawInsBack(VW) {
      const I = INS; if (!I) return;
      if (I.kind === 'dungeon') drawDoor(I);
      if (I.chest) { const C = I.chest; drawChest(C.x - E.cam + (C.shakeX || 0), GY + C.y, C.open, C.glow); }
    }
    function drawInsFront(VW) {
      const I = INS; if (!I || !I.items.length) return;
      const c = ctx;
      for (const it of I.items) {
        if (it.st === 'wait' || it.px == null) continue;
        const ic = ld('img/brjhunt/ui/cur_' + it.kind + '.webp'), x = it.px - E.cam, a = it.st === 'fly' ? clamp(1 - it.t / 0.3, 0, 1) : 1, sc = it.st === 'fly' ? 1 + it.t * 2 : 1;
        c.save(); c.globalAlpha = a; c.translate(x, it.py); c.scale(sc, sc);
        c.save(); c.globalCompositeOperation = 'lighter'; const g = c.createRadialGradient(0, 0, 2, 0, 0, 30); g.addColorStop(0, 'rgba(255,236,150,.8)'); g.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = g; c.fillRect(-30, -30, 60, 60); c.restore();
        if (ic) c.drawImage(ic, -18, -18, 36, 36); else outText('●', 0, 0, 24, '#ffd23c', 'center', 2);
        outText('+' + fmtNum(it.n), 0, 30, 16, '#fff', 'center', 4);
        c.restore();
      }
    }
    function insPill(c, VW, txt, y) {   // 제목 띠: 화면 위 가운데. 페이지(DOM 체력바·AUTO 버튼을 쓰는 쪽)에서는 오른쪽 버튼과 안 겹치게 왼쪽 위에 둔다
      c.font = '900 12.5px ' + FONT; const w = c.measureText(txt).width + 24, x = showHud ? VW / 2 - w / 2 : 8;
      c.fillStyle = 'rgba(10,6,24,.74)'; c.beginPath(); c.moveTo(x + 9, y); c.lineTo(x + w - 9, y); c.arc(x + w - 9, y + 9, 9, -1.571, 1.571); c.lineTo(x + 9, y + 18); c.arc(x + 9, y + 9, 9, 1.571, 4.712); c.closePath(); c.fill();
      c.strokeStyle = 'rgba(255,255,255,.3)'; c.lineWidth = 1; c.stroke(); outText(txt, x + w / 2, y + 9.5, 12.5, '#fff', 'center', 2.5);
    }
    function insBanner(c, VW, text, sub, col, dark, q, y) {   // q 0..1 : 나타남(0~.15) → 머묾 → 사라짐(.8~1)
      const a = q < 0.8 ? 1 : (1 - q) / 0.2, pop = E.reduced ? 1 : q < 0.15 ? 1 + (1 - q / 0.15) * 0.8 : 1;
      c.save(); c.globalAlpha = a; const bh = sub ? 66 : 52, g = c.createLinearGradient(0, 0, VW, 0);
      g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.18, dark); g.addColorStop(0.5, 'rgba(14,6,26,.92)'); g.addColorStop(0.82, dark); g.addColorStop(1, 'rgba(0,0,0,0)');
      c.globalAlpha = a * 0.85; c.fillStyle = g; c.fillRect(0, y - bh / 2, VW, bh); c.globalAlpha = a; c.fillStyle = col; c.fillRect(VW * 0.12, y - bh / 2, VW * 0.76, 2); c.fillRect(VW * 0.12, y + bh / 2 - 2, VW * 0.76, 2);
      outText(text, VW / 2, y - (sub ? 8 : 0), 28 * pop, col, 'center', 6, dark); if (sub) outText(sub, VW / 2, y + 20, 12.5, '#ffffff', 'center', 3);
      c.restore();
    }
    function drawInsHud(VW) {
      const I = INS; if (!I) return; const c = ctx, ph = I.phase, kindName = I.kind === 'dungeon' ? '🗝 열쇠 던전 ' + I.level + '단계' : I.kind === 'clanboss' ? '🐲 클랜 보스' : '🍖 클랜 보스 보상';
      let top = kindName;
      if (ph === 'wave' || ph === 'gap') top += ' · WAVE ' + Math.max(1, I.wave) + '/' + I.waves + (ph === 'wave' ? ' · 남은 ' + (aliveCount() + I.queue) : '');
      else if (ph === 'boss') top += I.kind === 'dungeon' ? ' · 수문장' : ' · 누적 피해 ' + I.total.toLocaleString('ko-KR');
      else if (ph === 'ff') top += ' · 소탕 ▶▶ ' + I.ffN + '/' + I.waves;
      else if (ph === 'total') top += ' · 총 피해 ' + I.total.toLocaleString('ko-KR');
      insPill(c, VW, top, 6);
      if (ph === 'hold') insPill(c, VW, '결과를 확인하고 있어요…', 28);
      if (ph === 'intro') {
        const q = clamp((I.pt - 0.1) / 1.7, 0, 1);
        if (I.kind === 'dungeon') insBanner(c, VW, (I.res || I.predict) === 'nokey' ? '던전 입장!' : '던전 입장!', '열쇠 던전 ' + I.level + '단계', '#ffe27a', '#4a2e08', q, LH * 0.42);
        else if (I.kind === 'clanboss') insBanner(c, VW, '클랜 보스 습격!', I.name || '이번 주 클랜 보스', '#ff8aa0', '#5a0a1e', q, LH * 0.42);
        else insBanner(c, VW, '보상 받기!', '클랜 보스를 함께 쓰러뜨렸어요', '#ffe27a', '#4a2e08', q, LH * 0.42);
      } else if (ph === 'wave' && I.pt < 1.1) insBanner(c, VW, 'WAVE ' + I.wave + '/' + I.waves, I.wave >= I.waves - 1 ? '곧 수문장이 나타나요!' : '몬스터가 몰려와요!', '#9be7ff', '#0a2f52', clamp(I.pt / 1.1, 0, 1), LH * 0.5);
      else if (ph === 'gap') insBanner(c, VW, 'WAVE CLEAR!', '', '#ffe27a', '#4a2e08', clamp(I.pt / 1.0, 0, 1), LH * 0.5);
      else if (ph === 'ff') { insBanner(c, VW, '소탕!  ▶▶', '열쇠 1개로 빠르게 쓸어버려요', '#ffe27a', '#4a2e08', clamp(I.pt / 2.6, 0.12, 0.8), LH * 0.38); }
      else if (ph === 'locked') insBanner(c, VW, '🔒 열쇠가 없어요', '시간이 지나면 열쇠가 다시 충전돼요', '#ff8aa0', '#5a0a1e', clamp(I.pt / 2.5, 0.1, 0.9), LH * 0.4);
      else if (ph === 'chest' && I.chest && I.chest.popped && I.pt < 2.4) insBanner(c, VW, '보상 획득!', '', '#ffe27a', '#4a2e08', clamp((I.pt - 1.3) / 1.1, 0, 1), LH * 0.3);
      else if (ph === 'lose') {
        const r = I.result || {}, pw = N(r.power), hp = N(r.hp), diff = hp > pw ? Math.ceil(hp - pw) : 0;
        c.save(); c.fillStyle = 'rgba(8,2,12,.55)'; c.fillRect(0, 0, VW, LH); c.restore();
        insBanner(c, VW, '패배…', diff > 0 ? '전투력이 ' + fmtNum(diff) + ' 모자라요' : '조금 더 강해져서 다시 도전해요', '#ff8aa0', '#5a0a1e', clamp(I.pt / 2.8, 0.1, 0.85), LH * 0.4);
        outText('열쇠는 그대로예요', VW / 2, LH * 0.4 + 52, 12, '#cfd6ff', 'center', 3);
      } else if (ph === 'total') {
        const q = clamp(I.totalT / 0.9, 0, 1), val = Math.round(I.total * (1 - Math.pow(1 - q, 3))), out = clamp((I.totalT - 2.6) / 0.6, 0, 1);
        c.save(); c.fillStyle = 'rgba(8,2,12,' + 0.62 * (1 - out) + ')'; c.fillRect(0, 0, VW, LH); c.globalAlpha = 1 - out;
        const pop = 1 + Math.max(0, 0.25 - I.totalT) * 3; outText('총 피해', VW / 2, LH * 0.34, 16, '#ffd0d8', 'center', 4); outText(val.toLocaleString('ko-KR') + '!', VW / 2, LH * 0.34 + 38, 40 * pop, '#ffe27a', 'center', 8, '#5a2a00');
        I.notes.forEach((t, i) => outText(t, VW / 2, LH * 0.34 + 76 + i * 20, 13, '#ffffff', 'center', 3.2));
        c.restore();
      }
    }

    // =====================================================================
    //  한 칸 갱신
    // =====================================================================
    function control(h) {
      if (INS && INS.noCtl && !boss) { AI.wasAuto = false; return NOCTL; }
      if (autoOn()) {
        if (!AI.wasAuto) { AI.hop = null; AI.tgt = null; AI.rethink = 0; AI.stuckT = 0; }
        AI.wasAuto = true; aiThink(h); return AI;
      }
      AI.wasAuto = false;
      const j = ED.jump, jh = Hh.jump;
      return { left: Hh.left, right: Hh.right, jump: j, jumpHeld: jh, down: Hh.down, attack: Hh.attack, s: [!!ED.s1, !!ED.s2, !!ED.s3, !!ED.s4, !!ED.s5, !!ED.s6, !!ED.s7, !!ED.s8] };
    }
    function updateFx(h) {
      for (let i = fxs.length - 1; i >= 0; i--) { const f = fxs[i]; f.t += h; if (f.t >= f.life) fxs.splice(i, 1); }
      for (let i = later_.length - 1; i >= 0; i--) { const l = later_[i]; l.t -= h; if (l.t <= 0) { later_.splice(i, 1); try { l.fn(); } catch (e) { } } }
      const lim = E.low ? PMLOW : PMAX;
      for (let i = 0; i < PMAX; i++) {
        const p = parts[i]; if (!p.on) continue;
        p.t += h; if (p.t >= p.life) { p.on = false; continue; }
        switch (p.k) {
          case 'dot': case 'dust': p.vy += 120 * h * (p.k === 'dust' ? -0.2 : 1); p.x += p.vx * h; p.y += p.vy * h; p.vx *= Math.exp(-h * 3); break;
          case 'spark': p.vy += 380 * h; p.x += p.vx * h; p.y += p.vy * h; break;
          case 'coin': {
            p.vy += 900 * h; p.x += p.vx * h; p.y += p.vy * h;
            if (p.y >= p.b && p.vy > 0) { p.y = p.b; p.vy *= -0.38; p.vx *= 0.6; if (Math.abs(p.vy) < 40) p.vy = 0; }
            if (p.t > 0.5 && !P.dead) {
              const dx = P.x - p.x, dy = P.y - 14 - p.y, d = Math.hypot(dx, dy) || 1, sp = 160 + (p.t - 0.5) * 520;
              p.vx = dx / d * sp; p.vy = dy / d * sp; p.b = 1e9;
              if (d < 12) { p.on = false; emit('coin', {}); newPart('ring', P.x, P.y - 14, 0, 0, 0.18, 10, '#ffe27a'); }
            }
            break;
          }
          case 'item': p.vy += 900 * h; p.x += p.vx * h; p.y += p.vy * h; if (p.y >= p.b && p.vy > 0) { p.y = p.b; p.vy *= -0.42; p.vx *= 0.5; if (Math.abs(p.vy) < 40) p.vy = 0; } break;
          case 'conv': break;
          default: p.x += p.vx * h; p.y += p.vy * h;
        }
      }
      for (let i = 0; i < TMAX; i++) { const t = texts[i]; if (!t.on) continue; t.t += h; t.y += t.vy * h; t.vy *= Math.exp(-h * 2.2); if (t.t >= t.life) t.on = false; }
      E.shake = Math.max(0, E.shake - h * 28); E.flash = Math.max(0, E.flash - h * 2.2); E.zoom = Math.max(0, E.zoom - h * 0.35);
      if (E.reduced) { E.shake = 0; E.zoom = 0; E.hitstop = 0; E.lines = 0; E.dimGoal = 0; }
      if (E.dimHold > 0) { E.dimHold -= h; E.dim += (E.dimGoal - E.dim) * Math.min(1, h * 12); } else { E.dimGoal = 0; E.dim *= Math.exp(-h * 5); if (E.dim < 0.01) E.dim = 0; }
      E.lines = Math.max(0, E.lines - h * 2.6);
      for (let i = callouts.length - 1; i >= 0; i--) { const k = callouts[i]; k.t += h; if (k.t >= k.life) callouts.splice(i, 1); }
      E.comboPunch = Math.max(0, E.comboPunch - h * 6);
      if (E.comboT > 0) { E.comboT -= h; if (E.comboT <= 0) E.combo = 0; }
    }
    function step(h) {
      if (E.paused || E.hidden || E.destroyed) return;
      E.t += h; addRun(h);
      if (E.hitstop > 0) { E.hitstop -= h; if (!E.reduced) { updateFx(h * 0.35); return; } }
      // 수동 → 자동 복귀 타이머
      if (E.manualT > 0) { if (Hh.left || Hh.right || Hh.jump || Hh.attack || Hh.s1 || Hh.s2 || Hh.s3 || Hh.s4 || Hh.s5 || Hh.s6 || Hh.s7 || Hh.s8) E.manualT = MANUAL_HOLD; else E.manualT -= h; }
      const Ct = control(h);
      updatePlayer(h, Ct);
      for (const k in ED) ED[k] = (typeof ED[k] === 'number' && ED[k] > h) ? ED[k] - h : false;
      if (INS) updateIns(h);
      if (boss) updateBoss(h); else if (!INS) updateSpawn(h);
      updateMobs(h); updateShots(h); updateFx(h);
      // 카메라: 보스가 나타나는 순간·총 피해 장면에서는 보스를 비춘다
      const bfocus = boss && (boss.state === 'intro' || boss.state === 'total' || boss.state === 'dying');
      const tx = clamp(bfocus ? boss.m.x - E.VW * 0.62 : P.x + P.face * 36 - E.VW * 0.5, 0, Math.max(0, map.W - E.VW));
      E.cam += (tx - E.cam) * Math.min(1, h * 6);
      if (E.levelT > 0) E.levelT -= h;
    }
    function addRun(h) {
      if (E.paused || E.hidden || E.destroyed || boss || INS) return;
      E.runAcc += h;
      if (E.runAcc >= REPORT_EVERY) flushReport();
    }
    function flushReport() {
      const secs = Math.min(40, Math.floor(E.runAcc));
      if (secs < 1) return;
      const kills = E.repKills; E.runAcc -= secs; E.repKills = 0;
      emit('report', { kills, secs });
    }
    function advance(dt) {
      if (E.paused || E.hidden) return;
      let left = dt * E.timeScale;
      if (E.slow > 0) { E.slow -= dt; left *= 0.3; }
      E.acc += left;
      let n = 0;
      while (E.acc >= FIX && n++ < 12) { step(FIX); E.acc -= FIX; }
      if (E.acc > FIX * 12) E.acc = 0;
    }

    // =====================================================================
    //  그리기
    // =====================================================================
    function chickSheetFor(pose) {
      switch (pose) {
        case 'idle': return sheet('chick_idle'); case 'run': return sheet('chick_run', 'chick_walk');
        case 'jump': return sheet('chick_jump'); case 'fall': return sheet('chick_fall', 'chick_jump');
        case 'atk0': return sheet('chick_attack1', 'chick_atk1'); case 'atk1': return sheet('chick_attack2', 'chick_atk2'); case 'atk2': return sheet('chick_attack3', 'chick_atk3', 'chick_attack2');
        case 'cast': return sheet('chick_cast', 'chick_skill'); case 'hurt': return sheet('chick_hurt', 'chick_hit'); case 'die': return sheet('chick_die', 'chick_hurt');
      }
      return null;
    }
    // 🏟 [2026-11-13 사장님 「보스전 배경이 너무 밋밋」] 필드 보스 방 배경 — 핏빛 달 · 별 · 구름 · 멀리 콜로세움 실루엣 · 횃불 기둥과 깃발 · 떠오르는 불씨(전부 코드로 그린 시차 배경)
    function bossSkyCanvas(VW) {
      const key = Math.round(VW) + 'x' + LH + 'x' + GY;
      if (E.bossSky && E.bossSkyKey === key) return E.bossSky;
      if (typeof document === 'undefined') return null;
      const cv = document.createElement('canvas'); cv.width = Math.max(2, Math.round(VW)); cv.height = LH; const c = cv.getContext('2d'); if (!c) return null;
      const g = c.createLinearGradient(0, 0, 0, GY); g.addColorStop(0, '#0a0620'); g.addColorStop(0.45, '#2a0c33'); g.addColorStop(0.8, '#7a1634'); g.addColorStop(1, '#d4542e');
      c.fillStyle = g; c.fillRect(0, 0, cv.width, LH);
      for (let i = 0; i < 90; i++) { const x = hash(i * 7 + 1) * cv.width, y = hash(i * 13 + 5) * GY * 0.6, r = 0.5 + hash(i * 3 + 9) * 1.3; c.globalAlpha = 0.25 + hash(i + 40) * 0.6; c.fillStyle = '#ffe9f0'; c.beginPath(); c.arc(x, y, r, 0, 6.3); c.fill(); }
      c.globalAlpha = 1;
      const mx = cv.width * 0.74, my = GY * 0.3, mr = Math.min(86, GY * 0.2);
      let gg = c.createRadialGradient(mx, my, mr * 0.6, mx, my, mr * 3.4); gg.addColorStop(0, 'rgba(255,90,80,.55)'); gg.addColorStop(1, 'rgba(255,60,60,0)'); c.fillStyle = gg; c.fillRect(mx - mr * 3.4, my - mr * 3.4, mr * 6.8, mr * 6.8);
      gg = c.createRadialGradient(mx - mr * 0.3, my - mr * 0.3, mr * 0.1, mx, my, mr); gg.addColorStop(0, '#ffd6c0'); gg.addColorStop(0.55, '#ff6a52'); gg.addColorStop(1, '#b8203a'); c.fillStyle = gg; c.beginPath(); c.arc(mx, my, mr, 0, 6.3); c.fill();
      c.globalAlpha = 0.18; c.fillStyle = '#5a0f2a'; for (const [dx, dy, r] of [[-0.3, -0.2, 0.2], [0.25, 0.1, 0.28], [-0.1, 0.4, 0.15], [0.35, -0.35, 0.12]]) { c.beginPath(); c.arc(mx + dx * mr, my + dy * mr, r * mr, 0, 6.3); c.fill(); }
      c.globalAlpha = 1; E.bossSky = cv; E.bossSkyKey = key; return cv;
    }
    function drawBossRoomBg(VW) {
      const c = ctx, cam = E.cam, t = E.t, low = E.low;
      const sky = bossSkyCanvas(VW);
      if (sky) c.drawImage(sky, 0, 0, VW, LH); else { const g = c.createLinearGradient(0, 0, 0, GY); g.addColorStop(0, '#0a0620'); g.addColorStop(1, '#a8402e'); c.fillStyle = g; c.fillRect(0, 0, VW, LH); }
      // 흐르는 먹구름 두 줄
      for (let band = 0; band < 2; band++) {
        const sp = band ? 260 : 180, y0 = GY * (band ? 0.46 : 0.26), off = cam * (0.04 + band * 0.05) + t * (band ? 9 : 5);
        c.fillStyle = band ? 'rgba(40,10,40,.55)' : 'rgba(24,8,40,.5)';
        for (let k = Math.floor(off / sp) - 1; k * sp - off < VW + sp; k++) { const x = k * sp - off, w = sp * (0.8 + hash(k * 5 + band * 17) * 0.6), h = 16 + hash(k * 3 + band) * 22; c.beginPath(); c.ellipse(x + w / 2, y0 + hash(k + 70) * 20, w / 2, h, 0, 0, 6.3); c.fill(); }
      }
      // 멀리 콜로세움 실루엣(아치 줄)
      { const off = cam * 0.22, sp = 360, base = GY, top = GY - 150; c.fillStyle = '#240a24';
        for (let k = Math.floor(off / sp) - 1; k * sp - off < VW + sp; k++) {
          const x = k * sp - off, tall = hash(k * 11 + 3) > 0.55;
          c.fillRect(x, top - (tall ? 40 : 0), sp + 1, base - top + (tall ? 40 : 0));
          c.fillStyle = '#12051a';
          for (let a = 0; a < 3; a++) { const ax = x + 30 + a * 110; c.beginPath(); c.moveTo(ax, base); c.lineTo(ax, top + 70); c.arc(ax + 36, top + 70, 36, Math.PI, 0); c.lineTo(ax + 72, base); c.closePath(); c.fill(); }
          c.fillStyle = '#240a24';
          if (tall) { c.fillRect(x + sp * 0.5 - 22, top - 90, 44, 52); c.beginPath(); c.moveTo(x + sp * 0.5 - 28, top - 90); c.lineTo(x + sp * 0.5, top - 128); c.lineTo(x + sp * 0.5 + 28, top - 90); c.closePath(); c.fill(); }
        } }
      // 지평선 붉은 안개
      { const hg = c.createLinearGradient(0, GY - 90, 0, GY); hg.addColorStop(0, 'rgba(255,90,60,0)'); hg.addColorStop(1, 'rgba(255,110,70,.38)'); c.fillStyle = hg; c.fillRect(0, GY - 90, VW, 90); }
      // 가까운 기둥 + 횃불 + 깃발
      { const off = cam * 0.55, sp = 330;
        for (let k = Math.floor(off / sp) - 1; k * sp - off < VW + 80; k++) {
          const x = k * sp - off + 120, fl = 0.78 + 0.22 * Math.sin(t * 9 + k * 2.3) + 0.06 * Math.sin(t * 23 + k);
          c.fillStyle = '#2b0f26'; c.fillRect(x - 17, 30, 34, GY - 30); c.fillStyle = '#3d1735'; c.fillRect(x - 17, 30, 7, GY - 30); c.fillStyle = '#1a0818'; c.fillRect(x - 22, 24, 44, 12); c.fillRect(x - 22, GY - 12, 44, 12);
          const sw = Math.sin(t * 2 + k) * 5;   // 붉은 깃발(살랑)
          c.fillStyle = '#8c1531'; c.beginPath(); c.moveTo(x + 30, 44); c.lineTo(x + 78 + sw, 44); c.lineTo(x + 78 + sw * 1.4, 128); c.lineTo(x + 54 + sw * 0.7, 108); c.lineTo(x + 30, 128); c.closePath(); c.fill();
          c.fillStyle = '#ffd23c'; c.beginPath(); c.arc(x + 54 + sw * 0.6, 76, 9, 0, 6.3); c.fill(); c.fillStyle = '#8c1531'; c.beginPath(); c.arc(x + 54 + sw * 0.6, 76, 4.5, 0, 6.3); c.fill();
          c.save(); c.globalCompositeOperation = 'lighter'; const gg = c.createRadialGradient(x, 96, 2, x, 96, (low ? 70 : 110) * fl); gg.addColorStop(0, 'rgba(255,170,80,.85)'); gg.addColorStop(0.4, 'rgba(255,90,50,.32)'); gg.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = gg; c.fillRect(x - 120, -20, 240, 240); c.restore();
          c.fillStyle = '#3a2a1a'; c.fillRect(x - 4, 100, 8, 22); c.fillStyle = '#ffe08a'; c.beginPath(); c.ellipse(x, 93, 5.5 * fl, 11 * fl, 0, 0, 6.3); c.fill(); c.fillStyle = '#ff7a3a'; c.beginPath(); c.ellipse(x, 97, 8 * fl, 13 * fl, 0, 0, 6.3); c.globalAlpha = 0.6; c.fill(); c.globalAlpha = 1;
        } }
      // 떠오르는 불씨
      if (!low) { c.save(); c.globalCompositeOperation = 'lighter';
        for (let i = 0; i < 26; i++) { const sp = 18 + hash(i * 3) * 30, life = (t * sp / 110 + hash(i * 7)) % 1, x = ((hash(i * 11) * (VW + 200) - cam * (0.3 + hash(i) * 0.4) - t * 14) % (VW + 200) + VW + 200) % (VW + 200) - 100, y = GY - life * (GY + 20), r = 1 + hash(i * 5) * 2;
          c.globalAlpha = Math.sin(life * 3.14) * 0.85; c.fillStyle = hash(i * 17) > 0.5 ? '#ffb15a' : '#ff6a4a'; c.beginPath(); c.arc(x + Math.sin(t * 2 + i) * 8, y, r, 0, 6.3); c.fill(); }
        c.restore(); }
    }
    function drawBg(VW) {
      if (map.theme) { drawThemeBg(VW); return; }
      if (map.room) { drawBossRoomBg(VW); return; }
      const cam = E.cam, h = HUE[D.reg < 0 ? 0 : D.reg];
      const room = map.room;
      const g = ctx.createLinearGradient(0, 0, 0, GY); g.addColorStop(0, room ? '#1a0e1e' : 'hsl(' + h + ',55%,66%)'); g.addColorStop(1, room ? '#3a1630' : 'hsl(' + ((h + 20) % 360) + ',65%,86%)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, VW, LH);
      const far = room ? null : sheet('bg_far_' + (D.reg + 1), 'bg_far');
      const im = room ? null : art('bg' + (D.reg + 1));
      if (far) {
        const hh = GY, sc = hh / (far.m.h || far.im.height), w = (far.m.w || far.im.width / far.n) * sc, off = cam * 0.25;
        for (let k = Math.floor(off / w); k * w - off < VW; k++) ctx.drawImage(far.im, 0, 0, far.m.w || far.im.width / far.n, far.m.h || far.im.height, k * w - off, 0, w + 1, hh);
      } else if (im) {
        const sh = 0.77, srcH = im.height * sh, s = (GY - 14) / srcH, w = im.width * s, off = cam * 0.25, y0 = 14;
        for (let k = Math.floor(off / w); k * w - off < VW; k++) {
          const x0 = k * w - off;
          if (((k % 2) + 2) % 2) { ctx.save(); ctx.translate(x0 + w, y0); ctx.scale(-1, 1); ctx.drawImage(im, 0, 0, im.width, srcH, 0, 0, w + 1, GY - y0); ctx.restore(); }
          else ctx.drawImage(im, 0, 0, im.width, srcH, x0, y0, w + 1, GY - y0);
        }
      } else {
        [[0.18, 70, 'hsl(' + h + ',30%,62%)', 90], [0.4, 56, 'hsl(' + h + ',28%,48%)', 70]].forEach(([f, sp, col, mh], li) => {
          const wx = cam * f, b0 = Math.floor(wx / sp) - 1; ctx.fillStyle = col;
          for (let b = b0; b < b0 + Math.ceil(VW / sp) + 3; b++) { const bw = sp * (0.6 + hash(b + li * 77) * 0.4), bh = 40 + hash(b + 99 + li * 31) * mh; ctx.fillRect(b * sp - wx, GY - bh, bw, bh); }
        });
      }
      // 가까운 뒷산(시차 0.55)
      if (!room) {
        ctx.fillStyle = 'hsla(' + h + ',30%,30%,.28)'; const off = cam * 0.55, sp = 120;
        for (let b = Math.floor(off / sp) - 1; b < Math.ceil((off + VW) / sp) + 1; b++) { const bw = sp * (0.55 + hash(b + 5) * 0.4), bh = 22 + hash(b * 3 + 8) * 40; ctx.fillRect(b * sp - off, GY - bh, bw, bh); }
      }
    }
    function drawTerrain(VW) {
      const cam = E.cam, h = map.hue != null ? map.hue : map.room ? 345 : HUE[D.reg < 0 ? 0 : D.reg], M = map;
      // 바닥
      const fl = sheet('floor_' + (D.reg + 1), 'floor');
      if (fl && !map.room) {
        const fw = fl.m.w || fl.im.width / fl.n, fh = fl.m.h || fl.im.height, hh = LH - GY + 6, w = fw * hh / fh; const off = cam;
        for (let k = Math.floor(off / w); k * w - off < VW; k++) ctx.drawImage(fl.im, 0, 0, fw, fh, k * w - off, GY - 6, w + 1, hh);
      } else {
        const g = ctx.createLinearGradient(0, GY, 0, LH); g.addColorStop(0, 'hsl(' + h + ',22%,40%)'); g.addColorStop(0.18, 'hsl(' + h + ',24%,30%)'); g.addColorStop(1, 'hsl(' + h + ',26%,16%)');
        ctx.fillStyle = g; ctx.fillRect(0, GY, VW, LH - GY);
        ctx.fillStyle = 'hsl(' + ((h + 90) % 360) + ',42%,48%)'; ctx.fillRect(0, GY - 3, VW, 5);
        ctx.fillStyle = 'rgba(255,255,255,.22)'; ctx.fillRect(0, GY - 3, VW, 1.5);
        ctx.fillStyle = 'rgba(0,0,0,.22)';
        for (let i = Math.floor(cam / 38); i * 38 - cam < VW; i++) { const x = i * 38 - cam + hash(i) * 20; ctx.fillRect(x, GY + 8 + hash(i + 40) * 22, 5 + hash(i + 9) * 8, 3); }
      }
      // 블록
      for (const b of M.blocks) {
        const x = b.x0 - cam; if (x > VW + 4 || b.x1 - cam < -4) continue;
        ctx.fillStyle = 'hsl(' + h + ',25%,34%)'; ctx.fillRect(x, b.y, b.x1 - b.x0, GY - b.y);
        ctx.fillStyle = 'hsl(' + h + ',30%,52%)'; ctx.fillRect(x, b.y, b.x1 - b.x0, 4);
        ctx.strokeStyle = 'rgba(0,0,0,.45)'; ctx.lineWidth = 1.5; ctx.strokeRect(x + 0.5, b.y + 0.5, b.x1 - b.x0 - 1, GY - b.y - 1);
        ctx.beginPath(); ctx.moveTo(x + 2, b.y + 6); ctx.lineTo(x + (b.x1 - b.x0) - 2, GY - 3); ctx.moveTo(x + (b.x1 - b.x0) - 2, b.y + 6); ctx.lineTo(x + 2, GY - 3); ctx.stroke();
      }
      // 발판
      const ps = sheet('plat_' + (D.reg + 1), 'plat');
      for (const p of M.plats) {
        if (p.kind !== 'plat') continue;
        const x = p.x0 - cam, w = p.x1 - p.x0; if (x > VW + 4 || x + w < -4) continue;
        if (ps) { const fw = ps.m.w || ps.im.width / ps.n, fh = ps.m.h || ps.im.height, hh = 16, tw = fw * hh / fh; ctx.save(); ctx.beginPath(); ctx.rect(x, p.y - 4, w, hh + 2); ctx.clip(); for (let tx = x; tx < x + w; tx += tw) ctx.drawImage(ps.im, 0, 0, fw, fh, tx, p.y - 4, tw + 0.5, hh); ctx.restore(); continue; }
        ctx.fillStyle = 'rgba(0,0,0,.22)'; ctx.fillRect(x + 3, p.y + 12, w - 6, 5);
        ctx.fillStyle = 'rgba(14,8,26,.78)'; ctx.fillRect(x - 1.5, p.y - 1.5, w + 3, 15);
        const g = ctx.createLinearGradient(0, p.y, 0, p.y + 12); g.addColorStop(0, 'hsl(' + ((h + 85) % 360) + ',48%,66%)'); g.addColorStop(0.22, 'hsl(' + ((h + 85) % 360) + ',40%,52%)'); g.addColorStop(0.3, 'hsl(' + ((h + 20) % 360) + ',34%,44%)'); g.addColorStop(1, 'hsl(' + h + ',30%,26%)');
        ctx.fillStyle = g; ctx.fillRect(x, p.y, w, 12);
        ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fillRect(x, p.y, w, 1.8);
        ctx.fillStyle = 'rgba(0,0,0,.3)'; for (let tx = x + 22; tx < x + w - 6; tx += 24) ctx.fillRect(tx, p.y + 4, 1.2, 8);
        // 끝 마감
        ctx.fillStyle = 'hsl(' + h + ',30%,20%)'; ctx.fillRect(x - 1, p.y, 2.5, 12); ctx.fillRect(x + w - 1.5, p.y, 2.5, 12);
      }
    }

    // 시전 자세: 전조(0~60%)에 몸을 모으고 발동(60~100%)에 터뜨린다 — 스킬마다 자세가 달라서 몸짓만 봐도 무엇인지 보인다
    function castPose(p) {
      const c = p.cast; if (!c) return null;
      const v = SKV[c.s.id] || SKV.slash, q = clamp(c.t / c.dur, 0, 1), f = p.face, o = { sx: 1, sy: 1, rot: 0, dx: 0, dy: 0, spin: 0 };
      const pre = clamp(q / 0.6, 0, 1), post = clamp((q - 0.6) / 0.4, 0, 1);
      switch (v.pose) {
        case 'lunge': o.rot = f * (q < 0.6 ? -0.28 * pre : -0.28 + 0.7 * post); o.sx = 1 + 0.18 * post; o.sy = 1 - 0.1 * post; o.dx = f * (q < 0.6 ? -3 * pre : -3 + 14 * post); break;
        case 'peck': { const b = Math.sin(q * Math.PI * 6); o.rot = f * (0.2 + 0.18 * b); o.dx = f * 3 * (b + 1); o.sy = 1 - 0.07 * (b + 1) / 2; break; }
        case 'spin': o.spin = q * Math.PI * 4; o.sx = 1.08; o.sy = 0.96; break;
        case 'raise': o.sy = 1 + 0.2 * pre - 0.3 * post; o.sx = 1 - 0.1 * pre + 0.16 * post; o.dy = 10 * pre - 8 * post; break;
        case 'sky': o.sy = 1.15; o.sx = 0.92; o.dy = 6 * pre; o.dx = Math.sin(q * 90) * 1.6 * pre; break;
        case 'breath': o.sx = 1 + 0.2 * pre; o.sy = 1 - 0.05 * pre; o.rot = f * (-0.22 * pre + 0.34 * post); o.dx = f * (-2 * pre + 6 * post); break;
        case 'throw': o.rot = f * (-0.35 * pre + 0.55 * post); o.sy = 1 + 0.08 * pre; break;
        case 'guard': o.sy = 0.78 + 0.1 * post; o.sx = 1.18 - 0.05 * post; break;
        case 'charge': o.sy = 0.8 + 0.2 * post; o.sx = 1.2 - 0.12 * post; o.rot = f * 0.15; o.dx = -f * 4 * pre; break;
        case 'storm': o.dy = 14 * Math.min(1, q * 3); o.rot = Math.sin(q * 20) * 0.08; o.sx = 1.1; o.sy = 1.1; o.spin = q * Math.PI * 2; break;
      }
      return o;
    }
    const lerp = (a, b, t) => a + (b - a) * t;
    // 기본 공격 3타 자세(준비 → 타격 → 정리): 1타 가볍게 찌르기 · 2타 반대로 휘두르기 · 3타 크게 모았다가 앞으로 뛰어들며 내려치기
    const ATK_W = [{ sx: 0.97, sy: 1.04, rot: -0.07, dx: -2, dy: 0 }, { sx: 0.96, sy: 1.03, rot: 0.09, dx: -2, dy: 0 }, { sx: 1.1, sy: 0.84, rot: -0.24, dx: -5, dy: 0 }];
    const ATK_S = [{ sx: 1.12, sy: 0.95, rot: 0.12, dx: 5, dy: 0 }, { sx: 1.14, sy: 0.94, rot: -0.16, dx: 7, dy: 0 }, { sx: 1.2, sy: 1.1, rot: 0.34, dx: 15, dy: 4 }];
    function drawChick() {
      const p = P, cam = E.cam;
      const x = p.x - cam;
      let pose = 'idle';
      if (p.dead) pose = 'die'; else if (p.hurtT > 0) pose = 'hurt'; else if (p.cast) pose = 'cast';
      else if (p.atkT > 0) pose = 'atk' + p.atkIdx; else if (!p.on) pose = p.vy < 0 ? 'jump' : 'fall'; else if (p.run > 30) pose = 'run';
      // 그림자(발판 위)
      if (!p.dead) { const sy = (p.on ? p.y : (platBelow(map, p.x, p.y).y)); shadow(x, sy, 15 * clamp(1 - (sy - p.y) / -120, 0.5, 1), 0.3 * clamp(1 + (p.y - sy) / 160, 0.3, 1)); }
      // 분노 오라
      if (E.rageT > 0 && !p.dead) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const rg = ctx.createRadialGradient(x, p.y - 22, 4, x, p.y - 22, 40); rg.addColorStop(0, 'rgba(255,120,100,.55)'); rg.addColorStop(1, 'rgba(255,60,60,0)'); ctx.fillStyle = rg; ctx.fillRect(x - 40, p.y - 62, 80, 80); ctx.restore(); if (!E.low && ((E.t * 8) | 0) !== E.rageN) { E.rageN = (E.t * 8) | 0; newPart('spark', x + E.cam + (rnd() - 0.5) * 26, p.y - 10 - rnd() * 30, 0, -50, 0.5, 7, '#ff8a7a'); } }
      // 보호막 오라
      if ((D.passive === 'shield' || p.shieldT > 0) && !p.dead) {
        const r = 26 + Math.sin(E.t * 4) * 1.5, col = '#6fd6ff';
        ctx.save(); ctx.globalAlpha = p.shieldT > 0 ? 0.55 : 0.28; ctx.strokeStyle = col; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.ellipse(x, p.y - 22, r, r * 1.1, 0, 0, 6.3); ctx.stroke();
        ctx.globalAlpha *= 0.3; ctx.fillStyle = col; ctx.fill(); ctx.restore();
      }
      // 스킬 오라: 시전 중에는 스킬 색 빛이 차오르고(큰 스킬은 빛기둥), 끝난 뒤 잠깐 남는다
      const cid = p.cast ? p.cast.s.id : (p.afterT > 0 ? p.afterId : null);
      if (cid && !p.dead) {
        const v = SKV[cid] || SKV.slash, q = p.cast ? clamp(p.cast.t / p.cast.dur, 0, 1) : 1, a = p.cast ? 0.35 + 0.6 * q : clamp(p.afterT * 2.4, 0, 0.8), R = 34 + v.size * 14;
        ctx.save(); ctx.globalCompositeOperation = 'lighter';
        const g = ctx.createRadialGradient(x, p.y - 22, 3, x, p.y - 22, R); g.addColorStop(0, '#ffffff'); g.addColorStop(0.35, v.col); g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.globalAlpha = a * 0.7; ctx.fillStyle = g; ctx.fillRect(x - R, p.y - 22 - R, R * 2, R * 2);
        if (v.size >= 3 && p.cast) { const w = 10 + 20 * q, g2 = ctx.createLinearGradient(0, p.y - 150, 0, p.y); g2.addColorStop(0, 'rgba(255,255,255,0)'); g2.addColorStop(1, v.col); ctx.globalAlpha = 0.5 * a; ctx.fillStyle = g2; ctx.fillRect(x - w / 2, p.y - 150, w, 150); }
        ctx.restore();
      }
      const o = { flip: p.face < 0 };
      let sx = 1, sy = 1, rot = 0, yy = p.y, fr = 0, dx = 0;
      const sq = p.sq;   // 양수 = 착지 찌그러짐, 음수 = 점프 늘어남
      if (sq > 0) { sx = 1 + sq * 0.14; sy = 1 - sq * 0.12; } else if (sq < 0) { sx = 1 + sq * 0.06; sy = 1 - sq * 0.08; }   // 체구가 출렁이지 않게 약하게(촐싹 방지)
      if (pose === 'run') { const ph = E.t * 11; yy -= Math.abs(Math.sin(ph)) * 1.6; rot = p.face * 0.07; }
      else if (pose === 'idle') { const b = Math.sin(E.t * 2); sy *= 1 + b * 0.008; sx *= 1 - b * 0.005; }
      else if (pose === 'jump') { sy *= 1.03; sx *= 0.98; rot = p.face * -0.05; }
      else if (pose === 'fall') { sy *= 0.99; sx *= 1.01; rot = p.face * 0.08; }
      else if (pose.length === 4 && pose.charAt(0) === 'a') {
        const q = clamp(1 - p.atkT / p.atkDur, 0, 1), W = ATK_W[p.atkIdx] || ATK_W[0], S = ATK_S[p.atkIdx] || ATK_S[0];
        let P0;
        if (q < 0.38) { const t = q / 0.38; P0 = { sx: lerp(1, W.sx, t), sy: lerp(1, W.sy, t), rot: lerp(0, W.rot, t), dx: lerp(0, W.dx, t), dy: 0 }; }
        else { const t = (q - 0.38) / 0.62, e = Math.min(1, t * 2.4), st = t > 0.55 ? (t - 0.55) / 0.45 : 0; P0 = { sx: lerp(lerp(W.sx, S.sx, e), 1, st), sy: lerp(lerp(W.sy, S.sy, e), 1, st), rot: lerp(lerp(W.rot, S.rot, e), 0, st), dx: lerp(lerp(W.dx, S.dx, e), 0, st), dy: lerp(S.dy * e, 0, st) }; }
        sx *= 1 + (P0.sx - 1) * 0.4; sy *= 1 + (P0.sy - 1) * 0.4; rot += p.face * P0.rot; dx += p.face * P0.dx; yy -= P0.dy; fr = Math.floor(q * 3);
      } else if (pose === 'cast') {
        const cp = castPose(p);
        if (cp) { sx *= cp.sx * (cp.spin ? 0.25 + 0.75 * Math.abs(Math.cos(cp.spin)) : 1); sy *= cp.sy; rot += cp.rot; dx += cp.dx; yy -= cp.dy; }
      }
      else if (pose === 'hurt') { rot = -p.face * 0.24; sx *= 1.04; sy *= 0.96; }
      else if (pose === 'die') { rot = -1.4 * p.face; yy = p.y; o.a = 0.92; }
      if (p.djT > 0 && !p.dead && pose !== 'cast') rot += p.face * (1 - p.djT / 0.32) * 6.283;   // 2단 점프: 한 바퀴 빙글
      if (p.inv > 0 && !p.dead && ((E.t * 22) | 0) % 2 === 0 && pose !== 'cast') o.a = 0.45;
      // 👗 [2026-11-13 사장님 「꾸미기를 입으면 가만히 서서 공격」] 꾸미기 스킨은 정지 그림이라 자세별 움직임을 코드로 입힌다(숨쉬기·달릴 때 통통·점프 늘어남·공격 돌진·시전 부풀림·피격 흔들림) + 스킨마다 다른 효과
      if (E.skinPath && !p.dead) {
        const t = E.t, f = p.face, atk = pose.length === 4 && pose.charAt(0) === 'a';
        if (pose === 'idle') { const b = Math.sin(t * 2.6); yy -= (b + 1) * 1.6; sy *= 1 + b * 0.03; sx *= 1 - b * 0.02; rot += Math.sin(t * 1.3) * 0.025; }
        else if (pose === 'run') { const ph = t * 12; yy -= Math.abs(Math.sin(ph)) * 5.5; rot += f * 0.13 + Math.sin(ph) * 0.05; sy *= 1 + Math.sin(ph * 2) * 0.045; sx *= 1 - Math.sin(ph * 2) * 0.03; }
        else if (pose === 'jump') { sy *= 1.1; sx *= 0.93; rot += f * -0.1; }
        else if (pose === 'fall') { sy *= 0.94; sx *= 1.07; rot += f * 0.14; }
        else if (atk) { sx = 1 + (sx - 1) * 2.6; sy = 1 + (sy - 1) * 2.6; rot = rot * 2.4; dx *= 2.8; }
        else if (pose === 'cast') { sx = 1 + (sx - 1) * 2.2; sy = 1 + (sy - 1) * 2.2; rot *= 1.8; yy -= 2 + Math.sin(t * 20) * 1.5; }
        else if (pose === 'hurt') { rot += Math.sin(t * 60) * 0.1; dx += Math.sin(t * 70) * 3; }
        const key = E.skinKey || '', rate = (atk ? 26 : pose === 'run' ? 14 : 8), n = Math.floor(t * rate);
        if (n !== E.skFxN) {
          E.skFxN = n; const cx = x + dx, cy = yy - 24, r2 = () => (rnd() - 0.5) * 2, up = (atk ? 70 : 38);
          if (key === 'sg') { const sp = rnd() < 0.5; newPart(sp ? 'spark' : 'emo', cx + r2() * 22, cy + r2() * 26, r2() * 20, -up * 0.6 - rnd() * 20, 0.8, sp ? 7 : 12, sp ? '#ffe27a' : (rnd() < 0.5 ? '⭐' : '✨')); }
          else if (key === 'pp') { newPart('emo', cx + r2() * 20, cy + 18 + rnd() * 6, r2() * 18, -up - rnd() * 24, 0.9, 10 + rnd() * 5, rnd() < 0.7 ? '🫧' : '💦'); }
          else if (key === 'tf') { newPart('emo', cx + r2() * 26, cy + r2() * 20, r2() * 40, -up * 0.5 - rnd() * 16, 0.8, 12, ['🃏', '♦️', '♠️', '♥️'][(rnd() * 4) | 0]); }
          else if (key === 'boss_sr') { newPart('spark', cx + r2() * 24, cy + 20 + rnd() * 8, r2() * 14, -up * 0.5, 0.9, 9, rnd() < 0.5 ? '#9b5cff' : '#2a1040'); if (rnd() < 0.18) newPart('emo', cx + r2() * 30, cy - 6, r2() * 12, 22, 0.8, 12, '🕸'); }
          else if (key === 'boss_ddo') { const sp = rnd() < 0.6; newPart(sp ? 'spark' : 'emo', cx + r2() * 22, cy + 10 + rnd() * 14, r2() * 22, -up - rnd() * 24, 0.7, sp ? 8 : 12, sp ? '#ff7a3a' : '🔥'); if (rnd() < 0.08) newPart('emo', cx, cy - 22, r2() * 10, -30, 0.9, 13, '☠'); }
          else if (key === 'boss_yj') { const sp = rnd() < 0.5; newPart(sp ? 'spark' : 'emo', cx - f * 16 + r2() * 12, cy + r2() * 16, -f * (30 + rnd() * 30), -up * 0.4 - rnd() * 14, 0.7, sp ? 8 : 12, sp ? '#ffb040' : '🔥'); }
          else if (key === 'boss_tw') { newPart('emo', cx + r2() * 26, cy + r2() * 18, r2() * 16, -up * 0.6 - rnd() * 16, 0.9, 11, rnd() < 0.5 ? '💔' : '🖤'); }
          else { newPart('spark', cx + r2() * 20, cy + r2() * 20, r2() * 20, -up * 0.5, 0.7, 8, '#ffe8a0'); }
        }
      }
      o.sx = sx; o.sy = sy; o.rot = rot;
      const px = x + dx;
      const sh = chickSheetFor(pose);
      const paint = (oo) => {
        if (E.skinPath) { const si = ld(E.skinPath); if (si) { spr(si, px, yy + 2, CHICK_H, oo); return; } }   // 👗 꾸미기 스킨(정지 그림) — 불러오는 동안은 기본 병아리
        if (sh) {
          const fps = sh.m.fps || 10; let f;
          if (pose === 'idle' || pose === 'run') f = Math.floor(E.t * fps); else if (pose === 'hurt') f = 0; else if (pose === 'die') f = Math.min(sh.n - 1, Math.floor(p.deadT < REVIVE_T ? (REVIVE_T - p.deadT) * 4 : 0)); else if (pose === 'cast') f = Math.min(sh.n - 1, Math.floor((p.cast ? p.cast.t / p.cast.dur : 1) * sh.n)); else f = Math.min(sh.n - 1, fr);
          drawSheet(sh, f, px, yy + 1, CHICK_H, oo);
        } else {
          let im = art('chick_' + (pose === 'die' || pose === 'hurt' ? 'hit' : pose === 'cast' ? 'skill' : (pose.length === 4 && pose.charAt(0) === 'a') ? ((p.atkIdx % 2) ? 'atk2' : 'atk1') : 'idle'));
          const has = !!im; if (!im) im = art('chick_idle'); if (!im) im = ld('img/brjang/parts/body_chick/front.png'); if (!im) im = emo('🐥', 40);
          const hk = has ? ({ chick_hit: 1.15, chick_skill: 0.95, chick_atk1: 1.1, chick_atk2: 1.1 }[(/chick_\w+/.exec(im.src || '') || [])[0]] || 1) : 1;
          spr(im, px, yy + 2, CHICK_H * hk, oo);
        }
      };
      paint(o);
      // 맞았을 때 · 스킬 터뜨릴 때 하얗게 번쩍
      const fl = p.hurtT > 0.12 ? 0.7 : (p.cast && p.cast.t / p.cast.dur > 0.55 && p.cast.t / p.cast.dur < 0.8 ? 0.45 : 0);
      if (fl > 0 && !p.dead) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; paint(Object.assign({}, o, { a: fl })); ctx.restore(); }
      // 사망 후 별
      if (p.dead) { const r = ((REVIVE_T - p.deadT) * 2) % 6.28; outText('💫', x + Math.cos(r) * 12, p.y - 52 + Math.sin(r) * 3, 14, '#fff', 'center', 0); }
    }

    function drawMob(m) {
      const cam = E.cam; let x = m.x - cam; if (x < -50 || x > E.VW + 50) return;
      const reg = D.reg + 1, dying = m.st === 'dying', hitting = m.hit > 0;
      let im = art('m' + reg + (hitting || dying ? '_hit' : '_idle')); if (!im) im = art('m' + reg + '_idle'); if (!im) im = emo(['🦐', '🥒', '💬', '🛵', '🐟', '🦆'][D.reg] || '👾', 30);
      let a = 1, sc = m.sc, rot = m.rot || 0, yy = m.y;
      if (m.st === 'spawn') { const q = clamp(m.t / 0.35, 0, 1); a = q; sc *= 0.5 + 0.5 * q; }
      if (dying) a = clamp(1 - m.t / 0.75, 0, 1);
      // 그림자
      if (!dying) { const sy = m.fly ? platBelow(map, m.x, m.y).y : m.y; shadow(x, sy, 11 * m.sc, m.fly ? 0.18 : 0.28); }
      if (m.big && !dying) { const pu = 0.65 + 0.35 * Math.sin(E.t * 5), R = 52 * m.sc; ctx.save(); ctx.globalCompositeOperation = 'lighter'; const gg = ctx.createRadialGradient(x, yy - 20 * m.sc, 6, x, yy - 20 * m.sc, R); gg.addColorStop(0, 'rgba(255,90,130,' + (0.55 * pu) + ')'); gg.addColorStop(0.55, 'rgba(255,170,60,' + (0.22 * pu) + ')'); gg.addColorStop(1, 'rgba(255,60,60,0)'); ctx.fillStyle = gg; ctx.fillRect(x - R, yy - 20 * m.sc - R, R * 2, R * 2); ctx.restore(); }
      if (m.el && !dying) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createRadialGradient(x, yy - 16 * m.sc, 4, x, yy - 16 * m.sc, 34 * m.sc); g.addColorStop(0, 'rgba(255,214,80,.5)'); g.addColorStop(1, 'rgba(255,160,40,0)'); ctx.fillStyle = g; ctx.fillRect(x - 40 * m.sc, yy - 60 * m.sc, 80 * m.sc, 70 * m.sc); ctx.restore(); }
      let sx = 1, sy = 1;
      if (m.fly) { yy += Math.sin(m.ph) * 1.5; rot += Math.sin(m.ph * 1.3) * 0.08; // 날개
        ctx.save(); ctx.globalAlpha = 0.85 * a; ctx.fillStyle = '#e8f6ff'; const fl = Math.sin(E.t * 30 + m.id) * 0.5 + 0.5;
        for (const sd of [-1, 1]) { ctx.beginPath(); ctx.ellipse(x + sd * 12 * m.sc, yy - 22 * m.sc - fl * 4, 9 * m.sc, 4 * m.sc + fl * 3, sd * -0.6, 0, 6.3); ctx.fill(); } ctx.restore(); }
      else if (m.st !== 'spawn' && !dying) { const wk = Math.abs(Math.sin((m.walk || 0) * 0.28)); yy -= wk * 2.2; sy *= 1 - wk * 0.05; rot += Math.sin((m.walk || 0) * 0.28) * 0.06; }
      if (m.sqz > 0.02) { sx *= 1 + m.sqz * 0.18; sy *= 1 - m.sqz * 0.16; }
      if (m.charge > 0) { sx *= 1 + Math.sin(E.t * 50) * 0.05; }
      const sfx = m.fxt > 0 && !dying && !m.boss ? m.fxk : '';
      if (sfx === 'shock') x += (hash((E.t * 60) | 0) - 0.5) * 3;
      if (sfx === 'push') { ctx.save(); ctx.strokeStyle = m.fxc; ctx.lineWidth = 2; ctx.globalAlpha = clamp(m.fxt / 0.3, 0, 1) * 0.8; for (let k = 0; k < 3; k++) { const ly = yy - (8 + k * 9) * sc; ctx.beginPath(); ctx.moveTo(x - m.fxd * 8, ly); ctx.lineTo(x - m.fxd * (22 + k * 5), ly); ctx.stroke(); } ctx.restore(); }
      spr(im, x, yy + 2, 34 * sc, { flip: m.face < 0, a, rot, sx, sy });
      if (sfx === 'burn' || sfx === 'gold' || (sfx === 'shock' && ((E.t * 28) | 0) % 2 === 0)) {   // 불=주황으로 달아오름 · 감전=노랗게 깜빡 · 황금알=금빛
        const t = tinted(im, sfx === 'burn' ? '#ff5a1c' : sfx === 'gold' ? '#ffd23c' : '#fff27a');
        if (t) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; spr(t, x, yy + 2, 34 * sc, { flip: m.face < 0, a: sfx === 'shock' ? 0.8 : 0.3 + 0.25 * Math.abs(Math.sin(E.t * 22)), rot, sx, sy }); ctx.restore(); }
      }
      if (sfx === 'shock') { ctx.save(); ctx.strokeStyle = '#fff6a0'; ctx.lineWidth = 1.6; ctx.globalAlpha = 0.9; for (let k = 0; k < 2; k++) { ctx.beginPath(); let px = x + (k ? 10 : -10) * sc, py = yy - 32 * sc; ctx.moveTo(px, py); for (let j = 0; j < 4; j++) { px += (hash(((E.t * 30) | 0) + j + k * 9) - 0.5) * 14; py += 9 * sc; ctx.lineTo(px, py); } ctx.stroke(); } ctx.restore(); }
      if (hitting && !dying) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; spr(im, x, yy + 2, 34 * sc, { flip: m.face < 0, a: 0.55 * (m.hit / 0.16), rot, sx, sy }); ctx.restore(); }
      if (m.charge > 0) outText('!', x, yy - 40 * m.sc, 16, '#ff5c5c', 'center', 3);
      if (m.big && !dying) {   // 이름표 + 큰 체력바
        const w = 96, bx = x - w / 2, by2 = yy - 40 * m.sc - 12; outText('👹 ' + m.name, x, by2 - 6, 13, '#ffd7df', 'center', 3);
        ctx.fillStyle = 'rgba(0,0,0,.7)'; ctx.fillRect(bx - 2, by2 - 2, w + 4, 10); ctx.fillStyle = '#3a1020'; ctx.fillRect(bx, by2, w, 6);
        const gq = ctx.createLinearGradient(bx, 0, bx + w, 0); gq.addColorStop(0, '#ff4d6d'); gq.addColorStop(1, '#ffb23c'); ctx.fillStyle = gq; ctx.fillRect(bx, by2, w * clamp(m.hp / m.max, 0, 1), 6);
        const left = Math.max(0, Math.ceil((m.ttl || 0) - (E.t - (m.t0 || E.t)))); outText(left + '초', bx + w + 18, by2 + 7, 10, left < 30 ? '#ff8a8a' : '#cfd6ff', 'center', 2);
      } else if (!dying && m.hp < m.max && m.st !== 'spawn') { const w = 26 * m.sc; ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillRect(x - w / 2 - 1, yy - 38 * m.sc - 1, w + 2, 5); ctx.fillStyle = m.el ? '#ffb23c' : '#ef5a6f'; ctx.fillRect(x - w / 2, yy - 38 * m.sc, w * clamp(m.hp / m.max, 0, 1), 3); }
    }
    function drawBossBody() {
      const B = boss; if (!B) return; const bm = B.m, cam = E.cam;
      let im = B.img ? ld('img/brjang/boss/' + B.img + '/front.png') : null; if (!im) im = emo('🐲', 110);
      let a = 1, rot = 0, x = bm.x - cam, y = bm.y + 4 - (B.z || 0), sy = 1;
      if (B.state === 'fight' && B.phase) y += Math.sin(E.t * 24) * 1.2 * B.phase;
      if (B.state === 'dying') { const q = Math.min(1, B.t / 1.6); a = 1 - q; rot = q * 0.9; y += q * 18; }
      if (B.state === 'leave') a = 1 - Math.min(1, B.t / 0.8);
      if (B.state === 'smash' && B.t < 0.5) x -= Math.sin(Math.min(1, B.t / 0.35) * Math.PI) * 60;
      if (B.state === 'intro' && B.t < 0.9) a = Math.min(1, B.t / 0.3); else sy = 1 + Math.sin(E.t * 4) * 0.015;
      const px = B.px || 128;
      shadow(bm.x - cam, bm.y, 50 * px / 128, 0.3);
      const o = { a, rot, sy, flip: false }; if (bm.hit > 0 && ((E.t * 40) | 0) % 2 === 0) o.a = a * 0.6;
      spr(im, x, y, px, o);
    }
    function drawBossGround() {
      const B = boss; if (!B || !B.atk || B.atk.done) return;
      const a = B.atk, q = clamp(a.t / a.dur, 0, 1), c = ctx;
      for (const x of a.pts) {
        const px = x - E.cam, py = GY + 1, r = 48;
        c.save(); c.globalAlpha = 0.2 + 0.3 * q + 0.1 * Math.sin(E.t * 30); c.fillStyle = '#ff3050';
        c.beginPath(); c.ellipse(px, py, r, r * 0.24, 0, 0, 6.3); c.fill();
        c.globalAlpha = 0.9; c.strokeStyle = '#ffd0d8'; c.lineWidth = 1.6; c.beginPath(); c.ellipse(px, py, r * q, r * 0.24 * q, 0, 0, 6.3); c.stroke(); c.restore();
      }
    }
    function drawBossHud(VW) {
      const B = boss, c = ctx, cin = E.cin || 0;
      if (cin > 0) { const hh = LH * 0.1 * cin; c.fillStyle = '#000'; c.fillRect(0, 0, VW, hh); c.fillRect(0, LH - hh, VW, hh); }
      if (!B) return;
      if (B.state === 'intro' && B.t > 0.9) {
        const q = clamp((B.t - 0.9) / 0.35, 0, 1), out = clamp((B.t - (BF_INTRO - 0.4)) / 0.4, 0, 1), a = q * (1 - out);
        const y = LH * 0.46, x0 = (1 - q) * -VW * 0.5;
        c.save(); c.globalAlpha = a * 0.78; c.fillStyle = '#12020a'; c.fillRect(0, y - 40, VW, 80);
        c.fillStyle = '#ff3050'; c.fillRect(0, y - 40, VW, 3); c.fillRect(0, y + 37, VW, 3); c.globalAlpha = a;
        outText('⚠ ' + (B.tag || 'STAGE ' + B.stage + ' BOSS'), VW / 2 + x0, y - 14, 14, '#ff9aaa', 'center', 3);
        outText(B.name, VW / 2 - x0, y + 18, 30, '#ffffff', 'center', 5);
        c.restore();
      }
      if (B.state === 'intro' || B.state === 'leave') return;
      const w = Math.min(300, VW - 36 - (INS && !showHud ? 24 : 0)), x = VW / 2 - w / 2, y = 8 + 14 * cin + 6 + (INS ? 38 : 0), r = clamp(B.hp / B.hpMax, 0, 1);
      c.fillStyle = 'rgba(0,0,0,.72)'; c.fillRect(x - 3, y - 3, w + 6, 18);
      c.fillStyle = B.phase >= 2 ? '#ff2a4a' : B.phase === 1 ? '#ff6a3a' : '#ef3c5a'; c.fillRect(x, y, w * r, 12);
      c.fillStyle = 'rgba(255,255,255,.28)'; c.fillRect(x, y, w * r, 4);
      c.fillStyle = 'rgba(255,255,255,.55)'; c.fillRect(x + w * 0.33 - 1, y - 1, 2, 14); c.fillRect(x + w * 0.66 - 1, y - 1, 2, 14);
      outText(B.name + (B.phase ? '  ' + '🔥'.repeat(B.phase) : '') + (B.clan ? '  ' + (r * 100).toFixed(1) + '%' : ''), VW / 2, y + 30, 13, '#fff', 'center', 3);
    }

    function crescent(c, r0, r1, a0, a1, col, alpha) {
      c.globalAlpha = alpha; c.fillStyle = col;
      c.beginPath(); c.arc(0, 0, r1, a0, a1); c.arc(-(r1 - r0) * 0.45, 0, r0, a1, a0, true); c.closePath(); c.fill();
    }
    function drawFxList() {
      const cam = E.cam, c = ctx;
      for (let i = 0; i < fxs.length; i++) {
        const f = fxs[i], q = clamp(f.t / f.life, 0, 1), fi = f.id ? fxImg(f.id) : null;
        c.save(); c.globalCompositeOperation = 'lighter';
        switch (f.k) {
          case 'swing': {   // 기본 공격 호: 머리가 휘두르고 꼬리가 길게 남는다
            const x = f.x - cam, y = f.y, R = 44 + f.idx * 6, e = 1 - Math.pow(1 - clamp(q * 1.5, 0, 1), 2);
            c.translate(x, y); c.scale(f.face, 1);
            const a0 = f.idx === 1 ? 1.1 : -1.3, a1 = f.idx === 1 ? -1.1 : 1.1, head = a0 + (a1 - a0) * e, dir = a1 > a0 ? 1 : -1;
            c.lineCap = 'round';
            const segs = f.idx === 2 ? 10 : 8;
            for (let k = 0; k < segs; k++) {
              const t0 = head - dir * k * 0.17, t1 = head - dir * (k + 1) * 0.17;
              if ((t0 - a0) * dir < 0) break;
              c.globalAlpha = (1 - k / segs) * (1 - q * q) * 0.95; c.strokeStyle = k < 2 ? '#ffffff' : (f.idx === 2 ? '#ffd27a' : '#ffe9a0'); c.lineWidth = (f.idx === 2 ? 14 : 10) * (1 - k / segs) + 1.5;
              c.beginPath(); c.arc(16, -2, R, t1, t0, dir < 0); c.stroke();
            }
            break; }
          case 'arc': {
            const x = f.x - cam, y = f.y, s = f.r * 1.5;
            c.translate(x, y); c.scale(f.face, 1);
            if (fi) { c.globalAlpha = 1 - q * q; c.translate(f.r * 0.55, 0); c.rotate(-0.6 + q * 1.2); c.drawImage(fi, -s / 2, -s / 2, s, s); }
            else { const e = clamp(q * 1.6, 0, 1), R = f.r * 0.8, kk = f.id === 'slash' && sheet('sk_slash') ? 0.55 : 1; c.rotate(-1.0 + e * 2.0); crescent(c, R * 0.55, R, -0.9, 0.9, f.col, (1 - q) * 0.9 * kk); c.strokeStyle = '#fff'; c.lineWidth = 2.5; c.globalAlpha = (1 - q) * kk; c.beginPath(); c.arc(0, 0, R, -0.8, 0.8); c.stroke(); }
            break; }
          case 'spin': {
            const x = f.x - cam, y = f.y; c.translate(x, y); c.scale(1, 0.62); c.rotate(f.t * 20);
            const R = f.r * 0.9; c.globalAlpha = q < 0.75 ? 0.95 : (1 - q) * 3.8;
            if (fi) c.drawImage(fi, -R, -R, R * 2, R * 2);
            else { c.strokeStyle = f.col; c.lineWidth = 6; c.lineCap = 'round'; for (let r = 0; r < 3; r++) { c.beginPath(); c.arc(0, 0, R, r * 2.1, r * 2.1 + 1.3); c.stroke(); } c.strokeStyle = '#fff'; c.lineWidth = 2; for (let r = 0; r < 3; r++) { c.beginPath(); c.arc(0, 0, R, r * 2.1 + 0.1, r * 2.1 + 1.1); c.stroke(); } }
            break; }
          case 'aoe': {
            const x = f.x - cam, y = f.y;
            if (f.id === 'thunder') {
              c.globalAlpha = q < 0.5 ? 1 : (1 - q) * 2; c.strokeStyle = '#fff'; c.lineWidth = 3; c.shadowColor = f.col; c.shadowBlur = E.low ? 0 : 10; c.lineJoin = 'round';
              c.beginPath(); let yy = -10, xx = x; c.moveTo(xx, yy); const sd = (f.x * 7) | 0; while (yy < y - 4) { yy += 20; xx = x + (hash(sd + (yy | 0)) - 0.5) * 22; c.lineTo(xx, Math.min(yy, y - 4)); } c.stroke(); c.shadowBlur = 0;
            }
            const rr = f.r * (0.4 + 0.8 * Math.min(1, q * 2.2));
            const g = c.createRadialGradient(x, y - 10, 2, x, y - 10, rr); g.addColorStop(0, '#ffffff'); g.addColorStop(0.35, f.col); g.addColorStop(1, 'rgba(0,0,0,0)');
            c.globalAlpha = (1 - q) * 0.9; c.fillStyle = g; c.fillRect(x - rr, y - 10 - rr, rr * 2, rr * 2);
            c.globalAlpha = (1 - q); c.strokeStyle = f.col; c.lineWidth = 2.4; c.beginPath(); c.ellipse(x, y + 1, rr, rr * 0.28, 0, 0, 6.3); c.stroke();
            if (f.id === 'storm') { c.translate(x, y - 20); c.scale(1, 0.6); c.rotate(f.t * 9); c.strokeStyle = f.col; c.lineWidth = 4; c.lineCap = 'round'; for (let r = 0; r < 3; r++) { c.beginPath(); c.arc(0, 0, rr * (0.5 + r * 0.25), r * 1.6, r * 1.6 + 3.2); c.stroke(); } }
            if (fi && f.id !== 'thunder') { c.globalAlpha = (1 - q) * 0.9; const s = rr * 2; c.drawImage(fi, x - s / 2, y - 16 - s / 2, s, s); }
            break; }
          case 'sf': {   // 스킬 그림 시트(4컷)를 크게 — 번쩍이게 lighter 합성
            const sh = sheet(f.sh); if (!sh) break;
            const m = sh.m, fw = m.w || sh.im.width / sh.n, fh = m.h || sh.im.height, fr0 = f.fr0 || 0, nf = Math.max(1, sh.n - fr0);
            const fr = fr0 + Math.min(nf - 1, Math.floor(q * nf)), s = f.w / fw * (f.grow ? 0.6 + 0.4 * Math.min(1, q * 3) : 1);
            const ax = m.anchor ? m.anchor[0] : fw / 2, ay = m.anchor ? m.anchor[1] : fh / 2;
            c.translate(f.x - cam, f.y); if (f.rot) c.rotate(f.rot); if (f.spinr) c.rotate(f.t * 14); c.scale(f.flip ? -1 : 1, f.sq || 1);
            c.globalAlpha = q > 0.8 ? (1 - q) / 0.2 : 1;
            c.drawImage(sh.im, fr * fw, 0, fw, fh, -ax * s, -ay * s, fw * s, fh * s);
            break; }
          case 'circle': {   // 시전 전조 마법진(땅에 눕힌 고리 + 돌아가는 눈금)
            const x = f.x - cam, a = q < 0.15 ? q / 0.15 : q > 0.75 ? (1 - q) / 0.25 : 1, R = f.r * (0.55 + 0.45 * Math.min(1, q * 3));
            c.translate(x, f.y + 1); c.scale(1, 0.32);
            c.globalAlpha = 0.85 * a; c.strokeStyle = f.col; c.lineWidth = 3; c.beginPath(); c.arc(0, 0, R, 0, 6.3); c.stroke();
            c.lineWidth = 1.6; c.beginPath(); c.arc(0, 0, R * 0.68, 0, 6.3); c.stroke();
            c.rotate(f.t * (f.big ? 3 : 2)); c.fillStyle = f.col; for (let k = 0; k < 6; k++) { c.rotate(1.047); c.fillRect(R * 0.68, -1.5, R * 0.3, 3); }
            c.globalAlpha = 0.28 * a; c.beginPath(); c.arc(0, 0, R * 0.9, 0, 6.3); c.fill();
            break; }
          case 'glint': { const x = f.x - cam, y = f.y, a = Math.sin(Math.min(1, q) * Math.PI), L = 26 * a; c.globalAlpha = a; c.strokeStyle = '#fff'; c.lineWidth = 2.4; c.beginPath(); c.moveTo(x - L, y); c.lineTo(x + L, y); c.moveTo(x, y - L * 0.8); c.lineTo(x, y + L * 0.8); c.stroke(); c.strokeStyle = f.col; c.lineWidth = 1.2; c.beginPath(); c.moveTo(x - L * 0.7, y - L * 0.7); c.lineTo(x + L * 0.7, y + L * 0.7); c.moveTo(x - L * 0.7, y + L * 0.7); c.lineTo(x + L * 0.7, y - L * 0.7); c.stroke(); break; }
          case 'wind': { c.translate(f.x - cam, f.y); c.scale(1, 0.5); c.rotate(-f.t * 10); c.strokeStyle = f.col; c.lineCap = 'round'; c.globalAlpha = (1 - q) * 0.8; for (let k = 0; k < 8; k++) { c.rotate(0.785); c.lineWidth = 3 - q * 2; c.beginPath(); c.arc(0, 0, f.r * (0.55 + q * 0.7), 0, 0.4); c.stroke(); } break; }
          case 'reticle': { const a = Math.min(1, q * 4) * (q > 0.85 ? (1 - q) / 0.15 : 1), R = f.r * (1.5 - 0.5 * q); c.translate(f.x - cam, f.y + 1); c.scale(1, 0.3); c.globalAlpha = a; c.strokeStyle = f.col; c.lineWidth = 3; c.beginPath(); c.arc(0, 0, R, 0, 6.3); c.stroke(); c.lineWidth = 2; c.beginPath(); c.arc(0, 0, f.r * 0.5, 0, 6.3); c.stroke(); c.beginPath(); c.moveTo(-R * 1.2, 0); c.lineTo(R * 1.2, 0); c.moveTo(0, -R); c.lineTo(0, R); c.stroke(); break; }
          case 'drop': { c.globalCompositeOperation = 'source-over'; const x = f.x - cam, y = f.y0 + (f.y1 - f.y0) * q * q; const g = c.createLinearGradient(x, y - 60, x, y); g.addColorStop(0, 'rgba(255,120,40,0)'); g.addColorStop(1, f.col); c.fillStyle = g; c.globalAlpha = 0.85; c.fillRect(x - 5, y - 60, 10, 60); c.globalAlpha = 1; c.fillStyle = '#2a1a14'; c.beginPath(); c.arc(x, y, 8, 0, 6.3); c.fill(); c.strokeStyle = f.col; c.lineWidth = 2.5; c.stroke(); c.fillStyle = '#fff'; c.beginPath(); c.arc(x + 3, y - 4, 2.6, 0, 6.3); c.fill(); break; }
          case 'crack': {
            const x = f.x - cam, y = f.y, a = q < 0.6 ? 1 : (1 - q) / 0.4; c.globalCompositeOperation = 'source-over'; c.globalAlpha = 0.85 * a; c.strokeStyle = '#1a0c08'; c.lineWidth = 2.2; c.lineJoin = 'round'; const sd = (f.x * 13) | 0;
            for (let k = 0; k < 7; k++) { const dir = (k / 6 - 0.5) * 2, L = f.w * (0.35 + hash(sd + k) * 0.35); c.beginPath(); c.moveTo(x, y + 2); for (let j = 1; j <= 3; j++) c.lineTo(x + dir * L * j / 3 + (hash(sd + k * 5 + j) - 0.5) * 8, y + 2 + Math.abs(hash(sd + k * 3 + j) - 0.3) * 3 * j); c.stroke(); }
            c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.45 * a; c.fillStyle = f.col; c.beginPath(); c.ellipse(x, y + 2, f.w * 0.5 * (0.6 + q * 0.4), 5, 0, 0, 6.3); c.fill();
            break; }
          case 'bolt': {
            const x = f.x - cam, y = f.y, a = q < 0.45 ? 1 : (1 - q) / 0.55; c.globalAlpha = a; c.lineJoin = 'round'; c.lineCap = 'round';
            const dr = (w, col) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); let yy = -20, xx = x, i = 0; c.moveTo(xx, yy); while (yy < y - 2) { yy = Math.min(y - 2, yy + 22); xx = x + (hash(f.seed + i++ * 7) - 0.5) * 26; c.lineTo(xx, yy); } c.stroke(); };
            if (!E.low) { c.shadowColor = f.col; c.shadowBlur = 14; } dr(7, f.col); c.shadowBlur = 0; dr(3, '#fff');
            break; }
          case 'egg': {
            const x = f.x0 + (f.x1 - f.x0) * q - cam, y = f.y0 + (f.y1 - f.y0) * q - Math.sin(q * Math.PI) * 46, sh = sheet('sk_egg'); c.translate(x, y); c.rotate(q * 10);
            if (sh) { const m = sh.m, fw = m.w || sh.im.width / sh.n, fh = m.h || sh.im.height, s = 36 / fw; c.drawImage(sh.im, 0, 0, fw, fh, -fw * s / 2, -fh * s / 2, fw * s, fh * s); }
            else { c.fillStyle = '#ffd23c'; c.beginPath(); c.ellipse(0, 0, 6, 8, 0, 0, 6.3); c.fill(); }
            break; }
          case 'tornado': { const a = q > 0.8 ? (1 - q) / 0.2 : 1; c.translate(f.x - cam, f.y); c.globalAlpha = a * 0.8; c.strokeStyle = f.col; c.lineCap = 'round'; for (let r = 0; r < 4; r++) { const rr = f.r * (0.35 + r * 0.28) * (0.7 + 0.3 * Math.min(1, q * 3)); c.save(); c.translate(0, -r * 16); c.scale(1, 0.28); c.rotate(f.t * (8 + r * 2)); c.lineWidth = 4 - r * 0.6; c.beginPath(); c.arc(0, 0, rr, 0, 4.2); c.stroke(); c.restore(); } break; }
          case 'dome': { const x = f.x - cam, a = q < 0.2 ? q / 0.2 : (1 - q) / 0.8, R = f.r * (0.6 + 0.4 * Math.min(1, q * 4)); c.globalAlpha = 0.6 * a; c.fillStyle = f.col; c.beginPath(); c.ellipse(x, f.y - 14, R * 0.9, R, 0, Math.PI, 0); c.fill(); c.globalAlpha = a; c.strokeStyle = '#fff'; c.lineWidth = 2; c.beginPath(); c.ellipse(x, f.y - 14, R * 0.9, R, 0, Math.PI, 0); c.stroke(); break; }
          case 'flash': { const x = f.x - cam, r = 26 * (0.6 + q * 0.8), g = c.createRadialGradient(x, f.y, 0, x, f.y, r); g.addColorStop(0, '#fff'); g.addColorStop(0.4, f.col); g.addColorStop(1, 'rgba(0,0,0,0)'); c.globalAlpha = 1 - q; c.fillStyle = g; c.fillRect(x - r, f.y - r, r * 2, r * 2); break; }
          case 'cut': { const L = 26 * Math.min(1, q * 5) + 4, a = 1 - q; c.translate(f.x - cam, f.y); c.rotate(f.ang); c.globalAlpha = a; c.strokeStyle = '#fff'; c.lineWidth = 3; c.lineCap = 'round'; c.beginPath(); c.moveTo(-L, 0); c.lineTo(L, 0); c.stroke(); c.strokeStyle = f.col; c.lineWidth = 7; c.globalAlpha = a * 0.45; c.beginPath(); c.moveTo(-L, 0); c.lineTo(L, 0); c.stroke(); break; }
          case 'dash': {
            const x = f.x - cam, y = f.y - 16; c.globalAlpha = (1 - q) * 0.8; const L = Math.min(f.r, f.r * clamp(f.t / 0.2, 0, 1) + 20);
            const g = c.createLinearGradient(x, 0, x + f.face * L, 0); g.addColorStop(0, f.col); g.addColorStop(1, 'rgba(0,0,0,0)');
            c.fillStyle = g; c.fillRect(Math.min(x, x + f.face * L), y - 7, Math.abs(L), 14);
            break; }
        }
        c.restore();
      }
      // 투사체
      for (const s of shots) {
        const x = s.x - cam, y = s.y;
        c.save(); c.globalCompositeOperation = 'lighter';
        if (s.from === 'e') { const g = c.createRadialGradient(x, y, 1, x, y, 8); g.addColorStop(0, '#fff'); g.addColorStop(0.4, '#ff5c5c'); g.addColorStop(1, 'rgba(255,60,60,0)'); c.fillStyle = g; c.fillRect(x - 9, y - 9, 18, 18); }
        else if (s.id === 'peck') {   // 부리 쐐기: 작고 빠른 주황 화살
          const d = Math.sign(s.vx), g = c.createRadialGradient(x, y, 1, x, y, 9); g.addColorStop(0, '#fff'); g.addColorStop(0.5, s.col); g.addColorStop(1, 'rgba(255,120,0,0)'); c.fillStyle = g; c.fillRect(x - 10, y - 10, 20, 20);
          c.globalCompositeOperation = 'source-over'; c.fillStyle = '#ffe6b8'; c.strokeStyle = '#7a3a00'; c.lineWidth = 1; c.beginPath(); c.moveTo(x + d * 9, y); c.lineTo(x - d * 5, y - 4.5); c.lineTo(x - d * 5, y + 4.5); c.closePath(); c.fill(); c.stroke();
        } else if (s.id === 'fire') {   // 불덩이: 큰 핵 + 길게 늘어진 불꽃 꼬리
          const d = Math.sign(s.vx), tl = 44, g1 = c.createLinearGradient(x, 0, x - d * tl, 0); g1.addColorStop(0, '#ffb03a'); g1.addColorStop(1, 'rgba(255,40,0,0)');
          c.globalAlpha = 0.85; c.fillStyle = g1; c.beginPath(); c.moveTo(x, y - 9); c.lineTo(x - d * tl, y - 2 + Math.sin(s.t * 40) * 3); c.lineTo(x - d * tl, y + 2); c.lineTo(x, y + 9); c.closePath(); c.fill();
          const g = c.createRadialGradient(x, y, 1, x, y, 16); g.addColorStop(0, '#ffffff'); g.addColorStop(0.35, '#ffd060'); g.addColorStop(0.7, s.col); g.addColorStop(1, 'rgba(255,40,0,0)'); c.globalAlpha = 1; c.fillStyle = g; c.fillRect(x - 17, y - 17, 34, 34);
        } else {
          const rr = s.id === 'fire' ? 11 : s.id === 'peck' ? 6 : 8, tl = 22; const g1 = c.createLinearGradient(x, 0, x - Math.sign(s.vx) * tl, 0); g1.addColorStop(0, s.col); g1.addColorStop(1, 'rgba(0,0,0,0)');
          c.globalAlpha = 0.8; c.fillStyle = g1; c.fillRect(Math.min(x, x - Math.sign(s.vx) * tl), y - rr * 0.5, tl, rr);
          const g = c.createRadialGradient(x, y, 1, x, y, rr + 4); g.addColorStop(0, '#fff'); g.addColorStop(0.4, s.col); g.addColorStop(1, 'rgba(0,0,0,0)'); c.globalAlpha = 1; c.fillStyle = g; c.fillRect(x - rr - 4, y - rr - 4, (rr + 4) * 2, (rr + 4) * 2);
        }
        c.restore();
      }
    }
    function drawParts() {
      const lim = E.low ? PMLOW : PMAX, cam = E.cam, c = ctx;
      for (let i = 0; i < lim; i++) {
        const p = parts[i]; if (!p.on) continue; const q = p.t / p.life, x = p.x - cam;
        if (x < -60 || x > E.VW + 60) continue;
        switch (p.k) {
          case 'dot': c.globalAlpha = 1 - q; c.fillStyle = p.c; c.beginPath(); c.arc(x, p.y, p.r * (1 - q * 0.4), 0, 6.3); c.fill(); break;
          case 'dust': c.globalAlpha = (1 - q) * 0.55; c.fillStyle = p.c; c.beginPath(); c.arc(x, p.y, p.r * (0.7 + q * 1.3), 0, 6.3); c.fill(); break;
          case 'spark': { c.globalAlpha = 1 - q; c.strokeStyle = p.c; c.lineWidth = 1.8; const l = p.r * (1 - q * 0.5) / 60; c.beginPath(); c.moveTo(x, p.y); c.lineTo(x - p.vx * l, p.y - p.vy * l); c.stroke(); break; }
          case 'ring': c.globalAlpha = (1 - q) * 0.85; c.strokeStyle = p.c; c.lineWidth = 2.2 * (1 - q) + 0.6; c.beginPath(); c.ellipse(x, p.y, p.r * (0.3 + 0.7 * q), p.r * (0.3 + 0.7 * q) * 0.55, 0, 0, 6.3); c.stroke(); break;
          case 'coin': { const ph = Math.cos(p.t * 12 + p.rot); c.globalAlpha = 1; c.fillStyle = '#ffd23c'; c.strokeStyle = '#a8741a'; c.lineWidth = 1; c.beginPath(); c.ellipse(x, p.y - 3, Math.max(0.8, Math.abs(ph)) * 3.6, 4, 0, 0, 6.3); c.fill(); c.stroke(); break; }
          case 'star': { c.save(); c.globalCompositeOperation = 'lighter'; c.translate(x, p.y); c.rotate(p.rot * 0.2 + q * 1.5); const s = p.r * (q < 0.25 ? q * 4 : 1 - (q - 0.25) * 1.2); c.globalAlpha = 1 - q * 0.6; c.fillStyle = p.c; c.beginPath(); for (let k = 0; k < 8; k++) { const r = k % 2 ? s * 0.28 : s; const a = k * Math.PI / 4; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.fill(); c.restore(); break; }
          case 'flash': { c.save(); c.globalCompositeOperation = 'lighter'; const r = p.r * (0.6 + q * 0.8); const g = c.createRadialGradient(x, p.y, 0, x, p.y, r); g.addColorStop(0, p.c); g.addColorStop(1, 'rgba(0,0,0,0)'); c.globalAlpha = (1 - q); c.fillStyle = g; c.fillRect(x - r, p.y - r, r * 2, r * 2); c.restore(); break; }
          case 'glow': { c.save(); c.globalCompositeOperation = 'lighter'; const r = p.r * (0.7 + 0.5 * Math.sin(q * 3.14)); const g = c.createRadialGradient(x, p.y, 0, x, p.y, r); g.addColorStop(0, p.c); g.addColorStop(1, 'rgba(0,0,0,0)'); c.globalAlpha = 0.55 * (1 - q); c.fillStyle = g; c.fillRect(x - r, p.y - r, r * 2, r * 2); c.restore(); break; }
          case 'beam': { c.save(); c.globalCompositeOperation = 'lighter'; const w = p.r * (1 - q * 0.6), g = c.createLinearGradient(0, p.y - 170, 0, p.y); g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(0.7, p.c); g.addColorStop(1, '#fff'); c.globalAlpha = Math.min(1, (1 - q) * 1.3) * 0.8; c.fillStyle = g; c.fillRect(x - w / 2, p.y - 170, w, 170); c.restore(); break; }
          case 'ghost': { const im = art('chick_idle'); if (im) spr(im, x, p.y + 2, CHICK_H, { a: (1 - q) * 0.4, flip: p.a < 0 }); break; }
          case 'conv': { const e = q * q, cx = p.a - cam, py = p.b + p.vy * (1 - e), px = cx + p.vx * (1 - e); c.save(); c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.3 + 0.7 * q; c.fillStyle = p.c; c.beginPath(); c.arc(px, py, p.r * (1 - q * 0.5), 0, 6.3); c.fill(); c.restore(); break; }
          case 'flame': { c.save(); c.globalCompositeOperation = 'lighter'; const r = p.r * (1 - q * 0.6), g = c.createRadialGradient(x, p.y, 0, x, p.y, r * 1.6); g.addColorStop(0, '#fff2c0'); g.addColorStop(0.4, p.c); g.addColorStop(1, 'rgba(255,40,0,0)'); c.globalAlpha = (1 - q) * 0.9; c.fillStyle = g; c.fillRect(x - r * 1.6, p.y - r * 1.6, r * 3.2, r * 3.2); c.restore(); break; }
          case 'emo': { const im = emo(p.c, Math.round(p.r)); if (im) spr(im, x, p.y + p.r * 0.7, p.r * 1.4, { a: 1 - q }); break; }
          case 'item': { const im = emo(p.c, Math.round(p.r)), al = q > 0.85 ? 1 - (q - 0.85) / 0.15 : 1, pu = 0.75 + 0.25 * Math.sin(p.t * 9);
            c.save(); c.globalCompositeOperation = 'lighter'; const gr = c.createRadialGradient(x, p.y - p.r * 0.5, 0, x, p.y - p.r * 0.5, p.r * (1.6 + (p.rar | 0) * 0.5)); gr.addColorStop(0, p.g || '#fff'); gr.addColorStop(1, 'rgba(0,0,0,0)'); c.globalAlpha = 0.65 * al * pu; c.fillStyle = gr; c.fillRect(x - p.r * 3, p.y - p.r * 3.2, p.r * 6, p.r * 5.4); c.restore();
            if (im) spr(im, x, p.y + p.r * 0.7, p.r * 1.4, { a: al }); break; }
        }
      }
      c.globalAlpha = 1;
    }
    function drawTexts() {
      const cam = E.cam;
      for (let i = 0; i < TMAX; i++) {
        const t = texts[i]; if (!t.on) continue; const q = t.t / t.life;
        const pop = t.kind === 'c' ? 1 + Math.max(0, 0.22 - t.t) * 4 : t.kind === 's' ? 1 + Math.max(0, 0.15 - t.t) * 2.4 : 1;
        ctx.globalAlpha = q > 0.7 ? (1 - q) / 0.3 : 1;
        outText(t.s, t.x - cam, t.y, t.size * pop, t.col, 'center', t.kind === 'c' ? 4 : 3, t.ol);
      }
      ctx.globalAlpha = 1;
    }
    const allies = [];
    function syncParty() {
      const ids = (st.party || []).slice(0, 3), key = ids.map(p => p && p.id).join(',');
      if (key === E.pkey) return; E.pkey = key; allies.length = 0;
      ids.forEach((p, i) => { if (p) allies.push({ ini: Array.from(String(p.n || '?'))[0] || '?', col: GR_COL[p.gr] || GR_COL.normal, x: P.x - 24 * (i + 1), y: P.y, i, hop: 0 }); });
    }
    function drawAllies(dt) {
      for (const a of allies) {
        const tx = P.x - P.face * (26 + a.i * 22), ty = P.on ? P.y : P.y;
        a.x += (tx - a.x) * Math.min(1, 0.07 * 60 * dt * 1.0 + 0.02); a.y += (ty - a.y) * Math.min(1, 0.1);
        const x = a.x - E.cam, y = a.y - 8 - Math.abs(Math.sin(E.t * 6 + a.i)) * 2;
        ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.beginPath(); ctx.ellipse(x, a.y + 1, 7, 1.6, 0, 0, 6.3); ctx.fill();
        ctx.fillStyle = a.col; ctx.strokeStyle = 'rgba(14,10,24,.9)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y - 6, 8, 0, 6.3); ctx.fill(); ctx.stroke();
        outText(a.ini, x, y - 6, 9, '#fff', 'center', 2);
      }
    }
    function drawHud(VW) {
      if (!showHud) return;
      const c = ctx;
      // 체력·마나
      const bw = 112, x = 8, y = 8;
      c.fillStyle = 'rgba(8,6,20,.62)'; c.fillRect(x - 3, y - 3, bw + 6, 33);
      const hr = clamp(P.hp / P.hpMax, 0, 1), mr = clamp(P.mp / P.mpMax, 0, 1);
      c.fillStyle = '#3a1a24'; c.fillRect(x, y, bw, 11); c.fillStyle = P.hpFlash > 0.1 ? '#ffffff' : (hr < 0.3 ? '#ff4d6a' : '#e8445f'); c.fillRect(x, y, bw * hr, 11); c.fillStyle = 'rgba(255,255,255,.28)'; c.fillRect(x, y, bw * hr, 4);
      c.fillStyle = '#16283f'; c.fillRect(x, y + 14, bw, 9); c.fillStyle = '#3f8cff'; c.fillRect(x, y + 14, bw * mr, 9); c.fillStyle = 'rgba(255,255,255,.25)'; c.fillRect(x, y + 14, bw * mr, 3);
      outText('HP ' + fmtNum(P.hp) + '/' + fmtNum(P.hpMax), x + 4, y + 5.5, 8, '#fff', 'left', 2.2);
      outText('MP ' + fmtNum(P.mp), x + 4, y + 18.5, 7, '#cfe1ff', 'left', 2);
      // AUTO 표시
      const au = autoOn();
      c.fillStyle = au ? 'rgba(40,160,90,.85)' : (E.autoWanted ? 'rgba(220,150,30,.85)' : 'rgba(90,100,130,.85)');
      c.fillRect(VW - 58, 8, 50, 16); outText(au ? 'AUTO' : (E.autoWanted ? '수동…' : '수동'), VW - 33, 16.5, 10, '#fff', 'center', 2);
      // 콤보
      if (E.combo >= 3) {
        const pun = 1 + E.comboPunch * 0.35;
        outText(E.combo + ' HIT', VW - 12, 52, 15 * pun, E.combo >= 30 ? '#ff7ad9' : E.combo >= 10 ? '#ffd23c' : '#ffffff', 'right', 3.5);
      }
      // 스킬 칸
      let sx = 8;
      for (let i = 0; i < 8; i++) {
        const s = skills[i], x0 = sx + i * 31, y0 = LH - 36;
        c.fillStyle = 'rgba(8,6,20,.7)'; c.fillRect(x0, y0, 28, 28);
        if (s) {
          const ic = ld('img/brjhunt/ui/skill_' + s.id + '.webp'); if (ic) c.drawImage(ic, x0 + 1, y0 + 1, 26, 26); else { c.fillStyle = s.col; c.fillRect(x0 + 6, y0 + 6, 16, 16); }
          if (slotCd[i] > 0) { c.fillStyle = 'rgba(0,0,0,.62)'; const rr = slotCd[i] / s.cd; c.fillRect(x0 + 1, y0 + 1, 26, 26 * clamp(rr, 0, 1)); }
          else if (P.mp < s.mp) { c.fillStyle = 'rgba(30,50,120,.55)'; c.fillRect(x0 + 1, y0 + 1, 26, 26); }
        }
        const using = s && P.cast && P.cast.i === i || (s && E.usingId === s.id && E.usingT > 0);
        if (using) { c.save(); c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.55 + 0.3 * Math.sin(E.t * 30); c.fillStyle = s.col; c.fillRect(x0, y0, 28, 28); c.restore(); }
        c.strokeStyle = using ? '#fff' : s && slotCd[i] <= 0 && P.mp >= s.mp ? s.col : 'rgba(255,255,255,.25)'; c.lineWidth = using ? 2.2 : 1.5; c.strokeRect(x0 + 0.5, y0 + 0.5, 27, 27);
        outText(String(i + 1), x0 + 5, y0 + 21, 9, '#fff', 'center', 2.4);
        if (using) outText('사용 중', x0 + 14, y0 - 5, 8, s.col, 'center', 2.4, SKV[s.id] ? SKV[s.id].dark : null);
      }
    }
    // 속도선: 가장자리에서 가운데로 모이는 선(논란 폭풍처럼 가장 큰 스킬만)
    function drawSpeedLines(VW) {
      const c = ctx, a = E.lines, cx = VW / 2, cy = LH * 0.5, n = 26;
      c.save(); c.strokeStyle = E.linesCol; c.lineWidth = 1.6; c.globalAlpha = Math.min(0.6, a * 0.7);
      for (let k = 0; k < n; k++) { const ang = hash(k * 13 + ((E.t * 14) | 0)) * 6.283, r0 = LH * (0.5 + hash(k + 7) * 0.2), r1 = r0 + 40 + hash(k * 3) * 60; c.beginPath(); c.moveTo(cx + Math.cos(ang) * r0 * 1.5, cy + Math.sin(ang) * r0); c.lineTo(cx + Math.cos(ang) * r1 * 1.5, cy + Math.sin(ang) * r1); c.stroke(); }
      c.restore();
    }
    function drawCallouts(VW) {
      const c = ctx;
      for (let i = 0; i < callouts.length; i++) {
        const k = callouts[i], q = k.t / k.life, row = k.sub ? 1 : 0;
        const a = q < 0.78 ? 1 : (1 - q) / 0.22, pop = E.reduced ? 1 : q < 0.14 ? 1 + (1 - q / 0.14) * 0.9 : 1 + Math.sin(Math.min(1, (q - 0.14) / 0.3) * Math.PI) * 0.04;
        const fs = (13 + k.size * 6.5) * k.scale * (k.sub ? 0.7 : 1) * pop, y = (boss ? LH * 0.32 : LH * 0.19) + row * 34 + (E.reduced ? 0 : -q * 5);
        c.font = '900 ' + fs + 'px ' + FONT; const tw = c.measureText(k.text).width, ic = ld('img/brjhunt/ui/skill_' + k.id + '.webp'), iw = ic ? fs * 1.25 : 0, tot = tw + iw + (iw ? 8 : 0), x0 = VW / 2 - tot / 2;
        c.save(); c.globalAlpha = a;
        if (k.size >= 2 && !k.sub) {   // 색 띠(컷인): 양끝이 사라지는 사선 띠
          const bw = k.size >= 4 ? VW : tot + 90, bh = fs * 1.55, g = c.createLinearGradient(VW / 2 - bw / 2, 0, VW / 2 + bw / 2, 0);
          g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.2, k.dark); g.addColorStop(0.5, k.col); g.addColorStop(0.8, k.dark); g.addColorStop(1, 'rgba(0,0,0,0)');
          c.globalAlpha = a * (k.size >= 3 ? 0.6 : 0.42); c.fillStyle = g; c.beginPath(); c.moveTo(VW / 2 - bw / 2, y + bh / 2); c.lineTo(VW / 2 - bw / 2 + 16, y - bh / 2); c.lineTo(VW / 2 + bw / 2, y - bh / 2); c.lineTo(VW / 2 + bw / 2 - 16, y + bh / 2); c.closePath(); c.fill(); c.globalAlpha = a;
        }
        if (ic) { c.save(); c.translate(x0 + iw / 2, y); c.rotate(-0.08); c.strokeStyle = k.col; c.lineWidth = 2; c.globalAlpha = a; c.drawImage(ic, -iw / 2, -iw / 2, iw, iw); c.strokeRect(-iw / 2, -iw / 2, iw, iw); c.restore(); }
        c.transform(1, 0, -0.12, 1, 0, 0);
        if (!E.low) { c.shadowColor = k.col; c.shadowBlur = 8 + k.size * 3; }
        outText(k.text + (k.max ? ' ★' : ''), x0 + iw + (iw ? 8 : 0) + tw / 2 + y * 0.12, y, fs, k.col, 'center', Math.max(3, fs / 4), k.dark);
        c.restore();
      }
    }
    function drawChickTag() {   // 병아리 머리 위 작은 이름표(어느 스킬을 쓰는 중인지 시선이 닿는 곳에서도 보이게)
      if (!callouts.length || P.dead) return; const k = callouts[callouts.length - 1]; if (k.t > 0.9) return;
      const x = clamp(P.x - E.cam, 30, E.VW - 30), a = clamp(1 - k.t / 0.9, 0, 1);
      ctx.save(); ctx.globalAlpha = a; outText(k.text, x, P.y - 66 - Math.min(k.t, 0.4) * 22, 11 + k.size, k.col, 'center', 3, k.dark); ctx.restore();
    }
    let vig = null;
    function buildVig() { const VW = E.VW; const g = ctx.createRadialGradient(VW / 2, LH * 0.55, LH * 0.5, VW / 2, LH * 0.55, Math.max(VW, LH) * 0.78); g.addColorStop(0, 'rgba(8,6,20,0)'); g.addColorStop(1, 'rgba(8,6,20,.34)'); vig = g; }
    function preloadSheets() {   // 그림 목록(manifest)이 오면 쓸 스킬 시트를 미리 읽어 둔다(첫 시전부터 큰 그림으로 나오게)
      if (!MAN || E.preSheets) return; E.preSheets = true;
      for (const n of ['fxImpact', 'fxCrit', 'fxDust']) sheet(n);
      for (let i = 0; i < 8; i++) { const k = skills[i]; if (k) { sheet('sk_' + k.id); } }
      for (const id of SKILL_IDS) if (E.castLog[id]) sheet('sk_' + id);
    }
    function draw() {
      const c = ctx, VW = E.VW, s = E.scale; if (!E.cssW) return;
      if (!E.preSheets && MAN) preloadSheets();
      c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, canvas.width, canvas.height);
      c.save(); c.scale(s, s);
      const sh = E.reduced ? 0 : E.shake, z = 1 + (E.reduced ? 0 : E.zoom), zx = E.zoom > 0.004 && E.zax ? clamp(E.zax, 0, VW) : VW / 2, zy = E.zoom > 0.004 && E.zay ? E.zay : LH * 0.62;
      c.translate(zx, zy); c.scale(z, z); c.translate(-zx, -zy);
      if (sh > 0.05) c.translate((rnd() - 0.5) * sh * 2, (rnd() - 0.5) * sh * 1.4);
      drawBg(VW); drawTerrain(VW); drawInsBack(VW); drawBossGround();
      if (E.dim > 0.01) { c.fillStyle = 'rgba(' + E.dimCol + ',' + E.dim.toFixed(3) + ')'; c.fillRect(-80, -50, VW + 160, LH + 100); }   // 큰 스킬: 배경이 어두워져 스킬 빛이 산다
      for (let i = 0; i < mobs.length; i++) { const m = mobs[i]; if (!m.boss) { drawMob(m); if (m.frz > 0 && m.st !== 'dying') { const fx = m.x - E.cam; ctx.save(); ctx.globalAlpha = 0.5; ctx.fillStyle = '#9fe8ff'; ctx.beginPath(); ctx.ellipse(fx, m.y - 12 * m.sc, 15 * m.sc, 18 * m.sc, 0, 0, 6.3); ctx.fill(); ctx.globalAlpha = 0.9; ctx.strokeStyle = '#e8fbff'; ctx.lineWidth = 1.5; ctx.stroke(); ctx.restore(); } } }
      if (boss) drawBossBody();
      drawAllies(0.016);
      drawChick();
      drawFxList(); drawParts(); drawTexts(); drawInsFront(VW); drawChickTag();
      c.restore();
      if (E.tint > 0) { c.globalAlpha = Math.min(0.2, E.tint * 0.2); c.fillStyle = E.tintCol; c.fillRect(0, 0, canvas.width, canvas.height); c.globalAlpha = 1; }
      if (E.flash > 0) { c.globalAlpha = Math.min(0.5, E.flash) * (E.reduced ? 0.35 : 1); c.fillStyle = E.flashCol; c.fillRect(0, 0, canvas.width, canvas.height); c.globalAlpha = 1; }
      c.save(); c.scale(s, s);
      if (vig) { c.fillStyle = vig; c.fillRect(0, 0, VW, LH); }
      if (E.lines > 0.02 && !E.low && !E.reduced) drawSpeedLines(VW);
      drawHud(VW); drawBossHud(VW); drawInsHud(VW); drawCallouts(VW);
      if (E.paused) { c.fillStyle = 'rgba(0,0,0,.45)'; c.fillRect(0, 0, VW, LH); outText('일시정지  (P)', VW / 2, LH / 2, 22, '#fff', 'center', 4); }
      c.restore();
    }

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
      E.cam = clamp(E.cam, 0, Math.max(0, map.W - E.VW));
    }

    // ---------- 구동 ----------
    function loop(ts) {
      E.raf = 0; if (!E.running || E.destroyed) return;
      const dt = Math.min(0.05, Math.max(0.001, (ts - E.last) / 1000 || 0.016)); E.last = ts;
      E.dtAvg = E.dtAvg * 0.95 + dt * 0.05;
      if (!E.low && E.dtAvg > 0.034) { if (++E.lowN > 90) { E.low = true; E.cssW = 0; } } else if (E.lowN > 0) E.lowN--;
      if ((E.frames & 31) === 0) measure();
      advance(dt); draw(); E.frames++;
      E.raf = requestAnimationFrame(loop);
    }
    function start() {
      if (E.running || E.destroyed || manual) return;
      if (hasDoc && document.hidden) return;
      E.running = true; E.last = performance.now(); E.raf = requestAnimationFrame(loop);
    }
    function stop() { const was = E.running; E.running = false; if (E.raf) cancelAnimationFrame(E.raf); E.raf = 0; if (was) flushReport(); }
    function onVis() { if (document.hidden) stop(); else if (E.vis) start(); }
    let io = null, onResize = null;
    if (hasDoc) {
      document.addEventListener('visibilitychange', onVis);
      if (typeof window !== 'undefined') { onResize = () => { E.cssW = 0; measure(); }; window.addEventListener('resize', onResize); }
      try { io = new IntersectionObserver(es => { E.vis = es[es.length - 1].isIntersecting; if (E.vis) start(); else stop(); }); io.observe(canvas); } catch (e) { }
    }

    function setState(s) {
      s = s || {};
      const prevStage = st.stage;
      st.stage = N(s.stage) || 1; st.region = String(s.region || ''); st.rec = N(s.rec_power != null ? s.rec_power : s.rec); st.kpmGiven = N(s.kpm_model != null ? s.kpm_model : s.kpm); st.kpm = st.kpmGiven || 100;
      st.party = Array.isArray(s.party) ? s.party : [];
      const c = s.combat || {};
      C = { atk: Math.max(1, N(c.atk) || 40), hp: Math.max(1, N(c.hp) || 400), def: Math.max(0, N(c.def) || 0), crit: clamp(N(c.crit != null ? c.crit : 5), 0, 100), critdmg: Math.max(100, N(c.critdmg != null ? c.critdmg : 150)), acc: Math.max(1, N(c.acc) || 100), mp: Math.max(1, N(c.mp) || 100), mpregen: N(c.mpregen != null ? c.mpregen : 4), power: N(c.power) };
      const m = s.mon || {};
      MON = { name: String(m.name || '몬스터'), hp: Math.max(1, N(m.hp) || 900), atk: Math.max(0, N(m.atk != null ? m.atk : 60)), def: N(m.def), eva: Math.max(0, N(m.eva != null ? m.eva : 90)), gold: N(m.gold) };
      const sk = s.skills || {}, act = Array.isArray(sk.active) ? sk.active : [];
      for (let i = 0; i < 8; i++) { const n = normSkill(act[i]), o = skills[i]; if (n && (!o || o.id !== n.id)) slotCd[i] = 0.3; skills[i] = n; }
      skills.passive = sk.passive && SKD[sk.passive] ? sk.passive : null;
      derive(); applyCombat(); syncParty(); E.preSheets = false;
      // 이미 나와 있는 몹에 새 체력 비율을 적용(처치 속도가 상태 변경에 맞게)
      for (const mm of mobs) if (!mm.boss && mm.st !== 'dying') { const fr = mm.hp / mm.max; mm.max = Math.max(1, D.mobHp * (mm.big ? (mm.hpMult || 22) : mm.el ? 2.6 : 1)); mm.hp = mm.max * fr; }
      if (E.inited && st.stage > prevStage && !INS) { E.levelT = 2.0; ring(P.x, P.y - 4, '#ffe14a', 80, 0.7); poof(P.x, P.y - 20, '#ffe14a', 14, 130); newPart('beam', P.x, P.y, 0, 0, 1.0, 30, '#ffe14a'); emit('levelup', {}); }
      E.inited = true;
      if (s.boss && !boss && !st.boss && !INS) startChallenge(s.boss);
      else if (s.boss && boss) { st.boss = s.boss; }
      else if (!s.boss && boss && !boss.inst && !boss.res && (boss.state === 'intro' || boss.state === 'fight')) { boss.state = 'leave'; boss.t = 0; }   // 판정을 못 받았으면(서버 오류) 연출만 접는다
    }
    function statsNow() {
      const win = Math.min(60, Math.max(10, E.t)); let n = 0;
      for (let i = E.killLog.length - 1; i >= 0 && E.killLog[i] > E.t - win; i--) n++;
      return {
        kills: E.kills, t: E.t, kpm: n / win * 60, kpmTotal: E.t > 0 ? E.kills / E.t * 60 : 0, hp: P.hp, hpMax: P.hpMax, mp: P.mp, mpMax: P.mpMax, auto: autoOn(), autoWanted: E.autoWanted,
        combo: E.combo, comboMax: E.comboMax, alive: P.dead ? false : true, dead: P.dead, deaths: E.deaths, x: P.x, y: P.y, on: P.on, plat: P.on ? P.plat.id : -1, face: P.face,
        mobs: aliveCount(), cam: E.cam, VW: E.VW, boss: boss ? boss.state : null, ratio: D.ratio, mobHp: D.mobHp, map: map.name, mapW: map.W, cd: slotCd.slice(), runSecs: E.runAcc, pendingKills: E.repKills, low: E.low, paused: E.paused, teleports: AI.teleports,
        casting: P.cast ? P.cast.s.id : null, usingId: E.usingId, reduced: E.reduced, dim: E.dim, zoom: E.zoom, callouts: callouts.length,
        inst: INS ? { kind: INS.kind, phase: INS.phase, wave: INS.wave, waves: INS.waves, total: INS.total, dmg: INS.dmg, left: INS.left, hits: INS.hits, res: INS.res, t: INS.t, items: INS.items.length, doorOpen: INS.doorOpen, locked: INS.locked, boss: boss ? boss.state : null, hpFrac: boss ? boss.hp / boss.hpMax : null } : null
      };
    }
    derive(); applyCombat(); measure(); buildVig();
    // 첫 화면이 비어 보이지 않게 가까운 곳에 몹을 미리 깐다
    for (let i = 0; i < 6; i++) { const m = spawnMob(); if (m) { m.st = 'patrol'; m.t = 0; } }

    const inst = {
      setState, start, stop, resize() { E.cssW = 0; measure(); },
      destroy() {
        flushReport(); E.destroyed = true; stop();
        if (hasDoc) { document.removeEventListener('visibilitychange', onVis); if (onResize) window.removeEventListener('resize', onResize); if (keyDown) { window.removeEventListener('keydown', keyDown); window.removeEventListener('keyup', keyUp); window.removeEventListener('blur', blurAll); } }
        if (io) try { io.disconnect(); } catch (e) { }
        for (const k in listeners) delete listeners[k];
      },
      on(name, cb) { (listeners[name] = listeners[name] || []).push(cb); return () => { const a = listeners[name]; if (a) { const i = a.indexOf(cb); if (i >= 0) a.splice(i, 1); } }; },
      tick(dt) { advance(dt); draw(); E.frames++; },
      sim(sec, dt) { dt = dt || 1 / 30; for (let t = 0; t < sec - 1e-9; t += dt) advance(dt); },
      stats: statsNow, input, setAuto, getAuto: () => E.autoWanted, isAutoActive: autoOn,
      potion(kind, pct) {   // 🧪 물약 — 서버가 허락한 뒤에만 부른다
        pct = clamp(N(pct), 0, 1); if (P.dead || !pct) return;
        if (kind === 'mp') { const v = Math.round(P.mpMax * pct); P.mp = Math.min(P.mpMax, P.mp + v); say('+' + fmtNum(v) + ' MP', P.x, P.y - PH - 8, 'h', 15, '#7fb8ff'); ring(P.x, P.y - 18, '#6fa8ff', 46, 0.45); for (let d = 0; d < (E.low ? 4 : 9); d++) newPart('spark', P.x + (rnd() - 0.5) * 26, P.y - 8 - rnd() * 30, (rnd() - 0.5) * 40, -60 - rnd() * 50, 0.6, 7, '#9cc8ff'); }
        else { const v = Math.round(P.hpMax * pct); P.hp = Math.min(P.hpMax, P.hp + v); say('+' + fmtNum(v), P.x, P.y - PH - 8, 'h', 16, '#7dff9a'); ring(P.x, P.y - 18, '#6fe89a', 46, 0.45); for (let d = 0; d < (E.low ? 4 : 9); d++) newPart('spark', P.x + (rnd() - 0.5) * 26, P.y - 8 - rnd() * 30, (rnd() - 0.5) * 40, -60 - rnd() * 50, 0.6, 7, '#9dffbe'); }
      },
      setParts(o) {   // {head:'crown', face:'sunglasses', neck:'scarf', back:'cape'} — 슬롯마다 하나
        const out = []; if (o && typeof o === 'object') for (const sl of ['back', 'neck', 'face', 'head']) { const k = o[sl]; if (typeof k === 'string' && PARTS[k] && PARTS[k].slot === sl) out.push({ slot: sl, key: k }); }
        E.parts = out;
      },
      setSkin(p) { { const m = (typeof p === 'string') ? /^img\/brjang\/skins\/([a-z_]+)\/front\.png$/.exec(p) : null; E.skinPath = m ? p : null; E.skinKey = m ? m[1] : ''; } },
      summonElite, dropFx, hasElite: () => !!(E.elite && E.elite.st !== 'dying'), clearElite() { if (E.elite) { E.elite.st = 'dying'; E.elite.t = 0; E.elite = null; } },
      startChallenge, bossResult, startInstance, instanceResult, skipInstance, abortInstance, setHidden(b) { b = !!b; if (b && !E.hidden) flushReport(); E.hidden = b; }, setPaused, setHud(b) { opts.hud = b; }, setKeys(b) { E.keysOff = !b; if (!b) blurAll(); },
      flush: flushReport, setTimeScale(v) { E.timeScale = v; },
      debug: {
        map: () => map, mobs: () => mobs, P, E, AI, D, skills, slotCd, spawnMob, shots: () => shots,
        setPos(x, y) { P.x = x; if (y != null) P.y = y; P.vx = P.vy = 0; const pl = platBelow(map, x, P.y); if (Math.abs(pl.y - P.y) < 1) { P.on = true; P.plat = pl; P.lastPlat = pl.id; } },
        manifest: () => MAN, anch: () => ANCH, clearMobs() { mobs.length = 0; E.spawnT = 1e9; }, spawnPause(b) { E.spawnT = b ? 1e9 : 0; },
        callouts: () => callouts.slice(), castLog: () => E.castLog, ins: () => INS, fxs: () => fxs, parts: () => parts, texts: () => texts, setLow(b) { E.low = !!b; E.cssW = 0; },
        genMap, setMap, lastReport: null, hurt: (d) => hurtPlayer(d, P.x + 20), killPlayer: () => { P.hp = 0; die(); }, keys: () => Object.assign({}, Hh)
      }
    };
    return inst;
  }

  const BrjArena = { create, genMap, version: 2, consts: { calRatio, LH, GY, GRAV, JUMP_V, RUN_V, PW, PH, CAL_TTK, REACH, MAX_MOBS } };
  root.BrjArena = BrjArena;
  if (typeof module !== 'undefined' && module.exports) module.exports = BrjArena;
})(typeof window !== 'undefined' ? window : globalThis);
