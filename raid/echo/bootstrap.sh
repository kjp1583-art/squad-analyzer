#!/bin/bash
# 레이드 0단계 — 짧은 시작 스크립트 (2026-10-08)
#
# 쓰는 법: Vultr 서버를 만들 때 「Additional Features」→「Enable Cloud-Init User-Data」 칸에 이 파일 전체를 붙여 넣는다.
#          (provision.sh 는 20KB 가 넘어 붙여 넣다 잘리거나 칸이 길이 제한으로 거부할 수 있다(Vultr 의 한도는 확인 못 함) — 이 파일은 2KB 남짓이다.)
#          서버가 처음 켜질 때 root 로 한 번 실행되어 GitHub 에서 provision.sh 를 받아 그대로 실행한다.
#          받은 스크립트는 root 로 실행되므로 REPO/REF 는 믿을 수 있는 값이어야 한다(기본: 이 프로젝트의 공개 저장소 main).
# 못 받으면: /root/RAID_SETUP_STATUS.txt 에 FAIL 과 이유가 남는다.

REF="${REF:-main}"                         # 받을 git 가지/태그/커밋. 에코 서버가 main 에 합쳐지기 전이면 그 가지 이름
REPO="${REPO:-kjp1583-art/squad-analyzer}"
export HOST="${HOST:-}"                    # 비우면 서버 IP 로 <a-b-c-d>.sslip.io 를 만든다
export RUN_BENCH="${RUN_BENCH:-1}"

ROOT="${ROOT:-}"                           # 시험용(실서버에서는 비워 둔다)
LOG="$ROOT/var/log/raid-provision.log"
STATUS="$ROOT/root/RAID_SETUP_STATUS.txt"
DEST="$ROOT/root/raid-provision.sh"
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS")"

fail() {
  {
    echo "상태: FAIL"
    echo "설명: 설치 스크립트를 받지 못했습니다 — $1"
    echo "시각: $(date -u +%FT%TZ)"
    echo
    echo "주소: https://raw.githubusercontent.com/$REPO/$REF/raid/echo/provision.sh"
    echo "서버를 삭제하고 다시 만들어 보세요(몇 센트). 같은 일이 되풀이되면 이 파일 내용을 채팅에 붙여 주세요."
  } > "$STATUS"
  cat "$STATUS" >> "$LOG"
  exit 1
}

URL="https://raw.githubusercontent.com/$REPO/$REF/raid/echo/provision.sh"
echo "[$(date -u +%FT%TZ)] bootstrap: $URL" >> "$LOG"
curl --fail --silent --show-error --location --retry 6 --retry-delay 5 --retry-all-errors \
  --connect-timeout 10 --max-time 60 "$URL" -o "$DEST" >> "$LOG" 2>&1 || fail "내려받기 실패(주소가 틀렸거나 REF 에 파일이 없음)"
[ "$(head -n 1 "$DEST")" = "#!/bin/bash" ] || fail "받은 파일이 설치 스크립트가 아님(첫 줄이 #!/bin/bash 가 아님)"
bash -n "$DEST" >> "$LOG" 2>&1 || fail "받은 파일의 문법 검사 실패"
export REF REPO
exec bash "$DEST"
