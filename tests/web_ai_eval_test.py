# -*- coding: utf-8 -*-
"""🤖 AI선생 주간평 카드 시험 — `python3 tests/web_ai_eval_test.py [--src index.html]`

왜: 2026-11-27 사장님 「주간평 개편안 전부 진행」 지시로
  ① `tooling/STYLE.md`(ai-eval-data)가 **첫 문장 진단 · ▸승리 조건/▸패배 패턴 · ① ② 액션 2개**로 바뀌었고
  ② `index.html` 의 `aiEvalBodyHtml` 이 그 포맷을 라벨 칩·번호 목록으로 그리게 바뀌었다.
시트에는 개편 전(문단 한 덩어리) 평가문이 190명분 그대로 남아 있으므로 **두 포맷이 같은 카드에서 읽혀야** 한다.

  A. 새 포맷 — 구획 3개 · 승리조건/패배패턴 행 2개(색 구분) · 액션 2개 번호목록 · 마커(▸ ①)가 글자로 남지 않음
  B. 옛 포맷 — 구획 3개 · 문단으로 나뉘어 읽힘 · 마커 없음 · 글자 손실 없음
  C. 계약 — 【전체】【지난주】【이번주】 키·순서 고정, 모르는 키는 키 이름 그대로, 구획 없는 글은 한 문단,
     HTML 이 섞여 들어와도 글자로만 그려진다
  D. 화면 — 폰 360 · 데스크톱 1280 에서 분석 탭 카드가 그려지고 가로 넘침 0, 콘솔·페이지 오류 0
  python3 tests/web_ai_eval_test.py [--src index.html] [--out 폴더] [--shot 폴더]
시트 스냅샷이 필요 없다(합성). playwright/openpyxl 이 없으면 SKIP.
"""
import argparse, asyncio, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "web_replay"))
try:
    import replay as R, synth
    import openpyxl  # noqa: F401
except Exception as e:   # pragma: no cover
    print("SKIP  playwright/openpyxl 없음 (%s) — 종료코드 0" % e); sys.exit(0)

NEW_NICK = synth.plain_names()[0]     # 가상01#TST — 개편 포맷
OLD_NICK = synth.plain_names()[1]     # 가상02#TST — 옛 포맷(시트에 남아 있는 190명분)
NOW = synth.NOW

# 개편 포맷(STYLE.md 2026-11-27): 첫 문장 진단 → ▸승리 조건 / ▸패배 패턴 → ① ② 액션
NEW = ("【전체】 이 사람은 이기는 판보다 지는 판에서 존재감이 남는 유형이야 — 팀이 앞서갈 때보다 뒤처질 때 더 바쁘게 움직이는 서폿이라, "
       "판을 뒤집는 카드보다 판이 무너지지 않게 붙잡는 쪽에 강점이 있어. "
       "【지난주】 21판 14승, 승률 67%로 전주 60%에서 한 칸 올랐어. "
       "▸승리 조건: 알리스타·레오나처럼 먼저 들어가서 여는 픽에서 거의 다 이겼고, 데스를 거의 안 준 판은 전부 승리였어. "
       "▸패배 패턴: 밤 늦게 첫 판에 모르가나·레나타처럼 사거리로 버티는 픽이 나오면 데스가 몰리면서 킬관여가 뚝 떨어져 — 늦은 시간에 낯선 카드를 잡는 흐름이 반복됐어. "
       "마지막 레나타 판만은 데스 없이 ACE를 받아 팀운 쪽이 컸고. "
       "【이번주】 ① 밤 10시를 넘겨 첫 판을 잡을 땐 알리스타·레오나 중 하나로 고정해서 열어 봐. "
       "② 모르가나를 꺼낼 판이면 라인전 5분까지 와드 두 개를 먼저 깔고 시작하는 것부터 해보자.")
