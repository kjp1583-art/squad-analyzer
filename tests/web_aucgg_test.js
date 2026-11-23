// 🔨 AUC.GG 연동 시험(2026-11-21): index.html 에서 연동 구역만 잘라 가짜 fetch·localStorage 로 돌린다. 사용: node tests/web_aucgg_test.js
const fs=require('fs'), path=require('path'); const src=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
const a=src.indexOf('const AUCGG_BASE='), b=src.indexOf('function _myFold(title,sub,body,open){'); if(a<0||b<0) throw new Error('연동 코드 없음');
const LIST=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures','aucgg_list.json'),'utf8')), D22=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures','aucgg_22.json'),'utf8'));
let fails=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) fails++; };
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function make(fetchImpl){
  const ls={}; const localStorage={getItem:k=>ls[k]??null,setItem:(k,v)=>{ls[k]=v;}};
  const doc={getElementById:()=>null};
  const f=new Function('fetch','localStorage','document','esc','AbortController','renderMyeol','LS','teamEmblem','myeolFairOf','teamLink','posIcon', 'function aucNoOf(d){ const m=String((d&&d.name)||"").match(/제\\s*(\\d+)\\s*회/); return m?+m[1]:null; }\n'+src.slice(a,b)+';return {AUCGG:()=>AUCGG,aucEnsure,aucParseList,aucParseDetail,aucNick,aucMyeolAuctions,aucExtraPrices,aucCardBody,ls:()=>LS};');
  return f(fetchImpl,localStorage,doc,esc,AbortController,()=>{},ls,()=>'',()=>null,(c)=>String(c),(p)=>p?'<img data-pos="'+p+'">':'');
}
const mk=(extra={})=>async url=>{ if(extra.fail) throw new Error('net'); const u=String(url);
  if(u.endsWith('/tournaments')) return {ok:true,json:async()=>extra.list||LIST};
  const m=u.match(/\/tournaments\/(\d+)$/); const id=+m[1];
  if(id===22) return {ok:true,json:async()=>D22};
  return {ok:true,json:async()=>({id,name:id===30?'제 10회 멸망전':'2026.08.14 미니토너먼트',mode:'AUCTION',finishedAt:'2026-12-01T10:00:00.000Z',teams:[{id:1,name:'가',captain:'팀장A#kr1',players:[{nickname:'선수1#x',position:'TOP',tier:'마스터',price:300,pick:null},{nickname:'선수2',position:'JGL',tier:'다이아몬드',price:450,pick:null}]}]})}; };
(async()=>{
  const A=make(mk());
  ok(A.aucNick('Gyuse0k#kr1')==='Gyuse0k'&&A.aucNick(' 택 스 ')==='택 스','닉네임에서 #태그 제거');
  const L=A.aucParseList(LIST); ok(L.length===6&&L[1].id===22&&L[1].mode==='AUCTION','목록 파싱(6건, 22번=경매)');
  const D=A.aucParseDetail(D22); ok(D.teams.length===12&&D.teams.every(t=>t.m.length===4),'제9회 상세 12팀 × 4명');
  ok(D.teams[0].m[0].pos==='정글'&&D.teams[0].m[0].price===550,'포지션 한글(JGL→정글)·낙찰가 숫자');
  ok(A.aucParseList({x:1})===null&&A.aucParseDetail({id:1})===null&&A.aucParseDetail(null)===null,'형식이 깨지면 null');
  // 내장 값(MYEOL_TEAMS9)과의 일치 — 8개 팀은 닉 표기까지 똑같아야 한다
  const blk=src.slice(src.indexOf('const MYEOL_TEAMS9=['),src.indexOf('];',src.indexOf('const MYEOL_TEAMS9=[')));
  const mine={}; for(const m of blk.matchAll(/\{cap:"([^"]*)",m:\[(.*?)\]\}/g)) mine[m[1]]=[...m[2].matchAll(/\["([^"]*)",(\d+)\]/g)].map(x=>[x[1],+x[2]]);
  const nm=s=>String(s).replace(/#.*$/,'').replace(/\s+/g,'').toLowerCase();
  const apiByCap={}; D.teams.forEach(t=>{ apiByCap[nm(t.cap)]=t.m.map(p=>[nm(p.n),p.price]).sort(); });
  let same=0; for(const cap in mine){ const x=(mine[cap]||[]).map(([n,p])=>[nm(n),p]).sort(); if(JSON.stringify(x)===JSON.stringify(apiByCap[nm(cap)]||[])) same++; }
  ok(same>=8,`내장 제9회 낙찰가와 API 가 ${same}/12팀 그대로 일치(나머지는 닉변·팀장 표기 차이)`);
  const priceSum=a=>a.reduce((s,t)=>s+t.m.reduce((q,p)=>q+(p.price||0),0),0), mineSum=Object.values(mine).flat().reduce((s,x)=>s+x[1],0);
  ok(priceSum(D.teams)===mineSum,`제9회 총 낙찰가 합이 같다(${mineSum})`);
  // 자동 수집
  await A.aucEnsure(); const g=A.AUCGG();
  ok(g.state==='ok'&&g.det.size===3,'경매 3건(22·21·15)만 상세를 받는다 — 드래프트는 안 받음');
  ok(A.aucExtraPrices().length===0,'제9회(내장)만 있으면 적정가 분포에 더할 게 없다');
  ok(!!A.ls()['aucgg_v1']&&JSON.parse(A.ls()['aucgg_v1']).det.length===3,'받은 상세를 캐시에 저장');
  // 새 멸망전이 목록에 생기면 자동으로 분포에 더한다
  const L2={tournaments:[...LIST.tournaments,{id:30,name:'제 10회 멸망전',mode:'AUCTION',createdAt:'2026-11-25T00:00:00.000Z',finishedAt:'2026-12-01T10:00:00.000Z',teamCount:12,champion:null}]};
  const B=make(mk({list:L2})); await B.aucEnsure();
  ok(B.aucMyeolAuctions().length===1&&B.aucExtraPrices().join()==='300,450','제10회 멸망전 낙찰가 300·450 이 분포에 자동 추가');
  ok(/제 10회 멸망전/.test(B.aucCardBody())&&/선수1/.test(B.aucCardBody())&&!/#x/.test(B.aucCardBody()),'카드에 새 대회가 나오고 태그는 안 보인다');
  // 캐시로 부팅 · 네트워크 실패해도 카드는 유지
  const ls=B.ls(); const C=make(mk({fail:true})); // 새 인스턴스는 빈 캐시 → 실패 표시
  await C.aucEnsure(); ok(C.AUCGG().state==='fail'&&/연결하지 못했어요/.test(C.aucCardBody()),'처음부터 실패하면 안내 문구');
  const E=(()=>{ const ls2={...ls}; const f=new Function('fetch','localStorage','document','esc','AbortController','renderMyeol',src.slice(a,b)+';return {AUCGG:()=>AUCGG,aucEnsure,aucExtraPrices,aucCardBody};'); return f(mk({fail:true}),{getItem:k=>ls2[k]??null,setItem:()=>{}},{getElementById:()=>null},esc,AbortController,()=>{}); })();
  await E.aucEnsure(); ok(E.AUCGG().state==='ok'&&E.aucExtraPrices().length===2,'캐시가 있으면 네트워크가 죽어도 이전 값을 그대로 쓴다');
  console.log(fails?'FAIL '+fails:'ALL PASS'); process.exit(fails?1:0);
})();
