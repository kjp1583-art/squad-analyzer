# -*- coding: utf-8 -*-
"""🎖 메인 웹 프로필의 흐접새우 시즌 칭호 칩 — 시험 (2026-10-12 사장님 「보상으로 자신의 웹 프로필에 칭호같은것도 부여해주고」)
  A. TITLES 탭 파서가 새 등급(시즌)·이모지(🥇🥈🥉)를 그대로 읽는다 (가짜 gviz 응답으로 loadTitles 를 실제로 돌린다)
  B. 시즌 칭호는 상점/유니크 칭호 뒤에 붙고, 최신 시즌 → 🥇🥈🥉 → 일반·하드·베리하드 순 · 설명 문구가 상점 칭호 문구가 아니다
  C. 많으면 최신 3개 + 「외 N개」 버튼 — 누르면 나머지가 같은 모양으로 펼쳐진다
  D. 시즌 칭호가 없는 사람의 칩은 기준 커밋과 글자 하나까지 같다(상점·유니크 칭호 레이아웃 불변)
  E. 등급이 시즌이 아니어도 이름이 「흐접새우 시즌N …」 이면 같은 칭호로 본다 · 이름의 HTML 은 글자로만
  F. 폰 320/360/412 에서 프로필 이름줄(.pname)이 가로로 넘치지 않는다 · 페이지 오류 0
  python3 tests/web_season_title_test.py [--src index.html] [--base <고치기 전 index.html>]   (--base 가 없으면 git 의 origin/main 에서 꺼낸다)
"""
import argparse, asyncio, json, os, subprocess, sys, tempfile, threading, http.server, socketserver, functools, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if x and not c else ''), flush=True)
    if not c: FAILS.append(n)

def gviz(rows):
    cols = [{'id': 'A', 'label': l, 'type': 'string'} for l in ('닉네임', '칭호', '이모지', '등급')]
    return {'version': '0.6', 'status': 'ok', 'table': {'cols': cols, 'rows': [{'c': [{'v': v, 'f': None} for v in r]} for r in rows]}}
ROWS = [
    ['시험이', '엄장신', '🧢', '에픽'],
    ['시험이', '스쿼드코인 No.7', '🪙', '유니크'],
    ['시험이', '흐접새우 시즌2 하드 준우승', '🥈', '시즌'],
    ['시험이', '흐접새우 시즌2 일반 챔피언', '🥇', '시즌'],
    ['시험이', '흐접새우 시즌3 베리하드 3위', '🥉', '시즌'],
    ['시험이', '흐접새우 시즌4 일반 챔피언', '🥇', '시즌'],
    ['시험이', '흐접새우 시즌1 일반 3위', '🥉', '시즌'],
    ['한개', '흐접새우 시즌2 일반 챔피언', '🥇', '시즌'],
    ['엉뚱이', '흐접새우 시즌5 하드 챔피언', '🥇', '유니크'],       # 등급이 어긋나도 이름으로 시즌 칭호로 본다
    ['공격', '흐접새우 시즌6 일반 <img src=x onerror="window.__xss=1">', '🥇<b>', '시즌'],
    ['긴이름', '흐접새우 시즌12 베리하드 챔피언 ' + '가' * 40, '🥇', '시즌'],
    ['평범', '상점칭호', '🏷️', '레어'],
]
def serve(root):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    class Q(h.func):
        def log_message(self, *a): pass
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=root)); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start(); return s

