# -*- coding: utf-8 -*-
"""🛡️ lol.ps 빌드 카드(desktop/lolps_build.py) 회귀 테스트.

  python3 tests/lolps_build_test.py

이 환경에는 tkinter(디스플레이)가 없으므로 창을 실제로 띄우지 않는다 — theme_ui_test.py 와 같은 방식으로
가짜 tkinter / 가짜 PIL.ImageTk 를 sys.modules 에 꽂아 '위젯을 어떻게 만들고 무엇을 넣는지'를 본다.
Pillow 렌더는 진짜로 돌려 이미지 크기·빈 카드 여부까지 확인한다.

검증 항목
  1) SvelteKit __data.json(devalue) 해석 + 실제 lol.ps 응답 fixture 파싱
  2) 픽 스왑 감지 — 폴링마다 내 칸 championId 가 바뀌면 대상이 따라 바뀌는가
  3) (챔피언, 라인) TTL 캐시 적중 / 실패 폴백 / 네트워크 없음
  4) 카드 렌더(펼침·접힘) + 이름이 칸을 넘지 않는지(잘림 방지)
  5) Tk 카드 창 생성·갱신·숨기기(가짜 tkinter)
"""
import gzip
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESKTOP = os.path.join(ROOT, "desktop")
FIXTURES = os.path.join(HERE, "fixtures")
if DESKTOP not in sys.path:
    sys.path.insert(0, DESKTOP)

import lolps_build as L  # noqa: E402


def load_fixture(name):
    with gzip.open(os.path.join(FIXTURES, name), "rt", encoding="utf-8") as fh:
        return json.load(fh)


def fake_statics():
    """네트워크 없이 이름표를 채운 StaticData."""
    st = L.StaticData(version="16.23.1", cache_dir="/tmp/lolps-test")
    st.items = {"3118": "악의", "2503": "어둠불꽃 횃불", "6655": "루덴의 메아리",
                "4645": "그림자불꽃", "3100": "리치베인", "3152": "마법공학 로켓 벨트",
                "3157": "존야의 모래시계", "3089": "라바돈의 죽음모자", "3020": "마법사의 신발"}
    st.runes = {"8112": {"name": "감전", "icon": "perk-images/Styles/Domination/Electrocute/Electrocute.png"},
                "8210": {"name": "무한한 정신", "icon": "x.png"}}
    st.trees = {"8100": {"name": "지배", "url": "https://ddragon/tree.png"},
                "8200": {"name": "마법", "url": "https://ddragon/tree2.png"}}
    st.spells = {"4": {"name": "점멸", "icon": "SummonerFlash.png"},
                 "14": {"name": "점화", "icon": "SummonerDot.png"}}
    st.ready = True
    return st


class NoNetImages(L.Images):
    """아이콘은 절대 받지 않는다(테스트에서 네트워크 금지) — 없는 아이콘 폴백 경로를 그대로 탄다."""

    def __init__(self):
        super().__init__(cache_dir="/tmp/lolps-test")
        self.loaded = []

    def _raw(self, url):
        return None


class FakePhoto:
    def __init__(self, image):
        self.image = image


