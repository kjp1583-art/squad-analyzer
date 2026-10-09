# -*- coding: utf-8 -*-
"""🦐 라스트 보스 = 흐접새우 본체 — 55분 최종 보스가 키아트의 새우 그림으로 나온다.
[2026-10-09 사장님 지시 「라스트보스를 흐접새우 본체가 등장하게끔 추가, 이미지는 키아트의 새우일러스트 추가해서 보스로」]
  A. 보스 정의: 그림 보스(img:'fin') · 이름 「흐접새우 본체」 · 클랜 보스처럼 접두 없음(brj) · 체력·반지름·속도·공격·패턴은 예전 그대로
  B. 그림 파일: img/survivors/boss_fin.webp — 투명 배경(알파) · 폭 256 · 60KB 이하 · 브라우저가 실제로 불러온다
  C. 나오는 순간: 배너 「🔥 최종 보스 — 👑 흐접새우 본체」 + 「대사」 · 55분 25초 전부터 그림을 미리 불러온다 · 그림이 그려진다(캔버스에 드로우 오류 0)
  D. 체력 = 3600 × bossMul × 1.6(최종 보스 배율) 그대로 · 처치하면 bossKill · 처치 배너에 dead 대사
  E. 소스에 「마스터 이」「MasterYi」가 남아 있지 않다(그림 요청 · 결과 말풍선 포함)
사용: python3 tests/survivors_finboss_test.py
"""
import asyncio, json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv_harness as H
from playwright.async_api import async_playwright
from PIL import Image

ROOT = H.ROOT
SHOT = os.environ.get('FIN_SHOT', '')   # 스크린샷 저장 폴더(없으면 안 찍음)


