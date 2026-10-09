#!/usr/bin/env node
/* 레이드 0단계 — G2' 방 부하 측정기 (2026-10-08)

   방마다 worker_threads 1개(설계 §7.1, resourceLimits.maxOldGenerationSizeMb 지정) 안에서 4액터 시뮬을 고정 30Hz 로 돌리고,
   틱 시간(시뮬 update + 스냅샷 인코딩 흉내 + 부모로 transferable 전달)·GC·힙·이벤트 루프 지연·CPU 를 잰다.
   ※ 합격 판정은 목표 사양(서울 1 vCPU VPS)에서만 의미가 있다 — 다른 기계의 값은 참고용이다.

   사용: node tests/raid/bench_rooms.js --rooms 3 --secs 900 [--realtime|--fast] [--hz 30] [--out FILE.json]
                                         [--combos "a,b,c,d;e,f,g,h"] [--src survivors.html] [--build-dir DIR]
                                         [--heap-mb 128] [--seed N] [--hb-timeout-ms 2000] [--load-timeout-s 60]
                                         [--wall-limit-s N] [--strict] [--quiet] [--fault kind:room:atSec]
   기본은 --realtime(드리프트 보정 타이머로 실제 시간에 맞춤). --fast 는 기다리지 않고 최대한 빨리(CI·점검용, 판정 대상 아님).
   --fault 는 이 도구 자신의 시험용(hang|crash|oom|throw): 예) --fault hang:1:3  = 1번 방이 3초 뒤 멈춘다.
   종료코드: 0 끝까지 측정함(게이트 통과 여부와 무관 · --strict 면 미달 시 4) · 1 방이 죽음/멈춤/예외 · 2 빌드(앵커) 실패 · 64 옵션 오류 · 130 SIGINT(중간 결과는 저장함) */
'use strict';
const fs = require('fs'), os = require('os'), path = require('path');
const { Worker } = require('worker_threads');
const { monitorEventLoopDelay } = require('perf_hooks');
const { ensureBuilt, AnchorErr } = require('./build_sim.js');
const { DEFAULT_COMBOS } = require('./mp_run.js');
const { r3 } = require('./bench_stats.js');

const LIMIT_TICK_P99 = 25, LIMIT_LOOP_P99 = 10;
const ELD_RES = 10;   // monitorEventLoopDelay 해상도(ms) — 히스토그램 값은 이 간격이 바탕선이라 지연 = 값 − 해상도

function parseArgs(argv) {
  const o = { rooms: 3, secs: 900, hz: 30, realtime: true, out: null, combos: null, src: null, buildDir: null, heapMb: 128, seed: null,
    hbMs: 2000, loadS: 60, wallLimitS: null, strict: false, quiet: false, fault: null };
  const num = (k, v) => { const n = Number(v); if (!Number.isFinite(n) || n <= 0) { console.error(`${k} 값이 올바른 숫자가 아닙니다: ${v}`); process.exit(64); } return n; };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], nx = () => argv[++i];
    if (a === '--rooms') o.rooms = Math.floor(num(a, nx()));
    else if (a === '--secs') o.secs = num(a, nx());
    else if (a === '--hz') o.hz = num(a, nx());
    else if (a === '--realtime') o.realtime = true;
    else if (a === '--fast') o.realtime = false;
    else if (a === '--out') o.out = nx();
    else if (a === '--combos') o.combos = nx();
    else if (a === '--src') o.src = nx();
    else if (a === '--build-dir') o.buildDir = nx();
    else if (a === '--heap-mb') o.heapMb = num(a, nx());
    else if (a === '--seed') o.seed = Number(nx()) | 0;
    else if (a === '--hb-timeout-ms') o.hbMs = num(a, nx());
    else if (a === '--load-timeout-s') o.loadS = num(a, nx());
    else if (a === '--wall-limit-s') o.wallLimitS = num(a, nx());
    else if (a === '--strict') o.strict = true;
    else if (a === '--quiet') o.quiet = true;
    else if (a === '--fault') { const [kind, room, at] = String(nx()).split(':'); if (!['hang', 'crash', 'oom', 'throw'].includes(kind)) { console.error('--fault 는 hang|crash|oom|throw:방번호:초'); process.exit(64); } o.fault = { kind, room: Number(room) | 0, at: Number(at) || 0 }; }
    else if (a === '-h' || a === '--help') o.help = true;
    else { console.error('알 수 없는 옵션: ' + a); process.exit(64); }
  }
  return o;
}

function cpusAllowed() {
  try { const m = fs.readFileSync('/proc/self/status', 'utf8').match(/Cpus_allowed_list:\s*(\S+)/); return m ? m[1] : null; } catch (e) { return null; }
}

