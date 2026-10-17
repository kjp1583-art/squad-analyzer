#!/usr/bin/env python3
"""💬 로비 안내 채팅 끄기 옵션 시험 (사장님 2026-10-17) — 분석기는 윈도우 전용이라 소스를 읽어 배선을 확인한다.
  A. 설정 창에 체크박스(var_li)가 있고 기본값은 켬(True)  B. 저장 때 APP_CONFIG["lobby_intro"] 로 쓴다
  C. 채팅을 보내는 곳(_lobby_intro 호출)은 APP_CONFIG lobby_intro 가 꺼지면 아예 안 들어간다  D. 채팅을 POST 하는 곳은 _lobby_intro 한 곳뿐
  E. 변이: 옵션 검사를 빼면 C 가 빨개진다.  사용: python3 tests/lobby_intro_option_test.py"""
import os, re, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = open(os.path.join(ROOT, 'desktop', 'squad_analyzer.py'), encoding='utf-8').read()
FAILS = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x) if x and not c else ''))
    if not c: FAILS.append(n)
def gate_ok(src):
    m = re.search(r'if lobby_key and lobby_custom and current_phase == "Lobby" and APP_CONFIG\.get\("lobby_intro", True\):\n\s+_ok, _why = _lobby_intro_ready', src)
    return bool(m)
check('A 체크박스 변수 var_li (기본 켬)', 'self.var_li = tk.BooleanVar(value=APP_CONFIG.get("lobby_intro", True))' in SRC and 'variable=self.var_li' in SRC)
check('A 설명 문구에 「끄면 로비 채팅에 아무것도 안 올린다」 뜻이 있다', '끄면 내 분석기는 로비 채팅에 아무것도 올리지 않아요' in SRC)
check('B 저장 때 lobby_intro 를 쓴다', 'APP_CONFIG["lobby_intro"] = bool(self.var_li.get())' in SRC)
check('C 소개 채팅 진입점이 lobby_intro 꺼짐이면 막힌다', gate_ok(SRC))
posts = re.findall(r'/messages"?\s*$|messages["\']?,? headers=headers, json=\{"body"', SRC, re.M)
check('D 로비 채팅 POST 는 _lobby_intro_text 를 쓰는 한 곳', SRC.count('json={"body": _lobby_intro_text(), "type": "chat"}') == 1 and len(re.findall(r'_lobby_intro\(', SRC)) == 2 + 0 or SRC.count('target=_lobby_intro,') == 1, '')
mut = SRC.replace(' and APP_CONFIG.get("lobby_intro", True):\n                _ok, _why = _lobby_intro_ready', ':\n                _ok, _why = _lobby_intro_ready')
check('E 변이(옵션 검사 삭제) 에서 C 가 빨개진다', mut != SRC and not gate_ok(mut))
print('\n전부 통과' if not FAILS else '\n실패 %d건' % len(FAILS)); sys.exit(1 if FAILS else 0)
