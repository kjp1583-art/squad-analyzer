# -*- coding: utf-8 -*-
"""❤️ 흐접새우 서바이벌 「체력 숫자」 시험 — 2026-10-09 사장님 지시 "체력슛자표기 해주고"
   사용: python3 tests/survivors_hpnum_test.py [--full] [--only 가,나,...]   (종료코드 0 = 전부 통과)
     기본 약 3~6분(부하가 높으면 더) · --full 은 Node 합계 점검을 수백 판으로 늘린다
   구성
     가  HUD 문자열(현재 / 최대) · 올림(살아 있으면 최소 1) · 반올림 · 네 자리 숫자 · 문자열이 바뀔 때만 DOM 갱신
     나  HUD 레이아웃 — 7개 화면 크기에서 가로 넘침 0 · 칸 겹침 0 · 숫자가 막대 안에 들어감(분노 게이지·보스 막대를 다 켠 상태)
     다  레벨업 카드 「(최대 체력 지금 → 바뀐 뒤)」 = 실제로 적용한 뒤 값 · 안 바뀌는 카드엔 없음 · 힌트 줄 끝 현재/최대
     라  일시정지 「❤️ 체력 N / M」 + 출처표(기본·용조련사·❤️·🌟·🍚·🗡·🎯) — 합 = 실제 최대 체력, 「기타」 0
     마  최대 체력 출처 합계 = 실제 최대 체력 — 캐릭터 전원 × 시드 × 무작위/강제 카드(Node vm 하네스, 수백 판은 --full)
     바  이어하기 — 저장→복원 뒤 숫자·출처표 동일 · 기준 커밋(352c963) 빌드로 저장한 옛 저장본을 새 빌드에서 불러오기
     사  오늘의 도전 난수열 불변 — 기준 커밋과 새 빌드의 카드 제안 순서·처치·경험치가 같다(표시만 바꿨다)
     아  최대 체력을 바꾸는 코드는 mhpAdd 한 곳뿐(소스 훑기) · 콘솔/페이지 오류 0
   임시 사본 survivors_hpn.html · survivors_hpo.html 에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, subprocess, tempfile, shutil, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
FULL = '--full' in sys.argv
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
BASE_COMMIT = '352c963'
NEW, OLD, OLDSRC = 'survivors_hpn.html', 'survivors_hpo.html', 'survivors_hpo_src.html'
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
def want(sec): return ONLY is None or sec in ONLY

EXTRA_NEW = r"""
window.__X={RES,hud,pauseGame,openLvup,drawCards,setCUR(v){CUR=v},hpText,mhpSrc,mhpPre,mhpGuess,mhpAdd,smHpGain,hpHtml,get RUN(){return RUN},get CH(){return CH}};
"""
EXTRA_OLD = r"""
window.__X={RES,hud,pauseGame,openLvup,drawCards,setCUR(v){CUR=v}};
"""
def prep():
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA_NEW)
    old = subprocess.run(['git', '-C', ROOT, 'show', BASE_COMMIT + ':survivors.html'], capture_output=True, check=True).stdout.decode('utf-8')
    open(os.path.join(ROOT, OLDSRC), 'w', encoding='utf-8').write(old)
    H.make_copy(src=OLDSRC, dst=OLD, extra=EXTRA_OLD)
def cleanup():
    for f in (NEW, OLD, OLDSRC):
        try: os.remove(os.path.join(ROOT, f))
        except Exception: pass

# ── 가 · HUD 문자열 ─────────────────────────────────────────────
HUD_SET = r"""([hp,mhp])=>{const x=__p6x,S=x.S;S.p.hp=hp;S.p.mhp=mhp;__X.hud();const e=document.getElementById('hpt'),b=document.getElementById('hpb');
  const rg=document.createRange();rg.selectNodeContents(e);return {t:e.textContent,sw:rg.getBoundingClientRect().width,cw:e.clientWidth,bw:b.clientWidth,bh:b.getBoundingClientRect().height}}"""
async def sec_hud(b, srv):
    ctx, pg, errs = await H.new_page(b, srv.port, page=NEW)
    await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();}")
    check('[가] 판이 시작되면 HUD 가 보인다', await pg.evaluate("()=>[__p6x.state,getComputedStyle(document.getElementById('hud')).display]") == ['play', 'block'])
    cases = [([161, 230], '161 / 230'), ([100, 100], '100 / 100'), ([0.3, 230], '1 / 230'), ([0.01, 100], '1 / 100'), ([0, 230], '0 / 230'), ([-5, 230], '0 / 230'),
             ([160.2, 229.6], '161 / 230'), ([99.5, 99.5], '100 / 100'), ([1234, 1234], '1234 / 1234'), ([987.4, 1234], '988 / 1234'), ([66, 66], '66 / 66')]
    for (hp, mhp), want_t in cases:
        r = await pg.evaluate(HUD_SET, [hp, mhp])
        check('[가] HUD %s/%s → 「%s」' % (hp, mhp, want_t), r['t'] == want_t, r)
    r = await pg.evaluate(HUD_SET, [1234, 1234])
    check('[가] 네 자리 숫자도 막대 안에 들어간다(글자 폭 %s ≤ 막대 폭 %s)' % (r['sw'], r['bw']), r['sw'] <= r['bw'] - 2, r)
    check('[가] 막대 높이 14px(8px → 14px)', abs(r['bh'] - 14) < 0.6, r)
    # 갱신 횟수: 같은 문자열이면 DOM 을 건드리지 않는다
    r = await pg.evaluate("""()=>{const S=__p6x.S,e=document.getElementById('hpt'),mo=new MutationObserver(()=>{});mo.observe(e,{childList:true,characterData:true,subtree:true});
      S.p.hp=100;S.p.mhp=100;__X.hud();mo.takeRecords();
      for(let i=0;i<300;i++)__X.hud();const idle=mo.takeRecords().length;                                   // 값이 그대로면 0 번
      let changes=0,prev=e.textContent,seq=[100,99.6,99.4,99.4,99.4,50,50,49.2,49.2,49.9,0.2,0.2,100];
      for(const h of seq){S.p.hp=h;__X.hud();for(let k=0;k<20;k++)__X.hud();if(e.textContent!==prev){changes++;prev=e.textContent;}}
      const rec=mo.takeRecords().length;mo.disconnect();return {idle,changes,rec}}""")
    check('[가] 값이 그대로면 DOM 갱신 0번(300프레임)', r['idle'] == 0, r)
    check('[가] DOM 갱신 횟수(%d) ≤ 문자열이 바뀐 횟수(%d)' % (r['rec'], r['changes']), r['rec'] <= r['changes'] and r['changes'] > 0, r)
    check('[가] 콘솔/페이지 오류 0', not errs, errs)
    await ctx.close()

# ── 나 · 레이아웃 ──────────────────────────────────────────────
VIEWS = [(360, 640), (320, 568), (390, 844), (412, 915), (640, 360), (844, 390), (1280, 800)]
LAYOUT = r"""([hp,mhp])=>{const x=__p6x,S=x.S;S.p.hp=hp;S.p.mhp=mhp;
  const rg=document.getElementById('rgw');rg.style.display='block';document.getElementById('rgt').textContent='🔥 분노 100%';
  const bb=document.getElementById('bossb');bb.style.display='block';document.getElementById('bossName').textContent='🦐 흐접새우의 클랜마스터 신림 · 2페이즈 (+2)';
  __X.hud();rg.style.display='block';bb.style.display='block';
  const R=id=>{const r=document.getElementById(id).getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}};
  const ids=['xpb','hrow_','hpb','rgw','bossb'];const hrow=document.querySelector('#hud .hrow');const hr=hrow.getBoundingClientRect();
  const rs={xpb:R('xpb'),hrow:{l:hr.left,t:hr.top,r:hr.right,b:hr.bottom,w:hr.width,h:hr.height},hpb:R('hpb'),rgw:R('rgw'),bossb:R('bossb'),hpt:R('hpt'),hud:R('hud')};
  const btns=['sndBtn','pauseBtn'].map(R);
  const de=document.documentElement,e=document.getElementById('hpt'),rng=document.createRange();rng.selectNodeContents(e);
  return {rs,btns,sx:de.scrollWidth-innerWidth,bsx:document.body.scrollWidth-innerWidth,iw:innerWidth,ih:innerHeight,tsw:rng.getBoundingClientRect().width,tcw:e.clientWidth,t:e.textContent}}"""
def inter(a, b):
    return max(0, min(a['r'], b['r']) - max(a['l'], b['l'])) * max(0, min(a['b'], b['b']) - max(a['t'], b['t']))
async def sec_layout(b, srv):
    for (w, h) in VIEWS:
        for (hp, mhp, ch) in [(1234, 1234, 'psg'), (161, 230, 'brj')]:
            ctx, pg, errs = await H.new_page(b, srv.port, w=w, h=h, page=NEW, mobile=(w < 700))
            await pg.evaluate("(c)=>{__p6x.CH_set(c);__p6x.start();}", ch)
            r = await pg.evaluate(LAYOUT, [hp, mhp]); rs = r['rs']
            order = ['xpb', 'hrow', 'hpb', 'rgw', 'bossb']
            ov = [(a, c, inter(rs[a], rs[c])) for i, a in enumerate(order) for c in order[i + 1:] if inter(rs[a], rs[c]) > 0.5]
            for bt in r['btns']:
                for k in ('hpb', 'rgw', 'bossb'):
                    if inter(bt, rs[k]) > 0.5: ov.append(('btn', k, inter(bt, rs[k])))
            inside = rs['hpt']['l'] >= rs['hpb']['l'] - 0.5 and rs['hpt']['r'] <= rs['hpb']['r'] + 0.5 and rs['hpt']['t'] >= rs['hpb']['t'] - 0.5 and rs['hpt']['b'] <= rs['hpb']['b'] + 0.5
            nm = '%dx%d %s(%d/%d)' % (w, h, ch, hp, mhp)
            check('[나] %s 가로 넘침 0' % nm, r['sx'] <= 0 and r['bsx'] <= 0, (r['sx'], r['bsx']))
            check('[나] %s HUD 칸 겹침 0 (HUD 높이 %dpx / 화면 %d)' % (nm, rs['hud']['h'], r['ih']), not ov, ov)
            check('[나] %s 숫자 「%s」가 막대 안(글자 %s ≤ 폭 %s)' % (nm, r['t'], r['tsw'], r['tcw']), inside and r['tsw'] <= r['tcw'] + 0.5, (rs['hpt'], rs['hpb'], r['tsw'], r['tcw']))
            check('[나] %s 오류 0' % nm, not errs, errs)
            await ctx.close()

# ── 다 · 레벨업 카드 ───────────────────────────────────────────
CARDS = r"""()=>{const x=__p6x,S=x.S,out=[];
  const apply=(o)=>{const a=Math.round(S.p.mhp),pre=__X.mhpPre(o),tag=x.cardOf(o).ds;x.applyUp(o);const b=Math.round(S.p.mhp);
    return {k:o.k,a,b,pre,tag:tag.includes('(최대 체력 '+a+' → '+(a+pre)+')'),hasTag:tag.includes('(최대 체력 '),ok:b===a+pre}};
  for(let i=0;i<5;i++)out.push(apply({t:'p',k:'hp',l:i}));                     // ❤️ 패시브 Lv1~5(+25 씩)
  out.push(apply({t:'pt',k:'pt:hp',p:'hp',l:0}));                              // 🌟 초월 첫 단계(+25)
  out.push(apply({t:'pt',k:'pt:hp',p:'hp',l:1}));                              // 🌟 초월 둘째 단계(최대 체력 변화 없음)
  for(let i=0;i<5;i++)out.push(apply({t:'sm',k:'sm:hp',r:'hp',l:i}));          // 🍚 든든한 밥 5번(12·10·9·7·6)
  for(let i=0;i<3;i++){out.push(apply({t:'tr',k:'tr:glassc',r:'glassc',l:i}));out.push(apply({t:'tr',k:'tr:focus',r:'focus',l:i}));}
  S.p.mhp=66;S.p.hp=66;out.push(apply({t:'tr',k:'tr:glassc',r:'glassc',l:0}));   // 60 아래로는 안 내려간다 → 66 → 60
  out.push(apply({t:'tr',k:'tr:focus',r:'focus',l:0}));                          // 이미 60 → 변화 없음(문구 없음)
  S.p.mhp=100;S.p.hp=100;
  for(const o of [{t:'w',k:Object.keys(x.WEAP)[0],l:0},{t:'co',k:'co:feast',r:'feast'},{t:'heal',k:'heal'},{t:'tr',k:'tr:swift',r:'swift',l:0},{t:'sm',k:'sm:ramen',r:'ramen',l:0}])
    out.push({k:o.k,hasTag:x.cardOf(o).ds.includes('최대 체력 '),pre:0,none:true});
  return out}"""
async def sec_cards(b, srv):
    ctx, pg, errs = await H.new_page(b, srv.port, page=NEW)
    await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();}")
    rs = await pg.evaluate(CARDS)
    bad = [r for r in rs if not r.get('none') and not (r['ok'] and (r['tag'] if r['pre'] else not r['hasTag']))]
    check('[다] 카드 %d장 — 미리 보여 준 「→」 값 = 적용 후 실제 최대 체력, 문구가 있어야 할 때만 있다' % len([r for r in rs if not r.get('none')]), not bad, bad)
    check('[다] 안 바뀌는 카드(무기·일회용·치킨·라면·민첩 거래)엔 최대 체력 문구가 없다', not any(r['hasTag'] for r in rs if r.get('none')), [r for r in rs if r.get('none')])
    seq = [(r['k'], r['a'], r['b']) for r in rs if not r.get('none')]
    check('[다] 든든한 밥 5번 = 100→112→122→131→138→144 (+12·10·9·7·6)', [r['b'] for r in rs if r['k'] == 'sm:hp'] == [x + 0 for x in [r['b'] for r in rs if r['k'] == 'sm:hp']] and
          [r['b'] - r['a'] for r in rs if r['k'] == 'sm:hp'] == [12, 10, 9, 7, 6], seq)
    check('[다] 유리 대포 −12 · 정조준 −10 · 66에서는 60까지만', [r['pre'] for r in rs if r['k'] in ('tr:glassc', 'tr:focus')][-2:] == [-6, 0], seq)
    # 화면: 힌트 줄과 실제 카드 문구
    r = await pg.evaluate("""()=>{const x=__p6x,S=x.S;S.p.mhp=165;S.p.hp=161;S.sm.hp=0;x.state='lvup';__X.setCUR([{t:'p',k:'hp',l:S.ps.hp||0},{t:'sm',k:'sm:hp',r:'hp',l:0},{t:'tr',k:'tr:glassc',r:'glassc',l:0}]);__X.drawCards();x.show('lvup');
      return {hint:document.getElementById('lvHint').textContent,cards:[...document.querySelectorAll('#choices .ch')].map(c=>c.innerText.replace(/\\s+/g,' '))}}""")
    check('[다] 힌트 줄 끝에 「❤️ 161 / 165」', r['hint'].replace('\u00a0', ' ').endswith('❤️ 161 / 165') and '❤️\u00a0161\u00a0/\u00a0165' in r['hint'], r['hint'])   # 줄이 바뀌어도 숫자가 쪼개지지 않게 붙임표 공백
    check('[다] 화면 카드에 「(최대 체력 165 → 190)」·「165 → 177」·「165 → 153」', '(최대 체력 165 → 190)' in r['cards'][0] and '(최대 체력 165 → 177)' in r['cards'][1] and '(최대 체력 165 → 153)' in r['cards'][2], r['cards'])
    check('[다] 오류 0', not errs, errs)
    await ctx.close()

# ── 라 · 일시정지 출처표 ───────────────────────────────────────
PAUSE = r"""(ch)=>{const x=__p6x;x.CH_set(ch);x.start();const S=x.S;
  for(let i=0;i<5;i++)x.applyUp({t:'p',k:'hp',l:i});x.applyUp({t:'pt',k:'pt:hp',p:'hp',l:0});for(let i=0;i<5;i++)x.applyUp({t:'sm',k:'sm:hp',r:'hp',l:i});
  for(let i=0;i<3;i++){x.applyUp({t:'tr',k:'tr:glassc',r:'glassc',l:i});x.applyUp({t:'tr',k:'tr:focus',r:'focus',l:i});}
  S.p.hp=161;__X.pauseGame();
  const rows={};for(const r of document.querySelectorAll('#mhpSrc .mr'))rows[r.dataset.mk]=r.textContent.replace(/\\s+/g,' ').trim();
  return {hp:document.getElementById('pHp').textContent,sum:document.querySelector('#mhpSrc summary').innerText,rows,mhp:S.p.mhp,src:__X.mhpSrc(),by:JSON.parse(JSON.stringify(S.mhpBy)),state:x.state,
    top:document.querySelector('#pInfo .build').firstElementChild.textContent}}"""
async def sec_pause(b, srv):
    for ch in ['brj', 'yj']:
        ctx, pg, errs = await H.new_page(b, srv.port, page=NEW)
        r = await pg.evaluate(PAUSE, ch)
        sm = r['by']
        total = 100 + (40 if ch == 'yj' else 0) + sum(sm.values())
        check('[라] %s 일시정지 첫 줄 「❤️ 체력 161 / %d」' % (ch, r['mhp']), r['hp'] == '161 / %d' % r['mhp'] and r['top'].startswith('❤️ 체력'), r)
        check('[라] %s 출처 합 = 실제 최대 체력(%d), 「기타」 없음' % (ch, r['mhp']), total == r['mhp'] and r['src']['etc'] == 0 and 'etc' not in r['rows'], (total, r))
        check('[라] %s 출처 값: ❤️ +125 · 🌟 +25 · 🍚 +44 · 🗡 −36 · 🎯 −30' % ch, sm.get('hp') == 125 and sm.get('pt') == 25 and sm.get('sm') == 44 and sm.get('glassc') == -36 and sm.get('focus') == -30, sm)
        check('[라] %s 표에 기본 100%s' % (ch, ' · 용조련사 +40' if ch == 'yj' else ''), '100' in r['rows']['base'] and (('+40' in r['rows'].get('ch', '')) if ch == 'yj' else 'ch' not in r['rows']), r['rows'])
        check('[라] %s 접이식(처음엔 접힘) · 요약에 최대 체력 %d' % (ch, r['mhp']), str(r['mhp']) in r['sum'] and await pg.evaluate("()=>document.getElementById('mhpSrc').tagName==='DETAILS'&&!document.getElementById('mhpSrc').open"), r['sum'])
        check('[라] %s 오류 0' % ch, not errs, errs)
        await ctx.close()
    # 90가지 무작위 순서의 거래·패시브: 합이 늘 맞고, 기타는 0
    ctx, pg, errs = await H.new_page(b, srv.port, page=NEW)
    r = await pg.evaluate("""()=>{const x=__p6x;let seed=12345;const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};const bad=[];let n=0;
      for(const ch of x.CHARS.map(c=>c.k)){x.CH_set(ch);x.start();const S=x.S;
        for(let i=0;i<40;i++){const pick=Math.floor(rnd()*5),o=[{t:'p',k:'hp',l:S.ps.hp||0},{t:'pt',k:'pt:hp',p:'hp',l:S.pt.hp||0},{t:'sm',k:'sm:hp',r:'hp',l:S.sm.hp||0},{t:'tr',k:'tr:glassc',r:'glassc',l:S.tr.glassc||0},{t:'tr',k:'tr:focus',r:'focus',l:S.tr.focus||0}][pick];
          if(pick===0&&(S.ps.hp||0)>=5)continue;if(pick===1&&(S.pt.hp||0)>=1)continue;if(pick===2&&(S.sm.hp||0)>=5)continue;if(pick>=3&&(S.tr[o.r]||0)>=3)continue;
          const a=S.p.mhp,pre=__X.mhpPre(o);x.applyUp(o);n++;const m=__X.mhpSrc();if(S.p.mhp!==a+pre||m.etc!==0)bad.push([ch,o.k,a,pre,S.p.mhp,m.etc]);}}
      return {n,bad:bad.slice(0,5)}}""")
    check('[라] 캐릭터 전원 × 무작위 순서 %d회 — 합 어긋남 0 · 미리보기 일치' % r['n'], not r['bad'] and r['n'] > 200, r)
    check('[라] 오류 0', not errs, errs)
    await ctx.close()

# ── 마 · Node 합계 점검 ────────────────────────────────────────
RUN_JS = r"""const vm=require('vm'),fs=require('fs');
const code=fs.readFileSync('sim.js','utf8');
const mk=()=>{const f=function(){};const p=new Proxy(f,{get(t,k){if(k===Symbol.toPrimitive)return()=>0;if(k==='length')return 0;if(k==='width'||k==='height')return 800;if(k==='measureText')return()=>({width:10});if(k==='getContext')return()=>mk();if(k==='children')return[];if(k==='firstElementChild')return mk();if(k==='checked')return false;if(k==='value')return '';if(k==='getBoundingClientRect')return()=>({left:0,top:0,width:800,height:600});return mk();},set(){return true;},apply(){return mk();},construct(){return mk();}});return p;};
const store={};const ls={getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=String(v)},removeItem:k=>{delete store[k]}};
const win={innerWidth:1280,innerHeight:800,devicePixelRatio:1,addEventListener(){},removeEventListener(){},localStorage:ls,sessionStorage:ls,location:{href:'',search:'',hash:'',origin:'x',pathname:'/'},fetch:()=>Promise.reject(new Error('no net')),requestAnimationFrame(){},setTimeout,clearTimeout,setInterval,clearInterval,performance,Date,Math,JSON,Promise,
 screen:{width:1280,height:800},matchMedia:()=>({matches:false,addEventListener(){}}),navigator:{hardwareConcurrency:8,userAgent:'node'},
 document:{getElementById:()=>mk(),createElement:()=>mk(),querySelector:()=>mk(),querySelectorAll:()=>[],addEventListener(){},body:mk(),documentElement:mk(),hidden:false,fonts:{load(){}}},
 Image:function(){return mk()},Audio:function(){return mk()},URL,Uint8Array,Float32Array,Map,Set,console:{log:console.log,warn(){},info(){},error(){}},Symbol,Object,Array,Number,String,Error,isNaN,parseInt,parseFloat,Infinity,NaN,encodeURIComponent,decodeURIComponent,AudioContext:undefined};
