# -*- coding: utf-8 -*-
"""🎮 흐접새우 서바이벌 「정보 표시 3종」 시험 — 2026-10-09 사장님 지시
   「esc 눌렀을때 현재 진행중인 게임의 난이도가 표시되게 추가 / 내 캐릭터의 현재 크리티컬확률과같은 스텟표기 추가 /
    레벨업 이후 능력선택창이 떴을때 내가 이미 가지고있는 능력명단 표기 추가」
   사용: python3 tests/survivors_info_test.py [--only 가,나,...] [--fast]   (종료코드 0 = 전부 통과 · 기본 약 4~8분, 부하가 높으면 더)
   구성
     가  일시정지 난이도 줄 — 일반·하드·베리하드·오늘의 도전·무한(일반/하드/베리하드에서 이어 간 것)별 문구·색·글자 · Esc 와 모바일 ⏸ 둘 다 ·
         「지금 몬스터 체력·공격력 ×N」이 실제로 스폰된 잡몹(엘리트·대형 제외)의 값과 같다(시각 여러 지점·무한 +30분 치 상한)
     나  능력치 표 값 — 새 도우미 함수 = 기준 커밋의 인라인 식(비트까지 같다, 무작위 상태 수천 개) · 표 행의 값·글자 = 도우미 · 행 순서·줄 수 불변 ·
         치명타 확률 구성(여섯 갈래 모두 켠 조합 포함) 합 = 합계 · 100% 초과 표기
     다  표시 = 실제 동작 — 치명타를 수천 번 쳐서 비율·배율이 표와 같다 · 이동 거리 · 줍는 범위 · 경험치 · 받는 피해 · 고기 반찬 회복이 표와 같다
     라  레벨업 「내가 가진 능력」 — S 와 정확히 일치(무기·패시브·유물·거래·작은 능력치·시너지) · 카드가 올려 주는 칩만 ▲ · 카드를 고른 뒤 갱신 ·
         이어하기 복구 뒤에도 보임 · 키보드 1·2·3·R·B 그대로 · 카드 앞 세 자식은 그대로 카드
     마  접이식 — 일시정지는 기본 펼침, 레벨업은 기본 접힘 · 사용자가 연 상태 기억(S 가 아니라 UI3)
     바  레이아웃 — 320×568·360×640·390×844·412×915·640×360·844×390·1280×800 에서 가로 넘침 0 · 카드 3장·다시 뽑기·봉인 접근 가능 · 겹침 0
     사  불변 — 새 S 키 0 · 새 최상위 let 0 · 이어하기 서명(RES.SIG) 같음 · 콘솔/페이지 오류 0
   임시 사본 survivors_cx_inf.html · survivors_cx_infb.html(기준 커밋)에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, json, re, subprocess, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
ONLY = None
if '--only' in sys.argv:
    ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(','))
FAST = '--fast' in sys.argv
BASE_COMMIT = os.environ.get('INFO_BASE_COMMIT', '4ed2f37')   # 이 기능들을 합치기 직전의 main — 규칙 불변·이어하기 서명 불변을 이 커밋과 견준다(2026-10-10 합칠 때 bfaaf08 → 4ed2f37: 그 사이 최종 보스가 이어하기 서명을 바꿨다). SIG 가 또 바뀌는 커밋이 들어오면 이 값을 그 직전 main 으로 다시 잡는다(INFO_BASE_COMMIT 로도 덮어쓸 수 있다)
NEW, OLD, OLDSRC = 'survivors_cx_inf.html', 'survivors_cx_infb.html', 'survivors_cx_infb_src.html'
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)
def want(sec): return ONLY is None or sec in ONLY

EXTRA_NEW = r"""
window.__X={RES,pauseGame,openLvup,drawCards,setCUR(v){CUR=v},get CUR(){return CUR},diffHtml,statRows,statsHtml,ownHtml,cardKey:ownCardKey,UI3,hx:uiHx,pcS:uiPcS,pcN:uiPcN,m2:uiM2,
  critChance,critMul,critParts,critCh,critLk,critPv,critPt,critTr,critSm,moveMul,slowMul,magMul,xpMul,armTotal,takenMul,VAMP_N,vampHp,lowMul,rageMul,rageCap,LOWHP_AT,
  cdMul,areaMul,dmgMul,PS,DUR,LK,KIND,mobX,XP_X,PASS,PT,TRD,SM,REL,SYN,TCAP,MAXLV,MAXEV,SLOTW,SLOTP,pmax,slotP,smn,hpMul,atkMul,SHV,TZ,
  get CH(){return CH},get RUN(){return RUN}};
/* 기준 커밋(bfaaf08)의 인라인 식 그대로 — 새 도우미가 이것과 비트까지 같아야 한다 */
window.__O={
 cc:()=>(CH.crit||0)+.03*LK()+.05*pv('crit')+(PTV('luck')?.05:0)+.06*trn('focus')+smv('crit'),
 cm:()=>2+.2*pv('crit')+.25*PTV('crit')+.15*(PTV('luck')?1:0),
 sp:(p)=>p.sp*(1+.08*pv('spd')+(CH.spd||0)+(CH.shv&&S.dT>0?SHV.spd:0)-.05*pv('turtle')+(S.spr>0?[.2,.3,.4][S.rel.sprint-1]:0)+.1*trn('gale')-.05*trn('iron')+smv('spd')+(S.x2.bT>0?S.x2.bs:0)+(S.rel.berserk&&p.hp<=p.mhp*.4?.1:0))*(p.slow>0?.6:1),
 mag:()=>(70*(1+.3*pv('mag')+(CH.mag||0)+.4*(PTV('mag')?1:0)+smv('mag')))**2,
 xp:(v)=>v*XP_X*(1+(CH.xp||0)+.08*pv('study')+S.syn.xp),
 arm:()=>pv('arm')+(CH.arm||0)+2*pv('turtle')+trn('iron'),
 tk:(p,d)=>{d*=(1+.1*pv('glass'))*(p.moving&&PTV('spd')?.94:1)*(CH.shv&&S.dT>0?1-SHV.red:1);return d;},
 vamp:()=>S.p.hp+1.5*pv('vamp'),
 low:(d)=>{if(CH.low&&S.p.hp<S.p.mhp*.3)d*=1+CH.low;return d;},
 rage:(d)=>{if(CH.rage)d*=1+Math.min(CH.rage+[0,.1,.2,.3][SGN('sg_tw')],Math.max(0,1-S.p.hp/S.p.mhp));return d;},
 newcc:()=>critChance(),newcm:()=>critMul(),newsp:(p)=>p.sp*moveMul()*slowMul(),newmag:()=>(70*magMul())**2,newxp:(v)=>v*XP_X*xpMul(),newarm:()=>armTotal(),
 newtk:(p,d)=>{d*=takenMul();return d;},newvamp:()=>S.p.hp+vampHp(),newlow:(d)=>{if(CH.low)d*=lowMul();return d;},newrage:(d)=>{if(CH.rage)d*=rageMul();return d;}};
window.__mb=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
"""
EXTRA_OLD = r"""
window.__X={RES,pauseGame,openLvup,drawCards,setCUR(v){CUR=v}};
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

async def new_page(*a, **k):
    """H.new_page + 페이지 안 계산(evaluate)마다 시간 제한 — 부하가 심할 때 브라우저가 말없이 멈추면 영원히 기다리지 말고 눈에 띄게 실패시킨다."""
    ctx, pg, errs = await H.new_page(*a, **k)
    ev = pg.evaluate
    async def guarded(*x, **y):
        return await asyncio.wait_for(ev(*x, **y), 300)
    pg.evaluate = guarded
    return ctx, pg, errs

def js_round(x): return math.floor(x + 0.5)
def fnum(r):   # 자바스크립트의 String(숫자)와 같은 모양(…0 은 정수처럼)
    s = ('%.1f' % r).rstrip('0').rstrip('.') if abs(r) < 1e15 else str(r)
    return s if s not in ('-0', '') else '0'
def pcS(v):
    r = js_round(v * 1000) / 10
    return ('−' if r < 0 else '+') + fnum(abs(r)) + '%'
def pcN(v): return fnum(js_round(v * 1000) / 10) + '%'
def hx(v):
    if v >= 100: return '{:,}'.format(js_round(v))
    if v >= 10: return str(js_round(v))
    return fnum(js_round(v * 10) / 10)

# 판 시작 · 일시정지 열기
START = r"""(a)=>{const x=__p6x;document.getElementById('hardChk').checked=(a.mode==='hard');document.getElementById('vhChk').checked=(a.mode==='vh');
  x.CH_set(a.ch||'brj');x.start(a.mode==='daily'?{daily:true}:undefined);return {st:x.state,hard:!!x.S.hard,vh:x.S.vh||0,dly:!!x.S.dly}}"""
READ = r"""()=>{const x=__p6x,S=x.S,d=document.getElementById('pDiff'),m=document.getElementById('pMul'),pi=document.getElementById('pInfo'),pt=document.getElementById('pTop');
  const m1=x.MIN();
  return {st:x.state,pauseOn:document.getElementById('pause').classList.contains('on'),diff:d?d.innerText.replace(/\s+/g,' ').trim():null,cls:d?d.className:null,kind:d?d.dataset.d:null,
    mul:m?m.innerText.replace(/\s+/g,' ').trim():null,bold:m?[...m.querySelectorAll('b')].map(b=>b.textContent):[],first:pt.firstElementChild?pt.firstElementChild.id:null,
    next:pt.children[1]?pt.children[1].id:null,t:S.t,m:m1,hm:x.hpMul(m1),am:x.atkMul(m1)*__X.mobX(m1),hard:!!S.hard,vh:S.vh||0,endless:S.endless||0,dly:S.dly?{date:S.dly.date,ranked:S.dly.ranked}:null,
    pinfo:pi.innerText.slice(0,200)}}"""
# 시간을 옮겨 놓고 실제 잡몹을 스폰시켜 본다(보스·몰이·대형은 막고 잡몹만) → 표시와 비교
SPAWN = r"""(t)=>{const x=__p6x,S=x.S;S.t=t;S.evT=1e9;S.bigT=1e9;S.nextBoss=1e9;S.nextMini=1e9;S.nextSp=1e9;S.won=true;S.p.hp=S.p.mhp=1e6;
  x.enemies.clear();S.spawnT=6;S.live.length=0;S.kc.fill(0);
  x.update(1/30);
  const rows=[];for(const e of x.enemies.a){if(!e.on||e.boss||e.el||e.bg)continue;const k=__X.KIND[e.ki];if(!k||!k.hp||!k.d)continue;rows.push({ki:e.ki,hp:e.mhp/k.hp,atk:e.dmg/k.d});}
  const S2=x.S;__X.pauseGame();   // 같은 호출 안에서 멈춘다 — 실제 게임 루프(rAF)가 사이에 시간을 더 흘리지 못하게
  return {rows,n:rows.length,t:S2.t}}"""
def parse_x(s):
    return float(s.replace('×', '').replace(',', ''))
def tol_ok(shown, actual):
    # 표시는 반올림한 글자 — 실제 값을 같은 규칙으로 반올림한 것과 같아야 한다(1ulp 어긋남은 반올림 경계에서만 문제 → 허용 오차를 한 자리 아래로)
    step = 0.1 if actual < 10 else 1.0
    return abs(shown - actual) <= step / 2 + 1e-6

async def open_by(pg, how):
    if how == 'esc':
        await pg.keyboard.press('Escape')
    else:
        await pg.click('#pauseBtn')
    await pg.wait_for_function("__p6x.state==='pause'", timeout=20000)

