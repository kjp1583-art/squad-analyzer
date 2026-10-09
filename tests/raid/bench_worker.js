/* 레이드 0단계 — 방 하나(워커 스레드) (2026-10-08)

   설계 §7.1: 방당 worker_threads 1개, 그 안에 vm 컨텍스트 하나가 4액터 시뮬을 고정 30Hz 로 돈다.
   틱마다 ① 시뮬 update ② 스냅샷 인코딩 흉내(실제 상태에서 더미 바이트 채움) ③ transferable 로 부모에 postMessage(= 하트비트).
   전체 틱 시간 = ①+②+③ 을 process.hrtime.bigint 로 잰다. bench_rooms.js 가 띄운다(직접 실행하지 않는다).

   일정 정책(--realtime): 틱 n 의 마감 = 기준시각 + n × (1000/hz) ms. 틱이 끝난 시각이 「다음 틱의 마감」을 넘기면 late 로 기록한다.
   따라잡지 않는다 — 밀린 틱을 연달아 몰아서 돌리지 않고(죽음의 나선 방지) 기준시각을 밀린 만큼 뒤로 옮긴다(게임이 실시간보다 느려진다).
   --fast: 기다리지 않고 최대한 빨리(점검용) — late 는 세지 않는다. */
'use strict';
const { parentPort, workerData, isMainThread } = require('worker_threads');
const v8 = require('v8');
const { PerformanceObserver } = require('perf_hooks');
const { loadSimCode } = require('./run_stub.js');
const { summarize, r3 } = require('./bench_stats.js');

if (isMainThread) { console.error('bench_worker.js 는 bench_rooms.js 가 띄우는 파일입니다.'); process.exit(64); }

const { id, chars, secs, hz, realtime, code, seed, fault } = workerData;
const MOVES = [{ KeyD: true }, { KeyS: true }, { KeyA: true }, { KeyW: true }];
const hr = () => Number(process.hrtime.bigint()) / 1e6;   // ms (소수)
const dtMs = 1000 / hz, dt = 1 / hz;
const total = Math.round(secs * hz);

let stopped = false;
parentPort.on('message', m => { if (m && m.t === 'stop') stopped = true; });

// GC 관찰(이 워커의 isolate)
const gc = { count: 0, total_ms: 0, max_ms: 0 };
const obs = new PerformanceObserver(list => { for (const e of list.getEntries()) { gc.count++; gc.total_ms += e.duration; if (e.duration > gc.max_ms) gc.max_ms = e.duration; } });

/* 스냅샷 인코딩 흉내: 머리 100B + 액터 4 × 32B + 살아 있는 적 × 7B. 실제 상태를 양자화해 채운다. */
const HEAD = 100, ACTOR = 32, PER_ENEMY = 7;
function encode(x, n) {
  const enemies = x.enemies.a;
  let live = 0;
  for (let i = 0; i < enemies.length; i++) if (enemies[i].on) live++;
  const len = HEAD + x.ACT.length * ACTOR + live * PER_ENEMY;
  const buf = new ArrayBuffer(len), dv = new DataView(buf);
  dv.setUint32(0, n, true); dv.setFloat32(4, x.S.t, true); dv.setUint16(8, live, true); dv.setUint8(10, x.ACT.length);
  let o = HEAD;
  for (const a of x.ACT) {
    const p = a.b.p;
    dv.setFloat32(o, p.x, true); dv.setFloat32(o + 4, p.y, true); dv.setFloat32(o + 8, p.hp, true); dv.setFloat32(o + 12, p.mhp, true);
    dv.setUint16(o + 16, a.b.lv & 0xffff, true); dv.setFloat32(o + 18, a.b.xp, true); dv.setUint16(o + 22, 0, true); dv.setUint32(o + 24, n, true);
    o += ACTOR;
  }
  for (let i = 0; i < enemies.length; i++) {
    const e = enemies[i]; if (!e.on) continue;
    dv.setInt16(o, Math.max(-32768, Math.min(32767, Math.round(e.x * 0.25))), true);
    dv.setInt16(o + 2, Math.max(-32768, Math.min(32767, Math.round(e.y * 0.25))), true);
    dv.setUint8(o + 4, Math.max(0, Math.min(255, Math.round((e.hp / (e.mhp || 1)) * 255))));
    dv.setUint8(o + 5, (e.ki | 0) & 255);
    dv.setUint8(o + 6, (e.boss ? 1 : 0) | (e.fl > 0 ? 2 : 0));
    o += PER_ENEMY;
  }
  return buf;
}

// 스레드 CPU 시간(선점·대기 제외) — 공용 기계에서 「일 자체의 크기」와 「CPU 를 못 받아 늦은 것」을 가르는 데 쓴다. Node 22.19+ 에서만 있음.
const hasCpu = typeof process.threadCpuUsage === 'function';
const cpuMs = () => { const u = process.threadCpuUsage(); return (u.user + u.system) / 1000; };

const sleep = ms => new Promise(r => setTimeout(r, ms));
const yieldLoop = () => new Promise(r => setImmediate(r));

