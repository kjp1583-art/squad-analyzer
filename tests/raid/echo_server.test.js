'use strict';
// 레이드 0단계 에코 서버 시험 (2026-10-08)
// 실행: cd raid/echo && npm ci --omit=dev && cd ../.. && node --test tests/raid/echo_server.test.js
// 서버는 별도 프로세스로 띄우고(포트 0 = 임의), 시간 관련 값은 환경변수로 줄여서 빠르게 돈다.
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const net = require('node:net');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ECHO_DIR = path.join(__dirname, '..', '..', 'raid', 'echo');
let WebSocket;
try { WebSocket = require(path.join(ECHO_DIR, 'node_modules', 'ws')); } catch (e) {
  console.error('ws 가 없습니다. 먼저: cd raid/echo && npm ci --omit=dev');
  throw e;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const LOAD = os.loadavg()[0];
// 시스템이 바쁘면 시간 허용 폭을 넓힌다(측정이 아니라 동작 확인이므로)
const SLACK = LOAD > 6 ? 3 : 1;

async function retry(fn, times = 2) {
  let last;
  for (let i = 0; i < times; i++) {
    try { return await fn(); } catch (e) { last = e; await sleep(200); }
  }
  throw last;
}

const FAST = { PING_S: '0.2', TICK_MS: '100', PONG_TO_S: '1', APP_IDLE_S: '30', GAP_EVENT_MS: '300' };
const procs = new Set();

async function startServer(env = {}) {
  const dataDir = env.DATA_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'raid-echo-data-'));
  const proc = spawn(process.execPath, [path.join(ECHO_DIR, 'server.js')], {
    env: Object.assign({}, process.env, { PORT: '0', HOST: '127.0.0.1', DATA_DIR: dataDir }, FAST, env),
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  procs.add(proc);
  let out = '';
  let err = '';
  proc.stderr.on('data', (d) => { err += d; });
  const port = await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('서버가 안 뜸: ' + out + err)), 8000);
    proc.stdout.on('data', (d) => {
      out += d;
      const m = out.match(/\{"listening":(\d+)/);
      if (m) { clearTimeout(t); resolve(Number(m[1])); }
    });
    proc.on('exit', (c) => reject(new Error('서버가 바로 종료 code=' + c + ' ' + out + err)));
  });
  const srv = {
    port, proc, dataDir, get out() { return out; }, get err() { return err; },
    url: `ws://127.0.0.1:${port}/ws`,
    http: `http://127.0.0.1:${port}`,
    async stop() {
      if (proc.exitCode !== null) return proc.exitCode;
      proc.kill('SIGTERM');
      return await new Promise((r) => { proc.on('exit', (c) => r(c)); setTimeout(() => proc.kill('SIGKILL'), 4000); });
    },
    async get(p, headers) {
      const r = await fetch(srv.http + p, { headers });
      const txt = await r.text();
      let j = null;
      try { j = JSON.parse(txt); } catch { /* 본문이 JSON 이 아닐 수 있음 */ }
      return { status: r.status, headers: r.headers, text: txt, json: j };
    },
  };
  return srv;
}
test.after(() => { for (const p of procs) { try { p.kill('SIGKILL'); } catch { /* 이미 종료 */ } } });

// 접속하고 받은 메시지를 모아 두는 클라
function client(srv, sid, opts = {}) {
  const q = sid === null ? '' : `?sid=${sid}`;
  const ws = new WebSocket(`${srv.url}${q}`, Object.assign({}, opts.ws));
  const c = { ws, msgs: [], closed: null, errors: [], waiters: [] };
  ws.on('message', (d, bin) => {
    if (bin) { c.msgs.push({ bin: true }); return; }
    let j; try { j = JSON.parse(d.toString()); } catch { j = { raw: d.toString() }; }
    c.msgs.push(j);
    c.waiters = c.waiters.filter((w) => !w(j));
  });
  ws.on('close', (code, reason) => { c.closed = { code, reason: reason.toString(), at: Date.now() }; c.waiters.forEach((w) => w(null)); });
  ws.on('error', (e) => c.errors.push(e));
  c.open = new Promise((res, rej) => { ws.once('open', res); ws.once('error', rej); ws.once('unexpected-response', (rq, rs) => rej(Object.assign(new Error('HTTP ' + rs.statusCode), { status: rs.statusCode, headers: rs.headers }))); });
  c.next = (pred, ms = 3000) => new Promise((res, rej) => {
    const hit = c.msgs.find(pred);
    if (hit) return res(hit);
    const t = setTimeout(() => rej(new Error('메시지 대기 시간 초과')), ms);
    c.waiters.push((m) => { if (m && pred(m)) { clearTimeout(t); res(m); return true; } return false; });
    return undefined;
  });
  c.hello = () => c.next((m) => m.t === 'hello');
  c.waitClose = (ms = 3000) => new Promise((res, rej) => {
    if (c.closed) return res(c.closed);
    const t = setTimeout(() => rej(new Error('close 대기 시간 초과')), ms);
    ws.once('close', () => { clearTimeout(t); res(c.closed); });
    return undefined;
  });
  c.send = (x) => ws.send(typeof x === 'string' || Buffer.isBuffer(x) ? x : JSON.stringify(x));
  return c;
}
async function connect(srv, sid, opts) {
  const c = client(srv, sid, opts);
  await c.open;
  c.helloMsg = await c.hello();
  return c;
}
// 업그레이드 시도 결과만 본다: {status} 거절 / {c} 성공
async function tryConnect(srv, sid, opts = {}) {
  const c = client(srv, sid, opts);
  try { await c.open; await c.hello(); return { c, status: 101 }; } catch (e) { return { status: e.status || 0, headers: e.headers, err: e }; }
}
const sidN = (() => { let i = 0; return (p = 's') => `${p}${Date.now().toString(36)}${(i++).toString(36)}_test`.slice(0, 40); })();

