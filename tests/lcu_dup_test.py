#!/usr/bin/env python3
"""lcu백필 경로의 같은 판 통째 중복 차단 시험(가짜 시트·가짜 LCU). 사용: python3 tests/lcu_dup_test.py
분석기는 윈도우 전용 모듈(winreg 등)을 불러와 리눅스에서 import 가 안 되므로 dup_append_test.py 처럼 소스에서 해당 블록만
잘라 실행한다. 실제 시트·LCU·디스코드에는 접속하지 않는다.

  A. _lcu_append_block 단위 — 확인 → 한 번 더 확인 → append → 응답 보존 → 사후 정리
  B. _lcu_backfill_once 통합 — 가짜 LCU 전적 + 가짜 시트로 한 회차를 통째로 돌려 연결(NameError·상태값 처리)까지 확인
  C. 실제 스레드 경합 — 여러 PC 가 같은 순간에 같은 판을 회수하는 상황(두 PC 는 한 블록만 남고, 몇 PC 든 앞선 블록은 보존)
핵심 규칙: 지우는 건 '내 블록뿐'이고, 그것도 같은 게임ID 의 완전한 블록이 내 앞에 이미 있을 때만. 확신이 없으면 지우지 않는다."""
import contextlib, io, os, random, re, sys, threading, time, types
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = open(os.path.join(ROOT, 'desktop', 'squad_analyzer.py'), encoding='utf-8').read()
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)

# ───────── 소스 조각 (모듈 전체는 import 불가) ─────────
CL_A, CL_B = SRC.index("def _dup_block_start("), SRC.index("def _noban_sheet_push(")          # 사후 정리 함수들
HP_A, HP_B = SRC.index("_LCU_BF_LOCK = threading.Lock()"), SRC.index("def _lcu_backfill_once(")  # 락 + 도우미
RUN_A, RUN_B = SRC.index("_LCU_BF_DONE = set()"), SRC.index("def _lcu_backfill_loop(")            # 락·도우미·회차 전부
TN = re.search(r"^def tnorm\(.*?(?=^\S)", SRC, re.S | re.M).group(0)

ns = {"re": re, "time": time, "random": random, "threading": threading}
exec(SRC[CL_A:CL_B], ns); exec(SRC[HP_A:HP_B], ns)
append_block, cleanup = ns['_lcu_append_block'], ns['_dup_cleanup_after_append']

# ───────── 가짜 시트 (구글 시트 의미: 1행 = 헤더, append 는 끝에 붙이고 updatedRange 로 시작 행을 알려 줌) ─────────
class Sheet:
    def __init__(self, rows, title="CLASSIC_NORMAL"):
        self.title = title; self.rows = [list(r) for r in rows]
        self.appends = 0; self.deletes = []; self.gid_reads = 0
        self.fail_reads = False; self.fail_append = None; self.no_resp = False
        self.before_append = None     # 내 append 가 실행되기 직전(확인은 이미 통과)에 상대 기록자가 먼저 쓴다
        self.post_append = None       # 내 append 직후, 사후 정리의 첫 읽기 직전에 일어나는 일
        self.after_gid_reads = None   # (n, fn): 게임ID 열을 n번째 읽은 직후 fn(self) — 확인과 확인 사이에 상대가 쓴다
        self.stale = None; self.stale_left = 0   # 앞으로 n번의 읽기는 옛 사본(= 상대가 쓰기 전)을 돌려준다
        self._post = None
    def row_values(self, i): return list(self.rows[i - 1]) if 0 < i <= len(self.rows) else []
    def col_values(self, c):
        if self._post:
            fn, self._post = self._post, None; fn(self)
        if self.fail_reads: raise RuntimeError("429 quota")
        src = self.rows
        if self.stale_left > 0: self.stale_left -= 1; src = self.stale
        col = [r[c - 1] if len(r) >= c else "" for r in src]
        while col and col[-1] == "": col.pop()
        if c == 1:
            self.gid_reads += 1
            if self.after_gid_reads and self.gid_reads == self.after_gid_reads[0]: self.after_gid_reads[1](self)
        return col
    def append_rows(self, rows, **kw):
        if self.fail_append: raise self.fail_append
        if self.before_append:
            fn, self.before_append = self.before_append, None; fn(self)
        start = len(self.rows) + 1
        self.rows += [list(r) for r in rows]; self.appends += 1
        self._post, self.post_append = self.post_append, None
        if self.no_resp: return None
        return {"updates": {"updatedRange": f"{self.title}!A{start}:S{start + len(rows) - 1}"}}
    def delete_rows(self, s, e):
        self.deletes.append((s, e)); del self.rows[s - 1:e]

