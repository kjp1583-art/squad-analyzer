# -*- coding: utf-8 -*-
"""🗝 흐접새우 서바이벌 「패시브 칸 예약(운 개선안 A)」 시험 — 2026-10-10 사장님 지시 「운은 A로 가보자」

   규칙: 패시브 칸 6개 중 마지막 한 칸은, 내 시작 무기(CH.w)의 각성 열쇠 패시브(WEAP[CH.w].pair)를 아직 안 가졌다면 그 패시브만 들어올 수 있다.
         열쇠를 이미 가졌거나 · 봉인했거나 · 부활(칸을 안 쓴다)이면 예약이 없다. 가진 패시브의 레벨업·다른 카드 종류는 그대로.
   사용: nice -n 10 python3 tests/survivors_pairslot_test.py   (종료코드 0 = 전부 통과 · 약 1분)
   가  5칸을 다른 패시브로 채우고 열쇠가 없을 때 — 새 비열쇠 패시브는 절대 안 나오고 열쇠는 나온다(18캐릭터 × 수천 번) · 기준 커밋은 나온다(시험에 이빨이 있다)
   나  열쇠 보유 / 봉인 / 다시 뽑기로 제외 / 부활 / 가진 패시브 레벨업 / 보스 상자 / 다시 뽑기·봉인 보충 / 예약이 풀리는 경우(CH.w 없음 · 열쇠가 PASS 에 없음)
   다  예약이 안 걸리는 상황에서는 기준 커밋과 카드 열도 난수 사용 횟수도 비트까지 같다(같은 시드로 두 사본을 나란히)
   라  몬테카를로 — FOCUS 정책(내 무기·열쇠 카드가 보이면 고르고 나머지는 무작위 패시브)으로 「칸이 꽉 찼는데 열쇠가 없는」 잠김 비율: 기준 ~20% → 0%(< 0.5%) · 준비 속도는 그대로
   마  18캐릭터 전부 열쇠가 PASS 에 있고 부활이 아니라 예약이 정상 동작한다
   바  화면 — 레벨업 창 한 줄(칸이 거의 찼을 때만) · 일시정지 패시브 칸 표시 · 칸 수 숫자는 그대로 6 · 열쇠를 가지면 사라진다
   임시 사본 survivors_pairslot_t.html · survivors_pairslot_tb.html(기준 커밋)을 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, subprocess, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
BASE_COMMIT = os.environ.get('FX_BASE_COMMIT', 'edf2155')
NEW, OLD, OLDSRC = 'survivors_pairslot_t.html', 'survivors_pairslot_tb.html', 'survivors_pairslot_tb_src.html'
FAILS = []; CHECKS = [0]
def check(n, c, x=''):
    CHECKS[0] += 1
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:900] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)

EXTRA = r"""
window.__K={PASS,SLOTP,SLOTW,MAXLV,get CH(){return CH},CHARS,WEAP,offers,reroll,banCard,openLvup,drawCards,applyUp,slotP,pv,pmax,get CUR(){return CUR},set CUR(v){CUR=v},
  keyRsv:typeof keyRsv==='function'?keyRsv:null,keyPassOf:typeof keyPassOf==='function'?keyPassOf:null,buildHtml,ownHtml,pauseGame,openChest,REV_LV,
  seed(s){let a=s>>>0;window.__rn=0;Math.random=()=>{window.__rn++;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}};
"""

# 모든 시험 공용: 한 캐릭터로 새 판을 만들고 패시브를 채운다(레벨 1)
SETUP = r"""
window.__setup=(ck,o)=>{o=o||{};const x=window.__p6x,K=window.__K;x.CH_set(ck);x.newRun();x.state='play';const S=x.S;
  S.lv=o.lv||10;S.rr=S.ban=0;S.banned=(o.banned||[]).slice();S.dly=null;
  const key=K.keyPassOf?K.keyPassOf():K.PASS[K.WEAP[K.CH.w].pair]?K.WEAP[K.CH.w].pair:null;
  const others=Object.keys(K.PASS).filter(k=>k!=='rev'&&k!==key);
  S.ps={};let n=o.fill===undefined?5:o.fill;
  // 채우는 패시브는 캐릭터마다 다르게(돌려 가며) 고른다
  const off=o.off||0;for(let i=0;i<others.length&&n>0;i++){const k=others[(i+off)%others.length];S.ps[k]=1;n--;}
  if(o.key)S.ps[key]=o.key;if(o.rev)S.ps.rev=1;if(o.psLv)for(const k in S.ps)S.ps[k]=Math.min(o.psLv,K.pmax(k));
  return {key,np:K.slotP(),others,has:Object.keys(S.ps)};};
window.__tally=(n,reps,excl,own)=>{const x=window.__p6x,K=window.__K,S=x.S;const key=K.CH.w&&K.WEAP[K.CH.w].pair;const t={newNonKey:0,newNonKeyList:{},key:0,pUp:0,w:0,other:0,total:0,rev:0};
  for(let i=0;i<reps;i++){const cs=K.offers(n||3,excl||null,own||false);for(const o of cs){t.total++;
    if(o.t==='p'){const had=(S.ps[o.k]||0)>0;if(o.k==='rev'){t.rev++;continue;}if(o.k===key&&!had)t.key++;else if(!had){t.newNonKey++;t.newNonKeyList[o.k]=(t.newNonKeyList[o.k]||0)+1;}else t.pUp++;}
    else if(o.t==='w')t.w++;else t.other++;}}
  return t;};
"""

async def main():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA + SETUP)
    old_src = subprocess.run(['git', 'show', BASE_COMMIT + ':survivors.html'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout
    open(os.path.join(ROOT, OLDSRC), 'w', encoding='utf-8').write(old_src)
    H.make_copy(src=OLDSRC, dst=OLD, extra=EXTRA + SETUP)
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, w=412, h=860, page=NEW)
            ctxo, pgo, erro = await H.new_page(b, srv.port, w=412, h=860, page=OLD)
            ev = lambda p_, js, a=None: p_.evaluate(js, a)
            CH = await ev(pg, "()=>window.__K.CHARS.map(c=>c.k)")
            info = await ev(pg, "()=>Object.fromEntries(window.__K.CHARS.map(c=>[c.k,[c.w,window.__K.WEAP[c.w]&&window.__K.WEAP[c.w].pair]]))")
            print('── 마 18캐릭터 · 열쇠 패시브 ──')
            check('캐릭터 18명', len(CH) == 18, len(CH))
            PASSK = await ev(pg, "()=>Object.keys(window.__K.PASS)")
            check('18캐릭터 전부 시작 무기가 있고 그 각성 열쇠(pair)가 PASS 에 있다', all(w and p in PASSK for (w, p) in info.values()), {k: v for k, v in info.items() if not (v[0] and v[1] in PASSK)})
            check('열쇠가 부활(칸을 안 쓰는 패시브)인 캐릭터는 없다 — 예약이 늘 의미가 있다', all(p != 'rev' for (w, p) in info.values()), [k for k, v in info.items() if v[1] == 'rev'])
            R0 = await ev(pg, "(cs)=>cs.map(ck=>{const s=window.__setup(ck,{fill:0});const K=window.__K;return [ck,s.key,K.keyPassOf(),K.keyRsv()]})", CH)
            check('판 시작 직후 18캐릭터 모두 예약이 걸린다(keyRsv = 시작 무기의 열쇠)', all(k == a == bb for (_, k, a, bb) in R0), R0[:3])

            print('── 가 5칸을 다른 패시브로 채운 뒤 ──')
            N = 1500
            RA = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5,off:i*3});window.__K.seed(1000+i);const t=window.__tally(3,N);t.ck=ck;t.np=s.np;return t;})", [CH, N])
            RO = await ev(pgo, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5,off:i*3});window.__K.seed(1000+i);const t=window.__tally(3,N);t.ck=ck;t.np=s.np;return t;})", [CH, N])
            check('판 준비: 18캐릭터 모두 패시브 5칸(열쇠 없음)', all(t['np'] == 5 for t in RA), [t['np'] for t in RA])
            check('새 비열쇠 패시브는 단 한 번도 안 나온다 (18캐릭터 × %d번 × 3장)' % N, all(t['newNonKey'] == 0 for t in RA), [(t['ck'], t['newNonKeyList']) for t in RA if t['newNonKey']][:3])
            check('열쇠 패시브는 나온다 (캐릭터마다 %d번 중 5%%↑ 에 한 장 이상 나오는 비율)' % N, all(t['key'] > N * 3 * .02 for t in RA), [(t['ck'], t['key']) for t in RA if t['key'] <= N * 3 * .02])
            check('기준 커밋은 새 비열쇠 패시브가 나온다(시험에 이빨이 있다) — 캐릭터마다 수십 번', all(t['newNonKey'] > 20 for t in RO), [(t['ck'], t['newNonKey']) for t in RO if t['newNonKey'] <= 20][:3])
            check('가진 패시브의 레벨업·무기 카드는 계속 나온다(후보가 줄어든 만큼 오히려 더 자주 — 기준의 90%% 이상)', all(a['pUp'] >= .9 * o_['pUp'] and a['w'] > 0 and o_['w'] > 0 for a, o_ in zip(RA, RO)), [(a['ck'], a['pUp'], o_['pUp']) for a, o_ in zip(RA, RO)][:4])

            print('── 나 경로별 ──')
            S3 = ['brj', 'ssu', 'bbb']
            sj = lambda opts, excl='null', own='false', n=1200: ev(pg, "([cs,o,N,ex,own])=>cs.map((ck,i)=>{const s=window.__setup(ck,o);window.__K.seed(7+i);const t=window.__tally(3,N,ex,own);t.ck=ck;t.np=s.np;return t;})", [S3, opts, n, None, False])
            r = await sj({'fill': 4, 'key': 1})
            check('열쇠를 이미 가졌으면(패시브 5칸) 예약 없음 — 새 패시브가 나온다', all(t['np'] == 5 and t['newNonKey'] > 0 and t['key'] == 0 for t in r), [(t['ck'], t['np'], t['newNonKey']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5});const K=window.__K,S=window.__p6x.S;S.banned=[s.key];K.seed(9+i);const t=window.__tally(3,N);t.ck=ck;t.key2=K.keyRsv();return t;})", [S3, 1200])
            check('열쇠를 봉인했으면 예약 없음 — 새 패시브가 나오고 열쇠는 안 나온다', all(t['newNonKey'] > 0 and t['key'] == 0 and t['key2'] is None for t in r), [(t['ck'], t['newNonKey'], t['key'], t['key2']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5});const K=window.__K;K.seed(11+i);const t=window.__tally(3,N,[s.key]);t.ck=ck;return t;})", [S3, 1200])
            check('다시 뽑기(열쇠 카드를 이번에만 제외)해도 예약은 풀리지 않는다 — 새 비열쇠 패시브 0 · 열쇠는 이번엔 안 나온다', all(t['newNonKey'] == 0 and t['key'] == 0 for t in r), [(t['ck'], t['newNonKey'], t['key']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5,rev:1,lv:30});const K=window.__K;K.seed(13+i);const t=window.__tally(3,N);t.ck=ck;t.np=K.slotP();return t;})", [S3, 1200])
            check('👼 부활을 가졌어도(칸 안 씀) 패시브 5칸 + 열쇠 예약이 그대로 — 새 비열쇠 패시브 0 · 열쇠 나옴', all(t['np'] == 5 and t['newNonKey'] == 0 and t['key'] > 0 for t in r), [(t['ck'], t['np'], t['newNonKey'], t['key']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5,lv:25});const K=window.__K;K.seed(15+i);const t=window.__tally(3,N);t.ck=ck;return t;})", [S3, 1500])
            check('Lv20+ 에 부활 카드는 칸이 꽉 차도 후보로 나온다(예약의 영향 없음) · 새 비열쇠 패시브 0', all(t['newNonKey'] == 0 and t['rev'] > 0 for t in r), [(t['ck'], t['newNonKey'], t['rev']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5,psLv:2});const K=window.__K;K.seed(17+i);const t=window.__tally(3,N);t.ck=ck;return t;})", [S3, 1200])
            check('가진 패시브는 레벨업 카드로 계속 나온다', all(t['pUp'] > 0 for t in r), [(t['ck'], t['pUp']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5});const K=window.__K;K.seed(19+i);const t=window.__tally(3,N,null,true);t.ck=ck;return t;})", [S3, 1200])
            check('보스 상자(own=true)도 같은 규칙 — 새 비열쇠 패시브 0 · 열쇠는 나온다', all(t['newNonKey'] == 0 and t['key'] > 0 for t in r), [(t['ck'], t['newNonKey'], t['key']) for t in r])
            r = await ev(pg, """([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5});const K=window.__K,S=window.__p6x.S;S.rr=1e9;S.ban=1e9;K.seed(21+i);let bad=0,seenKey=0,n=0;const key=s.key;
                for(let j=0;j<N;j++){K.openLvup&&0;K.CUR=K.offers(3);
                  K.reroll();for(const o of K.CUR){if(o.t==='p'&&!S.ps[o.k]&&o.k!=='rev'){if(o.k===key)seenKey++;else bad++;}}
                  {let bi=K.CUR.findIndex(o=>o&&o.k&&o.k!==key);if(bi>=0)K.banCard(bi);}S.banned.length=0;for(const o of K.CUR){if(o&&o.t==='p'&&!S.ps[o.k]&&o.k!=='rev'){if(o.k===key)seenKey++;else bad++;}}n++;}
                return {ck,bad,seenKey,n};})""", [S3, 600])
            check('다시 뽑기(reroll)·봉인 보충(banCard) 경로 수백 번 — 새 비열쇠 패시브 0', all(t['bad'] == 0 for t in r), r)
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5});const K=window.__K,S=window.__p6x.S;const sv=K.CH.w;K.CH.w=undefined;K.seed(23+i);const t=window.__tally(3,N);t.key=K.keyRsv();K.CH.w=sv;t.ck=ck;return t;})", [S3, 1200])
            check('CH.w 가 없으면 예약 없음(막다른 길 방지) — 새 패시브가 나온다', all(t['newNonKey'] > 0 and t['key'] is None for t in r), [(t['ck'], t['newNonKey'], t['key']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5});const K=window.__K;const wp=K.WEAP[K.CH.w],sv=wp.pair;wp.pair='__없는패시브__';K.seed(25+i);const t=window.__tally(3,N);t.keyRsv=K.keyRsv();wp.pair=sv;t.ck=ck;return t;})", [S3, 1200])
            check('열쇠가 PASS 에 없으면 예약 없음 — 새 패시브가 나온다', all(t['newNonKey'] > 0 and t['keyRsv'] is None for t in r), [(t['ck'], t['newNonKey'], t['keyRsv']) for t in r])
            r = await ev(pg, "([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:4});const K=window.__K;K.seed(27+i);const t=window.__tally(3,N);t.ck=ck;t.np=s.np;return t;})", [S3, 1200])
            check('4칸까지는 예약이 안 걸린다 — 새 패시브(열쇠 포함)가 모두 나온다', all(t['newNonKey'] > 0 and t['key'] > 0 for t in r), [(t['ck'], t['newNonKey'], t['key']) for t in r])
            r = await ev(pg, """([cs,N])=>cs.map((ck,i)=>{const s=window.__setup(ck,{fill:5,key:0});const K=window.__K,S=window.__p6x.S;for(const k in S.ps)S.ps[k]=1;
                // 열쇠 카드를 고르면 6칸이 되고, 그 뒤로는 새 패시브가 안 나온다
                K.applyUp({t:'p',k:s.key,l:0});const np=K.slotP();K.seed(29+i);const t=window.__tally(3,N);t.ck=ck;t.np=np;t.rsv=K.keyRsv();return t;})""", [S3, 800])
            check('열쇠를 고르면 6칸이 차고 예약이 사라진다 — 새 패시브 0 · 열쇠 카드 0', all(t['np'] == 6 and t['rsv'] is None and t['newNonKey'] == 0 and t['key'] == 0 for t in r), [(t['ck'], t['np'], t['rsv'], t['newNonKey']) for t in r])
            src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
            check('패시브를 얻는 곳은 applyUp 한 곳 · 카드를 뽑는 곳은 offers 한 곳(레벨업·다시 뽑기·봉인·보스 상자가 모두 거친다)',
                  len(re.findall(r'S\.ps\[o\.k\]=pv\(o\.k\)\+1', src)) == 1 and len(re.findall(r'\boffers\(', src)) == 5, (len(re.findall(r'S\.ps\[o\.k\]=pv\(o\.k\)\+1', src)), len(re.findall(r'\boffers\(', src))))

            print('── 다 예약이 안 걸리는 상황은 기준과 비트까지 같다 ──')
            states = [dict(fill=0), dict(fill=2), dict(fill=4), dict(fill=4, key=1), dict(fill=5, key=1), dict(fill=5, key=3, lv=30), dict(fill=5, rev=1, key=1, lv=30)]
            JS_SEQ = """([cs,states,N])=>{const out=[];cs.forEach((ck,i)=>states.forEach((st,j)=>{const s=window.__setup(ck,Object.assign({off:i*3+j},st));window.__K.seed(4242+i*31+j);
                const seq=[];for(let r=0;r<N;r++){const cs2=window.__K.offers(3,r%7===0?[window.__K.CH.w]:null,r%5===0);seq.push(cs2.map(o=>o.t+':'+(o.k||o.r||'')+':'+(o.l===undefined?'':o.l)).join(','));}
                out.push([ck,j,window.__rn,seq.join('|')]);}));return out;}"""
            A = await ev(pg, JS_SEQ, [CH, states, 60]); B = await ev(pgo, JS_SEQ, [CH, states, 60])
            diff = [(a[0], a[1]) for a, b_ in zip(A, B) if a[3] != b_[3] or a[2] != b_[2]]
            check('예약이 안 걸리는 7가지 상태 × 18캐릭터 × 60번(보스 상자 섞음): 카드 열 · Math.random 호출 횟수가 기준 커밋과 같다 (%d 조합)' % len(A), not diff and len(A) == 18 * len(states), diff[:5])
            # 예약이 걸리는 상태에서는 달라야 한다(비교 장치에 이빨이 있다)
            C1 = await ev(pg, JS_SEQ, [CH[:6], [dict(fill=5)], 60]); C2 = await ev(pgo, JS_SEQ, [CH[:6], [dict(fill=5)], 60])
            check('(대조) 5칸 · 열쇠 없음에서는 기준과 카드 열이 갈린다', sum(1 for a, b_ in zip(C1, C2) if a[3] != b_[3]) >= 5, '')

            print('── 라 몬테카를로 — FOCUS 정책 ──')
            MC = """([cs,trials,LV])=>{const x=window.__p6x,K=window.__K;const res=[];
              cs.forEach((ck,ci)=>{let lock=0,got=0,ready=[],keyAt=[],full=0;
                for(let tr=0;tr<trials;tr++){x.CH_set(ck);x.newRun();x.state='play';const S=x.S;S.dly=null;S.banned=[];S.rr=S.ban=0;S.ps={};S.ev={};
                  const w0=K.CH.w,key=K.WEAP[w0].pair;K.seed(90000+ci*1000+tr);let lockedNow=false,keyLv=-1,rd=-1;
                  for(let lv=1;lv<=LV;lv++){S.lv=lv;
                    const cs2=K.offers(3);
                    let pick=cs2.find(o=>o.t==='p'&&o.k===key&&!S.ps[key])||cs2.find(o=>o.t==='w'&&o.k===w0);
                    if(!pick){const ps=cs2.filter(o=>o.t==='p'&&o.k!=='rev');if(ps.length)pick=ps[Math.floor(Math.random()*ps.length)];}
                    if(pick){if(pick.t==='w')S.w[pick.k]=Math.min(8,(S.w[pick.k]||0)+1);else S.ps[pick.k]=Math.min(K.pmax(pick.k),(S.ps[pick.k]||0)+1);}
                    if(keyLv<0&&S.ps[key])keyLv=lv;
                    if(rd<0&&S.ps[key]&&(S.w[w0]||0)>=8)rd=lv;
                    if(!S.ps[key]&&K.slotP()>=K.SLOTP)lockedNow=true;}
                  if(lockedNow)lock++;if(S.ps[key])got++;keyAt.push(keyLv>0?keyLv:LV+1);ready.push(rd>0?rd:LV+1);}
                res.push({ck,lock,got,trials,keyAt:keyAt.sort((a,b)=>a-b),ready:ready.sort((a,b)=>a-b)});});
              return res;}"""
            TR, LVN = 100, 120
            MN = await ev(pg, MC, [CH, TR, LVN]); MO = await ev(pgo, MC, [CH, TR, LVN])
            ln = sum(r_['lock'] for r_ in MN); lo = sum(r_['lock'] for r_ in MO); tot = sum(r_['trials'] for r_ in MN)
            med = lambda rs, f: statistics.median([v for r_ in rs for v in r_[f]])
            print('  (FOCUS %d판 × 18캐릭터 × %d레벨) 칸 꽉 참 + 열쇠 없음(잠김) — 기준 %d/%d = %.1f%% → 새 %d/%d = %.2f%% · 열쇠를 얻은 중앙값 레벨 기준 %s → 새 %s · 준비(열쇠+무기 Lv8) 중앙값 기준 %s → 새 %s' % (TR, LVN, lo, tot, 100.0 * lo / tot, ln, tot, 100.0 * ln / tot, med(MO, 'keyAt'), med(MN, 'keyAt'), med(MO, 'ready'), med(MN, 'ready')))
            check('기준 커밋은 FOCUS 로도 잠긴다(>5%) — 시험에 이빨이 있다', lo / tot > .05, lo / tot)
            check('새 판은 잠김 < 0.5%% (측정 %.2f%%)' % (100.0 * ln / tot), ln / tot < .005, ln)
            check('열쇠를 얻는 속도는 안 느려진다(못 얻은 판은 %d+ 로 세어 낸 중앙값 레벨: 새 ≤ 기준)' % (LVN + 1), med(MN, 'keyAt') <= med(MO, 'keyAt'), (med(MO, 'keyAt'), med(MN, 'keyAt')))
            check('준비(열쇠 + 시작 무기 Lv8) 중앙값 레벨은 안 늘어난다(+1 이내 · 못 한 판은 %d+ 로 셈)' % (LVN + 1), med(MN, 'ready') <= med(MO, 'ready') + 1, (med(MO, 'ready'), med(MN, 'ready')))

            print('── 바 화면 ──')
            UI = await ev(pg, """()=>{const x=window.__p6x,K=window.__K,out={};
              const s=window.__setup('brj',{fill:5});K.seed(5);
              x.state='lvup';K.openLvup();const hint=document.getElementById('lvKey'),own=document.getElementById('lvOwn').textContent;
              out.lv5={hidden:hint.hidden,txt:hint.textContent,own:/마지막 한 칸은 🗝 열쇠 자리/.test(own),slots:/패시브 5\\/6/.test(own)};
              x.resume&&x.resume();
              window.__setup('brj',{fill:2});x.state='lvup';K.openLvup();out.lv2={hidden:document.getElementById('lvKey').hidden};x.resume&&x.resume();
              window.__setup('brj',{fill:5,key:1});x.state='lvup';K.openLvup();out.held={hidden:document.getElementById('lvKey').hidden,own:/열쇠 자리/.test(document.getElementById('lvOwn').textContent)};x.resume&&x.resume();
              window.__setup('brj',{fill:5});K.pauseGame();out.pause={t:document.getElementById('pInfo').textContent,html:document.getElementById('pInfo').innerHTML};x.resume&&x.resume();
              window.__setup('brj',{fill:5,key:1});K.pauseGame();out.pauseHeld=document.getElementById('pInfo').textContent;x.resume&&x.resume();
              out.help=[...document.querySelectorAll('#title li')].map(l=>l.textContent).join('\\n');
              return out;}""")
            check('레벨업 창: 패시브 5칸 · 열쇠 없음 → 한 줄 안내(쉬운 말) + 내 능력 목록의 패시브 줄에 「마지막 한 칸은 🗝 열쇠 자리」 + 숫자는 5/6 그대로',
                  not UI['lv5']['hidden'] and '마지막 한 칸은 내 무기의 🗝 각성 열쇠 패시브(아직 없을 때)를 위해 남겨 둬요' in UI['lv5']['txt'] and UI['lv5']['own'] and UI['lv5']['slots'], UI['lv5'])
            check('레벨업 창: 패시브 2칸이면 안내 줄을 숨긴다(칸이 거의 찼을 때만)', UI['lv2']['hidden'], UI['lv2'])
            check('레벨업 창: 열쇠를 가졌으면 안내도 「열쇠 자리」 표시도 없다', UI['held']['hidden'] and not UI['held']['own'], UI['held'])
            check('일시정지: 패시브 칸 숫자는 5/6 그대로 + 「마지막 한 칸은 🗝 열쇠 자리」 · 열쇠를 가지면 사라진다', '패시브 5/6' in UI['pause']['t'] and '마지막 한 칸은 🗝 열쇠 자리' in UI['pause']['t'] and '열쇠 자리' not in UI['pauseHeld'], UI['pause']['t'][:200])
            check('도움말: 「마지막 한 칸은 내 무기의 🗝 각성 열쇠 패시브(아직 없을 때)를 위해 남겨 둬요」', '마지막 한 칸은 내 무기의 🗝 각성 열쇠 패시브(아직 없을 때)를 위해 남겨 둬요' in UI['help'], '')
            check('페이지 오류 0', not errs, errs[:3])
            await b.close()
    finally:
        srv.close()
        for f in (NEW, OLD, OLDSRC):
            try: os.remove(os.path.join(ROOT, f))
            except Exception: pass
    print('\n검사 %d개 · 실패 %d' % (CHECKS[0], len(FAILS)))
    for f in FAILS: print('  ✗', f)
    sys.exit(1 if FAILS else 0)

asyncio.run(main())
