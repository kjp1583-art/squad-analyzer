# tests/raid — 레이드 0단계 시뮬 이식 · 방 부하 측정 (임시 측정 도구)

4인 파티 레이드 계획(`docs/party-raid/DESIGN.md` §4 「0단계」)에서 **서버가 흐접새우(`survivors.html`)의 게임 계산을 Node 에서
헤드리스로 돌릴 수 있는가**, **그 방을 서울 1 vCPU VPS 에서 3개 돌려도 틱이 버티는가**를 재는 도구입니다.
제품이 아닙니다. 읽기만 합니다 — `survivors.html`·`index.html`·`data/*` 는 건드리지 않습니다.

> 이 폴더의 `.build/`(생성물)는 git 에서 제외됩니다. 파이썬은 `g4_test.py` 편의 래퍼에만 쓰고, 나머지는 전부 **Node 22 만 있으면** 돕니다.

## 파일

| 파일 | 하는 일 |
|---|---|
| `build_sim.js` | `survivors.html` 의 메인 게임 `<script>` 블록에서 `sim.js`(최소 훅 `window.__p6x`) 와 `sim_mp.js`(4액터 패치 사본)를 만든다. 앵커 존재·유일성 검사 |
| `run_stub.js` | 브라우저 없이 `sim*.js` 를 올리는 DOM 스텁(Node `vm`) |
| `mp_run.js` | 4액터 N초 실행기. 예외·일찍 끝남·상태 멈춤·NaN 을 종료코드로 알림 |
| `cover.js` | 무기 전종이 실제로 피해를 남기는지(`dmgBy`) 확인 |
| `g4_test.py` | G4 판정 래퍼(5조합 + 보강 조합 × 900초, 무기 전종, 선택: 린트·결정성) |
| `bench_rooms.js` / `bench_worker.js` / `bench_stats.js` | G2' 측정기(방당 worker 1개 · 30Hz · 스냅샷 인코딩 흉내 · GC · 이벤트 루프 지연 · CPU) |
| `eslint.sim.config.js` | 시뮬 본체용 ESLint `no-undef` 설정 |
| `sim_selftest.js` | 시뮬 이식 쪽 자기 시험(앵커 훼손·연결부 같은 줄 구멍·판 종료 검출·낡은 사본 재사용·지연 생성 필드·월드 풀·퍼센타일·스텁·린트 민감도 등 41건) |
| `bench_selftest.js` | 방 부하 측정기 자기 시험(판정 표·힙 상한 무시 검출·거친 입력 거절·SIGINT/SIGTERM/SIGHUP·전체 시간 제한·저장 실패·주입 시험 등 59건, 약 1분) |
| `../../.github/workflows/raid-sim.yml` | 수동 실행 전용 점검(푸시·예약 트리거 없음, 계정 비밀 안 씀) |

## 사용법 (명령 전부)

