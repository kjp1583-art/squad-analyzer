# -*- coding: utf-8 -*-
"""🗓 제10회 멸망전 공지 반영 시험 — 일정 배너 · 본선 자동 전환 · 적정가 안내 문구 (2026-11-27)
실제 `index.html` 을 열고, 제10회 조편성 상수(MYEOL10_GROUPS)로 가짜 경매 대회를 만들어 확인한다.
시험 파일에는 실제 클랜원 닉네임을 적지 않는다 — 팀 이름은 페이지 상수에서 그대로 가져온다.

  A 본선 개막 = 2026-11-28 19:00 KST — 그 전 판은 스크림, 그 뒤 판은 본선 (제10회만)
  B 제9회(8/29 정오) 기준은 그대로 · 다른 회차는 건드리지 않는다
  C 조별 표 = 개막 전 판은 빠지고 개막 뒤 같은 조 팀끼리 붙은 판만 승패로 들어간다
  D 밴픽률 = 스크림/본선 판 수가 개막 시각으로 갈린다
  E 일정 배너 = 예선·4강·결승 + 집중 연습 + 규칙 한 줄, 지금 단계 강조(myeol10Phase)
  F 멸망전 화면: 제10회엔 배너가 보이고 제9회엔 없다
  G 적정가 안내 = 「참가 명단이 공지되면」 대신 경매 완료(참가 인원) 기준 문구
  H 페이지 오류 0

  python3 tests/web_myeol10_stage_test.py
"""
import asyncio, datetime as dt, json, os, re, sys, tempfile

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

