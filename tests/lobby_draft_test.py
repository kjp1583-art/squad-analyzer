#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎲 내전진행(팀뽑 자동화) 단위 테스트 — `python3 tests/lobby_draft_test.py`

롤 클라이언트 없이 돈다. DraftEngine 은 순수 로직이라 가짜 로비(이름 목록 + now 함수)만 주면
전체 흐름을 끝까지 돌릴 수 있다. LCU 층은 응답 dict 를 직접 넣어 확인한다.

검사: 가위바위보 승패·무승부 재대결·표기(묵/찌/빠/이모지)·초성 반복(ㅉㅉㅉㅉ/ㅁㅁㅁㅁ/ㅂㅂㅂㅂ/ㅃㅃㅃㅃ),
      카운트다운 '3' · '2' · '1' · '가위바위보!' 순차 전송, 선/후, 블루/레드, 1-2-2-2-1 순서,
      남은 1명 선 팀 자동 배정, 번호 파싱, 줄임말(맛장유→맛동산장인유미)·모호한 줄임말 재요청,
      비차례 발언·이미 뽑힌 인원·로비 밖 인원 무시, 시간 초과 재안내/중단,
      관전 슬롯(customSpectators) 판별과 참가 10명 확정 규칙(11~12명 방).
"""
import os
import py_compile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(ROOT, "desktop", "lobby_draft.py")
sys.path.insert(0, os.path.join(ROOT, "desktop"))

import lobby_draft as ld   # noqa: E402  (desktop 경로를 먼저 넣고 불러온다)

FAILS = []


def check(name, cond, info=""):
    ok = bool(cond)
    if not ok:
        FAILS.append(name)
    print(("PASS " if ok else "FAIL ") + name + (f"  — {info}" if (info and not ok) else ""), flush=True)


def spoken(eng):
    return "\n".join(eng.sent)


TEN = ["맛동산장인유미", "김철수", "이영희", "박민수", "최지훈",
      "정수빈", "한예린", "오도현", "서하늘", "강보람"]


# ─────────────────────── 1. 문구 해석 ───────────────────────
def test_parsing():
    check("가위/바위/보 그대로 인식", (ld.parse_rps("가위"), ld.parse_rps("바위"), ld.parse_rps("보")) == ("가위", "바위", "보"))
    check("묵=바위 · 찌=가위 · 빠=보", (ld.parse_rps("묵"), ld.parse_rps("찌"), ld.parse_rps("빠")) == ("바위", "가위", "보"))
    check("이모지·느낌표·공백 허용", ld.parse_rps(" ✌️ ") == "가위" and ld.parse_rps("바위!!") == "바위")
    check("'가위바위보!' 카운트 문장은 손이 아님",
          ld.parse_rps("3.. 2.. 1.. 가위바위보!") is None and ld.parse_rps("가위바위보") is None)
    check("두 손을 같이 쓴 줄은 무시", ld.parse_rps("가위 바위") is None and ld.parse_rps("가위/보") is None)
    check("잡담은 손이 아님", ld.parse_rps("가는중") is None and ld.parse_rps("ㅋㅋ") is None)

    # [2026-11-29 사장님 제보 "ㅉㅉㅉㅉ, ㅁㅁㅁㅁ 해도 인식을 못하네?"] 초성·반복 입력
    check("초성 반복: ㅉ=가위 · ㅁ=바위 · ㅂ/ㅃ=보",
          [ld.parse_rps(x) for x in ("ㅉ", "ㅉㅉ", "ㅉㅉㅉㅉ", "ㅁ", "ㅁㅁㅁㅁ", "ㅂㅂㅂㅂ", "ㅃㅃㅃㅃ")]
          == ["가위", "가위", "가위", "바위", "바위", "보", "보"])
    check("같은 손 반복: 찌찌찌 · 묵묵묵 · 빠빠빠 · 가위가위 · 바위바위 · 보보보",
          [ld.parse_rps(x) for x in ("찌찌찌", "묵묵묵", "빠빠빠", "가위가위", "바위바위", "보보보")]
          == ["가위", "바위", "보", "가위", "바위", "보"])
    check("반복 표기도 공백·느낌표 허용", ld.parse_rps(" ㅉㅉㅉ ") == "가위" and ld.parse_rps("묵묵묵!") == "바위")
    check("서로 다른 손이 섞이면 거름(찌묵 · ㅉㅁ · ㅁㅂ · 가위바위보)",
          all(ld.parse_rps(x) is None for x in ("찌묵", "ㅉㅁ", "ㅁㅂ", "보가위", "가위바위보")))
    check("카운트 숫자는 손이 아님", all(ld.parse_rps(x) is None for x in ("3", "2", "1", "가위바위보!")))

    check("가위>보 · 바위>가위 · 보>바위",
          (ld.rps_result("가위", "보"), ld.rps_result("바위", "가위"), ld.rps_result("보", "바위")) == (1, 1, 1))
    check("역방향은 -1 · 같은 손은 0",
          (ld.rps_result("보", "가위"), ld.rps_result("가위", "가위")) == (-1, 0))

    check("선/후 표기들", (ld.parse_side("선"), ld.parse_side("선픽"), ld.parse_side("후"), ld.parse_side("후픽"))
          == ("선", "선", "후", "후"))
    check("'선/후' 처럼 둘 다 쓴 질문 문장은 선택이 아님", ld.parse_side("선/후") is None)
    check("블루/레드 표기들", (ld.parse_color("블루"), ld.parse_color("블"), ld.parse_color("1팀"),
                          ld.parse_color("레드"), ld.parse_color("레"), ld.parse_color("2팀"))
          == ("블루", "블루", "블루", "레드", "레드", "레드"))
    check("'블루/레드' 안내문은 선택이 아님", ld.parse_color("블루/레드") is None)

    check("번호 표기 3·3번·#3·03", [ld.as_number(x) for x in ("3", "3번", "#3", "03", " 3. ")] == [3, 3, 3, 3, 3])
    check("번호가 아닌 것", (ld.as_number("삼"), ld.as_number("3번째아님"), ld.as_number("김철수")) == (None, None, None))

    check("줄임말 글자순서: 맛장유 → 맛동산장인유미",
          ld.match_names("맛장유", ["맛동산장인유미", "김철수"]) == ("seq", [0]))
    check("접두 일치가 부분 일치보다 우선", ld.match_names("김", ["김철수", "박김"])[0] == "prefix")
    check("정확 일치가 최우선", ld.match_names("김철수", ["김철수", "김철수2"]) == ("exact", [0]))


# ─────────────────────── 2. 엔진 도우미 ───────────────────────
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def tick(self, dt):
        self.t += dt


def test_engine_basics():
    check("8명 뽑기 순서 = 선1·후2·선2·후2 (7회) + 남은 1명",
          ld.draft_order(8) == ["S", "H", "H", "S", "S", "H", "H"], ld.draft_order(8))
    check("2명이면 뽑기 1회 + 남은 사람 없음", ld.draft_order(2) == ["S"], ld.draft_order(2))
    check("순서가 4칸 주기로 반복", ld.draft_order(12) == ["S", "H", "H", "S", "S", "H", "H", "S", "S", "H", "H"])

    rows = [{"name": "A", "key": "a", "spectator": False}, {"name": "B", "key": "b", "spectator": True}]
    check("선택 기본값 = 관전 슬롯 제외", ld.default_selection(rows) == ["A"])
    check("10명 이상이면 정확히 10명이어야 시작", (ld.selection_ready(12, 10), ld.selection_ready(12, 11),
                                              ld.selection_ready(12, 9)) == (True, False, False))
    check("10명 미만이면 모인 전원으로 시작", (ld.selection_ready(8, 8), ld.selection_ready(8, 7)) == (True, False))
    check("안내 문구: 12명 중 10명", "시작할 수 있어요" in ld.selection_hint(12, 10))
    check("안내 문구: 12명 중 11명 → 한 명 더 체크", "관전자로 체크" in ld.selection_hint(12, 11))

    eng = ld.DraftEngine(TEN, now=Clock())
    eng.start()
    check("시작하자마자 가위바위보 안내가 나감",
          "가위바위보" in eng.sent[0] and "(먼저 내는 2명이 팀장)" in eng.sent[0], eng.sent[:2])

    eng.feed("김철수", "가위")
    check("한 명만 냈을 때는 아직 팀장 확정 전", eng.phase == "rps" and not eng.winner)
    eng.feed("박민수", "보")
    check("두 번째가 내면 승패 판정(가위>보)",
          eng.winner == "김철수" and eng.phase == "side", (eng.winner, eng.phase))
    check("팀장 확정 공지에 두 이름이 다 들어감",
          "김철수" in spoken(eng) and "박민수" in spoken(eng))
    eng.feed("김철수", "후")
    check("승자가 '후' → 진영 선택권은 패자에게", eng.seon == "박민수" and eng.hu == "김철수")
    eng.feed("박민수", "레드")
    check("진영 확정 — 선 팀장이 레드", eng.seon_color == "레드" and eng.teams["레드"][:1] == ["박민수"])
    check("팀장 둘은 번호 명단에서 빠짐",
          len(eng.roster) == 8 and "김철수" not in [n for _i, n in eng.roster]
          and "박민수" not in [n for _i, n in eng.roster])
    check("번호 1~8 이 로비 순서대로", [n for n, _nm in eng.roster] == list(range(1, 9)))
    check("번호 명단을 로비에 공지", "1.맛동산장인유미" in spoken(eng))


# ─────────────────────── 3. 전체 흐름 ───────────────────────
def play_to_draft(eng):
    eng.start()
    eng.feed(TEN[1], "바위")
    eng.feed(TEN[2], "가위")          # 바위 승 → TEN[1] 팀장 승
    eng.feed(TEN[1], "선")            # 승자가 선
    eng.feed(TEN[1], "블루")          # 선이 블루


def test_full_flow():
    eng = ld.DraftEngine(TEN, now=Clock())
    play_to_draft(eng)
    check("드래프트 시작 — 블루 팀장이 선", eng.phase == "draft" and eng.seon == TEN[1] and eng.seon_color == "블루")
    check("첫 차례는 선 팀장", eng._current_captain() == TEN[1] and eng._current_side() == "S")

    # 후 팀장(레드)의 차례가 아닐 때 말해도 무시
    eng.feed(TEN[2], "5")
    check("차례가 아닌 사람의 지목은 무시", len(eng.teams["레드"]) == 1 and eng.turn == 0)

    eng.feed(TEN[1], "1")             # 선 1명
    check("선 팀장 1명 지목", len(eng.teams["블루"]) == 2 and eng.turn == 1)
    eng.feed(TEN[1], "2")             # 연속 차례가 아니므로 무시
    check("연속 차례가 아니면 같은 사람이 또 못 뽑음", len(eng.teams["블루"]) == 2)

    eng.feed(TEN[2], "2, 3")          # 후 2명
    check("후 팀장 2명 지목", [n for n in eng.teams["레드"]] == [TEN[2], TEN[3], TEN[4]],
          eng.teams["레드"])
    eng.feed(TEN[1], "4 5")           # 선 2명
    check("선 팀장 2명 지목", [n for n in eng.teams["블루"]] == [TEN[1], TEN[0], TEN[5], TEN[6]],
          eng.teams["블루"])
    eng.feed(TEN[2], "6")
    eng.feed(TEN[2], "7")
    check("후 팀장 마지막 2명", [n for n in eng.teams["레드"]] == [TEN[2], TEN[3], TEN[4], TEN[7], TEN[8]],
          eng.teams["레드"])
    check("남은 1명은 선 팀으로 자동 배정하고 종료",
          eng.phase == "done" and TEN[9] in eng.teams["블루"] and len(eng.teams["블루"]) == 5)
    check("최종 5:5 명단을 로비에 확정 공지",
          "🏁 팀뽑 종료!" in spoken(eng) and "🔵 블루 (5명)" in spoken(eng) and "🔴 레드 (5명)" in spoken(eng))
    check("종료 뒤 채팅에는 반응하지 않음",
          (eng.feed(TEN[1], "8"), eng.phase) == (None, "done"))


def test_tie_and_redeal():
    clk = Clock()
    eng = ld.DraftEngine(TEN, now=clk)
    eng.start()
    eng.feed(TEN[1], "가위")
    eng.feed(TEN[2], "찌")            # 찌 = 가위 → 무승부
    check("무승부면 자동 재대결 카운트", "무승부" in spoken(eng) and eng.phase == "rps" and eng.tie_pair == [TEN[1], TEN[2]])
    eng.feed(TEN[3], "보")
    check("재대결에는 두 팀장의 손만 반영", eng.phase == "rps" and len(eng.rps_round) == 0)
    eng.feed(TEN[1], "보")
    eng.feed(TEN[2], "가위")          # 가위 > 보 → TEN[2] 승
    check("재대결 판정", eng.winner == TEN[2] and eng.phase == "side")


def test_abbreviation_and_ambiguity():
    names = ["맛동산장인유미", "맛동산장인유미2", "김철수", "이영희", "박민수", "최지훈", "정수빈", "한예린", "오도현", "서하늘"]
    eng = ld.DraftEngine(names, now=Clock())
    eng.start()
    eng.feed(names[8], "바위")
    eng.feed(names[9], "가위")
    eng.feed(names[8], "선")
    eng.feed(names[8], "블루")
    draft_cap = names[8]
    body = "\n".join(ld.split_tokens("1"))
    check("드래프트 준비 완료", eng.phase == "draft" and len(eng.roster) == 8, (eng.phase, len(eng.roster)))

    eng.feed(draft_cap, "맛")
    check("'맛'은 두 명과 겹침 → 확정하지 않고 후보 번호를 알려 줌",
          "후보가 2명" in spoken(eng) and len(eng.teams["블루"]) == 1)
    check("모호할 때는 차례가 넘어가지 않음", eng.turn == 0)
    eng.feed(draft_cap, "맛장유")
    check("'맛장유'도 두 명과 겹쳐 재요청", "후보가 2명" in spoken(eng) and len(eng.teams["블루"]) == 1)
    eng.feed(draft_cap, "1번")
    check("번호로 다시 고르면 확정", len(eng.teams["블루"]) == 2)

    # 한 명만 남는 줄임말은 바로 확정
    eng2 = ld.DraftEngine(TEN, now=Clock())
    play_to_draft(eng2)
    eng2.feed(eng2.seon, "맛장유")
    check("유일한 줄임말은 바로 확정", "맛동산장인유미" in eng2.teams["블루"], eng2.teams["블루"])

    eng3 = ld.DraftEngine(TEN, now=Clock())
    play_to_draft(eng3)
    eng3.feed(eng3.seon, "철수")
    check("이름 일부(부분일치)로도 확정", "김철수" in eng3.teams["블루"], eng3.teams["블루"])


def test_ignored_and_errors():
    eng = ld.DraftEngine(TEN, now=Clock())
    play_to_draft(eng)
    eng.feed("로비밖사람", "1")
    check("로비 인원이 아니면 무시", len(eng.teams["블루"]) == 1)
    eng.feed(TEN[1], "1")
    eng.feed(TEN[2], "99")
    check("번호 범위 밖은 안내만, 차례 유지", eng.turn == 1 and "1~8번" in spoken(eng),
          (eng.turn, eng.sent[-1]))
    eng.feed(TEN[2], "zzzz")
    check("알아들을 수 없는 잡담은 조용히 무시", eng.turn == 1)
    eng.feed(TEN[2], "1")
    check("이미 뽑힌 번호는 안내만, 차례 유지", eng.turn == 1 and "이미 뽑혔" in spoken(eng))

    eng.feed(TEN[2], "2")
    eng.feed(TEN[2], "3 4")
    check("연속 1차례일 때는 2명을 한꺼번에 받지 않음", len(eng.teams["레드"]) == 3 and "이번엔 1명까지" in spoken(eng),
          (eng.teams["레드"], eng.sent[-1]))


def test_countdown_lines():
    """[2026-11-29 사장님 지시] 카운트다운을 '3' '2' '1' '가위바위보!' 로 각각 따로, 1초 간격으로 보낸다."""
    clk = Clock()
    eng = ld.DraftEngine(TEN, now=clk)
    eng.start()
    check("안내문 다음에 '3' 이 바로 따로 나감(한 줄에 몰아 보내지 않음)",
          eng.sent[:2] == ["🎲 팀장 가위바위보! (먼저 내는 2명이 팀장)", "3"], eng.sent[:3])
    check("'2'·'1'·'가위바위보!' 는 큐에 대기(전송 함수가 한 번도 막히지 않음)", len(eng.sent) == 2, eng.sent)
    got = ["3"]
    for _ in range(3):
        clk.tick(ld.DraftEngine.COUNTDOWN_GAP)
        eng.tick()
        got.append(eng.sent[-1])
    check("'3' → '2' → '1' → '가위바위보!' 순서로 한 줄씩", got == ["3", "2", "1", "가위바위보!"], got)
    check("카운트가 끝나도 가위바위보 단계 유지", eng.phase == "rps")
    check("응답 대기(deadline)는 카운트가 끝난 시점부터 셈",
          abs(eng.deadline - (clk.t + ld.DraftEngine.RPS_WAIT)) < 0.01, (eng.deadline, clk.t))
    check("카운트 중에도 사람 손은 그대로 받음",
          (eng.feed(TEN[1], "묵묵묵"), eng.rps_round) == (None, [(TEN[1], "바위")]), eng.rps_round)

    # 판정이 나면 남은 카운트 줄은 보내지 않는다(판정 뒤 로비에 '1' · '가위바위보!' 가 튀지 않게)
    clk2 = Clock()
    eng2 = ld.DraftEngine(TEN, now=clk2)
    eng2.start()
    eng2.feed(TEN[1], "ㅁㅁㅁㅁ")
    eng2.feed(TEN[2], "ㅉㅉㅉㅉ")
    check("초성 반복으로도 판정 — ㅁ(바위) > ㅉ(가위)", eng2.winner == TEN[1] and eng2.phase == "side",
          (eng2.winner, eng2.phase))
    n_before = len(eng2.sent)
    for _ in range(4):
        clk2.tick(ld.DraftEngine.COUNTDOWN_GAP)
        eng2.tick()
    check("판정 뒤 남은 카운트 줄은 보내지 않음", len(eng2.sent) == n_before, eng2.sent[n_before:])

    # 재대결·응답 없음 재시도도 같은 방식으로 한 줄씩
    clk3 = Clock()
    eng3 = ld.DraftEngine(TEN, now=clk3)
    eng3.start()
    eng3.feed(TEN[1], "ㅁㅁㅁㅁ")
    eng3.feed(TEN[2], "ㅁ")
    check("무승부 안내는 따로 나가고 카운트는 '3' 부터 다시",
          "무승부" in eng3.sent[-2] and eng3.sent[-1] == "3", eng3.sent[-2:])
    clk3.tick(ld.DraftEngine.COUNTDOWN_GAP)
    eng3.tick()
    check("무승부 재대결 카운트도 한 줄씩", eng3.sent[-1] == "2", eng3.sent[-1])


def test_timeout():
    clk = Clock()
    eng = ld.DraftEngine(TEN, now=clk)
    eng.start()
    clk.tick(ld.DraftEngine.COUNTDOWN_GAP * (len(ld.DraftEngine.COUNTDOWN) - 1) + ld.DraftEngine.RPS_WAIT + 1)
    eng.tick()
    check("가위바위보 응답이 없으면 다시 카운트", "다시 카운트" in eng.sent[-2] and eng.sent[-1] == "3"
          and eng.phase == "rps", eng.sent[-2:])
    eng.feed(TEN[1], "바위")
    for _ in range(4):
        clk.tick(ld.DraftEngine.RPS_WAIT + 1)
        eng.tick()
    check("재시도 후에도 안 모이면 중단하고 알림", eng.phase == "aborted" and "중단" in eng.sent[-1], eng.phase)

    clk2 = Clock()
    eng2 = ld.DraftEngine(TEN, now=clk2)
    play_to_draft(eng2)
    clk2.tick(ld.DraftEngine.PICK_WAIT + 1)
    eng2.tick()
    check("지목이 없으면 추천과 함께 다시 안내(⏳)", eng2.sent[-1].startswith("⏳") and "차례" in eng2.sent[-1]
          and eng2.phase == "draft", eng2.sent[-1])
    for _ in range(ld.DraftEngine.PICK_TRIES + 1):
        clk2.tick(ld.DraftEngine.PICK_WAIT + 1)
        eng2.tick()
    check("계속 지목이 없으면 채팅 도배 대신 중단", eng2.phase == "aborted", eng2.phase)

    clk3 = Clock()
    eng3 = ld.DraftEngine(TEN, now=clk3)
    eng3.start()
    eng3.feed(TEN[1], "바위")
    eng3.feed(TEN[2], "가위")
    for _ in range(ld.DraftEngine.ASK_TRIES + 1):
        clk3.tick(ld.DraftEngine.ASK_WAIT + 1)
        eng3.tick()
    check("선/후 응답이 계속 없으면 중단", eng3.phase == "aborted", eng3.phase)


# ─────────────────────── 4. 관전자 (11~12명 방) ───────────────────────
def lobby(members, spec=None, team100=None):
    return {"members": members,
            "gameConfig": {"isCustom": True,
                           "customTeam100": team100 or [],
                           "customTeam200": [],
                           "customSpectators": spec or []}}


def member(name, puuid=None, **kw):
    m = {"gameName": name, "puuid": puuid or ("pu_" + name)}
    m.update(kw)
    return m


def test_spectators():
    twelve = [member(n) for n in TEN] + [member("관전1"), member("관전2")]
    rows = ld.classify_members(lobby(twelve, spec=[{"puuid": "pu_관전1", "gameName": "관전1"},
                                                   {"puuid": "pu_관전2"}]))
    check("12명 방 — 관전 슬롯 2명을 관전자로 표시",
          [r["name"] for r in rows if r["spectator"]] == ["관전1", "관전2"])
    check("관전 슬롯을 제외하면 참가 후보 10명", len(ld.default_selection(rows)) == 10)

    rows2 = ld.classify_members(lobby([member(n) for n in TEN] + [member("관전1", isSpectator=True)]))
    check("isSpectator=true 도 관전자", [r["name"] for r in rows2 if r["spectator"]] == ["관전1"])

    rows3 = ld.classify_members(lobby([member(n) for n in TEN] + [member("관전1", role="SPECTATOR")]))
    check("role=SPECTATOR 도 관전자", [r["name"] for r in rows3 if r["spectator"]] == ["관전1"])

    rows4 = ld.classify_members(lobby([member(n) for n in TEN] + [member("관전1")],
                                      spec=["pu_관전1"], team100=[{"puuid": "pu_관전1"}]))
    check("팀 슬롯에 앉아 있으면 관전자 표시를 풀어 참가자로", not [r for r in rows4 if r["spectator"]])

    rows5 = ld.classify_members(lobby([member(n) for n in TEN]))
    check("10명 방은 관전자 없음 → 바로 시작 가능", ld.default_selection(rows5) == TEN)

    # 12명 방에서 호스트가 2번/3번을 관전자로 체크하면 참가 10명
    rows6 = ld.classify_members(lobby([member(n) for n in TEN] + [member("관전1"), member("관전2")]))
    picked = [r["name"] for r in rows6 if r["name"] not in ("김철수", "이영희")]
    check("표시가 없어도 호스트가 체크해 10명을 만들 수 있음", ld.selection_ready(len(rows6), len(picked)) is True)

    # 엔진은 확정된 10명만 안다 — 관전자 채팅은 무시
    eng = ld.DraftEngine(TEN, now=Clock())
    eng.start()
    eng.feed("관전1", "바위")
    eng.feed("관전2", "가위")
    check("확정 명단 밖(관전자) 채팅은 진행에 영향 없음", eng.phase == "rps" and not eng.rps_round)


def test_spectator_slots_merged():
    """2026-11-28 제보다 — members 에 빠진 관전 슬롯 인원·이름 빈 멤버가 목록에서 사라지지 않는지."""
    nine = [member(n) for n in TEN[:9]]

    # ① members 에 아예 없고 customSpectators 에만 있는 사람 → 관전자로 포함
    rows = ld.classify_members(lobby(nine, spec=[{"puuid": "pu_관전1", "summonerId": 111,
                                                   "gameName": "관전1#KR1"}]))
    names = [r["name"] for r in rows]
    check("members 에 없고 관전 슬롯에만 있어도 목록에 포함", "관전1" in names and len(rows) == 10, names)
    check("그 사람은 spectator=True (태그 #KR1 은 떼고 표시)",
          [r["name"] for r in rows if r["spectator"]] == ["관전1"])
    check("9명 팀 + 1명 관전 → 전원 체크하면 시작 가능(10명)",
          ld.selection_ready(len(rows), len(names)) is True and len(ld.default_selection(rows)) == 9)

    # ② members 의 gameName/summonerName 이 비고 displayName 만 있는 경우
    mem = nine + [{"puuid": "pu_관전2", "gameName": "", "summonerName": "", "displayName": "관전2"}]
    rows = ld.classify_members(lobby(mem, spec=[{"puuid": "pu_관전2"}]))
    check("gameName 비고 displayName 만 있어도 누락 없이 인식",
          [r["name"] for r in rows if r["spectator"]] == ["관전2"], [r["name"] for r in rows])

    # ③ members 쪽에는 이름이 아예 없고 customSpectators 에만 이름이 있는 경우 — 같은 사람을 한 줄로
    mem = nine + [{"puuid": "pu_관전3", "summonerId": 333}]
    rows = ld.classify_members(lobby(mem, spec=[{"puuid": "pu_관전3", "gameName": "관전3"}]))
    names = [r["name"] for r in rows]
    check("members 에는 이름이 없고 관전 슬롯에만 이름 → 관전 슬롯 이름으로 인식",
          "관전3" in names and names.count("관전3") == 1, names)
    check("이름 없는 빈 줄이 따로 생기지 않음", len(rows) == 10 and "" not in names, names)
    check("그 사람은 관전자로 표시", [r["name"] for r in rows if r["spectator"]] == ["관전3"])

    # ④ 같은 사람이 members·팀 슬롯·관전 슬롯에 같이 있어도 한 줄로 합치고 참가자로
    mem = nine + [member("관전4")]
    rows = ld.classify_members(lobby(mem,
                                     spec=[{"puuid": "pu_관전4", "gameName": "관전4"}],
                                     team100=[{"puuid": "pu_관전4", "gameName": "관전4"}]))
    names = [r["name"] for r in rows]
    check("members·팀·관전 슬롯 중복 → 한 줄로 합침", len(rows) == 10 and names.count("관전4") == 1, names)
    check("팀 슬롯에 앉아 있으면 참가자(spectator=False) 유지",
          not [r for r in rows if r.get("spectator")], [r for r in rows if r.get("spectator")])

    # ⑤ 팀 슬롯에만 있고 members 에 없는 사람도 빠지지 않는다
    rows = ld.classify_members(lobby(nine, team100=[{"puuid": "pu_팀원9", "gameName": "팀원9"}]))
    check("팀 슬롯에만 있는 사람도 참가자로 포함",
          "팀원9" in [r["name"] for r in rows] and not [r for r in rows if r.get("spectator")],
          [r["name"] for r in rows])

    # ⑥ 문자열 슬롯(puuid 문자열만 오는 형태)도 관전자로 잡는다
    rows = ld.classify_members(lobby(nine + [member("관전5")], spec=["pu_관전5"]))
    check("문자열 관전 슬롯(puuid)도 관전자로 표시",
          [r["name"] for r in rows if r["spectator"]] == ["관전5"], rows)

    # ⑦ 9명 팀 + 관전 2명 = 11명 방 → 관전 1명만 체크하면 10명 확정
    rows = ld.classify_members(lobby(nine,
                                     spec=[{"puuid": "pu_관전1", "gameName": "관전1"},
                                           {"puuid": "pu_관전2", "gameName": "관전2"}],
                                     team100=[{"puuid": "pu_관전1"}]))
    base = ld.default_selection(rows)                       # 팀 슬롯에 있는 관전1 만 참가자
    check("11명 방(팀 9 + 관전 2) — 전원이 rows 에 있고 참가 후보 10명",
          len(rows) == 11 and len(base) == 10, (len(rows), base))
    check("11명 방에서 관전자 1명만 빼면 시작 가능", ld.selection_ready(len(rows), len(base)) is True)

    # ⑧ 빈 슬롯(실제 로비는 빈 자리를 summonerId 0 / 빈 puuid 로 줄 수 있다)은 사람으로 세지 않는다
    empty = {"summonerId": 0, "puuid": "", "displayName": "", "gameName": ""}
    rows = ld.classify_members({"members": nine,
                               "gameConfig": {"customTeam100": [dict(empty), dict(empty)],
                                              "customTeam200": [dict(empty)],
                                              "customSpectators": [dict(empty), dict(empty)]}})
    check("빈 슬롯(summonerId 0·빈 puuid)은 사람으로 세지 않음",
          len(rows) == 9 and not [r for r in rows if r.get("spectator")], [r["name"] for r in rows])


def test_probe_names_via_lcu():
    """이름 없이 puuid/summonerId 만 온 사람을 probe_lobby 가 LCU 조회·채팅으로 채우는지."""
    nine = [member(n) for n in TEN[:9]]

    class FakeLcu:
        def __init__(self, lobby_obj, summoners=None, parts=None):
            self.lobby_obj = lobby_obj
            self.summoners = summoners or {}
            self.parts = parts or {}
            self.cid = ""
            self.asked = []
        def connect(self):
            return True
        def lobby(self):
            return self.lobby_obj
        def get(self, path):
            self.asked.append(path)
            return self.summoners.get(path)
        def chat_id(self):
            self.cid = "cid"
            return self.cid
        def participants(self):
            return self.parts

    # ① 소환사 조회(puuid) 로 이름을 얻는다
    lob = lobby(nine + [{"puuid": "pu_관전1"}], spec=[{"puuid": "pu_관전1"}])
    fake = FakeLcu(lob, summoners={"/lol-summoner/v2/summoners/puuid/pu_관전1":
                                   {"gameName": "관전1#KR1", "displayName": "관전1"}})
    info = ld.probe_lobby(fake)
    names = [r["name"] for r in info["rows"]]
    check("probe: puuid 만 있는 관전자도 목록에 들어간다", info["ok"] and len(info["rows"]) == 10, info)
    check("probe: 소환사 조회로 이름을 채운다", "관전1" in names, names)
    check("probe: 그 사람은 관전자 표시", [r["name"] for r in info["rows"] if r["spectator"]] == ["관전1"])
    check("probe: 참가 후보는 9명(관전자 제외)", info["candidates"] == TEN[:9], info["candidates"])

    # ② puuid 조회가 없으면 summonerId 조회로
    lob = lobby(nine + [{"summonerId": 222}], spec=[{"summonerId": 222}])
    fake = FakeLcu(lob, summoners={"/lol-summoner/v1/summoners/222": {"gameName": "관전2"}})
    info = ld.probe_lobby(fake)
    check("probe: summonerId 조회로 이름 보충", "관전2" in [r["name"] for r in info["rows"]], info["rows"])

    # ③ 소환사 조회가 실패하면 로비 채팅 참가자 명단으로
    lob = lobby(nine + [{"summonerId": 333}], spec=[{"summonerId": 333}])
    fake = FakeLcu(lob, parts={"333": "관전3"})
    info = ld.probe_lobby(fake)
    check("probe: 채팅 참가자 명단으로 이름 보충", "관전3" in [r["name"] for r in info["rows"]], info["rows"])

    # ④ 끝내 못 채워도 줄은 남긴다(인원이 모자라 보이지 않게)
    lob = lobby(nine + [{"summonerId": 444}], spec=[{"summonerId": 444}])
    info = ld.probe_lobby(FakeLcu(lob))
    names = [r["name"] for r in info["rows"]]
    check("probe: 이름을 못 얻어도 목록에서 빼지 않는다", len(info["rows"]) == 10 and any("이름 미확인" in n for n in names), names)


def test_engine_twelve_confirmed():
    """12명 방에서 관전 2명을 뺀 10명으로 돌린 전체 흐름."""
    eng = ld.DraftEngine(TEN, now=Clock())
    play_to_draft(eng)
    check("확정 10명으로 시작하면 번호는 8개", len(eng.roster) == 8)
    order = ["1", "2 3", "4 5", "6", "7"]
    caps = [eng._current_captain()]
    for tok in order:
        cap = eng._current_captain()
        eng.feed(cap, tok)
    check("관전자 2명이 빠진 10명도 5:5로 끝남",
          eng.phase == "done" and len(eng.teams["블루"]) == 5 and len(eng.teams["레드"]) == 5,
          (eng.phase, eng.teams))


# ─────────────────────── 4-1. 페이즈별 추천 ───────────────────────
STATS = {
    "맛동산장인유미": {"power": 3.2, "pos": "원딜", "tier": "T1", "games": 40, "wr": 0.55},
    "김철수": {"power": 3.0, "pos": "탑", "tier": "T2", "games": 30, "wr": 0.50},
    "이영희": {"power": 2.9, "pos": "정글", "tier": "T2", "games": 25, "wr": 0.52},
    "박민수": {"power": 3.1, "pos": "정글", "tier": "T1", "games": 28, "wr": 0.54},
    "최지훈": {"power": 2.6, "pos": "서폿", "tier": "T3", "games": 20, "wr": 0.48},
    "정수빈": {"power": 2.7, "pos": "원딜", "tier": "T3", "games": 18, "wr": 0.47},
    "한예린": {"power": 2.8, "pos": "미드", "tier": "T2", "games": 22, "wr": 0.51},
    "오도현": {"power": 2.5, "pos": "탑", "tier": "T3", "games": 15, "wr": 0.44},
    # 서하늘 — 클랜 기록 없음(추천 대상 아님)
}


def test_recommendations():
    cand = [(1, "맛동산장인유미"), (2, "서하늘")]
    rec = ld.recommend_picks(cand, STATS, filled_positions=["탑"])
    check("추천은 데이터 있는 후보 중에서만", [n for n, _w in rec] == [1] and len(rec) == 1, rec)
    check("추천 사유 = 빈 포지션 + 전투력 순위", rec[0][1] == "빈 포지션 원딜 · 전투력 1위", rec[0][1])

    flip = ld.recommend_picks([(1, "이영희"), (2, "최지훈")], STATS, filled_positions=["탑", "서폿"], limit=1)
    check("전투력이 낮아도 팀의 빈 포지션을 체우면 위로", flip[0][0] == 1 and "빈 포지션 정글" in flip[0][1], flip)
    nofill = ld.recommend_picks([(1, "이영희"), (2, "최지훈")], STATS, filled_positions=["탑", "서폿", "정글"], limit=1)
    check("빈 포지션이 없으면 전투력 순서로", nofill[0][0] == 1 and nofill[0][1] == "전투력 1위", nofill)
    check("데이터가 하나도 없으면 추천하지 않음", ld.recommend_picks([(1, "서하늘")], STATS, []) == [])
    check("2명 뽑는 차례는 1~2순위까지", len(ld.recommend_picks([(i + 1, n) for i, n in enumerate(TEN)], STATS, [], limit=2)) == 2)

    # 엔진: 차례마다 추천이 바뀌는지 — 포지션이 차면 그 포지션 추천이 사라진다
    eng = ld.DraftEngine(TEN, now=Clock(), stats=STATS)
    play_to_draft(eng)                       # 블루 팀장 = 김철수(탑)
    turn1 = eng.sent[-1]
    check("첫 차례 안내에 ★추천이 붙음", "★[" in turn1, turn1)
    check("첫 추천 — 원딜 1순위(맛동산장인유미)", "1.맛동산장인유미 ★[빈 포지션 원딜 · 전투력 1위]" in turn1, turn1)
    check("데이터 없는 후보에는 ★가 붙지 않음", "8.서하늘 ★" not in turn1)

    eng.feed(eng._current_captain(), "1")    # 블루 → 맛동산(원딜)
    red_turn = eng.sent[-1]
    check("후 팀장 차례 — 정글은 이미 있으니 보너스 없는 박민수는 추천 제외",
          "2.박민수 ★" not in red_turn, red_turn)
    check("후 팀장 추천은 빈 포지션 기준(미드·원딜)",
          "5.한예린 ★[빈 포지션 미드" in red_turn and "4.정수빈 ★[빈 포지션 원딜" in red_turn, red_turn)

    eng.feed(eng._current_captain(), "3 4")  # 레드 → 박민수·최지훈
    blue_turn = eng.sent[-1]
    check("블루 다음 차례 — 남은 인원·빈 포지션에 맞춰 추천이 바뀜",
          "2.박민수 ★[빈 포지션 정글 · 전투력 1위]" in blue_turn, blue_turn)


# ─────────────────────── 5. LCU 응답·실행기 구조 ───────────────────────
def test_lcu_shapes():
    class FakeClient:
        def __init__(self, lobby_obj, msgs):
            self.lobby_obj = lobby_obj
            self.msgs = msgs
            self.sent = []
            self.cid = "cid"
        def connect(self):
            return True
        def lobby(self):
            return self.lobby_obj
        def me(self):
            return {"id": "me", "gameName": "맛동산장인유미"}
        def chat_id(self):
            return self.cid
        def messages(self):
            return list(self.msgs)
        def participants(self):
            return {"id1": "김철수", "id2": "이박민수".replace("이", "")}
        def send(self, text):
            self.sent.append(text)
            return True

    lob = lobby([member(n) for n in TEN] + [member("관전1", isSpectator=True)])
    fake = FakeClient(lob, [
        {"id": "m0", "type": "chat", "fromId": "id1", "body": "지난 이야기"},
        {"id": "m1", "type": "chat", "fromId": "id2", "body": "바위"},
    ])
    runner = ld.DraftRunner(client=fake, interval=0.01, names=TEN)
    runner.start()
    for _ in range(200):
        if not runner.alive():
            break
        import time as _t
        _t.sleep(0.01)
    st = runner.status()
    check("실행기: 확정 명단으로 시작하고 엔진이 돌았다", st["members"] == TEN and st["phase"] in ("rps", "side", "done"))
    check("실행기: 시작 전 대화(히스토리)는 먹이지 않음", st["phase"] == "rps")
    check("실행기: 로비에 카운트를 보냈다", any("가위바위보" in s for s in fake.sent))
    check("실행기: 상태 조회에 단계·명단·기록이 있다",
          set(("phase", "lines", "teams", "remaining", "error")) - set(st) == set())

    runner.abort("테스트 종료")
    for _ in range(100):
        if not runner.alive():
            break
        import time as _t
        _t.sleep(0.01)
    check("실행기: 중단하면 스레드가 멈춘다", not runner.alive())


# ──────────── 6. 호스트 본인 채팅 · LCU 발신자 식별 (2026-11-29 제보) ────────────
#   "가위바위보 채팅쳐도 인식을 못하네?" — 내전진행을 누른 본인 채팅이 전부 버려지던 버그.
ME = TEN[0]          # 맛동산장인유미 — 분석기를 켜고 '내전진행'을 누른 호스트


class EchoLcu:
    """로비 채팅을 닮은 LCU 클라이언트 — 보낸 말이 곧바로 채팅 목록에 되돌아온다(실제 롤과 같다)."""

    def __init__(self, me, my_id, parts, echo=True):
        self._me = me
        self.my_id = my_id
        self.parts = parts
        self.echo = echo
        self.msgs = []
        self.sent = []
        self.cid = "cid"

    def connect(self):
        return True

    def me(self):
        return {"id": self.my_id, "gameName": self._me}

    def chat_id(self):
        return self.cid

    def messages(self):
        return list(self.msgs)

    def participants(self):
        return ld.chat_participant_names(self.parts) if isinstance(self.parts, list) else dict(self.parts)

    def send(self, text):
        self.sent.append(text)
        if self.echo:                    # 내가 보낸 안내문이 내 이름으로 채팅 목록에 다시 나온다
            self.msgs.append({"id": f"bot{len(self.msgs)}", "type": "chat", "body": text,
                              "fromId": self.my_id, "fromPid": "pid-1@kr.pvp.net",
                              "fromSummonerName": self._me})
        return True

    def say(self, from_id, body, name=None, **ids):
        m = {"id": f"m{len(self.msgs)}", "type": "chat", "body": body}
        if from_id:
            m["fromId"] = from_id
        if name:
            m["fromSummonerName"] = name
        m.update(ids)
        self.msgs.append(m)
        return m


def manual_runner(client, names, clk=None):
    """스레드 없이 _pump 를 직접 돌리는 실행기 — _run 이 하던 초기화만 옮겨 온다."""
    r = ld.DraftRunner(client=client, interval=0.01, names=names)
    mine = client.me()
    r._me, r._my_id = str(mine.get("gameName") or ""), str(mine.get("id") or "")
    r.engine = ld.DraftEngine(names, send=r._chat_send, now=clk or Clock())
    r.engine.start()
    r._pump()                            # 첫 폴링 = 시작 전 대화 프라임
    return r


def record_feed(runner):
    """엔진에 실제로 들어간 (발신자, 본문) 을 모은다."""
    fed = []
    orig = runner.engine.feed

    def rec(who, body):
        fed.append((who, body))
        orig(who, body)

    runner.engine.feed = rec
    return fed


def test_host_own_chat():
    parts = {f"id{i + 1}": n for i, n in enumerate(TEN)}
    c = EchoLcu(ME, "id1", parts)
    r = manual_runner(c, TEN)
    fed = record_feed(r)

    check("봇 안내문 에코(시작 전 히스토리)는 엔진에 먹이지 않음", fed == [], fed)
    check("봇이 보낸 문구는 에코를 받으면 기억에서 지운다", r._bot_sent == [], r._bot_sent)

    c.say("id1", "ㅉㅉㅉㅉ")                     # 호스트 본인이 직접 친 가위
    r._pump()
    check("호스트 본인 채팅이 엔진에 들어간다", (ME, "ㅉㅉㅉㅉ") in fed, fed)
    check("한 명만 냈으면 아직 팀장 확정 전", r.engine.phase == "rps" and not r.engine.captains)

    c.say("id2", "ㅂㅂㅂㅂ")                     # 김철수의 보 — 호스트 가위가 이긴다
    r._pump()
    check("호스트가 낸 가위도 인식돼 판정이 끝난다",
          r.engine.captains == [ME, TEN[1]] and r.engine.phase == "side",
          (r.engine.captains, r.engine.phase))

    c.say("id1", "선")                          # 호스트(승자)가 선
    r._pump()
    check("호스트가 친 '선' 인식", r.engine.phase == "color" and r.engine.seon == ME,
          (r.engine.phase, r.engine.seon))

    c.say("id1", "블루")                         # 호스트가 진영
    r._pump()
    check("호스트가 친 '블루' 인식 → 지명 시작",
          r.engine.phase == "draft" and r.engine.seon_color == "블루" and len(r.engine.roster) == 8,
          (r.engine.phase, r.engine.seon_color))

    # 지명 차례 — 호스트가 팀장이면 본인이 친 번호도 들어가야 한다
    cap = r.engine._current_captain()
    who_id = "id1" if cap == ME else [k for k, v in parts.items() if v == cap][0]
    c.say(who_id, "3")
    r._pump()
    check("지명 차례에 본인이 친 '3' 도 인식", 3 in r.engine.taken, (cap, r.engine.taken))


def test_participant_ids():
    ps = [
        {"id": "111", "pid": "pid-1@kr.pvp.net", "puuid": "pu-1-uuid", "summonerId": 111,
         "gameName": "맛동산장인유미", "gameTag": "KR1"},
        {"pid": "pid-2@kr.pvp.net", "puuid": "pu-2", "summonerId": 222, "gameName": "김철수"},
        {"id": "333", "name": "이영희"},
        {"lol": {"gameName": "박민수"}, "puuid": "pu-4"},
        {"id": "", "gameName": ""},
    ]
    m = ld.chat_participant_names(ps)
    check("id·pid·puuid·summonerId·'@' 앞까지 전부 한 닉네임으로 매핑",
          all(m.get(k) == "맛동산장인유미"
              for k in ("111", "pid-1", "pid-1@kr.pvp.net", "pu-1-uuid")), m)
    check("gameTag 가 있어도 닉네임은 gameName", m.get("pid-2") == "김철수" and m.get("pu-2") == "김철수", m)
    check("id 없이 name 만 있는 참가자도 매핑", m.get("333") == "이영희", m)
    check("lol 안에만 gameName 이 있어도 매핑", m.get("pu-4") == "박민수", m)
    check("이름 없는 참가자는 매핑하지 않음", "" not in m and len(m) >= 9, m)

    c = ld.LcuClient()
    c.cid = "cid"
    c.get = lambda path: ps               # LCU 응답을 그대로 준다
    got = ld.LcuClient.participants(c)
    check("LcuClient.participants 도 식별자 전부를 매핑",
          got.get("pu-1-uuid") == "맛동산장인유미" and got.get("pid-2@kr.pvp.net") == "김철수", got)


def test_pump_sender_ids():
    """fromPid('@' 접미사)·puuid·fromSummonerName 만 있는 LCU 메시지도 발신자를 찾는지."""
    raw = [{"id": "id1", "pid": "pid-1@kr.pvp.net", "summonerId": 111, "gameName": ME},
           {"pid": "pid-2@kr.pvp.net", "summonerId": 222, "gameName": TEN[1]},
           {"puuid": "pu-3", "summonerId": 333, "gameName": TEN[2]}]
    c = EchoLcu(ME, "id1", raw, echo=False)
    r = manual_runner(c, TEN)
    fed = record_feed(r)

    c.say(None, "바위", fromPid="pid-2@kr.pvp.net")          # fromId 없음 · '@' 접미사
    c.say(None, "가위", fromPid="pu-3")                       # fromPid 가 puuid 모양으로
    c.say(None, "보", name=TEN[3] + "#KR1")                  # 식별자 없이 fromSummonerName 만
    r._pump()
    check("fromPid('@' 포함) 로 발신자 식별", (TEN[1], "바위") in fed, fed)
    check("fromPid 가 puuid 모양이어도 발신자 식별", (TEN[2], "가위") in fed, fed)
    check("fromSummonerName 만 와도 발신자 식별(#태그 무시)", (TEN[3], "보") in fed, fed)

    # 명단에 없고 이름도 없는 줄은 버린다(디버그 로그는 한 번만)
    c.say(None, "ㅋㅋ", fromPid="pid-외부인@kr.pvp.net")
    r._pump()
    check("발신자를 못 찾는 줄은 건너뛰고 로그를 한 번만 남김",
          not [x for x in fed if x[1] == "ㅋㅋ"] and any(k.startswith("who-") for k in r._dbg_once), r._dbg_once)


def test_host_self_by_summoner_id():
    """참가자 명단에 내가 없고 fromSummonerName 도 비어 있어도 내 소환사 ID 로 내 채팅을 알아본다."""
    c = EchoLcu(ME, "111", {"id2": TEN[1]}, echo=False)
    r = manual_runner(c, TEN)
    fed = record_feed(r)
    c.say(None, "ㅉㅉㅉㅉ", fromSummonerId=111)
    r._pump()
    check("내 소환사 ID 만으로 내 채팅 인식", (ME, "ㅉㅉㅉㅉ") in fed, fed)


def test_bot_echo_filter():
    r = ld.DraftRunner(client=EchoLcu(ME, "id1", {}), names=TEN)
    r._me = ME
    r._remember_bot_text("3")
    r._remember_bot_text("3")
    check("봇이 같은 문구를 두 번 보내면 두 번까지 에코로 봄",
          (r._take_bot_echo(" 3 "), r._take_bot_echo("3"), r._take_bot_echo("3")) == (True, True, False))
    r._bot_sent[:] = [(time.monotonic() - 999.0, "2")]
    check("만료된 봇 문구는 에코로 보지 않음 — 호스트가 직접 친 같은 말은 먹인다",
          r._take_bot_echo("2") is False)


def test_compile():
    import tempfile
    tmp = tempfile.mkdtemp()
    for path in (MOD, os.path.join(ROOT, "desktop", "squad_analyzer.py"),
                 os.path.join(ROOT, "desktop", "theme_ui_test.py")):
        try:
            py_compile.compile(path, doraise=True, cfile=os.path.join(tmp, os.path.basename(path) + "c"))
            check("py_compile " + os.path.basename(path), True)
        except Exception as e:
            check("py_compile " + os.path.basename(path), False, e)


def main():
    test_parsing()
    test_engine_basics()
    test_countdown_lines()
    test_full_flow()
    test_tie_and_redeal()
    test_abbreviation_and_ambiguity()
    test_ignored_and_errors()
    test_timeout()
    test_spectators()
    test_spectator_slots_merged()
    test_probe_names_via_lcu()
    test_engine_twelve_confirmed()
    test_recommendations()
    test_lcu_shapes()
    test_host_own_chat()
    test_participant_ids()
    test_pump_sender_ids()
    test_host_self_by_summoner_id()
    test_bot_echo_filter()
    test_compile()
    print()
    if FAILS:
        print(f"❌ 실패 {len(FAILS)}건: " + ", ".join(FAILS))
        return 1
    print("✅ 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
