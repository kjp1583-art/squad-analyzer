# -*- coding: utf-8 -*-
"""🎲 로비 안내 뒤 클랜 정보 한 줄 시험 (사장님 2026-10-19 「지난주 기준 · 1234(소식·기록·팁·방 맞춤) 전부 랜덤」)
분석기에서 해당 구역 소스만 떼어 실행한다(롤 클라이언트·tk 없이).
  A. 지난주 소식 후보가 실제 data/weekly_review.json 에서 나온다(출석왕·MVP·붐비는 요일…) · 전부 70자 이하
  B. 방 맞춤: 방에 있는 사람이 지난주 상위일 때만 나온다 · 없는 사람 이름은 안 나온다
  C. 갈래가 무작위(여러 번 돌리면 소식·기록·팁·맞춤이 다 나온다) · 데이터가 없으면 팁만(빈 줄 없음)
  D. 안내 문장 앞부분(마크·버전)은 그대로 — 중복 방지가 쓰는 시작 문자열 불변 · 한 줄이 비면 안내만
  E. 설정 lobby_fun=false 면 한 줄이 안 붙는다(전송 코드가 옵션을 읽는다) · 설정 창에 체크박스·저장 키
  F. 지난주 라벨만 쓴다(「이번 주」 문구 없음)"""
import json, os, random, re, sys, types
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
src = open(os.path.join(ROOT, 'desktop', 'squad_analyzer.py'), encoding='utf-8').read()
a = src.index('def _lobby_intro_text'); b = src.index('def _lobby_intro_ready')
seg = src[a:b]
fails = []
def ok(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
WK = json.load(open(os.path.join(ROOT, 'data', 'weekly_review.json'), encoding='utf-8'))
def env(weekly=WK, meta=None):
    g = {'random': random, 'time': __import__('time'), 'CURRENT_VERSION': '83.99', 'LOBBY_INTRO_MARK': '스쿼드해체분석기',
         '_clanstat_meta': lambda: meta, 'APP_CONFIG': {}}
    class R:
        def __init__(s, d): s.d = d
        status_code = 200
        def json(s): return s.d
    g['requests'] = types.SimpleNamespace(get=lambda *a, **k: R(weekly))
    exec(seg, g); return g
g = env(meta={'n_games': 2104, 'champions': [{'name': '오른', 'n': 242}, {'name': '진', 'n': 100}]})
wk = g['_lobby_fun_week_lines'](WK)
ok(len(wk) >= 6 and all('지난주' in x for x in wk), 'A 지난주 소식 후보 %d개 — 전부 「지난주」 표기 (%s)' % (len(wk), wk[:2]))
ok(any('출석왕' in x for x in wk) and any('붐볐' in x for x in wk) and any('MVP' in x for x in wk), 'A 출석왕·붐비는 요일·MVP 최다가 들어 있다')
ok(all(len(x) <= g['LOBBY_FUN_MAX'] for x in wk + g['_lobby_fun_clan_lines']() + g['LOBBY_TIPS']), 'A 모든 후보가 %d자 이하' % g['LOBBY_FUN_MAX'])
top = WK['stats']['sr']['top'][0][0]
mem = g['_lobby_fun_member_lines'](WK, [top + '#KR1', '아무개#X'])
ok(len(mem) >= 1 and top in mem[0] and not any('아무개' in x for x in mem), 'B 방에 지난주 상위자가 있으면 그 사람 한 줄만 (%s)' % mem[:1])
ok(g['_lobby_fun_member_lines'](WK, ['아무개#X']) == [], 'B 방에 상위자가 없으면 맞춤 갈래는 비어 있다')
seen = set()
for i in range(400):
    random.seed(i); l = g['_lobby_fun_line']([top])
    if l.startswith('💡'): seen.add('팁')
    elif l.startswith('📚'): seen.add('기록')
    elif l.startswith('👋'): seen.add('맞춤')
    elif l.startswith('📅') or l[:1] in '🏅🎯🚫❄🍗🌟🔥🏆': seen.add('소식')
ok(seen == {'팁', '기록', '맞춤', '소식'}, 'C 400번 돌리면 네 갈래가 다 나온다 %s' % sorted(seen))
g2 = env(weekly=None, meta=None)
l = g2['_lobby_fun_line']([top])
ok(l.startswith('💡'), 'C 주간·클랜 데이터를 못 받으면 팁으로 대신 (%s)' % l[:20])
g3 = env(weekly={'placeholder': True, 'stats': {}}, meta=None)
ok(g3['_lobby_fun_line']([]).startswith('💡'), 'C 깡통(placeholder) 주간 데이터는 쓰지 않는다')
t0 = g['_lobby_intro_text'](); t1 = g['_lobby_intro_text']('💡 팁')
ok(t1.startswith(t0) and t1 == t0 + ' · 💡 팁' and t0.startswith('[스쿼드해체분석기 v83.99]'), 'D 안내 앞부분·시작 문자열 불변, 한 줄은 뒤에만')
ok(g['_lobby_intro_text']('') == t0, 'D 한 줄이 비면 안내만')
ok('이번 주' not in ' '.join(wk + g['_lobby_fun_clan_lines']() + g['LOBBY_TIPS']), 'F 「이번 주」 표기 없음')
ok('APP_CONFIG.get("lobby_fun", True)' in src and 'self.var_lf' in src and 'APP_CONFIG["lobby_fun"] = bool(self.var_lf.get())' in src, 'E 전송 코드가 lobby_fun 옵션을 읽고 · 설정 창에 체크박스 · 저장 키')
ok('_lobby_fun_line(names)' in src and "args=(headers, base_url, lobby_key, _irank, [" in src, 'E 방 인원 이름이 전송 스레드로 넘어간다')
print('\n전부 통과' if not fails else '\n실패 %d건' % len(fails)); sys.exit(1 if fails else 0)
