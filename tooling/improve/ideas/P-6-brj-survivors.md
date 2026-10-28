# P-6 🐤 브장신 서바이버 — 웹에서 하는 한 판 5~8분 생존 미니게임
- 상태: **출시 2026-09-29** — `survivors.html`(메인 탭 🦐 서바이벌 · `lab/P-6.html` 은 이동 안내) · 디스코드 로그인 기록·순위표(봇 `/p6/run`·`/p6/board`·`/p6/me`, 호스트 `p6_scores.json`) · 브장신 외 캐릭터는 그림 나올 때까지 ???(`REVEAL=false`)
- 한 줄: 브장신을 움직여 몰려오는 미니언을 피하며 자동 공격으로 버티고, 레벨업마다 무기 3개 중 하나를 고르는 웹 미니게임.
- 누구를 위해: 웹(SQUAD.GG)을 여는 클랜원 전원 — 특히 내전 없는 날 잠깐 들르는 사람. 디스코드 브장신 키우기를 안 하는 대다수도 로그인 없이 바로 한 판.
- 왜 지금: 사장님 요청 "브장신 주인공으로 P-6 시제품 만들어줘"(2026-09-29).
- 무엇을:
  - 타이틀(조작법 3줄 · 내 최고 기록) → ▶ 시작하기
  - PC WASD/방향키, 폰은 화면을 끌면 가상 조이스틱. 공격은 자동, 탭을 벗어나면 자동 일시정지.
  - 무기 4종(Lv1~5): 🌾 사료 투척(가까운 적) · 🍟 튀김기 오라(주변 지속 피해) · 🍣 아카보시 초밥(회전) · 🥚 달걀 폭탄(범위)
  - 패시브 5종: 👟 이동속도 · ❤️ 최대 HP · ⚡ 공격속도 · 🧲 획득 범위 · 🛡 깃털 갑옷
  - 시간이 갈수록 미니언 수·체력 상승, 3분 중간 보스, 6분 보스, 8분 버티면 승리
  - 결과: 생존 시간 · 처치 수 · 레벨 · 획득 무기 · 🔁 다시하기. 최고 기록은 내 브라우저(localStorage)에만.
- 이미 있는 것과의 관계: 디스코드 `#브장신키우기`(키우기·레이드·야생)는 텍스트 명령 기반 성장 게임이고, 이건 웹에서 손으로 조작하는 액션 한 판. 캐릭터 그림(img/brjang)만 공유하고 브장신 키우기의 레벨·장비·재화와는 아직 연결하지 않는다.
- 시제품: `lab/P-6.html`(메뉴 미연결 · noindex · 서버 쓰기 없음). 스크린샷은 시제품 세션 scratchpad `p6_*.png`.
- 만드는 순서:
  1) 시제품 — 한 파일 캔버스 게임, 로컬 최고 기록만 (완료)
  2) 다듬기 — 사장님 피드백으로 난이도 곡선·무기 밸런스·효과음·브장신 스킨(착용 스킨 반영) 조정, 메뉴 연결 여부 결정
  3) 로그인·순위표·보상 연결 — 디스코드 로그인 후 주간 순위표, 브장신 키우기 보상(사료 등) 소액 지급. **점수는 브라우저가 보내는 값이라 조작이 쉽다**: 보상 연결 시 서버 쪽 상한(판당 최대 시간 8분·처치 수 상한·하루 제출 횟수), 입력 기록 요약 검증, 보상은 순위 아닌 참가형 소액으로 시작
- 위험·되돌리기: 시제품은 독립 파일이라 다른 화면에 영향 없음 — 파일 삭제로 끝. 약한 폰 대비 적 수 상한(140/220)·오브젝트 풀. 순위표 단계에서는 점수 조작이 가장 큰 위험(위 3 참고).
- 성공 지표: 메뉴 연결 2주 뒤 — 시작 수·고유 플레이어 수·평균 생존 시간·재방문(2판↑) 비율, 브장신 키우기 채널 신규 유입.

## 진행 메모 (2026-09-29)
- 시제품: `lab/P-6.html` — 「🦐 흐접새우 서바이벌」. 흐접새우 트롤픽 적 7종(트롤 빌드 아이템 표시: AP 마오카이=라바돈 모자 머리 위, 마관 문도=마법사의 신발 발밑, 원딜 노틸=무한의 대검, 정글픽=강타 …), 보스 2종, 무기 4종, 클랜원 캐릭터 8명 해금, 협곡 배경(아군 정글→강가 3분→적 본진 6분, 코드로 그림).
- 개인별 기록(디스코드 로그인·시트 저장·순위표)은 **게임을 먼저 다듬은 뒤**(사장님 결정).
- 카톡 로그 말버릇 반영은 작업 환경 안전 설정에 막혀 보류 — 지금 대사·특성은 봇 공개 밈(BRJ_CAMEOS·BRJ_GEAR)만 사용.

