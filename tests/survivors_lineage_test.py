# -*- coding: utf-8 -*-
"""🧬 빌드 계열 시너지 시험 (2026-10-18 사장님 지시 「계열 시너지로 진행해」)
   사용: python3 tests/survivors_lineage_test.py [--only 가,나,...]
   가  분류표 완전성 — 모든 무기가 최소 1계열 · 미지 키 없음 · 계열마다 크기/공용 수 하한 · 부 계열은 주 계열과 다름
   나  단계 켜짐 — 2/4/6개 = 1/2/3단계 · 각성한 무기도 셈 · 무기를 잃으면 단계가 내려감 · 계열 보너스를 끄면(LINCFG.on=0) 전부 0
   다  보너스가 실제로 그 경로에 반영 — 탄막: 투사체 속도·곱빼기(실제 발사 개수)·쿨타임 / 광역: 범위·피해 / 설치: 끈기·피해 / 근접: 받는 피해·이동속도 / 단일: 치명타 확률·배율·피해
   라  계열 보너스가 켜지기 전엔 기존과 비트 동일 — 이 작업 전 커밋(BASE)과 같은 판(무기 1개 = 어떤 계열도 2개에 못 미침)을 18캐릭터 × 600프레임 돌려 지문 비교
   마  기존 주제 세트 불변 — BASE 의 SYN 표가 그대로 들어 있고 · 모든 세트가 (계열 끈 채) 예전과 같은 합을 내며 · 새 세트 3개가 있다
   바  표시 — 레벨업 카드 한 줄 · 일시정지 진행도 · 도감 항목(무기마다 계열)·안내 자료
   사  이어하기 왕복 — 저장 → 복구 뒤에도 같은 계열 단계·같은 식 값
   아  전부 끼워 돌리기 — 18캐릭터 × 5계열(6개 꽉 채움) × 각성 유/무 × 레벨 1/8 × 곱빼기 0/5 를 돌려 오류·NaN 이 없는지
   자  변이 — 식에서 계열 읽는 줄 하나씩을 지운 사본을 (다)에 넣으면 반드시 빨갛게 된다
   임시 사본 survivors_lt_*.html 을 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, re, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
BASE_REV = 'a112f9e'   # 이 작업 직전 커밋
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:500] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
def want(s): return ONLY is None or s in ONLY
HOOK = r"""
const T_=f=>{try{return f();}catch(e){return null;}};   // BASE(계열 이전 커밋) 사본에도 같은 훅을 꽂는다 — 없는 이름은 null
window.__L={LINEAGE:T_(()=>LINEAGE),LIN:T_(()=>LIN),LINT:T_(()=>LINT),LINN:T_(()=>LINN),LINCFG:T_(()=>LINCFG),linCnt:T_(()=>linCnt),linTier:T_(()=>linTier),linHint:T_(()=>linHint),linHtml:T_(()=>linHtml),linFxText:T_(()=>linFxText),PS,DUR,critChance,critMul,takenMul,moveMul,areaMul,dmgMul,cdMul,RES,pauseGame,buildHtml,cdxEntries,cdxView,SYN,WEAP,PASS,CHARS,
 get S(){return S},get state(){return state},set state(v){state=v},get keys(){return keys},set keys(v){keys=v},shots,enemies,pv,xpMul,LK,
 setCH(k){CH=CHARS.find(c=>c.k===k)}};
window.__fp=function(){const S=__L.S;let ex=0,ey=0,eh=0,n=0;for(const e of __L.enemies.a)if(e.on){n++;ex+=e.x;ey+=e.y;eh+=e.hp;}
 let sh=0;for(const s of __L.shots.a)if(s.on)sh++;
 return JSON.stringify([+S.t.toFixed(4),S.kills,S.lv,+S.xp.toFixed(3),+S.p.x.toFixed(3),+S.p.y.toFixed(3),+S.p.hp.toFixed(3),n,+ex.toFixed(2),+ey.toFixed(2),+eh.toFixed(2),sh]);};