// ───────────── 기본 규약 ─────────────
test('hello 형식 · conn 번호 · prev', async () => {
  const srv = await startServer();
  try {
    const sid = sidN();
    const a = await connect(srv, sid);
    const h = a.helloMsg;
    assert.equal(h.t, 'hello'); assert.equal(h.v, 1); assert.equal(h.sid, sid);
    assert.equal(h.conn, 1); assert.equal(h.prev, null);
    assert.equal(typeof h.srv_ms, 'number'); assert.ok(Math.abs(h.srv_ms - Date.now()) < 2000);
    assert.equal(h.tick_ms, 100); assert.equal(h.ping_s, 0.2); assert.equal(h.pong_to_s, 1);
    a.ws.close(1000, 'bye');
    await a.waitClose();
    await sleep(300);
    const b = await connect(srv, sid);
    assert.equal(b.helloMsg.conn, 2);
    const p = b.helloMsg.prev;
    assert.equal(p.code, 1000); assert.equal(p.why, 'bye'); assert.equal(p.by, 'peer');
    assert.ok(p.gap_ms >= 250 && p.gap_ms < 3000, 'gap_ms=' + p.gap_ms);
    assert.ok(Math.abs(p.close_ms - (b.helloMsg.srv_ms - p.gap_ms)) < 5);
    b.ws.close();
  } finally { await srv.stop(); }
});

test('sid 를 안 주면 서버가 만들어 hello 로 알려 주고, 그 sid 로 /log 가 된다 · /wstest 별칭', async () => {
  const srv = await startServer();
  try {
    const a = await connect(srv, null);
    assert.match(a.helloMsg.sid, /^[A-Za-z0-9_-]{6,40}$/);
    const lg = await srv.get('/log?sid=' + a.helloMsg.sid);
    assert.equal(lg.json.found, true);
    const w = new WebSocket(`ws://127.0.0.1:${srv.port}/wstest?sid=${sidN()}`);
    const got = await new Promise((r, j) => { w.once('message', (d) => r(JSON.parse(d))); w.once('error', j); });
    assert.equal(got.t, 'hello');
    w.close(); a.ws.close();
  } finally { await srv.stop(); }
});

test('tick: 주기·번호·드리프트 보정(서버 시각 기준 누적 오차가 작다)', async () => {
  await retry(async () => {
    const srv = await startServer({ TICK_MS: '100' });
    try {
      const a = await connect(srv, sidN());
      await sleep(2300 * SLACK);
      const ticks = a.msgs.filter((m) => m.t === 'tick');
      assert.ok(ticks.length >= 18, 'tick 수 ' + ticks.length);
      ticks.forEach((t, i) => assert.equal(t.n, i + 1, 'n 이 1부터 연속'));
      const span = ticks[ticks.length - 1].srv_ms - ticks[0].srv_ms;
      const expect = (ticks.length - 1) * 100;
      // 드리프트 보정이라 setInterval 처럼 지연이 쌓이지 않는다
      assert.ok(Math.abs(span - expect) <= 60 * SLACK, `span=${span} expect=${expect}`);
      const gaps = ticks.slice(1).map((t, i) => t.srv_ms - ticks[i].srv_ms);
      assert.ok(Math.max(...gaps) < 100 + 80 * SLACK, 'max gap ' + Math.max(...gaps));
      a.ws.close();
    } finally { await srv.stop(); }
  });
});

test('hb / bg / echo ack · 잘못된 JSON 은 echo · c 와 n 을 그대로 돌려줌', async () => {
  const srv = await startServer();
  try {
    const a = await connect(srv, sidN());
    const c0 = Date.now();
    a.send({ t: 'hb', n: 7, c: c0 });
    const hb = await a.next((m) => m.t === 'ack' && m.k === 'hb');
    assert.equal(hb.n, 7); assert.equal(hb.c, c0); assert.ok(hb.srv_ms >= c0 - 2000);
    a.send({ t: 'bg', n: 8, c: c0 + 1 });
    const bg = await a.next((m) => m.t === 'ack' && m.k === 'bg');
    assert.equal(bg.n, 8); assert.equal(bg.c, c0 + 1);
    a.send({ t: 'whatever', n: 9, c: 5, x: 'y' });
    const e1 = await a.next((m) => m.t === 'ack' && m.k === 'echo' && m.n === 9);
    assert.equal(e1.c, 5);
    a.send('이건 JSON 이 아님 {{{');
    const e2 = await a.next((m) => m.t === 'ack' && m.k === 'echo' && m.n === null && /JSON/.test(m.e));
    assert.equal(e2.c, null);
    a.send('[1,2,3]');
    await a.next((m) => m.t === 'ack' && m.k === 'echo' && m.e === '[1,2,3]');
    a.send({ t: 'hb', n: 'x', c: 'y' }); // 숫자가 아닌 n/c 는 null 로
    const hb2 = await a.next((m) => m.t === 'ack' && m.k === 'hb' && m.n === null);
    assert.equal(hb2.c, null);
    assert.equal(a.closed, null, '잘못된 JSON 으로 연결이 끊기면 안 된다');
    a.ws.close();
  } finally { await srv.stop(); }
});

// ───────────── 하트비트 · 생존 ─────────────
test('프로토콜 ping/pong 추적: pong 을 하는 클라는 /log 에 last_pong_ms, max_pong_gap_ms 가 쌓인다', async () => {
  const srv = await startServer();
  try {
    const sid = sidN();
    const a = await connect(srv, sid);
    a.send({ t: 'hb', n: 1, c: Date.now() });
    await sleep(1200 * SLACK);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.ok(lg.summary.last_pong_ms > Date.now() - 1000);
    assert.ok(lg.summary.max_pong_gap_ms >= 150 && lg.summary.max_pong_gap_ms < 900 * SLACK, 'pong gap ' + lg.summary.max_pong_gap_ms);
    assert.equal(lg.summary.conns, 1);
    a.ws.close();
  } finally { await srv.stop(); }
});

