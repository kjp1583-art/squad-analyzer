# -*- coding: utf-8 -*-
"""📰 주간스쿼드 기사 본문 200~260자(3~4문장) 렌더 시험 — `python3 tests/web_weekly_body_test.py`

왜: 2026-11-27 사장님 「기사 5~8개 백화점식 → 핵심 4~5개 · 본문 120자 → 200~260자(3~4문장)」 지시로
프롬프트(`tooling/weekly_review_prompt.md`)가 바뀌었다. 본문이 길어지면 ①지면에서 잘리거나(line-clamp·고정 높이)
②홈 1면 미리보기의 '이어 읽기'가 2줄 클램프에 함께 먹히고 ③폰에서 가로로 넘칠 수 있다.

  A. 프롬프트 점검 — 구분선은 하나, JSON 예시는 파싱되고 필드가 그대로, 4~5개·200~260자·7,500자·판수 헤드라인 금지·새 재료 줄 규칙이 있다
  B. 지면 렌더 — 247자 본문 5개가 잘리지 않고(클램프·고정 높이 없음) 그려지고 가로 넘침 0
  C. 홈 1면 미리보기 — 본문이 길어도 '이어 읽기 ›'가 보이고 가로 넘침 0
"""
import asyncio, json, os, re, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

BODY = ("이번 주 협곡은 예상 밖의 얼굴들이 주인공이었다. 내부티어 하위 라인에서 올라온 신예가 상현 상대 4승 1패를 거두며 판을 흔들었고, "
        "지난주 3픽에 그쳤던 노틸러스가 이번 주 40밴으로 1위에 올랐다. 편집국 확인 결과 그 챔피언이 풀린 판에서는 승률이 20%포인트 넘게 갈렸고, "
        "같은 팀 듀오 두 명은 여덟 판을 함께 뛰어 전부 이겼다. 다음 주에는 이 챔피언이 계속 밴으로 묶일지, 신예의 상승세가 멸망전 본선까지 이어질지 지켜볼 만하다.")

JS = """
() => {
  const B = %s;
  const ev = t => ({emoji:'🏟', section:'협곡', title:t, body:B, photo:{kind:'none',key:''}});
  const W = {placeholder:false, week:{from:'2026-11-16',to:'2026-11-22',label:'11월 셋째 주'}, generated_at:'2026-11-23 09:00',
    teacher:{name:'AI 선생님',mood:'🧑‍🏫 흐뭇'}, headline:'2티어, 상현을 잡았다', grade:{letter:'B+',reason:'114판·참가 88명'},
    summary:'이번 주는 하위 라인의 반란으로 요약됩니다.', events:[ev('t0'),ev('t1'),ev('t2'),ev('t3'),ev('t4')],
    brj:[], notices:[{kind:'알림',text:'이번 주 협곡 114판 · 참가 88명'}],
    students:[{name:'가나다',emoji:'🥇',line:'41판 20승, 이번 주의 엔진이었습니다.'}],
    awards:[{title:'이주의 장인',name:'가나다',why:'노틸러스 8판 7승'}], homework:['서폿 한 판씩'], closing:'다음 주에 또 봅시다.',
    facts:[], history:[], issue:10, stats:{}};
  const out = {len:B.length};
  const wrap = document.createElement('div'); document.body.appendChild(wrap);
  wrap.innerHTML = newsPageHtml(W, {});
  const ps = [...wrap.querySelectorAll('.np-art p')], lead = wrap.querySelector('.np-lead'), box = wrap.querySelector('.np');
  out.page = {n:ps.length, chars:ps.map(p=>p.textContent.length), clipped:ps.filter(p=>p.scrollHeight>p.clientHeight+1).length,
    clamp:ps.filter(p=>{const c=getComputedStyle(p); return (c.webkitLineClamp&&c.webkitLineClamp!=='none')||c.maxHeight!=='none';}).length,
    leadChars:lead.textContent.length, leadClipped:lead.scrollHeight>lead.clientHeight+1, over:box.scrollWidth-box.clientWidth};
  const saved = WEEKLY_REVIEW; WEEKLY_REVIEW = W;
  const t = document.createElement('div'); t.innerHTML = newsTeaserHtml(); document.body.appendChild(t);
  const card = t.querySelector('.nt-lead'), tl = t.querySelector('.nt-lead-t'), more = t.querySelector('.nt-more');
  const cb = card?card.getBoundingClientRect():null, pb = tl?tl.getBoundingClientRect():null, mb = more?more.getBoundingClientRect():null;
  out.tease = {hasMore:!!more, moreVisible: !!more && mb.bottom<=cb.bottom+0.5 && mb.top>=pb.bottom-1 && mb.width>0,
    leadChars:tl?tl.textContent.length:0, clamp:tl?getComputedStyle(tl).webkitLineClamp:'', over:t.scrollWidth-t.clientWidth};
  WEEKLY_REVIEW = saved; wrap.remove(); t.remove();
  out.docOver = document.documentElement.scrollWidth - innerWidth;
  return out;
}
""" % repr(BODY)


