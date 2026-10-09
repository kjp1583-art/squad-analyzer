#!/usr/bin/env node
/* 레이드 0단계 — 이 도구들 자신의 시험 (2026-10-08)

   "시험 도구가 조용히 틀리지 않는가"를 본다. 약점을 일부러 넣어 보고 도구가 잡는지 확인한다.
   1) 앵커마다 「없애기」「겹치기」 → build_sim 이 그 앵커 이름을 대며 실패하는가
   2) 패치가 버리는 연결부에 새 문장을 끼우면 → 실패하는가
   3) 퍼센타일 계산이 정확한가(nearest-rank, 알려진 답 + 무작위 대조)
   4) 스텁: 저장소(length/key)·이벤트 등록·fetch 거절·시드 결정성
   5) ESLint 게이트가 4액터 패치 안의 미정의 이름(예: 패치로 사라진 지역 변수)을 실제로 잡는가
   6) 이벤트 루프 지연 측정이 실제 막힘을 보는가
   7) (2026-10-09 보완) 연결부 같은 줄 구멍 · 판 종료(endRun) 검출 · 낡은 사본 재사용 · 지연 생성 S 필드 · 월드 풀 처리 방식 · 게임 시각 대조
   사용: node tests/raid/sim_selftest.js [--no-lint]      종료코드: 0 전부 통과 · 1 실패 있음 */
'use strict';
const fs = require('fs'), path = require('path'), os = require('os'), cp = require('child_process');
const B = require('./build_sim.js');
const { summarize, pct } = require('./bench_stats.js');
const { loadSimCode, makeWindow } = require('./run_stub.js');
const { stateHash, runCombo } = require('./mp_run.js');

const html = fs.readFileSync(path.join(B.REPO, 'survivors.html'), 'utf8');
let pass = 0, fail = 0;
const t = (name, ok, detail) => { if (ok) { pass++; console.log('ok   ' + name); } else { fail++; console.log('FAIL ' + name + (detail ? ' — ' + detail : '')); } };
const throwsAnchor = (h) => { try { B.buildFromHtml(h, 'x'); return null; } catch (e) { return e instanceof B.AnchorErr ? e.message : 'other:' + e.message; } };

// 메인 블록 안에서만 바꾼다(다른 <script> 블록의 같은 글자를 건드리지 않게)
const { main } = B.extractMain(html);
const swapMain = (fn) => html.replace(main, () => fn(main));
// 구간·치환 앵커는 update() 안에서 찾는 것이므로, 같은 글자가 더 앞(그리기 코드 등)에 있어도 update() 안의 것을 바꾼다
const UPD = main.indexOf('function update(dt){');
const WHOLE = new Set(B.ANCHOR_STRINGS.slice(-4));   // update·endRun·fire·die 는 파일 전체에서 1번
const mutate = (a, repl) => swapMain(m => { const from = WHOLE.has(a) ? 0 : UPD; const i = m.indexOf(a, from); return m.slice(0, i) + repl + m.slice(i + a.length); });

// 0) 원본은 빌드된다
t('원본 survivors.html 빌드', throwsAnchor(html) === null);

// 1) 앵커마다 없애기/겹치기
{
  const lines = B.ANCHOR_STRINGS;
  let okDel = 0, okDup = 0;
  const bad = [];
  for (const a of lines) {
    // 없애기: 첫 번째 나오는 곳을 망가뜨린다(앵커가 한 곳뿐이므로 곧 「0번」이 된다)
    const hDel = mutate(a, a.slice(0, 1) + '§' + a.slice(1));
    const mDel = throwsAnchor(hDel);
    const shown = a.length > 90 ? a.slice(0, 90) : a;
    if (mDel && mDel.startsWith('앵커') && mDel.includes(JSON.stringify(shown).slice(1, -1).slice(0, 40))) okDel++; else bad.push('없애기 ' + JSON.stringify(a.slice(0, 40)) + ' → ' + String(mDel).slice(0, 80));
    // 겹치기: 바로 뒤에 한 번 더 붙인다(2번이 된다)
    const hDup = mutate(a, a + a);
    const mDup = throwsAnchor(hDup);
    if (mDup && mDup.startsWith('앵커')) okDup++; else bad.push('겹치기 ' + JSON.stringify(a.slice(0, 40)) + ' → ' + String(mDup).slice(0, 80));
  }
  t(`앵커 ${lines.length}개 없애기 → 이름을 대며 실패`, okDel === lines.length, bad.filter(s => s.startsWith('없애기')).join(' | '));
  t(`앵커 ${lines.length}개 겹치기(유일성) → 실패`, okDup === lines.length, bad.filter(s => s.startsWith('겹치기')).join(' | '));
}
// 1b) 훅 앵커
t('훅 앵커(window.__p6=) 없음 → 실패', !!throwsAnchor(swapMain(m => m.replace('window.__p6=', 'window.__p7='))));
t('메인 블록 못 찾음 → 실패', !!throwsAnchor('<html><script>var a=1;</script></html>'));

