# -*- coding: utf-8 -*-
"""📖 흐접새우 서바이벌 「스킬 도감」 시험 — 첫 화면 버튼 · 겹창 · 발견 기록 · 저장 · 서버 동기화 · 게임 규칙 불변.
   [2026-10-09 사장님 지시] "게임내 존재하는 모든 스킬들에 대한 도감을 게임시작전 메인화면에 추가해주고, 그 도감열람은 스킬을 한번씩 인게임에서 골라본것만 열람가능하게 추가"
   사용: python3 tests/survivors_codex_test.py            (스크린샷: CDX_SHOTS=<폴더> · 정책 봇 비교 건너뛰기: CDX_NOSIM=1)
   임시 사본 survivors_cxdex.html · survivors_cxbase.html 은 .gitignore(survivors_cx*) 대상 — 시험이 끝나면 지운다. 같은 워크트리에서 survivors_x.html 을 쓰는 다른 시험과 동시에 돌려도 안 겹친다.
   섹션: ① 완전성 불변식 ② 발견 규칙 ③ 화면 ④ 저장 ⑤ 서버 동기화 ⑥ 규칙 불변(정책 봇) ⑦ 이어하기 서명 ⑧ 레이아웃 ⑨ 키보드 ⑩ 오류"""
import asyncio, sys, os, json, re, subprocess, shutil, glob, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
import survivors_charbal_sim as SIM
from playwright.async_api import async_playwright

FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:600]) if (not cond and extra != '') else ''), flush=True)
    if not cond: FAILS.append(name)

SHOTS = os.environ.get('CDX_SHOTS')
PAGE = 'survivors_cxdex.html'
BASE_PAGE = 'survivors_cxbase.html'
BASE_COMMIT = os.environ.get('CDX_BASE_COMMIT', '4ed2f37')   # 이 기능을 넣기 직전의 main(규칙 불변 증명용) — 2026-10-10 합칠 때 bfaaf08 → 4ed2f37(그 사이 최종 보스가 이어하기 서명을 바꿨다). SIG 가 또 바뀌는 커밋이 들어오면 직전 main 으로 다시 잡는다
KEYRE = re.compile(r'^[a-z]{1,3}:[a-z0-9_]{1,24}$')
LOGIN = "localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))"
SIZES = [(320, 568, True), (360, 640, True), (390, 844, True), (412, 915, True), (640, 360, True), (844, 390, True), (1280, 800, False)]

# 시험 사본에만 꽂는 훅 — 도감 내부(CDX·cdx*)와 표(PASS·PT·TRD·SM·CO)를 꺼내 본다(게임 로직은 안 바꾼다)
EXTRA = r"""
window.__cx={CDX,cdxEntries,cdxView,cdxStat,cdxKeys,cdxKeyOf,cdxNote,cdxMerge,cdxAttach,cdxAdd,cdxRead,cdxSave,PASS,PT,TRD,SM,CO,TIERS,REL,SYN,WEAP,CHARS,
 openLvup,evReady,evolve,RES,makeS,pmax,MAXLV,MAXEV,MAXPASS,REV_LV,SLOTW,SLOTP,synCalc,tkCalc,smn,trn,cardOf};
"""
BASE_EXTRA = r"""
window.__cx={PASS,PT,TRD,SM,CO,TIERS,REL,SYN,WEAP,CHARS,RES,makeS};
"""

async def mk(b, port, w=390, h=844, mobile=True, init=None, mock=None, page=PAGE, ready='window.__cx!==undefined&&window.__cdx!==undefined&&window.__cxui!==undefined'):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    errs = []
    async def route(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:%d/' % port): await r.continue_(); return
        if mock and 'bot-hosting.cloud' in u: await mock(r); return
        await r.abort()
    await ctx.route('**/*', route)
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
    await pg.goto('http://127.0.0.1:%d/%s' % (port, page))
    await pg.wait_for_function(ready, timeout=20000)
    return ctx, pg, errs

def seed_init(keys, once=True):
    """첫 방문에만 도감 저장값을 심는다(새로고침하면 그대로 두고 그 뒤 값이 이어진다)."""
    body = "if(!sessionStorage.getItem('__seeded')){localStorage.setItem('p6_codex_v1',%s);sessionStorage.setItem('__seeded','1');}" % json.dumps(json.dumps({'v': 1, 'k': sorted(keys)}))
    return "try{" + body + "}catch(e){}"

async def shot(pg, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True); await pg.screenshot(path=os.path.join(SHOTS, name))

def flat(o, out=None):
    """항목 안의 모든 글자 조각(이름·설명·단계 문구)을 모은다 — 키(key)·아이콘 같은 식별자는 뺀다."""
    out = [] if out is None else out
    if isinstance(o, str): out.append(o)
    elif isinstance(o, list):
        for x in o: flat(x, out)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in ('key', 'cat', 'sub', 'k', 'e', 'ic'): continue
            flat(v, out)
    return out

DOC_TEXT = r"""()=>{const o=[document.body.textContent];for(const el of document.querySelectorAll('*'))for(const a of el.attributes)o.push(a.value);o.push(document.title);return o.join('\n');}"""
DOM_TEXT = r"""()=>{const o=[];for(const r of [document.getElementById('cxOv'),document.getElementById('cxOpen')]){if(!r)continue;o.push(r.textContent);
  for(const el of [r,...r.querySelectorAll('*')])for(const a of el.attributes)o.push(a.value);}return o.join('\n');}"""

async def swipe(cdp, pg, x, y0, y1, steps=16):
    """진짜 손가락 쓸기(터치 이벤트 순서 touchStart → touchMove… → touchEnd) — Input.synthesizeScrollGesture 는 이 환경에서 일반 페이지도 못 굴려서 쓰지 않는다."""
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y0}]})
    for i in range(1, steps + 1):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y0 + (y1 - y0) * i / steps}]})
        await pg.wait_for_timeout(16)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    await pg.wait_for_timeout(450)

async def stat(pg): return await pg.evaluate("__cdx.stat()")
async def opened(pg): return await pg.evaluate("document.getElementById('cxOv').classList.contains('on')")
async def open_dex(pg):
    await pg.click('#cxOpen'); await pg.wait_for_function("document.getElementById('cxOv').classList.contains('on')")
async def tabs(pg): return await pg.evaluate("[...document.querySelectorAll('#cxBody .cxtab')].map(t=>({t:t.dataset.t,sel:t.getAttribute('aria-selected'),c:t.querySelector('.cxtc').textContent,tab:t.getAttribute('tabindex')}))")

def make_base_copy():
    """기준 커밋(도감을 넣기 전)의 survivors.html 에 같은 검증 훅을 꽂은 사본 — 규칙 불변 비교용. git 이 없거나 커밋이 없으면 False."""
    try:
        r = subprocess.run(['git', '-C', H.ROOT, 'show', BASE_COMMIT + ':survivors.html'], capture_output=True, timeout=30)
    except Exception as e:
        print('기준 커밋 사본을 못 만듦:', e); return False
    if r.returncode != 0 or len(r.stdout) < 100000: return False
    tmp = os.path.join(H.ROOT, 'survivors_cxbase_src.html')
    open(tmp, 'wb').write(r.stdout)
    try: H.make_copy(src='survivors_cxbase_src.html', dst=BASE_PAGE, extra=BASE_EXTRA)
    finally: os.remove(tmp)
    return True

