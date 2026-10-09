# -*- coding: utf-8 -*-
"""📱 미토·스크림 탭 폰 사용성 시험 — 루프 14회차 전달(A-17 · A-18, 2026-10-10 순찰 360×780)
  A. 미토 탭 첫 화면: 문서 높이가 짧다(최신 회차만 펼침 · 매치 카드 접힘 · 누적 전적 접힘) · 가로로 밀리지 않는다
  B. 접힌 회차를 열면 속(대진표·매치 카드)이 그려진다 · 모든 회차·매치·세트를 다 열어도 가로로 밀리지 않는다
  C. 대진표 박스를 누르면 그 매치 카드가 열려 보인다 — 회차마다 id 가 따로라 옛 회차 박스가 최신 회차로 튀지 않는다
  D. 스크림 탭 머리 카드(「· 마지막 날짜」)가 폰에서 가로로 밀지 않는다 · 데스크톱(1280)에서는 예전처럼 한 줄
  E. 페이지 오류 0
시트 스냅샷은 저장소에 없다 — 경로로 준다(실제 사이트와 같은 코드가 같은 데이터를 읽게 하는 tests/web_replay 하네스를 쓴다):
  python3 tests/web_mito_phone_test.py --xlsx <시트.xlsx> [--src index.html]
스냅샷이 없으면 SKIP(종료코드 0) 한다.
"""
import argparse, asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

MEASURE = r"""(route)=>{
  const de=document.documentElement,cw=de.clientWidth;
  const bad=[];
  for(const el of document.querySelectorAll('#view *')){const r=el.getBoundingClientRect();
    if(r.width>0&&r.right>cw+1){let p=el.parentElement,clip=false;while(p&&p.id!=='view'){const cs=getComputedStyle(p);if(/(auto|scroll|hidden)/.test(cs.overflowX)){clip=true;break;}p=p.parentElement;}
      if(!clip)bad.push((el.tagName+'.'+String(el.className||'').split(' ')[0]).slice(0,40)+'@'+Math.round(r.right));}}
  return {route,h:de.scrollHeight,vh:innerHeight,sw:de.scrollWidth,cw,bad:bad.slice(0,5)};
}"""

JS_A = "(async()=>{go('mito');await new Promise(r=>setTimeout(r,1200));const m=(%s)('mito');" % MEASURE + r"""
  m.rdTotal=document.querySelectorAll('details.mito-rd').length;
  m.rdOpen=document.querySelectorAll('details.mito-rd[open]').length;
  m.firstOpen=!!(document.querySelector('details.mito-rd')||{}).open;
  m.mtOpen=document.querySelectorAll('details.mito-mt[open]').length;
  m.accOpen=document.querySelectorAll('details.mito-acc[open]').length;
  m.accTable=!!document.querySelector('details.mito-acc .tblwrap table');
  const rd=document.querySelectorAll('details.mito-rd');
  const bodyN=d=>{const b=d&&d.querySelector(':scope>.mito-body');return b?b.children.length:-1;};
  m.olderBodies=[...rd].slice(1).map(bodyN);
  m.latestBody=bodyN(rd[0]);
  m.latestMatches=document.querySelectorAll('details.mito-rd[open] details.mito-mt').length;
  m.ids=[...document.querySelectorAll('[id^=mmatch]')].map(e=>e.id);
  return m;})()"""

JS_B = "(async()=>{go('mito');await new Promise(r=>setTimeout(r,1000));" + r"""
  const out={};
  const rd=[...document.querySelectorAll('details.mito-rd')];
  const fill=d=>{try{mitoFill(d);}catch(e){}};
  if(rd.length>1){const d=rd[1];d.open=true;fill(d);const b=d.querySelector(':scope>.mito-body');out.round2Body=b?b.children.length:-1;out.round2Matches=d.querySelectorAll('details.mito-mt').length;}
  for(const d of rd){d.open=true;fill(d);}
  for(const d of document.querySelectorAll('details.mito-mt')){d.open=true;fill(d);}
  for(const d of document.querySelectorAll('#view details')){d.open=true;}
  await new Promise(r=>setTimeout(r,600));
  const m=(%s)('mito-all-open');""" % MEASURE + r"""
  Object.assign(out,m);
  const ids=[...document.querySelectorAll('[id^=mmatch]')].map(e=>e.id);
  out.matchCount=ids.length;out.dupIds=ids.length-new Set(ids).size;
  out.domNodes=document.querySelectorAll('#view *').length;
  return out;})()"""

JS_C = r"""(async()=>{go('mito');await new Promise(r=>setTimeout(r,1000));
  const res={};
  const latest=document.querySelector('details.mito-rd');
  if(!latest){return {noBox:true,noRound:true};}
  const box=[...latest.querySelectorAll('.bk-box[onclick]')][0];
  if(!box){return {noBox:true};}
  const arg=/mitoJump\('([^']+)'\)/.exec(box.getAttribute('onclick'));
  res.arg=arg&&arg[1];
  box.click();
  await new Promise(r=>setTimeout(r,900));
  const t=document.getElementById('mmatch'+res.arg);
  res.found=!!t;res.open=!!(t&&t.open);res.filled=!!(t&&t.querySelector(':scope>.mito-body').children.length);
  res.inRound0=!!(t&&latest.contains(t));
  // 옛 회차: 3번째 회차를 열어 그 안의 박스를 누른다 — 열리는 매치가 그 회차 것이어야 한다
  const rd=[...document.querySelectorAll('details.mito-rd')];
  if(rd.length>2){const d=rd[2];d.open=true;mitoFill(d);
    const b2=[...d.querySelectorAll('.bk-box[onclick]')][0];
    if(b2){const a2=/mitoJump\('([^']+)'\)/.exec(b2.getAttribute('onclick'))[1];b2.click();await new Promise(r=>setTimeout(r,900));
      const t2=document.getElementById('mmatch'+a2);res.old={arg:a2,open:!!(t2&&t2.open),inOld:!!(t2&&d.contains(t2)),startsWith:a2.split('_')[0]};}}
  return res;})()"""