async def sec_diff(b, srv):
    # 일반·하드·베리하드 × (Esc · ⏸) — 문구·색 클래스·첫 자식 · 배율이 지금 시각의 값
    EXP = {'normal': ('🎮 난이도: 일반', 'normal', ''), 'hard': ('🎮 난이도: 🔥 하드', 'hard', 'hard'), 'vh': ('🎮 난이도: 💀 베리하드', 'vh', 'vh')}
    for mode in ('normal', 'hard', 'vh'):
        for how, mob in (('esc', False), ('btn', True)):
            ctx, pg, errs = await new_page(b, srv.port, w=412 if mob else 1280, h=860 if mob else 800, page=NEW, mobile=mob)
            s = await pg.evaluate(START, {'mode': mode})
            await pg.evaluate("()=>__adv(75,{god:true})")
            await open_by(pg, how)
            r = await pg.evaluate(READ)
            txt, kind, cls = EXP[mode]
            check('[가] %s · %s 로 열면 「%s」' % (mode, 'Esc' if how == 'esc' else '⏸ 버튼', txt), r['diff'] == txt and r['kind'] == kind and r['cls'].split()[-1] == (cls or 'dfl') and r['pauseOn'], r)
            check('[가] %s · %s #pTop(제목 바로 아래)가 난이도 줄 · 바로 다음이 배율 줄' % (mode, how), r['first'] == 'pDiff' and r['next'] == 'pMul', (r['first'], r['next']))
            e_hm, e_am = hx(r['hm']), hx(r['am'])
            check('[가] %s · %s 배율 글자 = 지금 시각(%.0f초)의 hpMul·atkMul×mobX (체력 ×%s · 공격력 ×%s)' % (mode, how, r['t'], e_hm, e_am),
                  r['bold'] == ['×' + e_hm, '×' + e_am] and '잡몹 기준' in r['mul'] and '보스·엘리트 제외' in r['mul'], r)
            check('[가] %s · %s 판 상태와 어긋나지 않는다(S.hard=%s S.vh=%s)' % (mode, how, r['hard'], r['vh']), r['hard'] == (mode != 'normal') and (r['vh'] == 1) == (mode == 'vh'), r)
            # 다시 Esc → 계속, 또 열면 같은 줄
            await pg.keyboard.press('Escape'); await pg.wait_for_function("__p6x.state==='play'", timeout=20000)
            check('[가] %s · %s 다시 누르면 계속(play)' % (mode, how), await pg.evaluate("()=>__p6x.state") == 'play')
            check('[가] %s · %s 오류 0' % (mode, how), not errs, errs)
            await ctx.close()
    # 시각 여러 지점 × 난이도 — 표시 = 실제 스폰된 잡몹(엘리트·대형 제외)
    times = [0.5, 120, 480, 900, 1800, 3000, 3550]
    for mode in ('normal', 'hard', 'vh'):
        ctx, pg, errs = await new_page(b, srv.port, page=NEW)
        await pg.evaluate(START, {'mode': mode, 'ch': 'brj'})
        bad, nmob, shown = [], 0, []
        for t in times:
            sp = await pg.evaluate(SPAWN, t)
            r = await pg.evaluate(READ)
            await pg.evaluate("()=>{__p6x.resume()}")
            hs, as_ = parse_x(r['bold'][0]), parse_x(r['bold'][1])
            shown.append((t, r['bold'][0], r['bold'][1]))
            if abs(r['t'] - sp['t']) > 1e-9: bad.append(('t', t, r['t'], sp['t']))
            if not sp['rows']: bad.append(('no-mob', t)); continue
            for q in sp['rows']:
                nmob += 1
                if not (tol_ok(hs, q['hp']) and tol_ok(as_, q['atk'])): bad.append((t, hs, q['hp'], as_, q['atk']))
        check('[가] %s — 시각 %d 지점에서 실제 스폰된 잡몹 %d마리의 체력·공격력 배율 = 표시 %s' % (mode, len(times), nmob, shown[:3] + ['…']), not bad and nmob >= len(times) * 3, bad[:4])
        check('[가] %s 오류 0' % mode, not errs, errs)
        await ctx.close()
    # 오늘의 도전
    for how, mob in (('esc', False), ('btn', True)):
        ctx, pg, errs = await new_page(b, srv.port, w=412 if mob else 1280, h=860 if mob else 800, page=NEW, mobile=mob)
        s = await pg.evaluate(START, {'mode': 'daily'})
        check('[가] 오늘의 도전이 시작된다(S.dly · 일반 규칙: hard=%s vh=%s)' % (s['hard'], s['vh']), s['dly'] and not s['hard'] and not s['vh'], s)
        await pg.evaluate("()=>__adv(60,{god:true})")
        await open_by(pg, how)
        r = await pg.evaluate(READ)
        md = r['dly']['date'][5:]
        check('[가] 오늘의 도전 · %s 「📅 오늘의 도전 %s」· 일반 규칙 · 연습 판(로그인 안 한 시험 환경)' % (how, md), r['kind'] == 'daily' and ('📅 오늘의 도전 ' + md) in r['diff'] and '일반 규칙' in r['diff'] and '연습 판(기록 안 돼요)' in r['diff'] and 'dfdl' in r['cls'], r)
        await pg.evaluate("()=>{__p6x.resume();__p6x.S.dly.ranked=1;__X.pauseGame()}")
        r = await pg.evaluate(READ)
        check('[가] 오늘의 도전 · 기록되는 판이면 「기록되는 판」', '기록되는 판' in r['diff'] and '연습 판' not in r['diff'], r['diff'])
        check('[가] 오늘의 도전에는 하드·베리하드 글자가 없다(만들 수 없는 조합)', '하드' not in r['diff'] and '무한' not in r['diff'], r['diff'])
        check('[가] 오늘의 도전 오류 0', not errs, errs)
        await ctx.close()
    # 무한 모드 — 일반·하드·베리하드에서 이어 간 것
    for mode in ('normal', 'hard', 'vh'):
        ctx, pg, errs = await new_page(b, srv.port, page=NEW)
        await pg.evaluate(START, {'mode': mode})
        await pg.evaluate("""async ()=>{const x=__p6x,S=x.S;S.t=3598;let n=0;while(n<400){if(x.state==='lvup'){x.pick(x.CUR[0]);continue}if(x.state!=='play')break;S.p.hp=S.p.mhp;x.update(0.05);n++;if(S.t>=3601)break}}""")
        st = await pg.evaluate("()=>__p6x.state")
        await pg.evaluate("()=>document.getElementById('endYes').click()")
        st2 = await pg.evaluate("()=>[__p6x.state,__p6x.S.endless]")
        check('[가] 무한(%s) 이어 가기 성립 %s → %s' % (mode, st, st2), st == 'result' and st2 == ['play', 1], (st, st2))
        await pg.evaluate("()=>__adv(5,{god:true})")
        await pg.evaluate("()=>__X.pauseGame()")
        r = await pg.evaluate(READ)
        nm = {'normal': '일반', 'hard': '🔥 하드', 'vh': '💀 베리하드'}[mode]
        check('[가] 무한(%s) 「♾ 무한 모드」+「이어 간 난이도: %s」' % (mode, nm), r['kind'] == 'endless' and '♾ 무한 모드' in r['diff'] and ('이어 간 난이도: ' + nm) in r['diff'] and r['endless'] == 1, r)
        e_hm, e_am = hx(r['hm']), hx(r['am'])
        check('[가] 무한(%s) 배율 = hpMul(MIN()) · MIN()=%.2f(60분 뒤 분당 0.6분 치)' % (mode, r['m']), r['bold'] == ['×' + e_hm, '×' + e_am] and r['m'] > 60, r)
        # +30분 치에서 멈춘다 — 배율이 그 뒤로 더 안 오른다
        seen = []
        for t in (3600 + 3000, 3600 + 6000, 3600 + 7000):
            await pg.evaluate("(t)=>{__p6x.resume();__p6x.S.t=t;__X.pauseGame()}", t)
            seen.append((await pg.evaluate(READ))['bold'])
        check('[가] 무한(%s) 난이도 +30분 치에서 멈춘다 — 그 뒤 시각에서 배율 표시가 같다 %s' % (mode, seen[0]), seen[0] == seen[1] == seen[2], seen)
        # 무한 시작 직후 SPAWN 비교
        sp = await pg.evaluate(SPAWN, 3600 + 1500); r = await pg.evaluate(READ)
        hs, as_ = parse_x(r['bold'][0]), parse_x(r['bold'][1])
        check('[가] 무한(%s) 실제 스폰된 잡몹 %d마리와 표시 일치' % (mode, len(sp['rows'])), sp['rows'] and all(tol_ok(hs, q['hp']) and tol_ok(as_, q['atk']) for q in sp['rows']), (r['bold'], sp['rows'][:2]))
        check('[가] 무한(%s) 오류 0' % mode, not errs, errs)
        await ctx.close()

# ── 나 · 능력치 표 값 ───────────────────────────────────────────
BITS = r"""(a)=>{const x=__p6x,O=window.__O,mb=window.__mb(a.seed),chars=x.CHARS.map(c=>c.k),X=__X;let n=0;const bad=[];
  const same=(k,u,v,ctx)=>{n++;if(!Object.is(u,v)&&bad.length<8)bad.push([k,u,v,ctx]);};
  for(let i=0;i<a.N;i++){
    const ck=chars[i%chars.length];x.CH_set(ck);x.start();const S=x.S,CH=x.CH,sv={};for(const f of ['crit','spd','mag','xp','arm','low','rage','shv'])sv[f]=CH[f];
    // 캐릭터 보정도 무작위로 흔든다(끝나면 되돌린다)
    if(mb()<.5)CH.crit=Math.round(mb()*50)/100;if(mb()<.5)CH.spd=Math.round((mb()-.3)*40)/100;if(mb()<.5)CH.mag=Math.round(mb()*60)/100;if(mb()<.5)CH.xp=Math.round(mb()*40)/100;
    if(mb()<.5)CH.arm=Math.floor(mb()*4);if(mb()<.3)CH.low=Math.round(mb()*80)/100;if(mb()<.3)CH.rage=Math.round(mb()*80)/100;if(mb()<.3)CH.shv=1;
    for(const k in X.PASS){const m=X.pmax(k),r=mb();if(r<.6)S.ps[k]=1+Math.floor(mb()*m);}
    for(const k in X.PT){if(mb()<.4)S.pt[k]=1+Math.floor(mb()*X.PT[k].length);}
    for(const k in X.TRD){if(mb()<.5)S.tr[k]=1+Math.floor(mb()*(X.TRD[k].cap||3));}
    for(const k in X.SM){if(k==='ramen')continue;if(mb()<.5)S.sm[k]=1+Math.floor(mb()*X.SM[k].cap);}
    S.ramen=mb()<.5?Math.floor(mb()*9):0;
    for(const k in X.REL){if(mb()<.3)S.rel[k]=1+Math.floor(mb()*3);}
    S.syn={dmg:mb()*.3,cd:mb()*.2,area:mb()*.3,xp:mb()*.3,luck:Math.floor(mb()*4)};
    S.x2.bT=mb()<.3?3:0;S.x2.bm=mb()*.2;S.x2.bs=mb()*.2;S.dT=mb()<.3?4:0;S.spr=mb()<.3?1:0;if(S.spr>0&&!S.rel.sprint)S.rel.sprint=1+Math.floor(mb()*3);
    const p=S.p;p.mhp=60+Math.floor(mb()*300);p.hp=Math.max(1,Math.floor(mb()*p.mhp));if(mb()<.4)p.hp=p.mhp;p.moving=mb()<.5;p.slow=mb()<.3?1:0;p.sp=180;
    const d=1+Math.floor(mb()*400)+mb(),v=.5+mb()*30;
    same('crit',O.cc(),O.newcc(),ck);same('critMul',O.cm(),O.newcm(),ck);same('speed',O.sp(p),O.newsp(p),ck);same('magnet',O.mag(),O.newmag(),ck);same('xp',O.xp(v),O.newxp(v),ck);
    same('armor',O.arm(),O.newarm(),ck);same('taken',O.tk(p,d),O.newtk(p,d),ck);same('vamp',O.vamp(),O.newvamp(),ck);same('low',O.low(d),O.newlow(d),ck);same('rage',O.rage(d),O.newrage(d),ck);
    // 구성 합 = 합계(식이 같은 순서로 더한다)
    same('critParts',X.critParts().reduce((a,q)=>a+q[1],0),X.critChance(),ck);
    for(const f in sv){if(sv[f]===undefined)delete CH[f];else CH[f]=sv[f];}
  }
  return {n,bad}}"""
