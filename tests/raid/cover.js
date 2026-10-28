#!/usr/bin/env node
/* 레이드 0단계 — 무기 전종 사용 확인 (2026-10-08)

   4액터에게 무기 전부를 나눠 쥐여 주고(레벨 8) 보스 직전(S.t=290)부터 N초 돌려,
   각 무기가 실제로 피해 기록(dmgBy)을 남겼는지 본다(1차로 나눠 쥐고, 빠진 무기는 2차로 모두가 쥐고 다시).
   첫 스파이크의 확인 스크립트는 무기 이름 39개를 손으로 적어 두었다 — 지금은 WEAP 표에서 동적으로 구하고,
   옛 목록(KNOWN_39)과 달라진 점(추가/삭제)을 보고한다. 목록이 어긋나도 시험은 현재 WEAP 기준으로 한다.

   사용: node tests/raid/cover.js [--secs 240] [--from 290] [--evo] [--combo brj,jjg,mms,hrb] [--seed 1] [--src …] [--json] [--out FILE]
     --evo : 각성(S.ev)·마스터 단계(S.tier)까지 올린 상태로 돈다(각성 분기 경로)
   종료코드: 0 전종 사용 확인 · 1 예외 · 4 사용 안 된 무기 있음/판이 일찍 끝남 · 2 빌드 실패 · 3 로드 시험 실패 · 64 옵션 오류 · 66 입력 파일을 못 읽음
   (--world-pools x4|first 로 월드 풀 처리 방식을 고를 수 있다 — build_sim.js 설명 참고) */
'use strict';
const fs = require('fs');
const { ensureBuilt, buildErrorCode } = require('./build_sim.js');
const { loadSimFile } = require('./run_stub.js');
const { pickKeys } = require('./mp_run.js');

// 2026-10-08 첫 스파이크의 하드코딩 목록(39종). 지금 WEAP 과 비교해 달라진 점을 알리는 용도로만 남긴다.
const KNOWN_39 = 'bash bell breath can cart chain chick egg eom feed frost fryer fuse gacha heart hole jhin kbd lid meteor pan pcards ping potion quill ram rkt rod shrimp slime snack snipe spk stamp sushi tempo twin whop wifi'.split(' ');

/* 한 판을 돌려 무기별 피해 기록을 모은다. assign(i) = i 번 액터에게 줄 무기 키 목록. */
function pass(o, all, assign, label) {
  const win = loadSimFile(o.simMpPath, { seed: o.seed });
  const x = win.__p6x;
  x.initMP(o.combo);
  // 액터마다 S 에 끼워 넣은 뒤(use) 직접 채운다 — 저장은 use 가 전환할 때 해 준다
  x.ACT.forEach((a, i) => {
    x.use(i);
    x.S.w = {}; x.S.ev = {}; x.S.tier = {};
    for (const k of assign(i)) {
      x.S.w[k] = 8;
      if (o.evo) { x.S.ev[k] = 1; if (x.TIERS && x.TIERS[k]) x.S.tier[k] = 5; }
    }
  });
  x.use(0);
  x.S.t = o.from;   // 보스(5분) 직전부터
  const r = { label, ticks: 0, error: null, ended_early: null };
  const total = Math.round(o.secs * 30);
  const t0 = process.hrtime.bigint();
  for (let s = 0; s < total; s++) {
    const t = s / 30;
    x.ACT.forEach((a, i) => { a.keys = pickKeys('circle', t, i); });
    try { x.update(1 / 30); }
    catch (e) { r.error = { at_game_s: +(x.S.t).toFixed(1), message: String(e && e.message || e), stack: String(e && e.stack || e).split('\n').slice(0, 6).join('\n') }; break; }
    r.ticks++;
    if (x.ENDS > 0 || x.state === 'result') { r.ended_early = { at_game_s: +x.S.t.toFixed(1) }; break; }
    if (x.state !== 'play') x.resume();
  }
  r.ms_per_tick = r.ticks ? +(Number(process.hrtime.bigint() - t0) / 1e6 / r.ticks).toFixed(2) : null;
  r.game_s = +x.S.t.toFixed(1);
  r.complete = !r.error && !r.ended_early && r.ticks === total;
  const used = {}; x.ACT.forEach(a => { for (const k in (a.b.dmgBy || {})) used[k] = (used[k] || 0) + a.b.dmgBy[k]; });
  r.used = all.filter(k => k in used);
  return r;
}

/* 1차: 무기를 4명에게 나눠 준다. 2차: 1차에서 빠진 무기만 4명 모두에게 쥐여 다시 돈다.
   2차가 필요한 이유(2026-10-09 실측) — 따라다니는 소환물 풀(rangs·pets·lid 궤도 등)이 액터별로 나뉘지 않아,
   그 무기를 안 가진 액터의 차례가 소유자의 소환물을 꺼 버린다(예: S.ev.shrimp 가 아닌 액터가 궤도 부메랑을 끈다).
   솔로 사본(sim.js)에서는 같은 무기가 피해를 남긴다. 즉 1차 누락은 4액터 텍스트 패치의 한계일 수 있어, 모두가 같은 무기를 쥔 2차에서도 못 확인된 것만 실패로 본다. */
