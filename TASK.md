# TASK — 곱빼기 패시브 제거, 곱빼기로 늘던 무기는 각자 레벨업으로 탄수 증가 (흐접새우 서바이벌 `survivors.html`)

사장님 지시(2026-10-18): 「곱빼기 패시브 제거하고 곱빼기로 늘어나는 스킬들 다 자체 스킬 레벨업으로 탄수 늘어나게 변경」

## 맥락
- 저장소 루트 CLAUDE.md 를 먼저 읽는다(패치노트·시험·SIG 규칙). main 에 push 하지 말고 이 브랜치(rs-amt)에만 push. 끝나면 RESULT.md 작성 후 push.
- 패시브 `PASS.amt`(🍱 곱빼기, max 3, 「날리거나 설치하는 개수 +1」)가 `pair:'amt'` 인 무기(feed, quill …)와 `pv('amt')`/`S.syn.amt`(계열 시너지 탄막 `LINT.bar` 의 amt)를 통해 개수를 늘린다. `grep -n "amt" survivors.html` 로 전부 찾는다(statsrow `{k:'amt'...}`, `shvAuraK`, 무기 발사부 `AM=pv('amt')+S.syn.amt` 등).
- 핵심: **곱빼기 패시브를 PASS 표에서 없앤다.** 그 패시브가 늘려 주던 개수(탄수·설치 수)는 **각 무기의 자체 레벨업 표(WEAP ds/ lvm 표 등)에 「Lv N: 개수 +1」로 녹인다**. 총 개수는 풀레벨 기준으로 옛 (무기 최대 + 곱빼기 3) 와 비슷하되 지나치지 않게(밸런스는 `tests/survivors_charbal_sim.py` 로 전/후 비교, 옛 곱빼기를 안 먹던 판과 먹던 판의 중간).
- `pair:'amt'` 였던 무기는 다른 패시브로 짝을 바꾼다(그 무기 성격에 맞게, 도감/카드 문구·`PAIR` 관련 시험 갱신).
- 계열 시너지(`LINT.bar` 의 `amt`)는 「개수 +1」 효과를 **무기 개수 증가로 계속** 쓸 수 있게 `S.syn.amt` 는 남긴다(패시브만 제거). 단 `pv('amt')` 읽던 곳은 정리.
- 이어하기 서명(SIG)은 표를 해시하므로 바뀐다 — 정상(진행 중 판 1회 초기화). 새 S 키·최상위 let 금지. 새 수치는 별도 const.
- 이어하기 저장/복구, 도감(`survivors_codex_test.py` 칸 수: PASS 하나 줄어 135→134, 패시브 17→16), cstat/cabil, unique_*, bbb 시험의 개수 기대를 갱신. 알려진 기준선 빨강(bal1, coin, hpnum, cstat/resume_world SIG, finduel/fx/info SIG, snack_early, pairslot, speed2)은 무시.
- 이미 곱빼기를 가진 옛 저장본/상점·해금과 무관(패시브는 판 안에서만 쓰임). 봇 쪽 변경 없음.
- 패치노트: `data/patch_notes.json` 맨 앞에 `"area":"squad","game":"sv"` 항목 1건(클랜원 말투: 곱빼기 패시브가 사라지고 무기 레벨업으로 개수가 늘어요 + 어떤 무기가 몇 레벨에 늘어나는지).
- 모델 이름을 커밋·주석에 쓰지 않는다. 커밋 꼬리말: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_018GzTivP446Z4KhefLmvcv5`

## 끝났을 때 RESULT.md 에
바뀐 무기 목록(무기 · 이전 개수 규칙 · 새 레벨별 개수 · 새 짝 패시브), 밸런스 전/후 수치, 시험 결과(새 빨강 vs 기준선), 남은 문제.