## 클랜원 캐릭터 그림 — 방식 2: 브장신 + 시그니처 소품 (사장님 선택)
| 캐릭터 | 능력 | 소품(출처) | 새로 뽑을 그림 |
|---|---|---|---|
| 🔫 집중겜 | 치명타 20% | 치속크라켄 → 미스 포츈 코스프레 + 머리 위 배지(치명적 속도 룬·크라켄 학살자 아이템) | 붉은 가발·삼각모·쌍권총 병아리 |
| 🥲 망무새 | HP 30%↓ 피해 +60% | "난 망했어"(BRJ_CAMEOS) | 울상 + 머리 위 먹구름 |
| 🏄 조선제일하리보 | 이동속도 +20% | 다대포 서핑보드(g_surf) | 자크 코스프레(연두 슬라임 옷) 병아리 |
| ✈️ 승수 | 초당 회복 0.8·받는 피해 -1 | 기내 서비스(공개 밈 기반 · 키 `ssu`) | 승무원 제복 + 쟁반 든 병아리 |
| 🪧 앙앵모르딱 | 초당 회복 | 「팀원과싸우지말자」 표어(g_slogan) | 표어 피켓을 든 브장신 |
| 🎭 일단즐겨 | 경험치 +20% | 재물획득의 비약 → 진 코스프레(참고 그림 기반) | 은백색 전면 가면·크림 망토·마젠타 스카프·금 건틀릿·백금 장총 병아리 |
| 🍔 김야옹 | 레벨업 회복·획득 범위 | 버거킹 쿠폰(g_burger)·고양이 귀 | 고양이 귀 + 햄버거 든 브장신 |
| 🧱 단단묵직 | 밀쳐내기·피해 감소 | "디펜더"(BRJ_CAMEOS) | 철갑 투구 + 벽돌 방패 든 브장신 |

### 그림 제작 완료 (2026-09-30) — 8종 `img/survivors/char_<key>.webp` (256px WebP, 10~22 KB), survivors.html 에 연결, `REVEAL=false` 로 숨김 — 공개는 사장님 결정
- 레시피: 환경에 키 없음(세션 프록시가 인증) → `POST https://api.openai.com/v1/images/edits` 멀티파트(model=gpt-image-2, image=front.png, quality=low, size=1024x1024, background=transparent, output_format=png, prompt). 프록시가 ~30초에 끊어 medium 은 실패, low 는 ~20초. 분당 입력 이미지 5장 제한이라 동시 4개 이하·429 는 재시도. 결과는 회색/어두운 배경에 합성해 눈으로 확인(contact sheet).
- 프롬프트 틀: `Keep this yellow chick character exactly as it is — same head shape, face, cheeks, beak, feet, outline and art style — and it is <소품>. Front view, full body, centered, transparent background, same art style as the original, no text, no letters, no numbers.`
- 소품 문구: jjg = pirate bounty-hunter captain (fiery red-orange wavy wig, tricorn hat with feather, red-and-gold coat, a pistol in each wing; 초안은 크라켄 검 — 교체). 머리 위 배지 2개(⚡ 치명적 속도 룬 · 🐙 크라켄 학살자 6672)는 그림에 굽지 않고 실행 때 그린다(Data Dragon 이 이 환경에서 막혀 있음 — `bdg` 필드, 카드·판·결과 얼굴, 못 불러오면 이모지 배지) · mms = sad teary face + small dark rain cloud above its head · hrb = slime-monster costume (translucent lime-green suit and hood, goo drips, face visible) · ssu = flight attendant (navy jacket, cap, red neckerchief, serving tray, charming smile) · amd = small picket sign, blank with a heart icon · ildj = 진 코스프레 — 편집 호출에 이미지 2장(image[]: 1=병아리 원본, 2=의상 참고 그림의 캐릭터 부분만 잘라 글자 제외). 프롬프트: 'Image 1 is the yellow chick mascot to keep … Image 2 is a reference for the COSTUME only … smooth silver-white full-face mask with narrow dark eye slits and faint red glint, sleek black hair cap with pointed top, big cream-white hooded cloak with gold trim, magenta-crimson scarf collar with green gem brooch, gold gauntlets, dark trousers, ornate white-and-gold long pistol'. 채택: 변형 a(부리가 마스크 아래로 빼꼼 + 분홍 볼 보임 — 병아리로 읽힘), 변형 b(마스크만)는 진처럼은 보이나 병아리 같지 않아 탈락(2회 호출로 통과) · kyo = cat ears + hamburger · ddmj = small iron helmet + brick-pattern shield.
- 전원 첫 시도에 통과(8장 + 폐기한 초안 3장: 방패 · 서핑보드 · 물약병 · 바벨은 주인 요청으로 교체).
- 연결: 카드(`artEl`) · 판 중 스프라이트(`charImg`) · 결과 얼굴 — 보스 그림과 같은 경로(`hasArt`/`artUrl`). `shown()` 이 false 인 캐릭터는 그림을 요청하지 않는다.

### (옛 계획 — 완료) 다음 세션에서 이어 할 일 — "P-6 캐릭터 이미지 뽑아줘"
- 사장님이 작업 환경 설정에 `OPENAI_API_KEY` 를 넣음(채팅에 키 붙여 넣기 금지 · 코드·저장소에 키 넣기 금지). 모델: GPT-Image-2(이미지 편집 — 원본 유지·소품만 추가).
- 스크립트: 기본 `img/brjang/skins/base/front.png` + 위 소품 프롬프트 → 결과 PNG 를 직접 보고 확인(원본 병아리 모양 유지·소품·투명 배경) → 틀리면 프롬프트 고쳐 다시 → 후보를 사장님께 → 확정분은 brjang-part 절차로 파츠화 → 게임 캐릭터·브장신 꾸미기에 넣기.
- 프롬프트 틀: "이 노란 병아리 캐릭터를 그대로 유지하고 ○○를 들고 있게. 정면·전신·투명 배경 PNG·원본과 같은 크기·그림체."
