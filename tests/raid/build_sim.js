#!/usr/bin/env node
/* 레이드 0단계 — 시뮬 이식 빌더 (2026-10-08)

   survivors.html 의 메인 게임 <script> 블록에서 서버용 시험 사본 두 개를 만든다.
     sim.js     = 메인 블록 + 최소 훅(window.__p6x)         — 솔로 1액터 그대로
     sim_mp.js  = sim.js 의 update() 를 4액터 구조로 텍스트 패치한 사본 — 시험·측정 전용
   ※ 이 텍스트 패치는 "가능한가"를 재는 시험용이다. 제품 빌드가 아니다(설계서가 제품에는 텍스트 패치 빌드를 금지).
   ※ survivors.html·index.html·data/* 는 읽기만 한다.

   사용: node tests/raid/build_sim.js [--src survivors.html] [--out tests/raid/.build] [--no-verify] [--quiet]
   모든 앵커 문자열은 존재·유일성을 검사하고, 하나라도 어긋나면 어느 앵커가 왜 안 맞는지 말하며 종료코드 2 로 실패한다. */
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');

const REPO = path.resolve(__dirname, '..', '..');

// ── 시험 도구가 쓰는 최소 훅 ────────────────────────────────────────────────
// (tests/sv_harness.py 의 HOOK 에는 의존하지 않는다 — 이 목록이 이 도구의 계약이다)
const HOOK = `
// ── 레이드 0단계 시험 훅(build_sim.js 가 꽂는다 · 제품 코드 아님) ──
window.__p6x={get S(){return S},get state(){return state},set state(v){state=v},get keys(){return keys},set keys(v){keys=v},get CUR(){return CUR},
update,resume,pick,newRun,start,endRun,CHARS,WEAP,PASS,TIERS,enemies,gems,props,items,shots,eshots,hazards,texts,
CH_set(k){CH=CHARS.find(c=>c.k===k)},get CH(){return CH},set CH(v){CH=v}/*__MP_HOOK__*/};
`;
// 훅이 반드시 내놓아야 하는 이름(로드 뒤 verify 가 확인)
const HOOK_KEYS = ['S', 'state', 'keys', 'CUR', 'update', 'resume', 'pick', 'newRun', 'start', 'endRun', 'CHARS', 'WEAP', 'PASS', 'TIERS',
  'enemies', 'gems', 'props', 'items', 'shots', 'eshots', 'hazards', 'texts', 'CH_set', 'CH'];
const MP_HOOK_KEYS = ['initMP', 'use', 'ACT', 'NDEATH', 'ACTI'];

// ── 액터(플레이어)별로 갈라 갖는 S 필드 — patch.py 의 PKS 그대로 ──
const PKS = 'lv xp need pendingLv p w ps ev revUsed ramen tier tk pt rel tr sm hc leechT stillT shield spr stT pulseT relT magT dq cd aura booms sushi newU staffT slowR proomT proom dashCd br x2 x3 mines wifiA wifiL wifiN wifiEv dmgBy rg rgB dT dS dA dN dW rr ban banned banMode syn synOn vk invCur invPk sgT sgC sgH sgK auT feedN feedA sushiA frP lastBlock auraR'.split(' ');
// 판(월드) 전체가 같이 쓰는 S 필드 — 스크래치 keys.js 의 WORLD 그대로
const WORLD = 't,kills,endless,hard,vh,dly,live,kc,ne,lite,nextBoss,nextMini,nextSp,miniN,bossN,bigT,bigSeen,evT,evN,propT,chickT,chkT,spawnT,seen,wvId,zapId,bossRef,room,cone,cardW,ebooms,beams,won,shake,flash,tcd,sayT,midKill,bossKill,canId,rangN,zone'.split(',');

const sha256 = s => crypto.createHash('sha256').update(s).digest('hex');
const count = (hay, needle) => { let n = 0, i = -1; while ((i = hay.indexOf(needle, i + 1)) >= 0) n++; return n; };

class AnchorErr extends Error {
  constructor(list) {
    super('앵커 ' + list.length + '건이 어긋났습니다 — survivors.html 이 바뀌어 패치가 맞지 않습니다:\n' + list.map(s => '  - ' + s).join('\n') +
      '\n대처: tests/raid/README.md 「앵커가 어긋났을 때」 참고. 조용히 틀린 사본을 만들지 않으려고 여기서 멈춥니다.');
    this.anchors = list;
  }
}

