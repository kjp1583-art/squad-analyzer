# 웹 재생 하네스 (tests/web_replay)

실제 웹(`index.html`)을 **구글 시트 스냅샷**으로 재생해서, 사이트가 실제로 계산한 값(선수 평가·솔랭 칸·십이귀월 명단)과
화면(프로필·카드 팝업)을 꺼낸다. 「웹 ↔ 툴링 ↔ 분석기 동일성 점검」과 「고치기 전/후 비교」에 쓴다.
**스냅샷은 저장소에 없다**(닉네임·PUUID 가 든 공개 저장소) — 경로로 받는다. 저장소에 올라가는 시험은 합성 데이터만 쓴다.

## 준비물
- Python 3.11 · `playwright`(async) · `openpyxl` · Chromium(`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, 다른 곳이면 `PW_CHROME=<경로>`)
- 시트 스냅샷(xlsx): `curl -sSL -o sheet.xlsx "https://docs.google.com/spreadsheets/d/10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU/export?format=xlsx"`
- (선택) 마스터 티어표 — 웹이 따로 읽는 별도 시트: `curl -sS -o master.txt "https://docs.google.com/spreadsheets/d/1UFuAYsXZGMquChIZY-HGsEbE5fmzk4apgWEwthvpQ44/gviz/tq?gid=0&headers=1&tqx=out:json"` → `--master master.txt`. 안 주면 빈 표(웹은 CLAN_TIERS 만 쓴다).

## 도구
| 파일 | 하는 일 |
|---|---|
| `replay.py` | 웹을 열어 평가·명단·솔랭 지도를 JSON 으로, 카드·프로필 화면을 PNG 로 저장 |
| `compare.py` | 두 번의 재생 결과(전/후)를 견줘 바뀐 선수·십이귀월 명단 변화를 표로 |
| `parity.py` | 같은 xlsx 로 웹·툴링(`tooling/sibguiwol.py`)·분석기(`_load_solo_ranks`)가 같은 값을 내는지 점검(종료코드 0=일치) |
| `chain_test.py` | 합성 시트로 「LINK 사슬 인물의 솔랭이 언랭이 아니다」 등을 판정하고 세 구현을 대조(`unittest`) |
| `synth.py` | 합성 시트(가짜 닉네임·PUUID) 만들기 — 3단 사슬·2단·본계에 행·피크만·사슬+피크만 + 일반 24명 |
| `fetch_gviz.py` · `fidelity.py` | 실제 gviz 응답 받기 · xlsx 로 만든 응답이 실제와 칸 단위로 같은지 대조 |
| `gviz.py` | xlsx → gviz JSON 변환(열 종류 다수결 · 다른 종류 칸은 비움 · 문자열 열 안의 날짜는 서식 글자) |

## 쓰는 법
```bash
# 1) 재생 — 선수별 평가 · 십이귀월 명단 · 화면 캡처(--focus)
python3 tests/web_replay/replay.py --xlsx sheet.xlsx --master master.txt --src index.html --out out_after --focus 닉네임 --cats rift,aram
#   out_after/rift.json  {players, roster, solo(SOLO_RANKS), icons(PROFILE_ICONS), meta, focus}
#   out_after/aram.json  칼바람 카테고리
#   out_after/focus_<닉>_{profile,card}[_stats].png   프로필 화면·카드 팝업·🏅솔랭 칸 묶음
#   out_after/meta.json  요청 기록 — served(답한 탭) · missing(스냅샷에 없어 빈 표로 답한 탭) · unknown(알아볼 수 없는 요청) · blocked(막은 외부 요청)

# 2) 고치기 전 소스(예: git show origin/main:index.html > /tmp/before/index.html)로도 같은 재생 → 전/후 비교
python3 tests/web_replay/compare.py out_before out_after

# 3) 세 구현이 같은 값을 내는가
python3 tests/web_replay/parity.py --xlsx sheet.xlsx --master master.txt

# 4) 합성 데이터 시험(약 10초) — WEB_SRC=<다른 index.html> 로 옛 웹에 돌리면 실패해야 한다
python3 tests/web_replay/chain_test.py
python3 desktop/solo_link_chain_test.py          # 분석기 쪽(AST 로 함수만 떼어 가짜 시트로)
```
`--now 2026-10-09T15:00:00` 은 웹의 `Date.now()`/`new Date()` 만 고정한다(한국 시각 · 타이머는 그대로). 합성 시험은 항상 고정한다.
`--gviz-dir <폴더>` 는 `fetch_gviz.py` 로 받은 **실제 응답**으로 재생한다(xlsx 보다 우선).
`--eval "<JS 식>" …` 는 로딩이 끝난 협곡 상태에서 식을 평가해 `evals.json` 에 남긴다(전역 `let`/`const` — `ASSESSMENTS`·`SOLO_RANKS`·`ALT_TO_MAIN`·`canonOfName` … — 에 접근 가능). 예: LINK 쌍마다 부계·본계가 같은 대표닉으로 풀리는지.

## 무엇을 가로채나
`index.html` 이 구글 시트에서 읽는 모든 길을 브라우저 안에서 가로챈다 — `gviz/tq` 의 `gid=`·`sheet=` 두 방식,
`fetch`(→ `google.visualization.Query.setResponse({…});`)와 `<script>` JSONP(→ `responseHandler:<콜백>` 이름 그대로 `<콜백>({…});`),
`headers=0`(첫 행도 데이터). `gid` ↔ 탭 이름은 `index.html` 의 `CATEGORIES`·`TIER_HISTORY_GID`·`CLAN_TIERS_GID` 상수에서 읽는다
(2026-10-09 실제 응답의 `sig` 로 확인: 354094721=CLAN_TIERS · 631610741=TIER_HISTORY · 1282932443=KIWI_KIWI · 840541878=LOL_CLASSIC).
이미지·폰트·광고·디스코드·앱스스크립트·ddragon 같은 외부 요청은 막고 `blocked` 에 남긴다(프로필 아이콘 이미지는 안 뜬다 — 값은 `icons` 로 본다).

## 얼마나 실제와 같은가
2026-10-09 에 실제 gviz 응답 29개 탭과 같은 시점의 xlsx 변환 결과를 칸 단위로 대조했다 — `PERKS`·`UNIQ_MARKET`(갱신 시각이 든 JSON 한 칸)을 뺀 27개 탭이 열 종류·행 수·칸 값 모두 같았고,
두 방식으로 웹을 재생한 결과(전 선수 전 필드 · 십이귀월 명단 · 솔랭 지도)도 협곡·칼바람 모두 같았다. 재현하지 못하는 것: 디스코드 로그인·봇 API·외부 이미지.

## 알려진 한계
- 툴링(`sibguiwol.py`)은 xlsx 에서 숫자로 저장된 닉네임(숫자만으로 된 닉)을 `1562.0` 꼴로 읽는다 — `parity.py` 는 비교에서 `.0` 을 뗀다.
- 툴링은 협곡 탭(`CLASSIC_NORMAL`)만, 마스터 티어표 없이 CLAN_TIERS 만 읽는다. 웹과 명단 이름·순서는 같고 power 는 0.001 안에서 다르다 — 숫자 칸에 글자로 든 `점수`("24.7" 꼴)를 gviz 는 비우고 openpyxl 은 숫자로 읽기 때문이다(2026-10-09 실측: 그 칸들을 비우면 명단 12명 모두 소수 넷째 자리까지 같다).
