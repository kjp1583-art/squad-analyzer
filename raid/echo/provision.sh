#!/bin/bash
# 레이드 0단계 — 서울 임시 서버 자동 설치 스크립트 (2026-10-08)
#
# 쓰는 법(권장): Vultr 에서 서버(Ubuntu 24.04 LTS x64, 서울, 가장 싼 $5)를 만들 때 배포 화면의
#          「Additional Features」→「Enable Cloud-Init User-Data」 칸에 이 파일 전체(또는 짧은 bootstrap.sh)를 붙여 넣는다.
#          서버가 처음 켜질 때 root 로 한 번 실행된다. (리눅스는 cloud-init user-data 가 Vultr 공식 권장 방법이다 —
#          「Startup Script」 칸의 Boot 종류는 Vultr 문서가 Windows/*BSD 용으로 적고 있어 우분투에서 도는지 확인 못 했다.)
#          줄바꿈은 LF 여야 한다(윈도우식 CRLF 면 첫 줄 #!/bin/bash 가 깨진다).
# 끝나면: /root/RAID_SETUP_STATUS.txt (OK/FAIL) · /var/log/raid-provision.log · https://HOST/health 의 setup 필드
# 다시 실행하는 방법: cloud-init 은 첫 부팅에 한 번만 돈다. 가장 쉬운 복구는 서버를 삭제하고 다시 만드는 것(몇 센트).
#          서버 안에서 손으로 다시 돌려도 안전하게 만들어져 있다(이미 된 것은 건너뛰거나 같은 값으로 덮어씀).
#
# 이 스크립트는 임시 측정용이다. 시험이 끝나면 서버를 삭제한다(꺼 두기만 해도 과금).

set -euo pipefail
umask 022   # 실행 환경의 umask 가 0077 이어도 /opt/raid/src 가 서비스 사용자(raid)에게 읽히게

# ───────────── 설정: 필요하면 아래 값을 고쳐서 붙여 넣는다 (환경변수로도 덮어쓸 수 있음) ─────────────
HOST="${HOST:-}"                          # 비우면 이 서버 공인 IP 로 만든 <a-b-c-d>.sslip.io. 도메인을 샀다면 여기에 적는다
REF="${REF:-main}"                        # 받을 git 가지/태그/커밋(40자)
REPO="${REPO:-kjp1583-art/squad-analyzer}" # GitHub 저장소 (공개 저장소만)
RUN_BENCH="${RUN_BENCH:-1}"               # 1 이면 에코 서버가 한가할 때 부하 시험을 자동으로 돌린다
NODE_MAJOR="${NODE_MAJOR:-22}"            # Node 주 버전
NODE_VERSION="${NODE_VERSION:-}"          # 비우면 nodejs.org 의 최신 ${NODE_MAJOR}.x. 고정하려면 예: 22.22.2
# ─────────────────────────────────────────────────────────────────────────────────────────────────

# 시험용: ROOT 를 임시 폴더로 바꾸면 모든 경로가 그 아래로 간다(실서버에서는 비워 둔다)
ROOT="${ROOT:-}"
LOG="$ROOT/var/log/raid-provision.log"
STATUS="$ROOT/root/RAID_SETUP_STATUS.txt"
OPT="$ROOT/opt"
NODE_LINK="$OPT/node"
SRC="$OPT/raid/src"
DATA_DIR_REAL="/var/lib/raid-echo"        # 서비스가 보는 경로(유닛 파일 안)
DATA_DIR="$ROOT$DATA_DIR_REAL"            # 이 스크립트가 만지는 경로
SVC_USER="raid"
APP_PORT="8080"
STARTED_AT="$(date +%s)"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS")" "$OPT"
export HOME="${HOME:-/root}"
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
# 받아 온 PATH 를 먼저 둔다(시험에서 가짜 명령이 진짜보다 앞서야 한다). 시스템 기본 경로는 뒤에 보탠다.
export PATH="$NODE_LINK/bin${PATH:+:$PATH}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# 시험 도구용: 위험한 명령이 어디를 가리키는지만 찍고 끝낸다(스텁 시험이 진짜 apt-get 을 부르지 않는지 사전 점검)
if [ "${PROVISION_PROBE:-}" = "1" ]; then
  for c in apt-get curl systemctl ufw useradd id chown gpg caddy journalctl; do command -v "$c" || echo "MISSING:$c"; done
  exit 0
fi

# 모든 출력은 로그 파일로. (Vultr 화면에는 안 보이므로 상태 파일을 따로 둔다)
exec >>"$LOG" 2>&1

