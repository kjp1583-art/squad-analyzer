// ⚔️ 제10회 멸망전 자동 화면 시험(2026-11-21): 실제 index.html 을 열고, AUC.GG 응답(가짜 제10회 멸망전)과 가짜 시트 판 몇 개를 넣어
//   명단·파워랭킹 화면이 그려지고(지출·팀장·스크림 승패 반영) 제9회 화면은 그대로인지 본다. 사용: node tests/web_myeol10_test.js
const {chromium}=require('playwright'); const fs=require('fs'), http=require('http'), path=require('path');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) fails++; };
const LIST={tournaments:[{id:30,name:'제 10회 멸망전',mode:'AUCTION',createdAt:'2026-11-25T00:00:00.000Z',finishedAt:'2026-12-01T10:00:00.000Z',teamCount:2,champion:null}]};
const mkp=(n,pos,price)=>({nickname:n,position:pos,tier:'마스터',price,pick:null});
const D30={id:30,name:'제 10회 멸망전',mode:'AUCTION',finishedAt:'2026-12-01T10:00:00.000Z',stages:[],teams:[
 {id:1,name:'가팀',captain:'팀장가#kr1',players:[mkp('가탑','TOP',300),mkp('가정글','JGL',450),mkp('가미드','MID',120),mkp('가원딜','BOT',0)]},
 {id:2,name:'나팀',captain:'팀장나',players:[mkp('나탑','TOP',200),mkp('나정글','JGL',100),mkp('나미드','MID',500),mkp('나원딜','BOT',50)]}]};
const srv=http.createServer((q,r)=>{ const f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); fs.readFile(f,(e,b)=>{ if(e){r.writeHead(404);r.end();return;} r.writeHead(200,{'content-type':f.endsWith('.html')?'text/html; charset=utf-8':f.endsWith('.js')?'text/javascript':'application/octet-stream'}); r.end(b); }); });
srv.listen(0,'127.0.0.1',async()=>{ const port=srv.address().port;
  const b=await chromium.launch({args:['--no-sandbox']}); const pg=await (await b.newContext({viewport:{width:480,height:900}})).newPage(); const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
  await pg.route('https://auc-gg.up.railway.app/**',r=>{ const u=r.request().url(); const h={'access-control-allow-origin':'*'};
    if(u.endsWith('/tournaments')) return r.fulfill({status:200,contentType:'application/json',headers:h,body:JSON.stringify(LIST)});
    r.fulfill({status:200,contentType:'application/json',headers:h,body:JSON.stringify(D30)}); });
  await pg.route(u=>{ const s=u.toString(); return !(s.startsWith('http://127.0.0.1')||s.startsWith('data:'))&&!s.includes('auc-gg'); },r=>r.abort());
  await pg.goto(`http://127.0.0.1:${port}/index.html`); await pg.waitForTimeout(2000);
  const r=await pg.evaluate(async()=>{
    await aucEnsure(true);
    const c=aucMyeolCfg();
    // 가짜 시트: 경매가 끝난(12/01 19:00 KST) 뒤 가탑·가정글·가미드·가원딜·팀장가 vs 나… 한 판 — 가팀 승
    const mk=(gid,day,names,side,res)=>names.map((n,i)=>({"게임ID":gid,"날짜":day,"소환사명":n+"#kr1","진영":side,"결과":res,"포지션":["탑","정글","미드","원딜","서폿"][i],"챔피언":"아리","KDA":"3/2/5","점수":"20"}));
    const A=["가탑","가정글","가미드","가원딜","팀장가"], B=["나탑","나정글","나미드","나원딜","팀장나"];
    const rows=[...mk("#1","2026-12-02 20:00",A,"블루팀","승리"),...mk("#1","2026-12-02 20:00",B,"레드팀","패배")];
    GAMES_ALL=new Map([["#1",{rows}]]);
    _MYEOL_MEMO={seq:-1}; tierOf=n=>'2中';   // 시험용 — 전원 같은 티어(종이 전력이 있는 상태)
    const html=myeolTeamRankHtml(c), ros=myeolRosterHtml(c);
    const S=_myeolScrimsFor(c);
    return {label:c.label, teams:c.teams.length, from:String(c.from), s:S&&S.list.length, rank:html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').slice(0,260), rosterHas:['팀장가','가탑','나정글','450'].map(x=>ros.includes(x)), rosterMain:/본선 <b/.test(ros), p9:myeolRosterHtml().includes('수직낙하하는중')};
  });
  console.log(JSON.stringify(r,null,1));
  ok(r.label==='제10회 멸망전'&&r.teams===2,'새 멸망전이 「제10회 멸망전」·2팀으로 자동 설정');
  ok(r.s===1,'경매가 끝난 뒤의 팀 대 팀 판 1개를 스크림 승패로 읽는다');
  ok(/지출 1,?\d*P?/.test(r.rank)||/지출/.test(r.rank),'파워랭킹에 지출이 나온다');
  ok(r.rank.indexOf('팀장가')>=0&&r.rank.indexOf('1승')>=0,'파워랭킹에 팀과 스크림 1승이 나온다');
  ok(r.rosterHas.every(Boolean),'명단에 팀장·선수·낙찰가가 나온다');
  ok(!r.rosterMain,'제10회 명단엔 제9회식 「본선」 칸이 없다');
  ok(r.p9===true,'제9회(내장) 명단 화면은 그대로 그려진다');
  ok(errs.length===0,'페이지 오류 0 '+errs.slice(0,2));
  console.log(fails?'FAIL '+fails:'ALL PASS'); await b.close(); srv.close(); process.exit(fails?1:0); });
