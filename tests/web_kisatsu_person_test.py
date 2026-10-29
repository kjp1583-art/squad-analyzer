# -*- coding: utf-8 -*-
"""⚔ 귀살대 사람 단위 시험 — `python3.13 tests/web_kisatsu_person_test.py`  (2026-10-29 「카무사리=귤갓 닉변 동일인물인데 귀살대에 중복」)
  A personKeyOf: 본계·부계·닉변 사슬이 한 키 · 남은 서로 다른 키
  B 귀살대(KISATSU) 안에 같은 사람이 두 번 없다 · 상현(사람 단위)과 겹치지 않는다
  C 귀살대 대표 닉이 그 사람이 쓴 닉 중 하나다"""
import asyncio, os, sys, tempfile, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R
import web_ideal_test as WI
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
JS = """(()=>{const top=[...ASSESSMENTS.entries()].filter(([n,a])=>a&&/^상현/.test(a.title||'')).map(([n])=>n);
 const topP=new Set(top.map(personKeyOf));
 const cnt={};KISATSU.forEach(k=>{const p=personKeyOf(k.name);cnt[p]=(cnt[p]||0)+1});
 return {a:personKeyOf('미드01#T'),b:personKeyOf('미드01부#T'),c:personKeyOf('다른사람#T'),kis:KISATSU.map(k=>k.name),dup:Object.entries(cnt).filter(([,c])=>c>1),overlap:KISATSU.filter(k=>topP.has(personKeyOf(k.name))).map(k=>k.name)}})()"""
async def main():
    tmp = tempfile.mkdtemp(prefix='ks_'); xlsx = os.path.join(tmp, 's.xlsx'); WI.build_xlsx(xlsx)
    res = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=xlsx, now=WI.NOW, cats=('rift',), shots=False, quiet=True, evals=(JS,))
    o = res['evals'][0]; log = res['meta']['log']
    ok(o['a'] == o['b'] and o['a'] != o['c'], 'A 본계·부계가 한 사람 키 · 남은 다른 키 %s %s %s' % (o['a'], o['b'], o['c']))
    ok(not o['dup'], 'B 귀살대에 같은 사람이 두 번 없다 %s' % o['dup'])
    ok(not o['overlap'], 'B 귀살대가 상현(사람)과 겹치지 않는다 %s' % o['overlap'])
    ok(not log['pageerror'] and not log['console'], '콘솔 오류 0 %s %s' % (log['pageerror'][:1], log['console'][:1]))
    snap = os.environ.get('KS_SNAPSHOT')
    if snap and os.path.exists(snap):   # 실제 시트 스냅샷이 있으면: 카무사리·귤 갓·귤갓입니다가 한 사람
        r2 = await R.replay(os.path.join(os.path.dirname(HERE), 'index.html'), xlsx=snap, cats=('rift',), shots=False, quiet=True, evals=("(()=>({same:personKeyOf('카무사리')===personKeyOf('귤 갓#Gyul')&&personKeyOf('귤갓입니다#KR1')===personKeyOf('귤 갓#Gyul')}))()",))
        ok(r2['evals'][0]['same'], '실제 시트: 카무사리 = 귤 갓 = 귤갓입니다 한 사람')
    print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
