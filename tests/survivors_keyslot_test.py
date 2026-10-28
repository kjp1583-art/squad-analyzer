# -*- coding: utf-8 -*-
"""🗝 흐접새우 서바이벌 「각성 열쇠 칸」 시험 — 2026-10-12 사장님 지시 「A로 가자」
   규칙: 열쇠 패시브(= 내가 가진 무기의 짝 패시브 WEAP[k].pair)는 패시브 6칸 밖의 열쇠 칸(MAXEV=3칸)에 먼저 들어간다.
         열쇠 칸이 가득 찼거나 열쇠가 아닌 패시브면 일반 칸(6)으로 간다. 부활은 어느 칸도 안 쓴다. 소속은 S.ps(얻은 순서)·S.w 에서 매번 계산한다(저장 안 함).
   사용: nice -n 10 python3 tests/survivors_keyslot_test.py   (종료코드 0 = 전부 통과)
   가  칸 계산 경계(열쇠 0~4개 · 공유 열쇠 · 부활 · 각성 뒤 · 무기를 얻어 일반 패시브가 열쇠가 됨 · 순서 무관 개수)
   나  카드 풀(레벨업 · 보스 상자 own · 다시 뽑기 · 봉인 보충): 일반 6칸이 꽉 차도 열쇠는 나오고 비열쇠 새 패시브는 안 나온다(18캐릭터)
   다  무작위 빌드 수만 번: 일반 칸 ≤ 6 · 열쇠 칸 ≤ 3 · 일반 칸 수는 무기를 얻어도 안 늘어난다 · 저장→복구(JSON 왕복)해도 같은 값
   라  각성 흐름(evReady · 열쇠 칸의 열쇠로 각성) · 초월 단계 패시브 · 같은 패시브 레벨업
   마  화면 문구(레벨업 창 · 일시정지 · 카드 · 도움말) · 옛 문구 잔재 없음
   바  18캐릭터 × 무작위 정책 몬테카를로: 잠김(칸 꽉 참 + 열쇠 없음) 0%
   임시 사본 survivors_keyslot_t.html (끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
NEW = 'survivors_keyslot_t.html'
FAILS = []; CHECKS = [0]
def check(n, c, x=''):
    CHECKS[0] += 1
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:900] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)

EXTRA = r"""
window.__K={PASS,SLOTP,SLOTW,MAXLV,MAXEV,WEAP,CHARS,offers,reroll,banCard,openLvup,applyUp,slotP,keyN,keyList,keyHeld,isKeyNew,cardOf,evReady,evolve,pv,pmax,PT,buildHtml,ownHtml,pauseGame,openChest,
  get CH(){return CH},get CUR(){return CUR},set CUR(v){CUR=v},
  seed(s){let a=s>>>0;Math.random=()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}};
window.__fresh=(ck,o)=>{o=o||{};const x=window.__p6x,K=window.__K;x.CH_set(ck);x.newRun();x.state='play';const S=x.S;
  S.lv=o.lv||10;S.rr=S.ban=0;S.banned=(o.banned||[]).slice();S.dly=null;S.ps={};
  if(o.w){S.w={};for(const w of o.w)S.w[w]=o.wlv||1;}
  return S;};
