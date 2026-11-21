// 🛡 팀 엠블럼(코드로 그린 SVG) — index.html 의 「팀 엠블럼」 블록과 같은 코드. 시안 확인용으로 따로 둔 사본이 아니라, 이 파일이 원본이고 index.html 에 붙여 넣는다.
const _EMB_PAL=[
 ["#1d4ed8","#60a5fa","#e0f2fe"],["#b91c1c","#f87171","#fee2e2"],["#6d28d9","#a78bfa","#ede9fe"],["#c2410c","#fb923c","#ffedd5"],
 ["#047857","#34d399","#d1fae5"],["#be185d","#f472b6","#fce7f3"],["#111827","#6b7280","#f3f4f6"],["#0e7490","#22d3ee","#cffafe"],
 ["#a16207","#facc15","#fef9c3"],["#1e3a8a","#38bdf8","#e0f2fe"],["#0f766e","#5eead4","#ccfbf1"],["#7e22ce","#e879f9","#fae8ff"]];
// 아이콘 — 0~100 좌표, 밝은 색(c) 채움 + 어두운 선(d). 전부 직접 그린 도형이다.
const _EMB_ICO=[
 (c,d)=>`<path d="M56 10 28 54h18l-6 36 32-48H52z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/>`,   // 0 번개
 (c,d)=>`<path d="M16 72 12 34l20 18 18-28 18 28 20-18-4 38z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><rect x="16" y="72" width="68" height="9" rx="2" fill="${c}" stroke="${d}" stroke-width="3"/><circle cx="12" cy="32" r="4" fill="${c}" stroke="${d}" stroke-width="2.5"/><circle cx="50" cy="20" r="4.5" fill="${c}" stroke="${d}" stroke-width="2.5"/><circle cx="88" cy="32" r="4" fill="${c}" stroke="${d}" stroke-width="2.5"/>`,   // 1 왕관
 (c,d)=>`<path d="M50 24c-6 10-18 14-40 14 8 6 14 10 26 10-6 4-12 6-22 6 12 8 26 8 36-2z M50 24c6 10 18 14 40 14-8 6-14 10-26 10 6 4 12 6 22 6-12 8-26 8-36-2z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M50 20l7 14-7 44-7-44z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/>`,   // 2 날개
 (c,d)=>{ let t=""; for(let i=0;i<8;i++){ const a=i*45*Math.PI/180; t+=`<rect x="44" y="9" width="12" height="17" rx="2" fill="${c}" stroke="${d}" stroke-width="2.5" transform="rotate(${i*45} 50 50)"/>`; }
   return t+`<circle cx="50" cy="50" r="29" fill="${c}" stroke="${d}" stroke-width="3"/><circle cx="50" cy="50" r="12" fill="${d}"/>`; },   // 3 톱니
 (c,d)=>`<path d="M50 8c4 14 22 22 22 44a22 22 0 0 1-44 0c0-10 6-14 8-22 4 6 6 8 10 8-2-12 0-22 4-30z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M50 50c3 8 10 11 10 20a10 10 0 0 1-20 0c0-6 6-10 10-20z" fill="${d}" opacity=".55"/>`,   // 4 불꽃
 (c,d)=>`<path d="M62 12A38 38 0 1 0 88 62 30 30 0 0 1 62 12z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M78 20l4 9 10 1-8 7 3 10-9-6-9 6 3-10-8-7 10-1z" fill="${c}" stroke="${d}" stroke-width="2.5" stroke-linejoin="round"/>`,   // 5 달과 별
 (c,d)=>`<path d="M50 12C30 12 18 26 18 44c0 10 4 16 10 20v12h44V64c6-4 10-10 10-20 0-18-12-32-32-32z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><ellipse cx="37" cy="46" rx="8" ry="10" fill="${d}"/><ellipse cx="63" cy="46" rx="8" ry="10" fill="${d}"/><path d="M50 54l-5 10h10z" fill="${d}"/><path d="M38 76v-8M46 76v-8M54 76v-8M62 76v-8" stroke="${d}" stroke-width="3" stroke-linecap="round"/>`,   // 6 해골
 (c,d)=>`<circle cx="50" cy="17" r="8" fill="none" stroke="${c}" stroke-width="6"/><path d="M50 25v58M32 40h36" stroke="${c}" stroke-width="7" stroke-linecap="round"/><path d="M14 58c4 20 20 28 36 28s32-8 36-28" fill="none" stroke="${c}" stroke-width="7" stroke-linecap="round"/><path d="M8 62l9-12 6 14zM92 62l-9-12-6 14z" fill="${c}"/>`,   // 7 닻
 (c,d)=>`<path d="M50 6c4 10 14 14 14 28 0 6-4 10-8 14 8-2 14-8 14-8 4 16-4 30-20 42-16-12-24-26-20-42 0 0 6 6 14 8-4-4-8-8-8-14 0-14 10-18 14-28z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M12 36c10 2 20 10 24 26-10-2-20-10-24-26zM88 36c-10 2-20 10-24 26 10-2 20-10 24-26z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/>`,   // 8 불사조
 (c,d)=>`<path d="M16 8l22 20h24l22-20 2 40c0 22-14 34-36 42C28 82 14 70 14 48z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M26 44l16 6-4 8zM74 44l-16 6 4 8z" fill="${d}"/><path d="M42 74h16l-8 8z" fill="${d}"/>`,   // 9 표범/고양이 머리
 (c,d)=>`<path d="M50 6 88 40 50 94 12 40z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M12 40h76M30 40 50 6l20 34M30 40l20 54 20-54" fill="none" stroke="${d}" stroke-width="2.5" stroke-linejoin="round" opacity=".65"/>`,   // 10 보석
 (c,d)=>`<path d="M82 10 30 56l10 8z" fill="${c}" opacity=".5"/><path d="M92 6 38 52l14 12z" fill="${c}" stroke="${d}" stroke-width="2.5" stroke-linejoin="round"/><circle cx="38" cy="68" r="22" fill="${c}" stroke="${d}" stroke-width="3"/><circle cx="31" cy="62" r="5" fill="${d}" opacity=".5"/><circle cx="46" cy="76" r="4" fill="${d}" opacity=".5"/>`,   // 11 유성
 (c,d)=>`<path d="M14 10l24 18h24l24-18-6 36c-2 20-14 34-30 44C34 80 22 66 20 46z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M30 46l14 4-2 8zM70 46 56 50l2 8z" fill="${d}"/><path d="M44 66l6 8 6-8z" fill="${d}"/>`,   // 12 늑대 머리
 (c,d)=>`<path d="M10 14l26 16h28l26-16-4 32-22 40H36L14 46z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/><path d="M28 44l18 6-6 8zM72 44 54 50l6 8z" fill="${d}"/><path d="M50 62l-5 9h10z" fill="${d}"/><path d="M42 80h16" stroke="${d}" stroke-width="3" stroke-linecap="round"/>`,   // 13 여우 머리
 (c,d)=>`<path d="M20 12 80 78M80 12 20 78" stroke="${c}" stroke-width="8" stroke-linecap="round"/><path d="M14 8l14 4-4 14zM86 8 72 12l4 14z" fill="${c}"/><path d="M22 74l-8 10 12-2zM78 74l8 10-12-2z" fill="${c}"/><path d="M20 12 80 78M80 12 20 78" stroke="${d}" stroke-width="2" stroke-linecap="round" opacity=".55"/>`,   // 14 교차 검
 (c,d)=>`<path d="M50 8l12 26 28 4-20 20 5 28-25-14-25 14 5-28L10 38l28-4z" fill="${c}" stroke="${d}" stroke-width="3" stroke-linejoin="round"/>`,   // 15 별
];
const _EMB_FRAME=[
 {p:"M50 4 92 16v34c0 24-18 38-42 46C26 88 8 74 8 50V16z",ix:0,iy:4},   // 방패
 {p:"M50 3 90 26v48L50 97 10 74V26z",ix:0,iy:0},                     // 육각
 {p:"M50 4a46 46 0 1 1 0 92A46 46 0 0 1 50 4z",ix:0,iy:0},          // 원형
 {p:"M10 8h80v50c0 20-18 30-40 38C28 88 10 78 10 58z",ix:0,iy:2},   // 평평한 방패
];
const _EMB_MAP={"하오":[0,0,0],"허거덩":[1,3,1],"우거":[2,1,2],"택스":[3,0,3],"지르":[4,1,4],"앙앵모르딱":[5,2,5],"카무사리":[6,0,6],"해원":[7,3,7],"프싱":[8,1,8],"siahk":[9,3,9],"뀨잉언진":[10,2,10],"수직낙하하는중":[11,0,11]};
let _embN=0;
function _embHash(s){ let h=2166136261; for(const ch of String(s)){ h^=ch.charCodeAt(0); h=Math.imul(h,16777619)>>>0; } return h; }
function teamEmblem(name,size){
  const k=String(name||"").replace(/#.*$/,"").replace(/[\s·.\-_]/g,"").toLowerCase();
  const m=_EMB_MAP[k]||(()=>{ const h=_embHash(k); return [h%_EMB_ICO.length,(h>>>5)%_EMB_FRAME.length,(h>>>9)%_EMB_PAL.length]; })();
  const [ic,fr,pl]=m, P=_EMB_PAL[pl], F=_EMB_FRAME[fr], id="emb"+(++_embN);
  const sz=size||28;
  return `<svg class="emb" viewBox="0 0 100 100" width="${sz}" height="${sz}" role="img" aria-label="${String(name||"").replace(/[<>"&]/g,"")} 엠블럼"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${P[1]}"/><stop offset="1" stop-color="${P[0]}"/></linearGradient></defs><path d="${F.p}" fill="url(#${id})" stroke="#e8eaf0" stroke-width="4" stroke-linejoin="round"/><path d="${F.p}" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="1.5" transform="translate(50 50) scale(.86) translate(-50 -50)"/><g transform="translate(50 ${50+F.iy}) scale(.6) translate(-50 -50)">${_EMB_ICO[ic](P[2],P[0])}</g></svg>`;
}
if(typeof module!=="undefined") module.exports={teamEmblem};
