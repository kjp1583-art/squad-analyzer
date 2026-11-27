# -*- coding: utf-8 -*-
"""🪶🎨 [v83.75] 분석기 경량화 + Pillow 카드 회귀 테스트.

재는 것
  ① 데이터 경량화 — _slim_rows(문자열 공유)가 '값·구조'를 바꾸지 않고 메모리만 줄이는가,
     시트 캐시가 예산/유휴 기준으로 원본 행을 내리는가(그리고 협곡 탭은 예산 압박에서 살아남는가).
  ② 계산 결과 보존 — 최근성 가중치(_recency_w_cell)가 예전 _recency_score 와 같은 값인가,
     견제압력(bp) 재작성이 **수정 전 산식 그대로** 같은 값을 내는가(아래 레퍼런스 구현과 대조).
  ③ Pillow 카드 — 슬롯 카드/게이지/뱃지가 요청 크기로 나오고, 색·비율이 맞고, 캐시가 동작·상한되는가.
  ④ 배선 — 슬롯 카드 배경·헤더 밴드·게이지·뱃지가 실제 UI 생성 코드에 붙어 있고,
     Pillow 가 없을 때(CARD_UI=False) 예전 문장 표기로 되돌아가는가.

   python3 tests/analyzer_light_ui_test.py        (창·네트워크 없이 실행)
"""
import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from _analyzer_headless import load_analyzer, synthetic_rows  # noqa: E402

S = load_analyzer()
SRC_PATH = os.path.join(ROOT, "desktop", "squad_analyzer.py")
SRC = open(SRC_PATH, encoding="utf-8").read()
TREE = ast.parse(SRC)

sys.path.insert(0, os.path.join(ROOT, "desktop"))
import card_render as CR  # noqa: E402
import theme  # noqa: E402


def deep(obj, seen=None):
    """객체가 붙잡고 있는 바이트(공유 문자열은 1회만)."""
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    size = sys.getsizeof(obj)
    if isinstance(obj, (str, bytes, int, float, bool, type(None))):
        return size
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += deep(k, seen) + deep(v, seen)
        return size
    if isinstance(obj, (list, tuple, set, frozenset)):
        for it in obj:
            size += deep(it, seen)
        return size
    return size


def _func(name):
    """짬입 함수(create_graphic_ui 내부의 _card_photo 등)도 찾는다."""
    for n in ast.walk(TREE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f"{name} 없음")


class _FakeSheet:
    def __init__(self, title, rows, gid=4242):
        self.title = title
        self.rows = rows
        self.id = gid


class _SheetCacheCase(unittest.TestCase):
    """캐시·경량화는 전역 상태를 만진다 — 테스트마다 원래 설정으로 되돌린다."""

    def setUp(self):
        self._saved = (S.SHEET_CACHE_SLIM, S.SHEET_CACHE_BUDGET_ROWS, S.SHEET_CACHE_IDLE_SEC,
                       dict(S.global_sheet_cache), dict(S.global_cache_time),
                       dict(S._SHEET_CACHE_LAST), dict(S._SHEET_CACHE_HITS))
        S.global_sheet_cache.clear()
        S.global_cache_time.clear()
        S._SHEET_CACHE_LAST.clear()
        S._SHEET_CACHE_HITS.clear()

    def tearDown(self):
        (S.SHEET_CACHE_SLIM, S.SHEET_CACHE_BUDGET_ROWS, S.SHEET_CACHE_IDLE_SEC,
         gc_, gt_, gl_, gh_) = self._saved
        for d, saved in ((S.global_sheet_cache, gc_), (S.global_cache_time, gt_),
                         (S._SHEET_CACHE_LAST, gl_), (S._SHEET_CACHE_HITS, gh_)):
            d.clear()
            d.update(saved)

    def load(self, sheet, force=True):
        """실제 fetch 경로만 합성 데이터로 바꿔 get_sheet_data_cached 를 그대로 태운다."""
        orig_gviz, orig_svc = S._gviz_rows_by_gid, S._svc_get_all_values
        S._gviz_rows_by_gid = lambda gid, timeout=8: None
        S._svc_get_all_values = lambda sheet_obj, retries=3: sheet.rows
        try:
            return S.get_sheet_data_cached(sheet, force=force)
        finally:
            S._gviz_rows_by_gid, S._svc_get_all_values = orig_gviz, orig_svc


