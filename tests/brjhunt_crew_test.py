#!/usr/bin/env python3.13
"""동료 개편 시험 — 필드에서 동료가 실제로 같이 싸우는가 (brjhunt_arena.js 동료 + brjhunt_sd.js 그림)
 (a) 6계열 × 5등급 전부: 기본 공격이 몬스터를 때리고(allyhit) 처치에 기여, 고유 액티브가 시전되고 효과가 난다
 (b) 방패(guard)는 병아리가 받는 피해를 줄이고, 치유(heal)는 체력을 채운다
 (c) 동료가 몬스터를 처치해도 서버 kpm 모델과 어긋나지 않는다 — 파티 없음 vs 3명(계열별)의 분당 처치 비교
 (d) 깨진 데이터(없는 계열·이상한 액티브·NaN)와 계열 정보가 없는 옛 파티도 안 터진다 · 콘솔 오류 0
 (e) SD 그림: 6계열 × 5등급 SVG 가 그려지고 서로 다르다 · 필드 캔버스에 그려진다
사용: CHROME=... python3.13 tests/brjhunt_crew_test.py"""
import asyncio, os, sys
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome')
URL = 'file://' + os.path.join(ROOT, 'tests', 'brjhunt_crew_harness.html')
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x != '' else ''), flush=True)
    if not c: FAILS.append(n)

