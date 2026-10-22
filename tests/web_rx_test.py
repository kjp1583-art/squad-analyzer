# -*- coding: utf-8 -*-
"""👏 한 번 탭 반응(P-29) 웹 시험 — `python3.13 tests/web_rx_test.py`
  A 버튼 자리: 축하→👏 · 부고→🫡 · 그 밖 알림 없음 · 인물 줄은 👏🫡  B 집계: 같은 사람·같은 칸·같은 이모지는 1회 · 형식 밖 값은 무시
  C 로그인 안 하면 누를 수 없다(로그인으로 보냄) · 로그인하면 먼저 숫자가 오르고 target 뉴스반응:{종료일} 에 「👏|알림0」 한 줄이 저장
  D 같은 칸 두 번 눌러도 저장은 한 번 · 이미 누른 것은 켜진 표시  E 폰 360 가로 넘침 0 · 콘솔 오류 0"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
JS = r"""()=>{
  const W={placeholder:false,week:{from:'2026-10-12',to:'2026-10-18',label:'10월 셋째 주'},headline:'h',grade:{letter:'B',reason:'r'},summary:'s',
    events:[{emoji:'🏟',section:'협곡',title:'t',body:'b',photo:{kind:'none',key:''}}],
    notices:[{kind:'축하',text:'a 7연승'},{kind:'부고',text:'b 별세'},{kind:'알림',text:'공지'}],
    students:[{name:'가나다',emoji:'🧑',line:'x'},{name:'라마바',emoji:'🧑',line:'y'}],awards:[],homework:[],closing:'c',brj:[],issue:5,stats:{},facts:[]};
  const root=document.createElement('div'); root.id='rxroot'; root.style.width='340px'; root.innerHTML=newsPageHtml(W,{}); document.body.appendChild(root);
  const ids=[...root.querySelectorAll('.np-rxb')].map(b=>b.dataset.rx);
  // JSONP 가로채기
  const posts=[]; window.__posts=posts; const oFetch=window.fetch; window.fetch=(u,o)=>{ if(o&&o.body&&String(o.body).includes('target=')) { posts.push(new URLSearchParams(String(o.body)).get('target')+'##'+new URLSearchParams(String(o.body)).get('content')); return Promise.resolve({}); } return oFetch(u,o); };
  window.__cbs=[]; const oAp=document.body.appendChild.bind(document.body); document.body.appendChild=function(n){ if(n&&n.tagName==='SCRIPT'&&decodeURIComponent(n.src).includes('뉴스반응:')){ const m=/callback=([^&]+)/.exec(n.src); window.__cbs.push(m[1]); window.__rxSrc=decodeURIComponent(n.src); return n; } return oAp(n); };
  _npRxLoad('2026-10-18');
  window[window.__cbs[0]]({comments:[{a:'가',c:'👏|알림0'},{a:'가',c:'👏|알림0'},{a:'나',c:'👏|알림0'},{a:'다',c:'🫡|알림1'},{a:'다',c:'👏|인물0'},{a:'x',c:'😡|알림0'},{a:'y',c:'👏|알림99999'},{a:'z',c:'아무말'}]});
  const g=id=>(root.querySelector('.np-rxb[data-rx="'+id+'"]')||{}).textContent;
  return {ids,src:window.__rxSrc,a0:g('알림0|👏'),a1:g('알림1|🫡'),p0:g('인물0|👏'),p1:g('인물1|🫡'),text:root.textContent};
}"""
async def after(pg):
    S = await pg.evaluate(JS)
    ok(sorted(S['ids']) == sorted(['알림0|👏','알림1|🫡','인물0|👏','인물0|🫡','인물1|👏','인물1|🫡']), 'A 축하=👏 · 부고=🫡 · 일반 알림 없음 · 인물 둘 다 — %s' % S['ids'])
    ok('target=%EB%89%B4%EC%8A%A4%EB%B0%98%EC%9D%91' in S['src'].replace('뉴스반응', '%EB%89%B4%EC%8A%A4%EB%B0%98%EC%9D%91') or '뉴스반응:2026-10-18' in S['src'], 'C 읽기 target 은 뉴스반응:{종료일} — %s' % S['src'][-80:])
    ok(S['a0'].strip().endswith('2') and S['a1'].strip().endswith('1') and S['p0'].strip().endswith('1') and S['p1'].strip().endswith('0'), 'B 집계: 같은 사람 중복 1회 · 형식 밖(😡·99999·아무말) 무시 — %r %r %r %r' % (S['a0'], S['a1'], S['p0'], S['p1']))
    r = await pg.evaluate("""()=>{ window.DISCORD_USER_BAK=DISCORD_USER; DISCORD_USER=null; let to=null; const o=window.dcLogin; window.dcLogin=t=>{to=t;}; _npReact('알림0','👏'); window.dcLogin=o; return {to,posts:window.__posts.length}; }""")
    ok(r['to'] == '뉴스:2026-10-18' and r['posts'] == 0, 'C 로그인 안 하면 저장 없이 로그인으로 보낸다(돌아올 곳 = 그 호) — %s' % r)
    r = await pg.evaluate("""()=>{ DISCORD_USER={id:'1',name:'나나',token:'tok',exp:Date.now()+1e7}; const b=document.querySelector('.np-rxb[data-rx="알림0|👏"]'); const before=b.textContent;
      _npReact('알림0','👏'); _npReact('알림0','👏'); _npReact('알림1','🫡'); _npReact('알림1','👍'); _npReact('아무거나9','👏');
      return {before,after:b.textContent,on:b.classList.contains('on'),posts:window.__posts.slice()}; }""")
    ok(r['after'].strip().endswith('3') and r['on'], 'C 누르면 먼저 숫자가 오르고 켜진 표시 — %r → %r' % (r['before'], r['after']))
    ok(r['posts'] == ['뉴스반응:2026-10-18##👏|알림0', '뉴스반응:2026-10-18##🫡|알림1'], 'D 같은 칸 두 번째·형식 밖 이모지·칸 이름은 저장 안 한다 — %s' % r['posts'])
    ov = await pg.evaluate("()=>{const e=document.getElementById('rxroot');return {sw:e.scrollWidth,cw:e.clientWidth}}")
    ok(ov['sw'] <= ov['cw'] + 1, 'E 폭 340 가로 넘침 없음 %s' % ov)
async def main():
    tmp = tempfile.mkdtemp(prefix='rx_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True, viewport=(360, 900), after=after)
    log = res['meta']['log']
    ok(not log['pageerror'], 'E 콘솔 페이지 예외 0 %s' % log['pageerror'][:2])
    ok(not log['console'], 'E 콘솔 오류 0 %s' % log['console'][:2])
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