HDR = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "매치평가", "패치버전", "KDA", "점수", "딜량", "아이템", "주룬", "보조룬", "스펠", "지표"]
KIWI_HDR = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "매치평가", "KDA", "패치버전", "점수", "딜량", "아이템", "주룬", "보조룬", "스펠", "지표"]
NAMES = [f"p{i}#KR1" for i in range(10)]
NATURAL = list(range(10)); RFIRST = [5, 0, 1, 2, 3, 4, 6, 7, 8, 9]   # 레드 한 명이 맨 앞 → 블루 5 → 레드 4 (이번 사고 블록의 모양)
LCU_M, RT_M = "g100|cs10|m25.0|kp50|vs20|cw1|wp5|wk2|dt300", "g100|cs10|m25.0|kp50|vs20|cw1|wp5|wk2|op3|tk4|dt300"
def mkrow(gid, name, team, ban, metric):
    return [gid, "2026-10-07 22:46", name, "pu-" + name, team, "탑", "아리", ban, "승리", "평가 없음", "v16.19", "1/2/3", "", "100",
            "1055", "8005|8000", "8200", "SummonerFlash|SummonerTeleport", metric]
def block(gid, kind="lcu", order=NATURAL, names=NAMES):
    """kind 'lcu' = 밴 공란·지표에 op/tk 없음(lcu백필 모양), 'rt' = 밴 채움·op/tk 있음(실시간 기록 모양)."""
    return [mkrow(gid, names[i], "블루팀" if i < 5 else "레드팀", "" if kind == "lcu" else "밴 안함", LCU_M if kind == "lcu" else RT_M) for i in order]
OTHER = [mkrow("#1", f"o{i}#KR1", "블루팀", "밴 안함", RT_M) for i in range(7)]
def mk(extra=(), title="CLASSIC_NORMAL"): return Sheet([HDR] + OTHER + list(extra), title)
nolog = lambda *_: None
nosleep = lambda *_: None
def call(sh, gid, rows, hd=HDR, sleep=nosleep):
    logs = []
    r = append_block(sh, hd, gid, rows, sleep=sleep, log=logs.append)
    return r, logs
def gcount(sh, gid): return sum(1 for r in sh.rows if r and r[0] == gid)
def resp_for(sh, start, n): return {"updates": {"updatedRange": f"{sh.title}!A{start}:S{start + n - 1}"}}

# ═══════════════ A. _lcu_append_block 단위 ═══════════════
# (가) 정상 — 중복 없음 → 아무것도 안 지움
sh = mk(); n0 = len(sh.rows); mine = block("#9")
r, logs = call(sh, "9", mine)
check("(가) 정상 → appended·10줄 추가·삭제 0·타판 보존",
      r == 'appended' and len(sh.rows) == n0 + 10 and sh.deletes == [] and sh.appends == 1
      and sh.rows[n0:] == mine and sh.rows[1:8] == OTHER, (r, logs))
# 이미 시트에 있음 → 안 씀(확인 1회로 끝 — 대기 없음)
slept = []
sh = mk(extra=block("#9", "rt", RFIRST)); n0 = len(sh.rows)
r, logs = call(sh, "9", block("#9"), sleep=lambda s: slept.append(s))
check("이미 있음 → exists·append 0회·대기 없음", r == 'exists' and sh.appends == 0 and len(sh.rows) == n0 and slept == [], (r, slept))
# 확인과 확인 사이(대기 중)에 다른 기록자가 먼저 씀 → 두 번째 확인이 잡는다
sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
r, logs = call(sh, "9", block("#9"), sleep=lambda s: sh.rows.extend([list(x) for x in rival]))
check("대기 중 선기록 → exists·내 append 0회·상대 10줄만",
      r == 'exists' and sh.appends == 0 and len(sh.rows) == n0 + 10 and sh.rows[n0:] == rival and any("먼저 기록" in m for m in logs), (r, logs))

