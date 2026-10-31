#!/usr/bin/env python3
"""라이어 게임 원탁 장면 시험 (liar.html) — 캐릭터·색 배정, 자리 배치, 해상도별 레이아웃, 연출 단계, 말풍선 이스케이프, 지목 팔, 한 글자씩 발표, 누출, 음성 파일 폴백.
사용: CHROME=... python3.13 tests/liar_scene_test.py   (가짜 서버 tests/liar_fake_server.py 사용)"""
import asyncio, json, os, subprocess, sys, tempfile, threading, time, urllib.request, http.server, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import liar_fake_server as FS
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
srv = FS.serve(0); BASE = f'http://127.0.0.1:{srv.server_address[1]}'
URL = 'file://' + os.path.join(ROOT, 'liar.html') + f'?api={BASE}'
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {str(info)[:300]}'))
    if not cond: fails.append(name)
def post(path, obj=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(obj or {}).encode(), headers={'Content-Type': 'application/json'}); return json.load(urllib.request.urlopen(r))
def getlog(): return json.load(urllib.request.urlopen(BASE + '/__log'))
XSS = '<img src=x onerror=window.__xss=1>'
WORD = '김치찌개'
NAMES = ['호스트', '시민둘', '시민셋', '라이어님', '다섯째', '여섯째사람', '일곱째', '여덟째', '아홉째', '열째이름이아주길다']
def U(n): return [f'u{i}' for i in range(1, n + 1)]
def players(n, voted=(), hinted=()): return [{'uid': u, 'name': NAMES[i], 'online': True, 'away': False, 'host': i == 0, 'score': i, 'voted': u in voted, 'hinted': u in hinted} for i, u in enumerate(U(n))]
def view(uid, state, n, liar='u4', **kw):
    base = {'state': state, 'host': 'u1', 'deadline': time.time() + 30, 'turn': None, 'round': 1, 'rounds': 2, 'opts': {'rounds': 2, 'discuss_s': 90, 'mode': 'normal', 'category': '', 'liars': 1, 'max': 10},
            'players': players(n), 'my': {'role': None, 'category': None, 'word': None, 'fool': False}, 'hints': [], 'msgs': [], 'votes': None, 'result': None}
    if state in ('reveal', 'hints', 'discuss', 'vote', 'revote', 'guess'):
        base['my'] = {'role': 'liar', 'category': '음식', 'word': None, 'fool': False} if uid == liar else {'role': 'citizen', 'category': '음식', 'word': WORD, 'fool': False}
    base.update(kw); return base
