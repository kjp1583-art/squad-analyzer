# 레이드 0단계 — 임시 에코/생존 시험 서버 + 서울 서버 설치 스크립트

> **임시 측정 도구입니다(제품 아님).** 폰(안드로이드 디스코드 내부창)이 WebSocket 연결을 얼마나 잘 붙잡는지,
> 끊겼다 다시 붙을 때 서버가 어떻게 보는지를 재기 위한 서버입니다. 시험이 끝나면 **서버를 삭제**합니다.
>
> ⚠️ **Vultr 는 서버를 꺼 두기만 해도 과금됩니다. 반드시 "삭제(Destroy)" 해야 멈춥니다.** (설계서 §8, Vultr 결제 문서 기준)
> 삭제 화면의 정확한 메뉴 이름은 확인 못 했습니다 — 서버 목록에서 그 서버가 사라졌는지로 확인하세요.

파일

| 파일 | 하는 일 |
|---|---|
| `server.js` | 에코/생존 시험 서버 (Node 22 + `ws` 하나) |
| `bootstrap.sh` | 2KB 짜리 짧은 시작 스크립트 — GitHub 에서 `provision.sh` 를 받아 실행. **사장님이 Vultr 칸에 붙여 넣는 것은 이것** |
| `provision.sh` | 서울 서버 한 대를 스스로 설정하는 설치 스크립트 (bootstrap 이 받아 실행. 직접 붙여 넣어도 됨) |
| `bench_when_idle.sh` | 에코 서버가 한가할 때만 부하 시험을 돌리는 도우미 (설치 스크립트가 서비스로 등록) |
| `package.json` · `package-lock.json` | `ws@8.18.3` 고정 |
| `../../tests/raid/echo_server.test.js` | 서버 시험 (`node --test`) |
| `../../tests/raid/provision_check.sh` | 설치 스크립트를 가짜 명령으로 돌려 보는 시험 |

---

## 1. 로컬에서 돌려 보기

```bash
cd raid/echo
npm ci --omit=dev          # ws@8.18.3 설치
PORT=8080 DATA_DIR=/tmp/raid-data node server.js
curl localhost:8080/health
```

시험:

```bash
cd raid/echo && npm ci --omit=dev && cd ../..
node --test tests/raid/echo_server.test.js     # 서버 시험 (약 1분)
bash tests/raid/provision_check.sh             # 설치 스크립트 스텁 시험 (약 1분)
# 선택: CADDY_REAL=/경로/caddy 를 주면 만들어진 Caddyfile 을 진짜 caddy validate 로 검사,
#       SIM_DIR=/경로 (tests/raid/bench_rooms.js 가 있는 형제 갈래) 를 주면 진짜 부하 시험 도구를 읽기 전용 소스 폴더에서 돌려 본다
```

## 2. 환경변수

| 이름 | 기본값 | 뜻 |
|---|---|---|
| `PORT` | 8080 | 포트. `0` 이면 빈 포트를 골라 시작 로그(JSON 한 줄)에 적음 |
| `HOST` | 127.0.0.1 | 묶을 주소. Caddy 뒤에서는 그대로 두세요 |
| `ALLOW_ORIGINS` | `https://kjp1583-art.github.io,http://localhost,http://127.0.0.1` | 쉼표 목록. WebSocket 의 `Origin` 검사. **Origin 이 없는 접속(시험 도구)은 통과.** 포트 없이 적은 `localhost`/`127.0.0.1` 은 어떤 포트든 허용 |
| `TRUST_PROXY` | (꺼짐) | `1` 이면 `X-Forwarded-For` 의 **맨 오른쪽** 값을 클라이언트 IP 로 씀(Caddy 가 붙이는 값). 끄면 소켓 주소. 값이 IP 모양이 아니면 소켓 주소 |
| `MAX_CONN` | 200 | 동시 WebSocket 상한. 넘으면 503 + `Retry-After` |
| `PER_IP` | 30 | IP 당 상한(이동통신 공유 IP 고려). IPv6 는 앞 64비트가 같으면 한 사람으로 셈 |
| `MAX_MSG_BYTES` | 4096 | 메시지 크기 상한. 넘으면 1009 로 닫음 |
| `MAX_MSG_PER_S` | 30 | 초당 받는 프레임 상한(앱 메시지·ping·**pong 모두**). 넘으면 1008 로 닫고, 닫은 뒤에도 쏟아지면 소켓을 바로 끊음 |
| `MAX_BYTES_PER_S` | 524288 | 연결 하나가 초당 받는 바이트 상한(정상 클라는 수 KB). 넘으면 1008 |
| `HTTP_PER_S` | 60 | IP 당 초당 HTTP 요청 상한. 넘으면 429 + `Retry-After: 1` (핑 페이지의 20번 연속 측정은 안 걸림) |
| `MAX_LIFE_S` | 3600 | 연결 총 수명. 넘으면 1001 `max-life` |
| `APP_IDLE_S` | 900 | 앱 메시지(hb/bg/echo)가 이만큼 없으면 1001 `app-idle` (생존 시험이라 길게) |
| `PING_S` | 5 | 프로토콜 ping 주기 |
| `PONG_TO_S` | 10 | pong 도 앱 메시지도 이만큼 없으면 1001 `no-response` |
| `DATA_DIR` | `/var/lib/raid-echo` | 부하 시험 결과(`bench_*.json`)·설치 상태(`setup.json`)가 있는 곳 |
| 그 밖(시험·조정용) | | `TICK_MS`(1000) · `GAP_EVENT_MS`(2500, 이 이상 벌어진 앱 메시지 간격을 기록) · `HEADERS_TIMEOUT_MS`(10000, 앱에 직접 붙는 연결의 slowloris 방어 — Caddy 뒤에서는 Caddyfile 의 `read_header 10s` 가 같은 일을 함) · `SESSION_MAX`(1000) · `EVENT_MAX`(300) · `SESSION_TTL_S`(21600) · `SWEEP_S`(60) |

