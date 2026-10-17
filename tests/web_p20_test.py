# -*- coding: utf-8 -*-
"""📅 P-20 웹 기본 보기를 「최신 패치」에서 「최근 30일」로 — 시험 (2026-10-11 사장님 「P20 진행시켜줘」 · 선택지 (나))
기본 범위 = 최근 30일(기준일 = 데이터의 마지막 기록일). 챔피언 티어 탭만 칩을 안 골랐으면 최신 패치. 통산인 화면은 그대로.

  S(합성 데이터 — 스냅샷 없이 늘 돈다)
    S1 기본 범위는 「최근 30일」: 라벨 · 칩 · 판수 · 경계(30일째 날은 들어가고 31일째 날은 빠진다)
    S2 최신 패치에 0판이라 목록에서 빠지던 사람이 이제 홈 목록에 보인다
    S3 패치 칩을 누르면 그 패치만 · 전체 칩 · 직접 고른 선택은 탭을 옮겨도 유지
    S4 챔피언 티어 탭은 최신 패치(안내 문구 포함) · 다른 탭은 최근 30일 · 챔피언 상세는 티어 탭 범위를 이어받는다
    S5 칩을 직접 누른 뒤에는 챔피언 티어 탭도 그 선택을 따른다
    S6 공유 링크(#p/·#g/)는 전체 기간으로 열고 그 뒤 탭을 옮겨도 전체 기간
    S7 프로필 승률 링 밑 한 줄 「최근 30일 · 통산 N전 W승」 (전체 기간이면 「전체 기간(통산)」)
    S8 기준일이 마지막 기록일 — 3달 묵은 스냅샷에서도 화면이 안 빈다 · 안내 문구
    S9 통산인 화면(내부티어·업적·전역일·플레이스타일·미토·멸망전·리포트·인간상성 …)은 범위가 달라도 글자가 같다
    S10 폰 360 가로 넘침 0 · 페이지 오류 0
  G(실제 시트 스냅샷 — --gviz-dir 또는 --xlsx, 없으면 SKIP)
    G1 기본 범위·판수가 다시 센 값과 같다 · G2 0판으로 빠지던 활동 클랜원 전/후 · G3 통산인 화면·선수별 통산 칸이 기준 커밋과 전수 동일
    G4 폰 360 가로 넘침 0 · G5 칼바람도 같은 규칙
  python3 tests/web_p20_test.py [--src index.html] [--gviz-dir <폴더> | --xlsx <시트.xlsx>] [--base-src <고치기 전 index.html>]
  --base-src 가 없으면 git 의 기준 커밋(BASE_COMMIT)에서 꺼낸다. 그것도 없으면 G3 의 전/후 비교만 건너뛴다.
"""
import argparse, asyncio, datetime as dt, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

BASE_COMMIT = '4ea539f'          # P-20 을 넣기 직전 커밋(기본 보기가 최신 패치이던 때)
NOW = '2026-10-11T15:00:00'       # 시계 고정(한국 시각)
COLS = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
POS = ['탑', '정글', '미드', '원딜', '서폿']
CHAMPS = ['가렌', '아리', '이즈리얼', '쓰레쉬', '리신', '제드', '카이사', '룰루', '문도', '야스오', '징크스', '블리츠']
fails = []


def ok(c, msg):
    print(('  ok   ' if c else '  FAIL ') + msg)
    if not c:
        fails.append(msg)


# ---------------------------------------------------------------- 합성 시트
def _nm(i): return '시험가%02d#KR1' % i


def make_games(last):
    """(게임ID, 날짜, 패치, 참가자 번호 10명) 목록. last = 마지막 기록일(date).
    16.20: last·last-1·last-2 (P01~P10) / 16.19: last-3 부터 이틀 간격으로 30일창 끝(last-29)까지 + 창 밖 하루(last-30) (P01~P09 + P11) / 16.18: 더 옛날 4판 (P01~P09 + P12)"""
    g = []
    n = 0
    def add(day, patch, who):
        nonlocal n
        n += 1
        g.append(('#80000%03d' % n, (last - dt.timedelta(days=day)).isoformat(), patch, who))
    for d in (2, 1, 0): add(d, 'v16.20', list(range(1, 11)))
    for d in list(range(3, 30, 2)) + [29, 30]: add(d, 'v16.19', list(range(1, 10)) + [11])   # 29 = 30일창의 첫 날(들어간다) · 30 = 창 밖 하루(빠진다)
    for d in (36, 41, 47, 60): add(d, 'v16.18', list(range(1, 10)) + [12])
    return g


