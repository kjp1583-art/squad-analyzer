/* 레이드 0단계 — 헤드리스 로더(DOM 스텁) (2026-10-08)

   build_sim.js 가 만든 sim.js / sim_mp.js 를 Node 의 vm 컨텍스트에서 "브라우저 없이" 올린다.
   스텁은 화면 그리기·소리·네트워크를 전부 삼키되, 시뮬이 실제로 쓰는 것(저장소·시계·난수)은 진짜처럼 동작시킨다.

   이 스텁이 지키는 것(첫 스파이크의 단순 스텁이 놓치던 부분)
   - localStorage 를 진짜 저장소처럼(length·key·clear 포함) 만든다. 예전 스텁은 length/key 가 없어
     이어하기(RES) 모듈의 저장본 훑기가 조용히 아무것도 안 했다.
   - document.hidden·visibilityState·addEventListener 를 기록한다 → 시험이 visibilitychange/pagehide 를 직접 쏴 볼 수 있다.
   - fetch 는 항상 거절(네트워크로 나가지 않는다 — 결과 전송 postRun 등이 실수로 밖에 닿지 않게). 호출 수를 센다.
   - 타이머(setTimeout/Interval)는 실행하지 않고 개수만 센다(UI 용 지연 문구뿐이고, 프로세스가 안 끝나는 일을 막는다).
   - 컨텍스트 자체의 내장 객체(Object·Array·Math …)를 쓴다(예전엔 바깥 세계 것을 건네서 instanceof 가 어긋날 수 있었다).
   - seed 옵션: 컨텍스트 안의 Math.random 을 시드 난수로 바꾼다(같은 시드 → 같은 판).
   - trace 옵션: 스텁이 받은 속성 접근 이름을 모아 「시뮬이 건드린 브라우저 API」 보고서를 만든다. */
'use strict';
const vm = require('vm'), fs = require('fs'), crypto = require('crypto');

function mulberry32(a) {
  return function () { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function makeStore() {
  const m = new Map();
  const st = {
    getItem: k => (m.has(String(k)) ? m.get(String(k)) : null),
    setItem: (k, v) => { m.set(String(k), String(v)); },
    removeItem: k => { m.delete(String(k)); },
    clear: () => { m.clear(); },
    key: i => { const a = [...m.keys()]; return i >= 0 && i < a.length ? a[i] : null; },
  };
  Object.defineProperty(st, 'length', { get: () => m.size });
  return st;
}

function makeWindow(opts = {}) {
  const stub = { props: new Map(), timers: 0, fetches: 0, consoleWarn: 0, consoleErr: 0, listeners: [] };
  const trace = !!opts.trace;
  const note = k => { if (typeof k === 'string') stub.props.set(k, (stub.props.get(k) || 0) + 1); };
  const mk = () => {
    const f = function () {};
    return new Proxy(f, {
      get(t, k) {
        if (trace) note(k);
        if (k === Symbol.toPrimitive) return () => 0;
        if (k === 'length') return 0;
        if (k === 'width' || k === 'height') return 800;
        if (k === 'measureText') return () => ({ width: 10 });
        if (k === 'getContext') return () => mk();
        if (k === 'children') return [];
        if (k === 'firstElementChild') return mk();
        if (k === 'checked') return false;
        if (k === 'value') return '';
        if (k === 'getBoundingClientRect') return () => ({ left: 0, top: 0, width: 800, height: 600 });
        return mk();
      },
      set() { return true; },
      apply() { return mk(); },
      construct() { return mk(); },
    });
  };
  const store = makeStore(), sess = makeStore();
  const listen = (who) => (type, fn) => { stub.listeners.push({ who, type, fn }); };
  const doc = {
    getElementById: () => mk(), createElement: () => mk(), querySelector: () => mk(), querySelectorAll: () => [],
    addEventListener: listen('document'), removeEventListener() {},
    body: mk(), documentElement: mk(), hidden: false, visibilityState: 'visible', fonts: { load() {} },
  };
  const cons = {
    log: opts.verbose ? console.log.bind(console) : () => {}, info: opts.verbose ? console.info.bind(console) : () => {},
    debug: () => {}, warn: (...a) => { stub.consoleWarn++; if (opts.verbose) console.warn(...a); },
    error: (...a) => { stub.consoleErr++; (opts.onConsoleError || (() => {}))(a); if (opts.verbose) console.error(...a); },
  };
  const nav = { hardwareConcurrency: 8, userAgent: 'node-headless', standalone: false, clipboard: { writeText: () => Promise.resolve() } };
  const win = {
    innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1, screen: { width: 1280, height: 800 },
    addEventListener: listen('window'), removeEventListener() {},
    localStorage: store, sessionStorage: sess,
    location: { href: 'http://localhost/survivors.html', search: '', hash: '', origin: 'http://localhost', pathname: '/survivors.html', replace() {}, assign() {} },
    fetch: () => { stub.fetches++; return Promise.reject(new Error('no net')); },
    requestAnimationFrame() { return 0; }, cancelAnimationFrame() {},
    setTimeout: () => { stub.timers++; return stub.timers; }, clearTimeout() {},
    setInterval: () => { stub.timers++; return stub.timers; }, clearInterval() {},
    performance, console: cons, URL, crypto: crypto.webcrypto, navigator: nav,
    matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
    document: doc, Image: function () { return mk(); }, Audio: function () { return mk(); },
    AudioContext: undefined, webkitAudioContext: undefined,
    getComputedStyle: () => mk(),
  };
  win.window = win; win.self = win; win.globalThis = win; win.top = win; win.parent = win;
  return { win, stub };
}

/* 코드 문자열을 새 컨텍스트에 올린다. 돌려주는 win 에는 __p6x(훅)와 __stub(스텁 기록)이 있다. */
function loadSimCode(code, opts = {}) {
  const { win, stub } = makeWindow(opts);
  const ctx = vm.createContext(win, { name: 'sim' });
  if (opts.seed != null) {   // 컨텍스트 안의 Math.random 을 시드 난수(mulberry32)로 바꾼다
    vm.runInContext(`(function(){var a=${opts.seed | 0};Math.random=function(){a=(a+0x6D2B79F5)|0;var t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};})();`, ctx, { filename: 'seed' });
  }
  try { vm.runInContext(code, ctx, { filename: opts.filename || 'sim.js' }); }
  catch (e) { const err = new Error('시뮬 로드 실패: ' + (e && e.message)); err.stack = 'LOAD ERR ' + (e && e.stack || e); err.cause = e; throw err; }
  win.__stub = stub;
  return win;
}

function loadSimFile(file, opts) { return loadSimCode(fs.readFileSync(file, 'utf8'), Object.assign({ filename: file }, opts)); }

/* 스텁 보고서: 시뮬이 건드린 API 이름·타이머·fetch 수 */
function stubReport(win) {
  const s = win.__stub;
  return { props: [...s.props.entries()].sort((a, b) => b[1] - a[1]).map(([k, n]) => k + ':' + n), timers: s.timers, fetches: s.fetches,
    console_warn: s.consoleWarn, console_error: s.consoleErr, listeners: s.listeners.map(l => l.who + ':' + l.type) };
}

module.exports = { loadSimCode, loadSimFile, makeWindow, stubReport, mulberry32 };
