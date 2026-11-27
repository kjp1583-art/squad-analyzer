# -*- coding: utf-8 -*-
"""⚔ 귀살대 듀얼 스플래시 시험 — (1·2)(3·4)(5·6) 세 그룹이 한 장의 가로 카드에서 번갈아 돈다 (2026-11-27)
합성 시트(가짜 닉네임·PUUID)만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다. build_xlsx·CAST_A 는 web_kisatsu_recent_test 에서 가져온다.

  A 구조 — 6인을 두 명씩 3그룹 · 슬라이드 3장 · 점 3개 · 한 번에 한 장만 보인다
  B 배치 — 왼쪽 반 = 홀수 순위(1/3/5), 오른쪽 반 = 짝수 순위(2/4/6) · 각 반에 순위 배지·소환사명·승률·전적·🔥폼
  C 배경 — 두 반 모두 그 사람 모스트 챔피언 스플래시(상현·하현 카드와 같은 mainSplashOf)가 깔린다
  D 전환 — 점을 누르면 그 그룹으로 바뀌고, 시간이 지나면 자동으로 다음 그룹으로 넘어간다
  E 클릭 — 반쪽을 누르면 그 소환사 전적 카드가 열린다
  F 반응형 — 360·1280 모두 글자 잘림·겹침·가로 넘침 0
  G 폴백 — 6명이 안 되면 마지막 그룹은 한 명만, 빈 반은 '다음 달에 만나요' · 오류 0
  H 동작 줄이기 — prefers-reduced-motion 이면 자동 순환이 아예 켜지지 않는다

  python3 tests/web_kisatsu_dual_test.py
"""
import asyncio, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
from web_kisatsu_recent_test import build_xlsx, CAST_A

CHAMPS = ['가렌', '아리', '이즈리얼', '쓰레쉬', '리신', '제드']

DUMP = r"""(()=>{
  const c=document.querySelector('.ksd');
  if(!c) return {ok:false};
  const rect=e=>{const r=e.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}};
  const txt=e=>e?e.textContent.replace(/\s+/g,' ').trim():'';
  const slides=[...c.querySelectorAll('.ksd-s')].map(s=>{
    const halfEls=[...s.querySelectorAll('.ksd-half')];
    return {
      on:s.classList.contains('on'),
      halves:halfEls.map(h=>{
        const side=h.classList.contains('l')?'l':(h.classList.contains('r')?'r':'?');
        const bg=h.parentElement.querySelector('.ksd-bg.'+side);
        return {side, empty:h.classList.contains('empty'), role:h.getAttribute('role'), no:txt(h.querySelector('.ksd-no')),
          nm:txt(h.querySelector('.ksd-nm')), wr:txt(h.querySelector('.ksd-wr')), rec:txt(h.querySelector('.ksd-rec')),
          hot:txt(h.querySelector('.ksd-hot')), title:h.getAttribute('title')||'',
          bg:bg?(bg.getAttribute('src')||''):'', box:rect(h)};
      })
    };
  });
  const act=c.querySelector('.ksd-s.on');
  const tight=[...c.querySelectorAll('.ksd-s.on .ksd-nm,.ksd-s.on .ksd-wr,.ksd-s.on .ksd-rec,.ksd-s.on .ksd-hot,.ksd-s.on .ksd-no')]
    .map(e=>({c:e.className, clip:e.scrollWidth>e.clientWidth+1, txt:txt(e)}));
  const a=act?rect(act):null;
  const out=[...c.querySelectorAll('.ksd-s.on .ksd-half')].filter(h=>{const r=rect(h);return a&&(r.l<a.l-1||r.r>a.r+1)}).length;
  // 반쪽 안쪽 글자가 반쪽 밖으로 나가는지
  const esc=[...c.querySelectorAll('.ksd-s.on .ksd-half')].map(h=>{const hr=rect(h);
    return [...h.querySelectorAll('.ksd-nm,.ksd-wr,.ksd-rec,.ksd-hot,.ksd-no')].filter(e=>{const r=rect(e);
      return r.l<hr.l-1||r.r>hr.r+1||r.t<hr.t-1||r.b>hr.b+1}).length}).reduce((x,y)=>x+y,0);
  // 위(배지)와 아래(이름·기록) 덩어리가 서로 겹치는지
  const collide=[...c.querySelectorAll('.ksd-s.on .ksd-half')].filter(h=>{const t=h.querySelector('.ksd-top'),b=h.querySelector('.ksd-bot');
    if(!t||!b) return false; const tr=rect(t),br=rect(b); return tr.b>br.t+1}).length;
  const de=document.documentElement;
  return {ok:true, slides, dots:[...c.querySelectorAll('.ksd-dots i')].map(d=>d.classList.contains('on')),
    n:slides.length, tight, out, esc, collide, i:c.dataset.i, sw:de.scrollWidth, cw:de.clientWidth,
    ks:KISATSU.map(x=>({name:x.name,wr:Math.round(x.wr),w:x.w,loss:x.g-x.w,f30g:x.f30g,f30w:x.f30w})),
    halfTitles:[...c.querySelectorAll('.ksd-s .ksd-half')].map(h=>h.getAttribute('title')||'')};
})()"""