/* hay 안에서 needle 이 정확히 want 번 나오는지 본다. 틀리면 fails 에 이유를 쌓고 -1 을 돌려준다. */
function need(fails, where, name, hay, needle, want = 1) {
  const n = count(hay, needle);
  if (n !== want) {
    fails.push(`[${name}] ${where} 안에서 ${n === 0 ? '찾지 못했습니다' : n + '번 나옵니다(유일해야 하는 곳은 ' + want + '번)'} — ${JSON.stringify(needle.length > 90 ? needle.slice(0, 90) + '…' : needle)}`);
    return -1;
  }
  return hay.indexOf(needle);
}

/* 메인 게임 <script> 블록을 찾는다: 훅 앵커(window.__p6={…};)를 가진, 가장 큰 블록. */
function extractMain(html) {
  const fails = [], blocks = [];
  const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;
  let m;
  while ((m = re.exec(html))) blocks.push(m[1]);
  if (!blocks.length) throw new AnchorErr(['<script> 블록을 하나도 못 찾았습니다']);
  const sizes = blocks.map(b => b.length);
  const withHook = blocks.map((b, i) => [b, i]).filter(([b]) => b.includes('window.__p6='));
  if (withHook.length !== 1) throw new AnchorErr([`훅 앵커 "window.__p6=" 를 가진 <script> 블록이 ${withHook.length}개입니다(1개여야 함) · 블록 크기 ${sizes.join('/')}`]);
  const [main, idx] = withHook[0];
  if (sizes[idx] !== Math.max(...sizes)) fails.push(`훅이 들어갈 블록(#${idx})이 가장 큰 블록이 아닙니다 · 블록 크기 ${sizes.join('/')}`);
  if (!/^\s*\(\(\)=>\{/.test(main)) fails.push('메인 블록이 "(()=>{" 로 시작하지 않습니다(즉시실행 함수 구조가 바뀜)');
  if (!/\}\)\(\);\s*$/.test(main)) fails.push('메인 블록이 "})();" 로 끝나지 않습니다(즉시실행 함수 구조가 바뀜)');
  if (fails.length) throw new AnchorErr(fails);
  return { main, idx, sizes };
}

/* 1) sim.js: 훅 꽂기 */
function makeSim(main) {
  const fails = [];
  const re = /window\.__p6=\{[^\n]*\};/g;
  const hits = main.match(re) || [];
  if (hits.length !== 1) fails.push(`[훅 앵커] "window.__p6={…};" 한 줄이 ${hits.length}개입니다(1개여야 함)`);
  else {
    const at = main.indexOf(hits[0]) + hits[0].length;
    if (!/^\s*\}\)\(\);\s*$/.test(main.slice(at))) fails.push('[훅 앵커] "window.__p6={…};" 뒤에 "})();" 외의 코드가 더 있습니다(훅이 IIFE 끝이 아닌 곳에 꽂힘)');
  }
  if (fails.length) throw new AnchorErr(fails);
  const at = main.indexOf(hits[0]) + hits[0].length;
  return main.slice(0, at) + '\n' + HOOK + main.slice(at);
}


// ── update() 를 자르는 구간 시작 앵커(앞에서 뒤로 이 순서) — 각각 update() 안에서 정확히 1번 나와야 한다 ──
const SEG_ANCHORS = {
  move: 'let mx=', live: 'S.live.length=0', wave: 'waveTick(dt);', wpn: 'weapons(dt);charTick(dt);relTick(dt);',
  shots: "SRC='feed';for(const s of shots.a)", en: "SRC='';for(const e of enemies.a){", haz: 'for(const h of hazards.a)',
  beam: 'if(beamTick(dt))return;', ebm: 'for(let i=S.ebooms.length-1', cone: 'if(S.cone){', mag: 'const mag=(70*',
  texts: 'for(const t of texts.a)if(t.on){t.life', map: 'mapTick(dt);if(state',
};
// ── 구간 안에서 문장을 바꾸는 치환 앵커 ──
const REP_ANCHORS = {
  hurtS: 'hurt(e,s.dmg)', vxS: 's.vx*(p.x-e.x)+s.vy*(p.y-e.y)',
  target: 'const dx=p.x-e.x,dy=p.y-e.y,d=Math.hypot(dx,dy)||1;',
  gemMerge: 'if((gemMT-=dt)<=0){gemMT=.25;gemMerge();}',
  mapTail: "bubTick(dt);\n  mapTick(dt);if(state!=='play')return;",
  lvup: 'if(S.pendingLv>0)openLvup();',
};
const FIRE = 'function fire(x,y,a,v,life,dmg,pc,r,c){const s=shots.get();if(!s)return;';
const DIE = 'function die(){';
const WHOLE_ANCHORS = ['function update(dt){', 'function endRun(won,quit){', FIRE, DIE];
// 자기 시험(sim_selftest.js)이 앵커마다 「없애기/겹치기」를 시험하는 데 쓴다
const ANCHOR_STRINGS = [...Object.values(SEG_ANCHORS), ...Object.values(REP_ANCHORS), ...WHOLE_ANCHORS];

