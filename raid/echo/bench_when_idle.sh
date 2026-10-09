#!/bin/bash
# 레이드 0단계 — 부하 시험을 "에코 서버에 접속자가 없을 때" 돌린다 (2026-10-08)
# 폰 시험(RTT·소켓 생존) 도중에 서버 CPU 를 먹으면 폰 숫자가 흐려지므로,
#  1) /health 의 conns 가 IDLE_S(기본 120초) 동안 계속 0 일 때 시작하고
#  2) 시험 도중 접속자가 생기면 시험을 멈추고(폰 쪽이 우선) 다시 조용해질 때까지 기다린다.
# 진행 상황은 DATA_DIR/bench_state.json (→ /health 의 setup.bench) 에 남긴다. 실패해도 설치 전체에는 영향 없음.
# 시험 목록: PLAN="방수:초:결과파일 ..." (기본 3방 900초, 8방 300초). 결과 파일이 이미 있고 JSON 이면 그 단계는 건너뛴다.
set -uo pipefail

DATA_DIR="${DATA_DIR:-/var/lib/raid-echo}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8080/health}"
NODE="${NODE:-/opt/node/bin/node}"
BENCH_JS="${BENCH_JS:-/opt/raid/src/tests/raid/bench_rooms.js}"
IDLE_S="${IDLE_S:-120}"
POLL_S="${POLL_S:-5}"
GIVE_UP_S="${GIVE_UP_S:-21600}"
PLAN="${PLAN:-3:900:bench_3rooms.json 8:300:bench_8rooms.json}"
STAGE_GRACE_S="${STAGE_GRACE_S:-600}"   # 각 단계 제한시간 = 초 + 이 값

log() { printf '[bench %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

# 값에서 따옴표·역슬래시·줄바꿈을 지워 JSON 에 안전하게 넣는다
jsafe() { printf '%s' "$1" | tr -d '\042\134' | tr '\n\r\t' '   ' | cut -c1-300; }
state() { # state <상태> <메시지>
  mkdir -p "$DATA_DIR" 2>/dev/null || true
  local tmp="$DATA_DIR/.bench_state.$$"
  if printf '{"state":"%s","msg":"%s","ts":%s}\n' "$(jsafe "$1")" "$(jsafe "$2")" "$(date +%s)000" > "$tmp"; then
    mv -f "$tmp" "$DATA_DIR/bench_state.json"
  else
    log "상태 파일을 못 씀: $DATA_DIR"
  fi
  log "$1: $2"
}

# 지금 접속자 수. 못 읽으면 -1 (= 모름 → 시작하지 않고 기다림)
conns() {
  local j n
  j="$(curl -fsS -m 5 "$HEALTH_URL" 2>/dev/null)" || { echo -1; return; }
  n="$(printf '%s' "$j" | sed -n 's/.*"conns":\([0-9][0-9]*\).*/\1/p')"
  [ -n "$n" ] && echo "$n" || echo -1
}

# 접속자가 IDLE_S 동안 계속 0 일 때까지 기다린다. GIVE_UP_S 가 지나면 1.
wait_idle() {
  local since=-1 now t0 c
  t0="$(date +%s)"
  while :; do
    now="$(date +%s)"
    if [ $((now - t0)) -ge "$GIVE_UP_S" ]; then return 1; fi
    c="$(conns)"
    if [ "$c" = "0" ]; then
      [ "$since" -lt 0 ] && since="$now"
      [ $((now - since)) -ge "$IDLE_S" ] && return 0
    else
      since=-1
    fi
    sleep "$POLL_S"
  done
}

# 한 단계 실행. 반환: 0 성공 / 1 실패 / 2 접속자 때문에 중단(다시 시도) / 3 이미 있음
run_stage() { # run_stage <방수> <초> <파일>
  local rooms="$1" secs="$2" file="$3" out pid rc c
  out="$DATA_DIR/$file"
  if [ -s "$out" ] && "$NODE" -e 'JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"))' "$out" 2>/dev/null; then
    log "$file 이미 있음 — 건너뜀"; return 3
  fi
  state running "${rooms}방 ${secs}초 시험 시작 (실시간)"
  timeout -k 10 $((secs + STAGE_GRACE_S)) "$NODE" "$BENCH_JS" --rooms "$rooms" --secs "$secs" --realtime --out "$out" &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    sleep "$POLL_S"
    c="$(conns)"
    if [ "$c" != "0" ] && [ "$c" != "-1" ]; then
      log "접속자 $c 명 발생 — 시험 중단"
      kill -TERM "$pid" 2>/dev/null; sleep 2; kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      rm -f "$out"
      return 2
    fi
  done
  wait "$pid"; rc=$?
  if [ "$rc" -ne 0 ]; then log "$file 종료코드 $rc"; return 1; fi
  if [ ! -s "$out" ]; then log "$file 결과 파일이 비어 있음"; return 1; fi
  return 0
}

main() {
  if [ ! -f "$BENCH_JS" ]; then
    state skipped "bench_rooms.js 가 저장소에 없음 ($BENCH_JS) — 시뮬 갈래가 아직 합쳐지지 않았을 수 있음"
    exit 0
  fi
  local failed="" item rooms secs file rc tries
  for item in $PLAN; do
    IFS=: read -r rooms secs file <<< "$item"
    tries=0
    while :; do
      state waiting "접속자 0명이 ${IDLE_S}초 이어지길 기다리는 중 (${file})"
      if ! wait_idle; then failed="$failed ${file}(기다리다 포기)"; break; fi
      run_stage "$rooms" "$secs" "$file"; rc=$?
      case "$rc" in
        0|3) break ;;
        2) tries=$((tries + 1)); [ "$tries" -ge 20 ] && { failed="$failed ${file}(접속자 때문에 20번 중단)"; break; }; continue ;;
        *) failed="$failed ${file}(실패)"; break ;;
      esac
    done
  done
  if [ -n "$failed" ]; then state failed "끝나지 못한 시험:$failed"; exit 1; fi
  state "done" "부하 시험 끝 — https://서버/bench 에서 결과를 볼 수 있음"
}

main "$@"
