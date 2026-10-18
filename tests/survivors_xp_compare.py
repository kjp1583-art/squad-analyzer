# -*- coding: utf-8 -*-
"""📊 패시브 고정 빌드 비교표 — survivors_charbal_sim.py run --preset 으로 뽑은 폴더들을 나란히 놓고 본다.
[2026-10-18 공부·획득 범위 개편] 목표: 공부·획득 범위 빌드의 가치가 근성(might) 빌드의 7~8할.

폴더 모양: ROOT/<빌드이름>/runs.*.jsonl  (빌드마다 같은 캐릭터·같은 시드로 돌린 것)
사용: python3 tests/survivors_xp_compare.py ROOT [--ref none] [--unit might5] [--build 이름,이름] [--json 파일]
  · 지표별 중앙값 표 · 같은 (캐릭터, 시드) 짝끼리의 평균 차이(기준 ref 대비)와 부트스트랩 95% 신뢰구간 · 「근성의 몇 할」 환산
  · 한 지표만 보지 말 것: 처치@5/10/15분 · 레벨 · 받은 피해 · 최저 HP · 생존 시간 · 치킨 줍기 수를 같이 본다
"""
import argparse, glob, json, os, random, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import survivors_charbal_sim as S

KEYS = [('surv', '생존 시간(초)'), ('k5', '처치@5분'), ('k10', '처치@10분'), ('k15', '처치@15분'), ('lv10', '레벨@10분'), ('lvend', '마지막 레벨'),
        ('t_lv5', 'Lv5 도달(초)'), ('t_lv10', 'Lv10 도달(초)'), ('dmg5', '첫5분 받은 피해'), ('min_hp', '최저 HP비율'), ('dealt', '준 피해 합'),
        ('pk_chk', '치킨 줍기'), ('pk_bomb', '폭탄 줍기'), ('pk_mag', '다이아 줍기'), ('d_study', '깨달음 파동 피해')]
HEAD = ['surv', 'k10', 'k15', 'lvend', 'dealt']      # 「근성의 몇 할」 환산에 쓰는 대표 지표
FN = {k: f for k, nm, hib, f in S.METRICS}


def load(d):
    rows = {}
    for f in glob.glob(os.path.join(d, 'runs*.jsonl')):
        for ln in open(f, encoding='utf-8'):
            ln = ln.strip()
            if not ln: continue
            r = json.loads(ln)
            if r.get('errs'): continue
            rows[(r['char'], r['seed'])] = r
    return rows


def val(r, k):
    try:
        v = FN[k](r)
    except Exception:
        return None
    if v is None or v >= S.INF / 2: return None
    return v


def boot(xs, n=2000, seed=1):
    rnd = random.Random(seed); m = len(xs)
    if m < 2: return (None, None)
    ms = sorted(sum(xs[rnd.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return (ms[int(.025 * n)], ms[int(.975 * n)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('--ref', default='none'); ap.add_argument('--unit', default='might5')
    ap.add_argument('--build', default=None); ap.add_argument('--json', default=None)
    a = ap.parse_args()
    names = [n for n in sorted(os.listdir(a.root)) if os.path.isdir(os.path.join(a.root, n))]
    if a.build: names = [n for n in a.build.split(',') if n in names]
    D = {n: load(os.path.join(a.root, n)) for n in names}
    ref = D.get(a.ref); unit = D.get(a.unit)
    if ref is None: sys.exit('기준 빌드(%s) 폴더가 없다' % a.ref)
    out = {}
    print('[빌드별 중앙값]  n = 판 수')
    print('  %-14s %4s | ' % ('빌드', 'n') + ' | '.join('%s' % nm for k, nm in KEYS))
    for n in names:
        row = {}
        cells = []
        for k, nm in KEYS:
            v = [x for x in (val(r, k) for r in D[n].values()) if x is not None]
            m = statistics.median(v) if v else None
            row[k] = m
            cells.append('-' if m is None else ('%.2f' % m if k == 'min_hp' else '%.0f' % m))
        out[n] = {'n': len(D[n]), 'med': row}
        print('  %-14s %4d | ' % (n, len(D[n])) + ' | '.join(cells))
    print()
    print('[기준(%s) 대비 짝 차이]  같은 캐릭터·같은 시드끼리 뺀 평균 (95%% 신뢰구간) — 처치·레벨·준 피해는 클수록, 받은 피해·Lv도달 초는 작을수록 좋다' % a.ref)
    delta = {}
    for n in names:
        if n == a.ref: continue
        delta[n] = {}
        print(' ' + n)
        for k, nm in KEYS:
            d = []
            for key, r in D[n].items():
                q = ref.get(key)
                if q is None: continue
                x, y = val(r, k), val(q, k)
                if x is None or y is None: continue
                d.append(x - y)
            if not d: continue
            mu = sum(d) / len(d); lo, hi = boot(d)
            delta[n][k] = mu
            sig = '' if lo is None else (' ★' if (lo > 0 or hi < 0) else '')
            print('    %-14s %+10.2f  (%+.2f ~ %+.2f)  n=%d%s' % (nm, mu, lo if lo is not None else 0, hi if hi is not None else 0, len(d), sig))
    if unit is not None and a.unit in delta:
        print('\n[근성(%s)의 몇 할?]  (빌드 − 기준) ÷ (%s − 기준) · 대표 지표 %s' % (a.unit, a.unit, ', '.join(HEAD)))
        for n in names:
            if n in (a.ref, a.unit) or n not in delta: continue
            rs = []
            for k in HEAD:
                u = delta[a.unit].get(k); b = delta[n].get(k)
                if u in (None, 0) or b is None: continue
                rs.append('%s %.0f%%' % (dict(KEYS)[k], 100 * b / u))
            print('  %-14s ' % n + ' · '.join(rs))
    if a.json:
        json.dump({'med': out, 'delta': delta}, open(a.json, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
