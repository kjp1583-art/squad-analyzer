"""디자인 리뉴얼(1~4) + 2026-11-27 상단 개편 회귀 테스트.
   - desktop/theme.py: 토큰·make_button/apply_ttk_theme 동작 + DWM 다크 타이틀바 헬퍼(apply_dark_titlebar).
   - desktop/squad_analyzer.py: lol.ps 스타일 텍스트 메뉴 계약(8칸·config 동기화·헤더 108~116px·
     제거된 5개 버튼 미노출·핵심 함수 시그니처 보존)을 검증한다.

   이 환경에는 tkinter(디스플레이)가 없으므로 위젯을 실제로 만들지 않는다.
   - theme.py 는 tkinter 를 함수 안에서만 import → 모듈째 import 해서 값/동작을 본다.
   - make_button/apply_ttk_theme 는 가짜 tkinter 모듈을 sys.modules 에 꽂아 넘어가는 인자를 본다.
     apply_dark_titlebar 는 가짜 ctypes(진짜 ctypes + 가짜 windll)로 DWM 호출을 들여다본다.
   - squad_analyzer.py 는 Windows 전용 import 가 많아 AST 로 구조·토큰 사용을 검증한다.

   python3 desktop/theme_ui_test.py
"""
import ast
import importlib.util
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
THEME_PATH = os.path.join(HERE, "theme.py")
SRC_PATH = os.path.join(HERE, "squad_analyzer.py")

HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")

# 헤더 텍스트 메뉴 8칸 — 아이콘 없이 글자만, 이 순서·이 이름이 사용자가 보는 메뉴다(계약).
NAV_LABELS = ["팀초대", "모의밴픽", "SQUAD.GG", "AUC.GG", "포지션별", "설정", "팀뽑선정", "후원하기"]
# 2026-11-27 개편으로 메뉴에서 뺑 5개 — UI 버튼만 사라지고 기능 정의는 남아야 한다.
REMOVED_LABELS = ["사용안내", "명예전당", "내부티어", "티어관리", "로그"]

# 기능·로직 보존 확인용 — UI 만 건드렸는데 실수로 지워지면 잡는다.
CORE_SIGNATURES = {
    "_live_poll_skip": ["active_id", "last_gid", "recorded", "last_t", "now", "gap"],
    "coach_map_ok": ["is_custom"],
    "_draft_coach_tick": ["s_json", "headers", "base_url"],
    "_team_split": ["entries", "cidx", "avoid_key"],
    "_captain_pick": ["entries", "exclude_tnorms", "cidx"],
    "_pos_recommend": ["A", "B", "idx"],
    "_ban_candidates": ["pool_rows", "ally_champs", "dead", "limit", "quiz", "bp", "threat", "weak"],
    "_clan_index": ["force"],
    "save_clan_tier": ["name", "tier"],
    "update_hof_stats": ["force"],
    "_spell_overlay_tick": ["root"],
    "_spellcheck_hotkey_loop": [],
    "ad_banner_engine": [],
    "update_gui": [],
}


def load_theme():
    spec = importlib.util.spec_from_file_location("theme_under_test", THEME_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg, bg):
    a, b = _lum(fg), _lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _is_emoji(ch):
    o = ord(ch)
    return (0x1F000 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF) or (0x2B00 <= o <= 0x2BFF) or o == 0xFE0F


# ── 가짜 tkinter ──────────────────────────────────────────────────────
class FakeWidget:
    def __init__(self, parent=None, **kw):
        self.parent, self.kw = parent, dict(kw)


class FakeStyle:
    records, maps, used = {}, {}, None

    def __init__(self, master=None):
        self.master = master

    def theme_names(self):
        return ("clam", "default")

    def theme_use(self, name):
        FakeStyle.used = name

    def configure(self, style, **kw):
        FakeStyle.records.setdefault(style, {}).update(kw)

    def map(self, style, **kw):
        FakeStyle.maps.setdefault(style, {}).update(kw)


class FakeRoot:
    def __init__(self):
        self.options = {}

    def option_add(self, pattern, value):
        self.options[pattern] = value


def install_fake_tkinter():
    tk = types.ModuleType("tkinter")
    tk.Button = type("Button", (FakeWidget,), {})
    ttk = types.ModuleType("tkinter.ttk")
    ttk.Style = FakeStyle
    tk.ttk = ttk
    saved = {k: sys.modules.get(k) for k in ("tkinter", "tkinter.ttk")}
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = ttk
    return saved


def restore_modules(saved):
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


