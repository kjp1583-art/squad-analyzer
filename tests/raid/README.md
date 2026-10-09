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
| `sim_selftest.js` | 이 도구들 자신의 시험(앵커 훼손·퍼센타일·스텁·린트 민감도 등 23건) |
| `../../.github/workflows/raid-sim.yml` | 수동 실행 전용 점검(푸시·예약 트리거 없음, 계정 비밀 안 씀) |

## 사용법 (명령 전부)

```bash
# 0) 도구 자기 시험 (약 1분)
node tests/raid/sim_selftest.js [--no-lint]

# 1) 빌드: tests/raid/.build/{sim.js, sim_mp.js, manifest.json}
node tests/raid/build_sim.js [--src survivors.html] [--out tests/raid/.build] [--no-verify] [--quiet]
#   종료코드 0 성공 · 2 앵커 어긋남 · 3 로드 시험 실패

# 2) 4액터 N초 (게임 시간, 빠르게 감기). 예외 시 게임 시각·스택을 찍고 종료코드 1
node tests/raid/mp_run.js --combo brj,jjg,mms,hrb --secs 900 [--hz 30] [--seed 1] [--move circle|stand|random] [--cpu] [--json] [--out FILE]
node tests/raid/mp_run.js --list            # 현재 캐릭터·무기·기본 조합을 JSON 으로
#   종료코드 0 통과 · 1 예외 · 4 판이 일찍 끝남/상태 멈춤/값이 유한하지 않음

# 3) 무기 전종 사용 확인 (보통 / 각성)
node tests/raid/cover.js [--secs 240] [--from 290] [--evo] [--seed 1]
#   종료코드 0 · 1 예외 · 4 끝내 피해를 못 남긴 무기 있음

# 4) G4 판정 (파이썬 3 필요, 나머지는 위 Node 명령을 부른다)
python3 tests/raid/g4_test.py                       # 5조합 + 보강 조합 × 900초 + 무기 전종 (공용 기계에서는 한 시간 안팎)
python3 tests/raid/g4_test.py --quick               # 조합 1개 120초 + 무기 60초
python3 tests/raid/g4_test.py --lint --determinism  # + ESLint no-undef, 같은 시드 두 번 해시 비교
python3 tests/raid/g4_test.py --combo "a,b,c,d" --secs 300 --out result.json
#   종료코드 0 통과 · 1 예외 · 2 빌드(앵커) · 3 린트 · 4 기준 미달 · 5 환경(시간 초과·eslint 없음)

# 5) G2' 방 부하 (서울 VPS 에서 15분 합격 측정)
node tests/raid/bench_rooms.js --rooms 3 --secs 900 --realtime --out bench_3rooms.json
node tests/raid/bench_rooms.js --rooms 8 --secs 300 --realtime --out bench_8rooms.json   # 8방은 기록만
node tests/raid/bench_rooms.js --rooms 3 --secs 60 --fast --out quick.json               # 점검용(판정 대상 아님)
#   옵션: --hz 30 --combos "a,b,c,d;e,f,g,h" --src survivors.html --heap-mb 128 --seed N --strict
#         --hb-timeout-ms 2000 --load-timeout-s 60 --wall-limit-s N --quiet
#   종료코드 0 끝까지 측정(합격 여부와 무관 · --strict 면 미달 시 4) · 1 방이 죽음/멈춤/예외 · 2 빌드 · 130 SIGINT(중간 결과 저장)
```

1 코어에 고정해서 재려면 `taskset -c 0 node tests/raid/bench_rooms.js …`. 측정 중에는 `uptime`(load)을 같이 기록하세요 —
JSON 의 `host.loadavg.start/end` 에도 들어갑니다.

## 합격 기준과 이 도구가 주장하는 것 / 주장하지 않는 것

| 기준 (DESIGN §4) | 이 도구 | 주장하는 것 | 주장하지 않는 것 |
|---|---|---|---|
| **G4** 시뮬 이식 뒤 5조합 × 900초 예외 0 · 무기 전종 | `g4_test.py` (`mp_run.js`·`cover.js`) | 텍스트 패치로 만든 **4액터 사본**이 현재 `survivors.html` 에서 900초 동안 예외·NaN 없이 돈다. 무기 전종이 피해를 남긴다. 같은 시드면 같은 판이다 | 제품 이식이 됐다는 것. 사본은 **시험용**이고 설계서가 제품에는 텍스트 패치 빌드를 금지한다 |
| **G2'** 서울 1 vCPU 3방 × 4액터 15분: 방 틱 p99 ≤ 25ms, 이벤트 루프 지연 p99 ≤ 10ms (8방은 기록만) | `bench_rooms.js` | 틱 시간(시뮬 + 스냅샷 인코딩 흉내 + 부모로 전달)·GC·루프 지연·CPU 를 **같은 방식으로** 잴 수 있다 | **샌드박스 수치는 서울 VPS 합격 근거가 아니다.** 공용 4코어에 load 가 수십이라 흔들림이 크다. JSON 의 `gates.G2.note` 에도 이 문장이 들어간다 |
| G1·G3·G5 | (다른 도구: 핑 페이지·에코 서버·소켓 생존 시험) | — | — |

