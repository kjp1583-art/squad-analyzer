#!/usr/bin/env python3
"""🔒 쓰기 전 선점(claim) 시험(가짜 시트) — 동시 기록에서 승자가 정확히 한 명인지, 승자가 죽으면 다른 분석기가 이어받는지, 읽기 실패 때 안전한지.
사용: python3 tests/game_claim_test.py"""
import os, re, sys, time, random, threading
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = open(os.path.join(ROOT, 'desktop', 'squad_analyzer.py'), encoding='utf-8').read()
a = SRC.index('CLAIM_TAB = "GAME_CLAIM"'); b = SRC.index("def _noban_sheet_push(")
ns = {"time": time, "os": os}; exec(SRC[a:b], ns)
claim = ns['_claim_game']; TTL = ns['CLAIM_TTL']
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)
class WS:
    def __init__(self): self.rows = [["키", "누가", "시각"]]; self.lock = threading.Lock(); self.fail_read = 0; self.fail_write = 0
    def get_all_values(self):
        with self.lock:
            if self.fail_read > 0: self.fail_read -= 1; raise RuntimeError("429")
            return [list(r) for r in self.rows]
    def append_rows(self, rows, value_input_option=None):
        with self.lock:
            if self.fail_write > 0: self.fail_write -= 1; raise RuntimeError("429")
            self.rows += [list(r) for r in rows]
G = "#8449047460"; T = "CLASSIC_NORMAL"
# 1 혼자면 선점
ws = WS(); r = claim(None, T, G, "A:1", now=1000, ws=ws)
check("혼자 → 선점", r[0] is True and len(ws.rows) == 2, r)
check("내 선점으로 다시 들어오면(재시작·다음 루프) 그대로 True", claim(None, T, G, "A:1", now=1010, ws=ws)[0] is True and len(ws.rows) == 2)
check("남이 선점한 뒤에 오면 False(TTL 안)", claim(None, T, G, "B:2", now=1020, ws=ws)[0] is False and len(ws.rows) == 2)
# 2 진짜 동시: 둘 다 읽기 전에 붙인다(경합) — 첫 줄 하나만 승자
class RaceWS(WS):
    """두 분석기가 모두 '아직 없음'을 본 뒤 각자 붙이는 최악의 순서를 흉내낸다: get_all_values 가 처음 두 번은 빈 표를 돌려준다."""
    def __init__(self): super().__init__(); self.loc = threading.local()
    def get_all_values(self):
        with self.lock:
            if not getattr(self.loc, "seen", False): self.loc.seen = True; return [["키", "누가", "시각"]]      # 호출한 쪽마다 첫 읽기는 빈 표(둘 다 '아직 없음'을 봄)
            return [list(r) for r in self.rows]
for order in ("AB", "BA"):
    ws = RaceWS(); res = {}
    def run(w):
        res[w] = claim(None, T, G, f"{w}:1", now=1000, ws=ws)
    seq = [threading.Thread(target=run, args=(w,)) for w in order]
    # 첫 읽기를 둘 다 하게 하려고 순서대로 시작
    for t in seq: t.start()
    for t in seq: t.join()
    winners = [w for w, v in res.items() if v[0] is True]
    check(f"동시 경합({order}): 승자는 정확히 한 명", len(winners) == 1, res)
# 3 많은 분석기가 동시에(스레드 12개) — 승자 1명
ws = WS(); res = {}
def run2(i): time.sleep(random.random() * 0.01); res[i] = claim(None, T, G, f"P{i}:1", now=1000, ws=ws)
ts = [threading.Thread(target=run2, args=(i,)) for i in range(12)]
[t.start() for t in ts]; [t.join() for t in ts]
check("12대 동시 → 승자 1명", sum(1 for v in res.values() if v[0] is True) == 1, {k: v[0] for k, v in res.items()})
# 4 승자가 TTL 안에 못 썼다 → 다음 순번 키로 다른 분석기가 이어받는다
ws = WS(); claim(None, T, G, "A:1", now=1000, ws=ws)
r = claim(None, T, G, "B:2", now=1000 + TTL + 5, ws=ws)
check("TTL 지나면 B 가 다음 순번 선점", r[0] is True and any(x[0].endswith("|1") for x in ws.rows), r)
check("이어받은 뒤 A 가 돌아와도(옛 선점) 승자가 아니다", claim(None, T, G, "A:1", now=1000 + TTL + 6, ws=ws)[0] is False)
ws2 = WS(); claim(None, T, G, "A:1", now=1000, ws=ws2)
check("아무도 이어받지 않았으면 만료된 내 선점으로 계속 쓸 수 있다", claim(None, T, G, "A:1", now=1000 + TTL + 6, ws=ws2)[0] is True and len(ws2.rows) == 2)
# 5 판마다·탭마다 따로
ws = WS(); claim(None, T, G, "A:1", now=1000, ws=ws)
check("다른 판은 따로", claim(None, T, "#999", "B:2", now=1001, ws=ws)[0] is True)
check("다른 탭(칼바람)은 따로", claim(None, "KIWI_KIWI", G, "B:2", now=1002, ws=ws)[0] is True)
# 6 시트 오류 → None (호출부가 보류)
ws = WS(); ws.fail_read = 1
check("읽기 실패 → None", claim(None, T, G, "A:1", now=1000, ws=ws)[0] is None)
ws = WS(); ws.fail_write = 1
check("쓰기 실패 → None(선점 줄이 안 남았다)", claim(None, T, G, "A:1", now=1000, ws=ws)[0] is None and len(ws.rows) == 1)
ws = WS(); r1 = claim(None, T, G, "A:1", now=1000, ws=ws); ws.fail_read = 1
check("이미 선점한 뒤 읽기 실패해도 줄은 그대로(중복 선점 없음)", claim(None, T, G, "A:1", now=1005, ws=ws)[0] is None and len(ws.rows) == 2)
# 7 소스 연결: 실시간·백필 모두 쓰기 전에 선점
live = SRC[SRC.index("_claim_game(global_spreadsheet, str(getattr(sheet_target"):]
check("실시간 경로: 선점 실패 시 이번 기록 건너뜀(_dedup_ok=False)", "_dedup_ok = False" in live[:900])
bf = SRC[SRC.index("def _lcu_backfill_once("):SRC.index("def _lcu_backfill_loop(")]
check("백필 경로: append 전에 선점, 못 하면 continue", bf.index("_claim_game(") < bf.index("ws.append_rows(rows)") and "continue" in bf[bf.index("_claim_game("):bf.index("ws.append_rows(rows)")])
print()
print("실패 %d건" % len(FAILS)); sys.exit(1 if FAILS else 0)
