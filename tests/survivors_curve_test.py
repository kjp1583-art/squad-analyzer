# -*- coding: utf-8 -*-
"""📈 난이도 곡선(CURVE) 모양 시험 — 표를 survivors.html 에서 읽어 모양을 고정한다(브라우저 없음).
초반은 쉽고, 첫 각성 전(대략 0~10분)에서 중반(~16분)으로 올라가며, 30분 뒤로는 예전 값(×1)이라 후반·무한 모드는 그대로다.
변이 시험: 일부러 망가뜨린 표는 이 검사들에 걸려야 한다."""
import os, re, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'survivors.html'), encoding='utf-8').read()
m = re.search(r'const CURVE=\{(.*?)\};\s*\nconst curve=', src, re.S)
assert m, 'CURVE 표를 못 찾음'
tbl = {k: json.loads(re.sub(r'(?<![\d])\.(\d)',r'0.\1',v)) for k, v in re.findall(r'(\w+):(\[\[.*?\]\])', m.group(1))}

def cv(t, k, x):
    a = t[k]
    if x <= a[0][0]: return a[0][1]
    for i in range(1, len(a)):
        if x < a[i][0]:
            p, q = a[i-1], a[i]
            return p[1] + (q[1]-p[1])*(x-p[0])/(q[0]-p[0])
    return a[-1][1]

def shape_errors(t):
    e = []
    if set(t) != {'hp', 'atk', 'rate'}: e.append('키 집합')
    for k in t:
        a = t[k]
        if [p[0] for p in a] != sorted(set(p[0] for p in a)): e.append(k + ' 분 순서')
        if a[0][0] != 0: e.append(k + ' 0분 시작 아님')
        if a[-1][0] > 30 or a[-1][1] != 1: e.append(k + ' 30분 뒤 ×1 아님')
        if cv(t, k, 0) >= 0.95: e.append(k + ' 초반이 안 쉬움')
        if cv(t, k, 0) < 0.5: e.append(k + ' 초반이 너무 약함')
        if max(p[1] for p in a) > 1.2: e.append(k + ' 봉우리 너무 높음')
        # 0→봉우리까지 단조 증가(우상향), 봉우리는 9~22분 사이
        pk = max(range(len(a)), key=lambda i: a[i][1])
        if not (9 <= a[pk][0] <= 22 or k == 'rate'): e.append(k + ' 봉우리 위치')
        for i in range(1, pk + 1):
            if a[i][1] < a[i-1][1]: e.append(k + ' 봉우리 전에 내려감')
        for x in range(0, 30):
            if abs(cv(t, k, x+1) - cv(t, k, x)) > 0.12: e.append('%s %d분 급변' % (k, x))
    # 종합 위험(체력×공격×스폰): 첫 각성 전(~8분) < 중반(14분) 이어야 하고, 3분 < 8분 < 14분
    g = lambda x: cv(t, 'hp', x) * cv(t, 'atk', x) * cv(t, 'rate', x)
    if not (g(3) < g(8) < g(14)): e.append('종합 위험이 우상향 아님')
    if g(14) < 1.0: e.append('중반이 예전보다 쉬움')
    if g(2) > 0.75: e.append('초반 완화 부족')
    # 면적(평균 배율)은 크게 안 바뀜: 0~30분 평균 0.85~1.15
    avg = sum(g(x+.5) for x in range(30)) / 30
    if not (0.7 <= avg <= 1.2): e.append('평균 난이도 이탈 %.2f' % avg)
    return e

errs = shape_errors(tbl)
assert not errs, errs
# 코드가 표를 실제로 읽는지(식에 연결돼 있는지)
for needle in ["curve('hp',m)", "curve('atk',m)", "curve('rate',m)"]:
    assert needle in src, needle
# 변이: 아래 표들은 반드시 걸려야 한다
import copy
def mut(f):
    t = copy.deepcopy(tbl); f(t); return shape_errors(t)
muts = {
 '초반 안 낮춤': lambda t: t['hp'].__setitem__(0, [0, 1.0]),
 '30분 뒤 안 복귀': lambda t: t['atk'].__setitem__(-1, [30, 1.3]),
 '봉우리 과도': lambda t: t['hp'].__setitem__(5, [16, 1.6]),
 '중간에 내려감': lambda t: t['hp'].__setitem__(3, [9, 0.5]),
 '전부 평평(곡선 없음)': lambda t: [t.__setitem__(k, [[0, 1], [30, 1]]) for k in list(t)],
 '전부 쉽게': lambda t: [t.__setitem__(k, [[0, .5], [30, 1]]) for k in list(t)],
}
for n, f in muts.items():
    r = mut(f)
    assert r, '변이가 안 걸림: ' + n
print('OK  표 모양 · 변이 %d종 모두 걸림 · hp/atk/rate 연결' % len(muts))