FIXED = r"""(a)=>{const x=__p6x,S=x.S,X=__X;
  x.CH_set(a.ch);x.start();const s=x.S;const A=(o)=>x.applyUp(o);
  const cfg=a.cfg||{};for(const k in (cfg.ps||{}))for(let i=0;i<cfg.ps[k];i++)A({t:'p',k,l:i});
  for(const k in (cfg.pt||{}))s.pt[k]=cfg.pt[k];for(const k in (cfg.tr||{}))for(let i=0;i<cfg.tr[k];i++)A({t:'tr',k:'tr:'+k,r:k,l:i});
  for(const k in (cfg.sm||{}))for(let i=0;i<cfg.sm[k];i++)A({t:'sm',k:'sm:'+k,r:k,l:i});
  for(const k in (cfg.rel||{}))s.rel[k]=cfg.rel[k];if(cfg.syn)s.syn=cfg.syn;if(cfg.hp!=null)s.p.hp=cfg.hp;if(cfg.dT)s.dT=cfg.dT;if(cfg.slow)s.p.slow=cfg.slow;if(cfg.moving!=null)s.p.moving=cfg.moving;
  X.pauseGame();
  const rows={};for(const r of document.querySelectorAll('#sttp .rw'))rows[r.dataset.k]={v:r.dataset.v,a:r.dataset.a===undefined?null:r.dataset.a,t:r.querySelector('.v').textContent,l:r.querySelector('.l').textContent,s:r.querySelector('.s')?r.querySelector('.s').textContent:null};
  const order=[...document.querySelectorAll('#sttp .rw')].map(r=>r.dataset.k);
  const H={dmg:x.dmgMul(),crit:X.critChance(),critdmg:X.critMul(),cd:X.cdMul(),area:X.areaMul(),move:X.moveMul()*X.slowMul(),taken:X.takenMul(),mag:X.magMul(),xp:X.xpMul(),pspd:X.PS(),dur:X.DUR(),amt:s.ps.amt||0,luck:X.LK(),vamp:s.ps.vamp||0,arm:X.armTotal()};
  return {rows,order,H,note:document.querySelector('#sttp .sn').textContent,open:document.getElementById('sttp').open,tag:document.getElementById('sttp').tagName,
    parts:X.critParts().map(q=>[q[0],q[1]]),vampHp:X.vampHp(),VAMP_N:X.VAMP_N,lowHp:X.LOWHP_AT,low:s.p.hp<s.p.mhp*.3,CHlow:x.CH.low||0,CHrage:x.CH.rage||0,rageMul:X.rageMul(),rageCap:X.rageCap(),lowMul:X.lowMul()}}"""
ROW_ORDER = ['dmg', 'crit', 'critdmg', 'cd', 'area', 'move', 'taken', 'mag', 'xp', 'pspd', 'dur', 'amt', 'luck', 'vamp']
def expect_rows(r):
    H_ = r['H']; e = {}
    e['dmg'] = pcS(H_['dmg'] - 1)
    cc = H_['crit']
    e['crit'] = ('100% (초과 +%s%%p)' % fnum(js_round((cc - 1) * 1000) / 10)) if cc > 1 else pcN(cc)
    e['critdmg'] = '×%.2f' % H_['critdmg']
    e['cd'] = pcS(H_['cd'] - 1); e['area'] = pcS(H_['area'] - 1); e['move'] = pcS(H_['move'] - 1)
    e['taken'] = '—' if (H_['arm'] == 0 and H_['taken'] == 1) else '−%s · ×%.2f' % (fnum(H_['arm']), H_['taken'])   # 2026-10-10 검수: 줄여 주는 효과가 하나도 없으면 「—」
    e['mag'] = pcS(H_['mag'] - 1); e['xp'] = pcS(H_['xp'] - 1); e['pspd'] = pcS(H_['pspd'] - 1); e['dur'] = pcS(H_['dur'] - 1)
    e['amt'] = '+%d' % H_['amt']; e['luck'] = '%d단계' % H_['luck']
    e['vamp'] = ('%d마리마다 +%s HP' % (r['VAMP_N'], fnum(r['vampHp']))) if H_['vamp'] else '—'
    return e
FIX_CASES = [
    ('빈 몸(브장신)', 'brj', {}),
    ('여섯 갈래 치명타(집중겜 +20% · 행운 패시브 · 급소 · 행운 초월 · 정조준 · 눈 밝히기)', 'jjg', {'ps': {'luck': 3, 'crit': 4}, 'pt': {'luck': 1}, 'tr': {'focus': 2}, 'sm': {'crit': 3}, 'syn': {'dmg': 0, 'cd': 0, 'area': 0, 'xp': 0, 'luck': 2}}),
    ('방어형(단단묵직 · 거북 · 철갑 · 광분 · 이동 중 초월)', 'ddmj', {'ps': {'arm': 3, 'turtle': 2, 'glass': 2, 'spd': 2}, 'pt': {'spd': 2}, 'tr': {'iron': 2, 'gale': 1}, 'moving': True}),
    ('범위·쿨·지속·속사·곱빼기·고기 반찬', 'brj', {'ps': {'area': 3, 'cd': 4, 'dur': 2, 'pspd': 3, 'amt': 2, 'vamp': 3, 'study': 2, 'mag': 3, 'might': 2}, 'pt': {'area': 1, 'pspd': 1, 'cd': 1, 'mag': 1}, 'tr': {'wide': 2, 'swift': 1}, 'sm': {'mag': 2, 'spd': 3, 'ramen': 4}}),
    ('용 변신 중 프싱(피해·이속·받는 피해 일시 효과)', 'psg', {'ps': {'might': 2, 'spd': 1}, 'dT': 5}),
    ('망무새(체력 낮을 때) · 느려짐', 'mms', {'hp': 20, 'slow': 1.5}),
    ('태웅(잃은 체력만큼)', 'tw', {'hp': 40, 'rel': {'sg_tw': 2}}),
    ('유미(경험치·줍기 캐릭터 보정) + 시너지 경험치', 'yumi', {'syn': {'dmg': 0, 'cd': 0, 'area': 0, 'xp': .12, 'luck': 0}, 'sm': {'mag': 2}}),
]
async def sec_values(b, srv):
    # (1) 도우미 = 기준 커밋의 인라인 식 — 무작위 상태 수천 개, 비트까지(Object.is)
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    N = 600 if FAST else 2400
    r = await pg.evaluate(BITS, {'seed': 20261009, 'N': N})
    check('[나] 새 도우미 함수 = 기준 커밋(%s)의 인라인 식 — 무작위 상태 %d개 × 11식 = %d번 비교, 비트까지 같다(Object.is)' % (BASE_COMMIT, N, r['n']), not r['bad'] and r['n'] >= N * 11, r['bad'])
    check('[나] 오류 0', not errs, errs)
    await ctx.close()
    # (2) 표 행 = 도우미 값, 글자 = 같은 규칙, 순서·줄 수 불변
    orders = []
    for (nm, ch, cfg) in FIX_CASES:
        ctx, pg, errs = await new_page(b, srv.port, page=NEW)
        r = await pg.evaluate(FIXED, {'ch': ch, 'cfg': cfg})
        orders.append(r['order'])
        exp = expect_rows(r)
        badv = [(k, r['rows'][k]['v'], r['H'][k]) for k in ROW_ORDER if k in r['rows'] and k != 'taken' and float(r['rows'][k]['v']) != float(r['H'][k])]
        if 'taken' in r['rows']:
            tk = r['rows']['taken']
            if float(tk['v']) != float(r['H']['taken']) or float(tk['a']) != float(r['H']['arm']): badv.append(('taken', tk, r['H']['taken'], r['H']['arm']))
        badt = [(k, r['rows'][k]['t'], exp[k]) for k in ROW_ORDER if k in r['rows'] and r['rows'][k]['t'] != exp[k]]
        check('[나] %s — 14행 · 순서 고정 · data-v = 도우미 값' % nm, r['order'] == ROW_ORDER and not badv, (r['order'], badv))
        check('[나] %s — 보이는 글자 = 같은 규칙(독립 계산) %s' % (nm, {k: r['rows'][k]['t'] for k in ('dmg', 'crit', 'taken', 'move')}), not badt, badt)
        tk_s = r['rows']['taken']['s'] or ''
        check('[나] %s — 받는 피해 행 아래 쉬운 설명 「맞은 피해에 ×N 곱하고, 그다음 N 깎아요(최소 1)」 숫자가 값과 같다' % nm, tk_s == ('아직 줄여 주는 효과가 없어요' if (r['H']['arm'] == 0 and r['H']['taken'] == 1) else '맞은 피해에 ×%.2f 곱하고, 그다음 %s 깎아요 (그래도 최소 1은 받아요)' % (r['H']['taken'], fnum(r['H']['arm']))), tk_s)
        check('[나] %s — 표 맨 아래 「지금 켜진 일시 효과(변신·버프·체력 조건·움직이는 중 효과)도 포함해요」' % nm, r['note'] == '지금 켜진 일시 효과(변신·버프·체력 조건·움직이는 중 효과)도 포함해요', r['note'])
        # 치명타 구성
        sub = r['rows']['crit']['s'] or ''
        got = re.findall(r'([가-힣 ]+?) \+([0-9.]+)%', sub.replace('구성: ', '').replace(' · ', ' · '))
        got = [(a.strip(), float(c)) for a, c in re.findall(r'([가-힣]+(?: [가-힣]+)?) \+([0-9.]+)%', sub)]
        total = sum(c for _, c in r['parts'])
        want_parts = [(a, js_round(c * 1000) / 10) for a, c in r['parts'] if c]
        check('[나] %s — 치명타 구성 줄: 0 인 갈래는 생략, 나머지 %d갈래가 값과 같다' % (nm, len(want_parts)), got == [(a, c) for a, c in want_parts] if want_parts else ('아직 없어요' in sub), (sub, want_parts))
        cc = float(r['rows']['crit']['v'])
        check('[나] %s — 구성 합(%.4f) = 합계 %.4f (정확히) · 보이는 글자의 합 ≈ 보이는 합계(±0.1)' % (nm, total, cc), total == cc and (not want_parts or abs(sum(c for _, c in got) - min(cc, 9) * 100) < 0.11 or cc > 1), (total, cc, got))
        if cc > 1: check('[나] %s — 100%% 초과를 정직하게 표기' % nm, r['rows']['crit']['t'].startswith('100% (초과 +'), r['rows']['crit']['t'])
        if nm.startswith('여섯 갈래'):
            labs = [a for a, _ in got]
            check('[나] 여섯 갈래를 모두 켠 조합 — 구성 줄에 캐릭터·행운·급소·행운 초월·정조준·눈 밝히기가 전부 있다', labs == ['캐릭터', '행운', '급소', '행운 초월', '정조준', '눈 밝히기'], (labs, sub))
        if nm.startswith('망무새'):
            check('[나] 망무새 — 피해 행 아래 「체력 30% 이하면 +60% 더 — 지금 켜짐」(체력 20이라 켜져 있다)', '체력 30% 이하면 +60% 더' in (r['rows']['dmg']['s'] or '') and r['low'] == ('지금 켜짐' in r['rows']['dmg']['s']), r['rows']['dmg'])
        if nm.startswith('태웅'):
            check('[나] 태웅 — 피해 행 아래 「잃은 체력만큼 +N% 더(최대 +N%)」 값이 rageMul·rageCap 과 같다', ('+%s 더(최대 +%s)' % (pcN(r['rageMul'] - 1), pcN(r['rageCap']))) in (r['rows']['dmg']['s'] or ''), (r['rows']['dmg'], r['rageMul'], r['rageCap']))
        check('[나] %s — 오류 0' % nm, not errs, errs)
        await ctx.close()
    check('[나] 어떤 빌드든 행 순서·줄 수가 같다(켜고 끌 때 화면이 흔들리지 않는다)', all(o == ROW_ORDER for o in orders), orders)
    # (3) 구성이 비어 있어도 줄은 있다
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    r = await pg.evaluate(FIXED, {'ch': 'brj', 'cfg': {}})
    check('[나] 빈 몸 — 치명타 구성 줄이 그래도 있다(「아직 없어요」)', '아직 없어요' in (r['rows']['crit']['s'] or '') and r['rows']['crit']['t'] == '0%', r['rows']['crit'])
    check('[나] 빈 몸 — 값 없는 행은 +0% · +0 · 0단계 · —', r['rows']['dmg']['t'] == '+0%' and r['rows']['amt']['t'] == '+0' and r['rows']['luck']['t'] == '0단계' and r['rows']['vamp']['t'] == '—' and r['rows']['taken']['t'] == '—', {k: v['t'] for k, v in r['rows'].items()})
    await ctx.close()