def make_xlsx(path, last):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'
    ws.append(COLS)
    for gi, (gid, day, patch, who) in enumerate(make_games(last)):
        blue_wins = gi % 2 == 0
        for k, p in enumerate(who):
            team = 0 if k < 5 else 1
            win = (team == 0) == blue_wins
            ws.append([gid, day + ' 21:00', _nm(p), 'test-puuid-%02d' % p, '블루팀' if team == 0 else '레드팀', POS[k % 5], CHAMPS[(p + gi) % 12], None,
                       '승리' if win else '패배', None, patch, '%d/%d/%d' % (3 + k, 2 + k % 3, 4 + k), 20.0 + k, float(20000 + 1000 * k), None, None, None, None,
                       'g%d|cs%d|m30.0|kp50|vs20|cw2|wp10|wk2|op0|tk1|dt20000|hs0|dr0|br0' % (12000 + 300 * k, 180 + 10 * k)])
    wb.save(path)


def expect(last):
    """파이썬이 다시 센 기대값."""
    games = make_games(last)
    frm = last - dt.timedelta(days=29)
    in30 = [x for x in games if dt.date.fromisoformat(x[1]) >= frm]
    latest = [x for x in games if x[2] == 'v16.20']
    allp = set(p for x in games for p in x[3])
    def rec(p, sub):
        n = w = 0
        for gi, (gid, day, patch, who) in enumerate(games):
            if (gid, day, patch, who) not in sub or p not in who: continue
            k = who.index(p); win = ((0 if k < 5 else 1) == 0) == (gi % 2 == 0)
            n += 1; w += win
        return n, w
    return {'games': games, 'from': frm, 'in30': in30, 'latest': latest, 'players30': set(p for x in in30 for p in x[3]),
            'playersLatest': set(p for x in latest for p in x[3]), 'allp': allp, 'rec': rec}


# ---------------------------------------------------------------- 브라우저에서 돌리는 식
STATE = r"""()=>({sel:PATCH_SEL,label:patchScopeLabel(),user:(typeof PATCH_USER!=='undefined'?PATCH_USER:null),meta:(typeof META_VIEW!=='undefined'?META_VIEW:null),games:GAMES.size,players:PLAYERS.size,playersAll:PLAYERS_ALL.size,
  r30:(typeof R30!=='undefined'?[R30.from,R30.to]:null),latest:LATEST_PATCH,on:[...document.querySelectorAll('#patchbar .pchip.on')].map(e=>e.textContent.trim()),
  chips:[...document.querySelectorAll('#patchbar .pchip')].map(e=>e.textContent.trim()),note:(document.querySelector('#patchnote')||{}).textContent||'',
  noteHidden:document.querySelector('#patchnote')?document.querySelector('#patchnote').classList.contains('hidden'):null})"""
GO = r"""async([route,arg])=>{go(route,arg);await new Promise(r=>setTimeout(r,700));}"""
CLICK = r"""async(txt)=>{const b=[...document.querySelectorAll('#patchbar .pchip')].find(e=>e.textContent.trim()===txt);if(!b)return false;b.click();await new Promise(r=>setTimeout(r,700));return true;}"""
OVERFLOW = r"""(route)=>{const de=document.documentElement;return {route,sw:de.scrollWidth,cw:de.clientWidth};}"""
HASHES = r"""async(items)=>{
  const H=s=>{let h=5381;for(let i=0;i<s.length;i++)h=((h<<5)+h+s.charCodeAt(i))|0;return (h>>>0).toString(16)+':'+s.length};
  const out={};
  for(const [route,arg] of items.routes){
    try{ go(route,arg); }catch(e){ out['route:'+route]='ERR '+e.message; continue; }
    await new Promise(r=>setTimeout(r,800));
    out['route:'+route]=H(document.querySelector('#view').innerText);
  }
  const names=[...PLAYERS_ALL.keys()];
  for(const n of names){
    try{ CUR_PLAYER=n;_STYLE_PCT={};renderStyle(n); out['style:'+n]=H(document.querySelector('#view').innerText); }catch(e){ out['style:'+n]='ERR'; }
    for(const f of ['recordRoomHtml','growthCardHtml','nightCardHtml']){
      try{ if(typeof window[f]==='function'||typeof eval(f)==='function') out[f+':'+n]=H(String(eval(f)(n)||'')); }catch(e){ out[f+':'+n]='ERR'; }
    }
  }
  for(const [n,a] of ASSESSMENTS){ const d=a.detail||{}; out['assess:'+n]=H(JSON.stringify([a.tier,a.label,a.games,a.title||null,a.power,d.score,d.wr,d.ai,d.mvp,d.troll,d.ace,d.solo,d.soloCur])); }
  out['playersAll']=PLAYERS_ALL.size+':'+[...PLAYERS_ALL.values()].reduce((s,x)=>s+x.length,0);
  out['gamesAll']=GAMES_ALL.size;
  return out;
}"""
ACT = r"""()=>{
  const ymd=d=>{const m=String(d||'').match(/^(\d{4})-(\d{2})-(\d{2})/);return m?m[0]:''};
  const add=(y,n)=>{const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(y);return new Date(Date.UTC(+m[1],+m[2]-1,+m[3]+n)).toISOString().slice(0,10)};
  let last=''; for(const [n,ps] of PLAYERS_ALL) for(const r of ps){const d=ymd(r['날짜']); if(d>last)last=d;}
  const from=add(last,-29);
  const act=[];
  for(const [n,ps] of PLAYERS_ALL){ if(isDeparted(n)) continue; let c=0; for(const r of ps){const d=ymd(r['날짜']); if(d>=from&&d<=last&&(r['결과']==='승리'||r['결과']==='패배')) c++;}
    if(c>=5) act.push({n,c30:c,shown:(PLAYERS.get(n)||[]).filter(r=>r['결과']==='승리'||r['결과']==='패배').length,inList:PLAYERS.has(n)}); }
  const med=a=>{a=a.slice().sort((x,y)=>x-y);return a.length?(a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2):0};
  return {last,from,sel:PATCH_SEL,games:GAMES.size,players:PLAYERS.size,act5:act.length,missing:act.filter(x=>!x.inList).length,lt5:act.filter(x=>x.shown<5).length,
          medShown:med(act.map(x=>x.shown)),medC30:med(act.map(x=>x.c30))};
}"""
RAWCOUNT = r"""()=>{
  const ymd=d=>{const m=String(d||'').match(/^(\d{4})-(\d{2})-(\d{2})/);return m?m[0]:''};
  let last=''; for(const r of RAW){ if(r['게임ID']){const d=ymd(r['날짜']); if(d>last)last=d;} }
  const add=(y,n)=>{const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(y);return new Date(Date.UTC(+m[1],+m[2]-1,+m[3]+n)).toISOString().slice(0,10)};
  const from=add(last,-29); const g=new Set();
  for(const r of RAW){ const id=r['게임ID']; if(!id)continue; const d=ymd(r['날짜']); if(d>=from&&d<=last) g.add(id); }
  return {last,from,games30:g.size};
}"""
TONGSAN_ROUTES = [['tiers', None], ['ach', None], ['army', None], ['mito', None], ['myeol', None], ['report', None], ['rival', None], ['market', None], ['cal', None], ['scrim', None]]


