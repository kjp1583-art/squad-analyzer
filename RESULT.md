# RESULT — 동료 개편 (브랜치 rs-crew · 웹 squad-analyzer + 봇 squad-naejeon-bot)

## 한 일
**서버 (bot.py `BRJ2:SUMMON` 구역 · 새 표/함수만 추가)**
- `BRS_FAMS` — 동료 계열 6종(검객·궁수·마법사·방패병·치유사·행운아). 계열은 카드 id 로 정해져 사람마다 늘 같다.
- 동료마다 **고유 액티브 1 + 고유 패시브 1** (`_bs_skills`): 이름 앞에 등급 말머리(견습·숙련·정예·명장·전설), 위력은 등급 × 동료 레벨로 커진다. 숫자는 전부 `BRS_FAM_*` 한 곳.
  - 액티브: 연속 베기 / 화살 비 / 마력 폭발 / 방패 벽(받는 피해 −%) / 응급 처치(체력 회복) / 황금 동전
  - 패시브: 파티에 있으면 병아리 공격력·크리·방어력·체력이 조금 오름 → `_bs_passive_bonus` → `_bt_parts`(전투력)에 반영. 합계 상한 `BRS_PAS_CAP`.
- `_bs_view` 카드마다 `sk`(계열·액티브·패시브 설명), 뷰에 `pas`(파티 패시브 합계). 소환 결과에 `fam`.
- 기존 균형: 장착효과(`BRS_GRADE_BONUS`)는 그대로, 패시브는 그 약 1/4~1/3 크기의 덤. 전설 3명 기준 장착 +45% 위에 전투력 약 +5%.

**웹**
- `brjhunt_sd.js`(신규) — **SD 캐릭터 그림 표 한 곳**. 계열별 몸·모자·소품 + 등급 색 바닥 테두리(SVG, 코드로 그림). 카드·파티 칸·필드가 같은 그림을 쓴다. 나중에 그림 파일로 바꾸려면 `BrjSD.FILES = {blade:'img/..webp', …}` 만 채우면 된다.
- `brjhunt_arena.js` — 파티 동료가 **실제로 같이 싸운다**: 병아리 곁을 따라다니며(근접 계열은 앞, 원거리는 뒤) 자동 기본 공격 · 고유 액티브 시전(충전 막대·이름 콜아웃·공격 선) · 패시브 색 고리/아이콘. 동료가 몬스터를 처치하면 일반 처치로 세어진다. 동료 타격은 화면 흔들림·콤보·타격 소리를 만들지 않는다. 보스 도전 중에는 보스를 때리지 않는다(승패는 서버).
  - **kpm 보정**: 동료가 보태는 피해만큼 몬스터 체력을 키워(`allyDpsNom`, `ALLY_UPTIME`) 분당 처치가 서버 모델과 같게 유지.
- `brjhunt.html` — 동료 창: 카드에 SD 그림·계열·⚡액티브·🔰패시브 설명, 파티 칸에 그림, 「파티 고유 스킬」 목록 + 패시브 합계, 소환 결과에도 그림.

## 시험
- 봇: `python3 tests/brj_crew_skill_test.py` ALL PASS(신규: 6계열×5등급·결정성·상한·옵트아웃·깨진 기록·장비 낀 캐릭터 스테이지 1/10/40/120). 기존 `brj_pacing/summon/summon_points/own_bonus/stats/power/skill/growth` ALL PASS (`brj_stats_test` 동료 파티 줄은 패시브를 포함하도록 고침).
- 웹 `tests/brjhunt_crew_test.py`(신규) 전부 통과: 30종 동료가 60초 안에 실제 타격 · 액티브 시전 · 방패 피해 −40%대 · 치유 · **파티 유무에 따른 분당 처치 ±20% 안(실측 0.93~1.07배)** · 깨진 데이터 · 보스 중 동료 비공격 · SD 그림 30종 구분 · 콘솔 오류 0.
- `tests/brjhunt_crew_ui_test.py`(신규) PC·폰: 카드 SD/설명/파티 칸/필드 동료 3명.
- `tests/brjhunt_arena_test.py` 전체(3시드·4구성·6맵) 실패 0 — 하네스 기본 파티에 동료 2명이 들어 있어 보정이 실제로 검증된다(0.5/1/2배 → 50/104/137).
- `brjhunt_skillfx/field/art/lowmode/ingame_ui` 통과. `brjhunt_test`·`brjhunt_battle_test`·`brjhunt_instance_test` 는 **기존부터** 이 환경에서 실패(클릭 타임아웃 등) — 이 변경 전/후 결과 동일(비교 확인).
- 환경: python3.13 에 playwright 패키지만 pip 로 설치하고 `CHROME=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` 로 돌렸다.

## 남은 위험 / 결정 필요
- **결정 필요**: 패시브 크기(`BRS_FAM_PAS_UNIT/GR`)와 액티브 위력은 가정값. 지금은 전설 3명 패시브 합이 공격력 +3%·체력 +5% 안팎(상한 15%/크리 3%p). 더 체감되게 하려면 `BRS_FAM_PAS_UNIT` 만 올리면 되나 `brj_pacing_test` 를 다시 돌려라.
- **결정 필요**: 이름 앞 말머리·계열 이름(검객/궁수…)은 임시 작명. 계열이 카드 id 해시라 「이 사람은 궁수」처럼 사람 성격과는 무관하다(원하면 포지션 기반으로 바꿀 수 있음).
- 처치 속도는 파티가 있어도 서버 모델에 맞게 보정되므로 **동료가 골드를 더 벌게 해 주진 않는다**(체감은 전투 연출·처치 분담).
- 그림은 코드 SVG(이미지 API 크레딧 소진). 진짜 그림 파일은 `BrjSD.FILES` 로 교체.
- 병합: 웹은 `brjhunt.html`(fieldState·tabCrew·cardHtml·sdPic·script 태그 2줄)·`brjhunt_arena.js`(상수 블록·hitMob·hurtPlayer·derive·syncParty/drawAllies 교체·step 한 줄)·`tests/fixtures/brj_view.json`(카드 sk). 봇은 SUMMON 구역 + `_bt_parts` 3줄. 서로 다른 갈래와 같은 줄을 건드렸으면 이 줄들만 보라.

## 패치노트 문안 (병합하는 쪽이 `data/patch_notes.json` 에 — area: brj)
```json
{ "id": "2026-11-13-crew-skills", "date": "2026-11-13", "tag": "개편", "area": "brj",
  "title": "🐥 동료 개편 — 이제 필드에서 같이 싸워요!",
  "how": "브장신 키우기 → 동료 창에서 파티에 넣기",
  "lines": ["동료마다 **고유 액티브**와 **고유 패시브**가 생겼어요. (검객·궁수·마법사·방패병·치유사·행운아)",
            "파티에 넣은 동료가 필드에서 병아리 곁을 따라다니며 **직접 몬스터를 때리고**, 방패를 씌워 주고, 체력을 채워 줘요.",
            "동료마다 귀여운 **SD 캐릭터 그림**이 생겼어요 (카드·파티·필드 모두).",
            "패시브는 파티에 있을 때 공격력·방어력·체력·크리티컬 확률을 조금씩 올려 줘요. 동료 창에서 설명을 확인하세요."] }
```