class ThemeTokens(unittest.TestCase):
    def setUp(self):
        self.t = load_theme()

    def test_roles_are_hex(self):
        names = ["BG", "BG_BAR", "BG_INPUT", "BG_CARD", "BG_RAISED", "SCRIM",
                 "TEXT", "TEXT_SUB", "TEXT_MUT", "TEXT_ON", "LINE", "LINE_STRONG",
                 "ACCENT", "ACCENT_H", "WIN", "TEAM_BLUE", "TEAM_BLUE_BG", "TEAM_BLUE_FG",
                 "TEAM_BLUE_SOFT", "LOSE", "TEAM_RED", "TEAM_RED_BG", "TEAM_RED_FG", "TEAM_RED_SOFT",
                 "GOLD", "SUCCESS", "SUCCESS_SOFT", "WARN", "INFO", "PURPLE",
                 "POS_TOP", "POS_JG", "POS_MID", "POS_ADC", "POS_SUP",
                 "TILE_GUIDE", "TILE_INVITE", "TILE_SETTINGS", "TILE_LOG", "TILE_DONATE", "TILE_OFF",
                 "CHROMA_KEY"]
        for n in names:
            v = getattr(self.t, n, None)
            self.assertIsInstance(v, str, n)
            self.assertRegex(v, HEX6, n)
        self.assertEqual(len(self.t.BURN_COLORS), 8)

    def test_semantic_aliases_stay_identical(self):
        t = self.t
        self.assertEqual(t.TEAM_BLUE, t.WIN)      # 웹 --win == --blue
        self.assertEqual(t.TEAM_RED, t.LOSE)      # 웹 --lose == --red
        self.assertEqual(t.POS_MID, t.WIN)
        self.assertEqual(t.POS_SUP, t.PURPLE)
        self.assertEqual(t.BG_BAR, t.BG_INPUT)    # surface-1 공유

    def test_contrast_aa(self):
        t = self.t
        self.assertGreaterEqual(contrast(t.TEXT, t.BG_CARD), 7.0)        # 본문 AAA
        self.assertGreaterEqual(contrast(t.TEXT_SUB, t.BG_CARD), 4.5)    # 보조 AA
        self.assertGreaterEqual(contrast(t.TEXT_MUT, t.BG_CARD), 4.5)    # 흐린 글자 AA (2026-11-26 웹 상향분)
        self.assertGreaterEqual(contrast(t.TEXT_ON, t.GOLD), 4.5)        # 골드 채움 위 글자

    def test_text_mut_matches_web(self):
        self.assertEqual(self.t.TEXT_MUT.lower(), "#7d869c")

    def test_colors_dict_covers_roles(self):
        for k in ("BG", "BG_CARD", "LINE", "TEXT", "ACCENT", "GOLD", "TILE_INVITE"):
            self.assertEqual(self.t.COLORS[k], getattr(self.t, k))

    def test_spacing_scale(self):
        t = self.t
        self.assertEqual((t.SP_1, t.SP_2, t.SP_3, t.SP_4, t.SP_6, t.SP_8), (4, 8, 12, 16, 24, 32))
        self.assertEqual(t.SPACING, {"XS": 4, "S": 8, "M": 12, "L": 16, "XL": 24, "XXL": 32})

    def test_fonts(self):
        f = self.t.FONTS
        for k in ("TITLE", "H1", "H2", "BODY", "SMALL", "MICRO", "NUM"):
            self.assertIn(len(f[k]), (2, 3), k)          # (family, size[, weight])
            self.assertIsInstance(f[k][0], str, k)
            self.assertIsInstance(f[k][1], int, k)
        self.assertEqual(f["NUM"][0], "Consolas")
        self.assertEqual(f["BODY"][0], "Malgun Gothic")

    def test_hairline_helper(self):
        h = self.t.hairline(self.t.BG_CARD)
        self.assertEqual(h["bg"], self.t.BG_CARD)
        self.assertEqual(h["highlightthickness"], 1)
        self.assertEqual(h["highlightbackground"], self.t.LINE)
        self.assertEqual(h["bd"], 0)
        self.assertEqual(h["relief"], "flat")
        self.assertEqual(h["highlightcolor"], self.t.ACCENT)   # 기본 포커스 링
        self.assertNotIn("bg", self.t.hairline())             # bg 생략 가능(위젯 기본색 유지)
        self.assertEqual(self.t.hairline(focus=self.t.LINE)["highlightcolor"], self.t.LINE)


class MakeButton(unittest.TestCase):
    def setUp(self):
        self.saved = install_fake_tkinter()
        self.t = load_theme()

    def tearDown(self):
        restore_modules(self.saved)

    def test_primary(self):
        b = self.t.make_button("parent", "저장", "primary")
        self.assertIsInstance(b, FakeWidget)
        self.assertEqual(b.parent, "parent")
        self.assertEqual(b.kw["text"], "저장")
        self.assertEqual(b.kw["bg"], self.t.ACCENT)
        self.assertEqual(b.kw["fg"], self.t.TEXT)
        self.assertEqual(b.kw["activebackground"], self.t.ACCENT_H)
        self.assertEqual(b.kw["bd"], 0)
        self.assertEqual(b.kw["relief"], "flat")
        self.assertEqual(b.kw["cursor"], "hand2")
        self.assertEqual(b.kw["padx"], self.t.SP_3)
        self.assertEqual(b.kw["pady"], self.t.SP_1)
        self.assertEqual(b.kw["font"], self.t.FONTS["BODY"])

    def test_every_kind_has_activebackground(self):
        for kind in ("neutral", "primary", "danger", "gold", "success", "warn", "info", "purple", "win"):
            b = self.t.make_button("p", "x", kind)
            self.assertTrue(b.kw["activebackground"], kind)
            self.assertEqual((b.kw["bg"], b.kw["fg"]), self.t._BTN_KIND[kind][:2], kind)

    def test_unknown_kind_falls_back_to_neutral(self):
        b = self.t.make_button("p", "x", "nope")
        self.assertEqual(b.kw["bg"], self.t.BG_RAISED)
        self.assertEqual(b.kw["fg"], self.t.TEXT_SUB)

    def test_kwargs_override(self):
        b = self.t.make_button("p", "x", "gold", width=20, pady=self.t.SP_3, command=len)
        self.assertEqual(b.kw["width"], 20)
        self.assertEqual(b.kw["pady"], self.t.SP_3)
        self.assertEqual(b.kw["command"], len)


