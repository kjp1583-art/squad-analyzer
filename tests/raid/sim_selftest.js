#!/usr/bin/env node
/* 레이드 0단계 — 이 도구들 자신의 시험 (2026-10-08)

   "시험 도구가 조용히 틀리지 않는가"를 본다. 약점을 일부러 넣어 보고 도구가 잡는지 확인한다.
   1) 앵커마다 「없애기」「겹치기」 → build_sim 이 그 앵커 이름을 대며 실패하는가
   2) 패치가 버리는 연결부에 새 문장을 끼우면 → 실패하는가
   3) 퍼센타일 계산이 정확한가(nearest-rank, 알려진 답 + 무작위 대조)
   4) 스텁: 저장소(length/key)·이벤트 등록·fetch 거절·시드 결정성
   5) ESLint 게이트가 4액터 패치 안의 미정의 이름(예: 패치로 사라진 지역 변수)을 실제로 잡는가
   6) 이벤트 루프 지연 측정이 실제 막힘을 보는가
   사용: node tests/raid/sim_selftest.js [--no-lint]      종료코드: 0 전부 통과 · 1 실패 있음 */
'use strict';
const fs = require('fs'), path = require('path'), os = require('os'), cp = require('child_process');
const B = require('./build_sim.js');
const { summarize, pct } = require('./bench_stats.js');
const { loadSimCode, makeWindow } = require('./run_stub.js');
const { stateHash } = require('./mp_run.js');

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

(async () => {
  main5();
  await eldTest();
  await new Promise(r => setTimeout(r, 50));
  console.log(`\n${fail ? 'FAIL' : 'PASS'} — 통과 ${pass} · 실패 ${fail}`);
  process.exit(fail ? 1 : 0);
})();