async def main():
    H.make_copy(dst=PAGE, extra=EXTRA)
    srv = H.Srv()
    base_ok = make_base_copy()
    async with async_playwright() as p:
        b = await H.launch(p)

        # ═════════════ ① 완전성 불변식 ═════════════
        print('\n── ① 완전성 불변식 — 표의 모든 스킬이 도감에 있고 도감에는 표에 없는 것이 없다 · 카드 종류마다 발견 키가 있다 ──', flush=True)
        ctx, pg, errs = await mk(b, srv.port)
        tb = await pg.evaluate("""()=>{const x=__cx;return {W:Object.keys(x.WEAP),P:Object.keys(x.PASS),T:Object.keys(x.TIERS),PT:Object.keys(x.PT),R:Object.keys(x.REL),D:Object.keys(x.TRD),M:Object.keys(x.SM),C:Object.keys(x.CO),Y:x.SYN.map(y=>y.k),
          ev:Object.keys(x.WEAP).filter(k=>x.WEAP[k].ev),only:Object.keys(x.WEAP).filter(k=>x.WEAP[k].only).map(k=>[k,x.WEAP[k].only]),chars:x.CHARS.map(c=>[c.k,c.w])}}""")
        ent = await pg.evaluate("__cx.cdxEntries()")
        want_tiles = ['w:' + k for k in tb['W']] + ['p:' + k for k in tb['P']] + ['rl:' + k for k in tb['R']] + ['tr:' + k for k in tb['D']] + ['sm:' + k for k in tb['M']] + ['co:' + k for k in tb['C']] + ['sy:' + k for k in tb['Y']]
        got_tiles = [e['key'] for e in ent]
        check('도감 칸 = 표의 모든 키(무기 %d · 패시브 %d · 유물 %d · 거래 %d · 작은 능력치 %d · 일회용 %d · 시너지 %d)' % (len(tb['W']), len(tb['P']), len(tb['R']), len(tb['D']), len(tb['M']), len(tb['C']), len(tb['Y'])), sorted(got_tiles) == sorted(want_tiles), (set(want_tiles) ^ set(got_tiles)))
        check('도감 칸 키가 서로 겹치지 않는다 · 총 %d칸' % len(got_tiles), len(set(got_tiles)) == len(got_tiles) == len(want_tiles))
        check('무기 40종(공용 22 + 고유 18) · 패시브 17 · 유물 22 · 거래 6 · 작은 능력치 6 · 일회용 4', (len(tb['W']), len(tb['P']), len(tb['R']), len(tb['D']), len(tb['M']), len(tb['C'])) == (40, 17, 22, 6, 6, 4) and len([1 for k, o in tb['only']]) == 18, (len(tb['W']), len(tb['only'])))
        check('PT(초월) 키는 모두 패시브 칸 안에 들어 있다', all(any(e['key'] == 'p:' + k and e['pt'] and e['pt']['key'] == 'pt:' + k and len(e['pt']['lv']) >= 1 for e in ent) for k in tb['PT']) and set(tb['PT']) <= set(tb['P']))
        check('TIERS(마스터·각성 단계) 키는 모두 무기 칸 안에 들어 있다 · 무기 40종 모두 단계표가 있다', all(any(e['key'] == 'w:' + k and e['ms'] and e['ms']['key'] == 'wt:' + k and len(e['ms']['m']) == 3 and len(e['ms']['e']) == 2 for e in ent) for k in tb['T']) and set(tb['T']) == set(tb['W']), set(tb['W']) - set(tb['T']))
        check('각성 형태(ev)는 무기마다 있다', all(any(e['key'] == 'w:' + k and e['ev'] and e['ev']['key'] == 'ev:' + k and e['ev']['nm'] and e['ev']['ds'] for e in ent) for k in tb['ev']) and set(tb['ev']) == set(tb['W']))
        keys = await pg.evaluate("(()=>{const K=__cx.cdxKeys();return {t:K.t,sub:K.sub,all:[...K.all]}})()")
        check('유효 키 목록에 칸 %d + 세부(wt·pt·ev) %d 개' % (len(keys['t']), len(keys['sub'])), len(keys['t']) == 127 and len(keys['sub']) == 40 + 10 + 40, (len(keys['t']), len(keys['sub'])))
        check('모든 키가 서버 계약 정규식 ^[a-z]{1,3}:[a-z0-9_]{1,24}$ 를 지킨다(서버가 거절하지 않게)', all(KEYRE.match(k) for k in keys['all']), [k for k in keys['all'] if not KEYRE.match(k)])
        check('키가 400개 상한 안(%d개)' % len(keys['all']), len(keys['all']) <= 400)
        check('모든 칸에 이름과 아이콘이 있다', all(e['nm'] and e['ic'] for e in ent), [e['key'] for e in ent if not (e['nm'] and e['ic'])])
        wl = [e for e in ent if e['cat'] == 'w']
        check('무기 칸마다 8단계 설명 · 짝 패시브 · 각성 형태 · 마스터 3 + 각성 2단계', all(len(e['lv']) == 8 and e['pair'] and e['ev'] and len(e['ms']['m']) == 3 and len(e['ms']['e']) == 2 for e in wl))
        ow = {k: o for k, o in tb['only']}
        uq = [e for e in wl if e['who']]
        check('고유 무기 18종은 모두 전용 캐릭터가 붙는다(WEAP.only === 캐릭터 키)', len(uq) == 18 and all(e['who']['k'] == ow[e['key'][2:]] for e in uq) and all(e['who']['nm'] for e in uq), [e['key'] for e in wl if (e['key'][2:] in ow) != bool(e['who'])])
        check('공용 무기 22종은 전용 표기가 없다', len([e for e in wl if not e['who']]) == 22)
        ch_w = {c: w for c, w in tb['chars']}
        check('고유 무기의 주인 캐릭터는 그 무기를 시작 무기로 쓴다(시작 = 고른 것)', all(ch_w.get(ow[k]) == k for k in ow), [(k, ow[k]) for k in ow if ch_w.get(ow[k]) != k])
        check('시작 무기가 고유 무기인 캐릭터는 시작 레벨 값을 갖는다', all(e['startLv'] >= 1 for e in uq) and all(e['startLv'] == 0 for e in wl if not e['who']))
        pl = [e for e in ent if e['cat'] == 'p']
        check('패시브 칸: 최대 Lv · 짝 무기 목록(부활 외 모두 1개 이상)', all(e['max'] >= 1 for e in pl) and all(len(e['pairs']) >= 1 for e in pl if e['key'] != 'p:rev') and len([e for e in pl if e['pt']]) == 10)
        check('유물 칸: Lv1~3 문구 3개 · 시그니처 15종은 전용 캐릭터', all(len(e['lv']) == 3 and all(e['lv']) for e in ent if e['cat'] == 'r') and len([e for e in ent if e['cat'] == 'r' and e['who']]) == 15)
        check('시너지 칸: 필요한 무기가 모두 실제 무기', all(e['req'] and all(('w:' + w['key'][2:]) in got_tiles for w in e['req']) for e in ent if e['cat'] == 's'))
        # 표 문구 속 HTML 조각 — 있으면 esc 규칙을 다시 정해야 한다
        allstr = [s for e in ent for s in flat(e)]
        check('표 문구에 < > & 가 없다(도감은 모두 esc() 해서 글자로 보여 준다)', not [s for s in allstr if re.search(r'[<>&]', s)], [s for s in allstr if re.search(r'[<>&]', s)][:3])

        # offers() 가 낼 수 있는 모든 카드 → 발견 키
        sweep_js = """async ([n,inject])=>{
          const x=__p6x,c=__cx,K=c.cdxKeys();c.RES.quiet=true;for(const ch of c.CHARS)if(ch.shop)x.SRVUNL.add(ch.k);const R=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
          const rnd=R(12345),pick=a=>a[Math.floor(rnd()*a.length)],mr=Math.random;Math.random=R(777);
          const types={},bad=[],seen=new Set(),W=Object.keys(c.WEAP),P=Object.keys(c.PASS);let cards=0;
          const off0=x.offers;
          try{
          for(let i=0;i<n;i++){
            if(i%250===0){const ch=c.CHARS[(i/250|0)%c.CHARS.length];x.CH_set(ch.k);x.start();}
            const S=x.S;S.lv=pick([1,5,12,20,23,24,30,31,45,70]);S.pendingLv=0;
            S.w={[x.CH.w]:2};S.ps={};S.ev={};S.tier={};S.pt={};S.rel={};S.tr={};S.sm={};S.ramen=0;S.banned=[];
            for(let j=0,m=Math.floor(rnd()*6);j<m;j++){const k=pick(W);if(c.WEAP[k].only&&c.WEAP[k].only!==x.CH.k&&rnd()<.7)continue;S.w[k]=1+Math.floor(rnd()*8);}
            for(let j=0,m=Math.floor(rnd()*6);j<m;j++){const k=pick(P);S.ps[k]=1+Math.floor(rnd()*c.pmax(k));}
            for(const k in S.w)if(S.w[k]>=8){if(rnd()<.4)S.ev[k]=1;if(rnd()<.6)S.tier[k]=Math.floor(rnd()*(S.ev[k]?5:3));}
            for(const k in S.ps)if(S.ps[k]>=c.pmax(k)&&c.PT[k]&&rnd()<.6)S.pt[k]=Math.floor(rnd()*c.PT[k].length);
            for(const k in c.REL)if(rnd()<.3)S.rel[k]=1+Math.floor(rnd()*3);
            for(const k in c.TRD)if(rnd()<.3)S.tr[k]=1+Math.floor(rnd()*(c.TRD[k].cap||3));
            for(const k in c.SM)if(rnd()<.3){if(k==='ramen')S.ramen=Math.floor(rnd()*c.SM.ramen.cap);else S.sm[k]=Math.floor(rnd()*c.SM[k].cap);}
            let cs=x.offers(3).concat(x.offers(1));
            if(inject&&i%97===0)cs=cs.concat([{t:'zz',k:'zz:nope',r:'nope'}]);
            for(const o of cs){cards++;types[o.t]=(types[o.t]||0)+1;const k=c.cdxKeyOf(o);
              if(o.t==='heal'){if(k!==null)bad.push(['heal 은 키가 없어야 한다',o.t,k]);continue;}
              if(!k||!K.all.has(k)){bad.push([o.t,o.k,k]);continue;}
              if(!K.tile.has(k)&&!K.all.has(k))bad.push([o.t,o.k,k]);seen.add(k);}
          }}finally{Math.random=mr;}
          return {cards,types,bad:bad.slice(0,8),nbad:bad.length,seen:[...seen]};}"""
        sw = await pg.evaluate(sweep_js, [4000, False])
        check('offers() 4000번(약 %d장) — 모든 카드가 발견 키로 바뀐다(키 없는 카드 0 · 치킨만 키 없음)' % sw['cards'], sw['nbad'] == 0 and sw['cards'] > 10000, sw['bad'])
        check('나온 카드 종류 = w p wt pt rl tr sm co heal 전부', set(sw['types']) == {'w', 'p', 'wt', 'pt', 'rl', 'tr', 'sm', 'co', 'heal'}, sw['types'])
        tile_seen = [k for k in sw['seen'] if k in set(keys['t'])]
        check('나온 카드로 닿은 칸 %d/127 — 무기·패시브·유물·거래·능력치·일회용 전 범주에 걸친다' % len(tile_seen), len(tile_seen) >= 80 and {k.split(':')[0] for k in tile_seen} >= {'w', 'p', 'rl', 'tr', 'sm', 'co'}, sorted({k.split(':')[0] for k in tile_seen}))
        sw2 = await pg.evaluate(sweep_js, [600, True])
        check('[자체 점검] 도감에 없는 새 카드 종류가 offers() 에 생기면 이 시험이 실패한다', sw2['nbad'] > 0 and any(x[0] == 'zz' for x in sw2['bad']), sw2['bad'])
        # 표가 늘면 도감이 저절로 늘어난다 — 표를 읽어 만든다는 증거
        r = await pg.evaluate("""()=>{const c=__cx;const m0=c.cdxStat().m;
          c.WEAP.zzz=Object.assign({},c.WEAP.feed,{nm:'가짜무기',ds:c.WEAP.feed.ds.slice()});c.TIERS.zzz=c.TIERS.feed;c.PASS.zzp={ic:'🧪',nm:'가짜패시브',ds:'가짜 설명'};c.TRD.zzt={ic:'🧪',nm:'가짜거래',ds:'가짜'};c.CO.zzc={ic:'🧪',nm:'가짜일회용',ds:'가짜'};
          c.CDX.kk=null;c.CDX.cat=null;const m1=c.cdxStat().m,keys=c.cdxEntries().map(e=>e.key);
          const r={m0,m1,has:['w:zzz','p:zzp','tr:zzt','co:zzc'].every(k=>keys.includes(k)),sub:c.cdxKeys().all.has('wt:zzz')&&c.cdxKeys().all.has('ev:zzz')};
          delete c.WEAP.zzz;delete c.TIERS.zzz;delete c.PASS.zzp;delete c.TRD.zzt;delete c.CO.zzc;c.CDX.kk=null;c.CDX.cat=null;r.back=c.cdxStat().m;return r;}""")
        check('[자체 점검] 표에 스킬을 더하면 도감 칸 수가 따라 늘어난다(127 → 131 → 되돌리면 127)', r['m0'] == 127 and r['m1'] == 131 and r['has'] and r['sub'] and r['back'] == 127, r)
        r = await pg.evaluate("""()=>{const c=__cx;const o={};c.WEAP.feed.ds[0]='시험용 첫 문구';const w0=c.PASS.spd.ds;c.PASS.spd.ds='시험용 패시브 문구';c.SM.ramen.base=.05;c.CDX.cat=null;
          for(const k of ['w:feed','p:spd','sm:ramen'])c.cdxNote(k);
          const v=c.cdxView();o.w=v.find(e=>e.key==='w:feed').lv[0];o.p=v.find(e=>e.key==='p:spd').ds;o.s=v.find(e=>e.key==='sm:ramen').first;
          c.WEAP.feed.ds[0]='가장 가까운 적에게 사료를 던진다';c.PASS.spd.ds=w0;c.SM.ramen.base=.03;c.CDX.cat=null;return o;}""")
        check('[자체 점검] 설명·숫자를 표에서 읽는다(표를 바꾸면 도감 문구와 숫자가 바뀐다)', r == {'w': '시험용 첫 문구', 'p': '시험용 패시브 문구', 's': '5%'}, r)
        check('[① 오류 없음]', not errs, errs)
        await ctx.close()

        # ═════════════ ② 발견 규칙 ═════════════
        print('\n── ② 발견 규칙 — 고른 카드만 · 정확한 키 · 같은 키는 한 번 · 치킨은 무시 · 각성(ev) · 시작 무기(w) · 시너지(sy) ──', flush=True)
        ctx, pg, errs = await mk(b, srv.port)
        await pg.evaluate("""()=>{window.__sets=0;const o=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='p6_codex_v1')window.__sets++;return o.apply(this,arguments);};
          window.__rc=0;const mr=Math.random;Math.random=function(){window.__rc++;return mr.apply(this,arguments);};
          __p6x.start();window.__ks=()=>[...__cx.CDX.s].sort();window.__reset=()=>{const c=__cx;c.CDX.s.clear();c.CDX.x.clear();localStorage.removeItem('p6_codex_v1');};}""")
        r = await pg.evaluate("window.__ks()")
        check('시작하면 시작 무기(브장신 🪶 엄 깃털 산탄)만 도감에 실린다', r == ['w:quill'], r)
        cases = [('w', {'t': 'w', 'k': 'pan', 'l': 0}, 'w:pan'), ('p', {'t': 'p', 'k': 'spd', 'l': 0}, 'p:spd'), ('wt', {'t': 'wt', 'k': 'wt:feed', 'w': 'feed', 'l': 0}, 'wt:feed'),
                 ('pt', {'t': 'pt', 'k': 'pt:spd', 'p': 'spd', 'l': 0}, 'pt:spd'), ('rl', {'t': 'rl', 'k': 'rl:tenth', 'r': 'tenth', 'l': 0}, 'rl:tenth'),
                 ('tr', {'t': 'tr', 'k': 'tr:glassc', 'r': 'glassc', 'l': 0}, 'tr:glassc'), ('sm', {'t': 'sm', 'k': 'sm:crit', 'r': 'crit', 'l': 0}, 'sm:crit'),
                 ('sm(라면)', {'t': 'sm', 'k': 'sm:ramen', 'r': 'ramen', 'l': 0}, 'sm:ramen'), ('co', {'t': 'co', 'k': 'co:dice', 'r': 'dice'}, 'co:dice'),
                 ('co(펄스)', {'t': 'co', 'k': 'co:pulse', 'r': 'pulse'}, 'co:pulse'), ('p(부활)', {'t': 'p', 'k': 'rev', 'l': 0}, 'p:rev'), ('rl(시그니처)', {'t': 'rl', 'k': 'rl:sg_yj', 'r': 'sg_yj', 'l': 0}, 'rl:sg_yj')]
        for nm, card, key in cases:
            before = await pg.evaluate("window.__ks()")
            await pg.evaluate("c=>__p6x.applyUp(c)", card)
            after = await pg.evaluate("window.__ks()")
            check('[%s] applyUp → 새 키 %s 하나만' % (nm, key), sorted(set(after) - set(before)) == [key] and len(after) == len(before) + 1, (key, set(after) - set(before)))
        n0 = await pg.evaluate("[window.__ks().length,window.__sets]")
        for nm, card, key in cases: await pg.evaluate("c=>__p6x.applyUp(c)", card)
        n1 = await pg.evaluate("[window.__ks().length,window.__sets]")
        check('같은 카드를 다시 골라도 키는 늘지 않고 저장소를 건드리지도 않는다(setItem 0번)', n1 == n0, (n0, n1))
        before = await pg.evaluate("window.__ks()")
        await pg.evaluate("__p6x.applyUp({t:'heal',k:'heal'})")
        check('치킨(heal)은 도감에 안 실린다', await pg.evaluate("window.__ks()") == before)
        await pg.evaluate("__p6x.applyUp({t:'zz',k:'zz:x',r:'x'});__p6x.applyUp(null&&0||{t:'w',k:'없는무기'});__p6x.applyUp({t:'w',k:'Feed'})")
        check('표에 없는 키(알 수 없는 카드·무기)는 적지 않는다', await pg.evaluate("window.__ks()") == before)
        # S 에 쓰지 않고 난수를 안 쓴다
        r = await pg.evaluate("""()=>{const x=__p6x,c=__cx;const snap=()=>JSON.stringify(x.S);const rc=window.__rc;const k0=Object.keys(x.S).join();
          const a=snap();c.CDX.s.delete('co:feast');c.cdxNote('co:feast');const b=snap();const rc2=window.__rc;
          for(let i=0;i<200000;i++)c.cdxNote('w:feed');const rc3=window.__rc;
          return {same:a===b,rcSame:rc===rc2&&rc2===rc3,k:k0===Object.keys(x.S).join()};}""")
        check('도감 기록은 S 를 건드리지 않는다(상태 문자열 그대로)', r['same'] and r['k'], r)
        check('도감 기록은 Math.random 을 한 번도 부르지 않는다(난수 흐름 그대로)', r['rcSame'], r)
        t = await pg.evaluate("""()=>{const c=__cx;const t0=performance.now();for(let i=0;i<300000;i++)c.cdxKeyOf({t:'w',k:'feed'}),c.cdxNote('w:feed');return performance.now()-t0;}""")
        check('이미 있는 키는 아주 싸다(30만 번 %.0f ms)' % t, t < 400, t)
        # 레벨업 화면 → 실제 선택
        r = await pg.evaluate("""()=>{const x=__p6x,c=__cx;x.start();const out=[];
          for(let i=0;i<12;i++){const S=x.S;S.pendingLv=1;S.lv+=1;c.openLvup();const o=x.CUR[i%3],k=c.cdxKeyOf(o),before=c.CDX.s.has(k);x.pick(o);out.push([o.t,k,before,c.CDX.s.has(k)]);if(x.state==='lvup')x.resume();}
          return out;}""")
        check('실제 레벨업 화면에서 고른 카드의 키가 기록된다(12번)', all(o[3] for o in r) and any(not o[2] for o in r), r[:4])
        # 보스 상자 — 각성 + 카드
        r = await pg.evaluate("""()=>{const x=__p6x,c=__cx;x.start();window.__reset();const S=x.S;S.w.feed=8;S.ps.amt=1;const k0=new Set(c.CDX.s);
          c.openLvup&&0;x.openChest();const nk=[...c.CDX.s].filter(k=>!k0.has(k));return {nk,ev:!!S.ev.feed,st:x.state};}""")
        check('보스 상자 — 각성(ev:feed)과 상자 카드가 함께 기록된다', 'ev:feed' in r['nk'] and r['ev'] and len(r['nk']) >= 2, r)
        # 보유한 것은 전부 도감에 있다(빌드 ⊆ 발견) — 여러 캐릭터로 길게
        r = await pg.evaluate("""()=>{const x=__p6x,c=__cx,miss=[];c.RES.quiet=true;const R=a=>()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
          const mr=Math.random;Math.random=R(99);let picks=0,chests=0;
          try{for(const ch of c.CHARS){if(ch.shop)x.SRVUNL.add(ch.k);x.CH_set(ch.k);x.start();const S=x.S;
            for(let i=0;i<90;i++){S.lv=Math.max(S.lv,i<30?5+i:30+i);S.pendingLv=1;c.openLvup();x.pick(x.CUR[i%3]);picks++;if(x.state==='lvup')x.resume();
              if(i%9===8){for(const k in S.w)if(S.w[k]<8&&i>20)S.w[k]=8;const pairk=Object.keys(S.w).map(k=>c.WEAP[k].pair);for(const p of pairk)if(!S.ps[p])S.ps[p]=1;x.openChest();chests++;if(x.state==='chest')x.resume();}}
            const own=[];for(const k in S.w)own.push('w:'+k);for(const k in S.ps)own.push('p:'+k);for(const k in S.rel)own.push('rl:'+k);for(const k in S.tr)own.push('tr:'+k);
            for(const k in S.sm)own.push('sm:'+k);if(S.ramen)own.push('sm:ramen');for(const k in S.pt)own.push('pt:'+k);for(const k in S.tier)own.push('wt:'+k);for(const k in S.ev)own.push('ev:'+k);for(const k of S.synOn)own.push('sy:'+k);
            for(const k of own)if(!c.CDX.s.has(k))miss.push(ch.k+':'+k);}}finally{Math.random=mr;}
          return {miss,picks,chests,n:c.cdxStat().n};}""")
        check('[빌드 ⊆ 도감] %d캐릭터 × 90번 선택 + 상자 %d번 — 가진 무기·패시브·유물·거래·능력치·초월·마스터·각성·시너지가 하나도 빠지지 않는다 (칸 %d/127 발견)' % (len(tb['chars']), r['chests'], r['n']), not r['miss'] and r['picks'] == 90 * len(tb['chars']), r['miss'][:5])
        check('모든 캐릭터로 시작해 보면 고유 무기가 전부 실린다(시작 무기 w:)', await pg.evaluate("""()=>{const x=__p6x,c=__cx;const miss=[];for(const ch of c.CHARS){if(ch.shop)x.SRVUNL.add(ch.k);x.CH_set(ch.k);x.start();if(!c.CDX.s.has('w:'+ch.w))miss.push(ch.k);}return miss;}""") == [])
        # 시너지 — 켜질 때
        r = await pg.evaluate("""()=>{const x=__p6x,c=__cx;window.__reset();x.CH_set('brj');x.start();const o=[];
          x.applyUp({t:'w',k:'fryer',l:0});o.push([...c.CDX.s].filter(k=>k.startsWith('sy:')));x.applyUp({t:'w',k:'egg',l:0});o.push([...c.CDX.s].filter(k=>k.startsWith('sy:')));
          x.applyUp({t:'w',k:'sushi',l:0});o.push([...c.CDX.s].filter(k=>k.startsWith('sy:')).sort());return o;}""")
        check('시너지는 조합이 완성되는 순간에만 실린다(튀김기+달걀 → 없음 · +초밥 → 주방 콤보)', r[0] == [] and r[1] == [] and r[2] == ['sy:kitchen'], r)
        # 각성 — evolve 직접
        r = await pg.evaluate("""()=>{const x=__p6x,c=__cx;window.__reset();x.start();const a=c.CDX.s.has('ev:quill');c.evolve('quill');return [a,c.CDX.s.has('ev:quill'),c.CDX.s.has('ev:feed')];}""")
        check('각성(evolve)해야만 ev: 가 실린다(다른 무기의 ev 는 그대로 없음)', r == [False, True, False], r)
        # 이어하기 복구는 새 기록을 만들지 않는다(S 는 복구 · 도감은 그대로) — 판 시작은 한 번만
        check('[② 오류 없음]', not errs, errs)
        await ctx.close()

        # ═════════════ ③ 화면 ═════════════
        print('\n── ③ 화면 — 처음엔 전부 미발견 · 발견한 칸만 열림 · 잠긴 칸 DOM 에 이름·설명 없음 · 탭 N/M · 상세 = 표 문구 · 전용 캐릭터 ──', flush=True)
        ctx, pg, errs = await mk(b, srv.port, 390, 844)
        pill = await pg.evaluate("(()=>{const e=document.getElementById('cxOpen'),r=e.getBoundingClientRect();return {t:e.textContent,w:r.width,h:r.height,al:e.getAttribute('aria-label'),pop:e.getAttribute('aria-haspopup'),cat:window.__cx.CDX.cat,body:document.getElementById('cxBody').childElementCount,txt:document.getElementById('cxN').textContent}})()")
        check('첫 화면에 「📖 스킬 도감」 버튼 + 진행 배지 0/127', '스킬 도감' in pill['t'] and pill['txt'] == '0/127' and pill['pop'] == 'dialog' and '0 / 127' in pill['al'], pill)
        check('열기 전에는 도감 칸·항목 데이터를 만들지 않는다(첫 화면 로드 비용 0)', pill['body'] == 0 and pill['cat'] is None, (pill['body'], pill['cat']))
        await open_dex(pg)
        check('열면 겹창이 뜬다(role=dialog · aria-modal · aria-labelledby)', await pg.evaluate("(()=>{const d=document.querySelector('#cxOv [role=dialog]');return d.getAttribute('aria-modal')==='true'&&document.getElementById(d.getAttribute('aria-labelledby')).textContent.includes('스킬 도감')})()"))
        prog = await pg.evaluate("document.querySelector('.cxprog').textContent")
        check('처음 상태: 진행 「0 / 127」', '0 / 127' in prog and '0%' in prog, prog)
        tabs0 = await tabs(pg)
        check('처음 상태: 탭 5개 · 무기 0/40 · 패시브 0/17 · 유물 0/22 · 기타 0/16 · 시너지 0/32', [(t['t'], t['c']) for t in tabs0] == [('w', '0/40'), ('p', '0/17'), ('r', '0/22'), ('x', '0/16'), ('s', '0/32')], tabs0)
        check('탭은 role=tablist/tab · 선택된 탭만 tabindex 0(로빙)', await pg.evaluate("(()=>{const tl=document.querySelector('[role=tablist]'),t=[...tl.querySelectorAll('[role=tab]')];return t.length===5&&t.filter(x=>x.getAttribute('aria-selected')==='true').length===1&&t.filter(x=>x.tabIndex===0).length===1&&!!document.querySelector('[role=tabpanel]')})()"))
        for t in 'wprxs':
            await pg.click('#cxTab_' + t)
            r = await pg.evaluate("({n:document.querySelectorAll('#cxPanel .cxt').length,l:document.querySelectorAll('#cxPanel .cxt.lock').length,q:[...document.querySelectorAll('#cxPanel .cxt')].every(e=>e.textContent.replace(/\\s/g,'')==='❓???')})")
            exp = {'w': 40, 'p': 17, 'r': 22, 'x': 16, 's': 32}[t]
            check('처음 상태 [%s 탭]: 칸 %d개 전부 잠김(❓ + ???)' % (t, exp), r['n'] == exp and r['l'] == exp and r['q'], r)
        names_all = [s for s in flat(ent) if re.search(r'[가-힣]', s)]   # 이름·설명 문구(숫자만인 값은 뺀다)
        blob = await pg.evaluate(DOM_TEXT)
        doc_locked = await pg.evaluate(DOC_TEXT)   # 문서 전체(첫 화면의 조작법·캐릭터 소개에 원래 있는 말까지) — 아래 일부 발견 상태에서 여기에 없던 문구가 새로 생기면 새는 것이다
        leak = sorted({s for s in names_all if len(s) >= 2 and s in blob})
        static_hit = set(leak)   # 모든 칸이 잠긴 겹창에 남는 글자는 도감이 스스로 쓰는 안내 문구뿐이다 — 거기 우연히 들어 있는 말(예: 시너지 「디스코」 ⊂ 「디스코드」)
        check('처음 상태: 겹창·버튼 어디에도(글자·aria-label·title·속성) 스킬 이름·설명이 없다 — 검사한 문구 %d개 · 안내 문구와 우연히 겹친 것 %s' % (len(set(names_all)), leak), static_hit <= {'디스코'} and ('디스코드' in blob or not static_hit), leak[:5])
        check('처음 상태: 잠긴 칸 속성에 키(w:feed 같은 식별자)가 새지 않는다', not re.search(r'\b(w|p|rl|tr|sm|co|sy):[a-z_0-9]+', blob), re.findall(r'\b(?:w|p|rl|tr|sm|co|sy):[a-z_0-9]+', blob)[:3])
        await pg.click('#cxTab_w'); await pg.locator('#cxPanel .cxt').first.click()
        t1 = await pg.evaluate("document.getElementById('cxD').textContent")
        check('잠긴 칸을 누르면 한 줄 안내만 — 「아직 못 만났어요 — 레벨업 카드나 보스 상자에서 한 번 골라 보세요」', t1.strip() == '아직 못 만났어요 — 레벨업 카드나 보스 상자에서 한 번 골라 보세요', t1)
        await pg.click('#cxTab_s'); await pg.locator('#cxPanel .cxt').first.click()
        t2 = await pg.evaluate("document.getElementById('cxD').textContent")
        check('시너지 잠긴 칸은 조합 안내 한 줄', t2.strip().startswith('아직 못 만났어요 — ') and '조합' in t2 and len(t2) < 60, t2)
        await shot(pg, '3_all_locked_390x844.png')
        await ctx.close()

        # 일부 발견 — 교차 참조(짝 패시브·짝 무기·시너지 재료) 가림까지
        D1 = ['w:feed', 'w:egg', 'w:breath', 'ev:breath', 'wt:breath', 'wt:feed', 'w:sing', 'w:eom', 'p:cd', 'p:mag', 'pt:mag', 'p:spd', 'rl:tenth', 'rl:sg_yj', 'tr:glassc', 'sm:ramen', 'sm:hp', 'co:feast', 'sy:dragon', 'w:fryer', 'sy:kitchen', 'w:sushi', 'w:quill', 'p:amt']
        D1 = [k for k in D1 if k != 'p:amt']   # 곱빼기(사료 투척의 짝)는 일부러 못 만난 것으로 둔다
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init=seed_init(D1))
        st = await stat(pg)
        tile_d = [k for k in D1 if k in set(keys['t'])]
        by = {}
        for k in tile_d: by[{'w': 'w', 'p': 'p', 'rl': 'r', 'tr': 'x', 'sm': 'x', 'co': 'x', 'sy': 's'}[k.split(':')[0]]] = by.get({'w': 'w', 'p': 'p', 'rl': 'r', 'tr': 'x', 'sm': 'x', 'co': 'x', 'sy': 's'}[k.split(':')[0]], 0) + 1
        check('저장된 발견으로 시작: 진행 %d/127 · 배지 같은 숫자' % len(tile_d), st['n'] == len(tile_d) and await pg.evaluate("document.getElementById('cxN').textContent") == '%d/127' % len(tile_d), st)
        await open_dex(pg)
        tabs1 = await tabs(pg)
        exp_tabs = [('w', '%d/40' % by.get('w', 0)), ('p', '%d/17' % by.get('p', 0)), ('r', '%d/22' % by.get('r', 0)), ('x', '%d/16' % by.get('x', 0)), ('s', '%d/32' % by.get('s', 0))]
        check('탭별 발견 N/M 이 정확하다 %s' % exp_tabs, [(t['t'], t['c']) for t in tabs1] == exp_tabs, tabs1)
        check('진행 줄·막대 숫자가 칸 수와 같다', await pg.evaluate("(()=>{const p=document.querySelector('.cxprog b').textContent,b=document.querySelector('.cxbar');return p==='%d / 127'&&b.getAttribute('aria-valuenow')==='%d'&&b.getAttribute('aria-valuemax')==='127'})()" % (len(tile_d), len(tile_d))))
        idx = {e['key']: e for e in ent}
        for t, cat in zip('wprxs', 'wprxs'):
            await pg.click('#cxTab_' + t)
            r = await pg.evaluate("""()=>[...document.querySelectorAll('#cxPanel .cxt')].map(e=>[e.classList.contains('lock'),e.getAttribute('aria-label'),e.textContent.trim()])""")
            keys_t = [e['key'] for e in ent if e['cat'] == cat]
            opens = [i for i, k in enumerate(keys_t) if k in D1]
            check('[%s 탭] 열린 칸은 정확히 발견한 것만(%d칸) — 순서는 표 순서 그대로' % (t, len(opens)), [i for i, x in enumerate(r) if not x[0]] == opens and len(r) == len(keys_t), ([i for i, x in enumerate(r) if not x[0]], opens))
            check('[%s 탭] 열린 칸에는 이름이, 잠긴 칸에는 ??? 만 보인다' % t, all((idx[keys_t[i]]['nm'] in r[i][2]) if not r[i][0] else r[i][2].replace(' ', '').replace('\n', '') == '❓???' for i in range(len(r))))
        # 잠긴 곳 전부 점검: 모든 칸을 하나씩 눌러 보며 DOM 에 새는 것이 없는지
        vis_idx = {}
        def visible_strings(e, D):
            D = set(D); out = []
            if e['key'] not in D: return out
            out += [e['nm']]
            c = e['cat']
            if c == 'w':
                out += e['lv'] + ([e['rl']] if e['rl'] else [])
                if e['who']: out += [e['who']['nm']]
                if e['pair'] and e['pair']['key'] in D: out += [e['pair']['nm']]
                if e['ev'] and e['ev']['key'] in D: out += [e['ev']['nm'], e['ev']['ds']]
                if e['ms'] and e['ms']['key'] in D:
                    out += e['ms']['m']
                    if e['ev'] and e['ev']['key'] in D: out += e['ms']['e']
            elif c == 'p':
                out += [e['ds']] + [w['nm'] for w in e['pairs'] if w['key'] in D]
                if e['pt'] and e['pt']['key'] in D: out += e['pt']['lv']
            elif c == 'r':
                out += e['lv'] + ([e['who']['nm']] if e['who'] else [])
            elif c == 'x':
                out += [e.get('ds', ''), e.get('unit', ''), e.get('first', ''), e.get('total', '')]
            elif c == 's':
                out += [e['ds']] + [w['nm'] for w in e['req'] if w['key'] in D]
            return [s for s in out if s]
        shown = [s for e in ent for s in visible_strings(e, D1)]
        shown_blob = '\n'.join(shown)
        forbid = sorted({s for s in names_all if len(s) >= 2 and s not in shown_blob and s not in static_hit})
        r = await pg.evaluate("""async (forbid)=>{const out=[];const T=()=>{const o=[];for(const r of [document.getElementById('cxOv'),document.getElementById('cxOpen')]){o.push(r.textContent);for(const el of [r,...r.querySelectorAll('*')])for(const a of el.attributes)o.push(a.value);}return o.join('\\n');};
          let n=0;for(const t of ['w','p','r','x','s']){document.getElementById('cxTab_'+t).click();const tiles=[...document.querySelectorAll('#cxPanel .cxt')];
            for(let i=0;i<tiles.length;i++){const cur=[...document.querySelectorAll('#cxPanel .cxt')][i];cur.click();n++;const b=T();for(const s of forbid)if(b.includes(s))out.push([t,i,s]);
              if(out.length>5)return {out,n};cur.click();}}
          return {out,n};}""", forbid)
        check('[누출 검사] 모든 칸(127개)을 하나씩 열어 봐도 못 만난 것의 이름·설명이 DOM·속성 어디에도 없다 — 가린 문구 %d개 × 칸 %d번' % (len(forbid), r['n']), not r['out'] and r['n'] == 127, r['out'][:6])
        doc_part = await pg.evaluate(DOC_TEXT)
        forbid_doc = [x for x in forbid if x not in doc_locked]
        check('[누출 검사] 문서 전체(겹창 밖 포함 모든 글자·속성)에도 못 만난 것의 문구가 새로 생기지 않는다 — 검사한 문구 %d개' % len(forbid_doc), not [x for x in forbid_doc if x in doc_part] and len(forbid_doc) > 30, [x for x in forbid_doc if x in doc_part][:5])
        check('[누출 검사] 가린 문구에 교차 참조(짝 패시브 곱빼기·낚싯대·튀김기 오라 …)가 들어 있다(검사가 비어 있지 않다)', all(any(w in s for s in forbid) for w in ['곱빼기', '낚싯대', '병아리 대폭격']), [w for w in ['곱빼기', '낚싯대', '병아리 대폭격'] if not any(w in s for s in forbid)])
        # 발견한 칸 상세 = 표 문구
        async def detail_of(t, key):
            await pg.click('#cxTab_' + t)
            keys_t = [e['key'] for e in ent if e['cat'] == t]
            i = keys_t.index(key)
            await pg.locator('#cxPanel .cxt').nth(i).click()
            return await pg.evaluate("document.getElementById('cxD').textContent")
        d = await detail_of('w', 'w:breath')
        e = idx['w:breath']
        check('상세(드래곤 브레스·각성 형태·마스터 발견): Lv1~8 설명이 표와 같다', all(s in d for s in e['lv']), [s for s in e['lv'] if s not in d])
        check('상세: 전용 캐릭터 「용조련사 전용」 + 시작 무기 안내(Lv2로 시작)', '용조련사 전용' in d and '처음부터 들고' in d and 'Lv2로 시작' in d, d[:200])
        check('상세: 각성 형태 이름·설명(발견)', e['ev']['nm'] in d and e['ev']['ds'] in d)
        check('상세: 마스터 3단계 + 각성 단계 2개 문구(ev·wt 모두 발견)', all(s in d for s in e['ms']['m'] + e['ms']['e']), [s for s in e['ms']['m'] + e['ms']['e'] if s not in d])
        check('상세: 짝 패시브(획득 범위 p:mag 발견)가 보인다', idx['p:mag']['nm'] in d)
        tile_lbl = await pg.evaluate("[...document.querySelectorAll('#cxPanel .cxt')].map(e=>e.getAttribute('aria-label')).filter(x=>x&&x.includes('드래곤'))")
        check('고유 무기 칸에 전용 캐릭터가 보인다(칸 이름표·🐲 표식)', tile_lbl == ['드래곤 브레스 — 용조련사 전용'] and await pg.evaluate("[...document.querySelectorAll('#cxPanel .cxt .cxwho')].map(e=>e.textContent).includes('🐲')"), tile_lbl)
        d = await detail_of('w', 'w:feed')
        e = idx['w:feed']
        check('상세(사료 투척 · 마스터만 발견 · 짝 패시브 곱빼기·각성 형태 미발견): 레벨 8줄 + 마스터 3단계', all(s in d for s in e['lv'] + e['ms']['m']))
        check('상세: 못 만난 짝 패시브 이름은 안 보이고 ❓ 안내만', '곱빼기' not in d and '짝 패시브 ❓' in d, d[:300])
        check('상세: 각성 형태 미발견 — 「✨ 각성: ??? (아직 각성시켜 본 적 없어요)」 + 각성 조건 한 줄', '✨ 각성: ??? (아직 각성시켜 본 적 없어요)' in d and '각성 조건: 무기 Lv8' in d and e['ev']['nm'] not in d and e['ev']['ds'] not in d)
        check('상세: 각성 단계(4~5)는 각성을 해 봐야 열린다 · 안내만', all(s not in d for s in e['ms']['e']) and '각성시키면 4단계부터' in d)
        d = await detail_of('w', 'w:egg')
        e = idx['w:egg']
        check('상세(달걀 폭탄 · 마스터도 미발견): 마스터 줄은 ??? 안내 · 목록은 레벨 8줄뿐', '마스터 단계' in d and '아직 마스터 카드를 골라 본 적 없어요' in d and await pg.evaluate("document.querySelectorAll('#cxD li').length") == 8)
        d = await detail_of('w', 'w:quill')
        check('고유 무기가 아닌 다른 캐릭터 전용 무기 상세에는 그 캐릭터 이름이 붙는다(엄 깃털 산탄 · 브장신 전용)', '브장신 전용' in d, d[:120])
        d = await detail_of('p', 'p:mag')
        e = idx['p:mag']
        check('상세(획득 범위): 설명 · 최대 Lv · 초월 단계 문구(pt 발견) · 짝 무기 중 발견한 것만', e['ds'] in d and ('최대 Lv%d' % e['max']) in d and all(s in d for s in e['pt']['lv']) and idx['w:breath']['nm'] in d and '❓ ×2' in d and '낚싯대' not in d and '맛동산 투척' not in d, d[:300])
        d = await detail_of('p', 'p:cd')
        e = idx['p:cd']
        check('상세(공격속도): 초월 미발견 → ??? 안내 · 초월 문구는 안 보인다', '🌟 초월' in d and '아직 초월시켜 본 적 없어요' in d and all(s not in d for s in e['pt']['lv']))
        d = await detail_of('r', 'rl:sg_yj')
        e = idx['rl:sg_yj']
        check('상세(시그니처 유물 쫑의 숨결): Lv1~3 문구 + 「용조련사 전용」', all(s in d for s in e['lv']) and '용조련사 전용' in d and '시그니처' in d, d[:200])
        d = await detail_of('r', 'rl:tenth')
        check('상세(공용 유물): Lv1~3 문구', all(s in d for s in idx['rl:tenth']['lv']) and '전용' not in d)
        d = await detail_of('x', 'tr:glassc')
        check('상세(거래 카드): 설명 + 최대 횟수', idx['tr:glassc']['ds'] in d and '최대 3번' in d and '얻는 만큼 잃어요' in d, d)
        d = await detail_of('x', 'sm:ramen')
        e = idx['sm:ramen']
        check('상세(작은 능력치 라면): 첫 한 입 · 줄어드는 비율 · 최대 횟수 · 합계가 표 값에서 나온다', (e['unit'] + ' +' + e['first']) in d and str(e['cap']) in d and e['total'] in d and e['first'] == '3%', (d, e))
        d = await detail_of('x', 'sm:hp')
        e = idx['sm:hp']
        check('상세(든든한 밥 · 최대 HP): 정수 값(+12) · 합계는 게임이 실제로 올리는 값(한 번마다 반올림)', e['first'] == '12' and e['total'] == '44' and '최대 HP +12' in d, (e, d))
        d = await detail_of('x', 'co:feast')
        check('상세(일회용): 설명', idx['co:feast']['ds'] in d)
        d = await detail_of('s', 'sy:dragon')
        e = idx['sy:dragon']
        check('상세(시너지 용의 식탁): 설명 · 재료 둘(드래곤 브레스·튀김기 오라)을 모두 만났으니 이름이 보이고 전용 무기 표기도 붙는다', e['ds'] in d and 'dragon' not in d and '드래곤 브레스' in d and '튀김기 오라' in d and '용조련사 전용' in d and '❓' not in d, d)
        d = await detail_of('s', 'sy:kitchen')
        check('상세(주방 콤보): 재료 3개 모두 발견 → 이름 3개 · ❓ 없음', all(idx['w:' + w]['nm'] in d for w in ['fryer', 'egg', 'sushi']) and '❓' not in d, d)
        await shot(pg, '3_detail_synergy_390x844.png')
        # 펼침: 한 번에 하나 · 다시 누르면 접힘 · 탭을 바꾸면 접힘
        await pg.click('#cxTab_w')
        tl = pg.locator('#cxPanel .cxt')
        await tl.nth(0).click(); await tl.nth(1).click()
        r = await pg.evaluate("({d:document.querySelectorAll('#cxD').length,ex:[...document.querySelectorAll('#cxPanel .cxt')].map(e=>e.getAttribute('aria-expanded'))})")
        check('펼침은 한 번에 한 칸(aria-expanded · aria-controls)', r['d'] == 1 and r['ex'].count('true') == 1 and r['ex'][1] == 'true', r)
        await tl.nth(1).click()
        check('같은 칸을 다시 누르면 접힌다', await pg.evaluate("document.querySelectorAll('#cxD').length") == 0)
        await tl.nth(2).click(); await pg.click('#cxTab_p')
        check('탭을 바꾸면 펼침이 접힌다', await pg.evaluate("document.querySelectorAll('#cxD').length") == 0)
        check('[③ 오류 없음]', not errs, errs)
        await ctx.close()

        # 시너지는 켜졌는데 재료 무기 하나를 못 만난 꼬인 저장값에서도(손으로 고친 기록·다른 기기 합치기) 못 만난 무기 이름은 안 나온다
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init=seed_init(['sy:dragon', 'w:breath']))
        await open_dex(pg); d = await detail_of('s', 'sy:dragon')
        check('재료 무기를 못 만났다면 이름 대신 ❓ ???(튀김기 오라가 안 보인다)', '❓ ???' in d and '튀김기 오라' not in d and '드래곤 브레스' in d, d)
        check('[교차 참조] 오류 없음', not errs, errs)
        await ctx.close()

        # 전부 발견
        ctx, pg, errs = await mk(b, srv.port, 360, 640, init=seed_init(keys['all']))
        st = await stat(pg)
        check('전부 발견 상태: 127/127 · 배지', st['n'] == 127 and st['m'] == 127 and await pg.evaluate("document.getElementById('cxN').textContent") == '127/127', st)
        await open_dex(pg)
        check('전부 발견: 탭 합계가 칸 수와 같다 · 100%', [t['c'] for t in await tabs(pg)] == ['40/40', '17/17', '22/22', '16/16', '32/32'] and '100%' in await pg.evaluate("document.querySelector('.cxprog').textContent"))
        # 모든 상세가 열린다(오류 없이) · 문구가 표와 같다 — 칸 127개 전부
        r = await pg.evaluate("""async ()=>{const out=[];const E=__cx.cdxEntries();let n=0;
          for(const t of ['w','p','r','x','s']){document.getElementById('cxTab_'+t).click();const tiles=[...document.querySelectorAll('#cxPanel .cxt')];
            for(let i=0;i<tiles.length;i++){tiles[i].click();const d=document.getElementById('cxD');n++;if(!d||!d.textContent.trim()||d.querySelector('.cxlk')&&0)out.push([t,i,'빈 상세']);
              const e=E.filter(x=>x.cat===t)[i];const txt=d?d.textContent:'';
              const need=[e.nm];if(e.lv)need.push(...e.lv);if(e.ds)need.push(e.ds);if(e.ev)need.push(e.ev.nm,e.ev.ds);if(e.ms)need.push(...e.ms.m,...e.ms.e);if(e.pt)need.push(...e.pt.lv);if(e.who)need.push(e.who.nm);if(e.req)need.push(...e.req.map(w=>w.nm));if(e.pairs)need.push(...e.pairs.map(w=>w.nm));if(e.pair)need.push(e.pair.nm);
              for(const s of need)if(!txt.includes(s))out.push([e.key,s]);tiles[i].click();}}
          return {out:out.slice(0,6),n};}""")
        check('전부 발견: 127칸 상세에 이름·설명·단계·각성·초월·짝·전용 캐릭터가 모두 있다', not r['out'] and r['n'] == 127, r['out'])
        await shot(pg, '3_all_found_360x640.png')
        await ctx.close()

        # 방어 — 그리다 예외가 나도 게임은 멀쩡하고 빈 창 대신 안내가 뜬다 · 각성 형태가 없는 무기가 생겨도 상세가 깨지지 않는다 · 다시 열면 맨 위부터
        ctx, pg, errs = await mk(b, srv.port, 390, 844)
        await pg.evaluate("()=>{window.__cdx.view=()=>{throw new Error('시험용')};}")
        await pg.click('#cxOpen')
        txt = await pg.evaluate("document.getElementById('cxBody').textContent")
        check('도감을 그리다 예외가 나도 안내 한 줄이 뜨고 겹창·게임은 멀쩡하다(페이지 오류 없음)', '도감을 그리지 못했어요' in txt and await opened(pg) and await pg.evaluate("__p6x.state") == 'title' and not errs, (txt, errs))
        await pg.click('#cxX'); await pg.click('#startBtn'); await pg.wait_for_timeout(100)
        check('그리기가 고장 나도 판 시작·진행은 정상', await pg.evaluate("__p6x.state") == 'play' and (await stat(pg))['n'] >= 1)
        await ctx.close()
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init=seed_init(['w:feed', 'p:amt']))
        await pg.evaluate("()=>{__cx.WEAP.feed.ev=null;__cx.CDX.kk=null;__cx.CDX.cat=null;}")
        await open_dex(pg); await pg.locator('#cxPanel .cxt').nth(0).click()
        d = await pg.evaluate("document.getElementById('cxD').textContent")
        check('각성 형태가 없는 무기: 상세에서 각성 칸만 빠진다', '각성' not in d, d[:200])
        check('각성 형태가 없는 무기: 레벨 문구는 그대로 · 오류 없음', idx['w:feed']['lv'][0] in d and not errs, errs)
        await ctx.close()
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init=seed_init(keys['all']))
        await open_dex(pg); await pg.evaluate("document.getElementById('cxBody').scrollTop=900"); await pg.click('#cxX'); await open_dex(pg)
        check('다시 열면 맨 위부터 보인다(이전 스크롤 위치를 끌고 오지 않는다)', await pg.evaluate("document.getElementById('cxBody').scrollTop") == 0)
        await ctx.close()

        # ═════════════ ④ 저장 ═════════════
        print('\n── ④ 저장 — 유지 · 정렬된 형식 · 손상·알 수 없는 키·거대한 값 · 저장소 차단 · 두 탭 동시 ──', flush=True)
        ctx, pg, errs = await mk(b, srv.port)
        await pg.evaluate("()=>{const c=__cx;['w:egg','p:spd','co:feast','rl:tenth','w:feed'].forEach(k=>c.cdxNote(k));}")
        raw = await pg.evaluate("localStorage.getItem('p6_codex_v1')")
        j = json.loads(raw)
        check('저장 형식 {v:1,k:[…]} · 정렬됨 · 키 5개', j == {'v': 1, 'k': sorted(['w:egg', 'p:spd', 'co:feast', 'rl:tenth', 'w:feed'])}, raw)
        await pg.reload(); await pg.wait_for_function("window.__cdx!==undefined&&window.__cx!==undefined")
        check('새로고침 뒤에도 그대로(진행 5/127)', (await stat(pg))['n'] == 5)
        await ctx.close()
        # 손상·조작
        junk_cases = {
            '깨진 JSON': ('not json {{{', 0, True), '배열 아닌 k': (json.dumps({'v': 1, 'k': 'w:feed'}), 0, True), '최상위가 배열': (json.dumps(['w:feed']), 0, True), 'null': ('null', 0, True),
            '섞인 값': (json.dumps({'v': 1, 'k': [1, None, {}, [], 'w:feed', 'BAD KEY', 'zz:nope', 'w:Feed', 'w:' + 'a' * 40, ':x', 'w:', 'w:egg ', 'p:spd']}), 2, False),
            '아주 큰 배열': (json.dumps({'v': 1, 'k': ['w:feed'] + ['zz:k%d' % i for i in range(50000)]}), 0, True),
            '아주 큰 문자열': (json.dumps({'v': 1, 'k': ['w:feed'], 'x': 'y' * 3_000_000}), 0, True),
            '표에 없는 키만': (json.dumps({'v': 1, 'k': ['zz:aaa', 'qq:bbb', 'w:nothing']}), 0, False),
        }
        for nm, (val, want_n, want_bad) in junk_cases.items():
            ctx, pg, errs = await mk(b, srv.port, init="try{localStorage.setItem('p6_codex_v1',%s)}catch(e){}" % json.dumps(val))
            st = await stat(pg)
            bad = await pg.evaluate("__cdx.bad")
            await open_dex(pg)
            note = await pg.evaluate("[...document.querySelectorAll('#cxBody .cxnote')].map(e=>e.textContent)")
            ok_sz = (await pg.evaluate("document.getElementById('cxPanel').querySelectorAll('.cxt').length")) == 40
            check('[%s] 진행 %d/127 · 읽을 수 없는 값 표시(%s) · 도감이 멀쩡히 열린다 · 오류 없음' % (nm, want_n, '알림' if want_bad else '없음'), st['n'] == want_n and st['m'] == 127 and bool(bad) == want_bad and ok_sz and (bool(note) == want_bad) and not errs, (st, bad, note, errs))
            if want_bad: check('[%s] 안내 문구가 도감 첫머리에 있다' % nm, bool(note) and '읽지 못해' in note[0], note)
            # 값이 손상된 채 새 발견을 저장하면 그때 새로 쓴다
            await pg.evaluate("__cx.cdxNote('w:egg')")
            after = json.loads(await pg.evaluate("localStorage.getItem('p6_codex_v1')"))
            exp_keys = sorted(({'w:feed'} if nm == '섞인 값' else set()) | ({'p:spd'} if nm == '섞인 값' else set()) | {'w:egg'})
            check('[%s] 다음 발견을 저장하면 새로 쓴다 — 알림이 사라지고 정상 형식 %s' % (nm, exp_keys), after.get('v') == 1 and sorted(k for k in after['k'] if k in set(keys['all'])) == exp_keys and not await pg.evaluate("__cdx.bad") and len(json.dumps(after)) < 12000, (after if len(json.dumps(after)) < 500 else len(json.dumps(after))))
            await ctx.close()
        # 표에 없는 키는 화면·서버에는 안 나가지만 저장에서는 지우지 않는다(다른 버전이 남긴 발견)
        ctx, pg, errs = await mk(b, srv.port, init="localStorage.setItem('p6_codex_v1',%s)" % json.dumps(json.dumps({'v': 1, 'k': ['zz:future', 'w:feed']})))
        await pg.evaluate("__cx.cdxNote('w:egg')")
        after = json.loads(await pg.evaluate("localStorage.getItem('p6_codex_v1')"))
        body = await pg.evaluate("(()=>{const b={t:1};__cx.cdxAttach(b);return b})()")
        check('표에 없는 키(zz:future)는 칸 수에 안 들어가고 서버 본문에도 안 나가지만 저장소에는 남는다', (await stat(pg))['n'] == 2 and 'zz:future' in after['k'] and sorted(body.get('codex', [])) == ['w:egg', 'w:feed'], (after, body))
        await ctx.close()
        # 저장소 차단 — 읽기부터 막힘
        block = """(function(){const th=function(){throw new DOMException('blocked','SecurityError')};
          try{Object.defineProperty(window,'localStorage',{get:th,configurable:true});}catch(e){}
          try{Object.defineProperty(window,'sessionStorage',{get:th,configurable:true});}catch(e){}})();"""
        ctx, pg, errs = await mk(b, srv.port, init=block)
        check('저장소 차단(읽기·쓰기 모두 예외): 페이지가 뜨고 배지 0/127', await pg.evaluate("document.getElementById('cxN').textContent") == '0/127' and await pg.evaluate("(()=>{try{localStorage.getItem('x');return false}catch(e){return true}})()"))
        await pg.evaluate("__p6x.start();__p6x.applyUp({t:'w',k:'pan',l:0});__p6x.applyUp({t:'p',k:'spd',l:0})")
        check('저장소 차단: 판을 시작하고 카드를 골라도 게임이 멈추지 않는다(이번 방문 동안은 메모리에 기록)', await pg.evaluate("__p6x.state") == 'play' and (await stat(pg))['n'] == 3)
        await pg.evaluate("__p6x.endRun(false,true)"); await pg.evaluate("document.getElementById('homeBtn').click()")
        await open_dex(pg)
        note = await pg.evaluate("[...document.querySelectorAll('#cxBody .cxnote')].map(e=>e.textContent)")
        first = await pg.evaluate("document.getElementById('cxBody').firstElementChild.className")
        check('저장소 차단: 도감 첫머리에 한 줄로 알린다(이번 방문 동안만)', len(note) == 1 and '저장하지 못해요' in note[0] and '이번 방문 동안만' in note[0] and first == 'cxnote', (note, first))
        check('저장소 차단: 이번 방문 동안 발견한 3칸은 열려 있다', await pg.evaluate("document.querySelector('.cxprog b').textContent") == '3 / 127' and await pg.evaluate("document.querySelectorAll('#cxPanel .cxt:not(.lock)').length") == 2)
        check('저장소 차단: 오류 없음', not errs, errs)
        await shot(pg, '4_storage_blocked_390x844.png')
        await ctx.close()
        # 쓰기만 막힘(용량 초과 따위)
        wblock = "(function(){const o=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='p6_codex_v1')throw new DOMException('quota','QuotaExceededError');return o.apply(this,arguments)}})();"
        ctx, pg, errs = await mk(b, srv.port, init=wblock)
        await pg.evaluate("__cx.cdxNote('w:feed')")
        await open_dex(pg)
        check('쓰기만 막혀도(용량 초과) 메모리에는 남고 알림이 뜬다', (await stat(pg))['n'] == 1 and await pg.evaluate("document.querySelectorAll('#cxBody .cxnote').length") == 1 and not errs, errs)
        await ctx.close()
        # 두 탭(같은 브라우저) 동시 쓰기 — 서로의 발견을 잃지 않는다
        ctx = await b.new_context(viewport={'width': 390, 'height': 844})
        async def route2(r):
            if r.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_()
            else: await r.abort()
        await ctx.route('**/*', route2)
        A = await ctx.new_page(); Bp = await ctx.new_page(); e2 = []
        for pgx in (A, Bp):
            pgx.on('pageerror', lambda e: e2.append(str(e)))
            await pgx.goto('http://127.0.0.1:%d/%s' % (srv.port, PAGE)); await pgx.wait_for_function("window.__cdx!==undefined&&window.__cx!==undefined")
        await A.evaluate("__cx.cdxNote('w:feed')"); await Bp.evaluate("__cx.cdxNote('w:egg')")   # 거의 같은 순간 — 저장소는 탭 사이에서 원자적이지 않아 한쪽이 덮일 수 있고, 덮인 쪽은 이벤트를 받는 대로 합집합을 다시 쓴다
        await A.wait_for_function("(()=>{try{return JSON.parse(localStorage.getItem('p6_codex_v1')).k.length===2}catch(e){return false}})()", timeout=6000)
        await A.wait_for_timeout(300)
        sa = await A.evaluate("[...__cx.CDX.s].sort()"); sb = await Bp.evaluate("[...__cx.CDX.s].sort()")
        ls = json.loads(await A.evaluate("localStorage.getItem('p6_codex_v1')"))['k']
        check('두 탭이 따로 발견해도 저장소에 합집합이 남는다', ls == ['w:egg', 'w:feed'], ls)
        check('다른 탭의 발견이 storage 이벤트로 이 탭에도 반영된다(배지까지)', sa == ['w:egg', 'w:feed'] and sb == ['w:egg', 'w:feed'] and await A.evaluate("document.getElementById('cxN').textContent") == '2/127', (sa, sb))
        # 이벤트 없이 낡은 메모리로 쓰는 경쟁 — 쓰기 직전에 다시 읽어 합친다
        await A.evaluate("localStorage.setItem('p6_codex_v1',JSON.stringify({v:1,k:['w:egg','p:cd','tr:iron']}))")   # 같은 탭에서 쓰면 storage 이벤트가 안 온다 = 이 탭의 메모리가 낡은 상태
        await A.evaluate("__cx.cdxNote('co:dice')")
        ls = json.loads(await A.evaluate("localStorage.getItem('p6_codex_v1')"))['k']
        check('낡은 메모리로 저장해도 저장소의 다른 발견을 지우지 않는다(쓰기 직전 합집합)', ls == sorted(['w:egg', 'p:cd', 'tr:iron', 'w:feed', 'co:dice']), ls)
        check('두 탭 시험에서 오류 없음', not e2, e2)
        await ctx.close()
        # 열려 있는 겹창은 다른 탭의 발견으로 갱신된다(보던 탭·펼친 칸 유지)
        ctx = await b.new_context(viewport={'width': 390, 'height': 844})
        await ctx.route('**/*', route2)
        A = await ctx.new_page(); Bp = await ctx.new_page()
        for pgx in (A, Bp):
            await pgx.goto('http://127.0.0.1:%d/%s' % (srv.port, PAGE)); await pgx.wait_for_function("window.__cdx!==undefined&&window.__cx!==undefined")
        await A.evaluate("__cx.cdxNote('p:spd')"); await A.wait_for_timeout(100)
        await A.click('#cxOpen'); await A.click('#cxTab_p'); await A.locator('#cxPanel .cxt').nth(0).click()
        await Bp.evaluate("__cx.cdxNote('p:hp')"); await A.wait_for_timeout(300)
        r = await A.evaluate("({tab:document.querySelector('.cxtab[aria-selected=true]').dataset.t,n:document.querySelector('.cxprog b').textContent,open:document.querySelectorAll('#cxD').length,ex:document.querySelector('#cxPanel .cxt[aria-expanded=true]')&&document.querySelector('#cxPanel .cxt[aria-expanded=true]').dataset.i,un:document.querySelectorAll('#cxPanel .cxt:not(.lock)').length})")
        check('겹창이 열려 있는 동안 다른 탭이 발견해도 갱신되고 보던 탭·펼친 칸이 유지된다', r == {'tab': 'p', 'n': '2 / 127', 'open': 1, 'ex': '0', 'un': 2}, r)
        await ctx.close()

        # ═════════════ ⑤ 서버 동기화(봇 모의) ═════════════
        print('\n── ⑤ 서버 동기화 — /p6/run 본문의 codex · /p6/me 응답의 codex · 구버전 봇 ──', flush=True)
        POSTS = []
        def mk_mock(state):
            async def mock(r):
                u = r.request.url
                hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
                if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
                if '/p6/board' in u: await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'board': [], 'hard': [], 'vhard': []})); return
                if '/p6/me' in u:
                    j = {'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1}
                    if 'codex' in state: j['codex'] = state['codex']
                    await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps(j)); return
                if '/p6/run' in u:
                    body = r.request.post_data or '{}'; POSTS.append((json.loads(body), len(body.encode('utf-8'))))
                    code = state.get('run_code')
                    await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': False, 'code': code} if code else {'ok': True, 'rank': 3, 'total': 9, 'unlocks': ['brj'], 'best_t': 10}))
                    return
                await r.fulfill(status=404, headers=hdr, body='{}')
            return mock
        async def logged(st, init=None, w=412, h=860):
            ctx, pg, errs = await mk(b, srv.port, w, h, mock=mk_mock(st), init=LOGIN + ';' + (init or ''))
            await pg.wait_for_timeout(400)
            return ctx, pg, errs
        POSTS.clear()
        ctx, pg, errs = await logged({})
        await pg.evaluate("__p6x.start();__adv(20,{god:true});__p6x.applyUp({t:'w',k:'egg',l:0});__p6x.applyUp({t:'rl',k:'rl:tenth',r:'tenth',l:0});__p6x.endRun(false,true)")
        await pg.wait_for_timeout(700)
        mine = sorted(await pg.evaluate("[...__cx.CDX.s]"))
        check('로그인한 판 기록 본문에 codex(내 발견 전체, 정렬)가 들어간다', len(POSTS) == 1 and POSTS[0][0].get('codex') == mine and len(mine) >= 3, (POSTS[0][0].get('codex') if POSTS else None, mine))
        check('본문의 기존 필드(t·kills·lv·ch·won·hard·vhard·unlocks·token)는 그대로', len(POSTS) == 1 and all(k in POSTS[0][0] for k in ('token', 't', 'kills', 'lv', 'ch', 'won', 'hard', 'vhard', 'unlocks')) and POSTS[0][0]['ch'] == 'brj')
        check('본문 크기 4096바이트 안(%d바이트)' % (POSTS[0][1] if POSTS else -1), POSTS and POSTS[0][1] < 4096, POSTS[0][1] if POSTS else None)
        check('codex 항목은 모두 서버 정규식 · 400개 이하', all(KEYRE.match(k) for k in POSTS[0][0]['codex']) and len(POSTS[0][0]['codex']) <= 400)
        check('기록 올린 뒤 오류 없음', not errs, errs)
        await ctx.close()
        # 가장 큰 경우 — 모든 키(217개) 발견 + 매우 긴 unlocks
        POSTS.clear()
        ctx, pg, errs = await logged({}, init=seed_init(keys['all']))
        await pg.evaluate("__p6x.start();__adv(20,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(700)
        check('모든 키를 발견한 사람의 본문: 전부 실리고(%d개) 4096바이트 안(%d바이트)' % (len(POSTS[0][0].get('codex', [])) if POSTS else -1, POSTS[0][1] if POSTS else -1), POSTS and sorted(POSTS[0][0]['codex']) == sorted(keys['all']) and POSTS[0][1] < 4096)
        # 한도를 넘기는 경우: 가장 새로 발견한 것부터 싣는다(방어)
        r = await pg.evaluate("""()=>{const c=__cx;const body={token:'x'.repeat(30),t:1,kills:2,lv:3,ch:'brj',won:false,hard:0,vhard:0,unlocks:['brj']};const full=Object.assign({},body);c.cdxAttach(full);
          const save=c.CDX.BODY;c.CDX.BODY=700;const small=Object.assign({},body);c.cdxAttach(small);c.CDX.BODY=save;
          const sz=o=>new TextEncoder().encode(JSON.stringify(o)).length;
          const order=[...c.CDX.s];const newest=order.slice(-small.codex.length).sort();
          c.CDX.BODY=10;const tiny=Object.assign({},body);c.cdxAttach(tiny);c.CDX.BODY=save;
          return {nf:full.codex.length,ns:small.codex.length,szs:sz(small),szf:sz(full),newest:JSON.stringify(newest)===JSON.stringify(small.codex),tiny:tiny.codex===undefined};}""")
        check('[방어] 한도(예: 700바이트)를 넘으면 가장 새로 발견한 것부터 싣고 한도 안에 든다', r['ns'] < r['nf'] and r['ns'] > 10 and r['szs'] <= 700 and r['newest'] and r['szf'] < 4096, r)
        check('[방어] 아무것도 못 싣는 극단에서는 codex 를 빼고 보낸다(본문이 깨지지 않음)', r['tiny'])
        check('[⑤ 오류 없음]', not errs, errs)
        await ctx.close()
        # /p6/me 의 codex 를 합친다(기기에도 저장)
        srv_list = ['w:feed', 'p:spd', 'rl:sg_yj', 'sy:kitchen', 'ev:egg', 'w:egg', 'zz:future']
        ctx, pg, errs = await logged({'codex': srv_list}, init="if(!sessionStorage.getItem('__s')){localStorage.setItem('p6_codex_v1',JSON.stringify({v:1,k:['w:sushi','tr:iron']}));sessionStorage.setItem('__s','1')}")
        await pg.wait_for_function("__cdx.stat().n>=6", timeout=8000)
        have = sorted(await pg.evaluate("[...__cx.CDX.s]")); ls = json.loads(await pg.evaluate("localStorage.getItem('p6_codex_v1')"))['k']
        check('/p6/me 의 codex 가 기기 발견과 합집합으로 합쳐진다', set(have) == {'w:sushi', 'tr:iron', 'w:feed', 'p:spd', 'rl:sg_yj', 'sy:kitchen', 'ev:egg', 'w:egg'}, have)
        check('합친 결과가 기기(localStorage)에도 저장된다(표에 없는 키도 보존)', set(ls) >= set(have) and 'zz:future' in ls and ls == sorted(ls), ls)
        check('배지도 새 숫자로(칸만 센다: w:sushi tr:iron w:feed p:spd rl:sg_yj sy:kitchen w:egg = 7)', await pg.evaluate("document.getElementById('cxN').textContent") == '7/127')
        await pg.reload(); await pg.wait_for_function("window.__cdx!==undefined"); await pg.wait_for_timeout(300)
        check('[me 합치기] 오류 없음', not errs, errs)
        await ctx.close()
        ctx, pg, errs = await logged({'codex': ['w:feed', 'p:spd']}, init="try{localStorage.removeItem('p6_codex_v1')}catch(e){}")
        await pg.wait_for_function("__cdx.stat().n>=2", timeout=8000)
        check('기기 저장이 비어 있어도 서버 기록으로 채워진다(다른 기기에서 이어보기)', (await stat(pg))['n'] == 2 and json.loads(await pg.evaluate("localStorage.getItem('p6_codex_v1')"))['k'] == ['p:spd', 'w:feed'])
        await ctx.close()
        # 겹창이 열려 있는 동안 서버 응답이 오면 갱신
        async def slow_me(r):
            u = r.request.url; hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
            if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
            if '/p6/me' in u:
                await asyncio.sleep(1.2); await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1, 'codex': ['w:feed', 'w:egg', 'p:spd']})); return
            await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'board': [], 'hard': [], 'vhard': []}))
        ctx, pg, errs = await mk(b, srv.port, 390, 844, mock=slow_me, init=LOGIN)
        await open_dex(pg)
        t0 = (await pg.evaluate("document.querySelector('.cxprog b').textContent"))
        await pg.wait_for_function("document.querySelector('.cxprog b').textContent==='3 / 127'", timeout=8000)
        check('겹창을 연 채 서버 응답이 늦게 와도 숫자·칸이 바로 갱신된다(%s → 3 / 127)' % t0, await pg.evaluate("document.querySelectorAll('#cxPanel .cxt:not(.lock)').length") == 2)
        await ctx.close()
        # 구버전 봇 — 필드 없음 / 형식 틀림
        for nm, val in [('필드 없음', None), ('문자열', 'w:feed'), ('객체', {'a': 1}), ('숫자', 7), ('null', 'NULL'), ('배열 안 쓰레기', [1, None, {}, 'BAD', 'zz:x', 'w:Feed', ['w:feed']]), ('빈 배열', [])]:
            st = {} if val is None else {'codex': (None if val == 'NULL' else val)}
            ctx, pg, errs = await logged(st, init="try{localStorage.removeItem('p6_codex_v1')}catch(e){}")
            await pg.wait_for_timeout(300)
            n = (await stat(pg))['n']; ls = await pg.evaluate("localStorage.getItem('p6_codex_v1')")
            check('[구버전/이상한 응답: %s] 조용히 무시 — 오류 없음 · 도감 그대로(0칸) · 저장소를 건드리지 않음' % nm, n == 0 and ls is None and not errs and await pg.evaluate("document.getElementById('acct').textContent.includes('로그인 중')"), (n, ls, errs))
            await ctx.close()
        # 판 기록이 서버에 거절돼 기기에 남을 때 — 보관본에는 codex 가 없고, 다시 올릴 때는 최신 codex 를 싣는다
        POSTS.clear()
        stt = {'run_code': 'upstream_down'}
        ctx, pg, errs = await logged(stt)
        await pg.evaluate("__p6x.start();__adv(20,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(800)
        keep = await pg.evaluate("localStorage.getItem('p6_unsent')")
        check('서버가 기록을 못 받으면 기기에 보관한다 — 보관본에는 도감 목록을 넣지 않는다', keep and 'codex' not in keep, keep)
        stt.pop('run_code'); await pg.evaluate("__cx.cdxNote('w:fryer')")
        n_before = len(POSTS)
        await pg.evaluate("document.getElementById('rRetry')&&document.getElementById('rRetry').click()"); await pg.wait_for_timeout(700)
        check('다시 저장하면 그 사이 늘어난 최신 도감(w:fryer 포함)이 실려 나간다', len(POSTS) == n_before + 1 and 'w:fryer' in POSTS[-1][0].get('codex', []) and POSTS[-1][0].get('codex') == sorted(await pg.evaluate("[...__cx.CDX.s]")), POSTS[-1][0].get('codex') if POSTS else None)
        await ctx.close()
        # 로그인 안 한 사람은 서버로 아무것도 안 나간다
        POSTS.clear()
        ctx, pg, errs = await mk(b, srv.port, mock=mk_mock({}))
        await pg.evaluate("__p6x.start();__adv(20,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(500)
        check('로그인 안 하면 판 기록 업로드 자체가 없다(도감도 기기에만)', not POSTS and (await stat(pg))['n'] >= 1)
        await ctx.close()

        # ═════════════ ⑦ 이어하기 서명 · 새 상태 없음 ═════════════
        print('\n── ⑦ 이어하기 서명 — 새 S 키 0 · 표 노드 변화 0 · 새 최상위 let 0 ──', flush=True)
        src_new = open(os.path.join(H.ROOT, 'survivors.html'), encoding='utf-8').read()
        def toplevel_lets(src):
            body = src[src.index("(()=>{\n'use strict';"):]
            return sorted(re.findall(r'^let ([A-Za-z_$][\w$]*)', body, re.M))
        if base_ok:
            src_base = open(os.path.join(H.ROOT, BASE_PAGE), encoding='utf-8').read()
            lets_b = toplevel_lets(src_base.replace('let INV_CAP=.80;', 'const INV_CAP=.80;')); lets_n = toplevel_lets(src_new)
            check('IIFE 최상위 let 이 기준 커밋과 같다(새 최상위 let 0 · %d개)' % len(lets_n), lets_b == lets_n, (set(lets_n) ^ set(lets_b)))
            ctxn, pgn, errn = await mk(b, srv.port, 390, 844)
            ctxb, pgb, errb = await mk(b, srv.port, 390, 844, page=BASE_PAGE, ready='window.__cx!==undefined&&window.__p6x!==undefined')
            fn = "()=>{const x=__p6x;x.start();return {sig:__cx.RES.SIG,keys:Object.keys(x.S),n:__cx.RES.STATIC?__cx.RES.STATIC.size:-1}}"
            fn_new = await pgn.evaluate(fn); fn_base = await pgb.evaluate(fn)
            check('이어하기 서명(SIG)이 기준 커밋과 같다 — 표 노드를 더하거나 빼지 않았다(%s)' % fn_new['sig'], fn_new['sig'] == fn_base['sig'] and fn_new['n'] == fn_base['n'], (fn_new['sig'], fn_base['sig']))
            check('판 상태 S 의 키 목록이 기준 커밋과 같다(새 S 키 0 · %d개)' % len(fn_new['keys']), fn_new['keys'] == fn_base['keys'], set(fn_new['keys']) ^ set(fn_base['keys']))
            r = await pgn.evaluate("""()=>{const x=__p6x,c=__cx;x.start();x.applyUp({t:'w',k:'feed',l:0});const b=c.RES.build();return {ok:b.text!==null,why:b.why||'',txt:b.text?b.text.includes('codex')||b.text.includes('p6_codex'):false}}""")
            check('판을 저장하는 이어하기 모듈이 새 상태 때문에 거부하지 않고, 저장본에 도감 정보가 섞이지 않는다', r['ok'] and not r['txt'], r)
            check('두 사본의 첫 화면 시험 오류 없음', not errn and not errb, (errn, errb))
            await ctxn.close(); await ctxb.close()
            # 옛 버전(기준 커밋)이 남긴 이어하기 저장본이 새 버전에서 그대로 되살아난다 — 같은 브라우저(같은 저장소)에서 사본만 바꿔 연다
            cx = await b.new_context(viewport={'width': 412, 'height': 860})
            async def route3(r):
                if r.request.url.startswith('http://127.0.0.1:%d/' % srv.port): await r.continue_()
                else: await r.abort()
            await cx.route('**/*', route3)
            pa = await cx.new_page(); e3 = []
            pa.on('pageerror', lambda e: e3.append(str(e)))
            await pa.goto('http://127.0.0.1:%d/%s' % (srv.port, BASE_PAGE)); await pa.wait_for_function("window.__p6x!==undefined&&window.__cx!==undefined")
            await pa.evaluate("()=>{__p6x.start();__adv(60,{god:true});document.getElementById('pauseBtn').click();}")
            h0 = await pa.evaluate("(()=>{const t=localStorage.getItem('p6_resume_v1');return t?JSON.parse(t.slice(0,t.indexOf('\\n'))):null})()")
            check('(준비) 기준 커밋 사본에서 일시정지 → 이어하기 저장본이 남는다', bool(h0) and h0.get('st') == 'pause' and h0.get('t', 0) >= 30, h0)
            await pa.goto('http://127.0.0.1:%d/%s' % (srv.port, PAGE)); await pa.wait_for_function("window.__p6x!==undefined&&window.__cx!==undefined&&window.__cdx!==undefined")
            r = await pa.evaluate("()=>{const h=__cx.RES.peek();return {why:h?__cx.RES.usableHead(h):'none',card:!document.getElementById('resCard').hidden,t:h&&h.t,lv:h&&h.lv,ch:h&&h.ch}}")
            check('옛 저장본의 서명이 새 버전에서도 유효하다(usableHead 가 비어 있다) · 이어하기 카드가 뜬다', r['why'] == '' and r['card'], r)
            await pa.click('#resGo'); await pa.wait_for_function("__p6x.state==='pause'", timeout=8000)
            r2 = await pa.evaluate("({t:Math.floor(__p6x.S.t),lv:__p6x.S.lv,ch:__p6x.CH.k,codex:(__cx.CDX.s.has('w:'+__p6x.CH.w))})")
            check('옛 저장본을 새 버전에서 이어하면 같은 판(시간·레벨·캐릭터)이 되살아난다', r2['t'] == r['t'] and r2['lv'] == r['lv'] and r2['ch'] == r['ch'], (r, r2))
            miss = await pa.evaluate("""()=>{const S=__p6x.S,c=__cx,own=[];for(const k in S.w)own.push('w:'+k);for(const k in S.ps)own.push('p:'+k);for(const k in S.rel)own.push('rl:'+k);for(const k in S.tr)own.push('tr:'+k);for(const k in S.sm)own.push('sm:'+k);
              if(S.ramen)own.push('sm:ramen');for(const k in S.pt)own.push('pt:'+k);for(const k in S.tier)own.push('wt:'+k);for(const k in S.ev)own.push('ev:'+k);for(const k of S.synOn)own.push('sy:'+k);return {own:own.length,miss:own.filter(k=>!c.CDX.s.has(k))};}""")
            check('도감이 생기기 전에 시작한 옛 판을 되살려도 가진 것(무기 %d개 등 %d개)이 모두 도감에 실린다 · 오류 없음' % (len(await pa.evaluate("Object.keys(__p6x.S.w)")), miss['own']), r2['codex'] and not miss['miss'] and miss['own'] >= 2 and not e3, (miss, e3))
            await cx.close()
        else:
            check('기준 커밋 사본을 만들 수 없어 ⑦ 비교를 못 했다(CDX_BASE_COMMIT 확인)', False)

        # ═════════════ ⑧ 레이아웃 ═════════════
        print('\n── ⑧ 레이아웃 — 7개 화면 크기에서 첫 화면 버튼 · 겹창 · 격자 · 상세 ──', flush=True)
        LAY = """()=>{const rc=e=>{const r=e.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom,w:r.width,h:r.height}};
          const hit=(a,b)=>a.l<b.r-.5&&b.l<a.r-.5&&a.t<b.b-.5&&b.t<a.b-.5;const o={};
          const vw=innerWidth,vh=innerHeight;o.vw=vw;o.vh=vh;o.doc=document.documentElement.scrollWidth<=vw;
          const els={cx:document.getElementById('cxOpen'),pn:document.getElementById('pnOpen'),lab:document.querySelector('.key .lab'),st:document.getElementById('startBtn')};
          const R={};for(const k in els)R[k]=rc(els[k]);o.R=R;
          o.inside=['cx','pn'].every(k=>R[k].l>=0&&R[k].r<=vw+.5);o.cxH=R.cx.h;o.cxW=R.cx.w;o.cxMin=Math.min(R.cx.h,R.cx.w);
          o.keyBox=(()=>{const k=rc(document.querySelector('.key'));return ['cx','pn','lab'].every(n=>R[n].l>=k.l-.5&&R[n].r<=k.r+.5&&R[n].t>=k.t-.5&&R[n].b<=k.b+.5)})();
          o.noHit=!hit(R.cx,R.pn)&&!hit(R.cx,R.lab)&&!hit(R.pn,R.lab);o.start=R.st.h;o.chip=document.getElementById('cxN').textContent;o.chipShown=getComputedStyle(document.getElementById('cxN')).display!=='none';
          return o;}"""
        OVL = """()=>{const rc=e=>{const r=e.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom,w:r.width,h:r.height}};
          const hit=(a,b)=>a.l<b.r-.5&&b.l<a.r-.5&&a.t<b.b-.5&&b.t<a.b-.5;const o={bad:[]};const vw=innerWidth,vh=innerHeight;
          const box=rc(document.querySelector('.cxbox')),body=document.getElementById('cxBody'),bd=rc(body);
          o.box=box;o.boxIn=box.l>=-.5&&box.r<=vw+.5&&box.t>=-.5&&box.b<=vh+.5;o.noScrollX=body.scrollWidth<=body.clientWidth+1&&document.documentElement.scrollWidth<=vw;
          const tabs=[...document.querySelectorAll('.cxtab')].map(rc);o.tabsIn=tabs.every(t=>t.l>=bd.l-.5&&t.r<=bd.r+.5);o.tabMin=Math.min(...tabs.map(t=>Math.min(t.w,t.h)));
          o.tabHit=tabs.some((a,i)=>tabs.some((b,j)=>i<j&&hit(a,b)));
          const x=rc(document.getElementById('cxX'));o.xMin=Math.min(x.w,x.h);const xin=x.l>=box.l&&x.r<=box.r&&x.t>=box.t;o.xIn=xin;
          const tiles=[...document.querySelectorAll('#cxPanel .cxt')];const tr=tiles.map(rc);o.nt=tiles.length;
          o.tileIn=tr.every(t=>t.l>=bd.l-.5&&t.r<=bd.r+.5);o.tileMin=Math.min(...tr.map(t=>Math.min(t.w,t.h)));o.tileHit=tr.some((a,i)=>tr.some((b,j)=>i<j&&hit(a,b)));
          o.tileTxt=tiles.every(t=>[...t.querySelectorAll('.cxnm')].every(n=>n.scrollWidth<=n.clientWidth+1));
          o.cols=new Set(tr.map(t=>Math.round(t.l))).size;
          const fs=[];for(const el of document.querySelectorAll('#cxOv *')){let own=false;for(const c of el.childNodes)if(c.nodeType===3&&c.textContent.trim())own=true;if(own){const s=parseFloat(getComputedStyle(el).fontSize);if(s<11.5)fs.push([el.className,el.textContent.slice(0,12),s]);}}
          o.smallFont=fs.slice(0,4);
          const d=document.getElementById('cxD');if(d){const dr=rc(d);o.dIn=dr.l>=bd.l-.5&&dr.r<=bd.r+.5;o.dHit=tr.some(t=>hit(t,dr));o.dTxt=[...d.querySelectorAll('*')].every(e=>e.scrollWidth<=e.clientWidth+1||getComputedStyle(e).display==='inline');o.dTop=dr.t;}
          return o;}"""
        for (w, h, mob) in SIZES:
            ctx, pg, errs = await mk(b, srv.port, w, h, mobile=mob, init=seed_init(keys['all']))
            tag = '%dx%d' % (w, h)
            for res_card in ([False, True] if (w > h and h <= 520) else [False]):   # 가로 화면은 이어하기 카드가 있을 때(hasres)의 배치도 같이 본다
                await pg.evaluate("on=>document.getElementById('title').classList.toggle('hasres',on)", res_card)
                o = await pg.evaluate(LAY)
                side = res_card   # 이어하기 카드 + 가로: 패치노트·도감 버튼이 키아트 옆(바깥)으로 나란히 나온다(기존 규칙)
                nm_ = tag + ('+이어하기' if res_card else '')
                check('[%s] 첫 화면: 도감 버튼이 화면 안에 있고 패치노트·← SQUAD.GG 와 겹치지 않는다%s' % (nm_, '(키아트 옆 배치)' if side else ' · 키아트 안'), o['inside'] and (o['keyBox'] or side) and o['noHit'] and o['doc'], o)
                check('[%s] 첫 화면: 도감 버튼 터치 영역 ≥ 40px(%dx%d) · 시작 버튼 높이 %d' % (nm_, o['cxW'], o['cxH'], o['start']), o['cxMin'] >= 40 and o['start'] >= 40, o)
                await shot(pg, '8_title_%s.png' % nm_.replace('+', '_'))
            await pg.evaluate("document.getElementById('title').classList.remove('hasres')")
            await open_dex(pg)
            o = await pg.evaluate(OVL)
            check('[%s] 겹창: 화면 안 · 가로 넘침 0 · 탭 5개 모두 안(터치 ≥ 40px %d) · 겹침 0' % (tag, o['tabMin']), o['boxIn'] and o['noScrollX'] and o['tabsIn'] and o['tabMin'] >= 40 and not o['tabHit'], o)
            check('[%s] 겹창: 닫기 버튼 ≥ 40px · 격자 %d칸 모두 안 · 열 %d개 · 칸 겹침 0 · 칸 터치 ≥ 40px(%d)' % (tag, o['nt'], o['cols'], o['tileMin']), o['xMin'] >= 40 and o['xIn'] and o['tileIn'] and not o['tileHit'] and o['tileMin'] >= 40 and o['nt'] == 40, o)
            if w <= 412 and w > h * 0.0: check('[%s] 폰 세로 폭에서 격자는 3~4열' % tag, 3 <= o['cols'] <= 4, o['cols'])
            check('[%s] 겹창: 칸 이름 글자가 칸 밖으로 안 넘친다 · 글자 ≥ 11.5px' % tag, o['tileTxt'] and not o['smallFont'], o['smallFont'])
            await shot(pg, '8_grid_%s.png' % tag)
            # 가장 긴 상세들 — 각성·마스터·초월이 다 있는 무기, 패시브(초월 포함), 유물, 시너지
            for t, key, lab in [('w', 'w:sing', '플레이브 노래부르기(긴 설명)'), ('w', 'w:breath', '용조련사 브레스'), ('w', 'w:eom', '엄장신 엄! 외침'), ('p', 'p:mag', '패시브+초월'), ('r', 'rl:sg_bgb', '시그니처 유물'), ('s', 'sy:kitchen', '시너지(재료 3)'), ('x', 'sm:hp', '작은 능력치')]:
                await pg.click('#cxTab_' + t)
                keys_t = [e['key'] for e in ent if e['cat'] == t]
                await pg.locator('#cxPanel .cxt').nth(keys_t.index(key)).click(); await pg.wait_for_timeout(60)
                o = await pg.evaluate(OVL)
                check('[%s] 상세 %s: 겹창 안 · 가로 넘침 0 · 칸과 겹침 0 · 글자 안 넘침 · 위쪽이 요약줄에 안 가림(상단 %.0f)' % (tag, lab, o.get('dTop', -1)), o['boxIn'] and o['noScrollX'] and o.get('dIn') and not o.get('dHit') and o.get('dTxt') and not o['smallFont'], o)
                if key in ('w:sing', 'w:breath', 'sm:hp'): await shot(pg, '8_detail_%s_%s.png' % (key.replace(':', '_'), tag))
            # 열린 상세가 위쪽부터 보이는지(요약줄 아래) — 스크롤 위치 점검
            await pg.click('#cxTab_w'); await pg.locator('#cxPanel .cxt').nth(34).click(); await pg.wait_for_timeout(60)
            vis = await pg.evaluate("""()=>{const b=document.getElementById('cxBody'),s=document.getElementById('cxSum'),d=document.getElementById('cxD').getBoundingClientRect(),sb=getComputedStyle(s).position==='sticky'?s.getBoundingClientRect().bottom:b.getBoundingClientRect().top;return d.top>=sb-1&&d.top<=innerHeight}""")
            check('[%s] 아래쪽 칸을 눌러도 펼친 상세의 위쪽이 보인다' % tag, vis)
            check('[%s] 오류 없음' % tag, not errs, errs)
            await ctx.close()

        # ═════════════ ⑨ 키보드 · 포커스 · 닫기 ═════════════
        print('\n── ⑨ 키보드 — Esc · Tab 가두기 · 포커스 복귀 · 화살표 탭 · 배경 눌러 닫기 · 게임 시작 시 자동 닫힘 ──', flush=True)
        ctx, pg, errs = await mk(b, srv.port, 390, 844, mobile=False, init=seed_init(D1))
        await pg.focus('#cxOpen'); await pg.keyboard.press('Enter'); await pg.wait_for_function("document.getElementById('cxOv').classList.contains('on')")
        check('키보드(Enter)로 열리고 포커스가 닫기(✕) 버튼으로 간다', await pg.evaluate("document.activeElement.id==='cxX'"))
        await pg.keyboard.press('Escape')
        check('Esc 로 닫힌다', not await opened(pg))
        check('닫으면 포커스가 「스킬 도감」 버튼으로 돌아온다', await pg.evaluate("document.activeElement.id==='cxOpen'"))
        check('Esc 가 게임(일시정지 등)에 새지 않는다 — 상태는 title', await pg.evaluate("__p6x.state") == 'title')
        await pg.click('#cxOpen'); await pg.click('#cxX')
        check('✕ 로 닫힌다 · 포커스 복귀', not await opened(pg) and await pg.evaluate("document.activeElement.id==='cxOpen'"))
        await pg.click('#cxOpen'); await pg.mouse.click(3, 3)
        check('바깥(어두운 배경)을 눌러 닫힌다', not await opened(pg))
        await pg.click('#cxOpen'); await pg.mouse.click(195, 400)
        check('겹창 안쪽을 눌러도 닫히지 않는다', await opened(pg))
        # Tab 가두기 — 겹창 안에서만 돈다
        inside = []
        for i in range(60):
            await pg.keyboard.press('Tab'); inside.append(await pg.evaluate("document.getElementById('cxOv').contains(document.activeElement)"))
        check('Tab 을 60번 눌러도 포커스가 겹창 밖으로 나가지 않는다', all(inside))
        inside = []
        for i in range(60):
            await pg.keyboard.press('Shift+Tab'); inside.append(await pg.evaluate("document.getElementById('cxOv').contains(document.activeElement)"))
        check('Shift+Tab 도 마찬가지', all(inside))
        await pg.focus('#cxX'); await pg.keyboard.press('Shift+Tab')
        last = await pg.evaluate("(()=>{const f=[...document.querySelectorAll('#cxOv button')].filter(b=>b.tabIndex>=0&&b.offsetParent);return document.activeElement===f[f.length-1]})()")
        check('첫 요소에서 Shift+Tab → 마지막 요소로 돈다', last)
        # 화살표로 탭 이동(자동 활성)
        await pg.focus('#cxTab_w'); await pg.keyboard.press('ArrowRight')
        r = await pg.evaluate("({a:document.activeElement.id,sel:document.querySelector('.cxtab[aria-selected=true]').dataset.t,tab:document.querySelector('.cxtab[aria-selected=true]').tabIndex})")
        check('→ 키로 다음 탭(패시브)이 열리고 포커스도 따라간다', r == {'a': 'cxTab_p', 'sel': 'p', 'tab': 0}, r)
        await pg.keyboard.press('End'); r = await pg.evaluate("document.querySelector('.cxtab[aria-selected=true]').dataset.t")
        await pg.keyboard.press('ArrowRight'); r2 = await pg.evaluate("document.querySelector('.cxtab[aria-selected=true]').dataset.t")
        await pg.keyboard.press('Home'); r3 = await pg.evaluate("document.querySelector('.cxtab[aria-selected=true]').dataset.t")
        check('End → 마지막 탭 · 한 번 더 → → 처음으로 · Home → 처음', (r, r2, r3) == ('s', 'w', 'w'), (r, r2, r3))
        # 칸에서 Enter/Space 로 펼침
        await pg.focus('#cxPanel .cxt >> nth=0'); await pg.keyboard.press('Enter')
        check('칸에서 Enter 로 펼쳐진다(aria-expanded)', await pg.evaluate("document.querySelector('#cxPanel .cxt').getAttribute('aria-expanded')") == 'true' and await pg.evaluate("document.querySelectorAll('#cxD').length") == 1)
        await pg.keyboard.press('Space')
        check('Space 로 다시 접힌다', await pg.evaluate("document.querySelectorAll('#cxD').length") == 0)
        # 게임 시작·이어하기 등으로 첫 화면이 사라지면 자동 닫힘
        await pg.evaluate("__p6x.start()"); await pg.wait_for_timeout(100)
        check('겹창을 연 채 판이 시작되면(첫 화면이 사라지면) 저절로 닫힌다 · 상태 play', not await opened(pg) and await pg.evaluate("__p6x.state") == 'play')
        await pg.evaluate("__p6x.applyUp({t:'w',k:'pan',l:0});__p6x.endRun(false,true)"); await pg.evaluate("document.getElementById('homeBtn').click()"); await pg.wait_for_timeout(100)
        check('처음으로 돌아오면 배지가 새 숫자로 센다(판 중 발견 반영)', await pg.evaluate("document.getElementById('cxN').textContent") == '%d/127' % (await stat(pg))['n'] and (await stat(pg))['n'] > len([k for k in D1 if k in set(keys['t'])]))
        await pg.click('#cxOpen'); check('돌아온 첫 화면에서 다시 열린다', await opened(pg))
        await pg.keyboard.press('Escape')
        # 겹창이 열려 있을 때 게임 단축키가 새지 않는다
        await pg.click('#cxOpen'); await pg.keyboard.press('KeyP'); await pg.keyboard.press('Digit1'); await pg.keyboard.press('KeyR')
        check('겹창 위에서 P·1·R 같은 게임 키를 눌러도 게임 상태는 title', await pg.evaluate("__p6x.state") == 'title' and await opened(pg))
        # 겹창이 열린 채 닫히지 않는 길이 없는지 — 시작 버튼·이어하기·오늘의 도전은 겹창 뒤에 가려져 못 누른다
        r = await pg.evaluate("""()=>{const ids=['startBtn','dailyBtn','resGo','homeBtn'],o={};for(const id of ids){const e=document.getElementById(id);if(!e||!e.offsetParent){o[id]='안 보임';continue;}const r=e.getBoundingClientRect(),el=document.elementFromPoint(Math.min(innerWidth-1,Math.max(0,r.left+r.width/2)),Math.min(innerHeight-1,Math.max(0,r.top+r.height/2)));o[id]=document.getElementById('cxOv').contains(el)?'가려짐':'눌림';}return o;}""")
        check('겹창이 열려 있으면 시작·오늘의 도전 버튼은 겹창에 가려져 눌리지 않는다', all(v != '눌림' for v in r.values()), r)
        check('[⑨ 오류 없음]', not errs, errs)
        await ctx.close()
        # 터치
        ctx, pg, errs = await mk(b, srv.port, 390, 844, mobile=True, init=seed_init(D1))
        await pg.tap('#cxOpen'); check('터치: 탭으로 열린다', await opened(pg))
        await pg.tap('#cxTab_p'); await pg.locator('#cxPanel .cxt').nth(2).tap()
        check('터치: 탭·칸 탭으로 상세가 펼쳐진다', await pg.evaluate("document.querySelectorAll('#cxD').length") == 1 and await pg.evaluate("document.querySelector('.cxtab[aria-selected=true]').dataset.t") == 'p')
        await pg.tap('#cxX'); check('터치: ✕ 탭으로 닫힌다', not await opened(pg))
        await pg.tap('#cxOpen'); await pg.tap('#cxTab_w')
        cdp = await ctx.new_cdp_session(pg)   # 진짜 손가락 쓸어올리기 — body{touch-action:none} 아래에서도 도감 목록(touch-action:pan-y)이 스크롤돼야 한다
        await swipe(cdp, pg, 195, 650, 230)
        sc = await pg.evaluate("[document.getElementById('cxBody').scrollTop,document.scrollingElement.scrollTop,__p6x.state,document.querySelectorAll('#cxD').length]")
        check('터치: 손가락으로 쓸어 올리면 도감 목록이 스크롤된다 · 뒤의 페이지·게임은 그대로 · 쓸다가 칸이 눌려 펼쳐지지 않는다', sc[0] > 100 and sc[1] == 0 and sc[2] == 'title' and sc[3] == 0, sc)
        await swipe(cdp, pg, 195, 300, 720)
        check('터치: 다시 내리면 위로 돌아온다', await pg.evaluate("document.getElementById('cxBody').scrollTop") < sc[0])
        await ctx.close()
        # 패치노트 겹창과 서로 방해하지 않는다
        ctx, pg, errs = await mk(b, srv.port, 390, 844, mobile=False, ready='window.__cx!==undefined&&window.__cdx!==undefined&&window.__pn!==undefined')
        await pg.click('#pnOpen'); await pg.keyboard.press('Escape'); await pg.click('#cxOpen'); await pg.keyboard.press('Escape'); await pg.click('#pnOpen')
        check('패치노트·스킬 도감 겹창을 번갈아 열고 닫아도 서로 안 걸린다', await pg.evaluate("document.getElementById('pnOv').classList.contains('on')&&!document.getElementById('cxOv').classList.contains('on')"))
        check('[패치노트와 함께] 오류 없음', not errs, errs)
        await ctx.close()

        # ═════════════ ③-2 시작 화면 실제 흐름: 한 판 해 보고 돌아와 도감 열기 ═════════════
        ctx, pg, errs = await mk(b, srv.port, 412, 860, mobile=False)
        await pg.click('#startBtn'); await pg.wait_for_timeout(150)
        await pg.evaluate("__adv(150,{god:true})")   # 레벨업 카드를 순서대로 고른다
        n_play = (await stat(pg))['n']
        await pg.evaluate("__p6x.endRun(false,true)"); await pg.evaluate("document.getElementById('homeBtn').click()"); await pg.wait_for_timeout(100)
        await pg.click('#cxOpen'); st = await stat(pg)
        check('실제로 한 판 해 보고 돌아오면 고른 카드만큼 도감이 열려 있다(칸 %d개 · 판 도중 %d)' % (st['n'], n_play), st['n'] >= 3 and await pg.evaluate("document.querySelectorAll('#cxPanel .cxt:not(.lock)').length") >= 1, st)
        await shot(pg, '3_after_run_412x860.png')
        check('[실제 한 판] 오류 없음', not errs, errs)
        await ctx.close()

        # ═════════════ ⑩ 통합 검수 보완 (2026-10-10) ═════════════
        print('\n── ⑩ 통합 검수 보완 — 창 높이 고정 · 아래쪽 닫기 · 저장 되읽기 · 새 형식 보존 · 1% ──', flush=True)
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init=seed_init(['w:feed']))
        await pg.click('#cxOpen')
        ys = []
        hs = []
        for t in ('w', 'p', 'r', 'x', 's'):
            await pg.evaluate("(t)=>document.querySelector('#cxBody .cxtab[data-t=\"'+t+'\"]').click()", t)
            r = await pg.evaluate("()=>({y:document.querySelector('#cxBody .cxtab').getBoundingClientRect().top,h:document.querySelector('.cxbox').getBoundingClientRect().height})")
            ys.append(round(r['y'])); hs.append(round(r['h']))
        check('탭을 바꿔도 탭 줄 위치·창 높이가 안 변한다 %s %s' % (ys, hs), len(set(ys)) == 1 and len(set(hs)) == 1, (ys, hs))
        pct = await pg.evaluate("()=>document.querySelector('.cxpct').textContent")
        check('한 칸만 발견해도 진행 퍼센트가 0%% 가 아니다(%s)' % pct, pct == '1%', pct)
        bx = await pg.evaluate("()=>{const r=document.getElementById('cxX2').getBoundingClientRect(),b=document.querySelector('.cxbox').getBoundingClientRect();return {h:r.height,inBox:r.bottom<=b.bottom+.5&&r.top>=b.top}}")
        check('아래쪽 「닫기」 버튼이 높이 44px 이상이고 창 안에 있다 %s' % bx, bx['h'] >= 44 and bx['inBox'], bx)
        await pg.click('#cxX2')
        check('아래쪽 「닫기」 로 닫힌다', not await opened(pg))
        check('오류 0', not errs, errs)
        await ctx.close()
        # 가로 화면에서도 dvh 규칙이 이긴다
        ctx, pg, errs = await mk(b, srv.port, 844, 390)
        await pg.click('#cxOpen')
        r = await pg.evaluate("()=>{const e=document.querySelector('.cxbox');return {h:e.getBoundingClientRect().height,css:CSS.supports('height','100dvh')}}")
        check('가로 화면 창 높이 = 보이는 높이 − 12 %s' % r, abs(r['h'] - 378) <= 1, r)
        await ctx.close()
        # setItem 이 에러 없이 아무것도 안 하면 메모리 모드로 알린다
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init="try{Storage.prototype.setItem=function(){};}catch(e){}")
        await pg.evaluate("__cx.cdxNote('w:feed')")
        check('저장이 조용히 무시되면 메모리 모드(mem=true)로 알린다', await pg.evaluate("__cdx.mem") is True)
        await ctx.close()
        # 더 새 형식(v:2)은 덮어쓰지 않는다
        v2 = "try{if(!sessionStorage.getItem('__s2')){localStorage.setItem('p6_codex_v1',JSON.stringify({v:2,k:['w:feed']}));sessionStorage.setItem('__s2','1');}}catch(e){}"
        ctx, pg, errs = await mk(b, srv.port, 390, 844, init=v2)
        await pg.evaluate("__cx.cdxNote('p:spd')")
        raw = await pg.evaluate("localStorage.getItem('p6_codex_v1')")
        check('v:2 저장값은 v:1 로 덮어쓰지 않고(메모리 모드) 읽은 칸도 보인다 %s' % raw, json.loads(raw)['v'] == 2 and await pg.evaluate("__cdx.mem") is True and await pg.evaluate("__cx.CDX.s.has('w:feed')"), raw)
        await ctx.close()

        await b.close()

    # ═════════════ ⑥ 규칙 불변 — 정책 봇 측정기 ═════════════
    print('\n── ⑥ 규칙 불변 — 정책 봇 측정기로 기준 커밋과 같은 시드·같은 조건의 결과 줄이 비트까지 같다 ──', flush=True)
    if os.environ.get('CDX_NOSIM'):
        print('(CDX_NOSIM 지정 — 건너뜀: 확인 못 함)')
    elif not base_ok:
        check('기준 커밋 사본이 없어 정책 봇 비교를 못 했다', False)
    else:
        tmp = tempfile.mkdtemp(prefix='cxsim_'); outA = os.path.join(tmp, 'new'); outB = os.path.join(tmp, 'base')   # 저장소 밖 임시 폴더(중단돼도 저장소가 더러워지지 않게)
        chars = os.environ.get('CDX_SIM_CHARS', 'brj,jjg,yj,eom,psg'); seeds = os.environ.get('CDX_SIM_SEEDS', '1-2'); cap = os.environ.get('CDX_SIM_CAP', '300')
        base_src = os.path.join(H.ROOT, BASE_PAGE)   # 훅이 꽂힌 사본이 아니라 원본 기준 사본을 따로 만든다
        r = subprocess.run(['git', '-C', H.ROOT, 'show', BASE_COMMIT + ':survivors.html'], capture_output=True, timeout=30)
        base_clean = os.path.join(H.ROOT, 'survivors_cxbase_clean.html'); open(base_clean, 'wb').write(r.stdout)
        def run_sim(out, html):
            cmd = ['nice', '-n', '10', sys.executable, os.path.join(H.ROOT, 'tests', 'survivors_charbal_sim.py'), 'run', '--out', out, '--chars', chars, '--seeds', seeds, '--policy', 'full', '--cap', cap, '--procs', '1', '--html', html, '--quiet']
            p = subprocess.run(cmd, cwd=H.ROOT, capture_output=True, text=True, timeout=3000)
            return p.returncode, p.stdout[-400:] + p.stderr[-400:]
        rc1, o1 = run_sim(outA, 'survivors.html'); rc2, o2 = run_sim(outB, os.path.basename(base_clean))
        os.remove(base_clean)
        def rows(out):
            R = {}
            for fn in glob.glob(os.path.join(out, 'runs.*.jsonl')):
                for ln in open(fn, encoding='utf-8'):
                    ln = ln.strip()
                    if ln:
                        j = json.loads(ln); R[(j['char'], j['seed'], j['policy'])] = j
            return R
        RA, RB = rows(outA), rows(outB)
        DROP = ('wall_s', 'html', 'sig', 'errs')
        diff = []
        for k in sorted(set(RA) | set(RB)):
            a = {x: v for x, v in (RA.get(k) or {}).items() if x not in DROP}; bb = {x: v for x, v in (RB.get(k) or {}).items() if x not in DROP}
            if a != bb: diff.append(k)
        n_chars = len({k[0] for k in RA}); n_seeds = len({k[1] for k in RA})
        exp_n = len(chars.split(',')) * len(SIM.parse_seeds(seeds))
        check('정책 봇 실행이 끝났다(새 사본 %d줄 · 기준 사본 %d줄 · 캐릭터 %d · 시드 %d · cap %s초)' % (len(RA), len(RB), n_chars, n_seeds, cap), rc1 == 0 and rc2 == 0 and len(RA) == len(RB) == exp_n, (rc1, rc2, exp_n, o1, o2))
        check('결과 줄이 비트까지 같다 — 처치·레벨·받은 피해·무기·궤적 모두(다른 줄 %d개)' % len(diff), not diff and len(RA) >= 8 and n_chars >= 4 and n_seeds >= 2, diff[:3])
        check('두 사본 모두 페이지 오류 0', all(not r.get('errs') and 'error' not in r for r in list(RA.values()) + list(RB.values())), [r.get('errs') for r in RA.values() if r.get('errs')][:2])
        sample = next(iter(RA.values()), {})
        check('(참고) 결과 줄에 처치 %s · 레벨 %s · 종료 %s초' % (sample.get('kills'), sample.get('lv'), sample.get('end_t')), bool(sample))
        shutil.rmtree(tmp, ignore_errors=True)

    srv.close()
    for f in (PAGE, BASE_PAGE, 'survivors_cxbase_src.html', 'survivors_cxbase_clean.html'):
        try: os.remove(os.path.join(H.ROOT, f))
        except OSError: pass
    print('\n검사 %d개 · 실패 %d' % (N[0], len(FAILS)))
    for f in FAILS: print('  ✗', f)
    return 1 if FAILS else 0
sys.exit(asyncio.run(main()))
