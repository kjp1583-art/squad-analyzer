# -*- coding: utf-8 -*-
"""✨ 웹 디자인 퀄리티 상승(1~4번) 시험 — `python3 tests/web_design_polish_test.py --xlsx <시트.xlsx> [--src index.html]`
  (스냅샷이 없으면 SKIP · 종료코드 0)

  1 카드 위계 — 핵심 섹션(.card.core)은 위쪽 하이라이트·그라데이션 표면, 보조 아코디언(details.hc-card)은 낮은 표면
  2 숫자 시각화 — 전적표 숫자 칸이 tabular-nums 이고, 내전 활약·승률에 3px 미니 게이지가 값에 맞는 폭으로 붙는다
  3 폰 360 — 「맨 위로」가 38px 원형이고 전적표 숫자 위에서는 비켜 주며(겹침 0), 카드 안에서 표 7열이 다 보인다
  4 스켈레톤 — renderLoading() 이 shimmer 뼈대를 그린다 · 호버/눌림 트랜지션 · reduced-motion 에서 끔
  + 콘솔 오류 0 · 페이지 가로 넘침 0 (폰·PC)
"""
import argparse, asyncio, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

EVAL_CARDS = r"""() => {
  const core = [...document.querySelectorAll('.hv2 .card.core')];
  const soft = [...document.querySelectorAll('.hv2 details.hc-card')];
  const cs = e => getComputedStyle(e);
  return {
    coreN: core.length,
    coreBg: core.length ? cs(core[0]).backgroundImage : '',
    coreShadow: core.length ? cs(core[0]).boxShadow : '',
    softN: soft.length,
    softBg: soft.length ? cs(soft[0]).backgroundColor : '',
    softShadow: soft.length ? cs(soft[0]).boxShadow : '',
    coreBgColor: core.length ? cs(core[0]).backgroundColor : '',
  };
}"""

EVAL_NUMS = r"""() => {
  const num = e => getComputedStyle(e).fontVariantNumeric;
  const rows = [...document.querySelectorAll('.ranktbl tbody tr')].slice(0, 3);
  const cells = rows.map(tr => [...tr.children]);
  const bars = rows.map(tr => {
    const score = tr.children[1], wr = tr.children[3];
    const sb = score.querySelector('.nbar'), wb = wr.querySelector('.nbar');
    const ratio = b => {
      if (!b) return null;
      const t = b.getBoundingClientRect(), i = b.querySelector('i').getBoundingClientRect();
      return t.width ? +(i.width / t.width * 100).toFixed(1) : null;
    };
    const num = v => parseFloat(String(v).split('/')[0].replace(/[^0-9.]/g, ''));
    return {
      scoreTxt: score.textContent.trim(), scoreNum: num(score.textContent),
      scoreBar: ratio(sb), wrTxt: wr.textContent.trim(), wrNum: num(wr.textContent), wrBar: ratio(wb),
      barH: sb ? +sb.getBoundingClientRect().height.toFixed(1) : null,
    };
  });
  const chips = [...document.querySelectorAll('.kz-corps-wr, .kzc-st b')].slice(0, 6);
  const kzcBar = document.querySelector('.kzc-st .nbar');
  return {
    cellFonts: cells.map(cs => cs.map(e => num(e))),
    bars,
    chipFonts: chips.map(num),
    kzcBar: kzcBar ? +kzcBar.getBoundingClientRect().height.toFixed(1) : null,
    trTransition: rows.length ? getComputedStyle(rows[0]).transitionDuration : null,
  };
}"""

EVAL_FIT = r"""() => {
  const t = document.querySelector('.ranktbl'), c = t.closest('.card'), cs = getComputedStyle(c);
  const t2 = document.querySelector('.champtbl'), c2 = t2 && t2.closest('.card'), cs2 = c2 && getComputedStyle(c2);
  const content = el => el.clientWidth - parseFloat(getComputedStyle(el).paddingLeft) - parseFloat(getComputedStyle(el).paddingRight);
  const de = document.documentElement;
  return {
    roster: {sw: t.scrollWidth, cw: Math.round(content(c)), pad: cs.paddingLeft},
    champ: t2 ? {sw: t2.scrollWidth, cw: Math.round(content(c2))} : null,
    page: {sw: de.scrollWidth, cw: de.clientWidth},
  };
}"""