/* 2) sim_mp.js: patch.py 를 옮긴 4액터 패치 */
function makeSimMp(sim) {
  const fails = [];
  const a = need(fails, 'sim.js', 'update 시작', sim, 'function update(dt){');
  const b = need(fails, 'sim.js', 'endRun 시작', sim, 'function endRun(won,quit){');
  if (a >= 0 && b >= 0 && a > b) fails.push('[update/endRun] update() 가 endRun() 뒤에 있습니다(순서가 바뀜)');
  if (a < 0 || b < 0) throw new AnchorErr(fails);
  const U = sim.slice(a, b);

  const I = {};
  for (const k in SEG_ANCHORS) I[k] = need(fails, 'update()', '구간 시작 ' + k, U, SEG_ANCHORS[k]);
  // 구간 순서(앞에서 뒤로 단조 증가)
  const order = ['move', 'live', 'wave', 'wpn', 'shots', 'en', 'haz', 'beam', 'ebm', 'cone', 'mag', 'texts', 'map'];
  if (!fails.length) for (let i = 1; i < order.length; i++) if (I[order[i]] <= I[order[i - 1]]) fails.push(`[구간 순서] update() 안에서 ${order[i]} 가 ${order[i - 1]} 보다 앞에 있습니다(순서가 바뀜)`);

  // 패치가 버리는 구간(앵커 사이의 짧은 연결부)이 예상한 모양 그대로인지 — 그 사이에 새 문장이 끼면 조용히 지워지므로 여기서 잡는다
  if (!fails.length) {
    const drops = [
      ['update 머리', U.slice(0, I.move), /^function update\(dt\)\{\s*S\.t\+=dt;const p=S\.p;EX\.tick\(dt\);[^\n]*\n\s*$/],
      ['waveTick~weapons 사이', U.slice(I.wave, I.wpn), /^waveTick\(dt\);if\(state!=='play'\)return;\s*$/],
      ['beamTick 줄', U.slice(I.beam, I.ebm), /^if\(beamTick\(dt\)\)return;\s*$/],
    ];
    for (const [nm, txt, re] of drops) if (!re.test(txt)) fails.push(`[버려지는 연결부: ${nm}] 예상한 모양이 아닙니다(그 사이에 새 코드가 끼었다면 패치가 조용히 지워 버립니다) — ${JSON.stringify(txt.length > 160 ? txt.slice(0, 160) + '…' : txt)}`);
  }
  if (fails.length) throw new AnchorErr(fails);

  const move = U.slice(I.move, I.live), live = U.slice(I.live, I.wave), wpn = U.slice(I.wpn, I.shots);
  let shots = U.slice(I.shots, I.en), en = U.slice(I.en, I.haz);
  const haz = U.slice(I.haz, I.beam), beam = U.slice(I.beam, I.ebm), ebm = U.slice(I.ebm, I.mag);
  let mag = U.slice(I.mag, I.texts), tail = U.slice(I.texts);

  need(fails, 'shots 구간', 'hurt(e,s.dmg)', shots, REP_ANCHORS.hurtS);
  need(fails, 'shots 구간', 's.vx*(p.x-e.x)+…', shots, REP_ANCHORS.vxS);
  need(fails, 'enemies 구간', '표적 선택', en, REP_ANCHORS.target);
  need(fails, 'mag 구간', 'gemMerge', mag, REP_ANCHORS.gemMerge);
  need(fails, 'tail 구간', 'mapTick 꼬리', tail, REP_ANCHORS.mapTail);
  need(fails, 'tail 구간', 'openLvup', tail, REP_ANCHORS.lvup);
  need(fails, 'sim.js', 'fire()', sim, FIRE);
  need(fails, 'sim.js', 'die()', sim, DIE);
  need(fails, 'sim.js', '훅 마커', sim, '/*__MP_HOOK__*/');
  if (fails.length) throw new AnchorErr(fails);

  const R = (s, from, to) => s.replace(from, () => to);   // 문자열 치환($ 패턴 해석 끔)
  shots = R(shots, REP_ANCHORS.hurtS, 'use(s.own|0);hurt(e,s.dmg)');
  shots = R(shots, REP_ANCHORS.vxS, 's.vx*(ACT[s.own|0].b.p.x-e.x)+s.vy*(ACT[s.own|0].b.p.y-e.y)');
  en = R(en, REP_ANCHORS.target, 'let ti=0,bd=1e18;for(let q=0;q<ACT.length;q++){const a=ACT[q].b.p;const d2=(a.x-e.x)**2+(a.y-e.y)**2;if(d2<bd){bd=d2;ti=q;}}use(ti);const p=S.p;const dx=p.x-e.x,dy=p.y-e.y,d=Math.hypot(dx,dy)||1;');
  mag = R(mag, REP_ANCHORS.gemMerge, '');
  tail = R(tail, REP_ANCHORS.mapTail, "bubTick(dt);\n  for(let ai=0;ai<ACT.length;ai++){use(ai);mapTick(dt);if(state!=='play')state='play';}");
  tail = R(tail, REP_ANCHORS.lvup, 'for(let ai=0;ai<ACT.length;ai++){use(ai);while(S.pendingLv>0){S.pendingLv--;const c=offers(3);applyUp(c[ai%c.length]);}}');

  const wrap = t => 'for(let ai=0;ai<ACT.length;ai++){use(ai);const p=S.p;\n  ' + t + '}\n  ';
  const moveLoop = 'for(let ai=0;ai<ACT.length;ai++){use(ai);const p=S.p,keys=ACT[ai].keys,joy=ACT[ai].joy;\n  ' + move + '}\n  ';
  const wpnLoop = 'for(let ai=0;ai<ACT.length;ai++){use(ai);' + wpn + '}\n  ';
  const beamLoop = 'for(let ai=0;ai<ACT.length;ai++){use(ai);beamTick(dt);}\n  ';
  const magLoop = 'if((gemMT-=dt)<=0){gemMT=.25;gemMerge();}\n  for(let ai=0;ai<ACT.length;ai++){use(ai);const p=S.p;\n  ' + mag + '}\n  ';

  const infra = `
// ── 4액터 시험 인프라(build_sim.js 가 만든다 · 액터별 필드는 use(i) 로 S 에 끼워 넣는다) ──
const ACT=[];let ACTI=-1,NDEATH=0;const PKS=${JSON.stringify(PKS)};
function use(i){if(i===ACTI)return;if(ACTI>=0){const a=ACT[ACTI];for(const k of PKS)a.b[k]=S[k];}
  const n=ACT[i];for(const k of PKS)S[k]=n.b[k];CH=n.ch;ACTI=i;}
function addActor(chk){CH=CHARS.find(c=>c.k===chk);if(!CH)throw new Error('알 수 없는 캐릭터 키: '+chk);newRun();const b={};for(const k of PKS)b[k]=S[k];
  ACT.push({b,ch:CH,keys:{},joy:{on:false,dx:0,dy:0}});ACTI=-1;}
function initMP(chs){ACT.length=0;ACTI=-1;NDEATH=0;for(const c of chs)addActor(c);
  // 월드 S 는 마지막 newRun 의 것 — 판 상태 초기화 후 첫 액터를 끼운다
  newRun();ACTI=-1;
  // 각 액터 시작 위치를 흩어 둔다
  ACT.forEach((a,i)=>{a.b.p.x=Math.cos(i*1.57)*120;a.b.p.y=Math.sin(i*1.57)*120;});use(0);state='play';}
`;
  const header = 'function update(dt){\n  S.t+=dt;EX.tick(dt);\n  ';
  const newUpdate = infra + header + moveLoop + live + 'use(Math.random()*ACT.length|0);waveTick(dt);\n  ' + wpnLoop + shots + en +
    wrap(haz) + beamLoop + wrap(ebm) + magLoop + tail;
  let js = sim.slice(0, a) + newUpdate + sim.slice(b);
  js = R(js, FIRE, FIRE + 's.own=ACTI;');
  js = R(js, DIE, 'function die(){const p=S.p;p.hp=p.mhp;p.inv=Math.max(p.inv,1.5);NDEATH++;return false;}\nfunction die_old(){');
  js = R(js, '/*__MP_HOOK__*/', ',initMP,use,ACT,get NDEATH(){return NDEATH},get ACTI(){return ACTI}');
  if (js.includes('/*__MP_HOOK__*/')) throw new AnchorErr(['[훅 마커] 치환이 끝나지 않았습니다']);
  return js;
}

/* 소스 한 번에: 입력 html → {sim, simMp, manifest} */
function buildFromHtml(html, srcLabel) {
  const { main, idx, sizes } = extractMain(html);
  const sim = makeSim(main);
  const simMp = makeSimMp(sim);
  const sha = sha256(html);
  const tag = `/* GENERATED by tests/raid/build_sim.js — src=${srcLabel || 'survivors.html'} sha256=${sha} — 시험용 사본(제품 아님) */\n`;
  return {
    sim: tag + sim, simMp: tag + simMp,
    manifest: { v: 1, kind: 'sim-build', src: srcLabel || 'survivors.html', survivors_sha256: sha, survivors_bytes: Buffer.byteLength(html),
      script_blocks: sizes, main_block_index: idx, sim_bytes: sim.length, sim_mp_bytes: simMp.length,
      sim_sha256: sha256(tag + sim), sim_mp_sha256: sha256(tag + simMp), PKS_count: PKS.length, WORLD_count: WORLD.length },
  };
}

/* 로드 시험: 두 사본이 스텁에서 올라오고, 훅이 계약대로이며, S 필드가 분류되는지 본다. 문제 목록을 돌려준다(빈 배열 = 이상 없음). */
function verify(built) {
  const { loadSimCode } = require('./run_stub.js');
  const problems = [], warns = [];
  const w1 = loadSimCode(built.sim);
  const x1 = w1.__p6x;
  for (const k of HOOK_KEYS) if (!(k in x1)) problems.push('훅에 ' + k + ' 가 없습니다');
  if (x1.CHARS && !x1.CHARS.length) problems.push('CHARS 가 비어 있습니다');
  const w2 = loadSimCode(built.simMp);
  const x2 = w2.__p6x;
  for (const k of MP_HOOK_KEYS) if (!(k in x2)) problems.push('4액터 훅에 ' + k + ' 가 없습니다');
  let classify = null;
  if (!problems.length) {
    try {
      x2.initMP(['brj', 'jjg', 'mms', 'hrb']);
      for (let i = 0; i < 60; i++) { x2.update(1 / 30); if (x2.state !== 'play') x2.resume(); }
      const keys = Object.keys(x2.S);
      const known = new Set([...PKS, ...WORLD]);
      const unclassified = keys.filter(k => !known.has(k));
      const missingPKS = PKS.filter(k => !keys.includes(k));
      classify = { S_keys: keys.length, unclassified, pks_missing_in_S: missingPKS };
      if (unclassified.length) warns.push('S 에 PKS(액터별)/WORLD(월드) 어디에도 분류되지 않은 필드: ' + unclassified.join(' ') +
        ' — 액터별로 갈라야 하는 필드면 build_sim.js 의 PKS 에, 월드 공용이면 WORLD 에 넣으세요(안 하면 4액터 시험에서 액터끼리 값을 공유)');
      if (missingPKS.length) warns.push('PKS 에 있으나 S 에 없는 필드: ' + missingPKS.join(' ') + ' — 이름이 바뀌었을 수 있습니다');
    } catch (e) { problems.push('4액터 초기화/60틱 시험이 예외로 멈췄습니다: ' + (e && e.stack || e).toString().split('\n').slice(0, 4).join(' | ')); }
  }
  return { problems, warns, classify };
}

function parseArgs(argv) {
  const o = { src: path.join(REPO, 'survivors.html'), out: path.join(__dirname, '.build'), verify: true, quiet: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--src') o.src = path.resolve(argv[++i]);
    else if (a === '--out') o.out = path.resolve(argv[++i]);
    else if (a === '--no-verify') o.verify = false;
    else if (a === '--quiet') o.quiet = true;
    else if (a === '-h' || a === '--help') { o.help = true; }
    else { console.error('알 수 없는 옵션: ' + a); process.exit(64); }
  }
  return o;
}

function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help) { console.log('node tests/raid/build_sim.js [--src survivors.html] [--out tests/raid/.build] [--no-verify] [--quiet]'); return 0; }
  const log = o.quiet ? () => {} : console.log;
  let html;
  try { html = fs.readFileSync(o.src, 'utf8'); } catch (e) { console.error('입력을 읽지 못했습니다: ' + o.src + ' — ' + e.message); return 66; }
  let built;
  try { built = buildFromHtml(html, path.relative(REPO, o.src) || o.src); }
  catch (e) { if (e instanceof AnchorErr) { console.error('BUILD FAIL\n' + e.message); return 2; } throw e; }
  fs.mkdirSync(o.out, { recursive: true });
  fs.writeFileSync(path.join(o.out, 'sim.js'), built.sim);
  fs.writeFileSync(path.join(o.out, 'sim_mp.js'), built.simMp);
  let ver = null;
  if (o.verify) {
    ver = verify(built);
    built.manifest.verify = { ok: !ver.problems.length, classify: ver.classify, warns: ver.warns };
  }
  built.manifest.built_at = new Date().toISOString();
  fs.writeFileSync(path.join(o.out, 'manifest.json'), JSON.stringify(built.manifest, null, 2) + '\n');
  log(`build ok — survivors sha256=${built.manifest.survivors_sha256.slice(0, 12)}… blocks=${built.manifest.script_blocks.join('/')} sim=${built.sim.length}B sim_mp=${built.simMp.length}B → ${path.relative(process.cwd(), o.out) || '.'}`);
  if (ver) {
    for (const w of ver.warns) console.warn('WARN ' + w);
    if (ver.problems.length) { console.error('VERIFY FAIL\n' + ver.problems.map(s => '  - ' + s).join('\n')); return 3; }
    log('verify ok — 훅 ' + HOOK_KEYS.length + '개 + 4액터 훅 ' + MP_HOOK_KEYS.length + '개, 4액터 60틱 통과, S 필드 ' + ver.classify.S_keys + '개(미분류 ' + ver.classify.unclassified.length + ')');
  }
  return 0;
}