# ── 1) 파서 ─────────────────────────────────────────────────────────────
class ParseTest(unittest.TestCase):
    def test_devalue_nested_refs(self):
        # [ {'a': 1, 'b': [2,3]}, 'hi', 7, 9 ]  → {'a':'hi','b':[7,9]}
        data = [{"a": 1, "b": 2}, "hi", [3, 4], 7, 9]
        self.assertEqual(L.devalue_resolve(data, 0), {"a": "hi", "b": [7, 9]})

    def test_devalue_bad_index(self):
        with self.assertRaises(L.LolPsError):
            L.devalue_resolve(["x"], 5)

    def test_parse_real_ahri_payload(self):
        payload = L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz"))
        self.assertIsNotNone(payload)
        self.assertEqual(payload.champion_id, 103)
        self.assertEqual(payload.lane, 2)
        self.assertEqual(payload.lane_label, "미드")
        self.assertEqual(payload.patch, "26.23")
        self.assertEqual(payload.version_id, 160)
        self.assertAlmostEqual(payload.win_rate, 51.14, places=2)
        self.assertAlmostEqual(payload.pick_rate, 9.94, places=2)
        self.assertEqual(payload.sample, 34691)
        self.assertEqual(payload.tier, 2)
        self.assertEqual(payload.ranking, 6)
        self.assertEqual(len(payload.variants), 2)
        first = payload.primary
        self.assertEqual(first.spells, (4, 14))
        self.assertEqual(first.first, (3118, 2503, 6655))
        self.assertEqual(first.second, (4645, 3100, 3152))
        self.assertEqual(first.third, (3157, 4645, 3089))
        self.assertEqual(first.combo, (3118, 4645, 3157, 3089))
        self.assertEqual(first.shoes, 3020)
        self.assertEqual(first.runes.main_tree, 8100)
        self.assertEqual(first.runes.sub_tree, 8200)
        self.assertEqual(first.runes.keystone, 8112)
        self.assertEqual(first.runes.main_runes, (8112, 8139, 8140, 8106))
        self.assertEqual(first.runes.sub_runes, (8210, 8226))
        self.assertEqual(first.runes.stat_perks, (5005, 5008, 5001))
        self.assertTrue(first.runes.has_page)

    def test_parse_low_sample_and_alt_spells(self):
        payload = L.parse_payload(load_fixture("lolps_kalista_nolane_data.json.gz"))
        self.assertIsNotNone(payload)
        self.assertEqual(payload.champion_id, 89)
        self.assertEqual(payload.lane, 4)          # lane 생략 → lol.ps 가 주 라인을 준다
        self.assertEqual(payload.lane_label, "서폿")
        self.assertGreaterEqual(len(payload.variants), 2)
        self.assertNotEqual(payload.variants[0].spells, payload.variants[1].spells)

    def test_parse_empty_summary_returns_none(self):
        payload = {"type": "data", "nodes": [
            {"type": "data", "data": [{"championId": 1, "champSummary": 2}, 999, []], "uses": {}}]}
        self.assertIsNone(L.parse_payload(payload))

    def test_parse_unknown_shape_raises(self):
        with self.assertRaises(L.LolPsError):
            L.parse_payload({"type": "data", "nodes": [{"type": "data", "data": [{"x": 1}]}]})
        with self.assertRaises(L.LolPsError):
            L.parse_payload("nope")

    def test_lane_ids(self):
        self.assertEqual(L.lane_id_of("TOP"), 0)
        self.assertEqual(L.lane_id_of("jungle"), 1)
        self.assertEqual(L.lane_id_of("MIDDLE"), 2)
        self.assertEqual(L.lane_id_of("BOTTOM"), 3)
        self.assertEqual(L.lane_id_of("UTILITY"), 4)
        self.assertEqual(L.lane_id_of("원딜"), 3)
        self.assertEqual(L.lane_id_of("서폿"), 4)
        self.assertIsNone(L.lane_id_of(""))
        self.assertIsNone(L.lane_id_of("fill"))
        self.assertEqual(L.LANE_IDS["탑"], 0)
        self.assertEqual(L.lane_name(4), "서폿")

    def test_build_url(self):
        self.assertIn("/champ/89/__data.json", L.build_url(89, 3))
        self.assertIn("lane=3", L.build_url(89, 3))
        self.assertNotIn("lane=", L.build_url(89, None))
        with self.assertRaises(ValueError):
            L.build_url(0, 1)


# ── 2) 픽 스왑 감지 ─────────────────────────────────────────────────────
def make_session(local_cell=3, my_champ=89, intent=0, pos="BOTTOM", puuid="me-1"):
    return {
        "localPlayerCellId": local_cell,
        "myTeam": [
            {"cellId": 1, "championId": 64, "assignedPosition": "JUNGLE", "puuid": "a"},
            {"cellId": local_cell, "championId": my_champ, "championPickIntent": intent,
             "assignedPosition": pos, "puuid": puuid},
            {"cellId": 4, "championId": 201, "assignedPosition": "UTILITY", "puuid": "b"},
        ],
        "theirTeam": [{"cellId": 5, "championId": 103, "assignedPosition": "MIDDLE"}],
    }


