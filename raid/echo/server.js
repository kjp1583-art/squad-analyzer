'use strict';
// 레이드 0단계 — 임시 에코/생존 시험 서버 (2026-10-08)
// 제품이 아니라 측정 도구다. 폰(안드로이드 디스코드 내부창)이 WebSocket 을 얼마나 오래·어떻게
// 붙잡고 있는지, 끊겼다 다시 붙을 때 서버가 옛 소켓을 어떻게 보는지를 "서버 쪽 기록"으로 남긴다.
// 통신 규약은 README.md 「규약」 참고. 의존성은 ws 하나.

const http = require('node:http');
const net = require('node:net');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { WebSocketServer } = require('ws');

// ───────────── 설정 (환경변수) ─────────────
function envNum(name, def, min, max) {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return def;
  const v = Number(raw);
  if (!Number.isFinite(v) || v < min || v > max) {
    console.error(`[설정] ${name}=${JSON.stringify(raw)} 는 범위(${min}~${max}) 밖이라 기본값 ${def} 을 씁니다`);
    return def;
  }
  return v;
}
const CFG = {
  PORT: envNum('PORT', 8080, 0, 65535),
  HOST: process.env.HOST || '127.0.0.1',
  ALLOW_ORIGINS: (process.env.ALLOW_ORIGINS !== undefined && process.env.ALLOW_ORIGINS !== ''
    ? process.env.ALLOW_ORIGINS
    : 'https://kjp1583-art.github.io,http://localhost,http://127.0.0.1')
    .split(',').map((s) => s.trim().toLowerCase()).filter(Boolean),
  TRUST_PROXY: process.env.TRUST_PROXY === '1',
  MAX_CONN: envNum('MAX_CONN', 200, 1, 100000),
  PER_IP: envNum('PER_IP', 30, 1, 100000),
  MAX_MSG_BYTES: envNum('MAX_MSG_BYTES', 4096, 16, 1 << 20),
  MAX_MSG_PER_S: envNum('MAX_MSG_PER_S', 30, 1, 10000),
  MAX_LIFE_S: envNum('MAX_LIFE_S', 3600, 0.1, 86400),
  APP_IDLE_S: envNum('APP_IDLE_S', 900, 0.1, 86400),
  PING_S: envNum('PING_S', 5, 0.05, 600),
  PONG_TO_S: envNum('PONG_TO_S', 10, 0.1, 600),
  DATA_DIR: process.env.DATA_DIR || '/var/lib/raid-echo',
  // 아래는 시험·튜닝용 (README 표의 "그 밖")
  TICK_MS: envNum('TICK_MS', 1000, 10, 60000),
  GAP_EVENT_MS: envNum('GAP_EVENT_MS', 2500, 10, 600000),
  HEADERS_TIMEOUT_MS: envNum('HEADERS_TIMEOUT_MS', 10000, 100, 120000),
  SESSION_MAX: envNum('SESSION_MAX', 300, 1, 100000),
  EVENT_MAX: envNum('EVENT_MAX', 300, 1, 10000),
  SESSION_TTL_S: envNum('SESSION_TTL_S', 6 * 3600, 1, 7 * 86400),
  SWEEP_S: envNum('SWEEP_S', 60, 0.1, 3600),
};
const V = 1;
const SID_RE = /^[A-Za-z0-9_-]{6,40}$/;
const BENCH_RE = /^bench_[A-Za-z0-9_-]{1,40}\.json$/;
const BENCH_MAX_BYTES = 1024 * 1024;
const LOG_MAX_BYTES = 64 * 1024;
const LIST_CAP = 50; // closes / replaced / bg_hints 길이 상한
const SLOW_WARN_BYTES = 64 * 1024;
const SLOW_KILL_BYTES = 256 * 1024;
const startedAt = Date.now();

// ───────────── 작은 도구 ─────────────
// 클라가 보낸 값은 길이를 자르고 제어문자를 지운다(로그·콘솔 오염 방지).
function clean(v, max) {
  if (v === undefined || v === null) return '';
  return String(v).replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, '').slice(0, max);
}
function num(v) { return typeof v === 'number' && Number.isFinite(v) ? v : null; }