CURRENT_STEP="시작"
WARNINGS=""
COMMIT=""
BENCH_NOTE=""

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
step() { CURRENT_STEP="$1"; log "=== 단계: $1"; write_status RUNNING "진행 중: $1"; }
warn() { WARNINGS="$WARNINGS
 - $*"; log "경고: $*"; }

# JSON 문자열에 안전하게 넣을 값(따옴표·역슬래시·줄바꿈·ESC 같은 제어문자 제거)
jsafe() { printf '%s' "$1" | tr '\n\r\t' '   ' | tr -d '\042\134\000-\037\177' | cut -c1-300; }

write_setup_json() { # write_setup_json <ok true|false> <단계> <메시지>
  [ -d "$DATA_DIR" ] || return 0
  local tmp="$DATA_DIR/.setup.json.$$"
  printf '{"ok":%s,"step":"%s","msg":"%s","host":"%s","commit":"%s","ts":%s}\n' \
    "$1" "$(jsafe "$2")" "$(jsafe "$3")" "$(jsafe "${HOST:-}")" "$(jsafe "$COMMIT")" "$(date +%s)000" > "$tmp" 2>/dev/null \
    && mv -f "$tmp" "$DATA_DIR/setup.json" 2>/dev/null || true
  chmod 0644 "$DATA_DIR/setup.json" 2>/dev/null || true
}

write_status() { # write_status <RUNNING|OK|FAIL> <한 줄 설명> [자세한 글]
  local state="$1" line="$2" detail="${3:-}" tmp="$STATUS.tmp"
  {
    echo "상태: $state"
    echo "설명: $line"
    echo "시각: $(date -u +%FT%TZ)  (시작 후 $(( $(date +%s) - STARTED_AT ))초)"
    if [ -n "${HOST:-}" ]; then
      echo
      echo "접속 주소"
      echo "  서버 상태  : https://$HOST/health"
      echo "  WebSocket  : wss://$HOST/ws"
      echo "  시험 페이지: https://kjp1583-art.github.io/squad-analyzer/raid-test/sock.html?ws=wss://$HOST/ws"
      echo "  부하 시험  : https://$HOST/bench?name=3rooms (합격 기준) · https://$HOST/bench?list=1 (목록)"
    fi
    [ -n "$COMMIT" ] && { echo; echo "받은 소스: $REPO @ $REF ($COMMIT)"; }
    [ -n "$detail" ] && { echo; printf '%s\n' "$detail"; }
    [ -n "$WARNINGS" ] && { echo; echo "경고(설치는 계속됨):$WARNINGS"; }
    echo
    echo "자세한 로그: $LOG"
    echo "시험이 끝나면 Vultr 에서 이 서버를 반드시 삭제하세요(꺼 두기만 해도 과금됩니다)."
  } > "$tmp" 2>/dev/null && mv -f "$tmp" "$STATUS" 2>/dev/null || true
  if [ "$state" != "RUNNING" ]; then
    # 같은 내용을 로그에도 남긴다
    { echo "----- RAID_SETUP_STATUS -----"; cat "$STATUS" 2>/dev/null; echo "-----------------------------"; } >> "$LOG" 2>/dev/null || true
  fi
}

on_exit() {
  local rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ]; then
    local last
    last="$(grep -v '^\[.*\] ===' "$LOG" 2>/dev/null | tail -n 8 || true)"
    write_setup_json false "$CURRENT_STEP" "실패: $(printf '%s' "$last" | tail -n 1)"
    write_status FAIL "실패한 단계: $CURRENT_STEP (종료코드 $rc)" "마지막 로그 줄:
$last

이 스크립트는 다시 실행해도 안전합니다. 같은 오류가 되풀이되면 이 파일 내용을 그대로 채팅에 붙여 주세요."
  fi
  exit "$rc"
}
trap on_exit EXIT

die() { log "오류: $*"; exit 1; }

retry() { # retry <횟수> <대기초> 명령...
  local n="$1" wait_s="$2" i; shift 2
  for ((i = 1; i <= n; i++)); do
    if "$@"; then return 0; fi
    log "재시도 $i/$n 실패: $*"
    sleep "$wait_s"
  done
  return 1
}
CURL=(curl --fail --silent --show-error --location --retry 4 --retry-delay 3 --retry-all-errors --connect-timeout 10 --max-time 300)
APT=(apt-get -o DPkg::Lock::Timeout=300 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold -y)

