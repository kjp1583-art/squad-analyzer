# -*- coding: utf-8 -*-
"""🎲 내전 진행(팀뽑) 자동화 — 로비 채팅만으로 가위바위보 팀장 선정부터 1-2-2-2-1 지목 종료까지.

[2026-11-27 사장님 지시]
  "내전진행 버튼을 추가해서 팀뽑진행부터 팀뽑종료까지 진행을 자동화… 각 유저에게 번호를 부여해서
   번호로 고르거나 하는 부가기능" / "각팀장제외한 8인의 유저중에 1명을 우선적으로 내팀으로 데려오고,
   그 다음 후인 팀장이 2명, 선인 팀장이 2명 … 마지막 남은 1인을 선의 팀으로 자동 배정"

두 층으로 나뉜다.
  · DraftEngine  — 순수 로직. 네트워크·Tk 없이 names/send/now 만 주입하면 그대로 돌아간다.
                   → tests/lobby_draft_test.py 가 가짜 로비로 전체 흐름을 끝까지 검증한다.
  · LcuClient / DraftRunner — 실제 롤 클라이언트(LCU) 로비·채팅 연결과 1.2초 폴링.
                   squad_analyzer.py 상단 '내전진행' 버튼이 띄운다.

진행 순서
  ⓪ (2026-11-27 추가 지시) 방에 11~12명이 있는 경우가 있다 — 관전 슬롯(customSpectators)을 먼저 관전자로
     표시하고, 참가자가 정확히 10명이 아니면 호스트가 관전자를 체크/해제하는 선택 창으로 10명을 확정한다.
  ① 로비 채팅에 '3.. 2.. 1.. 가위바위보!' → 먼저 낸 2명이 팀장 (무승부면 그 둘만 재대결)
  ② 승자가 '선'/'후' 선택 → 선 팀장이 '블루'/'레드' 선택(진영 선택권)
  ③ 팀장 둘을 뺀 나머지에게 1..N 번호를 붙여 공지
  ④ 선1 → 후2 → 선2 → 후2 … 남은 1명은 선 팀 자동 배정 (사장님 규칙 그대로)
      · 매 차례 남은 후보 줄에 '★[빈 포지션 정글 · 전투력 1위]' 처럼 추천 사유를 붙인다
        (전투력 = 내부티어 + 내전 승률, 이미 분석기가 들고 있는 클랜 인덱스만 사용. 데이터 없는 사람은 추천 없음)
  ⑤ 최종 🔵 블루 / 🔴 레드 명단 확정 공지
"""
import hashlib
import os
import re
import threading
import time

# ─────────────────────────── 채팅 문구 해석 ───────────────────────────
#   롤 채팅은 사람마다 표기가 제각각이다 — '가위!' '묵' '✌️' '3번' '맛장유' 를 전부 받아 준다.
_VS16 = "\ufe0f\ufe0e"                                     # 이모지 변형 선택자(없애야 '✌️'=='✌')
_PUNCT = ".,!?~…·、。\"'`“”‘’《》「」『』()[]{}<>*^"
_SEP_RE = re.compile(r"[ \t\r\n\u00a0,/&+·、|;]+")


def norm_text(s):
    """비교용 문구 — 이모지 변형선택자·공백·문장부호를 없애고 소문자로."""
    t = str(s or "")
    for ch in _VS16:
        t = t.replace(ch, "")
    t = "".join(ch for ch in t if ch not in _PUNCT)
    return "".join(t.split()).lower()


def split_tokens(s):
    """한 줄을 토큰들로 — '3, 5' / '3 5' / '3/5' / '3·5' → ['3','5']."""
    t = str(s or "")
    for ch in _VS16:
        t = t.replace(ch, "")
    out = []
    for raw in _SEP_RE.split(t):
        tok = "".join(ch for ch in raw if ch not in _PUNCT)
        if tok:
            out.append(tok.lower())
    return out


def _single(s):
    """구분자가 없이 한 덩어리일 때만 그 토큰 — '선/후' 같은 문장은 선택이 아니다."""
    toks = split_tokens(s)
    return toks[0] if len(toks) == 1 else None


# ── 가위바위보 ──
RPS_HANDS = ("가위", "바위", "보")
RPS_BEATS = {"가위": "보", "바위": "가위", "보": "바위"}      # key 가 value 를 이긴다
_RPS_TOKENS = {
    "가위": "가위", "찌": "가위", "✌": "가위", "scissors": "가위", "sci": "가위",
    "바위": "바위", "묵": "바위", "주먹": "바위", "✊": "바위", "rock": "바위",
    "보": "보", "빠": "보", "보자기": "보", "손바닥": "보", "✋": "보", "paper": "보",
}


def parse_rps(body):
    """'가위'/'바위'/'보' 한 손만 인정 — '가위바위보!' 같은 카운트 문장은 손이 아니다."""
    tok = _single(body)
    return _RPS_TOKENS.get(tok) if tok else None


def rps_result(a, b):
    """a 기준 승패 — 1:a 승, -1:b 승, 0:무승부(또는 잘못된 손)."""
    if a not in RPS_BEATS or b not in RPS_BEATS or a == b:
        return 0
    return 1 if RPS_BEATS[a] == b else -1


# ── 선/후 ──
_SIDE_TOKENS = {
    "선": "선", "선픽": "선", "선뽑": "선", "선팀": "선", "먼저": "선", "first": "선",
    "후": "후", "후픽": "후", "후뽑": "후", "후팀": "후", "나중": "후", "second": "후",
}


def parse_side(body):
    tok = _single(body)
    return _SIDE_TOKENS.get(tok) if tok else None


# ── 진영 ──
_COLOR_TOKENS = {
    "블루": "블루", "블": "블루", "블루팀": "블루", "1팀": "블루", "1": "블루",
    "blue": "블루", "b": "블루", "파랑": "블루", "파": "블루",
    "레드": "레드", "레": "레드", "레드팀": "레드", "2팀": "레드", "2": "레드",
    "red": "레드", "r": "레드", "빨강": "레드", "빨": "레드",
}


def parse_color(body):
    tok = _single(body)
    return _COLOR_TOKENS.get(tok) if tok else None


def other_color(color):
    return "레드" if color == "블루" else "블루"


# ── 번호 ──
_NUM_RE = re.compile(r"^#?0*(\d{1,2})(?:번|번째)?$")


