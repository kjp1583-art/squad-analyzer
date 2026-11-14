# -*- coding: utf-8 -*-
"""📈 P-47 새 패치 첫 며칠 — 챔피언 티어 탭이 이번 패치 판수가 적으면(NEWPATCH_MIN 미만) 직전 패치를 자동 합산하고 안내 한 줄을 보인다.
패치 칩을 직접 누르면 그 패치만 · 판수가 충분하면 이번 패치만 · NEWPATCH_MIN=0 이면 끔.
  python3.13 tests/web_newpatch_test.py --xlsx <시트.xlsx> [--src index.html]   (스냅샷이 없으면 SKIP · 종료코드 0)"""
import argparse, asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
GO = lambda minv: ("(async()=>{NEWPATCH_MIN=%s;PATCH_USER=false;PATCH_SEL=null;go('home');await new Promise(r=>setTimeout(r,400));go('champ');await new Promise(r=>setTimeout(r,900));"
                   "return {extra:PATCH_EXTRA,extraN:PATCH_EXTRA_N,latest:LATEST_PATCH,second:ALL_PATCHES[1]||'',games:GAMES.size,"
                   "patches:[...new Set([...GAMES.values()].map(g=>g.patch))].sort(),banner:!!document.querySelector('.np-merge'),bannerTxt:(document.querySelector('.np-merge')||{}).textContent||''};})()") % minv
async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX')); ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html')); a = ap.parse_args()
    if not a.xlsx or not os.path.exists(a.xlsx): print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 건너뜁니다'); return 0
    fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    pick = ("(async()=>{NEWPATCH_MIN=1e9;PATCH_USER=false;PATCH_SEL=null;go('home');await new Promise(r=>setTimeout(r,300));go('champ');await new Promise(r=>setTimeout(r,800));"
            "switchPatch(LATEST_PATCH);await new Promise(r=>setTimeout(r,800));return {extra:PATCH_EXTRA,user:PATCH_USER,banner:!!document.querySelector('.np-merge'),patches:[...new Set([...GAMES.values()].map(g=>g.patch))]};})()")
    res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, out=None, shots=False, cats=('rift',), quiet=True, viewport=(1280, 800), evals=[GO('1e9'), GO('0'), GO('1'), pick], timeout_s=300)
    big, off, one, chip = res['evals']; print(json.dumps(big, ensure_ascii=False)[:400])
    ok(big['extra'] == big['second'] and big['extra'] != '', f"판수가 모자라면 직전 패치({big['extra']})를 합친다 (이번 {big['extraN']}판)")
    ok(set(big['patches']) == {big['latest'], big['extra']}, f"집계에 두 패치만 들어간다 {big['patches']}")
    ok(big['banner'] and big['latest'] in big['bannerTxt'] and big['extra'] in big['bannerTxt'], '챔피언 티어 상단에 안내 한 줄')
    ok(off['extra'] == '' and not off['banner'] and off['patches'] == [off['latest']], 'NEWPATCH_MIN=0 → 끔(이번 패치만 · 안내 없음)')
    ok(one['extra'] == '' and one['patches'] == [one['latest']], '판수가 충분하면(임계 1판) 이번 패치만')
    ok(chip['extra'] == '' and chip['user'] and not chip['banner'], '패치 칩을 직접 누르면 그 패치만(합산 해제 · 안내 없음)')
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); return 1 if fails else 0
sys.exit(asyncio.run(main()))
