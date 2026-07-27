# -*- coding: utf-8 -*-
# 🎮 롤 로비 자동초대 테스터 (분석기 정식통합 전, LCU 초대 계약 확정용)
# ─────────────────────────────────────────────────────────────────────────
# 사용법:
#   1) League Client 켜고 '사용자 지정 게임' 로비를 직접 만든다(=당신이 로비 호스트).
#   2) 디스코드에서 당신 계정으로 /연동 (롤닉#태그) 돼 있어야 함(요청자 매칭).
#   3) 이 스크립트 실행:  py lobby_inviter_test.py     (requests 필요: pip install requests urllib3)
#   4) 디스코드 진행판에서 '팀초대' 버튼을 당신(=참가중)이 누른다.
#   5) 이 콘솔 로그를 그대로 복사해서 알려주면, 실제 초대되는 LCU 호출을 확정해 분석기에 넣습니다.
# ─────────────────────────────────────────────────────────────────────────
import time, base64, json, os
import requests, urllib3
urllib3.disable_warnings()

BRIDGE_URL = "http://fi15.bot-hosting.net:27116/invites"   # 봇 초대 브릿지(공개포트)
POLL_SEC   = 4

def _norm(s):   # 롤닉#태그 느슨한 매칭(공백제거·소문자)
    return (s or "").replace(" ", "").strip().lower()

def _find_lockfile():
    cands = []
    meta = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Riot Games", "RiotClientInstalls.json")
    try:
        if os.path.exists(meta):
            j = json.load(open(meta, encoding="utf-8"))
            for k in (j.get("associated_client") or {}):
                cands.append(os.path.normpath(k))
    except Exception:
        pass
    for d in "CDEFG":
        cands.append(f"{d}:\\Riot Games\\League of Legends")
    for base in cands:
        lf = os.path.join(base, "lockfile")
        if os.path.exists(lf):
            return lf
    return None

def _lcu():
    lf = _find_lockfile()
    if not lf:
        return None
    try:
        parts = open(lf).read().split(":")   # name:pid:port:password:protocol
        port, pw = parts[2], parts[3]
    except Exception:
        return None
    tok = base64.b64encode(("riot:" + pw).encode()).decode()
    h = {"Authorization": "Basic " + tok, "Accept": "application/json", "Content-Type": "application/json"}
    return f"https://127.0.0.1:{port}", h

def _get(base, h, path, t=3):
    return requests.get(base + path, headers=h, verify=False, timeout=t)

def current_riot_id(base, h):
    try:
        j = _get(base, h, "/lol-summoner/v1/current-summoner").json()
        gn = j.get("gameName") or j.get("displayName")
        tl = j.get("tagLine")
        return (f"{gn}#{tl}" if tl else gn), j.get("summonerId"), j.get("puuid")
    except Exception as e:
        return None, None, None

def resolve(base, h, riot_id):
    """롤닉#태그 → (summonerId, puuid). 여러 LCU 경로 시도하며 무엇이 되는지 로그."""
    gn, tl = (riot_id.rsplit("#", 1) + [None])[:2] if "#" in riot_id else (riot_id, None)
    # 경로 A: alias/lookup → puuid → summoner
    if tl:
        try:
            r = _get(base, h, f"/lol-summoner/v1/alias/lookup?gameName={gn}&tagLine={tl}")
            print(f"      [A alias/lookup] {r.status_code} {r.text[:120]}")
            if r.ok and r.json().get("puuid"):
                pu = r.json()["puuid"]
                s = _get(base, h, f"/lol-summoner/v2/summoners/puuid/{pu}")
                print(f"      [A summoners/puuid] {s.status_code} {s.text[:120]}")
                if s.ok:
                    return s.json().get("summonerId"), pu
        except Exception as e:
            print(f"      [A err] {e}")
    # 경로 B: aliases(POST)
    if tl:
        try:
            r = requests.post(base + "/lol-summoner/v1/summoners/aliases", headers=h,
                              data=json.dumps([{"gameName": gn, "tagLine": tl}]), verify=False, timeout=3)
            print(f"      [B aliases POST] {r.status_code} {r.text[:160]}")
            if r.ok and isinstance(r.json(), list) and r.json():
                d = r.json()[0]
                return d.get("summonerId"), d.get("puuid")
        except Exception as e:
            print(f"      [B err] {e}")
    # 경로 C: 구형 name 조회
    try:
        r = _get(base, h, f"/lol-summoner/v1/summoners?name={gn}")
        print(f"      [C summoners?name] {r.status_code} {r.text[:120]}")
        if r.ok and isinstance(r.json(), dict) and r.json().get("summonerId"):
            return r.json()["summonerId"], r.json().get("puuid")
    except Exception as e:
        print(f"      [C err] {e}")
    return None, None

def try_invite(base, h, summoner_ids):
    body = [{"toSummonerId": sid} for sid in summoner_ids if sid]
    if not body:
        print("   [초대] 유효 summonerId 0개 → 초대 스킵")
        return
    try:
        r = requests.post(base + "/lol-lobby/v2/lobby/invitations", headers=h,
                          data=json.dumps(body), verify=False, timeout=5)
        print(f"   [초대 POST /lol-lobby/v2/lobby/invitations] {r.status_code} {r.text[:300]}")
    except Exception as e:
        print(f"   [초대 err] {e}")

def main():
    print(f"[inviter] 브릿지 {BRIDGE_URL} 폴링 시작 — League 로비 켜두고 디스코드에서 '팀초대'를 눌러보세요.")
    seen = set()
    while True:
        try:
            L = _lcu()
            if not L:
                print("[inviter] League Client 미탐지(로그인/lockfile 없음) — 클라이언트 켜져있나요?")
                time.sleep(POLL_SEC); continue
            base, h = L
            me, my_sid, my_pu = current_riot_id(base, h)
            try:
                data = requests.get(BRIDGE_URL, timeout=6).json().get("invites", [])
            except Exception as e:
                print(f"[inviter] 브릿지 접속 실패: {e}"); time.sleep(POLL_SEC); continue
            for iv in data:
                if iv["id"] in seen:
                    continue
                if _norm(iv.get("requester")) != _norm(me):
                    continue                         # 내 LCU 소환사 != 요청자 → 내 요청 아님
                seen.add(iv["id"])
                print(f"\n[inviter] ▶ 내 요청 감지! {iv['team']}팀 · 요청자 {iv.get('requester')} · 대상 {len(iv['invitees'])}명 (나={me})")
                sids = []
                for rid in iv["invitees"]:
                    sid, pu = resolve(base, h, rid)
                    print(f"   - {rid} → summonerId={sid} puuid={str(pu)[:16]}")
                    if sid:
                        sids.append(sid)
                try_invite(base, h, sids)
        except Exception as e:
            print(f"[inviter] loop err: {e}")
        time.sleep(POLL_SEC)

if __name__ == "__main__":
    main()