def as_number(token):
    """'3' · '3번' · '3.' · '#3' · '03' → 3. 아니면 None."""
    m = _NUM_RE.match(norm_text(token))
    return int(m.group(1)) if m else None


# ── 이름(줄임말) ──
def name_key(s):
    """이름 비교 키 — 공백·태그(#KR1)·대소문자 무시."""
    t = str(s or "").strip()
    if "#" in t:
        t = t.split("#")[0]
    return "".join(t.split()).lower()


def is_subsequence(needle, hay):
    """글자 순서가 유지되면 True — '맛장유' ⊂ '맛동산장인유미'."""
    it = iter(hay)
    return all(ch in it for ch in needle)


def match_names(token, names):
    """토큰 → (단계, [후보 인덱스]). 단계는 정확 → 접두 → 부분 → 글자순서 순으로 가장 강한 것만."""
    tk = name_key(token)
    if not tk:
        return None, []
    keys = [name_key(n) for n in names]
    tests = (
        ("exact", lambda k: k == tk),
        ("prefix", lambda k: k.startswith(tk)),
        ("sub", lambda k: tk in k),
        ("seq", lambda k: is_subsequence(tk, k)),
    )
    for tier, test in tests:
        hits = [i for i, k in enumerate(keys) if k and test(k)]
        if hits:
            return tier, hits
    return None, []


def resolve_pick(token, roster, taken):
    """토큰 하나 → 로스터 번호.

    roster: [(번호, 이름)] 번호 순 · taken: 이미 뽑힌 번호 집합
    반환 kind — pick(확정) / taken(이미 뽑힘) / range(번호 범위 밖) / ambiguous(후보 여럿) / none(잡담)
    """
    tk = norm_text(token)
    if not tk:
        return {"kind": "none"}
    num = as_number(tk)
    if num is not None:
        if not (1 <= num <= len(roster)):
            return {"kind": "range", "num": num}
        if num in taken:
            return {"kind": "taken", "num": num}
        return {"kind": "pick", "num": num, "by": "number"}
    tier, idxs = match_names(tk, [nm for _n, nm in roster])
    if tier is None:
        return {"kind": "none"}
    nums = [roster[i][0] for i in idxs]
    alive = [n for n in nums if n not in taken]
    if len(nums) > 1 and len(alive) != 1:            # 2명 이상 겹치면 확정하지 않는다
        return {"kind": "ambiguous", "nums": nums, "tier": tier}
    num = alive[0] if len(nums) > 1 else nums[0]     # 이미 뽑힌 사람을 빼면 1명만 남는 경우도 확정
    if num in taken:
        return {"kind": "taken", "num": num}
    return {"kind": "pick", "num": num, "by": tier}


TARGET_PLAYERS = 10                                  # 내전 5:5 — 참가 확정 인원

# ── 페이즈별 추천 (2026-11-27 사장님 추가 지시) ──
#   "팀뽑할 때 너뽑고나뽑고 하는 각 페이즈마다 그 페이즈에 가장 강한 유저를 추천 …
#    1.맛동산장인 유미 (추천) 이런 느낌? 더 고급스럽게"
#   전투력(내부티어+내전 승률) + 이번 차례 팀의 빈 포지션 보너스로 줄을 세우고,
#   후보 목록에 '★[빈 포지션 정글 · 전투력 1위]'처럼 사유를 짧게 붙인다. 데이터 없는 외부인은 추천하지 않는다.
POS_ORDER = ("탑", "정글", "미드", "원딜", "서폿")
POS_BONUS = 0.45                                     # 빈 포지션을 채우는 후보 가산(전투력 1 = 예상승률 4%p)
_POS_ALIASES = {
    "탑": "탑", "top": "탑", "정글": "정글", "jungle": "정글", "jg": "정글",
    "미드": "미드", "mid": "미드", "middle": "미드", "원딜": "원딜", "adc": "원딜",
    "bottom": "원딜", "bot": "원딜", "서폿": "서폿", "서포터": "서폿", "support": "서폿",
    "utility": "서폿", "sup": "서폿",
}


def norm_pos(p):
    """'TOP'·'MIDDLE'·'BOTTOM'·'UTILITY' 까지 탑/정글/미드/원딜/서폿 로 맞춘다."""
    t = str(p or "\u0000").strip()
    return _POS_ALIASES.get(t, _POS_ALIASES.get(t.lower(), "")) if t != "\u0000" else ""


def _stat_of(stats, name):
    if not stats:
        return None
    return stats.get(name) or stats.get(name_key(name))


def recommend_picks(candidates, stats, filled_positions=(), limit=2):
    """이번 차례 팀 기준 추천 — candidates=[(번호, 이름)], stats={이름: {'power','pos','tier','games','wr'}}.

    반환: [(번호, '빈 포지션 정글 · 전투력 1위')] — 데이터가 있는 후보 중 상위 limit 명.
    """
    filled = [norm_pos(p) for p in (filled_positions or []) if norm_pos(p)]
    empty = [p for p in POS_ORDER if p not in filled]
    have = [(num, nm, st) for num, nm in (candidates or []) if (st := _stat_of(stats, nm))]
    if not have:
        return []
    ranked = sorted(have, key=lambda x: (-float(x[2].get("power") or 0), -int(x[2].get("games") or 0)))
    power_rank = {num: i + 1 for i, (num, _nm, _st) in enumerate(ranked)}
    scored = []
    for num, nm, st in have:
        pw = float(st.get("power") or 0)
        pos = norm_pos(st.get("pos"))
        fill = pos if (pos and pos in empty) else ""
        scored.append((pw + (POS_BONUS if fill else 0.0), pw, int(st.get("games") or 0), num, nm, st, fill))
    scored.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))
    out = []
    for _score, pw, games, num, _nm, st, fill in scored[:max(1, int(limit or 1))]:
        bits = []
        if fill:
            bits.append("빈 포지션 " + fill)
        r = power_rank.get(num)
        if r == 1:
            bits.append("전투력 1위")
        elif r == 2:
            bits.append("전투력 2위")
        wr = float(st.get("wr") or 0)
        if not bits and games >= 10 and wr >= 0.6:
            bits.append(f"내전 승률 {int(round(wr * 100))}%")
        if not bits:
            t = str(st.get("tier") or "")
            bits.append(("티어 " + t) if t else f"전투력 {pw:.1f}")
        out.append((num, " · ".join(bits)))
    return out


