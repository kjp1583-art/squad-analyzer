// 🛡 팀 엠블럼 시험 — index.html 에서 엠블럼 구역만 잘라 돌린다. 사용: node tests/web_emblem_test.js [--shot 출력.png]
const fs=require('fs'), path=require('path'); const src=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
const a=src.indexOf('const EMB_LIM='), b=src.indexOf('/* 🎨 엠블럼 꾸미기 창'); if(a<0||b<0) throw new Error('엠블럼 코드 없음');
const code=src.slice(a,b);
const api=new Function('IDEAL_API','document','fetch',code+';return {teamEmblem,teamEmblemCfg,embCfgOf,_embAssign,EMB_LIM,EMB_FRAMES,EMB_PAL,EMB_ACC,EMB_BORDER,EMB_PATN,getCfg:()=>EMB_CFG,setCfg:v=>{EMB_CFG=v;},clr:()=>_embDef.clear()};')('x',{},async()=>({}));
let bad=0; const ok=(n,c)=>{console.log((c?'  ok   ':'  FAIL ')+n); if(!c)bad++;};
const CAPS=["하 오","허거덩","우 거","택스#tax","지 르","앙앵모르딱","카무사리#귤 갓","해 원","프 싱","SIAH K","뀨잉언진","수직낙하하는중"];
api._embAssign(10,CAPS);
const cf=CAPS.map(c=>api.embCfgOf(c,10));
ok('12팀 문양이 모두 다르다',new Set(cf.map(x=>x.s)).size===12);
ok('12팀 배경색이 모두 다르다',new Set(cf.map(x=>x.c)).size===12);
ok('값이 한도 안에 있다',cf.every(x=>Object.entries(api.EMB_LIM).every(([k,l])=>Number.isInteger(x[k])&&x[k]>=0&&x[k]<l)));
api.clr(); api._embAssign(10,CAPS.slice().reverse()); ok('렌더 순서와 상관없이 같은 배정',JSON.stringify(CAPS.map(c=>api.embCfgOf(c,10)))===JSON.stringify(cf));
ok('태그·공백이 달라도 같은 팀',JSON.stringify(api.embCfgOf('택 스#tax',10))===JSON.stringify(api.embCfgOf('택스',10)));
api.setCfg({"10|하오":{f:2,p:3,s:5,c:1,a:2,b:1}}); ok('저장값이 있으면 그걸 쓴다',api.embCfgOf('하 오',10).s===5&&api.embCfgOf('하 오',10).f===2);
const svg=api.teamEmblem('하 오',40,10); ok('SVG 가 나오고 문양 이미지를 가리킨다',/^<svg/.test(svg)&&/img\/emblem\/s5\.webp/.test(svg));
ok('이름의 꺾쇠가 SVG 로 새지 않는다',!/<script|"><img/i.test(api.teamEmblem('<img onerror=x>"',30,10)));
ok('모든 조합이 SVG 를 만든다',(()=>{ for(let f=0;f<8;f++)for(let p=0;p<10;p++)for(let b2=0;b2<4;b2++){ if(!/^<svg[\s\S]*<\/svg>$/.test(api.teamEmblemCfg({f,p,s:0,c:0,a:0,b:b2},30,''))) return false; } return true; })());
const shot=process.argv.indexOf('--shot');
(async()=>{
  if(shot>0){ const {chromium}=require('playwright'); const br=await chromium.launch(); const pg=await br.newPage({viewport:{width:960,height:560}});
    api.setCfg({}); api.clr(); api._embAssign(10,CAPS);
    const root='file://'+path.join(__dirname,'..')+'/';
    await pg.goto(root+'index.html',{waitUntil:'domcontentloaded'}).catch(()=>{});
    await pg.setContent(`<base href="${root}"><body style="background:#0d1017;color:#ddd;font:13px sans-serif;display:grid;grid-template-columns:repeat(6,1fr);gap:12px;padding:16px">${CAPS.map(n=>`<div style="text-align:center">${api.teamEmblem(n,120,10)}<br>${n}<br>${api.teamEmblem(n,26,10)}</div>`).join("")}</body>`);
    await pg.waitForTimeout(500); await pg.screenshot({path:process.argv[shot+1]}); await br.close(); }
  console.log(bad?'FAILED':'ALL PASS'); process.exit(bad?1:0);
})();