### 알고 있는 한계 (읽고 쓰세요)

1. **텍스트 패치 사본은 제품과 다릅니다.** `update()` 를 문자열로 잘라 액터 루프로 감싼 것입니다. 제품은 「액터 번들」 리팩터(설계 §4.0)로 만듭니다. 이 사본이 재는 것은 "그런 구조가 가능하다/대략 이만큼 든다"입니다.
2. **액터별 무기 소유 구분이 완전하지 않습니다.** 액터마다 갈라 갖는 `S` 필드는 `build_sim.js` 의 `PKS`(72개)이고, 나머지는 판 전체가 같이 씁니다. 따라다니는 **소환물 풀**(`rangs` 새우깡 궤도 · `pets` 병아리 · `lid` 궤도 등)과 투사체 풀은 주인이 없어서, 그 무기를 안 가진 액터의 차례가 소유자의 소환물을 꺼 버리거나(예: `S.ev.shrimp` 가 아닌 액터가 궤도 부메랑을 끈다) 다른 액터의 것을 자기 것처럼 처리합니다. 실측: 무기를 4명에게 나눠 쥐면 `shrimp·chick·lid`(각성 땐 더) 가 **간헐적으로 피해를 못 남깁니다**(솔로 사본에서는 셋 다 남깁니다). 그래서 `cover.js` 는 1차에서 빠진 무기를 **4명 모두가 쥔** 2차로 다시 확인하고, 거기서도 못 본 것만 실패로 칩니다. 이 한계는 부하 수치에도 영향을 줍니다(소환물이 꺼지면 계산이 달라질 수 있으나 어느 쪽으로 얼마나인지는 확인 못 함).
3. **봇은 단순합니다.** 액터 4명이 사각형으로 돌고(`--move circle`), 레벨업 카드는 순서대로 고르며, **죽지 않습니다**(`die()` 를 무효화 — 피해를 흡수한 횟수만 셉니다). 후반(600초+)·실제 사람의 움직임·소생·관전 경로는 안 밟습니다.
4. **스냅샷 인코딩은 흉내입니다.** 살아 있는 적 × 7B + 액터 4 × 32B + 머리 100B 를 실제 상태에서 채우지만, 이벤트 큐(투사체·폭발·숫자)·델타 압축·소켓 쓰기·`ws` 라이브러리 비용은 **들어 있지 않습니다**. 부모 프로세스도 받은 버퍼를 세기만 하고 4개 소켓으로 보내지 않습니다.
5. **스텁이 삼키는 것.** 화면 그리기·소리·`fetch`(항상 거절, 횟수만 셈)·타이머(실행 안 함, 횟수만 셈). 그 밖에 시뮬이 건드린 브라우저 이름은 `mp_run.js --trace` 가 보여 줍니다. 이어하기(RES) 모듈은 로드되어 `visibilitychange`/`pagehide` 등을 등록하지만 헤드리스에서는 일어나지 않는 일입니다.
6. 이식 후 시뮬의 **서버 입력·시계·난수 정책**(고정 dt, 시드 PRNG)은 이 도구가 대신 정해 주지 않습니다. 시드 난수는 컨텍스트 안의 `Math.random` 을 바꿔 흉내 낸 것입니다.
7. 처음 1~2초(JIT 데우기)의 느린 틱이 `max`/p99.9 에 들어갑니다. 900초(27,000틱) 측정에서는 p99 에 거의 영향이 없지만, 짧은 측정(60~120초)에서는 눈에 띕니다.

## 산출물 스키마

### `bench_rooms.js --out` (`kind: "rooms-bench"`, `v: 1`)

