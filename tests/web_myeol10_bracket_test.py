# -*- coding: utf-8 -*-
"""🏆 제10회 멸망전 본선 토너먼트 대시보드 시험 (2026-11-29)
실제 `index.html` 을 열고, 제10회 조편성 상수(MYEOL10_GROUPS)로 가짜 경매 대회를 만들어 확인한다.

  A 예선 — 조별 순위(진출 A 3 · B 3 · C 2)를 대시보드가 조별 표와 같은 값으로 그린다
  B 8강 — 공식 대진표 상수(MYEOL10_KO_PAIRS) 4매치 · 시트 판을 세트로 세어 2-0/2-1 스코어가 자동으로 붙는다
  C 세트 캡 — 3판2선은 2승에서 끝난다(그 뒤 판은 연습으로 보고 스코어를 올리지 않는다)
  D 4강 — 8강 1·2경기 승자 / 3·4경기 승자로 대진이 채워지고, 기록이 없으면 「미정」이다
  E 결승 — 4강 승자가 정해져야 대진이 차고, 5판3선 3승이면 우승 자리가 금색으로 바뀐다
  F 단계 상태 — 시계와 세트 기록으로 완료·진행 중·예정을 가른다
  G 화면 — 폰(390)·PC(1280)에서 가로 넘침 0, 단계 4칸 · 매치 4/2/1칸
  H 일정 배너에 8강이 들어간다(예선 → 8강 → 4강 → 결승)
  I 제9회 본선 화면(4강 토너먼트)은 그대로 · 페이지 오류 0

시험 파일에는 실제 클랜원 닉네임을 적지 않는다 — 팀 이름은 페이지 상수에서 그대로 가져온다.
  python3 tests/web_myeol10_bracket_test.py
"""
import asyncio, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
try:
    import replay as R, synth, openpyxl
except Exception as e:
    print('SKIP  playwright/openpyxl 없음 (%s)' % e); sys.exit(0)

fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

FAKE_JS = """  const POS0=['TOP','JGL','MID','BOT'];
  let SEQ=0;
  const FAKE_TEAMS = MYEOL10_GROUPS.flatMap(G=>G.caps.map(c=>({captain:c,name:'팀 '+c,
    players:POS0.map((ps,k)=>({nickname:'시험선수'+String(SEQ++).padStart(2,'0'),position:ps,tier:'마스터',price:100+k*10,pick:null}))})));
  const FAKE_DET = aucParseDetail({id:30, name:'제 10회 멸망전', mode:'AUCTION', finishedAt:'2026-11-26T10:00:00.000Z', teams:FAKE_TEAMS});
  AUCGG.det.set(30, FAKE_DET);
  AUCGG.list=[{id:30, name:'제 10회 멸망전', mode:'AUCTION', createdAt:'2026-11-20T00:00:00.000Z', finishedAt:FAKE_DET.finishedAt, teamCount:FAKE_TEAMS.length}];
  AUCGG.state='ok'; AUCGG.t=Date.now(); _aucLastTry=Date.now();
"""

