# -*- coding: utf-8 -*-
"""
squad.gg 디자인 토큰 (데스크탑) — 웹 index.html의 :root 팔레트와 동일한 값.
DESIGN.md(프로젝트 루트) §2~4의 단일 토큰 표를 Tkinter에서 소비하는 모듈.

규칙:
- 새 hex 리터럴을 위젯에 직접 쓰지 말 것. 반드시 이 모듈의 토큰을 참조(theme.BG 등).
- 색 변경은 여기(그리고 웹 :root) 한 곳만 고치면 양쪽에 반영됨(규약 기반 동기화).
- Tkinter 제약: box-shadow/gradient/둥근모서리/alpha 불가 → 깊이는 surface 사다리 + 1px 헤어라인(highlightthickness)으로만.
"""

# ── 2.1 Surface ladder (배경 표면 사다리) ─────────────────────────────
BG          = "#11131a"   # canvas: 앱/창 배경 (웹 --bg)
BG_BAR      = "#171a23"   # 헤더/상단 바 = surface-1 (웹 --bg2)
BG_INPUT    = "#171a23"   # 입력 필드/리스트박스/우물 = surface-1
BG_CARD     = "#1b1f2b"   # 카드/패널/모달 바디 = surface-2 (웹 --card)
BG_RAISED   = "#212636"   # 올라온/활성 표면·중립 버튼 = surface-3 (웹 --card2)
SCRIM       = "#000000"   # 모달 백드롭 전용(순수 검정은 여기서만)

# ── 2.2 Ink hierarchy (텍스트 4단계) ──────────────────────────────────
TEXT        = "#e7eaf3"   # 기본 텍스트 (웹 --txt)
TEXT_SUB    = "#9aa3b8"   # 보조 텍스트/라벨 (웹 --sub)
TEXT_MUT    = "#717a91"   # 흐린 텍스트/메타 (웹 --mut)
TEXT_ON     = "#0e1017"   # 골드/밝은 채움 위의 텍스트

# ── 2.3 Borders (헤어라인 — 깊이 담당) ────────────────────────────────
LINE        = "#2a3042"   # 모든 카드/행/입력 보더 (웹 --line)
LINE_STRONG = "#3a4056"   # 강조/포커스 카드 엣지 (웹 --line-2)

# ── 2.4 Brand + semantic status (브랜드 + 시맨틱) ─────────────────────
ACCENT      = "#5b8cff"   # 브랜드 액센트: 로고, 주요 CTA, 포커스 링, 링크
ACCENT_H    = "#7ba0ff"   # 브랜드 컨트롤 hover

WIN         = "#3a73e8"   # 승리/블루팀 (웹 --win == --blue)
TEAM_BLUE   = "#3a73e8"
TEAM_BLUE_BG = "#16243f"  # 블루팀 헤더/카드 배경 워시 (웹 --blue-bg)
TEAM_BLUE_FG = "#9cc0ff"  # 블루팀 라인업/제목 텍스트

TEAM_BLUE_SOFT = "#182233" # 블루팀 슬롯 행(은은한 팀 틴트 — 큰 면적용, BG_CARD와 -bg 워시의 중간)

LOSE        = "#e84057"   # 패배/레드팀 (웹 --lose == --red)
TEAM_RED    = "#e84057"
TEAM_RED_BG = "#3a1c25"   # 레드팀 헤더/카드 배경 워시 (웹 --red-bg)
TEAM_RED_FG = "#ff9aa8"   # 레드팀 라인업/제목 텍스트
TEAM_RED_SOFT  = "#281a20" # 레드팀 슬롯 행(은은한 팀 틴트)

GOLD        = "#e0a437"   # 명예/골드(웹 --gold). 데스크탑 기존 밝은골드(#F5D47A)를 원하면 이 값만 교체.
SUCCESS     = "#2bb177"   # 성공/긍정 시너지/다운로드 OK (웹 --green)
WARN        = "#e8930c"   # 경고/대기/주의 (웹 --warn)
INFO        = "#39c7d6"   # 정보/ACE/보조 하이라이트 (웹 --cyan)
PURPLE      = "#8a5cd6"   # 서폿 롤/신화 티어 (웹 --purple)

