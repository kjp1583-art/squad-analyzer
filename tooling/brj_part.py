#!/usr/bin/env python3
"""🧩 브장신 파츠 레이어 추출·등록 — Pillow 만 사용(봇 호스트에 numpy 없음).

원리: ChatGPT 등 이미지 모델에 "기본 브장신이 이 아이템 하나만 착용한 전신"을 뽑게 한 뒤(PARTS_PROMPT.md),
그 그림을 기본 몸(parts/body/<view>.png)과 픽셀 비교해 **달라진 부분만** 투명 레이어로 잘라낸다.
파츠만 따로 그리게 하면 크기·위치가 매번 어긋나므로 이 방식이 안정적이다.

  · 배경 키잉(테두리 색 중앙값) → 실루엣 정합(발바닥·머리 꼭대기로 스케일·이동) → 차분 마스크 → 정리 → 슬롯 영역 제한
  · 결과: 1024×1024 RGBA(320 그리드 ×3.2), 파일명 parts/<slot>/<key>/<view>.png
  · 봇은 이 파일을 GitHub raw 에서 내려받아 몸 위에 얹는다(같은 모듈을 봇도 내려받아 import 한다 — 알고리즘 단일화)

CLI:
  python3 tooling/brj_part.py add --key c_hoodie --name "후드티" --slot o --rarity 레어 --emoji 🧥 --desc "한 줄" \
      --front gen_front.png [--quarter gen_quarter.png] [--price 10] [--limited] [--root img/brjang/parts]
  python3 tooling/brj_part.py remove --key c_hoodie
  python3 tooling/brj_part.py check --front gen_front.png            # 등록 없이 품질 리포트만
"""
import io, os, sys, json, argparse, datetime
from PIL import Image, ImageChops, ImageFilter, ImageOps

K = 3.2                      # 320 그리드 → 1024
SLOT_DIR = {"h": "h", "o": "o", "a": "a", "state": "state"}
SLOT_KO = {"모자": "h", "의상": "o", "장신구": "a", "상태": "state", "h": "h", "o": "o", "a": "a", "state": "state"}
# 슬롯별 허용 영역(320 그리드) — 이 밖의 차분은 생성 노이즈로 보고 버린다. None = 제한 없음
SLOT_REGION = {"o": (60, 170, 260, 300), "h": (0, 0, 320, 200), "a": None, "state": None}
NECK_Y, FEET_Y, HEAD_TOP = 183, 284, 34   # ANCHORS.md