JS = r"""(()=>{
""" + FAKE_JS + r"""
  const cfg=aucMyeolCfg(AUCGG.det.get(30));
  const mem=cap=>{ const t=cfg.teams.find(x=>x.cap===cap); return [t.cap,...t.m.map(x=>x[0])]; };
  const POS=['탑','정글','미드','원딜','서폿'];
  const row=(gid,day,n,side,res,i)=>({'게임ID':gid,'날짜':day,'소환사명':n+'#KR1','진영':side,'결과':res,'포지션':POS[i],
    '챔피언':'아리','KDA':'3/2/5','점수':'20','패치버전':'v16.20'});
  const mk=(gid,day,w,l)=>{
    const rows=[];
    mem(w).forEach((n,i)=>rows.push(row(gid,day,n,'블루팀','승리',i)));
    mem(l).forEach((n,i)=>rows.push(row(gid,day,n,'레드팀','패배',i)));
    return rows;
  };
  // '가짜 판' 만들기 — games 에 쌓고 GAMES_ALL 을 다시 만든다
  let SEQ2=0; const games=[];
  const add=(day,w,l)=>{ const gid='#b'+(++SEQ2); games.push([gid,{rows:mk(gid,day,w,l)}]); return gid; };
  const apply=()=>{ GAMES_ALL=new Map(games); DATA_SEQ++; _MYEOL_MEMO={seq:-1}; };

  // ── ① 예선: 조 안 6경기(인덱스 낮은 팀 승) → 3-0 / 2-1 / 1-2 / 0-3
  MYEOL10_GROUPS.forEach(G=>{ const c=G.caps; let n=0;
    for(const [i,j] of [[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]]) add('2026-11-28 19:'+String(10+(n++)*8).padStart(2,'0'), c[i], c[j]); });
  apply();
  const stat=ts=>{ const s=myeol10Stages(cfg, +new Date(ts)).st; return s.pre+'/'+s.qf+'/'+s.sf+'/'+s.fin; };
  const S0={before:stat('2026-11-27T12:00:00+09:00'), pre:stat('2026-11-28T20:00:00+09:00'), qfSoon:stat('2026-11-28T21:00:00+09:00')};
  // ── ② 8강: 대진표 4매치 · 첫 팀 2승 + (일부러) 3판째 패배 1판 → 스코어는 2-0 이어야 한다
  MYEOL10_KO_PAIRS.qf.forEach(([a,b],i)=>{
    add('2026-11-28 22:'+String(20+i*5).padStart(2,'0'), a, b);
    add('2026-11-28 22:'+String(40+i*5).padStart(2,'0'), a, b);
    add('2026-11-28 23:0'+i, b, a);   // 이미 끝난 시리즈 뒤 판 = 연습
  });
  apply();
  S0.qf=stat('2026-11-28T23:30:00+09:00');

  const G=myeol10Stages(cfg, +new Date('2026-11-28T23:30:00+09:00'));
  const gr=G.GD.map(D=>({g:D.g, adv:D.adv, rows:D.names.map((n,i)=>({n, w:D.rec[i].w, l:D.rec[i].l, r:D.rk.get(D.nks[i])})).sort((x,y)=>x.r-y.r)}));
  const qf=G.qf.map(q=>({a:q.a,b:q.b,wa:q.ser&&q.ser.wa,wb:q.ser&&q.ser.wb,sets:q.ser?q.ser.sets.length:0,win:q.ser?q.ser.win:null}));
  const sf=G.sf.map(s=>({a:s.a,b:s.b,wa:s.ser&&s.ser.wa,wb:s.ser&&s.ser.wb,win:s.ser?s.ser.win:null}));
  const fin={a:G.fin.a,b:G.fin.b,win:G.fin.ser?G.fin.ser.win:null};
  const html=myeol10BracketHtml(cfg, +new Date('2026-11-28T23:30:00+09:00'));
  const dom=document.createElement('div'); dom.innerHTML=html;

  // ── ③ 4강: 한 경기만 2-0, 다른 경기는 1-0 → 결승 대진은 아직 미정
  add('2026-11-29 16:20', sf[0].a, sf[0].b);
  add('2026-11-29 16:35', sf[0].a, sf[0].b);
  add('2026-11-29 17:00', sf[1].a, sf[1].b);
  apply();
  const G2=myeol10Stages(cfg, +new Date('2026-11-29T17:30:00+09:00'));
  const sf2=G2.sf.map(s=>({a:s.a,b:s.b,wa:s.ser&&s.ser.wa,wb:s.ser&&s.ser.wb,win:s.ser?s.ser.win:null}));
  const fin2={a:G2.fin.a,b:G2.fin.b};
  const st2=G2.st;

  // ── ④ 결승: 남은 4강 경기를 마저 잡고 결승 5판3선 3승
  add('2026-11-29 17:20', sf[1].b, sf[1].a);
  add('2026-11-29 17:40', sf[1].b, sf[1].a);
  apply();
  const G3=myeol10Stages(cfg, +new Date('2026-11-29T18:10:00+09:00'));
  const finTeams={a:G3.fin.a,b:G3.fin.b};
  const S1={sf:stat('2026-11-29T18:00:00+09:00')};   // 결승 판을 잡기 전 상태 — 4강까지 끝, 결승 예정
  const fw=G3.fin.a, fl=G3.fin.b;
  add('2026-11-29 19:20', fw, fl); add('2026-11-29 19:40', fl, fw); add('2026-11-29 20:00', fw, fl); add('2026-11-29 20:20', fw, fl);
  apply();
  const G4=myeol10Stages(cfg, +new Date('2026-11-29T20:40:00+09:00'));
  const fin4={a:G4.fin.a,b:G4.fin.b,wa:G4.fin.ser&&G4.fin.ser.wa,wb:G4.fin.ser&&G4.fin.ser.wb,win:G4.fin.ser?G4.fin.ser.win:null};
  const html4=myeol10BracketHtml(cfg, +new Date('2026-11-29T20:40:00+09:00'));
  const d4=document.createElement('div'); d4.innerHTML=html4;

  // ── ⑤ 단계 상태: 시계별(각 단계 데이터가 그 상태일 때 찍은 값 + 지금 데이터로 본 시계별 값)
  const st={before:S0.before, pre:S0.pre, qfSoon:S0.qfSoon, qf:S0.qf, sf:S1.sf, fin:stat('2026-11-29T20:40:00+09:00')};

  return {cfg:{label:cfg.label,teams:cfg.teams.length}, gr, qf, sf, sf2, st2, fin, fin2, finTeams, fin4,
    stat:st,
    dom:{stages:dom.querySelectorAll('.m10-st').length, grp:dom.querySelectorAll('.m10-grp').length,
      m:dom.querySelectorAll('.m10-m').length, cup:dom.querySelector('.m10-cup').className,
      qfTxt:dom.querySelectorAll('.m10-st')[1].innerText.replace(/\s+/g,' '),
      sfTxt:dom.querySelectorAll('.m10-st')[2].innerText.replace(/\s+/g,' '),
      finTxt:dom.querySelectorAll('.m10-st')[3].innerText.replace(/\s+/g,' '),
      flow:dom.querySelector('.m10-flow').innerText.replace(/\s+/g,' ')},
    done:{cup:d4.querySelector('.m10-cup').className, txt:d4.querySelectorAll('.m10-st')[3].innerText.replace(/\s+/g,' ')},
    sch:myeolScheduleHtml().replace(/<[^>]+>/g,' ').replace(/\s+/g,' '),
    sch8:myeolScheduleHtml().includes('8강'),
  };
})()"""