// 2) 버려지는 연결부에 새 문장이 끼면 실패
{
  const h = swapMain(m => m.replace("waveTick(dt);if(state!=='play')return;", () => "waveTick(dt);if(state!=='play')return;newThing(dt);"));
  const msg = throwsAnchor(h);
  t('waveTick~weapons 사이에 새 문장 → 실패(조용히 지워지지 않음)', !!msg && msg.includes('버려지는 연결부'), String(msg).slice(0, 120));
  const h2 = mutate('if(beamTick(dt))return;', 'if(beamTick(dt))return;newBeam(dt);');
  const msg2 = throwsAnchor(h2);
  t('beamTick 줄 뒤에 새 문장 → 실패', !!msg2 && msg2.includes('버려지는 연결부'), String(msg2).slice(0, 120));
  // (2026-10-09) update() 머리 줄의 EX.tick(dt); 뒤 같은 줄에 새 문장을 붙이면 조용히 사라지던 구멍
  const h4 = swapMain(m => m.replace('S.t+=dt;const p=S.p;EX.tick(dt);', () => 'S.t+=dt;const p=S.p;EX.tick(dt);NEWHEAD(dt);'));
  const msg4 = throwsAnchor(h4);
  t('update() 머리 줄 EX.tick(dt); 뒤 같은 줄에 새 문장 → 실패(구멍 막음)', !!msg4 && msg4.includes('버려지는 연결부'), String(msg4).slice(0, 120));
  const h5 = swapMain(m => m.replace('S.t+=dt;const p=S.p;EX.tick(dt);', () => 'S.t+=dt;const p=S.p;EX.tick(dt);   /* 블록 주석 뒤 */ NEWHEAD(dt);'));
  t('같은 줄 블록 주석 뒤 새 문장 → 실패', !!throwsAnchor(h5));
  const h6 = swapMain(m => m.replace('S.t+=dt;const p=S.p;EX.tick(dt);', () => 'S.t+=dt;const p=S.p;EX.tick(dt);   // 줄 끝 주석은 허용'));
  t('같은 줄 「//」 줄 끝 주석은 여전히 허용(원본에 있는 모양)', throwsAnchor(h6) === null);
  const h3 = mutate('function update(dt){', 'function update(dt){newFirst(dt);');
  const msg3 = throwsAnchor(h3);
  t('update() 맨 앞에 새 문장 → 실패', !!msg3 && msg3.includes('버려지는 연결부'), String(msg3).slice(0, 120));
}