# ── 다 · 표시 = 실제 동작 ──────────────────────────────────────
CRIT = r"""(a)=>{const x=__p6x,X=__X;x.CH_set(a.ch);x.start();const S=x.S;const A=(o)=>x.applyUp(o);
  for(const k in (a.ps||{}))for(let i=0;i<a.ps[k];i++)A({t:'p',k,l:i});for(const k in (a.pt||{}))S.pt[k]=a.pt[k];for(const k in (a.tr||{}))for(let i=0;i<a.tr[k];i++)A({t:'tr',k:'tr:'+k,r:k,l:i});
  for(const k in (a.sm||{}))for(let i=0;i<a.sm[k];i++)A({t:'sm',k:'sm:'+k,r:k,l:i});if(a.syn)S.syn=a.syn;if(a.chcrit!=null)x.CH.crit=a.chcrit;
  Math.random=window.__mb(a.seed);
  const e=x.spawnEnemy(0,1);e.on=true;e.x=1e6;e.y=1e6;S.live.length=0;
  const cc=X.critChance(),cm=X.critMul();let crits=0,n=a.N,mulBad=0,maxd=0;
  for(let i=0;i<n;i++){e.hp=e.mhp=1e6;x.hurt(e,100);const dealt=1e6-e.hp;if(dealt>150){crits++;if(Math.abs(dealt-100*cm)>1e-6)mulBad++;}else if(Math.abs(dealt-100)>1e-9)mulBad++;}
  x.pauseGame&&0;__X.pauseGame();
  const row=document.querySelector('#sttp .rw[data-k=crit] .v').textContent,row2=document.querySelector('#sttp .rw[data-k=critdmg] .v').textContent;
  return {cc,cm,crits,n,mulBad,row,row2}}"""
async def sec_behavior(b, srv):
    N = 6000 if FAST else 24000
    cases = [
        ('여섯 갈래 켠 집중겜', {'ch': 'jjg', 'ps': {'luck': 3, 'crit': 4}, 'pt': {'luck': 1}, 'tr': {'focus': 2}, 'sm': {'crit': 3}, 'syn': {'dmg': 0, 'cd': 0, 'area': 0, 'xp': 0, 'luck': 2}}),
        ('행운 패시브 2단계뿐인 브장신', {'ch': 'brj', 'ps': {'luck': 2}}),
        ('치명타 없는 브장신', {'ch': 'brj'}),
        ('100% 넘는 집중겜(캐릭터 보정을 키워 시험)', {'ch': 'jjg', 'chcrit': .7, 'ps': {'luck': 5, 'crit': 5}, 'pt': {'luck': 1}, 'tr': {'focus': 3}}),
    ]
    for (nm, cfg) in cases:
        ctx, pg, errs = await new_page(b, srv.port, page=NEW)
        r = await pg.evaluate(CRIT, dict(cfg, seed=987654, N=N))
        p = min(1.0, r['cc']); obs = r['crits'] / r['n']
        sig = math.sqrt(max(p * (1 - p), 1e-9) / r['n'])
        check('[다] %s — 치명타 확률 표시 %s ≈ %.1f%% 를 %d번 쳐서 관측 %.2f%% (4σ=%.2f%%p 안)' % (nm, r['row'], p * 100, r['n'], obs * 100, 400 * sig), abs(obs - p) <= 4 * sig + 1e-9 and (r['cc'] < 1 or obs == 1.0), (p, obs, r['row']))
        check('[다] %s — 치명타 피해 표시 %s = 실제 배율 ×%.4f(터진 %d번 전부 같은 배율 · 안 터진 판은 ×1)' % (nm, r['row2'], r['cm'], r['crits']), r['mulBad'] == 0 and r['row2'] == '×%.2f' % r['cm'], r)
        check('[다] %s — 오류 0' % nm, not errs, errs)
        await ctx.close()
    # 이동 거리 · 줍는 범위 · 경험치 · 받는 피해 · 고기 반찬
    # 이동 — 한 프레임 거리 ÷ (p.sp·dt) = moveMul()·slowMul() (update 가 slow 를 깎기 전 상태 기준)
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    MV = r"""(c)=>{const x=__p6x,X=__X;x.CH_set(c.ch);x.start();const S=x.S,p=S.p;x.enemies.clear();S.live.length=0;S.t=1;S.nextBoss=S.nextMini=S.nextSp=1e9;S.evT=1e9;S.bigT=1e9;S.spawnT=-1e9;
        const A=(o)=>x.applyUp(o);for(const k in (c.ps||{}))for(let i=0;i<c.ps[k];i++)A({t:'p',k,l:i});for(const k in (c.tr||{}))for(let i=0;i<c.tr[k];i++)A({t:'tr',k:'tr:'+k,r:k,l:i});for(const k in (c.sm||{}))for(let i=0;i<c.sm[k];i++)A({t:'sm',k:'sm:'+k,r:k,l:i});
        for(const k in (c.rel||{}))S.rel[k]=c.rel[k];if(c.dT)S.dT=c.dT;if(c.bell){S.x2.bT=5;S.x2.bm=.05;S.x2.bs=.06;}if(c.spr)S.spr=1;if(c.slow)p.slow=2;if(c.lowhp)p.hp=p.mhp*.3;
        p.x=0;p.y=0;x.keys={KeyD:true};
        const shown=X.moveMul()*X.slowMul();            // 표가 읽는 값(= data-v 가 될 값)
        __X.pauseGame();const row=+document.querySelector('#sttp .rw[data-k=move]').dataset.v;x.resume();
        S.p.slow=c.slow?2:0;S.p.hp=c.lowhp?S.p.mhp*.3:S.p.hp;x.keys={KeyD:true};p.x=0;
        x.update(1/30);const dx=p.x;x.keys={};
        return {c:c.nm,row,shown,real:dx/(1/30)/p.sp}}"""
    MCASES = [{'nm': '기본', 'ch': 'brj'}, {'nm': '신발 3 · 끈 고쳐 묶기 2', 'ch': 'brj', 'ps': {'spd': 3}, 'sm': {'spd': 2}}, {'nm': '조선제일하리보(+20%) · 거북 2 · 철갑 1', 'ch': 'hrb', 'ps': {'turtle': 2}, 'tr': {'iron': 1}},
              {'nm': '질풍 2 + 줄행랑(맞은 직후 Lv2)', 'ch': 'brj', 'tr': {'gale': 2}, 'rel': {'sprint': 2}, 'spr': True}, {'nm': '배수의 진 + 체력 40% 이하', 'ch': 'brj', 'rel': {'berserk': 2}, 'lowhp': True},
              {'nm': '용 변신(프싱)', 'ch': 'psg', 'dT': 5}, {'nm': '종소리 버프', 'ch': 'brj', 'bell': True}, {'nm': '느려짐(📜) 걸림', 'ch': 'brj', 'ps': {'spd': 2}, 'slow': True}, {'nm': '단단묵직(−10%)', 'ch': 'ddmj'}]
    for c in MCASES:
        r = await pg.evaluate(MV, c)
        check('[다] 이동 — %s: 표 %.4f · 실제 한 프레임 이동 비율 %.4f' % (c['nm'], r['row'], r['real']), abs(r['real'] - r['row']) < 1e-9 and abs(r['shown'] - r['row']) < 1e-12, r)
    check('[다] 이동 오류 0', not errs, errs); await ctx.close()
    # 줍는 범위 · 경험치
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    GEM = r"""(c)=>{const x=__p6x,X=__X;x.CH_set(c.ch);x.start();const S=x.S,p=S.p;x.enemies.clear();S.live.length=0;S.t=1;S.nextBoss=S.nextMini=S.nextSp=1e9;S.evT=1e9;S.bigT=1e9;S.spawnT=-1e9;
        const A=(o)=>x.applyUp(o);for(const k in (c.ps||{}))for(let i=0;i<c.ps[k];i++)A({t:'p',k,l:i});for(const k in (c.sm||{}))for(let i=0;i<c.sm[k];i++)A({t:'sm',k:'sm:'+k,r:k,l:i});if(c.syn)S.syn=c.syn;if(c.pt)for(const k in c.pt)S.pt[k]=c.pt[k];
        __X.pauseGame();const mg=+document.querySelector('#sttp .rw[data-k=mag]').dataset.v,xm=+document.querySelector('#sttp .rw[data-k=xp]').dataset.v;x.resume();
        const R=70*mg;const put=(d,v)=>{const g=x.gems.get();g.x=p.x+d;g.y=p.y;g.v=v;g.mag=0;return g;};
        x.gems.clear();const gin=put(R-.5,1),gout=put(R+.5,1);x.keys={};x.update(1/30);
        const magIn=gin.mag,magOut=gout.mag;
        x.gems.clear();S.xp=0;S.need=1e9;S.lv=1;const g=put(0,10);x.update(1/30);const gained=S.xp;
        return {c:c.nm,mg,xm,R,magIn,magOut,gained,want:10*X.XP_X*xm}}"""
    GCASES = [{'nm': '기본', 'ch': 'brj'}, {'nm': '자석 3 · 초월 1 · 자석 손질 2', 'ch': 'brj', 'ps': {'mag': 3}, 'pt': {'mag': 1}, 'sm': {'mag': 2}}, {'nm': '유미(줍기 +40%·경험치) + 공부 3 + 시너지', 'ch': 'yumi', 'ps': {'mag': 1, 'study': 3}, 'syn': {'dmg': 0, 'cd': 0, 'area': 0, 'xp': .12, 'luck': 0}},
              {'nm': '일단즐겨(경험치 +20%)', 'ch': 'ildj', 'ps': {'study': 2}}, {'nm': '김야옹(줍기 +50%)', 'ch': 'kyo'}]
    for c in GCASES:
        r = await pg.evaluate(GEM, c)
        check('[다] 줍는 범위 — %s: 표 +%.0f%% → 반경 %.1f · 안쪽(%.1f)은 끌려오고(mag=%s) 바깥쪽은 안 끌려온다(mag=%s)' % (c['nm'], (r['mg'] - 1) * 100, r['R'], r['R'] - .5, r['magIn'], r['magOut']), r['magIn'] == 1 and r['magOut'] == 0, r)
        check('[다] 경험치 — %s: 표 ×%.4f → 보석 10 → 실제 %.4f (기대 %.4f)' % (c['nm'], r['xm'], r['gained'], r['want']), abs(r['gained'] - r['want']) < 1e-9, r)
    check('[다] 줍기·경험치 오류 0', not errs, errs); await ctx.close()
    # 받는 피해 · 고기 반찬
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    HIT = r"""(c)=>{const x=__p6x,X=__X;x.CH_set(c.ch);x.start();const S=x.S,p=S.p;S.t=1;
        const A=(o)=>x.applyUp(o);for(const k in (c.ps||{}))for(let i=0;i<c.ps[k];i++)A({t:'p',k,l:i});for(const k in (c.tr||{}))for(let i=0;i<c.tr[k];i++)A({t:'tr',k:'tr:'+k,r:k,l:i});if(c.pt)for(const k in c.pt)S.pt[k]=c.pt[k];if(c.dT)S.dT=c.dT;
        p.mhp=p.hp=5000;p.moving=!!c.moving;S.shield=0;S.lastBlock=-99;
        __X.pauseGame();const r=document.querySelector('#sttp .rw[data-k=taken]'),a=+r.dataset.a,m=+r.dataset.v;x.resume();p.moving=!!c.moving;
        const out=[];for(const d of c.ds){p.inv=0;p.hp=5000;x.hitP(d);out.push([d,5000-p.hp,Math.max(1,d*m-a)]);}
        return {c:c.nm,a,m,out}}"""
    HCASES = [{'nm': '기본', 'ch': 'brj', 'ds': [1, 5, 30, 100]}, {'nm': '깃털 갑옷 3 · 거북 2 · 철갑 2', 'ch': 'brj', 'ps': {'arm': 3, 'turtle': 2}, 'tr': {'iron': 2}, 'ds': [1, 3, 8, 12, 40, 250]},
              {'nm': '광분 2(받는 피해 +20%)', 'ch': 'brj', 'ps': {'glass': 2}, 'ds': [10, 100]}, {'nm': '이동 중 초월 2(−6%) · 걷는 중', 'ch': 'brj', 'ps': {'spd': 5}, 'pt': {'spd': 2}, 'moving': True, 'ds': [10, 100]},
              {'nm': '단단묵직(−3)', 'ch': 'ddmj', 'ds': [2, 3, 4, 50]}, {'nm': '용 변신 중(−30%)', 'ch': 'psg', 'dT': 5, 'ds': [10, 200]}]
    for c in HCASES:
        r = await pg.evaluate(HIT, c)
        ok = all(abs(real - exp) < 1e-9 for _, real, exp in r['out'])
        check('[다] 받는 피해 — %s: 표 −%s · ×%.3f → 실제로 맞아 본 피해 %s' % (c['nm'], fnum(r['a']), r['m'], [(d, round(real, 3)) for d, real, _ in r['out']]), ok, r)
    VAMP = r"""()=>{const x=__p6x,X=__X;x.CH_set('brj');x.start();const S=x.S,p=S.p;for(let i=0;i<3;i++)x.applyUp({t:'p',k:'vamp',l:i});
        __X.pauseGame();const t=document.querySelector('#sttp .rw[data-k=vamp] .v').textContent;x.resume();
        p.mhp=500;p.hp=100;S.vk=X.VAMP_N-1;const e=x.spawnEnemy(0,1);e.on=true;e.x=1e6;e.y=1e6;e.hp=1;e.mhp=1;x.hurt(e,10);
        const heal=p.hp-100;S.vk=0;let n=0;p.hp=100;const hist=[];for(let i=0;i<X.VAMP_N*2;i++){const e2=x.spawnEnemy(0,1);e2.on=true;e2.x=1e6;e2.y=1e6;e2.hp=1;e2.mhp=1;const h0=p.hp;x.hurt(e2,10);if(p.hp>h0)hist.push([i+1,p.hp-h0]);}
        return {t,heal,vampHp:X.vampHp(),N:X.VAMP_N,hist}}"""
    r = await pg.evaluate(VAMP)
    check('[다] 고기 반찬 — 표 「%s」 = 실제: 처치 %d번째마다 +%s HP (관찰 %s)' % (r['t'], r['N'], fnum(r['vampHp']), r['hist']), r['t'] == '%d마리마다 +%s HP' % (r['N'], fnum(r['vampHp'])) and abs(r['heal'] - r['vampHp']) < 1e-9 and [h[0] for h in r['hist']] == [r['N'], r['N'] * 2] and all(abs(h[1] - r['vampHp']) < 1e-9 for h in r['hist']), r)
    check('[다] 받는 피해·고기 반찬 오류 0', not errs, errs); await ctx.close()

