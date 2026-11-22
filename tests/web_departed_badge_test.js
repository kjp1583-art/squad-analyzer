// 🚪 탈퇴 표시 시험 — departedChip/departedNote 만 잘라 돌린다. 사용: node tests/web_departed_badge_test.js
const fs=require('fs'); const s=fs.readFileSync(__dirname+'/../index.html','utf8');
const a=s.indexOf('function departedChip(name)'), b=s.indexOf('function tierGroupCls'); if(a<0||b<0) throw new Error('코드 없음');
const F=new Function('isDeparted',s.slice(a,b)+';return {departedChip,departedNote};')(n=>n==='듀우쿠우#KR1');
let bad=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) bad++; };
ok(/클랜 탈퇴/.test(F.departedChip('듀우쿠우#KR1'))&&/순위·평균/.test(F.departedNote('듀우쿠우#KR1')),'탈퇴자에겐 칩과 안내 줄이 나온다');
ok(F.departedChip('현역')===''&&F.departedNote('현역')==='','현역에겐 아무것도 안 붙는다');
console.log(bad?'FAILED':'ALL PASS'); process.exit(bad?1:0);