# (나) 실시간 블록이 먼저 있고 lcu 블록이 뒤에 붙음(순서가 달라도 이름 집합 동일) → lcu 블록만 삭제
sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])      # 둘 다 '없음'을 본 뒤 상대가 먼저 착륙
r, logs = call(sh, "9", block("#9", "lcu", NATURAL))
check("(나) 실시간 먼저·lcu 뒤 → deduped·lcu 블록만 삭제(행 %d~%d)" % (n0 + 11, n0 + 20),
      r == 'deduped' and sh.deletes == [(n0 + 11, n0 + 20)] and len(sh.rows) == n0 + 10 and sh.rows[n0:] == rival, (r, sh.deletes, logs))
check("(나) 타판·헤더 보존", sh.rows[0] == HDR and sh.rows[1:8] == OTHER)
check("(나) 삭제 로그에 게임ID·줄 수", any("[중복정리] ##9" in m and "10줄 삭제" in m for m in logs), logs)

# (다) lcu 블록이 먼저이고 실시간 블록이 뒤 → lcu 블록 보존(삭제 안 함), 이어지는 실시간 쪽 정리가 실시간 사본을 지운다
sh = mk(); n0 = len(sh.rows); mine = block("#9", "lcu", NATURAL); rt = block("#9", "rt", RFIRST)
sh.post_append = lambda s: s.rows.extend([list(x) for x in rt])           # 내 append 직후 상대가 뒤에 붙음
r, logs = call(sh, "9", mine)
check("(다) lcu 먼저·실시간 뒤 → appended·삭제 0(가장 앞선 블록은 안 지움)",
      r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20 and sh.rows[n0:n0 + 10] == mine, (r, sh.deletes, logs))
rt_names = [x[2] for x in rt]
res_rt = cleanup(sh, 1, 3, "#9", rt_names, resp_for(sh, n0 + 11, 10), sleep=nosleep, log=nolog)   # 실시간 쪽 사후 정리(기존 함수)
check("(다) 이어서 실시간 쪽 정리 → 실시간 사본 삭제·lcu 블록만 남음(양쪽 삭제 불가)",
      res_rt == 'deleted' and len(sh.rows) == n0 + 10 and sh.rows[n0:] == mine, res_rt)

# (라) 두 PC 의 lcu 블록이 연달아 → 뒤쪽만 삭제
sh = mk(); n0 = len(sh.rows); b1 = block("#9", "lcu", NATURAL); b2 = block("#9", "lcu", RFIRST)
sh.stale = [list(x) for x in sh.rows]
r1, _ = call(sh, "9", b1)
sh.stale_left = 2                                                          # PC2 는 확인 두 번 다 PC1 이 쓰기 전 사본을 봤다
r2, logs2 = call(sh, "9", b2)
check("(라) 두 PC lcu 연달아 → 먼저 쓴 쪽 appended·뒤쪽 deduped",
      r1 == 'appended' and r2 == 'deduped' and len(sh.rows) == n0 + 10 and sh.rows[n0:] == b1 and sh.deletes == [(n0 + 11, n0 + 20)], (r1, r2, sh.deletes))
# 같은 두 PC 지만 PC1 의 정리 읽기가 PC2 의 append 뒤에 일어남 → PC1 은 가장 앞이라 그대로
sh = mk(); n0 = len(sh.rows)
sh.post_append = lambda s: s.rows.extend([list(x) for x in b2])
r1, _ = call(sh, "9", b1)
check("(라) PC1 정리 시점에 PC2 가 이미 뒤에 있어도 PC1 은 유지", r1 == 'appended' and sh.deletes == [] and sh.rows[n0:n0 + 10] == b1 and len(sh.rows) == n0 + 20, (r1, sh.deletes))
# 3중 동시(셋 다 쓴 뒤 정리) — 최악이어도 가장 앞선 블록·타판은 반드시 보존(남는 중복은 알려진 한계)
sh = mk(); n0 = len(sh.rows); bs = [block("#9", "lcu", o) for o in (NATURAL, RFIRST, NATURAL)]
rs = [sh.append_rows(b) for b in bs]
o2 = cleanup(sh, 1, 3, "#9", [x[2] for x in bs[1]], rs[1], sleep=nosleep, log=nolog)
o3 = cleanup(sh, 1, 3, "#9", [x[2] for x in bs[2]], rs[2], sleep=nosleep, log=nolog)
check("(라) 3중: 가장 앞선 블록·타판 보존(셋째는 행 밀림으로 보류돼도 무손실)",
      o2 == 'deleted' and o3 in ('held', 'deleted') and sh.rows[n0:n0 + 10] == bs[0] and sh.rows[1:8] == OTHER and gcount(sh, "#9") >= 10, (o2, o3, gcount(sh, "#9")))

