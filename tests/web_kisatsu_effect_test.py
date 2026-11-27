# -*- coding: utf-8 -*-
"""⚔ 귀살대 이펙트 시험 — 전적 팝업·개인 전적 페이지에 상현/하현처럼 테마 연출 (2026-11-27
사장님 「귀살대도 상현하현처럼 전적카드에 이펙트 추가해줘」)
합성 시트(가짜 닉네임·PUUID)만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다.

  A 전적 팝업 — 귀살대원이면 kz-kis 테두리 글로우(청록) · 鬼殺隊 워터마크 · 물빛 입자 · ⚔ 귀살대 N위 칩
  B 우선순위 — 상현/하현이면 기존 테마(kz-up/kz-low)가 그대로 이기고 귀살대 연출은 붙지 않는다
  C 개인 전적 페이지 — kz-prof kz-kis · 鬼殺隊 워터마크 · 청록 후광·빛살 · `⚔ 귀살대 · N위` 엠블럼
  D 상현 개인 페이지는 그대로 `🩸 십이귀월 · 상현 N` 엠블럼
  E '동작 줄이기'면 테두리 맥동을 끈다 · 페이지 오류 0

  python3 tests/web_kisatsu_effect_test.py
"""
import asyncio, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
from web_kisatsu_recent_test import build_xlsx, CAST_A

SANGHYUN_1 = '상현01#T'

MODAL = r"""((nm)=>{
  openPlayerCard(nm);
  const c=document.querySelector('.tbm-card');
  if(!c) return {ok:false};
  const cs=getComputedStyle(c), fx=c.querySelector('.tbm-fx'), kj=c.querySelector('.tbm-kj'), bn=c.querySelector('.tbm-banner');
  const sub=c.querySelector('.tbm-sub');
  return {ok:true, cls:c.className, border:cs.borderColor, anim:cs.animationName, dur:cs.animationDuration,
    fx:!!fx, fxBg:fx?getComputedStyle(fx).backgroundImage:'', kj:kj?kj.textContent:'', kjColor:kj?getComputedStyle(kj).color:'',
    chip:sub?(sub.textContent.replace(/\s+/g,' ').trim()):'', firstShadow:sub&&sub.firstElementChild?getComputedStyle(sub.firstElementChild).boxShadow:'',
    name:(c.querySelector('.tbm-nm b')||{}).textContent||'', banner:!!bn};
})"""

PROF = r"""((nm)=>{
  go('player', nm);
  const c=document.querySelector('.card.kz-prof');
  if(!c) return {ok:false};
  const cs=getComputedStyle(c), em=c.querySelector('.kizuki-emblem'), kj=c.querySelector('.kzp-kj'),
        fx=c.querySelector('.kzp-fx'), rays=c.querySelector('.kzp-rays'), nmEl=c.querySelector('.pname');
  return {ok:true, cls:c.className, border:cs.borderColor, anim:cs.animationName,
    emCls:em?em.className:null, cap:em?(em.querySelector('.kz-cap')||{}).textContent||'':null,
    emSvg:em?!!em.querySelector('svg'):false, kj:kj?kj.textContent:'', kjColor:kj?getComputedStyle(kj).color:'',
    fx:!!fx, fxBg:fx?getComputedStyle(fx).backgroundImage:'', rays:!!rays, raysBg:rays?getComputedStyle(rays).backgroundImage:'',
    nameShadow:nmEl?getComputedStyle(nmEl).textShadow:'', chips:(c.querySelector('.pc-st')||{}).textContent||'', overflow:{sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth}};
})"""

fails = []
def call(js, nm):
    return js + "(" + json.dumps(nm) + ")"

