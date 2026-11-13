# TASK — 브장신 키우기(웹) 대형 작업 갈래

## 공통 맥락 (먼저 읽어라)
- 저장소 둘: **squad-analyzer(웹, 이 저장소)** + **squad-naejeon-bot(서버 bot.py)**. 두 저장소의 `CLAUDE.md` 를 먼저 읽고 규칙(패치노트 `data/patch_notes.json`·BUILD_ID·장비 끼워 시험·모델 이름 금지·키 금지)을 따른다. 봇 저장소는 `mcp__Claude_Code_Remote__add_repo`(owner kjp1583-art, repo squad-naejeon-bot, access push)로 붙인 뒤 clone 한다.
- 웹 브장신 키우기 = `brjhunt.html` + `brjhunt_arena.js`(캔버스 엔진). 서버 = `bot.py` 의 `BRJ2:*` 구역(`BRJ2_ROUTES`/`BRJ2_VIEWS` 등록 · 구역 표지 `# ==== BRJ2:X BEGIN/END ====` · 시험은 그 구역만 잘라 exec). 새 함수 이름은 bot.py 전체에서 유일해야 한다.
- 최근 구조: 인게임 HUD(하단 스킬 바·우측 메뉴 아이콘 · 메뉴는 `TABS`/`tabXxx()`/`DO={…}` 핸들러), 스킬 8칸(각성 단계마다 1칸·`BRK_*`), 엘리트 소환→장비 드랍(`BRJ2:LOOT`), 꾸미기 스킨 상점(`BRJ2:COS`, 맛동산), 동료 소환(`BRJ2:SUMMON`).
- 시험: 웹 `python3.13 tests/brjhunt_*_test.py`(playwright · 가짜 서버 `tests/fixtures/brj_view.json`) · 봇 `python3 tests/brj_*_test.py`. 새 기능마다 시험을 같이 만든다.
- **그림은 OpenAI 이미지 API 크레딧이 소진돼(2026-11-13) 못 뽑는다** → 코드로 그린 SVG/캔버스 도형·이모지로 만든다. 나중에 그림으로 교체하기 쉽게 한 곳(표)에 모아라.
- 다른 갈래 두 개가 같은 파일(brjhunt.html·bot.py)을 동시에 고친다. **새 코드는 새 구역/새 함수/새 탭으로 격리**하고 기존 줄은 꼭 필요한 만큼만 건드려라(병합 충돌 최소화).

## 진행 규칙
- `main` 에 push 금지. 이 브랜치(`rs-infinite`, 두 저장소 같은 이름)에만 push. 직접 적대적으로 검수(경계값·깨진 기록·중복 요청·저장 실패 되돌림). 끝나면 저장소 루트에 `RESULT.md`(한 일·시험 결과·남은 위험·패치노트 문안) 쓰고 push. 패치노트는 RESULT.md 에 문안만 적고 `data/patch_notes.json` 은 병합하는 쪽이 넣는다.
- 사장님은 비개발자·쉬운 한국어. 확정 못 한 설계는 RESULT.md 에 「결정 필요」로 적어라.

## 이 갈래의 일
### 환생 시스템 삭제 + 무한 성장 (사장님: 「환생시스템 삭제하고 무한히 성장하게끔 게임볼륨 확장」)
1. 환생(prestige) 탭·라우트(`/brj/prestige`·`/prestige_buy`·상자 등)·UI·환생 포인트를 없앤다. 이미 환생한 사람의 영구 보너스·보유 포인트·상자는 **손해 없이** 새 방식(영구 보너스로 환산 등)으로 이전하는 1회 마이그레이션을 만든다(깨진 기록 방어 · 되돌릴 수 있게 원본 보존).
2. 스테이지 상한(현재 30)을 없애 **무한히** 올라가게 한다: 필드 몬스터·권장 전투력·보스(10·20·30 …)·도전 던전·골드/드랍 곡선을 무한 확장 공식으로(구간마다 지역·몬스터 테마 반복/변주 · 숫자 폭주 방지 · `BRG_NUM_MAX` 등 상한 점검). 각성(`BRK_AWAKEN`) 요구 스테이지도 정리.
3. 환생이 하던 「장기 목표」를 대신할 무한 성장 목표(구간 보스·업적·누적 보상 등)를 설계해 구현. 시험(진행 속도 `tests/brj_pacing_test.py` 포함) 갱신.