PAGE_JS = r"""(()=>{const de=document.documentElement;return {sw:de.scrollWidth,cw:de.clientWidth,
  hidden:document.hidden, rm:matchMedia('(prefers-reduced-motion: reduce)').matches};})()"""

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def run(cast, vp, label, interact=False):
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, cast)
        async def scene(pg):
            o = {}
            await pg.evaluate("()=>{try{localStorage.setItem('sgg_welcome_off','1')}catch(e){}}")
            await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(800)
            # 자동 순환이 시험 도중에 끼어들지 않게 멀리 미뤄 둔다
            await pg.evaluate("()=>{const c=document.querySelector('.ksd'); if(c) c.dataset.next=Date.now()+600000}")
            o['base'] = await pg.evaluate(DUMP)
            o['page'] = await pg.evaluate(PAGE_JS)
            if interact:
                # C 배경 — 스플래시 표를 채운 뒤 다시 그려서 실제 DOM 배경을 확인한다(실제 사이트에선 ddragon 이 채운다)
                o['splash'] = await pg.evaluate("""(chs)=>{
                  for(const ch of chs){ SPLASHMAP[ch]='https://ddragon.test/cdn/img/champion/splash/'+encodeURIComponent(ch)+'_0.jpg'; }
                  go('home');
                  return null;}""", CHAMPS)
                await pg.wait_for_timeout(900)
                await pg.evaluate("()=>{const c=document.querySelector('.ksd'); if(c) c.dataset.next=Date.now()+600000}")
                o['splash'] = await pg.evaluate("""(()=>{
                  const c=document.querySelector('.ksd'); if(!c) return null;
                  const want=KISATSU.map(e=>ksdSplashOf(e.name)), plain=KISATSU.map(e=>mainSplashOf(e.name));
                  const imgs=[...c.querySelectorAll('img.ksd-bg')];
                  const got=imgs.map(e=>e.getAttribute('src')||'');
                  const fb=imgs.map(e=>e.getAttribute('data-fb')||'');
                  return {want, plain, got, fb, n:imgs.length,
                    wantCentered:want.length>0&&want.every(u=>u.indexOf('/img/champion/centered/')>=0),
                    fbOk:fb.every(u=>/\/img\/champion\/splash\//.test(u)),
                    fbIsPlain:fb.every((u,i)=>u===plain[i]),
                    fbUsed:got.every((u,i)=>u===fb[i])};})()""")
                # D 점 클릭 → 3번째 그룹
                await pg.click('.ksd-dots i:nth-child(3)')
                await pg.wait_for_timeout(1300)
                o['afterDot'] = await pg.evaluate(DUMP)
                # E 반쪽 클릭 → 전적 카드
                await pg.evaluate("()=>{const c=document.querySelector('.ksd'); c.dataset.next=Date.now()+600000;}")
                nm = await pg.evaluate("()=>document.querySelector('.ksd-s.on .ksd-half.l .ksd-nm').textContent")
                await pg.click('.ksd-s.on .ksd-half.l')
                await pg.wait_for_timeout(700)
                o['click'] = await pg.evaluate("""(nm)=>({pcard:!!document.querySelector('#pcard .pc-title, #pcard .pc-name, #pcard h2, #pcard .pc'),
                  html:(document.getElementById('pcard')||{}).innerHTML||'', has:((document.getElementById('pcard')||{}).innerHTML||'').indexOf(nm)>=0,
                  bodyOv:getComputedStyle(document.body).overflow, nm})""", nm)
                await pg.evaluate("()=>closePlayerCard()")
                await pg.wait_for_timeout(300)
            return o
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, viewport=vp, after=scene, timeout_s=300)
    return res['after'], res['meta']['log']


