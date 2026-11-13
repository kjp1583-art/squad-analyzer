#!/usr/bin/env python3.13
"""🐥 [실험 — 적용 안 함] 병아리 시트 사이사이에 중간 프레임을 만들어 움직임을 부드럽게 한다 (2026-11-13 사장님 「각 움직임 사이사이 프레임 이미지 추가」).
광학 흐름(OpenCV Farneback)으로 이웃한 두 칸을 서로 향해 반만큼 휘어 합친 중간 칸을 만든다 — 그림을 새로 그리는 게 아니라 있는 그림을 보간한다.
사용: python3.13 tooling/chick_tween.py [--preview 폴더]   (opencv-python-headless · numpy · Pillow 필요)
 · 원본 시트는 그대로 두고 img/brjhunt/v2/<이름>_t.webp 로 새로 쓴다. manifest.json 의 해당 항목을 새 파일·프레임 2배·fps 2배로 바꾼다(원본 항목은 *_orig 로 보존).
 · 반복 시트(idle·run)는 마지막→처음 사이도 만든다. 한 번만 도는 시트(공격·시전·쓰러짐)는 칸 사이만. 한 칸짜리(jump·fall·hurt)는 그대로."""
import json, os, sys
import numpy as np, cv2
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'img', 'brjhunt', 'v2')
man_path = os.path.join(D, 'manifest.json')
man = json.load(open(man_path, encoding='utf-8'))
LOOP = {'chick_idle', 'chick_run'}
ERR_MAX = float(os.environ.get('ERR_MAX', '38'))   # 이보다 크면 보간 대신 앞 칸을 한 번 더(고스트 방지)
def mid(a, b):
    """RGBA uint8 두 장 → 중간 RGBA. 흐름은 알파 포함 4채널 미리곱셈 그림에서 구한다."""
    fa = a.astype(np.float32); fb = b.astype(np.float32)
    pa = fa.copy(); pb = fb.copy(); pa[..., :3] *= pa[..., 3:4] / 255.0; pb[..., :3] *= pb[..., 3:4] / 255.0
    ga = cv2.cvtColor(np.clip(pa[..., :3], 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY); gb = cv2.cvtColor(np.clip(pb[..., :3], 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    ga = np.maximum(ga, (fa[..., 3] / 2).astype(np.uint8)); gb = np.maximum(gb, (fb[..., 3] / 2).astype(np.uint8))   # 알파 윤곽도 흐름에 반영
    flow_ab = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 4, 21, 5, 7, 1.5, 0)
    flow_ba = cv2.calcOpticalFlowFarneback(gb, ga, None, 0.5, 4, 21, 5, 7, 1.5, 0)
    h, w = ga.shape; gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    wa = cv2.remap(pa, gx - flow_ba[..., 0] * 0.5, gy - flow_ba[..., 1] * 0.5, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)   # a 를 b 쪽으로 반
    wb = cv2.remap(pb, gx - flow_ab[..., 0] * 0.5, gy - flow_ab[..., 1] * 0.5, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)   # b 를 a 쪽으로 반
    union = np.maximum(wa[..., 3], wb[..., 3]) > 40
    err = float(np.abs(wa - wb)[..., 3][union].mean()) if union.any() else 0.0      # 두 쪽이 안 겹치는 정도(알파 차이) — 크면 고스트가 생긴다
    m = (wa + wb) / 2.0; al = m[..., 3:4]
    rgb = np.where(al > 1, m[..., :3] * 255.0 / np.maximum(al, 1), 0)
    return np.clip(np.concatenate([rgb, al], axis=-1), 0, 255).astype(np.uint8), err
prev = sys.argv[sys.argv.index('--preview') + 1] if '--preview' in sys.argv else None
for name in sorted(man):
    m = man[name]
    if not name.startswith('chick_') or not isinstance(m, dict) or not m.get('file') or name.endswith('_orig') or m.get('frames', 1) < 2: continue
    if m.get('tween'): continue
    n, fw, fh = m['frames'], m['w'], m['h']; sheet = np.array(Image.open(os.path.join(D, m['file'])).convert('RGBA'))
    fr = [sheet[:, i * fw:(i + 1) * fw] for i in range(n)]; out = []
    for i in range(n):
        out.append(fr[i])
        j = (i + 1) % n
        if i == n - 1 and name not in LOOP: break
        mm, err = mid(fr[i], fr[j]); ok_ = err < ERR_MAX
        print('   ', name, i, '->', j, 'err %.1f' % err, '보간' if ok_ else '고스트 위험 → 앞 칸 유지')
        out.append(mm if ok_ else fr[i])
    new = np.concatenate(out, axis=1); newfile = m['file'].replace('.webp', '_t.webp')
    Image.fromarray(new).save(os.path.join(D, newfile), 'WEBP', quality=92, method=6)
    man[name + '_orig'] = dict(m)
    m2 = dict(m); m2.update(file=newfile, frames=len(out), tween=True)
    if m.get('fps'): m2['fps'] = m['fps'] * len(out) / n
    man[name] = m2
    print(name, n, '->', len(out), newfile, os.path.getsize(os.path.join(D, newfile)) // 1024, 'KB')
    if prev:
        os.makedirs(prev, exist_ok=True); bg = Image.new('RGBA', (fw * len(out), fh), (60, 70, 110, 255)); bg.alpha_composite(Image.fromarray(new)); bg.save(os.path.join(prev, name + '.png'))
json.dump(man, open(man_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