```bash
# 0) 도구 자기 시험 (각각 20초~1분)
node tests/raid/sim_selftest.js [--no-lint]
node tests/raid/bench_selftest.js

# 1) 빌드: tests/raid/.build/{sim.js, sim_mp.js, manifest.json}
node tests/raid/build_sim.js [--src survivors.html] [--out tests/raid/.build] [--no-verify] [--quiet] [--world-pools x4|first]
#   종료코드 0 성공 · 2 앵커 어긋남 · 3 로드 시험 실패 · 66 입력 파일을 못 읽음
#   --world-pools: 판 전체가 같이 쓰는 풀(적 투사체 등)을 액터마다 돌려 틱당 4번 진행(x4, 기본) / 첫 액터 차례에 1번만(first) — 아래 「한계 2」

# 2) 4액터 N초 (게임 시간, 빠르게 감기). 예외 시 게임 시각·스택을 찍고 종료코드 1
node tests/raid/mp_run.js --combo brj,jjg,mms,hrb --secs 900 [--hz 30] [--seed 1] [--move circle|stand|random] [--cpu] [--json] [--out FILE]
node tests/raid/mp_run.js --list            # 현재 캐릭터·무기·기본 조합을 JSON 으로
#   종료코드 0 통과 · 1 예외 · 4 판이 일찍 끝남(endRun 호출 또는 결과 화면)/상태 멈춤/값이 유한하지 않음/게임 시각 S.t 가 요청한 초와 1초 이상 다름

# 3) 무기 전종 사용 확인 (보통 / 각성)
node tests/raid/cover.js [--secs 240] [--from 290] [--evo] [--seed 1]
#   종료코드 0 · 1 예외 · 4 끝내 피해를 못 남긴 무기 있음

# 4) G4 판정 (파이썬 3 필요, 나머지는 위 Node 명령을 부른다)
python3 tests/raid/g4_test.py                       # 5조합 + 보강 조합 × 900초 + 무기 전종 (기계가 한가하면 20분, 붐비면 한 시간 안팎)
python3 tests/raid/g4_test.py --quick               # 조합 1개 120초 + 무기 60초
python3 tests/raid/g4_test.py --lint --determinism  # + ESLint no-undef, 같은 시드 두 번 해시 비교
python3 tests/raid/g4_test.py --combo "a,b,c,d" --secs 300 --out result.json
#   종료코드 0 통과 · 1 예외 · 2 빌드(앵커) · 3 린트 · 4 기준 미달 · 5 환경(시간 초과·eslint 없음)
#   마지막 줄: 「G4 PASS」는 조합당 900초 이상 · 기본 조합 전부 · 무기 전종 확인을 모두 했을 때만. --quick · 900초 미만 · --combo · --no-extra · --no-cover 면
#   예외 없이 끝나도 「G4 (비공식 — 합격 판정 아님: 사유)」로 찍는다. 실패는 항상 「G4 FAIL」.

# 5) G2' 방 부하 (서울 VPS 에서 15분 합격 측정)
node tests/raid/bench_rooms.js --rooms 3 --secs 900 --realtime --out bench_3rooms.json
node tests/raid/bench_rooms.js --rooms 8 --secs 300 --realtime --out bench_8rooms.json   # 8방은 기록만
node tests/raid/bench_rooms.js --rooms 3 --secs 60 --fast --out quick.json               # 점검용(판정 대상 아님)
#   옵션: --hz 30 --combos "a,b,c,d;e,f,g,h" (또는 --combos heavy) --src survivors.html --heap-mb 128 --seed N --strict
#         --hb-timeout-ms 2000 --load-timeout-s 60 --wall-limit-s N --quiet --world-pools x4|first
#   상한: --rooms ≤ 32 · --secs ≤ 21600 · --hz ≤ 240 · --heap-mb 16~65536 (넘으면 측정 전에 64 로 거절)
#   종료코드 0 끝까지 측정(합격 여부와 무관 · --strict 면 pass===false 일 때 4) · 1 방이 죽음/멈춤/예외 · 2 빌드(앵커) · 3 로드 시험 실패
#           5 전체 시간 제한(--wall-limit-s)에 걸림 · 6 결과 파일을 못 씀(요약은 먼저 찍고 JSON 전체를 stdout 에 남김) · 64 옵션 오류(--out 을 쓸 수 없는 경우 포함 — 측정 전에 확인)
#           66 입력 파일을 못 읽음 · 129/130/143 SIGHUP/SIGINT/SIGTERM
#   중간에 멈춘 결과(신호·전체 시간 제한)는 --out 이 아니라 <out 에서 .json 을 뗀 이름>.partial.json 에 저장한다 —
#   절반만 돈 결과가 완주한 결과 파일 이름을 차지하지 않게(이미 있는 결과 파일을 건너뛰는 스크립트가 속지 않도록).
```

**방별 힙 상한(`--heap-mb`)은 환경변수 `NODE_OPTIONS` 에 `--max-old-space-size` 가 있으면 조용히 무시됩니다**(Node 의 동작 — 이 샌드박스는
`NODE_OPTIONS=--max-old-space-size=8192` 라 4MB 든 128MB 든 방이 보고하는 한도가 8240MB 였습니다). 설계 §7.1 의 「한 방의 메모리 폭주는 그 방만」 격리는 상한이 적용될 때만 시험됩니다.
이 도구는 방이 보고한 한도를 `--heap-mb` 와 대조해 어긋나면 stderr 에 WARN, JSON 에 `input.heap_cap_effective:false`, `host.node_options` 를 남기고
합격 판정에서 「참고」로 돌립니다. OOM 경로를 시험할 때는 `env -u NODE_OPTIONS node tests/raid/bench_rooms.js … --heap-mb 64 --fault oom:1:3` (방 1만 `oom`, 나머지 정상) —
상한이 무시되는 환경에서 `--fault oom` 은 기계 메모리를 다 먹으므로 이 도구가 64 로 거절합니다.

1 코어에 고정해서 재려면 `taskset -c 0 node tests/raid/bench_rooms.js …`. 측정 중에는 `uptime`(load)을 같이 기록하세요 —
JSON 의 `host.loadavg.start/end` 에도 들어갑니다.

## 합격 기준과 이 도구가 주장하는 것 / 주장하지 않는 것

| 기준 (DESIGN §4) | 이 도구 | 주장하는 것 | 주장하지 않는 것 |
|---|---|---|---|
| **G4** 시뮬 이식 뒤 5조합 × 900초 예외 0 · 무기 전종 | `g4_test.py` (`mp_run.js`·`cover.js`) | 텍스트 패치로 만든 **4액터 사본**이 현재 `survivors.html` 에서 900초 동안 예외·NaN 없이 돈다. 무기 전종이 피해를 남긴다. 같은 시드면 같은 판이다 | 제품 이식이 됐다는 것. 사본은 **시험용**이고 설계서가 제품에는 텍스트 패치 빌드를 금지한다 |
| **G2'** 서울 1 vCPU 3방 × 4액터 15분: 방 틱 p99 ≤ 25ms, 이벤트 루프 지연 p99 ≤ 10ms (8방은 기록만) | `bench_rooms.js` | 틱 시간(시뮬 + 스냅샷 인코딩 흉내 + 부모로 전달)·GC·루프 지연·CPU 를 **같은 방식으로** 잴 수 있다 | **샌드박스 수치는 서울 VPS 합격 근거가 아니다.** 공용 4코어에 load 가 수십이라 흔들림이 크다. JSON 의 `gates.G2.note` 에도 이 문장이 들어간다. `gates.G2.pass` 는 아래 「합격 근거가 되는 조건」을 다 채웠을 때만 true/false 다 |
| G1·G3·G5 | (다른 도구: 핑 페이지·에코 서버·소켓 생존 시험) | — | — |

