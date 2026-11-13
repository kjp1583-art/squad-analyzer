# -*- coding: utf-8 -*-
"""📱 P-19 폰 첫 화면 머리 다이어트 시험 — 폰(360·390·412)에서 탭 줄 끝(=본문 시작)이 300px 안이고 가로로 안 밀리며,
필터 안 쓰는 탭(스크림·거래소·클랜일정·전역일)에선 필터 줄이 숨고, 내리면 헤더가 숨고 올리면 나오며 「↑ 맨 위로」가 뜬다. PC 는 그대로.
  python3 tests/web_phone_head_test.py --xlsx <시트.xlsx> [--src index.html]     (스냅샷이 없으면 SKIP · 종료코드 0)"""
import argparse, asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX')); ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    a = ap.parse_args()
    if not a.xlsx or not os.path.exists(a.xlsx):
        print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 건너뜁니다'); return 0
    fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    async def run(vp):
        async def after(pg):
            await pg.wait_for_timeout(1200); o = {}
            o['bottom'] = await pg.evaluate("Math.round(document.getElementById('tabswrap').getBoundingClientRect().bottom)")
            o['hdr'] = await pg.evaluate("Math.round(document.querySelector('header').getBoundingClientRect().height)")
            for k in ('home', 'scrim', 'market', 'cal', 'army'):
                await pg.evaluate("go('%s')" % k); await pg.wait_for_timeout(700)
                o[k] = await pg.evaluate("({nf:document.body.classList.contains('p19-nofilter'),fh:Math.round(document.getElementById('fltrow').getBoundingClientRect().height),"
                    "sw:document.documentElement.scrollWidth,cw:innerWidth,vis:(()=>{const t=document.querySelector('.tab.on'),w=document.getElementById('tabswrap');if(!t)return true;const a=t.getBoundingClientRect(),b=w.getBoundingClientRect();return a.left>=b.left-1&&a.right<=b.right+1})()})")
            await pg.evaluate("go('home')"); await pg.wait_for_timeout(500)
            await pg.evaluate("window.scrollTo(0,900)"); await pg.wait_for_timeout(400)
            await pg.evaluate("window.scrollBy(0,40)"); await pg.wait_for_timeout(500)
            o['down'] = await pg.evaluate("document.querySelector('header').classList.contains('p19-hide')")
            o['btn'] = await pg.evaluate("getComputedStyle(document.getElementById('toTopBtn')).display")
            await pg.evaluate("window.scrollBy(0,-60)"); await pg.wait_for_timeout(500)
            o['up'] = await pg.evaluate("document.querySelector('header').classList.contains('p19-hide')")
            return o
        return (await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, out=None, shots=False, cats=('rift',), quiet=True, viewport=vp, after=after, timeout_s=300))['after']
    for vp in ((360, 780), (390, 844), (412, 915)):
        o = await run(vp); t = '폰 %dx%d ' % vp
        ok(o['bottom'] <= 300, t + '탭 줄 끝(본문 시작) %dpx ≤ 300' % o['bottom'])
        ok(o['hdr'] <= 100, t + '헤더 %dpx ≤ 100' % o['hdr'])
        ok(all(o[k]['sw'] <= o[k]['cw'] for k in ('home', 'scrim', 'market', 'cal', 'army')), t + '가로 넘침 0')
        ok(not o['home']['nf'] and o['home']['fh'] > 0, t + '내전 탭은 필터 줄 있음')
        ok(all(o[k]['nf'] and o[k]['fh'] == 0 for k in ('scrim', 'market', 'cal', 'army')), t + '스크림·거래소·클랜일정·전역일은 필터 줄 숨김')
        ok(all(o[k]['vis'] for k in ('home', 'scrim', 'market', 'cal', 'army')), t + '현재 탭이 탭 줄 안에 보임')
        ok(o['down'] and not o['up'] and o['btn'] == 'block', t + '내리면 헤더 숨김·올리면 나옴·맨 위로 버튼 표시')
    pc = await run((1280, 800))
    ok(not pc['down'] and pc['btn'] == 'none', 'PC: 헤더 안 숨고 맨 위로 버튼 없음')
    ok(pc['hdr'] <= 70 and pc['home']['sw'] <= pc['home']['cw'], 'PC: 헤더 그대로(≤70)·가로 넘침 0')
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); return 1 if fails else 0
sys.exit(asyncio.run(main()))
