# -*- coding: utf-8 -*-
"""💘 이상형월드컵 탭 시험 (2026-10-18 사장님 「동일한 내부티어, 동일한 포지션인 유저를 양옆에 띄워서 …」)
합성 시트(가짜 닉네임·PUUID) + 봇 API 모의(Playwright route). 실제 닉네임·키는 쓰지 않는다.

  ① 탭 존재 · 폰 360 가로 넘침 0           ② 풀 목록(4명 미만 비활성 · 인원/참여자 수)
  ③ 후보 = 같은 티어·같은 포지션만 · 자기 자신/탈퇴자/유령/10판 미만/같은 사람 두 닉 제외 · 선언 포지션 우선
  ④ 8강→4강→결승, 라운드마다 /ideal/vote 가 올바른 a·b·w 로 · 양옆 카드(폭 50%)
  ⑤ 로그아웃이면 투표를 안 보내고 안내 · 로그인 버튼
  ⑥ 결과 화면 정렬(승률순) · 표본 부족 분리 · 내 우승자 강조 · 풀 밖 이름 무시
  ⑦ 401 이면 로그아웃 처리 · 429(재시도) / 503 / 네트워크 실패에도 진행 · 403 안내
  ⑧ 변이: 규칙 하나를 일부러 깨뜨린 사본에서는 시험이 실패해야 한다 (--no-mutants 로 생략)
  ⑨ 콘솔 오류 0

  python3 tests/web_ideal_test.py [--src index.html] [--no-mutants]
"""
import argparse, asyncio, datetime as dt, json, os, random, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

NOW = '2026-10-18T15:00:00'
API = 'https://hth3thmujs.apps.bot-hosting.cloud'
COLS = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
CHAMPS = ['가렌', '아리', '이즈리얼', '쓰레쉬', '리신', '제드', '카이사', '룰루']
LAST = dt.date(2026, 10, 17)

# ---- 합성 인원: (닉, 티어, 주 포지션, 비고) ----
MID = ['미드%02d#T' % i for i in range(1, 10)]           # 1中·미드 후보 9명
SUP = ['서폿%02d#T' % i for i in range(1, 5)]            # 1中·서폿 4명
TOP = ['탑%02d#T' % i for i in range(1, 6)]              # 2上·탑 5명 (+선언탑 1명 = 6)
JUG = ['정글%02d#T' % i for i in range(1, 4)]            # 3下·정글 3명 → 비활성
ACTIVE = [(n, '1中', '미드') for n in MID] + [(n, '1中', '서폿') for n in SUP] + [(n, '2上', '탑') for n in TOP] + [(n, '3下', '정글') for n in JUG] + [
    ('선언탑#T', '2上', '미드'),        # 실제로는 미드를 뛰지만 선언 주포지션이 탑 → 2上·탑 풀
    ('탈퇴미드#T', '1中', '미드'),      # DEPARTED
    ('미드01부#T', '1中', '미드'),      # 미드01 의 부계(LINK_ACCOUNT) → 같은 사람, 후보는 한 명
]
GHOST = ('유령미드#T', '1中', '미드')                      # 마지막 기록이 100일 전
NEWB = ('신입미드#T', '1中', '미드')                       # 4판
SELF = '미드02'


