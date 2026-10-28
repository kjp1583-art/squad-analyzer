# -*- coding: utf-8 -*-
"""ⓘ 탭 뜻풀이(P-32) 시험 — `python3.13 tests/web_tap_tip_test.py`
  폰(360 · 터치): A ⓘ 탭 → 시트 열림(본문 = 설명) · 같은 칸 다시 탭/닫기 버튼/바깥 탭/Esc 로 닫힘  B 키보드(Enter) 로 열림
  C onclick 이 걸린 칸의 ⓘ 는 이동을 막고 시트만 · 긴 title 이 있는 일반 칸은 자동으로 탭 대상(점선) · 짧은 title·버튼 안은 대상 아님  D 가로 넘침 0
  PC(1280): E ⓘ 안 보이고 시트 안 생기고 title 그대로  F 프로필 지표 칸(cell)·목록 칸(box)이 ⓘ 와 data-tt 를 낸다(소스)"""
import asyncio, os, sys, re, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
TIP = '내가 낀 판 밴율 − 내가 없는 판 밴율로 계산해 원래 인기 밴 챔프의 영향을 제거했습니다. 숫자가 클수록 상대가 나를 더 경계해요.'
SETUP = r"""(tip)=>{const r=document.createElement('div');r.id='tttest';r.style.cssText='padding:8px;position:fixed;top:120px;left:0;right:0;z-index:99990;background:#222';
  r.innerHTML=`<div class="cmp" id="c1" title="${tip}" data-tt="${tip}"><span class="cmp-k">견제<i class="tt-i" role="button" tabindex="0" aria-label="뜻풀이 보기">ⓘ</i></span><b class="cmp-v">12</b></div>
  <div id="nav" onclick="window.__navd=(window.__navd||0)+1"><div class="cmp" id="c2" title="${tip}" data-tt="${tip}"><span class="cmp-k">이동칸<i class="tt-i" role="button" tabindex="0">ⓘ</i></span></div></div>
  <span id="plain" title="${tip}">긴 설명 일반 칸</span><span id="short" title="짧은 말">짧음</span><button id="btn" title="${tip}">버튼</button>`;
  document.body.appendChild(r); return true;}"""
