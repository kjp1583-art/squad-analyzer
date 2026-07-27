import os
import sys
import base64
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
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
import ctypes

try:
    from PIL import Image, ImageTk
    PILLOW_INSTALLED = True
except ImportError:
    PILLOW_INSTALLED = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================================
# 📡 [스쿼드 해체 분석기 V80.1 마스터 빌드 - 밴 기록 버그픽스 & KDA 추가]
# =========================================================================
CURRENT_VERSION = "80.1"
VERSION_URL = "https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/refs/heads/main/version.txt"
EXE_URL = "https://github.com/kjp1583-art/squad-analyzer/releases/latest/download/squad_analyzer.exe"
DISCORD_WEBHOOK_URL = "여기에_디스코드_웹훅_URL을_붙여넣으세요"
DOCUMENT_ID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU'
LOL_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LOL_PATH, "lockfile")

CONFIG_DIR = os.path.join(os.environ.get('APPDATA', ''), 'SquadAnalyzer')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

gui_lock = threading.Lock()
sheet_cache_lock = threading.Lock()

global_sheet_cache = {}
global_cache_time = {}
CACHE_TTL = 60

def get_sheet_data_cached(sheet_obj, force=False):
    now = time.time()
    title = sheet_obj.title
    with sheet_cache_lock:
        if force or title not in global_sheet_cache or (now - global_cache_time.get(title, 0) > CACHE_TTL):
            try:
                data = sheet_obj.get_all_values()
                global_sheet_cache[title] = data
                global_cache_time[title] = now
                return data
            except Exception:
                return global_sheet_cache.get(title, [])
        return global_sheet_cache.get(title, [])

def invalidate_sheet_cache(title):
    with sheet_cache_lock:
        global_cache_time[title] = 0

def load_config():
    default_cfg = {"windows_startup": False, "lol_auto_show": False}
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

DDRAGON_VERSION = "14.22.1"
PATCH_VERSION_SHORT = "14.22"
try:
    ver_req = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=3)
    if ver_req.status_code == 200: 
        DDRAGON_VERSION = ver_req.json()[0]
        PATCH_VERSION_SHORT = ".".join(DDRAGON_VERSION.split(".")[:2]) if "." in DDRAGON_VERSION else DDRAGON_VERSION
except Exception: pass

POSITION_TRANSLATE_KOR = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서폿", "NONE": "선택안함"}
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER", "UNRANKED"]

CHAMP_KOR_TO_ENG = {
    "가렌": "Garen", "갈리오": "Galio", "갱플랭크": "Gangplank", "그라가스": "Gragas", "그레이브즈": "Graves",
    "그웬": "Gwen", "나르": "Gnar", "나미": "Nami", "나서스": "Nasus", "노틸러스": "Nautilus",
    "녹턴": "Nocturne", "누누": "Nunu", "누누와 윌럼프": "Nunu", "니달리": "Nidalee", "니코": "Neeko",
    "닐라": "Nilah", "다리우스": "Darius", "다이애나": "Diana", "드레이븐": "Draven", "라이즈": "Ryze",
    "라칸": "Rakan", "람머스": "Rammus", "럭스": "Lux", "럼블": "Rumble", "레나타": "Renata",
    "레나타 글라스크": "Renata", "레넥톤": "Renekton", "레오나": "Leona", "렉사이": "RekSai",
    "렐": "Rell", "렝가": "Rengar", "루시안": "Lucian", "룰루": "Lulu", "르블랑": "LeBlanc",
    "리 신": "LeeSin", "리신": "LeeSin", "리븐": "Riven", "리산드라": "Lissandra", "릴리아": "Lillia",
    "마스터 이": "MasterYi", "마스터이": "MasterYi", "마오카이": "Maokai", "말자하": "Malzahar", "말파이트": "Malphite",
    "모데카이저": "Mordekaiser", "모르가나": "Morgana", "밀리오": "Milio", "바드": "Bard", "바루스": "Varus",
    "바이": "Vi", "베이가": "Veigar", "베인": "Vayne", "벨베스": "Belveth", "벨코즈": "Velkoz",
    "볼리베어": "Volibear", "브라움": "Braum", "브라이어": "Briar", "브랜드": "Brand", "블라디미르": "Vladimir",
    "블리츠크랭크": "Blitzcrank", "빅토르": "Viktor", "뽀삐": "Poppy", "사미라": "Samira", "사이온": "Sion",
    "사일러스": "Sylas", "샤코": "Shaco", "세나": "Senna", "세라핀": "Seraphine", "세주아니": "Sejuani",
    "세트": "Sett", "소나": "Sona", "소라카": "Soraka", "쉔": "Shen", "쉬바나": "Shyvana",
    "스웨인": "Swain", "스카너": "Skarner", "스몰더": "Smolder", "시비르": "Sivir", "신 짜오": "XinZhao",
    "신짜오": "XinZhao", "신드라": "Syndra", "신지드": "Singed", "쓰레쉬": "Thresh", "아리": "Ahri",
    "아무무": "Amumu", "아우렐리온 솔": "AurelionSol", "아우렐리온솔": "AurelionSol", "아이번": "Ivern",
    "아지르": "Azir", "아칼리": "Akali", "아크샨": "Akshan", "아트록스": "Aatrox", "아펠리오스": "Aphelios",
    "알리스타": "Alistar", "애니": "Annie", "애니비아": "Anivia", "애쉬": "Ashe", "야스오": "Yasuo",
    "에코": "Ekko", "엘리스": "Elise", "오공": "MonkeyKing", "오른": "Ornn", "오리아나": "Orianna",
    "오로라": "Aurora", "올라프": "Olaf", "요네": "Yone", "요릭": "Yorick", "우디르": "Udyr", "우르곳": "Urgot",
    "워윅": "Warwick", "유미": "Yuumi", "이렐리아": "Irelia", "이브린": "Evelynn", "이블린": "Evelynn", "이즈리얼": "Ezreal",
    "일라오이": "Illaoi", "자르반 4세": "JarvanIV", "자르반4세": "JarvanIV", "자야": "Xayah", "자이라": "Zyra",
    "자크": "Zac", "잔나": "Janna", "잭스": "Jax", "제드": "Zed", "제라스": "Xerath",
    "제리": "Zeri", "제이스": "Jayce", "조이": "Zoe", "직스": "Ziggs", "진": "Jhin",
    "질리언": "Zilean", "징크스": "Jinx", "초가스": "Chogath", "카르마": "Karma", "카밀": "Camille",
    "카사딘": "Kassadin", "카서스": "Karthus", "카시오페아": "Cassiopeia", "카이사": "Kaisa", "카직스": "Khazix",
    "카타리나": "Katarina", "칼리스타": "Kalista", "케넨": "Kennen", "케이틀린": "Caitlyn", "케인": "Kayn",
    "케일": "Kayle", "코그모": "KogMaw", "코르키": "Corki", "퀸": "Quinn", "크산테": "KSante",
    "클레드": "Kled", "키아나": "Qiyana", "킨드레드": "Kindred", "타릭": "Taric", "탈론": "Talon",
    "탈리야": "Taliyah", "탐 켄치": "TahmKench", "탐켄치": "TahmKench", "트런들": "Trundle",
    "트리스타나": "Tristana", "트린다미어": "Tryndamere", "트위스티드 페이트": "TwistedFate", "트위스티드페이트": "TwistedFate",
    "트위치": "Twitch", "티모": "Teemo", "판테온": "Pantheon", "파이크": "Pyke", "피들스틱": "Fiddlesticks",
    "피오라": "Fiora", "피즈": "Fizz", "하이머딩거": "Heimerdinger", "헤카림": "Hecarim", "흐웨이": "Hwei", "암베사": "Ambessa",
    "나피리": "Naafiri", "비에고": "Viego", "벡스": "Vex", "멜": "Mel", "문도 박사": "DrMundo", "문도박사": "DrMundo",
    "문도": "DrMundo", "미스 포츈": "MissFortune", "미스포츈": "MissFortune", "미스포춘": "MissFortune", "트페": "TwistedFate"
}

try:
    champ_json_url = f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/data/ko_KR/champion.json"
    c_req = requests.get(champ_json_url, timeout=3)
    if c_req.status_code == 200:
        c_data = c_req.json().get("data", {})
        for eng_name, c_info in c_data.items():
            kor_name = c_info.get("name", "")
            if kor_name and eng_name:
                CHAMP_KOR_TO_ENG[kor_name] = eng_name
                CHAMP_KOR_TO_ENG[kor_name.replace(" ", "")] = eng_name
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
champion_image_cache = {}
global_champ_map = {}
global_spreadsheet = None
global_alt_map = {}

frozen_bans_str = ""
global_ingame_names = {}
global_puuid_fallback_map = {}

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
    button_widget.config(text="✅", fg="#2ecc71")
    window_root.after(1000, lambda: button_widget.config(text="📋", fg="#ffffff"))

def open_opgg_profile(full_name):
    if not full_name or full_name in ["Wait...", "대기 중...", "알 수 없는 유저"]: return
    clean_name = full_name.replace("🤖 ", "").replace(" 봇", "").strip()
    if "#" in clean_name:
        name_part, tag_part = clean_name.split("#", 1)
        url = "https://www.op.gg/summoners/kr/" + name_part + "-" + tag_part
    else: url = "https://www.op.gg/summoners/kr/" + clean_name
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

def broadcast_to_discord_webhook(content_text):
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL.startswith("여기에"): return
    def txt_thread():
        try:
            msg_lines = []
            msg_lines.append("🏆 **[스쿼드 내전 매치 결과 리포트]** 🏆")
            msg_lines.append("```md")
            msg_lines.append(str(content_text))
            msg_lines.append("```")
            msg_lines.append(f"*정찰 시스템 V{CURRENT_VERSION} 자동 인증*")
            requests.post(DISCORD_WEBHOOK_URL, json={"content": chr(10).join(msg_lines)}, timeout=5)
        except Exception: pass
    threading.Thread(target=txt_thread, daemon=True).start()

def toggle_windows_startup(enabled):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            exe_path = os.path.abspath(sys.argv[0]) if getattr(sys, 'frozen', False) else sys.executable
            winreg.SetValueEx(key, "SquadAnalyzer", 0, winreg.REG_SZ, f'"{exe_path}" --stealth')
        else:
            try: winreg.DeleteValue(key, "SquadAnalyzer")
            except Exception: pass
        winreg.CloseKey(key)
    except Exception: pass

def check_windows_startup_status():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, "SquadAnalyzer")
            winreg.CloseKey(key)
            return True
        except Exception:
            winreg.CloseKey(key)
            return False
    except Exception: return False

def process_monitor_loop():
    while True:
        try:
            output = subprocess.check_output('tasklist /FI "IMAGENAME eq LeagueClient.exe"', shell=True).decode('cp949', errors='ignore')
            if "LeagueClient.exe" in output: pass 
        except Exception: pass
        time.sleep(10)

def auto_updater_engine():
    if not getattr(sys, 'frozen', False): return
    try:
        v_res = requests.get(VERSION_URL, timeout=5)
        if v_res.status_code == 200:
            latest_version = v_res.text.strip()
            if latest_version != CURRENT_VERSION:
                exe_res = requests.get(EXE_URL, timeout=60)
                if exe_res.status_code == 200:
                    cur_exe = sys.executable
                    temp_exe = os.path.join(os.path.dirname(cur_exe), "update_temp.exe")
                    with open(temp_exe, "wb") as f: f.write(exe_res.content)
                    
                    bat_path = os.path.join(os.path.dirname(cur_exe), "updater.bat")
                    cmd_lines = []
                    cmd_lines.append("@echo off")
                    cmd_lines.append("timeout /t 2 /nobreak > nul")
                    cmd_lines.append('del "' + cur_exe + '"')
                    cmd_lines.append('rename "' + temp_exe + '" "' + os.path.basename(cur_exe) + '"')
                    cmd_lines.append('start "" "' + cur_exe + '"')
                    cmd_lines.append('del "%~f0"')
                    with open(bat_path, "w", encoding="cp949") as f: f.write(chr(10).join(cmd_lines))
                    
                    root_upd = tk.Tk()
                    root_upd.withdraw()
                    root_upd.attributes("-topmost", True)
                    info_msg = []
                    info_msg.append(f"새로운 버전(V{latest_version})이 감지되었습니다!")
                    info_msg.append("확인을 누르시면 프로그램이 재시작되며 업데이트가 적용됩니다.")
                    messagebox.showinfo("업데이트 안내", chr(10).join(info_msg))
                    root_upd.destroy()
                    subprocess.Popen([bat_path], shell=True)
                    os._exit(0)
    except Exception: pass