### 알고 있는 한계 (읽고 쓰세요)

1. **텍스트 패치 사본은 제품과 다릅니다.** `update()` 를 문자열로 잘라 액터 루프로 감싼 것입니다. 제품은 「액터 번들」 리팩터(설계 §4.0)로 만듭니다. 이 사본이 재는 것은 "그런 구조가 가능하다/대략 이만큼 든다"입니다.
2. **액터별 무기 소유 구분이 완전하지 않습니다.** 액터마다 갈라 갖는 `S` 필드는 `build_sim.js` 의 `PKS`(72개)이고, 나머지는 판 전체가 같이 씁니다. 따라다니는 **소환물 풀**(`rangs` 새우깡 궤도 · `pets` 병아리 · `lid` 궤도 등)과 투사체 풀은 주인이 없어서, 그 무기를 안 가진 액터의 차례가 소유자의 소환물을 꺼 버리거나(예: `S.ev.shrimp` 가 아닌 액터가 궤도 부메랑을 끈다) 다른 액터의 것을 자기 것처럼 처리합니다. 실측: 무기를 4명에게 나눠 쥐면 `shrimp·chick·lid`(각성 땐 더) 가 **간헐적으로 피해를 못 남깁니다**(솔로 사본에서는 셋 다 남깁니다). 그래서 `cover.js` 는 1차에서 빠진 무기를 **4명 모두가 쥔** 2차로 다시 확인하고, 거기서도 못 본 것만 실패로 칩니다. 이 한계는 부하 수치에도 영향을 줍니다(소환물이 꺼지면 계산이 달라질 수 있으나 어느 쪽으로 얼마나인지는 확인 못 함).
   **판 전체가 같이 쓰는 풀(적 투사체 `eshots` · 위험 지대 `hazards` · 구름 `clouds` · 시한폭탄 `ebooms` · 부채꼴 `cone` · 카드 `cardW`)은 틱당 4번 진행됩니다**(액터마다 한 번씩 돌리므로
   이동·수명이 4배 빠르다 — 적 투사체 하나를 넣고 `update(1/30)` 한 번: x4 는 13.33px·수명 −0.133, 솔로·`first` 는 3.33px·−0.033. `sim_selftest.js` 가 확인). 시한폭탄 같은 보스 공격은
   그 틱에 처음 도는 액터(액터 0)에게만 터지고 나머지는 못 맞습니다. 기본(`--world-pools x4`)은 첫 스파이크가 재던 방식이라 유지하고, `--world-pools first`(월드 풀을 첫 액터 차례에서 한 번만 돌림 —
   다른 액터는 이 풀에 맞지 않음)로 CPU 차이를 비교할 수 있게 했습니다. 차이 실측은 아래 「샌드박스 참고 수치」.
3. **봇은 단순합니다.** 액터 4명이 사각형으로 돌고(`--move circle`), 레벨업 카드는 순서대로 고르며, **죽지 않습니다**(`die()` 를 무효화 — 피해를 흡수한 횟수만 셉니다). 900초(S.t=900)까지는 돌지만 **사망·소생·관전·60분 승리(`WIN_T=3600`)·실제 사람의 움직임** 경로는 안 밟습니다.
4. **스냅샷 인코딩은 흉내입니다.** 살아 있는 적 × 7B + 액터 4 × 32B + 머리 100B 를 실제 상태에서 채우지만, 이벤트 큐(투사체·폭발·숫자)·델타 압축·소켓 쓰기·`ws` 라이브러리 비용은 **들어 있지 않습니다**. 부모 프로세스도 받은 버퍼를 세기만 하고 4개 소켓으로 보내지 않습니다.
5. **스텁이 삼키는 것.** 화면 그리기·소리·`fetch`(항상 거절, 횟수만 셈)·타이머(실행 안 함, 횟수만 셈). 그 밖에 시뮬이 건드린 브라우저 이름은 `mp_run.js --trace` 가 보여 줍니다. 이어하기(RES) 모듈은 로드되어 `visibilitychange`/`pagehide` 등을 등록하지만 헤드리스에서는 일어나지 않는 일입니다.
6. 이식 후 시뮬의 **서버 입력·시계·난수 정책**(고정 dt, 시드 PRNG)은 이 도구가 대신 정해 주지 않습니다. 시드 난수는 컨텍스트 안의 `Math.random` 을 바꿔 흉내 낸 것입니다.
7. 처음 1~2초(JIT 데우기)의 느린 틱이 `max`/p99.9 에 들어갑니다. 900초(27,000틱) 측정에서는 p99 에 거의 영향이 없지만, 짧은 측정(60~120초)에서는 눈에 띕니다.
8. **일정 정책이 설계 §2.4 와 다릅니다.** 설계는 「서버 루프는 hrtime 누적기, 따라잡기 최대 3틱」인데, 이 측정기는 **따라잡지 않습니다** — 늦으면 기준 시각을 뒤로 밀어 게임이 벽시계보다 느려집니다.
   정상 조건(3방 900초)에서는 차이가 미미합니다(wall 900.1~900.6s). 하지만 과부하에서는 조용히 스트레스가 덜어집니다(검증자 재현 — 이 보완 작업에서 다시 재지는 않음: 8방×300초 realtime, load 13→25 에서 wall 349.2s / 게임 300s). 그래서 방마다 `slip_s`(= 밀린 총량)와
   `late_ticks` 를 결과에 남기고 `gates.G2.aux.slip_s_max` 로 올립니다. `slip_s` 가 1초를 넘으면 `note` 에도 적습니다. 8방은 「기록만」이지만 이 값을 같이 읽으세요.
