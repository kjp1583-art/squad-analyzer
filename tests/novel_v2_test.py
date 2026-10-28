#!/usr/bin/env python3
"""「스콰드 생존게임」 새 원고(8장) 시험(Playwright). 사용: python3 tests/novel_v2_test.py [--shots DIR]
 닉네임 조사·검증 · 화자/초상 대조 · 엔딩 4종 경로(플래그·@rec 조합) · CG 6장 · 주인공 초상 없음 · 저장 후 복귀·새로고침 · 원고 버전 불일치 · 모바일 스크린샷."""
import asyncio, subprocess, sys, os, time, json, re
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'tooling'))
import novel_build as nb, glob
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
PORT = 8797; FAILS = []; NP = 0
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium')
def check(n, c, x=''):
    global NP
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:300] if x and not c else ''))
    if c: NP += 1
    else: FAILS.append(n)

DRIVE = """async (rules)=>{ const log={cg:[],picks:[],flags:{},end:null}; let ri=0;
 for(let i=0;i<60000;i++){ const m=__novel.mode();
  if(m.ws==='end'){log.end=m.end;log.flags={F1:__novel.getv('F1_APOLOGY'),F2:__novel.getv('F2_SPEAK'),F3:__novel.getv('F3_BACK'),OK:__novel.getv('END4_OK'),LAST:__novel.getv('LAST')};return log}
  if(document.getElementById('ovCred').classList.contains('on')){log.cred=(log.cred||0)+1;document.getElementById('credSkip').click()}
  else if(m.ws==='line')__novel.advance();
  else if(m.ws==='choice'){ let k=0; const r=rules[ri++]; if(r){const j=m.opts.findIndex(t=>t.includes(r)); if(j>=0)k=j} log.picks.push(m.opts[k]); __novel.choose(k) }
  else if(m.ws==='cg'){ log.cg.push(document.getElementById('cgImg').getAttribute('src')); __novel.closeCg() }
  await new Promise(r=>setTimeout(r,1)) }
 log.stuck=__novel.mode(); return log }"""

# 선택 순서: 1 자기소개 · 2 첫 인사 · 3 첫 스크림 뒤 · 4 연패(F1) · 5 확신 · 6 복기(F2) · 7 바론 앞(F3) · 8 마지막(LAST)
F1T, F1F = '죄송합니다. 안 그럴게요', '다들 못했잖아요'
F2T, F2F = '복기를 같이', '…괜찮아요'
F3T, F3F = '이건 제 잘못이네요. 앞으론', '아무 말도 하지 못한다'
SH, LT, NF = '제 몫이에요', '가방 한쪽', '탓하세요'
def rules(f1, f2, f3, last):
    # 규칙은 '선택이 나온 순서'대로 하나씩 쓴다(없으면 첫 보기)
    return ['저 별로', '잘 부탁', '위치를 잘못', f1, '정글 캠프가 아니라', f2, f3, last]
PATHS = {  # 이름: (규칙, 기대 엔딩, 기대 플래그)
 'end1 몫':            (rules(F1T, F2F, F3F, SH), 'end1', (1, 0, 0)),
 'end2 가볍게':        (rules(F1F, F2F, F3F, LT), 'end2', (0, 0, 0)),
 'end3 탓하세요':      (rules(F1T, F2T, F3T, NF), 'end3', (1, 1, 1)),
 'end4 몫(F2·F3 참)':  (rules(F1T, F2T, F3T, SH), 'end4', (1, 1, 1)),
 'end4 가볍게(F1 거짓)': (rules(F1F, F2T, F3T, LT), 'end4', (0, 1, 1)),
 'F2 거짓 F3 참 몫 -> end1': (rules(F1T, F2F, F3T, SH), 'end1', (1, 0, 1)),
 'F2 참 F3 거짓 가볍게 -> end2': (rules(F1T, F2T, F3F, LT), 'end2', (1, 1, 0)),
 'F2·F3 참 탓하세요 -> end3': (rules(F1F, F2T, F3T, NF), 'end3', (0, 1, 1)),
}

async def newpage(b, w=412, h=860, store=None):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, storage_state=store)
    async def route(r):
        if not r.request.url.startswith('http://localhost:%d/' % PORT): await r.abort()
        else: await r.continue_()
    await ctx.route('**/*', route); pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    await pg.goto('http://localhost:%d/novel.html?fast=1' % PORT)
    await pg.wait_for_function("!document.getElementById('tNew').disabled", timeout=20000)
    return ctx, pg, errs

