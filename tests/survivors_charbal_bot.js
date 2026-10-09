/* 흐접새우 서바이벌 — 캐릭터 성능 측정용 정책 봇 (survivors_charbal_sim.py 가 페이지 안에 꽂아 돌린다)
   [2026-10-09 사장님 지시 "엄장신 너무 구리다는의견이 나왔는데 검증"] 17~18명 전원을 같은 조건으로 재기 위한 자동 플레이.
   - 실제 게임 코드(update(dt) · pick · start)를 그대로 부른다. draw() 는 부르지 않는다.
   - 사람이 아닌 봇이라 절대 수치는 약하다. 목적은 캐릭터끼리의 상대 비교다.
   - 캐릭터별 예외는 절대 넣지 않는다 — 점수표·이동 규칙은 모든 캐릭터에게 똑같이 적용된다(CH.k 로 갈라 쓰는 곳 없음).
     (시작 무기 CH.w 는 「sigonly」 정책이 「내 시작 무기」를 가리키는 데만 쓴다.)
   - 정책 난수는 게임 난수(Math.random)와 따로 쓴다(정책이 게임의 난수 흐름을 건드리지 않는다). 같은 시드 = 같은 결과.
   정책
     full    : 이동(위협 회피 + 경험치 보석·아이템 줍기) + 한 가지 점수표로 카드 선택
     sigonly : 이동은 같고, 카드는 시작 무기를 키우는 것(레벨업·단계업·각성 짝 패시브 1단계)만. 다른 무기는 얻지 않는다. 나머지는 중립 패시브.
*/
(function () {
'use strict';
const X = window.__p6x, XX = window.__cbx;
if (!X || !XX) throw new Error('측정 훅(__p6x/__cbx)이 없다');

// ============================================================================================================
// 상수 — 카드 점수표 (높을수록 먼저 고른다). 캐릭터별 예외 없음.
// ============================================================================================================
const CARD = {
  tierAwake: 100,        // ✨ 각성한 무기의 단계 강화
  tierMaster: 96,        // 🏅 Lv8 무기의 마스터 단계 강화
  weaponUp: 88,          // 가진 무기 레벨업
  weaponUpNear: 6,       // …가진 무기가 Lv5 이상이면 가산(각성 가까움)
  weaponNewFirst: 90,    // 새 무기 — 무기가 NEW_FIRST_N 개 미만일 때(초반엔 가짓수를 늘린다)
  NEW_FIRST_N: 3,
  weaponNew: 62,         // 새 무기 — 그 뒤
  pairKey: 34,           // 가진 무기(Lv5 이상, 아직 각성 안 함)의 각성 짝 패시브를 처음 얻을 때 가산
  pairKeyEarly: 14,      // …무기가 Lv5 미만일 때
  // 패시브 [처음 점수, 레벨당 감소] — 처음 몇 단계가 가장 값지다(체감). 받는 피해 깎기·최대 HP 는 작은 피해가 쏟아지는 이 게임에서 일찍 값지다.
  passive: {
    arm: [92, -8], hp: [92, -10], might: [80, -2], cd: [80, -3], amt: [78, -6], area: [74, -3],
    rev: [72, 0], study: [64, -2], spd: [62, -4], mag: [60, -3], crit: [58, -3], pspd: [54, -3], vamp: [52, -4],
    turtle: [66, -10], glass: [46, -2], dur: [44, -3], luck: [42, -3],
  },
  passiveDefault: 40,
  transcend: 60,         // 🌟 만렙 패시브 초월
  relic: 58,             // 🏺 유물(시그니처 유물 포함 — 똑같이 본다)
  trade: 38,             // ⚖ 거래(얻는 만큼 잃는다)
  small: { ramen: 56, hp: 52, spd: 50, mag: 48, crit: 44, chk: 34 },
  smallDefault: 40,
  consumable: { shield: 54, pulse: 48, feast: 30, dice: 16 },
  heal: 20,              // 치킨 한 조각
  // HP 가 낮으면 회복 카드를 먼저
  lowHp1: 0.5, lowHp2: 0.3,
  lowHealBonus: 70, lowFeastBonus: 60, lowHpPassiveBonus: 20, lowHpSmallBonus: 20,
};
// 「sigonly」 정책 — 시작 무기 하나의 성장만 본다
const SIG = {
  own: 100,              // 시작 무기 레벨업 · 단계업
  pairOnce: 90,          // 시작 무기의 각성 짝 패시브(1단계만 — 각성 열쇠)
  pairMore: -50,         // 짝 패시브를 1단계 넘어서 올리지는 않는다
  neutral: { rev: 70, hp: 60, arm: 55, spd: 50, vamp: 38, turtle: 34 },   // 중립 패시브(공격력을 안 올린다)
  smallNeutral: { hp: 45, spd: 40 },
  neutralPt: { hp: 40, spd: 36, arm: 38 },
  other: 5,              // 그 밖(공격력 패시브·유물·거래 …) — 어쩔 수 없을 때만
  shield: 30,
  lowHealBonus: 70, lowFeastBonus: 60,
};

// ============================================================================================================
// 상수 — 이동 규칙 (위협 회피 + 줍기). 값이 클수록 그 일을 더 중요하게 본다.
// ============================================================================================================
const MOVE = {
  every: 2,                       // 몇 프레임마다 방향을 다시 고르나(dt=1/30 이면 15Hz)
  horScale: 1,                    // 내다보는 시간 전체의 배율(민감도 점검용)
  horE: [0.14, 0.32, 0.55],       // 몸 닿기(잡몹·보스)를 내다보는 시간(초)
  horEW: [1.0, 0.85, 0.6],        // 먼 미래일수록 덜 믿는다
  horS: [0.12, 0.25, 0.4, 0.55, 0.75, 1.0],   // 날아오는 탄을 내다보는 시간(탄은 곧게 날아가니 더 멀리 본다)
  scan: 1500,                     // 이 거리 안의 위협·줍기만 본다(화면 밖에서 오는 적도 봐야 다가가 싸운다)
  hitCost: 3.5,                   // 몸이 닿는 위치로 가면 드는 값(기본)
  nearMargin: 34,                 // 몸 바깥 이만큼 안이면 아슬아슬 값
  nearCost: 0.55,
  bossMargin: 50,                 // 보스는 아슬아슬 값이 이만큼 더 바깥에서 시작한다
  aheadR: 360,                    // 가는 방향 앞쪽에 적이 몰려 있으면 값 — 열린 쪽으로 간다
  aheadCost: 0.8,
  gap: 70,                        // 가장 가까운 적의 몸 바깥 거리가 이보다 멀면 다가간다(짧은 사거리 무기도 맞히도록 — 도망만 다니면 짧은 무기가 벌을 받는다)
  engage: 1.3,                    // …다가가는 끌림의 세기
  stick: 0.10,                    // 가던 방향 유지 보너스(떨림 방지 · 늘 움직인다 — 서 있으면 조준탄을 맞는다)
  shotHit: 2.6, shotMargin: 14,   // 날아오는 탄
  hazMargin: 14, boomMargin: 10,
  telegraph: 1.6,                 // 예고 원·선·부채꼴에 들어가는 값(기본)
  gemGain: 0.62, gemR: 150,
  chickGain: 2.6, chickR: 420,
  chestGain: 3.4, chestR: 900,
  magnetGain: 0.7, bombGain: 0.5, itemR: 500,
};

// ============================================================================================================
// 작은 도구
// ============================================================================================================
function mulberry32(a) { return function () { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const R2 = v => Math.round(v * 100) / 100;
const hpRatio = () => { const p = X.S.p; return p.mhp > 0 ? Math.max(0, p.hp) / p.mhp : 0; };

let CFG = null, PRNG = null;
const M = {};     // 지표 상태
let prevDir = -1, frame = 0, stall = 0;

// ============================================================================================================
// 카드 선택
// ============================================================================================================
function ownedWeaponCount() { return Object.keys(X.S.w).length; }
function pairNeededBy(passKey) {      // 이 패시브가 짝인 가진 무기들(아직 각성 전)
  const S = X.S, out = [];
  for (const w in S.w) if (X.WEAP[w] && X.WEAP[w].pair === passKey && !S.ev[w]) out.push(w);
  return out;
}
function scoreFull(o) {
  const S = X.S, hp = hpRatio();
  let s = 0;
  switch (o.t) {
    case 'wt': s = S.ev[o.w] ? CARD.tierAwake : CARD.tierMaster; break;
    case 'w':
      if (o.l > 0) s = CARD.weaponUp + (o.l >= 5 ? CARD.weaponUpNear : 0);
      else s = ownedWeaponCount() < CARD.NEW_FIRST_N ? CARD.weaponNewFirst : CARD.weaponNew;
      break;
    case 'p': {
      s = CARD.passive[o.k] != null ? CARD.passive[o.k][0] + CARD.passive[o.k][1] * XX.pv(o.k) : CARD.passiveDefault;
      if (XX.pv(o.k) === 0 && XX.evLeft() > 0) {          // 각성 열쇠: 가진 무기의 짝 패시브
        const ws = pairNeededBy(o.k);
        if (ws.length) s += ws.some(w => S.w[w] >= 5) ? CARD.pairKey : CARD.pairKeyEarly;
      }
      if (hp < CARD.lowHp1 && (o.k === 'hp' || o.k === 'vamp')) s += CARD.lowHpPassiveBonus * (hp < CARD.lowHp2 ? 1.5 : 1);
      break; }
    case 'pt': s = CARD.transcend; break;
    case 'rl': s = CARD.relic; break;
    case 'tr': s = CARD.trade; break;
    case 'sm':
      s = CARD.small[o.r] != null ? CARD.small[o.r] : CARD.smallDefault;
      if (hp < CARD.lowHp1 && o.r === 'hp') s += CARD.lowHpSmallBonus;
      break;
    case 'co':
      s = CARD.consumable[o.r] != null ? CARD.consumable[o.r] : 20;
      if (o.r === 'feast' && hp < CARD.lowHp1) s += CARD.lowFeastBonus * (hp < CARD.lowHp2 ? 1.3 : 1);
      break;
    case 'heal':
      s = CARD.heal + (hp < CARD.lowHp1 ? CARD.lowHealBonus * (hp < CARD.lowHp2 ? 1.3 : 1) : 0);
      break;
    default: s = 10;
  }
  return s;
}
function scoreSig(o) {
  const S = X.S, hp = hpRatio(), W = X.CH.w;       // W: 시작 무기(「내 시작 무기」를 가리키는 데만 쓴다)
  const pair = X.WEAP[W] ? X.WEAP[W].pair : null;
  switch (o.t) {
    case 'wt': return o.w === W ? SIG.own : SIG.other;
    case 'w': return o.k === W ? SIG.own : -100;       // 다른 무기는 얻지 않는다(미리 봉인해 두었으니 보통 안 나온다)
    case 'p':
      if (o.k === pair) return XX.pv(o.k) === 0 ? SIG.pairOnce : SIG.pairMore;
      return SIG.neutral[o.k] != null ? SIG.neutral[o.k] + (hp < CARD.lowHp1 && o.k === 'hp' ? CARD.lowHpPassiveBonus : 0) : SIG.other;
    case 'pt': return SIG.neutralPt[o.p] != null ? SIG.neutralPt[o.p] : SIG.other;
    case 'sm': return SIG.smallNeutral[o.r] != null ? SIG.smallNeutral[o.r] + (hp < CARD.lowHp1 && o.r === 'hp' ? CARD.lowHpSmallBonus : 0) : SIG.other;
    case 'co':
      if (o.r === 'feast') return 10 + (hp < CARD.lowHp1 ? SIG.lowFeastBonus : 0);
      if (o.r === 'shield') return SIG.shield;
      return SIG.other;
    case 'heal': return 12 + (hp < CARD.lowHp1 ? SIG.lowHealBonus : 0);
    default: return SIG.other;
  }
}
function chooseCard(cards) {
  const f = CFG.policy === 'sigonly' ? scoreSig : scoreFull;
  let best = null, bs = -1e9;
  for (const o of cards) { const s = f(o) + PRNG() * 0.01; if (s > bs) { bs = s; best = o; } }   // 같은 점수면 정책 난수로(결정론)
  return best;
}

// ============================================================================================================
// 이동 — 여덟 방향(키보드) 중 하나를 고른다. 후보마다 「앞으로 0.5초쯤 갔을 때」의 위험·이득을 어림해 가장 좋은 쪽.
// ============================================================================================================
const SQ = Math.SQRT1_2;
const DIRS = [[1, 0], [SQ, SQ], [0, 1], [-SQ, SQ], [-1, 0], [-SQ, -SQ], [0, -1], [SQ, -SQ]];
const KEYS = [{ KeyD: true }, { KeyD: true, KeyS: true }, { KeyS: true }, { KeyA: true, KeyS: true }, { KeyA: true }, { KeyA: true, KeyW: true }, { KeyW: true }, { KeyD: true, KeyW: true }];
const ND = DIRS.length, NE = MOVE.horE.length, NS = MOVE.horS.length;
const MAXT = 512;
// 위협(몸 닿기): 위치·속도·합친 반지름·가중치
const tx = new Float64Array(MAXT), ty = new Float64Array(MAXT), tvx = new Float64Array(MAXT), tvy = new Float64Array(MAXT), tR = new Float64Array(MAXT), tW = new Float64Array(MAXT), tM = new Float64Array(MAXT), tB = new Uint8Array(MAXT);
const cost = new Float64Array(ND), gain = new Float64Array(ND);
const comp = { E: new Float64Array(ND), A: new Float64Array(ND), G: new Float64Array(ND), S: new Float64Array(ND), H: new Float64Array(ND), T: new Float64Array(ND), P: new Float64Array(ND) };   // 디버깅용 — 항목별 합
const hxE = new Float64Array(NE * ND), hyE = new Float64Array(NE * ND), hxS = new Float64Array(NS * ND), hyS = new Float64Array(NS * ND);     // 후보 방향 × 시간대별 내 예상 위치
const HE = new Float64Array(NE), HS = new Float64Array(NS);   // 이번 결정의 시간대(초)
let DBG = null;

function playerSpeed(S, p) {
  const CH = X.CH;
  let k = 1 + 0.08 * XX.pv('spd') + (CH.spd || 0) + (CH.shv && S.dT > 0 ? X.SHV.spd : 0) - 0.05 * XX.pv('turtle') + (S.spr > 0 ? 0.3 : 0);
  if (p.slow > 0) k *= 0.6;
  return p.sp * Math.max(0.3, k);
}
function segDist2(px, py, ax, ay, bx, by) {      // 점-선분 거리^2
  const abx = bx - ax, aby = by - ay, l2 = abx * abx + aby * aby;
  let t = l2 > 0 ? ((px - ax) * abx + (py - ay) * aby) / l2 : 0; t = t < 0 ? 0 : t > 1 ? 1 : t;
  const qx = ax + abx * t - px, qy = ay + aby * t - py; return qx * qx + qy * qy;
}

function decide() {
  const S = X.S, p = S.p, px = p.x, py = p.y, pr = p.r, mhp = Math.max(1, p.mhp);
  const v = playerSpeed(S, p);
  const scan2 = MOVE.scan * MOVE.scan;
  const hurtAmt = d => 0.6 + 6 * d / mhp;                               // 한 방의 무게(최대 HP 대비)
  const KIND = XX.KIND;
  const hs = MOVE.horScale;
  for (let k = 0; k < NE; k++) { HE[k] = MOVE.horE[k] * hs; for (let i = 0; i < ND; i++) { hxE[k * ND + i] = px + DIRS[i][0] * v * HE[k]; hyE[k * ND + i] = py + DIRS[i][1] * v * HE[k]; } }
  for (let k = 0; k < NS; k++) { HS[k] = MOVE.horS[k] * hs; for (let i = 0; i < ND; i++) { hxS[k * ND + i] = px + DIRS[i][0] * v * HS[k]; hyS[k * ND + i] = py + DIRS[i][1] * v * HS[k]; } }
  for (const key in comp) comp[key].fill(0);
  gain.fill(0);
  // ----- 적(몸 닿기) 모으기
  let nT = 0;
  for (const e of X.enemies.a) {
    if (!e.on) continue;
    const dx = px - e.x, dy = py - e.y, d2 = dx * dx + dy * dy;
    if (d2 > scan2) continue;
    if (e.fear > 0 || e.eg === 1) continue;                             // 겁먹은 적·알은 해가 없다
    const d = Math.sqrt(d2) || 1;
    let sp = e.sp * (e.slow > 0 ? 0.55 : 1);
    if (e.st > 0) sp = 0;
    if (e.boss && e.fx > 0) sp *= 3.2;                                  // 보스 돌진
    else if (!e.boss && e.ph === 2) sp = 0;                             // 돌진 중인 잡몹은 아래 선분으로 따로 본다
    if (e.kb > 0 && !e.boss) sp = 0;
    if (nT < MAXT) {
      tx[nT] = e.x; ty[nT] = e.y; tvx[nT] = dx / d * sp; tvy[nT] = dy / d * sp;
      tR[nT] = e.r + pr; tW[nT] = hurtAmt(e.dmg) * (e.boss ? 1.15 : 1);
      tM[nT] = MOVE.nearMargin + (e.boss ? MOVE.bossMargin : 0); tB[nT] = e.boss ? 1 : 0;      // 보스는 더 멀리서 피한다 · 다가갈 목표로 삼지 않는다
      nT++;
    }
  }
  const hitMul = 1 - 0.8 * (p.inv > 0 ? Math.min(1, p.inv / 0.45) : 0);       // 무적이 남았으면 몸 닿기 값을 줄인다
  const cE = comp.E, cA = comp.A, cG = comp.G;
  // ----- E: 몸 닿기 (예상 위치에서)
  for (let k = 0; k < NE; k++) {
    const tau = HE[k], wk = MOVE.horEW[k];
    for (let i = 0; i < ND; i++) {
      const qx = hxE[k * ND + i], qy = hyE[k * ND + i];
      let c = 0;
      for (let j = 0; j < nT; j++) {
        const ddx = qx - (tx[j] + tvx[j] * tau), ddy = qy - (ty[j] + tvy[j] * tau), dd2 = ddx * ddx + ddy * ddy, R = tR[j], nm = tM[j], lim = R + nm;
        if (dd2 < lim * lim) {
          const gap = Math.sqrt(dd2) - R;
          if (gap < 0) c += MOVE.hitCost * tW[j] * hitMul;
          else { const f = (nm - gap) / nm; c += MOVE.nearCost * tW[j] * f * f; }
        }
      }
      cE[i] += c * wk;
    }
  }
  // ----- A: 가는 쪽 앞의 밀집 / G: 가장 가까운 적이 너무 멀면 다가감
  if (nT > 0) {
    const kk = NE - 1, tau = HE[kk], aR2 = MOVE.aheadR * MOVE.aheadR;
    for (let j = 0; j < nT; j++) {
      const ex = tx[j] - px, ey = ty[j] - py, d2 = ex * ex + ey * ey;
      if (d2 > aR2 || d2 < 1) continue;
      const d = Math.sqrt(d2), f = tW[j] / (1 + (d * d) / (120 * 120)), ux = ex / d, uy = ey / d;
      for (let i = 0; i < ND; i++) { const c = DIRS[i][0] * ux + DIRS[i][1] * uy; if (c > 0) cA[i] += MOVE.aheadCost * f * c * c; }
    }
    for (let i = 0; i < ND; i++) {
      const qx = hxE[kk * ND + i], qy = hyE[kk * ND + i]; let mg = 1e9;
      for (let j = 0; j < nT; j++) { if (tB[j]) continue; const g = Math.hypot(qx - (tx[j] + tvx[j] * tau), qy - (ty[j] + tvy[j] * tau)) - tR[j]; if (g < mg) mg = g; }
      if (mg > MOVE.gap) cG[i] += MOVE.engage * Math.min(1, (mg - MOVE.gap) / 150);
    }
  }
  // ----- S: 적 탄(곧게 날아간다)
  const cS = comp.S, sR = pr + 6;
  for (const b of X.eshots.a) {
    if (!b.on) continue;
    const dx0 = b.x - px, dy0 = b.y - py; if (dx0 * dx0 + dy0 * dy0 > scan2) continue;
    const w = hurtAmt(b.d);
    for (let k = 0; k < NS; k++) {
      const tau = HS[k]; if (tau > b.life) break;
      const sx = b.x + b.vx * tau, sy = b.y + b.vy * tau, lim = sR + MOVE.shotMargin, wk = 1 - 0.35 * (k / (NS - 1));
      for (let i = 0; i < ND; i++) {
        const ddx = hxS[k * ND + i] - sx, ddy = hyS[k * ND + i] - sy, dd2 = ddx * ddx + ddy * ddy;
        if (dd2 < lim * lim) { const gap = Math.sqrt(dd2) - sR; cS[i] += wk * w * (gap < 0 ? MOVE.shotHit : MOVE.nearCost * (1 - gap / MOVE.shotMargin)); }
      }
    }
  }
  // ----- H: 가만히 있는 위험(버섯·독가스)
  const cH = comp.H;
  for (const pool of [X.hazards, X.clouds]) {
    const rr = pool === X.hazards ? 8 : 20, mg = MOVE.hazMargin;
    for (const h of pool.a) {
      if (!h.on) continue;
      const dx0 = h.x - px, dy0 = h.y - py; if (dx0 * dx0 + dy0 * dy0 > scan2) continue;
      const w = hurtAmt(h.d), R = rr + pr, lim = R + mg;
      for (let k = 0; k < NE; k++) for (let i = 0; i < ND; i++) {
        const ddx = hxE[k * ND + i] - h.x, ddy = hyE[k * ND + i] - h.y, dd2 = ddx * ddx + ddy * ddy;
        if (dd2 < lim * lim) { const gap = Math.sqrt(dd2) - R; cH[i] += MOVE.horEW[k] * w * (gap < 0 ? MOVE.hitCost : MOVE.nearCost * (1 - gap / mg)); }
      }
    }
  }
  // ----- T: 예고(원·선·부채꼴) — 터지는 시각에 그 안에 있으면 맞는다
  const cT = comp.T;
  for (const b of S.ebooms) {
    if (!b) continue;
    const urg = 1 / (0.35 + Math.max(0, b.t)), w = MOVE.telegraph * (0.6 + 6 * b.d / mhp) * Math.min(2.2, urg), R = b.R + pr + MOVE.boomMargin;
    for (let k = 0; k < NE; k++) for (let i = 0; i < ND; i++) {
      const ddx = hxE[k * ND + i] - b.x, ddy = hyE[k * ND + i] - b.y;
      if (ddx * ddx + ddy * ddy < R * R) cT[i] += MOVE.horEW[k] * w * (HE[k] >= b.t - 0.12 ? 1 : 0.45);
    }
  }
  for (const b of S.beams) {
    if (!b || b.fl > 0) continue;
    const ax = b.x, ay = b.y, bx = b.x + b.ax * b.L, by = b.y + b.ay * b.L;
    const urg = 1 / (0.35 + Math.max(0, b.t)), w = MOVE.telegraph * (0.6 + 6 * b.d / mhp) * Math.min(2.2, urg), R = pr + 11 + 12;
    for (let k = 0; k < NE; k++) for (let i = 0; i < ND; i++) {
      if (segDist2(hxE[k * ND + i], hyE[k * ND + i], ax, ay, bx, by) < R * R) cT[i] += MOVE.horEW[k] * w * (HE[k] >= b.t - 0.12 ? 1 : 0.45);
    }
  }
  const sector = (ox, oy, ang, half, rad, t, d) => {          // 보스 숨결·포토카드 부채꼴
    const urg = 1 / (0.35 + Math.max(0, t)), w = MOVE.telegraph * (0.6 + 6 * d / mhp) * Math.min(2.2, urg);
    for (let k = 0; k < NE; k++) for (let i = 0; i < ND; i++) {
      const ddx = hxE[k * ND + i] - ox, ddy = hyE[k * ND + i] - oy, dd = Math.hypot(ddx, ddy);
      if (dd > rad + pr) continue;
      let da = Math.atan2(ddy, ddx) - ang; da = Math.atan2(Math.sin(da), Math.cos(da));
      if (Math.abs(da) < half + (dd > 1 ? Math.atan2(pr + 8, dd) : 3)) cT[i] += MOVE.horEW[k] * w * (HE[k] >= t - 0.12 ? 1 : 0.45);
    }
  };
  if (S.cone && S.cone.e && S.cone.e.on) sector(S.cone.e.x, S.cone.e.y, S.cone.a, S.cone.w, S.cone.R, S.cone.t, S.cone.d);
  if (S.cardW && S.cardW.e && S.cardW.e.on) sector(S.cardW.e.x, S.cardW.e.y, S.cardW.a, (S.cardW.n - 1) / 2 * S.cardW.sp + 0.06, S.cardW.L, S.cardW.t, S.cardW.e.dmg * 0.55);
  for (const e of X.enemies.a) {                              // 돌진하는 잡몹(말파이트·헤카림)의 직선 길
    if (!e.on || e.boss || !(e.ph === 1 || e.ph === 2)) continue;
    const K = KIND[e.ki]; if (!K || !(K.charge || K.cav)) continue;
    const len = K.cav ? 640 : 520, ax = e.x, ay = e.y, bx = e.x + e.ax * len, by = e.y + e.ay * len, R = pr + e.r + 14;
    const w = MOVE.telegraph * (0.6 + 6 * e.dmg / mhp);
    for (let k = 0; k < NE; k++) for (let i = 0; i < ND; i++) if (segDist2(hxE[k * ND + i], hyE[k * ND + i], ax, ay, bx, by) < R * R) cT[i] += MOVE.horEW[k] * w * 0.9;
  }
  // ----- P: 줍기(끌림) — 가까운 보석일수록 · 값이 클수록 · 그쪽으로 얼마나 다가가나(진행률)
  const kE = (NE - 1) * ND, stepLen = Math.max(1, v * HE[NE - 1]), cP = comp.P;
  const pull = (gx, gy, wgt) => {
    const d0 = Math.hypot(gx - px, gy - py);
    for (let i = 0; i < ND; i++) { const d1 = Math.hypot(gx - hxE[kE + i], gy - hyE[kE + i]); cP[i] += wgt * Math.max(-1, Math.min(1, (d0 - d1) / stepLen)); }
  };
  for (const g of X.gems.a) {
    if (!g.on) continue;
    const dx = g.x - px, dy = g.y - py, d2 = dx * dx + dy * dy; if (d2 > scan2) continue;
    pull(g.x, g.y, MOVE.gemGain * Math.sqrt(Math.min(60, g.v)) * 0.55 / (1 + d2 / (MOVE.gemR * MOVE.gemR)));
  }
  const hp = hpRatio();
  for (const it of X.items.a) {
    if (!it.on) continue;
    const d = Math.hypot(it.x - px, it.y - py);
    if (it.k === 'chest') pull(it.x, it.y, MOVE.chestGain / (1 + d / MOVE.chestR));
    else if (it.k === 'chicken') pull(it.x, it.y, MOVE.chickGain * Math.pow(1 - hp, 2) / (1 + d / MOVE.chickR) + 0.05);
    else if (it.k === 'magnet') pull(it.x, it.y, MOVE.magnetGain / (1 + d / MOVE.itemR));
    else if (it.k === 'bomb') pull(it.x, it.y, MOVE.bombGain * (S.ne > 40 ? 1.4 : 0.5) / (1 + d / MOVE.itemR));
  }
  // ----- 고르기
  let bi = 0, bs = -1e18;
  for (let i = 0; i < ND; i++) {
    cost[i] = comp.E[i] + comp.A[i] + comp.G[i] + comp.S[i] + comp.H[i] + comp.T[i];
    gain[i] = comp.P[i];
    let stick = 0;
    if (prevDir >= 0) { const dd = Math.min((i - prevDir + ND) % ND, (prevDir - i + ND) % ND); stick = dd === 0 ? MOVE.stick : dd === 1 ? MOVE.stick * 0.4 : 0; }
    const sc = gain[i] - cost[i] + stick + PRNG() * 1e-4;
    if (sc > bs) { bs = sc; bi = i; }
  }
  if (CFG.debug) DBG = { t: S.t, pick: bi, nT, v, cost: Array.from(cost), gain: Array.from(gain), comp: Object.fromEntries(Object.entries(comp).map(([k, a]) => [k, Array.from(a, R2)])) };
  return bi;
}

// ============================================================================================================
// 지표
// ============================================================================================================
function resetMetrics() {
  Object.assign(M, {
    series: { k: [], lv: [], hp: [] }, cp: {}, lv5: null, lv10: null, minHp: 1, minHpT: 0, bosses: [], bossRefs: [], nextMin: 1,
    steps: 0, ended: null, endT: null, nextTrace: 0,
  });
  const D = XX.dmg; D.taken = 0; D.hits = 0; D.t5 = 0; D.by = {}; D.n = {}; D.log = []; D.logOn = !!(CFG && CFG.trace); M.trace = [];
}
function snap() { const S = X.S; return { t: R2(S.t), k: S.kills, lv: S.lv, hp: R2(hpRatio()) }; }
function sample() {
  const S = X.S, p = S.p, t = S.t;
  if (S.lv >= 5 && M.lv5 === null) M.lv5 = R2(t);
  if (S.lv >= 10 && M.lv10 === null) M.lv10 = R2(t);
  const r = p.hp / p.mhp; if (r < M.minHp) { M.minHp = r; M.minHpT = t; }
  if (CFG.trace && t >= (M.nextTrace || 0)) {
    M.nextTrace = t + 2; let near = 0, ne = 0;
    for (const e of X.enemies.a) { if (!e.on) continue; ne++; if ((e.x - p.x) ** 2 + (e.y - p.y) ** 2 < 200 * 200) near++; }
    M.trace.push([R2(t), R2(r), ne, near, Math.round(p.x), Math.round(p.y), prevDir, S.lv]);
  }
  while (t >= M.nextMin * 60) {          // 분마다 한 줄 + 3·5·10·15분 시점 지표
    const m = M.nextMin++, s = snap();
    M.series.k.push(s.k); M.series.lv.push(s.lv); M.series.hp.push(s.hp);
    if (m === 3 || m === 5 || m === 10 || m === 15) M.cp['m' + m] = s;
  }
  // 보스 추적 — 쓰러졌는지(hp<=0) 물러났는지 구분한다
  for (const ref of M.bossRefs) {
    if (ref.done) continue;
    const e = ref.e;
    if (e.sn !== ref.sn) { ref.done = true; ref.fate = 'gone'; continue; }
    if (!e.on) { ref.done = true; ref.fate = e.hp <= 0 ? 'killed' : 'left'; ref.t1 = R2(t); }
    else ref.hpf = e.hp / e.mhp;
  }
}
function trackBosses() {        // 결정 틱마다 새 보스를 등록
  const S = X.S;
  for (const e of X.enemies.a) {
    if (!e.on || !e.boss) continue;
    if (M.bossRefs.some(r => r.sn === e.sn)) continue;
    M.bossRefs.push({ e, sn: e.sn, key: e.boss, t0: R2(S.t), mhp: Math.round(e.mhp), hpf: 1, done: false, fate: null, t1: null });
  }
}
function finalRow() {
  const S = X.S, p = S.p;
  const dmgBy = {}; let dealt = 0;
  for (const k in S.dmgBy) { dealt += S.dmgBy[k]; }
  const top = Object.entries(S.dmgBy).sort((a, b) => b[1] - a[1]).slice(0, 8);
  for (const [k, v] of top) dmgBy[k] = Math.round(v);
  const sigW = X.CH.w, sigDealt = S.dmgBy[sigW] || 0;
  const weapons = Object.keys(S.w).map(k => ({ k, l: S.w[k], ev: S.ev[k] ? 1 : 0, tier: S.tier[k] || 0 }));
  const cp = M.cp;
  const g = (m, f) => (cp['m' + m] ? cp['m' + m][f] : null);
  return {
    end_t: R2(S.t), ended: M.ended, dead: M.ended === 'dead',
    kills: S.kills, lv: S.lv, hp_end: R2(hpRatio()), mhp: Math.round(p.mhp),
    k3: g(3, 'k'), lv3: g(3, 'lv'), hp3: g(3, 'hp'),
    k5: g(5, 'k'), lv5: g(5, 'lv'), hp5: g(5, 'hp'),
    k10: g(10, 'k'), lv10: g(10, 'lv'), hp10: g(10, 'hp'),
    k15: g(15, 'k'), lv15: g(15, 'lv'), hp15: g(15, 'hp'),
    dmg5: R2(XX.dmg.t5), dmg_taken: R2(XX.dmg.taken), hits: XX.dmg.hits, min_hp: R2(M.minHp), min_hp_t: R2(M.minHpT),
    hit_src: Object.fromEntries(Object.entries(XX.dmg.by).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => [k, R2(v)])),
    hit_n: Object.fromEntries(Object.entries(XX.dmg.n).sort((a, b) => b[1] - a[1]).slice(0, 8)),
    t_lv5: M.lv5, t_lv10: M.lv10,
    weapons, ps: Object.assign({}, S.ps), rel: Object.assign({}, S.rel), tr: Object.assign({}, S.tr), sm: Object.assign({}, S.sm), syn: S.synOn.slice(), pt: Object.assign({}, S.pt),
    rev_used: S.revUsed > 0, evolved: Object.keys(S.ev),
    dealt: Math.round(dealt), sig_share: dealt > 0 ? R2(sigDealt / dealt) : null, dmg_by: dmgBy,
    bosses: M.bossRefs.map(r => ({ k: r.key, t0: r.t0, t1: r.t1, fate: r.fate || (r.done ? 'gone' : 'alive'), hpf: R2(r.hpf), mhp: r.mhp })),
    series: M.series, steps: M.steps,
    trace: CFG.trace ? M.trace : undefined, hit_log: CFG.trace ? XX.dmg.log : undefined,
  };
}

// ============================================================================================================
// 시작 · 돌리기
// ============================================================================================================
function applyParams(params) {      // 「--param MOVE.hitCost=3 CARD.passive.arm=90」 — 정책 민감도 점검용(결과 줄에 그대로 남는다)
  const roots = { MOVE, CARD, SIG };
  for (const path in (params || {})) {
    const parts = path.split('.'); let o = roots[parts[0]];
    if (!o) throw new Error('모르는 정책 상수 ' + path);
    for (let i = 1; i < parts.length - 1; i++) { o = o[parts[i]]; if (o == null) throw new Error('모르는 정책 상수 ' + path); }
    const last = parts[parts.length - 1];
    if (!(last in o) && parts.length < 3) throw new Error('모르는 정책 상수 ' + path);
    o[last] = Number(params[path]);
  }
}
function init(cfg) {
  CFG = Object.assign({ policy: 'full', cap: 900, dt: 1 / 30 }, cfg);
  applyParams(CFG.params);
  Math.random = mulberry32(CFG.seed >>> 0);                         // 게임 난수 — 이 판의 시드
  PRNG = mulberry32((CFG.seed ^ 0x9e3779b9) >>> 0);                // 정책 난수 — 게임 난수와 따로
  const k = CFG.char;
  const c = X.CHARS.find(x => x.k === k); if (!c) throw new Error('없는 캐릭터 ' + k);
  if (c.shop) X.SRVUNL.add(k);                                      // 🍘 상점 캐릭터는 서버 구매 목록(메모리)으로 연다
  if (c.boss) { const g = X.getProg(); g.bk[k] = 1; X.setProg(g); }  // 🐲 보스 캐릭터는 처치 기록(bk)으로 연다
  X.CH_set(k);
  XX.RES.quiet = true;                                              // 이어하기 저장 끔(측정에 쓸모없고 느리다)
  resetMetrics(); prevDir = -1; frame = 0; stall = 0;
  X.start();
  if (X.state !== 'play') throw new Error('시작이 안 됨: ' + X.state);
  const S = X.S;
  if (CFG.policy === 'sigonly') {                                   // 시작 무기 말고 다른 무기는 카드 풀에서 뺀다(게임의 봉인 장치 사용)
    S.banned = Object.keys(X.WEAP).filter(w => w !== X.CH.w);
  }
  return { char: k, w: X.CH.w, mhp: S.p.mhp, low: X.LOW, spawn: XX.SPAWN_R, view: [Math.round(XX.VW), Math.round(XX.VH)] };
}

function run(opts) {
  opts = opts || {};
  const t0 = performance.now(), maxMs = opts.maxMs || 4000;
  const dt = CFG.dt, every = MOVE.every;
  for (;;) {
    const st = X.state;
    if (st === 'result') { M.ended = X.S.won ? 'won' : 'dead'; M.endT = X.S.t; return { done: true, row: finalRow() }; }
    if (st === 'lvup') {
      const o = chooseCard(X.CUR);
      X.pick(o);
      prevDir = -1; frame = 0; stall = 0;
      continue;
    }
    if (st !== 'play') {                                            // 상자 · 일시정지 → 다시 시작
      X.resume();
      if (X.state === st && ++stall > 20) throw new Error('멈춤: state=' + st);
      prevDir = -1; frame = 0;
      continue;
    }
    stall = 0;
    const S = X.S;
    if (S.t >= CFG.cap) { M.ended = 'cap'; M.endT = S.t; return { done: true, row: finalRow() }; }
    if (performance.now() - t0 > maxMs) return { done: false, prog: snap() };
    if (frame % every === 0) {
      trackBosses();
      const d = decide();
      prevDir = d; X.keys = KEYS[d];
    }
    frame++;
    X.update(dt);
    M.steps++;
    sample();
  }
}

window.__cb = { init, run, CARD, SIG, MOVE, decide, chooseCard, snap: () => snap(), dbg: () => DBG };
})();
