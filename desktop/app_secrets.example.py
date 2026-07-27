# app_secrets.example.py
# 이 파일을 복사해서 app_secrets.py 로 만든 뒤 실제 값을 채우세요.
#   (Windows)  copy app_secrets.example.py app_secrets.py
# app_secrets.py 는 .gitignore 에 등록되어 커밋되지 않습니다.
# 공식 서명 릴리스는 GitHub Actions 가 GitHub Secrets 에서 이 값들을 주입해 빌드합니다.
DISCORD_WEBHOOK_URL   = ""    # Discord 내전기록 채널 웹훅 URL
PATCH_WEBHOOK_URL     = ""    # Discord 패치노트 채널 웹훅 URL
DISCORD_IPC_CLIENT_ID = ""    # Discord 앱 client id (반공개)
