#!/usr/bin/env node
/* 레이드 0단계 — 4액터 시뮬 실행기 (2026-10-08)

   sim_mp.js(4액터 패치 사본)를 스텁에 올려 고정 dt 로 N초(게임 시간)를 빨리 감는다.
   예외가 나면 게임 시각·스택을 찍고 종료코드 1. 판이 중간에 끝나거나(결과 화면), 상태가 풀리지 않거나, 값이 NaN/Infinity 가 되어도 실패다.

   사용: node tests/raid/mp_run.js [--combo brj,jjg,mms,hrb] [--secs 900] [--hz 30] [--seed 1] [--move circle|stand|random]
                                    [--src survivors.html] [--build-dir DIR] [--json] [--out FILE.json] [--cpu] [--world-pools x4|first]
   종료코드: 0 통과 · 1 예외 · 4 판이 일찍 끝남/상태 멈춤/비정상 값/게임 시각이 N초가 아님 · 2 빌드(앵커) 실패 · 3 로드 시험 실패 · 64 옵션 오류 · 66 입력 파일을 못 읽음 */
'use strict';
const fs = require('fs'), path = require('path');
const { ensureBuilt, buildErrorCode } = require('./build_sim.js');
const { loadSimFile } = require('./run_stub.js');

// 기본 5조합: 2026-10-08 첫 스파이크에서 쓰던 것(재현용). g4_test.py·bench_rooms.js 가 같은 목록을 쓴다.
const DEFAULT_COMBOS = ['brj,jjg,mms,hrb', 'ssu,amd,ildj,kyo', 'ddmj,psg,sr,ddo', 'tw,yumi,eom,yj', 'bgb,brj,psg,sr'];
// 기본 조합에 없는 캐릭터를 채우는 「보강 조합」의 빈자리 채움 순서(첫 스파이크에서 가장 무거웠던 조합의 캐릭터부터)
const PAD = ['eom', 'yj', 'tw', 'yumi', 'sr', 'ddo'];
// 가장 무거운 조합들(900초 CPU 실측 기준 틱당 평균이 큰 쪽: 3.9ms 안팎) — 합격 판정은 이쪽으로도 재 보라고 bench_rooms.js --combos heavy 가 쓴다
const HEAVY_COMBOS = ['ssu,amd,ildj,kyo', 'bbb,eom,yj,tw', 'ssu,amd,ildj,kyo'];
const MOVES = [{ KeyD: true }, { KeyS: true }, { KeyA: true }, { KeyW: true }];

/* 상태 해시: 같은 시드로 두 번 돌렸을 때 판이 같은지 보는 용도(액터 위치·체력·레벨·살아 있는 적). */
function stateHash(x) {
  let h = 0;
  const add = v => { h = (Math.imul(h ^ (Math.round(v * 1000) | 0), 16777619)) >>> 0; };
  add(x.S.t); add(x.S.kills || 0);
  for (const a of x.ACT) { const p = a.b.p; add(p.x); add(p.y); add(p.hp); add(a.b.lv); add(a.b.xp); }
  for (const e of x.enemies.a) if (e.on) { add(e.x); add(e.y); add(e.hp); }
  return h.toString(16).padStart(8, '0');
}

function pickKeys(move, t, i, rnd) {
  if (move === 'stand') return {};
  if (move === 'random') return MOVES[Math.floor(rnd() * 4)];
  return MOVES[Math.floor((t + i * 0.7) / 2.5) % 4];   // circle: 사각형으로 도는 봇(첫 스파이크와 같은 움직임)
}

