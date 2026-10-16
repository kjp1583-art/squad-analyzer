# -*- coding: utf-8 -*-
"""⚖️ 2026-10-15 평균 맞추기(브레스 하향 + 약한 무기 상향) 이전 값으로 되돌린 survivors.html 사본을 만든다.
옛 기준 커밋과 「비트까지 같다」를 따지는 시험(정책 봇이 어떤 무기를 집을지 모르는 판)은, 일부러 바꾼 피해 값 때문에 달라지는 걸 빼고 규칙 불변을 보려면
새 파일의 피해 값만 옛 값으로 되돌려 견주면 된다 — 값을 되돌렸는데도 다르면 그건 규칙이 바뀐 것이다."""
PAIRS = [   # (새 글자, 옛 글자)
    ("const BRT={R:190,w:.62,d:11,", "const BRT={R:190,w:.62,d:29,"),
    ("slime:{d:24,bd:12.8,", "slime:{d:17,bd:9.1,"),
    ("cart:{d:20,cd:7,", "cart:{d:5,cd:7,"),
    ("quill:{d:16,", "quill:{d:11.5,"),
    ("heart:{d:21,", "heart:{d:16,"),
    ("pcards:{d:19.5,", "pcards:{d:13,"),
    ("frost:{d:50,", "frost:{d:44,"),
    ("meteor:{d:14,", "meteor:{d:5,"),
    ("rkt:{d:7.5,", "rkt:{d:6,"),
    ("bell:{d:7,R:90", "bell:{d:5.5,R:90"),
    ("fryer:{d:15},sushi:{d:34},shrimp:{d:28},spk:{d:16}", "fryer:{d:5},sushi:{d:12},shrimp:{d:14},spk:{d:8}"),
    ("eom:{d:54,dg:", "eom:{d:48,dg:"),
    ("sing:{d:6.6,db:1.9,", "sing:{d:5.9,db:1.7,"),
]


def revert(text):
    for new, old in PAIRS:
        assert text.count(new) == 1, '되돌릴 글자를 못 찾았다(표 값이 또 바뀌었으면 tests/sv_old1015.py 도 같이 고친다): ' + new
        text = text.replace(new, old)
    return text
