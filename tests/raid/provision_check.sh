#!/bin/bash
# 레이드 0단계 — 설치 스크립트 스텁 실행 시험 (2026-10-08)
# 실제 우분투 서버가 없으므로 apt-get·curl·systemctl·ufw·useradd 같은 명령을 가짜(스텁)로 바꾸고
# ROOT 를 임시 폴더로 돌려서 "스크립트가 무엇을 어떤 순서로 하는지"만 확인한다.
# 실서버에서만 확인되는 것(apt 저장소·Let's Encrypt·ufw 실제 규칙·systemd 실제 기동)은 이 시험으로 알 수 없다.
#
# 실행: bash tests/raid/provision_check.sh        (종료코드 0 = 전부 통과)
# 선택: CADDY_REAL=/경로/caddy 를 주면 만들어진 Caddyfile 을 진짜 caddy validate 로 검사한다.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PROV="$REPO/raid/echo/provision.sh"
BENCH="$REPO/raid/echo/bench_when_idle.sh"
REAL_NODE="$(command -v node || true)"
T="$(mktemp -d "${TMPDIR:-/tmp}/raid-prov-check.XXXXXX")"
trap 'rm -rf "$T"' EXIT

PASS=0; FAIL=0
ok()   { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
check() { # check <설명> <명령...>
  local d="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi
}
contains() { grep -qF -- "$2" "$1"; }          # contains <파일> <글자>
lineno() { grep -nF -- "$2" "$1" | head -n 1 | cut -d: -f1; }   # 첫 줄 번호(없으면 빈 값)
lineno_re() { grep -nE -- "$2" "$1" | head -n 1 | cut -d: -f1; }
before() { # before <파일> <A> <B> : A 가 B 보다 먼저(둘 다 있어야 함)
  local a b; a="$(lineno "$1" "$2")"; b="$(lineno "$1" "$3")"
  [ -n "$a" ] && [ -n "$b" ] && [ "$a" -lt "$b" ]
}
section() { printf '\n== %s\n' "$1"; }

[ -n "$REAL_NODE" ] || { echo "node 가 필요합니다"; exit 2; }
command -v xz >/dev/null || { echo "xz 가 필요합니다"; exit 2; }

# ───────────── 스텁과 고정 파일 만들기 ─────────────
STUB="$T/stubs"; FIX="$T/fix"; mkdir -p "$STUB" "$FIX"
case "$(uname -m)" in x86_64) ARCH=x64 ;; aarch64|arm64) ARCH=arm64 ;; *) echo "지원 안 하는 CPU"; exit 2 ;; esac
NV="22.99.0"

# 가짜 Node 압축 파일: bin/node(--version 만 흉내, 나머지는 진짜 node), bin/npm(ci 흉내)
mkdir -p "$FIX/pkg/node-v$NV-linux-$ARCH/bin"
cat > "$FIX/pkg/node-v$NV-linux-$ARCH/bin/node" <<EOF
#!/bin/bash
if [ "\${1:-}" = "--version" ]; then echo v$NV; exit 0; fi
exec "$REAL_NODE" "\$@"
EOF
cat > "$FIX/pkg/node-v$NV-linux-$ARCH/bin/npm" <<'EOF'
#!/bin/bash
echo "npm $* (cwd=$PWD)" >> "$CALLS"
[ -n "${FAIL_NPM:-}" ] && { echo "npm ERR! 가짜 실패" >&2; exit 1; }
mkdir -p node_modules/ws
echo '{}' > node_modules/ws/package.json
EOF
chmod +x "$FIX/pkg/node-v$NV-linux-$ARCH/bin/"*
tar -cJf "$FIX/node.tar.xz" -C "$FIX/pkg" "node-v$NV-linux-$ARCH"
GOODSHA="$(sha256sum "$FIX/node.tar.xz" | awk '{print $1}')"
BADSHA="$(printf '0%.0s' $(seq 1 64))"
{
  echo "$GOODSHA  node-v$NV-linux-arm64.tar.xz"
  echo "$GOODSHA  node-v$NV-linux-x64.tar.xz"
  echo "aaaa$GOODSHA  node-v$NV-linux-x64.tar.gz"
  echo "$BADSHA  node-v$NV-darwin-x64.tar.xz"
} > "$FIX/shasums_good"
sed "s/^$GOODSHA  /$BADSHA  /" "$FIX/shasums_good" > "$FIX/shasums_bad"
grep -v "linux-" "$FIX/shasums_good" > "$FIX/shasums_noline"

# 명령 스텁
w() { cat > "$STUB/$1"; chmod +x "$STUB/$1"; }
w apt-get <<'EOF'
#!/bin/bash
echo "apt-get $*" >> "$CALLS"
[ -n "${FAIL_APT:-}" ] && { echo "E: 가짜 apt 실패" >&2; exit 100; }
exit 0
EOF
w curl <<'EOF'
#!/bin/bash
echo "curl $*" >> "$CALLS"
url=""; out=""
while [ $# -gt 0 ]; do
  case "$1" in -o) out="$2"; shift 2 ;; http*) url="$1"; shift ;; *) shift ;; esac
