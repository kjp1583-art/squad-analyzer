#!/usr/bin/env python3
"""🔨 밴픽 코치 추천이 실제로 맞았는지 사후 채점한다(2026-08-03 사장님 지시).

왜 필요한가: 오추천은 지금까지 전부 사장님이 눈으로 보고 제보해서 발견됐다
(2026-08-02 녹턴 — 이미 픽을 확정한 상대의 챔프폭, 2026-08-03 브라이어 — 포지션 불일치).
제보를 기다리는 대신 숫자로 보면, 고칠 곳을 데이터가 먼저 짚어준다.

어떻게 채점하나 — 밴한 챔프는 그 판에 나올 수 없으니 '추천이 옳았는지'를 직접 확인할 수 없다.
그래서 **추천했지만 밴하지 않은 챔프**만 본다. 이건 자연 실험이다:
  · 그 챔프가 실제로 그 판에 나왔다  → 위협 판단이 맞았다(밴했으면 값어치가 있었을 픽)
  · 아무도 안 꺼냈다                → 헛방(그 밴은 낭비였을 것)
반대 방향도 본다 — 상대가 실제로 꺼낸 챔프 중 추천 목록이 몇 %를 미리 짚었나(커버리지).

한계는 정직하게: 밴하지 않은 챔프는 '상대가 그 챔프를 쓸 수 있었다'는 사실만 알려주고,
안 꺼낸 이유(애초에 생각이 없었는지, 다른 자리로 갔는지)까지는 기록에 남지 않는다.
"""
import collections, datetime, re, sys

MATCH_WINDOW_H = 3.0     # 추천 시각 이후 이 시간 안에 시작된 그 사람의 판을 같은 판으로 본다
MIN_N = 5                # 이보다 표본이 적으면 비율을 말하지 않는다


def _norm(s):
    return "".join(str(s or "").split("#")[0].split()).lower()