def selection_ready(total, selected):
    """참가 확정이 가능한가 — 10명 이상 있으면 정확히 10명을 골라야 하고,
       10명이 안 되면 모인 전원으로 진행한다(그 사실은 selection_hint 가 안내한다)."""
    total, selected = int(total or 0), int(selected or 0)
    if total >= TARGET_PLAYERS:
        return selected == TARGET_PLAYERS
    return selected == total and total > 0


def selection_hint(total, selected):
    """선택 창 아래에 띄울 한 줄 — 왜 [시작]이 꺼져 있는지 바로 알 수 있게."""
    total, selected = int(total or 0), int(selected or 0)
    if total <= 0:
        return "로비에 아무도 없어요"
    if total >= TARGET_PLAYERS:
        if selected == TARGET_PLAYERS:
            return f"참가 {selected}명 — 시작할 수 있어요"
        left = selected - TARGET_PLAYERS
        if left > 0:
            return f"참가 {selected}명 — {left}명을 관전자로 체크해 주세요"
        return f"참가 {selected}명 — {TARGET_PLAYERS - selected}명을 더 참가로 체크해 주세요"
    return f"참가 {selected}/{total}명 — 10명이 안 되니 이 인원으로 시작합니다"


DRAFT_CYCLE = ("S", "H", "H", "S")                   # 선1 → 후2 → 선2 → 후2 …


def draft_order(n_players):
    """뽑기 순서 — 남는 1명은 순서에 넣지 않는다(선 팀 자동 배정). 8명 → S H H S S H H."""
    n = max(0, int(n_players or 0))
    return [DRAFT_CYCLE[i % len(DRAFT_CYCLE)] for i in range(n - 1)]


