"""docs/brjhunt_audio_sfx_names.md 를 brjhunt_audio.js 에서 다시 뽑는다(효과음을 더하거나 바꾼 뒤).
사용: CHROME=<크로미움> python3.13 tooling/brjhunt_audio_gen_names.py brjhunt_audio.js(절대경로) docs/brjhunt_audio_sfx_names.md
※ 「이벤트 → 효과음 권장표」는 이 파일 안 표(T)를 고친다. 시험(tests/brjhunt_audio_test.py)이 문서와 실제 이름이 같은지 본다."""
import os, sys, json, tempfile
from playwright.sync_api import sync_playwright
JS=sys.argv[1]; OUT=sys.argv[2]
PG=os.path.join(tempfile.mkdtemp(prefix='brjaudio_'),'p.html')
open(PG,'w').write('<!doctype html><meta charset=utf-8><body><script src="file://%s"></script></body>'%JS)
with sync_playwright() as p:
    br=p.chromium.launch(executable_path=os.environ['CHROME']); pg=br.new_page()
    pg.goto('file://'+PG)
    info=pg.evaluate("BrjAudio.sfxNames().map(n=>BrjAudio.sfxInfo(n))")
    tr=pg.evaluate("BrjAudio.trackNames().map(n=>[n,BrjAudio._trackInfo(n)])")
    br.close()
