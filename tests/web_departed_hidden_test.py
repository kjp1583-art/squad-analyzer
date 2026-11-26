# -*- coding: utf-8 -*-
"""🚪 [2026-11-27] 웹 내부티어·명예의 전당 탈퇴자(DEPARTED) 제외 점검.

왜: `ASSESSMENTS` 는 카드·프로필을 위해 탈퇴자까지 전원을 담는다. 그래서 내부티어 화면이 그것을
그대로 그려 탈퇴자가 칸 목록·명수·요약 카운트에 남아 있었고, 탈퇴 명단이 화면보다 늦게 도착하면
이미 그린 판정이 그대로 남았다. 명예의 전당은 랭킹에서 탈퇴자를 빼되 **커리어(대회 우승 역사)는
사장님 지시대로 보존**한다.

  A. 소스 점검 — renderTiers 두 루프의 isDeparted, loadDeparted 의 내부티어 재그리기,
     전당 랭킹 함수들(hofRecordsHtml·hofDetailHtml·hofMainBoxHtml·banPressureHofHtml·mitoHofHtml·
     computePredTitles·renderPredictionTitles·renderLckPredHof)의 제외, careerHofHtml 은 제외하지 않음
  B. 실행 점검(시트 스냅샷 필요) — 실제 데이터로 내부티어 화면과 전당 6탭을 그려
     탈퇴자 이름이 순위에 하나도 없고(커리어 탭은 우승 역사라 예외), 탈퇴 명단이 늦게 와도 화면이 갱신되며
     페이지 오류 0건인지 본다.
  python3 tests/web_departed_hidden_test.py --xlsx <시트.xlsx> [--src index.html]   (스냅샷 없으면 SKIP · 종료코드 0)
"""
import argparse, asyncio, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

# 랭킹에서 탈퇴자를 빼야 하는 함수 (커리어는 뺀다 — 역사 기록)
HOF_FILTERED = ["hofRecordsHtml", "hofDetailHtml", "hofMainBoxHtml", "banPressureHofHtml",
                "mitoHofHtml", "computePredTitles", "renderPredictionTitles", "renderLckPredHof"]


def fn_body(src, name):
    """function name( ... ) { ... } 본문(중괄호 균형). 없으면 빈 문자열."""
    m = re.search(r"function\s+%s\s*\(" % re.escape(name), src)
    if not m:
        return ""
    i = src.find("{", m.end())
    if i < 0:
        return ""
    depth, j = 0, i
    while j < len(src):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return ""


def src_checks(src_text):
    fails = []

    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c:
            fails.append(m)

    tiers = fn_body(src_text, "renderTiers")
    ok(tiers.count("isDeparted(name)") >= 2,
       "A1 renderTiers 의 두 루프(칸 분류·요약 카운트) 모두 탈퇴자를 건너뛴다 (%d곳)" % tiers.count("isDeparted(name)"))
    ok(tiers.count("ASSESSMENTS") >= 2 and tiers.count("for(const [name,a] of ASSESSMENTS)") >= 2,
       "A1b 두 루프 모두 이름을 꺼내 판정한다(두 번째 루프도 [name,a] 구조분해)")

    ld = fn_body(src_text, "loadDeparted")
    ok("computeAssessments()" in ld and "renderTiers()" in ld and "route)==='tiers'" in ld.replace(" ", ""),
       "A2 탈퇴 명단이 늦게 와도 내부티어를 보고 있으면 다시 계산해 다시 그린다")

    for n in HOF_FILTERED:
        b = fn_body(src_text, n)
        ok("isDeparted" in b, "A3 전당 랭킹 %s 는 탈퇴자를 뺀다" % n)

    ch = fn_body(src_text, "careerHofHtml")
    ok(bool(ch) and "isDeparted" not in ch, "A4 커리어(대회 우승 역사)는 거르지 않는다 — 사장님 지시대로 보존")
    ok("isDeparted" not in fn_body(src_text, "computeHOF"), "A4b computeHOF 는 집계만 한다(거르는 일은 그리는 쪽에서)")
    return fails


# 화면에 그려진 '사람 링크'(go('player','닉'))에서 탈퇴자 이름만 뽑는다 — 값·순위와 무관하게 이름 기준.
NAMES_JS = r"""
() => {
  const h = (document.querySelector('#view') || {innerHTML: ''}).innerHTML;
  const re = /go\('player',\s*'([^']*)'\)/g;
  const out = new Set(); let m;
  while ((m = re.exec(h))) out.add(m[1].replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  const bad = [...out].filter(n => { try { return isDeparted(n); } catch (e) { return false; } });
  return {names: out.size, bad};
}
"""


