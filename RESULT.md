# RESULT (rs-wp-b) — 롤러 자국 · 택배 상자

## 넣은 것
- 🛼 롤러 자국(`roll`, 각성 짝 이동속도 `spd`) — 달린 거리마다 푸른 불꽃 자국(풀 `trls` 110칸), 밟으면 지속 피해, 서 있으면 안 늘어남. 각성: 굵고 오래, 감속.
- 📦 택배 상자(`box`, 각성 짝 근성 `might`) — 처치 +1(스스로 이어지지 않게 box 처치는 제외) · 3초마다 +1 · 상한 30 · 10개(Lv3/5/8 -1, 각성 ×0.7)면 가장 몰린 곳에 던져 폭발(Lv1 1개 → Lv4 2 → Lv7 3 → 각성 +1).
- 자리: WEAP · PFX · PFXSN · LINEAGE · TIERS · W4 · 풀(newRun clear · RES POOL) · S.x2 필드(newX2) · 그리기(자국=바닥층, 상자=머리 위, 낙하=boom style 'box') · 처치 훅(`boxKill`).
- 새 S 키·최상위 let 없음. 새 난수 없음(기존 clusterSpot 만). SIG 는 자동 계산이라 옛 저장본은 버려진다(신규 무기 추가 때와 동일).
- 패치노트 `2026-10-22-sv-roll-box`.

## 측정 (weapon_arena --seeds 4)
- roll: L1 1082 · L5 1706 · L8 1882 · EV 2562 (중앙값 L8 1998 근처). 필드/보스 칸은 플레이어가 서 있어 0 — 의도.
- box(혼자는 처치가 없어 0): 사료 Lv4 동행 L8 1540 / EV 2879, 사료 Lv8 동행 L8 3121 / EV 4307.

## 시험
- 신규: `survivors_roll_test.py` 12/12 · `survivors_box_test.py` 17/17.
- 갱신: codex(칸 134→136, 무기 42→44, 공용 22→24 …) · resume/resume_world/fx 풀 목록에 `trls` · map 시험 A 는 BASE 이후 추가된 공용 무기를 A 용 사본에서만 뺌.
- 통과: crisis · ach · startpick · map · lineage(--only 가나다바사아자) · codex(기준 커밋/겹창 열 수 외).

## 남은 빨강 (이 환경 한정·내 변경과 무관)
- 얕은 클론이라 기준 커밋(`a112f9e`, `4ed2f37`, fx/pairslot OLDSRC)이 없어 fx · info · pairslot · lineage 라/마 · codex ⑦ 는 돌릴 수 없음(원래 빨강 목록).
- unique_weapons: fuse/cart/bash "Lv1 피해 0" 이 실행마다 바뀜(내 무기와 무관해 보이나 기준선 비교는 못 함).
- 못 돌린 것: resume · bal1 · coin · hpnum · cstat · finduel · snack_early · speed2 (원래 빨강).