9. **합격 지표(tick p99)는 틱의 1% 이하 정지를 통과시킵니다.** 27,000틱이면 270번까지 33ms 틱이 있어도 p99 는 한도 안일 수 있습니다(검증자의 주입 시험: 100번째 틱마다 40ms 정지 → p99 19.7ms 통과, 25ms 초과 9회. `bench_selftest.js` 에도 같은 모양의 시험이 있다).
   그래서 `gates.G2.aux` 에 보조 지표(25ms 초과 틱 비율 · late 비율 · 「마감 대비 완료 지연」= start_delay+tick 의 p99)를 함께 싣습니다. **「25ms 초과 틱 비율 ≤ 0.1%」를 보조 기준으로 제안**하며
   (`aux.over25_within_suggested`), 판정(`pass`)에는 쓰지 않습니다 — 설계서 G2' 를 바꾸는 일이라 사장님/설계 쪽 결정입니다.

## 샌드박스 참고 수치 (2026-10-09) — 서울 VPS 합격 근거가 아님

개발 샌드박스(4코어 공용 가상 머신, `taskset -c 0` 으로 한 코어에 고정, 기본 5조합 중 앞 3개)에서 잰 값입니다.
**다른 워크플로가 같이 돌아 load 가 40~60 까지 오르내렸고**, 기계 사양이 목표 VPS 와 다릅니다. 그래서 「이 도구가 돈다」는 증거이지 G2' 합격 증거가 아닙니다.

| 측정 | 조건 | 결과 |
|---|---|---|
| 3방 × 15분 realtime (1코어 고정) 2회 | load 0.9~2 (조용한 시간) | 방 틱 p99 **11.0 ~ 16.3ms** (한도 25) · p99.9 16~24ms · 25ms 넘은 틱 **4~5 / 27,000** · 가장 느린 틱 40~110ms(대부분 시작 직후) · 부모 이벤트 루프 지연 p99 **5.5 ~ 6.3ms** (한도 10) · CPU 점유 약 **36%** · GC 방당 2,100~2,800회(합 2.2~5초, 최대 36ms) · 힙 최대 약 30MB · rss 최대 약 297MB · 스냅샷 평균 1.1~1.2KB(최대 1,768B) |
| 3방 × 2분 realtime | load 40~54 (붐빌 때) | 방 틱 p99 **75~108ms**, 루프 지연 p99 113~135ms — 한도의 4~5배. 같은 조건에서 **스레드 CPU 시간**(`tick_cpu_ms`)은 p99 1.7~1.9ms 였다 → 대기 시간이 값을 지배했다 |
| 3방 × 2분 realtime | load 2.6 (조용) | 방 틱 p99 4.8~6.1ms · 루프 지연 p99 3.1ms |
| 8방 × 1분 realtime | load 3 (조용) | 방 틱 p99 5.2~7.8ms · 루프 지연 p99 4.9ms · CPU 62% · rss 314MB (※ 1분이라 초반의 가벼운 구간만) |
| 3방 × 15분 `--fast` 무거운 조합 3개 (고정 없음, load 50) | `tw,yumi,eom,yj` / `bgb,brj,psg,sr` / `ssu,amd,ildj,kyo` | 틱 **CPU 시간** p99 5.1~5.6ms · p99.9 6.6~7.1ms · 최대 약 15ms. 방 1개가 게임 1초에 쓴 CPU 약 100ms |
| G4 5조합 + 보강 1조합 × 900초 | load 20~60 | 전부 예외 0, 조합당 CPU 약 3.0~4.9ms/틱 (아래 요약) |
| 월드 풀 처리 비교 `--world-pools x4` vs `first` (2026-10-09) | `ssu,amd,ildj,kyo` 600초, 시드 7, 같은 판을 2회씩 번갈아(load 16~18) | 틱당 CPU **x4 2.194 / 2.169ms · first 2.188 / 2.168ms** — 차이 0.3% 이하(잡음 안). 같은 시드 두 번은 해시가 같고(결정적) x4 와 first 는 달라(판이 다르게 흐름). 적 수 최대 220 으로 같음. **이 한 조합·600초에서는 월드 풀 4배 진행이 CPU 수치를 눈에 띄게 바꾸지 않았다**(다른 조합·900초·판의 흐름이 달라지는 효과는 확인 못 함) |

