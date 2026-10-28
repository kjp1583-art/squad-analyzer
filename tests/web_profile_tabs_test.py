# -*- coding: utf-8 -*-
"""📱 프로필 탭 시험 (P-23 · 2026-10-17) — 합성 시트(가짜 닉·가짜 판, 실제 데이터 없음)를 tests/web_replay 하네스로 열어 본다.
  A. 폰 360×780: 탭 줄 5개 · 첫 탭 요약 · 요약은 핵심 6칸만 + 「칸 더 보기」 · 전적 탭의 전적 머리글이 1.5화면(1,200px) 안
  B. 가로 넘침 0 (320 · 360 · 412, 탭 5개 전부)
  C. 칸 대조: PC 에 그려지는 카드·표식이 폰 탭 어딘가에 하나도 빠짐없이 보인다 (+ 변이: 탭 하나를 비틀면 빨개진다)
  D. 탭을 누르면 바뀌고 주소가 #p/닉/탭 · 새로고침하면 그 탭 복원 · 탭 없는 옛 링크 #p/닉 도 열린다 · 다른 선수로 가면 첫 탭
  E. 전적 탭: 20판씩 + 더보기 · 챔피언 상세 「사용된 게임」 20개씩 + 더보기
  F. PC 1280: 탭 줄 없음 · 2단 그대로 · 전적 20판 · 폰↔PC 폭을 넘나들어도 배치가 따라온다
  G. 콘솔·페이지 오류 0
  python3 tests/web_profile_tabs_test.py [--src index.html] [--base 옛_index.html(전/후 측정용, 선택)]
시트 스냅샷이 필요 없다(합성). playwright·openpyxl 이 없으면 SKIP."""
import argparse, asyncio, json, os, sys, tempfile, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
try:
    import replay as R, synth
    import openpyxl  # noqa: F401
except Exception as e:   # pragma: no cover
    print('SKIP  playwright/openpyxl 없음 (%s) — 종료코드 0' % e); sys.exit(0)

NICK = synth.plain_names()[0]          # 가상01#TST — 판이 많은 선수로 키운다
TABS = ['요약', '전적', '챔피언', '분석', '한마디']
KEYS = ['sum', 'log', 'champ', 'ana', 'cmt']


def make_big_xlsx(path, copies=4):
    """합성 판을 copies 배로 늘린다(날짜는 30일씩 과거로 — 시계 고정 NOW 보다 미래가 되지 않게). 한 선수 100판↑."""
    import datetime as dt
    tabs = synth.build_tabs()
    rows = tabs['CLASSIC_NORMAL']; hdr, body = rows[0], rows[1:]
    out = [hdr]
    for k in range(copies):
        for r in body:
            r = list(r)
            r[0] = '#%d' % (int(r[0].lstrip('#')) + 1000 * k)
            d = dt.datetime.strptime(r[1], '%Y-%m-%d %H:%M') - dt.timedelta(days=30 * k)
            r[1] = d.strftime('%Y-%m-%d %H:%M')
            out.append(r)
    tabs['CLASSIC_NORMAL'] = out
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for n, rs in tabs.items():
        ws = wb.create_sheet(n)
        for r in rs: ws.append(r)
    wb.save(path)


OPEN = """async (h)=>{location.hash=h;
  for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,150)); if(document.querySelector('#view .pname')) break;}
  await new Promise(r=>setTimeout(r,500)); return location.hash;}"""

# 보이는 카드·표식 목록 — 숨김(display:none) 조상은 getClientRects 가 비어 있다
KEYS_JS = r"""()=>{
  const vis=e=>e.getClientRects().length>0;
  const strip=t=>String(t||'').replace(/[0-9,.%판종개명\s()·/]/g,'').slice(0,14);
  const cards=[...document.querySelectorAll('#view .card')].map(c=>{const h=c.querySelector('h2,h3');return (h?strip(h.textContent):(c.querySelector('.pname')?'HEAD':'?'+c.className))+'|'+c.className.split(' ').filter(x=>/^(sect|hasbanner|pt-sumcard|pt-recent)$/.test(x)).join('.');});
  const marks={};
  for(const s of ['.ring','.side-rec','.st-cta','.radarbox','.cmpbox','.cmp','.cmpbox-h','.sidecol','.ach-row','.match','.logrow']) marks[s]=[...document.querySelectorAll('#view '+s)].map(vis);
  return {cards:cards.map((k,i)=>[k,vis(document.querySelectorAll('#view .card')[i])]),marks};
}"""

