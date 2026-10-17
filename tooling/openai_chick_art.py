#!/usr/bin/env python3
"""🎨 OpenAI 이미지 API 로 브장신 병아리 캐릭터 그림 뽑기 → 초록 배경 제거 → 256px WebP (CLAUDE.md 「그림」 절 참고)
사용: python3 tooling/openai_chick_art.py "<소품 영어 문구>" 출력접두 [장수=3]
  예: python3 tooling/openai_chick_art.py "wearing polka-dot briefs on its head, holding a loot sack" /tmp/x/pty 3
  → /tmp/x/pty_1.png … (초록 배경 원본) · 마음에 드는 것을 골라:  python3 tooling/openai_chick_art.py --cut /tmp/x/pty_1.png img/survivors/char_<키>.webp
키는 환경에 없다 — 세션 프록시가 api.openai.com 호출에 인증을 붙인다. 투명 배경 옵션은 이 모델이 못 쓴다(그래서 초록 배경 + 제거)."""
import sys, subprocess, json, base64, os
from collections import deque
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'img', 'brjang', 'parts', 'body_chick', 'front.png')

def gen(prop, out):
    prompt = ("Keep this yellow chick character exactly as it is — same head shape, face, cheeks, beak, feet, outline and art style — and it is %s. "
              "Front view, full body, centered, on a solid flat bright green (#00ff00) background with no shadow, same art style as the original, no text, no letters, no numbers." % prop)
    r = subprocess.run(['curl', '-sS', '--max-time', '100', '-X', 'POST', 'https://api.openai.com/v1/images/edits',
                        '-F', 'model=gpt-image-2', '-F', 'image=@' + SRC, '-F', 'quality=low', '-F', 'size=1024x1024',
                        '-F', 'output_format=png', '-F', 'prompt=' + prompt], capture_output=True, text=True)
    try: j = json.loads(r.stdout)
    except Exception: return 'RAW ' + r.stdout[:200] + r.stderr[:200]
    if 'data' not in j: return json.dumps(j)[:300]
    open(out, 'wb').write(base64.b64decode(j['data'][0]['b64_json'])); return 'ok'

def cut(src, dst):
    from PIL import Image, ImageFilter
    import numpy as np
    im = Image.open(src).convert('RGB'); a = np.array(im).astype(int)
    bg = ((a[..., 1] - np.maximum(a[..., 0], a[..., 2])) > 70) & (a[..., 1] > 150)
    H, W = bg.shape; vis = np.zeros_like(bg); dq = deque()
    for x in range(W):
        for y in (0, H - 1):
            if bg[y, x]: dq.append((y, x)); vis[y, x] = 1
    for y in range(H):
        for x in (0, W - 1):
            if bg[y, x]: dq.append((y, x)); vis[y, x] = 1
    while dq:   # 가장자리와 이어진 초록만 지운다(외곽선 안쪽 색은 건드리지 않는다)
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and bg[ny, nx] and not vis[ny, nx]: vis[ny, nx] = 1; dq.append((ny, nx))
    am = Image.fromarray(np.where(vis, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    o = np.array(im).astype(int); edge = np.array(am) < 250
    fix = edge & ((o[..., 1] - np.maximum(o[..., 0], o[..., 2])) > 0)
    o[..., 1] = np.where(fix, np.maximum(o[..., 0], o[..., 2]), o[..., 1])   # 가장자리 초록 번짐 제거
    res = Image.fromarray(o.astype(np.uint8)).convert('RGBA'); res.putalpha(am)
    bb = res.getbbox(); cw = max(bb[2] - bb[0], bb[3] - bb[1]); pad = int(cw * .05); cx = (bb[0] + bb[2]) // 2; cy = (bb[1] + bb[3]) // 2; h = cw // 2 + pad
    res.crop((cx - h, cy - h, cx + h, cy + h)).resize((256, 256), Image.LANCZOS).save(dst, quality=90)
    print('saved', dst, os.path.getsize(dst), 'bytes')

if __name__ == '__main__':
    if sys.argv[1] == '--cut': cut(sys.argv[2], sys.argv[3])
    else:
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex:
            for i, res in enumerate(ex.map(lambda k: gen(sys.argv[1], '%s_%d.png' % (sys.argv[2], k)), range(1, n + 1)), 1): print(i, res)
