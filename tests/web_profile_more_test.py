# -*- coding: utf-8 -*-
"""🧾 프로필 전적 20판씩 더보기 시험 (루프 18회차 A-30) — index.html 의 pmListHtml·morePm 만 떼어 node 로 돌린다.
  A. 처음엔 20장만 그린다(593판 프로필도) · B. 더보기를 누르면 20장씩 늘고 남은 수가 맞다 · C. 다 보이면 버튼이 사라진다
  D. 다른 사람 프로필로 가면 20장부터 다시 · E. 소스에 한도 없는 list.map(matchCard) 가 남지 않았다"""
import re, subprocess, sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
m1 = re.search(r'const PM_STEP=20;.*?\nfunction morePm\(\)\{[^\n]*\n', src, re.S)
FAIL = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ' — ' + str(x)[:300])); 
    if not c: FAIL.append(n)
check('소스에 더보기 코드가 있다', bool(m1))
check('E 한도 없는 전적 렌더가 없다', 'list.map(r=>matchCard(r,name)).join("")' not in src)
check('렌더가 pmListHtml 을 쓴다', '<div id="pmList">${pmListHtml()}</div>' in src and 'if(_pmName!==name){_pmName=name;_pmLimit=PM_STEP;}' in src)
js = r"""
const els={};const document={getElementById:id=>els[id]||(els[id]={innerHTML:''})};
function matchCard(r,n){return '<i>'+r+'</i>'}
""" + m1.group(0) + r"""
const out={};
const cnt=h=>(h.match(/<i>/g)||[]).length, btn=h=>(h.match(/onclick="morePm\(\)"/g)||[]).length;
_pmList=Array.from({length:593},(_,i)=>i);_pmFor='x';_pmName='x';_pmLimit=PM_STEP;
els.pmList={innerHTML:pmListHtml()};
out.a=[cnt(els.pmList.innerHTML),btn(els.pmList.innerHTML),/573판 남음/.test(els.pmList.innerHTML)];
morePm();out.b=[cnt(els.pmList.innerHTML),/553판 남음/.test(els.pmList.innerHTML)];
for(let i=0;i<40;i++)morePm();out.c=[cnt(els.pmList.innerHTML),btn(els.pmList.innerHTML)];
_pmName='y';_pmLimit=PM_STEP;_pmList=Array.from({length:7},(_,i)=>i);out.d=[cnt(pmListHtml()),btn(pmListHtml())];
console.log(JSON.stringify(out));
"""
r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
o = json.loads(r.stdout) if r.returncode == 0 else {}
check('A 처음 20장 · 버튼 1개 · 573판 남음', o.get('a') == [20, 1, True], (o, r.stderr[-200:]))
check('B 더보기 한 번 → 40장 · 553판 남음', o.get('b') == [40, True], o)
check('C 다 보이면 593장 · 버튼 없음', o.get('c') == [593, 0], o)
check('D 적은 판 프로필은 전부 · 버튼 없음', o.get('d') == [7, 0], o)
print('\n전부 통과' if not FAIL else '\n실패 %d건' % len(FAIL)); sys.exit(1 if FAIL else 0)
