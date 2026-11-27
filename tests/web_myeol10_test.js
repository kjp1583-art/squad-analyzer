// ⚔️ 제10회 멸망전 자동 화면 시험(2026-11-21): 실제 index.html 을 열고, AUC.GG 응답(가짜 제10회 멸망전)과 가짜 시트 판 몇 개를 넣어
//   명단·파워랭킹 화면이 그려지고(지출·팀장·스크림 승패 반영) 제9회 화면은 그대로인지 본다. 사용: node tests/web_myeol10_test.js
const {chromium}=require('playwright'); const fs=require('fs'), http=require('http'), path=require('path');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) fails++; };
const LIST={tournaments:[{id:30,name:'제 10회 멸망전',mode:'AUCTION',createdAt:'2026-11-20T00:00:00.000Z',finishedAt:'2026-11-25T10:00:00.000Z',teamCount:2,champion:null}]};
const mkp=(n,pos,price)=>({nickname:n,position:pos,tier:'마스터',price,pick:null});
const D30={id:30,name:'제 10회 멸망전',mode:'AUCTION',finishedAt:'2026-11-25T10:00:00.000Z',stages:[],teams:[
 {id:1,name:'가팀',captain:'팀장가#kr1',players:[mkp('가탑','TOP',300),mkp('가정글','JGL',450),mkp('가미드','MID',120),mkp('가원딜','BOT',0)]},
 {id:2,name:'나팀',captain:'팀장나',players:[mkp('나탑','TOP',200),mkp('나정글','JGL',100),mkp('나미드','MID',500),mkp('나원딜','BOT',50)]},
 {id:3,name:'다팀',captain:'팀장다',players:[mkp('다1','TOP',10),mkp('다2','MID',20),mkp('다미드','MID',30),mkp('다원딜','BOT',40)]}]};
