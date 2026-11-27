# -*- coding: utf-8 -*-
"""⚔ 귀살대 헤더 — 세로로 꺾이지 않게·설명 간결화 시험 (2026-11-27 사장님 「귀살대 텍스트가 세로로 안좋게 표현되고있어」)
합성 시트(가짜 닉네임·PUUID)만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다. build_xlsx·CAST_A 는 web_kisatsu_recent_test 에서 가져온다.

  A 제목(⚔ 귀살대)과 한자(鬼殺隊)가 한 줄 — 360·390·768·1280 폭 모두에서 글자가 줄로 꺾이지 않는다
  B 제목·한자·설명이 카드 밖으로 넘치지 않고, 화면에 가로 스크롤이 생기지 않는다
  C 설명은 「상현을 맞라이너로 만났을 때 가장 잘 이기는 사냥꾼들」 한 문장만 — 90일·폼·탈퇴 설명은 화면에서 빠진다
  D 그 설명은 슬라이드 툴팁에 그대로 남아 있다(정보는 지우지 않고 접었다)
  E 필터링·정렬 로직은 그대로 — 6칸 · 최근 승률 내림차순 · 페이지 오류 0

  python3 tests/web_kisatsu_header_test.py
"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
from web_kisatsu_recent_test import build_xlsx, CAST_A

SUB_WANT = '상현을 맞라이너로 만났을 때 가장 잘 이기는 사냥꾼들'

MEASURE_JS = r"""(()=>{
  const t=document.querySelector('.kz-corps-t'), k=document.querySelector('.kz-corps-hd .kanji');
  const hd=document.querySelector('.kz-corps-hd'), sub=document.querySelector('.kz-corps-sub'), box=document.querySelector('.kz-corps');
  const rects=e=>e?[...e.getClientRects()].map(r=>({x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)})):[];
  const cs=t?getComputedStyle(t):null;
  const ov=(()=>{ if(!box) return null; const b=box.getBoundingClientRect();
    return [t,k,sub].filter(Boolean).filter(e=>{const r=e.getBoundingClientRect();return r.right>b.right+1||r.left<b.left-1||r.bottom>b.bottom+1}).length })();
  return {has:!!(t&&k&&hd&&sub&&box), txt:t?t.textContent.replace(/\s+/g,' ').trim():'',
    rects:rects(t), krects:rects(k), lines:(()=>{const rs=rects(t);return new Set(rs.map(r=>r.y)).size})(),
    lh:t?parseFloat(getComputedStyle(t).lineHeight)||0:0, fh:t?parseFloat(getComputedStyle(t).fontSize):0,
    ws:cs?cs.whiteSpace:null, shrink:cs?cs.flexShrink:null, height:t?t.offsetHeight:0,
    sameLine:(()=>{const a=rects(t)[0],b=rects(k)[0];return a&&b?Math.abs(a.y-b.y)<=3:null})(),
    subTxt:sub?sub.textContent.replace(/\s+/g,' ').trim():'', subRects:rects(sub), subLines:(()=>{const rs=rects(sub);return new Set(rs.map(r=>r.y)).size})(),
    over:ov, sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth,
    chipTips:[...document.querySelectorAll('.ksd-half')].map(e=>e.getAttribute('title')||''),
    n:(typeof KISATSU!=='undefined')?KISATSU.length:-1, wrs:(typeof KISATSU!=='undefined')?KISATSU.map(x=>Math.round(x.wr*1000)/1000):[]};
})()"""

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def run(vp):
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, CAST_A)
        async def scene(pg):
            await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(700)
            return {'m': await pg.evaluate(MEASURE_JS)}
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, viewport=vp, after=scene, timeout_s=300)
    return res['after']['m'], res['meta']['log']


async def main():
    for label, vp in (('360', (360, 740)), ('390', (390, 844)), ('721', (721, 900)), ('768', (768, 1024)), ('1024', (1024, 800)), ('1280', (1280, 800))):
        m, log = await run(vp)
        print('== %spx (innerWidth %d)' % (label, m['cw']))
        ok(m['has'], 'A 귀살대 제목·한자·설명이 그려졌다')
        if not m['has']:
            continue
        ok(m['txt'] == '⚔ 귀살대', 'A 제목 글자 %r' % m['txt'])
        ok(m['ws'] == 'nowrap' and m['shrink'] == '0', 'A 제목에 white-space:nowrap · flex-shrink:0 (%s %s)' % (m['ws'], m['shrink']))
        ok(m['lines'] == 1 and m['height'] <= m['lh'] * 1.5, 'A 제목이 한 줄 (줄 수 %d · 높이 %.0f / 줄높이 %.0f)' % (m['lines'], m['height'], m['lh']))
        ok(m['sameLine'] is True, 'A 한자 鬼殺隊가 제목과 같은 줄 %s' % m['krects'][:1])
        ok(m['over'] == 0, 'B 카드 밖으로 넘치는 요소 없음 %s' % m['over'])
        ok(m['sw'] <= m['cw'] + 1, 'B 가로 넘침 없음 %s' % {'sw': m['sw'], 'cw': m['cw']})
        ok(m['subTxt'] == SUB_WANT, 'C 설명은 한 문장 %r' % m['subTxt'])
        ok(all(t not in m['subTxt'] for t in ('90일', '15판', '폼', '탈퇴', '🔥')), 'C 90일·폼·탈퇴 설명은 화면에서 빠졌다')
        ok(m['chipTips'] and all('최근 90일' in t for t in m['chipTips']) and any('최근 30일' in t for t in m['chipTips']),
           'D 반쪽 툴팁에는 최근 90일·30일 기준이 남아 있다 %r' % (m['chipTips'][:1],))
        ok(m['n'] == 6 and m['wrs'] == sorted(m['wrs'], reverse=True), 'E 6칸 · 승률 내림차순 %s' % m['wrs'])
        ok(not log['pageerror'] and not log['console'], 'E 페이지 오류·콘솔 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