/* 한 조합을 돌린다. opts: {combo:[키…], secs, hz, seed, move, simMpPath, cpu, onTick} → 결과 객체(예외도 담는다) */
function runCombo(opts) {
  const hz = opts.hz || 30, secs = opts.secs || 300, dt = 1 / hz, move = opts.move || 'circle';
  const win = loadSimFile(opts.simMpPath, { seed: opts.seed != null ? opts.seed : undefined, trace: !!opts.trace });
  const x = win.__p6x;
  const res = { combo: opts.combo.join(','), secs, hz, seed: opts.seed != null ? opts.seed : null, move, ok: false, ticks: 0, error: null, ended_early: null, stuck: null, nonfinite: null, time_mismatch: null, hashes: [], hash_final: null };
  let rs = (opts.seed != null ? opts.seed : 12345) >>> 0;
  const rnd = () => { rs = (rs + 0x6D2B79F5) | 0; let t = Math.imul(rs ^ (rs >>> 15), 1 | rs); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  try { x.initMP(opts.combo); }
  catch (e) { res.error = { at_game_s: 0, tick: -1, message: String(e && e.message || e), stack: String(e && e.stack || e).split('\n').slice(0, 4).join('\n'), where: 'initMP' }; res.wall_ms = 0; res.ok = false; res.actors = []; res.weapons_start = []; return res; }
  res.weapons_start = x.ACT.map(a => Object.keys(a.b.w));
  const total = Math.round(secs * hz);
  let maxE = 0, stuckN = 0, lastBad = '';
  const t0 = process.hrtime.bigint(), c0 = process.cpuUsage();
  for (let s = 0; s < total; s++) {
    const t = s / hz;
    x.ACT.forEach((a, i) => { a.keys = pickKeys(move, t, i, rnd); });
    try { x.update(dt); }
    catch (e) { res.error = { at_game_s: +(s * dt).toFixed(2), tick: s, message: String(e && e.message || e), stack: String(e && e.stack || e).split('\n').slice(0, 6).join('\n') }; break; }
    res.ticks++;
    if (x.ENDS > 0 || x.state === 'result') { res.ended_early = { at_game_s: +(s * dt).toFixed(2), why: x.ENDS > 0 ? 'endRun() 이 불렸다(판 종료)' : '결과 화면(result)으로 넘어갔다' }; break; }
    if (x.state !== 'play') {
      const was = x.state;
      try { x.resume(); }
      catch (e) { res.error = { at_game_s: +(s * dt).toFixed(2), tick: s, message: String(e && e.message || e), stack: String(e && e.stack || e).split('\n').slice(0, 6).join('\n'), where: 'resume()' }; break; }
      // resume 이 상태를 못 바꾸면(이어하기 모듈의 stale 판정 등이 조용히 막는 경우) 무한 정지다 — 3틱 연속이면 실패로 본다
      if (x.state === was) { if (++stuckN >= 3) { res.stuck = { at_game_s: +(s * dt).toFixed(2), state: was }; break; } } else stuckN = 0;
    } else stuckN = 0;
    if (s % 300 === 0) {
      let ne = 0; for (const e of x.enemies.a) if (e.on) ne++;
      if (ne > maxE) maxE = ne;
      // NaN/Infinity 가드(설계 §7.1): 액터 위치·체력이 유한한 수인지
      for (let i = 0; i < x.ACT.length; i++) {
        const p = x.ACT[i].b.p;
        if (!(Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.hp))) { lastBad = `액터 ${i}(${x.ACT[i].ch.k}) x=${p.x} y=${p.y} hp=${p.hp}`; break; }
      }
      if (lastBad) { res.nonfinite = { at_game_s: +(s * dt).toFixed(2), what: lastBad }; break; }
    }
    if (s % (hz * 30) === 0) res.hashes.push(stateHash(x));   // 30초(게임 시간)마다
    if (opts.onTick) opts.onTick(s, x);
  }
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  const cu = process.cpuUsage(c0);
  x.use(0);
  res.wall_ms = +ms.toFixed(1);
  res.ms_per_tick = res.ticks ? +(ms / res.ticks).toFixed(3) : null;
  if (opts.cpu) res.cpu_ms_per_tick = res.ticks ? +(((cu.user + cu.system) / 1000) / res.ticks).toFixed(3) : null;
  res.game_s = +x.S.t.toFixed(1);
  res.hash_final = stateHash(x);
  res.max_enemies = maxE;
  res.deaths_absorbed = x.NDEATH;
  res.actors = x.ACT.map((a, i) => {
    const dm = a.b.dmgBy || {}; const tot = Object.values(dm).reduce((s, v) => s + v, 0);
    return { i, k: a.ch.k, lv: a.b.lv, dmg: Math.round(tot), weapons: Object.assign({}, a.b.w) };
  });
  // 무기별 피해 기록(전 액터 합) — g4/cover 가 "무기 사용"을 판정할 때 쓴다
  const used = {}; x.ACT.forEach(a => { for (const k in (a.b.dmgBy || {})) used[k] = (used[k] || 0) + a.b.dmgBy[k]; });
  res.dmg_by = used;
  // 틱 수만 맞고 게임 시각이 다르면(고정 dt 가 어긋난 경우 등) 「N초를 돌렸다」는 말이 거짓이다
  if (!res.error && res.ticks === total && Math.abs(res.game_s - secs) >= 1) res.time_mismatch = { game_s: res.game_s, secs };
  res.ok = !res.error && !res.ended_early && !res.stuck && !res.nonfinite && !res.time_mismatch && res.ticks === total;
  if (opts.trace) res.stub = require('./run_stub.js').stubReport(win);
  return res;
}