# ─────────────────────────── 엔진(순수 로직) ───────────────────────────
class DraftEngine:
    """로비 채팅 한 줄씩을 먹여 팀뽑을 진행하는 상태 기계. 네트워크·Tk 를 모른다."""

    RPS_WAIT = 25.0        # 카운트 후 2명이 낼 때까지 기다리는 시간
    RPS_TRIES = 3          # 다시 카운트하는 최대 횟수
    ASK_WAIT = 60.0        # 선/후 · 진영 선택 대기
    ASK_TRIES = 4          # 같은 질문을 다시 하는 최대 횟수
    PICK_WAIT = 75.0       # 한 차례 지목 대기
    PICK_TRIES = 5         # 같은 차례를 다시 안내하는 최대 횟수(넘으면 중단)

    def __init__(self, names, send=None, now=None, stats=None):
        self.names = [str(n).strip() for n in (names or []) if str(n or "").strip()]
        self.stats = stats or {}          # {이름: {'power','pos','tier','games','wr'}} — 분석기가 넣어 준다
        self._by_key = {}
        for n in self.names:
            self._by_key.setdefault(name_key(n), n)
        self._send = send if callable(send) else (lambda _t: None)
        self.now = now or time.monotonic
        self.sent = []          # 이 엔진이 로비에 보낸 말들(테스트·UI 공용)
        self.lines = []         # 진행 로그(최근 것만 유지)
        self.phase = "idle"
        self.reason = ""
        # 진행 상태
        self.captains = []      # [승자, 패자] — 가위바위보를 낸 순서가 아니라 판정 결과 순서
        self.winner = ""
        self.loser = ""
        self.seon = ""
        self.hu = ""
        self.seon_color = ""
        self.roster = []        # [(번호, 이름)] — 팀장 둘 제외
        self.order = []         # ['S','H','H',...] 뽑는 순서
        self.turn = 0
        self.taken = set()
        self.teams = {"블루": [], "레드": []}
        self.rps_round = []     # 이번 판정에서 던진 [(이름, 손)]
        self.tie_pair = []      # 무승부 재대결 대상
        self.tries = 0
        self.ask_tries = 0
        self.pick_tries = 0
        self.deadline = 0.0
        self._noticed = set()

    # ── 바깥으로 말하기 ──
    def says(self, text):
        text = str(text)
        self.sent.append(text)
        self.lines.append(text)
        if len(self.lines) > 300:
            del self.lines[:-300]
        try:
            self._send(text)
        except Exception:
            pass

    def _notice_once(self, key, text):
        if key in self._noticed:
            return
        self._noticed.add(key)
        self.says(text)

    # ── 시작 ──
    def start(self):
        if not self.names:
            self.abort("로비 인원을 읽지 못했어요")
            return self
        self.phase = "rps"
        self.tries = 0
        self.rps_round = []
        self.tie_pair = []
        self._countdown("🎲 팀장 가위바위보! 3.. 2.. 1.. 가위바위보! (먼저 내는 2명이 팀장)")
        return self

    def _countdown(self, text):
        self.tries += 1
        self.deadline = self.now() + self.RPS_WAIT
        self.says(text)

    def abort(self, reason="중단"):
        self.reason = str(reason)
        if self.phase not in ("done", "aborted"):
            self.phase = "aborted"
            self.says("⛔ 내전진행 중단 — " + str(reason))

    # ── 채팅 한 줄 ──
    def feed(self, who, body):
        if self.phase in ("idle", "done", "aborted"):
            return
        name = self._resolve(who)
        if not name:
            return                                   # 로비 인원이 아니면(관전자·외부) 무시
        if self.phase == "rps":
            self._feed_rps(name, body)
        elif self.phase == "side":
            self._feed_side(name, body)
        elif self.phase == "color":
            self._feed_color(name, body)
        elif self.phase == "draft":
            self._feed_draft(name, body)

    def _resolve(self, who):
        k = name_key(who)
        if k in self._by_key:
            return self._by_key[k]
        tier, idxs = match_names(k, self.names)
        return self.names[idxs[0]] if tier == "exact" and len(idxs) == 1 else ""

    # ── ① 가위바위보 ──
    def _feed_rps(self, name, body):
        hand = parse_rps(body)
        if not hand:
            return
        if self.tie_pair and name not in self.tie_pair:
            return                                   # 재대결은 두 팀장만
        if any(n == name for n, _h in self.rps_round):
            return                                   # 한 판정에서 한 번만 센다
        self.rps_round.append((name, hand))
        if len(self.rps_round) < 2:
            return
        (na, ha), (nb, hb) = self.rps_round
        res = rps_result(ha, hb)
        if res == 0:
            self.tie_pair = [na, nb]
            self.rps_round = []
            self.tries = 0
            self._countdown(f"🤝 무승부! {na} · {nb} 한 번 더 — 3.. 2.. 1.. 가위바위보!")
            return
        win, lose = (na, nb) if res > 0 else (nb, na)
        self.captains = [win, lose]
        self.winner, self.loser = win, lose
        self.tie_pair = []
        self.says(f"👑 팀장 확정 — {win}(승) · {lose}  ({ha} vs {hb})")
        self.phase = "side"
        self.ask_tries = 0
        self.deadline = self.now() + self.ASK_WAIT
        self.says(f"➡️ {win}님 — '선' 또는 '후' 를 채팅으로 골라주세요 (선 = 먼저 지명 + 진영 선택권)")

    # ── ② 선/후 ──
    def _feed_side(self, name, body):
        pick = parse_side(body)
        if not pick:
            return
        if name != self.winner:
            self._notice_once(("side", name), f"🙋 {name}님 — 이번 선택은 가위바위보 승자 {self.winner}님이 해주세요")
            return
        if pick == "선":
            self.seon, self.hu = self.winner, self.loser
        else:
            self.seon, self.hu = self.loser, self.winner
        self.says(f"📌 선: {self.seon} (지명 먼저 + 진영 선택) · 후: {self.hu}")
        self.phase = "color"
        self.ask_tries = 0
        self.deadline = self.now() + self.ASK_WAIT
        self.says(f"🚩 {self.seon}님 — 진영을 골라주세요: '블루' / '레드'")

    # ── ③ 진영 → 번호 부여 ──
    def _feed_color(self, name, body):
        color = parse_color(body)
        if not color:
            return
        if name != self.seon:
            self._notice_once(("color", name), f"🙋 {name}님 — 진영은 선({self.seon})이 고릅니다")
            return
        self.seon_color = color
        opp = other_color(color)
        self.teams = {color: [self.seon], opp: [self.hu]}
        self.says(f"🔵 블루: {self.seon}(팀장) · 🔴 레드: {self.hu}(팀장)" if color == "블루"
                  else f"🔵 블루: {self.hu}(팀장) · 🔴 레드: {self.seon}(팀장)")
        self._begin_draft()

    def _begin_draft(self):
        others = [n for n in self.names if n not in (self.seon, self.hu)]
        self.roster = [(i + 1, n) for i, n in enumerate(others)]
        self.order = draft_order(len(self.roster))
        self.turn = 0
        self.taken = set()
        self.phase = "draft"
        if not self.roster:
            self._finish()
            return
        self.says(f"📋 팀장 제외 {len(self.roster)}명 번호 — "
                  + " · ".join(f"{n}.{nm}" for n, nm in self.roster))
        self._announce_turn()

    # ── ④ 지목 ──
    def _feed_draft(self, name, body):
        cap = self._current_captain()
        if not cap or name != cap:
            return                                   # 차례가 아닌 사람의 채팅은 조용히 무시
        toks = split_tokens(body)
        if not toks:
            return
        run = self._run_len()
        picks, msgs = [], []
        took = set(self.taken)
        for tok in toks:
            r = resolve_pick(tok, self.roster, took)
            kind = r.get("kind")
            if kind == "pick":
                if len(picks) >= run:
                    msgs.append(f"✋ 이번엔 {run}명까지예요 — 남은 번호는 다음 차례에 골라주세요")
                    break
                picks.append(r["num"])
                took.add(r["num"])
            elif kind == "ambiguous":
                cand = [n for n in r.get("nums") or [] if n not in took]
                msgs.append(f"❓ '{tok}' 후보가 {len(cand)}명이에요 — "
                            + ", ".join(f"{n}번" for n in sorted(cand)) + " 중에서 번호로 다시 골라주세요")
            elif kind == "taken":
                msgs.append(f"🚫 {r['num']}번은 이미 뽑혔어요")
            elif kind == "range":
                msgs.append(f"❓ {r['num']}번은 없어요 — 1~{len(self.roster)}번 사이로 골라주세요")
        for m in dict.fromkeys(msgs):
            self.says(m)
        for num in picks:
            self._assign(num)
            if self.phase != "draft":
                return
        if picks:
            return
        if not msgs and any(as_number(t) is not None for t in toks):
            self._announce_turn()                    # 못 알아들었으면 남은 번호를 다시 보여 준다

    def _assign(self, num):
        side = self._current_side()
        color = self._color_of(side)
        name = dict(self.roster)[num]
        self.teams.setdefault(color, []).append(name)
        self.taken.add(num)
        self.turn += 1
        self.says(f"✅ {color} ← {num}. {name}  ({len(self.teams[color])}명)")
        if self.turn >= len(self.order):
            self._finish()
        else:
            self._announce_turn()

    def _filled_positions(self, color):
        """그 팀에 이미 앉은 사람들의 주포지션 — 빈 자리를 알아 추천에 쓴다."""
        out = []
        for nm in (self.teams.get(color) or []):
            st = _stat_of(self.stats, nm)
            if st and st.get("pos"):
                out.append(st["pos"])
        return out

    def _turn_recommendation(self, left):
        """이번 차례 추천 — {번호: '빈 포지션 정글 · 전투력 1위'}. 데이터 있는 후보만."""
        if not self.stats or not left:
            return {}
        color = self._color_of(self._current_side())
        recs = recommend_picks(left, self.stats, self._filled_positions(color),
                               limit=min(self._run_len() or 1, 2))
        return {num: why for num, why in recs}

    def _announce_turn(self, remind=False):
        side = self._current_side()
        if not side:
            self._finish()
            return
        cap = self._current_captain()
        color = self._color_of(side)
        icon = "🔵" if color == "블루" else "🔴"
        left = [(n, nm) for n, nm in self.roster if n not in self.taken]
        self.deadline = self.now() + self.PICK_WAIT
        if not remind:
            self.pick_tries = 0                   # 새 차례 — 다시 안내 횟수 초기화
        recs = self._turn_recommendation(left)
        items = [f"{n}.{nm}" + (f" ★[{recs[n]}]" if n in recs else "") for n, nm in left]
        head = ("⏳ " if remind else "") + f"{icon} {color} · {cap} 차례"
        line = head + " — " + " · ".join(items) + "  (번호나 이름으로)"
        if len(line) <= 220:
            self.says(line)
            return
        # 너무 길면 번호만 먼저, 추천은 다음 줄에 — 롤 채방 한 줄이 잘리지 않게
        self.says(f"{head} — 남은 번호 {', '.join(str(n) for n, _nm in left)} (번호나 이름으로)")
        if recs:
            self.says("★추천 — " + " · ".join(f"{n}.{nm}[{recs[n]}]" for n, nm in left if n in recs))

    def _finish(self):
        if self.phase == "done":
            return
        left = [(n, nm) for n, nm in self.roster if n not in self.taken]
        for num, nm in left:                         # 마지막 남은 1명은 선 팀으로 자동 배정
            self.teams.setdefault(self.seon_color, []).append(nm)
            self.taken.add(num)
            self.says(f"🎁 남은 {num}. {nm} → {self.seon_color}(선) 자동 배정")
        self.turn = max(self.turn, len(self.order))
        self.phase = "done"
        b = self.teams.get("블루") or []
        r = self.teams.get("레드") or []
        self.says("🏁 팀뽑 종료!")
        self.says(f"🔵 블루 ({len(b)}명): " + " · ".join(b))
        self.says(f"🔴 레드 ({len(r)}명): " + " · ".join(r))
        self.says("각자 로비에서 자기 진영 칸을 눌러 이동해 주세요.")

    # ── 시간 초과 ──
    def tick(self):
        if self.phase in ("idle", "done", "aborted"):
            return
        if self.now() < self.deadline:
            return
        if self.phase == "rps":
            if self.tries >= self.RPS_TRIES:
                self.abort("가위바위보 참가자가 모자라요")
                return
            got = [n for n, _h in self.rps_round]
            left = 2 - len(got)
            self._countdown(("⏳ 아직 " + str(left) + "명! " + "·".join(got)
                             + " 기다릴게요 — 3.. 2.. 1.. 가위바위보!") if got
                            else "⏳ 아직 2명! 3.. 2.. 1.. 가위바위보!")
        elif self.phase in ("side", "color"):
            self.ask_tries += 1
            if self.ask_tries > self.ASK_TRIES:
                self.abort("선택 응답이 없어서")
                return
            self.deadline = self.now() + self.ASK_WAIT
            if self.phase == "side":
                self.says(f"⏳ {self.winner}님 — '선' 또는 '후' 를 채팅으로 골라주세요")
            else:
                self.says(f"⏳ {self.seon}님 — '블루' 또는 '레드' 를 채팅으로 골라주세요")
        elif self.phase == "draft":
            self.pick_tries += 1
            if self.pick_tries > self.PICK_TRIES:
                self.abort("지명 응답이 없어서")
                return
            self._announce_turn(remind=True)

    # ── 조회 ──
    def _current_side(self):
        return self.order[self.turn] if self.turn < len(self.order) else ""

    def _current_captain(self):
        side = self._current_side()
        return self.seon if side == "S" else (self.hu if side == "H" else "")

    def _color_of(self, side):
        if side == "S":
            return self.seon_color or "블루"
        return other_color(self.seon_color or "블루")

    def _run_len(self):
        side = self._current_side()
        if not side:
            return 0
        n = 0
        for i in range(self.turn, len(self.order)):
            if self.order[i] != side:
                break
            n += 1
        return n

    def headline(self):
        if self.phase == "rps":
            return "✊ 팀장 가위바위보"
        if self.phase == "side":
            return f"➡️ {self.winner} 선/후 선택"
        if self.phase == "color":
            return f"🚩 {self.seon} 진영 선택"
        if self.phase == "draft":
            color = self._color_of(self._current_side())
            icon = "🔵" if color == "블루" else "🔴"
            return f"{icon} {color} 지목 {self.turn + 1}/{len(self.order)}"
        if self.phase == "done":
            return "🏁 팀뽑 종료"
        if self.phase == "aborted":
            return "⛔ 중단됨"
        return "대기"


