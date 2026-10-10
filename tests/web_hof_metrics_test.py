# -*- coding: utf-8 -*-
"""📊 명예의 전당 상세지표(DPM·GPM·분당 CS) — 지표 팩의 게임 시간(m)이 잘못 기록된 행을 되돌린다.
[2026-10-10 사장님 제보 「일단즐겨 서포터 웹 명예의 전당 DPM 랭킹이 이상하다」]
원인: 2026-09-19·09-22 다섯 판(50행)의 지표 팩은 m 칸에 게임 시간(분)이 아니라 분당 CS 가 들어 있었다(선수마다 0.86·6.6·9.45 …).
서폿 딜량 17,444 ÷ 0.86 = DPM 20,284 가 평균에 섞여 58판 평균 DPM 이 1,291(원딜 순위권)로 부풀었다. cs÷m 은 판마다 같은 값(26.67 …)이고 그게 진짜 게임 시간이다.
규칙(parseMetrics): 분당 CS 는 12.4 를 넘을 수 없으니 cs÷m > 14 이면 m = cs÷m (8~90분이 아니면 그 행의 지표를 버린다). 서식이 아니라 값으로 가린다 — 9/8 에 「vs 없는 행」으로 골라 멀쩡한 140행을 망가뜨린 일이 있었다.
  A. parseMetrics 단위: 되돌릴 행 · 건드리면 안 되는 행(정상 · 구서식 정상 · 경계) · 버릴 행
  B. 가짜 시트(정상 6판 + 망가진 1판)로 명예의 전당을 열어: 서폿 DPM 이 400 근처(2,057 이 아니다) · 원딜 1,100 · GPM·CS 도 정상
시트 스냅샷 없이 도는 합성 시험이다(가짜 닉네임·가짜 숫자만).  python3 tests/web_hof_metrics_test.py [--src index.html]
"""
import argparse, asyncio, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'web_replay'))
import replay as R

COLS = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
POS = ['탑', '정글', '미드', '원딜', '서폿']
# 포지션별 한 판 값: (cs, 골드, 딜량, 받은 피해) — 게임 시간 M=30분
STAT = {'탑': (210, 12600, 21000, 24000), '정글': (170, 12000, 15000, 22000), '미드': (240, 13500, 27000, 18000),
        '원딜': (270, 15000, 33000, 16000), '서폿': (30, 9000, 12000, 20000)}
M = 30.0
GOOD_GAMES = 6