EVAL_SKL = r"""() => {
  const before = document.getElementById('view').innerHTML.length;
  renderLoading();
  const w = document.querySelector('.skl');
  if (!w) return {ok: false};
  const l = document.querySelector('.skl-l');
  const cs = getComputedStyle(l);
  return {ok: true, blocks: document.querySelectorAll('.skl-card,.skl-hero').length,
          anim: cs.animationName, dur: cs.animationDuration, busy: w.getAttribute('aria-busy'),
          label: w.getAttribute('aria-label') || '', before};
}"""

BTN = r"""() => {
  const b = document.getElementById('toTopBtn');
  if (!b) return null;
  const r = b.getBoundingClientRect(), cs = getComputedStyle(b);
  const cells = [...document.querySelectorAll('.ranktbl tbody td')].filter(e => e.offsetParent);
  const hit = cells.some(e => { const q = e.getBoundingClientRect();
    return !(q.right < r.left || q.left > r.right || q.bottom < r.top || q.top > r.bottom); });
  return {x: r.left, y: r.top, w: Math.round(r.width), h: Math.round(r.height),
          disp: cs.display, op: cs.opacity, pe: cs.pointerEvents, radius: cs.borderRadius, hit,
          dodge: b.classList.contains('dodge'), on: b.classList.contains('on')};
}"""

