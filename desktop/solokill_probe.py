# -*- coding: utf-8 -*-
# 🔎 솔킬 데이터 소스 확인 프로브 — LCU가 최근 게임에 soloKills(challenges)를 주는지 검사
# 사용: League Client 켜둔 상태(가능하면 방금 내전 한 판 끝낸 뒤)에서  py solokill_probe.py
#       (requests 없으면  py -m pip install requests urllib3)
# 이 출력 전체를 복사해서 알려주면, 솔킬 가산을 붙일 수 있는지/어느 소스로 붙일지 확정합니다.
import base64, json, os, requests, urllib3
urllib3.disable_warnings()

def find_lockfile():
    cands=[]
    meta=os.path.join(os.environ.get("ProgramData",r"C:\ProgramData"),"Riot Games","RiotClientInstalls.json")
    try:
        if os.path.exists(meta):
            j=json.load(open(meta,encoding="utf-8"))
            for k in (j.get("associated_client") or {}): cands.append(os.path.normpath(k))
    except Exception: pass
    for d in "CDEFG": cands.append(f"{d}:\\Riot Games\\League of Legends")
    for b in cands:
        lf=os.path.join(b,"lockfile")
        if os.path.exists(lf): return lf
    return None

def lcu():
    lf=find_lockfile()
    if not lf: return None
    parts=open(lf).read().split(":")
    tok=base64.b64encode(("riot:"+parts[3]).encode()).decode()
    return f"https://127.0.0.1:{parts[2]}", {"Authorization":"Basic "+tok,"Accept":"application/json"}

def scan(label, txt, j):
    has_ch = '"challenges"' in txt
    has_sk = 'soloKills' in txt or 'SOLO_KILLS' in txt
    print(f"  [{label}] challenges 포함={has_ch}  soloKills 포함={has_sk}")
    try:
        parts = (j.get('participants') if isinstance(j,dict) else None) or []
        if not parts and isinstance(j,dict):
            games=(j.get('games') or {}).get('games') if isinstance(j.get('games'),dict) else None
            if games: parts=(games[0].get('participants') or [])
        if parts:
            p0=parts[0]; st=p0.get('stats', p0)
            print(f"    참가자[0] stats 키(앞10): {list(st.keys())[:10] if isinstance(st,dict) else '?'}")
            ch = (st.get('challenges') if isinstance(st,dict) else None) or p0.get('challenges')
            print(f"    참가자[0] challenges: {('있음, soloKills='+str(ch.get('soloKills')) if isinstance(ch,dict) else '없음')}")
    except Exception as e:
        print("    (구조파싱 오류)", e)

def main():
    L=lcu()
    if not L: print("League Client 미탐지 — 클라이언트 켜져있나요?"); return
    base,h=L
    print("=== 1) eog-stats-block (종료화면 있을 때만 응답) ===")
    try:
        r=requests.get(base+"/lol-end-of-game/v1/eog-stats-block",headers=h,verify=False,timeout=4)
        print("  HTTP",r.status_code)
        if r.ok: scan("eog", r.text, r.json())
    except Exception as e: print("  err",e)
    print("=== 2) 최근 매치 1건 (지속됨 — 아무때나) ===")
    try:
        r=requests.get(base+"/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=1",headers=h,verify=False,timeout=6)
        print("  HTTP",r.status_code)
        if r.ok: scan("match-history", r.text, r.json())
    except Exception as e: print("  err",e)

if __name__=="__main__": main()