```jsonc
{
  "v": 1, "kind": "rooms-bench", "started_at": "ISO", "finished_at": "ISO", "wall_s": 905.3, "interrupted": false,
  "host": { "node": "v22.x", "cpus": 4, "cpus_allowed": "0", "model": "CPU 이름", "loadavg": {"start":[1m,5m,15m], "end":[…]},
            "mem_mb": 7900, "platform": "linux-x64" },
  "input": { "survivors_sha256": "…", "actors": 4, "hz": 30, "secs": 900, "rooms": 3, "realtime": true,
             "combos": ["brj,jjg,mms,hrb", "…"], "heap_mb": 128, "seed": 20261008, "hb_timeout_ms": 2000 },
  "rooms": [ {
      "id": 0, "chars": ["brj","jjg","mms","hrb"], "ticks": 27000, "status": "ok",        // ok | stopped | ended_early | error | killed_hb | crashed | oom | load-timeout | wall-limit
      "game_s": 900, "wall_s": 900.1,
      "tick_ms":   {"n":27000,"mean":…,"p50":…,"p95":…,"p99":…,"p999":…,"max":…},          // 시뮬 + 인코딩 + 부모로 postMessage(= 하트비트)
      "update_ms": {…}, "encode_ms": {…},                                                   // 위 합의 분해
      "tick_cpu_ms": {…}, "tick_cpu_ms_total": …,                                        // 같은 틱의 스레드 CPU 시간(선점·대기 제외, Node 22.19+). 공용 기계에서 「일의 크기」와 「CPU 를 못 받아 늦은 것」을 가른다
      "start_delay_ms": {…},                                                                // realtime 에서 마감 대비 시작이 늦은 정도(타이머·스케줄러 잡음) / fast 면 null
      "late_ticks": 0, "late_max_ms": 0,                                                    // 틱이 끝난 시각이 「다음 틱의 마감」을 넘긴 횟수 / 최대 초과 ms
      "errors": 0, "first_error": null,
      "gc": {"count":…,"total_ms":…,"max_ms":…},                                            // PerformanceObserver 'gc' (컨텍스트 로드 뒤부터)
      "heap_mb_max": …, "heap_limit_mb": …, "snap_bytes": {"mean":…,"max":…}
    } ],
  "loop_delay_ms": {"p50":…,"p99":…,"max":…,"resolution_ms":10},    // 부모 monitorEventLoopDelay − 해상도 10ms(바탕선)
  "cpu": {"user_ms":…,"system_ms":…,"pct_of_1cpu":…,               // 프로세스 전체(워커·GC·JIT 스레드 포함) CPU ÷ 실제 시간
          "ms_per_room_game_s":…, "est_realtime_pct_of_1cpu":…},   // 방 1개가 게임 1초에 쓴 CPU(ms) / 그걸 실시간 30Hz·방 수만큼 돌릴 때 필요한 한 코어 점유율 추정(--fast·공용 기계에서도 의미 있음, 추정치)
  "rss_mb_max": …,
  "gates": { "G2": { "tick_p99_ms_max_over_rooms": …, "limit": 25, "loop_delay_p99_ms": …, "limit2": 10,
                     "pass": true | false | "기록만", "note": "합격 판정은 목표 사양(서울 1 vCPU VPS)에서만 의미가 있다 — 다른 기계의 값은 참고용 …" } }
}
```
- **공용 기계에서는 `tick_ms` 보다 `tick_cpu_ms` 를 먼저 보세요.** `tick_ms` 는 시계 시간이라 다른 프로세스에 CPU 를 빼앗기면 그대로 늘어납니다(load 가 코어 수보다 훨씬 크면 p99 가 일의 크기가 아니라 대기 시간이 됩니다). 단, 목표 VPS 에서는 세 방의 틱이 같은 순간에 몰려 한 코어를 나눠 쓰므로 합격 판정은 `tick_ms`(시계 시간) 기준입니다.
- 죽거나 멈춘 방은 `tick_ms` 등이 `null`, `error` 에 사유가 들어갑니다. 그 방만 끝나고 나머지는 계속됩니다.
- `pass`: 방 8개 이상이거나 `--fast` 이면 `"기록만"`. 그 밖에는 방 틱 p99 ≤ 25ms **그리고** 루프 지연 p99 ≤ 10ms **그리고** 모든 방이 정상 종료여야 `true`. 900초 미만 측정이거나 방이 3개가 아니면 `note` 에 합격 근거가 아니라고 덧붙입니다.
- 퍼센타일은 표본(틱마다 1개)을 **전부 모아 정렬한 뒤 nearest-rank**(`sorted[ceil(p·n/100)−1]`)로 구한 **정확한 값**입니다. (히스토그램 근사 아님. 단, 부모의 이벤트 루프 지연만은 Node 의 히스토그램이라 근사입니다.)

### 그 밖의 JSON