window.__keysOfWeapons=()=>{const S=window.__p6x.S;return window.__K.keyList();};
"""

async def main():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA)
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, w=412, h=860, page=NEW)
            ev = lambda js, a=None: pg.evaluate(js, a)
            CH = await ev("()=>__K.CHARS.map(c=>c.k)")
            WP = await ev("()=>Object.fromEntries(Object.keys(__K.WEAP).map(k=>[k,__K.WEAP[k].pair]))")
            PASSK = await ev("()=>Object.keys(__K.PASS)")
            # 서로 다른 열쇠를 가진 무기 4개 + 열쇠가 같은 무기 쌍
            seen = {}; distinct = []
            for w, p in WP.items():
                if p and p != 'rev' and p in PASSK and p not in seen: seen[p] = w; distinct.append(w)
            shared = None
            for w, p in WP.items():
                for w2, p2 in WP.items():
                    if w < w2 and p and p == p2 and p != 'rev' and p in PASSK: shared = (w, w2, p); break
                if shared: break
            print('서로 다른 열쇠 무기', len(distinct), '· 공유 열쇠', shared)
            check('서로 다른 열쇠를 가진 무기가 4개 이상 있다(시험 전제)', len(distinct) >= 4, len(distinct))

            print('── 가 칸 계산 경계 ──')
            JS_CALC = """([ck,ws,ps])=>{const S=__fresh(ck,{w:ws});for(const [k,l] of ps)S.ps[k]=l;const K=__K;return {slot:K.slotP(),key:K.keyN(),held:K.keyHeld(),list:K.keyList()};}"""
            k0 = [WP[w] for w in distinct[:4]]
            others = [p for p in PASSK if p != 'rev' and p not in WP.values()] or [p for p in PASSK if p != 'rev' and p not in k0]
            others = [p for p in PASSK if p != 'rev' and p not in k0][:8]
            r = await ev(JS_CALC, ['brj', distinct[:1], []]); check('아무것도 없으면 0/0', r['slot'] == 0 and r['key'] == 0, r)
            r = await ev(JS_CALC, ['brj', distinct[:1], [[k0[0], 1]]]); check('열쇠 1개: 일반 0 · 열쇠 1', r['slot'] == 0 and r['key'] == 1 and r['held'] == [k0[0]], r)
            r = await ev(JS_CALC, ['brj', distinct[:1], [[o, 1] for o in others[:6]] + [[k0[0], 1]]]); check('일반 6 + 열쇠 1: 일반 6/6 · 열쇠 1/3', r['slot'] == 6 and r['key'] == 1, r)
            r = await ev(JS_CALC, ['brj', distinct[:4], [[o, 1] for o in others[:6]] + [[k, 1] for k in k0]]); check('열쇠 4개(무기 4개): 열쇠 칸 3 · 4번째는 일반 칸 → 일반 7?', r['key'] == 3 and r['slot'] == 7, r)
            r = await ev(JS_CALC, ['brj', distinct[:4], [[k, 1] for k in k0] + [[o, 1] for o in others[:5]]]); check('열쇠 4개 + 일반 5: 열쇠 칸 3 · 일반 6(4번째 열쇠가 일반 칸으로)', r['key'] == 3 and r['slot'] == 6 and r['held'] == k0[:3], r)
            r = await ev(JS_CALC, ['brj', distinct[:1], [['rev', 1]] + [[k0[0], 1]]]); check('부활은 어느 칸도 안 쓴다', r['slot'] == 0 and r['key'] == 1, r)
            r = await ev(JS_CALC, ['brj', distinct[:1], [[others[0], 1], [others[1], 1]]]); check('열쇠가 아닌 패시브만 있으면 열쇠 칸 0', r['key'] == 0 and r['slot'] == 2, r)
            if shared:
                a, b2, p = shared
                r = await ev(JS_CALC, ['brj', [a, b2], [[p, 1]]]); check('두 무기가 같은 열쇠를 공유해도 열쇠 칸 1개', r['key'] == 1 and r['list'].count(p) == 1 and r['slot'] == 0, r)
            # 무기를 얻어 일반 패시브가 열쇠가 되는 경우: 일반 칸 수는 줄어든다
            r = await ev("""([ck,w0,w1,p1])=>{const S=__fresh(ck,{w:[w0]});S.ps[p1]=1;const a=[__K.slotP(),__K.keyN()];S.w[w1]=1;return {a,b:[__K.slotP(),__K.keyN()]};}""", ['brj', distinct[0], distinct[1], k0[1]])
            check('일반 칸에 있던 패시브가 무기를 얻어 열쇠가 되면 열쇠 칸으로 옮겨 간다(1/0 → 0/1)', r['a'] == [1, 0] and r['b'] == [0, 1], r)
            # 각성한 뒤에도 열쇠는 열쇠 칸에 남는다
            r = await ev("""([ck,w0,p0])=>{const S=__fresh(ck,{w:[w0]});S.ps[p0]=1;const a=[__K.slotP(),__K.keyN()];S.w[w0]=8;S.ev[w0]=1;return {a,b:[__K.slotP(),__K.keyN()]};}""", ['brj', distinct[0], k0[0]])
            check('각성한 뒤에도 그 열쇠는 열쇠 칸에 남는다(일반 칸으로 쫓겨나지 않는다)', r['a'] == [0, 1] and r['b'] == [0, 1], r)
            # 순서 무관 개수: 같은 집합을 다른 순서로 넣어도 칸 수가 같다
            rs = []
            for seed in range(30):
                order = [[k, 1] for k in k0] + [[o, 1] for o in others[:5]]
                random.Random(seed).shuffle(order)
                rs.append(await ev(JS_CALC, ['brj', distinct[:4], order]))
            check('같은 집합을 어떤 순서로 얻어도 일반/열쇠 칸 수가 같다(30가지 순서)', len({(x['slot'], x['key']) for x in rs}) == 1, {(x['slot'], x['key']) for x in rs})

            print('── 나 카드 풀 ──')
            TALLY = """([cs,N,opt,own])=>cs.map((ck,i)=>{const S=__fresh(ck,Object.assign({lv:25},opt.setup||{}));const K=__K;const key=K.WEAP[K.CH.w].pair;
                const others=Object.keys(K.PASS).filter(k=>k!=='rev'&&k!==key);for(let j=0;j<(opt.fill===undefined?6:opt.fill);j++)S.ps[others[(j+i*3)%others.length]]=1;
                if(opt.key)S.ps[key]=1;if(opt.ban)S.banned=[key];K.seed(100+i);
                const t={ck,key:0,nonKey:0,up:0,rev:0,tyKey:0,tyNorm:0,slot:K.slotP(),kn:K.keyN()};
                for(let r=0;r<N;r++){const cs2=K.offers(3,opt.excl?[key]:null,own);for(const o of cs2){if(o.t!=='p')continue;if(o.k==='rev'){t.rev++;continue;}const had=(S.ps[o.k]||0)>0;
                  if(had){t.up++;continue;}if(o.k===key){t.key++;const ty=K.cardOf(o).ty;if(/열쇠 칸/.test(ty))t.tyKey++;}else{t.nonKey++;if(/슬롯/.test(K.cardOf(o).ty))t.tyNorm++;}}}
                return t;})"""
            N = 1200
            r = await ev(TALLY, [CH, N, {}, False])
            check('일반 6칸 꽉 + 열쇠 없음: 새 비열쇠 패시브 0 · 열쇠 나옴(18캐릭터)', all(t['slot'] == 6 and t['kn'] == 0 and t['nonKey'] == 0 and t['key'] > N * .02 for t in r), [(t['ck'], t['slot'], t['nonKey'], t['key']) for t in r if not (t['slot'] == 6 and t['nonKey'] == 0 and t['key'] > N * .02)][:4])
            check('열쇠 카드 문구는 「열쇠 칸 1/3」', all(t['tyKey'] == t['key'] for t in r), [(t['ck'], t['tyKey'], t['key']) for t in r][:3])
            r = await ev(TALLY, [CH[:6], N, {'fill': 5}, False])
            check('일반 5칸 + 열쇠 없음: 새 일반 패시브도 나오고 열쇠도 나온다 · 일반 카드 문구는 「슬롯 6/6」', all(t['nonKey'] > 0 and t['key'] > 0 and t['tyNorm'] == t['nonKey'] for t in r), r[:2])
            r = await ev(TALLY, [CH[:6], N, {'fill': 6, 'key': 1}, False])
            check('일반 6칸 + 열쇠 보유: 새 패시브 0(레벨업 카드만)', all(t['nonKey'] == 0 and t['key'] == 0 and t['up'] > 0 for t in r), r[:2])
            r = await ev(TALLY, [CH[:6], N, {'fill': 6, 'ban': 1}, False])
            check('열쇠를 봉인하면 열쇠도 안 나온다(새 패시브 0)', all(t['nonKey'] == 0 and t['key'] == 0 for t in r), r[:2])
            r = await ev(TALLY, [CH[:6], N, {'fill': 6, 'excl': 1}, False])
            check('다시 뽑기로 열쇠를 이번에만 제외해도 일반 칸 규칙은 그대로(새 패시브 0)', all(t['nonKey'] == 0 and t['key'] == 0 for t in r), r[:2])
            r = await ev(TALLY, [CH[:6], N, {'fill': 6}, True])
            check('보스 상자(own): 안 가진 새 패시브는 열쇠도 안 나온다', all(t['nonKey'] == 0 and t['key'] == 0 for t in r), r[:2])
            r = await ev(TALLY, [CH[:6], N, {'fill': 6, 'setup': {'lv': 30}}, False])
            check('Lv20+ 부활 카드는 일반 칸이 꽉 차도 나온다', all(t['rev'] > 0 for t in r), r[:2])
            # 열쇠 칸 3개가 이미 찬 뒤: 4번째 무기의 열쇠는 일반 칸 규칙
            r = await ev("""([N])=>{const S=__fresh('brj',{lv:25,w:%s});const K=__K;const ks=K.keyList();const res={};
                for(const k of ks.slice(0,3))S.ps[k]=1;const others=Object.keys(K.PASS).filter(k=>k!=='rev'&&!ks.includes(k));
                for(let j=0;j<5;j++)S.ps[others[j]]=1;res.a={slot:K.slotP(),kn:K.keyN(),new4:K.isKeyNew(ks[3])};
                K.seed(5);let seen4=0,ty='';for(let r=0;r<N;r++)for(const o of K.offers(3))if(o.t==='p'&&o.k===ks[3]&&!S.ps[o.k]){seen4++;ty=K.cardOf(o).ty;}
                S.ps[others[5]]=1;res.b={slot:K.slotP()};K.seed(6);let seen4b=0,nk=0;for(let r=0;r<N;r++)for(const o of K.offers(3))if(o.t==='p'&&!S.ps[o.k]&&o.k!=='rev'){if(o.k===ks[3])seen4b++;else nk++;}
                res.seen4=seen4;res.ty=ty;res.seen4b=seen4b;res.nk=nk;return res;}""".replace('%s', json.dumps(distinct[:4])), [N])
            check('열쇠 칸이 3개 차면 4번째 무기의 열쇠는 일반 칸 규칙(열쇠 칸 새로 안 열림)', r['a']['kn'] == 3 and not r['a']['new4'] and r['a']['slot'] == 5, r)
            check('  └ 일반 5칸이면 4번째 열쇠가 「슬롯 6/6」 카드로 나온다', r['seen4'] > 0 and '슬롯 6/6' in r['ty'], r)
            check('  └ 일반 6칸이면 4번째 열쇠도 · 새 패시브도 안 나온다', r['b']['slot'] == 6 and r['seen4b'] == 0 and r['nk'] == 0, r)
            # 다시 뽑기·봉인 보충 경로
            r = await ev("""([cs,N])=>cs.map((ck,i)=>{const S=__fresh(ck,{lv:25});const K=__K;const key=K.WEAP[K.CH.w].pair;const others=Object.keys(K.PASS).filter(k=>k!=='rev'&&k!==key);
                for(let j=0;j<6;j++)S.ps[others[(j+i)%others.length]]=1;S.rr=1e9;S.ban=1e9;K.seed(21+i);let bad=0,seenKey=0;
                for(let j=0;j<N;j++){K.CUR=K.offers(3);K.reroll();for(const o of K.CUR)if(o.t==='p'&&!S.ps[o.k]&&o.k!=='rev'){if(o.k===key)seenKey++;else bad++;}
                  {const bi=K.CUR.findIndex(o=>o&&o.k&&o.k!==key);if(bi>=0)K.banCard(bi);}S.banned.length=0;for(const o of K.CUR)if(o&&o.t==='p'&&!S.ps[o.k]&&o.k!=='rev'){if(o.k===key)seenKey++;else bad++;}}
                return {ck,bad,seenKey};})""", [CH[:6], 300])
            check('다시 뽑기(reroll)·봉인 보충(banCard) 경로: 일반 6칸에서 비열쇠 새 패시브 0', all(t['bad'] == 0 for t in r), r)
            src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
            check('옛 예약 코드(keyRsv · KEY_RSV_NOTE · keyPassOf)가 남아 있지 않다', not re.search(r'keyRsv|KEY_RSV|keyPassOf', src))
            check('패시브를 얻는 곳은 applyUp 한 곳 · 카드를 뽑는 곳은 offers 한 곳', len(re.findall(r'S\.ps\[o\.k\]=pv\(o\.k\)\+1', src)) == 1 and len(re.findall(r'\boffers\(', src)) == 5, len(re.findall(r'\boffers\(', src)))

            print('── 다 무작위 빌드 ──')
            R = await ev("""([N,ws,seed])=>{const K=__K;const out={bad:[],maxSlot:0,maxKey:0,maxTot:0,incr:0,rt:0};const ids=Object.keys(K.WEAP);const pk=Object.keys(K.PASS);let a=seed;const rnd=()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
              for(let n=0;n<N;n++){const S=__fresh(K.CHARS[n%K.CHARS.length].k,{lv:25});K.seed(seed+n);let steps=0;
                for(let st=0;st<60;st++){const before=K.slotP();
                  const cs=K.offers(3);const c=cs[Math.floor(rnd()*cs.length)];
                  if(rnd()<.35){const w=ids[Math.floor(rnd()*ids.length)];if(!S.w[w]&&Object.keys(S.w).length<6){const b0=K.slotP();S.w[w]=1;if(K.slotP()>b0)out.incr++;}}
                  else if(c){if(c.t==='p')S.ps[c.k]=(S.ps[c.k]||0)+1;}
                  const sp=K.slotP(),kn=K.keyN();out.maxSlot=Math.max(out.maxSlot,sp);out.maxKey=Math.max(out.maxKey,kn);
                  if(sp>6||kn>3||sp<0)out.bad.push([n,st,sp,kn]);
                  // 저장→복구: JSON 왕복해도 같은 값
                  if(st%10===0){const ps=JSON.parse(JSON.stringify(S.ps)),w=JSON.parse(JSON.stringify(S.w));const S0=K.slotP(),K0=K.keyN(),H0=K.keyHeld().join();S.ps=ps;S.w=w;if(K.slotP()!==S0||K.keyN()!==K0||K.keyHeld().join()!==H0)out.rt++;}}}
              return out;}""", [400, None, 777])
            check('무작위 빌드 400판 × 60단계: 일반 칸 ≤ 6 · 열쇠 칸 ≤ 3 · 무기를 얻어도 일반 칸이 늘지 않는다', not R['bad'] and R['maxSlot'] <= 6 and R['maxKey'] <= 3 and R['incr'] == 0, R)
            check('  └ 6칸과 3칸이 실제로 다 차 본다(시험에 이빨이 있다)', R['maxSlot'] == 6 and R['maxKey'] == 3, R)
            check('  └ 저장→복구(JSON 왕복) 뒤 칸 계산이 같다', R['rt'] == 0, R)

            print('── 라 각성 · 초월 · 레벨업 ──')
            r = await ev("""([w0,p0])=>{const S=__fresh('brj',{w:[w0]});const K=__K;const others=Object.keys(K.PASS).filter(k=>k!=='rev'&&k!==p0);
                for(let j=0;j<6;j++)S.ps[others[j]]=1;S.ps[p0]=1;S.w[w0]=K.MAXLV;const rdy=K.evReady();return {rdy,slot:K.slotP(),kn:K.keyN()};}""", [distinct[0], k0[0]])
            check('일반 6칸이 꽉 차도 열쇠 칸의 열쇠로 무기 Lv8 이면 각성 준비(evReady)', r['rdy'] == [distinct[0]] and r['slot'] == 6 and r['kn'] == 1, r)
            r = await ev("""([w0,p0])=>{const S=__fresh('brj',{lv:25,w:[w0]});const K=__K;S.ps[p0]=1;let up=0,rare=0;K.seed(3);for(let r=0;r<500;r++)for(const o of K.offers(3))if(o.t==='p'&&o.k===p0)up++;
                const ty=K.cardOf({t:'p',k:p0,l:1}).ty;S.ps[p0]=K.pmax(p0);let pt=0;for(let r=0;r<800;r++)for(const o of K.offers(3))if(o.t==='pt'&&o.p===p0)pt++;return {up,ty,pt,pm:K.pmax(p0),hasPT:!!K.PT[p0]};}""", [distinct[0], k0[0]])
            check('열쇠 칸의 열쇠도 레벨업 카드가 계속 나온다 · 카드 문구는 「패시브 강화」', r['up'] > 0 and r['ty'] == '🎒 패시브 강화', r)
            check('열쇠 칸의 열쇠가 만렙이면 초월 카드가 나온다(초월 표가 있는 패시브일 때)', (not r['hasPT']) or r['pt'] > 0, r)
            r = await ev("""()=>{const S=__fresh('brj',{lv:25});const K=__K;const key=K.WEAP[K.CH.w].pair;S.ps={};const before=K.slotP();K.applyUp({t:'p',k:key,l:0});return {before,after:K.slotP(),kn:K.keyN(),ps:S.ps[key]};}""")
            check('열쇠 카드를 고르면(applyUp) 일반 칸은 그대로 · 열쇠 칸만 1 늘어난다', r['before'] == 0 and r['after'] == 0 and r['kn'] == 1 and r['ps'] == 1, r)

            print('── 마 화면 문구 ──')
            UI = await ev("""()=>{const x=window.__p6x,K=__K,out={};
              let S=__fresh('brj',{lv:10});const key=K.WEAP[K.CH.w].pair;const others=Object.keys(K.PASS).filter(k=>k!=='rev'&&k!==key);for(let j=0;j<5;j++)S.ps[others[j]]=1;
              x.state='lvup';K.openLvup();const hint=document.getElementById('lvKey'),own=document.getElementById('lvOwn').textContent,lh=document.getElementById('lvHint').textContent;
              out.lv5={hidden:hint.hidden,txt:hint.textContent,own,lh};x.resume&&x.resume();
              S=__fresh('brj',{lv:10});S.ps[others[0]]=1;x.state='lvup';K.openLvup();out.lv1={hidden:document.getElementById('lvKey').hidden};x.resume&&x.resume();
              S=__fresh('brj',{lv:10});for(let j=0;j<5;j++)S.ps[others[j]]=1;S.ps[key]=1;x.state='lvup';K.openLvup();out.held={hidden:document.getElementById('lvKey').hidden,own:document.getElementById('lvOwn').textContent};x.resume&&x.resume();
              S=__fresh('brj',{lv:10});for(let j=0;j<5;j++)S.ps[others[j]]=1;S.ps[key]=1;K.pauseGame();out.pause=document.getElementById('pInfo').textContent;x.resume&&x.resume();
              out.help=[...document.querySelectorAll('#title li')].map(l=>l.textContent).join('\\n');return out;}""")
            check('레벨업 창: 일반 5칸 + 열쇠 없음 → 한 줄 안내(쉬운 말) · 내 능력 목록에 「열쇠 0/3」 · 일반 5/6', not UI['lv5']['hidden'] and '열쇠 칸' in UI['lv5']['txt'] and '패시브 5/6' in UI['lv5']['own'] and '열쇠 0/3' in UI['lv5']['own'], UI['lv5'])
            check('레벨업 창 맨 위 줄에도 「패시브 5/6 · 열쇠 0/3」', '패시브 5/6 · 🗝 열쇠 0/3' in UI['lv5']['lh'], UI['lv5']['lh'])
            check('레벨업 창: 일반 1칸이면 안내 줄 숨김 · 열쇠를 가졌으면 안내 없음 · 「열쇠 1/3」', UI['lv1']['hidden'] and UI['held']['hidden'] and '열쇠 1/3' in UI['held']['own'], UI)
            check('일시정지: 「패시브 5/6 · 🗝 열쇠 1/3」', '패시브 5/6 · 🗝 열쇠 1/3' in UI['pause'], UI['pause'][:300])
            check('도움말: 새 규칙 문구가 있고 옛 「마지막 한 칸」 문구는 없다', '열쇠 칸(3칸)에 따로 들어가요' in UI['help'] and '마지막 한 칸' not in UI['help'], UI['help'][:400])
            check('옛 문구 잔재 없음(마지막 한 칸 · 열쇠 자리 · 남겨 둬요)', not re.search(r'마지막 한 칸|열쇠 자리|남겨 둬요', src))

            print('── 바 몬테카를로 — 잠김 ──')
            MC = """([cs,trials,LV])=>{const K=__K,x=window.__p6x;const res=[];
              cs.forEach((ck,ci)=>{let lock=0,got=0,ready=[];
                for(let tr=0;tr<trials;tr++){const S=__fresh(ck,{lv:1});K.seed(90000+ci*1000+tr);const w0=K.CH.w,key=K.WEAP[w0].pair;let locked=false,rd=-1;
                  for(let lv=1;lv<=LV;lv++){S.lv=lv;const cs2=K.offers(3);
                    let pick=cs2.find(o=>o.t==='p'&&o.k===key&&!S.ps[key])||cs2.find(o=>o.t==='w'&&o.k===w0);
                    if(!pick){const ps=cs2.filter(o=>o.t==='p'&&o.k!=='rev');if(ps.length)pick=ps[Math.floor(Math.random()*ps.length)];}
                    if(pick){if(pick.t==='w')S.w[pick.k]=Math.min(8,(S.w[pick.k]||0)+1);else S.ps[pick.k]=Math.min(K.pmax(pick.k),(S.ps[pick.k]||0)+1);}
                    if(rd<0&&S.ps[key]&&(S.w[w0]||0)>=8)rd=lv;
                    if(!S.ps[key]&&K.slotP()>=K.SLOTP&&!K.isKeyNew(key))locked=true;}
                  if(locked)lock++;if(S.ps[key])got++;ready.push(rd>0?rd:LV+1);}
                res.push({ck,lock,got,trials,ready:ready.sort((a,b)=>a-b)});});return res;}"""
            M = await ev(MC, [CH, 100, 120])
            tot = sum(m['trials'] for m in M); lock = sum(m['lock'] for m in M); got = sum(m['got'] for m in M)
            import statistics
            med = statistics.median([v for m in M for v in m['ready']])
            print('  (FOCUS %d판) 잠김 %d (%.2f%%) · 열쇠 얻음 %d/%d · 준비 중앙값 Lv%s' % (tot, lock, 100.0 * lock / tot, got, tot, med))
            check('잠김(칸 꽉 참 + 열쇠 없음) 0%', lock == 0, lock)
            check('열쇠는 거의 항상 얻는다(≥ 99%)', got / tot >= .99, got / tot)
            check('페이지 오류 0', not errs, errs[:3])
            await b.close()
    finally:
        srv.close()
        try: os.remove(os.path.join(ROOT, NEW))
        except Exception: pass
    print('\n검사 %d개 · 실패 %d' % (CHECKS[0], len(FAILS)))
    for f in FAILS: print('  ✗', f)
    sys.exit(1 if FAILS else 0)

asyncio.run(main())