function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help) { console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0]); return Promise.resolve(0); }
  const log = o.quiet ? () => {} : (...a) => console.log(...a);
  let b;
  try { b = ensureBuilt(o.src, o.buildDir); } catch (e) { if (e instanceof AnchorErr) { console.error('BUILD FAIL\n' + e.message); return Promise.resolve(2); } throw e; }
  const code = fs.readFileSync(b.simMpPath, 'utf8');
  const combos = (o.combos ? o.combos.split(';').map(s => s.trim()).filter(Boolean) : DEFAULT_COMBOS).map(c => c.split(',').map(s => s.trim()));
  for (const c of combos) if (c.length !== 4) { console.error('--combos 의 한 방은 캐릭터 4명입니다: ' + c.join(',')); return Promise.resolve(64); }
  const roomChars = Array.from({ length: o.rooms }, (_, i) => combos[i % combos.length]);
  const baseSeed = o.seed != null ? o.seed : 20261008;
  const startedAt = new Date().toISOString();
  const load0 = os.loadavg();
  const cpu0 = process.cpuUsage(), wall0 = process.hrtime.bigint();
  const eld = monitorEventLoopDelay({ resolution: ELD_RES }); eld.enable();
  let rssMax = 0;
  const rssTimer = setInterval(() => { const r = process.memoryUsage.rss(); if (r > rssMax) rssMax = r; }, 1000);
  rssMax = process.memoryUsage.rss();

  log(`[bench] 방 ${o.rooms}개 · ${o.secs}초 · ${o.hz}Hz · ${o.realtime ? 'realtime' : 'fast'} · 힙 한도 ${o.heapMb}MB · cpus_allowed=${cpusAllowed()} · load ${load0.map(v => v.toFixed(2)).join(' ')}`);
  log(`[bench] 조합: ${roomChars.map((c, i) => i + ':' + c.join(',')).join(' | ')}`);

  return new Promise(resolve => {
    const rooms = roomChars.map((chars, id) => ({ id, chars, worker: null, ready: false, lastSeen: 0, snaps: 0, snapBytes: 0, stats: null, status: null, error: null, exited: false, killedBy: null }));
    let interrupted = false, finished = false, hardTimer = null;

    const finish = () => {
      if (finished) return; finished = true;
      clearInterval(hbTimer); clearInterval(rssTimer); if (hardTimer) clearTimeout(hardTimer);
      eld.disable();
      const wallS = Number(process.hrtime.bigint() - wall0) / 1e9;
      const cu = process.cpuUsage(cpu0);
      const sub = v => Math.max(0, v / 1e6 - ELD_RES);
      const loop = { p50: r3(sub(eld.percentile(50))), p99: r3(sub(eld.percentile(99))), max: r3(sub(eld.max)), resolution_ms: ELD_RES, samples: eld.count };
      const outRooms = rooms.map(r => {
        const s = r.stats || {};
        const base = r.stats ? s : { id: r.id, chars: r.chars, ticks: r.snaps, status: r.killedBy || r.status || 'no-stats' };
        const o2 = Object.assign({}, base);
        if (r.killedBy) o2.status = r.killedBy;
        if (!r.stats) { o2.tick_ms = null; o2.update_ms = null; o2.encode_ms = null; o2.late_ticks = null; o2.late_max_ms = null; o2.errors = r.error ? 1 : 0; o2.gc = null; o2.heap_mb_max = null; o2.snap_bytes = { mean: r.snaps ? Math.round(r.snapBytes / r.snaps) : 0, max: null }; }
        if (r.error) o2.error = r.error;
        return o2;
      });
      const bad = outRooms.filter(r => r.status !== 'ok' && r.status !== 'stopped');
      const tickP99s = outRooms.map(r => r.tick_ms && r.tick_ms.p99).filter(v => v != null);
      const tickP99max = tickP99s.length ? Math.max(...tickP99s) : null;
      const cpuPct = r3(((cu.user + cu.system) / 1000) / (wallS * 1000) * 100);
      const m = 'G2 합격 판정은 목표 사양(서울 1 vCPU VPS)에서만 의미가 있다 — 다른 기계의 값은 참고용.';
      let pass, note = m;
      if (o.rooms >= 8) { pass = '기록만'; note += ' 방 8개는 합격이 아니라 기록(1단계 입장 제어가 거절·강등으로 버티는지는 1단계 합격 기준).'; }
      else if (!o.realtime) { pass = '기록만'; note += ' --fast 는 실시간이 아니라(기다리지 않음) 판정 대상이 아니다.'; }
      else if (bad.length || interrupted || tickP99max == null) { pass = false; note += ` 방이 정상 종료하지 못했다(${bad.map(r => r.id + ':' + r.status).join(',') || '중단됨'}).`; }
      else {
        pass = tickP99max <= LIMIT_TICK_P99 && loop.p99 <= LIMIT_LOOP_P99;
        if (o.secs < 900) note += ' 이번 측정은 900초 미만이라 15분 합격 근거가 아니다.';
        if (o.rooms !== 3) note += ` 방 ${o.rooms}개 — 합격 기준은 3방.`;
      }
      const result = {
        v: 1, kind: 'rooms-bench', started_at: startedAt, finished_at: new Date().toISOString(), wall_s: r3(wallS), interrupted,
        host: { node: process.version, cpus: os.cpus().length, cpus_allowed: cpusAllowed(), model: (os.cpus()[0] || {}).model || null,
          loadavg: { start: load0.map(r3), end: os.loadavg().map(r3) }, mem_mb: Math.round(os.totalmem() / 1048576), platform: `${process.platform}-${process.arch}` },
        input: { survivors_sha256: b.manifest.survivors_sha256, actors: 4, hz: o.hz, secs: o.secs, rooms: o.rooms, realtime: o.realtime,
          combos: roomChars.map(c => c.join(',')), heap_mb: o.heapMb, seed: baseSeed, hb_timeout_ms: o.hbMs },
        rooms: outRooms,
        loop_delay_ms: { p50: loop.p50, p99: loop.p99, max: loop.max, resolution_ms: loop.resolution_ms },
        cpu: { user_ms: r3(cu.user / 1000), system_ms: r3(cu.system / 1000), pct_of_1cpu: cpuPct },
        rss_mb_max: r3(rssMax / 1048576),
        gates: { G2: { tick_p99_ms_max_over_rooms: tickP99max, limit: LIMIT_TICK_P99, loop_delay_p99_ms: loop.p99, limit2: LIMIT_LOOP_P99, pass, note } },
      };
      if (o.out) { fs.mkdirSync(path.dirname(path.resolve(o.out)), { recursive: true }); fs.writeFileSync(o.out, JSON.stringify(result, null, 2) + '\n'); }
      if (!o.quiet) printSummary(result);
      resolve(interrupted ? 130 : bad.length ? 1 : (o.strict && pass === false) ? 4 : 0);
    };

    const checkDone = () => { if (rooms.every(r => r.exited)) finish(); };

    const killRoom = (r, why, extra) => {
      if (r.exited || r.killedBy) return;
      r.killedBy = why; if (extra) r.error = extra;
      log(`[bench] 방 ${r.id}: ${why} — 이 방만 terminate`);
      r.worker.terminate().catch(() => {});
    };

    rooms.forEach(r => {
      const fault = o.fault && o.fault.room === r.id ? { kind: o.fault.kind, at: o.fault.at } : null;
      const w = new Worker(path.join(__dirname, 'bench_worker.js'), {
        workerData: { id: r.id, chars: r.chars, secs: o.secs, hz: o.hz, realtime: o.realtime, code, seed: baseSeed + r.id, fault },
        resourceLimits: { maxOldGenerationSizeMb: o.heapMb },
      });
      r.worker = w; r.loadDeadline = Date.now() + o.loadS * 1000;
      w.on('message', m => {
        if (!m) return;
        if (m.t === 'ready') { r.ready = true; r.lastSeen = Date.now(); log(`[bench] 방 ${r.id} 준비(컨텍스트 로드 ${m.load_ms}ms)`); }
        else if (m.t === 'snap') { r.lastSeen = Date.now(); r.snaps++; r.snapBytes += m.buf.byteLength; }
        else if (m.t === 'done') { r.stats = m.stats; r.status = m.stats.status; }
        else if (m.t === 'fatal') { r.error = { message: m.message, stack: m.stack }; r.status = 'fatal'; }
      });
      w.on('error', e => { r.error = { message: String(e && e.message || e), code: e && e.code, stack: String(e && e.stack || '').split('\n').slice(0, 4).join('\n') }; if (!r.killedBy) r.killedBy = /OUT_OF_MEMORY/.test(String(e && e.code)) ? 'oom' : 'crashed'; });
      w.on('exit', code => { r.exited = true; r.exitCode = code; checkDone(); });
    });

    // 하트비트 감시 — 준비된 뒤 hbMs 동안 스냅샷(=하트비트)이 안 오면 그 방만 terminate
    const hbTimer = setInterval(() => {
      const now = Date.now();
      for (const r of rooms) {
        if (r.exited || r.killedBy) continue;
        if (!r.ready) { if (now > r.loadDeadline) killRoom(r, 'load-timeout', { message: `컨텍스트 로드가 ${o.loadS}초 안에 끝나지 않음` }); continue; }
        if (r.stats) continue;   // 끝나는 중
        if (now - r.lastSeen > o.hbMs) killRoom(r, 'killed_hb', { message: `하트비트 ${o.hbMs}ms 무응답(마지막 스냅샷 ${now - r.lastSeen}ms 전)` });
      }
    }, Math.min(250, Math.max(50, o.hbMs / 4)));

    const stopAll = () => { for (const r of rooms) if (!r.exited) try { r.worker.postMessage({ t: 'stop' }); } catch (e) { /* 이미 끝남 */ } };
    let sigs = 0;
    process.on('SIGINT', () => {
      sigs++;
      if (sigs === 1) { interrupted = true; log('\n[bench] SIGINT — 지금까지의 결과를 저장하고 끝냅니다(한 번 더 누르면 즉시 종료)'); stopAll(); setTimeout(() => { for (const r of rooms) if (!r.exited) r.worker.terminate().catch(() => {}); }, 3000).unref(); }
      else { for (const r of rooms) r.worker.terminate().catch(() => {}); setTimeout(() => process.exit(130), 200); }
    });
    // 전체 시간 제한(어떤 이유로든 안 끝날 때) — realtime 은 게임 시간의 2배 + 로드 여유, fast 는 넉넉히
    const limit = (o.wallLimitS != null ? o.wallLimitS : (o.realtime ? o.secs * 2 : Math.max(600, o.secs * 4)) + o.loadS);
    hardTimer = setTimeout(() => { log(`[bench] 전체 시간 제한 ${limit}s 초과 — 남은 방을 멈춥니다`); interrupted = true; stopAll(); setTimeout(() => { for (const r of rooms) if (!r.exited) killRoom(r, 'wall-limit'); }, 3000); }, limit * 1000);
    hardTimer.unref && hardTimer.unref();
  });
}