# ─────────────────────────── LCU 연결 ───────────────────────────
LOL_PATHS = [r"C:\Riot Games\League of Legends"]


def find_lockfile():
    """롤 lockfile 경로 — 설치 드라이브가 C:가 아니어도 찾는다(분석기 본체와 같은 규칙)."""
    env = os.environ.get("LOBBY_DRAFT_LOCKFILE")
    if env and os.path.exists(env):
        return env
    candidates = []
    try:
        import json
        meta = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                            "Riot Games", "RiotClientInstalls.json")
        if os.path.exists(meta):
            with open(meta, "r", encoding="utf-8") as f:
                candidates += [os.path.normpath(k) for k in (json.load(f).get("associated_client") or {})]
    except Exception:
        pass
    candidates += LOL_PATHS + [f"{d}:\\Riot Games\\League of Legends" for d in "CDEFG"]
    seen = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        lf = os.path.join(base, "lockfile")
        if os.path.exists(lf):
            return lf
    return ""


def _creds_from_lockfile(path):
    """lockfile(name:pid:port:password:protocol) → (base_url, headers)."""
    import base64
    with open(path, "r", encoding="utf-8") as f:
        parts = f.read().strip().split(":")
    if len(parts) < 4:
        return None
    port, pw = parts[2], parts[3]
    tok = base64.b64encode(("riot:" + pw).encode()).decode()
    return (f"https://127.0.0.1:{port}",
            {"Authorization": "Basic " + tok, "Accept": "application/json",
             "Content-Type": "application/json"})


# 멤버 dict 에서 닉네임이 들어오는 자리들 — LCU 응답마다 어느 칸에 들어오는지가 다르다.
NAME_FIELDS = ("gameName", "summonerName", "displayName", "summonerInternalName")


def _slot_name(d):
    """로비 인원/슬롯 dict → 닉네임(태그 제외). gameName 이 비어 있어도 displayName·summonerName 을 본다."""
    if not isinstance(d, dict):
        return ""
    for k in NAME_FIELDS:
        v = d.get(k)
        if v:
            nm = str(v).split("#")[0].strip()
            if nm:
                return nm
    return ""


def _id_str(v):
    """puuid/summonerId 를 문자열로 — 빈 슬롯이 0/None 으로 오는 것을 빈 값으로 본다."""
    t = str(v if v is not None else "").strip()
    return "" if t.lower() in ("", "0", "none", "null") else t