done
emit() { if [ -n "$out" ]; then cat > "$out"; else cat; fi; }
case "$url" in
  */latest-v22.x/SHASUMS256.txt) emit < "$FIX/shasums_good" ;;
  */dist/v22.99.0/SHASUMS256.txt)
    if [ -n "${BAD_SHA:-}" ]; then emit < "$FIX/shasums_bad"
    elif [ -n "${NO_SHA_LINE:-}" ]; then emit < "$FIX/shasums_noline"
    else emit < "$FIX/shasums_good"; fi ;;
  */dist/v22.99.0/node-v22.99.0-linux-*.tar.xz) emit < "$FIX/node.tar.xz" ;;
  *dl.cloudsmith.io*gpg.key) printf 'FAKE-KEY-BYTES' | emit ;;
  *dl.cloudsmith.io*debian.deb.txt) echo 'deb [signed-by=/usr/share/keyrings/caddy-stable-archive-keyring.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main' | emit ;;
  *169.254.169.254*) [ -n "${NO_META:-}" ] && exit 22; echo 203.0.113.7 | emit ;;
  *api.ipify.org*) echo 198.51.100.9 | emit ;;
  http://127.0.0.1:8080/health*)
    if [ -n "${HEALTH_SEQ:-}" ]; then   # bench 시험용: 파일의 첫 줄을 소비(마지막 줄은 계속 반복)
      n="$(head -n 1 "$HEALTH_SEQ")"; [ "$(wc -l < "$HEALTH_SEQ")" -gt 1 ] && sed -i 1d "$HEALTH_SEQ"
      [ "$n" = "down" ] && exit 7
      echo "{\"ok\":true,\"conns\":$n}" | emit
    else echo '{"ok":true,"conns":0}' | emit; fi ;;
  https://*/health) [ -n "${FAIL_PUBLIC:-}" ] && exit 7; echo '{"ok":true,"v":1}' | emit ;;
  *) echo "curl 스텁: 모르는 주소 $url" >&2; exit 22 ;;
esac
EOF
w gpg <<'EOF'
#!/bin/bash
echo "gpg $*" >> "$CALLS"
out=""; while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done
cat > "$out"
EOF
w systemctl <<'EOF'
#!/bin/bash
echo "systemctl $*" >> "$CALLS"
[ -n "${FAIL_BENCH_START:-}" ] && [ "$1" = "start" ] && exit 1
exit 0
EOF
w ufw <<'EOF'
#!/bin/bash
echo "ufw $*" >> "$CALLS"
exit 0
EOF
w useradd <<'EOF'
#!/bin/bash
echo "useradd $*" >> "$CALLS"
touch "$STATE/user_raid"
EOF
w id <<'EOF'
#!/bin/bash
if [ "${1:-}" = "raid" ]; then [ -e "$STATE/user_raid" ]; exit; fi
exec /usr/bin/id "$@"
EOF
w chown <<'EOF'
#!/bin/bash
echo "chown $*" >> "$CALLS"
EOF
w journalctl <<'EOF'
#!/bin/bash
echo "journalctl $*" >> "$CALLS"
echo "(가짜 journal 줄)"
EOF
w sleep <<'EOF'
#!/bin/bash
/usr/bin/sleep 0.05
EOF
w caddy <<'EOF'
#!/bin/bash
echo "caddy $*" >> "$CALLS"
if [ -n "${CADDY_REAL:-}" ] && [ -x "$CADDY_REAL" ]; then exec "$CADDY_REAL" "$@"; fi
exit 0
EOF

# 가짜 원격 저장소(git 은 진짜 사용 — 얕은 받기 흐름을 그대로 시험)
ORIGIN="$T/origin"
mkdir -p "$ORIGIN/raid/echo" "$ORIGIN/tests/raid"
cp "$REPO/raid/echo/server.js" "$REPO/raid/echo/package.json" "$REPO/raid/echo/package-lock.json" "$REPO/raid/echo/bench_when_idle.sh" "$ORIGIN/raid/echo/"
git -C "$ORIGIN" init -q -b main
git -C "$ORIGIN" -c user.email=t@t -c user.name=t add -A
git -C "$ORIGIN" -c user.email=t@t -c user.name=t commit -q -m base
git -C "$ORIGIN" branch nobench
cat > "$ORIGIN/tests/raid/bench_rooms.js" <<'EOF'
// 가짜 부하 시험: 인자를 받아 결과 파일을 쓴다
const a = process.argv.slice(2);
const get = (k) => a[a.indexOf(k) + 1];
require('fs').writeFileSync(get('--out'), JSON.stringify({ rooms: Number(get('--rooms')), secs: Number(get('--secs')), realtime: a.includes('--realtime') }));
EOF
git -C "$ORIGIN" -c user.email=t@t -c user.name=t add -A
git -C "$ORIGIN" -c user.email=t@t -c user.name=t commit -q -m bench
# nobench 가지는 bench_rooms.js 가 없는 커밋
git -C "$ORIGIN" branch -f nobench HEAD~1
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0="url.file://$ORIGIN.insteadOf"
export GIT_CONFIG_VALUE_0="https://github.com/kjp1583-art/squad-analyzer.git"
export GIT_TERMINAL_PROMPT=0

