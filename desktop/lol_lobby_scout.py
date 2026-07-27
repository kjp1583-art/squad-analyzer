import os
import base64
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOL_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LOL_PATH, "lockfile")

print("🛰️ [정찰 엔진 V6.1] 타겟 서랍(Team100/200) 정밀 동기화 시스템 가동...")

def get_lcu_credentials():
    if not os.path.exists(LOCKFILE_PATH):
        return None, None
    with open(LOCKFILE_PATH, "r") as f:
        content = f.read()
    parts = content.split(":")
    return parts[2], parts[3]

# 소환사 고유 ID로 라이엇 서버에서 진짜 닉네임#태그 100% 복구
def get_name_by_summoner_id(summoner_id, headers, base_url):
    if not summoner_id or summoner_id == 0:
        return "알 수 없는 유저"
    try:
        url = f"{base_url}/lol-summoner/v1/summoners/{summoner_id}"
        res = requests.get(url, headers=headers, verify=False)
        if res.status_code == 200:
            data = res.json()
            name = data.get('gameName') or data.get('displayName') or "소환사"
            tag = data.get('tagLine') or "KR1"
            return f"{name}#{tag}"
    except:
        pass
    return f"소환사({summoner_id})"

# 영문 포지션 코드를 직관적인 한글표기로 치환
POSITION_TRANSLATE = {
    "TOP": "🟦 TOP (탑)",
    "JUNGLE": "🟩 JUG (정글)",
    "MIDDLE": "🟪 MID (미드)",
    "BOTTOM": "🟥 ADC (원딜)",
    "UTILITY": "🟨 SUP (서폿)",
    "FILL": "🎲 FILL (채우기)",
    "NONE": "⚪ 선택 안 함",
    "": "⚪ 선택 안 함"
}

last_lobby_state = ""

try:
    while True:
        port, password = get_lcu_credentials()
        if not port:
            time.sleep(2)
            continue

        raw_token = f"riot:{password}"
        encoded_token = base64.b64encode(raw_token.encode('utf-8')).decode('utf-8')
        headers = {"Authorization": f"Basic {encoded_token}", "Accept": "application/json"}
        base_url = f"https://127.0.0.1:{port}"

        try:
            lobby_res = requests.get(f"{base_url}/lol-lobby/v2/lobby", headers=headers, verify=False)
            
            if lobby_res.status_code == 200:
                lobby_data = lobby_res.json()
                game_config = lobby_data.get('gameConfig', {})
                
                # 상준님 로그에서 체포한 진짜 블루/레드 서랍 타격
                custom_team_100 = game_config.get('customTeam100', [])
                custom_team_200 = game_config.get('customTeam200', [])
                
                lobby_fingerprint = ""
                blue_lineup = []
                red_lineup = []
                
                # 1. 블루 팀 (TEAM 100) 파싱
                for idx, p in enumerate(custom_team_100):
                    if p.get('isBot'):
                        b_id = p.get('botChampionId', 'AI')
                        name = f"🤖 컴퓨터_봇(ID:{b_id})"
                        raw_pos = p.get('botPosition', 'NONE')
                    else:
                        s_id = p.get('summonerId', 0)
                        name = get_name_by_summoner_id(s_id, headers, base_url)
                        raw_pos = p.get('firstPositionPreference', 'NONE')
                        
                    kor_pos = POSITION_TRANSLATE.get(raw_pos, f"기타({raw_pos})")
                    lobby_fingerprint += f"{name}_{raw_pos}_"
                    blue_lineup.append(f" 의자 {idx+1}: {name.ljust(22)} ➡️ 포지션: {kor_pos}")
                    
                # 2. 레드 팀 (TEAM 200) 파싱
                for idx, p in enumerate(custom_team_200):
                    if p.get('isBot'):
                        b_id = p.get('botChampionId', 'AI')
                        name = f"🤖 컴퓨터_봇(ID:{b_id})"
                        raw_pos = p.get('botPosition', 'NONE')
                    else:
                        s_id = p.get('summonerId', 0)
                        name = get_name_by_summoner_id(s_id, headers, base_url)
                        raw_pos = p.get('firstPositionPreference', 'NONE')
                        
                    kor_pos = POSITION_TRANSLATE.get(raw_pos, f"기타({raw_pos})")
                    lobby_fingerprint += f"{name}_{raw_pos}_"
                    red_lineup.append(f" 의자 {idx+1}: {name.ljust(22)} ➡️ 포지션: {kor_pos}")

                # 포지션 딸깍이거나 유저 인원 변동 시 새로고침
                if lobby_fingerprint != last_lobby_state:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print("=" * 65)
                    print("🎯 [사설 내전방 10인 실시간 포지션 정찰 대시보드] 🎯")
                    print("=" * 65)
                    
                    print("\n🟦 [왼쪽 팀 상황] (블루진영)")
                    if not blue_lineup: print(" 👤 명단 대기 중...")
                    for line in blue_lineup: print(line)
                        
                    print("\n🟥 [오른쪽 팀 상황] (레드진영)")
                    if not red_lineup: print(" 👤 명단 대기 중...")
                    for line in red_lineup: print(line)
                        
                    print("\n" + "=" * 65)
                    print("💡 대기실에서 포지션을 마우스로 변경하면 1초 만에 실시간 갱신됩니다.")
                    last_lobby_state = lobby_fingerprint
            else:
                print(f"📡 사설방 대기실 접속 시도 중... (상태 코드: {lobby_res.status_code})  ", end="\r")
                last_lobby_state = ""
                
        except Exception as e:
            pass

        time.sleep(1)

except KeyboardInterrupt:
    print("\n👋 정찰 프로그램을 안전하게 종료합니다.")