def _slot_id_keys(s):
    """dict 하나에서 puuid·summonerId·게임닉 키를 뽑는다(소문자)."""
    keys = set()
    for k in ("puuid", "summonerId"):
        v = _id_str(s.get(k))
        if v:
            keys.add(v.lower())
    nm = _slot_name(s)
    if nm:
        keys.add(name_key(nm))
    return keys


def _spec_keys(game_config):
    """gameConfig.customSpectators → 관전자 식별 키 집합(puuid·summonerId·게임닉)."""
    keys = set()
    for s in (game_config.get("customSpectators") or []):
        if isinstance(s, dict):
            keys |= _slot_id_keys(s)
        elif s:
            keys.add(str(s).lower())
    return keys


def _team_keys(game_config):
    """customTeam100/200 에 앉아 있는 사람 — 표시가 엇갈려도 참가자로 확정한다."""
    keys = set()
    for slot in ("customTeam100", "customTeam200"):
        for s in (game_config.get(slot) or []):
            if isinstance(s, dict):
                keys |= _slot_id_keys(s)
            elif s:
                keys.add(str(s).lower())
    return keys


def _slot_entries(game_config):
    """gameConfig 의 팀·관전 슬롯 → [(dict, 'team'|'spec')] — members 에 빠져 있어도 살리기 위한 목록.

    문자열로만 오는 슬롯은 puuid 와 닉네임을 구분할 수 없어 raw 로 넘긴다(양쪽 키로 맞춰 본다).
    """
    out = []
    for slot, place in (("customTeam100", "team"), ("customTeam200", "team"),
                        ("customSpectators", "spec")):
        for s in (game_config.get(slot) or []):
            if isinstance(s, dict):
                out.append((s, place))
            elif s:
                tok = str(s).strip()
                if tok:
                    out.append(({"_raw": tok}, place))
    return out


def classify_members(lobby):
    """로비 응답 → [{'name','key','spectator','puuid','summonerId'}] — members + 팀·관전 슬롯을 모두 합친다.

    11~12명 방에서 '누가 관전자인지'를 미리 표시해 주는 것이 목적이라, 확실한 신호가 없으면
    참가자로 둔다(관전자를 참가자로 잘못 볼지언정, 참가자를 관전자로 몰지 않는다 — 호스트가 창에서 고친다).

    2026-11-28 사장님 제보(관전자 슬롯 인원이 목록에 안 떠서 시작 불가):
      실제 `/lol-lobby/v2/lobby` 는 관전 슬롯(`customSpectators`) 인원을 members 에 넣지 않거나,
      gameName 이 비고 puuid/summonerId·displayName 만 넣어 준다. 그래서 members 만 돌면 그 사람이
      통째로 빠져 인원이 모자라고 관전자 체크도 할 수 없었다 → 멤버·팀·관전 슬롯을 puuid·summonerId·
      닉네임 기준으로 하나로 합친다. 이름이 아직 비면 probe_lobby 가 LCU 소환사 조회로 채운다.
    """
    lobby = lobby or {}
    gc = lobby.get("gameConfig") or {}
    spec, team = _spec_keys(gc), _team_keys(gc)
    rows, index = [], {}          # index: 'pu:…' / 'sid:…' / 'n:…' → row (같은 사람을 한 줄로 합치기)

    def _keys(pu, sid, key, raw):
        ks = []
        for k in (("pu:" + pu) if pu else "", ("sid:" + sid) if sid else "",
                  ("n:" + key) if key else "", ("pu:" + raw) if raw else "",
                  ("n:" + raw) if raw else ""):
            if k and k not in ks:
                ks.append(k)
        return ks

    def _merge(pu="", sid="", name="", raw="", spec_hint=False, team_hint=False):
        push = str(pu or "").lower()
        sid = str(sid or "").lower()
        raw = str(raw or "").strip().lower()
        name = str(name or "").strip()
        key = name_key(name) if name else ""
        row = None
        for k in _keys(push, sid, key, raw):
            if k in index:
                row = index[k]
                break
        if row is None:
            row = {"name": "", "key": "", "spectator": False, "puuid": "", "summonerId": "",
                   "raw": "", "_spec": False, "_team": False}
            rows.append(row)
        if name and not row["name"]:
            row["name"], row["key"] = name, key          # 한쪽에만 이름이 있으면 그 이름을 살린다
        if push and not row["puuid"]:
            row["puuid"] = push
        if sid and not row["summonerId"]:
            row["summonerId"] = sid
        if raw and not row["raw"]:
            row["raw"] = raw
        row["_spec"] = row["_spec"] or bool(spec_hint)
        row["_team"] = row["_team"] or bool(team_hint)
        for k in _keys(row["puuid"], row["summonerId"], row["key"], row["raw"]):
            index[k] = row
        return row

    for m in (lobby.get("members") or []):
        if not isinstance(m, dict):
            continue
        pu = _id_str(m.get("puuid"))
        sid = _id_str(m.get("summonerId"))
        nm = _slot_name(m)
        key = name_key(nm) if nm else ""
        spec_flag = (str(m.get("isSpectator", "")).lower() == "true"
                     or str(m.get("role", "")).upper() == "SPECTATOR"
                     or str(m.get("teamId", "")).strip() == "-1"
                     or (pu and pu.lower() in spec) or (sid and sid.lower() in spec)
                     or (key and key in spec))
        in_team = bool((pu and pu.lower() in team) or (sid and sid.lower() in team)
                       or (key and key in team))
        _merge(pu=pu, sid=sid, name=nm, spec_hint=bool(spec_flag and not in_team), team_hint=in_team)

    for rec, place in _slot_entries(gc):
        pu = _id_str(rec.get("puuid"))
        sid = _id_str(rec.get("summonerId"))
        nm = _slot_name(rec)
        if not (pu or sid or nm):
            tok = str(rec.get("_raw") or "").strip()
            if not tok:
                continue
            low = tok.lower()
            if ("pu:" + low) in index or ("sid:" + low) in index:
                pu = tok
            elif ("n:" + name_key(tok)) in index or len(low) < 24:
                nm = tok                       # 닉네임으로 본다
            else:
                pu = tok                       # puuid 모양(36자 UUID)으로 본다
        _merge(pu=pu, sid=sid, name=nm,
               spec_hint=(place == "spec"), team_hint=(place == "team"))

    out = []
    for r in rows:
        if r["_team"]:
            r["spectator"] = False             # 팀 슬롯에 앉아 있으면 참가자
        else:
            r["spectator"] = bool(r["_spec"])
        out.append({"name": r["name"], "key": r["key"], "spectator": r["spectator"],
                    "puuid": r["puuid"], "summonerId": r["summonerId"]})
    return out


