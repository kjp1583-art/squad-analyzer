# -*- coding: utf-8 -*-
"""🧬 빌드 계열 시너지 측정 — 계열 5개의 「대표 빌드」를 같은 조건·같은 시드로 돌려 서로 비교하고, 보너스 없음(전)/있음(후)도 같이 잰다.
   [2026-10-18 사장님 지시 「계열 시너지로 진행해」] 목표: 5계열의 지표가 서로 ±10% 안 · 전체 평균이 크게 오르지 않을 것.
   survivors_charbal_sim.py 의 정책 봇을 그대로 쓴다(여기서는 조건만 바꿔 여러 폴더에 나눠 돌리고 합쳐서 보여 준다).
   쓰는 법
     python3 tests/survivors_lineage_sim.py run --out /tmp/lin/h1 [--mode h] [--seeds 1-8] [--procs 2] [--html survivors.html]
     python3 tests/survivors_lineage_sim.py report --out /tmp/lin/h1
   조건 이름: <계열>+ (보너스 켬) · <계열>- (보너스 끔) · free+ / free- (계열 제한 없이 평소처럼)
   캐릭터: 계열마다 「시작 무기가 그 계열인」 캐릭터를 하나씩 넣어 시작 무기의 유불리를 계열 사이에 고르게 나눈다(brj 탄막 · eom 광역 · ssu 설치 · ddmj 근접 · sr 단일).
"""
import argparse, glob, json, os, subprocess, sys, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import survivors_charbal_sim as C

LINS = ['bar', 'aoe', 'zone', 'mel', 'one']
LNAME = {'bar': '🔫탄막', 'aoe': '💥광역', 'zone': '🧱설치', 'mel': '⚔근접', 'one': '🎯단일', 'free': '자유'}
CHARS = 'brj,eom,ssu,ddmj,sr'
KEYS = ['surv', 'k5', 'k10', 'lv10', 't_lv10', 'dmg5', 'min_hp', 'dealt']   # 보는 지표(survivors_charbal_sim.METRICS 키)


def conds():
    out = []
    for l in LINS + ['free']:
        for on in (True, False):
            out.append((l, on))
    return out


def cname(l, on):
    return l + ('+' if on else '-')


def cmd_run(a):
    env = dict(os.environ)
    if a.mode:
        env['SV_SIM_MODE'] = a.mode
    for l, on in conds():
        if a.only and cname(l, on) not in a.only.split(','):
            continue
        d = os.path.join(a.out, cname(l, on))
        os.makedirs(d, exist_ok=True)
        cmd = ['nice', '-n', '10', sys.executable, os.path.join(HERE, 'survivors_charbal_sim.py'), 'run', '--out', d, '--chars', a.chars, '--seeds', a.seeds,
               '--procs', str(a.procs), '--html', a.html, '--cap', str(a.cap), '--quiet']
        if l != 'free':
            cmd += ['--lin', l]
        if not on:
            cmd += ['--linoff']
        print('▶', cname(l, on), flush=True)
        subprocess.run(cmd, env=env, check=False)


def load(a):
    res = {}
    for l, on in conds():
        d = os.path.join(a.out, cname(l, on))
        rows = [r for r in C.load_rows(d) if 'error' not in r]
        by = {}
        for r in rows:
            by[(r['char'], r['seed'])] = r
        res[cname(l, on)] = by
    return res


def val(r, key):
    for k, nm, hi, fn in C.METRICS:
        if k == key:
            return fn(r)
    raise KeyError(key)


def mean_metric(by, key):
    v = [val(r, key) for r in by.values()]
    v = [x for x in v if x is not None and x < C.INF / 2]
    return statistics.mean(v) if v else None


def cmd_report(a):
    res = load(a)
    names = {k: nm for k, nm, hi, fn in C.METRICS}
    hib = {k: hi for k, nm, hi, fn in C.METRICS}
    print('조건별 판 수:', {k: len(v) for k, v in res.items()})
    for tag, suffix in (('후(보너스 켬)', '+'), ('전(보너스 끔)', '-')):
        print('\n== %s — 계열 대표 빌드 평균 ==' % tag)
        print('%-8s' % '지표' + ''.join('%10s' % LNAME[l] for l in LINS) + '%10s%10s' % ('5평균', '최대편차'))
        for k in KEYS:
            row = [mean_metric(res[l + suffix], k) for l in LINS]
            ok = [x for x in row if x is not None]
            if not ok:
                continue
            m = statistics.mean(ok)
            dev = max(abs(x / m - 1) for x in ok) if m else 0
            print('%-8s' % k + ''.join('%10.1f' % (x if x is not None else float('nan')) for x in row) + '%10.1f%9.0f%%' % (m, dev * 100))
    print('\n== 전→후 변화(%) — 같은 계열 · 같은 캐릭터·시드 ==')
    print('%-8s' % '지표' + ''.join('%10s' % LNAME[l] for l in LINS + ['free']) + '%10s' % '5평균')
    for k in KEYS:
        row = []
        for l in LINS + ['free']:
            a1, b1 = mean_metric(res[l + '+'], k), mean_metric(res[l + '-'], k)
            row.append((a1 / b1 - 1) * 100 if a1 is not None and b1 else None)
        five = [x for x in row[:5] if x is not None]
        print('%-8s' % k + ''.join('%9.1f%%' % x if x is not None else '%10s' % '-' for x in row) + '%9.1f%%' % (statistics.mean(five) if five else 0))
    print('\n(높을수록 좋은 지표: %s / 낮을수록 좋은 지표: %s)' % (','.join(k for k in KEYS if hib[k]), ','.join(k for k in KEYS if not hib[k])))
    # 켜진 계열 단계 — 대표 빌드가 정말 단계를 켰는지
    print('\n== 마지막 계열 단계(무기 수) 분포 — 후 ==')
    for l in LINS:
        c = {}
        for r in res[l + '+'].values():
            t = (r.get('lt') or {}).get(l, 0)
            c[t] = c.get(t, 0) + 1
        print(' ', LNAME[l], dict(sorted(c.items())))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run')
    r.add_argument('--out', required=True)
    r.add_argument('--mode', default='h', help='n|h|v (일반·하드·베리하드). 기본 h')
    r.add_argument('--seeds', default='1-8')
    r.add_argument('--cap', type=float, default=600, help='판 상한(초). 기본 600 = 10분(k15 는 없다)')
    r.add_argument('--procs', type=int, default=2)
    r.add_argument('--chars', default=CHARS)
    r.add_argument('--html', default='survivors.html')
    r.add_argument('--only', default='', help='쉼표 목록(예: bar+,bar-)')
    p = sp.add_parser('report')
    p.add_argument('--out', required=True)
    a = ap.parse_args()
    {'run': cmd_run, 'report': cmd_report}[a.cmd](a)


if __name__ == '__main__':
    main()