def update_hof_stats(force=False):
    global gui_data, global_spreadsheet
    if not global_spreadsheet: return
    try:
        all_ws = global_spreadsheet.worksheets()
        c_g_data = {"전체 (ALL)": {}}
        a_g_data = {"전체 (ALL)": {}}
        
        c_patches = set()
        a_patches = set()
        
        for ws in all_ws:
            title = ws.title
            if title not in ["CLASSIC_NORMAL", "KIWI_KIWI"]: continue
            is_classic = (title == "CLASSIC_NORMAL")
            
            rows = get_sheet_data_cached(ws, force=force)
            if len(rows) <= 1: continue
            
            headers = rows[0]
            col_gid = headers.index("게임ID") if "게임ID" in headers else -1
            col_name = headers.index("소환사명") if "소환사명" in headers else -1
            col_pos = headers.index("포지션") if "포지션" in headers else -1
            col_res = headers.index("결과") if "결과" in headers else -1
            col_eval = headers.index("매치평가") if "매치평가" in headers else -1
            col_patch = headers.index("패치버전") if "패치버전" in headers else -1
            
            if col_name == -1 or col_res == -1: continue
            
            eval_gids = set()
            if col_eval != -1 and col_gid != -1:
                for r in rows[1:]:
                    if len(r) > col_eval and r[col_eval] in ["MVP", "역적"]:
                        g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
                        if g_id: eval_gids.add(g_id)
            
            target_data = c_g_data if is_classic else a_g_data
            target_patches = c_patches if is_classic else a_patches
            processed_records = set()
            
            for r in rows[1:]:
                g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
                p_name = r[col_name] if col_name != -1 and col_name < len(r) else ""
                main_name = get_main_name(p_name)
                res = r[col_res] if col_res != -1 and col_res < len(r) else ""
                
                raw_pos_kor = r[col_pos] if col_pos != -1 and col_pos < len(r) else "선택안함"
                pos_eng = "NONE"
                for k, v in POSITION_TRANSLATE_KOR.items():
                    if v == raw_pos_kor: pos_eng = k
                
                evl = r[col_eval] if col_eval != -1 and col_eval < len(r) else ""
                patch_ver = r[col_patch].strip() if col_patch != -1 and col_patch < len(r) and r[col_patch].strip() else "과거버전"
                
                if not main_name or res not in ["승리", "패배"]: continue
                
                record_key = f"{g_id}_{main_name}"
                if record_key in processed_records: continue
                processed_records.add(record_key)
                
                target_patches.add(patch_ver)
                
                for p_ver in ["전체 (ALL)", patch_ver]:
                    if p_ver not in target_data: target_data[p_ver] = {}
                    
                    if main_name not in target_data[p_ver]:
                        target_data[p_ver][main_name] = {
                            "name": main_name, 
                            "main_pos": {},
                            "ALL": {"total": 0, "wins": 0, "mvp": 0, "troll": 0, "eval_total": 0},
                            "TOP": {"total": 0, "wins": 0, "mvp": 0, "troll": 0, "eval_total": 0},
                            "JUNGLE": {"total": 0, "wins": 0, "mvp": 0, "troll": 0, "eval_total": 0},
                            "MIDDLE": {"total": 0, "wins": 0, "mvp": 0, "troll": 0, "eval_total": 0},
                            "BOTTOM": {"total": 0, "wins": 0, "mvp": 0, "troll": 0, "eval_total": 0},
                            "UTILITY": {"total": 0, "wins": 0, "mvp": 0, "troll": 0, "eval_total": 0}
                        }
                    
                    target_data[p_ver][main_name]["ALL"]["total"] += 1
                    if pos_eng != "NONE":
                        target_data[p_ver][main_name]["main_pos"][pos_eng] = target_data[p_ver][main_name]["main_pos"].get(pos_eng, 0) + 1
                    
                    if res == "승리": target_data[p_ver][main_name]["ALL"]["wins"] += 1
                    
                    if g_id in eval_gids:
                        target_data[p_ver][main_name]["ALL"]["eval_total"] += 1
                        if evl == "MVP": target_data[p_ver][main_name]["ALL"]["mvp"] += 1
                        if evl == "역적": target_data[p_ver][main_name]["ALL"]["troll"] += 1
                    
                    if pos_eng in target_data[p_ver][main_name] and pos_eng != "NONE":
                        target_data[p_ver][main_name][pos_eng]["total"] += 1
                        if res == "승리": target_data[p_ver][main_name][pos_eng]["wins"] += 1
                        if g_id in eval_gids:
                            target_data[p_ver][main_name][pos_eng]["eval_total"] += 1
                            if evl == "MVP": target_data[p_ver][main_name][pos_eng]["mvp"] += 1
                            if evl == "역적": target_data[p_ver][main_name][pos_eng]["troll"] += 1
                            
        with gui_lock:
            gui_data["hof_classic"] = {
                "global_stats": c_g_data, 
                "patches": ["전체 (ALL)"] + sorted(list(c_patches), reverse=True)
            }
            gui_data["hof_aram"] = {
                "global_stats": a_g_data, 
                "patches": ["전체 (ALL)"] + sorted(list(a_patches), reverse=True)
            }
    except Exception: pass

def get_champ_eng_name(kor_name):
    if not kor_name: return None
    clean_name = kor_name.strip()
    if clean_name in CHAMP_KOR_TO_ENG: return CHAMP_KOR_TO_ENG[clean_name]
    for champ_id, data in global_champ_map.items():
        if data.get('kor') == clean_name: return data.get('eng')
    return None

def load_champion_image(champ_kor_name, size=32):
    if not PILLOW_INSTALLED or not champ_kor_name: return None
    champ_eng_name = get_champ_eng_name(champ_kor_name)
    if not champ_eng_name: return None 
    
    cache_key = f"{champ_eng_name}_{size}"
    if cache_key in champion_image_cache: 
        return champion_image_cache[cache_key]
        
    try:
        url = f"http://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{champ_eng_name}.png"
        res = requests.get(url, timeout=2)
        if res.status_code == 200:
            img_data = Image.open(BytesIO(res.content))
            img_resized = img_data.resize((size, size), Image.Resampling.LANCZOS)
            photo_img = ImageTk.PhotoImage(img_resized)
            champion_image_cache[cache_key] = photo_img
            return photo_img
    except Exception: pass
    return None

def crunch_sheet_statistics(blue_players, red_players, sheet):
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
        
        if col_puuid == -1 or col_res == -1: return {}, [], [], []
        data_rows = rows[1:]
    except Exception: return {}, [], [], []

    player_games, player_champ_counts, games_dict = {}, {}, {}
    processed_records = set()

    for r in data_rows:
        g_id = r[col_gid] if col_gid != -1 and col_gid < len(r) else ""
        p_name = r[col_name] if col_name != -1 and col_name < len(r) else ""
        main_name = get_main_name(p_name)
        
        t_name = r[col_team] if col_team != -1 and col_team < len(r) else ""
        matched_pos = r[col_pos] if col_pos != -1 and col_pos < len(r) else ""
        champ = r[col_champ] if col_champ != -1 and col_champ < len(r) else ""
        bans_str = r[col_bans] if col_bans != -1 and col_bans < len(r) else ""
        res = r[col_res] if col_res != -1 and col_res < len(r) else ""
        
        if not main_name or res not in ["승리", "패배"]: continue
        
        record_key = str(g_id) + "_" + str(main_name)
        if record_key in processed_records: continue
        processed_records.add(record_key)
        
        if main_name not in player_games:
            player_games[main_name] = []
            player_champ_counts[main_name] = {}
        
        safe_bans = str(bans_str) if bans_str else ""
        player_games[main_name].append({'champ': champ, 'bans': safe_bans, 'result': res, 'pos': matched_pos, 'team': t_name})
        if champ: player_champ_counts[main_name][champ] = player_champ_counts[main_name].get(champ, 0) + 1

        if g_id not in games_dict: games_dict[g_id] = {"블루팀": [], "레드팀": [], "winner": ""}
        if t_name == "블루팀":
            games_dict[g_id]["블루팀"].append(main_name)
            if res == "승리": games_dict[g_id]["winner"] = "블루팀"
        else:
            games_dict[g_id]["레드팀"].append(main_name)
            if res == "승리": games_dict[g_id]["winner"] = "레드팀"

    stats_dashboard, blue_pool, red_pool = {}, {}, {}

    for p in blue_players + red_players:
        p_puuid = p['puuid'].strip()
        main_name = get_main_name(p['name'])
        
        p_matches = player_games.get(main_name, [])
        total = len(p_matches)
        
        is_blue = any(bp['puuid'] == p['puuid'] for bp in blue_players)
        current_pool = blue_pool if is_blue else red_pool

        if total == 0:
            stats_dashboard[p_puuid] = {"summary": "기록 없음", "most_list": [], "op_list": [], "fatal_bans": [], "pos1": "선택안함", "pos2": "선택안함", "streak": "", "streak_val": 0, "overall_wr": 0.5, "side_wr_str": ""}
            continue
        
        wins = sum(1 for m in p_matches if m.get('result') == '승리')
        overall_wr = wins / total
        
        side_target = '블루팀' if is_blue else '레드팀'
        side_games = sum(1 for m in p_matches if m.get('team') == side_target)
        side_wins = sum(1 for m in p_matches if m.get('team') == side_target and m.get('result') == '승리')
        side_wr_str = f"진영 승률: {round((side_wins/side_games)*100)}% ({side_wins}승 {side_games-side_wins}패)" if side_games > 0 else "진영 승률: 기록없음"

        streak_str, streak_val = "", 0
        if p_matches:
            recent_matches = list(reversed(p_matches))
            current_res = recent_matches[0].get('result', '')
            streak_count = 0
            for m in recent_matches:
                if m.get('result') == current_res: streak_count += 1
                else: break
            if current_res == '승리': streak_str, streak_val = f" (🔥{streak_count}연승중)", streak_count
            elif current_res == '패배': streak_str, streak_val = f" (🌧️{streak_count}연패중)", -streak_count

        champ_counts = player_champ_counts.get(main_name, {})
        most_list, op_list = [], []
        
        user_ban_score = {}
        if champ_counts:
            sorted_champs = sorted(champ_counts.items(), key=lambda x: x[1], reverse=True)
            for c, v in sorted_champs[:3]: most_list.append({"name": c, "count": v})
            
            for c, v in sorted_champs[:5]:
                c_wins = sum(1 for m in p_matches if m.get('champ') == c and m.get('result') == '승리')
                c_wr = (c_wins / v) * 100
                if c_wr >= 50.0:  
                    op_list.append({"name": c, "wr": c_wr, "count": v})
                    user_ban_score[c] = user_ban_score.get(c, 0) + c_wr + (min(v, 10) * 2)
        
        top_5_champs = [c for c, _ in sorted_champs[:5]] if champ_counts else []
        fatal_bans = []
        for c in top_5_champs:
            b_games, b_wins = 0, 0
            for m in p_matches:
                clean_bans = [b.strip() for b in str(m.get('bans', '')).split(',') if b.strip()]
                if c in clean_bans:
                    b_games += 1
                    if m.get('result') == '승리': b_wins += 1
            if b_games >= 1: 
                b_wr = b_wins / b_games
                drop = overall_wr - b_wr
                if drop >= 0.10: 
                    fatal_bans.append({"champ": c, "drop": int(drop * 100), "b_wr": int(b_wr * 100), "b_games": b_games})
                    fatal_score = (drop * 100) * 1.5 + (min(b_games, 5) * 5)
                    user_ban_score[c] = user_ban_score.get(c, 0) + fatal_score
        
        fatal_bans.sort(key=lambda x: x['drop'], reverse=True)
        
        if user_ban_score:
            best_c = max(user_ban_score.items(), key=lambda x: x[1])
            current_pool[best_c[0]] = current_pool.get(best_c[0], 0) + best_c[1]

        stats_dashboard[p_puuid] = {
            "summary": f"{total}전 {wins}승 {total-wins}패 ({round(overall_wr*100, 1)}%)",
            "most_list": most_list, "op_list": op_list,
            "fatal_bans": fatal_bans,
            "streak": streak_str, "streak_val": streak_val,
            "overall_wr": overall_wr, "side_wr_str": side_wr_str
        }

    blue_advice_list = sorted(red_pool.items(), key=lambda x: x[1], reverse=True)[:3]
    red_advice_list = sorted(blue_pool.items(), key=lambda x: x[1], reverse=True)[:3]
    
    with gui_lock:
        gui_data["blue_ban_advice_list"] = [c for c, _ in blue_advice_list]
        gui_data["red_ban_advice_list"] = [c for c, _ in red_advice_list]

    def calculate_hybrid_power(players_list):
        power_sum = 0
        for p in players_list:
            t_icon = p.get('tier_icon', 'UNRANKED')
            t_score = TIERS.index(t_icon) if t_icon in TIERS else 4
            s_data = stats_dashboard.get(p['puuid'], {})
            wr_score = s_data.get('overall_wr', 0.5) * 10
            stk = s_data.get('streak_val', 0)
            power_sum += ((t_score + wr_score) / 2) + (stk * 0.3)
        return power_sum

    blue_power, red_power = calculate_hybrid_power(blue_players), calculate_hybrid_power(red_players)
    with gui_lock:
        if blue_power + red_power > 0:
            calc_b_wr = max(15, min(85, int(50 + ((blue_power - red_power) * 4))))
            gui_data["blue_win_rate"] = calc_b_wr
            gui_data["red_win_rate"] = 100 - gui_data["blue_win_rate"]
        else:
            gui_data["blue_win_rate"] = 50; gui_data["red_win_rate"] = 50

    pos_alerts, neg_alerts, nemesis_alerts = [], [], []
    
    for i in range(len(blue_players)):
        for j in range(i + 1, len(blue_players)):
            p1_m = get_main_name(blue_players[i]['name'])
            p2_m = get_main_name(blue_players[j]['name'])
            if p1_m and p2_m and p1_m != p2_m and not blue_players[i]['puuid'].startswith('BOT_'):
                dg, dw = 0, 0
                for g_data in games_dict.values():
                    if p1_m in g_data['블루팀'] and p2_m in g_data['블루팀']:
                        dg += 1; dw += 1 if g_data['winner'] == '블루팀' else 0
                    elif p1_m in g_data['레드팀'] and p2_m in g_data['레드팀']:
                        dg += 1; dw += 1 if g_data['winner'] == '레드팀' else 0
                
                if dg >= 10: 
                    dwr = (dw/dg)*100
                    p1_d, p2_d = str(blue_players[i]['name']).split('#')[0], str(blue_players[j]['name']).split('#')[0]
                    if dwr <= 35.0: neg_alerts.append(f" ⚠️ [블루팀] {p1_d} & {p2_d} ({dg}전 {dw}승 / {round(dwr)}%)")
                    elif dwr >= 65.0: pos_alerts.append(f" 🔥 [블루팀] {p1_d} & {p2_d} ({dg}전 {dw}승 / {round(dwr)}%)")

    for i in range(len(red_players)):
        for j in range(i + 1, len(red_players)):
            p1_m = get_main_name(red_players[i]['name'])
            p2_m = get_main_name(red_players[j]['name'])
            if p1_m and p2_m and p1_m != p2_m and not red_players[i]['puuid'].startswith('BOT_'):
                dg, dw = 0, 0
                for g_data in games_dict.values():
                    if p1_m in g_data['블루팀'] and p2_m in g_data['블루팀']:
                        dg += 1; dw += 1 if g_data['winner'] == '블루팀' else 0
                    elif p1_m in g_data['레드팀'] and p2_m in g_data['레드팀']:
                        dg += 1; dw += 1 if g_data['winner'] == '레드팀' else 0
                
                if dg >= 10:
                    dwr = (dw/dg)*100
                    p1_d, p2_d = str(red_players[i]['name']).split('#')[0], str(red_players[j]['name']).split('#')[0]
                    if dwr <= 35.0: neg_alerts.append(f" ⚠️ [레드팀] {p1_d} & {p2_d} ({dg}전 {dw}승 / {round(dwr)}%)")
                    elif dwr >= 65.0: pos_alerts.append(f" 🔥 [레드팀] {p1_d} & {p2_d} ({dg}전 {dw}승 / {round(dwr)}%)")

    for b_p in blue_players:
        b_main = get_main_name(b_p['name'])
        if not b_main or "bot_" in str(b_p.get('puuid','')).lower(): continue
        for r_p in red_players:
            r_main = get_main_name(r_p['name'])
            if not r_main or "bot_" in str(r_p.get('puuid','')).lower(): continue
            if b_main == r_main: continue
            
            hg, bw = 0, 0
            for g_data in games_dict.values():
                if b_main in g_data['블루팀'] and r_main in g_data['레드팀']:
                    hg += 1; bw += 1 if g_data['winner'] == '블루팀' else 0
                elif b_main in g_data['레드팀'] and r_main in g_data['블루팀']:
                    hg += 1; bw += 1 if g_data['winner'] == '레드팀' else 0
            
            if hg >= 10:
                wr = (bw / hg) * 100
                b_disp, r_disp = str(b_p['name']).split('#')[0], str(r_p['name']).split('#')[0]
                if wr <= 30.0: nemesis_alerts.append(f" 😱 [인간상성] {b_disp} ➡️ {r_disp} 매우 취약! ({hg}전 {bw}승 {hg-bw}패)")
                elif wr >= 70.0: nemesis_alerts.append(f" 😈 [담당일진] {b_disp} ➡️ {r_disp} 압살 중! ({hg}전 {bw}승 {hg-bw}패)")
                elif bw == (hg - bw): nemesis_alerts.append(f" ⚔️ [세기의대결] {b_disp} 🆚 {r_disp} 팽팽한 숙적! ({bw}승 {bw}패)")

    return stats_dashboard, pos_alerts, neg_alerts, nemesis_alerts

