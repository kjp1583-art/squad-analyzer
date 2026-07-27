# 스쿼드 해체 분석기 (Squad Analyzer)

리그 오브 레전드 클랜 내전(custom game) 도구입니다. LoL 클라이언트(LCU)를 읽어
팀 밸런스를 분석하고, 경기 기록을 구글 시트에 저장하며, Discord 웹훅으로 결과를
공지합니다. Windows 단일 실행파일(onefile exe, PyInstaller).

## 다운로드 / 설치

최신 서명된 빌드:
[releases/latest](https://github.com/kjp1583-art/squad-analyzer/releases/latest) →
`squad_analyzer.zip` 다운로드 → 압축 해제 → `squad_analyzer.exe` 실행.

배포본은 SignPath Foundation(무료 OSS 코드서명)으로 Authenticode 서명되어 있어
SmartScreen/Defender 차단이 줄어듭니다. 앱은 실행 시 최신 릴리스로 자동 업데이트됩니다.

## 소스로 빌드하기

- 요구사항: Windows, Python 3.14 (`py -3.14`), `pip install -r requirements.txt`,
  `pip install pyinstaller==6.21.0`.
- 비밀값 파일을 직접 준비하세요(저장소엔 포함되지 않음):
  - `app_secrets.py` — `app_secrets.example.py` 를 복사해 Discord 웹훅 URL / IPC client id 를 채움
  - `credentials.json.json` — 구글 서비스계정 키(시트 접근용)
  - 선택: 실행 PC에 `token.txt`(봇 토큰) / `riot_key.txt`(Riot API 키)
- 빌드: `pyinstaller --clean squad_analyzer.spec` → `dist/squad_analyzer.exe`

## 비밀값 & CI

이 저장소에는 Discord 웹훅이나 구글 서비스계정 키가 **포함되어 있지 않습니다.**
공식 서명 릴리스는 GitHub Actions(`.github/workflows/build-sign-release.yml`)가
GitHub 저장소 Secrets 에서 값을 주입해 빌드합니다. 로컬 빌드는 위의 비밀값 파일을
직접 두면 됩니다.

### 릴리스 절차
1. `squad_analyzer.py` 의 `CURRENT_VERSION` 을 올리고 커밋
2. `vNN.NN` 태그를 푸시 (예: `git tag v81.23 && git push origin v81.23`)
3. CI가 빌드 → SignPath 서명 → 릴리스에 서명된 exe/zip 게시 + `version.txt` 갱신
   (CI가 태그값으로 `CURRENT_VERSION` 과 `version.txt` 를 동기화하므로 자동 업데이트가 정확히 동작)

## 코드 서명

서명은 SignPath Foundation 무료 OSS 프로그램으로 GitHub Actions 안에서 수행됩니다.
개인키는 SignPath 클라우드를 벗어나지 않으며, 메인테이너는 키를 보유하지 않습니다.

## 라이선스

[MIT](LICENSE)

## 관련

- Discord 내전 큐봇은 별도의 비공개 저장소에 있습니다.
- op.gg 스타일 전적검색 사이트(`index.html`)는 이 저장소의 GitHub Pages 로 제공됩니다.