class T_SlimRows(unittest.TestCase):
    """① 저장 전 경량화 — 값은 그대로, 메모리만 준다."""

    def test_values_and_shape_unchanged(self):
        rows = synthetic_rows(3000)
        before = [list(r) for r in rows]
        S.SHEET_CACHE_SLIM = True
        out = S._slim_rows(rows)
        self.assertIs(out, rows, "제자리(in-place) 경량화 — 새 리스트를 만들면 일시적으로 2배가 된다")
        self.assertEqual(out, before, "값이 하나라도 달라지면 안 된다")
        self.assertTrue(all(isinstance(r, list) for r in out), "행은 list 그대로(호출부 계약)")
        self.assertEqual(len(out), len(before))

    def test_repeated_cells_share_objects(self):
        rows = [["게임ID", "포지션", "결과"], ["G1", "탑", "승리"], ["G2", "탑", "승리"], ["G3", "탑", "패배"]]
        S.SHEET_CACHE_SLIM = True
        S._slim_rows(rows)
        self.assertIs(rows[1][1], rows[2][1], "같은 포지션 문자열은 한 객체를 공유해야 한다")
        self.assertIs(rows[1][2], rows[2][2], "같은 결과 문자열도 공유")
        self.assertIsNot(rows[2][2], rows[3][2], "다른 값은 다른 객체")

    def test_memory_drops_on_full_size_sheet(self):
        rows = synthetic_rows(6000)
        before = deep(rows)
        S.SHEET_CACHE_SLIM = True
        S._slim_rows(rows)
        after = deep(rows)
        self.assertGreater(before - after, 500_000, f"저장할 게임ID·아이템처럼 유니크한 열은 공유 불가 — 그래도 500KB↑ 줄어야 한다: {before} → {after}")
        self.assertLess(after, before * 0.85, f"경량화 후가 85% 미만이어야 한다: {before} → {after}")

    def test_high_cardinality_column_is_not_pooled(self):
        """게임ID 처럼 유니크한 열은 풀링을 포기한다(공유 이득 0 + dict 만 커짐)."""
        rows = [["게임ID", "포지션"]] + [["KR_%d" % i, "탑"] for i in range(40)]
        S.SHEET_CACHE_SLIM = True
        S._slim_rows(rows, col_limit=8)
        self.assertEqual(rows[1][0], "KR_0")
        self.assertEqual(rows[40][0], "KR_39")
        self.assertIs(rows[1][1], rows[2][1])

    def test_flag_off_keeps_original_objects(self):
        a, b = "x" + "", "x" + ""       # 리터럴 상수 공유를 피해 '다른 객체'로 만든다
        rows = [["a", "b"], [a, "y"], [b, "y"]]
        S.SHEET_CACHE_SLIM = False
        try:
            S._slim_rows(rows)
            self.assertIs(rows[1][0], a)
            self.assertIs(rows[2][0], b)
        finally:
            S.SHEET_CACHE_SLIM = True