def get_lcu_credentials():
    if not os.path.exists(LOCKFILE_PATH): return None, None
    try:
        with open(LOCKFILE_PATH, "r") as f: content = f.read()
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
                # 🔥 [버그 수정 4] 챔피언 데이터 파싱 에러(침묵형 에러) 완전 차단
                if isinstance(c, dict) and c.get('id') is not None:
                    try:
                        c_id = int(c['id'])
                        champ_map[c_id] = {"kor": c.get('name', ''), "eng": c.get('alias', '')}
                        global_champ_map[c_id] = champ_map[c_id]
                    except (ValueError, TypeError): pass
    except Exception: pass
    return champ_map

def get_name_by_summoner_id(summoner_id, headers, base_url):
    if not summoner_id or summoner_id == 0: return "알 수 없는 유저"
    try:
        url = str(base_url) + "/lol-summoner/v1/summoners/" + str(summoner_id)
        res = requests.get(url, headers=headers, verify=False, timeout=2)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                g_name = str(data.get('gameName', '소환사'))
                tag = str(data.get('tagLine', 'KR1'))
                return g_name + "#" + tag
    except Exception: pass
    return "소환사(" + str(summoner_id) + ")"

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

# =========================================================================
# 🚫 V80.1 백엔드 루프 (픽창 증발 방어 & Batch 업데이트 & KDA 기록)
# =========================================================================
def lcu_core_backend_loop():
    global gui_data, global_captured_bans, global_spreadsheet, frozen_bans_str, global_ingame_names, global_puuid_fallback_map
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    try:
        json_key_path = resource_path('credentials.json.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_key_path, scope)
        client = gspread.authorize(creds)
        global_spreadsheet = client.open_by_key(DOCUMENT_ID)
        
        try:
            link_sheet = global_spreadsheet.worksheet("LINK_ACCOUNT")
            for r in link_sheet.get_all_values()[1:]:
                if len(r) >= 2 and r[0].strip() and r[1].strip():
                    global_alt_map[r[1].strip().split('#')[0].lower()] = r[0].strip()
        except Exception: pass
        threading.Thread(target=update_hof_stats, daemon=True).start()
    except Exception:
        with gui_lock:
            gui_data["status"] = "⚠️ 시트 연결 실패 (오프라인 로컬 정찰 모드 가동 중)"
        global_spreadsheet = None

    champ_map, sheet_row_indices = {}, []
    last_lobby_fingerprint, last_chat_game_id = "", ""
    recorded_game_ids = set() 
    active_recording_id = None
    last_ping_time = 0
    is_aram_session = False
    
    global_cached_blue = []
    global_cached_red = []
    global_pos_map = {}

    while True:
        try:
            port, password = get_lcu_credentials()
            if port and not champ_map: champ_map = build_translation_map(port, password)
            if not port:
                with gui_lock:
                    if "오프라인" not in gui_data["status"]: gui_data["status"] = "💤 롤 클라이언트를 실행해 주세요."
                time.sleep(2)
                continue

            raw_token = "riot:" + str(password)
            encoded_token = base64.b64encode(raw_token.encode('utf-8')).decode('utf-8')
            headers = {"Authorization": "Basic " + encoded_token, "Accept": "application/json"}
            base_url = "https://127.0.0.1:" + str(port)

            if time.time() - last_ping_time > 180:
                try:
                    curr_res = requests.get(str(base_url) + "/lol-summoner/v1/current-summoner", headers=headers, verify=False, timeout=2)
                    if curr_res.status_code == 200:
                        c_data = curr_res.json()
                        c_name = str(c_data.get('gameName', '')) + "#" + str(c_data.get('tagLine', ''))
                        c_puuid = c_data.get('puuid', '')
                        if c_puuid and global_spreadsheet:
                            try: on_sheet = global_spreadsheet.worksheet("ONLINE_USERS")
                            except Exception:
                                on_sheet = global_spreadsheet.add_worksheet(title="ONLINE_USERS", rows="1000", cols="3")
                                on_sheet.append_row(["닉네임", "PUUID", "마지막접속시간"])
                            records = get_sheet_data_cached(on_sheet)
                            found = False
                            current_time_str = str(int(time.time()))
                            row_idx_to_update = -1
                            for idx, row in enumerate(records):
                                if len(row) >= 2 and row[1] == c_puuid:
                                    row_idx_to_update = idx + 1; found = True; break
                            if found and row_idx_to_update > 0:
                                try:
                                    cells = [
                                        gspread.Cell(row=row_idx_to_update, col=1, value=c_name),
                                        gspread.Cell(row=row_idx_to_update, col=3, value=current_time_str)
                                    ]
                                    on_sheet.update_cells(cells)
                                    invalidate_sheet_cache("ONLINE_USERS")
                                except Exception: pass
                            else: 
                                on_sheet.append_row([c_name, c_puuid, current_time_str])
                                invalidate_sheet_cache("ONLINE_USERS")
                except Exception: pass
                last_ping_time = time.time()

            # 🔥 [버그 수정 1] 통신 타임아웃/렉 발생 시 밴데이터 강제 삭제 방어("None"으로 세팅)
            current_phase = "None"
            try:
                flow_res = requests.get(str(base_url) + "/lol-gameflow/v1/gameflow-phase", headers=headers, verify=False, timeout=3)
                if flow_res.status_code == 200: current_phase = flow_res.json()
            except Exception: pass

            detected_ban_ids = set()
            try:
                select_res = requests.get(str(base_url) + "/lol-champ-select/v1/session", headers=headers, verify=False, timeout=3)
                if select_res.status_code == 200:
                    s_json = select_res.json() or {}
                    for act_list in s_json.get('actions', []):
                        if isinstance(act_list, list):
                            for act in act_list:
                                if isinstance(act, dict) and act.get('type') == 'ban' and act.get('completed'):
                                    c_id = act.get('championId', 0)
                                    if str(c_id).isdigit() and int(c_id) > 0: detected_ban_ids.add(int(c_id))
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

            c100, c200, multi_id = [], [], ""
            queue_id = 0
            map_id = 11

            try:
                gf_res = requests.get(str(base_url) + "/lol-gameflow/v1/session", headers=headers, verify=False, timeout=3)
                if gf_res.status_code == 200:
                    gf_json = gf_res.json() or {}
                    gd = gf_json.get('gameData') or {}
                    
                    map_id = gd.get('map', {}).get('id', map_id)
                    queue_id = gd.get('queue', {}).get('id', 0)
                    
                    banned_champs = gd.get('bannedChampions') or []
                    if isinstance(banned_champs, dict):
                        for k in ['myTeamBans', 'theirTeamBans']:
                            for b_id in banned_champs.get(k) or []:
                                if str(b_id).isdigit() and int(b_id) > 0: detected_ban_ids.add(int(b_id))
                    elif isinstance(banned_champs, list):
                        for item in banned_champs:
                            if isinstance(item, int) and item > 0: detected_ban_ids.add(item)
                            elif isinstance(item, dict):
                                cid = item.get('championId', item.get('id', 0))
                                if str(cid).isdigit() and int(cid) > 0: detected_ban_ids.add(int(cid))
                    
                    if current_phase in ["ChampSelect", "GameStart", "InProgress"]:
                        raw_c100 = gd.get('teamOne') or []
                        raw_c200 = gd.get('teamTwo') or []
                        
                        c100 = [x for x in raw_c100 if isinstance(x, dict) and str(x.get('isSpectator', 'False')).lower() != 'true' and str(x.get('role', '')).upper() != "SPECTATOR"]
                        c200 = [x for x in raw_c200 if isinstance(x, dict) and str(x.get('isSpectator', 'False')).lower() != 'true' and str(x.get('role', '')).upper() != "SPECTATOR"]
            except Exception: pass

            if detected_ban_ids:
                for b_id in detected_ban_ids:
                    if b_id in champ_map: 
                        kor_name = champ_map[b_id]['kor']
                        if kor_name not in global_captured_bans:
                            global_captured_bans.append(kor_name)

            if current_phase in ["Lobby", "Matchmaking", "ReadyCheck", "None"] or (not c100 and not c200):
                try:
                    lobby_res = requests.get(str(base_url) + "/lol-lobby/v2/lobby", headers=headers, verify=False, timeout=3)
                    if lobby_res.status_code == 200:
                        lobby_data = lobby_res.json() or {}
                        multi_id = str(lobby_data.get('multiplayerGameId', ''))
                        
                        gc = lobby_data.get('gameConfig') or {}
                        queue_id = gc.get('queueId', queue_id)
                        map_id = gc.get('mapId', map_id)
                        is_custom = gc.get('isCustom', False)
                            
                        dict_text = str(gc).upper()
                        if "ARAM" in dict_text or "HOWLING" in dict_text or "BUTCHER" in dict_text or map_id in [12, 14] or queue_id == 450:
                            is_aram_session = True
                            
                        c100_temp, c200_temp = [], []
                        
                        if is_custom:
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
                                if t_id in ["100", "1", "ORDER", "TEAM1", "BLUE"]: 
                                    c100_temp.append(m)
                                elif t_id in ["200", "2", "CHAOS", "TEAM2", "RED"]: 
                                    c200_temp.append(m)
                                    
                        c100, c200 = c100_temp, c200_temp
                except Exception: pass
            
            if multi_id and multi_id != "0" and multi_id != last_chat_game_id:
                global_captured_bans.clear()
                frozen_bans_str = ""
                global_ingame_names.clear()
                global_puuid_fallback_map.clear()
                is_aram_session = False
                global_cached_blue.clear()
                global_cached_red.clear()
                global_pos_map.clear()
                active_recording_id = None
                last_lobby_fingerprint = ""
                try:
                    threading.Timer(1.5, send_lcu_chat_announcement, args=[f"[분석기 정찰 시스템] 스쿼드해체분석기 v{CURRENT_VERSION} 로딩 완료", headers, base_url]).start()
                    last_chat_game_id = multi_id
                except Exception: pass

            if current_phase in ["Lobby", "Matchmaking"] and not active_recording_id:
                global_captured_bans.clear()
                frozen_bans_str = ""
                global_ingame_names.clear()
                global_puuid_fallback_map.clear()

            forbidden_queues = [400, 420, 430, 440, 490, 700]
            is_valid_game = (queue_id not in forbidden_queues)
            
            with gui_lock:
                gui_data["bans"] = "🚫 10밴 현황: " + ", ".join(global_captured_bans) if global_captured_bans else "🚫 10밴 현황: 대기 중"

            if current_phase == "ChampSelect" and global_captured_bans:
                frozen_bans_str = ", ".join(global_captured_bans)

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
                            bot_kor_name = champ_map.get(bot_champ_id, {}).get('kor', '봇') if champ_map else '봇'
                            name = "🤖 " + str(bot_kor_name) + " 봇"
                            puuid = "BOT_" + str(bot_champ_id)
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
                            if not name: name = "알 수 없는 유저"
                            if not puuid: puuid = "TEMP_ID_" + str(s_id) + "_" + str(name)
                        
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
                if global_cached_blue or global_cached_red:
                    temp_blue, temp_red = global_cached_blue, global_cached_red
                else:
                    temp_blue, temp_red = parse_team(c100), parse_team(c200)
                    if temp_blue or temp_red:
                        global_cached_blue, global_cached_red = temp_blue, temp_red
                        need_stat_crunch = True
            else:
                temp_blue_parsed, temp_red_parsed = parse_team(c100), parse_team(c200)
                if temp_blue_parsed or temp_red_parsed:
                    temp_blue, temp_red = temp_blue_parsed, temp_red_parsed
                    global_cached_blue, global_cached_red = temp_blue, temp_red
                    need_stat_crunch = True
                else:
                    temp_blue, temp_red = global_cached_blue, global_cached_red

            lobby_fingerprint = "".join([str(p['puuid']) for p in temp_blue + temp_red])
            target_sheet_name = "KIWI_KIWI" if is_aram_session else "CLASSIC_NORMAL"

            if is_valid_game and global_spreadsheet:
                try: sheet_target = global_spreadsheet.worksheet(target_sheet_name)
                except Exception:
                    try:
                        # 🔥 신규 시트 생성 시 "KDA" 컬럼을 자동 추가하도록 세팅
                        sheet_target = global_spreadsheet.add_worksheet(title=target_sheet_name, rows="2000", cols="12")
                        sheet_target.append_row(["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "KDA", "매치평가", "패치버전"])
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
                        default_s = {"summary": "기록 없음", "most_list": [], "op_list": [], "fatal_bans": [], "streak": "", "side_wr_str": ""}
                        final_blue.append((p, cached_stats.get(p['puuid'], default_s)))
                    final_red = []
                    for p in temp_red:
                        default_s = {"summary": "기록 없음", "most_list": [], "op_list": [], "fatal_bans": [], "streak": "", "side_wr_str": ""}
                        final_red.append((p, cached_stats.get(p['puuid'], default_s)))
                        
                    with gui_lock:
                        gui_data["blue"] = final_blue
                        gui_data["red"] = final_red
                        gui_data["pos_synergy"] = "\n".join(cached_pos) if cached_pos else " - 특이사항 없음 (안정적)"
                        gui_data["neg_synergy"] = "\n".join(cached_neg) if cached_neg else " - 특이사항 없음 (평온)"
                        gui_data["nemesis_synergy"] = "\n".join(cached_nem) if cached_nem else " - 상성 매칭 없음 (평온)"
                        
                last_lobby_fingerprint = lobby_fingerprint

            with gui_lock:
                if current_phase == "Lobby":
                    if "오프라인" not in gui_data["status"]: gui_data["status"] = "🟢 대기실 정찰 중 (" + (target_sheet_name if is_valid_game else "기록 제외 모드") + ")"
                elif current_phase == "ChampSelect":
                    if "오프라인" not in gui_data["status"]: gui_data["status"] = "🔶 밴픽 진행 중 (데이터 절대 동결됨)"
                elif current_phase in ["GameStart", "InProgress"]:
                    if is_valid_game and active_recording_id:
                        if "오프라인" not in gui_data["status"]: gui_data["status"] = "🔥 인게임 기록 중 (데이터 절대 동결됨)"

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
                                
                            if not fetched_game_id: fetched_game_id = "CUSTOM_" + str(multi_id) if multi_id and multi_id != "0" else "CUSTOM_MATCH"
                            
                            if fetched_game_id not in recorded_game_ids:
                                lcu_puuid_map = {}
                                global_ingame_names.clear()
                                global_puuid_fallback_map.clear()
                                
                                for p in temp_blue + temp_red:
                                    c_name = str(p['name']).replace("🤖", "").replace(" 봇", "").strip().lower()
                                    lcu_puuid_map[c_name] = str(p['puuid'])
                                    
                                try: headers_row = get_sheet_data_cached(sheet_target)[0]
                                except Exception: headers_row = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "KDA", "매치평가", "패치버전"]
                                
                                missing_headers = []
                                # 🔥 KDA 열이 없는 구형 시트 대응 및 자동 추가
                                if "밴" not in headers_row: missing_headers.append("밴")
                                if "결과" not in headers_row: missing_headers.append("결과")
                                if "KDA" not in headers_row: missing_headers.append("KDA")
                                if "매치평가" not in headers_row: missing_headers.append("매치평가")
                                if "패치버전" not in headers_row: missing_headers.append("패치버전")
                                
                                if missing_headers:
                                    if not headers_row: 
                                        headers_row = ["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과", "KDA", "매치평가", "패치버전"]
                                        sheet_target.append_row(headers_row)
                                    else:
                                        cells_to_add = []
                                        start_col = len(headers_row) + 1
                                        for i, h in enumerate(missing_headers):
                                            cells_to_add.append(gspread.Cell(row=1, col=start_col+i, value=h))
                                            headers_row.append(h)
                                        try:
                                            sheet_target.update_cells(cells_to_add)
                                        except Exception: pass
                                    invalidate_sheet_cache(sheet_target.title)
                                    
                                res_col_idx = headers_row.index("결과") + 1 if "결과" in headers_row else 0
                                ban_col_idx = headers_row.index("밴") + 1 if "밴" in headers_row else 0
                                kda_col_idx = headers_row.index("KDA") + 1 if "KDA" in headers_row else 0
                                eval_col_idx = headers_row.index("매치평가") + 1 if "매치평가" in headers_row else 0
                                patch_col_idx = headers_row.index("패치버전") + 1 if "패치버전" in headers_row else 0
                                    
                                rows_to_append = []
                                team_color_cache = []
                                
                                eng_to_kor_map = {v['eng'].lower().replace(" ", ""): v['kor'] for v in champ_map.values() if isinstance(v, dict)}
                                CHAMP_ENG_TO_KOR_FALLBACK = {v: k for k, v in CHAMP_KOR_TO_ENG.items()}

                                for p in lr_json:
                                    if not isinstance(p, dict): continue
                                    s_name = str(p.get('summonerName', '소환사'))
                                    riot_name = str(p.get('riotIdGameName', ''))
                                    riot_tag = str(p.get('riotIdTagLine', ''))
                                    
                                    c_name_key = s_name.replace(" 봇", "").strip().lower()
                                    full_riot_id = (f"{riot_name}#{riot_tag}").lower().strip() if riot_name and riot_tag else ""
                                    p_puuid = lcu_puuid_map.get(full_riot_id) or lcu_puuid_map.get(c_name_key, "")
                                    
                                    if p_puuid:
                                        if full_riot_id: global_puuid_fallback_map[full_riot_id] = p_puuid
                                        global_puuid_fallback_map[c_name_key] = p_puuid
                                    
                                    c_name_raw = str(p.get('championName', 'Bot')).replace(" ", "")
                                    kor_cname = eng_to_kor_map.get(c_name_raw.lower(), c_name_raw) if eng_to_kor_map else c_name_raw
                                    if kor_cname == c_name_raw: kor_cname = CHAMP_ENG_TO_KOR_FALLBACK.get(c_name_raw, c_name_raw)
                                    
                                    if riot_name: global_ingame_names[c_name_raw.lower()] = f"{riot_name}#{riot_tag}" if riot_tag else riot_name
                                    else: global_ingame_names[c_name_raw.lower()] = s_name

                                    team_val = "블루팀" if p.get('team', 'ORDER') == "ORDER" else "레드팀"
                                    captured_bans_str = frozen_bans_str if frozen_bans_str else ", ".join(global_captured_bans)
                                    
                                    row_data = [""] * len(headers_row)
                                    def set_val(col_name, val):
                                        if col_name in headers_row: row_data[headers_row.index(col_name)] = val
                                            
                                    set_val("게임ID", "#" + str(fetched_game_id))
                                    set_val("날짜", time.strftime("%Y-%m-%d"))
                                    set_val("소환사명", s_name)
                                    set_val("PUUID", p_puuid)
                                    set_val("진영", team_val)
                                    
                                    cached_pos_kor = "선택안함"
                                    for bp in temp_blue + temp_red:
                                        if str(bp['puuid']) == str(p_puuid): 
                                            eng_pos = bp.get('chosen_pos_icon', 'NONE')
                                            cached_pos_kor = POSITION_TRANSLATE_KOR.get(eng_pos, "선택안함")
                                    set_val("포지션", cached_pos_kor)
                                    set_val("챔피언", kor_cname)
                                    set_val("밴", captured_bans_str)
                                    set_val("결과", "결과 대기")
                                    set_val("KDA", "") # 기록 대기용 공간 세팅
                                    set_val("매치평가", "") 
                                    set_val("패치버전", str(PATCH_VERSION_SHORT)) 
                                    
                                    rows_to_append.append(row_data)
                                    team_color_cache.append((team_val, p_puuid, c_name_raw.lower()))
                                    
                                if rows_to_append:
                                    next_row = len(get_sheet_data_cached(sheet_target)) + 1
                                    sheet_target.append_rows(rows_to_append)
                                    
                                    new_indices = []
                                    for i, (t_color, player_puuid, player_c_eng) in enumerate(team_color_cache):
                                        # 🔥 KDA 인덱스 포함 저장
                                        new_indices.append((sheet_target, next_row + i, t_color, res_col_idx, ban_col_idx, kda_col_idx, eval_col_idx, patch_col_idx, player_puuid, player_c_eng))
                                    sheet_row_indices = new_indices
                                    
                                    recorded_game_ids.add(fetched_game_id)
                                    active_recording_id = fetched_game_id
                                    invalidate_sheet_cache(target_sheet_name)
                except Exception: pass
            
            if current_phase == "EndOfGame" and active_recording_id is not None:
                try:
                    eog_res = requests.get(str(base_url) + "/lol-end-of-game/v1/eog-stats-block", headers=headers, verify=False, timeout=3)
                    match_data = None
                    win_id = 0
                    actual_bans = []
                    
                    if eog_res.status_code == 200:
                        match_data = eog_res.json()
                        
                    if not match_data:
                        hist_url = str(base_url) + "/lol-match-history/v1/products/lol/current-summoner/matches"
                        hist_res = requests.get(hist_url, headers=headers, verify=False, timeout=3)
                        if hist_res.status_code == 200:
                            games_list = hist_res.json().get('games', {}).get('games', [])
                            if games_list: match_data = games_list[0]
                    
                    if match_data:
                        for t in match_data.get('teams', []):
                            if t.get('isWinningTeam') == True or t.get('win') == 'Win' or t.get('win') == True:
                                win_id = t.get('teamId')
                            
                            # 🔥 [버그 수정 2] 결과창 밴 구조가 비정상일때 발생하는 에러 원천 방어
                            for ban in t.get('bans') or []:
                                b_id = ban.get('championId') if isinstance(ban, dict) else ban
                                try:
                                    b_id = int(b_id)
                                    if b_id in champ_map: actual_bans.append(champ_map[b_id]['kor'])
                                except (ValueError, TypeError): pass
                                
                        # KDA 데이터 맵핑까지 리턴 받도록 수정
                        achieves_list, mvp_puuid, mvp_c_eng, troll_puuid, troll_c_eng, kda_map = parse_endgame_achievements(
                            match_data, global_pos_map, champ_map, global_cached_blue, global_cached_red, is_aram_session
                        )
                        
                        cells_to_update = []
                        target_sheet_obj = None
                                        
                        for t_sheet, row_num, t_color, res_col, ban_col, kda_col, eval_col, patch_col, row_puuid, row_champ_eng in sheet_row_indices:
                            target_sheet_obj = t_sheet
                            res_str = "승리" if (t_color == "블루팀" and win_id == 100) or (t_color == "레드팀" and win_id == 200) else "패배"
                            
                            if res_col > 0:
                                cells_to_update.append(gspread.Cell(row=row_num, col=res_col, value=res_str))
                            
                            # 🔥 [버그 수정 3] 픽창에서 완벽히 수집해둔 밴 데이터(frozen_bans_str)가 있다면 
                            # 전적 API의 낡거나 불완전한 결과로 덮어쓰지 않음
                            if actual_bans and not frozen_bans_str and ban_col > 0:
                                cells_to_update.append(gspread.Cell(row=row_num, col=ban_col, value=", ".join(actual_bans)))

                            # 🔥 [신규] 게임 결과의 KDA 기록 일괄 업데이트    
                            if kda_col > 0:
                                kda_val = kda_map.get(str(row_puuid)) or kda_map.get(str(row_champ_eng)) or ""
                                if kda_val:
                                    cells_to_update.append(gspread.Cell(row=row_num, col=kda_col, value=kda_val))

                            eval_str = ""
                            if (row_puuid and row_puuid == mvp_puuid) or (row_champ_eng and row_champ_eng == mvp_c_eng): eval_str = "MVP"
                            elif (row_puuid and row_puuid == troll_puuid) or (row_champ_eng and row_champ_eng == troll_c_eng): eval_str = "역적"
                            
                            if eval_str and eval_col > 0:
                                cells_to_update.append(gspread.Cell(row=row_num, col=eval_col, value=eval_str))
                            
                            if patch_col > 0:
                                cells_to_update.append(gspread.Cell(row=row_num, col=patch_col, value=str(PATCH_VERSION_SHORT)))
                        
                        if target_sheet_obj and cells_to_update:
                            try:
                                target_sheet_obj.update_cells(cells_to_update)
                                invalidate_sheet_cache(target_sheet_obj.title)
                            except Exception: pass
                        
                        if achieves_list: 
                            ach_text = chr(10).join(achieves_list)
                            broadcast_to_discord_webhook(ach_text)
                            with gui_lock:
                                gui_data["achievements"] = achieves_list
                                
                        active_recording_id = None
                except Exception: pass
        except Exception: pass
        time.sleep(1.0)
# =========================================================================================

def parse_endgame_achievements(match_data, pos_map, champ_map, blue_players, red_players, is_aram=False):
    achievements = []
    mvp_puuid_out = ""
    mvp_c_eng_out = ""
    troll_puuid_out = ""
    troll_c_eng_out = ""
    kda_map = {}  # 🔥 KDA 정보 추출용 딕셔너리
    
    try:
        puuid_to_true_name = {}
        for p in blue_players + red_players:
            if p.get('puuid'):
                puuid_to_true_name[p['puuid']] = p['name']

        game_duration = match_data.get('gameLength', match_data.get('gameDuration', 0))
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
                for p in t.get('players', []):
                    p['teamId'] = t.get('teamId')
                    participants.append(p)
        
        id_to_name = {}
        puuid_to_name_from_identities = {}
        
        if participant_identities:
            for pi in participant_identities:
                if isinstance(pi, dict):
                    p_id = pi.get('participantId')
                    player = pi.get('player') or {}
                    if isinstance(player, dict):
                        name = player.get('gameName') or player.get('summonerName') or f"유저{p_id}"
                        puuid = player.get('puuid') or ""
                        id_to_name[p_id] = name
                        puuid_to_name_from_identities[p_id] = puuid
        else:
            for p in participants:
                p_id = p.get('participantId', p.get('summonerId', 0))
                name = p.get('summonerName') or p.get('gameName') or f"유저{p_id}"
                puuid = p.get('puuid') or ""
                id_to_name[p_id] = name
                puuid_to_name_from_identities[p_id] = puuid

        role_map = {100: {}, 200: {}}
        for p in participants:
            if isinstance(p, dict):
                t_id = p.get('teamId')
                p_id = p.get('participantId', p.get('summonerId', 0))
                puuid = puuid_to_name_from_identities.get(p_id)
                
                if not puuid:
                    riot_id = f"{p.get('riotIdGameName','')}#{p.get('riotIdTagLine','')}".lower().strip()
                    c_name = p.get('summonerName','').lower().strip()
                    puuid = global_puuid_fallback_map.get(riot_id) or global_puuid_fallback_map.get(c_name)

                role = pos_map.get(puuid, "NONE") if puuid else "NONE"
                if role == "NONE": role = str(p.get('teamPosition', 'NONE')).upper()
                    
                if t_id in role_map and role != "NONE":
                    role_map[t_id][role] = p
                    
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
                c_name = p.get('summonerName','').lower().strip()
                puuid = global_puuid_fallback_map.get(riot_id) or global_puuid_fallback_map.get(c_name)
            
            name = puuid_to_true_name.get(puuid)
            c_id = p.get('championId', 0)
            c_eng = champ_map.get(c_id, {}).get('eng', '').replace(" ", "").lower() if c_id in champ_map else ''
            
            if not name: name = global_ingame_names.get(c_eng)
            if not name: name = id_to_name.get(p_id, f"유저{p_id}")
            
            role = pos_map.get(puuid, "NONE") if puuid else "NONE"
            if role == "NONE": role = str(p.get('teamPosition', 'NONE')).upper()
            
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
            
            # 🔥 각 유저별 KDA 텍스트 매핑
            kda_str = f"{kills}/{deaths}/{assists}"
            if puuid: kda_map[str(puuid)] = kda_str
            if c_eng: kda_map[c_eng] = kda_str
            
            safe_d = max(1, deaths)
            kda_score = ((kills + assists) / safe_d) * 5.0
            dmg_score = ((dmg_dealt / safe_d) / 1000.0) * 2.0
            tank_score = ((dmg_taken / safe_d) / 1000.0) * 1.0
            vision_score_calc = vision * 0.4
            
            penalty_multiplier = 2.5
            if role == "BOTTOM": penalty_multiplier = 4.0
            elif role == "MIDDLE": penalty_multiplier = 3.0
            elif role == "JUNGLE": penalty_multiplier = 2.5
            elif role == "TOP": penalty_multiplier = 1.5
            elif role == "UTILITY": penalty_multiplier = 1.0
            
            death_penalty = deaths * penalty_multiplier
            ai_score = kda_score + dmg_score + tank_score + vision_score_calc - death_penalty
            
            player_scores.append({
                'name': name, 'puuid': str(puuid), 'c_eng': c_eng, 'score': ai_score, 
                'k': kills, 'd': deaths, 'a': assists, 
                'dmg': dmg_dealt, 'tank': dmg_taken, 'vs': vision
            })
            
            p_achieves = []
            
            if not is_aram:
                if is_win and game_duration <= 960: p_achieves.append("⏱️ [이차가 식기전에] 16분 이전 게임 승리자")
                if is_win and game_duration >= 3000: p_achieves.append("⏳ [진흙탕싸움] 50분 이상 게임 승리자")
                if is_win and deaths == 0: p_achieves.append("🛡️ [불사대마왕] 노데스 게임 승리")
                if is_win and dmg_dealt >= 80000: p_achieves.append("⚔️ [사디스트] 딜량 8만이상 달성 후 승리")
                if is_win and dmg_taken >= 120000: p_achieves.append("🩸 [마조히스트] 받은피해량 12만이상 달성 후 승리")
                if penta == 1: p_achieves.append(f"💀 [학살자] 펜타킬 1회 달성")
                    
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
                    if role == "JUNGLE" and is_win and (kills+assists) >= (opp_kp * 2) and (kills+assists) >= 5:
                        p_achieves.append(f"🌲 [(정글) 정글 차이] 상대 정글보다 킬관여(K+A) 2배 이상 달성 후 승리 (나: {kills+assists} vs 적: {opp_kp})")
                    if role == "UTILITY" and is_win and assists >= (opp_assists * 2) and assists >= 10:
                        p_achieves.append(f"🧿 [(서폿) 서폿 차이] 상대 서폿보다 어시스트 2배 이상 달성 후 승리 (나: {assists} vs 적: {opp_assists})")

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
            player_scores.sort(key=lambda x: x['score'], reverse=True)
            mvp = player_scores[0]
            troll = player_scores[-1]
            
            mvp_puuid_out = mvp.get('puuid', '')
            mvp_c_eng_out = mvp.get('c_eng', '')
            troll_puuid_out = troll.get('puuid', '')
            troll_c_eng_out = troll.get('c_eng', '')
            
            report_lines = []
            report_lines.append(f"🏆 **[Match MVP]** {mvp['name'].split('#')[0]} (AI 종합점수: {mvp['score']:.1f}점)")
            report_lines.append(f"  - K/D/A: {mvp['k']}/{mvp['d']}/{mvp['a']} | 가성비 딜: {int(mvp['dmg']/max(1,mvp['d'])):,} | 가성비 탱: {int(mvp['tank']/max(1,mvp['d'])):,} | 시야: {mvp['vs']}")
            report_lines.append(f"💀 **[오늘의 역적]** {troll['name'].split('#')[0]} (AI 종합점수: {troll['score']:.1f}점)")
            report_lines.append(f"  - K/D/A: {troll['k']}/{troll['d']}/{troll['a']} | 가성비 딜: {int(troll['dmg']/max(1,troll['d'])):,} | 가성비 탱: {int(troll['tank']/max(1,troll['d'])):,} | 시야: {troll['vs']}")
            
            achievements.insert(0, "\n".join(report_lines) + "\n")

    except Exception: pass
    
    # 🔥 리턴 값에 kda_map 포함
    return achievements, mvp_puuid_out, mvp_c_eng_out, troll_puuid_out, troll_c_eng_out, kda_map

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
def create_graphic_ui():
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass
    
    root = tk.Tk()
    root.title("스쿼드해체분석기 [Ver " + str(CURRENT_VERSION) + " - 아키텍처 대규모 최적화]")
    
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    
    app_w = min(1420, int(screen_w * 0.95))
    app_h = min(950, int(screen_h * 0.90))
    root.geometry(f"{app_w}x{app_h}")
    
    if screen_h <= 1080: root.state('zoomed')

    BG_MAIN = "#121315"
    root.configure(bg=BG_MAIN)

    try: root.iconbitmap(resource_path("icon.ico"))
    except Exception: pass

    is_stealth = "--stealth" in sys.argv
    with gui_lock: gui_data["is_hidden"] = is_stealth
    if is_stealth: root.withdraw()

    def stealth_monitor():
        was_running = False
        while True:
            try:
                output = subprocess.check_output('tasklist /FI "IMAGENAME eq LeagueClient.exe"', shell=True).decode('cp949', errors='ignore')
                is_running = "LeagueClient.exe" in output
                
                if is_running and not was_running:
                    with gui_lock:
                        auto_show = APP_CONFIG.get("lol_auto_show", False)
                        is_hid = gui_data.get("is_hidden", False)
                    if auto_show and is_hid:
                        root.after(0, root.deiconify)
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

    for pos_key in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]:
        position_images[pos_key] = robust_load_image(str(pos_key) + ".png", 28)
        
    for tier in TIERS:
        tier_images[tier] = robust_load_image(str(tier) + ".png", 32)

    FONT_TITLE = ("Malgun Gothic", 20, "bold")
    FONT_CREDIT = ("Malgun Gothic", 11)
    FONT_STATUS = ("Malgun Gothic", 12, "bold")
    FONT_BANS = ("Malgun Gothic", 12)
    FONT_LF_TITLE = ("Malgun Gothic", 12, "bold")
    FONT_SLOT_NAME = ("Malgun Gothic", 13, "bold")
    FONT_SLOT_STAT = ("Malgun Gothic", 11)
    FONT_SYNERGY = ("Malgun Gothic", 11)

    header = tk.Frame(root, bg="#1a1c1f", height=130)
    header.pack(fill="x", side="top", pady=(5, 5))
    header.pack_propagate(False) 
    
    ad_frame = tk.Frame(header, bg="#1a1c1f", width=345, height=120, cursor="hand2")
    ad_frame.pack_propagate(False) 
    ad_frame.pack(side="right", padx=15, pady=5)
    
    ad_lbl = tk.Label(ad_frame, text="✨ 스폰서 배너 로딩 중... ✨", bg="#1a1c1f", fg="#f39c12", font=("Malgun Gothic", 10, "bold"))
    ad_lbl.pack(expand=True, fill="both")
    
    def on_ad_click(event):
        link = ""
        with gui_lock: link = gui_data.get("ad_link", "")
        if link: webbrowser.open(link)
    ad_lbl.bind("<Button-1>", on_ad_click)

    mid_header = tk.Frame(header, bg="#1a1c1f")
    mid_header.pack(side="right", padx=20, pady=15)
    
    tk.Label(mid_header, text="개발 및 기획 : 맛동산장인 유미#Teana", bg="#1a1c1f", fg="#a0a8b5", font=FONT_CREDIT).pack(anchor="e", pady=3)
    
    status_var = tk.StringVar(value="📡 LCU 시스템 탐색 중...")
    bans_var = tk.StringVar(value="🚫 10밴 현황: 대기 중")
    tk.Label(mid_header, textvariable=status_var, bg="#1a1c1f", fg="#2ecc71", font=FONT_STATUS).pack(anchor="e", pady=3)
    tk.Label(mid_header, textvariable=bans_var, bg="#1a1c1f", fg="#bdc3c7", font=FONT_BANS).pack(anchor="e", pady=3)

    left_header = tk.Frame(header, bg="#1a1c1f")
    left_header.pack(side="left", fill="both", expand=True, padx=15, pady=5)

    try:
        yumi_img = tk.PhotoImage(file=resource_path("yumi_avatar.png")).subsample(7, 7)
        lbl_yumi = tk.Label(left_header, image=yumi_img, bg="#1a1c1f")
        lbl_yumi.image = yumi_img
        lbl_yumi.pack(side="left", padx=5)
    except Exception: pass

    text_frame = tk.Frame(left_header, bg="#1a1c1f")
    text_frame.pack(side="left", padx=5)
    
    tk.Label(text_frame, text="스쿼드해체분석기", bg="#1a1c1f", fg="#F5D47A", font=FONT_TITLE).pack(anchor="w", pady=(0, 5))
    
    sub_ctrl_frame = tk.Frame(text_frame, bg="#1a1c1f")
    sub_ctrl_frame.pack(anchor="w")
    
    btn_row1 = tk.Frame(sub_ctrl_frame, bg="#1a1c1f")
    btn_row1.pack(anchor="w", pady=(0, 2))
    btn_row2 = tk.Frame(sub_ctrl_frame, bg="#1a1c1f")
    btn_row2.pack(anchor="w", pady=(2, 0))
    
    # btn_balance = tk.Button(btn_row1, text="🤖 팀 밸런싱", font=("Malgun Gothic", 10, "bold"), bg="#1abc9c", fg="#ffffff", bd=0, padx=8, pady=2, cursor="hand2")
    # btn_balance.config(command=lambda: open_auto_balancer_window(root))
    # btn_balance.pack(side="left", padx=(0, 3))

    btn_guide = tk.Button(btn_row1, text="📖 사용 안내", font=("Malgun Gothic", 10, "bold"), bg="#4a6984", fg="#ffffff", bd=0, padx=8, pady=2, cursor="hand2")
    btn_guide.config(command=lambda: GuideWindow(root))
    btn_guide.pack(side="left", padx=3)
    
    btn_online = tk.Button(btn_row1, text="👥 접속자", font=("Malgun Gothic", 10, "bold"), bg="#8e44ad", fg="#ffffff", bd=0, padx=8, pady=2, cursor="hand2")
    btn_online.config(command=lambda: OnlineUsersWindow(root))
    btn_online.pack(side="left", padx=3)
    
    def open_hof_window(mode_type):
        try: ClanRankingWindow(root, mode=mode_type)
        except Exception as e: messagebox.showerror("전당 오류", f"데이터를 갱신 중입니다. 잠시 후 다시 시도해주세요.\n(에러: {str(e)})")
        
    btn_rank = tk.Button(btn_row1, text="🏆 명예의 전당", font=("Malgun Gothic", 10, "bold"), bg="#b33939", fg="#ffffff", bd=0, padx=8, activebackground="#8c1c1c", pady=2, cursor="hand2")
    btn_rank.config(command=lambda: open_hof_window("CLASSIC"))
    btn_rank.pack(side="left", padx=3)
    
    btn_aram_rank = tk.Button(btn_row1, text="❄️ 증내의 전당", font=("Malgun Gothic", 10, "bold"), bg="#2980b9", fg="#ffffff", bd=0, padx=8, activebackground="#1a5276", pady=2, cursor="hand2")
    btn_aram_rank.config(command=lambda: open_hof_window("ARAM"))
    btn_aram_rank.pack(side="left", padx=3)
    
    btn_patch = tk.Button(btn_row2, text="📜 패치노트", font=("Malgun Gothic", 10, "bold"), bg="#e67e22", fg="#ffffff", bd=0, padx=8, pady=2, cursor="hand2")
    btn_patch.config(command=lambda: PatchNoteWindow(root))
    btn_patch.pack(side="left", padx=(0, 3))

    btn_banpick = tk.Button(btn_row2, text="✅ 모의밴픽", font=("Malgun Gothic", 10, "bold"), bg="#d35400", fg="#ffffff", bd=0, padx=8, pady=2, cursor="hand2")
    btn_banpick.config(command=lambda: webbrowser.open("https://www.fullbanpick.com/"))
    btn_banpick.pack(side="left", padx=3)
    
    btn_set = tk.Button(btn_row2, text="⚙️ 설정", font=("Malgun Gothic", 10, "bold"), bg="#2c3e50", fg="#ffffff", bd=0, padx=10, pady=2, cursor="hand2")
    btn_set.config(command=lambda: ClanSettingsWindow(root))
    btn_set.pack(side="left", padx=3)

    bottom_container = tk.Frame(root, bg=BG_MAIN)
    bottom_container.pack(fill="x", side="bottom", padx=20, pady=5)
    
    bottom_container.columnconfigure(0, weight=1, uniform="bot_third")
    bottom_container.columnconfigure(1, weight=1, uniform="bot_third")
    bottom_container.columnconfigure(2, weight=1, uniform="bot_third")

    pos_card = tk.Frame(bottom_container, bg="#1a1c1f")
    pos_card.grid(row=0, column=0, sticky="nsew", padx=4)
    tk.Label(pos_card, text="🔥 고승률 시너지 명단 (10판 / 승률 65% ▲)", bg="#242823", fg="#2ecc71", font=FONT_LF_TITLE, anchor="w", padx=10, pady=4).pack(fill="x")
    pos_box = scrolledtext.ScrolledText(pos_card, height=3, bg="#161719", fg="#2ecc71", font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    pos_box.pack(fill="both", expand=True)
    pos_box.configure(state="disabled")

    neg_card = tk.Frame(bottom_container, bg="#1a1c1f")
    neg_card.grid(row=0, column=1, sticky="nsew", padx=4)
    tk.Label(neg_card, text="⚠️ 역시너지 경보 명단 (10판 / 승률 35% ▼)", bg="#2a2222", fg="#e67e22", font=FONT_LF_TITLE, anchor="w", padx=10, pady=4).pack(fill="x")
    neg_box = scrolledtext.ScrolledText(neg_card, height=3, bg="#161719", fg="#e67e22", font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    neg_box.pack(fill="both", expand=True)
    neg_box.configure(state="disabled")

    nemesis_card = tk.Frame(bottom_container, bg="#1a1c1f")
    nemesis_card.grid(row=0, column=2, sticky="nsew", padx=4)
    tk.Label(nemesis_card, text="⚔️ 적팀 인간상성 경보 (10판 / 승률 3:7 극단)", bg="#221919", fg="#ec7063", font=FONT_LF_TITLE, anchor="w", padx=10, pady=4).pack(fill="x")
    nemesis_box = scrolledtext.ScrolledText(nemesis_card, height=3, bg="#161719", fg="#ec7063", font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    nemesis_box.pack(fill="both", expand=True)
    nemesis_box.configure(state="disabled")

    body = tk.Frame(root, bg=BG_MAIN)
    body.pack(fill="both", expand=True, padx=20, pady=5)
    body.columnconfigure(0, weight=1, uniform="team_half")
    body.columnconfigure(1, weight=1, uniform="team_half")

    blue_card = tk.Frame(body, bg="#191b22")
    red_card = tk.Frame(body, bg="#221919")
    blue_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=5)
    red_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=5)
    
    b_head = tk.Frame(blue_card, bg="#1f2633")
    b_head.pack(fill="x")
    b_title_frame = tk.Frame(b_head, bg="#1f2633")
    b_title_frame.pack(side="left", fill="x", expand=True)
    
    blue_title_lbl = tk.Label(b_title_frame, text="🟦 BLUE TEAM", bg="#1f2633", fg="#5dade2", font=FONT_LF_TITLE, anchor="w", padx=12, pady=6)
    blue_title_lbl.pack(side="left")
    
    blue_ban_frame = tk.Frame(b_title_frame, bg="#1f2633")
    blue_ban_frame.pack(side="left", padx=5)
    
    def do_blue_multi():
        with gui_lock:
            open_multisearch(gui_data.get("blue", []))
    def do_red_multi():
        with gui_lock:
            open_multisearch(gui_data.get("red", []))
            
    btn_b_multi = tk.Button(b_head, text="🚀 멀티서치", font=("Malgun Gothic", 9, "bold"), bg="#2980b9", fg="white", bd=0, cursor="hand2", command=do_blue_multi)
    btn_b_multi.pack(side="right", padx=10, pady=5)

    r_head = tk.Frame(red_card, bg="#331f1f")
    r_head.pack(fill="x")
    r_title_frame = tk.Frame(r_head, bg="#331f1f")
    r_title_frame.pack(side="left", fill="x", expand=True)
    
    red_title_lbl = tk.Label(r_title_frame, text="🟥 RED TEAM", bg="#331f1f", fg="#ec7063", font=FONT_LF_TITLE, anchor="w", padx=12, pady=6)
    red_title_lbl.pack(side="left")
    
    red_ban_frame = tk.Frame(r_title_frame, bg="#331f1f")
    red_ban_frame.pack(side="left", padx=5)
    btn_r_multi = tk.Button(r_head, text="🚀 멀티서치", font=("Malgun Gothic", 9, "bold"), bg="#c0392b", fg="white", bd=0, cursor="hand2", command=do_red_multi)
    btn_r_multi.pack(side="right", padx=10, pady=5)

    blue_slots = []
    red_slots = []
    
    for i in range(5):
        bf = tk.Frame(blue_card, bg="#1f242e")
        bf.pack(fill="both", expand=True, padx=12, pady=1)
        bz = tk.Frame(bf, bg="#1f242e")
        bz.pack(fill="x", padx=10, pady=1)
        bti = tk.Label(bz, bg="#1f242e")
        bti.pack(side="left")
        btn = tk.Label(bz, text="Wait...", bg="#1f242e", fg="#ffffff", font=FONT_SLOT_NAME)
        btn.pack(side="left", padx=6)
        bcb = tk.Button(bz, text="📋", font=("Malgun Gothic", 9), bg="#2c374e", fg="#ffffff", bd=0, padx=5, pady=0, cursor="hand2")
        bcb.pack(side="left", padx=2)
        b_opgg = tk.Button(bz, text="🔍", font=("Malgun Gothic", 9), bg="#e67e22", fg="#ffffff", bd=0, padx=5, pady=0, cursor="hand2")
        b_opgg.pack(side="left", padx=2)
        tk.Label(bz, text="➡️", bg="#1f242e", fg="#7f8c8d").pack(side="left", padx=4)
        bpi = tk.Label(bz, bg="#1f242e")
        bpi.pack(side="left", padx=4)
        bc_frame_1 = tk.Frame(bf, bg="#1f242e")
        bc_frame_1.pack(fill="x", padx=12, pady=0)
        bsub_1 = tk.Label(bc_frame_1, text="정찰 대기 중...", bg="#1f242e", fg="#a9b3c2", font=FONT_SLOT_STAT, anchor="w")
        bsub_1.pack(side="left")
        bc_frame_2 = tk.Frame(bf, bg="#1f242e")
        bc_frame_2.pack(fill="x", padx=12, pady=0)
        bsub_2 = tk.Label(bc_frame_2, text="", bg="#1f242e", fg="#a9b3c2", font=FONT_SLOT_STAT, anchor="w")
        bsub_2.pack(side="left")
        bc_frame_3 = tk.Frame(bf, bg="#1f242e")
        bc_frame_3.pack(fill="x", padx=12, pady=0)
        bsub_3 = tk.Label(bc_frame_3, text="", bg="#1f242e", fg="#ff4757", font=FONT_SLOT_STAT, anchor="w")
        bsub_3.pack(side="left")
        blue_slots.append((btn, bsub_1, bti, bpi, bcb, bc_frame_1, b_opgg, bc_frame_2, bsub_2, bc_frame_3, bsub_3))

        rf = tk.Frame(red_card, bg="#2e2020")
        rf.pack(fill="both", expand=True, padx=12, pady=1)
        rz = tk.Frame(rf, bg="#2e2020")
        rz.pack(fill="x", padx=10, pady=1)
        rti = tk.Label(rz, bg="#2e2020")
        rti.pack(side="left")
        rtn = tk.Label(rz, text="Wait...", bg="#2e2020", fg="#ffffff", font=FONT_SLOT_NAME)
        rtn.pack(side="left", padx=6)
        rcb = tk.Button(rz, text="📋", font=("Malgun Gothic", 9), bg="#4e2c2c", fg="#ffffff", bd=0, padx=5, pady=0, cursor="hand2")
        rcb.pack(side="left", padx=2)
        r_opgg = tk.Button(rz, text="🔍", font=("Malgun Gothic", 9), bg="#e67e22", fg="#ffffff", bd=0, padx=5, pady=0, cursor="hand2")
        r_opgg.pack(side="left", padx=2)
        tk.Label(rz, text="➡️", bg="#2e2020", fg="#7f8c8d").pack(side="left", padx=4)
        rpi = tk.Label(rz, bg="#2e2020")
        rpi.pack(side="left", padx=4)
        rc_frame_1 = tk.Frame(rf, bg="#2e2020")
        rc_frame_1.pack(fill="x", padx=12, pady=0)
        rsub_1 = tk.Label(rc_frame_1, text="정찰 대기 중...", bg="#2e2020", fg="#c2a9a9", font=FONT_SLOT_STAT, anchor="w")
        rsub_1.pack(side="left")
        rc_frame_2 = tk.Frame(rf, bg="#2e2020")
        rc_frame_2.pack(fill="x", padx=12, pady=0)
        rsub_2 = tk.Label(rc_frame_2, text="", bg="#2e2020", fg="#c2a9a9", font=FONT_SLOT_STAT, anchor="w")
        rsub_2.pack(side="left")
        rc_frame_3 = tk.Frame(rf, bg="#2e2020")
        rc_frame_3.pack(fill="x", padx=12, pady=0)
        rsub_3 = tk.Label(rc_frame_3, text="", bg="#2e2020", fg="#ff4757", font=FONT_SLOT_STAT, anchor="w")
        rsub_3.pack(side="left")
        red_slots.append((rtn, rsub_1, rti, rpi, rcb, rc_frame_1, r_opgg, rc_frame_2, rsub_2, rc_frame_3, rsub_3))

    def update_gui():
        try:
            with gui_lock:
                local_achievements = list(gui_data.get("achievements", []))
                if local_achievements:
                    gui_data["achievements"] = []
                    
                local_status = gui_data.get("status", "")
                local_bans = gui_data.get("bans", "")
                local_b_wr = gui_data.get("blue_win_rate", 50)
                local_r_wr = gui_data.get("red_win_rate", 50)
                local_b_advice = list(gui_data.get("blue_ban_advice_list", []))
                local_r_advice = list(gui_data.get("red_ban_advice_list", []))
                
                local_blue = list(gui_data.get("blue", []))
                local_red = list(gui_data.get("red", []))
                
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
            
            blue_title_lbl.config(text=f"🟦 BLUE TEAM (예상 승률: {local_b_wr}%) | AI 추천 밴: ")
            for widget in blue_ban_frame.winfo_children(): widget.destroy()
            if not local_b_advice:
                tk.Label(blue_ban_frame, text="자유 밴", bg="#1f2633", fg="#5dade2", font=("Malgun Gothic", 11, "bold")).pack(side="left")
            else:
                for champ_name in local_b_advice:
                    img = load_champion_image(champ_name, size=24) 
                    if img:
                        lbl = tk.Label(blue_ban_frame, image=img, bg="#1f2633")
                        lbl.image = img
                        lbl.pack(side="left", padx=2)
                    else:
                        tk.Label(blue_ban_frame, text=champ_name, bg="#1f2633", fg="#5dade2", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=2)

            red_title_lbl.config(text=f"🟥 RED TEAM (예상 승률: {local_r_wr}%) | AI 추천 밴: ")
            for widget in red_ban_frame.winfo_children(): widget.destroy()
            if not local_r_advice:
                tk.Label(red_ban_frame, text="자유 밴", bg="#331f1f", fg="#ec7063", font=("Malgun Gothic", 11, "bold")).pack(side="left")
            else:
                for champ_name in local_r_advice:
                    img = load_champion_image(champ_name, size=24)
                    if img:
                        lbl = tk.Label(red_ban_frame, image=img, bg="#331f1f")
                        lbl.image = img
                        lbl.pack(side="left", padx=2)
                    else:
                        tk.Label(red_ban_frame, text=champ_name, bg="#331f1f", fg="#ec7063", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=2)

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

            for i in range(5):
                if i < len(local_blue):
                    p, s = local_blue[i]
                    name_str = str(p.get('name', ''))
                    lp_str = " | " + str(p.get('lp', 0)) + " LP" if p.get('tier_icon') != "UNRANKED" else ""
                    stk_str = str(s.get("streak", ""))
                    
                    blue_slots[i][0].config(text=name_str + lp_str + stk_str, fg="#5dade2")
                    blue_slots[i][1].config(text=" 전적: " + str(s.get('summary', '')) + " | 모스트: ")
                    for widget in blue_slots[i][5].winfo_children():
                        if widget != blue_slots[i][1]: widget.destroy()
                    
                    for champ_info in s.get("most_list", [])[:3]:
                        img = load_champion_image(champ_info["name"])
                        if img:
                            lbl = tk.Label(blue_slots[i][5], image=img, bg="#1f242e")
                            lbl.image = img; lbl.pack(side="left", padx=2)
                            tk.Label(blue_slots[i][5], text=str(champ_info["count"]) + "판 ", bg="#1f242e", fg="#a9b3c2", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 5))
                        else:
                            tk.Label(blue_slots[i][5], text=str(champ_info["name"]) + "(" + str(champ_info["count"]) + "판) ", bg="#1f242e", fg="#a9b3c2", font=("Malgun Gothic", 10)).pack(side="left", padx=2)

                    blue_slots[i][8].config(text=" 고승률픽: ")
                    for widget in blue_slots[i][7].winfo_children():
                        if widget != blue_slots[i][8]: widget.destroy()
                    
                    op_list = s.get("op_list", [])
                    if not op_list: tk.Label(blue_slots[i][7], text="없음", bg="#1f242e", fg="#a9b3c2", font=("Malgun Gothic", 10)).pack(side="left", padx=2)
                    else:
                        for champ_info in op_list[:3]:
                            img = load_champion_image(champ_info["name"])
                            if img:
                                lbl = tk.Label(blue_slots[i][7], image=img, bg="#1f242e")
                                lbl.image = img; lbl.pack(side="left", padx=2)
                                tk.Label(blue_slots[i][7], text=str(round(champ_info["wr"])) + "% (" + str(champ_info["count"]) + "판) ", bg="#1f242e", fg="#a9b3c2", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 5))
                            else:
                                tk.Label(blue_slots[i][7], text=str(champ_info["name"]) + "(" + str(round(champ_info["wr"])) + "%, " + str(champ_info["count"]) + "판) ", bg="#1f242e", fg="#a9b3c2", font=("Malgun Gothic", 10)).pack(side="left", padx=2)
                    
                    tk.Label(blue_slots[i][7], text="   |   " + str(s.get('side_wr_str', '')), bg="#1f242e", fg="#5dade2", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=5)

                    fatal_bans = s.get("fatal_bans", [])
                    if fatal_bans:
                        fb = fatal_bans[0]
                        text_fb = f"🎯 [약점 발견] '{fb['champ']}' 밴 당할 시 승률 {fb['b_wr']}% (⬇️ {fb['drop']}%p 하락, 표본 {fb['b_games']}게임)"
                        blue_slots[i][10].config(text=text_fb, fg="#ff4757")
                    else:
                        blue_slots[i][10].config(text="", fg="#7f8c8d")

                    ti = tier_images.get(p.get("tier_icon", "UNRANKED"))
                    ci = position_images.get(p.get("chosen_pos_icon", "NONE"))
                    blue_slots[i][2].config(image=ti if ti else ''); blue_slots[i][2].image = ti
                    blue_slots[i][3].config(image=ci if ci else ''); blue_slots[i][3].image = ci
                    
                    blue_slots[i][4].config(command=lambda b=blue_slots[i][4], n=p.get('name', ''): copy_id_to_clipboard(root, b, n), state="normal")
                    blue_slots[i][6].config(command=lambda n=p.get('name', ''): open_opgg_profile(n), state="normal")
                else:
                    blue_slots[i][0].config(text="대기 중...", fg="#7f8c8d")
                    blue_slots[i][1].config(text="소환사를 정찰하고 있습니다.")
                    blue_slots[i][8].config(text="")
                    blue_slots[i][10].config(text="")
                    
                    for widget in blue_slots[i][5].winfo_children():
                        if widget != blue_slots[i][1]: widget.destroy()
                    for widget in blue_slots[i][7].winfo_children():
                        if widget != blue_slots[i][8]: widget.destroy()
                        
                    blue_slots[i][2].config(image='')
                    blue_slots[i][3].config(image='')
                    blue_slots[i][4].config(command=None, state="disabled")
                    blue_slots[i][6].config(command=None, state="disabled")

                if i < len(local_red):
                    p, s = local_red[i]
                    name_str = str(p.get('name', ''))
                    lp_str = " | " + str(p.get('lp', 0)) + " LP" if p.get('tier_icon') != "UNRANKED" else ""
                    stk_str = str(s.get("streak", ""))
                    
                    red_slots[i][0].config(text=name_str + lp_str + stk_str, fg="#ec7063")
                    red_slots[i][1].config(text=" 전적: " + str(s.get('summary', '')) + " | 모스트: ")
                    for widget in red_slots[i][5].winfo_children():
                        if widget != red_slots[i][1]: widget.destroy()
                        
                    for champ_info in s.get("most_list", [])[:3]:
                        img = load_champion_image(champ_info["name"])
                        if img:
                            lbl = tk.Label(red_slots[i][5], image=img, bg="#2e2020")
                            lbl.image = img; lbl.pack(side="left", padx=2)
                            tk.Label(red_slots[i][5], text=str(champ_info["count"]) + "판 ", bg="#2e2020", fg="#c2a9a9", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 5))
                        else:
                            tk.Label(red_slots[i][5], text=str(champ_info["name"]) + "(" + str(champ_info["count"]) + "판) ", bg="#2e2020", fg="#c2a9a9", font=("Malgun Gothic", 10)).pack(side="left", padx=2)

                    red_slots[i][8].config(text=" 고승률픽: ")
                    for widget in red_slots[i][7].winfo_children():
                        if widget != red_slots[i][8]: widget.destroy()
                    
                    op_list = s.get("op_list", [])
                    if not op_list: tk.Label(red_slots[i][7], text="없음", bg="#2e2020", fg="#c2a9a9", font=("Malgun Gothic", 10)).pack(side="left", padx=2)
                    else:
                        for champ_info in op_list[:3]:
                            img = load_champion_image(champ_info["name"])
                            if img:
                                lbl = tk.Label(red_slots[i][7], image=img, bg="#2e2020")
                                lbl.image = img; lbl.pack(side="left", padx=2)
                                tk.Label(red_slots[i][7], text=str(round(champ_info["wr"])) + "% (" + str(champ_info["count"]) + "판) ", bg="#2e2020", fg="#c2a9a9", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 5))
                            else:
                                tk.Label(red_slots[i][7], text=str(champ_info["name"]) + "(" + str(round(champ_info["wr"])) + "%, " + str(champ_info["count"]) + "판) ", bg="#2e2020", fg="#c2a9a9", font=("Malgun Gothic", 10)).pack(side="left", padx=2)
                    
                    tk.Label(red_slots[i][7], text="   |   " + str(s.get('side_wr_str', '')), bg="#2e2020", fg="#ec7063", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=5)

                    fatal_bans = s.get("fatal_bans", [])
                    if fatal_bans:
                        fb = fatal_bans[0]
                        text_fb = f"🎯 [약점 발견] '{fb['champ']}' 밴 당할 시 승률 {fb['b_wr']}% (⬇️ {fb['drop']}%p 하락, 표본 {fb['b_games']}게임)"
                        red_slots[i][10].config(text=text_fb, fg="#ff4757")
                    else:
                        red_slots[i][10].config(text="", fg="#7f8c8d")

                    ti = tier_images.get(p.get("tier_icon", "UNRANKED"))
                    ci = position_images.get(p.get("chosen_pos_icon", "NONE"))
                    red_slots[i][2].config(image=ti if ti else ''); red_slots[i][2].image = ti
                    red_slots[i][3].config(image=ci if ci else ''); red_slots[i][3].image = ci
                    
                    red_slots[i][4].config(command=lambda b=red_slots[i][4], n=p.get('name', ''): copy_id_to_clipboard(root, b, n), state="normal")
                    red_slots[i][6].config(command=lambda n=p.get('name', ''): open_opgg_profile(n), state="normal")
                else:
                    red_slots[i][0].config(text="대기 중...", fg="#7f8c8d")
                    red_slots[i][1].config(text="소환사를 정찰하고 있습니다.")
                    red_slots[i][8].config(text="")
                    red_slots[i][10].config(text="")
                    
                    for widget in red_slots[i][5].winfo_children():
                        if widget != red_slots[i][1]: widget.destroy()
                    for widget in red_slots[i][7].winfo_children():
                        if widget != red_slots[i][8]: widget.destroy()
                        
                    red_slots[i][2].config(image='')
                    red_slots[i][3].config(image='')
                    red_slots[i][4].config(command=None, state="disabled")
                    red_slots[i][6].config(command=None, state="disabled")

            pos_box.configure(state="normal"); pos_box.delete("1.0", tk.END); pos_box.insert(tk.END, str(local_pos_syn)); pos_box.configure(state="disabled")
            neg_box.configure(state="normal"); neg_box.delete("1.0", tk.END); neg_box.insert(tk.END, str(local_neg_syn)); neg_box.configure(state="disabled")
            nemesis_box.configure(state="normal"); nemesis_box.delete("1.0", tk.END); nemesis_box.insert(tk.END, str(local_nem_syn)); nemesis_box.configure(state="disabled")
            
        except Exception: pass 
        finally: root.after(1000, update_gui)

    root.after(1000, update_gui)
    root.mainloop()