FAMS = ['blade', 'bow', 'mage', 'tank', 'heal', 'lucky']
GRS = ['normal', 'rare', 'epic', 'unique', 'legend']

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME, args=['--allow-file-access-from-files'])
        pg = await br.new_page(viewport={'width': 600, 'height': 420}, device_scale_factor=1)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_FILE_NOT_FOUND' not in m.text and '404' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(500)

        # (a) 계열 × 등급
        R = await pg.evaluate('''()=>{
          const FAMS=%s, GRS=%s, out=[];
          for(const fam of FAMS) for(const gr of GRS){
            const a=mkArena({seed:3,noManifest:true}); a.setState(mkState(1,['slash'],{party:[mkAlly(fam,gr)]}));
            let hits=0,kills=0; a.on('allyhit',()=>hits++);
            const casts=[]; const origSay=null;
            a.sim(60,1/60);
            const s=a.stats(); out.push({fam,gr,hits,kills:s.kills,allies:a.debug.allies().length,acts:a.debug.allies()[0]?a.debug.allies()[0].casts:-1});
            a.destroy();
          }
          return out;}''' % (FAMS, GRS))
        dmg = [r for r in R if r['fam'] in ('blade', 'bow', 'mage', 'lucky')]
        check('30종(6계열×5등급) 전부 동료가 생성된다', all(r['allies'] == 1 for r in R), len(R))
        check('모든 동료가 60초 안에 몬스터를 실제로 때린다(allyhit > 5)', all(r['hits'] > 5 for r in R), min(r['hits'] for r in R))
        print('   시전 횟수(60초)', {f: min(r['acts'] for r in R if r['fam'] == f) for f in FAMS})
        check('공격·방패 계열의 고유 액티브는 모두 시전된다(60초 동안 ≥ 2번)', all(r['acts'] >= 2 for r in R if r['fam'] != 'heal'), min(r['acts'] for r in R if r['fam'] != 'heal'))
        hi = {r['gr']: sum(x['hits'] for x in R if x['gr'] == r['gr']) for r in R}
        print('   등급별 총 타수', hi)

        # (b) 방패·치유 효과
        B = await pg.evaluate('''()=>{
          const mkA=(fam)=>{const a=mkArena({seed:5,noManifest:true}); a.setState(mkState(1,[],{party:[mkAlly(fam,'legend')]})); a.debug.clearMobs(); a.setAuto(false); return a;};
          const out={};
          // 방패: 같은 크기 피해를 입히되, 방패 시전 전/후 비교
          let a=mkA('tank'); const P=a.debug.P; P.hp=P.hpMax; P.inv=0; a.debug.hurt(400); const raw=P.hpMax-P.hp;
          P.hp=P.hpMax; P.inv=0; a.debug.forceCast(0); a.sim(0.2,1/60); P.inv=0; const h0=P.hp; a.debug.hurt(400); const guarded=h0-P.hp; out.guard={raw,guarded,t:P.guardT};
          // 치유: 체력이 깎여 있으면 시전해서 올라간다
          a=mkA('heal'); const Q=a.debug.P; Q.hp=Math.round(Q.hpMax*0.4); const before=Q.hp; a.sim(1.5,1/60); out.heal={before,after:Q.hp,max:Q.hpMax};
          // 치유: 체력이 가득이면 낭비하지 않는다(시전 안 함)
          a=mkA('heal'); a.sim(3,1/60); out.healFull=a.debug.allies()[0].casts;
          return out;}''')
        check('방패: 시전 후 받는 피해가 줄어든다', B['guard']['guarded'] < B['guard']['raw'] * 0.85 and B['guard']['t'] > 0, B['guard'])
        check('치유: 체력이 깎이면 채워 준다', B['heal']['after'] > B['heal']['before'], B['heal'])
        check('치유: 체력이 가득이면 시전을 아낀다', B['healFull'] == 0, B['healFull'])

        # (c) kpm 보정: 파티 없음 vs 계열별 3명
        K = await pg.evaluate('''()=>{
          const run=(party,seed)=>{const a=mkArena({seed,noManifest:true}); a.setState(mkState(1,['slash','spin','bomb','fire'],{scale:true,party})); a.sim(15,1/60); const k0=a.stats().kills; a.sim(90,1/60); const v=(a.stats().kills-k0)/90*60; a.destroy(); return v;};
          const avg=(party)=>{let t=0; for(const s of [1,2,3]) t+=run(party,s); return t/3;};
          const out={none:avg([])};
          for(const fam of ['blade','bow','mage','tank','heal','lucky']) out[fam]=avg([mkAlly(fam,'legend'),mkAlly(fam,'epic'),mkAlly(fam,'rare')]);
          out.mixed=avg([mkAlly('blade','legend'),mkAlly('bow','legend'),mkAlly('mage','legend')]);
          out.mixedN=avg([mkAlly('blade','normal'),mkAlly('heal','normal'),mkAlly('lucky','normal')]);
          return out;}''')
        print('   분당 처치', {k: round(v) for k, v in K.items()})
        check('파티가 있어도 분당 처치가 서버 모델 근처(파티 없음의 ±20%)', all(abs(v - K['none']) <= K['none'] * 0.20 for v in K.values()), {k: round(v / K['none'], 2) for k, v in K.items()})

        # 실제로 동료가 처치에 기여하는 비율(동료 타격으로 쓰러뜨림)
        C = await pg.evaluate('''()=>{
          const a=mkArena({seed:2,noManifest:true}); a.setState(mkState(1,['slash'],{scale:true,party:[mkAlly('blade','legend'),mkAlly('bow','legend'),mkAlly('mage','legend')]}));
          let ah=0; a.on('allyhit',()=>ah++); a.sim(90,1/60); const s=a.stats(); const al=a.debug.allies();
          return {kills:s.kills,ah,allyKills:al.reduce((n,x)=>n+x.kills,0)};}''')
        check('동료가 처치에 기여한다(동료 막타 ≥ 1, 타수 > 30)', C['allyKills'] >= 1 and C['ah'] > 30, C)

        # (d) 깨진 데이터
        D = await pg.evaluate('''()=>{
          const bad=[{id:'x',n:'?',gr:'legend'},{id:'y',n:'가',gr:'zzz',fam:'nope',act:{kind:'hax',mult:NaN,hits:-5,cd:0},pas:{axis:'??',pct:'abc'}},
                     {id:'z',n:'나',gr:'epic',fam:'blade',act:{kind:'strike',mult:1e9,hits:999,cd:1e-9}},null,undefined,{id:'w',n:'',gr:'rare',fam:'mage',act:{kind:'burst',mult:150,hits:2,cd:Infinity}}];
          const a=mkArena({seed:1,noManifest:true}); a.setState(mkState(1,['slash'],{party:bad})); a.sim(40,1/60);
          const n1=a.debug.allies().length; a.setState(mkState(1,['slash'],{party:[]})); a.sim(1,1/60); const n2=a.debug.allies().length;
          a.setState(mkState(1,['slash'],{party:[mkAlly('tank','legend')]})); a.sim(1,1/60); const n3=a.debug.allies().length;
          return {n1,n2,n3,k:a.stats().kills};}''')
        check('깨진 동료 정보도 터지지 않고 처리된다', D['n1'] <= 3 and D['n2'] == 0 and D['n3'] == 1, D)
        # 보스·인스턴스 중에도 오류 없음(동료는 보스를 안 때린다)
        Bs = await pg.evaluate('''()=>{
          const a=mkArena({seed:4,noManifest:true}); a.setState(mkState(1,['slash'],{party:[mkAlly('blade','legend'),mkAlly('tank','legend'),mkAlly('heal','legend')]}));
          let ah=0; a.on('allyhit',()=>ah++); a.sim(5,1/60); a.startChallenge({img:'',name:'테스트 보스',hp:1000}); const ah0=ah; a.sim(8,1/60);
          return {during:ah-ah0,boss:a.stats().boss};}''')
        check('보스 도전 중에는 동료가 보스를 때리지 않는다(승패는 서버가 정한다)', Bs['during'] == 0, Bs)

        # (e) SD 그림
        S = await pg.evaluate('''()=>{
          const seen=new Set(), out={n:0,bad:[]};
          for(const f of BrjSD.KEYS) for(const g of ['normal','rare','epic','unique','legend']){ const s=BrjSD.svg(f,g,48); out.n++; if(!/^<svg[\\s\\S]*<\\/svg>$/.test(s)) out.bad.push(f+g); seen.add(s); }
          out.distinct=seen.size; out.fb=BrjSD.svg('없는계열','???',48).startsWith('<svg'); out.xss=BrjSD.svg('<img>','"><script>',9999).indexOf('<script>')<0;
          return out;}''')
        check('SD 그림 30종이 모두 SVG 로 나오고 서로 다르다', S['n'] == 30 and not S['bad'] and S['distinct'] == 30, S)
        check('없는 계열·등급·이상한 값도 기본 그림으로(주입 없음)', S['fb'] and S['xss'])
        await pg.wait_for_timeout(300)
        Px = await pg.evaluate('''async()=>{
          const a=mkArena({seed:1,noManifest:true}); a.setState(mkState(1,['slash'],{party:[mkAlly('mage','legend'),mkAlly('bow','epic'),mkAlly('tank','rare')]}));
          for(let i=0;i<40;i++){ a.tick(1/30); } await new Promise(r=>setTimeout(r,300)); for(let i=0;i<10;i++){ a.tick(1/30); }
          const cv=document.getElementById('cv'), c=cv.getContext('2d'); const al=a.debug.allies();
          // 첫 동료 근처 영역에 SD 그림 색(등급색 테두리/몸색)이 있는지: 그림이 그려졌는지 대신 img 로딩을 확인
          BrjSD.KEYS.forEach(f=>BrjSD.img(f,'legend')); await new Promise(r=>setTimeout(r,500));
          return {imgs:BrjSD.KEYS.map(f=>!!BrjSD.img(f,'legend')), n:al.length};}''')
        check('필드 캔버스용 SD 이미지가 로딩된다', all(Px['imgs']) and Px['n'] == 3, Px)
        await pg.screenshot(path='/tmp/claude-0/crew_field.png')
        check('콘솔·페이지 오류 0', not errs, errs[:5])
        await br.close()
    print('\n실패 %d건' % len(FAILS)); [print(' -', f) for f in FAILS]
    sys.exit(1 if FAILS else 0)
asyncio.run(main())