function normIp(ip) {
  if (!ip) return '';
  ip = String(ip);
  if (ip.startsWith('::ffff:') && net.isIPv4(ip.slice(7))) return ip.slice(7);
  return ip;
}
// IPv6 는 한 가정·한 기기가 /64 를 통째로 받으므로 앞 4덩이로 묶어서 센다.
function ipKey(ip) {
  if (!ip.includes(':')) return ip;
  let head = ip.split('%')[0];
  let groups;
  if (head.includes('::')) {
    const [a, b] = head.split('::');
    const left = a ? a.split(':') : [];
    const right = b ? b.split(':') : [];
    groups = left.concat(Array(Math.max(0, 8 - left.length - right.length)).fill('0'), right);
  } else {
    groups = head.split(':');
  }
  return groups.slice(0, 4).map((g) => (parseInt(g || '0', 16) || 0).toString(16)).join(':') + '::/64';
}
function clientIp(req) {
  const sock = normIp(req.socket && req.socket.remoteAddress);
  if (!CFG.TRUST_PROXY) return sock;
  const xff = req.headers['x-forwarded-for'];
  if (!xff) return sock;
  // 프록시(Caddy)가 덧붙이는 값은 맨 오른쪽이다. 왼쪽은 클라가 위조할 수 있다.
  const last = normIp(String(xff).split(',').pop().trim());
  return net.isIP(last) ? last : sock;
}
function originAllowed(origin) {
  if (origin === undefined) return true; // 비브라우저 도구는 Origin 이 없다
  const o = String(origin).trim().toLowerCase();
  if (!o || o === 'null') return false;
  let u;
  try { u = new URL(o); } catch { return false; }
  for (const entry of CFG.ALLOW_ORIGINS) {
    if (entry === o) return true;
    let e;
    try { e = new URL(entry); } catch { continue; }
    // 포트 없이 적은 localhost 항목은 어떤 포트든 허용(로컬 개발용)
    if (!e.port && (e.hostname === 'localhost' || e.hostname === '127.0.0.1') &&
        e.protocol === u.protocol && e.hostname === u.hostname) return true;
  }
  return false;
}
function pfx(s) { return clean(s, 4); }

// ───────────── 세션 기록 (메모리) ─────────────
class Ring {
  constructor(cap) { this.cap = cap; this.a = []; this.h = 0; }
  push(x) {
    if (this.a.length < this.cap) this.a.push(x);
    else { this.a[this.h] = x; this.h = (this.h + 1) % this.cap; }
  }
  list() { return this.a.length < this.cap ? this.a.slice() : this.a.slice(this.h).concat(this.a.slice(0, this.h)); }
  get length() { return this.a.length; }
}
function pushCap(arr, x) { arr.push(x); if (arr.length > LIST_CAP) arr.shift(); }

const sessions = new Map(); // sid -> session (Map 순서 = 오래 안 쓴 순)
function newSession(sid) {
  return {
    sid, created: Date.now(), last_used: Date.now(), cur: null, lastClose: null, lastIp: null,
    nconn: 0, open: 0, closed: 0,
    events: new Ring(CFG.EVENT_MAX),
    sum: { last_msg_ms: null, last_pong_ms: null, max_msg_gap_ms: 0, max_pong_gap_ms: 0, bg_hints: [], closes: [], replaced: [] },
  };
}
function getSession(sid) {
  let s = sessions.get(sid);
  if (s) { sessions.delete(sid); sessions.set(sid, s); s.last_used = Date.now(); return s; }
  s = newSession(sid);
  sessions.set(sid, s);
  // 상한을 넘으면 가장 오래 안 쓴 것부터 버린다(접속 중인 세션은 건너뜀)
  if (sessions.size > CFG.SESSION_MAX) {
    for (const [k, v] of sessions) {
      if (sessions.size <= CFG.SESSION_MAX) break;
      if (v.cur || k === sid) continue;
      sessions.delete(k);
    }
  }
  return s;
}
function ev(s, name, extra) {
  s.events.push(Object.assign({ ts: Date.now(), ev: name }, extra));
}
function summaryOf(s) {
  const m = s.sum;
  return {
    conns: s.open, opened: s.nconn, closed: s.closed,
    last_msg_ms: m.last_msg_ms, last_pong_ms: m.last_pong_ms,
    max_msg_gap_ms: m.max_msg_gap_ms, max_pong_gap_ms: m.max_pong_gap_ms,
    bg_hints: m.bg_hints.slice(), closes: m.closes.slice(), replaced: m.replaced.slice(),
  };
}
function emptySummary() {
  return { conns: 0, opened: 0, closed: 0, last_msg_ms: null, last_pong_ms: null, max_msg_gap_ms: 0, max_pong_gap_ms: 0, bg_hints: [], closes: [], replaced: [] };
}
function sweepSessions() {
  const cut = Date.now() - CFG.SESSION_TTL_S * 1000;
  for (const [k, v] of sessions) if (!v.cur && v.last_used < cut) sessions.delete(k);
}

