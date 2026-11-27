# -*- coding: utf-8 -*-
"""⚖ 내부티어 평가 기준 개선 시험 (2026-11-27 사장님 승인)

합성 시트(가짜 닉네임·PUUID)만 쓴다 — 실제 클랜원 닉네임은 넣지 않는다.

  ① 가중치 = 솔랭 축 30%(솔랭 .25 + 솔랭승률 .05) · 내전 축 70%(AI .25·승률 .20·MVP .15·역적 .10)
  ② 판정 규칙(tierAssessLabel) — |등급차| 2 이상이라도 티어 평균 power 와의 차이가 0.25 미만이면 '적절'(자리 밀림)
  ③ 긴급픽스요망 = 4등급 이상 + power 차이 0.45 이상일 때만 (2티어 미스매치)
  ④ 90일 무기록(휴면) 인원 = label '휴면' · cls 'a-na' · 요약 카운트에 '휴면 N명' 분리 · '적절'로 세지 않음
  ⑤ 화면 불변식 — |등급차| 2 이상 & power 차이 0.25 미만인 사람은 저/고평가가 아니다
  ⑥ 하단 안내문이 실제 계산(현시즌 + 최근 3시즌 최고의 평균)과 맞는다 — 옛 '(최근 3시즌 최고티어 + 현시즌 티어) ÷ 2' 없음
  ⑦ 변이: 규칙 하나를 일부러 깨뜨린 사본에서는 시험이 실패해야 한다 (--no-mutants 로 생략)
  ⑧ 페이지 오류 0

  python3 tests/web_tier_assess_test.py [--src index.html] [--no-mutants]
"""
import argparse, asyncio, datetime as dt, os, random, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

COLS = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
CHAMPS = ['가렌', '아리', '이즈리얼', '쓰레쉬', '리신', '제드']
POS = ['탑', '정글', '미드', '원딜', '서폿']
TIERS = ['0', '1上', '1中', '1下', '2上', '2中', '2下', '3上', '3中', '3下']
LAST = dt.date(2026, 11, 26)                      # 데이터의 마지막 기록일 — 웹의 90일 기준일(2026-08-28)
PER_TIER = 4
N_GAMES = 56                                      # 10인 한 판 × 56
DORMANT = ('휴면테스트#T', '2中')                  # 12판이지만 마지막 판이 130일 전 → 휴면
NEWBIE = ('신입테스트#T', '1中')                   # 4판 → 표본부족


def _roster():
    """티어마다 4명 — 티어 안에서도 실력이 갈리게(승률·AI·솔랭) 잡는다. 일부는 티어와 실력이 어긋난다."""
    rnd = random.Random(7)
    out = []
    for ti, t in enumerate(TIERS):
        for k in range(PER_TIER):
            name = '%s%d#T' % (t.replace('上', 'S').replace('中', 'M').replace('下', 'H'), k)
            base = 10 - ti * 0.85 - k * 0.45            # 같은 티어 안에서 k 가 클수록 약함
            out.append({'n': name, 'tier': t, 'str': base + rnd.uniform(-1.1, 1.1)})
    return out


ROSTER = _roster()