# 2026-10-08: DPkg::Lock::Timeout 은 dpkg 잠금에만 듣고, apt-get update 의 lists 잠금·install 의 archives 잠금에는 안 듣는다
# (우분투 24.04 의 apt 2.8.3 으로 실측: 잠금을 다른 프로세스가 쥐면 0.4초 만에 E: Could not get lock). 첫 부팅의
# apt-daily / unattended-upgrades 와 겹치면 영구 실패하므로, 잠금 파일 4개를 누가 열고 있는 동안은 직접 기다린다.
APT_WAIT_S="${APT_WAIT_S:-600}"
apt_locks_busy() {
  local f
  for f in "$ROOT/var/lib/dpkg/lock-frontend" "$ROOT/var/lib/dpkg/lock" "$ROOT/var/lib/apt/lists/lock" "$ROOT/var/cache/apt/archives/lock"; do
    [ -e "$f" ] || continue
    if command -v fuser >/dev/null 2>&1; then
      fuser -s "$f" 2>/dev/null && return 0
    elif pgrep -x 'apt|apt-get|dpkg|unattended-upgr|apt.systemd.dai|aptitude' >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}
apt_wait() {
  local t0 now logged=0
  t0="$(date +%s)"
  while apt_locks_busy; do
    now="$(date +%s)"
    if [ $((now - t0)) -ge "$APT_WAIT_S" ]; then warn "apt 잠금이 ${APT_WAIT_S}초 넘게 안 풀림 — 그냥 시도함"; return 0; fi
    [ "$logged" -eq 0 ] && { log "다른 apt/dpkg 작업이 끝나길 기다리는 중(첫 부팅의 자동 업데이트일 수 있음)"; logged=1; }
    sleep 5
  done
  [ "$logged" -eq 0 ] || log "apt 잠금 풀림 ($(( $(date +%s) - t0 ))초 기다림)"
  return 0
}
aptq() { apt_wait; "${APT[@]}" "$@"; }

# 한 번에 하나만 돌게 한다(cloud-init 과 손으로 실행이 겹치지 않게)
mkdir -p "$ROOT/run"
exec 9>"$ROOT/run/raid-provision.lock"
flock -w "${LOCK_WAIT_S:-600}" 9 || die "다른 설치가 ${LOCK_WAIT_S:-600}초 넘게 돌고 있음"

[ "$(id -u)" -eq 0 ] || [ -n "$ROOT" ] || die "root 로 실행해야 합니다"
write_status RUNNING "설치 시작"
log "설치 시작: REF=$REF REPO=$REPO RUN_BENCH=$RUN_BENCH ROOT='${ROOT}'"

# ───────────── 1. 기본 패키지 ─────────────
step "기본 패키지 설치 (apt)"
retry 6 10 aptq update
retry 4 10 aptq install git curl ca-certificates ufw xz-utils gnupg apt-transport-https debian-keyring debian-archive-keyring

# ───────────── 2. 이 서버의 주소(HOST) ─────────────
step "서버 주소 정하기"
is_ipv4() { [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }
if [ -z "$HOST" ]; then
  PUBIP="$(curl -fsS --max-time 8 http://169.254.169.254/v1/interfaces/0/ipv4/address 2>/dev/null | tr -d '[:space:]' || true)"
  if ! is_ipv4 "$PUBIP"; then
    log "Vultr 메타데이터에서 IP 를 못 얻음 — 외부 서비스로 시도"
    for u in https://api.ipify.org https://ifconfig.me/ip https://ipv4.icanhazip.com; do
      PUBIP="$(curl -fsS --max-time 8 "$u" 2>/dev/null | tr -d '[:space:]' || true)"
      is_ipv4 "$PUBIP" && break
    done
  fi
  is_ipv4 "$PUBIP" || die "공인 IPv4 를 알아내지 못함 — 위쪽 HOST= 에 주소를 직접 적어 주세요"
  HOST="${PUBIP//./-}.sslip.io"
fi
[[ "$HOST" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || die "HOST 형식이 이상함: $HOST"
log "HOST=$HOST"

# ───────────── 3. Node 22 (nodejs.org 공식 tar.xz + sha256 검증) ─────────────
step "Node ${NODE_MAJOR} 설치"
case "$(uname -m)" in
  x86_64) NODE_ARCH="x64" ;;
  aarch64|arm64) NODE_ARCH="arm64" ;;
  *) die "지원하지 않는 CPU: $(uname -m)" ;;
