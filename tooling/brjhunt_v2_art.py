#!/usr/bin/env python3
"""🎨 브장신 키우기 3차 개편 — 사냥터 그림(img/brjhunt/v2/) 제작 파이프라인.

OpenAI 이미지 API 로 「한 장에 여러 컷이 든 시트」를 뽑아(한 장에서 뽑아야 얼굴·색·검이 컷끼리 어긋나지 않는다)
배경을 지우고 → 컷으로 자르고 → 크기·발 위치를 맞춰 → 가로 한 줄 WebP 시트 + manifest.json 으로 만든다.
키는 환경에 없다 — 세션 프록시가 api.openai.com 호출에 인증을 붙인다(CLAUDE.md 「그림」 절). 분당 입력 이미지 5장 제한 → 동시 3~4개·429 는 재시도.

사용(저장소 루트에서, PIL·numpy 가 있는 파이썬으로):
  python3 tooling/brjhunt_v2_art.py list                       # 작업 목록
  python3 tooling/brjhunt_v2_art.py gen  chickA chickB ... [-k 2] [--raw 폴더]   # 원본 뽑기(후보 k장) → 폴더/<작업>_<k>.png
  python3 tooling/brjhunt_v2_art.py build [이름...] [--raw 폴더]  # picks 대로 잘라 img/brjhunt/v2 와 manifest.json 만들기
  python3 tooling/brjhunt_v2_art.py sheet [--raw 폴더]            # 어두운/밝은 배경 contact sheet(눈 확인용) → <raw>/contact_*.png
원본(raw) PNG 는 저장소에 넣지 않는다(크다). 어느 후보를 썼는지는 tooling/brjhunt_v2_picks.json 에 남는다.
"""
import sys, os, json, base64, subprocess, time, math
from collections import deque
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'img', 'brjhunt', 'v2')
PICKS = os.path.join(ROOT, 'tooling', 'brjhunt_v2_picks.json')
H = os.path.join(ROOT, 'img', 'brjhunt')

CHICK_KEEP = ("Keep this yellow chick character exactly as it is: same round head, face with angry eyes, pink cheeks, small orange beak, "
              "orange feet, dark outline, flat cartoon art style, and the same small wooden sword. ")
GREEN = " Solid flat bright green (#00ff00) background, no shadow, no text, no numbers, no grid lines, no extra objects."
SAME = " Every frame the same size and scale, same character design, wide empty gaps between frames."

def chick(cells, what, cols, rows):
    return (CHICK_KEEP + "Draw a sprite sheet of %s: %d frames arranged in %d columns by %d rows. " % (what, cells, cols, rows)) + SAME + GREEN

def mon(name, what):
    return ("Keep this cute angry food monster exactly as it is (%s): same face, colors, outline and flat cartoon art style. Draw a sprite sheet in 3 columns by 2 rows, "
            "wide empty gaps between frames, every frame the same size, facing right in a three-quarter view. %s" % (name, what)) + GREEN

R = lambda n: os.path.join(H, n)
# 작업: 이름 -> (kind 'edit'(참조 그림 있음)|'gen', 참조, 크기, 프롬프트, 지우기 'green'|'black', (열,행))
JOBS = {}
def job(name, kind, ref, size, prompt, key, grid): JOBS[name] = dict(kind=kind, ref=ref, size=size, prompt=prompt, key=key, grid=grid)

CHICK_REF = '@chick_idle'
job('chickRun', 'edit', CHICK_REF, '1536x1024', chick(6, "a RUN CYCLE of the chick running to the right, full body, body leaning forward, legs in different stages of the run (contact, passing, push-off), sword held low behind", 3, 2), 'green', (3, 2))
job('chickIdleJump', 'edit', CHICK_REF, '1536x1024', chick(6,
    "6 poses in order left to right, top row then bottom row: (1) standing idle with the body at normal height holding the sword, (2) standing idle slightly crouched with knees bent, (3) standing idle stretched taller, "
    "(4) JUMP rising in the air with legs tucked up and the sword arm raised, (5) FALLING with legs dangling down and wings up, (6) HURT flinching backwards with eyes squeezed shut and mouth open in pain", 3, 2), 'green', (3, 2))