# 옛 포맷(개편 전 STYLE.md): 렌즈 예고 + 시간순 나열 — 시트에 남아 있는 실제 생김새
OLD = ("【전체】 이번엔 클랜 안에서의 위상으로 볼게. 통산 승률은 절반 언저리인데 지는 판에서도 팀 최고로 꼽히는 ACE가 MVP보다 많은 쪽이야. "
       "이기는 날의 주인공보다 지는 날에도 제 몫을 남겨 두는 버팀목 유형이 클랜에서 그리 흔하지 않다는 게 이 사람의 자리를 말해 줘. "
       "【지난주】 11.16~11.22에 21판 14승으로 승률 6할대 후반을 찍었어. 전주 20판 60%보다 한 칸 더 올라선 주야. "
       "하이라이트는 11/22 오후로, 14시 알리스타 4/3/21부터 유미, 세나, 알리스타 MVP, 레오나까지 다섯 판을 내리 이겼어. "
       "특히 15시대 세나는 딜이 이번 주 가장 크게 터진 판이었고, 16시대 알리스타 0/3/23은 데스를 거의 안 주고 MVP를 가져갔어. "
       "반대로 같은 날 20시 모르가나는 채점이 바닥이었고 이후 22시 레오나, 23시 직전 레나타 글라스크까지 패배가 이어졌는데, 마지막 레나타는 데스가 거의 없어 ACE를 받은 아까운 판이야. "
       "팀운이 낮게 잡힌 주라 그 정도 승률이면 오히려 선방이야. "
       "【이번주】 어디까지나 제안인데, 늦은 시간대에 비주류 카드로 넘어갈 때 모르가나 같은 낯선 픽보다 알리스타·레오나처럼 손에 익은 카드를 이어 가 보는 건 어때? "
       "세나처럼 딜이 나온 판을 한 번 복기해서 어떤 템이 그 폭발을 만들었는지 적어 두면 좋을 듯?")

fails = []
def ok(c, m):
    print(("  ok   " if c else "  FAIL ") + m)
    if not c: fails.append(m)

def make_xlsx(path, evals):
    tabs = synth.build_tabs()
    tabs["AI_EVAL"] = [["닉네임", "평가", "갱신일", "상태", "직전평가일"]] + [list(r) for r in evals]
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for name, rows in tabs.items():
        ws = wb.create_sheet(name)
        for r in rows: ws.append(r)
    wb.save(path)
    return path

# 카드가 그려진 화면에서 재는 값 — 구조·가로 넘침·색 구분
MEASURE_JS = r"""
(sel) => {
  const card = [...document.querySelectorAll('.card')].find(c => /AI선생 주간평/.test(c.textContent));
  if (!card) return {missing: true};
  const box = card.getBoundingClientRect();
  const aie = card.querySelector('.aie');
  const q = s => [...card.querySelectorAll(s)];
  const rows = q('.aie-row'), acts = q('.aie-acts li'), secs = q('.aie-sec');
  const color = e => e ? getComputedStyle(e).color : '';
  const tag = r => { const t = r.querySelector('.aie-rowt'); return t ? t.textContent.trim() : ''; };
  const wides = [...card.querySelectorAll('*')].filter(e => e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0)
    .map(e => (e.className || e.tagName) + ':' + e.scrollWidth + '>' + e.clientWidth).slice(0, 6);
  return {
    missing: false, date: (card.querySelector('h2 span') || {}).textContent || '',
    secs: secs.map(s => (s.querySelector('.aie-k') || {}).textContent || ''),
    paras: q('.aie-p').map(p => p.textContent.trim()),
    rows: rows.map(r => ({t: tag(r), cls: r.className, txt: r.textContent.trim()})),
    rowColorW: color((rows.find(r => /승리/.test(tag(r))) || {querySelector: () => null}).querySelector('.aie-rowt')),
    rowColorL: color((rows.find(r => /패배/.test(tag(r))) || {querySelector: () => null}).querySelector('.aie-rowt')),
    acts: acts.map(li => li.textContent.trim()),
    actNums: [...card.querySelectorAll('.aie-acts .aie-n')].map(n => n.textContent.trim()),
    text: card.querySelector('.aie') ? card.querySelector('.aie').textContent.replace(/\s+/g, ' ').trim() : '',
    box: {w: box.width, h: box.height, right: box.right, left: box.left},
    aieW: aie ? {sw: aie.scrollWidth, cw: aie.clientWidth} : null,
    wides, docOver: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tagWrap: [...card.querySelectorAll('.aie-rowt')].filter(t => t.getBoundingClientRect().height > 26).length,
  };
}
"""