// 3) 퍼센타일
{
  const a = Float64Array.from({ length: 1000 }, (_, i) => i + 1).sort(() => 0);   // 1..1000
  const s = summarize(a);
  t('percentile 1..1000: p50=500 p95=950 p99=990 p99.9=999 max=1000', s.p50 === 500 && s.p95 === 950 && s.p99 === 990 && s.p999 === 999 && s.max === 1000, JSON.stringify(s));
  t('percentile 소표본 [1..5]: p50=3 p99=5', pct([1, 2, 3, 4, 5], 50) === 3 && pct([1, 2, 3, 4, 5], 99) === 5);
  t('percentile 빈 배열 → null', summarize([], 0).p99 === null);
  // 무작위 대조: 단순 정렬 구현과 같은지
  let ok = true;
  for (let trial = 0; trial < 20; trial++) {
    const n = 1 + Math.floor(Math.random() * 30000);
    const arr = Float64Array.from({ length: n }, () => Math.random() * 50);
    const sorted = Array.from(arr).sort((x, y) => x - y);
    const naive = p => sorted[Math.max(0, Math.ceil(p / 100 * n) - 1)];
    const r = summarize(arr);
    const near = (x, y) => Math.abs(x - y) < 0.0006;
    if (!(near(r.p50, naive(50)) && near(r.p95, naive(95)) && near(r.p99, naive(99)) && near(r.p999, naive(99.9)) && near(r.max, sorted[n - 1]))) ok = false;
  }
  t('percentile 무작위 20회 단순 정렬 구현과 일치', ok);
  const big = new Float64Array(27000).fill(1); big[26999] = 400;   // 한 틱만 400ms → p99.9 는 영향 없고 max 만 400
  const sb = summarize(big);
  t('이상치 1/27000: p99.9=1, max=400 (히스토그램 근사가 아닌 정확한 값)', sb.p999 === 1 && sb.max === 400, JSON.stringify(sb));
}

// 4) 스텁
{
  const { win } = makeWindow();
  const ls = win.localStorage;
  ls.setItem('a', '1'); ls.setItem('b', '2');
  t('스텁 localStorage length/key', ls.length === 2 && ls.key(0) === 'a' && ls.key(1) === 'b' && ls.key(2) === null);
  ls.removeItem('a'); t('스텁 localStorage removeItem', ls.length === 1 && ls.getItem('a') === null);
  const built = B.buildFromHtml(html, 'survivors.html');
  const w = loadSimCode(built.sim);
  const evs = w.__stub.listeners.map(l => l.type);
  t('스텁: 이어하기 모듈의 visibilitychange/pagehide 등록이 기록됨', evs.includes('visibilitychange') && evs.includes('pagehide'), evs.join(','));
  let rej = false; w.fetch('x').catch(() => { rej = true; });
  const h1 = (() => { const x = loadSimCode(built.simMp, { seed: 5 }).__p6x; x.initMP(['brj', 'jjg', 'mms', 'hrb']); for (let i = 0; i < 600; i++) { x.ACT.forEach(a => { a.keys = { KeyD: true }; }); x.update(1 / 30); if (x.state !== 'play') x.resume(); } return stateHash(x); })();
  const h2 = (() => { const x = loadSimCode(built.simMp, { seed: 5 }).__p6x; x.initMP(['brj', 'jjg', 'mms', 'hrb']); for (let i = 0; i < 600; i++) { x.ACT.forEach(a => { a.keys = { KeyD: true }; }); x.update(1 / 30); if (x.state !== 'play') x.resume(); } return stateHash(x); })();
  const h3 = (() => { const x = loadSimCode(built.simMp, { seed: 6 }).__p6x; x.initMP(['brj', 'jjg', 'mms', 'hrb']); for (let i = 0; i < 600; i++) { x.ACT.forEach(a => { a.keys = { KeyD: true }; }); x.update(1 / 30); if (x.state !== 'play') x.resume(); } return stateHash(x); })();
  t('같은 시드 20초 → 같은 해시, 다른 시드 → 다른 해시', h1 === h2 && h1 !== h3, `${h1} ${h2} ${h3}`);
  t('이어하기 모듈의 저장소 쓰기 검사(probe)가 흔적을 남기지 않음', w.localStorage.getItem('p6_resume_probe') === null);
  Promise.resolve().then(() => new Promise(r => setImmediate(r))).then(() => t('스텁 fetch 거절이 실제로 일어남', rej));
}

