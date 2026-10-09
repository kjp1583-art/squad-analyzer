"""솔랭 LINK 사슬 단위 테스트 — squad_analyzer.py 는 Windows 전용 import 가 많아 _load_solo_ranks · _dep_link_groups · tnorm 만
   AST 로 떼어 가짜 시트(gspread 흉내)와 함께 실행한다. 가짜 닉네임·가짜 점수만 쓴다(외부 접속·실제 시트 없음).
   python desktop/solo_link_chain_test.py          (SA_SRC=<다른 squad_analyzer.py> 로 옛 소스에도 돌려 볼 수 있다)

   [2026-10-09 사장님 제보 "카무사리 웹에서 언랭으로 뜨는 이유"] LINK_ACCOUNT 사슬(A←B←C)을 한 그룹으로 합쳐
   현시즌 행이 옛 닉에 있어도 그룹 전원이 쓴다 — global_alt_map 삽입 순서에 기대지 않는다."""
import ast, csv, io, itertools, os, unittest

SRC = os.environ.get("SA_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py")
TEXT = open(SRC, encoding="utf-8").read()
TREE = ast.parse(TEXT)
FUNCS = {"_load_solo_ranks", "_dep_link_groups", "tnorm"}


MARK = "    # 🔗 [v82.50 사장님 제보"      # _load_solo_ranks 안의 '그룹 공유' 단계가 시작되는 주석


def load_ns(cut_share=False):
    """cut_share=True 면 그룹 공유 단계를 뺀 사본(블렌드·피크 채움까지만) — '사슬이 아닌 그룹은 그대로' 를 재는 기준."""
    lines = TEXT.splitlines(keepends=True)
    body = []
    for n in TREE.body:
        if not (isinstance(n, ast.FunctionDef) and n.name in FUNCS): continue
        if cut_share and n.name == "_load_solo_ranks":
            seg = "".join(lines[n.lineno - 1:n.end_lineno])
            seg = seg[:seg.index(MARK)] + "    return out\n"
            n = ast.parse(seg).body[0]
        body.append(n)
    assert {n.name for n in body} >= {"_load_solo_ranks", "tnorm"}, "함수를 못 찾음"
    ns = {"DOCUMENT_ID": "fake", "global_alt_map": {}, "global_spreadsheet": None, "_PEAK_SEASONS_CACHE": None}
    exec(compile(ast.Module(body=body, type_ignores=[]), SRC, "exec"), ns)
    return ns


class _WS:
    def __init__(self, rows): self.rows = rows
    def get_all_values(self): return [[str(c) for c in r] for r in self.rows]
class _SS:
    def __init__(self, rows): self.rows = rows
    def worksheet(self, name):
        assert name == "SOLO_RANK"
        return _WS(self.rows)


SOLO_HDR = ["닉네임", "티어", "LP", "솔랭승", "솔랭패", "점수"]
PEAK_HDR = ["닉네임", "차트닉", "최고티어", "최고시즌", "점수"]


def run_solo(ns, solo, peak, links):
    """solo: [(닉, 점수, 승, 패)] · peak: [(닉, 점수)] · links: [(본계, 부계)] 순서대로 global_alt_map 에 넣는다(분석기 부팅과 같은 방식)."""
    ns["global_spreadsheet"] = _SS([SOLO_HDR] + [[n, "MASTER I", 0, w, l, sc] for n, sc, w, l in solo])
    buf = io.StringIO(); wr = csv.writer(buf)
    wr.writerow(PEAK_HDR)
    for n, sc in peak: wr.writerow([n, n.split("#")[0], "master 1", "S14-2", sc])
    ns["_fetch_public_csv"] = lambda *a, **k: buf.getvalue()
    ns["_PEAK_SEASONS_CACHE"] = None
    ns["global_alt_map"] = {}
    for main, sub in links:
        ns["global_alt_map"][sub.strip().split("#")[0].lower()] = main.strip()
    return ns["_load_solo_ranks"]()


def old_groups_share(out, alt_map, tnorm):
    """수정 전 v82.50 공유 로직(쌍마다 그룹 · 삽입 순서 의존) — 사슬이 아닌 그룹에서 새 로직과 같아야 함을 보이는 기준."""
    out = {k: dict(v) for k, v in out.items()}
    groups = {}
    for _sub, _main in alt_map.items():
        g = groups.setdefault(tnorm(_main), {tnorm(_main)}); g.add(tnorm(_sub))
    for _mk, keys in groups.items():
        cands = [out[k] for k in keys if k in out]
        if not cands: continue
        best = max(cands, key=lambda d: ((d.get("wins", 0) + d.get("losses", 0)) > 0, d.get("score") or -1e9))
        for k in keys:
            if out.get(k) is not best: out[k] = dict(best)
    return out


# 제보된 구조의 합성판: 행 A(계정 이전) → 행 B(닉변) 사슬 · 마스터 행은 맨 옛 닉에만
CHAIN_LINKS = [("체인중#Mid", "체인옛#Old"), ("체인현#Now", "체인중#Mid")]
CHAIN_SOLO = [("체인옛#Old", 3400, 90, 60)]
CHAIN_PEAK = [("체인현#Now", 2900), ("체인중#Mid", 2900), ("체인옛#Old", 3100)]