STRUCT_JS = r"""
([NEW, OLD]) => {
  const grab = (html) => {
    const w = document.createElement('div'); w.innerHTML = html;
    const q = s => [...w.querySelectorAll(s)];
    return {secs: q('.aie-sec').map(s => (s.querySelector('.aie-k') || {}).textContent || ''),
            rows: q('.aie-row').map(r => ({t: (r.querySelector('.aie-rowt') || {}).textContent || '', cls: r.className,
                                           c: (r.querySelector('.aie-rowc') || {}).textContent || ''})),
            acts: q('.aie-acts li').map(li => li.textContent.trim()),
            nums: q('.aie-acts .aie-n').map(n => n.textContent.trim()),
            paras: q('.aie-p').map(p => p.textContent.trim()),
            text: w.textContent.replace(/\s+/g, ' ').trim(), html: w.innerHTML};
  };
  const n = grab(aiEvalBodyHtml(NEW)), o = grab(aiEvalBodyHtml(OLD));
  const inj = document.createElement('div'); inj.innerHTML = aiEvalBodyHtml('【전체】 <img src=x onerror=alert(1)> <b>굵게</b>');
  return {
    new: n, old: o,
    plain: grab(aiEvalBodyHtml('구획 없는 글 하나. 두 번째 문장.')),
    empty: aiEvalBodyHtml(''),
    unknown: grab(aiEvalBodyHtml('【전체】 가 【지난주】 나 【기타】 다')),
    spaced: grab(aiEvalBodyHtml('【전체】 진단. 【지난주】 요약. ▸ 승리 조건: 알리스타에서 이겼어. ▸ 패배 패턴: 모르가나에서 졌어.')),
    invalid: grab(aiEvalBodyHtml('【전체】 앞 문장. 【지난주】 뒤 문장.')),
    inject: {img: inj.querySelectorAll('img').length, b: inj.querySelectorAll('b').length, text: inj.textContent.trim()},
  };
}
"""

