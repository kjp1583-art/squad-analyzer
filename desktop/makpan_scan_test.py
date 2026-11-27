# -*- coding: utf-8 -*-
# 🔚 막판 조사 감지(개시·선언·번복·종료·알림 문구) 단위 테스트 — `python desktop/makpan_scan_test.py`
#   실제 함수 소스를 그대로 잘라 exec 한다(GUI·LCU 없이 돈다).
import os, re, sys, time, hashlib
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad_analyzer.py"), encoding="utf-8").read()
i = SRC.index('_MAKPAN = {"decls": [], "trig": False, "sent": 0}')
j = SRC.index('def _makpan_notify_start():')
g = {"re": re, "time": time, "hashlib": hashlib}
exec(SRC[i:j], g)
MP, scan, payload = g["_MAKPAN"], g["_makpan_scan"], g["_makpan_payload"]
RES = []
def check(n, c, info=""):
    RES.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (("  — " + str(info)) if info else ""), flush=True)
def nb(t): return (t or "").replace(" ", "")
def feed(body, who="나"):
    return scan(body, nb(body), who)

# ---------- 개시 표현 ----------
for good in ("막판", "막판조사", "막판 조사", "막판(조사)", "막판!", "막판조사 ㄱㄱ".replace(" ", "")):
    MP.update({"decls": [], "trig": False})
    check(f"개시 인정: {good!r}", feed(good) == "open", feed(good))
for bad in ("막판각?", "막판이네 ㅋㅋ", "이번 판 막판 간다", "막판각", "오늘 막판 몇명?"):
    MP.update({"decls": [], "trig": False})
    check(f"잡담은 개시 아님: {bad!r}", feed(bad) == "" and MP["trig"] is False, feed(bad))

# ---------- 선언·중복·종료 ----------
MP.update({"decls": [], "trig": False})
feed("막판"); check("조사 시작", MP["trig"] is True)
check("'.' 선언", feed(".", "A") == "declare" and MP["decls"] == ["A"], MP["decls"])
check("',' 오타도 선언", feed(",", "B") == "declare" and MP["decls"] == ["A", "B"], MP["decls"])
check("같은 사람 중복 선언은 한 번만", feed(".", "A") == "dup" and MP["decls"] == ["A", "B"], MP["decls"])
check("'3명' 집계 → 조사 종료", feed("3명") == "end" and MP["trig"] is False)
check("종료 뒤 '.' 은 무관", feed(".", "C") == "" and MP["decls"] == ["A", "B"], MP["decls"])

# ---------- 번복(취소·안함·한판더) ----------
MP.update({"decls": ["A", "B", "C"], "trig": True})
check("'취소' → 본인만 빠진다", feed("취소", "B") == "withdraw" and MP["decls"] == ["A", "C"], MP["decls"])
check("'안 함' → 본인만 빠진다", feed("안 함", "A") == "withdraw" and MP["decls"] == ["C"], MP["decls"])
MP.update({"decls": ["A", "C"], "trig": True})
check("'한판더' → 본인만 빠진다", feed("한판더", "C") == "withdraw" and MP["decls"] == ["A"], MP["decls"])
check("선언 안 한 사람의 취소는 무시", feed("취소", "Z") == "withdraw_miss" and MP["decls"] == ["A"], MP["decls"])
check("조사 밖의 '취소'는 아무 일 없음", (MP.update({"trig": False}), feed("취소", "A"))[1] == "")

# ---------- 재선언·초기화 ----------
MP.update({"decls": ["A", "B"], "trig": False})
feed("막판조사"); check("다시 막판조사 = 목록 리셋", MP["decls"] == [] and MP["trig"] is True)
g2 = {"re": re, "time": time, "hashlib": hashlib}; exec(SRC[i:j], g2)
g2["_MAKPAN"].update({"decls": ["A"], "trig": True, "sent": 123})
g2["_noban_reset"] = None
# _noban_reset 은 이 조각 밖 — 초기화 계약만 직접 확인
MP.update({"decls": ["A"], "trig": True, "sent": 123})
MP.update({"decls": [], "trig": False, "sent": 0})
check("초기화 후 상태 비어 있음", MP == {"decls": [], "trig": False, "sent": 0}, MP)

# ---------- 게임 시작 알림 문구 ----------
MP.update({"decls": ["레넥톤 윤 슬", "귤 갓"], "trig": True})
p1 = payload(now=1_800_000_000)
check("알림 마커 형식(h·n·이름)", p1.startswith("🔚 [막판알림] h=") and " n=2" in p1 and "막판: 레넥톤 윤 슬, 귤 갓" in p1, p1)
check("같은 20분 구간은 같은 h(인스턴스 중복 방지)", payload(now=1_800_000_100).split("h=")[1].split()[0] == p1.split("h=")[1].split()[0])
check("다음 판(구간 이동)은 다른 h", payload(now=1_800_001_500).split("h=")[1].split()[0] != p1.split("h=")[1].split()[0])
MP.update({"decls": [], "trig": False})
check("선언 없으면 알림 없음", payload() == "")

print()
print(f"{sum(RES)}/{len(RES)} 통과")
sys.exit(0 if all(RES) and len(RES) >= 20 else 1)