def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def main():
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); build_xlsx(x, CAST_A)

        async def scene(pg):
            o = {}
            await pg.evaluate("()=>{try{localStorage.setItem('sgg_welcome_off','1')}catch(e){}}")
            await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(800)
            o['list'] = await pg.evaluate("()=>KISATSU.map(x=>x.name)")
            # 합성 데이터는 귀살대원들이 하현과 겹칠 수 있다 → 시험은 두 상황을 직접 만든다:
            #   plain = 하현/상현이 아닌 귀살대원(귀살대 연출이 그대로 나와야 함)
            #   ov    = 하현과 겹치는 귀살대원(하현 테마 유지 + 귀살대 칩 병기)
            k1 = await pg.evaluate("()=>KISATSU[0].name")
            k2 = await pg.evaluate("()=>KISATSU[1].name")
            o['k1'], o['k2'] = k1, k2
            o['t1'] = await pg.evaluate("(nm)=>((ASSESSMENTS.get(nm)||{}).title||'')", k1)
            o['t2'] = await pg.evaluate("(nm)=>((ASSESSMENTS.get(nm)||{}).title||'')", k2)
            o['rank1'] = await pg.evaluate("(nm)=>kisatsuRankOf(nm)", k1)
            o['rankSang'] = await pg.evaluate("(nm)=>kisatsuRankOf(nm)", SANGHYUN_1)
            await pg.evaluate("(nm)=>{const a=ASSESSMENTS.get(nm); if(a) a.title='';}", k1)     # k1 을 '귀살대만' 으로
            await pg.evaluate("(nm)=>{const a=ASSESSMENTS.get(nm); if(a) a.title='하현 3';}", k2)  # k2 를 '하현과 겹침' 으로
            await pg.evaluate("()=>go('home')"); await pg.wait_for_timeout(500)
            o['m_kis'] = await pg.evaluate(call(MODAL, k1))
            await pg.evaluate("()=>closePlayerCard()"); await pg.wait_for_timeout(200)
            o['p_kis'] = await pg.evaluate(call(PROF, k1))
            o['m_ov'] = await pg.evaluate(call(MODAL, k2))
            await pg.evaluate("()=>closePlayerCard()"); await pg.wait_for_timeout(200)
            o['p_ov'] = await pg.evaluate(call(PROF, k2))
            o['m_up'] = await pg.evaluate(call(MODAL, SANGHYUN_1))
            await pg.evaluate("()=>closePlayerCard()"); await pg.wait_for_timeout(200)
            o['p_up'] = await pg.evaluate(call(PROF, SANGHYUN_1))
            await pg.emulate_media(reduced_motion='reduce'); await pg.wait_for_timeout(200)
            o['rm'] = await pg.evaluate(call(PROF, k1))
            o['rmM'] = await pg.evaluate(call(MODAL, k1))
            return o

        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, now='2026-11-27T10:00:00',
                             cats=('rift',), shots=False, quiet=True, viewport=(1280, 900), after=scene, timeout_s=300)
    o, log = res['after'], res['meta']['log']
    print('  귀살대:', o['list'])

    ok(o['rank1'] == 1 and o['rankSang'] == 0, 'A 귀살대 1위/상현 순위 판정 (귀살대 %s · 상현 %s)' % (o['rank1'], o['rankSang']))
    print('  시험 인물:', o['k1'], '(원래 %r)' % o['t1'], '/', o['k2'], '(→ 하현 3)')
    m = o['m_kis']
    ok(m['ok'] and 'kz-kis' in m['cls'], 'A 팝업이 kz-kis 테마 %s' % (m['ok'] and m['cls']))
    ok('kzpcK' in m['anim'] and 'rgba(96, 235, 190' in m['border'], 'A 청록 테두리가 숨 쉰다 anim=%s border=%s' % (m['anim'], m['border']))
    ok(m['fx'] and '120, 220' in m['fxBg'].replace(' ', '') or (m['fx'] and 'rgba(40, 220, 170' in m['fxBg']), 'A 팝업 후광 레이어 %s' % m['fxBg'][:70])
    ok(m['kj'] == '鬼殺隊' and m['kjColor'] not in ('', 'rgb(255, 255, 255)'), 'A 鬼殺隊 워터마크 %r %s' % (m['kj'], m['kjColor']))
    ok('귀살대 1위' in m['chip'], 'A ⚔ 귀살대 1위 칩 %r' % m['chip'][:40])
    ok(m['firstShadow'] not in ('', 'none'), 'A 칩이 빛난다 %s' % m['firstShadow'])

    u = o['m_up']
    ok(u['ok'] and 'kz-up' in u['cls'] and 'kz-kis' not in u['cls'], 'B 상현은 기존 kz-up 테마 그대로 %s' % u['cls'])
    ok(u['kj'].startswith('上弦') and 'kzpcU' in u['anim'], 'B 상현 워터마크·테두리 %r %s' % (u['kj'], u['anim']))
    ok('귀살대' not in u['chip'], 'B 상현 팝업엔 귀살대 칩을 겹치지 않는다(상현은 후보에서 제외) %r' % u['chip'][:40])
    ov = o['m_ov']
    ok(ov['ok'] and 'kz-low' in ov['cls'] and 'kz-kis' not in ov['cls'], 'B 하현과 겹치면 하현 테마가 우선 %s' % ov['cls'])
    ok(ov['kj'].startswith('下弦') and '귀살대 2위' in ov['chip'], 'B 테마는 하현, 칩은 귀살대를 병기 %r / %r' % (ov['kj'], ov['chip'][:40]))

    p = o['p_kis']
    ok(p['ok'] and 'kz-prof' in p['cls'] and 'kz-kis' in p['cls'], 'C 개인 페이지가 kz-prof kz-kis %s' % p['cls'])
    ok('kzpcK' in p['anim'], 'C 테두리 맥동 %s' % p['anim'])
    ok(p['emCls'] == 'kizuki-emblem kis' and p['emSvg'], 'C 귀살대 엠블럼 %s' % p['emCls'])
    ok(p['cap'] == '⚔ 귀살대 · 1위', 'C 엠블럼 캡션 %r' % p['cap'])
    ok(p['kj'] == '鬼殺隊', 'C 鬼殺隊 워터마크 %r' % p['kj'])
    ok(p['fx'] and p['rays'] and '220,170' in p['fxBg'].replace(' ', ''), 'C 후광·빛살 %s' % p['fxBg'][:70])
    ok(p['nameShadow'] not in ('', 'none'), 'C 이름 글로우 %s' % p['nameShadow'])
    ok(p['overflow']['sw'] <= p['overflow']['cw'] + 1, 'C 가로 넘침 0 %s' % p['overflow'])

    po = o['p_ov']
    ok(po['ok'] and 'kz-low' in po['cls'] and po['emCls'] == 'kizuki-emblem low', 'D 하현 겹침 프로필도 하현 그대로 %s %s' % (po['cls'], po['emCls']))
    ok('귀살대 2위' in (po.get('chips') or ''), 'D 하현 겹침 프로필 이름 밑에 귀살대 칩 병기 %r' % (po.get('chips') or '')[:40])

    pu = o['p_up']
    ok(pu['ok'] and 'kz-up' in pu['cls'] and 'kz-kis' not in pu['cls'], 'D 상현 페이지는 kz-up %s' % pu['cls'])
    ok(pu['emCls'] == 'kizuki-emblem up' and pu['cap'].startswith('🩸 십이귀월 · 상현 1'), 'D 상현 엠블럼 그대로 %r' % pu['cap'])
    ok(pu['kj'] == '上弦', 'D 상현 워터마크 %r' % pu['kj'])

    rm, rmm = o['rm'], o['rmM']
    ok(rm['ok'] and rm['anim'] in ('none', ''), 'E 동작 줄이기면 테두리 맥동 끔 %s' % rm['anim'])
    ok(rmm['ok'] and 'kzpcK' not in rmm['anim'], 'E 팝업도 맥동 끔 %s' % rmm['anim'])
    ok(not log['pageerror'] and not log['console'], 'E 페이지 오류·콘솔 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