async def screen(src, xlsx, out, width, shot_dir):
    """한 폭에서 폰/데스크톱 화면을 열어 두 선수의 분석 탭 카드를 잰다."""
    async def after(pg):
        out2 = {}
        for tag, nick in (("new", NEW_NICK), ("old", OLD_NICK)):
            await pg.evaluate("()=>sheetTab('aieval')")
            await pg.evaluate("(n)=>go('player', n)", nick)
            await pg.wait_for_selector(".aie", state="attached", timeout=20000)
            await pg.evaluate("()=>setProfTab('ana')")
            await pg.wait_for_timeout(350)
            out2[tag] = await pg.evaluate(MEASURE_JS, "ana")
            if shot_dir:
                el = await pg.evaluate_handle("()=>{const c=[...document.querySelectorAll('.card')].find(c=>/AI선생 주간평/.test(c.textContent)); if(c) c.scrollIntoView({block:'center'}); return c||null;}")
                elm = el.as_element()
                if elm:
                    await pg.wait_for_timeout(200)
                    await elm.screenshot(path=os.path.join(shot_dir, "aie_%d_%s.png" % (width, tag)))
        return out2
    ev = "(" + STRUCT_JS + ")([%s, %s])" % (json.dumps(NEW, ensure_ascii=False), json.dumps(OLD, ensure_ascii=False))
    r = await R.replay(src, xlsx, None, None, NOW, out, (), True, (), (width, 960), evals=(ev,), after=after)
    return {"struct": r["evals"][0], "screen": r.get("after"), "log": r["meta"]["log"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "index.html"))
    ap.add_argument("--out", default=tempfile.mkdtemp(prefix="aieval_"))
    ap.add_argument("--shot", default=None, help="카드 스크린샷을 남길 폴더(선택)")
    a = ap.parse_args()
    if a.shot: os.makedirs(a.shot, exist_ok=True)
    xlsx = make_xlsx(os.path.join(a.out, "synth_aieval.xlsx"),
                     [[NEW_NICK, NEW, "2026-10-05", "평가", ""], [OLD_NICK, OLD, "2026-10-05", "평가", ""]])

    print("A. 구조(새 포맷 / 옛 포맷)")
    res = asyncio.run(screen(a.src, xlsx, a.out, 430, a.shot))
    s = res["struct"]; n, o = s["new"], s["old"]
    ok(n["secs"] == ["전체기간", "지난주 평가", "다음 주 액션"], "새 포맷 구획 3개·라벨 %s" % n["secs"])
    ok(len(n["rows"]) == 2, "새 포맷 패턴 행 2개 (%d)" % len(n["rows"]))
    ok([r["t"] for r in n["rows"]] == ["승리 조건", "패배 패턴"], "행 라벨 %s" % [r["t"] for r in n["rows"]])
    ok("w" in n["rows"][0]["cls"] and "l" in n["rows"][1]["cls"], "행 색 구분 %s" % [r["cls"] for r in n["rows"]])
    ok(len(n["acts"]) == 2 and n["nums"] == ["1", "2"], "액션 2개·번호 %s" % n["acts"])
    ok("▸" not in n["text"] and "①" not in n["text"] and "②" not in n["text"], "마커가 글자로 남지 않음")
    ok("승리 조건" in n["rows"][0]["c"] or "알리스타" in n["rows"][0]["c"], "행 본문 유지: %s" % n["rows"][0]["c"][:30])
    ok(o["secs"] == ["전체기간", "지난주 평가", "다음 주 액션"], "옛 포맷 구획 3개 %s" % o["secs"])
    ok(len(o["rows"]) == 0 and len(o["acts"]) == 0, "옛 포맷엔 패턴행·액션 없음")
    ok(len(o["paras"]) >= 4, "옛 포맷 문단 분할 %d개" % len(o["paras"]))
    ok("이번엔 클랜 안에서의 위상으로 볼게" in o["text"] and "11.16~11.22" in o["text"], "옛 포맷 글자 손실 없음")

    print("B. 계약(키·순서·이스케이프)")
    ok(s["plain"]["secs"] == [] and len(s["plain"]["paras"]) == 1, "구획 없는 글은 한 문단")
    ok(s["empty"] == "", "빈 글은 빈 문자열")
    ok(s["unknown"]["secs"] == ["전체기간", "지난주 평가", "기타"], "모르는 키는 키 이름 그대로 %s" % s["unknown"]["secs"])
    ok(len(s["spaced"]["rows"]) == 2 and s["spaced"]["rows"][0]["t"] == "승리 조건", "`▸ 승리 조건` 처럼 띄어 써도 행으로")
    ok(s["invalid"]["secs"] == ["전체기간", "지난주 평가"] and len(s["invalid"]["paras"]) == 2, "한 줄짜리 옛 글도 문단으로")
    ok(s["inject"]["img"] == 0 and s["inject"]["b"] == 0, "HTML 은 글자로만 그려진다")
    ok("<img" in s["inject"]["text"], "주입하려던 글자는 그대로 보인다")

    print("C. 화면(폰 360 · 데스크톱 1280)")
    first = asyncio.run(screen(a.src, xlsx, a.out, 360, a.shot))
    res["screen"] = first["screen"]
    errs = first["log"]["pageerror"] + first["log"]["console"]
    ok(not errs, "360px 콘솔·페이지 오류 0 %s" % errs[:3])
    desks = asyncio.run(screen(a.src, xlsx, a.out, 1280, a.shot))
    derr = desks["log"]["pageerror"] + desks["log"]["console"]
    ok(not derr, "1280px 콘솔·페이지 오류 0 %s" % derr[:3])
    for width, sc in ((360, first["screen"]), (1280, desks["screen"])):
        for tag in ("new", "old"):
            m = (sc or {}).get(tag) or {}
            ok(not m.get("missing"), "%dpx %s 카드가 분석 탭에 그려짐" % (width, tag))
            if m.get("missing"): continue
            ok(not m["wides"], "%dpx %s 가로 넘침 0 %s" % (width, tag, m["wides"][:3]))
            ok(m["tagWrap"] == 0, "%dpx %s 라벨 칩 줄바꿈 없음(%d)" % (width, tag, m["tagWrap"]))
            ok(m["box"]["right"] <= width + 1, "%dpx %s 카드가 화면 안 (%d)" % (width, tag, int(m["box"]["right"])))
        mn, mo = (sc or {}).get("new") or {}, (sc or {}).get("old") or {}
        if mn and mo:
            ok(len(mn["secs"]) == 3 and len(mo["secs"]) == 3, "%dpx 두 포맷 모두 구획 3개 %s / %s" % (width, mn["secs"], mo["secs"]))
            ok(len(mn["acts"]) == 2, "%dpx 새 포맷 액션 2개" % width)
            ok(mn["rowColorW"] and mn["rowColorL"] and mn["rowColorW"] != mn["rowColorL"],
               "%dpx 승리/패배 라벨 색이 다름 (%s / %s)" % (width, mn["rowColorW"], mn["rowColorL"]))
            ok(mn["date"].strip() == "2026-10-05", "%dpx 갱신일 표시 %s" % (width, mn["date"].strip()))

    print()
    if fails:
        print("FAIL %d건 — %s" % (len(fails), a.out)); sys.exit(1)
    print("PASS — 전부 통과. 결과 폴더: %s" % a.out)


if __name__ == "__main__":
    main()