def default_selection(rows):
    """선택 창의 기본값 — 관전 슬롯으로 보이는 사람만 빼 둔 참가자 이름들(이름 미확인 행은 뺀다)."""
    return [r["name"] for r in (rows or [])
            if not r.get("spectator") and str(r.get("name") or "").strip()]


def _resolve_names(client, rows):
    """이름이 빈 행(puuid/summonerId 만 온 사람)을 LCU 소환사 조회·로비 채팅으로 채운다."""
    blank = [r for r in rows if not str(r.get("name") or "").strip()]
    if not blank:
        return rows
    parts = {}
    try:
        if not getattr(client, "cid", ""):
            client.chat_id()
        parts = client.participants() or {}
    except Exception:
        parts = {}
    for r in blank:
        pu, sid = _id_str(r.get("puuid")), _id_str(r.get("summonerId"))
        nm = ""
        for path in ((f"/lol-summoner/v2/summoners/puuid/{pu}" if pu else ""),
                     (f"/lol-summoner/v1/summoners/{sid}" if sid else "")):
            if not path:
                continue
            try:
                nm = _slot_name(client.get(path) or {})
            except Exception:
                nm = ""
            if nm:
                break
        if not nm and sid:
            nm = _slot_name({"gameName": parts.get(sid) or parts.get(sid.lower()) or ""})
        if nm:
            r["name"], r["key"] = nm, name_key(nm)
    return rows


def probe_lobby(client=None):
    """내전진행을 누른 직후 로비를 읽어 온다 — {'ok','error','rows','candidates'}."""
    c = client or LcuClient()
    try:
        if not c.connect():
            return {"ok": False, "rows": [], "candidates": [],
                    "error": "롤 클라이언트를 찾지 못했어요 — 롤을 켜고 커스텀 로비에 들어간 뒤 다시 눌러 주세요."}
        lobby = c.lobby()
        if not lobby:
            return {"ok": False, "rows": [], "candidates": [],
                    "error": "로비 정보를 읽지 못했어요 — 커스텀 게임 방에 들어가 있는지 확인해 주세요."}
        rows = _resolve_names(c, classify_members(lobby))
        for r in rows:                                    # 끝내 이름을 못 얻어도 목록에서 빼지 않는다
            if not str(r.get("name") or "").strip():
                tail = str(r.get("summonerId") or r.get("puuid") or "")[:6]
                r["name"] = "이름 미확인" + (f"({tail})" if tail else "")
                r["key"] = ""
                r["unknown"] = True
        if not rows:
            return {"ok": False, "rows": [], "candidates": [], "error": "로비 인원을 읽지 못했어요."}
        return {"ok": True, "error": "", "rows": rows, "candidates": default_selection(rows)}
    except Exception as e:
        return {"ok": False, "rows": [], "candidates": [], "error": f"{type(e).__name__}: {e}"}


class LcuClient:
    """롤 클라이언트(LCU) 로비·채팅 — 분석기 본체가 쓰는 경로와 같은 것만 쓴다."""

    def __init__(self, lockfile=None, timeout=2.5, http=None):
        self.lockfile = lockfile
        self.timeout = timeout
        self._http = http
        self.base = ""
        self.headers = {}
        self.lobby_key = ""
        self.cid = ""
        self.my_id = ""

    # ── 저수준 ──
    def _requests(self):
        if self._http is None:
            import requests
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
            self._http = requests
        return self._http

    def connect(self):
        lf = self.lockfile or find_lockfile()
        if not lf or not os.path.exists(lf):
            return False
        got = _creds_from_lockfile(lf)
        if not got:
            return False
        self.base, self.headers = got
        return True

    def get(self, path):
        r = self._requests().get(self.base + path, headers=self.headers, verify=False,
                                 timeout=self.timeout)
        return r.json() if r.status_code == 200 else None

    def post(self, path, obj):
        r = self._requests().post(self.base + path, headers=self.headers, json=obj,
                                  verify=False, timeout=self.timeout)
        return r.status_code < 400

    # ── 로비/채팅 ──
    def lobby(self):
        return self.get("/lol-lobby/v2/lobby") or {}

    def members(self):
        """로비 인원 전체(관전자 포함) — [{'name','key','spectator'}]."""
        return classify_members(self.lobby())

    def players(self):
        """관전 슬롯에 없는 인원 — [{'name','key'}]."""
        return [m for m in self.members() if not m.get("spectator")]

    def me(self):
        j = self.get("/lol-summoner/v1/current-summoner") or {}
        self.my_id = str(j.get("summonerId") or "")
        return {"id": self.my_id, "gameName": str(j.get("gameName") or j.get("displayName") or "")}

    def chat_id(self):
        """로비 채팅방 — 방 채팅 ID(multiUserChatId)가 들어간 대화 우선, 없으면 customGame/lobby."""
        self.lobby_key = str((self.lobby() or {}).get("multiUserChatId") or "")
        convs = self.get("/lol-chat/v1/conversations") or []
        convs = [c for c in convs if isinstance(c, dict)]
        key = self.lobby_key.split("@")[0].lower()
        for c in convs:
            if key and key in str(c.get("id", "")).lower():
                self.cid = str(c.get("id"))
                return self.cid
        for c in convs:
            if str(c.get("type")) in ("customGame", "lobby"):
                self.cid = str(c.get("id"))
                return self.cid
        return ""

    def messages(self):
        if not self.cid:
            return None
        ms = self.get("/lol-chat/v1/conversations/" + self.cid + "/messages")
        return ms if isinstance(ms, list) else None

    def participants(self):
        """fromId(summonerId) → 게임닉."""
        out = {}
        if not self.cid:
            return out
        ps = self.get("/lol-chat/v1/conversations/" + self.cid + "/participants") or []
        for p in ps:
            if isinstance(p, dict) and p.get("id"):
                out[str(p["id"])] = str(p.get("gameName") or p.get("name") or "")
        return out

    def send(self, text):
        if not self.cid and not self.chat_id():
            return False
        return self.post("/lol-chat/v1/conversations/" + self.cid + "/messages",
                         {"body": str(text), "type": "chat"})


