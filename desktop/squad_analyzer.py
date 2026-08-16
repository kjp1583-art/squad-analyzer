import os
import sys
import base64
import math
import time
import requests
import urllib3
import urllib.parse
import itertools
import gspread
import threading
import subprocess
import winreg
import webbrowser
import re
import json
import random
import hashlib
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import tkinter.font as tkfont   # 창 크기에 맞춘 UI 폰트 스케일(UF/_UI_FONTS)
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
import ctypes
import theme  # [디자인 토큰] 웹 :root와 동일 팔레트 (DESIGN.md)

try:
    from PIL import Image, ImageTk
    PILLOW_INSTALLED = True
except ImportError:
    PILLOW_INSTALLED = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================================
# 📡 [스쿼드 해체 분석기 V80.9 마스터 빌드 - AI 밸런스 패치 및 버전 오류 수정]
# =========================================================================
CURRENT_VERSION = "82.97"
VERSION_URL = "https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/refs/heads/main/version.txt"
EXE_URL = "https://github.com/kjp1583-art/squad-analyzer/releases/latest/download/squad_analyzer.exe"
ZIP_URL = "https://github.com/kjp1583-art/squad-analyzer/releases/latest/download/squad_analyzer.zip"  # [V81.28] onedir 폴더 zip

# === 비밀값 외부화 (공개 git에 webhook/IPC id를 넣지 않음) =====================
# 우선순위: app_secrets.py(로컬·CI 빌드 시 생성, .gitignore) → 환경변수 → "".
# app_secrets 부재/오류는 전부 흡수(앱이 죽지 않음). 빈 값이면 기존 가드가 발송만 건너뜀.
try:
    import app_secrets as _secrets
except Exception:
    _secrets = None
def _secret(name, default=""):
    val = getattr(_secrets, name, None) if _secrets is not None else None
    return val if val else os.environ.get(name, default)
DISCORD_WEBHOOK_URL   = _secret("DISCORD_WEBHOOK_URL")     # [레거시] 원래 내전기록 메인 채널. 현재 직접 발송 없음(십이귀월→RESULT 이전, 게임시작→GAME_START). CALL/RESULT 미설정 시 폴백용으로만 잔존.
PATCH_WEBHOOK_URL     = _secret("PATCH_WEBHOOK_URL")       # 패치노트 전용 채널
# 2026-07-04 채널 분리: 인원호출/멘션 vs 경기종료/매치결과. 미설정 시 기존 채널로 폴백.
CALL_WEBHOOK_URL      = _secret("CALL_WEBHOOK_URL")   or DISCORD_WEBHOOK_URL   # 인원호출/멘션(호출자 @멘션)
RESULT_WEBHOOK_URL    = _secret("RESULT_WEBHOOK_URL") or DISCORD_WEBHOOK_URL   # 경기종료 알림·매치결과 리포트
# 2026-07-05 채널 분리: 게임시작 알림 전용 채널(미설정 시 CALL 채널로 폴백).
GAME_START_WEBHOOK_URL = _secret("GAME_START_WEBHOOK_URL") or CALL_WEBHOOK_URL # 내전 게임시작 알림 전용
# [v81.63 사장님 지시] 🎯DATA(봇 스코어보드용 구조화 로스터) 전용 채널(#스해분데이터처리소) —
#   설정되면 사람용 #자동내전기록에서 데이터줄 완전 제거, 미설정 시 기존 스포일러 방식 폴백.
DATA_WEBHOOK_URL = _secret("DATA_WEBHOOK_URL")
HOST_NOTICE_WEBHOOK_URL = _secret("HOST_NOTICE_WEBHOOK_URL")   # 사장님 관리 공지(PEAK_SEASONS 누락 명단 등)
DISCORD_IPC_CLIENT_ID = _secret("DISCORD_IPC_CLIENT_ID")   # 로컬 디스코드 IPC 핸드셰이크용
# ===========================================================================
global_discord_id = None                         # 내 디스코드ID (IPC로 1회 획득 후 캐시)

# ===== 출석체크(호스트 전용, Discord REST) =====
DISCORD_API = "https://discord.com/api/v10"
ATTENDANCE_CHANNEL_ID = "1521085084885712916"    # 실클랜 본채널(서버 1095659611777937458)
EMOJI_CHECK = "%E2%9C%85"                         # ✅ URL 인코딩 (참가/출석)
EMOJI_MAKTAN = "%F0%9F%94%9A"                     # 🔚 URL 인코딩 (막판)
BOT_TOKEN = None                                 # 호스트 PC의 token.txt에서만 로드(배포 EXE엔 미포함)
global_bot_user_id = None
ATTENDANCE_CAP = 10                              # 참가 정원
attendance_active = False
attendance_msg_id = None
attend_order = []                                # ✅ 리액션 순서 discord_id 리스트 (참가/대기 순번)
maktan_set = set()                               # 🔚 누른 discord_id (막판)
attend_names = {}                                # discord_id -> 표시명
called_pinged_games = set()                      # 게임당 호출자 멘션 1회
attendance_roster = {}                           # (구) 호환용 — len 표시에 사용
attend_lock = threading.Lock()                   # 큐 상태(order/maktan) 일관 스냅샷용 — 폴링↔게임시작핑 경합 방지

def get_discord_user_id():
    """로컬 디스코드 클라이언트(IPC)에서 현재 로그인 유저의 디스코드ID를 읽음. 실패 시 None.
       (디스코드 켜져있으면 팝업/로그인 없이 바로 ID 획득 — 롤닉↔디스코드 자동매핑용)"""
    import struct, json as _json
    for i in range(10):
        path = r'\\.\pipe\discord-ipc-' + str(i)
        try:
            f = open(path, 'r+b', 0)
        except Exception:
            continue
        try:
            payload = _json.dumps({"v": 1, "client_id": DISCORD_IPC_CLIENT_ID}).encode('utf-8')
            f.write(struct.pack('<II', 0, len(payload)) + payload); f.flush()
            head = f.read(8)
            if len(head) < 8:
                f.close(); continue
            _op, length = struct.unpack('<II', head)
            data = f.read(length); f.close()
            resp = _json.loads(data.decode('utf-8'))
            user = (resp.get("data", {}) or {}).get("user")
            if user and user.get("id"):
                return str(user["id"])
        except Exception:
            try: f.close()
            except Exception: pass
    return None
DOCUMENT_ID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU'
LOL_PATH = r"C:\Riot Games\League of Legends"          # 폴백 기본값(자동탐지 실패 시에만 사용)
LOCKFILE_PATH = os.path.join(LOL_PATH, "lockfile")

_LOL_LOCKFILE_CACHE = None
def _find_lol_lockfile():
    """롤 설치 드라이브가 C:가 아니어도(D:, E: 등) lockfile을 찾는다.
    1순위: RiotClientInstalls.json(%ProgramData%) — 실제 설치경로가 담긴 공식 메타파일.
    2순위: 흔한 드라이브 문자 폴백. 한번 찾으면 캐시(설치경로가 세션 중 바뀌지 않으므로)."""
    global _LOL_LOCKFILE_CACHE
    if _LOL_LOCKFILE_CACHE and os.path.exists(_LOL_LOCKFILE_CACHE):
        return _LOL_LOCKFILE_CACHE
    candidates = []
    try:
        meta_path = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Riot Games", "RiotClientInstalls.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            for k in (meta.get("associated_client") or {}).keys():
                candidates.append(os.path.normpath(k))
    except Exception: pass
    candidates.append(LOL_PATH)
    for drive in "CDEFG":
        candidates.append(f"{drive}:\\Riot Games\\League of Legends")
    seen = set()
    for base in candidates:
        if base in seen: continue
        seen.add(base)
        lf = os.path.join(base, "lockfile")
        if os.path.exists(lf):
            _LOL_LOCKFILE_CACHE = lf
            return lf
    return None

CONFIG_DIR = os.path.join(os.environ.get('APPDATA', ''), 'SquadAnalyzer')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

gui_lock = threading.Lock()
sheet_cache_lock = threading.Lock()

global_sheet_cache = {}
global_cache_time = {}
CACHE_TTL = 240   # [429완화] 60→240초: 시트 읽기 빈도↓ (분당 할당량 60회 공유 압박 완화)

def _gviz_rows_by_gid(gid, timeout=8):
    """공개 gviz CSV(gid+headers=1)로 시트 전체(헤더 포함)를 get_all_values()와 동일 구조·동일 행순서로 반환. 실패 None.
       [V81.47 사장님 지시: 시트 API 폭주 근본차단] gviz는 서비스계정 '읽기' 할당량(분당 60회 공유)과 무관 →
       게임 시작/종료 순간 전 인스턴스 동시 읽기가 여기로 빠져 429 폭주를 원천 제거. 쓰기만 서비스계정.
       ⚠️ gid 필수(sheet=탭이름은 이름 불일치 시 gviz가 '첫 시트(CLASSIC_NORMAL)'로 조용히 폴백해 엉뚱한 데이터
          반환 — 실측 확증. sheet_obj.id(정확한 워크시트 gid)로 고정해 오시트 반환 차단.)
       ⚠️ headers=1 필수(미지정 시 문자열컬럼을 다중행헤더로 오감지해 헤더/행수 붕괴 — 실측)."""
    if gid is None: return None
    try:
        import csv as _csv, io as _io
        txt = _fetch_public_csv(DOCUMENT_ID, gid=gid, headers=1, timeout=timeout)
        rows = list(_csv.reader(_io.StringIO(txt)))
        return rows if rows else None
    except Exception:
        return None

def _svc_get_all_values(sheet_obj, retries=3):
    """서비스계정 직독(gviz 우회) — 최신성/정확성이 꼭 필요한 폴백 경로. 429면 백오프 재시도, 실패 시 None."""
    for _att in range(retries):
        try:
            return sheet_obj.get_all_values()
        except Exception as e:
            if "429" in str(e) and _att < retries - 1:
                time.sleep(1.5 * (_att + 1)); continue
            return None
    return None

def get_sheet_data_cached(sheet_obj, force=False, prefer_service=False):
    """읽기 우선순위: (1)메모리캐시 (2)공개 gviz(할당량0, gid고정) (3)서비스계정 폴백.
       prefer_service=True면 gviz를 건너뛰고 서비스계정 직독(행번호 정확성이 중요한 finalize 쓰기 전용).
       [V81.47 리뷰반영] 네트워크 fetch는 락 밖에서 수행(다른 스레드 읽기 블로킹 방지). 동시 fetch는 gviz 할당량0라 무해."""
    now = time.time()
    title = sheet_obj.title
    # 1) 신선 캐시면 즉시 반환(락 짧게 유지)
    with sheet_cache_lock:
        cached = global_sheet_cache.get(title)
        if not force and cached is not None and (now - global_cache_time.get(title, 0) <= CACHE_TTL):
            return cached
        prev_len = len(cached) if cached else 0
    # 2) 실제 fetch는 락 밖에서(gviz 8s+폴백 동안 타 스레드 블록 방지)
    result = None
    if not prefer_service:
        g = _gviz_rows_by_gid(getattr(sheet_obj, "id", None))
        # 잘림/부분응답 방어: 직전 캐시의 절반 미만이면 의심 → 서비스계정 폴백.
        #   직전 기준이라 정당한 행 감소(SOLO_RANK clear+재작성/시즌리셋)에도 1회 폴백 후 자연 회복(역대max로 고정 안 됨).
        if g is not None and (prev_len == 0 or len(g) >= max(1, int(prev_len * 0.5))):
            result = g
    if result is None:
        result = _svc_get_all_values(sheet_obj)
    # 3) 저장(락 짧게)
    with sheet_cache_lock:
        if result is not None:
            global_sheet_cache[title] = result
            global_cache_time[title] = now
            return result
        # 서비스까지 실패: prefer_service(행번호 정확성 필요)면 stale 대신 []→호출부 재시도 유도(엉뚱한 행 쓰기 방지)
        if prefer_service:
            return []
        return global_sheet_cache.get(title, [])

def invalidate_sheet_cache(title):
    with sheet_cache_lock:
        global_cache_time[title] = 0

def load_config():
    default_cfg = {"windows_startup": False, "lol_auto_show": True, "minimize_to_tray": False,
                   "pos_view_default": True,   # [v82.37] 대기실 모스트 표시 기본값(True=현재포지션)
                   "show_synergy": True}       # 🧩 우측 시너지 3칸(고승률·역시너지·천적) 표시
    # [v82.30] lol_auto_show 기본값을 설정 UI(True)와 일치시킴
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                default_cfg.update(json.load(f))
    except Exception: pass
    return default_cfg

def save_config(cfg):
    try:
        if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f)
    except Exception: pass

APP_CONFIG = load_config()
global_champ_map = {}

# 🎨 [v81.93] '내 꾸미기' — 분석기 로컬 전환(내 화면·내 칸에만 적용, 봇/공유 무관). config.json에 저장.
#   T1 세트(엠블럼 PNG는 번들). 변형: 없음/레드/골드/블랙. 순환 버튼으로 전환.
# 🎨 [v82.2] T1_set의 프레임 시안(t1_red_black_frame/t1_black_frame/t1_white_frame.png) 재현:
#    베젤(테두리+슬롯 바탕) + 화이트 패널 + 우측 T1 로고. (Tk 위젯이라 이미지 원본 대신 스타일로 재현)
# 🅣 [v82.18 사장님 지시] 프레임 꾸미기 전면 폐기 → '엠블럼' 시스템으로 전환.
#    봇 /상점 구매·장착(서버 검증) → /cosmetics "frame" 값(variant) → 그 유저 칸 '맨 우측 하단'에 엠블럼 로고만 표시.
# [v82.23] LCK 팀 엠블렘 확장 — 사장님 제공 teamlogo 이미지(160x63 알파). variant 키 = 봇 FRAME_ITEMS와 1:1.
T1_EMBLEM_FILES = {
    "t1_red": "T1_red_emblem.png",
    "geng": "geng.png", "hle": "hle.png", "dk": "DK.png", "kt": "klt.png", "drx": "drx.png",
    "ns": "nongsim.png", "dn": "DN.png", "bnk": "BNK.png", "brion": "brion.png",
}
T1_FRAME_PAD = (13, 2, 4)    # 슬롯 안쪽 여백(좌우, 상, 하) — 프레임 폐기로 하단 로고 밴드 여백 불필요(세로 공간 회수)

# 🖥 [v82.17] 창 크기 프리셋(설정에서 선택, config.json `win_preset` 저장). auto=화면 맞춤(기존 동작), max=최대화.
WIN_PRESETS = {"compact": (1280, 950), "standard": (1420, 1045), "wide": (1560, 1150)}
WIN_PRESET_CHOICES = [("auto", "자동 (화면 맞춤)"), ("compact", "컴팩트 1280×950"), ("standard", "표준 1420×1045"),
                      ("wide", "와이드 1560×1150"), ("max", "최대화 (전체 화면)")]

# 🔥 [V80.9] 패치 버전 동기화 최적화
CS_REFRESH_SEC = 8      # 🧭 밴픽 진입 후 이 시간 동안은 로비를 더 읽어 포지션을 정정(관전→플레이어 이동 대응)
DDRAGON_VERSION = "14.23.1"
PATCH_VERSION_SHORT = "14.23"

POSITION_TRANSLATE_KOR = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서폿", "NONE": "선택안함"}
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER", "UNRANKED"]
CHAMP_KOR_TO_ENG = {}
GLOBAL_NUMERIC_CHAMP_MAP = {}

try:
    ver_req = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=3)
    if ver_req.status_code == 200: 
        DDRAGON_VERSION = ver_req.json()[0]
        match = re.search(r'^(\d+\.\d+)', DDRAGON_VERSION)
        if match:
            PATCH_VERSION_SHORT = match.group(1)
        else:
            PATCH_VERSION_SHORT = ".".join(DDRAGON_VERSION.split(".")[:2]) if "." in DDRAGON_VERSION else DDRAGON_VERSION
        
    if DDRAGON_VERSION:
        champ_json_url = f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/data/ko_KR/champion.json"
        c_req = requests.get(champ_json_url, timeout=3)
        if c_req.status_code == 200:
            c_data = c_req.json().get("data", {})
            for eng_name, c_info in c_data.items():
                kor_name = c_info.get("name", "")
                c_id = c_info.get("key", "")
                # 🚫 [2026-08-01 사장님 제보] '롤 클래식' 항목 제외 — 초상화가 2009년 그림으로 뜨던 원인.
                #   라이엇이 클래식 모드를 내며 Jade_* (key 60000번대) 항목을 추가했는데 한글명이
                #   정규 챔피언과 같아서, 한글명이 키인 맵을 뒤에 오는 Jade 쪽이 덮어썼다.
                if str(eng_name).startswith("Jade_") or (str(c_id).isdigit() and int(c_id) >= 60000):
                    continue
                if kor_name and eng_name:
                    CHAMP_KOR_TO_ENG[kor_name] = eng_name
                    CHAMP_KOR_TO_ENG[kor_name.replace(" ", "")] = eng_name
                if c_id.isdigit() and kor_name:
                    global_champ_map[int(c_id)] = {"kor": kor_name, "eng": eng_name}
                    GLOBAL_NUMERIC_CHAMP_MAP[int(c_id)] = kor_name.replace(" ", "")
except Exception: pass

gui_data = {
    "status": "📡 LCU 시스템 탐색 중...",
    "bans": "🚫 10밴 현황: 대기 중",
    "blue": [], "red": [],
    "pos_synergy": " - 특이사항 없음 (안정적)",
    "neg_synergy": " - 특이사항 없음 (평온)",
    "nemesis_synergy": " - 상성 매칭 없음 (평온)",
    "achievements": [],
    "blue_win_rate": 50, "red_win_rate": 50,
    "blue_ban_advice_list": [], "red_ban_advice_list": [],
    "hof_classic": {"global_stats": {}, "patches": ["전체 (ALL)"]},
    "hof_aram": {"global_stats": {}, "patches": ["전체 (ALL)"]}, 
    "ad_image_obj": None, 
    "ad_link": "https://link.coupang.com/a/epBR4G2abY",
    "ad_text": "✨ 스폰서 배너 로딩 중... ✨",
    "ad_list": [], "ad_index": 0, "last_ad_time": 0,
    "is_hidden": False
}

global_captured_bans = []
global_user_ban_map = {}
frozen_user_bans = {}
global_pick_order_map = {}   # 🥇 [v82.26] 픽순서(1~10) — puuid → 완료된 pick 액션 등장 순서(드래프트 모드만)
frozen_pick_order = {}
# 🎭 [v82.30] 밴픽 확정 챔피언 — puuid → championId. 라이브 playerlist는 '니코 변신' 시 변신 대상을 반환하므로
#   (니코는 패시브로 레벨1부터 변신 가능) 기록 소스로 쓰면 챔프가 틀리고, 같은 팀 동일 챔프 충돌까지 유발.
global_lock_champ_map = {}
frozen_lock_champ = {}
# 🎭 [v82.30] 인게임 '변신 형태' 표시명 → 원래 챔피언. 밴픽 확정 데이터가 없을 때(게임 도중 분석기 실행 등)의 2차 방어선.
#   실제 사고: 나르가 메가나르 상태로 종료 → '메가나르'로 기록돼 나르 전적과 분리됨.
_TRANSFORM_NAME_FIX = {
    "메가나르": "나르", "megagnar": "Gnar", "gnarbig": "Gnar",
    "에그니비아": "애니비아", "eggnivia": "Anivia", "aniviaegg": "Anivia", "알니비아": "애니비아",
}
def _fix_transform_name(n):
    """변신 표시명이면 원래 챔피언명으로 되돌린다(대소문자·공백 무시). 아니면 그대로."""
    if not n: return n
    return _TRANSFORM_NAME_FIX.get(str(n).strip(), _TRANSFORM_NAME_FIX.get(str(n).replace(" ", "").lower(), n))
champion_image_cache = {}
global_spreadsheet = None
global_alt_map = {}
frozen_bans_str = ""
global_ingame_names = {}
global_puuid_fallback_map = {}
has_logged_execution = False   # 🔥 실행횟수: 프로세스당 1회만 증가(모듈 전역 → 스레드 재시작에도 유지)

def get_main_name(name):
    if not name: return ""
    clean_name = str(name).split('#')[0].strip().lower()
    return global_alt_map.get(clean_name, str(name).split('#')[0].strip())

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
        path = os.path.join(base_path, relative_path)
        if os.path.exists(path): return path
    except Exception: pass
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base_path, relative_path)

def copy_id_to_clipboard(window_root, button_widget, full_name):
    if not full_name or full_name in ["Wait...", "대기 중...", "알 수 없는 유저"]: return
    clean_name = full_name.replace("🤖 ", "").replace(" 봇", "").strip()
    window_root.clipboard_clear()
    window_root.clipboard_append(clean_name)
    button_widget.config(text="✅", fg=theme.SUCCESS)
    window_root.after(1000, lambda: button_widget.config(text="📋", fg=theme.TEXT))

def open_opgg_profile(full_name):
    if not full_name or full_name in ["Wait...", "대기 중...", "알 수 없는 유저"]: return
    clean_name = full_name.replace("🤖 ", "").replace(" 봇", "").strip()
    if "#" in clean_name:
        name_part, tag_part = clean_name.split("#", 1)
        riot_id = name_part.strip() + "-" + tag_part.strip()
    else:
        riot_id = clean_name
    # deeplol.gg 로 검색 (예: /summoner/KR/맛동산장인  유미-Teana, URL 인코딩)
    url = "https://www.deeplol.gg/summoner/KR/" + urllib.parse.quote(riot_id)
    webbrowser.open(url)

def open_multisearch(team_data):
    if not team_data: return
    names = []
    for p, _ in team_data:
        n = p.get('name', '')
        if n and not n.startswith("Wait") and not n.startswith("대기 중") and not n.startswith("알 수") and "봇" not in n:
            names.append(n.replace("🤖 ", "").split('#')[0].strip())
    if names:
        url = "https://www.op.gg/multisearch/kr?summoners=" + urllib.parse.quote(",".join(names))
        webbrowser.open(url)

def _rotation_label(seq):
    # 1경기 형탐 · 2경기 동탐 · 3경기 조율 (3판 로테이션 반복)
    return ("형탐", "동탐", "조율")[(int(seq) - 1) % 3]

_NB_TEAMS = {"blue": [], "red": []}   # 🚫 [v82.46] 노밴 진영 판정용 — 리포트 발송 직전 루프가 팀 로스터를 복사해 둠

# 🏅 [v82.48 사장님 지시] 시트 전체 기록 기반 '게임 간' 타이틀 자동판정 —
#   한 게임 데이터만으로는 못 잡던 것들(하루 판수·연승·당일 전 라인 승리·연속 맞라이너 전승)을
#   결과 리포트 직전에 시트에서 계산해 덧붙인다. 판정 실패는 무해(빈 리스트 반환).
#   ※ '복수자'는 미토 3판2선승 구조상 매 시리즈 자연발생이라 자동판정 제외(2026-07-28 사장님 판단).
def cross_game_titles(sheet_rows, this_gid):
    out = []
    try:
        if not sheet_rows or len(sheet_rows) < 2: return out
        H = sheet_rows[0]
        ci = lambda n: H.index(n) if n in H else -1
        c_gid, c_date, c_name, c_pu = ci("게임ID"), ci("날짜"), ci("소환사명"), ci("PUUID")
        c_pos, c_res, c_side = ci("포지션"), ci("결과"), ci("진영")
        if min(c_gid, c_date, c_name, c_res) < 0: return out
        rows = [r for r in sheet_rows[1:] if len(r) > max(c_gid, c_date, c_name, c_res, c_pos, c_side)]
        key = lambda r: (str(r[c_pu]).strip().lower() if c_pu >= 0 and str(r[c_pu]).strip() else str(r[c_name]).strip())
        disp = lambda r: str(r[c_name]).split("#")[0].strip()

        # 이 게임 참가자 · 게임 순서(시트 기록 순 = 시간순)
        gids = []
        for r in rows:
            g = str(r[c_gid]).strip()
            if g and (not gids or gids[-1] != g): gids.append(g)
        try: gi_now = gids.index(str(this_gid).strip())
        except ValueError: gi_now = len(gids) - 1
        cur = [r for r in rows if str(r[c_gid]).strip() == str(this_gid).strip()]
        if not cur: return out
        today = str(cur[0][c_date])[:10]

        by_player_today = {}
        for r in rows:
            if str(r[c_date])[:10] != today: continue
            by_player_today.setdefault(key(r), []).append(r)

        for r in cur:
            k, nm = key(r), disp(r)
            mine = by_player_today.get(k, [])
            played = [x for x in mine if str(x[c_res]) in ("승리", "패배")]
            # ① 하루 종일 할 수 있어 — 당일 내전 20판 달성(달성 판에서 1회)
            if len(played) == 20 and str(r[c_res]) in ("승리", "패배"):
                out.append(f"🕛 [하루 종일 할 수 있어] 하루 내전 20판 달성 ({nm})")
            # ② 다재다능 — 당일 5개 라인 각각 1승 이상
            if c_pos >= 0 and str(r[c_res]) == "승리":
                wins_pos = {str(x[c_pos]).strip() for x in played if str(x[c_res]) == "승리"}
                if {"탑", "정글", "미드", "원딜", "서폿"} <= wins_pos:
                    out.append(f"🎭 [다재다능] 하루 안에 모든 라인에서 1승씩 달성 ({nm})")
            # ③ 모두가 내 발아래 — 10연승(이번 판 포함, 시트 전체 기준)
            if str(r[c_res]) == "승리":
                streak = 0
                for g in reversed(gids[:gi_now + 1]):
                    row = next((x for x in rows if str(x[c_gid]).strip() == g and key(x) == k
                                and str(x[c_res]) in ("승리", "패배")), None)
                    if row is None: continue
                    if str(row[c_res]) == "승리": streak += 1
                    else: break
                if streak == 10:
                    out.append(f"👑 [모두가 내 발아래] 내전 10연승 달성 ({nm})")
            # ④ 스토커 — 최근 3게임 연속 같은 맞라이너와 붙어 전승
            if c_pos >= 0 and c_side >= 0 and str(r[c_res]) == "승리" and gi_now >= 2:
                opps, ok = [], True
                for g in gids[gi_now - 2: gi_now + 1]:
                    me = next((x for x in rows if str(x[c_gid]).strip() == g and key(x) == k), None)
                    if me is None or str(me[c_res]) != "승리": ok = False; break
                    o = next((x for x in rows if str(x[c_gid]).strip() == g
                              and str(x[c_pos]).strip() == str(me[c_pos]).strip()
                              and str(x[c_side]).strip() != str(me[c_side]).strip()), None)
                    if o is None: ok = False; break
                    opps.append(key(o))
                if ok and len(opps) == 3 and len(set(opps)) == 1:
                    o_nm = next((disp(x) for x in rows if key(x) == opps[0]), "상대")
                    out.append(f"🕵 [스토커] 3판 연속 같은 맞라이너({o_nm})와 만나 전부 승리 ({nm})")
    except Exception as _e:
        print(f"[titles] 게임간 타이틀 판정 생략: {type(_e).__name__}", flush=True)
    return out

def broadcast_to_discord_webhook(content_text):
    if not RESULT_WEBHOOK_URL or RESULT_WEBHOOK_URL.startswith("여기에"): return
    if _OUTDATED: return   # 🛑 킬스위치: 신버전 감지된 구버전은 발송 금지
    def txt_thread():
        try:
            makpan = ""
            try:   # 🔚 [v82.41] 막판 선언 감지분을 결과에 부착
                if _MAKPAN.get("decls"):
                    makpan = chr(10) + f"🔚 막판 선언: {', '.join(_MAKPAN['decls'])} ({len(_MAKPAN['decls'])}명)"
            except Exception: pass
            block = "```md" + chr(10) + str(content_text) + chr(10) + "```" + makpan   # 봇용 풀포맷(기존 구조 유지)
            # ① [2026-08-07 사장님 지시 — 메시지 2개→1개] 같은 인스턴스가 보낸 최근 '경기 종료' 메시지가 있으면
            #    그 메시지를 '편집'해 리포트를 이어붙인다 → 사람 채널은 한 박스. (편집은 봇 on_message 미발화라
            #    봇 신호는 아래 ②로 별도 보전. 다른 인스턴스가 마감한 판은 id가 없어 기존처럼 새 메시지 = 안전 강하)
            merged = False
            try:
                if _END_MSG.get("id") and time.time() - float(_END_MSG.get("at", 0)) < 1800:
                    _base = RESULT_WEBHOOK_URL.split("?")[0]
                    _one = ("```md" + chr(10) + _END_MSG.get("content", "") + chr(10)
                            + str(content_text) + makpan + chr(10) + "```")
                    pr = requests.patch(f"{_base}/messages/{_END_MSG['id']}", json={"content": _one}, timeout=8)
                    merged = pr.status_code < 400
            except Exception: pass
            # ② 봇 신호(종료 2차 트리거·타이틀 자동부여·버전서명 파싱)는 풀포맷 그대로 —
            #    병합 성공 시 DATA 채널로(봇은 채널 무관 마커 감지), 실패·DATA 미설정 시 기존처럼 결과 채널로.
            full = (f"🏆 **[스쿼드 내전 매치 결과 리포트]** 🏆 v{CURRENT_VERSION}" + chr(10) + block)
            _has_data = DATA_WEBHOOK_URL and not DATA_WEBHOOK_URL.startswith("여기에")
            _bot_url = DATA_WEBHOOK_URL if (merged and _has_data) else (RESULT_WEBHOOK_URL if not merged else None)
            if _bot_url:
                r = requests.post(_bot_url, json={"content": full}, timeout=5)
                if r.status_code >= 400: print(f"[웹훅 실패] 매치결과 {r.status_code}: {r.text[:150]}", flush=True)
            elif merged:
                print("[웹훅] 매치결과 — 종료 메시지에 병합(한 박스) · DATA 채널 미설정이라 봇 신호 생략 불가 상황 아님", flush=True)
        except Exception as e: print(f"[웹훅 예외] 매치결과: {e}", flush=True)
    threading.Thread(target=txt_thread, daemon=True).start()

def broadcast_game_start_webhook(content_text, data_text=None):
    # 🎬 로딩 진입(InProgress) 시 발송. 봇이 'on_message'로 "내전 게임 시작" 마커를 감지해 호출자 멘션.
    # 2026-07-05: 게임시작 전용 채널(GAME_START_WEBHOOK_URL)로 발송. 봇은 채널 무관·내용마커로 감지하므로 안전.
    # [v81.63] data_text가 있으면 DATA 전용 채널(#스해분데이터처리소)로 별도 발송 — 사람용 기록엔 데이터줄 없음.
    #   봇은 두 메시지 모두 '내전 게임 시작' 마커로 처리(디바운스로 1회만 시작처리, 로스터 파싱은 디바운스 앞이라 어느 쪽이든 반영).
    _url = GAME_START_WEBHOOK_URL
    if not _url or _url.startswith("여기에"): return
    if _OUTDATED: return   # 🛑 킬스위치: 신버전 감지된 구버전은 발송 금지
    # 🚫🔚 [2026-07-25 사장님 지시] 노밴·막판 부착은 시작기록이 아니라 매치 결과 리포트(broadcast_to_discord_webhook)에서.
    def txt_thread():
        # [v81.62] 발송 재시도 3회(3~7s 백오프) — 시작 기록은 발송자가 append 승자 1명뿐이라 일시 네트워크 오류=기록 유실이던 단일발송 취약점 보강.
        # [v81.64 사장님 지시] 자동내전기록은 사람용 3줄(경기번호·블루·레드)만 — 🎬헤더·버전인증 줄 제거.
        #   봇의 시작신호 마커('내전 게임 시작')·버전서명이 담긴 풀 포맷은 DATA 채널로만 발송(봇은 채널 무관 감지라 안전).
        #   ⚠️ DATA 웹훅 미설정 폴백에서는 자동내전기록이 유일한 신호 경로 → 기존 풀 포맷 유지(마커 제거 금지).
        def _framed(_body):
            return ("🎬 **[스쿼드 내전 게임 시작]** 🎬  ⏰ " + time.strftime("%H:%M") + chr(10)
                    + str(_body) + chr(10) + f"*정찰 시스템 V{CURRENT_VERSION} 자동 인증*")
        if data_text and DATA_WEBHOOK_URL and not DATA_WEBHOOK_URL.startswith("여기에"):
            targets = [(_url, str(content_text)),               # 사람용: 본문만(3줄)
                       (DATA_WEBHOOK_URL, _framed(data_text))]  # 봇용: 마커+본문+DATA+버전
        else:
            targets = [(_url, _framed(content_text))]           # 폴백: 기존 5줄(+스포일러 DATA)
        for _u, _c in targets:
            for _wtry in range(3):
                try:
                    r = requests.post(_u, json={"content": _c}, timeout=8)
                    if r.status_code < 400: break
                except Exception: pass
                time.sleep(3 + random.uniform(0, 4))
    threading.Thread(target=txt_thread, daemon=True).start()

def _noban_of_side(players):
    """[2026-07-29 사장님 지시] 이 진영이 실제로 픽한 노밴 챔피언 목록.
       경기 종료 로스터에 팀별로 붙인다 — 선언이 없으면 'X'."""
    picked = []
    try:
        for c in (_NOBAN.get("decls") or []):
            for _pl in (players or []):
                _pu = str(_pl.get("puuid") or "").strip().lower() if isinstance(_pl, dict) else ""
                try: _cid = int(_pl.get("championId") or 0) or int(global_lock_champ_map.get(_pu) or 0)
                except Exception: _cid = 0
                _kor = (global_champ_map.get(_cid) or {}).get("kor") or GLOBAL_NUMERIC_CHAMP_MAP.get(_cid, "")
                if _cid and _kor == c and c not in picked:
                    picked.append(c)
    except Exception: pass
    return ", ".join(picked) if picked else "X"


def broadcast_game_end_webhook(roster_text):
    # 🏁 [2026-07-07] 종료 감지(eog) 즉시 발송 — finalize 성공/_is_appender와 독립.
    #   봇이 '경기 종료' 마커로 종료 트리거(막판 제거·호출→시작대기). 여러 인스턴스가 보내도 봇이 팀 epoch 가드로 게임당 1회만 처리.
    #   [v81.62 사장님 지시] 발송처를 게임시작 채널(#자동내전기록)에서 결과 채널(#내전결과리포트)로 이전 —
    #   자동내전기록엔 '게임 시작' 기록만, 경기결과(종료·리포트)는 내전결과리포트로 모음. 봇은 채널 무관·내용마커 감지라 안전.
    _url = RESULT_WEBHOOK_URL
    if not _url or _url.startswith("여기에"): return
    if _OUTDATED: return   # 🛑 킬스위치: 신버전 감지된 구버전은 발송 금지
    def txt_thread():
        # [v81.62] 발송 재시도 3회 — 종료신호도 발송자 1명(append 승자)이라 동일 보강.
        # [2026-08-07 사장님 지시] 버전은 헤더 시간 옆에 V표기만(하단 '자동 인증' 줄 제거 — 봇 _VER_SIG_RE가
        #   이 헤더 형식도 인식하도록 봇과 동시 패치). ?wait=true 로 메시지 id를 받아 두면
        #   매치 결과 리포트가 이 메시지를 '편집'으로 이어붙여 사람 채널이 한 박스가 된다.
        # [2026-08-07 사장님 지시] 메시지 전체를 ```md 코드박스 하나로 — 편집 병합 때도 같은 박스 안에 이어붙인다
        _body = ("🏁 **[스쿼드 내전 경기 종료]** 🏁  ⏰ " + time.strftime("%H:%M")
                 + f" · V{CURRENT_VERSION}" + chr(10) + str(roster_text))
        msg = "```md" + chr(10) + _body + chr(10) + "```"
        _wu = _url + ("&wait=true" if "?" in _url else "?wait=true")
        for _wtry in range(3):
            try:
                r = requests.post(_wu, json={"content": msg}, timeout=8)
                if r.status_code < 400:
                    try:
                        _END_MSG.update({"id": str((r.json() or {}).get("id") or ""), "at": time.time(), "content": _body})
                    except Exception: pass
                    return
            except Exception: pass
            time.sleep(3 + random.uniform(0, 4))
    threading.Thread(target=txt_thread, daemon=True).start()

_END_MSG = {"id": "", "at": 0.0, "content": ""}   # 최근 '경기 종료' 웹훅 메시지(리포트 편집 병합용)

def broadcast_plain_webhook(content_text):
    # 래퍼 없이 한 줄 그대로 발송 (간결한 종료 알림용)
    if not RESULT_WEBHOOK_URL or RESULT_WEBHOOK_URL.startswith("여기에"): return
    if _OUTDATED: return   # 🛑 킬스위치: 신버전 감지된 구버전은 발송 금지
    def txt_thread():
        try:
            r = requests.post(RESULT_WEBHOOK_URL, json={"content": str(content_text)}, timeout=5)
            if r.status_code >= 400: print(f"[웹훅 실패] 종료알림 {r.status_code}: {r.text[:150]}", flush=True)
        except Exception as e: print(f"[웹훅 예외] 종료알림: {e}", flush=True)
    threading.Thread(target=txt_thread, daemon=True).start()

# ===== 출석체크: Discord REST (호스트 전용) =====
def load_bot_token():
    """token.txt(호스트 PC 로컬 파일)에서 봇 토큰 로드. 없으면 None(=호스트 아님 → 출석 기능 비활성)."""
    global BOT_TOKEN
    if BOT_TOKEN: return BOT_TOKEN
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    for p in [resource_path("token.txt"),
              os.path.join(base, "token.txt"),
              os.path.join(base, "..", "SquadBot", "token.txt"),
              r"C:\SquadBot\token.txt"]:
        try:
            if p and os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    t = f.read().strip()
                if t: BOT_TOKEN = t; return BOT_TOKEN
        except Exception: pass
    return None

def _discord_headers():
    return {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

def discord_get_bot_user_id():
    global global_bot_user_id
    if global_bot_user_id: return global_bot_user_id
    try:
        r = requests.get(f"{DISCORD_API}/users/@me", headers=_discord_headers(), timeout=8)
        if r.status_code == 200: global_bot_user_id = str(r.json().get("id", ""))
    except Exception: pass
    return global_bot_user_id

def discord_post_message(content):
    try:
        r = requests.post(f"{DISCORD_API}/channels/{ATTENDANCE_CHANNEL_ID}/messages",
                          headers=_discord_headers(), json={"content": content}, timeout=8)
        if r.status_code == 200: return r.json().get("id")
    except Exception: pass
    return None

def discord_add_reaction(mid, emoji_q=EMOJI_CHECK):
    try:
        requests.put(f"{DISCORD_API}/channels/{ATTENDANCE_CHANNEL_ID}/messages/{mid}/reactions/{emoji_q}/@me",
                     headers=_discord_headers(), timeout=8)
    except Exception: pass

def discord_get_reactors(mid, emoji_q=EMOJI_CHECK):
    out = []
    try:
        r = requests.get(f"{DISCORD_API}/channels/{ATTENDANCE_CHANNEL_ID}/messages/{mid}/reactions/{emoji_q}?limit=100",
                         headers=_discord_headers(), timeout=8)
        if r.status_code == 200:
            for u in r.json(): out.append((str(u.get("id")), u.get("username", "")))
    except Exception: pass
    return out

def discord_edit_message(mid, content):
    try:
        requests.patch(f"{DISCORD_API}/channels/{ATTENDANCE_CHANNEL_ID}/messages/{mid}",
                       headers=_discord_headers(), json={"content": content}, timeout=8)
    except Exception: pass

def load_discord_nick_map():
    """ONLINE_USERS에서 {discord_id: 롤닉} (큐 표시용). 실패 시 빈 dict → username 폴백."""
    out = {}
    try:
        if not global_spreadsheet: return out
        ws = global_spreadsheet.worksheet("ONLINE_USERS")
        rows = get_sheet_data_cached(ws, force=False)
        if not rows: return out
        h = rows[0]
        ni = h.index("닉네임") if "닉네임" in h else 0
        di = h.index("디스코드ID") if "디스코드ID" in h else 4
        for r in rows[1:]:
            if len(r) > max(ni, di):
                did = str(r[di]).strip(); nm = str(r[ni]).strip().split('#')[0]
                if did.isdigit() and nm: out[did] = nm
    except Exception: pass
    return out

def compute_queue():
    """attend_order(✅순서)+maktan_set(🔚)+정원 → (참가, 막판, 호출, 대기) discord_id 리스트."""
    with attend_lock:                            # order·maktan을 한 번에 스냅샷(분리대입 경합 방지)
        order = list(attend_order)
        mset = set(maktan_set)
    cap = ATTENDANCE_CAP
    chamga = order[:cap]
    overflow = order[cap:]
    maktan = [d for d in chamga if d in mset]
    hochul = overflow[:len(maktan)]              # 막판 1명당 대기 1명을 호출로 승격
    daegi = overflow[len(maktan):]
    return chamga, maktan, hochul, daegi

def queue_display_text():
    chamga, maktan, hochul, daegi = compute_queue()
    nick = load_discord_nick_map()
    def nm(d): return nick.get(d) or attend_names.get(d) or ("유저" + d[-4:] if d else "?")
    def names(lst): return ", ".join(nm(d) for d in lst) if lst else "-"
    L = []
    L.append("🎮 **내전 큐** (정원 " + str(ATTENDANCE_CAP) + ")")
    L.append("참가하려면 ✅ · 막판(이번 판 후 나감)이면 🔚")
    L.append("")
    L.append("🟢 **참가** (" + str(len(chamga)) + "/" + str(ATTENDANCE_CAP) + "): " + names(chamga))
    if maktan: L.append("🔚 **막판** (" + str(len(maktan)) + "): " + names(maktan))
    if hochul: L.append("📣 **호출** (" + str(len(hochul)) + "): " + names(hochul) + "  ← 다음 판 대기!")
    if daegi: L.append("⏳ **대기** (" + str(len(daegi)) + "): " + names(daegi))
    return "\n".join(L)

def _attendance_poll_loop():
    global attend_order, maktan_set, attend_names, attendance_roster
    while attendance_active and attendance_msg_id:
        try:
            bot_id = discord_get_bot_user_id()
            order, names = [], {}
            for uid, uname in discord_get_reactors(attendance_msg_id, EMOJI_CHECK):
                if bot_id and uid == bot_id: continue   # 봇 자신 제외
                if uid not in names: order.append(uid)
                names[uid] = uname or names.get(uid, "")
            mset = set()
            for uid, uname in discord_get_reactors(attendance_msg_id, EMOJI_MAKTAN):
                if bot_id and uid == bot_id: continue
                mset.add(uid)
                if uid not in names: names[uid] = uname or ""
            with attend_lock:                       # order·maktan 동시 공개(compute_queue가 중간 상태 못 보게)
                attend_order = order
                maktan_set = mset
                attend_names = names
                attendance_roster = {d: names.get(d, "") for d in order}   # 호환(len 표시)
            discord_edit_message(attendance_msg_id, queue_display_text())   # 메시지 라이브 갱신(락 밖)
        except Exception: pass
        for _ in range(12):
            if not attendance_active: break
            time.sleep(1)

def start_attendance():
    """내전 큐 메시지 게시 + ✅·🔚 부착 + 폴링 시작. (성공여부, 메시지) 반환."""
    global attendance_active, attendance_msg_id, attend_order, maktan_set, attend_names, called_pinged_games, attendance_roster
    if not load_bot_token():
        return False, "token.txt가 없어 출석 기능을 쓸 수 없습니다 (호스트 전용)."
    attend_order = []; maktan_set = set(); attend_names = {}; called_pinged_games = set(); attendance_roster = {}
    mid = discord_post_message(queue_display_text())
    if not mid:
        return False, "메시지 게시 실패 — 봇이 채널에 있고 권한이 있는지 확인하세요."
    discord_add_reaction(mid, EMOJI_CHECK)
    discord_add_reaction(mid, EMOJI_MAKTAN)
    attendance_msg_id = mid
    attendance_active = True
    threading.Thread(target=_attendance_poll_loop, daemon=True).start()
    return True, "내전 큐 시작됨"

def stop_attendance():
    global attendance_active
    attendance_active = False

# ===== 🎮 롤 로비 자동초대 폴러 (2026-07-06) =====
# 봇 /invites(팀초대 버튼 요청) 폴링 → '내 LCU 현재소환사 == 요청자'(=내가 로비 호스트)면
# 같은 조 나머지 9명을 LCU(/lol-lobby/v2/lobby/invitations)로 실제 초대. (요청자 아니면 조용히 무시)
INVITE_BRIDGE_URL = "https://hth3thmujs.apps.bot-hosting.cloud/invites"   # 봇 공개엔드포인트(노드 이전 시 변경)
VOICE_BRIDGE_URL = "https://hth3thmujs.apps.bot-hosting.cloud/voice"      # 봇: 요청자가 들어가 있는 음성방 인원
_processed_invites = {}   # invite_id -> 처리시각(180s 보관, 봇 TTL 120s보다 길게 → 재발동 방지)

def _inv_norm(s):
    return (s or "").replace(" ", "").strip().lower()

def _inv_lcu_creds():
    lf = _find_lol_lockfile()
    if not lf: return None
    try:
        parts = open(lf).read().split(":")   # name:pid:port:password:protocol
        port, pw = parts[2], parts[3]
    except Exception:
        return None
    tok = base64.b64encode(("riot:" + pw).encode()).decode()
    return (f"https://127.0.0.1:{port}",
            {"Authorization": "Basic " + tok, "Accept": "application/json", "Content-Type": "application/json"})

def _inv_current_riot_id(base, h):
    try:
        j = requests.get(base + "/lol-summoner/v1/current-summoner", headers=h, verify=False, timeout=3).json()
        gn = j.get("gameName") or j.get("displayName"); tl = j.get("tagLine")
        return f"{gn}#{tl}" if tl else gn
    except Exception:
        return None

def _inv_resolve_summoner_id(base, h, riot_id):
    """롤닉#태그 → summonerId (LCU 여러 경로 순차 시도). 실패 None. (테스터로 검증된 경로 그대로)"""
    gn, tl = (riot_id.rsplit("#", 1) + [None])[:2] if "#" in (riot_id or "") else (riot_id, None)
    if tl:   # A) alias/lookup → puuid → summoner
        try:
            r = requests.get(base + f"/lol-summoner/v1/alias/lookup?gameName={gn}&tagLine={tl}", headers=h, verify=False, timeout=3)
            if r.ok and r.json().get("puuid"):
                s = requests.get(base + f"/lol-summoner/v2/summoners/puuid/{r.json()['puuid']}", headers=h, verify=False, timeout=3)
                if s.ok and s.json().get("summonerId"): return s.json()["summonerId"]
        except Exception: pass
        try:   # B) aliases POST
            r = requests.post(base + "/lol-summoner/v1/summoners/aliases", headers=h,
                              data=json.dumps([{"gameName": gn, "tagLine": tl}]), verify=False, timeout=3)
            if r.ok and isinstance(r.json(), list) and r.json() and r.json()[0].get("summonerId"):
                return r.json()[0]["summonerId"]
        except Exception: pass
    try:   # C) 구형 name 조회
        r = requests.get(base + f"/lol-summoner/v1/summoners?name={gn}", headers=h, verify=False, timeout=3)
        if r.ok and isinstance(r.json(), dict) and r.json().get("summonerId"):
            return r.json()["summonerId"]
    except Exception: pass
    return None

def _lobby_invite_poll_loop():
    while True:
        try:
            try:
                invites = requests.get(INVITE_BRIDGE_URL, timeout=6).json().get("invites", [])
            except Exception:
                invites = []
            now = time.time()
            for k in [k for k, v in list(_processed_invites.items()) if now - v > 180]:
                _processed_invites.pop(k, None)                       # 오래된 처리기록 정리
            fresh = [iv for iv in invites if iv.get("id") and iv["id"] not in _processed_invites]
            if fresh:
                L = _inv_lcu_creds()
                if L:
                    base, h = L
                    me = _inv_current_riot_id(base, h)
                    if me:
                        for iv in fresh:
                            if _inv_norm(iv.get("requester")) != _inv_norm(me):
                                continue                              # 내 요청 아님 → 무시(마킹 안 함)
                            _processed_invites[iv["id"]] = now
                            sids = []
                            for rid in iv.get("invitees", []):
                                sid = _inv_resolve_summoner_id(base, h, rid)
                                print(f"[invite] {rid} -> summonerId={sid}", flush=True)
                                if sid: sids.append(sid)
                            body = [{"toSummonerId": s} for s in sids]
                            if body:
                                try:
                                    r = requests.post(base + "/lol-lobby/v2/lobby/invitations", headers=h,
                                                      data=json.dumps(body), verify=False, timeout=5)
                                    print(f"[invite] {iv.get('team')}팀 {len(body)}명 초대 → HTTP {r.status_code}", flush=True)
                                except Exception as e:
                                    print(f"[invite] 초대 실패: {e}", flush=True)
                            else:
                                print(f"[invite] {iv.get('team')}팀 — 해석된 소환사 0명(초대 스킵)", flush=True)
        except Exception as e:
            print(f"[invite] loop err: {e}", flush=True)
        time.sleep(5)

def _invite_voice_members():
    """🎮 [2026-08-13] '음성방 초대' 버튼 — 디스코드로 알트탭하지 않고 분석기에서 바로 초대.
       봇 /voice 가 '요청자가 지금 들어가 있는 음성방'만 돌려주므로 대상 선정 규칙은 /팀초대와 같다
       (봇 제외·본인 제외). 초대 실행부는 기존 폴러와 동일한 LCU 경로를 그대로 쓴다.
       반환: (성공여부, 사용자에게 보여줄 메시지)"""
    L = _inv_lcu_creds()
    if not L:
        return False, "League 클라이언트를 찾지 못했어요.\n롤을 켜고 로그인한 뒤 다시 눌러주세요."
    base, h = L
    me = _inv_current_riot_id(base, h)
    if not me:
        return False, "현재 소환사를 읽지 못했어요.\n롤 클라이언트가 완전히 켜졌는지 확인해주세요."
    try:
        from urllib.parse import quote
        j = requests.get(f"{VOICE_BRIDGE_URL}?requester={quote(me)}", timeout=8).json() or {}
    except Exception as e:
        return False, f"봇 조회에 실패했어요: {e}"
    ch = j.get("channel") or "음성방"
    invitees = [x for x in (j.get("invitees") or []) if x]
    if not invitees:
        return False, (f"'{me}' 가 들어가 있는 음성방을 찾지 못했어요.\n"
                       "디스코드 음성방에 먼저 들어가 주시고, 봇에 /연동 이 돼 있는지도 확인해주세요.")
    sids = []
    for rid in invitees:
        sid = _inv_resolve_summoner_id(base, h, rid)
        print(f"[voice-invite] {rid} -> summonerId={sid}", flush=True)
        if sid: sids.append(sid)
    if not sids:
        return False, f"'{ch}' 인원 {len(invitees)}명 중 롤 계정을 해석한 사람이 없어요.\n(미연동자만 있는 방일 수 있어요)"
    try:
        r = requests.post(base + "/lol-lobby/v2/lobby/invitations", headers=h,
                          data=json.dumps([{"toSummonerId": s} for s in sids]), verify=False, timeout=6)
    except Exception as e:
        return False, f"초대 전송에 실패했어요: {e}"
    if r.status_code >= 300:
        return False, (f"롤이 초대를 거부했어요 (HTTP {r.status_code}).\n"
                       "사용자 지정 게임 로비를 먼저 만들어 두셨는지 확인해주세요.")
    miss = len(invitees) - len(sids)
    print(f"[voice-invite] {ch} {len(sids)}명 초대 → HTTP {r.status_code}", flush=True)
    return True, (f"🎮 '{ch}' 음성방 {len(sids)}명에게 초대를 보냈어요!"
                  + (f"\n(계정을 못 찾은 {miss}명은 빠졌어요 — 그 분들은 /연동 이 필요해요)" if miss else ""))

def ping_called_at_gamestart(game_id):
    """게임 시작 시 호출자(승격된 대기자)를 웹훅으로 @멘션. 게임당 1회. (호스트만)"""
    try:
        if not attendance_active: return
        if game_id in called_pinged_games: return
        chamga, maktan, hochul, daegi = compute_queue()
        if not hochul: return                        # 호출자 없으면 마킹도 안 함 → 나중에 막판 생겨도 멘션 가능
        called_pinged_games.add(game_id)             # 실제 멘션하는 게임만 1회 기록
        mentions = " ".join(f"<@{d}>" for d in hochul)
        content = "🎬 **게임 시작!** 호출된 분들 다음 판 준비해주세요 👉 " + mentions
        def _t():
            try:
                requests.post(CALL_WEBHOOK_URL,
                              json={"content": content, "allowed_mentions": {"parse": ["users"]}}, timeout=5)
            except Exception: pass
        threading.Thread(target=_t, daemon=True).start()
    except Exception: pass

# 🗒️ [2026-07-29] 콘솔 없는 창 모드로 빌드돼 print 기록이 통째로 버려지고 있었다.
#    문제 추적이 불가능해서(사장님이 로그를 볼 방법이 없었음) 실행 폴더의 파일로 남긴다.
LOG_PATH = os.path.join(
    os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)),
    "analyzer_log.txt")


class _TeeLog:
    """화면(있으면)과 파일에 동시에 쓴다. 파일 쓰기가 실패해도 프로그램은 계속 돈다."""
    def __init__(self, stream, fh): self._s, self._f = stream, fh
    def write(self, msg):
        try:
            if self._s: self._s.write(msg)
        except Exception: pass
        try:
            self._f.write(msg); self._f.flush()
        except Exception: pass
        return len(msg or "")
    def flush(self):
        for _t in (self._s, self._f):
            try:
                if _t: _t.flush()
            except Exception: pass


def _start_file_log():
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 5 * 1024 * 1024:
            os.replace(LOG_PATH, LOG_PATH + ".old")     # 5MB 넘으면 한 세대만 보관
        fh = open(LOG_PATH, "a", encoding="utf-8", errors="replace")
        fh.write(f"\n===== 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} v{CURRENT_VERSION} =====\n")
        fh.flush()
        sys.stdout = _TeeLog(sys.stdout, fh)
        sys.stderr = _TeeLog(sys.stderr, fh)
    except Exception: pass


_STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def startup_registered():
    """부팅 자동실행에 실제로 등록돼 있는 명령줄. 없으면 None.
       [2026-08-12 사장님 제보 '체크해둬도 작동을 안 한다'] 지금까지 등록 성공/실패를 확인할
       방법이 없었다 — 실패해도 except 로 삼키고 체크박스만 켜진 채로 남았다."""
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_KEY, 0, winreg.KEY_READ)
        try: v, _t = winreg.QueryValueEx(k, "SquadAnalyzer"); return v
        finally: winreg.CloseKey(k)
    except Exception:
        return None

def startup_cmdline():
    exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    return f'"{exe}" --stealth'

def toggle_windows_startup(enabled):
    """부팅 시 자동실행 등록/해제. 반환 (성공, 설명) — 실패를 더 이상 조용히 삼키지 않는다."""
    want = startup_cmdline() if enabled else None
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                winreg.SetValueEx(key, "SquadAnalyzer", 0, winreg.REG_SZ, want)
            else:
                try: winreg.DeleteValue(key, "SquadAnalyzer")
                except FileNotFoundError: pass
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        msg = f"레지스트리 쓰기 실패: {type(e).__name__} {e}"
        print(f"[startup] {msg}", flush=True); return False, msg
    got = startup_registered()                       # ✅ 쓴 값을 되읽어 확인한다
    if enabled and got != want:
        msg = f"등록했는데 되읽으니 값이 다릅니다(보안 프로그램이 되돌렸을 수 있어요) — 현재값: {got}"
        print(f"[startup] {msg}", flush=True); return False, msg
    if (not enabled) and got:
        msg = f"해제했는데 값이 남아 있습니다 — 현재값: {got}"
        print(f"[startup] {msg}", flush=True); return False, msg
    print(f"[startup] {'등록' if enabled else '해제'} 완료 — {got or '(없음)'}", flush=True)
    return True, (got or "")

UPDATER_BAT_TEMPLATE = r'''@echo off
set /a w=0
:waitpid
tasklist /FI "PID eq __PID__" 2>nul | find "__PID__" >nul
if errorlevel 1 goto gone
set /a w+=1
if %w% GEQ 60 goto gone
ping -n 2 127.0.0.1 >nul
goto waitpid
:gone
set /a b=0
:bkexe
if not exist "__APP__\__EXE__" goto bkint
move /y "__APP__\__EXE__" "__APP__\_sqa_old_exe" >nul 2>&1
if not exist "__APP__\__EXE__" goto bkint
set /a b+=1
if %b% GEQ 20 goto safe_relaunch
ping -n 2 127.0.0.1 >nul
goto bkexe
:bkint
set /a b=0
:bkintloop
if not exist "__APP__\_internal" goto putnew
if exist "__APP__\_sqa_old_internal" rmdir /s /q "__APP__\_sqa_old_internal" >nul 2>&1
move /y "__APP__\_internal" "__APP__\_sqa_old_internal" >nul 2>&1
if not exist "__APP__\_internal" goto putnew
set /a b+=1
if %b% GEQ 20 goto rollback
ping -n 2 127.0.0.1 >nul
goto bkintloop
:putnew
move /y "__NEW__\__EXE__" "__APP__\__EXE__" >nul 2>&1
move /y "__NEW__\_internal" "__APP__\_internal" >nul 2>&1
if not exist "__APP__\__EXE__" goto rollback
if not exist "__APP__\_internal" goto rollback
if exist "__APP__\_sqa_old_exe" del /f /q "__APP__\_sqa_old_exe" >nul 2>&1
if exist "__APP__\_sqa_old_internal" rmdir /s /q "__APP__\_sqa_old_internal" >nul 2>&1
rmdir /s /q "__STAGE__" >nul 2>&1
start "" "__APP__\__EXE__"
del "%~f0" >nul 2>&1
goto :eof
:rollback
if exist "__APP__\__EXE__" del /f /q "__APP__\__EXE__" >nul 2>&1
if exist "__APP__\_internal" rmdir /s /q "__APP__\_internal" >nul 2>&1
if exist "__APP__\_sqa_old_exe" move /y "__APP__\_sqa_old_exe" "__APP__\__EXE__" >nul 2>&1
if exist "__APP__\_sqa_old_internal" move /y "__APP__\_sqa_old_internal" "__APP__\_internal" >nul 2>&1
:safe_relaunch
if exist "__APP__\__EXE__" start "" "__APP__\__EXE__"
del "%~f0" >nul 2>&1
'''

def _make_updater_bat(pid, app_dir, new_root, exe_name, stage):
    b = (UPDATER_BAT_TEMPLATE
         .replace("__PID__", str(pid)).replace("__APP__", app_dir)
         .replace("__NEW__", new_root).replace("__EXE__", exe_name)
         .replace("__STAGE__", stage))
    return b.replace("\r\n", "\n").replace("\n", "\r\n")   # 확실히 CRLF

_UPDATE_EXIT_REQUESTED = False   # 🔄 업데이터가 교체 준비 완료 → GUI가 '업데이트 중' 안내 후 종료하도록 신호
_OUTDATED = False   # 🛑 [v81.65 원격 킬스위치] 신버전 감지 시 True → 모든 웹훅 발송 즉시 중단(구버전 마비).
                    #    자동 업데이트 성공 시 재시작으로 해소, 다운로드 실패해도 발송 중단은 유지(10분 주기 재시도).
_LIVE_GAME = [False]   # 🛡️ [v81.67] 폴링 루프가 매 주기 갱신 — 게임(챔슬렉~종료)·기록 중 여부.
_HDR_MIG_DONE = set()  # 🧱 [v81.72] 시트별 헤더 자동생성 시도 1회 제한 — 실패 반복이 쓰기쿼터 소진하던 사고 방지.
                       #    라이브 중 신버전이 릴리스돼도 업데이터가 재시작을 연기(게임 중 재시작=종료신호 유실 방지).

def _auto_update_once():
    # [V81.28] onedir 자동 업데이트: 새 버전 zip 다운로드 → 압축해제 → 폴더(exe+_internal) 교체(백업+롤백).
    #   구 onefile(단일 exe) 업데이터는 이 함수로 대체됨. 온디렉토리는 임시추출이 없어 'python DLL 로드실패' 원천 제거.
    global _OUTDATED
    if _LIVE_GAME[0] and not _OUTDATED:
        return   # 🛡️ [v81.67] 게임·기록 중엔 버전 확인/킬스위치/재시작 전부 연기(종료신호 유실 방지) — 게임 끝나면 다음 주기에 진행
    try:
        v_res = requests.get(VERSION_URL, timeout=5)
        if v_res.status_code != 200: return
        latest_version = v_res.text.strip()
        def _vnum(v):
            try: return tuple(int(x) for x in str(v).strip().lstrip('vV').split('.'))
            except Exception: return (0,)
        if _vnum(latest_version) <= _vnum(CURRENT_VERSION): return
        if not _OUTDATED:
            _OUTDATED = True   # 다운로드 성공 여부와 무관하게 이 시점부터 웹훅 발송 전면 중단(봇에 구버전 신호 안 보냄)
            print(f"[update] 신버전 v{latest_version} 감지 — 웹훅 발송 중단(킬스위치) 후 자동 업데이트 시도", flush=True)
            try:
                with gui_lock: gui_data["status"] = "🛑 신버전 감지 — 자동 업데이트 대기 중"
            except Exception: pass

        zr = requests.get(ZIP_URL, timeout=180)
        if zr.status_code != 200: return
        data = zr.content
        if len(data) < 1_000_000 or data[:2] != b'PK': return   # 진짜 zip(PK)인지 — 깨진/HTML 응답이면 중단

        import zipfile, io, shutil, tempfile
        cur_exe  = sys.executable
        cur_name = os.path.basename(cur_exe)
        app_dir  = os.path.dirname(cur_exe)                       # 현재 앱 폴더(exe+_internal 위치)
        tmp      = tempfile.gettempdir()
        stage    = os.path.join(tmp, "_sqa_update_stage")
        bat_path = os.path.join(tmp, "sqa_updater.bat")
        try:
            if os.path.isdir(stage): shutil.rmtree(stage, ignore_errors=True)
        except Exception: pass
        os.makedirs(stage, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf: zf.extractall(stage)

        # 스테이징에서 새 앱 루트(exe + _internal 보유) 탐색
        new_root = None
        for r_, _d, files in os.walk(stage):
            if cur_name in files and os.path.isdir(os.path.join(r_, "_internal")): new_root = r_; break
        if not new_root: return
        try:                                                      # 무결성 게이트: python3xx.dll 있는지
            if not any(fn.lower().startswith("python3") and fn.lower().endswith(".dll")
                       for fn in os.listdir(os.path.join(new_root, "_internal"))): return
        except Exception: return

        if _LIVE_GAME[0]:      # 🛡️ [v81.67] 다운로드 중 게임이 시작된 경우 — 게임 끝날 때까지 교체·재시작 연기.
            _OUTDATED = False  #    연기 동안은 발송 재개(이번 게임 종료신호 보전 — 어차피 직후 신버전으로 재시작).
            while _LIVE_GAME[0]:
                time.sleep(30)
            _OUTDATED = True
        with open(bat_path, "w", encoding="cp949") as f:
            f.write(_make_updater_bat(os.getpid(), app_dir, new_root, cur_name, stage))
        subprocess.Popen(["cmd", "/c", bat_path], shell=False,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # 무음 종료 방지: GUI에 '업데이트 중' 안내를 띄우게 신호 → GUI가 안내 후 종료. (업데이터 bat은 프로세스 종료를 대기)
        global _UPDATE_EXIT_REQUESTED
        _UPDATE_EXIT_REQUESTED = True
        time.sleep(9)          # 폴백: GUI 미기동 등으로 처리 못하면 여기서 직접 종료
        os._exit(0)
    except Exception: pass

def auto_updater_engine():
    # [v81.65] 기동 시 1회 → 10분 주기 상시 감시로 확장(원격 킬스위치) — 켜둔 채 방치된 인스턴스도
    #   패치 릴리스 즉시 발송 중단(_OUTDATED)되고 자동 업데이트·재시작됨. 실패 시 10분마다 재시도.
    if not getattr(sys, 'frozen', False): return
    while True:
        try: _auto_update_once()
        except Exception: pass
        time.sleep(600)

PRED_BRIDGE_URL = INVITE_BRIDGE_URL.rsplit("/", 1)[0] + "/predictions"   # 🎲 봇 승부예측 누적전적 엔드포인트(초대브릿지와 동일 호스트)
_pred_mirror_last = [None]
def _prediction_mirror_loop():
    """[2026-07-08] 봇 /predictions(누적 승부예측 전적) 폴링 → PREDICTIONS 시트탭 미러(호스트만·5분).
       웹이 gviz로 읽어 '승부의신/롤알못' 타이틀 표시. clear+update 멱등 덮어쓰기라 다중 인스턴스 무해하나 쓰기 절약 위해 호스트 1대만."""
    time.sleep(45)   # 시작 지터
    while True:
        try:
            if load_bot_token() and global_spreadsheet is not None:   # 호스트(token 보유) 1대만
                try: tally = requests.get(PRED_BRIDGE_URL, timeout=6).json().get("tally", {})
                except Exception: tally = None
                if isinstance(tally, dict) and tally and tally != _pred_mirror_last[0]:
                    now_s = time.strftime("%Y-%m-%d %H:%M")
                    rows = [["디스코드ID", "이름", "적중", "총예측", "적중률", "갱신"]]
                    for uid, rec in tally.items():
                        try: h = int(rec.get("hits", 0)); tt = int(rec.get("total", 0))
                        except Exception: continue
                        if tt <= 0: continue
                        rows.append([str(uid), str(rec.get("name", "")), h, tt, round(h / tt * 100, 1), now_s])
                    try:
                        try: ws = global_spreadsheet.worksheet("PREDICTIONS")
                        except Exception: ws = global_spreadsheet.add_worksheet(title="PREDICTIONS", rows="500", cols="6")
                        ws.clear(); ws.update(rows)
                        _pred_mirror_last[0] = tally
                        print(f"[pred] PREDICTIONS 미러 {len(rows)-1}명", flush=True)
                    except Exception as e:
                        print(f"[pred] 시트 미러 실패: {e}", flush=True)
        except Exception: pass
        time.sleep(300)

CAREER_BRIDGE_URL = INVITE_BRIDGE_URL.rsplit("/", 1)[0] + "/careers"   # 🏆 봇 커리어(우승 기록) 엔드포인트
_career_mirror_last = [None]
def _career_mirror_loop():
    """[2026-07-12 사장님 지시] 봇 /careers(대회 우승 누적 기록 — '우승자' 역할 스캔) 폴링 → CAREER 시트탭 미러(호스트만·10분).
       웹이 gviz로 읽어 명예의전당 커리어 섹션·개인 전적창 우승 표시. clear+update 멱등 덮어쓰기."""
    time.sleep(60)   # 시작 지터
    while True:
        try:
            if load_bot_token() and global_spreadsheet is not None:   # 호스트(token 보유) 1대만
                try: car = requests.get(CAREER_BRIDGE_URL, timeout=6).json()
                except Exception: car = None
                recs = (car or {}).get("records") or []
                if recs and car != _career_mirror_last[0]:
                    # 대회별 최신 기록(=현재 보유팀) 판정: 같은 title 중 마지막 record
                    latest = {}
                    for i, r in enumerate(recs): latest[r.get("title", "")] = i
                    rows = [["대회명", "이름", "롤닉", "획득일", "현재"]]
                    for i, r in enumerate(recs):
                        t = str(r.get("title", "")).strip()
                        if not t: continue
                        names = r.get("names") or []; riots = r.get("riot") or []
                        for j, nm in enumerate(names):
                            rt = riots[j] if j < len(riots) else ""
                            rows.append([t, str(nm), str(rt or ""), str(r.get("date", "")), 1 if latest.get(t) == i else 0])
                    try:
                        try: ws = global_spreadsheet.worksheet("CAREER")
                        except Exception: ws = global_spreadsheet.add_worksheet(title="CAREER", rows="1000", cols="6")
                        ws.clear(); ws.update(rows)
                        _career_mirror_last[0] = car
                        print(f"[career] CAREER 미러 {len(rows)-1}행", flush=True)
                    except Exception as e:
                        print(f"[career] 시트 미러 실패: {e}", flush=True)
        except Exception: pass
        time.sleep(600)

# ===== 🖼️ 상점 꾸미기(포인트 상품) — 봇 /cosmetics 폴링 → 밴픽 화면 '내 칸' 장식 =====
# [2026-07-15 사장님 지시] 디스코드 진행판뿐 아니라 분석기에서 각자가 차지하는 칸도 꾸밀 수 있게.
#   호스트 전용이 아니라 '모든 PC'에서 돌아야 한다(각자 화면에 모두의 장식이 보여야 하므로).
COSMETIC_BRIDGE_URL = INVITE_BRIDGE_URL.rsplit("/", 1)[0] + "/cosmetics"
COSMETICS = {}          # {tnorm(롤닉): {"deco":{"pre","suf"}, "cell":{"border","fg","bg","badge"}}}

def _cos_of(name):
    """롤닉 → 장식 정보(없으면 {}). 태그(#KR1) 제거·공백무시 정규화로 매칭."""
    try: return COSMETICS.get(tnorm(name)) or {}
    except Exception: return {}

def _cosmetics_loop():
    """봇 /cosmetics 60초 폴링. 실패해도 조용히 이전 값 유지(장식은 없어도 게임엔 지장 없음)."""
    global COSMETICS
    while True:
        try:
            d = (requests.get(COSMETIC_BRIDGE_URL, timeout=6).json() or {}).get("players") or {}
            COSMETICS = {tnorm(k): v for k, v in d.items() if k}
        except Exception:
            pass
        time.sleep(60)

TIER_BRIDGE_URL = INVITE_BRIDGE_URL.rsplit("/", 1)[0] + "/tiers"   # 🎖 봇 내부티어 역할 엔드포인트
def _tier_role_sync_loop():
    """🎖 [2026-07-13 사장님 지시] 디스코드 내부티어 역할 → CLAN_TIERS '신규 인원만' 추가(호스트·15분).
       기존 인원의 티어는 마스터 티어차트가 권위(sync_master_tier_chart) — 여기선 절대 덮어쓰지 않음.
       읽기=공개 gviz CSV(서비스 읽기 0), 쓰기=save_clan_tier(신규 1행 append)."""
    time.sleep(150)
    while True:
        try:
            if load_bot_token() and global_spreadsheet is not None:
                try: ent = (requests.get(TIER_BRIDGE_URL, timeout=6).json() or {}).get("entries") or []
                except Exception: ent = []
                if ent:
                    import csv as _csv, io as _io
                    cur = None
                    try:
                        rows = list(_csv.reader(_io.StringIO(_fetch_public_csv(DOCUMENT_ID, CLAN_TIERS_GID))))
                        if rows and (rows[0][0] if rows[0] else "").strip() == "닉네임":
                            cur = {tnorm(r[0]) for r in rows[1:] if r and r[0].strip()}
                    except Exception: cur = None
                    if cur:   # 현황을 못 읽으면 중복 위험 → 이번 주기 스킵
                        added = 0
                        for e in ent:
                            nm = (str(e.get("riot") or "").split("#")[0] or str(e.get("name") or "")).strip()
                            t = str(e.get("tier") or "").strip()
                            if not nm or not t: continue
                            k1 = tnorm(nm); k2 = tnorm(str(e.get("name") or ""))
                            if (k1 and k1 in cur) or (k2 and k2 in cur): continue   # 이미 등재 → 마스터 차트 권위 유지
                            if save_clan_tier(nm, t):
                                cur.add(k1); added += 1
                        if added: print(f"[tier] 디스코드 티어역할 → CLAN_TIERS 신규 {added}명 추가", flush=True)
        except Exception: pass
        time.sleep(900)

# 🎯 [2026-07-16 사장님 지시] 클랜포지션 자동화 — 봇 /positions 폴링 → CLAN_POSITIONS 전량 재작성(호스트·1h).
#   (기존 sync_positions.py 예약작업이 7/5 이후 멈춤 → 봇 상시 스캔+분석기 폴링으로 대체, 티어와 동일 파이프라인)
POSITION_BRIDGE_URL = INVITE_BRIDGE_URL.rsplit("/", 1)[0] + "/positions"
_POS_LAST_SIG = [None]
def _write_clan_positions(entries):
    """CLAN_POSITIONS 전량 재작성(서비스계정 clear→put). Discord 역할이 권위 — 역할 삭제도 반영."""
    now = time.strftime("%Y-%m-%d %H:%M")
    rows = [["닉네임", "디스코드ID", "주포지션", "부포지션", "갱신시각"]]
    for e in entries:
        nm = str(e.get("name") or "").strip()
        if not nm: continue
        rows.append([nm, str(e.get("did") or ""), str(e.get("main") or ""), str(e.get("subs") or ""), now])
    if len(rows) < 51: return False                # 안전판: 스캔 실패로 인원 급감 시 덮어쓰기 금지
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(resource_path('credentials.json.json'), scope)
    tok = creds.get_access_token().access_token
    H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    base = "https://sheets.googleapis.com/v4/spreadsheets/" + DOCUMENT_ID + "/values/CLAN_POSITIONS"
    requests.post(base + "!A1:E1000:clear", headers=H, timeout=30)   # 트레일링 잔여행 제거(인원 감소 반영)
    r = requests.put(base + "!A1?valueInputOption=RAW", headers=H, data=json.dumps({"values": rows}), timeout=40)
    return r.status_code == 200

def _position_sync_loop():
    """봇 /positions → CLAN_POSITIONS 재작성(호스트·1h). 변화 없으면 쓰기 생략(쿼터 절약)."""
    time.sleep(200)
    while True:
        try:
            if load_bot_token() and global_spreadsheet is not None:
                ent = (requests.get(POSITION_BRIDGE_URL, timeout=6).json() or {}).get("entries") or []
                if ent and len(ent) >= 50:
                    sig = tuple(sorted((str(e.get("name","")), str(e.get("main","")), str(e.get("subs",""))) for e in ent))
                    if sig != _POS_LAST_SIG[0]:            # 변동 있을 때만 쓰기
                        if _write_clan_positions(ent):
                            _POS_LAST_SIG[0] = sig
                            print(f"[pos] 포지션 역할 → CLAN_POSITIONS {len(ent)}명 재작성", flush=True)
        except Exception as e:
            print(f"[pos] 동기화 실패(무시): {e}", flush=True)
        time.sleep(3600)

MY_RIOT_NAME = [""]   # 🩺 LCU 로그인 계정 롤닉#태그(폴링 루프가 채움)
def _version_heartbeat_loop():
    """🩺 [2026-07-13 사장님 지시] 실행 인스턴스별 [롤닉, 버전, 마지막 실행]을 VERSIONS 탭에 기록 —
       누가 구버전/미갱신인지 시트에서 바로 확인(구버전 접속자 색출). 시작 90초 후 1회 + 이후 60분 주기.
       라이브 중 429 경쟁 최소화: 읽기 1회(col A) + 셀 update 1회의 초경량 upsert."""
    time.sleep(90)
    while True:
        try:
            nm = MY_RIOT_NAME[0]
            if nm and global_spreadsheet is not None:
                try: ws = global_spreadsheet.worksheet("VERSIONS")
                except Exception: ws = global_spreadsheet.add_worksheet(title="VERSIONS", rows="300", cols="4")
                now_s = time.strftime("%Y-%m-%d %H:%M")
                col = ws.col_values(1)
                if not col: ws.update("A1:C1", [["롤닉", "버전", "마지막 실행"]]); col = ["롤닉"]
                row = None
                for i, v in enumerate(col[1:], 2):
                    if str(v).strip() == nm: row = i; break
                if row: ws.update(f"B{row}:C{row}", [[CURRENT_VERSION, now_s]])
                else: ws.append_row([nm, CURRENT_VERSION, now_s])
        except Exception: pass
        time.sleep(3600)


# ─────────────────────────────────────────────────────────────
# 🕵️ [2026-08-07 사장님 전용 · 비공개 기능 — 패치노트에도 싣지 않는다] 스펠체크 헬퍼
#   상대 점멸을 보고 Ctrl+F2~F6(탑/정글/미드/원딜/서폿)을 누르면 라이엇 공식 로컬 API(2999)에서
#   인게임 시각을 읽어 [상대 챔피언명 +5:00]을 계산, '아직 안 지난' 타이머 전부를
#   "가렌 17:00 리신 18:00" 형태로 클립보드에 갱신한다. Ctrl+F7=재복사, Shift 추가=우주적통찰(272초).
#   채팅 입력은 사람이 직접(Ctrl+V) — 게임에 키 입력을 주입하지 않으므로 자동화 아님.
#   사장님 계정(MY_RIOT_NAME)이 아닐 땐 스레드가 아무것도 하지 않는다.
_SPELL_OWNERS = {"맛동산장인유미"}
_SPELL_TIMERS = {}   # 표기명 -> 만료 인게임초
def _spell_set_clipboard(text):
    """[2026-08-12 사장님 제보 '아무리 눌러도 아무 텍스트도 복사가 안돼'] 64비트 핸들 절단 버그 수정.
       ctypes 의 기본 restype 은 c_int(32비트)라, GlobalAlloc 이 돌려주는 64비트 HGLOBAL 이 잘려서
       들어왔다. 잘린 핸들로 GlobalLock 을 부르면 NULL 이 나오고 memmove(NULL,...) 에서 접근 위반이
       터지는데, 그 예외를 호출부 루프의 except 가 통째로 삼켜 아무 일도 없는 것처럼 보였다.
       restype/argtypes 를 명시해 절단을 없애고, 실패하면 조용히 넘기지 말고 원인을 찍는다."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32; k = ctypes.windll.kernel32
    u.OpenClipboard.argtypes = [wintypes.HWND]; u.OpenClipboard.restype = wintypes.BOOL
    u.EmptyClipboard.restype = wintypes.BOOL
    u.CloseClipboard.restype = wintypes.BOOL
    u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u.SetClipboardData.restype = wintypes.HANDLE
    k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]; k.GlobalAlloc.restype = wintypes.HGLOBAL
    k.GlobalLock.argtypes = [wintypes.HGLOBAL]; k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    k.GlobalFree.argtypes = [wintypes.HGLOBAL]; k.GlobalFree.restype = wintypes.HGLOBAL
    opened = False
    for _ in range(10):        # 다른 앱이 클립보드를 쥐고 있으면 잠깐 뒤 재시도
        if u.OpenClipboard(None): opened = True; break
        time.sleep(0.05)
    if not opened:
        print("[spell] 클립보드를 다른 프로그램이 점유 중 — 복사 실패", flush=True); return False
    h = None
    try:
        u.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h = k.GlobalAlloc(0x2002, len(data))          # GMEM_DDESHARE|GMEM_MOVEABLE
        if not h:
            print("[spell] GlobalAlloc 실패 — 복사 실패", flush=True); return False
        ptr = k.GlobalLock(h)
        if not ptr:
            print("[spell] GlobalLock 실패 — 복사 실패", flush=True); return False
        ctypes.memmove(ptr, data, len(data)); k.GlobalUnlock(h)
        if not u.SetClipboardData(13, h):             # CF_UNICODETEXT
            print(f"[spell] SetClipboardData 실패 (err {ctypes.get_last_error()})", flush=True); return False
        h = None                                      # 성공 시 소유권은 OS로 넘어간다 — 우리가 free 하면 안 됨
        return True
    except Exception as e:
        print(f"[spell] 클립보드 쓰기 예외: {type(e).__name__} {e}", flush=True); return False
    finally:
        if h: k.GlobalFree(h)                         # 실패 경로에서만 회수(누수 방지)
        u.CloseClipboard()
def _spell_live(path):
    r = requests.get("https://127.0.0.1:2999/liveclientdata/" + path, verify=False, timeout=1.5)
    return r.json() if r.status_code == 200 else None
def _spell_enemy_champ(pos_key):
    try:
        me = str(_spell_live("activeplayername") or "").strip()
        pl = _spell_live("playerlist") or []
        my_team = next((p.get("team") for p in pl
                        if str(p.get("riotId") or p.get("summonerName") or "") == me), None)
        if not my_team: return None
        for p in pl:
            if p.get("team") != my_team and str(p.get("position") or "").upper() == pos_key:
                return str(p.get("championName") or "").replace(" ", "") or None
    except Exception: pass
    return None
def _spellcheck_hotkey_loop():
    """[2026-08-12 사장님 재제보 '전혀 안 되더라, 이 방법으론 안 되나봐']

    원인을 못 짚은 채 같은 구조를 고치는 건 세 번째다. 이번엔 구조에서 의심스러운 것을 걷어내고,
    무엇보다 **어디서 막혔는지 눈에 보이게** 만든다.

    ① 조합키(Ctrl)를 뺀 새 기본키 — F6~F10. F2~F5 는 롤에서 '아군 시점 전환'이라 조합키를 붙일
       수밖에 없었는데, 조합키가 끼면 롤이 먼저 먹거나 사용자가 Ctrl 을 놓친다.
       롤 기본 키설정은 F1~F5(자신·아군 시점)까지만 쓰고 F6 이상은 비어 있어 단독으로 잡을 수 있다.
       (처음엔 숫자패드로 잡았는데 사장님 키보드가 텐키리스라 못 쓴다 — 2026-08-12 제보)
    ② 키가 눌린 건 잡았는데 뒤 관문에서 걸러진 경우를 전부 로그로 남긴다 — 소유자 불일치·인게임
       미연결·클립보드 실패가 지금까지 조용히 넘어갔다.
    ③ 상태를 gui_data['spell_diag'] 에 실어 분석기 화면에서 바로 확인할 수 있게 한다.
    """
    import ctypes, winsound
    u = ctypes.windll.user32
    u.GetAsyncKeyState.argtypes = [ctypes.c_int]; u.GetAsyncKeyState.restype = ctypes.c_short
    # F6~F10(단독) — 롤은 F1~F5(자신·아군 시점)까지만 쓰고 그 위는 비어 있다
    SOLO = {0x75: ("TOP", "top"), 0x76: ("JUNGLE", "jg"), 0x77: ("MIDDLE", "mid"),
            0x78: ("BOTTOM", "bot"), 0x79: ("UTILITY", "sup")}          # F6 F7 F8 F9 F10
    VK_RECOPY = 0x7A                                                     # F11 — 다시 복사
    # 숫자패드 1~5 도 그대로 받는다(텐키 있는 PC에서 더 편한 사람용)
    NUMPAD = {0x61: ("TOP", "top"), 0x62: ("JUNGLE", "jg"), 0x63: ("MIDDLE", "mid"),
              0x64: ("BOTTOM", "bot"), 0x65: ("UTILITY", "sup")}
    VK_SHIFT, VK_CTRL, VK_NUM0 = 0x10, 0x11, 0x60
    # 🔑 [2026-08-12] 눌림 판정을 최하위 비트(&1)에서 '직접 추적하는 눌림→뗌 전환'으로 교체.
    #   MSDN 명시: &1('마지막 조회 이후 눌림')은 다른 프로세스가 먼저 GetAsyncKeyState 를 부르면
    #   그쪽이 가져가 버린다. 롤 클라이언트처럼 입력을 상시 폴링하는 프로그램과 같이 돌면 키가 씹힌다.
    #   최상위 비트(0x8000, 현재 눌림 상태)는 공유 자원이 아니므로 우리가 에지를 만들면 안 씹힌다.
    _down = {}
    def _pressed(vk):
        cur = bool(u.GetAsyncKeyState(vk) & 0x8000)
        was = _down.get(vk, False)
        _down[vk] = cur
        return cur and not was
    def owner_ok():
        nm = (MY_RIOT_NAME[0] or "").split("#")[0].replace(" ", "").lower()
        return nm in {o.lower() for o in _SPELL_OWNERS}
    def game_time():
        gs = _spell_live("gamestats") or {}
        t = gs.get("gameTime")
        return int(float(t)) if t is not None else None
    def push_clip(now, diag=None):
        live = sorted(((n, x) for n, x in _SPELL_TIMERS.items() if x > now), key=lambda e: e[1])
        for n in [n for n, x in _SPELL_TIMERS.items() if x <= now]: _SPELL_TIMERS.pop(n, None)
        if not live:
            if diag: diag("복사할 타이머가 없어요(전부 만료)")
            return
        txt = " ".join(f"{n} {x//60}:{x%60:02d}" for n, x in live)
        ok = _spell_set_clipboard(txt)
        if diag: diag(("복사됨: " + txt) if ok else ("클립보드 쓰기 실패 — " + txt))
        if ok: winsound.MessageBeep(0x40)
    def _diag(msg):
        try:
            with gui_lock:
                gui_data["spell_diag"] = msg; gui_data["spell_diag_at"] = time.time()
        except Exception: pass
        print(f"[spell] {msg}", flush=True)
    print("[spell] 헬퍼 시작 — F6/F7/F8/F9/F10 = 탑/정글/미드/원딜/서폿 · F11 = 다시 복사 "
          "(Shift 함께 누르면 신발 272초) · 숫자패드 1~5,0 도 동일", flush=True)
    last_gt = [0]
    while True:
        time.sleep(0.05)
        try:
            hit = None; recopy = False
            for vk in SOLO:                         # F6~F10 — 조합키 없이 바로
                if _pressed(vk): hit = SOLO[vk]
            for vk in NUMPAD:                       # 숫자패드도 동일하게 받는다
                if _pressed(vk): hit = NUMPAD[vk]
            if _pressed(VK_RECOPY) or _pressed(VK_NUM0): recopy = True
            if not (hit or recopy): continue
            if not owner_ok():
                _diag(f"전용 계정이 아니라 무시 — 현재 계정 '{MY_RIOT_NAME[0] or '미확인'}'"); continue
            now = game_time()
            if now is None:
                _diag("인게임 시각을 못 읽음(포트 2999 무응답) — 게임 중에만 동작"); continue
            if now < last_gt[0] - 60: _SPELL_TIMERS.clear()   # 새 게임(시각 역행) — 이전 판 타이머 파기
            last_gt[0] = now
            if hit:
                pos_key, fallback = hit
                cd = 272 if (u.GetAsyncKeyState(VK_SHIFT) & 0x8000) else 300
                label = _spell_enemy_champ(pos_key) or fallback
                _SPELL_TIMERS[label] = now + cd
            push_clip(now, _diag)
        except Exception:
            time.sleep(1)

def announce_patch_if_updated():
    """신버전으로 업데이트된 뒤 첫 실행 시, 릴리스 노트를 웹훅으로 1회 알림.
       호스트(token.txt 보유)만 발송 → 배포본 다수가 중복 도배하는 것 방지.

       [v82.51 사장님 지시] 패치노트는 분석기·웹·봇을 묶어 CI(patch-note 워크플로)에서 발송한다.
       분석기가 따로 또 보내면 같은 내용이 두 번 올라가므로 기본 비활성 —
       CI를 못 쓰는 상황에서만 환경변수 PATCH_NOTE_SELF=1 로 되살린다."""
    if os.environ.get("PATCH_NOTE_SELF") != "1":
        try:                                            # 버전 기록만 갱신(다음에 켜도 과거분 도배 방지)
            cfg = load_config()
            if cfg.get("last_patch_version") != CURRENT_VERSION:
                cfg["last_patch_version"] = CURRENT_VERSION; save_config(cfg)
        except Exception: pass
        return
    try:
        if not load_bot_token(): return                 # 호스트 1대만
        cfg = load_config()
        if cfg.get("last_patch_version") == CURRENT_VERSION: return   # 같은 버전 재시작은 무시
        note = ""
        try:
            r = requests.get("https://api.github.com/repos/kjp1583-art/squad-analyzer/releases/latest", timeout=6)
            if r.status_code == 200:
                note = (r.json().get("body") or "").strip()
                for _m in ("\n---", "🔐"):        # '---' 이하(다운로드 안내·SHA256 등 기술 푸터)는 디스코드 패치노트에 노출 안 함
                    note = note.split(_m)[0]
                # [2026-07-21 사장님 지시] SHA256 등 기술 줄은 위치 불문 제거(구분선 없이 본문에 섞여도 필터)
                note = "\n".join(l for l in note.splitlines()
                                 if not l.strip().lower().startswith(("sha256", "sha-256", "checksum")))
                note = note.strip()[:500]
        except Exception: pass
        cfg["last_patch_version"] = CURRENT_VERSION
        save_config(cfg)
        msg = f"🔔 **스쿼드해체분석기 v{CURRENT_VERSION} 업데이트 적용됨**"
        if note: msg += chr(10) + note
        msg += chr(10) + "⚠️ **구버전 사용 중이신 분은 분석기를 껐다 켜면 자동 업데이트됩니다!**"
        try:                                            # 패치노트 전용 웹훅으로 발송(내전기록 채널과 분리)
            requests.post(PATCH_WEBHOOK_URL, json={"content": msg}, timeout=5)
        except Exception: pass
    except Exception: pass

# =========================================================================
# 🎖 내부티어 (클랜 자체 평가표) — squad.gg 웹과 동일하게 유지 (클랜원 정보)
# =========================================================================
TIER_DATA = {
    "1上": ["새벽문앙","여니","나는빌레","승수","KBJ0628"],
    "1中": ["Daype","나눙강운","태웅","난오눅만살아","삼겹살맛있더라","야릇한언니돌","빨디즈장군이","은화","베볼배볼","용죤전사","默言","vaundy","두우쿠우","수직낙하하는중","최강У도깨비","꿩79","무새","앵섭","겨울"],
    "1下": ["지르","별구름비","뭉탱이","조금늙음","SiahK","예니야","앙꼬없","파랑","순애","지옥의왕","프싱","반가","뎁뚜처럼","태희","수화은연","새우깡","Gyuse0k","apmidplzz","불전마사지소환사","맛동산장인유미","그냥해","weiha","가보자","시원"],
    "2上": ["하오","아기설탕이","격품","덕현하콩만돌","오리고기(꼬눈)","Planb","Widersehen","piacerdamor","촛파","영유아기달달핀","오뎅이","아기빠급이","아이스아메리카노","가리비","쭌생","신정수","꽃을피우니","BeakYerin","나야","지율게없다구","고구마","SOOP거북00","재첩국","팀원과쌔우지말자","아기언지니","쌉처바"],
    "2中": ["민병이","한입","타나","즐거워하부하루","maru","맨헤라공원펜티도둑","사랑두리공이","loaa","dacapo","새찡","김쪼랭","섬광","한별","러버덕","무빙","derek","힝구리","누누","개구리","간절한영에소환사","별빛하민","정글위치생각해요"],
    "2下": ["집중겜","피파하고싶다으아","아라","브론즈장인신지드","풋뼛풍커리","4단강등고승현","건백","건빡","모근이","아기선도부","옴팡이","지노","hee츠","배고배고","태양","텍스","밍구","아기레명이","오함마","아리"],
    "3上": ["윤가","JESTER","pontior","나르아빠","chihuahua","봇치","조선제일하리보","칼든인간백정","que사디아","모득희","체소초보다","용수없어도이겨","나쁜마음고처먹기","흐접부어","먹찌","젠이즈","9DYeok","태민교육","감자피덕","니퍼펜치골라"],
    "3中": ["튀긴사이다","hehehi","과자테두리","鐵뱅꽂皇","上대탑노물갱즙","용감한앰스터","TheCarterIII","춘식이","치아요청","요트","천고래인저"],
    "3下": ["탱크보이","탱크보이 이우경","주옥망겜","발목에모기물림","뇌룡오공","へいちょうねこ","단무지싫어","선생짓못해먹겠네"],
}
# 닉변 반영 (구닉이 표에 있던 사람의 현재 닉 → 같은 티어)
TIER_NICK = {
    "언진":"2上","RayB":"2上","현타온덕현하콩":"2上","설탕":"2上","十代":"2上","사슬":"2上",
    "레멍이":"2下","앙앵모르딱":"1中","망무새":"1中","뽀뽀":"1下",
    "윤슬":"3中","윤카":"3上","주옥갓겜":"3下","병장고양이":"3下","김야웅":"2中",
    "우거":"1下","카페":"3中","나만":"3中","ascass":"2上","커리크랩칠리크림":"2上",
    "레알티슈도둑":"2中","듀우쿠우":"2中","새벽문앞":"1上","맨헤라공원팬티도둑":"2中","뵤뵤":"1下",
}
TIER_ORDER_LIST = ["0","1上","1中","1下","2上","2中","2下","3上","3中","3下"]  # "0"=0티어(최상위, 上/中/下 없음)
def tnorm(s):
    return "".join(str(s or "").split("#")[0].lower().split())
TIER_OF = {}
for _t, _names in TIER_DATA.items():
    for _nm in _names: TIER_OF[tnorm(_nm)] = _t
for _nm, _t in TIER_NICK.items(): TIER_OF[tnorm(_nm)] = _t
def tier_of(name):
    t = TIER_OF.get(tnorm(name))
    if t: return t
    # 🔗 [v82.50] 부계정 이름으로 조회된 경우 본계정 티어로 폴백(웹 tierOf와 동일 규칙).
    #    CLAN_TIERS에서 부계정 행을 지워도 과거 기록(부계정 닉으로 남은 행)이 티어 미보유로 떨어지지 않게 한다.
    try:
        mn = get_main_name(name)
        if mn and tnorm(mn) != tnorm(name): return TIER_OF.get(tnorm(mn))
    except Exception: pass
    return None

# ===== 내부티어 SSOT (CLAN_TIERS 시트) =====
def load_clan_tiers():
    """CLAN_TIERS 시트에서 {tnorm(닉네임): 티어} 읽어 TIER_OF 재구성. 실패/빈 시트면 하드코딩 유지."""
    try:
        if not global_spreadsheet: return
        ws = global_spreadsheet.worksheet("CLAN_TIERS")
        rows = ws.get_all_values()
        if not rows or len(rows) < 2: return
        h = rows[0]
        ni = h.index("닉네임") if "닉네임" in h else 0
        ti = h.index("티어") if "티어" in h else 1
        new_map = {}
        for r in rows[1:]:
            if len(r) > max(ni, ti):
                nm = str(r[ni]).strip(); t = str(r[ti]).strip()
                if nm and t: new_map[tnorm(nm)] = t
        if new_map:
            TIER_OF.clear(); TIER_OF.update(new_map)
    except Exception: pass

# ===== 선언 포지션(디스코드 역할 탑(주)/정글(부)… → CLAN_POSITIONS 시트, sync_positions.py가 매일 갱신) =====
POSITION_OF = {}   # tnorm(닉네임) -> (주포지션, 부포지션문자열)  예: ("탑", "정글/미드") / 부포 "ALL"=전포지션
def load_clan_positions():
    """CLAN_POSITIONS 시트에서 선언 주/부 포지션 로드(내부티어표 표시용)."""
    try:
        if not global_spreadsheet: return
        rows = global_spreadsheet.worksheet("CLAN_POSITIONS").get_all_values()
        if not rows or len(rows) < 2: return
        h = rows[0]
        ni = h.index("닉네임") if "닉네임" in h else 0
        mi = h.index("주포지션") if "주포지션" in h else 2
        si = h.index("부포지션") if "부포지션" in h else 3
        new_map = {}
        for r in rows[1:]:
            if len(r) > max(ni, mi, si) and str(r[ni]).strip():
                new_map[tnorm(r[ni])] = (str(r[mi]).strip(), str(r[si]).strip())
        if new_map:
            POSITION_OF.clear(); POSITION_OF.update(new_map)
    except Exception: pass

def position_label(name):
    """'탑(주)·정글/미드(부)' 형태 라벨. 선언 포지션 없으면 빈 문자열."""
    mp, sp = POSITION_OF.get(tnorm(name), ("", ""))
    parts = []
    if mp: parts.append(f"{mp}(주)")
    if sp: parts.append(("전라인" if sp == "ALL" else sp) + "(부)")
    return "·".join(parts)

def _clan_tiers_ws():
    if not global_spreadsheet: return None
    try:
        return global_spreadsheet.worksheet("CLAN_TIERS")
    except Exception:
        try:
            ws = global_spreadsheet.add_worksheet(title="CLAN_TIERS", rows="600", cols="4")
            ws.append_row(["닉네임", "티어"])
            return ws
        except Exception: return None

def save_clan_tier(name, tier):
    """CLAN_TIERS upsert: 닉(tnorm) 있으면 티어 변경, 없으면 추가."""
    try:
        ws = _clan_tiers_ws()
        if not ws: return False
        rows = ws.get_all_values()
        h = rows[0] if rows else ["닉네임", "티어"]
        ni = h.index("닉네임") if "닉네임" in h else 0
        ti = h.index("티어") if "티어" in h else 1
        key = tnorm(name)
        for idx, r in enumerate(rows[1:], start=2):
            if len(r) > ni and tnorm(r[ni]) == key:
                ws.update_cell(idx, ti + 1, tier); load_clan_tiers(); return True
        new = [""] * max(len(h), 2); new[ni] = name; new[ti] = tier
        ws.append_row(new); load_clan_tiers(); return True
    except Exception:
        return False

def delete_clan_tier(name):
    try:
        ws = _clan_tiers_ws()
        if not ws: return False
        rows = ws.get_all_values()
        h = rows[0]; ni = h.index("닉네임") if "닉네임" in h else 0
        key = tnorm(name)
        for idx, r in enumerate(rows[1:], start=2):
            if len(r) > ni and tnorm(r[ni]) == key:
                ws.delete_rows(idx); load_clan_tiers(); return True
        return False
    except Exception:
        return False

def list_clan_tiers():
    """현재 CLAN_TIERS 전체 [(닉,티어)] (관리 UI용)."""
    try:
        ws = _clan_tiers_ws()
        if ws:
            rows = ws.get_all_values()
            if rows and len(rows) >= 2:
                h = rows[0]
                ni = h.index("닉네임") if "닉네임" in h else 0
                ti = h.index("티어") if "티어" in h else 1
                return [(r[ni].strip(), r[ti].strip()) for r in rows[1:]
                        if len(r) > max(ni, ti) and r[ni].strip()]
    except Exception: pass
    return []

# ===== 마스터 내부티어표 자동 동기화(2026-07-03 사장님 지시: "항상 무조건 연동유지") =====
# 사장님이 직접 편집하는 시각적 티어 차트(별도 시트) → CLAN_TIERS(SSOT) 를 호스트가 15분 주기 upsert(추가·변경만, 삭제 없음).
# 읽기는 전부 공개 gviz CSV(서비스계정 읽기 할당량 0), 쓰기만 서비스계정(별개 할당량) — 429 상황에도 안전.
MASTER_TIER_SHEET_ID = "1UFuAYsXZGMquChIZY-HGsEbE5fmzk4apgWEwthvpQ44"
CLAN_TIERS_GID = 354094721

def _fetch_public_csv(doc_id, gid=None, sheet=None, headers=None, timeout=20):
    import urllib.request, urllib.parse
    q = ("gid=" + str(gid)) if gid is not None else ("sheet=" + urllib.parse.quote(str(sheet)))
    if headers is not None: q += "&headers=" + str(headers)   # 데이터 시트는 headers=1 권장(다중행 헤더 오감지 방지)
    url = "https://docs.google.com/spreadsheets/d/" + doc_id + "/gviz/tq?tqx=out:csv&" + q
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

def _parse_master_tier_chart(csv_text):
    """시각적 격자 차트 → [(닉,티어)]. 등급행(上/中/下) 기준 열 동적 매핑(열 이동에도 안전). 실패·규모미달 시 None."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(csv_text)))
    gr = -1
    for i, r in enumerate(rows):
        vals = [x.strip() for x in r]
        if "上등급" in vals and "下등급" in vals:
            gr = i; break
    if gr < 1: return None
    grp_row = rows[gr - 1]                       # 바로 윗행 = 그룹(0티어/I/II/III)
    GRP = {"0티어": "0", "I티어": "1", "II티어": "2", "III티어": "3"}
    col_tier = {}; cur = None
    width = max(len(grp_row), len(rows[gr]))
    for c in range(width):
        g_raw = (grp_row[c] if c < len(grp_row) else "").replace(" ", "").strip()
        if g_raw in GRP: cur = GRP[g_raw]
        if g_raw == "0티어":
            col_tier[c] = "0"; continue
        gd = (rows[gr][c] if c < len(rows[gr]) else "").strip()
        if cur and cur != "0" and gd[:1] in ("上", "中", "下"):
            col_tier[c] = cur + gd[0]
    if len(col_tier) < 7: return None            # 열 매핑 절반 미만=구조 변경 → 스킵
    out = []
    for r in rows[gr + 2:]:                      # gr+1=닉네임 헤더행 → 그 다음부터
        c1 = (r[1] if len(r) > 1 else "").strip()
        if re.match(r"^\d?티어", c1): break      # 하단 legend('0티어'/'1티어 상'…) 도달 시 중단
        for c, tier in col_tier.items():
            nm = (r[c] if len(r) > c else "").strip()
            if not nm or nm == "-": continue
            if ("티어" in nm) or ("등급" in nm) or nm == "닉네임": continue
            out.append((nm, tier))
    return out if len(out) >= 80 else None       # 규모 미달=편집 중일 가능성 → 이번 주기 스킵

def sync_master_tier_chart():
    """마스터 차트 → CLAN_TIERS upsert(추가·변경만, 삭제 없음). 변동 있을 때만 1회 전체쓰기. 호스트에서만 호출."""
    try:
        master = _parse_master_tier_chart(_fetch_public_csv(MASTER_TIER_SHEET_ID, 0))
        if not master: return False
        import csv as _csv, io as _io
        cur_rows = list(_csv.reader(_io.StringIO(_fetch_public_csv(DOCUMENT_ID, CLAN_TIERS_GID))))
        if not cur_rows or (cur_rows[0][0] if cur_rows[0] else "").strip() != "닉네임": return False
        cur_data = [[r[0].strip(), (r[1].strip() if len(r) > 1 else "")] for r in cur_rows[1:] if r and r[0].strip()]
        if len(cur_data) < 150: return False     # gviz 잘림 등 이상 → 전체쓰기 금지(안전판)
        m_map = {}; m_order = []
        for nm, t in master:
            k = tnorm(nm)
            if k not in m_map: m_order.append(k)
            m_map[k] = (nm, t)
        changed = 0; matched = set(); out_rows = []; hist = []   # hist: 🎖 티어 변동 이력(TIER_HISTORY)
        for nk, tier in cur_data:
            k = tnorm(nk)
            if k in m_map:
                matched.add(k)
                if m_map[k][1] != tier:
                    changed += 1
                    hist.append([nk, tier, m_map[k][1]])         # [닉, 이전티어, 새티어]
                out_rows.append([nk, m_map[k][1]])
            else:
                out_rows.append([nk, tier])      # 표에 없는 기존 인원은 유지(삭제 없음)
        appends = [m_map[k] for k in m_order if k not in matched]
        for nm, t in appends: hist.append([nm, "", t])           # 신규 부여(이전티어 없음)
        if changed == 0 and not appends: return True   # 이미 일치 → 쓰기 생략
        full = [["닉네임", "티어"]] + out_rows + [[nm, t] for nm, t in appends]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(resource_path('credentials.json.json'), scope)
        tok = creds.get_access_token().access_token
        url = ("https://sheets.googleapis.com/v4/spreadsheets/" + DOCUMENT_ID +
               "/values/CLAN_TIERS!A1?valueInputOption=RAW")
        resp = requests.put(url, headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
                            data=json.dumps({"values": full}), timeout=30)
        if resp.status_code == 200:
            _append_tier_history(hist, tok)      # 🎖 티어 변동 이력 적재(웹 '내부티어 기록' 카드)
            try: load_clan_tiers()               # 앱 메모리 즉시 갱신
            except Exception: pass
            return True
        return False
    except Exception:
        return False

def _append_tier_history(hist, tok):
    """🎖 [2026-07-15 사장님 지시] 티어 변동을 TIER_HISTORY 시트에 append (op.gg 과거티어 스타일 기록).
       CLAN_TIERS는 현재값만 덮어쓰므로 변동 기록이 남지 않던 문제를 보완. 변동이 있을 때만, 1회만 시도(쿼터 안전)."""
    if not hist: return
    try:
        today = time.strftime("%Y-%m-%d")        # 호스트 PC 로컬시간(KST)
        rows = [[nk, prev, new, today] for nk, prev, new in hist]
        url = ("https://sheets.googleapis.com/v4/spreadsheets/" + DOCUMENT_ID +
               "/values/TIER_HISTORY!A1:D1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS")
        r = requests.post(url, headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
                          data=json.dumps({"values": rows}), timeout=30)
        if r.status_code == 200:
            print(f"[tier] 티어 변동 {len(rows)}건 → TIER_HISTORY 기록", flush=True)
        else:
            print(f"[tier] TIER_HISTORY 기록 실패({r.status_code}) — 이번 변동은 미기록", flush=True)
    except Exception as e:
        print(f"[tier] TIER_HISTORY 기록 예외: {e}", flush=True)   # 실패해도 본 동기화는 계속

# ===== 솔로랭크 조회(Riot API) — 내부티어 평가의 객관 앵커. riot_key.txt 있을 때만 작동 =====
def load_riot_key():
    """riot_key.txt(호스트 로컬)에서 Riot API 키 로드. 없으면 None → 솔랭 기능 비활성."""
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    for p in [resource_path("riot_key.txt"), os.path.join(base, "riot_key.txt"),
              r"C:\SquadAnalyzer\riot_key.txt", os.path.join(base, "..", "SquadBot", "riot_key.txt")]:
        try:
            if p and os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f: k = f.read().strip()
                if k: return k
        except Exception: pass
    return None

# ===== 🧠 [v81.74 사장님 지시] 밴픽 실시간 코칭 — claude_key.txt 있는 PC에서만 작동(없으면 완전 비활성) =====
#   설계: 내 픽 차례에만 1회 호출(밴픽 30초 제한 → 저지연 우선). 컨텍스트는 '현재 밴픽판 + 내 챔프풀'만(작음).
#   비용: 시스템 프롬프트(코칭 규칙+클랜 챔프 메타)는 프롬프트 캐싱 → 2번째 호출부터 그 부분 1/10 가격.
def load_claude_key():
    """claude_key.txt에서 Anthropic API 키 로드. 없으면 None → 고스트밴픽왕 비활성(타 클랜원 무해).
       [v81.75] 메모장이 붙이는 '.txt.txt', 대소문자, 흔한 설치 경로까지 폭넓게 탐색(사장님 '키 넣었는데 안 됨' 대응)."""
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    names = ["claude_key.txt", "claude_key.txt.txt", "claude_key", "CLAUDE_KEY.txt"]
    dirs = [base, os.path.join(base, ".."), r"C:\SquadAnalyzer", os.path.expanduser("~\\Desktop"),
            os.path.expanduser("~"), os.getcwd()]
    cands = [resource_path("claude_key.txt")]
    for d in dirs:
        for n in names:
            try: cands.append(os.path.join(d, n))
            except Exception: pass
    for p in cands:
        try:
            if p and os.path.exists(p):
                with open(p, "r", encoding="utf-8-sig") as f: k = f.read().strip().strip('"').strip("'")
                if k and k.startswith("sk-"):
                    return k
                if k:   # 파일은 있는데 내용이 키 형식이 아님 → 화면에 알림(조용한 실패 방지)
                    with gui_lock:
                        gui_data["draft_advice"] = f"⚠️ 고스트밴픽왕: 키 파일 내용이 이상해요\n({os.path.basename(p)} — 'sk-'로 시작해야 합니다)"
                        gui_data["draft_advice_ts"] = time.time()
        except Exception: pass
    return None

DRAFT_MODEL = "claude-sonnet-5"     # 밴픽 30초 제한 → 저지연/저비용 우선(품질 부족하면 claude-opus-4-8로 상향)
_DRAFT_SEEN = set()                 # 같은 밴픽 상황 중복 호출 방지(상태 해시)
_DRAFT_BUSY = [False]
_DRAFT_POOL_CACHE = {}              # {내이름: [(챔프, 판수, 승)]} — 밴픽당 1회 계산

# ===== 🧠 [v82.29 사장님 지시] 내전 특화 컨텍스트 — "일반 LoL 지식"이 모르는 클랜 고유 데이터 =====
#   설계 근거(2026-07-21 실측): 협곡 485게임 기준 (플레이어,챔프) 5판↑ 230쌍 = 챔프폭 신호는 쓸 만함.
#   반면 (챔프A vs 챔프B) 라인 매치업은 3판↑이 199종뿐 = 학습 불가 → 상성 판단은 LLM 지식에 맡기고
#   우리는 '누가 뭘 잘하나 / 누가 누구를 이겨왔나'만 사실로 제공하는 역할 분담.
#   ⚠️ 시트는 1회만 스캔해 인덱스로 캐시(10분) — 10명 각각 스캔하면 밴픽 30초 안에 못 끝냄.
_CLAN_IDX = {"ts": 0.0, "by_pu": {}, "h2h": {}, "syn": {}, "nm2pu": {}}

def _clan_index(force=False):
    """내전 전적 1회 스캔 → {puuid: 챔프폭·주포지션}, 맞대결(h2h), 동료(syn) 인덱스. gviz 캐시라 할당량 0."""
    now = time.time()
    if not force and _CLAN_IDX["ts"] and (now - _CLAN_IDX["ts"]) < 600: return _CLAN_IDX
    by_pu, h2h, syn = {}, {}, {}
    mu1, mu2, mu3 = {}, {}, {}   # ⚔️ [v82.35] 라인 매치업: (내챔,상대챔) / (선수,내챔,상대챔) / (선수,상대챔)
    _lo_recs = []                # 📊 [v82.40] 저티어 오프롤 성과픽용 원자료 (pu, 포지션, 챔프, 승) — 협곡만·시간순
    _bp_ban, _bp_side = {}, {}   # [v82.32] 견제압력용: {gid:{진영:set(밴)}}, {gid:{puuid:진영}} — 협곡만
    try:
        if not global_spreadsheet: return _CLAN_IDX
        # [2026-07-30 사장님 지시] AI 코치는 협곡만 — 칼바람은 챔프 선택 성격이 달라 장인 판단을 왜곡한다.
        for _tab in ("CLASSIC_NORMAL",):
            try: tab = global_spreadsheet.worksheet(_tab)
            except Exception: continue
            rows = get_sheet_data_cached(tab)
            if not rows or len(rows) < 2: continue
            h = rows[0]
            ci = lambda n: h.index(n) if n in h else -1
            c_g, c_pu, c_ch, c_rs = ci("게임ID"), ci("PUUID"), ci("챔피언"), ci("결과")
            c_nm, c_ps, c_tm = ci("소환사명"), ci("포지션"), ci("진영")
            c_bn = ci("밴")
            c_mv, c_kd, c_gp = ci("매치평가"), ci("KDA"), ci("지표")   # 🕸 [v82.86] 육각형 축 원자료
            c_pt = ci("패치버전")
            # 🕸 [검증 지적] 웹 육각형 비교군은 '최신 패치' 화면 기준 — rad 집계도 최신 패치 행만
            _pset = set()
            for _r0 in rows[1:]:
                if 0 <= c_pt < len(_r0):
                    _pv0 = str(_r0[c_pt] or "").strip().lstrip("vV")
                    if _pv0: _pset.add(_pv0)
            def _pnum(pp):
                try:
                    aa = pp.split(".")
                    return int(aa[0]) * 1000 + int(aa[1])
                except Exception: return -1
            _latest_patch = max(_pset, key=_pnum) if _pset else ""
            if min(c_g, c_pu, c_ch, c_rs) < 0: continue
            per_game = {}
            for r in rows[1:]:
                if len(r) <= max(c_g, c_pu, c_ch, c_rs): continue
                res = str(r[c_rs]).strip()
                if res not in ("승리", "패배"): continue
                pu = str(r[c_pu]).strip().lower()
                if not pu: continue
                gid = str(r[c_g]).strip()
                if gid in per_game and pu in per_game[gid]: continue   # 중복행 방어
                ch = str(r[c_ch]).strip()
                nm = str(r[c_nm]).strip() if 0 <= c_nm < len(r) else ""
                ps = str(r[c_ps]).strip() if 0 <= c_ps < len(r) else ""
                tm = str(r[c_tm]).strip() if 0 <= c_tm < len(r) else ""
                e = by_pu.setdefault(pu, {"name": nm, "champs": {}, "pos": {}, "g": 0, "w": 0})
                # 🎭 [2026-08-10] 익명화 백필 행(소환사명=챔피언명·태그 없음)은 대표닉 갱신에서 제외
                if nm and "#" in nm and nm.replace(" ", "") != ch.replace(" ", ""): e["name"] = nm
                e["g"] += 1; e["w"] += (res == "승리")
                # 🕸 [v82.86] 웹 육각형과 동일한 6축 원자료(포지션별) — 캐리·성장·시야·생존·교전·챔프폭
                _pv = str(r[c_pt] or "").strip().lstrip("vV") if 0 <= c_pt < len(r) else ""
                if ps and ps != "선택안함" and _latest_patch and _pv == _latest_patch:
                    rd = e.setdefault("rad", {}).setdefault(ps, {"g": 0, "mvp": 0, "csS": 0.0, "csN": 0,
                                                                 "vsS": 0.0, "vsN": 0, "dS": 0, "kaS": 0, "kn": 0, "ch": set()})
                    rd["g"] += 1
                    if 0 <= c_mv < len(r) and str(r[c_mv]).strip() == "MVP": rd["mvp"] += 1
                    if ch: rd["ch"].add(re.sub(r"\s+", "", ch))   # 표기 변형('자르반 4세'/'자르반4세') 1챔프로
                    if 0 <= c_kd < len(r):
                        try:
                            _k, _d, _a = [int(x) for x in str(r[c_kd]).split("/")]
                            rd["dS"] += _d; rd["kaS"] += _k + _a; rd["kn"] += 1
                        except Exception: pass
                    if 0 <= c_gp < len(r):
                        _o = {}
                        for _t in str(r[c_gp] or "").split("|"):
                            _m = re.match(r"^([a-z]+)(-?\d+(?:\.\d+)?)$", _t.strip())
                            if _m: _o[_m.group(1)] = float(_m.group(2))
                        if _o.get("m"):
                            if _o.get("cs") is not None: rd["csS"] += _o["cs"] / _o["m"]; rd["csN"] += 1
                            if _o.get("vs") is not None: rd["vsS"] += _o["vs"]; rd["vsN"] += 1
                if ch:
                    cw = e["champs"].setdefault(ch, [0, 0]); cw[0] += 1; cw[1] += (res == "승리")
                    if ps and ps != "선택안함":   # [v82.40] 챔프별 '어느 라인에서 쌓은 기록인지' — 교차라인 숙련 과신 방지
                        _cp = e.setdefault("chpos", {}).setdefault(ch, {}); _cp[ps] = _cp.get(ps, 0) + 1
                if ps and ps != "선택안함": e["pos"][ps] = e["pos"].get(ps, 0) + 1
                per_game.setdefault(gid, {})[pu] = (tm, res, ch, ps)   # [v82.35] 매치업용 챔프·포지션 동반
                if _tab == "CLASSIC_NORMAL":
                    _lo_recs.append((pu, ps, ch, res == "승리"))   # 📊 저티어 오프롤 통계용
                if _tab == "CLASSIC_NORMAL":   # [v82.32] 견제압력 원자료(협곡만 — 칼바람은 밴 없음)
                    _bp_side.setdefault(gid, {})[pu] = tm
                    _b = str(r[c_bn]).strip() if 0 <= c_bn < len(r) else ""
                    if _b and _b not in ("밴 없음", "밴 안함", "기록 대기", "결과 대기", "평가 대기", "알수없음"):
                        _bp_ban.setdefault(gid, {}).setdefault(tm, set()).add(_b)
            for gid, mem in per_game.items():
                items = list(mem.items())
                # ⚖️ [v82.35] 그 판의 '팀 평균 내부티어차' — 매치업 승률의 최대 교란요인(실측 1티어당 ±15%p).
                #    0티어가 최상위이므로, (내 팀 평균 − 상대 평균)이 양수면 우리 팀이 더 약했다는 뜻.
                _tsum, _tcnt = {}, {}
                for _p, (_t, _r, _c, _s) in mem.items():
                    _tv = tier_of((by_pu.get(_p) or {}).get("name") or "")
                    try: _tv = int(str(_tv)[0]) if _tv not in (None, "") else None
                    except Exception: _tv = None
                    if _tv is not None and _t:
                        _tsum[_t] = _tsum.get(_t, 0) + _tv; _tcnt[_t] = _tcnt.get(_t, 0) + 1
                _tavg = {k: _tsum[k] / _tcnt[k] for k in _tsum if _tcnt.get(k, 0) >= 4}
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        a, (ta, ra, ca, pa) = items[i]; b, (tb, rb, cb, pb) = items[j]
                        if not ta or not tb: continue
                        k = (a, b) if a < b else (b, a)
                        first_res = ra if k[0] == a else rb
                        d = (syn if ta == tb else h2h).setdefault(k, [0, 0])
                        d[0] += 1; d[1] += (first_res == "승리")
                        # ⚔️ [v82.35] 라인 매치업 — 같은 포지션·다른 진영일 때만 '맞라인'으로 인정
                        if ta != tb and ca and cb and pa and pa == pb and pa != "선택안함":
                            for _me, _op, _mt, _ot in (((a, ca, ra), (b, cb), ta, tb),
                                                       ((b, cb, rb), (a, ca), tb, ta)):
                                _pu2, _mc, _rs2 = _me; _oc = _op[1]
                                _w2 = 1 if _rs2 == "승리" else 0
                                # 팀 전력차(양수 = 우리 팀이 더 약했음). 티어 정보 부족하면 0으로 둔다.
                                _td = 0.0
                                if _mt in _tavg and _ot in _tavg: _td = _tavg[_mt] - _tavg[_ot]
                                for _d, _k in ((mu1, (_mc, _oc)), (mu2, (_pu2, _mc, _oc)), (mu3, (_pu2, _oc))):
                                    _e2 = _d.setdefault(_k, [0, 0, 0.0])
                                    _e2[0] += 1; _e2[1] += _w2; _e2[2] += _td
    except Exception: pass
    # 이름(태그·공백 무시) → puuid 폴백맵: 토너먼트 드래프트 등에서 상대 puuid가 빈 경우 대비
    nm2pu = {}
    try:
        for _pu, _e in by_pu.items():
            _k = tnorm(_e.get("name") or "")
            if _k and (_k not in nm2pu or _e["g"] > by_pu[nm2pu[_k]]["g"]): nm2pu[_k] = _pu
    except Exception: pass
    # 🎯 [v82.32] 견제 압력 — 웹(computeBanPressure)과 동일 산식. {puuid: [{champ,targeted,z}...]}
    bp = {}
    try:
        _gs = [g for g in _bp_ban if len(_bp_side.get(g, {})) >= 8]
        if _gs:
            for _pu, _e in by_pu.items():
                _mains = sorted(((c, g) for c, (g, w) in _e["champs"].items() if g >= 4), key=lambda x: -x[1])[:6]
                if not _mains: continue
                _pres = [g for g in _gs if _pu in _bp_side.get(g, {})]
                _abs = [g for g in _gs if _pu not in _bp_side.get(g, {})]
                if len(_pres) < 8 or len(_abs) < 20: continue
                _out = []
                for _c, _n in _mains:
                    _ino = 0
                    for _g in _pres:
                        _opp = "레드팀" if _bp_side[_g].get(_pu) == "블루팀" else "블루팀"
                        if _c in _bp_ban[_g].get(_opp, set()): _ino += 1
                    _outo = sum(0.5 for _g in _abs if any(_c in s for s in _bp_ban[_g].values()))
                    _a, _b = _ino / len(_pres), _outo / len(_abs)
                    _se = math.sqrt(max(_a * (1 - _a), 1e-6) / len(_pres) + max(_b * (1 - _b), 1e-6) / len(_abs))
                    _z = (_a - _b) / _se if _se > 0 else 0.0
                    if _z > 1.5 and _a > _b:
                        _out.append({"champ": _c, "targeted": int(round((_a - _b) * 100)), "z": round(_z, 1)})
                if _out:
                    _out.sort(key=lambda x: -x["targeted"])
                    bp[_pu] = _out
    except Exception as _e:
        print(f"[banpressure] 코치용 계산 실패(무시): {_e}", flush=True)
    # 🎯 [v82.40] 선픽 안전도 — (선수,챔프)가 '여러 상대를 만나고도 카운터당한 매치업이 없는가'.
    #   safe[(pu,champ)] = [총판, 총승, 상대종류수, 카운터매치업수(3판↑ 승률40%↓)]. mu2에서 요약.
    safe = {}
    try:
        for (_pu2, _mc2, _oc2), _v2 in mu2.items():
            _n2, _w2 = _v2[0], _v2[1]
            _s = safe.setdefault((_pu2, _mc2), [0, 0, 0, 0])
            _s[0] += _n2; _s[1] += _w2; _s[2] += 1
            if _n2 >= 3 and _w2 / _n2 < 0.4: _s[3] += 1
    except Exception: pass
    # 📊 [v82.40] 저티어(2·3) 오프롤 성과픽 — 실측+반분 재현성 통과분만(우연 필터). 하드코딩 금지 원칙에 따라 매번 계산.
    loff_good_txt, loff_bad_txt = "", ""
    try:
        _mp2 = {p2: max(e2["pos"].items(), key=lambda x: x[1])[0]
                for p2, e2 in by_pu.items() if e2.get("pos") and sum(e2["pos"].values()) >= 8}
        _stat = {}
        _half = len(_lo_recs) // 2
        for _i4, (_pu4, _ps4, _ch4, _w4) in enumerate(_lo_recs):
            if not _ch4 or _pu4 not in _mp2 or _mp2[_pu4] == _ps4: continue
            _tv4 = str(tier_of((by_pu.get(_pu4) or {}).get("name") or "") or "")
            if not _tv4 or _tv4[0] not in ("2", "3"): continue
            _e4 = _stat.setdefault(_ch4, [0, 0, 0, 0, 0, 0])   # n,w, 전반n,전반w, 후반n,후반w
            _e4[0] += 1; _e4[1] += _w4
            if _i4 < _half: _e4[2] += 1; _e4[3] += _w4
            else: _e4[4] += 1; _e4[5] += _w4
        _good, _bad = [], []
        for _ch4, (_n4, _w4b, _n1, _w1, _n2, _w2b) in _stat.items():
            _wr4 = _w4b / _n4 * 100
            if (_n4 >= 8 and _wr4 >= 60 and _n1 >= 3 and _n2 >= 3
                    and _w1 / _n1 >= 0.5 and _w2b / _n2 >= 0.5):   # 반분 양쪽 다 50%↑ = 우연 필터
                _good.append((round(_wr4), _ch4, _n4))
            elif _n4 >= 10 and _wr4 <= 35:
                _bad.append((round(_wr4), _ch4, _n4))
        _good.sort(reverse=True); _bad.sort()
        loff_good_txt = " · ".join(f"{c} {n}판{w}%" for w, c, n in _good[:6])
        loff_bad_txt = " · ".join(f"{c} {n}판{w}%" for w, c, n in _bad[:5])
    except Exception: pass
    # 🛟 [2026-07-31] 실패 결과를 캐시에 굳히지 않는다.
    #   시트 읽기가 한 번 막히면(429 등) by_pu 가 빈 채로 ts 가 찍혀, 10분 동안 "클랜 데이터 없음"이
    #   그 판과 다음 판까지 이어졌다. 빈 결과는 캐시하지 말고 다음 호출에서 곧바로 다시 시도한다.
    #   (직전에 성공한 인덱스가 있으면 그걸 그대로 유지 — 빈 값으로 덮어쓰지 않는다.)
    if not by_pu:
        if _CLAN_IDX.get("by_pu"):
            print("[draft] 클랜 인덱스 갱신 실패 — 직전 인덱스 유지(재시도 예정)", flush=True)
        else:
            print("[draft] 클랜 인덱스가 비었습니다 — 다음 호출에서 재시도", flush=True)
        return _CLAN_IDX
    _CLAN_IDX.update({"ts": now, "by_pu": by_pu, "h2h": h2h, "syn": syn, "nm2pu": nm2pu, "bp": bp,
                      "mu1": mu1, "mu2": mu2, "mu3": mu3, "safe": safe,
                      "loff_good_txt": loff_good_txt, "loff_bad_txt": loff_bad_txt})
    return _CLAN_IDX

def _clan_pu(pu, nm, idx):
    """puuid 우선, 없으면 소환사명으로 해석 → 인덱스 키(puuid). 못 찾으면 ''."""
    k = str(pu or "").strip().lower()
    if k and k in (idx.get("by_pu") or {}): return k
    k2 = tnorm(nm or "")
    return (idx.get("nm2pu") or {}).get(k2, "") if k2 else ""

def _clan_line(pu, idx, limit=4, min_g=3):
    """puuid → '- 이름(주포지션) [내전 N판]: 챔프 N판 X% · …' 한 줄. 표본 없으면 빈 문자열."""
    e = (idx.get("by_pu") or {}).get(str(pu or "").strip().lower())
    if not e: return ""
    ch = sorted(([c, g, w] for c, (g, w) in e["champs"].items() if g >= min_g), key=lambda x: -x[1])[:limit]
    if not ch: return ""
    mp = max(e["pos"].items(), key=lambda x: x[1])[0] if e["pos"] else ""
    nm = str(e["name"]).split("#")[0].strip() or "클랜원"
    _tv = tier_of(e.get("name") or "")   # [v82.40] 내부티어 — P3·P4 판단용
    return (f"- {nm}{f'({mp})' if mp else ''}{f'[{_tv}티어]' if _tv not in (None, '') else ''} [내전 {e['g']}판 {round(e['w']/e['g']*100) if e['g'] else 0}%]: "
            + " · ".join(f"{c} {g}판 {round(w/g*100) if g else 0}%" for c, g, w in ch))

def _safe_pick_txt(my_pu, my_pool, idx, opp_champs, my_pos=""):
    """🎯 [v82.40] 선픽 안전 추천.
       A(일반): 내 챔프 중 '여러 상대(3종↑)를 8판↑ 겪고도 카운터당한 매치업 0'인 것.
       B(이 상대): 그 챔프가 '지금 이 적팀이 뽑을 법한 챔프'를 상대로 강했는지/약했는지 표본 3판↑만.
       각 챔프에 '어느 라인에서 쌓은 기록인지'를 붙인다 — 미드 숙련을 탑 배정 판에 그대로 신뢰하는 오류 방지.
       반환 (일반문구, 이상대문구). 표본 없으면 빈 문자열."""
    safe = idx.get("safe") or {}
    mu2 = idx.get("mu2") or {}
    pu = str(my_pu or "").strip().lower()
    if not pu: return "", ""
    _chpos = ((idx.get("by_pu") or {}).get(pu) or {}).get("chpos") or {}
    def _postag(_c):
        _d = _chpos.get(_c) or {}
        if not _d: return ""
        _tp, _tn = max(_d.items(), key=lambda x: x[1])
        _tag = f" [{_tp} {_tn}판]"
        if my_pos and my_pos != "선택안함" and _tp != my_pos and _d.get(my_pos, 0) < 3:
            _tag += f" ⚠️지금 배정({my_pos})과 다른 라인 숙련"
        return _tag
    gen, opp = [], []
    _oc_set = set(x for x in (opp_champs or []) if x)
    for _c, _g, _w in (my_pool or [])[:14]:
        e = safe.get((pu, _c))
        if e and e[0] >= 8 and e[2] >= 3:
            _n, _wn, _kinds, _bad = e
            _wr = round(_wn / _n * 100)
            if _bad == 0 and _wr >= 52:
                gen.append(f"- {_c}: 상대 {_kinds}종 {_n}판 {_wr}% · 카운터당한 판 없음{_postag(_c)}")
        for _oc in _oc_set:
            v = mu2.get((pu, _c, _oc))
            if v and v[0] >= 3:
                _wr2 = round(v[1] / v[0] * 100)
                if _wr2 >= 60: opp.append(f"- {_c}(으)로 {_oc} 상대 {v[0]}판 {_wr2}% → 이번 상대에 강함")
                elif _wr2 <= 35: opp.append(f"- ⚠️{_c}(으)로 {_oc} 상대 {v[0]}판 {_wr2}% → 이번 상대엔 위험")
    return "\n".join(gen[:6]), "\n".join(opp[:6])

def _mu_lookup(pu, my_champ, opp_champ, idx, min_n=4):
    """⚔️ [v82.35] 라인 매치업 전적 — 구체적인 것부터 찾고, 표본이 모자라면 한 단계씩 물러선다.
       ① 이 선수가 이 챔프로 그 챔프 상대  ② 이 선수가 그 챔프 상대(내 챔프 무관)  ③ 클랜 전체 챔프 대 챔프
       ⚠️ 실측상 ①은 1.9%에서만 잡히고 ①②③ 합쳐도 약 39% → 없으면 조용히 생략(억지로 만들지 않음).
       반환 (근거라벨, 판수, 승수) 또는 (None,0,0)."""
    if not my_champ or not opp_champ: return None, 0, 0, 0.0
    pu = str(pu or "").strip().lower()
    for lab, key, src in (("이 선수 이 챔프", (pu, my_champ, opp_champ), "mu2"),
                          ("이 선수",         (pu, opp_champ),            "mu3"),
                          ("클랜 전체",       (my_champ, opp_champ),      "mu1")):
        try:
            rec = (idx.get(src) or {}).get(key)
            if not rec: continue
            n, w = rec[0], rec[1]
            td = (rec[2] / n) if len(rec) > 2 and n else 0.0   # 그 판들의 평균 팀 전력차
            if n >= min_n: return lab, n, w, td
        except Exception: pass
    return None, 0, 0, 0.0

def _mu_txt(pu, my_champ, opp_champ, idx, min_n=4):
    """'7판 2승 29% (이 선수) · 팀 전력 0.4티어 불리' 형태. 표본 없으면 빈 문자열.
       ⚖️ 팀 전력차를 함께 적는 이유: 이 승률은 라인전이 아니라 '팀의 승패'라, 전력이 기울었던
          판이 섞여 있으면 매치업 자체의 유불리로 오해하게 된다(실측 1티어당 ±15%p)."""
    lab, n, w, td = _mu_lookup(pu, my_champ, opp_champ, idx, min_n)
    if not lab: return ""
    s = f"{n}판 {w}승 {round(w / n * 100)}% ({lab})"
    if abs(td) >= 0.3:   # 0.3티어 미만은 노이즈 → 굳이 붙이지 않음
        s += f" · 그 판들 팀 전력 {abs(td):.1f}티어 " + ("불리" if td > 0 else "유리")
    return s

def _pair_txt(my_pu, other_pu, idx, kind, min_g):
    """맞대결(h2h)/동료(syn) 전적 문구. 표본 min_g 미만이면 빈 문자열(노이즈 차단)."""
    a, b = str(my_pu or "").strip().lower(), str(other_pu or "").strip().lower()
    if not a or not b or a == b: return ""
    k = (a, b) if a < b else (b, a)
    d = (idx.get(kind) or {}).get(k)
    if not d or d[0] < min_g: return ""
    my_w = d[1] if k[0] == a else d[0] - d[1]
    return f"{d[0]}판 {my_w}승 {d[0]-my_w}패 ({round(my_w/d[0]*100)}%)"

_QUIZ_PREF_CACHE = {"at": 0.0, "map": {}}


def _quiz_pref(force=False):
    """🗳️ [2026-07-30 사장님 지시] 밴픽 퀴즈에서 클랜원들이 직접 적어낸 '이 사람 상대면 이걸 자른다'.
       {상대닉: [(챔프, 표, 적중), ...]} — 코치 추천 순위의 근거로 쓴다. 실패하면 빈 값(무해)."""
    if not force and _QUIZ_PREF_CACHE["map"] and time.time() - _QUIZ_PREF_CACHE["at"] < 1800:
        return _QUIZ_PREF_CACHE["map"]
    out = {}
    try:
        import urllib.request as _u, csv as _csv, io as _io
        url = (f"https://docs.google.com/spreadsheets/d/{DOCUMENT_ID}/gviz/tq?tqx=out:csv"
               f"&sheet=QUIZ_PREF&headers=1")
        rows = list(_csv.reader(_io.StringIO(
            _u.urlopen(_u.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8)
            .read().decode("utf-8"))))
        if rows and len(rows) > 1:
            h = rows[0]
            ci = {c: i for i, c in enumerate(h)}
            for r in rows[1:]:
                try:
                    nm = r[ci["상대"]].strip(); ch = r[ci["챔피언"]].strip()
                    v = int(float(r[ci["표"]] or 0)); hit = int(float(r[ci["적중"]] or 0))
                except Exception: continue
                if nm and ch and v > 0: out.setdefault(nm, []).append((ch, v, hit))
            for nm in out: out[nm].sort(key=lambda x: -x[1])
    except Exception: pass
    _QUIZ_PREF_CACHE.update({"at": time.time(), "map": out})
    return out


def _pool_by_puuid(puuid, limit=6, pos=""):
    """[v81.77] PUUID로 그 사람의 챔피언별 (판수, 승) 상위 N — 밴 추천의 '상대 장인' 판단용.

    pos 를 주면 **그 포지션에서 실제로 쓴 전적만** 집계한다.
    [2026-08-03 사장님 제보] 정글 브라이어 원챔장인이 탑에 갔는데 브라이어 밴을 추천하던 문제.
      포지션 병기(v82.45)와 프롬프트 규칙(★장인 저격 밴은 포지션이 맞을 때만)만으로는 안 막혔다 —
      후보 목록 자체에서 빼야 한다. 쉬바나/녹턴 건과 같은 처방(데이터 레이어에서 차단).
    """
    key = str(puuid or "").strip().lower()
    if not key or not global_spreadsheet: return []
    want = str(pos or "").strip()
    agg = {}
    # 🎯 [2026-08-11 주간감사 반영] 밴 추천 위협 적중률 12%의 주범 = '옛날에 몇 판 한 잡픽'이
    #    후보로 올라오는 것(뽀삐 20회·로크 19회 헛방). 최근 사용 여부와 점유율을 같이 재서
    #    호출부가 '이번 판에 진짜 나올 픽'만 고를 수 있게 한다.
    _RECENT_DAYS = 90
    _cut = time.strftime("%Y-%m-%d", time.localtime(time.time() - _RECENT_DAYS * 86400))
    rec = {}      # 챔프 -> 최근 판수
    tot_all = 0   # (그 포지션) 총 판수
    tot_rec = 0   # (그 포지션) 최근 총 판수
    try:
        # [2026-07-30 사장님 지시] AI 코치는 협곡만 — 칼바람은 챔프 선택 성격이 달라 장인 판단을 왜곡한다.
        for _tab in ("CLASSIC_NORMAL",):
            try: tab = global_spreadsheet.worksheet(_tab)
            except Exception: continue
            rows = get_sheet_data_cached(tab)
            if not rows: continue
            h = rows[0]
            ci = lambda n: h.index(n) if n in h else -1
            c_pu, c_ch, c_rs, c_nm = ci("PUUID"), ci("챔피언"), ci("결과"), ci("소환사명")
            c_ps = ci("포지션")
            if min(c_pu, c_ch) < 0: continue
            if want and c_ps < 0: continue        # 포지션 열이 없으면 필터를 흉내내지 않는다
            for r in rows[1:]:
                if len(r) <= max(c_pu, c_ch): continue
                if str(r[c_pu]).strip().lower() != key: continue
                ch = str(r[c_ch]).strip()
                if not ch: continue
                if want:
                    _ps = str(r[c_ps]).strip() if len(r) > c_ps else ""
                    if _ps != want: continue
                g, w, nm = agg.get(ch, (0, 0, ""))
                nm = nm or (str(r[c_nm]).strip() if c_nm >= 0 and len(r) > c_nm else "")
                agg[ch] = (g + 1, w + (1 if (c_rs >= 0 and len(r) > c_rs and str(r[c_rs]).strip() == "승리") else 0), nm)
                tot_all += 1
                _c_dt = ci("날짜")
                if 0 <= _c_dt < len(r) and str(r[_c_dt]).strip()[:10] >= _cut:
                    rec[ch] = rec.get(ch, 0) + 1; tot_rec += 1
    except Exception: pass
    # 정렬: 최근 판수 우선 → 총 판수. 반환 원소 = [챔프, 총판, 승, 닉, 최근판, 점유율%(최근 없으면 통산 기준)]
    def _share(c, g):
        base = tot_rec if tot_rec >= 5 else tot_all
        num = rec.get(c, 0) if tot_rec >= 5 else g
        return round(num / base * 100) if base else 0
    out = sorted(([c, g, w, nm, rec.get(c, 0), _share(c, g)] for c, (g, w, nm) in agg.items()),
                 key=lambda x: (-x[4], -x[1]))[:limit]
    return out


def _enemy_ban_pool(pu, ep, cidx, limit=6):
    """밴 모드에서 상대 1명의 '이번 판에 실제로 나올 수 있는' 챔프폭 블록 → (머리말, [챔프표기…]).

    이번 판 포지션(ep)을 알면 그 자리 전적만 싣는다. 그 자리 전적이 아예 없으면 챔프를 싣지 않고
    '저격 밴 가치 없음'을 명시한다 — 다른 자리 주력은 이번 판에 나올 수 없으므로 후보가 아니다.
    """
    pu = str(pu or "").strip().lower()
    if not pu: return None
    _e = ((cidx or {}).get("by_pu") or {}).get(pu) or {}
    _cp = _e.get("chpos") or {}
    full = _pool_by_puuid(pu, limit=limit) or []
    nm = str(_e.get("name") or (full[0][3] if full and len(full[0]) > 3 else "") or "상대").split("#")[0].strip() or "상대"
    hdr = nm + (f" [이번 판 포지션: {ep}]" if ep else "")

    def _live(rows):
        """🎯 [2026-08-11 주간감사 실측 반영] '이번 판에 나올 픽'만 남긴다.
           과거 밴 로그 202건을 그 자리 점유율로 나눠 재보니 —
             점유 0%(그 자리 전적 없음) 64건 → 적중 0 / 1~9% 48건 → 적중 2(4%) / 10%↑ 90건 → 적중 27(30%).
           즉 점유 10% 미만 추천의 96%가 그 판에 등장조차 안 했다. 임계 10%가 최적점이었다
           (후보 55% 감축, 실제 적중은 29건 중 27건 유지, 정밀도 14%→30%).
           15%로 올리면 적중의 3분의 1을 잃어 과했다."""
        keep = [t for t in rows if len(t) < 6 or (t[5] >= 10 and t[1] >= 2)]
        return keep or rows[:2]      # 전부 걸러지면 최소한 주력 2개는 남긴다

    def _fmt(rows, with_pos):
        out = []
        for t in rows:
            c3, g3, w3 = t[0], t[1], t[2]
            s = f"{c3}({g3}판 {round(w3 / g3 * 100) if g3 else 0}%"
            if len(t) > 5:
                s += f"·최근90일 {t[4]}판·점유 {t[5]}%"
            if with_pos:
                _d = _cp.get(c3) or {}
                _mp = max(_d.items(), key=lambda x: x[1])[0] if _d else ""
                if _mp: s += f"·{_mp}전적"
            out.append(s + ")")
        return out

    if not ep:
        return (hdr, _fmt(_live(full), True)) if full else None
    lst = _pool_by_puuid(pu, limit=limit, pos=ep) or []
    if lst:
        return (hdr, _fmt(_live(lst), False))   # 전부 그 포지션 전적이라 병기가 불필요
    off = ", ".join(_fmt(full[:3], True))
    return (hdr, [f"※ {ep} 전적 0판 — 이 사람 저격 밴은 값이 없다"
                  + (f" (다른 자리 주력 {off} 은 이번 판에 못 씀)" if off else " (내전 전적 자체가 없음)")])

def _my_champ_pool(my_name, limit=12):
    """시트 전적에서 '내' 챔피언별 (판수, 승) 상위 N개. 라이브 중 서비스계정 호출 없이 gviz 캐시만 사용."""
    key = tnorm(my_name or "")
    if not key: return []
    if key in _DRAFT_POOL_CACHE: return _DRAFT_POOL_CACHE[key]
    agg = {}
    try:
        if not global_spreadsheet: return []
        # [2026-07-30 사장님 지시] AI 코치는 협곡만 — 칼바람 숙련을 협곡 챔프폭으로 세면 안 된다.
        for _tab_name in ("CLASSIC_NORMAL",):
            try: tab = global_spreadsheet.worksheet(_tab_name)
            except Exception: continue
            rows = get_sheet_data_cached(tab)   # gviz 캐시(읽기 할당량 0) — 라이브 중 서비스계정 미사용
            if not rows: continue
            h = rows[0]
            ci = lambda n: h.index(n) if n in h else -1
            c_nm, c_ch, c_rs = ci("소환사명"), ci("챔피언"), ci("결과")
            if min(c_nm, c_ch) < 0: continue
            for r in rows[1:]:
                if len(r) <= max(c_nm, c_ch, c_rs): continue
                if tnorm(r[c_nm]) != key: continue
                ch = str(r[c_ch]).strip()
                if not ch: continue
                g, w = agg.get(ch, (0, 0))
                agg[ch] = (g + 1, w + (1 if (c_rs >= 0 and str(r[c_rs]).strip() == "승리") else 0))
    except Exception: pass
    out = sorted(([c, g, w] for c, (g, w) in agg.items()), key=lambda x: -x[1])[:limit]
    _DRAFT_POOL_CACHE[key] = out
    return out

def _clan_meta_lines(limit=25):
    """클랜 챔피언 메타 요약(판수순 상위) — 시스템 프롬프트에 넣어 캐싱되는 '고정' 파트.

    [2026-07-31 수정] 예전엔 전당(HOF) 집계를 읽었는데, HOF 프리로드는 호스트 PC에서만 돌아
    구독자 PC에서는 이 값이 **항상** 비었다. 그 결과 밴 추천이 "클랜 내전 챔피언 메타도 표본 없음
    → 밴 근거 데이터 전무"로 나갔다(비호스트 전원 상시 발생). 코치가 이미 쓰는 _clan_index 로 바꿔
    호스트/구독자 구분 없이 같은 자료를 보게 한다. HOF 가 이미 있으면 그걸 먼저 쓴다(집계 재사용)."""
    rows = []
    try:
        gs = dict(gui_data.get("hof_classic", {}).get("global_stats", {}).get("전체 (ALL)", {}))
    except Exception:
        gs = {}
    for ch, st in (gs or {}).items():
        try:
            g = int(st.get("games", st.get("판수", 0)) or 0)
            w = int(st.get("wins", st.get("승", 0)) or 0)
            if g >= 4: rows.append((ch, g, round(w / g * 100)))
        except Exception: continue
    if not rows:                      # 구독자 PC(=HOF 없음) → 시트 인덱스에서 직접 집계
        try:
            agg = {}
            for _e in ((_clan_index() or {}).get("by_pu") or {}).values():
                for _ch, _gw in (_e.get("champs") or {}).items():
                    a = agg.setdefault(_ch, [0, 0]); a[0] += _gw[0]; a[1] += _gw[1]
            for _ch, (g, w) in agg.items():
                if g >= 4: rows.append((_ch, g, round(w / g * 100)))
        except Exception: pass
    rows.sort(key=lambda x: -x[1])
    return "\n".join(f"- {c}: {g}판 {wr}%" for c, g, wr in rows[:limit]) or "(클랜 표본 없음)"

# 📈 [v82.21] 현 패치 티어리스트 스크래퍼 — op.gg 챔피언 페이지(__next_f 스트림)에서 포지션별 랭킹 추출.
#   고스트밴픽왕 시스템 프롬프트에 주입(모델이 '요즘 OP'를 모름 → 현 메타 지식 보강). 12시간 캐시(+파일 영속).
_PATCH_META = {"ts": 0.0, "text": "", "patch": "", "fetching": False}
_PATCH_META_FILE = "patch_meta_cache.json"

def _fetch_patch_meta():
    """op.gg 에메랄드+ 티어리스트 → 포지션별 상위 8 + 고밴률 목록 텍스트. 실패 시 None."""
    import urllib.request as _u, gzip as _gz
    url = "https://op.gg/ko/lol/champions?region=kr&tier=emerald_plus"
    req = _u.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko", "Accept-Encoding": "gzip"})
    with _u.urlopen(req, timeout=15) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip": raw = _gz.decompress(raw)
        html = raw.decode("utf-8", "replace")
    pat = re.compile(
        r'\\"key\\":\\"[a-z0-9]+\\",\\"name\\":\\"([^"\\]+)\\",[^{]*?'
        r'\\"positionName\\":\\"(\w+)\\",\\"positionWinRate\\":([\d.]+),\\"positionPickRate\\":([\d.]+),'
        r'\\"positionBanRate\\":([\d.]+),[^{]*?\\"positionTierData\\":\{\\"tier\\":(\d+),\\"rank\\":(\d+)')
    pos_kor = {"TOP": "탑", "JUNGLE": "정글", "MID": "미드", "ADC": "원딜", "SUPPORT": "서폿"}
    by_pos = {}
    bans = []
    for m in pat.finditer(html):
        nm, pos, wr, pr, br, tier, rank = m.group(1), m.group(2).upper(), float(m.group(3)), float(m.group(4)), float(m.group(5)), int(m.group(6)), int(m.group(7))
        by_pos.setdefault(pos, []).append((rank, nm, tier, wr))
        if br >= 20: bans.append((br, nm, pos))
    if sum(len(v) for v in by_pos.values()) < 60: return None   # 파싱 실패/구조 변경 감지
    pm = re.search(r"/lol/([\d.]+)/champion/", html)
    patch = pm.group(1) if pm else ""
    lines = []
    for pos in ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT"):
        rows = sorted(by_pos.get(pos, []))[:8]
        if rows:
            lines.append(f"- {pos_kor[pos]}: " + ", ".join(f"{nm}({wr:.0f}%)" for _r, nm, _t, wr in rows))   # [2026-07-25 사장님 지시] T0·T1 코드 표기 제거(랭킹순 나열로 충분)
    _ban_max = {}
    for br, nm, _p in bans: _ban_max[nm] = max(_ban_max.get(nm, 0), br)   # 포지션별 중복 행 → 챔프당 1개
    top_bans = sorted(_ban_max.items(), key=lambda x: -x[1])[:8]
    if top_bans:
        lines.append("- 고밴률(OP 지표): " + ", ".join(f"{nm}({br:.0f}%)" for nm, br in top_bans))
    return {"patch": patch, "text": "\n".join(lines)}

def _patch_meta_text():
    """캐시된 티어리스트 텍스트 반환(+오래되면 백그라운드 갱신). 없으면 ''."""
    now = time.time()
    if not _PATCH_META["text"]:
        try:   # 파일 캐시 복원(재시작 직후)
            with open(_PATCH_META_FILE, encoding="utf-8") as f:   # 실행 폴더(config.json과 동일 위치)
                d = json.load(f)
            _PATCH_META.update({"ts": float(d.get("ts", 0)), "text": d.get("text", ""), "patch": d.get("patch", "")})
        except Exception: pass
    if (now - _PATCH_META["ts"] > 12 * 3600) and not _PATCH_META["fetching"]:
        _PATCH_META["fetching"] = True
        def _bg():
            try:
                r = _fetch_patch_meta()
                if r:
                    _PATCH_META.update({"ts": time.time(), "text": r["text"], "patch": r["patch"]})
                    try:
                        with open(_PATCH_META_FILE, "w", encoding="utf-8") as f:
                            json.dump({"ts": _PATCH_META["ts"], "text": r["text"], "patch": r["patch"]}, f, ensure_ascii=False)
                    except Exception: pass
                    print(f"[draft] 패치 메타 갱신 — {r['patch']} ({len(r['text'])}자)", flush=True)
            except Exception as e:
                print(f"[draft] 패치 메타 갱신 실패(무시): {e}", flush=True)
            finally:
                _PATCH_META["fetching"] = False
        threading.Thread(target=_bg, daemon=True).start()
    return _PATCH_META["text"]

# [v81.77] 픽 추천 품질 개선 — '사일러스 상대인데 알리스타 추천' 같은 매치업 무시 사례 대응.
#   핵심: 라인 매치업(내 상대 라이너)을 최우선으로 명시하고, 카운터당하는 픽은 아예 배제하도록 규칙화.
# [v82.21 전면 개편] 명장(양대인·김정수·씨맥류) 드래프트 이론 이식 — 윈컨디션 설계·픽순서·밸런스 점검.
_DRAFT_RULES = (
    "너는 LCK 우승팀 감독급 밴픽 전략가다. 명장들의 드래프트 이론(조합 컨셉 우선·구도 설계)을 따른다.\n"
    "지금 사용자의 **픽 차례**다. 남은 시간이 짧으니 결론부터, 그러나 아래 사고 순서를 반드시 지켜라.\n\n"
    "【★★맛장유 5원칙 — 모든 픽 판단에 최우선 적용】\n"
    "P1. **라인전 최소 반반**: 지는 라인전을 전제로 한 픽 금지. 못 이겨도 반반은 가져가야 이후 그림이 성립한다.\n"
    "P2. **상대 조합이 고밸류·탄탄하면 저밸류 픽 금지**: 실수해도 일어날 힘(목숨코인)이 없어지고,\n"
    "    스노우볼을 완벽히 굴려야만 이기는 고난이도 조합이 돼버린다.\n"
    "P3. **내부티어 높은 사람의 저밸류 픽은 손해**: 캐리를 해야 할 사람이 캐리를 못 하게 된다.\n"
    "    고티어(0·1티어)일수록 고밸류 캐리픽을 맡겨라. (티어 정보는 픽·팀원 줄의 'N티어' — 0이 최상위)\n"
    "P4. **저티어가 고티어를 쉽게 위협하는 픽은 고가치**: 예로 저티어 나서스가 라인전만 무난히 넘기면\n"
    "    타겟팅 쇠약으로 0티어 캐리에게도 무시 못 할 존재가 된다. 이런 '라인전만 넘기면 되는 견제픽'을 저티어에게 가산.\n"
    "P5. **팀 CC 총량이 많을수록 게임이 쉽다**: 동급 후보면 CC 있는 쪽을 우선하라.\n"
    "⚠️ **스킬 지식 주의**: 리워크·패치로 스킬이 바뀐 챔프가 있다(예: 스카너 궁은 더는 타겟팅이 아니라 스킬샷형).\n"
    "   특정 스킬의 메커니즘이 확실치 않으면 그것을 근거로 단정하지 말고, 클랜 내전의 판수·승률 데이터를 우선하라.\n"
    "⚠️ **솔랭 메타·티어리스트를 근거로 쓰지 마라** — 판단은 클랜 내전 데이터로만 한다.\n"
    "   추천하는 모든 줄에 클랜 숫자를 하나 이상 붙이고, 없으면 '(클랜 데이터 없음)'이라고 밝혀라.\n\n"
    "【명장의 사고 순서 — 반드시 이대로】\n"
    "1) **윈컨디션 설계**: 양팀 확정 픽을 보고 '우리는 무엇으로 이기는 조합인가'를 한 문장으로 정의하라.\n"
    "   조합 아키타입: ①한타 궁연계(원콤) ②포킹·공성 ③돌진 다이브 ④스플릿 1-3-1 ⑤하이퍼캐리 보호.\n"
    "   내 픽은 이 윈컨디션을 완성하는 조각이면 좋다. 단 ★내전에선 5명이 컨셉을 맞추는 일이 거의 없으니\n"
    "   (실측: 3명 이상 같은 컨셉 3%뿐), 컨셉을 억지로 맞추려 티어·상성·챔프폭을 희생하지 마라.\n"
    "   상대 조합의 윈컨디션도 정의하고, 그것을 깨는 픽이면 가산점.\n"
    "2) **라인 매치업**: 상대 라이너에게 카운터당하는 픽 절대 금지.\n"
    "   - [내 라인 상대]가 없으면, **픽 옆의 '← 이름(주:라인)'**(그 픽을 실제로 고른 사람)으로 상대를 특정하라.\n"
    "     챔프의 '통상 주 포지션'으로 단정하면 안 된다 — 럭스·세라핀처럼 두 라인 다 쓰는 챔프에서 반드시 틀린다.\n"
    "     예: 럭스를 고른 사람이 주:미드이고 서폿 유저는 럭스 전적이 0이면 → 그 럭스는 미드로 보는 게 맞다.\n"
    "     귀속 정보가 없으면 '상대 라이너 미확정'으로 두고 블라인드 안전픽으로 대응하라.\n"
    "   - 대표 함정: 사일러스 상대 강궁 챔프(궁 강탈), 짧은 사거리로 장사거리 포킹 상대, 돌진기로 CC덩어리에 진입.\n"
    "3) **픽 순서 읽기**: 내 라인의 상대가 아직 미확정이면 나는 '선픽' — 카운터 여지 적은 블라인드 안전픽·플렉스픽(2개 라인 가능) 우선.\n"
    "   [내 챔프 숙련도] 블록의 '카운터당한 판 없음'은 **숙련도 근거일 뿐 선픽 안전이 아니다**(정밀 카운터를\n"
    "   잘 안 가서 안 진 것일 수 있음). **블라인드 안전성은 라인전 특성으로 판단**하라: 붙어야만 힘쓰는 근접\n"
    "   이니시(상대 원거리에 무력)나 하드 카운터가 명확한 챔프만 후픽으로 돌리고, 사거리·안전한 파밍으로\n"
    "   라인전이 안정적인 챔프는 숙련만 높으면 선픽으로 무방하다. 챔프 이름으로 미리 단정 말고 실제 성립으로 판단.\n"
    "   (B) '이번 상대에 강함'이 겹치면 확신 강화, '위험'이 뜬 픽은 선픽 금지. 인용 시 판수를 함께.\n"
    "   상대 라이너가 이미 확정이면 '후픽' 이점 — 확실한 카운터픽을 노려라.\n"
    "4) **팀 밸런스 점검(★내가 유연할 때 특히 중요)**: AD/AP 밸런스·앞라인·이니시·스케일링·CC.\n"
    "   - **내가 여러 스타일을 소화 가능하면(AD·AP·탱 다 됨), 우리 팀에 부족한 쪽을 메우는 방향으로 추천하라.**\n"
    "     ① [우리 팀원 챔프폭]이 AP에 쏠려 있으면(=팀이 AP 선호) 나는 AD 쪽으로. 그 반대면 AP로.\n"
    "     ② 이미 픽된 우리 챔프에 AP가 많으면 나는 AD로(그 반대도). 각 챔프의 주 데미지 타입은 네가 판단하라.\n"
    "     ③ 특히 **내가 선픽(빠른 순서)이면** 팀 성향을 보고 미리 부족한 타입을 선점해 뒷사람 선택지를 넓혀라.\n"
    "   - 한쪽 데미지로만 몰리면 상대가 방어템 하나로 막으니, 밸런스가 조합의 기본이다.\n"
    "5) **사용자 챔프풀**: 다뤄본 챔프 우선 — 이론상 최적이어도 숙련 없는 픽은 후순위.\n"
    "6) **★내전 특화(이 클랜에서만 참인 정보)** — [상대/우리 팀원 내전 챔프폭]이 주어지면 반드시 활용하라.\n"
    "   - **상대 미확정 라이너 예측**: 아직 안 뽑은 상대는 자기 챔프폭 중에서 뽑는다. 그 사람의 최다판수 챔프를\n"
    "     '유력 픽'으로 가정하고, 그것에 지지 않는 픽을 골라라. (선픽 상황에서 이게 결정적)\n"
    "   - **우리 팀원 챔프폭**: 팀원이 못 다루는 챔프를 전제로 조합을 짜지 마라. 팀원 주력픽과 맞물리는 픽 우선.\n"
    "   - **맞대결 전적**: 특정 상대에게 계속 졌다면 같은 방식의 픽을 반복하지 마라.\n"
    "   - ⚠️ **표본 주의**: 5판 미만 기록은 우연이다. 판수가 적은 승률(예: 3판 100%)을 근거로 쓰지 마라.\n"
    "   - ⚠️ **[맞대결]·[동료와의 합] 수치는 개인 실력차가 섞인 값**이다(팀은 매판 랜덤 배정). '이 조합이 좋다/나쁘다'의\n"
    "     근거로 절대 쓰지 마라. 조합 판단은 오직 '팀원이 어떤 챔프를 다룰 수 있는가'(챔프폭)로만 하라.\n"
    "     맞대결 열세는 '그 상대가 강하니 안전한 픽을 골라라' 정도로만 참고하라.\n"
    "6-2) ⚔️**[내 챔프폭 × 이 라인 상대]**가 주어지면, 같은 매치업을 클랜에서 실제로 겪은 기록이다.\n"
    "   후보 둘이 비슷할 때 이걸로 가르되, 표본이 4~10판이라 오차가 크니 **조합·상성 판단을 뒤집지는 마라.**\n"
    "   인용할 땐 '레넥톤으로 나르 상대 7판 2승 29%'처럼 **판수를 반드시 함께** 말하라.\n"
    "7) 동급 후보면 **클랜 내전에서 실제로 성적이 좋았던 쪽**을 우선하라(판수 5판 이상). 판수를 함께 밝혀라.\n\n"
    "【절대 규칙】\n"
    "- 이미 밴되었거나 이미 픽된 챔피언은 추천 금지.\n"
    "- 사용자 라인이 아닌 포지션의 챔프를 추천하지 마라.\n"
    "- 상성상 불리한 픽을 '무난하다'는 이유로 추천하지 마라.\n"
    "- ★포지션을 지어내지 마라. 5명이 다 나오기 전에는 어떤 픽의 포지션도 확정이 아니다.\n"
    "  '서폿 럭스'처럼 단정하지 말고 '미드 유저가 고른 럭스'처럼 근거를 밝혀라. 근거가 없으면 포지션을 언급하지 마라.\n"
    "  ⚠️ 한 답변 안에서 같은 픽을 서로 다른 포지션으로 말하면 절대 안 된다(예: 앞에선 '서폿 럭스', 뒤에선 '상대 서폿은 쓰레쉬 선호').\n\n"
    "【출력 형식 — 한국어, 이 형식만·★최대한 짧게(오버레이 작은 창이라 시인성이 생명)】\n"
    "🆚 (상대 챔프 / '미확정')  🎯 (윈컨 5단어 이내)\n"
    "1. 챔피언명 — 이유 (★20자 이내, 판수% 포함 시 그것만)\n"
    "2. 챔피언명 — 이유\n"
    "3. 챔피언명 — 이유\n\n"
    "서술형 문장 금지·접속사 금지·중복 근거 금지. '무난함' 같은 두루뭉술한 말 금지.\n"
    "T0·T1·T2 같은 티어 코드 표기 금지 — 필요하면 'OP픽'·'현 메타 강챔'처럼 말로 써라.\n"
    "★사용자가 이미 아는 사실을 재나열 금지 — '파이크·카밀 밴당함' 같은 밴 목록 표기 절대 금지.\n"
    "  화면에 다 보이는 정보다. 추천 챔피언과 그 이유만 딱 보여줘라(밴은 후보 선정에서 조용히 제외만).\n"
    "예: '1. 제라스 — 17판 76%·선픽안전' / '2. 리산드라 — 돌진 받아치기'. 이 밀도로.\n\n"
    "★위 요약 뒤에 반드시 구분줄 '=====근거=====' 를 쓰고, 그 아래에 **판단 근거**를 항목당 한 줄씩(총 6줄 이내) 적어라.\n"
    "근거에는 왜 그 결론인지의 핵심 논리·데이터(판수%·견제압력·매치업)를 담는다. 사용자는 평소 요약만 보고,\n"
    "궁금할 때 근거를 펼쳐 본다 — 근거가 요약과 모순되면 안 된다."
)

# 🚫 [v81.77 사장님 지시] 밴 차례에도 AI 추천(5개) — 기존 통계 추천과 별개로 '구도'를 읽는 밴.
_DRAFT_BAN_RULES = (
    "너는 LCK 우승팀 감독급 밴픽 전략가다. 명장들의 밴 전략(페이즈별 목적 분리)을 따른다.\n"
    "지금 사용자의 **밴 차례**다. 구도를 읽고 **밴 5개**를 우선순위대로 추천하라.\n\n"
    "【명장의 밴 전략 — 페이즈로 목적이 다르다】\n"
    "★ 양팀 확정 픽이 0~2개(1페이즈 밴): 조합이 없으니 '사람'을 잘라라.\n"
    "  ① 상대 팀 장인 챔프(클랜 전적 판수·승률 높은 픽) 저격 ② 클랜이 실제로 밴해온 픽(견제 압력).\n"
    "  → 판수가 많고 승률도 높은 '밥줄 챔프'가 최우선 1순위. 솔랭 메타는 근거로 삼지 마라.\n"
    "★ 양팀 확정 픽이 3개 이상(2페이즈 밴): 이제 '조합'을 잘라라.\n"
    "  ③ 우리 확정 조합을 무너뜨리는 카운터 챔프 차단(우리 윈컨디션을 지키는 밴).\n"
    "  ④ 상대 조합의 마지막 퍼즐(빈 앞라인/이니시/AP딜을 완성해줄 픽) 차단.\n"
    "  ⑤ ★2페이즈 상대 픽 예측은 '무조건부 최다판'이 아니라 **조합 맥락 조건부**로 하라.\n"
    "     상대 확정 픽이 AD로 쏠렸으면, 남은 상대는 밸런스를 맞추러 **자기 챔프폭 안의 AP 픽**을 고를 확률이 높다\n"
    "     — 최다판 AD 챔프가 아니라 그 사람 챔프폭의 AP 대안이 진짜 나올 픽이니 그쪽을 밴 후보로 올려라.\n"
    "     (실측: 클랜 탑 유저가 팀 미드 AD일 때 AP 브루저 선택률 15%→25%로 상승, 주력 AD 브루저는 20%→8% 급감)\n"
    "     반대(AP 쏠림 → AD 대안 예측)도 동일. 챔프의 AD/AP는 네가 판단하라.\n"
    "  → 이 페이즈에 단순 OP 밴은 낭비다. 구도를 읽어라.\n"
    "보조 근거: 클랜 내전 승률이 비정상적으로 높은 챔프(표본 4판 이상만 신뢰).\n\n"
    "【★내전 특화 — 밴의 절반은 '사람'을 밴하는 것이다】\n"
    "- [상대 팀원들의 내전 챔프폭]이 주어지면 그것이 1페이즈 밴의 최우선 근거다. 판수 많고 승률 높은\n"
    "  '그 사람의 밥줄 챔프'를 자르면 상대는 숙련 없는 2번째 카드를 꺼내야 한다.\n"
    "- 단, 판수가 적은 고승률(3판 100% 등)은 우연이니 밴 근거로 쓰지 마라. 판수 5판 이상을 우선하라.\n"
    "- ★[2026-08-11 감사 반영] 챔프폭에 붙은 **'점유 P%'가 그 픽이 이번 판에 나올 확률**이다(그 자리에서 P판 중 몇 번 꺼냈나).\n"
    "  밴의 가치 = 등장 확률 × 위력. 실측하니 점유율 한 자릿수 픽 추천은 **96%가 그 판에 등장조차 안 했다** —\n"
    "  통산 승률이 아무리 높아도 점유율이 낮으면 밴 후보로 올리지 마라. 같은 값이면 점유율 높은 쪽을 먼저 자른다.\n"
    "  5개를 억지로 채우려 저확률 픽을 끼워 넣지 마라 — **확신 있는 3~4개**가 낭비 없는 밴이다.\n"
    "- ★선픽 위험군: 챔프폭에서 **판수 비중이 크고 승률도 높은** 챔프는 매치업을 안 가리고 꺼내는 '선픽 카드'다.\n"
    "  1페이즈 밴에서 같은 값이면 이쪽을 우선하라(어차피 나올 확률이 가장 높은 픽이 가장 값진 밴이다).\n"
    "- ★[이번 판 포지션]이 표기된 상대의 챔프폭은 **이미 그 포지션 전적만 걸러서** 실려 있다. 목록에 없는\n"
    "  챔프는 그 사람이 이번 판에 쓸 수 없다는 뜻이니, 기억이나 명성으로 다른 챔프를 끌어와 밴하지 마라.\n"
    "  '※ ○○ 전적 0판'이라고 적힌 상대는 저격 밴 대상이 아니다 — 그 사람에게 밴을 쓰지 마라.\n"
    "- 우리 팀원이 잘 쓰는 챔프를 밴하지 마라(자책 밴).\n"
    "- ⚔️[우리 팀이 실제로 약했던 상대 픽]이 주어지면, 그 픽은 '우리 팀원을 직접 무너뜨린 전적'이 있는 밴 후보다.\n"
    "  단 표본이 4~10판으로 작으니 단독 근거로 1순위에 올리지 말고, 상대가 실제로 뽑을 챔프일 때만 쓰라.\n"
    "  인용할 땐 '○○ 상대 7판 2승 29%'처럼 **판수를 반드시 함께** 말하라(승률만 말하면 과신하게 된다).\n"
    "- ★[견제 압력] 블록이 주어지면 그것이 챔프폭·승률보다 **더 강한 근거**다. 클랜원 수십 명이 수십 판을\n"
    "  겪고 '이 사람의 이 챔프는 막아야 한다'고 실제 행동으로 합의한 결과이기 때문이다. 1페이즈 밴에서\n"
    "  견제 압력 상위 챔프를 최우선으로 올리고, 이유에 '클랜이 실제로 밴해온 픽'임을 밝혀라.\n\n"
    "【절대 규칙】\n"
    "- 이미 밴되었거나 이미 픽된 챔피언은 추천 금지.\n"
    "- ★★**우리 팀(나·아군)이 쓸 챔피언을 밴 후보로 올리지 마라** — 밴은 오직 '상대가' 쓸 픽을 자르는 것이다.\n"
    "  우리 팀 관련 데이터에 나온 챔프를 밴하라는 건 아군 손해이자 명백한 오류다.\n"
    "- 실존하는 챔피언의 **정식 한글 이름만** 사용하라. 존재하지 않는 이름을 지어내면 절대 안 된다.\n"
    "- ★★**모든 추천 줄에는 클랜 데이터의 숫자를 하나 이상 붙여라**(판수·승률·밴 당한 횟수 등).\n"
    "  숫자를 붙일 수 없으면 그 줄 끝에 '(클랜 데이터 없음)'이라고 명시하라. 어느 쪽인지 읽는 사람이 알아야 한다.\n"
    "- ★★**솔랭 메타·티어리스트·패치 OP를 근거로 쓰지 마라.** 판단은 오직 클랜 내전 데이터로 한다.\n"
    "  '현 패치 OP', '고밴률', '메타 챔프' 같은 표현 자체를 쓰지 마라 — 클랜원 누구나 아는 일반론이라 값이 없다.\n"
    "- 상대 데이터가 없으면 그 사실을 밝히고 클랜 내전 통계만으로 추천하라 — 근거 없는 저격 밴을 지어내지 마라.\n"
    "- ★★장인 챔프 저격 밴은 **그 챔프의 전적 포지션과 그 선수의 이번 판 포지션이 맞을 때만** 가치가 있다.\n"
    "  [이번 판 포지션]이 붙은 상대는 데이터가 이미 그 자리 전적만 남겨 뒀다. 포지션 표기가 없는 상대만\n"
    "  챔프 옆 '·정글전적'(그 챔프를 실제로 쓴 라인) 표기를 보고 네가 직접 걸러라 — 조합상 다른 라인을\n"
    "  가는 게 명백하면 그 라인 전용 장인챔프(예: 정글 샤코)는 위협이 아니고, 그 밴은 낭비다.\n"
    "  ★유명한 원챔장인이라도 이번 판 자리가 다르면 그 챔프는 나오지 않는다. 이름값으로 밴하지 마라.\n"
    "- ★포지션을 지어내지 마라. 내전은 밴픽에 포지션 배정이 없어 '누가 어느 라인인지'는 대부분 미확정이다.\n"
    "  픽 옆에 '← 이름(주:라인)'이 있으면 그 사람이 고른 것이고, 그게 포지션 추정의 유일한 근거다.\n"
    "  '서폿 럭스', '탑 뽀삐' 같이 단정하지 말고, 필요하면 '미드 유저가 고른 럭스'처럼 근거를 밝혀 말하라.\n"
    "  근거가 없으면 포지션을 아예 언급하지 마라. 한 답변 안에서 같은 픽의 포지션을 다르게 말하면 절대 안 된다.\n\n"
    "【출력 형식 — 한국어·★최대한 짧게(오버레이 작은 창이라 시인성이 생명)】\n"
    "- 밴 개수는 사용자 메시지가 지정(1페이즈 3 / 2페이즈 2). '1. 챔프 — 이유(★20자 이내)' 우선순위대로.\n"
    "- [클랜 밴픽퀴즈 표]가 있으면 강한 참고 신호다 — 표가 많고 적중 이력이 있는 챔프는 우선순위를 올려라.\n"
    "  예: '1. 레넥톤 — 레멍이 43판·견제압력 1위' / '2. 세라핀 — 상대 포킹 완성 차단'. 이 밀도로.\n"
    "- 픽 방향/내 픽 설계를 요구받으면 밴 아래 '→'로 시작해 **픽당 한 줄**(챔프 — 20자 근거).\n"
    "- 서술형 문장·접속사·배경 설명 금지. 경고(⚠️)는 꼭 필요한 것 하나만 한 줄.\n"
    "- T0·T1 같은 티어 코드 표기 금지 — 필요하면 'OP픽'처럼 말로.\n"
    "- 사용자가 이미 아는 사실(어떤 챔프가 밴됐는지 등)을 요약에 재나열 금지 — 추천만 딱.\n"
    "- ★요약 뒤에 구분줄 '=====근거=====' 를 쓰고, 그 아래 판단 근거를 항목당 한 줄(총 6줄 이내).\n"
    "  왜 이 밴/픽인지의 핵심 논리·데이터. 사용자는 요약만 보다가 궁금하면 펼쳐 본다."
)

def _draft_advise(ctx, my_pool):
    """Claude 호출 → 추천 텍스트. 실패하면 None(무해하게 조용히 스킵).
       [v82.33] 호스트(claude_key.txt) = 로컬 직접 호출(무료·캐시). 구독자(구독 토큰) = 봇 프록시(사장님 키)."""
    key = load_claude_key()
    tok = _coach_token()
    if not key and not tok: return None
    is_ban = ctx.get("mode") == "ban"
    pool_txt = "\n".join(f"- {c}: {g}판 {round(w/g*100) if g else 0}%" for c, g, w in my_pool) or "(내전 기록 없음)"
    # [v81.77] 라인 매치업을 최상단에 명시 — '사일러스 상대 알리스타' 같은 상성 무시 방지의 핵심
    _lane = ctx.get("lane_enemy") or ""
    # [v82.34] 픽은 '누가 골랐는지'까지 붙여 제시 — 포지션 환각(예: 근거 없이 '서폿 럭스' 단정) 방지
    _ed = [x for x in (ctx.get("enemy_desc") or []) if x]
    _ad = [x for x in (ctx.get("ally_desc") or []) if x]
    _enemy_txt = ("\n" + "\n".join(f"  · {x}" for x in _ed)) if _ed else "아직 없음"
    _ally_txt = ("\n" + "\n".join(f"  · {x}" for x in _ad)) if _ad else "아직 없음"
    _n_e, _n_a = len(_ed), len(_ad) + 1   # 우리 팀은 나 포함
    _phase_txt = (f"\n[밴픽 진행도] 상대 확정 {_n_e}/5명 · 우리 확정 {_n_a}/5명"
                  + ("  ※ 아직 5명이 다 안 나왔다 — 어떤 픽의 포지션도 단정하지 마라."
                     if (_n_e < 5 or _n_a < 5) else ""))
    # 🧠 [v82.29] 내전 특화 블록 — 이 클랜에서만 참인 사실(일반 LoL 지식으로는 절대 알 수 없음)
    _ca = "\n".join(ctx.get("clan_ally") or [])
    _ce = "\n".join(ctx.get("clan_enemy") or [])
    _syn = "\n".join(ctx.get("syn") or [])
    _h2h = ctx.get("h2h") or ""
    clan_blk = ""
    if _ce: clan_blk += f"\n\n[★상대 팀원들의 내전 챔프폭 — 이들이 실제로 뽑을 확률이 높은 챔프]\n{_ce}"
    if _ca: clan_blk += f"\n\n[우리 팀원들의 내전 챔프폭 — 함께 굴러갈 조합 판단용]\n{_ca}"
    if _h2h: clan_blk += f"\n\n[내 라인 상대와의 통산 맞대결] {_h2h}"
    if _syn: clan_blk += f"\n\n[동료와의 통산 합(참고용·표본 작음)]\n{_syn}"
    # 🚫 [v82.44 사장님 제보] 밴 모드 전용 클랜 블록 — **아군 챔프폭 제외**.
    #   상대 식별이 안 된 판에서 아군 챔프폭이 유일한 데이터가 되면 모델이 '장인 저격'을
    #   아군 풀에 적용해 우리 픽(뽀삐·렐)을 밴하라고 하던 실사고(7/24 22:51) 차단.
    clan_blk_ban = ""
    if _ce: clan_blk_ban += f"\n\n[★상대 팀원들의 내전 챔프폭 — 이들이 실제로 뽑을 확률이 높은 챔프]\n{_ce}"
    # 🎯 [v82.32] 견제 압력 — 승률·판수가 못 잡는 신호. 클랜이 "그 사람이 있을 때만" 밴해온 픽 = 집단이 검증한 위협.
    _bp = ctx.get("bp") or []
    _bp_blk = ""
    if _bp:
        _bp_blk = ("\n\n[★★견제 압력 — 클랜이 실제로 밴해온 챔프(가장 강력한 근거)]\n"
                   + "\n".join(_bp)
                   + "\n※ +N%p = 그 선수가 있을 때 상대팀이 이 챔프를 밴하는 비율이 평소보다 N%p 높다는 뜻.\n"
                     "   클랜원들이 수십 판을 겪고 내린 집단 판단이라, 단순 승률·판수보다 신뢰도가 높다.\n"
                     "   여기 오른 챔프는 밴 우선순위 상단에 두고, 그 근거를 이유에 밝혀라.")
    # 🚫 [v82.41] 노밴 선언 — 로비 채팅에서 감지된 '밴 금지 약속' 챔피언
    _nb = ctx.get("noban") or []
    _nb_blk = ""
    if _nb:
        _nb_blk = ("\n\n[🚫 노밴 선언 — 로비에서 '1페이즈 밴 금지'로 약속된 챔피언(채팅 감지)]\n"
                   + "\n".join(f"- {c}" for c in _nb)
                   + "\n※ 클랜 규칙: **1페이즈에서는 이 챔피언을 절대 밴 추천에 넣지 마라.**\n"
                     "   단 **2페이즈에서는 밴해도 된다** — 상대 조합을 보고 이 챔피언이 위협적이면 2페이즈 밴 후보로 올려라.\n"
                     "   또한 선언했다고 반드시 플레이하는 건 아니다(안 하는 경우도 많음) — '픽 가능성이 높은 후보' 정도의\n"
                     "   참고 정보로만 쓰고, 조합 예측을 이 픽 하나에 걸지 마라.")
    # 🎯 [v82.40] 선픽 안전 블록 — 상대 무관 안정성(A) + 이 상대 특정(B)
    _sg = ctx.get("safe_gen") or ""
    _so = ctx.get("safe_opp") or ""
    _safe_blk = ""
    if _sg or _so:
        _safe_blk = "\n\n[🎯 내 챔프 숙련도 — '이 사람이 이 챔프로 실제로 잘했는가'(카운터당한 판 유무)]"
        if _sg: _safe_blk += ("\n(A) 여러 상대를 겪고도 유독 진 매치업이 없던 내 챔프\n" + _sg)
        if _so: _safe_blk += ("\n(B) 이번 상대가 뽑을 법한 챔프 상대 내 실적\n" + _so)
        _safe_blk += ("\n※★이 데이터는 '숙련도'일 뿐 '선픽 안전'이 아니다(우리 내전이 정밀 카운터를 잘 안 가서 안 진 것일 수 있음).\n"
                      "   **선픽 가능 여부는 그 챔프의 라인전 특성으로 네가 판단하라** — 기준: ①붙으면 즉사하는 근접 이니시라\n"
                      "   상대가 원거리로 맞추면 무력한가 ②라인전에서 하드 카운터가 명확한가. 그런 챔프만 후픽으로 돌리고,\n"
                      "   **사거리·기동성·안전한 파밍으로 라인전이 안정적인 챔프는 숙련만 높으면 선픽으로 무방하다.**\n"
                      "   특정 챔프 이름으로 미리 단정하지 말고, 실제 라인전 성립 여부로 판단하라. 판수는 함께 말하라.\n"
                      "   ★각 챔프의 [라인 N판] 표기는 그 숙련이 쌓인 포지션이다. 지금 내 포지션과 다른 라인의 숙련이면\n"
                      "   (⚠️ 표시) 그 라인 숙련을 지금 라인에 그대로 신뢰하지 마라 — 같은 라인 기록이 있는 픽을 우선하라.")
    # 📊 [v82.40] 저티어 오프롤 성과픽(P4 실측 근거) — 내가 2·3티어일 때만 주입(그 외엔 무관한 정보)
    _loff_blk = ""
    _mt3 = str(ctx.get("my_tier") or "")
    if _mt3[:1] in ("2", "3"):
        _lg = ctx.get("loff_good") or ""; _lb = ctx.get("loff_bad") or ""
        if _lg or _lb:
            _loff_blk = "\n\n[📊 클랜 실측 — 저티어가 오프롤로도 성과 낸 픽(P4 근거·반분검증 통과분)]"
            if _lg: _loff_blk += "\n성과: " + _lg
            if _lb: _loff_blk += "\n함정: " + _lb
            _loff_blk += "\n※ 내가 저티어로 오프롤/애매한 배정일 때 참고 가중. 표본 8~30판이라 단독 근거 금지."
    # ⚔️ [v82.35] 라인 매치업 실적 — 표본이 작으니 '동점일 때 가르는 근거'로만 쓰라고 못박는다.
    _mu = ctx.get("mu") or []
    _wk = ctx.get("weak") or []
    _mu_blk = ""
    if _mu:
        _mu_blk = ("\n\n[⚔️ 내 챔프폭 × 이 라인 상대 — 클랜 내전 실적]\n" + "\n".join(_mu)
                   + "\n※ 표본이 4~10판 수준이라 오차가 크다. 상성·조합 판단이 비슷할 때 가르는 용도로만 쓰고,\n"
                     "   이 숫자만으로 조합이 어긋나는 픽을 밀지 마라. 인용할 땐 반드시 판수를 함께 말하라.\n"
                     "※★이 승률은 '라인전 승리'가 아니라 '그 판 팀의 승패'다. 실측상 팀 평균 티어차가 1티어면\n"
                     "   승률이 35%↔65%로 갈리는 반면, 라인 상대의 티어차 2단계는 겨우 5%p만 움직인다.\n"
                     "   즉 낮은 승률의 상당 부분은 '그날 팀 전력'이지 이 매치업 자체가 아니다. 과대해석 금지.")
    _wk_blk = ""
    if _wk:
        _wk_blk = ("\n\n[⚔️ 우리 팀이 실제로 약했던 상대 픽 — 유력 밴 후보]\n" + "\n".join(_wk)
                   + "\n※ 우리 팀원이 이 상대 픽을 만나면 실제로 성적이 나빴다는 뜻. 표본이 작으니(4~10판)\n"
                     "   단독 근거로 쓰지 말고, 상대가 실제로 뽑을 만한 픽일 때만 밴 후보로 올려라. 판수를 함께 말하라.\n"
                     "※★이 승률도 '팀의 승패'다. 그날 팀 전력이 불리해서 진 판이 섞여 있으니, 낮은 승률을\n"
                     "   '이 챔프에게 카운터당한다'는 증거로 단정하지 마라. 상성이 실제로 성립할 때만 근거로 써라.")
    if is_ban:
        # 밴 모드 [v82.39 설계B]: '내 밴'이 아니라 '우리 팀이 밴할 것'을 페이즈별로 통째 추천(5명이 상의해 밴).
        _bphase = int(ctx.get("ban_phase") or 1)
        _opp = ctx.get("enemy_pools") or []
        if not any(champs for _n, champs in _opp):     # [2026-07-29] 왜 '상대 전적 없음'이 됐는지 로그로 구분
            print(f"[ghost] 상대 전적 없음으로 추천 — 상대 {len(_opp)}명 인식, 내전 기록 붙은 인원 0", flush=True)
        opp_txt = "\n".join(
            f"- {nm or '상대'}: " + ", ".join(champs)   # [v82.45] champs = 포지션 병기된 문자열 목록
            for nm, champs in _opp if champs) or ("(상대 전적 정보 없음 — ★저격 밴이 불가능하다.\n"
                                                  " 이 경우 [클랜 내전 챔피언 메타]와 우리 팀 데이터만으로 추천하고,\n"
                                                  " 맨 앞줄에 '상대 데이터 없음 — 클랜 내전 통계만으로 판단'이라고 반드시 밝혀라.\n"
                                                  " 솔랭 메타·티어리스트를 근거로 지어내지 마라)")
        # 🗳️ 클랜 집단 판단 — 밴픽 퀴즈에서 실제로 적어낸 표(상대 선수별 상위 3)
        _qp = _quiz_pref()
        _qp_lines = []
        if _qp:
            for _nm in (ctx.get("enemy_names") or []):
                _hit = _qp.get(_nm) or _qp.get(str(_nm).split("#")[0])
                if not _hit: continue
                _qp_lines.append(f"- {_nm}: " + ", ".join(f"{c} {v}표(적중 {h})" for c, v, h in _hit[:3]))
        if _qp_lines:
            opp_txt += ("\n\n[🗳️ 클랜 집단 판단 — 밴픽 퀴즈 표(클랜원이 직접 적어낸 밴 후보)]\n"
                        + "\n".join(_qp_lines)
                        + "\n★이건 클랜원 여러 명이 같은 상대를 두고 '무엇을 자를까'를 직접 적어낸 결과다.\n"
                          "  동급 후보면 표가 많은 쪽을 우선하고, 이유에 '클랜 다수 의견(N표)'임을 밝혀라.\n"
                          "  단 표가 3표 미만이면 참고만 하라. 적중 수는 그 답이 실제로 상대가 꺼낸 픽이었던 횟수다.")
        _ef = ctx.get("enemy_filled_pos") or []
        _eo = ctx.get("enemy_open_pos") or []
        if _ef:
            opp_txt += ("\n\n[상대 자리 현황] 이미 채워짐: " + ", ".join(_ef)
                        + " / 아직 빈 자리: " + (", ".join(_eo) if _eo else "없음")
                        + "\n★★밴 후보는 **빈 자리에 나올 픽**만 올려라. 이미 채워진 자리(예: 상대 서폿 확정)의\n"
                          "  챔프를 밴하는 것은 아무것도 막지 못하는 낭비다 — 절대 추천하지 마라.\n"
                          "★그 자리에 누가 갈지는 [상대 팀원들의 내전 챔프폭]의 '[이번 판 포지션]' 표기로 확정하라.\n"
                          "  포지션이 남은 사람의, 그 포지션 전적이 있는 챔프만 저격 대상이다.\n"
                          "★이미 챔피언을 확정한 상대 선수는 [상대 팀원들의 내전 챔프폭]에서 아예 빠져 있다.\n"
                          "  거기 없는 사람의 장인챔을 기억으로 되살려 밴 후보에 올리지 마라 — 그 사람은 이미 픽이 끝났다.")
        if _bphase == 1:
            _task = ("★**1페이즈 밴**. ① 우리 팀 밴 **3개** 우선순위로(챔피언 자체가 위험한 것: 현 패치 OP·상대\n"
                     "장인·견제압력). ② 픽 방향 **딱 한 줄**(단정 금지). 전체 출력 극도로 짧게 — 근거는 판수%·핵심 단어만.")
        else:
            _picked = ctx.get("already_picked")
            _task = ("★**2페이즈 밴**. ① 우리 팀 밴 **2개** 우선순위로(우리 윈컨을 깨는 카운터·상대 조합 마지막 퍼즐).\n"
                     + ("② 나는 이미 픽함 — 밴만."
                        if _picked else
                        "② 나는 후픽 — 이 밴과 동시에 내 픽 후보 **1~2개, 각 한 줄**(챔프 — 20자 근거).")
                     + " 전체 출력 극도로 짧게.")
        user_txt = (
            f"{_task}\n\n"
            f"[내 포지션] {ctx['pos']}\n"
            f"[우리 팀 확정 픽] {_ally_txt}\n"
            f"[상대 팀 확정 픽] {_enemy_txt}\n"
            f"[이미 밴된 챔피언] {', '.join(ctx['bans']) or '없음'}"
            f"{_phase_txt}\n"
            + (f"\n[내가 다뤄본 챔피언(내전 기록)]\n{pool_txt}\n" + _safe_blk + "\n" if _bphase == 2 and not ctx.get('already_picked') else "")
            + f"\n[상대 팀 선수들이 잘 다루는 챔피언(클랜 내전 전적)]\n{opp_txt}"
            + _nb_blk
            + _bp_blk
            + _wk_blk
            + clan_blk_ban   # [v82.44] 밴 모드엔 아군 챔프폭 미주입(아군 픽 밴 추천 사고 방지)
            + ((chr(10) + chr(10) + "[클랜 밴픽퀴즈 표 — 클랜원들이 '이 상대에게 밴할 챔프'로 투표한 집단 학습]" + chr(10)
                + chr(10).join(ctx.get("quiz") or [])) if ctx.get("quiz") else "")
        )
    else:
        _mt2 = ctx.get("my_tier")
        user_txt = (
            f"[내 포지션] {ctx['pos']}" + (f" · 내 내부티어 {_mt2}티어(0=최상위)" if _mt2 not in (None, "") else "") + "\n"
            f"[★내 라인 상대] {_lane or '아직 확정 안 됨'}\n"
            f"[우리 팀 확정 픽] {_ally_txt}\n"
            f"[상대 팀 확정 픽] {_enemy_txt}\n"
            f"[이미 밴된 챔피언] {', '.join(ctx['bans']) or '없음'}"
            f"{_phase_txt}\n\n"
            f"[내가 다뤄본 챔피언(내전 기록)]\n{pool_txt}"
            + _nb_blk
            + _safe_blk
            + _loff_blk
            + _mu_blk
            + clan_blk
        )
    # 시스템 프롬프트(코칭 규칙 + 현 패치 메타 + 클랜 메타) — 호스트·구독자 공통
    # [2026-07-29 사장님 지시] 솔랭 티어리스트(메타 챔프) 주입 제거 — 판단 근거를 클랜 데이터로만 좁힌다.
    #   일반론은 클랜원 누구나 아는 얘기라 조언의 값이 없었고, 근거 없는 단정의 출처이기도 했다.
    system_text = ((_DRAFT_BAN_RULES if is_ban else _DRAFT_RULES)
                   + "\n\n[클랜 내전 챔피언 메타(판수순)]\n" + _clan_meta_lines())
    # 🌐 [v82.33] 구독자(로컬 키 없음) → 봇 프록시로 호출(사장님 키는 서버에만, 유출 방지)
    if not key:
        return _draft_advise_via_proxy(tok, system_text, user_txt, ctx.get("me"))
    # 🏠 호스트(claude_key.txt) → 로컬 직접 호출(무료·프롬프트 캐시)
    try:
        import anthropic
    except Exception:
        print("[draft] anthropic 패키지 없음 — 고스트밴픽왕 비활성", flush=True)
        return "⚠️ 고스트밴픽왕: 프로그램 구성요소 누락(재설치 필요)"
    try:
        cl = anthropic.Anthropic(api_key=key, timeout=14.0, max_retries=1)
        # ⚡ [2026-08-12 사장님 제보 '추천 뜨는 게 너무 느리다'] 스트리밍으로 바꾼다.
        #   예전엔 550토큰을 다 만든 뒤에야 화면에 떴다. 출력의 뒷부분은 접혀 있는 '근거' 6줄이라
        #   정작 급한 요약 3줄까지 그것을 기다렸다. 이제 도착하는 대로 뿌리고, 요약이 끝나는
        #   구분줄(=====근거=====)이 오면 그 시점에 이미 볼 것은 다 보인다.
        _hdr = ("🚫 %s페이즈 밴 추천" % ctx.get("ban_phase") if is_ban else "🧠 AI 픽 추천")
        buf = []
        with cl.messages.stream(
                model=DRAFT_MODEL,
                max_tokens=550,   # [v82.40] 요약(짧게) + 접힌 근거 6줄 — 시인성과 신뢰도 동시 확보
                thinking={"type": "disabled"},          # 밴픽 30초 제한 → 저지연 최우선
                output_config={"effort": "medium"},     # [v81.77] 상성 판단 품질 ↑ (low는 매치업을 대충 봄)
                system=[{"type": "text", "text": system_text,
                         "cache_control": {"type": "ephemeral"}}],   # 고정 파트 → 캐시(2회차부터 1/10 가격)
                messages=[{"role": "user", "content": user_txt}],
        ) as st:
            _last = 0.0
            for piece in st.text_stream:
                buf.append(piece)
                _now = time.time()
                if _now - _last < 0.12: continue     # 매 토큰마다 다시 그리면 GUI 가 버벅인다
                _last = _now
                _partial = "".join(buf)
                _sum = _partial.split(_REASON_SEP)[0].rstrip()
                if not _sum: continue
                with gui_lock:
                    gui_data["draft_advice"] = f"{_hdr}\n{_sum}"
                    gui_data["draft_advice_ts"] = time.time()
            resp = st.get_final_message()
        if getattr(resp, "stop_reason", "") == "refusal": return None
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        try:
            u = resp.usage
            print(f"[draft] 추천 완료 (in={u.input_tokens} cache_read={getattr(u,'cache_read_input_tokens',0)} out={u.output_tokens})", flush=True)
        except Exception: pass
        return txt or None
    except Exception as e:
        # [v81.75] 조용한 실패 금지 — 원인을 오버레이에 그대로 띄워 사장님이 바로 진단하게
        _m = str(e); _t = type(e).__name__
        print(f"[draft] 호출 실패: {_t} {_m[:200]}", flush=True)
        if "authentication" in _m.lower() or "401" in _m or "invalid x-api-key" in _m.lower():
            return "⚠️ 고스트밴픽왕: API 키가 잘못됐어요\n(키를 다시 발급받아 claude_key.txt에 붙여넣어 주세요)"
        if "credit" in _m.lower() or "billing" in _m.lower() or "quota" in _m.lower():
            return "⚠️ 고스트밴픽왕: 크레딧이 부족해요\n(console.anthropic.com → Billing에서 충전해 주세요)"
        if "timeout" in _m.lower() or "timed out" in _m.lower():
            return "⚠️ 고스트밴픽왕: 응답이 늦어 이번 픽은 건너뛰었어요"
        return f"⚠️ 고스트밴픽왕 오류: {_t}\n{_m[:120]}"

_COACH_PROXY_URL = "https://hth3thmujs.apps.bot-hosting.cloud/draft-coach"   # 봇 프록시(INVITE_BRIDGE와 동일 노드)
def _coach_token():
    """구독자 토큰 — config.json에 저장(설정 UI에서 입력). 없으면 None."""
    try:
        t = str(APP_CONFIG.get("coach_token", "") or "").strip()
        return t or None
    except Exception:
        return None

def _draft_advise_via_proxy(token, system_text, user_txt, who=""):
    """구독자용 — 봇 프록시에 밴픽 컨텍스트 전송(사장님 키로 대신 호출). 키는 이 PC에 절대 안 옴.
       who = 내 라이엇 계정 식별자 → 서버가 토큰-계정 결속(토큰 공유 차단)에 사용."""
    try:
        r = requests.post(_COACH_PROXY_URL, json={
            "token": token, "model": DRAFT_MODEL, "max_tokens": 550,
            "who": str(who or ""), "system": system_text, "user": user_txt}, timeout=20)
        j = r.json() if r.content else {}
        if j.get("text"): return str(j["text"]).strip() or None
        code = str(j.get("code") or "")
        if code == "empty":   # [2026-07-31] 서버가 빈 응답을 받은 경우 — 재시도하면 대개 나온다
            return "⚠️ 고스트밴픽왕: 잠시 후 다시 시도해 주세요"
        if code == "quota":   # [v82.34] 사용량 한도 — 서버가 보낸 안내를 그대로 표시
            return "⏳ 고스트밴픽왕\n" + str(j.get("error") or "사용량 한도에 도달했어요")
        if code == "shared":  # [v82.34] 토큰이 다른 계정에서 사용 중
            return "🔐 고스트밴픽왕\n" + str(j.get("error") or "이 토큰은 다른 계정에서 쓰이고 있어요")
        if code in ("no_token", "expired"):
            return "⚠️ 고스트밴픽왕 구독이 만료됐거나 토큰이 올바르지 않아요\n디스코드에서 /구독 으로 확인해 주세요"
        if code == "no_key":
            return "⚠️ 고스트밴픽왕: 서버 설정이 아직 안 됐어요(맛장유 문의)"
        return "⚠️ 고스트밴픽왕: 잠시 후 다시 시도해 주세요"
    except Exception as e:
        print(f"[draft] 프록시 호출 실패: {e}", flush=True)
        return "⚠️ 고스트밴픽왕: 서버 연결 실패(인터넷 확인)"

_BANS_SHOWN = [None]   # 🚫 [v81.77] 10밴 아이콘 재렌더 캐시(매초 이미지 재생성 방지)
_DRAFT_OVL = {"win": None, "lbl": None, "shown": "", "expanded": False, "btn_more": None, "dock_rect": None}

def _lol_client_rect():
    """🧲 롤 클라이언트(LeagueClientUx, 클래스 RCLIENT) 창 좌표. 없거나 최소화면 None."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        hwnd = u.FindWindowW("RCLIENT", None) or u.FindWindowW(None, "League of Legends")
        if not hwnd or not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd): return None
        r = wintypes.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(r)): return None
        if (r.right - r.left) < 400 or (r.bottom - r.top) < 300: return None
        return (int(r.left), int(r.top), int(r.right), int(r.bottom))
    except Exception:
        return None

def _dock_overlay(w):
    """🧲 [2026-07-25 사장님 지시] 오버레이를 롤 클라 우측에 자석처럼 부착.
       클라가 움직였을 때만 재배치(그 외엔 사용자가 끌어놓은 위치 존중). 클라 못 찾으면 화면 우측 기본 위치."""
    try:
        rect = _lol_client_rect()
        if rect is None:
            if _DRAFT_OVL.get("dock_rect") is None:   # 최초 1회만 기본 위치
                _DRAFT_OVL["dock_rect"] = "fallback"
                w.geometry("+%d+%d" % (max(0, w.winfo_screenwidth() - (DRAFT_OVL_WRAP + 70)), 90))
            return
        if rect == _DRAFT_OVL.get("dock_rect"): return   # 클라 안 움직임 → 그대로
        _DRAFT_OVL["dock_rect"] = rect
        sw = w.winfo_screenwidth()
        x = rect[2] + 6                                   # 클라 오른쪽 모서리 +6px
        _ow = DRAFT_OVL_WRAP + 60                         # 창이 커졌으니 폭도 같이 계산(안 그러면 화면 밖으로 나간다)
        if x + _ow > sw: x = max(0, sw - _ow - 5)         # 화면 밖이면 우측 끝에 겹쳐 부착
        y = max(0, rect[1] + 60)
        w.geometry("+%d+%d" % (x, y))
    except Exception: pass
DRAWER_ALPHA = 0.93      # ☰ 서랍 불투명도 — 낮을수록 뒤가 잘 비친다 (0.75 는 사장님이 별로라 하여 롤백)
# 💝 후원 계좌 — squad.gg 고스트밴픽왕 소개 페이지(coach.html)에 이미 공개된 것과 같은 계좌.
#   바뀌면 여기 세 줄만 고치면 된다(설정 파일로 덮어쓸 수도 있게 load_config 값을 우선한다).
DONATE_BANK, DONATE_ACCT, DONATE_NAME = "토스뱅크", "1000-2535-5662", "박상준"
# 🔆 오버레이 시인성 — 테두리 두께·색, 글자 줄바꿈 폭
DRAFT_OVL_BORDER = 3
DRAFT_OVL_EDGE = "#f5d47a"       # 평소 테두리(금색)
DRAFT_OVL_FLASH = "#ff5a5a"      # 새 추천이 뜰 때 깜빡이는 색
DRAFT_OVL_WRAP = 520             # 380 → 520 (글자도 11 → 14pt)

_REASON_SEP = "=====근거====="   # [v82.40] AI 출력의 요약/근거 구분자 — 기본은 요약만 표시, 버튼으로 근거 펼침

def _split_reason(txt):
    """AI 출력 → (요약, 근거). 구분자 없으면 전부 요약."""
    t = str(txt or "")
    if _REASON_SEP in t:
        a, b = t.split(_REASON_SEP, 1)
        return a.strip(), b.strip()
    return t.strip(), ""

def _draft_overlay_sync(root):
    """gui_data['draft_advice']를 항상-위 카드 오버레이에 반영. 추천 없으면 숨김. (GUI 스레드 전용)

    🎨 [2026-08-12 사장님 지시 '상업 프로그램급으로'] 회색 상자에 글자를 통째로 붓던 것을
       카드 UI 로 다시 만들었다. 구조를 살려서 그리면 같은 내용도 훨씬 빨리 읽힌다.
         · 프레임리스 + 둥근 모서리(투명색 트릭) · 모드별 강조색(밴=적, 픽=청)
         · 추천 줄을 파싱해 [순위 배지][챔피언 굵게][근거 흐리게] 3단으로 분리
         · 픽 방향(→)은 강조 박스, 경고(⚠️)는 호박색 줄로 따로
         · 제목줄을 잡고 끌어 옮길 수 있음(프레임리스라 OS 타이틀바가 없다)
    """
    with gui_lock:
        txt = str(gui_data.get("draft_advice", "") or "")
        ts = float(gui_data.get("draft_advice_ts", 0) or 0)
    if txt and ts and time.time() - ts > 90:   # 90초 지나면 자동 소멸(다음 밴픽 대비)
        txt = ""
        with gui_lock: gui_data["draft_advice"] = ""
    w = _DRAFT_OVL["win"]
    if not txt:
        if w is not None:
            try: w.withdraw()
            except Exception: pass
        _DRAFT_OVL["shown"] = ""
        return
    if w is None or not w.winfo_exists():
        _draft_build_card(root)
        w = _DRAFT_OVL["win"]
        try: _dock_overlay(w)
        except Exception: pass
    if _DRAFT_OVL["shown"] != txt:
        try:
            # ⚡ 스트리밍 중에는 같은 추천의 글자가 늘어나는 것뿐이다. 그때마다 창을 다시 끌어올리면
            #    초당 여러 번 깜빡이며 인게임 포커스를 흔든다 — 첫 줄(제목)이 바뀔 때만 '새 추천'으로 본다.
            _key = str(txt).split("\n", 1)[0]
            _fresh = (_key != _DRAFT_OVL.get("hdr"))
            _DRAFT_OVL["shown"] = txt
            if _fresh:
                _DRAFT_OVL["hdr"] = _key
                _DRAFT_OVL["expanded"] = False   # 새 추천은 항상 요약부터
            _DRAFT_OVL["_render"]()
            if _fresh:
                w.deiconify(); w.attributes("-topmost", True); w.lift()
                _draft_flash(w)                  # 🔆 강조색 링으로 시선 유도
        except Exception: pass
    try: _dock_overlay(w)   # 🧲 클라가 움직였으면 따라붙기(표시 중일 때만)
    except Exception: pass


# 🎨 카드 팔레트 — 다크 글래스 + 모드별 강조색
_OVC = {"magic": "#010203",        # 투명 처리용(둥근 모서리 바깥)
        "card": "#0e1016", "surface": "#171b23", "line": "#252b36",
        "text": "#eef2f8", "sub": "#8d9aae", "dim": "#6b7789",
        "ban": "#ff5f6d", "pick": "#5aa2ff", "gold": "#f5d47a", "warn": "#ffb347"}

def _rrect(cv, x1, y1, x2, y2, r, **kw):
    """캔버스 둥근 사각형 — Tk 에 기본 도형이 없어 직접 그린다."""
    pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2,
           x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
    return cv.create_polygon(pts, smooth=True, splinesteps=24, **kw)

_DRAFT_LINE_RE = re.compile(r"^\s*(\d+)\s*[.)]\s*(.+?)\s*(?:[—–]|(?<=\s)-)\s*(.*)$")

def _draft_build_card(root):
    """카드 창을 만든다. 내용은 _render() 가 채운다."""
    C = _OVC
    w = tk.Toplevel(root)
    w.title("고스트밴픽왕")
    w.overrideredirect(True)                     # 프레임리스 — OS 타이틀바 제거
    w.attributes("-topmost", True)
    rounded = True
    try:
        w.configure(bg=C["magic"]); w.attributes("-transparentcolor", C["magic"])
    except Exception:
        rounded = False; w.configure(bg=C["card"])
    try: w.attributes("-alpha", 0.98)
    except Exception: pass

    cv = tk.Canvas(w, bg=(C["magic"] if rounded else C["card"]), highlightthickness=0, bd=0)
    cv.pack(fill="both", expand=True)
    body = tk.Frame(cv, bg=C["card"])
    win_id = cv.create_window(10, 8, window=body, anchor="nw")

    # ── 헤더 ──
    hd = tk.Frame(body, bg=C["card"]); hd.pack(fill="x", padx=16, pady=(13, 0))
    badge = tk.Label(hd, text=" 밴 ", bg=C["ban"], fg="#12141a",
                     font=UF(10, "bold"), padx=7, pady=2)
    badge.pack(side="left")
    tk.Label(hd, text="고스트밴픽왕", bg=C["card"], fg=C["text"],
             font=UF(13, "bold")).pack(side="left", padx=(9, 0))
    sub = tk.Label(hd, text="", bg=C["card"], fg=C["dim"], font=UF(9))
    sub.pack(side="left", padx=(8, 0))
    close = tk.Label(hd, text="✕", bg=C["card"], fg=C["dim"], font=UF(12), cursor="hand2")
    close.pack(side="right")
    close.bind("<Button-1>", lambda e: (_DRAFT_OVL.update({"shown": "", "hdr": None}), w.withdraw()))
    close.bind("<Enter>", lambda e: close.config(fg=C["ban"]))
    close.bind("<Leave>", lambda e: close.config(fg=C["dim"]))

    rule = tk.Frame(body, bg=C["ban"], height=2)
    rule.pack(fill="x", padx=16, pady=(9, 0))

    rows = tk.Frame(body, bg=C["card"]); rows.pack(fill="x", padx=16, pady=(10, 0))

    # ── 푸터 ──
    ft = tk.Frame(body, bg=C["card"]); ft.pack(fill="x", padx=16, pady=(10, 13))
    more = tk.Label(ft, text="근거 보기 ▼", bg=C["surface"], fg=C["sub"],
                    font=UF(10), padx=11, pady=4, cursor="hand2")
    more.pack(side="left")
    more.bind("<Enter>", lambda e: more.config(fg=C["text"]))
    more.bind("<Leave>", lambda e: more.config(fg=C["sub"]))
    tk.Label(ft, text="⠿ 끌어서 이동", bg=C["card"], fg=C["dim"],
             font=UF(9)).pack(side="right")

    # ── 제목줄을 잡고 창 이동(프레임리스라 OS 가 안 해준다) ──
    drag = {"x": 0, "y": 0}
    def _dn(e): drag["x"], drag["y"] = e.x_root, e.y_root
    def _mv(e):
        try:
            w.geometry("+%d+%d" % (w.winfo_x() + e.x_root - drag["x"], w.winfo_y() + e.y_root - drag["y"]))
            drag["x"], drag["y"] = e.x_root, e.y_root
            _DRAFT_OVL["dock_rect"] = "manual"      # 손으로 옮겼으면 자동 도킹이 되돌리지 않게
        except Exception: pass
    for _wg in (hd, body, rows):
        _wg.bind("<Button-1>", _dn); _wg.bind("<B1-Motion>", _mv)

    def _row(parent, kind, a, b=""):
        """추천 한 줄 — kind: num(순위) / ctx(대치·윈컨) / dir(픽 방향) / warn(경고) / plain"""
        f = tk.Frame(parent, bg=C["card"]); f.pack(fill="x", pady=2)
        if kind == "num":
            tk.Label(f, text=a, bg=_DRAFT_OVL["accent"], fg="#12141a", width=2,
                     font=UF(10, "bold")).pack(side="left", pady=1)
            tx = tk.Frame(f, bg=C["card"]); tx.pack(side="left", fill="x", expand=True, padx=(9, 0))
            tk.Label(tx, text=b[0], bg=C["card"], fg=C["text"], anchor="w",
                     font=UF(14, "bold")).pack(anchor="w")
            if b[1]:
                tk.Label(tx, text=b[1], bg=C["card"], fg=C["sub"], anchor="w", justify="left",
                         wraplength=DRAFT_OVL_WRAP - 40, font=UF(10)).pack(anchor="w")
        elif kind == "dir":
            box = tk.Frame(f, bg=C["surface"]); box.pack(fill="x")
            tk.Frame(box, bg=_DRAFT_OVL["accent"], width=3).pack(side="left", fill="y")
            tk.Label(box, text=a, bg=C["surface"], fg=C["text"], anchor="w", justify="left",
                     wraplength=DRAFT_OVL_WRAP - 30, font=UF(12, "bold"),
                     padx=10, pady=7).pack(side="left", fill="x", expand=True)
        elif kind == "warn":
            tk.Label(f, text=a, bg=C["card"], fg=C["warn"], anchor="w", justify="left",
                     wraplength=DRAFT_OVL_WRAP, font=UF(11)).pack(anchor="w")
        elif kind == "ctx":
            tk.Label(f, text=a, bg=C["surface"], fg=C["sub"], anchor="w", justify="left",
                     wraplength=DRAFT_OVL_WRAP - 20, font=UF(11),
                     padx=9, pady=5).pack(anchor="w", fill="x")
        else:
            tk.Label(f, text=a, bg=C["card"], fg=C["text"], anchor="w", justify="left",
                     wraplength=DRAFT_OVL_WRAP, font=UF(12)).pack(anchor="w")

    def _render():
        try:
            raw = str(_DRAFT_OVL.get("shown") or "")
            lines = raw.split("\n")
            head = lines[0] if lines else ""
            is_ban = "밴" in head
            _DRAFT_OVL["accent"] = C["ban"] if is_ban else C["pick"]
            badge.config(text=(" 밴 " if is_ban else " 픽 "), bg=_DRAFT_OVL["accent"])
            rule.config(bg=_DRAFT_OVL["accent"])
            sub.config(text=head.replace("🚫", "").replace("🧠", "").strip())
            summ, reason = _split_reason("\n".join(lines[1:]))
            for ch in rows.winfo_children(): ch.destroy()
            for ln in [x for x in summ.split("\n") if x.strip()]:
                t = ln.strip()
                m = _DRAFT_LINE_RE.match(t)
                if m: _row(rows, "num", m.group(1), (m.group(2).replace("*", "").strip(), m.group(3).strip()))
                elif t.startswith("→"): _row(rows, "dir", t.lstrip("→ ").strip())
                elif t.startswith("⚠"): _row(rows, "warn", t)
                elif t.startswith(("🆚", "🎯")): _row(rows, "ctx", t)
                else: _row(rows, "plain", t)
            if reason and _DRAFT_OVL.get("expanded"):
                tk.Frame(rows, bg=C["line"], height=1).pack(fill="x", pady=(9, 6))
                tk.Label(rows, text="📎 판단 근거", bg=C["card"], fg=C["dim"],
                         font=UF(9, "bold")).pack(anchor="w")
                tk.Label(rows, text=reason.strip(), bg=C["card"], fg=C["sub"], anchor="w", justify="left",
                         wraplength=DRAFT_OVL_WRAP, font=UF(10)).pack(anchor="w", pady=(2, 0))
            if reason:
                more.config(text=("근거 접기 ▲" if _DRAFT_OVL.get("expanded") else "근거 보기 ▼"))
                more.pack(side="left")
            else:
                more.pack_forget()
            _draft_fit()
        except Exception as e:
            print(f"[draft] 오버레이 렌더 실패: {type(e).__name__} {e}", flush=True)

    def _draft_fit():
        """내용 크기에 맞춰 창·배경을 다시 그린다(그림자 여백 포함)."""
        body.update_idletasks()
        bw, bh = body.winfo_reqwidth(), body.winfo_reqheight()
        # 폭을 내용에 맡기면 스트리밍 중 글자가 늘 때마다 창이 좌우로 출렁인다 — 최소폭으로 고정한다.
        bw = max(bw, DRAFT_OVL_WRAP - 40)
        W, H = bw + 20, bh + 18
        w.geometry("%dx%d" % (W, H))
        cv.configure(width=W, height=H)
        cv.coords(win_id, 10, 8)
        cv.delete("bgart")
        _rrect(cv, 4, 4, W - 4, H - 4, 16, fill="#05070b", outline="", tags="bgart")      # 그림자
        _rrect(cv, 2, 2, W - 6, H - 6, 16, fill=C["card"],
               outline=_DRAFT_OVL.get("ring") or _DRAFT_OVL.get("accent") or C["gold"],
               width=2, tags="bgart")
        cv.tag_lower("bgart")
    _DRAFT_OVL["_fit"] = _draft_fit

    def _toggle(_e=None):
        _DRAFT_OVL["expanded"] = not _DRAFT_OVL.get("expanded"); _render()
    more.bind("<Button-1>", _toggle)

    _DRAFT_OVL.update({"win": w, "lbl": None, "btn_more": more, "_render": _render,
                       "accent": C["ban"], "ring": None, "cv": cv})


def _draft_flash(w, n=6):
    """새 추천이 떴을 때 카드 테두리를 몇 번 깜빡인다. 소리는 내지 않는다(인게임 방해)."""
    def _step(i):
        try:
            if not w.winfo_exists(): return
            _DRAFT_OVL["ring"] = "#ffffff" if i % 2 == 0 else None
            fit = _DRAFT_OVL.get("_fit")
            if fit: fit()
            if i < n: w.after(130, _step, i + 1)
            else:
                _DRAFT_OVL["ring"] = None
                if fit: fit()
        except Exception: pass
    try: _step(0)
    except Exception: pass


# ===== 📊 [v82.34] 추천 적중 기록 — '추천대로 했을 때 실제로 이겼는가'를 나중에 검증하기 위한 원자료 =====
#   설계: 추천이 뜨면 추천 챔프 목록을 보관 → 내가 실제로 밴/픽을 확정하는 순간 대조 → 봇에 1건 전송.
#   게임ID는 밴픽 중엔 모르므로 나중에 시트(CLASSIC_NORMAL)와 시각·닉으로 조인해 승패를 붙인다.
#   ⚠️ 절대 코치 동작을 방해하지 않는다(전부 예외 무시).
_COACH_LOG_URL = "https://hth3thmujs.apps.bot-hosting.cloud/coach-log"
_COACH_LAST = {}     # mode -> {"rec":[챔프...], "ts":epoch, "sent":False}

def _parse_rec_champs(txt):
    """추천 텍스트("1. 챔피언명 — 이유") → 순서대로 챔프명 리스트."""
    out = []
    try:
        for line in str(txt or "").split("\n"):
            m = re.match(r"\s*(\d+)\s*[.)]\s*(.+)", line.strip())
            if not m: continue
            nm = re.split(r"[—–\-:]", m.group(2), 1)[0]
            nm = nm.replace("*", "").replace("`", "").strip()
            if nm and len(nm) <= 12 and nm not in out: out.append(nm)
    except Exception: pass
    return out[:10]

def _coach_log_send(mode, rec, actual, who):
    """추천 vs 실제 선택 1건 전송(비동기·조용히 실패)."""
    def _w():
        try:
            rank = (rec.index(actual) + 1) if actual in rec else 0
            requests.post(_COACH_LOG_URL, json={
                "token": _coach_token() or "", "who": str(who or ""), "mode": mode,
                "rec": rec, "actual": actual, "rank": rank}, timeout=8)
            print(f"[coachlog] {mode} 추천{len(rec)}개 · 실제 {actual} · 따름순위 {rank}", flush=True)
        except Exception: pass
    try: threading.Thread(target=_w, daemon=True).start()
    except Exception: pass

def _coach_outcome_tick(s_json, my_cell, kor):
    """내가 밴/픽을 '확정'했는지 감지 → 보관된 추천과 대조해 1회 전송."""
    try:
        for act_list in s_json.get("actions", []) or []:
            for act in (act_list if isinstance(act_list, list) else []):
                if not (isinstance(act, dict) and act.get("actorCellId") == my_cell
                        and act.get("completed") and act.get("type") in ("pick", "ban")):
                    continue
                m = act.get("type")
                st = _COACH_LAST.get(m)
                if not st or st.get("sent"): continue
                ch = kor(act.get("championId"))
                if not ch: continue
                st["sent"] = True
                _coach_log_send(m, st.get("rec") or [], ch, st.get("who") or "")
    except Exception: pass

def _draft_coach_tick(s_json, headers, base_url):
    """밴픽 세션에서 '내 차례'(픽 또는 밴)를 감지 → 비동기로 코칭 요청. 폴링 루프에서 매 주기 호출(가벼움).
       [v81.77] 밴 차례도 지원 + 라인 매치업/상대 장인 컨텍스트 추가(추천 품질 개선)."""
    if _DRAFT_BUSY[0] or not (load_claude_key() or _coach_token()): return   # [v82.33] 호스트 키 또는 구독 토큰
    try:
        my_cell = s_json.get("localPlayerCellId")
        if my_cell is None: return
        def _kor(cid):
            try:
                cid = int(cid or 0)
                if cid <= 0: return ""
                _e = global_champ_map.get(cid)     # ⚠️ champ_map은 폴링루프 지역변수 — 전역 맵을 써야 함
                if isinstance(_e, dict) and _e.get('kor'): return _e['kor']
                return GLOBAL_NUMERIC_CHAMP_MAP.get(cid, "")
            except Exception: return ""
        _coach_outcome_tick(s_json, my_cell, _kor)   # 📊 내가 확정한 밴/픽 ↔ 추천 대조 기록
        # ① 트리거 판정 [v82.39 설계B] — 밴은 '팀 밴'을 페이즈 시작에 통째로(내 차례 무관, 5명이 상의해 밴하므로).
        #    표준 드래프트: 1페이즈 밴 6개(양팀) → 픽6 → 2페이즈 밴 4개 → 픽4. 우리 팀 기준 3밴+2밴.
        mode = None; ban_phase = 0; my_already_picked = False
        _ban_inprog = False; _bans_done = 0; _my_pick_turn = False
        for act_list in s_json.get("actions", []) or []:
            for act in (act_list if isinstance(act_list, list) else []):
                if not isinstance(act, dict): continue
                _t = act.get("type")
                if _t == "ban":
                    if act.get("completed"): _bans_done += 1
                    if act.get("isInProgress") and not act.get("completed"): _ban_inprog = True
                elif _t == "pick" and act.get("actorCellId") == my_cell:
                    if act.get("completed"): my_already_picked = True
                    if act.get("isInProgress") and not act.get("completed"): _my_pick_turn = True
        if _ban_inprog:
            mode = "ban"; ban_phase = 1 if _bans_done < 6 else 2   # 1페이즈 밴 6개 완료 전=phase1
        elif _my_pick_turn:
            mode = "pick"
        else:
            return
        # ② 현재 밴픽판 수집
        def _pos(p):
            return POSITION_TRANSLATE_KOR.get(str(p.get("assignedPosition") or "").upper(), "")
        ally, enemy, my_pos, lane_enemy = [], [], "선택안함", ""
        my_champ = ""   # 내 확정 픽(2페이즈 밴 때 존재) — 추천 금지 목록에 포함
        my_pu, ally_pus, enemy_pus, lane_enemy_pu = "", [], [], ""
        _cidx = None
        try: _cidx = _clan_index()
        except Exception: pass
        def _rpu(p):   # puuid 없으면 소환사명으로 해석(토너먼트 드래프트 대비)
            _v = str(p.get("puuid") or "").strip().lower()
            if _cidx:
                _r = _clan_pu(_v, p.get("summonerName") or p.get("gameName") or "", _cidx)
                if _r: return _r
            return _v
        # 🧭 [v82.34] 픽을 '누가 골랐는지'에 귀속 — 포지션 환각 방지의 핵심.
        #   내전은 assignedPosition이 비어 포지션을 알 수 없음(v82.31 확인) → AI가 '서폿 럭스' 식으로 지어내고
        #   다음 문장에서 실제 서폿 유저 챔프폭과 모순을 냈음. 픽한 사람의 주포지션·그 챔프 전적을 함께 줘서
        #   '누구의 픽인지'로 추론하게 만든다. 포지션이 확정 안 됐으면 확정된 척하지 않는다.
        def _pick_desc(champ, pu, confirmed_pos=""):
            if not champ: return ""
            _e = ((_cidx or {}).get("by_pu") or {}).get(str(pu or "").strip().lower()) if pu else None
            _bits = []
            if confirmed_pos: _bits.append(f"포지션 확정:{confirmed_pos}")
            if _e:
                _nm = str(_e.get("name", "")).split("#")[0].strip() or "?"
                _mp = max(_e["pos"].items(), key=lambda x: x[1])[0] if _e.get("pos") else ""
                _cg, _cw = (_e.get("champs") or {}).get(champ, [0, 0])
                _tv = tier_of(_e.get("name") or "")   # [v82.40] 내부티어 — P3·P4(티어별 밸류픽 배분) 판단용
                _t = _nm + (f"(주:{_mp})" if _mp else "") + (f"[{_tv}티어]" if _tv not in (None, "") else "")
                _t += f" · 이 챔프 {_cg}판" + (f" {round(_cw/_cg*100)}%" if _cg else " (전적 없음)")
                _bits.append(_t)
            if not _bits: return champ
            return f"{champ} ← " + " / ".join(_bits)
        ally_desc, enemy_desc = [], []   # [v82.34] 픽 귀속 문장(누가 골랐는지)
        # 🧭 [2026-08-08 사장님 제보: "오함마가 서폿인 걸 알면서 왜 유력이라고 하나"]
        #   내전 커스텀은 assignedPosition이 비지만, 자동매칭 배정 포지션은 UI가 로비 로스터
        #   (gui_data blue/red: chosen_pos_icon)로 이미 알고 있다 — 세션 값이 비면 이걸로 폴백해
        #   ep·my_pos·lane_enemy 판정에 실제 배정 포지션을 쓴다(AI가 서폿 후보를 추리할 필요 제거).
        _gpos = {}
        try:
            with gui_lock:
                for _sd0 in ("blue", "red"):
                    for _p0, _s0 in (gui_data.get(_sd0) or []):
                        _pu0 = str(_p0.get("puuid") or "").strip().lower()
                        _k0 = POSITION_TRANSLATE_KOR.get(str(_p0.get("chosen_pos_icon") or "").upper(), "")
                        if _pu0 and _k0 and _k0 != "선택안함": _gpos[_pu0] = _k0
        except Exception: pass
        _pos_raw = _pos
        def _pos(p):
            _v = _pos_raw(p)
            if _v and _v != "선택안함": return _v
            return _gpos.get(str(_rpu(p) or "").strip().lower(), _v)
        for p in s_json.get("myTeam", []) or []:
            _pu = _rpu(p)
            if p.get("cellId") == my_cell:
                my_pos = _pos(p) or "선택안함"
                my_pu = _pu
            c = _kor(p.get("championId"))
            if p.get("cellId") == my_cell and c: my_champ = c
            if p.get("cellId") != my_cell:
                if c:
                    ally.append((c, _pos(p)))
                    ally_desc.append(_pick_desc(c, _pu, _pos(p)))
                if _pu: ally_pus.append(_pu)
        enemy_pools = []
        for p in s_json.get("theirTeam", []) or []:
            c = _kor(p.get("championId")); ep = _pos(p)
            _pu = _rpu(p)
            if c:
                enemy.append((c, ep))
                enemy_desc.append(_pick_desc(c, _pu, ep))
            if _pu: enemy_pus.append(_pu)
            # ★ 내 라인 상대(같은 포지션의 상대 챔프) — 픽 추천에서 상성 판단의 핵심
            if ep and my_pos != "선택안함" and ep == my_pos:
                if c: lane_enemy = f"{c} ({ep})"
                if _pu: lane_enemy_pu = _pu
            # 🎯 [2026-08-02 사장님 제보] 이미 픽을 확정한 상대는 다른 챔프를 꺼낼 수 없다.
            #    (1페이즈에 쉬바나를 픽한 사람의 챔프폭에 있던 녹턴이 2페이즈 밴 후보로 올라오던 문제)
            #    프롬프트 규칙만으로는 안 막힌다 — 데이터에서 아예 빼야 한다.
            if mode == "ban" and c:
                continue
            if mode == "ban":   # 밴 모드: 상대 선수별 '장인 챔프'(시트 전적, gviz 캐시라 할당량 0)
                try:
                    # [v82.45] 챔프별 '실제 플레이 포지션' 병기 → [v82.73] 이번 판 포지션 전적만 싣기.
                    _blk = _enemy_ban_pool(_pu, ep, _cidx) if _pu else None
                    if _blk: enemy_pools.append(_blk)
                except Exception: pass
        # 🛟 [v82.47 사장님 지시] 토너먼트 드래프트: 챔프선택 세션 theirTeam이 익명(퍼uid 없음)이라
        #    상대 명단이 통째로 비어 "상대 전적 없음" 티어리스트 밴만 나가던 문제 — UI가 동결해 둔
        #    로비 로스터(gui_data blue/red: 퍼uid + 이번 판 포지션)로 폴백. RayB 정글인데 서폿 밴 추천
        #    같은 포지션 무시 추천도 같은 뿌리(포지션 미전달)라 여기서 함께 해결된다.
        if not enemy_pus and my_pu:
            try:
                with gui_lock:
                    _fb_b = [dict(p) for p, _s in (gui_data.get("blue") or [])]
                    _fb_r = [dict(p) for p, _s in (gui_data.get("red") or [])]
                _pus_b = [str(p.get("puuid") or "").strip().lower() for p in _fb_b]
                _pus_r = [str(p.get("puuid") or "").strip().lower() for p in _fb_r]
                _en_fb = _fb_r if my_pu in _pus_b else _fb_b if my_pu in _pus_r else []
                for _p5 in _en_fb:
                    _pu = str(_p5.get("puuid") or "").strip().lower()
                    if not _pu or _pu.startswith(("bot_", "temp")): continue
                    _ep5 = POSITION_TRANSLATE_KOR.get(str(_p5.get("chosen_pos_icon") or "").upper(), "")
                    enemy_pus.append(_pu)
                    if _ep5 and my_pos != "선택안함" and _ep5 == my_pos and not lane_enemy_pu:
                        lane_enemy_pu = _pu
                    if mode == "ban":
                        try:
                            _blk = _enemy_ban_pool(_pu, _ep5, _cidx)
                            if _blk: enemy_pools.append(_blk)
                        except Exception: pass
                if enemy_pus:
                    print(f"[ghost] 세션 상대정보 없음 → 동결 로비 로스터 폴백({len(enemy_pus)}명)", flush=True)
                else:
                    print(f"[ghost] 상대 판별 실패 — 로비 로스터도 비었음(blue {len(_fb_b)} / red {len(_fb_r)}, 내 puuid 매칭 실패)", flush=True)
            except Exception: pass
        # 🧠 [v82.29] 내전 특화 컨텍스트 — 양팀 전원의 클랜 챔프폭 + 나와의 맞대결/합 전적
        clan_ally, clan_enemy, h2h_txt, syn_lines = [], [], "", []
        bp_lines = []   # [v82.32] 견제 압력 — 클랜이 실제로 밴해온 '진짜 무서운 픽'
        mu_lines, weak_lines = [], []   # ⚔️ [v82.35] 라인 매치업 실적 / 우리 팀이 취약한 상대 픽
        try:
            _idx = _cidx or _clan_index()
            if mode == "ban":
                _bpm = _idx.get("bp") or {}
                for _pu in enemy_pus:
                    _bl = _bpm.get(_pu)
                    if not _bl: continue
                    _e2 = (_idx.get("by_pu") or {}).get(_pu) or {}
                    _nm2 = str(_e2.get("name", "")).split("#")[0] or "상대"
                    bp_lines.append(f"- {_nm2}: " + " · ".join(
                        f"{x['champ']} +{x['targeted']}%p(z{x['z']})" for x in _bl[:3]))
            for _pu in ally_pus:
                _l = _clan_line(_pu, _idx)
                if _l: clan_ally.append(_l)
                _s = _pair_txt(my_pu, _pu, _idx, "syn", 10)     # 동료: 10판↑만(랜덤 배정이라 노이즈 큼)
                if _s:
                    _e = (_idx.get("by_pu") or {}).get(_pu) or {}
                    syn_lines.append(f"- {str(_e.get('name','')).split('#')[0] or '동료'}와 함께: {_s}")
            for _pu in enemy_pus:
                _l = _clan_line(_pu, _idx)
                if _l: clan_enemy.append(_l)
            if lane_enemy_pu:
                _h = _pair_txt(my_pu, lane_enemy_pu, _idx, "h2h", 5)   # 맞대결: 5판↑만
                if _h:
                    _e = (_idx.get("by_pu") or {}).get(lane_enemy_pu) or {}
                    h2h_txt = f"{str(_e.get('name','')).split('#')[0] or '상대'} 상대 통산 {_h}"
            # ⚔️ [v82.35] 픽 차례 — 내 챔프폭 각각이 '이 라인 상대 챔프'에게 어땠는지
            if mode != "ban":
                _lc = (lane_enemy or "").split(" (")[0].strip()
                if _lc:
                    for _c, _g, _w in (_my_champ_pool(MY_RIOT_NAME[0]) or [])[:12]:
                        _t = _mu_txt(my_pu, _c, _lc, _idx)
                        if _t: mu_lines.append(f"- {_c}(으)로 {_lc} 상대: {_t}")
                    mu_lines.sort()
            # ⚔️ [v82.35] 밴 차례 — 우리 팀 확정 픽이 '어떤 상대 픽에 약한지'(그게 곧 밴 후보)
            else:
                _mu1 = _idx.get("mu1") or {}; _mu2 = _idx.get("mu2") or {}
                _seen_w = set()
                for _pu_a, (_ca, _pa) in zip(ally_pus, ally) if len(ally_pus) == len(ally) else []:
                    _e3 = (_idx.get("by_pu") or {}).get(_pu_a) or {}
                    _nm3 = str(_e3.get("name", "")).split("#")[0] or "팀원"
                    _cand = {}
                    for _k4, _v4 in _mu2.items():
                        _p4, _mc4, _oc4 = _k4
                        if _p4 == _pu_a and _mc4 == _ca and _v4[0] >= 4:
                            _cand[_oc4] = (_v4[0], _v4[1], (_v4[2] / _v4[0]) if len(_v4) > 2 else 0.0, "이 선수 이 챔프")
                    for _k5, _v5 in _mu1.items():
                        _mc5, _oc5 = _k5
                        if _mc5 == _ca and _v5[0] >= 5 and _oc5 not in _cand:
                            _cand[_oc5] = (_v5[0], _v5[1], (_v5[2] / _v5[0]) if len(_v5) > 2 else 0.0, "클랜 전체")
                    for _oc, (_n, _w, _td, _lab) in sorted(_cand.items(), key=lambda x: x[1][1] / max(1, x[1][0]))[:2]:
                        _wr = round(_w / _n * 100)
                        if _wr <= 40 and (_nm3, _oc) not in _seen_w:
                            _seen_w.add((_nm3, _oc))
                            _ex = ""
                            if abs(_td) >= 0.3:
                                _ex = f" · 그 판들 팀 전력 {abs(_td):.1f}티어 " + ("불리(승률이 낮은 이유가 이쪽일 수 있음)" if _td > 0 else "유리")
                            weak_lines.append(f"- {_nm3}({_ca})는 {_oc} 상대로 {_n}판 {_w}승 {_wr}% ({_lab}){_ex}")
        except Exception: pass
        # 🎯 [v82.40] 선픽 안전 추천 — 상대 예상 챔프 = 잠긴 상대 픽 + 상대 유저별 주력 2개
        safe_gen, safe_opp = "", ""
        try:
            _idx2 = _cidx or _clan_index()
            _opp_champs = set(c for c, _p in enemy)
            for _pu in enemy_pus:
                _e = (_idx2.get("by_pu") or {}).get(_pu) or {}
                for _ch, _cw in sorted((_e.get("champs") or {}).items(), key=lambda x: -x[1][0])[:2]:
                    if _cw[0] >= 3: _opp_champs.add(_ch)
            safe_gen, safe_opp = _safe_pick_txt(my_pu, _my_champ_pool(MY_RIOT_NAME[0]), _idx2, _opp_champs, my_pos)
        except Exception: pass
        bans = []
        for act_list in s_json.get("actions", []) or []:
            for act in (act_list if isinstance(act_list, list) else []):
                if isinstance(act, dict) and act.get("type") == "ban" and act.get("completed"):
                    c = _kor(act.get("championId"))
                    if c and c not in bans: bans.append(c)
        # 🎯 [2026-07-30 사장님 지적] 상대 서폿이 이미 확정인데 서폿 챔프를 밴 추천하던 오류.
        #    이미 채워진 자리의 챔프는 나올 수 없으니 밴 후보에서 빠져야 한다.
        _ROLES5 = ["탑", "정글", "미드", "원딜", "서폿"]
        _e_filled = sorted({str(_p) for _c, _p in enemy if _p and _p in _ROLES5}, key=_ROLES5.index)
        _e_open = [r for r in _ROLES5 if r not in _e_filled]
        # 🎯 [2026-08-02] 토너먼트 드래프트(상대 익명 → 로비 로스터 폴백)에서는 '누가 픽했는지'를 못 맞춘다.
        #    대신 이미 채워진 자리의 사람은 어차피 끝났으므로, 그 포지션표가 붙은 챔프폭을 통째로 뺀다.
        if mode == "ban" and _e_filled:
            _keep = []
            for _nm6, _cs6 in enemy_pools:
                _m6 = re.search(r"\[이번 판 포지션:\s*([^\]]+)\]", str(_nm6))
                if _m6 and _m6.group(1).strip() in _e_filled: continue
                _keep.append((_nm6, _cs6))
            if len(_keep) != len(enemy_pools):
                print(f"[draft] 이미 픽 끝난 자리 {len(enemy_pools)-len(_keep)}명 챔프폭 제외 (채워짐: {','.join(_e_filled)})", flush=True)
            enemy_pools = _keep
        # 🚫 [2026-08-06 사장님 제보] 1페이즈에 밴한 챔프가 2페이즈 밴 추천에 또 나옴 — 픽과 같은 교훈:
        #    프롬프트 금지 규칙만으로는 안 막힌다. 이미 밴된 챔프를 후보 데이터(상대 챔프폭)에서 아예 뺀다.
        _dead_ch = set(bans) | {c for c, _ in ally} | {c for c, _ in enemy} | ({my_champ} if my_champ else set())
        if mode == "ban" and _dead_ch:
            enemy_pools = [(_h7, [_s7 for _s7 in _cs7 if _s7.split("(")[0].strip() not in _dead_ch])
                           for _h7, _cs7 in enemy_pools]
        # 🔨 [2026-08-07 사장님 지시] 밴픽 퀴즈 표(클랜 집단 학습) — 이번 판 상대에게 찍힌 밴 표를 근거로 첨부
        quiz_lines = []
        if mode == "ban":
            try:
                _qm = _quiz_pref_map()
                _enames = {str(_n9).split('[')[0].strip() for _n9, _cs9 in (enemy_pools or [])}
                for _pu9 in enemy_pus:
                    _e9 = ((_cidx or {}).get("by_pu") or {}).get(_pu9) or {}
                    if _e9.get("name"): _enames.add(str(_e9["name"]).split('#')[0].strip())
                for _nm9 in sorted(_enames):
                    for _c9, _v9, _h9 in _qm.get(tnorm(_nm9), [])[:3]:
                        if _c9 in _dead_ch or _v9 <= 0: continue
                        quiz_lines.append(f"{_nm9} ← {_c9} {_v9}표" + (f"·적중{_h9}" if _h9 else ""))
            except Exception: pass
        ctx = {"mode": mode, "pos": my_pos, "ally": ally, "enemy": enemy, "bans": bans,
               "enemy_filled_pos": _e_filled, "enemy_open_pos": _e_open,
               "enemy_names": [_n for _n, _cs in (enemy_pools or [])],   # 🗳️ 퀴즈 표 조회용
               "lane_enemy": lane_enemy, "enemy_pools": enemy_pools,
               "clan_ally": clan_ally, "clan_enemy": clan_enemy, "h2h": h2h_txt, "syn": syn_lines,
               "me": (my_pu or MY_RIOT_NAME[0] or ""),   # 🔐 [v82.34] 토큰-계정 결속용 식별자(공유 차단)
               "bp": bp_lines, "ally_desc": ally_desc, "enemy_desc": enemy_desc,
               "mu": mu_lines, "weak": weak_lines,   # ⚔️ [v82.35] 라인 매치업 / 우리 팀 취약 구도
               "ban_phase": ban_phase, "already_picked": my_already_picked,   # [v82.39] 설계B
               "safe_gen": safe_gen, "safe_opp": safe_opp,   # 🎯 [v82.40] 선픽 안전(일반/이 상대)
               "my_tier": tier_of(MY_RIOT_NAME[0]),   # P3·P4 — 내 내부티어에 맞는 밸류픽 배분
               "loff_good": ((_cidx or {}).get("loff_good_txt") or ""),   # 📊 저티어 오프롤 성과/함정픽(실측)
               "loff_bad": ((_cidx or {}).get("loff_bad_txt") or ""),
               "quiz": quiz_lines,   # 🔨 밴픽퀴즈 표(클랜 집단 학습, 밴 모드만)
               "noban": list(_NOBAN.get("decls") or []),   # 🚫 이 판 노밴 선언(로비 채팅 감지)
               "pos_known": bool(my_pos and my_pos != "선택안함")}
        # 밴은 페이즈당 1회만(팀 밴 통째 추천) / 픽은 판 상태 바뀌면 갱신
        # [2026-07-25 사장님 제보 수정] 서명에 게임 식별자 포함 — 닷지·다음 게임에서 같은 서명("banphase1")으로
        #   오인돼 추천이 안 뜨던 문제 해결(gameId 없으면 10분 창 폴백으로라도 게임 간 구분).
        _sid = str(s_json.get("gameId") or "") or f"t{int(time.time() // 600)}"
        if mode == "ban":
            sig = f"{_sid}|banphase{ban_phase}"
        else:
            sig = f"{_sid}|pick|{my_pos}|{','.join(c for c,_ in ally)}|{','.join(c for c,_ in enemy)}|{','.join(sorted(bans))}"
        if sig in _DRAFT_SEEN: return          # 같은 상황 재호출 금지(폴링이 초당 여러 번 도니 필수)
        _DRAFT_SEEN.add(sig)
        if len(_DRAFT_SEEN) > 200: _DRAFT_SEEN.clear()

        def _work():
            _DRAFT_BUSY[0] = True
            try:
                with gui_lock:
                    gui_data["draft_advice"] = "🚫 밴 분석 중…" if mode == "ban" else "🧠 픽 분석 중…"
                    gui_data["draft_advice_ts"] = time.time()
                txt = _draft_advise(ctx, _my_champ_pool(MY_RIOT_NAME[0]))
                # 🚫 [2026-08-06 사장님 제보] 데이터에서 빼도 모델이 일반 지식으로 죽은 챔프(이미 밴·픽)를
                #    추천할 수 있다 — 응답에서 해당 줄을 잘라내는 최종 방어. 요약부의 "N. 챔프 — 이유" 줄만 손댄다.
                try:
                    if mode == "ban" and txt and not str(txt).lstrip().startswith(("⚠️", "⏳", "🔐", "✅")):
                        _sum8, _rea8 = _split_reason(txt)
                        _keep8, _cut8, _n8 = [], [], 0
                        for _ln8 in _sum8.split("\n"):
                            _m8 = re.match(r"\s*\d+\s*[.)]\s*(.+)", _ln8.strip())
                            if _m8:
                                _nm8 = re.split(r"[—–\-:]", _m8.group(1), 1)[0].replace("*", "").replace("`", "").strip()
                                if _nm8 in _dead_ch:
                                    _cut8.append(_nm8); continue
                                _n8 += 1
                                _ln8 = re.sub(r"^(\s*)\d+(\s*[.)])", lambda m9: f"{m9.group(1)}{_n8}{m9.group(2)}", _ln8)
                            _keep8.append(_ln8)
                        if _cut8:
                            print(f"[coach] 죽은 챔프 추천 {len(_cut8)}건 제거: {', '.join(_cut8)}", flush=True)
                            txt = "\n".join(_keep8) + ((f"\n{_REASON_SEP}\n" + _rea8) if _rea8 else "")
                except Exception: pass
                # 🗒️ [2026-07-30] 코치가 실제로 뭐라고 답했는지 로그에 남긴다.
                #    화면은 잠깐 뜨고 사라져 사후 검증이 불가능했다 — 규칙을 고치려면 실제 답을 봐야 한다.
                try:
                    _opp_n = sum(1 for _n, _cs in (ctx.get("enemy_pools") or []) if _cs)
                    print(f"[coach] {mode}{ban_phase if mode == 'ban' else ''} "
                          f"내포지션={ctx.get('pos')} 상대확정={ctx.get('enemy_filled_pos')} "
                          f"빈자리={ctx.get('enemy_open_pos')} 상대전적붙은인원={_opp_n}\n"
                          f"{str(txt or '(빈 응답)')}\n[coach] ----", flush=True)
                except Exception: pass
                # 📊 [v82.34] 추천 챔프 보관 — 내가 실제로 확정하는 순간 대조해 기록(경고문구는 제외)
                try:
                    if txt and not str(txt).lstrip().startswith(("⚠️", "⏳", "🔐", "✅")):
                        _rc = _parse_rec_champs(_split_reason(txt)[0])   # 근거 줄의 번호를 챔프로 오인하지 않게 요약부만
                        if _rc: _COACH_LAST[mode] = {"rec": _rc, "ts": time.time(),
                                                     "sent": False, "who": ctx.get("me") or ""}
                except Exception: pass
                # 🔁 [2026-07-31] '잠시 후 다시 시도' 문구도 정상 답변으로 취급해 서명을 안 지우던 탓에
                #    그 판은 끝까지 재시도가 안 됐다(2페이즈 밴 무응답의 체감 증상).
                #    만료·한도·토큰공유(⏳🔐/구독)는 재시도해도 소용없으니 제외한다.
                _transient = (not txt) or str(txt).lstrip().startswith(
                    ("⚠️ 고스트밴픽왕: 잠시 후", "⚠️ 고스트밴픽왕: 서버 연결", "⚠️ 고스트밴픽왕: 응답이 늦어"))
                with gui_lock:
                    if txt and not _transient:
                        _hdr = (f"🚫 {ban_phase}페이즈 밴 추천" if mode == "ban" else "🧠 AI 픽 추천")
                        gui_data["draft_advice"] = f"{_hdr}\n{txt}"
                    elif _transient:
                        gui_data["draft_advice"] = ("⚠️ 추천 생성 실패 — 잠시 후 자동 재시도합니다"
                                                     if (load_claude_key() or _coach_token()) else "")
                        _DRAFT_SEEN.discard(sig)   # 서명 철회 → 다음 폴링에서 실제로 재시도
                    gui_data["draft_advice_ts"] = time.time()
            except Exception: pass
            finally: _DRAFT_BUSY[0] = False
        threading.Thread(target=_work, daemon=True).start()
    except Exception: pass

_TIER_BASE = {"IRON":0,"BRONZE":400,"SILVER":800,"GOLD":1200,"PLATINUM":1600,"EMERALD":2000,
              "DIAMOND":2400,"MASTER":2800,"GRANDMASTER":2800,"CHALLENGER":2800}
_DIV = {"IV":0,"III":1,"II":2,"I":3}
def _rank_score(tier, rank, lp):
    """티어+디비전+LP → MMR 대용 사다리 점수(실력순서 단조)."""
    base = _TIER_BASE.get((tier or "").upper())
    if base is None: return None
    if (tier or "").upper() in ("MASTER","GRANDMASTER","CHALLENGER"): return base + int(lp or 0)
    return base + _DIV.get((rank or "").upper(), 0) * 100 + min(int(lp or 0), 99)

_PREV_SEASON_CACHE = {}   # {tnorm(name): (name, tier_str, score)} — 이번 세션 LCU에서 캡처한 직전시즌
def _prev_season_from_ranked(rj):
    """LCU ranked-stats json → 솔로랭크 직전 1시즌(마감) '티어문자열, 점수'. 없으면 (None,None).
    ⚠️ 최상위 highestPreviousSeasonEndTier 등은 플렉스 등 다른 큐 데이터가 섞여 들어올 수 있어
    반드시 queueMap.RANKED_SOLO_5x5 안쪽 값만 사용(실제 클라 응답으로 검증됨, 2026-07-01)."""
    if not isinstance(rj, dict): return None, None
    solo = ((rj.get("queueMap") or {}).get("RANKED_SOLO_5x5")) or {}
    for tk, dk in (("previousSeasonEndTier", "previousSeasonEndDivision"),
                   ("previousSeasonHighestTier", "previousSeasonHighestDivision")):
        t = str(solo.get(tk) or "").upper().strip()
        d = str(solo.get(dk) or "").upper().strip()
        if t and t not in ("NONE", "UNRANKED", ""):
            sc = _rank_score(t, d, 0)
            if sc is not None: return (f"{t} {d}".strip(), sc)
    return None, None

def fetch_solo_rank_by_riotid(riot_id, key, region="kr", routing="asia"):
    """롤닉#태그 → account-v1로 진짜 PUUID 해석 → 솔랭. (시트 PUUID는 LCU형식이라 직접 못 씀)"""
    try:
        if "#" not in str(riot_id): return None
        import urllib.parse
        gn, tl = str(riot_id).rsplit("#", 1)
        h = {"X-Riot-Token": key}
        ar = requests.get(f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
                          f"{urllib.parse.quote(gn.strip())}/{urllib.parse.quote(tl.strip())}", headers=h, timeout=8)
        if ar.status_code != 200: return None
        puuid = ar.json().get("puuid")
        if not puuid: return None
        b = f"https://{region}.api.riotgames.com"
        r = requests.get(f"{b}/lol/league/v4/entries/by-puuid/{puuid}", headers=h, timeout=8)
        if r.status_code != 200:   # 폴백: summoner-v4 → by-summoner
            sr = requests.get(f"{b}/lol/summoner/v4/summoners/by-puuid/{puuid}", headers=h, timeout=8)
            if sr.status_code != 200: return None
            r = requests.get(f"{b}/lol/league/v4/entries/by-summoner/{sr.json().get('id')}", headers=h, timeout=8)
            if r.status_code != 200: return None
        for e in r.json():
            if e.get("queueType") == "RANKED_SOLO_5x5":
                t, rk, lp = e.get("tier"), e.get("rank"), e.get("leaguePoints", 0)
                w, l = e.get("wins", 0), e.get("losses", 0)
                return {"tier": t, "rank": rk, "lp": lp, "wins": w, "losses": l, "score": _rank_score(t, rk, lp)}
        return {"tier": "UNRANKED", "score": None}
    except Exception: return None

def update_solo_ranks():
    """내부티어 보유 클랜원 솔랭을 롤닉으로 조회해 SOLO_RANK 시트에 저장.
       매칭 키 = tnorm(닉네임). (LCU PUUID는 녹화 세션마다 불안정해 못 씀 — 티어와 동일하게 이름 기반)."""
    key = load_riot_key()
    if not key or not global_spreadsheet: return
    # 시트에서 {tnorm(게임닉): 롤닉#태그} 맵 (소환사명 = 풀 롤닉#태그)
    rid_map = {}
    try:
        rows0 = get_sheet_data_cached(global_spreadsheet.worksheet("CLASSIC_NORMAL"), force=True)
        h0 = rows0[0]; ni = h0.index("소환사명")
        for r in rows0[1:]:
            if len(r) > ni:
                rid = str(r[ni]).strip()
                if "#" in rid:
                    k = tnorm(rid)
                    if k and k not in rid_map: rid_map[k] = rid
    except Exception: pass
    with gui_lock:
        gstats = dict(gui_data.get("hof_classic", {}).get("global_stats", {}).get("전체 (ALL)", {}))
        aliases = dict(gui_data.get("hof_classic", {}).get("aliases", {}))
    out = [["닉네임","티어","LP","솔랭승","솔랭패","점수","갱신"]]
    for _pk, s in gstats.items():
        nm = s.get("name", "")
        if not tier_of(nm): continue
        rid = rid_map.get(tnorm(nm))
        if not rid:
            for al in aliases.get(_pk, ()):        # 닉변 시 과거 닉으로도 매칭
                rid = rid_map.get(tnorm(al))
                if rid: break
        if not rid: continue
        rk = fetch_solo_rank_by_riotid(rid, key)
        if rk and rk.get("score") is not None:
            out.append([nm, f"{rk['tier']} {rk.get('rank','')}".strip(), rk.get("lp",0),
                        rk.get("wins",0), rk.get("losses",0), rk["score"],
                        time.strftime("%Y-%m-%d %H:%M")])
        time.sleep(1.3)   # rate limit
    # 🛡️ [v82.48 사장님 제보 — 시트 전멸 사고 방지] 예전엔 조회 결과와 무관하게 clear+덮어쓰기라,
    #    Riot API 키 만료·네트워크 실패로 전건 조회가 실패하면 SOLO_RANK가 헤더만 남고 통째로 비워졌다.
    #    ① 수집 0건이면 아예 쓰지 않음 ② 기존 대비 절반 미만으로 급감해도 보류(부분 실패 보호).
    try:
        try: ws = global_spreadsheet.worksheet("SOLO_RANK")
        except Exception: ws = global_spreadsheet.add_worksheet(title="SOLO_RANK", rows="400", cols="7")
        _new_n = len(out) - 1
        if _new_n <= 0:
            print("[solo] 수집 0건 — 기존 SOLO_RANK 보존(덮어쓰기 취소). Riot API 키 만료 여부 확인 필요", flush=True)
            return
        try:
            _prev_n = max(0, len([r for r in (get_sheet_data_cached(ws, force=True) or [])[1:] if r and str(r[0]).strip()]))
        except Exception:
            _prev_n = 0
        if _prev_n >= 10 and _new_n < _prev_n * 0.5:
            print(f"[solo] 수집 급감({_prev_n}→{_new_n}) — 부분 실패로 보고 덮어쓰기 보류", flush=True)
            return
        ws.clear(); ws.update(out)
        invalidate_sheet_cache("SOLO_RANK")
        print(f"[solo] SOLO_RANK 갱신 {_new_n}명", flush=True)
    except Exception as _se:
        print(f"[solo] SOLO_RANK 기록 실패: {type(_se).__name__}", flush=True)

def solo_rank_engine():
    """시작 90초 후 + 12시간마다 솔랭 갱신(키 없으면 no-op).
       🛡️ [v82.48] 갱신 대상은 gui_data['hof_classic'] 집계에서 뽑는데, 시작 직후엔 아직 비어 있을 수 있다.
          예전엔 그 상태로 돌면 대상 0명 → 시트를 헤더만 남기고 비우는 사고가 났다(위 가드로 이중 방어).
          여기서는 집계가 준비될 때까지 최대 10분 대기 후 시작한다."""
    time.sleep(90)
    for _ in range(60):
        try:
            with gui_lock:
                _ready = bool(gui_data.get("hof_classic", {}).get("global_stats", {}).get("전체 (ALL)"))
            if _ready: break
        except Exception: pass
        time.sleep(10)
    while True:
        try:
            if load_riot_key() and global_spreadsheet: update_solo_ranks()
        except Exception: pass
        time.sleep(12 * 3600)

# ===== 📋 PEAK_SEASONS 누락 알림(반자동, 호스트 전용) — [2026-07-16 사장님 지시] =====
#   과거 3시즌 최고티어(PEAK_SEASONS)는 op.gg를 보고 사람이 직접 입력하는 수동 스냅샷(자동 측정 소스 없음).
#   새 클랜원이 들어오면 그 사람만 아직 PEAK_SEASONS에 없으므로, '누구를 측정해야 하는지' 목록을 뽑아
#   HOST_NOTICE 채널로 알린다. (측정 자체는 사장님이 op.gg 보고 입력 → 이미 있는 사람은 재측정 불필요)
_PEAK_NOTIFIED = None    # tnorm(닉네임) 집합 — 이미 파악/알린 사람. None=미로딩. 파일 없으면 '첫 실행=기준선'.
_PEAK_NOTIFIED_FILE = os.path.join(CONFIG_DIR, 'peak_notified.json')

def _load_peak_notified():
    """[2026-07-16 사장님 지시=선택지2] 기준선 방식 — 파일 존재하면 True(기준선 있음), 없으면 False(첫 실행)."""
    global _PEAK_NOTIFIED
    if _PEAK_NOTIFIED is not None: return True
    try:
        with open(_PEAK_NOTIFIED_FILE, encoding='utf-8') as f:
            _PEAK_NOTIFIED = set(json.load(f))
        return True                                  # 파일 있음 = 기준선 이미 설정됨
    except Exception:
        _PEAK_NOTIFIED = set()
        return False                                 # 파일 없음 = 최초 실행(현 미측정자를 기준선으로 시드)

def _save_peak_notified():
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(_PEAK_NOTIFIED_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(_PEAK_NOTIFIED), f, ensure_ascii=False)
    except Exception: pass

def _fow_scrape_peak(riot_id, top_n=3):
    """[2026-07-16 사장님 지시] fow.lol에서 최근 top_n 시즌 '솔로랭크 최고기록(LP포함)' 중 최고점 스크랩.
       → {tier_str,season,score,detail}. 실패(404·솔로없음·네트워크) 시 None. op.gg 수동측정의 2800 눌림 해결."""
    import re as _re, urllib.parse as _up, urllib.request as _ur
    if "#" not in str(riot_id): return None
    nm, tg = str(riot_id).rsplit("#", 1)
    u = "https://www.fow.lol/find/kr/" + _up.quote(nm.strip() + "-" + tg.strip())
    html = None
    for _a in range(2):                                   # 503/타임아웃 1회 재시도
        try:
            html = _ur.urlopen(_ur.Request(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}),
                               timeout=12).read().decode("utf-8", "ignore"); break
        except Exception: time.sleep(4)
    if not html: return None
    badges = _re.findall(r"tipsy_live'\s+tipsy='([^']*)'>(S[^<]*)</DIV>", html)   # 시즌 뱃지(최신순)
    seasons = []
    for tip, label in badges:
        if "솔로랭크" not in tip: continue
        m = _re.search(r"최고 기록:\s*([A-Z]+)\s+([IV]+)\s*-\s*(\d+)", tip.split("<HR>")[0])   # 솔로 섹션(첫 HR 전)
        if not m: continue
        t, d, lp = m.group(1), m.group(2), int(m.group(3))
        seasons.append((label.split(":")[0].strip().replace(" ", ""), t, d, lp, _rank_score(t, d, lp)))
    if not seasons: return None
    recent = seasons[:top_n]
    best = max(recent, key=lambda x: x[4] or 0)
    _dn = {"I": "1", "II": "2", "III": "3", "IV": "4"}
    return {"tier_str": (best[1].lower() + " " + _dn.get(best[2], "")).strip(), "season": best[0], "score": best[4],
            "detail": " / ".join(f"{s[0]}:{s[1].lower()} {_dn.get(s[2],'')}({s[4]})" for s in recent)}

def _peak_append_rows(rows):
    """PEAK_SEASONS 끝에 행 추가(서비스계정). rows=[[닉네임,차트닉,최고티어,최고시즌,점수,상세,측정일],...]."""
    if not rows: return True
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(resource_path('credentials.json.json'), scope)
        tok = creds.get_access_token().access_token
        u = ("https://sheets.googleapis.com/v4/spreadsheets/" + DOCUMENT_ID +
             "/values/PEAK_SEASONS!A1:G1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS")
        r = requests.post(u, headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
                          data=json.dumps({"values": rows}), timeout=30)
        return r.status_code == 200
    except Exception as e:
        print(f"[peak] PEAK 추가 실패: {e}", flush=True); return False

def _peak_missing_check():
    """CLAN_TIERS(로스터) − PEAK_SEASONS(측정완료) = 미측정 신규 인원 → fow.lol 자동 스크랩→PEAK 추가.
       연동없음·fow미확인은 HOST_NOTICE로 '수동 필요' 안내. 읽기는 공개 gviz(할당량0). 호스트 1대만."""
    import csv as _csv, io as _io, urllib.parse
    if not load_bot_token(): return                       # 호스트 1대만
    # [2026-07-21 사장님 지시] 과거티어 자동측정 결과는 설명서 채널(HOST_NOTICE) → 데이터처리소(DATA)로 이동. DATA 미설정 시 기존 채널 폴백.
    url = DATA_WEBHOOK_URL if (DATA_WEBHOOK_URL and not DATA_WEBHOOK_URL.startswith("여기에")) else HOST_NOTICE_WEBHOOK_URL
    if not url or url.startswith("여기에"): return          # 웹훅 미설정이면 조용히 skip
    # ① 측정 완료 집합(PEAK_SEASONS)
    try:
        prows = list(_csv.reader(_io.StringIO(_fetch_public_csv(DOCUMENT_ID, sheet="PEAK_SEASONS", headers=1, timeout=8))))
    except Exception: return
    if not prows or "닉네임" not in prows[0]: return         # 시트 못 읽으면(일시 오류) 이번 주기 skip — 오탐 방지
    pni = prows[0].index("닉네임")
    have = {tnorm(r[pni]) for r in prows[1:] if len(r) > pni and r[pni].strip()}
    if not have: return                                   # 빈 시트로 읽히면(잘림 등) 전원 오탐 위험 → skip
    # ② 클랜 로스터(CLAN_TIERS) — 내부티어 보유자 = 측정 대상
    try:
        crows = list(_csv.reader(_io.StringIO(_fetch_public_csv(DOCUMENT_ID, gid=CLAN_TIERS_GID, timeout=8))))
    except Exception: return
    if not crows or (crows[0][0] if crows[0] else "").strip() != "닉네임": return
    roster = [r[0].strip() for r in crows[1:] if r and r[0].strip()]
    if len(roster) < 100: return                          # gviz 잘림 등 이상 → 전체쓰기 사고 방지(1회 원칙)
    # ③ 롤닉#태그 맵(fow 조회용) — 기존 PEAK 닉네임(태그포함) + CLASSIC_NORMAL·KIWI_KIWI 소환사명(공개 csv)
    rid = {}
    for r in prows[1:]:                                   # 기존 PEAK 닉네임에 태그가 있으면 우선 활용
        if len(r) > pni and "#" in str(r[pni]):
            k = tnorm(r[pni])
            if k and k not in rid: rid[k] = str(r[pni]).strip()
    for _sh in ("CLASSIC_NORMAL", "KIWI_KIWI"):
        try:
            rows0 = list(_csv.reader(_io.StringIO(_fetch_public_csv(DOCUMENT_ID, sheet=_sh, headers=1, timeout=8))))
            if rows0 and "소환사명" in rows0[0]:
                si = rows0[0].index("소환사명")
                for r in rows0[1:]:
                    if len(r) > si and "#" in str(r[si]):
                        k = tnorm(r[si])
                        if k and k not in rid: rid[k] = str(r[si]).strip()
        except Exception: pass
    # ④ 미측정 = 로스터에 있지만 PEAK에 없음.
    missing = [nm for nm in roster if tnorm(nm) not in have]
    # [선택지2=기준선] 최초 실행(파일 없음)이면 '현재 미측정 전원'을 조용히 기준선으로 시드 → 알림 X.
    #   이후부터 새로 생긴 미측정자(=신규 인원)만 알린다. 유효한 읽기(위 가드 통과) 뒤에만 시드해 오탐 방지.
    if not _load_peak_notified():
        for nm in missing: _PEAK_NOTIFIED.add(tnorm(nm))
        _save_peak_notified()
        print(f"[peak] 기준선 설정 — 현재 미측정 {len(missing)}명 조용히 시드(이후 신규 인원만 알림)", flush=True)
        return
    fresh = [nm for nm in missing if tnorm(nm) not in _PEAK_NOTIFIED]
    if not fresh: return
    batch = fresh[:8]                                     # 이번 주기 처리량 제한(fow 부하·쿼터 안전)
    today = time.strftime("%Y-%m-%d %H:%M") + " (fow)"
    auto_rows = []; auto_done = []; manual = []
    for nm in batch:
        r_id = rid.get(tnorm(nm))
        if not r_id:
            manual.append((nm, None)); continue          # 연동 없음 → 수동
        res = _fow_scrape_peak(r_id)
        time.sleep(3)                                     # fow 예의상 간격
        if res and res.get("score") and 500 <= int(res["score"]) <= 4000:
            auto_rows.append([r_id, nm, res["tier_str"], res["season"], str(res["score"]), res["detail"], today])
            auto_done.append((nm, res))
        else:
            manual.append((nm, r_id))                     # 404·솔로기록없음 → 수동
    wrote = _peak_append_rows(auto_rows)
    if wrote:                                             # 시트 반영 성공 시에만 처리완료 마킹(실패 시 다음 주기 재시도)
        for nm in batch: _PEAK_NOTIFIED.add(tnorm(nm))
        _save_peak_notified()
    # ⑤ 결과 알림(HOST_NOTICE)
    lines = ["📋 **[과거티어 자동 측정]** 신규 인원 처리 결과 (fow.lol · 최근 3시즌 솔로 최고)"]
    if auto_done:
        lines.append(f"✅ **{len(auto_done)}명 자동 측정 완료** — PEAK_SEASONS에 바로 반영됐어요:")
        for nm, res in auto_done: lines.append(f"• {nm} — **{res['tier_str'].upper()}** ({res['score']}점)")
    if manual:
        lines.append(f"✍️ **{len(manual)}명 수동 필요** (fow 미확인·연동 없음) — op.gg/fow 확인 후 시트 입력:")
        for nm, r_id in manual[:20]: lines.append(f"• {nm}" + (f"  (`{r_id}`)" if r_id else "  (연동 없음)"))
    lines.append("-# 새 인원당 1회 처리 · 자동 측정 실패분만 수동으로 채워주시면 돼요")
    try: requests.post(url, json={"content": "\n".join(lines)[:1990]}, timeout=8)
    except Exception: pass
    print(f"[peak] 자동측정 {len(auto_done)} · 수동필요 {len(manual)} · 시트반영 {wrote}", flush=True)

def peak_missing_engine():
    """시작 4분 후 + 6시간마다 PEAK_SEASONS 누락 점검(호스트 전용·공개 읽기)."""
    time.sleep(240)
    while True:
        try: _peak_missing_check()
        except Exception: pass
        time.sleep(6 * 3600)

# ===== 🛠️ '결과 대기' 백필 데몬(호스트, Riot Match-V5) — [v81.62 사장님 지시: 결과대기 근본 해결] =====
# 경위: finalize는 '게임 당시 그 게임을 기록하던 인스턴스'만 수행 가능(인메모리 active_recording_id) →
#   전원 조기종료·전광판 스킵(eog 캡처 실패)·429 쓰기예산 소진·로비 이탈 게이트 등 어느 하나로도 승자 기입이
#   유실되면 소급 수단이 전혀 없어 시트에 '결과 대기'가 영구 잔존(반복 재발). LCU/웹훅 경로와 완전히 독립인
#   사후 회복 루프: 시트의 '#<게임ID>'를 Match-V5(KR_<게임ID>, asia)로 조회해 결과(+KDA·평가 마감)를 채움.
# 설계: 호스트 전용(riot_key.txt 보유 시)·15분 주기 → 어떤 실패 모드든 최대 1주기 내 자동 마감.
#   읽기=gviz(get_sheet_data_cached, 읽기 할당량 0) 스캔 + 쓰기 직전 서비스계정 재독(행번호 정확성),
#   쓰기=게임당 update_cells 1회. 404(리엇 미보관·CUSTOM_ 폴백ID)는 스킵셋으로 무한 재시도 방지.
_BF_POS_KOR = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서폿"}
_bf_skip_gids = set()    # 영구 조회불가 게임ID(세션 한정) — 매 주기 재시도 방지
_bf_404_counts = {}      # gid -> 404 횟수. [적대적리뷰 반영] 장기게임(40~60분)·리엇 색인 지연 중 404를 즉시 영구스킵하면
                         # 그 게임 백필이 세션 내내 무력화 → 6주기(약 90분) 유예 후에만 영구 스킵.

def backfill_pending_results():
    key = load_riot_key()
    if not key or not global_spreadsheet: return
    hdrs = {"X-Riot-Token": key}
    now = time.time()
    for tab in ("CLASSIC_NORMAL", "KIWI_KIWI"):
        try:
            ws = global_spreadsheet.worksheet(tab)
            rows = get_sheet_data_cached(ws, force=True)   # gviz — 읽기 할당량 0
        except Exception:
            continue
        if not rows or len(rows) < 2: continue
        hd = rows[0]
        def _ci(name): return hd.index(name) if name in hd else -1
        c_gid, c_res, c_date = _ci("게임ID"), _ci("결과"), _ci("날짜")
        c_side, c_pos, c_name = _ci("진영"), _ci("포지션"), _ci("소환사명")
        c_kda, c_eval = _ci("KDA"), _ci("매치평가")
        c_item, c_rune1, c_rune2 = _ci("아이템"), _ci("주룬"), _ci("보조룬")   # 🛒 [v81.70] 백필에도 소급
        c_spell = _ci("스펠")   # 🔮 [v81.73] 스펠 소급
        if c_gid < 0 or c_res < 0 or c_side < 0: continue
        # ① '결과 대기' + '#숫자' 게임ID 수집(CUSTOM_ 폴백ID는 리엇 역추적 불가 → 제외)
        #   🏅 [v82.48 사장님 지시] 여기에 '결과는 있는데 매치평가가 「평가 없음」인 게임'도 포함 —
        #      과거 백필로 마감돼 평가가 비어 있던 게임들을 Match-V5로 소급 계산해 채운다.
        #      (조회 가능한 범위만 자연 처리되고, 다 채워지면 대상이 사라져 스스로 멈춘다)
        # 게임당 평가는 MVP·ACE·역적 3명뿐 → 나머지 7명의 '평가 없음'은 정상값이다.
        # 게임ID 단위로 '평가가 하나라도 기록된 게임'을 소급 완료로 보고 재조회 대상에서 제외(무한 재조회 방지).
        _eval_done_gids = set()
        if c_eval >= 0:
            for r in rows[1:]:
                try:
                    if len(r) <= max(c_gid, c_eval): continue
                    if str(r[c_eval]).strip() in ("MVP", "ACE", "역적"):
                        _eval_done_gids.add(str(r[c_gid]).strip())
                except Exception: continue
        pend = []
        _pend_meta = {}   # gid -> (가장 이른 날짜문자열, [시트행번호…]) — 오래된 미보관 판 마감용
        for _ri, r in enumerate(rows[1:], start=2):
            try:
                if len(r) <= max(c_gid, c_res): continue
                _res_v = str(r[c_res]).strip()
                _eval_v = str(r[c_eval]).strip() if (c_eval >= 0 and len(r) > c_eval) else ""
                _need_eval = ((_res_v in ("승리", "패배")) and (_eval_v == "평가 없음")
                              and str(r[c_gid]).strip() not in _eval_done_gids)
                if _res_v != "결과 대기" and not _need_eval: continue
                gid = str(r[c_gid]).strip()
                if not re.fullmatch(r"#\d+", gid) or gid in _bf_skip_gids: continue
                # 진행중/방금 끝난 게임의 라이브 finalize와 경합 방지: 시작 30분 경과 행만(날짜 파싱 불가 시 안전하게 보류)
                try:
                    if now - time.mktime(time.strptime(str(r[c_date]).strip(), "%Y-%m-%d %H:%M")) < 1800: continue
                except Exception:
                    continue
                if gid not in pend: pend.append(gid)
                _m = _pend_meta.setdefault(gid, [str(r[c_date]).strip(), []])
                if _res_v == "결과 대기": _m[1].append(_ri)
            except Exception: continue
        for gid in pend:
            try:
                resp = requests.get("https://asia.api.riotgames.com/lol/match/v5/matches/KR_" + gid.lstrip("#"),
                                    headers=hdrs, timeout=10)
                if resp.status_code == 404:
                    _bf_404_counts[gid] = _bf_404_counts.get(gid, 0) + 1
                    if _bf_404_counts[gid] >= 6:   # 6주기(약 90분) 연속 404 = 진행중 게임이 아니라 진짜 미보관
                        _bf_skip_gids.add(gid)
                        print(f"[backfill] {gid} 리엇 미보관(404×{_bf_404_counts[gid]}) → 영구 스킵", flush=True)
                        # 🧹 [2026-08-11 주간감사 반영] 7일 넘게 '결과 대기'로 남은 미보관 판은 영영 못 채운다.
                        #    그대로 두면 시트에 유령 행이 쌓이고 매주 감사에 같은 항목이 계속 뜬다 → '무효'로 마감.
                        try:
                            _md, _mrows = _pend_meta.get(gid, ["", []])
                            _age = now - time.mktime(time.strptime(_md, "%Y-%m-%d %H:%M"))
                            if _mrows and _age > 7 * 86400:
                                ws.update_cells([gspread.Cell(row=_r, col=c_res + 1, value="무효") for _r in _mrows])
                                print(f"[backfill] 🧹 {gid} 7일 초과 미보관 — {len(_mrows)}행 '무효' 마감", flush=True)
                        except Exception as _ce:
                            print(f"[backfill] 마감 실패(무시): {type(_ce).__name__}", flush=True)
                    continue
                if resp.status_code == 429:
                    try: time.sleep(min(int(resp.headers.get("Retry-After", "10") or 10), 120))
                    except Exception: time.sleep(10)
                    return   # [적대적리뷰 반영] 탭 break가 아니라 주기 전체 중단(다음 탭 재요청으로 Retry-After 위반 방지)
                if resp.status_code != 200: continue
                info = (resp.json() or {}).get("info") or {}
                win_by_team = {tm.get("teamId"): bool(tm.get("win")) for tm in info.get("teams", [])}
                if 100 not in win_by_team and 200 not in win_by_team: continue
                # 참가자 KDA 매칭 맵: ①소환사명(롤닉#태그, tnorm) ②(진영, 포지션) 폴백
                kda_by_name, kda_by_pos = {}, {}
                ext_by_name, ext_by_pos = {}, {}   # 🛒 (아이템, 주룬, 보조룬)
                for p in info.get("participants", []):
                    _k = "{}/{}/{}".format(p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0))
                    _it = "|".join(str(p.get(f"item{_n}") or "") for _n in range(7) if p.get(f"item{_n}"))
                    try:
                        _sty = (p.get("perks") or {}).get("styles") or []
                        _ks = ((_sty[0].get("selections") or [{}])[0].get("perk")) if _sty else None
                        _p1 = _sty[0].get("style") if _sty else None
                        _p2 = _sty[1].get("style") if len(_sty) > 1 else None
                    except Exception: _ks = _p1 = _p2 = None
                    _s1 = p.get("summoner1Id"); _s2 = p.get("summoner2Id")   # 🔮 [v81.73] 스펠 숫자ID(4=점멸 등) → 웹이 ddragon key로 매핑
                    _sp = f"{_s1}|{_s2}" if (_s1 and _s2) else ""
                    _ext = (_it, f"{_ks}|{_p1}" if (_ks and _p1) else "", str(_p2) if _p2 else "", _sp)
                    _rn = str(p.get("riotIdGameName") or "").strip()
                    _rt = str(p.get("riotIdTagline") or "").strip()
                    if _rn:
                        kda_by_name[tnorm(_rn + ("#" + _rt if _rt else ""))] = _k
                        ext_by_name[tnorm(_rn + ("#" + _rt if _rt else ""))] = _ext
                    _sd = "블루팀" if p.get("teamId") == 100 else "레드팀"
                    _ps = _BF_POS_KOR.get(str(p.get("teamPosition") or "").upper())
                    if _ps:
                        kda_by_pos[(_sd, _ps)] = _k
                        ext_by_pos[(_sd, _ps)] = _ext
                # 🏅 [v82.48] 매치평가(MVP/ACE/역적) 소급 계산 — 실패해도 무해(빈 dict)
                _bf_evals = _bf_compute_evals(info, is_aram=(tab == "KIWI_KIWI"))
                # ② 쓰기 직전 서비스계정 재독(행번호 정확성 — gviz 스캔 뒤 행 추가/수동편집 대비)
                live = ws.get_all_values()
                cells = []
                for r_i, lr in enumerate(live[1:], start=2):
                    if len(lr) <= max(c_gid, c_res, c_side): continue
                    if str(lr[c_gid]).strip() != gid: continue
                    _lres = str(lr[c_res]).strip()
                    _leval = str(lr[c_eval]).strip() if (c_eval >= 0 and len(lr) > c_eval) else ""
                    _eval_only = (_lres in ("승리", "패배")) and (_leval == "평가 없음")   # 🏅 평가만 소급하는 행
                    if _lres != "결과 대기" and not _eval_only: continue
                    side = str(lr[c_side]).strip()
                    tid = 100 if side == "블루팀" else (200 if side == "레드팀" else None)
                    if tid is None: continue
                    if not _eval_only:
                        cells.append(gspread.Cell(row=r_i, col=c_res + 1, value="승리" if win_by_team.get(tid) else "패배"))
                    if c_kda >= 0 and len(lr) > c_kda and str(lr[c_kda]).strip() == "기록 대기":
                        _k = kda_by_name.get(tnorm(str(lr[c_name]).strip())) if (c_name >= 0 and len(lr) > c_name) else None
                        if not _k and c_pos >= 0 and len(lr) > c_pos:
                            _k = kda_by_pos.get((side, str(lr[c_pos]).strip()))
                        if _k: cells.append(gspread.Cell(row=r_i, col=c_kda + 1, value=_k))
                    if c_eval >= 0 and len(lr) > c_eval and str(lr[c_eval]).strip() in ("평가 대기", "평가 없음"):
                        # 🏅 [v82.48 사장님 지시] 매치평가 소급 — Match-V5 participants는 EOG와 필드 호환이라
                        #    (kills/deaths/assists·딜·받은딜·힐·시야·CS·포탑·오브젝트딜·teamPosition 전부 존재)
                        #    동일한 parse_endgame_achievements 산식으로 MVP/ACE/역적을 그대로 계산할 수 있다.
                        #    (예전 '소급 불가' 주석은 사실과 달랐음.) 계산 실패 시에만 기존대로 '평가 없음'.
                        _ev = _bf_eval_for_row(_bf_evals, side, str(lr[c_pos]).strip() if (c_pos >= 0 and len(lr) > c_pos) else "",
                                               str(lr[c_name]).strip() if (c_name >= 0 and len(lr) > c_name) else "")
                        if _ev or not _eval_only:   # 평가만 소급하는 행은 계산 성공했을 때만 기록(불필요한 재기록 방지)
                            cells.append(gspread.Cell(row=r_i, col=c_eval + 1, value=_ev or "평가 없음"))
                    # 🛒 [v81.70] 아이템·룬 소급(열이 있고 미기록일 때만)
                    _ex = (ext_by_name.get(tnorm(str(lr[c_name]).strip())) if (c_name >= 0 and len(lr) > c_name) else None) \
                          or (ext_by_pos.get((side, str(lr[c_pos]).strip())) if (c_pos >= 0 and len(lr) > c_pos) else None)
                    if _ex:
                        if c_item >= 0 and (len(lr) <= c_item or str(lr[c_item]).strip() in ("", "기록 대기")):
                            cells.append(gspread.Cell(row=r_i, col=c_item + 1, value=_ex[0]))
                        if c_rune1 >= 0 and _ex[1] and (len(lr) <= c_rune1 or not str(lr[c_rune1]).strip()):
                            cells.append(gspread.Cell(row=r_i, col=c_rune1 + 1, value=_ex[1]))
                        if c_rune2 >= 0 and _ex[2] and (len(lr) <= c_rune2 or not str(lr[c_rune2]).strip()):
                            cells.append(gspread.Cell(row=r_i, col=c_rune2 + 1, value=_ex[2]))
                        if c_spell >= 0 and len(_ex) > 3 and _ex[3] and (len(lr) <= c_spell or not str(lr[c_spell]).strip()):
                            cells.append(gspread.Cell(row=r_i, col=c_spell + 1, value=_ex[3]))
                if cells:
                    ws.update_cells(cells)
                    print(f"[backfill] ✅ {tab} {gid} 결과 백필 완료({len(cells)}셀)", flush=True)
                    # 🏆 [v81.67 사장님 지시] 백필 시 디스코드 결과 리포트도 발송 — 종료신호 유실 게임이 시트만 조용히
                    #    마감되고 #내전결과리포트에 아무것도 안 남던 구멍 보완. ⚠️ 봇 종료 트리거 어구('경기 종료',
                    #    '매치 결과 리포트')는 금지 — 다음 판이 이미 진행 중일 때 뒷북 종료처리로 진행판이 꼬임.
                    try:
                        _bw = win_by_team.get(100)
                        _bl, _rl, _dt = [], [], ""
                        for lr in live[1:]:
                            if len(lr) <= max(c_gid, c_side) or str(lr[c_gid]).strip() != gid: continue
                            if not _dt and c_date >= 0 and len(lr) > c_date: _dt = str(lr[c_date]).strip()
                            _nm = str(lr[c_name]).strip().split("#")[0] if (c_name >= 0 and len(lr) > c_name) else "?"
                            _kv = str(lr[c_kda]).strip() if (c_kda >= 0 and len(lr) > c_kda) else ""
                            _cell = _nm + (f" ({_kv})" if _kv and "대기" not in _kv else "")
                            (_bl if str(lr[c_side]).strip() == "블루팀" else _rl).append(_cell)
                        _msg = ("🏆 **[스쿼드 내전 결과 — 자동 복구]** 🏆  " + (f"🕐 {_dt} 판" if _dt else "") + chr(10)
                                + ("🟦 **블루 승리!**" if _bw else "🟥 **레드 승리!**") + chr(10)
                                + "🟦 " + ", ".join(_bl) + chr(10)
                                + "🟥 " + ", ".join(_rl) + chr(10)
                                + "-# 종료 신호가 유실된 게임을 리엇 공식 기록으로 자동 복구했어요 (매치평가 없음)")
                        broadcast_plain_webhook(_msg)
                    except Exception as _re:
                        print(f"[backfill] 리포트 발송 실패(무시): {_re}", flush=True)
            except Exception as _be:
                print(f"[backfill] {gid} 실패(다음 주기 재시도): {type(_be).__name__} {str(_be)[:100]}", flush=True)
            time.sleep(1.3)   # rate limit(개인키 여유)


def _bf_compute_evals(info, is_aram=False):
    """[v82.48] Match-V5 info → {"puuid": "MVP"/"ACE"/"역적", ("진영","포지션"): ...} 평가 맵.
       종료신호 유실 게임(백필)도 라이브와 동일한 산식으로 매치평가를 채우기 위해
       parse_endgame_achievements를 그대로 재사용한다(EOG와 필드 호환)."""
    out = {}
    try:
        md = {"gameDuration": info.get("gameDuration", 0),
              "teams": [{"teamId": t.get("teamId"), "win": bool(t.get("win"))} for t in (info.get("teams") or [])],
              "participants": list(info.get("participants") or [])}
        if not md["participants"]: return out
        _, mvp_pu, mvp_cid, mvp_tid, ace_pu, ace_cid, ace_tid, tr_pu, tr_cid, tr_tid, *_rest = \
            parse_endgame_achievements(md, {}, {}, [], [], is_aram=is_aram)
        _sd = lambda t: "블루팀" if t == 100 else ("레드팀" if t == 200 else "")
        for pu, cid, tid, label in ((mvp_pu, mvp_cid, mvp_tid, "MVP"),
                                    (ace_pu, ace_cid, ace_tid, "ACE"),
                                    (tr_pu, tr_cid, tr_tid, "역적")):
            if not label: continue
            _p = str(pu or "").strip().lower()
            if _p and not _p.startswith(("bot_", "temp")): out[_p] = label
            _pos = None
            for q in md["participants"]:
                if str(q.get("puuid", "")).strip().lower() == _p:
                    _pos = _BF_POS_KOR.get(str(q.get("teamPosition") or "").upper()); break
            if _pos and _sd(tid): out[(_sd(tid), _pos)] = label
    except Exception as _e:
        print(f"[backfill] 매치평가 소급 생략: {type(_e).__name__}", flush=True)
    return out

def _bf_eval_for_row(evals, side, pos, name):
    """행(진영·포지션·소환사명) → 평가 라벨. 매칭 실패 시 None(호출부가 '평가 없음' 폴백)."""
    if not evals: return None
    try:
        if side and pos and (side, pos) in evals: return evals[(side, pos)]
    except Exception: pass
    return None

# 🏟 [2026-08-02 사장님 지시] 미니토너먼트 전적 분리
#   미토도 일반 내전도 deeplol.gg 제휴 토너먼트코드로 방을 판다(코드 유무로는 구분 불가).
#   그래서 여기서는 게임ID → 코드 매핑만 MITO_GAMES 탭에 적재하고, "어떤 코드가 미토인지"는
#   웹이 MITO_CODES 탭(사장님이 회차별로 등록)과 대조해 가른다.
#   · 코드를 못 얻은 게임도 빈 값으로 기록한다 → 매 주기 재조회하는 무한루프 방지.
#   · 한 주기 40게임으로 제한(레이트리밋 여유). 과거분은 몇 시간에 걸쳐 저절로 다 채워진다.
_MITO_SCAN_PER_CYCLE = 40

def sync_mito_games():
    """CLASSIC_NORMAL·KIWI_KIWI 의 게임ID를 Match-V5로 조회해 토너먼트코드를 MITO_GAMES 탭에 적재."""
    key = load_riot_key()
    if not key or not global_spreadsheet: return
    hdrs = {"X-Riot-Token": key}
    try:
        try:
            ws = global_spreadsheet.worksheet("MITO_GAMES")
        except Exception:
            ws = global_spreadsheet.add_worksheet(title="MITO_GAMES", rows="4000", cols="3")
            ws.append_row(["게임ID", "날짜", "토너먼트코드"])
        known = set()
        try:
            for r in (get_sheet_data_cached(ws, force=True) or [])[1:]:
                if r and str(r[0]).strip(): known.add(str(r[0]).strip())
        except Exception: pass
    except Exception as _e:
        print(f"[mito] MITO_GAMES 준비 실패: {type(_e).__name__}", flush=True); return

    # 아직 조회 안 한 게임ID를 최신순으로 수집(오늘 미토가 가장 먼저 채워지도록)
    todo = {}
    for tab in ("CLASSIC_NORMAL", "KIWI_KIWI"):
        try:
            rows = get_sheet_data_cached(global_spreadsheet.worksheet(tab), force=True)
        except Exception: continue
        if not rows or len(rows) < 2: continue
        hd = rows[0]
        if "게임ID" not in hd or "날짜" not in hd: continue
        cg, cd = hd.index("게임ID"), hd.index("날짜")
        for r in rows[1:]:
            try:
                gid = str(r[cg]).strip()
                if not re.fullmatch(r"#\d+", gid) or gid in known or gid in _bf_skip_gids: continue
                todo[gid] = str(r[cd]).strip()
            except Exception: continue
    if not todo: return
    picks = sorted(todo.items(), key=lambda kv: kv[1], reverse=True)[:_MITO_SCAN_PER_CYCLE]

    # 🏟 [2026-08-10 사장님 제보: 미토 웹 표기 이상] 게임 종료 직후엔 Match-V5가 아직 색인 전이라
    #    404가 나는데, 이를 '영구 미보관'으로 오판해 빈 코드로 봉인 → 어제 미토가 통째로 누락됐다.
    #    24시간 안 된 게임은 404/빈코드를 기록하지 않고 다음 주기에 재조회한다.
    def _fresh(date_s):
        try:
            return (time.time() - time.mktime(time.strptime(str(date_s)[:16], "%Y-%m-%d %H:%M"))) < 24 * 3600
        except Exception:
            return False
    new_rows, found = [], 0
    for gid, date_s in picks:
        try:
            resp = requests.get("https://asia.api.riotgames.com/lol/match/v5/matches/KR_" + gid.lstrip("#"),
                                headers=hdrs, timeout=10)
            if resp.status_code == 429:
                try: time.sleep(min(int(resp.headers.get("Retry-After", "10") or 10), 120))
                except Exception: time.sleep(10)
                break                      # 이번 주기는 여기까지 — 다음 주기에 이어서
            if resp.status_code == 404:
                if _fresh(date_s): continue          # 색인 전일 수 있음 — 다음 주기 재조회
                new_rows.append([gid, date_s, ""])   # 하루 지나도 404 = 진짜 미보관 → 영구 제외
                continue
            if resp.status_code != 200: continue
            code = str(((resp.json() or {}).get("info") or {}).get("tournamentCode") or "").strip()
            if not code and _fresh(date_s): continue   # 갓 끝난 판의 빈 코드도 보류(색인 지연 의심)
            new_rows.append([gid, date_s, code])
            if code:
                found += 1
                print(f"[mito] 토너먼트 게임 발견: {gid} {date_s} {code}", flush=True)
        except Exception:
            continue
        time.sleep(0.15)                   # 레이트리밋 여유
    if new_rows:
        try:
            ws.append_rows(new_rows)
            print(f"[mito] {len(new_rows)}게임 기록(토너먼트 {found}건) · 남은 미조회 {len(todo)-len(new_rows)}", flush=True)
        except Exception as _e:
            print(f"[mito] 기록 실패: {type(_e).__name__}", flush=True)

def backfill_result_engine():
    """시작 3분 후 + 15분마다 '결과 대기' 백필(키/시트 없으면 no-op) — 실질 호스트 1대만 가동, 쓰기 멱등이라 중복 무해."""
    time.sleep(180)
    while True:
        try:
            if load_riot_key() and global_spreadsheet: backfill_pending_results()
        except Exception as _e:
            print(f"[backfill] 주기 실패(무시): {type(_e).__name__} {str(_e)[:120]}", flush=True)
        try:
            sync_mito_games()
        except Exception as _e:
            print(f"[mito] 주기 실패(무시): {type(_e).__name__} {str(_e)[:120]}", flush=True)
        time.sleep(900)

_PEAK_SEASONS_CACHE = None   # {tnorm(닉네임): peak점수} — 세션 1회 로드(시즌 중 불변)

def _load_solo_ranks():
    """SOLO_RANK 시트 → {tnorm(닉네임): {score, wins, losses, wr, cur}}. score=(현시즌+과거3시즌최고)/2 블렌드."""
    out = {}
    ok = False
    try:
        if not global_spreadsheet: return out
        ws = global_spreadsheet.worksheet("SOLO_RANK")
        rows = ws.get_all_values()
        if not rows or len(rows) < 2: return out
        h = rows[0]
        ni = h.index("닉네임") if "닉네임" in h else 0
        si = h.index("점수") if "점수" in h else -1
        wi = h.index("솔랭승") if "솔랭승" in h else -1
        li = h.index("솔랭패") if "솔랭패" in h else -1
        for r in rows[1:]:
            if si < 0 or len(r) <= si: continue
            nmk = tnorm(r[ni])
            try: sc = float(r[si])
            except Exception: continue
            try: w, l = int(r[wi]), int(r[li])
            except Exception: w = l = 0
            if nmk: out[nmk] = {"score": sc, "wins": w, "losses": l, "wr": (w/(w+l)*100) if (w+l) else None}
        # 🛡️ [v82.49 사장님 제보] '헤더 + 빈 행만 남은 시트'는 len(rows)>=2라 예전엔 정상 읽기로 통과했다.
        #    그 결과 solo 점수가 PEAK_SEASONS 있는 사람에게만 생겨, 십이귀월이 반쪽 명단으로 재편되고
        #    (PEAK 없는 신규 클랜원이 통째로 누락) 웹과 결과가 어긋났다. 유효 행 0건 = 실패로 간주.
        ok = bool(out)
        if not out:
            print("[solo] SOLO_RANK 유효 데이터 0건 — 십이귀월/티어평가 계산 보류(시트 복구 대기)", flush=True)
    except Exception: pass
    # ★ (v81.40) 과거 3시즌 최고티어 블렌드 — 솔랭점수 = (최근3시즌 최고 + 현시즌)/2 (2026-07-03 사장님 지시)
    #    ⚠️ SOLO_RANK 읽기 성공 시에만 블렌드 — 429 등 일시 실패 사이클에 peak-only로 점수가 널뛰어
    #    십이귀월 거짓 재편 웹훅이 발사되는 것을 방지(리뷰 확인 결함). 실패 시 {}=이전과 동일한 안전 동작.
    if not ok: return {}
    global _PEAK_SEASONS_CACHE
    try:
        if _PEAK_SEASONS_CACHE is None:   # 시즌 중 불변 데이터 → 세션 1회만 조회(UI 프리징 최소화, 실패 시 다음 호출 재시도)
            import csv as _csv, io as _io
            prows = list(_csv.reader(_io.StringIO(_fetch_public_csv(DOCUMENT_ID, sheet="PEAK_SEASONS", headers=1, timeout=8))))
            cache = {}
            if prows and "닉네임" in prows[0]:
                hh = prows[0]; ni2 = hh.index("닉네임"); pi = hh.index("점수") if "점수" in hh else -1
                if pi >= 0:
                    for r in prows[1:]:
                        if len(r) <= max(ni2, pi) or not r[ni2].strip(): continue
                        try: pk = float(r[pi])
                        except Exception: continue
                        k = tnorm(r[ni2])
                        if k not in cache: cache[k] = pk   # 중복행은 첫 값만(이중 평균 방지)
            _PEAK_SEASONS_CACHE = cache
        for k, pk in _PEAK_SEASONS_CACHE.items():
            if k in out:
                cur = out[k]["score"]
                out[k]["score"] = (cur + pk) / 2.0
                out[k]["cur"] = cur                       # 현시즌 원값 보존(뱃지 등 현시즌 판단용)
            else:
                out[k] = {"score": pk, "wins": 0, "losses": 0, "wr": None, "cur": None}   # 과거만 보유(솔랭 쉬는 클랜원)
    except Exception: pass
    # 🔗 [v82.50 사장님 제보 — 귤갓 십이귀월 누락] 부계정 통합(LINK_ACCOUNT) 반영.
    #    웹(index.html)은 SOLO_RANK 조회 시 LINK_ACCOUNT 별칭 후보까지 훑어 본계·부계 중 데이터가 있는 쪽을 쓰는데,
    #    분석기는 PUUID 닉변 별칭만 봐서 '계정 이전 통합' 케이스(예: 귤 갓 ← 귤갓입니다)의 솔랭·PEAK를 못 찾았다.
    #    → 웹과 같은 판단이 되도록, 통합 그룹 안에서 현시즌 데이터가 있는 엔트리를 그룹 전원에게 공유한다.
    try:
        groups = {}
        for _sub, _main in (global_alt_map or {}).items():
            g = groups.setdefault(tnorm(_main), {tnorm(_main)})
            g.add(tnorm(_sub))
        for _mk, keys in groups.items():
            cands = [out[k] for k in keys if k in out]
            if not cands: continue
            # 현시즌 전적(승+패)이 있는 엔트리 우선 → 없으면 점수 최고값
            best = max(cands, key=lambda d: ((d.get("wins", 0) + d.get("losses", 0)) > 0, d.get("score") or -1e9))
            for k in keys:
                if out.get(k) is not best: out[k] = dict(best)
    except Exception: pass
    return out

def save_prev_seasons():
    """이번 세션 캡처한 직전시즌을 PREV_SEASON 시트에 upsert(이름 기준, 더 높은 점수만 유지). clear 안 해서 누적됨."""
    if not global_spreadsheet or not _PREV_SEASON_CACHE: return
    try:
        try: ws = global_spreadsheet.worksheet("PREV_SEASON")
        except Exception:
            ws = global_spreadsheet.add_worksheet(title="PREV_SEASON", rows="400", cols="4")
            ws.update([["닉네임", "직전티어", "점수", "갱신"]])
        rows = ws.get_all_values()
        existing = {}
        for i, r in enumerate(rows[1:], start=2):
            if r and r[0]: existing[tnorm(r[0])] = (i, r)
        cells, appends = [], []
        stamp = time.strftime("%Y-%m-%d %H:%M")
        for k, (nm, pt, sc) in list(_PREV_SEASON_CACHE.items()):
            if k in existing:
                ri, r = existing[k]
                try: old = float(str(r[2]).strip()) if len(r) > 2 and str(r[2]).strip() else -1
                except Exception: old = -1
                if sc > old:
                    cells += [gspread.Cell(ri, 2, pt), gspread.Cell(ri, 3, sc), gspread.Cell(ri, 4, stamp)]
            else:
                appends.append([nm, pt, sc, stamp])
        if cells: ws.update_cells(cells)
        for a in appends: ws.append_row(a)
    except Exception: pass

def _load_prev_seasons():
    """PREV_SEASON 시트 → {tnorm(닉네임): score}. 없으면 {}."""
    out = {}
    try:
        if not global_spreadsheet: return out
        ws = global_spreadsheet.worksheet("PREV_SEASON")
        rows = ws.get_all_values()
        if not rows or len(rows) < 2: return out
        h = rows[0]
        ni = h.index("닉네임") if "닉네임" in h else 0
        si = h.index("점수") if "점수" in h else 2
        for r in rows[1:]:
            if len(r) > max(ni, si) and r[ni]:
                try: out[tnorm(r[ni])] = float(str(r[si]).strip())
                except Exception: pass
    except Exception: pass
    return out

# 평가 기준 (웹 squad.gg와 동일) — 신뢰도 강화: 베이지안 shrinkage + leave-one-out + z표준화 + AI점수 평균 + 솔랭
TIER_MIN_GAMES = 10            # 평가 최소 표본
TIER_MIN_EVAL = 5             # MVP/역적율 인정 최소 평가판
SHRINK_WR = 10               # 승률 shrinkage 강도(판수 등가) — 표본 적으면 평균으로 끌어당김
SHRINK_AI = 10               # AI점수 shrinkage 강도
SHRINK_EVAL = 5              # MVP/역적율 shrinkage 강도
ASSESS_Z = 0.85              # 고/저평가 임계(동티어 대비 z-합성점수)
# 합성 가중치 — 솔랭(객관 외부 실력) 최대, AI점수(내부 퍼포먼스) 다음. 솔랭 데이터 없으면 자동 재정규화.
W_SOLO, W_AI, W_WR, W_SOLOWR, W_MVP, W_TROLL = 0.35, 0.20, 0.15, 0.10, 0.10, 0.10  # [V81.26] 역적이 드물어진 만큼 역적율 가중 0.05→0.10(MVP와 동급)
SHRINK_SOLOWR = 20           # 솔랭 승률 shrinkage(솔랭은 판수 많아 강하게 안 당겨도 됨)

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
def _std(xs, mu):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2 or mu is None: return None
    return (sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5

def _player_metrics_from_stat(s):
    a = s.get("ALL", {})
    g = a.get("total", 0); w = a.get("wins", 0)
    et = a.get("eval_total", 0); mvp = a.get("mvp", 0); troll = a.get("troll", 0); ace = a.get("ace", 0)
    ai_sum = a.get("ai_sum", 0.0); ai_n = a.get("ai_n", 0)
    return {
        "games": g, "wins": w, "eval": et, "mvp": mvp, "troll": troll, "ace": ace, "ai_sum": ai_sum, "ai_n": ai_n,
        "wr": (w / g * 100) if g else None,
        "mvpRate": ((mvp + 0.5 * ace) / et * 100) if et else None,   # ACE는 MVP의 절반 가중으로 긍정 반영
        "trollRate": (troll / et * 100) if et else None,
        "aceRate": (ace / (g - w) * 100) if (g - w) > 0 else None,    # ACE획득률 = ACE ÷ 패배수(진 판에서만 %)
        "avgAI": (ai_sum / ai_n) if ai_n else None,
        "recent30": a.get("recent30", 0),   # [v82.27] 최근 30일 판수(십이귀월 활동 조건)
    }

def compute_tier_assessment():
    """동티어 평균 대비 고/저평가 판정 — 신뢰도 강화판.
    (1)베이지안 shrinkage로 소표본 노이즈 억제 (2)본인 제외 leave-one-out 평균
    (3)지표별 z-표준화로 스케일 통일 (4)AI 종합점수 평균 도입(가장 조밀한 신호).
    반환: (assessments[list], tier_avg[dict])"""
    with gui_lock:
        _hofc = gui_data.get("hof_classic", {})
        gstats = _hofc.get("global_stats", {}).get("전체 (ALL)", {})
        aliases = _hofc.get("aliases", {})
    solo = _load_solo_ranks()                    # {puuid: {score, wins, losses, wr}} (없으면 {})
    # [v81.31 보류] 직전시즌 블렌드 중단 — 현재시즌 점수만 사용(v81.28 이전과 동일). 사유는 위 캡처부 주석 참고.
    members = []  # (tier, name, metrics)
    for _pk, s in gstats.items():
        nm = s.get("name", "")
        t = tier_of(nm)
        if not t:
            for _al in aliases.get(_pk, ()):     # 닉변 시 과거 닉으로 티어 복원
                t = tier_of(_al)
                if t: break
        if not t: continue
        m = _player_metrics_from_stat(s)
        # 닉변 대응: 현재닉+과거닉 후보 중 '현시즌 데이터 보유'(wr 있음) 엔트리 우선
        # (peak-only 엔트리가 현재닉에 걸려 과거닉의 실제 현시즌 기록을 가리는 것 방지 — 리뷰 확인 결함)
        _cands = [solo.get(tnorm(nm))] + [solo.get(tnorm(_al)) for _al in aliases.get(_pk, ())]
        _cands = [c for c in _cands if c]
        sr = next((c for c in _cands if c.get("wr") is not None), _cands[0] if _cands else None)
        m["soloScore"] = sr.get("score") if sr else None
        m["soloWR"] = sr.get("wr") if sr else None
        m["soloW"] = sr.get("wins", 0) if sr else 0
        m["soloL"] = sr.get("losses", 0) if sr else 0
        members.append((t, nm, m))

    elig = [(t, nm, m) for (t, nm, m) in members if m["games"] >= TIER_MIN_GAMES]
    # 전체 사전평균(shrinkage prior)
    g_wr  = _mean([m["wr"] for _, _, m in elig]) or 50.0
    g_ai  = _mean([m["avgAI"] for _, _, m in elig if m["avgAI"] is not None]) or 0.0
    g_mvp = _mean([m["mvpRate"] for _, _, m in elig if m["eval"] >= TIER_MIN_EVAL]) or 10.0
    g_tr  = _mean([m["trollRate"] for _, _, m in elig if m["eval"] >= TIER_MIN_EVAL]) or 10.0
    g_solowr = _mean([m["soloWR"] for _, _, m in elig if m["soloWR"] is not None]) or 50.0

    def shrunk(m):
        wr = (m["wins"] + SHRINK_WR * (g_wr / 100.0)) / (m["games"] + SHRINK_WR) * 100.0
        ai = ((m["ai_sum"] + SHRINK_AI * g_ai) / (m["ai_n"] + SHRINK_AI)) if m["ai_n"] > 0 else None
        if m["eval"] >= TIER_MIN_EVAL:
            mvp = (m["mvp"] + SHRINK_EVAL * (g_mvp / 100.0)) / (m["eval"] + SHRINK_EVAL) * 100.0
            tr  = (m["troll"] + SHRINK_EVAL * (g_tr / 100.0)) / (m["eval"] + SHRINK_EVAL) * 100.0
        else:
            mvp = tr = None
        ss = m["soloScore"]                       # 솔랭 점수는 많은 판수 기반 안정값 → 원값 사용
        if m["soloWR"] is not None:
            swr = (m["soloW"] + SHRINK_SOLOWR * (g_solowr / 100.0)) / (m["soloW"] + m["soloL"] + SHRINK_SOLOWR) * 100.0
        else:
            swr = None
        return {"wr": wr, "ai": ai, "mvp": mvp, "tr": tr, "solo": ss, "solowr": swr}

    sh = {id(m): shrunk(m) for _, _, m in elig}
    by_tier = {}
    for t, nm, m in elig:
        by_tier.setdefault(t, []).append(m)
    # 티어 표본 부족 시 폴백용 global std
    def _col(k): return [sh[id(m)][k] for _, _, m in elig]
    G_STD = {k: (_std(_col(k), _mean(_col(k))) or 1.0) for k in ("wr", "ai", "mvp", "tr", "solo", "solowr")}

    tier_avg = {}
    for t, ms in by_tier.items():
        tier_avg[t] = {
            "wr": _mean([sh[id(m)]["wr"] for m in ms]),
            "ai": _mean([sh[id(m)]["ai"] for m in ms]),
            "mvp": _mean([sh[id(m)]["mvp"] for m in ms]),
            "troll": _mean([sh[id(m)]["tr"] for m in ms]),
            "solo": _mean([sh[id(m)]["solo"] for m in ms]),
            "solowr": _mean([sh[id(m)]["solowr"] for m in ms]),
            "n": len(ms),
        }

    out = []
    for t, nm, m in members:
        if m["games"] < TIER_MIN_GAMES:
            out.append({"name": nm, "tier": t, "label": "표본부족", "games": m["games"], "detail": None}); continue
        peers = [x for x in by_tier.get(t, []) if x is not m]    # leave-one-out
        s_me = sh[id(m)]
        def z(metric, gkey):
            me = s_me[metric]
            if me is None: return None
            vals = [sh[id(x)][metric] for x in peers if sh[id(x)][metric] is not None]
            mu = _mean(vals)
            if mu is None: return 0.0                # 동티어 비교군 없음 → 중립
            sd = _std(vals, mu) or 0.0
            sd = max(sd, 0.6 * G_STD[gkey])           # 소티어(표본 2~3명) std가 작아 z 폭주하는 것 방지(전체분포 하한)
            return (me - mu) / sd
        z_wr, z_ai, z_mvp, z_tr = z("wr","wr"), z("ai","ai"), z("mvp","mvp"), z("tr","tr")
        z_solo, z_solowr = z("solo","solo"), z("solowr","solowr")
        terms = []
        if z_solo   is not None: terms.append((W_SOLO, z_solo))     # 솔랭 점수(객관 외부 실력) = 최대 가중
        if z_ai     is not None: terms.append((W_AI, z_ai))
        if z_wr     is not None: terms.append((W_WR, z_wr))
        if z_solowr is not None: terms.append((W_SOLOWR, z_solowr))
        if z_mvp    is not None: terms.append((W_MVP, z_mvp))
        if z_tr     is not None: terms.append((W_TROLL, -z_tr))     # 역적율↑ = 나쁨 → 부호 반전
        wsum = sum(w for w, _ in terms) or 1.0
        composite = sum(w * zz for w, zz in terms) / wsum          # 가중치 재정규화된 z-합성
        if composite >= ASSESS_Z: label = "저평가"
        elif composite <= -ASSESS_Z: label = "고평가"
        else: label = "적절"
        avg = tier_avg.get(t, {})
        out.append({"name": nm, "tier": t, "label": label, "games": m["games"], "detail": {
            "wr": round(m["wr"]) if m["wr"] is not None else None, "wrAvg": round(avg["wr"]) if avg.get("wr") is not None else None,
            "ai": round(m["avgAI"], 1) if m["avgAI"] is not None else None, "aiAvg": round(avg["ai"], 1) if avg.get("ai") is not None else None,
            "mvp": round(m["mvpRate"]) if m["mvpRate"] is not None else None, "mvpAvg": round(avg["mvp"]) if avg.get("mvp") is not None else None,
            "troll": round(m["trollRate"]) if m["trollRate"] is not None else None, "trollAvg": round(avg["troll"]) if avg.get("troll") is not None else None,
            "ace": round(m["aceRate"]) if m.get("aceRate") is not None else None,
            "solo": round(m["soloScore"]) if m["soloScore"] is not None else None, "soloAvg": round(avg["solo"]) if avg.get("solo") is not None else None,
            "soloWR": round(m["soloWR"]) if m["soloWR"] is not None else None,
            "score": round(composite, 2),
        }})

    # 🗡 상현 파워랭킹: 솔로랭크 보유 + 내전 10판↑(elig) 중 종합 파워점수(전체평균 z, 기존 가중치) top3
    _GM = {k: _mean(_col(k)) for k in ("wr", "ai", "mvp", "tr", "solo", "solowr")}
    def _zg(s_, k):
        v = s_[k]
        if v is None or _GM.get(k) is None: return None
        return (v - _GM[k]) / (G_STD[k] or 1.0)
    _powered = []
    for _t, _nm, _m in elig:
        s_ = sh[id(_m)]
        if s_["solo"] is None: continue
        if _m.get("recent30", 0) < 5: continue   # [v82.27 사장님 지시] 최근 30일 5판↑만 십이귀월 편성(유령 방지)
        _tm = []
        for _w, _zk, _neg in ((W_SOLO,"solo",1),(W_AI,"ai",1),(W_WR,"wr",1),(W_SOLOWR,"solowr",1),(W_MVP,"mvp",1),(W_TROLL,"tr",-1)):
            _z = _zg(s_, _zk)
            if _z is not None: _tm.append((_w, _neg * _z))
        _ws = sum(w for w, _ in _tm) or 1.0
        _powered.append((sum(w * zz for w, zz in _tm) / _ws, (s_["solo"] if s_["solo"] is not None else -1e9), _nm, _t))
    # 파워 내림차순, 동점 시 솔랭↑, 그래도 같으면 이름순(웹과 동일 규칙 → 웹·앱 순위 일관)
    _powered.sort(key=lambda x: (-x[0], -x[1], x[2]))
    # [2026-08-07 사장님 지시 — 동서 구분 삭제] 상현 6 = 0·1티어 리그 상위 6(구 서부 상현),
    # 하현 6 = 2·3티어 리그 상위 6(구 동부 상현 승격). 나머지 하현 폐지 — 웹 index.html과 동일 규칙.
    def _league_of(t): return "서부" if str(t)[:1] in ("0", "1") else "동부"
    _title_by_name = {}
    _west = [x for x in _powered if _league_of(x[3]) == "서부"]
    _east = [x for x in _powered if _league_of(x[3]) == "동부"]
    for _i, (_p, _s, _nm, _t4) in enumerate(_west[:6]): _title_by_name[_nm] = "상현 " + str(_i + 1)
    for _i, (_p, _s, _nm, _t4) in enumerate(_east[:6]): _title_by_name[_nm] = "하현 " + str(_i + 1)
    for o in out:
        _t = _title_by_name.get(o["name"])
        if _t: o["title"] = _t

    # 🎯 평가로직 = 클랜 전체 기준 재배치(웹 index.html과 동일). elig 전원을 전체평균 z 절대파워로 세운 뒤
    # 실제 티어 분포와 같은 칸 수(_slots)에 성적순 재배치 → 추정 티어가 현 티어보다 위=저평가/아래=고평가/같음=적절.
    # (전체를 한 통에 넣되 슬롯 수를 실제 분포에 맞춰 '상위티어=전원저평가' 붕괴 방지 = 사장님 '전체 한 그룹' 관점)
    _TORD = ['0','1上','1中','1下','2上','2中','2下','3上','3中','3下']
    _torder = [t for t in _TORD if t in by_tier] + [t for t in by_tier if t not in _TORD]
    _slots = []
    for _t in _torder:
        for _ in range(len(by_tier[_t])): _slots.append(_t)
    def _tidx(t): return _TORD.index(t) if t in _TORD else 99
    _pa = []
    for _t, _nm, _m in elig:
        s_ = sh[id(_m)]
        _tm = []
        for _w, _zk, _neg in ((W_SOLO,"solo",1),(W_AI,"ai",1),(W_WR,"wr",1),(W_SOLOWR,"solowr",1),(W_MVP,"mvp",1),(W_TROLL,"tr",-1)):
            _z = _zg(s_, _zk)
            if _z is not None: _tm.append((_w, _neg * _z))
        _ws = sum(w for w, _ in _tm) or 1.0
        _pa.append((sum(w * zz for w, zz in _tm) / _ws, _nm, _t))
    _pa.sort(key=lambda x: (-x[0], x[1]))
    _N = len(_pa) or 1
    _impl = {}
    for _i, (_p, _nm, _t) in enumerate(_pa):
        _it = _slots[_i] if _i < len(_slots) else _t
        _di = _tidx(_t) - _tidx(_it)
        # ±1등급(약 0.5티어) 이내 = 적절, 2등급 이상 벌어질 때만 저/고평가
        _lab = "저평가" if _di >= 2 else ("고평가" if _di <= -2 else "적절")
        _impl[_nm] = (_it, max(1, round((_i + 1) / _N * 100.0)), _lab)
    for o in out:
        _info = _impl.get(o["name"])
        if _info and o.get("detail") is not None:
            o["implTier"], o["implPct"], o["label"] = _info[0], _info[1], _info[2]

    return out, tier_avg

# ===== 🩸 십이귀월(상현/하현) 로스터 변동 → 자동내전기록 채널 웹훅 (호스트만) =====
def _sibguiwol_roster(league=""):
    """[v82.26] league='서부'/'동부' — 해당 리그 상현1~6·하현1~6 순서 리스트(12개, 빈칸 가능). 없으면 None."""
    try:
        assessments, _ = compute_tier_assessment()
    except Exception:
        return None
    by_title = {}
    for a in assessments:
        _t = a.get("title")
        if _t: by_title[_t] = str(a.get("name", ""))
    _pre = (league + " ") if league else ""
    seq = [by_title.get(f"{_pre}상현 {i}", "") for i in range(1, 7)] + [by_title.get(f"{_pre}하현 {i}", "") for i in range(1, 7)]
    return seq if any(seq) else None

def _sibguiwol_aram_roster():
    """칼바람(KIWI) 파워랭킹 top12 — 웹 index.html 칼바람 내부티어와 동일 산식(2026-07-20 사장님 결정:
    '솔랭 고티어의 체급도 영향이 분명 존재'). 후보=내부티어 보유+솔랭 보유+칼바람 10판↑,
    지표=칼바람 성적(wr/ai/mvp/tr) + 솔랭점수/솔랭승률, 가중치·타이브레이커 전부 협곡 _powered와 동일."""
    try:
        with gui_lock:
            _hofa = gui_data.get("hof_aram", {})
            gstats = _hofa.get("global_stats", {}).get("전체 (ALL)", {})
            aliases = _hofa.get("aliases", {})
        if not gstats: return None
        solo = _load_solo_ranks()
        ms = []
        for _pk, s in gstats.items():
            nm = s.get("name", "")
            t = tier_of(nm)
            if not t:
                for _al in aliases.get(_pk, ()):
                    t = tier_of(_al)
                    if t: break
            if not t: continue                       # 웹과 동일: 내부티어 보유자만
            m = _player_metrics_from_stat(s)
            if m["games"] < TIER_MIN_GAMES: continue
            _cands = [solo.get(tnorm(nm))] + [solo.get(tnorm(_al)) for _al in aliases.get(_pk, ())]
            _cands = [c for c in _cands if c]
            sr = next((c for c in _cands if c.get("wr") is not None), _cands[0] if _cands else None)
            m["soloScore"] = sr.get("score") if sr else None
            m["soloWR"] = sr.get("wr") if sr else None
            m["soloW"] = sr.get("wins", 0) if sr else 0
            m["soloL"] = sr.get("losses", 0) if sr else 0
            ms.append((nm, m))
        if len(ms) < 2: return None
        g_wr  = _mean([m["wr"] for _, m in ms]) or 50.0
        g_ai  = _mean([m["avgAI"] for _, m in ms if m["avgAI"] is not None]) or 0.0
        g_mvp = _mean([m["mvpRate"] for _, m in ms if m["eval"] >= TIER_MIN_EVAL]) or 10.0
        g_tr  = _mean([m["trollRate"] for _, m in ms if m["eval"] >= TIER_MIN_EVAL]) or 10.0
        g_solowr = _mean([m["soloWR"] for _, m in ms if m["soloWR"] is not None]) or 50.0
        sh = {}
        for nm, m in ms:
            wr = (m["wins"] + SHRINK_WR * (g_wr / 100.0)) / (m["games"] + SHRINK_WR) * 100.0
            ai = ((m["ai_sum"] + SHRINK_AI * g_ai) / (m["ai_n"] + SHRINK_AI)) if m["ai_n"] > 0 else None
            if m["eval"] >= TIER_MIN_EVAL:
                mvp = (m["mvp"] + SHRINK_EVAL * (g_mvp / 100.0)) / (m["eval"] + SHRINK_EVAL) * 100.0
                tr  = (m["troll"] + SHRINK_EVAL * (g_tr / 100.0)) / (m["eval"] + SHRINK_EVAL) * 100.0
            else:
                mvp = tr = None
            if m["soloWR"] is not None:
                swr = (m["soloW"] + SHRINK_SOLOWR * (g_solowr / 100.0)) / (m["soloW"] + m["soloL"] + SHRINK_SOLOWR) * 100.0
            else:
                swr = None
            sh[nm] = {"wr": wr, "ai": ai, "mvp": mvp, "tr": tr, "solo": m["soloScore"], "solowr": swr}
        def _col(k): return [sh[nm][k] for nm, _ in ms]
        GM  = {k: _mean(_col(k)) for k in ("wr", "ai", "mvp", "tr", "solo", "solowr")}
        GSD = {k: (_std(_col(k), GM[k]) or 1.0) for k in ("wr", "ai", "mvp", "tr", "solo", "solowr")}
        ranked = []
        for nm, m in ms:
            if sh[nm]["solo"] is None: continue      # 웹과 동일: 솔랭 보유자만 후보
            if m.get("recent30", 0) < 5: continue    # [v82.27] 최근 30일 5판↑(칼바람도 동일 활동 조건)
            tm = []
            for w, k, neg in ((W_SOLO, "solo", 1), (W_AI, "ai", 1), (W_WR, "wr", 1),
                              (W_SOLOWR, "solowr", 1), (W_MVP, "mvp", 1), (W_TROLL, "tr", -1)):
                v = sh[nm][k]
                if v is None or GM[k] is None: continue
                tm.append((w, neg * (v - GM[k]) / GSD[k]))
            ws = sum(w for w, _ in tm) or 1.0
            ranked.append((sum(w * zz for w, zz in tm) / ws, (sh[nm]["solo"] if sh[nm]["solo"] is not None else -1e9), nm))
        ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
        seq = [nm for _, _, nm in ranked[:12]]
        seq += [""] * (12 - len(seq))
        return seq if any(seq) else None
    except Exception:
        return None

def _post_sibguiwol_webhook(prev, cur, aram=False, league=""):
    # 2026-07-04: 십이귀월 재편 공지를 내전기록 → 내전결과리포트(RESULT) 채널로 이동(사장님 지시)
    if not RESULT_WEBHOOK_URL or RESULT_WEBHOOK_URL.startswith("여기에"): return
    def _nm(x): return str(x).split("#")[0]
    NUM = ["壱", "弐", "参", "肆", "伍", "陸"]
    prev = (list(prev) + [""] * 12)[:12]
    prevset = set(x for x in prev if x); curset = set(x for x in cur if x)
    prev_top = set(x for x in prev[:6] if x); cur_top = set(x for x in cur[:6] if x)
    newcomers = [x for x in cur if x and x not in prevset]
    dropouts  = [x for x in prev if x and x not in curset]
    promoted  = [x for x in cur[:6] if x and x in prevset and x not in prev_top]   # 하현→상현
    demoted   = [x for x in cur[6:] if x and x in prev_top]                          # 상현→하현
    sang = "\n".join(f"`{NUM[i]}`　**{_nm(cur[i])}**" for i in range(6) if cur[i]) or "—"
    haha = "\n".join(f"`{NUM[i]}`　{_nm(cur[6 + i])}" for i in range(6) if cur[6 + i]) or "—"
    ch = []
    if newcomers: ch.append("🆕 **신규 진입** — " + ", ".join(_nm(x) for x in newcomers))
    if dropouts:  ch.append("💀 **이탈** — " + ", ".join(_nm(x) for x in dropouts))
    if promoted:  ch.append("⬆️ **상현 승격** — " + ", ".join(_nm(x) for x in promoted))
    if demoted:   ch.append("⬇️ **하현 강등** — " + ", ".join(_nm(x) for x in demoted))
    # [2026-07-29 사장님 지시] 조 내 순위만 바뀐 경우에도 공지 — 웹 화면과 웹훅 명단을 완전히 일치시킨다.
    if not ch:
        _pi = {x: i for i, x in enumerate(prev) if x}
        _mv = [(x, _pi[x] - i) for i, x in enumerate(cur) if x and x in _pi and _pi[x] != i]
        _mv.sort(key=lambda t: -abs(t[1]))
        if _mv:
            ch.append("🔄 **순위 변동** — " + ", ".join(
                f"{_nm(x)} {'▲' if d > 0 else '▼'}{abs(d)}" for x, d in _mv[:6]))
    if aram:
        desc = "　**칼바람 파워랭킹 최강 12인이 재편성되었다.**\n　_솔로랭크·칼바람 내전성적 종합_\n\n" + ("\n".join(ch) if ch else "순위 변동")
        title, color, content = "❄️　칼바람 십이귀월 ( 十二鬼月 ) 　재편성　❄️", 0x2B6E9B, "❄️❄️　**칼바람 십이귀월이 재편성되었다!**　❄️❄️"
        footer = "스쿼드해체분석기 · 칼바람(KIWI) 파워랭킹 (1~6위 상현 · 7~12위 하현)"
    elif league:   # [v82.26] 서부(0·1티어)/동부(2·3티어) 리그 분할
        _tier_txt = "0·1티어" if league == "서부" else "2·3티어"
        desc = f"　**{league} 리그({_tier_txt}) 파워랭킹 최강 12인이 재편성되었다.**\n　_솔로랭크·AI·내전성적 종합_\n\n" + ("\n".join(ch) if ch else "순위 변동")
        title = f"⚔️　{league} 십이귀월 ( 十二鬼月 ) 　재편성　⚔️"
        color = 0x9B1B1B if league == "서부" else 0x1B4A9B
        content = f"🩸🩸　**{league} 십이귀월이 재편성되었다!**　🩸🩸"
        footer = f"스쿼드해체분석기 · squad.gg 내부티어 {league} 리그({_tier_txt}) — 파워 1~6위 상현 · 7~12위 하현"
    else:
        desc = "　**파워랭킹 최강 12인이 재편성되었다.**\n　_솔로랭크·AI·내전성적 종합_\n\n" + ("\n".join(ch) if ch else "순위 변동")
        title, color, content = "⚔️　십이귀월 ( 十二鬼月 ) 　재편성　⚔️", 0x9B1B1B, "🩸🩸　**십이귀월이 재편성되었다!**　🩸🩸"
        footer = "스쿼드해체분석기 · squad.gg — 상현=0·1티어 상위 6 · 하현=2·3티어 상위 6"
    embed = {
        "title": title,
        "description": desc, "color": color,
        "fields": [
            {"name": "🗡　상현 ( 上弦 )", "value": sang, "inline": True},
            {"name": "🌙　하현 ( 下弦 )", "value": haha, "inline": True},
        ],
        "footer": {"text": footer},
    }
    try:
        requests.post(RESULT_WEBHOOK_URL, json={"content": content, "embeds": [embed]}, timeout=6)
    except Exception: pass

def announce_sibguiwol_if_changed():
    """상현/하현 세트가 바뀌면 웹훅 발송(협곡 + 칼바람 각각). 호스트(token.txt)만. 첫 실행은 기준선만 저장(공지 X)."""
    try:
        if not load_bot_token(): return
        for cfg_key, roster_fn, is_aram, _lg in (
                ("sibguiwol_unified", lambda: _sibguiwol_roster(), False, ""),   # [2026-08-07] 동서 통합 단일 12인
                ("sibguiwol_roster_aram", _sibguiwol_aram_roster, True, "")):
            try:
                cur = roster_fn()
                if not cur: continue
                cfg = load_config()
                prev = cfg.get(cfg_key)
                if prev is None:                   # 최초 = baseline만 저장, 공지 안 함(스팸 방지)
                    cfg[cfg_key] = cur; save_config(cfg); continue
                prev = (list(prev) + [""] * 12)[:12]
                # [2026-07-29 사장님 지시] 순서만 바뀐 경우도 공지 대상 — 세트만 보면 웹과 명단이 어긋나 보인다.
                if list(cur) != list(prev):
                    _post_sibguiwol_webhook(prev, cur, aram=is_aram, league=_lg)
                    cfg[cfg_key] = cur; save_config(cfg)
            except Exception: pass
    except Exception: pass

# ===== 📊 [v81.96] 사전집계 재계산(호스트) — 원본 전량스캔을 '호스트 1대·주기당 1회'로 이동 =====
#   Phase2a: additive(집계 탭 STAT_CHAMP/STAT_PLAYER만 씀, 어떤 읽기경로도 안 바꿈). 소비자 전환은 Phase2b(crunch)·3(웹).
_STAT_LAST_REBUILD = [0.0]
def rebuild_stat_aggregate():
    """CLASSIC_NORMAL(gviz) → STAT_CHAMP(키|소환사명|챔피언|포지션|판수|승) + STAT_PLAYER(종합) 재작성(서비스계정 REST clear+put).
       호스트만(호출부 load_bot_token 게이트=단일 writer). 실패/급감 시 조용히 스킵(집계 없으면 소비자가 원본 폴백)."""
    import urllib.request as _u, csv as _csv, io as _io
    from collections import defaultdict as _dd
    try:
        _url = f"https://docs.google.com/spreadsheets/d/{DOCUMENT_ID}/gviz/tq?tqx=out:csv&gid=1926038351&headers=1"  # CLASSIC_NORMAL
        _rows = list(_csv.reader(_io.StringIO(_u.urlopen(_u.Request(_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read().decode("utf-8"))))
        if not _rows or len(_rows) < 2: return
        _h = _rows[0]; _ci = {c: i for i, c in enumerate(_h)}
        _need = ["게임ID", "소환사명", "PUUID", "진영", "포지션", "챔피언", "결과", "매치평가", "점수"]
        if any(c not in _ci for c in _need): return
        G, NM, PU, SD, PO, CH, RS, EV, SC = [_ci[c] for c in _need]
        BN = _ci.get("밴", -1)   # 약점발견(STAT_BAN)용, 없으면 스킵
        SKIP_BAN = {"밴 없음", "밴 안함", "기록 대기", "결과 대기", "평가 대기", "알수없음", ""}
        _seen = set(); _champ = _dd(lambda: [0, 0]); _disp = {}
        _pl = _dd(lambda: [0, 0, 0, 0, 0, 0.0, 0, 0, 0, 0, 0])   # g,w,mvp,tr,ace,ssum,sn,bg,bw,rg,rw
        _gban = _dd(set)                                        # gid -> {밴 챔프}
        _roster = _dd(lambda: {"블루팀": set(), "레드팀": set(), "win": None})  # gid -> 진영별 pk + 승리진영
        _seq = _dd(list); _seqseen = set()                     # pk -> 결과열(게임dedup, 연승용)
        _pchamps = _dd(set); _pgames = _dd(dict)               # pk -> 챔프풀 / {gid:win} (약점용)
        # 🎯 [v83.4] 포지션별 약점 — 그 사람이 '그 포지션으로 뛴 판'에서만 센다.
        #   STAT_BAN 에 포지션 열을 더하면 안 된다: 읽는 쪽이 BAN[(키,챔프)] = ... 로 '대입'이라
        #   행이 포지션만큼 쪼개지는 순간 마지막 포지션 값만 남아 구버전 클라이언트가 조용히 틀린다.
        #   그래서 별도 탭(STAT_BAN_POS)으로 낸다 — 구버전은 읽지 않으므로 영향이 없다.
        _pchamps_pos = _dd(set); _pgpos = _dd(dict)            # (pk,포지션) -> 챔프풀 / pk -> {gid: 포지션}
        # [v82.5] PUUID 누락 행을 crunch와 동일하게 이름→PUUID 폴백으로 본계 키에 합산(키 분리로 판수 어긋나던 것 수정)
        _name_fb = {}
        for r in _rows[1:]:
            if len(r) <= max(PU, NM): continue
            _pu = str(r[PU]).strip().lower()
            _mn = get_main_name(str(r[NM]).strip())
            if _pu and _mn: _name_fb[_mn] = _pu
        for r in _rows[1:]:
            if len(r) <= max(G, NM, PU, SD, CH, RS): continue
            gid = str(r[G]).strip()
            pk = str(r[PU]).strip().lower() or _name_fb.get(get_main_name(str(r[NM]).strip()), tnorm(r[NM]))
            if not pk: continue
            if BN != -1 and BN < len(r):                       # 게임별 밴 집합(행 반복 무관, set 누적)
                for _b in str(r[BN]).split(","):
                    _b = _b.strip()
                    if _b and _b not in SKIP_BAN: _gban[gid].add(_b)
            pos = str(r[PO]).strip() if PO < len(r) else ""
            sd = str(r[SD]).strip()
            res = str(r[RS]).strip(); win = 1 if res == "승리" else 0; dec = res in ("승리", "패배"); cc = str(r[CH]).strip()
            if not dec: continue                                  # [v82.5] crunch와 동일: 결과 미확정 행 제외
            k = (gid, pk)                                         # [v82.5] crunch와 동일: 게임당 1레코드(첫 행 채택)
            if k in _seen: continue
            _seen.add(k); _disp[pk] = str(r[NM]).strip()
            if cc:
                e = _champ[(pk, cc, pos)]; e[0] += 1; e[1] += win; _pchamps[pk].add(cc)
                if pos: _pchamps_pos[(pk, pos)].add(cc)
            p = _pl[pk]
            p[0] += 1; p[1] += win
            ev = str(r[EV]).strip() if EV < len(r) else ""
            if ev == "MVP": p[2] += 1
            elif ev == "역적": p[3] += 1
            elif ev == "ACE": p[4] += 1
            try:
                if SC < len(r) and str(r[SC]).strip(): p[5] += float(r[SC]); p[6] += 1
            except Exception: pass
            if sd == "블루팀": p[7] += 1; p[8] += win
            elif sd == "레드팀": p[9] += 1; p[10] += win
            _side = "블루팀" if sd == "블루팀" else "레드팀"   # [v82.5] crunch games_dict와 동일: 빈 진영도 레드로(동일 quirk 유지)
            _roster[gid][_side].add(pk)
            if win: _roster[gid]["win"] = _side
            if dec and (gid, pk) not in _seqseen:              # 연승 시퀀스(게임 dedup, append순=시간순)
                _seqseen.add((gid, pk)); _seq[pk].append(res); _pgames[pk][gid] = win
                _pgpos[pk][gid] = pos
        def _streak(pk):
            s = _seq.get(pk, [])
            if not s: return 0
            cur = s[-1]; c = 0
            for x in reversed(s):
                if x == cur: c += 1
                else: break
            return c if cur == "승리" else (-c if cur == "패배" else 0)
        # 같은팀 시너지(진영별 분리 — crunch가 '현재 배정 진영의 동반 게임만' 계산하므로) / 맞상대 상성
        _syn = _dd(lambda: [0, 0]); _nem = _dd(lambda: [0, 0])
        for gid, rr in _roster.items():
            w = rr["win"]
            if w is None: continue
            for side in ("블루팀", "레드팀"):
                mem = sorted(rr[side])
                for i in range(len(mem)):
                    for j in range(i + 1, len(mem)):
                        se = _syn[(mem[i], mem[j], side)]; se[0] += 1; se[1] += (1 if side == w else 0)
            for b in rr["블루팀"]:
                for rd in rr["레드팀"]:
                    a1, a2 = sorted([b, rd]); ne = _nem[(a1, a2)]; ne[0] += 1
                    ne[1] += (1 if w == ("블루팀" if a1 == b else "레드팀") else 0)
        # 약점(선수 챔프가 그 선수 게임에서 밴된 판수)
        _ban = _dd(lambda: [0, 0]); _banp = _dd(lambda: [0, 0])
        for pk, gw in _pgames.items():
            _gp = _pgpos.get(pk, {})
            for gid, win in gw.items():
                _po = _gp.get(gid, "")
                for bc in _gban.get(gid, ()):
                    if bc in _pchamps[pk]:
                        be = _ban[(pk, bc)]; be[0] += 1; be[1] += win
                    if _po and bc in _pchamps_pos.get((pk, _po), ()):
                        bp = _banp[(pk, bc, _po)]; bp[0] += 1; bp[1] += win
        champ_vals = [["키", "소환사명", "챔피언", "포지션", "판수", "승"]]
        for (pk, c, pos), e in _champ.items():
            if e[0] > 0: champ_vals.append([pk, _disp.get(pk, ""), c, pos, e[0], e[1]])
        player_vals = [["키", "소환사명", "총판수", "총승", "MVP", "역적", "ACE", "점수합", "점수판수", "블루판", "블루승", "레드판", "레드승", "연승"]]
        for pk, p in _pl.items():
            player_vals.append([pk, _disp.get(pk, ""), p[0], p[1], p[2], p[3], p[4], round(p[5], 1), p[6], p[7], p[8], p[9], p[10], _streak(pk)])
        syn_vals = [["키A", "키B", "진영", "판수", "같은팀승"]] + [[a, b, sd_, e[0], e[1]] for (a, b, sd_), e in _syn.items() if e[0] >= 5]
        nem_vals = [["키A", "키B", "판수", "A측승"]] + [[a, b, e[0], e[1]] for (a, b), e in _nem.items() if e[0] >= 5]
        ban_vals = [["키", "챔피언", "밴판수", "밴판승"]] + [[pk, c, e[0], e[1]] for (pk, c), e in _ban.items() if e[0] >= 3]
        banpos_vals = ([["키", "챔피언", "포지션", "밴판수", "밴판승"]]
                       + [[pk, c, po, e[0], e[1]] for (pk, c, po), e in _banp.items() if e[0] >= 3])
        if len(player_vals) < 20 or len(champ_vals) < 50: return   # 안전판: 읽기 실패/급감 시 덮어쓰기 금지
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(resource_path('credentials.json.json'), scope)
        tok = creds.get_access_token().access_token
        H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
        _tabs = (("STAT_CHAMP", champ_vals), ("STAT_PLAYER", player_vals),
                 ("STAT_SYNERGY", syn_vals), ("STAT_NEMESIS", nem_vals), ("STAT_BAN", ban_vals),
                 ("STAT_BAN_POS", banpos_vals))
        try:   # 신규 집계탭 없으면 생성(호스트 최초 1회)
            _ws = {ws.title: ws for ws in global_spreadsheet.worksheets()} if global_spreadsheet else {}
            for _t in ("STAT_SYNERGY", "STAT_NEMESIS", "STAT_BAN", "STAT_BAN_POS"):
                if _t not in _ws:
                    try: global_spreadsheet.add_worksheet(title=_t, rows=20000, cols=8)
                    except Exception: pass
            # ⚠️ 값 쓰기(values.update)는 격자를 자동으로 늘려주지 않는다 — 행이 넘치면 통째로 실패한다.
            #   STAT_BAN 은 2000행짜리 탭에 이미 1860행이라 곧 벽에 닿는다(2026-08-13 실측).
            #   내용이 탭보다 커졌으면 먼저 늘려 둔다.
            for _t, _v in _tabs:
                w = _ws.get(_t)
                if w is not None and getattr(w, "row_count", 0) and len(_v) + 20 > w.row_count:
                    try:
                        w.resize(rows=len(_v) + 5000)
                        print(f"[stat_agg] {_t} 탭 행 확장 → {len(_v)+5000}", flush=True)
                    except Exception: pass
        except Exception: pass
        for tab, vals in _tabs:
            base = f"https://sheets.googleapis.com/v4/spreadsheets/{DOCUMENT_ID}/values/{tab}"
            try:
                requests.post(base + "!A1:Z1000000:clear", headers=H, timeout=30)
                requests.put(base + "!A1?valueInputOption=RAW", headers=H, data=json.dumps({"values": vals}), timeout=60)
            except Exception as _we:
                print(f"[stat_agg] {tab} 쓰기 실패: {type(_we).__name__}", flush=True)
        print(f"[stat_agg] 사전집계 갱신 — CHAMP {len(champ_vals)-1} · PLAYER {len(player_vals)-1} · SYN {len(syn_vals)-1} · NEM {len(nem_vals)-1} · BAN {len(ban_vals)-1} · BANPOS {len(banpos_vals)-1}", flush=True)
    except Exception as e:
        print(f"[stat_agg] 재계산 실패(무시): {type(e).__name__}: {e}", flush=True)

def update_hof_stats(force=False):
    global gui_data, global_spreadsheet
    if not global_spreadsheet: return
    try:
        all_ws = global_spreadsheet.worksheets()
        c_g_data, a_g_data = {"전체 (ALL)": {}}, {"전체 (ALL)": {}}
        def _hof_parse_met(s):
            """📊 '지표' 팩("g8566|cs26|m25.9|kp82|...") → {키: float}. 실패 시 {}."""
            out = {}
            try:
                for tok in str(s or "").split("|"):
                    m2 = re.match(r"([a-z]+)(-?[\d.]+)$", tok.strip())
                    if m2: out[m2.group(1)] = float(m2.group(2))
            except Exception: return {}
            return out
        c_rec, a_rec = {}, {}   # 🏅 [v82.22] 기록실 — p_key별 킬/데스/어시/딜량/AI점수 기록(단일게임 최고 + 누적)
        c_patches, a_patches = set(), set()
        c_aliases, a_aliases = {}, {}   # p_key(PUUID) -> {그 사람의 모든 닉} : 닉변 시 티어 복원용
        
        for ws in all_ws:
            title = ws.title
            if title not in ["CLASSIC_NORMAL", "KIWI_KIWI"]: continue
            is_classic = (title == "CLASSIC_NORMAL")
            
            rows = get_sheet_data_cached(ws, force=force)
            if len(rows) <= 1: continue
            
            headers = rows[0]
            col_gid = headers.index("게임ID") if "게임ID" in headers else -1
            col_name = headers.index("소환사명") if "소환사명" in headers else -1
            col_puuid = headers.index("PUUID") if "PUUID" in headers else -1
            col_pos = headers.index("포지션") if "포지션" in headers else -1
            col_res = headers.index("결과") if "결과" in headers else -1
            col_eval = headers.index("매치평가") if "매치평가" in headers else -1
            col_patch = headers.index("패치버전") if "패치버전" in headers else -1
            col_score = headers.index("점수") if "점수" in headers else -1   # AI 종합점수(티어평가 신뢰도용)
            col_kda = headers.index("KDA") if "KDA" in headers else -1        # [v82.22] 기록실용
            col_dmg = headers.index("딜량") if "딜량" in headers else -1
            col_date = headers.index("날짜") if "날짜" in headers else -1
            col_champ = headers.index("챔피언") if "챔피언" in headers else -1
            col_met = headers.index("지표") if "지표" in headers else -1   # 📊 [v82.41] 기록실 상세지표(웹 동일)
            target_rec = c_rec if is_classic else a_rec
            
            if col_res == -1: continue
            
            eval_gids = set()
            if col_eval != -1 and col_gid != -1:
                for r in rows[1:]:
                    if len(r) > col_eval and r[col_eval] in ["MVP", "역적", "ACE"]:
                        g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
                        if g_id: eval_gids.add(g_id)
            
            target_data = c_g_data if is_classic else a_g_data
            target_patches = c_patches if is_classic else a_patches
            target_aliases = c_aliases if is_classic else a_aliases
            processed_records = set()
            
            puuid_to_latest_name = {}
            name_to_puuid_fallback = {}
            for r in rows[1:]:
                puuid = str(r[col_puuid]).strip().lower() if col_puuid != -1 and col_puuid < len(r) else ""
                name = r[col_name].strip() if col_name != -1 and col_name < len(r) else ""
                main_name = get_main_name(name)
                if puuid and main_name:
                    puuid_to_latest_name[puuid] = name 
                    name_to_puuid_fallback[main_name] = puuid
            
            for r in rows[1:]:
                g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
                raw_name = r[col_name].strip() if col_name != -1 and col_name < len(r) else ""
                main_name = get_main_name(raw_name)
                
                raw_puuid = str(r[col_puuid]).strip().lower() if col_puuid != -1 and col_puuid < len(r) else ""
                p_key = raw_puuid if raw_puuid else name_to_puuid_fallback.get(main_name, main_name)
                if p_key and main_name: target_aliases.setdefault(p_key, set()).add(main_name)

                res = r[col_res] if col_res != -1 and col_res < len(r) else ""
                
                raw_pos_kor = r[col_pos] if col_pos != -1 and col_pos < len(r) else "선택안함"
                pos_eng = "NONE"
                for k, v in POSITION_TRANSLATE_KOR.items():
                    if v == raw_pos_kor: pos_eng = k
                
                evl = r[col_eval] if col_eval != -1 and col_eval < len(r) else ""
                patch_ver = r[col_patch].strip() if col_patch != -1 and col_patch < len(r) and r[col_patch].strip() else "과거버전"
                patch_ver = patch_ver.replace("'", "") 
                
                if not p_key or res not in ["승리", "패배"]: continue
                
                record_key = f"{g_id}_{p_key}"
                if record_key in processed_records: continue
                processed_records.add(record_key)
                
                target_patches.add(patch_ver)

                display_name = puuid_to_latest_name.get(p_key, main_name) if raw_puuid else main_name

                # 🏅 [v82.22] 기록실 집계 — 게임당 1레코드(위 dedup 통과분), 패치 무관 전체 누적
                try:
                    _rc = target_rec.setdefault(p_key, {"name": display_name, "g": 0, "tk": 0, "td": 0, "ta": 0,
                                                        "dmg_sum": 0, "dmg_n": 0, "mx_k": (-1, "", ""), "mx_d": (-1, "", ""),
                                                        "mx_a": (-1, "", ""), "mx_dmg": (-1, "", ""), "mx_sc": (-1.0, "", "")})
                    _rc["name"] = display_name; _rc["g"] += 1
                    _rch = r[col_champ] if 0 <= col_champ < len(r) else ""
                    _rdt = str(r[col_date])[5:10] if 0 <= col_date < len(r) else ""   # 'MM-DD'
                    _rkda = str(r[col_kda]).strip() if 0 <= col_kda < len(r) else ""
                    _rm = re.fullmatch(r"(\d+)/(\d+)/(\d+)", _rkda)
                    if _rm:
                        _k, _d, _a = int(_rm.group(1)), int(_rm.group(2)), int(_rm.group(3))
                        _rc["tk"] += _k; _rc["td"] += _d; _rc["ta"] += _a
                        if _k > _rc["mx_k"][0]: _rc["mx_k"] = (_k, _rch, _rdt)
                        if _d > _rc["mx_d"][0]: _rc["mx_d"] = (_d, _rch, _rdt)
                        if _a > _rc["mx_a"][0]: _rc["mx_a"] = (_a, _rch, _rdt)
                    _rdv = str(r[col_dmg]).replace(",", "").strip() if 0 <= col_dmg < len(r) else ""
                    if _rdv.isdigit():
                        _rdi = int(_rdv)
                        _rc["dmg_sum"] += _rdi; _rc["dmg_n"] += 1
                        if _rdi > _rc["mx_dmg"][0]: _rc["mx_dmg"] = (_rdi, _rch, _rdt)
                    _rsv2 = None
                    if 0 <= col_score < len(r):
                        try:
                            _rsv2 = float(str(r[col_score]).strip())
                            if _rsv2 > _rc["mx_sc"][0]: _rc["mx_sc"] = (_rsv2, _rch, _rdt)
                        except Exception: _rsv2 = None
                    # 📊 [v82.41] 웹 기록실 확장 지표 미러 — 평균 AI점수·무데스/두자릿킬·상세지표 팩·포지션별 버킷
                    if _rm:
                        _rc["kda_n"] = _rc.get("kda_n", 0) + 1
                        if _d == 0: _rc["nd_n"] = _rc.get("nd_n", 0) + 1
                        if _k >= 10: _rc["dk_n"] = _rc.get("dk_n", 0) + 1
                    if _rsv2 is not None:
                        _rc["sc_sum"] = _rc.get("sc_sum", 0.0) + _rsv2; _rc["sc_n"] = _rc.get("sc_n", 0) + 1
                    _pp = None
                    if pos_eng in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
                        _pp = _rc.setdefault("pp", {}).setdefault(pos_eng,
                              {"met_n": 0, "dpm": 0.0, "gpm": 0.0, "cspm": 0.0, "dmg_sum": 0, "dmg_n": 0, "sc_sum": 0.0, "sc_n": 0})
                        if _rdv.isdigit(): _pp["dmg_sum"] += int(_rdv); _pp["dmg_n"] += 1
                        if _rsv2 is not None: _pp["sc_sum"] += _rsv2; _pp["sc_n"] += 1
                    _mt = _hof_parse_met(r[col_met] if 0 <= col_met < len(r) else "")
                    _mmin = _mt.get("m", 0)
                    if _mmin >= 1:
                        _rc["met_n"] = _rc.get("met_n", 0) + 1
                        _dpm1 = (int(_rdv) if _rdv.isdigit() else 0) / _mmin
                        _rc["dpm_sum"] = _rc.get("dpm_sum", 0.0) + _dpm1
                        if "g" in _mt: _rc["gpm_sum"] = _rc.get("gpm_sum", 0.0) + _mt["g"] / _mmin
                        if "cs" in _mt: _rc["cspm_sum"] = _rc.get("cspm_sum", 0.0) + _mt["cs"] / _mmin
                        if "kp" in _mt: _rc["kp_sum"] = _rc.get("kp_sum", 0.0) + _mt["kp"]
                        if "vs" in _mt: _rc["vs_sum"] = _rc.get("vs_sum", 0.0) + _mt["vs"]
                        if "cw" in _mt: _rc["cw_sum"] = _rc.get("cw_sum", 0) + int(_mt["cw"])
                        if "wp" in _mt: _rc["wp_sum"] = _rc.get("wp_sum", 0) + int(_mt["wp"])
                        if "wk" in _mt: _rc["wk_sum"] = _rc.get("wk_sum", 0) + int(_mt["wk"])
                        if "sk" in _mt: _rc["sk_sum"] = _rc.get("sk_sum", 0) + int(_mt["sk"])
                        if "hs" in _mt: _rc["hs_sum"] = _rc.get("hs_sum", 0) + int(_mt["hs"])
                        if "dr" in _mt: _rc["dr_sum"] = _rc.get("dr_sum", 0) + int(_mt["dr"])
                        if "br" in _mt: _rc["br_sum"] = _rc.get("br_sum", 0) + int(_mt["br"])
                        if "tk" in _mt: _rc["tur_sum"] = _rc.get("tur_sum", 0) + int(_mt["tk"])
                        if "dt" in _mt:
                            _rc["dtpm_sum"] = _rc.get("dtpm_sum", 0.0) + _mt["dt"] / _mmin
                            if _mt["dt"] > _rc.get("mx_dt", (-1, "", ""))[0]: _rc["mx_dt"] = (int(_mt["dt"]), _rch, _rdt)
                        if _pp is not None:
                            _pp["met_n"] += 1; _pp["dpm"] += _dpm1
                            if "g" in _mt: _pp["gpm"] += _mt["g"] / _mmin
                            if "cs" in _mt: _pp["cspm"] += _mt["cs"] / _mmin
                except Exception: pass

                for p_ver in ["전체 (ALL)", patch_ver]:
                    if p_ver not in target_data: target_data[p_ver] = {}
                    if p_key not in target_data[p_ver]:
                        target_data[p_ver][p_key] = {
                            "name": display_name,
                            "main_pos": {},
                            "ALL": {"total": 0, "wins": 0, "mvp": 0, "ace": 0, "troll": 0, "eval_total": 0, "ai_sum": 0.0, "ai_n": 0, "recent30": 0},
                            "TOP": {"total": 0, "wins": 0, "mvp": 0, "ace": 0, "troll": 0, "eval_total": 0},
                            "JUNGLE": {"total": 0, "wins": 0, "mvp": 0, "ace": 0, "troll": 0, "eval_total": 0},
                            "MIDDLE": {"total": 0, "wins": 0, "mvp": 0, "ace": 0, "troll": 0, "eval_total": 0},
                            "BOTTOM": {"total": 0, "wins": 0, "mvp": 0, "ace": 0, "troll": 0, "eval_total": 0},
                            "UTILITY": {"total": 0, "wins": 0, "mvp": 0, "ace": 0, "troll": 0, "eval_total": 0}
                        }
                    else:
                        target_data[p_ver][p_key]["name"] = display_name
                    
                    target_data[p_ver][p_key]["ALL"]["total"] += 1
                    if pos_eng != "NONE": target_data[p_ver][p_key]["main_pos"][pos_eng] = target_data[p_ver][p_key]["main_pos"].get(pos_eng, 0) + 1
                    if res == "승리": target_data[p_ver][p_key]["ALL"]["wins"] += 1
                    # [v82.27 사장님 지시] 십이귀월 활동 조건용 — 최근 30일 내 판수
                    try:
                        _dm = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(r[col_date]) if 0 <= col_date < len(r) else "")
                        if _dm and time.mktime((int(_dm.group(1)), int(_dm.group(2)), int(_dm.group(3)), 0, 0, 0, 0, 0, -1)) >= time.time() - 30 * 86400:
                            target_data[p_ver][p_key]["ALL"]["recent30"] = target_data[p_ver][p_key]["ALL"].get("recent30", 0) + 1
                    except Exception: pass
                    
                    if g_id in eval_gids:
                        target_data[p_ver][p_key]["ALL"]["eval_total"] += 1
                        if evl == "MVP": target_data[p_ver][p_key]["ALL"]["mvp"] += 1
                        if evl == "ACE": target_data[p_ver][p_key]["ALL"]["ace"] += 1
                        if evl == "역적": target_data[p_ver][p_key]["ALL"]["troll"] += 1
                        # AI 종합점수 평균용 누적 (점수 컬럼이 숫자일 때만)
                        if col_score != -1 and col_score < len(r):
                            try:
                                _sv = float(str(r[col_score]).strip())
                                target_data[p_ver][p_key]["ALL"]["ai_sum"] += _sv
                                target_data[p_ver][p_key]["ALL"]["ai_n"] += 1
                            except Exception: pass
                    
                    if pos_eng in target_data[p_ver][p_key] and pos_eng != "NONE":
                        target_data[p_ver][p_key][pos_eng]["total"] += 1
                        if res == "승리": target_data[p_ver][p_key][pos_eng]["wins"] += 1
                        if g_id in eval_gids:
                            target_data[p_ver][p_key][pos_eng]["eval_total"] += 1
                            if evl == "MVP": target_data[p_ver][p_key][pos_eng]["mvp"] += 1
                            if evl == "ACE": target_data[p_ver][p_key][pos_eng]["ace"] += 1
                            if evl == "역적": target_data[p_ver][p_key][pos_eng]["troll"] += 1
                            
        with gui_lock:
            gui_data["hof_classic"] = {"global_stats": c_g_data, "patches": ["전체 (ALL)"] + sorted(list(c_patches), reverse=True), "aliases": {k: list(v) for k, v in c_aliases.items()}}
            gui_data["hof_aram"] = {"global_stats": a_g_data, "patches": ["전체 (ALL)"] + sorted(list(a_patches), reverse=True), "aliases": {k: list(v) for k, v in a_aliases.items()}}
            gui_data["hof_records"] = {"classic": c_rec, "aram": a_rec}   # 🏅 [v82.22] 기록실
    except Exception: pass
    try:
        if load_bot_token(): sync_master_tier_chart()   # 🎖 마스터 티어표→CLAN_TIERS 자동 동기화(호스트만, 15분 주기)
    except Exception: pass
    try: announce_sibguiwol_if_changed()   # 🩸 십이귀월 로스터 변동 시 웹훅(호스트만)
    except Exception: pass

def get_champ_eng_name(kor_name):
    if not kor_name: return None
    clean_name = kor_name.strip()
    if clean_name in CHAMP_KOR_TO_ENG: return CHAMP_KOR_TO_ENG[clean_name]
    for champ_id, data in global_champ_map.items():
        if data.get('kor') == clean_name: return data.get('eng')
    return None

def _dedupe_champ_entries(entries):
    """[2026-07-29 사장님 제보] 같은 챔피언 초상화가 두 번 나오던 문제.
       시트에 한글명 표기가 갈린 기록(리메이크·표기 변경 등)이 서로 다른 키로 집계돼
       모스트/고승률픽에 같은 챔프가 중복으로 실렸다. 영문 키로 합쳐서 하나로 만든다."""
    out, seen = [], {}
    for e in entries or []:
        k = get_champ_eng_name(e.get("name")) or str(e.get("name") or "")
        if not k: continue
        if k in seen:
            seen[k]["count"] = int(seen[k].get("count", 0)) + int(e.get("count", 0))
            continue
        seen[k] = dict(e); out.append(seen[k])
    return out


def _champ_id_of(kor_name):
    """한글 챔피언명 → 숫자 ID(초상화 주소용). 공백 유무 차이는 무시."""
    _k = str(kor_name or "").replace(" ", "")
    for _cid, _d in global_champ_map.items():
        if str(_d.get("kor") or "").replace(" ", "") == _k: return _cid
    return 0


def load_champion_image(champ_kor_name, size=32):
    """[2026-07-29 사장님 제보] 초상화가 옛날 그림으로 바뀐 문제.
       Data Dragon 최신 버전이 구 아트를 주는 구간이 있어, 실제 클라이언트와 같은 아트를 쓰는
       Community Dragon(라이브 클라이언트 에셋 미러)을 먼저 받고, 실패할 때만 종전 경로로 떨어진다."""
    if not PILLOW_INSTALLED or not champ_kor_name: return None
    champ_eng_name = get_champ_eng_name(champ_kor_name)
    if not champ_eng_name: return None

    cache_key = f"{champ_eng_name}_{size}"
    if cache_key in champion_image_cache: return champion_image_cache[cache_key]

    urls = []
    _cid = _champ_id_of(champ_kor_name)
    if _cid:
        urls.append("https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/"
                    f"default/v1/champion-icons/{_cid}.png")
    urls.append(f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{champ_eng_name}.png")
    for url in urls:
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                img_data = Image.open(BytesIO(res.content)).convert("RGBA")
                img_resized = img_data.resize((size, size), Image.Resampling.LANCZOS)
                photo_img = ImageTk.PhotoImage(img_resized)
                champion_image_cache[cache_key] = photo_img
                return photo_img
        except Exception: pass
    return None

# 🎯 [v83.4 사장님 지시] "밴 당할 시 승률 N% 하락" 을 현재포지션 기준으로도 낸다.
#   기존 줄은 그 사람의 **전체 라인** 승률을 기준으로 계산한다 — 원딜만 하는 사람에겐 맞지만,
#   정글·서폿을 오가는 사람에겐 "그래서 지금 이 자리에서 얼마나 아픈가"를 못 알려준다.
#   문턱은 전체 기준과 **똑같이** 둔다(밴된 판 5판↑·하락 10%p↑). 포지션이라고 기준을 낮추면
#   표본 3판짜리 −40%p 같은 숫자가 튀어나와 경고가 싸구려가 된다.
#   다만 기준선(그 포지션 승률) 자체가 흔들리면 안 되므로, 그 포지션 10판 이상일 때만 계산한다.
#   실측(2026-08-13 CLASSIC_NORMAL): 채점 가능한 (사람,포지션) 222쌍 중 73쌍(33%)에 경고가 뜬다.
FB_MIN_BAN_GAMES = 5     # 그 챔프가 밴된 판이 이만큼은 돼야 비율을 말한다(전체 기준과 동일)
FB_MIN_DROP = 0.10       # 하락폭 문턱(전체 기준과 동일)
FB_POS_MIN_GAMES = 10    # 그 포지션 기준 승률이 흔들리지 않을 최소 표본
FB_POS_ROLES = ("탑", "정글", "미드", "원딜", "서폿")


def _ga(nm):
    """이름 뒤 주격 조사 — 받침 있으면 '이', 없으면 '가'. 한글이 아니면 '가'(wei ha가)."""
    c = str(nm or "").strip()[-1:] if str(nm or "").strip() else ""
    if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28: return "이"
    return "가"


def _fatal_bans_pos_entry(pos_games, pos_wins, cand):
    """한 포지션의 약점 목록. cand = [(챔프, 밴판수, 밴판승), ...]. 없으면 []."""
    if pos_games < FB_POS_MIN_GAMES: return []
    pwr = pos_wins / pos_games
    out = []
    for c, bg_, bw_ in cand:
        if bg_ < FB_MIN_BAN_GAMES: continue
        b_wr = bw_ / bg_
        drop = pwr - b_wr
        if drop >= FB_MIN_DROP:
            out.append({"champ": c, "drop": int(drop * 100), "b_wr": int(b_wr * 100),
                        "b_games": bg_, "pos_games": pos_games})
    out.sort(key=lambda x: -x["drop"])
    return out


def _compute_pos_champ_lists(p_matches):
    """[2026-07-08] 포지션별(한글 탑/정글/미드/원딜/서폿) 모스트5 + 고승률픽 계산 → (most_by_pos, op_by_pos).
       [v82.36 사장님 지시] 고승률픽 기준을 **전체라인과 동일하게 통일**: 5판↑ + 승률 60%↑.
         (이전엔 3판↑·50%↑로 완화돼 있어, 같은 사람인데 전체라인 뷰와 포지션 뷰의 고승률픽이 달랐음.
          50%대 챔프가 '고승률픽'으로 뜨는 것도 이름과 안 맞았다.)
       ※ 후보 스캔은 상위 8개 유지 — 문턱은 같게 하되, 포지션 표본이 작아 6~8위에 걸린
         '5판 60%' 챔프까지 놓치지 않기 위함(스캔 범위는 표시 기준이 아니라 탐색 범위).
       m['pos']는 시트 '포지션' 컬럼값(한글)."""
    most_by_pos, op_by_pos = {}, {}
    for _pk in ("탑", "정글", "미드", "원딜", "서폿"):
        _pm = [m for m in p_matches if m.get('pos') == _pk]
        if not _pm: continue
        _pc = {}
        for _m in _pm:
            _c = _m.get('champ')
            if _c: _pc[_c] = _pc.get(_c, 0) + 1
        if not _pc: continue
        _sc = sorted(_pc.items(), key=lambda x: (-x[1], x[0]))   # [v82.5] 동률은 이름순(결정적) — 집계 경로와 동일 규칙
        most_by_pos[_pk] = _dedupe_champ_entries([{"name": c, "count": v} for c, v in _sc[:8]])[:5]
        _ops = []
        for c, v in _sc[:8]:
            _cw = sum(1 for _m in _pm if _m.get('champ') == c and _m.get('result') == '승리')
            _wr = (_cw / v) * 100
            if v >= 5 and _wr >= 60.0:   # [v82.36] 전체라인과 동일 기준
                _ops.append({"name": c, "wr": _wr, "count": v})
        _ops.sort(key=lambda x: (-x["wr"], -x["count"]))
        op_by_pos[_pk] = _dedupe_champ_entries(_ops)
    return most_by_pos, op_by_pos

# 🎯 [v82.37] 대기실 모스트 표시 기본값 — 설정(config.json `pos_view_default`)에서 사용자가 지정.
#   세션 중 버튼으로 바꾼 값(gui_data["pos_view_mode"])이 있으면 그게 우선, 없으면 이 기본값을 쓴다.
# 🔠 [2026-08-13 사장님 제보 '창을 줄이면 글자가 그대로라 못 읽겠다'] 창 크기에 따라 같이 변하는 폰트.
#   튜플 폰트(UF(11))는 위젯에 박히는 순간 크기가 굳는다 — 창을 줄여도 글자는 그대로라
#   좁은 화면에서 글자끼리 겹치고 잘린다. Tk 는 '이름 있는 폰트'를 쓰면 그 폰트의 size 만 바꿔도
#   그 폰트를 쓰는 모든 위젯이 한 번에 다시 그려진다 → 앱 전체 글자를 한 줄로 확대·축소할 수 있다.
_UI_FONTS = {}          # (family, 기준크기, weight) -> tkfont.Font
_UI_SCALE = [1.0]
UI_BASE_W, UI_BASE_H = 1560, 1045    # 이 크기일 때 배율 1.0 ('표준' 프리셋 기준)

def UF(size, weight="normal", family="Malgun Gothic"):
    """이름 있는 폰트를 돌려준다(같은 조합은 재사용). 배율이 바뀌면 여기 등록된 폰트가 전부 따라간다."""
    key = (family, int(size), weight)
    f = _UI_FONTS.get(key)
    if f is None:
        try:
            f = tkfont.Font(family=family, size=max(6, int(round(size * _UI_SCALE[0]))), weight=weight)
        except Exception:
            return (family, int(size), weight)      # 루트가 아직 없으면 옛 방식으로 폴백
        _UI_FONTS[key] = f
    return f

def ui_scale_apply(scale):
    """앱 전체 글자 배율 변경. 너무 잦은 재계산을 막으려 2% 미만 변화는 무시한다."""
    #  아래로 0.55 까지 열어 둔다 — 사장님이 창을 아주 작게 쓰실 때 글자가 안 줄면 서로 겹친다.
    #  위로는 1.30 까지만 — 큰 화면에서 무한정 커지면 정작 정보가 덜 들어간다.
    scale = max(0.55, min(1.30, float(scale)))
    if abs(scale - _UI_SCALE[0]) < 0.02: return
    _UI_SCALE[0] = scale
    for (fam, base, wt), f in list(_UI_FONTS.items()):
        try: f.configure(size=max(6, int(round(base * scale))))
        except Exception: pass

_POSVIEW_BTN = [None]   # 설정 저장 시 버튼 문구·색을 즉시 맞추기 위한 참조
_SYNERGY_SYNC = [None]  # 🧩 우측 시너지 3칸 표시/숨김을 설정 창에서 즉시 적용하기 위한 콜백

def _posview_default():
    try: return bool(APP_CONFIG.get("pos_view_default", True))
    except Exception: return True

def _posview_btn_sync(on):
    """토글 버튼 문구·색을 상태에 맞춤(설정 변경·토글 양쪽에서 호출)."""
    try:
        b = _POSVIEW_BTN[0]
        if b is not None:
            b.config(text=("모스트: 현재포지션" if on else "모스트: 전체라인"),
                     bg=(theme.SUCCESS if on else theme.BG_RAISED))
    except Exception: pass

def _fatal_ban_text(p, s, pos_view):
    """대기실 약점 한 줄. 현재포지션 뷰면 그 포지션 기준, 없으면 전체 기준으로 폴백.
       [v83.4 사장님 지시] 전체 기준만 보여주면 정글·서폿을 오가는 사람에게
       '지금 이 자리에서 얼마나 아픈가'를 못 알려준다. 모스트/고승률픽이 이미 포지션을 따라가므로
       같은 줄에서 약점만 전체 기준으로 남아 있으면 오히려 어긋나 보인다.
       그 포지션 표본이 얇으면(FB_POS_MIN_GAMES 미만) 억지로 만들지 않고 전체 기준으로 돌아간다."""
    if pos_view:
        pkor = POSITION_TRANSLATE_KOR.get(str(p.get("chosen_pos_icon", "NONE")), "선택안함")
        fbp = (s.get("fatal_bans_by_pos") or {}).get(pkor) or []
        if fbp:
            fb = fbp[0]
            return f"[{pkor}] {fb['champ']} 밴 당할 시 승률 {fb['drop']}% 하락"
    fbs = s.get("fatal_bans") or []
    if not fbs: return ""
    fb = fbs[0]
    # 포지션 뷰인데 그 자리 표본이 모자라 전체로 돌아왔다면, 무엇 기준인지 밝힌다.
    return (("[전체] " if pos_view else "") + f"{fb['champ']} 밴 당할 시 승률 {fb['drop']}% 하락")


def _display_champ_lists(p, s, pos_view):
    """대기실 슬롯 표시용 (모스트, 고승률픽, 포지션태그) 선택.
       pos_view=False → 전체 라인 모스트/고승률픽(기존). True → 현재 선택 포지션의 모스트5+고승률픽(해당 포지션 기록 없거나 미선택이면 전체 폴백)."""
    if pos_view:
        cpi = str(p.get("chosen_pos_icon", "NONE"))
        pkor = POSITION_TRANSLATE_KOR.get(cpi, "선택안함")
        mbp = s.get("most_by_pos", {}) or {}
        obp = s.get("op_by_pos", {}) or {}
        if pkor in mbp:
            return mbp.get(pkor, []), obp.get(pkor, []), "[" + pkor + "]"
        return s.get("most_list", []), s.get("op_list", []), "[전체]"
    return s.get("most_list", []), s.get("op_list", []), ""

def _gviz_tab_csv(tab_name):
    """공개 gviz로 탭 전체를 CSV로 읽기(서비스계정 읽기 할당량 미사용 — 429 무관)."""
    import csv as _csv, io as _io, urllib.request as _u, urllib.parse as _up
    url = (f"https://docs.google.com/spreadsheets/d/{DOCUMENT_ID}/gviz/tq?tqx=out:csv"
           f"&sheet={_up.quote(tab_name)}&headers=1&cb={int(time.time())}")   # cb=캐시버스터(gviz 캐시가 스키마 변경 직후 구버전을 주는 것 방지)
    raw = _u.urlopen(_u.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8")
    return list(_csv.reader(_io.StringIO(raw)))

_QUIZ_PREF_CACHE = {"ts": 0.0, "map": {}}

def _quiz_pref_map():
    """🔨 [2026-08-07 사장님 지시] 밴픽 퀴즈의 '상대별 밴 표'(QUIZ_PREF 탭)를 밴 추천 근거로.
    {tnorm(상대): [(챔프, 표, 적중), ...표순]} — 공개 gviz, 10분 캐시."""
    now = time.time()
    if _QUIZ_PREF_CACHE["ts"] and now - _QUIZ_PREF_CACHE["ts"] < 600: return _QUIZ_PREF_CACHE["map"]
    _QUIZ_PREF_CACHE["ts"] = now
    try:
        rows = _gviz_tab_csv("QUIZ_PREF")
        h = {c: i for i, c in enumerate(rows[0])} if rows else {}
        ni, ci, vi, hi = h.get("상대"), h.get("챔피언"), h.get("표"), h.get("적중")
        if None not in (ni, ci, vi, hi):
            mp = {}
            for r in rows[1:]:
                if len(r) <= max(ni, ci, vi, hi): continue
                k = tnorm(r[ni])
                if not k or not str(r[ci]).strip(): continue
                try: v, ht = int(float(r[vi] or 0)), int(float(r[hi] or 0))
                except Exception: v, ht = 0, 0
                mp.setdefault(k, []).append((str(r[ci]).strip(), v, ht))
            for k in mp: mp[k].sort(key=lambda x: -x[1])
            _QUIZ_PREF_CACHE["map"] = mp
    except Exception as e:
        print(f"[quiz] QUIZ_PREF 로드 실패(무시): {e}", flush=True)
    return _QUIZ_PREF_CACHE["map"]

def _crunch_from_aggregate(blue_players, red_players):
    """[v82.5 시트경량화 2b] crunch를 사전집계탭(STAT_*)에서 계산 — 원본 CLASSIC_NORMAL 전체읽기 제거.
       읽기는 전부 공개 gviz(할당량 무관). 집계가 비었거나 급감이면 예외 → 호출부가 원본 경로 폴백.
       집계는 호스트가 20분마다 갱신(rebuild_stat_aggregate) — 최대 20분 지연은 로비 표시용으로 허용."""
    def _i(x):
        try: return int(float(str(x).replace(",", "").strip() or 0))
        except Exception: return 0
    # ── 집계 로드 ──
    P = {}                      # 키 -> {name,g,w,bg,bw,rg,rw,stk}
    name_to_key = {}
    rows = _gviz_tab_csv("STAT_PLAYER")
    h = {c: i for i, c in enumerate(rows[0])} if rows else {}
    for r in rows[1:]:
        k = str(r[h["키"]]).strip().lower()
        if not k: continue
        P[k] = {"name": r[h["소환사명"]], "g": _i(r[h["총판수"]]), "w": _i(r[h["총승"]]),
                "bg": _i(r[h["블루판"]]), "bw": _i(r[h["블루승"]]),
                "rg": _i(r[h["레드판"]]), "rw": _i(r[h["레드승"]]), "stk": _i(r[h.get("연승", -1)] if "연승" in h else 0)}
        mn = get_main_name(str(r[h["소환사명"]]))
        if mn: name_to_key[mn] = k
    if len(P) < 20: raise RuntimeError("STAT_PLAYER 표본 부족")
    C = {}                      # 키 -> {champ: {"n":판수,"w":승, "pos":{한글포지션:(n,w)}}}
    rows = _gviz_tab_csv("STAT_CHAMP")
    h = {c: i for i, c in enumerate(rows[0])} if rows else {}
    for r in rows[1:]:
        k = str(r[h["키"]]).strip().lower(); c = str(r[h["챔피언"]]).strip()
        if not k or not c: continue
        pos = str(r[h["포지션"]]).strip(); n, w = _i(r[h["판수"]]), _i(r[h["승"]])
        e = C.setdefault(k, {}).setdefault(c, {"n": 0, "w": 0, "pos": {}})
        e["n"] += n; e["w"] += w
        if pos:
            pn, pw_ = e["pos"].get(pos, (0, 0)); e["pos"][pos] = (pn + n, pw_ + w)
    if sum(len(v) for v in C.values()) < 50: raise RuntimeError("STAT_CHAMP 표본 부족")
    SYN, NEM, BAN = {}, {}, {}
    rows = _gviz_tab_csv("STAT_SYNERGY")
    h = {c: i for i, c in enumerate(rows[0])} if rows else {}
    for r in rows[1:]:
        SYN[(str(r[h["키A"]]).strip().lower(), str(r[h["키B"]]).strip().lower(), str(r[h["진영"]]).strip())] = (_i(r[h["판수"]]), _i(r[h["같은팀승"]]))
    rows = _gviz_tab_csv("STAT_NEMESIS")
    h = {c: i for i, c in enumerate(rows[0])} if rows else {}
    for r in rows[1:]:
        NEM[(str(r[h["키A"]]).strip().lower(), str(r[h["키B"]]).strip().lower())] = (_i(r[h["판수"]]), _i(r[h["A측승"]]))
    rows = _gviz_tab_csv("STAT_BAN")
    h = {c: i for i, c in enumerate(rows[0])} if rows else {}
    for r in rows[1:]:
        BAN[(str(r[h["키"]]).strip().lower(), str(r[h["챔피언"]]).strip())] = (_i(r[h["밴판수"]]), _i(r[h["밴판승"]]))
    # 🎯 [v83.4] 포지션별 약점 — 호스트가 아직 옛 버전이면 이 탭이 없다. 없으면 조용히 전체 기준만 쓴다.
    BANP = {}
    try:
        rows = _gviz_tab_csv("STAT_BAN_POS")
        h = {c: i for i, c in enumerate(rows[0])} if rows else {}
        if {"키", "챔피언", "포지션", "밴판수", "밴판승"} <= set(h):
            for r in rows[1:]:
                BANP[(str(r[h["키"]]).strip().lower(), str(r[h["챔피언"]]).strip(),
                      str(r[h["포지션"]]).strip())] = (_i(r[h["밴판수"]]), _i(r[h["밴판승"]]))
    except Exception:
        BANP = {}

    def _key_of(p):
        uid = str(p.get('puuid', '')).strip().lower()
        if uid and uid in P: return uid
        return name_to_key.get(get_main_name(p.get('name', '')), uid or get_main_name(p.get('name', '')))

    # ── 대시보드(원본 crunch와 동일 규칙) ──
    stats_dashboard, blue_pool, red_pool = {}, {}, {}
    for p in blue_players + red_players:
        p_key = _key_of(p)
        pd = P.get(p_key)
        is_blue = any(str(bp.get('puuid', '')).strip().lower() == str(p.get('puuid', '')).strip().lower() for bp in blue_players)
        current_pool = blue_pool if is_blue else red_pool
        if not pd or pd["g"] == 0:
            stats_dashboard[p_key] = {"summary": "기록 없음", "most_list": [], "op_list": [], "most_by_pos": {}, "op_by_pos": {}, "fatal_bans": [], "fatal_bans_by_pos": {}, "pos1": "선택안함", "pos2": "선택안함", "streak": "", "streak_val": 0, "overall_wr": 0.5, "games": 0, "side_wr_str": ""}
            continue
        total, wins = pd["g"], pd["w"]
        overall_wr = wins / total
        sg, sw = (pd["bg"], pd["bw"]) if is_blue else (pd["rg"], pd["rw"])
        side_wr_str = f"진영 승률: {round((sw/sg)*100)}% ({sw}승 {sg-sw}패)" if sg > 0 else "진영 승률: 기록없음"
        sv = pd["stk"]
        # [2026-08-01] 이름 옆 '연승중/연패중' 표기 제거 — 5연승 이상은 닉네임 불타는 효과로 대신한다.
        #   표시 문자열은 더 이상 쓰지 않고 값(streak_val)만 넘긴다.
        champs = C.get(p_key, {})
        most_list, op_list, fatal_bans, user_ban_score = [], [], [], {}
        sorted_champs = sorted(champs.items(), key=lambda x: (-x[1]["n"], x[0]))   # 동률 이름순(원본과 동일)
        for c, e in sorted_champs[:5]: most_list.append({"name": c, "count": e["n"]})
        for c, e in sorted_champs[:5]:
            c_wr = (e["w"] / e["n"]) * 100 if e["n"] else 0
            if e["n"] >= 5 and c_wr >= 60.0:
                op_list.append({"name": c, "wr": c_wr, "count": e["n"]})
                user_ban_score[c] = user_ban_score.get(c, 0) + c_wr + (min(e["n"], 10) * 2)
        for c, _e in sorted_champs[:5]:
            bg_, bw_ = BAN.get((p_key, c), (0, 0))
            if bg_ >= 5:
                b_wr = bw_ / bg_
                drop = overall_wr - b_wr
                if drop >= 0.10:
                    fatal_bans.append({"champ": c, "drop": int(drop * 100), "b_wr": int(b_wr * 100), "b_games": bg_})
                    user_ban_score[c] = user_ban_score.get(c, 0) + (drop * 100) * 1.5 + (min(bg_, 5) * 5)
        fatal_bans.sort(key=lambda x: x['drop'], reverse=True)
        for _c, _sc in sorted(user_ban_score.items(), key=lambda x: x[1], reverse=True)[:3]:
            current_pool[_c] = current_pool.get(_c, 0) + _sc
        most_by_pos, op_by_pos, fatal_bans_by_pos = {}, {}, {}
        for _pk in FB_POS_ROLES:
            _pc = {c: e["pos"][_pk] for c, e in champs.items() if _pk in e["pos"]}
            if not _pc: continue
            _sc2 = sorted(_pc.items(), key=lambda x: (-x[1][0], x[0]))   # 동률 이름순(원본과 동일)
            most_by_pos[_pk] = _dedupe_champ_entries([{"name": c, "count": nv[0]} for c, nv in _sc2[:8]])[:5]
            _ops = []
            for c, (n_, w_) in _sc2[:8]:
                _wr = (w_ / n_) * 100 if n_ else 0
                if n_ >= 3 and _wr >= 50.0: _ops.append({"name": c, "wr": _wr, "count": n_})
            _ops.sort(key=lambda x: (-x["wr"], -x["count"]))
            op_by_pos[_pk] = _ops
            # 🎯 [v83.4] 이 포지션에서의 약점 — 기준선도 이 포지션 승률로 잡는다(전체 승률이 아니라).
            _pn = sum(nv[0] for _c, nv in _pc.items()); _pw = sum(nv[1] for _c, nv in _pc.items())
            _fb = _fatal_bans_pos_entry(_pn, _pw,
                                        [(c,) + tuple(BANP.get((p_key, c, _pk), (0, 0))) for c, _nv in _sc2[:5]])
            if _fb: fatal_bans_by_pos[_pk] = _fb
        stats_dashboard[p_key] = {
            "summary": f"{total}전 {wins}승 {total-wins}패 ({round(overall_wr*100, 1)}%)",
            "most_list": most_list, "op_list": op_list, "fatal_bans": fatal_bans,
            "fatal_bans_by_pos": fatal_bans_by_pos,
            "most_by_pos": most_by_pos, "op_by_pos": op_by_pos,
            "streak": "", "streak_val": sv, "overall_wr": overall_wr, "games": total, "side_wr_str": side_wr_str
        }

    blue_advice_list = sorted(red_pool.items(), key=lambda x: x[1], reverse=True)[:10]
    red_advice_list = sorted(blue_pool.items(), key=lambda x: x[1], reverse=True)[:10]
    with gui_lock:
        gui_data["blue_ban_advice_list"] = [c for c, _ in blue_advice_list]
        gui_data["red_ban_advice_list"] = [c for c, _ in red_advice_list]

    def calculate_hybrid_power(players_list):
        power_sum = 0
        for p in players_list:
            t_icon = p.get('tier_icon', 'UNRANKED')
            t_score = TIERS.index(t_icon) if t_icon in TIERS else 4
            s_data = stats_dashboard.get(_key_of(p), {})
            g = s_data.get('games', 0)
            raw_wr = s_data.get('overall_wr', 0.5)
            K = 8
            shrunk_wr = (raw_wr * g + 0.5 * K) / (g + K)
            streak_factor = min(1.0, g / 10.0)
            power_sum += ((t_score + shrunk_wr * 10) / 2) + (s_data.get('streak_val', 0) * 0.3 * streak_factor)
        return power_sum

    blue_power, red_power = calculate_hybrid_power(blue_players), calculate_hybrid_power(red_players)
    with gui_lock:
        if blue_power + red_power > 0:
            gui_data["blue_win_rate"] = max(15, min(85, int(50 + ((blue_power - red_power) * 4))))
            gui_data["red_win_rate"] = 100 - gui_data["blue_win_rate"]
        else:
            gui_data["blue_win_rate"] = 50; gui_data["red_win_rate"] = 50

    pos_alerts, neg_alerts, nemesis_alerts = [], [], []
    for team_players, t_name, opp_name in [(blue_players, '블루팀', '레드팀'), (red_players, '레드팀', '블루팀')]:
        for i in range(len(team_players)):
            for j in range(i + 1, len(team_players)):
                p1_key, p2_key = _key_of(team_players[i]), _key_of(team_players[j])
                p1_uid = str(team_players[i].get('puuid', '')).strip().lower()
                if p1_key and p2_key and p1_key != p2_key and not p1_uid.startswith('bot_'):
                    a, b = (p1_key, p2_key) if p1_key <= p2_key else (p2_key, p1_key)
                    dg, dw = SYN.get((a, b, t_name), (0, 0))   # 현재 배정 진영의 동반 게임만(원본 crunch와 동일)
                    if dg >= 10:
                        dwr = (dw / dg) * 100
                        p1_d, p2_d = str(team_players[i]['name']).split('#')[0], str(team_players[j]['name']).split('#')[0]
                        if dwr <= 40.0: neg_alerts.append(f" ⚠ {p1_d} & {p2_d} {round(dwr)}%")
                        elif dwr >= 60.0: pos_alerts.append(f" 🔥 {p1_d} & {p2_d} {round(dwr)}%")

    for b_p in blue_players:
        b_key = _key_of(b_p)
        b_uid = str(b_p.get('puuid', '')).strip().lower()
        if not b_key or "bot_" in b_uid: continue
        for r_p in red_players:
            r_key = _key_of(r_p)
            r_uid = str(r_p.get('puuid', '')).strip().lower()
            if not r_key or "bot_" in r_uid or b_key == r_key: continue
            a, b = (b_key, r_key) if b_key <= r_key else (r_key, b_key)
            hg, aw = NEM.get((a, b), (0, 0))
            if hg >= 10:
                bw = aw if a == b_key else (hg - aw)   # A측승 = 정렬상 앞 키 기준 → 블루측 관점으로 환산
                wr = (bw / hg) * 100
                b_disp, r_disp = str(b_p['name']).split('#')[0], str(r_p['name']).split('#')[0]
                # 🗣 [2026-08-16 사장님 지시] "A ➡ B 27%" 는 누가 앞서는지 읽는 사람마다 달랐다.
                #    강한 쪽을 앞에 두고 조사+전적으로 문장을 만든다 — "레멍이가 wei ha 상대로 8승 3패".
                #    (기존 5:5 표기는 6승 6패여도 '5:5'로 찍히던 오표기도 겸사겸사 수정)
                if wr <= 30.0: nemesis_alerts.append(f" 💀 {r_disp}{_ga(r_disp)} {b_disp} 상대로 {hg - bw}승 {bw}패")
                elif wr >= 70.0: nemesis_alerts.append(f" 💀 {b_disp}{_ga(b_disp)} {r_disp} 상대로 {bw}승 {hg - bw}패")
                elif bw == (hg - bw): nemesis_alerts.append(f" ⚔ {b_disp} 🆚 {r_disp} {bw}승 {bw}패 호각")

    return stats_dashboard, pos_alerts, neg_alerts, nemesis_alerts

def crunch_sheet_statistics(blue_players, red_players, sheet):
    # [v82.5] 협곡은 사전집계(gviz, 할당량 무관) 우선 — 실패/표본부족 시에만 원본 전체읽기 폴백(429 원인 제거)
    try:
        if getattr(sheet, "title", "") == "CLASSIC_NORMAL":
            _r = _crunch_from_aggregate(blue_players, red_players)
            print("[crunch] 사전집계 경로 사용(gviz)", flush=True)
            return _r
    except Exception as _ae:
        print(f"[crunch] 집계 폴백→원본: {type(_ae).__name__}: {_ae}", flush=True)
    try:
        rows = get_sheet_data_cached(sheet)
        if not rows or len(rows) <= 1: return {}, [], [], []
        
        headers = rows[0]
        col_gid = headers.index("게임ID") if "게임ID" in headers else -1
        col_name = headers.index("소환사명") if "소환사명" in headers else -1
        col_puuid = headers.index("PUUID") if "PUUID" in headers else -1
        col_team = headers.index("진영") if "진영" in headers else -1
        col_pos = headers.index("포지션") if "포지션" in headers else -1
        col_champ = headers.index("챔피언") if "챔피언" in headers else -1
        col_bans = headers.index("밴") if "밴" in headers else -1
        col_res = headers.index("결과") if "결과" in headers else -1
        
        if col_res == -1: return {}, [], [], []
        data_rows = rows[1:]
    except Exception: return {}, [], [], []

    name_to_puuid_fallback = {} 
    for bp in blue_players + red_players:
        bp_name = get_main_name(bp.get('name', ''))
        bp_puuid = str(bp.get('puuid', '')).strip().lower()
        if bp_name and bp_puuid and not bp_puuid.startswith('temp_'):
            name_to_puuid_fallback[bp_name] = bp_puuid

    for r in data_rows:
        r_puuid = str(r[col_puuid]).strip().lower() if col_puuid != -1 and col_puuid < len(r) else ""
        r_name = get_main_name(r[col_name] if col_name != -1 and col_name < len(r) else "")
        if r_puuid and r_name and not r_puuid.startswith('temp_'):
            name_to_puuid_fallback[r_name] = r_puuid

    game_all_bans = {}
    for r in data_rows:
        g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
        if not g_id: continue
        bans_str = r[col_bans] if col_bans != -1 and col_bans < len(r) else ""
        if g_id not in game_all_bans: game_all_bans[g_id] = set()
        
        for b in str(bans_str).split(','):
            b_clean = b.strip()
            if b_clean and b_clean not in ["밴 없음", "밴 안함", "기록 대기", "결과 대기", "평가 대기", "알수없음"]:
                game_all_bans[g_id].add(b_clean)

    player_games, player_champ_counts, games_dict = {}, {}, {}
    processed_records = set()

    for r in data_rows:
        g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
        raw_uid = str(r[col_puuid]).strip().lower() if col_puuid != -1 and col_puuid < len(r) else ""
        raw_nam = get_main_name(r[col_name] if col_name != -1 and col_name < len(r) else "")
        
        p_key = raw_uid if raw_uid else name_to_puuid_fallback.get(raw_nam, raw_nam)
        
        t_name = r[col_team] if col_team != -1 and col_team < len(r) else ""
        matched_pos = r[col_pos] if col_pos != -1 and col_pos < len(r) else ""
        champ = r[col_champ] if col_champ != -1 and col_champ < len(r) else ""
        res = r[col_res] if col_res != -1 and col_res < len(r) else ""
        
        if not p_key or res not in ["승리", "패배"]: continue
        record_key = f"{g_id}_{p_key}"
        if record_key in processed_records: continue
        processed_records.add(record_key)
        
        if p_key not in player_games:
            player_games[p_key] = []; player_champ_counts[p_key] = {}
        
        safe_bans = ", ".join(game_all_bans.get(g_id, set()))
        player_games[p_key].append({'g_id': g_id, 'champ': champ, 'bans': safe_bans, 'result': res, 'pos': matched_pos, 'team': t_name})
        
        if champ: player_champ_counts[p_key][champ] = player_champ_counts[p_key].get(champ, 0) + 1

        if g_id not in games_dict: games_dict[g_id] = {"블루팀": [], "레드팀": [], "winner": ""}
        if t_name == "블루팀":
            games_dict[g_id]["블루팀"].append(p_key)
            if res == "승리": games_dict[g_id]["winner"] = "블루팀"
        else:
            games_dict[g_id]["레드팀"].append(p_key)
            if res == "승리": games_dict[g_id]["winner"] = "레드팀"

    # 🎯 [v82.32] 견제 압력(Ban Pressure) — "그 사람이 있을 때만 밴되는 챔프" = 클랜이 실제로 무서워하는 픽.
    #   웹(index.html computeBanPressure)과 동일 산식: present − absent×0.5, z>1.5만 유효.
    #   승률·약점밴이 못 잡는 신호(클랜의 집단 학습)를 밴 추천에 반영한다.
    _BP_MIN_CHAMP, _BP_MIN_PRESENT, _BP_MIN_ABSENT = 4, 8, 20
    def _compute_ban_pressure():
        try:
            # ① 게임별 진영·밴 수집(8인 이상 완전 기록만)
            g_side_ban, g_side_of, g_cnt = {}, {}, {}
            for r in data_rows:
                g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
                if not g_id: continue
                uid = str(r[col_puuid]).strip().lower() if col_puuid != -1 and col_puuid < len(r) else ""
                nam = get_main_name(r[col_name] if col_name != -1 and col_name < len(r) else "")
                k = uid if uid else name_to_puuid_fallback.get(nam, nam)
                if not k: continue
                side = r[col_team] if col_team != -1 and col_team < len(r) else ""
                g_side_of.setdefault(g_id, {})[k] = side
                g_cnt[g_id] = g_cnt.get(g_id, 0) + 1
                b = str(r[col_bans] if col_bans != -1 and col_bans < len(r) else "").strip()
                if b and b not in ["밴 없음", "밴 안함", "기록 대기", "결과 대기", "평가 대기", "알수없음"]:
                    g_side_ban.setdefault(g_id, {}).setdefault(side, set()).add(b)
            ginfo = [(gid, g_side_ban[gid], g_side_of.get(gid, {}))
                     for gid in g_side_ban if g_cnt.get(gid, 0) >= 8]
            if not ginfo: return {}
            # ② 선수별 present/absent 분할 → 챔프별 밴율 차이
            out = {}
            for p_key, champs in player_champ_counts.items():
                mains = [(c, n) for c, n in champs.items() if n >= _BP_MIN_CHAMP]
                if not mains: continue
                mains.sort(key=lambda x: -x[1])
                present = [g for g in ginfo if p_key in g[2]]
                absent = [g for g in ginfo if p_key not in g[2]]
                if len(present) < _BP_MIN_PRESENT or len(absent) < _BP_MIN_ABSENT: continue
                for c, n in mains[:6]:
                    ino = 0
                    for _gid, bs, so in present:
                        opp = "레드팀" if so.get(p_key) == "블루팀" else "블루팀"
                        if c in bs.get(opp, set()): ino += 1
                    outo = sum(0.5 for _gid, bs, _so in absent
                               if any(c in s for s in bs.values()))   # 양팀→한팀 스케일 보정
                    a, b_ = ino / len(present), outo / len(absent)
                    se = math.sqrt(max(a * (1 - a), 1e-6) / len(present)
                                   + max(b_ * (1 - b_), 1e-6) / len(absent))
                    z = (a - b_) / se if se > 0 else 0.0
                    if z > 1.5 and (a - b_) > 0:
                        out[(p_key, c)] = {"targeted": (a - b_) * 100, "z": z}
            return out
        except Exception as e:
            print(f"[banpressure] 계산 실패(무시): {e}", flush=True)
            return {}
    ban_pressure_map = _compute_ban_pressure()
    if ban_pressure_map:
        print(f"[banpressure] 유효 견제압력 {len(ban_pressure_map)}건", flush=True)

    stats_dashboard, blue_pool, red_pool = {}, {}, {}
    for p in blue_players + red_players:
        p_puuid = str(p.get('puuid', '')).strip().lower()
        p_name = get_main_name(p.get('name', ''))
        
        p_key = p_puuid if p_puuid else name_to_puuid_fallback.get(p_name, p_name)
        
        p_matches = player_games.get(p_key, [])
        total = len(p_matches)
        
        is_blue = any(str(bp.get('puuid', '')).strip().lower() == p_puuid for bp in blue_players)
        current_pool = blue_pool if is_blue else red_pool

        if total == 0:
            stats_dashboard[p_key] = {"summary": "기록 없음", "most_list": [], "op_list": [], "most_by_pos": {}, "op_by_pos": {}, "fatal_bans": [], "fatal_bans_by_pos": {}, "pos1": "선택안함", "pos2": "선택안함", "streak": "", "streak_val": 0, "overall_wr": 0.5, "games": 0, "side_wr_str": ""}
            continue
        
        wins = sum(1 for m in p_matches if m.get('result') == '승리')
        overall_wr = wins / total
        side_target = '블루팀' if is_blue else '레드팀'
        side_games = sum(1 for m in p_matches if m.get('team') == side_target)
        side_wins = sum(1 for m in p_matches if m.get('team') == side_target and m.get('result') == '승리')
        side_wr_str = f"진영 승률: {round((side_wins/side_games)*100)}% ({side_wins}승 {side_games-side_wins}패)" if side_games > 0 else "진영 승률: 기록없음"

        streak_val = 0
        if p_matches:
            recent_matches = list(reversed(p_matches))
            current_res = recent_matches[0].get('result', '')
            streak_count = 0
            for m in recent_matches:
                if m.get('result') == current_res: streak_count += 1
                else: break
            if current_res == '승리': streak_val = streak_count
            elif current_res == '패배': streak_val = -streak_count

        champ_counts = player_champ_counts.get(p_key, {})
        most_list, op_list, fatal_bans = [], [], []
        user_ban_score = {}
        if champ_counts:
            sorted_champs = sorted(champ_counts.items(), key=lambda x: (-x[1], x[0]))   # [v82.5] 동률 이름순(집계 경로와 동일)
            for c, v in sorted_champs[:8]: most_list.append({"name": c, "count": v})
            most_list = _dedupe_champ_entries(most_list)[:5]   # [시인성] 모스트5까지(초상화 표시)
            for c, v in sorted_champs[:5]:
                c_wins = sum(1 for m in p_matches if m.get('champ') == c and m.get('result') == '승리')
                c_wr = (c_wins / v) * 100
                if v >= 5 and c_wr >= 60.0:   # [시인성] 고승률픽 = 5판↑ + 승률 60%↑
                    op_list.append({"name": c, "wr": c_wr, "count": v})
                    user_ban_score[c] = user_ban_score.get(c, 0) + c_wr + (min(v, 10) * 2)
            
            op_list = _dedupe_champ_entries(op_list)
            top_5_champs = [c for c, _ in sorted_champs[:5]]
            for c in top_5_champs:
                b_games, b_wins = 0, 0
                for m in p_matches:
                    m_gid = m.get('g_id')
                    clean_bans = game_all_bans.get(m_gid, set())
                    if c in clean_bans:
                        b_games += 1
                        if m.get('result') == '승리': b_wins += 1
                if b_games >= 5:   # 약점발견 표본 최소 5판 이상
                    b_wr = b_wins / b_games
                    drop = overall_wr - b_wr
                    if drop >= 0.10:
                        fatal_bans.append({"champ": c, "drop": int(drop * 100), "b_wr": int(b_wr * 100), "b_games": b_games})
                        user_ban_score[c] = user_ban_score.get(c, 0) + (drop * 100) * 1.5 + (min(b_games, 5) * 5)
        
        # 🎯 [v82.32] 견제 압력 가산 — 클랜이 이 사람 상대로만 유독 밴하는 챔프에 점수.
        #   targeted(%p)×2.0 → +16%p면 +32점(약점밴 15%p ≈ 47점과 같은 급).
        bp_list = []
        for _c in champ_counts:
            _bp = ban_pressure_map.get((p_key, _c))
            if _bp:
                user_ban_score[_c] = user_ban_score.get(_c, 0) + _bp["targeted"] * 2.0
                bp_list.append({"champ": _c, "targeted": int(round(_bp["targeted"])), "z": round(_bp["z"], 1)})
        bp_list.sort(key=lambda x: -x["targeted"])

        fatal_bans.sort(key=lambda x: x['drop'], reverse=True)
        if user_ban_score:
            # 플레이어당 상위 3개 위협 챔프를 밴 풀에 누적 → AI 추천 밴 5개가 확실히 채워지도록
            for _c, _sc in sorted(user_ban_score.items(), key=lambda x: x[1], reverse=True)[:3]:
                current_pool[_c] = current_pool.get(_c, 0) + _sc

        # 🎯 [2026-07-08] 포지션별 모스트/고승률픽 (대기실 '현재 선택 포지션' 뷰 토글용)
        most_by_pos, op_by_pos = _compute_pos_champ_lists(p_matches)
        # 🎯 [v83.4] 포지션별 약점 — 이 경로는 원본 로그를 들고 있어 시트 집계 없이 바로 낸다.
        fatal_bans_by_pos = {}
        for _pk in FB_POS_ROLES:
            _pm = [m for m in p_matches if m.get('pos') == _pk]
            if len(_pm) < FB_POS_MIN_GAMES: continue
            _pw = sum(1 for m in _pm if m.get('result') == '승리')
            _pcnt = {}
            for m in _pm:
                _c = m.get('champ')
                if _c: _pcnt[_c] = _pcnt.get(_c, 0) + 1
            _cand = []
            for _c, _n in sorted(_pcnt.items(), key=lambda x: (-x[1], x[0]))[:5]:
                _bm = [m for m in _pm if _c in game_all_bans.get(m.get('g_id'), set())]
                _cand.append((_c, len(_bm), sum(1 for m in _bm if m.get('result') == '승리')))
            _fb = _fatal_bans_pos_entry(len(_pm), _pw, _cand)
            if _fb: fatal_bans_by_pos[_pk] = _fb

        stats_dashboard[p_key] = {
            "summary": f"{total}전 {wins}승 {total-wins}패 ({round(overall_wr*100, 1)}%)",
            "most_list": most_list, "op_list": op_list, "fatal_bans": fatal_bans, "ban_pressure": bp_list,
            "fatal_bans_by_pos": fatal_bans_by_pos,
            "most_by_pos": most_by_pos, "op_by_pos": op_by_pos,
            "streak": "", "streak_val": streak_val, "overall_wr": overall_wr, "games": total, "side_wr_str": side_wr_str
        }

    # 🚫 [v81.76 사장님 지시] 추천 밴 5 → 10개(GUI는 5개씩 2줄)
    blue_advice_list = sorted(red_pool.items(), key=lambda x: x[1], reverse=True)[:10]
    red_advice_list = sorted(blue_pool.items(), key=lambda x: x[1], reverse=True)[:10]
    
    with gui_lock:
        gui_data["blue_ban_advice_list"] = [c for c, _ in blue_advice_list]
        gui_data["red_ban_advice_list"] = [c for c, _ in red_advice_list]

    def calculate_hybrid_power(players_list):
        power_sum = 0
        for p in players_list:
            t_icon = p.get('tier_icon', 'UNRANKED')
            t_score = TIERS.index(t_icon) if t_icon in TIERS else 4
            
            p_uid = str(p.get('puuid', '')).strip().lower()
            p_nam = get_main_name(p.get('name', ''))
            p_key = p_uid if p_uid else name_to_puuid_fallback.get(p_nam, p_nam)
            
            s_data = stats_dashboard.get(p_key, {})
            g = s_data.get('games', 0)
            raw_wr = s_data.get('overall_wr', 0.5)
            # 🔥 베이지안 수축: 판수 적을수록 승률을 50%로 수렴 (작은 표본 노이즈 억제 → 예측 신뢰도↑)
            K = 8
            shrunk_wr = (raw_wr * g + 0.5 * K) / (g + K)
            # 연승/연패 가중치도 판수 적으면 축소 (2판 2연승이 예측을 크게 흔들지 않도록)
            streak_factor = min(1.0, g / 10.0)
            power_sum += ((t_score + shrunk_wr * 10) / 2) + (s_data.get('streak_val', 0) * 0.3 * streak_factor)
        return power_sum

    blue_power, red_power = calculate_hybrid_power(blue_players), calculate_hybrid_power(red_players)
    with gui_lock:
        if blue_power + red_power > 0:
            gui_data["blue_win_rate"] = max(15, min(85, int(50 + ((blue_power - red_power) * 4))))
            gui_data["red_win_rate"] = 100 - gui_data["blue_win_rate"]
        else:
            gui_data["blue_win_rate"] = 50; gui_data["red_win_rate"] = 50

    pos_alerts, neg_alerts, nemesis_alerts = [], [], []
    for team_players, t_name, opp_name in [(blue_players, '블루팀', '레드팀'), (red_players, '레드팀', '블루팀')]:
        for i in range(len(team_players)):
            for j in range(i + 1, len(team_players)):
                p1_uid = str(team_players[i].get('puuid', '')).strip().lower()
                p1_name = get_main_name(team_players[i].get('name', ''))
                p1_key = p1_uid if p1_uid else name_to_puuid_fallback.get(p1_name, p1_name)
                
                p2_uid = str(team_players[j].get('puuid', '')).strip().lower()
                p2_name = get_main_name(team_players[j].get('name', ''))
                p2_key = p2_uid if p2_uid else name_to_puuid_fallback.get(p2_name, p2_name)
                
                if p1_key and p2_key and p1_key != p2_key and not p1_uid.startswith('bot_'):
                    dg, dw = 0, 0
                    for g_data in games_dict.values():
                        if p1_key in g_data[t_name] and p2_key in g_data[t_name]:
                            dg += 1; dw += 1 if g_data['winner'] == t_name else 0
                    if dg >= 10: 
                        dwr = (dw/dg)*100
                        p1_d, p2_d = str(team_players[i]['name']).split('#')[0], str(team_players[j]['name']).split('#')[0]
                        # [v81.78 사장님 지시] 시너지 조건 완화 — 고승률 65% → 60% (역시너지는 기존 35% 유지)
                        if dwr <= 40.0: neg_alerts.append(f" ⚠ {p1_d} & {p2_d} {round(dwr)}%")
                        elif dwr >= 60.0: pos_alerts.append(f" 🔥 {p1_d} & {p2_d} {round(dwr)}%")

    for b_p in blue_players:
        b_uid = str(b_p.get('puuid', '')).strip().lower()
        b_name = get_main_name(b_p.get('name', ''))
        b_key = b_uid if b_uid else name_to_puuid_fallback.get(b_name, b_name)
        if not b_key or "bot_" in b_uid: continue
        
        for r_p in red_players:
            r_uid = str(r_p.get('puuid', '')).strip().lower()
            r_name = get_main_name(r_p.get('name', ''))
            r_key = r_uid if r_uid else name_to_puuid_fallback.get(r_name, r_name)
            if not r_key or "bot_" in r_uid or b_key == r_key: continue
            
            hg, bw = 0, 0
            for g_data in games_dict.values():
                if b_key in g_data['블루팀'] and r_key in g_data['레드팀']: hg += 1; bw += 1 if g_data['winner'] == '블루팀' else 0
                elif b_key in g_data['레드팀'] and r_key in g_data['블루팀']: hg += 1; bw += 1 if g_data['winner'] == '레드팀' else 0
            if hg >= 10:
                wr = (bw / hg) * 100
                b_disp, r_disp = str(b_p['name']).split('#')[0], str(r_p['name']).split('#')[0]
                # 🗣 [2026-08-16 사장님 지시] "A ➡ B 27%" 는 누가 앞서는지 읽는 사람마다 달랐다.
                #    강한 쪽을 앞에 두고 조사+전적으로 문장을 만든다 — "레멍이가 wei ha 상대로 8승 3패".
                #    (기존 5:5 표기는 6승 6패여도 '5:5'로 찍히던 오표기도 겸사겸사 수정)
                if wr <= 30.0: nemesis_alerts.append(f" 💀 {r_disp}{_ga(r_disp)} {b_disp} 상대로 {hg - bw}승 {bw}패")
                elif wr >= 70.0: nemesis_alerts.append(f" 💀 {b_disp}{_ga(b_disp)} {r_disp} 상대로 {bw}승 {hg - bw}패")
                elif bw == (hg - bw): nemesis_alerts.append(f" ⚔ {b_disp} 🆚 {r_disp} {bw}승 {bw}패 호각")

    return stats_dashboard, pos_alerts, neg_alerts, nemesis_alerts

def get_lcu_credentials():
    lf = _find_lol_lockfile()
    if not lf: return None, None
    try:
        with open(lf, "r") as f: content = f.read()
        parts = content.split(":")
        return parts[2], parts[3]
    except Exception: return None, None

def build_translation_map(port, password):
    raw_token = "riot:" + str(password)
    encoded_token = base64.b64encode(raw_token.encode('utf-8')).decode('utf-8')
    headers = {"Authorization": "Basic " + encoded_token, "Accept": "application/json"}
    champ_map = {}
    try:
        url = "https://127.0.0.1:" + str(port) + "/lol-game-data/assets/v1/champions.json"
        res = requests.get(url, headers=headers, verify=False, timeout=3)
        if res.status_code == 200:
            for c in res.json(): 
                if isinstance(c, dict) and c.get('id') is not None:
                    try:
                        c_id = int(c['id'])
                        champ_map[c_id] = {"kor": c.get('name', ''), "eng": c.get('alias', '')}
                        global_champ_map[c_id] = champ_map[c_id]
                    except (ValueError, TypeError): pass
    except Exception: pass
    if not champ_map: champ_map = global_champ_map.copy()
    return champ_map

def send_lcu_chat_announcement(message, headers, base_url):
    try:
        res = requests.get(str(base_url) + "/lol-chat/v1/conversations", headers=headers, verify=False, timeout=2)
        if res.status_code == 200:
            convs = res.json()
            if isinstance(convs, list):
                for conv in convs:
                    if isinstance(conv, dict) and conv.get('type') in ['customGame', 'lobby']:
                        c_id = conv.get('id')
                        url = str(base_url) + "/lol-chat/v1/conversations/" + str(c_id) + "/messages"
                        requests.post(url, headers=headers, json={"body": message, "type": "chat"}, verify=False, timeout=2)
                        break
    except Exception: pass

# ===== 👑 팀장뽑기 (2026-08-06 사장님 지시) =====
#   내전 방 인원 중 전력이 가장 비슷한 2명을 팀장으로 자동 선정해 팀원뽑기를 시킨다.
#   · 직전 판 팀장은 후보에서 제외(두 판 연속 방지가 관건) — 후보가 모자라면 제외 대신 큰 감점으로 완화
#   · 주포지션 고려: 두 팀장의 주포지션이 같으면 가산(같을 필요는 없음 — 같으면 남는 포지션 풀이 대칭)
_CAPTAIN_STATE_FILE = os.path.join(CONFIG_DIR, 'captains_recent.json')

def _captain_recent_load():
    """직전 판 팀장 tnorm 목록. 6시간 지나면 다른 날 내전으로 보고 리셋."""
    try:
        with open(_CAPTAIN_STATE_FILE, encoding='utf-8') as f: d = json.load(f)
        if time.time() - float(d.get('at', 0)) > 6 * 3600: return []
        return [str(x) for x in (d.get('last') or [])]
    except Exception: return []

def _captain_recent_save(pair_tnorms):
    try:
        if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
        with open(_CAPTAIN_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last': list(pair_tnorms), 'at': time.time()}, f, ensure_ascii=False)
    except Exception: pass

def _captain_power(p, s):
    """개인 전력 스칼라 — 예상 승률과 같은 공식(calculate_hybrid_power의 1인분)에 내부티어를 절반 섞는다."""
    t_icon = (p or {}).get('tier_icon', 'UNRANKED')
    t_score = TIERS.index(t_icon) if t_icon in TIERS else 4
    s = s or {}
    g = s.get('games', 0); raw_wr = s.get('overall_wr', 0.5)
    K = 8
    shrunk = (raw_wr * g + 0.5 * K) / (g + K)
    pw = (t_score + shrunk * 10) / 2 + s.get('streak_val', 0) * 0.3 * min(1.0, g / 10.0)
    tv = tier_of((p or {}).get('name') or '')
    if tv in TIER_ORDER_LIST:            # 클랜 공식 사다리(내부티어)가 있으면 그쪽을 절반 가중
        pw = pw * 0.5 + (9 - TIER_ORDER_LIST.index(tv)) * 0.5
    return pw

def _captain_main_pos(p, cidx):
    """주포지션 — 클랜 시트 전적의 최다 포지션 우선, 없으면 로비에서 고른 포지션."""
    try:
        e = ((cidx or {}).get('by_pu') or {}).get(str((p or {}).get('puuid') or '').strip().lower())
        if e and e.get('pos'): return max(e['pos'].items(), key=lambda x: x[1])[0]
    except Exception: pass
    return str((p or {}).get('chosen_pos_icon') or '')

def _captain_pick(entries, exclude_tnorms, cidx):
    """entries=[(player,stats)...] → (a, b, 사유) 또는 (None, None, 안내문). a/b={'nm','tn','pw','pos'}"""
    cand = []
    for p, s in entries:
        nm = str((p or {}).get('name') or '').strip()
        if not nm: continue
        if str((p or {}).get('puuid') or '').startswith('BOT_'): continue   # 연습봇 제외
        cand.append({'nm': nm, 'tn': tnorm(nm), 'pw': _captain_power(p, s),
                     'pos': _captain_main_pos(p, cidx), 'tier': tier_of(nm) or ''})
    if len(cand) < 4:
        return None, None, f"방 인원이 부족해요({len(cand)}명) — 4명부터 뽑을 수 있어요"
    hard = [c for c in cand if c['tn'] not in exclude_tnorms]
    soft = len(hard) < 2      # 직전 팀장을 빼면 2명이 안 남는 극단 상황 — 감점으로 완화(되도록 회피)
    pool = cand if soft else hard
    best = None
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            a, b = pool[i], pool[j]
            sc = abs(a['pw'] - b['pw'])
            if a['pos'] and a['pos'] == b['pos']: sc -= 0.6
            if soft:
                sc += 2.5 * ((a['tn'] in exclude_tnorms) + (b['tn'] in exclude_tnorms))
            if best is None or sc < best[0]: best = (sc, a, b)
    _, a, b = best
    why = [f"전력차 {abs(a['pw'] - b['pw']):.1f}"]
    if a['pos'] and a['pos'] == b['pos']: why.append(f"주포지션 동일({a['pos']})")
    elif a['pos'] or b['pos']: why.append(f"주포지션 {a['pos'] or '?'}·{b['pos'] or '?'}")
    if exclude_tnorms and not soft: why.append("직전 판 팀장 제외")
    return a, b, " · ".join(why)


# ===== 🚫 노밴 감지(v82.41 사장님 지시) — 커스텀 로비 채팅의 '노밴' 선언을 읽어 기록·코치 반영 =====
#   선언 흐름: 진행자 "노밴" → (3333/2222 준비신호) → 각 팀 대표가 챔피언명 선언(초성 "ㅋㅇㄴ"=키아나,
#   축약 "블츠"=블리츠크랭크 등) 또는 거절("없음"/"x"/"ㅌㅌㅌ"/무응답). 감지분은 게임시작 웹훅 기록 + 코치 밴 제외.
_NB_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_NB_JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ",
            "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

def _nb_jamo(s):
    """한글 문자열 → (초성열, 자음열[초성+종성]). 비한글 문자는 그대로 통과."""
    cho, full = [], []
    for ch in s:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            c = _NB_CHO[o // 588]
            cho.append(c); full.append(c)
            j = _NB_JONG[o % 28]
            if j: full.append(j)
        else:
            cho.append(ch); full.append(ch)
    return "".join(cho), "".join(full)

# 자주 쓰는 축약 별칭(퍼지 매칭이 못 잡거나 모호한 것만 — 나머지는 접두/부분수열/초성이 커버)
_NB_ALIAS = {"블츠": "블리츠크랭크", "블크": "블리츠크랭크", "트페": "트위스티드 페이트", "미포": "미스 포츈",
             "아우솔": "아우렐리온 솔", "문도": "문도 박사", "케틀": "케이틀린", "그브": "그레이브즈",
             "마이": "마스터 이", "트타": "트리스타나", "하이머": "하이머딩거", "노틸": "노틸러스",
             "럼블이": "럼블", "쓰레기": "쓰레쉬"}
# 노밴 안 함 선언 패턴 — 챔피언으로 오인하면 안 됨
_NB_DECLINE = None   # 지연 컴파일(re 임포트 위치 무관)

def resolve_champ_decl(txt, champs, played=None):
    """채팅 선언 → 챔피언 한글명(없으면 None).
       우선순위: 완전일치 > 별칭 > 초성열 일치 > 자음열(종성 포함) 일치 > 접두 > 음절 부분수열.
       동률이면 '선언자가 실제로 해본 챔프' 우선(ㅋㅇㄴ: 키아나 vs 케인 같은 충돌 해소), 최후엔 짧은 이름."""
    global _NB_DECLINE
    if _NB_DECLINE is None:
        _NB_DECLINE = re.compile(r"^(없음|없어요?|없다|노|no|pass|패스|[xX.~!?]+|[ㅌ]+|ㄴㄴ+|ㄴㅇ)$", re.I)
    t = "".join(str(txt or "").split()).strip(".!?~;:")
    if not t or len(t) > 12: return None
    if _NB_DECLINE.match(t): return None
    if len(set(t)) == 1 and len(t) >= 2 and t[0] in "ㅋㅎㅠㅜzZ": return None   # ㅋㅋㅋ/ㅎㅎ 웃음
    norm = {c: "".join(str(c).split()) for c in champs if c}
    low = t.lower()
    for c, n in norm.items():
        if low == n.lower(): return c
    a = _NB_ALIAS.get(t)
    if a:
        an = "".join(a.split())
        for c, n in norm.items():
            if n == an: return c
    def _pick(cands):
        if not cands: return None
        if len(cands) == 1: return cands[0]
        pl = played or set()
        hit = [c for c in cands if c in pl]
        if len(hit) == 1: return hit[0]
        if hit: cands = hit
        return sorted(cands, key=lambda c: len(norm[c]))[0]
    if re.fullmatch(r"[ㄱ-ㅎ]{2,}", t):
        r = _pick([c for c, n in norm.items() if _nb_jamo(n)[0] == t])       # ①초성열(사람들이 주로 치는 형태)
        if r: return r
        return _pick([c for c, n in norm.items() if _nb_jamo(n)[1] == t])    # ②종성 포함 자음열
    if len(t) >= 2:
        pref = _pick([c for c, n in norm.items() if n.startswith(t)])
        if pref: return pref
        def _subseq(small, big):
            it = iter(big)
            return all(ch in it for ch in small)
        return _pick([c for c, n in norm.items() if _subseq(t, n)])
    return None

def _noban_sheet_push(game_id, date_str):
    """🚫 감지된 노밴 선언을 NOBAN 탭에 적재(웹 노밴률·게임 상세 표시용). 기록 append 승자만 호출(중복 방지).
       1회 시도 원칙(쿼터 보호 — v81.72 교훈), 실패는 무해(디코 리포트에는 어차피 남음)."""
    try:
        if not _NOBAN.get("decls") or global_spreadsheet is None: return
        try:
            ws = global_spreadsheet.worksheet("NOBAN")
        except Exception:
            ws = global_spreadsheet.add_worksheet(title="NOBAN", rows="1000", cols="3")
            ws.update(values=[["게임ID", "날짜", "챔피언"]], range_name="A1")
        ws.append_rows([[str(game_id), date_str, c] for c in _NOBAN["decls"]])
        print(f"[noban] NOBAN 탭 적재 — {len(_NOBAN['decls'])}건 (게임 {game_id})", flush=True)
    except Exception as e:
        print(f"[noban] 시트 적재 실패(무시): {e}", flush=True)

_NOBAN = {"decls": [], "trig": False, "conv": None, "seen": set(), "names": {}, "last": 0.0, "r1": False, "r2": False}
# 🔚 막판자 조사(같은 로비 채팅 의식) — 진행자 "막판(조사)" → 카운트다운(3/2/1) 중 '.'(오타 ',' 포함) 타이핑 = 막판 선언
_MAKPAN = {"decls": [], "trig": False}

def _noban_reset():
    _NOBAN.update({"decls": [], "trig": False, "conv": None, "seen": set(), "names": {}, "r1": False, "r2": False})
    _MAKPAN.update({"decls": [], "trig": False})

def _nb_played(who):
    try:
        return {c for c, _g, _w in (_my_champ_pool(who) or [])}
    except Exception:
        return set()

def noban_tick(headers, base_url, phase):
    """Lobby/ChampSelect에서 2초 간격으로 커스텀 로비 채팅을 읽어 노밴 선언 수집(히스토리 소급이라 순간 놓침 없음)."""
    try:
        if phase not in ("Lobby", "ChampSelect", "Matchmaking"):
            # [2026-07-25] 결과 리포트가 선언을 부착하므로 종료 직후엔 유지 — 마지막 로비활동 10분 뒤(None)에만 초기화.
            #   (다음 판 로비 진입 시엔 대화방 id 변경으로 어차피 리셋됨)
            if phase == "None" and (_NOBAN["decls"] or _NOBAN["trig"] or _MAKPAN["decls"]) \
               and time.time() - _NOBAN.get("ts", 0) > 600:
                _noban_reset()
            return
        now = time.time()
        if now - _NOBAN["last"] < 2: return   # [v82.41] 2초 간격 — '선언 직후 1초 만에 게임시작' 경합창 최소화
        _NOBAN["last"] = now
        _NOBAN["ts"] = now   # 로비 활동 시각(초기화 유예 기준)
        res = requests.get(str(base_url) + "/lol-chat/v1/conversations", headers=headers, verify=False, timeout=2)
        if res.status_code != 200:
            if now - _NOBAN.get("diag", 0) > 30:
                _NOBAN["diag"] = now; print(f"[noban] conversations HTTP {res.status_code}", flush=True)
            return
        _all = [c for c in (res.json() or []) if isinstance(c, dict)]
        # [v82.42] 타입명('customGame' 등)은 클라 버전에 따라 다를 수 있음 → 대화방 id 패턴으로도 이중 판정
        def _cand(c):
            t = str(c.get("type") or ""); i = str(c.get("id") or "")
            return (t in ("customGame", "lobby", "championSelect")
                    or "sec.pvp.net" in i or "champ-select" in i)
        convs = [c for c in _all if _cand(c)]
        if not convs:
            if now - _NOBAN.get("diag", 0) > 30:   # 진단: 어떤 대화방들이 보이는지 30초마다 1회
                _NOBAN["diag"] = now
                print("[noban] 후보 대화방 없음 — 보이는 대화방: "
                      + (", ".join(f"{c.get('type')}:{str(c.get('id'))[-22:]}" for c in _all[:8]) or "없음"), flush=True)
            return
        conv = sorted(convs, key=lambda c: str(c.get("type")) != "customGame")[0]   # 로비 채팅 우선
        cid = conv.get("id")
        if _NOBAN["conv"] not in (None, cid) and conv.get("type") != "championSelect":
            _noban_reset()                                       # 새 로비 → 이전 판 선언 폐기
        if _NOBAN["conv"] is None or conv.get("type") != "championSelect":
            _NOBAN["conv"] = cid
        try:
            pres = requests.get(str(base_url) + "/lol-chat/v1/conversations/" + str(cid) + "/participants",
                                headers=headers, verify=False, timeout=2)
            if pres.status_code == 200:
                for p in (pres.json() or []):
                    if isinstance(p, dict) and p.get("id"):
                        _NOBAN["names"][str(p["id"])] = str(p.get("gameName") or p.get("name") or "")
        except Exception: pass
        mres = requests.get(str(base_url) + "/lol-chat/v1/conversations/" + str(cid) + "/messages",
                            headers=headers, verify=False, timeout=2)
        if mres.status_code != 200:
            if now - _NOBAN.get("diag", 0) > 30:
                _NOBAN["diag"] = now; print(f"[noban] messages HTTP {mres.status_code} (conv {str(cid)[-22:]})", flush=True)
            return
        # [v82.42] 챔프맵이 비어도 트리거·막판조사는 동작해야 함 — 챔피언 해석 단계에서만 스킵
        champs = [v.get("kor") for v in global_champ_map.values() if isinstance(v, dict) and v.get("kor")]
        for m in (mres.json() or []):
            if not isinstance(m, dict): continue
            mid = str(m.get("id") or "") or (str(m.get("timestamp")) + "|" + str(m.get("fromId")))
            if mid in _NOBAN["seen"]: continue
            _NOBAN["seen"].add(mid)
            body = str(m.get("body") or "").strip()
            if not body: continue
            nb = body.replace(" ", "")
            who = (_NOBAN["names"].get(str(m.get("fromId") or "")) or
                   str(m.get("fromSummonerName") or "")).split("#")[0].strip()
            if "노밴" in nb:
                _NOBAN["trig"] = True; _NOBAN["decls"] = []      # 재선언 시 목록 리셋
                continue
            # [v82.43 사장님 제보] 실제 의식: '노밴'은 음성으로만 외치고 채팅엔 팀 준비신호만 —
            #   1팀 완료 = "1ㅇ", 2팀 완료 = "2ㅇ". 둘 다 찍히면 노밴 카운트 모드 진입.
            if nb.lower() in ("1ㅇ", "1o", "1이", "1엥"): _NOBAN["r1"] = True; continue
            if nb.lower() in ("2ㅇ", "2o", "2이", "2엥"): _NOBAN["r2"] = True; continue
            if _NOBAN["r1"] and _NOBAN["r2"] and not _NOBAN["trig"]:
                _NOBAN["trig"] = True; _NOBAN["decls"] = []
                print("[noban] 양팀 준비(1ㅇ·2ㅇ) 감지 — 노밴 카운트 모드 진입", flush=True)
            if "막판" in nb:                                      # 🔚 막판(조사) 개시 — 재선언 시 리셋
                _MAKPAN["trig"] = True; _MAKPAN["decls"] = []
                continue
            if _MAKPAN["trig"]:
                if re.fullmatch(r"[.,·]+", nb):                   # '.' 선언(오타 ',' 포함)
                    if who and who not in _MAKPAN["decls"]:
                        _MAKPAN["decls"].append(who)
                        print(f"[makpan] 막판 선언 — {who} <- '{body}'", flush=True)
                    continue
                if re.fullmatch(r"\d+명", nb):                # 'N명' 집계 → 조사 종료
                    _MAKPAN["trig"] = False
                    print(f"[makpan] 조사 종료 — {len(_MAKPAN['decls'])}명: {', '.join(_MAKPAN['decls'])}", flush=True)
                    continue
            if not _NOBAN["trig"]: continue
            if re.fullmatch(r"[\d\s]+", body): continue           # 3333/2222 준비 신호·카운트다운
            champ = resolve_champ_decl(body, champs, _nb_played(who))   # who는 동률 해소에만 사용(기록 안 함)
            if champ and champ not in _NOBAN["decls"]:
                _NOBAN["decls"].append(champ)
                print(f"[noban] 선언 감지 — {champ} <- '{body}' (by {who or '?'})", flush=True)
        if len(_NOBAN["seen"]) > 3000: _NOBAN["seen"] = set(list(_NOBAN["seen"])[-500:])
    except Exception: pass

# =========================================================================
# 🚫 V80.9 백엔드 루프
# =========================================================================
def connect_sheet():
    """구글 시트 연결. 성공 시 global_spreadsheet 설정 후 True, 실패(429 등) 시 None 후 False.
       시작 시 한 번 실패해도 루프에서 주기적으로 재시도 → 영구 오프라인 방지.
       [v81.62] 함수 내 3회 재시도(4~10s 지터) — open_by_key가 실제 메타데이터 읽기(공유 분당 quota 소모)라
       동시시작 버스트·순간 네트워크 블립 1회로 곧장 '시트 연결 실패' 배너가 뜨던 간헐 문제 흡수(백엔드 스레드라 GUI 무영향)."""
    global global_spreadsheet
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    for _ctry in range(3):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(resource_path('credentials.json.json'), scope)
            client = gspread.authorize(creds)
            global_spreadsheet = client.open_by_key(DOCUMENT_ID)
            try:
                link_sheet = global_spreadsheet.worksheet("LINK_ACCOUNT")
                for r in link_sheet.get_all_values()[1:]:
                    if len(r) >= 2 and r[0].strip() and r[1].strip():
                        global_alt_map[r[1].strip().split('#')[0].lower()] = r[0].strip()
            except Exception: pass
            try: load_clan_tiers()   # 내부티어 SSOT: CLAN_TIERS 시트에서 로드(하드코딩 폴백)
            except Exception: pass
            try: load_clan_positions()   # 선언 포지션(디스코드 역할 → CLAN_POSITIONS 시트) 로드
            except Exception: pass
            return True
        except Exception:
            if _ctry < 2: time.sleep(4 + random.uniform(0, 6))
    global_spreadsheet = None
    return False

def lcu_core_backend_loop():
    global gui_data, global_captured_bans, global_user_ban_map, frozen_user_bans, global_spreadsheet, frozen_bans_str, global_ingame_names, global_puuid_fallback_map, PATCH_VERSION_SHORT, has_logged_execution, global_discord_id, global_pick_order_map, frozen_pick_order, global_lock_champ_map, frozen_lock_champ
    # 시작 동시부하 분산: 여러 클랜원이 동시에 켜도 인스턴스별 0~24초 지터로 시트 API 버스트 완화(429 방지)
    try: time.sleep(os.getpid() % 25)
    except Exception: pass
    # 시트 연결 (실패해도 아래 while 루프에서 자동 재연결)
    if connect_sheet():
        if load_bot_token():   # [429완화] HOF 전체읽기(큰 시트)는 호스트만 시작 프리로드 — 일반 멤버는 전당/티어 창 열 때 지연 로드(시작 읽기 버스트↓)
            threading.Thread(target=update_hof_stats, daemon=True).start()
    else:
        with gui_lock:
            gui_data["status"] = "⚠ 시트 연결 실패 (오프라인 모드 · 자동 재시도 중)"

    champ_map = {}
    last_lobby_fingerprint, last_chat_game_id = "", ""
    recorded_game_ids = set()
    appended_game_ids = set()            # 🔒 [중복방지] 이 인스턴스가 '실제로 append'한 게임ID(=기록 주체) → 웹훅도 이 인스턴스만 발송
    posted_game_ids = set()              # 🔔 [웹훅] 이 인스턴스가 결과 웹훅을 이미 보낸 게임ID (게임당 1회, cells_to_update 무관)
    announced_starts = set()             # 🎬 게임 시작 웹훅을 이미 보낸 게임ID (게임당 1회 발송)
    announced_ends = set()               # 🏁 [2026-07-07] 경기 종료 웹훅을 이미 보낸 게임ID (봇 종료신호, 인스턴스당 게임당 1회)
    nonclan_games = set()                # 🚧 [2026-08-11] 클랜원 0명이라 기록을 건너뛴 게임ID (로그 1회만)
    game_seq = 0                         # 🔢 게임 진입 카운터 (커스텀게임 gameId=0일 때 판별 — 같은멤버 연속게임 중복기록 방지)
    _gid_wait = {}                       # 👥 로스터해시 -> 게임ID 조회 첫 실패 시각 — 합성 ID 폴백 90초 유예용
    was_in_prog = False                  #    이전 루프가 InProgress였나 (전환 감지용)
    last_known_phase = "None"            # [V81.48] gameflow-phase 폴링 실패 시 직전 phase 유지(헛플립→game_seq 드리프트 방지)
    _roster_wait_since = {}              # [V81.48] 게임ID별 '완전 로스터 대기 시작 시각'(파편 append 방지 게이트용)
    _cs_since = [0.0]                    # 🧭 [2026-07-29] 밴픽 진입 시각 — 진입 직후 몇 초는 로비를 더 읽어 포지션 정정
    active_recording_id = None
    active_recording_sheet_name = None   # 🔥 기록 시작 시점의 시트(KIWI/CLASSIC) 고정 — finalize가 엉뚱한 시트에 쓰는 것 방지
    eog_retry_count = 0
    eog_write_retry = 0                  # [V81.45] finalize '읽기 stale(행 가시성)' 재시도 카운터
    _fin_write_retry = 0                 # [2026-07-07] finalize 'update_cells 쓰기' 전용 재시도 카운터(가시성 대기와 예산 분리)
    eog_block_cache = None               # 🔥 [V81.24] 종료화면 진입 즉시 캡처한 '이 게임'의 전광판(전원) = {gid, data}
    EOG_MIN_ROSTER = 6                   #    완전 로스터로 인정하는 최소 인원
    last_sheet_reconnect = time.time()   # 🔁 시트 자동 재연결 throttle
    reconnect_fail = 0                    # [429완화] 재접속 지수 백오프 카운터 (악순환 차단)
    last_hof_refresh = time.time()        # 🩸 십이귀월 자동감지용 주기 HOF 갱신(호스트만)
    
    last_ping_time = 0
    global_my_puuid = ""
    
    is_aram_session = False
    _mode_logged = set()                 # 🧭 [2026-07-30] 모드 정보를 게임당 한 번만 로그로 남기기 위한 표시
    global_cached_blue = []
    global_cached_red = []
    global_pos_map = {}

    while True:
        try:
            port, password = get_lcu_credentials()
            if port and not champ_map: champ_map = build_translation_map(port, password)
            # 🔁 시트 연결 자동복구: 429로 실패 시 지수 백오프(45s→90→180→360→720→900cap)로 재시도 → 다같이 하염없이 재시도하는 악순환 차단
            # [v81.62] 첫 재연결만 12초 특례(+지터) — 순간 블립 후 '실패' 배너가 최소 45초+ 고착되던 체감 문제 단축(두 번째 실패부터 기존 백오프).
            if global_spreadsheet is None:
                _rc_delay = (12 if reconnect_fail == 0 else min(45 * (2 ** reconnect_fail), 900)) + (os.getpid() % 30)
                if time.time() - last_sheet_reconnect > _rc_delay:
                    last_sheet_reconnect = time.time()
                    if connect_sheet():
                        reconnect_fail = 0
                        with gui_lock: gui_data["status"] = "✅ 시트 재연결됨"
                        if load_bot_token():   # HOF 프리로드는 호스트만(일반 멤버는 창 열 때 지연 로드)
                            threading.Thread(target=update_hof_stats, daemon=True).start()
                    else:
                        reconnect_fail = min(reconnect_fail + 1, 5)
            # 🩸 십이귀월 자동 감지: 호스트에서 15분마다 HOF 재갱신 → update_hof_stats 끝에서 로스터 변동 체크·웹훅
            # [v82.42 사장님 지시] 인게임 중엔 무거운 집계(시트 전체 파싱) 유예 — 저사양 PC 프레임 드랍 방지(게임 끝나면 다음 주기에 자연 실행)
            if (global_spreadsheet is not None and time.time() - last_hof_refresh > 900 and load_bot_token()
                    and last_known_phase not in ("GameStart", "InProgress", "Reconnect")):
                last_hof_refresh = time.time()
                threading.Thread(target=update_hof_stats, args=(True,), daemon=True).start()
            # 📊 [v81.96] 사전집계 재계산 — 호스트만(load_bot_token), 20분 주기, 데몬(폴링 지연 없음)
            if global_spreadsheet is not None and time.time() - _STAT_LAST_REBUILD[0] > 1200 and load_bot_token():
                _STAT_LAST_REBUILD[0] = time.time()
                threading.Thread(target=rebuild_stat_aggregate, daemon=True).start()
            if not port:
                with gui_lock:
                    if "오프라인" not in gui_data["status"]: gui_data["status"] = "💤 롤 클라이언트를 실행해 주세요."
                time.sleep(2)
                continue

            raw_token = "riot:" + str(password)
            encoded_token = base64.b64encode(raw_token.encode('utf-8')).decode('utf-8')
            headers = {"Authorization": "Basic " + encoded_token, "Accept": "application/json"}
            base_url = "https://127.0.0.1:" + str(port)

            # 🔥 [V80.9] 롤 LCU 내부 통신망에서 오피셜 현재 패치 버전 강제 추출
            try:
                ver_res = requests.get(str(base_url) + "/lol-patch/v1/game-version", headers=headers, verify=False, timeout=2)
                if ver_res.status_code == 200:
                    local_ver = ver_res.json()
                    if local_ver and "." in local_ver:
                        parts = str(local_ver).replace('"', '').split(".")
                        if len(parts) >= 2:
                            PATCH_VERSION_SHORT = f"{parts[0]}.{parts[1]}"
            except Exception: pass

            if not global_my_puuid or time.time() - last_ping_time > 180:
                try:
                    curr_res = requests.get(str(base_url) + "/lol-summoner/v1/current-summoner", headers=headers, verify=False, timeout=2)
                    if curr_res.status_code == 200:
                        c_data = curr_res.json()
                        c_name = str(c_data.get('gameName', '')) + "#" + str(c_data.get('tagLine', ''))
                        global_my_puuid = c_data.get('puuid', '').strip().lower()
                        if c_data.get('gameName'): MY_RIOT_NAME[0] = c_name   # 🩺 버전 하트비트용 내 계정 식별자
                        # 🏅 [v81.31 보류] 직전시즌 솔랭 앵커 반영 기능 잠정 중단.
                        # 사유: 애초 요청은 "직전시즌 최고점(맥시멈)"이었으나 LCU current-ranked-stats의
                        # previousSeasonEndTier는 "시즌 종료 시점" 값이라 개념이 달랐고(실측: 다이아3=2500점,
                        # 실제 최고점은 마스터), 진짜 최고점 필드(/lol-regalia/v2/.../regalia의
                        # lastSeasonHighestRank)는 LP가 없고 솔로/자유 랭크 중 어느 큐 값인지 구분이 안 돼
                        # 정확한 솔로랭크 전용 캡처가 불가능함(2026-07-01 실측 확인). 함수(_prev_season_from_ranked/
                        # save_prev_seasons/_load_prev_seasons)는 남겨두되 호출은 꺼서 v81.28 이전(현재시즌 점수만
                        # 사용)으로 복귀. 더 나은 데이터 소스가 생기면 여기 재활성화.
                        # try:
                        #     _my = str(c_data.get('gameName', '')).strip()
                        #     if _my and tnorm(_my) not in _PREV_SEASON_CACHE:
                        #         _rs = requests.get(str(base_url) + "/lol-ranked/v1/current-ranked-stats", headers=headers, verify=False, timeout=3)
                        #         if _rs.status_code == 200:
                        #             _pt, _psc = _prev_season_from_ranked(_rs.json() or {})
                        #             if _psc is not None:
                        #                 _PREV_SEASON_CACHE[tnorm(_my)] = (_my, _pt, _psc)
                        #                 print(f"[prev-season] {_my} 직전시즌 {_pt} ({_psc}점) 캡처", flush=True)
                        #                 if global_spreadsheet:
                        #                     try: save_prev_seasons()
                        #                     except Exception: pass
                        # except Exception: pass
                        if global_discord_id is None:   # 디스코드ID 1회 자동 획득 (롤닉↔디스코드 매핑용)
                            try: global_discord_id = get_discord_user_id()
                            except Exception: global_discord_id = None

                        if global_my_puuid and global_spreadsheet:
                            try: on_sheet = global_spreadsheet.worksheet("ONLINE_USERS")
                            except Exception:
                                on_sheet = global_spreadsheet.add_worksheet(title="ONLINE_USERS", rows="1000", cols="5")
                                on_sheet.append_row(["닉네임", "PUUID", "마지막접속시간", "누적사용시간(분)", "디스코드ID"])
                            
                            records = get_sheet_data_cached(on_sheet, force=False)   # [V81.45] 3분 주기 접속기록에 강제읽기 불필요(캐시 240s) — 쿼터 절약

                            if records and len(records[0]) < 5:
                                try:
                                    cells_to_add = []
                                    if len(records[0]) < 4: cells_to_add.append(gspread.Cell(row=1, col=4, value="누적사용시간(분)"))
                                    if len(records[0]) < 5: cells_to_add.append(gspread.Cell(row=1, col=5, value="디스코드ID"))
                                    if cells_to_add:
                                        on_sheet.update_cells(cells_to_add)
                                        invalidate_sheet_cache("ONLINE_USERS")
                                        records = get_sheet_data_cached(on_sheet, force=True)
                                except Exception: pass
                                
                            headers_row = records[0] if records else ["닉네임", "PUUID", "마지막접속시간", "누적사용시간(분)", "디스코드ID"]
                            time_col = headers_row.index("마지막접속시간") if "마지막접속시간" in headers_row else 2
                            usage_col = headers_row.index("누적사용시간(분)") if "누적사용시간(분)" in headers_row else 3
                            exec_col = headers_row.index("실행횟수") if "실행횟수" in headers_row else 4
                            dc_col = headers_row.index("디스코드ID") if "디스코드ID" in headers_row else 4

                            found = False
                            current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
                            row_idx_to_update = -1
                            
                            for idx, row in enumerate(records):
                                if len(row) > 1 and row[1] == global_my_puuid:
                                    row_idx_to_update = idx + 1
                                    found = True; break
                                    
                            if found and row_idx_to_update > 1:
                                row_data = records[row_idx_to_update - 1]
                                try: exec_count = int(row_data[exec_col]) if len(row_data) > exec_col and str(row_data[exec_col]).isdigit() else 0
                                except: exec_count = 0
                                try: total_mins = int(row_data[usage_col]) if len(row_data) > usage_col and str(row_data[usage_col]).isdigit() else 0
                                except: total_mins = 0
                                
                                if not has_logged_execution:
                                    exec_count += 1
                                    has_logged_execution = True
                                    
                                if last_ping_time > 0: 
                                    total_mins += 3
                                    
                                try:
                                    cells = [
                                        gspread.Cell(row=row_idx_to_update, col=1, value=c_name),
                                        gspread.Cell(row=row_idx_to_update, col=time_col+1, value=current_time_str),
                                        gspread.Cell(row=row_idx_to_update, col=usage_col+1, value=str(total_mins))
                                    ]
                                    if global_discord_id:
                                        cells.append(gspread.Cell(row=row_idx_to_update, col=dc_col+1, value=str(global_discord_id)))
                                    on_sheet.update_cells(cells)
                                    invalidate_sheet_cache("ONLINE_USERS")
                                except Exception: pass
                            else:
                                exec_count = 1
                                total_mins = 0
                                has_logged_execution = True
                                
                                new_row = [""] * max(len(headers_row), 5)
                                new_row[0] = c_name
                                new_row[1] = global_my_puuid
                                new_row[time_col] = current_time_str
                                new_row[usage_col] = str(total_mins)
                                if global_discord_id and dc_col < len(new_row):
                                    new_row[dc_col] = str(global_discord_id)
                                
                                try:
                                    if not records: on_sheet.append_row(["닉네임", "PUUID", "마지막접속시간", "누적사용시간(분)", "디스코드ID"])
                                    on_sheet.append_row(new_row)
                                    invalidate_sheet_cache("ONLINE_USERS")
                                except Exception: pass
                except Exception: pass
                last_ping_time = time.time()

            # [V81.48] 폴링 실패/타임아웃 시 current_phase를 "None"으로 떨구지 않고 '직전 phase 유지'.
            #   (인게임 중 gameflow-phase 요청 1회 실패 → current_phase="None" → was_in_prog 헛플립 →
            #    다음 성공 폴링에서 game_seq++ → 커스텀게임 fetched_game_id가 갈려 '같은 게임 중복기록' 유발하던 버그.)
            try:
                flow_res = requests.get(str(base_url) + "/lol-gameflow/v1/gameflow-phase", headers=headers, verify=False, timeout=3)
                current_phase = flow_res.json() if flow_res.status_code == 200 else last_known_phase
            except Exception:
                current_phase = last_known_phase
            last_known_phase = current_phase
            # 🧭 [2026-07-29 사장님 제보] 관전→플레이어로 자리를 옮기자마자 밴픽이 시작되면, 얼기 직전
            #    로비 폴링이 그 사람을 아직 관전자·포지션 미정으로 보고 그대로 굳어 포지션이 꼬였다.
            #    밴픽 진입 후 CS_REFRESH_SEC 동안은 로비를 계속 읽어 캐시를 정정한다(화면은 즉시 뜬다).
            if current_phase == "ChampSelect":
                if _cs_since[0] == 0.0: _cs_since[0] = time.time()
            else:
                _cs_since[0] = 0.0
            _cs_fresh = _cs_since[0] > 0 and (time.time() - _cs_since[0]) < CS_REFRESH_SEC
            try: noban_tick(headers, base_url, current_phase)   # 🚫 노밴 선언 감지(로비 채팅, 2초 간격)
            except Exception: pass

            # 🔢 게임에 새로 '진입'할 때마다 카운터 증가 (새 게임 = 새 ID 보장)
            # Reconnect 등 인게임 phase를 한 게임으로 묶어, 도중 끊김→재접속 시 중복 증가(=같은 게임 중복기록) 방지
            _INGAME_PHASES = ("GameStart", "InProgress", "Reconnect", "PreEndOfGame", "WaitingForStats", "EndOfGame")
            _in_prog_now = (current_phase in _INGAME_PHASES)
            if _in_prog_now and not was_in_prog:
                game_seq += 1
                # 🧠 [v82.42 사장님 지시] 게임 진입 순간 코치 팝업 즉시 숨김 — 항상-위 창이 전체화면(독점) 모드를
                #    깨서 순간 렉/깜빡임을 유발할 수 있음(90초 자동소멸을 기다리지 않음)
                try:
                    with gui_lock:
                        gui_data["draft_advice"] = ""; gui_data["draft_advice_ts"] = 0
                except Exception: pass
            was_in_prog = _in_prog_now
            # 🛡️ [v81.67] 자동 업데이트 재시작 게이트용 미러 — 게임/기록 중이면 업데이터가 재시작을 연기.
            _LIVE_GAME[0] = bool(_in_prog_now or active_recording_id or current_phase == "ChampSelect")

            c100, c200, multi_id = [], [], ""
            queue_id = -1
            map_id = 11
            is_custom_game_flag = False

            try:
                gf_res = requests.get(str(base_url) + "/lol-gameflow/v1/session", headers=headers, verify=False, timeout=3)
                if gf_res.status_code == 200:
                    gf_json = gf_res.json() or {}
                    gd = gf_json.get('gameData') or {}
                    
                    map_id = gd.get('map', {}).get('id', map_id)
                    
                    if 'queue' in gd and 'id' in gd['queue']:
                        queue_id = gd['queue']['id']
                    
                    if gd.get('isCustomGame'): 
                        is_custom_game_flag = True
                    
                    if current_phase in ["ChampSelect", "GameStart", "InProgress"]:
                        raw_c100 = gd.get('teamOne') or []
                        raw_c200 = gd.get('teamTwo') or []
                        
                        c100 = [x for x in raw_c100 if isinstance(x, dict) and str(x.get('isSpectator', 'False')).lower() != 'true' and str(x.get('role', '')).upper() != "SPECTATOR"]
                        c200 = [x for x in raw_c200 if isinstance(x, dict) and str(x.get('isSpectator', 'False')).lower() != 'true' and str(x.get('role', '')).upper() != "SPECTATOR"]
            except Exception: pass

            detected_ban_ids = set()
            try:
                select_res = requests.get(str(base_url) + "/lol-champ-select/v1/session", headers=headers, verify=False, timeout=3)
                if select_res.status_code == 200:
                    s_json = select_res.json() or {}

                    # 🧠 [v81.74] 내 픽 차례면 고스트밴픽왕(키 없으면 즉시 return, 비동기라 폴링 지연 없음)
                    # [v82.20 사장님 지시] 내전(커스텀·소환사의 협곡)에서만 작동 — 일반 매칭·칼바람(맵12)에선 비활성
                    if is_custom_game_flag and map_id != 12:
                        try: _draft_coach_tick(s_json, headers, base_url)
                        except Exception: pass

                    cell_to_puuid = {}
                    for t_key in ['myTeam', 'theirTeam']:
                        for p_info in s_json.get(t_key, []):
                            c_id = p_info.get('cellId')
                            p_puuid = p_info.get('puuid', '')
                            if not p_puuid and str(p_info.get('playerType', '')).lower() == 'bot':
                                p_puuid = f"BOT_{p_info.get('championId', 0)}"
                            elif not p_puuid and p_info.get('summonerId'):
                                p_puuid = f"TEMP_ID_{p_info['summonerId']}_{p_info.get('summonerName','')}"

                            if c_id is not None and p_puuid:
                                cell_to_puuid[c_id] = p_puuid.strip().lower()
                                # 🎭 [v82.30] 확정 챔피언 기억 — 인게임 변신(니코)에 오염되지 않는 유일한 소스
                                try:
                                    _lc = int(p_info.get('championId') or 0)
                                    if _lc > 0: global_lock_champ_map[p_puuid.strip().lower()] = _lc
                                except Exception: pass

                    # 🛟 [v82.2 긴급] 토너먼트 드래프트 커스텀(큐 3130 '토너먼트 교차 선택' 등)은 챔프선택 동안
                    #    gameData.teamOne/teamTwo가 빈 배열 → 슬롯 0명(유저 인식 안 됨). 챔프선택 세션의
                    #    myTeam/theirTeam(퍼uid·summonerId 보유)으로 로스터 폴백. team 필드 1=블루, 2=레드.
                    #    이름은 parse_team의 summonerId 조회가 채우고, 포지션은 기존 인덱스 폴백 그대로.
                    if not c100 and not c200:
                        _fb_blue, _fb_red = [], []
                        for _tk in ('myTeam', 'theirTeam'):
                            for _p in s_json.get(_tk, []) or []:
                                if not isinstance(_p, dict): continue
                                if not (_p.get('puuid') or _p.get('summonerId') or str(_p.get('playerType', '')).lower() == 'bot'): continue
                                _e = {'summonerId': _p.get('summonerId', 0),
                                      'puuid': _p.get('puuid', '') or '',
                                      'summonerName': _p.get('summonerName', '') or _p.get('gameName', ''),
                                      'assignedPosition': _p.get('assignedPosition', '')}
                                if str(_p.get('playerType', '')).lower() == 'bot':
                                    _e['puuid'] = f"BOT_{_p.get('championId', 0)}"
                                    _e['botChampionId'] = _p.get('championId', 0)
                                (_fb_blue if _p.get('team', 1) == 1 else _fb_red).append(_e)
                        if _fb_blue or _fb_red:
                            c100, c200 = _fb_blue, _fb_red
                            print(f"[v82.2진단] 챔프선택 폴백 로스터 {len(c100)}v{len(c200)}", flush=True)

                    # 🥇 [v82.26] 픽순서(1~10) 캡처 — 완료된 pick 액션의 등장 순서(드래프트 모드만 의미, 블라인드/칼바람은 빈 맵)
                    try:
                        _pk_n, _pk_map = 0, {}
                        for _al in s_json.get('actions', []):
                            if isinstance(_al, list):
                                for _ac in _al:
                                    if isinstance(_ac, dict) and _ac.get('type') == 'pick':
                                        _pk_n += 1
                                        if _ac.get('completed') and _ac.get('actorCellId') in cell_to_puuid:
                                            _pk_map[cell_to_puuid[_ac['actorCellId']]] = _pk_n
                        if _pk_map: global_pick_order_map = _pk_map
                    except Exception: pass

                    for act_list in s_json.get('actions', []):
                        if isinstance(act_list, list):
                            for act in act_list:
                                if isinstance(act, dict) and act.get('type') == 'ban' and act.get('completed'):
                                    banned_c_id = act.get('championId', 0)
                                    actor_cell = act.get('actorCellId')
                                    if str(banned_c_id).isdigit() and int(banned_c_id) > 0:
                                        detected_ban_ids.add(int(banned_c_id))
                                        
                                        if actor_cell in cell_to_puuid:
                                            b_id_int = int(banned_c_id)
                                            kor_n = ""
                                            if b_id_int in champ_map: kor_n = champ_map[b_id_int]['kor']
                                            elif b_id_int in GLOBAL_NUMERIC_CHAMP_MAP: kor_n = GLOBAL_NUMERIC_CHAMP_MAP[b_id_int]
                                            
                                            p_uid = cell_to_puuid[actor_cell]
                                            if kor_n: global_user_ban_map[p_uid] = kor_n

                    b_obj = s_json.get('bans') or {}
                    if isinstance(b_obj, dict):
                        for b_id in b_obj.get('myTeamBans', []) + b_obj.get('theirTeamBans', []):
                            if str(b_id).isdigit() and int(b_id) > 0: detected_ban_ids.add(int(b_id))
            except Exception: pass
            
            try:
                b_res = requests.get(str(base_url) + "/lol-champ-select/v1/banned-champions", headers=headers, verify=False, timeout=3)
                if b_res.status_code == 200:
                    b_json = b_res.json() or {}
                    for b_id in b_json.get('myTeamBans', []) + b_json.get('theirTeamBans', []):
                        if str(b_id).isdigit() and int(b_id) > 0: detected_ban_ids.add(int(b_id))
            except Exception: pass

            if detected_ban_ids:
                for b_id in detected_ban_ids:
                    kor_name = ""
                    if b_id in champ_map: kor_name = champ_map[b_id]['kor']
                    elif b_id in GLOBAL_NUMERIC_CHAMP_MAP: kor_name = GLOBAL_NUMERIC_CHAMP_MAP[b_id]
                    
                    if kor_name and kor_name not in global_captured_bans:
                        global_captured_bans.append(kor_name)

            if current_phase in ["Lobby", "Matchmaking", "ReadyCheck", "None"] or (not c100 and not c200) or _cs_fresh:
                try:
                    lobby_res = requests.get(str(base_url) + "/lol-lobby/v2/lobby", headers=headers, verify=False, timeout=3)
                    if lobby_res.status_code == 200:
                        lobby_data = lobby_res.json() or {}
                        multi_id = str(lobby_data.get('multiplayerGameId', ''))
                        
                        gc = lobby_data.get('gameConfig') or {}
                        if 'queueId' in gc: queue_id = gc['queueId']
                        if gc.get('isCustom'): is_custom_game_flag = True
                        map_id = gc.get('mapId', map_id)
                        
                        dict_text = str(gc).upper()
                        # 🧭 [2026-08-01 사장님 제보] 칼바람 매치게임 방에 있다가 커스텀 방으로 옮겨도
                        #    계속 칼바람(KIWI_KIWI) 전적이 뜨던 문제.
                        #    원인: is_aram_session 이 루프 밖 변수인데 **True 로만 켜지고**, 해제는
                        #    새 게임ID(multi_id)가 잡힐 때뿐이었다. 방을 옮기는 것만으로는 안 풀린다.
                        #    → 로비·대기 단계에서는 지금 방의 설정을 그대로 반영해 해제까지 되게 한다.
                        #      (챔프선택·인게임 중에는 조회가 잠깐 흔들려도 모드가 뒤집히지 않게 래치 유지)
                        _aram_now = ("ARAM" in dict_text or "HOWLING" in dict_text or "BUTCHER" in dict_text
                                     or map_id in [12, 14] or queue_id == 450)
                        if _aram_now:
                            is_aram_session = True
                        elif current_phase in ["Lobby", "Matchmaking", "ReadyCheck", "None"]:
                            if is_aram_session:
                                print("[mode] 칼바람 신호가 사라짐(방 이동) — 협곡 기준으로 전환", flush=True)
                            is_aram_session = False
                            
                        c100_temp, c200_temp = [], []
                        
                        if is_custom_game_flag:
                            r100 = gc.get('customTeam100') or []
                            r200 = gc.get('customTeam200') or []
                            c100_temp = [x for x in r100 if str(x.get('isSpectator', 'False')).lower() != 'true']
                            c200_temp = [x for x in r200 if str(x.get('isSpectator', 'False')).lower() != 'true']
                            
                            if not c100_temp and not c200_temp:
                                for m in lobby_data.get('members', []):
                                    if not isinstance(m, dict): continue
                                    is_spec = str(m.get('isSpectator', 'False')).lower() == 'true'
                                    role = str(m.get('role', '')).upper()
                                    if is_spec or role == 'SPECTATOR': continue
                                    
                                    t_id = str(m.get('teamId', '')).strip().upper()
                                    if t_id in ["100", "1"]: c100_temp.append(m)
                                    elif t_id in ["200", "2"]: c200_temp.append(m)
                        else:
                            for m in lobby_data.get('members', []):
                                if not isinstance(m, dict): continue
                                is_spec = str(m.get('isSpectator', 'False')).lower() == 'true'
                                role = str(m.get('role', '')).upper()
                                if is_spec or role == 'SPECTATOR': continue
                                
                                t_id = str(m.get('teamId', '')).strip().upper()
                                if t_id in ["100", "1", "ORDER", "TEAM1", "BLUE"]: c100_temp.append(m)
                                elif t_id in ["200", "2", "CHAOS", "TEAM2", "RED"]: c200_temp.append(m)
                                    
                        c100, c200 = c100_temp, c200_temp
                except Exception: pass
            
            if multi_id and multi_id != "0" and multi_id != last_chat_game_id:
                global_captured_bans.clear()
                global_user_ban_map.clear()
                frozen_user_bans.clear()
                global_pick_order_map.clear(); frozen_pick_order.clear()
                global_lock_champ_map.clear(); frozen_lock_champ.clear()
                frozen_bans_str = ""
                global_ingame_names.clear()
                global_puuid_fallback_map.clear()
                is_aram_session = False
                is_custom_game_flag = False
                global_cached_blue.clear()
                global_cached_red.clear()
                global_pos_map.clear()
                active_recording_id = None
                eog_retry_count = 0
                eog_write_retry = 0          # 새 게임 진입 시 finalize 재시도 예산도 초기화(리뷰반영: 예산 누수 방지)
                _fin_write_retry = 0
                last_lobby_fingerprint = ""
                try:
                    threading.Timer(1.5, send_lcu_chat_announcement, args=[f"[분석기 정찰 시스템] 스쿼드해체분석기 v{CURRENT_VERSION} 로딩 완료", headers, base_url]).start()
                    last_chat_game_id = multi_id
                except Exception: pass

            if current_phase in ["Lobby", "Matchmaking"] and not active_recording_id:
                global_captured_bans.clear()
                global_user_ban_map.clear()
                frozen_user_bans.clear()
                global_pick_order_map.clear(); frozen_pick_order.clear()
                global_lock_champ_map.clear(); frozen_lock_champ.clear()
                frozen_bans_str = ""
                global_ingame_names.clear()
                global_puuid_fallback_map.clear()

            is_valid_game = (queue_id == 0 or is_custom_game_flag)
            
            with gui_lock:
                # [v81.77] 제목만 텍스트, 챔피언은 아이콘으로 → 목록을 그대로 전달
                gui_data["bans"] = f"🚫 10밴 현황 ({len(global_captured_bans)}/10):" if global_captured_bans else "🚫 10밴 현황: 대기 중"
                gui_data["ban_list"] = list(global_captured_bans)

            if current_phase == "ChampSelect":
                if global_captured_bans: frozen_bans_str = ", ".join(global_captured_bans)
                if global_user_ban_map: frozen_user_bans = global_user_ban_map.copy()
                if global_pick_order_map: frozen_pick_order = global_pick_order_map.copy()   # 🥇 [v82.26]
                if global_lock_champ_map: frozen_lock_champ = global_lock_champ_map.copy()   # 🎭 [v82.30]

            def parse_team(raw_list):
                parsed = []
                if not raw_list or not isinstance(raw_list, list): return parsed
                fallback_pos = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
                
                for idx, p in enumerate(raw_list):
                    try: 
                        if not isinstance(p, dict): continue
                        
                        s_name, g_name = p.get('summonerName', ''), p.get('gameName', '')
                        name = s_name if s_name else g_name if g_name else ""
                        puuid, s_id = p.get('puuid', ''), p.get('summonerId', 0)
                        
                        if str(puuid).startswith("BOT_"):
                            bot_champ_id = p.get('botChampionId', 0)
                            bot_kor_name = champ_map.get(bot_champ_id, {}).get('kor', '') if champ_map else ''
                            if not bot_kor_name: bot_kor_name = GLOBAL_NUMERIC_CHAMP_MAP.get(bot_champ_id, '봇')
                            name = f"🤖 {bot_kor_name} 봇"
                            puuid = f"BOT_{bot_champ_id}"
                        else:
                            if s_id and not name:
                                try:
                                    su_res = requests.get(str(base_url) + "/lol-summoner/v1/summoners/" + str(s_id), headers=headers, verify=False, timeout=2)
                                    if su_res.status_code == 200:
                                        data = su_res.json()
                                        g_name = str(data.get('gameName', ''))
                                        tag = str(data.get('tagLine', ''))
                                        name = f"{g_name}#{tag}" if tag else g_name
                                        if not puuid: puuid = data.get('puuid', '')
                                except Exception: pass
                            # 🛟 [v82.2] 토너먼트 드래프트 상대팀은 summonerId 익명화(0) → PUUID로 이름 해석
                            if not name and puuid and not str(puuid).startswith(("BOT_", "TEMP")):
                                try:
                                    su2_res = requests.get(str(base_url) + "/lol-summoner/v2/summoners/puuid/" + str(puuid), headers=headers, verify=False, timeout=2)
                                    if su2_res.status_code == 200:
                                        data2 = su2_res.json()
                                        g_name2 = str(data2.get('gameName', ''))
                                        tag2 = str(data2.get('tagLine', ''))
                                        name = f"{g_name2}#{tag2}" if tag2 else g_name2
                                except Exception: pass
                            if not name: name = "알 수 없는 유저"
                            if not puuid: puuid = f"TEMP_ID_{s_id}_{name}"
                        
                        raw_pos = str(p.get('assignedPosition', '')).upper()
                        if not raw_pos or raw_pos in ['NONE', 'UNSELECTED', '']: raw_pos = str(p.get('firstPositionPreference', '')).upper()
                        if not raw_pos or raw_pos in ['NONE', 'UNSELECTED', '']: raw_pos = str(p.get('position', '')).upper()
                        if not raw_pos or raw_pos in ['NONE', 'UNSELECTED', '']: raw_pos = str(p.get('role', '')).upper()
                        
                        if raw_pos not in fallback_pos:
                            raw_pos = fallback_pos[idx] if idx < 5 else "NONE"
                            
                        chosen_pos_icon_key = raw_pos
                        rank_tier, rank_lp = "UNRANKED", 0

                        try:
                            if puuid and not puuid.startswith("TEMP"):
                                rank_res = requests.get(str(base_url) + "/lol-ranked/v1/ranked-stats/" + str(puuid), headers=headers, verify=False, timeout=2)
                                if rank_res.status_code == 200:
                                    r_json = rank_res.json() or {}
                                    for q in r_json.get('queues') or []:
                                        if isinstance(q, dict) and q.get('queueType') == 'RANKED_SOLO_5x5':
                                            rank_tier = str(q.get('tier', 'UNRANKED')).upper(); rank_lp = q.get('leaguePoints', 0); break
                        except Exception: pass
                                
                        parsed.append({'name': name, 'puuid': puuid, 'chosen_pos_icon': chosen_pos_icon_key, 'tier_icon': rank_tier, 'lp': rank_lp, 'original_idx': idx})
                    except Exception: pass
                    
                pw = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4, "NONE": 5}
                parsed.sort(key=lambda x: (pw.get(x['chosen_pos_icon'], 5), x.get('original_idx', 99))) 
                return parsed

            FREEZE_PHASES = ["ChampSelect", "GameStart", "InProgress", "PreEndOfGame", "EndOfGame", "Reconnect", "WaitingForStats"]
            is_frozen = current_phase in FREEZE_PHASES or (current_phase == "None" and (global_cached_blue or global_cached_red))
            
            need_stat_crunch = False
            
            if is_frozen:
                # [v82.2] 프리즈 캐시가 '부분 로스터'로 잠기는 문제 방어: 새 파싱이 캐시보다 인원이 많으면 갱신
                #   (재시작·타이밍에 따라 초기 폴링이 일부만 잡은 채 얼어붙어 유저 인식이 비어 보이던 것)
                if global_cached_blue or global_cached_red:
                    temp_blue, temp_red = global_cached_blue, global_cached_red
                    # 🧭 [2026-07-29] 밴픽 진입 직후 창: 인원이 같아도 포지션 배치가 달라졌으면 교체.
                    #    (관전→플레이어 이동은 인원이 그대로인 경우가 있어 아래 '인원 증가' 조건을 통과 못 했다)
                    if _cs_fresh and (c100 or c200):
                        _nb2, _nr2 = parse_team(c100), parse_team(c200)
                        def _sig(_lst):
                            return sorted((str(_p.get("puuid") or "").lower(), str(_p.get("chosen_pos_icon") or ""))
                                          for _p in (_lst or []))
                        if (_nb2 or _nr2) and (_sig(_nb2) + _sig(_nr2)) != (_sig(temp_blue) + _sig(temp_red)) \
                                and len(_nb2) + len(_nr2) >= len(temp_blue) + len(temp_red):
                            temp_blue, temp_red = _nb2, _nr2
                            global_cached_blue, global_cached_red = _nb2, _nr2
                            need_stat_crunch = True
                            print(f"[포지션정정] 밴픽 직후 로비 재확인 — {len(_nb2)}v{len(_nr2)} 갱신", flush=True)
                    if len(c100) + len(c200) > len(global_cached_blue) + len(global_cached_red):
                        _nb, _nr = parse_team(c100), parse_team(c200)
                        if len(_nb) + len(_nr) > len(temp_blue) + len(temp_red):
                            temp_blue, temp_red = _nb, _nr
                            global_cached_blue, global_cached_red = _nb, _nr
                            need_stat_crunch = True
                            print(f"[v82.2진단] 프리즈 캐시 확장 {len(_nb)}v{len(_nr)}", flush=True)
                else:
                    temp_blue, temp_red = parse_team(c100), parse_team(c200)
                    if temp_blue or temp_red:
                        global_cached_blue, global_cached_red = temp_blue, temp_red
                        need_stat_crunch = True
                        print(f"[v82.2진단] 프리즈 첫 파싱 {len(temp_blue)}v{len(temp_red)}", flush=True)
            else:
                temp_blue_parsed, temp_red_parsed = parse_team(c100), parse_team(c200)
                if temp_blue_parsed or temp_red_parsed:
                    temp_blue, temp_red = temp_blue_parsed, temp_red_parsed
                    global_cached_blue, global_cached_red = temp_blue, temp_red
                    need_stat_crunch = True
                else:
                    temp_blue, temp_red = global_cached_blue, global_cached_red

            if temp_blue or temp_red:
                global_pos_map.clear()
                for p in temp_blue + temp_red:
                    if p.get('puuid'): global_pos_map[p['puuid'].strip().lower()] = p['chosen_pos_icon']

            lobby_fingerprint = "".join([str(p['puuid']) for p in temp_blue + temp_red])
            target_sheet_name = "KIWI_KIWI" if is_aram_session else "CLASSIC_NORMAL"
            # 🧭 [2026-07-30] 롤 클래식 같은 새 모드를 협곡과 구분하려면 그 모드의 식별값을 알아야 한다.
            #    지금은 칼바람만 판정하고 나머지를 협곡으로 보내므로, 새 모드가 협곡 탭에 섞인다.
            #    판별 근거를 잡기 위해 게임당 한 번 모드 정보를 로그로 남긴다.
            if is_valid_game and active_recording_id and active_recording_id not in _mode_logged:
                _mode_logged.add(active_recording_id)
                if len(_mode_logged) > 200: _mode_logged.clear()
                print(f"[mode] {active_recording_id} queueId={queue_id} mapId={map_id} "
                      f"custom={is_custom_game_flag} aram={is_aram_session} → {target_sheet_name}", flush=True)

            if is_valid_game and global_spreadsheet:
                try: sheet_target = global_spreadsheet.worksheet(target_sheet_name)
                except Exception:
                    try:
                        sheet_target = global_spreadsheet.add_worksheet(title=target_sheet_name, rows="2000", cols="12")
                        sheet_target.append_row(["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "KDA", "매치평가", "패치버전", "점수", "딜량"])
                    except Exception: sheet_target = global_spreadsheet.get_worksheet(0)
            else: sheet_target = None

            if (lobby_fingerprint != last_lobby_fingerprint) and need_stat_crunch:
                if sheet_target: 
                    cached_stats, cached_pos, cached_neg, cached_nem = crunch_sheet_statistics(temp_blue, temp_red, sheet_target)
                else: 
                    cached_stats, cached_pos, cached_neg, cached_nem = {}, [], [], []
                    
                if not cached_stats and len(temp_blue + temp_red) > 0:
                    pass 
                else:
                    final_blue = []
                    for p in temp_blue:
                        default_s = {"summary": "기록 없음", "most_list": [], "op_list": [], "fatal_bans": [], "fatal_bans_by_pos": {}, "streak": "", "side_wr_str": ""}
                        p_uid = str(p.get('puuid', '')).strip().lower()
                        p_nam = get_main_name(p.get('name', ''))
                        p_key = p_uid if p_uid else p_nam
                        final_blue.append((p, cached_stats.get(p_key, default_s)))
                    final_red = []
                    for p in temp_red:
                        default_s = {"summary": "기록 없음", "most_list": [], "op_list": [], "fatal_bans": [], "fatal_bans_by_pos": {}, "streak": "", "side_wr_str": ""}
                        p_uid = str(p.get('puuid', '')).strip().lower()
                        p_nam = get_main_name(p.get('name', ''))
                        p_key = p_uid if p_uid else p_nam
                        final_red.append((p, cached_stats.get(p_key, default_s)))
                        
                    with gui_lock:
                        gui_data["blue"] = final_blue
                        gui_data["red"] = final_red
                        gui_data["pos_synergy"] = "\n".join(cached_pos) if cached_pos else " - 특이사항 없음 (안정적)"
                        gui_data["neg_synergy"] = "\n".join(cached_neg) if cached_neg else " - 특이사항 없음 (평온)"
                        gui_data["nemesis_synergy"] = "\n".join(cached_nem) if cached_nem else " - 상성 매칭 없음 (평온)"
                        
                last_lobby_fingerprint = lobby_fingerprint

            with gui_lock:
                if current_phase == "Lobby":
                    if "오프라인" not in gui_data["status"]: 
                        gui_data["status"] = "🟢 대기실 정찰 중 (" + (target_sheet_name if is_valid_game else "매칭 게임 기록 생략됨") + ")"
                elif current_phase == "ChampSelect":
                    if "오프라인" not in gui_data["status"]: 
                        gui_data["status"] = "🔶 밴픽 진행 중" + (" (데이터 동결됨)" if is_valid_game else " [매칭 게임 제외]")
                elif current_phase in ["GameStart", "InProgress"]:
                    if is_valid_game and active_recording_id:
                        if "오프라인" not in gui_data["status"]: gui_data["status"] = "🔥 인게임 기록 중 (데이터 동결됨)"
                    elif not is_valid_game:
                        if "오프라인" not in gui_data["status"]: gui_data["status"] = "👀 매칭 게임 (기록 생략됨)"

            if current_phase == "InProgress" and is_valid_game and sheet_target:
                try:
                    live_res = requests.get("https://127.0.0.1:2999/liveclientdata/playerlist", verify=False, timeout=1)
                    if live_res.status_code == 200:
                        lr_json = live_res.json()
                        if isinstance(lr_json, list):
                            fetched_game_id = None
                            try:
                                session_res = requests.get(str(base_url) + "/lol-gameflow/v1/session", headers=headers, verify=False, timeout=2)
                                if session_res.status_code == 200: fetched_game_id = session_res.json().get('gameData', {}).get('gameId')
                            except Exception: pass
                                
                            if not fetched_game_id:
                                fingerprint = "".join([str(p.get('puuid', '')) for p in temp_blue + temp_red])
                                hashed_id = hashlib.md5(fingerprint.encode()).hexdigest()[:10]
                                # 👥 [2026-08-16 사장님 제보 '한 경기가 두 개로'] 조회가 한 번 실패했다고 바로 합성 ID를
                                #    만들면, 실번호를 받은 다른 인스턴스와 ID가 달라 중복 게이트를 둘 다 통과한다
                                #    (실측 3건 — 7/17·7/31·8/15, 같은 판 20행). 일시 실패는 다음 폴링에서 대부분
                                #    회복되므로 90초까지는 이번 루프 기록을 미루고 재조회만 한다.
                                if len(_gid_wait) > 100: _gid_wait.clear()
                                if time.time() - _gid_wait.setdefault(hashed_id, time.time()) < 90.0:
                                    fetched_game_id = None
                                else:
                                    # 커스텀게임은 gameId=0 → 게임카운터(game_seq) 붙여 같은 멤버 연속게임도 고유 ID 보장(#2 기록버그)
                                    fetched_game_id = (f"CUSTOM_{hashed_id}_{game_seq}" if fingerprint else f"CUSTOM_MATCH_{game_seq}")

                            if fetched_game_id and fetched_game_id not in recorded_game_ids:
                                
                                human_puuids = []
                                for p in temp_blue + temp_red:
                                    p_uid = str(p.get('puuid', '')).strip().lower()
                                    if p_uid and not p_uid.startswith('bot_') and not p_uid.startswith('temp_'):
                                        human_puuids.append(p_uid)
                                human_puuids.sort()
                                
                                # [V81.45] 🎬 시작 알림을 '리더 전용'에서 '기록 승자 발송'으로 이동(아래 _appended_ok 지점).
                                #   리더(로스터 1번)가 분석기를 안 켜면 시작 웹훅이 영영 안 나가던 단일실패점 제거 —
                                #   분석기를 켠 사람 중 기록 append에 성공한 정확히 1명이 게임당 1회 발송.

                                # 📣 게임 시작 시 호출자(승격된 대기자) 멘션 — 호스트만. 내전기록 작성과 동시에.
                                try: ping_called_at_gamestart(fetched_game_id)
                                except Exception: pass

                                # 🔒 [중복방지] human_puuids 내 순위 기반 '결정적' 시차 — 순위0=0.5s, 이후 +3s씩.
                                #     앞 순위가 먼저 기록 → 뒤 순위는 append 직전 재확인 후 건너뜀.
                                #   [모의테스트 HIGH 수정] 로스터에 자기 puuid가 없는 인스턴스(관전자 등)가 전부 rank0으로
                                #     몰려 동시 append 충돌(중복 10행)하던 것 → 로스터 뒤(10~) 해시분산 순번 부여로 충돌 제거.
                                try:
                                    if human_puuids and global_my_puuid in human_puuids:
                                        _my_rank = human_puuids.index(global_my_puuid)
                                    else:
                                        _my_rank = 10 + (int(hashlib.md5(str(global_my_puuid or 'x').encode()).hexdigest(), 16) % 8)
                                except Exception:
                                    _my_rank = 10
                                time.sleep(0.5 + _my_rank * 3.0)
                                
                                lcu_puuid_map = {}
                                global_ingame_names.clear()
                                global_puuid_fallback_map.clear()
                                
                                for p in temp_blue + temp_red:
                                    c_name = str(p['name']).replace("🤖", "").replace(" 봇", "").strip().lower()
                                    lcu_puuid_map[c_name] = str(p['puuid']).strip().lower()
                                    
                                try: sheet_data_fresh = get_sheet_data_cached(sheet_target, force=True)
                                except Exception: sheet_data_fresh = []
                                
                                # list()로 복사 — get_sheet_data_cached가 캐시객체를 그대로 반환하므로 아래 headers_row.append가 캐시를 오염시키지 않게(리뷰반영)
                                headers_row = list(sheet_data_fresh[0]) if sheet_data_fresh else ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "KDA", "매치평가", "패치버전", "점수", "딜량"]

                                # 🧩 [v81.90 2026-07-15 사장님 제보] 관전→참가 등으로 밴픽 PUUID맵(lcu_puuid_map)에 없는 실제 플레이어 대비:
                                #   시트 '과거기록의 소환사명→PUUID' 폴백맵. 같은 LCU형식 PUUID라 안전(Match-V5 Riot PUUID와 형식 달라 못 씀).
                                #   사례: 건빡이 밴픽 때 관전이라 lcu_puuid_map 누락 → PUUID 빈칸 기록됐으나 과거 62행에 PUUID 존재 → 폴백으로 복구.
                                sheet_puuid_fallback = {}
                                try:
                                    _sn_i = headers_row.index("소환사명"); _pu_i = headers_row.index("PUUID")
                                    for _hr in (sheet_data_fresh[1:] if sheet_data_fresh else []):
                                        if len(_hr) <= max(_sn_i, _pu_i): continue
                                        _pv = str(_hr[_pu_i]).strip().lower(); _nm = str(_hr[_sn_i]).strip().lower()
                                        if _pv and _nm:
                                            sheet_puuid_fallback[_nm] = _pv                        # 풀 소환사명(태그포함) 키
                                            _nk = re.sub(r"#.*$", "", _nm).replace(" ", "")        # 태그·공백 제거 키
                                            if _nk: sheet_puuid_fallback.setdefault(_nk, _pv)
                                except Exception: pass

                                missing_headers = []
                                if "PUUID" not in headers_row: missing_headers.append("PUUID")
                                if "밴" not in headers_row: missing_headers.append("밴")
                                if "결과" not in headers_row: missing_headers.append("결과")
                                if "KDA" not in headers_row: missing_headers.append("KDA")
                                if "매치평가" not in headers_row: missing_headers.append("매치평가")
                                if "패치버전" not in headers_row: missing_headers.append("패치버전")
                                if "점수" not in headers_row: missing_headers.append("점수")
                                if "딜량" not in headers_row: missing_headers.append("딜량")
                                # 🛒 [v81.70 사장님 지시] 아이템 빌드 + 주룬/보조룬 기록(웹 전적카드 표시용)
                                if "아이템" not in headers_row: missing_headers.append("아이템")
                                if "주룬" not in headers_row: missing_headers.append("주룬")
                                if "보조룬" not in headers_row: missing_headers.append("보조룬")
                                if "스펠" not in headers_row: missing_headers.append("스펠")   # 🔮 [v81.73] 소환사 스펠(점멸·점화 등)
                                if "지표" not in headers_row: missing_headers.append("지표")   # 📊 [v82.26] 상세지표 팩(골드·CS·분·KP·시야·와드·오브젝트 등)+픽순서
                                
                                # [v81.72] 헤더 자동생성 사고 수정 — 과거 행 잔여값으로 테이블 폭이 부풀면(헤더행 뒤 빈칸 다수)
                                #   기존 start_col=len(headers_row)+1이 그리드 폭을 넘어 update_cells가 '영구 실패(무음 pass)'했고,
                                #   그 실패 쓰기가 기록 전까지 매 폴링루프×전 인스턴스 반복돼 분당 쓰기쿼터를 소진 → append/finalize 429
                                #   → 전 게임 결과대기(2026-07-13 실전 사고). 수정: ①빈 트레일링 헤더 슬롯을 재활용(첫 빈칸 위치에 기입)
                                #   ②그리드 부족 시 add_cols로 확장 ③시도는 시트당 세션 1회(_HDR_MIG_DONE) — 실패해도 재폭격 안 함.
                                if missing_headers and sheet_target.title not in _HDR_MIG_DONE:
                                    _HDR_MIG_DONE.add(sheet_target.title)
                                    if not sheet_data_fresh:
                                        sheet_target.append_row(headers_row)
                                    else:
                                        _eff = len(headers_row)
                                        while _eff > 0 and not str(headers_row[_eff - 1]).strip(): _eff -= 1
                                        try:
                                            _need = _eff + len(missing_headers)
                                            if sheet_target.col_count < _need:
                                                sheet_target.add_cols(_need - sheet_target.col_count)
                                        except Exception as _ge:
                                            print(f"[헤더] 그리드 확장 실패: {type(_ge).__name__}", flush=True)
                                        cells_to_add = []
                                        for i, h in enumerate(missing_headers):
                                            _col = _eff + 1 + i
                                            cells_to_add.append(gspread.Cell(row=1, col=_col, value=h))
                                            if _col - 1 < len(headers_row): headers_row[_col - 1] = h
                                            else: headers_row.append(h)
                                        try:
                                            sheet_target.update_cells(cells_to_add)
                                        except Exception as _he:
                                            print(f"[헤더] 신규 열 생성 실패({sheet_target.title}): {type(_he).__name__} {str(_he)[:120]}", flush=True)
                                    invalidate_sheet_cache(sheet_target.title)
                                    try: sheet_data_fresh = get_sheet_data_cached(sheet_target, force=True)
                                    except Exception: pass
                                    if sheet_data_fresh: headers_row = list(sheet_data_fresh[0])
                                    
                                res_col_idx = headers_row.index("결과") + 1 if "결과" in headers_row else 0
                                ban_col_idx = headers_row.index("밴") + 1 if "밴" in headers_row else 0
                                kda_col_idx = headers_row.index("KDA") + 1 if "KDA" in headers_row else 0
                                eval_col_idx = headers_row.index("매치평가") + 1 if "매치평가" in headers_row else 0
                                patch_col_idx = headers_row.index("패치버전") + 1 if "패치버전" in headers_row else 0
                                gid_idx = headers_row.index("게임ID") if "게임ID" in headers_row else 0
                                puuid_idx = headers_row.index("PUUID") if "PUUID" in headers_row else -1
                                team_idx = headers_row.index("진영") if "진영" in headers_row else -1
                                champ_idx = headers_row.index("챔피언") if "챔피언" in headers_row else -1

                                game_id_str = f"#{fetched_game_id}"
                                existing_rows_count = 0
                                has_bot = False   # 🤖 puuid 없는 봇이 끼면 True → 기록 생략(#2)

                                for row in sheet_data_fresh:
                                    if len(row) > gid_idx and row[gid_idx] == game_id_str:
                                        existing_rows_count += 1
                                # 👥 [2026-08-16] 합성 ID 폴백일 땐 게임ID 문자열 대조가 무력하다 — 남은 실번호로 적는다.
                                #    같은 로스터(PUUID 8명 이상 일치)가 최근 30분 내 다른 게임ID로 이미 기록돼 있으면
                                #    그게 이 판이다 → 내 합성 ID 기록은 중복이므로 '이미 기록됨'으로 처리.
                                if existing_rows_count == 0 and "CUSTOM" in str(fetched_game_id):
                                    try:
                                        _pu_i = headers_row.index("PUUID"); _dt_i = headers_row.index("날짜")
                                        _mine = {u for u in human_puuids if u}
                                        if len(_mine) >= 8:
                                            _now_t = time.time(); _byg = {}
                                            for row in (sheet_data_fresh[1:] if sheet_data_fresh else []):
                                                if len(row) <= max(_pu_i, _dt_i, gid_idx): continue
                                                _g = str(row[gid_idx]).strip()
                                                if not _g or _g == game_id_str: continue
                                                try: _t = time.mktime(time.strptime(str(row[_dt_i])[:16], "%Y-%m-%d %H:%M"))
                                                except Exception: continue
                                                if _now_t - _t > 1800: continue
                                                _byg.setdefault(_g, set()).add(str(row[_pu_i]).strip().lower())
                                            for _g, _pus in _byg.items():
                                                if len(_mine & _pus) >= 8:
                                                    existing_rows_count = 99
                                                    print(f"[중복방지] 같은 로스터가 {_g} 로 이미 기록됨 — 합성 ID({game_id_str}) 기록 생략", flush=True)
                                                    break
                                    except Exception: pass
                                        
                                _record_confirmed = False   # [V81.45] 기록 확정 여부 — 미확정(429 등)이면 다음 루프 재시도
                                _dedup_ok = True
                                _appended_ok = False
                                col_a_now = []   # [V81.48] 완전성 게이트로 append 블록을 건너뛰어도 아래 재확인이 NameError 안 나게 선초기화
                                if existing_rows_count >= 5:
                                    recorded_game_ids.add(fetched_game_id)
                                    active_recording_id = fetched_game_id
                                    active_recording_sheet_name = target_sheet_name
                                    eog_retry_count = 0
                                    _record_confirmed = True
                                else:
                                    rows_to_append = []
                                    team_color_cache = []
                                    roster_data = []   # 🎮 [2026-07-08] 봇 진행판 스코어보드용: (side B/R, 포지션, 챔피언, 이름)
                                    
                                    eng_to_kor_map = {v['eng'].lower().replace(" ", ""): v['kor'] for v in champ_map.values() if isinstance(v, dict)}
                                    CHAMP_ENG_TO_KOR_FALLBACK = {v: k for k, v in CHAMP_KOR_TO_ENG.items()}

                                    for p in lr_json:
                                        if not isinstance(p, dict): continue
                                        s_name = str(p.get('summonerName', '소환사'))
                                        riot_name = str(p.get('riotIdGameName', ''))
                                        riot_tag = str(p.get('riotIdTagLine', ''))
                                        
                                        if len(riot_tag) > 10 and "-" in riot_tag:
                                            riot_tag = ""
                                            
                                        c_name_key = s_name.replace(" 봇", "").strip().lower()
                                        full_riot_id = (f"{riot_name}#{riot_tag}").lower().strip() if riot_name and riot_tag else ""
                                        p_puuid = lcu_puuid_map.get(full_riot_id) or lcu_puuid_map.get(c_name_key, "")
                                        if not p_puuid and riot_name:   # [v81.90] 밴픽맵 누락(관전→참가 등) → 시트 과거기록 소환사명 폴백(같은 LCU형식)
                                            _fk = full_riot_id or c_name_key
                                            p_puuid = sheet_puuid_fallback.get(_fk) or sheet_puuid_fallback.get(re.sub(r"#.*$", "", _fk).replace(" ", "")) or ""
                                        # 🤖 puuid 없는 봇 감지 (실제 플레이어는 puuid 또는 riot ID 보유) — 봇 매치는 기록 생략(#2)
                                        if (not p_puuid) and (not riot_name or s_name.rstrip().endswith("봇")):
                                            has_bot = True

                                        if p_puuid:
                                            if full_riot_id: global_puuid_fallback_map[full_riot_id] = p_puuid
                                            global_puuid_fallback_map[c_name_key] = p_puuid
                                        
                                        c_name_raw = str(p.get('championName', 'Bot')).replace(" ", "")
                                        kor_cname = eng_to_kor_map.get(c_name_raw.lower(), c_name_raw) if eng_to_kor_map else c_name_raw
                                        if kor_cname == c_name_raw: kor_cname = CHAMP_ENG_TO_KOR_FALLBACK.get(c_name_raw, c_name_raw)
                                        # 🎭 [v82.30] 니코 변신 보정 — 라이브 playerlist는 변신 대상 챔프를 반환하므로
                                        #   밴픽에서 확정된 챔피언이 있으면 그것을 우선(같은 팀 동일 챔프 기록·MVP 오귀속의 근본 원인).
                                        try:
                                            _lc = frozen_lock_champ.get(p_puuid) or global_lock_champ_map.get(p_puuid)
                                            if _lc:
                                                _le = str((champ_map.get(_lc) or {}).get('eng', '')).replace(" ", "")
                                                _lk = (champ_map.get(_lc) or {}).get('kor') or GLOBAL_NUMERIC_CHAMP_MAP.get(_lc, "")
                                                if _lk and _lk != kor_cname:
                                                    print(f"[변신보정] {s_name}: playerlist '{kor_cname}' → 확정 '{_lk}'", flush=True)
                                                if _lk: kor_cname = _lk
                                                if _le: c_name_raw = _le
                                        except Exception: pass
                                        # 2차 방어선 — 밴픽 확정값이 없어도 변신 표시명(메가나르·에그니비아 등)은 원래 챔프로 복원
                                        _pre_fix = kor_cname
                                        kor_cname = _fix_transform_name(kor_cname)
                                        c_name_raw = _fix_transform_name(c_name_raw)
                                        if _pre_fix != kor_cname:
                                            print(f"[변신보정] {s_name}: '{_pre_fix}' → '{kor_cname}' (표시명 정규화)", flush=True)
                                        
                                        if riot_name: global_ingame_names[c_name_raw.lower()] = f"{riot_name}#{riot_tag}" if riot_tag else riot_name
                                        else: global_ingame_names[c_name_raw.lower()] = s_name

                                        team_val = "블루팀" if p.get('team', 'ORDER') == "ORDER" else "레드팀"
                                        t_id_num = 100 if team_val == "블루팀" else 200
                                        
                                        my_ban = frozen_user_bans.get(p_puuid, "")
                                        if not my_ban:
                                            for k_uid, v_ban in frozen_user_bans.items():
                                                if k_uid in p_puuid or p_puuid in k_uid:
                                                    my_ban = v_ban
                                                    break
                                                    
                                        if not my_ban:
                                            if is_aram_session or not global_captured_bans:
                                                my_ban = "밴 없음"
                                            else:
                                                my_ban = "밴 안함"
                                            
                                        row_data = [""] * len(headers_row)
                                        def set_val(col_name, val):
                                            if col_name in headers_row: row_data[headers_row.index(col_name)] = val
                                                
                                        set_val("게임ID", game_id_str)
                                        set_val("날짜", time.strftime("%Y-%m-%d %H:%M"))   # [2026-07-06 사장님 요청] 날짜+시작시간(로컬=KST). 웹 경기결과에 시간 표시. 과거 게임은 날짜만.
                                        set_val("소환사명", s_name)
                                        set_val("PUUID", p_puuid)
                                        set_val("진영", team_val)
                                        
                                        cached_pos_kor = "선택안함"
                                        for bp in temp_blue + temp_red:
                                            if str(bp['puuid']).strip().lower() == str(p_puuid).strip().lower(): 
                                                eng_pos = bp.get('chosen_pos_icon', 'NONE')
                                                cached_pos_kor = POSITION_TRANSLATE_KOR.get(eng_pos, "선택안함")
                                        set_val("포지션", cached_pos_kor)
                                        set_val("챔피언", kor_cname)
                                        set_val("밴", my_ban)
                                        set_val("결과", "결과 대기")
                                        set_val("KDA", "기록 대기")
                                        set_val("매치평가", "평가 대기")
                                        # 🛒 [v81.70] 룬은 라이브 playerlist(p.runes)에 있으므로 시작 시점 기록, 아이템은 종료(finalize/백필)에서.
                                        set_val("아이템", "기록 대기")
                                        set_val("지표", "기록 대기")   # 📊 [v82.26] finalize에서 상세지표 팩 기입
                                        try:
                                            _ru = p.get('runes') or {}
                                            _ks = (_ru.get('keystone') or {}).get('id')
                                            _pt = (_ru.get('primaryRuneTree') or {}).get('id')
                                            _st = (_ru.get('secondaryRuneTree') or {}).get('id')
                                            if _ks and _pt: set_val("주룬", f"{_ks}|{_pt}")
                                            if _st: set_val("보조룬", str(_st))
                                        except Exception: pass
                                        # 🔮 [v81.73] 소환사 스펠 — 라이브 playerlist summonerSpells.rawDisplayName에서 스펠키(SummonerFlash 등) 추출.
                                        try:
                                            _sp = p.get('summonerSpells') or {}
                                            _sk = []
                                            for _slot in ('summonerSpellOne', 'summonerSpellTwo'):
                                                _raw = str((_sp.get(_slot) or {}).get('rawDisplayName') or (_sp.get(_slot) or {}).get('rawDescription') or '')
                                                _m = re.search(r'(Summoner[A-Za-z]+)_(?:DisplayName|Description)', _raw)
                                                if _m: _sk.append(_m.group(1))
                                            if len(_sk) == 2: set_val("스펠", "|".join(_sk))
                                        except Exception: pass
                                        
                                        # 🔥 [V80.9] 패치 버전을 텍스트로 안전하게 작성 (이스케이프 문자)
                                        set_val("패치버전", f"v{PATCH_VERSION_SHORT}") 
                                        
                                        rows_to_append.append(row_data)
                                        team_color_cache.append((t_id_num, p_puuid, kor_cname.replace(" ", "")))
                                        roster_data.append(("B" if team_val == "블루팀" else "R", cached_pos_kor, kor_cname, s_name))   # 🎮 스코어보드용

                                    # [V81.48] 🧩 완전성 게이트 — 라이브 로스터(playerlist)가 밴픽 확정 인원만큼 다 로드됐을 때만 기록.
                                    #   근본원인: append 소스가 실시간 playerlist라 로딩 중 폴링이 '부분 로드' 순간(레드1명만 등)을 잡으면
                                    #   그 부분만 append → R1/B1R1처럼 여러 번 쪼개져 들어가 finalize 실패(결과대기)로 남던 문제.
                                    #   완전할 때만 1회 append → 정상처럼 B5 R5 나란히. 미완이면 이번 루프 기록 보류·다음 루프 재시도.
                                    _frozen_n = len([_p for _p in (temp_blue + temp_red)
                                                     if str(_p.get('puuid', '')).strip()
                                                     and not str(_p.get('puuid', '')).lower().startswith(('bot_', 'temp_'))])
                                    _live_n = len([_p for _p in lr_json if isinstance(_p, dict)])
                                    if len(_roster_wait_since) > 300: _roster_wait_since.clear()   # [리뷰반영] 메모리 상한(장수명 세션)
                                    _wait0 = _roster_wait_since.setdefault(fetched_game_id, time.time())
                                    _waited = time.time() - _wait0
                                    # 기대 인원 = 밴픽 확정 로스터(≥6)면 그 값, 미캡처(분석기 늦게 켬 등)면 표준 5v5=10 기준(리뷰반영: _frozen_n=0시 120s 지연 방지).
                                    _expected = _frozen_n if _frozen_n >= 6 else 10
                                    # 라이브 로스터가 기대 인원만큼 로드되면 즉시 기록. 미달이면 120초 후 현재값으로(무기록 방지).
                                    _roster_complete = (_live_n >= _expected) or (_waited > 120 and _live_n >= 6)
                                    if rows_to_append and not has_bot and not _roster_complete:
                                        with gui_lock: gui_data["status"] = f"⏳ 로스터 로딩 대기 ({_live_n}/{_frozen_n or '?'}인) — 완전해지면 기록"
                                    # 🚧 [2026-08-11 사장님 제보 '10명 중 한 명도 모르겠다'] 비클랜 판 기록 차단.
                                    #   분석기를 켠 사람이 우리 클랜원이 아니면 그 사람의 남의 내전까지 우리 시트에 들어오고
                                    #   시작 웹훅 → 봇 현황판에 남의 내전이 뜬다(8/11 21:07 #8336352560, 10인 전원 외부인).
                                    #   내부티어 로스터(CLAN_TIERS, 270명)에 한 명도 안 걸리면 우리 판이 아니다 → 기록·웹훅 모두 생략.
                                    #   실측: 과거 1002판 중 클랜원 0명인 판은 한 판도 없음(최소 1명) → 오탐 위험 없음.
                                    #   로스터 로드 실패(50명 미만)면 게이트를 열어 둔다(진짜 내전을 놓치는 쪽이 더 나쁨).
                                    if rows_to_append and _roster_complete and len(TIER_OF) >= 50:
                                        _clan_hit = sum(1 for _rd in roster_data if tier_of(_rd[3]))
                                        if _clan_hit == 0:
                                            if fetched_game_id not in nonclan_games:
                                                nonclan_games.add(fetched_game_id)
                                                print(f"[기록생략] 클랜원 0명 — 우리 내전이 아니라 판단해 기록·시작알림 모두 생략 ({game_id_str})", flush=True)
                                            with gui_lock: gui_data["status"] = "⏸️ 클랜원이 없는 판 — 기록하지 않습니다"
                                            rows_to_append = []
                                    # [트래픽↓ 2026-07-07 동시시작 429 완화] 신선한 col_values(서비스계정) 재확인+append는 '하위 순번(0~3)'만 수행.
                                    #   상위 순번은 서비스계정 안 건드리고 다음 루프에서 gviz(위 sheet_data_fresh)로 기록확인→existing_rows_count≥5면 스킵.
                                    #   → 2팀 동시시작 시 gviz stale이어도 서비스읽기 ~20 → ~8로 감소. 승자 append는 이미 게임당 1회.
                                    #   단 하위순번 전원 미가동 등으로 35초 넘게 미기록이면 상위 순번도 에스컬레이션해 반드시 기록(단일실패점 방지).
                                    if rows_to_append and not has_bot and _roster_complete and (_my_rank < 4 or _waited > 35):
                                        _appended_ok = False
                                        try: col_a_now = sheet_target.col_values(gid_idx + 1)   # 🔒 중복방지: append 직전 최신 게임ID열 재확인
                                        except Exception:
                                            col_a_now = []; _dedup_ok = False   # [V81.45] 재확인 실패(429 등) → 이번 루프 기록 보류(중복 원천 차단)
                                        # [모의테스트 HIGH 수정] 상위 순번(rank>0)은 낮은 순번의 append가 시트반영에 늦는 창을 대비해
                                        #   count가 0이면 한 번 더 짧게 대기 후 재확인 → 동시 append(중복 10행) 창을 더 좁힘.
                                        if _dedup_ok and _my_rank > 0 and col_a_now.count(game_id_str) == 0:
                                            time.sleep(1.5)
                                            try: col_a_now = sheet_target.col_values(gid_idx + 1)
                                            except Exception: pass
                                        # [2026-07-29 사장님 제보 — 한 판 20명] '5줄 미만'에서 '한 줄도 없을 때'로 좁힌다.
                                        #   완전성 게이트 도입 후로는 항상 10줄을 통째로 넣으므로, 한 줄이라도 있으면 남이 이미 쓴 것이다.
                                        if _dedup_ok and col_a_now.count(game_id_str) == 0:
                                            for _atry in range(2):   # [V81.45] 429 등 일시 오류 1회 재시도
                                                try:
                                                    if _atry > 0:
                                                        # [리뷰반영] 재시도 전 중복 재확인 — 백오프(2.5~4.5s)가 랭크시차(3s)보다 길어
                                                        #   그 사이 다른 인스턴스가 기록했을 수 있음. 재확인 불가면 보류(중복 위험 차단).
                                                        try:
                                                            if sheet_target.col_values(gid_idx + 1).count(game_id_str) > 0: break
                                                        except Exception: break
                                                    sheet_target.append_rows(rows_to_append); _appended_ok = True; break
                                                except Exception:
                                                    if _atry == 0: time.sleep(2.5 + random.uniform(0, 2))
                                            if _appended_ok:
                                                appended_game_ids.add(fetched_game_id)   # 이 인스턴스가 기록 주체 → 웹훅 발송 자격
                                                try: _noban_sheet_push(fetched_game_id, time.strftime("%Y-%m-%d %H:%M"))   # 🚫 노밴 선언 → NOBAN 탭(웹 표시용)
                                                except Exception: pass
                                        # 🎬 [V81.45] 게임 시작 알림 — 기록 승자(append 성공자)가 게임당 1회 발송.
                                        #    (구버전은 리더=로스터 1번만 발송 → 리더가 분석기 안 켜면 시작 신호 전멸이던 단일실패점 제거)
                                        if _appended_ok and fetched_game_id not in announced_starts:   # [2026-07-08] 서브게이트 (temp_blue or temp_red) 제거 — append 승자가 밴픽로스터 미보유(늦게켠/재시작 인스턴스)여도 시작웹훅 발송(lr_json 폴백, 종료웹훅과 대칭)
                                            try:
                                                def _cn_s(n): return str(n).split('#')[0].replace('🤖','').replace(' 봇','').strip()
                                                b_names_s = [_cn_s(p.get('name','')) for p in temp_blue if p.get('name')]
                                                r_names_s = [_cn_s(p.get('name','')) for p in temp_red if p.get('name')]
                                                if not (b_names_s or r_names_s):   # [2026-07-08] 밴픽 로스터 캐시 비면 append 소스 lr_json에서 직접 추출(append 승자는 반드시 lr_json 보유)
                                                    for _lp in lr_json:
                                                        if not isinstance(_lp, dict): continue
                                                        _nm = _cn_s(_lp.get('riotIdGameName') or _lp.get('summonerName') or '')
                                                        if not _nm or _nm.rstrip().endswith('봇'): continue
                                                        (b_names_s if _lp.get('team', 'ORDER') == 'ORDER' else r_names_s).append(_nm)
                                                _aram_tag = " ❄️(칼바람)" if is_aram_session else ""   # [v82.24] 자동내전기록에 칼바람 표시
                                                start_msg = (f"🎮 **{game_seq}경기 ({_rotation_label(game_seq)})**{_aram_tag}" + chr(10)
                                                             + "🟦 블루: " + ", ".join(b_names_s) + chr(10)
                                                             + "🟥 레드: " + ", ".join(r_names_s))
                                                _data_msg = None
                                                if roster_data:   # 🎮 [2026-07-08] 봇 진행판 스코어보드용 구조화 로스터(side^포지션^챔피언^이름). 봇만 파싱.
                                                    _ord = {"탑": 0, "정글": 1, "미드": 2, "원딜": 3, "서폿": 4}
                                                    _rd = sorted(roster_data, key=lambda x: (x[0], _ord.get(x[1], 8)))
                                                    _data_line = "🎯DATA: " + " | ".join(
                                                        "{}^{}^{}^{}".format(s, p, c, str(n).replace("|", "").replace("^", "")) for s, p, c, n in _rd)
                                                    if DATA_WEBHOOK_URL and not DATA_WEBHOOK_URL.startswith("여기에"):
                                                        # [v81.63 사장님 지시] 데이터줄을 전용 채널(#스해분데이터처리소)로 분리 — 자동내전기록은 사람용만.
                                                        _data_msg = start_msg + chr(10) + _data_line
                                                    else:
                                                        # 폴백(전용 웹훅 미설정): 기존 스포일러 방식으로 본문에 포함
                                                        start_msg += chr(10) + "-# ||" + _data_line + "||"
                                                broadcast_game_start_webhook(start_msg, data_text=_data_msg)
                                                announced_starts.add(fetched_game_id)
                                            except Exception: pass
                                        
                                        if _appended_ok:
                                            next_row = (len(col_a_now) if col_a_now else len(sheet_data_fresh)) + 1   # 🔧 next_row 미정의 NameError 수정
                                            new_indices = []
                                            for i, (t_id_n, player_puuid, player_c_kor) in enumerate(team_color_cache):
                                                new_indices.append((sheet_target, next_row + i, t_id_n, res_col_idx, ban_col_idx, kda_col_idx, eval_col_idx, patch_col_idx, player_puuid, player_c_kor))
                                            sheet_row_indices = new_indices
                                        
                                # [V81.45] 기록 확정 판정: 내가 저장했거나(_appended_ok), 남이 이미 저장(재확인 ≥5행)했을 때만.
                                #   확정 못 하면(429 폭주 등) 마킹하지 않고 다음 루프에서 통째로 재시도 → '기록 증발' 방지.
                                if not _record_confirmed:
                                    _record_confirmed = bool(_appended_ok)          # 내가 저장 성공
                                try:
                                    if (not _record_confirmed) and _dedup_ok and col_a_now.count(game_id_str) >= 5:
                                        _record_confirmed = True                     # 다른 인스턴스가 이미 기록 완료
                                except Exception: pass
                                if has_bot:
                                    recorded_game_ids.add(fetched_game_id)   # 🤖 봇 매치: 재처리 방지 마킹만, 기록·finalize 생략(#2)
                                    with gui_lock: gui_data["status"] = "🤖 봇 포함 매치 — 기록 생략됨"
                                elif _record_confirmed:
                                    recorded_game_ids.add(fetched_game_id)
                                    active_recording_id = fetched_game_id
                                    active_recording_sheet_name = target_sheet_name
                                    eog_retry_count = 0
                                    invalidate_sheet_cache(target_sheet_name)
                                else:
                                    time.sleep(3.0)   # 시트 일시 오류 — 마킹 없이 다음 루프에서 기록 재시도
                except Exception: pass
            
            # 🔥 [V81.24] 종료화면(전광판)이 보이는 순간 전원 스탯을 미리 캡처·캐시 — 플레이어가 곧장
            #    로비로 나가 전광판이 사라져도 최종 기록 때 이 캐시를 써서 '기록 누락'을 원천 방지.
            #    gid로 태깅 → 다음 게임에선 자동 재캡처(스테일 방지). 완전 로스터(≥6)일 때만 캐시.
            if (active_recording_id and current_phase in ("WaitingForStats", "EndOfGame", "PreEndOfGame")
                    and (eog_block_cache is None or eog_block_cache.get('gid') != active_recording_id)):
                try:
                    _eb = requests.get(str(base_url) + "/lol-end-of-game/v1/eog-stats-block", headers=headers, verify=False, timeout=3)
                    if _eb.status_code == 200:
                        _ebj = _eb.json()
                        if _ebj and _ebj.get('teams'):
                            _ebn = sum(len(t.get('players', []) or []) for t in _ebj.get('teams', []))
                            if _ebn >= EOG_MIN_ROSTER:
                                eog_block_cache = {'gid': active_recording_id, 'data': _ebj}
                except Exception: pass

            should_trigger_eog = False
            if active_recording_id is not None:
                if current_phase in ["PreEndOfGame", "EndOfGame", "WaitingForStats"]:
                    should_trigger_eog = True
                elif current_phase in ["Lobby", "Matchmaking", "ReadyCheck", "None"]:
                    should_trigger_eog = True

            if should_trigger_eog and is_valid_game and sheet_target:
                try:
                    # 🔥 [칼바람 MVP/역적 누락 수정] finalize는 항상 '기록 시작 시점의 시트'에 기록한다.
                    # 게임 종료 후 로비에서 is_aram_session이 풀리면(1066행) sheet_target이 협곡으로 바뀌어
                    # 칼바람 행을 협곡 시트에서 찾다 실패 → MVP/역적이 안 써지던 문제를 방지.
                    if active_recording_sheet_name and global_spreadsheet:
                        try: sheet_target = global_spreadsheet.worksheet(active_recording_sheet_name)
                        except Exception: pass
                    human_puuids = []
                    for p in temp_blue + temp_red:
                        p_uid = str(p.get('puuid', '')).strip().lower()
                        if p_uid and not p_uid.startswith('bot_') and not p_uid.startswith('temp_'):
                            human_puuids.append(p_uid)
                    human_puuids.sort()
                    
                    is_leader = False
                    if human_puuids and global_my_puuid == human_puuids[0]: is_leader = True
                    elif not human_puuids: is_leader = True 

                    if eog_retry_count == 0:
                        time.sleep(random.uniform(0.5, 1.5))   # 멀티 인스턴스 쓰기충돌 회피용 지터 — 게임당 1회만(재시도마다 재지불 안 함)
                    match_data = None

                    _md_verified = False   # [리뷰반영] match_data가 '이 게임'으로 검증됐는지(종료신호 오발 방지). eog(캐시 gid일치/라이브)만 True.
                    # 🔥 [V81.24] 미리 캡처해 둔 '이 게임'의 전광판 캐시 최우선 — 빨리 나가도 전원 기록(누락 방지).
                    if eog_block_cache and eog_block_cache.get('gid') == active_recording_id:
                        _cd = eog_block_cache.get('data') or {}
                        if _cd.get('teams') and sum(len(t.get('players', []) or []) for t in _cd.get('teams', [])) >= 2:
                            match_data = _cd; _md_verified = True

                    # 캐시가 없으면(캡처도 못한 극단적 빠른 이탈) 라이브 전광판 재시도.
                    # 커스텀 게임은 match-history에 '본인'만 담겨 나머지 9명이 누락되므로 전광판이 최우선.
                    if not match_data:
                        try:
                            eog_res = requests.get(str(base_url) + "/lol-end-of-game/v1/eog-stats-block", headers=headers, verify=False, timeout=3)
                            if eog_res.status_code == 200:
                                eog_json = eog_res.json()
                                if eog_json and eog_json.get('teams'):
                                    _cnt = sum(len(t.get('players', []) or []) for t in eog_json.get('teams', []))
                                    if _cnt >= 2: match_data = eog_json; _md_verified = True
                        except Exception: pass

                    # 전광판이 없으면(이미 로비로 빠진 뒤 등) 매치 히스토리로 폴백
                    if not match_data:
                        hist_url = str(base_url) + "/lol-match-history/v1/products/lol/current-summoner/matches"
                        try:
                            hist_res = requests.get(hist_url, headers=headers, verify=False, timeout=3)
                            if hist_res.status_code == 200:
                                games_list = hist_res.json().get('games', {}).get('games', [])
                                if games_list:
                                    for g in games_list:
                                        _gid_exact = str(g.get('gameId')) == str(active_recording_id)   # [리뷰반영] 정확 gameId 매칭만 검증됨(CUSTOM_ 무차별 매칭·games_list[0] 폴백은 미검증)
                                        if _gid_exact or "CUSTOM_" in str(active_recording_id):
                                            match_data = g; _md_verified = _gid_exact; break
                                    if not match_data and games_list:
                                        match_data = games_list[0]
                        except Exception: pass

                    # 참가자 수 확인 (본인만 담긴 불완전 데이터 판별)
                    _pcnt = 0
                    if match_data:
                        if match_data.get('participants'): _pcnt = len(match_data.get('participants') or [])
                        else: _pcnt = sum(len(t.get('players', []) or []) for t in match_data.get('teams', []))

                    # 🔥 [V81.24] 보통은 위 캐시로 전원(≥6) 확보됨. 그래도 부족하면 전광판 갱신을 더 기다리고,
                    #    끝내 캡처 자체가 실패한 극단적 경우에만 미기록(1명짜리 쓰레기 기록·단독 MVP 방지).
                    if _pcnt < EOG_MIN_ROSTER:
                        eog_retry_count += 1
                        if eog_retry_count < 8:
                            time.sleep(1.0)
                            continue
                        else:
                            active_recording_id = None   # 캡처 끝내 실패 → 불완전 기록 방지
                            eog_retry_count = 0
                            eog_write_retry = 0; _fin_write_retry = 0   # [리뷰반영] 게임 포기 시 재시도 예산도 대칭 리셋(방어적)
                            continue
                    
                    if match_data:
                        win_id = 0
                        for t in match_data.get('teams', []):
                            if t.get('isWinningTeam') == True or t.get('win') == 'Win' or t.get('win') == True:
                                win_id = t.get('teamId')
                                
                        achieves_list, mvp_puuid, mvp_cid, mvp_team_id, ace_puuid, ace_cid, ace_team_id, troll_puuid, troll_cid, troll_team_id, kda_map, score_map, dmg_map, item_map, metrics_map, pos_final_map = parse_endgame_achievements(
                            match_data, global_pos_map, champ_map, global_cached_blue, global_cached_red, is_aram_session
                        )

                        # 🏁 [2026-07-07 종료신호 분리] eog 확인 즉시 '경기 종료+로스터' 발송(finalize/_is_appender 무관).
                        #   → 1팀처럼 finalize가 결과대기로 멈추거나, 2팀처럼 마감 인스턴스 부재로 결과웹훅이 유실돼도
                        #     봇은 이 신호로 종료 인식(막판 제거·호출→참가). 봇은 팀 epoch 가드로 게임당 1회만 처리(중복 무해).
                        # [2026-07-08 도배완화] 종료웹훅을 append 승자(_is_appender)만 발송 → 3~4개 인스턴스 각자발송 도배를 1건화.
                        #   승자 부재/eog미포착 드문 케이스는 '매치 결과 리포트'(아래 리포트 발송 — 이제 finalizer가 확실히 발송)가 봇의 2차 종료신호로 커버 + 봇 75분 스윕 백스톱.
                        if _md_verified and (active_recording_id in appended_game_ids) and active_recording_id not in announced_ends:
                            try:
                                def _cn_e(n): return str(n).split('#')[0].replace('🤖','').replace(' 봇','').strip()
                                def _names_e(lst):
                                    out = []
                                    for p in (lst or []):
                                        nm = p.get('name') if isinstance(p, dict) else str(p)
                                        nm = _cn_e(nm)
                                        if nm and not nm.startswith('Wait') and not nm.startswith('대기'): out.append(nm)
                                    return out
                                _be = _names_e(global_cached_blue); _re = _names_e(global_cached_red)
                                if not (_be or _re):   # [리뷰반영] 캐시 비면(중간실행 인스턴스) match_data 참가자에서 직접 추출 → 캐시미스도 신호 발송
                                    _mdn = []
                                    for _tm in (match_data.get('teams') or []):
                                        for _p in (_tm.get('players') or []):
                                            _mdn.append(_cn_e(_p.get('summonerName') or _p.get('name') or ''))
                                    if not _mdn:
                                        for _pi in (match_data.get('participantIdentities') or []):
                                            _pl = _pi.get('player') or {}
                                            _mdn.append(_cn_e(_pl.get('gameName') or _pl.get('summonerName') or ''))
                                    _be = [x for x in _mdn if x]; _re = []
                                _nb_b = _noban_of_side(global_cached_blue)
                                _nb_r = _noban_of_side(global_cached_red)
                                _end_roster = ("🟦 블루: " + ", ".join(_be) + f"        (노밴 : {_nb_b})" + chr(10)
                                               + "🟥 레드: " + ", ".join(_re) + f"        (노밴 : {_nb_r})")
                                _ws = "블루" if win_id == 100 else ("레드" if win_id == 200 else None)   # 🎲 [2026-07-08] 승부예측 채점용 승리진영 부착(봇 _pred_winner가 파싱)
                                if _ws: _end_roster += chr(10) + "🏆 " + _ws + " 승"
                                broadcast_game_end_webhook(_end_roster)
                                announced_ends.add(active_recording_id)   # 로스터 비어도 마킹(결정적) — 마커만으로도 봇 종료 트리거
                            except Exception: pass

                        # 🔔 [웹훅] [A안 2026-07-06] 리포트는 '시트 평가 확정 후'에 발송(아래 finalize 성공 지점) →
                        #   웹훅↔시트가 항상 같은 '최종' 파스결과라 초박빙 ACE 불일치가 사라짐.
                        #   (예전엔 여기서 시트기록 전에 즉시 발송 → 이른 스냅샷 ACE가 나중에 시트에서 뒤집혀도 웹훅은 그대로 = 불일치)
                        #   (종료 로스터 메시지는 제거됨 — 매치 결과 리포트만. 봇은 '매치 결과 리포트'를 종료 신호로 인식.)

                        # [V81.45→V81.47] 쓰기 폭주 차단 + 행정합 정확성(리뷰반영).
                        _finalize_gid = f"#{active_recording_id}"
                        _is_appender = active_recording_id in appended_game_ids
                        def _gid_col(rows):
                            h = rows[0] if rows else []
                            return h.index("게임ID") if "게임ID" in h else 0
                        def _game_visible(rows):
                            if not rows: return False
                            gi = _gid_col(rows)
                            return any(len(r) > gi and r[gi] == _finalize_gid for r in rows[1:])
                        def _game_all_finalized(rows):
                            """이 게임 행이 존재하고 전부 결과·평가 기입 완료면 True(=더 쓸 것 없음)."""
                            if not rows: return False
                            h = rows[0]; gi = _gid_col(rows)
                            ri = h.index("결과") if "결과" in h else -1
                            ei = h.index("매치평가") if "매치평가" in h else -1
                            found = False
                            for r in rows[1:]:
                                if len(r) > gi and r[gi] == _finalize_gid:
                                    found = True
                                    res = r[ri] if ri != -1 and len(r) > ri else ""
                                    ev = r[ei] if ei != -1 and len(r) > ei else ""
                                    if not (res in ("승리", "패배") and ev not in ("", "평가 대기")):
                                        return False
                            return found
                        # 비주체(append 승자 아님)는 '결정적 순번(rank)' 양보 후 값싼 gviz로 '이미 마감?'만 확인 → 마감이면 스킵(쓰기 0).
                        #   [V81.48] 랜덤 15~30s → rank 계단(12 + rank*6s)으로 변경: 앞 순번이 먼저 마감하면 뒤 순번은 여기서 스킵 →
                        #   여러 비주체가 동시에 몰려 429 충돌·예산소진으로 '결과대기 영구화'되던 문제 해소. 주체 부재 시엔 순차로 반드시 1명이 마감.
                        if not _is_appender:
                            try:
                                if human_puuids and global_my_puuid in human_puuids:
                                    _fr = human_puuids.index(global_my_puuid)          # 이 게임 로스터 내 결정적 순번(0~9)
                                else:
                                    _fr = int(hashlib.md5(str(global_my_puuid or 'x').encode()).hexdigest(), 16) % 7  # 폴백: 인스턴스별 해시 분산(0~6)
                            except Exception: _fr = 0
                            time.sleep(12.0 + _fr * 6.0)
                            try: _pre = get_sheet_data_cached(sheet_target, force=True)   # gviz-first(할당량0)
                            except Exception: _pre = []
                            if _game_all_finalized(_pre):
                                active_recording_id = None; eog_write_retry = 0; _fin_write_retry = 0   # [리뷰반영] 쓰기예산도 리셋 — 같은 로비 연속게임(multi_id 불변)서 예산 누수로 다음 게임 조기포기 방지
                                continue
                        # 실제 기입은 항상 authoritative(서비스계정) 행번호 사용 — gviz 행드롭/오시트 리스크 제거(리뷰 #1/#9).
                        try: sheet_data_check = get_sheet_data_cached(sheet_target, force=True, prefer_service=True)
                        except Exception: sheet_data_check = []
                        if (not sheet_data_check) or (not _game_visible(sheet_data_check)):
                            eog_write_retry += 1
                            if eog_write_retry < 20:
                                time.sleep(5.0)
                                continue

                        if sheet_data_check:
                            headers_ch = sheet_data_check[0]
                            gid_c = headers_ch.index("게임ID") if "게임ID" in headers_ch else -1
                            res_c = headers_ch.index("결과") if "결과" in headers_ch else -1
                            puuid_c = headers_ch.index("PUUID") if "PUUID" in headers_ch else -1
                            champ_c = headers_ch.index("챔피언") if "챔피언" in headers_ch else -1
                            team_c = headers_ch.index("진영") if "진영" in headers_ch else -1
                            ban_c = headers_ch.index("밴") if "밴" in headers_ch else -1
                            kda_c = headers_ch.index("KDA") if "KDA" in headers_ch else -1
                            eval_c = headers_ch.index("매치평가") if "매치평가" in headers_ch else -1
                            patch_c = headers_ch.index("패치버전") if "패치버전" in headers_ch else -1
                            score_c = headers_ch.index("점수") if "점수" in headers_ch else -1
                            dmg_c = headers_ch.index("딜량") if "딜량" in headers_ch else -1
                            item_c = headers_ch.index("아이템") if "아이템" in headers_ch else -1   # 🛒 [v81.70]
                            met_c = headers_ch.index("지표") if "지표" in headers_ch else -1   # 📊 [v82.26]
                            pos_c = headers_ch.index("포지션") if "포지션" in headers_ch else -1   # 🧭 [v82.31]
                            
                            target_gid = f"#{active_recording_id}"
                            cells_to_update = []

                            # [모의테스트 HIGH — 잔여 중복 감지] 같은 게임ID + 같은 PUUID가 2회↑면 멀티인스턴스 동시 append 잔재(중복행).
                            #   구글시트는 원자적 락이 없어 100% 방지가 불가 → 남으면 감지해 로그·GUI로 알림(오삭제 위험 때문에 자동삭제 안 함, 수동 정리 유도).
                            if gid_c != -1 and puuid_c != -1:
                                _seen_pk, _dup_n = set(), 0
                                for _r in sheet_data_check[1:]:
                                    if len(_r) > max(gid_c, puuid_c) and _r[gid_c] == target_gid:
                                        _pk = _r[puuid_c].strip().lower()
                                        if _pk and _pk in _seen_pk: _dup_n += 1
                                        elif _pk: _seen_pk.add(_pk)
                                if _dup_n > 0:
                                    print(f"[중복감지] {target_gid} 중복행 {_dup_n}개 — 시트에서 수동 정리 필요(동시기록 잔재)", flush=True)
                                    with gui_lock: gui_data["status"] = f"⚠️ {target_gid} 중복행 {_dup_n}개 감지 — 시트 확인 요망"

                            if gid_c != -1:
                                for r_idx, r in enumerate(sheet_data_check):
                                    if r_idx == 0: continue
                                    if len(r) > gid_c and r[gid_c] == target_gid:
                                        
                                        r_res = r[res_c] if res_c != -1 and len(r) > res_c else ""
                                        r_eval = r[eval_c] if eval_c != -1 and len(r) > eval_c else ""
                                        
                                        if r_res in ["승리", "패배"] and r_eval not in ["", "평가 대기"]:
                                            continue
                                            
                                        row_num = r_idx + 1
                                        row_puuid = r[puuid_c].strip().lower() if puuid_c != -1 and len(r) > puuid_c else ""
                                        row_team_str = r[team_c] if team_c != -1 and len(r) > team_c else ""
                                        row_champ_str = r[champ_c].replace(" ", "") if champ_c != -1 and len(r) > champ_c else ""
                                        t_id_num = 100 if row_team_str == "블루팀" else (200 if row_team_str == "레드팀" else 0)
                                        
                                        res_str = "승리" if t_id_num == win_id else "패배"
                                        if res_c != -1: cells_to_update.append(gspread.Cell(row=row_num, col=res_c+1, value=res_str))
                                        
                                        if ban_c != -1:
                                            existing_ban = r[ban_c] if len(r) > ban_c else ""
                                            my_ban = ""
                                            if not existing_ban or existing_ban in ["대기 중", "기록 대기", "", "밴 없음"]:
                                                my_ban = frozen_user_bans.get(row_puuid, "")
                                                if not my_ban:
                                                    for k_uid, v_ban in frozen_user_bans.items():
                                                        if k_uid in row_puuid or row_puuid in k_uid:
                                                            my_ban = v_ban; break
                                                if not my_ban:
                                                    if is_aram_session or not global_captured_bans: my_ban = "밴 없음"
                                                    else: my_ban = "밴 안함"
                                                cells_to_update.append(gspread.Cell(row=row_num, col=ban_c+1, value=my_ban))
                                            
                                        row_cid = 0
                                        for k, v in global_champ_map.items():
                                            if v['kor'].replace(" ", "") == row_champ_str: row_cid = k; break
                                        if row_cid == 0:
                                            for k, v in GLOBAL_NUMERIC_CHAMP_MAP.items():
                                                if v == row_champ_str: row_cid = k; break
                                            
                                        if kda_c != -1:
                                            kda_val = kda_map.get(row_puuid) or kda_map.get(f"{t_id_num}_{row_cid}") or "-"
                                            if kda_val: cells_to_update.append(gspread.Cell(row=row_num, col=kda_c+1, value=kda_val))

                                        # 🛒 [v81.70] 최종 아이템 빌드 ("id|id|..." — 웹이 ddragon 아이콘으로 렌더)
                                        if item_c != -1:
                                            _iv = item_map.get(row_puuid) or item_map.get(f"{t_id_num}_{row_cid}")
                                            cells_to_update.append(gspread.Cell(row=row_num, col=item_c+1, value=_iv if _iv else ""))

                                        # 🔥 웹 AI-Score/딜량 기록 (0·음수도 안전하게 — None만 스킵)
                                        if score_c != -1:
                                            sv = score_map.get(row_puuid)
                                            if sv is None: sv = score_map.get(f"{t_id_num}_{row_cid}")
                                            if sv is not None: cells_to_update.append(gspread.Cell(row=row_num, col=score_c+1, value=sv))
                                        if dmg_c != -1:
                                            dv = dmg_map.get(row_puuid)
                                            if dv is None: dv = dmg_map.get(f"{t_id_num}_{row_cid}")
                                            if dv is not None: cells_to_update.append(gspread.Cell(row=row_num, col=dmg_c+1, value=dv))

                                        # 🧭 [v82.31] 포지션 확정 — 시작 시점 값은 커스텀에서 인덱스 추측이라 틀릴 수 있어
                                        #   실제 플레이 기준(EOG)으로 덮어쓴다. EOG에 없으면 기존 값 유지.
                                        if pos_c != -1:
                                            _pv = pos_final_map.get(row_puuid) or pos_final_map.get(f"{t_id_num}_{row_cid}")
                                            _pold = r[pos_c] if len(r) > pos_c else ""
                                            if _pv and _pv != _pold:
                                                cells_to_update.append(gspread.Cell(row=row_num, col=pos_c+1, value=_pv))
                                                print(f"[포지션정정] {target_gid} {_pold or '(빈칸)'} → {_pv}", flush=True)

                                        # 📊 [v82.26] 상세지표 팩 + 픽순서(드래프트만, pk1~10)
                                        if met_c != -1:
                                            _mv = metrics_map.get(row_puuid) or metrics_map.get(f"{t_id_num}_{row_cid}") or ""
                                            _po = frozen_pick_order.get(row_puuid)
                                            if _po: _mv = (_mv + "|" if _mv else "") + f"pk{_po}"
                                            cells_to_update.append(gspread.Cell(row=row_num, col=met_c+1, value=_mv))
                                            
                                        eval_str = "평가 없음"
                                        is_mvp = False
                                        is_ace = False
                                        is_troll = False

                                        # 🎭 [v82.30] puuid로 판정 가능하면 챔피언 대체판정을 쓰지 않는다.
                                        #   (구버전은 puuid 불일치 시 챔프ID로 넘어가, 니코가 변신 대상의 MVP를 같이 받는 사고 발생)
                                        def _hit(_pu, _cid, _tid):
                                            _pu = str(_pu or "").strip().lower()
                                            if row_puuid and _pu: return row_puuid == _pu       # 양쪽 puuid 확보 → 이것만 신뢰
                                            return bool(row_cid and _cid and row_cid == _cid and t_id_num == _tid)
                                        is_mvp = _hit(mvp_puuid, mvp_cid, mvp_team_id)
                                        is_ace = _hit(ace_puuid, ace_cid, ace_team_id)
                                        is_troll = _hit(troll_puuid, troll_cid, troll_team_id)

                                        if is_mvp: eval_str = "MVP"
                                        elif is_ace: eval_str = "ACE"
                                        elif is_troll: eval_str = "역적"
                                        
                                        if eval_c != -1: cells_to_update.append(gspread.Cell(row=row_num, col=eval_c+1, value=eval_str))
                                        
                                        # 🔥 [V80.9] 패치 버전을 텍스트로 안전하게 고정
                                        if patch_c != -1: cells_to_update.append(gspread.Cell(row=row_num, col=patch_c+1, value=f"v{PATCH_VERSION_SHORT}"))

                            if cells_to_update:
                                # [V81.45] '결과 대기 영원' 수정 / [2026-07-07 쓰기429 근본완화] 예전엔 실패 시 최대 20회×3=60번 update_cells를
                                #   짧은 간격(5s)으로 재시도 → 피크(2~3로비 종료 클러스터)에 분당 쓰기할당량(≈60/분)을 재시도가 스스로 소진하는 악순환.
                                #   ①429면 내부 즉시중단(짧은 연타 무의미) ②외부 20→8회·5s→25~45s 롱백오프(할당량 창≈60s 리셋 대기)
                                #   → 낭비 쓰기 60→~8회, 인스턴스별 지터로 재시도 분산 → 성공률↑·결과대기↓.
                                _final_ok = False; _last_429 = False
                                for _try in range(3):
                                    try:
                                        sheet_target.update_cells(cells_to_update)
                                        invalidate_sheet_cache(sheet_target.title)
                                        _final_ok = True
                                        break
                                    except Exception as _fe:
                                        _last_429 = ('429' in str(_fe)) or ('quota' in str(_fe).lower()) or ('rate' in str(_fe).lower())
                                        print(f"[finalize] 결과 기록 실패(시도 {_try+1}/3, 429={_last_429}): {type(_fe).__name__}", flush=True)
                                        if _last_429: break                    # 할당량 소진 → 내부 연타 무의미, 외부 롱백오프로
                                        if _try < 2: time.sleep(2.0 * (_try + 1) + random.uniform(0, 2))
                                if not _final_ok:
                                    _fin_write_retry += 1        # [2026-07-07] finalize '쓰기' 전용 카운터 — 위 '행 가시성 대기'(eog_write_retry)와 예산 분리(공유 시 가시성대기가 쓰기예산 잠식하던 문제 차단)
                                    if _fin_write_retry < 8:      # 대기가 길어졌으니 횟수↓(낭비 쓰기 60→~8, 총 재시도 ~5분)
                                        time.sleep(random.uniform(25, 45) if _last_429 else 5.0)   # 429=할당량 리셋 대기+지터, 일시오류=짧게
                                        continue
                                    else:
                                        print(f"[finalize] ⚠️ {_finalize_gid} 결과기입 최종포기(8회 초과) → 결과대기 잔존", flush=True)

                            # [2026-07-07 리포트 유실 수정 / 2026-07-08 발송게이트 이동] _final_ok(시트 마감 성공) 게이트는 v81.56에서 제거됨
                            #   (마감이 429로 실패해도 리포트는 나가도록). 그런데 발송이 'if cells_to_update:' 안에 있어, 비주체가 finalize
                            #   경쟁을 먼저 이겨 전 행을 마감해버리면(비주체는 12s+ 핸디캡이라 드묾) 주체의 다음 루프에서 모든 행이 이미 마감돼
                            #   cells_to_update가 비고→블록 스킵→리포트 미발송(비주체는 _is_appender=False라 원래 안 쏨)이던 NIT(2026-07-07 리뷰).
                            #   발송을 블록 밖(마감/쓰기 여부 무관)으로 이동해 해소. achieves_list는 시트에 쓰는 값과 동일 파스라 발송해도 불일치 없음.
                            #   dedup: _is_appender(append 주체 단독 발송) + posted_game_ids(인스턴스내 1회) → 채널 중복 없음.
                            #   _game_visible 가드: 행이 실제 시트에 존재할 때만 발송(20회 가시성대기 포기한 '행 미출현' 극단케이스 배제).
                            # [2026-07-08 리포트 유실 근본수정] _is_appender(게임'시작' append 승자) 게이트 제거 —
                            #   리포트는 finalize(게임종료) 시점 발송인데, 시작 append 승자가 늦게켠/eog포기 인스턴스면 finalize를 실제 완료한 '다른'(비주체) 인스턴스가
                            #   시트는 마감하지만 _is_appender=False라 리포트를 못 쏴 매 게임 유실됐음. 이제 finalize 지점 도달(=행 가시+마감 수행) 인스턴스가 발송.
                            #   단일발송 유지: 비주체는 rank 스태거(L3012) 후 '이미 마감?' 확인되면 continue(L3017)로 여기 도달 안 함 → 실제 마감 수행한 ~1인스턴스만 도달. posted_game_ids로 인스턴스내 1회.
                            try:   # 🏅 [v82.48] 게임 간 타이틀(하루 판수·연승·다재다능·스토커) 합류
                                _xt = cross_game_titles(sheet_data_check, _finalize_gid)
                                if _xt: achieves_list = list(achieves_list) + _xt
                            except Exception: pass
                            if achieves_list and _game_visible(sheet_data_check) and (active_recording_id not in posted_game_ids):
                                posted_game_ids.add(active_recording_id)
                                try:   # 🚫 [v82.46] 노밴 진영 판정용 팀 로스터 미러 — global_cached_blue/red는 이 루프의
                                    #    지역변수라 웹훅 함수(모듈 스코프)에서 못 읽음 → 발송 직전 모듈 전역에 복사
                                    _NB_TEAMS["blue"] = list(global_cached_blue or [])
                                    _NB_TEAMS["red"] = list(global_cached_red or [])
                                except Exception: pass
                                try: broadcast_to_discord_webhook(chr(10).join(achieves_list))
                                except Exception: pass

                        if achieves_list:
                            with gui_lock:
                                gui_data["achievements"] = achieves_list

                        active_recording_id = None
                        eog_retry_count = 0
                        eog_write_retry = 0
                        _fin_write_retry = 0
                except Exception as _ee:
                    print(f"[finalize] 예외로 결과대기 잔존 가능: {type(_ee).__name__} {str(_ee)[:120]}", flush=True)
        except Exception: pass
        time.sleep(1.0)
# =========================================================================================

def parse_endgame_achievements(match_data, pos_map, champ_map, blue_players, red_players, is_aram=False):
    achievements = []
    mvp_puuid_out = ""
    mvp_cid_out = 0
    mvp_team_id_out = 0
    ace_puuid_out = ""
    ace_cid_out = 0
    ace_team_id_out = 0
    troll_puuid_out = ""
    troll_cid_out = 0
    troll_team_id_out = 0
    kda_map = {}
    score_map = {}   # AI 종합점수 (웹 AI-Score용) : puuid / "{t_id}_{c_id}" -> 점수
    dmg_map = {}     # 챔피언에게 가한 피해량 (웹 딜량바용)
    pos_final_map = {}   # 🧭 [v82.31] 확정 포지션(한글) — finalize가 시트 '포지션'을 실제값으로 정정
    metrics_map = {} # 📊 [v82.26] 상세지표 팩 "g골드|cs|m분|kp킬관여%|vs시야|cw제어와드|wp|wk|op오브젝트관여%|tk포탑킬|dt받은피해|hs힐실드|dr용|br바론" ([v82.28] od→op: 오브젝트 딜 폐기, 처치 관여율로)
    _team_obj = {100: 0, 200: 0}   # [v82.28] 팀별 에픽 오브젝트(용+바론) 처치 수 — op 분모
    item_map = {}    # 🛒 [v81.70] 최종 아이템 빌드 "id|id|..." : puuid / "{t_id}_{c_id}"
    def _items_join(p):
        try:
            if isinstance(p.get('items'), list):   # eog-stats-block 포맷
                return "|".join(str(int(x)) for x in p['items'] if x)
            st = p.get('stats') or {}
            out = []
            for _ik in ("ITEM0","ITEM1","ITEM2","ITEM3","ITEM4","ITEM5","ITEM6",
                        "item0","item1","item2","item3","item4","item5","item6"):
                v = st.get(_ik)
                if v:
                    try: out.append(str(int(v)))
                    except Exception: pass
            return "|".join(out)
        except Exception:
            return ""

    try:
        puuid_to_true_name = {}
        for p in blue_players + red_players:
            if p.get('puuid'):
                puuid_to_true_name[p['puuid'].strip().lower()] = p['name']

        game_duration = match_data.get('gameLength', match_data.get('gameDuration', 0))
        try: game_duration = float(game_duration)            # 비숫자(문자열 등) 방어 — 분당계산 TypeError로 리포트 통째 증발하던 버그
        except Exception: game_duration = 0.0
        teams = {100: {'kills': 0, 'win': False}, 200: {'kills': 0, 'win': False}}
        
        for team in match_data.get('teams', []):
            if isinstance(team, dict):
                t_id = team.get('teamId')
                if t_id in teams: 
                    teams[t_id]['win'] = (team.get('isWinningTeam') == True or team.get('win') == 'Win' or team.get('win') == True)
                    
        participants = match_data.get('participants') or []
        participant_identities = match_data.get('participantIdentities') or []
        
        if not participants:
            for t in match_data.get('teams', []):
                tid = t.get('teamId')
                try: tid = int(tid)
                except Exception: pass
                for p in t.get('players', []):
                    p['teamId'] = tid
                    participants.append(p)
        
        id_to_name = {}
        puuid_to_name_from_identities = {}
        
        if participant_identities:
            for pi in participant_identities:
                if isinstance(pi, dict):
                    p_id = pi.get('participantId')
                    player = pi.get('player') or {}
                    if isinstance(player, dict):
                        name = player.get('gameName') or player.get('summonerName') or player.get('riotIdGameName') or f"유저{p_id}"
                        puuid = player.get('puuid') or ""
                        id_to_name[p_id] = name
                        puuid_to_name_from_identities[p_id] = str(puuid).strip().lower()
        else:
            for p in participants:
                p_id = p.get('participantId', p.get('summonerId', 0))
                name = p.get('summonerName') or p.get('gameName') or p.get('riotIdGameName') or f"유저{p_id}"
                puuid = p.get('puuid') or ""
                id_to_name[p_id] = name
                puuid_to_name_from_identities[p_id] = str(puuid).strip().lower()

        role_map = {100: {}, 200: {}}
        for p in participants:
            if isinstance(p, dict):
                t_id = p.get('teamId')
                p_id = p.get('participantId', p.get('summonerId', 0))
                puuid = puuid_to_name_from_identities.get(p_id)
                
                if not puuid:
                    riot_id = f"{p.get('riotIdGameName','')}#{p.get('riotIdTagLine','')}".lower().strip()
                    c_name = p.get('summonerName','').replace("🤖", "").replace(" 봇", "").strip().lower()
                    puuid = global_puuid_fallback_map.get(riot_id) or global_puuid_fallback_map.get(c_name)
                
                if puuid: puuid = puuid.strip().lower()

                # 🧭 [v82.31] 실제 플레이 포지션(EOG teamPosition) 우선 — 커스텀 내전은 밴픽에 포지션 배정이 없어
                #   pos_map이 '로스터 인덱스 추측값'이라 신뢰 불가(원딜이 서폿으로 잡히던 원인). EOG 값이 없을 때만 폴백.
                _eogp = str(p.get('teamPosition') or p.get('individualPosition') or '').upper()
                role = _eogp if _eogp in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY") else (pos_map.get(puuid, "NONE") if puuid else "NONE")

                if t_id in role_map and role != "NONE":
                    role_map[t_id][role] = p
                    
        # 팀 총 킬 (KP% 계산용) — 기존엔 미집계라 전투민족 업적도 안 떴음
        for _p in participants:
            if isinstance(_p, dict):
                _t = _p.get('teamId')
                _st = _p.get('stats', _p)
                if isinstance(_st, dict) and _t in teams:
                    teams[_t]['kills'] += _st.get('kills', _st.get('CHAMPIONS_KILLED', 0))
                    # [v82.28] 팀 에픽 오브젝트(용+바론) 처치 합 — 오브젝트 처치 관여율(op) 분모
                    _team_obj[_t] = _team_obj.get(_t, 0) + int(_st.get('dragonKills', _st.get('DRAGON_KILLS', 0)) or 0) + int(_st.get('baronKills', _st.get('BARON_KILLS', 0)) or 0)

        player_scores = []
        for p in participants:
            if not isinstance(p, dict): continue
            t_id = p.get('teamId')
            if t_id not in teams: continue
            stats = p.get('stats', p)
            if not isinstance(stats, dict): continue
            
            p_id = p.get('participantId', p.get('summonerId', 0))
            puuid = puuid_to_name_from_identities.get(p_id)
            
            if not puuid:
                riot_id = f"{p.get('riotIdGameName','')}#{p.get('riotIdTagLine','')}".lower().strip()
                c_name = p.get('summonerName','').replace("🤖", "").replace(" 봇", "").strip().lower()
                puuid = global_puuid_fallback_map.get(riot_id) or global_puuid_fallback_map.get(c_name)
                
            if puuid: puuid = puuid.strip().lower()
            
            name = puuid_to_true_name.get(puuid)
            if not name: name = id_to_name.get(p_id, f"유저{p_id}")

            c_id = p.get('championId', 0)

            # 🏷️ [v81.71] '유저{숫자}' 노출 수정 — 최근 롤 패치로 종료 데이터의 summonerName이 빈 값으로 오는
            #   플레이어 발생(라이엇 소환사명 → Riot ID 전환). 밴픽 캐시 없는 인스턴스(늦게 켠/재시작)가 마감하면
            #   숫자 폴백이 그대로 리포트에 노출 → ①riotIdGameName(신표준) ②라이브 로스터의 챔피언→이름 맵으로 보강.
            if (not name) or str(name).startswith("유저"):
                _rn71 = str(p.get('riotIdGameName') or '').strip()
                if _rn71: name = _rn71
            if (not name) or str(name).startswith("유저"):
                try:
                    _eng71 = str((global_champ_map.get(c_id) or {}).get('eng', '')).replace(' ', '').lower()
                    _gn71 = global_ingame_names.get(_eng71)
                    if _gn71: name = str(_gn71).split('#')[0]
                except Exception: pass
            # 🎭 [2026-08-08 사장님 제보: 푸비니정리→리 신] 폴백이 챔피언 이름을 소환사명으로
            #   흘리면 웹 닉변 병합이 그걸 최신 닉으로 뽑는다 — 챔피언명과 같으면 무효 처리
            try:
                _kor71 = str((global_champ_map.get(c_id) or {}).get('kor', '')).replace(' ', '')
                if name and _kor71 and str(name).replace(' ', '') == _kor71:
                    name = f"유저{c_id}"
            except Exception: pass
            
            # 🧭 [v82.31] EOG 실제 포지션 우선(위와 동일 이유) — AI 평가의 역할별 데스 페널티도 이 값을 씀
            _eogp = str(p.get('teamPosition') or p.get('individualPosition') or '').upper()
            role = _eogp if _eogp in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY") else (pos_map.get(puuid, "NONE") if puuid else "NONE")
            if role != "NONE":
                _pk = POSITION_TRANSLATE_KOR.get(role)
                if _pk:
                    if puuid: pos_final_map[puuid] = _pk
                    pos_final_map[f"{t_id}_{c_id}"] = _pk

            is_win = teams[t_id]['win']
            deaths = stats.get('deaths', stats.get('NUM_DEATHS', 0))
            kills = stats.get('kills', stats.get('CHAMPIONS_KILLED', 0))
            assists = stats.get('assists', stats.get('ASSISTS', 0))
            dmg_dealt = stats.get('totalDamageDealtToChampions', stats.get('TOTAL_DAMAGE_DEALT_TO_CHAMPIONS', 0))
            dmg_taken = stats.get('totalDamageTaken', stats.get('TOTAL_DAMAGE_TAKEN', 0))
            penta = stats.get('pentaKills', stats.get('PENTA_KILLS', 0))
            vision = stats.get('visionScore', stats.get('VISION_SCORE', 0))
            champ_level = stats.get('champLevel', stats.get('LEVEL', 0))
            gold_earned = stats.get('goldEarned', stats.get('GOLD_EARNED', 0))
            
            # 🔥 [V80.9] 유틸 서포터를 위한 힐/보호막(HPS) 점수 반영
            heal_amount = stats.get('totalHealOnTeammates', stats.get('TOTAL_HEAL_ON_TEAMMATES', stats.get('totalHeal', stats.get('TOTAL_HEAL', 0))))
            shield_amount = stats.get('totalDamageShieldedOnTeammates', stats.get('TOTAL_DAMAGE_SHIELDED_ON_TEAMMATES', 0))
            # 🔥 [V81.7] CS·오브젝트 지표
            minions = stats.get('totalMinionsKilled', stats.get('MINIONS_KILLED', 0))
            neutral = stats.get('neutralMinionsKilled', stats.get('NEUTRAL_MINIONS_KILLED', 0))
            turret_kills = stats.get('turretKills', stats.get('TURRETS_KILLED', 0))
            obj_dmg = stats.get('damageDealtToObjectives', stats.get('TOTAL_DAMAGE_DEALT_TO_OBJECTIVES', stats.get('damageDealtToTurrets', 0)))
            # 📊 [v82.26] 상세지표 추가 수집(제어와드·와드·용/바론)
            ctrl_wards = stats.get('visionWardsBoughtInGame', stats.get('VISION_WARDS_BOUGHT_IN_GAME', 0))
            wards_placed = stats.get('wardsPlaced', stats.get('WARD_PLACED', 0))
            wards_killed = stats.get('wardsKilled', stats.get('WARD_KILLED', 0))
            dragon_k = stats.get('dragonKills', stats.get('DRAGON_KILLS', 0))
            baron_k = stats.get('baronKills', stats.get('BARON_KILLS', 0))

            kda_str = f"{kills}/{deaths}/{assists}"
            if puuid: kda_map[puuid] = kda_str
            kda_map[f"{t_id}_{c_id}"] = kda_str
            _itm = _items_join(p)   # 🛒 최종 아이템 빌드
            if _itm:
                if puuid: item_map[puuid] = _itm
                item_map[f"{t_id}_{c_id}"] = _itm
            
            # 🔥 [V81.7] 평점 공식 개편 — 분당 정규화 + KP% + 오브젝트/CS + 데스 삼중차감 완화
            safe_d = max(1, deaths)
            mins = game_duration / 60.0
            if mins < 1.0:                  # 0/누락/음수(리메이크·부분읽힘) → 분당지표 폭주 방지: 평균 게임길이로 가정
                mins = 25.0
            team_kills = teams[t_id]['kills']

            # 1) 전투 관여 (킬+어시) — [v82.38] ÷데스 폐지, ÷분(분당 관여)으로 전환.
            #    사유(실측): 기존 (킬+어시)/데스 는 데스를 KDA 분모로 한 번, 아래 데스페널티로 또 한 번 차감하는
            #    '이중차감'이라 데스↔점수 상관이 −0.71(킬 +0.40·어시 +0.35보다 강함)로 데스가 점수를 지배했음.
            #    → 6데스 이상인데 MVP 되는 비율이 4%뿐(전체 판의 49%가 6데스↑인데)이라 '캐리형(고킬 고데스)'이 배제됨.
            #    분당 관여로 바꾸면 데스는 아래 페널티에서만 반영 → 상관 −0.50, 6데스 MVP 4%→15%로 정상화.
            #    가중 18.0 = 기존 점수대(평균 ~26)와 비슷하게 유지(웹 점수칩·십이귀월 산식 호환)하며 데스 지배만 완화.
            kda_score = ((kills + assists) / mins) * 18.0
            # 2) 킬관여 KP% (팀 기여) — 1.0(100%)로 상한: 어시 폭주(예 39어시)가 KP점수를 과보상하던 문제 차단
            kp = min(1.0, (kills + assists) / max(1, team_kills))
            kp_score = kp * 12.0
            # 3) 분당 딜 (÷데스 → ÷분 정규화: 게임 길이/데스 영향 분리)
            dmg_score = (dmg_dealt / mins) / 1000.0 * 7.0
            # 4) 분당 받은피해(탱)
            tank_score = (dmg_taken / mins) / 1000.0 * 2.0
            # 5) 분당 힐/보호막 (서폿 인챈터 기여)
            heal_shield_score = ((heal_amount + shield_amount) / mins) / 1000.0 * 5.0
            # 6) 분당 시야 [2026-07-06 사장님 지시: 서폿 ACE 편중(전체 ACE의 50.6%) 교정 → 시야 가중 3.5→2.0 추가 하향.
            #    (v81.47에 5.0→3.5 했으나 여전히 서폿 우세) 시야는 역할무관 공통항이나 분당시야가 압도적인 서폿에 실질 최대 작용]
            vision_score_calc = (vision / mins) * 2.0
            # 7) 분당 CS (파밍)
            cs_score = ((minions + neutral) / mins) * 0.5
            # 8) 오브젝트 (포탑킬 + 분당 오브젝트 딜)
            obj_score = turret_kills * 1.5 + (obj_dmg / mins) / 1000.0 * 1.5

            # 9) 데스 페널티 (역할별 배수) — [v82.38] KDA 이중차감 제거에 맞춰 전 포지션 완화.
            #    기존(탑1.0/정글1.3/미드1.8/원딜1.8/서폿1.1)은 미드·원딜(1.8)이 과벌받아 포지션 평균이 낮았음
            #    (정글29.8↔미드24.0, 격차 5.8). 미드·원딜을 1.3으로 낮춰 정글과 균형 → 격차 2.9로 축소.
            penalty_multiplier = 1.5
            if not is_aram:
                if role == "BOTTOM": penalty_multiplier = 1.3
                elif role == "MIDDLE": penalty_multiplier = 1.3
                elif role == "JUNGLE": penalty_multiplier = 1.1
                elif role == "TOP": penalty_multiplier = 0.9
                elif role == "UTILITY": penalty_multiplier = 1.0
            death_penalty = deaths * penalty_multiplier

            ai_score = (kda_score + kp_score + dmg_score + tank_score + heal_shield_score
                        + vision_score_calc + cs_score + obj_score - death_penalty)

            player_scores.append({
                'name': name, 'puuid': str(puuid), 'c_id': c_id, 't_id': t_id, 'score': ai_score,
                'role': role,                                  # 🔥 같은 역할(라인 맞상대) 비교용
                'k': kills, 'd': deaths, 'a': assists, 'kp': round(kp * 100),
                'dmg': dmg_dealt, 'tank': dmg_taken, 'hs': heal_amount + shield_amount, 'vs': vision
            })
            # 🔥 웹 AI-Score/딜량용 맵 (KDA와 동일한 키 방식 → 동일 매칭 보장)
            if puuid:
                score_map[puuid] = round(ai_score, 1)
                dmg_map[puuid] = int(dmg_dealt)
            score_map[f"{t_id}_{c_id}"] = round(ai_score, 1)
            dmg_map[f"{t_id}_{c_id}"] = int(dmg_dealt)
            # 📊 [v82.26] 상세지표 팩 — 시트 '지표' 1열에 압축 저장(열 증식 방지). DPM/GPM/분당CS/골드대비딜은 g·cs·m으로 파생 계산.
            try:
                # [v82.28] op = 오브젝트 처치 관여율(%) — (내 용+바론 처치)/(팀 용+바론 처치). EOG는 어시 미제공이라 킬 기준(백필 Match-V5분은 관여 포함).
                _to = _team_obj.get(t_id, 0)
                _op_part = f"|op{round((int(dragon_k) + int(baron_k)) / _to * 100)}" if _to > 0 else ""
                _met = (f"g{int(gold_earned)}|cs{int(minions) + int(neutral)}|m{mins:.1f}|kp{round(kp * 100)}"
                        f"|vs{int(vision)}|cw{int(ctrl_wards)}|wp{int(wards_placed)}|wk{int(wards_killed)}"
                        f"{_op_part}|tk{int(turret_kills)}|dt{int(dmg_taken)}|hs{int(heal_amount + shield_amount)}"
                        f"|dr{int(dragon_k)}|br{int(baron_k)}")
                if puuid: metrics_map[puuid] = _met
                metrics_map[f"{t_id}_{c_id}"] = _met
            except Exception: pass
            
            p_achieves = []
            
            if not is_aram:
                if is_win and game_duration <= 960: p_achieves.append("⏱ [이차가 식기전에] 16분 이전 게임 승리자")
                if is_win and game_duration >= 3000: p_achieves.append("⏳ [진흙탕싸움] 50분 이상 게임 승리자")
                if is_win and deaths == 0: p_achieves.append("🛡 [불사대마왕] 노데스 게임 승리")
                if is_win and dmg_dealt >= 80000: p_achieves.append("⚔ [사디스트] 딜량 8만이상 달성 후 승리")
                if is_win and dmg_taken >= 120000: p_achieves.append("🩸 [마조히스트] 받은피해량 12만이상 달성 후 승리")
                if penta >= 1: p_achieves.append(f"💀 [학살자] 펜타킬 {penta}회 달성")
                    
                opp_t_id = 200 if t_id == 100 else 100
                opp_p = role_map[opp_t_id].get(role, {})
                opp_stats = opp_p.get('stats', opp_p)
                
                if opp_stats:
                    opp_gold = opp_stats.get('goldEarned', opp_stats.get('GOLD_EARNED', 0))
                    opp_lvl = opp_stats.get('champLevel', opp_stats.get('LEVEL', 0))
                    opp_kp = opp_stats.get('kills', opp_stats.get('CHAMPIONS_KILLED', 0)) + opp_stats.get('assists', opp_stats.get('ASSISTS', 0))
                    opp_assists = opp_stats.get('assists', opp_stats.get('ASSISTS', 0))
                    
                    if game_duration <= 2400 and (gold_earned - opp_gold) >= 5000:
                        p_achieves.append(f"💰 [빈부격차] 40분 이전 맞라이너 5000골드 이상 격차 발생 (+{gold_earned - opp_gold:,}G)")
                    if role == "TOP" and is_win and (champ_level - opp_lvl) >= 4:
                        p_achieves.append(f"💪 [(탑) 탑 차이] 상대 탑보다 4레벨 이상 격차로 승리 (나: {champ_level}렙 vs 적: {opp_lvl}렙)")
                    if role == "JUNGLE" and is_win and game_duration >= 1800 and (kills+assists) >= (opp_kp * 2) and (kills+assists) >= 5:
                        p_achieves.append(f"🌲 [(정글) 정글 차이] 30분+ 게임에서 상대 정글보다 킬관여(K+A) 2배 이상 달성 후 승리 (나: {kills+assists} vs 적: {opp_kp})")
                    if role == "UTILITY" and is_win and game_duration >= 1800 and assists >= (opp_assists * 2) and assists >= 10:
                        p_achieves.append(f"🧿 [(서폿) 서폿 차이] 30분+ 게임에서 상대 서폿보다 어시스트 2배 이상 달성 후 승리 (나: {assists} vs 적: {opp_assists})")

                if role == "UTILITY" and game_duration >= 1800:
                    ally_adc = role_map[t_id].get('BOTTOM', {})
                    if ally_adc:
                        adc_stats = ally_adc.get('stats', ally_adc)
                        adc_dmg = adc_stats.get('totalDamageDealtToChampions', adc_stats.get('TOTAL_DAMAGE_DEALT_TO_CHAMPIONS', 0))
                        if dmg_dealt > adc_dmg and dmg_dealt > 0:
                            p_achieves.append(f"💥 [(서폿) 이것도 못 넣냐] 30분 이후 게임에서 아군 원딜보다 딜량 높음 (서폿: {dmg_dealt:,} vs 원딜: {adc_dmg:,})")
                
                if penta >= 2 and is_win and role == "BOTTOM":
                    p_achieves.append(f"👑 [(원딜) 펜타킬 2회] 한 게임 펜타킬 2회 이상 달성 후 승리 ({penta}회)")

            if p_achieves:
                clean_name = name.split('#')[0]
                ach_str = f"👑 [{clean_name}]\n"
                for a in p_achieves: ach_str += f"  - {a}\n"
                achievements.append(ach_str)

        if not is_aram:
            total_kills = teams[100]['kills'] + teams[200]['kills']
            if total_kills >= 100:
                for t_id in [100, 200]:
                    if teams[t_id]['win']:
                        achievements.append(f"🔥 [전투민족] 양팀 도합 100킬 이상 돌파! ({t_id}팀 승리 / 총 {total_kills}킬)")
                        break

        if player_scores:
            ps = sorted(player_scores, key=lambda x: x['score'], reverse=True)
            # 🔥 봇/빈 puuid는 시트 행과 매칭이 안 돼 역적이 누락되므로, 유효 puuid 보유자를 우선 선정
            def _valid_pu(p):
                u = str(p.get('puuid', '')).strip().lower()
                return bool(u) and u != 'none' and not u.startswith('bot_') and not u.startswith('temp')
            pool = [p for p in ps if _valid_pu(p)]
            if len(pool) < 2: pool = ps              # 유효자가 2명 미만이면 전체 사용(역적 임계 표본)
            mvp = next((p for p in ps if _valid_pu(p)), ps[0])   # (임시 기본값) — 아래서 이긴팀 기준으로 재선정

            # 🔥 [V81.25] MVP=이긴팀 최고 · ACE=진팀 최고 · 역적=진팀 최저(편향수정).
            win_t = next((tid for tid in (100, 200) if teams.get(tid, {}).get('win')), None)
            if win_t:
                winners = [p for p in pool if p.get('t_id') == win_t]
                losers  = [p for p in pool if p.get('t_id') != win_t]
            else:                                    # 승패 불명(드묾) → 전체를 한 풀로(구버전 호환)
                winners, losers = pool, []
            if winners: mvp = max(winners, key=lambda x: x['score'])         # 이긴팀 최고
            ace = max(losers, key=lambda x: x['score']) if losers else None   # 진팀 최고

            # 역적: 진팀(없으면 전체)에서 '같은 역할 맞상대(평균 상한 cap)보다 크게 뒤진 사람'.
            #   AI점수는 역할마다 절대 스케일이 달라(원딜·미드 천장↑, 서폿↓) 전체 최저/−1σ 방식이
            #   원딜·미드를 자주, 서폿을 거의 안 잡던 편향(시뮬 8만판: 미드30%·원딜28% vs 서폿11%)을 제거.
            #   상대 스머프가 격차를 부풀려 멀쩡한 사람을 역적 만드는 것 방지 위해 상대점수는 게임평균까지 cap.
            troll_pool = losers if losers else pool
            _sc = [p['score'] for p in pool]
            _avg = sum(_sc) / len(_sc)
            ROLE_DEFICIT_MARGIN = 38.0   # [V81.26] 역적은 '한 판을 크게 말아먹은' 경우만 — 시뮬상 게임당 ~15%(5판에 한번 미만)
            def _same_role_opp_best(p):
                opp_t = 200 if p.get('t_id') == 100 else 100
                r = p.get('role', 'NONE')
                if r in ('NONE', '', None): return None
                cands = [q['score'] for q in pool if q.get('t_id') == opp_t and q.get('role') == r]
                return max(cands) if cands else None
            troll = None
            if not is_aram:
                deficits = []
                for p in troll_pool:
                    if p is mvp or p is ace: continue
                    ob = _same_role_opp_best(p)
                    if ob is None: continue
                    ref = min(ob, _avg)
                    deficits.append((ref - p['score'], p))
                if deficits:
                    gap, cand = max(deficits, key=lambda x: x[0])
                    if gap >= ROLE_DEFICIT_MARGIN: troll = cand
            if troll is None:                        # ARAM·역할매칭 불가 → 진팀(전체) 최저가 평균−max(8,1σ) 아래면
                cand = min(troll_pool, key=lambda x: x['score']) if troll_pool else None
                if cand is not None and cand is not mvp and cand is not ace:
                    _std = (sum((x - _avg) ** 2 for x in _sc) / max(1, len(_sc) - 1)) ** 0.5
                    if cand['score'] < _avg - max(18.0, 1.5 * _std): troll = cand   # [V81.26] 폴백도 강화(엄청 못한 판만)

            mvp_puuid_out = mvp.get('puuid', '')
            mvp_cid_out = mvp.get('c_id', 0)
            mvp_team_id_out = mvp.get('t_id', 0)
            if ace:
                ace_puuid_out = ace.get('puuid', '')
                ace_cid_out = ace.get('c_id', 0)
                ace_team_id_out = ace.get('t_id', 0)
            if troll:
                troll_puuid_out = troll.get('puuid', '')
                troll_cid_out = troll.get('c_id', 0)
                troll_team_id_out = troll.get('t_id', 0)

            def _champ_kr(x):   # [V81.47] MVP/ACE/역적 사용 챔피언명(한글). 조회 실패 시 빈 문자열 → 괄호 생략
                try: cid = int(x.get('c_id', 0))          # 매치히스토리 폴백 경로에서 문자열로 올 수 있어 정수화(리뷰반영)
                except Exception: cid = 0
                info = champ_map.get(cid) if isinstance(champ_map, dict) else None
                if isinstance(info, dict) and info.get('kor'): return info['kor']
                if isinstance(info, str) and info: return info
                g = global_champ_map.get(cid)             # 공백 보존된 한글명 폴백(GLOBAL_NUMERIC은 공백제거라 '리 신'→'리신' 되는 문제 회피)
                if isinstance(g, dict) and g.get('kor'): return g['kor']
                return GLOBAL_NUMERIC_CHAMP_MAP.get(cid, '')

            # [2026-07-16 사장님 지시] 시인성 향상 — MVP/ACE/역적 아래 K/D/A·딜량 상세 한 줄(_stat_line) 제거.
            #   (KDA·딜량은 시트·웹 전적에 그대로 기록됨. 리포트는 '누가 MVP/ACE/역적인가'만 간결히.)
            report_lines = []
            report_lines.append(f"🏆 [MVP] {mvp['name'].split('#')[0]}" + (f" ({_champ_kr(mvp)})" if _champ_kr(mvp) else "") + f" (AI점수 {mvp['score']:.1f}점)")
            if ace:
                report_lines.append(f"🔥 [ACE] {ace['name'].split('#')[0]}" + (f" ({_champ_kr(ace)})" if _champ_kr(ace) else "") + f" (AI점수 {ace['score']:.1f}점)")
            if troll:
                report_lines.append(f"💀 [역적] {troll['name'].split('#')[0]}" + (f" ({_champ_kr(troll)})" if _champ_kr(troll) else "") + f" (AI점수 {troll['score']:.1f}점)")
            else:
                report_lines.append("✨ 이번 경기는 역적 없이 다들 제 몫을 했어요!")

            achievements.insert(0, "\n".join(report_lines) + "\n")

    except Exception:
        try:                                        # 무음 실패 → 로그 파일에 흔적 남겨 디버깅 가능하게(드물게만 실행)
            import traceback
            with open(resource_path("score_error.log"), "a", encoding="utf-8") as _lf:
                _lf.write(traceback.format_exc() + "\n")
        except Exception: pass
    
    return achievements, mvp_puuid_out, mvp_cid_out, mvp_team_id_out, ace_puuid_out, ace_cid_out, ace_team_id_out, troll_puuid_out, troll_cid_out, troll_team_id_out, kda_map, score_map, dmg_map, item_map, metrics_map, pos_final_map

def ad_banner_engine():
    global gui_data
    last_config = ""
    while True:
        try:
            headers = {"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0"}
            req = requests.get("https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/main/ad_config.txt", headers=headers, timeout=5)
            
            if req.status_code == 200:
                current_config = req.text.strip()
                if current_config and current_config != last_config:
                    new_ads = []
                    for line in current_config.split('\n'):
                        line = line.strip()
                        if not line: continue
                        img_url, click_url = None, None
                        
                        if "<a " in line.lower() and "<img " in line.lower():
                            href_match = re.search(r'href=[\'"]([^\'"]+)', line)
                            src_match = re.search(r'src=[\'"]([^\'"]+)', line)
                            if href_match and src_match:
                                click_url = href_match.group(1)
                                img_url = src_match.group(1).replace("&amp;", "&")
                        elif "|" in line:
                            parts = line.split('|')
                            if len(parts) >= 2:
                                img_url = parts[0].strip()
                                click_url = parts[1].strip()

                        if img_url and click_url and PILLOW_INSTALLED:
                            try:
                                img_res = requests.get(img_url, headers=headers, timeout=5)
                                if img_res.status_code == 200:
                                    pil_img = Image.open(BytesIO(img_res.content)).convert('RGBA')
                                    pil_img = pil_img.resize((345, 120), Image.Resampling.LANCZOS)
                                    new_ads.append({"img_obj": pil_img, "link": click_url})
                            except Exception: pass

                    with gui_lock:
                        if new_ads:
                            gui_data["ad_list"] = new_ads
                            gui_data["ad_index"] = 0
                            gui_data["last_ad_time"] = 0
                        last_config = current_config
        except Exception: pass
        time.sleep(60)

# =========================================================================
# 🚫 V80.0 GUI 렌더링 엔진 (Thread Safe UI Updates)
# =========================================================================
class TierAdminWindow(tk.Toplevel):
    """관리자용 내부티어 편집기 — CLAN_TIERS 시트에 부여/변경/삭제 (웹·앱 자동 반영)."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("내부티어 관리 (관리자)")
        self.geometry("560x660")
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self._all = []; self._view = []
        self._build()
        self._refresh()

    def _build(self):
        top = tk.Frame(self, bg=theme.BG_BAR); top.pack(fill="x")
        tk.Label(top, text="🎖 내부티어 관리", bg=theme.BG_BAR, fg=theme.GOLD,
                 font=UF(15, "bold")).pack(side="left", padx=18, pady=12)

        form = tk.Frame(self, bg=theme.BG); form.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(form, text="닉네임", bg=theme.BG, fg=theme.TEXT, font=UF(11)).grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        tk.Entry(form, textvariable=self.name_var, bg=theme.BG_INPUT, fg=theme.TEXT, insertbackground=theme.TEXT,
                 bd=0, font=UF(12)).grid(row=0, column=1, padx=8, pady=4, sticky="we")
        tk.Label(form, text="티어", bg=theme.BG, fg=theme.TEXT, font=UF(11)).grid(row=1, column=0, sticky="w", pady=4)
        self.tier_var = tk.StringVar(value="1上")   # 신규 부여 기본값(0티어 오지정 방지). 목록 클릭 시 자동 대체
        ttk.Combobox(form, textvariable=self.tier_var, values=TIER_ORDER_LIST, state="readonly",
                     width=10, font=UF(12)).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        form.columnconfigure(1, weight=1)

        btns = tk.Frame(self, bg=theme.BG); btns.pack(fill="x", padx=18, pady=4)
        tk.Button(btns, text="💾 부여 / 변경 저장", bg=theme.SUCCESS, fg=theme.TEXT, bd=0, padx=12, pady=6,
                  font=UF(11, "bold"), cursor="hand2", command=self._save).pack(side="left")
        tk.Button(btns, text="🗑 선택 삭제", bg=theme.LOSE, fg=theme.TEXT, bd=0, padx=12, pady=6,
                  font=UF(11, "bold"), cursor="hand2", command=self._delete).pack(side="left", padx=8)
        tk.Label(self, text="이름 입력 후 티어 선택 → 저장 (있으면 변경·없으면 추가). 아래 목록 클릭 시 폼 자동입력. 웹·앱 자동 반영.",
                 bg=theme.BG, fg=theme.TEXT_SUB, font=UF(9), wraplength=520, justify="left").pack(fill="x", padx=18, pady=(2, 8))

        lf = tk.Frame(self, bg=theme.BG); lf.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        tk.Label(lf, text="🔎 검색", bg=theme.BG, fg=theme.TEXT_SUB, font=UF(9)).pack(anchor="w")
        self.search_var = tk.StringVar()
        tk.Entry(lf, textvariable=self.search_var, bg=theme.BG_INPUT, fg=theme.TEXT, insertbackground=theme.TEXT,
                 bd=0, font=UF(11)).pack(fill="x", pady=(0, 6))
        self.search_var.trace_add("write", lambda *a: self._render_list())
        self.listbox = tk.Listbox(lf, bg=theme.BG_INPUT, fg=theme.TEXT, bd=0, highlightthickness=0,
                                  font=UF(11), selectbackground=theme.BG_RAISED, activestyle="none")
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

    def _refresh(self):
        # 창이 즉시 뜨도록 시트 읽기는 백그라운드에서 (429/느린 연결 시 메인스레드 프리징으로 창이 안 뜨던 문제 방지)
        try: self.title("내부티어 관리 (관리자) — 불러오는 중…")
        except Exception: pass
        self._pending = None; self._poll_n = 0
        def _work():
            try:
                data = sorted(list_clan_tiers(),
                              key=lambda x: (TIER_ORDER_LIST.index(x[1]) if x[1] in TIER_ORDER_LIST else 99, x[0]))
            except Exception:
                data = []
            self._pending = data   # 참조 대입은 GIL 하에서 원자적 — 메인스레드가 폴링
        threading.Thread(target=_work, daemon=True).start()
        self._poll_refresh()

    def _poll_refresh(self):
        try:
            if not self.winfo_exists(): return
        except Exception:
            return
        if self._pending is not None:
            self._all = self._pending; self._pending = None
            self._render_list(); return
        self._poll_n += 1
        if self._poll_n > 80:   # 약 12초 후 타임아웃 → 스피너 해제
            self._all = []; self._render_list()
            try: self.title("내부티어 관리 (관리자) — 시트 연결 확인 필요")
            except Exception: pass
            return
        try: self.after(150, self._poll_refresh)
        except Exception: pass

    def _render_list(self):
        q = tnorm(self.search_var.get())
        self.listbox.delete(0, tk.END); self._view = []
        for nm, t in self._all:
            if q and q not in tnorm(nm): continue
            self.listbox.insert(tk.END, "  " + t + "    " + nm); self._view.append((nm, t))
        self.title("내부티어 관리 (관리자) — 총 " + str(len(self._all)) + "명")

    def _on_select(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        nm, t = self._view[sel[0]]
        self.name_var.set(nm); self.tier_var.set(t)

    def _save(self):
        nm = self.name_var.get().strip(); t = self.tier_var.get().strip()
        if not nm: messagebox.showwarning("티어 관리", "닉네임을 입력하세요."); return
        if t not in TIER_ORDER_LIST: messagebox.showwarning("티어 관리", "티어를 선택하세요."); return
        if save_clan_tier(nm, t):
            messagebox.showinfo("티어 관리", "저장됨: " + nm + " → " + t + "\n(웹·앱 자동 반영)")
            self.name_var.set(""); self._refresh()
        else:
            messagebox.showerror("티어 관리", "저장 실패 (시트 연결을 확인하세요).")

    def _delete(self):
        nm = self.name_var.get().strip()
        if not nm: messagebox.showwarning("티어 관리", "삭제할 닉네임을 목록에서 선택하세요."); return
        if messagebox.askyesno("티어 관리", "'" + nm + "' 티어를 삭제할까요?"):
            if delete_clan_tier(nm):
                messagebox.showinfo("티어 관리", "삭제됨: " + nm); self.name_var.set(""); self._refresh()
            else:
                messagebox.showerror("티어 관리", "삭제 실패 (목록에 없거나 시트 오류).")

def create_graphic_ui():
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass
    
    root = tk.Tk()
    root.title("스쿼드해체분석기 [v" + str(CURRENT_VERSION) + "]")   # 마케팅 부제만 제거·버전은 유지(사장님 요청 — 실행 버전 확인용)
    
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    
    # [v82.18] 1순위: 지난 종료 시 저장된 창 크기(win_last) — 사용자가 조절한 크기를 그대로 복원
    # [v82.17] 2순위: 프리셋 / 3순위: auto(화면 맞춤)
    _preset = APP_CONFIG.get("win_preset", "auto")
    _last = str(APP_CONFIG.get("win_last") or "")
    _mres = re.fullmatch(r"(\d{3,4})x(\d{3,4})", _last)
    if _last == "max":
        root.geometry(f"{min(1560, int(screen_w*0.95))}x{min(1150, int(screen_h*0.95))}")
        root.state('zoomed')
    elif _mres:
        _lw, _lh = int(_mres.group(1)), int(_mres.group(2))
        root.geometry(f"{min(_lw, int(screen_w*0.95))}x{min(_lh, int(screen_h*0.95))}")
    elif _preset in WIN_PRESETS:
        _pw, _ph = WIN_PRESETS[_preset]
        app_w = min(_pw, int(screen_w * 0.95)); app_h = min(_ph, int(screen_h * 0.95))
        root.geometry(f"{app_w}x{app_h}")
    else:
        app_w = min(1560, int(screen_w * 0.95))   # [v82.16] 가로 +10%
        app_h = min(1150, int(screen_h * 0.95))   # [v82.10] 세로 +10%
        root.geometry(f"{app_w}x{app_h}")
        if _preset == "max" or screen_h <= 1080: root.state('zoomed')

    BG_MAIN = theme.BG
    root.configure(bg=BG_MAIN)

    try: root.iconbitmap(resource_path("icon.ico"))
    except Exception: pass

    is_stealth = "--stealth" in sys.argv
    with gui_lock: gui_data["is_hidden"] = is_stealth
    if is_stealth: root.withdraw()

    # 🪟 [v82.30] 창 표시상태 추적 — 기존엔 --stealth/트레이 숨김만 '숨김'으로 쳐서,
    #   작업표시줄로 최소화해두면 롤을 켜도 자동 팝업이 동작하지 않았다.
    def _on_root_unmap(e):
        if e.widget is root:
            with gui_lock: gui_data["is_hidden"] = True
    def _on_root_map(e):
        if e.widget is root:
            with gui_lock: gui_data["is_hidden"] = False
    root.bind("<Unmap>", _on_root_unmap)
    root.bind("<Map>", _on_root_map)

    def stealth_monitor():
        was_running = False
        while True:
            try:
                output = subprocess.check_output('tasklist /FI "IMAGENAME eq LeagueClient.exe"', shell=True).decode('cp949', errors='ignore')
                is_running = "LeagueClient.exe" in output
                
                if is_running and not was_running:
                    with gui_lock:
                        auto_show = APP_CONFIG.get("lol_auto_show", True)
                        is_hid = gui_data.get("is_hidden", False)
                    if auto_show and is_hid:
                        root.after(0, root.deiconify)
                        root.after(0, lambda: root.state('normal') if root.state()=='iconic' else None)
                        root.after(0, root.lift)
                        root.after(0, lambda: root.attributes('-topmost', True))
                        root.after(100, lambda: root.attributes('-topmost', False))
                        with gui_lock: gui_data["is_hidden"] = False
                was_running = is_running
            except Exception: pass
            time.sleep(3)
            
    threading.Thread(target=stealth_monitor, daemon=True).start()

    position_images = {}
    tier_images = {}
    
    def robust_load_image(file_name, target_size):
        if not PILLOW_INSTALLED: return None
        try:
            pil_img = Image.open(resource_path(file_name))
            resized = pil_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(resized)
        except Exception: return None

    # 🎨 [v81.93] T1 '내 꾸미기' 엠블럼 — 비율 유지 로드(로고 왜곡 방지). 번들 실패 시 None(조용히 미표시).
    # [v82.8] 엠블럼 라벨 로더 제거 — 프레임 이미지에 로고 포함(별도 엠블럼 미사용)

    # [v82.18] 엠블럼 로더 — variant별 로고를 팀 배경색 위에 합성(높이 26px, 원본 비율 유지). 캐시.
    _T1_REG = set()   # 엠블럼이 표시된 슬롯(bf) 레지스트리 — 매 사이클 스윕으로 잔상 원천 차단
    _T1_EMB_CACHE = {}
    def _t1_emblem_photo(ck, soft_bg, target_h=26):
        if not PILLOW_INSTALLED: return None
        key = (ck, soft_bg)
        if key in _T1_EMB_CACHE: return _T1_EMB_CACHE[key]
        try:
            im = Image.open(resource_path(T1_EMBLEM_FILES[ck])).convert("RGBA")
            w0, h0 = im.size
            nw = max(1, int(w0 * target_h / max(1, h0)))
            im = im.resize((nw, target_h), Image.Resampling.LANCZOS)
            base = Image.new("RGBA", im.size, soft_bg)   # 팀 배경색 합성(라벨 투명 불가 대응)
            ph = ImageTk.PhotoImage(Image.alpha_composite(base, im))
            _T1_EMB_CACHE[key] = ph
            return ph
        except Exception: return None

    for pos_key in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]:
        position_images[pos_key] = robust_load_image(str(pos_key) + ".png", 28)
        
    for tier in TIERS:
        tier_images[tier] = robust_load_image(str(tier) + ".png", 32)

    FONT_TITLE = UF(20, "bold")
    FONT_CREDIT = UF(11)
    FONT_STATUS = UF(12, "bold")
    FONT_BANS = UF(12)
    FONT_LF_TITLE = UF(12, "bold")
    FONT_SLOT_NAME = UF(13, "bold")
    FONT_SLOT_STAT = UF(11)
    FONT_SYNERGY = UF(11)

    header = tk.Frame(root, bg=theme.BG_BAR, height=158)
    header.pack(fill="x", side="top", pady=(5, 5))
    header.pack_propagate(False) 
    
    # [v82.13 시안 반영] 광고 = 헤더 우측 상단 코너(꽉 차게), 개발·기획/상태/10밴 = 헤더(광고 왼쪽)
    ad_frame = tk.Frame(header, bg=theme.BG_BAR, width=345, height=150, cursor="hand2")
    ad_frame.pack_propagate(False)
    ad_frame.pack(side="right", padx=(6, 8), pady=4)
    ad_lbl = tk.Label(ad_frame, text="✨ 스폰서 배너 로딩 중... ✨", bg=theme.BG_BAR, fg=theme.WARN, font=UF(10, "bold"))
    ad_lbl.pack(expand=True, fill="both")
    def on_ad_click(event):
        link = ""
        with gui_lock: link = gui_data.get("ad_link", "")
        if link: webbrowser.open(link)
    ad_lbl.bind("<Button-1>", on_ad_click)

    mid_header = tk.Frame(header, bg=theme.BG_BAR)
    mid_header.pack(side="right", padx=20, pady=15)

    tk.Label(mid_header, text="개발 및 기획 : 맛동산장인 유미#Teana", bg=theme.BG_BAR, fg=theme.TEXT_SUB, font=FONT_CREDIT).pack(anchor="e", pady=3)

    status_var = tk.StringVar(value="📡 LCU 시스템 탐색 중...")
    bans_var = tk.StringVar(value="🚫 10밴 현황: 대기 중")
    tk.Label(mid_header, textvariable=status_var, bg=theme.BG_BAR, fg=theme.SUCCESS, font=FONT_STATUS).pack(anchor="e", pady=3)
    # 🚫 [v81.77 사장님 지시] 10밴 현황 = 텍스트 나열 → 챔피언 초상화 아이콘. 라벨(제목)+아이콘 줄로 분리.
    bans_row = tk.Frame(mid_header, bg=theme.BG_BAR)
    bans_row.pack(anchor="e", pady=3)
    tk.Label(bans_row, textvariable=bans_var, bg=theme.BG_BAR, fg=theme.TEXT_SUB, font=FONT_BANS).pack(side="left", padx=(0, 6))
    bans_icon_frame = tk.Frame(bans_row, bg=theme.BG_BAR)
    bans_icon_frame.pack(side="left")

    left_header = tk.Frame(header, bg=theme.BG_BAR)
    left_header.pack(side="left", fill="both", expand=True, padx=15, pady=5)

    try:
        yumi_img = tk.PhotoImage(file=resource_path("yumi_avatar.png")).subsample(7, 7)
        lbl_yumi = tk.Label(left_header, image=yumi_img, bg=theme.BG_BAR)
        lbl_yumi.image = yumi_img
        lbl_yumi.pack(side="left", padx=5)
    except Exception: pass

    text_frame = tk.Frame(left_header, bg=theme.BG_BAR)
    text_frame.pack(side="left", padx=5)
    
    _title_row = tk.Frame(text_frame, bg=theme.BG_BAR); _title_row.pack(anchor="w", pady=(0, 5))
    _btn_menu = tk.Button(_title_row, text="☰", font=UF(15, "bold"),
                          bg=theme.BG_RAISED, fg=theme.GOLD, bd=0, padx=10, pady=1,
                          activebackground=theme.GOLD, activeforeground="#1b1b1b", cursor="hand2")
    _btn_menu.pack(side="left", padx=(0, 10))
    tk.Label(_title_row, text="스쿼드해체분석기", bg=theme.BG_BAR, fg=theme.GOLD, font=FONT_TITLE).pack(side="left")
    
    # ☰ [2026-08-12 사장님 지시] 상단 버튼 무더기 → 왼쪽 서랍. 모바일 게임 메뉴처럼 반투명 타일 격자.
    #   ⚠️ Tk 는 위젯 단위 투명도가 없다. 그래서 서랍을 '별도 Toplevel'로 띄우고 -alpha 를 준다 —
    #      창 전체에 알파가 먹으므로 뒤에 있는 분석기 화면이 실제로 비쳐 보인다(가짜 합성이 아니다).
    #      대신 본체가 움직이거나 크기가 바뀌면 서랍이 따라가야 한다 → <Configure> 로 좌표를 맞춘다.
    _DRW = {"open": False, "w": 268, "x": 0, "busy": False, "win": None}
    C_PANEL, C_TILE, C_TILE_H = "#0d1017", "#1a1f2b", "#28303f"

    drawer = tk.Toplevel(root)
    drawer.withdraw()
    drawer.overrideredirect(True)
    drawer.transient(root)
    drawer.configure(bg=C_PANEL)
    # [2026-08-12 사장님 지시] 0.93 → 0.75. 20%p 더 비치게 해서 서랍을 열어도 뒤 로스터가 읽힌다.
    try: drawer.attributes("-alpha", DRAWER_ALPHA)
    except Exception: pass

    _drw_head = tk.Frame(drawer, bg=C_PANEL); _drw_head.pack(fill="x", padx=18, pady=(18, 4))
    tk.Label(_drw_head, text="MENU", bg=C_PANEL, fg=theme.GOLD,
             font=UF(12, "bold")).pack(side="left")
    _drw_x = tk.Label(_drw_head, text="✕", bg=C_PANEL, fg="#6b7789",
                      font=UF(13), cursor="hand2")
    _drw_x.pack(side="right")
    tk.Frame(drawer, bg="#222a37", height=1).pack(fill="x", padx=18, pady=(6, 10))

    _drw_body = tk.Frame(drawer, bg=C_PANEL); _drw_body.pack(fill="both", expand=True, padx=12)
    for _c in range(3): _drw_body.columnconfigure(_c, weight=1, uniform="tiles")
    _drw_cell = [0]

    class _Tile:
        """아이콘 타일 — 기존 tk.Button 자리를 대신한다. config(text=, bg=) 를 받아 주므로
           _posview_btn_sync 같은 기존 코드가 그대로 동작한다."""
        def __init__(self, icon, label, cmd, accent):
            r, c = divmod(_drw_cell[0], 3); _drw_cell[0] += 1
            self.f = tk.Frame(_drw_body, bg=C_TILE, cursor="hand2")
            self.f.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            self.bar = tk.Frame(self.f, bg=accent, height=2); self.bar.pack(fill="x")
            self.ic = tk.Label(self.f, text=icon, bg=C_TILE, fg=accent, font=UF(17, family="Segoe UI Emoji"))
            self.ic.pack(pady=(9, 1))
            self.tx = tk.Label(self.f, text=label, bg=C_TILE, fg="#cdd6e3",
                               font=UF(9), wraplength=74, justify="center")
            self.tx.pack(pady=(0, 9))
            self.cmd = cmd
            for wgt in (self.f, self.ic, self.tx):
                wgt.bind("<Button-1>", self._hit)
                wgt.bind("<Enter>", lambda e: self._bg(C_TILE_H))
                wgt.bind("<Leave>", lambda e: self._bg(C_TILE))
        def _bg(self, col):
            for wgt in (self.f, self.ic, self.tx):
                try: wgt.configure(bg=col)
                except Exception: pass
        def _hit(self, _e=None):
            try: self.cmd()
            except Exception as ex: print(f"[drawer] {ex}", flush=True)
            root.after(140, _drw_close)
        def config(self, text=None, bg=None, **_kw):
            if text:                                   # '모스트: 현재포지션' → 두 줄로 접어 넣는다
                self.tx.config(text=str(text).split(":")[-1].strip() or text)
            if bg:
                self.bar.config(bg=bg); self.ic.config(fg=bg)
        configure = config
        def pack(self, *_a, **_kw): pass                # 옛 코드가 pack 을 불러도 무시(격자로 이미 배치됨)

    def _drw_add(icon, label, cmd, accent):
        return _Tile(icon, label, cmd, accent)

    _drw_add("📖", "사용 안내", lambda: GuideWindow(root), "#9db8ff")

    # 🎮 [2026-08-13] 음성방 초대 — 디스코드 /팀초대와 같은 일을 분석기에서 바로. 로비 호스트가 누른다.
    def _do_voice_invite():
        def _work():
            ok, msg = _invite_voice_members()
            root.after(0, lambda: (messagebox.showinfo if ok else messagebox.showwarning)("음성방 초대", msg))
        threading.Thread(target=_work, daemon=True).start()

    _drw_add("🎮", "음성방 초대", _do_voice_invite, "#7ee1a8")

    # 👥 접속자 버튼 제거(2026-07-05 사장님 지시). 접속기록 자체는 백그라운드로 계속 시트에 기록됨.
    # ❄ 증내의 전당 버튼 삭제(2026-07-16) → 명예의 전당 창 내부 '칼바람' 탭으로 통합
    def open_hof_window(mode_type):
        try: ClanRankingWindow(root, mode=mode_type)
        except Exception as e: messagebox.showerror("전당 오류", f"데이터를 갱신 중입니다. 잠시 후 다시 시도해주세요.\n(에러: {str(e)})")

    _drw_add("🏆", "명예의 전당", lambda: open_hof_window("CLASSIC"), theme.LOSE)

    def open_tier_window():
        try: TierAssessmentWindow(root)
        except Exception as e: messagebox.showerror("평가 오류", f"데이터를 갱신 중입니다. 잠시 후 다시 시도해주세요.\n(에러: {str(e)})")
    _drw_add("🎖", "내부티어", open_tier_window, theme.PURPLE)

    # 📜 패치노트 버튼 폐기(2026-07-01) — 패치 안내는 디스코드 웹훅으로 대체

    _drw_add("🧪", "모의밴픽", lambda: webbrowser.open("https://www.fullbanpick.com/"), theme.WARN)

    _drw_add("🌐", "SQUAD.GG", lambda: webbrowser.open("https://kjp1583-art.github.io/squad-analyzer/"), theme.ACCENT)

    # 🏟 [v82.41 사장님 지시] 클랜원 제작 토너먼트(경매) 사이트 바로가기
    _drw_add("🔨", "AUC.GG", lambda: webbrowser.open("https://auc-gg.up.railway.app/"), theme.GOLD)

    # 🎯 [2026-07-08] 대기실 모스트 표시 토글: 전체 라인 ↔ 현재 선택 포지션(모스트3 + 그 포지션 고승률픽)
    def _toggle_pos_view():
        with gui_lock:
            gui_data["pos_view_mode"] = not gui_data.get("pos_view_mode", _posview_default())
            _on = gui_data["pos_view_mode"]
        _posview_btn_sync(_on)
    # [v82.37] 초기 문구·색은 설정값(pos_view_default)을 따른다 — 하드코딩하면 화면과 실동작이 어긋남
    _pv0 = _posview_default()
    btn_posview = _drw_add("🎯", ("현재포지션" if _pv0 else "전체라인"), _toggle_pos_view,
                           (theme.SUCCESS if _pv0 else "#6b7789"))
    _POSVIEW_BTN[0] = btn_posview   # 설정 창에서 즉시 갱신할 수 있도록 참조 보관

    _drw_add("⚙", "설정", lambda: ClanSettingsWindow(root), "#cdd6e3")

    # 🗒️ [2026-07-29] 로그 보기 — 창 모드라 콘솔이 없어 문제가 생겨도 확인할 방법이 없었다.

    def _open_log():
        try:
            if not os.path.exists(LOG_PATH):
                messagebox.showinfo("로그", "아직 기록이 없습니다."); return
            os.startfile(LOG_PATH)
        except Exception as e:
            messagebox.showerror("로그", f"열지 못했습니다: {e}\n\n경로: {LOG_PATH}")
    _drw_add("🗒", "로그", _open_log, "#8d9aae")

    # 🏟 토너먼트 버튼 삭제(2026-07-16 사장님 지시)

    # 🅣 [v82.8] '내 꾸미기' 로컬 버튼 폐지 — 구매 검증이 불가능해 아무나 쓰던 문제.
    #    T1 프레임은 이제 봇 /상점에서 구매·장착(서버 검증) → /cosmetics로 내려와 모든 PC에 표시.

    # 👑 [2026-08-06 사장님 지시] 팀장뽑기 — 방 인원 중 전력이 가장 비슷한 2인 자동 선정(직전 판 팀장 회피)
    def _do_pick_captains(extra_exclude=None):
        with gui_lock:
            entries = list(gui_data.get("blue") or []) + list(gui_data.get("red") or [])
        def worker():
            try: cidx = _clan_index()
            except Exception: cidx = None
            recent = set(_captain_recent_load()) | set(extra_exclude or [])
            a, b, why = _captain_pick(entries, recent, cidx)
            def show():
                if not a:
                    messagebox.showinfo("팀장뽑기", why); return
                _captain_recent_save([a['tn'], b['tn']])
                w = tk.Toplevel(root); w.title("팀장뽑기")
                w.attributes("-topmost", True); w.configure(bg="#12141a")
                tk.Label(w, text="👑 이번 판 팀장", bg="#12141a", fg="#f5d47a",
                         font=UF(13, "bold")).pack(padx=18, pady=(14, 4))
                def _one(c):
                    t = c['nm'].split('#')[0].strip() + (f"  [{c['tier']}티어]" if c['tier'] else "") \
                        + (f"  주:{c['pos']}" if c['pos'] else "")
                    tk.Label(w, text=t, bg="#12141a", fg="#e8eaf0",
                             font=UF(12, "bold")).pack(padx=18, pady=2)
                _one(a)
                tk.Label(w, text="VS", bg="#12141a", fg="#8a93a6", font=UF(10)).pack()
                _one(b)
                tk.Label(w, text=why, bg="#12141a", fg="#8a93a6", font=UF(9)).pack(padx=18, pady=(6, 2))
                bs = tk.Frame(w, bg="#12141a"); bs.pack(pady=(6, 12))
                def _announce():
                    def w2():
                        try:
                            port, pw2 = get_lcu_credentials()
                            if not port: return
                            hd = {"Authorization": "Basic " + base64.b64encode(("riot:" + str(pw2)).encode()).decode(),
                                  "Accept": "application/json"}
                            send_lcu_chat_announcement(
                                f"👑 팀장 자동선정: {a['nm'].split('#')[0]} vs {b['nm'].split('#')[0]} ({why})",
                                hd, "https://127.0.0.1:" + str(port))
                        except Exception: pass
                    threading.Thread(target=w2, daemon=True).start()
                tk.Button(bs, text="📢 로비에 알리기", command=_announce, bg="#1e2436", fg="#9db8ff",
                          relief="flat", padx=10).pack(side="left", padx=4)
                tk.Button(bs, text="🔁 다시 뽑기", bg="#232838", fg="#cfd6e4", relief="flat", padx=10,
                          command=lambda: (w.destroy(), _do_pick_captains(set(extra_exclude or []) | {a['tn'], b['tn']}))
                          ).pack(side="left", padx=4)
                tk.Button(bs, text="닫기", command=w.destroy, bg="#232838", fg="#cfd6e4",
                          relief="flat", padx=10).pack(side="left", padx=4)
            root.after(0, show)
        threading.Thread(target=worker, daemon=True).start()
    _drw_add("👑", "팀뽑선정", _do_pick_captains, theme.GOLD)

    # 🎖 티어관리 — token.txt 보유한 호스트 PC에서만 노출 (내전 큐 버튼은 삭제됨 2026-07-02, 백엔드/데이터는 유지)
    if load_bot_token():
        def open_tieradmin_window():
            try: TierAdminWindow(root)
            except Exception as e:
                messagebox.showerror("티어관리 오류", f"티어 관리 창을 여는 중 오류가 발생했습니다.\n(에러: {str(e)})")
        _drw_add("🛠", "티어관리", open_tieradmin_window, theme.PURPLE)

    # 💝 [2026-08-12 사장님 지시] 후원 — 계좌·예금주를 띄우고 한 번에 복사할 수 있게
    def _open_donate():
        _bank = APP_CONFIG.get("donate_bank") or DONATE_BANK
        _acct = APP_CONFIG.get("donate_acct") or DONATE_ACCT
        _name = APP_CONFIG.get("donate_name") or DONATE_NAME
        w = tk.Toplevel(root); w.title("후원")
        w.configure(bg="#0e1016"); w.attributes("-topmost", True); w.resizable(False, False)
        try:   # 본체 가운데에 띄운다(모니터 구석에 뜨면 못 찾는다)
            w.update_idletasks()
            w.geometry("+%d+%d" % (root.winfo_rootx() + root.winfo_width() // 2 - 190,
                                   root.winfo_rooty() + 160))
        except Exception: pass
        tk.Frame(w, bg="#f5d47a", height=3).pack(fill="x")
        tk.Label(w, text="💝  후원하기", bg="#0e1016", fg="#f5d47a",
                 font=UF(15, "bold")).pack(anchor="w", padx=22, pady=(16, 2))
        tk.Label(w, text="분석기·squad.gg·디스코드 봇은 클랜원 한 명이 사비로 굴리고 있어요.\n"
                         "AI 비용·서버비에 그대로 들어갑니다. 부담 갖지 마세요 🙏",
                 bg="#0e1016", fg="#8d9aae", font=UF(9), justify="left").pack(anchor="w", padx=22)
        box = tk.Frame(w, bg="#171b23"); box.pack(fill="x", padx=22, pady=(14, 6))
        tk.Label(box, text=_bank, bg="#171b23", fg="#8d9aae",
                 font=UF(10)).pack(anchor="w", padx=14, pady=(11, 0))
        tk.Label(box, text=_acct, bg="#171b23", fg="#eef2f8",
                 font=UF(19, "bold")).pack(anchor="w", padx=14)
        tk.Label(box, text=f"예금주  {_name}", bg="#171b23", fg="#cdd6e3",
                 font=UF(10)).pack(anchor="w", padx=14, pady=(1, 12))
        _msg = tk.Label(w, text="", bg="#0e1016", fg="#5ad48a", font=UF(9))
        _msg.pack(anchor="w", padx=22)
        def _copy(full=False):
            try:
                w.clipboard_clear()
                w.clipboard_append(f"{_bank} {_acct} {_name}" if full else _acct.replace("-", ""))
                w.update()          # 창이 닫혀도 클립보드가 남게(Tk 는 소유 창이 사라지면 내용도 사라진다)
                _msg.config(text=("✅ 은행·계좌·예금주를 복사했어요" if full else "✅ 계좌번호를 복사했어요"))
            except Exception as e:
                _msg.config(text=f"복사 실패: {e}", fg="#ff8a8a")
        bar = tk.Frame(w, bg="#0e1016"); bar.pack(fill="x", padx=22, pady=(8, 18))
        tk.Button(bar, text="계좌번호 복사", command=lambda: _copy(False), bg="#f5d47a", fg="#1b1b1b",
                  relief="flat", font=UF(10, "bold"), padx=14, pady=5,
                  cursor="hand2").pack(side="left")
        tk.Button(bar, text="전체 복사", command=lambda: _copy(True), bg="#1e2436", fg="#9db8ff",
                  relief="flat", font=UF(10), padx=12, pady=5,
                  cursor="hand2").pack(side="left", padx=6)
        tk.Button(bar, text="닫기", command=w.destroy, bg="#232838", fg="#cfd6e4",
                  relief="flat", font=UF(10), padx=12, pady=5,
                  cursor="hand2").pack(side="right")
    _drw_add("💝", "후원하기", _open_donate, "#ff8fb1")

    tk.Frame(drawer, bg="#222a37", height=1).pack(fill="x", padx=18, pady=(12, 0))
    tk.Label(drawer, text=f"스쿼드해체분석기  v{CURRENT_VERSION}", bg=C_PANEL, fg="#5a6474",
             font=UF(8)).pack(anchor="w", padx=20, pady=(8, 14))

    def _drw_geo():
        """본체 창에 맞춰 서랍 위치·높이를 잡는다(본체가 움직이거나 크기가 바뀌면 따라간다)."""
        try:
            rx, ry = root.winfo_rootx(), root.winfo_rooty()
            rh = root.winfo_height()
            drawer.geometry("%dx%d+%d+%d" % (_DRW["w"], max(320, rh), rx + _DRW["x"], ry))
        except Exception: pass

    def _drw_animate(target):
        if _DRW["busy"]: return
        _DRW["busy"] = True
        def _step():
            x = _DRW["x"]
            d = 30 if target > x else -30
            x = min(target, x + d) if d > 0 else max(target, x + d)
            _DRW["x"] = x
            _drw_geo()
            if x != target: root.after(8, _step)
            else:
                _DRW["busy"] = False
                if target < 0: drawer.withdraw()
        if target >= 0:
            _drw_geo(); drawer.deiconify(); drawer.lift(); drawer.attributes("-topmost", True)
            root.after(60, lambda: drawer.attributes("-topmost", False))
        _step()

    def _drw_toggle(_e=None):
        if _DRW["busy"]: return          # 미끄러지는 중에 또 누르면 열림/닫힘 상태가 어긋난다
        _DRW["open"] = not _DRW["open"]
        if _DRW["open"] and _DRW["x"] >= 0: _DRW["x"] = -_DRW["w"]      # 닫힌 상태 좌표 보정
        _drw_animate(0 if _DRW["open"] else -_DRW["w"])
        _btn_menu.config(text=("✕" if _DRW["open"] else "☰"))

    def _drw_close(_e=None):
        if _DRW["open"]: _drw_toggle()

    _DRW["x"] = -_DRW["w"]
    _drw_x.bind("<Button-1>", _drw_close)
    _btn_menu.config(command=_drw_toggle)
    root.bind("<Escape>", _drw_close)
    # 🖱 [2026-08-12 사장님 지시] ✕ 말고 화면 아무 데나 눌러도 닫히게.
    #   root.bind 는 root 자신의 빈 자리를 눌렀을 때만 오므로 자식 위젯 클릭이 안 잡힌다 → bind_all.
    #   단 서랍 안(별도 Toplevel)을 누른 건 제외해야 메뉴를 고르기도 전에 닫히지 않는다.
    #   ☰ 버튼도 제외 — 여기서 닫고 토글이 또 열어 버리면 영영 안 열린다.
    def _drw_click_away(e):
        if not _DRW["open"]: return
        try:
            if e.widget.winfo_toplevel() is drawer: return
            if e.widget is _btn_menu: return
        except Exception: pass
        _drw_close()
    root.bind_all("<Button-1>", _drw_click_away, add="+")
    # 🔠 [2026-08-13 사장님 제보] 창 크기에 맞춰 글자 크기도 같이 바꾼다.
    #   해상도만 줄고 글자는 그대로여서 작게 쓰면 읽을 수가 없었다.
    #   ⚠️ <Configure> 는 창을 끄는 동안 초당 수십 번 온다 — 그때마다 폰트를 다시 계산하면
    #      화면이 덜덜 떨린다. 마지막 이벤트로부터 140ms 뒤에 한 번만 적용한다(디바운스).
    _ui_job = [None]
    def _ui_do():
        _ui_job[0] = None
        try:
            w, h = root.winfo_width(), root.winfo_height()
            if w < 200 or h < 200: return          # 최소화·초기화 중엔 무시
            ui_scale_apply(min(w / UI_BASE_W, h / UI_BASE_H))
        except Exception: pass
    def _ui_rescale(_e=None):
        if _ui_job[0]:
            try: root.after_cancel(_ui_job[0])
            except Exception: pass
        _ui_job[0] = root.after(140, _ui_do)
    root.bind("<Configure>", lambda e: (_ui_rescale() if e.widget is root else None), add="+")
    root.after(500, _ui_do)                        # 시작 크기(프리셋·저장된 크기)에도 즉시 반영

    # 본체를 움직이거나 크기를 바꾸면 따라오고, 최소화하면 같이 숨는다(따로 떠 있는 창이라 필수)
    root.bind("<Configure>", lambda e: (_drw_geo() if _DRW["open"] else None), add="+")
    root.bind("<Unmap>", lambda e: (drawer.withdraw() if e.widget is root else None), add="+")
    root.bind("<Map>", lambda e: (_drw_geo() or drawer.deiconify()) if (e.widget is root and _DRW["open"]) else None, add="+")

    # [v82.12] 하단 가로 3칸 → 레드팀 우측 세로 패널로 이동(사장님 지시). 광고·개발텍스트도 이 열로.
    body = tk.Frame(root, bg=BG_MAIN)
    body.pack(fill="both", expand=True, padx=20, pady=5)
    # [v82.15] 시안 비율 = 팀:팀:우측 2:2:1 비례 분할(고정폭 X — 창 폭 무관 동일 비율, 블루팀 우측끝이 설정버튼보다 오른쪽)
    body.columnconfigure(0, weight=2, uniform="cols3")
    body.columnconfigure(1, weight=2, uniform="cols3")
    body.columnconfigure(2, weight=1, uniform="cols3")
    body.rowconfigure(0, weight=1)

    blue_card = tk.Frame(body, bg=theme.BG_CARD)
    red_card = tk.Frame(body, bg=theme.BG_CARD)
    blue_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=5)
    red_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=5)

    right_panel = tk.Frame(body, bg=BG_MAIN)
    right_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=5)
    # 🧩 [2026-08-12 사장님 지시] 우측 시너지 3칸 접기 — 끄면 그 열을 통째로 빼서 두 팀 칸이 넓어진다.
    #   열을 남긴 채 위젯만 숨기면 빈 칸이 그대로 남는다 → grid_remove + 열 가중치 0 이 함께 가야 한다.
    def _synergy_sync(on=None):
        if on is None: on = bool(APP_CONFIG.get("show_synergy", True))
        try:
            if on:
                body.columnconfigure(2, weight=1, uniform="cols3")
                right_panel.grid()
            else:
                right_panel.grid_remove()
                body.columnconfigure(2, weight=0, uniform="")
        except Exception: pass
    _SYNERGY_SYNC[0] = _synergy_sync
    _synergy_sync()                      # 저장된 설정대로 시작(끈 채로 재시작해도 유지)
    # [v82.13 시안] 우측 열 = 시너지 3칸만 세로 균등 분할(광고·개발텍스트는 헤더로 복귀)

    pos_card = tk.Frame(right_panel, bg=theme.BG_BAR)
    pos_card.pack(fill="both", expand=True, pady=(0, 6))
    tk.Label(pos_card, text="🔥 고승률 시너지", bg=theme.BG_CARD, fg=theme.SUCCESS, font=FONT_LF_TITLE, anchor="w", padx=10, pady=4).pack(fill="x")
    pos_box = scrolledtext.ScrolledText(pos_card, height=3, width=22, bg=theme.BG_INPUT, fg=theme.SUCCESS, font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    pos_box.pack(fill="both", expand=True)
    pos_box.configure(state="disabled")

    neg_card = tk.Frame(right_panel, bg=theme.BG_BAR)
    neg_card.pack(fill="both", expand=True, pady=(0, 6))
    tk.Label(neg_card, text="⚠ 역시너지 경보", bg=theme.BG_CARD, fg=theme.WARN, font=FONT_LF_TITLE, anchor="w", padx=10, pady=4).pack(fill="x")
    neg_box = scrolledtext.ScrolledText(neg_card, height=3, width=22, bg=theme.BG_INPUT, fg=theme.WARN, font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    neg_box.pack(fill="both", expand=True)
    neg_box.configure(state="disabled")

    nemesis_card = tk.Frame(right_panel, bg=theme.BG_BAR)
    nemesis_card.pack(fill="both", expand=True)
    tk.Label(nemesis_card, text="⚔ 적팀 인간상성", bg=theme.BG_CARD, fg=theme.TEAM_RED_FG, font=FONT_LF_TITLE, anchor="w", padx=10, pady=4).pack(fill="x")
    nemesis_box = scrolledtext.ScrolledText(nemesis_card, height=3, width=22, bg=theme.BG_INPUT, fg=theme.TEAM_RED_FG, font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    nemesis_box.pack(fill="both", expand=True)
    nemesis_box.configure(state="disabled")

    b_head = tk.Frame(blue_card, bg=theme.TEAM_BLUE_BG)
    b_head.pack(fill="x")
    b_title_frame = tk.Frame(b_head, bg=theme.TEAM_BLUE_BG)
    b_title_frame.pack(side="left", fill="x", expand=True)

    blue_title_lbl = tk.Label(b_title_frame, text="🟦 BLUE TEAM", bg=theme.TEAM_BLUE_BG, fg=theme.TEAM_BLUE_FG, font=FONT_LF_TITLE, anchor="w", padx=12, pady=6)
    blue_title_lbl.pack(side="left")

    blue_ban_frame = tk.Frame(b_title_frame, bg=theme.TEAM_BLUE_BG)
    blue_ban_frame.pack(side="left", padx=5)
    
    def do_blue_multi():
        with gui_lock:
            open_multisearch(gui_data.get("blue", []))
    def do_red_multi():
        with gui_lock:
            open_multisearch(gui_data.get("red", []))
            
    btn_b_multi = tk.Button(b_head, text="멀티서치", font=UF(9, "bold"), bg=theme.WIN, fg="white", bd=0, cursor="hand2", command=do_blue_multi)
    btn_b_multi.pack(side="right", padx=10, pady=5)

    r_head = tk.Frame(red_card, bg=theme.TEAM_RED_BG)
    r_head.pack(fill="x")
    r_title_frame = tk.Frame(r_head, bg=theme.TEAM_RED_BG)
    r_title_frame.pack(side="left", fill="x", expand=True)

    red_title_lbl = tk.Label(r_title_frame, text="🟥 RED TEAM", bg=theme.TEAM_RED_BG, fg=theme.TEAM_RED_FG, font=FONT_LF_TITLE, anchor="w", padx=12, pady=6)
    red_title_lbl.pack(side="left")

    red_ban_frame = tk.Frame(r_title_frame, bg=theme.TEAM_RED_BG)
    red_ban_frame.pack(side="left", padx=5)
    btn_r_multi = tk.Button(r_head, text="멀티서치", font=UF(9, "bold"), bg=theme.LOSE, fg="white", bd=0, cursor="hand2", command=do_red_multi)
    btn_r_multi.pack(side="right", padx=10, pady=5)

    blue_slots = []
    red_slots = []

    # [v82.19] 슬롯 5칸 고정 균등 높이 — 유저가 들어와 내용이 늘어도 칸 크기가 변하지 않게 grid uniform 분할
    b_slots_wrap = tk.Frame(blue_card, bg=theme.BG_CARD)
    b_slots_wrap.pack(fill="both", expand=True)
    b_slots_wrap.columnconfigure(0, weight=1)
    r_slots_wrap = tk.Frame(red_card, bg=theme.BG_CARD)
    r_slots_wrap.pack(fill="both", expand=True)
    r_slots_wrap.columnconfigure(0, weight=1)
    for _i in range(5):
        b_slots_wrap.rowconfigure(_i, weight=1, uniform="bslot")
        r_slots_wrap.rowconfigure(_i, weight=1, uniform="rslot")

    for i in range(5):
        bf = tk.Frame(b_slots_wrap, bg=theme.TEAM_BLUE_SOFT)
        bf.grid(row=i, column=0, sticky="nsew", padx=12, pady=1)
        bf.pack_propagate(False)   # 내부(pack) 내용이 커져도 칸이 안 늘어남 — 항상 균등 분할 크기 고정
        # [v82.9] 내용은 안쪽 컨테이너에 담고 바깥 여백(T1_FRAME_PAD)을 확보 — 프레임(베젤·하단 로고)이 여백에 보임
        binner = tk.Frame(bf, bg=theme.TEAM_BLUE_SOFT)
        binner.pack(fill="both", expand=True, padx=T1_FRAME_PAD[0], pady=(T1_FRAME_PAD[1], T1_FRAME_PAD[2]))
        bz = tk.Frame(binner, bg=theme.TEAM_BLUE_SOFT)
        bz.pack(fill="x", padx=10, pady=1)
        bti = tk.Label(bz, bg=theme.TEAM_BLUE_SOFT)
        bti.pack(side="left")
        btn = tk.Label(bz, text="Wait...", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT, font=FONT_SLOT_NAME)
        btn.pack(side="left", padx=6)
        bcb = tk.Button(bz, text="📋", font=UF(9), bg=theme.BG_RAISED, fg=theme.TEXT, bd=0, padx=5, pady=0, cursor="hand2")
        bcb.pack(side="left", padx=2)
        b_opgg = tk.Button(bz, text="🔍", font=UF(9), bg=theme.WARN, fg=theme.TEXT, bd=0, padx=5, pady=0, cursor="hand2")
        b_opgg.pack(side="left", padx=2)
        tk.Label(bz, text="➡", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT_MUT).pack(side="left", padx=4)
        bpi = tk.Label(bz, bg=theme.TEAM_BLUE_SOFT)
        bpi.pack(side="left", padx=4)
        btr = tk.Label(bz, text="", bg=theme.TEAM_BLUE_SOFT, fg=theme.GOLD, font=UF(11, "bold"))
        btr.pack(side="left", padx=(2, 0))
        bem = tk.Label(bz, bg=theme.TEAM_BLUE_SOFT)   # 🎨 [v81.93] '내 꾸미기' 엠블럼(내 칸에만)
        bem.pack(side="right", padx=(0, 6))
        bc_frame_1 = tk.Frame(binner, bg=theme.TEAM_BLUE_SOFT)
        bc_frame_1.pack(fill="x", padx=12, pady=0)
        bsub_1 = tk.Label(bc_frame_1, text="정찰 대기 중...", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT_SUB, font=FONT_SLOT_STAT, anchor="w")
        bsub_1.pack(side="left")
        bc_frame_2 = tk.Frame(binner, bg=theme.TEAM_BLUE_SOFT)
        bc_frame_2.pack(fill="x", padx=12, pady=0)
        bsub_2 = tk.Label(bc_frame_2, text="", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT_SUB, font=FONT_SLOT_STAT, anchor="w")
        bsub_2.pack(side="left")
        bc_frame_3 = tk.Frame(binner, bg=theme.TEAM_BLUE_SOFT)
        bc_frame_3.pack(fill="x", padx=12, pady=0)
        bsub_3 = tk.Label(bc_frame_3, text="", bg=theme.TEAM_BLUE_SOFT, fg=theme.LOSE, font=FONT_SLOT_STAT, anchor="w")
        bsub_3.pack(side="left")
        blue_slots.append((btn, bsub_1, bti, bpi, bcb, bc_frame_1, b_opgg, bc_frame_2, bsub_2, bc_frame_3, bsub_3, btr, bf, bem))   # [12]=칸 프레임 · [13]=🎨꾸미기 엠블럼

        rf = tk.Frame(r_slots_wrap, bg=theme.TEAM_RED_SOFT)
        rf.grid(row=i, column=0, sticky="nsew", padx=12, pady=1)
        rf.pack_propagate(False)   # [v82.19] 균등 분할 크기 고정
        rinner = tk.Frame(rf, bg=theme.TEAM_RED_SOFT)   # [v82.9] 프레임 여백용 안쪽 컨테이너
        rinner.pack(fill="both", expand=True, padx=T1_FRAME_PAD[0], pady=(T1_FRAME_PAD[1], T1_FRAME_PAD[2]))
        rz = tk.Frame(rinner, bg=theme.TEAM_RED_SOFT)
        rz.pack(fill="x", padx=10, pady=1)
        rti = tk.Label(rz, bg=theme.TEAM_RED_SOFT)
        rti.pack(side="left")
        rtn = tk.Label(rz, text="Wait...", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT, font=FONT_SLOT_NAME)
        rtn.pack(side="left", padx=6)
        rcb = tk.Button(rz, text="📋", font=UF(9), bg=theme.TEAM_RED_BG, fg=theme.TEXT, bd=0, padx=5, pady=0, cursor="hand2")
        rcb.pack(side="left", padx=2)
        r_opgg = tk.Button(rz, text="🔍", font=UF(9), bg=theme.WARN, fg=theme.TEXT, bd=0, padx=5, pady=0, cursor="hand2")
        r_opgg.pack(side="left", padx=2)
        tk.Label(rz, text="➡", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT_MUT).pack(side="left", padx=4)
        rpi = tk.Label(rz, bg=theme.TEAM_RED_SOFT)
        rpi.pack(side="left", padx=4)
        rtr = tk.Label(rz, text="", bg=theme.TEAM_RED_SOFT, fg=theme.GOLD, font=UF(11, "bold"))
        rtr.pack(side="left", padx=(2, 0))
        rem = tk.Label(rz, bg=theme.TEAM_RED_SOFT)   # 🎨 [v81.93] '내 꾸미기' 엠블럼(내 칸에만)
        rem.pack(side="right", padx=(0, 6))
        rc_frame_1 = tk.Frame(rinner, bg=theme.TEAM_RED_SOFT)
        rc_frame_1.pack(fill="x", padx=12, pady=0)
        rsub_1 = tk.Label(rc_frame_1, text="정찰 대기 중...", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT_SUB, font=FONT_SLOT_STAT, anchor="w")
        rsub_1.pack(side="left")
        rc_frame_2 = tk.Frame(rinner, bg=theme.TEAM_RED_SOFT)
        rc_frame_2.pack(fill="x", padx=12, pady=0)
        rsub_2 = tk.Label(rc_frame_2, text="", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT_SUB, font=FONT_SLOT_STAT, anchor="w")
        rsub_2.pack(side="left")
        rc_frame_3 = tk.Frame(rinner, bg=theme.TEAM_RED_SOFT)
        rc_frame_3.pack(fill="x", padx=12, pady=0)
        rsub_3 = tk.Label(rc_frame_3, text="", bg=theme.TEAM_RED_SOFT, fg=theme.LOSE, font=FONT_SLOT_STAT, anchor="w")
        rsub_3.pack(side="left")
        red_slots.append((rtn, rsub_1, rti, rpi, rcb, rc_frame_1, r_opgg, rc_frame_2, rsub_2, rc_frame_3, rsub_3, rtr, rf, rem))   # [12]=칸 프레임 · [13]=🎨꾸미기 엠블럼

    # 🔥 [2026-08-01 사장님 지시] 연승/연패 텍스트는 이름 옆에서 빼고, **5연승 이상**만
    #    닉네임이 불타는 효과로 대신한다. 텍스트가 아니라 색이 일렁이는 방식.
    BURN_MIN_STREAK = 5
    BURN_COLORS = ("#FFE08A", "#FFC44A", "#FF9E33", "#FF7A29", "#FF5A1F", "#FF7A29", "#FF9E33", "#FFC44A")
    _BURN_LABELS = set()          # 지금 불타는 중인 이름 라벨들(티커가 여기만 다시 칠한다)

    def _apply_burn(slot, sv):
        """5연승 이상이면 닉네임을 불타게, 아니면 원래 색으로 되돌린다.
           원래 색은 불이 붙는 순간에 기억해 둔다 — 상점 테마 색을 쓰는 사람도 정확히 복원된다."""
        try:
            lbl = slot[0]
            if int(sv or 0) >= BURN_MIN_STREAK:
                if not getattr(lbl, "_burning", False):
                    lbl._burn_prev = lbl.cget("fg")
                    lbl._burning = True
                    _BURN_LABELS.add(lbl)
                lbl.config(fg=BURN_COLORS[int(time.time() * 7) % len(BURN_COLORS)])
            elif getattr(lbl, "_burning", False):
                lbl.config(fg=getattr(lbl, "_burn_prev", None) or lbl.cget("fg"))
                lbl._burning = False
                _BURN_LABELS.discard(lbl)
        except Exception:
            pass

    def _burn_tick():
        """이름 라벨 갱신은 1초 주기라 불꽃이 뚝뚝 끊긴다 → 불타는 칸만 따로 자주 다시 칠한다."""
        try:
            c = BURN_COLORS[int(time.time() * 7) % len(BURN_COLORS)]
            for lbl in list(_BURN_LABELS):
                try:
                    if getattr(lbl, "_burning", False) and lbl.winfo_exists(): lbl.config(fg=c)
                    else: _BURN_LABELS.discard(lbl)
                except Exception:
                    _BURN_LABELS.discard(lbl)
        except Exception:
            pass
        finally:
            root.after(140, _burn_tick)

    def update_gui():
        try:
            with gui_lock:
                local_achievements = list(gui_data.get("achievements", []))
                if local_achievements:
                    gui_data["achievements"] = []
                    
                local_status = gui_data.get("status", "")
                # 🕵️ 스펠체크 헬퍼 상태 — 왜 안 되는지 콘솔을 안 봐도 보이게(사장님 전용 기능이라 값이 있을 때만)
                _sd = gui_data.get("spell_diag", "")
                if _sd and time.time() - gui_data.get("spell_diag_at", 0) < 20:
                    local_status = f"🕵️ {_sd}"
                local_bans = gui_data.get("bans", "")
                local_b_wr = gui_data.get("blue_win_rate", 50)
                local_r_wr = gui_data.get("red_win_rate", 50)
                local_b_advice = list(gui_data.get("blue_ban_advice_list", []))
                local_r_advice = list(gui_data.get("red_ban_advice_list", []))
                
                local_blue = list(gui_data.get("blue", []))
                local_red = list(gui_data.get("red", []))
                local_pos_view = gui_data.get("pos_view_mode", _posview_default())   # [v82.37] 설정값 따름

                local_pos_syn = gui_data.get("pos_synergy", "")
                local_neg_syn = gui_data.get("neg_synergy", "")
                local_nem_syn = gui_data.get("nemesis_synergy", "")
                
                ad_list = list(gui_data.get("ad_list", []))
                ad_index = gui_data.get("ad_index", 0)
                last_ad_time = gui_data.get("last_ad_time", 0)
                
            if local_achievements:
                ach_text = "아래 유저들이 게임 종료 후 특수 타이틀(업적)을 달성했습니다!\n\n"
                for a in local_achievements: ach_text += str(a) + "\n"
                def show_popup():
                    top_msg = tk.Toplevel(root)
                    top_msg.withdraw()
                    top_msg.attributes("-topmost", True)
                    messagebox.showinfo("🏆 매치 결과 리포트 및 타이틀 획득!", ach_text, parent=top_msg)
                    top_msg.destroy()
                root.after(100, show_popup)
                
            status_var.set(local_status)
            bans_var.set(local_bans)

            # 🚫 [v81.77] 10밴 현황을 챔피언 초상화로 렌더(텍스트 나열 → 아이콘)
            _bl = list(gui_data.get("ban_list", []))
            if _bl != _BANS_SHOWN[0]:
                _BANS_SHOWN[0] = _bl
                for w in bans_icon_frame.winfo_children(): w.destroy()
                for _bn in _bl:
                    _bimg = load_champion_image(_bn, size=22)
                    if _bimg:
                        _bl2 = tk.Label(bans_icon_frame, image=_bimg, bg=theme.BG_BAR)
                        _bl2.image = _bimg
                        _bl2.pack(side="left", padx=1)
                    # [시인성] 밴 챔피언 이름 텍스트 표기 제거 — 아이콘만(이미지 없으면 생략)

            blue_title_lbl.config(text=f"🟦 BLUE TEAM (예상 승률: {local_b_wr}%) | 밴 추천: ")
            # 🚫 [v81.76] 추천 밴 10개 → 5개씩 2줄(grid). 가로 한 줄로 늘어지지 않게.
            for widget in blue_ban_frame.winfo_children(): widget.destroy()
            if not local_b_advice:
                tk.Label(blue_ban_frame, text="자유 밴", bg=theme.TEAM_BLUE_BG, fg=theme.TEAM_BLUE_FG, font=UF(11, "bold")).grid(row=0, column=0, sticky="w")
            else:
                for _bi, champ_name in enumerate(local_b_advice):
                    _r, _c = divmod(_bi, 5)
                    img = load_champion_image(champ_name, size=24)
                    if img:
                        lbl = tk.Label(blue_ban_frame, image=img, bg=theme.TEAM_BLUE_BG)
                        lbl.image = img
                        lbl.grid(row=_r, column=_c, padx=2, pady=1)
                    else:
                        tk.Label(blue_ban_frame, text=champ_name, bg=theme.TEAM_BLUE_BG, fg=theme.TEAM_BLUE_FG, font=UF(10, "bold")).grid(row=_r, column=_c, padx=2, pady=1)

            red_title_lbl.config(text=f"🟥 RED TEAM (예상 승률: {local_r_wr}%) | 밴 추천: ")
            for widget in red_ban_frame.winfo_children(): widget.destroy()
            if not local_r_advice:
                tk.Label(red_ban_frame, text="자유 밴", bg=theme.TEAM_RED_BG, fg=theme.TEAM_RED_FG, font=UF(11, "bold")).grid(row=0, column=0, sticky="w")
            else:
                for _ri, champ_name in enumerate(local_r_advice):
                    _r, _c = divmod(_ri, 5)      # [v81.76] 5개씩 2줄
                    img = load_champion_image(champ_name, size=24)
                    if img:
                        lbl = tk.Label(red_ban_frame, image=img, bg=theme.TEAM_RED_BG)
                        lbl.image = img
                        lbl.grid(row=_r, column=_c, padx=2, pady=1)
                    else:
                        tk.Label(red_ban_frame, text=champ_name, bg=theme.TEAM_RED_BG, fg=theme.TEAM_RED_FG, font=UF(10, "bold")).grid(row=_r, column=_c, padx=2, pady=1)

            if ad_list:
                current_time = time.time()
                if current_time - last_ad_time > 5.0:
                    current_ad = ad_list[ad_index]
                    photo = ImageTk.PhotoImage(current_ad["img_obj"])
                    ad_lbl.config(image=photo, text="")
                    ad_lbl.image = photo 
                    with gui_lock:
                        gui_data["ad_link"] = current_ad["link"]
                        gui_data["ad_index"] = (ad_index + 1) % len(ad_list)
                        gui_data["last_ad_time"] = current_time

            def _apply_cosmetic(slot, raw_name, soft_bg, base_fg):
                """🖼️ 상점에서 산 '내 칸' 테마 적용 — 테두리·이름색·배경·뱃지. 없으면 기본으로 복원."""
                cos = _cos_of(raw_name)
                frm = slot[12]
                cell = cos.get("cell") or {}
                nm_lbl = slot[0]
                # 👻 [v82.34] 고스트밴픽왕 구독자 엠블렘 — 서버(봇)가 구독 검증해 내려준 값만 신뢰(로컬 위조 불가)
                _gh = " 👻" if cos.get("ghost") else ""
                if getattr(frm, "_t1_on", False):   # [v82.3] T1 꾸미기 활성 칸은 프레임/이름 리셋 금지(매 프레임 덮어쓰기 충돌 → 프리징)
                    deco = cos.get("deco") or {}
                    badge = (cell.get("badge") or "")
                    return deco.get("pre", ""), deco.get("suf", ""), ((" " + badge if badge else "") + _gh)
                try:
                    if cell:
                        bg = cell.get("bg") or soft_bg
                        bd = cell.get("border", soft_bg)
                        anim = cell.get("anim") or []
                        if anim:   # 👨‍💻 개발자 전용 — 매 프레임 색이 흐르는 네온 무지개(상점템은 전부 고정색)
                            bd = anim[int(time.time() * 3) % len(anim)]
                        frm.config(highlightbackground=bd, highlightcolor=bd,
                                   highlightthickness=int(cell.get("thick", 2) or 2), bg=bg)
                        nm_lbl.config(fg=cell.get("fg") or base_fg, bg=bg)
                    else:
                        frm.config(highlightthickness=0, bg=soft_bg)
                        nm_lbl.config(fg=base_fg, bg=soft_bg)   # 테마 해제 시 기본색 복원(잔상 방지)
                except Exception:
                    pass
                deco = cos.get("deco") or {}
                badge = (cell.get("badge") or "")
                return deco.get("pre", ""), deco.get("suf", ""), ((" " + badge if badge else "") + _gh)

            def _apply_my_cosmetic(slot, p, soft_bg):
                """🅣 [v82.18] 엠블럼 시스템 — 상점 구매·장착자(봇 /cosmetics 서버 검증)의 칸 '맨 우측 하단'에 로고만 표시.
                   프레임(배경 이미지·테두리·여백) 전면 폐기. 상태 변화 없으면 no-op(리드로우 폭풍 방지)."""
                try:
                    ck = str((_cos_of(str(p.get('name', ''))) or {}).get("frame") or "")   # 서버가 소유·장착 검증한 값만 도착
                    if ck in T1_EMBLEM_FILES:
                        _t1_live.append(slot[12])   # 이번 사이클 '살아있는' 엠블럼(스윕 보호) — 조기 return보다 먼저
                        if getattr(slot[12], "_t1_last", None) == ck: return
                        ph = _t1_emblem_photo(ck, soft_bg)
                        if ph is None: return
                        slot[12]._t1_last = ck
                        _T1_REG.add(slot[12])
                        lbl = getattr(slot[12], "_t1_bg", None)
                        if lbl is None:
                            lbl = tk.Label(slot[12], bd=0, highlightthickness=0, bg=soft_bg)
                            slot[12]._t1_bg = lbl
                        lbl.config(image=ph, bg=soft_bg); lbl.image = ph
                        lbl.place(relx=1.0, rely=1.0, x=-6, y=-4, anchor="se")   # 칸 맨 우측 하단
                        lbl.lift()
                    else:
                        if getattr(slot[12], "_t1_last", None) == "off": return
                        slot[12]._t1_last = "off"
                        lbl = getattr(slot[12], "_t1_bg", None)
                        if lbl is not None: lbl.place_forget()
                except Exception: pass

            _t1_live = []   # [v82.7] 이번 사이클에 프레임을 받은 슬롯 — 루프 뒤 스윕에서 이외 프레임 전부 제거
            for i in range(5):
                if i < len(local_blue):
                    p, s = local_blue[i]
                    name_str = str(p.get('name', '')) # 유저 요청에 따라 무조건 현재 클라이언트의 최신 닉네임 우선 표시
                    lp_str = " | " + str(p.get('lp', 0)) + " LP" if p.get('tier_icon') != "UNRANKED" else ""
                    _pre, _suf, _bdg = _apply_cosmetic(blue_slots[i], name_str, theme.TEAM_BLUE_SOFT, theme.TEAM_BLUE_FG)
                    _apply_my_cosmetic(blue_slots[i], p, theme.TEAM_BLUE_SOFT)
                    _apply_burn(blue_slots[i], s.get("streak_val", 0))   # 🔥 5연승 이상이면 닉네임이 탄다
                    name_str = _pre + name_str + _suf + _bdg
                    blue_slots[i][0].config(text=name_str + lp_str)
                    _most_disp, _op_disp, _pos_tag = _display_champ_lists(p, s, local_pos_view)
                    blue_slots[i][1].config(text=" 전적: " + str(s.get('summary', '')) + " | 모스트" + _pos_tag + ": ")
                    for widget in blue_slots[i][5].winfo_children():
                        if widget != blue_slots[i][1]: widget.destroy()
                    
                    for champ_info in _most_disp[:5]:   # [시인성] 모스트5·초상화만(판수 텍스트 제거)
                        img = load_champion_image(champ_info["name"])
                        if img:
                            lbl = tk.Label(blue_slots[i][5], image=img, bg=theme.TEAM_BLUE_SOFT)
                            lbl.image = img; lbl.pack(side="left", padx=2)
                        else:
                            tk.Label(blue_slots[i][5], text=str(champ_info["name"]) + " ", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=2)

                    blue_slots[i][8].config(text=" 고승률픽" + _pos_tag + ": ")
                    for widget in blue_slots[i][7].winfo_children():
                        if widget != blue_slots[i][8]: widget.destroy()
                    
                    op_list = _op_disp
                    if not op_list: tk.Label(blue_slots[i][7], text="없음", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=2)
                    else:
                        for champ_info in op_list[:5]:   # [시인성] 고승률픽 초상화만(승률·판수 텍스트 제거)
                            img = load_champion_image(champ_info["name"])
                            if img:
                                lbl = tk.Label(blue_slots[i][7], image=img, bg=theme.TEAM_BLUE_SOFT)
                                lbl.image = img; lbl.pack(side="left", padx=2)
                            else:
                                tk.Label(blue_slots[i][7], text=str(champ_info["name"]) + " ", bg=theme.TEAM_BLUE_SOFT, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=2)
                    # [시인성] 진영승률 표기 제거

                    text_fb = _fatal_ban_text(p, s, local_pos_view)
                    if text_fb:
                        blue_slots[i][10].config(text=text_fb, fg=theme.LOSE)
                        blue_slots[i][9].pack(fill="x", padx=12, pady=0)   # [v82.11] 경고 있을 때만 줄 표시(빈 줄이 세로공간 잠식 → 서폿칸 잘림)
                    else:
                        blue_slots[i][10].config(text="", fg=theme.TEXT_MUT)
                        blue_slots[i][9].pack_forget()

                    ti = tier_images.get(p.get("tier_icon", "UNRANKED"))
                    ci = position_images.get(p.get("chosen_pos_icon", "NONE"))
                    blue_slots[i][2].config(image=ti if ti else ''); blue_slots[i][2].image = ti
                    blue_slots[i][3].config(image=ci if ci else ''); blue_slots[i][3].image = ci
                    _ct = tier_of(name_str)
                    blue_slots[i][11].config(text=(str(_ct) if _ct else ""))

                    blue_slots[i][4].config(command=lambda b=blue_slots[i][4], n=name_str: copy_id_to_clipboard(root, b, n), state="normal")
                    blue_slots[i][6].config(command=lambda n=name_str: open_opgg_profile(n), state="normal")
                else:
                    _apply_my_cosmetic(blue_slots[i], {}, theme.TEAM_BLUE_SOFT)   # [v82.6] 빈 슬롯 꾸미기 잔상 정리(자리이동 시 프레임 남던 것)
                    _apply_burn(blue_slots[i], 0)   # 빈 슬롯이 되면 불도 끈다(잔상 방지)
                    blue_slots[i][0].config(text="대기 중...", fg=theme.TEXT_MUT)
                    blue_slots[i][1].config(text="소환사를 정찰하고 있습니다.")
                    blue_slots[i][8].config(text="")
                    blue_slots[i][10].config(text=""); blue_slots[i][9].pack_forget()
                    
                    for widget in blue_slots[i][5].winfo_children():
                        if widget != blue_slots[i][1]: widget.destroy()
                    for widget in blue_slots[i][7].winfo_children():
                        if widget != blue_slots[i][8]: widget.destroy()
                        
                    blue_slots[i][2].config(image='')
                    blue_slots[i][3].config(image='')
                    blue_slots[i][11].config(text="")
                    blue_slots[i][4].config(command=None, state="disabled")
                    blue_slots[i][6].config(command=None, state="disabled")

                if i < len(local_red):
                    p, s = local_red[i]
                    name_str = str(p.get('name', '')) # 유저 요청에 따라 무조건 현재 클라이언트의 최신 닉네임 우선 표시
                    lp_str = " | " + str(p.get('lp', 0)) + " LP" if p.get('tier_icon') != "UNRANKED" else ""
                    
                    _pre, _suf, _bdg = _apply_cosmetic(red_slots[i], name_str, theme.TEAM_RED_SOFT, theme.TEAM_RED_FG)
                    _apply_my_cosmetic(red_slots[i], p, theme.TEAM_RED_SOFT)
                    _apply_burn(red_slots[i], s.get("streak_val", 0))    # 🔥 5연승 이상이면 닉네임이 탄다
                    name_str = _pre + name_str + _suf + _bdg
                    red_slots[i][0].config(text=name_str + lp_str)
                    _most_disp, _op_disp, _pos_tag = _display_champ_lists(p, s, local_pos_view)
                    red_slots[i][1].config(text=" 전적: " + str(s.get('summary', '')) + " | 모스트" + _pos_tag + ": ")
                    for widget in red_slots[i][5].winfo_children():
                        if widget != red_slots[i][1]: widget.destroy()
                        
                    for champ_info in _most_disp[:5]:   # [시인성] 모스트5·초상화만(판수 텍스트 제거)
                        img = load_champion_image(champ_info["name"])
                        if img:
                            lbl = tk.Label(red_slots[i][5], image=img, bg=theme.TEAM_RED_SOFT)
                            lbl.image = img; lbl.pack(side="left", padx=2)
                        else:
                            tk.Label(red_slots[i][5], text=str(champ_info["name"]) + " ", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=2)

                    red_slots[i][8].config(text=" 고승률픽" + _pos_tag + ": ")
                    for widget in red_slots[i][7].winfo_children():
                        if widget != red_slots[i][8]: widget.destroy()
                    
                    op_list = _op_disp
                    if not op_list: tk.Label(red_slots[i][7], text="없음", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=2)
                    else:
                        for champ_info in op_list[:5]:   # [시인성] 고승률픽 초상화만(승률·판수 텍스트 제거)
                            img = load_champion_image(champ_info["name"])
                            if img:
                                lbl = tk.Label(red_slots[i][7], image=img, bg=theme.TEAM_RED_SOFT)
                                lbl.image = img; lbl.pack(side="left", padx=2)
                            else:
                                tk.Label(red_slots[i][7], text=str(champ_info["name"]) + " ", bg=theme.TEAM_RED_SOFT, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=2)
                    # [시인성] 진영승률 표기 제거

                    text_fb = _fatal_ban_text(p, s, local_pos_view)
                    if text_fb:
                        red_slots[i][10].config(text=text_fb, fg=theme.LOSE)
                        red_slots[i][9].pack(fill="x", padx=12, pady=0)   # [v82.11] 경고 있을 때만 줄 표시
                    else:
                        red_slots[i][10].config(text="", fg=theme.TEXT_MUT)
                        red_slots[i][9].pack_forget()

                    ti = tier_images.get(p.get("tier_icon", "UNRANKED"))
                    ci = position_images.get(p.get("chosen_pos_icon", "NONE"))
                    red_slots[i][2].config(image=ti if ti else ''); red_slots[i][2].image = ti
                    red_slots[i][3].config(image=ci if ci else ''); red_slots[i][3].image = ci
                    _ct = tier_of(name_str)
                    red_slots[i][11].config(text=(str(_ct) if _ct else ""))

                    red_slots[i][4].config(command=lambda b=red_slots[i][4], n=name_str: copy_id_to_clipboard(root, b, n), state="normal")
                    red_slots[i][6].config(command=lambda n=name_str: open_opgg_profile(n), state="normal")
                else:
                    _apply_my_cosmetic(red_slots[i], {}, theme.TEAM_RED_SOFT)   # [v82.6] 빈 슬롯 꾸미기 잔상 정리
                    _apply_burn(red_slots[i], 0)   # 빈 슬롯이 되면 불도 끈다(잔상 방지)
                    red_slots[i][0].config(text="대기 중...", fg=theme.TEXT_MUT)
                    red_slots[i][1].config(text="소환사를 정찰하고 있습니다.")
                    red_slots[i][8].config(text="")
                    red_slots[i][10].config(text=""); red_slots[i][9].pack_forget()
                    
                    for widget in red_slots[i][5].winfo_children():
                        if widget != red_slots[i][1]: widget.destroy()
                    for widget in red_slots[i][7].winfo_children():
                        if widget != red_slots[i][8]: widget.destroy()
                        
                    red_slots[i][2].config(image='')
                    red_slots[i][3].config(image='')
                    red_slots[i][11].config(text="")
                    red_slots[i][4].config(command=None, state="disabled")
                    red_slots[i][6].config(command=None, state="disabled")

            # [v82.7] 엠블럼 잔상 스윕 — 이번 사이클에 엠블럼을 받지 않은 슬롯은 경로 불문 강제 제거(자리이동 잔상 방지)
            for _bf in list(_T1_REG):
                if _bf in _t1_live: continue
                try:
                    _l = getattr(_bf, "_t1_bg", None)
                    if _l is not None: _l.place_forget()
                    _bf._t1_last = "off"
                except Exception: pass
                _T1_REG.discard(_bf)

            pos_box.configure(state="normal"); pos_box.delete("1.0", tk.END); pos_box.insert(tk.END, str(local_pos_syn)); pos_box.configure(state="disabled")
            neg_box.configure(state="normal"); neg_box.delete("1.0", tk.END); neg_box.insert(tk.END, str(local_neg_syn)); neg_box.configure(state="disabled")
            nemesis_box.configure(state="normal"); nemesis_box.delete("1.0", tk.END); nemesis_box.insert(tk.END, str(local_nem_syn)); nemesis_box.configure(state="disabled")
            
            # 🧠 [v81.74] 고스트밴픽왕 오버레이 — 추천이 생기면 항상-위 작은 창으로 띄움(롤 클라 위에 보이게)
            try: _draft_overlay_sync(root)
            except Exception: pass

        except Exception: pass
        finally: root.after(1000, update_gui)

    root.after(1000, update_gui)
    root.after(200, _burn_tick)   # 🔥 불꽃 애니메이션(불타는 칸만 다시 칠함)

    # ===== 트레이 모드(설정에서 켤 때만): X(닫기)→트레이 최소화. 기본값 OFF = X 누르면 완전 종료. =====
    _tray = {"icon": None}
    def _tray_image():
        try:
            from PIL import Image
            return Image.open(resource_path("icon.ico"))
        except Exception:
            try:
                from PIL import Image
                return Image.new("RGB", (64, 64), (125, 95, 153))
            except Exception:
                return None
    def _tray_show(icon=None, item=None):
        root.after(0, root.deiconify); root.after(0, root.lift)
        root.after(0, lambda: root.attributes('-topmost', True))
        root.after(150, lambda: root.attributes('-topmost', False))
        with gui_lock: gui_data["is_hidden"] = False
    def _save_win_size():
        """[v82.18] 종료 시 현재 창 크기 저장 — 다음 실행에서 그대로 복원(사용자가 늘리고 줄인 크기 기억)."""
        try:
            if root.state() == "zoomed":
                APP_CONFIG["win_last"] = "max"
            else:
                APP_CONFIG["win_last"] = f"{root.winfo_width()}x{root.winfo_height()}"
            save_config(APP_CONFIG)
        except Exception: pass
    def _tray_quit(icon=None, item=None):
        _save_win_size()
        try:
            if _tray.get("icon"): _tray["icon"].stop()
        except Exception: pass
        os._exit(0)
    def _hide_to_tray():
        root.withdraw()
        with gui_lock: gui_data["is_hidden"] = True
        try:
            if _tray.get("icon"): _tray["icon"].notify("트레이에서 백그라운드 실행 중입니다. (우클릭 → 종료로 완전 종료)", "스쿼드해체분석기")
        except Exception: pass
    def _on_close():
        # 설정 minimize_to_tray가 켜져 있고 트레이 아이콘이 살아있으면 최소화, 아니면 완전 종료(기본값)
        if APP_CONFIG.get("minimize_to_tray", False) and _tray.get("icon"):
            _hide_to_tray()
        else:
            _tray_quit()
    if APP_CONFIG.get("minimize_to_tray", False):   # 설정 켜진 경우에만 트레이 아이콘 생성
        try:
            import pystray
            from pystray import Menu as _TMenu, MenuItem as _TItem
            _img = _tray_image()
            if _img is not None:
                _tray["icon"] = pystray.Icon("squad_analyzer", _img, "스쿼드해체분석기",
                                             _TMenu(_TItem("열기", _tray_show, default=True), _TItem("종료", _tray_quit)))
                threading.Thread(target=_tray["icon"].run, daemon=True).start()
        except Exception as _te:
            print(f"[tray] 트레이 비활성: {_te}", flush=True)
    root.protocol("WM_DELETE_WINDOW", _on_close)   # 기본 X=완전종료, 설정 켜면 트레이 최소화

    # 🔄 자동 업데이트 안내: 업데이터가 교체 준비되면(무음 종료 대신) 안내창 잠깐 띄우고 재시작
    def _show_update_notice():
        try:
            win = tk.Toplevel(root); win.overrideredirect(True); win.configure(bg=theme.BG_BAR)
            win.attributes("-topmost", True)
            w, h = 440, 140
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            fr = tk.Frame(win, bg=theme.BG_BAR, highlightbackground=theme.GOLD, highlightthickness=2); fr.pack(fill="both", expand=True)
            tk.Label(fr, text="🔄  새 버전으로 업데이트 중", bg=theme.BG_BAR, fg=theme.GOLD, font=UF(15, "bold")).pack(pady=(24, 6))
            tk.Label(fr, text="잠시 후 프로그램이 자동으로 다시 시작됩니다.", bg=theme.BG_BAR, fg=theme.TEXT, font=UF(11)).pack()
            tk.Label(fr, text="(창이 잠깐 닫혔다가 새 버전으로 켜집니다 — 정상입니다)", bg=theme.BG_BAR, fg=theme.TEXT_SUB, font=UF(9)).pack(pady=(6, 0))
            win.update()
        except Exception: pass
    def _poll_update_exit():
        if _UPDATE_EXIT_REQUESTED:
            try:
                with gui_lock: gui_data["status"] = "🔄 새 버전 업데이트 적용 중..."
            except Exception: pass
            _show_update_notice()
            root.after(2800, lambda: os._exit(0))   # 안내 2.8초 노출 후 종료 → 업데이터가 폴더 교체·재실행
            return
        root.after(700, _poll_update_exit)
    root.after(1500, _poll_update_exit)

    root.mainloop()

class ClanRankingWindow(tk.Toplevel):
    def __init__(self, parent, mode="CLASSIC"):
        super().__init__(parent)
        self.mode = mode   # 시작 카테고리(창 안에서 협곡/칼바람 탭으로 전환)
        self.title_text = "스쿼드 명예의 전당"
        self.title(self.title_text)
        self.geometry("1200x850")
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        self.current_pos = "ALL"
        self.current_ver = "전체 (ALL)"
        
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg=theme.BG_BAR, height=60)
        top_bar.pack(fill="x", side="top")
        
        self.title_lbl = tk.Label(top_bar, text=self.title_text, bg=theme.BG_BAR, fg=theme.GOLD, font=UF(16, "bold"))
        self.title_lbl.pack(side="left", padx=20, pady=15)

        btn_frame = tk.Frame(top_bar, bg=theme.BG_BAR)
        btn_frame.pack(side="right", padx=20, pady=15)

        self.btn_refresh = tk.Button(btn_frame, text="데이터 갱신", font=UF(10, "bold"), bg=theme.BG_RAISED, fg=theme.TEXT, bd=0, padx=12, pady=4, cursor="hand2", command=self.refresh_action)
        self.btn_refresh.pack(side="right", padx=5)

        tk.Label(btn_frame, text="메타(패치) 필터:", bg=theme.BG_BAR, fg=theme.TEXT, font=UF(10)).pack(side="left", padx=5)

        self.ver_var = tk.StringVar()
        self.ver_combo = ttk.Combobox(btn_frame, textvariable=self.ver_var, state="readonly", width=12, font=UF(10))
        self.ver_combo.bind("<<ComboboxSelected>>", self.switch_version)
        self.ver_combo.pack(side="left", padx=5)

        # 🗺❄ 카테고리 탭(협곡/칼바람) — 기존 '증내의 전당' 버튼을 여기로 통합(2026-07-16)
        self.cat_frame = tk.Frame(self, bg=theme.BG)
        self.cat_frame.pack(fill="x", padx=20, pady=(8, 0))
        self.cat_btns = {}
        for c_key, c_kor in [("CLASSIC", "협곡"), ("ARAM", "칼바람")]:
            cb = tk.Button(self.cat_frame, text=c_kor, font=UF(11, "bold"), bg=theme.BG_CARD, fg=theme.TEXT_SUB, bd=0, padx=22, pady=5, cursor="hand2", command=lambda k=c_key: self.switch_mode(k))
            cb.pack(side="left", padx=(0, 6))
            self.cat_btns[c_key] = cb
        # 🏅 [v82.22] 기록실 토글 — 킬/데스/어시/딜량/AI점수 단일게임·누적 랭킹
        self.records_mode = False
        self.btn_records = tk.Button(self.cat_frame, text="🏅 기록실", font=UF(11, "bold"), bg=theme.BG_CARD, fg=theme.TEXT_SUB, bd=0, padx=22, pady=5, cursor="hand2", command=self.toggle_records)
        self.btn_records.pack(side="left", padx=(18, 0))

        # 포지션 필터(협곡 전용) — 항상 생성하고 모드에 따라 pack/pack_forget
        self.pos_frame = tk.Frame(self, bg=theme.BG)
        self.pos_btns = {}
        pos_list = [("ALL", "통합"), ("TOP", "탑"), ("JUNGLE", "정글"), ("MIDDLE", "미드"), ("BOTTOM", "원딜"), ("UTILITY", "서폿")]
        for p_key, p_kor in pos_list:
            btn = tk.Button(self.pos_frame, text=p_kor, font=UF(11, "bold"), bg=theme.BG_CARD, fg=theme.TEXT_SUB, bd=0, padx=15, pady=4, cursor="hand2", command=lambda k=p_key: self.switch_pos(k))
            btn.pack(side="left", padx=5)
            self.pos_btns[p_key] = btn
        self._apply_mode_ui()

        self.grid_frame = tk.Frame(self, bg=theme.BG)
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        self.grid_frame.columnconfigure(0, weight=1, uniform="rank_card")
        self.grid_frame.columnconfigure(1, weight=1, uniform="rank_card")
        self.grid_frame.rowconfigure(0, weight=1)
        self.grid_frame.rowconfigure(1, weight=1)
        
        # HOF 데이터가 아직 없으면(비호스트 지연로드) 자동 로드 후 렌더
        with gui_lock: _has_hof = bool(gui_data.get("hof_classic", {}).get("global_stats", {}).get("전체 (ALL)")) or bool(gui_data.get("hof_aram", {}).get("global_stats", {}).get("전체 (ALL)"))
        if _has_hof:
            self.update_versions(); self.render_data()
        else:
            self.refresh_action()

        bot_bar = tk.Frame(self, bg=theme.BG, height=50)
        bot_bar.pack(fill="x", side="bottom")
        tk.Button(bot_bar, text="닫기", font=UF(11, "bold"), bg=theme.BG_RAISED, fg=theme.TEXT, bd=0, width=20, pady=6, cursor="hand2", command=self.destroy).pack(pady=10)

    def _apply_mode_ui(self):
        # 카테고리 버튼 하이라이트 + 포지션 필터(협곡·종합랭킹에서만 노출)
        for k, b in self.cat_btns.items():
            if k == self.mode: b.config(bg=theme.ACCENT, fg=theme.TEXT)
            else: b.config(bg=theme.BG_CARD, fg=theme.TEXT_SUB)
        _rec = getattr(self, "records_mode", False)
        try: self.btn_records.config(bg=(theme.GOLD if _rec else theme.BG_CARD), fg=("#1b1b1b" if _rec else theme.TEXT_SUB))
        except Exception: pass
        if self.mode == "CLASSIC" and not _rec:
            self.pos_frame.pack(fill="x", padx=20, pady=5, after=self.cat_frame)
        else:
            self.pos_frame.pack_forget()

    def toggle_records(self):
        self.records_mode = not getattr(self, "records_mode", False)
        self._apply_mode_ui()
        self.render_data()

    def switch_mode(self, mode):
        if mode == self.mode: return
        self.mode = mode
        self.current_pos = "ALL"
        self.current_ver = "전체 (ALL)"
        self._apply_mode_ui()
        self.update_versions()
        self.render_data()

    def switch_pos(self, pos_key):
        self.current_pos = pos_key
        self.render_data()

    def switch_version(self, event=None):
        val = self.ver_var.get()
        if "ALL" in val: self.current_ver = "전체 (ALL)"
        else: self.current_ver = val
        self.render_data()

    def update_versions(self):
        target_key = "hof_classic" if self.mode == "CLASSIC" else "hof_aram"
        with gui_lock:
            patches = list(gui_data.get(target_key, {}).get("patches", ["전체 (ALL)"]))
            
        cb_values = patches
        if "과거버전" in cb_values:
            cb_values.remove("과거버전")
            cb_values.append("과거버전")
            
        self.ver_combo['values'] = cb_values
        
        if self.current_ver not in cb_values:
            if "전체 (ALL)" in cb_values:
                self.current_ver = "전체 (ALL)"
            else:
                self.current_ver = cb_values[0] if cb_values else ""
                
        self.ver_combo.set(self.current_ver)

    def refresh_action(self):
        self.btn_refresh.config(text="갱신 중...", state="disabled")
        def worker():
            update_hof_stats(force=True)
            self.after(0, self.update_versions)
            self.after(0, self.render_data)
            self.after(0, lambda: self.btn_refresh.config(text="데이터 갱신", state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def render_records(self):
        """🏅 [v82.22] 기록실 — 단일게임(최다킬/데스/어시/최대딜량/최고AI점수) + 누적(킬·데스·어시 총합, 평균딜량, KDA평점) TOP10."""
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        with gui_lock:
            recs = dict(gui_data.get("hof_records", {}).get("classic" if self.mode == "CLASSIC" else "aram", {}))
        cv = tk.Canvas(self.grid_frame, bg=theme.BG, highlightthickness=0)
        sb = ttk.Scrollbar(self.grid_frame, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=theme.BG)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw", width=1130)
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        inner.columnconfigure(0, weight=1, uniform="reccol"); inner.columnconfigure(1, weight=1, uniform="reccol")
        rl = list(recs.values())
        _fmtn = lambda v: f"{v:,}"
        cards = [
            ("⚔ 한 판 최다킬", theme.GOLD,
             [(x["mx_k"][0], f"{str(x['name']).split('#')[0]} — {x['mx_k'][0]}킬 ({x['mx_k'][1]} · {x['mx_k'][2]})") for x in rl if x["mx_k"][0] > 0]),
            ("💀 한 판 최다데스", theme.TEAM_RED_FG,
             [(x["mx_d"][0], f"{str(x['name']).split('#')[0]} — {x['mx_d'][0]}데스 ({x['mx_d'][1]} · {x['mx_d'][2]})") for x in rl if x["mx_d"][0] > 0]),
            ("🤝 한 판 최다어시", theme.SUCCESS,
             [(x["mx_a"][0], f"{str(x['name']).split('#')[0]} — {x['mx_a'][0]}어시 ({x['mx_a'][1]} · {x['mx_a'][2]})") for x in rl if x["mx_a"][0] > 0]),
            ("💥 한 판 최대 딜량", theme.WARN,
             [(x["mx_dmg"][0], f"{str(x['name']).split('#')[0]} — {_fmtn(x['mx_dmg'][0])} ({x['mx_dmg'][1]} · {x['mx_dmg'][2]})") for x in rl if x["mx_dmg"][0] > 0]),
            ("🧠 한 판 최고 AI점수", theme.PURPLE if hasattr(theme, "PURPLE") else theme.GOLD,
             [(x["mx_sc"][0], f"{str(x['name']).split('#')[0]} — {x['mx_sc'][0]:.1f}점 ({x['mx_sc'][1]} · {x['mx_sc'][2]})") for x in rl if x["mx_sc"][0] > 0]),
            ("⚔ 누적 킬왕", theme.GOLD,
             [(x["tk"], f"{str(x['name']).split('#')[0]} — 총 {_fmtn(x['tk'])}킬 ({x['g']}판)") for x in rl if x["tk"] > 0]),
            ("💀 누적 데스왕", theme.TEAM_RED_FG,
             [(x["td"], f"{str(x['name']).split('#')[0]} — 총 {_fmtn(x['td'])}데스 ({x['g']}판)") for x in rl if x["td"] > 0]),
            ("🤝 누적 어시왕", theme.SUCCESS,
             [(x["ta"], f"{str(x['name']).split('#')[0]} — 총 {_fmtn(x['ta'])}어시 ({x['g']}판)") for x in rl if x["ta"] > 0]),
            ("📈 KDA 평점 (10판↑)", theme.TEAM_BLUE_FG,
             [((x["tk"] + x["ta"]) / max(1, x["td"]), f"{str(x['name']).split('#')[0]} — {(x['tk'] + x['ta']) / max(1, x['td']):.2f} ({x['tk']}/{x['td']}/{x['ta']})") for x in rl if x["g"] >= 10 and (x["tk"] + x["td"] + x["ta"]) > 0]),
        ]
        # 📊 [v82.41] 웹 기록실과 동일 확장 — 포지션별 라인지표 + 상세지표(웹 squad.gg 기록실 미러)
        _POSK = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서폿"}
        _nm = lambda x: str(x["name"]).split("#")[0]
        def _pline(min_n, skey, nkey, fv):
            """포지션별 (선수×포지션) 엔트리 — 한 사람이 여러 포지션으로 동시 랭크 가능(웹과 동일 규칙)."""
            out = []
            for x in rl:
                for pos, v in (x.get("pp") or {}).items():
                    n = v.get(nkey, 0)
                    if n >= min_n:
                        val = v.get(skey, 0.0) / n
                        out.append((val, f"{_nm(x)} — {fv(val)} ({n}판·{_POSK.get(pos, pos)})"))
            return out
        def _avg(min_n, skey, nkey, fv):
            return [(x.get(skey, 0.0) / x.get(nkey, 1), f"{_nm(x)} — {fv(x.get(skey, 0.0) / x.get(nkey, 1))} ({x.get(nkey, 0)}판)")
                    for x in rl if x.get(nkey, 0) >= min_n]
        def _tot(skey, nkey, fv):
            return [(x.get(skey, 0), f"{_nm(x)} — {fv(x.get(skey, 0))} ({x.get(nkey, 0)}판)") for x in rl if x.get(skey, 0) > 0]
        cards += [
            ("💥 평균 딜량 (10판↑·포지션별)", theme.WARN, _pline(10, "dmg_sum", "dmg_n", lambda v: f"평균 {_fmtn(int(v))}")),
            ("🧠 평균 AI점수 (10판↑·포지션별)", theme.PURPLE if hasattr(theme, "PURPLE") else theme.GOLD,
             _pline(10, "sc_sum", "sc_n", lambda v: f"{v:.1f}점")),
            ("⚡ 분당 데미지 DPM (5판↑·포지션별)", theme.WARN, _pline(5, "dpm", "met_n", lambda v: f"분당 {_fmtn(int(v))}")),
            ("💰 분당 골드 GPM (5판↑·포지션별)", theme.GOLD, _pline(5, "gpm", "met_n", lambda v: f"분당 {_fmtn(int(v))}G")),
            ("🌾 분당 CS (5판↑·포지션별)", theme.SUCCESS, _pline(5, "cspm", "met_n", lambda v: f"분당 {v:.1f}개")),
            ("🤝 평균 킬관여율 (5판↑)", theme.SUCCESS, _avg(5, "kp_sum", "met_n", lambda v: f"{round(v)}%")),
            ("👁 평균 시야점수 (5판↑)", theme.TEAM_BLUE_FG, _avg(5, "vs_sum", "met_n", lambda v: f"{v:.1f}점")),
            ("🔮 제어와드왕 (누적)", theme.PURPLE if hasattr(theme, "PURPLE") else theme.GOLD,
             _tot("cw_sum", "met_n", lambda v: f"총 {_fmtn(v)}개")),
            ("🗡 솔로킬왕 (누적)", theme.TEAM_RED_FG, _tot("sk_sum", "met_n", lambda v: f"총 {_fmtn(v)}회")),
            ("🗡 솔킬률 (5판↑·판당 솔로킬)", theme.TEAM_RED_FG,
             [(x.get("sk_sum", 0) / x["met_n"], f"{_nm(x)} — {round(x.get('sk_sum', 0) / x['met_n'] * 100)}% ({x.get('sk_sum', 0)}회/{x['met_n']}판)")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("sk_sum", 0) > 0]),
            ("🛡 분당 받은 피해 (5판↑·탱킹)", theme.TEAM_BLUE_FG, _avg(5, "dtpm_sum", "met_n", lambda v: f"분당 {_fmtn(int(v))}")),
            ("🛡 한 판 최다 받은 피해", theme.TEAM_BLUE_FG,
             [(x["mx_dt"][0], f"{_nm(x)} — {_fmtn(x['mx_dt'][0])} ({x['mx_dt'][1]} · {x['mx_dt'][2]})") for x in rl if x.get("mx_dt", (-1,))[0] > 0]),
            ("🐉 평균 드래곤 관여 (5판↑)", theme.SUCCESS,
             [(x.get("dr_sum", 0) / x["met_n"], f"{_nm(x)} — 판당 {x.get('dr_sum', 0) / x['met_n']:.2f}마리 (총 {x.get('dr_sum', 0)}·{x['met_n']}판)")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("dr_sum", 0) > 0]),
            ("🟣 평균 바론 관여 (5판↑)", theme.PURPLE if hasattr(theme, "PURPLE") else theme.GOLD,
             [(x.get("br_sum", 0) / x["met_n"], f"{_nm(x)} — 판당 {x.get('br_sum', 0) / x['met_n']:.2f}마리 (총 {x.get('br_sum', 0)}·{x['met_n']}판)")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("br_sum", 0) > 0]),
            ("🏰 평균 포탑 철거 (5판↑)", theme.GOLD,
             [(x.get("tur_sum", 0) / x["met_n"], f"{_nm(x)} — 판당 {x.get('tur_sum', 0) / x['met_n']:.2f}개 (총 {x.get('tur_sum', 0)}·{x['met_n']}판)")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("tur_sum", 0) > 0]),
            ("💚 평균 힐+실드 (5판↑)", theme.SUCCESS,
             [(x.get("hs_sum", 0) / x["met_n"], f"{_nm(x)} — 판당 {_fmtn(int(x.get('hs_sum', 0) / x['met_n']))} ({x['met_n']}판)")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("hs_sum", 0) > 0]),
            ("👁 평균 와드 설치 (5판↑)", theme.TEAM_BLUE_FG,
             [(x.get("wp_sum", 0) / x["met_n"], f"{_nm(x)} — 판당 {x.get('wp_sum', 0) / x['met_n']:.1f}개 (총 {_fmtn(x.get('wp_sum', 0))})")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("wp_sum", 0) > 0]),
            ("🧹 평균 와드 제거 (5판↑)", theme.SUCCESS,
             [(x.get("wk_sum", 0) / x["met_n"], f"{_nm(x)} — 판당 {x.get('wk_sum', 0) / x['met_n']:.1f}개 (총 {_fmtn(x.get('wk_sum', 0))})")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("wk_sum", 0) > 0]),
            ("🤝 평균 어시스트 (5판↑)", theme.SUCCESS,
             [(x["ta"] / x["kda_n"], f"{_nm(x)} — 판당 {x['ta'] / x['kda_n']:.1f}개 (총 {_fmtn(x['ta'])}·{x['kda_n']}판)")
              for x in rl if x.get("kda_n", 0) >= 5]),
            ("🛡 무데스 경기 비율 (10판↑)", theme.TEAM_BLUE_FG,
             [(x.get("nd_n", 0) / x["kda_n"], f"{_nm(x)} — {x.get('nd_n', 0) / x['kda_n'] * 100:.1f}% ({x.get('nd_n', 0)}판/{x['kda_n']}판)")
              for x in rl if x.get("kda_n", 0) >= 10 and x.get("nd_n", 0) > 0]),
            ("🔥 두 자릿수 킬 비율 (10판↑)", theme.TEAM_RED_FG,
             [(x.get("dk_n", 0) / x["kda_n"], f"{_nm(x)} — {x.get('dk_n', 0) / x['kda_n'] * 100:.1f}% ({x.get('dk_n', 0)}판/{x['kda_n']}판)")
              for x in rl if x.get("kda_n", 0) >= 10 and x.get("dk_n", 0) > 0]),
            ("💪 골드 효율 딜/골드 (5판↑)", theme.GOLD,
             [(x.get("dpm_sum", 0.0) / x["gpm_sum"], f"{_nm(x)} — 골드당 {x.get('dpm_sum', 0.0) / x['gpm_sum']:.2f}딜 ({x['met_n']}판)")
              for x in rl if x.get("met_n", 0) >= 5 and x.get("gpm_sum", 0) > 0]),
        ]
        for idx, (title, color, entries) in enumerate(cards):
            card = tk.Frame(inner, bg=theme.BG_BAR)
            card.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=8, pady=8)
            tk.Label(card, text=f"{title} TOP 10", bg=theme.BG_CARD, fg=color, font=UF(12, "bold"), anchor="w", padx=12, pady=6).pack(fill="x")
            box = tk.Text(card, bg=theme.BG_CARD, fg=theme.TEXT, font=UF(10), bd=0, highlightthickness=0, padx=12, pady=10, height=11)
            top = sorted(entries, key=lambda x: -x[0])[:10]
            if not top:
                box.insert(tk.END, "\n 💤 기록 데이터가 부족합니다.")
            else:
                for i, (_v, line) in enumerate(top):
                    medal = "🥇 " if i == 0 else ("🥈 " if i == 1 else ("🥉 " if i == 2 else f" [{i+1}위] "))
                    box.insert(tk.END, medal + line + "\n")
            box.configure(state="disabled")
            box.pack(fill="both", expand=True)

    def render_data(self):
        try:
            if getattr(self, "records_mode", False):
                self.render_records(); return
            if self.mode == "CLASSIC":
                for k, btn in self.pos_btns.items():
                    if k == self.current_pos: btn.config(bg=theme.WARN, fg=theme.TEXT)
                    else: btn.config(bg=theme.BG_CARD, fg=theme.TEXT_SUB)

            for widget in self.grid_frame.winfo_children(): widget.destroy()
            
            target_key = "hof_classic" if self.mode == "CLASSIC" else "hof_aram"
            with gui_lock:
                g_data_raw = gui_data.get(target_key, {}).get("global_stats", {})
            
            ver_data = g_data_raw.get(self.current_ver, {})
            pos = self.current_pos if self.mode == "CLASSIC" else "ALL"
            
            min_games_wr = 10 if pos == "ALL" else 5
            min_games_eval = 5 if pos == "ALL" else 3
            
            if self.current_ver != "전체 (ALL)":
                min_games_wr = max(3, min_games_wr // 2)
                min_games_eval = max(2, min_games_eval // 2)
            
            data_list = []
            for puuid, s_data in ver_data.items():
                if pos == "ALL":
                    t = s_data["ALL"]["total"]
                    w = s_data["ALL"]["wins"]
                    m = s_data["ALL"]["mvp"]
                    tr = s_data["ALL"]["troll"]
                    et = s_data["ALL"]["eval_total"]
                else:
                    p_stats = s_data.get(pos, {})
                    t = p_stats.get("total", 0)
                    w = p_stats.get("wins", 0)
                    m = p_stats.get("mvp", 0)
                    tr = p_stats.get("troll", 0)
                    et = p_stats.get("eval_total", 0)
                    
                if t == 0: continue
                data_list.append({
                    "name": s_data["name"], "total": t, "wins": w, 
                    "mvp": m, "troll": tr, "eval_total": et,
                    "main_pos": s_data.get("main_pos", {})
                })

            most_games = sorted(data_list, key=lambda x: x['total'], reverse=True)[:10]
            highest_wr = sorted([x for x in data_list if x['total'] >= min_games_wr], key=lambda x: (x['wins']/x['total'], x['total']), reverse=True)[:10]
            highest_mvp = sorted([x for x in data_list if x['eval_total'] >= min_games_eval and x['mvp'] > 0], key=lambda x: (x['mvp']/x['eval_total'], x['mvp']), reverse=True)[:10]
            highest_troll = sorted([x for x in data_list if x['eval_total'] >= min_games_eval and x['troll'] > 0], key=lambda x: (x['troll']/x['eval_total'], x['troll']), reverse=True)[:10]

            def draw_card(row, col, title, lst, stat_type):
                card = tk.Frame(self.grid_frame, bg=theme.BG_BAR, bd=0); card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
                header_bg = theme.BG_CARD if stat_type in ["total", "wr"] else theme.BG_CARD if stat_type == "troll" else theme.BG_CARD
                header_fg = theme.GOLD if stat_type in ["total", "wr"] else theme.TEAM_RED_FG if stat_type == "troll" else theme.GOLD
                
                if self.mode == "ARAM" and stat_type in ["total", "wr"]: header_fg = theme.TEAM_BLUE_FG
                
                lbl_f = tk.Frame(card, bg=header_bg, height=35); lbl_f.pack(fill="x")
                tk.Label(lbl_f, text=title, bg=header_bg, fg=header_fg, font=UF(12, "bold")).pack(anchor="w", padx=12, pady=6)
                box = tk.Text(card, bg=theme.BG_CARD, fg=theme.TEXT, font=UF(10), bd=0, highlightthickness=0, padx=12, pady=12); box.pack(fill="both", expand=True)
                
                if not lst:
                    box.insert(tk.END, f"\n 💤 기준({min_games_wr if stat_type == 'wr' else min_games_eval}판)을 충족하는 유저 데이터가 부족합니다.")
                else:
                    for idx, s in enumerate(lst):
                        name_clean = str(s['name']).split('#')[0]
                        pos_info = ""
                        
                        if pos == "ALL" and self.mode == "CLASSIC":
                            best_p = max(s['main_pos'], key=s['main_pos'].get) if s['main_pos'] else "NONE"
                            pos_info = f"[{POSITION_TRANSLATE_KOR.get(best_p, '선택안함')}] "
                        
                        if stat_type == "wr": metric = f"{round((s['wins'] / s['total']) * 100, 1)}% ({s['wins']}승/{s['total']}전)"
                        elif stat_type == "total": metric = f"{s['total']}판 ({s['wins']}승)"
                        elif stat_type == "mvp": metric = f"{round((s['mvp'] / s['eval_total']) * 100, 1)}% ({s['mvp']}회 / 평가 {s['eval_total']}판)"
                        elif stat_type == "troll": metric = f"{round((s['troll'] / s['eval_total']) * 100, 1)}% ({s['troll']}회 / 평가 {s['eval_total']}판)"
                        
                        medal_str = f" [{idx+1}위] "
                        if idx == 0: medal_str = "🥇 "
                        elif idx == 1: medal_str = "🥈 "
                        elif idx == 2: medal_str = "🥉 "
                        
                        box.insert(tk.END, f"{medal_str}{pos_info}{name_clean} ➡ {metric}\n")
                box.configure(state="disabled")

            pos_kor = "통합" if pos == "ALL" else POSITION_TRANSLATE_KOR.get(pos, "선택안함")
            title_prefix = f"[{pos_kor}] " if self.mode == "CLASSIC" else "[칼바람] "
            patch_txt = f"[{self.current_ver}] " if self.current_ver != "전체 (ALL)" else ""
            
            draw_card(0, 0, f"🎖 {patch_txt}{title_prefix}망령 TOP 10", most_games, "total")
            draw_card(0, 1, f"📈 {patch_txt}{title_prefix}승률왕 TOP 10", highest_wr, "wr")
            draw_card(1, 0, f"👑 {patch_txt}{title_prefix}MVP 획득률 TOP 10", highest_mvp, "mvp")
            draw_card(1, 1, f"💀 {patch_txt}{title_prefix}역적 지목률 TOP 10", highest_troll, "troll")
        except Exception as e: pass

class TierAssessmentWindow(tk.Toplevel):
    TIER_ORDER = ["0","1上","1中","1下","2上","2中","2下","3上","3中","3下"]
    def __init__(self, parent):
        super().__init__(parent)
        self.title("내부티어 평가 (동티어 평균 대비 승률·MVP율·역적율)")
        self.geometry("1120x860")
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        top = tk.Frame(self, bg=theme.BG_BAR, height=58)
        top.pack(fill="x", side="top")
        tk.Label(top, text="🎖 내부티어 평가", bg=theme.BG_BAR, fg=theme.GOLD, font=UF(16, "bold")).pack(side="left", padx=20, pady=14)
        self.btn_refresh = tk.Button(top, text="데이터 갱신", font=UF(10, "bold"), bg=theme.BG_RAISED, fg=theme.TEXT, bd=0, padx=12, pady=4, cursor="hand2", command=self.refresh_action)
        self.btn_refresh.pack(side="right", padx=20, pady=14)
        tk.Label(top, text="기준: 협곡 전체 · 같은 내부티어 평균 대비 (승률×1 + MVP율×0.5 − 역적율×0.5, ±7)   ·   ℹ MVP율 = (MVP + ACE×0.5) / 평가판 — 진팀 ACE도 MVP의 절반으로 합산됩니다",
                 bg=theme.BG_BAR, fg=theme.TEXT_SUB, font=UF(9)).pack(side="right", padx=8)

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=16, pady=10)
        self.canvas = tk.Canvas(body, bg=theme.BG, highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=theme.BG)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw", width=1062)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # HOF 데이터가 아직 없으면(비호스트 지연로드) 자동으로 먼저 로드 후 렌더 → '갱신 눌러주세요' 회피
        with gui_lock: _has_hof = bool(gui_data.get("hof_classic", {}).get("global_stats", {}).get("전체 (ALL)"))
        if _has_hof: self.render_data()
        else: self.refresh_action()

        bot = tk.Frame(self, bg=theme.BG, height=46)
        bot.pack(fill="x", side="bottom")
        tk.Button(bot, text="닫기", font=UF(11, "bold"), bg=theme.BG_RAISED, fg=theme.TEXT, bd=0, width=20, pady=6, cursor="hand2", command=self._close).pack(pady=8)

    def _close(self):
        try: self.canvas.unbind_all("<MouseWheel>")
        except Exception: pass
        self.destroy()

    def refresh_action(self):
        self.btn_refresh.config(text="갱신 중...", state="disabled")
        def worker():
            update_hof_stats(force=True)
            self.after(0, self.render_data)
            self.after(0, lambda: self.btn_refresh.config(text="데이터 갱신", state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def render_data(self):
        try:
            for w in self.inner.winfo_children(): w.destroy()
            assessments, tier_avg = compute_tier_assessment()
            if not assessments:
                tk.Label(self.inner, text="데이터를 불러오는 중입니다. 데이터 갱신을 눌러주세요.",
                         bg=theme.BG, fg=theme.TEXT_SUB, font=UF(12)).pack(pady=50)
                return
            by_tier = {}
            for a in assessments: by_tier.setdefault(a["tier"], []).append(a)
            label_color = {"고평가": theme.LOSE, "저평가": theme.ACCENT, "적절": theme.SUCCESS, "표본부족": theme.TEXT_MUT}
            order_label = {"고평가": 0, "저평가": 1, "적절": 2, "표본부족": 3}

            tk.Label(self.inner, text="🔵저평가 = 클랜 전체 성적이 현 티어보다 2등급↑ 위(승격 후보)   🟢적절 = 티어와 비슷(±0.5티어)   🔴고평가 = 2등급↑ 아래   ·   🎯전체 상위 X% = 클랜 전체 종합실력 순위",
                     bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), anchor="w").pack(fill="x", padx=4, pady=(0, 6))

            for t in self.TIER_ORDER:
                members = by_tier.get(t, [])
                if not members: continue
                avg = tier_avg.get(t, {})
                hdr = tk.Frame(self.inner, bg=theme.BG_BAR)
                hdr.pack(fill="x", pady=(10, 2))
                tk.Label(hdr, text=f"  [{t}]", bg=theme.BG_BAR, fg=theme.GOLD, font=UF(13, "bold")).pack(side="left", padx=(6, 0), pady=5)
                if avg.get("wr") is not None:
                    avg_txt = f"동티어 평균 — 승률 {round(avg['wr'])}%"
                    if avg.get("mvp") is not None: avg_txt += f" · MVP율 {round(avg['mvp'])}%"
                    if avg.get("troll") is not None: avg_txt += f" · 역적율 {round(avg['troll'])}%"
                    avg_txt += f"  ·  표본 {avg.get('n', 0)}명"
                else:
                    avg_txt = "동티어 표본 부족"
                tk.Label(hdr, text=avg_txt, bg=theme.BG_BAR, fg=theme.TEXT_SUB, font=UF(10)).pack(side="left", padx=8, pady=5)

                members.sort(key=lambda x: (order_label.get(x["label"], 9), x.get("implPct", 999)))
                for a in members:
                    row = tk.Frame(self.inner, bg=theme.BG_CARD)
                    row.pack(fill="x", pady=1, padx=2)
                    nm = str(a["name"]).split("#")[0]
                    tk.Label(row, text=nm, bg=theme.BG_CARD, fg=theme.TEXT, font=UF(11, "bold"), width=16, anchor="w").pack(side="left", padx=(10, 4), pady=5)
                    _pos = position_label(a["name"])   # 선언 포지션(디스코드 역할 → CLAN_POSITIONS 시트)
                    if _pos:
                        tk.Label(row, text=f" {_pos} ", bg=theme.BG_RAISED, fg=theme.TEAM_BLUE_FG,
                                 font=UF(9, "bold")).pack(side="left", padx=(0, 4))
                    if a.get("title"):   # 🗡 상현(1~3위) / 🌙 하현(4~6위) 십이귀월 정예 타이틀
                        _isup = "상현" in str(a["title"])
                        tk.Label(row, text=f" {'🗡' if _isup else '🌙'} {a['title']} ",
                                 bg=(theme.TEAM_RED_BG if _isup else theme.BG_RAISED), fg=(theme.GOLD if _isup else theme.TEXT),
                                 font=UF(10, "bold")).pack(side="left", padx=(0, 4))
                    tk.Label(row, text=f" {a['label']} ", bg=theme.BG, fg=label_color.get(a["label"], theme.TEXT), font=UF(10, "bold")).pack(side="left", padx=4)
                    d = a.get("detail")
                    if d:
                        det = (f"🎯 전체 상위 {a['implPct']}%   ·   " if a.get("implPct") is not None else "") + f"승률 {d['wr']}%(동티어 {d.get('wrAvg','—')}%)"
                        if d.get("solo") is not None: det += f"   ·   🏅솔랭 {d['solo']}점" + (f"({d['soloWR']}%)" if d.get('soloWR') is not None else "") + f"(동티어 {d.get('soloAvg','—')})"
                        if d.get("ai") is not None: det += f"   ·   AI {d['ai']}(동티어 {d.get('aiAvg','—')})"
                        if d.get("mvp") is not None: det += f"   ·   MVP율 {d['mvp']}%(동티어 {d.get('mvpAvg','—')}%)"
                        if d.get("troll") is not None: det += f"   ·   역적율 {d['troll']}%(동티어 {d.get('trollAvg','—')}%)"
                        if d.get("ace") is not None: det += f"   ·   ACE율 {d['ace']}%(패배중)"
                    else:
                        det = f"{a['games']}판 — 평가엔 10판 이상 필요"
                    tk.Label(row, text=det, bg=theme.BG_CARD, fg=theme.TEXT_SUB, font=UF(10), anchor="w").pack(side="left", padx=8)
        except Exception as e:
            for w in self.inner.winfo_children(): w.destroy()
            tk.Label(self.inner, text=f"표시 중 오류 — 잠시 후 🔄 갱신을 눌러주세요.\n({e})", bg=theme.BG, fg=theme.TEXT_SUB, font=UF(11)).pack(pady=40)

class PatchNoteWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("패치노트")
        self.geometry("600x450")
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="📜 스쿼드해체분석기 버전별 업데이트 기록", bg=theme.BG_BAR, fg=theme.GOLD, font=UF(16, "bold"), pady=15).pack(fill="x")
        txt = scrolledtext.ScrolledText(self, bg=theme.BG_CARD, fg=theme.TEXT, font=UF(11), padx=15, pady=15, bd=0)
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        
        notes = [
            "[V81.97] 작업표시줄 제목에 버전 표기 복원",
            "- (수정) 작업표시줄/창 제목에 현재 버전([v81.97])을 다시 표시합니다. 내가 켠 게 몇 버전인지 바로 확인돼요. (예전의 'AI 밸런스 패치 및 안정화' 문구는 계속 제외)",
            "",
            "[V81.96] (내부) 시트 장기 안정화 준비 — 사전집계 자동 갱신",
            "- (내부) 시트가 커져도 느려지지 않도록, 호스트 PC가 20분마다 전적을 '요약 표(STAT_CHAMP/STAT_PLAYER)'로 미리 계산해 둡니다. 지금은 요약 표를 만들어두기만 하고(화면 동작 변화 없음), 다음 업데이트부터 대기실·웹이 이 요약을 읽어 빨라집니다.",
            "",
            "[V81.95] 밴픽 화면 시인성 개선 — 불필요한 텍스트 대청소",
            "- (개선) 밴픽 화면을 초상화 위주로 깔끔하게 정리했어요. ①모스트=많이 한 순서로 초상화 5개(판수 텍스트 제거) ②고승률픽(60%↑)=초상화만(승률·판수 제거) ③진영승률·약점발견 문구 제거(→'○○ 밴 당할 시 승률 N% 하락'만) ④10밴 현황 챔피언 이름 텍스트 제거(아이콘만) ⑤작업표시줄 제목 간소화 ⑥하단 시너지/역시너지/상성 조건표기 제거 및 내용 간결화.",
            "",
            "[V81.94] '내 꾸미기' 적용 안 되던 문제 수정",
            "- (수정) '🎨 내 꾸미기'를 눌러도 T1이 안 뜨던 문제를 고쳤어요. 내 칸을 찾는 방식이 대기실 상황에 따라 안 맞던 걸 이름 기준으로 바꿨고, 버튼을 누르면 바로 반영되도록 했습니다.",
            "",
            "[V81.93] 🎨 '내 꾸미기'(시험) — 내 칸에 T1 테마",
            "- (신규) 상단 '🎨 내 꾸미기' 버튼으로 내 칸(밴픽 화면)에 T1 엠블럼+테두리를 입혀볼 수 있어요. 버튼을 누를 때마다 없음→레드→골드→블랙으로 바뀝니다. 지금은 시험 기능이라 '내 화면·내 칸'에만 보이고(공유 안 됨), 설정은 저장됩니다. 대기실/밴픽 화면에서 내 칸에 반영돼요.",
            "",
            "[V81.92] 긴급 롤백 — 대기실 감지 문제 수정",
            "- (수정) v81.91에서 대기실 반영 속도를 최적화하려다 일부 상황에서 대기실 인원 감지가 안 되던 문제가 있었어요. 안정성을 위해 해당 최적화를 되돌렸습니다. 대기실 감지가 정상 동작합니다. (속도 최적화는 안전하게 재작업 후 다시 적용 예정)",
            "",
            "[V81.90] 관전→참가 늦은 합류자 PUUID 누락 방지",
            "- (수정) 밴픽(챔프선택) 때 관전이었다가 게임 시작 직전 참가한 인원은 PUUID가 시트에 빈칸으로 기록되던 문제를 보완했어요. 이제 PUUID를 못 잡으면 그 사람의 과거 시트 기록(소환사명 기준)에서 PUUID를 찾아 채웁니다. 전적 통계가 더 정확하게 합쳐집니다.",
            "",
            "[V81.89] 내부티어 평가 — '적절' 판정 폭 완화(±0.5티어)",
            "- (조정) 클랜 전체 재배치 결과가 현재 티어와 ±1등급(약 0.5티어) 이내면 '적절'로 봅니다. 2등급 이상 벌어질 때만 저평가/고평가로 표시해, 애매한 차이로 과하게 등락 후보가 뜨던 걸 줄였어요. (웹과 동일)",
            "",
            "[V81.88] 내부티어 평가로직 개편 — 클랜 전체 기준",
            "- (변경) 내부티어 고평가/저평가 판정을 '같은 티어끼리 비교'에서 '클랜원 전체를 종합실력 순으로 세운 뒤 실제 티어 분포와 같은 칸 수에 재배치'하는 방식으로 바꿨습니다. 재배치된 추정 티어가 현재 티어보다 위면 저평가(승격 후보), 아래면 고평가, 같으면 적절입니다.",
            "- (표기) 각 클랜원 줄에 '🎯 전체 상위 X%'(클랜 전체 종합실력 순위)를 함께 표시합니다. 표기 라벨(고평가/저평가/적절)은 그대로라 한눈에 보기 편합니다. 스쿼드.gg 웹과 완전히 동일한 로직입니다.",
            "",
            "[V81.2] 칼바람 평가 공정화 (포지션 보정 제거 & 역적 지정 수정)",
            "- (수정) 칼바람에서 역적이 지정되지 않고 MVP만 찍히던 문제 해결. 역적 후보(최저점)의 식별자가 시트와 매칭되지 않아 누락되던 것을, 시트와 매칭되는 최저점 인원으로 정확히 지정하도록 보강했습니다.",
            "- (개선) 칼바람은 포지션이 없으므로 포지션별 데스 페널티 보정을 빼고 5명 전원을 동일 조건으로 평가합니다. (협곡은 기존대로 포지션 보정 유지)",
            "",
            "[V81.1] 칼바람 MVP/역적 기록 수정 & 닉변 통합 보강",
            "- (수정) 칼바람(증내전) 게임의 MVP/역적이 시트에 제대로 기록되지 않던 문제를 해결했습니다. 게임 종료 후 로비로 돌아갈 때 칼바람 판정이 풀려 협곡 시트에 잘못 기록을 시도하던 버그를 바로잡아, 이제 항상 올바른 시트(칼바람=KIWI)에 MVP/역적이 남습니다.",
            "- (개선) 닉네임을 바꾼 클랜원도 PUUID로 전적이 자동 통합되며(명예의전당·랭킹·내부티어평가 공통), 새 닉이 티어표에 없어도 과거 닉으로 내부티어를 자동 복원합니다. (스쿼드.gg 웹과 동일 로직)",
            "",
            "[V81.0] 내부티어 평가 신설 & 스쿼드.gg 연동",
            "- (신규) 상단 '🎖 내부티어 평가' 버튼 추가! 같은 내부티어 인원들의 평균(승률·MVP율·역적율)과 대조해 각 클랜원을 고평가/적절/저평가로 판정합니다. (개인 승률만 보던 방식보다 신뢰도 향상)",
            "- (신규) 스쿼드.gg 웹사이트가 GitHub Pages로 이전되어 더 안정적으로 열립니다. '🌐 스쿼드.gg' 버튼이 새 주소로 연결됩니다.",
            "- (개선) 웹/앱 내부티어 데이터·평가기준을 동일하게 동기화했습니다.",
            "",
            "[V80.9] AI 평가 기준 개선 & 롤 버전 텍스트 오류 해결",
            "- (개선) 원딜의 데스 페널티를 완화(-4.0 -> -3.0점)하여 불합리한 역적 지목 빈도를 낮췄습니다.",
            "- (개선) 유틸형 서포터의 힐/보호막(방어막) 제공량을 MVP 점수(가성비 딜과 동급 가중치)에 반영하여 서포터의 기여도를 공정하게 평가합니다.",
            "- (수정) 구글 시트의 자동 숫자/날짜 변환 버그를 막기 위해 패치 버전을 텍스트 형식(예: v15.4)으로 강제 고정하여 오기록 현상(26.13 등)을 완벽히 해결했습니다.",
            "",
            "[V80.8] 대기실 튕김 시 결과 누락 방어 및 전수조사 패치",
            "- 이제 통계창을 안 보고 로비로 튕기거나 '건너뛰기'를 눌러도 프로그램이 백그라운드에서 전적을 긁어와 결과를 기록합니다.",
            "- 게임 종료 시 내 기록뿐만 아니라, 중복 도배된 모든 대기줄을 전수 조사하여 한 번에 치유/업데이트 합니다.",
        ]
        
        for line in notes:
            if line.startswith("["): txt.insert(tk.END, line + "\n", "title")
            else: txt.insert(tk.END, line + "\n\n" + "-"*50 + "\n\n")
        
        txt.tag_config("title", foreground=theme.TEAM_BLUE_FG, font=UF(12, "bold"))
        txt.configure(state="disabled")

class ClanSettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("환경 설정")
        self.geometry("560x720")   # [v82.37] 모스트 표시 옵션 추가로 확장
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg=theme.BG_BAR, height=55)
        top_bar.pack(fill="x", side="top")
        tk.Label(top_bar, text="⚙ 환경 설정 (SETTINGS)", bg=theme.BG_BAR, fg=theme.GOLD, font=UF(14, "bold")).pack(side="left", padx=20, pady=12)

        # 🐞 [2026-08-12 사장님 제보 '체크를 꺼도 다시 켜져 있다'] 원인은 저장이 아니라 배치였다.
        #   Tk packer 는 순서대로 요청 크기를 나눠 준다. 본문(body_frame)이 먼저 packed 되고 옵션이
        #   늘어 요청 높이가 창을 넘기면, 뒤에 packed 되는 저장 버튼 줄에 남는 공간이 0이 되어
        #   '설정 및 저장' 버튼이 화면 밖으로 밀려난다 → 사장님은 X 로 닫을 수밖에 없고 저장이 안 된다.
        #   ① 저장 줄을 본문보다 먼저 pack 해 항상 자리를 확보하고
        #   ② 본문을 스크롤 가능하게 만들어, 앞으로 옵션이 더 늘어도 같은 사고가 안 나게 한다.
        bot_bar = tk.Frame(self, bg=theme.BG, height=56); bot_bar.pack(fill="x", side="bottom")
        bot_bar.pack_propagate(False)
        tk.Button(bot_bar, text="설정 및 저장", font=UF(11, "bold"), bg=theme.TEAM_RED_BG,
                  fg=theme.TEXT, bd=0, width=20, pady=6, cursor="hand2",
                  command=self.apply_settings).pack(pady=11)

        _scroll_wrap = tk.Frame(self, bg=theme.BG); _scroll_wrap.pack(fill="both", expand=True)
        _cv = tk.Canvas(_scroll_wrap, bg=theme.BG, highlightthickness=0, bd=0)
        _sb = ttk.Scrollbar(_scroll_wrap, orient="vertical", command=_cv.yview)
        _cv.configure(yscrollcommand=_sb.set)
        _sb.pack(side="right", fill="y"); _cv.pack(side="left", fill="both", expand=True)
        body_frame = tk.Frame(_cv, bg=theme.BG)
        _bw = _cv.create_window(0, 0, window=body_frame, anchor="nw")
        body_frame.bind("<Configure>", lambda e: _cv.configure(scrollregion=_cv.bbox("all")))
        _cv.bind("<Configure>", lambda e: _cv.itemconfigure(_bw, width=e.width))
        self.bind("<MouseWheel>", lambda e: _cv.yview_scroll(int(-e.delta / 120), "units"))
        body_frame.configure(padx=25, pady=20)
        
        style = ttk.Style()
        style.configure("TCheckbutton", background=theme.BG, foreground=theme.TEXT, font=UF(10))
        
        self.var_startup = tk.BooleanVar(value=APP_CONFIG.get("windows_startup", False))
        self.var_lol_auto = tk.BooleanVar(value=APP_CONFIG.get("lol_auto_show", True))
        self.var_tray = tk.BooleanVar(value=APP_CONFIG.get("minimize_to_tray", False))
        self.var_posview = tk.BooleanVar(value=APP_CONFIG.get("pos_view_default", True))   # [v82.37]
        self.var_syn = tk.BooleanVar(value=APP_CONFIG.get("show_synergy", True))   # 🧩 우측 시너지 3칸
        
        # 체크박스를 먼저(오른쪽) 배치해 공간을 확보 → 긴 설명이 밀어내지 않음. 설명은 wraplength로 줄바꿈.
        opt_f1 = tk.Frame(body_frame, bg=theme.BG); opt_f1.pack(fill="x", pady=10)
        ttk.Checkbutton(opt_f1, variable=self.var_startup, style="TCheckbutton").pack(side="right", padx=(8, 6))
        txt_f1 = tk.Frame(opt_f1, bg=theme.BG); txt_f1.pack(side="left", fill="both", expand=True)
        tk.Label(txt_f1, text="컴퓨터 부팅 시 스텔스(숨김) 자동 실행", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_f1, text="백그라운드에 숨어 대기하며 리소스를 최소화합니다.", bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=430, justify="left").pack(anchor="w", pady=4)
        # 🔎 [2026-08-12] 체크박스는 '내 의도'일 뿐이고 실제로 등록됐는지는 별개다 — 진짜 상태를 그대로 보여준다
        _reg = startup_registered()
        _same = (_reg == startup_cmdline())
        tk.Label(txt_f1,
                 text=("✅ 현재 등록됨" if _same else (f"⚠️ 등록값이 지금 실행 파일과 다릅니다 — {_reg}" if _reg else "⛔ 현재 등록 안 됨")),
                 bg=theme.BG, fg=("#5ad48a" if _same else ("#ffb347" if _reg else "#ff8a8a")),
                 font=UF(9), wraplength=430, justify="left").pack(anchor="w")

        opt_f2 = tk.Frame(body_frame, bg=theme.BG); opt_f2.pack(fill="x", pady=10)
        ttk.Checkbutton(opt_f2, variable=self.var_lol_auto, style="TCheckbutton").pack(side="right", padx=(8, 6))
        txt_f2 = tk.Frame(opt_f2, bg=theme.BG); txt_f2.pack(side="left", fill="both", expand=True)
        tk.Label(txt_f2, text="롤 클라이언트 켜질 때 자동 팝업", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_f2, text="이미 실행 중인(숨겨진) 분석기를 화면에 띄웁니다. 분석기가 아예 꺼져 있으면 "
                             "롤을 켜도 아무 일도 일어나지 않아요 — 위의 '부팅 시 자동 실행'을 함께 켜 주세요.",
                 bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=430, justify="left").pack(anchor="w", pady=4)

        opt_f3 = tk.Frame(body_frame, bg=theme.BG); opt_f3.pack(fill="x", pady=10)
        ttk.Checkbutton(opt_f3, variable=self.var_tray, style="TCheckbutton").pack(side="right", padx=(8, 6))
        txt_f3 = tk.Frame(opt_f3, bg=theme.BG); txt_f3.pack(side="left", fill="both", expand=True)
        tk.Label(txt_f3, text="닫기(X) 시 트레이로 최소화", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_f3, text="끄면(기본) X로 완전 종료 · 켜면 트레이에서 백그라운드 실행 (재시작 후 적용)", bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=430, justify="left").pack(anchor="w", pady=4)

        # 🧩 [2026-08-12 사장님 지시] 우측 시너지 3칸 접기 — 끄면 두 팀 칸이 그만큼 넓어진다
        opt_sy = tk.Frame(body_frame, bg=theme.BG); opt_sy.pack(fill="x", pady=10)
        ttk.Checkbutton(opt_sy, variable=self.var_syn, style="TCheckbutton").pack(side="right", padx=(8, 6))
        txt_sy = tk.Frame(opt_sy, bg=theme.BG); txt_sy.pack(side="left", fill="both", expand=True)
        tk.Label(txt_sy, text="우측 시너지 3칸 표시", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_sy, text="고승률 시너지·역시너지 경보·천적 관계 칸입니다. 끄면 그 열이 사라지고 "
                             "블루/레드 팀 칸이 넓어져 더 컴팩트하게 씁니다. (저장 즉시 적용)",
                 bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=430, justify="left").pack(anchor="w", pady=4)

        # 🎯 [v82.37] 대기실 모스트 표시 기본값 — 켜면 '현재포지션', 끄면 '전체라인'으로 시작
        opt_pv = tk.Frame(body_frame, bg=theme.BG); opt_pv.pack(fill="x", pady=10)
        ttk.Checkbutton(opt_pv, variable=self.var_posview, style="TCheckbutton").pack(side="right", padx=(8, 6))
        txt_pv = tk.Frame(opt_pv, bg=theme.BG); txt_pv.pack(side="left", fill="both", expand=True)
        tk.Label(txt_pv, text="대기실 모스트를 '현재 포지션' 기준으로 표시", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_pv, text="켜면 각자 선택한 포지션의 모스트·고승률픽만, 끄면 전체 라인 기준으로 보여줍니다. (상단 버튼으로 언제든 전환 가능)",
                 bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=430, justify="left").pack(anchor="w", pady=4)

        # 🖥 [v82.17] 창 크기 프리셋 — 선택 즉시(저장 시) 적용, 재시작 후에도 유지
        opt_f4 = tk.Frame(body_frame, bg=theme.BG); opt_f4.pack(fill="x", pady=10)
        _cur_key = APP_CONFIG.get("win_preset", "auto")
        _cur_label = next((lb for k, lb in WIN_PRESET_CHOICES if k == _cur_key), WIN_PRESET_CHOICES[0][1])
        self.var_preset = tk.StringVar(value=_cur_label)
        cb_preset = ttk.Combobox(opt_f4, textvariable=self.var_preset, state="readonly", width=18,
                                 values=[lb for _k, lb in WIN_PRESET_CHOICES], font=UF(10))
        cb_preset.pack(side="right", padx=(8, 6))
        txt_f4 = tk.Frame(opt_f4, bg=theme.BG); txt_f4.pack(side="left", fill="both", expand=True)
        tk.Label(txt_f4, text="창 크기 프리셋", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_f4, text="화면·취향에 맞는 창 크기를 고르세요. 저장 즉시 적용되며 다음 실행에도 유지됩니다.", bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=380, justify="left").pack(anchor="w", pady=4)

        # 🧠 [v82.33] 고스트밴픽왕 구독 토큰 — 호스트(키 보유)는 비워도 됨. 구독자는 디스코드 /구독 토큰 붙여넣기.
        opt_f5 = tk.Frame(body_frame, bg=theme.BG); opt_f5.pack(fill="x", pady=10)
        txt_f5 = tk.Frame(opt_f5, bg=theme.BG); txt_f5.pack(side="left", fill="both", expand=True)
        tk.Label(txt_f5, text="🧠 고스트밴픽왕 구독 토큰", bg=theme.BG, fg=theme.TEXT, font=UF(12, "bold")).pack(anchor="w")
        tk.Label(txt_f5, text="디스코드에서 /구독 으로 받은 토큰을 붙여넣으세요. 내 밴/픽 차례에 AI 추천이 뜹니다.", bg=theme.BG, fg=theme.TEXT_SUB, font=UF(10), wraplength=500, justify="left").pack(anchor="w", pady=4)
        self.var_coach = tk.StringVar(value=APP_CONFIG.get("coach_token", ""))
        tk.Entry(txt_f5, textvariable=self.var_coach, font=UF(11, family="Consolas"), width=46,
                 bg=theme.BG_RAISED, fg=theme.TEXT, insertbackground=theme.TEXT, relief="flat").pack(anchor="w", pady=(4, 0), ipady=3)


    def apply_settings(self):
        val_start = self.var_startup.get()
        val_auto = self.var_lol_auto.get()
        val_tray = self.var_tray.get()
        _tray_changed = (bool(APP_CONFIG.get("minimize_to_tray", False)) != bool(val_tray))
        APP_CONFIG["windows_startup"] = val_start
        APP_CONFIG["lol_auto_show"] = val_auto
        APP_CONFIG["minimize_to_tray"] = val_tray
        # 🖥 [v82.17] 창 크기 프리셋 저장 + 즉시 적용
        _sel_label = self.var_preset.get()
        _sel_key = next((k for k, lb in WIN_PRESET_CHOICES if lb == _sel_label), "auto")
        APP_CONFIG["win_preset"] = _sel_key
        APP_CONFIG["coach_token"] = self.var_coach.get().strip()   # 🧠 [v82.33] 구독 토큰
        # 🎯 [v82.37] 모스트 표시 기본값 — 저장 즉시 화면·버튼에 반영(재시작 기다릴 필요 없게)
        _pv = bool(self.var_posview.get())
        APP_CONFIG["pos_view_default"] = _pv
        APP_CONFIG["show_synergy"] = bool(self.var_syn.get())   # 🧩 우측 시너지 3칸
        try:
            if _SYNERGY_SYNC[0]: _SYNERGY_SYNC[0](APP_CONFIG["show_synergy"])   # 재시작 없이 즉시 반영
        except Exception: pass
        try:
            with gui_lock: gui_data["pos_view_mode"] = _pv
            _posview_btn_sync(_pv)
        except Exception: pass
        APP_CONFIG.pop("win_last", None)   # [v82.18] 프리셋을 고르면 '마지막 크기 기억'보다 우선 적용되도록 초기화
        try:
            _root = self.master
            _sw, _sh = _root.winfo_screenwidth(), _root.winfo_screenheight()
            if _sel_key in WIN_PRESETS:
                _pw, _ph = WIN_PRESETS[_sel_key]
                _root.state('normal')
                _root.geometry(f"{min(_pw, int(_sw*0.95))}x{min(_ph, int(_sh*0.95))}")
            elif _sel_key == "max":
                _root.state('zoomed')
            else:   # auto = 화면 맞춤(기존 동작)
                _root.state('normal')
                _root.geometry(f"{min(1560, int(_sw*0.95))}x{min(1150, int(_sh*0.95))}")
                if _sh <= 1080: _root.state('zoomed')
        except Exception: pass
        save_config(APP_CONFIG)
        _ok, _detail = toggle_windows_startup(val_start)
        self.destroy()
        if not _ok:
            messagebox.showwarning("자동 실행 등록 실패",
                                   "부팅 시 자동 실행을 " + ("등록" if val_start else "해제") + "하지 못했습니다.\n\n"
                                   + _detail + "\n\n백신·보안 프로그램이 시작프로그램 등록을 막는 경우가 많습니다. "
                                   "예외로 등록하거나, 시작프로그램 폴더에 바로가기를 직접 넣어 주세요.")
        elif val_auto and not val_start:
            messagebox.showinfo("확인해 주세요",
                                "'롤 켜질 때 자동 팝업'만 켜져 있습니다.\n\n"
                                "이 기능은 이미 실행 중인 분석기를 화면에 띄우는 것이라, 분석기가 꺼져 있으면 "
                                "롤을 켜도 아무 일도 일어나지 않습니다.\n"
                                "롤을 켤 때 분석기가 저절로 뜨게 하려면 '부팅 시 자동 실행'도 함께 켜 주세요.")
        if _tray_changed:
            messagebox.showinfo("환경 설정", "트레이 최소화 설정은 프로그램을 재시작하면 적용됩니다.")

class GuideWindow(tk.Toplevel):
    """📖 사용 안내 — [2026-08-12 정리] v81 시절 문구가 그대로 남아 실제와 어긋나 있었다.
       (없어진 '🤖 AI 밸런서' 버튼 안내, 부캐를 시트에 손으로 등록하라는 안내 등)
       지금 실제로 도는 기능만 적는다. 기능이 바뀌면 여기와 웹 소개(analyzer.html)를 같이 고칠 것."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("사용 안내")
        self.geometry("640x620")
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.create_widgets()

    GUIDE = [
        ("자동으로 도는 것", None),
        ("🎖 대기실·밴픽창 정보", "양 팀 10명 칸에 내부티어·내전 전적·모스트 챔피언과 그 포지션 고승률픽이 뜹니다."),
        ("🎯 저격 밴 추천", "상대가 실제로 자주 꺼내고 잘하는 챔피언을 클랜 내전 기록에서 찾아 올립니다. "
                          "승률만이 아니라 그 자리에서 몇 번 꺼냈는지(점유율)까지 봅니다."),
        ("⚔ 시너지·천적 경보", "우측 3칸 — 고승률 시너지 / 같이 서면 지는 역시너지 / 나에게 유독 강한 천적. "
                             "설정에서 끄면 두 팀 칸이 넓어집니다."),
        ("🖥 로딩 화면 오버레이", "로딩 중 10명의 티어·전적을 한 장으로 띄웁니다. 내전에서만 뜨고 솔랭·일반게임엔 안 뜹니다."),
        ("📝 전적 자동 기록", "경기가 끝나면 챔피언·KDA·아이템·룬·CS 까지 구글 시트에 쌓입니다. "
                            "그 판에 한 명만 켜져 있어도 기록됩니다."),
        ("👑 디스코드 결과 리포트", "종료 시 결과·MVP·역적·밴 목록이 디스코드에 자동으로 올라갑니다."),
        ("🔗 닉변·부계 통합", "이름을 바꿔도 PUUID 로 같은 사람으로 묶습니다. 따로 등록하지 않아도 됩니다."),
        ("🚫 노밴 선언 감지", "로비 채팅의 '○○ 노밴' 약속을 읽어 기록하고, 1페이즈 밴 추천에서 제외합니다."),
        ("🔄 자동 업데이트", "새 버전이 나오면 켜져 있는 동안 알아서 받아 교체하고 다시 켭니다."),
        ("직접 누르는 것", None),
        ("☰ 서랍 메뉴", "제목 옆 ☰ — 명예의전당·내부티어·SQUAD.GG·설정·로그·후원 등이 들어 있습니다. "
                      "화면 아무 데나 누르면 닫힙니다."),
        ("👑 팀뽑선정", "방에 있는 사람 중 전력이 가장 비슷한 2인을 팀장으로 뽑습니다(직전 판 팀장은 회피). "
                      "결과를 로비 채팅에 바로 알릴 수 있습니다."),
        ("🎯 모스트 표시 전환", "모스트를 '현재 선택한 포지션' 기준으로 볼지 '전체 라인' 기준으로 볼지 바꿉니다."),
        ("⚙ 설정", "부팅 시 자동 실행(숨김) · 롤 켜질 때 자동 팝업 · 트레이 최소화 · 시너지 3칸 표시 · "
                  "창 크기 · 고스트밴픽왕 구독 토큰. 바꾼 뒤 반드시 [설정 및 저장]을 눌러야 적용됩니다."),
        ("알아두면 좋은 것", None),
        ("🧠 고스트밴픽왕", "밴·픽 차례에 AI 추천을 받는 구독 기능입니다. 구독 안 해도 나머지는 전부 무료입니다."),
        ("🩹 누락된 판", "아무도 분석기를 안 켠 판은 기록이 비어 있습니다. 디스코드 누락경기 채널에 "
                       "deeplol 주소를 올리면 봇이 채워 넣고 판당 포인트도 지급합니다."),
        ("🔐 계정 정보", "아이디·비밀번호는 묻지도, 알 수도 없습니다. 롤 클라이언트가 자기 PC 안에 열어 둔 "
                       "공식 통로로 화면에 이미 보이는 정보만 읽습니다."),
    ]

    def create_widgets(self):
        tk.Label(self, text="📖 스쿼드해체분석기 사용 안내", bg=theme.BG_BAR, fg=theme.GOLD,
                 font=UF(16, "bold"), pady=15).pack(fill="x")
        txt = scrolledtext.ScrolledText(self, bg=theme.BG_CARD, fg=theme.TEXT,
                                        font=UF(11), padx=22, pady=18, bd=0,
                                        highlightthickness=0, wrap="word", spacing3=4)
        txt.pack(fill="both", expand=True)
        txt.tag_configure("sec", foreground=theme.GOLD, font=UF(11, "bold"),
                          spacing1=14, spacing3=6)
        txt.tag_configure("h", foreground=theme.TEXT, font=UF(11, "bold"), spacing1=8)
        txt.tag_configure("b", foreground=theme.TEXT_SUB, font=UF(10),
                          lmargin1=14, lmargin2=14, spacing3=6)
        for head, body in self.GUIDE:
            if body is None:
                txt.insert(tk.END, f"── {head} ──\n", "sec")
            else:
                txt.insert(tk.END, head + "\n", "h")
                txt.insert(tk.END, body + "\n", "b")
        txt.insert(tk.END, f"\n버전 v{CURRENT_VERSION} · 자세한 소개는 SQUAD.GG 웹의 "
                           "'스쿼드해체분석기' 페이지에서도 볼 수 있어요.\n", "b")
        txt.configure(state="disabled")

class OnlineUsersWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("실시간 접속자")
        self.geometry("450x450")
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg=theme.BG_BAR, height=50)
        top_bar.pack(fill="x", side="top")
        tk.Label(top_bar, text="👥 실시간 접속자 현황", bg=theme.BG_BAR, fg=theme.SUCCESS, font=UF(14, "bold")).pack(side="left", padx=20, pady=10)
        self.list_box = scrolledtext.ScrolledText(self, bg=theme.BG_CARD, fg=theme.TEXT, font=UF(11), bd=0, highlightthickness=0, padx=15, pady=15)
        self.list_box.pack(fill="both", expand=True, padx=20, pady=20)
        self.list_box.insert(tk.END, "📡 통신 중... 데이터를 불러옵니다.")
        self.list_box.configure(state="disabled")
        threading.Thread(target=self.fetch_users, daemon=True).start()

    def fetch_users(self):
        global global_spreadsheet
        if not global_spreadsheet: self.update_list(["❌ 시트 연결이 되지 않았습니다."]); return
        try:
            on_sheet = global_spreadsheet.worksheet("ONLINE_USERS")
            records = get_sheet_data_cached(on_sheet)
            active_users, current_time = [], int(time.time())
            
            if len(records) > 1:
                headers = records[0]
                time_col = headers.index("마지막접속시간") if "마지막접속시간" in headers else 2
                usage_col = headers.index("누적사용시간(분)") if "누적사용시간(분)" in headers else 3
                
                for row in records[1:]:
                    if len(row) > time_col:
                        try:
                            last_time_str = str(row[time_col])
                            if last_time_str.isdigit():
                                last_t = int(last_time_str)
                            else:
                                last_t = int(time.mktime(time.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")))
                                
                            if current_time - last_t <= 300:
                                min_c = row[usage_col] if len(row) > usage_col else "0"
                                
                                hours = int(min_c) // 60 if str(min_c).isdigit() else 0
                                mins = int(min_c) % 60 if str(min_c).isdigit() else 0
                                time_str = f"{hours}시간 {mins}분" if hours > 0 else f"{mins}분"
                                
                                active_users.append(f"🟢 {row[0]}\n   ↪ 누적 접속: {time_str}")
                        except Exception: pass
            self.update_list(active_users if active_users else ["💤 현재 접속 중인 다른 유저가 없습니다."])
        except Exception: self.update_list(["❌ 접속자 정보를 불러오지 못했습니다."])

    def update_list(self, items):
        self.list_box.configure(state="normal")
        self.list_box.delete("1.0", tk.END)
        for item in items: self.list_box.insert(tk.END, str(item) + "\n\n")
        self.list_box.configure(state="disabled")

if __name__ == "__main__":
    _start_file_log()          # 🗒️ 실행 폴더 analyzer_log.txt 에 기록 남기기(창 모드라 콘솔이 없음)
    # 🔥 단일 인스턴스 잠금 — 중복 실행 차단(실행횟수가 인스턴스마다 중복 누적되던 문제 해결)
    try:
        import ctypes
        _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _k32.CreateMutexW(None, False, "Global\\SquadAnalyzer_SingleInstance")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS (이미 실행 중일 때만)
            sys.exit(0)
    except Exception:
        pass

    if APP_CONFIG.get("windows_startup"):
        # 설치 위치를 옮기거나 재설치하면 등록된 경로가 옛 경로로 남아 조용히 실패한다 — 매 시작 시 맞춘다
        _cur = startup_registered()
        if _cur != startup_cmdline():
            print(f"[startup] 등록값 불일치 — 재등록합니다 (이전: {_cur})", flush=True)
        toggle_windows_startup(True)
    else:
        _cur = startup_registered()
        if _cur: print(f"[startup] 설정은 꺼져 있는데 레지스트리에 남아 있음 — 정리 {_cur}", flush=True); toggle_windows_startup(False)
        
    threading.Thread(target=auto_updater_engine, daemon=True).start()
    threading.Thread(target=announce_patch_if_updated, daemon=True).start()   # 신버전 패치노트 웹훅 알림(호스트 1회)
    threading.Thread(target=solo_rank_engine, daemon=True).start()            # 솔랭 갱신(riot_key 있을 때만, 12h)
    threading.Thread(target=backfill_result_engine, daemon=True).start()      # 🛠️ '결과 대기' 백필(호스트·Match-V5, 15분) [v81.62]
    threading.Thread(target=peak_missing_engine, daemon=True).start()         # 📋 PEAK_SEASONS 누락 알림(호스트·6h) [2026-07-16]

    # 🧠 [v81.75] 고스트밴픽왕 키 인식 여부를 켤 때 1회 알림 — '키 넣었는데 왜 안 뜨지?'를 바로 진단(키 없으면 조용, 타 클랜원 무해)
    def _draft_key_probe():
        time.sleep(6)
        try:
            if load_claude_key():
                with gui_lock:
                    gui_data["draft_advice"] = "✅ 고스트밴픽왕 준비 완료\nAPI 키를 인식했어요. 내 픽 차례에 추천이 뜹니다."
                    gui_data["draft_advice_ts"] = time.time()
                print("[draft] 키 인식됨 — 고스트밴픽왕 활성", flush=True)
            elif _coach_token():   # [v82.33] 구독자 — 토큰 인식
                with gui_lock:
                    gui_data["draft_advice"] = "✅ 고스트밴픽왕 구독 활성\n구독 토큰을 인식했어요. 내 밴/픽 차례에 추천이 뜹니다."
                    gui_data["draft_advice_ts"] = time.time()
                print("[draft] 구독 토큰 인식됨 — 고스트밴픽왕 활성", flush=True)
        except Exception: pass
    threading.Thread(target=_draft_key_probe, daemon=True).start()
    threading.Thread(target=lcu_core_backend_loop, daemon=True).start()
    threading.Thread(target=_lobby_invite_poll_loop, daemon=True).start()     # 🎮 팀초대→롤 로비 자동초대
    threading.Thread(target=_prediction_mirror_loop, daemon=True).start()     # 🎲 승부예측 전적 미러(호스트만 → PREDICTIONS 시트)
    threading.Thread(target=_career_mirror_loop, daemon=True).start()         # 🏆 커리어(우승 기록) 미러(호스트만 → CAREER 시트)
    threading.Thread(target=_version_heartbeat_loop, daemon=True).start()     # 🩺 버전 하트비트(전 인스턴스 → VERSIONS 시트)
    threading.Thread(target=_tier_role_sync_loop, daemon=True).start()        # 🎖 디스코드 티어역할 → CLAN_TIERS 신규 추가(호스트만)
    threading.Thread(target=_position_sync_loop, daemon=True).start()         # 🎯 디스코드 포지션역할 → CLAN_POSITIONS 재작성(호스트만, 1h)
    threading.Thread(target=_cosmetics_loop, daemon=True).start()             # 🖼️ 상점 장식(모든 PC) → 밴픽 '내 칸' 꾸미기
    threading.Thread(target=_spellcheck_hotkey_loop, daemon=True).start()    # 🕵️ 스펠체크 헬퍼(사장님 계정 전용·비공개)
    threading.Thread(target=ad_banner_engine, daemon=True).start()
    
    create_graphic_ui()