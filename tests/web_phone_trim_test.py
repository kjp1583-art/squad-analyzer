# -*- coding: utf-8 -*-
"""✂️ P-36·P-37 폰 다듬기 시험 — 멸망전·주간스쿼드·내부티어가 폰에서 짧고(접기) 가로로 밀리지 않으며, PC 에서는 내부티어가 예전처럼 모두 펼쳐진다.
  python3 tests/web_phone_trim_test.py --xlsx <시트.xlsx> [--src index.html]     (스냅샷이 없으면 SKIP · 종료코드 0)
기준(360×780): 멸망전 ≤ 6화면 · 주간스쿼드 ≤ 10화면 · 내부티어 ≤ 6화면 / 가로 넘침 0. 측정은 10/24 순찰과 같은 방식(scrollHeight÷화면 높이)."""
import argparse, asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
J = lambda route: ("(async()=>{go('%s');await new Promise(r=>setTimeout(r,1500));const de=document.documentElement;"
                   "return {route:'%s',screens:+(de.scrollHeight/innerHeight).toFixed(1),sw:de.scrollWidth,cw:de.clientWidth,"
                   "leagues:document.querySelectorAll('details.tb-league').length,leaguesOpen:document.querySelectorAll('details.tb-league[open]').length,"
                   "myfold:document.querySelectorAll('details.myfold').length,myfoldOpen:document.querySelectorAll('details.myfold[open]').length};})()") % (route, route)

async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX')); ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    a = ap.parse_args()
    if not a.xlsx or not os.path.exists(a.xlsx):
        print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 건너뜁니다'); return 0
    fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    kw = dict(xlsx=a.xlsx, out=None, shots=False, cats=('rift',), quiet=True, evals=[J('myeol'), J('news'), J('tiers')], timeout_s=300)
    ph = await R.replay(os.path.abspath(a.src), viewport=(360, 780), **kw)
    pc = await R.replay(os.path.abspath(a.src), viewport=(1280, 800), **kw)
    my, nw, ti = ph['evals']; print('폰', json.dumps(ph['evals'], ensure_ascii=False))
    ok(my['screens'] <= 6, f"멸망전 폰 {my['screens']}화면 ≤ 6 (옛 23.3)"); ok(nw['screens'] <= 10, f"주간스쿼드 폰 {nw['screens']}화면 ≤ 10 (옛 16.4)"); ok(ti['screens'] <= 6, f"내부티어 폰 {ti['screens']}화면 ≤ 6 (옛 13.2)")
    ok(all(e['sw'] <= e['cw'] for e in ph['evals']), '폰 가로 넘침 0')
    ok(my['myfold'] == 8 and my['myfoldOpen'] == 1, f"멸망전: 카드 8개 중 4강만 펼침 ({my['myfoldOpen']}/{my['myfold']})")
    ok(ti['leagues'] == 2 and ti['leaguesOpen'] == 1, f"내부티어 폰: 첫 리그만 펼침 ({ti['leaguesOpen']}/{ti['leagues']})")
    pm, pn, pt = pc['evals']; print('PC', json.dumps(pc['evals'], ensure_ascii=False))
    ok(pt['leagues'] == 2 and pt['leaguesOpen'] == 2, 'PC: 내부티어 두 리그 모두 펼침(예전 그대로)')
    ok(all(e['sw'] <= e['cw'] for e in pc['evals']), 'PC 가로 넘침 0')
    print('ALL PASS' if not fails else f'FAIL {len(fails)}'); return 1 if fails else 0
sys.exit(asyncio.run(main()))