async def main():
    EXTRA = "window.__fin={get BIMG(){return BIMG},cap:[],hook(){const ob=banner;window.__fin.ob=ob;window.__fin.cap=[];banner=function(a,b,c){window.__fin.cap.push([a,b,c]);return ob.apply(this,arguments)};},unhook(){banner=window.__fin.ob;}};"
    p = H.make_copy('survivors.html', 'survivors_finx.html', extra=EXTRA)
    srv = H.Srv()
    fails = []
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)
    src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    ok('MasterYi' not in src and '마스터 이' not in src, 'E1 소스에 「마스터 이」·MasterYi 가 없다')
    im = Image.open(os.path.join(ROOT, 'img/survivors/boss_fin.webp'))
    sz = os.path.getsize(os.path.join(ROOT, 'img/survivors/boss_fin.webp'))
    ok(im.mode in ('RGBA', 'LA') and im.getchannel('A').getextrema()[0] == 0, 'B1 그림이 투명 배경(알파)이다 (mode %s, alpha min %s)' % (im.mode, im.getchannel('A').getextrema()[0] if im.mode == 'RGBA' else '-'))
    ok(im.width == 256 and 150 <= im.height <= 300, 'B2 폭 256 · 높이 적당 (%dx%d)' % im.size)
    ok(sz <= 60000, 'B3 파일 크기 ≤ 60KB (%d)' % sz)
    # 가장자리는 투명 · 가운데는 불투명(오려 낸 그림이 맞다)
    a = im.getchannel('A'); w, h = im.size
    border = [a.getpixel((x, 0)) for x in range(0, w, 8)] + [a.getpixel((x, h - 1)) for x in range(0, w, 8)] + [a.getpixel((0, y)) for y in range(0, h, 8)] + [a.getpixel((w - 1, y)) for y in range(0, h, 8)]
    ok(max(border) <= 40, 'B4 그림 테두리 픽셀은 거의 투명 (최대 알파 %d)' % max(border))
    ok(a.getpixel((w // 2, h // 2)) >= 250, 'B5 가운데는 불투명 (알파 %d)' % a.getpixel((w // 2, h // 2)))
    async with async_playwright() as pw:
        b = await H.launch(pw)
        ctx, pg, errs = await H.new_page(b, srv.port, w=1280, h=720, page='survivors_finx.html')
        info = await pg.evaluate("""()=>{const X=window.__p6x,B=X.BOSS.fin;return {img:B.img,nm:B.nm,brj:B.brj,fin:B.fin,id:B.id||null,acc:B.acc||null,r:B.r,sp:B.sp,hp:B.hp,d:B.d,xp:B.xp,atk:B.atk,sum:B.sum,sp0:B.sp0,hit:B.hit,dead:B.dead}}""")
        print('A', json.dumps(info, ensure_ascii=False)[:400])
        ok(info['img'] == 'fin' and info['fin'] == 1 and info['brj'] == 1, 'A1 그림 보스(img:fin) · 최종(fin) · 접두 없음(brj)')
        ok(info['nm'] == '👑 흐접새우 본체', 'A2 이름 「👑 흐접새우 본체」 (%s)' % info['nm'])
        ok(info['id'] is None and info['acc'] is None, 'A3 챔피언 그림·장신구 설정이 없다')
        ok((info['r'], info['sp'], info['hp'], info['d'], info['xp'], info['sum']) == (58, 66, 3600, 30, 300, 5) and info['atk'] == ['dash', 'ring', 'summon', 'shroom', 'shots'],
           'A4 체력·반지름·속도·공격·경험치·패턴은 예전 그대로 (%s)' % [info[k] for k in ('r', 'sp', 'hp', 'd', 'xp', 'sum')])
        ok(len(info['sp0']) >= 3 and len(info['hit']) >= 3 and len(info['dead']) >= 2, 'A5 등장·피격·처치 대사가 있다')
        # 판 시작 → 55분 25초 전 미리 불러오기
        r = await pg.evaluate("""()=>{const X=window.__p6x;X.CH_set('brj');X.start();const S=X.S;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;
          const F=window.__fin;const pre=!!F.BIMG.fin;S.t=3280;S.nextBoss=3300;X.update(1/30);return {pre,after:!!F.BIMG.fin}}""")
        ok(not r['pre'] and r['after'], 'C1 55분 25초 전(3275초 이후)부터 그림을 미리 불러온다 (전 %s → 후 %s)' % (r['pre'], r['after']))
        await pg.wait_for_function("window.__fin.BIMG.fin&&window.__fin.BIMG.fin.c", timeout=15000)
        nat = await pg.evaluate("()=>({w:window.__fin.BIMG.fin.c.width,h:window.__fin.BIMG.fin.c.height})")
        ok(nat['w'] > 100 and nat['h'] > 80, 'C2 브라우저가 그림을 불러왔다 (%s)' % nat)
        # 나오는 순간 배너(가로채기)
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,F=window.__fin;F.hook();
          S.t=3300;S.nextBoss=Infinity;const e=X.spawnBoss('fin');F.unhook();
          return {on:!!e,boss:e&&e.boss,mhp:e&&e.mhp,bossMul:X.bossMul(X.MIN()),cap:F.cap}}""")
        print('C', json.dumps(r, ensure_ascii=False)[:300])
        cap = r['cap'][0] if r['cap'] else ['', '']
        ok(r['on'] and r['boss'] == 'fin', 'C3 spawnBoss(fin) 로 나온다')
        ok(cap[0] == '🔥 최종 보스 — 👑 흐접새우 본체', 'C4 배너 제목 「🔥 최종 보스 — 👑 흐접새우 본체」 (%s)' % cap[0])
        ok(cap[1].startswith('「') and cap[1].endswith('」') and cap[1][1:-1] in info['sp0'], 'C5 배너 대사가 sp0 중 하나 (%s)' % cap[1])
        ok(abs(r['mhp'] - 3600 * r['bossMul'] * 1.6) < 1e-6 * r['mhp'], 'D1 체력 = 3600 × bossMul × 1.6 (%.2f vs %.2f)' % (r['mhp'], 3600 * r['bossMul'] * 1.6))
        # 그리기: 보스를 플레이어 옆에 두고 몇 프레임 돌린 뒤 그린다(오류 0) + 스크린샷
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S;const e=S.bossRef;e.x=S.p.x+170;e.y=S.p.y-20;
          let err=null;try{for(let i=0;i<20;i++){X.update(1/30);}X.draw();}catch(x){err=String(x)}
          return {err,nm:e.b.nm,on:e.on}}""")
        ok(r['err'] is None and r['on'], 'C6 그림 보스를 그리는 동안 오류 0 (%s)' % r['err'])
        if SHOT:
            os.makedirs(SHOT, exist_ok=True)
            await pg.screenshot(path=os.path.join(SHOT, 'fin_boss_1280.png'))
        # 처치
        r = await pg.evaluate("""()=>{const X=window.__p6x,S=X.S,F=window.__fin;F.hook();
          const e=S.bossRef;X.hurt(e,1e15);F.unhook();return {kill:S.bossKill,cap:F.cap.map(c=>[c[0],c[1]])}}""")
        ok(r['kill'] == 1, 'D2 처치하면 bossKill = 1')
        dead = [c for c in r['cap'] if '처치' in c[0]]
        ok(dead and dead[0][0] == '🏆 👑 흐접새우 본체 처치!' and dead[0][1][1:-1] in info['dead'], 'D3 처치 배너 + dead 대사 (%s)' % (dead[:1],))
        # 모바일 폭에서도 그려진다
        ctx2, pg2, errs2 = await H.new_page(b, srv.port, w=360, h=640, page='survivors_finx.html', mobile=True)
        r = await pg2.evaluate("""()=>{const X=window.__p6x;X.CH_set('brj');X.start();const S=X.S;S.p.hp=S.p.mhp=1e9;S.p.inv=1e9;S.t=3300;S.nextBoss=Infinity;const e=X.spawnBoss('fin');e.x=S.p.x+120;e.y=S.p.y-10;
          let err=null;try{for(let i=0;i<10;i++)X.update(1/30);X.draw();}catch(x){err=String(x)}return {err}}""")
        ok(r['err'] is None, 'C7 모바일 360×640 에서도 오류 0')
        if SHOT:
            await pg2.wait_for_timeout(300)
            await pg2.screenshot(path=os.path.join(SHOT, 'fin_boss_360.png'))
        real = [e for e in errs + errs2 if 'finx' not in e]
        ok(not real, 'E2 콘솔·페이지 오류 0 %s' % real[:3])
        await b.close()
    srv.close()
    try:
        os.remove(p)
    except Exception:
        pass
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