def prompt_checks():
    t = open(os.path.join(ROOT, 'tooling', 'weekly_review_prompt.md'), encoding='utf-8').read()
    lines = t.splitlines()
    cut = [i for i, l in enumerate(lines) if l.strip() == '---']
    ok(cut and not any(l.strip() == '---' for l in lines[cut[0] + 1:]), 'A 프롬프트 구분선(---)은 맨 앞 하나뿐 — 봇이 거기서 자른다')
    blocks = re.findall(r"```\n(\{.*?\n\})\n```", t, re.S)
    ok(len(blocks) == 1, 'A JSON 예시 블록 하나')
    try:
        d = json.loads(blocks[0]); good = True
    except Exception as e:
        d = {}; good = False; ok(False, 'A JSON 예시 파싱 %s' % e)
    if good:
        ok(set(d) == {'placeholder', 'week', 'generated_at', 'teacher', 'headline', 'grade', 'summary', 'events', 'brj', 'notices',
                      'students', 'awards', 'homework', 'closing', 'facts', 'history'}, 'A JSON 예시 필드 16개 그대로(웹·봇이 읽는 이름)')
    body = '\n'.join(lines[cut[0] + 1:])
    for needle, m in (('4~5개', 'A 기사 4~5개로 압축'), ('200~260자', 'A 본문 200~260자(3~4문장)'), ('7,500자', 'A 전체 출력 7,500자 상한'),
                      ('판수·요일만 센 헤드라인', 'A 판수·요일 헤드라인 금지'), ('메타 한 줄 진단', 'A 칼럼 = 메타 진단 + 다음 주 관전'),
                      ('[전주 대비]', 'A [전주 대비] 재료 규칙'), ('[원챔/장인]', 'A [원챔/장인]'), ('[라이벌 맞대결]', 'A [라이벌 맞대결]'),
                      ('[포지션/시간 메타]', 'A [포지션/시간 메타]'), ('[티어 이변]', 'A [티어 이변]'), ('[멸망전/대회]', 'A [멸망전/대회]'),
                      ('`brj` 필드에서만', 'A 브장신 brj 분리 원칙 유지'),
                      ('기레기', 'A 자극적 헤드라인 지시(기레기 톤)'), ('자극적 1면 제목', 'A 기사 제목도 1면 제목 문법'),
                      ('사실은 한 톨도 흔들지 않습니다', 'A 자극은 표현만 — 사실 왜곡 금지'), ('Before → After', 'A 담담한 요약체 → 1면 제목 예시')):
        ok(needle in body, m)
    ok('200~260자' in body and '120자 안' in body, 'A brj 코너 본문은 120자 안 그대로(길이 규칙 분리)')


async def render(viewport):
    async def after(pg):
        return await pg.evaluate(JS)
    tmp = tempfile.mkdtemp(prefix='wkbody_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    res = await R.replay(os.path.join(ROOT, 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True,
                         viewport=viewport, after=after)
    return res


async def main():
    prompt_checks()
    for vw, vh in ((1280, 900), (360, 780)):
        res = await render((vw, vh)); S = res.get('after') or {}
        pe = res['meta'].get('pageerror') or []
        P, T = S.get('page', {}), S.get('tease', {})
        ok(0 < S.get('len', 0) <= 260, '%dpx 본문 길이 %s자 (200~260 안)' % (vw, S.get('len')))
        ok(P.get('n') == 4, '%dpx 지면 기사 4개(1면 톱 제외) — 본문 5개 전부 그려짐' % vw)
        ok(P.get('clipped') == 0 and P.get('clamp') == 0, '%dpx 기사 본문이 잘리지 않는다(클램프·고정 높이 없음)' % vw)
        ok(P.get('leadClipped') is False and P.get('leadChars', 0) >= 200, '%dpx 1면 톱 본문 전문 %s자 그대로' % (vw, P.get('leadChars')))
        ok(P.get('over') == 0 and S.get('docOver') == 0, '%dpx 가로 넘침 0 (지면 %s · 문서 %s)' % (vw, P.get('over'), S.get('docOver')))
        ok(T.get('hasMore') and T.get('moreVisible'), '%dpx 홈 1면 미리보기 「이어 읽기 ›」가 2줄 클램프에 먹히지 않고 보인다' % vw)
        ok(T.get('over') == 0, '%dpx 미리보기 가로 넘침 0' % vw)
        ok(not pe, '%dpx 페이지 오류 0 %s' % (vw, pe[:2]))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    return 0 if not fails else 1

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