esac
NODE_DIST="${NODE_DIST_BASE:-https://nodejs.org/dist}"
if [ -z "$NODE_VERSION" ]; then
  # 최신 22.x 의 SHASUMS 에서 파일 이름으로 버전을 읽는다(보안 패치를 자동으로 받으려는 선택)
  "${CURL[@]}" "$NODE_DIST/latest-v${NODE_MAJOR}.x/SHASUMS256.txt" -o "$OPT/.latest-shasums.txt"
  NODE_VERSION="$(sed -n "s/.*node-v\\(${NODE_MAJOR}\\.[0-9]*\\.[0-9]*\\)-linux-${NODE_ARCH}\\.tar\\.xz\$/\\1/p" "$OPT/.latest-shasums.txt" | head -n 1)"
  [ -n "$NODE_VERSION" ] || die "최신 Node ${NODE_MAJOR}.x 버전을 못 읽음"
fi
[[ "$NODE_VERSION" =~ ^${NODE_MAJOR}\.[0-9]+\.[0-9]+$ ]] || die "Node 버전 형식이 이상함: $NODE_VERSION"
NODE_DIR="$OPT/node-v$NODE_VERSION"
if [ -x "$NODE_DIR/bin/node" ]; then
  log "Node v$NODE_VERSION 이미 설치됨"
else
  TMPD="$(mktemp -d "$OPT/.nodedl.XXXXXX")"
  TARBALL="node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz"
  "${CURL[@]}" "$NODE_DIST/v$NODE_VERSION/SHASUMS256.txt" -o "$TMPD/SHASUMS256.txt"
  "${CURL[@]}" "$NODE_DIST/v$NODE_VERSION/$TARBALL" -o "$TMPD/$TARBALL"
  EXPECT="$(awk -v f="$TARBALL" '$2 == f { print $1 }' "$TMPD/SHASUMS256.txt" | head -n 1)"
  [[ "$EXPECT" =~ ^[0-9a-f]{64}$ ]] || die "SHASUMS256.txt 에 $TARBALL 의 해시가 없음"
  ACTUAL="$(sha256sum "$TMPD/$TARBALL" | awk '{print $1}')"
  [ "$EXPECT" = "$ACTUAL" ] || die "Node 압축 파일의 sha256 이 다름(기대 $EXPECT, 실제 $ACTUAL) — 설치 중단"
  log "sha256 검증 통과: $ACTUAL"
  mkdir -p "$TMPD/x"
  tar -xJf "$TMPD/$TARBALL" -C "$TMPD/x" --strip-components=1
  [ -x "$TMPD/x/bin/node" ] || die "압축을 풀었는데 bin/node 가 없음"
  rm -rf "$NODE_DIR"
  mv "$TMPD/x" "$NODE_DIR"
  rm -rf "$TMPD"
fi
ln -sfn "$NODE_DIR" "$NODE_LINK"
NODE_BIN="$NODE_LINK/bin/node"
if [ -z "$ROOT" ]; then
  ln -sf "$NODE_LINK/bin/node" /usr/local/bin/node
  ln -sf "$NODE_LINK/bin/npm" /usr/local/bin/npm
fi
GOT_NODE="$("$NODE_BIN" --version)"
log "node $GOT_NODE"
[[ "$GOT_NODE" == v${NODE_MAJOR}.* ]] || die "설치된 Node 버전이 $GOT_NODE (v${NODE_MAJOR}.x 가 아님)"

# ───────────── 4. Caddy (공식 apt 저장소) ─────────────
# 출처: https://caddyserver.com/docs/install#debian-ubuntu-raspbian (2026-10-08 확인)
step "Caddy 설치"
KEYRING="$ROOT/usr/share/keyrings/caddy-stable-archive-keyring.gpg"
CADDY_LIST="$ROOT/etc/apt/sources.list.d/caddy-stable.list"
mkdir -p "$(dirname "$KEYRING")" "$(dirname "$CADDY_LIST")"
if [ ! -s "$KEYRING" ] || [ ! -s "$CADDY_LIST" ]; then
  "${CURL[@]}" https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor --yes -o "$KEYRING"
  "${CURL[@]}" https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt -o "$CADDY_LIST"
  chmod o+r "$KEYRING" "$CADDY_LIST"
  retry 6 10 aptq update
fi
retry 4 10 aptq install caddy