class PickSwapTest(unittest.TestCase):
    def test_my_cell_and_champion(self):
        cell, cid, pos = L.my_pick_from_session(make_session())
        self.assertEqual((cell, cid, pos), (3, 89, "BOTTOM"))

    def test_pick_swap_changes_champion(self):
        """내가 칼리스타를 픽한 뒤 팀원과 픽 스왑 → 같은 칸의 championId 가 바뀐다."""
        first = L.my_pick_from_session(make_session(my_champ=89))
        self.assertEqual(first[1], 89)
        # 스왑: 내 칸(3)은 201(브라움)을, 4번 칸은 89(칼리스타)를 갖는다
        swapped = make_session(my_champ=201)
        swapped["myTeam"][2]["championId"] = 89
        second = L.my_pick_from_session(swapped)
        self.assertEqual(second[1], 201)
        self.assertNotEqual(first[1], second[1])

    def test_pick_swap_propagates_to_tracker(self):
        """트래커는 폴링할 때마다 feed() 를 받아 새 챔피언 빌드로 갈아탄다(첫 픽에서 멈추지 않는다)."""
        tr = L.BuildTracker()
        tr.store = L.BuildStore()
        calls = []

        def fake_request(cid, lane=None, fetch=None):
            calls.append((cid, lane))

        tr.store.request = fake_request
        tr.feed(89, "BOTTOM")
        self.assertEqual(tr.target, (89, 3))
        rev1 = tr.rev
        tr.feed(89, "BOTTOM")               # 같은 값 — 대상/리비전 그대로
        self.assertEqual(tr.rev, rev1)
        tr.feed(201, "BOTTOM")              # 스왑 후
        self.assertEqual(tr.target, (201, 3))
        self.assertGreater(tr.rev, rev1)
        self.assertEqual(calls, [(89, 3), (201, 3)])
        tr.feed(201, "BOTTOM", phase="InProgress")     # 밴픽 끝 → 숨김
        self.assertEqual(tr.target, (0, None))

    def test_hover_intent_before_pick(self):
        _, cid, _ = L.my_pick_from_session(make_session(my_champ=0, intent=103))
        self.assertEqual(cid, 103)

    def test_puuid_fallback(self):
        session = make_session()
        session.pop("localPlayerCellId")
        cell, cid, _ = L.my_pick_from_session(session, my_puuid="me-1")
        self.assertEqual((cell, cid), (3, 89))

    def test_fallback_position(self):
        s = make_session(pos="")
        _, _, pos = L.my_pick_from_session(s, fallback_pos="미드")
        self.assertEqual(pos, "미드")
        self.assertEqual(L.lane_id_of(pos), 2)

    def test_no_session(self):
        self.assertEqual(L.my_pick_from_session(None), (None, 0, ""))
        self.assertEqual(L.my_pick_from_session({}), (None, 0, ""))