job('chickAtk12', 'edit', CHICK_REF, '1536x1024', chick(6,
    "two sword attacks. Top row, attack one, 3 frames: (1) wind-up pulling the sword back behind the body, (2) fast horizontal sword swing forward at full extension, (3) follow-through with the sword far forward. "
    "Bottom row, attack two, 3 frames: (1) crouch with the sword low behind, (2) rising diagonal upward slash, (3) sword raised high after the slash. Chick faces right, no motion lines, no slash effect drawn", 3, 2), 'green', (3, 2))
job('chickAtk3Cast', 'edit', CHICK_REF, '1536x1024', chick(6,
    "a sword attack and a spell cast. Top row, attack three, 3 frames: (1) leaping up with the sword raised overhead in both hands, (2) bringing the sword down hard in an overhead chop, (3) landing crouched with the sword stuck forward at the end of the chop. "
    "Bottom row, casting a skill, 3 frames: (1) crouch gathering energy with the sword held close, (2) standing tall with the sword pointed up high in both hands and a determined shout, (3) thrusting the sword forward with one arm. Chick faces right, no glow, no effects drawn", 3, 2), 'green', (3, 2))
job('chickDie', 'edit', CHICK_REF, '1536x1024', chick(6,
    "a DEFEAT animation in order left to right, top row then bottom row: (1) knocked back leaning far backwards with eyes squeezed shut, (2) dizzy tipping over with swirly eyes and the sword dropping, "
    "(3) lying flat on its back on the ground with swirly eyes and legs up, the sword beside it, (4) same lying pose but sad and a bit flatter, (5) sitting dazed with stars circling over its head, (6) standing up again weakly", 3, 2), 'green', (3, 2))
MON = [('m1', '새우 shrimp'), ('m2', 'tofu block'), ('m3', 'spiky puffball'), ('m4', 'red helmet delivery rider'), ('m5', 'fried chicken drumstick'), ('m6', 'ramen cup')]
for k, nm in MON:
    job('mon_' + k, 'edit', '@%s_idle' % k, '1536x1024', mon(nm, "Frames in order, top row then bottom row: (1) walking step with the left foot forward, (2) walking passing pose, (3) walking step with the right foot forward, (4) walking passing pose with a small hop, "
        "(5) HIT reaction: eyes squeezed shut in pain with the mouth open, body squashed and tilted back, with two small yellow sparkle stars around it, (6) DEFEATED: flattened and tipped over with swirly dizzy eyes and little stars, slightly faded."), 'green', (3, 2))

# ---- 지역 6곳: 발판 키트(바닥 조각·떠 있는 발판·벽 블록) · 원경 · 근경
REGIONS = [('1', '합정 골목', 'a Seoul back alley at sunset with red brick walls and old power lines', 'worn red brick and concrete paving, cracked asphalt'),
           ('2', 'bhc 합정점 앞', 'a sunny Seoul riverside street in front of a red fried chicken restaurant', 'clean paving stones with a little grass and a red-and-white curb'),
           ('3', '홍대 먹자골목', 'a Seoul night food alley full of neon signs, lanterns and restaurants', 'dark wet paving stones with neon-pink and purple light reflections'),
           ('4', '상수 뒷길', 'a quiet golden-hour Seoul back street with small cafes, vines and bicycles', 'warm sandy pavement with moss and vines, wooden planks'),
           ('5', '망원 시장', 'a busy Seoul traditional market with fruit and fish stalls under arcade canopies', 'worn tile floor with wooden crates and striped awning edges'),
           ('6', '한강 둔치', 'the Han river bank at orange sunset with bridges and tall apartment towers in the distance', 'grassy riverbank with stone edging and cycling path tiles')]