해석할 때 조심할 것
- 시계 시간(`tick_ms`)은 공용 기계에서 거의 쓸모가 없을 만큼 흔들립니다. 같은 구성이 load 에 따라 p99 가 5ms 에서 100ms 로 바뀌었습니다. VPS 에서는 **다른 프로세스를 끄고** 재세요.
- 세 방의 틱이 같은 순간에 몰리면 1 vCPU 에서는 서로 기다립니다. 틱 CPU 시간이 p99 약 4~5ms 이므로 세 방이 겹치면 대략 12~15ms 로 보이는데, 이것은 **추정**이고 실제 겹침은 `--realtime` 측정(위 표 첫 줄)이 보여 줍니다.
- 가장 느린 틱이 처음 몇 초(JIT 데우기)에만 몰린다고 보면 안 됩니다. 처음 측정(2회)에서는 대부분 시작 직후였지만, 검증의 15분 재현에서는 최악 틱 3개가 모두 중간 게임 시각(888/173/632초)에 53~63ms 였고
  방당 25ms 초과 9~17회·late 9~11회였습니다(합격 한도 안이었음). 즉 GC 최대 25~33ms 와 겹친 정지가 약 1.5분에 한 번 있는 셈입니다 — 원인은 확인 못 함. `tick_max_at_game_s` 와 `tick_over_25ms` 를 같이 보세요.
- 이 수치에 **소켓 쓰기·직렬화(`ws`)·이벤트 큐·델타 인코딩**은 들어 있지 않습니다. 실제 서버의 비용은 이보다 큽니다.

## 산출물 스키마

### `bench_rooms.js --out` (`kind: "rooms-bench"`, `v: 1`)

```jsonc
{
  "v": 1, "kind": "rooms-bench", "started_at": "ISO", "finished_at": "ISO", "wall_s": 905.3,
  "interrupted": false, "interrupted_by": null,                       // SIGINT | SIGTERM | SIGHUP | "wall-limit" — 중단됐으면 이 파일은 <out>.partial.json
  "host": { "node": "v22.x", "cpus": 4, "cpus_allowed": "0", "cores_effective": 1, "model": "CPU 이름", "loadavg": {"start":[1m,5m,15m], "end":[…]},
            "mem_mb": 7900, "platform": "linux-x64",
            "node_options": null, "nice": 0,                           // NODE_OPTIONS 값(힙 상한을 덮어쓰는지 보려고) · 프로세스 nice 값
            "cgroup": {"cpu_max": "max 100000", "cpu_weight": "100", "quota_cpus": null} },   // 컨테이너/systemd 의 CPU 쿼터·가중치(읽을 수 있을 때)
  "input": { "survivors_sha256": "…", "actors": 4, "hz": 30, "secs": 900, "rooms": 3, "realtime": true,
             "combos": ["brj,jjg,mms,hrb", "…"], "heap_mb": 128, "heap_cap_effective": true, "heap_limit_reported_mb": 176,   // 방이 보고한 힙 한도 ≈ heap_mb+48 이어야 상한이 적용된 것
             "world_pools": "x4", "seed": 20261008, "hb_timeout_ms": 2000 },
  "rooms": [ {
      "id": 0, "chars": ["brj","jjg","mms","hrb"], "ticks": 27000, "status": "ok",        // 아래 「방 상태」 참고
      "game_s": 900, "wall_s": 900.1,
      "tick_ms":   {"n":27000,"mean":…,"p50":…,"p95":…,"p99":…,"p999":…,"max":…},          // 시뮬 + 인코딩 + 부모로 postMessage(= 하트비트)
      "update_ms": {…}, "encode_ms": {…},                                                   // 위 합의 분해
      "tick_cpu_ms": {…}, "tick_cpu_ms_total": …,                                        // 같은 틱의 스레드 CPU 시간(선점·대기 제외, Node 22.19+). 공용 기계에서 「일의 크기」와 「CPU 를 못 받아 늦은 것」을 가른다
      "start_delay_ms": {…},                                                                // realtime 에서 마감 대비 시작이 늦은 정도(타이머·스케줄러 잡음) / fast 면 null
      "tick_over_25ms": 0, "tick_max_at_game_s": 0.3,                                      // 틱이 25ms 를 넘은 횟수 / 가장 느린 틱이 나온 게임 시각(초: 시작 직후 데우기인지 중간인지 구분)
      "late_ticks": 0, "late_max_ms": 0, "slip_s": 0,                                       // 틱이 끝난 시각이 「다음 틱의 마감」을 넘긴 횟수 / 최대 초과 ms / 그렇게 밀린 총량(초: 게임이 벽시계보다 느려진 만큼. fast 면 null)
      "deadline_ms": {…},                                                                   // 마감 대비 완료 지연 = start_delay + tick (realtime 만) — 시작이 늦은 정지까지 함께 본다
      "errors": 0, "first_error": null,
      "gc": {"count":…,"total_ms":…,"max_ms":…},                                            // PerformanceObserver 'gc' (컨텍스트 로드 뒤부터)
      "heap_mb_max": …, "heap_limit_mb": …, "snap_bytes": {"mean":…,"max":…}      // heap_limit_mb: 방이 보고한 힙 한도(상한이 적용되면 --heap-mb+48MB 안팎)
    } ],
  "loop_delay_ms": {"p50":…,"p99":…,"max":…,"resolution_ms":10},    // 부모 monitorEventLoopDelay − 해상도 10ms(바탕선)
  "cpu": {"user_ms":…,"system_ms":…,"pct_of_1cpu":…,               // 프로세스 전체(워커·GC·JIT 스레드 포함) CPU ÷ 실제 시간
          "ms_per_room_game_s":…, "est_realtime_pct_of_1cpu":…},   // 방 1개가 게임 1초에 쓴 CPU(ms) / 그걸 실시간 30Hz·방 수만큼 돌릴 때 필요한 한 코어 점유율 추정(--fast·공용 기계에서도 의미 있음, 추정치)
  "rss_mb_max": …,
  "gates": { "G2": { "tick_p99_ms_max_over_rooms": …, "limit": 25, "loop_delay_p99_ms": …, "limit2": 10,
                     "within_limits": true | false | null,       // 두 수치가 한도 안인가(조건과 무관한 사실)
                     "qualified": true | false, "qualified_unmet": ["측정 4초 < 900초", …],   // 합격 근거가 되는 조건을 다 채웠나 / 못 채운 이유
                     "pass": true | false | "참고" | "기록만",
                     "aux": { "late_ratio_max": …, "tick_over_25ms_ratio_max": …, "deadline_p99_ms_max": …, "slip_s_max": …, "suggested_over25_ratio_limit": 0.001, "over25_within_suggested": … },
                     "note": "합격 판정은 목표 사양(서울 1 vCPU VPS)에서만 의미가 있다 — 다른 기계의 값은 참고용 …" } }
}
```