# 시나리오 하나를 돌린다: run_prov <이름> [VAR=값 ...]  → $T/<이름>/ 아래에 ROOT 등을 만든다
run_prov() {
  local name="$1"; shift
  local d="$T/$name"
  mkdir -p "$d/root" "$d/state" "$d/home"
  : >> "$d/calls.log"
  env -i PATH="$STUB:/usr/local/bin:/usr/bin:/bin" HOME="$d/home" \
    ROOT="$d/root" CALLS="$d/calls.log" FIX="$FIX" STATE="$d/state" \
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0="$GIT_CONFIG_KEY_0" GIT_CONFIG_VALUE_0="$GIT_CONFIG_VALUE_0" GIT_TERMINAL_PROMPT=0 \
    CADDY_REAL="${CADDY_REAL:-}" \
    "$@" bash "$PROV" > "$d/stdout.txt" 2>&1
  echo $? > "$d/rc"
}
rcof() { cat "$T/$1/rc"; }
R() { echo "$T/$1/root"; }
CALLS_OF() { echo "$T/$1/calls.log"; }

# 사전 점검: 위험한 명령(apt-get·systemctl·ufw·useradd …)이 전부 스텁을 가리키는지 확인한다.
# 하나라도 진짜를 가리키면 아무것도 실행하지 않고 중단한다(2026-10-08: 이 점검이 없을 때 진짜 apt-get 이 돈 적이 있다).
PROBE="$(env -i PATH="$STUB:/usr/local/bin:/usr/bin:/bin" HOME="$T" ROOT="$T/probe/root" PROVISION_PROBE=1 bash "$PROV" 2>&1)"
for c in apt-get curl systemctl ufw useradd id chown gpg caddy journalctl; do
  if ! printf '%s\n' "$PROBE" | grep -qx "$STUB/$c"; then
    echo "중단: 시험 환경에서 '$c' 가 스텁($STUB/$c)이 아니라 진짜를 가리킵니다. 출력:"; echo "$PROBE"; exit 2
  fi
done

# ───────────── 정적 검사 ─────────────
section "정적 검사"
check "provision.sh bash -n" bash -n "$PROV"
check "bench_when_idle.sh bash -n" bash -n "$BENCH"
if command -v shellcheck >/dev/null; then
  check "shellcheck 경고 0 (provision.sh · bench_when_idle.sh · 이 시험)" shellcheck "$PROV" "$BENCH" "$HERE/provision_check.sh"
else
  echo "  --   shellcheck 없음 — 건너뜀 (pip install shellcheck-py)"
fi
check "첫 줄이 #!/bin/bash (Startup Script · cloud-init 둘 다)" test "$(head -n 1 "$PROV")" = "#!/bin/bash"
check "set -euo pipefail" grep -q '^set -euo pipefail' "$PROV"
check "토큰·키로 보이는 글자가 없다" bash -c "! grep -nEi '(api[_-]?key|secret|token|password|AKIA|ghp_|sk-)' '$PROV' '$BENCH'"
check "모델 이름이 없다" bash -c "! grep -niE 'claude|anthropic|gpt' '$PROV' '$BENCH' '$REPO/raid/echo/server.js' '$REPO/raid/echo/README.md'"

# ───────────── 정상 실행 ─────────────
section "정상 실행 (Vultr 메타데이터 IP, bench_rooms.js 있음)"
run_prov ok REF=main
D="$T/ok"; C="$D/calls.log"; ROOTD="$D/root"; ST="$ROOTD/root/RAID_SETUP_STATUS.txt"
check "종료코드 0" test "$(rcof ok)" = 0
check "상태 파일 OK" contains "$ST" "상태: OK"
check "HOST = IP 를 하이픈으로 바꾼 sslip.io" contains "$ST" "https://203-0-113-7.sslip.io/health"
check "wss 주소가 상태 파일에" contains "$ST" "wss://203-0-113-7.sslip.io/ws"
check "시험 페이지 주소가 상태 파일에" contains "$ST" "https://kjp1583-art.github.io/squad-analyzer/raid-test/sock.html?ws=wss://203-0-113-7.sslip.io/ws"
check "삭제 경고 문구가 상태 파일에" contains "$ST" "반드시 삭제"
check "같은 내용이 /var/log/raid-provision.log 에도" contains "$ROOTD/var/log/raid-provision.log" "상태: OK"
check "메타데이터 주소를 먼저 불렀다" contains "$C" "169.254.169.254/v1/interfaces/0/ipv4/address"
check "외부 IP 서비스는 안 불렀다" bash -c "! grep -q ipify '$C'"
check "apt 호출에 잠금 대기 옵션" contains "$C" "DPkg::Lock::Timeout=300"
check "필수 패키지 설치 (git curl ca-certificates ufw xz-utils)" bash -c "grep 'apt-get' '$C' | grep -q 'install git curl ca-certificates ufw xz-utils'"
check "Node: 최신 22.x 를 SHASUMS 에서 읽어 고름" contains "$C" "latest-v22.x/SHASUMS256.txt"
check "Node: 해당 버전 SHASUMS256.txt 도 받음" contains "$C" "dist/v$NV/SHASUMS256.txt"
check "Node: /opt/node → node-v$NV 링크" test "$(readlink "$ROOTD/opt/node")" = "$ROOTD/opt/node-v$NV"
check "Node: bin/node 실행됨" test "$("$ROOTD/opt/node/bin/node" --version)" = "v$NV"
check "Caddy: 공식 키·목록 주소" bash -c "grep -q 'cloudsmith.io/public/caddy/stable/gpg.key' '$C' && grep -q 'cloudsmith.io/public/caddy/stable/debian.deb.txt' '$C'"
check "Caddy: 키링 파일 생김" test -s "$ROOTD/usr/share/keyrings/caddy-stable-archive-keyring.gpg"
check "Caddy: apt 목록 파일 생김" test -s "$ROOTD/etc/apt/sources.list.d/caddy-stable.list"
check "Caddy: apt install caddy" bash -c "grep 'apt-get' '$C' | grep -q 'install caddy'"
check "소스: /opt/raid/src 에 raid/echo/server.js" test -f "$ROOTD/opt/raid/src/raid/echo/server.js"
check "소스: 깊이 1 (커밋이 하나뿐)" test "$(git -C "$ROOTD/opt/raid/src" rev-list --count HEAD)" = 1
check "npm ci --omit=dev 를 raid/echo 에서" bash -c "grep -q 'npm ci --omit=dev.*raid/echo' '$C'"
check "node_modules/ws 설치됨" test -d "$ROOTD/opt/raid/src/raid/echo/node_modules/ws"
check "사용자 raid 를 시스템 계정·nologin 으로 한 번 만듦" bash -c "grep -c '^useradd' '$C' | grep -qx 1 && grep '^useradd' '$C' | grep -q -- '--system' && grep '^useradd' '$C' | grep -q nologin"
check "데이터 폴더 생김" test -d "$ROOTD/var/lib/raid-echo"