# (마) 같은 로스터의 서로 다른 게임ID 연속 판 → 둘 다 보존(절대 지우지 않음)
sh = mk(extra=block("#8", "rt", RFIRST)); n0 = len(sh.rows); g8 = [list(x) for x in sh.rows[-10:]]
r, logs = call(sh, "9", block("#9"))
check("(마) 같은 10명·다른 게임ID 연속 판 → appended·두 판 모두 보존",
      r == 'appended' and sh.deletes == [] and gcount(sh, "#8") == 10 and gcount(sh, "#9") == 10 and sh.rows[n0 - 10:n0] == g8, (r, sh.deletes))
sh = mk(extra=block("#8", "lcu")); n0 = len(sh.rows)                         # 바로 앞 판이 같은 로스터 lcu 블록이어도 마찬가지
r, logs = call(sh, "9", block("#9", "lcu", RFIRST))
check("(마) 바로 앞 판이 같은 로스터여도 삭제 0", r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 10)
# 같은 로스터 연속 판에서 #9 만 경합 → #9 뒤쪽만 지우고 #8 은 그대로
sh = mk(extra=block("#8", "lcu")); n0 = len(sh.rows); g8 = [list(x) for x in sh.rows[-10:]]; rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
r, logs = call(sh, "9", block("#9"))
check("(마) 연속 판 + #9 경합 → #9 뒤쪽만 삭제·#8 보존", r == 'deduped' and sh.deletes == [(n0 + 11, n0 + 20)] and sh.rows[n0 - 10:n0] == g8 and sh.rows[n0:] == rival, (r, sh.deletes))

# (바) append 응답 없음 / 읽기 실패 / 행 밀림 → 보류하고 아무것도 안 지움
sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival]); sh.no_resp = True
r, logs = call(sh, "9", block("#9"))
check("(바) append 응답 없음 → 보류·삭제 0(중복 20줄 보존)", r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20 and any("보류" in m for m in logs), (r, logs))
sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
sh.post_append = lambda s: setattr(s, 'fail_reads', True)
r, logs = call(sh, "9", block("#9"))
check("(바) 사후 정리 읽기 실패 → 보류·삭제 0", r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20 and any("읽기 실패" in m for m in logs), (r, logs))
sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
sh.post_append = lambda s: s.rows.__delitem__(slice(1, 3))               # 내 블록 위쪽 2행이 사라져 행 번호가 밀림
r, logs = call(sh, "9", block("#9"))
check("(바) 행 밀림 → 보류·삭제 0", r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20 - 2 and gcount(sh, "#9") == 20, (r, sh.deletes, logs))
sh = mk(extra=block("#9", "rt", RFIRST)[:5]); n0 = len(sh.rows)           # 앞선 사본이 불완전(5줄뿐)이면 확인 단계에서 이미 '있음'
r, logs = call(sh, "9", block("#9"))
check("앞선 사본이 불완전해도 같은 게임ID 가 있으면 안 씀(종전 규칙 그대로)", r == 'exists' and sh.appends == 0 and len(sh.rows) == n0)
sh = mk(); n0 = len(sh.rows); other_names = NAMES[:9] + ["zz#KR1"]; rival = block("#9", "rt", RFIRST, other_names)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
r, logs = call(sh, "9", block("#9"))
check("(바) 앞선 블록의 이름 집합이 다르면(다른 판일 가능성) 삭제 0", r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20, (r, logs))