# ── 3) 캐시·조회 폴백 ──────────────────────────────────────────────────
class CacheTest(unittest.TestCase):
    def test_single_fetch_for_same_key(self):
        store = L.BuildStore()
        calls = []

        def fake(cid, lane):
            calls.append((cid, lane))
            return L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz"))

        store.request(103, 2, fetch=fake)
        for _ in range(40):
            store.peek(103, 2)
            store.request(103, 2, fetch=fake)
            if store.peek(103, 2)[1] == "ready":
                break
            store._worker_join = None
            import time
            time.sleep(0.05)
        payload, status = store.peek(103, 2)
        self.assertEqual(status, "ready")
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(payload.champion_id, 103)
        # 두 번째 요청은 캐시 적중 — 조회 안 함
        store.request(103, 2, fetch=fake)
        self.assertEqual(len(calls), 1)

    def test_negative_cache(self):
        store = L.BuildStore()
        calls = []

        def fake(cid, lane):
            calls.append(cid)
            return None

        store.request(999, 0, fetch=fake)
        import time
        for _ in range(40):
            if store.peek(999, 0)[1] == "empty":
                break
            time.sleep(0.05)
        self.assertEqual(store.peek(999, 0)[1], "empty")
        store.request(999, 0, fetch=fake)
        time.sleep(0.1)
        self.assertEqual(len(calls), 1)

    def test_failure_falls_back_quietly(self):
        store = L.BuildStore()

        def boom(cid, lane):
            raise L.LolPsError("HTTP 500")

        store.request(7, 1, fetch=boom)
        import time
        for _ in range(40):
            if store.peek(7, 1)[1] == "error":
                break
            time.sleep(0.05)
        self.assertEqual(store.peek(7, 1), (None, "error"))
        # 재시도 대기 중에는 다시 요청하지 않는다(초당 폴링으로 서버를 두드리지 않게)
        calls = []
        store.request(7, 1, fetch=lambda c, l: calls.append(c))
        time.sleep(0.1)
        self.assertEqual(calls, [])

    def test_request_without_fetcher_never_raises(self):
        store = L.BuildStore()
        store.request(0, 0)                    # 챔피언 없음
        store.request(5, None)                 # 백그라운드 조회(네트워크 실패해도 조용)
        import time
        time.sleep(0.2)

    def test_fetch_offline_raises_lolps_error(self):
        class BadSession:
            def get(self, *a, **kw):
                raise RuntimeError("no network")

        with self.assertRaises(Exception):
            L.fetch_build(103, 2, session=BadSession())

    def test_fetch_with_fake_response(self):
        payload = load_fixture("lolps_kalista_nolane_data.json.gz")

        class Resp:
            status_code = 200

            def json(self):
                return payload

        class Session:
            def __init__(self):
                self.urls = []

            def get(self, url, **kw):
                self.urls.append(url)
                return Resp()

        sess = Session()
        got = L.fetch_build(89, None, session=sess)
        self.assertTrue(got.auto_lane)
        self.assertEqual(got.lane, 4)
        self.assertNotIn("lane=", sess.urls[0])
        got2 = L.fetch_build(89, 3, session=sess)
        self.assertIn("lane=3", sess.urls[1])
        self.assertEqual(got2.lane, 4)          # 요청 라인 표본이 없어 주 라인으로 돌아온 응답
        self.assertTrue(got2.auto_lane)

    def test_fetch_same_lane_not_marked_auto(self):
        payload = load_fixture("lolps_ahri_mid_data.json.gz")

        class Resp:
            status_code = 200

            def json(self):
                return payload

        class Session:
            def get(self, url, **kw):
                return Resp()

        got = L.fetch_build(103, 2, session=Session())
        self.assertFalse(got.auto_lane)
        self.assertEqual(got.lane, 2)

    def test_lane_fallback_marks_auto(self):
        """미드를 요청했는데 표본이 없어 lol.ps 가 주 라인(서폿)을 돌려주면 '기준' 표시를 단다."""
        payload = load_fixture("lolps_kalista_nolane_data.json.gz")

        class Resp:
            status_code = 200

            def json(self):
                return payload

        class Session:
            def get(self, url, **kw):
                return Resp()

        got = L.fetch_build(89, 2, session=Session())     # 미드 요청 → 응답 laneId 4
        self.assertTrue(got.auto_lane)
        self.assertEqual(got.lane, 4)


