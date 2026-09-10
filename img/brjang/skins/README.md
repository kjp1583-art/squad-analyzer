# 🌟 브장신 스킨 — 「별수호자 브장신」 제작 프롬프트 · 적용 규격

> 롤 스킨처럼 **캐릭터의 겉모습만** 바꾼다. 능력치·전투력 변화 없음. 맛동산 상점 판매(🍘 10개 = 1만원).
> 이 폴더(`img/brjang/skins/<skin>/`)에 PNG 를 넣으면 봇이 GitHub raw 에서 내려받아 벡터 브장신 대신 그린다.

## 1. 이미지 생성 모델에 줄 프롬프트 (그대로 복사)

### 공통 — 캐릭터 정의 (매 장 앞에 붙인다)

```
Character sheet asset for a Discord pet-raising game. Subject: "Brjangsin", a round chicken mascot.
Base anatomy (must be kept EXACTLY so game overlays line up): a wide egg-shaped body with a domed head
that is one single blob (no neck), body fills about 60% of the canvas width and sits slightly below center;
two tiny round black eyes with a single white highlight, set wide apart on the upper third of the blob;
short thick eyebrow strokes above the eyes; a small trapezoid yellow beak centered just below the eyes;
two small serrated (zig-zag) wings sticking out at mid-height on both sides; no visible legs or feet;
no comb on the head (hats go there).
Rendering style: flat cel-shaded sticker art, very thick uniform dark-navy ink outline (like a marker),
two-tone shading only (base color + one shadow tone), no gradients on the outline, no texture, no text,
no background. Cute, deadpan face, slightly unimpressed expression.
Output: a single character, centered, on a fully TRANSPARENT background, 1024x1024 PNG, generous
margin (character bounding box roughly x 190-830, y 20-860 so hats and wings fit), no drop shadow.
```

### 스킨 — 「별수호자」 콘셉트

```
Skin theme: "Star Guardian" magical-girl style. Palette: pastel pink (#F7A8C9), lavender (#C9B6F2),
mint (#A8E6D9), cream white body (#FFF6EC), star-gold accents (#FFD65A), dark-navy outline (#12121A).
Costume (painted ON the blob body, following its curve): a sailor-style collar with a big pink ribbon bow
at the chest, a short pleated skirt line around the lower third of the body (the body's lower part
is treated as the skirt — pink with a lavender hem band), a tiny star brooch in the middle of the bow.
Head: a small gold tiara with one glowing five-point star, sitting ON TOP of the dome (thin, low profile,
nothing taller than 12% of the canvas so game hats can still cover it); two long flowing pastel-pink
ribbon streamers from the tiara trailing down the sides of the body.
Wings: replace the plain serrated wings with small translucent pastel wings (pink→lavender→mint),
same position and size as the base wings (they must stay within x 20-300 of a 320 grid, i.e. not wider
than the body's sides by more than 15%).
Effects: a few small four-point sparkle stars floating around the character (max 6, small), soft mint
glow rim on the wings only. No aura behind the body, no large magic circle.
Keep the eyes tiny and black with one highlight, beak yellow. It must still read as the same chicken.
```

### 시점 — 각각 따로 생성 (3장 필수 + 1장 선택)

| 파일 | 프롬프트 뒤에 덧붙일 문장 | 봇에서 쓰는 곳 |
|---|---|---|
| `front.png` | `View: straight front view, face centered, both eyes symmetric, looking at the viewer.` | 현황 카드·가방·의상함(정면) |
| `oblique.png` | `View: front view but the face is shifted about 10% to the LEFT of the body center (character glances to its right / viewer's left); the far (right) eye is slightly narrower; body silhouette unchanged.` | 합정점 매장 화면(fx=−30) |
| `quarter.png` | `View: three-quarter BACK-side view — we see the character from behind and slightly to the right; only the RIGHT eye and the tip of the beak peek out on the right edge of the head; the bow is hidden, the skirt hem and ribbon streamers show from behind; body silhouette unchanged.` | 전투 화면 내 브장신(quarter, fx=+58) |
| `egg.png` (선택) | `Egg form: a plain smooth egg (same outline style) with pastel pink/lavender star-shaped speckles and a tiny tiara resting on top.` | Lv.0 알 |

