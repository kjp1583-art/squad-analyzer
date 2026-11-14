# -*- coding: utf-8 -*-
"""🧍 꾸미기 파츠 따라붙기 시험(2026-11-14 「캐릭터가 움직일 때 꾸미기가 어긋난다」) — 병아리 시트 칸마다 머리 기준점(cx·cy·r)과 몸통 기준점(bx·by)이 있고,
몸통·등 이미지 파츠(parts.json rel=body)는 몸통 기준점을, 머리·얼굴 파츠(rel=head)는 머리 기준점을 따라간다. 사용: python3 tests/brjhunt_parts_anchor_test.py"""
import json, os, sys
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
A = json.load(open(os.path.join(R, 'img/brjhunt/v2/chick_anchors.json'), encoding='utf-8'))
P = json.load(open(os.path.join(R, 'img/brjhunt/parts/parts.json'), encoding='utf-8'))
n = bad = 0; dx = []; dy = []
for sheet, frames in A.items():
    for f in frames:
        if not f: continue
        n += 1
        if 'bx' not in f or 'by' not in f: bad += 1; continue
        dx.append((f['bx'] - f['cx']) / f['r']); dy.append((f['by'] - f['cy']) / f['r'])
ok(n > 20 and bad == 0, f'모든 칸({n})에 몸통 기준점 bx·by 가 있다')
ok(min(dx) > -0.9 and max(dx) < 0.9 and 0.8 < min(dy) and max(dy) < 1.9, f'몸통 기준점이 머리 아래 정상 범위 (가로 {min(dx):.2f}~{max(dx):.2f}r · 세로 {min(dy):.2f}~{max(dy):.2f}r)')
ok(max(dx) - min(dx) > 0.25, f'몸통이 머리에 대해 실제로 움직인다(가로 폭 {max(dx) - min(dx):.2f}r) — 머리 기준 고정이면 어긋나는 이유')
parts = {k: v for k, v in P.items() if not k.startswith('_')}
ok(all(v.get('rel') == ('body' if v['slot'] in ('body', 'back') else 'head') for v in parts.values()), f'파츠 {len(parts)}종: 몸통·등은 rel=body · 머리·얼굴은 rel=head')
ok('bx' in P['_head'] and 'by' in P['_head'], 'parts.json 에 기본 병아리의 몸통 기준점이 적혀 있다')
src = open(os.path.join(R, 'brjhunt_arena.js'), encoding='utf-8').read()
ok("m.rel === 'body'" in src and 'g.bx' in src and 'bx: ((pa.bx' in src, '엔진이 몸통 파츠를 몸통 기준점(bx·by)에 그린다')
print('ALL PASS' if not fails else f'FAIL {len(fails)}'); sys.exit(1 if fails else 0)
