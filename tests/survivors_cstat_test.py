# -*- coding: utf-8 -*-
"""✨ 흐접새우 서바이벌 「고유스텟」 시험 — 2026-10-12 사장님 지시
   「집중겜의 치명타20%처럼 캐릭터마다 가지고있는 고유한 스텟을 고유스텟 이라고 명명하고 캐릭터선택창에서 잘 확인할수있도록」
   사용: python3 tests/survivors_cstat_test.py [--fast]   (종료코드 0 = 전부 통과 · --fast 는 규칙 불변(비트 비교)을 건너뛴다)
   구성
     가  정답표 — CSTAT 키 = CHARS 키(18명 1:1) · 행 모양 · 없음 캐릭터(브장신·엄장신)는 이유 한 줄
     나  표시 = 코드 값 — 문구의 숫자가 CHARS 필드·상수(SHV·CSK·LOWHP_AT)에서 나온다: 값을 일부러 바꾸면(변이) 문구가 따라 바뀐다
     다  표시 = 실제 동작 — 판을 시작해 치명타·이동속도·방어·경험치·줍는 범위·쿨타임·최대 HP·회복·용 변신·스탭·진실의 방·돌진이 문구와 같은 값으로 움직인다
     라  선택 화면 — 로스터 카드 18장(잠긴 카드 포함)에 칩 · 설명창 「✨ 고유스텟」 구획 · 용어 통일 · 고유 무기와 구분
     마  폰·PC 화면 — 가로 넘침 0 · 칩 글자 넘침 0 · 카드 높이 증가 한도 · 대비 4.5 · 터치 대상 · 페이지 오류 0
     바  규칙 불변 — 이어하기 서명(SIG) 같음 · 새 최상위 let 0 · 새 S 키 0 · tests/survivors_equiv.py 비트 동일(--fast 면 건너뜀)
   임시 사본 survivors_cb_cstat.html · survivors_cb_cstat_base.html(기준 커밋)에 훅을 꽂아 쓴다(끝나면 지운다 · 커밋하지 않는다)."""
import asyncio, sys, os, re, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_harness as H
from playwright.async_api import async_playwright
ROOT = H.ROOT
FAST = '--fast' in sys.argv
BASE_COMMIT = os.environ.get('CSTAT_BASE_COMMIT', 'bf755af')   # 전 캐릭터 고유능력(2026-10-12 사장님 지시)을 넣기 직전의 main — 서명·높이 비교와 「안 바뀐 캐릭터는 비트 동일」의 기준
CHANGED = ['brj', 'mms', 'hrb', 'amd', 'ildj', 'ddmj', 'eom', 'bbb', 'yj', 'bgb', 'tw', 'ddo']   # 이번에 능력이 새로 붙었거나 값이 달라진 캐릭터(앞 10명은 CSX 표 키, tw=씩씩 +70%, ddo=방 반경 190)
LOWHP_ONLY = ['mms', 'amd', 'tw']   # 저체력 조건에서만 켜지는 능력(태웅 씩씩 상한은 체력을 70% 넘게 잃어야 닿는다) — 150초 판에선 그 조건을 안 밟아 판이 같을 수 있다(조건을 밟는 동작은 survivors_cabil_test.py 가 직접 확인)
SAME = ['jjg', 'sr', 'yumi', 'ssu', 'kyo']                      # 안 바뀐 캐릭터 — 기준과 비트까지 같아야 한다
NEW, OLD = 'survivors_cb_cstat.html', 'survivors_cb_cstat_base.html'
HEIGHT_LIMIT = 1.35      # 로스터 두 목록(클랜원+보스) 높이가 기준의 이 배수를 넘으면 빨강(칩 두 줄 = 카드마다 +30px 안팎 → 폰 360 폭에서 약 1.25배)
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else ('  ← ' + str(x)[:700] if x != '' else '')), flush=True)
    if not c: FAILS.append(n)

EXTRA = r"""
window.__cs={CHARS,CSTAT,cstat,cstatChip,cstatHtml,csChip,CSK,SHV,LOWHP_AT,CRIT_BASE,RES,allies,taeDash,charTick,
  critChance,critMul,moveMul,armTotal,xpMul,magMul,cdMul,lowMul,takenMul,dmgMul,rageCap,rageMul,
  get CH(){return CH},get S(){return S}};
"""