범위를 벗어난 값은 기본값으로 돌아가고 시작할 때 경고 한 줄을 남깁니다.

## 3. 엔드포인트

모든 HTTP 응답: JSON, `Cache-Control: no-store`, `Access-Control-Allow-Origin: *`, `Timing-Allow-Origin: *`.

| 주소 | 응답 |
|---|---|
| `GET /health` | `{ok, v:1, now, up_s, conns, peak, errors, rej:{origin,sid,limit}, drop:{http_rate,flood}, act, act_ago_ms, bench, setup}` — `errors` 는 처리 안 된 예외 횟수(삼키지 않고 센다), `rej` 는 거절 횟수, `drop` 은 속도 한도로 쳐낸 횟수, `act`·`act_ago_ms` 는 **폰 시험 활동**(WebSocket 접속 시도·`/ping`·`/log`)의 누적 횟수와 마지막으로부터 지난 ms(`/health`·`/bench` 는 안 셈 — 부하 시험이 이걸 보고 물러남), `bench` 는 부하 시험 결과 파일이 있는지, `setup` 은 설치 상태(`setup.json`) + 부하 시험 진행(`bench_state.json` → `setup.bench`) |
| `GET /ping` | `{t:<서버 ms>}` (아주 작게) |
| `GET /log?sid=<sid>` | `{sid, found, now, summary, events}` — 그 sid 에 대해 **서버가 본** 기록. 64KB 가 넘으면 오래된 이벤트부터 잘라 `truncated:true` |
| `GET /bench` | `DATA_DIR/bench_*.json` 중 가장 최근 것(512KB 상한, 깨진 파일은 건너뜀, 파일 내용은 (이름·mtime·크기) 기준으로 한 번만 읽어 캐시). 없으면 `{found:false}`. `?list=1` 은 파일 목록, `?name=3rooms` 는 `bench_3rooms.json` 선택 — 이름은 폴더 목록과 대조만 하므로 경로 조작이 안 먹힘. **합격 기준인 3방 결과는 `?name=3rooms`** (8방 결과가 생기면 맨 `/bench` 는 더 최근인 8방, 곧 기록용을 줌) |
| `GET /` | 짧은 한글 안내 |
| `WS /ws?sid=<sid>` (별칭 `/wstest`) | 아래 규약 |

## 4. 통신 규약 요약

`sid` 는 클라가 만든 6~40자 `[A-Za-z0-9_-]`(틀리면 400), 없으면 서버가 만들어 hello 로 알려 줍니다.

서버 → 클라:

```
{t:"hello", v:1, sid, srv_ms, conn, prev:null|{close_ms,code,why,gap_ms,quiet_ms,by}, tick_ms, ping_s, pong_to_s, idle_s, life_s}
{t:"tick", n, srv_ms}                       매 tick_ms(1초)마다. n 은 이 연결에서 1부터
{t:"ack", k:"hb"|"bg"|"echo", n, c, srv_ms} 클라 메시지에 대한 답. c·n 은 클라가 보낸 숫자를 그대로(숫자가 아니면 null)
```

