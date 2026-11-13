/* brjhunt_sd.js — 브장신 키우기 동료 SD(2등신) 캐릭터 그림 표.
 *
 * 전역 BrjSD = { FAMS, svg(fam, gr, px), img(fam, gr), famOf(key) }
 *   - 동료 카드 · 파티 칸 · 필드(캔버스)가 모두 이 한 곳의 그림을 쓴다.
 *   - 그림은 코드로 그린 SVG(계열별 몸통·소품·표정 + 등급 색 테두리). 나중에 진짜 그림 파일로 바꾸려면
 *     아래 FILES 표에 계열 → 파일 경로를 적기만 하면 된다(웹/필드 모두 그 파일을 대신 쓴다). 비어 있으면 코드 그림.
 *   - 계열 키는 서버(bot.py BRS_FAMS)와 같다: blade bow mage tank heal lucky.
 */
(function (root) {
  'use strict';
  const FILES = {};   // 예: { blade: 'img/brjhunt/crew/blade.webp' } — 비워 두면 아래 코드 그림을 쓴다
  const GR = { normal: '#98a2b8', rare: '#4aa3ff', epic: '#b678ff', unique: '#ffa23a', legend: '#ff5c7a' };
  // 계열: 이모지 · 이름 · 몸 색 · 소품(손에 든 것) 그리는 조각
  const FAMS = {
    blade: { em: '🗡', ko: '검객',   body: '#e8d27a', prop: '<path d="M43 28 L51 12 L54 15 L46 31 Z" fill="#dfe8f5" stroke="#31405c" stroke-width="1.5"/><rect x="41" y="29" width="8" height="3" rx="1" fill="#8a5a2b" stroke="#31405c" stroke-width="1"/>', hat: '<path d="M16 22 Q32 6 48 22 L44 24 Q32 14 20 24 Z" fill="#c0392b" stroke="#31405c" stroke-width="1.5"/>' },
    bow:   { em: '🏹', ko: '궁수',   body: '#8ed08b', prop: '<path d="M46 14 Q58 32 46 50" fill="none" stroke="#8a5a2b" stroke-width="3" stroke-linecap="round"/><path d="M46 14 L46 50" stroke="#e8e8e8" stroke-width="1"/>', hat: '<path d="M18 22 Q32 4 46 22 Z" fill="#2f8f4e" stroke="#31405c" stroke-width="1.5"/><path d="M44 18 L54 10" stroke="#e8c37a" stroke-width="2.5" stroke-linecap="round"/>' },
    mage:  { em: '🔮', ko: '마법사', body: '#b79cf0', prop: '<path d="M44 52 L48 20" stroke="#8a5a2b" stroke-width="3" stroke-linecap="round"/><circle cx="48" cy="17" r="6" fill="#7fe3ff" stroke="#31405c" stroke-width="1.5"/><circle cx="46" cy="15" r="1.8" fill="#fff"/>', hat: '<path d="M14 24 L34 0 L50 24 Z" fill="#6a4bc2" stroke="#31405c" stroke-width="1.5"/><circle cx="34" cy="8" r="2" fill="#ffe27a"/>' },
    tank:  { em: '🛡', ko: '방패병', body: '#9db4d8', prop: '<path d="M40 24 L56 24 L56 38 Q56 48 48 52 Q40 48 40 38 Z" fill="#6f87b3" stroke="#31405c" stroke-width="1.8"/><path d="M48 28 L48 46 M43 36 L53 36" stroke="#dfe8f5" stroke-width="2"/>', hat: '<path d="M16 24 Q32 6 48 24 L48 28 L16 28 Z" fill="#8795ad" stroke="#31405c" stroke-width="1.5"/><rect x="30" y="10" width="4" height="9" rx="1" fill="#c0392b"/>' },
    heal:  { em: '💚', ko: '치유사', body: '#ffd0e0', prop: '<path d="M46 34 h12 M52 28 v12" stroke="#2fbf71" stroke-width="5" stroke-linecap="round"/><circle cx="52" cy="34" r="9" fill="none" stroke="#fff" stroke-width="1.2" opacity=".7"/>', hat: '<path d="M18 22 Q32 8 46 22 Z" fill="#fff" stroke="#31405c" stroke-width="1.5"/><path d="M29 12 h6 M32 9 v6" stroke="#e74c6a" stroke-width="2.6" stroke-linecap="round"/>' },
    lucky: { em: '🍀', ko: '행운아', body: '#ffe27a', prop: '<circle cx="50" cy="34" r="8" fill="#ffd23c" stroke="#8a5a00" stroke-width="1.8"/><text x="50" y="38.5" font-size="11" font-weight="bold" text-anchor="middle" fill="#8a5a00">$</text>', hat: '<path d="M16 24 Q32 8 48 24 Z" fill="#3fbf6a" stroke="#31405c" stroke-width="1.5"/><circle cx="32" cy="14" r="3" fill="#fff"/>' }
  };
  const KEYS = Object.keys(FAMS);
  function famOf(k) { return FAMS[k] ? k : 'blade'; }
  function esc(s) { return String(s).replace(/[&<>"']/g, c => '&#' + c.charCodeAt(0) + ';'); }
  function grCol(gr) { return GR[gr] || GR.normal; }
  // 64×64 SVG 한 장: 큰 머리 + 작은 몸(2등신), 등급 색 바닥 테두리
  function svg(fam, gr, px) {
    fam = famOf(fam); const f = FAMS[fam], col = grCol(gr), sz = Math.max(16, Math.min(256, px | 0 || 48));
    if (FILES[fam]) return '<img class="sd" src="' + esc(FILES[fam]) + '" width="' + sz + '" height="' + sz + '" alt="" style="border-radius:50%;border:2px solid ' + col + '">';
    return '<svg class="sd" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="' + sz + '" height="' + sz + '" aria-hidden="true">' +
      '<ellipse cx="32" cy="60" rx="17" ry="3.2" fill="rgba(0,0,0,.28)"/>' +
      '<ellipse cx="32" cy="58" rx="19" ry="4" fill="none" stroke="' + col + '" stroke-width="3"/>' +
      '<rect x="22" y="40" width="20" height="16" rx="7" fill="' + f.body + '" stroke="#31405c" stroke-width="1.8"/>' +
      '<rect x="24" y="53" width="6" height="5" rx="2" fill="#31405c"/><rect x="34" y="53" width="6" height="5" rx="2" fill="#31405c"/>' +
      '<circle cx="32" cy="27" r="16" fill="#fff6c7" stroke="#31405c" stroke-width="2"/>' + f.hat +
      '<circle cx="26" cy="29" r="2.6" fill="#31405c"/><circle cx="38" cy="29" r="2.6" fill="#31405c"/><circle cx="25.2" cy="28" r=".9" fill="#fff"/><circle cx="37.2" cy="28" r=".9" fill="#fff"/>' +
      '<ellipse cx="21.5" cy="34" rx="3" ry="2" fill="#ff9aa8" opacity=".75"/><ellipse cx="42.5" cy="34" rx="3" ry="2" fill="#ff9aa8" opacity=".75"/>' +
      '<path d="M29 35 Q32 38 35 35" fill="none" stroke="#31405c" stroke-width="1.6" stroke-linecap="round"/>' +
      f.prop + '</svg>';
  }
  // 필드(캔버스)용: SVG → Image 한 번만 만들어 둔다. 아직 안 불러졌으면 null(그리는 쪽이 대체 도형을 쓴다)
  const cache = {};
  function img(fam, gr) {
    fam = famOf(fam); const key = fam + '|' + (GR[gr] ? gr : 'normal');
    let c = cache[key];
    if (!c) {
      if (typeof Image === 'undefined') return null;
      c = cache[key] = { im: new Image(), ok: false };
      c.im.onload = function () { c.ok = true; }; c.im.onerror = function () { c.ok = false; };
      c.im.src = FILES[fam] ? FILES[fam] : 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg(fam, gr, 64).replace('class="sd" ', ''));
    }
    return c.ok ? c.im : null;
  }
  root.BrjSD = { FAMS: FAMS, KEYS: KEYS, FILES: FILES, svg: svg, img: img, famOf: famOf, col: grCol };
})(typeof window !== 'undefined' ? window : globalThis);