win.window=win;win.self=win;win.globalThis=win;
const ctx=vm.createContext(win);
try{vm.runInContext(code,ctx);}catch(e){console.log('LOAD ERR',e.stack.split('\n').slice(0,6).join('\\n'));process.exit(1);}
module.exports=win;"""
AUDIT_JS = r"""const w=require('./run.js');const x=w.__p6x,Q=w.__hp;
const NS=+(process.env.SEEDS||2),SEC=+(process.env.SEC||420),CHS=process.env.CHS?process.env.CHS.split(','):x.CHARS.map(c=>c.k);
let bad=[],runs=0,cards=0,pre=0,chk=0,minMhp=1e9,maxMhp=0,forced=0,pickN=0,natural=0;
const fail=m=>{if(bad.length<20)bad.push(m);};
function check(tag){chk++;const m=Q.mhpSrc();let sum=100+m.ch;for(const r of m.rows)sum+=r[1];
  if(m.mh!==Math.round(x.S.p.mhp)||sum+m.etc!==m.mh)fail(tag+' sum');if(m.etc!==0)fail(tag+' etc='+m.etc+' mhp='+m.mh);
  minMhp=Math.min(minMhp,m.mh);maxMhp=Math.max(maxMhp,m.mh);const t=Q.hpText();if(!/^\d+ \/ \d+$/.test(t))fail(tag+' text '+t);}
