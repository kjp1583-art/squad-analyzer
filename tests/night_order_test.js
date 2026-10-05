// node tests/night_order_test.js — index.html 의 P14 구간(nightOrderStats)을 떼어 시험
const fs=require('fs'),assert=require('assert');
const s=fs.readFileSync(__dirname+'/../index.html','utf8');
const m=/\/\*P14-BEGIN[\s\S]*?\/\*P14-END\*\//.exec(s); assert(m,'P14 구간 없음');
const nightOrderStats=new Function(m[0]+';return nightOrderStats;')();
let gid=1000;
const R=(d,res='승리',o={})=>Object.assign({"게임ID":"#"+(gid++),"날짜":d,"소환사명":"a#1","PUUID":"p","결과":res,"KDA":"2/1/3","점수":"20"},o);
// 정오 경계: 11:59 는 전날 밤, 12:00 은 새 밤
let S=nightOrderStats([R("2026-10-01 11:59"),R("2026-10-01 12:00")]);
assert.equal(S.first.n,2,'서로 다른 밤 → 둘 다 1판째');
// 자정 넘김: 23:50 와 00:10 은 같은 밤 → 2번째 판은 mid
S=nightOrderStats([R("2026-10-01 23:50"),R("2026-10-02 00:10")]);
assert.equal(S.first.n,1); assert.equal(S.mid.n,1);
// 같은 시각 판: 게임ID 순
// (문자열 비교 기준: "#10" < "#9" → #10 이 1판째 → 승)
S=nightOrderStats([R("2026-10-01 20:00","패배",{"게임ID":"#9"}),R("2026-10-01 20:00","승리",{"게임ID":"#10"})]);
assert.equal(S.first.w,1);
// 결과 대기·무효·시각 없음 제외, 번호도 안 먹음
S=nightOrderStats([R("2026-10-01 20:00","결과 대기"),R("2026-10-01 20:10","무효"),R("2026-10-01","승리"),R("2026-10-01 20:20","승리")]);
assert.equal(S.total,1); assert.equal(S.first.n,1);
// 빈 입력·한 밤 1판
S=nightOrderStats([]); assert.equal(S.total,0); assert.equal(S.kind,'none'); assert.equal(S.first.wr,null);
S=nightOrderStats([R("2026-10-01 20:00")]); assert.equal(S.first.n,1); assert.equal(S.mid.n,0); assert.equal(S.first.ok,false);
// 중복(같은 게임ID·PUUID) 한 번만
const d=R("2026-10-01 20:00"); S=nightOrderStats([d,Object.assign({},d)]); assert.equal(S.total,1);
// 4판째 이후 분류
const night=[...Array(5)].map((_,i)=>R(`2026-10-01 2${i}:00`));
S=nightOrderStats(night); assert.deepEqual([S.first.n,S.mid.n,S.late.n],[1,2,2]);
// 표본 14/15 경계: 1판째 n판(각각 다른 밤) + 2판째 15판
function mkset(nFirst,nRest,firstWins,restWins){ const rows=[]; let day=1;
  for(let i=0;i<Math.max(nFirst,nRest);i++){ const dd=`2026-08-${String(day).padStart(2,'0')}`; day++;
    if(i<nFirst) rows.push(R(dd+" 20:00",i<firstWins?"승리":"패배"));
    if(i<nRest) rows.push(R(dd+" 21:00",i<restWins?"승리":"패배")); }
  return rows; }
S=nightOrderStats(mkset(14,14,5,12)); assert.equal(S.first.ok,false); assert.equal(S.kind,'none');
S=nightOrderStats(mkset(15,14,5,12)); assert.equal(S.rest.ok,false); assert.equal(S.kind,'none');
S=nightOrderStats(mkset(15,15,5,12)); assert.equal(S.first.ok,true); assert.equal(S.kind,'warm'); assert(S.diff>=10);
S=nightOrderStats(mkset(15,15,12,5)); assert.equal(S.kind,'fresh');
S=nightOrderStats(mkset(15,15,8,9)); assert.equal(S.kind,'flat');
// 부계 합산: 호출측이 사람 단위로 묶은 목록(다른 PUUID)을 넘기면 한 밤 번호가 합쳐진다
S=nightOrderStats([R("2026-10-01 20:00","승리",{PUUID:"main"}),R("2026-10-01 21:00","패배",{PUUID:"alt","소환사명":"b#2"})]);
assert.equal(S.first.n,1); assert.equal(S.mid.n,1);
// 최근 90일: 번호는 전 기간, 집계만 90일
const now=Date.UTC(2026,9,5);
S=nightOrderStats([R("2026-05-01 20:00"),R("2026-10-01 20:00"),R("2026-10-01 21:00")],{days:90,now});
assert.equal(S.first.n,1); assert.equal(S.mid.n,1);
S=nightOrderStats([R("2026-09-30 20:00"),R("2026-09-30 21:00")],{days:90,now}); assert.equal(S.total,2);
// KDA·점수
S=nightOrderStats([R("2026-10-01 20:00","승리",{KDA:"4/2/2",점수:"30"})]); assert.equal(S.first.kda,3); assert.equal(S.first.score,30);
console.log('night_order_test OK');
