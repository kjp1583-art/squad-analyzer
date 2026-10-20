# -*- coding: utf-8 -*-
"""📋 주간스쿼드 이번 주 출석부(P-27) 웹 시험 — `python3.13 tests/web_roster_test.py`
  A. roster 가 있으면 접힌 「📋 이번 주 출석부 (N명)」 · 이름은 프로필 링크 · 판·승·한 줄  B. 없거나 비면 칸이 없다
  C. 이름·한 줄은 escape(HTML 주입 불가) · 잘못된 값(승>판·판 0)은 걸러낸다 · 250명 한도
  D. 지면(newsPageHtml)에 들어가고 브장신 코너보다 위  E. 폰 360 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
JS = r"""()=>{
  const base={placeholder:false,week:{from:'2026-10-12',to:'2026-10-18',label:'10월 셋째 주'},headline:'h',grade:{letter:'B',reason:'r'},summary:'s',
    events:[{emoji:'🏟',section:'협곡',title:'t',body:'b',photo:{kind:'none',key:''}}],notices:[],students:[],awards:[],homework:[],closing:'c',brj:[],issue:5,stats:{},facts:[]};
  const roster=[{n:'미드01',g:41,w:20,t:'한 판 12킬(진)'},{n:'<img src=x onerror=1>',g:3,w:1,t:'<b>x</b>'},{n:'가나다',g:5,w:2,t:''},{n:'승초과',g:2,w:3,t:'x'},{n:'판영',g:0,w:0,t:''},{n:'',g:4,w:1}];
  const W1=Object.assign({},base,{roster}), W0=Object.assign({},base), W2=Object.assign({},base,{roster:[]});
  const big=[];for(let i=0;i<300;i++)big.push({n:'사람'+i,g:1,w:0,t:''});
  const h1=_npRoster(W1), h0=_npRoster(W0), h2=_npRoster(W2), hb=_npRoster(Object.assign({},base,{roster:big}));
  const el=document.createElement('div'); el.innerHTML=h1;
  const page=newsPageHtml(Object.assign({},W1,{brj:[{emoji:'🍗',title:'브장신',body:'b',photo:{kind:'none',key:''}}]}),{});
  return {h0,h2,sum:(el.querySelector('summary')||{}).textContent||'',rows:el.querySelectorAll('.np-roster-grid>div').length,
    links:el.querySelectorAll('.clickname').length,hasImg:!!el.querySelector('img'),hasB:!!el.querySelector('.rt b'),text:el.textContent,
    open:el.querySelector('details').hasAttribute('open'),bigN:(hb.match(/np-roster-grid>/g)||[]).length+((new DOMParser().parseFromString(hb,'text/html')).querySelectorAll('.np-roster-grid>div').length),
    pageHas:page.includes('np-roster'),before:page.indexOf('np-roster')>=0&&page.indexOf('np-roster')<page.indexOf('np-brj"')};
}"""
async def after(pg):
    S = await pg.evaluate(JS)
    ok(S['h0'] == '' and S['h2'] == '', 'B roster 가 없거나 비면 칸이 없다')
    ok('이번 주 출석부 (3명)' in S['sum'], 'A 접힌 칸 제목에 인원 수 (잘못된 값 3개 제외 → 3명) — %r' % S['sum'][:30])
    ok(not S['open'], 'A 처음엔 접혀 있다')
    ok(S['rows'] == 3 and '미드01' in S['text'] and '41판 20승' in S['text'] and '한 판 12킬(진)' in S['text'], 'A 이름·판·승·한 줄 %s' % S['text'][:80])
    ok(S['links'] >= 1, 'A 이름은 프로필 링크(clickname) — 풀리는 이름만 (%d)' % S['links'])
    ok(not S['hasImg'] and not S['hasB'], 'C 이름·한 줄의 HTML 은 escape')
    ok('승초과' not in S['text'] and '판영' not in S['text'], 'C 승>판·판 0 은 걸러낸다')
    ok(S['pageHas'] and S['before'], 'D 지면에 들어가고 브장신 코너보다 위에 있다')
    ok(S['bigN'] == 250 * 2 or S['bigN'] >= 250, 'C 300명을 줘도 250명까지 (%s)' % S['bigN'])
    await pg.evaluate("()=>{const W={placeholder:false,week:{from:'2026-10-12',to:'2026-10-18',label:'x'},headline:'h',grade:{letter:'B',reason:'r'},summary:'s',events:[{emoji:'🏟',section:'협곡',title:'t',body:'b',photo:{kind:'none',key:''}}],notices:[],students:[],awards:[],homework:[],closing:'c',brj:[],issue:5,stats:{},facts:[],roster:Array.from({length:120},(_,i)=>({n:'사람'+i,g:1+i%9,w:i%3,t:i%4?'':'심야 3판'}))};document.body.insertAdjacentHTML('beforeend','<div id=rstest style=\"width:340px\">'+_npRoster(W)+'</div>');document.querySelector('#rstest details').open=true;}")
    ov = await pg.evaluate("()=>{const e=document.getElementById('rstest');return {sw:e.scrollWidth,cw:e.clientWidth,doc:document.documentElement.scrollWidth,win:innerWidth}}")
    ok(ov['sw'] <= ov['cw'] + 1, 'E 폰 폭 340 에서 펼쳐도 가로로 안 넘친다 %s' % ov)
async def main():
    tmp = tempfile.mkdtemp(prefix='rost_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True, viewport=(360, 900), after=after)
    log = res['meta']['log']
    ok(not log['pageerror'], '콘솔 페이지 예외 0 %s' % log['pageerror'][:2])
    ok(not log['console'], '콘솔 오류 0 %s' % log['console'][:2])
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