async def phone(pg):
    await pg.evaluate(SETUP, TIP); await pg.wait_for_timeout(700)   # 자동 표시(0.3초 묶음) 기다림
    st = await pg.evaluate("()=>({hov:matchMedia('(hover:none)').matches,ii:getComputedStyle(document.querySelector('#c1 .tt-i')).display,plain:document.getElementById('plain').dataset.tt===undefined?null:1,short:document.getElementById('short').dataset.tt===undefined?null:1,btn:document.getElementById('btn').dataset.tt===undefined?null:1})")
    ok(st['hov'] and st['ii'] != 'none', 'A 터치 기기에서 ⓘ 가 보인다 %s' % st)
    ok(st['plain'] == 1 and st['short'] is None and st['btn'] is None, 'C 긴 일반 칸만 자동 대상(짧은 title·버튼 제외) %s' % st)
    await pg.tap('#c1 .tt-i')
    s = await pg.evaluate("()=>{const e=document.getElementById('ttSheet');return {on:!!e&&e.classList.contains('on'),t:e?e.querySelector('.tt-b').textContent:''}}")
    ok(s['on'] and s['t'] == TIP, 'A ⓘ 탭 → 시트 열림 · 본문 = 설명 %s' % s['t'][:20])
    box = await pg.evaluate("()=>{const r=document.getElementById('ttSheet').getBoundingClientRect();return {l:r.left,r:r.right,w:innerWidth,b:r.bottom,h:innerHeight}}")
    ok(box['l'] >= 0 and box['r'] <= box['w'] and box['b'] <= box['h'], 'D 시트가 화면 안 %s' % box)
    await pg.tap('#c1 .tt-i'); on = await pg.evaluate("()=>document.getElementById('ttSheet').classList.contains('on')")
    ok(not on, 'A 같은 ⓘ 다시 탭 = 닫힘')
    await pg.tap('#c1 .tt-i'); await pg.tap('#ttSheet .tt-x'); on = await pg.evaluate("()=>document.getElementById('ttSheet').classList.contains('on')")
    ok(not on, 'A 닫기 버튼으로 닫힘')
    await pg.tap('#c1 .tt-i'); await pg.tap('#short'); on = await pg.evaluate("()=>document.getElementById('ttSheet').classList.contains('on')")
    ok(not on, 'A 바깥 탭으로 닫힘')
    await pg.tap('#c1 .tt-i'); await pg.keyboard.press('Escape'); on = await pg.evaluate("()=>document.getElementById('ttSheet').classList.contains('on')")
    ok(not on, 'A Esc 로 닫힘')
    await pg.focus('#c1 .tt-i'); await pg.keyboard.press('Enter'); on = await pg.evaluate("()=>document.getElementById('ttSheet').classList.contains('on')")
    ok(on, 'B 키보드 Enter 로 열림'); await pg.keyboard.press('Escape')
    await pg.tap('#c2 .tt-i'); r = await pg.evaluate("()=>({navd:window.__navd||0,on:document.getElementById('ttSheet').classList.contains('on')})")
    ok(r['navd'] == 0 and r['on'], 'C onclick 칸 안의 ⓘ 는 이동을 막고 시트만 연다 %s' % r)
    await pg.tap('#short'); await pg.tap('#plain')
    r = await pg.evaluate("()=>({on:document.getElementById('ttSheet').classList.contains('on')})")
    ok(r['on'], 'C 긴 일반 칸을 탭하면 시트가 열린다')
    await pg.tap('#nav'); r = await pg.evaluate("()=>({navd:window.__navd||0})")
    ok(r['navd'] >= 1, 'C onclick 칸 자체는 그대로 동작한다 %s' % r)
    ov = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
    ok(ov['sw'] <= ov['cw'] + 1, 'D 가로 넘침 없음 %s' % ov)
async def pc(pg):
    await pg.evaluate(SETUP, TIP); await pg.wait_for_timeout(700)
    st = await pg.evaluate("()=>({hov:matchMedia('(hover:none)').matches,ii:getComputedStyle(document.querySelector('#c1 .tt-i')).display,sheet:!!document.getElementById('ttSheet'),title:document.getElementById('plain').getAttribute('title').length,plainTt:document.getElementById('plain').dataset.tt!==undefined})")
    ok(not st['hov'] and st['ii'] == 'none' and not st['sheet'] and st['title'] > 25 and not st['plainTt'], 'E PC 는 지금과 같다(ⓘ 숨김 · 시트 없음 · title 그대로) %s' % st)
    await pg.click('#c1'); s = await pg.evaluate("()=>!!document.getElementById('ttSheet')")
    ok(not s, 'E PC 에서 클릭해도 시트가 안 생긴다')
async def main():
    tmp = tempfile.mkdtemp(prefix='tt_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    for name, vp, fn in (('폰', (360, 800), phone), ('PC', (1280, 800), pc)):
        res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True, viewport=vp, after=fn)
        log = res['meta']['log']; ok(not log['pageerror'] and not log['console'], '%s 콘솔 오류 0 %s %s' % (name, log['pageerror'][:1], log['console'][:1]))
    src = open(os.path.join(os.path.dirname(HERE), 'index.html'), encoding='utf-8').read()
    n = len(re.findall(r'data-tt="\$\{escAttr\(tip\)\}"`:\'\'\}><span class="cmp-k">\$\{k\}\$\{tip\?\'<i class="tt-i"', src))
    ok(n == 2, 'F 프로필 지표 칸(cell)·목록 칸(box) 둘 다 ⓘ 와 data-tt 를 낸다(%d)' % n)
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