function printSummary(res) {
  const f = v => (v == null ? '-' : v);
  console.log(`\n[bench] 결과 — 방 ${res.input.rooms} · ${res.input.secs}s · ${res.input.realtime ? 'realtime' : 'fast'} · wall ${res.wall_s}s · host ${res.host.cpus}cpu(허용 ${res.host.cpus_allowed}) load ${res.host.loadavg.start.join('/')}→${res.host.loadavg.end.join('/')}`);
  console.log('방  상태       틱수   tick p50/p95/p99/p99.9/max (ms)             update p99  encode p99  late(최대ms)  GC(횟수/합ms/최대ms)  힙max  snap(평균/최대B)');
  for (const r of res.rooms) {
    const t = r.tick_ms || {};
    console.log(`${String(r.id).padEnd(3)} ${String(r.status).padEnd(10)} ${String(r.ticks).padStart(6)}  ${[t.p50, t.p95, t.p99, t.p999, t.max].map(f).join(' / ').padEnd(40)} ${String(f(r.update_ms && r.update_ms.p99)).padStart(8)}  ${String(f(r.encode_ms && r.encode_ms.p99)).padStart(9)}  ${String(f(r.late_ticks)).padStart(4)}(${f(r.late_max_ms)})  ${r.gc ? r.gc.count + '/' + r.gc.total_ms + '/' + r.gc.max_ms : '-'}  ${f(r.heap_mb_max)}  ${r.snap_bytes ? r.snap_bytes.mean + '/' + r.snap_bytes.max : '-'}${r.error ? '  ERR: ' + r.error.message : ''}${r.first_error ? '  EXC: ' + r.first_error.message : ''}`);
  }
  console.log(`이벤트 루프 지연(부모) p50/p99/max = ${res.loop_delay_ms.p50}/${res.loop_delay_ms.p99}/${res.loop_delay_ms.max} ms · CPU ${res.cpu.pct_of_1cpu}% of 1 CPU (user ${res.cpu.user_ms}ms sys ${res.cpu.system_ms}ms) · rss max ${res.rss_mb_max}MB`);
  const g = res.gates.G2;
  console.log(`G2': tick p99(방 최대) ${g.tick_p99_ms_max_over_rooms} / ${g.limit}ms · 루프 지연 p99 ${g.loop_delay_p99_ms} / ${g.limit2}ms → ${g.pass}`);
  console.log('  ' + g.note);
}

module.exports = { parseArgs };
if (require.main === module) main().then(c => process.exit(c));
