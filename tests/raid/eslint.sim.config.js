/* 시뮬 본체(sim.js / sim_mp.js)용 ESLint 설정 — no-undef 만 본다(설계서 §4.0 게이트).
   전역 eslint(flat config)로 `eslint -c tests/raid/eslint.sim.config.js tests/raid/.build/sim.js` 처럼 부른다.
   브라우저 전역은 시뮬 코드가 실제로 쓰는 것만 적는다(범위를 넓게 열어 두면 진짜 미정의 이름이 가려진다). */
'use strict';
const BROWSER = {
  window: 'readonly', document: 'readonly', navigator: 'readonly', localStorage: 'readonly', sessionStorage: 'readonly',
  performance: 'readonly', location: 'readonly', fetch: 'readonly', crypto: 'readonly', console: 'readonly',
  requestAnimationFrame: 'readonly', cancelAnimationFrame: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
  setInterval: 'readonly', clearInterval: 'readonly', addEventListener: 'readonly', removeEventListener: 'readonly',
  matchMedia: 'readonly', getComputedStyle: 'readonly', innerWidth: 'readonly', innerHeight: 'readonly',
  Image: 'readonly', Audio: 'readonly', AudioContext: 'readonly', webkitAudioContext: 'readonly',
  URL: 'readonly', URLSearchParams: 'readonly', TextEncoder: 'readonly', TextDecoder: 'readonly', Blob: 'readonly',
  CanvasGradient: 'readonly', CanvasPattern: 'readonly', CanvasRenderingContext2D: 'readonly', Node: 'readonly', Window: 'readonly',
  screen: 'readonly', self: 'readonly', Event: 'readonly', KeyboardEvent: 'readonly', Path2D: 'readonly', OffscreenCanvas: 'readonly',
  atob: 'readonly', btoa: 'readonly', alert: 'readonly', open: 'readonly',
};
module.exports = [{
  files: ['**/*.js'],
  languageOptions: { ecmaVersion: 'latest', sourceType: 'script', globals: BROWSER },
  linterOptions: { reportUnusedDisableDirectives: false },
  rules: { 'no-undef': 'error' },
}];
