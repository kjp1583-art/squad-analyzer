#!/usr/bin/env python3.13
"""✂️ 통짜 스킨(별수호자·수영장파티·트위스티드)을 꾸미기 파츠 이미지로 쪼갠다 (2026-11-14 사장님 「3개 스킨을 파츠로 분리해 꾸미기로 재출시」).
스킨 front.png 와 기본 병아리(parts/body_chick/front.png)를 비교해 「스킨에서 달라진 픽셀」만 남기고, 부위 상자로 나눠 투명 webp 로 저장한다.
좌표는 병아리 시트 머리 앵커와 같은 단위 — 머리 중심 (cx,cy)·반지름 r(가장 넓은 노랑 폭/2) 기준 ox,oy,w,h 로 img/brjhunt/parts/parts.json 에 적는다.
  python3.13 tooling/brj_split_skin.py [--sheet 미리보기.png]
부위 상자(박스)는 1024px 원본 좌표. 눈·부리·볼은 상자에서 빼서 움직이는 병아리 얼굴을 안 덮는다."""
import json, os, sys
import cv2, numpy as np
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR = os.path.join(ROOT, 'img', 'brjang'); OUT = os.path.join(ROOT, 'img', 'brjhunt', 'parts')
base = np.array(Image.open(os.path.join(BR, 'parts/body_chick/front.png')).convert('RGBA')).astype(int)

def head_of(im):   # chick_head_anchors.py 와 같은 방식: 노랑 마스크에서 가장 넓은 줄 → 중심·반지름
    a = im[..., 3] > 128
    yel = a & (im[..., 0] > 225) & (im[..., 1] > 190) & (im[..., 2] > 100) & (im[..., 2] < 215)
    ys = np.where(yel.any(1))[0]; top = ys[0]; span = ys[-1] - top; best = (0, top, 0)
    for y in range(top, top + int(span * 0.38) + 1):
        xs = np.where(yel[y])[0]
        if len(xs) and xs[-1] - xs[0] > best[0]: best = (xs[-1] - xs[0], y, (xs[0] + xs[-1]) / 2)
    r = best[0] / 2.0
    return best[2], top + r, r
CX, CY, R = head_of(base)

# 파츠: 키 -> (스킨, 슬롯, 이름, 이모지, 등급, 설명, [포함 상자 (x0,y0,x1,y1)…], [뺄 상자…])   좌표 = 1024 원본
FACE = (255, 330, 770, 600)     # 눈·부리·볼 — 어느 파츠도 여기는 안 가져온다(움직이는 병아리 얼굴)
PARTS = {
 'sg_tiara':  ('sg', 'head', '별수호자 티아라', '🌟', '전설', '별빛 머리띠와 날개 귀 — 별수호자 브장신의 머리.', [(110, 100, 910, 330), (110, 330, 290, 620), (730, 330, 910, 620)], [FACE]),
 'sg_dress':  ('sg', 'body', '별수호자 드레스', '✨', '전설', '별이 박힌 푸른 드레스.', [(300, 560, 740, 825)], []),
 'pp_shades': ('pp', 'face', '하트 선글라스', '🕶', '전설', '머리 위에 척 올린 하트 선글라스.', [(250, 130, 730, 360)], [FACE]),
 'pp_flower': ('pp', 'head', '히비스커스 꽃', '🌺', '에픽', '귀 옆에 꽂은 빨간 꽃.', [(640, 110, 940, 365), (790, 365, 940, 440)], []),
 'pp_aloha':  ('pp', 'body', '알로하 셔츠 · 수영복', '🩳', '전설', '꽃무늬 셔츠에 파란 수영복 바지, 꽃 목걸이까지.', [(300, 560, 740, 825)], []),
 'pp_ring':   ('pp', 'back', '오리 튜브', '🛟', '에픽', '옆구리에 낀 오리 튜브.', [(0, 520, 300, 820)], []),
 'tf_hat':    ('tf', 'head', '트위스티드 모자', '🎩', '전설', '스페이드 문양 모자와 하얀 깃털.', [(190, 80, 940, 340)], [FACE]),
 'tf_coat':   ('tf', 'body', '트위스티드 코트', '🃏', '전설', '"빨강이 좋겠군" — 코트와 넥타이, 손에 든 카드까지.', [(300, 560, 740, 825)], []),
}
def mask_of(skin, boxes, cut, skin_body=False):
    s = np.array(Image.open(os.path.join(BR, 'skins', skin, 'front.png')).convert('RGBA')).astype(int)
    d = ((np.abs(s[..., :3] - base[..., :3]).sum(2) > 70) | (np.abs(s[..., 3] - base[..., 3]) > 80)) & (s[..., 3] > 40)
    box = np.zeros(d.shape, bool)
    for x0, y0, x1, y1 in boxes: box[y0:y1, x0:x1] = True
    for x0, y0, x1, y1 in cut: box[y0:y1, x0:x1] = False
    if skin_body:
        r_, g_, b_ = s[..., 0], s[..., 1], s[..., 2]
        yel = (r_ > 225) & (g_ > 195) & (b_ > 100) & (b_ < 215); org = (r_ > 215) & (g_ > 110) & (g_ < 190) & (b_ < 100)
        d &= ~(yel | org)
    m = (d & box).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 900: keep[lab == i] = 1
    keep = cv2.dilate(keep, np.ones((5, 5), np.uint8))          # 검은 외곽선 가장자리까지 살린다
    keep = keep.astype(bool) & (s[..., 3] > 40)
    return s, keep

def main():
    os.makedirs(OUT, exist_ok=True); man = {}; tiles = []
    for key, (skin, slot, nm, em, rar, ds, boxes, cut) in PARTS.items():
        s, keep = mask_of(skin, boxes, cut, slot == 'body')
        ys, xs = np.where(keep); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        rgba = s.astype(np.uint8).copy(); rgba[..., 3] = np.where(keep, s[..., 3], 0).astype(np.uint8)
        im = Image.fromarray(rgba).crop((x0, y0, x1, y1))
        sc = 256 / max(im.size) if max(im.size) > 256 else 1.0
        if sc < 1: im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
        im.save(os.path.join(OUT, key + '.webp'), quality=88, method=6)
        man[key] = {'slot': slot, 'ox': round((x0 - CX) / R, 4), 'oy': round((y0 - CY) / R, 4), 'w': round((x1 - x0) / R, 4), 'h': round((y1 - y0) / R, 4), 'file': key + '.webp'}
        tiles.append((key, Image.fromarray(rgba).crop((x0, y0, x1, y1)).resize((200, int(200 * (y1 - y0) / (x1 - x0))) if (x1 - x0) >= (y1 - y0) else (int(200 * (x1 - x0) / (y1 - y0)), 200))))
        print(key, slot, man[key], os.path.getsize(os.path.join(OUT, key + '.webp')))
    json.dump({'_head': {'cx': round(CX, 1), 'cy': round(CY, 1), 'r': round(R, 1)}, **man}, open(os.path.join(OUT, 'parts.json'), 'w'), ensure_ascii=False, indent=1)
    if '--sheet' in sys.argv:
        W = Image.new('RGBA', (220 * 4, 230 * 2), (60, 70, 90, 255))
        for i, (k, t) in enumerate(tiles): W.alpha_composite(t, (220 * (i % 4) + 10, 230 * (i // 4) + 10))
        W.save(sys.argv[sys.argv.index('--sheet') + 1])
main()
