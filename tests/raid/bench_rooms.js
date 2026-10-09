#!/usr/bin/env node
/* 레이드 0단계 — G2' 방 부하 측정기 (2026-10-08)

   방마다 worker_threads 1개(설계 §7.1, resourceLimits.maxOldGenerationSizeMb 지정) 안에서 4액터 시뮬을 고정 30Hz 로 돌리고,
   틱 시간(시뮬 update + 스냅샷 인코딩 흉내 + 부모로 transferable 전달)·GC·힙·이벤트 루프 지연·CPU 를 잰다.
   ※ 합격 판정은 목표 사양(서울 1 vCPU VPS)에서만 의미가 있다 — 다른 기계의 값은 참고용이다.
   ※ gates.G2.pass 는 「합격 근거가 되는 조건」(900초 이상 · 방 3개 · realtime · 30Hz · 허용 코어 1개 · 힙 상한 적용 · 기계가 붐비지 않음)을
     모두 채웠을 때만 true/false 이고, 아니면 "참고"(합격도 불합격도 아님)다. 사유는 gates.G2.qualified_unmet 에 있다.

   사용: node tests/raid/bench_rooms.js --rooms 3 --secs 900 [--realtime|--fast] [--hz 30] [--out FILE.json]
                                         [--combos "a,b,c,d;e,f,g,h"] [--src survivors.html] [--build-dir DIR]
                                         [--heap-mb 128] [--seed N] [--hb-timeout-ms 2000] [--load-timeout-s 60]
                                         [--wall-limit-s N] [--strict] [--quiet] [--fault kind:room:atSec] [--world-pools x4|first]
   기본은 --realtime(드리프트 보정 타이머로 실제 시간에 맞춤). --fast 는 기다리지 않고 최대한 빨리(CI·점검용, 판정 대상 아님).
   --fault 는 이 도구 자신의 시험용(hang|crash|oom|throw): 예) --fault hang:1:3  = 1번 방이 3초 뒤 멈춘다.
   --combos 에는 목록 대신 이름 heavy 를 쓸 수 있다(가장 무거운 조합 3개: mp_run.js 의 HEAVY_COMBOS).
   NODE_OPTIONS 에 --max-old-space-size 가 있으면 방별 힙 상한(--heap-mb)이 조용히 무시된다 — 이 도구가 알아채서 경고하고 JSON 에 적는다(VPS 에서는 비우고 돌릴 것).
   종료코드: 0 끝까지 측정함(게이트 통과 여부와 무관 · --strict 면 pass===false 일 때 4) · 1 방이 죽음/멈춤/예외 · 2 빌드(앵커) 실패 · 3 로드 시험 실패
             5 전체 시간 제한(--wall-limit-s)에 걸림 · 6 결과 파일을 못 씀 · 64 옵션 오류 · 66 입력 파일을 못 읽음 · 129/130/143 SIGHUP/SIGINT/SIGTERM(중간 결과는 <out>.partial.json 에 저장)
   중간에 멈춘 결과는 완주한 결과와 섞이지 않도록 --out 이 아니라 <out 에서 .json 을 뗀 이름>.partial.json 에 쓴다. */
'use strict';
const fs = require('fs'), os = require('os'), path = require('path');
const { Worker } = require('worker_threads');
const { monitorEventLoopDelay } = require('perf_hooks');
const { ensureBuilt, buildErrorCode } = require('./build_sim.js');
const { DEFAULT_COMBOS, HEAVY_COMBOS } = require('./mp_run.js');
const { r3 } = require('./bench_stats.js');

const LIMIT_TICK_P99 = 25, LIMIT_LOOP_P99 = 10;
const LIMITS = { rooms_max: 32, secs_max: 21600, hz_max: 240, heap_min_mb: 16, heap_max_mb: 65536 };   // 터무니없는 값은 시작 전에 거절한다
const HEAP_SLACK_MB = 128;   // 보고되는 힙 한도 = maxOldGenerationSizeMb + 젊은 세대(Node 22 에서 +48MB) — 이보다 크면 상한이 무시된 것
const ELD_RES = 10;   // monitorEventLoopDelay 해상도(ms) — 히스토그램 값은 이 간격이 바탕선이라 지연 = 값 − 해상도