# 롤 색 (탑/정글/미드/원딜/서폿) — 웹 POS_COLOR와 동일
POS_TOP     = "#c9482f"
POS_JG      = "#2f9d57"
POS_MID     = "#3a73e8"   # == WIN
POS_ADC     = "#d9a13a"
POS_SUP     = "#8a5cd6"   # == PURPLE

# ── 딕셔너리 접근용(선택) ─────────────────────────────────────────────
COLORS = {
    "BG": BG, "BG_BAR": BG_BAR, "BG_INPUT": BG_INPUT, "BG_CARD": BG_CARD,
    "BG_RAISED": BG_RAISED, "SCRIM": SCRIM,
    "TEXT": TEXT, "TEXT_SUB": TEXT_SUB, "TEXT_MUT": TEXT_MUT, "TEXT_ON": TEXT_ON,
    "LINE": LINE, "LINE_STRONG": LINE_STRONG,
    "ACCENT": ACCENT, "ACCENT_H": ACCENT_H,
    "WIN": WIN, "TEAM_BLUE": TEAM_BLUE, "TEAM_BLUE_BG": TEAM_BLUE_BG, "TEAM_BLUE_FG": TEAM_BLUE_FG, "TEAM_BLUE_SOFT": TEAM_BLUE_SOFT,
    "LOSE": LOSE, "TEAM_RED": TEAM_RED, "TEAM_RED_BG": TEAM_RED_BG, "TEAM_RED_FG": TEAM_RED_FG, "TEAM_RED_SOFT": TEAM_RED_SOFT,
    "GOLD": GOLD, "SUCCESS": SUCCESS, "WARN": WARN, "INFO": INFO, "PURPLE": PURPLE,
}

# ── 3. Typography (Malgun Gothic 스케일) ──────────────────────────────
_FF = "Malgun Gothic"
FONTS = {
    "TITLE": (_FF, 20, "bold"),   # 메인 타이틀
    "H1":    (_FF, 16, "bold"),   # 모달 헤더(14/15/16 드리프트 통일)
    "H2":    (_FF, 13, "bold"),   # 카드/슬롯 제목
    "BODY":  (_FF, 11),           # 본문/버튼
    "SMALL": (_FF, 10),           # 캡션/설명
    "MICRO": (_FF, 9),            # 최소 라벨
    "NUM":   ("Consolas", 11),    # 숫자/초대코드(자리 정렬)
}

# ── 4. Spacing (4px 베이스 — padx/pady/ipad*) ─────────────────────────
SPACING = {"XS": 4, "S": 8, "M": 12, "L": 16, "XL": 24, "XXL": 32}
SP_1, SP_2, SP_3, SP_4, SP_6, SP_8 = 4, 8, 12, 16, 24, 32


# ── 버튼 팩토리(다음 패스용, 선택) ────────────────────────────────────
# 모든 버튼에 일관된 색/hover/geometry 부여. kind: neutral/primary/danger/gold/success/warn/info/purple/win
_BTN_KIND = {
    "neutral": (BG_RAISED, TEXT_SUB, BG_CARD),
    "primary": (ACCENT,   TEXT,     ACCENT_H),
    "danger":  (LOSE,     TEXT,     "#c22f43"),
    "gold":    (GOLD,     TEXT_ON,  "#c88f2c"),
    "success": (SUCCESS,  TEXT,     "#249c67"),
    "warn":    (WARN,     TEXT,     "#c9800a"),
    "info":    (INFO,     TEXT_ON,  "#2fb0bd"),
    "purple":  (PURPLE,   TEXT,     "#764fbb"),
    "win":     (WIN,      TEXT,     "#3163c9"),
}

def make_button(parent, text, kind="neutral", **kw):
    """일관 스타일 tk.Button. tkinter는 함수 상단에서 import된 곳에서 넘겨줄 필요 없이 지역 import."""
    import tkinter as tk
    bg, fg, active = _BTN_KIND.get(kind, _BTN_KIND["neutral"])
    opts = dict(bg=bg, fg=fg, activebackground=active, activeforeground=fg,
                font=FONTS["BODY"], bd=0, relief="flat", padx=SP_3, pady=SP_1, cursor="hand2")
    opts.update(kw)
    return tk.Button(parent, text=text, **opts)