class T_SheetCache(unittest.TestCase):
    """① 캐시가 원본 행을 영구 보관하지 않는다."""

    def setUp(self):
        self.case = _SheetCacheCase("run")
        self.case.setUp()
        S.SHEET_CACHE_SLIM = True
        S._sheet_cache_trim(budget=0, idle=0)      # 남은 것 비우기

    def tearDown(self):
        self.case.tearDown()

    def test_store_and_hit(self):
        sheet = _FakeSheet("T_A", synthetic_rows(300))
        got = self.case.load(sheet)
        self.assertEqual(len(got), 301)
        self.assertEqual(S._sheet_cache_stats()["tabs"], 1)
        again = self.case.load(sheet, force=False)
        self.assertIs(again, got, "신선 캐시면 같은 객체를 돌려준다(재조회 없음)")
        self.assertGreaterEqual(S._SHEET_CACHE_HITS.get("T_A", 0), 1)

    def test_budget_evicts_least_recent(self):
        S.SHEET_CACHE_BUDGET_ROWS = 1200
        S.SHEET_CACHE_IDLE_SEC = 0
        self.case.load(_FakeSheet("T_BIG", synthetic_rows(800, seed=1)))
        self.case.load(_FakeSheet("T_SMALL", synthetic_rows(400, seed=2)))
        self.case.load(_FakeSheet("T_NEW", synthetic_rows(400, seed=3)))
        st = S._sheet_cache_stats()
        self.assertLessEqual(st["rows"], 1200, f"예산을 넘겨 들고 있으면 안 된다: {st}")
        self.assertNotIn("T_BIG", list(S.global_sheet_cache), "가장 오래 안 쓴 탭부터 내린다")

    def test_hot_lane_tab_survives_budget_pressure(self):
        """협곡(CLASSIC_NORMAL)은 다른 탭보다 오래됐어도 예산 압박에서 마지막까지 남는다.
           801(협곡) + 401 = 1202 ≤ 1250 이지만 +401 = 1603 이면 예산 초과 → 먼저 쌓인 T_X 가 나간다."""
        S.SHEET_CACHE_BUDGET_ROWS = 1250
        S.SHEET_CACHE_IDLE_SEC = 0
        self.case.load(_FakeSheet("CLASSIC_NORMAL", synthetic_rows(800, seed=4)))
        self.case.load(_FakeSheet("T_X", synthetic_rows(400, seed=5)))
        self.case.load(_FakeSheet("T_Y", synthetic_rows(400, seed=6)))
        self.assertIn("CLASSIC_NORMAL", list(S.global_sheet_cache), "협곡 탭이 밀려나면 안 된다")
        self.assertNotIn("T_X", list(S.global_sheet_cache))
        self.assertLessEqual(S._sheet_cache_stats()["rows"], 1250)

    def test_idle_tab_released(self):
        S.SHEET_CACHE_BUDGET_ROWS = 0          # 예산은 끄고 유휴만 본다
        S.SHEET_CACHE_IDLE_SEC = 600
        self.case.load(_FakeSheet("T_IDLE", synthetic_rows(200, seed=7)))
        self.case.load(_FakeSheet("T_LIVE", synthetic_rows(200, seed=8)))
        drop = S._sheet_cache_trim(idle=600, now=S._SHEET_CACHE_LAST["T_LIVE"] + 1000, keep="T_LIVE")
        self.assertIn("T_IDLE", drop)
        self.assertIn("T_LIVE", S.global_sheet_cache)
        self.assertNotIn("T_IDLE", S.global_sheet_cache)

    def test_release_and_stats(self):
        self.case.load(_FakeSheet("T_R", synthetic_rows(100, seed=9)))
        self.assertTrue(S._sheet_cache_release("T_R"))
        self.assertFalse(S._sheet_cache_release("T_R"))
        self.assertEqual(S._sheet_cache_stats(), {"tabs": 0, "rows": 0})

    def test_slim_applied_on_store(self):
        S.SHEET_CACHE_SLIM = True
        rows = [["h1", "h2"], ["탑", "승리"], ["탑", "승리"]]
        self.case.load(_FakeSheet("T_S", rows))
        got = S.global_sheet_cache["T_S"]
        self.assertIs(got[1][0], got[2][0], "캐시에 담기 전에 문자열 공유가 적용된다")


class T_IndexRecency(unittest.TestCase):
    """② 최근성 가중치 — 예전 _recency_score 한 줄짜리 호출과 같은 값."""

    def test_cell_weight_matches_score(self):
        now = S.time.time()
        for ds in ("2026-11-01", "2026-11-01 21:33", "2026. 11. 1.", "2026/11/01",
                   "2025-01-05", "", "쓰레기값"):
            want = S._recency_score([(ds, 1)], now=now)[0]
            got = S._recency_w_cell(ds, now)
            self.assertAlmostEqual(got, want, places=6, msg=ds)

    def test_date_memo_returns_same_value(self):
        a = S._sheet_date("2026-11-27 21:00")
        b = S._sheet_date("2026-11-27 21:00")
        self.assertEqual(a, b)
        self.assertIsNotNone(a)
        self.assertIsNone(S._sheet_date(""))


