# 클랜 내전판 조합 통계(clan_meta.json) — 프로경기 meta.json과 같은 개념·다른 규모.
# 소표본이므로 전 지표에 베이지안 수축: shrunk = (w + 0.5K) / (n + K).
import openpyxl, collections, json, sys, datetime
WB=sys.argv[1] if len(sys.argv)>1 else "/tmp/aied/squad_sheet.xlsx"
K_BASE, K_PAIR, MIN_PAIR = 30, 20, 5
wb=openpyxl.load_workbook(WB, read_only=True)
rs=list(wb["CLASSIC_NORMAL"].values); ix={n:i for i,n in enumerate(rs[0]) if n}
def nc(s): return str(s or "").replace(" ","").strip()
games=collections.defaultdict(dict)
base=collections.defaultdict(lambda:[0,0])          # 챔프 → [판,승]
posn=collections.defaultdict(collections.Counter)   # 챔프 → 포지션 판수
for r in rs[1:]:
    res=str(r[ix['결과']] if ix['결과']<len(r) else '')
    if res not in ("승리","패배"): continue
    gid=r[ix['게임ID']] if '게임ID' in ix else r[0]
    team=str(r[ix['진영']] or ''); pos=str(r[ix['포지션']] or ''); ch=nc(r[ix['챔피언']])
    if not ch: continue
    base[ch][0]+=1; base[ch][1]+=(res=="승리")
    if pos in ("탑","정글","미드","원딜","서폿"): posn[ch][pos]+=1
    if team in ("블루팀","레드팀") and pos in ("탑","정글","미드","원딜","서폿"):
        games[gid][(team,pos)]=(ch,res=="승리")
def shrunk(w,n,K): return (w+0.5*K)/(n+K)
# 카운터(포지션별, 방향 있음: a가 b를 상대로 이긴 비율)
cnt=collections.defaultdict(lambda:[0,0])   # (pos,a,b) → [판, a승]
for g in games.values():
    for pos in ("탑","정글","미드","원딜","서폿"):
        b=g.get(("블루팀",pos)); r=g.get(("레드팀",pos))
        if not b or not r or b[0]==r[0]: continue
        cnt[(pos,b[0],r[0])][0]+=1; cnt[(pos,b[0],r[0])][1]+=b[1]
        cnt[(pos,r[0],b[0])][0]+=1; cnt[(pos,r[0],b[0])][1]+=r[1]
counter=collections.defaultdict(dict)
for (pos,a,b),(n,w) in cnt.items():
    if n>=MIN_PAIR:
        counter[pos].setdefault(a,{})[b]=[round(shrunk(w,n,K_PAIR),4), n]
# 시너지(같은 팀 2챔프 승률)
sy=collections.defaultdict(lambda:[0,0])
for g in games.values():
    for team in ("블루팀","레드팀"):
        es=[v for (t,p),v in g.items() if t==team]
        for i in range(len(es)):
            for j in range(i+1,len(es)):
                k="|".join(sorted([es[i][0],es[j][0]]))
                sy[k][0]+=1; sy[k][1]+=es[i][1]
synergy={k:[round(shrunk(w,n,K_PAIR),4),n] for k,(n,w) in sy.items() if n>=MIN_PAIR}
champions=[{"name":c,"n":n,"wr":round(shrunk(w,n,K_BASE),4),
            "positions":{p:v for p,v in posn[c].most_common() if v>=3}}
           for c,(n,w) in base.items() if n>=10]
out={"generated":str(datetime.date.today()),"source":"CLASSIC_NORMAL","n_games":len(games),
     "shrink":{"base":K_BASE,"pair":K_PAIR,"min_pair":MIN_PAIR},
     "note":"클랜 내전 실측 조합 통계 — 값은 수축 승률(소표본 보정), [승률, 판수] 쌍. 팀 승패 기반이라 개인 상성 단정 금지.",
     "champions":champions,"counter":counter,"synergy":synergy}
OUT=sys.argv[2] if len(sys.argv)>2 else "clan_meta.json"
json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False)
print("게임",len(games),"챔프",len(champions),"카운터쌍",sum(len(v2) for v in counter.values() for v2 in v.values()),"시너지쌍",len(synergy))