# ── 4) 렌더 ────────────────────────────────────────────────────────────
class RenderTest(unittest.TestCase):
    def setUp(self):
        self.payload = L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz"))
        self.statics = fake_statics()
        self.images = NoNetImages()

    def test_render_card_size(self):
        img = L.render_card(self.payload, self.statics, self.images, "아리")
        # [v83.80] 카드 확대 — 폭 372 → 520, 글자·아이콘도 최종 픽셀 기준으로 키웠다
        self.assertEqual(img.size[0], 520)
        self.assertGreaterEqual(img.size[1], 500)
        self.assertEqual(img.mode, "RGBA")
        # 빈 카드가 아니다 — 글자/배경 픽셀이 여러 색으로 존재
        colors = img.convert("RGB").getcolors(maxcolors=200000)
        self.assertGreater(len(colors), 30)

    def test_render_collapsed(self):
        img = L.render_collapsed(self.payload, self.statics, self.images, "아리")
        self.assertEqual(img.size, (520, 88))

    def test_render_scale_keeps_output_size(self):
        """scale=1 과 scale=2 는 같은 최종 크기 — 2배는 선명도만 올린다."""
        one = L.render_card(self.payload, self.statics, self.images, "아리", scale=1)
        two = L.render_card(self.payload, self.statics, self.images, "아리", scale=2)
        self.assertEqual(one.size, two.size)

    def test_icon_sizes_are_final_pixels(self):
        """[v83.80] 아이콘 요청은 render_card 가 그리는 크기(최종 px × scale)와 같아야 캐시에 걸린다.

        전에는 26 을 요청해 놓고 2배 캔버스에 그대로 붙여, 축소 후 13px 로 쪼그라들었다.
        """
        self.assertEqual(
            (L.ICON_ITEM, L.ICON_CHAMP, L.ICON_SPELL, L.ICON_RUNE, L.ICON_KEYSTONE,
             L.ICON_TREE, L.ICON_SHARD, L.ICON_COLLAPSED),
            (36, 52, 34, 26, 36, 26, 22, 30))
        reqs = L.icon_requests_for(self.payload, self.statics)
        self.assertIn((self.statics.item(3118).url, L.ICON_ITEM * 2), reqs)
        self.assertIn((self.statics.spell(4).url, L.ICON_SPELL * 2), reqs)
        reqs1 = L.icon_requests_for(self.payload, self.statics, scale=1)
        self.assertIn((self.statics.item(3118).url, L.ICON_ITEM), reqs1)

    def test_render_without_static_names(self):
        """정적 데이터를 못 받아도(이름 폴백·아이콘 없음) 카드가 그려져야 한다."""
        blank = L.StaticData(version="", cache_dir="/tmp/lolps-test")
        img = L.render_card(self.payload, blank, self.images, "")
        self.assertEqual(img.size[0], 520)

    def test_render_needs_payload(self):
        with self.assertRaises(ValueError):
            L.render_card(None, self.statics, self.images, "x")

    def test_names_never_overflow(self):
        """아이템 이름은 칸 폭을 넘지 않는다(넘치면 두 줄/말줄임으로 잘라 그린다)."""
        from PIL import ImageDraw, Image
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        f1, f2 = L._font(13.5), L._font(12)
        for name in ("마법공학 로켓 벨트", "라바돈의 죽음모자", "존야의 모래시계", "아주아주아주긴아이템이름입니다"):
            max_w = 100
            lines = L._wrap_lines(draw, name, f1, f2, max_w)
            self.assertTrue(lines)
            self.assertLessEqual(len(lines), 2)
            for text, font in lines:
                self.assertLessEqual(L._text_w(draw, text, font)[0], max_w + 1, text)

    def test_fit_truncates(self):
        from PIL import ImageDraw, Image
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        got = L._fit(draw, "아주아주아주긴이름", L._font(10), 30)
        self.assertLessEqual(L._text_w(draw, got, L._font(10))[0], 32)

    def test_icon_requests_cover_card(self):
        reqs = L.icon_requests_for(self.payload, self.statics)
        urls = [u for u, _ in reqs]
        self.assertTrue(any("/img/item/3118.png" in u for u in urls))
        self.assertTrue(any("SummonerFlash.png" in u for u in urls))
        self.assertTrue(all(size > 0 for _, size in reqs))
        collapsed = L.icon_requests_for(self.payload, self.statics, collapsed=True)
        self.assertTrue(any("/img/item/3118.png" in u for u, _ in collapsed))


# ── 5) Tk 카드 창(가짜 tkinter) ─────────────────────────────────────────
class FakeLabel:
    def __init__(self, master=None, **kw):
        self.master = master
        self.options = dict(kw)
        self.binds = []
        self.geom = ""

    def pack(self, **kw):
        return None

    def configure(self, **kw):
        self.options.update(kw)

    config = configure

    def bind(self, seq, fn, add=None):
        self.binds.append((seq, fn))

    def cget(self, key):
        return self.options.get(key)