# 가짜 경매 대회(JS 안에서 만든다) — 팀·선수 이름은 전부 페이지 상수(MYEOL10_GROUPS)에서 가져온다
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
  const G=MYEOL10_GROUPS[0].caps, win=G[0], lose=G[1];          // A조 두 팀
  const mem=cap=>{ const t=cfg.teams.find(x=>x.cap===cap); return [t.cap,...t.m.map(x=>x[0])]; };   // 5명(팀장+선수 4)
  const POS=['탑','정글','미드','원딜','서폿'];
  const row=(gid,day,n,side,res,i)=>({'게임ID':gid,'날짜':day,'소환사명':n+'#KR1','진영':side,'결과':res,'포지션':POS[i],
    '챔피언':'아리','KDA':'3/2/5','점수':'20','패치버전':'v16.20'});
  const mk=(gid,day,w,l)=>{
    const rows=[];
    mem(w).forEach((n,i)=>rows.push(row(gid,day,n,'블루팀','승리',i)));
    mem(l).forEach((n,i)=>rows.push(row(gid,day,n,'레드팀','패배',i)));
    return rows;
  };
  const g=[...mk('#a1','2026-11-27 21:00',win,lose),    // 경매 뒤·개막 전
           ...mk('#a2','2026-11-28 18:30',lose,win),    // 개막 30분 전
           ...mk('#a3','2026-11-28 20:10',win,lose),    // 개막 뒤
           ...mk('#a4','2026-11-29 16:30',lose,win)];   // 개막 뒤(4강 날)
  GAMES_ALL=new Map(['#a1','#a2','#a3','#a4'].map((id,i)=>[id,{rows:g.slice(i*10,i*10+10)}]));
  DATA_SEQ++; _MYEOL_MEMO={seq:-1};

  const D=s=>new Date(s);
  const cut10=_myeolMainCut(10), cut9=_myeolMainCut(9);
  const st={p1:_myeolStage(10,D('2026-11-28T18:30:00+09:00')), p2:_myeolStage(10,D('2026-11-28T19:00:00+09:00')),
    p3:_myeolStage(10,D('2026-11-29T16:30:00+09:00')),
    p9a:_myeolStage(9,D('2026-08-29T11:00:00+09:00')), p9b:_myeolStage(9,D('2026-08-29T13:00:00+09:00')),
    p11:_myeolStage(11,D('2026-11-29T13:00:00+09:00')), cut11:_myeolMainCut(11)};
  const sc=_myeolScrimsFor(cfg), S=sc?sc.list.slice().sort((a,b)=>a.day-b.day):[];
  const bpS=myeolBpStats(cfg,'scrim'), bpM=myeolBpStats(cfg,'main');
  const grp=myeolGroups10Html(cfg), grpText=grp.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ');
  const ph=o=>({cur:o.cur?o.cur.k:null,next:o.next?o.next.k:null});
  const sch=myeolScheduleHtml();
  const hiM=sch.match(/mx-sch-i next"><b>([^<]+)</);
  return {cfg:{label:cfg.label,teams:cfg.teams.length, from:String(cfg.from)},
    cut:{d10:cut10?cut10.toISOString():null, d9:cut9?cut9.toISOString():null, d11:_myeolMainCut(11)}, st,
    scrims:S.length, wins:S.map(m=>m.win+' 승 vs '+m.lose),
    bp:{scrim:bpS&&bpS.n, main:bpM&&bpM.n, cut:!!(bpM&&bpM.cut)},
    grp:{cards:(grp.match(/class="gt-card"/g)||[]).length, text:grpText.slice(0,400)},
    phase:{a:ph(myeol10Phase(+D('2026-11-27T02:00:00+09:00'))), b:ph(myeol10Phase(+D('2026-11-28T19:30:00+09:00'))), c:ph(myeol10Phase(+D('2026-11-29T18:40:00+09:00')))},
    nowNext:(myeol10Phase().next||{}).k||null, hi:hiM?hiM[1]:null,
    sch:{len:sch.length,
      has:[['예선',/예선/],['8강',/8강/],['4강',/4강/],['결승',/결승/],['11/28(토) 19:00',/11\/28\(토\) 19:00/],['11/28(토) 예선 직후',/11\/28\(토\) 예선 직후/],['11/29(일) 16:00',/11\/29\(일\) 16:00/],
           ['11/29(일) 19:00',/11\/29\(일\) 19:00/],['집중 연습',/집중 연습 11\/22~27/],['규칙',/60명 12팀 · 예외 참가 4명\(참가비 2배·상금 클랜 기부\)/]].filter(x=>x[1].test(sch)).map(x=>x[0])}};
})()"""

RENDER_JS = r"""(()=>{
  MYEOL_ED=null; MYEOL_VIEW='scrim'; go('myeol');
  const out={sch10:document.querySelectorAll('.mx-sch').length,
    schTxt:(document.querySelector('.mx-sch')||{}).innerText||'',
    edTabs:[...document.querySelectorAll('.mx-ed button')].map(b=>b.textContent.trim()).join('|'),
    view:(document.querySelector('.mx-seg button.on')||{}).textContent||''};
  setMyeolEd(9); out.sch9=document.querySelectorAll('.mx-sch').length;
  myeol10Phase; setMyeolEd(10); MYEOL_VIEW='price'; renderMyeol();
  out.price=((document.querySelector('.mx-note div')||{}).textContent||'').replace(/\s+/g,' ');
  const st=document.querySelector('.mx-stat'); out.stat=st?st.innerText.replace(/\s+/g,' '):'';
  out.priceLen=(document.querySelector('.mx-note div')||{textContent:''}).textContent.length;
  return out;
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
    o['errs'] = errs[:3]
    return o


async def main():
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); wb = openpyxl.Workbook(); wb.remove(wb.active)
        for n, rs in synth.build_tabs().items():
            ws = wb.create_sheet(n)
            for r in rs: ws.append(r)
        wb.save(x)
        res = await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, out=td, now='2026-11-27T02:00:00',
                             shots=False, viewport=(430, 960), after=after, quiet=True, timeout_s=300)
    o = res['after'] or {}
    st = o.get('st') or {}
    print('  cfg:', o.get('cfg'), '\n  scrims:', o.get('scrims'), o.get('wins'))
    print('  grp:', (o.get('grp') or {}).get('text', '')[:200])
    print('  price:', ((o.get('render') or {}).get('price') or '')[-160:])
    ok((o.get('cfg') or {}).get('label') == '제10회 멸망전' and (o.get('cfg') or {}).get('teams') == 12,
       '준비: 가짜 제10회 대회 12팀 %s' % o.get('cfg'))
    ok((o.get('cut') or {}).get('d10') == '2026-11-28T10:00:00.000Z', 'A 제10회 본선 개막 = 2026-11-28 19:00 KST %s' % (o.get('cut') or {}).get('d10'))
    ok(st.get('p1') == '스크림', 'A 11/28 18:30 판은 스크림 (%s)' % st.get('p1'))
    ok(st.get('p2') == '본선', 'A 11/28 19:00 판은 본선 (%s)' % st.get('p2'))
    ok(st.get('p3') == '본선', 'A 11/29 16:30 판은 본선 (%s)' % st.get('p3'))
    ok((o.get('cut') or {}).get('d9') == '2026-08-29T03:00:00.000Z', 'B 제9회 개막은 8/29 정오 그대로 %s' % (o.get('cut') or {}).get('d9'))
    ok(st.get('p9a') == '스크림' and st.get('p9b') == '본선', 'B 제9회 판정도 그대로 (%s / %s)' % (st.get('p9a'), st.get('p9b')))
    ok(st.get('cut11') is None and st.get('p11') == '스크림', 'B 다른 회차는 손대지 않는다 (cut=%s)' % st.get('cut11'))
    ok(o.get('scrims') == 4, 'A 팀 대 팀 판 4개를 읽는다 (%s)' % o.get('scrims'))
    bp = o.get('bp') or {}
    ok(bp.get('scrim') == 2 and bp.get('main') == 2, 'D 밴픽률 스크림 2판 · 본선 2판 (%s/%s)' % (bp.get('scrim'), bp.get('main')))
    ok(bp.get('cut') is True, 'D 밴픽률이 본선 개막 시각을 인식한다')
    grp = o.get('grp') or {}
    ok(grp.get('cards') == 3, 'C 조별 표 3칸 (%s)' % grp.get('cards'))
    ok('개막 전' not in (grp.get('text') or ''), 'C 본선 판이 있으면 「개막 전」 문구가 아니다')
    ok('1-1' not in (grp.get('text') or '') and re.search(r'1\s*-\s*0', grp.get('text') or ''),
       'C A조 표에 본선 첫 판만 들어간다(1승0패) — 같은 두 팀 재경기는 세지 않는다 %s' % (grp.get('text') or '')[:120])
    ph = o.get('phase') or {}
    ok(ph.get('a') == {'cur': None, 'next': '예선'}, 'E 11/27 새벽: 다음은 예선 (%s)' % ph.get('a'))
    ok(ph.get('b') == {'cur': '예선', 'next': '8강'}, 'E 11/28 19:30: 예선 진행 · 다음 8강 (%s)' % ph.get('b'))
    ok(ph.get('c') == {'cur': '4강', 'next': '결승'}, 'E 11/29 18:40: 4강 진행 · 다음 결승 (%s)' % ph.get('c'))
    have = (o.get('sch') or {}).get('has') or []
    ok(len(have) == 10, 'E 배너에 일정 4개(예선·8강·4강·결승) · 집중 연습 · 규칙 한 줄이 다 있다 %s' % have)
    ok(o.get('hi') == o.get('nowNext'), 'E 지금 다음 단계를 강조한다 (%s / %s)' % (o.get('hi'), o.get('nowNext')))
    r = o.get('render') or {}
    ok(r.get('sch10') == 1 and '예선' in (r.get('schTxt') or ''), 'F 제10회 화면에 일정 배너가 보인다 (%s)' % r.get('sch10'))
    ok(r.get('sch9') == 0, 'F 제9회 화면엔 배너가 없다 (%s)' % r.get('sch9'))
    ok('확정' in (r.get('price') or '') and '공지되면' not in (r.get('price') or ''),
       'G 적정가 안내가 경매 완료 기준으로 바뀐다 %s' % (r.get('price') or '')[-110:])
    ok(not o.get('errs'), 'H 페이지 오류 0 %s' % (o.get('errs') or [])[:1])
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
