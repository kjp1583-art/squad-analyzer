# -*- coding: utf-8 -*-
"""🎮 스쿼드 미니게임 포털 시험 — `python3.13 tests/web_games_test.py`
  A 상단 탭에 「🎮 미니게임」이 있고 옛 「🦐 서바이벌」 탭은 없다 · 머리 링크도 하나로 합쳐졌다
  B 탭을 누르면 포털이 열린다(#games · 대표 배너 · 게임 카드 3장(흐접새우·스콰드 생존게임·브장신 키우기) + 준비 중 칸) · 카드의 플레이 링크가 survivors.html / novel.html
  C 장르 필터(액션 → 흐접새우만, 이야기 → 스콰드 생존게임만, 전체 → 둘 다) · 대표 배너 점을 누르면 다른 게임으로
  D 게임 소식에 두 게임의 패치노트가 게임 이름표와 함께 나온다
  E 플레이를 누르면 「마지막으로 한 게임」이 기억되고 다시 열면 「이어서 하기」가 뜬다
  F 폰(360)·PC(1280) 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
async def scene(pg):
    out = {}
    out['tabs'] = await pg.evaluate("()=>[...document.querySelectorAll('.tabs .tab')].map(t=>t.textContent.trim())")
    out['head'] = await pg.evaluate("()=>[...document.querySelectorAll('a.coachlink')].map(a=>a.textContent.trim())")
    await pg.evaluate("()=>{document.addEventListener('click',e=>{const a=e.target.closest('a.mg-play');if(a)e.preventDefault();},true)}")   # 시험 중엔 페이지 이동 막기
    await pg.evaluate("()=>{try{localStorage.removeItem('sgg_mg_last')}catch(e){}}")
    await pg.evaluate("()=>{const t=[...document.querySelectorAll('.tabs .tab')].find(t=>t.textContent.includes('미니게임'));t.click()}")
    await pg.wait_for_selector('#mgRoot .mg-card', timeout=8000); await pg.wait_for_timeout(900)
    out['hash'] = await pg.evaluate("()=>location.hash")
    out['cards'] = await pg.evaluate("()=>[...document.querySelectorAll('.mg-card:not(.soon)')].map(c=>({n:c.querySelector('.mg-name').textContent.trim(),href:c.querySelector('a.mg-play').getAttribute('href')}))")
    out['soon'] = await pg.evaluate("()=>document.querySelectorAll('.mg-card.soon').length")
    out['hero'] = await pg.evaluate("()=>!!document.querySelector('.mg-hero .mg-hero-t')")
    out['feed'] = await pg.evaluate("()=>[...document.querySelectorAll('.mg-fi .mg-fg')].map(e=>e.textContent.trim())")
    await pg.click("button.mg-chip:has-text('액션')"); out['f_act'] = await pg.evaluate("()=>[...document.querySelectorAll('.mg-card:not(.soon) .mg-name')].map(e=>e.textContent.trim())")
    await pg.click("button.mg-chip:has-text('이야기')"); out['f_story'] = await pg.evaluate("()=>[...document.querySelectorAll('.mg-card:not(.soon) .mg-name')].map(e=>e.textContent.trim())")
    await pg.click("button.mg-chip:has-text('육성')"); out['f_raise'] = await pg.evaluate("()=>[...document.querySelectorAll('.mg-card:not(.soon) .mg-name')].map(e=>e.textContent.trim())")
    out['bj_btns'] = await pg.evaluate("()=>[...document.querySelectorAll('.mg-card[data-mg=bj] .mg-act > *')].map(e=>e.textContent.trim())")
    await pg.click("button.mg-chip:has-text('전체')"); out['f_all'] = await pg.evaluate("()=>document.querySelectorAll('.mg-card:not(.soon)').length")
    h0 = await pg.evaluate("()=>document.querySelector('.mg-hero-t').textContent")
    await pg.evaluate("()=>document.querySelectorAll('.mg-hero-dots i')[1].click()"); h1 = await pg.evaluate("()=>document.querySelector('.mg-hero-t').textContent")
    out['hero_changed'] = h0 != h1
    await pg.click(".mg-card[data-mg=sv] a.mg-play")
    out['last'] = await pg.evaluate("()=>localStorage.getItem('sgg_mg_last')")
    await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>go('games')"); await pg.wait_for_selector('#mgRoot .mg-card', timeout=8000)
    out['recent'] = await pg.evaluate("()=>{const e=document.querySelector('.mg-recent');return e?e.textContent.trim():''}")
    out['ov'] = await pg.evaluate("()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
    return out
async def main():
    tmp = tempfile.mkdtemp(prefix='mg_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    for name, vp in (('폰', (360, 800)), ('PC', (1280, 800))):
        res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True, viewport=vp, after=scene)
        o = res['after']; log = res['meta']['log']
        print('==', name)
        ok(any('미니게임' in t for t in o['tabs']) and not any('서바이벌' in t for t in o['tabs']), 'A 탭: 🎮 미니게임 있음 · 옛 서바이벌 탭 없음 %s' % o['tabs'][-4:])
        ok(sum('미니게임' in t for t in o['head']) == 1 and not any('생존게임' in t for t in o['head']), 'A 머리 링크가 하나로 합쳐짐 %s' % o['head'])
        ok(o['hash'] == '#games' and o['hero'], 'B 포털이 열린다(#games · 대표 배너) %s' % o['hash'])
        ok([c['href'] for c in o['cards']] == ['survivors.html', 'novel.html', 'brjang.html'] and o['soon'] == 1, 'B 카드 3장 · 링크 맞음 · 준비 중 칸 1 %s' % o['cards'])
        ok(o['f_act'] == ['🦐 흐접새우 서바이벌'] and o['f_story'] == ['📖 스콰드 생존게임'] and o['f_raise'] == ['🍗 브장신 키우기'] and o['f_all'] == 3, 'C 장르 필터 %s %s %s %s' % (o['f_act'], o['f_story'], o['f_raise'], o['f_all']))
        ok(o['bj_btns'] == ['📖 시작하는 법 보기', '📚 브키도감'], 'B 브장신 카드는 디스코드 게임이라 「시작하는 법」·「브키도감」 버튼 %s' % o['bj_btns'])
        ok(o['hero_changed'], 'C 대표 배너 점으로 게임이 바뀐다')
        ok('흐접새우 서바이벌' in o['feed'] and '스콰드 생존게임' in o['feed'] and '브장신 키우기' in o['feed'], 'D 게임 소식에 세 게임이 이름표와 함께 나온다 %s' % o['feed'][:6])
        ok('sgg_mg_last' not in (o['last'] or '') and '"id":"sv"' in (o['last'] or ''), 'E 마지막으로 한 게임 기억 %s' % o['last'])
        ok('이어서 하기' in o['recent'] and '흐접새우' in o['recent'], 'E 다시 열면 이어서 하기 %s' % o['recent'])
        ok(o['ov']['sw'] <= o['ov']['cw'] + 1, 'F 가로 넘침 없음 %s' % o['ov'])
        ok(not log['pageerror'] and not log['console'], 'F 콘솔 오류 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
