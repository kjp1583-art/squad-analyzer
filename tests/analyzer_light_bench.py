# -*- coding: utf-8 -*-
"""분석기 경량화 실측 벤치 — 합성 협곡 27,376행(실측 규모)로 '전/후'를 같은 조건에서 잰다.

    python3 tests/analyzer_light_bench.py            # 현재 코드(경량화 ON)
    python3 tests/analyzer_light_bench.py --legacy   # 경량화 OFF(수정 전 동작 재현)

재는 것
  ① 시트 캐시 메모리: 6탭(협곡 27,376 + 나머지 5×8,000행) 적재 후
     - 캐시가 들고 있는 행 객체의 deep size(공유 문자열은 1회만 계산)
     - 프로세스 RSS 증가분
     - 남아 있는 총 행수(예산 정리 동작)
  ② 클랜 인덱스 빌드: _clan_index(force=True) 소요 시간과 RSS 증가분(2회차=워밍 후)
  ③ 날짜 파싱: _sheet_date 27,376회(최근성 가중이 행마다 날짜를 읽는 경로)

⛔ 이 파일은 테스트가 아니다(CI 수집 대상 이름 `*_test.py` 아님) — 실측 로그용.
"""
import gc
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _analyzer_headless import load_analyzer, synthetic_rows  # noqa: E402

LEGACY = "--legacy" in sys.argv


