# -*- coding: utf-8 -*-
"""🎨 [v83.75] 분석기 그래픽 카드 렌더러 — Pillow 로 '카드·게이지·뱃지'를 그린다(2배 해상도 → LANCZOS 축소).

왜 따로 두나
  · Tkinter 는 둥근 모서리·그라데이션·알파·그림자가 없다(DESIGN.md §안내). 지금까지는 1px 헤어라인과
    surface 사다리로만 깊이를 냈다. 이 모듈이 그 한계를 이미지 한 장으로 메운다(팀 컬러 그라데이션·
    둥근 카드 모서리·광택 있는 게이지·링 뱃지).
  · tkinter 를 import 하지 않는다 → 창 없이(테스트·CI) 그려서 결과를 파일로 검증할 수 있다.
    ImageTk.PhotoImage 변환은 호출부(squad_analyzer.py, GUI 스레드)가 맡는다.

메모리
  · 모든 결과는 (크기·색·값) 키로 LRU 캐시한다 — 같은 슬롯 10칸이 같은 이미지를 공유하고,
    창 크기가 잠깐 흔들려도 매번 다시 그리지 않는다. CACHE_MAX 를 넘으면 가장 오래 안 쓴 것부터 버린다.
  · 2배로 그린 중간 이미지는 반환 전에 축소해 버리므로 캐시에 남지 않는다.
"""
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

CARD_VERSION = "1.0"      # 렌더 규칙이 바뀌면 올린다(캐시 키에 포함 — 구 이미지 재사용 방지)
SS = 2                    # 슈퍼샘플 배율(둥근 모서리·링 안티앨리어싱)
CACHE_MAX = 32            # 캐시 항목 상한(항목당 수백 KB — 최대 ~10MB)

_CACHE = OrderedDict()
_FONT_CACHE = {}
_FONT_PATHS = None

