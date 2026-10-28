# -*- coding: utf-8 -*-
"""📱 브키도감 패치노트 · 내부티어 평가 카드 폰(360×780) 길이 시험 — 루프 15회차 전달(A-28)
  A. 브키도감 🗞 패치노트: 처음엔 최근 8개만(옛 코드는 전부 펼쳐 22화면) · 「더 보기」를 누르면 전부(데이터 그대로) · 가로로 안 밀림
  B. 🎖 내부티어 평가: 티어표 아래 「재미 지수」 여섯 카드는 기본 펼침(사장님 「펼치자」 10/11) · 접으면 확 줄어든다 · 접고 펴는 상태는 다시 그려져도 유지 · 펼친 높이 상한
  C. 페이지 오류 0
시트 스냅샷은 저장소에 없다 — 경로로 준다(tests/web_replay 하네스):
  python3 tests/web_brj_tier_phone_test.py --xlsx <시트.xlsx> [--src index.html] [--base <옛 index.html>]   (--base 를 주면 전/후 높이를 나란히 찍는다 — 옛 파일은 저장소 폴더 안에 두어야 data/ 를 읽는다)
스냅샷이 없으면 SKIP(종료코드 0) 한다. 받는 법: tests/web_replay/README.md (export?format=xlsx).
"""
import argparse, asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

JS_A = r"""(async()=>{BRJ_TAB='patch';go('brjang');await new Promise(r=>setTimeout(r,1500));const de=document.documentElement;
  const cnt=()=>document.querySelectorAll('#view .brjsec [style*="border-left:4px"]').length;
  const o={h0:de.scrollHeight,vh:innerHeight,n0:cnt(),total:(typeof BRJ_PATCH!=='undefined'&&BRJ_PATCH)?BRJ_PATCH.length:-1,sw0:de.scrollWidth,cw:de.clientWidth};
  const b=[...document.querySelectorAll('#view .brjsec button')].find(x=>/더 보기/.test(x.textContent));
  o.hasMore=!!b;o.moreTxt=b?b.textContent:'';
  if(b){b.click();await new Promise(r=>setTimeout(r,300));}
  o.n1=cnt();o.h1=de.scrollHeight;o.sw1=de.scrollWidth;o.moreAfter=![...document.querySelectorAll('#view .brjsec button')].every(x=>!/더 보기/.test(x.textContent));
  return o;})()"""

JS_B = r"""(async()=>{go('tiers');await new Promise(r=>setTimeout(r,1500));const de=document.documentElement,W=ms=>new Promise(r=>setTimeout(r,ms));
  const vis=()=>[...document.querySelectorAll('#view>.card .card')].filter(c=>c.getBoundingClientRect().height>0).length;
  const det=document.querySelector('details.tfun');
  const o={h0:de.scrollHeight,vh:innerHeight,sw0:de.scrollWidth,cw:de.clientWidth,hasDet:!!det,open0:!!(det&&det.open),visCards0:vis(),
    boards:document.querySelectorAll('.tb-league').length,titles:[...document.querySelectorAll('#view>.card h3')].map(h=>h.textContent.slice(0,6)),keep0:(typeof TFUN_OPEN!=='undefined')?TFUN_OPEN:null};
  if(det){det.open=false;await W(300);o.closed=!det.open;o.hc=de.scrollHeight;o.visCardsC=vis();o.keepC=(typeof TFUN_OPEN!=='undefined')?TFUN_OPEN:null;
    renderTiers();await W(200);o.closedAfterRender=!(document.querySelector('details.tfun')||{open:true}).open;
    const d2=document.querySelector('details.tfun');d2.open=true;await W(300);o.reopen=d2.open;o.keepO=(typeof TFUN_OPEN!=='undefined')?TFUN_OPEN:null;o.sw1=de.scrollWidth;
    renderTiers();await W(200);o.openAfterRender=!!(document.querySelector('details.tfun')||{}).open;}
  return o;})()"""

async def measure(src, xlsx):
    res = await R.replay(os.path.abspath(src), xlsx=xlsx, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True, evals=[JS_A, JS_B], timeout_s=300)
    return res['evals'][0], res['evals'][1], res['meta']['log']['pageerror']

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX'))
    ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    ap.add_argument('--base', default=None)
    a = ap.parse_args()
    if not a.xlsx or not os.path.exists(a.xlsx):
        print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 건너뜁니다 — 종료코드 0'); return 0
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c: fails.append(msg)
    if a.base:
        A0, B0, _ = await measure(a.base, a.xlsx)
        print('전(옛 코드): 패치노트 %.1f화면(%d개) · 내부티어 %.1f화면' % (A0['h0'] / A0['vh'], A0['n0'], B0['h0'] / B0['vh']))
    A, B, errs = await measure(a.src, a.xlsx)
    print('A', json.dumps(A, ensure_ascii=False)); print('B', json.dumps(B, ensure_ascii=False))
    print('후: 패치노트 %.1f화면 → 펼치면 %.1f화면 · 내부티어(펼침) %.1f화면 → 접으면 %.1f화면' % (A['h0'] / A['vh'], A['h1'] / A['vh'], B['h0'] / B['vh'], B.get('hc', 0) / B['vh']))
    ok(A['total'] > 8, 'A0 브장신 패치노트가 9개 이상 있다 (%d)' % A['total'])
    ok(A['n0'] == 8 and A['hasMore'], 'A1 처음엔 최근 8개만 + 「더 보기」 (%d개)' % A['n0'])
    ok(A['h0'] / A['vh'] <= 7, 'A2 첫 화면 길이 %.1f화면 ≤ 7 (옛 코드 22화면)' % (A['h0'] / A['vh']))
    ok(A['n1'] == A['total'] and not A['moreAfter'], 'A3 「더 보기」를 누르면 전부 나온다 (%d/%d) · 버튼은 사라진다' % (A['n1'], A['total']))
    ok(A['sw0'] <= A['cw'] and A['sw1'] <= A['cw'], 'A4 가로로 밀리지 않는다 (%d/%d ≤ %d)' % (A['sw0'], A['sw1'], A['cw']))
    ok(B['hasDet'] and B['open0'] and B.get('keep0') is True, 'B1 재미 지수 묶음이 있고 처음부터 펼쳐져 있다')
    ok(B['visCards0'] >= 3, 'B2 처음 화면에 지수 카드 %d장이 바로 보인다' % B['visCards0'])
    ok(B['h0'] / B['vh'] <= 16, 'B2b 펼친 내부티어 평가 길이 %.1f화면 ≤ 16 (옛 코드 13화면 — 상한)' % (B['h0'] / B['vh']))
    ok(B['boards'] >= 2, 'B3 티어표(리그 보드)는 접지 않고 그대로 보인다 (%d개)' % B['boards'])
    ok(B.get('closed') and B['h0'] - B['hc'] >= 3000, 'B4 접으면 확 짧아진다 (높이 %d → %d)' % (B['h0'], B['hc']))
    ok(B.get('sw1', 0) <= B['cw'] and B['sw0'] <= B['cw'], 'B5 가로로 밀리지 않는다')
    ok(B.get('keepC') is False and B.get('closedAfterRender') is True, 'B6a 접어 두면 다시 그려도(카드 안 「전체 보기」 등) 접힌 채 유지된다')
    ok(B.get('reopen') and B.get('keepO') is True and B.get('openAfterRender') is True, 'B6b 다시 펴면 다시 그려도 펼침이 유지된다')
    ok(not errs, 'C 페이지 오류 0 %s' % errs[:3])
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
