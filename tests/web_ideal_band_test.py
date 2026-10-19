# -*- coding: utf-8 -*-
"""⚖️ 이상형월드컵 대진 시험 (사장님 2026-10-19 「내부티어가 아니라 비슷한 전투력으로 매칭 ±1.0」)
index.html 의 idealBracket 만 떼어 node 로 돌린다.
  A. 풀이 넉넉하면 8명, 전원이 어떤 한 사람(기준)과 전투력 ±1.0 안   B. 기준 근처가 4명 미만인 사람은 기준으로 안 잡힌다
  C. 어느 기준도 안 되면 기준에 가장 가까운 4명(그래도 열린다)   D. 4명 미만 풀은 null   E. 중복 없음 · 입력을 바꾸지 않음
  F. 반복해서 돌리면 여러 사람이 기준이 된다(매번 같은 대진이 아니다)"""
import os, re, subprocess, sys, json
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
def grab(a, b):
    i = src.index(a); j = src.index(b, i); return src[i:j]
js = ('const IDEAL_MIN_POOL=4, IDEAL_FULL=8;' + re.search(r'const IDEAL_BAND=[^;]+;', src).group(0) + '\n'
      + grab('function idealShuffle', 'function idealPoolAt') + grab('function idealBracket', 'function idealPick'))
test = js + r"""
const mk=(pws)=>pws.map((p,i)=>({name:'p'+i,pw:p}));
const out={};
const rich=mk([4,4.15,4.3,4.45,4.6,4.75,4.9,5.05,5.2,5.35,5.5,9,9.2]);
let bad=0,sizes={},anchors=new Set(),before=JSON.stringify(rich);
for(let i=0;i<400;i++){const b=idealBracket(rich);sizes[b.length]=(sizes[b.length]||0)+1;
  if(new Set(b.map(x=>x.name)).size!==b.length)bad++;
  const ok=b.some(a=>b.every(c=>Math.abs(c.pw-a.pw)<=1.0+1e-9)); if(!ok)bad++;
  b.forEach(x=>anchors.add(x.name));}
out.A={bad,sizes,anchors:anchors.size,mut:JSON.stringify(rich)!==before};
// B: 9.0/9.2 는 근처가 1명뿐 → 기준이 돼도 4명이 안 되므로 대진에 섞여도 항상 낮은 쪽과 안 묶인다
let far=0;for(let i=0;i<400;i++){const b=idealBracket(rich);const hi=b.filter(x=>x.pw>=9),lo=b.filter(x=>x.pw<8);if(hi.length&&lo.length)far++;}
out.B=far;
// C: 서로 멀리 떨어진 4명 → 그래도 열린다
const sp=mk([1,4,7,10]);const c=idealBracket(sp);out.C=c&&c.length;
out.D=[idealBracket(mk([1,2,3])),idealBracket([])];
// 5~7명: 4강
const m=mk([5,5.2,5.4,5.6,5.8,6,6.2]);out.E=idealBracket(m).length;
// 8명 이상 가까운 사람이 있으면 4강보다 8강을 우선
const two=mk([1,1.1,1.2,1.3,1.4,1.5,6,6.1,6.2,6.3,6.4,6.5,6.6,6.7,6.8]);let e8=0;for(let i=0;i<200;i++)if(idealBracket(two).length===8)e8++;out.G=e8;
console.log(JSON.stringify(out));
"""
r = subprocess.run(['node', '-e', test], capture_output=True, text=True)
if r.returncode: print(r.stderr[-800:]); sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1]); fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
ok(o['A']['bad'] == 0 and set(o['A']['sizes']) == {'8'}, 'A 넉넉한 풀은 항상 8명 · 중복 없음 · 전원이 한 기준과 ±1.0 안 %s' % o['A'])
ok(not o['A']['mut'], 'E 입력 배열을 바꾸지 않는다')
ok(o['A']['anchors'] >= 8, 'F 여러 사람이 대진에 오른다(매번 같은 대진이 아니다) — %d명' % o['A']['anchors'])
ok(o['B'] == 0, 'B 전투력이 크게 떨어진 사람(9점대)은 낮은 쪽과 한 대진에 안 섞인다 (%d회)' % o['B'])
ok(o['C'] == 4, 'C 서로 먼 4명뿐이어도 가까운 순 4명으로 열린다 (%s)' % o['C'])
ok(o['D'] == [None, None], 'D 4명 미만 풀은 대진을 만들지 않는다 %s' % o['D'])
ok(o['E'] == 4, 'E 5~7명 풀은 4강(4명)으로 짠다 (%s)' % o['E'])
ok(o['G'] == 200, 'G 8강이 가능한 기준이 있으면 항상 8강으로 짠다 (%d/200)' % o['G'])
print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
