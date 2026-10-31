#!/usr/bin/env python3.13
"""img/brjhunt/v2/manifest.json 시험 — 모든 파일이 있고, 시트 크기 = w×frames · h, 알파가 있고, 앵커가 안에 있고, 필요한 이름이 다 있고, 총 용량 ≤ 2.5MB."""
import os, sys, json
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'img', 'brjhunt', 'v2')
man = json.load(open(os.path.join(D, 'manifest.json')))
bad = []
def chk(c, msg):
    if not c: bad.append(msg)
need = ['chick_idle', 'chick_run', 'chick_jump', 'chick_fall', 'chick_hurt', 'chick_attack1', 'chick_attack2', 'chick_attack3', 'chick_cast', 'chick_die',
        'fxSlash1', 'fxSlash2', 'fxSlash3', 'fxImpact', 'fxCrit', 'fxDust', 'fxCoin']
need += ['sk_' + k for k in 'slash peck spin bomb thunder fire egg shield shrimp storm'.split()]
for i in range(1, 7):
    need += ['m%d_%s' % (i, s) for s in ('walk', 'hit', 'die')] + ['%s%d' % (s, i) for s in ('ground', 'plat', 'block', 'far', 'near')]
for n in need: chk(n in man, '빠짐: ' + n)
total = 0
for n, m in man.items():
    for k in ('file', 'frames', 'w', 'h', 'fps', 'anchor'): chk(k in m, '%s: %s 없음' % (n, k))
    p = os.path.join(D, m.get('file', '_none_')); chk(os.path.exists(p), '%s: 파일 없음' % n)
    if not os.path.exists(p): continue
    total += os.path.getsize(p)
    im = Image.open(p); chk(im.size == (m['w'] * m['frames'], m['h']), '%s: 크기 %s != %dx%d×%d프레임' % (n, im.size, m['w'], m['h'], m['frames']))
    ax, ay = m['anchor']; chk(0 <= ax <= m['w'] and 0 <= ay <= m['h'], '%s: 앵커 밖 %s' % (n, m['anchor']))
    if n.startswith('far'): continue
    a = im.convert('RGBA').getchannel('A'); lo, hi = a.getextrema()
    chk(lo < 10 and hi > 240, '%s: 알파가 없다(투명 %d~%d)' % (n, lo, hi))
    for f in range(m['frames']):      # 빈 프레임 금지
        fa = a.crop((f * m['w'], 0, (f + 1) * m['w'], m['h'])); chk(fa.point(lambda v: 255 if v > 24 else 0).getbbox() is not None, '%s: %d번 프레임이 비었다' % (n, f))
chk(total <= 2.5 * 1024 * 1024, '총 용량 %.2fMB > 2.5MB' % (total / 1048576))
print('항목 %d · 총 %.2fMB' % (len(man), total / 1048576))
if bad: print('\n'.join('FAIL ' + b for b in bad)); sys.exit(1)
print('OK brjhunt_art_test')