// 5) 린트 게이트가 패치 안의 미정의 이름을 잡는가
const main5 = () => {
  if (process.argv.includes('--no-lint')) return;
  fs.mkdirSync(path.join(__dirname, '.build'), { recursive: true });
  const eslint = (() => { try { return cp.execSync('command -v eslint', { encoding: 'utf8' }).trim(); } catch (e) { return null; } })();
  if (!eslint) { console.log('skip 린트 시험 — eslint 없음'); return; }
  const tmp = fs.mkdtempSync(path.join(__dirname, '.build', 'lint-'));
  const built = B.buildFromHtml(html, 'survivors.html');
  const run = (code) => {
    const f = path.join(tmp, 'x.js'); fs.writeFileSync(f, code);   // (설정 파일의 기준 폴더 안에 두어야 린트 대상이 된다)
    const r = cp.spawnSync(eslint, ['--no-config-lookup', '-c', path.join(__dirname, 'eslint.sim.config.js'), '-f', 'json', f], { encoding: 'utf8' });
    try { return JSON.parse(r.stdout)[0].messages.filter(m => m.ruleId === 'no-undef').map(m => m.message.split("'")[1]); } catch (e) { return ['<린트 출력 이상: ' + (r.stderr || r.stdout).slice(0, 100) + '>']; }
  };
  const base = run(built.simMp);
  t('린트: 원본 4액터 패치 사본은 DOMMatrix 외에 새 항목 없음', base.every(n => n === 'DOMMatrix') && base.includes('DOMMatrix'), base.join(','));
  // (a) 지역 변수 p 를 안 만들어 주는 패치 실수(설계서 §4.0 에 적힌 612초 ReferenceError 류)
  const noP = built.simMp.split('use(ai);const p=S.p;').join('use(ai);');
  const r1 = run(noP);
  t('린트: 액터 루프에서 const p=S.p 를 빼면 p 가 no-undef 로 잡힘', r1.includes('p'), r1.join(','));
  // (b) 패치가 만든 이름의 오타
  const typo = built.simMp.replace('ACT[s.own|0].b.p.x', 'ACTT[s.own|0].b.p.x');
  const r2 = run(typo);
  t('린트: 패치 안의 이름 오타(ACTT)가 잡힘', r2.includes('ACTT'), r2.join(','));
  fs.rmSync(tmp, { recursive: true, force: true });
};

// 6) 이벤트 루프 지연 측정이 실제 막힘을 보는가
function eldTest() {
  return new Promise(res => {
    const { monitorEventLoopDelay } = require('perf_hooks');
    const h = monitorEventLoopDelay({ resolution: 10 }); h.enable();
    setTimeout(() => { const e = Date.now(); while (Date.now() - e < 300); }, 200);   // 타이머 안에서 300ms 막기
    setTimeout(() => {
      h.disable();
      const maxDelay = h.max / 1e6 - 10;
      t('이벤트 루프 지연: 300ms 막힘이 max 로 보임(≥ 250ms)', maxDelay >= 250, 'max−해상도 = ' + maxDelay.toFixed(1) + 'ms');
      res();
    }, 900);
  });
}