def build_xlsx(path):
    from openpyxl import Workbook
    rnd = random.Random(11)
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'; ws.append(COLS)
    players = {p['n']: p for p in ROSTER}
    everyone = [p['n'] for p in ROSTER]
    pu = {n: 'pu-%d' % i for i, n in enumerate(everyone + [DORMANT[0], NEWBIE[0]])}
    gid = [9000]

    def put(g, day, name, side, pos, res, ev, score, kda):
        ws.append(['#%d' % g, day, name, pu.get(name, 'pu-x'), side, pos, rnd.choice(CHAMPS), None, res, ev,
                   'v16.23', kda, score, 20000.0, None, None, None, None, None])

    def ten(day):
        pick = rnd.sample(everyone, 10)
        gid[0] += 1
        g = gid[0]
        strs = [players[n]['str'] for n in pick]
        mu = sum(strs) / len(strs)
        rows = []
        for i, n in enumerate(pick):
            p = 1 / (1 + pow(2.718281828, -(players[n]['str'] - mu) / 1.4))
            win = rnd.random() < p
            sc = max(4.0, min(48.0, 21 + (players[n]['str'] - 5) * 4.2 + rnd.uniform(-4, 4)))
            rows.append({'n': n, 'side': '블루팀' if i < 5 else '레드팀', 'res': '승리' if win else '패배',
                         'pos': POS[i % 5], 'sc': round(sc, 1)})
        # MVP = 이긴 팀 최고 점수 / 역적 = 진 팀 최저 점수
        winners = [r for r in rows if r['res'] == '승리']
        losers = [r for r in rows if r['res'] == '패배']
        for r in rows: r['ev'] = None
        if winners:
            m = max(winners, key=lambda r: r['sc'])
            if rnd.random() < .8: m['ev'] = 'MVP'
        if losers:
            b = min(losers, key=lambda r: r['sc'])
            if rnd.random() < .25: b['ev'] = '역적'
        for r in rows:
            kda = '%d/%d/%d' % (rnd.randint(0, 12), rnd.randint(0, 9), rnd.randint(0, 18))
            put(g, day + ' 21:00', r['n'], r['side'], r['pos'], r['res'], r['ev'], r['sc'], kda)

    for i in range(N_GAMES):
        day = (LAST - dt.timedelta(days=i % 40)).isoformat()
        ten(day)

    # 🎯 휴면: 12판 전부 120~160일 전 → 90일 컷(08-28) 밖
    for i in range(12):
        gid[0] += 1
        day = (LAST - dt.timedelta(days=120 + i * 3)).isoformat() + ' 21:00'
        for j in range(10):
            nm = DORMANT[0] if j == 0 else rnd.choice(everyone)
            put(gid[0], day, nm, ('블루팀' if j < 5 else '레드팀'), POS[j % 5],
                '승리' if j < 5 else '패배', None, 30.0, '5/3/8')
    # 🎯 신입: 4판만
    for i in range(4):
        gid[0] += 1
        day = (LAST - dt.timedelta(days=i)).isoformat() + ' 21:00'
        for j in range(10):
            nm = NEWBIE[0] if j == 0 else rnd.choice(everyone)
            put(gid[0], day, nm, ('블루팀' if j < 5 else '레드팀'), POS[j % 5],
                '승리' if j < 5 else '패배', None, 20.0, '3/4/9')

    tiers = [['닉네임', '티어']] + [[p['n'].split('#')[0], p['tier']] for p in ROSTER] + \
            [[DORMANT[0].split('#')[0], DORMANT[1]], [NEWBIE[0].split('#')[0], NEWBIE[1]]]
    solo = [['닉네임', '티어', 'LP', '솔랭승', '솔랭패', '점수', '갱신', '아이콘', '레벨']]
    for i, p in enumerate(ROSTER):
        sc = int(max(300, min(3600, 1200 + p['str'] * 250)))
        tier, lp = ('MASTER I', sc - 2800) if sc >= 2800 else ('DIAMOND II', 40 + i % 50)
        solo.append([p['n'], tier, lp, 60 + i % 40, 50 + i % 30, sc, '2026-11-26 13:00', 1000 + i, 200 + i])
    for name, rows in (('CLAN_TIERS', tiers), ('SOLO_RANK', solo),
                       ('LINK_ACCOUNT', [['본계정', '부계정 롤닉 (#태그 있어도 됨)', '메모 (선택)']]),
                       ('DEPARTED', [['닉네임', '갱신시각']])):
        w = wb.create_sheet(name)
        for r in rows: w.append(r)
    wb.save(path)


STATE_JS = r"""(() => {
  try{ renderTiers(); }catch(e){}
  const rows={}; const players=[]; const dorm=[];
  for(const [n,a] of ASSESSMENTS){
    if(isDeparted(n)) continue;
    rows[a.label]=(rows[a.label]||0)+1;
    if(a.detail && a.power!=null) players.push({n, tier:a.tier, label:a.label, gap:a.implGap, dev:a.powerDev, games:a.games});
    if(a.label==='휴면') dorm.push({n, cls:a.cls, games:a.games, detail:!!a.detail});
  }
  const chips={}; document.querySelectorAll('.tb-tag').forEach(e=>{const t=e.textContent.trim(); chips[t]=(chips[t]||0)+1;});
  const card=document.querySelector('.card'); const txt=card?card.innerText:'';
  const i=txt.indexOf('내부티어 평가');
  const rule={};
  if(typeof tierAssessLabel==='function'){
    const cases=[[2,0.10,'적절'],[2,0.24,'적절'],[-2,0.20,'적절'],[2,0.30,'저평가'],[-2,0.30,'고평가'],
                 [4,0.50,'긴급픽스요망↑저평가'],[-4,0.60,'긴급픽스요망↓고평가'],[4,0.20,'적절'],
                 [4,0.30,'저평가'],[1,0.90,'적절'],[3,0.80,'저평가'],[-3,0.46,'고평가']];
    rule.cases=cases.map(([di,dev,want])=>{ const r=tierAssessLabel(di,dev); return {di,dev,want,got:r.label,ok:r.label===want}; });
  }
  return {rows, players, dorm, chips, rule,
    w:{solo:W_SOLO, ai:W_AI, wr:W_WR, solowr:W_SOLOWR, mvp:W_MVP, troll:W_TROLL,
       border:(typeof TIER_POW_BORDER!=='undefined'?TIER_POW_BORDER:null),
       urgent:(typeof TIER_POW_URGENT!=='undefined'?TIER_POW_URGENT:null)},
    hasOld:/최고티어 \+ 현시즌 티어/.test(txt), hasNew:txt.indexOf('최근 3시즌 최고 점수')>=0,
    sum:txt.slice(i, i+430)};
})()"""

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)


