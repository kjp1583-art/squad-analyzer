# -*- coding: utf-8 -*-
"""🩹 스크림 예외 판(MYEOL_SCRIM_FORCE) 시험 — 가짜 팀 둘 + 가짜 판 둘(한쪽 3명+대타 2명)로 _myeolScrimsCalc 를 돌려
  A 예외 목록에 있는 판은 자동 기준(4인↑)을 못 채워도 스크림으로 잡힌다  B 목록에 없는 같은 모양의 판은 여전히 안 잡힌다  C 팀 이름이 그 회차에 없으면 안 잡힌다
  python3 tests/web_scrim_force_test.py"""
import asyncio, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'web_replay'))
try:
    import replay as R, synth, openpyxl
except Exception as e:
    print('SKIP (%s)' % e); sys.exit(0)
fails = 0
def ok(c, m):
    global fails; print(('  ok   ' if c else '  FAIL ') + m); fails += (not c)
JS = """()=>{
  const mk=(gid,blueNames,redNames,blueWin)=>({id:gid,rows:[
    ...blueNames.map(n=>({"게임ID":gid,"날짜":"2026-11-27 00:25","소환사명":n,"진영":"블루팀","결과":blueWin?"승리":"패배","KDA":"1/1/1"})),
    ...redNames.map(n=>({"게임ID":gid,"날짜":"2026-11-27 00:25","소환사명":n,"진영":"레드팀","결과":blueWin?"패배":"승리","KDA":"1/1/1"}))]});
  const A=["뀨잉언진","a1","a2","a3","a4"], B=["하 오","b1","b2","b3","b4"];
  const teams=[{cap:"뀨잉언진",m:A.slice(1).map(n=>[n,0])},{cap:"하 오",m:B.slice(1).map(n=>[n,0])}];
  const sub=["대타1","대타2"];
  const G=new Map();
  G.set("#8474399763",mk("#8474399763",A,[...B.slice(0,3),...sub],true));       // 예외 목록 판: 뀨잉언진 5(블루 승) vs 하 오 3+대타 2
  G.set("#9999999999",mk("#9999999999",A,[...B.slice(0,3),...sub],true));       // 같은 모양이지만 목록에 없음
  const old=window.GAMES_ALL; GAMES_ALL=G;
  const r1=_myeolScrimsCalc(teams,new Date(2026,0,1));
  const r2=_myeolScrimsCalc([{cap:"다른팀",m:[]},{cap:"하 오",m:[]}],new Date(2026,0,1));
  return {ids:r1.list.map(x=>x.gid+"|"+x.win+">"+x.lose), n2:r2.list.length, rec:Object.fromEntries(r1.rec)};
}"""
async def after(pg):
    o = await pg.evaluate(JS)
    ok(o['ids'] == ['#8474399763|뀨잉언진>하 오'], 'A 예외 판만 스크림으로 잡힘 · 승자 뀨잉언진 %s' % o['ids'])
    ok('#9999999999' not in ''.join(o['ids']), 'B 목록에 없는 같은 모양 판은 안 잡힘')
    ok(o['n2'] == 0, 'C 팀이 그 회차에 없으면 안 잡힘')
async def main():
    with tempfile.TemporaryDirectory() as td:
        x = os.path.join(td, 's.xlsx'); wb = openpyxl.Workbook(); wb.remove(wb.active)
        for n, rs in synth.build_tabs().items():
            ws = wb.create_sheet(n)
            for r in rs: ws.append(r)
        wb.save(x)
        await R.replay(os.path.join(HERE, '..', 'index.html'), xlsx=x, out=td, focus=(), shots=False, viewport=(1100, 900), after=after, quiet=True)
asyncio.run(main())
print('전부 통과' if not fails else '실패 %d건' % fails); sys.exit(1 if fails else 0)
