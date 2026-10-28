---
name: brjang-part
description: 브장신 키우기 꾸미기 파츠(옷·모자·장신구) 추가 — ChatGPT 등으로 뽑은 "착용 전신 PNG"를 레이어로 잘라 manifest 에 등록하고 main 에 푸시. "파츠 추가", "의상 추가", "꾸미기 등록", "브장신 옷" 요청에 사용.
---
# 브장신 파츠 추가

## 입력
- 착용 전신 PNG 1~2장(정면 필수 `front`, 옆모습 `quarter` 선택). 생성 프롬프트는 `img/brjang/parts/PARTS_PROMPT.md`.
- 메타: 키(영문, `c_` 접두), 이름, 슬롯(모자 h / 의상 o / 장신구 a), 등급(일반/레어/에픽/전설), 이모지, 한 줄 설명, 맛동산 가격(0이면 상점 안 팜 → 뽑기 풀), 한정 여부.

## 절차
1. `python3 tooling/brj_part.py check --front <png> --slot <h|o|a>` 로 리포트 확인. `iou < 0.93` 이나 `warn` 이 있으면 사용자에게 재생성을 권하고 멈춘다.
2. `python3 tooling/brj_part.py add --key c_x --name "이름" --slot o --rarity 에픽 --emoji 🧥 --desc "한 줄" --front f.png [--quarter q.png] [--price 10] [--limited]`
   → `img/brjang/parts/<slot>/<key>/<view>.png` + `img/brjang/parts/manifest.json` 갱신.
3. 미리보기: `python3 tooling/brj_part.py preview --key c_x` 가 있으면 쓰고, 없으면 레이어 PNG 를 `parts/body/front.png` 위에 합성해 사용자에게 보여 준다.
4. 커밋·푸시(main). 봇은 10분 안에 manifest 를 다시 읽어 자동 반영(`/파츠새로고침` 으로 즉시), 웹은 페이지 새로고침이면 된다.

## 의상은 스킨으로 (2026-09-10)
- 의상·헤어·얼굴이 바뀌는 그림은 파츠가 아니라 **전신 스킨**: `python3 tooling/brj_part.py skin --key c_suit --name "검은 정장" --front f.png [--oblique o.png] [--quarter q.png] [--egg e.png] [--price N]`
  → `img/brjang/skins/<key>/<view>.png` + `manifest.json` 의 `skins`. 기존 의상 아이템 키(c_suit…)면 착용 시 자동으로 그 스킨이 되고, 새 키면 맛동산 상점 스킨 아이템이 된다.
- 파츠(차분 레이어)는 모자(h)·장신구/소품/효과(a)만.

## 규칙
- 레이어는 반드시 `extract_layer` 로 만든다(직접 그린 파츠 금지 — 위치가 어긋난다).
- 기존 키를 덮어쓰면 그 키를 착용 중인 사람 전원의 모습이 바뀐다. 이름을 바꿀 때만 덮어쓰고, 다른 아이템이면 새 키.
- `state` 슬롯(work/staff/stun)은 봇 상태 표식이라 상점·뽑기에 안 나온다.
