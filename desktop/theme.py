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
SCRIM       = "#000000"   # 모달 백드롭·그림자 전용(순수 검정은 여기서만)

# ── 2.2 Ink hierarchy (텍스트 4단계) ──────────────────────────────────
TEXT        = "#e7eaf3"   # 기본 텍스트 (웹 --txt)
TEXT_SUB    = "#9aa3b8"   # 보조 텍스트/라벨 (웹 --sub)
TEXT_MUT    = "#7d869c"   # 흐린 텍스트/메타 (웹 --mut). 2026-11-27 웹과 동기화 — BG_CARD 위 4.51:1(AA)
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

SUCCESS_SOFT = "#7ee1a8"  # 밝은 성공 텍스트(어두운 배경 위 'UP!'·초대 계열) — SUCCESS 의 밝은 잉크

# 롤 색 (탑/정글/미드/원딜/서폿) — 웹 POS_COLOR와 동일
POS_TOP     = "#c9482f"
POS_JG      = "#2f9d57"
POS_MID     = "#3a73e8"   # == WIN
POS_ADC     = "#d9a13a"
POS_SUP     = "#8a5cd6"   # == PURPLE

# ── 2.5 헤더 타일 액센트 (상단 13칸 아이콘 색 — 하드코딩 승격) ────────
TILE_GUIDE    = TEAM_BLUE_FG  # 📖 사용안내
TILE_INVITE   = SUCCESS_SOFT  # 🎮 팀초대
TILE_SETTINGS = TEXT          # ⚙ 설정
TILE_LOG      = TEXT_SUB      # 🗒 로그
TILE_DONATE   = "#ff8fb1"     # 💝 후원하기(하트 핑크 — 타일 아이콘 전용)
TILE_OFF      = "#6b7789"     # 토글 꺼짐(모스트: 전체라인) — 켜짐은 SUCCESS

# 기술용 색(시각 팔레트 아님)
CHROMA_KEY  = "#010203"   # 초상화/카드 오버레이의 '투명' 키 컬러 — 화면에 그려지지 않는다

# 연승 불꽃 애니메이션 팔레트(5연승 이상 닉네임) — 시각 토큰이 아니라 효과 시퀀스
BURN_COLORS = ("#FFE08A", "#FFC44A", "#FF9E33", "#FF7A29", "#FF5A1F",
               "#FF7A29", "#FF9E33", "#FFC44A")