class FakeWindow:
    instances = []

    def __init__(self, master=None, **kw):
        self.master = master
        self.options = dict(kw)
        self.binds = []
        self.geometry_value = ""
        self.visible = True
        self.destroyed = False
        self.attributes_calls = []
        FakeWindow.instances.append(self)

    def title(self, text):
        self.options["title"] = text

    def overrideredirect(self, flag):
        self.options["overrideredirect"] = flag

    def attributes(self, *a):
        self.attributes_calls.append(a)

    def configure(self, **kw):
        self.options.update(kw)

    config = configure

    def bind(self, seq, fn, add=None):
        self.binds.append((seq, fn))

    def pack(self, **kw):
        return None

    def geometry(self, value=None):
        if value:
            self.geometry_value = value
            parts = value.split("+")
            if len(parts) == 3:
                self._x, self._y = int(parts[1]), int(parts[2])
        return self.geometry_value

    def winfo_x(self):
        return getattr(self, "_x", 100)

    def winfo_y(self):
        return getattr(self, "_y", 100)

    def winfo_width(self):
        return 520

    def winfo_height(self):
        return 400

    def winfo_exists(self):
        return not self.destroyed

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def update_idletasks(self):
        return None

    def deiconify(self):
        self.visible = True

    def withdraw(self):
        self.visible = False

    def lift(self):
        return None

    def destroy(self):
        self.destroyed = True


class TkOverlayTest(unittest.TestCase):
    def setUp(self):
        self._saved = {k: sys.modules.get(k) for k in ("tkinter", "PIL.ImageTk")}
        tk = types.ModuleType("tkinter")
        tk.Toplevel = FakeWindow
        tk.Label = FakeLabel
        sys.modules["tkinter"] = tk
        imgtk = types.ModuleType("PIL.ImageTk")
        imgtk.PhotoImage = FakePhoto
        sys.modules["PIL.ImageTk"] = imgtk
        import PIL
        self._pil_imgtk = getattr(PIL, "ImageTk", None)
        PIL.ImageTk = imgtk
        FakeWindow.instances = []
        self.root = FakeWindow()

    def tearDown(self):
        import PIL
        for k, v in self._saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        if self._pil_imgtk is None:
            try:
                del PIL.ImageTk
            except Exception:
                pass
        else:
            PIL.ImageTk = self._pil_imgtk

    def _overlay(self):
        pos = {}
        ov = L.BuildOverlay(self.root, pos_store=pos)
        return ov, pos

    def test_show_creates_window_and_sets_image(self):
        ov, pos = self._overlay()
        img = L.render_card(L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz")),
                            fake_statics(), NoNetImages(), "아리")
        ov.show(img, "103:2:1")
        self.assertIsNotNone(ov.win)
        self.assertTrue(ov.win.visible)
        self.assertEqual(ov.win.options.get("title"), "챔피언 빌드 (lol.ps)")
        self.assertTrue(ov.win.options.get("overrideredirect"))
        self.assertIn(("-topmost", True), [tuple(a) for a in ov.win.attributes_calls])
        self.assertEqual(ov.label.options.get("width"), 520)
        self.assertIn("520", ov.win.geometry_value)
        self.assertEqual(ov.key, "103:2:1")
        self.assertGreater(len(ov.label.binds), 2)     # 드래그·더블클릭 바인딩

    def test_geometry_keeps_position_on_size_change(self):
        ov, _ = self._overlay()
        img = L.render_card(L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz")),
                            fake_statics(), NoNetImages(), "아리")
        ov.show(img, "k1")
        first = ov.win.geometry_value
        small = L.render_collapsed(L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz")),
                                   fake_statics(), NoNetImages(), "아리")
        ov.show(small, "k1", collapsed=True)
        self.assertIn("520x88", ov.win.geometry_value)
        x_first = first.split("+")[1]
        x_now = ov.win.geometry_value.split("+")[1]
        self.assertEqual(x_first, x_now)

    def test_hide_and_dismiss(self):
        ov, _ = self._overlay()
        img = L.render_collapsed(L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz")),
                                 fake_statics(), NoNetImages(), "아리")
        ov.show(img, "k")
        ov.hide()
        self.assertFalse(ov.win.visible)
        ov.show(img, "k")                      # 다시 보이기
        self.assertTrue(ov.win.visible)
        ov.hide(dismiss=True)                  # 닫기 → 같은 대상은 다시 안 뜬다
        self.assertEqual(ov.dismissed, "k")
        ov.show(img, "k")
        self.assertFalse(ov.win.visible)
        ov.show(img, "k2")                     # 새 챔피언이면 뜬다
        self.assertTrue(ov.win.visible)

    def test_toggle_collapsed_calls_back(self):
        ov, _ = self._overlay()
        seen = []
        ov.on_toggle = lambda c: seen.append(c)
        ov.set_collapsed(True)
        ov.set_collapsed(False)
        self.assertEqual(seen, [True, False])

    def test_dock_left_of_client(self):
        ov, _ = self._overlay()
        ov.dock_fn = lambda: (1000, 100, 900, 800)   # 클라 왼쪽 바깥에 자리가 있다
        img = L.render_collapsed(L.parse_payload(load_fixture("lolps_ahri_mid_data.json.gz")),
                                 fake_statics(), NoNetImages(), "아리")
        ov.show(img, "k")
        self.assertIn("+474+190", ov.win.geometry_value)     # 1000-520-6, 100+90
        ov2, _ = self._overlay()
        ov2.dock_fn = lambda: (200, 100, 900, 800)          # 화면 왼쪽이라 바깥에 자리 없음 → 안쪽
        ov2.show(img, "k2")
        self.assertIn("+210+", ov2.win.geometry_value)       # 200+10

    def test_tracker_sync_without_payload_hides(self):
        ov, _ = self._overlay()
        tr = L.BuildTracker()
        tr.overlay = ov
        tr.feed(0, "")
        tr.sync(None)                          # 대상 없음 → 아무 일도 없어야
        self.assertIsNone(ov.win)