test('pong 도 앱 메시지도 없으면 PONG_TO_S 뒤 1001 no-response (autoPong:false)', async () => {
  const srv = await startServer({ PONG_TO_S: '1' });
  try {
    const sid = sidN();
    const t0 = Date.now();
    const a = await connect(srv, sid, { ws: { autoPong: false } });
    const cl = await a.waitClose(4000 * SLACK);
    const dt = cl.at - t0;
    assert.equal(cl.code, 1001); assert.equal(cl.reason, 'no-response');
    assert.ok(dt >= 900 && dt < 2500 * SLACK, 'dt=' + dt);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    const c = lg.summary.closes[0];
    assert.equal(c.code, 1001); assert.equal(c.by, 'server'); assert.equal(c.why, 'no-response');
    assert.equal(lg.summary.conns, 0);
  } finally { await srv.stop(); }
});

test('앱 메시지가 없어도 pong 이 오는 동안은 PONG_TO 로 안 끊기지만, APP_IDLE_S 가 지나면 1001 app-idle', async () => {
  const srv = await startServer({ APP_IDLE_S: '1.5', PONG_TO_S: '1' });
  try {
    const t0 = Date.now();
    const a = await connect(srv, sidN());
    const cl = await a.waitClose(5000 * SLACK);
    const dt = cl.at - t0;
    assert.equal(cl.code, 1001); assert.equal(cl.reason, 'app-idle');
    assert.ok(dt >= 1400 && dt < 3500 * SLACK, 'dt=' + dt);
    // hb 를 계속 보내면 살아 있다
    const b = await connect(srv, sidN());
    const iv = setInterval(() => { try { b.send({ t: 'hb', n: 1, c: Date.now() }); } catch { /* 닫힘 */ } }, 200);
    await sleep(2500 * SLACK);
    clearInterval(iv);
    assert.equal(b.closed, null);
    b.ws.close();
  } finally { await srv.stop(); }
});

test('연결 총 수명 MAX_LIFE_S 초과 시 1001 max-life', async () => {
  const srv = await startServer({ MAX_LIFE_S: '1' });
  try {
    const a = await connect(srv, sidN());
    const iv = setInterval(() => { try { a.send({ t: 'hb', n: 1, c: 1 }); } catch { /* 닫힘 */ } }, 150);
    const cl = await a.waitClose(4000 * SLACK);
    clearInterval(iv);
    assert.equal(cl.code, 1001); assert.equal(cl.reason, 'max-life');
  } finally { await srv.stop(); }
});

// ───────────── 같은 sid 교체 ─────────────
test('같은 sid 새 연결: 옛 연결 4001 replaced · replaced 기록값이 타당 · prev 가 replaced', async () => {
  const srv = await startServer({ PING_S: '30', PONG_TO_S: '30', TICK_MS: '1000' }); // 서버가 pong 을 기다리지 않게 길게
  try {
    const sid = sidN();
    const a = await connect(srv, sid, { ws: { autoPong: false } });
    a.send({ t: 'hb', n: 1, c: Date.now() });
    await a.next((m) => m.k === 'hb');
    await sleep(600);
    const b = await connect(srv, sid);
    const cl = await a.waitClose(3000);
    assert.equal(cl.code, 4001); assert.equal(cl.reason, 'replaced');
    assert.equal(b.helloMsg.conn, 2);
    assert.equal(b.helloMsg.prev.code, 4001); assert.equal(b.helloMsg.prev.why, 'replaced'); assert.equal(b.helloMsg.prev.by, 'server');
    assert.ok(b.helloMsg.prev.quiet_ms >= 500 && b.helloMsg.prev.quiet_ms < 2500 * SLACK, 'quiet ' + b.helloMsg.prev.quiet_ms);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.equal(lg.summary.replaced.length, 1);
    const r = lg.summary.replaced[0];
    // 옛 연결이 마지막 앱 메시지를 보낸 지 약 600ms (서버는 그동안 살아 있다고 믿음)
    assert.ok(r.old_msg_age_ms >= 550 && r.old_msg_age_ms < 2500 * SLACK, 'old_msg_age_ms=' + r.old_msg_age_ms);
    // autoPong:false 라 pong 은 한 번도 없었다 → 연결 시각 기준 나이(>= 메시지 나이)
    assert.ok(r.old_pong_age_ms >= r.old_msg_age_ms, `pong ${r.old_pong_age_ms} msg ${r.old_msg_age_ms}`);
    assert.equal(lg.summary.opened, 2);
    assert.equal(lg.summary.conns, 1);
    assert.ok(lg.events.some((e) => e.ev === 'replaced' && e.conn === 1 && e.new_conn === 2));
    assert.ok(lg.summary.closes.some((c) => c.code === 4001 && c.by === 'server' && c.conn === 1));
    b.ws.close();
  } finally { await srv.stop(); }
});

test('같은 sid 로 동시에 5개를 열어도 마지막 하나만 남고 나머지는 4001', async () => {
  const srv = await startServer();
  try {
    const sid = sidN();
    const cs = await Promise.all([1, 2, 3, 4, 5].map(() => tryConnect(srv, sid)));
    await sleep(500);
    const open = cs.filter((x) => x.c && x.c.ws.readyState === 1);
    assert.equal(open.length, 1);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.equal(lg.summary.conns, 1);
    assert.equal(lg.summary.replaced.length, 4);
    open[0].c.ws.close();
  } finally { await srv.stop(); }
});