U="$ROOTD/etc/systemd/system/raid-echo.service"
for kv in "User=raid" "Environment=PORT=8080" "Environment=HOST=127.0.0.1" "Environment=TRUST_PROXY=1" "Environment=DATA_DIR=/var/lib/raid-echo" \
          "ExecStart=/opt/node/bin/node server.js" "Restart=always" "NoNewPrivileges=yes" "ProtectSystem=strict" \
          "ReadWritePaths=/var/lib/raid-echo" "PrivateTmp=yes" "MemoryMax=400M" "WorkingDirectory=/opt/raid/src/raid/echo"; do
  check "raid-echo.service: $kv" contains "$U" "$kv"
done
check "raid-echo.service: node 와 충돌하는 MemoryDenyWriteExecute 를 쓰지 않음" bash -c "! grep -q MemoryDenyWriteExecute '$U'"
check "raid-bench.service: oneshot · raid 사용자 · 쓰기는 데이터 폴더만" bash -c "grep -q 'Type=oneshot' '$ROOTD/etc/systemd/system/raid-bench.service' && grep -q 'User=raid' '$ROOTD/etc/systemd/system/raid-bench.service' && grep -q 'ReadWritePaths=/var/lib/raid-echo' '$ROOTD/etc/systemd/system/raid-bench.service'"

CF="$ROOTD/etc/caddy/Caddyfile"
check "Caddyfile: HOST 블록 + reverse_proxy 127.0.0.1:8080" bash -c "grep -q '^203-0-113-7.sslip.io {' '$CF' && grep -q 'reverse_proxy 127.0.0.1:8080' '$CF'"
if [ -n "${CADDY_REAL:-}" ] && [ -x "${CADDY_REAL:-}" ]; then
  check "진짜 caddy validate 가 Caddyfile 을 통과시킴" env HOME="$D/home" "$CADDY_REAL" validate --config "$CF" --adapter caddyfile
  check "진짜 caddy fmt 와 형식이 같다" bash -c "'$CADDY_REAL' fmt --diff '$CF'"
else
  echo "  --   CADDY_REAL 없음 — 진짜 caddy validate 는 건너뜀"
fi

# ufw 순서: 허용 규칙 → 기본 deny → enable 이 맨 마지막
UF="$D/ufw.log"; grep '^ufw ' "$C" > "$UF"
check "ufw: 22/tcp limit" contains "$UF" "ufw limit 22/tcp"
check "ufw: 80/tcp·443/tcp·443/udp 허용" bash -c "grep -qx 'ufw allow 80/tcp' '$UF' && grep -qx 'ufw allow 443/tcp' '$UF' && grep -qx 'ufw allow 443/udp' '$UF'"
check "ufw: 기본 deny incoming" contains "$UF" "ufw default deny incoming"
check "ufw: 22 허용이 enable 보다 먼저 (SSH 가 막히는 순서 아님)" before "$UF" "ufw limit 22/tcp" "ufw --force enable"
check "ufw: 80·443 허용이 enable 보다 먼저" before "$UF" "ufw allow 443/udp" "ufw --force enable"
check "ufw: deny 설정이 enable 보다 먼저" before "$UF" "ufw default deny incoming" "ufw --force enable"
check "ufw: enable 뒤에는 상태 조회만" bash -c "awk '/--force enable/{f=1;next} f' '$UF' | grep -vq 'ufw status' && exit 1 || exit 0"