// ───────────── 통계·상태 ─────────────
const stats = { errors: 0, last_error: '', rej: { origin: 0, sid: 0, limit: 0 }, peak: 0 };
const live = new Set(); // 열려 있는(닫는 중 아닌) 연결
let slotsUsed = 0;      // MAX_CONN 계산용(닫는 중인 것은 즉시 반납)
const perIp = new Map();
let shuttingDown = false;
let errWindow = [];

function noteError(kind, e) {
  stats.errors++;
  stats.last_error = clean(`${kind}: ${e && e.message ? e.message : e}`, 200);
  const n = stats.errors;
  if (n <= 20 || n % 100 === 0) console.error(`[오류 #${n}] ${stats.last_error}`);
  // 짧은 시간에 오류가 폭주하면 계속 삼키지 않고 죽어서 systemd 가 다시 띄우게 한다.
  const now = Date.now();
  errWindow.push(now);
  errWindow = errWindow.filter((t) => now - t < 60000);
  if (errWindow.length > 200) { console.error('[치명] 1분에 오류 200건 초과 — 종료합니다'); process.exit(1); }
}
process.on('uncaughtException', (e) => noteError('uncaughtException', e));
process.on('unhandledRejection', (e) => noteError('unhandledRejection', e));

function release(c) {
  if (c.released) return;
  c.released = true;
  slotsUsed--;
  const k = c.ipKey;
  const n = (perIp.get(k) || 1) - 1;
  if (n <= 0) perIp.delete(k); else perIp.set(k, n);
  live.delete(c);
}

// ───────────── 연결 ─────────────
function send(c, obj) {
  const ws = c.ws;
  if (ws.readyState !== 1) return;
  if (ws.bufferedAmount > SLOW_KILL_BYTES) { closeConn(c, 4005, 'slow-reader'); return; }
  if (ws.bufferedAmount > SLOW_WARN_BYTES) return; // 느린 수신자에게는 건너뜀
  ws.send(JSON.stringify(obj), (err) => { if (err) c.sendErr = true; });
}

function recordClose(c, code, why, by) {
  if (c.recorded) return;
  c.recorded = true;
  const s = c.s;
  const now = Date.now();
  s.open = Math.max(0, s.open - 1);
  s.closed++;
  pushCap(s.sum.closes, { ms: now, code, why, by, conn: c.idx });
  ev(s, 'close', { conn: c.idx, code, why, by, life_ms: now - c.openedAt });
  if (s.cur === c) {
    s.lastClose = { close_ms: now, code, why, by, last_heard: Math.max(c.lastApp, c.lastPong) };
    s.cur = null;
  }
  release(c);
  console.log(`[닫힘] sid=${pfx(s.sid)} conn=${c.idx} code=${code} by=${by} why=${why} life=${((now - c.openedAt) / 1000).toFixed(1)}s`);
}

function closeConn(c, code, why, by = 'server') {
  if (c.closing) return;
  c.closing = true;
  why = clean(why, 60);
  recordClose(c, code, why, by);
  try { c.ws.close(code, why); } catch { try { c.ws.terminate(); } catch { /* 이미 끊김 */ } }
  c.termTimer = setTimeout(() => { try { c.ws.terminate(); } catch { /* 이미 끊김 */ } }, 2000);
  c.termTimer.unref();
}