`prev` — 같은 sid 의 직전 연결이 어떻게 끝났는지. `gap_ms` = 닫힌 뒤 지난 시간, `quiet_ms` = 서버가 마지막으로 그 연결의 소식(앱 메시지·pong)을 들은 뒤 지난 시간, `by` = `peer`/`server`.
(교체로 닫혔다면 `code:4001`, `gap_ms` 는 0 근처이고 **`quiet_ms` 가 "폰이 사라져 있던 동안 서버는 옛 소켓이 살아 있다고 믿은 시간"** 입니다.)

클라 → 서버(JSON 글자): `{t:"hb",n,c}` 보이는 동안 1초마다 · `{t:"bg",n,c}` 화면이 숨겨질 때 한 번 · 그 밖의 것(잘못된 JSON 포함)은 echo.

서버 동작과 닫는 코드:

| 상황 | 코드·이유 |
|---|---|
| 프로토콜 ping 을 `PING_S` 마다 보냄. pong·앱 메시지 둘 다 `PONG_TO_S` 동안 없음 | 1001 `no-response` |
| 앱 메시지가 `APP_IDLE_S` 동안 없음 | 1001 `app-idle` |
| 연결이 `MAX_LIFE_S` 를 넘김 | 1001 `max-life` |
| 같은 sid 로 새 연결이 옴 | 옛 연결 4001 `replaced` (+ `replaced` 기록) |
| 바이너리 프레임 | 1003 |
| `MAX_MSG_BYTES` 초과 | 1009 |
| 초당 `MAX_MSG_PER_S` 초과(pong·ping 포함) 또는 초당 `MAX_BYTES_PER_S` 초과 | 1008 `rate-limit` (폭주하면 닫기 인사 없이 소켓 종료) |
| 받는 쪽이 너무 느려 쌓임(256KB) | 4005 `slow-reader` |
| 서버 종료(SIGTERM) | 1001 `server-shutdown` |

`/log` 의 `summary`:

```
{conns, opened, closed, last_msg_ms, last_pong_ms, max_msg_gap_ms, max_pong_gap_ms,
 bg_hints:[ms...], closes:[{ms,code,why,by,conn}], replaced:[{ms,old_msg_age_ms,old_pong_age_ms}]}
```

* `conns` = 지금 열려 있는 연결 수, `opened`/`closed` = 지금까지 열린/닫힌 총 횟수.
* `*_ms` 의 `ms` 는 서버의 `Date.now()`(에폭 ms). `max_*_gap_ms` 는 **한 연결 안에서** 연달아 받은 메시지(pong) 사이의 가장 긴 간격.
* `by:"peer"` 는 상대가 닫았거나 네트워크가 끊긴 경우(1006 포함), `"server"` 는 서버가 닫은 경우.
* `old_msg_age_ms` / `old_pong_age_ms` — 교체되는 순간 옛 연결이 마지막으로 앱 메시지/pong 을 받은 지 몇 ms 였는지(한 번도 못 받았으면 연결을 연 때부터). **서버가 "아직 살아 있다"고 믿은 시간**입니다.
* `events` — `{ts, ev, ...}`: `open`(UA·Origin·`ip_changed`) · `first_hb` · `bg` · `msg_gap`(앱 메시지가 `GAP_EVENT_MS` 이상 벌어짐) · `pong_gap` · `echo` · `replaced` · `error` · `close`. 1초마다 오는 hb 는 하나하나 기록하지 않습니다(링 버퍼 300개가 5분 만에 차므로).

기록의 한계: 세션 기록은 **서버 메모리**입니다(sid 당 이벤트 300개 링 버퍼, 세션 1000개 상한, 6시간 뒤 정리). 상한을 넘으면 **앱 메시지를 한 번도 못 받은 세션(접속만 하고 간 것)부터** 버리므로, 폰 시험 기록이 남이 만든 sid 에 쉽게 밀려나지는 않습니다. 그래도 서버를 다시 시작하면 전부 사라지니 **시험이 끝나면 `/log` 결과(화면의 복사 버튼)를 바로 채팅에 붙여 두세요.** 클라가 보낸 값은 길이를 자르고 제어문자를 지웁니다. 콘솔 로그에는 IP·sid 앞 4자만 남깁니다.

---

## 5. 서울 서버 만들기 (사장님)

