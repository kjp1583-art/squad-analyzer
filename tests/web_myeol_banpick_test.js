// 🚫 멸망전 「밴픽률」 탭 시험(2026-11-23): 스크림/본선 분리 · 판당 중복 제거 · 빈 상태 · XSS 없음. 사용: node tests/web_myeol_banpick_test.js
const {chromium}=require('playwright'); const fs=require('fs'), http=require('http'), path=require('path');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) fails++; };
const srv=http.createServer((q,r)=>{ const f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); fs.readFile(f,(e,b)=>{ if(e){r.writeHead(404);r.end();return;} r.writeHead(200,{'content-type':f.endsWith('.html')?'text/html; charset=utf-8':'application/octet-stream'}); r.end(b); }); });
srv.listen(0,'127.0.0.1',async()=>{ const port=srv.address().port;
  const b=await chromium.launch({args:['--no-sandbox']}); const pg=await (await b.newContext({viewport:{width:480,height:900}})).newPage(); const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
  await pg.route(u=>{ const s=u.toString(); return !(s.startsWith('http://127.0.0.1')||s.startsWith('data:')); },r=>r.abort());
  await pg.goto(`http://127.0.0.1:${port}/index.html`); await pg.waitForTimeout(2000);
  const r=await pg.evaluate(()=>{
    const T=MYEOL_TEAMS9, A=T[0], B=T[1];
    const names=t=>[t.cap,...t.m.map(x=>x[0])].slice(0,5);
    const mk=(gid,day,t,side,res,champs,ban)=>names(t).map((n,i)=>({"게임ID":gid,"날짜":day,"소환사명":n,"진영":side,"결과":res,"포지션":["탑","정글","미드","원딜","서폿"][i],"챔피언":champs[i],"밴":ban,"KDA":"1/1/1"}));
    const C1=["아트록스","리 신","<img src=x onerror=window.__xss=1>","징크스","레오나"], C2=["제이스","자르반 4세","아리","직스","쓰레쉬"];
    // 스크림 2판(8/25·8/26) + 본선 1판(9/1) — 양 팀 같은 챔피언 밴("뽀삐")은 한 판에 1번만 센다
    const g=[["#s1","2026-08-25 20:00","승리"],["#s2","2026-08-26 20:00","패배"],["#m1","2026-09-01 20:00","승리"]];
    const m=new Map();
    for(const [id,d,res] of g){ const o=res==="승리"?"패배":"승리"; m.set(id,{rows:[...mk(id,d,A,"블루팀",res,C1,"뽀삐"),...mk(id,d,B,"레드팀",o,C2,"뽀삐")]}); }
    GAMES_ALL=m; _MYEOL_MEMO={seq:-1};
    const S=myeolBpStats(null,"scrim"), M=myeolBpStats(null,"main");
    const row=(D,c)=>D.rows.find(x=>x.c===c)||{};
    computeMyeol=()=>({list:[],ladder:[],maxD:"2026-11-23"}); MYEOL_ED=9; MYEOL_VIEW="bp"; MYEOL_BP="scrim"; renderMyeol();
    const t1=document.getElementById('view')?document.getElementById('view').innerText:document.body.innerText;
    const h1=document.body.innerHTML; setMyeolBp("main"); const t2=document.body.innerText;
    return {sn:S&&S.n, mn:M&&M.n, popS:row(S,"뽀삐"), popM:row(M,"뽀삐"), artS:row(S,"아트록스"), jaxS:row(S,"제이스"), views:myeolViewsFor({kind:"builtin"}).map(v=>v[0]).join(),
      t1:t1.replace(/\s+/g,' '), t2:t2.replace(/\s+/g,' '), xss:window.__xss===undefined, imgInj:!!document.querySelector('img[src=x]')};
  });
  console.log(JSON.stringify({sn:r.sn,mn:r.mn,popS:r.popS,popM:r.popM,artS:r.artS},null,0));
  ok(r.sn===2&&r.mn===1,'스크림 2판 · 본선 1판으로 갈라진다');
  ok(r.popS.bn===2&&r.popS.pk===0&&r.popM.bn===1,'양 팀이 같이 밴한 뽀삐도 한 판에 1번만(스크림 2 · 본선 1)');
  ok(r.artS.pk===2&&r.jaxS.pk===2,'픽은 판 수만큼');
  ok(/밴픽률/.test(r.views.replace('bp','밴픽률'))&&/bp/.test(r.views),'하위 탭에 밴픽률(bp)이 있다');
  ok(/Most Picks/.test(r.t1)&&/Most Banned/.test(r.t1)&&/스크림 2판/.test(r.t1)&&/뽀삐/.test(r.t1),'스크림 화면: Most Picks · Most Banned · 2판');
  ok(/본선 1판/.test(r.t2)&&!/스크림 2판/.test(r.t2),'본선으로 바꾸면 본선 1판만');
  ok(r.xss&&!r.imgInj,'챔피언 이름 XSS 없음');
  ok(!errs.length,'페이지 오류 0 '+errs.slice(0,2));
  await b.close(); srv.close(); console.log(fails?'FAIL '+fails:'ALL PASS'); process.exit(fails?1:0); });
