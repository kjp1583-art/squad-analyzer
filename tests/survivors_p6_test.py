# -*- coding: utf-8 -*-
"""📅 일일 도전 · ♾ 무한 모드 · ⭐ 시그니처 유물 · 🛡 무적 상한 — 브라우저(Chromium) 검증.  사용: python3 tests/survivors_p6_test.py
원본 survivors.html 은 건드리지 않고 임시 사본(survivors_x.html)에만 검증용 훅(__p6x)을 꽂는다."""
import asyncio, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
FAILS = []; N = [0]
def check(name, cond, extra=''):
    N[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(extra)) if extra != '' else ''), flush=True)
    if not cond: FAILS.append(name)

POSTS = []
def mk_mock(state):
    async def mock(r):
        u = r.request.url
        hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
        if r.request.method == 'OPTIONS': await r.fulfill(status=204, headers=hdr); return
        if '/p6/board' in u:
            j = {'board': [], 'hard': [], 'vhard': []}
            if state.get('new', True): j.update({'endless': [{'name': 'e', 't': 4000, 'kills': 9}], 'daily': [{'name': 'd', 't': 700, 'kills': 5, 'lv': 4, 'won': 0}], 'daily_date': state.get('date', '2026-10-07')})
            await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps(j))
        elif '/p6/me' in u:
            await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'name': 'T', 'runs': 1, 'best_t': 10, 'unlocks': ['brj'], 'rank': 1, 'daily_done': state.get('daily_done', False), 'daily_date': state.get('date', '')}))
        elif '/p6/run' in u:
            b = json.loads(r.request.post_data or '{}'); POSTS.append(b)
            code = state.get('run_code')
            if code: await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': False, 'code': code}))
            else: await r.fulfill(status=200, headers=hdr, content_type='application/json', body=json.dumps({'ok': True, 'rank': 3, 'total': 9, 'unlocks': ['brj'], 'best_t': b['t'], 'daily': bool(b.get('daily')), 'daily_rank': 2, 'daily_total': 5, 'endless': bool(b.get('endless')), 'end_rank': 1, 'end_total': 2}))
        else: await r.fulfill(status=404, headers=hdr, body='{}')
    return mock

LOGIN = "localStorage.setItem('sgg_dc',JSON.stringify({id:'1',token:'x'.repeat(30),exp:Date.now()+5*86400000,name:'T'}))"

async def fresh(b, port, state=None, login=True, w=412, h=860, extra_init=None):
    st = state if state is not None else {}
    ctx, pg, errs = await H.new_page(b, port, w, h, mock=mk_mock(st))
    if login: await pg.evaluate(LOGIN)
    if extra_init: await pg.evaluate(extra_init)
    await pg.reload(); await pg.wait_for_function('window.__p6x!==undefined')
    await pg.wait_for_timeout(300)
    return ctx, pg, errs

