# -*- coding: utf-8 -*-
"""🛡 무적 상한 시뮬 — 실제 hitP/invGrant 코드를 그대로 돌려 접촉 빈도(λ, 초당 '맞을 뻔한' 횟수)별로
   무적 가동률(uptime)과 실제로 맞는 횟수(hits/s)를 상한 후보(0.60·0.70·0.80·없음)와 비교한다.   사용: python3 tests/survivors_inv_sim.py"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
JS = r"""(a)=>{const x=__p6x;const out=[];x.setCap(a.cap);
 for(const cfg of a.cfgs){x.CH_set(cfg.c);x.start();const S=x.S,p=S.p;p.hp=p.mhp=1e12;S.pt.arm=cfg.arm;S.rel.sprint=cfg.spr;
  let s=12345;const rnd=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};
  for(const lam of a.lams){S.t=0;p.inv=0;S.invCur='';S.dashCd=0;let up=0,hits=0,pk=0;const dt=1/60,N=60*a.sec,pr=1-Math.exp(-lam*dt);
   for(let i=0;i<N;i++){S.t+=dt;if(p.inv>0)p.inv-=dt;if(S.dashCd>0)S.dashCd-=dt;if(p.inv>pk)pk=p.inv;if(p.inv>0)up++;
    if(lam>=60||rnd()<pr){const h0=p.hp;x.hitP(5,'');if(p.hp<h0)hits++;}}
   out.push({cfg:cfg.n,lam,uptime:up/N,hps:hits/a.sec,peak:pk});}}
 return out;}"""
CFGS = [{'n': '기본 .45', 'c': 'brj', 'arm': 0, 'spr': 0}, {'n': '방패계열 .57', 'c': 'brj', 'arm': 1, 'spr': 0},
        {'n': '방패+줄행랑3 .77', 'c': 'brj', 'arm': 1, 'spr': 3}, {'n': '태웅 돌진(.45/.5)', 'c': 'tw', 'arm': 0, 'spr': 0}, {'n': '태웅+방패+줄행랑3', 'c': 'tw', 'arm': 1, 'spr': 3}]
LAMS = [.5, 1, 2, 4, 10, 60]
async def main():
    H.make_copy(dst='survivors_inv.html'); srv = H.Srv()
    async with async_playwright() as p:
        b = await H.launch(p); ctx, pg, errs = await H.new_page(b, srv.port, page='survivors_inv.html')
        res = {}
        for cap in [.6, .7, .8, 9]:
            res[cap] = await pg.evaluate(JS, {'cap': cap, 'cfgs': CFGS, 'lams': LAMS, 'sec': 600})
        print('빌드 / 접촉빈도λ(/초)  →  상한별 [가동률% · 맞는 횟수/초]  (상한 없음 = 9)')
        for ci, cfg in enumerate(CFGS):
            for li, lam in enumerate(LAMS):
                row = [res[c][ci * len(LAMS) + li] for c in [.6, .7, .8, 9]]
                print('  %-18s λ=%-4s ' % (cfg['n'], lam) + ' | '.join('cap%.2f: %5.1f%% %.2f/s peak%.2f' % (c if c < 9 else 99, r['uptime'] * 100, r['hps'], r['peak']) for c, r in zip([.6, .7, .8, 9], row)))
        ref = {(r['cfg'], r['lam']): r for r in res[9]}
        worst = {}
        for c in [.6, .7, .8]:
            w = max((r['hps'] / ref[(r['cfg'], r['lam'])]['hps'] - 1) for r in res[c] if ref[(r['cfg'], r['lam'])]['hps'] > 0)
            worst[c] = round(w * 100, 1)
        print('상한 없음 대비 최악의 피격 횟수 증가(%):', worst)
        print('errs', errs); await b.close()
    srv.close(); os.remove(os.path.join(H.ROOT, 'survivors_inv.html'))
asyncio.run(main())
