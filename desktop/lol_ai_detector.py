import os
import sys
import base64
import time
import requests
import urllib3
import gspread
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from oauth2client.service_account import ServiceAccountCredentials

try:
    from PIL import Image, ImageTk
    PILLOW_INSTALLED = True
except ImportError:
    PILLOW_INSTALLED = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================================
# 📡 [하이엔드 상업용 마스터 빌드 에디션 - V32.0]
# =========================================================================
CURRENT_VERSION = "32.0"
VERSION_URL = "https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/refs/heads/main/version.txt"
EXE_URL = "https://github.com/kjp1583-art/squad-analyzer/releases/latest/download/squad_analyzer.exe"
DISCORD_WEBHOOK_URL = "여기에_디스코드_웹훅_URL을_붙여넣으세요"
# =========================================================================

DOCUMENT_ID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU'
LOL_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LOL_PATH, "lockfile")

# 💡 [V32.0 상업용 핵심] 프로그램 동작을 실시간 제어하는 글로벌 세팅 오브젝트
app_config = {
    "discord_enabled": True,       # 디스코드 웹훅 전송 활성화
    "aram_split_enabled": True,    # 칼바람나락 데이터 자동 분리 기록
    "scan_interval": 1.0,          # LCU 시스템 탐색 주기 (초 단위)
    "chat_announcement": True      # 대기실 진입 시 안내 멘트 자동 채팅
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

gui_data = {
    "status": "📡 LCU 시스템 탐색 중...",
    "bans": "🚫 10밴 현황: 대기 중",
    "blue": [],
    "red": [],
    "pos_synergy": " - 특이사항 없음 (진영 밸런스 안정적)",
    "neg_synergy": " - 특이사항 없음 (진영 밸런스 안정적)",
    "achievements": [],
    "blue_win_rate": 50,
    "red_win_rate": 50,
    "blue_ban_advice": "없음",
    "red_ban_advice": "없음",
    "global_stats": {},
    "monthly_stats": {}
}

global_captured_bans = []

def copy_id_to_clipboard(window_root, button_widget, full_name):
    if not full_name or full_name in ["Wait...", "대기 중...", "알 수 없는 유저"]: return
    clean_name = full_name.split('#')[0].strip().replace("🤖 ", "").replace(" 봇", "").strip()
    window_root.clipboard_clear()
    window_root.clipboard_append(clean_name)
    button_widget.config(text="✅", fg="#2ecc71")
    window_root.after(1000, lambda: button_widget.config(text="📋", fg="#ffffff"))

def broadcast_to_discord_webhook(content_text):
    if not app_config["discord_enabled"]: return  # 💡 설정 연동: 디코 전송 꺼져있으면 패스
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL.startswith("여기에"): return
    def txt_thread():
        try:
            payload = {"content": f"🏆 **[스쿼드 내전 특수 업적 달성 알림]** 🏆\n```md\n{content_text}\n
```\n*정찰 시스템 V{CURRENT_VERSION} 자동 인증*"}
            requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        except: pass
    threading.Thread(target=txt_thread, daemon=True).start()

# 💡 [V32.0 신설] OP.GG 인터페이스를 오마주한 초고급 플랫 다크 설정 제어판
class ClanSettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("설정")
        self.geometry("600x480")
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

        # 체크박스 변수 바인딩
        var_discord = tk.BooleanVar(value=app_config["discord_enabled"])
        var_aram = tk.BooleanVar(value=app_config["aram_split_enabled"])
        var_chat = tk.BooleanVar(value=app_config["chat_announcement"])

        def create_toggle_option(parent, title, desc, var_target, config_key):
            opt_f = tk.Frame(parent, bg="#121315", pady=10)
            opt_f.pack(fill="x")
            
            txt_f = tk.Frame(opt_f, bg="#121315")
            txt_f.pack(side="left", fill="both")
            tk.Label(txt_f, text=title, bg="#121315", fg="#ffffff", font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
            tk.Label(txt_f, text=desc, bg="#121315", fg="#a0a8b5", font=("Malgun Gothic", 10)).pack(anchor="w", pady=2)
            
            def on_toggle():
                app_config[config_key] = var_target.get()
            
            cb = tk.Checkbutton(opt_f, variable=var_target, bg="#121315", activebackground="#121315", selectcolor="#1a1c1f", bd=0, command=on_toggle)
            cb.pack(side="right", padx=10, pady=5)

        create_toggle_option(body_frame, "디스코드 웹훅 실시간 브로드캐스팅", "특수 업적 달성 발생 시 설정된 디스코드 채널로 실시간 축하 문구를 전송합니다.", var_discord, "discord_enabled")
        
        # 구분선
        tk.Frame(body_frame, bg="#22252a", height=1).pack(fill="x", pady=5)
        
        create_toggle_option(body_frame, "칼바람나락(ARAM) 매치 데이터 자동 분리", "칼바람 나락 매치 감지 시 대기실 장부를 왜곡하지 않고 별도 시트 탭에 기록합니다.", var_aram, "aram_split_enabled")
        
        tk.Frame(body_frame, bg="#22252a", height=1).pack(fill="x", pady=5)
        
        create_toggle_option(body_frame, "대기실 입장 시 안내 문구 자동 채팅", "내전 방 세션이 성립되는 순간 분석기 로딩 완료 알림 메시지를 인게임 룸 채팅으로 사격합니다.", var_chat, "chat_announcement")

        tk.Frame(body_frame, bg="#22252a", height=1).pack(fill="x", pady=5)

        # 정찰 주기 슬라이더 단락
        speed_f = tk.Frame(body_frame, bg="#121315", pady=10)
        speed_f.pack(fill="x")
        txt_s = tk.Frame(speed_f, bg="#121315")
        txt_s.pack(side="left")
        tk.Label(txt_s, text="LCU 레이더 탐색 핵심 주기 설정", bg="#121315", fg="#ffffff", font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(txt_s, text="롤 클라이언트를 스캔하는 초 단위 주기입니다. 낮을수록 정밀하나 과부하를 유발합니다.", bg="#121315", fg="#a0a8b5", font=("Malgun Gothic", 10)).pack(anchor="w", pady=2)

        def on_speed_change(val):
            app_config["scan_interval"] = float(val)

        sp_scale = tk.Scale(speed_f, from_=0.5, to=4.0, resolution=0.5, orient=tk.HORIZONTAL, bg="#121315", fg="#F5D47A", highlightthickness=0, bd=0, length=120, command=on_speed_change)
        sp_scale.set(app_config["scan_interval"])
        sp_scale.pack(side="right", padx=10)

        # 마감 하단바
        bot_bar = tk.Frame(self, bg="#121315", height=50)
        bot_bar.pack(fill="x", side="bottom")
        tk.Button(bot_bar, text="설정 저장 및 닫기", font=("Malgun Gothic", 11, "bold"), bg="#4e2c2c", fg="#ffffff", activebackground="#6b3b3b", bd=0, width=20, pady=6, cursor="hand2", command=self.destroy).pack(pady=15)

class ClanRankingWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("명예의 전당")
        self.geometry("1100x650")
        self.configure(bg="#121315")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg="#1a1c1f", height=60)
        top_bar.pack(fill="x", side="top")
        tk.Label(top_bar, text="🏆 SQUAD CLAN HONOR HALL", bg="#1a1c1f", fg="#F5D47A", font=("Malgun Gothic", 16, "bold")).pack(side="left", padx=20, pady=15)
        
        grid_frame = tk.Frame(self, bg="#121315")
        grid_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        grid_frame.columnconfigure(0, weight=1, uniform="rank_card")
        grid_frame.columnconfigure(1, weight=1, uniform="rank_card")
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.rowconfigure(1, weight=1)

        g_data = gui_data.get("global_stats", {})
        m_data = gui_data.get("monthly_stats", {})

        m_wins = sorted(m_data.items(), key=lambda x: x[1]['wins'], reverse=True)[:5]
        m_wr_list = [item for item in m_data.items() if item[1]['total'] >= 3]
        m_highest_wr = sorted(m_wr_list, key=lambda x: (x[1]['wins'] / x[1]['total']), reverse=True)[:5]
        g_loss_list = [item for item in g_data.items() if item[1]['total'] >= 5]
        g_lowest_wr = sorted(g_loss_list, key=lambda x: (x[1]['wins'] / x[1]['total']), reverse=False)[:5]
        g_most_games = sorted(g_data.items(), key=lambda x: x[1]['total'], reverse=True)[:5]

        def draw_premium_card(parent, row, col, title, data_list, rank_type):
            card = tk.Frame(parent, bg="#1a1c1f", bd=0)
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            
            header_bg = "#22252a" if "이달" in title else "#2a2222" if "패배" in title else "#242823"
            header_fg = "#F5D47A" if "이달" in title else "#ec7063" if "패배" in title else "#5dade2"
            lbl_f = tk.Frame(card, bg=header_bg, height=35)
            lbl_f.pack(fill="x")
            tk.Label(lbl_f, text=title, bg=header_bg, fg=header_fg, font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=12, pady=6)
            
            box = tk.Text(card, bg="#1e2124", fg="#ffffff", font=("Malgun Gothic", 11), bd=0, highlightthickness=0, padx=12, pady=12)
            box.pack(fill="both", expand=True)
            
            if not data_list:
                box.insert(tk.END, chr(10) + " 💤 축적된 장부 데이터가 부족합니다.")
            else:
                for idx, (puuid, s) in enumerate(data_list):
                    name_clean = s['name'].split('#')[0]
                    if rank_type == "wins": metric = f"{s['wins']}승"
                    elif rank_type == "wr": metric = f"{((s['wins']/s['total'])*100):.1f}% ({s['total']}전)"
                    else: metric = f"{s['total']}판"
                    
                    medal = ["🥇 ", "🥈 ", "🥉 ", " 4. ", " 5. "]
                    box.insert(tk.END, f"{medal[idx]}{name_clean} ➡️ {metric}{chr(10)}")
            box.configure(state="disabled")

        draw_premium_card(grid_frame, 0, 0, "🔥 이달의 다승왕 TOP 5 (월간 자동 리셋)", m_wins, "wins")
        draw_premium_card(grid_frame, 0, 1, "📈 이달의 최고 승률왕 TOP 5 (3판↑)", m_highest_wr, "wr")
        draw_premium_card(grid_frame, 1, 0, "🌧️ 명예의 패배왕 TOP 5 (역대 5판↑ / 승률 최저순)", g_lowest_wr, "wr")
        draw_premium_card(grid_frame, 1, 1, "🎖️ 역대 전설의 판수왕 TOP 5 (클랜 기여도)", g_most_games, "total")

        bot_bar = tk.Frame(self, bg="#121315", height=50)
        bot_bar.pack(fill="x", side="bottom")
        tk.Button(bot_bar, text="명예의 전당 닫기", font=("Malgun Gothic", 11, "bold"), bg="#4E6548", fg="#ffffff", activebackground="#384A33", bd=0, width=20, pady=6, cursor="hand2", command=self.destroy).pack(pady=10)

def crunch_sheet_statistics(blue_players, red_players, sheet):
    try:
        raw_data = sheet.get_all_values()
        if len(raw_data) <= 1: return {}, [], []
        rows = raw_data[1:]
    except: return {}, [], []

    player_games = {}
    player_champ_counts = {}
    games_dict = {}
    global_board_data = {}
    monthly_board_data = {}
    
    current_month_token = time.strftime("%Y-%m")
    POS_ENG_MAP = {"탑": "TOP", "정글": "JUNGLE", "미드": "MIDDLE", "원딜": "BOTTOM", "서폿": "UTILITY"}

    for r in rows:
        if len(r) < 9 or r[8] not in ["승리", "패배"]: continue
        g_id, date_str, p_name, p_puuid, t_name, matched_pos, champ, bans_str, res = r[:9]
        p_puuid = p_puuid.strip()
        if not p_puuid: continue
        
        if p_puuid not in global_board_data:
            global_board_data[p_puuid] = {"name": p_name, "total": 0, "wins": 0}
        global_board_data[p_puuid]["total"] += 1
        if res == "승리": global_board_data[p_puuid]["wins"] += 1

        if str(date_str).strip().startswith(current_month_token):
            if p_puuid not in monthly_board_data:
                monthly_board_data[p_puuid] = {"name": p_name, "total": 0, "wins": 0}
            monthly_board_data[p_puuid]["total"] += 1
            if res == "승리": monthly_board_data[p_puuid]["wins"] += 1

        if p_puuid not in player_games:
            player_games[p_puuid] = []
            player_champ_counts[p_puuid] = {}
        
        safe_bans = str(bans_str) if bans_str else ""
        player_games[p_puuid].append({'champ': champ, 'bans': safe_bans, 'result': res, 'pos': matched_pos})
        if champ: player_champ_counts[p_puuid][champ] = player_champ_counts[p_puuid].get(champ, 0) + 1

        if g_id not in games_dict: games_dict[g_id] = {"블루팀": [], "레드팀": [], "winner": ""}
        if t_name == "블루팀":
            games_dict[g_id]["블루팀"].append(p_puuid)
            if res == "승리": games_dict[g_id]["winner"] = "블루팀"
        else:
            games_dict[g_id]["레드팀"].append(p_puuid)
            if res == "승리": games_dict[g_id]["winner"] = "레드팀"

    gui_data["global_stats"] = global_board_data
    gui_data["monthly_stats"] = monthly_board_data

    stats_dashboard = {}
    blue_pool, red_pool = {}, {}

    for p in blue_players + red_players:
        p_puuid = p['puuid'].strip()
        p_matches = player_games.get(p_puuid, [])
        total = len(p_matches)
        
        is_blue = p in blue_players
        current_pool = blue_pool if is_blue else red_pool

        if total == 0:
            stats_dashboard[p_puuid] = {"summary": "기록 없음", "most": "-", "op": "없음", "pos1": "NONE", "pos2": "NONE", "champ_drops": {}, "streak": "", "streak_val": 0}
            continue
        
        wins = sum(1 for m in p_matches if m.get('result') == '승리')
        overall_wr = wins / total
        
        streak_str, streak_val = "", 0
        if p_matches:
            recent_matches = list(reversed(p_matches))
            current_res = recent_matches[0].get('result', '')
            streak_count = 0
            for m in recent_matches:
                if m.get('result') == current_res: streak_count += 1
                else: break
            if current_res == '승리':
                streak_str = f" (🔥{streak_count}연승중)"
                streak_val = streak_count
            elif current_res == '패배':
                streak_str = f" (🌧️{streak_count}연패중)"
                streak_val = -streak_count

        champ_counts = player_champ_counts.get(p_puuid, {})
        if champ_counts:
            sorted_champs = sorted(champ_counts.items(), key=lambda x: x[1], reverse=True)
            most_str = ", ".join([f"{c}({v}판)" for c, v in sorted_champs[:3]])
            top_5_champs = [c for c, _ in sorted_champs[:5]]
            
            for c, v in sorted_champs:
                c_wins = sum(1 for m in p_matches if m.get('champ') == c and m.get('result') == '승리')
                c_wr = (c_wins / v) * 100
                if v >= 3 and c_wr >= 55: current_pool[c] = current_pool.get(c, 0) + (v * (c_wr / 100))
        else:
            most_str = "-"
            top_5_champs = []

        champ_drops = {}
        for c in top_5_champs:
            banned_games = 0
            banned_wins = 0
            for m in p_matches:
                clean_bans = [b.strip() for b in m.get('bans', '').split(',') if b.strip()]
                if c in clean_bans:
                    banned_games += 1
                    if m.get('result') == '승리': banned_wins += 1
            if banned_games > 0:
                banned_wr = banned_wins / banned_games
                wr_drop = (overall_wr - banned_wr) * 100
                champ_drops[c] = max(0, wr_drop)
            else: champ_drops[c] = 0

        op_list = []
        for c, v in sorted_champs[:5]:
            c_wins = sum(1 for m in p_matches if m.get('champ') == c and m.get('result') == '승리')
            c_wr = (c_wins / v) * 100
            if c_wr >= 55.0: op_list.append(f"{c}({c_wr:.0f}%, {v}판)")
        op_str = ", ".join(op_list) if op_list else "없음"

        pos_counts = {}
        for m in p_matches:
            if m.get('pos') and m.get('pos') != "선택안함": pos_counts[m['pos']] = pos_counts.get(m['pos'], 0) + 1
        sorted_pos = sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)
        pos1 = sorted_pos[0][0] if len(sorted_pos) > 0 else "NONE"
        pos2 = sorted_pos[1][0] if len(sorted_pos) > 1 else "NONE"

        stats_dashboard[p_puuid] = {
            "summary": f"{total}전 {wins}승 {total-wins}패 ({(overall_wr*100):.1f}%)",
            "most": most_str, "op": op_str,
            "pos1": POSITION_TRANSLATE.get(pos1, "선택안함"), "pos2": POSITION_TRANSLATE.get(pos2, "선택안함"),
            "champ_drops": champ_drops,
            "streak": streak_str,
            "streak_val": streak_val
        }

    blue_advice_list = sorted(red_pool.items(), key=lambda x: x[1], reverse=True)[:3]
    red_advice_list = sorted(blue_pool.items(), key=lambda x: x[1], reverse=True)[:3]
    gui_data["blue_ban_advice"] = ", ".join([c for c, _ in blue_advice_list]) if blue_advice_list else "자유 밴"
    gui_data["red_ban_advice"] = ", ".join([c for c, _ in red_advice_list]) if red_advice_list else "자유 밴"

    TIER_WEIGHT = {"IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4, "PLATINUM": 5, "EMERALD": 6, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10, "UNRANKED": 4}
    def calculate_team_power(players_list):
        power_sum = 0
        for p in players_list:
            t_score = TIER_WEIGHT.get(p.get('tier_icon', 'UNRANKED'), 4)
            s_data = stats_dashboard.get(p['puuid'], {})
            stk = s_data.get('streak_val', 0)
            power_sum += t_score + (stk * 0.3)
        return power_sum

    blue_power = calculate_team_power(blue_players)
    red_power = calculate_team_power(red_players)
    if blue_power + red_power > 0:
        b_wr = int(50 + ((blue_power - red_power) * 4))
        gui_data["blue_win_rate"] = max(15, min(85, b_wr))
        gui_data["red_win_rate"] = 100 - gui_data["blue_win_rate"]
    else: gui_data["blue_win_rate"], gui_data["red_win_rate"] = 50, 50

    pos_alerts, neg_alerts = [], []
    def check_team_synergy(players, team_label):
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                id1 = players[i]['puuid'].strip()
                id2 = players[j]['puuid'].strip()
                if not id1 or id1.startswith('BOT_') or not id2 or id2.startswith('BOT_'): continue
                duo_games, duo_wins = 0, 0
                for g_id, g_data in games_dict.items():
                    if (id1 in g_data['블루팀'] and id2 in g_data['블루팀']) or (id1 in g_data['레드팀'] and id2 in g_data['레드팀']):
                        duo_games += 1
                        if g_data['winner'] == ('블루팀' if id1 in g_data['블루팀'] else '레드팀'): duo_wins += 1
                if duo_games >= 10:
                    duo_wr = (duo_wins / duo_games) * 100
                    p1_clean = players[i]['name'].split('#')[0]
                    p2_clean = players[j]['name'].split('#')[0]
                    if duo_wr <= 35.0: neg_alerts.append(f" ⚠️ [{team_label}] {p1_clean} & {p2_clean} ({duo_games}전 {duo_wins}승 / 승률 {duo_wr:.0f}%)")
                    elif duo_wr >= 65.0: pos_alerts.append(f" 🔥 [{team_label}] {p1_clean} & {p2_clean} ({duo_games}전 {duo_wins}승 / 승률 {duo_wr:.0f}%)")
                        
    check_team_synergy(blue_players, "블루")
    check_team_synergy(red_players, "레드")
    return stats_dashboard, pos_alerts, neg_alerts

def parse_endgame_achievements(match_data):
    achievements = []
    try:
        game_duration = match_data.get('gameDuration', 0)
        teams = {100: {'kills': 0, 'win': False}, 200: {'kills': 0, 'win': False}}
        for team in match_data.get('teams', []):
            if isinstance(team, dict):
                t_id = team.get('teamId')
                if t_id in teams: teams[t_id]['win'] = (team.get('win') == 'Win')
        participants = match_data.get('participants', [])
        participant_identities = match_data.get('participantIdentities', [])
        id_to_name = {}
        for pi in participant_identities:
            if isinstance(pi, dict):
                p_id = pi.get('participantId')
                player = pi.get('player', {})
                if isinstance(player, dict):
                    name = player.get('gameName') or player.get('summonerName') or f"유저{p_id}"
                    id_to_name[p_id] = name
        for p in participants:
            if isinstance(p, dict):
                t_id = p.get('teamId')
                stats = p.get('stats', {})
                if isinstance(stats, dict) and t_id in teams: teams[t_id]['kills'] += stats.get('kills', 0)
        for p in participants:
            if not isinstance(p, dict): continue
            t_id = p.get('teamId')
            if t_id not in teams: continue
            stats = p.get('stats', {})
            if not isinstance(stats, dict): continue
            p_id = p.get('participantId')
            name = id_to_name.get(p_id, f"유저{p_id}")
            is_win = teams[t_id]['win']
            deaths = stats.get('deaths', 0)
            dmg_dealt = stats.get('totalDamageDealtToChampions', 0)
            dmg_taken = stats.get('totalDamageTaken', 0)
            penta = stats.get('pentaKills', 0)
            p_achieves = []
            if is_win and game_duration <= 960: p_achieves.append("⏱️ [이차가 식기전에] 16분 이전 게임 승리자")
            if is_win and game_duration >= 3000: p_achieves.append("⏳ [진흙탕싸움] 50분 이상 게임 승리자")
            if is_win and deaths == 0: p_achieves.append("🛡️ [불사대마왕] 노데스 게임 승리")
            if is_win and dmg_dealt >= 80000: p_achieves.append("⚔️ [사디스트] 딜량 8만이상 후 승리")
            if is_win and dmg_taken >= 120000: p_achieves.append("🩸 [마조히스트] 받은피해량 12만이상 후 승리")
            if penta >= 1: p_achieves.append(f"💀 [학살자] 펜타킬 달성 ({penta}회)")
            if is_win and (teams[100]['kills'] + teams[200]['kills']) >= 100: p_achieves.append("🔥 [전투민족] 양팀 도합 100킬 이상 승리")
            if p_achieves:
                text_block = "👑 [" + str(name) + "]" + chr(10) + chr(10).join(["  - " + str(a) for a in p_achieves])
                achievements.append(text_block)
    except: pass
    return achievements

def lcu_core_backend_loop():
    global gui_data, global_captured_bans
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(resource_path('credentials.json.json'), scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(DOCUMENT_ID)
        sheet_classic = spreadsheet.get_worksheet(0)
    except:
        gui_data["status"] = "❌ 구글 시트 열쇠 파일(JSON) 누락"
        return

    POSITION_TRANSLATE = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서폿", "NONE": "선택안함", "": "선택안함"}
    global_position_cache, champ_map = {}, {}
    sheet_row_indices = []
    last_lobby_fingerprint, last_chat_game_id = "", ""
    recorded_game_ids = set() 
    active_recording_id = None

    while True:
        try:
            port, password = get_lcu_credentials()
            if port and not champ_map: champ_map = build_translation_map(port, password)
            if not port:
                gui_data["status"] = "💤 롤 클라이언트를 실행해 주세요."
                time.sleep(2)
                continue

            raw_token = f"riot:{password}"
            encoded_token = base64.b64encode(raw_token.encode('utf-8')).decode('utf-8')
            headers = {"Authorization": f"Basic {encoded_token}", "Accept": "application/json"}
            base_url = f"https://127.0.0.1:{port}"

            try:
                flow_res = requests.get(f"{base_url}/lol-gameflow/v1/gameflow-phase", headers=headers, verify=False, timeout=3)
                current_phase = flow_res.json() if flow_res.status_code == 200 else "Lobby"
            except: current_phase = "Lobby"

            detected_ban_ids = set()
            try:
                select_res = requests.get(f"{base_url}/lol-champ-select/v1/session", headers=headers, verify=False, timeout=3)
                if select_res.status_code == 200:
                    s_json = select_res.json()
                    if isinstance(s_json, dict):
                        for act_list in s_json.get('actions') or []:
                            if isinstance(act_list, list):
                                for act in act_list:
                                    if isinstance(act, dict) and act.get('type') == 'ban' and act.get('completed') and act.get('championId', 0) > 0:
                                        detected_ban_ids.add(act['championId'])
                        b_obj = s_json.get('bans') or {}
                        if isinstance(b_obj, dict):
                            for b_id in (b_obj.get('myTeamBans') or []) + (b_obj.get('theirTeamBans') or []):
                                if isinstance(b_id, int) and b_id > 0: detected_ban_ids.add(b_id)
            except: pass

            if detected_ban_ids: global_captured_bans = list(set([champ_map[b_id] for b_id in detected_ban_ids if b_id in champ_map]))

            c100, c200, multi_id = [], [], ""
            try:
                lobby_res = requests.get(f"{base_url}/lol-lobby/v2/lobby", headers=headers, verify=False, timeout=3)
                if lobby_res.status_code == 200:
                    lobby_data = lobby_res.json() or {}
                    members = lobby_data.get('members') or []
                    for m in members:
                        if isinstance(m, dict):
                            if m.get('teamId') == 100: c100.append(m)
                            elif m.get('teamId') == 200: c200.append(m)
                    if not c100 and not c200:
                        game_config = lobby_data.get('gameConfig') or {}
                        if isinstance(game_config, dict):
                            c100 = game_config.get('customTeam100') or []
                            c200 = game_config.get('customTeam200') or []
                    multi_id_raw = lobby_data.get('multiplayerGameId')
                    multi_id = str(multi_id_raw) if multi_id_raw is not None else ""
            except: pass

            if not c100 and not c200:
                try:
                    gf_res = requests.get(f"{base_url}/lol-gameflow/v1/session", headers=headers, verify=False, timeout=3)
                    if gf_res.status_code == 200:
                        gf_json = gf_res.json()
                        if isinstance(gf_json, dict):
                            gd = gf_json.get('gameData') or {}
                            if isinstance(gd, dict):
                                c100 = gd.get('teamOne') or []
                                c200 = gd.get('teamTwo') or []
                except: pass

            # 💡 설정 연동: 자동 알림 비활성화 시 채팅 스킵
            if app_config["chat_announcement"] and multi_id and multi_id != "0" and multi_id != last_chat_game_id:
                threading.Timer(1.5, send_lcu_chat_announcement, args=[f"[분석기 정찰 시스템] v{CURRENT_VERSION} 로딩 완료", headers, base_url]).start()
                last_chat_game_id = multi_id
            
            def parse_team(raw_list):
                parsed = []
                if not raw_list or not isinstance(raw_list, list): return parsed
                for p in raw_list:
                    if not isinstance(p, dict): continue
                    raw_pos = p.get('firstPositionPreference') or p.get('assignedPosition') or p.get('position') or 'NONE'
                    chosen_pos_icon_key = raw_pos if raw_pos in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] else "NONE"
                    rank_tier = "UNRANKED"
                    rank_lp = 0
                    name = p.get('summonerName') or p.get('gameName') or ""
                    puuid = p.get('puuid') or ''
                    s_id = p.get('summonerId') or 0
                    if p.get('isBot') or str(puuid).startswith("BOT_"):
                        bot_id = p.get('botChampionId') or 0
                        champ_name = champ_map.get(bot_id, "봇")
                        name = f"🤖 {champ_name} 봇"
                        puuid = f"BOT_{bot_id}"
                    else:
                        if s_id and not name: name = get_name_by_summoner_id(s_id, headers, base_url)
                        if not name: name = "알 수 없는 유저"
                        if s_id and not puuid:
                            try:
                                su_res = requests.get(f"{base_url}/lol-summoner/v1/summoners/{s_id}", headers=headers, verify=False, timeout=2)
                                if su_res.status_code == 200:
                                    su_json = su_res.json()
                                    if isinstance(su_json, dict): puuid = su_json.get('puuid', '')
                            except: pass
                        if not puuid: puuid = f"TEMP_ID_{s_id}_{name}"
                        try:
                            if puuid and not puuid.startswith("TEMP"):
                                rank_res = requests.get(f"{base_url}/lol-ranked/v1/ranked-stats/{puuid}", headers=headers, verify=False, timeout=2)
                                if rank_res.status_code == 200:
                                    r_json = rank_res.json()
                                    if isinstance(r_json, dict):
                                        queues = r_json.get('queues') or []
                                        solo_q = next((q for q in queues if isinstance(q, dict) and q.get('queueType') == 'RANKED_SOLO_5x5'), None)
                                        if solo_q:
                                            rank_tier = (solo_q.get('tier') or 'UNRANKED').upper()
                                            rank_lp = solo_q.get('leaguePoints') or 0
                        except: pass
                    global_position_cache[puuid] = POSITION_TRANSLATE.get(raw_pos, "선택안함")
                    parsed.append({'name': name, 'puuid': puuid, 'chosen_pos_icon': chosen_pos_icon_key, 'tier_icon': rank_tier, 'lp': rank_lp})
                pw = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
                parsed.sort(key=lambda x: pw.get(x['chosen_pos_icon'], 5)) 
                return parsed

            temp_blue = parse_team(c100)
            temp_red = parse_team(c200)

            lobby_fingerprint = "".join([f"{p['puuid']}" for p in temp_blue + temp_red])
            if lobby_fingerprint != last_lobby_fingerprint:
                cached_stats, cached_pos, cached_neg = crunch_sheet_statistics(temp_blue, temp_red, sheet_classic)
                final_blue, final_red = [], []
                for p in temp_blue:
                    s = cached_stats.get(p['puuid'], {"summary": "-", "most": "-", "op": "-", "pos1": "NONE", "pos2": "NONE", "champ_drops": {}, "streak": ""})
                    final_blue.append((p, s))
                gui_data["blue"] = final_blue
                for p in temp_red:
                    s = cached_stats.get(p['puuid'], {"summary": "-", "most": "-", "op": "-", "pos1": "NONE", "pos2": "NONE", "champ_drops": {}})
                    final_red.append((p, s))
                gui_data["red"] = final_red
                gui_data["pos_synergy"] = chr(10).join(cached_pos) if cached_pos else " - 특이사항 없음 (진영 밸런스 안정적)"
                gui_data["neg_synergy"] = chr(10).join(cached_neg) if cached_neg else " - 역시너지 매칭 없음 (평온)"
                last_lobby_fingerprint = lobby_fingerprint

            if current_phase == "Lobby": gui_data["status"] = "🟢 대기실 정찰 중 (수집 레이더 가동)"
            elif current_phase == "ChampSelect": gui_data["status"] = "🔶 밴픽 진행 중 (라인업 데이터 동결)"
            elif current_phase == "InProgress":
                if active_recording_id: gui_data["status"] = f"🔥 인게임 전적 추적 마킹 활성화 (ID: {active_recording_id})"

            if current_phase == "InProgress": gui_data["bans"] = f"🚫 10밴 현황: {', '.join(global_captured_bans) if global_captured_bans else '없음 (사설/봇방)'}"
            else: gui_data["bans"] = f"🚫 10밴 현황: {', '.join(global_captured_bans) if global_captured_bans else '진행 중'}"

            try:
                live_res = requests.get("https://127.0.0.1:2999/liveclientdata/playerlist", verify=False, timeout=1)
                if live_res.status_code == 200:
                    live_data = live_res.json()
                    if isinstance(live_data, list):
                        fetched_game_id = None
                        try:
                            session_res = requests.get(f"{base_url}/lol-gameflow/v1/session", headers=headers, verify=False, timeout=2)
                            if session_res.status_code == 200:
                                s_json = session_res.json()
                                if isinstance(s_json, dict): fetched_game_id = s_json.get('gameData', {}).get('gameId')
                        except: pass
                        if not fetched_game_id: fetched_game_id = f"CUSTOM_{multi_id}" if multi_id and multi_id != "0" else "CUSTOM_MATCH"
                        
                        if fetched_game_id not in recorded_game_ids:
                            game_mode = "CLASSIC"
                            # 💡 설정 연동: 칼바람 분리가 켜져 있을 때만 모드 감지 루틴 추적
                            if app_config["aram_split_enabled"]:
                                try:
                                    stats_res = requests.get("https://127.0.0.1:2999/liveclientdata/gamestats", verify=False, timeout=1)
                                    if stats_res.status_code == 200: game_mode = stats_res.json().get("gameMode", "CLASSIC")
                                except: pass

                            target_sheet = sheet_classic
                            if game_mode == "ARAM":
                                try: target_sheet = spreadsheet.worksheet("칼바람나락")
                                except:
                                    try:
                                        target_sheet = spreadsheet.add_worksheet(title="칼바람나락", rows="2000", cols="15")
                                        target_sheet.append_row(["게임ID", "날짜", "소환사명", "PUUID", "진영", "포지션", "챔피언", "밴", "결과"])
                                    except: target_sheet = sheet_classic

                            lcu_puuid_map = {}
                            for p in temp_blue + temp_red:
                                clean_name = p['name'].replace("🤖", "").replace(" 봇", "").strip().lower()
                                lcu_puuid_map[clean_name] = p['puuid']

                            rows_to_append = []
                            for p in live_data:
                                if not isinstance(p, dict): continue
                                s_name = p.get('summonerName', '소환사')
                                clean_name_key = s_name.replace(" 봇", "").strip().lower()
                                p_puuid = lcu_puuid_map.get(clean_name_key, "")
                                if not p_puuid and not ("봇" in s_name or "bot" in s_name.lower()):
                                    try:
                                        sum_res = requests.get(f"{base_url}/lol-summoner/v1/summoners?name={clean_name_key}", headers=headers, verify=False, timeout=2)
                                        if sum_res.status_code == 200:
                                            su_json = sum_res.json()
                                            if isinstance(su_json, dict): p_puuid = su_json.get('puuid', '')
                                    except: pass
                                if not p_puuid:
                                    c_name_raw = p.get('championName', 'Bot')
                                    kor_cname = champ_map.get(c_name_raw, c_name_raw)
                                    p_puuid = f"BOT_FALLBACK_{kor_cname}"
                                team_raw = p.get('team', 'ORDER')
                                team_name = "블루팀" if team_raw == "ORDER" else "레드팀"
                                kor_champ = champ_map.get(p.get('championName', '')) or p.get('championName', '')
                                matched_pos = global_position_cache.get(p_puuid, "선택안함")
                                rows_to_append.append([
                                    f"#{fetched_game_id}", time.strftime("%Y-%m-%d"), s_name, p_puuid, team_name, matched_pos, kor_champ, ", ".join(global_captured_bans), "결과 대기"
                                ])
                            if rows_to_append:
                                next_row = len(target_sheet.get_all_values()) + 1
                                target_sheet.append_rows(rows_to_append)
                                sheet_row_indices = [(target_sheet, next_row + i, r[4]) for i, r in enumerate(rows_to_append)]
                                recorded_game_ids.add(fetched_game_id)
                                active_recording_id = fetched_game_id
            except: pass
            
            if current_phase == "EndOfGame" and active_recording_id is not None:
                try:
                    hist_res = requests.get(f"{base_url}/lol-match-history/v1/products/lol/current-summoner/matches", headers=headers, verify=False, timeout=3)
                    if hist_res.status_code == 200:
                        h_json = hist_res.json()
                        if isinstance(h_json, dict):
                            games_wrapper = h_json.get('games', {})
                            if isinstance(games_wrapper, dict):
                                games_list = games_wrapper.get('games', [])
                                if isinstance(games_list, list) and games_list:
                                    match_data = games_list[0]
                                    win_id = next((t.get('teamId') for t in match_data.get('teams', []) if t.get('win') == 'Win'), 0)
                                    for t_sheet, row_num, t_color in sheet_row_indices:
                                        res_str = "승리" if (t_color == "블루팀" and win_id == 100) or (t_color == "레드팀" and win_id == 200) else "패배"
                                        t_sheet.update_cell(row_num, 9, res_str)
                                    achieves_list = parse_endgame_achievements(match_data)
                                    if achieves_list:
                                        gui_data["achievements"] = achieves_list
                                        broadcast_to_discord_webhook(chr(10).join(achieves_list))
                                    active_recording_id, global_captured_bans = None, [] 
                except: pass
        except: pass
        
        # 💡 설정 연동: 사용자가 조정한 LCU 레이더 정찰 주기를 동적으로 주입
        time.sleep(app_config["scan_interval"])

def create_graphic_ui():
    root = tk.Tk()
    root.title(f"스쿼드해체분석기 [Ver {CURRENT_VERSION}]")
    root.geometry("1420x1010") # 💡 광고창 공간 확보를 위해 세로폭 확장 개조
    root.resizable(True, True)
    
    BG_MAIN = "#121315"
    BG_CARD_BLUE = "#191b22"
    BG_CARD_RED = "#221919"
    root.configure(bg=BG_MAIN)

    try:
        icon_path = resource_path("image_10.png")
        icon_image = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, icon_image) 
    except: pass

    position_images, tier_images = {}, {}
    def robust_load_image(file_name, target_size):
        if not PILLOW_INSTALLED: return None
        try:
            img_p = resource_path(file_name)
            if not os.path.exists(img_p): return None
            pil_img = Image.open(img_p)
            pil_img = pil_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(pil_img)
        except: return None

    for pos_key in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]: position_images[pos_key] = robust_load_image(f"{pos_key}.png", 28)
    TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER", "UNRANKED"]
    for tier in TIERS: tier_images[tier] = robust_load_image(f"{tier}.png", 32)

    FONT_TITLE = ("Malgun Gothic", 24, "bold")
    FONT_CREDIT = ("Malgun Gothic", 12)
    FONT_STATUS = ("Malgun Gothic", 13, "bold")
    FONT_BANS = ("Malgun Gothic", 13)
    FONT_LF_TITLE = ("Malgun Gothic", 12, "bold")
    FONT_SLOT_NAME = ("Malgun Gothic", 14, "bold")
    FONT_SLOT_STAT = ("Malgun Gothic", 11)
    FONT_SYNERGY = ("Malgun Gothic", 12)

    header = tk.Frame(root, bg="#1a1c1f", height=80)
    header.pack(fill="x", side="top", padx=0, pady=0)

    left_header = tk.Frame(header, bg="#1a1c1f")
    left_header.pack(side="left", padx=20)

    try:
        img_path = resource_path("yumi_avatar.png")
        yumi_img = tk.PhotoImage(file=img_path).subsample(5, 5)
        img_label = tk.Label(left_header, image=yumi_img, bg="#1a1c1f")
        img_label.image = yumi_img
        img_label.pack(side="left", padx=5)
    except: pass

    text_frame = tk.Frame(left_header, bg="#1a1c1f")
    text_frame.pack(side="left", padx=5)
    tk.Label(text_frame, text="스쿼드해체분석기", bg="#1a1c1f", fg="#F5D47A", font=FONT_TITLE).pack(anchor="w")
    
    sub_ctrl_frame = tk.Frame(text_frame, bg="#1a1c1f")
    sub_ctrl_frame.pack(anchor="w")
    tk.Label(sub_ctrl_frame, text="맛동산장인 유미#Teana | ", bg="#1a1c1f", fg="#a0a8b5", font=FONT_CREDIT).pack(side="left")
    
    btn_rank_board = tk.Button(sub_ctrl_frame, text="🏆 명예의 전당", font=("Malgun Gothic", 10, "bold"), bg="#b33939", fg="#ffffff", activebackground="#8c1c1c", activeforeground="#ffffff", bd=0, padx=8, pady=2, cursor="hand2")
    btn_rank_board.pack(side="left", padx=3)
    btn_rank_board.config(command=lambda: ClanRankingWindow(root))

    # 💡 [V32.0 설정 버튼 엠블럼 스냅인]
    btn_settings = tk.Button(sub_ctrl_frame, text="⚙️ 설정", font=("Malgun Gothic", 10, "bold"), bg="#2c3e50", fg="#ffffff", activebackground="#1a252f", activeforeground="#ffffff", bd=0, padx=10, pady=2, cursor="hand2")
    btn_settings.pack(side="left", padx=3)
    btn_settings.config(command=lambda: ClanSettingsWindow(root))

    right_header = tk.Frame(header, bg="#1a1c1f")
    right_header.pack(side="right", padx=20)

    status_var = tk.StringVar(value="📡 LCU 통신 탐색 레이더 가동 중...")
    tk.Label(right_header, textvariable=status_var, bg="#1a1c1f", fg="#2ecc71", font=FONT_STATUS).pack(anchor="e", pady=1)

    bans_var = tk.StringVar(value="🚫 10밴 현황: 대기 중")
    tk.Label(right_header, textvariable=bans_var, bg="#1a1c1f", fg="#bdc3c7", font=FONT_BANS).pack(anchor="e", pady=1)

    # 💡 [V32.0 상업화 패키지] 메인 윈도우 최하단 프리미엄 광고 배포 슬롯
    ad_bar = tk.Frame(root, bg="#1f2226", height=50)
    ad_bar.pack(fill="x", side="bottom", padx=0, pady=0)
    
    def open_ad_link():
        # 실제 광고 웹페이지나 제어 링크로 연동 창구 개설 가능
        webbrowser.open("https://github.com/kjp1583-art/squad-analyzer")

    btn_ad = tk.Button(ad_bar, text="🔥 [PREMIUM SPONSOR] 전적 유저 수동 조회 및 내전 듀오 신청 바로가기 🔗 | 광고 제휴 문의: 유미#Teana", font=("Malgun Gothic", 11, "bold"), bg="#1f2226", fg="#F5D47A", activebackground="#2c313a", activeforeground="#F5D47A", bd=0, relief="flat", justify="center", cursor="hand2", command=open_ad_link)
    btn_ad.pack(fill="both", expand=True)

    bottom_container = tk.Frame(root, bg=BG_MAIN)
    bottom_container.pack(fill="x", side="bottom", padx=20, pady=15)
    bottom_container.columnconfigure(0, weight=1, uniform="team_half") 
    bottom_container.columnconfigure(1, weight=1, uniform="team_half")

    pos_card = tk.Frame(bottom_container, bg="#1a1c1f")
    pos_card.grid(row=0, column=0, sticky="nsew", padx=6)
    tk.Label(pos_card, text="🔥 무적 듀오 시너지 리포트 (10판이상 / 승률 65% ▲)", bg="#242823", fg="#2ecc71", font=FONT_LF_TITLE, anchor="w", padx=10).pack(fill="x")
    pos_box = scrolledtext.ScrolledText(pos_card, height=5, bg="#161719", fg="#2ecc71", font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    pos_box.pack(fill="both", expand=True)
    pos_box.configure(state="disabled")

    neg_card = tk.Frame(bottom_container, bg="#1a1c1f")
    neg_card.grid(row=0, column=1, sticky="nsew", padx=6)
    tk.Label(neg_card, text="⚠️ 역시너지 경보 명단 (10판이상 / 승률 35% ▼)", bg="#2a2222", fg="#ec7063", font=FONT_LF_TITLE, anchor="w", padx=10).pack(fill="x")
    neg_box = scrolledtext.ScrolledText(neg_card, height=5, bg="#161719", fg="#ec7063", font=FONT_SYNERGY, bd=0, highlightthickness=0, padx=8, pady=8)
    neg_box.pack(fill="both", expand=True)
    neg_box.configure(state="disabled")

    body = tk.Frame(root, bg=BG_MAIN)
    body.pack(fill="both", expand=True, padx=20, pady=10)
    body.columnconfigure(0, weight=1, uniform="team_half") 
    body.columnconfigure(1, weight=1, uniform="team_half")

    blue_card = tk.Frame(body, bg=BG_CARD_BLUE)
    blue_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=5)
    blue_title_lbl = tk.Label(blue_card, text="🟦 BLUE TEAM", bg="#1f2633", fg="#5dade2", font=FONT_LF_TITLE, anchor="w", padx=12, pady=6)
    blue_title_lbl.pack(fill="x")

    red_card = tk.Frame(body, bg=BG_CARD_RED)
    red_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=5)
    red_title_lbl = tk.Label(red_card, text="🟥 RED TEAM", bg="#331f1f", fg="#ec7063", font=FONT_LF_TITLE, anchor="w", padx=12, pady=6)
    red_title_lbl.pack(fill="x")

    blue_slots, red_slots = [], []
    for idx in range(5):
        bf = tk.Frame(blue_card, bg="#1f242e", height=75)
        bf.pack(fill="both", expand=True, padx=12, pady=6)
        bz = tk.Frame(bf, bg="#1f242e")
        bz.pack(fill="x", padx=10, pady=4)
        bti = tk.Label(bz, bg="#1f242e")
        bti.pack(side="left")
        btn = tk.Label(bz, text="Wait...", bg="#1f242e", fg="#ffffff", font=FONT_SLOT_NAME)
        btn.pack(side="left", padx=6)
        bcb = tk.Button(bz, text="📋", font=("Malgun Gothic", 9), bg="#2c374e", fg="#ffffff", activebackground="#3b4b6b", bd=0, padx=5, pady=1, cursor="hand2")
        bcb.pack(side="left", padx=4)
        tk.Label(bz, text="➡️", bg="#1f242e", fg="#7f8c8d").pack(side="left", padx=4)
        bpi = tk.Label(bz, bg="#1f242e")
        bpi.pack(side="left", padx=4)
        bsub = tk.Label(bf, text="정찰 대기 중...", bg="#1f242e", fg="#a9b3c2", font=FONT_SLOT_STAT, anchor="nw", justify="left")
        bsub.pack(fill="both", expand=True, padx=12, pady=2)
        blue_slots.append((btn, bsub, bti, bpi, bcb, bf))

        rf = tk.Frame(red_card, bg="#2e2020", height=75)
        rf.pack(fill="both", expand=True, padx=12, pady=6)
        rz = tk.Frame(rf, bg="#2e2020")
        rz.pack(fill="x", padx=10, pady=4)
        rti = tk.Label(rz, bg="#2e2020")
        rti.pack(side="left")
        rtn = tk.Label(rz, text="Wait...", bg="#2e2020", fg="#ffffff", font=FONT_SLOT_NAME)
        rtn.pack(side="left", padx=6)
        rcb = tk.Button(rz, text="📋", font=("Malgun Gothic", 9), bg="#4e2c2c", fg="#ffffff", activebackground="#6b3b3b", bd=0, padx=5, pady=1, cursor="hand2")
        rcb.pack(side="left", padx=4)
        tk.Label(rz, text="➡️", bg="#2e2020", fg="#7f8c8d").pack(side="left", padx=4)
        rpi = tk.Label(rz, bg="#2e2020")
        rpi.pack(side="left", padx=4)
        rsub = tk.Label(rf, text="정찰 대기 중...", bg="#2e2020", fg="#c2a9a9", font=FONT_SLOT_STAT, anchor="nw", justify="left")
        rsub.pack(fill="both", expand=True, padx=12, pady=2)
        red_slots.append((rtn, rsub, rti, rpi, rcb, rf))

    def update_gui():
        if gui_data.get("achievements"):
            at = chr(10).join(gui_data["achievements"])
            gui_data["achievements"] = [] 
            messagebox.showinfo("🏆 내전 타이틀 달성 알림!", "아래 유저들이 특수 타이틀 조건을 달성했습니다!" + chr(10) + chr(10) + at)

        status_var.set(gui_data["status"])
        bans_var.set(gui_data["bans"])
        
        blue_title_lbl.config(text=f" 🟦 BLUE TEAM (예상 승률: {gui_data['blue_win_rate']}% | AI 추천 밴: {gui_data['blue_ban_advice']}) ")
        red_title_lbl.config(text=f" 🟥 RED TEAM (예상 승률: {gui_data['red_win_rate']}% | AI 추천 밴: {gui_data['red_ban_advice']}) ")

        for i in range(5):
            if i < len(gui_data["blue"]):
                p, s = gui_data["blue"][i]
                rs = f"| {p['lp']} LP" if p['tier_icon'] != "UNRANKED" else ""
                stk = s.get("streak", "")
                cd = [dv for bc, dv in s.get("champ_drops", {}).items() if bc in global_captured_bans and dv > 0]
                ds = f" (🎯-{max(cd):.0f}%)" if cd else ""
                blue_slots[i][0].config(text=p['name'] + " " + rs + stk + ds, fg="#5dade2")
                blue_slots[i][1].config(text=f" 전적: {s['summary']} | 꿀챔: {s['op']}\n 모스트: {s['most']}")
                ti = tier_images.get(p.get("tier_icon", "UNRANKED"))
                blue_slots[i][2].config(image=ti if ti else '')
                blue_slots[i][2].image = ti
                ci = position_images.get(p.get("chosen_pos_icon", "NONE"))
                blue_slots[i][3].config(image=ci if ci else '')
                blue_slots[i][3].image = ci
                blue_slots[i][4].config(command=lambda b=blue_slots[i][4], n=p.get('name', ''): copy_id_to_clipboard(root, b, n), state="normal", text="📋")
            else:
                blue_slots[i][0].config(text="대기 중...", fg="#7f8c8d")
                blue_slots[i][1].config(text="소환사를 정찰하고 있습니다.")
                blue_slots[i][2].config(image='')
                blue_slots[i][3].config(image='')
                blue_slots[i][4].config(command=None, state="disabled", text="📋")
                
            if i < len(gui_data["red"]):
                p, s = gui_data["red"][i]
                rs = f"| {p['lp']} LP" if p['tier_icon'] != "UNRANKED" else ""
                stk = s.get("streak", "")
                cd = [dv for bc, dv in s.get("champ_drops", {}).items() if bc in global_captured_bans and dv > 0]
                ds = f" (🎯-{max(cd):.0f}%)" if cd else ""
                red_slots[i][0].config(text=p['name'] + " " + rs + stk + ds, fg="#ec7063")
                red_slots[i][1].config(text=f" 전적: {s['summary']} | 꿀챔: {s['op']}" + chr(10) + f" 모스트: {s['most']}")
                ti = tier_images.get(p.get("tier_icon", "UNRANKED"))
                red_slots[i][2].config(image=ti if ti else '')
                red_slots[i][2].image = ti
                ci = position_images.get(p.get("chosen_pos_icon", "NONE"))
                red_slots[i][3].config(image=ci if ci else '')
                red_slots[i][3].image = ci
                red_slots[i][4].config(command=lambda b=red_slots[i][4], n=p.get('name', ''): copy_id_to_clipboard(root, b, n), state="normal", text="📋")
            else:
                red_slots[i][0].config(text="대기 중...", fg="#7f8c8d")
                red_slots[i][1].config(text="소환사를 정찰하고 있습니다.")
                red_slots[i][2].config(image='')
                red_slots[i][3].config(image='')
                red_slots[i][4].config(command=None, state="disabled", text="📋")
        
        pos_box.configure(state="normal")
        pos_box.delete("1.0", tk.END)
        pos_box.insert(tk.END, gui_data["pos_synergy"])
        pos_box.configure(state="disabled")
        neg_box.configure(state="normal")
        neg_box.delete("1.0", tk.END)
        neg_box.insert(tk.END, gui_data["neg_synergy"])
        neg_box.configure(state="disabled")
        
        # 💡 설정 연동: 사용자가 조정한 프레임 레이트로 GUI 갱신 틱 동적 제어
        root.after(int(app_config["scan_interval"] * 800), update_gui)

    root.after(800, update_gui)
    root.mainloop()

if __name__ == "__main__":
    threading.Thread(target=lcu_core_backend_loop, daemon=True).start()
    create_graphic_ui()