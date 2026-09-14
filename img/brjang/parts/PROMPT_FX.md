# ✨ 날개 · 오라 · 장신구 생성 프롬프트 (뒤 장식/소품 전용)

> 대상: `c_wing`(날개) · `c_aura`(오라) 같은 **뒤 장식**과 목·가슴·손에 붙는 **장신구(a 슬롯)**.
> 의상·헤어·얼굴이 바뀌는 것은 여기가 아니라 **전신 스킨**(`PARTS_PROMPT.md` 참고).
> 이 문서는 `tooling/brj_part.py extract_layer` 가 **실패 없이 잘라낼 수 있는 그림**을 받기 위한 규격이다.

## 왜 규격이 빡센가 — 파이프라인이 하는 일
받은 그림에서 **기본 몸(`parts/body/front.png`)과 달라진 부분만** 잘라 투명 레이어로 만든다. 그래서:

| 파이프라인 동작 | 그림이 지켜야 할 것 |
|---|---|
| 테두리 픽셀 색을 배경으로 보고 키잉 | 아이템이 **캔버스 가장자리에서 40px 이상** 떨어질 것 |
| 실루엣 IoU 로 크기·위치 정합 | 몸(머리·팔·발) 실루엣이 참조와 **동일**할 것 (덮임 0.90 미만이면 반려) |
| 몸 **바깥** 새 픽셀은 색과 무관하게 채택 | 몸 밖 장식은 자유 |
| 몸 **안쪽**은 색 차이 72 이상만 채택 | 몸 위에 겹치는 부분은 **크림색(#FDEAA8)과 확연히 다른 색** |
| 몸 외곽선 ±4px 띠는 무시 | 외곽선에 딱 붙여 그리지 말 것(5px 이상 안/밖으로) |
| 5px 미만 조각 제거(열림 필터) | 가장 얇은 획도 **8px 이상**, 흩뿌린 점·반짝이 금지 |
| 차분 면적 35% 초과면 반려 | 화면을 가득 채우는 연출 금지 |
| **레이어는 몸 위에 합성된다** | 날개·오라는 **몸 실루엣을 침범하면 안 된다**(아래 규칙) |

### ⚠ 뒤 장식(날개·오라)의 핵심 규칙
봇은 PNG 파츠를 **몸 위에** 그린다. 날개가 몸통을 덮으면 그대로 얼굴·몸을 가린다.
→ **날개·오라는 몸 실루엣 바깥에서만 보이게** 그린다. 몸과 겹치는 안쪽 부분은 *몸에 가려진 것처럼* 아예 그리지 않는다.
→ 반투명 글로우를 몸 위에 깔지 않는다. 불투명한 형태(깃털·불꽃 혀·링·리본)로 만든다.

## 캔버스 앵커 (1024×1024 기준)
| 항목 | 좌표 |
|---|---|
| 캐릭터 전체 | x 230–794, y 109–909 |
| 머리 | 중심 (512, 390) · 반지름 282 · 꼭대기 y109 |
| 눈 | (384, 397) / (640, 397) |
| 목선 | y 586 |
| 몸통 | x 358–666 · y 586–845 |
| 날개 끝(손) | 왼 (269, 707) · 오른 (755, 710) |
| 발바닥 | y 909 |

---

## 1) 공통 헤더 — 모든 요청 맨 앞에 그대로 붙인다
> ChatGPT 는 반드시 **편집(인페인팅) 모드**. 참조로 `parts/body/front.png` 를 올리고, 바꿀 영역만 브러시로 칠한 뒤 아래를 붙인다.

```
Reference image attached: "Brjangsin", a chubby pastel-yellow chick mascot on a 1024x1024 canvas — big round head,
tiny navy eyes with straight brows, small orange beak, pink cheek blush, stubby wings as arms, orange feet.
Flat cel-shaded sticker style, uniform dark-navy outline, two-tone shading, no texture, no gradient mesh, no text,
no watermark, no background props.

This is an EDIT of the attached image, not a new drawing. Keep the character 100% identical and byte-for-byte
unchanged: same pose, same camera, same size and position, same flat light-cream background, same line weight,
same palette. Do not redraw or shift the face, eyes, brows, beak, blush, arms or feet by even one pixel.
Add ONLY the single item described below.

HARD CONSTRAINTS (the asset is auto-cut by a diff script, so these are not stylistic suggestions):
- Keep the item at least 40px away from every canvas edge. Nothing may touch or bleed off the border.
- The thinnest stroke or shape of the item must be at least 8px wide. No sparkle dust, no thin rays,
  no scattered specks, no particles smaller than 8px — they get erased by the cutter.
- Do not draw the item exactly along the body's outline; stay at least 5px inside or outside it.
- The item must cover less than a third of the canvas.
- Anything drawn on top of the body must be a colour clearly different from the cream body (#FDEAA8).
```

## 2) 뒤 장식(날개 · 오라) — 공통 헤더 뒤에 붙인다
```
LAYER TYPE: BACK DECORATION. The item sits BEHIND the character, but it must be drawn so that it is only ever
visible OUTSIDE the character's silhouette. Where the item would pass behind the head, body, arms or feet,
simply do not draw it — treat the character as fully opaque and occluding. The result must read correctly if the
item were pasted on top of the character: no part of the face or body may be covered or tinted.
Use solid opaque shapes with the same navy outline as the character. No transparent glow over the body,
no soft blur, no screen/overlay haze.
ITEM: <여기에 아래 표의 문장>
```

| 키 | 이름 | ITEM 문장 |
|---|---|---|
| `c_wing` | 황금 날개 | `a pair of large golden feathered angel wings spreading up and outward from behind the shoulders, five long primary feathers per side plus three shorter covert feathers, each feather a solid shape with a navy outline and a lighter gold inner highlight.` |
| `c_wing_bat` | 어둠의 박쥐 날개 | `a pair of dark-purple bat wings spreading outward from behind the shoulders, three pointed membrane lobes per side with thick bone struts, solid fill with a navy outline.` |
| `c_wing_mech` | 기계 날개 | `a pair of angular steel-blue mechanical wings behind the shoulders, three flat metal blades per side fanning upward, each blade a solid plate with a navy outline and one cyan stripe.` |
| `c_aura` | 논란 오라 | `a ring of solid red-orange flame tongues rising around the outside of the body, eight to ten chunky teardrop-shaped flames of alternating red and orange, each with a navy outline, forming a halo that hugs the silhouette without covering it.` |
| `c_aura_ice` | 서리 오라 | `a ring of solid pale-blue ice shards standing around the outside of the body, eight chunky angular crystals of alternating light blue and white, each with a navy outline.` |
| `c_aura_holy` | 신성 오라 | `a thick solid gold ring halo standing vertically behind the character like a disc rim, only the rim visible around the outside of the silhouette, with a navy outline.` |

## 3) 장신구(a 슬롯 · 손·목·가슴) — 공통 헤더 뒤에 붙인다
```
LAYER TYPE: ACCESSORY. The item sits ON TOP of the character and may overlap the body, but it must never cover
the eyes, brows, beak or cheek blush — the face stays fully readable. Draw it as a solid shape with the same
navy outline as the character, resting on the body so it follows the body's curves and never floats.
ITEM: <여기에 아래 표의 문장>
```

| 붙는 곳 | 문장에 넣을 위치 표현 |
|---|---|
| 목 | `wrapped around the neck at the neckline` |
| 가슴 | `resting flat on the chest just below the neckline` |
| 오른손 | `held in the right stubby wing at the right side of the body` |
| 왼손 | `held in the left stubby wing at the left side of the body` |
| 등 뒤 소품 | 2번(뒤 장식) 규칙을 쓴다 |

| 키 | 이름 | ITEM 문장 |
|---|---|---|
| `c_cape` | 망토 | `a crimson cape fastened at the neck with a round gold clasp, the cloth falling behind the body and flaring out on both sides past the silhouette.` |
| `c_tail` | 여우 꼬리 | `a big fluffy orange fox tail with a white tip curling out from the lower right of the body.` |
| `c_lantern` | 청사초롱 | `a blue-and-red Korean paper lantern held in the right stubby wing at the right side of the body, hanging from a short wooden handle.` |
| `c_ribbon` | 리본 | `a big pink satin ribbon bow tied around the neck at the neckline, two loops and two short tails.` |
| `c_medal` | 금메달 | `a round gold medal on a thick navy-striped ribbon resting flat on the chest just below the neckline.` |
| `c_book` | 마법서 | `a thick purple spellbook with gold corner fittings held in the left stubby wing at the left side of the body.` |

## 4) 옆모습(quarter)이 필요하면
같은 요청을 `parts/body/quarter.png`(오른쪽을 보는 옆모습)로 한 번 더 한다. 헤더의 `front` 관련 문구는 그대로 두고 아래를 덧붙인다.
```
This reference is the SIDE view (character facing right). Place the item consistently with that angle: the far-side
half is partly hidden behind the body, the near-side half is fully visible.
```

## 5) 받은 뒤 — 등록 전 검사
```
python3 tooling/brj_part.py check --front <받은.png> --slot a
```
- `cover` ≥ 0.90 (몸 실루엣이 참조와 같은가) · `iou` ≥ 0.93 · `warn` 없음 → 통과
- `area` 0.002~0.35 사이 · 미리보기에서 얼굴이 안 가려지는지 눈으로 확인
- 통과하면 `brj_part.py add --key c_x --slot a ...` 로 등록 → main 푸시 → 봇 10분 내 반영(`/파츠새로고침` 즉시)

## 6) 자주 나는 실패와 원인
| 증상 | 원인 | 고치는 말 |
|---|---|---|
| 레이어가 텅 빔 | 아이템이 몸 안쪽인데 크림색과 비슷 | `use a colour clearly different from the cream body` |
| 반짝이·불티가 사라짐 | 5px 미만 조각 제거 | `no particles smaller than 8px` |
| 목걸이 줄이 끊김 | 몸 외곽선 ±4px 띠에 걸림 | `keep the chain at least 5px inside the body outline` |
| 배경 키잉 실패 | 아이템이 캔버스 가장자리에 닿음 | `at least 40px away from every canvas edge` |
| `cover` 낮음 / 크기 어긋남 | 캐릭터를 다시 그림 | 편집 모드로 다시, `do not redraw the character` 강조 |
| 얼굴이 가려짐 | 날개·오라가 몸을 덮음 | 2번 `LAYER TYPE: BACK DECORATION` 블록을 반드시 포함 |