# ── 라 · 보유 목록 ─────────────────────────────────────────────
RICH = r"""(a)=>{const x=__p6x,X=__X;x.CH_set(a.ch);x.start();const S=x.S;const A=(o)=>x.applyUp(o);
  for(const k of a.w){const t=(S.w[k]||0);if(!t)A({t:'w',k,l:0});}
  for(const k in a.wl)while(S.w[k]<a.wl[k])A({t:'w',k,l:S.w[k]});
  for(const k in a.ps)for(let i=S.ps[k]||0;i<a.ps[k];i++)A({t:'p',k,l:i});
  for(const k in (a.pt||{}))S.pt[k]=a.pt[k];for(const k of (a.ev||[])){S.ev[k]=1;}for(const k in (a.tier||{}))S.tier[k]=a.tier[k];x.tkCalc();
  for(const k in (a.rel||{}))S.rel[k]=a.rel[k];for(const k in (a.tr||{}))for(let i=0;i<a.tr[k];i++)A({t:'tr',k:'tr:'+k,r:k,l:i});
  for(const k in (a.sm||{}))for(let i=0;i<a.sm[k];i++)A({t:'sm',k:'sm:'+k,r:k,l:i});
  x.synCalc();S.pendingLv=a.pending||1;return {w:Object.keys(S.w),ps:Object.keys(S.ps),syn:S.synOn.slice(),rel:Object.keys(S.rel),tr:Object.keys(S.tr)}}"""
OWN = r"""()=>{const x=__p6x,S=x.S,X=__X;const chips=[...document.querySelectorAll('#lvOwn .chip')].map(c=>({k:c.dataset.ck,up:c.classList.contains('up'),m:!!c.querySelector('.upm'),t:c.innerText.replace(/\s+/g,' ').trim()}));
  const heads=[...document.querySelectorAll('#lvOwn .gh')].map(h=>h.innerText.replace(/\s+/g,' ').trim());
  return {chips,heads,S:{w:Object.keys(S.w),wl:Object.assign({},S.w),ps:Object.keys(S.ps),psl:Object.assign({},S.ps),pt:Object.assign({},S.pt),ev:Object.keys(S.ev),tier:Object.assign({},S.tier),rel:Object.keys(S.rel),rell:Object.assign({},S.rel),tr:Object.keys(S.tr),trl:Object.assign({},S.tr),
      sm:Object.keys(X.SM).filter(k=>X.smn(k)>0),sml:Object.fromEntries(Object.keys(X.SM).map(k=>[k,X.smn(k)])),syn:S.synOn.slice(),slotP:X.slotP()},
    children:[...document.getElementById('choices').children].map(c=>c.className),lvOwnInChoices:!!document.querySelector('#choices #lvOwn'),own:!!document.querySelector('#lvOwn .own'),cards:document.querySelectorAll('#choices .ch').length}}"""
def expect_keys(S):
    k = ['w:' + a for a in S['w']] + ['p:' + a for a in S['ps']] + ['r:' + a for a in S['rel']] + ['t:' + a for a in S['tr']] + ['s:' + a for a in S['sm']] + ['y:' + a for a in S['syn']]
    return k
