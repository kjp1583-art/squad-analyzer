/* 흐접새우 서바이벌 — 보스전(1:1) 측정용 봇 (survivors_bossduel_sim.py 가 survivors_charbal_bot.js 다음에 꽂아 돌린다)
   [2026-10-17 태웅 씩씩 박치기 개편] 「한 캐릭터가 보스 한 마리를 혼자 상대하면 얼마나 걸리고 얼마나 아픈가」를 같은 정책 봇·같은 시드로 잰다.
   - 이동은 charbal 봇의 decide()를 그대로 쓴다(캐릭터별 예외 없음). 카드 선택은 없다 — 무기는 시작 무기 하나를 정해 둔 레벨로 쥐여 준다.
   - 잡몹 스폰·보스 소환 졸개는 끈다(보스 하나만). 시각은 S.t=t0 로 맞춘다(보스 체력·공격력이 시간에 따라 오른다).
   - 지표: 처치 시간 · 받은 피해 · 사망 여부 · 제한 시간에 보스 체력이 얼마 남았나.
*/
(function () {
'use strict';
const X = window.__p6x, XX = window.__cbx, C = window.__cb;
let CF = null, boss = null, frame = 0, prev = -1, dmg0 = 0;
const R2 = v => Math.round(v * 100) / 100;

function init(cfg) {
  CF = Object.assign({ t0: 300, boss: 'sr', lv: 5, ev: 0, cap: 240, dt: 1 / 30, summon: 0 }, cfg);
  C.init({ char: CF.char, seed: CF.seed, policy: 'sigonly', cap: 99999, dt: CF.dt, params: {}, trace: false, rel: {}, preset: null });
  const S = X.S, w = X.CH.w;
  window.__duelQuiet = true;                                        // waveSpawn 을 끈다(훅은 sim 이 꽂는다)
  for (const e of X.enemies.a) e.on = false;
  S.t = CF.t0; S.nextBoss = Infinity; S.nextMini = Infinity;
  S.w[w] = CF.lv; if (CF.ev) S.ev[w] = 1;
  if (X.synCalc) X.synCalc();
  S.p.hp = S.p.mhp;
  boss = X.spawnBoss(CF.boss);
  if (!boss) throw new Error('보스를 못 냈다');
  if (!CF.summon) boss.atk = (boss.atk || []).filter(a => a !== 'summon');
  boss.hp = boss.mhp = boss.mhp * (CF.hpMul || 1);
  XX.dmg.taken = 0; XX.dmg.hits = 0; XX.dmg.by = {}; XX.dmg.n = {};
  frame = 0; prev = -1;
  return { char: CF.char, w, mhp: S.p.mhp, bossHp: Math.round(boss.mhp), bossR: boss.r };
}

function run(opts) {
  const t0 = performance.now(), maxMs = (opts && opts.maxMs) || 3000, every = C.MOVE.every, dt = CF.dt, S = X.S, tStart = CF.t0;
  for (;;) {
    const st = X.state;
    if (st === 'result') return fin('dead');
    if (st === 'lvup') { X.pick(C.chooseCard(X.CUR)); prev = -1; frame = 0; continue; }
    if (st !== 'play') { X.resume(); prev = -1; frame = 0; continue; }
    if (!boss.on) return fin(boss.hp <= 0 ? 'killed' : 'left');
    if (S.t - tStart >= CF.cap) return fin('timeout');
    if (performance.now() - t0 > maxMs) return { done: false, prog: { t: R2(S.t - tStart), hpf: R2(boss.hp / boss.mhp) } };
    if (frame % every === 0) { const d = C.decide(); prev = d; X.keys = C.KEYS[d]; }
    frame++;
    X.update(dt);
  }
}
function fin(how) {
  const S = X.S, p = S.p, D = XX.dmg;
  const hit = {}; for (const k in D.by) hit[k] = R2(D.by[k]);
  const dealt = {}; for (const k in S.dmgBy) dealt[k] = Math.round(S.dmgBy[k]);
  return { done: true, row: { how, dead: how === 'dead', t: R2(S.t - CF.t0), bossHpf: R2(Math.max(0, boss.hp) / boss.mhp), taken: R2(D.taken), hits: D.hits, hp_end: R2(Math.max(0, p.hp) / p.mhp), mhp: Math.round(p.mhp), hit_src: hit, dealt, w: X.CH.w } };
}
window.__bd = { init, run };
})();