class ApplyTtkTheme(unittest.TestCase):
    def setUp(self):
        FakeStyle.records.clear(); FakeStyle.maps.clear(); FakeStyle.used = None
        self.saved = install_fake_tkinter()
        self.t = load_theme()
        self.root = FakeRoot()

    def tearDown(self):
        restore_modules(self.saved)

    def test_uses_clam_and_darkens_every_widget_class(self):
        st = self.t.apply_ttk_theme(self.root)
        self.assertIsNotNone(st)
        self.assertEqual(FakeStyle.used, "clam")        # Windows 기본 회색 위젯 방지
        rec = FakeStyle.records
        for cls in ("TCombobox", "Vertical.TScrollbar", "Horizontal.TScrollbar",
                    "TCheckbutton", "TNotebook", "TNotebook.Tab", "Treeview", "Treeview.Heading",
                    "TFrame", "TLabel"):
            self.assertIn(cls, rec, cls)

        self.assertEqual(rec["TCombobox"]["fieldbackground"], self.t.BG_INPUT)
        self.assertEqual(rec["TCombobox"]["foreground"], self.t.TEXT)
        self.assertEqual(rec["TCombobox"]["arrowcolor"], self.t.TEXT_SUB)
        self.assertEqual(rec["Vertical.TScrollbar"]["troughcolor"], self.t.BG_INPUT)
        self.assertEqual(rec["Vertical.TScrollbar"]["background"], self.t.BG_RAISED)
        self.assertEqual(rec["Horizontal.TScrollbar"]["background"], self.t.BG_RAISED)
        self.assertEqual(rec["TNotebook"]["background"], self.t.BG)
        self.assertEqual(rec["Treeview"]["fieldbackground"], self.t.BG_CARD)
        self.assertEqual(rec["Treeview.Heading"]["background"], self.t.BG_RAISED)

    def test_combobox_popdown_listbox_is_dark(self):
        self.t.apply_ttk_theme(self.root)
        self.assertEqual(self.root.options["*TCombobox*Listbox.background"], self.t.BG_INPUT)
        self.assertEqual(self.root.options["*TCombobox*Listbox.foreground"], self.t.TEXT)

    def test_font_passthrough(self):
        self.t.apply_ttk_theme(self.root, font=("Malgun Gothic", 10))
        self.assertEqual(FakeStyle.records["TCheckbutton"]["font"], ("Malgun Gothic", 10))

    def test_never_raises_without_root(self):
        self.assertIsNotNone(self.t.apply_ttk_theme())

    def test_never_raises_when_ttk_is_broken(self):
        def boom(*a, **k):
            raise RuntimeError("no ttk here")
        sys.modules["tkinter.ttk"].Style = boom
        self.assertIsNone(self.t.apply_ttk_theme(self.root))   # 조용히 폴백(앱은 그대로 뜬다)


# ── 가짜 ctypes (DWM 호출 수집) ──────────────────────────────────────
import ctypes as _real_ctypes


class FakeDwm:
    def __init__(self, fail_attrs=(), error_attrs=()):
        self.calls = []
        self.fail = set(fail_attrs)
        self.error = set(error_attrs)   # 예외 대신 HRESULT 에러 코드를 돌려주는 속성(구형 Windows)

    def DwmSetWindowAttribute(self, hwnd, attr, ptr, size):
        a = int(getattr(attr, "value", attr))
        if a in self.fail:
            raise OSError("attribute not supported")
        h = int(getattr(hwnd, "value", hwnd))
        val = _real_ctypes.cast(ptr, _real_ctypes.POINTER(_real_ctypes.c_int)).contents.value
        self.calls.append((h, a, val))
        return 0x80070057 if a in self.error else 0


class FakeUser32:
    def __init__(self, parent=4242):
        self.parent = parent

    def GetParent(self, hwnd):
        return self.parent


class FakeWindll:
    def __init__(self, dwm=None, parent=4242):
        self.dwmapi = dwm or FakeDwm()
        self.user32 = FakeUser32(parent)


class FakeWin:
    def __init__(self, winfo_id=11):
        self._id = winfo_id
        self.binds, self.idle = [], 0

    def update_idletasks(self):
        self.idle += 1

    def winfo_id(self):
        return self._id

    def bind(self, seq, fn, add=None):
        self.binds.append(seq)


