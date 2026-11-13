/* 🏺 브장신 키우기(웹) 「유물」 창 — 유물 장비 · 어빌리티 · 고유 장비 · 일일 던전 2종 · 재화 상점 (2026-11-13)
   서버: bot.py BRJ2:RELIC (/brj/rl_*). 이 파일은 brjhunt.html 의 전역(V·act·say·snd·esc·fmt·N·R·render)을 호출 시점에 쓴다 — 새 코드를 한 곳에 모아 다른 갈래와 충돌하지 않게 했다.
   그림이 아직 없다(OpenAI 이미지 크레딧 소진) → 이모지로 그린다. 나중에 그림으로 바꿀 때는 아래 ART 표 한 곳만 고치면 된다.
   brjhunt.html 에서 쓰는 것: BrjRelic.tab() (창 본문) · BrjRelic.DO (버튼 핸들러) · BrjRelic.fx() (스킬 쿨다운 감소 %) */
(function(){
'use strict';
const ART={   // 키 → 이모지(또는 나중에 <img> 경로로 바꿀 자리). cur: 재화, rar: 유물 등급, abi: 어빌리티 등급
  cur:{coin:'🏺',crystal:'🔮',dust:'✨'},
  rar:['⚪','🟣','🟠','🔴'],
  tab:'🏺'
};
const RAR_C=['#8fa3b8','#b36cff','#ff9d2e','#ff4f6b'], ABI_C=['#8fa3b8','#b36cff','#ffb02e','#43d17a'];
const ST={sub:'relic',sel:null,res:null,lock:null,mergeSlot:'crown'};
const SUBS=[['relic','🏺 유물'],['abi','🔮 어빌리티'],['uq','🌟 고유'],['dun','⛏ 던전'],['shop','🛒 상점']];
const g=n=>window[n];
const esc_=s=>(typeof esc==='function')?esc(s):String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{ const x=Number(v); return Number.isFinite(x)?x:0; };
const fm=v=>(typeof fmt==='function')?fmt(v):String(Math.round(num(v)).toLocaleString('ko-KR'));
const RV=()=>{ const v=(typeof V!=='undefined'&&V)?V.relic:null; return v&&typeof v==='object'&&Array.isArray(v.slots)?v:null; };
function injectCss(){
  if(document.getElementById('rlcss')) return;
  const s=document.createElement('style'); s.id='rlcss';
  s.textContent=`
.rl-sub{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.rl-sub button{flex:1 1 auto;min-width:70px;border:2px solid var(--line);background:var(--panel2);color:var(--text);border-radius:10px;padding:8px 6px;font-weight:900;font-size:13px;cursor:pointer}
.rl-sub button.on{border-color:var(--gold);box-shadow:0 0 10px var(--glow)}
.rl-slots{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0}
.rl-slot{border:2px dashed var(--line);border-radius:12px;padding:8px 4px;text-align:center;background:var(--panel2);min-height:92px;font-size:12px}
.rl-slot.has{border-style:solid}
.rl-ic{font-size:30px;line-height:1.1}
.rl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:8px;margin-top:8px}
.rl-it{border:2px solid var(--line);border-radius:12px;padding:6px;text-align:center;background:var(--panel2);cursor:pointer;font-size:12px;color:var(--text);position:relative}
.rl-it.sel{outline:3px solid var(--gold);outline-offset:1px}
.rl-it .lk{position:absolute;top:2px;right:4px;font-size:11px}
.rl-it .eqm{position:absolute;top:2px;left:4px;font-size:10px;font-weight:900;color:var(--gold)}
.rl-line{display:flex;justify-content:space-between;align-items:center;gap:8px;border:2px solid var(--line);border-radius:10px;padding:8px 10px;margin:6px 0;background:var(--panel2);font-weight:800}
.rl-line.lk{border-color:var(--gold)}
.rl-line .g{font-size:11px;font-weight:900;padding:1px 7px;border-radius:99px;border:1px solid currentColor}
.rl-cmp{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media(max-width:520px){.rl-cmp{grid-template-columns:1fr}}
.rl-res{border:2px solid var(--gold);border-radius:12px;padding:8px;margin:8px 0;background:var(--panel2)}
.rl-tier{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.rl-tier .btn{flex:1 1 90px}
.rl-shop{display:flex;justify-content:space-between;align-items:center;gap:8px;border:2px solid var(--line);border-radius:10px;padding:8px 10px;margin:6px 0;background:var(--panel2)}
.rl-shop .d{font-size:11.5px;color:var(--sub)}
`;
  document.head.appendChild(s);
}
const cur=k=>ART.cur[k]||'';
function head(v){
  return `<div class="card"><h2>${ART.tab} 유물 <span class="pill gold">${cur('coin')} ${fm(v.coin)}</span> <span class="pill">${cur('crystal')} ${fm(v.crystal)}</span> <span class="pill">${cur('dust')} ${fm(v.dust)}</span></h2>
  <div class="sub">유물·어빌리티·고유 장비는 일반 장비와 <b>따로</b> 더해져요. 🏺 주화는 <b>유물 발굴지</b>에서, 🔮 수정은 <b>수정굴</b>에서 <b>하루 1번씩</b> 깨고 얻어요(보상도 넉넉해요).</div>
  <div class="rl-sub" role="tablist">${SUBS.map(([k,n])=>`<button role="tab" aria-selected="${ST.sub===k}" class="${ST.sub===k?'on':''}" data-do="rlsub" data-sub="${k}">${n}</button>`).join('')}</div></div>`;
}
function bonusLine(v){
  const b=v.bonus||{}, p=b.pct||{}, a=b.add||{}, f=v.fx||{}, nm={atk:'공격력',hp:'체력',def:'방어력',acc:'명중',crit:'치명타',critdmg:'치명피해'}, o=[];
  Object.keys(p).forEach(k=>{ if(num(p[k])>0) o.push(`${nm[k]||k} +${num(p[k])}%`); });
  Object.keys(a).forEach(k=>{ if(num(a[k])>0) o.push(`${nm[k]||k} +${num(a[k])}%p`); });
  const fn={cd:'쿨다운 -',gold:'처치 골드 +',elite:'엘리트 충전 +',boss:'보스·던전 피해 +',skill:'스킬 피해 +'};
  Object.keys(f).forEach(k=>{ if(num(f[k])>0) o.push(`${fn[k]||k}${num(f[k])}%`); });
  return o.length?`<div class="pillrow" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">${o.map(t=>`<span class="pill">${esc_(t)}</span>`).join('')}</div>`:`<div class="mut" style="margin-top:6px">아직 이 창에서 받는 보너스가 없어요.</div>`;
}
function itemBox(it,eq,sel){
  const c=RAR_C[Math.max(0,Math.min(3,num(it.rar)))];
  return `<button class="rl-it ${sel?'sel':''}" style="border-color:${c}" data-do="rlsel" data-id="${esc_(it.id)}" aria-label="${esc_(it.name)} ${esc_(it.rar_name)} +${num(it.lv)}">${eq?'<span class="eqm">장착</span>':''}${it.lock?'<span class="lk">🔒</span>':''}<div class="rl-ic">${esc_(it.emoji)}</div><div style="font-weight:900;color:${c}">${esc_(it.rar_name)} +${num(it.lv)}</div><div>${esc_(it.name)}</div><div class="mut">${esc_(it.stat_name)} +${num(it.val)}${it.kind==='pct'?'%':'%p'}</div></button>`;
}
function valTxt(it){ return `${esc_(it.stat_name)} +${num(it.val)}${it.kind==='pct'?'%':'%p'}`; }
function resHtml(){
  if(!ST.res) return '';
  const r=ST.res, o=[];
  (r.relics||[]).forEach(x=>{ const it=x.item||{}; o.push(`<span style="color:${RAR_C[num(it.rar)]||'inherit'}">${esc_(it.emoji)} ${esc_(it.rar_name)} ${esc_(it.name)}${x.scrapped?' (가득 차서 분해)':''}</span>`); });
  (r.unique||[]).forEach(x=>{ const i=x.info||{}; o.push(`<b style="color:#ffb02e">🌟 고유 장비! ${esc_(i.emoji)} ${esc_(i.name)} ${x.new?'(새로 얻음)':'★'+num(x.star)}</b>`); });
  if(num(r.dust)) o.push(`${cur('dust')} 가루 +${fm(r.dust)}`);
  if(!o.length) return '';
  return `<div class="rl-res"><b>방금 얻은 것</b><div style="margin-top:4px;display:flex;flex-direction:column;gap:2px">${o.map(t=>`<div>${t}</div>`).join('')}</div></div>`;
}
function subRelic(v){
  const byId={}; v.relics.forEach(x=>{ byId[x.id]=x; });
  const eqIds=new Set(Object.values(v.eq||{}));
  const slots=v.slots.map(s=>{ const it=byId[(v.eq||{})[s.slot]];
    return it?`<button class="rl-slot has" style="border-color:${RAR_C[num(it.rar)]}" data-do="rlunequip" data-slot="${esc_(s.slot)}" aria-label="${esc_(it.name)} 벗기"><div class="rl-ic">${esc_(it.emoji)}</div><div style="font-weight:900;color:${RAR_C[num(it.rar)]}">${esc_(it.rar_name)} +${num(it.lv)}</div><div>${esc_(it.name)}</div><div class="mut">${valTxt(it)}</div></button>`
      :`<div class="rl-slot"><div class="rl-ic" style="opacity:.35">${esc_(s.emoji)}</div><div class="mut">${esc_(s.name)}</div><div class="mut">${esc_(s.stat_name)}</div></div>`; }).join('');
  const sorted=v.relics.slice().sort((a,b)=>(num(b.rar)-num(a.rar))||(num(b.lv)-num(a.lv))||String(a.id).localeCompare(String(b.id)));
  const sel=ST.sel&&byId[ST.sel]?byId[ST.sel]:null;
  let det='';
  if(sel){
    const eq=eqIds.has(sel.id), can=num(v.dust)>=num(sel.cost);
    det=`<div class="rl-res"><div style="font-weight:900;color:${RAR_C[num(sel.rar)]}">${esc_(sel.emoji)} ${esc_(sel.rar_name)} ${esc_(sel.name)} +${num(sel.lv)}</div>
      <div>${valTxt(sel)}${sel.next_val!=null?` → <b>+${num(sel.next_val)}${sel.kind==='pct'?'%':'%p'}</b> (다음 강화)`:' · 최고 강화'}</div>
      <div class="btns" style="margin-top:6px">
        ${eq?`<button class="btn alt" data-do="rlunequip" data-slot="${esc_(sel.slot)}">벗기</button>`:`<button class="btn gold" data-do="rlequip" data-id="${esc_(sel.id)}">장착</button>`}
        ${sel.cost!=null?`<button class="btn ${can?'gold':'alt'}" data-do="rlenh" data-id="${esc_(sel.id)}">강화 ${cur('dust')}${fm(sel.cost)}</button>`:''}
        <button class="btn alt" data-do="rllock" data-id="${esc_(sel.id)}">${sel.lock?'🔓 잠금 풀기':'🔒 잠그기'}</button>
        ${eq||sel.lock?'':`<button class="btn alt" data-do="rlscrap" data-id="${esc_(sel.id)}">분해 ${cur('dust')}+${fm(sel.scrap)}</button>`}
      </div></div>`;
  }
  const cnt={}; v.relics.forEach(x=>{ if(!x.lock&&!eqIds.has(x.id)){ const k=x.slot+':'+x.rar; cnt[k]=(cnt[k]||0)+1; } });
  const mergeBtns=Object.keys(cnt).filter(k=>cnt[k]>=3&&num(k.split(':')[1])<3).map(k=>{ const [sl,rr]=k.split(':'), sn=(v.slots.find(s=>s.slot===sl)||{}).name||sl;
    return `<button class="btn gold" data-do="rlmerge" data-slot="${esc_(sl)}" data-rar="${esc_(rr)}">합성: ${esc_(sn)} ${esc_((v.rarities[num(rr)]||{}).name)} ${cnt[k]}개 → 한 등급 위</button>`; }).join('');
  return `<div class="card"><h2>착용 중인 유물</h2>${bonusLine(v)}<div class="rl-slots">${slots}</div>
    <div class="btns"><button class="btn gold" data-do="rlbox" data-n="1">${cur('coin')}${fm(v.box.cost)} 유물상자 열기</button><button class="btn alt" data-do="rlscrapall">희귀 일괄 분해</button></div>
    <div class="mut" style="margin-top:4px">천장: 전설 이상 ${num(v.box.pity)}/${num(v.box.pity_max)} · 신화 ${num(v.box.mpity)}/${num(v.box.mpity_max)} · 고유 ${num(v.box.upity)}/${num(v.box.upity_max)} (고유 확률 ${num(v.box.unique_p)}%) · 등급 확률 ${v.rarities.map(r=>esc_(r.name)+' '+num(r.p)+'%').join(' · ')}</div></div>
    ${resHtml()}${det}
    <div class="card"><h2>보관함 <span class="pill">${v.relics.length}/${num(v.cap)}</span></h2>
    ${mergeBtns?`<div class="btns" style="margin-bottom:6px">${mergeBtns}</div>`:''}
    ${sorted.length?`<div class="rl-grid">${sorted.map(it=>itemBox(it,eqIds.has(it.id),ST.sel===it.id)).join('')}</div>`:`<div class="mut">유물이 없어요. 던전에서 주화를 모아 상자를 열어 보세요.</div>`}</div>`;
}
function ablRow(l,locked){ const c=ABI_C[num(l.grade)]||'inherit'; return `<span><span class="g" style="color:${c}">${esc_(l.grade_name)}</span> ${esc_(l.name)} <b style="color:${c}">+${num(l.val)}${esc_(l.unit)}</b></span>`; }
function subAbi(v){
  const a=v.abi, n=num(a.unlock);
  if(!Array.isArray(ST.lock)||ST.lock.length!==n) ST.lock=(Array.isArray(a.lock)&&a.lock.length===n?a.lock:new Array(n).fill(false)).map(Boolean);
  const nLock=ST.lock.filter(Boolean).length, base=num(a.base)||num(a.cost);
  const cst=a.lines.length?base*Math.pow(2,Math.min(2,nLock)):base;      // 화면에서 고른 잠금 기준(서버도 보낸 잠금으로 같은 식으로 센다)
  const rows=a.lines.length?a.lines.map((l,i)=>`<div class="rl-line ${ST.lock[i]?'lk':''}">${ablRow(l)}<label><input type="checkbox" data-rlock="${i}" ${ST.lock[i]?'checked':''} ${a.pend?'disabled':''}> 🔒</label></div>`).join('')
    :`<div class="mut">아직 어빌리티가 없어요. 아래 버튼으로 처음 굴려 보세요(첫 굴림은 바로 적용돼요).</div>`;
  const pend=a.pend?`<div class="rl-res"><b>새로 나온 줄을 비교해요</b><div class="rl-cmp"><div><div class="mut">지금</div>${a.lines.map(l=>`<div class="rl-line">${ablRow(l)}</div>`).join('')}</div><div><div class="mut">새 결과</div>${a.pend.map(l=>`<div class="rl-line">${ablRow(l)}</div>`).join('')}</div></div>
    <div class="btns" style="margin-top:6px"><button class="btn gold" data-do="rlapply">새 결과로 바꾸기</button><button class="btn alt" data-do="rlkeep">지금 걸 유지</button></div></div>`:'';
  const unlocks=[2,3].filter(k=>k>n).map(k=>`<div class="mut">${k}번째 줄: 🔮 ${fm(a.unlock_cost[String(k)])} 로 상점에서 열 수 있어요.</div>`).join('');
  return `<div class="card"><h2>🔮 어빌리티 <span class="pill">${n}/${num(a.max)}줄</span></h2>
    <div class="sub">수정으로 줄을 다시 굴려요. 마음에 드는 줄은 🔒 잠그면 그대로 남고, 대신 수정이 더 들어요(잠근 줄 1개 ×2 · 2개 ×4). 굴린 결과는 비교한 뒤에 바꿀지 정해요.</div>
    ${rows}${pend}
    ${a.pend?'':`<div class="btns"><button class="btn ${num(v.crystal)>=cst?'gold':'alt'}" data-do="rlroll">${a.lines.length?'다시 굴리기':'처음 굴리기'} 🔮${fm(cst)}</button></div>`}
    ${unlocks}
    <div class="mut" style="margin-top:6px">등급 확률 ${a.grades.map(x=>esc_(x.name)+' '+num(x.p)+'%').join(' · ')} · 능력치: ${a.stats.map(s=>esc_(s.name)+'(최대 '+num(s.max)+esc_(s.unit)+')').join(', ')}</div></div>`;
}
function subUq(v){
  const u=v.unique, on=new Set(u.on||[]);
  return `<div class="card"><h2>🌟 고유 장비 <span class="pill">${on.size}/${num(u.slots)}칸</span></h2>
    <div class="sub">클랜원 닉네임이 붙은 장비예요. 하나마다 <b>특수 능력</b>이 있고 ${num(u.slots)}개까지 낄 수 있어요. 얻는 길: 유물상자(극확률·천장) · 상점 고유 상자(주 1번) · 엘리트 처치(${num(u.elite_p)}%). 같은 걸 또 얻으면 ★이 올라 능력이 +${num(u.star_pct)}%씩 세져요(최대 ★${num(u.star_max)}).</div>
    <div class="rl-grid" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">${u.list.map(x=>{
      const base=Object.keys(x.base||{}).map(k=>`${({atk:'공격력',hp:'체력',def:'방어력',acc:'명중',crit:'치명타',critdmg:'치명피해'})[k]||k} +${num(x.base[k])}%`).join(' · ');
      return `<div class="rl-it" style="cursor:default;border-color:${x.owned?'#ffb02e':'var(--line)'};${x.owned?'':'opacity:.55'}">
      <div class="rl-ic">${esc_(x.emoji)}</div><div style="font-weight:900">${esc_(x.name)}</div>
      ${x.owned?`<div style="color:#ffb02e;font-weight:900">${'★'.repeat(num(x.star))}${'☆'.repeat(Math.max(0,num(u.star_max)-num(x.star)))}</div><div><b>${esc_(x.text)}</b></div>${base?`<div class="mut">${esc_(base)}</div>`:''}
        <button class="btn ${on.has(x.key)?'alt':'gold'}" data-do="rluq" data-key="${esc_(x.key)}">${on.has(x.key)?'빼기':'끼기'}</button>`
        :`<div class="mut">아직 못 얻었어요</div><div class="mut">${esc_(x.text)}</div>`}</div>`; }).join('')}</div></div>`;
}
function subDun(v){
  return `<div class="card"><h2>⛏ 일일 던전</h2><div class="sub">하루 ${num(v.dun[0]&&v.dun[0].max)}번씩, 날짜가 바뀌면 새로 채워져요(한국 시간 자정). 전투력이 모자라면 입장 횟수는 줄지 않아요. 보상은 스테이지가 높을수록 조금 늘어요.</div>
    ${v.dun.map(d=>`<div class="rl-res"><div style="font-weight:900">${esc_(d.emoji)} ${esc_(d.name)} <span class="pill">${num(d.used)}/${num(d.max)}</span> <span class="mut">얻는 것: ${cur(d.cur)} ${esc_(d.cur_name)}</span></div>
      <div class="rl-tier">${d.tiers.map((t,i)=>`<button class="btn ${t.ok&&num(d.used)<num(d.max)?'gold':'alt'}" data-do="rldun" data-dun="${esc_(d.key)}" data-tier="${i}" ${num(d.used)>=num(d.max)?'disabled':''}>${esc_(t.name)}<br><span style="font-size:11px">${cur(d.cur)}+${fm(t.reward)} · 전투력 ${fm(t.need)}${t.ok?'':' 필요'}</span></button>`).join('')}</div></div>`).join('')}</div>`;
}
function subShop(v){
  return `<div class="card"><h2>🛒 재화 상점</h2><div class="sub">던전에서 번 재화로 사요. 사면 바로 처리돼요.</div>
    ${v.shop.map(s=>{ const left=[s.day_left!=null?`오늘 ${num(s.day_left)}번 남음`:'',s.week_left!=null?`이번 주 ${num(s.week_left)}번 남음`:''].filter(Boolean).join(' · ');
      const can=!s.sold_out&&num(v[s.cur])>=num(s.price);
      return `<div class="rl-shop"><div><div style="font-weight:900">${esc_(s.emoji)} ${esc_(s.name)}</div><div class="d">${esc_(s.desc)}${left?' · '+esc_(left):''}</div></div>
      <button class="btn ${can?'gold':'alt'}" data-do="rlbuy" data-key="${esc_(s.key)}" data-name="${esc_(s.name)}" ${s.sold_out?'disabled':''}>${s.sold_out?'품절':cur(s.cur)+fm(s.price)}</button></div>`; }).join('')}</div>`;
}
function tab(){
  injectCss();
  const v=RV();
  if(!v) return `<div class="card empty"><div class="big">🏺</div><div class="sub">유물 정보를 아직 받지 못했어요. 서버가 업데이트되는 중일 수 있어요. 위쪽 새로고침(↻)을 눌러 보세요.</div></div>`;
  const f={relic:subRelic,abi:subAbi,uq:subUq,dun:subDun,shop:subShop}[ST.sub]||subRelic;
  let body=''; try{ body=f(v); }catch(e){ console.warn(e); body='<div class="card empty"><div class="sub">이 칸을 그리지 못했어요. 새로고침(↻)을 눌러 보세요.</div></div>'; }
  return head(v)+body;
}
const MSG={short:'재화가 모자라요.',limit:'오늘(또는 이번 주) 더는 못 해요.',owned:'이미 가지고 있어요.',need_prev:'앞의 줄을 먼저 열어야 해요.',gone:'그 유물을 찾을 수 없어요.',save_fail:'저장하지 못해서 취소했어요. 잠시 뒤 다시 해 주세요.',none:'할 수 있는 게 없어요.',max:'이미 최고 강화예요.',nopend:'비교할 새 결과가 없어요.',all_locked:'전부 잠그면 굴릴 수 없어요.',not_owned:'아직 없는 고유 장비예요.'};
const sayR=(j,okTxt)=>{ if(j.result==='ok'||j.result==='win') say(okTxt,'ok'); else say(MSG[j.result]||'처리하지 못했어요.','bad'); };
const B=(path,body,fn)=>act(path,body,fn);
const DO_={
  rlsub:el=>{ ST.sub=el.dataset.sub||'relic'; ST.res=null; render(); },
  rlsel:el=>{ ST.sel=(ST.sel===el.dataset.id)?null:el.dataset.id; render(); },
  rlequip:el=>B('/brj/rl_equip',{id:el.dataset.id},j=>sayR(j,'장착했어요!')),
  rlunequip:el=>B('/brj/rl_equip',{off:el.dataset.slot},j=>sayR(j,'벗었어요.')),
  rllock:el=>B('/brj/rl_lock',{id:el.dataset.id},j=>sayR(j,'잠금을 바꿨어요.')),
  rlenh:el=>B('/brj/rl_enhance',{id:el.dataset.id},j=>{ if(j.result==='ok'){ say(`✨ 강화! +${num((j.item||{}).lv)}`,'ok'); snd('enhance_ok'); } else say(j.result==='short'?'✨ 가루가 모자라요. 분해하거나 상점에서 사세요.':(MSG[j.result]||'강화하지 못했어요.'),'bad'); }),
  rlscrap:el=>{ if(!confirm('이 유물을 분해할까요?')) return; B('/brj/rl_scrap',{ids:[el.dataset.id]},j=>{ if(j.result==='ok'){ ST.sel=null; say(`♻ 분해해서 ✨ ${fm(j.dust)} 받았어요.`,'ok'); } else say(MSG[j.result]||'분해하지 못했어요.','bad'); }); },
  rlscrapall:()=>{ const v=RV(); if(!v) return; const eq=new Set(Object.values(v.eq||{})); const ids=v.relics.filter(x=>num(x.rar)===0&&!x.lock&&!eq.has(x.id)).map(x=>x.id).slice(0,80);
    if(!ids.length){ say('분해할 희귀 유물이 없어요(장착·잠금은 빠져요).','info'); render(); return; }
    if(!confirm(`희귀 유물 ${ids.length}개를 분해할까요? (장착·잠금 제외)`)) return;
    B('/brj/rl_scrap',{ids},j=>{ if(j.result==='ok'){ ST.sel=null; say(`♻ ${fm(j.n)}개 분해 · ✨ ${fm(j.dust)} 받았어요.`,'ok'); } else say(MSG[j.result]||'분해하지 못했어요.','bad'); }); },
  rlmerge:el=>B('/brj/rl_merge',{slot:el.dataset.slot,rar:Number(el.dataset.rar)},j=>{ if(j.result==='ok'){ const it=j.item||{}; ST.sel=it.id||null; say(`🔨 합성 성공! ${esc_(it.emoji||'')} ${esc_(it.rar_name||'')} ${esc_(it.name||'')} (가루 +${fm(j.back)})`,'ok'); snd('summon'); } else say(j.result==='short'?'같은 칸·같은 등급 3개가 필요해요(장착·잠금 제외).':(MSG[j.result]||'합성하지 못했어요.'),'bad'); }),
  rlbox:()=>B('/brj/rl_shop',{key:'box1'},j=>{ if(j.result==='ok'){ ST.res=j.got||null; snd('summon'); say('🎁 유물상자를 열었어요!','ok'); } else say(MSG[j.result]||'열지 못했어요.','bad'); }),
  rlbuy:el=>{ const nm=el.dataset.name||'이 상품'; if(!confirm(`「${nm}」을(를) 살까요?`)) return;
    B('/brj/rl_shop',{key:el.dataset.key},j=>{ if(j.result==='ok'){ const gt=j.got||{}; ST.res=(gt.relics&&gt.relics.length)||(gt.unique&&gt.unique.length)||gt.dust?gt:null; say(`🛒 「${nm}」을(를) 샀어요!`,'ok'); snd('summon'); } else say(MSG[j.result]||'사지 못했어요.','bad'); }); },
  rldun:el=>B('/brj/rl_dungeon',{dun:el.dataset.dun,tier:Number(el.dataset.tier)},j=>{
    if(j.result==='win'){ const k=Object.keys(j.got||{}).find(x=>x!=='dust'); say(`⛏ 클리어! ${cur(k)} +${fm((j.got||{})[k])}${num((j.got||{}).dust)?` · ${cur('dust')} +${fm(j.got.dust)}`:''}`,'ok'); snd('levelup'); }
    else if(j.result==='lose') say(`💥 전투력이 모자라요 (내 ${fm(j.power)} / 필요 ${fm(j.need)}). 입장 횟수는 그대로예요.`,'bad');
    else say(MSG[j.result]||'입장하지 못했어요.','bad'); }),
  rlroll:()=>{ const v=RV(); if(!v) return; B('/brj/rl_abi',{act:'roll',lock:(ST.lock||[]).map(Boolean)},j=>{ if(j.result==='ok'){ snd('summon'); say(j.view&&j.view.relic&&j.view.relic.abi&&j.view.relic.abi.pend?'🔮 새 결과가 나왔어요. 비교해서 정하세요.':'🔮 어빌리티가 정해졌어요!','ok'); } else say(j.result==='short'?`🔮 수정이 모자라요${j.cost?` (${fm(j.cost)} 필요)`:''}.`:(MSG[j.result]||'굴리지 못했어요.'),'bad'); }); },
  rlapply:()=>B('/brj/rl_abi',{act:'apply'},j=>sayR(j,'🔮 새 결과로 바꿨어요!')),
  rlkeep:()=>B('/brj/rl_abi',{act:'keep'},j=>sayR(j,'지금 걸 유지했어요.')),
  rluq:el=>{ const v=RV(); if(!v) return; const on=new Set(v.unique.on||[]); const k=el.dataset.key;
    if(on.has(k)) on.delete(k); else { if(on.size>=num(v.unique.slots)){ say(`고유 장비는 ${num(v.unique.slots)}개까지 낄 수 있어요. 하나를 먼저 빼 주세요.`,'bad'); render(); return; } on.add(k); }
    B('/brj/rl_unique',{on:Array.from(on)},j=>sayR(j,'바꿨어요!')); },
};
document.addEventListener('change',e=>{   // 어빌리티 줄 잠금 체크(서버에 보내지 않고 굴릴 때 함께 보낸다)
  const t=e.target; if(!t||t.dataset==null||t.dataset.rlock==null) return;
  const i=Number(t.dataset.rlock); if(!Array.isArray(ST.lock)) return;
  const nx=ST.lock.slice(); nx[i]=!!t.checked;
  if(nx.filter(Boolean).length>=nx.length){ t.checked=false; if(typeof say==='function') say('전부 잠글 수는 없어요.','bad'); if(typeof render==='function') render(); return; }
  ST.lock=nx; if(typeof render==='function') render();
});
function fx(){ const v=RV(); return v&&v.fx?v.fx:{}; }
window.BrjRelic={tab,DO:DO_,fx,ART,_st:ST};
})();
