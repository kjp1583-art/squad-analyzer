// 🦐 최종 보스 1:1 — 회피 휴리스틱 봇(페이지 안에서 돈다). 정책 봇(survivors_charbal_bot.js)은 회피를 못 해서 1:1 난이도를 잴 수 없다 — 이 봇은 「예고를 읽고 피하는 사람」을 흉내 낸다.
// 사람처럼: ① 예고가 뜬 지 0.3초 뒤부터 반응한다(반응 시간) ② 0.1초마다만 방향을 고른다 ③ 속도는 내 이동속도(p.sp)를 넘지 않는다 ④ 보스 쪽(공격 사거리)에 머무르려 한다.
// 한계: 한 걸음 앞만 보는 탐욕 방식이라 사람보다 못 피하는 상황(좁은 틈 두 번 연속 등)도, 사람이 못 하는 정밀한 회피도 있다 — 난이도는 「대략」 보는 용도.
(function () {
  const X = window.__p6x, FD = window.__fd;
  const CFG = { react: 0.3, every: 3, horizon: [0.15, 0.3, 0.45, 0.6, 0.8, 1.0, 1.3], want: 240, sloppy: 0 };   // sloppy: 0~1 — 클수록 헛발질(방향을 가끔 틀림)
  let frame = 0, prev = -1;
  const DIRS = [[0, 0]];
  for (let i = 0; i < 16; i++) { const a = i * Math.PI / 8; DIRS.push([Math.cos(a), Math.sin(a)]); }
  const KEYSET = (ux, uy) => { const k = {}; if (ux > 0.38) k.KeyD = true; if (ux < -0.38) k.KeyA = true; if (uy > 0.38) k.KeyS = true; if (uy < -0.38) k.KeyW = true; return k; };
  function inBand(z, x, y, pr) {
    const dx = x - z.x, dy = y - z.y, al = dx * z.ax + dy * z.ay, pe = Math.abs(-dx * z.ay + dy * z.ax);
    return al > -z.w * 0.5 && al < z.L + 10 && pe < z.w / 2 + pr + 8;
  }
  function depth(z, x, y) {   // 이 구역 안쪽으로 얼마나 들어갔나(0 이하면 밖) — 모양마다 가장자리까지 거리
    if (z.k === 'c') { const dx = x - z.x, dy = y - z.y, d = Math.hypot(dx, dy); let da = Math.atan2(dy, dx) - z.a; da = Math.atan2(Math.sin(da), Math.cos(da)); return Math.min(z.R - d, (z.w - Math.abs(da)) * d); }
    if (z.k === 'd') return z.R - Math.hypot(x - z.x, y - z.y);
    if (z.k === 'o') return Math.hypot(x - z.x, y - z.y) - z.R;
    return -1;
  }
  function decide() {
    const S = X.S, p = S.p, D = FD.D, du = D && D.du;
    if (!du) return null;
    const sp = p.sp * 0.98;
    let best = 0, bs = 1e18;
    const bul = []; for (const b of X.eshots.a) if (b.on) bul.push(b);
    const zs = du.z.filter(z => z.fl <= 0 && (z.T - z.t >= CFG.react || z.k === 'b' && z.t <= 0));
    const safeO = zs.find(z => z.k === 'o');
    for (let i = 0; i < DIRS.length; i++) {
      const u = DIRS[i]; let cost = 0;
      for (const tau of CFG.horizon) {
        const q = { x: p.x + u[0] * sp * tau, y: p.y + u[1] * sp * tau };
        for (const b of bul) { const bx = b.x + b.vx * tau, by = b.y + b.vy * tau, d = Math.hypot(bx - q.x, by - q.y); if (d < p.r + 6 + 14) cost += 9 * (1.4 - tau); else if (d < p.r + 6 + 34) cost += 1.5; }
        const dd = Math.hypot(D.x - q.x, D.y - q.y); if (dd < D.r + p.r + 34) cost += 4;
      }
      for (const z of zs) {
        const tf = Math.max(0, z.t), te = Math.min(tf, 1.7), q = { x: p.x + u[0] * sp * te, y: p.y + u[1] * sp * te };
        if (z.k === 'b') { if (inBand(z, q.x, q.y, p.r)) cost += 8; continue; }
        if (z.k === 's') continue;
        const dp = depth(z, q.x, q.y);
        const w = tf <= 1.7 ? 1 : 0.25;
        if (dp > -10) cost += w * (6 + Math.max(0, dp) / 40);
      }
      const q1 = { x: p.x + u[0] * sp * 0.6, y: p.y + u[1] * sp * 0.6 }, c = Math.hypot(q1.x - du.cx, q1.y - du.cy);
      if (c > du.R - p.r - 40) cost += 2.5 + (c - (du.R - p.r - 40)) / 30;
      const dB = Math.hypot(D.x - q1.x, D.y - q1.y); cost += 0.004 * Math.abs(dB - CFG.want);   // 사거리 유지
      if (safeO) cost += 0.02 * Math.max(0, Math.hypot(q1.x - safeO.x, q1.y - safeO.y) - safeO.R * 0.5);   // 안전지대가 있으면 그 안쪽으로
      if (i === prev) cost -= 0.3;
      cost += (i === 0 ? 0.05 : 0);
      if (cost < bs) { bs = cost; best = i; }
    }
    if (CFG.sloppy && Math.random() < CFG.sloppy * 0.15) best = (Math.random() * DIRS.length) | 0;
    return best;
  }
  function step() {   // 한 프레임 이동 키 정하기(0.1초마다)
    if (frame++ % CFG.every === 0) {
      const d = decide();
      if (d === null) { X.keys = {}; prev = -1; return; }
      prev = d; X.keys = KEYSET(DIRS[d][0], DIRS[d][1]);
    }
  }
  window.__fbot = { CFG, step, decide, reset() { frame = 0; prev = -1; } };
})();