RENDER_JS = r"""(async()=>{
""" + FAKE_JS + r"""
  const cfg=aucMyeolCfg(AUCGG.det.get(30));
  const mem=cap=>{ const t=cfg.teams.find(x=>x.cap===cap); return [t.cap,...t.m.map(x=>x[0])]; };
  const POS=['탑','정글','미드','원딜','서폿'];
  const row=(gid,day,n,side,res,i)=>({'게임ID':gid,'날짜':day,'소환사명':n+'#KR1','진영':side,'결과':res,'포지션':POS[i],'챔피언':'아리','KDA':'3/2/5','점수':'20'});
  const mk=(gid,day,w,l)=>{ const rows=[];
    mem(w).forEach((n,i)=>rows.push(row(gid,day,n,'블루팀','승리',i)));
    mem(l).forEach((n,i)=>rows.push(row(gid,day,n,'레드팀','패배',i))); return rows; };
  let S=0; const games=[];
  const add=(d,w,l)=>{ const g='#c'+(++S); games.push([g,{rows:mk(g,d,w,l)}]); };
  MYEOL10_GROUPS.forEach(G=>{ const c=G.caps; let n=0;
    for(const [i,j] of [[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]]) add('2026-11-28 19:'+String(10+(n++)*8).padStart(2,'0'), c[i], c[j]); });
  MYEOL10_KO_PAIRS.qf.forEach(([a,b],i)=>{ add('2026-11-28 22:'+String(20+i*5).padStart(2,'0'), a, b); add('2026-11-28 22:'+String(40+i*5).padStart(2,'0'), a, b); });
  GAMES_ALL=new Map(games); DATA_SEQ++; _MYEOL_MEMO={seq:-1};

  MYEOL_ED=10; MYEOL_VIEW='main'; go('myeol'); renderMyeol();
  const out={};
  const settle=()=>new Promise(r=>setTimeout(r,150));
  await settle();
  const stages=()=>[...document.querySelectorAll('.m10-st')];
  out.boardN=document.querySelectorAll('.m10').length;
  out.stageN=stages().length;
  out.mat=stages().map(s=>s.querySelectorAll('.m10-m').length);
  out.winRows=stages().map(s=>s.querySelectorAll('.m10-t.win').length);
  out.foldOpen=(document.querySelector('.mx-fold[open] .mx-tt b')||{}).textContent||'';
  out.head=(document.querySelector('.mx-fold[open] .mx-tt')||{}).textContent||'';
  // 제9회 화면은 그대로
  setMyeolEd(9); MYEOL_VIEW='main'; renderMyeol(); await settle();
  out.old9={bracket:document.querySelectorAll('.bk-m').length, champ:document.querySelectorAll('.ch-hero').length,
    txt:(view().innerText||'').replace(/\s+/g,' ').slice(0,120)};
  out.m10on9=document.querySelectorAll('.m10').length;
  return out;
})()"""