G={
'휘두름(공격 모션)':[('swing1','swing2','swing3'),'기본 공격 콤보 1·2·3타 — 스윙 시작 순간(타격 전)에 한 번씩. `swing_big` 은 스킬/강공격 휘두름.'],
}
rows=[]
rows.append("# 브장신 사냥터 소리 v2 — 효과음 이름표\n")
rows.append("`brjhunt_audio.js` v2 (외부 음원 없이 Web Audio 합성). 부르는 법: `BrjAudio.sfx('이름', {vol, rate, pan, x, dist})`.\n")
rows.append("- `vol` 0~2 음량 배수 · `rate` 음높이 배수(0.25~4) · `pan` -1(왼)~1(오) 또는 `x` 화면 속 위치 -1~1(플레이어 기준 몬스터 위치를 넣으면 알아서 좌우로) · `dist` 0~1(멀수록 작고 둔탁)")
rows.append("- 같은 이름을 연타해도 **소리마다 변형(표의 「변형」 칸)이 돌아가고 음높이·음량·좌우가 조금씩 달라서** 기계처럼 들리지 않는다. 같은 이름 최소 간격(`gap`)보다 빨리 부르면 새 소리는 버려지니(일부러), 마리 수가 많아도 소리가 뭉개지지 않는다.")
rows.append("- 동시 발음 상한: 일반 10 · 스킬 16 · 중요 24 (넘치면 새 소리를 버림). 우선순위 `p`: 0 일반 · 1 스킬 · 2 중요.")
rows.append("- 스킬 10종(`slash peck spin bomb thunder fire egg shield shrimp storm`)은 각각 **전조(`_charge`) · 발동(이름 그대로) · 여운(`_tail`)** 3개. `BrjAudio.skillSfx(id,'charge'|'cast'|'tail')` 가 이름을 돌려준다.")
rows.append("- 예전 이름(`hit crit kill coin levelup boss_in boss_win boss_lose click tab error summon summon_rare enhance_ok enhance_fail awaken skill_<id>`)은 **그대로 살아 있다** — 기존 호출은 수정 없이 더 묵직한 소리로 바뀐다.\n")
rows.append("## 이벤트 → 효과음 권장표 (UI 담당용)\n")
rows.append("| 사건 | 효과음 | 메모 |\n|---|---|---|")
T=[
("기본 공격 1·2·3타 시작","`swing1` `swing2` `swing3`","콤보 순서대로. 3타는 묵직함"),
("기본 공격이 몬스터에 맞음","`hit`","한 마리 맞을 때마다. 여러 마리 동시면 가장 가까운 한 마리만(최소 간격이 알아서 솎음). `x` 에 몬스터 상대 위치"),
("크리티컬로 맞음","`crit`","`hit` 대신(겹치지 않게)"),
("스킬·강공격이 맞음","`hit_heavy`","스킬 발동음과 함께 쓰면 타격감이 산다"),
("몬스터가 맞고 아파함","`mon_hurt`","선택. `hit` 위에 얇게"),
("몬스터 처치(일반)","`mon_die` + 코인이면 `coin_drop`","처치 숫자가 많으면 `kill` 로 가볍게 대체 가능"),
("엘리트 등장 / 처치","`elite_spawn` / `mon_die_elite`",""),
("코인 먹음(자석 흡수)","`coin`","연속으로 먹으면 `{rate: 1+0.04*n}` 처럼 음높이를 올리면 좋다. 한꺼번에 많이면 `coin_big`"),
("바닥에 코인 떨어짐","`coin_drop`",""),
("아이템/드랍 줍기","`pickup`",""),
("점프 / 2단 점프","`jump` / `jump2`",""),
("착지","`land`(작게) / `land_hard`(높은 데서)","낙하 속도가 크면 hard"),
("↓+점프로 아래 발판","`drop_down`",""),
("달리기 발소리","`step`","걸음마다(0.12~0.2초). 변형 4종이 돌아가며 나옴. `vol: 0.6` 권장"),
("플레이어 피격","`hurt` (큰 피해는 `hurt_heavy`)","무적 시간 동안 연속 호출해도 최소 간격이 솎음"),
("방어/방패 막음","`shield_block`",""),
("플레이어 사망 / 부활","`die` / `revive`",""),
("스킬 시전 시작(캐스트 바)","`skill_<id>_charge`","전조 — cast 시간이 있는 스킬에만"),
("스킬 발동","`skill_<id>`","휘두름+타격 층 포함"),
("스킬 효과가 남음(장판·잔불)","`skill_<id>_tail`","발동 직후 한 번"),
("MP 부족 / 쿨다운 안 끝남","`no_mp`","스킬 키를 눌렀는데 못 쓸 때"),
("쿨다운 끝남(선택)","`skill_ready`","작게. 너무 자주 나오면 생략"),
("콤보 5·10·25 … 달성","`combo_up` + `{rate:1+0.05*(콤보/5)}`",""),
("레벨업","`levelup`",""),
("각성 / 환생 / 큰 연출","`awaken`",""),
("AUTO 켜기 / 끄기","`auto_on` / `auto_off`",""),
("버튼 클릭 / 탭 바꿈","`click` / `tab`",""),
("창 열기 / 닫기","`ui_open` / `ui_close`",""),
("장비 착용","`equip`",""),
("강화 성공 / 실패","`enhance_ok` / `enhance_fail`",""),
("소환 / 희귀 소환","`summon` / `summon_rare`",""),
("에러·모자람 안내","`error`",""),
("보스 입장","`boss_in`","BGM 은 `bgm('boss')`"),
("보스 공격 예고(빨간 경고)","`boss_warn`",""),
("보스 내려찍기 / 큰 한방","`boss_slam`",""),
("보스 격노","`boss_rage`",""),
("보스 처치 연출(슬로모션)","`boss_die`","이어서 `boss_win`"),
("보스전 승리 / 패배","`boss_win` / `boss_lose`",""),
]
for a,b,c in T: rows.append("| %s | %s | %s |"%(a,b,c))
rows.append("\n## BGM\n")
rows.append("`BrjAudio.bgm('field1'..'field6'|'boss'|'menu'|null)` — 지역 1~6(합정 골목·bhc·홍대·상수·망원·한강)에 맞춰 `field<지역번호>`, 보스/도전 던전은 `boss`, 로그인·메뉴 화면은 `menu`.")
rows.append("`BrjAudio.setIntensity(0~1)` — 전투 강도. 몬스터가 많이 몰리거나 콤보가 높으면 올리고(예: `min(1, 0.5 + 콤보/40)`), 가만히 있으면 내린다. 0.2 이하 = 패드·베이스만 / 0.3 하이햇 / 0.45 킥·스네어 / 0.6 아르페지오 / 0.75 리드 / 0.9↑ 심벌·라이저. 기본 0.9. 보스곡은 +0.25 보정이라 항상 빽빽하다.")
rows.append("\n| 트랙 | BPM | 조 | 베이스 | 패드 | 아르페지오 | 리드 | 드럼 |\n|---|---|---|---|---|---|---|---|")
ROOT=['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
for n,t in tr:
    rows.append("| `%s` | %d | %s %s | %s | %s | %s | %s | %s/%s/%s |"%(n,t['bpm'],ROOT[t['root']%12],t['sc'],t['bass'],t['pad'],t['arp'],t['lead'],t['kit']['k'],t['kit']['s'],t['kit']['h']))
rows.append("\n## 전체 효과음 목록 (%d개)\n"%len(info))
rows.append("| 이름 | 길이(초) | 우선순위 | 최소 간격(초) | 변형 |\n|---|---|---|---|---|")
for i in info: rows.append("| `%s` | %.2f | %d | %.3f | %d |"%(i['name'],i['dur'],i['priority'],i['gap'],i['variants']))
open(OUT,'w').write("\n".join(rows)+"\n")
print(len(info))
