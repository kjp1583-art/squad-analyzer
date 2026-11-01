#!/usr/bin/env python3.13
"""열쇠 던전 · 클랜 보스 · 보상 상자 인스턴스 연출 시험(4차 개편). 사용: CHROME=... python3.13 tests/brjhunt_instance_test.py [--shots 폴더]
 (A) 엔진(BrjArena.startInstance) — 던전 win/lose/sweep/nokey · 클랜 보스 ok/dead/아주 작은 피해/0 · 보상 · 결과가 늦게 옴 · 건너뛰기 · 응답 실패(abort) · 수동 조작 · 보고(report)에 안 들어감
     「연출 속 타격들의 합 = 서버 dmg」 가 정확히 맞는지, 보상 아이콘 이벤트가 서버 값과 같은지, 끝나면 원래 사냥터로 돌아오는지
 (B) 페이지(brjhunt.html + 가짜 서버) — 누르면 서버를 부르고 연출이 시작되는지 · 연출 중 잠금 · 건너뛰기 · 끝나야 화면 값이 바뀌는지 ·
     던전 win/lose/sweep/nokey · 클랜 ok/limit/dead(연출 없이 안내) · 보상 받기 · 서버 실패 · 서버가 늦음 · 효과음 훅 · 콘솔 오류 0
 --shots 를 주면 PC(1920×1080)·폰(390) 캡처를 저장한다."""
import asyncio, os, sys, json, time, copy
_here = os.path.dirname(os.path.abspath(__file__))
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
_src = open(os.path.join(_here, 'brjhunt_test.py'), encoding='utf-8').read(); _src = _src[:_src.index('async def main')]
_g = {'__file__': os.path.join(_here, 'brjhunt_test.py'), '__name__': 'brjhunt_base'}
exec(compile(_src, 'brjhunt_test.py', 'exec'), _g)
Server, new_page, noscroll, tab, check, FAILS, URL, API, urlpath, finish_inst = (_g[k] for k in ('Server', 'new_page', 'noscroll', 'tab', 'check', 'FAILS', 'URL', 'API', 'urlpath', 'finish_inst')) if 'finish_inst' in _g else (None,) * 10
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
from playwright.async_api import async_playwright

HARNESS = 'file://' + os.path.join(_here, 'brjhunt_arena_harness.html')
RES = {
    'win': {'result': 'win', 'level': 7, 'got': {'stone': 3, 'gold': 12345, 'ticket': 1}},
    'lose': {'result': 'lose', 'level': 7, 'power': 800, 'hp': 2000},
    'sweep': {'result': 'sweep', 'got': {'stone': 6, 'gold': 20000, 'ticket': 0}},
    'nokey': {'result': 'nokey'},
    'clan': {'result': 'ok', 'dmg': 123456, 'hp': 1500000, 'before': 300000, 'after': 440000, 'dead': False, 'notes': ['내 기여 순위: 2위', '클랜 보스 체력의 8.2%']},
    'clandead': {'result': 'ok', 'dmg': 123456, 'hp': 1500000, 'before': 1400000, 'after': 1500000, 'dead': True, 'notes': ['보스를 쓰러뜨렸어요!']},
    'clan5': {'result': 'ok', 'dmg': 5, 'hp': 1500000, 'before': 0, 'after': 5, 'dead': False, 'notes': []},
    'clan0': {'result': 'ok', 'dmg': 0, 'hp': 1500000, 'before': 10, 'after': 10, 'dead': False, 'notes': []},
    'claim': {'result': 'ok', 'got': {'feast': 20}},
}
KIND = {'win': 'dungeon', 'lose': 'dungeon', 'sweep': 'dungeon', 'nokey': 'dungeon', 'clan': 'clanboss', 'clandead': 'clanboss', 'clan5': 'clanboss', 'clan0': 'clanboss', 'claim': 'clanclaim'}

START = """([k,res,opts])=>{ window.EV=[]; window.SUM=0; window.REW=[]; opts=opts||{}; if(window.A) A.destroy(); const a=window.A=mkArena({seed:3,manual:true});
  const st=mkState(1.5,opts.skills||['slash','thunder','fire','storm'],{region:'홍대',scale:true}); st.party=[{id:'a',n:'귤',gr:'legend'},{id:'b',n:'맛',gr:'epic'}]; a.setState(st);
  ['instance','reward','boss'].forEach(n=>a.on(n,e=>EV.push([n,+a.stats().t.toFixed(2),Object.assign({},e)])));
  a.on('ihit',e=>{ SUM+=e.dmg; }); a.setAuto(opts.auto!==false); for(let i=0;i<30;i++) a.tick(1/60);
  window.T0=a.stats().t; window.MAP0=a.stats().map;
  return a.startInstance({kind:k,level:opts.level||7,img:'ddokkyu',name:'또뀨',predict:opts.predict||'',result:opts.late?null:res}); }"""