MEASURE_JS = r"""(()=>{
  MYEOL_ED=10; MYEOL_VIEW='main'; renderMyeol();
  const m10=document.querySelector('.m10');
  const wide=[];
  if(m10) m10.querySelectorAll('*').forEach(e=>{ const r=e.getBoundingClientRect(); if(r.width&&r.right>window.innerWidth+1) wide.push(e.className||e.tagName); });
  return {sw:document.documentElement.scrollWidth, iw:window.innerWidth, over:wide.slice(0,4)};
})()"""


async def after(pg):
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    async def h(route):
        await route.fulfill(status=200, content_type='application/json',
                            headers={'access-control-allow-origin': '*'}, body=json.dumps({'tournaments': []}))
    await pg.route('**/auc-gg.up.railway.app/**', h)
    o = await pg.evaluate(JS)
    o['render'] = await pg.evaluate(RENDER_JS)
    sizes = {}
    for tag, (w, hh) in (('phone', (390, 844)), ('narrow', (360, 780)), ('pc', (1280, 1000))):
        await pg.set_viewport_size({'width': w, 'height': hh})
        await pg.wait_for_timeout(250)
        sizes[tag] = await pg.evaluate(MEASURE_JS)
    o['render']['sizes'] = sizes
    o['errs'] = errs[:3]
    return o