# (사) 헤더에 열이 없음 → 정리 생략(쓰기는 종전대로)
for miss, tag in (("소환사명", "소환사명"), ("게임ID", "게임ID")):
    hd2 = [h for h in HDR if h != miss]
    sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
    sh.before_append = lambda s, rv=rival: s.rows.extend([list(x) for x in rv])
    r, logs = call(sh, "9", block("#9"), hd=hd2)
    check(f"(사) 헤더에 {miss} 열 없음 → 정리 생략·삭제 0·로그", r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20
          and any("중복정리 생략" in m and tag in m for m in logs), (r, logs))
for label, bad_rows in (("게임ID 칸이 헤더의 게임ID 열에 안 놓임", [["x", "#9", f"p{i}#KR1"] + ["-"] * 3 for i in range(10)]),
                        ("행이 헤더의 소환사명 열보다 짧음", [["#9", "x"] for _ in range(10)])):
    sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
    sh.before_append = lambda s, rv=rival: s.rows.extend([list(x) for x in rv])
    r, logs = call(sh, "9", bad_rows)
    check(f"(사) 쓴 행의 열 배치가 헤더와 안 맞으면({label}) 정리 생략·삭제 0",
          r == 'appended' and sh.deletes == [] and len(sh.rows) == n0 + 20 and any("열 배치" in m for m in logs), (r, logs))

# 예외는 밖으로 던지지 않는다
sh = mk(); n0 = len(sh.rows); sh.fail_append = RuntimeError("500 backend")
r, logs = call(sh, "9", block("#9"))
check("append 예외 → failed·로그 '기입 실패'·시트 불변", r == 'failed' and len(sh.rows) == n0 and any("기입 실패" in m and "500" in m for m in logs), (r, logs))
sh = mk(); sh.fail_reads = True
r, logs = call(sh, "9", block("#9"))
check("확인 읽기 예외 → failed(쓰지 않음)", r == 'failed' and sh.appends == 0 and any("기입 실패" in m for m in logs), (r, logs))
r, logs = call(None, "9", block("#9"))
check("시트 객체가 망가져도 예외 안 던짐 → failed", r == 'failed', (r, logs))
r, logs = call(mk(), "9", [])
check("쓸 행이 없으면 failed", r == 'failed')
def badlog(_): raise RuntimeError("stdout closed")                             # 로그 출력 자체가 실패해도 기록 흐름은 안 깨진다
sh = mk(); sh.fail_append = RuntimeError("500 backend")
check("로그 함수가 예외를 내도 도우미는 안 던짐(failed)", append_block(sh, HDR, "9", block("#9"), sleep=nosleep, log=badlog) == 'failed')
sh = mk(); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
check("로그 함수가 예외를 내도 정리는 정상 수행(deduped)", append_block(sh, HDR, "9", block("#9"), sleep=nosleep, log=badlog) == 'deduped'
      and len(sh.rows) == n0 + 10 and sh.rows[n0:] == rival)
sh = mk(); n0 = len(sh.rows)
class Boom(Sheet):
    def delete_rows(self, s, e): raise RuntimeError("403 protected range")