const srv=http.createServer((q,r)=>{ const f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); fs.readFile(f,(e,b)=>{ if(e){r.writeHead(404);r.end();return;} r.writeHead(200,{'content-type':f.endsWith('.html')?'text/html; charset=utf-8':f.endsWith('.js')?'text/javascript':'application/octet-stream'}); r.end(b); }); });
srv.listen(0,'127.0.0.1',async()=>{ const port=srv.address().port;
  const b=await chromium.launch({args:['--no-sandbox']}); const pg=await (await b.newContext({viewport:{width:480,height:900}})).newPage(); const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
  await pg.route('https://auc-gg.up.railway.app/**',r=>{ const u=r.request().url(); const h={'access-control-allow-origin':'*'};
    if(u.endsWith('/tournaments')) return r.fulfill({status:200,contentType:'application/json',headers:h,body:JSON.stringify(LIST)});
    r.fulfill({status:200,contentType:'application/json',headers:h,body:JSON.stringify(D30)}); });
  await pg.route(u=>{ const s=u.toString(); return !(s.startsWith('http://127.0.0.1')||s.startsWith('data:'))&&!s.includes('auc-gg'); },r=>r.abort());
  await pg.goto(`http://127.0.0.1:${port}/index.html`); await pg.waitForTimeout(2000);
  const r=await pg.evaluate(async()=>{
    const preE=myeolEditions().map(e=>e.no+':'+e.kind).join(), preV=myeolViewsFor(myeolEditions()[0]).map(v=>v[0]).join();
    await aucEnsure(true);
    const c=aucMyeolCfg();
    const postE=myeolEditions().map(e=>e.no+':'+e.kind+(e.latest?'*':'')).join(), postV=myeolViewsFor(myeolEditions()[0]).map(v=>v[0]).join(), v9=myeolViewsFor(myeolEditions()[1]).map(v=>v[0]).join();
    // 가짜 시트: 경매가 끝난(11/25 19:00 KST) 뒤 · 본선 개막(11/28 19:00) 전 가탑·가정글·가미드·가원딜·팀장가 vs 나… 한 판 — 가팀 승
    const mk=(gid,day,names,side,res)=>names.map((n,i)=>({"게임ID":gid,"날짜":day,"소환사명":n+"#kr1","진영":side,"결과":res,"포지션":["탑","정글","미드","원딜","서폿"][i],"챔피언":"아리","KDA":"3/2/5","점수":"20"}));
    const A=["가탑","가정글","가미드","가원딜","팀장가"], B=["나탑","나정글","나미드","나원딜","팀장나"];
    const rows=[...mk("#1","2026-11-26 20:00",A,"블루팀","승리"),...mk("#1","2026-11-26 20:00",B,"레드팀","패배")];
    GAMES_ALL=new Map([["#1",{rows}]]);
    _MYEOL_MEMO={seq:-1}; tierOf=n=>'2中';   // 시험용 — 전원 같은 티어(종이 전력이 있는 상태)
    const html=myeolTeamRankHtml(c), ros=myeolRosterHtml(c);
    const S=_myeolScrimsFor(c);

    // ── 봇듀오·미드정글 자동 라인업 ──
    const duo1=aucDuoList(c,'bot'), mj1=aucDuoList(c,'mj');
    const g1=duo1.filter(d=>d.t==='팀장가'), n1=duo1.filter(d=>d.t==='팀장나'), d1=duo1.filter(d=>d.t==='팀장다'), mjd=mj1.filter(d=>d.t==='팀장다');
    // 두 번째 같은 라인업 판을 더해 「실측」으로 덮이는지
    const rows2=[...mk("#2","2026-11-27 20:00",A,"블루팀","승리"),...mk("#2","2026-11-27 20:00",B,"레드팀","패배")];
    GAMES_ALL=new Map([["#1",{rows}],["#2",{rows:rows2}]]); _MYEOL_MEMO={seq:-1};
    const duo2=aucDuoList(c,'bot');
    const html2=myeolBotDuoHtml(c), mjHtml=myeolMidJglHtml(c), scr=myeolScrimHtml(c);
    const grp=myeolGroups10Html(c);
    SCRIM_SEL={ed:10,k:_myNk('팀장가'),cap:'팀장가'}; const scrSel=myeolScrimHtml(c).replace(/<[^>]+>/g,' ').replace(/\s+/g,' '); SCRIM_SEL=null;
    return {scrSel:scrSel.slice(0,400), grp:grp.replace(/<[^>]+>/g,' ').replace(/\s+/g,' '), grpN:(grp.match(/class="gt-card"/g)||[]).length, eds:{preE,preV,postE,postV,v9}, duo:{g1,n1,d1,mjd,real:duo2.filter(d=>d.t==='팀장가'),html2:html2.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').slice(0,300),mj:mjHtml.includes('팀장가')||mjHtml.includes('가정글'),scr:scr.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').slice(0,200)}, label:c.label, teams:c.teams.length, from:String(c.from), s:S&&S.list.length, rank:html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').slice(0,260), rosterHas:['팀장가','가탑','나정글','450'].map(x=>ros.includes(x)), rosterMain:/본선 <b/.test(ros), p9:myeolRosterHtml().includes('수직낙하하는중')};
  });
  console.log(JSON.stringify(r,null,1));
  ok(r.label==='제10회 멸망전'&&r.teams===3,'새 멸망전이 「제10회 멸망전」·3팀으로 자동 설정');

  ok(r.eds.preE==='10:upcoming,9:builtin'&&r.eds.preV==='auction,price','경매 전: 상위 탭 「제10회(예정)·제9회」 — 하위 탭은 경매결과·적정가뿐');
  ok(r.eds.postE==='10:auc*,9:builtin'&&r.eds.postV==='auction,rank,scrim,bp,main,price','경매 결과가 올라오면: 제10회가 최신이 되고 경매결과·파워랭킹·스크림·적정가 탭이 생긴다');
  ok(r.eds.v9==='auction,rank,scrim,bp,main','제9회 하위 탭: 경매결과·파워랭킹·스크림·본선(적정가는 최신 회차만)');
  const D=r.duo;
  ok(D.g1.length===1&&D.g1[0].ad==='가원딜'&&D.g1[0].sup==='팀장가'&&D.g1[0].note==='경매 포지션 기준','팀 가: 선수 4명의 포지션으로 팀장=서폿을 추리고 봇듀오 확정');
  ok(D.n1.length===1&&D.n1[0].sup==='팀장나','팀 나: 같은 방식으로 확정');
  ok(D.d1.length===1&&D.d1[0].sup==='팀장다'&&D.d1[0].note==='팀장 자리 미확정','팀 다: 팀장 자리가 둘(정글·서폿)이면 미확정 표기, 가능한 조합만 남긴다');
  ok(D.mjd.length===2&&D.mjd.every(d=>d.sup==='팀장다'),'팀 다 미드·정글: 미드가 2명이면 경우의수 2개('+D.mjd.length+')');
  ok(D.real.length===1&&D.real[0].note==='실측 2판'&&D.real[0].ad==='가원딜','같은 라인업 판이 2번 있으면 「실측 2판」으로 바뀐다');
  ok(/팀장가/.test(D.html2)&&/가원딜/.test(D.html2),'봇듀오 화면에 이름이 나온다');
  ok(D.mj===true,'미드·정글 화면도 그려진다');
  ok(/팀장가/.test(D.scr)&&/승/.test(D.scr),'스크림 전적 목록에 팀과 승이 나온다');
  ok(r.grpN===3&&/A조/.test(r.grp)&&/B조/.test(r.grp)&&/C조/.test(r.grp)&&/개막 전/.test(r.grp),'제10회 본선 조편성이 A·B·C조 3칸으로 그려진다(개막 전)');
  ok(/팀장가 스크림 기록/.test(r.scrSel)&&/2경기 2승 0패/.test(r.scrSel)&&/전체 보기/.test(r.scrSel),'스크림 순위표에서 팀을 고르면 그 팀 경기만 나온다(2경기 2승 0패 · 전체 보기 버튼)');
  ok(r.s===1,'경매가 끝난 뒤의 팀 대 팀 판 1개를 스크림 승패로 읽는다');
  ok(/지출 1,?\d*P?/.test(r.rank)||/지출/.test(r.rank),'파워랭킹에 지출이 나온다');
  ok(r.rank.indexOf('팀장가')>=0&&/1 - 0/.test(r.rank),'파워랭킹에 팀과 스크림 1승이 나온다');
  ok(r.rosterHas.every(Boolean),'명단에 팀장·선수·낙찰가가 나온다');
  ok(!r.rosterMain,'제10회 명단엔 제9회식 「본선」 칸이 없다');
  ok(r.p9===true,'제9회(내장) 명단 화면은 그대로 그려진다');
  ok(errs.length===0,'페이지 오류 0 '+errs.slice(0,2));
  console.log(fails?'FAIL '+fails:'ALL PASS'); await b.close(); srv.close(); process.exit(fails?1:0); });