class SquadAnalyzerWiringTest(unittest.TestCase):
    """분석기 본체에 실제로 연결돼 있는지(리베이스·리팩터 중 빠지면 잡는다)."""

    def setUp(self):
        with open(os.path.join(DESKTOP, "squad_analyzer.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_import_is_guarded(self):
        self.assertIn("import lolps_build", self.src)
        self.assertIn("lolps_build = None", self.src)

    def test_feed_called_from_champ_select(self):
        self.assertIn("lolps_build.feed(", self.src)
        self.assertIn("my_pick_from_session(", self.src)
        # 픽 스왑 감지를 위해 챔프선택 세션을 읽는 블록 안에서 불러야 한다
        i = self.src.index("lolps_build.feed(_lb_cid")
        window = self.src[i - 4000:i + 500]
        self.assertIn("/lol-champ-select/v1/session", window)

    def test_card_hidden_when_leaving_champ_select(self):
        # 닷지·게임 시작으로 밴픽 세션이 404 가 되면 ChampSelect 블록이 안 돌아 feed 가 안 불린다.
        #   그래서 페이즈 이탈 분기에서도 카드를 비운다(안 비우면 로비·인게임에 낡은 카드가 남는다).
        i = self.src.index('if current_phase == "ChampSelect":\n                if _cs_since[0] == 0.0')
        window = self.src[i:i + 700]
        self.assertIn("lolps_build.feed(0", window)

    def test_gui_tick_hooked(self):
        self.assertIn("def _lolps_build_sync(root)", self.src)
        self.assertIn("_lolps_build_sync(root)", self.src)
        self.assertIn("_lolps_dock_rect", self.src)
        self.assertIn("set_dock_provider", self.src)

    def test_spec_bundles_module(self):
        with open(os.path.join(DESKTOP, "squad_analyzer.spec"), encoding="utf-8") as fh:
            spec = fh.read()
        self.assertIn("lolps_build", spec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
