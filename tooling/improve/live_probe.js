// 라이브 웹 폰 화면 측정(루프 도구 · 2026-11-24). 사용: HASHES='#home,#hof' SIZES=360x780 NODE_PATH=$(npm root -g) node live_probe.js
// 브라우저는 TLS 검증을 끄지 않는다 — 요청마다 curl(--cacert /root/.ccr/ca-bundle.crt)로 받아 page.route 로 채워 준다.
const {chromium}=require('playwright');const {execFileSync}=require('child_process');
function fetchCurl(url,method,body,headers){
  const args=['-sS','--max-time','40','--cacert','/root/.ccr/ca-bundle.crt','-i','-X',method||'GET'];
  for(const [k,v] of Object.entries(headers||{})){ if(/^(host|content-length|accept-encoding|connection)$/i.test(k)) continue; args.push('-H',`${k}: ${v}`);} 
  if(body) args.push('--data-binary',body);
  args.push(url);
  const out=execFileSync('curl',args,{maxBuffer:200*1024*1024});
  // 마지막 응답 헤더 블록 분리(리다이렉트·100-continue 대비)
  let buf=out, idx;
  while(true){ const sep=buf.indexOf('\r\n\r\n'); if(sep<0) break; const head=buf.slice(0,sep).toString('latin1'); const m=head.match(/^HTTP\/[\d.]+ (\d+)/); if(m&&(+m[1]===100||/Connection established/i.test(head.split('\r\n')[0])||(+m[1]>=300&&+m[1]<400&&/\nlocation:/i.test(head)))){buf=buf.slice(sep+4);continue;} const status=+m[1]; const hdrs={}; head.split('\r\n').slice(1).forEach(l=>{const i=l.indexOf(':'); if(i>0) hdrs[l.slice(0,i).toLowerCase()]=l.slice(i+1).trim();}); delete hdrs['transfer-encoding']; delete hdrs['content-encoding']; delete hdrs['content-length']; return {status,hdrs,body:buf.slice(sep+4)}; }
  return {status:502,hdrs:{},body:Buffer.from('')};
}
(async()=>{
  const b=await chromium.launch();
  const HASHES=(process.env.HASHES||'').split(',');const SIZES=process.env.SIZES?process.env.SIZES.split(',').map(x=>x.split('x').map(Number)):[[360,780],[390,844],[412,915],[1280,800]];
  for(const hs of HASHES) for(const [w,h] of SIZES){
    const ctx=await b.newContext({viewport:{width:w,height:h}});const pg=await ctx.newPage();
    await pg.route('**/*',async r=>{const q=r.request();const u=q.url();
      if(u.startsWith('data:')||u.startsWith('blob:')) return r.continue();
      try{const f=fetchCurl(u,q.method(),q.postData(),q.headers());await r.fulfill({status:f.status,headers:f.hdrs,body:f.body});}catch(e){await r.abort();}});
    await pg.goto('https://kjp1583-art.github.io/squad-analyzer/'+hs,{waitUntil:'domcontentloaded',timeout:60000});
    await pg.waitForTimeout(12000);
    const v=await pg.evaluate(()=>{const t=document.getElementById('tabswrap')||document.querySelector('.tabs');const r=t?t.getBoundingClientRect():null;return {tabsBottom:r?Math.round(r.bottom+scrollY):null,sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,docH:document.documentElement.scrollHeight}});
    console.log(hs||'(home)',w,h,JSON.stringify(v),'screens',(v.docH/h).toFixed(1));await ctx.close();}
  await b.close();
})().catch(e=>{console.error('ERR',e.message);process.exit(1)});
