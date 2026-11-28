// 🏳️ 멸망전 본선 몰수 경기(MYEOL_FORFEITS) 시험(2026-11-28): 판 기록이 없어도 조별 승패표에 「승/패 · 몰수」로 들어가고
//   팀 페이지 경기 일정에 눌리지 않는 「몰수」 줄로 뜨는지 본다. 사용: node tests/web_myeol_forfeit_test.js
const {chromium}=require('playwright'); const fs=require('fs'), http=require('http'), path=require('path');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ console.log((c?'  ok   ':'  FAIL ')+m); if(!c) fails++; };
const LIST={tournaments:[{id:30,name:'제 10회 멸망전',mode:'AUCTION',createdAt:'2026-11-20T00:00:00.000Z',finishedAt:'2026-11-25T10:00:00.000Z',teamCount:4,champion:null}]};
const mkp=(n,pos)=>({nickname:n,position:pos,tier:'마스터',price:100,pick:null});
const T=(id,cap)=>({id,name:cap+'팀',captain:cap,players:['TOP','JGL','MID','BOT'].map((p,i)=>mkp(cap+'_'+i,p))});
const D30={id:30,name:'제 10회 멸망전',mode:'AUCTION',finishedAt:'2026-11-25T10:00:00.000Z',stages:[],teams:[T(1,'카무사리'),T(2,'해 원'),T(3,'프 싱'),T(4,'뀨잉언진')]};
const srv=http.createServer((q,r)=>{ const f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); fs.readFile(f,(e,b)=>{ if(e){r.writeHead(404);r.end();return;} r.writeHead(200,{'content-type':f.endsWith('.html')?'text/html; charset=utf-8':'application/octet-stream'}); r.end(b); }); });
srv.listen(0,'127.0.0.1',async()=>{ const port=srv.address().port;
  const b=await chromium.launch({args:['--no-sandbox']}); const pg=await (await b.newContext({viewport:{width:1100,height:900}})).newPage(); const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
  await pg.route('https://auc-gg.up.railway.app/**',r=>{ const u=r.request().url(); const h={'access-control-allow-origin':'*'};
    r.fulfill({status:200,contentType:'application/json',headers:h,body:JSON.stringify(u.endsWith('/tournaments')?LIST:D30)}); });
  await pg.route(u=>{ const s=u.toString(); return !(s.startsWith('http://127.0.0.1')||s.startsWith('data:'))&&!s.includes('auc-gg'); },r=>r.abort());
  await pg.goto(`http://127.0.0.1:${port}/index.html`); await pg.waitForTimeout(2000);
  const r=await pg.evaluate(async()=>{
    await aucEnsure(true); const c=aucMyeolCfg();
    const mk=(gid,day,cap,side,res)=>[cap,...[0,1,2,3].map(i=>cap+'_'+i)].map((n,i)=>({"게임ID":gid,"날짜":day,"소환사명":n+"#kr1","진영":side,"결과":res,"포지션":["탑","정글","미드","원딜","서폿"][i],"챔피언":"아리","KDA":"3/2/5","점수":"20"}));
    GAMES_ALL=new Map([["#1",{rows:[...mk("#1","2026-11-26 20:00","카무사리","블루팀","승리"),...mk("#1","2026-11-26 20:00","해 원","레드팀","패배")]}]]);
    _MYEOL_MEMO={seq:-1}; tierOf=n=>'2中';
    const grp=myeolGroups10Html(c);
    const d=document.createElement('div'); d.innerHTML=grp; const cC=[...d.querySelectorAll('.gt-card')].find(x=>/C조/.test(x.textContent));
    const row=n=>[...cC.querySelectorAll('tr')].find(tr=>(tr.querySelector('th.gt-tm')||{}).textContent?.includes(n));
    const kk=row('뀨잉언진'), ps=row('프 싱');
    go('team','10|뀨잉언진'); await new Promise(z=>setTimeout(z,400)); const tp=document.querySelector('.tp-mw')?.innerHTML||'';
    go('team','10|프 싱'); await new Promise(z=>setTimeout(z,400)); const tp2=document.querySelector('.tp-mw')?.innerHTML||'';
    return {v:(view().textContent||'').replace(/\s+/g,' ').slice(0,300),kk:kk&&kk.textContent.replace(/\s+/g,' '), ps:ps&&ps.textContent.replace(/\s+/g,' '), tp, tp2};
  });
  ok(r.kk&&/승 몰수/.test(r.kk)&&/1-0/.test(r.kk),'뀨잉언진 줄: 프 싱 상대 「승 몰수」 · 1-0 — '+r.kk);
  ok(r.ps&&/패 몰수/.test(r.ps)&&/0-1/.test(r.ps),'프 싱 줄: 뀨잉언진 상대 「패 몰수」 · 0-1 — '+r.ps);
  ok(/몰수/.test(r.tp)&&!/onclick="go\('vs','10\|ff:/.test(r.tp),'뀨잉언진 팀 페이지 경기 일정에 몰수 줄(눌리지 않음)');
  ok(/몰수/.test(r.tp2)&&/tp-m l/.test(r.tp2),'프 싱 팀 페이지엔 패배로');
  ok(errs.length===0,'페이지 오류 0 '+errs.join(' | '));
  await b.close(); srv.close(); console.log(fails?`FAIL ${fails}`:'ALL OK'); process.exit(fails?1:0);
});
