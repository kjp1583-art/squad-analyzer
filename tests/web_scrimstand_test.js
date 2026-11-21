// 스크림 순위표(_scrimStandings) 시험 — 함수만 뽑아 돌린다
const fs=require('fs'); const s=fs.readFileSync(__dirname+'/../index.html','utf8');
const m=/function _scrimStandings\(list\)\{[\s\S]*?\n\}\n/.exec(s); if(!m) throw new Error('없음');
const F=new Function(m[0]+';return _scrimStandings;')();
let bad=0; const ok=(n,c)=>{console.log((c?'  ok   ':'  FAIL ')+n); if(!c)bad++;};
const D=(d)=>new Date(2026,10,d); let id=1;
const g=(day,win,lose)=>({day:D(day),gid:String(id++),win,lose});
const L=[g(1,'A','B'),g(1,'A','C'),g(2,'B','C'),g(3,'C','A'),g(3,'B','A')];
const r=F(L); const by=Object.fromEntries(r.map(e=>[e.t,e]));
ok('A 2-2 · B 2-1 · C 1-3 → 1위 B', r[0].t==='B'&&by.B.w===2&&by.B.l===1);
ok('A 2승 2패', by.A.w===2&&by.A.l===2);
ok('B 연속 2W', by.B.streak==='2W');
ok('A 연속 2L', by.A.streak==='2L');
// 3일 전엔 A 2-0, B 1-1, C 0-2 → A1 B2 C3 / 지금 B1 A2 C3
ok('B 순위 ▲1', by.B.chg===1); ok('A 순위 ▼1', by.A.chg===-1); ok('C 변동 없음', by.C.chg===0);
ok('빈 목록도 안 죽는다', F([]).length===0);
ok('하루치뿐이면 변동 0', F([g(5,'A','B')]).every(e=>e.chg===0&&!e.isNew));
console.log(bad?'FAILED':'ALL PASS'); process.exit(bad?1:0);