// ───────────── /log ─────────────
test('/log: summary·events 내용 (open·bg·msg_gap·close) · bg_hints · 서버가 닫은 건 by=server', async () => {
  const srv = await startServer({ MAX_MSG_PER_S: '1000' });
  try {
    const sid = sidN();
    const a = await connect(srv, sid, { ws: { headers: { 'User-Agent': 'TestUA/1.0 ' + 'x'.repeat(500) } } });
    a.send({ t: 'hb', n: 1, c: Date.now() });
    await sleep(500);                                  // GAP_EVENT_MS=300 보다 길게 쉬었다가
    a.send({ t: 'bg', n: 2, c: Date.now() - 40 });
    await a.next((m) => m.k === 'bg');
    a.ws.close(1000, 'x');
    await a.waitClose();
    await sleep(100);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.equal(lg.sid, sid); assert.equal(lg.found, true); assert.equal(typeof lg.now, 'number');
    const s = lg.summary;
    assert.equal(s.opened, 1); assert.equal(s.closed, 1); assert.equal(s.conns, 0);
    assert.ok(s.last_msg_ms <= lg.now && s.last_msg_ms > lg.now - 3000);
    assert.equal(s.bg_hints.length, 1);
    assert.ok(s.max_msg_gap_ms >= 450, 'max_msg_gap_ms=' + s.max_msg_gap_ms);
    assert.deepEqual(Object.keys(s).sort(), ['bg_hints', 'closed', 'closes', 'conns', 'last_msg_ms', 'last_pong_ms', 'max_msg_gap_ms', 'max_pong_gap_ms', 'opened', 'replaced'].sort());
    assert.equal(s.closes[0].code, 1000); assert.equal(s.closes[0].by, 'peer'); assert.equal(s.closes[0].conn, 1);
    const names = lg.events.map((e) => e.ev);
    assert.equal(names[0], 'open'); assert.equal(names[names.length - 1], 'close');
    assert.ok(names.includes('bg') && names.includes('msg_gap') && names.includes('first_hb'));
    const open = lg.events[0];
    assert.ok(open.ua.startsWith('TestUA/1.0') && open.ua.length <= 120, 'UA 길이 ' + open.ua.length);
    const bgEv = lg.events.find((e) => e.ev === 'bg');
    assert.ok(bgEv.skew_ms >= 40 && bgEv.skew_ms < 3000);
    assert.ok(lg.events.every((e, i, arr) => i === 0 || e.ts >= arr[i - 1].ts), 'events 는 시간 순');
    // 서버가 닫은 경우
    const sid2 = sidN();
    const b = await connect(srv, sid2);
    b.ws.send(Buffer.from([1, 2, 3]), { binary: true });
    await b.waitClose();
    const lg2 = (await srv.get('/log?sid=' + sid2)).json;
    assert.equal(lg2.summary.closes[0].code, 1003); assert.equal(lg2.summary.closes[0].by, 'server');
  } finally { await srv.stop(); }
});

test('/log: 없는 sid 는 found:false + 빈 summary, 형식이 틀리면 400, sid 를 만들지 않는다', async () => {
  const srv = await startServer();
  try {
    const r = await srv.get('/log?sid=nobody_here');
    assert.equal(r.status, 200); assert.equal(r.json.found, false); assert.equal(r.json.summary.opened, 0); assert.deepEqual(r.json.events, []);
    assert.equal((await srv.get('/log?sid=ab')).status, 400);
    assert.equal((await srv.get('/log')).status, 400);
    assert.equal((await srv.get('/log?sid=' + encodeURIComponent('a/../b$$$$$'))).status, 400);
    assert.equal((await srv.get('/log?sid=nobody_here')).json.found, false, '조회가 세션을 만들면 안 된다');
  } finally { await srv.stop(); }
});

test('클라가 보낸 값은 길이를 자르고 제어문자를 지운다', async () => {
  const srv = await startServer();
  try {
    const sid = sidN();
    const a = await connect(srv, sid);
    const evil = 'A\u0000B\u001b[31mC\u0007' + 'z'.repeat(1000) + '\u2028end';
    a.send({ t: 'custom', n: 1, c: 1, junk: evil });
    const ack = await a.next((m) => m.k === 'echo');
    assert.ok(ack.e.length <= 200);
    assert.doesNotMatch(ack.e, /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/);
    a.ws.close(1000, 'r\u0001e\u001bason');
    await a.waitClose();
    await sleep(100);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.equal(lg.summary.closes[0].why, 'reason');
    assert.doesNotMatch(JSON.stringify(lg), /[\u0000-\u001f]/);
    const out = srv.out + srv.err;
    assert.doesNotMatch(out.replace(/\n/g, ''), /\u001b/);
    assert.ok(out.includes(`sid=${sid.slice(0, 4)} `) && !out.includes(sid), '콘솔에는 sid 앞 4자만');
  } finally { await srv.stop(); }
});

// ───────────── 입구 방어 ─────────────
test('Origin 검사: 허용 / 거부 / 없음(비브라우저) / localhost 아무 포트 / 위장 도메인 / null', async () => {
  const srv = await startServer();
  try {
    const ok = async (origin) => { const r = await tryConnect(srv, sidN(), { ws: origin === undefined ? {} : { origin } }); if (r.c) r.c.ws.close(); return r.status; };
    assert.equal(await ok(undefined), 101);
    assert.equal(await ok('https://kjp1583-art.github.io'), 101);
    assert.equal(await ok('http://localhost'), 101);
    assert.equal(await ok('http://localhost:5173'), 101);
    assert.equal(await ok('http://127.0.0.1:8000'), 101);
    assert.equal(await ok('https://evil.example'), 403);
    assert.equal(await ok('https://kjp1583-art.github.io.evil.example'), 403);
    assert.equal(await ok('http://kjp1583-art.github.io'), 403, '스킴이 다르면 거부');
    assert.equal(await ok('http://localhost.evil.example'), 403);
    assert.equal(await ok('null'), 403);
    const h = (await srv.get('/health')).json;
    assert.ok(h.rej.origin >= 5);
  } finally { await srv.stop(); }
});

test('ALLOW_ORIGINS 환경변수로 바꾼 목록을 따른다', async () => {
  const srv = await startServer({ ALLOW_ORIGINS: 'https://a.example, https://b.example' });
  try {
    const st = async (o) => { const r = await tryConnect(srv, sidN(), { ws: { origin: o } }); if (r.c) r.c.ws.close(); return r.status; };
    assert.equal(await st('https://b.example'), 101);
    assert.equal(await st('https://kjp1583-art.github.io'), 403);
    assert.equal(await st('http://localhost'), 403);
  } finally { await srv.stop(); }
});

