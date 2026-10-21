# RESULT — 🎒 출발 보너스(시작 선택 · S-5)

## 만든 것
- 판이 시작되면(0초) 「🎒 출발 보너스 — 하나 고르세요」 오버레이에 서로 다른 3장. 고르기 전엔 게임 시간이 안 흐른다(상태 `stpick`). 키보드 1·2·3 지원.
- 후보 10종 `STARTV`: 시작 무기 Lv+1 · 패시브 하나(Lv1) · 유물 하나(Lv1, 시그니처 제외) · 이속 +10% · 최대 HP +20% · 처음 5분 경험치 ×1.3 · 첫 보스 상자 카드 +1장 · 다시 뽑기 +2/봉인 +1 · 획득 범위 +30% · 쿨 −8%.
- 캐릭터 성향 가중 `STARTW`(근접 HP·이속 / 원거리 쿨·범위). 일일 도전은 `RN('start')` 로 3장(무작위 패시브·유물 포함) 고정.
- 지속 효과는 `S.x3.sv`(숫자 몇 개)에 저장 — 새 S 키·최상위 let 없음, 이어하기가 그대로 복구. 최대 HP 는 `mhpAdd('st')`(출처표 `MHPN.st`).
- 새 코드는 `survivors.html` 의 `function start` 바로 위 한 구획(`[S-5]` 표시).
- 시험 `tests/survivors_startpick_test.py`(30항목), charbal `--startpick N` 옵션, `data/patch_notes.json` 항목(area squad · game sv).

## 기획과 다르게 한 것 (확인 부탁)
- 「치킨 1개 즉시」: 0초엔 HP가 가득이라 값이 없어 → 「다시 뽑기 +2 · 봉인 +1」.
- 「첫 보스 상자 확정」: 보스는 원래 늘 상자를 떨궈서 → 「첫 보스 상자에서 카드 +1장」.
- 자동 시험(`navigator.webdriver`)에서는 오버레이를 건너뛴다 — 기존 시험 69개가 `start()` 직후 `play` 를 믿는다. 켜려면 `STARTCFG.force=1`, 자동 선택은 `STARTCFG.auto=칸`.

## 건드린 기존 줄 (충돌 대비)
`ovs` 배열 · 키보드 1~3(`stpick`) · `start()` 끝의 `startPickOpen()` 한 줄 · `moveMul`/`magMul`/`xpMul`/`cdMul` 각 끝에 `svB(..)` 항 · `MHPN` 에 `st` · `openChest` 3줄(첫 상자 +1) · `#stpick` 오버레이 HTML. charbal: `survivors_charbal_sim.py`(`--startpick`, 훅) · `survivors_charbal_bot.js`(1줄).

## 시험 결과
- 새 시험 30/30 통과 (오버레이 시간 정지·폰 360 가로 넘침 0·중복 없음·가중·효과 10종·6캐릭터×10효과 진행·일일 도전·이어하기 복구·콘솔 오류 0).
- 기존 시험 64개: 빨강 18개 — 전부 변경 전 파일에서도 빨강(bal1·cstat·hpnum·finduel·fx·info·pairslot·snack_early·speed2 + barrage_up·bbb·bgb·codex·hall·pty·unique_weapons·lineage). 새로 생긴 빨강 없음. (`p6` 은 병렬 실행 중 1회 빨강, 단독 재실행 65/65 · 변경 전 65/65 → 불안정한 실패.)
- 이어하기 `resume_test`/`resume_world_test`: 변경 전과 동일(68/1 빨강, 실패 목록 동일).
- charbal 20캐릭터 × 시드 6, 보너스 없음 vs `--startpick 0`: 처치@10 평균 −0.8%(−4.1%~+0.7%), Lv@10 평균 −0.6%. **처치@10 이 ~5400 에서 포화(스폰 한도)라 이 봇으로는 보너스 효과가 안 보인다**(= +8% 안쪽은 충족하지만 증명력이 약하다). 자동 선택이 적용되는지는 별도로 확인함.

## 남은 문제
- 이어하기 중 오버레이 도중에 창을 닫으면 그 판은 저장 전이라 사라진다(RES.begin 이 옛 저장본을 비움). 3택 1 은 1~2초라 허용으로 봤다.
- 측정 한계: 선택지별 편차는 봇이 선택 id 를 기록하지 않아 못 쟀다.

## 사장님께 물을 것
1. 위 두 항목 교체(다시 뽑기·상자 +1장) 괜찮은지.
2. 선택지별 세기를 재려면 charbal 에 선택 id 기록을 넣고 `--startpick 0/1/2` 를 고정 id 로 바꿔야 한다 — 진행할까요?