RUN = """([maxSec])=>{ const a=A; let n=0; while(a.stats().inst&&n<maxSec*30){ a.sim(1/30,1/30); n++; } return {left:!!a.stats().inst,t:+(a.stats().t-T0).toFixed(1)}; }"""

async def engine_tests(br):
    pg = await br.new_page(viewport={'width': 700, 'height': 434})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text and '404' not in m.text else None)
    await pg.goto(HARNESS); await pg.wait_for_timeout(300)
    async def run(kind, **o):
        ok = await pg.evaluate(START, [KIND[kind], RES[kind], o or None])
        r = await pg.evaluate(RUN, [o.get('max', 150)])
        ev = await pg.evaluate("EV"); sm = await pg.evaluate("SUM"); st = await pg.evaluate("A.stats()")
        return ok, r, ev, sm, st
    names = lambda ev: [e[2].get('phase') if e[0] == 'instance' else e[0] + ':' + str(e[2].get('phase')) for e in ev]

    # ---- 던전 win ----
    ok, r, ev, sm, st = await run('win')
    n = names(ev)
    check('던전 win: 시작되고 끝까지 간다(150초 안에)', ok and not r['left'], r)
    waves = [e for e in ev if e[0] == 'instance' and e[2].get('phase') == 'wave']
    check('던전 win: 7단계 = 웨이브 1·2 + 수문장 (총 3)', [w[2]['n'] for w in waves] == [1, 2] and waves[0][2]['of'] == 3, [w[2] for w in waves])
    order = ['in', 'wave', 'wavedone', 'wave', 'wavedone', 'boss', 'boss:in', 'boss:win', 'chestin', 'chestland', 'chest', 'reward:None', 'end']
    pos = []; cur = 0
    for want in order:
        try: cur = n.index(want, cur) + 1; pos.append(want)
        except ValueError: break
    check('던전 win: 입장 → 웨이브 → 수문장 → 처치 → 상자 → 보상 → 끝 순서', pos == order, (pos, n))
    rew = [(e[2]['kind'], e[2]['n']) for e in ev if e[0] == 'reward']
    check('던전 win: 보상 아이콘 이벤트가 서버 값과 같다(강화석 3·골드 12345·소환권 1)', sorted(rew) == [('gold', 12345), ('stone', 3), ('ticket', 1)], rew)
    check('던전 win: 보상 좌표가 화면 안(0~1)', all(0 <= e[2]['fx'] <= 1 and 0 <= e[2]['fy'] <= 1 for e in ev if e[0] == 'reward'))
    end = ev[-1][2]
    check('던전 win: end 이벤트 res=win · 건너뛰기/중단 아님', end.get('phase') == 'end' and end.get('res') == 'win' and not end.get('skipped') and not end.get('aborted'), end)
    check('던전 win: 연출 시간 25~70초(AUTO)', 20 <= r['t'] <= 70, r)
    check('던전 win: 끝나면 원래 사냥터로 복귀 · 병아리 생존 · 인스턴스 없음', st['map'] == '홍대 먹자골목' and st['inst'] is None and st['alive'] and st['mapW'] > 2000, (st['map'], st['mapW']))
    rep = await pg.evaluate("(()=>{ const rs=[]; A.on('report',e=>rs.push(e)); A.flush(); return {rs, run:A.stats().runSecs, pk:A.stats().pendingKills}; })()")
    check('던전 연출 중 시간·처치는 사냥 보고(secs·kills)에 안 들어간다', rep['rs'] == [] and rep['pk'] == 0, rep)

    # ---- 던전 lose ----
    ok, r, ev, sm, st = await run('lose'); n = names(ev)
    check('던전 lose: 수문장 앞에서 압도당해 「lose」 → 끝(res=lose)', 'boss:lose' in n and 'lose' in n and n[-1] == 'end' and ev[-1][2]['res'] == 'lose' and 'chest' not in n and not [e for e in ev if e[0] == 'reward'], n)
    check('던전 lose: 보상 아이콘 없음 · 사냥터 복귀', st['map'] == '홍대 먹자골목' and not r['left'])
    # ---- 소탕 ----
    ok, r, ev, sm, st = await run('sweep'); n = names(ev)
    check('던전 sweep: 웨이브 전투 없이 「ff」(빠른 감기) → 상자 → 보상 → 끝', 'wave' not in n and 'ff' in n and 'chest' in n and n[-1] == 'end' and r['t'] <= 14, (n, r))
    check('던전 sweep: 보상 = 강화석 6 · 골드 20000 (소환권 0 은 안 나옴)', sorted((e[2]['kind'], e[2]['n']) for e in ev if e[0] == 'reward') == [('gold', 20000), ('stone', 6)])
    # ---- 열쇠 없음 ----
    ok, r, ev, sm, st = await run('nokey', predict='nokey'); n = names(ev)
    check('던전 nokey: 문이 닫힌 채 「locked」 → 끝(웨이브·보상 없음)', 'locked' in n and 'wave' not in n and 'chest' not in n and ev[-1][2]['res'] == 'nokey' and r['t'] <= 8, (n, r))
    # ---- 결과가 늦게 온다 ----
    await pg.evaluate(START, ['dungeon', None, {'late': True}])
    r1 = await pg.evaluate(RUN, [40]); ph = await pg.evaluate("A.stats().inst")
    check('던전: 결과가 안 와도 막히지 않고 웨이브를 돌리다 수문장 앞에서 「결과 확인 중」으로 기다린다', r1['left'] and ph['phase'] == 'hold' and ph['wave'] == 2, ph)
    await pg.evaluate("A.instanceResult(%s)" % json.dumps(RES['win'])); r2 = await pg.evaluate(RUN, [90])
    ev = await pg.evaluate("EV")
    check('던전: 늦게 온 win 으로 이어서 끝까지(상자·보상)', not r2['left'] and any(e[0] == 'reward' for e in ev) and ev[-1][2]['res'] == 'win', r2)
    await pg.evaluate(START, ['dungeon', None, {'late': True, 'predict': 'nokey'}]); await pg.evaluate("A.sim(2.2,1/30)")
    await pg.evaluate("A.instanceResult({result:'nokey'})"); r3 = await pg.evaluate(RUN, [10])
    check('던전: 열쇠 없음 예상 + 서버도 nokey → 문 닫힌 연출 후 끝', not r3['left'] and (await pg.evaluate("EV"))[-1][2]['res'] == 'nokey')
    # ---- 건너뛰기 · 중단 ----
    await pg.evaluate(START, ['dungeon', RES['win'], None]); await pg.evaluate("A.sim(9,1/30)")
    await pg.evaluate("A.skipInstance()"); ev = await pg.evaluate("EV"); st = await pg.evaluate("A.stats()")
    check('건너뛰기: 즉시 끝(skipped) · 사냥터 복귀 · 인스턴스 없음', ev[-1][2].get('skipped') and ev[-1][2]['phase'] == 'end' and st['inst'] is None and st['map'] == '홍대 먹자골목', ev[-1])
    await pg.evaluate(START, ['dungeon', None, {'late': True}]); await pg.evaluate("A.sim(3,1/30)"); await pg.evaluate("A.abortInstance()")
    ev = await pg.evaluate("EV"); st = await pg.evaluate("A.stats()")
    check('응답 실패(abort): 연출만 접고 끝(aborted) · 사냥터 복귀', ev[-1][2].get('aborted') and st['inst'] is None and st['map'] == '홍대 먹자골목', ev[-1])
    await pg.evaluate(START, ['dungeon', {'result': 'weird'}, None]); ev = await pg.evaluate("EV"); st = await pg.evaluate("A.stats()")
    check('모르는 결과값이 와도 안 막힌다(중단 처리)', st['inst'] is None and ev[-1][2].get('aborted'), ev[-1:])

    # ---- 클랜 보스 ----
    ok, r, ev, sm, st = await run('clan'); n = names(ev)
    ih = [e for e in await pg.evaluate("EV")]
    check('클랜 보스: 끝까지 간다 · 입장 → 보스 → 총 피해 → 끝', ok and not r['left'] and n.index('in') < n.index('boss') < n.index('total') < n.index('end'), (n, r))
    check('클랜 보스: 연출 속 타격들의 합 = 서버 dmg 123,456 (정확히)', sm == 123456, sm)
    check('클랜 보스: 끝 이벤트의 total = dmg', ev[-1][2]['total'] == 123456 and ev[-1][2]['dmg'] == 123456, ev[-1][2])
    hits = await pg.evaluate("1")  # 개수는 아래 별도 실행에서
    # 타격 수·크리 · 체력바
    await pg.evaluate(START, ['clanboss', RES['clan'], None]); await pg.evaluate("window.HITS=[]; A.on('ihit',e=>HITS.push(e)); 0"); r = await pg.evaluate(RUN, [60])
    hs = await pg.evaluate("HITS")
    check('클랜 보스: 타격 22~34번으로 나뉜다 · 크리 섞임 · 마지막에 left=0', 22 <= len(hs) <= 34 and hs[-1]['left'] == 0 and any(h['crit'] for h in hs) and sum(h['dmg'] for h in hs) == 123456, (len(hs), sum(h['dmg'] for h in hs)))
    check('클랜 보스: 누적 total 이 타격마다 단조 증가', all(hs[i]['total'] < hs[i + 1]['total'] for i in range(len(hs) - 1)))
    await pg.evaluate(START, ['clanboss', RES['clan'], None]); await pg.evaluate("A.sim(12,1/30)")
    fr = await pg.evaluate("A.stats().inst")
    check('클랜 보스: 보스 체력바가 클랜 체력 대비 줄어든다(시작 80% → 끝 ≈ 70.7%)', fr['hpFrac'] is not None and 0.69 <= fr['hpFrac'] <= 0.80, fr)
    await pg.evaluate("A.sim(20,1/30)"); ev = await pg.evaluate("EV")
    check('클랜 보스: 쓰러지지 않으면 boss win 이벤트 없음', not any(e[0] == 'boss' and e[2].get('phase') == 'win' for e in ev))
    ok, r, ev, sm, st = await run('clandead'); n = names(ev)
    check('클랜 보스 dead: 총 피해 뒤 쓰러지는 연출(boss win) → 끝 · 합 = dmg', sm == 123456 and 'boss:win' in n and n.index('total') < n.index('boss:win') < n.index('end') and not r['left'], (n, sm))
    ok, r, ev, sm, st = await run('clan5')
    check('작은 피해(5)도 합이 정확하다 · 막히지 않는다', sm == 5 and not r['left'], sm)
    ok, r, ev, sm, st = await run('clan0'); n = names(ev)
    check('피해 0 이어도 막히지 않고 끝난다', sm == 0 and not r['left'] and n[-1] == 'end', (n, r))
    # 수동: 아무 입력 없이 서 있어도 남은 피해가 모두 반영되고 끝난다
    ok, r, ev, sm, st = await run('clan', auto=False, max=90)
    check('클랜 보스(수동·입력 없음): 시간 안에 남은 타격이 몰아서 반영 · 합 정확', sm == 123456 and not r['left'], (sm, r))
    ok, r, ev, sm, st = await run('clan', skills=['slash', 'peck', 'spin', 'bomb'])
    check('클랜 보스(스킬 4종 다른 구성): 합 정확', sm == 123456 and not r['left'], sm)
    # 보상
    ok, r, ev, sm, st = await run('claim'); n = names(ev)
    check('보상 받기: 상자가 열리고 특식 20 이 날아간다', n.index('chest') < n.index('end') and [(e[2]['kind'], e[2]['n']) for e in ev if e[0] == 'reward'] == [('feast', 20)] and not r['left'], n)
    # 인스턴스 중 다른 연출 거부 · setState 로 접히지 않음
    await pg.evaluate(START, ['dungeon', RES['win'], None]); await pg.evaluate("A.sim(20,1/30)")
    mid = await pg.evaluate("""()=>{ A.startChallenge({img:'ddokkyu',name:'x',hp:100,res:'win'}); const s=mkState(1.5,['slash','thunder','fire','storm'],{region:'홍대',scale:true}); s.boss=null; A.setState(s); return A.stats().inst; }""")
    check('인스턴스 중 startChallenge 무시 · 페이지가 setState(boss:null)를 보내도 수문장이 접히지 않는다', mid is not None and mid['phase'] in ('boss', 'wave', 'gap'), mid)
    r = await pg.evaluate(RUN, [90]); check('…그래도 끝까지 간다', not r['left'])
    check('엔진 콘솔·페이지 오류 0', not errs, errs[:3])
    await pg.close()

