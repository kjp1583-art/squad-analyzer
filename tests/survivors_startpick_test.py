# -*- coding: utf-8 -*-
"""🎒 출발 보너스(시작 3택 1 · S-5) 검증 (2026-10-21).
사용: python3.13 tests/survivors_startpick_test.py      (종료코드 0 = 전부 통과)
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅을 꽂는다.
구성: A 자동 시험은 건너뜀 · B 오버레이(시간 정지·1~3 키·폰 360) · C 3장 중복 없음·가중치·성향 · D 효과 10종 · E 일일 도전 시드 · F 이어하기"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
H.HOOK += "\nwindow.__sp={pauseGame,STARTV,STARTW,STARTCFG,startDraw,startApply,startPickOpen,svB,get STCUR(){return STCUR},RES,moveMul,magMul,cdMul,xpMul,PASS,REL,MAXLV,hpText,mhpSrc};\n"
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)[:300]) if not cond and extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)
def near(a, b, tol=1e-9): return a is not None and abs(a - b) <= tol
ALL = ['wlv', 'ps', 'rel', 'mv', 'hp', 'xp', 'ch', 'rr', 'mag', 'cd']

async def main():
    H.make_copy(os.environ.get('SV_SRC', 'survivors.html')); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p, args=['--autoplay-policy=no-user-gesture-required'])
        ctx, pg, errs = await H.new_page(b, srv.port, w=360, h=640)
        await pg.evaluate("__p6x.srvUnl(['brj'])")
        E = lambda js, *a: pg.evaluate(js, *a)

        # ───────────────── A. 자동 시험에서는 건너뛴다(옛 시험이 start() 직후 play 를 믿는다)
        r = await E("()=>{const x=__p6x;x.CH_set('brj');x.start();return [x.state,__sp.STCUR.length,__sp.svB('mv')]}")
        check('A1 webdriver 에서는 오버레이 없이 바로 play', r[0] == 'play' and r[1] == 0, r)

        # ───────────────── B. 오버레이
        await E("()=>{__sp.STARTCFG.force=1}")
        r = await E("()=>{const x=__p6x;x.CH_set('brj');x.start();return [x.state,__sp.STCUR.length,document.getElementById('stpick').classList.contains('on'),document.getElementById('stChoices').children.length,document.getElementById('lvup').classList.contains('on')]}")
        check('B1 force 면 start() 가 stpick 상태로 멈추고 카드 3장이 뜬다', r == ['stpick', 3, True, 3, False], r)
        t0 = await E("()=>__p6x.S.t"); await pg.wait_for_timeout(700)
        r = await E("()=>[__p6x.S.t,__p6x.state,__p6x.S.pendingLv,Object.keys(__p6x.S.w).length]")
        check('B2 고르기 전에는 게임 시간이 흐르지 않는다(rAF 700ms)', r[0] == t0 and r[1] == 'stpick', r)
        r = await E("()=>{const d=document.documentElement,bx=document.querySelector('#stpick .box').getBoundingClientRect();return [d.scrollWidth,innerWidth,bx.left,bx.right,bx.bottom,innerHeight,document.body.scrollWidth]}")
        check('B3 폰 360 폭에서 가로 넘침 0 · 상자가 화면 안', r[0] <= r[1] and r[2] >= 0 and r[3] <= r[1] and r[6] <= r[1], r)
        await pg.keyboard.press('Digit2'); await pg.wait_for_timeout(100)
        r = await E("()=>[__p6x.state,document.getElementById('stpick').classList.contains('on'),__p6x.S.x3.sv&&__p6x.S.x3.sv.id]")
        check('B4 키보드 2 → 두 번째 카드 선택 → play 로 시작', r[0] == 'play' and not r[1] and r[2], r)
        await pg.wait_for_timeout(300)
        r = await E("()=>__p6x.S.t"); check('B5 고른 뒤 시간이 흐른다', r > 0, r)
        # 클릭 선택 + 중복 클릭 방지
        r = await E("()=>{const x=__p6x;x.start();const bs=[...document.getElementById('stChoices').children];bs[0].click();const id=x.S.x3.sv.id;bs[1].click();return [x.state,id===x.S.x3.sv.id]}")
        check('B6 클릭으로 고르고, 이미 시작한 뒤 다른 카드를 눌러도 무시', r == ['play', True], r)

        # ───────────────── C. 3장 중복 없음 · 가중치 · 성향
        r = await E("""()=>{const x=__p6x;let bad=0,dupArg=0;const cnt={};
          for(let i=0;i<400;i++){x.CH_set('brj');x.start();/* force → 오버레이 */const c=__sp.STCUR,ids=c.map(q=>q.id);
            if(c.length!==3||new Set(ids).size!==3)bad++;for(const q of c){cnt[q.id]=(cnt[q.id]||0)+1;
              if(q.id==='ps'&&(!__sp.PASS[q.a]||q.a==='rev'||x.S.ps[q.a]))dupArg++;
              if(q.id==='rel'&&(!x.REL[q.a]||x.REL[q.a].ch))dupArg++;}}
          return {bad,dupArg,cnt}}""")
        check('C1 400판: 늘 서로 다른 3장 · 패시브/유물 인자가 유효(부활·시그니처 제외)', r['bad'] == 0 and r['dupArg'] == 0 and all(r['cnt'].get(k, 0) > 0 for k in ALL), r)
        r = await E("""()=>{const x=__p6x,out={};for(const ch of ['ddmj','ildj']){x.CH_set(ch);const cnt={};for(let i=0;i<1500;i++){x.start();for(const q of __sp.STCUR)cnt[q.id]=(cnt[q.id]||0)+1;}out[ch]=cnt;}return out}""")
        a, c2 = r['ddmj'], r['ildj']
        check('C2 성향 가중: 근접(단단묵직)은 HP·이속, 원거리(일단즐겨)는 쿨·범위가 더 자주', a['hp'] > c2['hp'] * 1.15 and a['mv'] > c2['mv'] * 1.1 and c2['cd'] > a['cd'] * 1.2 and c2['mag'] > a['mag'] * 1.1, (a, c2))

        # ───────────────── D. 효과 10종(장비 없는 평범한 캐릭터 + 장비·유물 낀 캐릭터)
        async def fresh(ch='brj'):
            await E("(ch)=>{const x=__p6x;x.CH_set(ch);__sp.STARTCFG.force=0;x.start();}", ch)
        async def apply(cid, a=None):
            return await E("([cid,a])=>{const S=__p6x.S;__sp.startApply({id:cid,a});return 1}", [cid, a])
        await fresh('brj')
        base = await E("()=>{const S=__p6x.S;return {w:S.w.quill,mv:__sp.moveMul(),mag:__sp.magMul(),cd:__sp.cdMul(),xp:__sp.xpMul(),mhp:S.p.mhp,hp:S.p.hp,rr:S.rr,ban:S.ban}}")
        await apply('wlv'); r = await E("()=>__p6x.S.w.quill"); check('D1 시작 무기 Lv+1', r == base['w'] + 1, r)
        await fresh('brj'); await apply('ps', 'crit'); r = await E("()=>[__p6x.S.ps.crit,__p6x.S.p.mhp]"); check('D2 패시브 Lv1 지급', r[0] == 1, r)
        await fresh('brj'); await apply('ps', 'hp'); r = await E("()=>[__p6x.S.ps.hp,__p6x.S.p.mhp,__p6x.S.mhpBy.hp]"); check('D2b 최대HP 패시브는 +25 · 출처표(mhpBy)에 기록', r[0] == 1 and r[1] == base['mhp'] + 25 and r[2] == 25, r)
        await fresh('brj'); await apply('rel', 'tenth'); r = await E("()=>__p6x.S.rel.tenth"); check('D3 유물 Lv1 지급', r == 1, r)
        await fresh('brj'); await apply('mv'); r = await E("()=>__sp.moveMul()"); check('D4 이동속도 +10%', near(r, base['mv'] + .10, 1e-9), (r, base['mv']))
        await fresh('brj'); await apply('hp'); r = await E("()=>{const S=__p6x.S,m=__sp.mhpSrc();return [S.p.mhp,S.p.hp,S.mhpBy.st,m.etc]}")
        check('D5 최대HP +20%(출처표 st) · 현재HP도 채움 · 「기타」0', r[0] == base['mhp'] + round(base['mhp'] * .2) and r[1] == r[0] and r[2] == round(base['mhp'] * .2) and r[3] == 0, r)
        await fresh('brj'); await apply('xp'); r = await E("()=>{const S=__p6x.S,a=__sp.xpMul();S.t=299;const b=__sp.xpMul();S.t=300.5;const c=__sp.xpMul();return [a,b,c]}")
        check('D6 경험치 +0.3 은 처음 5분(S.t<300)만', near(r[0], base['xp'] + .3) and near(r[1], base['xp'] + .3) and near(r[2], base['xp']), (r, base['xp']))
        await fresh('brj'); await apply('rr'); r = await E("()=>[__p6x.S.rr,__p6x.S.ban]"); check('D7 다시 뽑기 +2 · 봉인 +1', r == [base['rr'] + 2, base['ban'] + 1], r)
        await fresh('brj'); await apply('mag'); r = await E("()=>__sp.magMul()"); check('D8 획득 범위 +30%', near(r, base['mag'] + .30), (r, base['mag']))
        await fresh('brj'); await apply('cd'); r = await E("()=>__sp.cdMul()"); check('D9 쿨타임 −8%', near(r, base['cd'] * .92, 1e-9), (r, base['cd']))
        await fresh('brj'); await apply('ch')
        r = await E("""()=>{const x=__p6x,S=x.S;let n1=0,n2=0;const real=x.applyUp;
          // 보스 상자를 두 번 열어 카드 수를 센다(같은 난수열로 두 번)
          const cnt=()=>document.querySelectorAll('#chestList .cr:not(.ev)').length-1;   // 다시 뽑기 줄 하나 뺀다
          Math.random=(()=>{let s=1;return ()=>{s=(s*16807)%2147483647;return s/2147483647}})();
          x.openChest();n1=cnt();const sv1=S.x3.sv.ch;x.resume();
          Math.random=(()=>{let s=1;return ()=>{s=(s*16807)%2147483647;return s/2147483647}})();
          x.openChest();n2=cnt();return {n1,n2,sv1,sv2:S.x3.sv.ch,title:document.getElementById('chestT').textContent}}""")
        check('D10 첫 보스 상자만 카드 +1장 · 소모되면 sv.ch=0', r['n1'] == r['n2'] + 1 and r['sv1'] == 0 and r['sv2'] == 0, r)

        # 엄장신·장비 낀 판에서 전 효과가 오류 없이 적용되고 한 판이 돈다(CLAUDE.md 🧪 — 조건부 경로도 한 번씩)
        for ch in ['brj', 'ddmj', 'kyo', 'tw', 'yj', 'bbb']:
            for cid in ALL:
                await fresh(ch)
                a = await E("([cid])=>{const S=__p6x.S;S.rel.tenth=0;delete S.rel.tenth;if(cid==='ps')return 'crit';if(cid==='rel')return 'leech';return null}", [cid])
                await apply(cid, a)
                r = await E("()=>{const x=__p6x;const S=x.S;S.p.hp=S.p.mhp;for(let i=0;i<120;i++){S.p.hp=S.p.mhp;x.keys={KeyD:true};x.update(1/30);if(x.state==='lvup')x.pick(x.CUR[0]);}return [x.state,isFinite(S.p.hp),isFinite(S.p.mhp),S.t>3]}")
                if not (r[0] in ('play', 'lvup') and r[1] and r[2] and r[3]):
                    check('D11 %s×%s 4초 진행' % (ch, cid), False, r)
        check('D11 6캐릭터 × 10효과 4초씩 진행 — 이상 없음', not any(f.startswith('D11') for f in FAILS))

        # ───────────────── E. 일일 도전: 같은 날 같은 3장
        async def daily_pick():
            return await E("""()=>{const x=__p6x;__sp.STARTCFG.force=1;x.CH_set('brj');x.start({daily:true});const c=JSON.stringify(__sp.STCUR);return c}""")
        d1 = await daily_pick(); d2 = await daily_pick(); d3 = await daily_pick()
        check('E1 오늘의 도전: 시작할 때마다 같은 3장(무작위 패시브·유물 포함)', d1 == d2 == d3 and len(json.loads(d1)) == 3, (d1, d2, d3))
        # 일반 판은 무작위: 40번 중 서로 다른 구성이 여럿
        r = await E("""()=>{const x=__p6x,s=new Set();for(let i=0;i<40;i++){x.CH_set('brj');x.start();s.add(JSON.stringify(__sp.STCUR));}return s.size}""")
        check('E2 일반 판은 무작위(40번에 여러 구성)', r > 5, r)

        # ───────────────── F. 이어하기: 지속 효과가 저장·복구된다
        async def roundtrip(cid, a=None):
            await E("()=>{__sp.STARTCFG.force=0}")
            await E("([cid,a])=>{const x=__p6x;x.CH_set('brj');x.start();__sp.startApply({id:cid,a});for(let i=0;i<30;i++)x.update(1/30);__sp.pauseGame();}", [cid, a])
            return await E("""()=>{const x=__p6x,t=localStorage.getItem(__sp.RES.KEY);if(!t)return {err:'no-save'};
              x.S.x3.sv=null;x.S.rr=-9;x.state='title';const ok=__sp.RES.restore(t);const S=x.S;
              return {ok,sv:S.x3.sv,mv:__sp.moveMul(),mhp:S.p.mhp,mag:__sp.magMul(),cd:__sp.cdMul(),xp:__sp.xpMul(),t:S.t,st:x.state,w:S.w.quill,ps:S.ps,rel:S.rel,rr:S.rr}}""")
        r = await roundtrip('mv'); check('F1 이동속도 보너스가 저장·복구된다', r.get('ok') and r['sv'] and r['sv']['mv'] == .10 and r['sv']['id'] == 'mv' and near(r['mv'], 1 + .10 + 0, 0.5), r)
        r = await roundtrip('hp'); check('F2 최대HP 보너스 복구(mhp 120 + 출처표 일치)', r.get('ok') and r['mhp'] == 120 + 24, r)  # 브장신 기본 hp 20 → 120 → +20%(24)
        r = await roundtrip('xp'); check('F3 초반 경험치 보너스 복구(5분 안)', r.get('ok') and r['sv']['xp'] == .3 and r['xp'] > 1.25, r)
        r = await roundtrip('ps', 'cd'); check('F4 패시브 복구', r.get('ok') and r['ps'].get('cd') == 1, r)
        r = await roundtrip('rel', 'tenth'); check('F5 유물 복구', r.get('ok') and r['rel'].get('tenth') == 1, r)
        r = await roundtrip('wlv'); check('F6 무기 Lv 복구', r.get('ok') and r['w'] == 2, r)

        check('콘솔/페이지 오류 0', not errs, errs[:3])
        await b.close()
    srv.close()
    print('\n%d 항목 중 실패 %d' % (N[0], len(FAILS)))
    if FAILS: print('실패:', FAILS); sys.exit(1)
if __name__ == '__main__': asyncio.run(main())