### `gates.G2.pass` 를 읽는 법 (JSON 을 기계가 읽거나 요약 한 줄만 볼 때)

| `pass` | 뜻 |
|---|---|
| `true` / `false` | **합격 근거가 되는 조건을 전부 채운 측정**에서 방 틱 p99 ≤ 25ms **그리고** 루프 지연 p99 ≤ 10ms 인가(그리고 모든 방이 정상 종료). 조건: 측정 900초 이상 · 방 3개 · `--realtime` · 30Hz · **쓸 수 있는 CPU 코어 1개**(`taskset -c 0`, 1코어 기계, 또는 cgroup 쿼터 1 이하) · 방별 힙 상한이 적용됨 · 측정 중 load(1분) ≤ 코어 수 × 2 |
| `"참고"` | 위 조건 중 하나라도 못 채웠다 — **합격도 불합격도 아니다**(`within_limits` 는 수치가 한도 안/밖이었다는 사실만 알려 줌). 이유는 `qualified_unmet` 과 `note`. 요약 한 줄에는 「참고(합격 판정 아님)」으로 찍힌다 |
| `"기록만"` | 방 8개 이상이거나 `--fast` — 판정 대상이 아님 |
| `false`(조건과 무관) | 방이 죽었거나(`oom`·`killed_hb`·`error` …) 중간에 멈췄다 — 합격으로 읽힐 일이 없는 쪽이라 조건을 따지지 않고 `false` |

`aux` 는 판정에 안 쓰이는 보조 지표입니다(한계 9). **합격은 같은 조건으로 3번 재서 가장 나쁜 값으로 판단**하세요 — 방들의 틱 격자 위상은 컨텍스트 로드 시각 차로 정해져 실행마다 달라, 같은 조건에서도 p99 가 11.0 → 16.3ms 처럼 흔들립니다.
기본 3방은 조합 0·1·2 이고 가장 무거운 조합(`bbb,eom,yj,tw` · `ssu,amd,ildj,kyo`, 900초 CPU 약 3.9ms/틱)보다 20% 가량 가볍습니다(검증의 실측: 기본 평균 3.2 vs 최대 3.9ms). 무거운 쪽으로 재려면 `--combos heavy`
(= `ssu,amd,ildj,kyo;bbb,eom,yj,tw;ssu,amd,ildj,kyo`).

### 방 상태 (`rooms[].status`)

`ok`(끝까지) · `stopped`(`stop` 메시지로 정상 중단) · `ended_early`(판이 중간에 끝남 — 승리·종료 호출) · `error`(`update()` 가 예외 — **통계는 그때까지 채워져 있고** `first_error` 에 사유) ·
`killed_hb`(하트비트 무응답 → 그 방만 terminate, 통계 `null`) · `crashed`(워커 비정상 종료) · `oom`(방별 힙 상한 초과 — 상한이 적용될 때만 나온다) · `load-timeout`(컨텍스트 로드가 `--load-timeout-s` 초과) ·
`wall-limit`(전체 시간 제한에 걸려 terminate) · `fatal`(워커 초기화 오류, 예: 없는 캐릭터 키) · `no-stats`(통계 없이 끝남).
- **공용 기계에서는 `tick_ms` 보다 `tick_cpu_ms` 를 먼저 보세요.** `tick_ms` 는 시계 시간이라 다른 프로세스에 CPU 를 빼앗기면 그대로 늘어납니다(load 가 코어 수보다 훨씬 크면 p99 가 일의 크기가 아니라 대기 시간이 됩니다). 단, 목표 VPS 에서는 세 방의 틱이 같은 순간에 몰려 한 코어를 나눠 쓰므로 합격 판정은 `tick_ms`(시계 시간) 기준입니다.
- 죽거나 멈춘 방(`killed_hb`·`crashed`·`oom`·`load-timeout`·`fatal`)은 `tick_ms` 등이 `null`, `error` 에 사유가 들어갑니다. 그 방만 끝나고 나머지는 계속됩니다. (`error` — `update()` 예외 — 는 통계가 채워져 있습니다.)
- 퍼센타일은 표본(틱마다 1개)을 **전부 모아 정렬한 뒤 nearest-rank**(`sorted[ceil(p·n/100)−1]`)로 구한 **정확한 값**입니다. (히스토그램 근사 아님. 단, 부모의 이벤트 루프 지연만은 Node 의 히스토그램이라 근사입니다.)