function parseArgs(argv) {
  const o = { combo: 'brj,jjg,mms,hrb', secs: 900, hz: 30, seed: null, move: 'circle', src: null, buildDir: null, json: false, out: null, cpu: false, trace: false, worldPools: 'x4' };
  const num = (k, v) => { const n = Number(v); if (!Number.isFinite(n) || n <= 0) { console.error(`${k} 값이 숫자가 아닙니다: ${v}`); process.exit(64); } return n; };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], nx = () => argv[++i];
    if (a === '--combo') o.combo = nx();
    else if (a === '--secs') o.secs = num(a, nx());
    else if (a === '--hz') o.hz = num(a, nx());
    else if (a === '--seed') o.seed = Number(nx()) | 0;
    else if (a === '--move') { o.move = nx(); if (!['circle', 'stand', 'random'].includes(o.move)) { console.error('--move 는 circle|stand|random'); process.exit(64); } }
    else if (a === '--src') o.src = nx();
    else if (a === '--build-dir') o.buildDir = nx();
    else if (a === '--json') o.json = true;
    else if (a === '--out') o.out = nx();
    else if (a === '--cpu') o.cpu = true;
    else if (a === '--trace') o.trace = true;
    else if (a === '--world-pools') { o.worldPools = nx(); if (!['x4', 'first'].includes(o.worldPools)) { console.error('--world-pools 는 x4|first'); process.exit(64); } }
    else if (a === '--list') o.list = true;
    else if (a === '-h' || a === '--help') { o.help = true; }
    else { console.error('알 수 없는 옵션: ' + a); process.exit(64); }
  }
  return o;
}

function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help) { console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0]); return 0; }
  let b;
  try { b = ensureBuilt(o.src, o.buildDir, { worldPools: o.worldPools }); } catch (e) { const c = buildErrorCode(e); if (c != null) return c; throw e; }
  if (o.list) {   // 캐릭터·무기 목록(g4_test.py 가 조합을 검사할 때 쓴다)
    const w = loadSimFile(b.simMpPath), x = w.__p6x;
    console.log(JSON.stringify({ chars: x.CHARS.map(c => c.k), weapons: Object.keys(x.WEAP), default_combos: DEFAULT_COMBOS, pad: PAD, survivors_sha256: b.manifest.survivors_sha256 }));
    return 0;
  }
  const combo = o.combo.split(',').map(s => s.trim()).filter(Boolean);
  if (combo.length !== 4) { console.error('--combo 는 캐릭터 키 4개를 쉼표로(예: brj,jjg,mms,hrb)'); return 64; }
  const r = runCombo({ combo, secs: o.secs, hz: o.hz, seed: o.seed, move: o.move, simMpPath: b.simMpPath, cpu: o.cpu, trace: o.trace });
  r.survivors_sha256 = b.manifest.survivors_sha256;
  if (!o.json) {
    console.log(`[mp_run] 조합 ${r.combo} · ${r.secs}초 · ${r.hz}Hz · move=${r.move}${r.seed != null ? ' · seed=' + r.seed : ''}`);
    if (r.actors.length) console.log('actors', r.actors.length, 'weapons per actor', JSON.stringify(r.weapons_start));
    if (r.actors.length) console.log(`ticks ${r.ticks} ms/tick ${r.ms_per_tick}${r.cpu_ms_per_tick != null ? ' CPU ms/tick ' + r.cpu_ms_per_tick : ''} S.t ${r.game_s} maxE ${r.max_enemies} deaths(hits that would kill) ${r.deaths_absorbed}`);
    for (const a of r.actors) console.log(` actor ${a.i} ${a.k} lv ${a.lv} dmg ${a.dmg} weapons ${JSON.stringify(a.weapons)}`);
    if (r.error) console.log(`ERR at game t=${r.error.at_game_s}s${r.error.where ? ' (' + r.error.where + ')' : ''}\n${r.error.stack}`);
    if (r.ended_early) console.log(`FAIL 판이 일찍 끝남 t=${r.ended_early.at_game_s}s — ${r.ended_early.why}`);
    if (r.stuck) console.log(`FAIL 상태가 풀리지 않음 t=${r.stuck.at_game_s}s state=${r.stuck.state} — resume() 이 상태를 못 바꿈(이어하기 모듈 stale/상점 판정이 막고 있을 수 있음)`);
    if (r.time_mismatch) console.log(`FAIL 게임 시각이 요청과 다름 — S.t=${r.time_mismatch.game_s}s, 요청 ${r.time_mismatch.secs}s`);
    if (r.nonfinite) console.log(`FAIL 값이 유한하지 않음 t=${r.nonfinite.at_game_s}s — ${r.nonfinite.what}`);
    if (r.stub) console.log('stub:', JSON.stringify(r.stub));
    console.log(r.ok ? 'RESULT PASS' : 'RESULT FAIL');
  }
  if (o.out) fs.writeFileSync(o.out, JSON.stringify(r, null, 2) + '\n');
  if (o.json) console.log(JSON.stringify(r));
  if (r.error) return 1;
  return r.ok ? 0 : 4;
}

module.exports = { runCombo, pickKeys, stateHash, DEFAULT_COMBOS, HEAVY_COMBOS, PAD };
if (require.main === module) process.exit(main());