# ───────────── 5. 소스 받기 ─────────────
step "소스 받기 (git)"
mkdir -p "$SRC"
if [ ! -d "$SRC/.git" ]; then git -C "$SRC" init -q; fi
git -C "$SRC" remote remove origin 2>/dev/null || true
git -C "$SRC" remote add origin "https://github.com/$REPO.git"
# 가지·태그·커밋 모두 같은 방법으로 받는다(깊이 1)
retry 4 10 git -C "$SRC" fetch --depth 1 --no-tags origin "$REF"
git -C "$SRC" checkout -q -f --detach FETCH_HEAD
COMMIT="$(git -C "$SRC" rev-parse --short=10 HEAD)"
log "소스 커밋: $COMMIT"
[ -f "$SRC/raid/echo/server.js" ] || die "받은 소스에 raid/echo/server.js 가 없음 (REF=$REF 에 에코 서버가 아직 없나요?)"

step "에코 서버 의존성 설치 (npm ci)"
( cd "$SRC/raid/echo" && npm ci --omit=dev --ignore-scripts --no-audit --no-fund )
[ -d "$SRC/raid/echo/node_modules/ws" ] || die "npm ci 뒤에 ws 가 없음"

# ───────────── 6. 사용자·폴더·서비스 ─────────────
step "서비스 사용자와 폴더"
if ! id "$SVC_USER" >/dev/null 2>&1; then
  useradd --system --user-group --home-dir "$DATA_DIR_REAL" --no-create-home --shell /usr/sbin/nologin "$SVC_USER"
fi
mkdir -p "$DATA_DIR"
chown "$SVC_USER:$SVC_USER" "$DATA_DIR" 2>/dev/null || [ -n "$ROOT" ]
chmod 0755 "$DATA_DIR"

step "systemd 서비스 등록 (raid-echo)"
UNIT_DIR="$ROOT/etc/systemd/system"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/raid-echo.service" <<EOF
[Unit]
Description=Raid stage-0 echo/survival test server (temporary)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_USER
WorkingDirectory=/opt/raid/src/raid/echo
Environment=NODE_ENV=production
Environment=PORT=$APP_PORT
Environment=HOST=127.0.0.1
Environment=TRUST_PROXY=1
Environment=DATA_DIR=$DATA_DIR_REAL
ExecStart=/opt/node/bin/node server.js
Restart=always
RestartSec=2
TimeoutStopSec=10
LimitNOFILE=4096
MemoryMax=400M
TasksMax=128
UMask=0022
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$DATA_DIR_REAL
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
LockPersonality=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$UNIT_DIR/raid-echo.service"

# 부하 시험: 에코 서버가 한가할 때만 돌고, 접속자가 생기면 물러난다(bench_when_idle.sh)
cat > "$UNIT_DIR/raid-bench.service" <<EOF
[Unit]
Description=Raid stage-0 load test (runs only while the echo server is idle)
After=raid-echo.service
Wants=raid-echo.service

[Service]
Type=oneshot
User=$SVC_USER
Group=$SVC_USER
WorkingDirectory=/opt/raid/src
Environment=DATA_DIR=$DATA_DIR_REAL
Environment=HEALTH_URL=http://127.0.0.1:$APP_PORT/health
Environment=NODE=/opt/node/bin/node
Environment=BENCH_JS=/opt/raid/src/tests/raid/bench_rooms.js
Environment=BUILD_DIR=$DATA_DIR_REAL/build
ExecStart=/bin/bash /opt/raid/src/raid/echo/bench_when_idle.sh
ExecStopPost=/bin/bash /opt/raid/src/raid/echo/bench_when_idle.sh --post
TimeoutStartSec=infinity
# 폰 시험(에코 서버)이 항상 먼저: CPU 를 다툴 때 거의 안 받는다
Nice=19
CPUWeight=1
IOWeight=1
# 메모리 한도로 일부가 죽어도 유닛 전체를 끝내지 않는다(스크립트가 실패를 기록할 수 있게)
OOMPolicy=continue
MemoryMax=550M
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$DATA_DIR_REAL
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
EOF
chmod 0644 "$UNIT_DIR/raid-bench.service"

systemctl daemon-reload
systemctl enable raid-echo.service
systemctl restart raid-echo.service

step "에코 서버가 로컬에서 뜨는지 확인"
retry 20 1 "${CURL[@]}" --retry 0 -m 3 "http://127.0.0.1:$APP_PORT/health" -o "$OPT/.local-health.json" || {
  journalctl -u raid-echo --no-pager -n 20 2>&1 | tail -n 20 || true
  die "raid-echo 가 127.0.0.1:$APP_PORT 에서 응답하지 않음"
}
log "로컬 /health: $(head -c 300 "$OPT/.local-health.json")"