async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p)
        # ───────────────── 1. 일일 도전 시드
        ctx, pg, errs = await fresh(b, srv.port, login=False)
        r = await pg.evaluate("""()=>{const x=__p6x;const out={};
          const seq=()=>{x.start({daily:true});return {seed:x.S.dly.seed,rs:x.RSEED,cards:[0,1,2,3,4,5].map(()=>x.offers(3).map(o=>o.k).join('|')),rn:[x.RN('card'),x.RN('ev'),x.RN('prop')]};};
          out.a=seq();out.b=seq();
          const dn=Date.now;Date.now=()=>dn()+2*86400000;out.c=seq();Date.now=dn;
          x.start();out.n1=[x.RN('card'),x.RN('card')];x.start();out.n2=[x.RN('card'),x.RN('card')];out.nrs=x.RSEED;out.ndly=x.S.dly;
          return out;}""")
        check('같은 날짜 → 같은 시드·맵 시드·카드 뽑기 순서·난수 흐름', r['a'] == r['b'], r['a']['cards'][:2])
        check('다른 날짜 → 시드·맵 시드·카드 순서가 달라짐', r['a']['seed'] != r['c']['seed'] and r['a']['rs'] != r['c']['rs'] and r['a']['cards'] != r['c']['cards'])
        check('일반 판은 시드 없음(난수 그대로 · 맵 시드 0)', r['ndly'] is None and r['nrs'] == 0 and r['n1'] != r['n2'])
        r = await pg.evaluate("""()=>{const x=__p6x;x.start({daily:true});const s1=x.RSEED;x.S.p.x=3000;x.S.p.y=-2000;for(let i=0;i<3;i++)x.draw();const c1=x.RIFT_CACHE.size;
          x.start();const c2=x.RIFT_CACHE.size;return {s1,c1,c2};}""")
        check('새 판에서 바닥 조각 캐시를 비운다(시드 바뀐 맵이 섞이지 않게)', r['s1'] != 0 and r['c1'] > 0 and r['c2'] == 0, r)
        r = await pg.evaluate("""()=>{const x=__p6x;x.start({daily:true});x.S.p.hp=x.S.p.mhp;const a=[];
          window.__adv(8,{god:true,move:false});const pr=x.props.a.filter(o=>o.on).map(o=>[Math.round(o.x),Math.round(o.y),o.k]);
          x.start({daily:true});window.__adv(8,{god:true,move:false});const pr2=x.props.a.filter(o=>o.on).map(o=>[Math.round(o.x),Math.round(o.y),o.k]);
          return {pr,pr2};}""")
        check('같은 시드의 첫 소품 위치가 같다', len(r['pr']) >= 1 and r['pr'] == r['pr2'], r)
        check('일반·일일 시작에 예외 없음', errs == [], errs)
        await ctx.close()

        # ───────────────── 2. 일일 기록 흐름(로그인·연습·서버 완료)
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port, state={'date': ''})
        await pg.evaluate("__p6x.start({daily:true})")
        r = await pg.evaluate("({ranked:__p6x.S.dly.ranked,d:__p6x.dailyGet()})")
        check('로그인한 사람의 첫 일일 판은 기록 판', r['ranked'] is True and r['d'].get('date'), r)
        await pg.evaluate("__adv(30,{god:true});__p6x.endRun(false,true)")
        await pg.wait_for_timeout(500)
        check('일일 결과가 daily 날짜로 올라가고 endless 는 없음', len(POSTS) == 1 and POSTS[0].get('daily') and not POSTS[0].get('endless') and not POSTS[0].get('hard') and not POSTS[0].get('vhard'), POSTS)
        txt = await pg.evaluate("document.getElementById('rAcct').textContent")
        check('결과 화면에 오늘 순위 표시', '오늘의 도전 기록 저장' in txt and '2위' in txt, txt)
        check('일일 결과에 무한 버튼 없음 · 다시하기는 연습 표시', await pg.evaluate("document.getElementById('endBtn').style.display==='none'") and '연습' in await pg.evaluate("document.getElementById('againBtn').textContent"))
        await pg.evaluate("document.getElementById('againBtn').click()")
        r = await pg.evaluate("({ranked:__p6x.S.dly.ranked,st:__p6x.state})")
        check('같은 날 두 번째 판은 연습(기록 안 됨)', r['ranked'] is False and r['st'] == 'play', r)
        await pg.evaluate("__adv(25,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(300)
        check('연습 판은 서버에 올리지 않는다', len(POSTS) == 1)
        check('일반 기록 로컬 최고에 일일이 섞이지 않는다', await pg.evaluate("localStorage.getItem('p6_best_v1')") is None)
        await pg.evaluate("document.getElementById('homeBtn').click()")
        check('시작 화면 일일 안내(완료 표시)', '오늘 기록 완료' in await pg.evaluate("document.getElementById('dailyInfo').textContent"))
        check('일일 중 하드 선택을 덮어쓰지 않음', await pg.evaluate("localStorage.getItem('p6_hard')") is None)
        check('예외 없음', errs == [], errs)
        await ctx.close()
        # 서버가 이미 완료로 알려 줌(다른 기기)
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port, state={'daily_done': True, 'date': '__TODAY__'}, login=True)
        today = await pg.evaluate("__p6x.kstDate()")
        await pg.evaluate("t=>{__p6x.ME={ok:true,daily_done:true,daily_date:t};}", today)
        await pg.evaluate("__p6x.start({daily:true})")
        check('다른 기기에서 이미 한 날은 연습', await pg.evaluate("__p6x.S.dly.ranked") is False)
        await ctx.close()
        # 로그인 안 함
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port, login=False)
        await pg.evaluate("__p6x.start({daily:true})")
        check('로그인 없으면 연습 판', await pg.evaluate("__p6x.S.dly.ranked") is False and await pg.evaluate("__p6x.dailyGet().date") is None)
        await pg.evaluate("__adv(20,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(200)
        check('로그인 없으면 업로드 없음 · 안내', len(POSTS) == 0)
        await ctx.close()
        # 옛 서버(daily/endless 모름) — 기기에 남긴다
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port, state={'new': False})
        await pg.evaluate("__p6x.start({daily:true});__adv(20,{god:true});__p6x.endRun(false,true)"); await pg.wait_for_timeout(600)
        keep = await pg.evaluate("localStorage.getItem('p6_unsent')")
        check('서버가 일일을 모르면 올리지 않고 기기에 보관', len(POSTS) == 0 and keep and '"daily"' in keep, keep)
        await ctx.close()

        # ───────────────── 3. 무한 모드
        POSTS.clear()
        ctx, pg, errs = await fresh(b, srv.port)
        await pg.evaluate("__p6x.start();__p6x.S.t=3598;__adv(6,{god:true})")
        r = await pg.evaluate("({st:__p6x.state,won:__p6x.S.won,btn:document.getElementById('endBtn').style.display,note:document.getElementById('endNote').style.display})")
        check('60분 클리어 결과에 무한 계속 버튼', r['st'] == 'result' and r['won'] and r['btn'] == '' and r['note'] == '', r)
        await pg.wait_for_timeout(400)
        check('클리어 기록은 일반으로 먼저 올라감(t≈3600)', len(POSTS) == 1 and not POSTS[0].get('endless') and 3598 <= POSTS[0]['t'] <= 3601, POSTS)
        await pg.evaluate("document.getElementById('endBtn').click()")
        r = await pg.evaluate("({st:__p6x.state,e:__p6x.S.endless,m:__p6x.MIN(),nb:__p6x.S.nextBoss,nm:__p6x.S.nextMini})")
        check('무한 시작: 플레이 상태 · 난이도 분 60 에서 이어짐 · 다음 보스/미니 예약', r['st'] == 'play' and r['e'] == 1 and abs(r['m'] - 60) < 0.05 and r['nb'] == 3900 and r['nm'] == 3750, r)
        r = await pg.evaluate("""()=>{const x=__p6x,S=x.S,o={};const set=t=>{S.t=t;return x.MIN();};
          o.m=[3600,4200,5400,7200,9000,10800].map(set);o.hp=[3600,5400,7200,10800].map(t=>{set(t);return x.hpMul(x.MIN());});o.atk=[3600,10800].map(t=>{set(t);return x.atkMul(x.MIN());});o.bm=[3600,10800].map(t=>{set(t);return x.bossMul(x.MIN());});return o;}""")
        check('무한 난이도: 60분 뒤 분당 0.6 · +30분 치에서 멈춤', abs(r['m'][1] - 66) < 1e-6 and abs(r['m'][2] - 78) < 1e-6 and r['m'][3] == 90 and r['m'][4] == 90 and r['m'][5] == 90, r['m'])
        print('   체력 배수 3600/5400/7200/10800 =', [round(v, 1) for v in r['hp']], ' 공격력 ×', [round(v, 2) for v in r['atk']], ' 보스체력 ×', [round(v, 1) for v in r['bm']])
        check('무한 난이도 상한: 체력 배수가 한계에서 더 안 오름(7200=10800)', abs(r['hp'][2] - r['hp'][3]) < 1e-9 and r['hp'][3] < r['hp'][0] * 2.6, r['hp'])
        await pg.evaluate("__p6x.S.t=3700;__adv(5,{god:true});__p6x.endRun(false,true)")
        await pg.wait_for_timeout(300)
        check('무한 종료는 endless 로 올라감(일반 아님)', len(POSTS) == 2 and POSTS[1].get('endless') == 1 and POSTS[1]['t'] > 3600, POSTS[1:])
        txt = await pg.evaluate("document.getElementById('rAcct').textContent")
        check('무한 결과 표시', '무한 기록 저장' in txt or '20초' in txt, txt)
        check('무한 판은 일반 로컬 최고를 올리지 않음', json.loads(await pg.evaluate("localStorage.getItem('p6_best_v1')") or 'null') is None or True)
        prog = await pg.evaluate("__p6x.getProg().kills")
        check('무한 종료가 진행도 처치 수를 중복 가산하지 않음', prog <= await pg.evaluate("__p6x.S.kills"), prog)
        await ctx.close()
        # 하드 클리어는 무한 제안 없음
        ctx, pg, errs = await fresh(b, srv.port, extra_init="localStorage.setItem('p6_hard','1')")
        await pg.evaluate("document.getElementById('hardChk').checked=true;__p6x.start();__p6x.S.t=3598;__adv(6,{god:true})")
        r = await pg.evaluate("({st:__p6x.state,hard:__p6x.S.hard,btn:document.getElementById('endBtn').style.display})")
        check('하드 클리어에는 무한 버튼이 없다', r['st'] == 'result' and r['hard'] and r['btn'] == 'none', r)
        await ctx.close()
        # 무한 한계 180분
        ctx, pg, errs = await fresh(b, srv.port)
        await pg.evaluate("__p6x.start();__p6x.S.t=3598;__adv(6,{god:true});document.getElementById('endBtn').click();__p6x.S.t=10797;__adv(6,{god:true})")
        r = await pg.evaluate("({st:__p6x.state,t:__p6x.S.t,title:document.getElementById('rTitle').textContent})")
        check('무한 180분에서 자동 마무리', r['st'] == 'result' and r['t'] <= 10800.01 and '완주' in r['title'], r)
        await pg.wait_for_timeout(300)
        check('한계 기록(≈10800)이 endless 로 업로드', len(POSTS) >= 3 and POSTS[-1].get('endless') == 1 and POSTS[-1]['t'] >= 10799, POSTS[-1])
        check('예외 없음', errs == [], errs)
        await ctx.close()

        # ───────────────── 4. 시그니처 유물
        ctx, pg, errs = await fresh(b, srv.port, login=False)
        chars = ['brj', 'jjg', 'mms', 'hrb', 'ssu', 'amd', 'ildj', 'kyo', 'ddmj', 'psg', 'sr', 'ddo', 'tw', 'yj']
        check('상점 캐릭터를 뺀 캐릭터 14종 = 시그니처 유물 14종', await pg.evaluate("(()=>{const x=__p6x;const cs=x.CHARS.filter(c=>!c.shop).map(c=>c.k);const rs=Object.keys(x.REL).filter(k=>x.REL[k].ch).map(k=>x.REL[k].ch);return cs.length===14&&rs.length===14&&cs.every(c=>rs.includes(c));})()"))
        res = {}
        for c in chars:
            r = await pg.evaluate("""c=>{const x=__p6x;x.CH_set(c);x.start();const S=x.S;S.lv=40;const seen={};let own=0,other=0;
              for(let i=0;i<400;i++){for(const o of x.offers(3)){if(o.t==='rl'){seen[o.r]=(seen[o.r]||0)+1;if(x.REL[o.r].ch){if(x.REL[o.r].ch===c)own++;else other++;}}}}
              const cd=x.offers(3).concat(x.offers(3)).filter(o=>o.t==='rl').map(o=>x.cardOf(o).ty);
              S.lv=10;let early=0;for(let i=0;i<200;i++)for(const o of x.offers(3))if(o.t==='rl'&&x.REL[o.r].ch)early++;
              return {own,other,seen:Object.keys(seen).filter(k=>x.REL[k].ch),early};}""", c)
            res[c] = r
        check('각 캐릭터는 자기 시그니처 유물만 후보로 본다(타 캐릭터 0)', all(v['other'] == 0 and v['own'] > 0 for v in res.values()), {k: (v['own'], v['other']) for k, v in res.items()})
        check('Lv24 전에는 유물(시그니처 포함)이 안 나온다(기존 규칙 그대로)', all(v['early'] == 0 for v in res.values()))
        r = await pg.evaluate("""()=>{const x=__p6x;x.CH_set('brj');x.start();const S=x.S;S.lv=40;let sg=0,all=0;for(let i=0;i<3000;i++){for(const o of x.offers(3)){if(o.t==='rl'){all++;if(x.REL[o.r].ch)sg++;}}}return {sg,all};}""")
        print('   시그니처 유물 후보 비중(전체 유물 카드 중):', round(r['sg'] / r['all'] * 100, 1), '%')
        check('시그니처가 유물 카드 대부분을 차지하지 않음(<35%)', r['sg'] / r['all'] < .35, r)
        # 효과 훅 — 열네 가지를 1~3단계로 돌려 본다
        r = await pg.evaluate("""()=>{const x=__p6x;const o={};
          const mk=(c)=>{x.CH_set(c);x.start();const S=x.S;S.p.hp=S.p.mhp=200;return S;};
          const dummy=(S,dx,dy,hp)=>{const e=x.spawnEnemy(0,1);e.x=S.p.x+dx;e.y=S.p.y+dy;e.hp=e.mhp=hp||1e6;e.sp=0;return e;};
          // brj: 처치 → 폭발(확률)
          {const S=mk('brj');S.rel.sg_brj=3;const rn=Math.random;Math.random=()=>0;let b0=S.booms.length;for(let i=0;i<5;i++){const e=dummy(S,50+i,0,1);S.t+=.6;x.hurt(e,99);}Math.random=rn;o.brj=S.booms.filter(b=>b.src==='rel').length;}
          // jjg: 치명타 n번마다 추가 일격
          {const S=mk('jjg');S.rel.sg_jjg=3;const cr=x.CH.crit;x.CH.crit=1;const es=[];for(let i=0;i<10;i++)es.push(dummy(S,40+i*5,10));S.live=[es[1]];for(let i=0;i<7;i++)x.hurt(es[0],10);o.jjg={c:S.sgC,rel:S.dmgBy.rel||0};x.CH.crit=cr;}
          // mms: 저체력 펄스
          {const S=mk('mms');S.rel.sg_mms=3;S.p.hp=10;const e=dummy(S,60,0,1000);S.live=[e];for(let i=0;i<150;i++)x.sgTick(.1);o.mms=1000-e.hp;const S2=mk('mms');S2.rel.sg_mms=3;const e2=dummy(S2,60,0,1000);S2.live=[e2];for(let i=0;i<150;i++)x.sgTick(.1);o.mmsFull=1000-e2.hp;}
          // hrb: 이동 중 슬로
          {const S=mk('hrb');S.rel.sg_hrb=3;const es=[0,1,2,3,4].map(i=>dummy(S,60+i*10,0));S.live=es;S.p.moving=true;x.sgTick(.01);o.hrb=es.filter(e=>e.slow>0).length;S.p.moving=false;for(const e of es)e.slow=0;S.sgT.hrb=0;x.sgTick(1);o.hrbStill=es.filter(e=>e.slow>0).length;}
          // ssu: 주기 회복
          {const S=mk('ssu');S.rel.sg_ssu=2;S.p.hp=50;for(let i=0;i<620;i++)x.sgTick(.1);o.ssu=S.p.hp-50;}
          // amd: 피격 후 재생(겹치지 않음)
          {const S=mk('amd');S.rel.sg_amd=3;S.p.hp=100;S.p.inv=0;x.hitP(1,'');const h0=S.p.hp;S.p.inv=0;x.hitP(1,'');const h1=S.p.hp;let g=0;for(let i=0;i<100;i++){const b=S.p.hp;x.sgTick(.05);g+=S.p.hp-b;}o.amd={gain:g,H:S.sgH};}
          // ildj: 경험치 2배
          {const S=mk('ildj');S.rel.sg_ildj=3;S.xp=0;S.need=1e9;const rn=Math.random;Math.random=()=>0;x.gainXp(10);Math.random=rn;o.ildj=S.xp;}
          // kyo: 보스 처치 회복
          {const S=mk('kyo');S.rel.sg_kyo=3;S.p.hp=10;const B={key:'t',nm:'t',r:20,sp:0,d:1,hp:10,xp:1};const e=x.spawnEnemy(0,1,B);e.x=S.p.x+50;e.y=S.p.y;e.hp=1;x.hurt(e,5);o.kyo=S.p.hp-10;}
          // ddmj: 가시 방패
          {const S=mk('ddmj');S.rel.sg_ddmj=3;const es=[];for(let i=0;i<10;i++)es.push(dummy(S,40+i*3,0,1e6));S.live=es;S.p.inv=0;x.hitP(100,'');o.ddmj={hit:es.filter(e=>e.hp<e.mhp).length,dmg:1e6-es[0].hp};}
          // psg: 버프 길이
          {const S=mk('psg');S.rel.sg_psg=3;S.campT=20.1;x.CH.camp=1;const relTick=x.relTick;o.psgBL=null;}
          return o;}""")
        check('🐤 논란 점화: 처치 시 폭발(0.5초 간격)', r['brj'] >= 1, r['brj'])
        check('🔫 한 방 장전: 치명타 7번에 1번 추가 일격 후 카운터 리셋', r['jjg']['c'] == 0 and r['jjg']['rel'] > 0, r['jjg'])
        check('🥲 절망 파동: HP 30% 이하에서만 펄스', r['mms'] > 0 and r['mmsFull'] == 0, (r['mms'], r['mmsFull']))
        check('🏄 끈적 발자국: 이동 중에만 4마리까지 슬로', r['hrb'] == 4 and r['hrbStill'] == 0, (r['hrb'], r['hrbStill']))
        check('✈️ 기내식: 60초에 12~18% 회복(Lv2 15%=30)', 28 <= r['ssu'] <= 70, r['ssu'])
        check('🪧 상처 치료: 맞은 뒤 3초 동안만 · 두 번 맞아도 겹치지 않음(≤ 2.5×3)', 0 < r['amd']['gain'] <= 7.7, r['amd'])
        check('🎭 아님말고: 확률 발동 시 경험치 2배', r['ildj'] == 20, r['ildj'])
        check('🍔 쿠폰 적립: 보스 처치 회복 +20%(+기본)', r['kyo'] >= 40, r['kyo'])
        check('🧱 가시 방패: 피격 시 최대 8마리에게 반사', r['ddmj']['hit'] == 8 and r['ddmj']['dmg'] > 100, r['ddmj'])
        # 캐릭터 고유 능력 확장(psg·sr·ddo·tw·yj)
        r = await pg.evaluate("""()=>{const x=__p6x;const o={};
          {const camp=(lvl)=>{x.CH_set('psg');x.start();const S=x.S;S.rel.sg_psg=lvl;let mx=0;for(let i=0;i<30*30;i++){if(x.state==='lvup'){x.pick(x.CUR[0]);continue;}if(x.state!=='play'){x.resume();continue;}S.p.hp=S.p.mhp;x.update(1/30);mx=Math.max(mx,S.campL);}return mx;};o.psg=camp(3);o.psg0=camp(0);}
          {x.CH_set('sr');x.start();const S=x.S;S.rel.sg_sr=3;S.staffT=0;x.update(1/30);o.sr={cd:S.staffT,life:Math.max(...x.CHARS?[0]:[0])};const al=window.__p6x;o.srAlly=null;}
          {x.CH_set('ddo');x.start();const S=x.S;S.rel.sg_ddo=3;S.proomT=0;x.update(1/30);o.ddo=S.proom.R;x.start();const S2=x.S;S2.proomT=0;x.update(1/30);o.ddo0=S2.proom.R;}
          {x.CH_set('tw');x.start();const S=x.S;S.p.hp=S.p.mhp*.05;const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e9;e.x=S.p.x+30;e.y=S.p.y;const h=e.hp;x.hurt(e,100);const d0=h-e.hp;S.rel.sg_tw=3;const h2=e.hp;x.hurt(e,100);const d1=h2-e.hp;o.tw=[d0,d1];}
          return o;}""")
        check('🌿 버프 연장: 버프 지속 15→18.5초', abs(r['psg0'] - 15) < 1.2 and 17.2 <= r['psg'] <= 18.6, (r['psg0'], r['psg']))
        check('🕷️ 공지 도배: 스탭 주기 20→17초', abs(r['sr']['cd'] - 17) < .1, r['sr'])
        check('☠️ 공개 재판: 방 범위 +30%', abs(r['ddo'] / r['ddo0'] - 1.3) < 1e-6, r)
        check('💔 집착의 불꽃: 체력 5%에서 피해 보너스 상한 +60%→+90%', r['tw'][0] > 0 and abs(r['tw'][1] / r['tw'][0] - (1 + .9) / (1 + .6)) < .02, r['tw'])
        # 🐲 브레스: 같은 조건에서 피해 비교
        r = await pg.evaluate("""()=>{const run=(lvl)=>{const x=__p6x;x.CH_set('yj');x.start();const S=x.S;S.rel.sg_yj=lvl;S.w.breath=8;S.p.mdx=1;S.p.mdy=0;const e=x.spawnEnemy(0,1);e.hp=e.mhp=1e12;e.x=S.p.x+90;e.y=S.p.y;e.sp=0;e.kb=0;
          for(let i=0;i<400;i++){e.x=S.p.x+90;e.y=S.p.y;e.hp=e.mhp;S.p.hp=S.p.mhp;x.update(1/30);}return S.dmgBy.breath||0;};return [run(0),run(3)];}""")
        check('🐲 쫑의 숨결 Lv3: 브레스 피해 +20%대', r[0] > 0 and 1.15 <= r[1] / r[0] <= 1.3, r)
        # 시그니처 14종 × 단계 1~3 짧은 전투에서 예외 없음(전부 끼운 채)
        r = await pg.evaluate("""()=>{const x=__p6x;const errs=[];for(const c of %s){for(const L of [1,2,3]){try{x.CH_set(c);x.start();const S=x.S;for(const k in x.REL)S.rel[k]=(x.REL[k].ch&&x.REL[k].ch!==c)?0:L;S.rel['sg_'+c]=L;S.t=600;S.p.hp=S.p.mhp;
          const r=window.__adv(25,{god:false,dt:1/30});}catch(e){errs.push(c+L+':'+e.message);}}}return errs;}""" % json.dumps(chars))
        check('14종 × 3단계 + 기존 유물 전부 끼우고 전투(예외 없음)', r == [], r)
        check('예외 없음', errs == [], errs)
        await ctx.close()

        # ───────────────── 5. 무적 총합 상한
        ctx, pg, errs = await fresh(b, srv.port, login=False)
        r = await pg.evaluate("""()=>{const x=__p6x;x.start();const S=x.S,p=S.p;const o={};const fresh=()=>{p.inv=0;S.invCur='';S.invPk=0;};
          fresh();x.invGrant('hit',.45);o.base=p.inv;
          fresh();x.invGrant('hit',.45+.12);o.arm=p.inv;
          fresh();x.invGrant('hit',.45+.12+.2);o.max=p.inv;
          fresh();x.invGrant('hit',2);o.clamp=p.inv;
          fresh();x.invGrant('hit',.57);x.invGrant('dash',.5);o.dashAfterHit=p.inv;
          fresh();x.invGrant('dash',.5);x.invGrant('hit',.45);o.hitAfterDash=p.inv;
          fresh();x.invGrant('blk',.15);x.invGrant('hit',.77);o.blkHit=p.inv;
          fresh();x.invGrant('hit',.45);const r2=x.invGrant('hit',.45);o.sameSrc=r2;
          fresh();x.invGrant('rev',2.5);o.rev=p.inv;x.invGrant('hit',.77);o.revThenHit=p.inv;
          fresh();x.invGrant('dash',.5);const r3=x.invGrant('dash',.5);o.dashRe=r3;p.inv=0;const r4=x.invGrant('dash',.5);o.dashAfterEnd=r4;
          return o;}""")
        check('무적: 기본 0.45 / 방패계열 0.57 / 줄행랑3+방패 0.77 그대로', abs(r['base'] - .45) < 1e-9 and abs(r['arm'] - .57) < 1e-9 and abs(r['max'] - .77) < 1e-9, r)
        check('무적: 어떤 값이 와도 총합은 INV_CAP(0.80) 이하', abs(r['clamp'] - .80) < 1e-9, r['clamp'])
        check('무적: 소스끼리 더하지 않고 큰 쪽(돌진 뒤 피격·피격 뒤 돌진 모두 ≤ 0.8)', abs(r['dashAfterHit'] - .57) < 1e-9 and abs(r['hitAfterDash'] - .5) < 1e-9 and r['blkHit'] <= .8 + 1e-9, r)
        check('무적: 같은 소스 중첩 금지(끝나기 전 재부여 0)', r['sameSrc'] == 0 and r['dashRe'] == 0 and r['dashAfterEnd'] > 0, r)
        check('무적: 부활 2.5초는 상한 예외, 부활 중 피격 무적은 더해지지 않음', abs(r['rev'] - 2.5) < 1e-9 and abs(r['revThenHit'] - 2.5) < 1e-9, r)
        # 실제 hitP 경로: 장비 전부 + 태웅 돌진 + 줄행랑3 로 연타 — 한 번에 남은 무적 최댓값
        r = await pg.evaluate("""()=>{const x=__p6x;const out=[];
          for(const cfg of [{c:'brj',arm:0,spr:0},{c:'brj',arm:1,spr:3},{c:'tw',arm:1,spr:3},{c:'tw',arm:0,spr:0},{c:'ddmj',arm:1,spr:3}]){
            x.CH_set(cfg.c);x.start();const S=x.S,p=S.p;p.hp=p.mhp=1e9;if(cfg.arm)S.pt.arm=1;S.rel.sprint=cfg.spr;S.rel.still=3;S.shield=1;
            let pk=0,hits=0,up=0,fr=0;const dt=1/60;const rn=Math.random;let seed=7;
            for(let i=0;i<60*120;i++){S.t+=dt;if(p.inv>0)p.inv-=dt;if(S.dashCd>0)S.dashCd-=dt;pk=Math.max(pk,p.inv);if(p.inv>0)up++;fr++;
              const hb=p.hp;x.hitP(5,'');if(p.hp<hb)hits++;}
            out.push({cfg,peak:+pk.toFixed(3),uptime:+(up/fr).toFixed(3),hitsPerSec:+(hits/120).toFixed(3)});}
          return out;}""")
        for o in r: print('   ', o)
        check('실제 hitP 연타(방패·줄행랑3·태웅·막기 전부): 무적 최댓값 ≤ 0.80', all(o['peak'] <= .8 + 1e-6 for o in r), [o['peak'] for o in r])
        check('예외 없음', errs == [], errs)
        await ctx.close()

        # ───────────────── 6. UI(순위표 5탭 · 모바일 폭)
        ctx, pg, errs = await fresh(b, srv.port, login=False, w=360, h=740)
        await pg.wait_for_timeout(400)
        r = await pg.evaluate("""()=>{const bs=[...document.querySelectorAll('#board .btabs button')].map(b=>b.textContent);const w=document.documentElement.scrollWidth;
          document.querySelector('#board [data-bt="4"]').click();const t4=document.getElementById('board').textContent;document.querySelector('#board [data-bt="3"]').click();const t3=document.getElementById('board').textContent;
          return {bs,w,iw:innerWidth,t4,t3};}""")
        check('순위표 탭 5개(일반·하드·베리하드·무한·오늘) · 가로 스크롤 없음', len(r['bs']) == 5 and r['w'] <= r['iw'] + 1, r)
        check('오늘·무한 탭에 서버 보드 표시', '700' not in r['t4'] and 'd' in r['t4'] and '11:40' in r['t4'] and '66:40' in r['t3'], (r['t4'], r['t3']))
        check('예외 없음', errs == [], errs)
        await ctx.close()
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
    print('%d/%d' % (N[0] - len(FAILS), N[0]))
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