test('sid 형식 검사: 짧음·긴·이상한 글자 400', async () => {
  const srv = await startServer();
  try {
    for (const bad of ['abc', 'a'.repeat(41), 'abc def', 'abc$def', '한글한글한글', 'abc.def_', 'a%00bcdef']) {
      const r = await tryConnect(srv, bad);
      assert.equal(r.status, 400, JSON.stringify(bad));
    }
    for (const good of ['abcdef', 'A'.repeat(40), 'a_b-c_d-e']) {
      const r = await tryConnect(srv, good); assert.equal(r.status, 101, good); r.c.ws.close();
    }
    assert.equal((await srv.get('/health')).json.rej.sid, 7);
  } finally { await srv.stop(); }
});

test('잘못된 경로·메서드 업그레이드는 거절', async () => {
  const srv = await startServer();
  try {
    const w = new WebSocket(`ws://127.0.0.1:${srv.port}/nope?sid=${sidN()}`);
    const st = await new Promise((r) => { w.once('unexpected-response', (q, s) => r(s.statusCode)); w.once('error', () => r(0)); });
    assert.equal(st, 404);
    assert.equal((await srv.get('/nope')).status, 404);
    const r = await fetch(srv.http + '/health', { method: 'POST', body: 'x' });
    assert.equal(r.status, 405);
  } finally { await srv.stop(); }
});

test('전체 한도 MAX_CONN 초과는 503 + Retry-After, 자리가 나면 다시 받는다 · /health rej.limit', async () => {
  const srv = await startServer({ MAX_CONN: '3', PER_IP: '100' });
  try {
    const cs = [];
    for (let i = 0; i < 3; i++) cs.push(await connect(srv, sidN()));
    const r = await tryConnect(srv, sidN());
    assert.equal(r.status, 503); assert.ok(r.headers['retry-after']);
    cs[0].ws.close(); await cs[0].waitClose(); await sleep(100);
    const r2 = await tryConnect(srv, sidN());
    assert.equal(r2.status, 101); r2.c.ws.close();
    const h = (await srv.get('/health')).json;
    assert.equal(h.rej.limit, 1); assert.ok(h.peak >= 3);
    cs.forEach((c) => c.ws.close());
  } finally { await srv.stop(); }
});

test('IP당 한도 PER_IP 초과는 503 · 같은 sid 재접속(교체)은 한도를 먹지 않는다', async () => {
  const srv = await startServer({ PER_IP: '2' });
  try {
    const s1 = sidN(); const s2 = sidN();
    const a = await connect(srv, s1);
    const b = await connect(srv, s2);
    assert.equal((await tryConnect(srv, sidN())).status, 503);
    const a2 = await tryConnect(srv, s1);               // 폰이 재접속한 상황: 옛 소켓이 아직 안 닫혀 있어도 된다
    assert.equal(a2.status, 101);
    await a.waitClose();
    assert.equal(a.closed.code, 4001);
    a2.c.ws.close(); b.ws.close();
  } finally { await srv.stop(); }
});

test('TRUST_PROXY 끔: X-Forwarded-For 를 무시하고 소켓 주소로 센다(위조해도 한도 우회 불가)', async () => {
  const srv = await startServer({ PER_IP: '2', TRUST_PROXY: '0' });
  try {
    const mk = (xff) => tryConnect(srv, sidN(), { ws: { headers: { 'X-Forwarded-For': xff } } });
    const a = await mk('1.1.1.1'); const b = await mk('2.2.2.2');
    assert.equal(a.status, 101); assert.equal(b.status, 101);
    assert.equal((await mk('3.3.3.3')).status, 503);
    a.c.ws.close(); b.c.ws.close();
  } finally { await srv.stop(); }
});

test('TRUST_PROXY 켬: X-Forwarded-For 맨 오른쪽 값으로 센다(왼쪽 위조 무시) · 이상한 값은 소켓 주소 · IPv6 는 /64', async () => {
  const srv = await startServer({ PER_IP: '2', TRUST_PROXY: '1' });
  try {
    const mk = (xff) => tryConnect(srv, sidN(), { ws: { headers: xff === undefined ? {} : { 'X-Forwarded-For': xff } } });
    const keep = [];
    const t = async (xff, want) => { const r = await mk(xff); assert.equal(r.status, want, `xff=${xff}`); if (r.c) keep.push(r.c); };
    // 맨 오른쪽 9.9.9.9 두 개 → 왼쪽을 바꿔 위조해도 세 번째는 거절
    await t('1.1.1.1, 9.9.9.9', 101);
    await t('2.2.2.2, 9.9.9.9', 101);
    await t('3.3.3.3, 9.9.9.9', 503);
    // 다른 사용자(오른쪽이 다름)는 영향 없음
    await t('9.9.9.9, 8.8.8.8', 101);
    // 맨 오른쪽이 IP 가 아니면 소켓 주소(127.0.0.1)로 센다
    await t('garbage', 101);
    await t('also, garbage', 101);
    await t(undefined, 503); // 127.0.0.1 이미 2개
    // IPv6 는 같은 /64 를 한 사람으로 센다
    await t('2001:db8:1:2:aaaa::1', 101);
    await t('2001:db8:1:2:bbbb::2', 101);
    await t('2001:db8:1:2:cccc::3', 503);
    await t('2001:db8:1:3::1', 101);
    // IPv4 매핑 표기는 IPv4 와 같은 사람
    await t('::ffff:7.7.7.7', 101);
    await t('7.7.7.7', 101);
    await t('::ffff:7.7.7.7', 503);
    keep.forEach((c) => c.ws.close());
  } finally { await srv.stop(); }
});