### 그 밖의 JSON

- `build_sim.js` → `.build/manifest.json`: `survivors_sha256`, `builder_sha256`(build_sim.js 자신의 해시), `world_pools`, `script_blocks`(스크립트 블록 크기), `sim_sha256`, `sim_mp_sha256`, `verify.classify`(`S` 필드 분류 결과: 런타임 60틱 + 코드의 `S.<이름>` 정적 스캔), `built_at`. 생성된 `sim.js`/`sim_mp.js` 첫 줄에도 입력 sha256 이 주석으로 들어갑니다. 다른 도구(`mp_run`·`cover`·`bench_rooms`)는 **`survivors.html` 이 바뀌었거나 `build_sim.js` 자신이 바뀌었거나 `--world-pools` 가 다르면 자동으로 다시 빌드**하고(낡은 사본으로 조용히 시험하지 않음 — 패치 규칙을 고친 직후에도 마찬가지), 새로 만들 때 로드 시험(`verify`)도 합니다. S 필드 분류 경고(WARN)는 사본을 재사용할 때도 stderr 로 다시 알립니다.
- `mp_run.js --json/--out`: `combo, secs, hz, seed, ok, ticks, error{at_game_s,message,stack}, ended_early, stuck, nonfinite, time_mismatch, ms_per_tick, cpu_ms_per_tick, game_s, max_enemies, deaths_absorbed, actors[{k,lv,dmg,weapons}], dmg_by, hashes[30초마다], hash_final`.
- `cover.js --json`: `weapons_now, known_39, added, removed, first_pass_missing, second_pass_recovered, used, missing, ok`.
- `g4_test.py --out`: `combos, extra_combos, base_seed, runs[], cover[], determinism, lint, loadavg_start/end, exit, qualified, qualified_unmet, key_warnings, verdict`(마지막 줄 문구).

## `survivors.html` 이 바뀌어 앵커가 어긋났을 때

`build_sim.js` 는 패치가 기대하는 모든 문자열(`update()` 를 자르는 13곳 · 문장 치환 6곳 · `fire()`/`die()`/`endRun()` · 훅 자리)이 **존재하고 유일한지**,
구간 순서가 그대로인지, 패치가 **버리는 연결부**(`update()` 머리 · `waveTick`~`weapons` 사이 · `beamTick` 줄)에 새 문장이 끼지 않았는지 검사합니다
(머리 줄은 `EX.tick(dt);` 뒤에 **줄 끝 `//` 주석만** 허용합니다 — 같은 줄에 새 문장을 붙이면 4액터 사본에서 조용히 사라지므로 실패시킵니다).
하나라도 어긋나면 어느 앵커가 왜(없음 / N번 나옴 / 순서 바뀜 / 연결부에 새 코드) 안 맞는지 적고 **종료코드 2** 로 멈춥니다. 조용히 틀린 사본은 만들지 않습니다.

대처:
1. 메시지의 `[이름]` 과 문자열을 `build_sim.js` 의 `SEG_ANCHORS` / `REP_ANCHORS` / `makeSimMp` 에서 찾는다.
2. `survivors.html` 의 `function update(dt){` 근처에서 그 줄이 어떻게 바뀌었는지 `git log -p survivors.html` 로 본다.
3. 앵커 문자열을 새 모양으로 고치고, 치환 결과(`makeSimMp` 안 문자열)에 같은 의미의 변화를 반영한다. **새 문장이 연결부에 끼었다면** 그 문장이 액터마다 돌아야 하는지(루프 안으로) 월드에서 한 번만 돌아야 하는지 정해서 넣는다.
4. `S` 에 새 필드가 생겼다면 `verify` 가 `미분류` 로 알려 줍니다(런타임 60틱에 보이는 것 + 코드에 `S.<이름>` 으로 적힌 지연 생성 필드) — 액터별이면 `PKS`, 판 공용이면 `WORLD` 에 넣는다. 경고는 빌드를 막지 않으므로 `g4_test.py --strict-keys` 로 실패시킬 수 있고, 안 켜도 마지막 줄에 「경고 N건」이 붙는다.
5. `build_sim.js` 를 고쳤으면 다른 도구가 알아서 사본을 다시 만든다(`builder_sha256`). `node tests/raid/sim_selftest.js` 가 통과하는지(앵커를 일부러 망가뜨려도 잡는지), `g4_test.py --quick --lint --determinism` 이 통과하는지 확인한다.

## 린트 게이트 (`--lint`)