sh = Boom([HDR] + OTHER); n0 = len(sh.rows); rival = block("#9", "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
r, logs = call(sh, "9", block("#9"))
check("삭제 자체가 실패해도 예외 안 던짐·시트 불변(중복 보존)", r == 'appended' and len(sh.rows) == n0 + 20 and any("삭제 안 함" in m for m in logs), (r, logs))

# ═══════════════ B. _lcu_backfill_once 통합 (가짜 LCU 전적 + 가짜 시트) ═══════════════
LANES = [("TOP", ""), ("JUNGLE", ""), ("MIDDLE", ""), ("BOTTOM", "DUO_CARRY"), ("BOTTOM", "DUO_SUPPORT")]
def game_detail(gid, names=NAMES, map_id=11, order=NATURAL):
    parts, idents = [], []
    for pos, i in enumerate(order):
        pid = pos + 1; team = 100 if i < 5 else 200; lane, role = LANES[i % 5]
        parts.append({"participantId": pid, "teamId": team, "championId": 1, "spell1Id": 4, "spell2Id": 12,
                      "stats": {"kills": 1, "deaths": 2, "assists": 3, "win": team == 100, "goldEarned": 1000, "totalMinionsKilled": 10,
                                "neutralMinionsKilled": 0, "visionScore": 5, "visionWardsBoughtInGame": 0, "wardsPlaced": 1, "wardsKilled": 0,
                                "totalDamageTaken": 100, "totalDamageDealtToChampions": 500, "item0": 1055, "perk0": 8005,
                                "perkPrimaryStyle": 8000, "perkSubStyle": 8200},
                      "timeline": {"lane": lane, "role": role}})
        gn, tg = names[i].split("#")
        idents.append({"participantId": pid, "player": {"gameName": gn, "tagLine": tg, "puuid": f"pu{i}"}})
    return {"gameId": int(gid), "mapId": map_id, "gameType": "CUSTOM_GAME", "gameDuration": 1800,
            "gameCreation": time.time() * 1000 - 3600_000, "gameVersion": "16.19.123.456", "participants": parts,
            "participantIdentities": idents, "teams": [{"teamId": 100, "win": "Win"}, {"teamId": 200, "win": "Fail"}]}
class Resp:
    def __init__(self, d): self.d = d
    def json(self): return self.d
class FakeReq:
    def __init__(self, details): self.details = details; self.calls = []
    def get(self, url, headers=None, verify=None, timeout=None):
        self.calls.append(url)
        if "/matches?" in url:
            return Resp({"games": {"games": [{"gameId": int(g), "gameType": "CUSTOM_GAME", "mapId": d["mapId"], "gameCreation": d["gameCreation"]}
                                             for g, d in self.details.items()]}})
        if url.endswith("/lol-summoner/v1/current-summoner"): return Resp({"puuid": "ME"})
        m = re.search(r"/games/(\d+)$", url)
        if m and m.group(1) in self.details: return Resp(self.details[m.group(1)])
        raise AssertionError("예상 밖 요청 " + url)
def make_env(details, classic_extra=(), kiwi_extra=()):
    sheets = {"CLASSIC_NORMAL": Sheet([HDR] + OTHER + list(classic_extra), "CLASSIC_NORMAL"),
              "KIWI_KIWI": Sheet([KIWI_HDR] + OTHER + list(kiwi_extra), "KIWI_KIWI")}
    req = FakeReq(details)
    e = {"re": re, "random": random, "threading": threading, "requests": req, "global_champ_map": {1: {"kor": "아리"}},
         "time": types.SimpleNamespace(sleep=lambda s: None, time=time.time, strftime=time.strftime, localtime=time.localtime),
         "global_spreadsheet": types.SimpleNamespace(worksheet=lambda tn: sheets[tn]),
         "_inv_lcu_creds": lambda: ("https://127.0.0.1:2999", {"Authorization": "x"}),
         "parse_endgame_achievements": lambda *a, **k: [None, "pu0", None, None, "pu5", None, None, "pu9", None, None, None, {"pu0": 9.5, "pu5": 8.0}]}
    exec(TN, e); exec(SRC[CL_A:CL_B], e); exec(SRC[RUN_A:RUN_B], e)
    return e, sheets, req
def run_once(e):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): e['_lcu_backfill_once']()
    return buf.getvalue()

GID = "8410400062"
# B1 정상 회수 + 같은 10명이 연달아 치른 다음 판(로스터·시간으로 건너뛰지 않는다)
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
sh = sheets["CLASSIC_NORMAL"]; n0 = len(sh.rows); prev = [list(x) for x in sh.rows[-10:]]
out = run_once(e)
check("B1 통합: 같은 로스터의 다음 판도 회수(10행) — 이전 판 보존", sh.appends == 1 and len(sh.rows) == n0 + 10 and sh.deletes == []
      and sh.rows[n0 - 10:n0] == prev and gcount(sh, "#" + GID) == 10 and GID in e['_LCU_BF_DONE'], out)
check("B1 통합: 종전 로그 문구 유지", f"[lcu백필] #{GID} CLASSIC_NORMAL 10행 회수 (클랜원 10명" in out, out)
newrows = sh.rows[n0:]
check("B1 통합: 쓴 행 모양(게임ID·이름·19칸)", all(r[0] == "#" + GID and len(r) == 19 for r in newrows) and [r[2] for r in newrows] == NAMES, newrows[:1])
# B2 다른 PC 가 확인과 확인 사이에 먼저 씀
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
sh = sheets["CLASSIC_NORMAL"]; n0 = len(sh.rows); rival = block("#" + GID, "rt", RFIRST)
sh.after_gid_reads = (2, lambda s: s.rows.extend([list(x) for x in rival]))   # 1=회차 시작 스냅샷, 2=도우미 첫 확인 → 직후 상대가 씀
out = run_once(e)
check("B2 통합: 대기 중 선기록 → 내 append 0회·회수 처리로 기록·상대 10줄만", sh.appends == 0 and len(sh.rows) == n0 + 10 and sh.rows[n0:] == rival
      and GID in e['_LCU_BF_DONE'] and "먼저 기록" in out and "행 회수" not in out, out)
