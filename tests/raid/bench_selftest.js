#!/usr/bin/env node
/* 레이드 0단계 — 방 부하 측정기(bench_rooms.js) 자신의 시험 (2026-10-09)

   "측정기가 합격처럼 읽히는 거짓 출력을 내지 않는가 · 거친 입력과 종료에도 결과를 안 잃는가"를 본다.
   1) 판정 표(judgeG2): 합격 근거가 되는 조건을 하나라도 못 채우면 pass 는 true/false 가 아니라 "참고"
   2) 힙 상한: NODE_OPTIONS 의 --max-old-space-size 가 방별 상한을 덮어쓰면 알아채는가 · 상한이 적용되면 OOM 이 그 방만 죽이는가
   3) 입력 거절: 쓸 수 없는 --out(파일 아래·/proc) · 없는 --src · 터무니없는 --rooms/--secs  → 오래 걸리지 않고 한 줄 안내
   4) 종료: SIGINT/SIGTERM/SIGHUP → 중간 결과가 <out>.partial.json 에 남고 --out 은 안 만들어짐 · 전체 시간 제한 → 종료코드 5
   5) 결과 JSON: 보조 지표·slip_s·host 정보·상태 문자열
   사용: node tests/raid/bench_selftest.js        종료코드: 0 전부 통과 · 1 실패 있음
   ※ 공용 기계에서 시간에 민감한 시험은 한 번 다시 해 본다. 이 시험은 몇 분이 걸린다(짧은 측정을 여러 번 돈다). */
'use strict';
const fs = require('fs'), os = require('os'), path = require('path'), cp = require('child_process');
const { judgeG2, countCpuList, checkOutWritable } = require('./bench_rooms.js');
const { HEAVY_COMBOS } = require('./mp_run.js');

const BENCH = path.join(__dirname, 'bench_rooms.js');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'raid-benchtest-'));
let pass = 0, fail = 0;
const t = (name, ok, detail) => { if (ok) { pass++; console.log('ok   ' + name); } else { fail++; console.log('FAIL ' + name + (detail ? ' — ' + detail : '')); } };
const j = f => JSON.parse(fs.readFileSync(f, 'utf8'));
const cleanEnv = () => { const e = { ...process.env }; delete e.NODE_OPTIONS; return e; };

