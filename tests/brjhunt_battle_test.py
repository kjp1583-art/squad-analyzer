#!/usr/bin/env python3
"""brjhunt.html 필드(발판 아레나) 통합 시험(Playwright + 가짜 서버). 사용: CHROME=... python3.13 tests/brjhunt_battle_test.py [--shots 폴더]
tests/brjhunt_test.py 의 가짜 서버·페이지 도우미를 그대로 불러다 쓴다(그 파일의 main 앞부분만 실행).
본다: 필드가 그려지고 흐르는지 · 체력/마나 바·AUTO 버튼·콤보 · 키보드(이동·점프·공격·스킬·Tab)와 화면 버튼(터치) 입력이 엔진에 닿는지 ·
다른 탭에서는 키보드가 꺼지는지 · 사냥 보고(/brj/hunt: 마릿수·초·스테이지·골드 반영 · 「아직」이면 쌓아 두기 · 실패하면 버리기) ·
소리 연결(전투 이벤트 → 효과음 이름) · 도전 던전·보스(승/패/판정 못 받음/몰림) · 탭 전환 · 숨김 · 콘솔 오류 · 390/360/320/1280/1920 폭."""
import asyncio, os, sys, json
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'brjhunt_test.py'), encoding='utf-8').read()
_src = _src[:_src.index('async def main')]
_g = {'__file__': os.path.join(_here, 'brjhunt_test.py'), '__name__': 'brjhunt_base'}
exec(compile(_src, 'brjhunt_test.py', 'exec'), _g)
Server, new_page, noscroll, tab, check, make_view, FAILS, SHOTS = (_g[k] for k in ('Server', 'new_page', 'noscroll', 'tab', 'check', 'make_view', 'FAILS', 'SHOTS'))
from playwright.async_api import async_playwright

import hashlib
async def HASHF(pg): return hashlib.md5(await pg.locator('#fcv').screenshot()).hexdigest()
async def T(pg): return await pg.evaluate('window.__bt.t')
async def shot(pg, name):
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); await pg.locator('#stage').screenshot(path=f'{SHOTS}/{name}.png')
async def spy(pg):   # 보스 상태가 지나간 순서를 모은다
    await pg.evaluate("window.__seen=[]; setInterval(()=>{const b=window.__bt.boss; const s=window.__seen; if(s[s.length-1]!==b) s.push(b);},40)")
async def sfx_spy(pg):   # 효과음 이름을 모은다(소리 자체는 못 듣지만 어떤 이벤트가 어떤 이름을 불렀는지는 볼 수 있다)
    await pg.evaluate("window.__sfx=[]; const o=BrjAudio.sfx; BrjAudio.sfx=function(n,x){ window.__sfx.push(n); return o.apply(this,arguments); }; 0")
def hunt_view(stage=10, gate=True):
    v = make_view(); v['stage'] = stage; v['region'] = '홍대 먹자골목'; v['dungeon']['gate']['stage'] = 10 if gate else 0
    v['field']['stage'] = stage; return v
