# 운영 규칙 (사장님 지시 기록)

## 릴리스 정책 (2026-07-27 지시)
- **웹(squad.gg) 패치**: 묻지 말고 바로 반영 (머지·배포까지 자동 진행, BUILD_ID 타임스탬프 치환 필수)
- **봇(squad-naejeon-bot) 패치**: 묻지 말고 바로 반영 (머지 시 Koyeb 자동 재배포)
- **분석기(desktop) 패치**: 사장님이 명시적으로 지시할 때만 릴리스

## 주간평 (AI_EVAL)
- 매주 월요일 자동 생성 (예약 등록됨) → `ai-eval-data` 브랜치 `ai_eval_latest.json` → Apps Script가 6시간마다 시트 반영
- 말투: 전원 부드러운 제안형 (규칙: `ai-eval-data` 브랜치 `tooling/STYLE.md`)

## 봇 (squad-naejeon-bot)
- 저장소가 최신 기준 (2026-07-26 이후). 구버전 사본(핸드오프 폴더 등)으로 덮어쓰지 말 것.
- 분석기 미가동 경고: ONLINE_USERS 하트비트 12분 내면 경고 생략 (2026-07-27 오탐 수정)

## 배포 참고
- 웹은 GitHub Pages (main 머지 = 자동 배포). 봇은 Koyeb이 main을 바라봄.
- 비밀키(riot_key, token, credentials)는 GitHub에 절대 올리지 않음 — 드라이브/PC/Koyeb 환경변수로만.