/* bench_rooms.js 를 돌려 {rc, out, err, ms} 를 돌려준다. opts.env, opts.timeout(ms), opts.onOut(text, child) 로 중간에 개입할 수 있다. */
function run(args, opts = {}) {
  return new Promise(resolve => {
    const t0 = Date.now();
    const child = cp.spawn(process.execPath, [BENCH, ...args], { env: opts.env || cleanEnv(), stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '', err = '';
    child.stdout.on('data', d => { out += d; if (opts.onOut) opts.onOut(out, child); });
    child.stderr.on('data', d => { err += d; });
    const killer = setTimeout(() => { err += '\n[selftest] 제한 시간 초과 — 강제 종료'; child.kill('SIGKILL'); }, opts.timeout || 120000);
    child.on('exit', (code, sig) => { clearTimeout(killer); resolve({ rc: code == null ? 'sig:' + sig : code, out, err, ms: Date.now() - t0 }); });
  });
}
const waitReady = (n) => { let sent = false; return (out, child, sig) => { if (!sent && (out.match(/준비\(/g) || []).length >= n) { sent = true; setTimeout(() => child.kill(sig), 700); } }; };

(async () => {
  // 1) 판정 표
  {
    const base = { rooms: 3, secs: 900, hz: 30, realtime: true, effCores: 1, heapCapEffective: true, loadMax: 0.5, badIds: [], interrupted: false, interruptedBy: null, tickP99max: 12, loopP99: 5 };
    const J = over => judgeG2({ ...base, ...over });
    t('판정: 조건을 다 채우고 한도 안 → true', J({}).pass === true && J({}).qualified === true);
    t('판정: 조건을 다 채우고 tick p99 초과 → false', J({ tickP99max: 26 }).pass === false);
    t('판정: 조건을 다 채우고 루프 지연 초과 → false', J({ loopP99: 11 }).pass === false);
    for (const [nm, over] of [['측정 4초', { secs: 4 }], ['측정 899초', { secs: 899 }], ['방 1개', { rooms: 1 }], ['방 5개', { rooms: 5 }], ['코어 4개(taskset 안 함)', { effCores: 4 }], ['힙 상한 무시됨', { heapCapEffective: false }],
      ['기계가 붐빔(load 3)', { loadMax: 3 }], ['60Hz', { hz: 60 }]]) {
      const r = J(over);
      t(`판정: ${nm} + 한도 안 → "참고" (true 가 아님)`, r.pass === '참고' && r.qualified === false && r.unmet.length >= 1 && r.withinLimits === true, JSON.stringify(r.pass));
      t(`판정: ${nm} + 한도 밖 → "참고" (false 도 아님)`, J({ ...over, tickP99max: 80, loopP99: 50 }).pass === '참고');
    }
    t('판정: 방 8개 → "기록만"', J({ rooms: 8 }).pass === '기록만');
    t('판정: --fast → "기록만"', J({ realtime: false }).pass === '기록만');
    t('판정: 방이 죽었으면 조건과 무관하게 false', J({ badIds: ['1:oom'] }).pass === false && J({ badIds: ['1:oom'], secs: 3 }).pass === false);
    t('판정: 중단(SIGTERM)은 false · 사유가 note 에', J({ interrupted: true, interruptedBy: 'SIGTERM' }).pass === false && /SIGTERM/.test(J({ interrupted: true, interruptedBy: 'SIGTERM' }).note));
    t('판정: 측정값이 없으면(tickP99max=null) false', J({ tickP99max: null }).pass === false);
    t('판정: 참고일 때 note 에 사유가 들어간다', /900초/.test(J({ secs: 4 }).note) && /합격도 불합격도 아니다/.test(J({ secs: 4 }).note));
    t('CPU 목록 세기: "0"=1 · "0-3"=4 · "0-3,5"=5 · 엉뚱한 값=null', countCpuList('0') === 1 && countCpuList('0-3') === 4 && countCpuList('0-3,5') === 5 && countCpuList('x') === null && countCpuList(null) === null);
  }

  // 3) 입력 거절 — 빠르고 한 줄 안내여야 한다(측정을 시작하지 않는다)
  {
    const f = path.join(TMP, 'afile'); fs.writeFileSync(f, 'x');
    let r = await run(['--rooms', '1', '--secs', '1', '--out', path.join(f, 'x.json')], { timeout: 20000 });
    t('--out 이 파일 아래 → 측정 전에 64 로 거절(스택 없음)', r.rc === 64 && /--out 을 쓸 수 없어/.test(r.err) && !/\n\s+at /.test(r.err) && r.ms < 8000, `rc=${r.rc} ${r.ms}ms ${r.err.slice(0, 160)}`);
    r = await run(['--rooms', '1', '--secs', '1', '--out', '/proc/nope/x.json'], { timeout: 20000 });
    t('--out /proc/… → 멈추지 않고 즉시 64 (예전엔 mkdir 이 100초+ 돌았다)', r.rc === 64 && r.ms < 8000, `rc=${r.rc} ${r.ms}ms ${r.err.slice(0, 160)}`);
    t('checkOutWritable: 정상 경로는 null, 새 하위 폴더도 null', checkOutWritable(path.join(TMP, 'ok', 'deep', 'x.json')) === null);
    r = await run(['--rooms', '1', '--secs', '1', '--src', path.join(TMP, 'nope.html')], { timeout: 20000 });
    t('--src 없는 파일 → 66 + 한 줄 안내(스택 없음)', r.rc === 66 && /읽지 못했습니다/.test(r.err) && !/\n\s+at /.test(r.err), `rc=${r.rc} ${r.err.slice(0, 160)}`);
    r = await run(['--rooms', '1000', '--secs', '2', '--fast'], { timeout: 20000 });
    t('--rooms 1000 → 64 (상한 32)', r.rc === 64 && /너무 큽니다/.test(r.err) && r.ms < 8000, `rc=${r.rc} ${r.err.slice(0, 100)}`);
    r = await run(['--rooms', '1', '--secs', '1e9', '--fast'], { timeout: 20000 });
    t('--secs 1e9 → 64 (치명 오류가 아니라 거절)', r.rc === 64 && /너무 큽니다/.test(r.err) && !/Array buffer/.test(r.err), `rc=${r.rc} ${r.err.slice(0, 100)}`);
    r = await run(['--rooms', '1', '--secs', '1', '--heap-mb', '2'], { timeout: 20000 });
    t('--heap-mb 2 → 64', r.rc === 64, `rc=${r.rc}`);
  }

  // 2) 힙 상한
  {
    const ev = { ...process.env, NODE_OPTIONS: '--max-old-space-size=8192' };
    const o1 = path.join(TMP, 'heap_ignored.json');
    let r = await run(['--rooms', '3', '--secs', '3', '--fast', '--heap-mb', '64', '--out', o1], { env: ev, timeout: 90000 });
    const J1 = fs.existsSync(o1) ? j(o1) : null;
    t('NODE_OPTIONS 가 상한을 덮어쓰면: stderr 경고 · input.heap_cap_effective=false · host.node_options 기록', r.rc === 0 && /힙 상한 64MB 가 적용되지 않았습니다/.test(r.err) && J1 && J1.input.heap_cap_effective === false && /max-old-space-size/.test(J1.host.node_options || ''), `rc=${r.rc} ${r.err.slice(0, 200)}`);
    t('  └ 방이 보고한 힙 한도가 상한+128MB 보다 크다(상한이 무시된 증거)', J1 && J1.input.heap_limit_reported_mb > 64 + 128, J1 && String(J1.input.heap_limit_reported_mb));
    r = await run(['--rooms', '3', '--secs', '3', '--fast', '--fault', 'oom:1:1'], { env: ev, timeout: 30000 });
    t('NODE_OPTIONS 가 상한을 덮어쓴 채 --fault oom → 기계 메모리를 먹지 않게 64 로 거절', r.rc === 64 && /env -u NODE_OPTIONS/.test(r.err), `rc=${r.rc} ${r.err.slice(0, 160)}`);

    const o2 = path.join(TMP, 'heap_ok.json');
    r = await run(['--rooms', '3', '--secs', '3', '--fast', '--heap-mb', '64', '--out', o2], { timeout: 90000 });
    const J2 = fs.existsSync(o2) ? j(o2) : null;
    t('NODE_OPTIONS 없음: heap_cap_effective=true · 보고 한도 ≈ 상한+48 · 경고 없음', r.rc === 0 && J2 && J2.input.heap_cap_effective === true && J2.input.heap_limit_reported_mb <= 64 + 128 && !/적용되지 않았습니다/.test(r.err), `rc=${r.rc} ${J2 && J2.input.heap_limit_reported_mb}`);
    const o3 = path.join(TMP, 'oom.json');
    r = await run(['--rooms', '3', '--secs', '6', '--realtime', '--heap-mb', '64', '--fault', 'oom:1:2', '--out', o3], { timeout: 90000 });
    const J3 = fs.existsSync(o3) ? j(o3) : null;
    const st = J3 ? J3.rooms.map(x => x.status).join(',') : '?';
    t('상한이 적용되면 oom 은 그 방만 죽는다: 방1=oom, 방0·2=ok, 종료코드 1', r.rc === 1 && st === 'ok,oom,ok', `rc=${r.rc} statuses=${st} ${r.err.slice(0, 160)}`);
    t('  └ oom 방의 heap_limit_mb 가 상한 근처(≤ 64+128)로 기록됨', J3 && J3.rooms[1].heap_limit_mb != null && J3.rooms[1].heap_limit_mb <= 64 + 128, J3 && String(J3.rooms[1].heap_limit_mb));
  }

  // 결과 JSON 의 모양(짧은 realtime)
  {
    const o = path.join(TMP, 'shape.json');
    const r = await run(['--rooms', '3', '--secs', '5', '--realtime', '--combos', 'heavy', '--out', o], { timeout: 90000 });
    const J = fs.existsSync(o) ? j(o) : null;
    const g = J && J.gates.G2;
    t('realtime 5초 3방: 종료 0 · pass="참고" (900초 미만) · qualified=false · 사유 목록', r.rc === 0 && g && g.pass === '참고' && g.qualified === false && g.qualified_unmet.some(s => /900초/.test(s)), `rc=${r.rc} ${g && g.pass}`);
    t('  └ 한 줄 요약에 "참고(합격 판정 아님)" 가 찍힘 · "→ true" 는 없음', /참고\(합격 판정 아님\)/.test(r.out) && !/→ true/.test(r.out));
    t('  └ gates.G2 에 within_limits · aux(late_ratio·over25_ratio·deadline_p99·slip) 가 있음', g && typeof g.within_limits === 'boolean' && g.aux && 'late_ratio_max' in g.aux && 'tick_over_25ms_ratio_max' in g.aux && g.aux.deadline_p99_ms_max != null && g.aux.slip_s_max != null, JSON.stringify(g && g.aux));
    t('  └ 방마다 deadline_ms(마감 대비 완료 지연)·slip_s 가 있음', J && J.rooms.every(x => x.deadline_ms && x.deadline_ms.p99 != null && x.slip_s != null));
    t('  └ host 에 node_options · nice · cgroup · cores_effective 가 기록됨', J && 'node_options' in J.host && 'nice' in J.host && J.host.cgroup && 'cpu_max' in J.host.cgroup && J.host.cores_effective >= 1);
    t('  └ --combos heavy → HEAVY_COMBOS 가 방에 들어감', J && J.input.combos.join(';') === HEAVY_COMBOS.join(';'), J && J.input.combos.join(';'));
    const of = path.join(TMP, 'fast.json');
    await run(['--rooms', '3', '--secs', '3', '--fast', '--out', of], { timeout: 90000 });
    t('--fast 는 pass="기록만"', fs.existsSync(of) && j(of).gates.G2.pass === '기록만');
  }

  // 방 상태 문자열(README 와 맞는가)
  {
    const o = path.join(TMP, 'throw.json');
    const r = await run(['--rooms', '3', '--secs', '4', '--realtime', '--fault', 'throw:1:1', '--out', o], { timeout: 90000 });
    const J = fs.existsSync(o) ? j(o) : null;
    t("--fault throw: 방1 status='error' · 종료코드 1 · 통계(tick_ms)는 채워져 있다(README: error 는 null 이 아님)", r.rc === 1 && J && J.rooms[1].status === 'error' && J.rooms[1].tick_ms && J.rooms[1].tick_ms.n > 0 && J.rooms[1].first_error, `rc=${r.rc} ${J && J.rooms[1].status}`);
    const o2 = path.join(TMP, 'hang.json');
    const r2 = await run(['--rooms', '3', '--secs', '6', '--realtime', '--fault', 'hang:1:2', '--out', o2], { timeout: 90000 });
    const J2 = fs.existsSync(o2) ? j(o2) : null;
    t("--fault hang: 방1 status='killed_hb', tick_ms=null · 방0·2 ok · 종료코드 1", r2.rc === 1 && J2 && J2.rooms.map(x => x.status).join(',') === 'ok,killed_hb,ok' && J2.rooms[1].tick_ms === null, `rc=${r2.rc} ${J2 && J2.rooms.map(x => x.status)}`);
  }

  // 소스를 일부러 망가뜨려 측정기의 눈을 시험한다(--src 로 고친 사본을 준다)
  {
    const html = fs.readFileSync(path.join(__dirname, '..', '..', 'survivors.html'), 'utf8');
    const inject = (from, to) => { if (html.split(from).length !== 2) throw new Error('주입 앵커가 유일하지 않음'); return html.replace(from, () => to); };
    const WPN = 'weapons(dt);charTick(dt);relTick(dt);';
    // (a) 판이 일찍 끝나는 사본 → 방 status='ended_early'
    const f1 = path.join(TMP, 'end.html'); fs.writeFileSync(f1, inject(WPN, WPN + 'if(S.t>1)endRun(false);'));
    const o1 = path.join(TMP, 'end.json');
    let r = await run(['--rooms', '1', '--secs', '5', '--fast', '--src', f1, '--build-dir', path.join(TMP, 'b_end'), '--out', o1], { timeout: 90000 });
    t("판이 일찍 끝나는 사본: 방 status='ended_early' · 종료코드 1 (patched 꼬리가 state 를 되돌려도 ENDS 로 잡는다)", r.rc === 1 && fs.existsSync(o1) && j(o1).rooms[0].status === 'ended_early', `rc=${r.rc} ${fs.existsSync(o1) && j(o1).rooms[0].status}`);
    // (b) 100틱마다 40ms 멈추는 사본(1% 미만) → tick p99 는 통과해도 보조 지표(25ms 초과 비율)가 잡는다
    const f2 = path.join(TMP, 'stall.html'); fs.writeFileSync(f2, inject(WPN, WPN + 'if((globalThis.__c=(globalThis.__c||0)+1)%100===0){const e=Date.now();while(Date.now()-e<40);}'));
    const o2 = path.join(TMP, 'stall.json');
    r = await run(['--rooms', '1', '--secs', '14', '--realtime', '--src', f2, '--build-dir', path.join(TMP, 'b_stall'), '--out', o2], { timeout: 90000 });
    const J = fs.existsSync(o2) ? j(o2) : null;
    const rm = J && J.rooms[0], g = J && J.gates.G2;
    t('0.7% 틱이 40ms 멈추는 사본: tick_over_25ms ≥ 3 · late_ticks ≥ 3 · 보조 지표 over25 비율이 제안 한도(0.1%)를 넘어 over25_within_suggested=false',
      rm && rm.tick_over_25ms >= 3 && rm.late_ticks >= 3 && g.aux.tick_over_25ms_ratio_max > 0.001 && g.aux.over25_within_suggested === false, JSON.stringify(rm && [rm.tick_over_25ms, rm.late_ticks, g && g.aux]));
    t('  └ 같은 측정에서 deadline_ms.max ≥ 40 (시작 지연+틱 합산 지표가 정지를 본다)', rm && rm.deadline_ms.max >= 40, rm && String(rm.deadline_ms.max));
  }

  // 4) 종료 신호와 전체 시간 제한
  for (const [sig, code] of [['SIGINT', 130], ['SIGTERM', 143], ['SIGHUP', 129]]) {
    const o = path.join(TMP, 'sig_' + sig + '.json'), part = path.join(TMP, 'sig_' + sig + '.partial.json');
    const r = await run(['--rooms', '3', '--secs', '60', '--realtime', '--out', o], { timeout: 60000, onOut: (() => { const w = waitReady(3); return (out, child) => w(out, child, sig); })() });
    const P = fs.existsSync(part) ? j(part) : null;
    t(`${sig}: 종료코드 ${code} · 중간 결과가 .partial.json 에 · --out 은 만들어지지 않음 · interrupted_by=${sig} · pass=false`,
      r.rc === code && P && P.interrupted === true && P.interrupted_by === sig && P.gates.G2.pass === false && !fs.existsSync(o), `rc=${r.rc} partial=${!!P} out=${fs.existsSync(o)} ${r.err.slice(0, 120)}`);
    t(`  └ ${sig}: 부분 결과에도 방 통계(ticks>0)가 있다`, P && P.rooms.every(x => x.ticks > 0 && x.tick_ms), P && JSON.stringify(P.rooms.map(x => x.ticks)));
  }
  {
    const o = path.join(TMP, 'wall.json'), part = path.join(TMP, 'wall.partial.json');
    const r = await run(['--rooms', '3', '--secs', '60', '--realtime', '--wall-limit-s', '3', '--out', o], { timeout: 60000 });
    const P = fs.existsSync(part) ? j(part) : null;
    t('--wall-limit-s 3: 종료코드 5(SIGINT 의 130 이 아님) · interrupted_by=wall-limit · 부분 결과 저장', r.rc === 5 && P && P.interrupted_by === 'wall-limit' && !fs.existsSync(o), `rc=${r.rc} ${P && P.interrupted_by}`);
  }

  // 결과 저장 실패 — 요약을 먼저 찍고 JSON 을 stdout 에 남긴다
  {
    // 측정이 끝나는 순간 --out 의 자리를 폴더로 바꿔 놓아 renameSync 가 실패하게 한다
    const o = path.join(TMP, 'savefail.json');
    const r = await run(['--rooms', '1', '--secs', '4', '--realtime', '--out', o], {
      timeout: 60000,
      onOut: (out) => { if (!fs.existsSync(o) && /준비\(/.test(out)) try { fs.mkdirSync(o); fs.writeFileSync(path.join(o, 'keep'), 'x'); } catch (e) { /* 이미 만듦 */ } },
    });
    const jsonLine = r.out.split('\n').find(l => l.startsWith('{"v":1,"kind":"rooms-bench"'));
    t('저장 실패: 요약이 먼저 찍히고 · 사유가 stderr 에 · JSON 전체가 stdout 에 · 종료코드 6', /\[bench\] 결과/.test(r.out) && /결과 파일을 쓰지 못했습니다/.test(r.err) && !!jsonLine && r.rc === 6, `rc=${r.rc} ${r.err.slice(0, 200)}`);
  }

  fs.rmSync(TMP, { recursive: true, force: true });
  console.log(`\n${fail ? 'FAIL' : 'PASS'} — 통과 ${pass} · 실패 ${fail}`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); try { fs.rmSync(TMP, { recursive: true, force: true }); } catch (x) { /* 무시 */ } process.exit(1); });