> Vultr 화면 이름은 **docs.vultr.com 공식 문서(`Enable Cloud-Init User-Data` 등)와 Vultr API(서울=`icn`, 이미지 `Ubuntu 24.04 LTS x64`, 서울의 가장 싼 `vc2-1c-1gb` 월 $5)** 로 검증 단계에서 확인된 것만 썼습니다(이 개발 환경에서 Vultr 화면을 직접 열어 보지는 못했습니다). 화면이 여기 적힌 것과 다르면 스크린샷을 채팅에 올려 주세요.
> 비용: **시간당 과금**(월 $5 ≒ 시간당 $0.007)이라 몇 시간 쓰고 삭제하면 몇 센트입니다.
> 처음이면 Vultr 가입과 결제 수단(카드 등) 등록이 먼저 필요합니다(화면은 확인 못 함).
> ⚠️ 배포 화면에서 **`Auto Backups`(자동 백업) 같은 추가 기능은 켜지 마세요** — 켜면 서버 요금 말고 따로 붙습니다. 기본값 그대로 두면 됩니다.

### 5-1. 붙여 넣을 글 복사하기

1. 브라우저로 <https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/main/raid/echo/bootstrap.sh> 를 엽니다(글자만 있는 페이지가 나옵니다). **`main` 에 이 파일이 아직 없으면(합치기 전이면) 주소의 `main` 을 가지 이름으로 바꿉니다** — 이 경우 아래 5-2 에서 붙여 넣은 글 맨 위 `REF="${REF:-main}"` 의 `main` 도 같은 이름으로 고칩니다.
2. 화면 전체를 선택(`Ctrl+A`)하고 복사(`Ctrl+C`). **메모장 같은 데에 한 번 붙였다가 다시 복사하지 마세요**(윈도우 메모장은 줄바꿈 글자를 바꿔서 첫 줄이 깨질 수 있습니다). 바로 5-2 의 칸에 붙입니다.

### 5-2. 서버 만들기

1. Vultr 로그인 → `Products` → `Compute` → `Deploy` (또는 `Deploy Server`).
2. **Shared CPU**(또는 `Cloud Compute`) → 위치 **Seoul** → 가장 싼 플랜(**$5/월, 1 vCPU / 1GB**) → 이미지 **Ubuntu 24.04 LTS x64**.
3. 아래쪽 **`Additional Features`** 에서 **`Enable Cloud-Init User-Data`** 를 켜면 글 칸이 나옵니다. 거기에 5-1 에서 복사한 글을 **붙여 넣습니다**. (리눅스 서버는 이 칸이 Vultr 공식 권장 방법입니다. 「Startup Script」의 `Boot` 종류는 Vultr 문서가 Windows/BSD 용으로 적고 있어서 우분투에서 도는지 확인하지 못했습니다 — 아래 「안 될 때」 참고.)
4. 서버 이름(`Server Label`)은 아무거나(예: `raid-test`). **`Deploy Now`**.
5. 서버가 켜지고 **약 5~10분** 기다립니다(프로그램 설치 + 인증서 발급).
6. 서버 목록에서 그 서버의 **IP 주소**를 확인합니다. IP 가 `203.0.113.7` 이면 브라우저(또는 폰)에서 `https://203-0-113-7.sslip.io/health` 를 엽니다(점 `.` 을 하이픈 `-` 으로). `{"ok":true,...}` 가 보이면 성공입니다.
7. 시험 페이지 주소(서버 주소를 `?ws=` 뒤에 붙여 쓰는 방식)는 서버 안의 `/root/RAID_SETUP_STATUS.txt` 에도 적혀 있고, 채팅에서 안내해 드립니다.
8. **시험이 끝나면 서버를 삭제합니다**(서버 목록에서 그 서버를 열어 삭제/Destroy). 꺼 두기만 하면 계속 과금됩니다. 삭제 메뉴의 정확한 이름은 확인 못 함 — 목록에서 서버가 사라졌는지로 확인하세요.

### 5-3. 안 될 때 (가장 쉬운 방법부터)

1. **서버를 삭제하고 5-2 를 처음부터 다시 하세요(몇 센트).** cloud-init 은 첫 부팅에 한 번만 도므로, 서버 안을 고치는 것보다 이게 훨씬 쉽습니다.
2. 10~15분이 지나도 `/health` 가 안 열리면, 스크립트가 돌았는지부터 봐야 합니다. Vultr 서버 화면의 **웹 콘솔**(서버 상세의 콘솔/`View Console` 메뉴로 알지만 **메뉴 이름은 확인 못 함**)로 들어가 `root` 로 로그인합니다(비밀번호는 서버 상세 화면에 표시된다고 알지만 **확인 못 함**). 그리고:
   ```
   cat /root/RAID_SETUP_STATUS.txt     # 상태: OK / FAIL / RUNNING, 실패한 단계, 마지막 로그 줄
   ls /var/log/raid-provision.log      # 이 파일이 없으면 스크립트가 아예 안 돈 것
   ```
   `FAIL` 이면 그 내용 전체를 채팅에 붙여 주세요. **로그 파일도 없으면 스크립트가 안 돈 것**이니 서버를 삭제하고 다른 칸으로 다시 만듭니다: `Orchestration` → `Scripts` → `Add Startup Script` → 이름(예: `raid-echo`) → 종류 `Boot` → 내용에 같은 글 붙여 넣기 → 저장, 그리고 서버를 만들 때 `Server Settings` 의 `Startup Script` 에서 그걸 고릅니다. (이 칸이 우분투에서 도는지도 확인하지 못했습니다.)