# B3 append 직전 경합 → 내 블록만 정리
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
sh = sheets["CLASSIC_NORMAL"]; n0 = len(sh.rows); rival = block("#" + GID, "rt", RFIRST)
sh.before_append = lambda s: s.rows.extend([list(x) for x in rival])
out = run_once(e)
check("B3 통합: 경합 → 상대 사본만 남기고 내 블록 삭제·회수 확정", sh.appends == 1 and len(sh.rows) == n0 + 10 and sh.rows[n0:] == rival
      and sh.deletes == [(n0 + 11, n0 + 20)] and GID in e['_LCU_BF_DONE'] and "동시 기록 경합" in out and "행 회수" not in out, (out, sh.deletes))
check("B3 통합: 정리 로그가 찍힘", "[중복정리]" in out and "10줄 삭제" in out, out)
# B4 append 예외 → 기입 실패 로그·DONE 미등록 → 다음 회차에 재시도로 회수
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
sh = sheets["CLASSIC_NORMAL"]; n0 = len(sh.rows); sh.fail_append = RuntimeError("503 backend")
out = run_once(e)
check("B4 통합: append 예외 → '기입 실패' 로그·DONE 미등록·시트 불변", f"[lcu백필] #{GID} 기입 실패: 503 backend" in out and GID not in e['_LCU_BF_DONE'] and len(sh.rows) == n0, out)
sh.fail_append = None
out = run_once(e)
check("B4 통합: 다음 회차에 재시도해 회수", f"#{GID} CLASSIC_NORMAL 10행 회수" in out and GID in e['_LCU_BF_DONE'] and gcount(sh, "#" + GID) == 10, out)
out = run_once(e)
check("B4 통합: 회수 뒤 회차는 아무것도 안 씀", sh.appends == 1 and gcount(sh, "#" + GID) == 10)
# B5 회차 락 — 이전 회차가 진행 중이면 건너뛰고(남의 락을 풀지 않는다), 끝나면 다시 돈다
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
sh = sheets["CLASSIC_NORMAL"]; n0 = len(sh.rows)
e['_LCU_BF_LOCK'].acquire()
out = run_once(e)
check("B5 통합: 회차 진행 중이면 건너뜀 — LCU·시트 무접촉·락 유지", "이전 회차가 아직 진행 중" in out and req.calls == [] and sh.appends == 0
      and e['_LCU_BF_LOCK'].locked(), out)
e['_LCU_BF_LOCK'].release()
out = run_once(e)
check("B5 통합: 락이 풀리면 정상 회수·회차 뒤 락 해제", gcount(sh, "#" + GID) == 10 and not e['_LCU_BF_LOCK'].locked(), out)
# 회차 안에서 예외가 나도 락은 풀린다
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
e['_inv_lcu_creds'] = lambda: (_ for _ in ()).throw(RuntimeError("lcu down"))
try: run_once(e); raised = False
except RuntimeError: raised = True
check("B5 통합: 회차 예외 후에도 락 해제(다음 주기 정상)", raised and not e['_LCU_BF_LOCK'].locked())
# B6 칼바람 탭(열 순서가 다른 KIWI_KIWI)도 같은 경로 — 경합 시 뒤쪽 정리
KG = "8410400099"
e, sheets, req = make_env({KG: game_detail(KG, map_id=12)}, kiwi_extra=block("#8410400002", "rt", RFIRST))
ks = sheets["KIWI_KIWI"]; n0 = len(ks.rows); rival = block("#" + KG, "rt", RFIRST)
ks.before_append = lambda s: s.rows.extend([list(x) for x in rival])
out = run_once(e)
check("B6 통합: KIWI_KIWI 도 경합 시 뒤쪽 정리", ks.deletes == [(n0 + 11, n0 + 20)] and ks.rows[n0:] == rival and KG in e['_LCU_BF_DONE']
      and len(sheets["CLASSIC_NORMAL"].rows) == 1 + len(OTHER), (out, ks.deletes))