for(const ch of CHS)for(let sd=1;sd<=NS;sd++){
  x.CH_set(ch);x.start();runs++;let seed=sd*7919+ch.length*131+ch.charCodeAt(0);const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  const dt=1/20,N=Math.round(SEC/dt);let nextForce=20;
  for(let i=0;i<N;i++){const st=x.state;if(st==='result')break;
    if(st==='lvup'){
      for(const o of x.CUR){cards++;const p=Q.mhpPre(o),d=x.cardOf(o).ds;if(p){pre++;const a=Math.round(x.S.p.mhp),b=Math.round(x.S.p.mhp+p);if(!d.includes('(최대 체력 '+a+' → '+b+')'))fail(ch+' card text '+o.k);}else if(d.includes('(최대 체력 '))fail(ch+' tag on no-change card '+o.k);}
      const o=x.CUR[Math.floor(rnd()*x.CUR.length)];const m0=Math.round(x.S.p.mhp),p=Q.mhpPre(o);if(p)natural++;x.pick(o);pickN++;
      if(Math.round(x.S.p.mhp)!==m0+p)fail(ch+' preview '+o.k+' '+m0+'+'+p+'!='+Math.round(x.S.p.mhp));
      check(ch+' pick');continue;}
    if(st!=='play'){x.resume();continue;}
    const S=x.S;S.p.hp=S.p.mhp;const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
    if(S.t>=nextForce){nextForce+=25+rnd()*40;
      const opts=[];if((S.ps.hp||0)<5)opts.push({t:'p',k:'hp',l:S.ps.hp||0});if(!(S.pt.hp))opts.push({t:'pt',k:'pt:hp',p:'hp',l:0});
      if((S.sm.hp||0)<5)opts.push({t:'sm',k:'sm:hp',r:'hp',l:S.sm.hp||0});for(const r of ['glassc','focus'])if((S.tr[r]||0)<3&&S.p.mhp>70)opts.push({t:'tr',k:'tr:'+r,r,l:S.tr[r]||0});
      if(opts.length){const o=opts[Math.floor(rnd()*opts.length)];const m0=Math.round(S.p.mhp),p=Q.mhpPre(o),d=x.cardOf(o).ds;
        x.applyUp(o);forced++;const m1=Math.round(S.p.mhp);if(m1!==m0+p)fail(ch+' forced preview '+o.k+' '+m0+'+'+p+'!='+m1);if(p&&!d.includes('(최대 체력 '+m0+' → '+(m0+p)+')'))fail(ch+' forced text');check(ch+' forced');}}
    x.update(dt);}
  check(ch+' end');}
