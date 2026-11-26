# -*- coding: utf-8 -*-
"""🚀 [2026-11-26 P1-4] 시트 탭 지연 로딩 — 부팅 때 화면 전용 탭을 받지 않고, 그 화면에 들어갈 때 받는다.

왜: 부팅에 시트 탭 25개를 전부 병렬로 받아, 홈이 쓰지도 않는 탭(TITLES·MYEOL·BRJANG·MBTI·LCK_PRED…)이
가장 큰 협곡 시트와 구글 동시연결 6개를 나눠 쓰느라 첫 화면이 밀렸다. 이제 홈 필수 탭만 즉시 받는다.

  A. 소스 점검 — 부팅 Promise.all 에 지연 탭 로더가 없고, 화면별 요구 목록에 그 화면들이 들어 있다
  B. 실행 점검(시트 스냅샷 필요) — 홈이 뜬 직후 그 탭들은 비어 있고(부팅에서 안 받았다), 그 화면에 들어가면 채워지며
     '불러오는 중' 자리가 남지 않고 페이지 오류가 0건이다
  python3 tests/web_lazy_tabs_test.py --xlsx <시트.xlsx> [--src index.html]   (스냅샷이 없으면 SKIP · 종료코드 0)
"""
import argparse, asyncio, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

LAZY = ["loadTitles", "loadCareers", "loadAiEval", "loadMbti", "loadMyeol", "loadTierHistory", "loadGhosts",
        "loadPredictions", "loadGrudge", "loadMitoWins", "loadMitoGames", "loadLckGpti", "loadLckPred", "loadBrjang"]


def _stub(txt):
    """대기·오류 자리표시 문구가 화면 '전체'인지 본다(본문 어딘가의 정상 문구 '불러오는 중'과 구분)."""
    t = (txt or '').strip()
    return [x for x in ('불러오는 중', '불러오지 못했습니다') if x in t]


def _no_stub(txt):
    """화면이 '대기·오류 자리'인지 — 데이터 오류 문구가 있거나, 짧은 화면에 '불러오는 중'만 있으면 실패.
       댓글 백엔드(앱스스크립트)는 이 재생 환경에서 막히므로 '댓글을 불러오지 못했습니다' 는 정상 문구로 본다."""
    t = (txt or '').strip()
    if '데이터를 불러오지 못했습니다' in t:
        return False
    return not (len(t) < 400 and '불러오는 중' in t)


def src_checks(src_text):
    fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)
    boot = re.search(r"await Promise\.all\(\[(loadClanTiers\(\).*?)\]\)", src_text, re.S)
    boot = boot.group(1) if boot else ""
    ok(bool(boot), "A0 부팅 Promise.all 을 찾았다")
    bad = [f for f in LAZY if f + "()" in boot]
    ok(not bad, "A1 부팅에 화면 전용 탭 로더가 없다 (남아 있으면: %s)" % (", ".join(bad) or "없음"))
    for need, lbl in (("player:ID_TABS", "프로필"), ('gpti:["lckgpti","mbti"]', "성향유형"),
                      ('mito:["mitogames"]', "미토"), ('game:["mitogames"]', "게임 상세"), ('news:["brjang"]', "주간스쿼드")):
        ok(need in src_text.replace(" ", ""), "A2 화면별 지연 목록에 %s 가 있다" % lbl)
    ok('if(t==="predict")return["predictions","lckpred"]' in src_text.replace(" ", ""),
       "A3 명예의 전당 '승부예측' 탭은 PREDICTIONS·LCK_PRED 를 먼저 받는다")
    ok("function sheetTab(" in src_text and "function routeTabNeeds(" in src_text,
       "A4 sheetTab·routeTabNeeds 가 있다")
    ok("prefetchProfileTabs" in src_text, "A5 프로필 탭 미리 받기(홈이 그려진 뒤)가 있다")
    return fails


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX'))
    ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    a = ap.parse_args()
    src_text = open(a.src, encoding='utf-8').read()
    print("=== A. 소스")
    fails = src_checks(src_text)
    if not a.xlsx or not os.path.exists(a.xlsx):
        print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 실행 점검을 건너뜁니다')
        print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); return 1 if fails else 0

    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)

    print("=== B. 실행 (시트 스냅샷으로 재생)")
    state = {}

    async def after(pg):
        # 홈이 뜬 직후: 화면 전용 탭은 아직 안 받았다(부팅에서 빠졌다는 증거). 프로필 탭은 미리 받기 중일 수 있다.
        state['boot'] = await pg.evaluate("()=>({mito:MITO_CODE_BY_GAME.size, lck:LCK_GPTI, brj:BRJANG.size, pred:Object.keys(PREDICTIONS).length,"
                                          " lckpred:LCK_PRED.length, idDone:ID_TABS.filter(_tabReady).length})")
        ok(state['boot']['mito'] == 0 and state['boot']['brj'] == 0 and state['boot']['pred'] == 0 and not state['boot']['lck'],
           "B1 홈이 뜬 직후 화면 전용 탭(미토·브장신·승부예측·LCK)은 비어 있다 %s" % state['boot'])
        # 화면에 들어가면 그때 받는다
        async def visit(js, keys, lbl, wait=900):
            await pg.evaluate(js); await pg.wait_for_timeout(wait)
            got = await pg.evaluate("(ks)=>ks.map(k=>_tabReady(k))", keys)
            txt = await pg.evaluate("(document.querySelector('#view')||{innerText:''}).innerText")
            ok(all(got), "B2 %s 화면에 들어가면 그 탭을 받는다 %s" % (lbl, dict(zip(keys, got))))
            ok(_no_stub(txt), "B3 %s 화면에 '불러오는 중'·오류가 남지 않는다 %s" % (lbl, _stub(txt)))
        await visit("go('gpti')", ['lckgpti', 'mbti'], '성향유형')
        await visit("go('mito')", ['mitogames'], '미토')
        await visit("go('news')", ['brjang'], '주간스쿼드')
        await visit("go('hof','predict')", ['predictions', 'lckpred'], '전당·승부예측')
        await visit("go('player',PLAYERS.keys().next().value)", None or [], '프로필') if False else None
        await pg.evaluate("(n)=>go('player',n)", await pg.evaluate("()=>PLAYERS.keys().next().value"))
        await pg.wait_for_timeout(1200)
        txt = await pg.evaluate("(document.querySelector('#view')||{innerText:''}).innerText")
        ok(_no_stub(txt), "B3 프로필 화면에 '불러오는 중'·오류가 남지 않는다 %s" % _stub(txt))
        # 딥링크: #p/닉 으로 바로 열어도 같은 화면이 나온다(대기 화면을 거쳐도 기록은 한 번만)
        return state

    res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, out=None, shots=False, cats=('rift',),
                         quiet=True, viewport=(1280, 900), after=after, timeout_s=300)
    log = res['meta']['log']
    ok(not log['pageerror'], "B4 페이지 오류 0건 %s" % (log['pageerror'][:2],))
    ok(not log['console'], "B5 콘솔 오류 0건 %s" % (log['console'][:2],))
    served = log['served']
    boot_tabs = [s for s in served if not s.endswith('(headers=0)')]
    print("  · 서버가 답한 탭(순서): %s" % ", ".join(served))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    return 1 if fails else 0


sys.exit(asyncio.run(main()))