async def run_once(src, td, tag):
    x = os.path.join(td, 's_%s.xlsx' % tag); build_xlsx(x)
    res = await R.replay(src, xlsx=x, now='2026-11-27T18:30:00', cats=('rift',), shots=False, quiet=True,
                         evals=(STATE_JS,), timeout_s=300)
    return res['evals'][0], res['meta']['log']


def check(S):
    w = S['w']
    ok(abs(w['solo'] - .25) < 1e-9 and abs(w['ai'] - .25) < 1e-9 and abs(w['wr'] - .20) < 1e-9
       and abs(w['solowr'] - .05) < 1e-9 and abs(w['mvp'] - .15) < 1e-9 and abs(w['troll'] - .10) < 1e-9,
       '① 가중치 = 솔랭 .25 · AI .25 · 승률 .20 · 솔랭승률 .05 · MVP .15 · 역적 .10  %s' % w)
    ok(abs((w['solo'] + w['solowr']) - .30) < 1e-9 and abs((w['ai'] + w['wr'] + w['mvp'] + w['troll']) - .70) < 1e-9,
       '① 솔랭 축 합계 30%% · 내전 축 70%% (%.2f / %.2f)' % (w['solo'] + w['solowr'], w['ai'] + w['wr'] + w['mvp'] + w['troll']))
    ok(w['border'] == 0.25 and w['urgent'] == 0.45, '②③ 컷 값 = 경계선 0.25 · 긴급 0.45 (%s / %s)' % (w['border'], w['urgent']))

    rule = S['rule']
    ok(bool(rule.get('cases')), '② 판정 규칙 함수(tierAssessLabel)가 페이지에 있다')
    for c in rule.get('cases') or []:
        ok(c['ok'], '② tierAssessLabel(di=%+d, power차=%.2f) = %s (실제 %s)' % (c['di'], c['dev'], c['want'], c['got']))

    dorm = S['dorm']
    ok(len(dorm) == 1 and dorm[0]['n'].split('#')[0] == DORMANT[0].split('#')[0],
       '④ 90일 무기록 1명만 휴면 (실제 %s)' % [d['n'] for d in dorm])
    if dorm:
        d = dorm[0]
        ok(d['cls'] == 'a-na' and d['games'] >= 10, '④ 휴면 = cls a-na · 10판 이상 (%s, %d판)' % (d['cls'], d['games']))
    ok(S['rows'].get('표본부족', 0) >= 1, '④ 10판 미만은 표본부족으로 남는다 (실제 %s)' % S['rows'].get('표본부족'))
    ok(any(p['n'].startswith(NEWBIE[0].split('#')[0]) for p in S['players']) is False
       and not any(d['n'].startswith(NEWBIE[0].split('#')[0]) for d in dorm),
       '④ 4판짜리 신입은 휴면이 아니라 표본부족이다')
    ok(S['chips'].get('휴면') == 1, '④ 화면 칩에도 휴면이 1개 뜬다 %s' % S['chips'])
    ok('휴면 1명' in S['sum'].replace('**', ''), '④ 요약 카운트에 "휴면 1명" 분리 표시 %r' % S['sum'][:200])
    ok(S['chips'].get('적절', 0) == S['rows'].get('적절', -1), '④ 적절 칩 수 = 적절 인원 (휴면이 적절로 새지 않는다)')

    players = S['players']
    ok(len(players) >= 20, '합성 표본: 평가된 인원 %d명' % len(players))
    border_ok = [p for p in players if abs(p['gap'] or 0) >= 2 and p['dev'] is not None and p['dev'] < 0.25
                 and p['label'] == '적절']
    ok(bool(border_ok), '⑤ 등급차 2 이상이라도 power 차이 0.25 미만이면 적절(자리 밀림)로 남는다 %s' %
       ['%s(dev=%.2f,gap=%d)' % (p['n'].split('#')[0], p['dev'], p['gap']) for p in border_ok])
    bad_flag = [p for p in players if p['label'] in ('저평가', '고평가') and (p['dev'] is None or p['dev'] < 0.25 or abs(p['gap'] or 0) < 2)]
    ok(not bad_flag, '⑤ 저/고평가를 단 사람은 모두 등급차 2↑ & power 차이 0.25↑ %s' %
       ['%s(gap=%s,dev=%s,%s)' % (p['n'].split('#')[0], p['gap'], p['dev'], p['label']) for p in bad_flag])
    bad_urgent = [p for p in players if str(p['label']).startswith('긴급') and not ((p['gap'] or 0) >= 4 and p['dev'] is not None and p['dev'] >= 0.45)]
    ok(not bad_urgent, '③ 긴급픽스는 4등급↑ + power 차이 0.45↑ 뿐 %s' %
       ['%s(gap=%s,dev=%s)' % (p['n'].split('#')[0], p['gap'], p['dev']) for p in bad_urgent])
    ok(any(p['label'] in ('저평가', '고평가') for p in players), '⑤ 합성 표본에 저/고평가 사례가 있다(규칙이 실제로 돌았다)')

    ok(not S['hasOld'], '⑥ 옛 문구 "(최근 3시즌 최고티어 + 현시즌 티어) ÷ 2" 가 없다')
    ok(S['hasNew'], '⑥ 안내문이 실제 계산(현시즌 + 최근 3시즌 최고의 평균)을 말한다')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(REPO, 'index.html'))
    ap.add_argument('--no-mutants', action='store_true')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='tierassess_')
    S, log = await run_once(a.src, tmp, 'main')
    print('  분포:', S['rows'], '| 칩:', S['chips'])
    check(S)
    ok(not log['pageerror'], '⑧ 페이지 예외 0  %s' % log['pageerror'][:2])
    ok(not log['console'], '⑧ 콘솔 오류 0  %s' % log['console'][:2])

    if not a.no_mutants:
        src = open(a.src, encoding='utf-8').read()
        MUTANTS = [
            ('가중치를 옛 값으로', 'const W_SOLO=0.25, W_AI=0.25, W_WR=0.20, W_SOLOWR=0.05, W_MVP=0.15, W_TROLL=0.10;',
             'const W_SOLO=0.35, W_AI=0.20, W_WR=0.15, W_SOLOWR=0.10, W_MVP=0.10, W_TROLL=0.10;'),
            ('경계선 컷을 0으로', 'const TIER_POW_BORDER=0.25, TIER_POW_URGENT=0.45;',
             'const TIER_POW_BORDER=0, TIER_POW_URGENT=0.45;'),
            ('휴면 라벨을 끄기', 'if(!x.act){ label="휴면"; cls="a-na"; }', 'if(false){ label="휴면"; cls="a-na"; }'),
            ('긴급픽스 power 컷을 빼기', 'const urgent = Math.abs(di)>=4 && (pdev==null || pdev>=TIER_POW_URGENT);',
             'const urgent = Math.abs(di)>=4;'),
        ]
        for label, old, new in MUTANTS:
            if src.count(old) != 1:
                ok(False, '⑦ 변이 「%s」: 바꿀 자리를 찾지 못했다(%d곳) — 시험 갱신 필요' % (label, src.count(old))); continue
            d = os.path.join(tmp, 'mut_%d' % MUTANTS.index((label, old, new))); os.makedirs(d, exist_ok=True)
            for sub in ('data', 'img'):
                link = os.path.join(d, sub)
                if not os.path.exists(link) and os.path.isdir(os.path.join(REPO, sub)): os.symlink(os.path.join(REPO, sub), link)
            mp = os.path.join(d, 'index.html')
            open(mp, 'w', encoding='utf-8').write(src.replace(old, new))
            keep = list(fails); before = len(fails)
            try:
                S2, _ = await run_once(mp, tmp, 'mut%d' % MUTANTS.index((label, old, new)))
                check(S2)
                killed = len(fails) > before
            except Exception:
                killed = True
            del fails[before:]
            fails[:] = keep
            ok(killed, '⑦ 변이 「%s」 → 시험이 잡아낸다' % label)

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())