async def start(pg, nick='민준'):
    await pg.fill('#nickIn', nick); await pg.click('#tNew')
    await pg.wait_for_function("__novel.mode().ws!=='title'")

async def main():
    sp = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=CHROME)
            await run(b)
            await b.close()
    finally:
        sp.terminate()
    print('\n통과 %d · 실패 %d' % (NP, len(FAILS)))
    for f in FAILS: print('  실패:', f)
    return 1 if FAILS else 0

async def run(b):
    ctx, pg, errs = await newpage(b)
    # ---- 1) 닉네임 조사
    J = await pg.evaluate("""()=>{const n=__novel.nick, out={}; for(const nm of ['민준','철수','영희','Faker','Mal','Kim','Zed','7','3','1','8','ㅋㅋ','민 준','a_b']){
      out[nm]=['이/가','은/는','을/를','와/과','야/아','이에요/예요','으로/로'].map(k=>nm+n.josa(nm,k)).join(' ')} return out}""")
    exp = {  # 받침 없음 / 있음 / ㄹ받침 / 영문 / 숫자
     '민준': '민준이 민준은 민준을 민준과 민준아 민준이에요 민준으로', '철수': '철수가 철수는 철수를 철수와 철수야 철수예요 철수로',
     '영희': '영희가 영희는 영희를 영희와 영희야 영희예요 영희로', 'Faker': 'Faker이 Faker은 Faker을 Faker과 Faker아 Faker이에요 Faker로',
     'Mal': 'Mal이 Mal은 Mal을 Mal과 Mal아 Mal이에요 Mal로', 'Kim': 'Kim이 Kim은 Kim을 Kim과 Kim아 Kim이에요 Kim으로',
     'Zed': 'Zed가 Zed는 Zed를 Zed와 Zed야 Zed예요 Zed로', '7': '7이 7은 7을 7과 7아 7이에요 7로', '3': '3이 3은 3을 3과 3아 3이에요 3으로',
     '1': '1이 1은 1을 1과 1아 1이에요 1로', '8': '8이 8은 8을 8과 8아 8이에요 8로', 'ㅋㅋ': 'ㅋㅋ이 ㅋㅋ은 ㅋㅋ을 ㅋㅋ과 ㅋㅋ아 ㅋㅋ이에요 ㅋㅋ으로',
     '민 준': '민 준이 민 준은 민 준을 민 준과 민 준아 민 준이에요 민 준으로', 'a_b': 'a_b가 a_b는 a_b를 a_b와 a_b야 a_b예요 a_b로'}
    # (영문 규칙: 글자 이름 끝소리 — l m n r 만 받침, 숫자: 0 1 3 6 7 8 받침. 민준 = 받침 ㄴ 이므로 위 첫 줄 정정)
    exp['민준'] = '민준이 민준은 민준을 민준과 민준아 민준이에요 민준으로'
    for k, v in exp.items(): check('조사 %s' % k, J[k] == v, J[k] + ' != ' + v)
    S = await pg.evaluate("""()=>{__novel.nick.set('철수'); const s=__novel.nick.sub; return [s('{PLAYER}님이 왔다'),s('{PLAYER}이/가 {PLAYER}은/는 {PLAYER}을/를 {PLAYER}와/과 {PLAYER}야/아 {PLAYER}이에요/예요'),s('{PLAYER}는 간다'),s('{PLAYER}입니다')]}""")
    check('치환 평문·조사 표기', S == ['철수님이 왔다', '철수가 철수는 철수를 철수와 철수야 철수예요', '철수는 간다', '철수입니다'], S)
    S = await pg.evaluate("""()=>{__novel.nick.set('민준'); return [__novel.nick.sub('{PLAYER}는 간다'),__novel.nick.sub('{PLAYER}님')]}""")
    check('받침 있는 닉 + 평문 는 → 은', S == ['민준은 간다', '민준님'], S)
    # ---- 2) 닉네임 검증
    V = await pg.evaluate("""()=>['', ' ', '가', '열두글자열두글자열두글자', '열세글자열세글자열세글자열세', 'a  b', '<b>x</b>', '{PLAYER}', '이름😀', '!!!', '___', 'ab_c-d.e', '홍 길동'].map(x=>__novel.nick.check(x)||'ok')""")
    check('닉 검증: 빈칸·공백·특수문자·길이', [v == 'ok' for v in V] == [False, False, True, True, False, False, False, False, False, False, False, True, True], V)
    check('닉 지정 시 정리(공백 접기·12자)', await pg.evaluate("__novel.nick.clean('  가   나  ')==='가 나'&&__novel.nick.clean('1234567890123456').length===12"))
    # ---- 3) 시작 화면: 잘못된 닉이면 시작 안 됨 · 기본값(디스코드 닉)
    await pg.fill('#nickIn', '<<>>'); await pg.click('#tNew'); await pg.wait_for_timeout(200)
    check('잘못된 닉이면 시작되지 않고 안내', (await pg.evaluate("__novel.mode().ws"))=='title' and (await pg.inner_text('#nickErr')) != '')
    await ctx.close()
    ctx = await b.new_context(viewport={'width': 412, 'height': 860}); await ctx.add_init_script("localStorage.setItem('sgg_dc',JSON.stringify({id:'1',name:'디코 닉',token:'T'.repeat(40),exp:Date.now()+9e6}))")
    pg2 = await ctx.new_page(); await pg2.goto('http://localhost:%d/novel.html?fast=1' % PORT); await pg2.wait_for_function("!document.getElementById('tNew').disabled", timeout=20000)
    check('기본 닉 = 디스코드 닉', await pg2.input_value('#nickIn') == '디코 닉', await pg2.input_value('#nickIn'))
    await ctx.close()
    # ---- 4) 화자·@show 대조
    files = sorted(glob.glob(os.path.join(ROOT, 'data/novel/ch/ch_*.txt')), key=nb.file_key)
    story, c, _ = nb.build(files, True)
    check('빌드 --strict 오류 0', not c.errors and not c.warns, (c.errors + c.warns)[:3])
    names = sorted({o['s'] for o in story['ops'] if o['o'] == 'say'} - {'{PLAYER}'})
    ctx, pg, errs = await newpage(b)
    res = await pg.evaluate("(n)=>n.map(x=>[x,!!__novel.charOf(x)])", names)
    miss = [x for x, ok in res if not ok]
    check('말하는 이름 전부 캐릭터에 연결(브장신 제외)', miss == ['브장신'], miss)
    man = json.load(open(os.path.join(ROOT, 'img/novel/manifest.json')))
    ids = sorted({x['id'] for o in story['ops'] if o['o'] == 'show' for x in o['ids']})
    check('@show id 전부 manifest 에 있음', all(i in man['ch'] and os.path.exists(os.path.join(ROOT, 'img/novel/ch_%s.webp' % i)) for i in ids), [i for i in ids if i not in man['ch']])
    check('CG 파일 6장', all(os.path.exists(os.path.join(ROOT, 'img/novel/cg/%s.webp' % i)) for i in nb.CGS))
    # ---- 5) 엔딩 경로
    for name, (rl, ee, fl) in PATHS.items():
        await ctx.close(); ctx, pg, errs = await newpage(b)
        await start(pg)
        log = await pg.evaluate(DRIVE, rl)
        check('경로 [%s] → %s' % (name, ee), log.get('end') == ee and (log['flags']['F1'], log['flags']['F2'], log['flags']['F3']) == fl, log)
        if name == 'end4 몫(F2·F3 참)':
            check('end4: @rec LAST=share 와 END4_OK 기록', log['flags']['LAST'] == 'share' and log['flags']['OK'] == 1, log['flags'])
            check('CG 3장(낙찰표·빈자리·입력중)이 이 경로에서 나옴', [x.split('/')[-1] for x in log['cg']] == ['bid.webp', 'lobby.webp', 'typing.webp'], log['cg'])
        if name == 'end1 몫': check('end1 CG: 낙찰표·빈자리·클립', [x.split('/')[-1] for x in log['cg']] == ['bid.webp', 'lobby.webp', 'clip.webp'], log['cg'])
        if name == 'end2 가볍게': check('end2 CG: 정류장', log['cg'][-1].endswith('stop.webp'), log['cg'])
        if name == 'end3 탓하세요': check('end3 CG: 방 인원 5→4', log['cg'][-1].endswith('room.webp'), log['cg'])
        check('  [%s] 엔딩 끝에 @credits 가 한 번 나옴' % name, log.get('cred') == 1, log.get('cred'))
        check('  [%s] 스크립트 오류 없음' % name, not errs, errs[:2])
        g = await pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('sq_novel2_end')||'{}'))")
        check('  [%s] 엔딩 기록 저장' % name, g == [ee], g)
    # 도감
    await pg.evaluate("__novel.goTitle()"); await pg.click('#tGal'); txt = await pg.inner_text('#gal')
    check('도감: 본 엔딩은 이름, 나머지는 ???', '???' in txt, txt)
    # ---- 6) 주인공 초상 없음 · 이름표 닉
    await ctx.close(); ctx, pg, errs = await newpage(b); await start(pg, 'Kim7')
    seen = {'me': 0, 'bad': 0}
    for i in range(3000):
        m = await pg.evaluate("__novel.mode()")
        if m['ws'] == 'line':
            op = await pg.evaluate("(()=>{const o=__novel.STORY.ops[__novel.ST().pc];return o?[o.o,o.s,o.k||0]:null})()")
            if op and op[1] == '{PLAYER}':
                nm = await pg.inner_text('#name'); on = await pg.evaluate("[...document.querySelectorAll('#chars .ch.on')].length")
                imgs = await pg.evaluate("[...document.querySelectorAll('#chars img')].map(i=>i.alt)")
                seen['me'] += 1
                if nm != 'Kim7' or on or 'Kim7' in imgs: seen['bad'] += 1
                if seen['me'] >= 12: break
            await pg.evaluate("__novel.advance()")
        elif m['ws'] == 'choice': await pg.evaluate("__novel.choose(0)")
        elif m['ws'] == 'cg': await pg.evaluate("__novel.closeCg()")
        await pg.wait_for_timeout(2)
    check('주인공 말풍선: 이름표=닉·말하는 초상 없음(12줄)', seen['me'] >= 12 and seen['bad'] == 0, seen)
    # ---- 7) 저장 후 복귀·새로고침
    st = await pg.evaluate("({pc:__novel.ST().pc, t:__novel.mode().text, nick:__novel.nick.get()})")
    store = await ctx.storage_state()
    ctx2, pg2, e2 = await newpage(b, store=store)
    check('새로고침 뒤 닉 유지', await pg2.input_value('#nickIn') == 'Kim7')
    check('이어하기 활성', not await pg2.evaluate("document.getElementById('tCont').disabled"))
    await pg2.click('#tCont'); await pg2.wait_for_function("__novel.mode().ws!=='title'")
    for _ in range(30):
        m = await pg2.evaluate("__novel.mode()")
        if m['ws'] == 'line': break
        await pg2.wait_for_timeout(50)
    check('이어하기: 저장한 줄로 복귀', (await pg2.evaluate("__novel.mode()"))['pc'] == st['pc'] or (await pg2.evaluate("__novel.mode().text")) == st['t'], st)
    # 슬롯 저장·불러오기
    await pg2.evaluate("__novel.goTitle()"); await pg2.evaluate("document.getElementById('tCont').click()"); await pg2.wait_for_timeout(200)
    await pg2.click('#bMenu'); await pg2.click('#mSave'); await pg2.click('#slList .slot >> nth=0'); await pg2.wait_for_timeout(100)
    sl = await pg2.evaluate("JSON.parse(localStorage.getItem('sq_novel2_slots')||'[]')[0]")
    check('슬롯 저장(닉 포함)', bool(sl) and sl.get('nick') == 'Kim7', sl and sl.get('nick'))
    # 이름 바꾸기(메뉴)
    await pg2.click('#bMenu') if await pg2.evaluate("!document.getElementById('ovMenu').classList.contains('on')") else None
    await pg2.click('#mNick'); await pg2.fill('#nickIn2', '새 이름'); await pg2.click('#nickOk'); await pg2.wait_for_timeout(100)
    check('이름 바꾸기 → 저장·즉시 반영', await pg2.evaluate("__novel.nick.get()") == '새 이름' and await pg2.evaluate("JSON.parse(localStorage.getItem('sq_novel2_nick'))") == '새 이름')
    await pg2.click('#mNick') if await pg2.evaluate("document.getElementById('ovMenu').classList.contains('on')") else None
    # 옛 버전 세이브는 버린다
    await ctx2.close()
    ctx3 = await b.new_context(viewport={'width': 412, 'height': 860}); await ctx3.add_init_script("localStorage.setItem('sq_novel2_last',JSON.stringify({pc:5,V:{},clues:[],bg:'white',show:null,mood:'none',play:3,ts:1,sv:'775:11',ch:0}))")
    pg3 = await ctx3.new_page(); await pg3.goto('http://localhost:%d/novel.html?fast=1' % PORT); await pg3.wait_for_function("!document.getElementById('tNew').disabled", timeout=20000)
    check('옛 원고 이어하기는 비활성(SV 불일치)', await pg3.evaluate("document.getElementById('tCont').disabled"))
    check('SV 는 봇 규칙(숫자·:)을 지킨다', re.match(r'^[0-9:]{1,24}$', await pg3.evaluate("__novel.sy.SV")) is not None, await pg3.evaluate("__novel.sy.SV"))
    await ctx3.close(); await ctx.close()
    # ---- 8) CG 확대(핀치·더블탭·드래그) · 크레딧
    await ctx.close(); ctx, pg, errs = await newpage(b); await start(pg)
    for _ in range(4000):
        m = await pg.evaluate("__novel.mode()")
        if m['ws'] == 'cg': break
        if m['ws'] == 'line': await pg.evaluate("__novel.advance()")
        elif m['ws'] == 'choice': await pg.evaluate("__novel.choose(0)")
        await pg.wait_for_timeout(1)
    await pg.wait_for_timeout(1100)
    ws = lambda: pg.evaluate("__novel.mode().ws")
    z = lambda: pg.evaluate("__novel.cgz()")
    check('CG1 낙찰표 2560 원본', await pg.evaluate("document.getElementById('cgImg').naturalWidth") == 2560)
    await pg.mouse.dblclick(206, 430); await pg.wait_for_timeout(500)
    check('더블탭 확대(닫히지 않음)', (await z())['s'] > 2.5 and await ws() == 'cg', await z())
    x0 = (await z())['x']
    await pg.mouse.move(250, 430); await pg.mouse.down(); await pg.mouse.move(150, 430, steps=6); await pg.mouse.up(); await pg.wait_for_timeout(500)
    check('확대 중 드래그 = 이동, 닫히지 않음', (await z())['x'] != x0 and await ws() == 'cg', await z())
    await pg.mouse.click(206, 430); await pg.wait_for_timeout(700)
    check('확대 중 한 번 탭은 넘어가지 않음', await ws() == 'cg')
    await pg.mouse.dblclick(206, 430); await pg.wait_for_timeout(500)
    check('더블탭으로 원래 크기', (await z())['s'] == 1 and await ws() == 'cg', await z())
    await pg.evaluate("""()=>{const b=document.getElementById('cg');const ev=(t,id,x,y)=>b.dispatchEvent(new PointerEvent(t,{pointerId:id,clientX:x,clientY:y,bubbles:true,pointerType:'touch'}));
      ev('pointerdown',1,180,430);ev('pointerdown',2,230,430);ev('pointermove',1,120,430);ev('pointermove',2,290,430);ev('pointerup',2,290,430);ev('pointerup',1,120,430)}""")
    await pg.wait_for_timeout(500)
    check('핀치 확대(닫히지 않음)', (await z())['s'] > 2 and await ws() == 'cg', await z())
    await pg.click('#cgRst'); await pg.wait_for_timeout(100)
    check('↺ 버튼으로 원래 크기', (await z())['s'] == 1)
    await pg.mouse.click(206, 430); await pg.wait_for_timeout(900)
    check('확대 안 한 한 번 탭은 CG 를 닫고 다음 줄로', await ws() == 'line')
    # 크레딧: 엔딩 카드에서 선택적으로
    await pg.evaluate("__novel.goTitle()"); await ctx.close(); ctx, pg, errs = await newpage(b); await start(pg)
    log = await pg.evaluate(DRIVE, PATHS['end1 몫'][0])
    check('크레딧: 엔딩 카드에 버튼(목록 있음)', await pg.evaluate("getComputedStyle(document.getElementById('eCred')).display")!='none')
    await pg.click('#eCred'); await pg.wait_for_timeout(300)
    t = await pg.inner_text('#credRoll')
    check('크레딧 화면: 본 명단 41명 + 소제목, 건너뛰기', all(n in t for n in ['Da capo', '현타온덕현하콩', '승수', '겨 울']) and t.count('\n')>40 and await pg.is_visible('#credSkip'), t[:80])
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); await pg.screenshot(path=os.path.join(SHOTS, '10_출연진_크레딧.png'))
    await pg.click('#credSkip'); await pg.wait_for_timeout(100)
    check('건너뛰기 → 엔딩 카드로 복귀(이야기 불변)', await pg.evaluate("document.getElementById('endcard').classList.contains('on')&&__novel.mode().ws==='end'"))
    await ctx.close()
    if SHOTS: await shots(b)