async function main() {
  const tLoad = hr();
  const win = loadSimCode(code, { seed });
  const x = win.__p6x;
  x.initMP(chars);
  parentPort.postMessage({ t: 'ready', load_ms: r3(hr() - tLoad) });
  try { obs.observe({ entryTypes: ['gc'] }); } catch (e) { gc.unsupported = String(e && e.message); }   // 컨텍스트 로드 뒤부터만 센다(틱 중의 GC 가 대상)

  const A = { tick: new Float64Array(total), upd: new Float64Array(total), enc: new Float64Array(total), start: new Float64Array(total), cpu: new Float64Array(total) };
  let cpuTotal = 0;
  let n = 0, late = 0, lateMax = 0, errors = 0, firstError = null, snapSum = 0, snapMax = 0, heapMax = 0, status = 'ok';
  const t0 = hr();
  let anchor = t0;

  for (; n < total && !stopped; n++) {
    const deadline = anchor + n * dtMs;   // (anchor 는 밀리면 뒤로 옮겨 간다)
    if (realtime) { const w = deadline - hr(); if (w > 0) await sleep(w); else await yieldLoop(); }
    else await yieldLoop();   // 관찰자(GC)·정지 메시지가 돌 틈을 준다
    if (stopped) break;
    const s0 = hr();
    A.start[n] = realtime ? Math.max(0, s0 - deadline) : 0;

    if (fault && fault.at != null && (s0 - t0) / 1000 >= fault.at) {   // 시험 전용 고장 주입
      if (fault.kind === 'hang') { for (;;) { /* 일부러 멈춘다(부모가 2초 뒤 이 방만 terminate) */ } }
      if (fault.kind === 'crash') { setImmediate(() => { throw new Error('시험용 충돌(fault=crash)'); }); await sleep(50); }
      if (fault.kind === 'oom') { const keep = []; for (;;) keep.push(new Array(200000).fill(n)); }
      if (fault.kind === 'throw') { fault.kind = null; try { x.update(NaN); throw new Error('시험용 예외(fault=throw)'); } catch (e) { errors++; firstError = firstError || { at_tick: n, message: String(e.message), stack: String(e.stack).split('\n').slice(0, 4).join('\n') }; status = 'error'; break; } }
    }

    const c0 = hasCpu ? cpuMs() : 0;
    const tS = n / hz;
    x.ACT.forEach((a, i) => { a.keys = MOVES[Math.floor((tS + i * 0.7) / 2.5) % 4]; });
    let u0 = s0, u1 = s0, e1 = s0, p1 = s0;
    try {
      u0 = hr();
      x.update(dt);
      if (x.state !== 'play') { if (x.state === 'result') { status = 'ended_early'; n++; break; } x.resume(); }
      u1 = hr();
      const buf = encode(x, n);
      e1 = hr();
      snapSum += buf.byteLength; if (buf.byteLength > snapMax) snapMax = buf.byteLength;
      parentPort.postMessage({ t: 'snap', n, buf }, [buf]);   // transferable — 하트비트를 겸한다
      p1 = hr();
    } catch (e) {
      errors++; firstError = { at_tick: n, at_game_s: r3(n / hz), message: String(e && e.message || e), stack: String(e && e.stack || e).split('\n').slice(0, 5).join('\n') };
      status = 'error';
      break;   // 실제 서버도 예외가 난 방은 끝낸다
    }
    A.upd[n] = u1 - u0; A.enc[n] = e1 - u1; A.tick[n] = p1 - s0;
    if (hasCpu) { const dc = cpuMs() - c0; A.cpu[n] = dc; cpuTotal += dc; }
    if (n % 30 === 0) { const h = v8.getHeapStatistics().used_heap_size / 1048576; if (h > heapMax) heapMax = h; }
    if (realtime) {
      const next = anchor + (n + 1) * dtMs;
      if (p1 > next) { late++; const l = p1 - next; if (l > lateMax) lateMax = l; anchor += l; }   // 따라잡지 않고 일정을 뒤로 민다
    }
  }
  const wallMs = hr() - t0;
  await yieldLoop();
  try { for (const e of obs.takeRecords()) { gc.count++; gc.total_ms += e.duration; if (e.duration > gc.max_ms) gc.max_ms = e.duration; } } catch (e) { /* 무시 */ }
  obs.disconnect();
  const heapNow = v8.getHeapStatistics();
  if (stopped && status === 'ok') status = 'stopped';
  parentPort.postMessage({ t: 'done', stats: {
    id, chars, ticks: n, status, game_s: r3(n / hz), wall_s: r3(wallMs / 1000),
    tick_ms: summarize(A.tick, n), update_ms: summarize(A.upd, n), encode_ms: summarize(A.enc, n), start_delay_ms: realtime ? summarize(A.start, n) : null,
    tick_cpu_ms: hasCpu ? summarize(A.cpu, n) : null, tick_cpu_ms_total: hasCpu ? r3(cpuTotal) : null,
    late_ticks: late, late_max_ms: r3(lateMax), errors, first_error: firstError,
    gc: { count: gc.count, total_ms: r3(gc.total_ms), max_ms: r3(gc.max_ms), unsupported: gc.unsupported },
    heap_mb_max: r3(Math.max(heapMax, heapNow.used_heap_size / 1048576)), heap_limit_mb: r3(heapNow.heap_size_limit / 1048576),
    snap_bytes: { mean: n ? Math.round(snapSum / n) : 0, max: snapMax },
  } });
  parentPort.close();   // 메시지 수신기가 워커를 붙잡고 있으면 끝나지 않는다 — 닫아야 정상 종료한다
}

main().catch(e => { parentPort.postMessage({ t: 'fatal', message: String(e && e.message || e), stack: String(e && e.stack || e).split('\n').slice(0, 6).join('\n') }); parentPort.close(); });