async def main():
    # ── 360(폰) · 상호작용
    o, log = await run(CAST_A, (360, 740), '360', interact=True)
    b = o['base']
    ok(b['ok'], 'A 귀살대 듀얼 스플래시 카드가 그려졌다')
    ok(b['n'] == 3 and len(b['dots']) == 3, 'A 6인 → 슬라이드 3장 · 점 3개 (실제 %d장 %d개)' % (b['n'], len(b['dots'])))
    ok(b['slides'][0]['on'] and not b['slides'][1]['on'] and not b['slides'][2]['on'], 'A 처음엔 첫 그룹 한 장만 보인다')
    ranks = [(h['side'], h['no']) for s in b['slides'] for h in s['halves']]
    ok(ranks == [('l', '1위'), ('r', '2위'), ('l', '3위'), ('r', '4위'), ('l', '5위'), ('r', '6위')],
       'B 왼쪽 홀수 · 오른쪽 짝수 순위 배치 %s' % ranks)
    ok(all(h['role'] == 'button' and h['nm'] for s in b['slides'] for h in s['halves']), 'B 각 반이 눌러지는 버튼이고 소환사명이 있다')
    ks = b['ks']
    ok(len(ks) == 6, 'B 귀살대 6인 (실제 %d)' % len(ks))
    for g in range(3):
        for side, idx in (('l', 0), ('r', 1)):
            h = b['slides'][g]['halves'][idx]; k = ks[g * 2 + idx]
            ok(h['nm'] == k['name'].split('#')[0] and h['wr'] == '%d%%' % k['wr']
               and h['rec'] == '%d승%d패' % (k['w'], k['loss']),
               'B %d번째 그룹 %s반 = %s %d%% · %d승%d패 (실제 %s %s %s)' % (g + 1, '왼' if side == 'l' else '오', h['nm'], k['wr'], k['w'], k['loss'], h['nm'], h['wr'], h['rec']))
    hot = [h['hot'] for s in b['slides'] for h in s['halves']]
    want_hot = ['🔥 %d%%' % int(k['f30w'] / k['f30g'] * 100 + 0.5) if k['f30g'] >= 5 else '' for k in ks]
    ok(hot == want_hot and any(hot), 'B 🔥 최근 30일 폼이 5판 이상인 사람에게만 붙는다 %s' % hot)
    ok(all('최근 90일' in t and '상현 맞라이너' in t for t in b['halfTitles']), 'B 반쪽 툴팁에 90일·맞라이너 기준이 남아 있다 %r' % b['halfTitles'][:1])
    ok(not any(t['clip'] for t in b['tight']), 'F 360 글자 잘림 없음 %s' % [t for t in b['tight'] if t['clip']])
    ok(b['out'] == 0 and b['esc'] == 0 and b['collide'] == 0,
       'F 360 반쪽·글자가 카드 밖으로 안 나가고 위/아래 덩어리가 안 겹친다 (out %d esc %d collide %d)' % (b['out'], b['esc'], b['collide']))
    ok(b['sw'] <= b['cw'] + 1, 'F 360 페이지 가로 넘침 0 %s' % {'sw': b['sw'], 'cw': b['cw']})
    ok(not log['pageerror'] and not log['console'], 'G 페이지 오류·콘솔 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))

    sp = o['splash']
    ok(sp and sp['n'] == 6 and sp['wantCentered'] and all(sp['want']),
       'C 배경 주소 = 챔피언이 가운데인 centered 원화(반쪽마다 한 장) %s' % (sp and sp['want'][:2],))
    ok(sp and sp['fbOk'] and sp['fbIsPlain'] and sp['fbUsed'],
       'C centered 가 없으면 원본 스플래시로 되돌아간다(시험 환경은 ddragon 이 막혀 폴백이 실제로 동작) fb=%s' % (sp and sp['fb'][:2],))

    ad = o['afterDot']
    ok(ad['i'] == '2' and ad['slides'][2]['on'] and ad['dots'] == [False, False, True],
       'D 점을 누르면 그 그룹으로 바뀐다 (i=%s dots=%s)' % (ad['i'], ad['dots']))
    ok(ad['slides'][2]['halves'][0]['no'] == '5위' and ad['slides'][2]['halves'][1]['no'] == '6위', 'D 3번째 점 = 5·6위 그룹')

    cl = o['click']
    ok(cl['has'] and cl['bodyOv'] == 'hidden', 'E 반쪽을 누르면 그 소환사(%s) 전적 카드가 열린다' % cl['nm'])

    # 자동 순환 — 점을 누르지 않아도 시간이 지나면 다음 그룹으로 넘어간다
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, CAST_A)
        async def auto(pg):
            await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(600)
            i0 = await pg.evaluate("()=>document.querySelector('.ksd').dataset.i")
            await pg.wait_for_timeout(6400)
            return {'i0': i0, 'i1': await pg.evaluate("()=>document.querySelector('.ksd').dataset.i"),
                    'hidden': await pg.evaluate("()=>document.hidden")}
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, viewport=(1280, 800), after=auto, timeout_s=300)
    a = res['after']
    ok((not a['hidden']) and a['i0'] == '0' and a['i1'] == '1', 'D 5.2초 뒤 자동으로 다음 그룹 (i %s → %s, hidden=%s)' % (a['i0'], a['i1'], a['hidden']))

    # ── 1280(PC)
    o2, log2 = await run(CAST_A, (1280, 800), '1280')
    b2 = o2['base']
    ok(b2['n'] == 3 and b2['out'] == 0 and b2['esc'] == 0 and b2['collide'] == 0,
       'F 1280 반쪽·글자 배치 정상 (out %d esc %d collide %d)' % (b2['out'], b2['esc'], b2['collide']))
    ok(not any(t['clip'] for t in b2['tight']) and b2['sw'] <= b2['cw'] + 1, 'F 1280 글자 잘림·가로 넘침 0 %s' % b2['tight'])
    ok(not log2['pageerror'] and not log2['console'], 'F 1280 페이지 오류·콘솔 0')

    # ── G 폴백 — 3명뿐일 때 (마지막 그룹은 한 명 + 빈 반)
    o3, log3 = await run(CAST_A[:2], (360, 740), '3명')
    b3 = o3['base']
    ok(b3['ok'] and b3['n'] == 2, 'G 3명이면 슬라이드 2장 (실제 %d)' % b3['n'])
    ok(b3['slides'][1]['halves'][1]['empty'] and b3['slides'][1]['halves'][0]['nm'],
       'G 마지막 그룹은 한 명만 그리고 나머지 반은 비운다 %s' % [h['empty'] for h in b3['slides'][1]['halves']])
    ok(b3['out'] == 0 and b3['esc'] == 0 and b3['sw'] <= b3['cw'] + 1, 'G 폴백에서도 배치·가로 넘침 0')
    ok(not log3['pageerror'], 'G 폴백 페이지 오류 0 %s' % (log3['pageerror'][:1],))

    # ── H 동작 줄이기 — 자동 순환 정지
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, CAST_A)
        async def rm(pg):
            await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(500)
            await pg.emulate_media(reduced_motion='reduce'); await pg.wait_for_timeout(300)
            r = await pg.evaluate("""(()=>{ try{clearInterval(KSD_T)}catch(e){} KSD_T=null; ksdStart();
              const i0=document.querySelector('.ksd').dataset.i;
              document.querySelector('.ksd').dataset.next=0; ksdTick();
              return {timer:KSD_T===null, i0, i1:document.querySelector('.ksd').dataset.i,
                      rm:matchMedia('(prefers-reduced-motion: reduce)').matches};})()""")
            await pg.wait_for_timeout(1200)
            r['i2'] = await pg.evaluate("()=>document.querySelector('.ksd').dataset.i")
            return r
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, viewport=(360, 740), after=rm, timeout_s=300)
    r = res['after']
    ok(r['rm'] and r['timer'], 'H 동작 줄이기면 자동 순환 타이머를 켜지 않는다 %s' % r)
    ok(r['i0'] == r['i1'] == r['i2'] == '0', 'H 동작 줄이기에선 자동으로 안 넘어간다 %s' % r)

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