test('메시지 크기 한도: 초과 1009 · 한도 이내는 통과', async () => {
  const srv = await startServer({ MAX_MSG_BYTES: '256' });
  try {
    const sid = sidN();
    const a = await connect(srv, sid);
    a.send(JSON.stringify({ t: 'x', pad: 'p'.repeat(150) }));
    await a.next((m) => m.k === 'echo');
    a.send('q'.repeat(300));
    const cl = await a.waitClose();
    assert.equal(cl.code, 1009);
    await sleep(100);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.equal(lg.summary.closes[0].code, 1009); assert.equal(lg.summary.closes[0].by, 'server');
    // 방어선(ws maxPayload)을 넘는 거대 프레임: 1009 또는 연결 리셋(1006)이어도 서버는 산다
    const sid2 = sidN();
    const b = await connect(srv, sid2);
    b.ws.send(Buffer.alloc(2 * 1024 * 1024, 0x61).toString());
    const cl2 = await b.waitClose();
    assert.ok(cl2.code === 1009 || cl2.code === 1006, '거대 프레임 close=' + cl2.code);
    await sleep(100);
    const lg2 = (await srv.get('/log?sid=' + sid2)).json;
    assert.equal(lg2.summary.closes[0].by, 'server', '서버가 닫은 것으로 기록');
    assert.equal((await srv.get('/health')).json.errors, 0);
  } finally { await srv.stop(); }
});

test('초당 메시지 한도 초과 1008 (앱 메시지와 클라 ping 모두)', async () => {
  const srv = await startServer({ MAX_MSG_PER_S: '10' });
  try {
    const a = await connect(srv, sidN());
    for (let i = 0; i < 40; i++) { try { a.send({ t: 'hb', n: i, c: i }); } catch { break; } }
    const cl = await a.waitClose();
    assert.equal(cl.code, 1008); assert.equal(cl.reason, 'rate-limit');
    const b = await connect(srv, sidN());
    for (let i = 0; i < 40; i++) { try { b.ws.ping(); } catch { break; } }
    assert.equal((await b.waitClose()).code, 1008);
    // 한도 안에서 꾸준히 보내면 괜찮다
    const c = await connect(srv, sidN());
    for (let i = 0; i < 6; i++) { c.send({ t: 'hb', n: i, c: i }); await sleep(250); }
    assert.equal(c.closed, null); c.ws.close();
  } finally { await srv.stop(); }
});

test('바이너리 프레임은 1003 으로 거절', async () => {
  const srv = await startServer();
  try {
    const a = await connect(srv, sidN());
    a.ws.send(Buffer.from('abc'), { binary: true });
    const cl = await a.waitClose();
    assert.equal(cl.code, 1003);
  } finally { await srv.stop(); }
});

// ───────────── HTTP ─────────────
test('HTTP: /health 형식 · /ping · / 안내 · CORS 헤더 · no-store · OPTIONS · HEAD', async () => {
  const srv = await startServer();
  try {
    const h = await srv.get('/health');
    assert.equal(h.status, 200);
    assert.equal(h.headers.get('access-control-allow-origin'), '*');
    assert.equal(h.headers.get('cache-control'), 'no-store');
    assert.match(h.headers.get('content-type'), /application\/json/);
    for (const k of ['ok', 'v', 'now', 'up_s', 'conns', 'peak', 'errors', 'rej', 'bench']) assert.ok(k in h.json, k);
    assert.equal(h.json.ok, true); assert.equal(h.json.v, 1); assert.equal(h.json.errors, 0);
    assert.deepEqual(Object.keys(h.json.rej).sort(), ['limit', 'origin', 'sid']);
    const p = await srv.get('/ping');
    assert.ok(Math.abs(p.json.t - Date.now()) < 2000); assert.ok(p.text.length < 40);
    assert.equal(p.headers.get('access-control-allow-origin'), '*');
    const root = await srv.get('/');
    assert.match(root.headers.get('content-type'), /text\/plain/); assert.match(root.text, /레이드/);
    const o = await fetch(srv.http + '/log', { method: 'OPTIONS', headers: { Origin: 'https://x.example', 'Access-Control-Request-Method': 'GET' } });
    assert.equal(o.status, 204); assert.equal(o.headers.get('access-control-allow-origin'), '*');
    const hd = await fetch(srv.http + '/health', { method: 'HEAD' });
    assert.equal(hd.status, 200); assert.equal((await hd.text()), '');
    const l = await srv.get('/log?sid=zzzzzzzz');
    assert.equal(l.headers.get('access-control-allow-origin'), '*');
  } finally { await srv.stop(); }
});

test('/bench: 가장 최근 파일 · name 으로 선택 · list · 경로 조작과 이상한 이름 무시 · 1MB 상한 · 깨진 파일 건너뜀', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'raid-bench-'));
  const w = (n, body, ageSec) => { const f = path.join(dir, n); fs.writeFileSync(f, body); const t = new Date(Date.now() - ageSec * 1000); fs.utimesSync(f, t, t); };
  w('bench_3rooms.json', JSON.stringify({ rooms: 3, p99: 12.5 }), 100);
  w('bench_8rooms.json', JSON.stringify({ rooms: 8, p99: 40 }), 10);
  w('secret.json', JSON.stringify({ secret: true }), 1);            // 패턴 밖 — 무시
  w('bench_.json', '{"x":1}', 1);                                   // 이름 비어 있음 — 무시
  w('bench_broken.json', '{"truncated":', 5);                       // 쓰다 만 파일 — 건너뜀
  fs.symlinkSync('/etc/hostname', path.join(dir, 'bench_link.json')); // 링크 — 무시
  const srv = await startServer({ DATA_DIR: dir });
  try {
    let r = await srv.get('/bench');
    assert.equal(r.json.rooms, 8, '가장 최근(깨진 것·패턴 밖 제외)');
    assert.equal((await srv.get('/bench?name=3rooms')).json.rooms, 3);
    assert.equal((await srv.get('/bench?name=bench_3rooms.json')).json.rooms, 3);
    const l = (await srv.get('/bench?list=1')).json;
    assert.deepEqual(l.files.map((f) => f.name).sort(), ['bench_3rooms.json', 'bench_8rooms.json', 'bench_broken.json']);
    for (const bad of ['../../etc/passwd', '..%2f..%2fetc%2fpasswd', '3rooms/../../x', '%00', 'secret', '..', 'link']) {
      r = await srv.get('/bench?name=' + bad);
      assert.equal(r.json.found, false, bad);
    }
    assert.equal((await srv.get('/bench/../../etc/passwd')).status, 404);
    assert.equal((await srv.get('/health')).json.bench, true);
    // 1MB 초과
    w('bench_huge.json', JSON.stringify({ pad: 'x'.repeat(1024 * 1024 + 10) }), 0);
    r = await srv.get('/bench');
    assert.equal(r.json.found, false); assert.equal(r.json.error, 'too_large');
    assert.ok(r.text.length < 200);
  } finally { await srv.stop(); }
  const empty = await startServer({ DATA_DIR: path.join(dir, 'does-not-exist') });
  try {
    assert.deepEqual((await empty.get('/bench')).json, { found: false });
    assert.equal((await empty.get('/health')).json.bench, false);
  } finally { await empty.stop(); }
});

