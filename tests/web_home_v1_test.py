# -*- coding: utf-8 -*-
"""🏠 홈 1단계(제목 문구 · 여백/제목 통일 · 섹션 버튼 · 공지 한 줄 · 처음 오셨나요 접기) 시험 — `python3.13 tests/web_home_v1_test.py`
  A 새 제목이 보이고 옛 제목(플레이어 목록 · 챔피언 통계 · 최근 게임 · 다가오는 일정 · 거래소)이 홈에서 사라졌다
  B 첫 방문엔 「처음 오셨나요」가 펼쳐 있고 · 다시 열면(이미 봄) 접혀 있다 · 「다시 안 보기」를 누르면 사라진다
  C 섹션마다 버튼이 있고 눌렀을 때 맞는 화면으로 간다(내부티어 · 내전기록)
  D 공지는 폰에서도 한 줄(말줄임)이고 눌러서 펼친다
  E 홈 정리 규칙(.hv2)이 홈 밖 화면에 새지 않는다 · 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
async def scene(pg):
    o = {}
    await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(500)
    o['h'] = await pg.evaluate("()=>[...document.querySelectorAll('.hv2 h2, .hv2 .hsec-k, .hv2 .welcome summary b')].map(e=>e.textContent.trim())")
    o['open1'] = await pg.evaluate("()=>{const d=document.getElementById('welcomeCard');return d?d.hasAttribute('open'):null}")
    await pg.evaluate("()=>{try{localStorage.setItem('sgg_welcome_seen','1')}catch(e){}}"); await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(300)
    o['open2'] = await pg.evaluate("()=>{const d=document.getElementById('welcomeCard');return d?d.hasAttribute('open'):null}")
    o['ctas'] = await pg.evaluate("()=>[...document.querySelectorAll('.hv2 .cta')].map(e=>e.textContent.trim())")
    o['megaWS'] = await pg.evaluate("()=>{const m=document.querySelector('#megaboard:not(.hidden) .mega-msg');return m?getComputedStyle(m).whiteSpace:null}")
    if o['megaWS']:
        await pg.click('#megaboard'); o['megaOpen'] = await pg.evaluate("()=>document.getElementById('megaboard').classList.contains('open')")
        await pg.click('#megaboard'); o['megaOpen2'] = await pg.evaluate("()=>document.getElementById('megaboard').classList.contains('open')")
    o['ov'] = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
    # C: 버튼 동작
    o['hasKz'] = await pg.evaluate("()=>!![...document.querySelectorAll('.hv2 .cta')].find(b=>b.textContent.includes('내부티어'))")
    o['r1'] = 'tiers'
    if o['hasKz']:
        await pg.evaluate("()=>{[...document.querySelectorAll('.hv2 .cta')].find(b=>b.textContent.includes('내부티어')).click()}"); await pg.wait_for_timeout(400)
        o['r1'] = await pg.evaluate("()=>history.state&&history.state.route")
    await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>{[...document.querySelectorAll('.hv2 .cta')].find(b=>b.textContent.includes('내전기록')).click()}"); await pg.wait_for_timeout(400)
    o['r2'] = await pg.evaluate("()=>history.state&&history.state.route")
    # E: 홈 밖에서는 .hv2 없음
    o['outside'] = await pg.evaluate("()=>!!document.querySelector('.hv2')")
    await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>{try{localStorage.removeItem('sgg_welcome_off')}catch(e){}}")
    await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>welcomeClose()"); o['closed'] = await pg.evaluate("()=>!document.getElementById('welcomeCard')")
    return o
async def main():
    tmp = tempfile.mkdtemp(prefix='hv1_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    for name, vp in (('폰', (390, 844)), ('PC', (1280, 800))):
        res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=(os.environ.get('HV_SNAPSHOT') if os.environ.get('HV_SNAPSHOT') and os.path.exists(os.environ.get('HV_SNAPSHOT')) else xlsx), now=WI.NOW, cats=('rift',), shots=False, quiet=True, viewport=vp, after=scene)
        o = res['after']; log = res['meta']['log']; print('==', name)
        H = ' | '.join(o['h'])
        ok(all(t in H for t in ('클랜원 전적표', '챔피언별 승률·픽률', '방금 끝난 내전', '이번 주 클랜 한눈에')) and not any(t in H for t in ('플레이어 목록', '챔피언 통계', '🕒 최근 게임', '다가오는 일정', '🏪 거래소')), 'A 새 제목 · 옛 제목 없음 %s' % H[:160])
        ok(o['open1'] is True and o['open2'] is False, 'B 첫 방문엔 펼침, 본 뒤엔 접힘 %s %s' % (o['open1'], o['open2']))
        ok(o['closed'], 'B 「다시 안 보기」로 사라진다')
        ok((any('내부티어' in c for c in o['ctas']) or not o['hasKz']) and any('내전기록' in c for c in o['ctas']), 'C 섹션 버튼 %s (십이귀월 보드 %s)' % (o['ctas'], o['hasKz']))
        ok(o['r1'] == 'tiers' and o['r2'] == 'log', 'C 버튼이 맞는 화면으로 간다 %s %s' % (o['r1'], o['r2']))
        if o['megaWS'] is not None: ok(o['megaWS'] == 'nowrap' and o['megaOpen'] and not o['megaOpen2'], 'D 공지 한 줄 · 눌러서 펼침/접힘 %s' % o['megaWS'])
        else: print('  --   D 공지 없음(이 데이터에선 건너뜀)')
        ok(not o['outside'], 'E 홈 밖 화면엔 .hv2 규칙이 없다')
        ok(o['ov']['sw'] <= o['ov']['cw'] + 1, 'E 가로 넘침 없음 %s' % o['ov'])
        ok(not log['pageerror'] and not log['console'], 'E 콘솔 오류 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
