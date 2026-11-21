// 낙찰가 평가(aucVerdict) 경계 시험 — index.html 에서 함수만 뽑아 돌린다
const fs=require('fs'); const s=fs.readFileSync(__dirname+'/../index.html','utf8');
const m=/function aucVerdict\(price,fair\)\{[\s\S]*?\n\}\n/.exec(s); if(!m) throw new Error('aucVerdict 없음');
const aucVerdict=new Function(m[0]+';return aucVerdict;')();
let bad=0; const ok=(n,c)=>{console.log((c?'  ok   ':'  FAIL ')+n); if(!c)bad++;};
ok('적정가 없으면 평가 안 함',aucVerdict(100,null)===null&&aucVerdict(100,0)===null);
ok('5P 유찰급은 적정',aucVerdict(5,20).t==='적정');
ok('100 vs 400 = 꿀매물',aucVerdict(100,400).k==='steal');
ok('250 vs 400 = 가성비',aucVerdict(250,400).k==='good');
ok('400 vs 400 = 적정',aucVerdict(400,400).k==='fair');
ok('600 vs 400 = 비쌈',aucVerdict(600,400).k==='pricey');
ok('900 vs 175 = 흑우',aucVerdict(900,175).k==='over');
ok('차이 30P 미만은 적정',aucVerdict(60,40).k==='fair');
console.log(bad?'FAILED':'ALL PASS'); process.exit(bad?1:0);