> 모델이 시점을 못 맞추면 `front.png` 하나만 있어도 된다 — 봇이 나머지 두 시점을 정면 이미지를 옆으로 밀고 좌우반전해서 대체한다(품질은 떨어짐).

### 검수 체크리스트(이미지 받은 뒤)

- [ ] 배경 완전 투명(체커보드 없음), 1024×1024, 캐릭터가 중앙·바운딩 박스 x 190–830 / y 20–860 안
- [ ] 눈 2개(quarter 는 1개)·부리 노랑·외곽선 진남색 — "같은 브장신"으로 읽히는가
- [ ] 머리 꼭대기 위로 티아라·리본 외에 아무것도 튀어나오지 않음(모자 슬롯이 덮어야 함)
- [ ] 글자·워터마크·서명 없음

## 2. 봇 적용 규격(개발용)

- **좌표계**: 벡터 브장신 320×320 기준. 1024 PNG 는 `k = 1024/320 = 3.2` 배. 봇은 `size` 에 맞춰 LANCZOS 축소.
- **몸통 기준 박스(320)**: x 64–256, y 78–262 (머리 돔 상단 y 78, 눈높이 y 142, 부리 중심 (160,164), 하반신 절개선 y≈168–180).
  1024 로는 x 205–819, y 250–838, 눈높이 y 454.
- **스킨이 대체하는 것**: 몸통·얼굴·날개·단계 의상(앞치마/빨간 조끼/선글라스/왕관)·몸 색. → 스킨 장착 시 `VEC_STAGE` 의 특징 집합을 **무시**하고 스킨 PNG 만 그린다(왕관은 티아라가 대신).
- **스킨 위에 그대로 얹는 것**(기존 벡터 함수 재사용, 같은 좌표):
  - 모자(h) 6종 — 머리 앵커 (86–216, 4–100) · 삿갓은 (30–290)
  - 장신구(a) 7종 — 목도리 (92,170)-(228,190) · 코인 목걸이 호 (110,150)-(210,210) · 트로피 (228–270, 200–240) · 응원봉 (256–276, 150–250) · 풍선 (22,10)-(72,70)+줄 (58,150) · 황금 날개 (−4..30 / 290..324, 110–182) · 논란 오라 뒤 타원 (34,48)-(286,282)
  - 상태 3종 — 근무 상자 (236,206)-(296,258) · 스탭 명찰 (186,196)-(214,216) · 행동불능 별 (100,40)(160,24)(220,40) + 눈 X 는 스킨에서 생략(별만)
  - 의상(o) 6종은 **숨김**(스킨 의상이 우선) — 가방엔 그대로 남고 스킨 해제 시 다시 보임
- **시점 매핑**: `fx=0` → `front.png`, `fx<0` → `oblique.png`(fx>0 이면 좌우반전), `quarter=True` → `quarter.png`(fx<0 이면 좌우반전). 파일이 없으면 `front.png` 를 fx 만큼 평행이동으로 대체.
- **배포 경로**: `https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/main/img/brjang/skins/<skin>/<view>.png`
  봇은 첫 사용 때 `BASE/skins/<skin>/` 에 내려받아 캐시(실패 시 벡터로 폴백, 로그 `[skin]`). `self_update` 는 bot.py 만 갈아끼우므로 에셋은 이 경로에서만 온다.
- **상점**: `MD_SHOP` 에 `("skin_sg", 10, "skin_sg", 1, "🌟 별수호자 브장신 — 겉모습만 바뀐다(회차 리셋에도 유지)")`, 아이템 `BRJ_ITEMS["skin_sg"]` 슬롯 `s`(스킨). 기록 `r["skin"]` 에 키 저장, `"스킨 별수호자"` / `"스킨 해제"` 채팅으로 전환. 부화(리셋) 때 `skin`·가방의 스킨 아이템은 유지.