def _key_bg(im):
    """테두리 색을 배경으로 보고 알파 생성. 반환 RGBA(배경 투명)."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    border = [rgb.getpixel((x, y)) for x in range(0, w, max(1, w // 64)) for y in (0, 1, h - 2, h - 1)] + \
             [rgb.getpixel((x, y)) for y in range(0, h, max(1, h // 64)) for x in (0, 1, w - 2, w - 1)]
    bg = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))
    if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 0:      # 이미 투명 배경이면 그대로
        return im.convert("RGBA"), bg
    d = ImageChops.lighter(ImageChops.lighter(ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).getchannel(0),
                                              ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).getchannel(1)),
                           ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).getchannel(2))
    hard = d.point(lambda v: 255 if v > 40 else 0)
    hard = hard.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))   # 1px 헤일로 제거
    out = rgb.convert("RGBA"); out.putalpha(hard)
    return out, bg


def _bbox(alpha):
    b = alpha.point(lambda v: 255 if v > 128 else 0).getbbox()
    return b


def _register(gen, base):
    """gen(RGBA) 실루엣을 base(RGBA) 실루엣에 맞춘다 — 모자·풍선처럼 몸 밖으로 튀어나온 아이템이 있어도 몸통이 지배하도록
       (스케일 후보 × 오프셋 언덕오르기)로 실루엣 IoU 최대 지점을 찾는다. 탐색은 1/4 해상도, 적용은 원본. 반환 (정합 RGBA, s, dx, dy)."""
    ba = base.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    ga = gen.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    gb, bb = ga.getbbox(), ba.getbbox()
    if not gb or not bb: raise ValueError("실루엣을 못 찾았어요(배경 키잉 실패)")
    Q = 4; W, H = base.size; w, h = W // Q, H // Q
    ba_q = ba.resize((w, h), Image.NEAREST); ba_q_pix = ba_q.histogram()[255]
    def _lower_center(a, box):
        """아래쪽 30% 행의 bbox 중심 x(발·몸통) — 머리 위 아이템에 안 흔들린다."""
        y0 = box[1] + int((box[3] - box[1]) * 0.7)
        sub = a.crop((0, y0, a.width, box[3] + 1)).getbbox()
        return (sub[0] + sub[2]) / 2 if sub else (box[0] + box[2]) / 2
    cands = set()
    for sc in ((bb[2] - bb[0]) / max(1, gb[2] - gb[0]), (bb[3] - bb[1]) / max(1, gb[3] - gb[1])):
        cands.add(round(sc, 3))
    for sc in (0.9, 0.94, 0.97, 1.0, 1.03, 1.06, 1.1): cands.add(sc)
    best = None
    for sc in sorted(cands):
        if not 0.6 < sc < 1.6: continue
        gq = ga.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.NEAREST)
        gqb = gq.getbbox()
        if not gqb: continue
        dx = int(round(_lower_center(ba_q, ba_q.getbbox()) - _lower_center(gq, gqb)))
        dy = int(round(ba_q.getbbox()[3] - gqb[3]))
        def _iou(ddx, ddy):
            o = Image.new("L", (w, h), 0); o.paste(gq, (ddx, ddy))
            inter = ImageChops.darker(o, ba_q).histogram()[255]
            return inter / max(1, o.histogram()[255] + ba_q_pix - inter)
        cur = (_iou(dx, dy), dx, dy)
        for step in (3, 1):
            improved = True
            while improved:
                improved = False
                for ex, ey in ((step, 0), (-step, 0), (0, step), (0, -step)):
                    v = _iou(cur[1] + ex, cur[2] + ey)
                    if v > cur[0] + 1e-4: cur = (v, cur[1] + ex, cur[2] + ey); improved = True
        if best is None or cur[0] > best[0]: best = (cur[0], sc, cur[1], cur[2])
    _v, s, dxq, dyq = best
    g2 = gen.resize((max(1, int(round(W * s))), max(1, int(round(H * s)))), Image.LANCZOS) if abs(s - 1) > 0.002 else gen
    # 원본 해상도에서 ±3px 재정합
    ba_pix = ba.histogram()[255]; g2a = g2.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    def _iou_full(ddx, ddy):
        o = Image.new("L", (W, H), 0); o.paste(g2a, (ddx, ddy))
        inter = ImageChops.darker(o, ba).histogram()[255]
        return inter / max(1, o.histogram()[255] + ba_pix - inter)
    cur = (_iou_full(dxq * Q, dyq * Q), dxq * Q, dyq * Q)
    for step in (2, 1):
        improved = True
        while improved:
            improved = False
            for ex, ey in ((step, 0), (-step, 0), (0, step), (0, -step)):
                v = _iou_full(cur[1] + ex, cur[2] + ey)
                if v > cur[0] + 1e-5: cur = (v, cur[1] + ex, cur[2] + ey); improved = True
    dx, dy = cur[1], cur[2]
    out = Image.new("RGBA", base.size, (0, 0, 0, 0)); out.paste(g2, (dx, dy), g2)
    return out, s, dx, dy


def extract_layer(gen_bytes, base_bytes, slot):
    """착용 전신(gen) − 기본 몸(base) → 파츠 레이어 PNG bytes, 리포트 dict."""
    gen = Image.open(io.BytesIO(gen_bytes)); gen.load()
    base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    if gen.size != base.size: gen = gen.resize(base.size, Image.LANCZOS)
    gen, bg = _key_bg(gen)
    gen, s, dx, dy = _register(gen, base)
    ga, ba = gen.getchannel("A"), base.getchannel("A")
    # 색 차분(둘 다 불투명인 곳) ∪ 새로 생긴 픽셀(gen 만 불투명)
    dif = ImageChops.difference(gen.convert("RGB"), base.convert("RGB"))
    dmax = ImageChops.lighter(ImageChops.lighter(dif.getchannel(0), dif.getchannel(1)), dif.getchannel(2))
    ba_h = ba.point(lambda v: 255 if v > 128 else 0)
    both = ImageChops.darker(ga, ba).point(lambda v: 255 if v > 128 else 0)
    changed = ImageChops.darker(dmax.point(lambda v: 255 if v > 56 else 0), both)
    edge = ImageChops.subtract(ba_h.filter(ImageFilter.MaxFilter(9)), ba_h.filter(ImageFilter.MinFilter(9)))   # 기본 몸 외곽선 ±4px 띠 — 리샘플 잔상은 여기서 나온다
    changed = ImageChops.darker(changed, ImageChops.invert(edge))
    new_px = ImageChops.darker(ga.point(lambda v: 255 if v > 128 else 0), ImageChops.invert(ba_h))
    mask = ImageChops.lighter(changed, new_px)
    mask = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))   # 구멍 메우기(닫힘)
    mask = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))   # 5px 미만 조각 제거(열림)
    mask = mask.filter(ImageFilter.MaxFilter(5))                                    # 외곽선 두 픽셀 여유
    reg = SLOT_REGION.get(slot)
    if reg:
        box = Image.new("L", mask.size, 0)
        from PIL import ImageDraw
        ImageDraw.Draw(box).rectangle([reg[0] * K, reg[1] * K, reg[2] * K, reg[3] * K], fill=255)
        mask = ImageChops.darker(mask, box)
    mask = ImageChops.darker(mask, ga)                                              # gen 의 실제 알파 안에서만
    layer = gen.copy(); layer.putalpha(mask)
    # 리포트
    inter = ImageChops.darker(ga, ba).point(lambda v: 255 if v > 128 else 0)
    union = ImageChops.lighter(ga, ba).point(lambda v: 255 if v > 128 else 0)
    hist_i, hist_u, hist_m = inter.histogram()[255], union.histogram()[255], mask.histogram()[255]
    iou = hist_i / max(1, hist_u); cover = hist_i / max(1, ba.point(lambda v: 255 if v > 128 else 0).histogram()[255])
    area = hist_m / (base.size[0] * base.size[1])
    bb = mask.getbbox()
    rep = {"iou": round(iou, 4), "cover": round(cover, 4), "scale": round(s, 4), "dx": dx, "dy": dy, "area": round(area, 4),
           "bbox320": [round(v / K, 1) for v in bb] if bb else None, "bg": "#%02x%02x%02x" % bg}
    warn = []
    if cover < 0.90: warn.append(f"실루엣 불일치(기본 몸 덮임 {cover:.2f} < 0.90) — 포즈·크기가 참조와 다름, 재생성 권장")
    if area < 0.002: warn.append("차분이 거의 없음 — 아이템이 안 그려졌거나 너무 작음")
    if area > 0.35: warn.append("차분이 너무 큼 — 캐릭터 전체가 바뀐 것 같음(색·선 변형)")
    rep["warn"] = warn
    buf = io.BytesIO(); layer.save(buf, "PNG", optimize=True)
    return buf.getvalue(), rep


def load_manifest(root):
    p = os.path.join(root, "manifest.json")
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return {"version": 1, "parts": {}}


def save_manifest(root, m):
    p = os.path.join(root, "manifest.json")
    with open(p, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=1)


def add_part(root, key, name, slot, rarity, emoji, desc, files, price=0, limited=False, base_dir=None):
    """files: {view: gen_bytes}. root 아래에 레이어 저장 + manifest 갱신. 반환 (manifest entry, {view: report})."""
    slot = SLOT_KO.get(slot, slot)
    if slot not in SLOT_DIR: raise ValueError(f"슬롯은 h/o/a/state 중 하나: {slot}")
    base_dir = base_dir or os.path.join(root, "body")
    reports, views = {}, []
    for view, gb in files.items():
        with open(os.path.join(base_dir, f"{view}.png"), "rb") as f: bb = f.read()
        png, rep = extract_layer(gb, bb, slot)
        d = os.path.join(root, SLOT_DIR[slot], key); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{view}.png"), "wb") as f: f.write(png)
        reports[view] = rep; views.append(view)
    m = load_manifest(root)
    ent = {"name": name, "slot": slot, "rarity": rarity, "emoji": emoji, "desc": desc, "views": views,
           "price": int(price or 0), "limited": bool(limited), "added": datetime.date.today().isoformat()}
    m.setdefault("parts", {})[key] = ent
    save_manifest(root, m)
    return ent, reports


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("--key", required=True); a.add_argument("--name", required=True); a.add_argument("--slot", required=True)
    a.add_argument("--rarity", default="에픽"); a.add_argument("--emoji", default="🧩"); a.add_argument("--desc", default="")
    a.add_argument("--front", required=True); a.add_argument("--quarter"); a.add_argument("--oblique"); a.add_argument("--price", type=int, default=0)
    a.add_argument("--limited", action="store_true"); a.add_argument("--root", default="img/brjang/parts")
    r = sub.add_parser("remove"); r.add_argument("--key", required=True); r.add_argument("--root", default="img/brjang/parts")
    c = sub.add_parser("check"); c.add_argument("--front", required=True); c.add_argument("--slot", default="o"); c.add_argument("--root", default="img/brjang/parts")
    args = ap.parse_args()
    if args.cmd == "remove":
        m = load_manifest(args.root); ent = m.get("parts", {}).pop(args.key, None); save_manifest(args.root, m)
        print("removed" if ent else "no such key", args.key); return
    if args.cmd == "check":
        with open(args.front, "rb") as f: gb = f.read()
        with open(os.path.join(args.root, "body", "front.png"), "rb") as f: bb = f.read()
        _png, rep = extract_layer(gb, bb, SLOT_KO.get(args.slot, args.slot)); print(json.dumps(rep, ensure_ascii=False, indent=1)); return
    files = {}
    for v in ("front", "quarter", "oblique"):
        p = getattr(args, v)
        if p:
            with open(p, "rb") as f: files[v] = f.read()
    ent, reps = add_part(args.root, args.key, args.name, args.slot, args.rarity, args.emoji, args.desc, files, args.price, args.limited)
    print(json.dumps({"entry": ent, "reports": reps}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
