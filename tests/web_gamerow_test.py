# -*- coding: utf-8 -*-
"""📱 게임 상세 줄(.prow) 닉네임 시험 — 폰 폭에서 닉네임이 0폭으로 눌리지 않는다 (2026-10-23 사장님 「닉네임이 하나도 안 뜬다」)
  `python3.13 tests/web_gamerow_test.py`  A 360·390·412 폭에서 모든 줄의 닉네임 폭 ≥ 글자 수만큼(잘리지 않거나 말줄임이라도 40px↑)  B 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
async def after(pg):
    gid = await pg.evaluate("()=>[...GAMES.keys()].find(k=>{const g=GAMES.get(k);return g&&Object.values(g.teams).flat().length>=8})||[...GAMES.keys()][0]")
    for w in (360, 390, 412):
        await pg.set_viewport_size({'width': w, 'height': 800})
        r = await pg.evaluate("""(gid)=>{const root=document.createElement('div');root.id='gr';root.style.cssText='width:'+(innerWidth-16)+'px;margin:0 8px';document.body.appendChild(root);
          root.innerHTML=gameDetailHtml(GAMES.get(gid));
          const rows=[...root.querySelectorAll('.prow')];const o=rows.map(p=>{const c=p.querySelector('.clickname');return {t:c?c.textContent:'',w:c?Math.round(c.getBoundingClientRect().width):-1,sw:p.scrollWidth,cw:p.clientWidth}});
          const res={n:rows.length,min:Math.min(...o.map(x=>x.w)),over:o.some(x=>x.sw>x.cw+1),sample:o.slice(0,3),doc:document.documentElement.scrollWidth,win:innerWidth};root.remove();return res;}""", gid)
        ok(r['n'] >= 5 and r['min'] >= 40, '폭 %d · 줄 %d개 · 가장 좁은 닉네임 %dpx — %s' % (w, r['n'], r['min'], r['sample']))
        ok(not r['over'] and r['doc'] <= r['win'], '폭 %d · 줄·문서 가로 넘침 없음 %s' % (w, (r['doc'], r['win'])))
async def main():
    tmp = tempfile.mkdtemp(prefix='gr_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True, viewport=(390, 844), after=after)
    log = res['meta']['log']
    ok(not log['pageerror'] and not log['console'], '콘솔 오류 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