function onAppMessage(c, data) {
  const s = c.s;
  const now = Date.now();
  // 속도 한도(초당)
  if (now - c.winStart >= 1000) { c.winStart = now; c.winCount = 0; }
  if (++c.winCount > CFG.MAX_MSG_PER_S) { closeConn(c, 1008, 'rate-limit'); return; }

  const gap = now - c.lastApp;
  if (c.nApp > 0 && gap > s.sum.max_msg_gap_ms) s.sum.max_msg_gap_ms = gap;
  if (c.nApp > 0 && gap >= CFG.GAP_EVENT_MS) ev(s, 'msg_gap', { conn: c.idx, gap_ms: gap });
  c.lastApp = now;
  c.nApp++;
  s.sum.last_msg_ms = now;

  let msg = null;
  const text = data.toString('utf8');
  try { const j = JSON.parse(text); if (j && typeof j === 'object' && !Array.isArray(j)) msg = j; } catch { /* 잘못된 JSON 은 echo 로 */ }
  const t = msg && typeof msg.t === 'string' ? msg.t : '';
  const n = msg ? num(msg.n) : null;
  const cc = msg ? num(msg.c) : null;
  if (t === 'hb' || t === 'bg') {
    if (t === 'bg') {
      pushCap(s.sum.bg_hints, now);
      ev(s, 'bg', { conn: c.idx, n, c: cc, skew_ms: cc === null ? null : now - cc });
    } else if (c.nHb === 0) {
      ev(s, 'first_hb', { conn: c.idx, n, skew_ms: cc === null ? null : now - cc });
    }
    if (t === 'hb') c.nHb++;
    send(c, { t: 'ack', k: t, n, c: cc, srv_ms: now });
    return;
  }
  // 그 밖의 것은 모두 echo
  if (!msg) ev(s, 'echo', { conn: c.idx, len: text.length, json: false });
  else ev(s, 'echo', { conn: c.idx, len: text.length, json: true, tt: clean(t, 20) });
  send(c, { t: 'ack', k: 'echo', n, c: cc, srv_ms: now, len: text.length, e: clean(text, 200) });
}

function onPong(c) {
  const s = c.s;
  const now = Date.now();
  const gap = now - c.lastPong;
  if (c.nPong > 0 && gap > s.sum.max_pong_gap_ms) s.sum.max_pong_gap_ms = gap;
  if (c.nPong > 0 && gap > CFG.PING_S * 2000 + 500) ev(s, 'pong_gap', { conn: c.idx, gap_ms: gap });
  c.lastPong = now;
  c.nPong++;
  s.sum.last_pong_ms = now;
}