def hits(srv, path='/brj/hunt'): return [b for p, b in srv.hits if p == path]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}))
        # ---- 기본: 그려지고 흐른다 ----
        srv = Server(); srv.view = hunt_view(); ctx, pg, errs = await new_page(b, srv, scheme='dark')
        await sfx_spy(pg)
        check('필드 캔버스가 화면 위쪽(상단 HUD 바로 아래)에 있음', await pg.locator('#stage #fcv').count() == 1)
        box = await pg.locator('#fcv').bounding_box()
        check('캔버스 높이 170~300px · 폭은 화면 가득', 170 <= box['height'] <= 300 and box['width'] >= 380, box)
        t0 = await T(pg); h0 = await HASHF(pg); await pg.wait_for_timeout(700); t1 = await T(pg); h1 = await HASHF(pg)
        check('필드 시간이 흐름', t1 - t0 >= 0.4, (t0, t1)); check('픽셀이 시간에 따라 변함', h0 != h1)
        check('동료 1명(파티 c1)이 나옴', await pg.evaluate('window.__bt.party') == 1)
        check('HUD: 체력·마나 바와 AUTO 버튼(켜짐)', await pg.locator('#hpBar').is_visible() and await pg.locator('#mpBar').is_visible() and 'HP' in await pg.inner_text('#hpTxt') and 'MP' in await pg.inner_text('#mpTxt') and await pg.get_attribute('#autoBtn', 'aria-pressed') == 'true' and 'AUTO' in await pg.inner_text('#autoBtn'))
        check('서버 스탯이 엔진에 들어감(체력 1448 · MP 134)', (await pg.evaluate('window.__bt.stats.hpMax')) == 1448 and (await pg.evaluate('window.__bt.stats.mpMax')) == 134, await pg.evaluate('window.__bt.stats'))
        await shot(pg, 'ui_field_1'); await pg.wait_for_timeout(2500); await shot(pg, 'ui_field_2')
        check('가만히 둬도(AUTO) 몬스터를 잡음(처치 수 증가)', await pg.evaluate('window.__bt.kills') >= 1)
        check('가로 스크롤 없음(390px)', await noscroll(pg))
        check('쌓인 골드 숫자는 서버 값 기반', (await pg.inner_text('#pend')).replace(',', '').isdigit())
        # ---- 분당 처치: 시계를 빨리 돌려 잰다(전투력 700 / 권장 400) ----
        await pg.evaluate('window.__bt.field.setTimeScale(12)'); await pg.wait_for_timeout(9000); await pg.evaluate('window.__bt.field.setTimeScale(1)')
        s = await pg.evaluate('window.__bt.stats'); check('분당 처치: 전투력이 권장의 1.75배면(서버 어림 110) AUTO 의 평균이 분당 60~170(맵·운에 따라 ±25% 흔들림)', 60 <= s['kpmTotal'] <= 170, s['kpmTotal'])
        txt = await pg.text_content('#hudL')
        check('HUD 에 분당 처치·몬스터 1마리 드랍 골드(100처치당 2.27)가 보임', '분당 처치' in txt and '2.27' in txt and '100처치' in txt, txt)
        check('카메라가 병아리를 따라 필드를 가로지름(세계 폭 ≫ 화면 폭)', s['mapW'] > s['VW'] * 2 and s['VW'] < 800, (s['mapW'], s['VW']))
        names = set(await pg.evaluate('window.__sfx'))
        check('소리: 휘두름·타격·몬스터 처치 효과음 이름이 불림', {'hit', 'mon_die'} <= names and any(n.startswith('swing') for n in names), sorted(names))
        check('소리: 스킬 시전 시 전조·발동 이름이 불림(skill_<id>_charge / skill_<id>)', any(n.endswith('_charge') for n in names) and any(n in ('skill_slash', 'skill_peck') for n in names), sorted(names))
        check('소리: 스킬 전조·발동·여운은 스킬 이름', any(n.endswith('_tail') for n in names), sorted(names))
        # ---- 사냥 보고 ----
        await pg.evaluate('window.__bt.hq.min=0'); c0 = len(hits(srv)); await pg.evaluate('window.__bt.field.flush()'); await pg.wait_for_timeout(300)
        hh = hits(srv)[c0:]
        check('보고 → /brj/hunt {kills,secs,stage,token} (정수 · secs 1~40 · 스테이지 10)', len(hh) == 1 and set(hh[0]) == {'kills', 'secs', 'stage', 'token'} and all(isinstance(hh[0][k], int) for k in ('kills', 'secs', 'stage')) and 1 <= hh[0]['secs'] <= 40 and hh[0]['stage'] == 10 and hh[0]['kills'] >= 1 and hh[0]['token'] == 'T' * 40, hh)
        check('보고한 마리 수가 서버 응답의 골드로 보임(직접 사냥 칸)', await pg.evaluate('window.__bt.got') >= 1 and '직접 사냥' in await pg.text_content('#hGot'), await pg.text_content('#hGot'))
        # ---- 사냥 보고: 서버가 「아직」 이라고 하면 쌓아 두고 다음에 보낸다 ----
        k0 = srv.hunted
        srv.override['/brj/hunt'] = lambda body: (200, {'ok': False, 'code': 'too_soon', 'got': 0, 'accepted': 0, 'view': make_view()})
        await pg.evaluate('window.__bt.hq.min=0; window.__bt.field.setTimeScale(14)'); await pg.wait_for_timeout(3500); await pg.evaluate('window.__bt.field.setTimeScale(1)')
        await pg.evaluate('window.__bt.field.flush(); window.__bt.hq.min=0'); await pg.wait_for_timeout(300)
        q = await pg.evaluate('({k:window.__bt.hq.k,s:window.__bt.hq.s})')
        check('too_soon: 보낸 만큼 버리지 않고 쌓아 둠(마리 수·초가 남음)', q['k'] >= 1 and q['s'] >= 1, q)
        srv.override.pop('/brj/hunt'); await pg.evaluate('window.__bt.hq.min=0; window.__bt.hq.rej=0'); c0 = len(hits(srv)); await pg.evaluate('window.__bt.sendHunt()'); await pg.wait_for_timeout(300)
        hh = hits(srv)[c0:]; check('다음 주기에 쌓아 둔 것을 한꺼번에 보냄(secs ≤ 40)', len(hh) == 1 and 1 <= hh[0]['secs'] <= 40 and hh[0]['kills'] >= 1, hh)
        # ---- 사냥 보고: 네트워크가 끊기면 같은 걸 조용히 다시 보내지 않고 알린다 ----
        await pg.evaluate("window.__fb=[]; const of=window.fetch; window.fetch=function(u,o){ if(String(u).includes('/brj/hunt')) window.__fb.push(JSON.parse(o.body)); return of.apply(this,arguments); }; 0")
        srv.abort_paths = ['/brj/hunt']; await pg.evaluate('window.__bt.hq.k=5; window.__bt.hq.s=30; window.__bt.hq.min=0'); c0 = len(hits(srv)); await pg.evaluate('window.__bt.sendHunt()'); await pg.wait_for_timeout(400)
        q = await pg.evaluate('({k:window.__bt.hq.k,s:window.__bt.hq.s,f:window.__bt.hq.fail})')
        check('네트워크 오류: 그 묶음은 버림(조용한 재시도 없음) · 알림 토스트', q['s'] == 0 and q['k'] == 0 and q['f'] == 'net' and '보내지 못했어요' in await pg.inner_text('#toastBox'), q)
        await pg.wait_for_timeout(1200); check('네트워크 오류 뒤 같은 묶음(5마리·30초)을 다시 보내지 않음', len([h for h in await pg.evaluate('window.__fb') if h['kills'] == 5 and h['secs'] == 30]) == 1, await pg.evaluate('window.__fb'))
        srv.abort_paths = []
        # ---- 사냥 보고: 스테이지가 서버와 다르면 버린다 ----
        srv.override['/brj/hunt'] = lambda body: (200, {'ok': False, 'code': 'stage', 'got': 0, 'accepted': 0, 'view': hunt_view(10)})
        await pg.evaluate('window.__bt.hq.k=4; window.__bt.hq.s=30; window.__bt.hq.min=0; window.__bt.sendHunt()'); await pg.wait_for_timeout(300)
        q = await pg.evaluate('({k:window.__bt.hq.k,s:window.__bt.hq.s})'); check('stage 거절: 버림', q['s'] == 0 and q['k'] == 0, q); srv.override.pop('/brj/hunt')
        # ---- 사냥 보고: 간격(secs×0.7초 이전엔 안 보냄) · 1초 미만은 보내지 않음 ----
        c0 = len(hits(srv)); await pg.evaluate('window.__bt.hq.k=1; window.__bt.hq.s=0.4; window.__bt.hq.min=0; window.__bt.sendHunt()'); await pg.wait_for_timeout(200)
        check('1초 미만은 보내지 않음', len(hits(srv)) == c0)
        await pg.evaluate('window.__bt.hq.k=3; window.__bt.hq.s=20; window.__bt.hq.min=0; window.__bt.sendHunt()'); await pg.wait_for_timeout(250); await pg.evaluate('window.__bt.hq.k=3; window.__bt.hq.s=20; window.__bt.sendHunt()'); await pg.wait_for_timeout(250)
        check('연달아 보내지 않음(직전 보고 secs×0.7초 동안 쉼)', len(hits(srv)) == c0 + 1, len(hits(srv)) - c0)
        await pg.evaluate('window.__bt.hq.k=0; window.__bt.hq.s=0')
        check('콘솔 오류 없음', not errs, errs)
        # ---- 키보드 ----
        await pg.evaluate("window.__keys=()=>window.__bt.field.debug.keys()")
        await pg.keyboard.down('ArrowRight'); await pg.wait_for_timeout(120); k = await pg.evaluate('window.__keys()'); st = await pg.evaluate('window.__bt.stats')
        check('→ 키: 오른쪽 입력 + 바로 수동으로 바뀜(AUTO 표시가 「수동」)', k['right'] is True and st['auto'] is False and '수동' in await pg.inner_text('#autoBtn'), (k, st['auto']))
        await pg.keyboard.up('ArrowRight')
        await pg.keyboard.down('Alt'); await pg.wait_for_timeout(60); k = await pg.evaluate('window.__keys()'); await pg.keyboard.up('Alt'); check('Alt: 점프 입력', k['jump'] is True, k)
        await pg.keyboard.down('Control'); await pg.wait_for_timeout(60); k = await pg.evaluate('window.__keys()'); await pg.keyboard.up('Control'); check('Ctrl: 기본 공격 입력', k['attack'] is True, k)
        await pg.keyboard.down('ArrowDown'); await pg.keyboard.down('Space'); await pg.wait_for_timeout(60); k = await pg.evaluate('window.__keys()'); await pg.keyboard.up('Space'); await pg.keyboard.up('ArrowDown')
        check('↓ + Space: 아래 발판으로 내려가기 입력(두 키 동시)', k['down'] is True and k['jump'] is True, k)
        for _try in range(4):   # 맞아서 휘청이는 동안(hurt)에는 스킬을 못 쓰는 게 정상이라, 몇 번까지는 다시 눌러 본다
            await pg.wait_for_function('window.__bt.stats.cd[0]<=0 && window.__bt.stats.mp>=20', timeout=8000); await pg.keyboard.press('1'); await pg.wait_for_timeout(250)
            st = await pg.evaluate('window.__bt.stats')
            if st['cd'][0] > 0: break
        check('1 키: 1번 스킬 사용(쿨다운이 돌기 시작)', st['cd'][0] > 0, st['cd'])
        ok_buf = False
        for _try in range(4):
            await pg.wait_for_function('window.__bt.stats.cd[0]>0 && window.__bt.stats.cd[0]<0.1', timeout=8000, polling=10); await pg.keyboard.press('1'); await pg.wait_for_timeout(450)
            st = await pg.evaluate('window.__bt.stats')
            if st['cd'][0] > 1.0: ok_buf = True; break
        check('쿨다운이 거의 끝날 때 눌러도 놓치지 않음(0.16초 입력 기억)', ok_buf, st['cd'])
        await pg.keyboard.press('Tab'); await pg.wait_for_timeout(100)
        check('Tab: AUTO 꺼짐(버튼 aria-pressed=false · localStorage 저장)', await pg.get_attribute('#autoBtn', 'aria-pressed') == 'false' and await pg.evaluate("localStorage.getItem('brjhunt_auto')") == '0')
        await pg.keyboard.press('Tab'); await pg.wait_for_timeout(100); check('Tab 다시: AUTO 켜짐', await pg.get_attribute('#autoBtn', 'aria-pressed') == 'true' and 'AUTO' in await pg.inner_text('#autoBtn'))
        await pg.click('#autoBtn'); await pg.wait_for_timeout(100); check('AUTO 버튼 클릭: 꺼짐', await pg.get_attribute('#autoBtn', 'aria-pressed') == 'false')
        await pg.click('#autoBtn'); await pg.wait_for_timeout(100); check('AUTO 버튼 다시: 켜짐', await pg.get_attribute('#autoBtn', 'aria-pressed') == 'true')
        await pg.keyboard.down('ArrowLeft'); await pg.wait_for_timeout(80); await pg.keyboard.up('ArrowLeft'); await pg.wait_for_timeout(100)
        await pg.click('#autoBtn'); await pg.wait_for_timeout(100); st = await pg.evaluate('window.__bt.stats'); check('수동 표시 중 AUTO 버튼 → 즉시 AUTO(켜짐)', st['autoWanted'] is True and (st['auto'] is True or 'AUTO' in await pg.inner_text('#autoBtn')), st['auto'])
        await pg.click('#keyBtn'); check('? 버튼: 조작법 도움말이 열림(키 이름이 보임)', await pg.locator('#keyHelp.show').count() == 1 and 'Ctrl' in await pg.inner_text('#keyHelp') and 'Tab' in await pg.inner_text('#keyHelp'))
        await shot(pg, 'ui_keyhelp'); await pg.keyboard.press('Escape'); check('Esc 로 도움말 닫힘', await pg.locator('#keyHelp.show').count() == 0)
        check('도움말을 열고 닫은 뒤에도 오류 없음', not errs, errs)
        # ---- 다른 탭에서는 키보드가 필드를 움직이지 않는다 ----
        await tab(pg, 'skill'); await pg.wait_for_timeout(200)
        await pg.keyboard.down('ArrowRight'); await pg.wait_for_timeout(100); k = await pg.evaluate('window.__keys()'); await pg.keyboard.up('ArrowRight')
        check('스킬 탭: 방향키가 필드로 안 감(페이지 스크롤은 그대로)', k['right'] is False, k)
        await tab(pg, 'hunt'); await pg.wait_for_timeout(200); await pg.keyboard.down('ArrowRight'); await pg.wait_for_timeout(100); k = await pg.evaluate('window.__keys()'); await pg.keyboard.up('ArrowRight')
        check('사냥터로 돌아오면 다시 키보드가 필드로 감', k['right'] is True, k)
        # ---- 핫바 스킬 버튼(마우스) ----
        await pg.keyboard.press('Tab'); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(2500)
        cd1 = (await pg.evaluate('window.__bt.stats.cd'))[1]
        await pg.click('#dock .sk[data-cast="1"]'); await pg.wait_for_timeout(250); st = await pg.evaluate('window.__bt.stats')
        check('핫바 2번 스킬 버튼을 누르면 사용(쿨다운 시작)', st['cd'][1] > 0 or cd1 > 0, st['cd'])
        check('핫바 스킬 칸에 단축키 숫자 표시', await pg.locator('#dock .sk[data-cast="0"] .kb').inner_text() == '1')
        check('핫바 아래 단축키 안내 한 줄', '이동' in await pg.inner_text('#dock .keyhint') and 'AUTO' in await pg.inner_text('#dock .keyhint'))
        # ---- 보스: 응답이 win ----
        await spy(pg); c0 = len(srv.hits)
        check('스테이지 10 은 보스 관문 → 필드 아래 큰 버튼이 「보스 도전」', await pg.locator('#dock [data-do=boss]').count() == 1)
        await pg.click('#dock [data-do=boss]'); await pg.wait_for_timeout(250)
        bh = [(pa, bo) for pa, bo in srv.hits[c0:] if pa == '/brj/boss']
        check('보스 도전 → /brj/boss 한 번(토큰 포함)', len(bh) == 1 and bh[0][1] == {'token': 'T' * 40}, bh)
        check('보스 중 BGM 이 boss 트랙', await pg.evaluate('window.__bt.bgm') == 'boss')
        check('보스전 중에는 큰 버튼이 꺼짐(중복 도전 방지)', await pg.locator('#dock .push').is_disabled())
        await pg.wait_for_timeout(900); await shot(pg, 'ui_boss_intro')
        check('보스 연출 시작(boss 상태 있음)', await pg.evaluate('window.__bt.boss') is not None)
        check('보스 중에도 화면 폭이 그대로(앱이 뷰포트보다 넓어지지 않음) · 체력바가 아래로 비켜남', await pg.evaluate("document.getElementById('app').getBoundingClientRect().width<=innerWidth+0.5") and await pg.evaluate("document.body.classList.contains('inboss') && document.getElementById('hudL').getBoundingClientRect().bottom>200"))
        await pg.wait_for_timeout(5500); await shot(pg, 'ui_boss_fight')
        await pg.wait_for_function("window.__bt.boss==='dying'", timeout=30000); await pg.wait_for_timeout(1200); await shot(pg, 'ui_boss_win')
        await pg.wait_for_function("window.__bt.boss===null", timeout=30000); await pg.wait_for_timeout(500)
        seen = await pg.evaluate('window.__seen')
        check('win 응답 → 보스가 쓰러지는 연출(dying)을 거쳐 사냥으로 복귀', 'dying' in seen and 'smash' not in seen and seen[-1] is None, seen)
        check('win 문구', '쓰러뜨렸어요' in await pg.inner_text('.msg'))
        check('보스가 끝나면 BGM 이 지역 트랙으로 복귀 · 큰 버튼 복귀', await pg.evaluate('window.__bt.bgm') == 'field3' and await pg.locator('#dock [data-do=boss]').is_enabled())
        names = set(await pg.evaluate('window.__sfx'))
        check('소리: 보스 입장·처치·승리 이름이 불림', {'boss_in', 'boss_die', 'boss_win'} <= names, sorted(names))
        check('보스 뒤 오류 없음', not errs, errs)
        # ---- 보스: 응답이 lose ----
        srv.override['/brj/boss'] = lambda body: (200, {'ok': True, 'result': 'lose', 'boss': 10, 'power': 300, 'hp': 534, 'view': hunt_view()})
        await pg.evaluate('window.__seen=[]'); await pg.wait_for_timeout(200)
        await pg.click('#dock [data-do=boss]'); await pg.wait_for_timeout(8000); await shot(pg, 'ui_boss_fight2')
        await pg.wait_for_function("window.__bt.boss==='smash'", timeout=30000); await pg.wait_for_timeout(1000); await shot(pg, 'ui_boss_lose')
        await pg.wait_for_function("window.__bt.boss===null", timeout=30000); await pg.wait_for_timeout(500)
        seen = await pg.evaluate('window.__seen')
        check('lose 응답 → 병아리가 쓰러지는 연출(smash), 보스는 안 쓰러짐', 'smash' in seen and 'dying' not in seen and seen[-1] is None, seen)
        check('lose 문구', '졌어요' in await pg.inner_text('.msg'))
        check('소리: 패배 이름이 불림', 'boss_lose' in set(await pg.evaluate('window.__sfx')))
        # ---- 서버가 일을 못 한 경우(몰림): 연출이 걸려 남지 않는다 ----
        srv.mode = 'busy'; await pg.click('#dock [data-do=boss]'); await pg.wait_for_timeout(1500)
        srv.mode = 'ok'; await pg.wait_for_timeout(2500)
        check('몰림이면 보스 연출이 취소되어 사냥으로 돌아옴', await pg.evaluate('window.__bt.boss') is None and await pg.evaluate('window.__bt.bgm') == 'field3' and await pg.locator('#dock [data-do=boss]').is_enabled(), await pg.evaluate('window.__bt.boss'))
        # ---- 탭 전환: 필드는 작은 창으로 이어서 돈다 ----
        await tab(pg, 'adv'); await pg.wait_for_timeout(600); box = await pg.locator('#fcv').bounding_box()
        check('다른 탭에서는 필드가 작은 창(약 112px)으로 줄어듦', 100 <= box['height'] <= 125, box)
        ta = await T(pg); await pg.wait_for_timeout(600); check('다른 탭에서도 필드는 계속 돎', await T(pg) - ta >= 0.3)
        check('다른 탭에서는 핫바(dock)·화면 조작 버튼이 숨겨짐', not await pg.is_visible('#dock') and not await pg.is_visible('#touch'))
        check('모험 탭에도 보스 도전 버튼은 하나', await pg.locator('#main [data-do=boss]').count() == 1)
        await tab(pg, 'hunt'); await pg.wait_for_timeout(600); box = await pg.locator('#fcv').bounding_box()
        check('사냥터로 돌아오면 큰 화면으로 복귀', box['height'] >= 170 and await pg.is_visible('#dock'), box)
        # 탭이 숨겨지면 멈추고 그때까지 한 것을 보고한다
        c0 = len(hits(srv)); await pg.evaluate('window.__bt.hq.min=0; window.__bt.field.setTimeScale(10)'); await pg.wait_for_timeout(1800); await pg.evaluate('window.__bt.field.setTimeScale(1)')
        await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))"); await pg.wait_for_timeout(400)
        check('탭이 숨겨질 때 그때까지 한 사냥을 보고함', len(hits(srv)) > c0, len(hits(srv)) - c0)
        th = await T(pg); await pg.wait_for_timeout(700); check('탭이 숨겨지면 필드가 멈춤', await T(pg) - th < 0.05)
        await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}); document.dispatchEvent(new Event('visibilitychange'))"); await pg.wait_for_timeout(300)
        th = await T(pg); await pg.wait_for_timeout(700); check('다시 보이면 이어서 흐름', await T(pg) - th >= 0.3)
        check('콘솔 오류 없음', not errs, errs); await ctx.close()
        # ---- 화면 조작 버튼(터치) ----
        srv = Server(); srv.view = hunt_view(9, False); ctx, pg, errs = await new_page(b, srv, w=390, h=800, touch=True); await pg.wait_for_timeout(300)
        await pg.evaluate("window.__keys=()=>window.__bt.field.debug.keys()")
        check('터치 기기: 화면 조작 버튼(🎮)이 기본으로 켜져 있고 필드 아래에 보임', await pg.locator('body.touch #touch').count() == 1 and await pg.is_visible('#touch [data-k=attack]') and await pg.get_attribute('#padBtn', 'aria-pressed') == 'true')
        bx = await pg.evaluate("(()=>{const r=s=>document.querySelector(s).getBoundingClientRect();return {f:r('#fieldBox').bottom,t:r('#touch').top,tb:r('#touch').bottom,d:r('#dock').top,n:r('#nav').top,h:innerHeight,btn:Math.min(...[...document.querySelectorAll('#touch .tp')].map(e=>Math.min(e.getBoundingClientRect().width,e.getBoundingClientRect().height)))}})()")
        check('조작 버튼은 필드를 가리지 않고(필드 바로 아래 줄) 모두 화면 안 · 버튼 최소 44px', bx['t'] >= bx['f'] - 1 and bx['tb'] <= bx['d'] + 1 and bx['n'] <= bx['h'] and bx['btn'] >= 44, bx)
        check('터치 기기에서는 키보드 안내 줄이 숨겨짐', not await pg.is_visible('#dock .keyhint'))
        async def hold(sel, pid=7):
            await pg.locator(sel).dispatch_event('pointerdown', {'pointerId': pid, 'pointerType': 'touch', 'isPrimary': True, 'bubbles': True})
        async def lift(sel, pid=7):
            await pg.locator(sel).dispatch_event('pointerup', {'pointerId': pid, 'pointerType': 'touch', 'isPrimary': True, 'bubbles': True})
        await hold('#touch [data-k=right]'); await pg.wait_for_timeout(100); k = await pg.evaluate('window.__keys()')
        check('▶ 버튼을 누르고 있는 동안 오른쪽 입력', k['right'] is True and k['left'] is False, k)
        await lift('#touch [data-k=right]'); await pg.wait_for_timeout(60); check('손을 떼면 입력이 풀림', (await pg.evaluate('window.__keys()'))['right'] is False)
        await hold('#touch [data-k=left]', 8); await hold('#touch [data-k=attack]', 9); await pg.wait_for_timeout(80); k = await pg.evaluate('window.__keys()')
        check('두 손가락 동시 조작(◀ + ⚔) — 둘 다 입력됨', k['left'] is True and k['attack'] is True, k)
        await lift('#touch [data-k=left]', 8); await lift('#touch [data-k=attack]', 9)
        await hold('#touch [data-k=jump]', 10); await pg.wait_for_timeout(50); k = await pg.evaluate('window.__keys()'); await lift('#touch [data-k=jump]', 10); check('⤒ 점프 입력', k['jump'] is True, k)
        await pg.locator('#touch [data-k=drop]').dispatch_event('pointerdown', {'pointerId': 11, 'pointerType': 'touch', 'isPrimary': True, 'bubbles': True}); await pg.wait_for_timeout(40); k = await pg.evaluate('window.__keys()')
        check('⤓ 내려가기 = 아래 + 점프를 함께 입력', k['down'] is True and k['jump'] is True, k)
        await lift('#touch [data-k=drop]', 11); await pg.wait_for_timeout(250); k = await pg.evaluate('window.__keys()'); check('내려가기 버튼 뒤 입력이 스스로 풀림', k['down'] is False and k['jump'] is False, k)
        await pg.evaluate("window.dispatchEvent(new Event('blur'))")
        await pg.locator('#dock .sk[data-cast="0"]').dispatch_event('pointerdown', {'pointerId': 12, 'pointerType': 'touch', 'isPrimary': True, 'bubbles': True}); await pg.wait_for_timeout(250)
        check('핫바 스킬을 손가락이 닿는 순간 사용(쿨다운 시작)', (await pg.evaluate('window.__bt.stats.cd'))[0] > 0)
        n_h = len(hits(srv)); await pg.click('#padBtn'); await pg.wait_for_timeout(200)
        check('🎮 버튼으로 화면 조작 버튼을 끄고 켬(저장)', await pg.locator('body.touch').count() == 0 and await pg.evaluate("localStorage.getItem('brjhunt_pad')") == '0')
        await pg.click('#padBtn'); await pg.wait_for_timeout(100); check('다시 켜짐', await pg.locator('body.touch').count() == 1)
        await shot(pg, 'ui_touch_390'); check('터치 화면: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs)
        await ctx.close()
        # 마우스 기기(PC)에서는 기본으로 꺼져 있다
        srv = Server(); ctx, pg, errs = await new_page(b, srv, w=1280, h=800); await pg.wait_for_timeout(300)
        check('PC: 화면 조작 버튼은 기본으로 꺼짐 · 키보드 안내 줄이 보임', await pg.locator('body.touch').count() == 0 and not await pg.is_visible('#touch') and await pg.is_visible('#dock .keyhint'))
        await pg.click('#padBtn'); await pg.wait_for_timeout(200); check('PC 에서도 🎮 로 켤 수 있음', await pg.is_visible('#touch [data-k=attack]'))
        await ctx.close()
        # ---- 파티가 비면 병아리만 / 관문 없으면 돌파 버튼 ----
        srv = Server(); v = make_view(); v['summon']['party'] = []; v['dungeon']['gate']['stage'] = 0; srv.view = v
        ctx, pg, errs = await new_page(b, srv, scheme='light')
        check('파티가 비면 동료 0', await pg.evaluate('window.__bt.party') == 0)
        check('관문이 없으면 보스 도전 버튼 없음 · 도전 던전 버튼', await pg.locator('#main [data-do=boss], #dock [data-do=boss]').count() == 0 and await pg.locator('#dock [data-do=chal]').count() == 1)
        await pg.wait_for_timeout(1500); await shot(pg, 'ui_field_light_solo')
        check('라이트: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs); await ctx.close()
        # ---- 도전 던전: 이김/짐이 서버 응답대로(엔진 연출) ----
        srv = Server(); v = make_view(); v['dungeon']['gate']['stage'] = 0; srv.view = v
        srv.override['/brj/push'] = lambda body: (200, {'ok': True, 'result': 'ok', 'cost': 0, 'view': copy_view(v)})
        ctx, pg, errs = await new_page(b, srv); await spy(pg)
        await pg.click('#dock [data-do=chal]'); await pg.wait_for_function("window.__bt.boss==='dying'", timeout=40000); await pg.wait_for_function("window.__bt.boss===null", timeout=30000)
        check('도전 던전 승리 → 쓰러지는 연출 + 클리어 문구', 'dying' in await pg.evaluate('window.__seen') and '클리어' in await pg.inner_text('.msg'), await pg.inner_text('.msg'))
        check('도전 뒤 오류 없음', not errs, errs); await ctx.close()
        # ---- 파티 3명 ----
        srv = Server(); v = make_view(); v['summon']['party'] = ['c1', 'c2', 'c4']; srv.view = v
        ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(2200)
        check('파티 3명', await pg.evaluate('window.__bt.party') == 3); await shot(pg, 'ui_field_party3')
        check('XSS 없음·오류 없음', await pg.evaluate('window.__xss') is None and not errs, errs); await ctx.close()
        # ---- 옛 서버(전투 스탯·field 가 없는 뷰): 엔진이 기본값으로라도 돈다 ----
        def _old(body):
            v = make_view()
            for k in ('stats', 'field', 'combat', 'hunt'): v.pop(k, None)
            return 200, {'ok': True, 'view': v}
        srv = Server(); srv.override['/brj/idle'] = _old; ctx, pg, errs = await new_page(b, srv); await pg.wait_for_timeout(1500)
        await tab(pg, 'grow'); check('옛 서버: 스탯 탭은 안내만 · 사냥터·필드는 돎', '전투 스탯 정보를 아직 받지 못했어요' in await pg.inner_text('#main') and await T(pg) > 0.5 and not errs, errs); await ctx.close()
        # ---- 좁은 폰(360·320px) ----
        for w in (360, 320):
            srv = Server(); ctx, pg, errs = await new_page(b, srv, w=w, h=640, touch=True)
            for k in ('hunt', 'skill', 'crew', 'grow', 'adv'):
                await tab(pg, k); await pg.wait_for_timeout(200)
                check(f'{w}px {k}: 가로 스크롤 없음', await noscroll(pg))
            await tab(pg, 'hunt'); await pg.wait_for_timeout(500)
            check(f'{w}px: 필드·조작 버튼·핫바·탭바가 한 화면에 다 보임', await pg.evaluate("(()=>{const r=e=>document.querySelector(e).getBoundingClientRect(); return r('#touch').bottom<=r('#dock').top+1 && r('#dock').bottom<=r('#nav').top+1 && r('#nav').bottom<=innerHeight+1 && r('#fcv').height>=150;})()"))
            if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_w{w}.png')
            check(f'{w}px: 오류 없음', not errs, errs); await ctx.close()
        # ---- 데스크톱 폭 ----
        for (w, h) in ((1280, 800), (1920, 1000)):
            srv = Server(); ctx, pg, errs = await new_page(b, srv, w=w, h=h)
            await pg.wait_for_timeout(1500); check(f'{w}px: 가로 스크롤·오류 없음', await noscroll(pg) and not errs, errs)
            fb = await pg.locator('#fieldBox').bounding_box(); check(f'{w}px: 왼쪽 큰 필드 · 오른쪽 패널', fb['width'] > w * 0.6 and fb['height'] > h * 0.55, fb)
            if SHOTS: await pg.screenshot(path=f'{SHOTS}/ui_wide_{w}.png')
            await ctx.close()
        await b.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과'); sys.exit(1 if FAILS else 0)
import copy
def copy_view(v): return copy.deepcopy(v)
asyncio.run(main())
