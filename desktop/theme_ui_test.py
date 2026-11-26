"""디자인 리뉴얼(1~4) 회귀 테스트 — desktop/theme.py 토큰·make_button/apply_ttk_theme 동작과
   desktop/squad_analyzer.py 의 UI 계약(_HTile 13칸·config 동기화·헤어라인·슬롯 튜플)을 검증한다.

   이 환경에는 tkinter(디스플레이)가 없으므로 위젯을 실제로 만들지 않는다.
   - theme.py 는 tkinter 를 함수 안에서만 import → 모듈째 import 해서 값/동작을 본다.
   - make_button/apply_ttk_theme 는 가짜 tkinter 모듈을 sys.modules 에 꽂아 넘어가는 인자를 본다.
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

# 헤더 타일 13칸 — 아이콘 순서가 바뀌면 사용자가 보는 배치가 바뀐다(계약).
TILE_ICONS = ["📖", "🎮", "🏆", "🎖", "🧪", "🌐", "🔨", "🎯", "⚙", "🗒", "👑", "💝", "🛠"]

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


class AnalyzerUiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = open(SRC_PATH, encoding="utf-8").read()
        cls.tree = ast.parse(cls.src)
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
        self.assertIsNotNone(self.find_class("_HTile"))

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

    # ── 2. 상단 헤더 타일 ──
    def test_thirteen_tiles_in_two_rows(self):
        ui = self.find_func("create_graphic_ui")
        tiles = [c for c in self.calls_in(ui)
                 if isinstance(c.func, ast.Name) and c.func.id == "_HTile"]
        self.assertEqual(len(tiles), 13, "헤더 타일은 13칸(가로 2줄 7+6) 계약")
        icons = []
        for c in tiles:
            self.assertTrue(c.args and isinstance(c.args[0], ast.Constant), "타일 아이콘은 상수")
            icons.append(c.args[0].value)
        self.assertEqual(icons, TILE_ICONS)

        # 7개 윗줄 / 나머지 아랫줄
        htile = self.find_class("_HTile")
        init = next(n for n in htile.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        seven = [n for n in ast.walk(init)
                 if isinstance(n, ast.Compare) and isinstance(n.left, ast.Subscript)
                 and any(isinstance(x, ast.Constant) and x.value == 7 for x in n.comparators)]
        self.assertEqual(len(seven), 1, "앞 7개는 윗줄, 나머지는 아랫줄")

    def test_tile_accents_are_tokens(self):
        ui = self.find_func("create_graphic_ui")
        tiles = [c for c in self.calls_in(ui)
                 if isinstance(c.func, ast.Name) and c.func.id == "_HTile"]
        for c in tiles:
            accent = c.args[3]
            if isinstance(accent, ast.IfExp):
                self.assertIsInstance(accent.body, ast.Attribute)
                self.assertIsInstance(accent.orelse, ast.Attribute)
            else:
                self.assertIsInstance(accent, ast.Attribute, ast.dump(accent))   # theme.X
                self.assertEqual(accent.value.id, "theme")

    def test_header_is_slimmer_but_width_kept(self):
        ui = self.find_func("create_graphic_ui")
        assigns = {}
        for n in ast.walk(ui):
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    if isinstance(tgt, ast.Name):
                        assigns[tgt.id] = n.value
                    elif isinstance(tgt, ast.Tuple) and isinstance(n.value, ast.Tuple):
                        for el_t, el_v in zip(tgt.elts, n.value.elts):
                            if isinstance(el_t, ast.Name):
                                assigns[el_t.id] = el_v
        header_h = assigns["HEADER_H"]
        self.assertIsInstance(header_h, ast.Constant)
        self.assertGreaterEqual(header_h.value, 128)
        self.assertLessEqual(header_h.value, 136)          # 158 → 128~136 슬림화

        # 타일: 바깥 74×58 (안쪽 72×56 + 1px 보더) — 정사각형(74×74)에서 슬림 비율로
        tw, th = assigns["TILE_W"].value, assigns["TILE_H"].value
        self.assertEqual(tw, 72)
        self.assertEqual(th, 56)
        self.assertEqual(tw + 2, 74)                       # 가로 폭은 그대로(7칸 546px)
        self.assertLess(th, tw)

        # 헤더/광고 프레임이 HEADER_H 를 함께 따른다(배너 잘림 방지: 136-8=128 ≥ 120 배너 높이)
        frames = [c for c in self.calls_in(ui) if isinstance(c.func, ast.Attribute) and c.func.attr == "Frame"]
        ad_h = [self.kw(c, "height") for c in frames
                if isinstance(c.func.value, ast.Name) and c.func.value.id == "tk"]
        self.assertTrue(any(isinstance(v, ast.BinOp) and isinstance(v.op, ast.Sub) for v in ad_h if v is not None))
        self.assertGreaterEqual(header_h.value - 8, 120)

    def test_tile_has_hairline_and_hover(self):
        htile = self.find_class("_HTile")
        init = next(n for n in htile.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        frames = [c for c in self.calls_in(init) if isinstance(c.func, ast.Attribute) and c.func.attr == "Frame"]
        self.assertTrue(frames)
        self.assertTrue(any(self.kw(c, "highlightbackground") is not None
                            and self.kw(c, "highlightthickness") is not None for c in frames),
                        "타일에도 1px 헤어라인")
        names = [n.name for n in htile.body if isinstance(n, ast.FunctionDef)]
        self.assertIn("_hover", names)
        hover = next(n for n in htile.body if isinstance(n, ast.FunctionDef) and n.name == "_hover")
        src = ast.unparse(hover)
        self.assertIn("theme.LINE_STRONG", src)            # hover 보더 강조
        self.assertIn("theme.LINE", src)

    def test_posview_config_contract_preserved(self):
        """_posview_btn_sync / 설정 창이 쓰는 config(text=, bg=) 계약."""
        htile = self.find_class("_HTile")
        cfg = next(n for n in htile.body if isinstance(n, ast.FunctionDef) and n.name == "config")
        self.assertEqual([a.arg for a in cfg.args.args], ["self", "text", "bg"])
        self.assertTrue(any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and n.value.id == "config"
                            for n in htile.body), "configure = config 별칭 유지")

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

    # ── 3. 팀 슬롯 카드 ──
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