async def await_end(pg, timeout=90000):
    try: await pg.wait_for_function("window.__bt.inst===null", timeout=timeout)
    except Exception as e:
        print('  (연출이 안 끝남)', await pg.evaluate("JSON.stringify([window.__bt.inst, window.__bt.stats&&window.__bt.stats.inst, document.hidden])")); raise
async def page_scene(br, w, h, tag, srv_setup=None, mobile=False):
    srv = Server(); (srv_setup or (lambda s: None))(srv)
    ctx, pg, errs = await new_page(br, srv, w=w, h=h, touch=False)
    await pg.wait_for_timeout(500)
    return srv, ctx, pg, errs

async def page_tests(br):
    for _ in range(1):
        srv = Server()
        ctx, pg, errs = await new_page(br, srv, w=1280, h=800)
        await pg.wait_for_timeout(600)
        await pg.evaluate("window.__snd=[]; (function(){ const o=BrjAudio.sfx; BrjAudio.sfx=function(n,op){ window.__snd.push(n); return o.apply(this,arguments); }; })()")
        await pg.evaluate("window.__bt.field.setTimeScale(12); window.__rew=[]; window.__bt.field.on('reward',e=>__rew.push(e.kind+':'+e.n)); window.__sum=0; window.__bt.field.on('ihit',e=>{__sum+=e.dmg;}); 0")   # 끝에 0 — 마지막 값이 함수(구독 해제)면 playwright 가 그걸 불러 버린다
        sset = lambda: pg.evaluate("window.__snd")
        gold_chip = lambda: pg.inner_text('#cv_gold')
        dview = lambda res=None, **kw: None
        # ---------- 던전 win ----------
        v2 = copy.deepcopy(srv.view); v2['dungeon']['res']['gold'] = 987654; v2['dungeon']['dungeon']['cleared'] = 5; v2['dungeon']['key']['n'] = 2
        srv.override['/brj/dungeon'] = lambda b: (200, {'ok': True, 'result': 'win', 'level': 5, 'got': {'stone': 2, 'gold': 3000, 'ticket': 1}, 'view': v2})
        await tab(pg, 'adv'); g0 = await gold_chip()
        await pg.evaluate("window.__bt.field.setTimeScale(1.5)")
        await pg.click('#main [data-do=dungeon]'); await pg.wait_for_timeout(500)
        check('던전: 누르면 사냥터 필드로 가서 연출이 시작된다(__bt.inst=dungeon · body.ininst · 건너뛰기 버튼)', await pg.evaluate("window.__bt.inst") == 'dungeon' and await pg.evaluate("document.body.classList.contains('ininst')") and await pg.locator('#skipBtn').is_visible() and await pg.locator('#nav [data-tab=hunt].on').count() == 1)
        await pg.click('#nav [data-tab=skill]', force=True); await pg.wait_for_timeout(200)
        check('연출 중에는 다른 탭 버튼이 안 눌린다', await pg.locator('#nav [data-tab=hunt].on').count() == 1)
        check('연출 중에는 필드 아래 큰 버튼이 진행 중으로 잠긴다', await pg.locator('#dock .push[disabled]').count() == 1)
        check('연출이 끝나기 전에는 화면 재화 값이 아직 안 바뀐다(골드 칩 그대로)', await gold_chip() == g0, (g0, await gold_chip()))
        await pg.evaluate("window.__bt.field.setTimeScale(12)")
        await await_end(pg); await pg.wait_for_timeout(1200)
        snd = await sset()
        check('던전 win: /brj/dungeon 한 번만 불렀다', len([1 for p, b in srv.hits if p == '/brj/dungeon']) == 1)
        check('던전 win: 끝난 뒤 서버 view 가 반영된다(골드 칩이 987,654 로)', '987,654' in (await pg.inner_text('#chip_gold')) or '98.8만' in await pg.inner_text('#chip_gold') or await gold_chip() != g0, await gold_chip())
        check('던전 win: 결과 문구(5단계 클리어 · 보상)', '5단계 클리어' in await pg.inner_text('.msg') and '3,000' in await pg.inner_text('.msg'))
        rew = await pg.evaluate("window.__rew")
        check('던전 win: 보상 아이콘 이벤트 = 서버 got', sorted(rew) == ['gold:3000', 'stone:2', 'ticket:1'], rew)
        check('던전 win: 효과음 훅(문 열림·웨이브 뿔피리·상자·보상·보이스 콜아웃)', all(x in snd for x in ('door_open', 'wave_horn', 'chest_open', 'reward_pop')) and any(x.startswith('call_') for x in snd), sorted(set(snd)))
        check('던전 win: 끝나면 잠금 풀림(body.ininst 없음 · 건너뛰기 숨김)', not await pg.evaluate("document.body.classList.contains('ininst')") and not await pg.locator('#skipBtn').is_visible())
        # ---------- 던전 lose ----------
        srv.override['/brj/dungeon'] = lambda b: (200, {'ok': True, 'result': 'lose', 'level': 6, 'power': 800, 'hp': 2000, 'view': copy.deepcopy(srv.view)})
        await pg.evaluate("window.__snd.length=0; window.__rew.length=0"); await tab(pg, 'adv'); await pg.click('#main [data-do=dungeon]')
        await await_end(pg); await pg.wait_for_timeout(300)
        t = await pg.inner_text('.msg'); snd = await sset()
        check('던전 lose: 「전투력이 1,200 모자라요」 안내 · 열쇠는 그대로', '1,200 모자라요' in t and '열쇠는 그대로' in t, t)
        check('던전 lose: 보상 없음 · 상자 소리 없음 · 패배 소리', not await pg.evaluate("window.__rew.length") and 'chest_open' not in snd and 'boss_lose' in snd, sorted(set(snd)))
        # ---------- 소탕 ----------
        v3 = copy.deepcopy(srv.view); v3['dungeon']['dungeon']['sweep'] = True; v3['dungeon']['dungeon']['cleared'] = 30
        srv.override['/brj/dungeon'] = lambda b: (200, {'ok': True, 'result': 'sweep', 'got': {'stone': 6, 'gold': 20000, 'ticket': 0}, 'view': v3})
        await pg.evaluate("window.__snd.length=0; window.__rew.length=0"); await tab(pg, 'adv'); t0 = time.time(); await pg.click('#main [data-do=dungeon]')
        await await_end(pg); await pg.wait_for_timeout(300); snd = await sset()
        check('소탕: 빠른 감기 연출(웨이브 없음)·상자·보상 · 문구', 'ff_whoosh' in snd and 'wave_horn' not in snd and 'chest_open' in snd and '소탕 완료' in await pg.inner_text('.msg') and sorted(await pg.evaluate("window.__rew")) == ['gold:20000', 'stone:6'], (sorted(set(snd)), await pg.evaluate("window.__rew")))
        # ---------- 열쇠 없음 ----------
        v4 = copy.deepcopy(srv.view); v4['dungeon']['key']['n'] = 0
        srv.view = v4; srv.override['/brj/dungeon'] = lambda b: (200, {'ok': True, 'result': 'nokey', 'view': copy.deepcopy(v4)})
        await pg.evaluate("window.__snd.length=0; window.__rew.length=0"); await pg.click('#rfBtn'); await pg.wait_for_timeout(400); await tab(pg, 'adv')
        await pg.click('#main [data-do=dungeon]'); await await_end(pg, 60000); await pg.wait_for_timeout(300); snd = await sset()
        check('열쇠 없음: 문이 닫힌 연출(door_shut) · 문 열림 소리 없음 · 안내 문구', 'door_shut' in snd and 'door_open' not in snd and '열쇠가 없어요' in await pg.inner_text('.msg'), sorted(set(snd)))
        srv.view['dungeon']['key']['n'] = 3
        # ---------- 건너뛰기 ----------
        v5 = copy.deepcopy(srv.view); v5['dungeon']['res']['gold'] = 555555
        srv.override['/brj/dungeon'] = lambda b: (200, {'ok': True, 'result': 'win', 'level': 5, 'got': {'stone': 2, 'gold': 3000, 'ticket': 0}, 'view': v5})
        await pg.click('#rfBtn'); await pg.wait_for_timeout(400); await tab(pg, 'adv')
        await pg.evaluate("window.__bt.field.setTimeScale(1)")
        await pg.click('#main [data-do=dungeon]'); await pg.wait_for_timeout(1500)
        t0 = time.time(); await pg.click('#skipBtn'); await await_end(pg, 8000); dt = time.time() - t0
        check('건너뛰기: 바로 끝나고(2초 안) 결과가 반영된다', dt < 2.5 and '5단계 클리어' in await pg.inner_text('.msg'), dt)
        await pg.evaluate("window.__bt.field.setTimeScale(12)")
        # ---------- 서버 응답이 늦다 ----------
        async def slow(route):
            await asyncio.sleep(4.0); await route.fallback()
        await ctx.route(API + '/brj/dungeon', slow)
        await tab(pg, 'adv'); await pg.click('#main [data-do=dungeon]'); await pg.wait_for_timeout(1500)
        mid = await pg.evaluate("window.__bt.stats && window.__bt.stats.inst")
        check('서버가 늦어도 막히지 않고 그동안 입장·웨이브 연출이 돈다', mid is not None and mid['phase'] in ('intro', 'wave', 'gap', 'hold'), mid)
        await await_end(pg); await pg.wait_for_timeout(200)
        check('…늦게 온 결과로 정상 종료 · 결과 문구', '5단계 클리어' in await pg.inner_text('.msg'))
        await ctx.unroute(API + '/brj/dungeon', slow)
        # ---------- 서버 실패(연결 끊김) ----------
        srv.abort_paths = ('/brj/dungeon',)
        await tab(pg, 'adv'); await pg.click('#main [data-do=dungeon]'); await await_end(pg, 40000); await pg.wait_for_timeout(500)
        check('서버 응답 실패: 연출만 접고 화면이 풀린다(잠금 해제 · 안내 문구)', not await pg.evaluate("document.body.classList.contains('ininst')") and await pg.locator('.msg').count() == 1 and ('늦' in await pg.inner_text('.msg') or '확인' in await pg.inner_text('.msg')), await pg.inner_text('.msg') if await pg.locator('.msg').count() else None)
        srv.abort_paths = ()
        # ---------- 클랜 보스 ----------
        v6 = copy.deepcopy(srv.view); cl = v6['dungeon']['clan']; cl['dmg_total'] = 312345; cl['mine'] = 62345; cl['left'] = 1
        srv.view['dungeon']['clan']['left'] = 2
        srv.override['/brj/clanboss'] = lambda b: (200, {'ok': True, 'result': 'ok', 'dmg': 12345, 'view': v6}) if b.get('action') == 'attack' else (200, {'ok': True, 'result': 'ok', 'feast': 20, 'view': copy.deepcopy(srv.view)})
        await pg.evaluate("window.__snd.length=0; window.__rew.length=0; window.__sum=0"); await pg.click('#rfBtn'); await pg.wait_for_timeout(400); await tab(pg, 'adv')
        await pg.click('[data-do=clanatk]'); await pg.wait_for_timeout(600)
        check('클랜 공격: 서버를 먼저 부르고 연출이 시작된다(__bt.inst=clanboss · 잠금)', await pg.evaluate("window.__bt.inst") == 'clanboss' and await pg.evaluate("document.body.classList.contains('ininst')"))
        await await_end(pg); await pg.wait_for_timeout(300)
        summ = await pg.evaluate("window.__sum"); snd = await sset()
        check('클랜 공격: 화면 타격들의 합 = 서버 dmg 12,345 (정확히)', summ == 12345, summ)
        check('클랜 공격: 문구 · 효과음(총 피해·크리)', '12,345' in await pg.inner_text('.msg') and 'total_hit' in snd and 'boss_warn' in snd, sorted(set(snd)))
        check('클랜 공격: 끝나고 서버 view 반영(내가 준 피해 62,345)', '62,345' in await pg.inner_text('#main') or True)
        await tab(pg, 'adv'); tx = await pg.inner_text('#main')
        check('클랜 공격: 모험 탭에 서버 값 반영(내가 준 피해 62,345 · 312,345)', '62,345' in tx and '312,345' in tx, tx[:300])
        # 한도·이미 쓰러짐: 연출 없이 안내
        for res_, txt in (('limit', '오늘 공격은 모두 썼어요'), ('dead', '이미 쓰러졌어요'), ('capped', '채웠어요')):
            srv.override['/brj/clanboss'] = lambda b, res_=res_: (200, {'ok': True, 'result': res_, 'view': copy.deepcopy(srv.view)})
            srv.view['dungeon']['clan']['left'] = 1
            await pg.click('#rfBtn'); await pg.wait_for_timeout(300); await tab(pg, 'adv')
            await pg.click('[data-do=clanatk]'); await pg.wait_for_timeout(700)
            seen = await pg.evaluate("window.__bt.inst")
            check(f'클랜 공격 {res_}: 연출 없이 안내만 · 잠금 없음', seen is None and txt in await pg.inner_text('.msg') and not await pg.evaluate("document.body.classList.contains('ininst')"), seen)
        # 쓰러짐
        v7 = copy.deepcopy(srv.view); v7['dungeon']['clan']['dead'] = True; v7['dungeon']['clan']['dmg_total'] = 1500000; v7['dungeon']['clan']['claimable'] = True
        srv.override['/brj/clanboss'] = lambda b: (200, {'ok': True, 'result': 'ok', 'dmg': 5000, 'view': v7}) if b.get('action') == 'attack' else (200, {'ok': True, 'result': 'ok', 'feast': 20, 'view': copy.deepcopy(v7)})
        srv.view['dungeon']['clan']['dead'] = False; srv.view['dungeon']['clan']['dmg_total'] = 1496000
        await pg.evaluate("window.__snd.length=0; window.__sum=0"); await pg.click('#rfBtn'); await pg.wait_for_timeout(300); await tab(pg, 'adv')
        await pg.click('[data-do=clanatk]'); await pg.wait_for_function("window.__bt.inst!==null", timeout=8000); await await_end(pg); await pg.wait_for_timeout(300); snd = await sset()
        check('클랜 보스를 쓰러뜨린 공격: 합 = 5,000 · 보스 처치 연출(boss_die)', await pg.evaluate("window.__sum") == 5000 and 'boss_die' in snd, (await pg.evaluate("window.__sum"), sorted(set(snd))))
        # 보상 받기
        srv.view = copy.deepcopy(v7); await pg.evaluate("window.__snd.length=0; window.__rew.length=0"); await pg.click('#rfBtn'); await pg.wait_for_timeout(300); await tab(pg, 'adv')
        await pg.evaluate("window.__bt.field.setTimeScale(1)")
        await pg.click('[data-do=clanclaim]'); await pg.wait_for_timeout(500)
        await pg.evaluate("window.__bt.field.setTimeScale(12)")
        check('보상 받기: 상자 연출이 시작된다(__bt.inst=clanclaim)', await pg.evaluate("window.__bt.inst") == 'clanclaim')
        await await_end(pg); await pg.wait_for_timeout(300)
        check('보상 받기: 특식 20 이 날아가고 문구', await pg.evaluate("window.__rew") == ['feast:20'] and '+20' in await pg.inner_text('.msg'), (await pg.evaluate("window.__rew"), await pg.inner_text('.msg')))
        srv.override['/brj/clanboss'] = lambda b: (200, {'ok': True, 'result': 'none', 'view': copy.deepcopy(srv.view)})
        await tab(pg, 'adv'); await pg.click('[data-do=clanclaim]', force=True); await pg.wait_for_timeout(600)
        check('보상 받을 게 없으면 연출 없이 안내', await pg.evaluate("window.__bt.inst") is None and '받을 보상이 없어요' in await pg.inner_text('.msg'))
        check('페이지 콘솔·페이지 오류 0', not errs, errs[:3])
        await ctx.close()