RICH_CASES = {
    'full': {'ch': 'jjg', 'w': ['tempo', 'fryer', 'feed', 'egg', 'shrimp', 'sushi'], 'wl': {'tempo': 8, 'fryer': 6, 'feed': 4, 'egg': 3, 'shrimp': 2, 'sushi': 8},
             'ps': {'arm': 5, 'spd': 3, 'cd': 5, 'mag': 2, 'crit': 3, 'luck': 2}, 'pt': {'arm': 1, 'cd': 2}, 'ev': ['tempo'], 'tier': {'tempo': 2, 'sushi': 3},
             'rel': {'tenth': 2, 'leech': 1, 'sg_jjg': 3}, 'tr': {'gale': 1, 'focus': 1, 'glassc': 2}, 'sm': {'crit': 2, 'ramen': 1, 'hp': 1}, 'pending': 1},
    'early': {'ch': 'eom', 'w': [], 'wl': {}, 'ps': {}, 'pending': 1},
}
async def sec_own(b, srv):
    # (1) 꽉 찬 빌드 — S 와 정확히 일치
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    info = await pg.evaluate(RICH, RICH_CASES['full'])
    await pg.evaluate("()=>{const x=__p6x;x.state='lvup';__X.openLvup()}")
    o = await pg.evaluate(OWN); S = o['S']
    check('[라] 꽉 찬 빌드 — 칩 키 목록(순서까지) = S 의 무기·패시브·유물·거래·작은 능력치·시너지 %d개' % len(o['chips']), [c['k'] for c in o['chips']] == expect_keys(S) and len(o['chips']) >= 20, ([c['k'] for c in o['chips']], expect_keys(S)))
    check('[라] 갈래 제목: ⚔ 무기 6/6 · 각성 · 🎒 패시브 6/6 · 🏺 유물 · ⚖ 거래 · 🍴 작은 능력치 · 🔗 켜진 시너지', o['heads'][0].startswith('⚔ 무기 6/6 · ✨ 각성 1/3') and o['heads'][1].startswith('🎒 패시브 6/6')
          and any(h.startswith('🏺 유물 3') for h in o['heads']) and any(h.startswith('⚖ 거래 3') for h in o['heads']) and any(h.startswith('🍴 작은 능력치 3') for h in o['heads']) and any(h.startswith('🔗 켜진 시너지 %d' % len(S['syn'])) for h in o['heads']), o['heads'])
    byk = {c['k']: c['t'] for c in o['chips']}
    bad = []
    for k in S['w']:
        t = byk['w:' + k]; L = S['wl'][k]
        if k in S['ev']:
            if '✨ 각성' not in t: bad.append(('각성 표시', k, t))
        else:
            if 'Lv%d/8' % L not in t.replace(' ', ''): bad.append(('Lv', k, t))
            if '각성 열쇠: Lv8 %s' % ('✔' if L >= 8 else '✖') not in t: bad.append(('Lv8 조건', k, t))
        if S['tier'].get(k) and ('%s%d/%d' % ('✨' if k in S['ev'] else '🏅', S['tier'][k], 5 if k in S['ev'] else 3)) not in t: bad.append(('단계', k, t))
    for k in S['ps']:
        t = byk['p:' + k]
        if 'Lv%d/' % S['psl'][k] not in t.replace(' ', ''): bad.append(('패시브 Lv', k, t))
        if S['pt'].get(k) and ('🌟%d/' % S['pt'][k]) not in t: bad.append(('초월', k, t))
    for k in S['rel']:
        if 'Lv%d/3' % S['rell'][k] not in byk['r:' + k].replace(' ', ''): bad.append(('유물', k, byk['r:' + k]))
    for k in S['tr']:
        if '×%d/' % S['trl'][k] not in byk['t:' + k].replace(' ', ''): bad.append(('거래', k, byk['t:' + k]))
    for k in S['sm']:
        if '×%d/' % S['sml'][k] not in byk['s:' + k].replace(' ', ''): bad.append(('작은', k, byk['s:' + k]))
    check('[라] 칩 글자 — 무기 Lv·각성·마스터 단계·짝 패시브 ✔/✖ · 패시브 Lv·🌟 · 유물 Lv · 거래 ×n · 작은 능력치 ×n 이 S 와 같다', not bad, bad[:5])
    check('[라] 새 컨테이너는 #choices 바깥 — 앞 세 자식은 그대로 카드 3장 + 다시 뽑기 줄', not o['lvOwnInChoices'] and o['children'][:3] == ['ch', 'ch', 'ch'] and o['children'][3] == 'lvx' and o['cards'] == 3, o['children'])
    # ▲ — 카드가 올려 주는 칩만
    r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,X=__X;const w=Object.keys(S.w);
      const cards=[{t:'w',k:'fryer',l:S.w.fryer},{t:'p',k:'cd',l:S.ps.cd},{t:'wt',k:'wt:tempo',w:'tempo',l:S.tier.tempo},{t:'pt',k:'pt:arm',p:'arm',l:1},{t:'rl',k:'rl:tenth',r:'tenth',l:2},{t:'tr',k:'tr:gale',r:'gale',l:1},{t:'sm',k:'sm:crit',r:'crit',l:2},
        {t:'w',k:'kbd',l:0},{t:'p',k:'dur',l:0},{t:'co',k:'co:feast',r:'feast'},{t:'heal',k:'heal'},{t:'rl',k:'rl:storm',r:'storm',l:0},{t:'tr',k:'tr:swift',r:'swift',l:0},{t:'sm',k:'sm:mag',r:'mag',l:0}];
      __X.setCUR(cards);__X.drawCards();return cards.map(c=>__X.cardKey(c))}""")
    o = await pg.evaluate(OWN)
    ups = [c['k'] for c in o['chips'] if c['up']]
    want_up = ['w:fryer', 'p:cd', 'w:tempo', 'p:arm', 'r:tenth', 't:gale', 's:crit']
    check('[라] ▲(금색 테두리)는 카드가 올려 주는 칩만 — 기대 %s · 실제 %s' % (want_up, ups), sorted(ups) == sorted(want_up) and all(c['m'] == c['up'] for c in o['chips']), (ups, r))
    check('[라] 새 무기·새 패시브·새 유물·새 거래·새 작은 능력치·일회용·치킨 카드는 칩이 없으니 ▲ 도 없다(cardKey 가 빈 글자)', r[7:] == ['', '', '', '', '', '', ''], r)
    check('[라] 카드가 하나도 안 올려 주면 안내 「▲ 금색」 줄이 없다', await pg.evaluate("""()=>{__X.setCUR([{t:'co',k:'co:feast',r:'feast'},{t:'heal',k:'heal'},{t:'w',k:'kbd',l:0}]);__X.drawCards();return !document.querySelector('#lvOwn .lg')&&!document.querySelector('#lvOwn .chip.up')}"""))
    # 다시 뽑기 → ▲ 갱신 / 카드 고르기 → 다음 레벨업에서 갱신
    await pg.evaluate("()=>{__X.setCUR([{t:'w',k:'fryer',l:__p6x.S.w.fryer},{t:'p',k:'spd',l:__p6x.S.ps.spd},{t:'co',k:'co:feast',r:'feast'}]);__p6x.S.pendingLv=2;__X.drawCards();}")
    a0 = await pg.evaluate(OWN)
    check('[라] ▲ 가 지금 떠 있는 카드에 맞춰 바뀐다(튀김·신발)', sorted(c['k'] for c in a0['chips'] if c['up']) == ['p:spd', 'w:fryer'], [c['k'] for c in a0['chips'] if c['up']])
    lv0 = a0['S']['wl']['fryer']; sp0 = a0['S']['psl']['spd']
    await pg.click('#choices .ch:nth-child(1)')    # 진짜 클릭으로 고른다(튀김기 레벨업)
    await pg.wait_for_function("__p6x.state==='lvup'||__p6x.state==='play'", timeout=20000)
    st = await pg.evaluate("()=>__p6x.state")
    check('[라] 카드를 고르면 남은 레벨업이 있어 다시 선택창(%s)' % st, st == 'lvup', st)
    a1 = await pg.evaluate(OWN)
    t1 = {c['k']: c['t'] for c in a1['chips']}['w:fryer'].replace(' ', '')
    check('[라] 고른 뒤 다음 레벨업에서 목록이 갱신 — 튀김기 Lv%d → Lv%d' % (lv0, lv0 + 1), a1['S']['wl']['fryer'] == lv0 + 1 and ('Lv%d/8' % (lv0 + 1)) in t1, (a1['S']['wl'], t1))
    check('[라] 다음 선택창에서도 칩 키 = S', [c['k'] for c in a1['chips']] == expect_keys(a1['S']), ([c['k'] for c in a1['chips']], expect_keys(a1['S'])))
    # 오류
    check('[라] 꽉 찬 빌드 오류 0', not errs, errs)
    await ctx.close()
    # (2) 초반 빈 빌드 — 무기 하나뿐, 없는 갈래는 안 그린다
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate(RICH, RICH_CASES['early'])
    await pg.evaluate("()=>{__p6x.state='lvup';__X.openLvup()}")
    o = await pg.evaluate(OWN)
    check('[라] 초반 — 무기 칩 하나뿐 · 제목은 「⚔ 무기 1/6」 하나 · 패시브·유물·거래·작은 능력치·시너지 갈래는 아예 안 그린다', len(o['chips']) == 1 and o['heads'] == ['⚔ 무기 1/6 · ✨ 각성 0/3'] and o['chips'][0]['k'].startswith('w:'), (o['heads'], [c['k'] for c in o['chips']]))
    check('[라] 초반 오류 0', not errs, errs)
    await ctx.close()
    # (3) 키보드 1·2·3·R·B
    for key in ('1', '2', '3'):
        ctx, pg, errs = await new_page(b, srv.port, page=NEW)
        await pg.evaluate(RICH, dict(RICH_CASES['early'], pending=1))
        await pg.evaluate("()=>{__p6x.state='lvup';__X.openLvup();__X.setCUR([{t:'w',k:'kbd',l:0},{t:'p',k:'cd',l:0},{t:'p',k:'mag',l:0}]);__X.drawCards();}")   # 카드를 못 박아 둔다 — 어느 숫자가 어느 카드인지 엄격히 본다
        before = await pg.evaluate("()=>[Object.keys(__p6x.S.w),Object.keys(__p6x.S.ps)]")
        await pg.keyboard.press('Digit' + key)
        await pg.wait_for_function("__p6x.state==='play'", timeout=20000)
        after = await pg.evaluate("()=>[Object.keys(__p6x.S.w),Object.keys(__p6x.S.ps)]")
        got = ('kbd' in after[0], 'cd' in after[1], 'mag' in after[1])
        check('[라] 키보드 %s → %d번째 카드만 고른다(무기 키보드 · 패시브 공격속도 · 패시브 획득 범위 중 %s)' % (key, int(key), got), got == tuple(i == int(key) - 1 for i in range(3)) and before[1] == [], (before, after))
        check('[라] 키보드 %s 오류 0' % key, not errs, errs)
        await ctx.close()
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate(RICH, dict(RICH_CASES['early'], pending=1))
    await pg.evaluate("()=>{__p6x.state='lvup';__X.openLvup()}")
    r0 = await pg.evaluate("()=>({rr:__p6x.S.rr,cur:__X.CUR.map(o=>o.k||o.t),own:document.getElementById('lvOwn').innerHTML.length})")
    await pg.keyboard.press('KeyR')
    r1 = await pg.evaluate("()=>({rr:__p6x.S.rr,cur:__X.CUR.map(o=>o.k||o.t),state:__p6x.state,ups:[...document.querySelectorAll('#lvOwn .chip.up')].map(c=>c.dataset.ck),cards:document.querySelectorAll('#choices .ch').length})")
    check('[라] 키보드 R — 다시 뽑기 %d → %d · 카드 3장 · 목록이 새 카드에 맞춰 다시 그려진다' % (r0['rr'], r1['rr']), r1['rr'] == r0['rr'] - 1 and r1['state'] == 'lvup' and r1['cards'] == 3, (r0, r1))
    await pg.keyboard.press('KeyB')
    r2 = await pg.evaluate("()=>({ban:__p6x.S.ban,mode:__p6x.S.banMode,cls:document.getElementById('banBtn').className,cards:document.querySelectorAll('#choices .ch').length,own:!!document.querySelector('#lvOwn .own'),hint:document.getElementById('lvHint').textContent})")
    check('[라] 키보드 B — 봉인 모드 켜짐 · 카드 3장 · 목록도 그대로 있다', r2['mode'] is True and 'on' in r2['cls'].split() and r2['cards'] == 3 and r2['own'], r2)
    await pg.keyboard.press('KeyB')
    r3 = await pg.evaluate("()=>({mode:__p6x.S.banMode})")
    check('[라] 키보드 B 한 번 더 — 봉인 모드 꺼짐', r3['mode'] is False, r3)
    check('[라] R·B 오류 0', not errs, errs)
    await ctx.close()
    # (4) 이어하기 복구 뒤에도 보인다 (레벨업 저장본 → 새 페이지 → 복구)
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate(RICH, RICH_CASES['full'])
    await pg.evaluate("()=>{const x=__p6x;x.state='lvup';__X.openLvup()}")
    blob = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')")
    pre = await pg.evaluate(OWN)
    await ctx.close()
    check('[라] 레벨업 순간 저장본이 만들어졌다', blob is not None and len(blob) > 100, blob and len(blob))
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", blob)
    await pg.reload(); await pg.wait_for_function('window.__X!==undefined')
    ok = await pg.evaluate("()=>__X.RES.restore()")
    st = await pg.evaluate("()=>__p6x.state")
    o = await pg.evaluate(OWN)
    check('[라] 이어하기 복구 → 레벨업 선택창(%s) · 「내가 가진 능력」이 복구 뒤에도 보이고 복구 전과 같다' % st, ok is True and st == 'lvup' and o['own'] and [c['k'] for c in o['chips']] == [c['k'] for c in pre['chips']] == expect_keys(o['S']) and [c['up'] for c in o['chips']] == [c['up'] for c in pre['chips']], (ok, st, [c['k'] for c in o['chips']][:6]))
    check('[라] 복구 뒤에도 카드 3장 + 다시 뽑기 줄 · 표(#sttl)도 있다', o['children'][:3] == ['ch', 'ch', 'ch'] and bool(await pg.evaluate("()=>!!document.getElementById('sttl')")), o['children'])
    check('[라] 이어하기 오류 0', not errs, errs)
    await ctx.close()

# ── 마 · 접이식 ────────────────────────────────────────────────
async def sec_fold(b, srv):
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate(RICH, RICH_CASES['full'])
    await pg.evaluate("()=>__X.pauseGame()")
    st = await pg.evaluate("()=>({tag:document.getElementById('sttp').tagName,open:document.getElementById('sttp').open,rows:document.querySelectorAll('#sttp .rw').length,vis:document.getElementById('sttp').querySelector('.rw').checkVisibility()})")
    check('[마] 일시정지 — 표는 기본으로 펼쳐져 있다(details open · 행 %d개가 보인다)' % st['rows'], st['tag'] == 'DETAILS' and st['open'] and st['rows'] == 14 and st['vis'], st)
    await pg.click('#sttp > summary')
    await pg.wait_for_function("__X.UI3.pOpen===false", timeout=15000)
    await pg.evaluate("()=>{__p6x.resume();__X.pauseGame()}")
    st = await pg.evaluate("()=>({open:document.getElementById('sttp').open,ui:Object.assign({},__X.UI3)})")
    check('[마] 일시정지 — 접어 두면 다음 일시정지에도 접혀 있다(UI3 에 기억 · S 가 아니다)', st['open'] is False and st['ui']['pOpen'] is False, st)
    await pg.click('#sttp > summary'); await pg.wait_for_function("__X.UI3.pOpen===true", timeout=15000)
    await pg.evaluate("()=>{__p6x.resume();__X.pauseGame()}")
    check('[마] 일시정지 — 다시 펴면 다시 펼쳐진다', await pg.evaluate("()=>document.getElementById('sttp').open") is True)
    # 레벨업: 기본 접힘 → 열면 기억
    await pg.evaluate("()=>{__p6x.resume();const S=__p6x.S;S.pendingLv=3;__p6x.state='lvup';__X.openLvup()}")
    st = await pg.evaluate("()=>({tag:document.getElementById('sttl').tagName,open:document.getElementById('sttl').open,rowsVisible:document.querySelector('#sttl .rw').checkVisibility(),rows:document.querySelectorAll('#sttl .rw').length,cards:document.querySelectorAll('#choices .ch').length})")
    check('[마] 레벨업 — 표는 기본 접힘(카드가 먼저): details 닫힘 · 행은 안 보인다 · 카드 3장', st['tag'] == 'DETAILS' and st['open'] is False and not st['rowsVisible'] and st['rows'] == 14 and st['cards'] == 3, st)
    await pg.click('#sttl > summary'); await pg.wait_for_function("__X.UI3.lOpen===true", timeout=15000)
    await pg.evaluate("()=>__X.drawCards()")      # 다시 뽑기·봉인 모드가 화면을 다시 그린다
    check('[마] 레벨업 — 연 표는 다시 그려도(다시 뽑기·봉인) 열려 있다', await pg.evaluate("()=>document.getElementById('sttl').open") is True)
    await pg.click('#choices .ch:nth-child(1)')
    await pg.wait_for_function("__p6x.state==='lvup'", timeout=20000)
    check('[마] 레벨업 — 카드를 고른 뒤 다음 선택창에서도 열려 있다', await pg.evaluate("()=>document.getElementById('sttl').open") is True)
    await pg.click('#sttl > summary'); await pg.wait_for_function("__X.UI3.lOpen===false", timeout=15000)
    await pg.evaluate("()=>__X.drawCards()")
    check('[마] 레벨업 — 접으면 접힌 채로 기억', await pg.evaluate("()=>document.getElementById('sttl').open") is False)
    check('[마] 일시정지 표와 레벨업 표는 따로 기억한다', await pg.evaluate("()=>[__X.UI3.pOpen,__X.UI3.lOpen]") == [True, False])
    # 같은 표 — 일시정지와 레벨업의 행 값이 같다(같은 상태에서)
    same = await pg.evaluate("""()=>{const q=id=>[...document.querySelectorAll('#'+id+' .rw')].map(r=>[r.dataset.k,r.dataset.v,r.querySelector('.v').textContent]);
      const l=q('sttl');__p6x.S.pendingLv=0;__X.pauseGame();const p=q('sttp');return {same:JSON.stringify(l)===JSON.stringify(p),n:l.length}}""")
    check('[마] 같은 상태에서 일시정지 표와 레벨업 표의 값·글자가 같다(함수 하나가 두 곳에 그린다)', same['same'] and same['n'] == 14, same)
    check('[마] 오류 0', not errs, errs)
    await ctx.close()

# ── 바 · 레이아웃 ──────────────────────────────────────────────
VIEWS = [(320, 568), (360, 640), (390, 844), (412, 915), (640, 360), (844, 390), (1280, 800)]
LAY_LV = r"""()=>{const R=e=>{const r=e.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}};
  const box=document.querySelector('#lvup .box'),de=document.documentElement;
  const q=s=>[...document.querySelectorAll(s)];
  const cards=q('#choices .ch'),rr=document.getElementById('rrBtn'),ban=document.getElementById('banBtn'),own=document.querySelector('#lvOwn .own'),st=document.getElementById('sttl'),hint=document.getElementById('lvHint');
  const reach=e=>{e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect(),bb=box.getBoundingClientRect(),cx=Math.min(innerWidth-1,Math.max(0,r.left+r.width/2)),lo=Math.max(r.top+1,bb.top+1),hi=Math.min(r.bottom-1,bb.bottom-1,innerHeight-1),cy=Math.max(lo,Math.min(hi,(lo+hi)/2));   /* 칸이 스크롤 상자보다 길면 상자 안에 보이는 부분의 한가운데를 누른다(상자 밖 바탕을 누르면 안 된다) */const h=document.elementFromPoint(cx,cy);return !!h&&(e===h||e.contains(h))&&cy>=0&&cy<=innerHeight&&cx>=0&&cx<=innerWidth;};
  const out={iw:innerWidth,ih:innerHeight,sx:de.scrollWidth-innerWidth,bsx:box.scrollWidth-box.clientWidth,boxh:R(box).h,boxch:box.scrollHeight};
  out.reach={cards:cards.map(reach),rr:reach(rr),ban:reach(ban),own:reach(own),st:reach(st)};
  box.scrollTop=0;
  const rs={};cards.forEach((c,i)=>rs['c'+i]=R(c));rs.lvx=R(document.querySelector('#choices .lvx'));rs.own=R(own);rs.st=R(st);rs.hint=R(hint);
  const names=Object.keys(rs),ov=[];for(let i=0;i<names.length;i++)for(let j=i+1;j<names.length;j++){const a=rs[names[i]],b=rs[names[j]];const w=Math.min(a.r,b.r)-Math.max(a.l,b.l),h=Math.min(a.b,b.b)-Math.max(a.t,b.t);if(w>.5&&h>.5)ov.push([names[i],names[j],Math.round(w*h)]);}
  out.ov=ov;
  const ob=R(own),cb=[];for(const c of q('#lvOwn .chip')){const r=R(c);if(r.r>ob.r+.5||r.l<ob.l-.5)cb.push([c.dataset.ck,r.l,r.r,ob.l,ob.r]);}out.chipOut=cb;out.chips=q('#lvOwn .chip').length;
  const rowsBad=[];for(const rw of q('#sttl .rw')){const l=rw.querySelector('.l'),v=rw.querySelector('.v');if(!st.open)break;const a=R(l),b=R(v);const w=Math.min(a.r,b.r)-Math.max(a.l,b.l),h=Math.min(a.b,b.b)-Math.max(a.t,b.t);if((w>.5&&h>.5)||rw.scrollWidth>rw.clientWidth+1)rowsBad.push([rw.dataset.k,w,h,rw.scrollWidth,rw.clientWidth]);}
  out.rowsBad=rowsBad;
  // 칩 안 글자가 단어 중간에서 끊기지 않는다: 이름 글자(한글 연속)가 두 줄로 쪼개졌는지 — 칩 높이가 한 줄 높이의 몇 배인지로 본다(작은 글씨 줄 포함해 너무 높으면 의심)
  out.chipMaxH=Math.max(...q('#lvOwn .chip').map(c=>R(c).h));
  return out}"""
LAY_PA = r"""()=>{const R=e=>{const r=e.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}};
  const box=document.querySelector('#pause .box'),de=document.documentElement,q=s=>[...document.querySelectorAll(s)];
  const out={iw:innerWidth,ih:innerHeight,sx:de.scrollWidth-innerWidth,bsx:box.scrollWidth-box.clientWidth,stOpen:document.getElementById('sttp').open};
  const d=R(document.getElementById('pDiff')),m=R(document.getElementById('pMul')),st=R(document.getElementById('sttp'));
  const ov=[];const nm=['d','m','st'],rs=[d,m,st];for(let i=0;i<3;i++)for(let j=i+1;j<3;j++){const a=rs[i],b=rs[j];const w=Math.min(a.r,b.r)-Math.max(a.l,b.l),h=Math.min(a.b,b.b)-Math.max(a.t,b.t);if(w>.5&&h>.5)ov.push([nm[i],nm[j]]);}
  out.ov=ov;
  const bb=R(box);out.inBox=[d,m,st].every(r=>r.l>=bb.l-.5&&r.r<=bb.r+.5);
  const rowsBad=[];for(const rw of q('#sttp .rw')){const l=rw.querySelector('.l'),v=rw.querySelector('.v');const a=R(l),b=R(v);const w=Math.min(a.r,b.r)-Math.max(a.l,b.l),h=Math.min(a.b,b.b)-Math.max(a.t,b.t);if((w>.5&&h>.5)||rw.scrollWidth>rw.clientWidth+1)rowsBad.push([rw.dataset.k,w,h,rw.scrollWidth,rw.clientWidth]);}
  out.rowsBad=rowsBad;
  const btn=document.getElementById('resumeBtn');btn.scrollIntoView({block:'nearest'});const r=btn.getBoundingClientRect();const h=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);out.resumeReach=!!h&&(h===btn||btn.contains(h));
  const dd=document.getElementById('pDiff');dd.scrollIntoView({block:'nearest'});const rd=dd.getBoundingClientRect();out.diffVisible=rd.top>=0&&rd.bottom<=innerHeight;
  return out}"""
async def sec_layout(b, srv):
    for (w, h) in VIEWS:
        tag = '%dx%d' % (w, h)
        # 레벨업 — 꽉 찬 빌드(표 접힘 · 펼침) / 초반
        for nm, case, op in (('꽉 찬 빌드·표 접힘', 'full', False), ('꽉 찬 빌드·표 펼침', 'full', True), ('초반', 'early', False)):
            ctx, pg, errs = await new_page(b, srv.port, w=w, h=h, page=NEW, mobile=(w < 700))
            await pg.evaluate(RICH, RICH_CASES[case])
            await pg.evaluate("(op)=>{__X.UI3.lOpen=op;__p6x.state='lvup';__X.openLvup();__p6x.S.rr=3;__p6x.S.ban=3;__X.drawCards();}", op)
            r = await pg.evaluate(LAY_LV)
            check('[바] %s %s 레벨업 — 가로 넘침 0 (페이지 %d · 박스 %d)' % (tag, nm, r['sx'], r['bsx']), r['sx'] <= 0 and r['bsx'] <= 0, r)
            check('[바] %s %s 레벨업 — 카드 3장 · 다시 뽑기 · 봉인 · 목록 · 표가 스크롤로 닿는다(실제로 눌릴 위치) %s' % (tag, nm, r['reach']), all(r['reach']['cards']) and r['reach']['rr'] and r['reach']['ban'] and r['reach']['own'] and r['reach']['st'], r['reach'])
            check('[바] %s %s 레벨업 — 카드·버튼·목록·표가 서로 겹치지 않는다' % (tag, nm), not r['ov'], r['ov'])
            check('[바] %s %s 레벨업 — 칩 %d개가 목록 칸 안(좌우)에 있다 · 표 행의 이름·값이 안 겹친다' % (tag, nm, r['chips']), not r['chipOut'] and not r['rowsBad'], (r['chipOut'][:3], r['rowsBad'][:3]))
            check('[바] %s %s 레벨업 오류 0' % (tag, nm), not errs, errs)
            await ctx.close()
        # 일시정지 — 일반·베리하드(난이도 줄 색 달라도 같은 칸) · 표 펼침 · 꽉 찬 빌드
        for mode in ('normal', 'vh', 'over'):   # over: 치명타 확률이 100% 를 넘어 「100% (초과 +N%p)」 처럼 가장 긴 글자가 나오는 경우
            ctx, pg, errs = await new_page(b, srv.port, w=w, h=h, page=NEW, mobile=(w < 700))
            await pg.evaluate("(m)=>{document.getElementById('hardChk').checked=false;document.getElementById('vhChk').checked=(m==='vh');}", mode)
            await pg.evaluate(RICH, dict(RICH_CASES['full'], ch='jjg'))
            await pg.evaluate("(m)=>{const x=__p6x;x.S.hard=m==='vh';x.S.vh=m==='vh'?1:0;if(m==='over')x.CH.crit=.95;__X.UI3.pOpen=true;__X.pauseGame();}", mode)
            if mode == 'over':
                t = await pg.evaluate("()=>document.querySelector('#sttp .rw[data-k=crit] .v').textContent")
                check('[바] %s 100%% 넘는 치명타 글자가 실제로 나왔다 「%s」' % (tag, t), t.startswith('100% (초과 +'), t)
            r = await pg.evaluate(LAY_PA)
            check('[바] %s %s 일시정지 — 가로 넘침 0 · 난이도 줄·배율 줄·표가 박스 안 · 서로 안 겹침' % (tag, mode), r['sx'] <= 0 and r['bsx'] <= 0 and r['inBox'] and not r['ov'], r)
            check('[바] %s %s 일시정지 — 표 행의 이름·값이 안 겹치고 넘치지 않는다 · 계속하기가 눌린다 · 난이도 줄이 스크롤로 닿는다' % (tag, mode), not r['rowsBad'] and r['resumeReach'] and r['diffVisible'], r)
            check('[바] %s %s 일시정지 오류 0' % (tag, mode), not errs, errs)
            await ctx.close()

# ── 사 · 불변 ──────────────────────────────────────────────────
def toplevel_lets(src):
    body = src[src.index("(()=>{\n'use strict';"):]
    names = set()
    for line in body.split('\n'):
        if line.startswith('let '):
            for m in re.finditer(r'(?:^let |,)\s*([A-Za-z_$][\w$]*)\s*=', line.split('//')[0]):
                names.add(m.group(1))
    return names
async def sec_invariant(b, srv):
    new_src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    old_src = open(os.path.join(ROOT, OLDSRC), encoding='utf-8').read()
    nl, ol = toplevel_lets(new_src), toplevel_lets(old_src)
    check('[사] 새 최상위 let 0 — 기준 커밋과 같은 %d개(늘어난 것 %s · 사라진 것 %s)' % (len(ol), sorted(nl - ol), sorted(ol - nl)), nl == ol and len(ol) > 20, (sorted(nl - ol), sorted(ol - nl)))
    # S 키 · 이어하기 서명
    res = {}
    for nm, pgn in (('old', OLD), ('new', NEW)):
        ctx, pg, errs = await new_page(b, srv.port, page=pgn)
        res[nm] = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('jjg');x.start();const S=x.S;for(let i=0;i<3;i++)x.applyUp({t:'p',k:'crit',l:i});__X.pauseGame();
          return {keys:Object.keys(S).sort(),sig:__X.RES.SIG,st:x.state,saved:localStorage.getItem('p6_resume_v1')!==null}}""")
        res[nm]['errs'] = errs; await ctx.close()
    check('[사] 새 S 키 0 — 새 판의 S 키 %d개가 기준 커밋과 같다' % len(res['old']['keys']), res['new']['keys'] == res['old']['keys'], (sorted(set(res['new']['keys']) - set(res['old']['keys'])), sorted(set(res['old']['keys']) - set(res['new']['keys']))))
    check('[사] 이어하기 서명(RES.SIG) 불변 — %s' % res['new']['sig'], res['new']['sig'] == res['old']['sig'] and res['new']['sig'].startswith('1:'), (res['old']['sig'], res['new']['sig']))
    check('[사] 일시정지 저장본이 새 빌드에서도 만들어진다', res['new']['saved'] and res['old']['saved'], res)
    # 표시 함수는 판을 바꾸지 않고 난수를 쓰지 않는다 — 이어하기 직렬화기(RES.build)로 S·풀 전체를 찍어 전후를 견준다
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate(RICH, RICH_CASES['full'])
    r = await pg.evaluate("""()=>{const x=__p6x,X=__X;x.S.pendingLv=1;__X.setCUR(x.offers(3));x.state='lvup';
      const snap=()=>{const b=X.RES.build();return b.body||('ERR '+b.why)};
      let calls=0;const orig=Math.random;Math.random=function(){calls++;return orig.call(Math)};
      const a=snap();const outs=[X.diffHtml(),X.statsHtml('p'),X.statsHtml('l'),X.ownHtml(),JSON.stringify(X.statRows()),X.critParts().length];
      for(let i=0;i<5;i++){X.diffHtml();X.statsHtml('l');X.ownHtml();X.statRows();}
      const z=snap();Math.random=orig;
      return {same:a===z,len:a.length,calls,okLen:outs[0].length>50&&outs[1].length>500&&outs[3].length>500,err:a.startsWith('ERR')?a:null}}""")
    check('[사] 표시 함수(난이도 줄·표·보유 목록)는 판 상태(S·풀 %d자)를 하나도 바꾸지 않고 난수(Math.random)를 한 번도 안 쓴다(호출 %d번)' % (r['len'], r['calls']), r['same'] and r['calls'] == 0 and r['okLen'] and not r['err'], r)
    check('[사] 순수성 시험 오류 0', not errs, errs)
    await ctx.close()
    # 기준 빌드로 저장한 일시정지 저장본 → 새 빌드에서 복구(옛 저장본이 폐기되지 않는다)
    ctx, pg, errs = await new_page(b, srv.port, page=OLD)
    await pg.evaluate("()=>{const x=__p6x;x.CH_set('brj');x.start();__adv(40,{god:true});__X.pauseGame();}")
    blob = await pg.evaluate("()=>localStorage.getItem('p6_resume_v1')")
    await ctx.close()
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    await pg.evaluate("(b)=>localStorage.setItem('p6_resume_v1',b)", blob)
    await pg.reload(); await pg.wait_for_function('window.__X!==undefined')
    ok = await pg.evaluate("()=>__X.RES.restore()")
    r = await pg.evaluate("()=>({st:__p6x.state,diff:document.getElementById('pDiff')&&document.getElementById('pDiff').innerText,stt:!!document.getElementById('sttp'),first:document.getElementById('pTop').firstElementChild.className})")
    check('[사] 옛 빌드 저장본 → 새 빌드 복구(폐기 안 됨) · 일시정지 화면에 난이도·표가 보인다 %s' % r, ok is True and r['st'] == 'pause' and r['diff'] == '🎮 난이도: 일반' and r['stt'], (ok, r))
    check('[사] 복구 오류 0', not errs, errs)
    await ctx.close()