class T_BanPressureEquivalence(unittest.TestCase):
    """② 견제압력(bp) 재작성이 '수정 전 산식 그대로' 같은 값을 내는지 — 독립 레퍼런스와 대조.

    아래 _ref_bp 는 v83.71 구현(선수 × 주챔프 × 판 3중 루프 + any(...))을 그대로 옮긴 것이다.
    최적화는 이 값을 바꾸지 않아야 한다(바꾸면 밴 추천 근거가 달라진다).
    """

    @staticmethod
    def _ref_bp(rows, by_pu):
        h = rows[0]
        ci = lambda n: h.index(n) if n in h else -1
        c_g, c_pu, c_ch, c_rs = ci("게임ID"), ci("PUUID"), ci("챔피언"), ci("결과")
        c_ps, c_tm, c_bn = ci("포지션"), ci("진영"), ci("밴")
        side, ban = {}, {}
        for r in rows[1:]:
            if len(r) <= max(c_g, c_pu, c_ch, c_rs, c_tm): continue
            res = str(r[c_rs]).strip()
            if res not in ("승리", "패배"): continue
            pu = str(r[c_pu]).strip().lower()
            gid = str(r[c_g]).strip()
            tm = str(r[c_tm]).strip()
            if not pu: continue
            side.setdefault(gid, {})[pu] = tm
            b = str(r[c_bn]).strip()
            if b and b not in ("밴 없음", "밴 안함", "기록 대기", "결과 대기", "평가 대기", "알수없음"):
                ban.setdefault(gid, {}).setdefault(tm, set()).add(b)
        import math
        bp = {}
        gs = [g for g in ban if len(side.get(g, {})) >= 8]
        if not gs:
            return bp
        for pu, e in by_pu.items():
            mains = sorted(((c, g) for c, (g, w) in e["champs"].items() if g >= 4), key=lambda x: -x[1])[:6]
            if not mains: continue
            pres = [g for g in gs if pu in side.get(g, {})]
            absent = [g for g in gs if pu not in side.get(g, {})]
            if len(pres) < 8 or len(absent) < 20: continue
            out = []
            for c, _n in mains:
                ino = 0
                for g in pres:
                    opp = "레드팀" if side[g].get(pu) == "블루팀" else "블루팀"
                    if c in ban[g].get(opp, set()):
                        ino += 1
                outo = sum(0.5 for g in absent if any(c in s for s in ban[g].values()))
                a, b = ino / len(pres), outo / len(absent)
                se = math.sqrt(max(a * (1 - a), 1e-6) / len(pres) + max(b * (1 - b), 1e-6) / len(absent))
                z = (a - b) / se if se > 0 else 0.0
                if z > 1.5 and a > b:
                    out.append({"champ": c, "targeted": int(round((a - b) * 100)), "z": round(z, 1)})
            if out:
                out.sort(key=lambda x: -x["targeted"])
                bp[pu] = out
        return bp

    def test_bp_matches_legacy_formula(self):
        rows = synthetic_rows(27376)
        idx = self._build(rows)
        want = self._ref_bp(rows, idx["by_pu"])
        got = idx["bp"]

        def norm(d):
            return {k: [(x["champ"], x["targeted"], x["z"]) for x in v] for k, v in (d or {}).items()}

        self.assertEqual(norm(got), norm(want), "견제압력 값이 수정 전 산식과 달라졌다")
        self.assertTrue(want, "합성 데이터에 밴 근거가 하나도 없으면 이 테스트는 의미가 없다")

    @staticmethod
    def _build(rows):
        class FS:
            def __init__(s, t, r):
                s.title = t
                s.rows = r
                s.id = 7

        class FB:
            def worksheet(s, n):
                if n != "CLASSIC_NORMAL":
                    raise KeyError(n)
                return FS(n, rows)

        o_book, o_get = S.global_spreadsheet, S.get_sheet_data_cached
        S.global_spreadsheet = FB()
        S.get_sheet_data_cached = lambda sheet_obj, force=False, prefer_service=False: rows
        try:
            return S._clan_index(force=True)
        finally:
            S.global_spreadsheet, S.get_sheet_data_cached = o_book, o_get