# ───────────── 7. 방화벽 (Caddy 를 띄우기 전에 80/443 을 열어 둔다 — 첫 인증서 발급이 막히지 않게) ─────────────
# 허용 규칙을 먼저 넣고 마지막에 켠다(SSH 가 막히는 순서가 되지 않게)
step "방화벽 (ufw)"
ufw limit 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw default deny incoming
ufw default allow outgoing
ufw --force enable
ufw status verbose || true

# ───────────── 8. Caddy 설정 (HTTPS 자동 발급 + 프록시) ─────────────
step "Caddy 설정"
CADDYFILE="$ROOT/etc/caddy/Caddyfile"
mkdir -p "$(dirname "$CADDYFILE")"
cat > "$CADDYFILE" <<EOF
# 레이드 0단계 임시 서버 — raid/echo/provision.sh 가 만든 파일
{
	servers {
		timeouts {
			read_header 10s
			idle 2m
		}
	}
}

$HOST {
	reverse_proxy 127.0.0.1:$APP_PORT
}
EOF
if command -v caddy >/dev/null 2>&1; then
  caddy validate --config "$CADDYFILE" --adapter caddyfile
fi
systemctl enable caddy
systemctl restart caddy

# ───────────── 9. 밖에서 보이는지 스스로 확인 ─────────────
step "https://$HOST/health 확인"
# 인증서 발급에 몇 분 걸릴 수 있어 기다린다. curl 자체 재시도(--retry)는 꺼서(한 번 실패에 12초가 더 걸렸다)
# 48번 x (5초 + 응답 대기 최대 8초) = 보통 약 4분, 아주 느리면 최대 약 10분.
if ! retry 48 5 "${CURL[@]}" --retry 0 -m 8 "https://$HOST/health" -o "$OPT/.public-health.json"; then
  journalctl -u caddy --no-pager -n 30 2>&1 | tail -n 30 || true
  die "https://$HOST/health 가 열리지 않음 — 80/443 이 막혔거나 인증서 발급 실패일 수 있음(README 문제 해결 참고)"
fi
grep -q '"ok":true' "$OPT/.public-health.json" || die "https://$HOST/health 응답이 이상함: $(head -c 200 "$OPT/.public-health.json")"
log "공개 /health: $(head -c 300 "$OPT/.public-health.json")"

# ───────────── 10. 부하 시험 예약 ─────────────
if [ "$RUN_BENCH" = "1" ]; then
  step "부하 시험 예약 (한가할 때 시작)"
  if [ -f "$SRC/tests/raid/bench_rooms.js" ]; then
    systemctl daemon-reload
    if systemctl start --no-block raid-bench.service; then
      BENCH_NOTE="부하 시험(raid-bench)을 예약했습니다. 에코 서버에 접속자가 2분 동안 0명이면 시작하고(3방 15분 → 8방 5분), 접속자가 생기면 멈추고 기다립니다. 진행: https://$HOST/health 의 setup.bench · 결과: 목록 https://$HOST/bench?list=1 · 합격 기준인 3방 결과 https://$HOST/bench?name=3rooms (8방은 기록용)"
    else
      warn "raid-bench 를 시작하지 못함 (journalctl -u raid-bench 확인)"
      BENCH_NOTE="부하 시험 시작 실패"
    fi
  else
    warn "tests/raid/bench_rooms.js 가 받은 소스에 없어 부하 시험을 건너뜀 (REF=$REF — 시뮬 갈래가 합쳐진 가지를 REF 로 지정하세요)"
    BENCH_NOTE="부하 시험 건너뜀: bench_rooms.js 없음"
    printf '{"state":"skipped","msg":"bench_rooms.js 없음 (REF=%s)","ts":%s000}\n' "$(jsafe "$REF")" "$(date +%s)" > "$DATA_DIR/bench_state.json" || true
    chown "$SVC_USER:$SVC_USER" "$DATA_DIR/bench_state.json" 2>/dev/null || true
  fi
else
  BENCH_NOTE="부하 시험은 RUN_BENCH=0 이라 예약하지 않았습니다"
fi

# ───────────── 끝 ─────────────
CURRENT_STEP="완료"
write_setup_json true "완료" "설치 끝${WARNINGS:+ (경고 있음)}"
write_status OK "설치 끝 — 서버가 켜졌습니다" "$BENCH_NOTE"
log "설치 끝 ($(( $(date +%s) - STARTED_AT ))초)"