for rid, rn, scene, surf in REGIONS:
    job('plat' + rid, 'edit', '@bg' + rid, '1536x1024',
        ("Same art style as this background (%s). Draw a 2D platformer terrain kit in the same cartoon style, three separate objects on a solid flat bright green (#00ff00) background with wide gaps between them, "
         "all seen from the side: TOP: one long horizontal ground slab about 4 times wider than tall, with a flat walkable top surface (%s) and a thick earthy underside, with rounded left and right ends. "
         "MIDDLE: one thin floating one-way platform about 6 times wider than tall, a plank or ledge that fits the theme, flat top, with small end caps. "
         "BOTTOM: one square solid wall block, same material as the ground. No characters, no text, no shadows, outlined like the background art.") % (scene, surf), 'green', (1, 3))
    job('far' + rid, 'edit', '@bg' + rid, '1536x1024',
        ("Same art style and color mood as this reference. A wide panorama of the DISTANT background of %s: far-away buildings and skyline fading into haze, soft low contrast, a gradient sky, "
         "no characters, no foreground objects, nothing on the ground, nothing in the lower third but the far skyline base fading to a soft haze. No text.") % scene, 'none', (1, 1))
    job('near' + rid, 'edit', '@bg' + rid, '1536x1024',
        ("Same art style as this reference. A single horizontal row of near-ground scenery props for %s (for example shop fronts, trees, lamp posts, signs, stalls, benches), "
         "side view, each prop standing on the same flat ground line in the lower half of the image, spaced apart with empty gaps, nothing touching the left and right edges. "
         "Solid flat bright green (#00ff00) background everywhere else, no sky, no ground, no characters, no text, no shadows.") % scene, 'green', (1, 1))

# ---- 이펙트(검정 배경 → 밝기를 알파로) · 코인·먼지는 초록 배경
FXB = (" Game VFX sprite sheet, 4 frames arranged in 2 columns by 2 rows, wide empty gaps, every frame the same size, the effect centered in its cell, glowing, hand-painted cartoon game style. "
       "Pure solid black background, no character, no text, no numbers, no grid lines.")
FXS = [('fxSlash1', 'A horizontal crescent sword slash arc sweeping left to right: thin at first, then a full bright arc, then fading into sparkles. Bright white core, cyan-blue glowing edge.'),
       ('fxSlash2', 'A rising diagonal crescent sword slash arc from lower left to upper right: thin at first, then a full bright arc, then fading into sparkles. Golden-orange core with white edge.'),
       ('fxSlash3', 'A huge overhead vertical sword slam: a bright vertical arc coming down with a ground shockwave ring at the end, then fading. White and yellow with orange glow.'),
       ('fxImpact', 'A hit impact burst: a sharp starburst flash with spark lines radiating, expanding and fading frame by frame. White-yellow center, orange edge.'),
       ('fxCrit', 'A critical hit effect: a large four-point sparkle star with radiating rays, shimmering and rotating, growing then fading. Red, gold and white.'),
       ('sk_slash', 'A golden X-shaped double cross slash: two crossing bright crescent slashes appearing one after the other, then a flash and fade.'),
       ('sk_peck', 'A rapid beak-pecking attack: many small bright orange-yellow stab sparks and little star bursts popping in a cluster, growing then fading.'),
       ('sk_spin', 'A cyan whirlwind spin attack: a bright swirling ring of wind blades around the center, spinning, growing and fading.'),
       ('sk_bomb', 'A fried-chicken-drumstick bomb explosion: a small falling drumstick, then a big orange-red fireball explosion with smoke and sparks, then fading.'),
       ('sk_thunder', 'A lightning strike from above: a jagged bright yellow lightning bolt striking down, a bright ground flash with electric sparks, then fading.'),
       ('sk_fire', 'A spicy red-orange chili flame wave blasting forward: a fire stream growing and spreading, red and orange with yellow core, then fading.'),
       ('sk_egg', 'A golden egg glowing and rolling with a shining golden trail of sparkles, then bursting in a golden flash.'),
       ('sk_shield', 'A brown and gold protective aura: a round shimmering dome of light with small hexagon patterns pulsing, appearing and fading, warm amber glow.'),
       ('sk_shrimp', 'A swarm of small pink shrimp silhouettes rushing forward with pink sparkles and a pink glow, growing then fading.'),
       ('sk_storm', 'A purple and magenta tornado storm: a swirling funnel with lightning and debris, growing to a huge storm then fading.')]