# 전체 순서: apt → Node 받기 → 해시 확인 뒤 압축 풀기 → Caddy → 소스 → npm → 서비스 → Caddy 재시작 → ufw → 공개 health → bench
check "순서: Node 압축 파일은 해시를 받은 뒤 내려받음" before "$C" "dist/v$NV/SHASUMS256.txt" "linux-$ARCH.tar.xz -o"
check "순서: apt update 가 Node 설치보다 먼저" before "$C" "apt-get -o DPkg::Lock::Timeout=300 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold -y update" "latest-v22.x"
check "순서: raid-echo 시작 뒤에 caddy 재시작" before "$C" "systemctl restart raid-echo.service" "systemctl restart caddy"
check "순서: caddy 재시작 뒤에 ufw enable" before "$C" "systemctl restart caddy" "ufw --force enable"
check "순서: ufw enable 뒤에 공개 /health 확인" before "$C" "ufw --force enable" "https://203-0-113-7.sslip.io/health"
check "순서: 공개 /health 확인 뒤에 raid-bench 시작" before "$C" "https://203-0-113-7.sslip.io/health" "systemctl start --no-block raid-bench.service"
check "systemctl: daemon-reload · enable raid-echo · enable caddy" bash -c "grep -q 'systemctl daemon-reload' '$C' && grep -q 'systemctl enable raid-echo.service' '$C' && grep -q 'systemctl enable caddy' '$C'"
check "setup.json 이 유효한 JSON 이고 ok:true" bash -c "'$REAL_NODE' -e 'const j=JSON.parse(require(\"fs\").readFileSync(process.argv[1],\"utf8\")); if(j.ok!==true||j.host!==\"203-0-113-7.sslip.io\"||!j.commit) process.exit(1)' '$ROOTD/var/lib/raid-echo/setup.json'"
check "root 가 아니면 /usr/local/bin 링크를 건드리지 않음(ROOT 시험 모드)" test ! -e /usr/local/bin/node.provision-check

# 유닛 검증 (systemd-analyze 가 --root 를 지원하면)
section "systemd-analyze verify"
if command -v systemd-analyze >/dev/null; then
  VR="$T/verifyroot"; mkdir -p "$VR/etc/systemd/system" "$VR/opt/node/bin" "$VR/opt/raid/src/raid/echo" "$VR/opt/raid/src/raid/echo" "$VR/var/lib/raid-echo" "$VR/bin" "$VR/usr/bin"
  cp "$U" "$ROOTD/etc/systemd/system/raid-bench.service" "$VR/etc/systemd/system/"
  printf '#!/bin/sh\n' > "$VR/opt/node/bin/node"; chmod +x "$VR/opt/node/bin/node"
  cp /bin/bash "$VR/bin/bash" 2>/dev/null || true
  : > "$VR/opt/raid/src/raid/echo/bench_when_idle.sh"
  VOUT="$(systemd-analyze verify --root="$VR" /etc/systemd/system/raid-echo.service /etc/systemd/system/raid-bench.service 2>&1)"; VRC=$?
  while IFS= read -r l; do printf '        %s\n' "$l"; done <<< "$VOUT"
  # raid 사용자는 이 샌드박스에 없으므로 그 경고 하나만 허용한다
  REST="$(echo "$VOUT" | grep -v -iE "raid.*(not found|does not exist|Failed to resolve)|Unknown user|multi-user.target|network-online|Failed to create|Cannot determine cgroup|cgroup" || true)"
  if [ -z "$REST" ]; then ok "systemd-analyze verify: 유닛 문법·옵션 오류 없음 (rc=$VRC)"; else bad "systemd-analyze verify 가 지적함: $REST"; fi
else
  echo "  --   systemd-analyze 없음 — 건너뜀"
fi

# ───────────── 외부 IP 서비스로 대체 / HOST 지정 ─────────────
section "메타데이터가 안 될 때 · HOST 를 직접 줄 때"
run_prov nometa NO_META=1
check "메타데이터 실패 → 외부 서비스 IP 로 HOST 결정 (198-51-100-9.sslip.io)" contains "$(R nometa)/root/RAID_SETUP_STATUS.txt" "198-51-100-9.sslip.io"
run_prov myhost HOST=raid.example.com
check "HOST 지정 시 그 값을 Caddyfile 에" grep -q '^raid.example.com {' "$(R myhost)/etc/caddy/Caddyfile"
check "HOST 지정 시 메타데이터를 부르지 않음" bash -c "! grep -q 169.254 '$(CALLS_OF myhost)'"

