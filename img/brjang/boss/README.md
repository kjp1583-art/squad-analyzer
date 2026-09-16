# 🐲 월드보스 원화

`img/brjang/boss/<보스>/<뷰>.png` — 봇이 GitHub raw 로 직접 받아 씁니다(`SKIN_URL`).
보스별로 어떤 뷰가 있는지는 `bot.py` 의 `BOSS_IMG` 에 적습니다.

| 보스 | 폴더 | 필요한 파일 |
|---|---|---|
| 신림 | `shinlim/` | front · roar · tongue · growl · bite · idle · back (7종 · 이미 있음) |
| 또뀨 | `ddokkyu/` | **front.png** |
| 용조련사 | `yongjo/` | **front.png** |

- **front.png 하나만 있으면 됩니다.** 나머지 뷰(포효·물기·으르렁 등)는 자동으로 front 로 떨어집니다.
- 뷰를 더 그리면 `BOSS_IMG` 의 튜플에 그 이름을 추가하세요.
  예: `"또뀨": ("boss/ddokkyu", ("front", "roar"))`
  (거기 적힌 뷰만 부팅 때 미리 받습니다 — 없는 파일을 매번 받으러 가지 않게.)
- 정사각 PNG 를 권장합니다. 512px 로 줄여서 캐시하므로 1024² 이상은 불필요합니다.
- 원화가 있으면 **출현 공지에 큰 이미지**로, 없으면 벡터 그림으로 자동 대체됩니다.
