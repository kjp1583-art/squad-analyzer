#!/usr/bin/env python3
"""패치노트를 디스코드 패치노트 채널로 발송한다.

분석기 릴리스 워크플로가 빌드 성공 후 자동 호출하고, patch-note 워크플로도 같은 코드를 쓴다.
(예전엔 patch-note 쪽에 파이썬이 인라인으로 박혀 있어서, 릴리스만 하고 발송을 잊는 일이 반복됐다.)

입력(환경변수): IN_VER / IN_ANALYZER / IN_WEB / IN_BOT — 채워진 칸만 임베드에 실린다.

📝 작성 원칙: 클랜원 누구나 읽고 바로 이해할 수 있게.
  · 무엇이 달라졌는지 + 그래서 뭐가 좋아지는지, 한 줄에 하나씩
  · 파일명·함수명·API 이름 금지
  · 버전 번호는 헤더에만
"""
import base64, datetime, json, os, re, sys, urllib.request


def _clean(s):
    """줄머리 불릿을 통일하고 빈 줄을 없앤다."""
    out = []
    for line in (s or "").replace("\\n", "\n").splitlines():
        t = line.strip().lstrip("-·*").strip()
        if t: out.append("· " + t)
    return "\n".join(out)


def main():
    raw = os.environ.get("APP_SECRETS_B64", "")
    if not raw:
        print("APP_SECRETS_B64 시크릿 없음", file=sys.stderr); return 1
    src = base64.b64decode(re.sub(r"\s", "", raw)).decode("utf-8", "replace")
    m = re.search(r'^\s*PATCH_WEBHOOK_URL\s*=\s*["\']([^"\']+)["\']', src, re.M)
    if not m:
        print("app_secrets.py에 PATCH_WEBHOOK_URL 없음", file=sys.stderr); return 1
    url = m.group(1)

    ver = (os.environ.get("IN_VER") or "").strip().lstrip("vV")
    fields = []
    a = _clean(os.environ.get("IN_ANALYZER"))
    if a: fields.append({"name": f"🖥️ 분석기{f' (v{ver})' if ver else ''}", "value": a[:1024], "inline": False})
    w = _clean(os.environ.get("IN_WEB"))
    if w: fields.append({"name": "🌐 웹 (squad.gg)", "value": w[:1024], "inline": False})
    b = _clean(os.environ.get("IN_BOT"))
    if b: fields.append({"name": "🤖 내전봇", "value": b[:1024], "inline": False})
    if not fields:
        print("보낼 내용이 없습니다 — 최소 한 칸은 채워주세요", file=sys.stderr); return 1

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    foot = []
    if a: foot.append("분석기는 껐다 켜면 자동 업데이트돼요")
    if w: foot.append("웹은 새로고침하면 바로 적용")
    if b: foot.append("봇은 따로 하실 것 없어요")

    payload = {"content": "🔔 　**스쿼드 업데이트 안내**",
               "embeds": [{"title": f"📋 {today} 패치노트", "color": 0x5A9BD5,
                           "fields": fields, "footer": {"text": " · ".join(foot)}}]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "squad-ci"})
    with urllib.request.urlopen(req, timeout=20) as r:
        print("발송 완료:", r.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
