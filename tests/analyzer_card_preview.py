# -*- coding: utf-8 -*-
"""Pillow 카드 미리보기 생성 — 슬롯 카드·게이지·뱃지를 실제 앱 배치대로 합성해 PNG 로 저장한다.

    python3 tests/analyzer_card_preview.py [출력경로]

기본 출력: downloads/analyzer_pillow_card_preview.png
   (앱에서는 같은 이미지를 Tk 라벨 배경/이미지로 쓰고, 글자는 Tk 폰트로 그린다.
    여기서는 '이미지가 어떻게 보이는지'를 확인하려고 글자까지 같은 크기·색으로 얹었다.)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "desktop"))

from PIL import Image, ImageDraw  # noqa: E402

import card_render as CR  # noqa: E402
import theme  # noqa: E402

DESKTOP = os.path.join(ROOT, "desktop")
_ICON = {}


def icon(name):
    """번들 아이콘(desktop/{TIER,TOP,…}.png)을 원본 해상도로 — 뱃지에 실제로 합성되는 그림."""
    if name in _ICON:
        return _ICON[name]
    im = None
    try:
        im = Image.open(os.path.join(DESKTOP, name + ".png")).convert("RGBA")
    except Exception:
        im = None
    _ICON[name] = im
    return im

OUT_DEFAULT = os.path.join(os.path.dirname(ROOT), "downloads", "analyzer_pillow_card_preview.png")

TIER_RING = {"IRON": "#7d869c", "BRONZE": "#a9713f", "SILVER": "#aeb6c4", "GOLD": "#e0a437",
             "PLATINUM": "#39c7d6", "EMERALD": "#2bb177", "DIAMOND": "#5b8cff",
             "MASTER": "#8a5cd6", "GRANDMASTER": "#e84057", "CHALLENGER": "#e0a437",
             "UNRANKED": "#4a5266"}
POS_RING = {"TOP": theme.POS_TOP, "JUNGLE": theme.POS_JG, "MIDDLE": theme.POS_MID,
            "BOTTOM": theme.POS_ADC, "UTILITY": theme.POS_SUP, "NONE": "#7d869c"}
POS_KOR = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서폿", "NONE": "—"}

SAMPLE = {
    "blue": [("맛동산장인유미", "내전 214판 61%", "유미 · 룰루 · 나미", "유미 71% · 룰루 64%", "DIAMOND", "UTILITY", "1上 ⚔9.4"),
             ("허거덩", "내전 188판 54%", "로크 · 판테온", "로크 66% · 아리 61%", "PLATINUM", "MIDDLE", "2上 ⚔8.1"),
             ("Donk", "내전 302판 58%", "리신 · 비에고", "리신 63% · 비에고 60%", "MASTER", "JUNGLE", "0 ⚔10.2"),
             ("새벽문앞", "내전 156판 49%", "이즈리얼 · 카이사", "이즈리얼 58%", "GOLD", "BOTTOM", "2中 ⚔6.9"),
             ("뵤뵤", "내전 97판 52%", "그라가스 · 케넨", "그라가스 57%", "SILVER", "TOP", "3上 ⚔5.8")],
    "red": [("커리크랩칠리크림", "내전 240판 57%", "아지르 · 빅토르", "아지르 62%", "EMERALD", "MIDDLE", "1下 ⚔8.8"),
            ("레알티슈도둑", "내전 201판 46%", "세나 · 진", "진 55%", "GOLD", "BOTTOM", "2中 ⚔6.4"),
            ("우거", "내전 175판 55%", "마오카이 · 세주아니", "마오카이 61%", "DIAMOND", "JUNGLE", "1上 ⚔9.1"),
            ("카페", "내전 132판 51%", "럼블 · 크산테", "럼블 58%", "PLATINUM", "TOP", "2上 ⚔7.7"),
            ("나만", "내전 81판 44%", "밀리오 · 룰루", "밀리오 52%", "SILVER", "UTILITY", "3中 ⚔5.5")],
}


def _badge(kind, tier, bg):
    return CR.badge(34, TIER_RING.get(tier, TIER_RING["UNRANKED"]), CR.mix(bg, "#ffffff", 0.06), bg,
                    icon=icon(tier), kind=kind)


def draw_slot(sheet, x, y, w, h, team, row, bg, scale=1.0):
    """슬롯 카드 한 칸 = 카드 이미지 + (앱에서는 Tk 라벨이 그리는) 4줄 글자."""
    fill = theme.TEAM_BLUE_SOFT if team == "blue" else theme.TEAM_RED_SOFT
    fg_team = theme.TEAM_BLUE_FG if team == "blue" else theme.TEAM_RED_FG
    card = CR.slot_card(w, h, team=team, bg=bg, fill=fill)
    sheet.paste(card, (x, y), card)
    d = ImageDraw.Draw(sheet)
    name, jeok, most, op, tier, pos, pw = row
    # 좌측 액센트(3px Tk 프레임과 같은 자리) 위에 뱃지 두 개 — 실제 번들 아이콘(티어.png·포지션.png)을 합성
    bx = x + 14
    for kind, col, ic in (("TIER-" + tier, TIER_RING.get(tier, TIER_RING["UNRANKED"]), tier),
                          ("POS-" + pos, POS_RING.get(pos, POS_RING["NONE"]), pos)):
        b = CR.badge(34, col, CR.mix(fill, "#ffffff", 0.06), fill, icon=icon(ic), kind=kind)
        sheet.paste(b, (bx, y + (h - 34) // 2), b)
        bx += 39
    tx = bx + 6
    d.text((tx, y + 8), name, font=CR.font(13), fill=theme.TEXT, anchor="la")
    d.text((tx + 120, y + 10), "DIAMOND 42LP", font=CR.font(9), fill=theme.GOLD, anchor="la")
    d.text((x + w - 14, y + 9), pw, font=CR.font(10), fill=theme.GOLD, anchor="ra")
    d.text((tx, y + 28), f" 전적: {jeok}", font=CR.font(11), fill=theme.TEXT_SUB, anchor="la")
    d.text((tx, y + 46), f" 포지션 {POS_KOR.get(pos, '—')} · {tier}", font=CR.font(11),
           fill=theme.TEXT_MUT, anchor="la")
    d.line([(tx, y + 64), (x + w - 16, y + 64)], fill=CR.mix(fill, "#ffffff", 0.06), width=1)
    d.text((tx, y + 68), f" 모스트: {most}", font=CR.font(11), fill=fg_team, anchor="la")
    d.text((tx, y + 86), f" 고승률픽: {op}", font=CR.font(11), fill=theme.SUCCESS_SOFT, anchor="la")
    return card


def main(out_path=None):
    out_path = out_path or OUT_DEFAULT
    W, H = 1180, 820
    sheet = Image.new("RGB", (W, H), theme.BG)
    d = ImageDraw.Draw(sheet)
    d.text((24, 18), "SQUAD.GG 분석기 · Pillow 카드 시안 (v83.75)", font=CR.font(16), fill=theme.TEXT)
    d.text((24, 42), "슬롯 카드 = 둥근 모서리 + 팀 컬러 좌측 글로우 + 바닥 음영 · 헤더 = 팀 그라데이션 밴드 + "
                     "예상승률 게이지 · 뱃지 = 포지션/티어 링", font=CR.font(10), fill=theme.TEXT_MUT)

    col_w, slot_h, gap = 560, 112, 8
    for ci, team in enumerate(("blue", "red")):
        x0 = 24 + ci * (col_w + 16)
        hbg = theme.TEAM_BLUE_BG if team == "blue" else theme.TEAM_RED_BG
        hfg = theme.TEAM_BLUE_FG if team == "blue" else theme.TEAM_RED_FG
        title = "BLUE TEAM" if team == "blue" else "RED TEAM"
        hy = 76
        band = CR.team_band(col_w, 34, team=team, bg=hbg)
        sheet.paste(band, (x0, hy), band)
        d = ImageDraw.Draw(sheet)
        d.text((x0 + 14, hy + 17), title, font=CR.font(12), fill=hfg, anchor="lm")
        wr = 62 if team == "blue" else 38
        g = CR.winrate_gauge(168, 22, wr, bg=hbg)
        sheet.paste(g, (x0 + 118, hy + 6), g)
        pg = CR.power_gauge(150, 22, 41.6 if team == "blue" else 37.5, vmax=60.0, bg=hbg,
                            label="전투력", text=theme.TEXT)
        sheet.paste(pg, (x0 + 296, hy + 6), pg)
        d = ImageDraw.Draw(sheet)
        d.text((x0 + col_w - 12, hy + 17), "│ 밴 추천:", font=CR.font(11), fill=hfg, anchor="rm")
        for i, row in enumerate(SAMPLE[team]):
            draw_slot(sheet, x0, hy + 42 + i * (slot_h + gap), col_w, slot_h, team, row, theme.BG_CARD)

    # 뱃지·게이지 견본 줄
    y = 76 + 42 + 5 * (slot_h + gap) + 26
    d = ImageDraw.Draw(sheet)
    d.text((24, y), "뱃지", font=CR.font(12), fill=theme.TEXT_SUB)
    x = 24
    for pos in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
        b = CR.badge(34, POS_RING[pos], CR.mix(theme.BG_CARD, "#ffffff", 0.06), theme.BG_CARD,
                     icon=icon(pos), kind="POS-" + pos)
        sheet.paste(b, (x, y + 20), b)
        d.text((x + 17, y + 58), POS_KOR[pos], font=CR.font(9), fill=theme.TEXT_MUT, anchor="ma")
        x += 46
    x += 24
    d.text((x, y), "티어", font=CR.font(12), fill=theme.TEXT_SUB)
    for tier in ("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER",
                 "GRANDMASTER", "CHALLENGER"):
        b = CR.badge(34, TIER_RING[tier], CR.mix(theme.BG_CARD, "#ffffff", 0.06), theme.BG_CARD,
                     icon=icon(tier), kind="TIER-" + tier)
        sheet.paste(b, (x, y + 20), b)
        d.text((x + 17, y + 58), tier[:6], font=CR.font(8), fill=theme.TEXT_MUT, anchor="ma")
        x += 46

    # 게이지 견본(비율별)
    y2 = y + 84
    d.text((24, y2), "예상 승률 게이지 — 15 / 50 / 85%", font=CR.font(12), fill=theme.TEXT_SUB)
    gx = 24
    for pct in (15, 50, 85):
        g = CR.winrate_gauge(200, 24, pct, bg=theme.BG_CARD)
        sheet.paste(g, (gx, y2 + 20), g)
        gx += 214

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)
    print("저장:", out_path, sheet.size, "cache:", CR.cache_info()["items"])
    return out_path


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