/* 다른 도구(mp_run·cover·bench)가 쓴다: 빌드 폴더의 사본이 지금 survivors.html 과 같은 것인지 sha256 으로 확인하고,
   없거나 낡았으면 새로 만든다. 낡은 사본으로 조용히 시험하는 일을 막는다. */
function ensureBuilt(src, outDir, opts = {}) {
  src = path.resolve(src || path.join(REPO, 'survivors.html'));
  outDir = path.resolve(outDir || path.join(__dirname, '.build'));
  const html = fs.readFileSync(src, 'utf8');
  const sha = sha256(html);
  const mf = path.join(outDir, 'manifest.json');
  let m = null;
  try { m = JSON.parse(fs.readFileSync(mf, 'utf8')); } catch (e) { /* 없음 */ }
  const ok = m && m.survivors_sha256 === sha && fs.existsSync(path.join(outDir, 'sim.js')) && fs.existsSync(path.join(outDir, 'sim_mp.js'));
  if (!ok || opts.force) {
    const built = buildFromHtml(html, path.relative(REPO, src) || src);   // 앵커가 어긋나면 AnchorErr 로 멈춘다
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'sim.js'), built.sim);
    fs.writeFileSync(path.join(outDir, 'sim_mp.js'), built.simMp);
    built.manifest.built_at = new Date().toISOString();
    fs.writeFileSync(mf, JSON.stringify(built.manifest, null, 2) + '\n');
    m = built.manifest;
  }
  return { simPath: path.join(outDir, 'sim.js'), simMpPath: path.join(outDir, 'sim_mp.js'), manifest: m, sha256: sha, src };
}

module.exports = { ensureBuilt, ANCHOR_STRINGS, SEG_ANCHORS, REP_ANCHORS, buildFromHtml, verify, extractMain, makeSim, makeSimMp, AnchorErr, PKS, WORLD, HOOK_KEYS, MP_HOOK_KEYS, sha256, REPO };
if (require.main === module) process.exit(main());
