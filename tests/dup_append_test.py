#!/usr/bin/env python3
"""같은 판 통째 중복 기록 사후 정리 시험(가짜 시트). 사용: python3 tests/dup_append_test.py"""
import os, re, sys, time
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = open(os.path.join(ROOT, 'desktop', 'squad_analyzer.py'), encoding='utf-8').read()
a = SRC.index("def _dup_block_start(")
b = SRC.index("def _noban_sheet_push(")
ns = {"re": re, "time": time}
exec(SRC[a:b], ns)
cl = ns['_dup_cleanup_after_append']
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)

class Sheet:
    def __init__(self, rows): self.rows = [list(r) for r in rows]; self.fail_read = False; self.hook = None
    def col_values(self, c):
        if self.fail_read: raise RuntimeError("429")
        col = [r[c - 1] if len(r) >= c else "" for r in self.rows]
        while col and col[-1] == "": col.pop()
        return col
    def append_rows(self, rows):
        start = len(self.rows) + 1; self.rows += [list(r) for r in rows]
        return {"updates": {"updatedRange": f"Sheet1!A{start}:C{start + len(rows) - 1}"}}
    def delete_rows(self, s, e): del self.rows[s - 1:e]
NAMES = [f"p{i}" for i in range(10)]
def block(gid, names=NAMES): return [[gid, n, "x"] for n in names]
OTHER = [["#1", f"o{i}", "x"] for i in range(7)]
nolog = lambda *_: None
nosleep = lambda *_: None
def run(sh, gid, names, resp, **k): return cl(sh, 1, 2, gid, names, resp, sleep=nosleep, log=k.get('log', nolog))

# 1 정상: 한 블록만
sh = Sheet(OTHER); r = sh.append_rows(block("#9")); n0 = len(sh.rows)
check("정상 → none, 줄 보존", run(sh, "#9", NAMES, r) == 'none' and len(sh.rows) == n0)
# 2 동시 append: A 먼저, B 나중. 둘 다 정리 실행(순서 둘 다 시험)
for order in ("AB", "BA"):
    sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9"))
    res = {}
    for who in order: res[who] = run(sh, "#9", NAMES, ra if who == "A" else rb)
    gids = [r[0] for r in sh.rows]
    check(f"동시 정리 {order}: A none B deleted", res == {"A": "none", "B": "deleted"}, res)
    check(f"동시 정리 {order}: 정확히 10줄 남음·타판 보존", gids.count("#9") == 10 and gids.count("#1") == 7 and len(sh.rows) == 17)
# 3 읽기 실패 → 보존
sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9")); sh.fail_read = True
check("읽기 실패 → held·삭제 없음", run(sh, "#9", NAMES, rb) == 'held' and len(sh.rows) == 27)
# 4 응답 없음
sh = Sheet(OTHER + block("#9") + block("#9"))
check("append 응답 없음 → held", run(sh, "#9", NAMES, None) == 'held' and len(sh.rows) == 27)
# 5 행 밀림: 응답의 start 와 실제 위치 불일치
sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9")); del sh.rows[0:2]
check("행 밀림 → held·삭제 없음", run(sh, "#9", NAMES, rb) == 'held' and len(sh.rows) == 25)
# 6 시그니처 불일치(내 소환사명과 다름)
sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9"))
check("시그니처 다름 → 안 지움", run(sh, "#9", [f"z{i}" for i in range(10)], rb) == 'held' and len(sh.rows) == 27)
# 7 삭제 직전 행이 바뀜(그 사이 다른 인스턴스가 앞선 블록 삭제 등)
sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9"))
orig = sh.col_values; cnt = {"n": 0}
def cv(c):
    cnt["n"] += 1
    if cnt["n"] == 3: del sh.rows[7:17]   # 3번째 읽기(삭제 직전 재확인 시작) 전에 앞선 블록이 사라짐
    return orig(c)
sh.col_values = cv
res = run(sh, "#9", NAMES, rb)
check("직전 재확인에서 변동 → 삭제 안 함", res in ('held', 'none') and [r[0] for r in sh.rows].count("#9") >= 10, res)
# 8 앞선 블록이 불완전(5줄뿐)이면 안 지움
sh = Sheet(OTHER + block("#9")[:5]); rb = sh.append_rows(block("#9"))
check("앞선 사본이 불완전 → 안 지움", run(sh, "#9", NAMES, rb) != 'deleted' and len(sh.rows) == 22)
# 9 3중 동시: A,B,C — B,C 삭제, A 만 남음
sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9")); rc = sh.append_rows(block("#9"))
out = {"C": run(sh, "#9", NAMES, rc)}
out["A"] = run(sh, "#9", NAMES, ra)
check("3중: C 삭제·A 유지", out == {"C": "deleted", "A": "none"} and [r[0] for r in sh.rows].count("#9") == 20, out)
# 10 소비자 순서 무관: 소환사명 순서가 달라도(정렬 비교) 정리
sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9", NAMES[::-1]))
check("이름 순서만 다른 사본 → 정리", run(sh, "#9", NAMES[::-1], rb) == 'deleted' and len(sh.rows) == 17)
# 11 로그 남김
logs = []; sh = Sheet(OTHER); ra = sh.append_rows(block("#9")); rb = sh.append_rows(block("#9"))
run(sh, "#9", NAMES, rb, log=lambda m: logs.append(m))
check("삭제 로그에 게임ID·줄 수", any("[중복정리] ##9" in m and "10줄 삭제" in m for m in logs), logs)
print("\n실패 %d건" % len(FAILS)); sys.exit(1 if FAILS else 0)