def make_xlsx(path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = 'CLASSIC_NORMAL'
    ws.append(COLS)
    n = 0
    for gi in range(GOOD_GAMES + 1):
        gid = '#70000%02d' % (gi + 1)
        bad = gi == GOOD_GAMES   # 마지막 판: m 칸에 분당 CS 가 들어간 옛 서식
        blue_wins = gi % 2 == 0
        for team in (0, 1):
            for pi, pos in enumerate(POS):
                n += 1
                cs, gold, dmg, dt = STAT[pos]
                k, d, a = 3 + pi, 2 + (pi % 3), 4 + pi
                if bad:
                    pack = 'g%d|cs%d|m%.2f|kp50.0|cw2|wp10|wk2|dt%d' % (gold, cs, cs / M, dt)   # 옛 서식(vs·op·tk 없음) + m 이 분당 CS
                else:
                    pack = 'g%d|cs%d|m%.1f|kp50|vs20|cw2|wp10|wk2|op0|tk1|dt%d|hs0|dr0|br0|pk3' % (gold, cs, M, dt)
                win = (team == 0) == blue_wins
                ws.append([gid, '2026-10-%02d 21:00' % (gi + 1), '시험가%d#KR%d' % (team * 5 + pi + 1, team + 1), 'test-puuid-%d' % (team * 5 + pi + 1),
                           '블루팀' if team == 0 else '레드팀', pos, '시험챔프%d' % (pi + 1), None, '승리' if win else '패배', None, 'v16.20',
                           '%d/%d/%d' % (k, d, a), 20.0 + pi, float(dmg), None, None, None, None, pack])
    wb.save(path)


JS_A = r"""(()=>{
  const P=s=>parseMetrics({"지표":s});
  const r=(o)=>o?+o.m.toFixed(2):null;
  return {
    fixSupp: r(P('g7631|cs23|m0.86|kp55.0|cw10|wp35|wk10|dt22169')),          // 26.74 로 되돌림
    fixADC:  r(P('g15918|cs252|m9.45|kp71.43|cw0|wp5|wk4|dt16745')),          // 26.67
    fixLow:  r(P('g5424|cs17|m0.7|kp50.0|cw6|wp31|wk5|dt14330')),             // 24.29
    okNew:   r(P('g12468|cs51|m28.9|kp71|vs99|cw12|wp37|wk13|op0|tk2|dt18742|hs439|dr0|br0|pk5')),
    okOldFmt:r(P('g8610|cs150|m26.5|kp30.0|cw2|wp4|wk4|dt33385')),            // vs 없는 옛 서식이어도 정상 행은 그대로(9/8 사고)
    okFast:  r(P('g17000|cs330|m27.0|kp50|vs20|dt20000')),                    // 분당 CS 12.2 — 정상 중 가장 높은 쪽
    edge:    r(P('g9000|cs196|m14.0|kp50|vs20|dt20000')),                      // 14.0분에 196 → 분당 14.0 : 경계(14 초과 아님)는 그대로
    dropBig: r(P('g9000|cs100|m1.0|kp50|vs20|dt20000')),                       // 되돌린 값 100분 → 버림(null)
    dropTiny:r(P('g9000|cs100|m5.0|kp50|vs20|dt20000')),                       // 되돌린 값 20분 → 정상 범위라 20.0 으로 되돌림
    noCs:    r(P('m0.5|kp50')),                                                // cs 없음 — 건드리지 않음(0.5 그대로)
    wait:    parseMetrics({"지표":"기록 대기"}),
  };
})()"""

JS_B = r"""(async()=>{
  go('hof','rift');
  for(let i=0;i<80;i++){ await new Promise(r=>setTimeout(r,400)); if([...document.querySelectorAll('.hof-grid .card h2')].some(h=>/DPM/.test(h.textContent))) break; }
  const out={};
  for(const h of document.querySelectorAll('.hof-grid .card h2')){
    const t=h.textContent.replace(/\s+/g,' ').trim();
    if(/DPM|GPM|분당 CS/.test(t)){ out[/DPM/.test(t)?'DPM':/GPM/.test(t)?'GPM':'CS']=[...h.parentElement.querySelectorAll('.hof-row')].map(r=>r.textContent.replace(/\s+/g,' ').trim()); }
  }
  return out;
})()"""


def num(s):
    import re
    m = re.search(r'분당\s*([\d,\.]+)', s)
    return float(m.group(1).replace(',', '')) if m else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(HERE, '..', 'index.html'))
    a = ap.parse_args()
    fails = []

    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg)
        if not c:
            fails.append(msg)
    tmp = tempfile.mkdtemp(prefix='hofm_')
    xl = os.path.join(tmp, 'fake.xlsx')
    make_xlsx(xl)
    res = await R.replay(os.path.abspath(a.src), xlsx=xl, out=None, shots=False, cats=('rift',), viewport=(430, 960), quiet=True,
                         evals=[JS_A, JS_B], timeout_s=300)
    A, B = res['evals']
    print('A', json.dumps(A, ensure_ascii=False))
    print('B', json.dumps(B, ensure_ascii=False)[:900])
    ok(abs(A['fixSupp'] - 26.74) < 0.02, 'A1 m 칸이 분당 CS 인 서폿 행(cs23·m0.86)이 게임 시간 26.74분으로 되돌아온다 (%s)' % A['fixSupp'])
    ok(abs(A['fixADC'] - 26.67) < 0.02, 'A2 원딜 행(cs252·m9.45) → 26.67분 (%s)' % A['fixADC'])
    ok(abs(A['fixLow'] - 24.29) < 0.02, 'A3 cs 가 작은 행(cs17·m0.7) → 24.29분 (%s)' % A['fixLow'])
    ok(A['okNew'] == 28.9 and A['okOldFmt'] == 26.5 and A['okFast'] == 27.0, 'A4 정상 행은 서식이 새것이든 옛것(vs 없음)이든 그대로다 (%s · %s · %s)' % (A['okNew'], A['okOldFmt'], A['okFast']))
    ok(A['edge'] == 14.0, 'A5 경계(분당 CS 14.0)는 그대로 둔다 (%s)' % A['edge'])
    ok(A['dropBig'] is None, 'A6 되돌린 값이 90분을 넘는 행(cs100·m1.0)은 지표를 버린다 (%s)' % A['dropBig'])
    ok(A['dropTiny'] == 20.0, 'A7 cs100·m5.0 → 20.0분 (정상 범위라 되돌린다) (%s)' % A['dropTiny'])
    ok(A['noCs'] == 0.5 and A['wait'] is None, 'A8 cs 가 없으면 건드리지 않고, 「기록 대기」는 그대로 null (%s · %s)' % (A['noCs'], A['wait']))
    dpm = B.get('DPM') or []
    gpm = B.get('GPM') or []
    csp = B.get('CS') or []
    ok(len(dpm) == 10, 'B0 DPM 카드에 10칸이 찬다 (%d)' % len(dpm))
    supp = [num(x) for x in dpm if '서폿' in x]
    adc = [num(x) for x in dpm if '원딜' in x]
    ok(supp and all(abs(v - 400) <= 8 for v in supp), 'B1 서폿 DPM 이 400 근처다(망가진 판이 안 섞였다 — 안 고치면 2,057) %s' % supp)
    ok(adc and all(abs(v - 1100) <= 22 for v in adc), 'B2 원딜 DPM 이 1,100 근처다 %s' % adc)
    ok(dpm and '원딜' in dpm[0] and '원딜' in dpm[1], 'B3 1·2위는 원딜(서폿이 위로 올라오지 않는다) %s' % dpm[:2])
    ok(gpm and all(abs((num(x) or 0) - (500 if '원딜' in x else 300 if '서폿' in x else {'탑': 420, '정글': 400, '미드': 450}.get(x.split('(')[-1].split('·')[-1].rstrip(')'), 0))) <= 12 for x in gpm if num(x)),
       'B4 GPM 도 정상이다 (원딜 500G · 서폿 300G …) %s' % gpm[:4])
    ok(csp and abs((num(csp[0]) or 0) - 9.0) <= 0.2 and '원딜' in csp[0], 'B5 분당 CS 1위는 원딜 9.0개다 (%s)' % csp[:1])
    errs = res['meta']['log']['pageerror']
    ok(not errs, 'C 페이지 오류 0 %s' % errs[:3])
    print('\n결과: %s (%d건 실패)' % ('통과' if not fails else '실패', len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
