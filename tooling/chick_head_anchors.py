#!/usr/bin/env python3.13
"""🐥 병아리 시트(img/brjhunt/v2/chick_*.webp) 한 칸마다 머리 위치를 재서 img/brjhunt/v2/chick_anchors.json 으로 저장한다.
꾸미기 파츠(왕관·안경·목도리·망토 …)가 움직이는 병아리 머리에 붙어 따라다니게 하는 좌표표다. 시트 그림을 바꾸면 다시 돌린다:  python3.13 tooling/chick_head_anchors.py
칸마다 {cx, cy, r, ex, ey} = 머리 중심 · 반지름 · 눈 중심 (칸 안 픽셀 좌표). 몸통은 노랑, 칼은 갈색, 눈은 짙은 색이라 색으로 가른다."""
import json, os
import numpy as np
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'img', 'brjhunt', 'v2')
man = json.load(open(os.path.join(D, 'manifest.json'), encoding='utf-8'))
out = {}
for name, m in man.items():
    if not name.startswith('chick_') or not isinstance(m, dict) or not m.get('file'): continue
    im = np.array(Image.open(os.path.join(D, m['file'])).convert('RGBA')).astype(int)
    fw, fh, n = m['w'], m['h'], m['frames']; frames = []
    for f in range(n):
        c = im[:, f * fw:(f + 1) * fw]; a = c[..., 3] > 128
        yel = a & (c[..., 0] > 225) & (c[..., 1] > 190) & (c[..., 2] > 100) & (c[..., 2] < 215)
        ys = np.where(yel.any(1))[0]
        if not len(ys): frames.append(None); continue
        top = ys[0]; span = max(1, ys[-1] - top); best = (0, top, 0)
        for y in range(top, top + int(span * 0.38) + 1):
            xs = np.where(yel[y])[0]
            if len(xs) and xs[-1] - xs[0] > best[0]: best = (xs[-1] - xs[0], y, (xs[0] + xs[-1]) / 2)
        wdt, wy, cx = best; r = wdt / 2.0; cy = top + r
        dark = a & (c[..., 0] < 90) & (c[..., 1] < 80) & (c[..., 2] < 110)
        yy, xx = np.mgrid[0:fh, 0:fw]; inside = ((xx - cx) ** 2 + (yy - cy) ** 2 < (r * 0.85) ** 2) & dark & (yy > cy - r * 0.35) & (yy < cy + r * 0.3)
        if inside.sum() > 6: ex, ey = float(xx[inside].mean()), float(yy[inside].mean())
        else: ex, ey = cx, cy + r * 0.1
        # 🧍 [2026-11-14 사장님 「캐릭터가 움직일 때 꾸미기가 어긋난다」] 몸통 파츠(드레스·셔츠·튜브)는 머리가 아니라 몸통을 따라가야 한다 — 달리기·공격에서 몸은 머리 대비 최대 0.4r 가로 · 0.3r 세로로 움직인다.
        #   몸통 기준점 = 머리 바로 아래 띠(머리 중심 아래 1.0r~1.9r · 가로 ±1.0r)에 있는 노랑 화소의 무게중심. 잡히지 않으면 머리 기준(cy+1.25r)으로.
        yy2, xx2 = np.mgrid[0:fh, 0:fw]; band = yel & (yy2 > cy + 1.0 * r) & (yy2 < cy + 1.9 * r) & (abs(xx2 - cx) < 1.0 * r)
        if band.sum() >= 20: bx, by = float(xx2[band].mean()), float(yy2[band].mean())
        else: bx, by = float(cx), float(cy + 1.25 * r)
        frames.append({'cx': round(float(cx), 1), 'cy': round(float(cy), 1), 'r': round(float(r), 1), 'ex': round(ex, 1), 'ey': round(ey, 1), 'bx': round(bx, 1), 'by': round(by, 1)})
    rs = sorted(f['r'] for f in frames if f)    # 같은 시트는 머리 크기가 거의 같다 — 중앙값에서 ±15% 안으로 눌러 팔·칼 때문에 튄 값을 바로잡는다
    if rs:
        med = rs[len(rs) // 2]; top_by = None
        for f in frames:
            if not f: continue
            r0 = f['r']; r1 = min(max(r0, med * 0.85), med * 1.15)
            if r1 != r0: f['cy'] = round(f['cy'] - r0 + r1, 1); f['r'] = round(r1, 1)
    out[name] = frames
json.dump(out, open(os.path.join(D, 'chick_anchors.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print({k: len(v) for k, v in out.items()})
