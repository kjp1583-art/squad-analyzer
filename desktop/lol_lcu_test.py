import os
import base64
import requests
import urllib3

# 보안 경고 메시지 끄기 (롤 로컬 서버가 자체 인증서를 써서 뜨는 경고 방지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. 롤 표준 설치 경로 지정
LOL_PATH = r"C:\Riot Games\League of Legends"
LOCKFILE_PATH = os.path.join(LOL_PATH, "lockfile")

print("🔍 롤 클라이언트의 비밀 열쇠(lockfile)를 찾는 중...")

if not os.path.exists(LOCKFILE_PATH):
    print("\n❌ 롤 클라이언트가 켜져 있지 않거나 경로가 잘못되었습니다!")
    print("👉 반드시 '롤 클라이언트'를 로그인까지 완료한 상태에서 이 코드를 실행해 주세요.\n")
    exit()

try:
    # 2. lockfile 열어서 포트 번호와 비밀번호 뜯어내기
    with open(LOCKFILE_PATH, "r") as f:
        lockfile_content = f.read()

    # 데이터 구조: processName:PID:Port:Password:Protocol
    parts = lockfile_content.split(":")
    port = parts[2]
    password = parts[3]
    
    print(f"🔑 열쇠 확보 성공! (연결 포트: {port})")

    # 3. 라이엇 서버 접속용 인증 토큰 생성 (아이디는 무조건 'riot'으로 고정)
    raw_token = f"riot:{password}"
    encoded_token = base64.b64encode(raw_token.encode('utf-8')).decode('utf-8')
    
    headers = {
        "Authorization": f"Basic {encoded_token}",
        "Accept": "application/json"
    }

    # 4. 테스트: 현재 로그인한 소환사 정보 API 호출
    url = f"https://127.0.0.1:{port}/lol-summoner/v1/current-summoner"
    
    print("📡 롤 내부 서버에 닉네임 정보를 요청합니다...")
    response = requests.get(url, headers=headers, verify=False)
    
    if response.status_code == 200:
        user_data = response.json()
        print("\n" + "="*50)
        print("🎉 [LCU API 연결 완벽하게 성공!] 🎉")
        print(f"📡 현재 로그인된 계정: {user_data.get('displayName')}")
        print(f"⭐ 소환사 레벨: {user_data.get('summonerLevel')}")
        print("="*50 + "\n")
        print("화면 캡처 없이 '스킨 무시/진영 완벽 구별' 장부로 가기 위한 첫 단추가 끼워졌습니다!")
    else:
        print(f"❌ 서버 응답 실패 (에러 코드: {response.status_code})")

except Exception as e:
    print(f"❌ 에러 발생: {e}")