def install_fake_ctypes(windll):
    """진짜 ctypes 의 타입 헬퍼(c_int/byref/sizeof…)는 그대로 쓰고 windll 만 가짜로 바꿔치웁니다."""
    fake = types.ModuleType("ctypes")
    for name in dir(_real_ctypes):
        try: setattr(fake, name, getattr(_real_ctypes, name))
        except Exception: pass
    fake.windll = windll
    saved = sys.modules.get("ctypes")
    sys.modules["ctypes"] = fake
    return saved


class DarkTitlebar(unittest.TestCase):
    def setUp(self):
        self.t = load_theme()

    def tearDown(self):
        sys.modules.pop("ctypes", None)
        if _real_ctypes is not None:
            sys.modules["ctypes"] = _real_ctypes

    def test_helper_exists_with_contract(self):
        import inspect
        f = getattr(self.t, "apply_dark_titlebar", None)
        self.assertTrue(callable(f), "theme.apply_dark_titlebar 헬퍼가 필요하다")
        params = list(inspect.signature(f).parameters)
        self.assertEqual(params[:3], ["win", "bg_hex", "text_hex"], params)

    def test_dwm_attribute_numbers(self):
        self.assertEqual(self.t.DWMWA_USE_IMMERSIVE_DARK_MODE, 20)
        self.assertEqual(self.t.DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, 19)
        self.assertEqual(self.t.DWMWA_CAPTION_COLOR, 35)
        self.assertEqual(self.t.DWMWA_TEXT_COLOR, 36)

    def test_hex_to_colorref_is_0x00bbggrr(self):
        c = self.t.hex_to_colorref
        self.assertEqual(c("#0f1117"), 0x0017110f)   # R=0f G=11 B=17 → 0x00BBGGRR
        self.assertEqual(c("#eef1f7"), 0x00f7f1ee)
        self.assertEqual(c("#5b8cff"), 0x00ff8c5b)
        self.assertEqual(c(self.t.BG), self.t.hex_to_colorref(self.t.BG))
        with self.assertRaises(ValueError):
            c("nope")

    def test_silently_passes_without_windows(self):
        w = FakeWin()
        self.assertFalse(self.t.apply_dark_titlebar(w))   # ctypes.windll 없음 → False, 예외 없음
        self.assertFalse(self.t.apply_dark_titlebar(w, bg_hex="#0f1117"))

    def test_sets_dark_mode_and_caption_colors(self):
        dwm = FakeDwm()
        saved = install_fake_ctypes(FakeWindll(dwm))
        try:
            win = FakeWin(winfo_id=11)
            self.assertTrue(self.t.apply_dark_titlebar(win, bg_hex="#0f1117", text_hex="#eef1f7"))
        finally:
            sys.modules["ctypes"] = saved
        self.assertEqual(win.idle, 1, "update_idletasks 뒤에 적용")
        self.assertIn("<Map>", win.binds, "매핑 시점 재적용(일부 빌드는 매핑 전 값을 버린다)")
        got = {(a, v) for (_h, a, v) in dwm.calls}
        self.assertIn((20, 1), got, "DWMWA_USE_IMMERSIVE_DARK_MODE(20)=1")
        self.assertIn((35, 0x0017110f), got, "DWMWA_CAPTION_COLOR(35)=COLORREF")
        self.assertIn((36, 0x00f7f1ee), got, "DWMWA_TEXT_COLOR(36)=COLORREF")
        self.assertTrue(all(h == 4242 for (h, _a, _v) in dwm.calls), "최상위 창 HWND(GetParent)에 걸어야 함")

    def test_falls_back_to_old_dark_mode_attribute(self):
        dwm = FakeDwm(fail_attrs=(20,))
        saved = install_fake_ctypes(FakeWindll(dwm))
        try:
            self.assertTrue(self.t.apply_dark_titlebar(FakeWin()))
        finally:
            sys.modules["ctypes"] = saved
        attrs = {a for (_h, a, _v) in dwm.calls}
        self.assertIn(19, attrs, "구형 Windows(1809~1909)는 19")
        self.assertIn(35, attrs)
        self.assertIn(36, attrs)

    def test_falls_back_when_new_attribute_returns_error_code(self):
        """구형 빌드는 지원하지 않는 속성에 예외가 아니라 HRESULT 에러를 돌려준다 — 19 로 내려가야 한다."""
        dwm = FakeDwm(error_attrs=(20,))
        saved = install_fake_ctypes(FakeWindll(dwm))
        try:
            self.t.apply_dark_titlebar(FakeWin())
        finally:
            sys.modules["ctypes"] = saved
        self.assertIn((19, 1), {(a, v) for (_h, a, v) in dwm.calls})

    def test_defaults_follow_theme_tokens(self):
        dwm = FakeDwm()
        saved = install_fake_ctypes(FakeWindll(dwm))
        try:
            self.t.apply_dark_titlebar(FakeWin())
        finally:
            sys.modules["ctypes"] = saved
        got = {(a, v) for (_h, a, v) in dwm.calls}
        self.assertIn((35, self.t.hex_to_colorref(self.t.BG)), got)
        self.assertIn((36, self.t.hex_to_colorref(self.t.TEXT)), got)