async def shots(b):
    os.makedirs(SHOTS, exist_ok=True); H = lambda n: os.path.join(SHOTS, n)
    ctx, pg, errs = await newpage(b)
    await pg.fill('#nickIn', '민준'); await pg.wait_for_timeout(300); await pg.screenshot(path=H('01_시작_닉네임.png'))
    await pg.fill('#nickIn', '<<>>'); await pg.click('#tNew'); await pg.wait_for_timeout(200); await pg.screenshot(path=H('01b_닉네임_오류.png'))
    await pg.fill('#nickIn', '민준'); await pg.click('#tNew')
    want = {'kakao': False, 'voice': False, 'choice': False, 'cg': False}
    for i in range(4000):
        m = await pg.evaluate("__novel.mode()"); bg = await pg.evaluate("__novel.ST().bg")
        if m['ws'] == 'line':
            if bg == 'kakao' and not want['kakao'] and await pg.evaluate("document.getElementById('kchat').children.length>=4&&document.getElementById('box').classList.contains('kk')"):
                await pg.wait_for_timeout(150); await pg.screenshot(path=H('02_톡_장면.png')); want['kakao'] = True
            if bg == 'voice' and not want['voice'] and m['pc'] > 120:
                await pg.wait_for_timeout(500); await pg.screenshot(path=H('03_음성_장면.png')); want['voice'] = True
            await pg.evaluate("__novel.advance()")
        elif m['ws'] == 'choice':
            if not want['choice']: await pg.wait_for_timeout(200); await pg.screenshot(path=H('04_선택지.png')); want['choice'] = True
            await pg.evaluate("__novel.choose(0)")
        elif m['ws'] == 'cg':
            if not want.get('cg'): await pg.wait_for_timeout(1200); await pg.screenshot(path=H('05_CG_낙찰표.png')); want['cg'] = True
            await pg.evaluate("__novel.closeCg()")
            if all(want.values()): break
        await pg.wait_for_timeout(2)
    await ctx.close()
    for name, key in (('06_엔딩1_몫', 'end1 몫'), ('07_엔딩2_가볍게', 'end2 가볍게'), ('08_엔딩3_탓하세요', 'end3 탓하세요'), ('09_엔딩4_제잘못이네요', 'end4 몫(F2·F3 참)')):
        ctx, pg, errs = await newpage(b); await start(pg); rl = PATHS[key][0]; ri = 0; shot_last = False; cred_shot = False
        for i in range(60000):
            m = await pg.evaluate("__novel.mode()")
            if await pg.evaluate("document.getElementById('ovCred').classList.contains('on')"):
                if not cred_shot: await pg.wait_for_timeout(900); await pg.screenshot(path=H(name + '_크레딧.png')); cred_shot = True
                await pg.evaluate("document.getElementById('credSkip').click()"); continue
            if m['ws'] == 'end':
                await pg.wait_for_timeout(500); await pg.screenshot(path=H(name + '_카드.png')); break
            if m['ws'] == 'line':
                if m['pc'] > 0 and await pg.evaluate("(()=>{const o=__novel.STORY.ops;let k=__novel.ST().pc+1;return o[k]&&(o[k].o==='credits')})()"):
                    await pg.wait_for_timeout(200); await pg.screenshot(path=H(name + '_마지막장면.png'))
                await pg.evaluate("__novel.advance()")
            elif m['ws'] == 'choice':
                r = rl[ri] if ri < len(rl) else None; ri += 1; j = next((k for k, t in enumerate(m['opts']) if r and r in t), 0); await pg.evaluate("__novel.choose(%d)" % j)
            elif m['ws'] == 'cg':
                if name.startswith('0') and not shot_last and (await pg.evaluate("__novel.mode().ch")) == 7:
                    await pg.wait_for_timeout(1200); await pg.screenshot(path=H(name + '_CG.png')); shot_last = True
                await pg.evaluate("__novel.closeCg()")
            await pg.wait_for_timeout(1)
        await ctx.close()

if __name__ == '__main__': sys.exit(asyncio.run(main()))