function parseArgs(argv) {
  const o = { rooms: 3, secs: 900, hz: 30, realtime: true, out: null, combos: null, src: null, buildDir: null, heapMb: 128, seed: null,
    hbMs: 2000, loadS: 60, wallLimitS: null, strict: false, quiet: false, fault: null, worldPools: 'x4' };
  const num = (k, v, max, min = 0) => {
    const n = Number(v);
    if (!Number.isFinite(n) || n <= 0) { console.error(`${k} 값이 올바른 숫자가 아닙니다: ${v}`); process.exit(64); }
    if (max != null && n > max) { console.error(`${k} 값이 너무 큽니다: ${v} (최대 ${max})`); process.exit(64); }
    if (n < min) { console.error(`${k} 값이 너무 작습니다: ${v} (최소 ${min})`); process.exit(64); }
    return n;
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], nx = () => argv[++i];
    if (a === '--rooms') o.rooms = Math.floor(num(a, nx(), LIMITS.rooms_max));
    else if (a === '--secs') o.secs = num(a, nx(), LIMITS.secs_max);
    else if (a === '--hz') o.hz = num(a, nx(), LIMITS.hz_max);
    else if (a === '--realtime') o.realtime = true;
    else if (a === '--fast') o.realtime = false;
    else if (a === '--out') o.out = nx();
    else if (a === '--combos') o.combos = nx();
    else if (a === '--src') o.src = nx();
    else if (a === '--build-dir') o.buildDir = nx();
    else if (a === '--heap-mb') o.heapMb = num(a, nx(), LIMITS.heap_max_mb, LIMITS.heap_min_mb);
    else if (a === '--seed') o.seed = Number(nx()) | 0;
    else if (a === '--hb-timeout-ms') o.hbMs = num(a, nx(), 600000, 100);
    else if (a === '--load-timeout-s') o.loadS = num(a, nx(), 3600);
    else if (a === '--wall-limit-s') o.wallLimitS = num(a, nx(), 7 * 86400);
    else if (a === '--world-pools') { o.worldPools = nx(); if (!['x4', 'first'].includes(o.worldPools)) { console.error('--world-pools 는 x4|first'); process.exit(64); } }
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

/* 판정 규칙(순수 함수 — sim_selftest 가 표로 시험한다).
   pass: true/false 는 「합격 근거가 되는 조건」을 전부 채웠을 때만. 그렇지 않으면 "참고"(합격도 불합격도 아님)·"기록만".
   방이 정상 종료하지 못했으면(죽음·멈춤·중단) 조건과 무관하게 false — 합격으로 읽힐 일이 없는 쪽이다. */
function judgeG2(c) {
  const unmet = [];
  if (c.secs < 900) unmet.push(`측정 ${c.secs}초 < 900초`);
  if (c.rooms !== 3) unmet.push(`방 ${c.rooms}개 (합격 기준은 3방)`);
  if (!c.realtime) unmet.push('--fast (실시간이 아님)');
  if (c.hz !== 30) unmet.push(`${c.hz}Hz (기준은 30Hz)`);
  if (c.effCores !== 1) unmet.push(`쓸 수 있는 CPU 코어 ${c.effCores}개 (목표는 1 vCPU — taskset -c 0 으로 고정하거나 1코어 기계에서)`);
  if (!c.heapCapEffective) unmet.push('방별 힙 상한이 적용되지 않음 (NODE_OPTIONS 의 --max-old-space-size 가 덮어씀 — 비우고 다시)');
  if (c.loadMax > 2 * c.effCores) unmet.push(`측정 중 기계가 붐볐음 (load ${r3(c.loadMax)} > 코어 ${c.effCores} × 2)`);
  const qualified = unmet.length === 0;
  const withinLimits = c.tickP99max == null ? null : (c.tickP99max <= LIMIT_TICK_P99 && c.loopP99 <= LIMIT_LOOP_P99);
  let pass, note = 'G2 합격 판정은 목표 사양(서울 1 vCPU VPS)에서만 의미가 있다 — 다른 기계의 값은 참고용.';
  if (c.rooms >= 8) { pass = '기록만'; note += ' 방 8개는 합격이 아니라 기록(1단계 입장 제어가 거절·강등으로 버티는지는 1단계 합격 기준).'; }
  else if (!c.realtime) { pass = '기록만'; note += ' --fast 는 실시간이 아니라(기다리지 않음) 판정 대상이 아니다.'; }
  else if (c.badIds.length || c.interrupted || c.tickP99max == null) { pass = false; note += ` 방이 정상 종료하지 못했다(${c.badIds.join(',') || '중단됨' + (c.interruptedBy ? '·' + c.interruptedBy : '')}).`; }
  else if (!qualified) { pass = '참고'; note += ` 이번 측정은 합격 판정의 조건을 못 채워 합격도 불합격도 아니다(수치는 한도 ${withinLimits ? '안' : '밖'}): ` + unmet.join(' · ') + '.'; }
  else pass = withinLimits;
  return { pass, qualified, unmet, withinLimits, note };
}

// "0-3,5" → 4+1=5 개
function countCpuList(l) {
  if (!l) return null;
  let n = 0;
  for (const part of String(l).split(',')) {
    const m = part.trim().match(/^(\d+)(?:-(\d+))?$/);
    if (!m) return null;
    n += m[2] != null ? Number(m[2]) - Number(m[1]) + 1 : 1;
  }
  return n > 0 ? n : null;
}
const readText = f => { try { return fs.readFileSync(f, 'utf8').trim(); } catch (e) { return null; } };
/* cgroup 이 CPU 를 제한하는지(컨테이너·systemd 유닛) — v2 cpu.max / v1 cfs_quota. quota_cpus = 쿼터 ÷ 주기(제한 없으면 null) */
function cgroupCpu() {
  const cpuMax = readText('/sys/fs/cgroup/cpu.max'), weight = readText('/sys/fs/cgroup/cpu.weight');
  let quota = null;
  if (cpuMax) { const [q, p] = cpuMax.split(/\s+/); if (q !== 'max' && Number(q) > 0 && Number(p) > 0) quota = Number(q) / Number(p); }
  else {
    const q = Number(readText('/sys/fs/cgroup/cpu/cpu.cfs_quota_us')), p = Number(readText('/sys/fs/cgroup/cpu/cpu.cfs_period_us'));
    if (q > 0 && p > 0) quota = q / p;
  }
  return { cpu_max: cpuMax, cpu_weight: weight, quota_cpus: quota == null ? null : r3(quota) };
}
const NODE_OPTIONS_HEAP = /--max[-_]old[-_]space[-_]size/;
function heapFlagFromEnv() { return NODE_OPTIONS_HEAP.test(process.env.NODE_OPTIONS || '') || process.execArgv.some(a => NODE_OPTIONS_HEAP.test(a)); }

/* --out 이 쓸 수 있는 곳인지 측정 전에 확인한다(15분 재고 나서 저장이 안 되는 일을 막는다). 문제가 있으면 사유 문자열. */
function checkOutWritable(out) {
  const abs = path.resolve(out);
  if (/^\/(proc|sys|dev)(\/|$)/.test(abs)) return `${abs} — 쓸 수 없는 가상 폴더입니다`;
  let dir = path.dirname(abs);
  while (!fs.existsSync(dir)) { const up = path.dirname(dir); if (up === dir) break; dir = up; }   // 가장 가까운 기존 상위 폴더
  try { if (!fs.statSync(dir).isDirectory()) return `${dir} 는 폴더가 아닙니다`; fs.accessSync(dir, fs.constants.W_OK); } catch (e) { return `${dir} 에 쓸 수 없습니다 (${e.code || e.message})`; }
  try {
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    const probe = abs + '.probe-' + process.pid; fs.writeFileSync(probe, 'x'); fs.unlinkSync(probe);
  } catch (e) { return `${abs} 를 만들 수 없습니다 (${e.code || e.message})`; }
  return null;
}
/* 결과를 임시 이름으로 쓰고 바꿔치기한다(읽는 쪽이 반쯤 쓴 파일을 보지 않게). 실패하면 사유 문자열. */
function saveJson(file, obj) {
  try {
    const abs = path.resolve(file), tmp = abs + '.tmp-' + process.pid;
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(tmp, JSON.stringify(obj, null, 2) + '\n'); fs.renameSync(tmp, abs);
    return null;
  } catch (e) { return String(e && e.message || e); }
}
const partialName = out => out.replace(/\.json$/i, '') + '.partial.json';

function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help) { console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0]); return Promise.resolve(0); }
  const log = o.quiet ? () => {} : (...a) => console.log(...a);
  if (o.fault && o.fault.kind === 'oom' && heapFlagFromEnv()) { console.error('--fault oom 은 방별 힙 상한이 적용될 때만 안전합니다(NODE_OPTIONS/명령줄에 --max-old-space-size 가 있으면 상한이 무시되어 기계 메모리를 다 먹습니다). `env -u NODE_OPTIONS node …` 로 다시 실행하세요.'); return Promise.resolve(64); }
  if (o.out) { const why = checkOutWritable(o.out); if (why) { console.error('--out 을 쓸 수 없어 측정을 시작하지 않습니다: ' + why); return Promise.resolve(64); } }
  let b;
  try { b = ensureBuilt(o.src, o.buildDir, { worldPools: o.worldPools }); } catch (e) { const c = buildErrorCode(e); if (c != null) return Promise.resolve(c); throw e; }
  const code = fs.readFileSync(b.simMpPath, 'utf8');
  const comboList = o.combos === 'heavy' ? HEAVY_COMBOS : (o.combos ? o.combos.split(';').map(s => s.trim()).filter(Boolean) : DEFAULT_COMBOS);
  const combos = comboList.map(c => c.split(',').map(s => s.trim()));
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
    let interrupted = false, interruptedBy = null, finished = false, hardTimer = null, heapCapEffective = true;
    const heapSeen = [];   // 방이 보고한 실제 힙 한도(MB)

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
        if (!r.stats) { o2.tick_ms = null; o2.update_ms = null; o2.encode_ms = null; o2.late_ticks = null; o2.late_max_ms = null; o2.errors = r.error ? 1 : 0; o2.gc = null; o2.heap_mb_max = null; o2.heap_limit_mb = r.heapLimitMb != null ? r.heapLimitMb : null; o2.snap_bytes = { mean: r.snaps ? Math.round(r.snapBytes / r.snaps) : 0, max: null }; }
        if (r.error) o2.error = r.error;
        return o2;
      });
      const bad = outRooms.filter(r => r.status !== 'ok' && r.status !== 'stopped');
      const tickP99s = outRooms.map(r => r.tick_ms && r.tick_ms.p99).filter(v => v != null);
      const tickP99max = tickP99s.length ? Math.max(...tickP99s) : null;
      const roomGameS = outRooms.reduce((a, r) => a + (r.game_s != null ? r.game_s : (r.ticks || 0) / o.hz), 0);   // 방들이 돌린 게임 시간의 합(초)
      const cpuPct = r3(((cu.user + cu.system) / 1000) / (wallS * 1000) * 100);

      // ── 합격 근거가 되는 조건인가 ──
      const allowedList = cpusAllowed(), allowedN = countCpuList(allowedList), cg = cgroupCpu();
      const effCores = Math.min(allowedN != null ? allowedN : os.cpus().length, cg.quota_cpus != null ? Math.max(1, Math.ceil(cg.quota_cpus - 1e-9)) : Infinity);
      const loadEnd = os.loadavg();
      const judged = judgeG2({ rooms: o.rooms, secs: o.secs, hz: o.hz, realtime: o.realtime, effCores, heapCapEffective, loadMax: Math.max(load0[0], loadEnd[0]),
        badIds: bad.map(r => r.id + ':' + r.status), interrupted, interruptedBy, tickP99max, loopP99: loop.p99 });
      const { unmet, qualified, withinLimits } = judged;
      const ratio = (a, n) => (n ? r3(a / n) : null);
      const ok_rooms = outRooms.filter(r => r.tick_ms && r.ticks);
      const maxOf = f => { const v = ok_rooms.map(f).filter(x => x != null); return v.length ? Math.max(...v) : null; };
      const aux = {
        // 보조 지표(판정에는 안 쓰임 — 합격 지표 tick p99 는 1% 정지를 통과시키므로 함께 본다. 설계서에는 「25ms 초과 틱 비율 ≤ 0.1%」를 보조 기준으로 제안)
        late_ratio_max: maxOf(r => ratio(r.late_ticks, r.ticks)), tick_over_25ms_ratio_max: maxOf(r => ratio(r.tick_over_25ms, r.ticks)),
        deadline_p99_ms_max: maxOf(r => r.deadline_ms && r.deadline_ms.p99), slip_s_max: maxOf(r => r.slip_s),
        suggested_over25_ratio_limit: 0.001,
      };
      aux.over25_within_suggested = aux.tick_over_25ms_ratio_max == null ? null : aux.tick_over_25ms_ratio_max <= aux.suggested_over25_ratio_limit;
      let pass = judged.pass, note = judged.note;
      if (aux.slip_s_max != null && aux.slip_s_max > 1) note += ` 과부하로 게임 시간이 벽시계보다 최대 ${aux.slip_s_max}초 느려졌다(slip_s) — 스트레스가 덜어진 측정이다.`;
      const exitCode = interruptedBy === 'SIGINT' ? 130 : interruptedBy === 'SIGTERM' ? 143 : interruptedBy === 'SIGHUP' ? 129 : interruptedBy === 'wall-limit' ? 5
        : bad.length ? 1 : (o.strict && pass === false) ? 4 : 0;
      const result = {
        v: 1, kind: 'rooms-bench', started_at: startedAt, finished_at: new Date().toISOString(), wall_s: r3(wallS), interrupted, interrupted_by: interruptedBy,
        host: { node: process.version, cpus: os.cpus().length, cpus_allowed: allowedList, cores_effective: effCores, model: (os.cpus()[0] || {}).model || null,
          loadavg: { start: load0.map(r3), end: loadEnd.map(r3) }, mem_mb: Math.round(os.totalmem() / 1048576), platform: `${process.platform}-${process.arch}`,
          node_options: process.env.NODE_OPTIONS || null, nice: (() => { try { return os.getPriority(); } catch (e) { return null; } })(), cgroup: cg },
        input: { survivors_sha256: b.manifest.survivors_sha256, actors: 4, hz: o.hz, secs: o.secs, rooms: o.rooms, realtime: o.realtime,
          combos: roomChars.map(c => c.join(',')), heap_mb: o.heapMb, heap_cap_effective: heapCapEffective, heap_limit_reported_mb: heapSeen.length ? Math.max(...heapSeen) : null,
          world_pools: o.worldPools, seed: baseSeed, hb_timeout_ms: o.hbMs },
        rooms: outRooms,
        loop_delay_ms: { p50: loop.p50, p99: loop.p99, max: loop.max, resolution_ms: loop.resolution_ms },
        cpu: { user_ms: r3(cu.user / 1000), system_ms: r3(cu.system / 1000), pct_of_1cpu: cpuPct,
          // 방 1개가 게임 1초를 돌리는 데 쓴 CPU(ms) — 공용 기계·--fast 에서도 의미가 있다. 실시간(30Hz)으로 전용 코어에서 돌린다면 필요한 점유율의 추정.
          ms_per_room_game_s: roomGameS ? r3((cu.user + cu.system) / 1000 / roomGameS) : null,
          est_realtime_pct_of_1cpu: roomGameS && wallS ? r3(((cu.user + cu.system) / 1000 / roomGameS) * o.rooms / 10) : null },
        rss_mb_max: r3(rssMax / 1048576),
        gates: { G2: { tick_p99_ms_max_over_rooms: tickP99max, limit: LIMIT_TICK_P99, loop_delay_p99_ms: loop.p99, limit2: LIMIT_LOOP_P99,
          within_limits: withinLimits, qualified, qualified_unmet: unmet, pass, aux, note } },
      };
      // 요약을 먼저 찍고(저장이 실패해도 숫자는 남는다) 저장한다. 중간에 멈춘 결과는 완주한 결과 이름을 쓰지 않는다.
      if (!o.quiet) printSummary(result);
      let saveFailed = false;
      if (o.out) {
        const target = interrupted ? partialName(o.out) : o.out;
        const err = saveJson(target, result);
        if (err) { saveFailed = true; console.error('결과 파일을 쓰지 못했습니다: ' + target + ' — ' + err + '\n아래에 JSON 전체를 찍습니다.'); console.log(JSON.stringify(result)); }
        else log(`[bench] 결과 저장: ${target}`);
      }
      resolve(exitCode === 0 && saveFailed ? 6 : exitCode);
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
        if (m.t === 'ready') {
          r.ready = true; r.lastSeen = Date.now(); r.heapLimitMb = m.heap_limit_mb; log(`[bench] 방 ${r.id} 준비(컨텍스트 로드 ${m.load_ms}ms · 힙 한도 ${m.heap_limit_mb}MB)`);
          // resourceLimits.maxOldGenerationSizeMb 가 정말 적용됐는지: 적용되면 보고되는 한도는 --heap-mb + 젊은 세대(약 48MB) 안팎이다.
          // NODE_OPTIONS 의 --max-old-space-size 가 있으면 조용히 덮어써서 훨씬 큰 값이 보고된다(2026-10-09 실측: 4~128MB 어느 값이든 8240).
          if (m.heap_limit_mb != null) heapSeen.push(m.heap_limit_mb);
          if (m.heap_limit_mb != null && m.heap_limit_mb > o.heapMb + HEAP_SLACK_MB) {
            if (heapCapEffective) console.error(`WARN 방별 힙 상한 ${o.heapMb}MB 가 적용되지 않았습니다(방이 보고한 한도 ${m.heap_limit_mb}MB). NODE_OPTIONS=${JSON.stringify(process.env.NODE_OPTIONS || '')} 의 --max-old-space-size 가 덮어쓴 것으로 보입니다 — 설계 §7.1 의 「한 방의 메모리 폭주는 그 방만」 격리가 이 측정에서는 검증되지 않습니다. NODE_OPTIONS 를 비우고(env -u NODE_OPTIONS) 다시 재세요.`);
            heapCapEffective = false;
          }
        }
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
    const SIGCODE = { SIGINT: 130, SIGTERM: 143, SIGHUP: 129 };
    for (const sig of Object.keys(SIGCODE)) process.on(sig, () => {
      sigs++;
      if (sigs === 1) {
        interrupted = true; interruptedBy = sig;
        log(`\n[bench] ${sig} — 지금까지의 결과를 <out>.partial.json 에 저장하고 끝냅니다(한 번 더 보내면 즉시 종료)`);
        stopAll(); setTimeout(() => { for (const r of rooms) if (!r.exited) r.worker.terminate().catch(() => {}); }, 3000).unref();
      } else { for (const r of rooms) r.worker.terminate().catch(() => {}); setTimeout(() => process.exit(SIGCODE[sig]), 200); }
    });
    // 전체 시간 제한(어떤 이유로든 안 끝날 때) — realtime 은 게임 시간의 2배 + 로드 여유, fast 는 넉넉히
    const limit = (o.wallLimitS != null ? o.wallLimitS : (o.realtime ? o.secs * 2 : Math.max(600, o.secs * 4)) + o.loadS);
    hardTimer = setTimeout(() => { log(`[bench] 전체 시간 제한 ${limit}s 초과 — 남은 방을 멈춥니다`); interrupted = true; interruptedBy = interruptedBy || 'wall-limit'; stopAll(); setTimeout(() => { for (const r of rooms) if (!r.exited) killRoom(r, 'wall-limit'); }, 3000); }, limit * 1000);
    hardTimer.unref && hardTimer.unref();
  });
}