JS_D = "(async()=>{go('scrim');await new Promise(r=>setTimeout(r,1500));return (%s)('scrim');})()" % MEASURE
JS_D2 = r"""(()=>{const e=document.querySelector('.sx-total');return e?{ws:getComputedStyle(e).whiteSpace,w:Math.round(e.getBoundingClientRect().width)}:null;})()"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX'))
    ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    a = ap.parse_args()
    if not a.xlsx or not os.path.exists(a.xlsx):
        print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 건너뜁니다 — 종료코드 0')
        return 0
    fails = []

    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)
    res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True,
                         evals=[JS_A, JS_B, JS_C, JS_D, JS_D2], timeout_s=300)
    A, B, C, D, D2 = res['evals']
    print('A', json.dumps({k: v for k, v in A.items() if k != 'ids'}, ensure_ascii=False))
    scr = A['h'] / A['vh']
    ok(A['rdTotal'] >= 2, 'A0 회차 카드가 여러 개 있다 (%d)' % A['rdTotal'])
    ok(scr <= 12, 'A1 첫 화면 문서 높이 %.1f화면 ≤ 12 (옛 코드는 폰에서 220화면)' % scr)
    ok(A['sw'] <= A['cw'], 'A2 가로로 밀리지 않는다 (폭 %d ≤ %d) %s' % (A['sw'], A['cw'], A['bad']))
    ok(A['rdOpen'] == 1 and A['firstOpen'], 'A3 최신 회차 한 개만 펼쳐져 있다 (열린 회차 %d)' % A['rdOpen'])
    ok(A['mtOpen'] == 0, 'A4 매치 카드는 모두 접혀 있다 (열린 매치 %d)' % A['mtOpen'])
    ok(A['accOpen'] == 0 and A['accTable'], 'A5 누적 전적은 위에 접혀 있고 표는 .tblwrap 안에 있다')
    ok(A['latestBody'] > 0 and all(n == 0 for n in A['olderBodies']), 'A6 접힌 옛 회차는 속을 그리지 않았다 (옛 회차 속 요소 %s · 최신 %d)' % (A['olderBodies'], A['latestBody']))
    ok(A['latestMatches'] >= 1, 'A7 최신 회차에 매치 요약 줄이 있다 (%d)' % A['latestMatches'])
    print('B', json.dumps(B, ensure_ascii=False))
    ok(B.get('round2Body', -1) > 0 and B.get('round2Matches', 1) >= 0, 'B1 접힌 회차를 열면 속이 그려진다 (%s)' % B.get('round2Body'))
    ok(B['sw'] <= B['cw'], 'B2 모든 회차·매치·세트를 다 열어도 가로로 밀리지 않는다 (폭 %d ≤ %d) %s' % (B['sw'], B['cw'], B['bad']))
    ok(B['dupIds'] == 0 and B['matchCount'] >= 2, 'B3 매치 카드 id 가 회차마다 따로다 (카드 %d · 겹침 %d)' % (B['matchCount'], B['dupIds']))
    print('C', json.dumps(C, ensure_ascii=False))
    if C.get('noRound'):
        ok(False, 'C0 접는 회차 카드(details.mito-rd)가 없다')
    elif C.get('noBox'):
        print('SKIP  C: 최신 회차에 대진표 박스가 없어 건너뜀')
    else:
        ok(C['found'] and C['open'] and C['filled'] and C['inRound0'], 'C1 대진표 박스를 누르면 그 매치 카드가 열린다 (%s)' % {k: C[k] for k in ('arg', 'found', 'open', 'filled', 'inRound0')})
        if 'old' in C:
            o = C['old']
            ok(o['open'] and o['inOld'] and o['startsWith'] == '2', 'C2 옛 회차의 박스는 그 회차의 매치를 연다 (최신 회차로 튀지 않는다) %s' % o)
    print('D', json.dumps(D, ensure_ascii=False), json.dumps(D2, ensure_ascii=False))
    ok(D['sw'] <= D['cw'], 'D1 스크림 탭이 폰에서 가로로 밀리지 않는다 (폭 %d ≤ %d) %s' % (D['sw'], D['cw'], D['bad']))
    ok(D2 and D2['ws'] == 'normal', 'D2 폰에서 .sx-total 줄바꿈 허용 (white-space:%s)' % (D2 and D2['ws']))
    # 데스크톱: 예전처럼 한 줄(nowrap)
    res2 = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, out=None, shots=False, cats=('rift',), viewport=(1280, 800), quiet=True,
                          evals=["(async()=>{go('scrim');await new Promise(r=>setTimeout(r,1500));const e=document.querySelector('.sx-total');return e?getComputedStyle(e).whiteSpace:null;})()"], timeout_s=300)
    ok(res2['evals'][0] == 'nowrap', 'D3 데스크톱(1280)에서는 .sx-total 이 예전처럼 한 줄이다 (%s)' % res2['evals'][0])
    errs = res['meta']['log']['pageerror']
    ok(not errs, 'E 페이지 오류 0 %s' % errs[:3])
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
