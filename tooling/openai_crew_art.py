#!/usr/bin/env python3.13
"""🎨 동료 SD 캐릭터(계열 5 × 등급 5 = 25장)를 OpenAI 이미지 API 로 뽑는다 (2026-11-14 사장님 「동료들 이미지API 활용해서 SD캐릭터 일러스트 추가」).
기본 병아리 그림을 참조(편집 모드)로 써서 같은 그림체로 직업군 복장·등급별 장비를 입힌다 → 초록 배경 제거 → 256px WebP (img/brjhunt/crew/<계열>_<등급>.webp).
키는 환경에 없다(세션 프록시가 api.openai.com 에 인증을 붙인다 · CLAUDE.md 「그림」 절). 크레딧이 바닥이면 credit_balance_exhausted 로 멈춘다 — 충전 뒤 다시 돌린다.
사용:  python3.13 tooling/openai_crew_art.py gen  [fam[_grade] …]     원본(초록 배경) 을 /tmp/crew_raw/ 에 뽑는다(이미 있으면 건너뜀 · 동시 4개 이하)
       python3.13 tooling/openai_crew_art.py cut                      /tmp/crew_raw/*.png → img/brjhunt/crew/*.webp (배경 제거)
       python3.13 tooling/openai_crew_art.py wire                     img/brjhunt/crew 에 있는 파일을 brjhunt_sd.js FILES 표에 적는다
뽑은 뒤 contact sheet 로 눈으로 확인하고, 틀린 장만 gen 을 다시 돌린다(같은 이름은 지우고)."""
import sys, os, subprocess, json, base64, re, glob, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RAW = '/tmp/crew_raw'; OUT = os.path.join(ROOT, 'img', 'brjhunt', 'crew')
SRC = os.path.join(ROOT, 'img', 'brjang', 'parts', 'body_chick', 'front.png')
FAMS = {
    'tank':  'a sturdy tank knight: dented steel helmet, big round shield on one wing, short sword, standing firmly',
    'blade': 'a nimble assassin: dark hooded cloak with a scarf over the lower face, twin daggers, crouching ready pose',
    'mage':  'a mage: tall pointed wizard hat, long robe, a glowing crystal staff, magic sparkles',
    'bow':   'an archer: green ranger hood with a feather, a quiver on the back, a longbow, calm aiming pose',
    'heal':  'a healer: white and pink priest robe with a hood, a small heart-topped staff, soft green healing glow',
}
GRADES = {   # 등급이 오를수록 장비가 화려해진다 — 색 팔레트도 등급색(brjhunt_sd.js GRP)과 맞춘다
    'normal': 'simple plain cloth gear, grey-silver accents',
    'rare':   'neat well-made gear with blue accents and a faint blue glow',
    'epic':   'ornate gear with purple accents, small floating purple sparkles',
    'unique': 'gilded luxurious gear with orange-gold accents, a gold star emblem on the chest, golden sparkles',
    'legend': 'legendary radiant gear with pink-red accents, a small golden crown and tiny wings, a glowing aura, many sparkles',
}
def prompt(fam, gr):
    return ("Keep this yellow chick mascot exactly as it is — same head shape, face, cheeks, beak, outline and flat cel-shaded sticker art style — but redraw it as a cute chibi SD (super-deformed, 2-head-tall) fantasy %s. "
            "Gear tier: %s. Front view, full body, centered, on a solid flat bright green (#00ff00) background with no shadow, no text, no letters, no numbers." % (FAMS[fam], GRADES[gr]))
def gen_one(key):
    fam, gr = key.split('_'); out = os.path.join(RAW, key + '.png')
    if os.path.exists(out): return key, 'skip'
    for attempt in range(4):
        r = subprocess.run(['curl', '-sS', '--max-time', '100', '-X', 'POST', 'https://api.openai.com/v1/images/edits', '-F', 'model=gpt-image-2', '-F', 'image=@' + SRC, '-F', 'quality=low',
                            '-F', 'size=1024x1024', '-F', 'output_format=png', '-F', 'prompt=' + prompt(fam, gr)], capture_output=True, text=True)
        try: j = json.loads(r.stdout)
        except Exception: j = {'error': {'message': 'RAW ' + r.stdout[:120] + r.stderr[:120]}}
        if 'data' in j: open(out, 'wb').write(base64.b64decode(j['data'][0]['b64_json'])); return key, 'ok'
        e = j.get('error', {}); msg = str(e.get('message', ''))
        if e.get('code') == 'credit_balance_exhausted' or 'no credits' in msg: return key, 'STOP 크레딧 없음 — 충전 필요'
        time.sleep(8 * (attempt + 1))        # 429(분당 5장)·일시 오류는 기다렸다 재시도
    return key, 'FAIL ' + msg[:120]
def keys(args):
    ks = []
    for a in args or [f + '_' + g for f in FAMS for g in GRADES]:
        if a in FAMS: ks += [a + '_' + g for g in GRADES]
        elif '_' in a and a.split('_')[0] in FAMS and a.split('_')[1] in GRADES: ks.append(a)
    return ks
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'gen':
        os.makedirs(RAW, exist_ok=True); ks = keys(sys.argv[2:])
        with ThreadPoolExecutor(3) as ex:
            for k, res in ex.map(gen_one, ks):
                print(k, res, flush=True)
                if res.startswith('STOP'): os._exit(2)
    elif cmd == 'cut':
        import openai_chick_art as A
        os.makedirs(OUT, exist_ok=True)
        for f in sorted(glob.glob(RAW + '/*.png')):
            dst = os.path.join(OUT, os.path.basename(f)[:-4] + '.webp'); A.cut(f, dst); print('cut', dst)
    elif cmd == 'wire':
        p = os.path.join(ROOT, 'brjhunt_sd.js'); s = open(p, encoding='utf-8').read()
        have = sorted(os.path.basename(f)[:-5] for f in glob.glob(OUT + '/*.webp'))
        body = ', '.join("%s: 'img/brjhunt/crew/%s.webp'" % (k, k) for k in have)
        s2 = re.sub(r"const FILES = \{[^;]*?\};", "const FILES = {%s};" % (' ' + body + ' ' if body else ''), s, count=1, flags=re.S)
        open(p, 'w', encoding='utf-8').write(s2); print('FILES', len(have), '개 연결')
    else: print(__doc__)
main()