function attach(ws, req, sid, ip) {
  const s = getSession(sid);
  const now = Date.now();
  const c = {
    ws, s, ip, ipKey: ipKey(ip), idx: ++s.nconn, openedAt: now,
    lastApp: now, lastPong: now, lastPing: now, nApp: 0, nHb: 0, nPong: 0, tickN: 0,
    winStart: now, winCount: 0, closing: false, recorded: false, released: false, closeBy: null,
  };
  // 같은 sid 의 옛 연결은 4001 로 닫는다 — 이때 옛 연결을 서버가 얼마나 "살아 있다"고 믿었는지를 남긴다.
  const old = s.cur;
  if (old && !old.closing) {
    const oa = now - old.lastApp;
    const op = now - old.lastPong;
    pushCap(s.sum.replaced, { ms: now, old_msg_age_ms: oa, old_pong_age_ms: op });
    ev(s, 'replaced', { conn: old.idx, new_conn: c.idx, old_msg_age_ms: oa, old_pong_age_ms: op });
    closeConn(old, 4001, 'replaced');
  }
  s.cur = c;
  s.open++;
  live.add(c);
  stats.peak = Math.max(stats.peak, live.size);
  const ipChanged = s.lastIp !== null && s.lastIp !== ip;
  s.lastIp = ip;
  ev(s, 'open', {
    conn: c.idx, ua: clean(req.headers['user-agent'], 120), origin: clean(req.headers.origin, 80), ip_changed: ipChanged,
  });
  const lc = s.lastClose;
  const prev = lc ? {
    close_ms: lc.close_ms, code: lc.code, why: lc.why, gap_ms: now - lc.close_ms,
    quiet_ms: now - lc.last_heard, by: lc.by,
  } : null;
  console.log(`[열림] ip=${pfx(ip)} sid=${pfx(sid)} conn=${c.idx} live=${live.size}`);

  ws.on('message', (data, isBinary) => {
    try {
      if (c.closing) return;
      if (isBinary) { closeConn(c, 1003, 'binary-not-supported'); return; }
      if (data.length > CFG.MAX_MSG_BYTES) { closeConn(c, 1009, 'too-big'); return; }
      onAppMessage(c, data);
    } catch (e) { noteError('message', e); }
  });
  ws.on('pong', () => { try { if (!c.closing) onPong(c); } catch (e) { noteError('pong', e); } });
  ws.on('ping', () => { // 클라가 먼저 ping 을 보내도 속도 한도에 센다(ws 가 pong 은 알아서 보냄)
    const t = Date.now();
    if (t - c.winStart >= 1000) { c.winStart = t; c.winCount = 0; }
    if (++c.winCount > CFG.MAX_MSG_PER_S) closeConn(c, 1008, 'rate-limit');
  });
  ws.on('error', (err) => {
    try {
      ev(s, 'error', { conn: c.idx, msg: clean(err && err.message, 80), code: clean(err && err.code, 40) });
      if (err && err.code === 'WS_ERR_UNSUPPORTED_MESSAGE_LENGTH') c.closeBy = 'server';
    } catch (e) { noteError('ws-error', e); }
  });
  ws.on('close', (code, reason) => {
    try {
      if (c.termTimer) clearTimeout(c.termTimer);
      let by = c.closeBy;
      if (!by) by = (code === 1002 || code === 1007 || code === 1009) ? 'server' : 'peer';
      recordClose(c, code, clean(reason && reason.toString(), 60), by);
      release(c);
    } catch (e) { noteError('ws-close', e); }
  });

  send(c, {
    t: 'hello', v: V, sid, srv_ms: now, conn: c.idx, prev,
    tick_ms: CFG.TICK_MS, ping_s: CFG.PING_S, pong_to_s: CFG.PONG_TO_S,
    idle_s: CFG.APP_IDLE_S, life_s: CFG.MAX_LIFE_S,
  });
}

// ───────────── 타이머 하나로 전부 (드리프트 보정) ─────────────
let loopTimer = null;
function startLoop() {
  const t0 = Date.now();
  let i = 0;
  const step = () => {
    if (shuttingDown) return;
    try { runTick(); } catch (e) { noteError('tick', e); }
    i++;
    let next = t0 + (i + 1) * CFG.TICK_MS;
    const now = Date.now();
    while (next <= now) { i++; next = t0 + (i + 1) * CFG.TICK_MS; } // 한참 밀렸으면 몰아서 보내지 않고 건너뜀
    loopTimer = setTimeout(step, next - now);
  };
  loopTimer = setTimeout(step, CFG.TICK_MS);
}
function runTick() {
  const now = Date.now();
  for (const c of live) {
    try {
      if (c.closing) continue;
      if (now - c.openedAt > CFG.MAX_LIFE_S * 1000) { closeConn(c, 1001, 'max-life'); continue; }
      if (now - c.lastApp > CFG.APP_IDLE_S * 1000) { closeConn(c, 1001, 'app-idle'); continue; }
      if (now - Math.max(c.lastApp, c.lastPong) > CFG.PONG_TO_S * 1000) { closeConn(c, 1001, 'no-response'); continue; }
      if (now - c.lastPing >= CFG.PING_S * 1000 - CFG.TICK_MS / 2) {
        c.lastPing = now;
        c.ws.ping();
      }
      c.tickN++;
      send(c, { t: 'tick', n: c.tickN, srv_ms: now });
    } catch (e) { noteError('tick-conn', e); }
  }
}