# ── 아 · 통합 검수 보완 (2026-10-10) ───────────────────────────
async def sec_review(b, srv):
    # (1) 난이도 줄은 일시정지 제목 바로 아래 · 낮은 가로 창(640x300)에서도 「계속하기」 고정 버튼에 안 가려진다
    for (w, h) in ((640, 300), (360, 640)):
        ctx, pg, errs = await new_page(b, srv.port, w=w, h=h, page=NEW, mobile=True)
        await pg.evaluate(RICH, dict(RICH_CASES['full'], ch='jjg'))
        await pg.evaluate("()=>{__p6x.S.hard=true;__X.UI3.pOpen=true;__X.pauseGame();}")
        r = await pg.evaluate("""()=>{const R=id=>document.getElementById(id).getBoundingClientRect(),h2=document.querySelector('#pause h2').getBoundingClientRect(),d=R('pDiff'),m=R('pMul'),s=document.querySelector('#pause .snd').getBoundingClientRect(),btn=R('resumeBtn');
          return {afterH2:d.top>=h2.bottom-1&&d.top-h2.bottom<30,aboveSettings:m.bottom<=s.top+1,clear:m.bottom<=btn.top+1,dTop:d.top,mBot:m.bottom,bTop:btn.top}}""")
        check('[아] %dx%d 일시정지 — 난이도 줄·배율 줄이 제목 바로 아래(소리 설정 위)이고 계속하기 버튼에 안 가려진다 %s' % (w, h, r), r['afterH2'] and r['aboveSettings'] and r['clear'], r)
        check('[아] %dx%d 오류 0' % (w, h), not errs, errs)
        await ctx.close()
    # (2) 오늘의 도전 줄 배경은 전역 .dly(!important 그라데이션)에 안 먹힌다
    ctx, pg, errs = await new_page(b, srv.port, w=360, h=640, page=NEW, mobile=True)
    await pg.evaluate("()=>{const x=__p6x;x.CH_set('brj');x.start({daily:true});__X.pauseGame();}")
    r = await pg.evaluate("()=>{const d=document.getElementById('pDiff'),c=getComputedStyle(d);return {bg:c.backgroundImage,col:c.backgroundColor,cls:d.className}}")
    check('[아] 오늘의 도전 난이도 줄은 그라데이션(전역 .dly) 없이 의도한 배경색 %s' % r, r['bg'] == 'none' and r['col'] == 'rgb(16, 48, 59)', r)
    await ctx.close()
    # (3) 레벨업: 능력치 접이식 줄이 보유 명단 위 · 연달아 열리는 레벨업은 맨 위에서 시작
    ctx, pg, errs = await new_page(b, srv.port, w=360, h=640, page=NEW, mobile=True)
    await pg.evaluate(RICH, RICH_CASES['full'])
    r = await pg.evaluate("""()=>{__p6x.state='lvup';__X.openLvup();const bx=document.querySelector('#lvup .box'),st=document.getElementById('sttl'),ow=document.querySelector('#lvOwn .own');
      const before=st.compareDocumentPosition(ow)&4;bx.scrollTop=800;__X.openLvup();return {before:!!before,top:bx.scrollTop}}""")
    check('[아] 레벨업 — 「내 능력치」 줄이 보유 명단 위에 있고, 다시 열리면 스크롤이 맨 위로 돌아온다 %s' % r, r['before'] and r['top'] == 0, r)
    await ctx.close()
    # (4) 받는 피해 줄: 모든 줄이는 효과가 없으면 「—」
    ctx, pg, errs = await new_page(b, srv.port, page=NEW)
    r = await pg.evaluate("()=>{__p6x.CH_set('brj');__p6x.start();const t=__X.statRows().find(r=>r.k==='taken');return {t:t.t,s:t.s}}")
    check('[아] 빈 몸의 받는 피해 줄은 「—」· 「아직 줄여 주는 효과가 없어요」 %s' % r, r['t'] == '—' and r['s'] == '아직 줄여 주는 효과가 없어요', r)
    await ctx.close()

async def main():
    prep(); srv = H.Srv()
    try:
        async with async_playwright() as p:
            b = await H.launch(p)
            for sec, fn in [('가', sec_diff), ('나', sec_values), ('다', sec_behavior), ('라', sec_own), ('마', sec_fold), ('바', sec_layout), ('사', sec_invariant), ('아', sec_review)]:
                if want(sec):
                    print('── %s ──' % sec, flush=True)
                    try: await fn(b, srv)
                    except Exception as e: check('[%s] 구획이 끝까지 돌지 못했다(예외·시간 초과)' % sec, False, repr(e))
            await b.close()
    finally:
        srv.close()
        if ONLY is None or '--keep' not in sys.argv: cleanup()
    print('\n' + ('전부 통과' if not FAILS else '실패 %d건: %s' % (len(FAILS), FAILS)))
    return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