class T(unittest.TestCase):
    def test_chain_reaches_the_row_on_the_oldest_name(self):
        ns = load_ns()
        out = run_solo(ns, CHAIN_SOLO, CHAIN_PEAK, CHAIN_LINKS)
        for nm in ("체인현", "체인중", "체인옛"):
            self.assertEqual(out[nm]["wins"] + out[nm]["losses"], 150, nm)
            self.assertAlmostEqual(out[nm]["score"], 3250.0, msg=nm)         # (3400 + 옛 닉 피크 3100) / 2
            self.assertEqual(out[nm]["cur"], 3400, nm)

    def test_result_does_not_depend_on_link_row_order(self):
        ref = None
        for perm in itertools.permutations(CHAIN_LINKS):
            out = run_solo(load_ns(), CHAIN_SOLO, CHAIN_PEAK, list(perm))
            snap = {k: (round(v["score"], 6), v["wins"], v["losses"], v.get("cur")) for k, v in out.items()}
            ref = ref or snap
            self.assertEqual(snap, ref, "LINK 행 순서를 바꿨더니 결과가 달라졌다: %s" % (perm,))
        self.assertEqual(ref["체인현"][1] + ref["체인현"][2], 150)

    def test_three_deep_chain_in_every_order(self):
        links = [("가#K", "나#K"), ("나#K", "다#K"), ("다#K", "라#K")]      # 4단 사슬: 가←나←다←라
        for perm in itertools.permutations(links):
            out = run_solo(load_ns(), [("라#K", 2000, 30, 20)], [("가#K", 2500)], list(perm))
            for nm in ("가", "나", "다", "라"):
                self.assertEqual(out[nm]["wins"], 30, "%s %s" % (perm, nm))

    def test_non_chain_groups_same_as_before(self):
        # 사슬이 아닌 그룹(본계에 행 · 부계에 행 · 둘 다 행 · 행 없음)은 수정 전 공유 로직과 결과가 같다
        links = [("본갑#A", "부갑#A"), ("본을#B", "부을#B"), ("본병#C", "부병#C"), ("본정#D", "부정#D")]
        solo = [("본갑#A", 2500, 40, 30), ("부을#B", 2100, 20, 10), ("본병#C", 1800, 10, 10), ("부병#C", 2600, 50, 50)]
        peak = [("본갑#A", 2700), ("본을#B", 2400), ("본정#D", 2900)]
        new = run_solo(load_ns(), solo, peak, links)
        ns = load_ns(cut_share=True)
        pre = run_solo(ns, solo, peak, links)                       # 블렌드까지만
        alt_map = {sub.split("#")[0].lower(): main for main, sub in links}
        expect = old_groups_share(pre, alt_map, ns["tnorm"])
        self.assertEqual(set(new), set(expect))
        rnd = lambda d: {a: (round(b, 6) if isinstance(b, float) else b) for a, b in d.items()}
        for k in new: self.assertEqual(rnd(new[k]), rnd(expect[k]), k)

    def test_member_without_any_entry_is_not_invented(self):
        out = run_solo(load_ns(), [("가#K", 2000, 30, 20)], [], [("가#K", "나#K"), ("다#K", "라#K")])
        self.assertIn("나", out)                    # 같은 그룹의 부계는 본계 기록을 쓴다
        self.assertNotIn("다", out)                  # 엔트리가 하나도 없는 그룹은 만들어 내지 않는다
        self.assertNotIn("라", out)

    def test_group_without_current_season_shares_best_peak(self):
        # 현시즌 전적이 없는 그룹: 점수 최고 피크를 그룹 전원이 쓴다(분석기 v82.50 그대로 — 웹·툴링도 같은 규칙)
        # (SOLO_RANK 에 유효 행이 하나도 없으면 분석기는 통째로 {} 를 돌려주므로 — 이 그룹과 무관한 행 하나를 둔다)
        out = run_solo(load_ns(), [("무관#K", 2000, 5, 5)], [("본#K", 2600), ("부#K", 3000)], [("본#K", "부#K")])
        self.assertEqual(out["본"]["score"], 3000); self.assertEqual(out["부"]["score"], 3000)
        self.assertEqual(out["본"]["wins"] + out["본"]["losses"], 0)

    def test_current_season_beats_higher_peak_only_entry(self):
        out = run_solo(load_ns(), [("부#K", 1800, 20, 20)], [("본#K", 3200)], [("본#K", "부#K")])
        self.assertEqual(out["본"]["wins"], 20)      # 피크만 높은 엔트리보다 현시즌 전적이 있는 쪽이 우선
        self.assertEqual(out["본"]["cur"], 1800)

    def test_tie_is_deterministic(self):
        outs = []
        for perm in itertools.permutations([("가#K", "나#K"), ("가#K", "다#K"), ("가#K", "라#K")]):
            out = run_solo(load_ns(), [("나#K", 2000, 10, 10), ("다#K", 2000, 11, 9), ("라#K", 2000, 12, 8)], [], list(perm))
            outs.append(out["가"]["wins"])
        self.assertEqual(len(set(outs)), 1, outs)    # 동점이면 닉 순서(나 < 다 < 라) — 집합 순회 순서에 기대지 않는다
        self.assertEqual(outs[0], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