3. 붙여 넣는 칸이 길이 제한으로 거부하면 짧은 `bootstrap.sh`(2KB)를 쓰고 있는지 확인하세요. 그래도 거부하면 스크린샷을 올려 주세요.

### 설치 스크립트가 하는 일 (순서)

1. 필수 패키지 설치(`apt`). **첫 부팅의 자동 업데이트가 apt 잠금을 쥐고 있으면 직접 기다립니다**(잠금 파일 4개를 누가 열고 있는 동안, 최대 600초). `DPkg::Lock::Timeout` 은 dpkg 잠금에만 듣고 `apt-get update` 의 목록 잠금·`install` 의 보관함 잠금에는 안 듣기 때문입니다(우분투 24.04 의 apt 2.8.3 으로 실측).
2. 서버 주소 정하기 — `HOST` 가 비어 있으면 Vultr 메타데이터 `http://169.254.169.254/v1/interfaces/0/ipv4/address` 로 공인 IP 를 알아내(안 되면 `api.ipify.org` 등) `<a-b-c-d>.sslip.io` 로 만듭니다. 도메인을 샀다면 스크립트 위쪽 `HOST=` 에 적고(DNS A 레코드가 이 서버를 가리켜야 함) 붙여 넣으세요.
3. **Node 22**를 nodejs.org 에서 `tar.xz` 로 받아 `SHASUMS256.txt` 로 **sha256 검증 후** `/opt/node-v22.x.y` 에 풀고 `/opt/node` 링크를 겁니다. 해시가 안 맞으면 즉시 중단합니다.
4. **Caddy** — 공식 apt 저장소 방식(<https://caddyserver.com/docs/install#debian-ubuntu-raspbian>, 2026-10-08 확인). Cloudsmith 의 키·목록을 받아 `apt install caddy`.
5. 소스 받기 — `git fetch --depth 1 origin <REF>` 로 `/opt/raid/src` 에(가지·태그·커밋 모두 같은 방법). 이어서 `raid/echo` 에서 `npm ci --omit=dev --ignore-scripts`.
6. 사용자 `raid` 생성, systemd 서비스 `raid-echo`(`127.0.0.1:8080`, `TRUST_PROXY=1`) 등록·시작. 하드닝: `NoNewPrivileges` · `ProtectSystem=strict` + `ReadWritePaths=/var/lib/raid-echo` · `ProtectHome` · `PrivateTmp` · `PrivateDevices` · 커널/cgroup 보호 · `RestrictAddressFamilies` · `CapabilityBoundingSet=` 비움 · `MemoryMax=400M` · `Restart=always`. (`MemoryDenyWriteExecute` 는 Node 의 JIT 와 충돌하므로 **쓰지 않음**.)
7. 방화벽 `ufw` — **허용 규칙을 먼저** 넣고 마지막에 켭니다: `22/tcp`(limit) · `80/tcp` · `443/tcp` · `443/udp`, 기본 deny incoming. **Caddy 를 띄우기 전에** 해서 첫 인증서 발급(80번 포트)이 막히지 않게 합니다.
8. Caddyfile 작성(`HOST` 에 대해 TLS 자동 발급 + `reverse_proxy 127.0.0.1:8080`, WebSocket 은 기본 지원, 전역 옵션 `read_header 10s`·`idle 2m`) 후 Caddy 재시작.
9. 스스로 `https://HOST/health` 를 확인(인증서 발급 대기). 실패한 호출은 5초 쉬고 다시, 최대 48번 — **보통 약 4분, 아주 느리면 최대 약 10분** 뒤에야 FAIL 로 기록됩니다(그동안 상태 파일은 `RUNNING`).
10. `RUN_BENCH=1`(기본)이면 부하 시험 서비스 `raid-bench` 를 예약(아래).

끝나면 `/root/RAID_SETUP_STATUS.txt`(OK/FAIL, 실패한 단계, 마지막 로그 줄, 접속 주소)와 `/var/log/raid-provision.log` 에 같은 내용이 남고, 서버가 떠 있으면 `/health` 의 `setup` 필드에도 보입니다. 서버 안에서 손으로 다시 돌려도 안전하게 만들었습니다(이미 받은 Node·키는 다시 받지 않고, 유닛 파일은 같은 값으로 덮어씀). 하지만 cloud-init 은 한 번만 돌므로 **다시 해야 할 때는 서버를 삭제하고 다시 만드는 것이 가장 쉽습니다.**

스크립트 위쪽 설정(환경변수로도 덮어쓰기 가능): `HOST` · `REF`(기본 `main`) · `REPO`(기본 `kjp1583-art/squad-analyzer`) · `RUN_BENCH`(기본 1) · `NODE_VERSION`(비우면 최신 22.x). `bootstrap.sh` 는 `REF`·`REPO`·`HOST`·`RUN_BENCH` 를 그대로 `provision.sh` 에 넘깁니다.

* **`REF` 주의**: 에코 서버와 시험 도구가 `main` 에 합쳐지기 전이라면 `REF` 를 그 가지 이름(예: 통합 브랜치)으로 바꾸세요. `main` 에 `raid/echo/server.js` 가 없으면 설치는 "소스 받기" 단계에서 멈춥니다. `tests/raid/bench_rooms.js` 가 없으면 부하 시험만 건너뛰고 설치는 성공합니다(상태 파일에 사유).
* **신뢰 범위**: `bootstrap.sh` 는 GitHub 의 `REPO`/`REF` 에서 받은 스크립트를 **root 로 실행**합니다. 기본값(이 프로젝트의 공개 저장소)이 아닌 곳을 가리키지 마세요.
* **Node 버전 선택 이유**: 고정 버전은 보안 패치를 놓치고, `latest-v22.x/SHASUMS256.txt` 에서 파일 이름으로 읽으면 항상 22 계열의 최신 패치를 받습니다. 대신 새 패치가 문제를 일으키면 `NODE_VERSION=22.x.y` 로 고정하면 됩니다. 다운로드 무결성은 같은 디렉터리의 `SHASUMS256.txt`(HTTPS)로 검증합니다. GPG 서명(`SHASUMS256.txt.sig`)까지는 검증하지 않습니다 — HTTPS 로 nodejs.org 를 믿는 수준입니다.

### 부하 시험 (raid-bench)

* `bench_when_idle.sh` 가 **접속자(`conns`)가 2분 연속 0 이고, 마지막 폰 활동(`act_ago_ms`: WebSocket 접속 시도·`/ping`·`/log`)도 2분보다 오래됐을 때** 시작합니다:
  `node tests/raid/bench_rooms.js --rooms 3 --secs 900 --realtime --build-dir <DATA_DIR>/build --out <DATA_DIR>/bench_3rooms.json` → 이어서 `--rooms 8 --secs 300 ... bench_8rooms.json`.
  (`--build-dir` 가 필수입니다: 서비스는 `raid` 사용자 + `ProtectSystem=strict` 라 소스 폴더에 쓸 수 없는데 시험 도구는 기본으로 소스 폴더 안에 `.build` 를 만들려 하기 때문 — 2026-10-08 검증에서 이 때문에 G2' 측정이 한 번도 못 도는 결함이 나와 고쳤습니다.)
* **폰 시험이 우선**입니다. 시험 도중 **1초마다** 확인해서 접속자가 생기거나 폰 활동 횟수(`act`)가 올라가면(5초보다 짧은 접속이나 HTTP 요청 한두 번도 잡힙니다) 시험을 멈추고(미완성 결과 삭제) 다시 조용해질 때까지 기다립니다. 서비스는 `Nice=19` · `CPUWeight=1` 이라 CPU 를 다툴 때는 에코 서버가 거의 다 가져갑니다.
* **그래도 완벽하지는 않습니다.** 시험이 돌고 있는 도중 폰이 처음 접속하면, 감지해서 멈출 때까지 최대 1~2초는 겹칠 수 있습니다. 1 vCPU 서버에서 그 사이 RTT 가 얼마나 늘어나는지는 **재 보지 못했습니다**(이 개발 환경은 4코어 공용). 그래서: **G1(RTT)·G5(소켓 생존) 측정 전에 `https://HOST/health` 의 `setup.bench.state` 를 보고, `running` 이면 그 시험이 끝나거나 `waiting` 으로 바뀔 때까지 몇 분 기다린 뒤** 재세요. 설치가 끝나고 2분 뒤 자동으로 시작하는 구조이므로 처음 여는 시간대와 겹칠 수 있습니다.
* 진행: `https://HOST/health` 의 `setup.bench.state`(`waiting`/`running`/`done`/`failed`/`skipped`) · 결과: 목록 `https://HOST/bench?list=1` · **합격 기준인 3방 결과 `https://HOST/bench?name=3rooms`**(8방은 기록용).
* 서버를 재부팅하면 자동으로 다시 시작되지 않습니다(필요하면 `systemctl start raid-bench`).
* 1GB 서버에서 8방 시험이 메모리(`MemoryMax=550M`)에 걸려 죽으면 `OOMPolicy=continue` 와 `ExecStopPost`(`bench_when_idle.sh --post`)가 `bench_state.json` 을 `failed` 로 고쳐 둡니다(그렇게 되도록 만들었으나 실서버에서 OOM 을 일으켜 보지는 못함). 이 숫자도 측정 결과의 일부입니다.

---

## 6. 확인하기

```bash
curl https://HOST/health            # {"ok":true,"v":1,...}
curl https://HOST/ping
curl "https://HOST/log?sid=내sid"   # 시험 페이지 맨 아래에 보이는 sid
curl https://HOST/bench?list=1      # 부하 시험 결과 목록
curl https://HOST/bench?name=3rooms # 합격 기준인 3방 결과
```

브라우저 주소창에 `https://HOST/health` 를 넣어 열어도 됩니다. 서버 안에서 보려면(Vultr 웹 콘솔 등):

```
cat /root/RAID_SETUP_STATUS.txt     # 설치 결과
journalctl -u raid-echo -n 50       # 에코 서버 로그
journalctl -u raid-bench -n 50      # 부하 시험 로그
```

## 7. 문제 해결

| 증상 | 확인 |
|---|---|
| **뭔가 이상하다** | **서버를 삭제하고 5-2 를 처음부터 다시 하세요(몇 센트).** 서버 안을 고치는 것보다 쉽습니다 |
| `https://HOST/health` 가 안 열림 (10분 지나도) | 위 5-3 의 2번(`/root/RAID_SETUP_STATUS.txt`·`/var/log/raid-provision.log` 확인). 서버 안에서는 `ufw status` 에 80·443 허용인지, Vultr 쪽 방화벽 그룹을 따로 만들었다면 거기도 80/tcp·443/tcp·443/udp 허용인지, `journalctl -u caddy -n 50` 의 인증서 발급 오류 |
| 인증서 발급 실패 | `sslip.io` 는 여러 사람이 함께 쓰는 공용 도메인이라 Let's Encrypt 의 발급 횟수 제한에 걸릴 수 있습니다(실제로 그런지는 **확인 못 함**). Caddy 는 Let's Encrypt 가 안 되면 자동으로 **ZeroSSL** 로 넘어가 다시 시도합니다 — 몇 분 더 기다려 보세요. 계속 안 되면 도메인을 사서 `HOST` 로 지정하면 됩니다 |
| `{"ok":true}` 는 나오는데 폰에서만 안 붙음 | 시험 페이지는 `https://kjp1583-art.github.io` 에서 열어야 합니다(`Origin` 검사). 다른 주소에서 열면 403 |
| 503 | `MAX_CONN`/`PER_IP` 초과 — `/health` 의 `rej.limit`. 한 통신사 공유 IP 로 30개 넘게 붙는 일은 시험에선 없습니다 |
| 429 | 한 IP 가 1초에 `HTTP_PER_S`(60)개 넘게 요청 — `/health` 의 `drop.http_rate`. 시험 페이지의 정상 측정에선 나오지 않습니다 |
| 연결이 `1008 rate-limit` 으로 끊김 | 프레임·바이트 속도 한도 — `/health` 의 `drop.flood`. 정상 시험 페이지에선 나오지 않습니다 |
| 400 | sid 형식 오류 (`rej.sid`) |
| `errors` 가 0 이 아님 | 서버가 처리 못 한 예외를 삼키고 센 횟수입니다. `journalctl -u raid-echo` 로 원인을 보고 채팅에 붙여 주세요. 1분에 200건이 넘으면 스스로 종료하고 systemd 가 다시 띄웁니다 |
| `setup.bench.state` 가 `failed`/`skipped` | `failed` 면 `msg` 에 끝나지 못한 시험이 적힙니다(메모리 한도 초과일 수 있음). `skipped` 는 `bench_rooms.js` 가 받은 소스에 없다는 뜻(`REF` 확인) |
| 설치 스크립트가 멈춤/실패 | `/root/RAID_SETUP_STATUS.txt` 의 "실패한 단계" 와 "마지막 로그 줄"을 채팅에 붙여 주세요 |

## 8. 보안 메모

* 인증 없는 공개 시험 서버입니다. 저장하는 개인정보는 없고(IP 는 메모리의 한도 계산에만 쓰고 `/log` 에 안 넣음, 콘솔엔 앞 4자), sid 를 아는 사람만 그 sid 의 기록을 볼 수 있습니다(임의의 6~40자).
* 비밀·토큰은 코드에 없습니다(공개 저장소). 이 서버는 외부 서비스에 키를 쓰지 않습니다.
* 방어: Origin 검사 · sid 형식 · 전체/IP 한도 · 프레임 속도 한도(앱 메시지·ping·pong 모두)와 바이트 속도 한도 · 메시지 크기 · 바이너리 거절 · IP 당 HTTP 속도 한도(429) · 한 연결당 HTTP 요청 100개 · `/bench` 응답 캐시(요청이 몰려도 메모리가 안 늘어남) · 처리 안 된 예외 카운터 · 느린 수신자 차단 · SIGTERM 깨끗한 종료.
* 헤더를 천천히 보내는 연결(slowloris): 외부에 노출되는 쪽은 Caddy 이므로 **Caddyfile 의 `read_header 10s`·`idle 2m`** 이 막습니다. 앱의 `HEADERS_TIMEOUT_MS` 는 앱에 직접 붙을 때(로컬 시험 등)만 의미가 있습니다. (Caddy 에서 `read_header` 를 넣은 효과를 진짜 서버에서 다시 재 보지는 못했습니다. Caddyfile 문법만 진짜 `caddy validate` 로 확인.)
* 이 서버를 목표로 한 공격에 버티도록 만든 것은 아닙니다(임시 도구). 알려진 한계: 세션 기록은 메모리라 서버 재시작 시 사라지고, 앱 메시지를 받은 세션이 1000개를 넘으면 오래된 것부터 버려집니다.

## 9. 이 도구에 대해 확인한 것 / 못 한 것

* **개발 환경(우분투 서버 없음)에서 확인**: 서버 시험 `node --test tests/raid/echo_server.test.js`(규약·방어·한도·종료·pong 폭주·`/bench` 메모리·세션 보존·활동 표시), 설치 스크립트는 `bash -n` · `shellcheck` · 가짜 명령으로 돌린 스텁 실행 시험(`tests/raid/provision_check.sh`: 생성된 유닛·Caddyfile·ufw 순서·sha 검증 실패 시 중단·재실행·apt 잠금 대기·bootstrap) · `systemd-analyze verify` · 진짜 `caddy validate`(`CADDY_REAL=/경로/caddy`) · **진짜 `bench_rooms.js` 를 읽기 전용으로 마운트한 소스 폴더에서 `bench_when_idle.sh` 로 돌리는 시험**(같은 저장소에 `tests/raid/bench_rooms.js` 가 있거나 `SIM_DIR=형제 갈래 폴더` 를 줄 때, `unshare -m` 가 되는 환경에서).
* **실제 서버에서만 확인되는 것(확인 못 함)**: Vultr 에서 cloud-init user-data 로 이 형식이 root 로 실행되는지(리눅스 권장 방법이라는 것은 문서로 확인) · 「Startup Script」`Boot` 종류가 우분투에서 도는지 · 우분투 24.04 에서 apt/Cloudsmith 저장소 설치 · 첫 부팅에서 apt 잠금 경합이 실제로 얼마나 오래 가는지 · 잠금 확인에 쓰는 `fuser`(없으면 `pgrep` 으로 대체)가 그 이미지에 있는지 · Let's Encrypt/ZeroSSL 실제 발급(특히 sslip.io 한도) · Vultr 메타데이터 응답 · systemd 하드닝 옵션이 이 서버의 커널에서 실제로 적용·호환되는지(스텁 시험은 유닛을 읽지 않으므로 `226/NAMESPACE` 같은 실패를 못 봄) · ufw 실제 규칙(Vultr 이미지의 ufw 기본 상태 포함) · `Nice`/`CPUWeight` 가 1 vCPU 에서 폰 RTT 에 미치는 영향 · OOM 때 `bench_state.json` 이 `failed` 로 바뀌는지 · 1 vCPU/1GB 에서의 메모리·성능 · 폰 → 서울 실제 RTT.
