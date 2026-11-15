// 🦉 P-48 새벽반 판정 시험: index.html 의 nightOwlOf 를 잘라 가짜 데이터로 돌린다. 사용: node tests/web_nightowl_test.js
const fs=require('fs'); const s=fs.readFileSync(__dirname+'/../index.html','utf8');
const a=s.indexOf('const NIGHTOWL_MIN'), b=s.indexOf('function isDeparted(name){'); if(a<0||b<0) throw new Error('코드 없음');
let fails=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) fails++; };
const pad=n=>String(n).padStart(2,'0');
function rdt(x){ const m=String(x||'').trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?/); return m?new Date(+m[1],+m[2]-1,+m[3],+(m[4]||0),+(m[5]||0)):null; }
const day=i=>{ const d=new Date(Date.now()-i*86400000); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`; };
const mk=(n,hour,off=1)=>Array.from({length:n},(_,i)=>({"날짜":`${day(off+i)} ${pad(hour)}:10`}));
const PL=new Map([['올빼미',[...mk(8,1),...mk(4,21,10)]],['저녁',mk(20,21)],['표본적음',mk(9,2)],['옛날',mk(20,2,100)],['탈퇴',mk(20,2)],['시각없음',Array.from({length:20},(_,i)=>({"날짜":day(i+1)}))],['경계',[...mk(5,4),...mk(5,5)]]]);
const f=new Function('PLAYERS','PLAYERS_ALL','isDeparted','canonOfName','_rdt', s.slice(a,b)+';return nightOwlOf;')(PL,PL,n=>n==='탈퇴',n=>n,rdt);
ok(f('올빼미')&&f('올빼미').k===8&&f('올빼미').n===12, '새벽 8/12판(67%) → 새벽반');
ok(!f('저녁'), '저녁에만 뛰면 아님');
ok(!f('표본적음'), '10판 미만이면 뱃지 없음');
ok(!f('옛날'), '2개월 넘은 판만 있으면 아님');
ok(!f('탈퇴'), '탈퇴자는 제외');
ok(!f('시각없음'), '시각이 없는 판은 세지 않음');
ok(f('경계')&&f('경계').k===5, '4시 59분까지 새벽 · 5시는 아님(5/10=50% 경계 포함)');
ok(!f('없는사람'), '기록 없는 사람은 null');
console.log(fails?'FAIL '+fails:'ALL PASS'); process.exit(fails?1:0);