# 내부티어 칸의 이름 버튼은 openPlayerCard(...) 로 프로필 카드를 연다 — 그 이름을 그대로 꺼내 판정한다.
TB_NAMES_JS = r"""
() => {
  const out = [...document.querySelectorAll('#view .tb-name')].map(b => {
    const m = /openPlayerCard\(&quot;(.*?)&quot;\)/.exec(b.getAttribute('onclick') || '') ||
              /openPlayerCard\("(.*?)"\)/.exec(b.getAttribute('onclick') || '');
    return m ? m[1].replace(/&amp;/g, '&') : null;
  }).filter(Boolean);
  const bad = out.filter(n => { try { return isDeparted(n); } catch (e) { return false; } });
  return {shown: out.length, bad};
}
"""


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
        print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
        return 1 if fails else 0

    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c:
            fails.append(m)

    print("=== B. 실행 (시트 스냅샷으로 재생)")
    state = {}

    async def after(pg):
        async def ev(js, *args):
            return await pg.evaluate(js, *args) if args else await pg.evaluate(js)

        info = await ev("""()=>{
          const dep=[...ASSESSMENTS.keys()].filter(n=>isDeparted(n));
          return {departed:DEPARTED_SET.size, ass:ASSESSMENTS.size, assDep:dep.length};
        }""")
        state['info'] = info
        print("  · 탈퇴 명단 %d명 · 평가 대상 %d명(그중 탈퇴자 %d명)" % (info['departed'], info['ass'], info['assDep']))
        if not info['departed'] or not info['assDep']:
            print('SKIP  실행 점검 — 이 스냅샷에는 탈퇴자/평가 대상이 없어 확인할 것이 없습니다')
            return state

        # ① 내부티어 — 칸 목록·명수에 탈퇴자 0명
        await ev("()=>go('tiers')")
        await pg.wait_for_timeout(700)
        t = await ev("""()=>{
          const inBoard=new Set(); LEAGUES.forEach(L=>L.groups.forEach(g=>g.cols.forEach(c=>inBoard.add(c))));
          let exp=0; for(const [n,a] of ASSESSMENTS) if(!isDeparted(n)&&inBoard.has(a.tier)) exp++;
          return {shown:document.querySelectorAll('#view .tb-name').length, exp,
                  depTotal:ASSESSMENTS.size-[...ASSESSMENTS.keys()].filter(n=>!isDeparted(n)).length};
        }""")
        names = await ev(TB_NAMES_JS)
        ok(not names['bad'], "B1 내부티어 칸에 탈퇴자 이름이 없다 %s" % (names['bad'][:5],))
        ok(names['shown'] == t['exp'], "B1c 칸 이름 버튼 %d개를 모두 읽었다(탈퇴자 판정 대상)" % names['shown'])
        ok(t['shown'] > 0 and t['shown'] == t['exp'],
           "B2 칸에 그려진 인원(%d) = 탈퇴자를 뺀 평가 대상(%d)" % (t['shown'], t['exp']))

        # ①b 재미 지수 6가지(억울·항노화·뒷심·CS강박·몇 판째·세대대결)를 모두 펼쳐도 탈퇴자 0명
        for f in ("toggleGrudge", "toggleAA", "toggleGrit", "toggleCso"):
            try:
                await ev("()=>%s()" % f)
                await pg.wait_for_timeout(350)
            except Exception:
                pass
        full = await ev(NAMES_JS)
        ok(not full['bad'], "B2b 펼친 재미 지수까지 통틀어 탈퇴자 이름이 없다 %s" % (full['bad'][:5],))

        # ② 탈퇴 명단이 화면보다 늦게 도착 — 비우고 그린 뒤 loadDeparted 로 갱신되는지
        late = await ev("""async ()=>{
          DEPARTED_SET=new Set(); ASSESSMENTS=new Map(); TIER_AVG={}; DATA_SEQ++;
          renderTiers();
          const before=document.querySelectorAll('#view .tb-name').length;
          await loadDeparted();
          await new Promise(r=>setTimeout(r,300));
          return {before, after:document.querySelectorAll('#view .tb-name').length};
        }""")
        names2 = await ev(NAMES_JS)
        ok(late['before'] == 0 and late['after'] > 0,
           "B3 탈퇴 명단 도착 전 빈 화면(%d) → loadDeparted 뒤 다시 그려짐(%d)" % (late['before'], late['after']))
        ok(not names2['bad'], "B4 늦게 도착한 뒤에도 탈퇴자 이름이 없다 %s" % (names2['bad'][:5],))

        # ③ 명예의 전당 6탭 — 랭킹은 탈퇴자 0명, 커리어는 역사라 예외
        for tab, lbl in (("rank", "기본 랭킹"), ("pressure", "견제·미토·망령"), ("record", "기록실"),
                         ("detail", "상세지표"), ("predict", "승부예측"), ("career", "커리어·우승")):
            await ev("(t)=>go('hof',t)", tab)
            await pg.wait_for_timeout(1400)
            r = await ev(NAMES_JS)
            txt = await ev("()=>(document.querySelector('#view')||{innerText:''}).innerText.slice(0,200)")
            ok(len(txt.strip()) > 0, "B5 전당 '%s' 탭이 그려진다" % lbl)
            if tab == "career":
                print("  · 커리어 탭의 탈퇴자 이름 %d개 — 우승 역사라 남는 것이 정상(실패 아님)" % len(r['bad']))
            else:
                ok(not r['bad'], "B6 전당 '%s' 랭킹에 탈퇴자가 없다 %s" % (lbl, r['bad'][:5]))
        return state

    res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, out=None, shots=False, cats=('rift',),
                         quiet=True, viewport=(1280, 900), after=after, timeout_s=420)
    log = res['meta']['log']
    ok(not log['pageerror'], "B7 페이지 오류 0건 %s" % (log['pageerror'][:2],))
    ok(not log['console'], "B8 콘솔 오류 0건 %s" % (log['console'][:2],))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    return 1 if fails else 0


sys.exit(asyncio.run(main()))