# Windows 는 맑은 고딕, 없으면 흔한 대체 폰트를 쓴다(테스트·CI 는 DejaVu).
_WIN_FONTS = (("C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf"),
              ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf"))
_LINUX_FONTS = (("/usr/share/fonts/pickle-hwp/NotoSansCJKkr-Regular.otf",
                 "/usr/share/fonts/pickle-hwp/NotoSansCJKkr-Regular.otf"),
                ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                 "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
                ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"))
_MAC_FONTS = (("/System/Library/Fonts/Supplemental/AppleGothic.ttf",) * 2,)


def _font_path(bold):
    """굵은/보통 폰트 파일 경로(없으면 None → Pillow 기본 비트맵 폰트)."""
    global _FONT_PATHS
    if _FONT_PATHS is None:
        cands = _WIN_FONTS + _LINUX_FONTS + _MAC_FONTS
        _FONT_PATHS = []
        for bold_p, reg_p in cands:
            pair = [None, None]
            for i, p in enumerate((bold_p, reg_p)):
                try:
                    with open(p, "rb"):
                        pair[i] = p
                except Exception:
                    pass
            _FONT_PATHS.append(tuple(pair))
    for pair in _FONT_PATHS:
        p = pair[0] if bold else pair[1]
        if p:
            return p
    return None


def font(size, bold=False):
    """(크기, 굵기)별 폰트 캐시 — 매 프레임 ImageFont 를 새로 만들면 느리고 객체가 쌓인다."""
    key = (int(size), bool(bold))
    f = _FONT_CACHE.get(key)
    if f is not None:
        return f
    p = _font_path(bold)
    try:
        f = ImageFont.truetype(p, int(size)) if p else ImageFont.load_default(size=int(size))
    except Exception:
        try:
            f = ImageFont.load_default(size=int(size))
        except Exception:
            f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


# ── 색 유틸 ──────────────────────────────────────────────────────────────────
def hex_rgb(c):
    """'#rrggbb' | (r,g,b) | (r,g,b,a) → (r,g,b,a)."""
    if isinstance(c, (tuple, list)):
        t = tuple(int(x) for x in c)
        return t if len(t) == 4 else (t[0], t[1], t[2], 255)
    h = str(c or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        return (0, 0, 0, 255)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def mix(c1, c2, t):
    """두 색을 t(0=c1, 1=c2) 비율로 섞는다 — 그라데인·광택·그림자 계산용."""
    a, b = hex_rgb(c1), hex_rgb(c2)
    t = max(0.0, min(1.0, float(t)))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


def _vgrad(size, top, bottom):
    """세로 그라데이션 이미지(1px 폭으로 그려 늘린다 — 픽셀 수를 아낀다)."""
    w, h = size
    col = Image.new("RGBA", (1, max(1, h)))
    px = col.load()
    for y in range(max(1, h)):
        px[0, y] = mix(top, bottom, 0 if h <= 1 else y / (h - 1))
    return col.resize((max(1, w), max(1, h)), Image.Resampling.NEAREST)


def _hgrad(size, left, right):
    w, h = size
    row = Image.new("RGBA", (max(1, w), 1))
    px = row.load()
    for x in range(max(1, w)):
        px[x, 0] = mix(left, right, 0 if w <= 1 else x / (w - 1))
    return row.resize((max(1, w), max(1, h)), Image.Resampling.NEAREST)


def _rrect_mask(size, radius, box=None):
    """둥근 사각형 마스크(L) — 마스크로 합성하면 '둥근 모서리 + 그라데이션'을 한 번에 얻는다."""
    w, h = size
    box = box or (0, 0, w - 1, h - 1)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle(box, radius=max(0, int(radius)), fill=255)
    return m


def _paste_round(base, patch, box, radius):
    """base 위에 patch 를 둥근 사각형 모양으로 붙인다."""
    m = _rrect_mask(patch.size, radius)
    base.paste(patch, (box[0], box[1]), m)


def _fit_font(text, max_w, base_px, bold=True, min_px=6):
    """주어진 폭에 들어가는 가장 큰 폰트 — 좁은 게이지에서 숫자가 밖으로 삐져나가지 않게."""
    size = max(min_px, int(base_px))
    while size > min_px:
        f = font(size, bold)
        try:
            w = f.getbbox(text)[2] - f.getbbox(text)[0]
        except Exception:
            w = len(text) * size * 0.6
        if w <= max_w:
            return f
        size -= 1
    return font(min_px, bold)


def _cached(key, maker):
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return hit
    img = maker()
    _CACHE[key] = img
    while len(_CACHE) > CACHE_MAX:
        _CACHE.popitem(last=False)
    return img


def cache_info():
    return {"items": len(_CACHE), "max": CACHE_MAX, "keys": list(_CACHE)}


def clear_cache():
    _CACHE.clear()


# ── 슬롯 카드 ────────────────────────────────────────────────────────────────
def slot_card(w, h, team="blue", bg="#1b1f2b", fill=None, accent=None,
              radius=10, glow=11, bottom_shade=4, ss=SS):
    """블루/레드 10인 슬롯 카드 한 장 — 둥근 모서리 + 팀 컬러 좌측 글로우 + 바닥 음영.

    w,h    : 실제 위젯 크기(px). 내부에서 ss 배로 그린 뒤 LANCZOS 로 줄인다.
    bg     : 카드 바깥(모서리) 색 = 슬롯을 담는 컨테이너의 배경색. 이 색으로 네 모서리를 덮어 '둥글게' 보인다.
    fill   :카드 안쪽 바탕색 — 슬롯 안쪽 프레임들의 bg 와 **같은 값**을 넘겨야 이음새가 안 보인다.
    accent : 팀 컬러(좌측 액센트 바·글로우 기준색).
    glow   : 좌측에서 팀 컬러가 사라지는 폭(px). 액센트 바(3px Tk 프레임) 오른쪽으로 번지는 빛.
    """
    w, h = int(max(1, w)), int(max(1, h))
    team = str(team or "blue")
    fill = fill or ("#182233" if team == "blue" else "#281a20")
    accent = accent or ("#3a73e8" if team == "blue" else "#e84057")
    key = ("slot", CARD_VERSION, w, h, team, bg, fill, accent, radius, glow, bottom_shade, ss)

    def _make():
        W, H = w * ss, h * ss
        img = Image.new("RGBA", (W, H), hex_rgb(bg))
        r = max(2, int(radius * ss))
        d = ImageDraw.Draw(img)
        # ① 카드 바탕 — 둥근 모서리(밖은 bg 색이라 컨테이너 배경과 이어진다)
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, fill=hex_rgb(fill))
        # ② 좌측 팀 컬러 글로우 — 가로 그라데이션을 카드 모양으로 잘라 얹는다
        gw = max(2, int(glow * ss))
        band = _hgrad((gw, H), mix(accent, fill, 0.12), fill)
        al = Image.new("L", (gw, H), 255)
        ap = al.load()
        fade = 6 * ss
        for y in range(H):                       # 위아래 끝은 잦아들게(카드 안에 자연스럽게)
            edge = min(y, H - 1 - y)
            k = 1.0 if edge > fade else max(0.15, edge / float(fade))
            for x in range(gw):
                ap[x, y] = int(255 * k)
        card = _rrect_mask((W, H), r).crop((0, 0, gw, H))
        mp = card.load()
        for y in range(H):                       # 두 마스크(세로 페이드 × 카드 모양)를 곱한다
            for x in range(gw):
                mp[x, y] = (mp[x, y] * ap[x, y]) // 255
        img.paste(band, (0, 0), card)
        # ③ 바닥 음영 — 카드가 살짝 '앉아' 보이게(가장자리 4px)
        bh = max(1, int(bottom_shade * ss))
        strip = _vgrad((W, bh), fill, mix(fill, (0, 0, 0), 0.35))
        img.paste(strip, (0, H - bh),
                  _rrect_mask((W, H), r).crop((0, H - bh, W, H)))
        # ④ 안쪽 하이라이트/그림자 한 줄 — 위에서 빛이 오는 느낌(테두리처럼 보이지 않게 아주 약하게)
        d = ImageDraw.Draw(img)
        inset = max(1, ss // 2)
        d.rounded_rectangle((inset, inset, W - 1 - inset, H - 1 - inset), radius=max(1, r - inset),
                            outline=mix(fill, (255, 255, 255), 0.07), width=max(1, ss // 2))
        d.line([(r, H - 1 - inset), (W - r, H - 1 - inset)],
               fill=mix(fill, (0, 0, 0), 0.28), width=max(1, ss // 2))
        return img.resize((w, h), Image.Resampling.LANCZOS)

    return _cached(key, _make)


# ── 게이지 ───────────────────────────────────────────────────────────────────
def winrate_gauge(w, h, blue_pct, bg="#16243f", left="#3a73e8", right="#e84057",
                  text="#e7eaf3", track="#0f1626", ss=SS):
    """⚖ 예상 승률 게이지 — 블루/레드 비율을 한 알약 안에 채우고 양 끝에 %를 새긴다.

    blue_pct : 블루 예상 승률(0~100). None/문자 변환 실패면 중립(50)으로 그린다.
    bg       : 위젯 배경색(모서리를 이 색으로 덮어 알약 모양을 만든다) = 헤더 배경.
    """
    w, h = int(max(8, w)), int(max(6, h))
    try:
        bp = float(blue_pct)
    except Exception:
        bp = 50.0
    bp = max(0.0, min(100.0, bp))
    rp = 100.0 - bp
    key = ("wr", CARD_VERSION, w, h, round(bp, 1), bg, left, right, text, track, ss)

    def _make():
        W, H = w * ss, h * ss
        img = Image.new("RGBA", (W, H), hex_rgb(bg))
        r = H // 2
        # 트랙(빈 알약)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, fill=hex_rgb(track))
        # 블루/레드 채움 — 두 구간을 따로 그리면 경계에 둥근 모서리 때문에 틈이 생긴다.
        #   → 폼 전체를 가로 그라데이션으로 한 번에 칠한 뒤 알약 마스크로 잘라 넣는다(이음새 0).
        split = int(round(W * bp / 100.0))
        pad = max(1, ss)
        fill_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if split > 0:
            fill_img.paste(_hgrad((split, H), mix(left, (255, 255, 255), 0.18), left), (0, 0))
        if W - split > 0:
            fill_img.paste(_hgrad((W - split, H), right, mix(right, (0, 0, 0), 0.22)), (split, 0))
        img.paste(fill_img.crop((pad, pad, W - pad, H - pad)), (pad, pad),
                  _rrect_mask((W - 2 * pad, H - 2 * pad), max(1, r - pad)))
        # 가운데 구분 노치 + 위쪽 하이라이트(유리 느낌)
        d = ImageDraw.Draw(img)
        if 0 < split < W:
            d.line([(split, int(H * 0.18)), (split, int(H * 0.82))],
                   fill=mix(track, (255, 255, 255), 0.55), width=max(1, ss))
        d.line([(r, max(1, ss // 2)), (W - r, max(1, ss // 2))],
               fill=mix(left, (255, 255, 255), 0.35), width=max(1, ss // 2))
        # 테두리
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, outline=mix(track, (255, 255, 255), 0.16),
                            width=max(1, ss))
        # 숫자 — 블루는 왼쪽, 레드는 오른쪽 정렬. 폭이 좁으면 '62:38' 하나만, 더 좁으면 생략.
        if w >= 120:
            lt, rt = f"{bp:.0f}%", f"{rp:.0f}%"
            f = _fit_font(lt, (W // 2) * 0.62, (h - 12) * ss)
            d.text((r + 2 * ss, H / 2), lt, font=f, fill=hex_rgb(text), anchor="lm")
            f = _fit_font(rt, (W // 2) * 0.62, (h - 12) * ss)
            d.text((W - r - 2 * ss, H / 2), rt, font=f, fill=hex_rgb(text), anchor="rm")
        elif w >= 72:
            t = f"{bp:.0f}:{rp:.0f}"
            d.text((W / 2, H / 2), t, font=_fit_font(t, W - 4 * ss, (h - 12) * ss),
                   fill=hex_rgb(text), anchor="mm")
        return img.resize((w, h), Image.Resampling.LANCZOS)

    return _cached(key, _make)


def power_gauge(w, h, value, vmax=12.0, fill="#e0a437", bg="#1b1f2b", track="#232a3c",
                text="#e7eaf3", label="", ss=SS):
    """⚔ 전투력 게이지 — 0~vmax 스케일의 얇은 바로 '수치가 어디쯤인지'를 보여준다.

    전투력은 팀 전체 합으로 이야기하는 값이라 팀 제목 옆에 한 줄로 둔다(선수 개인은 숫자 라벨 그대로).
    """
    w, h = int(max(8, w)), int(max(6, h))
    try:
        v = float(value)
    except Exception:
        v = 0.0
    ratio = max(0.0, min(1.0, v / float(vmax or 1)))
    key = ("pw", CARD_VERSION, w, h, round(ratio, 3), fill, bg, track, text, label, ss)

    def _make():
        W, H = w * ss, h * ss
        img = Image.new("RGBA", (W, H), hex_rgb(bg))
        d = ImageDraw.Draw(img)
        r = H // 2
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, fill=hex_rgb(track))
        fw = int(round((W - 2 * max(1, ss)) * ratio))
        if fw > 2:
            seg = _hgrad((fw, H - 2 * max(1, ss)), mix(fill, (255, 255, 255), 0.25), fill)
            img.paste(seg, (max(1, ss), max(1, ss)), _rrect_mask(seg.size, max(1, (H - 2 * max(1, ss)) // 2)))
        d = ImageDraw.Draw(img)
        d.line([(r, max(1, ss // 2)), (W - r, max(1, ss // 2))],
               fill=mix(fill, (255, 255, 255), 0.30), width=max(1, ss // 2))
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, outline=mix(track, (255, 255, 255), 0.14),
                            width=max(1, ss))
        txt = (f"{label} {v:.1f}" if label else f"{v:.1f}")
        f = _fit_font(txt, W - 10 * ss, (h - 11) * ss)
        # 글자 뒤에 반투명 판 — 채움색 위에서도 숫자가 읽히게(금색 바탕에 흰 글자는 묻힘)
        tb = d.textbbox((W / 2, H / 2), txt, font=f, anchor="mm")
        plate = Image.new("RGBA", (max(1, int(tb[2] - tb[0]) + 7 * ss), max(1, int(tb[3] - tb[1]) + 3 * ss)),
                          (10, 12, 20, 255))
        pmask = _rrect_mask(plate.size, max(1, plate.height // 2 - ss // 2))
        plate.putalpha(pmask.point(lambda a: a * 120 // 255))     # 둥근 반투명 판
        img.alpha_composite(plate, (int((W - plate.width) / 2), int((H - plate.height) / 2)))
        d = ImageDraw.Draw(img)
        d.text((W / 2, H / 2), txt, font=f, fill=hex_rgb(text), anchor="mm")
        return img.resize((w, h), Image.Resampling.LANCZOS)

    return _cached(key, _make)


# ── 뱃지(포지션·티어) ────────────────────────────────────────────────────────
def badge(size, ring, fill, bg, icon=None, icon_ratio=0.72, ss=3, kind=""):
    """포지션·티어 뱃지 — 팀 틴트 원판 + 링(포지션/티어 색) + 가운데 아이콘.

    icon : PIL RGBA 아이콘(있으면 가운데 합성). 없으면 링만 있는 원판.
    kind : 캐시 키 구분자(예: 'JUNGLE'·'DIAMOND') — 같은 크기·색이라도 아이콘이 다르면 다른 항목.
    """
    size = int(max(8, size))
    key = ("badge", CARD_VERSION, size, ring, fill, bg, icon_ratio, ss, kind, id(icon) if icon is not None else 0)

    def _make():
        S = size * ss
        img = Image.new("RGBA", (S, S), hex_rgb(bg))
        d = ImageDraw.Draw(img)
        pad = max(1, ss // 2)
        d.ellipse((pad, pad, S - 1 - pad, S - 1 - pad), fill=hex_rgb(fill))
        # 위쪽 하이라이트 — 원판이 살짝 도드라져 보이게
        d.arc((pad, pad, S - 1 - pad, S - 1 - pad), 200, 340,
              fill=mix(fill, (255, 255, 255), 0.35), width=max(1, ss))
        if icon is not None:
            isz = max(2, int(S * icon_ratio))
            ic = icon.copy()
            if ic.mode != "RGBA":
                ic = ic.convert("RGBA")
            ic.thumbnail((isz, isz), Image.Resampling.LANCZOS)
            img.alpha_composite(ic, ((S - ic.width) // 2, (S - ic.height) // 2))
        d.ellipse((pad, pad, S - 1 - pad, S - 1 - pad), outline=hex_rgb(ring), width=max(2, ss))
        return img.resize((size, size), Image.Resampling.LANCZOS)

    return _cached(key, _make)


def team_band(w, h, team="blue", bg="#16243f", ss=2):
    """헤더용 팀 컬러 밴드 — 왼쪽은 팀 색이 살짝 돌고 오른쪽으로 배경에 잦아드는 가로 그라데이션.
       카드와 같은 이유로 bg(헤더 배경)와 같은 계열이어야 글자 뒤 이음새가 안 보인다."""
    w, h = int(max(1, w)), int(max(1, h))
    key = ("band", CARD_VERSION, w, h, team, bg, ss)

    def _make():
        base = str(bg)
        tint = mix("#3a73e8" if str(team) == "blue" else "#e84057", base, 0.90)
        W, H = w * ss, h * ss
        img = Image.new("RGBA", (W, H), hex_rgb(base))
        row = _hgrad((max(1, int(W * 0.55)), 1), tint, base)
        img.paste(row.resize((max(1, int(W * 0.55)), H), Image.Resampling.NEAREST), (0, 0))
        return img.resize((w, h), Image.Resampling.LANCZOS)

    return _cached(key, _make)