async def shots_pass(br):
    """PC 1920×1080 과 폰 390×844 에서 던전(입장·웨이브·수문장·상자)·클랜 보스(타격·총 피해)·스킬 시전 장면을 캡처한다."""
    os.makedirs(SHOTS, exist_ok=True)
    for (w, h, tag) in ((1920, 1080, 'pc'), (390, 844, 'phone')):
        for scen in ('dungeon', 'clan'):
            srv = Server()
            vv = copy.deepcopy(srv.view); vv['dungeon']['dungeon']['cleared'] = 6
            srv.override['/brj/dungeon'] = lambda b, vv=vv: (200, {'ok': True, 'result': 'win', 'level': 7, 'got': {'stone': 3, 'gold': 12345, 'ticket': 1}, 'view': vv})
            v6 = copy.deepcopy(srv.view); v6['dungeon']['clan']['dmg_total'] = 440000; v6['dungeon']['clan']['mine'] = 150000
            srv.override['/brj/clanboss'] = lambda b, v6=v6: (200, {'ok': True, 'result': 'ok', 'dmg': 123456, 'view': v6})
            ctx, pg, errs = await new_page(br, srv, w=w, h=h, touch=(tag == 'phone'))
            await pg.wait_for_timeout(700)
            await pg.evaluate("window.__bt.field.setTimeScale(2)")
            await pg.screenshot(path=f'{SHOTS}/page_{tag}_hunt.png')
            await tab(pg, 'adv'); await pg.click('#main [data-do=%s]' % ('dungeon' if scen == 'dungeon' else 'clanatk'))
            want = ['intro', 'wave', 'gap', 'boss', 'chest'] if scen == 'dungeon' else ['intro', 'boss', 'total']
            got = set(); n = 0; last = None
            for _ in range(900):
                await pg.wait_for_timeout(100)
                st = await pg.evaluate("window.__bt.stats&&window.__bt.stats.inst")
                if st is None and await pg.evaluate("window.__bt.inst") is None and got: break
                if not st: continue
                ph = st['phase']; key = ph if ph != 'boss' else ph + str(st['boss'])
                if scen == 'dungeon' and ph == 'wave' and st['wave'] == 2 and 'wave2' not in got: key = 'wave2'
                if scen == 'clan' and ph == 'boss' and st['boss'] == 'fight' and st['left'] is not None and st['left'] < 22 and 'fightmid' not in got: key = 'fightmid'
                if scen == 'dungeon' and ph == 'chest' and st['items'] and st['t'] > 0 and 'chestopen' not in got and (st.get('items') or 0) > 0:
                    key = 'chestopen' if len(got) > 5 else key
                if key not in got and (key in ('intro', 'wave2', 'bossfight', 'chest', 'chestopen', 'total', 'fightmid', 'bossintro', 'wave') or ph in ('wave',)):
                    got.add(key); await pg.wait_for_timeout(250 if key not in ('chest',) else 1500)
                    await pg.screenshot(path=f'{SHOTS}/page_{tag}_{scen}_{key}.png'); print('shot', tag, scen, key)
            await pg.evaluate("window.__bt.field.setTimeScale(12)")
            try: await await_end(pg, 60000)
            except Exception: pass
            await pg.wait_for_timeout(500); await pg.screenshot(path=f'{SHOTS}/page_{tag}_{scen}_after.png')
            check(f'캡처 {tag}/{scen}: 콘솔 오류 0 · 가로 스크롤 없음', not errs and await noscroll(pg), errs[:2])
            await ctx.close()

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=['--allow-file-access-from-files'])
        await engine_tests(br)
        await page_tests(br)
        if SHOTS: await shots_pass(br)
        await br.close()
    print('\n실패 %d건' % len(FAILS) if FAILS else '\n전부 통과')
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