# ---------------------------------------------------------------- S 시험
async def run_synth(src, tmp):
    last = dt.date(2026, 10, 11)
    xl = os.path.join(tmp, 'fakeA.xlsx'); make_xlsx(xl, last)
    E = expect(last)
    me = _nm(1)

    async def after(pg):
        o = {}
        o['s0'] = await pg.evaluate(STATE)
        o['homeText'] = await pg.evaluate("()=>document.querySelector('#view').innerText")
        # S2: 홈 표에 P11(최신 패치 0판 · 30일 안 16.19 출전) 이 있는가
        o['home_has_p11'] = await pg.evaluate("(n)=>PLAYERS.has(n)", _nm(11))
        o['home_has_p12'] = await pg.evaluate("(n)=>PLAYERS.has(n)", _nm(12))
        # S7: 프로필 한 줄
        await pg.evaluate(GO, ['player', me])
        o['ring_r30'] = await pg.evaluate("()=>{const e=document.querySelector('.side-scope');return e?e.textContent.replace(/\\s+/g,' ').trim():null}")
        o['ring_pct'] = await pg.evaluate("()=>{const e=document.querySelector('.ring .inner b');return e?e.textContent:null}")
        o['ring_rec'] = await pg.evaluate("()=>{const e=document.querySelector('.side-rec');return e?e.textContent.replace(/\\s+/g,' ').trim():null}")
        # S4: 챔피언 티어 탭 → 최신 패치
        await pg.evaluate(GO, ['champ', None]); o['champ0'] = await pg.evaluate(STATE)
        await pg.evaluate("()=>{const c=champTierData('ALL')[0];window.__ch=c?c.champ:null}")
        ch = await pg.evaluate("()=>window.__ch")
        await pg.evaluate(GO, ['champlog', ch]); o['champlog'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['home', None]); o['home_after_champ'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['champ', None]); o['champ1'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['player', me]); o['player_after_champ'] = await pg.evaluate(STATE)
        # S3: 패치 칩 → 그 패치만 · 탭을 옮겨도 유지
        await pg.evaluate(GO, ['home', None])
        await pg.evaluate(CLICK, '16.18'); o['p18'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['log', None]); o['p18_log'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['champ', None]); o['p18_champ'] = await pg.evaluate(STATE)
        await pg.evaluate(CLICK, '전체'); o['all'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['player', me]); o['ring_all'] = await pg.evaluate("()=>{const e=document.querySelector('.side-scope');return e?e.textContent.replace(/\\s+/g,' ').trim():null}")
        # S5: 최근 30일 칩을 직접 누르고 티어 탭으로
        await pg.evaluate(CLICK, '최근 30일'); await pg.evaluate(GO, ['champ', None]); o['r30_user_champ'] = await pg.evaluate(STATE)
        # S6: 공유 링크
        await pg.evaluate("()=>{PATCH_SEL=null;PATCH_USER=false;build();renderPatchbar();go('home')}"); await pg.wait_for_timeout(300)
        o['pre_link'] = await pg.evaluate(STATE)
        await pg.evaluate("(n)=>{_openRoute({k:'p',cat:'rift',arg:n},true)}", me); await pg.wait_for_timeout(700)
        o['link_p'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['home', None]); o['link_then_home'] = await pg.evaluate(STATE)
        await pg.evaluate("()=>{PATCH_SEL=null;PATCH_USER=false;build();renderPatchbar();go('home')}"); await pg.wait_for_timeout(300)
        gid = E['games'][-1][0]   # 가장 오래된 판 — 30일 밖
        await pg.evaluate("(g)=>{_openRoute({k:'g',cat:'rift',arg:g.replace('#','')},true)}", gid); await pg.wait_for_timeout(700)
        o['link_g'] = await pg.evaluate(STATE)
        o['link_g_open'] = await pg.evaluate("()=>((history.state||{}).route)")
        # S9: 통산 화면은 범위가 달라도 같다(첫 판 캐시 효과를 피하려 한 바퀴 돌려 데운 뒤)
        txt = {}
        for rnd in ('warm', 'R30', 'ALL', 'LATEST'):
            sel = {'warm': 'R30', 'R30': 'R30', 'ALL': 'ALL', 'LATEST': '16.20'}[rnd]
            await pg.evaluate("(s)=>{PATCH_USER=true;PATCH_SEL=s;build();renderPatchbar();}", sel)
            for route, arg in TONGSAN_ROUTES + [['style', me]]:
                t = await pg.evaluate("async([r,a])=>{go(r,a);await new Promise(x=>setTimeout(x,600));return document.querySelector('#view').innerText}", [route, arg])
                txt.setdefault(route, {})[rnd] = t
        o['tongsan'] = {k: (v['R30'] == v['ALL'] == v['LATEST']) for k, v in txt.items()}
        # S11 보완: GPTI 누적 · 일찍 return 하는 화면 · 30일 0판 선수 자동 전환
        await pg.evaluate("()=>{PATCH_USER=false;PATCH_AUTO=false;PATCH_SEL=null;build();renderPatchbar();go('home')}"); await pg.wait_for_timeout(300)
        await pg.evaluate("()=>{window.parseMetrics=()=>({kp:1,dt:1,vs:1,g:1,cs:1,m:30});window.parseKDA=()=>({k:1,d:1,a:1});GPTI_ROWS={base:[{b:1}]};build();}")
        TOT = "()=>Object.values(GPTI_ROWS||{}).reduce((a,v)=>a+v.length,0)"
        o['gpti0'] = await pg.evaluate(TOT)
        for r_ in ('champ', 'home', 'champ', 'home', 'mastery'):
            await pg.evaluate(GO, [r_, None])
        o['gpti1'] = await pg.evaluate(TOT)
        await pg.evaluate(GO, ['champ', None]); await pg.evaluate(GO, ['gpti', None]); o['champ_gpti'] = await pg.evaluate(STATE)
        for r_ in ('champ', 'report'):
            await pg.evaluate(GO, [r_, None])
        o['champ_report'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['champ', None]); await pg.evaluate(GO, ['player', _nm(12)])
        o['fell'] = await pg.evaluate(STATE)
        o['fell_txt'] = await pg.evaluate("()=>document.querySelector('#view').innerText")
        # [A-32] 자동 전체 기간으로 열린 상태에서 곧바로 다른 선수(30일 안 기록 있음)를 열면 기본 범위(최근 30일)로 돌아오고 거짓 안내가 안 남는다
        await pg.evaluate(GO, ['home', None]); await pg.evaluate(GO, ['player', _nm(12)])
        o['a32_first'] = await pg.evaluate("()=>({sel:PATCH_SEL,auto:PATCH_AUTO,note:(document.querySelector('#patchnote')||{}).textContent||''})")
        await pg.evaluate(GO, ['player', _nm(1)])
        o['a32_next'] = await pg.evaluate("()=>({sel:PATCH_SEL,auto:PATCH_AUTO,note:(document.querySelector('#patchnote')||{}).textContent||''})")
        await pg.evaluate(GO, ['champ', None]); o['fell_champ'] = await pg.evaluate(STATE)
        await pg.evaluate(GO, ['home', None]); o['fell_home'] = await pg.evaluate(STATE)
        # S10 폰 넘침
        o['overflow'] = []
        await pg.evaluate("()=>{PATCH_USER=false;PATCH_SEL=null;build();renderPatchbar();}")
        for route, arg in (['home', None], ['player', me], ['champ', None], ['log', None]):
            await pg.evaluate(GO, [route, arg]); o['overflow'].append(await pg.evaluate(OVERFLOW, route))
        return o

    res = await R.replay(src, xlsx=xl, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True, now=NOW, after=after, timeout_s=300)
    o = res['after']
    print('[S] 합성 시트 A: 판 %d · 30일창 %s~%s %d판 · 16.20 %d판' % (len(E['games']), E['from'], last, len(E['in30']), len(E['latest'])))
    s0 = o['s0']
    ok(s0['sel'] == 'R30' and s0['label'] == '최근 30일', 'S1a 기본 범위는 「최근 30일」이다 (sel=%s · 라벨=%s)' % (s0['sel'], s0['label']))
    ok(s0['chips'][:2] == ['최근 30일', '16.20'] and s0['on'] == ['최근 30일'], 'S1b 패치 줄 맨 앞이 [최근 30일] 칩이고 켜져 있다 (%s · 켜짐 %s)' % (s0['chips'][:3], s0['on']))
    ok(s0['r30'] == [E['from'].isoformat(), last.isoformat()], 'S1c 30일창 = 마지막 기록일 포함 30일 (%s)' % s0['r30'])
    ok(s0['games'] == len(E['in30']), 'S1d 기본 화면 판수가 다시 센 값과 같다: %d == %d (30일째 날 판은 들어가고 31일째 날 판은 빠진다)' % (s0['games'], len(E['in30'])))
    ok('9/12~10/11' in s0['note'] and not s0['noteHidden'], 'S1e 칩 줄 밑에 기간 안내가 있다 (%s)' % s0['note'])
    ok(o['home_has_p11'] and not o['home_has_p12'], 'S2 최신 패치에 0판이던 활동 클랜원(P11)이 홈 목록에 보이고, 30일 밖에만 뛴 사람(P12)은 안 보인다 (%s · %s)' % (o['home_has_p11'], o['home_has_p12']))
    ok(s0['players'] == len(E['players30']) and s0['playersAll'] == len(E['allp']), 'S2b 홈 인원 %d == 30일 출전 %d · 통산 인원 %d == %d' % (s0['players'], len(E['players30']), s0['playersAll'], len(E['allp'])))
    n30, w30 = E['rec'](1, E['in30']); nall, wall = E['rec'](1, E['games'])
    ok(o['ring_r30'] == '최근 30일 · 통산 %d전 %d승' % (nall, wall), 'S7a 프로필 링 밑 한 줄 = 「최근 30일 · 통산 %d전 %d승」 (%s)' % (nall, wall, o['ring_r30']))
    ok(o['ring_rec'].startswith('%d전 %d승 %d패' % (n30, w30, n30 - w30)), 'S7b 링 밑 전적은 30일치다 (%s)' % o['ring_rec'])
    ok(o['ring_all'] == '전체 기간(통산)', 'S7c 전체 기간이면 「전체 기간(통산)」 한 줄만 (%s)' % o['ring_all'])
    c0 = o['champ0']
    ok(c0['sel'] == '16.20' and c0['games'] == len(E['latest']) and c0['on'] == ['16.20'] and '최신 패치(16.20)' in c0['note'],
       'S4a 챔피언 티어 탭은 최신 패치로 열리고 안내가 나온다 (sel=%s · 판 %d · 켜짐 %s · 안내 %s)' % (c0['sel'], c0['games'], c0['on'], c0['note'][:30]))
    ok(o['champlog']['sel'] == '16.20', 'S4b 티어 탭에서 챔피언 상세로 들어가면 같은 범위를 이어 본다 (%s)' % o['champlog']['sel'])
    ok(o['home_after_champ']['sel'] == 'R30' and o['home_after_champ']['games'] == len(E['in30']), 'S4c 다른 탭(홈)으로 가면 다시 최근 30일 (%s · %d판)' % (o['home_after_champ']['sel'], o['home_after_champ']['games']))
    ok(o['champ1']['sel'] == '16.20' and o['player_after_champ']['sel'] == 'R30', 'S4d 티어 탭 ↔ 선수 페이지를 오가도 각자 기본 범위로 간다 (%s · %s)' % (o['champ1']['sel'], o['player_after_champ']['sel']))
    n18 = len([x for x in E['games'] if x[2] == 'v16.18'])
    ok(o['p18']['sel'] == '16.18' and o['p18']['games'] == n18 and o['p18']['user'], 'S3a 16.18 칩 → 그 패치 %d판만 (%s · %d판)' % (n18, o['p18']['sel'], o['p18']['games']))
    ok(o['p18_log']['sel'] == '16.18' and o['p18_champ']['sel'] == '16.18', 'S3b 직접 고른 패치는 탭을 옮겨도(내전기록·챔피언 티어) 유지된다 (%s · %s)' % (o['p18_log']['sel'], o['p18_champ']['sel']))
    ok(o['all']['sel'] == 'ALL' and o['all']['games'] == len(E['games']), 'S3c 전체 칩 → 전부 %d판 (%d)' % (len(E['games']), o['all']['games']))
    ok(o['r30_user_champ']['sel'] == 'R30' and o['r30_user_champ']['on'] == ['최근 30일'], 'S5 최근 30일 칩을 직접 누르면 챔피언 티어 탭도 최근 30일이다 (%s)' % o['r30_user_champ']['sel'])
    ok(o['pre_link']['sel'] == 'R30', 'S6a (링크 전) 기본은 최근 30일')
    ok(o['link_p']['sel'] == 'ALL' and o['link_then_home']['sel'] == 'ALL', 'S6b #p/ 링크는 전체 기간으로 열고 그 뒤 탭을 옮겨도 전체 기간 (%s → %s)' % (o['link_p']['sel'], o['link_then_home']['sel']))
    ok(o['link_g']['sel'] == 'ALL' and o['link_g_open'] == 'game', 'S6c #g/ 링크(30일 밖 판)도 전체 기간으로 열려 판이 열린다 (%s · %s)' % (o['link_g']['sel'], o['link_g_open']))
    ok(all(o['tongsan'].values()), 'S9 통산인 화면 글자가 최근 30일·전체·최신 패치에서 같다: %s' % {k: v for k, v in o['tongsan'].items()})
    ok(o['gpti0'] == o['gpti1'] and o['gpti0'] > 1, 'S11a 탭을 왕복해도 GPTI_ROWS 총 행수가 그대로 (%s → %s)' % (o['gpti0'], o['gpti1']))
    cg, cr = o['champ_gpti'], o['champ_report']
    ok(cg['sel'] == 'R30' and not cg['meta'] and '최신 패치' not in cg['note'] and cr['sel'] == 'R30' and not cr['meta'], 'S11b 챔피언 티어 → 성향유형·리포트(일찍 return 하는 화면)도 최근 30일로 돌아오고 안내가 사라진다 (%s · %s)' % (cg['sel'], cr['sel']))
    f = o['fell']
    ok(f['sel'] == 'ALL' and not f['user'] and '최근 30일에는 기록이 없어' in o['fell_txt'] and '전체 기간(' not in o['fell_txt'].split('기록이 없어')[0][-30:], 'S11c 30일 0판 선수를 열면 전체 기간으로 풀리고 문구는 「최근 30일에는 …」 (sel=%s user=%s)' % (f['sel'], f['user']))
    ok(o['a32_first']['sel'] == 'ALL' and o['a32_first']['auto'] and '검색한 선수가' in o['a32_first']['note'], 'A32a 0판 선수를 열면 자동 전체 기간 + 안내 (%s)' % o['a32_first'])
    ok(o['a32_next']['sel'] == 'R30' and not o['a32_next']['auto'] and '검색한 선수가' not in o['a32_next']['note'], 'A32b 곧바로 다른 선수를 열면 최근 30일로 돌아오고 거짓 안내가 사라진다 (%s)' % o['a32_next'])
    ok(o['fell_champ']['sel'] == '16.20' and o['fell_home']['sel'] == 'R30', 'S11d 자동 전환은 직접 고른 게 아니다 — 그 뒤 티어 탭은 최신 패치 · 홈은 최근 30일 (%s · %s)' % (o['fell_champ']['sel'], o['fell_home']['sel']))
    bad = [x for x in o['overflow'] if x['sw'] > x['cw'] + 1]
    ok(not bad, 'S10a 폰 360 가로 넘침 0 %s' % ([(x['route'], x['sw'], x['cw']) for x in o['overflow']]))
    ok(not res['meta']['log']['pageerror'], 'S10b 페이지 오류 0 %s' % res['meta']['log']['pageerror'][:3])

    # S8 묵은 스냅샷 — 마지막 기록일이 3달 전
    old_last = dt.date(2026, 7, 11)
    xl2 = os.path.join(tmp, 'fakeB.xlsx'); make_xlsx(xl2, old_last)
    E2 = expect(old_last)

    async def after2(pg):
        o = {'s0': await pg.evaluate(STATE)}
        o['view'] = await pg.evaluate("()=>document.querySelector('#view').innerText.length")
        await pg.evaluate(GO, ['player', _nm(1)]); o['ring'] = await pg.evaluate("()=>{const e=document.querySelector('.side-scope');return e?e.textContent.replace(/\\s+/g,' ').trim():null}")
        return o
    r2 = await R.replay(src, xlsx=xl2, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True, now=NOW, after=after2, timeout_s=300)
    p = r2['after']
    ok(p['s0']['sel'] == 'R30' and p['s0']['games'] == len(E2['in30']) and p['s0']['games'] > 0 and p['s0']['players'] > 0,
       'S8a 3달 묵은 스냅샷에서도 최근 30일이 비지 않는다 (기준일 %s · %d판 · %d명)' % (p['s0']['r30'][1], p['s0']['games'], p['s0']['players']))
    ok('마지막 내전이 92일 전' in p['s0']['note'], 'S8b 기준일을 마지막 기록일로 잡았다는 안내가 나온다 (%s)' % p['s0']['note'])
    ok(p['ring'] and p['ring'].startswith('최근 30일 · 통산'), 'S8c 프로필 한 줄도 정상 (%s)' % p['ring'])
    ok(not r2['meta']['log']['pageerror'], 'S8d 페이지 오류 0')


