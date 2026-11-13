/* brjhunt_sd.js — 브장신 키우기 동료 SD(2등신) 캐릭터 그림 표.
 *
 * 전역 BrjSD = { FAMS, svg(fam, gr, px), img(fam, gr), famOf(key) }
 *   - 동료 카드 · 파티 칸 · 필드(캔버스)가 모두 이 한 곳의 그림을 쓴다.
 *   - 그림은 코드로 그린 SVG(계열별 몸통·소품·표정 + 등급 색 테두리). 나중에 진짜 그림 파일로 바꾸려면
 *     아래 FILES 표에 계열 → 파일 경로를 적기만 하면 된다(웹/필드 모두 그 파일을 대신 쓴다). 비어 있으면 코드 그림.
 *   - 계열 키는 서버(bot.py BRS_FAMS)와 같다: tank(탑) blade(정글) mage(미드) bow(원딜) heal(서폿).
 *   - 등급 팔레트(GRP): 등급마다 몸 색조·테두리·오라·반짝이가 확 다르다 — 한눈에 등급이 보이게. 이 표 한 곳에서만 고친다.
 */
(function (root) {
  'use strict';
  const FILES = {};   // 예: { blade: 'img/brjhunt/crew/blade.webp' } — 비워 두면 아래 코드 그림을 쓴다
  // 등급 팔레트: ring 테두리색 · tint 몸 색조(섞는 비율 mix) · glow 오라 · spark 반짝이 수 · extra 장식(star 가슴 별 / crown 왕관+날개)
  const GRP = {
    normal: { ring: '#98a2b8', ringW: 3,   tint: '#9aa3b5', mix: 0.28, glow: 0,    spark: 0, extra: '' },
    rare:   { ring: '#4aa3ff', ringW: 3.4, tint: '#4aa3ff', mix: 0.22, glow: 0.35, spark: 0, extra: '' },
    epic:   { ring: '#b678ff', ringW: 3.8, tint: '#b678ff', mix: 0.28, glow: 0.55, spark: 3, extra: '' },
    unique: { ring: '#ffa23a', ringW: 4.2, tint: '#ffb347', mix: 0.30, glow: 0.75, spark: 5, extra: 'star' },
    legend: { ring: '#ff5c7a', ringW: 4.6, tint: '#ff8aa0', mix: 0.30, glow: 1.0,  spark: 8, extra: 'crown' }
  };
  const GR = {}; for (const k in GRP) GR[k] = GRP[k].ring;
  // 계열: 이모지 · 이름 · 몸 색 · 소품(손에 든 것) 그리는 조각
  const FAMS = {
    blade: { em: '🗡', ko: '암살자', pos: '정글',   body: '#e8d27a', prop: '<path d="M43 28 L51 12 L54 15 L46 31 Z" fill="#dfe8f5" stroke="#31405c" stroke-width="1.5"/><rect x="41" y="29" width="8" height="3" rx="1" fill="#8a5a2b" stroke="#31405c" stroke-width="1"/>', hat: '<path d="M16 22 Q32 6 48 22 L44 24 Q32 14 20 24 Z" fill="#c0392b" stroke="#31405c" stroke-width="1.5"/>' },
    bow:   { em: '🏹', ko: '사수', pos: '원딜',   body: '#8ed08b', prop: '<path d="M46 14 Q58 32 46 50" fill="none" stroke="#8a5a2b" stroke-width="3" stroke-linecap="round"/><path d="M46 14 L46 50" stroke="#e8e8e8" stroke-width="1"/>', hat: '<path d="M18 22 Q32 4 46 22 Z" fill="#2f8f4e" stroke="#31405c" stroke-width="1.5"/><path d="M44 18 L54 10" stroke="#e8c37a" stroke-width="2.5" stroke-linecap="round"/>' },
    mage:  { em: '🔮', ko: '마법사', pos: '미드', body: '#b79cf0', prop: '<path d="M44 52 L48 20" stroke="#8a5a2b" stroke-width="3" stroke-linecap="round"/><circle cx="48" cy="17" r="6" fill="#7fe3ff" stroke="#31405c" stroke-width="1.5"/><circle cx="46" cy="15" r="1.8" fill="#fff"/>', hat: '<path d="M14 24 L34 0 L50 24 Z" fill="#6a4bc2" stroke="#31405c" stroke-width="1.5"/><circle cx="34" cy="8" r="2" fill="#ffe27a"/>' },
    tank:  { em: '🛡', ko: '탱커', pos: '탑', body: '#9db4d8', prop: '<path d="M40 24 L56 24 L56 38 Q56 48 48 52 Q40 48 40 38 Z" fill="#6f87b3" stroke="#31405c" stroke-width="1.8"/><path d="M48 28 L48 46 M43 36 L53 36" stroke="#dfe8f5" stroke-width="2"/>', hat: '<path d="M16 24 Q32 6 48 24 L48 28 L16 28 Z" fill="#8795ad" stroke="#31405c" stroke-width="1.5"/><rect x="30" y="10" width="4" height="9" rx="1" fill="#c0392b"/>' },
    heal:  { em: '💚', ko: '치유사', pos: '서폿', body: '#ffd0e0', prop: '<path d="M46 34 h12 M52 28 v12" stroke="#2fbf71" stroke-width="5" stroke-linecap="round"/><circle cx="52" cy="34" r="9" fill="none" stroke="#fff" stroke-width="1.2" opacity=".7"/>', hat: '<path d="M18 22 Q32 8 46 22 Z" fill="#fff" stroke="#31405c" stroke-width="1.5"/><path d="M29 12 h6 M32 9 v6" stroke="#e74c6a" stroke-width="2.6" stroke-linecap="round"/>' },
  };
  const KEYS = Object.keys(FAMS);
  function famOf(k) { return FAMS[k] ? k : 'blade'; }
  function esc(s) { return String(s).replace(/[&<>"']/g, c => '&#' + c.charCodeAt(0) + ';'); }
  function grCol(gr) { return GR[gr] || GR.normal; }
  function hex2rgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function mixHex(a, b, t) { const x = hex2rgb(a), y = hex2rgb(b); return '#' + [0, 1, 2].map(i => Math.round(x[i] + (y[i] - x[i]) * t).toString(16).padStart(2, '0')).join(''); }
  const SPK = [[10, 14], [54, 12], [8, 40], [57, 38], [32, 3], [16, 52], [50, 52], [4, 26]];
  function grOf(g) { return GRP[g] ? g : 'normal'; }
  // 64×64 SVG 한 장: 큰 머리 + 작은 몸(2등신), 등급마다 몸 색조·테두리·오라·반짝이·장식이 다르다
  function svg(fam, gr, px) {
    fam = famOf(fam); gr = grOf(gr); const f = FAMS[fam], P = GRP[gr], col = P.ring, sz = Math.max(16, Math.min(256, px | 0 || 48));
    if (FILES[fam]) return '<img class="sd" src="' + esc(FILES[fam]) + '" width="' + sz + '" height="' + sz + '" alt="" style="border-radius:50%;border:2px solid ' + col + '">';
    const body = mixHex(f.body, P.tint, P.mix), gid = 'sdg-' + gr;
    let o = '<svg class="sd" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="' + sz + '" height="' + sz + '" aria-hidden="true">';
    if (P.glow) o += '<defs><radialGradient id="' + gid + '"><stop offset="55%" stop-color="' + col + '" stop-opacity="' + (0.55 * P.glow).toFixed(2) + '"/><stop offset="100%" stop-color="' + col + '" stop-opacity="0"/></radialGradient></defs><circle cx="32" cy="34" r="31" fill="url(#' + gid + ')"/>';
    if (P.extra === 'crown') o += '<path d="M6 30 Q14 22 20 34 L20 46 Q10 44 6 30 Z M58 30 Q50 22 44 34 L44 46 Q54 44 58 30 Z" fill="#fff3c4" stroke="' + col + '" stroke-width="1.5" opacity=".95"/>';   // 날개
    o += '<ellipse cx="32" cy="60" rx="17" ry="3.2" fill="rgba(0,0,0,.28)"/>' +
      '<ellipse cx="32" cy="58" rx="19" ry="4" fill="none" stroke="' + col + '" stroke-width="' + P.ringW + '"/>' +
      (gr === 'legend' ? '<ellipse cx="32" cy="58" rx="22" ry="5" fill="none" stroke="#ffd23c" stroke-width="1.4" stroke-dasharray="3 2"/>' : '') +
      '<rect x="22" y="40" width="20" height="16" rx="7" fill="' + body + '" stroke="#31405c" stroke-width="1.8"/>' +
      '<rect x="24" y="53" width="6" height="5" rx="2" fill="#31405c"/><rect x="34" y="53" width="6" height="5" rx="2" fill="#31405c"/>' +
      (P.extra === 'star' || P.extra === 'crown' ? '<path d="M32 43 l1.9 3.9 4.2.6 -3 3 .7 4.2 -3.8-2 -3.8 2 .7-4.2 -3-3 4.2-.6z" fill="#ffd23c" stroke="#8a5a00" stroke-width=".8"/>' : '') +
      '<circle cx="32" cy="27" r="16" fill="#fff6c7" stroke="#31405c" stroke-width="2"/>' + f.hat +
      '<circle cx="26" cy="29" r="2.6" fill="#31405c"/><circle cx="38" cy="29" r="2.6" fill="#31405c"/><circle cx="25.2" cy="28" r=".9" fill="#fff"/><circle cx="37.2" cy="28" r=".9" fill="#fff"/>' +
      '<ellipse cx="21.5" cy="34" rx="3" ry="2" fill="#ff9aa8" opacity=".75"/><ellipse cx="42.5" cy="34" rx="3" ry="2" fill="#ff9aa8" opacity=".75"/>' +
      '<path d="M29 35 Q32 38 35 35" fill="none" stroke="#31405c" stroke-width="1.6" stroke-linecap="round"/>' +
      f.prop;
    if (P.extra === 'crown') o += '<path d="M20 12 L24 4 L28 10 L32 2 L36 10 L40 4 L44 12 Z" fill="#ffd23c" stroke="#8a5a00" stroke-width="1.3"/><circle cx="32" cy="6" r="1.4" fill="#ff5c7a"/>';
    for (let i = 0; i < P.spark; i++) { const q = SPK[i % SPK.length], r = i % 2 ? 2.2 : 3.2; o += '<path d="M' + q[0] + ' ' + (q[1] - r) + ' L' + (q[0] + r * .35) + ' ' + (q[1] - r * .35) + ' L' + (q[0] + r) + ' ' + q[1] + ' L' + (q[0] + r * .35) + ' ' + (q[1] + r * .35) + ' L' + q[0] + ' ' + (q[1] + r) + ' L' + (q[0] - r * .35) + ' ' + (q[1] + r * .35) + ' L' + (q[0] - r) + ' ' + q[1] + ' L' + (q[0] - r * .35) + ' ' + (q[1] - r * .35) + ' Z" fill="' + (gr === 'legend' ? '#fff3c4' : '#fff') + '" opacity=".92"/>'; }
    return o + '</svg>';
  }
  // 필드(캔버스)용: SVG → Image 한 번만 만들어 둔다. 아직 안 불러졌으면 null(그리는 쪽이 대체 도형을 쓴다)
  const cache = {};
  function img(fam, gr) {
    fam = famOf(fam); gr = grOf(gr); const key = fam + '|' + gr;
    let c = cache[key];
    if (!c) {
      if (typeof Image === 'undefined') return null;
      c = cache[key] = { im: new Image(), ok: false };
      c.im.onload = function () { c.ok = true; }; c.im.onerror = function () { c.ok = false; };
      c.im.src = FILES[fam] ? FILES[fam] : 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg(fam, gr, 64).replace('class="sd" ', ''));
    }
    return c.ok ? c.im : null;
  }
  root.BrjSD = { FAMS: FAMS, KEYS: KEYS, FILES: FILES, GRP: GRP, svg: svg, img: img, famOf: famOf, col: grCol };
})(typeof window !== 'undefined' ? window : globalThis);
