# -*- coding: utf-8 -*-
"""🛡️ [2026-11-27 사장님 지시] 밴픽창에서 '내가 고른 챔피언'의 lol.ps 빌드(아이템·룬·스펠) 카드.

무엇을 하나
  - 챔피언이 정해지면 lol.ps 의 챔피언 페이지 데이터를 읽어 1코어·2~3코어 후보, 핵심 룬/보조 룬,
    스펠, 승률·픽률·표본을 뽑는다.
  - 뽑은 값을 Pillow 로 '컴팩트 빌드 카드' 한 장으로 그려 항상-위 창에 띄운다(롤 클라이언트 위).
  - 픽 스왑(내 칸의 챔피언이 바뀜)은 부르는 쪽(squad_analyzer)이 폴링마다 넘겨주는 championId 로
    감지한다 — 이 모듈은 '지금 대상이 바뀌었나'만 보고 새 빌드로 갈아탄다.

데이터 경로 (브라우저 없이 평문 JSON)
  https://lol.ps/champ/{championId}/__data.json?tier=2&region=0&lane={lane}
  - lane 생략 시 lol.ps 가 그 챔피언의 주 라인(top1LaneId) 데이터를 준다(포지션 미정 내전용).
  - 응답은 SvelteKit 의 devalue 디하이드레이션 payload:
        {"type":"data","nodes":[{"type":"data","data":[...],"uses":{...}}, ...]}
    nodes[i].data 는 **평평한 배열**이고 data[0] 이 그 노드의 루트 값이다. 컨테이너(객체/배열) 안의
    정수는 같은 배열의 인덱스 참조이고, 문자열·숫자 같은 원시값은 그 자리에 그대로 들어 있다.
    (예: data[0] = {"championId": 1, "champSummary": 2, ...} → data[1]=89, data[2]=[{...}, ...])
  - 챔피언 페이지 노드는 champSummary 키를 가진 루트이고, 공용 레이아웃 노드에 versionInfo(패치 목록)가 있다.

설계 원칙
  - UI 스레드를 절대 막지 않는다: 네트워크는 전용 워커 1개, 렌더도 별도 스레드, GUI 는 완성된 이미지만 받는다.
  - lol.ps 가 느리거나 죽어도 조용히 아무 일도 일어나지 않는다(분석기 본체 기능 무영향).
  - (championId, lane) TTL 캐시 + 최대 개수 제한 — 밴픽 몇 판을 돌려도 메모리가 늘지 않는다.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, replace
from queue import Empty, Queue

try:                                      # 앱에는 항상 있다(다른 기능이 이미 사용). 테스트 환경 폴백용.
    import requests
except Exception:                         # pragma: no cover - requests 없는 환경
    requests = None

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except Exception:                         # pragma: no cover - Pillow 없는 환경(카드 미표시)
    Image = ImageDraw = ImageFont = None
    PIL_OK = False

try:                                      # 같은 폴더(desktop)의 디자인 토큰. 없으면 아래 기본값.
    import theme as _theme
except Exception:                         # pragma: no cover
    _theme = None


def _tok(name, default):
    return getattr(_theme, name, default) if _theme is not None else default


# ── 팔레트(theme.py 토큰 — 새 hex 를 만들지 않는다) ─────────────────────────
C_BG       = _tok("BG", "#11131a")
C_CARD     = _tok("BG_CARD", "#1b1f2b")
C_RAISED   = _tok("BG_RAISED", "#212636")
C_INPUT    = _tok("BG_INPUT", "#171a23")
C_LINE     = _tok("LINE", "#2a3042")
C_LINE2    = _tok("LINE_STRONG", "#3a4056")
C_TEXT     = _tok("TEXT", "#e7eaf3")
C_SUB      = _tok("TEXT_SUB", "#9aa3b8")
C_MUT      = _tok("TEXT_MUT", "#7d869c")
C_ON       = _tok("TEXT_ON", "#0e1017")
C_ACCENT   = _tok("ACCENT", "#5b8cff")
C_ACCENT_H = _tok("ACCENT_H", "#7ba0ff")
C_GOLD     = _tok("GOLD", "#e0a437")
C_SUCCESS  = _tok("SUCCESS", "#2bb177")
C_LOSE     = _tok("LOSE", "#e84057")
C_WARN     = _tok("WARN", "#e8930c")
C_INFO     = _tok("INFO", "#39c7d6")
C_PURPLE   = _tok("PURPLE", "#8a5cd6")
C_CHROMA   = _tok("CHROMA_KEY", "#010203")

# ── lol.ps 고정 파라미터 ───────────────────────────────────────────────────
LOLPS_URL = "https://lol.ps/champ/{cid}/__data.json?tier=2&region=0&lane={lane}"
LOLPS_URL_NO_LANE = "https://lol.ps/champ/{cid}/__data.json?tier=2&region=0"
LOLPS_TIER = 2                     # lol.ps 티어 필터(2 = 골드+ 상위 구간 기준값)
LOLPS_REGION = 0
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SquadAnalyzer")
DD_BASE = "https://ddragon.leagueoflegends.com/cdn"

# lol.ps laneId: 0 탑 · 1 정글 · 2 미드 · 3 원딜 · 4 서폿 (2026-11-27 실측: 아리 2=34,691판,
#   리신 1=87,003판, 아트록스 0=23,122판, 진 3=23,344판, 잔나·쓰레쉬 4=3,704·42,209판)
LANES = ("탑", "정글", "미드", "원딜", "서폿")
LANE_IDS = {name: i for i, name in enumerate(LANES)}
# LCU assignedPosition / 앱 내부 표기 → lol.ps laneId
POS_ALIASES = {
    "TOP": "탑", "탑": "탑",
    "JUNGLE": "정글", "정글": "정글",
    "MIDDLE": "미드", "MID": "미드", "미드": "미드",
    "BOTTOM": "원딜", "ADC": "원딜", "BOT": "원딜", "원딜": "원딜",
    "UTILITY": "서폿", "SUPPORT": "서폿", "서폿": "서폿", "SUP": "서폿",
}


def lane_id_of(position):
    """'top'/'MIDDLE'/'원딜' 같은 표기 → lol.ps laneId(0~4). 모르면 None."""
    try:
        key = str(position or "").strip().upper()
    except Exception:
        return None
    if not key:
        return None
    kor = POS_ALIASES.get(key)
    if kor is None:
        kor = POS_ALIASES.get(str(position or "").strip())
    return LANE_IDS.get(kor) if kor else None


def lane_name(lane_id):
    try:
        i = int(lane_id)
    except Exception:
        return ""
    return LANES[i] if 0 <= i < len(LANES) else ""


# 아이템/룬을 못 받아왔을 때를 위한 스탯 파편(DDragon 에 이름 목록이 따로 없다 — 롤 고정값)
STAT_SHARDS = {
    5001: ("체력 증가", "statmodshealthscalingicon.png"),
    5002: ("방어력", "statmodsarmoricon.png"),
    5003: ("마법 저항력", "statmodsmagicresicon.png"),
    5004: ("공격 속도", "statmodsattackspeedicon.png"),
    5005: ("공격 속도", "statmodsattackspeedicon.png"),
    5007: ("스킬 가속", "statmodscdrscalingicon.png"),
    5008: ("적응형 능력치", "statmodsadaptiveforceicon.png"),
    5011: ("체력", "statmodshealthscalingicon.png"),
    5013: ("체력 증가", "statmodshealthscalingicon.png"),
}
# 스탯 파편 아이콘은 Data Dragon 에 PascalCase, Community Dragon 에 소문자 경로로 있다.
#   (DDragon: img/perk-images/StatMods/StatModsArmorIcon.png · CDragon: v1/perk-images/statmods/statmodsarmoricon.png)
#   DDragon 경로는 일부 파일이 403 이라 Community Dragon 소문자 경로를 쓴다.
STAT_SHARD_URL = ("https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/"
                  "default/v1/perk-images/statmods/{file}")


# =========================================================================
# 1) SvelteKit __data.json(devalue) 파서 — 순수 함수
# =========================================================================
class LolPsError(Exception):
    """lol.ps 응답이 우리가 아는 모양이 아님."""


def devalue_resolve(data, index, _depth=0):
    """평평한 devalue 배열 data 의 index 값을 실제 파이썬 값으로 푼다."""
    if _depth > 96:
        raise LolPsError("devalue 중첩이 너무 깊음")
    if not isinstance(index, int) or isinstance(index, bool):
        raise LolPsError("참조 인덱스가 정수가 아님")
    if index < 0 or index >= len(data):
        raise LolPsError("참조 인덱스 범위 밖")
    value = data[index]
    if isinstance(value, list):
        return [devalue_resolve(data, i, _depth + 1) for i in value]
    if isinstance(value, dict):
        out = {}
        for key, ref in value.items():
            out[key] = devalue_resolve(data, ref, _depth + 1) if isinstance(ref, int) and not isinstance(ref, bool) else ref
        return out
    return value


def _node_root_refs(node):
    """nodes[i] → (data, root_refs). 노드 모양이 아니면 (None, None)."""
    if not isinstance(node, dict):
        return None, None
    data = node.get("data")
    if not isinstance(data, list) or not data:
        return None, None
    root = data[0]
    if not isinstance(root, dict):
        return data, None
    return data, root


def _num(value, default=0.0):
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(str(value).strip().replace(",", ""))
    except Exception:
        return default


def _int(value, default=0):
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(float(str(value).strip()))
    except Exception:
        return default


def _id_list(value):
    out = []
    if isinstance(value, (list, tuple)):
        for v in value:
            i = _int(v, 0)
            if i > 0:
                out.append(i)
    return tuple(out)


@dataclass(frozen=True)
class RunePage:
    main_tree: int = 0
    sub_tree: int = 0
    keystone: int = 0
    main_runes: tuple = ()      # 각인 포함 주 룬(keystone 포함)
    sub_runes: tuple = ()
    stat_perks: tuple = ()

    @property
    def has_page(self):
        return bool(self.keystone or self.main_runes)


@dataclass(frozen=True)
class BuildVariant:
    build_type: int = 0
    win_rate: float = 0.0
    pick_rate: float = 0.0
    sample: int = 0
    spells: tuple = ()          # (spell1Id, spell2Id)
    runes: RunePage = RunePage()
    shoes: int = 0
    first: tuple = ()           # 1코어 후보
    second: tuple = ()          # 2코어 후보
    third: tuple = ()           # 3코어 후보
    combo: tuple = ()           # coreItemIdList — 완성 코어 조합
    starts: tuple = ()          # startingItemIdList — 시작 아이템 조합들
    tier: int = 0
    ranking: int = 0

    @property
    def spell_pair(self):
        return tuple(self.spells or ())[:2]


@dataclass(frozen=True)
class BuildPayload:
    champion_id: int = 0
    lane: int = -1
    version_id: int = 0
    patch: str = ""
    win_rate: float = 0.0
    pick_rate: float = 0.0
    ban_rate: float = 0.0
    sample: int = 0
    tier: int = 0
    ranking: int = 0
    variants: tuple = ()
    fetched_at: float = 0.0
    auto_lane: bool = False     # 포지션 미정 → 주 라인 데이터

    @property
    def primary(self):
        return self.variants[0] if self.variants else BuildVariant()

    @property
    def lane_label(self):
        return lane_name(self.lane)


def parse_payload(payload):
    """__data.json(dict) → BuildPayload. 데이터가 없으면(빈 champSummary) None.

    lol.ps 응답 모양이 바뀌어 우리가 아는 키가 없으면 LolPsError.
    """
    if not isinstance(payload, dict):
        raise LolPsError("payload 가 dict 가 아님")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise LolPsError("nodes 없음")

    versions = None
    page_data = None
    page_refs = None
    for node in nodes:
        data, refs = _node_root_refs(node)
        if data is None or refs is None:
            continue
        if versions is None and "versionInfo" in refs:
            try:
                got = devalue_resolve(data, refs["versionInfo"])
                if isinstance(got, list):
                    versions = got
            except Exception:
                pass
        if page_refs is None and "champSummary" in refs:
            page_data, page_refs = data, refs
    if page_refs is None:
        raise LolPsError("champSummary 노드 없음")

    try:
        summary = devalue_resolve(page_data, page_refs["champSummary"])
    except Exception as exc:
        raise LolPsError(f"champSummary 해석 실패: {exc}")
    if not isinstance(summary, list):
        raise LolPsError("champSummary 가 리스트가 아님")
    rows = [r for r in summary if isinstance(r, dict)]
    if not rows:
        return None

    champion_id = _int(devalue_resolve(page_data, page_refs["championId"])) if "championId" in page_refs else _int(rows[0].get("championId"))
    lane = _int(rows[0].get("laneId"), -1)
    version_id = _int(rows[0].get("versionId"), 0)
    patch = ""
    if isinstance(versions, list):
        for v in versions:
            if isinstance(v, dict) and _int(v.get("versionId"), 0) == version_id:
                patch = str(v.get("description") or "")
                break

    variants = []
    for row in sorted(rows, key=lambda r: _int(r.get("buildTypeId"), 0)):
        runes = RunePage(
            main_tree=_int(row.get("mainRuneCategory"), 0),
            sub_tree=_int(row.get("subRuneCategory"), 0),
            keystone=_int(row.get("mainRune1"), 0),
            main_runes=_id_list([row.get("mainRune1"), row.get("mainRune2"),
                                 row.get("mainRune3"), row.get("mainRune4")]),
            sub_runes=_id_list([row.get("subRune1"), row.get("subRune2")]),
            stat_perks=_id_list([row.get("statperk1Id"), row.get("statperk2Id"),
                                 row.get("statperk3Id")]),
        )
        starts = []
        raw_starts = row.get("startingItemIdList")
        if isinstance(raw_starts, list):
            for grp in raw_starts:
                if isinstance(grp, list):
                    ids = _id_list(grp)
                    if ids:
                        starts.append(ids)
        variants.append(BuildVariant(
            build_type=_int(row.get("buildTypeId"), 0),
            win_rate=_num(row.get("winRate")),
            pick_rate=_num(row.get("pickRate")),
            sample=_int(row.get("count"), 0),
            spells=(_int(row.get("spell1Id"), 0), _int(row.get("spell2Id"), 0)),
            runes=runes,
            shoes=_int(row.get("shoesId"), 0),
            first=_id_list(row.get("item_1coreList")),
            second=_id_list(row.get("item_2coreList")),
            third=_id_list(row.get("item_3coreList")),
            combo=_id_list(row.get("coreItemIdList")),
            starts=tuple(starts),
            tier=_int(row.get("psTier"), 0),
            ranking=_int(row.get("ranking"), 0),
        ))
    if not variants:
        return None

    first_row = rows[0]
    return BuildPayload(
        champion_id=champion_id,
        lane=lane,
        version_id=version_id,
        patch=patch,
        win_rate=_num(first_row.get("winRate")),
        pick_rate=_num(first_row.get("pickRate")),
        ban_rate=_num(first_row.get("banRate")),
        sample=_int(first_row.get("count"), 0),
        tier=_int(first_row.get("psTier"), 0),
        ranking=_int(first_row.get("ranking"), 0),
        variants=tuple(variants),
        fetched_at=time.time(),
    )


# =========================================================================
# 2) LCU 세션 → '내 칸의 지금 챔피언' (픽 스왑 감지의 핵심 — 순수 함수)
# =========================================================================
def my_pick_from_session(session, my_puuid="", fallback_pos=""):
    """ChampSelect 세션 JSON → (cellId, championId, 포지션 표기).

    - 내 칸은 localPlayerCellId 로 찾는다. 없으면(관전 등) myTeam 안에서 puuid 로 찾는다.
    - 픽 스왑은 세션의 그 칸 championId 가 바뀌는 것으로 나타나므로, **폴링할 때마다 이 함수를
      다시 부르면** 스왑이 그대로 감지된다(첫 픽만 기억하고 멈추지 않는다).
    - 아직 확정 전이면 championPickIntent(호버)를 쓴다 — 밴픽 중 미리 빌드를 볼 수 있게.
    """
    if not isinstance(session, dict):
        return None, 0, ""
    my_team = session.get("myTeam")
    if not isinstance(my_team, list):
        my_team = []
    cell = session.get("localPlayerCellId")
    try:
        cell = int(cell) if cell is not None else None
    except Exception:
        cell = None
    me = None
    if cell is not None:
        for p in my_team:
            if isinstance(p, dict) and _int(p.get("cellId"), -1) == cell:
                me = p
                break
    if me is None and my_puuid:
        want = str(my_puuid).strip().lower()
        for p in my_team:
            if isinstance(p, dict) and str(p.get("puuid") or "").strip().lower() == want:
                me = p
                break
    if me is None:
        return cell, 0, ""
    cid = _int(me.get("championId"), 0)
    if cid <= 0:
        cid = _int(me.get("championPickIntent"), 0)
    pos = str(me.get("assignedPosition") or "").strip()
    if not pos:
        pos = str(fallback_pos or "").strip()
    return _int(me.get("cellId"), cell if cell is not None else -1), cid, pos


# =========================================================================
# 3) 네트워크 — lol.ps 조회
# =========================================================================
def build_url(champion_id, lane=None):
    cid = _int(champion_id, 0)
    if cid <= 0:
        raise ValueError("champion_id 필요")
    if lane is None:
        return LOLPS_URL_NO_LANE.format(cid=cid)
    return LOLPS_URL.format(cid=cid, lane=_int(lane, 0))


def fetch_build(champion_id, lane=None, timeout=8.0, session=None):
    """lol.ps 조회 → BuildPayload | None(데이터 없음). 실패는 예외로 던진다(부르는 쪽이 조용히 삼킴)."""
    url = build_url(champion_id, lane)
    getter = session.get if session is not None else (requests.get if requests is not None else None)
    if getter is None:
        raise LolPsError("HTTP 클라이언트 없음")
    resp = getter(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                  timeout=timeout)
    if getattr(resp, "status_code", 0) != 200:
        raise LolPsError(f"HTTP {getattr(resp, 'status_code', '?')}")
    payload = resp.json()
    parsed = parse_payload(payload)
    if parsed is None:
        return None
    # lane 을 지정했는데 lol.ps 가 다른 라인 데이터를 줬다면(그 라인 표본이 너무 적을 때 주 라인으로
    #   되돌아온다) 카드에 'OO 기준'이라고 밝힌다 — 내 라인 데이터인 척하지 않는다.
    if lane is None or _int(parsed.lane, -1) != _int(lane, -2):
        parsed = replace(parsed, auto_lane=True)
    return parsed


# =========================================================================
# 4) 정적 데이터(한글 이름·아이콘 URL) — Data Dragon, 디스크 캐시
# =========================================================================
@dataclass(frozen=True)
class Icon:
    name: str = ""
    url: str = ""


def _default_cache_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.squad_analyzer")
    return os.path.join(base, "SquadAnalyzer", "lolps_cache")


class StaticData:
    """Data Dragon 한글 이름표(item·rune·spell·스탯파편). 한 번 받아 디스크에 캐시한다.

    - ready 가 False 인 동안에는 이름 대신 '아이템 3118' 같은 폴백을 쓰고, 준비되면 on_ready 로 알린다.
    - 실패해도 예외를 밖으로 던지지 않는다(카드는 폴백 이름으로 그대로 뜬다).
    """

    MAX_AGE = 7 * 24 * 3600

    def __init__(self, version="", cache_dir=None):
        self.version = str(version or "")
        self.cache_dir = cache_dir or _default_cache_dir()
        self.ready = False
        self.items = {}
        self.runes = {}
        self.trees = {}
        self.spells = {}
        self._lock = threading.Lock()
        self._thread = None
        self._callbacks = []
        self._tried = False

    # ── 로딩 ──
    def _cache_path(self):
        ver = re.sub(r"[^0-9A-Za-z_.-]", "_", self.version or "latest")
        return os.path.join(self.cache_dir, f"static_{ver}.json.gz")

    def ensure(self, on_ready=None, force=False):
        """백그라운드 1회 로딩 시작(이미 준비됐으면 콜백만 즉시 호출)."""
        if on_ready is not None:
            if self.ready:
                try:
                    on_ready()
                except Exception:
                    pass
            else:
                with self._lock:
                    self._callbacks.append(on_ready)
        if self.ready or (self._tried and not force):
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._load, name="lolps-static", daemon=True)
            self._thread.start()

    def _load(self):
        self._tried = True
        try:
            data = self._read_cache() or self._download()
            if not data:
                return
            self._apply(data)
            self.ready = True
            with self._lock:
                cbs, self._callbacks = list(self._callbacks), []
            for cb in cbs:
                try:
                    cb()
                except Exception:
                    pass
        except Exception as exc:                      # 조용히 폴백 이름으로
            print(f"[lolps] 정적 데이터 로딩 실패 — {type(exc).__name__} {exc}", flush=True)

    def _read_cache(self):
        try:
            path = self._cache_path()
            if not os.path.exists(path):
                return None
            if time.time() - os.path.getmtime(path) > self.MAX_AGE:
                return None
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data.get("items"):
                self.version = data.get("version") or self.version
                return data
        except Exception:
            return None
        return None

    def _download(self):
        if requests is None:
            return None
        ver = self.version
        if not ver:
            try:
                r = requests.get(f"{DD_BASE}/api/versions.json", timeout=6)
                ver = (r.json() or ["16.23.1"])[0]
            except Exception:
                ver = ""
        if not ver:
            return None
        self.version = ver
        base = f"{DD_BASE}/{ver}/data/ko_KR"
        items, runes, trees, spells = {}, {}, {}, {}
        try:
            r = requests.get(f"{base}/item.json", timeout=12)
            for iid, info in ((r.json() or {}).get("data") or {}).items():
                if isinstance(info, dict) and info.get("name"):
                    items[str(iid)] = str(info["name"])
        except Exception:
            pass
        try:
            r = requests.get(f"{base}/runesReforged.json", timeout=12)
            for tree in (r.json() or []):
                if not isinstance(tree, dict):
                    continue
                tid = str(_int(tree.get("id"), 0))
                if tid and tree.get("name"):
                    trees[tid] = {"name": str(tree["name"]), "icon": str(tree.get("icon") or "")}
                for slot in tree.get("slots") or []:
                    for rune in (slot or {}).get("runes") or []:
                        rid = str(_int(rune.get("id"), 0))
                        if rid and rune.get("name"):
                            runes[rid] = {"name": str(rune["name"]), "icon": str(rune.get("icon") or "")}
        except Exception:
            pass
        try:
            r = requests.get(f"{base}/summoner.json", timeout=12)
            for key, info in ((r.json() or {}).get("data") or {}).items():
                if not isinstance(info, dict):
                    continue
                sid = _int(info.get("key"), 0)
                if sid and info.get("name") and "_Jade" not in key:
                    spells.setdefault(str(sid), {"name": str(info["name"]),
                                                 "icon": str((info.get("image") or {}).get("full") or "")})
        except Exception:
            pass
        if not items and not runes:
            return None
        data = {"version": ver, "saved": time.time(), "items": items,
                "runes": runes, "trees": trees, "spells": spells}
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            tmp = self._cache_path() + ".tmp"
            with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, self._cache_path())
        except Exception:
            pass
        return data

    def _apply(self, data):
        self.items = dict(data.get("items") or {})
        raw_trees = dict(data.get("trees") or {})
        self.runes = {k: dict(v) for k, v in (data.get("runes") or {}).items()}
        self.spells = {k: dict(v) for k, v in (data.get("spells") or {}).items()}
        self.trees = {}
        for tid, info in raw_trees.items():
            icon = str((info or {}).get("icon") or "")
            self.trees[tid] = {"name": str((info or {}).get("name") or ""),
                               "url": f"{DD_BASE}/img/{icon}" if icon else ""}

    # ── 조회 ──
    def item(self, iid):
        iid = _int(iid, 0)
        if iid <= 0:
            return Icon()
        name = self.items.get(str(iid)) or f"아이템 {iid}"
        return Icon(name=name, url=f"{DD_BASE}/{self.version or '16.23.1'}/img/item/{iid}.png")

    def rune(self, rid):
        rid = _int(rid, 0)
        if rid <= 0:
            return Icon()
        info = self.runes.get(str(rid)) or {}
        icon = str(info.get("icon") or "")
        url = f"{DD_BASE}/img/{icon}" if icon else ""
        return Icon(name=str(info.get("name") or f"룬 {rid}"), url=url)

    def tree(self, tid):
        tid = _int(tid, 0)
        if tid <= 0:
            return Icon()
        info = self.trees.get(str(tid)) or {}
        return Icon(name=str(info.get("name") or ""), url=str(info.get("url") or ""))

    def spell(self, sid):
        sid = _int(sid, 0)
        if sid <= 0:
            return Icon()
        info = self.spells.get(str(sid)) or {}
        icon = str(info.get("icon") or "")
        url = f"{DD_BASE}/{self.version or '16.23.1'}/img/spell/{icon}" if icon else ""
        return Icon(name=str(info.get("name") or f"스펠 {sid}"), url=url)

    def shard(self, sid):
        sid = _int(sid, 0)
        name, fn = STAT_SHARDS.get(sid, ("", ""))
        return Icon(name=name, url=STAT_SHARD_URL.format(file=fn) if fn else "")


# =========================================================================
# 5) 아이콘 이미지 — 메모리/디스크 캐시 + 백그라운드 다운로드
# =========================================================================
class Images:
    """아이콘 PNG 를 (url,size) 키로 캐시. GUI 는 get() 만 쓰고, 다운로드는 prefetch() 가 백그라운드에서."""

    MAX_MEM = 220

    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or _default_cache_dir()
        self._mem = {}
        self._order = []
        self._lock = threading.Lock()
        self._pending = set()
        self._thread = None
        self._queue = Queue()
        self.done_count = [0]

    def _disk_path(self, url):
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.cache_dir, "icons", h + ".img")

    def _raw(self, url):
        path = self._disk_path(url)
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, "rb") as fh:
                    return fh.read()
        except Exception:
            pass
        if requests is None:
            return None
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=6)
        if getattr(r, "status_code", 0) != 200 or not r.content:
            return None
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(r.content)
        except Exception:
            pass
        return r.content

    def load(self, url, size):
        """(url,size) 아이콘 — 없으면 None(그리기는 이름 글자로 폴백). 호출 스레드에서 네트워크를 탄다."""
        if not PIL_OK or not url:
            return None
        key = (url, int(size))
        with self._lock:
            img = self._mem.get(key)
        if img is not None:
            return img
        raw = self._raw(url)
        if not raw:
            return None
        try:
            from io import BytesIO
            img = Image.open(BytesIO(raw)).convert("RGBA")
            img = img.resize((int(size), int(size)), Image.LANCZOS)
        except Exception:
            return None
        with self._lock:
            if key not in self._mem:
                self._mem[key] = img
                self._order.append(key)
                while len(self._order) > self.MAX_MEM:
                    old = self._order.pop(0)
                    self._mem.pop(old, None)
        return img

    def get(self, url, size):
        """캐시에 있을 때만(비블로킹). GUI 스레드용."""
        if not PIL_OK or not url:
            return None
        with self._lock:
            return self._mem.get((url, int(size)))

    @property
    def idle(self):
        """받는 중인 아이콘이 없나 — 렌더 신호(다 받은 뒤 한 번만 다시 그리기 위해)."""
        with self._lock:
            return not self._pending

    def prefetch(self, requests_list, on_done=None):
        """[(url,size), ...] 를 백그라운드 1스레드로 받아 둔다. 받은 게 있으면 on_done() 1회."""
        if not PIL_OK:
            return
        todo = []
        with self._lock:
            for url, size in requests_list or []:
                if not url:
                    continue
                key = (url, int(size))
                if key in self._mem or key in self._pending:
                    continue
                self._pending.add(key)
                todo.append(key)
        if not todo:
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass
            return
        with self._lock:
            for key in todo:
                self._queue.put((key, on_done))
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._worker, name="lolps-icons", daemon=True)
                self._thread.start()

    def _worker(self):
        while True:
            try:
                key, on_done = self._queue.get(timeout=0.5)
            except Empty:
                return
            url, size = key
            got = None
            try:
                got = self.load(url, size)
            except Exception:
                got = None
            finally:
                with self._lock:
                    self._pending.discard(key)
                self.done_count[0] += 1
                if got is not None and on_done:
                    try:
                        on_done()
                    except Exception:
                        pass


# =========================================================================
# 6) 조회 캐시 + 전용 워커 1개 (UI 스레드 비블로킹)
# =========================================================================
class BuildStore:
    """(championId, lane) TTL 캐시. 조회는 워커 스레드 1개가 큐에서 하나씩 처리한다."""

    TTL = 30 * 60          # 30분 — 밴픽 몇 판 도는 동안 같은 판을 다시 안 받는다
    NEG_TTL = 10 * 60      # 데이터 없음(표본 0)도 10분은 다시 안 받는다
    RETRY_AFTER = 45       # 실패한 키는 45초 뒤에만 재시도(초당 폴링으로 서버 두드리지 않게)
    MAX_ENTRIES = 48

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}        # key -> (payload|None, ts)
        self._inflight = set()
        self._failed = {}      # key -> (ts, msg)
        self._q = Queue()
        self._thread = None
        self.results = {}      # key -> payload (새로 도착한 결과; GUI 가 take)

    @staticmethod
    def key_of(champion_id, lane):
        return (int(champion_id or 0), None if lane is None else int(lane))

    def peek(self, champion_id, lane):
        """(payload|None, status) — status: ready/empty/loading/error. 캐시만 본다(비블로킹)."""
        key = self.key_of(champion_id, lane)
        now = time.time()
        with self._lock:
            hit = self._data.get(key)
            if hit is not None:
                payload, ts = hit
                ttl = self.TTL if payload is not None else self.NEG_TTL
                if now - ts < ttl:
                    return payload, ("ready" if payload is not None else "empty")
            if key in self._inflight:
                return None, "loading"
            fail = self._failed.get(key)
            if fail and now - fail[0] < self.RETRY_AFTER:
                return None, "error"
        return None, "none"

    def take_result(self, champion_id, lane):
        key = self.key_of(champion_id, lane)
        with self._lock:
            return self.results.pop(key, _MISSING)

    def request(self, champion_id, lane=None, fetch=None):
        """캐시에 없으면 워커에 넣는다. 절대 블로킹하지 않는다."""
        key = self.key_of(champion_id, lane)
        if not key[0]:
            return
        _, status = self.peek(*key)
        if status in ("ready", "empty", "loading"):
            return
        with self._lock:
            if key in self._inflight:
                return
            fail = self._failed.get(key)
            if fail and time.time() - fail[0] < self.RETRY_AFTER:
                return
            self._inflight.add(key)
            self._q.put((key, fetch or fetch_build))
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._worker, name="lolps-fetch", daemon=True)
                self._thread.start()

    def _worker(self):
        while True:
            try:
                key, fetcher = self._q.get(timeout=0.5)
            except Empty:
                return
            cid, lane = key
            payload, err = None, ""
            try:
                payload = fetcher(cid, lane)
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"[:160]
            now = time.time()
            with self._lock:
                self._inflight.discard(key)
                if err:
                    self._failed[key] = (now, err)
                    print(f"[lolps] 빌드 조회 실패 {cid}/{lane} — {err}", flush=True)
                else:
                    self._data[key] = (payload, now)
                    self._failed.pop(key, None)
                    self.results[key] = payload
                    if payload is None:
                        print(f"[lolps] 빌드 데이터 없음 {cid}/{lane}", flush=True)
                    else:
                        print(f"[lolps] 빌드 {cid}/{lane} — {len(payload.variants)}종 · "
                              f"{payload.sample}판 · {payload.patch}", flush=True)
                    while len(self._data) > self.MAX_ENTRIES:
                        oldest = min(self._data.items(), key=lambda kv: kv[1][1])[0]
                        self._data.pop(oldest, None)


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


# =========================================================================
# 7) 렌더 — Pillow 로 컴팩트 빌드 카드 1장
# =========================================================================
_FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.environ.get("SystemRoot", ""),
    "/usr/share/fonts/pickle-hwp",
    "/usr/share/fonts/truetype/nanum",
    "/usr/share/fonts/opentype/noto",
    "/usr/share/fonts/truetype/noto",
    "/System/Library/Fonts",
]
_FONT_FILES = {
    True: ("malgunbd.ttf", "malgun.ttf", "NotoSansCJKkr-Bold.otf", "NotoSansCJKkr-Regular.otf",
           "NanumGothicBold.ttf", "NanumGothic.ttf", "NotoSansKR-Bold.otf", "NotoSansCJK-Bold.ttc",
           "AppleSDGothicNeo-Bold.ttf", "AppleSDGothicNeo.ttf"),
    False: ("malgun.ttf", "NotoSansCJKkr-Regular.otf", "NanumGothic.ttf", "NotoSansKR-Regular.otf",
            "NotoSansCJK-Regular.ttc", "AppleSDGothicNeo.ttf"),
}
_font_cache = {}
_font_path_cache = {}


def _font_path(bold=False):
    if bold in _font_path_cache:
        return _font_path_cache[bold]
    found = ""
    for mode in ((True, False) if bold else (False,)):
        for name in _FONT_FILES[mode]:
            for d in _FONT_DIRS:
                if not d:
                    continue
                path = os.path.join(d, name)
                if os.path.exists(path):
                    found = path
                    break
            if found:
                break
        if found:
            break
    _font_path_cache[bold] = found
    return found


def _font(size, bold=False):
    key = (round(float(size), 1), bool(bold))
    f = _font_cache.get(key)
    if f is not None:
        return f
    px = max(1, int(round(float(size))))
    path = _font_path(bold)
    try:
        if path:
            f = ImageFont.truetype(path, px)
        else:
            f = ImageFont.load_default(px)
    except Exception:
        try:
            f = ImageFont.load_default()
        except Exception:
            f = None
    _font_cache[key] = f
    return f


def _text_w(draw, txt, font):
    try:
        box = draw.textbbox((0, 0), txt, font=font)
        return box[2] - box[0], box[3] - box[1]
    except Exception:
        return (len(str(txt)) * 6, 10)


def _fit(draw, txt, font, max_w):
    """max_w 안에 들어가게 줄인다(말줄임 …). 잘려 보이지 않게 하는 마지막 안전장치."""
    txt = str(txt or "")
    if not txt or max_w <= 1:
        return ""
    if _text_w(draw, txt, font)[0] <= max_w:
        return txt
    lo, hi = 0, len(txt)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_w(draw, txt[:mid] + "…", font)[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (txt[:lo] + "…") if lo > 0 else ""


def _wrap_lines(draw, txt, font1, font2, max_w, max_lines=2):
    """이름을 max_w 칸에 넣는다: 한 줄에 들어가면 한 줄, 아니면 두 번째(작은) 폰트로 두 줄.

    그래도 넘치면 말줄임 — 아이콘 칸을 절대 침범하지 않게 하는 마지막 안전장치.
    """
    txt = str(txt or "").strip()
    if not txt or max_w <= 1:
        return []
    if _text_w(draw, txt, font1)[0] <= max_w:
        return [(txt, font1)]
    space = txt.rfind(" ")
    parts = [txt[:space], txt[space + 1:]] if space > 0 else []
    if parts and max(_text_w(draw, p, font2)[0] for p in parts) <= max_w:
        return [(p, font2) for p in parts]
    # 글자 단위로 두 줄에 나눠 본다
    lo, hi = 1, len(txt) - 1
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if _text_w(draw, txt[:mid], font2)[0] <= max_w and _text_w(draw, txt[mid:], font2)[0] <= max_w:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if best:
        return [(txt[:best], font2), (txt[best:], font2)]
    return [(_fit(draw, txt, font2, max_w), font2)]


def _rr(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _gradient(w, h, top, bottom):
    """세로 그라데이션 — 카드 배경에만 쓴다(면적 대비 비용 작음)."""
    img = Image.new("RGB", (1, max(1, h)), top)
    px = img.load()
    t = tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(bottom[i:i + 2], 16) for i in (1, 3, 5))
    for y in range(h):
        f = y / max(1, h - 1)
        px[0, y] = (int(t[0] + (b[0] - t[0]) * f), int(t[1] + (b[1] - t[1]) * f),
                    int(t[2] + (b[2] - t[2]) * f))
    return img.resize((w, h))


def _paste_icon(card, icons, url, size, xy, radius=None):
    """아이콘을 둥근 모서리로 붙인다. 없으면 빈 사각형만 남긴다(자리는 지킨다)."""
    x, y = xy
    img = icons.get(url, size) if icons is not None else None
    if img is None:
        d = ImageDraw.Draw(card)
        _rr(d, (x, y, x + size, y + size), radius if radius is not None else max(3, size // 5),
            fill=C_INPUT, outline=C_LINE, width=1)
        return False
    if radius is None:
        radius = max(3, size // 5)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    card.paste(img, (int(x), int(y)), mask)
    return True


def _spell_text_texts(payload):
    """카드에 필요한 아이콘 요청 목록 — prefetch 용."""
    out = []
    for v in payload.variants[:2]:
        for sid in (v.spells or ())[:2]:
            out.append(sid)
    return out


def render_card(payload, statics=None, icons=None, champion_name="", champion_icon=None,
                collapsed=False, scale=2, now=None):
    """BuildPayload → PIL.Image (RGBA). 카드 배경은 둥근 모서리 + 투명(CHROMA_KEY) 바탕."""
    if not PIL_OK:
        raise RuntimeError("Pillow 없음")
    if payload is None:
        raise ValueError("payload 없음")
    statics = statics or StaticData()
    S = max(1, int(scale))
    W = 372
    pad = 14
    collapsed = bool(collapsed)

    # ── 이름표 ──
    prim = payload.primary
    champ_title = str(champion_name or "").strip() or f"챔피언 {payload.champion_id}"
    lane_txt = payload.lane_label or ""
    sub_txt = " ".join(x for x in (lane_txt, f"패치 {payload.patch}" if payload.patch else "") if x)

    body = Image.new("RGB", (W * S, (100 if collapsed else 460) * S), C_BG)
    try:                       # 은은한 세로 그라데이션(카드 배경 전용) — 토큰 두 색 사이
        body.paste(_gradient(W * S, body.size[1], C_CARD, C_BG), (0, 0))
    except Exception:
        body.paste(Image.new("RGB", body.size, C_CARD), (0, 0))
    draw = ImageDraw.Draw(body)
    f_name = _font(15.5 * S, True)
    f_sub = _font(9.5 * S)
    f_stat = _font(11 * S, True)
    f_label = _font(9 * S, True)
    f_item = _font(9.5 * S)
    f_rune = _font(11 * S, True)
    f_badge = _font(9.5 * S, True)

    y = pad
    # ── 헤더 ──
    icon_sz = 40
    _paste_icon(body, icons, "", icon_sz, (pad * S, y * S))       # 자리(로컬 초상화가 있으면 아래에서 덮어씀)
    if champion_icon is not None:
        try:
            cimg = champion_icon if champion_icon.size == (icon_sz, icon_sz) else champion_icon.resize((icon_sz, icon_sz), Image.LANCZOS)
            mask = Image.new("L", (icon_sz, icon_sz), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, icon_sz - 1, icon_sz - 1), radius=9, fill=255)
            body.paste(cimg.convert("RGBA"), (pad * S, y * S), mask)
        except Exception:
            pass
    tx = pad + icon_sz + 10
    draw.text((tx * S, (y + 1) * S), _fit(draw, champ_title, f_name, (W - tx - pad - 58) * S), font=f_name, fill=C_TEXT)
    draw.text((tx * S, (y + 22) * S), _fit(draw, sub_txt, f_sub, (W - tx - pad - 58) * S), font=f_sub, fill=C_SUB)

    # 티어 배지(오른쪽 위)
    tier_txt = f"{payload.tier}티어" if 1 <= payload.tier <= 5 else ("표본 부족" if payload.sample < 200 else "—")
    bw, _bh = _text_w(draw, tier_txt, f_badge)
    bw = max(bw + 14 * S, 30 * S)
    bx2 = (W - pad - 20) * S          # 우상단 ✕ 자리를 비워 둔다
    bx1 = bx2 - bw
    _rr(draw, (bx1, (y + 2) * S, bx2, (y + 18) * S), 4 * S,
        fill=(C_GOLD if 1 <= payload.tier <= 5 else C_RAISED))
    draw.text(((bx1 + bx2) / 2, (y + 10) * S), tier_txt, font=f_badge,
              fill=(C_ON if 1 <= payload.tier <= 5 else C_MUT), anchor="mm")
    if payload.ranking:
        rank = f"{payload.ranking}위"
        draw.text((bx2, (y + 23) * S), rank, font=f_sub, fill=C_MUT, anchor="ra")
    # 닫기(✕) / 접기(▾) — 창 쪽 클릭 판정 영역과 같은 자리. 글자 대신 선으로 그린다(폰트에 글리프 없음 대비)
    cx, cy = (W - 15) * S, (y + 9) * S
    lw = max(1, S)
    draw.line([(cx - 5 * S, cy - 5 * S), (cx + 5 * S, cy + 5 * S)], fill=C_MUT, width=lw)
    draw.line([(cx - 5 * S, cy + 5 * S), (cx + 5 * S, cy - 5 * S)], fill=C_MUT, width=lw)
    ty = (y + 28) * S
    if collapsed:
        draw.polygon([(cx - 5 * S, ty + 3 * S), (cx + 5 * S, ty + 3 * S), (cx, ty - 3 * S)], fill=C_MUT)
    else:
        draw.polygon([(cx - 5 * S, ty - 3 * S), (cx + 5 * S, ty - 3 * S), (cx, ty + 3 * S)], fill=C_MUT)
    y += 48

    # ── 승률/픽률 줄 ──
    wr_color = C_SUCCESS if payload.win_rate >= 50 else C_LOSE
    parts = [(f"승률 {payload.win_rate:.1f}%", wr_color, True),
             (f"픽률 {payload.pick_rate:.1f}%", C_SUB, False),
             (f"밴률 {payload.ban_rate:.1f}%", C_SUB, False)]
    if payload.sample:
        parts.append((f"{payload.sample:,}판", C_MUT, False))
    px = pad * S
    for txt, color, bold in parts:
        fnt = _font(10.5 * S, bold)
        draw.text((px, y * S), txt, font=fnt, fill=color)
        px += _text_w(draw, txt, fnt)[0] + 12 * S
    if payload.auto_lane and lane_txt:
        draw.text(((W - pad) * S, y * S), f"{lane_txt} 기준", font=f_sub, fill=C_MUT, anchor="ra")
    y += 22
    draw.line([(pad * S, y * S), ((W - pad) * S, y * S)], fill=C_LINE, width=max(1, S // 2))
    y += 10

    def section(title):
        nonlocal y
        draw.text((pad * S, y * S), title, font=f_label, fill=C_MUT)
        y += 16

    def item_row(label, ids, limit=3):
        nonlocal y
        draw.text((pad * S, (y + 8) * S), label, font=f_sub, fill=C_SUB)
        x = (pad + 34) * S
        colw = ((W - pad) - (pad + 34)) / float(max(1, limit))
        isz = 26
        for idx, iid in enumerate(list(ids)[:limit]):
            info = statics.item(iid)
            col_x = x + idx * colw * S
            _paste_icon(body, icons, info.url, isz, (col_x, y * S))
            lines = _wrap_lines(draw, info.name, f_item, _font(8.5 * S), (colw - isz - 8) * S)
            ly = y + (isz - 13 * len(lines)) / 2 + 1
            for text, fnt in lines:
                draw.text((col_x + (isz + 6) * S, ly * S), text, font=fnt, fill=C_TEXT)
                ly += 12
        y += isz + 8

    # ── 아이템 ──
    section("아이템")
    if prim.first:
        item_row("1코어", prim.first)
    if prim.second:
        item_row("2코어", prim.second)
    if prim.third:
        item_row("3코어", prim.third)
    shoes = prim.shoes
    if shoes:
        draw.text((pad * S, (y + 8) * S), "신발", font=f_sub, fill=C_SUB)
        info = statics.item(shoes)
        _paste_icon(body, icons, info.url, 26, ((pad + 34) * S, y * S))
        draw.text(((pad + 34 + 32) * S, (y + 7) * S), _fit(draw, info.name, f_item, (W - pad - pad - 66) * S),
                  font=f_item, fill=C_TEXT)
        y += 32

    y += 4
    draw.line([(pad * S, y * S), ((W - pad) * S, y * S)], fill=C_LINE, width=max(1, S // 2))
    y += 10

    # ── 룬 ──
    runes = prim.runes
    section("룬")
    if runes.has_page:
        main_tree = statics.tree(runes.main_tree)
        sub_tree = statics.tree(runes.sub_tree)
        key = statics.rune(runes.keystone)
        # 주 룬: 트리 이름 · 각인 크게 · 나머지 작게
        draw.text((pad * S, (y + 6) * S), "주", font=f_sub, fill=C_SUB)
        _paste_icon(body, icons, main_tree.url, 20, ((pad + 22) * S, (y + 2) * S))
        tname = _fit(draw, main_tree.name, f_sub, 44 * S)
        draw.text(((pad + 46) * S, (y + 6) * S), tname, font=f_sub, fill=C_SUB)
        x = (pad + 46 + 48) * S
        _paste_icon(body, icons, key.url, 26, (x, y * S))
        kname = _fit(draw, key.name, f_rune, (W - pad - (pad + 46 + 48) - 30 - 3 * 18 - 6) * S)
        draw.text((x + 30 * S, (y + 7) * S), kname, font=f_rune, fill=C_TEXT)
        kx = x + 30 * S + _text_w(draw, kname, f_rune)[0] + 8 * S
        for rid in runes.main_runes[1:4]:
            info = statics.rune(rid)
            _paste_icon(body, icons, info.url, 18, (kx, (y + 4) * S), radius=9)
            kx += 20 * S
        y += 30
        # 보조 룬 + 스탯 파편
        draw.text((pad * S, (y + 4) * S), "보조", font=f_sub, fill=C_SUB)
        _paste_icon(body, icons, sub_tree.url, 18, ((pad + 22) * S, y * S))
        sname = _fit(draw, sub_tree.name, f_sub, 44 * S)
        draw.text(((pad + 44) * S, (y + 4) * S), sname, font=f_sub, fill=C_SUB)
        sx = (pad + 44 + 48) * S
        for rid in runes.sub_runes[:2]:
            info = statics.rune(rid)
            _paste_icon(body, icons, info.url, 18, (sx, y * S), radius=9)
            sx += 20 * S
        # 스탯 파편은 오른쪽 끝에
        shard_x = (W - pad) * S - len(runes.stat_perks[:3]) * 18 * S
        for sid in runes.stat_perks[:3]:
            info = statics.shard(sid)
            _paste_icon(body, icons, info.url, 16, (shard_x, (y + 1) * S), radius=8)
            shard_x += 18 * S
        y += 24
    else:
        draw.text((pad * S, y * S), "룬 데이터 없음(표본 부족)", font=f_sub, fill=C_MUT)
        y += 20

    draw.line([(pad * S, y * S), ((W - pad) * S, y * S)], fill=C_LINE, width=max(1, S // 2))
    y += 10

    # ── 스펠 ──
    section("스펠")
    spx = pad * S
    for sid in (prim.spells or ())[:2]:
        info = statics.spell(sid)
        ok = _paste_icon(body, icons, info.url, 24, (spx, y * S))
        draw.text((spx + 28 * S, (y + 6) * S), _fit(draw, info.name, f_item, 52 * S), font=f_item, fill=C_TEXT)
        spx += 28 * S + _text_w(draw, info.name, f_item)[0] + 14 * S
    alt = [v for v in payload.variants[1:3] if tuple(v.spells) != tuple(prim.spells)]
    if alt:
        alt_sp = " + ".join(statics.spell(s).name for s in alt[0].spells if statics.spell(s).name)
        draw.text(((W - pad) * S, (y + 6) * S), _fit(draw, f"대안 {alt_sp}", f_sub, 120 * S),
                  font=f_sub, fill=C_MUT, anchor="ra")
    y += 26

    # ── 푸터 ──
    y += 6
    when = payload.fetched_at or (now or time.time())
    try:
        mins = int(max(0, (now or time.time()) - when) // 60)
    except Exception:
        mins = 0
    foot = "lol.ps · 골드+" if not payload.patch else f"lol.ps · 패치 {payload.patch} · 갱신 {mins}분 전"
    draw.text((pad * S, y * S), foot, font=_font(8.5 * S), fill=C_MUT)
    draw.text(((W - pad) * S, y * S), "클릭=접기 · 드래그=이동 · 더블클릭=위치 초기화",
              font=_font(8.5 * S), fill=C_MUT, anchor="ra")
    y += 14

    H = int(round(y + pad - 4))
    card = body.crop((0, 0, W * S, H * S)).convert("RGBA")
    # 액자: 둥근 모서리 + 헤어라인. 바깥은 CHROMA_KEY(창의 투명 키)
    out = Image.new("RGBA", (W * S, H * S), C_CHROMA + "ff")
    mask = Image.new("L", (W * S, H * S), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((1 * S, 1 * S, (W - 1) * S, (H - 1) * S), radius=12 * S, fill=255)
    out.paste(card, (0, 0), mask)
    border = ImageDraw.Draw(out)
    border.rounded_rectangle((1 * S, 1 * S, (W - 1) * S, (H - 1) * S), radius=12 * S,
                             outline=C_LINE2, width=max(1, S))
    # 상단 액센트 라인(브랜드)
    border.line([(16 * S, 1 * S), ((W - 16) * S, 1 * S)], fill=C_ACCENT, width=max(1, S))
    if S != 1:
        out = out.resize((W, H), Image.LANCZOS)
    return out


def render_collapsed(payload, statics=None, icons=None, champion_name="", champion_icon=None, now=None):
    """접힌 모드 — 한 줄 요약(초상화·코어·룬·스펠·승률)."""
    if not PIL_OK:
        raise RuntimeError("Pillow 없음")
    if payload is None:
        raise ValueError("payload 없음")
    statics = statics or StaticData()
    W, H = 372, 64
    card = Image.new("RGB", (W, H), C_CARD)
    draw = ImageDraw.Draw(card)
    prim = payload.primary
    x = 12
    if champion_icon is not None:
        try:
            img = champion_icon.resize((30, 30), Image.LANCZOS).convert("RGBA")
            mask = Image.new("L", (30, 30), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, 29, 29), radius=7, fill=255)
            card.paste(img, (x, 17), mask)
        except Exception:
            pass
    else:
        _rr(draw, (x, 17, x + 30, 47), 7, fill=C_INPUT, outline=C_LINE)
    x += 38
    name = str(champion_name or "").strip() or f"챔피언 {payload.champion_id}"
    draw.text((x, 8), _fit(draw, name, _font(12.5, True), 96), font=_font(12.5, True), fill=C_TEXT)
    draw.text((x, 26), _fit(draw, f"{payload.lane_label} · {payload.win_rate:.1f}% · {payload.sample:,}판",
                            _font(9), 108), font=_font(9), fill=C_SUB)
    x = 170
    core = list(prim.combo or (prim.first[:1] + prim.second[:1] + prim.third[:1]))
    for iid in core[:4]:
        info = statics.item(iid)
        _paste_icon(card, icons, info.url, 22, (x, 20))
        x += 25
    x += 4
    key = statics.rune(prim.runes.keystone)
    if prim.runes.keystone:
        _paste_icon(card, icons, key.url, 22, (x, 20), radius=11)
        x += 25
    for sid in (prim.spells or ())[:2]:
        info = statics.spell(sid)
        _paste_icon(card, icons, info.url, 22, (x, 20))
        x += 25
    # 접힌 카드에도 닫기(✕)·펴기(▴) 자리를 보여 준다
    dd = ImageDraw.Draw(card)
    bx, by = W - 13, 22
    dd.line([(bx - 4, by - 4), (bx + 4, by + 4)], fill=C_MUT, width=1)
    dd.line([(bx - 4, by + 4), (bx + 4, by - 4)], fill=C_MUT, width=1)
    cy2 = 42
    dd.polygon([(bx - 5, cy2 + 3), (bx + 5, cy2 + 3), (bx, cy2 - 3)], fill=C_MUT)
    out = Image.new("RGBA", (W, H), C_CHROMA + "ff")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, W - 1, H - 1), radius=11, fill=255)
    out.paste(card, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle((1, 1, W - 1, H - 1), radius=11, outline=C_LINE2, width=1)
    return out


def icon_requests_for(payload, statics, collapsed=False):
    """prefetch 할 (url,size) 목록 — 카드에 실제로 그려질 아이콘 전체."""
    out = []
    prim = payload.primary
    if not collapsed:
        for iid in list(prim.first[:3]) + list(prim.second[:3]) + list(prim.third[:3]) + [prim.shoes]:
            if iid:
                out.append((statics.item(iid).url, 26))
        if prim.runes.has_page:
            out.append((statics.tree(prim.runes.main_tree).url, 20))
            out.append((statics.tree(prim.runes.sub_tree).url, 18))
            out.append((statics.rune(prim.runes.keystone).url, 26))
            for rid in list(prim.runes.main_runes[1:4]) + list(prim.runes.sub_runes[:2]):
                out.append((statics.rune(rid).url, 18))
            for sid in prim.runes.stat_perks[:3]:
                out.append((statics.shard(sid).url, 16))
        for sid in (prim.spells or ())[:2]:
            out.append((statics.spell(sid).url, 24))
    else:
        for iid in list(prim.combo or ())[:4]:
            out.append((statics.item(iid).url, 22))
        if prim.runes.keystone:
            out.append((statics.rune(prim.runes.keystone).url, 22))
        for sid in (prim.spells or ())[:2]:
            out.append((statics.spell(sid).url, 22))
    return out


# =========================================================================
# 8) 항상-위 카드 창(Tk) — 달라진 그림만 갈아끼운다
# =========================================================================
CARD_W = 372


class BuildOverlay:
    """프레임리스 항상-위 카드. GUI 스레드에서만 만진다."""

    def __init__(self, root, pos_store=None, pos_key="lolps_card_pos", title="챔피언 빌드"):
        self.root = root
        self.win = None
        self.label = None
        self.photo = None
        self.key = None
        self.collapsed = False
        self.manual = False
        self.dismissed = None            # 닫은 대상 키 — 같은 대상이면 다시 안 뜬다
        self.pos_store = pos_store
        self.pos_key = pos_key
        self.dock_fn = None              # () -> (x, y, w, h) 롤 클라 창 사각형(스크린 좌표). 앱이 넘겨준다.
        self.on_toggle = None
        self._drag = {"x": 0, "y": 0}
        self._size = (0, 0)
        self._placed = False
        self._pressed = False
        self._moved = False

    # ── 내부 ──
    def _ensure(self):
        if self.win is not None:
            try:
                if self.win.winfo_exists():
                    return self.win
            except Exception:
                pass
        import tkinter as tk
        w = tk.Toplevel(self.root)
        w.title("챔피언 빌드 (lol.ps)")
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.configure(bg=C_CHROMA)
            w.attributes("-transparentcolor", C_CHROMA)
        except Exception:
            pass
        lab = tk.Label(w, bd=0, bg=C_CHROMA, highlightthickness=0)
        lab.pack()
        lab.bind("<Button-1>", self._on_press)
        lab.bind("<B1-Motion>", self._on_drag)
        lab.bind("<ButtonRelease-1>", self._on_release)
        lab.bind("<Double-Button-1>", lambda e: self.reset_position())
        w.bind("<Button-1>", self._on_press)
        w.bind("<B1-Motion>", self._on_drag)
        w.bind("<ButtonRelease-1>", self._on_release)
        self.win, self.label = w, lab
        return w

    def _on_press(self, event):
        """우상단 ✕ = 이 챔피언 카드 닫기, ▾ = 접기, 나머지는 드래그(움직임 없이 떼면 접기 토글)."""
        try:
            x, y = event.x, event.y
        except Exception:
            return
        self._drag = {"x": event.x_root, "y": event.y_root}
        self._moved = False
        w = self._size[0] or CARD_W
        if x >= w - 26 and y <= 26:
            self.hide(dismiss=True)
            return
        if x >= w - 26 and 26 < y <= 42:
            self.set_collapsed(not self.collapsed)
            return
        self._pressed = True

    def _on_drag(self, event):
        if not getattr(self, "_pressed", False) or self.win is None:
            return
        try:
            dx = event.x_root - self._drag["x"]
            dy = event.y_root - self._drag["y"]
            if abs(dx) + abs(dy) < 2 and not self._moved:
                return
            self._moved = True
            self._drag = {"x": event.x_root, "y": event.y_root}
            nx = self.win.winfo_x() + dx
            ny = self.win.winfo_y() + dy
            nx, ny = self._clamp(nx, ny)
            self.win.geometry("+%d+%d" % (nx, ny))
            self.manual = True
        except Exception:
            pass

    def _on_release(self, _event=None):
        was_pressed = getattr(self, "_pressed", False)
        self._pressed = False
        if self.manual:
            try:
                if self.pos_store is not None:
                    self.pos_store[self.pos_key] = [self.win.winfo_x(), self.win.winfo_y()]
            except Exception:
                pass
        if was_pressed and not getattr(self, "_moved", False):
            self.set_collapsed(not self.collapsed)      # 클릭(움직임 없음) = 접기/펴기

    def _clamp(self, x, y):
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            ww, wh = self._size[0] or CARD_W, self._size[1] or 200
            x = max(-ww + 60, min(int(x), sw - 60))
            y = max(0, min(int(y), sh - 40))
        except Exception:
            pass
        return int(x), int(y)

    def reset_position(self):
        self.manual = False
        try:
            if self.pos_store is not None:
                self.pos_store.pop(self.pos_key, None)
        except Exception:
            pass
        self._place()
    def _place(self):
        """자리 잡기 — ①손으로 옮긴 자리 ②롤 클라 왼쪽 바깥 ③화면 오른쪽 아래.

        고스트밴픽왕 카드는 클라 오른쪽에 붙으므로 카드가 서로 겹치지 않게 왼쪽을 기본으로 한다.
        """
        w = self.win
        if w is None:
            return
        try:
            ww, wh = self._size
            if self.manual and self.pos_store is not None:
                pos = self.pos_store.get(self.pos_key)
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    x, y = self._clamp(pos[0], pos[1])
                    w.geometry("%dx%d+%d+%d" % (ww, wh, x, y))
                    return
            x = y = None
            rect = None
            try:
                rect = self.dock_fn() if self.dock_fn else None
            except Exception:
                rect = None
            if isinstance(rect, (list, tuple)) and len(rect) == 4 and rect[2] > 200:
                rx, ry, rw, rh = rect
                if rx - ww - 6 >= 0:                       # 클라 왼쪽 바깥에 자리가 있으면
                    x, y = rx - ww - 6, ry + 90
                else:                                      # 없으면 클라 안 왼쪽 아래
                    x, y = rx + 10, ry + max(90, rh - wh - 70)
            if x is None:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                x, y = sw - ww - 26, sh - wh - 90
            x, y = self._clamp(x, y)
            w.geometry("%dx%d+%d+%d" % (ww, wh, x, y))
        except Exception:
            pass

    # ── 공개 ──
    def show(self, image, key, collapsed=False):
        """image(PIL) 를 창에 올린다. 같은 대상이면 그림만 갈아끼운다."""
        from PIL import ImageTk
        w = self._ensure()
        if self.dismissed == key:
            return None
        ww, wh = image.size
        photo = ImageTk.PhotoImage(image)
        self.photo = photo
        self.label.configure(image=photo, width=ww, height=wh)
        size_changed = (ww, wh) != self._size
        self._size = (ww, wh)
        self.key = key
        self.collapsed = bool(collapsed)
        try:
            if not self._placed:
                self._place()
                self._placed = True
            elif size_changed and not self.manual:
                # 접기/펴기로 크기만 바뀌었으면 있던 자리를 지킨다(모서리로 튀지 않게)
                x, y = self._clamp(w.winfo_x(), w.winfo_y())
                w.geometry("%dx%d+%d+%d" % (ww, wh, x, y))
            else:
                w.geometry("%dx%d" % (ww, wh))
            w.deiconify()
            w.attributes("-topmost", True)
            w.lift()
        except Exception:
            pass
        return key

    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        try:
            self.set_collapsed(self.collapsed)
        except Exception:
            pass

    def set_collapsed(self, value):
        self.collapsed = bool(value)
        cb = getattr(self, "on_toggle", None)
        if cb:
            try:
                cb(self.collapsed)
            except Exception:
                pass

    def hide(self, dismiss=False):
        if dismiss and self.key is not None:
            self.dismissed = self.key
        try:
            if self.win is not None:
                self.win.withdraw()
        except Exception:
            pass

    def destroy(self):
        try:
            if self.win is not None:
                self.win.destroy()
        except Exception:
            pass
        self.win = None


# =========================================================================
# 9) 트래커 — LCU 스레드가 feed(), GUI 스레드가 sync()
# =========================================================================
class BuildTracker:
    """지금 대상(챔피언·라인)의 빌드를 조회해 카드로 보여준다.

    - feed(): LCU 폴링 스레드. 챔피언이 바뀌면(픽 스왑 포함) 대상만 갈아끼운다(비블로킹).
    - sync(): GUI 스레드 1초 틱. 준비된 그림이 있으면 창에 올린다.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.store = BuildStore()
        self.images = None
        self.statics = None
        self.overlay = None
        self.target = (0, None)          # (championId, laneId|None)
        self.target_name = ""
        self.rev = 0
        self.visible = False
        self._render_q = Queue()
        self._render_thread = None
        self._rendered = {}              # rev -> (image, key, collapsed)
        self._render_busy = set()
        self._last_render_rev = -1
        self._last_error = ""
        self._shown_target = None        # 지금 화면에 뜬 카드의 (챔프, 라인) — 대상이 바뀌면 낡은 카드를 내린다
        self.cache_dir = _default_cache_dir()
        self.dock_provider = None        # () -> (x,y,w,h) 롤 클라 창. 앱이 _lol_client_rect 로 넘겨준다.
        self.pos_store = None            # 수동 위치 기억(APP_CONFIG)

    # ── 설정 ──
    def configure(self, ddragon_version="", champion_name_lookup=None, cache_dir=None):
        if cache_dir:
            self.cache_dir = cache_dir
            if self.images is not None:
                self.images.cache_dir = cache_dir
        if self.statics is None or (ddragon_version and ddragon_version != self.statics.version):
            self.statics = StaticData(version=ddragon_version, cache_dir=self.cache_dir)
        if self.images is None:
            self.images = Images(cache_dir=self.cache_dir)
        self.name_lookup = champion_name_lookup

    def set_dock_provider(self, fn):
        """카드 기본 자리 — 롤 클라 창 사각형(x,y,w,h). None 이면 화면 오른쪽 아래."""
        self.dock_provider = fn
        if self.overlay is not None:
            self.overlay.dock_fn = fn

    def _champion_name(self, cid):
        try:
            if getattr(self, "name_lookup", None):
                return str(self.name_lookup(cid) or "")
        except Exception:
            pass
        return ""

    # ── LCU 쪽 ──
    def feed(self, champion_id, position="", phase="ChampSelect"):
        """내 칸의 지금 챔피언·포지션. 같은 값이면 아무 일도 안 한다(폴링마다 불러도 안전)."""
        try:
            cid = _int(champion_id, 0)
        except Exception:
            cid = 0
        if str(phase or "") != "ChampSelect" or cid <= 0:
            with self._lock:
                if self.target != (0, None):
                    self.target = (0, None)
                    self.target_name = ""
                    self.rev += 1
            return
        lane = lane_id_of(position)
        with self._lock:
            if (cid, lane) == self.target:
                return
            self.target = (cid, lane)
            self.target_name = self._champion_name(cid)
            self.rev += 1
        self.store.request(cid, lane)

    # ── GUI 쪽 ──
    def sync(self, root=None):
        """GUI 1초 틱. 준비된 빌드가 있으면 카드를 올리고, 없으면 내린다."""
        with self._lock:
            cid, lane = self.target
            rev = self.rev
            name = self.target_name
        if root is not None and self.overlay is None:
            self.overlay = BuildOverlay(root, pos_store=self.pos_store)
            self.overlay.on_toggle = lambda _c: self.request_render()
            self.overlay.dock_fn = self.dock_provider
        if not cid:
            if self.overlay is not None:
                self.overlay.hide()
            self._shown_target = None
            return
        # 새 결과가 도착했으면 렌더 큐로
        got = self.store.take_result(cid, lane)
        payload, status = self.store.peek(cid, lane)
        if payload is None and status in ("none", "error"):
            self.store.request(cid, lane)
            payload, status = self.store.peek(cid, lane)
        if payload is None:
            # 새 챔피언(스왑 포함)으로 바뀌었는데 아직 데이터가 없으면 — 이전 챔피언 카드를 남기지 않는다
            if self.overlay is not None and self._shown_target not in (None, (cid, lane)):
                self.overlay.hide()
                self._shown_target = None
            return
        if self.statics is not None and not self.statics.ready:
            self.statics.ensure(on_ready=self.request_render)
        if self.images is None:
            self.images = Images(cache_dir=self.cache_dir)
        # 아이콘 프리페치 → 도착하면 다시 렌더
        try:
            self.images.prefetch(icon_requests_for(payload, self.statics, self.overlay.collapsed if self.overlay else False),
                                 on_done=self.request_render)
        except Exception:
            pass
        # 접힘 상태까지 반영한 렌더 요청(바뀐 게 없으면 no-op)
        self.request_render()
        if self.overlay is None:            # 창을 아직 못 만들었으면 그림은 다음 틱에 쓴다
            return
        img = self._pop_rendered(rev, self.overlay.collapsed)
        if img is not None:
            image, key, collapsed = img
            try:
                self.overlay.show(image, key, collapsed=collapsed)
                self._shown_target = (cid, lane)
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"

    def request_render(self, force=False):
        """지금 대상·접힘 상태의 카드 그림을 백그라운드에서 만든다(같은 조건이면 no-op).

        아이콘을 다 받기 전(idle=False)에도 한 번 그려 두고, 다 받으면(idle=True) 한 번 더 그린다.
        그 사이에 오는 콜백은 같은 조건이라 무시된다 — 렌더가 여러 번 도는 일이 없다.
        """
        with self._lock:
            cid, lane = self.target
            rev = self.rev
            name = self.target_name
        if not cid:
            return
        payload, _status = self.store.peek(cid, lane)
        if payload is None:
            return
        collapsed = bool(self.overlay.collapsed) if self.overlay else False
        sig = (rev, collapsed,
               self.statics.ready if self.statics else False,
               self.images.idle if self.images else True)
        if not force and self._last_render_rev == sig:
            return
        if sig in self._render_busy:
            return
        self._last_render_rev = sig
        self._render_busy.add(sig)
        self._render_q.put((sig, rev, payload, name, collapsed))
        self._ensure_render_thread()

    def _ensure_render_thread(self):
        if self._render_thread is not None and self._render_thread.is_alive():
            return
        self._render_thread = threading.Thread(target=self._render_worker, name="lolps-render", daemon=True)
        self._render_thread.start()

    def _render_worker(self):
        while True:
            try:
                sig, rev, payload, name, collapsed = self._render_q.get(timeout=2.0)
            except Empty:
                return
            try:
                champion_icon = None
                try:
                    champion_icon = self.images.load(
                        "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/%d.png"
                        % int(payload.champion_id), 40)
                except Exception:
                    champion_icon = None
                if collapsed:
                    img = render_collapsed(payload, self.statics, self.images, name, champion_icon)
                else:
                    img = render_card(payload, self.statics, self.images, name, champion_icon,
                                      collapsed=False)
                key = f"{payload.champion_id}:{payload.lane}:{rev}:{int(collapsed)}:{payload.version_id}"
                with self._lock:
                    self._rendered[(rev, bool(collapsed))] = (img, key, bool(collapsed))
                    while len(self._rendered) > 6:
                        self._rendered.pop(min(self._rendered), None)
            except Exception as exc:
                self._last_error = f"render {type(exc).__name__}: {exc}"
                print(f"[lolps] 카드 렌더 실패 — {self._last_error}", flush=True)
            finally:
                self._render_busy.discard(sig)

    def _pop_rendered(self, rev, collapsed=False):
        with self._lock:
            return self._rendered.pop((rev, bool(collapsed)), None)

    def close(self):
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None


# 앱이 쓰는 단일 인스턴스
tracker = BuildTracker()


def configure(ddragon_version="", champion_name_lookup=None, cache_dir=None):
    tracker.configure(ddragon_version, champion_name_lookup, cache_dir)


def set_dock_provider(fn):
    tracker.set_dock_provider(fn)


def feed(champion_id, position="", phase="ChampSelect"):
    tracker.feed(champion_id, position, phase)


def sync(root):
    tracker.sync(root)