# ---------------------------------------------------------------- G 시험(스냅샷)
def base_src_dir(arg, tmp):
    """고치기 전 index.html 이 든 폴더(data/ 등은 저장소 것을 이어 붙인다). 못 만들면 None."""
    out = os.path.join(tmp, 'base'); os.makedirs(out, exist_ok=True)
    try:
        if arg:
            txt = open(arg, encoding='utf-8').read()
        else:
            txt = subprocess.check_output(['git', '-C', REPO, 'show', '%s:index.html' % BASE_COMMIT], stderr=subprocess.DEVNULL).decode('utf-8')
    except Exception:
        return None
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(txt)
    for f in os.listdir(REPO):
        if f in ('.git', 'index.html'): continue
        try: os.symlink(os.path.join(REPO, f), os.path.join(out, f))
        except OSError: pass
    return os.path.join(out, 'index.html')


async def snap_run(src, gviz_dir, xlsx, cats=('rift',), width=430):
    items = {'routes': TONGSAN_ROUTES}
    async def after(pg):
        o = {'state': await pg.evaluate(STATE), 'act': await pg.evaluate(ACT), 'raw': await pg.evaluate(RAWCOUNT)}
        # 챔피언 표기 통일(build 의 「자르반4세/자르반 4세」 합치기)은 지금 범위의 판만 골라 원본 행의 이름을 바꾼다 — 기존 동작이라
        # 범위가 바뀌면 통산 화면에도 표기 합쳐짐이 새어 든다. 범위 변경 자체의 영향만 보려고 두 판 모두 전체 기간으로 한 번 짜서 표기를 같게 만든 뒤 기본으로 돌아온다.
        await pg.evaluate("()=>{PATCH_USER=true;PATCH_SEL='ALL';build();PATCH_SEL=null;PATCH_USER=false;build();renderPatchbar();}")
        o['h1'] = await pg.evaluate(HASHES, items)
        await pg.wait_for_timeout(1500)
        o['h2'] = await pg.evaluate(HASHES, items)
        return o
    return await R.replay(src, xlsx=xlsx, gviz_dir=gviz_dir, out=None, shots=False, cats=cats, viewport=(width, 780), quiet=True, now=NOW, after=after, timeout_s=600)