test('/health 의 setup 필드: DATA_DIR/setup.json 이 있으면 보여 주고, 크면 무시', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'raid-setup-'));
  fs.writeFileSync(path.join(dir, 'setup.json'), JSON.stringify({ ok: true, step: 'done' }));
  const srv = await startServer({ DATA_DIR: dir });
  try {
    assert.deepEqual((await srv.get('/health')).json.setup, { ok: true, step: 'done' });
  } finally { await srv.stop(); }
  fs.writeFileSync(path.join(dir, 'setup.json'), JSON.stringify({ pad: 'x'.repeat(5000) }));
  const srv2 = await startServer({ DATA_DIR: dir });
  try { assert.equal((await srv2.get('/health')).json.setup, null); } finally { await srv2.stop(); }
  // 부하 시험 진행(bench_state.json)은 setup 안의 bench 로 합쳐진다
  fs.writeFileSync(path.join(dir, 'setup.json'), JSON.stringify({ ok: true }));
  fs.writeFileSync(path.join(dir, 'bench_state.json'), JSON.stringify({ state: 'running', msg: '3방' }));
  const srv3 = await startServer({ DATA_DIR: dir });
  try { assert.deepEqual((await srv3.get('/health')).json.setup, { ok: true, bench: { state: 'running', msg: '3방' } }); } finally { await srv3.stop(); }
  fs.rmSync(path.join(dir, 'setup.json'));
  const srv4 = await startServer({ DATA_DIR: dir });
  try { assert.deepEqual((await srv4.get('/health')).json.setup, { bench: { state: 'running', msg: '3방' } }); } finally { await srv4.stop(); }
});

// ───────────── 메모리 한도 ─────────────
test('메모리 한도: 세션 수 상한(가장 오래 안 쓴 것부터 버림, 접속 중인 세션은 유지) · 이벤트 링 버퍼 · 목록 상한', async () => {
  const srv = await startServer({ SESSION_MAX: '5', EVENT_MAX: '10', MAX_MSG_PER_S: '10000' });
  try {
    const keep = sidN('keep');
    const k = await connect(srv, keep);          // 접속 중인 세션은 상한이 넘어도 안 버려진다
    const sids = [];
    for (let i = 0; i < 8; i++) { const s = sidN('m' + i); sids.push(s); const c = await connect(srv, s); c.ws.close(); await c.waitClose(); }
    assert.equal((await srv.get('/log?sid=' + sids[0])).json.found, false, '가장 오래된 것은 버려짐');
    assert.equal((await srv.get('/log?sid=' + sids[7])).json.found, true);
    assert.equal((await srv.get('/log?sid=' + keep)).json.found, true, '접속 중인 세션 유지');
    // 이벤트 링 버퍼: echo 60개 → 10개만 남고 최신이 남는다
    const sid = sidN('ring');
    const a = await connect(srv, sid);
    for (let i = 0; i < 60; i++) a.send({ t: 'custom', n: i });
    await a.next((m) => m.k === 'echo' && m.n === 59);
    const lg = (await srv.get('/log?sid=' + sid)).json;
    assert.equal(lg.events.length, 10);
    assert.equal(lg.events[lg.events.length - 1].ev, 'echo');
    // 목록(closes) 상한 50: 재접속 70번
    const sid3 = sidN('many');
    for (let i = 0; i < 70; i++) { const c = await connect(srv, sid3); c.ws.close(); await c.waitClose(); }
    await sleep(300); // 마지막 close 를 서버가 기록할 시간(클라 쪽 close 가 서버보다 먼저 보일 수 있음)
    const l3 = (await srv.get('/log?sid=' + sid3)).json;
    assert.equal(l3.summary.opened, 70, JSON.stringify(l3.summary).slice(0, 400)); assert.equal(l3.summary.closes.length, 50);
    assert.equal(l3.summary.closes[49].conn, 70);
    a.ws.close(); k.ws.close();
  } finally { await srv.stop(); }
});

test('/log 응답 크기 상한(64KB): 이벤트가 크면 오래된 것부터 줄이고 truncated 표시', async () => {
  const srv = await startServer({ EVENT_MAX: '10000', MAX_MSG_PER_S: '10000', MAX_MSG_BYTES: '4096' });
  try {
    const sid = sidN();
    const a = await connect(srv, sid);
    for (let i = 0; i < 1500; i++) a.send({ t: 'c'.repeat(15), n: i });
    await a.next((m) => m.k === 'echo' && m.n === 1499, 8000);
    const r = await srv.get('/log?sid=' + sid);
    assert.ok(r.text.length <= 64 * 1024, 'len ' + r.text.length);
    assert.equal(r.json.truncated, true);
    assert.equal(r.json.events[r.json.events.length - 1].ev, 'echo');
    a.ws.close();
  } finally { await srv.stop(); }
});