for n, d in FXS: job(n, 'gen', None, '1024x1024', d + FXB, 'black', (2, 2))
job('fxDust', 'gen', None, '1024x1024', "Cartoon dust puff effect, 4 frames in 2 columns by 2 rows, wide gaps: a small beige-brown smoke puff with soft outline expanding and fading frame by frame, round cartoon cloud shapes. Solid flat bright green (#00ff00) background, no text.", 'green', (2, 2))
job('fxCoin', 'gen', None, '1024x1024', "Cartoon gold coin spinning, 4 frames in 2 columns by 2 rows, wide gaps, every frame the same size: front view, three-quarter turn, thin edge view, back view. Shiny gold with a star emblem, dark outline, no text and no numbers. Solid flat bright green (#00ff00) background.", 'green', (2, 2))

# ---------------------------------------------------------------- 뽑기(API)
def ref_path(ref, raw):
    """'@chick_idle' -> 초록 배경에 얹은 1024 참조 PNG(원본 투명 WebP 는 배경이 번져 일관성이 떨어진다)"""
    if not ref: return None
    if not ref.startswith('@'): return ref
    name = ref[1:]; p = os.path.join(raw, '_ref_%s.png' % name)
    if not os.path.exists(p):
        src = name + '.webp' if os.path.exists(R(name + '.webp')) else name
        im = Image.open(R(src)).convert('RGBA'); im = im.resize((1024, int(1024 * im.height / im.width)), Image.LANCZOS)
        bg = Image.new('RGB', im.size, (0, 255, 0)); bg.paste(im, (0, 0), im); bg.save(p)
    return p

def call_api(j, raw, out):
    p = j['prompt']
    ref = ref_path(j['ref'], raw)
    for attempt in range(6):
        if ref:
            cmd = ['curl', '-sS', '--max-time', '110', '-X', 'POST', 'https://api.openai.com/v1/images/edits', '-F', 'model=gpt-image-2', '-F', 'image=@' + ref,
                   '-F', 'quality=low', '-F', 'size=' + j['size'], '-F', 'output_format=png', '-F', 'prompt=' + p]
        else:
            body = json.dumps(dict(model='gpt-image-2', prompt=p, quality='low', size=j['size'], output_format='png'))
            cmd = ['curl', '-sS', '--max-time', '110', '-X', 'POST', 'https://api.openai.com/v1/images/generations', '-H', 'Content-Type: application/json', '-d', body]
        r = subprocess.run(cmd, capture_output=True, text=True)
        try: d = json.loads(r.stdout)
        except Exception: d = {}
        if 'data' in d:
            open(out, 'wb').write(base64.b64decode(d['data'][0]['b64_json'])); return 'ok'
        msg = json.dumps(d)[:200] if d else (r.stdout[:150] + r.stderr[:150])
        time.sleep(15 + 10 * attempt)       # 429·프록시 끊김은 기다렸다 재시도
    return 'FAIL ' + msg

def cmd_gen(names, k, raw):
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(raw, exist_ok=True)
    todo = []
    for n in names:
        for i in range(1, k + 1):
            out = os.path.join(raw, '%s_%d.png' % (n, i))
            if not os.path.exists(out): todo.append((n, out))
    def run(t):
        n, out = t; r = call_api(JOBS[n], raw, out); print(os.path.basename(out), r, flush=True); return r
    with ThreadPoolExecutor(3) as ex: list(ex.map(run, todo))