async def run_snapshot(src, gviz_dir, xlsx, base_arg, tmp):
    print('\n[G] 실제 시트 스냅샷 재생 (%s)' % (gviz_dir or xlsx))
    new = await snap_run(src, gviz_dir, xlsx)
    a = new['after']
    st, rc, act = a['state'], a['raw'], a['act']
    ok(st['sel'] == 'R30' and st['label'] == '최근 30일', 'G1a 기본 범위 최근 30일 (sel=%s)' % st['sel'])
    ok(st['games'] == rc['games30'] and st['r30'] == [rc['from'], rc['last']], 'G1b 기본 화면 판수 %d == 시트에서 다시 센 %d (%s~%s)' % (st['games'], rc['games30'], rc['from'], rc['last']))
    ok(act['act5'] > 0 and act['missing'] == 0 and act['lt5'] == 0, 'G2a (후) 30일 5판↑ 활동 클랜원 %d명 중 홈에서 빠지는 사람 %d · 화면 판수 5판 미만 %d' % (act['act5'], act['missing'], act['lt5']))
        # 기준 커밋과 전/후
    base = base_src_dir(base_arg, tmp)
    if not base:
        print('  SKIP G2b·G3 (기준 커밋 index.html 을 못 구함 — --base-src 로 주세요)')
    else:
        old = await snap_run(base, gviz_dir, xlsx)
        b = old['after']; ba = b['act']
        pct = lambda x, n: (100.0 * x / n) if n else 0.0
        print('  [전] 기준 커밋(기본=최신 패치 %s): 활동 %d명 중 0판이라 빠짐 %d(%.1f%%) · 5판 미만 %d(%.1f%%) · 한 사람 화면 판수 중앙값 %s (30일 %s) · 화면 %d판 %d명' % (
            b['state']['sel'], ba['act5'], ba['missing'], pct(ba['missing'], ba['act5']), ba['lt5'], pct(ba['lt5'], ba['act5']), ba['medShown'], ba['medC30'], ba['games'], ba['players']))
        print('  [후] 이번 변경(기본=최근 30일): 활동 %d명 중 0판이라 빠짐 %d(%.1f%%) · 5판 미만 %d(%.1f%%) · 한 사람 화면 판수 중앙값 %s (30일 %s) · 화면 %d판 %d명' % (
            act['act5'], act['missing'], pct(act['missing'], act['act5']), act['lt5'], pct(act['lt5'], act['act5']), act['medShown'], act['medC30'], act['games'], act['players']))
        ok(ba['act5'] == act['act5'] and ba['missing'] > 0 and act['missing'] < ba['missing'], 'G2b 0판으로 빠지던 활동 클랜원이 줄었다: %d → %d명' % (ba['missing'], act['missing']))
        # 통산 전수 비교 — 각 판에서 두 번 잰 값이 서로 다른(=시간·난수로 흔들리는) 항목은 뺀다
        def stable(run):
            h1, h2 = run['after']['h1'], run['after']['h2']
            return {k: v for k, v in h2.items() if h1.get(k) == v}
        sb, sn = stable(old), stable(new)
        keys = sorted(set(sb) & set(sn))
        noisy = len(set(old['after']['h2']) | set(new['after']['h2'])) - len(keys)
        diff = [k for k in keys if sb[k] != sn[k]]
        total = len(set(old['after']['h2']) | set(new['after']['h2']))
        print('  통산 항목 %d개 중 비교 %d개(두 번 재서 흔들리는 %d개 제외) · 다른 것 %d개' % (total, len(keys), noisy, len(diff)))
        ok(len(keys) > 0.9 * total, 'G3a 비교에서 빠진 항목이 10%% 미만이다 (빠짐 %d/%d)' % (noisy, total))
        ok(not diff, 'G3b 통산인 화면·선수별 통산 칸(내부티어 평가·플레이스타일·기록실·성장·밤 성적·업적·전역일·미토·멸망전·리포트·인간상성 …)이 기준 커밋과 전수 동일 %s' % diff[:8])
        ok(old['after']['h2'].get('playersAll') == new['after']['h2'].get('playersAll') and old['after']['h2'].get('gamesAll') == new['after']['h2'].get('gamesAll'),
           'G3c 통산 맵(PLAYERS_ALL·GAMES_ALL) 크기 동일 (%s · %s)' % (new['after']['h2'].get('playersAll'), new['after']['h2'].get('gamesAll')))
    ok(not new['meta']['log']['pageerror'], 'G0 페이지 오류 0 %s' % new['meta']['log']['pageerror'][:3])
    # 폰 360 + 칼바람
    async def after_phone(pg):
        o = {'ov': []}
        nm = await pg.evaluate("()=>{let b=null,bn=-1;for(const [n,ps] of PLAYERS){const m=ps.length;if(m>bn){bn=m;b=n}}return b}")
        for route, arg in (['home', None], ['player', nm], ['champ', None], ['log', None], ['mastery', None]):
            await pg.evaluate(GO, [route, arg]); o['ov'].append(await pg.evaluate(OVERFLOW, route))
        await pg.evaluate("()=>{loadCategory('aram')}")
        await pg.wait_for_function("()=>{const s=document.querySelector('#status');return !!s&&s.textContent.startsWith('칼바람 —')&&/플레이어 \\d+명/.test(s.textContent)}", timeout=300000)
        await pg.wait_for_timeout(800)
        o['aram'] = await pg.evaluate(STATE); o['aramAct'] = await pg.evaluate(ACT)
        for route, arg in (['home', None], ['champ', None]):
            await pg.evaluate(GO, [route, arg]); o['ov'].append(await pg.evaluate(OVERFLOW, 'aram-' + route))
        o['aramChamp'] = await pg.evaluate(STATE)
        return o
    ph = await R.replay(src, xlsx=xlsx, gviz_dir=gviz_dir, out=None, shots=False, cats=('rift',), viewport=(360, 780), quiet=True, now=NOW, after=after_phone, timeout_s=600)
    p = ph['after']
    bad = [x for x in p['ov'] if x['sw'] > x['cw'] + 1]
    ok(not bad, 'G4 폰 360 가로 넘침 0 %s' % [(x['route'], x['sw'], x['cw']) for x in p['ov']])
    ok(p['aram']['sel'] == 'R30' and p['aramAct']['games'] > 0, 'G5a 칼바람도 기본 최근 30일 (%s · %d판 · 기준일 %s)' % (p['aram']['sel'], p['aramAct']['games'], p['aramAct']['last']))
    ok(p['aramChamp']['sel'] == p['aramChamp']['latest'], 'G5b 칼바람 챔피언 티어 탭도 최신 패치 (%s)' % p['aramChamp']['sel'])
    ok(not ph['meta']['log']['pageerror'], 'G6 페이지 오류 0 %s' % ph['meta']['log']['pageerror'][:3])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(REPO, 'index.html'))
    ap.add_argument('--gviz-dir'); ap.add_argument('--xlsx'); ap.add_argument('--base-src')
    ap.add_argument('--skip-synth', action='store_true')
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    tmp = tempfile.mkdtemp(prefix='p20_')
    if not a.skip_synth:
        await run_synth(src, tmp)
    if a.gviz_dir or a.xlsx:
        await run_snapshot(src, a.gviz_dir, a.xlsx, a.base_src, tmp)
    else:
        print('\nSKIP G (시트 스냅샷이 없다 — --gviz-dir 또는 --xlsx)')
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