test('오래 지난 세션은 청소된다(SESSION_TTL_S) — 접속 중인 것은 남는다', async () => {
  const srv = await startServer({ SESSION_TTL_S: '1', SWEEP_S: '0.3' });
  try {
    const s1 = sidN('old'); const s2 = sidN('live');
    const c1 = await connect(srv, s1); c1.ws.close(); await c1.waitClose();
    const c2 = await connect(srv, s2);
    await sleep(2200);
    assert.equal((await srv.get('/log?sid=' + s1)).json.found, false);
    assert.equal((await srv.get('/log?sid=' + s2)).json.found, true);
    c2.ws.close();
  } finally { await srv.stop(); }
});

// ───────────── 견고함 ─────────────
test('slowloris: 헤더를 아주 천천히 보내는 연결은 시간 제한으로 끊긴다 / 아무것도 안 보내는 연결도', async () => {
  const srv = await startServer({ HEADERS_TIMEOUT_MS: '600' });
  try {
    const closedAfter = (writer) => new Promise((resolve) => {
      const t0 = Date.now();
      const s = net.connect(srv.port, '127.0.0.1');
      let timer;
      s.on('connect', () => { timer = writer(s); });
      s.on('error', () => {});
      s.resume(); // 읽지 않으면 서버가 끊어도 'close' 가 안 온다
      s.on('close', () => { clearInterval(timer); resolve(Date.now() - t0); });
      setTimeout(() => { clearInterval(timer); s.destroy(); resolve(-1); }, 8000);
    });
    const slow = await closedAfter((s) => {
      s.write('GET /health HTTP/1.1\r\nHost: x\r\n');
      return setInterval(() => { try { s.write('X-Slow: 1\r\n'); } catch { /* 닫힘 */ } }, 150);
    });
    assert.ok(slow > 0 && slow < 6000 * SLACK, 'slowloris 가 끊긴 시간(ms): ' + slow);
    const silent = await closedAfter(() => null);
    assert.ok(silent > 0 && silent < 6000 * SLACK, '무입력 연결이 끊긴 시간(ms): ' + silent);
    // 서버는 멀쩡
    assert.equal((await srv.get('/health')).status, 200);
  } finally { await srv.stop(); }
});

test('쓰레기 입력(깨진 HTTP·거대 헤더·이상한 업그레이드)에도 서버가 안 죽고 errors 가 0', async () => {
  const srv = await startServer();
  try {
    const raw = (data) => new Promise((resolve) => {
      const s = net.connect(srv.port, '127.0.0.1');
      let got = '';
      s.on('data', (d) => { got += d; });
      s.on('error', () => {});
      s.on('close', () => resolve(got));
      s.on('connect', () => s.write(data));
      setTimeout(() => { s.destroy(); }, 1500);
    });
    const g1 = await raw('\x00\x01\x02garbage\r\n\r\n');
    assert.match(g1, /^HTTP\/1\.1 400/);
    const g2 = await raw('GET /' + 'a'.repeat(20000) + ' HTTP/1.1\r\nHost: x\r\n\r\n');
    assert.match(g2, /^HTTP\/1\.1 4(31|14|00)/);
    const g3 = await raw('GET /ws?sid=abcdef12 HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n'); // 키 없음
    assert.match(g3, /^HTTP\/1\.1 400/);
    await raw('GET /health HTTP/1.1\r\nHost: x\r\nContent-Length: 99999999999999999999\r\n\r\n');
    await raw('GET /%zz HTTP/1.1\r\nHost: x\r\n\r\n');
    // 깨진 WebSocket 프레임
    const a = await connect(srv, sidN());
    a.ws._socket.write(Buffer.from([0x81, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]));
    await a.waitClose().catch(() => {});
    await sleep(200);
    const h = (await srv.get('/health')).json;
    assert.equal(h.ok, true); assert.equal(h.errors, 0, 'last_error 없음');
    assert.equal(srv.proc.exitCode, null);
  } finally { await srv.stop(); }
});

test('한 타이머로 연결 40개 모두에게 tick 이 간다(이벤트 루프 안 막힘)', async () => {
  await retry(async () => {
    const srv = await startServer({ MAX_CONN: '100', PER_IP: '100', TICK_MS: '100' });
    try {
      const cs = await Promise.all(Array.from({ length: 40 }, (_, i) => connect(srv, sidN('c' + i))));
      await sleep(1500 * SLACK);
      for (const c of cs) {
        const n = c.msgs.filter((m) => m.t === 'tick').length;
        assert.ok(n >= 10, 'tick 수 ' + n);
      }
      assert.equal((await srv.get('/health')).json.conns, 40);
      cs.forEach((c) => c.ws.close());
    } finally { await srv.stop(); }
  });
});

test('SIGTERM: 소켓에 1001 을 보내고 종료코드 0 으로 깔끔히 종료', async () => {
  const srv = await startServer();
  const a = await connect(srv, sidN());
  const b = await connect(srv, sidN());
  const t0 = Date.now();
  srv.proc.kill('SIGTERM');
  const code = await new Promise((r) => { srv.proc.on('exit', (c) => r(c)); setTimeout(() => r('timeout'), 5000); });
  assert.equal(code, 0);
  assert.ok(Date.now() - t0 < 3000, '종료까지 ' + (Date.now() - t0));
  assert.equal((await a.waitClose()).code, 1001);
  assert.equal((await b.waitClose()).code, 1001);
  assert.match(srv.out, /SIGTERM/);
});

test('환경변수 잘못된 값은 기본값으로 돌아가고 경고만 한다', async () => {
  const srv = await startServer({ MAX_CONN: 'abc', PER_IP: '-5', PING_S: '' });
  try {
    assert.match(srv.err, /MAX_CONN/); assert.match(srv.err, /PER_IP/);
    const a = await connect(srv, sidN());
    assert.equal(a.helloMsg.ping_s, 5);     // 빈 값 → 기본값 5
    a.ws.close();
  } finally { await srv.stop(); }
});