window.__go=function(n,dt){dt=dt||1/30;for(let i=0;i<n;i++){const st=__L.state;if(st==='result')break;
  if(st==='lvup'){__p6x.pick(__p6x.CUR[0]);continue;} if(st!=='play'){__p6x.resume();continue;}
  const S=__L.S;S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;__L.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];__p6x.update(dt);}return __L.state;};
"""
SEEDJS = """(()=>{const mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
 Math.random=mb(%d);window.requestAnimationFrame=()=>0;window.cancelAnimationFrame=()=>{};window.AudioContext=undefined;window.webkitAudioContext=undefined;
 try{localStorage.setItem('p6_fx','0');}catch(e){}})();"""
ROOT = H.ROOT
def mk(dst, src='survivors.html'):
    return H.make_copy(src=src, dst=dst, extra='\n' + HOOK)
async def page(b, port, name, seed=7):
    ctx = await b.new_context(viewport={'width': 1000, 'height': 700})
    await ctx.add_init_script(SEEDJS % (0x5eed0000 ^ seed))
    errs = []
    async def route(r):
        if r.request.url.startswith('http://127.0.0.1:%d/' % port): await r.continue_()
        else: await r.abort()
    await ctx.route('**/*', route)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)[:300]))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text[:300]) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/%s' % (port, name))
    await pg.wait_for_function('window.__L!==undefined&&window.__p6x!==undefined', polling=50, timeout=20000)
    return ctx, pg, errs

# ── 다: 효과 검사 (변이 시험에도 그대로 쓴다) ─────────────────────────────────────────────────────────────────
EFFECT_JS = r"""()=>{const L=__L,x=__p6x,out={};
 x.start();const S=L.S;
 const members=k=>Object.keys(L.LINEAGE).filter(w=>L.LINEAGE[w].includes(k)&&!L.WEAP[w].only);
 const set=(k,n)=>{S.w={};for(const w of members(k).slice(0,n))S.w[w]=1;x.synCalc();};
 const snap=()=>({ps:L.PS(),dur:L.DUR(),cc:L.critChance(),cm:L.critMul(),tk:L.takenMul(),mv:L.moveMul(),ar:L.areaMul(),dm:L.dmgMul(),cd:L.cdMul(),amt:S.syn.amt});
 // 기준선: 아무 계열도 안 켠 상태(무기 1개)
 S.w={feed:1};x.synCalc();const b0=snap();
 const R={};
 for(const k of ['bar','aoe','zone','mel','one']){set(k,4);const a=snap();set(k,2);const a2=snap();R[k]={a,a2,n:members(k).length};}
 out.b0=b0;out.R=R;return out;}"""
def effect_verdict(r):
    b0, R = r['b0'], r['R']; bad = []
    def up(x, y): return y > x + 1e-9
    def dn(x, y): return y < x - 1e-9
    for k, f in (('bar', 'ps'), ('zone', 'dur'), ('one', 'cc'), ('one', 'cm'), ('aoe', 'ar'), ('mel', 'mv')):
        if not up(b0[f], R[k]['a'][f]): bad.append('%s→%s 안 올랐다' % (k, f))
    if not dn(b0['tk'], R['mel']['a']['tk']): bad.append('mel→tk 안 내려갔다')
    if not dn(b0['cd'], R['bar']['a']['cd']): bad.append('bar→cd(쿨타임) 안 줄었다')
    if R['bar']['a']['amt'] != 1: bad.append('bar 4개 → amt 1 이어야 한다: %s' % R['bar']['a']['amt'])
    for k, f in (('aoe', 'dm'), ('zone', 'dm'), ('one', 'dm')):
        if not up(b0[f], R[k]['a'][f]): bad.append('%s→%s 안 올랐다' % (k, f))
    for k in R:
        if not (R[k]['a2'] and R[k]['n'] >= 4): bad.append('%s 공용 무기 4개 이상 필요' % k)
    # 4개가 2개보다 크거나 같다(단계가 오를수록 안 약해진다)
    for k, f, sgn in (('bar', 'ps', 1), ('aoe', 'ar', 1), ('zone', 'dur', 1), ('one', 'cc', 1), ('mel', 'mv', 1)):
        if R[k]['a'][f] < R[k]['a2'][f] - 1e-9: bad.append('%s %s 단계가 올랐는데 약해졌다' % (k, f))
    return bad

async def main():
    srv = H.Srv()
    mk('survivors_lt_a.html')
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await page(b, srv.port, 'survivors_lt_a.html')
        # ── 가 ──
        if want('가'):
            r = await pg.evaluate("""()=>{const L=__L,W=Object.keys(L.WEAP),cnt={},com={};
              const miss=W.filter(w=>!L.LINEAGE[w]),unk=Object.keys(L.LINEAGE).filter(w=>!L.WEAP[w]);
              const badk=[],dup=[];for(const w in L.LINEAGE){const a=L.LINEAGE[w];if(a.length<1||a.length>2)badk.push(w);for(const k of a)if(!L.LIN[k])badk.push(w+':'+k);if(a.length===2&&a[0]===a[1])dup.push(w);}
              for(const w of W)for(const k of (L.LINEAGE[w]||[])){cnt[k]=(cnt[k]||0)+1;if(!L.WEAP[w].only)com[k]=(com[k]||0)+1;}
              return {n:W.length,miss,unk,badk,dup,cnt,com,lins:Object.keys(L.LIN),tiers:Object.keys(L.LINT).map(k=>L.LINT[k].length)};}""")
            check('가1 모든 무기가 최소 1계열(%d종)' % r['n'], not r['miss'], r['miss'])
            check('가2 분류표에 없는 무기 키 없음', not r['unk'], r['unk'])
            check('가3 계열 키가 LIN 에 있고 한 무기 1~2계열', not r['badk'], r['badk'])
            check('가4 부 계열이 주 계열과 같지 않다', not r['dup'], r['dup'])
            check('가5 계열 5개 · 단계표 3칸씩', len(r['lins']) == 5 and all(t == 3 for t in r['tiers']), r)
            check('가6 계열마다 무기 9종 이상 · 공용 4종 이상(6칸을 채울 수 있다)', all(r['cnt'].get(k, 0) >= 9 and r['com'].get(k, 0) >= 4 for k in r['lins']), r)
            check('가7 계열 크기 격차 2배 이내', max(r['cnt'].values()) <= 2 * min(r['cnt'].values()), r['cnt'])
            print('   계열별 무기 수', r['cnt'], '· 공용', r['com'])
        # ── 나 ──
        if want('나'):
            r = await pg.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S,res={};
              const m=Object.keys(L.LINEAGE).filter(w=>L.LINEAGE[w].includes('one')&&!L.WEAP[w].only);
              const T=()=>S.syn.lt.one;const set=n=>{S.w={};for(const w of m.slice(0,n))S.w[w]=1;x.synCalc();return T();};
              res.t=[0,1,2,3,4,5,6].map(set);
              set(4);S.ev[m[0]]=1;x.synCalc();res.ev=T();S.ev={};
              set(4);delete S.w[m[1]];x.synCalc();res.lost=T();
              set(6);res.six=T();res.pct=S.syn.crit;
              L.LINCFG.on=0;x.synCalc();res.off=T();res.offc=S.syn.crit;L.LINCFG.on=1;x.synCalc();res.on=T();
              S.w={};x.synCalc();res.empty=Object.values(S.syn.lt).every(v=>v===0);
              return res;}""")
            check('나1 단계: 0·1개=0 · 2~3개=1 · 4~5개=2 · 6개=3', r['t'] == [0, 0, 1, 1, 2, 2, 3], r['t'])
            check('나2 각성한 무기도 한 개로 센다', r['ev'] == 2, r['ev'])
            check('나3 무기를 잃으면 단계가 내려간다(4개→3개)', r['lost'] == 1, r['lost'])
            check('나4 6개 = 3단계 · 치명타 확률 +12%p', r['six'] == 3 and abs(r['pct'] - .12) < 1e-9, r)
            check('나5 LINCFG.on=0 이면 전부 0 · 다시 켜면 돌아온다', r['off'] == 0 and r['offc'] == 0 and r['on'] == 3, r)
            check('나6 무기가 없으면 전 계열 0', r['empty'])
        # ── 다 ──
        if want('다'):
            r = await pg.evaluate(EFFECT_JS)
            bad = effect_verdict(r)
            check('다1 계열별 보너스가 해당 식에 반영(PS·DUR·치명타·받는 피해·이동·범위·피해·쿨타임·곱빼기)', not bad, bad)
            # 곱빼기 +1 이 진짜 발사 개수를 늘리나: 사료 투척(곱빼기를 받는 무기)의 첫 발사 수 — 탄막 4개 vs 계열 끔
            async def volley(on):
                c2, p2, e2 = await page(b, srv.port, 'survivors_lt_a.html', seed=11)
                n = await p2.evaluate("""on=>{const L=__L,x=__p6x;x.start();const S=L.S;L.LINCFG.on=on;S.w={feed:3,shrimp:1,can:1,rkt:1};x.synCalc();
                  let best=0;for(let i=0;i<90;i++){S.p.hp=S.p.mhp;x.update(1/30);let n=0;for(const s of L.shots.a)if(s.on)n++;best=Math.max(best,n);}return {best,amt:S.syn.amt,pv:L.pv('amt')};}""", on)
                await c2.close(); return n
            a, o = await volley(1), await volley(0)
            check('다2 탄막 4개: 곱빼기 +1 이 켜지고 사료 투척 개수가 늘어난다', a['amt'] == 1 and o['amt'] == 0 and a['best'] > o['best'], (a, o))
        # ── 마 ──
        if want('마'):
            base = subprocess.run(['git', 'show', BASE_REV + ':survivors.html'], cwd=ROOT, capture_output=True, text=True).stdout
            open(os.path.join(ROOT, 'survivors_lt_base_src.html'), 'w', encoding='utf-8').write(base)
            mk('survivors_lt_b.html', 'survivors_lt_base_src.html')
            c3, p3, e3 = await page(b, srv.port, 'survivors_lt_b.html')
            sb = await p3.evaluate("()=>__L.SYN.map(y=>({k:y.k,req:y.req,fx:y.fx}))")
            sn = await pg.evaluate("()=>__L.SYN.map(y=>({k:y.k,req:y.req,fx:y.fx}))")
            await c3.close()
            nb = {y['k']: y for y in sn}
            check('마1 기존 세트 %d개가 그대로(키·재료·효과)' % len(sb), all(y['k'] in nb and nb[y['k']] == y for y in sb), [y['k'] for y in sb if y['k'] not in nb or nb[y['k']] != y])
            new = [y for y in sn if y['k'] not in {z['k'] for z in sb}]
            want_new = {('frost', 'can'): {'xp': .1, 'dmg': .06}, ('snipe', 'kbd'): {'cd': .08}, ('hole', 'gacha'): {'luck': 1, 'dmg': .06}}
            check('마2 새 세트 3개(얼음·저격·블랙홀) 재료·효과', len(new) == 3 and all(want_new.get(tuple(y['req'])) == y['fx'] for y in new), new)
            r = await pg.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S;L.LINCFG.on=0;const bad=[];
              for(const y of L.SYN){S.w={};for(const k of y.req)S.w[k]=1;x.synCalc();
                const exp={dmg:0,cd:0,area:0,xp:0,luck:0};for(const z of L.SYN)if(z.req.every(k=>S.w[k]))for(const q in z.fx)exp[q]+=z.fx[q];
                for(const q in exp)if(Math.abs(S.syn[q]-exp[q])>1e-12)bad.push(y.k+':'+q);
                if(!S.synOn.includes(y.k))bad.push(y.k+':off');
                for(const q of ['pspd','amt','dur','crit','crm','tk','mv'])if(S.syn[q]!==0)bad.push(y.k+':'+q+'!=0');}
              return {n:L.SYN.length,bad};}""")
            check('마3 계열을 끄면 모든 세트(%d개)가 예전과 같은 합 · 새 키는 0' % r['n'], not r['bad'], r['bad'])
            # 새 세트도 실제 효과가 읽힌다(경험치·행운·쿨타임)
            r = await pg.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S;L.LINCFG.on=0;const o={};
              S.w={feed:1};x.synCalc();const b={xp:L.xpMul(),lk:L.LK(),cd:L.cdMul(),dm:L.dmgMul()};
              S.w={frost:1,can:1};x.synCalc();o.xp=L.xpMul()/b.xp;o.dm=L.dmgMul()/b.dm;
              S.w={snipe:1,kbd:1};x.synCalc();o.cd=L.cdMul()/b.cd;
              S.w={hole:1,gacha:1};x.synCalc();o.lk=L.LK()-b.lk;o.dm2=L.dmgMul()/b.dm;return o;}""")
            check('마4 새 세트가 식에 읽힌다(경험치 +10%·피해 +6% / 쿨타임 -8% / 행운 +1·피해 +6%)',
                  abs(r['xp'] - 1.1 / 1.0) < 1e-9 * 1e3 and abs(r['dm'] - 1.06) < 1e-6 and abs(r['cd'] - .92) < 1e-6 and r['lk'] == 1 and abs(r['dm2'] - 1.06) < 1e-6, r)
        # ── 라 ──
        if want('라'):
            base_ok = os.path.exists(os.path.join(ROOT, 'survivors_lt_b.html'))
            if not base_ok:
                base = subprocess.run(['git', 'show', BASE_REV + ':survivors.html'], cwd=ROOT, capture_output=True, text=True).stdout
                open(os.path.join(ROOT, 'survivors_lt_base_src.html'), 'w', encoding='utf-8').write(base)
                mk('survivors_lt_b.html', 'survivors_lt_base_src.html')
            chars = await pg.evaluate("()=>__L.CHARS.map(c=>({k:c.k,boss:!!c.boss,shop:!!c.shop}))")
            same = 0; diffs = []
            for c in chars:
                fps = []
                for name in ('survivors_lt_b.html', 'survivors_lt_a.html'):
                    c4, p4, e4 = await page(b, srv.port, name, seed=21)
                    fp = await p4.evaluate("""k=>{const x=__p6x;if(window.__L.CHARS.find(c=>c.k===k).shop)x.SRVUNL.add(k);if(__L.CHARS.find(c=>c.k===k).boss){const g=x.getProg();g.bk[k]=1;x.setProg(g);}
                      __L.setCH(k);x.start();__go(600);return __fp();}""", c['k'])
                    fps.append(fp); await c4.close()
                if fps[0] == fps[1]: same += 1
                else: diffs.append((c['k'], fps))
            check('라1 계열이 안 켜진 판(무기 1개) %d캐릭터 × 600프레임이 BASE 와 지문까지 같다' % len(chars), same == len(chars), diffs[:2])
            # 켜진 판은 달라야 정상(보너스가 실제로 있다는 반대 증거)
            fps = []
            for name in ('survivors_lt_b.html', 'survivors_lt_a.html'):
                c4, p4, e4 = await page(b, srv.port, name, seed=21)
                fps.append(await p4.evaluate("""()=>{const x=__p6x;x.start();const S=__L.S;S.w={feed:1,shrimp:1,can:1,rkt:1};x.synCalc();__go(600);return __fp();}"""))
                await c4.close()
            check('라2 (반대 증거) 탄막 4개를 쥔 판은 BASE 와 달라진다', fps[0] != fps[1])
        # ── 바 ──
        if want('바'):
            r = await pg.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S;S.w={feed:2,shrimp:1};x.synCalc();
              const c1=x.cardOf({t:'w',k:'can',l:0}),c2=x.cardOf({t:'w',k:'feed',l:2});
              S.w={feed:2,shrimp:1,can:1,rkt:1};x.synCalc();const hb=L.buildHtml();
              const e=L.cdxEntries().filter(q=>q.cat==='w');const lin=e.filter(q=>q.lin&&q.lin.length);
              return {c1:c1.ds,c1ty:c1.ty,c2:c2.ds,hb,nw:e.length,nlin:lin.length,one:e.find(q=>q.key==='w:snipe').lin,sub:(window.__cdx&&window.__cdx.lin)?window.__cdx.lin().length:-1};}""")
            check('바1 새 무기 카드에 「🔫 탄막 계열 (내가 2→3/4)」', '탄막 계열 (내가 2→3/4)' in r['c1'] and '🔫' in r['c1ty'], (r['c1'][-200:], r['c1ty']))
            check('바2 무기 강화 카드에도 계열 줄 (내가 2/4)', '탄막 계열 (내가 2/4)' in r['c2'], r['c2'][-150:])
            check('바3 일시정지 화면에 계열 진행도(4/6 · 2단계 · 다음 6개 → …)', '빌드 계열' in r['hb'] and '🔫 탄막 4/6 · 2단계' in r['hb'] and '다음 단계 6개' in r['hb'], re.sub('<[^>]+>', ' ', r['hb'])[-500:])
            check('바4 도감 무기 41종 전부 계열이 있다', r['nlin'] == r['nw'], (r['nlin'], r['nw']))
            check('바5 도감 다리에서 계열 안내 5개', r['sub'] == 5, r['sub'])
        # ── 사 ──
        if want('사'):
            r = await pg.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S;S.w={feed:3,shrimp:2,can:1,rkt:1,kbd:1};S.hp&&0;x.synCalc();
              const a={lt:JSON.stringify(S.syn.lt),ps:L.PS(),amt:S.syn.amt,cc:L.critChance()};
              L.pauseGame();const text=localStorage.getItem(L.RES.KEY);
              if(!text)return {err:'no-save'};
              S.syn={dmg:0,cd:0,area:0,xp:0,luck:0,pspd:0,amt:0,dur:0,crit:0,crm:0,tk:0,mv:0};__L.state='title';const ok=L.RES.restore(text);
              const S2=__L.S;const b={lt:JSON.stringify(S2.syn.lt),ps:L.PS(),amt:S2.syn.amt,cc:L.critChance(),ok};return {a,b};}""")
            check('사1 저장 → 복구 뒤에도 계열 단계·식 값이 같다', 'err' not in r and r['b']['ok'] and r['a'] == {k: v for k, v in r['b'].items() if k != 'ok'}, r)
        # ── 아 ──
        if want('아'):
            chars = await pg.evaluate("()=>__L.CHARS.map(c=>({k:c.k,w:c.w,boss:!!c.boss,shop:!!c.shop}))")
            tot = 0; bad = []
            for ch in chars:
                for lin in ('bar', 'aoe', 'zone', 'mel', 'one'):
                    for ev in (0, 1):
                        for lv, am in ((1, 0), (8, 5)):
                            c5, p5, e5 = await page(b, srv.port, 'survivors_lt_a.html', seed=31 + tot)
                            tot += 1
                            r = await p5.evaluate("""a=>{const x=__p6x,L=__L;if(a.ch.shop)x.SRVUNL.add(a.ch.k);if(a.ch.boss){const g=x.getProg();g.bk[a.ch.k]=1;x.setProg(g);}
                              L.setCH(a.ch.k);x.start();const S=L.S;
                              const com=Object.keys(L.LINEAGE).filter(w=>L.LINEAGE[w].includes(a.lin)&&!L.WEAP[w].only);
                              S.w={};S.w[a.ch.w]=a.lv;for(const w of com){if(Object.keys(S.w).length>=L.SLOTW)break;S.w[w]=a.lv;}
                              if(a.ev){let n=0;for(const w in S.w){if(n>=3)break;if(L.WEAP[w].ev){S.ev[w]=1;n++;}}}
                              S.ps.amt=a.am;S.ps.pspd=a.am;S.ps.dur=a.am;x.synCalc();
                              const lt=Object.assign({},S.syn.lt);__go(240);
                              const ok=Number.isFinite(S.p.hp)&&Number.isFinite(S.p.x)&&Number.isFinite(S.t);
                              const sy=Object.values(S.syn).every(v=>typeof v!=='number'||Number.isFinite(v));
                              return {ok,sy,lt,n:Object.keys(S.w).length,t:S.t};}""", {'ch': ch, 'lin': lin, 'ev': ev, 'lv': lv, 'am': am})
                            if errs_of(e5) or not r['ok'] or not r['sy']: bad.append((ch['k'], lin, ev, lv, am, r, errs_of(e5)[:2]))
                            await c5.close()
            check('아1 %d판(18캐릭터×5계열×각성2×레벨2) 오류·NaN 없음' % tot, not bad, bad[:3])
        # ── 자 ──
        if want('자'):
            src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
            muts = {
              'PS 가 syn.pspd 를 안 읽음': ("(pv('pspd')+S.syn.pspd)", "pv('pspd')"),
              'DUR 가 syn.dur 를 안 읽음': ("(pv('dur')+S.syn.dur)", "pv('dur')"),
              'critChance 가 syn.crit 를 안 읽음': ("+critSm()+S.syn.crit;", "+critSm();"),
              'critMul 이 syn.crm 을 안 읽음': ("+.15*(PTV('luck')?1:0)+S.syn.crm;", "+.15*(PTV('luck')?1:0);"),
              'takenMul 이 syn.tk 를 안 읽음': ("csTaken()*(1-S.syn.tk)*", "csTaken()*"),
              'moveMul 이 syn.mv 를 안 읽음': ("+csMove()+S.syn.mv;", "+csMove();"),
              '무기 발사가 syn.amt 를 안 읽음': ("AM=pv('amt')+S.syn.amt;", "AM=pv('amt');"),
              '단계표 합산을 빼먹음': ("if(t){const fx=LINT[k][t-1];for(const q in fx)f[q]+=fx[q];}", ""),
            }
            for nm, (a, bq) in muts.items():
                if src.count(a) != 1:
                    check('자 변이 「%s」 대상 줄 1개' % nm, False, src.count(a)); continue
                open(os.path.join(ROOT, 'survivors_lt_mut_src.html'), 'w', encoding='utf-8').write(src.replace(a, bq))
                mk('survivors_lt_m.html', 'survivors_lt_mut_src.html')
                c6, p6, e6 = await page(b, srv.port, 'survivors_lt_m.html')
                try:
                    r = await p6.evaluate(EFFECT_JS); bad = effect_verdict(r)
                    am = await p6.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S;S.w={feed:3,shrimp:1,can:1,rkt:1};x.synCalc();let best=0;for(let i=0;i<90;i++){S.p.hp=S.p.mhp;x.update(1/30);let n=0;for(const s of L.shots.a)if(s.on)n++;best=Math.max(best,n);}return best;}""")
                except Exception as ex:
                    bad = ['예외 ' + str(ex)[:80]]; am = 0
                # 곱빼기 변이는 발사 개수로만 드러난다
                if nm.startswith('무기 발사'):
                    c7, p7, e7 = await page(b, srv.port, 'survivors_lt_a.html', seed=7)
                    ref = await p7.evaluate("""()=>{const L=__L,x=__p6x;x.start();const S=L.S;S.w={feed:3,shrimp:1,can:1,rkt:1};x.synCalc();let best=0;for(let i=0;i<90;i++){S.p.hp=S.p.mhp;x.update(1/30);let n=0;for(const s of L.shots.a)if(s.on)n++;best=Math.max(best,n);}return best;}""")
                    await c7.close()
                    # 같은 시드에서 정상판보다 개수가 줄어야(=곱빼기 +1 이 안 읽힘) 잡힌 것
                    check('자 변이 「%s」 → 시험이 잡는다' % nm, am < ref, (am, ref))
                else:
                    check('자 변이 「%s」 → 시험이 잡는다' % nm, bool(bad), r)
                await c6.close()
            for f in ('survivors_lt_mut_src.html', 'survivors_lt_m.html'):
                try: os.remove(os.path.join(ROOT, f))
                except OSError: pass
        check('스크립트 오류 없음(본 페이지)', not errs_of(errs), errs_of(errs)[:2])
        await b.close()
    srv.close()
    for f in os.listdir(ROOT):
        if f.startswith('survivors_lt_'):
            try: os.remove(os.path.join(ROOT, f))
            except OSError: pass
    print('실패 %d' % len(FAILS)); return 1 if FAILS else 0
def errs_of(e): return [x for x in e]
sys.exit(asyncio.run(main()))