# B7 헤더에 소환사명이 없는 탭 — 쓰기는 종전대로·정리만 생략(로그)
e, sheets, req = make_env({GID: game_detail(GID)}, classic_extra=block("#8410400001", "rt", RFIRST))
sh = sheets["CLASSIC_NORMAL"]; sh.rows[0] = [h for h in HDR if h != "소환사명"] + [""]; n0 = len(sh.rows)
out = run_once(e)
check("B7 통합: 헤더에 소환사명 없음 → 쓰기 유지·정리 생략 로그", sh.appends == 1 and gcount(sh, "#" + GID) == 10 and "중복정리 생략" in out and GID in e['_LCU_BF_DONE'], out)


# ═══════════════ C. 실제 스레드 경합 (여러 PC 가 같은 순간에 같은 판을 회수하는 상황) ═══════════════
#   각 API 호출은 원자적이고 응답은 지연되어 도착하는 가짜 시트에 스레드 N개가 동시에 도우미를 돌린다.
#   불변식: ① 두 PC 면 어떤 끼어들기에서도 정확히 한 블록만 남는다 ② 몇 PC 든 가장 앞선 블록은 지워지지 않고(무기록 불가)
#   타판·헤더는 건드려지지 않는다. (셋 이상이 동시에 겹치면 행 밀림으로 사본이 남을 수 있다 — 보류하고 남기는 쪽이 안전한 한계)
class TSheet:
    def __init__(self, lat): self.rows = [list(HDR)] + [list(r) for r in OTHER]; self.lock = threading.Lock(); self.lat = lat; self.title = "CLASSIC_NORMAL"
    def _l(self): time.sleep(random.uniform(0, self.lat))
    def col_values(self, c):
        self._l()
        with self.lock: col = [r[c - 1] if len(r) >= c else "" for r in self.rows]
        self._l()
        while col and col[-1] == "": col.pop()
        return col
    def append_rows(self, rows, **kw):
        self._l()
        with self.lock:
            start = len(self.rows) + 1; self.rows += [list(r) for r in rows]
        self._l()
        return {"updates": {"updatedRange": f"{self.title}!A{start}:S{start + len(rows) - 1}"}}
    def delete_rows(self, s, e):
        self._l()
        with self.lock: del self.rows[s - 1:e]
def race(nwriters, lat=0.0008):
    sh = TSheet(lat); out = {}; bar = threading.Barrier(nwriters)
    orders = [NATURAL, RFIRST, NATURAL[::-1], [3, 1, 2, 0, 4, 5, 6, 7, 8, 9]]
    def w(i):
        bar.wait()
        out[i] = append_block(sh, HDR, "9", block("#9", "lcu", orders[i % 4]), sleep=lambda s: time.sleep(random.uniform(0, lat * 2)), log=nolog)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(nwriters)]
    [t.start() for t in ts]; [t.join() for t in ts]
    return sh, out
random.seed(20261008)
bad2 = bad_loss = bad_other = 0; T2 = 80
for _ in range(T2):
    sh, out = race(2)
    if gcount(sh, "#9") != 10: bad2 += 1
    if sh.rows[0] != HDR or sh.rows[1:8] != OTHER: bad_other += 1
check(f"C 스레드 경합: 두 PC {T2}회 → 매번 정확히 한 블록(10줄)·타판 무손상", bad2 == 0 and bad_other == 0, (bad2, bad_other))
for nw in (3, 4):
    T = 40; loss = other = notmult = 0
    for _ in range(T):
        sh, out = race(nw)
        n9 = gcount(sh, "#9")
        if n9 < 10: loss += 1
        if n9 % 10: notmult += 1
        if sh.rows[0] != HDR or sh.rows[1:8] != OTHER: other += 1
    check(f"C 스레드 경합: {nw}개 PC {T}회 → 무기록·반쪽 삭제·타판 훼손 0 (남는 중복은 허용 한계)", loss == 0 and notmult == 0 and other == 0, (loss, notmult, other))

print("\n실패 %d건" % len(FAILS)); sys.exit(1 if FAILS else 0)