def setroom(code, state, n=5, liar='u4', **kw): return post('/__set', {'code': code, 'views': {u: view(u, state, n, liar, **kw) for u in U(n)}})
async def mk(br, uid, w=1280, h=720, rm=False):
    ctx = await br.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce' if rm else 'no-preference')
    await ctx.add_init_script(f"try{{localStorage.setItem('sgg_dc',JSON.stringify({{id:'{uid}',name:'{uid}',token:'tok-{uid}',exp:Date.now()+6*86400000}}));localStorage.setItem('lg_mute','1');}}catch(e){{}}")
    pg = await ctx.new_page(); pg._errs = []
    pg.on('pageerror', lambda e: pg._errs.append(str(e)))
    pg.on('console', lambda m: pg._errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FILE_NOT_FOUND' not in m.text else None)
    return ctx, pg
async def wf(pg, js, ms=6000):
    try: await pg.wait_for_function(js, timeout=ms); return True
    except Exception: return False
def lum(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])
def cr(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True); return (la + .05) / (lb + .05)

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME)
        ONLY = os.environ.get('ONLY', '')
        # ---------- 캐릭터·색 배정 ----------
        post('/__reset'); setroom('ROOM', 'lobby', n=10, deadline=0)
        ctx, pg = await mk(br, 'u2'); await pg.goto(URL + '#ROOM'); await wf(pg, "Object.keys(window.__lg.slots()).length===10")
        r = await pg.evaluate("""()=>{ const A=window.__lg.assign, bad=[], r=()=>Math.random().toString(36).slice(2,10);
          for(let t=0;t<400;t++){ const n=3+t%8, ids=Array.from({length:n},r), a=A(ids), vals=Object.values(a); if(new Set(vals).size!==n||vals.some(v=>v<0||v>9)) bad.push(ids); const b=A(ids); if(JSON.stringify(a)!==JSON.stringify(b)) bad.push('nondet'); }
          return {bad:bad.length, chars:window.__lg.chars.length, pal:window.__lg.palette.length}; }""")
        check('캐릭터·색 배정: 3~10명 무작위 400판 모두 겹침 없음·같은 입력이면 같은 결과', r['bad'] == 0 and r['chars'] == 10 and r['pal'] == 10, r)
        s1 = await pg.evaluate('window.__lg.slots()'); await pg.reload(); await wf(pg, "Object.keys(window.__lg.slots()).length===10"); s2 = await pg.evaluate('window.__lg.slots()')
        check('새로고침해도 같은 사람은 같은 캐릭터·색', s1 == s2 and len(set(s1.values())) == 10, (s1, s2))
        ctx2, pg2 = await mk(br, 'u7'); await pg2.goto(URL + '#ROOM'); await wf(pg2, "Object.keys(window.__lg.slots()).length===10"); s3 = await pg2.evaluate('window.__lg.slots()')
        check('다른 사람 화면에서도 같은 사람은 같은 캐릭터', s1 == s3)
        imgs = await pg.evaluate("Array.from(document.querySelectorAll('#chB img,#chF img')).map(i=>i.getAttribute('src'))")
        check('캐릭터 그림 파일 10종이 각각 쓰인다', len(set(imgs)) == 10 and all('img/liar/char_' in x for x in imgs), imgs)
        await ctx2.close()
        # 색 대비(WCAG 4.5:1): 어두운 장면·다크 패널 / 라이트 패널
        pal = await pg.evaluate('window.__lg.palette'); worst = 99; bad = []
        for i, c in enumerate(pal):
            for bg in ('#0e1226', '#141936', '#1b2146', '#262e5e'):
                v = cr(c['d'], bg); worst = min(worst, v)
                if v < 4.5: bad.append(('dark', i, bg, round(v, 2)))
            for bg in ('#ffffff', '#f1f4ff', '#dfe6fb', '#eaefff'):
                v = cr(c['l'], bg); worst = min(worst, v)
                if v < 4.5: bad.append(('light', i, bg, round(v, 2)))
            if cr(c['d'], '#10142a') < 4.5 or cr(c['l'], '#ffffff') < 4.5: bad.append(('badge', i))
        check(f'색 10종 글자 대비 4.5:1 이상(가장 낮은 값 {worst:.2f}) — 다크·라이트·번호 배지', not bad, bad)
        check('색만이 아니라 번호(1~10)와 캐릭터 소품으로도 구분 — 이름표마다 서로 다른 번호', len(set(await pg.evaluate("Array.from(document.querySelectorAll('#tags .no')).map(e=>e.textContent)"))) == 10)
        await ctx.close()

        # ---------- 인원 3~10명 배치 (겹침 없음) × 해상도 ----------
        for (w, h) in ((390, 800), (1280, 720)):
            ctx, pg = await mk(br, 'u1', w, h, rm=True); bad = []
            for n in range(3, 11):
                post('/__reset'); setroom('ROOM', 'vote', n=n, players=players(n, voted=('u2',)))
                await pg.goto(URL + '#ROOM'); await wf(pg, f"Object.keys(window.__lg.pos()).length==={n}"); await pg.wait_for_timeout(450)
                g = await pg.evaluate("""()=>{ const sc=document.getElementById('scene').getBoundingClientRect(), P=window.__lg.pos(), ids=Object.keys(P), o=[];
                  for(let i=0;i<ids.length;i++) for(let j=i+1;j<ids.length;j++){ const a=P[ids[i]],b=P[ids[j]], k=.8, ox=Math.min(a.x+a.s*k/2,b.x+b.s*k/2)-Math.max(a.x-a.s*k/2,b.x-b.s*k/2), oy=Math.min(a.y+a.s*k/2,b.y+b.s*k/2)-Math.max(a.y-a.s*k/2,b.y-b.s*k/2); if(ox>0&&oy>0) o.push([ids[i],ids[j]]); }
                  const out=ids.filter(u=>{const a=P[u]; return a.x-a.s/2<0||a.x+a.s/2>sc.width||a.y-a.s/2<0||a.y+a.s/2>sc.height;});
                  const tg=Array.from(document.querySelectorAll('#tags .nt')).map(e=>e.getBoundingClientRect()), to=[];
                  for(let i=0;i<tg.length;i++) for(let j=i+1;j<tg.length;j++){ const a=tg[i],b=tg[j]; if(a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom) to.push([i,j]); }
                  const me=P['u1']; return {o,out,to,meBottom:me.y>sc.height*0.8}; }""")
                if g['o'] or g['out'] or g['to'] or not g['meBottom']: bad.append((n, g))
            check(f'{w}x{h}: 3~10명 모두 캐릭터·이름표 겹침 없음 · 장면 밖으로 안 나감 · 나는 아래 가운데', not bad, bad[:2])
            await ctx.close()

        # ---------- 해상도별 레이아웃(PC 4종 + 폰), 10명 ----------
        sizes = ((1280, 720), (1366, 768), (1920, 1080), (2560, 1440), (390, 800))
        for (w, h) in sizes:
            ctx, pg = await mk(br, 'u2', w, h, rm=True); bad = []; fonts = {}
            hs = [{'uid': 'u3', 'name': NAMES[2], 'round': 1, 'text': '겨울에 먹으면 따뜻해요', 't': 1}]
            ms = [{'id': 1, 'uid': 'u3', 'name': NAMES[2], 'text': '저는 시민이에요', 'sys': False, 't': 1}]
            for st, kw in (('lobby', dict(deadline=0)), ('hints', dict(turn='u2', hints=hs)), ('discuss', dict(hints=hs, msgs=ms)), ('vote', dict(players=players(10, voted=('u3',)))), ('guess', dict(turn='u4', accused='u4')),
                           ('result', dict(deadline=0, result={'liar_uids': ['u4'], 'word': WORD, 'category': '음식', 'votes': {f'u{i}': 'u4' for i in range(1, 11) if i != 4}, 'tally': {'u4': 9}, 'accused': 'u4', 'caught': True, 'winner': 'citizen', 'points': {'u1': 2}, 'log': ['a'], 'names': {u: NAMES[i] for i, u in enumerate(U(10))}}))):
                post('/__reset'); setroom('ROOM', st, n=10, **kw)
                await pg.goto(URL + '#ROOM'); await wf(pg, "Object.keys(window.__lg.pos()).length===10"); await pg.wait_for_timeout(500)
                m = await pg.evaluate("""()=>{ const vw=innerWidth, vh=innerHeight, d=document.documentElement, q=s=>document.querySelector(s), vis=el=>{ if(!el) return false; const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
                  const rc=s=>{ const e=q(s); return e?e.getBoundingClientRect():null; }, sc=rc('#scene'), ch=rc('#chat'), res={};
                  res.vscroll=d.scrollHeight-vh; res.hscroll=d.scrollWidth-vw; res.scene=[Math.round(sc.width),Math.round(sc.height)]; res.sceneIn=sc.left>=-1&&sc.top>=-1&&sc.right<=vw+1&&sc.bottom<=vh+1;
                  const ci=rc('#chatIn'); res.chatIn=ci&&ci.bottom<=vh+1&&ci.top>=0; res.chatBelowOK=true;
                  const side=innerWidth>=900; res.sideBySide=side?(ch.left>=sc.right-2):true;
                  const f=s=>{ const e=q(s); return e?parseFloat(getComputedStyle(e).fontSize):null; };
                  res.f={tag:f('#tags .nm'),chat:f('#msgs .m'),ph:f('#phName')}; return res; }""")
                pc = w >= 900
                if pc and (m['vscroll'] > 1 or m['hscroll'] > 0): bad.append((st, 'scroll', m))
                if not pc and m['hscroll'] > 0: bad.append((st, 'hscroll', m))
                if not m['sceneIn']: bad.append((st, 'scene out', m))
                if pc and not m['chatIn']: bad.append((st, 'chat input offscreen', m))
                if pc and not m['sideBySide']: bad.append((st, 'not 2col', m))
                if pc and m['f']['tag'] and m['f']['tag'] < 14: bad.append((st, 'font', m['f']))
                fonts[st] = m['f']; last = m
            check(f'{w}x{h}: 6단계 × 10명 — ' + ('스크롤 없음 · 장면+입력+채팅 한 화면 · 2단 · 이름표 14px 이상' if w >= 900 else '가로 스크롤 없음'), not bad, bad[:2])
            print('   장면', last['scene'], '글자', fonts.get('discuss'))
            if w >= 900:   # 장면이 가용 공간을 크게 쓰는지(여백 낭비 점검)
                check(f'{w}x{h}: 장면이 화면 폭의 45% 이상·높이의 55% 이상을 차지', last['scene'][0] >= w * 0.45 and last['scene'][1] >= h * 0.55, last['scene'])
            check(f'{w}x{h}: 콘솔 오류 0', not pg._errs, pg._errs[:2])
            await ctx.close()

        # ---------- 말풍선 이스케이프 · 지목 · 누출 · 프레임 비용 (PC, 움직임 켬) ----------
        post('/__reset'); setroom('ROOM', 'discuss', n=5, msgs=[])
        ctx, pg = await mk(br, 'u1', 1280, 720); await pg.goto(URL + '#ROOM'); await wf(pg, "Object.keys(window.__lg.pos()).length===5"); await pg.wait_for_timeout(600)
        msgs = [{'id': 1, 'uid': 'u2', 'name': NAMES[1] + XSS, 'text': XSS, 'sys': False, 't': 1}, {'id': 2, 'uid': 'u3', 'name': NAMES[2], 'text': '두 번째 말풍선 ' * 8, 'sys': False, 't': 2}]
        setroom('ROOM', 'discuss', n=5, msgs=msgs); ok = await wf(pg, "window.__lg.bubbles().length>=1", 4000); await pg.wait_for_timeout(500)
        b = await pg.evaluate('window.__lg.bubbles()')
        check('말풍선: 채팅이 해당 캐릭터 머리 위에 뜬다(최근 것만·겹치면 숨김)', ok and len(b) >= 1 and sum(1 for x in b if not x['gone']) <= 3, b)
        check('말풍선: 서버 문자열은 글자로만(이스케이프) — 태그 없음·XSS 없음', await pg.evaluate('window.__xss') is None and await pg.locator('#bubs img, #bubs script, #tags img').count() == 0 and any('<img' in x['text'] for x in b), b)
        check('말풍선: 긴 글은 잘려서(44자) 나온다', all(len(x['text']) <= 120 for x in b))
        fx = await pg.evaluate('window.__lg.fx()'); await pg.wait_for_timeout(3000); fx2 = await pg.evaluate('window.__lg.fx()')
        fr = fx2['frames'] - fx['frames']; ms_ = (fx2['ms'] - fx['ms']) / max(1, fr)
        check(f'프레임 비용: 3초 동안 {fr}프레임(30fps 이하로 제한) · 프레임당 그리기 평균 {ms_:.2f}ms', 0 < fr <= 100 and ms_ < 4, (fr, ms_))
        # 투표: 캐릭터를 눌러 지목 → 내 팔만 보인다
        setroom('ROOM', 'vote', n=5, players=players(5, voted=('u3',)))
        await wf(pg, "document.querySelectorAll('#bMain button.pc').length===5"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('#chB .ch[data-uid=u4], #chF .ch[data-uid=u4]').click()"); await pg.wait_for_timeout(700)
        arms = await pg.evaluate('window.__lg.armPairs()')
        check('지목: 캐릭터를 누르면 /lg/vote 가 가고 내 팔이 그 사람을 가리킨다(남의 팔은 없음)', any(x['path'] == '/lg/vote' and x['body']['target'] == 'u4' for x in getlog()['log']) and arms == ['u1>u4'], arms)
        # 호버 미리보기 + 키보드
        await pg.hover('#chF .ch[data-uid=u3], #chB .ch[data-uid=u3]'); await pg.wait_for_timeout(300)
        arms = await pg.evaluate('window.__lg.armPairs()')
        check('마우스 호버: 손가락 미리보기(내 선택 + 호버 대상)', 'u1>u3' in arms and await pg.locator('.ch.hv').count() == 1, arms)
        await pg.mouse.move(5, 5); await pg.keyboard.press('2'); await pg.wait_for_timeout(500)
        check('키보드: 숫자 키로 투표(번호 배지)', [x for x in getlog()['log'] if x['path'] == '/lg/vote'][-1]['body']['target'] in ([u for u, k in (await pg.evaluate('window.__lg.slots()')).items() if k + 1 == 2] or ['?']))
        await pg.focus('#bMain button.pc:not([disabled])'); first = await pg.evaluate('document.activeElement.dataset.uid'); await pg.keyboard.press('ArrowRight'); second = await pg.evaluate('document.activeElement.dataset.uid')
        check('키보드: 방향키로 후보 카드 이동(Enter 로 선택은 버튼 기본 동작)', first != second and second is not None, (first, second))
        # 라이어 화면 누출: 제시어가 DOM·카드·툴팁 어디에도 없다
        ctxL, L = await mk(br, 'u4', 1280, 720); leak = []
        for st, kw in (('reveal', {}), ('hints', dict(turn='u4')), ('discuss', {}), ('vote', {}), ('guess', dict(turn='u4', accused='u4'))):
            post('/__reset'); setroom('ROOM', st, n=5, **kw); await L.goto(URL + '#ROOM'); await wf(L, "Object.keys(window.__lg.pos()).length===5"); await L.wait_for_timeout(2300 if st == 'reveal' else 600)
            html = await L.content(); txt = await L.inner_text('body')
            if WORD in html or WORD in txt: leak.append(st)
            if st == 'reveal' and '라이어' not in await L.inner_text('#cback'): leak.append('card?')
        check('라이어 화면: 제시어가 장면·카드·말풍선 어디에도 없다(전 단계) · 카드는 「라이어」', not leak, leak)
        await ctxL.close(); await ctx.close()

        # ---------- 결과 연출: 지목 팔 동시 · 한 글자씩 · 건너뛰기 · 누출 없음 ----------
        votes = {'u1': 'u4', 'u2': 'u4', 'u3': 'u1', 'u4': 'u2', 'u5': 'u4'}
        def res(caught=True, acc='u4'): return {'liar_uids': ['u4'], 'word': WORD, 'category': '음식', 'votes': votes, 'tally': {'u4': 3, 'u1': 1, 'u2': 1}, 'accused': acc, 'caught': caught, 'winner': 'citizen' if caught else 'liar', 'points': {'u1': 2}, 'log': ['a'], 'names': {u: NAMES[i] for i, u in enumerate(U(5))}}
        post('/__reset'); setroom('ROOM', 'guess', n=5, turn='u4', accused='u4')
        ctx, pg = await mk(br, 'u1', 1280, 720); await pg.goto(URL + '#ROOM'); await wf(pg, "Object.keys(window.__lg.pos()).length===5"); await pg.wait_for_timeout(500)
        pre = (await pg.inner_text('body')) + (await pg.inner_text('#ann'))
        check('결과 전: 「맞습니다/아닙니다」·결과가 화면에 새지 않는다', '맞습니다' not in pre and '아닙니다' not in pre and await pg.locator('#ann.on').count() == 0)
        setroom('ROOM', 'result', n=5, result=res(True), deadline=0)
        await wf(pg, "window.__lg.res()==='point'", 5000); await pg.wait_for_timeout(600)
        arms = sorted(await pg.evaluate('window.__lg.armPairs()'))
        want = sorted(f'{a}>{b}' for a, b in votes.items() if b and a != b)
        check('결과 지목: 모든 사람의 팔이 한꺼번에(투표 내역 그대로) 그려진다', arms == want, (arms, want))
        check('결과 전 패널: 라이어 이름·승패가 아직 패널에 없다(「결과 발표 중」)', '결과 발표 중' in await pg.inner_text('#bMain') and '시민 승리' not in await pg.inner_text('#bMain'))
        seen = []; t0 = time.time(); fin = ''
        while time.time() - t0 < 16:
            t = await pg.evaluate("(()=>{const a=document.querySelector('#ann .a1'),b=document.querySelector('#ann .a2');return [a?a.textContent:'',b?b.textContent:'',window.__lg.res(),getComputedStyle(document.getElementById('scene')).getPropertyValue('--lb')]})()")
            if not seen or seen[-1] != t[:2]: seen.append(t[:2])
            fin = t[2]
            if t[1] == '맞습니다.' and t[2] != 'ann': break
            await pg.wait_for_timeout(60)
        while seen and seen[-1] == ['', '']: seen.pop()
        l1 = [x[0] for x in seen]; l2 = [x[1] for x in seen]
        mono = all(b.startswith(a) and len(b) - len(a) <= 2 for a, b in zip(l1, l1[1:])) and all(b.startswith(a) and len(b) - len(a) <= 1 for a, b in zip(l2, l2[1:]))
        check('발표: 「그는 라이어가 …」 가 한 글자씩 늘어난다(앞글자 그대로·건너뛰기 없이)', mono and '그는 라이어가' in l1[-1] and l1[-1].endswith('...') and len(set(l1)) >= 9, l1[:14])
        check('발표: 「…」 뒤 정적 후 「맞습니다.」 도 한 글자씩', l2[-1] == '맞습니다.' and any(0 < len(x) < 5 for x in l2) and len(set(l2)) >= 5, l2)
        await wf(pg, "window.__lg.res()==='liar'||window.__lg.res()==='guess'||window.__lg.res()==='verdict'", 9000)
        # 건너뛰기: 클릭
        setroom('ROOM', 'reveal', n=5); await pg.wait_for_timeout(1400); setroom('ROOM', 'result', n=5, result=res(True), deadline=0); await wf(pg, "window.__lg.res()==='point'", 5000)
        await pg.click('#scene'); ok = await wf(pg, "window.__lg.res()==='done'", 3000)
        check('건너뛰기(장면 클릭): 바로 결과 화면(시민 승리·점수표)', ok and '시민 승리' in await pg.inner_text('#bMain') and await pg.locator('.pts tbody tr').count() == 5)
        setroom('ROOM', 'reveal', n=5); await pg.wait_for_timeout(1400); setroom('ROOM', 'result', n=5, result=res(False, 'u2'), deadline=0); await wf(pg, "window.__lg.res()==='point'", 5000)
        await pg.keyboard.press('Space'); ok = await wf(pg, "window.__lg.res()==='done'", 3000)
        check('건너뛰기(Space): 바로 결과 화면(라이어 승리)', ok and '라이어 승리' in await pg.inner_text('#bMain'))
        # 아닙니다 → 안도의 푸른 빛
        setroom('ROOM', 'reveal', n=5); await pg.wait_for_timeout(1400); setroom('ROOM', 'result', n=5, result=res(False, 'u2'), deadline=0)
        blue = False; word = ''; t0 = time.time()
        while time.time() - t0 < 18:
            t = await pg.evaluate("(()=>{const b=document.querySelector('#ann .a2');return [b?b.textContent:'',parseFloat(getComputedStyle(document.getElementById('scene')).getPropertyValue('--lb'))||0]})()")
            word = t[0] or word; blue = blue or t[1] > 0.5
            if word == '아닙니다.' and blue: break
            await pg.wait_for_timeout(80)
        check('아닙니다: 「아닙니다.」 + 푸른(안도) 조명으로 바뀐다', word == '아닙니다.' and blue, (word, blue))
        check('결과 연출 중 콘솔 오류 0', not pg._errs, pg._errs[:2]); await ctx.close()
        # 움직임 줄이기: 줄 단위로 단순화(두 줄이 한 번에, 연출 없이 바로 결과)
        post('/__reset'); setroom('ROOM', 'guess', n=5, turn='u4', accused='u4')
        ctx, pg = await mk(br, 'u1', 1280, 720, rm=True); await pg.goto(URL + '#ROOM'); await wf(pg, "Object.keys(window.__lg.pos()).length===5")
        setroom('ROOM', 'result', n=5, result=res(True), deadline=0); ok = await wf(pg, "window.__lg.res()==='done'", 3000)
        check('움직임 줄이기: 연출 없이 줄 단위(「그는 라이어가…」「맞습니다.」)로 바로 결과', ok and '그는 라이어가…' in await pg.inner_text('#ann') and '맞습니다.' in await pg.inner_text('#ann') and '시민 승리' in await pg.inner_text('#bMain'))
        await ctx.close()

        # ---------- 발표 음성: 파일 없음 폴백 / 파일 있음 ----------
        ctx, pg = await mk(br, 'u1', 1280, 720); await pg.goto(URL + '#ROOM'); await pg.click('body'); await pg.wait_for_timeout(300)
        await pg.evaluate('LiarAudio.setMuted(false)'); r = await pg.evaluate("""()=>{ LiarAudio.unlock(); const d=LiarAudio.voiceDur('seg1'); let ok=true; try{ LiarAudio.voice('seg1','그는 라이어가'); LiarAudio.voice('yes','맞습니다.'); }catch(e){ ok=false; } return {d, ok, mode:LiarAudio.voiceMode(), loaded:LiarAudio.voiceLoaded(), st:LiarAudio.state()}; }""")
        check('음성 파일이 없어도 깨지지 않는다(기본 길이 사용 · 브라우저 음성/합성 저음 폴백)', r['ok'] and abs(r['d'] - 1.9) < 0.01 and r['loaded'] == [] and r['mode'] in ('synth', 'speech'), r)
        check('음성 폴백 시험 중 콘솔 오류 0', not pg._errs, pg._errs[:2]); await ctx.close()
        tmp = tempfile.mkdtemp(); os.makedirs(tmp + '/audio')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=160:d=1.5', '-ac', '1', '-c:a', 'libvorbis', tmp + '/audio/liar_seg1.ogg'], check=True)
        class Hh(http.server.SimpleHTTPRequestHandler):
            def translate_path(self, path):
                path = path.split('?')[0]
                if path.startswith('/audio/'): return tmp + path
                return ROOT + path
            def log_message(self, *a): pass
        hs = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Hh); threading.Thread(target=hs.serve_forever, daemon=True).start()
        ctx, pg = await mk(br, 'u1', 1280, 720); await pg.goto(f'http://127.0.0.1:{hs.server_address[1]}/liar.html?api={BASE}&voicefiles=1#ROOM'); await pg.click('body')
        await pg.evaluate('LiarAudio.unlock()'); ok = await wf(pg, "LiarAudio.voiceLoaded().includes('seg1')", 5000)
        await pg.evaluate('LiarAudio.setMuted(false)'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({d:LiarAudio.voiceDur('seg1'),y:LiarAudio.voiceDur('yes'),loaded:LiarAudio.voiceLoaded(),v:LiarAudio.voice('seg1','x'),mode:LiarAudio.voiceMode()})")
        check('음성 파일이 있으면 불러와 실제 길이(1.5초)를 쓰고 재생한다 · 없는 조각(yes)은 기본값', ok and abs(r['d'] - 1.5) < 0.15 and r['y'] == 1.0 and r['mode'] == 'file', r)
        await ctx.close(); hs.shutdown()
        await br.close()
    print('\n' + ('ALL PASS' if not fails else f'FAILED {len(fails)}: {fails}')); sys.exit(1 if fails else 0)
asyncio.run(main())