SCROLL_ROSTER = r"""() => {
  const t = document.querySelector('.ranktbl');
  const r = t.getBoundingClientRect();
  window.scrollTo(0, window.scrollY + r.top - (window.innerHeight - 210));
  return true;
}"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=os.environ.get('WEB_XLSX'))
    ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    a = ap.parse_args()
    if not a.xlsx or not os.path.exists(a.xlsx):
        print('SKIP  시트 스냅샷(--xlsx 또는 WEB_XLSX)이 없어 건너뜁니다'); return 0
    fails = []
    def ok(c, m):
        print(('  ok   ' if c else '  FAIL ') + m)
        if not c: fails.append(m)

    async def scene(pg):
        o = {}
        await pg.evaluate("()=>{try{localStorage.setItem('sgg_welcome_off','1')}catch(e){}}")
        await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(1100)
        o['cards'] = await pg.evaluate(EVAL_CARDS)
        o['nums'] = await pg.evaluate(EVAL_NUMS)
        o['fit'] = await pg.evaluate(EVAL_FIT)
        # 4 스켈레톤 → 원래 화면으로 되돌린다
        o['skl'] = await pg.evaluate(EVAL_SKL)
        await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(700)
        # 3 「맨 위로」 — 전적표가 버튼 자리 아래에 오도록 내린 뒤
        await pg.evaluate(SCROLL_ROSTER); await pg.wait_for_timeout(600)
        o['btnOverTable'] = await pg.evaluate(BTN)
        # 표가 없는 맨 아래에서는 다시 보인다
        await pg.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)"); await pg.wait_for_timeout(600)
        o['btnBottom'] = await pg.evaluate(BTN)
        await pg.evaluate("()=>window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        return o

    for name, vp in (('폰', (360, 780)), ('PC', (1280, 900))):
        res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, now='2026-11-27T09:20:00',
                             shots=False, quiet=True, viewport=vp, after=scene)
        o, log = res['after'], res['meta']['log']
        print('==', name)
        if name == '폰':
            c = o['cards']
            ok(c['coreN'] >= 3 and 'gradient' in c['coreBg'] and c['coreShadow'] != 'none',
               '1 핵심 카드 %d장 · 위쪽 그라데이션 · 하이라이트 그림자' % c['coreN'])
            ok(c['softN'] >= 1 and c['softShadow'] == 'none' and c['softBg'] != c['coreBgColor'],
               '1 보조 아코디언은 낮은 표면(그림자 없음) %s vs %s' % (c['softBg'], c['coreBgColor']))
        n = o['nums']
        ok(all('tabular-nums' in f for row in n['cellFonts'] for f in row[1:4]),
           '2 전적표 숫자 칸 tabular-nums %s' % n['cellFonts'][0][1:5] if n['cellFonts'] else '2 전적표 없음')
        bars = [b for b in n['bars'] if b['scoreBar'] is not None and b['wrBar'] is not None]
        ok(len(bars) >= 2 and all(abs(b['scoreBar'] - b['scoreNum']) <= 2 and abs(b['wrBar'] - b['wrNum']) <= 2 for b in bars),
           '2 게이지 폭이 값과 일치 %s' % [(b['scoreNum'], b['scoreBar'], b['wrNum'], b['wrBar']) for b in bars])
        ok(all(b['barH'] and 2 <= b['barH'] <= 4 for b in bars), '2 게이지 높이 3px %s' % [b['barH'] for b in bars])
        ok(all(f == 'tabular-nums' for f in n['chipFonts']) if n['chipFonts'] else True,
           '2 순위 칩 숫자 tabular-nums %s' % n['chipFonts'])
        ok(n['kzcBar'] is not None and 2 <= n['kzcBar'] <= 4, '2 최강 12인 카드 승률 게이지 %s' % n['kzcBar'])
        ok(n['trTransition'] not in (None, '0s'), '4 표 행 호버 트랜지션 %s' % n['trTransition'])
        s = o['skl']
        ok(s['ok'] and s['blocks'] >= 5 and s['anim'] == 'skl-shine' and s['busy'] == 'true',
           '4 로딩 스켈레톤 %s' % (s and {k: s[k] for k in ('blocks', 'anim', 'dur', 'busy')}))
        f = o['fit']
        ok(f['page']['sw'] <= f['page']['cw'] + 1, '3 페이지 가로 넘침 0 %s' % f['page'])
        ok(f['roster']['sw'] <= f['roster']['cw'] + 1, '3 전적표가 카드 안에 %s' % f['roster'])
        if f['champ']: ok(f['champ']['sw'] <= f['champ']['cw'] + 1, '3 챔피언표가 카드 안에 %s' % f['champ'])
        if name == '폰':
            b, bb = o['btnOverTable'], o['btnBottom']
            ok(b is not None and b['w'] <= 40 and b['h'] <= 40 and '50%' in b['radius'],
               '3 「맨 위로」 38px 원형 %s' % (b and {k: b[k] for k in ('w', 'h', 'radius')}))
            ok(b is not None and b['on'] and (not b['hit'] or b['op'] == '0' or b['disp'] == 'none' or b['pe'] == 'none'),
               '3 전적표 숫자 위에서 겹치지 않는다(hit=%s op=%s dodge=%s)' % (b and b['hit'], b and b['op'], b and b['dodge']))
            ok(bb is not None and bb['on'] and bb['op'] == '1' and bb['w'] > 0,
               '3 표가 없을 땐 다시 보인다 %s' % (bb and {k: bb[k] for k in ('on', 'op', 'hit')}))
        else:
            b = o['btnOverTable']
            ok(b is not None and b['disp'] == 'none', '3 PC 에서는 숨김 %s' % (b and b['disp']))
        ok(not log['pageerror'] and not log['console'], '콘솔 오류 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))

    # 3 폭 412(안드로이드 기본 폭) — 전적표가 카드 밖으로 넘치지 않는다(2026-11-27 이전 425 > 350)
    async def fit412(pg):
        await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(900)
        return await pg.evaluate(EVAL_FIT)
    res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, now='2026-11-27T09:20:00', shots=False, quiet=True,
                         viewport=(412, 900), after=fit412)
    f = res['after']
    ok(f['roster']['sw'] <= f['roster']['cw'] + 1 and f['page']['sw'] <= f['page']['cw'] + 1,
       '3 412px 전적표·페이지 가로 넘침 0 %s' % f['roster'])

    # 4 reduced-motion — 애니메이션/전환을 끈다
    async def rm(pg):
        await pg.emulate_media(reduced_motion='reduce')
        return await pg.evaluate("""()=>{const r=document.querySelector('.kzrow')||document.querySelector('.ranktbl tbody tr');
          const c=document.querySelector('.card.core');
          return {tr:r?getComputedStyle(r).transitionDuration:null, skl:(()=>{renderLoading(); const s=document.querySelector('.skl-l'); const v=s?getComputedStyle(s).animationName:'none'; go('home'); return v;})()};}""")
    res = await R.replay(os.path.abspath(a.src), xlsx=a.xlsx, now='2026-11-27T09:20:00', shots=False, quiet=True,
                         viewport=(1280, 900), after=rm)
    r = res['after']
    ok(r['tr'] in ('0s', '0s, 0s', None) or all(x.strip() == '0s' for x in (r['tr'] or '').split(',')), '4 reduced-motion 전환 끔 %s' % r['tr'])

    print('ALL PASS' if not fails else 'FAIL %d' % len(fails))
    return 1 if fails else 0

sys.exit(asyncio.run(main()))