class T_PoolRowsFastPath(unittest.TestCase):
    """🪶 `_pool_rows` 가 '사람별 행 묶음'을 쓰든(수정 후) 27,000행을 통째로 훑든(수정 전) 같은 값을 낸다."""

    def test_fast_path_matches_full_scan(self):
        rows = synthetic_rows(12000, seed=31)

        class FS:
            def __init__(s, t, r):
                s.title = t
                s.rows = r
                s.id = 11

        class FB:
            def worksheet(s, n):
                if n != "CLASSIC_NORMAL":
                    raise KeyError(n)
                return FS(n, rows)

        o_book, o_get = S.global_spreadsheet, S.get_sheet_data_cached
        S.global_spreadsheet = FB()
        S.get_sheet_data_cached = lambda sheet_obj, force=False, prefer_service=False: rows
        try:
            S._clan_index(force=True)
            pus = ["pu-%04d-%s" % (i, "ab" * 18) for i in range(1, 4)]

            def run(fast):
                S._POOLROWS_CACHE["ts"].clear()
                S._POOLROWS_CACHE["data"].clear()
                S._BU_PU_CACHE.clear()
                orig = S._rows_by_puuid
                if not fast:
                    S._rows_by_puuid = lambda *a, **k: None
                try:
                    return [S._pool_rows(p) for p in pus]
                finally:
                    S._rows_by_puuid = orig

            slow, fast = run(False), run(True)
            self.assertTrue(any(slow), "합성 데이터에 전적이 있어야 비교가 의미 있다")
            self.assertEqual(fast, slow, "사람별 묶음을 써도 집계 결과가 같아야 한다")
        finally:
            S.global_spreadsheet, S.get_sheet_data_cached = o_book, o_get