function printSummary(res) {
  const f = v => (v == null ? '-' : v);
  console.log(`\n[bench] 결과 — 방 ${res.input.rooms} · ${res.input.secs}s · ${res.input.realtime ? 'realtime' : 'fast'} · wall ${res.wall_s}s · host ${res.host.cpus}cpu(허용 ${res.host.cpus_allowed}) load ${res.host.loadavg.start.join('/')}→${res.host.loadavg.end.join('/')}`);
  console.log('방  상태       틱수   tick p50/p95/p99/p99.9/max (ms)             update p99  encode p99  CPU시간 p99/max  late(최대ms)  GC(횟수/합ms/최대ms)  힙max  snap(평균/최대B)');
  for (const r of res.rooms) {
    const t = r.tick_ms || {};
    console.log(`${String(r.id).padEnd(3)} ${String(r.status).padEnd(10)} ${String(r.ticks).padStart(6)}  ${[t.p50, t.p95, t.p99, t.p999, t.max].map(f).join(' / ').padEnd(40)} ${String(f(r.update_ms && r.update_ms.p99)).padStart(8)}  ${String(f(r.encode_ms && r.encode_ms.p99)).padStart(9)}  ${(r.tick_cpu_ms ? r.tick_cpu_ms.p99 + '/' + r.tick_cpu_ms.max : '-').padStart(14)}  ${String(f(r.late_ticks)).padStart(4)}(${f(r.late_max_ms)})  ${r.gc ? r.gc.count + '/' + r.gc.total_ms + '/' + r.gc.max_ms : '-'}  ${f(r.heap_mb_max)}  ${r.snap_bytes ? r.snap_bytes.mean + '/' + r.snap_bytes.max : '-'}${r.error ? '  ERR: ' + r.error.message : ''}${r.first_error ? '  EXC: ' + r.first_error.message : ''}`);
  }
  console.log(`이벤트 루프 지연(부모) p50/p99/max = ${res.loop_delay_ms.p50}/${res.loop_delay_ms.p99}/${res.loop_delay_ms.max} ms · CPU ${res.cpu.pct_of_1cpu}% of 1 CPU (user ${res.cpu.user_ms}ms sys ${res.cpu.system_ms}ms) · rss max ${res.rss_mb_max}MB`);
  const g = res.gates.G2;
  const verdict = g.pass === true ? '합격' : g.pass === false ? '불합격' : g.pass === '참고' ? '참고(합격 판정 아님)' : String(g.pass);
  console.log(`G2': tick p99(방 최대) ${g.tick_p99_ms_max_over_rooms} / ${g.limit}ms · 루프 지연 p99 ${g.loop_delay_p99_ms} / ${g.limit2}ms → ${verdict}`);
  const x = g.aux;
  console.log(`  보조: 25ms 초과 틱 비율 최대 ${x.tick_over_25ms_ratio_max}(제안 한도 ${x.suggested_over25_ratio_limit}) · late 비율 최대 ${x.late_ratio_max} · 마감 대비 완료 지연 p99 최대 ${x.deadline_p99_ms_max}ms · slip ${x.slip_s_max}초`);
  console.log('  ' + g.note);
}

module.exports = { parseArgs, judgeG2, countCpuList, checkOutWritable };
if (require.main === module) main().then(c => process.exit(c));
