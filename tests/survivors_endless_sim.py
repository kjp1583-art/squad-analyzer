# -*- coding: utf-8 -*-
"""♾ 무한 모드 장시간 시뮬 — 무적(god) 봇이 카드를 첫 장씩 고르며 돌아다닌다. 서버 상한(50+250t · 10+t//12) 통과 · 메모리/풀 크기 · 단계 비용을 체크포인트마다 기록.
   사용: python3 tests/survivors_endless_sim.py [끝 분=180] [dt=0.05] [캐릭터=brj] [max]"""
import asyncio, sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
END_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 180
DT = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
CH = sys.argv[3] if len(sys.argv) > 3 else 'brj'
MAXK = (sys.argv[4] == 'max') if len(sys.argv) > 4 else False   # max: 피해 배율을 극단으로 올려 처치율·경험치율의 천장을 잰다(서버 상한 점검용)
STEP = r"""(args)=>{const x=__p6x;const {untilT,dt}=args;let n=0;const t0=performance.now();
 while(n<400000){const st=x.state;
  if(st==='result'){ if(x.S.won&&!x.S.endless&&x.S.t<%d){x.contEndless();continue;} return {done:'result'}; }
  if(st==='lvup'){x.pick(x.CUR[0]);continue;} if(st!=='play'){x.resume();continue;}
  const S=x.S;if(S.t>=untilT)break;S.p.hp=S.p.mhp;if(args.max){S.syn.dmg=1e5;}
  const k=Math.floor(S.t/2.5)%%4;x.keys=[{KeyD:true},{KeyS:true},{KeyA:true},{KeyW:true}][k];
  x.update(dt);n++;}
 return {n,ms:performance.now()-t0,state:x.state};}""" % 10800
async def main():
    H.make_copy(); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port)
        await pg.evaluate("c=>{__p6x.SRVUNL.add(c);__p6x.CH_set(c);__p6x.start();}", CH)
        rows = []; t_wall = time.time(); bad = []
        marks = [10 * i for i in range(1, int(END_MIN // 10) + 1)] + ([END_MIN] if END_MIN % 10 else [])
        for mk in marks:
            r = await pg.evaluate(STEP, {'untilT': mk * 60, 'dt': DT, 'max': MAXK})
            if r.get('done'): print('결과 화면으로 끝남', mk); break
            snap = await pg.evaluate("""()=>{const x=__p6x,S=x.S;if(window.gc)window.gc();const m=performance.memory?performance.memory.usedJSHeapSize/1048576:0;
              let live=0;for(const e of x.enemies.a)if(e.on)live++;
              return {t:Math.floor(S.t),kills:S.kills,lv:S.lv,heap:+m.toFixed(1),live,booms:S.booms.length,ebooms:S.ebooms.length,beams:S.beams.length,dq:S.dq.length,mines:S.mines.length,
                dmgKeys:Object.keys(S.dmgBy).length,cache:x.RIFT_CACHE.size,endless:S.endless,min:+x.MIN().toFixed(1),w:Object.keys(S.w).length,tier:Object.values(S.tier).reduce((a,b)=>a+b,0),
                rel:Object.keys(S.rel).length,xp:S.xp};}""")
            snap['ms_step'] = round(r['ms'] / max(1, r['n']), 3); snap['wall'] = round(time.time() - t_wall)
            snap['ok_kills'] = snap['kills'] <= 50 + 250 * snap['t']; snap['ok_lv'] = snap['lv'] <= 10 + snap['t'] // 12
            rows.append(snap); print(json.dumps(snap, ensure_ascii=False), flush=True)
            if not (snap['ok_kills'] and snap['ok_lv']): bad.append(snap)
        print('errs', errs)
        print('서버 상한 위반:', bad if bad else '없음')
        await b.close()
    srv.close()
    try: os.remove(os.path.join(H.ROOT, 'survivors_x.html'))
    except Exception: pass
asyncio.run(main())