def _dt(s):
    s = str(s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(s[:19], f)
        except ValueError: continue
    return None


def load(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for tab in ("COACH_LOG", "CLASSIC_NORMAL"):
        rows = list(wb[tab].values)
        head = [str(c or "").strip() for c in rows[0]]
        out[tab] = (head, rows[1:])
    return out


def audit(data):
    (ch, crows) = data["COACH_LOG"]
    (gh, grows) = data["CLASSIC_NORMAL"]
    ci = {c: i for i, c in enumerate(ch)}
    gi = {c: i for i, c in enumerate(gh)}
    g = lambda r, i: (r[i] if i is not None and len(r) > i else None)

    # 게임 인덱스: (정규화닉) → [(시각, 게임ID, 진영)], 그리고 게임ID → 참가자
    played, game = collections.defaultdict(list), collections.defaultdict(list)
    for r in grows:
        gid, day = g(r, gi.get("게임ID")), _dt(g(r, gi.get("날짜")))
        nm, side = g(r, gi.get("소환사명")), g(r, gi.get("진영"))
        if not gid or not nm: continue
        game[gid].append({"nm": nm, "side": side, "champ": str(g(r, gi.get("챔피언")) or "").strip(),
                          "pos": str(g(r, gi.get("포지션")) or "").strip(),
                          "ban": str(g(r, gi.get("밴")) or "").strip()})
        if day: played[_norm(nm)].append((day, gid))
    for k in played: played[k].sort()

    st = {"ban_rows": 0, "matched": 0, "unbanned": 0, "hit": 0,
          "enemy_champs": 0, "covered": 0, "pick_rows": 0, "pick_follow": 0}
    misses, hits = collections.Counter(), collections.Counter()
    per_person = collections.defaultdict(lambda: [0, 0])

    for r in crows:
        mode = str(g(r, ci.get("모드")) or "").strip()
        who = g(r, ci.get("닉네임"))
        rec = [x.strip() for x in str(g(r, ci.get("추천")) or "").split(",") if x.strip()]
        actual = str(g(r, ci.get("실제선택")) or "").strip()
        ts = _dt(g(r, ci.get("시각")))
        if mode == "pick":
            st["pick_rows"] += 1
            try:
                if float(g(r, ci.get("따름순위")) or 0) > 0: st["pick_follow"] += 1
            except (TypeError, ValueError): pass
            continue
        if mode != "ban" or not rec or not ts: continue
        st["ban_rows"] += 1

        # 그 사람이 추천 직후에 실제로 뛴 판 찾기
        gid = None
        for day, _gid in played.get(_norm(who), []):
            d = (day - ts).total_seconds() / 3600.0
            if -0.5 <= d <= MATCH_WINDOW_H: gid = _gid; break
        if not gid: continue
        st["matched"] += 1

        me = next((p for p in game[gid] if _norm(p["nm"]) == _norm(who)), None)
        if not me: continue
        enemy = [p for p in game[gid] if p["side"] and p["side"] != me["side"]]
        enemy_champs = {p["champ"] for p in enemy if p["champ"]}

        # ① 추천했지만 밴하지 않은 챔프 — 실제로 상대가 꺼냈나
        for c in rec:
            if c == actual: continue          # 밴해버렸으면 나올 수 없다 — 채점 대상 아님
            st["unbanned"] += 1
            if c in enemy_champs:
                st["hit"] += 1; hits[c] += 1; per_person[who][0] += 1
            else:
                misses[c] += 1
            per_person[who][1] += 1

        # ② 상대가 실제로 꺼낸 챔프를 추천이 미리 짚었나(커버리지)
        for c in enemy_champs:
            st["enemy_champs"] += 1
            if c in rec: st["covered"] += 1

    return st, misses, hits, per_person


def report(st, misses, hits, per_person):
    L = ["# 🔨 밴픽 코치 추천 채점", ""]
    L.append(f"밴 추천 기록 {st['ban_rows']}건 · 그중 경기와 이어붙인 것 {st['matched']}건")
    if st["unbanned"] >= MIN_N:
        pct = 100.0 * st["hit"] / st["unbanned"]
        L.append(f"- **위협 적중률 {pct:.0f}%** — 추천했지만 밴하지 않은 챔프 {st['unbanned']}개 중 "
                 f"{st['hit']}개가 실제로 상대에게서 나왔어요")
        L.append(f"  (밴한 챔프는 나올 수 없으니 채점에서 뺐습니다 — 그래야 '맞췄다'가 공짜로 안 나옵니다)")
    else:
        L.append(f"- 위협 적중률: 표본 부족({st['unbanned']}개) — {MIN_N}개는 모여야 말할 수 있어요")
    if st["enemy_champs"] >= MIN_N:
        pct = 100.0 * st["covered"] / st["enemy_champs"]
        L.append(f"- **커버리지 {pct:.0f}%** — 상대가 실제로 꺼낸 챔프 {st['enemy_champs']}개 중 "
                 f"{st['covered']}개를 추천이 미리 짚었어요")
    if st["pick_rows"]:
        L.append(f"- 픽 추천 채택률 {100.0*st['pick_follow']/st['pick_rows']:.0f}% "
                 f"({st['pick_follow']}/{st['pick_rows']}건 — 추천 안에서 골랐다)")
    if hits:
        L += ["", "### 잘 짚은 챔프 (밴 안 했더니 실제로 나옴)"]
        L += [f"- {c} {n}회" for c, n in hits.most_common(8)]
    if misses:
        L += ["", "### 헛방이 잦은 챔프 (추천했는데 그 판에 아무도 안 꺼냄)"]
        L += [f"- {c} {n}회" for c, n in misses.most_common(10)]
        L.append("-# 여기 위쪽이 오추천 후보예요 — 포지션이 안 맞거나 이미 픽이 끝난 상대의 챔프폭일 수 있습니다")
    ranked = [(w, h, n) for w, (h, n) in per_person.items() if n >= MIN_N]
    if ranked:
        ranked.sort(key=lambda x: -x[1] / x[2])
        L += ["", "### 사용자별 (표본 5개 이상)"]
        L += [f"- {w} — {100.0*h/n:.0f}% ({h}/{n})" for w, h, n in ranked[:8]]
    return "\n".join(L)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "squad_sheet.xlsx"
    st, misses, hits, per_person = audit(load(path))
    txt = report(st, misses, hits, per_person)
    print(txt)
    try:
        open("coach_audit.md", "w", encoding="utf-8").write(txt + "\n")
    except Exception: pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