# ───────────── bench_rooms.js 가 없는 가지 ─────────────
section "bench_rooms.js 가 없을 때 — 설치 전체는 성공, 사유 기록"
run_prov nobench REF=nobench
check "종료코드 0 (설치는 성공)" test "$(rcof nobench)" = 0
check "상태 파일 OK + 경고에 bench_rooms.js 사유" bash -c "grep -q '상태: OK' '$(R nobench)/root/RAID_SETUP_STATUS.txt' && grep -q 'bench_rooms.js' '$(R nobench)/root/RAID_SETUP_STATUS.txt'"
check "raid-bench 를 시작하지 않음" bash -c "! grep -q 'start --no-block raid-bench' '$(CALLS_OF nobench)'"
check "bench_state.json 에 skipped" grep -q '"state":"skipped"' "$(R nobench)/var/lib/raid-echo/bench_state.json"
run_prov nobench0 RUN_BENCH=0
check "RUN_BENCH=0 이면 예약 안 함" bash -c "! grep -q 'raid-bench' '$(CALLS_OF nobench0)' || ! grep -q 'start --no-block' '$(CALLS_OF nobench0)'"
run_prov benchstartfail FAIL_BENCH_START=1
check "raid-bench 시작 실패는 경고일 뿐 설치는 성공" bash -c "test \"\$(cat '$T/benchstartfail/rc')\" = 0 && grep -q '상태: OK' '$(R benchstartfail)/root/RAID_SETUP_STATUS.txt' && grep -q '경고' '$(R benchstartfail)/root/RAID_SETUP_STATUS.txt'"

# ───────────── 실패 시나리오 ─────────────
section "실패 시나리오 — 멈추고, 상태 파일에 단계와 사유"
run_prov badsha BAD_SHA=1
S="$(R badsha)/root/RAID_SETUP_STATUS.txt"
check "sha256 불일치: 종료코드 ≠ 0" test "$(rcof badsha)" != 0
check "sha256 불일치: 상태 FAIL + 단계 'Node'" bash -c "grep -q '상태: FAIL' '$S' && grep -q '실패한 단계: Node' '$S'"
check "sha256 불일치: 마지막 오류 줄이 상태 파일에 (sha256 이 다름)" contains "$S" "sha256"
check "sha256 불일치: 압축을 풀지도 /opt/node 를 만들지도 않음" bash -c "test ! -e '$(R badsha)/opt/node' && test ! -d '$(R badsha)/opt/node-v$NV'"
check "sha256 불일치: 이후 단계(Caddy 설치·소스 받기·ufw)가 실행되지 않음" bash -c "! grep -q 'install caddy' '$(CALLS_OF badsha)' && ! grep -q '^ufw' '$(CALLS_OF badsha)' && test ! -d '$(R badsha)/opt/raid/src/.git'"
check "sha256 불일치: setup.json 은 데이터 폴더가 없으므로 안 만들어도 됨(파일 없음 또는 ok:false)" bash -c "test ! -e '$(R badsha)/var/lib/raid-echo/setup.json' || grep -q '\"ok\":false' '$(R badsha)/var/lib/raid-echo/setup.json'"
run_prov noline NO_SHA_LINE=1
check "SHASUMS 에 해당 파일 줄이 없어도 중단" bash -c "test \"\$(cat '$T/noline/rc')\" != 0 && grep -q '해시가 없음' '$(R noline)/root/RAID_SETUP_STATUS.txt'"
run_prov aptfail FAIL_APT=1
check "apt 실패: 단계 이름 기록 · 종료코드 ≠ 0" bash -c "test \"\$(cat '$T/aptfail/rc')\" != 0 && grep -q '실패한 단계: 기본 패키지' '$(R aptfail)/root/RAID_SETUP_STATUS.txt'"
check "apt 실패: 재시도했다 (5번)" test "$(grep -c ' update$' "$(CALLS_OF aptfail)")" -ge 5
run_prov npmfail FAIL_NPM=1
check "npm 실패: 단계 'npm ci' 기록 · 서비스 등록 전에 중단" bash -c "test \"\$(cat '$T/npmfail/rc')\" != 0 && grep -q '실패한 단계: 에코 서버 의존성' '$(R npmfail)/root/RAID_SETUP_STATUS.txt' && ! grep -q 'enable raid-echo' '$(CALLS_OF npmfail)'"
run_prov badref REF=no-such-branch
check "없는 REF: 단계 '소스 받기' 에서 중단" bash -c "test \"\$(cat '$T/badref/rc')\" != 0 && grep -q '실패한 단계: 소스 받기' '$(R badref)/root/RAID_SETUP_STATUS.txt'"
run_prov badhost 'HOST=a b;rm -rf'
check "이상한 HOST 는 거부(명령 주입 방지)" bash -c "test \"\$(cat '$T/badhost/rc')\" != 0 && grep -q 'HOST 형식' '$(R badhost)/var/log/raid-provision.log'"
run_prov nopub FAIL_PUBLIC=1
S="$(R nopub)/root/RAID_SETUP_STATUS.txt"
check "공개 /health 가 안 열리면 FAIL (단계: health 확인)" bash -c "test \"\$(cat '$T/nopub/rc')\" != 0 && grep -q '상태: FAIL' '$S' && grep -q 'health 확인' '$S'"
check "공개 /health 실패: 80/443 · 인증서 단서가 로그에" bash -c "grep -q '80/443' '$(R nopub)/var/log/raid-provision.log'"
check "공개 /health 실패: 기다리며 재시도(48번) 했다" test "$(grep -c 'https://203-0-113-7.sslip.io/health' "$(CALLS_OF nopub)")" -ge 40
check "공개 /health 실패: bench 는 시작하지 않음" bash -c "! grep -q 'start --no-block raid-bench' '$(CALLS_OF nopub)'"
check "공개 /health 실패: setup.json 에 ok:false 와 단계" bash -c "grep -q '\"ok\":false' '$(R nopub)/var/lib/raid-echo/setup.json' && grep -q 'health' '$(R nopub)/var/lib/raid-echo/setup.json'"