// 7) 2026-10-09 보완 — 검증에서 나온 지적마다 재현 → 수정 → 회귀 시험
function section7() {
  const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'raid-selftest-'));
  const write = (name, text) => { const f = path.join(TMP, name); fs.writeFileSync(f, text); return f; };
  try {
    // 7a) 판 종료(endRun) 검출 — 패치된 꼬리가 state 를 'play' 로 되돌려도(되돌리지 않게 고쳤고, 되돌려도) ENDS 가 센다
    {
      const inj = swapMain(m => m.replace('weapons(dt);charTick(dt);relTick(dt);', () => 'weapons(dt);charTick(dt);relTick(dt);if(S.t>1)endRun(false);'));
      const built = B.buildFromHtml(inj, 'inj');
      const f = write('end_sim_mp.js', built.simMp);
      const r = runCombo({ combo: ['brj', 'jjg', 'mms', 'hrb'], secs: 5, hz: 30, seed: 1, move: 'circle', simMpPath: f });
      t('endRun 주입: mp_run 이 「판이 일찍 끝남」으로 잡는다(ended_early, ok=false)', !!r.ended_early && r.ok === false, JSON.stringify(r.ended_early));
      const x = loadSimCode(built.simMp, { seed: 1 }).__p6x; x.initMP(['brj', 'jjg', 'mms', 'hrb']);
      for (let i = 0; i < 60 && x.state === 'play'; i++) x.update(1 / 30);
      t('endRun 주입: update() 가 끝난 뒤 state 가 result 로 남음(꼬리가 play 로 덮어쓰지 않음) · ENDS ≥ 1', x.state === 'result' && x.ENDS >= 1, `state=${x.state} ENDS=${x.ENDS}`);
      // 원본은 900초 안에 endRun 이 안 불린다(여기서는 20초)
      const ok = runCombo({ combo: ['brj', 'jjg', 'mms', 'hrb'], secs: 20, hz: 30, seed: 1, move: 'circle', simMpPath: write('ok_sim_mp.js', B.buildFromHtml(html, 'x').simMp) });
      t('원본: 20초 통과(ENDS 오검출 없음)', ok.ok === true, JSON.stringify(ok.ended_early || ok.error));
    }
    // 7b) 게임 시각 대조: 틱 수가 맞아도 S.t 가 다르면 실패
    {
      const mp = B.buildFromHtml(html, 'x').simMp;
      const bad = mp.replace('S.t+=dt;EX.tick(dt);', 'S.t+=dt*0.5;EX.tick(dt);');
      t('(시험 준비) 시각 어긋남 주입이 적용됨', bad !== mp);
      const r = runCombo({ combo: ['brj', 'jjg', 'mms', 'hrb'], secs: 10, hz: 30, seed: 1, move: 'circle', simMpPath: write('tm_sim_mp.js', bad) });
      t('S.t 가 요청한 초와 1초 이상 다르면 time_mismatch · ok=false', !!r.time_mismatch && r.ok === false, JSON.stringify({ g: r.game_s, tm: r.time_mismatch, ok: r.ok }));
    }
    // 7c) 낡은 사본 재사용 방지: build_sim.js 를 고치면 ensureBuilt 가 다시 만든다
    {
      const dir = path.join(TMP, 'raid'); fs.mkdirSync(dir);
      for (const f of fs.readdirSync(__dirname)) if (/\.(js|py)$/.test(f)) fs.copyFileSync(path.join(__dirname, f), path.join(dir, f));
      const srcCopy = write('surv.html', html), bdir = path.join(TMP, 'b');
      const run = (args) => cp.spawnSync(process.execPath, [path.join(dir, 'mp_run.js'), '--src', srcCopy, '--build-dir', bdir, '--secs', '2', '--json', ...args], { encoding: 'utf8' });
      const r1 = run([]);
      const before = fs.readFileSync(path.join(bdir, 'sim_mp.js'), 'utf8');
      t('(시험 준비) 첫 빌드 성공 · die() 의 무적 상수 1.5 가 들어 있음', r1.status === 0 && before.includes('p.inv=Math.max(p.inv,1.5)'), `rc=${r1.status} ${r1.stderr.slice(0, 120)}`);
      const bs = path.join(dir, 'build_sim.js');
      fs.writeFileSync(bs, fs.readFileSync(bs, 'utf8').replace('p.inv=Math.max(p.inv,1.5)', 'p.inv=Math.max(p.inv,9.9)'));
      const r2 = run([]);
      const after = fs.readFileSync(path.join(bdir, 'sim_mp.js'), 'utf8');
      t('build_sim.js 만 고쳐도 mp_run 이 낡은 사본을 버리고 다시 만든다(9.9 반영)', r2.status === 0 && after.includes('Math.max(p.inv,9.9)') && !after.includes('Math.max(p.inv,1.5)'), `rc=${r2.status}`);
      const mtime = fs.statSync(path.join(bdir, 'sim_mp.js')).mtimeMs;
      const r3 = run([]);
      t('바뀐 게 없으면 다시 만들지 않는다(재사용)', r3.status === 0 && fs.statSync(path.join(bdir, 'sim_mp.js')).mtimeMs === mtime);
      // --world-pools 가 다르면 다른 사본이어야 한다
      const r4 = run(['--world-pools', 'first']);
      t('--world-pools 를 바꾸면 사본을 다시 만든다(first 는 월드 풀을 한 번만 돌림)', r4.status === 0 && JSON.parse(fs.readFileSync(path.join(bdir, 'manifest.json'), 'utf8')).world_pools === 'first');
      const miss = cp.spawnSync(process.execPath, [path.join(dir, 'mp_run.js'), '--src', path.join(TMP, 'nope.html'), '--build-dir', bdir, '--secs', '1'], { encoding: 'utf8' });
      t('--src 가 없는 파일이면 스택이 아니라 한 줄 안내 + 종료코드 66', miss.status === 66 && !/at .*\(.*:\d+:\d+\)/.test(miss.stderr) && /읽지 못했습니다/.test(miss.stderr), `rc=${miss.status} ${miss.stderr.slice(0, 200)}`);
    }
    // 7d) 지연 생성 S 필드: 60틱 안에는 안 생기지만 코드에 S.<이름> 으로 적힌 것은 정적 스캔이 잡는다
    {
      const inj = swapMain(m => m.replace('window.__p6=', () => 'function zzLazy(){S.lazyThing=1;}\nwindow.__p6='));
      const built = B.buildFromHtml(inj, 'inj');
      const v = B.verify(built);
      t('정적 스캔: 60틱 안엔 안 생기는 S.lazyThing 을 미분류로 경고', v.classify.static_unclassified.includes('lazyThing') && !v.classify.unclassified.includes('lazyThing') && v.warns.some(w => w.includes('lazyThing')), JSON.stringify(v.classify));
      const base = B.verify(B.buildFromHtml(html, 'x'));
      t('원본: 정적 스캔이 런타임 S 키 수 이상을 찾고(놓치는 게 없다) 미분류가 런타임과 같은 수', base.classify.static_names >= base.classify.S_keys && base.classify.static_unclassified.length === 0, JSON.stringify(base.classify));
    }
    // 7e) 월드 풀 처리: x4(기본)는 틱당 4번 진행, first 는 1번 — README 한계 문구의 근거
    {
      const mv = mode => {
        const built = B.buildFromHtml(html, 'x', { worldPools: mode });
        const x = loadSimCode(built.simMp, { seed: 1 }).__p6x; x.initMP(['brj', 'jjg', 'mms', 'hrb']);
        x.use(0);
        for (let i = 0; i < 3; i++) x.update(1 / 30);   // 데우기
        const b = x.eshots.get(); b.x = b.ox = 5000; b.y = b.oy = 5000; b.vx = 100; b.vy = 0; b.life = 2; b.d = 1; b.g = '♪'; b.sl = 0; b.k = 0; b.src = null; b.sn = 0;
        x.update(1 / 30);
        return { dx: b.x - 5000, life: b.life };
      };
      const a = mv('x4'), f = mv('first');
      t('월드 풀(적 투사체) x4: 틱당 4배 진행(이동 13.33, 수명 −0.133)', Math.abs(a.dx - 13.3333) < 0.01 && Math.abs((2 - a.life) - 0.1333) < 0.001, JSON.stringify(a));
      t('월드 풀(적 투사체) first: 1배 진행(이동 3.33, 수명 −0.033)', Math.abs(f.dx - 3.3333) < 0.01 && Math.abs((2 - f.life) - 0.0333) < 0.001, JSON.stringify(f));
      // first 도 900초가 아니라 짧게나마 예외 없이 도는지
      const r = runCombo({ combo: ['brj', 'jjg', 'mms', 'hrb'], secs: 30, hz: 30, seed: 1, move: 'circle', simMpPath: write('first_sim_mp.js', B.buildFromHtml(html, 'x', { worldPools: 'first' }).simMp) });
      t('--world-pools first 사본이 30초 예외 없이 돈다', r.ok === true, JSON.stringify(r.error || r.ended_early));
    }
  } finally { fs.rmSync(TMP, { recursive: true, force: true }); }
}

(async () => {
  main5();
  section7();
  await eldTest();
  await new Promise(r => setTimeout(r, 50));
  console.log(`\n${fail ? 'FAIL' : 'PASS'} — 통과 ${pass} · 실패 ${fail}`);
  process.exit(fail ? 1 : 0);
})();