def build_xlsx(path):
    from openpyxl import Workbook
    rnd = random.Random(5)
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'; ws.append(COLS)
    pos_of = {n: p for n, _, p in ACTIVE + [GHOST, NEWB]}
    pu_of = {n: 'pu-' + re.sub(r'\W', '', n) + str(i) for i, (n, _, _) in enumerate(ACTIVE + [GHOST, NEWB])}
    pu_of['미드01부#T'] = 'pu-sub01'
    gid = [9000]

    def game(day, names):
        gid[0] += 1
        blue_wins = rnd.random() < .5
        for k, n in enumerate(names):
            win = (k < 5) == blue_wins
            ws.append(['#%d' % gid[0], (LAST - dt.timedelta(days=day)).isoformat() + ' 21:00', n, pu_of[n], '블루팀' if k < 5 else '레드팀', pos_of[n],
                       rnd.choice(CHAMPS), None, '승리' if win else '패배', None, 'v16.20',
                       '%d/%d/%d' % (rnd.randint(0, 9), rnd.randint(0, 7), rnd.randint(0, 12)), 20.0, 20000.0, None, None, None, None, None])
    act = [n for n, _, _ in ACTIVE]
    for g in range(12):                                   # 100일 전 — 유령은 여기서만
        game(110, [GHOST[0]] + [act[(g + j) % len(act)] for j in range(9)])
    for g in range(90):                                   # 최근 — 유령 제외 · 신입은 앞 4판만
        base = [act[(g * 7 + j) % len(act)] for j in range(10)]
        if g < 4: base[0] = NEWB[0]
        game(g % 20, base)
    tiers = [[n.split('#')[0], t] for n, t, _ in ACTIVE + [GHOST, NEWB]]
    for name, rows in (('CLAN_TIERS', [['닉네임', '티어']] + tiers),
                       ('LINK_ACCOUNT', [['본계정', '부계정 롤닉 (#태그 있어도 됨)', '메모 (선택)'], ['미드01#T', '미드01부#T', '']]),
                       ('DEPARTED', [['닉네임', '갱신시각'], ['탈퇴미드', '2026-10-17 09:00']]),
                       ('CLAN_POSITIONS', [['닉네임', '주포지션', '부포지션'], ['선언탑', '탑', '']])):
        w = wb.create_sheet(name)
        for r in rows: w.append(r)
    wb.save(path)


fails = []
def ok(c, msg):
    print(('  ok   ' if c else '  FAIL ') + msg)
    if not c: fails.append(msg)