# ─────────────────────────── 실행 스레드 ───────────────────────────
class DraftRunner:
    """실제 로비에서 엔진을 돌린다 — 1.2초마다 로비 채팅을 훑어 엔진에 먹이고, 끝나면 스스로 멈춘다."""

    INTERVAL = 1.2

    def __init__(self, client=None, interval=None, engine_factory=None, names=None,
                 stats=None, stats_factory=None):
        self.client = client or LcuClient()
        self.interval = float(interval or self.INTERVAL)
        self.engine_factory = engine_factory or DraftEngine
        self.engine = None
        self.confirmed = [str(n) for n in (names or []) if str(n or "").strip()]   # 호스트가 확정한 참가자
        self.stats = stats or {}           # 페이즈별 추천용 데이터(분석기가 주입)
        self.stats_factory = stats_factory  # 스레드 안에서 만드는 게 낫다(시트 조회가 느릴 수 있음)
        self.error = ""
        self.phase = "starting"
        self._stop = threading.Event()
        self._th = None
        self._seen = set()
        self._ids = {}
        self._tick_no = 0
        self._primed = False
        self._me = ""
        self._names = []
        self.started_at = time.time()

    # ── 밖에서 쓰는 것 ──
    def start(self):
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()
        return self

    def alive(self):
        return bool(self._th and self._th.is_alive())

    def stop(self):
        self._stop.set()

    def abort(self, reason="사용자가 중단"):
        try:
            if self.engine and self.engine.phase not in ("done", "aborted"):
                self.engine.abort(reason)
        except Exception:
            pass
        self._stop.set()

    def status(self):
        e = self.engine
        if self.error:
            phase = "error"
        elif e is not None:
            phase = e.phase                      # 화면에는 엔진의 단계(rps/side/color/draft/done)를 보여 준다
        else:
            phase = "starting"
        return {
            "phase": phase,
            "error": self.error,
            "alive": self.alive(),
            "headline": e.headline() if e else "",
            "teams": {k: list(v) for k, v in (e.teams if e else {}).items()},
            "remaining": ([f"{n}. {nm}" for n, nm in e.roster if n not in e.taken] if e else []),
            "lines": list(e.lines) if e else [],
            "members": list(e.names) if e else [],
        }

    # ── 스레드 본체 ──
    def _run(self):
        try:
            c = self.client
            if not c.connect():
                self.error = "롤 클라이언트를 찾지 못했어요 — 롤을 켜고 커스텀 로비에 들어간 뒤 다시 눌러 주세요."
                self.phase = "error"
                return
            if self.confirmed:
                names = list(self.confirmed)          # 호스트가 선택 창에서 확정한 참가자 그대로
            else:
                names = [m["name"] for m in c.players() if m.get("name")]   # 관전 슬롯 제외
            if len(names) < 3:
                self.error = (f"참가자가 {len(names)}명이에요 — 팀장 2명 + 1명, 최소 3명이 있어야 시작할 수 있어요."
                              if names else "커스텀 로비에 들어가 있는지 확인해 주세요.")
                self.phase = "error"
                return
            self._names = names
            self._me = (c.me() or {}).get("gameName") or ""
            if not self.stats and self.stats_factory:
                try:
                    self.stats = self.stats_factory(names) or {}
                except Exception as e:
                    print(f"[lobby-draft] 추천 데이터를 못 만들었습니다(추천 없이 진행): {type(e).__name__}", flush=True)
                    self.stats = {}
            try:
                self.engine = self.engine_factory(names, send=self._chat_send, stats=self.stats)
            except TypeError:
                self.engine = self.engine_factory(names, send=self._chat_send)
            self.phase = "running"
            self.engine.start()
            while not self._stop.is_set():
                self._pump()
                self.engine.tick()
                if self.engine.phase in ("done", "aborted"):
                    break
                time.sleep(self.interval)
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.phase = "error"
        finally:
            if self.engine is not None and self.phase != "error":
                self.phase = self.engine.phase
            self._stop.set()

    def _chat_send(self, text):
        try:
            if not self.client.send(text):
                print(f"[lobby-draft] 채팅 발송 실패: {text[:40]}", flush=True)
        except Exception as e:
            print(f"[lobby-draft] 채팅 발송 예외: {type(e).__name__}", flush=True)

    def _pump(self):
        c = self.client
        if not c.cid:
            c.chat_id()
        msgs = c.messages()
        if msgs is None:
            return
        self._tick_no += 1
        if not self._ids or self._tick_no % 5 == 1:   # 참가자 id→닉은 5회마다 갱신(이름 변경 대비)
            try:
                self._ids = c.participants()
            except Exception:
                pass
        ids = self._ids
        cur = set()
        for m in msgs:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "")
            if not mid:
                mid = hashlib.md5((str(m.get("timestamp")) + "|" + str(m.get("fromId")) + "|"
                                   + str(m.get("body"))).encode()).hexdigest()
            cur.add(mid)
            if mid in self._seen:
                continue
            self._seen.add(mid)
            if not self._primed:
                continue                          # 시작 전에 쌓여 있던 대화는 먹이지 않는다
            if str(m.get("type") or "chat") not in ("chat", ""):
                continue
            fid = str(m.get("fromId") or "")
            who = (ids.get(fid)
                   or str(m.get("fromSummonerName") or "").split("#")[0]).strip()
            body = str(m.get("body") or "").strip()
            if not who or not body:
                continue
            if name_key(who) == name_key(self._me):
                continue                          # 내가 보낸 안내문은 다시 먹지 않는다
            self.engine.feed(who, body)
        if not self._primed:
            self._primed = True
        if cur:
            self._seen &= cur                     # 롤이 오래된 줄을 지우면 우리 기록도 같이 정리


# ── 프로세스 하나에 하나만 — 버튼을 두 번 눌러도 진행이 겹치지 않는다 ──
RUNNER = {"r": None}


def current_runner():
    return RUNNER["r"]


def start_runner(client=None, names=None, stats=None, stats_factory=None):
    r = RUNNER["r"]
    if r is not None and r.alive():
        return r
    r = DraftRunner(client=client, names=names, stats=stats, stats_factory=stats_factory)
    RUNNER["r"] = r
    return r.start()