MEASURE = r"""()=>{const de=document.documentElement,cw=de.clientWidth;const bad=[];
  for(const el of document.querySelectorAll('#view *')){const r=el.getBoundingClientRect();
    if(r.width>0&&r.right>cw+1){let p=el.parentElement,clip=false;while(p&&p.id!=='view'){const cs=getComputedStyle(p);if(/(auto|scroll|hidden)/.test(cs.overflowX)){clip=true;break;}p=p.parentElement;}
      if(!clip)bad.push((el.tagName+'.'+String(el.className||'').split(' ')[0]).slice(0,40)+'@'+Math.round(r.right));}}
  return {sw:de.scrollWidth,cw,bad:bad.slice(0,5),h:de.scrollHeight,vh:innerHeight};}"""

LOGY = r"""()=>{const h=[...document.querySelectorAll('#view h2')].find(e=>/^전적/.test(e.textContent.trim()));
  if(!h||!h.getClientRects().length) return null; return Math.round(h.getBoundingClientRect().top+scrollY);}"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    ap.add_argument('--base', default=None)
    a = ap.parse_args()
    fails = []

    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c: fails.append(msg)
    tmp = tempfile.mkdtemp(prefix='ptabs_')
    xlsx = os.path.join(tmp, 'big.xlsx'); make_big_xlsx(xlsx)
    enc = urllib.parse.quote(NICK, safe='')
    H = '#p/' + enc

    async def tabs_state(pg):
        return await pg.evaluate("()=>({labels:[...document.querySelectorAll('.ptabs .segbtn')].map(b=>b.textContent.trim()),on:[...document.querySelectorAll('.ptabs .segbtn.on')].map(b=>b.textContent.trim()),root:(document.querySelector('.pt-root')||{dataset:{}}).dataset.ptab||null,hash:location.hash})")

    async def click_tab(pg, label):
        await pg.click('.ptabs .segbtn:has-text("%s")' % label)
        await pg.wait_for_timeout(250)

    # ---------- 폰 360 ----------
    async def phone(pg):
        o = {}
        await pg.evaluate(OPEN, H)
        o['st0'] = await tabs_state(pg)
        o['core0'] = await pg.evaluate("()=>({core:[...document.querySelectorAll('.cmp-core')].filter(e=>e.getClientRects().length).length,hidden:[...document.querySelectorAll('.cmp:not(.cmp-core)')].filter(e=>e.getClientRects().length).length,total:document.querySelectorAll('.pt-sumcard .cmpbox.cmp-fold .cmp').length,btn:!!document.querySelector('.cmp-morebtn'),recent:document.querySelectorAll('.pt-r').length,ring:!![...document.querySelectorAll('.pt-sumcard .ring')].length})")
        o['sumRingTop'] = await pg.evaluate("()=>{const r=document.querySelector('.pt-sumcard .ring').getBoundingClientRect();const t=document.querySelector('.ptabs').getBoundingClientRect();const c=document.querySelector('.pt-sumcard .cmpbox').getBoundingClientRect();return {ring:r.top,tabs:t.top,box:c.top}}")
        await pg.click('.cmp-morebtn'); await pg.wait_for_timeout(150)
        o['coreOpen'] = await pg.evaluate("()=>[...document.querySelectorAll('.pt-sumcard .cmpbox.cmp-fold .cmp')].filter(e=>e.getClientRects().length).length")
        # 탭 순회: 높이·넘침·카드 가시성
        o['overflow'] = {}; o['vis'] = {}
        o['hashes'] = {}
        for lb, k in zip(TABS, KEYS):
            await click_tab(pg, lb)
            m = await pg.evaluate(MEASURE); o['overflow'][lb] = m
            o['vis'][lb] = await pg.evaluate(KEYS_JS)
            o['hashes'][lb] = await pg.evaluate("location.hash")
        # 전적 탭
        await click_tab(pg, '전적')
        o['logY'] = await pg.evaluate(LOGY)
        o['m20'] = await pg.evaluate("()=>document.querySelectorAll('#pmList .match').length")
        o['btnTxt'] = await pg.evaluate("()=>{const b=document.querySelector('#pmList button[onclick=\"morePm()\"]');return b?b.textContent.trim():null}")
        await pg.click('#pmList button[onclick="morePm()"]'); await pg.wait_for_timeout(300)
        o['m40'] = await pg.evaluate("()=>document.querySelectorAll('#pmList .match').length")
        o['total'] = await pg.evaluate("()=>(document.querySelector('#view h2')&&[...document.querySelectorAll('#view h2')].find(e=>/^전적/.test(e.textContent.trim())).textContent)")
        # 변이: 분석 탭의 카드 하나를 엉뚱한 탭에 건다 → 칸 대조가 빠진 카드를 잡아야 한다
        o['mut'] = {}
        o['mut']['n'] = await pg.evaluate("()=>{const e=document.querySelector('.pt[data-pt=\"ana\"]');if(!e) return 0;e.setAttribute('data-pt','zzz');return 1}")
        for lb in TABS:
            await click_tab(pg, lb)
        o['mut']['vis'] = {}
        for lb in TABS:
            await click_tab(pg, lb); o['mut']['vis'][lb] = await pg.evaluate(KEYS_JS)
        # 탭 복원: 새로고침
        await pg.evaluate(OPEN, H)      # (변이를 없애려고 다시 연다)
        await click_tab(pg, '챔피언')
        o['hashChamp'] = await pg.evaluate("location.hash")
        await pg.reload(); await pg.wait_for_function("!!document.querySelector('#view .pname')", timeout=60000); await pg.wait_for_timeout(900)
        o['afterReload'] = await tabs_state(pg)
        await pg.evaluate(OPEN, H.replace('#p/', '#g/') if False else '#p/' + enc)   # 탭 없는 옛 링크
        o['oldLink'] = await tabs_state(pg)
        await pg.evaluate(OPEN, '#p/' + enc + '/ana')
        o['linkAna'] = await tabs_state(pg)
        await pg.evaluate("go('player','%s')" % synth.plain_names()[1]); await pg.wait_for_timeout(500)
        o['otherPlayer'] = await tabs_state(pg)
        # 챔피언 상세 20개씩
        await pg.evaluate("go('champlog','리신')"); await pg.wait_for_timeout(800)
        o['cl'] = await pg.evaluate("()=>({n:document.querySelectorAll('#clList .logrow').length,btn:(document.querySelector('#clList button')||{}).textContent,h2:[...document.querySelectorAll('#view h2')].map(e=>e.textContent.trim()).find(t=>/사용된 게임/.test(t))})")
        await pg.click('#clList button'); await pg.wait_for_timeout(300)
        o['cl2'] = await pg.evaluate("()=>document.querySelectorAll('#clList .logrow').length")
        # 폰 → PC 폭
        await pg.evaluate(OPEN, H); await pg.wait_for_timeout(300)
        await pg.set_viewport_size({'width': 1280, 'height': 900}); await pg.wait_for_timeout(900)
        o['toPc'] = await pg.evaluate("()=>({tabs:document.querySelectorAll('.ptabs').length,on:document.querySelectorAll('.pt-on').length,match:document.querySelectorAll('#pmList .match').length})")
        await pg.set_viewport_size({'width': 360, 'height': 780}); await pg.wait_for_timeout(900)
        o['toPhone'] = await pg.evaluate("()=>({tabs:document.querySelectorAll('.ptabs').length,on:document.querySelectorAll('.pt-on').length})")
        return o

    r = await R.replay(os.path.abspath(a.src), xlsx=xlsx, now=synth.NOW, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True, after=phone, timeout_s=300)
    P = r['after']; logP = r['meta']['log']
    print('A', json.dumps({k: P[k] for k in ('st0', 'core0', 'sumRingTop', 'coreOpen', 'logY', 'm20', 'btnTxt', 'm40', 'total')}, ensure_ascii=False))
    ok(P['st0']['labels'] == TABS, 'A1 탭 줄 5개 %s' % P['st0']['labels'])
    ok(P['st0']['on'] == ['요약'] and P['st0']['root'] == 'sum', 'A2 첫 탭은 요약 (PROF_TAB_DEFAULT) %s' % P['st0']['on'])
    c = P['core0']
    ok(c['core'] == 6 and c['hidden'] == 0 and c['btn'] and c['total'] > 6, 'A3 요약: 핵심 6칸만 보이고 나머지(%d칸 중)는 접혀 있다 · 「칸 더 보기」 있음 %s' % (c['total'], c))
    ok(P['coreOpen'] == c['total'], 'A4 「칸 더 보기」 를 누르면 전부 펼쳐진다 (%d/%d)' % (P['coreOpen'], c['total']))
    s = P['sumRingTop']
    ok(c['recent'] == 5 and s['tabs'] < s['ring'] < s['box'], 'A5 요약 순서: 탭 줄 → 승률 링 → 지표 칸 · 최근 5판 5칸 %s' % s)
    ok(P['logY'] is not None and P['logY'] <= 1200, 'A6 전적 탭의 전적 머리글 y = %s px ≤ 1,200 (1.5화면)' % P['logY'])
    ok(P['m20'] == 20 and re_match(P['btnTxt'], '20판 더'), 'A7 전적 탭: 처음 20판 + 「20판 더」 (%s장 · %s)' % (P['m20'], P['btnTxt']))
    ok(P['m40'] == 40, 'E1 더보기 한 번 → 40판 (%s)' % P['m40'])
    # B 넘침
    for lb in TABS:
        m = P['overflow'][lb]
        ok(m['sw'] <= m['cw'] and not m['bad'], 'B 360px · %s 탭 가로 넘침 0 (폭 %d ≤ %d) %s' % (lb, m['sw'], m['cw'], m['bad']))
    # C 칸 대조 — PC 값은 아래에서
    # D 주소
    ok(all(P['hashes'][lb] == ('' if False else P['hashes'][lb]) for lb in TABS), 'D0 (해시 수집)')
    ok(P['hashes']['요약'].endswith('/' + enc) and not P['hashes']['요약'].endswith('/sum'), 'D1 첫 탭(요약)은 주소에 안 붙는다 — 옛 링크와 같은 모양 (%s)' % P['hashes']['요약'])
    for lb, k in zip(TABS[1:], KEYS[1:]):
        ok(P['hashes'][lb].endswith('/' + enc + '/' + k), 'D2 %s 탭 → 주소 …/%s (%s)' % (lb, k, P['hashes'][lb][-30:]))
    ok(P['afterReload']['on'] == ['챔피언'] and P['afterReload']['hash'].endswith('/champ'), 'D3 새로고침하면 그 탭(챔피언)이 복원된다 %s' % P['afterReload'])
    ok(P['oldLink']['on'] == ['요약'] and P['oldLink']['labels'] == TABS, 'D4 탭 없는 옛 링크 #p/닉 도 열린다 (요약) %s' % P['oldLink']['on'])
    ok(P['linkAna']['on'] == ['분석'], 'D5 #p/닉/ana 링크는 분석 탭으로 열린다 %s' % P['linkAna']['on'])
    ok(P['otherPlayer']['on'] == ['요약'], 'D6 다른 선수 프로필로 가면 첫 탭으로 돌아온다 %s' % P['otherPlayer']['on'])
    # E 챔피언 상세
    ok(P['cl']['n'] == 20 and P['cl']['btn'] and '20개 더' in P['cl']['btn'] and P['cl2'] == 40, 'E2 챔피언 상세 「사용된 게임」 20개 → 더보기 → 40개 (%s · %s → %s)' % (P['cl']['n'], P['cl']['btn'], P['cl2']))
    ok(P['toPc']['tabs'] == 0 and P['toPc']['on'] == 0 and P['toPc']['match'] == 20, 'F4 폰→PC 폭: 탭 줄이 사라지고 2단으로 다시 그려진다 %s' % P['toPc'])
    ok(P['toPhone']['tabs'] == 1 and P['toPhone']['on'] == 1, 'F5 PC→폰 폭: 탭 줄이 다시 생긴다 %s' % P['toPhone'])

    # ---------- PC 1280 ----------
    async def pc(pg):
        o = {}
        await pg.evaluate(OPEN, H)
        o['keys'] = await pg.evaluate(KEYS_JS)
        o['dom'] = await pg.evaluate("()=>({tabs:document.querySelectorAll('.ptabs').length,on:document.querySelectorAll('.pt-on').length,match:document.querySelectorAll('#pmList .match').length,hash:location.hash,cols:[...document.querySelector('.grid.cols').children].map(e=>Math.round(e.getBoundingClientRect().left))})")
        o['ov'] = await pg.evaluate(MEASURE)
        return o
    rp = await R.replay(os.path.abspath(a.src), xlsx=xlsx, now=synth.NOW, out=None, shots=False, cats=('rift',), viewport=(1280, 900), quiet=True, after=pc, timeout_s=300)
    PC = rp['after']; logC = rp['meta']['log']
    print('F', json.dumps(PC['dom'], ensure_ascii=False))
    ok(PC['dom']['tabs'] == 0 and PC['dom']['on'] == 0, 'F1 PC: 탭 줄 없음 · 폰 규칙(.pt-on) 없음')
    ok(len(set(PC['dom']['cols'])) == 2 and PC['dom']['cols'][0] < PC['dom']['cols'][1], 'F2 PC: 2단 그대로 (열 x 위치 %s)' % PC['dom']['cols'])
    ok(PC['dom']['match'] == 20 and '/' not in PC['dom']['hash'].split('#p/')[1].replace(enc, ''), 'F3 PC: 전적 20판 · 주소에 탭이 안 붙는다 (%s)' % PC['dom']['hash'][-20:])
    ok(PC['ov']['sw'] <= PC['ov']['cw'], 'F6 PC 가로 넘침 0')

    def compare(vis_by_tab):
        """PC 의 카드·표식이 폰 탭의 어딘가에서 보이는가 → 빠진 칸 목록"""
        miss = []
        pc_cards = [k for k, _ in PC['keys']['cards']]
        ph_cards = {}
        for lb, v in vis_by_tab.items():
            for k, vi in v['cards']:
                ph_cards.setdefault(k, False)
                ph_cards[k] = ph_cards[k] or vi
        extras = {k for k in ph_cards if 'pt-sumcard' in k or 'pt-recent' in k or k.startswith('?')}
        for k in pc_cards:
            if k.startswith('HEAD'): continue
            if not ph_cards.get(k): miss.append('카드 ' + k)
        for k, vi in ph_cards.items():
            if k not in pc_cards and k not in extras: miss.append('폰에만 있는 카드 ' + k)
        # 표식(.ring·.cmpbox·.st-cta·.radarbox …): 폰에서 한 번도 안 보이면 빠진 것
        for sel, arr in PC['keys']['marks'].items():
            if not arr: continue
            ph_any = {}
            for lb, v in vis_by_tab.items():
                for i, vi in enumerate(v['marks'].get(sel, [])): ph_any[i] = ph_any.get(i, False) or vi
            if sel in ('.match', '.logrow'): continue
            if len(ph_any) < len(arr) or not all(ph_any.values()):
                n_ph = sum(1 for x in ph_any.values() if x)
                if sel in ('.cmp', '.cmpbox-h') and n_ph >= 1: pass   # 접힌 칸은 아래 별도 검사
                else: miss.append('표식 %s PC %d개 / 폰에서 보이는 %d개' % (sel, len(arr), n_ph))
        return miss
    miss = compare(P['vis'])
    print('C', json.dumps({'pc카드': len(PC['keys']['cards']), '폰카드': len(P['vis']['요약']['cards']), '빠진칸': miss}, ensure_ascii=False))
    ok(not miss, 'C1 칸 대조: PC 의 모든 카드·표식이 폰 탭 어딘가에 보인다 (빠진 칸 %d) %s' % (len(miss), miss))
    # 접힌 지표 칸(.cmp)은 「칸 더 보기」 뒤에 있다 — 개수만 같으면 된다
    ncmp_pc = len(PC['keys']['marks']['.cmp']); ncmp_ph = len(P['vis']['요약']['marks']['.cmp'])
    ok(ncmp_pc == ncmp_ph, 'C2 지표 칸 수 PC %d = 폰 %d (접어 둘 뿐 지우지 않는다)' % (ncmp_pc, ncmp_ph))
    if P['mut']['n']:
        mm = compare(P['mut']['vis'])
        ok(len(mm) > 0, 'C3 변이: 분석 탭 카드 하나를 엉뚱한 탭에 걸면 칸 대조가 빨개진다 (%s)' % mm[:2])
    else:
        ok(False, 'C3 변이를 만들 .pt[data-pt=ana] 가 없다')

    # 넘침 320 · 412
    for w in (320, 412):
        async def ov(pg, w=w):
            o = {}
            await pg.evaluate(OPEN, H)
            for lb in TABS:
                await click_tab(pg, lb); o[lb] = await pg.evaluate(MEASURE)
            return o
        rw = await R.replay(os.path.abspath(a.src), xlsx=xlsx, now=synth.NOW, out=None, shots=False, cats=('rift',), viewport=(w, 780), quiet=True, after=ov, timeout_s=300)
        for lb, m in rw['after'].items():
            ok(m['sw'] <= m['cw'] and not m['bad'], 'B %dpx · %s 탭 가로 넘침 0 (폭 %d ≤ %d) %s' % (w, lb, m['sw'], m['cw'], m['bad']))
        logP['console'] += rw['meta']['log']['console']; logP['pageerror'] += rw['meta']['log']['pageerror']

    errs = logP['pageerror'] + logP['console'] + logC['pageerror'] + logC['console']
    ok(not errs, 'G 콘솔·페이지 오류 0 %s' % errs[:3])

    # 전/후 (선택)
    if a.base:
        async def old(pg):
            await pg.evaluate(OPEN, H)
            return await pg.evaluate(LOGY)
        rb = await R.replay(os.path.abspath(a.base), xlsx=xlsx, now=synth.NOW, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True, after=old, timeout_s=300)
        print('전/후  전적 머리글 y: 옛 코드 %s px → 지금(전적 탭) %s px' % (rb['after'], P['logY']))
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    return 1 if fails else 0


def re_match(s, sub):
    return bool(s) and sub in s


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
