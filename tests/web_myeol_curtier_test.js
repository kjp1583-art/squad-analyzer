// 🏷 적정가 현재 티어·현재 닉 시험 — computeMyeol 안의 curTier 만 잘라 돌린다. 사용: node tests/web_myeol_curtier_test.js
const fs=require('fs'); const s=fs.readFileSync(__dirname+'/../index.html','utf8');
const a=s.indexOf('  const _TN={0:"0티어"'), b=s.indexOf('  const N2C=new Map();',a); if(a<0||b<0) throw new Error('코드 없음');
const cur={ '카무사리':'2中', '옛날':'1', '영':'0', '없음':null };
const curTier=new Function('tierOf',s.slice(a,b)+';return curTier;')(n=>cur[n]??null);
let bad=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) bad++; };
ok(JSON.stringify(curTier('카무사리','귤 갓','I티어','下'))===JSON.stringify(['II티어','中']),'현재 티어표(2中)가 스냅샷(I티어 下)보다 우선');
ok(JSON.stringify(curTier('영','x','I티어','上'))===JSON.stringify(['0티어','-']),'0티어는 등급 없이');
ok(JSON.stringify(curTier('옛날','x','III티어','下'))===JSON.stringify(['III티어','下']),'등급이 빠진 값은 못 믿고 스냅샷');
ok(JSON.stringify(curTier('없음','없음','II티어','上'))===JSON.stringify(['II티어','上']),'티어표에 없으면 스냅샷');
console.log(bad?'FAILED':'ALL PASS'); process.exit(bad?1:0);