# ───────────── 다시 실행해도 안전 ─────────────
section "재실행 (idempotent)"
run_prov again
D2="$T/again"
sha_units1="$(cat "$D2/root/etc/systemd/system/"*.service "$D2/root/etc/caddy/Caddyfile" | sha256sum)"
cp "$D2/calls.log" "$D2/calls1.log"
run_prov again
check "두 번째 실행도 종료코드 0" test "$(rcof again)" = 0
sha_units2="$(cat "$D2/root/etc/systemd/system/"*.service "$D2/root/etc/caddy/Caddyfile" | sha256sum)"
check "유닛·Caddyfile 이 첫 실행과 똑같다" test "$sha_units1" = "$sha_units2"
check "Node 를 다시 내려받지 않음 (압축 파일 요청 1번뿐)" test "$(grep -c 'linux-.*\.tar\.xz -o' "$D2/calls.log")" = 1
check "사용자는 한 번만 만듦" test "$(grep -c '^useradd' "$D2/calls.log")" = 1
check "/opt/node 링크가 그대로 (링크 안에 링크가 생기지 않음)" bash -c "test \"\$(readlink '$D2/root/opt/node')\" = '$D2/root/opt/node-v$NV' && test ! -e '$D2/root/opt/node-v$NV/node-v$NV'"
check "Caddy 키링을 다시 받지 않음 (gpg.key 요청 1번뿐)" test "$(grep -c 'gpg.key' "$D2/calls.log")" = 1
check "소스는 여전히 깊이 1 · 작업 트리 깨끗" bash -c "test \"\$(git -C '$D2/root/opt/raid/src' rev-list --count HEAD)\" = 1 && test -z \"\$(git -C '$D2/root/opt/raid/src' status --porcelain --untracked-files=no)\""
# 중간에 실패했다가 고친 뒤 재실행
run_prov recover FAIL_PUBLIC=1
check "(복구) 1차는 공개 health 실패" test "$(rcof recover)" != 0
run_prov recover
check "(복구) 같은 폴더에서 다시 돌리면 성공하고 상태 파일이 OK 로 바뀜" bash -c "test \"\$(cat '$T/recover/rc')\" = 0 && grep -q '상태: OK' '$(R recover)/root/RAID_SETUP_STATUS.txt' && ! grep -q '상태: FAIL' '$(R recover)/root/RAID_SETUP_STATUS.txt'"

# 동시에 두 번 실행 막기
section "동시 실행 잠금"
mkdir -p "$T/lock/root/run"
( exec 8>"$T/lock/root/run/raid-provision.lock"; flock 8; sleep 4 ) &
LOCKPID=$!
sleep 0.5
run_prov lock LOCK_WAIT_S=1 ROOT="$T/lock/root"
check "다른 설치가 잠금을 쥐고 있으면 기다리다 실패" bash -c "test \"\$(cat '$T/lock/rc')\" != 0 && grep -q '다른 설치가' '$T/lock/root/var/log/raid-provision.log'"
wait "$LOCKPID" 2>/dev/null

# ───────────── bench_when_idle.sh ─────────────
section "bench_when_idle.sh (한가할 때만 · 접속자가 생기면 물러남)"
mkbench() { # mkbench <이름> : 가짜 BENCH_JS 와 DATA_DIR 준비
  local d="$T/b_$1"; mkdir -p "$d/data"
  cat > "$d/bench_rooms.js" <<'EOF'
const a = process.argv.slice(2);
const get = (k) => a[a.indexOf(k) + 1];
const fs = require('fs');
if (process.env.BENCH_FAIL) { console.error('가짜 실패'); process.exit(3); }
// 접속자 중단 시험: 첫 실행에서는 "폰이 접속했다"(3명) → 곧 사라진다 는 흐름을 health 시퀀스 파일에 써 넣고 오래 버틴다
if (process.env.ABORT_TEST) {
  const marker = process.env.SEQ_FILE + '.marker';
  if (!fs.existsSync(marker)) {
    fs.writeFileSync(marker, '1');
    fs.writeFileSync(process.env.SEQ_FILE, '3\n3\n0\n');
    setTimeout(() => {}, 30000);
    return;
  }
}
setTimeout(() => {
  fs.writeFileSync(get('--out'), JSON.stringify({ rooms: Number(get('--rooms')), secs: Number(get('--secs')), realtime: a.includes('--realtime') }));
}, Number(process.env.BENCH_MS || 600));
EOF
  echo "$d"
}
run_bench() { # run_bench <dir> VAR=값 ...
  local d="$1"; shift
  env -i PATH="$STUB:/usr/local/bin:/usr/bin:/bin" CALLS="$d/calls.log" FIX="$FIX" \
    DATA_DIR="$d/data" NODE="$REAL_NODE" BENCH_JS="$d/bench_rooms.js" IDLE_S=1 POLL_S=1 GIVE_UP_S=30 STAGE_GRACE_S=20 \
    PLAN="3:900:bench_3rooms.json 8:300:bench_8rooms.json" "$@" bash "$BENCH" > "$d/out.txt" 2>&1
  echo $? > "$d/rc"
}
# sleep 스텁이 0.05 초라 POLL_S=1 이어도 빠르게 돈다 → 시간 판정은 date 기준(IDLE_S=1)