# ── 딕셔너리 접근용(선택) ─────────────────────────────────────────────
COLORS = {
    "BG": BG, "BG_BAR": BG_BAR, "BG_INPUT": BG_INPUT, "BG_CARD": BG_CARD,
    "BG_RAISED": BG_RAISED, "SCRIM": SCRIM,
    "TEXT": TEXT, "TEXT_SUB": TEXT_SUB, "TEXT_MUT": TEXT_MUT, "TEXT_ON": TEXT_ON,
    "LINE": LINE, "LINE_STRONG": LINE_STRONG,
    "ACCENT": ACCENT, "ACCENT_H": ACCENT_H,
    "WIN": WIN, "TEAM_BLUE": TEAM_BLUE, "TEAM_BLUE_BG": TEAM_BLUE_BG, "TEAM_BLUE_FG": TEAM_BLUE_FG, "TEAM_BLUE_SOFT": TEAM_BLUE_SOFT,
    "LOSE": LOSE, "TEAM_RED": TEAM_RED, "TEAM_RED_BG": TEAM_RED_BG, "TEAM_RED_FG": TEAM_RED_FG, "TEAM_RED_SOFT": TEAM_RED_SOFT,
    "GOLD": GOLD, "SUCCESS": SUCCESS, "SUCCESS_SOFT": SUCCESS_SOFT, "WARN": WARN, "INFO": INFO, "PURPLE": PURPLE,
    "TILE_GUIDE": TILE_GUIDE, "TILE_INVITE": TILE_INVITE, "TILE_SETTINGS": TILE_SETTINGS,
    "TILE_LOG": TILE_LOG, "TILE_DONATE": TILE_DONATE, "TILE_OFF": TILE_OFF,
    "CHROMA_KEY": CHROMA_KEY,
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


# ── 5. 공통 위젯 옵션 (헤어라인 카드/입력) ─────────────────────────────
def hairline(bg=None, focus=ACCENT, thickness=1, **kw):
    """E1 카드·입력 공통 옵션 — 1px 헤어라인 + bd 0.  tk.Frame(p, **theme.hairline(theme.BG_CARD))
       focus 색은 Entry/Text 가 포커스를 받을 때의 보더색(highlightcolor)."""
    opts = {"bd": 0, "relief": "flat", "highlightthickness": thickness,
            "highlightbackground": LINE, "highlightcolor": focus}
    if bg is not None:
        opts["bg"] = bg
    opts.update(kw)
    return opts


# ── 6. ttk 다크 테마 (Windows 기본 밝은 회색 위젯 혼입 방지) ──────────
def apply_ttk_theme(root=None, font=None):
    """ttk 위젯(TCombobox/Vertical·Horizontal.TScrollbar/TCheckbutton/TNotebook/Treeview)을
       다크 토큰으로 통일한다. clam 기반 — 색 지정이 전 플랫폼에서 먹는 테마를 우선 쓰고,
       없으면 현재 테마에 그대로 색만 입힌다. 어떤 이유로든 실패해도 앱 실행을 막지 않는다(조용히 폴백).
       font: 앱의 이름 있는 폰트(UF(...))를 넘기면 체크박스 글자도 창 크기 배율을 따라간다."""
    try:
        from tkinter import ttk
    except Exception:
        return None
    try:
        st = ttk.Style(root)
    except Exception:
        return None
    try:
        if "clam" in st.theme_names():
            st.theme_use("clam")
    except Exception:
        pass

    def _c(style, **kw):
        try: st.configure(style, **kw)
        except Exception: pass

    def _m(style, **kw):
        try: st.map(style, **kw)
        except Exception: pass

    # 기본 컨테이너 — ttk 프레임/라벨이 밝은 회색으로 남지 않게
    _c("TFrame", background=BG)
    _c("TLabel", background=BG, foreground=TEXT)
    _c("TLabelframe", background=BG, bordercolor=LINE, lightcolor=BG, darkcolor=BG)
    _c("TLabelframe.Label", background=BG, foreground=TEXT_SUB)

    # 체크박스(설정 창)
    _c("TCheckbutton", background=BG, foreground=TEXT, focuscolor=BG,
       bordercolor=LINE, lightcolor=BG, darkcolor=BG,
       indicatorbackground=BG_INPUT, indicatorforeground=TEXT_ON, indicatorrelief="flat",
       **(({"font": font}) if font is not None else {}))
    _m("TCheckbutton",
       background=[("active", BG)],
       foreground=[("disabled", TEXT_MUT)],
       indicatorbackground=[("selected", ACCENT), ("active", BG_RAISED)])

    # 콤보박스(티어·패치 필터·창 크기 프리셋)
    _c("TCombobox", fieldbackground=BG_INPUT, background=BG_RAISED, foreground=TEXT,
       arrowcolor=TEXT_SUB, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
       selectbackground=BG_INPUT, selectforeground=TEXT, padding=SP_1)
    _m("TCombobox",
       fieldbackground=[("readonly", BG_INPUT), ("disabled", BG_BAR)],
       foreground=[("readonly", TEXT), ("disabled", TEXT_MUT)],
       background=[("active", BG_RAISED), ("readonly", BG_RAISED)],
       arrowcolor=[("active", TEXT), ("disabled", TEXT_MUT)])

    # 스크롤바(세로/가로 공통)
    for _sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        _c(_sb, background=BG_RAISED, troughcolor=BG_INPUT, bordercolor=LINE,
           arrowcolor=TEXT_SUB, lightcolor=BG_RAISED, darkcolor=BG_RAISED,
           relief="flat", gripcount=0, arrowsize=SP_3)
        _m(_sb, background=[("active", LINE_STRONG), ("pressed", LINE_STRONG)],
           arrowcolor=[("active", TEXT)])

    # 노트북 탭
    _c("TNotebook", background=BG, bordercolor=LINE, lightcolor=BG, darkcolor=BG,
       tabmargins=(0, SP_1, 0, 0))
    _c("TNotebook.Tab", background=BG_CARD, foreground=TEXT_SUB, bordercolor=LINE,
       lightcolor=BG_CARD, darkcolor=BG_CARD, padding=(SP_3, SP_1))
    _m("TNotebook.Tab", background=[("selected", BG_RAISED)],
       foreground=[("selected", TEXT)], expand=[("selected", (0, 0, 0, 0))])

    # 트리뷰(표)
    _c("Treeview", background=BG_CARD, fieldbackground=BG_CARD, foreground=TEXT,
       bordercolor=LINE, lightcolor=BG_CARD, darkcolor=BG_CARD, borderwidth=0, rowheight=22)
    _c("Treeview.Heading", background=BG_RAISED, foreground=TEXT_SUB,
       bordercolor=LINE, relief="flat")
    _m("Treeview", background=[("selected", BG_RAISED)], foreground=[("selected", TEXT)])
    _m("Treeview.Heading", background=[("active", BG_RAISED)], foreground=[("active", TEXT)])

    # 콤보 드롭다운 목록은 ttk 가 아니라 tk.Listbox 로 뜬다 → 옵션DB로 색을 준다
    if root is not None:
        try:
            for pat, val in (("*TCombobox*Listbox.background", BG_INPUT),
                             ("*TCombobox*Listbox.foreground", TEXT),
                             ("*TCombobox*Listbox.selectBackground", ACCENT),
                             ("*TCombobox*Listbox.selectForeground", TEXT_ON),
                             ("*TCombobox*Listbox.borderWidth", 0)):
                root.option_add(pat, val)
        except Exception:
            pass
    return st


# ── 7. Windows DWM 다크 타이틀바 ───────────────────────────────────────
# 창 상단의 흰 제목 표시줄(비클라이언트 영역)을 앱 배경과 같은 다크 톤으로 맞춘다.
# 네이티브 캡션을 그대로 쓰므로 에어로 스냅·리사이즈 프레임·작업표시줄 아이콘은 손대지 않는다.
# 비-Windows(테스트·Linux 빌드)에서는 조용히 통과한다 — 어떤 경우에도 앱 실행을 막지 않는다.
DWMWA_USE_IMMERSIVE_DARK_MODE = 20        # Windows 10 20H1+ / 11
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19    # Windows 10 1809~1909 폴백
DWMWA_CAPTION_COLOR = 35                  # Windows 11 22000+ — 캡션 배경
DWMWA_TEXT_COLOR = 36                     # Windows 11 22000+ — 캡션 글자


def hex_to_colorref(hex_color):
    """'#RRGGBB' → Win32 COLORREF 0x00BBGGRR. DWM 색 인자는 이 바이트 순서(RGB 역순)다.
       #0f1117 → 0x0017110f, #eef1f7 → 0x00f7f1ee."""
    h = str(hex_color).strip().lstrip("#")
    if len(h) != 6:
        raise ValueError("hex_color must be #RRGGBB: " + str(hex_color))
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def apply_dark_titlebar(win, bg_hex=None, text_hex=None):
    """창 상단 제목 표시줄을 다크로 (Windows 10 1809+ / Windows 11).
       bg_hex = 캡션 배경(= 앱 배경), text_hex = 캡션 글자색. 둘 다 생략하면 BG/TEXT 토큰.
       Windows 11 에서는 캡션/글자 색까지 앱 팔레트에 맞춘다(구형 빌드는 다크 모드만).
       성공 여부를 bool 로 돌려주되, 실패해도 예외를 올리지 않는다(앱은 그대로 뜬다)."""
    bg_hex = bg_hex or BG
    text_hex = text_hex or TEXT
    try:
        import ctypes
        dwm = ctypes.windll.dwmapi
        user32 = ctypes.windll.user32
    except Exception:
        return False   # 비-Windows: 조용히 통과

    try:
        win.update_idletasks()
    except Exception:
        pass
    try:
        # Tk 의 winfo_id() 는 자식 HWND — DWM 은 최상위(프레임) HWND 를 요구한다.
        hwnd = int(user32.GetParent(win.winfo_id()) or win.winfo_id())
    except Exception:
        return False
    if not hwnd:
        return False

    try:
        caption = hex_to_colorref(bg_hex)
    except Exception:
        caption = hex_to_colorref(BG)
    try:
        text = hex_to_colorref(text_hex)
    except Exception:
        text = hex_to_colorref(TEXT)

    def _set(attr, value):
        try:
            val = ctypes.c_int(int(value))
            hr = dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), ctypes.c_uint(int(attr)),
                                           ctypes.byref(val), ctypes.sizeof(val))
            # S_OK(0) 만 성공 — 구형 Windows 는 '모르는 속성'에 예외 대신 에러 코드를 돌려준다
            # (그래서 20 이 실패하면 19 로 내려가 다크 모드를 걸어야 한다).
            return hr in (0, None)
        except Exception:
            return False

    def _apply():
        if not _set(DWMWA_USE_IMMERSIVE_DARK_MODE, 1):
            _set(DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, 1)   # 1809~1909
        _set(DWMWA_CAPTION_COLOR, caption)               # Win11 22000+ (실패해도 다크 모드만으로 OK)
        _set(DWMWA_TEXT_COLOR, text)

    _apply()
    try:   # 창이 처음 그려질 때 한 번 더 — 매핑 전 호출은 일부 빌드에서 무시된다.
        win.bind("<Map>", lambda _e: _apply(), add="+")
    except Exception:
        pass
    return True


# ── 버튼 팩토리 ───────────────────────────────────────────────────────
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