class ClanRankingWindow(tk.Toplevel):
    def __init__(self, parent, mode="CLASSIC"):
        super().__init__(parent)
        self.mode = mode
        self.title_text = "스쿼드 명예의 전당 (협곡 프리미엄)" if self.mode == "CLASSIC" else "증내의 전당 (칼바람 프리미엄)"
        self.title(self.title_text)
        self.geometry("1200x850")
        self.configure(bg="#121315")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        self.current_pos = "ALL"
        self.current_ver = "전체 (ALL)"
        
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg="#1a1c1f", height=60)
        top_bar.pack(fill="x", side="top")
        
        header_color = "#F5D47A" if self.mode == "CLASSIC" else "#85c1e9"
        self.title_lbl = tk.Label(top_bar, text=f"🏆 {self.title_text}", bg="#1a1c1f", fg=header_color, font=("Malgun Gothic", 16, "bold"))
        self.title_lbl.pack(side="left", padx=20, pady=15)
        
        btn_frame = tk.Frame(top_bar, bg="#1a1c1f")
        btn_frame.pack(side="right", padx=20, pady=15)
        
        self.btn_refresh = tk.Button(btn_frame, text="🔄 데이터 갱신", font=("Malgun Gothic", 10, "bold"), bg="#4a6984", fg="#ffffff", bd=0, padx=12, pady=4, cursor="hand2", command=self.refresh_action)
        self.btn_refresh.pack(side="right", padx=5)

        tk.Label(btn_frame, text="메타(패치) 필터:", bg="#1a1c1f", fg="#ffffff", font=("Malgun Gothic", 10)).pack(side="left", padx=5)
        
        self.ver_var = tk.StringVar()
        self.ver_combo = ttk.Combobox(btn_frame, textvariable=self.ver_var, state="readonly", width=12, font=("Malgun Gothic", 10))
        self.ver_combo.bind("<<ComboboxSelected>>", self.switch_version)
        self.ver_combo.pack(side="left", padx=5)

        self.pos_frame = tk.Frame(self, bg="#121315")
        self.pos_btns = {}
        
        if self.mode == "CLASSIC":
            self.pos_frame.pack(fill="x", padx=20, pady=5)
            pos_list = [("ALL", "통합"), ("TOP", "탑"), ("JUNGLE", "정글"), ("MIDDLE", "미드"), ("BOTTOM", "원딜"), ("UTILITY", "서폿")]
            for p_key, p_kor in pos_list:
                btn = tk.Button(self.pos_frame, text=p_kor, font=("Malgun Gothic", 11, "bold"), bg="#1e2124", fg="#a0a8b5", bd=0, padx=15, pady=4, cursor="hand2", command=lambda k=p_key: self.switch_pos(k))
                btn.pack(side="left", padx=5)
                self.pos_btns[p_key] = btn

        self.grid_frame = tk.Frame(self, bg="#121315")
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        self.grid_frame.columnconfigure(0, weight=1, uniform="rank_card")
        self.grid_frame.columnconfigure(1, weight=1, uniform="rank_card")
        self.grid_frame.rowconfigure(0, weight=1)
        self.grid_frame.rowconfigure(1, weight=1)
        
        self.update_versions()
        self.render_data()
        
        bot_bar = tk.Frame(self, bg="#121315", height=50)
        bot_bar.pack(fill="x", side="bottom")
        tk.Button(bot_bar, text="닫기", font=("Malgun Gothic", 11, "bold"), bg="#4E6548", fg="#ffffff", bd=0, width=20, pady=6, cursor="hand2", command=self.destroy).pack(pady=10)

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
        self.btn_refresh.config(text="🔄 갱신 중...", state="disabled")
        def worker():
            update_hof_stats(force=True)
            self.after(0, self.update_versions)
            self.after(0, self.render_data)
            self.after(0, lambda: self.btn_refresh.config(text="🔄 데이터 갱신", state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def render_data(self):
        try:
            if self.mode == "CLASSIC":
                for k, btn in self.pos_btns.items():
                    if k == self.current_pos: btn.config(bg="#f39c12", fg="#ffffff")
                    else: btn.config(bg="#1e2124", fg="#a0a8b5")

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
                card = tk.Frame(self.grid_frame, bg="#1a1c1f", bd=0); card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
                header_bg = "#22252a" if stat_type in ["total", "wr"] else "#2a2222" if stat_type == "troll" else "#242823"
                header_fg = "#F5D47A" if stat_type in ["total", "wr"] else "#ec7063" if stat_type == "troll" else "#f1c40f"
                
                if self.mode == "ARAM" and stat_type in ["total", "wr"]: header_fg = "#85c1e9"
                
                lbl_f = tk.Frame(card, bg=header_bg, height=35); lbl_f.pack(fill="x")
                tk.Label(lbl_f, text=title, bg=header_bg, fg=header_fg, font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=12, pady=6)
                box = tk.Text(card, bg="#1e2124", fg="#ffffff", font=("Malgun Gothic", 10), bd=0, highlightthickness=0, padx=12, pady=12); box.pack(fill="both", expand=True)
                
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
                        
                        box.insert(tk.END, f"{medal_str}{pos_info}{name_clean} ➡️ {metric}\n")
                box.configure(state="disabled")

            pos_kor = "통합" if pos == "ALL" else POSITION_TRANSLATE_KOR.get(pos, "선택안함")
            title_prefix = f"[{pos_kor}] " if self.mode == "CLASSIC" else "[증내] "
            patch_txt = f"[{self.current_ver}] " if self.current_ver != "전체 (ALL)" else ""
            
            draw_card(0, 0, f"🎖️ {patch_txt}{title_prefix}망령 TOP 10", most_games, "total")
            draw_card(0, 1, f"📈 {patch_txt}{title_prefix}승률왕 TOP 10", highest_wr, "wr")
            draw_card(1, 0, f"👑 {patch_txt}{title_prefix}MVP 획득률 TOP 10", highest_mvp, "mvp")
            draw_card(1, 1, f"💀 {patch_txt}{title_prefix}역적 지목률 TOP 10", highest_troll, "troll")
        except Exception as e: pass

class PatchNoteWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("패치노트")
        self.geometry("600x450")
        self.configure(bg="#121315")
        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="📜 스쿼드해체분석기 버전별 업데이트 기록", bg="#1a1c1f", fg="#F5D47A", font=("Malgun Gothic", 16, "bold"), pady=15).pack(fill="x")
        txt = scrolledtext.ScrolledText(self, bg="#1e2124", fg="#ffffff", font=("Malgun Gothic", 11), padx=15, pady=15, bd=0)
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        
        notes = [
            "[V80.1] 밴(Ban) 데이터 증발 방어 및 KDA 기록 기능 추가",
            "- (신규) 구글 시트에 KDA(킬/데스/어시)가 직접 기록되는 자동 로깅 기능 개발",
            "- (신규) KDA 열이 없는 기존 사용자들을 위한 시트 자동 업데이트(마이그레이션) 적용",
            "- (수정) 로딩창 렉으로 통신 타임아웃 발생 시 밴 데이터가 강제 초기화되던 버그 완벽 차단",
            "- (수정) 라이엇 통계 API 오류 시 옛날 게임의 밴 데이터로 덮어쓰기 되던 논리 구조 개선",
            "- (수정) 챔피언 ID가 없는 더미 데이터 파싱 중 발생하는 침묵 에러(Silent Error) 해결",
            "",
            "[V80.0] API 쿼터 절약 & 런타임 락(Lock) 엔진 도입",
            "- 다중 스레드 동기화 락(Lock)을 걸어 데이터 증발(빈칸) 버그 원천 차단",
            "- 구글 시트 스마트 캐싱 및 일괄 업데이트(Batch) 도입으로 API 통신 속도 향상",
        ]
        
        for line in notes:
            if line.startswith("["): txt.insert(tk.END, line + "\n", "title")
            else: txt.insert(tk.END, line + "\n\n" + "-"*50 + "\n\n")
        
        txt.tag_config("title", foreground="#5dade2", font=("Malgun Gothic", 12, "bold"))
        txt.configure(state="disabled")

class ClanSettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("환경 설정")
        self.geometry("550x300")
        self.configure(bg="#121315")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg="#1a1c1f", height=55)
        top_bar.pack(fill="x", side="top")
        tk.Label(top_bar, text="⚙️ 환경 설정 (SETTINGS)", bg="#1a1c1f", fg="#F5D47A", font=("Malgun Gothic", 14, "bold")).pack(side="left", padx=20, pady=12)
        body_frame = tk.Frame(self, bg="#121315")
        body_frame.pack(fill="both", expand=True, padx=25, pady=20)
        
        style = ttk.Style()
        style.configure("TCheckbutton", background="#121315", foreground="#ffffff", font=("Malgun Gothic", 10))
        
        self.var_startup = tk.BooleanVar(value=APP_CONFIG.get("windows_startup", False))
        self.var_lol_auto = tk.BooleanVar(value=APP_CONFIG.get("lol_auto_show", True))
        
        opt_f1 = tk.Frame(body_frame, bg="#121315"); opt_f1.pack(fill="x", pady=10)
        txt_f1 = tk.Frame(opt_f1, bg="#121315"); txt_f1.pack(side="left", fill="both")
        tk.Label(txt_f1, text="컴퓨터 부팅 시 스텔스(숨김) 자동 실행", bg="#121315", fg="#ffffff", font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(txt_f1, text="백그라운드에 숨어 대기하며 리소스를 최소화합니다.", bg="#121315", fg="#a0a8b5", font=("Malgun Gothic", 10)).pack(anchor="w", pady=4)
        ttk.Checkbutton(opt_f1, variable=self.var_startup, style="TCheckbutton").pack(side="right", padx=10)

        opt_f2 = tk.Frame(body_frame, bg="#121315"); opt_f2.pack(fill="x", pady=10)
        txt_f2 = tk.Frame(opt_f2, bg="#121315"); txt_f2.pack(side="left", fill="both")
        tk.Label(txt_f2, text="롤 클라이언트 켜질 때 자동 팝업", bg="#121315", fg="#ffffff", font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(txt_f2, text="롤이 켜지는 순간 숨겨진 프로그램이 자동으로 화면에 나타납니다.", bg="#121315", fg="#a0a8b5", font=("Malgun Gothic", 10)).pack(anchor="w", pady=4)
        ttk.Checkbutton(opt_f2, variable=self.var_lol_auto, style="TCheckbutton").pack(side="right", padx=10)
        
        bot_bar = tk.Frame(self, bg="#121315", height=50); bot_bar.pack(fill="x", side="bottom")
        tk.Button(bot_bar, text="설정 및 저장", font=("Malgun Gothic", 11, "bold"), bg="#4e2c2c", fg="#ffffff", bd=0, width=20, pady=6, cursor="hand2", command=self.apply_settings).pack(pady=15)

    def apply_settings(self):
        val_start = self.var_startup.get()
        val_auto = self.var_lol_auto.get()
        APP_CONFIG["windows_startup"] = val_start
        APP_CONFIG["lol_auto_show"] = val_auto
        save_config(APP_CONFIG)
        toggle_windows_startup(val_start)
        self.destroy()

class GuideWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("사용 안내")
        self.geometry("600x420")
        self.configure(bg="#121315")
        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="📖 스쿼드해체분석기 사용 안내", bg="#1a1c1f", fg="#F5D47A", font=("Malgun Gothic", 16, "bold"), pady=15).pack(fill="x")
        txt = tk.Text(self, bg="#1e2124", fg="#ffffff", font=("Malgun Gothic", 11), padx=20, pady=20, bd=0)
        txt.pack(fill="both", expand=True)
        for line in ["1. [🎯저격 밴 분석] 치명적인 승률 하락폭을 즉각 박제합니다.", "2. [🤖AI 밸런서] 상단 🤖버튼을 누르면 최적의 황금 밸런스를 짜줍니다.", "3. [🔗부캐 통합] 구글 시트에 부캐를 등록해두면 완벽히 통합됩니다.", "4. [⚔️라이벌 경보] 적팀에 배치된 상대방과 역대 승률이 극단적일 때 알립니다.", "5. [👑디코 리포트] 게임 종료 시 AI가 MVP와 범인을 리포팅합니다.", "6. [🔥KDA 기록] 구글 시트 내 KDA가 자동 수집 및 기록됩니다."]: txt.insert(tk.END, line + "\n\n")
        txt.configure(state="disabled")

class OnlineUsersWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("실시간 접속자")
        self.geometry("350x450")
        self.configure(bg="#121315")
        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg="#1a1c1f", height=50)
        top_bar.pack(fill="x", side="top")
        tk.Label(top_bar, text="👥 실시간 접속자 현황", bg="#1a1c1f", fg="#2ecc71", font=("Malgun Gothic", 14, "bold")).pack(side="left", padx=20, pady=10)
        self.list_box = scrolledtext.ScrolledText(self, bg="#1e2124", fg="#ffffff", font=("Malgun Gothic", 11), bd=0, highlightthickness=0, padx=15, pady=15)
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
                for row in records[1:]:
                    if len(row) >= 3:
                        try:
                            if current_time - int(row[2]) <= 300: active_users.append("🟢 " + str(row[0]))
                        except Exception: pass
            self.update_list(active_users if active_users else ["💤 현재 접속 중인 다른 유저가 없습니다."])
        except Exception: self.update_list(["❌ 접속자 정보를 불러오지 못했습니다."])

    def update_list(self, items):
        self.list_box.configure(state="normal")
        self.list_box.delete("1.0", tk.END)
        for item in items: self.list_box.insert(tk.END, str(item) + "\n")
        self.list_box.configure(state="disabled")

if __name__ == "__main__":
    if APP_CONFIG.get("windows_startup"):
        toggle_windows_startup(True)
        
    threading.Thread(target=auto_updater_engine, daemon=True).start()
    threading.Thread(target=lcu_core_backend_loop, daemon=True).start()
    threading.Thread(target=ad_banner_engine, daemon=True).start()
    
    create_graphic_ui()