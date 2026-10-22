# TASK (rs-wp-b) — 흐접새우 신규 무기/패시브 구현
공통 맥락: 웹 저장소 squad-analyzer 의 survivors.html(흐접새우 서바이벌). 기획안은 tooling/improve/ideas/SV-weapons-passives-2026-10-22.md (사장님이 무기 6종 전부 + 패시브 P-2 동전 지갑·P-4 부적·P-5 연쇄 를 승인). CLAUDE.md 의 🎯(한 줄 컨셉·가만히 서 있는 보상 금지) 를 지킬 것.
너의 갈래: 무기 W-1 롤러 자국, W-4 택배 상자(처치 연동)
방법: 기존 무기 하나(예: wifi, can, ping, gacha)가 어디에 어떻게 들어가 있는지 grep 으로 전부 따라가 같은 자리(WEAP·궁합표·PFXSN·계보 LINEAGE·튜닝 카드·그리기·시험)에 똑같이 넣는다. 패시브는 PASS + 배율 훅(svB 등).
규칙: resume SIG 해시 표(CHARS/WEAP/TIERS/SYN/REL…)는 건드리면 resume 시험이 갈리니 기존 신규 무기 추가 때의 방식(SIG 갱신 관례)을 git log 로 찾아 따른다 · 새 S 키/최상위 let 금지(모듈 const 객체는 판마다 리셋) · 새 난수는 RN('key') · 일일 도전 시드 결정성 유지 · 폰 360px 가로 넘침 없음 · 콘솔 오류 0.
강도: tests/survivors_weapon_arena.py --seeds 4 --boss --field --only <무기> 로 중앙값(L8 1998 · 보스 872 · 필드 505) 근처에 맞춘다(너무 세도 약해도 안 됨). 새 무기마다 tests/survivors_<이름>_test.py 추가. python3.13 으로 실행. 관련 기존 시험(codex·lineage·startpick·ach·map·crisis) 돌려 새 빨강 없게(원래 빨강 목록: codex #resGo, resume, bal1, coin, hpnum, cstat, finduel/fx/info, snack_early, pairslot, speed2).
패치노트: data/patch_notes.json 맨 앞에 항목 1개(area squad · game sv · 클랜원 말투). BUILD_ID 는 survivors.html 에는 없음(index.html 만).
진행 규칙: main 에 push 금지 · 이 브랜치(rs-wp-b)에만 커밋/push · 직접 적대적 검수(장비/조건부 경로) · 끝나면 RESULT.md(무엇을 넣었나·측정값·남은 빨강) 작성 후 push. 커밋 메시지에 모델 이름 금지.
