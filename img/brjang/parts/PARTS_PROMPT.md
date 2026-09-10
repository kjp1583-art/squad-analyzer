# 🧥 브장신 파츠(옷·모자·장신구·상태) 생성 프롬프트 — 새 원화 기준

## 원칙
- 파츠는 **"기본 브장신이 그 파츠 하나만 착용한 전신 그림"**으로 뽑는다. 파츠만 따로 그리게 하면 크기·위치가 매번 어긋난다.
  뽑은 그림을 `parts/body/front.png`(또는 quarter)와 픽셀 비교해 **달라진 부분만** 잘라 투명 레이어로 만든다(맞춤 스크립트가 함).
- 그래서 매 장마다 **기본 몸 이미지를 참조로 첨부**하고, "same character, same pose, same camera, same line weight, same palette" 를 반드시 넣는다.
- 시점: `front`(정면) 필수, `quarter`(오른쪽 보는 옆모습, 전투용) 필수, `oblique`(곁눈) 선택.
- 캔버스: 1024×1024, 캐릭터 위치·크기는 참조와 동일(머리 꼭대기 y≈110, 발바닥 y≈910). 배경은 참조와 같은 단색(키잉용).

## 공통 프롬프트 (모든 장 앞에 그대로)
```
Reference image attached: "Brjangsin", a chubby pastel-yellow chick mascot — big round head, tiny navy eyes with
straight brows, small orange beak, pink cheek blush, stubby wings as arms, orange feet. Flat cel-shaded sticker
style, uniform dark-navy outline, two-tone shading, no texture, no text, no background props.
Draw the SAME character in the SAME pose, SAME camera angle, SAME size and position on a 1024x1024 canvas with the
SAME flat light-cream background, identical line weight and palette. Change NOTHING except: the character is now
wearing / holding the single item described below. The item must follow the body's curves, never float, never
extend past what a real garment on this body would cover; keep the face fully visible unless stated.
```

## 파츠별 문장 (공통 프롬프트 뒤에 붙인다) — 봇 키 = 파일명

### 의상(o) — 몸통만 덮는다. 머리·팔·발은 원화 그대로
| 키 | 이름 | 문장 |
|---|---|---|
| `apron` (단계) | 앞치마 | `ITEM: a dark-green kitchen apron tied around the torso, bib covering the belly, thin neck strap, straps not covering the wings.` |
| `red` (단계) | 빨간 조끼 | `ITEM: a snug red sleeveless vest over the torso, small V opening at the chest, hem at the top of the feet.` |
| `c_suit` | 검은 정장 | `ITEM: a tiny black tuxedo jacket over the torso with a white shirt front and a thin red necktie; wings poke out of the sleeves.` |
| `c_hanbok` | 한복 | `ITEM: a Korean hanbok — light-blue short jeogori top with a pink ribbon (otgoreum), and a pink chima skirt from the belly down to the feet.` |
| `c_pajama` | 줄무늬 잠옷 | `ITEM: white pajamas with horizontal sky-blue stripes covering the torso, soft rounded collar.` |
| `c_jersey` | 스쿼드 유니폼 | `ITEM: a royal-blue esports team jersey with a white horizontal chest stripe and a small white "S" crest on the chest.` |
| `c_bhc` | bhc 유니폼 | `ITEM: a bright orange fast-food staff polo with a small white name tag on the chest.` |
| `c_jgpos` | 2티어하 코스프레 | `ITEM: a purple pull-over with a big white number "2" on the chest and a small red down-arrow badge on the right shoulder.` |

### 모자(h) — 머리 꼭대기 기준. 눈·눈썹은 가리지 말 것(선글라스 제외)
| 키 | 이름 | 문장 |
|---|---|---|
| `crown` (단계) | 왕관 | `ITEM: a small gold five-point crown sitting on top of the head, slightly tilted.` |
| `sungl` (단계) | 선글라스 | `ITEM: black rectangular sunglasses covering both eyes, thin bridge; brows still visible above.` |
| `c_santa` | 산타 모자 | `ITEM: a red Santa hat with white fur brim and a white pom-pom, flopping to the right.` |
| `c_head` | 게이밍 헤드셋 | `ITEM: a black over-ear gaming headset — headband over the top of the head, round ear cups on both sides, tiny mic boom on the left.` |
| `c_gat` | 삿갓 | `ITEM: a wide conical Korean straw hat (satgat), dark brown, brim wider than the head, chin string.` |
| `c_pin` | 병아리 머리핀 | `ITEM: a tiny yellow chick-shaped hair clip on the upper right of the head.` |
| `c_helm` | 예비군 철모 | `ITEM: an olive-green military helmet with a cloth cover, sitting low on the head, brows visible.` |
| `c_halo` | 천사 링 | `ITEM: a glowing gold angel halo floating just above the head.` |
| `c_yumi` | 머리 위의 유미 | `ITEM: a tiny lavender-purple cat (round body, pointy ears, small black eyes, curled tail) sitting on top of the head, looking down.` |

### 장신구(a)
| 키 | 이름 | 문장 |
|---|---|---|
| `c_scarf` | 목도리 | `ITEM: a red knitted scarf wrapped around the neck, one tail hanging down the right side of the chest.` |
| `c_coin` | 스쿼드코인 목걸이 | `ITEM: a thin gold chain necklace with a big round gold coin medallion resting on the chest.` |
| `c_trophy` | 미니 트로피 | `ITEM: holding a small gold two-handled trophy in the right wing, at the side of the body.` |
| `c_sign` | 응원봉 | `ITEM: holding a pink cheering light stick (glow stick) upright in the right wing.` |
| `c_balloon` | 풍선 | `ITEM: holding a string in the left wing tied to a red balloon floating up-left above the head.` |
| `c_wing` | 황금 날개 | `ITEM: a pair of large golden angel wings spread out behind the body (behind the shoulders), the character in front.` |
| `c_aura` | 논란 오라 | `ITEM: a soft glowing red-orange aura / flame halo surrounding the whole body, behind the character.` |

### 상태(state)
| 키 | 이름 | 문장 |
|---|---|---|
| `work` | 근무 상자 | `ITEM: holding a brown cardboard delivery box (with a tan tape strip) in the right wing at the side of the body.` |
| `staff` | 스탭 명찰 | `ITEM: a small light-blue rectangular staff badge pinned on the right side of the chest.` |
| `stun` | 행동불능 | `EXPRESSION: eyes replaced by "X X" marks, three small gold four-point stars circling above the head.` |

## 품질 체크(받은 뒤)
- [ ] 캐릭터 실루엣(머리 크기·팔·발 위치)이 참조와 1~2px 안에서 같다 → 아니면 재생성(맞춤 스크립트가 못 잡는다)
- [ ] 아이템 외의 색·선이 안 바뀌었다(볼터치·부리 등)
- [ ] 의상이 팔·머리 위로 넘치지 않는다, 모자가 눈을 가리지 않는다(선글라스 제외)
- [ ] 글자·워터마크 없음