`eslint --no-config-lookup -c tests/raid/eslint.sim.config.js tests/raid/.build/sim.js tests/raid/.build/sim_mp.js` — `no-undef` 만 봅니다.
`sim.js`(솔로 훅 사본)와 `sim_mp.js`(패치 사본) **둘 다** 봅니다 — 패치가 만든 지역 변수 누락(설계서가 적은 612초 `ReferenceError` 류)을 잡으려는 것입니다
(`sim_selftest.js` 가 `const p=S.p` 를 일부러 빼 보고 잡히는지 확인합니다). 알려진 항목: `DOMMatrix` 1건(`try/catch` 안의 `new DOMMatrix()`) — `g4_test.py` 의 `KNOWN_LINT` 가 허용합니다.
브라우저 전역은 시뮬 코드가 쓰는 것만 설정 파일에 적었습니다(넓게 열면 진짜 미정의 이름이 가려집니다).

## VPS 에서 직접 돌리기 (Node 22 만 있으면 됨)

```bash
git clone --depth 1 https://github.com/kjp1583-art/squad-analyzer.git && cd squad-analyzer   # 또는 이 폴더와 survivors.html 만 복사
node tests/raid/build_sim.js
node tests/raid/bench_rooms.js --rooms 3 --secs 900 --realtime --out bench_3rooms.json
node tests/raid/bench_rooms.js --rooms 8 --secs 300 --realtime --out bench_8rooms.json
node tests/raid/mp_run.js --combo brj,jjg,mms,hrb --secs 900 --cpu
```
- 파이썬·ESLint 는 필요 없습니다(`g4_test.py`·`--lint` 만 씀). 측정 중에는 다른 무거운 작업(빌드·도커 pull)을 돌리지 않습니다.
- **`NODE_OPTIONS` 를 비우고 돌리세요**(`env -u NODE_OPTIONS node …`). `--max-old-space-size` 가 있으면 방별 힙 상한이 무시되어 합격 판정이 「참고」로 돌아갑니다(위 「사용법」).
- 1 vCPU 가 아닌 기계라면 `taskset -c 0` 으로 한 코어에 고정하고 `host.cpus_allowed` / `host.cores_effective` 를 확인하세요(JSON 에 같이 적힙니다). 합격 판정은 쓸 수 있는 코어가 1개일 때만 나옵니다.
- **우선순위를 낮춘 서비스(`Nice=19`·`CPUWeight=1`)로 돌리면 합격 측정이 왜곡됩니다**: CPU 가중치가 1 이면 백그라운드(sshd·journald·에코 서버)가 조금만 움직여도 tick/루프 지연이 부풀어,
  「실패」 값이 일의 크기가 아니라 우선순위를 반영합니다(합격이면 보수적으로 유효). 합격 측정용 유닛은 `Nice=0`·기본 `CPUWeight` 로 분리하는 것을 권합니다(에코 서버가 한가할 때만 돌리므로 충분). `host.nice`·`host.cgroup`(cpu.max/cpu.weight)에 실제 값이 기록됩니다.
- 합격 판정은 **같은 조건으로 3번 재서 가장 나쁜 값**으로, 가능하면 `--combos heavy` 로도 한 번 — 위 「`gates.G2.pass` 를 읽는 법」.
- 15분 실측은 `--realtime` 으로 실제로 15분이 걸립니다. 중간에 멈추려면 Ctrl-C **한 번**(SIGTERM·SIGHUP 도 같음 — 지금까지의 결과를 `<out>.partial.json` 에 저장하고 끝냄), 두 번이면 즉시 종료. 메모리: 8방×300초 rss 약 432MB, 3방×900초 약 294MB.
- 시험 전용 고장 주입: `--fault hang:1:5`(1번 방이 5초 뒤 멈춤 → 2초 무응답으로 그 방만 terminate), `crash`·`oom`·`throw` 도 있습니다(`oom` 은 `NODE_OPTIONS` 를 비워야 안전).

## 첫 스파이크(2026-10-08)와 달라진 점

이 도구는 첫 스파이크(저장소 밖의 일회용 스크립트 묶음)를 옮겨 온 것입니다. 달라진 점만 적습니다.
- DOM 스텁: localStorage 를 진짜 저장소처럼(`length`/`key`/`clear`), 이벤트 등록 기록, `fetch` 거절·타이머 비실행(횟수 기록), 컨텍스트 자체 내장 객체 사용, 시드 옵션, `--trace`.
- 패치 빌더: 파이썬 → Node. 앵커 존재·유일성·순서·버려지는 연결부 검사 추가. 훅 목록은 이 폴더 안(`build_sim.js`)에 정의합니다. 산출한 `update()` 본문은 스파이크 사본과 **바이트 단위로 같습니다**(2026-10-09 비교) —
  이후 보완(판 종료 카운터 `ENDS`, 꼬리의 `state` 되돌림 조건, `--world-pools`)은 의도한 차이입니다.
- 4액터 실행기: 조합·초·시드·이동 방식 지정, 예외 시 게임 시각·스택, 상태 멈춤·NaN 감시, 판 종료·게임 시각 대조, 해시.
- 무기 확인: 하드코딩 39개 → `WEAP` 에서 동적으로 구함(현재 **40종**: `sing`(노래부르기) 추가). 1차/2차 확인과 `--evo`.
- G4 래퍼: 기본 5조합 + 현재 캐릭터(18명) 중 빠진 것을 채우는 보강 조합 1개(`bbb,eom,yj,tw`).