class FakeTKWidget:
    """AnalyzerUiContract 의 _TextNavBtn 동작 테스트용 최소 위젯(configure/bind/pack 만)."""
    def __init__(self, parent=None, **kw):
        self.parent = parent
        self.kw = dict(kw)
        self.binds, self.packed = {}, None

    def pack(self, *a, **k):
        self.packed = (a, k)

    def bind(self, seq, fn, add=None):
        self.binds[seq] = fn

    def configure(self, **kw):
        self.kw.update(kw)

    config = configure

    def cget(self, k):
        return self.kw.get(k)

    def winfo_children(self):
        return []


class AnalyzerUiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = open(SRC_PATH, encoding="utf-8").read()
        cls.tree = ast.parse(cls.src)
        cls.theme_mod = load_theme()
        cls.fake_tk = types.SimpleNamespace(Frame=FakeTKWidget, Label=FakeTKWidget)
        cls.doc_calls = {  # docstring 은 제외한 '전체 노드'
            n for n in ast.walk(cls.tree)
        }

    # ── helpers ──
    def find_func(self, name, cls=None):
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
                return n
        return None

    def find_class(self, name):
        for n in ast.walk(self.tree):
            if isinstance(n, ast.ClassDef) and n.name == name:
                return n
        return None

    def calls_in(self, node):
        return [n for n in ast.walk(node) if isinstance(n, ast.Call)]

    def attr_calls(self, node, obj, attr):
        out = []
        for c in self.calls_in(node):
            f = c.func
            if isinstance(f, ast.Attribute) and f.attr == attr and \
                    isinstance(f.value, ast.Name) and f.value.id == obj:
                out.append(c)
        return out

    def kw(self, call, name):
        for k in call.keywords:
            if k.arg == name:
                return k.value
        return None

    # ── 0. 기본 ──
    def test_theme_is_imported_and_no_hex_literals_left(self):
        self.assertIn("import theme", self.src)
        pattern = re.compile(r"^#[0-9a-fA-F]{3,8}$")
        left = [(n.lineno, n.value) for n in ast.walk(self.tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and pattern.match(n.value)]
        self.assertEqual(left, [], f"UI 코드에 남은 hex 리터럴: {left[:10]}")

    def test_gui_entry_and_key_renderers_exist(self):
        for name in ("create_graphic_ui", "update_gui", "_spell_overlay_tick", "_draft_overlay_sync"):
            self.assertIsNotNone(self.find_func(name), name)
        self.assertIsNotNone(self.find_class("_TextNavBtn"), "헤더 메뉴는 텍스트 버튼(_TextNavBtn)")
        self.assertIsNone(self.find_class("_HTile"), "아이콘 타일(_HTile)은 상단에서 사라져야 함")

    def test_core_logic_signatures_untouched(self):
        seen = {}
        for n in ast.walk(self.tree):
            if isinstance(n, ast.FunctionDef) and n.name in CORE_SIGNATURES:
                seen[n.name] = [a.arg for a in n.args.args]
        for name, args in CORE_SIGNATURES.items():
            self.assertEqual(seen.get(name), args, name)

    # ── 1. ttk 테마 ──
    def test_ttk_theme_applied_at_startup_and_in_settings(self):
        ui = self.find_func("create_graphic_ui")
        self.assertGreaterEqual(len(self.attr_calls(ui, "theme", "apply_ttk_theme")), 1)
        settings = self.find_class("ClanSettingsWindow")
        self.assertEqual(len(self.attr_calls(settings, "theme", "apply_ttk_theme")), 1)

    # ── 2. 상단 텍스트 메뉴 바 (lol.ps 스타일) ──
    def nav_calls(self):
        ui = self.find_func("create_graphic_ui")
        return [c for c in self.calls_in(ui)
                if isinstance(c.func, ast.Name) and c.func.id == "_TextNavBtn"]

    def test_eight_text_menu_buttons_in_one_row(self):
        navs = self.nav_calls()
        self.assertEqual(len(navs), 8, "상단 메뉴는 텍스트 8칸(한 줄) 계약")
        labels = []
        for c in navs:
            lab = c.args[0]
            if isinstance(lab, ast.IfExp):        # 포지션 토글: 켜짐/꺼짐 문구
                lab = lab.body
            self.assertIsInstance(lab, ast.Constant, ast.dump(lab))
            self.assertIsInstance(lab.value, str)
            labels.append(lab.value)
        self.assertEqual(labels, NAV_LABELS)

        # 2줄로 깨지지 않게: 두 줄짜리 btn_row1/btn_row2 배치가 남아 있으면 실패
        ui_src = ast.unparse(self.find_func("create_graphic_ui"))
        self.assertNotIn("btn_row2", ui_src)

    def test_no_icons_left_in_header_menu(self):
        nav_src = ast.unparse(self.find_class("_TextNavBtn"))
        self.assertNotIn("Segoe UI Emoji", nav_src, "메뉴는 아이콘 없는 텍스트 전용")
        for c in self.nav_calls():
            lab = c.args[0].body if isinstance(c.args[0], ast.IfExp) else c.args[0]
            self.assertFalse(any(_is_emoji(ch) for ch in lab.value), lab.value)

    def test_removed_buttons_are_not_in_menu_but_features_survive(self):
        ui = self.find_func("create_graphic_ui")
        ui_src = ast.unparse(ui)
        for gone in REMOVED_LABELS:
            self.assertNotIn('"%s"' % gone, ui_src, gone)
        for c in self.nav_calls():
            lab = c.args[0].body if isinstance(c.args[0], ast.IfExp) else c.args[0]
            self.assertNotIn(lab.value, REMOVED_LABELS)
        self.assertNotIn("_HTile(", ui_src)

        # 기능은 살아 있어야 한다 — 정의·창 클래스를 지우면 회귀
        for cls_name in ("GuideWindow", "ClanRankingWindow", "TierAssessmentWindow", "TierAdminWindow"):
            self.assertIsNotNone(self.find_class(cls_name), cls_name)
        for fn_name in ("open_hof_window", "open_tier_window", "open_tieradmin_window", "_open_log"):
            self.assertIsNotNone(self.find_func(fn_name), fn_name)

    def test_text_nav_style_and_hover(self):
        nav = self.find_class("_TextNavBtn")
        src = ast.unparse(nav)
        self.assertIn("theme.TEXT", src)          # 활성·hover 글자
        self.assertIn("theme.TEXT_SUB", src)      # 기본 글자
        self.assertIn("theme.BG_RAISED", src)     # hover 미세 배경
        self.assertIn("theme.GOLD", src)          # 기본 밑줄(액센트)
        self.assertIn("height=2", src, "활성 밑줄은 2px")
        names = [n.name for n in nav.body if isinstance(n, ast.FunctionDef)]
        for m in ("_paint", "_hover", "_hit", "config"):
            self.assertIn(m, names)
        pad = next(n for n in nav.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "PAD_X" for t in n.targets))
        self.assertGreaterEqual(pad.value.value, 10, "lol.ps 스타일 좌우 여백 10~12px")
        self.assertLessEqual(pad.value.value, 12)
        self.assertTrue(any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and n.value.id == "config"
                            for n in nav.body), "configure = config 별칭 유지")

    def test_header_height_slim(self):
        ui = self.find_func("create_graphic_ui")
        assigns = {}
        for n in ast.walk(ui):
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    if isinstance(tgt, ast.Name):
                        assigns[tgt.id] = n.value
        header_h = assigns["HEADER_H"]
        self.assertIsInstance(header_h, ast.Constant)
        self.assertGreaterEqual(header_h.value, 108)
        self.assertLessEqual(header_h.value, 116, "1줄 메뉴바로 136 → 108~116 슬림화")

        # 광고 프레임 높이 = HEADER_H - 8, 배너 이미지는 그 높이에 맞춘다(AD_BANNER_H)
        frames = [c for c in self.calls_in(ui) if isinstance(c.func, ast.Attribute) and c.func.attr == "Frame"]
        ad_h = [self.kw(c, "height") for c in frames
                if isinstance(c.func.value, ast.Name) and c.func.value.id == "tk"]
        self.assertTrue(any(isinstance(v, ast.BinOp) and isinstance(v.op, ast.Sub) for v in ad_h if v is not None))
        ad_consts = {}
        for n in ast.parse(self.src).body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Tuple) and len(n.value.elts) == 2:
                if isinstance(n.targets[0], ast.Tuple):
                    for el_t, el_v in zip(n.targets[0].elts, n.value.elts):
                        if isinstance(el_t, ast.Name):
                            ad_consts[el_t.id] = el_v
        self.assertEqual(ad_consts["AD_BANNER_H"].value, header_h.value - 8,
                         "배너 높이 = 헤더 높이 - 위아래 pady(4+4)")
        self.assertGreaterEqual(ad_consts["AD_BANNER_W"].value, 300)

    def test_nav_fit_keeps_menu_on_one_line_at_1280(self):
        """1280(컴팩트)에서도 8칸이 잘리지 않게 폭을 지키는 장치가 있다."""
        fit = self.find_func("_nav_fit")
        self.assertIsNotNone(fit, "_nav_fit 폭 보정 필요")
        src = ast.unparse(fit)
        self.assertIn("winfo_width", src)
        self.assertIn("pack_forget", src)
        self.assertGreaterEqual(src.count("credit_row"), 2)
        self.assertIn("padx", src, "크레딧을 집혀도 넘치면 버튼 좌우 여백을 줄인다")
        self.assertIn("UF(10)", src, "마지막 수단은 메뉴 글자 한 단계 축소(11 → 10pt)")
        self.assertIn("nav_bar.winfo_reqwidth", src)
        ui_src = ast.unparse(self.find_func("create_graphic_ui"))
        self.assertIn("NAV_CREDIT_MIN_W", ui_src)
        self.assertIn("_nav_fit()", ui_src, "창 크기 변경(_ui_do)에서 폭 보정 호출")

    def test_dwm_applied_to_root_and_modals(self):
        ui = self.find_func("create_graphic_ui")
        root_calls = self.attr_calls(ui, "theme", "apply_dark_titlebar")
        self.assertGreaterEqual(len(root_calls), 1, "메인 창 상단 다크 타이틀바")
        self.assertIsNotNone(self.kw(root_calls[0], "bg_hex"), "메인 창은 앱 배경색을 넘긴다")
        for cls_name in ("ClanSettingsWindow", "ClanRankingWindow", "TierAssessmentWindow",
                         "GuideWindow", "TierAdminWindow", "PatchNoteWindow", "OnlineUsersWindow"):
            node = self.find_class(cls_name)
            self.assertGreaterEqual(len(self.attr_calls(node, "theme", "apply_dark_titlebar")), 1, cls_name)

    # ── 2.5 포지션 토글 동기화 계약 ──
    def test_posview_config_contract_preserved(self):
        """_posview_btn_sync / 설정 창이 쓰는 config(text=, bg=) 계약."""
        nav = self.find_class("_TextNavBtn")
        cfg = next(n for n in nav.body if isinstance(n, ast.FunctionDef) and n.name == "config")
        self.assertEqual([a.arg for a in cfg.args.args][:3], ["self", "text", "bg"])
        src = ast.unparse(cfg)
        self.assertIn("현재포지션", src)      # '모스트: 현재포지션' → '포지션별' 축약 유지
        self.assertIn("_active", src)         # bg 색 → 활성 밑줄 토글

        sync = self.find_func("_posview_btn_sync")
        self.assertIsNotNone(sync)
        src = ast.unparse(sync)
        self.assertIn("_POSVIEW_BTN", src)
        self.assertIn("b.config(text=", src)     # 문구 동기화
        self.assertIn("bg=", src)               # 색 동기화(SUCCESS/BG_RAISED)

        ui = self.find_func("create_graphic_ui")
        self.assertTrue(any(isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "_POSVIEW_BTN"
                            and isinstance(n.slice, ast.Constant) and n.slice.value == 0 for n in ast.walk(ui)),
                        "_POSVIEW_BTN[0] = btn_posview 등록 유지")
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "config"
                            and isinstance(n.func.value, ast.Name) and n.func.value.id == "btn_posview"
                            for n in ast.walk(ui)), "토글 상태를 밑줄로 반영(config(bg=))하는 초기 호출")

    # ── 3. 팀 슬롯 카드 ──
    # ── 2.6 텍스트 메뉴 버튼 동작(가짜 tkinter 로 실제 실행) ──
    def _load_text_nav_class(self):
        nav = self.find_class("_TextNavBtn")
        src = ast.get_source_segment(self.src, nav)
        self.assertIsNotNone(src)
        box = FakeTKWidget()
        ns = {"tk": self.fake_tk, "theme": self.theme_mod,
              "UF": lambda *a, **k: ("Malgun Gothic", 11), "nav_bar": box}
        exec(compile(src, "<nav>", "exec"), ns)   # 테스트에서만 클래스 소스를 그대로 실행
        return ns["_TextNavBtn"], box

    def test_text_nav_behaviour(self):
        cls, box = self._load_text_nav_class()
        hits = []
        b = cls("포지션별", lambda: hits.append(1))
        t = self.theme_mod
        self.assertEqual(b.tx.kw["text"], "포지션별")
        self.assertEqual(b.tx.kw["fg"], t.TEXT_SUB)     # 기본: 흐린 글자
        self.assertEqual(b.bar.kw["bg"], t.BG_BAR)     # 꺼짐: 밑줄 안 보임
        b._hover(True)
        self.assertEqual(b.tx.kw["fg"], t.TEXT)         # hover: 글자 밝아짐
        self.assertEqual(b.tx.kw["bg"], t.BG_RAISED)    # hover: 미세 배경
        b._hover(False)
        self.assertEqual(b.tx.kw["fg"], t.TEXT_SUB)
        self.assertEqual(b.tx.kw["bg"], t.BG_BAR)
        # 켜짐 — _posview_btn_sync 와 같은 호출(bg=SUCCESS) → 밑줄이 SUCCESS 로 산다
        b.config(text="모스트: 현재포지션", bg=t.SUCCESS)
        self.assertEqual(b.tx.kw["text"], "포지션별")
        self.assertEqual(b.bar.kw["bg"], t.SUCCESS)
        self.assertEqual(b.tx.kw["fg"], t.TEXT)
        # 다시 꺼짐 — bg=BG_RAISED → 밑줄·강조 해제
        b.config(text="모스트: 전체라인", bg=t.BG_RAISED)
        self.assertEqual(b.tx.kw["text"], "전체라인")
        self.assertEqual(b.bar.kw["bg"], t.BG_BAR)
        self.assertEqual(b.tx.kw["fg"], t.TEXT_SUB)
        # 클릭 → 명령 실행
        b._hit()
        self.assertEqual(hits, [1])
        # hover 는 밑줄 상태를 건드리지 않는다(켜짐은 켜짐대로)
        b.config(bg=t.SUCCESS)
        b._hover(True)
        self.assertEqual(b.bar.kw["bg"], t.SUCCESS)

    def test_slot_tuples_keep_fourteen_fields(self):
        ui = self.find_func("create_graphic_ui")
        appends = [c for c in self.calls_in(ui)
                   if isinstance(c.func, ast.Attribute) and c.func.attr == "append"
                   and isinstance(c.func.value, ast.Name) and c.func.value.id in ("blue_slots", "red_slots")]
        self.assertEqual(len(appends), 2)
        for c in appends:
            self.assertIsInstance(c.args[0], ast.Tuple)
            self.assertEqual(len(c.args[0].elts), 14, "슬롯 튜플 인덱스([12]=칸 프레임,[13]=엠블럼) 계약")

    def test_slot_hairline_and_team_accent_bar(self):
        ui = self.find_func("create_graphic_ui")
        frames = [c for c in self.calls_in(ui) if isinstance(c.func, ast.Attribute) and c.func.attr == "Frame"]
        hair = [c for c in frames
                if isinstance(self.kw(c, "highlightbackground"), ast.Attribute)
                and self.kw(c, "highlightbackground").attr == "LINE"]
        helper = self.attr_calls(ui, "theme", "hairline")
        self.assertGreaterEqual(len(hair) + len(helper), 8,
                                f"카드/슬롯/패널 헤어라인 부족: {len(hair)} + {len(helper)}")
        self.assertGreaterEqual(len(hair), 2, "슬롯 카드(블루/레드)는 직접 1px 헤어라인")
        bars = []
        for c in frames:
            w = self.kw(c, "width")
            bg = self.kw(c, "bg")
            if isinstance(w, ast.Constant) and w.value == 3 and isinstance(bg, ast.Attribute) \
                    and bg.attr in ("TEAM_BLUE", "TEAM_RED"):
                bars.append(bg.attr)
        self.assertEqual(sorted(bars), ["TEAM_BLUE", "TEAM_RED"], "슬롯 좌측 3px 팀 컬러 바")

    def test_numeric_labels_use_tabular_font(self):
        ui = self.find_func("create_graphic_ui")
        assign = [n for n in ast.walk(ui) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "FONT_SLOT_NUM" for t in n.targets)]
        self.assertEqual(len(assign), 1)
        src = ast.unparse(assign[0].value)
        self.assertIn("FONTS['NUM']", src)
        self.assertIn("UF(", src)          # 이름 있는 폰트 → 창 크기 배율 유지

        used = [c for c in self.calls_in(ui) if isinstance(c.func, ast.Attribute) and c.func.attr == "Label"
                and isinstance(self.kw(c, "font"), ast.Name) and self.kw(c, "font").id == "FONT_SLOT_NUM"]
        self.assertGreaterEqual(len(used), 2)   # 블루/레드 티어·전투력 라벨

    def test_cosmetic_reset_restores_hairline(self):
        reset = None
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "config":
                k = {kw.arg for kw in n.keywords}
                if {"highlightthickness", "highlightbackground", "bg"} <= k and \
                        isinstance(self.kw(n, "highlightthickness"), ast.Constant) and \
                        self.kw(n, "highlightthickness").value == 1:
                    reset = n
        self.assertIsNotNone(reset, "꾸미기 해제 시 1px 헤어라인 복원")

    # ── 4. 토큰 정리 / 모달 ──
    def test_modals_use_spacing_tokens_and_button_factory(self):
        for cls_name in ("ClanRankingWindow", "TierAssessmentWindow", "ClanSettingsWindow", "GuideWindow"):
            node = self.find_class(cls_name)
            self.assertIsNotNone(node, cls_name)
            self.assertGreaterEqual(ast.unparse(node).count("theme.SP_"), 3, cls_name)
        for cls_name in ("ClanRankingWindow", "TierAssessmentWindow", "ClanSettingsWindow"):
            node = self.find_class(cls_name)
            self.assertGreaterEqual(len(self.attr_calls(node, "theme", "make_button")), 1, cls_name)

    def test_modal_headers_and_bodies_use_surface_tokens(self):
        for cls_name in ("ClanRankingWindow", "TierAssessmentWindow", "ClanSettingsWindow", "GuideWindow"):
            node = self.find_class(cls_name)
            src = ast.unparse(node)
            self.assertIn("theme.BG", src, cls_name)
            self.assertFalse(re.search(r"#[0-9a-fA-F]{6}", src), cls_name)

    def test_raw_scrollbars_are_dark(self):
        """기본 tk.Scrollbar(Windows 회색)는 남기지 않는다."""
        left = [n.lineno for n in ast.walk(self.tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "Scrollbar" and isinstance(n.func.value, ast.Name) and n.func.value.id == "tk"]
        self.assertEqual(left, [], f"tk.Scrollbar 남음: {left}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