# ---- 봇 모의 ----
class Bot:
    def __init__(self):
        self.on = True; self.posts = []; self.gets = []
        self.vote_codes = []        # 다음 POST 들이 줄 상태(없으면 200). 'NET' = 연결 끊김
        self.cand = {}; self.voters = {}; self.stats_code = 200
    async def handler(self, route):
        req = route.request; u = req.url
        hdr = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
        if req.method == 'OPTIONS': await route.fulfill(status=204, headers=hdr); return
        js = lambda o, st=200: route.fulfill(status=st, headers=hdr, content_type='application/json', body=json.dumps(o, ensure_ascii=False))
        if '/ideal/vote' in u:
            b = json.loads(req.post_data or '{}'); self.posts.append(b)
            c = self.vote_codes.pop(0) if self.vote_codes else 200
            if c == 'NET': await route.abort(); return
            if c == 200: await js({'ok': True, 'mine': len(self.posts)})
            elif c == 429: await js({'ok': False, 'error': 'rate'}, 429)
            elif c == '429full': await js({'ok': False, 'error': 'full'}, 429)
            else: await js({'ok': False, 'error': 'x'}, c)
        elif '/ideal/stats' in u:
            q = dict(x.split('=', 1) for x in u.split('?', 1)[1].split('&')) if '?' in u else {}
            self.gets.append(q)
            if self.stats_code != 200: await js({'ok': False}, self.stats_code); return
            if 'pool' in q:
                from urllib.parse import unquote
                pool = unquote(q['pool'])
                await js({'ok': True, 'pool': pool, 'voters': self.voters.get(pool, 0), 'cand': self.cand.get(pool, {}), 'mine': {}})
            else:
                await js({'ok': True, 'on': self.on, 'pools': {p: {'cand': len(c), 'votes': sum(v[1] for v in c.values()) // 2, 'voters': self.voters.get(p, 0)} for p, c in self.cand.items()}})
        else: await route.fulfill(status=404, headers=hdr, body='{}')


LOGIN = "(n)=>{DISCORD_USER={id:'1',name:n,avatar:'',token:'x'.repeat(30),exp:Date.now()+86400000}; localStorage.setItem('sgg_dc',JSON.stringify(DISCORD_USER));}"
LOGOUT = "()=>{DISCORD_USER=null; localStorage.removeItem('sgg_dc');}"
OVERFLOW = "()=>({sw:document.documentElement.scrollWidth, iw:window.innerWidth, bw:document.body.scrollWidth})"


async def open_ideal(pg):
    await pg.evaluate("()=>{IDEAL.stat={state:'idle',pools:{},at:0}; IDEAL.res={}; IDEAL.mine={};}")
    await pg.evaluate("()=>go('ideal')")
    await pg.wait_for_timeout(400)


async def pools_dom(pg):
    return await pg.evaluate("()=>[...document.querySelectorAll('.iw-pool')].map(e=>({n:e.querySelector('b').textContent,off:e.classList.contains('off'),t:e.textContent}))")


async def play(pg, bot, mode='alt'):
    """현재 월드컵을 끝까지 — 매 대진 직전에 (a,b,승자)를 기록해 두고 반환."""
    exp = []
    for _ in range(12):
        st = await pg.evaluate("()=>{const R=IDEAL.run; if(!R||R.done) return null; return {a:R.cur[R.mi*2].vname,b:R.cur[R.mi*2+1].vname,round:R.round,mi:R.mi,n:R.cur.length/2}}")
        if not st: break
        side = (len(exp) % 2) if mode == 'alt' else 0
        exp.append((st['a'], st['b'], st['a'] if side == 0 else st['b'], st['round']))
        await pg.click('.iw-duel .iw-card' + ('.l' if side == 0 else '.r'))
        await pg.wait_for_timeout(60)
    return exp


async def scenarios(pg, bot, label=''):
    S = {}
    await pg.route(API + '/**', bot.handler)
    # 대표 후보 풀 결과(서버 쪽 집계) — 정렬·표본 부족 시험용
    names = [n for n in MID if n != SELF + '#T']
    bot.cand = {'1中·미드': {}, '1中·서폿': {}}
    wr = [(5, 5), (4, 5), (3, 5), (2, 4), (1, 4), (9, 10), (0, 3), (1, 2), (2, 2)]
    for n, v in zip(MID, wr): bot.cand['1中·미드'][n] = list(v)
    bot.cand['1中·미드']['탈퇴미드#T'] = [50, 50]            # 풀 밖(탈퇴자) 이름 — 결과에 나오면 안 된다
    bot.voters = {'1中·미드': 7, '1中·서폿': 2}
    # ---------------- ① 탭 · 폰 가로 넘침
    await pg.evaluate(LOGOUT)
    S['tab'] = await pg.evaluate("()=>[...document.querySelectorAll('.tabs .tab')].some(t=>t.textContent.includes('이상형월드컵'))")
    await open_ideal(pg)
    S['hash'] = await pg.evaluate("location.hash")
    ov = await pg.evaluate(OVERFLOW)
    S['ov_list'] = ov
    # ---------------- ② ③ 풀 목록 (로그아웃)
    S['pools_out'] = await pools_dom(pg)
    S['cands_out'] = await pg.evaluate("()=>{const o={}; for(const [k,p] of idealPools()) o[k]=p.cands.map(c=>c.name); return o}")
    S['gets_out'] = len(bot.gets)
    # ---------------- ④ ⑤ 로그아웃 상태로 서폿 풀(4명 → 4강)
    await pg.evaluate("()=>idealStart('1中·서폿')")
    await pg.wait_for_timeout(100)
    box = await pg.evaluate("()=>[...document.querySelectorAll('.iw-duel .iw-card')].map(e=>{const r=e.getBoundingClientRect(); return {x:r.x,w:r.width,y:r.y}})")
    S['duel_out'] = box; S['duel_ov'] = await pg.evaluate(OVERFLOW)
    S['round_label_out'] = await pg.evaluate("()=>document.querySelector('.iw-round').textContent")
    exp_out = await play(pg, bot)
    await pg.wait_for_timeout(500)
    S['out_exp'] = exp_out; S['out_posts'] = len(bot.posts)
    S['out_note'] = await pg.evaluate("()=>document.getElementById('iw-note').textContent")
    S['out_dc_btn'] = await pg.evaluate("()=>!!document.querySelector('#iw-note .iw-dc')")
    S['out_win'] = await pg.evaluate("()=>!!document.querySelector('.iw-win')")
    # ---------------- 로그인 후 목록(자기 자신 제외 · 참여자 수)
    await pg.evaluate(LOGIN, SELF)
    await open_ideal(pg)
    await pg.wait_for_timeout(400)
    S['pools_in'] = await pools_dom(pg)
    S['cands_in'] = await pg.evaluate("()=>{const o={}; for(const [k,p] of idealPools()) o[k]=p.cands.map(c=>c.name); return o}")
    S['gets_in'] = len(bot.gets)
    # ---------------- ④ 미드 풀 8강 → 결승, 라운드마다 투표
    bot.posts.clear()
    await pg.evaluate("()=>idealStart('1中·미드')")
    S['run_cur'] = await pg.evaluate("()=>IDEAL.run.cur.map(c=>c.name)")
    S['rounds_seen'] = []
    exp = await play(pg, bot)
    await pg.wait_for_timeout(2600)
    S['in_exp'] = exp; S['in_posts'] = list(bot.posts)
    S['winner'] = await pg.evaluate("()=>IDEAL.run&&IDEAL.run.winner&&IDEAL.run.winner.vname")
    S['in_win'] = await pg.evaluate("()=>!!document.querySelector('.iw-win')")
    S['in_note'] = await pg.evaluate("()=>document.getElementById('iw-note').textContent")
    S['ov_win'] = await pg.evaluate(OVERFLOW)
    # ---------------- ⑥ 결과 화면
    await pg.click('.iw-act .iw-go')
    await pg.wait_for_selector('.iw-row', timeout=5000)
    S['rows'] = await pg.evaluate("()=>[...document.querySelectorAll('.iw-row')].map(e=>({n:e.querySelector('.iw-rn').textContent.replace('내 우승자','').trim(),v:e.querySelector('.iw-rv').textContent.trim(),me:e.classList.contains('me'),bar:e.querySelector('.iw-bar span').style.width}))")
    S['few'] = await pg.evaluate("()=>[...document.querySelectorAll('.iw-chip')].map(e=>e.textContent.trim())")
    S['voters_txt'] = await pg.evaluate("()=>document.querySelector('.iw-voters').textContent")
    S['res_text'] = await pg.evaluate("()=>document.querySelector('.iw').textContent")
    S['ov_res'] = await pg.evaluate(OVERFLOW)
    # ---------------- ⑥ 풀 카드의 「결과 보기」
    await open_ideal(pg)
    await pg.wait_for_timeout(300)
    await pg.evaluate("()=>idealShowResult('1中·서폿')")
    await pg.wait_for_timeout(500)
    S['res2_rows'] = await pg.evaluate("()=>document.querySelectorAll('.iw-row').length")
    S['res2_empty'] = await pg.evaluate("()=>document.querySelector('.iw-rest')?document.querySelector('.iw-rest').textContent:''")
    # ---------------- ⑦ 429(재시도) · 503 · 네트워크 실패 · 403 · 401
    async def run_with(codes, pool='1中·서폿'):
        await open_ideal(pg); await pg.evaluate(LOGIN, SELF)
        bot.posts.clear(); bot.vote_codes[:] = codes
        await pg.evaluate("(p)=>idealStart(p)", pool)
        e = await play(pg, bot)
        await pg.wait_for_timeout(3200)
        return e, await pg.evaluate("()=>({win:!!document.querySelector('.iw-win'),note:document.getElementById('iw-note').textContent,failed:IDEAL.failed,sent:IDEAL.sent,stop:IDEAL.stop,user:DISCORD_USER?DISCORD_USER.name:null,ls:localStorage.getItem('sgg_dc')})")
    S['r429'] = await run_with([429])
    S['r503'] = await run_with([503, 503, 503])
    S['rnet'] = await run_with(['NET', 'NET', 'NET'])
    S['r403'] = await run_with([403])
    S['r401'] = await run_with([401])
    S['r401_posts'] = len(bot.posts)
    # ---------------- 쉬는 중 (on:false) · 서버 다운
    await pg.evaluate(LOGIN, SELF); bot.on = False
    await open_ideal(pg); await pg.wait_for_timeout(400)
    S['off'] = await pg.evaluate("()=>document.querySelector('.iw').textContent")
    S['off_start'] = await pg.evaluate("()=>document.querySelectorAll('.iw-go').length")
    bot.on = True; bot.stats_code = 503
    await open_ideal(pg); await pg.wait_for_timeout(400)
    S['down'] = await pg.evaluate("()=>document.querySelector('.iw').textContent")
    bot.stats_code = 401
    await open_ideal(pg); await pg.wait_for_timeout(400)
    S['stat401_user'] = await pg.evaluate("()=>DISCORD_USER")
    bot.stats_code = 200
    return S


def check(S, strict_extra=True):
    names_mid = [n for n in MID]
    # ① ② ③ ---- 로그아웃 상태
    ok(S['tab'], '① 상단 탭에 「💘 이상형월드컵」이 있다')
    ok(S['hash'] == '#ideal', '① 주소가 #ideal  (%s)' % S['hash'])
    ok(S['ov_list']['sw'] <= S['ov_list']['iw'] and S['ov_list']['bw'] <= S['ov_list']['iw'], '① 폰 360 목록 가로 넘침 0 %s' % S['ov_list'])
    p = {x['n']: x for x in S['pools_out']}
    ok(set(p) == {'1中·미드', '1中·서폿', '2上·탑', '3下·정글'}, '② 풀은 (티어·포지션)별: %s' % sorted(p))
    ok(p.get('3下·정글', {}).get('off') and '후보가 모자라요' in p['3下·정글']['t'], '② 후보 3명 풀은 「후보가 모자라요」로 비활성')
    ok(not p.get('1中·서폿', {}).get('off') and not p.get('2上·탑', {}).get('off'), '② 4명·6명 풀은 활성')
    ok('후보 9명' in p.get('1中·미드', {}).get('t', ''), '② 인원 수 표시(미드 9명)  (%s)' % p.get('1中·미드', {}).get('t', '')[:40])
    ok('로그인하면 참여자 수' in p.get('1中·미드', {}).get('t', ''), '② 로그아웃이면 참여자 수 자리에 로그인 안내')
    c = S['cands_out']
    ok(sorted(c.get('1中·미드', [])) == sorted(MID), '③ 미드 풀 = 미드01~09 (탈퇴자·유령·신입·부계 중복·선언탑 제외)  %s' % sorted(c.get('1中·미드', [])))
    ok(sorted(c.get('2上·탑', [])) == sorted(TOP + ['선언탑#T']), '③ 탑 풀 = 탑01~05 + 선언 주포지션 탑  %s' % sorted(c.get('2上·탑', [])))
    ok(sorted(c.get('1中·서폿', [])) == sorted(SUP), '③ 같은 티어라도 포지션이 다르면 다른 풀(서폿 4명)')
    ok(all(len(v) == len(set(v)) for v in c.values()), '③ 한 풀에 같은 후보가 두 번 나오지 않는다')
    ok(S['gets_out'] == 0, '⑤ 로그아웃이면 봇에 아무것도 묻지 않는다 (stats 요청 %d)' % S['gets_out'])
    # ④ ⑤ 로그아웃 월드컵
    b = S['duel_out']
    ok(len(b) == 2 and abs(b[0]['w'] - b[1]['w']) < 3 and b[1]['x'] > b[0]['x'] and abs(b[0]['y'] - b[1]['y']) < 3, '④ 양옆 카드 두 장 · 같은 높이 %s' % b)
    ok(len(b) == 2 and 0.38 <= b[0]['w'] / 360 <= 0.5 and 0.38 <= b[1]['w'] / 360 <= 0.5, '④ 폰에서도 좌우 각 약 50%% 폭 (%.0f / %.0f px)' % (b[0]['w'], b[1]['w']) if len(b) == 2 else '④ 카드 폭')
    ok(S['duel_ov']['sw'] <= S['duel_ov']['iw'], '④ 대진 화면 가로 넘침 0')
    ok(S['round_label_out'].startswith('4강'), '④ 후보 4명 풀은 4강부터  (%s)' % S['round_label_out'])
    ok([e[3] for e in S['out_exp']] == [4, 4, 2], '④ 4강 2경기 → 결승  %s' % [e[3] for e in S['out_exp']])
    ok(S['out_posts'] == 0, '⑤ 로그아웃이면 투표를 보내지 않는다 (%d)' % S['out_posts'])
    ok('로그인하면 투표가 모여요' in S['out_note'] and S['out_dc_btn'], '⑤ 로그인 안내 + 로그인 버튼')
    ok(S['out_win'], '⑤ 그래도 월드컵은 끝까지 간다(우승 화면)')
    # 로그인 후
    p = {x['n']: x for x in S['pools_in']}
    ok('후보 8명' in p.get('1中·미드', {}).get('t', ''), '③ 로그인하면 내 자신(미드02)이 후보에서 빠진다  (%s)' % p.get('1中·미드', {}).get('t', '')[:30])
    ok('미드02#T' not in S['cands_in'].get('1中·미드', []), '③ 후보 목록에 미드02 없음')
    ok('참여 7명' in p.get('1中·미드', {}).get('t', ''), '② 참여자 수 표시(7명)  (%s)' % p.get('1中·미드', {}).get('t', ''))
    ok(S['gets_in'] >= 1, '⑤ 로그인하면 stats 를 묻는다')
    # ④ 8강
    run = S['run_cur']
    ok(len(run) == 8 and len(set(run)) == 8 and set(run) <= set(S['cands_in']['1中·미드']), '④ 후보 8명을 풀에서 뽑는다(중복 없음)')
    ex = S['in_exp']
    ok([e[3] for e in ex] == [8, 8, 8, 8, 4, 4, 2], '④ 8강 4경기 → 4강 2경기 → 결승 1경기  %s' % [e[3] for e in ex])
    po = S['in_posts']
    ok(len(po) == 7, '④ 라운드마다 한 번씩 7번 투표 (%d)' % len(po))
    ok([(x['a'], x['b'], x['w']) for x in po] == [(e[0], e[1], e[2]) for e in ex], '④ 투표 a·b·w 가 눈앞 대진과 정확히 같다')
    ok(all(x['pool'] == '1中·미드' and len(x['token']) > 10 and x['w'] in (x['a'], x['b']) for x in po), '④ pool·token 포함 · 승자는 a 또는 b')
    ok(not any('|' in x['a'] + x['b'] + x['pool'] for x in po), '④ a·b·pool 에 | 없음')
    ok(S['in_win'] and S['winner'] == ex[-1][2], '④ 우승자 = 결승에서 고른 쪽')
    ok(S['ov_win']['sw'] <= S['ov_win']['iw'], '④ 우승 화면 가로 넘침 0')
    ok(S['in_note'].strip() == '', '④ 정상이면 실패 안내가 없다  (%r)' % S['in_note'][:40])
    # ⑥ 결과
    rows = S['rows']
    exp_order = sorted([(n, v) for n, v in zip(MID, [(5, 5), (4, 5), (3, 5), (2, 4), (1, 4), (9, 10), (0, 3), (1, 2), (2, 2)]) if v[1] >= 3 and n != SELF + '#T'], key=lambda x: (-x[1][0] / x[1][1], -x[1][1]))
    shown = [r['n'] for r in rows]
    topn = min(10, max(3, -(-len(exp_order) // 2)))
    want = [n.split('#')[0] for n, _ in exp_order][:topn]
    mine_n = S['winner'].split('#')[0] if S['winner'] else None
    if mine_n and mine_n in [n.split('#')[0] for n, _ in exp_order] and mine_n not in want: want.append(mine_n)
    ok(shown == want, '⑥ 승률 내림차순 · 상위 절반만(하위권은 접음) · 표본 3 미만은 빠짐 · 내 우승자는 항상  %s' % shown)
    ok(rows and rows[0]['v'].startswith('100%'), '⑥ 1위 승률 100%%  (%s)' % (rows[0]['v'] if rows else ''))
    ok(all(re.fullmatch(r'\d+%', r['bar']) for r in rows) and rows and rows[0]['bar'] == '100%', '⑥ 막대 그래프 폭 = 승률')
    ok(any(r['me'] for r in rows) == (S['winner'] in [n for n, _ in exp_order]), '⑥ 내가 고른 우승자는 강조(순위표에 있을 때)')
    few = ' '.join(S['few'])
    ok('미드08' in few and '미드09' in few and '미드07' not in few and '미드06' not in few, '⑥ 표본 부족 칸: 붙은 수 3 미만(미드08·09)만 — 3판은 순위표  %s' % few)
    ok('탈퇴미드' not in S['res_text'], '⑥ 서버가 풀 밖(탈퇴자) 이름을 줘도 안 보인다')
    ok('참여 7명' in S['voters_txt'], '⑥ 결과에 참여자 수')
    ok(not re.search(r'꼴찌|최하위|못생|최악', S['res_text']), '⑥ 조롱 문구 없음')
    ok('이번 월드컵 결과' in S['res_text'], '⑥ 「이번 월드컵 결과」 톤')
    ok(S['ov_res']['sw'] <= S['ov_res']['iw'], '⑥ 결과 화면 가로 넘침 0')
    ok(S['res2_rows'] == 0, '⑥ 서폿 풀: 표본이 없으면 행 0 · 안내 문구 (%s)' % S['res2_empty'][:20])
    # ⑦ 실패 처리
    e, r = S['r429']
    ok(r['win'] and r['sent'] == 3 and r['failed'] == 0, '⑦ 429(rate) 한 번은 재시도해서 3번 모두 들어간다  %s' % {k: r[k] for k in ('sent', 'failed')})
    e, r = S['r503']
    ok(r['win'] and r['failed'] >= 1 and '투표를 못 보냈어요' in r['note'], '⑦ 503 이어도 월드컵은 끝까지 · 「투표를 못 보냈어요」 작게 표시  %s' % r['note'][:30])
    e, r = S['rnet']
    ok(r['win'] and r['failed'] >= 1 and '투표를 못 보냈어요' in r['note'], '⑦ 네트워크 실패에도 진행 · 안내')
    e, r = S['r403']
    ok(r['win'] and r['stop'] == 'member' and '클랜 멤버만' in r['note'], '⑦ 403 은 클랜 멤버 안내(더 보내지 않음)')
    e, r = S['r401']
    ok(r['win'] and r['user'] is None and r['ls'] is None and '로그인이 풀렸어요' in r['note'], '⑦ 401 이면 로그아웃 처리(저장된 로그인도 지움) + 안내, 월드컵은 계속')
    ok('쉬는 중' in S['off'] and S['off_start'] == 0, '⑦ on:false 이면 「지금은 쉬는 중」 · 시작 버튼 없음')
    ok('쉬는 중' in S['down'], '⑦ 서버가 503 이어도 「지금은 쉬는 중」으로 안전하게 열린다')
    ok(S['stat401_user'] is None, '⑦ stats 401 → 로그아웃 처리')


async def run_once(src, tmp, name):
    xlsx = os.path.join(tmp, 'ideal.xlsx')
    if not os.path.exists(xlsx): build_xlsx(xlsx)
    bot = Bot(); holder = {}
    async def after(pg):
        holder['S'] = await scenarios(pg, bot)
        return None
    res = await R.replay(src, xlsx=xlsx, now=NOW, cats=('rift',), shots=False, quiet=True, viewport=(360, 900), after=after)
    log = res['meta']['log']
    return holder.get('S'), log


MUTANTS = [
    ('탈퇴자 제외 빼기', "if(pe.keys.some(k=>isDeparted(k))) continue;", ""),
    ('유령 제외 빼기', "if(lastGameDate(rows)<gcut) continue;", ""),
    ('10판 미만 제외 빼기', "if(w+l<TIER_MIN_GAMES) continue;", ""),
    ('LINK 사람 단위 합치기 빼기', 'if(g&&g.length) k="g:"+g[0];', ""),
    ('내 자신 제외 빼기', "if(me&&(c.keys.has(me))) continue;", ""),
    ('승자를 항상 왼쪽으로 보냄', "idealSend(R.pool,a.vname,b.vname,win.vname);", "idealSend(R.pool,a.vname,b.vname,a.vname);"),
    ('승률 오름차순', "b.wr-a.wr||b.n-a.n||(a.c.name<b.c.name?-1:1));\n  const few", "a.wr-b.wr||b.n-a.n||(a.c.name<b.c.name?-1:1));\n  const few"),
    ('401 에도 로그인 유지', "if(r.status===401){ idealAuthLost(); IDEAL.stop=\"auth\"; }", "if(false){}"),
    ('로그아웃에도 투표 전송', "if(!dcValid()||IDEAL.stop) return;\n  const body", "if(IDEAL.stop) return;\n  const body"),
    ('선언 포지션 무시', "if(d&&POS_LIST.includes(d.main)){ pos=d.main; break; }", "if(false){}"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(REPO, 'index.html'))
    ap.add_argument('--no-mutants', action='store_true')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='ideal_')
    S, log = asyncio.run(run_once(a.src, tmp, 'main'))
    check(S)
    ok(not log['pageerror'], '⑨ 페이지 예외 0  %s' % log['pageerror'][:2])
    ok(not log['console'], '⑨ 콘솔 오류 0  %s' % log['console'][:2])
    ok(not log['unknown'], '하네스: 알 수 없는 시트 요청 0  %s' % log['unknown'][:2])
    if not a.no_mutants:
        src = open(a.src, encoding='utf-8').read()
        for label, old, new in MUTANTS:
            if src.count(old) != 1:
                ok(False, '⑧ 변이 「%s」: 바꿀 자리를 찾지 못했다(%d곳) — 시험 갱신 필요' % (label, src.count(old))); continue
            d = os.path.join(tmp, 'mut'); os.makedirs(d, exist_ok=True)
            for sub in ('data', 'img'):
                link = os.path.join(d, sub)
                if not os.path.exists(link) and os.path.isdir(os.path.join(REPO, sub)): os.symlink(os.path.join(REPO, sub), link)
            mp = os.path.join(d, 'index.html')
            open(mp, 'w', encoding='utf-8').write(src.replace(old, new))
            before = len(fails)
            keep = list(fails)
            try:
                S2, log2 = asyncio.run(run_once(mp, tmp, label))
                check(S2)
                killed = len(fails) > before
            except Exception as e:
                killed = True
            del fails[before:]
            fails[:] = keep
            ok(killed, '⑧ 변이 「%s」 → 시험이 잡아낸다' % label)
    print('\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