# ---------------------------------------------------------------- 배경 지우기·자르기
def key_green(im):
    """가장자리와 이어진 초록만 지운다(외곽선 안쪽 색은 건드리지 않는다) → RGBA uint8"""
    a = np.array(im.convert('RGB')).astype(int)
    bg = ((a[..., 1] - np.maximum(a[..., 0], a[..., 2])) > 70) & (a[..., 1] > 150)
    Hh, Ww = bg.shape; vis = np.zeros_like(bg); dq = deque()
    for x in range(Ww):
        for y in (0, Hh - 1):
            if bg[y, x] and not vis[y, x]: dq.append((y, x)); vis[y, x] = 1
    for y in range(Hh):
        for x in (0, Ww - 1):
            if bg[y, x] and not vis[y, x]: dq.append((y, x)); vis[y, x] = 1
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < Hh and 0 <= nx < Ww and bg[ny, nx] and not vis[ny, nx]: vis[ny, nx] = 1; dq.append((ny, nx))
    # 가장자리와 안 이어진 초록 구멍(발 사이 등)도 지운다: 순수한 초록만
    pure = ((a[..., 1] - np.maximum(a[..., 0], a[..., 2])) > 110) & (a[..., 1] > 190)
    vis = vis | pure
    am = Image.fromarray(np.where(vis, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
    o = a.copy(); edge = np.array(am) < 250
    fix = edge & ((o[..., 1] - np.maximum(o[..., 0], o[..., 2])) > 0)
    o[..., 1] = np.where(fix, np.maximum(o[..., 0], o[..., 2]), o[..., 1])      # 가장자리 초록 번짐 제거
    out = np.dstack([np.clip(o, 0, 255).astype(np.uint8), np.array(am)])
    return Image.fromarray(out, 'RGBA')

def key_black(im, boost=1.15):
    """검정 배경: 밝기를 알파로, 색은 알파로 나눠 되살린다(검은 바탕 위에 얹으면 원래 그림과 같다)"""
    a = np.array(im.convert('RGB')).astype(float)
    m = a.max(axis=2); al = np.clip(m / 255.0 * boost, 0, 1); al[m < 10] = 0
    col = np.where(al[..., None] > 0, a / np.maximum(al[..., None], 1e-3), 0)
    out = np.dstack([np.clip(col, 0, 255), al * 255]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')

def cells_of(rgba, grid, dil=9):
    """덩어리(연결 성분)를 칸에 배정해 칸마다 RGBA 한 장씩 돌려준다(칸 경계를 넘는 검·꼬리도 제 칸에 붙는다)"""
    cols, rows = grid; arr = np.array(rgba); Hh, Ww = arr.shape[:2]
    mask = Image.fromarray(((arr[..., 3] > 40) * 255).astype(np.uint8))
    if dil: mask = mask.filter(ImageFilter.MaxFilter(dil | 1))
    sm = np.array(mask.resize((Ww // 4, Hh // 4), Image.NEAREST)) > 127
    lab = np.zeros(sm.shape, np.int32); n = 0; sh, sw = sm.shape; info = {}
    for y0 in range(sh):
        for x0 in range(sw):
            if sm[y0, x0] and not lab[y0, x0]:
                n += 1; lab[y0, x0] = n; dq = deque([(y0, x0)]); cnt = 0; sx = sy = 0
                while dq:
                    y, x = dq.popleft(); cnt += 1; sx += x; sy += y
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < sh and 0 <= nx < sw and sm[ny, nx] and not lab[ny, nx]: lab[ny, nx] = n; dq.append((ny, nx))
                info[n] = (cnt, sx / cnt * 4, sy / cnt * 4)
    out = []
    big = {k: v for k, v in info.items() if v[0] > 12}          # 점 하나짜리 얼룩은 버린다
    full = np.kron(lab, np.ones((4, 4), np.int32)); full = np.pad(full, ((0, Hh - full.shape[0]), (0, Ww - full.shape[1])))
    for r in range(rows):
        for c in range(cols):
            ids = [k for k, (cnt, cx, cy) in big.items() if int(cx // (Ww / cols)) == c and int(cy // (Hh / rows)) == r]
            sel = np.isin(full, ids) if ids else np.zeros((Hh, Ww), bool)
            a2 = arr.copy(); a2[..., 3] = np.where(sel, arr[..., 3], 0)
            out.append(Image.fromarray(a2, 'RGBA'))
    return out

def seamless(im, b):
    """가로로 이어 붙여도 이음매가 안 보이게: 오른쪽 끝 b 칸을 왼쪽 끝과 섞는다(너비 b 줄어듦)"""
    a = np.array(im.convert('RGB')).astype(float); Ww = a.shape[1]; r = a[:, :Ww - b].copy()
    for x in range(b):
        t = x / b; r[:, x] = a[:, x] * t + a[:, Ww - b + x] * (1 - t)
    return Image.fromarray(r.astype(np.uint8))

def match_color(frames, ref_name):
    """원본 병아리·몬스터의 밝은 몸 색과 중앙값을 맞춘다(생성물이 조금 주황 쪽으로 번지는 걸 되돌림, 채널별 ±15% 안)"""
    ref = np.array(Image.open(R(ref_name + '.webp')).convert('RGBA'))
    def med(a):
        m = (a[..., 3] > 250) & (a[..., :3].mean(axis=2) > 150)
        return np.median(a[m][:, :3], axis=0) if m.sum() > 50 else None
    mr = med(ref); out = []
    for f in frames:
        a = np.array(f); mf = med(a)
        if mr is None or mf is None: out.append(f); continue
        g = np.clip(mr / np.maximum(mf, 1), 0.85, 1.15)
        a[..., :3] = np.clip(a[..., :3].astype(float) * g, 0, 255).astype(np.uint8); out.append(Image.fromarray(a, 'RGBA'))
    return out

# ---------------------------------------------------------------- 시트 정의
# 이름: dict(job, cells(쓸 칸 번호, 0부터 · 위→아래, 왼→오), scale(원본→출력), fps, mode 'feet'(발 가운데가 앵커)|'center', ref(색 맞출 원본))
SHEETS = {}
def sheet(name, jobn, cells, scale, fps, mode='feet', ref=None, loop=True): SHEETS[name] = dict(job=jobn, cells=cells, scale=scale, fps=fps, mode=mode, ref=ref, loop=loop)
CS = 0.40
sheet('chick_run', 'chickRun', [0, 1, 2, 3, 4, 5], CS, 12, ref='chick_idle')
sheet('chick_idle', 'chickIdleJump', [0, 1, 2, 1], CS, 4, ref='chick_idle')
sheet('chick_jump', 'chickIdleJump', [3], CS, 1, ref='chick_idle')
sheet('chick_fall', 'chickIdleJump', [4], CS, 1, ref='chick_idle')
sheet('chick_hurt', 'chickIdleJump', [5], CS, 1, ref='chick_idle')
sheet('chick_attack1', 'chickAtk12', [0, 1, 2], CS, 14, ref='chick_idle', loop=False)
sheet('chick_attack2', 'chickAtk12', [3, 4, 5], CS, 14, ref='chick_idle', loop=False)
sheet('chick_attack3', 'chickAtk3Cast', [0, 1, 2], CS, 12, ref='chick_idle', loop=False)
sheet('chick_cast', 'chickAtk3Cast', [3, 4, 5], CS, 10, ref='chick_idle', loop=False)
sheet('chick_die', 'chickDie', [1, 2], CS, 5, ref='chick_idle', loop=False)
for k, _ in MON:
    sheet(k + '_walk', 'mon_' + k, [0, 1, 2, 3], 0.46, 6, ref=k + '_idle')
    sheet(k + '_hit', 'mon_' + k, [4], 0.46, 1, ref=k + '_idle')
    sheet(k + '_die', 'mon_' + k, [5], 0.46, 1, ref=k + '_idle', loop=False)
for n, _ in FXS: sheet(n, n, [0, 1, 2, 3], 0.36, 14 if n.startswith('fx') else 12, mode='center', loop=False)
sheet('fxDust', 'fxDust', [0, 1, 2], 0.30, 10, mode='feet', loop=False)
sheet('fxCoin', 'fxCoin', [0, 1, 2, 3], 0.20, 10, mode='center')

def load_pick(raw, n):
    picks = json.load(open(PICKS)) if os.path.exists(PICKS) else {}
    return os.path.join(raw, '%s_%d.png' % (n, picks.get(n, 1)))

def keyed(raw, jn):
    j = JOBS[jn]; im = Image.open(load_pick(raw, jn)).convert('RGB')
    return key_green(im) if j['key'] == 'green' else key_black(im)

def bbox_of(im): return im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()

def build_sheet(raw, name, sp, man):
    j = JOBS[sp['job']]; rg = keyed(raw, sp['job']); W, Hh = rg.size
    cells = cells_of(rg, j['grid']); cw, ch = W / j['grid'][0], Hh / j['grid'][1]
    sel = [cells[i] for i in sp['cells']]
    if sp['ref']: sel = match_color(sel, sp['ref'])
    boxes = [bbox_of(f) for f in sel]
    if any(b is None for b in boxes): raise SystemExit('빈 칸이 있다: %s %s' % (name, boxes))
    s = sp['scale']
    # 칸 안 위치(가로)는 원본 그대로 유지(몸이 칸마다 덜렁거리지 않게), 세로는 발바닥(상자 아래)을 맞춘다
    items = []
    for i, f, b in zip(sp['cells'], sel, boxes):
        c, r = i % j['grid'][0], i // j['grid'][0]
        cx0 = (c + 0.5) * cw; bx = ((b[0] + b[2]) / 2 - cx0) * s
        crop = f.crop(b).resize((max(1, round((b[2] - b[0]) * s)), max(1, round((b[3] - b[1]) * s))), Image.LANCZOS)
        items.append((crop, bx))
    if sp['mode'] == 'center':          # 이펙트: 원본 칸 중심이 앵커, 모든 칸 같은 크기
        half = max(max(abs(bx) + c.width / 2 for c, bx in items), 8)
        cyc = []
        for i, f, b in zip(sp['cells'], sel, boxes):
            r = i // j['grid'][0]; cy0 = (r + 0.5) * ch; cyc.append(((b[1] + b[3]) / 2 - cy0) * s)
        halfy = max(max(abs(y) + c.height / 2 for (c, bx), y in zip(items, cyc)), 8)
        cwid, chei = int(math.ceil(half * 2)) + 4, int(math.ceil(halfy * 2)) + 4
        strip = Image.new('RGBA', (cwid * len(items), chei))
        for k, ((c, bx), y) in enumerate(zip(items, cyc)):
            strip.alpha_composite(c, (int(k * cwid + cwid / 2 + bx - c.width / 2), int(chei / 2 + y - c.height / 2)))
        anchor = [cwid // 2, chei // 2]
    else:                               # 발바닥 기준
        left = max(c.width / 2 - bx for c, bx in items); right = max(c.width / 2 + bx for c, bx in items)
        cwid = int(math.ceil(max(left, right) * 2)) + 4; chei = max(c.height for c, bx in items) + 4
        strip = Image.new('RGBA', (cwid * len(items), chei))
        for k, (c, bx) in enumerate(items):
            strip.alpha_composite(c, (int(k * cwid + cwid / 2 + bx - c.width / 2), chei - 2 - c.height))
        anchor = [cwid // 2, chei - 2]
    if name == 'fxDust':      # 흐려지는 컷에 남은 초록 기운 제거
        a = np.array(strip).astype(int); a[..., 1] = np.minimum(a[..., 1], np.maximum(a[..., 0], a[..., 2])); strip = Image.fromarray(a.astype(np.uint8), 'RGBA')
    fn = name + '.webp'; os.makedirs(OUT, exist_ok=True)
    strip.save(os.path.join(OUT, fn), 'WEBP', quality=88, method=6, alpha_quality=95)
    man[name] = dict(file=fn, frames=len(items), w=cwid, h=chei, fps=sp['fps'], anchor=anchor, loop=sp['loop'])

# 지형·배경
def build_terrain(raw, man):
    for rid, rn, *_ in REGIONS:
        # 발판 키트: 위(바닥 조각) · 가운데(떠 있는 발판) · 아래(벽 블록)
        rg = keyed(raw, 'plat' + rid); cells = cells_of(rg, (1, 3), dil=15)
        for nm, cell, hh, caps in (('ground', cells[0], 96, 20), ('plat', cells[1], 30, 10), ('block', cells[2], 64, 0)):
            b = bbox_of(cell)
            if b is None: raise SystemExit('빈 칸: ' + nm + rid)
            im = cell.crop(b); s = hh / im.height; im = im.resize((max(1, round(im.width * s)), hh), Image.LANCZOS)
            key = '%s%s' % (nm, rid); im.save(os.path.join(OUT, key + '.webp'), 'WEBP', quality=88, method=6, alpha_quality=95)
            top = int(np.argmax(np.array(im.getchannel('A')).max(axis=1) > 128))
            man[key] = dict(file=key + '.webp', frames=1, w=im.width, h=im.height, fps=0, anchor=[im.width // 2, top], cap=[caps, caps], top=top, loop=False)
        far = Image.open(load_pick(raw, 'far' + rid)).convert('RGB'); far = seamless(far, int(far.width * 0.12))
        far = far.resize((768, round(768 * far.height / far.width)), Image.LANCZOS)
        key = 'far' + rid; far.save(os.path.join(OUT, key + '.webp'), 'WEBP', quality=72, method=6)
        man[key] = dict(file=key + '.webp', frames=1, w=far.width, h=far.height, fps=0, anchor=[0, far.height], tile=True, loop=False)
        nr = keyed(raw, 'near' + rid); b = bbox_of(nr)
        nr = nr.crop((0, b[1], nr.width, b[3])); s = 0.55; nr = nr.resize((round(nr.width * s), round(nr.height * s)), Image.LANCZOS)
        key = 'near' + rid; nr.save(os.path.join(OUT, key + '.webp'), 'WEBP', quality=84, method=6, alpha_quality=90)
        man[key] = dict(file=key + '.webp', frames=1, w=nr.width, h=nr.height, fps=0, anchor=[0, nr.height], tile=True, loop=False)

def cmd_build(names, raw):
    man = {}; os.makedirs(OUT, exist_ok=True)
    for n, sp in SHEETS.items():
        if names and n not in names: continue
        if not os.path.exists(load_pick(raw, sp['job'])): print('원본 없음(건너뜀):', n); continue
        build_sheet(raw, n, sp, man); print('built', n, man[n]['frames'], 'frames', man[n]['w'], 'x', man[n]['h'])
    if not names or any(n.startswith(('plat', 'ground')) for n in names):
        if all(os.path.exists(load_pick(raw, 'plat' + r[0])) and os.path.exists(load_pick(raw, 'far' + r[0])) and os.path.exists(load_pick(raw, 'near' + r[0])) for r in REGIONS): build_terrain(raw, man)
    mp = os.path.join(OUT, 'manifest.json')
    old = json.load(open(mp)) if os.path.exists(mp) else {}
    old.update(man); old = {k: old[k] for k in sorted(old)}
    json.dump(old, open(mp, 'w'), ensure_ascii=False, indent=1); print('manifest', len(old), 'entries')

def cmd_sheet(raw):
    man = json.load(open(os.path.join(OUT, 'manifest.json')))
    groups = {'chick': [k for k in man if k.startswith('chick_')], 'mon': [k for k in man if k[0] == 'm' and k[1].isdigit()],
              'fx': [k for k in man if k.startswith(('fx', 'sk_'))], 'terrain': [k for k in man if k.startswith(('ground', 'plat', 'block', 'far', 'near'))]}
    for g, keys in groups.items():
        for tone, bgc in (('dark', (44, 46, 66)), ('light', (236, 232, 222))):
            rows = []
            for k in keys:
                m = man[k]; im = Image.open(os.path.join(OUT, m['file'])).convert('RGBA'); rows.append(im)
            if not rows: continue
            Wd = max(r.width for r in rows) + 8; Ht = sum(r.height + 6 for r in rows) + 6
            sh = Image.new('RGBA', (Wd, Ht), bgc + (255,)); y = 6
            for r in rows: sh.alpha_composite(r, (4, y)); y += r.height + 6
            if Wd > 1800: sh = sh.resize((1800, round(Ht * 1800 / Wd)))
            sh.convert('RGB').save(os.path.join(raw, 'contact_%s_%s.png' % (g, tone)))
            print('contact', g, tone, sh.size)

if __name__ == '__main__':
    a = sys.argv[1:]; cmd = a[0] if a else 'list'; raw = '/tmp/brjv2raw'; k = 1; names = []; i = 1
    while i < len(a):
        if a[i] == '--raw': raw = a[i + 1]; i += 2
        elif a[i] == '-k': k = int(a[i + 1]); i += 2
        else: names.append(a[i]); i += 1
    if cmd == 'gen': cmd_gen(names, k, raw)
    elif cmd == 'build': cmd_build(names, raw)
    elif cmd == 'sheet': cmd_sheet(raw)
    else:
        for n, j in JOBS.items(): print(n, j['size'], j['key'], j['grid'])