function runCover(o) {
  const probe = loadSimFile(o.simMpPath, { seed: o.seed });
  const table = Object.keys(probe.__p6x.WEAP);
  // 코드가 실제로 읽는 무기 키(S.w.<키>)와 WEAP 표를 맞춰 본다. 표에만 있거나 코드에만 있는 것은 보고하고, 코드에만 있는 것도 시험 대상에 넣는다.
  const refs = new Set(); for (const m of fs.readFileSync(o.simMpPath, 'utf8').matchAll(/\bS\.w\.([a-z][a-z0-9_]*)/g)) refs.add(m[1]);
  const codeOnly = [...refs].filter(k => !table.includes(k)), tableOnly = table.filter(k => !refs.has(k));
  const all = [...table, ...codeOnly];
  const added = all.filter(k => !KNOWN_39.includes(k)), removed = KNOWN_39.filter(k => !all.includes(k));
  const per = Math.ceil(all.length / o.combo.length);
  const p1 = pass(o, all, i => all.slice(i * per, (i + 1) * per), '1차(나눠 쥠)');
  const missing1 = all.filter(k => !p1.used.includes(k));
  let p2 = null, recovered = [];
  if (p1.complete && missing1.length) {
    p2 = pass(o, all, () => missing1, '2차(빠진 무기를 모두가 쥠)');
    recovered = missing1.filter(k => p2.used.includes(k));
  }
  const used = new Set([...p1.used, ...(p2 ? p2.used : [])]);
  const missing = all.filter(k => !used.has(k));
  const err = p1.error || (p2 && p2.error) || null;
  const early = p1.ended_early || (p2 && p2.ended_early) || null;
  return {
    evo: !!o.evo, combo: o.combo.join(','), secs: o.secs, from: o.from, weapons_now: all.length, known_39: KNOWN_39.length, added, removed, code_only: codeOnly, table_only: tableOnly,
    ticks: p1.ticks + (p2 ? p2.ticks : 0), ms_per_tick: p1.ms_per_tick, game_s: p1.game_s,
    error: err, ended_early: early, first_pass_missing: missing1, second_pass_recovered: recovered,
    used: all.filter(k => used.has(k)), missing,
    ok: !err && !early && p1.complete && (!p2 || p2.complete) && missing.length === 0,
  };
}

function parseArgs(argv) {
  const o = { secs: 240, from: 290, evo: false, combo: 'brj,jjg,mms,hrb', seed: undefined, src: null, buildDir: null, json: false, out: null, worldPools: 'x4' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], nx = () => argv[++i];
    if (a === '--secs') o.secs = Number(nx());
    else if (a === '--from') o.from = Number(nx());
    else if (a === '--evo') o.evo = true;
    else if (a === '--combo') o.combo = nx();
    else if (a === '--seed') o.seed = Number(nx()) | 0;
    else if (a === '--src') o.src = nx();
    else if (a === '--build-dir') o.buildDir = nx();
    else if (a === '--json') o.json = true;
    else if (a === '--out') o.out = nx();
    else if (a === '--world-pools') { o.worldPools = nx(); if (!['x4', 'first'].includes(o.worldPools)) { console.error('--world-pools 는 x4|first'); process.exit(64); } }
    else if (a === '-h' || a === '--help') o.help = true;
    else { console.error('알 수 없는 옵션: ' + a); process.exit(64); }
  }
  if (!(o.secs > 0) || !(o.from >= 0)) { console.error('--secs/--from 값이 올바르지 않습니다'); process.exit(64); }
  return o;
}

function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help) { console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0]); return 0; }
  let b;
  try { b = ensureBuilt(o.src, o.buildDir, { worldPools: o.worldPools }); } catch (e) { const c = buildErrorCode(e); if (c != null) return c; throw e; }
  const combo = o.combo.split(',').map(s => s.trim()).filter(Boolean);
  if (combo.length !== 4) { console.error('--combo 는 캐릭터 키 4개'); return 64; }
  const r = runCover({ ...o, combo, simMpPath: b.simMpPath });
  r.survivors_sha256 = b.manifest.survivors_sha256;
  if (!o.json) {
    console.log(`[cover] 무기 ${r.weapons_now}종(옛 목록 ${r.known_39}종) · ${r.secs}초(S.t ${r.from}부터)${r.evo ? ' · 각성/마스터' : ''}`);
    if (r.added.length || r.removed.length) console.log(`옛 목록과 다른 점 — 추가: ${r.added.join(',') || '없음'} · 삭제: ${r.removed.join(',') || '없음'}  (시험은 현재 WEAP 기준)`);
    if (r.code_only.length || r.table_only.length) console.log(`코드(S.w.<키>)와 WEAP 표가 다름 — 코드에만: ${r.code_only.join(',') || '없음'} · 표에만: ${r.table_only.join(',') || '없음'}`);
    else console.log(`코드의 S.w.<키> 참조 ${r.weapons_now}종 = WEAP 표 ${r.weapons_now}종 (일치)`);
    console.log(`ticks ${r.ticks} ms/tick ${r.ms_per_tick} S.t ${r.game_s}`);
    if (r.error) console.log(`ERR t=${r.error.at_game_s}s\n${r.error.stack}`);
    if (r.ended_early) console.log(`FAIL 판이 일찍 끝남 t=${r.ended_early.at_game_s}s`);
    console.log(`weapons with dmg recorded: ${r.used.length} / ${r.weapons_now}  missing: ${r.missing.join(',') || '없음'}`);
    if (r.first_pass_missing.length) console.log(`  └ 1차(나눠 쥠)에서 빠진 것: ${r.first_pass_missing.join(',')} → 2차(모두가 쥠)에서 확인됨: ${r.second_pass_recovered.join(',') || '없음'} — README 「한계」 참고`);
    console.log(r.ok ? 'RESULT PASS' : 'RESULT FAIL');
  } else console.log(JSON.stringify(r));
  if (o.out) fs.writeFileSync(o.out, JSON.stringify(r, null, 2) + '\n');
  if (r.error) return 1;
  return r.ok ? 0 : 4;
}

module.exports = { runCover, KNOWN_39 };
if (require.main === module) process.exit(main());