async def open_page(b, port, name, w=390, rows=ROWS):
    ctx = await b.new_context(viewport={'width': w, 'height': 800}, is_mobile=False, has_touch=w < 600)
    errs = []
    async def gen(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:%d/' % port): await r.continue_(); return
        if 'docs.google.com' in u and 'sheet=TITLES' in u:
            m = re.search(r'responseHandler:([A-Za-z0-9_]+)', u)
            await r.fulfill(status=200, content_type='application/javascript', body='%s(%s);' % (m.group(1), json.dumps(gviz(rows), ensure_ascii=False))); return
        await r.abort()
    await ctx.route('**/*', gen)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto('http://127.0.0.1:%d/%s' % (port, name))
    await pg.wait_for_function("typeof titleChip==='function'&&typeof loadTitles==='function'", timeout=20000)
    await pg.evaluate("async()=>{TITLES=await loadTitles();}")
    return ctx, pg, errs

async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', default=os.path.join(REPO, 'index.html')); ap.add_argument('--base')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='sttl_')
    open(os.path.join(tmp, 'new.html'), 'w', encoding='utf-8').write(open(a.src, encoding='utf-8').read())
    if a.base: base = open(a.base, encoding='utf-8').read()
    else: base = subprocess.run(['git', 'show', 'origin/main:index.html'], cwd=REPO, capture_output=True, text=True, encoding='utf-8').stdout
    open(os.path.join(tmp, 'base.html'), 'w', encoding='utf-8').write(base)
    srv = serve(tmp); port = srv.server_address[1]
    async with async_playwright() as p:
        b = await H.launch(p)
        ctx, pg, errs = await open_page(b, port, 'new.html')
        # A. 파서
        got = await pg.evaluate("(()=>{const o={};for(const [k,v] of TITLES)o[k]=v.map(x=>[x.title,x.emoji,x.tier]);return o;})()")
        s = got.get('시험이', [])
        check('A 파서: 시험이의 7줄을 모두 읽는다', len(s) == 7, s)
        check('A 파서: 등급 「시즌」·이모지 🥇 그대로', ['흐접새우 시즌4 일반 챔피언', '🥇', '시즌'] in s and ['엄장신', '🧢', '에픽'] in s, s)
        # B. 순서·문구
        h = await pg.evaluate("titleChip('시험이')")
        order = await pg.evaluate("(()=>{const d=document.createElement('div');d.innerHTML=titleChip('시험이');return [...d.querySelectorAll('span[title]')].map(e=>e.textContent.trim());})()")
        check('B 순서: 유니크 → 상점 → 시즌(최신 시즌 먼저·🥇🥈🥉)', order[:2] == ['🪙 스쿼드코인 No.7', '🧢 엄장신'] and order[2:5] == ['🥇 흐접새우 시즌4 일반 챔피언', '🥉 흐접새우 시즌3 베리하드 3위', '🥇 흐접새우 시즌2 일반 챔피언'], order)
        tips = await pg.evaluate("(()=>{const d=document.createElement('div');d.innerHTML=titleChip('시험이');return [...d.querySelectorAll('span[title]')].map(e=>e.title);})()")
        check('B 설명: 시즌 칭호는 상점 문구가 아니다', all('포인트 상점' not in t for t in tips[2:]) and all('시즌' in t for t in tips[2:]) and '포인트 상점' in tips[1], tips)
        # C. 접힘
        n = await pg.evaluate("(()=>{const d=document.createElement('div');d.innerHTML=titleChip('시험이');const x=[...d.querySelectorAll('.stt-grp > span')];return {all:x.length,hid:x.filter(e=>e.style.display==='none').length,btn:(d.querySelector('.stt-more')||{}).textContent}})()")
        check('C 접힘: 시즌 칭호 5개 → 3개 보이고 2개 숨김 · 「외 2개」', n['all'] == 5 and n['hid'] == 2 and n['btn'] == '외 2개', n)
        r = await pg.evaluate("""(()=>{const d=document.createElement('div');d.id='tmpwrap';document.body.appendChild(d);d.innerHTML=titleChip('시험이');
          d.querySelector('.stt-more').click();const x=[...d.querySelectorAll('.stt-grp > span')];
          const out={vis:x.filter(e=>getComputedStyle(e).display!=='none').length,btn:!!d.querySelector('.stt-more'),bd:getComputedStyle(x[4]).borderTopWidth,fs:getComputedStyle(x[4]).fontSize,last:x[4].textContent.trim()};d.remove();return out;})()""")
        check('C 펼침: 버튼을 누르면 5개 모두 보이고 버튼은 사라진다 · 같은 모양(테두리·글자 크기)', r['vis'] == 5 and not r['btn'] and r['bd'] == '1px' and r['fs'] == '12.5px', r)
        check('C 시즌 칭호 3개 이하면 버튼 없음', await pg.evaluate("titleChip('한개').indexOf('stt-more')<0&&titleChip('한개').indexOf('stt-grp')>=0"))
        # E. 이름으로 판별 · esc
        h = await pg.evaluate("titleChip('엉뚱이')")
        check('E 등급이 유니크여도 이름이 「흐접새우 시즌N」 이면 시즌 칭호로 그린다(상점·경매 문구 없음)', 'stt-grp' in h and '경매·거래소' not in h and '시즌5 하드' in h, h[:300])
        await pg.evaluate("document.body.insertAdjacentHTML('beforeend','<div id=\"xs\">'+titleChip('공격')+'</div>')")
        check('E 이름의 HTML 은 글자로만(실행·태그화 안 됨)', await pg.evaluate("!window.__xss&&!document.querySelector('#xs img')&&document.getElementById('xs').textContent.indexOf('<img src=x')>=0"))
        await pg.evaluate("document.getElementById('xs').remove()")
        check('E 시즌 칭호는 코인 수집 뱃지 개수에 안 센다', await pg.evaluate("coinCountOf('엉뚱이')===0&&coinCountOf('시험이')===1"))
        check('E titleOf: 상점/유니크가 있으면 그게 대표', await pg.evaluate("titleOf('시험이').title")=='스쿼드코인 No.7')
        # D. 시즌 칭호 없는 사람 = 기준과 동일
        d_new = await pg.evaluate("[titleChip('평범'),titleChip('없는사람'),titleChip('시험이').split('stt-grp')[0]]")
        await ctx.close()
        ctxb, pgb, errsb = await open_page(b, port, 'base.html')
        d_base = await pgb.evaluate("[titleChip('평범'),titleChip('없는사람'),'']")
        check('D 시즌 칭호 없는 사람(상점 칭호·칭호 없음)의 칩이 기준 커밋과 같다', d_new[0] == d_base[0] and d_new[1] == d_base[1] and d_new[0].startswith('<span'), (d_new[0][:120], d_base[0][:120]))
        base_old = await pgb.evaluate("(()=>{TITLES=new Map([['시험이',[{name:'시험이',title:'엄장신',emoji:'🧢',tier:'에픽'},{name:'시험이',title:'스쿼드코인 No.7',emoji:'🪙',tier:'유니크'}]]]);return titleChip('시험이');})()")
        ctx, pg, errs2 = await open_page(b, port, 'new.html')
        new_old = await pg.evaluate("(()=>{TITLES=new Map([['시험이',[{name:'시험이',title:'엄장신',emoji:'🧢',tier:'에픽'},{name:'시험이',title:'스쿼드코인 No.7',emoji:'🪙',tier:'유니크'}]]]);return titleChip('시험이');})()")
        check('D 유니크+상점 칭호 둘이 있는 사람도 기준과 글자까지 같다', new_old == base_old, (new_old[:150], base_old[:150]))
        await ctxb.close(); await ctx.close()
        # F. 폰 폭
        for w in (320, 360, 412):
            ctx, pg, errs3 = await open_page(b, port, 'new.html', w=w)
            r = await pg.evaluate("""()=>{
              const host=document.createElement('div');host.className='prof';host.style.cssText='position:absolute;left:0;top:0;width:100%;padding:0 12px;box-sizing:border-box';
              const mk=(n)=>`<div class="pname" id="pn_${n}">★ 긴이름 <span class="ptag">3上</span>${titleChip(n)}</div>`;
              host.innerHTML=mk('시험이')+mk('긴이름')+mk('엉뚱이');document.body.appendChild(host);
              const out=[];for(const e of host.querySelectorAll('.pname')){if(e.scrollWidth>e.clientWidth+1)out.push(e.id+':'+e.scrollWidth+'>'+e.clientWidth);
                for(const c of e.querySelectorAll('.stt-grp > span')){const q=c.getBoundingClientRect();if(q.width&&q.right>innerWidth+1)out.push(e.id+' chip '+Math.round(q.right));}}
              if(document.documentElement.scrollWidth>innerWidth+1)out.push('page '+document.documentElement.scrollWidth);
              host.querySelectorAll('.stt-more').forEach(b=>b.click());
              for(const e of host.querySelectorAll('.pname')){if(e.scrollWidth>e.clientWidth+1)out.push('open '+e.id+':'+e.scrollWidth+'>'+e.clientWidth);}
              if(document.documentElement.scrollWidth>innerWidth+1)out.push('open page '+document.documentElement.scrollWidth);
              return out;}""")
            check('F 폭 %d: 프로필 이름줄 가로 넘침 없음(접힘·펼침 모두)' % w, not r, r)
            bt = await pg.evaluate("(()=>{const d=document.createElement('div');d.innerHTML=titleChip('시험이');document.body.appendChild(d);const r=d.querySelector('.stt-more').getBoundingClientRect();d.remove();return [r.width,r.height]})()")
            check('F 폭 %d: 「외 N개」 버튼 터치 높이 28px 이상' % w, bt[1] >= 28, bt)
            check('F 폭 %d: 페이지 오류 0' % w, errs3 == [], errs3)
            await ctx.close()
        check('페이지 오류 0', errs == [] and errs2 == [], (errs, errs2))
        await b.close()
    srv.shutdown()
    print('\nFAILS:', FAILS if FAILS else 'none'); sys.exit(1 if FAILS else 0)
asyncio.run(main())