B="$(mkbench idle)"; echo 0 > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq"
check "접속자 0 이 이어지면 두 단계 실행 · 종료코드 0" test "$(cat "$B/rc")" = 0
check "3방 900초 --realtime 인자가 그대로 전달됨" bash -c "'$REAL_NODE' -e 'const j=JSON.parse(require(\"fs\").readFileSync(process.argv[1],\"utf8\")); if(j.rooms!==3||j.secs!==900||j.realtime!==true) process.exit(1)' '$B/data/bench_3rooms.json'"
check "8방 300초 결과 파일도 생김" test -s "$B/data/bench_8rooms.json"
check "bench_state.json 이 done" grep -q '"state":"done"' "$B/data/bench_state.json"
check "다시 돌리면 이미 있는 단계는 건너뜀" bash -c "mt1=\$(stat -c %Y '$B/data/bench_3rooms.json'); sleep 1.1; echo 0 > '$B/seq'; cd /; env -i PATH='$STUB:/usr/bin:/bin' CALLS='$B/calls.log' FIX='$FIX' DATA_DIR='$B/data' NODE='$REAL_NODE' BENCH_JS='$B/bench_rooms.js' IDLE_S=1 POLL_S=1 HEALTH_SEQ='$B/seq' bash '$BENCH' >> '$B/out.txt' 2>&1; test \"\$(stat -c %Y '$B/data/bench_3rooms.json')\" = \"\$mt1\" && grep -q '이미 있음' '$B/out.txt'"

B="$(mkbench busy)"
# 접속자 2명이 몇 번 보이다가 0 이 계속됨 → 그동안은 시작하지 않는다
printf '2\n2\n1\n0\n' > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq"
check "접속자가 있는 동안엔 시작하지 않고 0 이 이어진 뒤 실행" bash -c "test \"\$(cat '$B/rc')\" = 0 && test -s '$B/data/bench_3rooms.json'"
check "대기 중 상태 'waiting' 이 기록된 적 있다" grep -q 'waiting' "$B/out.txt"

B="$(mkbench abort)"
# 시험이 도는 도중 접속자 3명이 생김(가짜 bench_rooms.js 가 시퀀스 파일에 써 넣음) → 중단·결과 파일 삭제 → 다시 기다렸다 재시도
echo 0 > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq" ABORT_TEST=1 SEQ_FILE="$B/seq" BENCH_MS=200
check "시험 도중 접속자 발생 → '시험 중단' 로그" grep -q '시험 중단' "$B/out.txt"
check "중단된 단계는 불완전한 결과 파일을 남기지 않았거나 나중에 완성됨" bash -c "! test -e '$B/data/bench_3rooms.json' || '$REAL_NODE' -e 'JSON.parse(require(\"fs\").readFileSync(process.argv[1],\"utf8\"))' '$B/data/bench_3rooms.json'"
check "중단 뒤 다시 기다렸다가 재시도했다 (running 이 2번 이상)" test "$(grep -c 'running:' "$B/out.txt")" -ge 2

B="$(mkbench nojs)"; rm -f "$B/bench_rooms.js"; echo 0 > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq"
check "bench_rooms.js 가 없으면 skipped 로 기록하고 종료코드 0" bash -c "test \"\$(cat '$B/rc')\" = 0 && grep -q '\"state\":\"skipped\"' '$B/data/bench_state.json'"

B="$(mkbench fail)"; echo 0 > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq" BENCH_FAIL=1
check "시험이 실패하면 failed 로 기록, 어느 파일인지 남기고 종료코드 1" bash -c "test \"\$(cat '$B/rc')\" = 1 && grep -q '\"state\":\"failed\"' '$B/data/bench_state.json' && grep -q 'bench_3rooms.json' '$B/data/bench_state.json'"

B="$(mkbench giveup)"; echo 5 > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq" GIVE_UP_S=2
check "계속 접속자가 있으면 GIVE_UP_S 뒤 포기하고 failed" bash -c "test \"\$(cat '$B/rc')\" = 1 && grep -q '기다리다 포기' '$B/data/bench_state.json'"

B="$(mkbench down)"; echo down > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq" GIVE_UP_S=2
check "/health 를 못 읽으면(서버 죽음) 시작하지 않는다" bash -c "test \"\$(cat '$B/rc')\" = 1 && test ! -e '$B/data/bench_3rooms.json'"

B="$(mkbench inject)"; echo 0 > "$B/seq"
run_bench "$B" HEALTH_SEQ="$B/seq" PLAN='1:2:bench_a.json 1:2:bench_b.json'
check "PLAN 으로 단계 목록을 바꿀 수 있다" bash -c "test -s '$B/data/bench_a.json' && test -s '$B/data/bench_b.json'"

printf '\n== 결과: 통과 %d · 실패 %d (load %s)\n' "$PASS" "$FAIL" "$(cut -d' ' -f1 /proc/loadavg)"
[ "$FAIL" -eq 0 ]
