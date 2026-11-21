#!/usr/bin/env python3
"""🛡 팀 엠블럼 「문양」 — OpenAI 이미지 API(텍스트→이미지)로 e스포츠 팀 문양 느낌의 흑백 실루엣 32종을 뽑아 img/emblem/s<번호>.webp 로 저장.
흰 문양 + 검정 배경 → 웹이 SVG 마스크(밝기)로 읽어 원하는 색을 입힌다. 실제 프로게임단 로고는 쓰지 않는다 — 동물·무기·천체 같은 흔한 상징만.
사용: python3 tooling/openai_emblem_symbols.py <작업폴더> [번호 …]   (작업폴더에 raw PNG 를 두고, 그다음 웹용 WebP 를 img/emblem/ 에 쓴다)
키는 환경에 없다 — 세션 프록시가 api.openai.com 호출에 인증을 붙인다(CLAUDE.md 「그림」 절)."""
import sys, os, json, base64, subprocess
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMS = ["a roaring tiger head","a Chinese-style serpent dragon head","a snarling wolf head","an eagle head in profile with spread wings","a phoenix rising with flame wings",
 "a lion head with mane","a growling bear head","a cunning fox head","a shark with open jaws","a coiled cobra ready to strike","a charging bull head with horns","a prowling panther head",
 "an owl with wide eyes and spread wings","a scorpion with raised tail","a royal crown with jewels","a grinning skull with crossed bones","a bold lightning bolt","a raging flame",
 "a sword pointing up with small wings","a heraldic shield with a star","a pair of feathered wings","three slashing claw marks","a five-pointed star with rays","a ship anchor with a rope",
 "a gear cog with a lightning core","a shooting comet with a tail","a crescent moon with a star","a faceted diamond gem","a laurel wreath around a star","a trident","an all-seeing eye with rays","a clenched fist",
 ][:32]
def gen(i, out):
    prompt = ("A bold esports team emblem symbol: %s. Pure solid WHITE shape on a pure solid BLACK background, thick clean vector-style silhouette with fine black negative-space lines "
              "for details (eyes, feathers, scales), strong readable shape, centered, filling most of the square, no gradients, no gray, no text, no letters, no numbers, not any existing brand's logo." % SYMS[i])
    r = subprocess.run(['curl','-sS','--max-time','100','-X','POST','https://api.openai.com/v1/images/generations','-H','Content-Type: application/json',
        '-d', json.dumps({'model':'gpt-image-2','prompt':prompt,'quality':'low','size':'1024x1024','output_format':'png'})], capture_output=True, text=True)
    try: j = json.loads(r.stdout)
    except Exception: return 'RAW ' + r.stdout[:160]
    if 'data' not in j: return json.dumps(j)[:200]
    open(out, 'wb').write(base64.b64decode(j['data'][0]['b64_json'])); return 'ok'
def to_webp(src, dst):
    from PIL import Image, ImageOps
    im = Image.open(src).convert('L'); im = ImageOps.autocontrast(im, cutoff=1)
    bb = ImageOps.invert(im).point(lambda v: 255 if v > 200 else 0)  # 흰 문양 영역(검정 배경 반전→밝은 부분)
    box = im.point(lambda v: 255 if v > 90 else 0).getbbox() or (0, 0, im.width, im.height)
    w = box[2] - box[0]; h = box[3] - box[1]; s = max(w, h); pad = int(s * .06); cx = (box[0] + box[2]) // 2; cy = (box[1] + box[3]) // 2; hh = s // 2 + pad
    im = im.crop((cx - hh, cy - hh, cx + hh, cy + hh)).resize((160, 160), Image.LANCZOS)
    im.save(dst, quality=88); return os.path.getsize(dst)
if __name__ == '__main__':
    work = sys.argv[1]; os.makedirs(work, exist_ok=True)
    ids = [int(x) for x in sys.argv[2:]] or list(range(len(SYMS)))
    def one(i):
        out = os.path.join(work, 's%d.png' % i)
        if os.path.exists(out): return i, 'cached'
        for t in range(3):
            r = gen(i, out)
            if r == 'ok': return i, r
        return i, r
    with ThreadPoolExecutor(4) as ex:
        for i, r in ex.map(one, ids): print(i, r, flush=True)
    for i in ids:
        p = os.path.join(work, 's%d.png' % i)
        if os.path.exists(p): to_webp(p, os.path.join(ROOT, 'img', 'emblem', 's%d.webp' % i))