console.log(JSON.stringify({runs,cards,preCards:pre,picks:pickN,naturalHpPicks:natural,forced,checks:chk,minMhp,maxMhp,bad}));
process.exit(bad.length?1:0);"""
def sec_node():
    d = tempfile.mkdtemp(prefix='hpnum_')
    try:
        s = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
        m = re.search(r"window\.__p6=\{[^\n]*\};", s); assert m
        s = s.replace(m.group(0), m.group(0) + '\n' + H.HOOK + 'window.__hp={mhpPre,mhpSrc,hpText,hpHtml,mhpGuess,mhpTag,smHpGain,mhpAdd};\n').replace('const INV_CAP=.80;', 'let INV_CAP=.80;')
        blocks = [(mm.start(1), mm.end(1)) for mm in re.finditer(r'<script[^>]*>(.*?)</script>', s, re.S)]
        a, b = [x for x in blocks if '__p6x' in s[x[0]:x[1]]][0]
        open(os.path.join(d, 'sim.js'), 'w', encoding='utf-8').write(s[a:b])
        open(os.path.join(d, 'run.js'), 'w', encoding='utf-8').write(RUN_JS)
        open(os.path.join(d, 'audit.js'), 'w', encoding='utf-8').write(AUDIT_JS)
        env = dict(os.environ, SEEDS=os.environ.get('HPN_SEEDS', '12' if FULL else '2'), SEC=os.environ.get('HPN_SEC', '600' if FULL else '420'))
        t0 = time.time()
        p = subprocess.run(['node', 'audit.js'], cwd=d, env=env, capture_output=True, text=True, timeout=7000)
        out = (p.stdout.strip().splitlines() or [''])[-1]
        try: j = json.loads(out)
        except Exception: j = None
        check('[마] Node 합계 점검 — 캐릭터 전원 × 시드 %s × %ss, 종료코드 0' % (env['SEEDS'], env['SEC']), p.returncode == 0 and j is not None, (p.returncode, out, p.stderr[:600]))
        if j:
            print('     판 %d · 점검 %d회 · 카드 %d장(최대 체력 카드 %d) · 선택 %d(그중 최대 체력 카드 %d) · 강제 적용 %d · 최대 체력 범위 %d~%d · %.0fs' % (j['runs'], j['checks'], j['cards'], j['preCards'], j['picks'], j['naturalHpPicks'], j['forced'], j['minMhp'], j['maxMhp'], time.time() - t0))
            check('[마] 점검이 실제로 돌았다(최대 체력 카드가 제안·선택됨, 강제 적용 다수)', j['runs'] >= 18 and j['preCards'] > 0 and j['forced'] > 4 * j['runs'], j)
            check('[마] 합계·미리보기·문구 어긋남 0', not j['bad'], j['bad'])
    finally:
        shutil.rmtree(d, ignore_errors=True)

# ── 바 · 이어하기 ──────────────────────────────────────────────
BUILD_STATE = r"""(a)=>{const x=__p6x;x.CH_set(a.ch);x.start();const S=x.S;
  for(const o of a.cards)x.applyUp(o);
  for(let i=0;i<30*4;i++){x.update(1/30);if(x.state==='lvup'){x.pick(x.CUR[0]);} if(x.state!=='play')x.resume();}
  S.p.hp=Math.min(S.p.hp,S.p.mhp*.7);
  __X.pauseGame();
  return {blob:localStorage.getItem('p6_resume_v1'),mhp:S.p.mhp,hp:S.p.hp,state:x.state}}"""
CARDS_MIX = [{'t': 'p', 'k': 'hp', 'l': 0}, {'t': 'p', 'k': 'hp', 'l': 1}, {'t': 'p', 'k': 'hp', 'l': 2}, {'t': 'sm', 'k': 'sm:hp', 'r': 'hp', 'l': 0}, {'t': 'sm', 'k': 'sm:hp', 'r': 'hp', 'l': 1},
             {'t': 'tr', 'k': 'tr:glassc', 'r': 'glassc', 'l': 0}, {'t': 'tr', 'k': 'tr:glassc', 'r': 'glassc', 'l': 1}]
CARDS_BOTH = CARDS_MIX + [{'t': 'tr', 'k': 'tr:focus', 'r': 'focus', 'l': 0}]
SEE = r"""()=>{const x=__p6x,S=x.S;return {state:x.state,mhp:S.p.mhp,hp:S.p.hp,hpt:document.getElementById('pHp')&&document.getElementById('pHp').textContent,by:S.mhpBy?JSON.parse(JSON.stringify(S.mhpBy)):null,
  src:__X.mhpSrc(),rows:[...document.querySelectorAll('#mhpSrc .mr')].map(r=>r.dataset.mk+':'+r.textContent.replace(/\\s+/g,' ').trim()),hud:document.getElementById('hpt').textContent,
  ps:Object.assign({},S.ps),sm:Object.assign({},S.sm),tr:Object.assign({},S.tr),pt:Object.assign({},S.pt)}}"""
async def restore_in(b, srv, page, blob):
    ctx, pg, errs = await H.new_page(b, srv.port, page=page)
    await pg.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", blob)
    await pg.reload(); await pg.wait_for_function('window.__X!==undefined')
    ok = await pg.evaluate("()=>__X.RES.restore()")
    info = await pg.evaluate("()=>({state:__p6x.state,why:__X.RES.info&&__X.RES.info.why,left:localStorage.getItem('p6_resume_v1')!==null})")
    return ctx, pg, errs, ok, info
async def sec_resume(b, srv):
    for (ch, cards, nm) in [('yj', CARDS_MIX, '용조련사·패시브·밥·유리 대포'), ('brj', CARDS_BOTH, '브장신·유리 대포+정조준')]:
        ctx, pg, errs = await H.new_page(b, srv.port, page=NEW)
        pre = await pg.evaluate(BUILD_STATE, {'ch': ch, 'cards': cards}); s0 = await pg.evaluate(SEE)
        check('[바] (새→새) %s 저장됨(일시정지)' % nm, pre['blob'] is not None and pre['state'] == 'pause', pre['state'])
        await ctx.close()
        c2, p2, e2, ok, info = await restore_in(b, srv, NEW, pre['blob'])
        s1 = await p2.evaluate(SEE)
        check('[바] (새→새) %s 복원됨 · 일시정지 화면' % nm, ok is True and s1['state'] == 'pause', (ok, info))
        check('[바] (새→새) %s 체력 %s → %s · HUD 숫자 · 출처표 동일' % (nm, s0['hpt'], s1['hpt']), s0['mhp'] == s1['mhp'] and s0['by'] == s1['by'] and s0['rows'] == s1['rows'] and s0['hpt'] == s1['hpt'] and s1['hud'] == s1['hpt'], (s0, s1))   # 복원 직후 HUD(뒤에 깔린 막대)도 같은 숫자
        check('[바] (새→새) %s 출처 합 = 최대 체력, 기타 0' % nm, s1['src']['etc'] == 0, s1['src'])
        # 계속하기 → 카드 하나 더 → 다시 일시정지
        r = await p2.evaluate("""()=>{const x=__p6x;x.resume();const S=x.S;x.applyUp({t:'p',k:'hp',l:3});__X.hud();return {st:x.state,hud:document.getElementById('hpt').textContent,etc:__X.mhpSrc().etc,mhp:S.p.mhp}}""")
        check('[바] (새→새) %s 이어서 카드를 먹어도 합이 맞다' % nm, r['etc'] == 0 and r['hud'].endswith('/ %d' % r['mhp']), r)
        check('[바] (새→새) %s 오류 0' % nm, not e2, e2); await c2.close()
    # 옛 저장본(기준 커밋 빌드로 저장) → 새 빌드
    for (ch, cards, nm, expect_split) in [('yj', CARDS_MIX, '유리 대포만', 'glassc'), ('brj', CARDS_BOTH, '유리 대포+정조준(가를 수 없음)', 'tr'), ('brj', CARDS_MIX[:5], '거래 카드 없음', None)]:
        ctx, pg, errs = await H.new_page(b, srv.port, page=OLD)
        pre = await pg.evaluate(BUILD_STATE, {'ch': ch, 'cards': cards})
        has_old = await pg.evaluate("()=>('mhpBy' in __p6x.S)")
        await ctx.close()
        check('[바] (옛→새) %s 기준 커밋 빌드는 mhpBy 가 없다(옛 저장본 맞음) · 저장됨' % nm, pre['blob'] is not None and not has_old and pre['state'] == 'pause', (has_old, pre['state']))
        c2, p2, e2, ok, info = await restore_in(b, srv, NEW, pre['blob'])
        s1 = await p2.evaluate(SEE)
        check('[바] (옛→새) %s 새 빌드에서 복원된다(폐기되지 않음) %s' % (nm, info), ok is True and s1['state'] == 'pause' and info['state'] == 'pause', (ok, info))
        check('[바] (옛→새) %s 체력 %s · 최대 체력 %s 그대로' % (nm, s1['hpt'], pre['mhp']), s1['mhp'] == pre['mhp'] and s1['hpt'].endswith('/ %d' % pre['mhp']), (s1, pre))
        check('[바] (옛→새) %s 출처표를 현재 상태에서 다시 짠다 — 합 = 최대 체력, 기타 0 %s' % (nm, s1['rows']), s1['src']['etc'] == 0 and s1['by'] is not None and (expect_split is None or expect_split in s1['by']), s1)
        check('[바] (옛→새) %s 오류 0' % nm, not e2, e2); await c2.close()

# ── 사 · 오늘의 도전 난수열 불변 ───────────────────────────────
DET = r"""(a)=>{const x=__p6x;x.CH_set(a.ch);x.start({daily:true});const out=[];let seed=a.seed;const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  const dt=1/30,N=Math.round(a.sec/dt);
  for(let i=0;i<N;i++){const st=x.state;if(st==='result')break;
    if(st==='lvup'){out.push(x.CUR.map(o=>o.k||o.t).join(','));x.pick(x.CUR[Math.floor(rnd()*x.CUR.length)]);continue;}
    if(st!=='play'){x.resume();continue;}
    const S=x.S;S.p.hp=Math.max(S.p.hp,S.p.mhp*.5);const k=Math.floor(S.t/2.5)%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];x.update(dt);}
  const S=x.S;return {offers:out,kills:S.kills,lv:S.lv,t:Math.round(S.t*100)/100,xp:Math.round(S.xp*1000)/1000,mhp:S.p.mhp,w:JSON.stringify(S.w),daily:!!S.dly}}"""
DET2 = r"""(a)=>{const x=__p6x;x.CH_set(a.ch);x.start({daily:true});const S=x.S;S.lv=a.lv;S.t=1200;const out=[];
  for(let i=0;i<a.n;i++){const c=x.offers(3);out.push(c.map(o=>(o.k||o.t)+(o.l!=null?':'+o.l:'')).join(','));x.applyUp(c[i%c.length]);if(i%7===3){S.rr=3;}}
  return {out,next:[x.RN('card'),x.RN('card'),x.RN('spawn')],mhp:S.p.mhp,ps:JSON.stringify(S.ps),tr:JSON.stringify(S.tr),sm:JSON.stringify(S.sm),daily:!!S.dly,seed:x.RSEED}}"""
async def sec_det(b, srv):
    # (1) 판을 돌려 보면 같은 빌드끼리도 처치 수가 조금 흔들린다(연출용 Math.random 등) — 그래서 흔들림 없는 비교를 따로 한다:
    #     같은 오늘의 도전 씨앗·같은 상태에서 카드 제안을 80번 이어 뽑아(최대 체력 카드가 섞여 있다) 기준 커밋과 새 빌드를 견주고, 그다음 난수 값까지 같아야 한다.
    for ch, lv in [('brj', 40), ('yj', 40), ('psg', 60), ('bbb', 40)]:
        res = {}
        for nm, pgname in (('old', OLD), ('new', NEW)):
            ctx, pg, errs = await H.new_page(b, srv.port, page=pgname)
            res[nm] = await pg.evaluate(DET2, {'ch': ch, 'lv': lv, 'n': 80}); await ctx.close()
            if errs: check('[사] %s %s 오류 0' % (ch, nm), False, errs)
        o, n = res['old'], res['new']
        hp_cards = sum(1 for r in n['out'] for c in r.split(',') if re.match(r'^(hp|sm:hp|tr:glassc|tr:focus|pt:hp):\d+$', c))
        check('[사] 오늘의 도전 %s — 카드 제안 80번(최대 체력 카드 %d번 등장)이 기준 커밋과 한 장도 다르지 않고, 뒤이은 난수 3개도 같다' % (ch, hp_cards), o == n and n['daily'] and hp_cards > 0, (o['out'][:3], n['out'][:3], o['next'], n['next']))
    # (2) 판을 실제로 돌려도 처음 카드 제안 3번은 같다(네 번 돌려 본다)
    for ch in ['brj', 'psg']:
        offs = []
        for pgname in (OLD, OLD, NEW, NEW):
            ctx, pg, errs = await H.new_page(b, srv.port, page=pgname)
            r = await pg.evaluate(DET, {'ch': ch, 'seed': 777, 'sec': 100}); await ctx.close(); offs.append(r['offers'][:3])
        check('[사] 오늘의 도전 %s — 실제 판의 첫 카드 제안 3번이 네 번 모두 같다' % ch, offs[0] == offs[1] == offs[2] == offs[3] and len(offs[0]) == 3, offs)

# ── 아 · 소스 훑기 ─────────────────────────────────────────────
def sec_source():
    s = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    hits = [(m.start(), s[max(0, m.start() - 30):m.end() + 30].replace('\n', ' ')) for m in re.finditer(r'\bp\.mhp\s*[-+*/]?=(?!=)', s)]
    check('[아] 플레이어 최대 체력(p.mhp)을 바꾸는 줄은 mhpAdd 한 곳뿐 — 새 경로는 mhpAdd 를 써야 한다', len(hits) == 1 and 'function mhpAdd' in s[max(0, hits[0][0] - 40):hits[0][0]], hits)
    hits2 = [m.group(0) for m in re.finditer(r"S\.p\s*=[^=]|S\.p\[['\"]mhp['\"]\]\s*[-+*/]?=|\.p\.mhp\s*=[^=]|Object\.assign\(S\.p", s)]
    check('[아] S.p 를 통째로 바꾸거나 mhp 를 다른 식으로 쓰는 곳이 없다', not hits2, hits2)

async def main():
    prep(); srv = H.Srv()
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            for sec, fn in [('가', sec_hud), ('나', sec_layout), ('다', sec_cards), ('라', sec_pause), ('바', sec_resume), ('사', sec_det)]:
                if want(sec):
                    print('── %s ──' % sec, flush=True); await fn(b, srv)
            await b.close()
        if want('마'): print('── 마 ──', flush=True); sec_node()
        if want('아'): print('── 아 ──', flush=True); sec_source()
    finally:
        srv.close(); cleanup()
    print('\n' + ('전부 통과' if not FAILS else '실패 %d건: %s' % (len(FAILS), FAILS)))
    return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