async def main():
    base_src = subprocess.check_output(['git', '-C', ROOT, 'show', BASE_COMMIT + ':survivors.html']).decode('utf-8')
    open(os.path.join(ROOT, 'survivors_cb_cstat_base_src.html'), 'w', encoding='utf-8').write(base_src)
    H.make_copy(src='survivors.html', dst=NEW, extra=EXTRA)
    H.make_copy(src='survivors_cb_cstat_base_src.html', dst=OLD, extra='window.__cs={RES,CHARS};\n')   # 기준 사본은 서명·높이 비교에만 쓴다
    srv = H.Srv()
    try:
        async with async_playwright() as pw:
            b = await H.launch(pw)
            ctx, pg, errs = await H.new_page(b, srv.port, 412, 860, page=NEW, ready='__cs')
            await pg.wait_for_timeout(500)

            # ── 가 정답표
            r = await pg.evaluate("""()=>{const x=__cs;const ks=x.CHARS.map(c=>c.k),cs=Object.keys(x.CSTAT);
              const rows={};for(const c of x.CHARS)rows[c.k]=x.cstat(c);
              return {ks,cs,rows,shape:x.CHARS.every(c=>{const d=x.cstat(c);return d.rows.every(r=>r.ic&&r.nm&&r.ds&&typeof r.v==='string')&&(d.rows.length>0||d.none.length>=6)})}}""")
            check('[가] CHARS 18명 = CSTAT 18키 1:1(순서 무관)', len(r['ks']) == 18 and sorted(r['ks']) == sorted(r['cs']), (r['ks'], r['cs']))
            check('[가] 모든 행이 {ic,nm,v,ds} · 없음 캐릭터는 이유 한 줄', r['shape'])
            none = sorted(k for k, d in r['rows'].items() if not d['rows'])
            check('[가] 고유스텟 없음 0명 — 브장신·엄장신도 능력이 생겼다(2026-10-12)', none == [], none)
            check('[가] 18명 전원 1줄 이상', all(len(d['rows']) >= 1 for d in r['rows'].values()))
            check('[가] 고유 무기·시작 무기는 고유스텟 행에 안 들어간다(「고유 무기」「시작」 낱말 0)',
                  not any(re.search('고유 무기|시작 무기|해금', row['nm'] + row['ds']) for d in r['rows'].values() for row in d['rows']))

            # ── 나 값 = 코드 (필드·상수를 읽어서 만든다 — 변이로 확인)
            # (캐릭터, 값을 꺼내는 식, 서식) — 문구(이름+값+설명)에 서식 글자가 들어 있어야 한다
            PC, NUM = 'pct', 'num'
            SPEC = [
                ('jjg', 'c.crit', PC), ('mms', 'c.low', PC), ('mms', 'x.LOWHP_AT', PC), ('hrb', 'c.spd', PC),
                ('ssu', 'c.regen', NUM), ('ssu', 'c.arm', NUM), ('amd', 'c.regen', NUM), ('ildj', 'c.xp', PC),
                ('kyo', 'c.lvheal', NUM), ('kyo', 'c.mag', PC), ('ddmj', 'c.arm', NUM), ('ddmj', '-c.spd', PC),
                ('psg', 'x.SHV.dur', NUM), ('psg', 'x.SHV.spd', PC), ('psg', 'x.SHV.red', PC), ('psg', 'x.SHV.dmg-1', PC), ('psg', 'x.SHV.acc', PC), ('psg', 'x.SHV.accMax', NUM),
                ('bbb', 'c.cdr', PC),
                ('sr', 'x.CSK.staff.every', NUM), ('sr', 'x.CSK.staff.n', NUM), ('sr', 'x.CSK.staff.life', NUM), ('sr', '1-x.CSK.staff.slow', PC),
                ('ddo', 'x.CSK.room.every', NUM), ('ddo', 'x.CSK.room.hold', NUM),
                ('tw', 'c.rage', PC), ('tw', 'x.CSK.dash.inv', NUM), ('tw', 'x.CSK.dash.cd', NUM),
                ('yumi', 'c.mag', PC), ('yumi', 'c.auto', NUM),
                ('yj', 'c.hp', NUM), ('yj', 'c.arm', NUM), ('yj', '-c.spd', PC),
                ('bgb', 'c.spd', PC), ('bgb', 'c.mag', PC),
                ('jjg', 'x.CRIT_BASE', NUM),
            ]
            # 변이 가능한 대상: CHARS 필드(c.xxx) · SHV/CSK 안의 숫자. (LOWHP_AT·CRIT_BASE 는 const 숫자라 못 바꾼다 → 표시값 일치만 본다)
            res = await pg.evaluate("""(SPEC)=>{const x=__cs,out=[];
              const fmt=(v,f)=>f==='pct'?(Math.round(v*1000)/10)+'%':String(Math.round(v*100)/100);
              const text=k=>{const c=x.CHARS.find(c=>c.k===k);return x.cstat(c).rows.map(r=>r.nm+' '+r.v+' '+r.ds).join(' | ')};
              for(const [k,expr,f] of SPEC){
                const c=x.CHARS.find(c=>c.k===k);const ev=()=>eval(expr);
                const v0=ev(),t0=text(k),want0=fmt(Math.abs(v0),f);
                const o={k,expr,want0,shown:t0.includes(want0)};
                // 변이: 필드/상수를 바꿔 본다
                const m=expr.replace(/^-/,'').replace(/-1$/,'').replace(/^1-/,'');const isConst=/LOWHP_AT|CRIT_BASE/.test(expr);
                if(!isConst){
                  const parts=m.split('.');const key=parts.pop();const obj=eval(parts.join('.'));const old=obj[key];
                  const delta=f==='pct'?.07:3;obj[key]=old+(/^1-|-1$/.test(expr)?-delta:delta);   // 식이 1-값 · 값-1 이면 표시값이 바뀌게 방향을 맞춘다
                  const v1=ev(),want1=fmt(Math.abs(v1),f);o.want1=want1;o.mut=text(k).includes(want1);o.moved=want1!==want0;
                  obj[key]=old;
                }
                out.push(o);}
              return out}""", SPEC)
            for o in res:
                check('[나] %s %s → 「%s」 가 문구에 나온다' % (o['k'], o['expr'], o['want0']), o['shown'], o)
                if 'mut' in o:
                    check('[나] %s %s 를 바꾸면 문구가 따라 바뀐다(→ 「%s」)' % (o['k'], o['expr'], o['want1']), o['mut'] and o['moved'], o)

            # ── 다 표시 = 실제 동작
            beh = await pg.evaluate("""()=>{const x=__cs,P=window.__p6x,out={};
              const num=(s)=>{const m=String(s).match(/-?\\d+(\\.\\d+)?/);return m?parseFloat(m[0]):NaN};
              const row=(k,nm)=>x.cstat(x.CHARS.find(c=>c.k===k)).rows.find(r=>r.nm===nm);
              P.srvUnl(['yumi','bbb','eom']);   // 상점 캐릭터는 서버 구매 목록에 있어야 판이 그 캐릭터로 시작한다
              const begin=k=>{P.CH_set(k);P.start();const S=P.S;S.spawnT=-1e12;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;S.propT=S.chickT=1e12;for(const q of P.enemies.a)q.on=false;if(P.CH.k!==k)throw new Error('캐릭터가 안 바뀜 '+k);return S};
              const base=(()=>{begin('brj');return {cc:x.critChance?x.critChance():0}})();
              // 치명타
              let S=begin('jjg');out.crit={shown:num(row('jjg','치명타').v)/100,real:x.critChance()-(begin('brj'),x.critChance()),cm:x.critMul()};begin('jjg');
              // 위기 피해
              S=begin('mms');S.p.hp=S.p.mhp*.2;const lo=x.lowMul();S.p.hp=S.p.mhp;out.low={shown:num(row('mms','위기 피해').v)/100,real:lo-1,off:x.lowMul(),at:x.LOWHP_AT};
              S.p.hp=S.p.mhp*(x.LOWHP_AT+.02);out.low.justAbove=x.lowMul();S.p.hp=S.p.mhp*(x.LOWHP_AT-.02);out.low.justBelow=x.lowMul();
              // 이동속도
              out.spd={};for(const k of ['hrb','ddmj','yj','bgb']){S=begin(k);const b=(begin('brj'),x.moveMul());begin(k);out.spd[k]={shown:num(row(k,'이동속도').v)/100,real:x.moveMul()-b};}
              // 받는 피해
              out.arm={};for(const k of ['ssu','ddmj','yj']){begin(k);out.arm[k]={shown:-num(row(k,'받는 피해').v),real:x.armTotal()};}
              // 경험치 · 줍는 범위 · 쿨타임 · 최대 HP
              begin('ildj');out.xp={shown:num(row('ildj','경험치').v)/100,real:x.xpMul()-1};
              out.mag={};for(const k of ['kyo','yumi','bgb']){begin(k);out.mag[k]={shown:num(row(k,'줍는 범위').v)/100,real:x.magMul()-1};}
              begin('bbb');out.cdr={shown:num(row('bbb','쿨타임').v)/100,real:x.cdMul()-1};
              begin('yj');out.hp={shown:num(row('yj','최대 HP').v),real:P.S.p.mhp-100};
              // 회복(초당)
              out.regen={};for(const k of ['ssu','amd']){S=begin(k);S.w={};S.p.hp=50;P.keys={};for(let i=0;i<30;i++)P.update(1/30);out.regen[k]={shown:num(row(k,'HP 회복').v.replace('초당','')),real:S.p.hp-50};}
              // 레벨업 회복
              S=begin('kyo');S.p.hp=40;S.need=10;S.xp=0;P.gainXp(10);out.lv={shown:num(row('kyo','레벨업 회복').v),real:S.p.hp-40,state:P.state};
              return out}""")
            check('[다] 집중겜 치명타 확률 = 문구(+20%)', abs(beh['crit']['shown'] - beh['crit']['real']) < 1e-9 and abs(beh['crit']['shown'] - 0.2) < 1e-9, beh['crit'])
            check('[다] 치명타 피해 기본 배율 = CRIT_BASE', beh['crit']['cm'] == 2, beh['crit'])
            check('[다] 망무새 체력 낮으면 피해 보정 = 문구 · 체력 차면 1 · 경계(30%) 위·아래', abs(beh['low']['shown'] - beh['low']['real']) < 1e-9 and beh['low']['off'] == 1 and beh['low']['justAbove'] == 1 and beh['low']['justBelow'] > 1, beh['low'])
            for k, v in beh['spd'].items():
                check('[다] %s 이동속도 보정 = 문구' % k, abs(v['shown'] - v['real']) < 1e-9, v)
            for k, v in beh['arm'].items():
                check('[다] %s 받는 피해 깎기 = 문구' % k, v['shown'] == v['real'], v)
            check('[다] 일단즐겨 경험치 = 문구', abs(beh['xp']['shown'] - beh['xp']['real']) < 1e-9, beh['xp'])
            for k, v in beh['mag'].items():
                check('[다] %s 줍는 범위 = 문구' % k, abs(v['shown'] - v['real']) < 1e-9, v)
            check('[다] 배불배불 쿨타임 = 문구', abs(beh['cdr']['shown'] - beh['cdr']['real']) < 1e-9, beh['cdr'])
            check('[다] 용조련사 최대 HP = 문구', beh['hp']['shown'] == beh['hp']['real'], beh['hp'])
            for k, v in beh['regen'].items():
                check('[다] %s 초당 회복 = 문구(1초 동안 실제 회복)' % k, abs(v['shown'] - v['real']) < .06, v)
            check('[다] 김야옹 레벨업 회복 = 문구', beh['lv']['shown'] == beh['lv']['real'], beh['lv'])

            boss = await pg.evaluate("""()=>{const x=__cs,P=window.__p6x,out={};
              const begin=k=>{P.CH_set(k);P.start();const S=P.S;S.spawnT=-1e12;S.nextBoss=S.nextMini=S.evT=S.bigT=S.nextSp=1e12;S.need=1e12;S.propT=S.chickT=1e12;for(const q of P.enemies.a)q.on=false;S.p.hp=S.p.mhp;if(P.CH.k!==k)throw new Error('캐릭터가 안 바뀜 '+k);return S};
              // 프싱: 변신 시간·이동속도·받는 피해·무기 피해
              let S=begin('psg');const m0=x.moveMul(),t0=x.takenMul(),d0=x.dmgMul();P.shvStart();
              out.psg={dur:S.dT,spd:x.moveMul()-m0,red:1-x.takenMul()/t0,dmg:x.dmgMul()/d0-1};
              // 신림: 스탭
              S=begin('sr');S.staffT=.01;for(const a of x.allies.a)a.on=false;P.update(1/30);const al=x.allies.a.filter(a=>a.on);
              out.sr={n:al.length,life:al[0]?al[0].life:0,next:S.staffT,slowR:S.slowR};
              // 또뀨: 진실의 방
              S=begin('ddo');S.proomT=.01;P.update(1/30);out.ddo={hold:S.proom.t,next:S.proomT};
              // 태웅: 돌진
              S=begin('tw');S.dashCd=0;x.taeDash();out.tw={cd:S.dashCd,inv:S.p.inv};
              return out}""")
            sk = boss
            check('[다] 프싱 용 변신 시간·이동속도·받는 피해·무기 피해 = SHV(문구 값)', abs(sk['psg']['dur'] - 11) < 1e-9 and abs(sk['psg']['spd'] - .2) < 1e-9 and abs(sk['psg']['red'] - .3) < 1e-9 and abs(sk['psg']['dmg'] - .2) < 1e-9, sk['psg'])
            check('[다] 신림 스탭 = 2명 · 10초 · 다음 임명 20초 뒤 · 감속 오라 켜짐', sk['sr']['n'] == 2 and 9.9 < sk['sr']['life'] <= 10 and 19.9 < sk['sr']['next'] <= 20 and sk['sr']['slowR'] > 0, sk['sr'])
            check('[다] 또뀨 진실의 방 = 3초 · 다음 방 10초 뒤', 2.9 < sk['ddo']['hold'] <= 3 and 9.9 < sk['ddo']['next'] <= 10, sk['ddo'])
            check('[다] 태웅 돌진 = 2.5초에 한 번 · 0.5초 무적', sk['tw']['cd'] == 2.5 and .4 <= sk['tw']['inv'] <= .5, sk['tw'])
            src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
            check('[다] 게임 코드가 고유스텟 숫자를 CSK 에서 읽는다(옛 글자 상수 0)',
                  all(t in src for t in ['S.staffT=(CSK.staff.every', 'i<CSK.staff.n', 'a.life=(CSK.staff.life', 'spm*=CSK.staff.slow', 'S.proomT=CSK.room.every', 'CSK.room.hold*DUR()', 'S.dashCd=CSK.dash.cd', "invGrant('dash',CSK.dash.inv)", 'critMul=()=>CRIT_BASE+'])
                  and 'S.staffT=20-' not in src and 'S.proomT=10;' not in src and 'S.dashCd=5;' not in src)

            # ── 라 선택 화면
            ui = await pg.evaluate("""()=>{const q=s=>[...document.querySelectorAll(s)];
              const cards=q('#roster .rc').concat(q('#bossRoster .bc'));
              const chips=cards.map(b=>{const c=b.querySelector('.cs');return c?c.textContent:null});
              const lockedWithChip=q('#roster .rc.lock,#bossRoster .bc.lock').filter(b=>b.querySelector('.cs')).length;
              const lockN=q('#roster .rc.lock,#bossRoster .bc.lock').length;
              const desc={};const x=__cs;
              const btn=[...q('#roster .rc'),...q('#bossRoster .bc')];
              for(const b of btn){b.click();desc[b.textContent.slice(0,12)]=document.getElementById('chDesc').innerHTML;}
              document.getElementById('roster').querySelector('.rc').click();
              return {n:cards.length,chips,lockedWithChip,lockN,desc,head:document.querySelector('.rosterH').textContent}}""")
            check('[라] 로스터 카드 18장 전부에 고유스텟 칩', ui['n'] == 18 and all(c and '고유스텟' in c for c in ui['chips']), ui['chips'])
            check('[라] 잠긴 카드(%d장)에도 칩이 보인다' % ui['lockN'], ui['lockN'] >= 10 and ui['lockedWithChip'] == ui['lockN'], (ui['lockN'], ui['lockedWithChip']))
            check('[라] 「없음」 칩 0장 — 18명 전원 능력이 있다', sum('없음' in c for c in ui['chips']) == 0, ui['chips'])
            check('[라] 칩 글자 = 「✨ 고유스텟」 + 핵심 한 줄(예: 치명타 +20%, 외 N)', any('치명타 +20%' in c for c in ui['chips']) and any(re.search(r'외\d', c) for c in ui['chips']), ui['chips'])
            check('[라] 첫 화면 클랜원 머리글에 용어 설명', '고유스텟' in ui['head'], ui['head'])
            # 설명창: 18명 모두 「✨ 고유스텟」 구획 · 고유 무기 문구는 그대로
            bad = []
            for name, html in ui['desc'].items():
                if '✨ 고유스텟' not in html or 'class="cstat"' not in html: bad.append(('구획없음', name))
            check('[라] 선택 설명창 18개 모두 「✨ 고유스텟」 구획(잠긴 캐릭터 포함)', len(ui['desc']) == 18 and not bad, (len(ui['desc']), bad))
            allhtml = ' '.join(ui['desc'].values())
            check('[라] 설명창: 「고유스텟 없음」 문구 0곳', len(re.findall('고유스텟 없음 —', allhtml)) == 0, allhtml.count('고유스텟 없음'))
            check('[라] 고유 무기는 「고유 무기」로 따로 — 설명 문장(ds)에는 고유 무기 표기가 남고 고유스텟 구획 안에는 없다',
                  all(('고유 무기' in re.sub(r'<div class="cstat">.*', '', h, flags=re.S) or '전용 무기' in h) for k, h in ui['desc'].items() if k[:2] not in ('브장', '엄장')) and not re.search(r'class="cstat">[^"]*고유 무기', allhtml.replace('\n', '')) and '고유 무기' not in ''.join(re.findall(r'<div class="cstat">.*?</div></div>', allhtml, flags=re.S)))
            # 용어 통일 — 소스 전체에서 변형 표기 0
            check('[라] 용어 통일 — 「고유 스텟」「고유능력」「고유 능력」「고유 스탯」 표기 0', not re.search(r'고유 스텟|고유 ?능력|고유 ?스탯|고유스탯|고유 ?효과', src), re.findall(r'.{10}(?:고유 스텟|고유 ?능력|고유 ?스탯|고유스탯).{10}', src)[:5])
            # ds 에 숫자 중복이 남지 않았다 — 캐릭터 ds 에서 능력 숫자(%·초당·HP N)가 사라졌는지
            dsd = await pg.evaluate("()=>__cs.CHARS.map(c=>({k:c.k,ds:c.ds}))")
            dup = [(d['k'], m) for d in dsd for m in re.findall(r'[+-]\d+%|초당 HP|HP \d+ 회복|받는 피해 -\d', d['ds'])]
            check('[라] 설명문(ds)에 고유스텟 숫자가 겹쳐 남지 않았다(구획과 모순 0)', not dup, dup)
            # 위험: esc — 구획 HTML 에 원시 < 가 없다(esc 통과)
            check('[라] 구획 HTML 은 esc 를 거친다(모든 행이 태그 없이 글자만)', await pg.evaluate("()=>__cs.CHARS.every(c=>{const h=__cs.cstatHtml(c);return !/&lt;|<script/i.test(h)})"))

            check('[라/마] 첫 화면 오류 0', not errs, errs)
            await ctx.close()

            # ── 마 폰·PC 화면
            VIEWS = [(360, 640, True), (320, 568, True), (412, 915, True), (844, 390, True), (1280, 800, False)]
            MEASURE = """()=>{const q=s=>[...document.querySelectorAll(s)];
              const rh=document.getElementById('roster').getBoundingClientRect().height,bh=document.getElementById('bossRoster').getBoundingClientRect().height;
              const cards=q('#roster .rc,#bossRoster .bc');
              const cardH=cards.map(b=>Math.round(b.getBoundingClientRect().height));
              const chips=q('.cs');let over=0,out=0,ks=0,small=0;const lum=c=>{const a=c.map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
              const rgb=s=>{const m=s.match(/rgba?\\(([^)]+)\\)/);const p=m[1].split(',').map(parseFloat);return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}};
              const eff=el=>{let layers=[];for(let e=el;e;e=e.parentElement){const c=rgb(getComputedStyle(e).backgroundColor);if(c.a>0)layers.push(c);if(c.a>=1)break;}
                let bg={r:14,g:18,b:36};for(const c of layers.reverse()){bg={r:bg.r*(1-c.a)+c.r*c.a,g:bg.g*(1-c.a)+c.g*c.a,b:bg.b*(1-c.a)+c.b*c.a};}return bg};
              const cr=(el)=>{const f=rgb(getComputedStyle(el).color),b=eff(el),op=parseFloat(getComputedStyle(el).opacity)||1;
                const fg={r:f.r*f.a+b.r*(1-f.a),g:f.g*f.a+b.g*(1-f.a),b:f.b*f.a+b.b*(1-f.a)};const L1=lum([fg.r,fg.g,fg.b]),L2=lum([b.r,b.g,b.b]);return (Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05)};
              let minCr=99,minWho='';
              for(const c of chips){const r=c.getBoundingClientRect(),card=c.closest('button').getBoundingClientRect();
                if(c.scrollWidth>c.clientWidth+1)over++;if(r.left<card.left-.5||r.right>card.right+.5)out++;if(getComputedStyle(c).wordBreak!=='keep-all')ks++;
                for(const el of [c,c.querySelector('i')]){const v=cr(el);if(v<minCr){minCr=v;minWho=c.textContent}}}
              for(const b of cards){const r=b.getBoundingClientRect();if(r.width<44||r.height<44)small++;}
              return {rh,bh,tot:rh+bh,cardH,over,out,ks,small,minCr,minWho,sw:document.documentElement.scrollWidth,iw:innerWidth,nchips:chips.length,
                maxCard:Math.max(...cardH)}}"""
            for (w, h, mob) in VIEWS:
                cb, pb, eb = await H.new_page(b, srv.port, w, h, mobile=mob, page=OLD, ready='__cs'); await pb.wait_for_timeout(400)
                mb = await pb.evaluate(MEASURE); await cb.close()
                cn, pn, en = await H.new_page(b, srv.port, w, h, mobile=mob, page=NEW, ready='__cs'); await pn.wait_for_timeout(400)
                mn = await pn.evaluate(MEASURE)
                tag = '%dx%d' % (w, h)
                ratio = mn['tot'] / mb['tot']
                check('[마] %s 가로 넘침 0(페이지 폭 = 화면 폭)' % tag, mn['sw'] <= mn['iw'], (mn['sw'], mn['iw']))
                check('[마] %s 칩 18개 · 글자 넘침 0 · 카드 밖으로 안 나감 · keep-all' % tag, mn['nchips'] == 18 and mn['over'] == 0 and mn['out'] == 0 and mn['ks'] == 0, mn)
                check('[마] %s 목록 높이 증가 %.0f → %.0f px (×%.2f, 한도 ×%.2f)' % (tag, mb['tot'], mn['tot'], ratio, HEIGHT_LIMIT), ratio <= HEIGHT_LIMIT, (mb['tot'], mn['tot']))
                check('[마] %s 가장 큰 카드 %dpx (기준 %dpx 의 1.7배 이내)' % (tag, mn['maxCard'], mb['maxCard']), mn['maxCard'] <= mb['maxCard'] * 1.7, (mn['maxCard'], mb['maxCard']))
                check('[마] %s 칩 글자 대비 %.1f ≥ 4.5 (잠긴 카드 포함)' % (tag, mn['minCr']), mn['minCr'] >= 4.5, (mn['minCr'], mn['minWho']))
                check('[마] %s 카드 터치 대상 44px 이상' % tag, mn['small'] == 0, mn['small'])
                # 설명창 구획 대비·넘침
                dd = await pn.evaluate("""()=>{document.querySelectorAll('#roster .rc')[8].click();const d=document.getElementById('chDesc');const c=d.querySelector('.cstat');const r=c.getBoundingClientRect(),p=d.getBoundingClientRect();
                  return {w:r.width,pw:p.width,over:c.scrollWidth>c.clientWidth+1,sw:document.documentElement.scrollWidth,iw:innerWidth}}""")
                check('[마] %s 설명창 구획이 폭 안에 들어간다' % tag, not dd['over'] and dd['w'] <= dd['pw'] + 1 and dd['sw'] <= dd['iw'], dd)
                check('[마] %s 페이지 오류 0' % tag, not en and not eb, (en, eb))
                await cn.close()

            # 설명창 글자 대비(색 조합 계산) — 구획 본문·강조·이름
            cc = await (await H.new_page(b, srv.port, 360, 640, mobile=True, page=NEW, ready='__cs'))[1].evaluate("""()=>{document.querySelectorAll('#roster .rc')[1].click();
              const lum=c=>{const a=c.map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
              const rgb=s=>{const m=s.match(/rgba?\\(([^)]+)\\)/);const p=m[1].split(',').map(parseFloat);return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}};
              const bgOf=el=>{for(let e=el;e;e=e.parentElement){const c=rgb(getComputedStyle(e).backgroundColor);if(c.a>=.99)return c;}return {r:14,g:18,b:36}};
              const out=[];for(const sel of ['.cstat .cst','.cstat .tx','.cstat .tx>b','.cstat .cv']){const el=document.querySelector(sel);const f=rgb(getComputedStyle(el).color),b=bgOf(el);const L1=lum([f.r,f.g,f.b]),L2=lum([b.r,b.g,b.b]);out.push([sel,(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05)]);}return out}""")
            check('[마] 설명창 구획 글자 대비 ≥ 4.5', all(v >= 4.5 for _, v in cc), cc)

            # ── 바 규칙 불변
            ob = await H.new_page(b, srv.port, 412, 860, page=OLD, ready='__cs'); nb = await H.new_page(b, srv.port, 412, 860, page=NEW, ready='__cs')
            def sigjs(): return "()=>{const P=window.__p6x;P.CH_set('brj');P.start();return {sig:__cs.RES.SIG,keys:Object.keys(P.S).sort(),st:P.state}}"
            so = await ob[1].evaluate(sigjs()); sn = await nb[1].evaluate(sigjs())
            check('[바] 이어하기 서명(RES.SIG) 불변 — %s' % sn['sig'], so['sig'] == sn['sig'] and sn['sig'].startswith('1:'), (so['sig'], sn['sig']))
            check('[바] 새 S 키 0 (%d개 = 기준과 같은 키)' % len(sn['keys']), so['keys'] == sn['keys'], set(so['keys']) ^ set(sn['keys']))
            await ob[0].close(); await nb[0].close()
            await b.close()
    finally:
        srv.close()
    # 새 최상위 let 0
    def lets(t): return set(re.findall(r'^let (\w+)', t, flags=re.M))
    new_src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
    check('[바] 새 최상위 let 0', lets(new_src) == lets(base_src), lets(new_src) ^ lets(base_src))
    # 정적 표(SIG 에 들어가는 표) 안에 CSTAT 가 끼지 않았다
    check('[바] CSTAT 은 TABLES(서명 표) 밖의 별도 const', 'const TABLES={KIND,BOSS,WEAP,PASS,REL,TRD,SM,CO,TIERS,PT,SYN,CHARS,PROP,PICK};' in new_src and 'CSTAT' not in re.search(r'const TABLES=\{[^}]*\}', new_src).group(0))
    for f in (NEW, OLD, 'survivors_cb_cstat_base_src.html'):
        try: os.remove(os.path.join(ROOT, f))
        except OSError: pass
    if not FAST:
        # 규칙 불변 — 비트 비교(정책 봇 · 같은 시드). 브라우저는 A·B 하나씩(동시 2개)
        def equiv(chars):
            cmd = [sys.executable, os.path.join(ROOT, 'tests', 'survivors_equiv.py'), '--a', BASE_COMMIT, '--b', 'survivors.html',
                   '--chars', ','.join(chars), '--seeds', '1', '--cap', '150', '--modes', 'n']
            out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            return out.returncode, (out.stdout + out.stderr).strip().splitlines()
        rc, lines = equiv(SAME)
        check('[바] 규칙 불변 — 안 바뀐 %d명(%s)은 기준 %s 와 비트 동일(150초 · 일반)' % (len(SAME), ','.join(SAME), BASE_COMMIT), rc == 0, '\n'.join(lines[-6:]))
        rc, lines = equiv(CHANGED)
        diff = {c: any(l.startswith('✗') and ('] %s ' % c) in l for l in lines) for c in CHANGED}
        same = [c for c, d in diff.items() if not d and c not in LOWHP_ONLY]
        check('[바] 바뀐 %d명 중 저체력 전용(%s) 말고는 판이 실제로 달라진다(능력이 정말 켜진다) — 안 달라진 캐릭터: %s' % (len(CHANGED), ','.join(LOWHP_ONLY), same or '없음'), not same, '\n'.join(lines[-12:]))
    print('\n%s — 실패 %d건' % ('통과' if not FAILS else '실패', len(FAILS)))
    for f in FAILS: print(' ·', f)
    sys.exit(1 if FAILS else 0)

asyncio.run(main())