- `build_sim.js` → `.build/manifest.json`: `survivors_sha256`, `script_blocks`(스크립트 블록 크기), `sim_sha256`, `sim_mp_sha256`, `verify.classify`(`S` 필드 분류 결과), `built_at`. 생성된 `sim.js`/`sim_mp.js` 첫 줄에도 입력 sha256 이 주석으로 들어갑니다. 다른 도구는 sha256 이 현재 `survivors.html` 과 다르면 **자동으로 다시 빌드**합니다(낡은 사본으로 조용히 시험하지 않음).
- `mp_run.js --json/--out`: `combo, secs, hz, seed, ok, ticks, error{at_game_s,message,stack}, ended_early, stuck, nonfinite, ms_per_tick, cpu_ms_per_tick, game_s, max_enemies, deaths_absorbed, actors[{k,lv,dmg,weapons}], dmg_by, hashes[30초마다], hash_final`.
- `cover.js --json`: `weapons_now, known_39, added, removed, first_pass_missing, second_pass_recovered, used, missing, ok`.
- `g4_test.py --out`: `combos, extra_combos, base_seed, runs[], cover[], determinism, lint, loadavg_start/end, exit`.

## `survivors.html` 이 바뀌어 앵커가 어긋났을 때

`build_sim.js` 는 패치가 기대하는 모든 문자열(`update()` 를 자르는 13곳 · 문장 치환 6곳 · `fire()`/`die()`/`endRun()` · 훅 자리)이 **존재하고 유일한지**,
구간 순서가 그대로인지, 패치가 **버리는 연결부**(`update()` 머리 · `waveTick`~`weapons` 사이 · `beamTick` 줄)에 새 문장이 끼지 않았는지 검사합니다.
하나라도 어긋나면 어느 앵커가 왜(없음 / N번 나옴 / 순서 바뀜 / 연결부에 새 코드) 안 맞는지 적고 **종료코드 2** 로 멈춥니다. 조용히 틀린 사본은 만들지 않습니다.

대처:
1. 메시지의 `[이름]` 과 문자열을 `build_sim.js` 의 `SEG_ANCHORS` / `REP_ANCHORS` / `makeSimMp` 에서 찾는다.
2. `survivors.html` 의 `function update(dt){` 근처에서 그 줄이 어떻게 바뀌었는지 `git log -p survivors.html` 로 본다.
3. 앵커 문자열을 새 모양으로 고치고, 치환 결과(`makeSimMp` 안 문자열)에 같은 의미의 변화를 반영한다. **새 문장이 연결부에 끼었다면** 그 문장이 액터마다 돌아야 하는지(루프 안으로) 월드에서 한 번만 돌아야 하는지 정해서 넣는다.
4. `S` 에 새 필드가 생겼다면 `verify` 가 `미분류` 로 알려 줍니다 — 액터별이면 `PKS`, 판 공용이면 `WORLD` 에 넣는다.
5. `node tests/raid/sim_selftest.js` 가 통과하는지(앵커를 일부러 망가뜨려도 잡는지), `g4_test.py --quick --lint --determinism` 이 통과하는지 확인한다.

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
- 1 vCPU 가 아닌 기계라면 `taskset -c 0` 으로 한 코어에 고정하고 `host.cpus_allowed` 를 확인하세요(JSON 에 같이 적힙니다).
- 15분 실측은 `--realtime` 으로 실제로 15분이 걸립니다. 중간에 멈추려면 Ctrl-C **한 번**(지금까지의 결과를 저장하고 끝냄), 두 번이면 즉시 종료.
- 시험 전용 고장 주입: `--fault hang:1:5`(1번 방이 5초 뒤 멈춤 → 2초 무응답으로 그 방만 terminate), `crash`·`oom`·`throw` 도 있습니다.

## 스크래치 원본에서 달라진 점

- 스크래치 `run.js`(DOM 스텁) → `run_stub.js`: localStorage 를 진짜 저장소처럼(`length`/`key`/`clear`), 이벤트 등록 기록, `fetch` 거절·타이머 비실행(횟수 기록), 컨텍스트 자체 내장 객체 사용, 시드 옵션, `--trace`.
- `patch.py` → `build_sim.js`(Node): 앵커 존재·유일성·순서·버려지는 연결부 검사 추가. 파이썬 불필요. 갱신된 훅은 `tests/sv_harness.py` 의 `HOOK` 에 의존하지 않고 이 파일 안에 정의합니다. 산출한 `update()` 본문은 스크래치 `sim_mp.js` 의 것과 **바이트 단위로 같습니다**(2026-10-09 비교).
- `mp.js`/`mpcpu.js` → `mp_run.js`: 조합·초·시드·이동 방식 지정, 예외 시 게임 시각·스택, 상태 멈춤·NaN 감시, 해시.
- `cover.js`: 하드코딩 39개 → `WEAP` 에서 동적으로 구함(현재 **40종**: `sing`(노래부르기) 추가). 1차/2차 확인과 `--evo`.
- `runall.sh` → `g4_test.py`: 기본 5조합 + 현재 캐릭터(18명) 중 빠진 것을 채우는 보강 조합 1개(`bbb,eom,yj,tw`).