class T_CardRender(unittest.TestCase):
    """③ Pillow 카드 — 크기·색·비율·캐시."""

    def setUp(self):
        CR.clear_cache()

    def test_import_does_not_need_tkinter(self):
        src = open(os.path.join(ROOT, "desktop", "card_render.py"), encoding="utf-8").read()
        self.assertNotIn("import tkinter", src)
        self.assertNotIn("from tkinter", src)

    def test_slot_card_size_and_colors(self):
        w, h = 320, 96
        img = CR.slot_card(w, h, team="blue", bg="#000000", fill="#182233").convert("RGB")
        self.assertEqual(img.size, (w, h))
        self.assertEqual(img.getpixel((0, 0)), (0, 0, 0), "둥근 모서리 밖은 컨테이너 배경색")
        self.assertEqual(img.getpixel((w - 1, h - 1)), (0, 0, 0))
        center = img.getpixel((w // 2, h // 2))
        self.assertLessEqual(sum(abs(c - t) for c, t in zip(center, (24, 34, 51))), 9,
                             f"카드 안쪽은 슬롯 프레임 bg 와 같아야 이음새가 없다: {center}")

    def test_slot_card_has_left_glow_gradient(self):
        img = CR.slot_card(320, 96, team="red", bg="#1b1f2b", fill="#281a20").convert("RGB")
        left_top = img.getpixel((7, 6))
        left_mid = img.getpixel((7, 48))
        inner = img.getpixel((160, 48))
        self.assertNotEqual(left_mid, inner, "좌측에 팀 컬러 글로우가 있어야 한다")
        self.assertGreater(left_mid[0], inner[0], "레드 팀 컬러는 붉은 쪽으로 돌아야 한다")

    def test_slot_card_cache_shared_and_bounded(self):
        a = CR.slot_card(200, 60, team="blue")
        b = CR.slot_card(200, 60, team="blue")
        self.assertIs(a, b, "같은 크기·색이면 같은 이미지 객체(10칸 공유)를 돌려준다")
        c = CR.slot_card(200, 62, team="blue")
        self.assertIsNot(a, c)
        for i in range(CR.CACHE_MAX + 12):
            CR.slot_card(100 + i, 40 + i)
        self.assertLessEqual(CR.cache_info()["items"], CR.CACHE_MAX, "캐시가 무한히 늘면 안 된다")

    def test_winrate_gauge_proportion_and_clamp(self):
        w, h = 200, 22
        img = CR.winrate_gauge(w, h, 25, bg="#16243f").convert("RGB")
        self.assertEqual(img.size, (w, h))
        blue_x, red_x = img.getpixel((20, h // 2)), img.getpixel((150, h // 2))
        self.assertGreater(blue_x[2], blue_x[0], f"25% 지점 왼쪽은 블루: {blue_x}")
        self.assertGreater(red_x[0], red_x[2], f"오른쪽은 레드: {red_x}")
        # 경계가 25%(x=50) 근처 — 글자(getbbox)를 피해 알약 아래쪽에서 본다
        row = [img.getpixel((x, h - 3)) for x in range(w)]
        edge = next((x for x in range(1, w - 2)
                     if row[x][0] > row[x][2] and row[x + 1][0] > row[x + 1][2]
                     and row[x - 1][2] >= row[x - 1][0]), None)
        self.assertIsNotNone(edge, "블루→레드 경계를 찾지 못했다")
        self.assertLess(abs(edge - 50), 6, f"25% 경계가 x=50 근처여야 한다: {edge}")

    def test_winrate_gauge_clamps(self):
        for pct in (-30, 0, 100, 170, None, "abc"):
            img = CR.winrate_gauge(160, 20, pct, bg="#16243f")
            self.assertEqual(img.size, (160, 20))

    def test_badge_ring_fill_and_icon(self):
        from PIL import Image
        icon = Image.new("RGBA", (20, 20), (0, 255, 0, 255))
        img = CR.badge(34, ring="#ff0000", fill="#101010", bg="#000000", icon=icon, kind="T").convert("RGB")
        self.assertEqual(img.size, (34, 34))
        self.assertEqual(img.getpixel((17, 17))[1], 255, "가운데는 아이콘(초록)")
        ring = img.getpixel((17, 1))
        self.assertGreater(ring[0], ring[2], f"테두리는 링 색(빨강): {ring}")
        self.assertEqual(img.getpixel((0, 0)), (0, 0, 0), "모서리는 위젯 배경")

    def test_badge_without_icon_still_rings(self):
        img = CR.badge(28, ring="#00ff00", fill="#111111", bg="#000000", icon=None, kind="P").convert("RGB")
        self.assertEqual(img.size, (28, 28))
        self.assertEqual(img.getpixel((14, 14)), (17, 17, 17))

    def test_team_band_and_power_gauge(self):
        band = CR.team_band(400, 30, team="blue", bg="#16243f").convert("RGB")
        self.assertEqual(band.size, (400, 30))
        self.assertNotEqual(band.getpixel((10, 15)), band.getpixel((390, 15)), "팀 컬러 그라데이션")
        pg = CR.power_gauge(140, 22, 42.0, vmax=60.0, bg="#16243f", label="전투력")
        self.assertEqual(pg.size, (140, 22))

    def test_hex_and_mix_helpers(self):
        self.assertEqual(CR.hex_rgb("#3a73e8"), (58, 115, 232, 255))
        self.assertEqual(CR.hex_rgb("3a73e8"), (58, 115, 232, 255))
        self.assertEqual(CR.mix("#000000", "#ffffff", 0.5)[:3], (128, 128, 128))
        self.assertEqual(CR.mix("#000000", "#ffffff", 5)[:3], (255, 255, 255), "범위를 넘는 t 는 잘라낸다")


class T_ThemeTokens(unittest.TestCase):
    def test_badge_ring_maps_cover_vocabulary(self):
        self.assertTrue(set(S.TIERS) <= set(theme.TIER_RING), set(S.TIERS) - set(theme.TIER_RING))
        self.assertTrue({"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"} <= set(theme.POS_RING))
        for c in list(theme.TIER_RING.values()) + list(theme.POS_RING.values()):
            self.assertRegex(c, r"^#[0-9a-fA-F]{6}$")


class T_UiWiring(unittest.TestCase):
    """④ UI 배선 — AST 로 확인(창을 만들 수 없는 환경)."""

    @classmethod
    def setUpClass(cls):
        cls.ui = _func("create_graphic_ui")
        cls.calls = [c for c in ast.walk(cls.ui) if isinstance(c, ast.Call)]

    def _by_name(self, name):
        return [c for c in self.calls if isinstance(c.func, ast.Name) and c.func.id == name]

    def test_slot_cards_get_image_background(self):
        got = [c for c in self._by_name("_card_bg")
               if c.args and isinstance(c.args[0], ast.Name) and c.args[0].id in ("bf", "rf")]
        self.assertEqual(len(got), 2, "블루/레드 슬롯 프레임 모두 카드 배경 이미지를 가져야 한다")

    def test_header_band_and_gauges(self):
        bands = [c for c in self._by_name("_team_band") if c.args]
        heads = [(c.args[0].id, c.args[1].value) for c in bands
                 if isinstance(c.args[0], ast.Name) and isinstance(c.args[1], ast.Constant)]
        self.assertIn(("b_head", "blue"), heads)
        self.assertIn(("r_head", "red"), heads)
        labels = {n.targets[0].id for n in ast.walk(self.ui)
                  if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
        for name in ("blue_wr_gauge", "blue_pw_gauge", "red_wr_gauge", "red_pw_gauge"):
            self.assertIn(name, labels, f"{name} 라벨이 없다")

    def test_gauges_are_updated_with_values(self):
        upd = _func("update_gui")
        calls = [c for c in ast.walk(upd) if isinstance(c, ast.Call)]
        wr = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == "_set_winrate_gauge"]
        pw = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == "_set_power_gauge"]
        self.assertEqual(len(wr), 2, "블루/레드 예상승률 게이지 갱신")
        self.assertEqual(len(pw), 2, "블루/레드 전투력 게이지 갱신")
        src = ast.unparse(upd)
        self.assertIn("_team_power_sum", src, "팀 전투력 합계를 넘긴다")

    def test_badges_replace_plain_icons(self):
        upd = _func("update_gui")
        calls = [c for c in ast.walk(upd) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Name) and c.func.id == "_badge_photo"]
        self.assertGreaterEqual(len(calls), 4, "블루/레드 × 티어/포지션 뱃지")
        src = ast.unparse(upd)
        self.assertIn("theme.TIER_RING", src)
        self.assertIn("theme.POS_RING", src)

    def test_title_falls_back_without_pillow(self):
        """Pillow/카드 렌더러가 없으면(CARD_UI=False) 예전처럼 제목에 승률 숫자를 쓴다."""
        upd = _func("update_gui")
        both = [c for c in ast.walk(upd) if isinstance(c, ast.Call)
                and isinstance(c.func, ast.Attribute) and c.func.attr == "config"]
        txt = [k.value for c in both for k in c.keywords
               if k.arg == "text" and isinstance(k.value, ast.IfExp)]
        joined = " ".join(ast.unparse(t) for t in txt)
        self.assertIn("예상 승률", joined)
        self.assertIn("CARD_UI", joined)

    def test_slot_rows_still_four_lines(self):
        """v83.71 계약 — 슬롯 4줄(아이디·전적·모스트·고승률픽)과 14칸 튜플 유지."""
        for var in ("blue_slots", "red_slots"):
            app = [c for c in self.calls if isinstance(c.func, ast.Attribute) and c.func.attr == "append"
                   and isinstance(c.func.value, ast.Name) and c.func.value.id == var]
            self.assertEqual(len(app), 1, var)
            self.assertEqual(len(app[0].args[0].elts), 14, f"{var} 튜플 인덱스 계약")
        self.assertNotIn("truncat", ast.unparse(self.ui).lower())

    def test_card_helpers_cached_by_size(self):
        """카드/게이지/뱃지/밴드는 (종류·크기·색·값) 키로 캐시한다 — 매 프레임 다시 그리지 않는다."""
        for name in ("_card_photo", "_gauge_photo", "_badge_photo"):
            src = ast.unparse(_func(name))
            self.assertIn(".get(", src, f"{name}: 캐시 조회")
            self.assertIn("if ph is not None", src, f"{name}: 캐시 허트면 바로 반환")
        for name in ("_card_bg", "_team_band"):
            src = ast.unparse(_func(name))
            self.assertIn("after(60", src, f"{name}: 크기 변경 디바운스")


if __name__ == "__main__":
    unittest.main(verbosity=2)