async def main():
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); wb = openpyxl.Workbook(); wb.remove(wb.active)
        for n, rs in synth.build_tabs().items():
            ws = wb.create_sheet(n)
            for r in rs: ws.append(r)
        wb.save(x)
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, out=td, now='2026-11-28T23:30:00',
                             shots=False, viewport=(430, 960), after=after, quiet=True, timeout_s=300)
    o = res['after'] or {}
    cfg = o.get('cfg') or {}
    print('  cfg:', cfg)
    print('  조별:', json.dumps(o.get('gr'), ensure_ascii=False)[:400])
    print('  8강:', json.dumps(o.get('qf'), ensure_ascii=False)[:400])
    print('  상태:', o.get('stat'))

    ok(cfg.get('label') == '제10회 멸망전' and cfg.get('teams') == 12, '준비: 가짜 제10회 대회 12팀')

    # A 예선
    gr = o.get('gr') or []
    ok(len(gr) == 3 and [g['adv'] for g in gr] == [3, 3, 2], 'A 진출 팀 수 A3 · B3 · C2 %s' % [g['adv'] for g in gr])
    ok(all([r['w'] for r in g['rows']] == [3, 2, 1, 0] and [r['r'] for r in g['rows']] == [1, 2, 3, 4] for g in gr),
       'A 조별 순위가 3-0 / 2-1 / 1-2 / 0-3 순서로 나온다 %s' % [[(r['w'], r['l']) for r in g['rows']] for g in gr])

    # B 8강
    qf = o.get('qf') or []
    ok(len(qf) == 4, 'B 8강 4매치')
    ok(all(x['wa'] == 2 and x['wb'] == 0 for x in qf), 'B 8강 스코어가 판 기록에서 2-0 으로 붙는다 %s' % [(x['wa'], x['wb']) for x in qf])
    ok(all(x['sets'] == 2 for x in qf), 'C 3판2선은 2승에서 끝 — 뒤에 붙은 연습 판은 세지 않는다 %s' % [x['sets'] for x in qf])
    ok(all(x['win'] == x['a'] for x in qf), 'B 8강 승자는 2승 쪽 %s' % [x['win'] for x in qf])

    # D 4강
    sf = o.get('sf') or []
    ok(sf and sf[0]['a'] == qf[0]['a'] and sf[0]['b'] == qf[1]['a'] and sf[1]['a'] == qf[2]['a'] and sf[1]['b'] == qf[3]['a'],
       'D 4강 = 8강 1·2경기 승자 / 3·4경기 승자 %s' % [(x['a'], x['b']) for x in sf])
    ok((o.get('fin') or {}).get('a') is None and (o.get('fin') or {}).get('b') is None, 'D 4강 전엔 4강 대진이 「미정」')
    st2 = o.get('st2') or {}
    ok(st2.get('sf') == 'live', 'F 11/29 17:30 — 4강 진행 중 (%s)' % st2.get('sf'))
    ok(st2.get('fin') == 'soon', 'F 11/29 17:30 — 결승 예정 (%s)' % st2.get('fin'))
    sf2 = o.get('sf2') or []
    ok(sf2 and sf2[0]['win'] == sf2[0]['a'] and sf2[1]['win'] is None, 'E 4강 1경기만 끝나면 그 승자만 정해진다 %s' % [x['win'] for x in sf2])
    ok((o.get('fin2') or {}).get('a') == sf2[0]['a'] and (o.get('fin2') or {}).get('b') is None, 'E 4강 반대편이 비면 결승 한 자리는 비워 둔다 %s' % (o.get('fin2'),))

    # E 결승
    ft = o.get('finTeams') or {}
    ok(ft.get('a') and ft.get('b') and ft.get('a') != ft.get('b'), 'E 4강이 다 끝나면 결승 대진이 찬다 %s' % (ft,))
    fin4 = o.get('fin4') or {}
    ok(fin4.get('wa') == 3 and fin4.get('win') == fin4.get('a'), 'E 결승 5판3선 — 3승이면 우승 확정 %s' % (fin4,))
    done = o.get('done') or {}
    ok('win' in (done.get('cup') or '') and '우승' in (done.get('txt') or ''), 'E 우승 자리가 금색(win)으로 바뀐다 %s' % done.get('cup'))

    # F 단계 상태
    stat = o.get('stat') or {}
    ok(stat.get('before') == 'soon/soon/soon/soon', 'F 11/27 — 네 단계 모두 예정 (%s)' % stat.get('before'))
    ok(stat.get('pre') == 'done/soon/soon/soon', 'F 11/28 20시 — 예선 완료 · 8강 예정 (%s)' % stat.get('pre'))
    ok(stat.get('qf') == 'done/done/soon/soon', 'F 11/28 23시 — 예선·8강 완료 (%s)' % stat.get('qf'))
    ok(stat.get('sf') == 'done/done/done/soon', 'F 11/29 18시 — 4강까지 끝 · 결승 예정 (%s)' % stat.get('sf'))
    ok(stat.get('fin') == 'done/done/done/done', 'F 결승까지 끝나면 네 단계 완료 (%s)' % stat.get('fin'))

    # G 화면
    dom = o.get('dom') or {}
    ok(dom.get('stages') == 4 and dom.get('grp') == 3 and dom.get('m') == 7, 'G 대시보드 = 단계 4칸 · 조 3칸 · 매치 7개 %s' % {k: dom.get(k) for k in ('stages', 'grp', 'm')})
    ok('지 르' in (dom.get('qfTxt') or '') and '2' in (dom.get('qfTxt') or ''), 'G 8강 칸에 팀·스코어가 찍힌다 %s' % (dom.get('qfTxt') or '')[:80])
    ok('예선' in (dom.get('flow') or '') and '결승' in (dom.get('flow') or ''), 'G 단계 흐름에 예선~결승이 다 있다 %s' % (dom.get('flow') or '')[:80])
    r = o.get('render') or {}
    ok(r.get('stageN') == 4 and r.get('mat') == [0, 4, 2, 1], 'G 실제 화면: 단계 4칸 · 매치 4/2/1 %s' % (r.get('mat'),))
    ok((r.get('foldOpen') or '') == '본선 토너먼트', 'G 본선 탭 첫 섹션이 「본선 토너먼트」로 펼쳐 있다 %s' % r.get('foldOpen'))
    sizes = r.get('sizes') or {}
    for tag in ('phone', 'narrow', 'pc'):
        m = sizes.get(tag) or {}
        ok(m and m.get('sw', 10 ** 6) <= m.get('iw', 0) and not m.get('over'),
           'G %s 가로 넘침 0 (%s)' % (tag, m))

    # H 일정 배너
    ok(o.get('sch8') is True and '8강' in (o.get('sch') or ''), 'H 일정 배너에 8강이 들어간다')
    ok('4강' in (o.get('sch') or '') and '결승' in (o.get('sch') or ''), 'H 4강·결승도 그대로')

    # I 제9회
    old = r.get('old9') or {}
    ok(old.get('bracket') == 3 and old.get('champ') == 1, 'I 제9회 본선 화면(결승·4강 2경기·우승 배너)은 그대로 %s' % {k: old.get(k) for k in ('bracket', 'champ')})
    ok(r.get('m10on9') == 0, 'I 제9회 화면엔 제10회 대시보드가 없다')
    ok(not o.get('errs') and not (r.get('errs') if isinstance(r.get('errs'), list) else []), 'I 페이지 오류 0 %s' % ((o.get('errs') or [])[:1],))

    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