def peak_rss_mb():
    """프로세스 최대 RSS(MB) = Linux VmHWM / Windows PeakWorkingSetSize. RSS 순간값은 할당자·GC 때문에
       흔들려서 '이 작업을 하며 실제로 찍힌 최고치'를 본다(전/후 프로세스를 따로 띄워 비교)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        c = _PMC()
        c.cb = ctypes.sizeof(_PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                 ctypes.byref(c), c.cb)
        return int(c.PeakWorkingSetSize) / 1048576.0
    except Exception:
        return 0.0


def rss_kb():
    """현재 프로세스 RSS(KB). Linux=/proc, Windows=psapi(있으면). 실패 시 0."""
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * (os.sysconf("SC_PAGE_SIZE") // 1024)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        c = _PMC()
        c.cb = ctypes.sizeof(_PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                 ctypes.byref(c), c.cb)
        return int(c.WorkingSetSize) // 1024
    except Exception:
        return 0


def deep_size(obj, seen=None, _depth=0):
    """객체가 실제로 붙잡고 있는 바이트(문자열 공유는 id 로 1회만)."""
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    size = sys.getsizeof(obj)
    if isinstance(obj, (str, bytes, bytearray, int, float, bool, type(None))):
        return size
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += deep_size(k, seen, _depth + 1) + deep_size(v, seen, _depth + 1)
        return size
    if isinstance(obj, (list, tuple, set, frozenset)):
        for it in obj:
            size += deep_size(it, seen, _depth + 1)
        return size
    return size


class _FakeSheet:
    _next = [1000]

    def __init__(self, title, rows):
        self.title = title
        self.rows = rows
        self.id = _FakeSheet._next[0]
        _FakeSheet._next[0] += 1


class _FakeBook:
    def __init__(self, tabs):
        self.tabs = tabs

    def worksheet(self, name):
        if name not in self.tabs:
            raise KeyError(name)
        return self.tabs[name]


def bench_cache(S):
    """① 시트 캐시 — (a) 협곡 1탭만 적재한 뒤의 크기(경량화 효과만 본다) (b) 6탭 적재 후 총 보유량."""
    cn_rows = synthetic_rows(27376)
    others = {}
    for i, extra in enumerate(["KIWI_KIWI", "SOLO_RANK", "MITO_GAMES", "STAT_CHAMP", "LINK_ACCOUNT"]):
        others[extra] = synthetic_rows(8000 + i * 100, seed=100 + i)
    S.global_sheet_cache.clear()
    S.global_cache_time.clear()
    if hasattr(S, "_SHEET_CACHE_LAST"):
        S._SHEET_CACHE_LAST.clear()
    if hasattr(S, "_SHEET_CACHE_HITS"):
        S._SHEET_CACHE_HITS.clear()

    orig_gviz, orig_svc = S._gviz_rows_by_gid, S._svc_get_all_values
    S._gviz_rows_by_gid = lambda gid, timeout=8: None
    cur = {"rows": cn_rows}
    S._svc_get_all_values = lambda sheet_obj, retries=3: cur["rows"]
    try:
        # (a) 협곡 1탭 — 예산/유휴 정리를 끄고 '경량화만' 잰다
        keep_budget, keep_idle = S.SHEET_CACHE_BUDGET_ROWS, S.SHEET_CACHE_IDLE_SEC
        S.SHEET_CACHE_BUDGET_ROWS, S.SHEET_CACHE_IDLE_SEC = 0, 0
        t0 = time.perf_counter()
        S.get_sheet_data_cached(_FakeSheet("CLASSIC_NORMAL", cn_rows), force=True)
        one_s = time.perf_counter() - t0
        one_mb = deep_size(S.global_sheet_cache) / 1048576
        S.global_sheet_cache.clear(); S.global_cache_time.clear()
        S._SHEET_CACHE_LAST.clear(); S._SHEET_CACHE_HITS.clear()
        S.SHEET_CACHE_BUDGET_ROWS, S.SHEET_CACHE_IDLE_SEC = keep_budget, keep_idle

        # (b) 6탭 — 실제 설정(예산·유휴 정리 포함)
        t0 = time.perf_counter()
        S.get_sheet_data_cached(_FakeSheet("CLASSIC_NORMAL", cn_rows), force=True)
        for t in others:
            cur["rows"] = others[t]
            S.get_sheet_data_cached(_FakeSheet(t, others[t]), force=True)
            S.get_sheet_data_cached(_FakeSheet(t, others[t]))     # 한 번 더 읽기(현실: 여러 기능이 같은 탭 재사용)
        load_s = time.perf_counter() - t0
        held = sum(len(v) for v in S.global_sheet_cache.values())
        kept = sorted(S.global_sheet_cache)
        size = deep_size(S.global_sheet_cache)
        del cn_rows, others
        gc.collect()
        return dict(one_s=one_s, one_mb=one_mb, load_s=load_s, rows=held,
                    size_mb=size / 1048576, kept=kept)
    finally:
        S._gviz_rows_by_gid, S._svc_get_all_values = orig_gviz, orig_svc


def bench_index(S, rows):
    """② 클랜 인덱스 빌드 — 실제 함수 그대로(시트 fetch 만 합성으로 대체)."""
    book = _FakeBook({"CLASSIC_NORMAL": _FakeSheet("CLASSIC_NORMAL", rows)})
    orig_book, orig_get = S.global_spreadsheet, S.get_sheet_data_cached
    S.global_spreadsheet = book
    S.get_sheet_data_cached = lambda sheet_obj, force=False, prefer_service=False: rows
    try:
        S._CLAN_IDX["ts"] = 0.0
        t0 = time.perf_counter()
        idx = S._clan_index(force=True)
        first = time.perf_counter() - t0
        S._CLAN_IDX["ts"] = 0.0
        t0 = time.perf_counter()
        idx = S._clan_index(force=True)
        second = time.perf_counter() - t0
        gc.collect()
        return dict(first_s=first, warm_s=second, people=len(idx.get("by_pu") or {}),
                    h2h=len(idx.get("h2h") or {}), mu2=len(idx.get("mu2") or {}),
                    idx_mb=deep_size(idx) / 1048576)
    finally:
        S.global_spreadsheet, S.get_sheet_data_cached = orig_book, orig_get


def bench_pool(S, rows):
    """④ 인물별 밴픽 스캔(_pool_rows ×10) — 사람마다 27,000행을 다시 훑는지."""
    book = _FakeBook({"CLASSIC_NORMAL": _FakeSheet("CLASSIC_NORMAL", rows)})
    orig_book, orig_get = S.global_spreadsheet, S.get_sheet_data_cached
    S.global_spreadsheet = book
    S.get_sheet_data_cached = lambda sheet_obj, force=False, prefer_service=False: rows
    pus = [f"pu-{i:04d}-{'ab' * 18}" for i in range(1, 11)]

    def run(fast):
        S._POOLROWS_CACHE["ts"].clear(); S._POOLROWS_CACHE["data"].clear()
        if hasattr(S, "_BU_PU_CACHE"):
            S._BU_PU_CACHE.clear()
        orig_by = getattr(S, "_rows_by_puuid", None)
        if not fast and orig_by is not None:
            S._rows_by_puuid = lambda *a, **k: None      # 수정 전 동작(전체 행 스캔) 재현
        try:
            t0 = time.perf_counter()
            got = [S._pool_rows(pu) for pu in pus]
            return time.perf_counter() - t0, got
        finally:
            if orig_by is not None:
                S._rows_by_puuid = orig_by

    try:
        t_slow, a = run(False)
        t_fast, b = run(True)
        same = [sorted((x["champ"], x["g"], x["w"]) for x in one) for one in a] == \
               [sorted((x["champ"], x["g"], x["w"]) for x in one) for one in b]
        return dict(slow_s=t_slow, fast_s=t_fast, same=same, people=len(pus))
    finally:
        S.global_spreadsheet, S.get_sheet_data_cached = orig_book, orig_get


def bench_dates(S, rows):
    """③ 날짜 파싱 — 최근성 가중이 행마다 부르는 경로."""
    dates = [r[11] for r in rows[1:]]
    t0 = time.perf_counter()
    n = 0
    for d in dates:
        if S._sheet_date(d) is not None:
            n += 1
    return dict(calls=len(dates), ok=n, ms=(time.perf_counter() - t0) * 1000)


def main():
    S = load_analyzer()
    if LEGACY:
        S.SHEET_CACHE_SLIM = False
        S.SHEET_CACHE_BUDGET_ROWS = 0        # 무제한 = 수정 전 동작
        S.SHEET_CACHE_IDLE_SEC = 0
    mode = "LEGACY(수정 전)" if LEGACY else "SLIM(수정 후)"
    rows = synthetic_rows(27376)
    print(f"\n=== analyzer light bench · {mode} ===")
    print(f"합성 행수: {len(rows) - 1:,} (헤더 포함) · 모듈: {S.CURRENT_VERSION}")

    a = bench_cache(S)
    print("\n① 시트 캐시")
    print(f"   협곡 1탭(27,376행) 적재 : {a['one_s']:.2f}s · 캐시 deep size {a['one_mb']:.1f} MB")
    print(f"   6탭 적재               : {a['load_s']:.2f}s")
    print(f"   보관 행수               : {a['rows']:,}행  (탭: {', '.join(a['kept'])})")
    print(f"   캐시 deep size          : {a['size_mb']:.1f} MB")

    b = bench_index(S, rows)
    print("\n② 클랜 인덱스 빌드 (_clan_index)")
    print(f"   첫 빌드       : {b['first_s'] * 1000:.0f} ms")
    print(f"   워밍 빌드     : {b['warm_s'] * 1000:.0f} ms")
    print(f"   사람/맞대결/매치업: {b['people']} / {b['h2h']:,} / {b['mu2']:,}")
    print(f"   인덱스 크기   : {b['idx_mb']:.1f} MB")

    d = bench_dates(S, rows)
    print("\n③ 날짜 파싱 (행 수만큼)")
    print(f"   {d['calls']:,}회 · 성공 {d['ok']:,} · {d['ms']:.0f} ms")

    e = bench_pool(S, rows)
    print(f"\n④ 인물별 밴픽 스캔 (_pool_rows ×{e['people']}명)")
    print(f"   수정 전 : {e['slow_s'] * 1000:.0f} ms  (사람마다 27,000행 재스캔)")
    print(f"   수정 후 : {e['fast_s'] * 1000:.0f} ms  · 결과 동일: {e['same']}")
    print(f"\n프로세스 최대 RSS(이 벤치 전체) : {peak_rss_mb():.1f} MB")
    print()


if __name__ == "__main__":
    main()