// ───────────── HTTP ─────────────
const BASE_HEADERS = {
  'Cache-Control': 'no-store',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '600',
  'Timing-Allow-Origin': '*',
  'X-Content-Type-Options': 'nosniff',
};
function reply(req, res, status, body, type) {
  const buf = Buffer.from(body, 'utf8');
  res.writeHead(status, Object.assign({ 'Content-Type': type, 'Content-Length': buf.length }, BASE_HEADERS));
  res.end(req.method === 'HEAD' ? undefined : buf);
}
function json(req, res, status, obj) { reply(req, res, status, JSON.stringify(obj), 'application/json; charset=utf-8'); }

let setupCache = { at: 0, v: null };
function readSmallJson(name) {
  try {
    const p = path.join(CFG.DATA_DIR, name);
    const st = fs.statSync(p);
    if (st.isFile() && st.size <= 4096) return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch { /* 없거나 깨졌으면 없는 것으로 */ }
  return null;
}
// 설치 스크립트가 남기는 상태(setup.json)와 부하 시험 진행(bench_state.json)을 /health 에 보여 준다.
function readSetup() {
  const now = Date.now();
  if (now - setupCache.at < 5000) return setupCache.v;
  setupCache.at = now;
  const su = readSmallJson('setup.json');
  const bs = readSmallJson('bench_state.json');
  if (su && typeof su === 'object' && !Array.isArray(su)) setupCache.v = bs ? Object.assign({}, su, { bench: bs }) : su;
  else setupCache.v = bs ? { bench: bs } : null;
  return setupCache.v;
}
async function listBench() {
  let names;
  try { names = await fs.promises.readdir(CFG.DATA_DIR); } catch { return []; }
  const out = [];
  for (const nm of names) {
    if (!BENCH_RE.test(nm)) continue; // 고정 패턴만
    try {
      const st = await fs.promises.lstat(path.join(CFG.DATA_DIR, nm)); // 심볼릭 링크는 건너뜀(isFile 이 거짓)
      if (st.isFile()) out.push({ name: nm, mtime_ms: Math.floor(st.mtimeMs), size: st.size });
    } catch { /* 사라짐 */ }
  }
  out.sort((a, b) => b.mtime_ms - a.mtime_ms || (a.name < b.name ? 1 : -1));
  return out;
}
let benchPresent = false;
async function refreshBenchFlag() { try { benchPresent = (await listBench()).length > 0; } catch { /* 무시 */ } }

async function benchHandler(req, res, url) {
  const list = await listBench();
  if (url.searchParams.get('list') === '1') {
    return json(req, res, 200, { found: list.length > 0, files: list });
  }
  const want = url.searchParams.get('name'); // 파일 이름 그대로가 아니라 목록과 대조만 한다
  let cands = list;
  if (want !== null) {
    const w = clean(want, 60).replace(/^bench_/, '').replace(/\.json$/, '');
    cands = list.filter((f) => f.name === `bench_${w}.json`);
  }
  for (const f of cands) {
    if (f.size > BENCH_MAX_BYTES) { return json(req, res, 200, { found: false, error: 'too_large', file: f.name }); }
    try {
      const txt = await fs.promises.readFile(path.join(CFG.DATA_DIR, f.name), 'utf8');
      JSON.parse(txt); // 깨진 파일(쓰는 중)은 건너뛴다
      return reply(req, res, 200, txt, 'application/json; charset=utf-8');
    } catch { /* 다음 후보 */ }
  }
  return json(req, res, 200, { found: false });
}

const HOME_TEXT = [
  '레이드 0단계 임시 시험 서버입니다. (제품 아님 — 시험이 끝나면 서버째 삭제됩니다)',
  '',
  '  /health   서버 상태 (JSON)',
  '  /ping     핑 시험용 (아주 작은 JSON)',
  '  /log?sid= 그 접속 번호(sid)에 대해 서버가 본 기록',
  '  /bench    마지막 부하 시험 결과',
  '  /ws?sid=  WebSocket (wss)',
  '',
].join('\n');

function handleHttp(req, res) {
  let url;
  try { url = new URL(req.url, 'http://x'); } catch { return json(req, res, 400, { error: 'bad_url' }); }
  const m = req.method;
  if (m === 'OPTIONS') { res.writeHead(204, BASE_HEADERS); return res.end(); }
  if (m !== 'GET' && m !== 'HEAD') { res.setHeader('Allow', 'GET, HEAD, OPTIONS'); return json(req, res, 405, { error: 'method' }); }
  const p = url.pathname;
  if (p === '/health') {
    return json(req, res, 200, {
      ok: true, v: V, now: Date.now(), up_s: Math.floor((Date.now() - startedAt) / 1000),
      conns: live.size, peak: stats.peak, errors: stats.errors, rej: stats.rej, bench: benchPresent,
      setup: readSetup(),
    });
  }
  if (p === '/ping') return json(req, res, 200, { t: Date.now() });
  if (p === '/log') {
    const sid = url.searchParams.get('sid') || '';
    if (!SID_RE.test(sid)) return json(req, res, 400, { error: 'bad_sid' });
    const s = sessions.get(sid); // 읽기만 — 세션을 만들거나 "최근 사용"으로 올리지 않는다
    if (!s) return json(req, res, 200, { sid, found: false, now: Date.now(), summary: emptySummary(), events: [] });
    const body = { sid, found: true, now: Date.now(), summary: summaryOf(s), events: s.events.list() };
    let txt = JSON.stringify(body);
    while (txt.length > LOG_MAX_BYTES && body.events.length > 0) {
      body.events = body.events.slice(Math.min(20, body.events.length));
      body.truncated = true;
      txt = JSON.stringify(body);
    }
    return reply(req, res, 200, txt, 'application/json; charset=utf-8');
  }
  if (p === '/bench') {
    benchHandler(req, res, url).catch((e) => { noteError('bench', e); if (!res.headersSent) json(req, res, 500, { error: 'internal' }); });
    return undefined;
  }
  if (p === '/') return reply(req, res, 200, HOME_TEXT, 'text/plain; charset=utf-8');
  return json(req, res, 404, { error: 'not_found' });
}

const server = http.createServer({ maxHeaderSize: 8192 }, (req, res) => {
  try { handleHttp(req, res); } catch (e) {
    noteError('http', e);
    try { if (!res.headersSent) json(req, res, 500, { error: 'internal' }); else res.end(); } catch { /* 무시 */ }
  }
});
// slowloris 대비: 헤더를 천천히 보내거나 아예 안 보내는 연결을 끊는다.
server.headersTimeout = CFG.HEADERS_TIMEOUT_MS;
server.requestTimeout = Math.round(CFG.HEADERS_TIMEOUT_MS * 1.5);
server.keepAliveTimeout = 5000;
server.timeout = Math.round(CFG.HEADERS_TIMEOUT_MS * 1.5); // 아무 바이트도 안 보내는 연결(업그레이드된 소켓은 ws 가 0 으로 풀어 줌)
server.connectionsCheckingInterval = Math.min(2000, CFG.HEADERS_TIMEOUT_MS);
server.maxConnections = CFG.MAX_CONN * 2 + 100;
server.on('clientError', (err, socket) => {
  try {
    const to = err && (err.code === 'ERR_HTTP_REQUEST_TIMEOUT' || err.code === 'ERR_HTTP_HEADERS_TIMEOUT');
    if (socket.writable) socket.end(`HTTP/1.1 ${to ? '408 Request Timeout' : '400 Bad Request'}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
    else socket.destroy();
  } catch { /* 무시 */ }
});

// ───────────── WebSocket 업그레이드 ─────────────
// maxPayload 는 메모리 방어선(넉넉하게). 정확한 한도(MAX_MSG_BYTES)는 메시지 핸들러에서 1009 로 깔끔히 닫는다 —
// ws 가 한도 초과를 중간에 발견하면 읽지 않은 데이터 때문에 TCP 리셋이 나서 상대가 1009 대신 1006 을 볼 수 있다.
const HARD_MAX_PAYLOAD = Math.max(CFG.MAX_MSG_BYTES * 4, 65536);
const wss = new WebSocketServer({ noServer: true, maxPayload: HARD_MAX_PAYLOAD, perMessageDeflate: false, clientTracking: false });
function rejectUpgrade(socket, status, text, extra) {
  try {
    socket.end(`HTTP/1.1 ${status} ${text}\r\nConnection: close\r\nContent-Length: 0\r\n${extra || ''}\r\n`);
  } catch { socket.destroy(); }
}
server.on('upgrade', (req, socket, head) => {
  socket.on('error', () => { /* 연결 중 끊김은 정상 */ });
  try {
    if (shuttingDown) return rejectUpgrade(socket, 503, 'Service Unavailable', 'Retry-After: 5\r\n');
    let url;
    try { url = new URL(req.url, 'http://x'); } catch { return rejectUpgrade(socket, 400, 'Bad Request'); }
    if (url.pathname !== '/ws' && url.pathname !== '/wstest') return rejectUpgrade(socket, 404, 'Not Found');
    if (req.method !== 'GET') return rejectUpgrade(socket, 405, 'Method Not Allowed');
    if (!originAllowed(req.headers.origin)) { stats.rej.origin++; return rejectUpgrade(socket, 403, 'Forbidden'); }
    let sid = url.searchParams.get('sid');
    if (sid === null || sid === '') sid = crypto.randomBytes(12).toString('base64url');
    else if (!SID_RE.test(sid)) { stats.rej.sid++; return rejectUpgrade(socket, 400, 'Bad Request'); }
    const ip = clientIp(req);
    const key = ipKey(ip);
    // 같은 sid 의 옛 연결은 곧 4001 로 교체되므로 한도 계산에서 뺀다.
    const prev = sessions.get(sid);
    const replacing = prev && prev.cur && !prev.cur.closing ? prev.cur : null;
    const totalNow = slotsUsed - (replacing ? 1 : 0);
    const ipNow = (perIp.get(key) || 0) - (replacing && replacing.ipKey === key ? 1 : 0);
    if (totalNow >= CFG.MAX_CONN || ipNow >= CFG.PER_IP) {
      stats.rej.limit++;
      return rejectUpgrade(socket, 503, 'Service Unavailable', 'Retry-After: 5\r\n');
    }
    wss.handleUpgrade(req, socket, head, (ws) => {
      slotsUsed++;
      perIp.set(key, (perIp.get(key) || 0) + 1);
      try { attach(ws, req, sid, ip); } catch (e) {
        noteError('attach', e);
        try { ws.terminate(); } catch { /* 무시 */ }
      }
    });
  } catch (e) {
    noteError('upgrade', e);
    try { socket.destroy(); } catch { /* 무시 */ }
  }
});

// ───────────── 시작·종료 ─────────────
function shutdown(sig) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`[종료] ${sig} — 소켓 ${live.size}개에 1001 을 보내고 닫습니다`);
  if (loopTimer) clearTimeout(loopTimer);
  clearInterval(benchTimer);
  clearInterval(sweepTimer);
  server.close();
  server.closeIdleConnections();
  for (const c of Array.from(live)) {
    try { c.closing = true; c.closeBy = 'server'; c.ws.close(1001, 'server-shutdown'); } catch { /* 무시 */ }
  }
  const t = setTimeout(() => { console.log('[종료] 2초 대기 끝 — 강제 종료'); process.exit(0); }, 2000);
  const poll = setInterval(() => {
    if (live.size === 0 || Array.from(live).every((c) => c.ws.readyState === 3)) { clearInterval(poll); clearTimeout(t); setTimeout(() => process.exit(0), 50); }
  }, 20);
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

const benchTimer = setInterval(refreshBenchFlag, 5000);
benchTimer.unref();
const sweepTimer = setInterval(sweepSessions, CFG.SWEEP_S * 1000);
sweepTimer.unref();

server.listen(CFG.PORT, CFG.HOST, () => {
  const a = server.address();
  refreshBenchFlag();
  startLoop();
  console.log(JSON.stringify({ listening: a.port, host: a.address, trust_proxy: CFG.TRUST_PROXY, origins: CFG.ALLOW_ORIGINS, v: V }));
});
server.on('error', (e) => { console.error(`[치명] 서버를 열지 못했습니다: ${e.message}`); process.exit(1); });
