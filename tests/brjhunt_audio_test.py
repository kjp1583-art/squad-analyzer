#!/usr/bin/env python3.13
"""brjhunt_audio.js v2 시험(Playwright + OfflineAudioContext). 사용:
  CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome python3.13 tests/brjhunt_audio_test.py [--shots 폴더]

소리를 귀로 들을 수는 없으니 **파형을 숫자로** 본다:
  - 효과음 전부(81종) · BGM 8트랙을 OfflineAudioContext 로 렌더 → 무음 아님 · 피크 <= 0.98(기본 볼륨, 그리고 마스터/효과음/BGM 1.0 최대 볼륨)
    · 직류 오프셋 없음 · NaN 없음 · 길이 · 꼬리가 끝에서 잘리지 않음 · 시작 클릭 없음
  - 서로 다른 소리인지(파형 해시 + 스펙트럼 상관) · 「묵직함」(타격음에 저음 쿵 + 고음 크랙 층이 같이 있는지) · 스킬 전조/발동/여운이 서로 다른지
  - 같은 소리 반복: 라운드 로빈(연속 호출이 서로 다른 파형) · 음높이/음량 흔들림 · 최소 간격으로 솎음 · 동시 발음 상한
  - 좌우 패닝 · 거리(작고 둔탁) · 스테레오 폭
  - BGM: 16마디 구성(인트로→A→B→A′→되돌림) · 템포 · 루프 이음매(인트로를 건너뛰고 A 로 돌아옴) · 강도 층 · 트랙끼리 BPM/조/악기 구성이 다름
  - 이름표 문서(docs/brjhunt_audio_sfx_names.md)가 실제 효과음 이름과 어긋나지 않는지
  - 파형 + 스펙트로그램을 PNG 로 저장(눈으로 확인용): <shots>/sfx_sheet_*.png, bgm_sheet.png
  - 라이브 동작: 제스처 전 무음(AudioContext 도 안 만듦) · 탭 숨김 정지/복귀 · 음소거 · 동시 발음 제한 · 볼륨 저장 ·
    localStorage 막힘/깨진 값에서도 동작 · BGM 전환 · onChange · 강도 설정
귀로 듣는 맛(타격감이 좋은가, 음악이 듣기 좋은가)은 이 시험이 보증하지 못한다 — 숫자와 그림으로만 본 것이다."""
import base64, hashlib, json, os, re, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else tempfile.mkdtemp(prefix='brjaudio_')
os.makedirs(SHOTS, exist_ok=True)
JS = os.path.join(ROOT, 'brjhunt_audio.js')
DOC = os.path.join(ROOT, 'docs', 'brjhunt_audio_sfx_names.md')
FAILS = []


def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' ' + str(x)) if x != '' and not c else ''))
    if not c:
        FAILS.append(n)


tmp = tempfile.mkdtemp(prefix='brjaudio_page_')
PAGE = os.path.join(tmp, 'page.html')
open(PAGE, 'w').write('<!doctype html><meta charset=utf-8><body><button id=b>x</button>'
                      '<script src="file://%s"></script></body>' % JS)
URL = 'file://' + PAGE
FLAGS = ['--autoplay-policy=user-gesture-required']
# AudioContext 생성 횟수 세기
COUNT_INIT = """(()=>{window.__acCount=0;const A=window.AudioContext;if(A){window.AudioContext=function(...a){window.__acCount++;return new A(...a)};window.AudioContext.prototype=A.prototype}})();"""
B64 = """()=>{window.__b64=(f)=>{const u=new Uint8Array(f.buffer,f.byteOffset,f.byteLength);let s='';for(let i=0;i<u.length;i+=0x8000)s+=String.fromCharCode.apply(null,u.subarray(i,i+0x8000));return btoa(s)}}"""


def render(page, opt):
    r = page.evaluate("""async (o)=>{const r=await BrjAudio._render(o);return {b:__b64(r.data),bR:__b64(r.dataR),played:r.played,dropped:r.dropped,sr:r.sampleRate,endPos:r.endPos,endStep:r.endStep}}""", opt)
    r['x'] = np.frombuffer(base64.b64decode(r['b']), dtype=np.float32).copy()
    r['xr'] = np.frombuffer(base64.b64decode(r['bR']), dtype=np.float32).copy()
    return r


# ------------------------------------------------------------------ 그림
def spectro(x, sr, w, h):
    """로그 크기 스펙트로그램 → (h, w) RGB"""
    n = 1024
    if len(x) < n * 2:
        x = np.pad(x, (0, n * 2 - len(x)))
    hop = max(1, (len(x) - n) // (w - 1))
    win = np.hanning(n)
    cols = []
    for i in range(w):
        s = i * hop
        seg = x[s:s + n]
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        cols.append(np.abs(np.fft.rfft(seg * win)))
    m = np.array(cols).T  # (513, w)
    db = 20 * np.log10(m + 1e-6)
    db = np.clip((db + 30) / 80, 0, 1)  # 상대 -30..+50 dB
    # 표시 주파수: 로그축 40Hz ~ 12kHz
    fr = np.fft.rfftfreq(n, 1 / sr)
    ys = np.geomspace(40, min(12000, sr / 2 * 0.95), h)
    img = np.zeros((h, w))
    for j, f in enumerate(ys):
        img[h - 1 - j] = db[int(np.clip(np.searchsorted(fr, f), 0, len(fr) - 1))]
    r = np.clip(img * 3 - 1, 0, 1); g = np.clip(img * 3 - 0.4, 0, 1) * 0.9; b = np.clip(0.3 + img * 1.5 - img ** 2 * 1.2, 0, 1) * (img > 0.02)
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)


def tile(name, x, sr, w, h, note=''):
    im = Image.new('RGB', (w, h), (14, 14, 22))
    d = ImageDraw.Draw(im)
    wh = int(h * 0.38)
    # 파형(구간별 최소/최대)
    mid = 14 + wh // 2
    seg = np.array_split(x, w)
    for i, s in enumerate(seg):
        if len(s):
            d.line([(i, mid - int(np.clip(s.max(), -1, 1) * wh / 2)), (i, mid - int(np.clip(s.min(), -1, 1) * wh / 2))], fill=(120, 220, 140))
    d.line([(0, mid), (w, mid)], fill=(50, 50, 70))
    sp = spectro(x, sr, w, h - 14 - wh - 2)
    im.paste(Image.fromarray(sp), (0, 14 + wh + 2))
    d.text((3, 1), '%s  %s' % (name, note), fill=(255, 255, 255))
    return im


def sheet(tiles, cols, path):
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new('RGB', (cols * tw, rows * th), (0, 0, 0))
    for i, t in enumerate(tiles):
        im.paste(t, ((i % cols) * tw, (i // cols) * th))
    im.save(path)


def stats(x):
    a = np.abs(x)
    return dict(peak=float(a.max()), rms=float(np.sqrt(np.mean(x.astype(np.float64) ** 2))), dc=float(np.mean(x, dtype=np.float64)),
                nan=bool(np.isnan(x).any() or np.isinf(x).any()), clip=int((a > 0.95).sum()))


def centroid(x, sr):
    m = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float((m * f).sum() / max(m.sum(), 1e-12))


def band_vec(x, sr, n=24):
    m = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    edges = np.geomspace(40, 12000, n + 1)
    v = np.array([m[(f >= edges[i]) & (f < edges[i + 1])].sum() for i in range(n)]) + 1e-12
    v = np.log(v)
    return v - v.mean()




def lowhigh(x, sr, n=None):
    x = x[:n] if n else x
    m = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    tot = m.sum() + 1e-18
    return float(m[f < 250].sum() / tot), float(m[f > 2000].sum() / tot)


def main():
    chrome = os.environ.get('CHROME')
    with sync_playwright() as p:
        br = p.chromium.launch(**({'executable_path': chrome} if chrome else {}), args=FLAGS)
        ctx = br.new_context()
        ctx.add_init_script(COUNT_INIT)
        page = ctx.new_page()
        errs = []
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        page.goto(URL)
        page.evaluate(B64)

        names = page.evaluate('BrjAudio.sfxNames()')
        tracks = page.evaluate('BrjAudio.trackNames()')
        SK = 'slash peck spin bomb thunder fire egg shield shrimp storm'.split()
        old_names = ['hit', 'crit', 'kill', 'coin', 'levelup', 'boss_in', 'boss_win', 'boss_lose', 'click', 'tab', 'error', 'summon', 'summon_rare',
                     'enhance_ok', 'enhance_fail', 'awaken'] + ['skill_' + s for s in SK]
        new_names = (['swing1', 'swing2', 'swing3', 'swing_big', 'hit_heavy', 'mon_hurt', 'mon_die', 'mon_die_elite', 'elite_spawn', 'coin_big', 'coin_drop', 'pickup',
                      'jump', 'jump2', 'land', 'land_hard', 'step', 'drop_down', 'hurt', 'hurt_heavy', 'shield_block', 'die', 'revive', 'combo_up',
                      'ui_open', 'ui_close', 'auto_on', 'auto_off', 'equip', 'no_mp', 'skill_ready', 'boss_warn', 'boss_rage', 'boss_slam', 'boss_die']
                     + ['skill_%s_%s' % (s, ph) for s in SK for ph in ('charge', 'tail')])
        need_bgm = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'boss', 'menu']
        check('예전 효과음 26종 이름이 그대로 살아 있다', set(old_names) <= set(names), set(old_names) - set(names))
        check('새 효과음 이름 전부(%d종)' % len(new_names), set(new_names) <= set(names), set(new_names) - set(names))
        check('효과음 이름 중복 없음 · 총 %d종' % len(names), len(set(names)) == len(names) and len(names) == len(old_names) + len(new_names), len(names))
        check('BGM 트랙 8종 전부', sorted(tracks) == sorted(need_bgm), tracks)
        check('전역 API 모양(계약 + setIntensity/skillSfx)', page.evaluate("['unlock','sfx','bgm','setMaster','setSfx','setBgm','muted','state','onChange','sfxNames','trackNames','setIntensity','skillSfx'].every(k=>typeof BrjAudio[k]==='function')"))
        check('skillSfx 이름 규칙', page.evaluate("[BrjAudio.skillSfx('fire','charge'),BrjAudio.skillSfx('fire','cast'),BrjAudio.skillSfx('fire','tail'),BrjAudio.skillSfx('nope','cast')]") == ['skill_fire_charge', 'skill_fire', 'skill_fire_tail', None])
        st = page.evaluate('BrjAudio.state()')
        check('기본 볼륨 마스터 0.6 · BGM 0.35 · 음소거 아님', st['master'] == 0.6 and st['bgm'] == 0.35 and st['muted'] is False, st)

        # ---------------------------------------------------------- 이름표 문서
        doc = open(DOC, encoding='utf-8').read()
        tail_names = set(re.findall(r'^\| `([a-z0-9_]+)` \| [0-9.]+ \| \d \| ', doc, re.M))
        check('이름표 문서의 효과음 목록 == 실제 효과음 목록', tail_names == set(names), (set(names) ^ tail_names))

        # ---------------------------------------------------------- 효과음 파형
        print('\n== 효과음 렌더 ==')
        SR = 44100
        tiles = []
        sfx_wavs = {}; bands = {}; lh = {}
        for n in names:
            dur = page.evaluate('BrjAudio._sfxDur(%s)' % json.dumps(n))
            secs = dur + 0.5
            r = render(page, {'sfx': [{'name': n, 'at': 0.02}], 'seconds': secs, 'sampleRate': SR, 'seed': 7})
            x = r['x']; s = stats(x)
            sfx_wavs[n] = x
            check('sfx %s 길이 %.2fs' % (n, secs), abs(len(x) - int(np.ceil(SR * secs))) <= 1 and r['played'] == 1)
            check('sfx %s 무음 아님(피크 %.2f)' % (n, s['peak']), s['peak'] >= 0.05 and s['rms'] > 0.003, s)
            check('sfx %s 클리핑 없음 피크<=0.98' % n, s['peak'] <= 0.98 and s['clip'] == 0 and not s['nan'], s)
            act = x[:int((dur + 0.1) * SR)]
            check('sfx %s 직류 없음(|평균| %.4f)' % (n, abs(act.mean())), abs(act.mean()) < 0.01, act.mean())
            check('sfx %s 시작 클릭 없음' % n, abs(float(x[0])) < 0.03)
            tail = np.abs(x[-int(0.05 * SR):]).max()
            check('sfx %s 꼬리가 끝에서 잘리지 않음(%.4f)' % (n, tail), tail < 0.02, tail)
            rm = render(page, {'sfx': [{'name': n, 'at': 0.02}], 'seconds': secs, 'sampleRate': SR, 'seed': 7,
                               'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
            check('sfx %s 최대 볼륨에서도 피크<=0.98 (%.3f)' % (n, np.abs(rm['x']).max()), np.abs(rm['x']).max() <= 0.98)
            bands[n] = np.concatenate([band_vec(x[int(u * SR):int(v * SR)], SR, 16) for u, v in ((0, 0.12), (0.12, 0.3), (0.3, 0.9))])
            lh[n] = lowhigh(x[:int(0.4 * SR)], SR)
            tiles.append(tile(n, x, SR, 260, 130, 'pk %.2f c%dHz' % (s['peak'], centroid(act, SR))))
        per = 24
        for i in range(0, len(tiles), per):
            sheet(tiles[i:i + per], 4, os.path.join(SHOTS, 'sfx_sheet_%d.png' % (i // per + 1)))
        hs = {hashlib.sha1(v.tobytes()).hexdigest() for v in sfx_wavs.values()}
        check('효과음 %d종 파형이 모두 서로 다름' % len(names), len(hs) == len(sfx_wavs))
        worst = max(((float(np.corrcoef(bands[a], bands[b])[0, 1]), a, b) for i, a in enumerate(names) for b in names[i + 1:]))
        print('   가장 비슷한 두 소리(스펙트럼 상관): %.3f %s ~ %s' % worst)
        check('서로 다른 효과음의 스펙트럼이 같지 않음(최대 상관 %.4f)' % worst[0], worst[0] < 0.995, worst)
        # 스킬 3단(전조·발동·여운)이 서로 다름
        for s in SK:
            tri = ['skill_%s_charge' % s, 'skill_%s' % s, 'skill_%s_tail' % s]
            cs = [float(np.corrcoef(bands[a], bands[b])[0, 1]) for i, a in enumerate(tri) for b in tri[i + 1:]]
            check('스킬 %s 전조·발동·여운이 서로 다른 소리(상관 최대 %.2f)' % (s, max(cs)), max(cs) < 0.97, cs)
        # 묵직함: 타격류는 저음 쿵(250Hz 아래)과 고음 크랙(2kHz 위)이 같이 있어야
        for n, lo_min, hi_min in [('hit', 0.25, 0.01), ('hit_heavy', 0.4, 0.003), ('crit', 0.2, 0.02), ('boss_slam', 0.5, 0.01), ('skill_bomb', 0.5, 0.003), ('mon_die', 0.3, 0.01)]:
            lo, hi = lh[n]
            check('%s 묵직함: 저음층 %.2f >= %.2f · 크랙층 %.3f >= %.3f' % (n, lo, lo_min, hi, hi_min), lo >= lo_min and hi >= hi_min, lh[n])
        # 휘두름은 바람 소리 — 저음 쿵이 지배적이면 안 됨
        for n in ['swing1', 'swing2', 'skill_slash_charge']:
            check('%s 휘두름은 고음 노이즈 위주(저음 %.2f < 0.5)' % (n, lh[n][0]), lh[n][0] < 0.5, lh[n])

        # ---------------------------------------------------------- 같은 소리 반복 · 변주
        print('\n== 반복 · 변주 ==')
        seq = [{'name': 'hit', 'at': 0.1 + i * 0.25} for i in range(9)]
        r = render(page, {'sfx': seq, 'seconds': 2.8, 'sampleRate': SR, 'seed': 5})
        segs = [r['x'][int((0.1 + i * 0.25) * SR):int((0.1 + i * 0.25 + 0.2) * SR)] for i in range(9)]
        check('타격음 9연타: 모두 재생(%d)' % r['played'], r['played'] == 9)
        hh = {hashlib.sha1(sg.tobytes()).hexdigest() for sg in segs}
        check('타격음 9연타가 전부 다른 파형(라운드 로빈 + 흔들림)', len(hh) == 9)
        cents = [centroid(sg, SR) for sg in segs]
        pks = [float(np.abs(sg).max()) for sg in segs]
        check('연타 사이 음색(무게중심)이 달라진다 — 최대/최소 %.2f' % (max(cents) / min(cents)), max(cents) / min(cents) > 1.06, cents)
        check('연타 사이 음량이 조금씩 다르되 크게 튀지 않음 — 최대/최소 %.2f' % (max(pks) / min(pks)), 1.03 < max(pks) / min(pks) < 2.0, pks)
        a = render(page, {'sfx': [{'name': 'hit', 'at': 0.02}], 'seconds': 0.4, 'seed': 1})['x']
        b = render(page, {'sfx': [{'name': 'hit', 'at': 0.02}], 'seconds': 0.4, 'seed': 2})['x']
        c = render(page, {'sfx': [{'name': 'hit', 'at': 0.02}], 'seconds': 0.4, 'seed': 1})['x']
        check('같은 시드는 (거의)같은 파형 · 다른 시드는 다른 파형(최대 차이 %.2g / %.2g)' % (np.abs(a - c).max(), np.abs(a - b).max()), np.abs(a - c).max() < 2e-4 and np.abs(a - b).max() > 1e-2)
        lo = render(page, {'sfx': [{'name': 'coin', 'at': 0.02, 'rate': 0.5}], 'seconds': 0.9})['x']
        hi = render(page, {'sfx': [{'name': 'coin', 'at': 0.02, 'rate': 2}], 'seconds': 0.9})['x']
        check('rate 옵션이 음높이를 바꾼다(코인 0.5x < 2x)', centroid(lo, SR) < centroid(hi, SR) * 0.7, (centroid(lo, SR), centroid(hi, SR)))
        q = render(page, {'sfx': [{'name': 'coin', 'at': 0.02, 'vol': 0.25}], 'seconds': 0.9})['x']
        full = sfx_wavs['coin']
        check('vol 옵션이 음량을 바꾼다', 0.1 < np.abs(q).max() / np.abs(full).max() < 0.6, np.abs(q).max() / np.abs(full).max())
        # 최소 간격
        r = render(page, {'sfx': [{'name': 'hit', 'at': 0.5 + i * 0.001} for i in range(40)], 'seconds': 1.5})
        check('같은 효과음 40연타(1ms 간격) → 최소 간격으로 솎음(재생 %d)' % r['played'], r['played'] <= 2, r['played'])
        for n in ['hit', 'coin', 'swing1', 'kill', 'step', 'click']:
            g = page.evaluate('BrjAudio._sfxMeta(%s).gap' % json.dumps(n))
            r = render(page, {'sfx': [{'name': n, 'at': 0.1 + i * (g * 0.5)} for i in range(10)], 'seconds': 1.2})
            r2 = render(page, {'sfx': [{'name': n, 'at': 0.1 + i * (g * 1.2)} for i in range(10)], 'seconds': 1.2})
            check('%s 간격 %.3fs: 절반 간격이면 솎아내고(%d/10) 1.2배 간격이면 전부 재생(%d/10)' % (n, g, r['played'], r2['played']), r['played'] <= 6 and r2['played'] == 10, (r['played'], r2['played']))
        # 분당 100마리 수준
        ev = []
        for i in range(60):
            t0 = 0.1 + i * 0.6
            ev += [{'name': 'hit', 'at': t0}, {'name': 'mon_die', 'at': t0 + 0.15}, {'name': 'coin', 'at': t0 + 0.3}]
        r = render(page, {'sfx': ev, 'seconds': 37, 'sampleRate': 22050})
        check('분당 100마리 수준(60킬/36초) 연출에서 전부 재생(%d/%d)' % (r['played'], len(ev)), r['played'] == len(ev), (r['played'], r['dropped']))
        # 난전: 0.8초 안에 여러 마리 + 스킬 겹침 → 상한 안에서 솎임, 클리핑 없음
        ev = [{'name': n, 'at': 0.05 + (i % 8) * 0.012} for i, n in enumerate(['hit', 'crit', 'mon_die', 'coin', 'skill_fire', 'skill_thunder', 'hurt', 'swing3'] * 6)]
        r = render(page, {'sfx': ev, 'seconds': 2, 'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
        check('난전(48호출/0.1초) 피크<=0.98 · 상한 안에서 재생(%d)' % r['played'], np.abs(r['x']).max() <= 0.98 and r['played'] <= 24, (np.abs(r['x']).max(), r['played']))

        # ---------------------------------------------------------- 패닝 · 거리
        print('\n== 패닝 · 거리 ==')
        def rms(v): return float(np.sqrt(np.mean(v.astype(np.float64) ** 2)))
        rl = render(page, {'sfx': [{'name': 'hit_heavy', 'at': 0.02, 'pan': -1}], 'seconds': 1})
        rr = render(page, {'sfx': [{'name': 'hit_heavy', 'at': 0.02, 'pan': 1}], 'seconds': 1})
        rc = render(page, {'sfx': [{'name': 'hit_heavy', 'at': 0.02, 'pan': 0}], 'seconds': 1})
        check('pan -1: 왼쪽이 오른쪽보다 큼(%.3f vs %.3f)' % (rms(rl['x']), rms(rl['xr'])), rms(rl['x']) > rms(rl['xr']) * 2.5)
        check('pan +1: 오른쪽이 왼쪽보다 큼', rms(rr['xr']) > rr['x'].std() * 2.5)
        check('pan 0: 좌우 비슷함', 0.8 < rms(rc['x']) / rms(rc['xr']) < 1.25, (rms(rc['x']), rms(rc['xr'])))
        rx = render(page, {'sfx': [{'name': 'hit_heavy', 'at': 0.02, 'x': 0.8}], 'seconds': 1})
        check('x=0.8(화면 오른쪽 몬스터) → 오른쪽으로 치우침', rms(rx['xr']) > rms(rx['x']) * 1.5)
        rd = render(page, {'sfx': [{'name': 'hit_heavy', 'at': 0.02, 'dist': 1}], 'seconds': 1})
        check('dist 1: 더 작다(%.2f배)' % (rms(rd['x']) / rms(rc['x'])), rms(rd['x']) < rms(rc['x']) * 0.8)
        check('dist 1: 더 둔탁하다(무게중심 %d → %d Hz)' % (centroid(rc['x'][:SR // 2], SR), centroid(rd['x'][:SR // 2], SR)), centroid(rd['x'][:SR // 2], SR) < centroid(rc['x'][:SR // 2], SR))

        # ---------------------------------------------------------- BGM 파형
        print('\n== BGM 렌더(32초) ==')
        btiles = []; vecs = {}; hashes = {}; infos = {}; SB = 22050
        for t in tracks:
            infos[t] = page.evaluate('BrjAudio._trackInfo(%s)' % json.dumps(t))
            ti = infos[t]
            secs = 32
            r = render(page, {'bgm': t, 'seconds': secs, 'sampleRate': SB, 'seed': 3})
            x = r['x']; s = stats(x)
            check('bgm %s 길이 %d초' % (t, secs), len(x) == SB * secs)
            check('bgm %s 무음 아님(피크 %.2f · rms %.3f)' % (t, s['peak'], s['rms']), s['peak'] >= 0.05 and s['rms'] >= 0.015, s)
            check('bgm %s 피크<=0.98 · NaN 없음' % t, s['peak'] <= 0.98 and s['clip'] == 0 and not s['nan'], s)
            check('bgm %s 직류 없음(%.4f)' % (t, s['dc']), abs(s['dc']) < 0.01, s['dc'])
            segs = [rms(x[i * 2 * SB:(i + 1) * 2 * SB]) for i in range(secs // 2)]
            check('bgm %s 2초 구간마다 소리가 있다(최소 %.3f)' % (t, min(segs)), min(segs) > 0.004, [round(v, 3) for v in segs])
            rm = render(page, {'bgm': t, 'seconds': 16, 'sampleRate': SB, 'seed': 3, 'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
            check('bgm %s 최대 볼륨 피크<=0.98 (%.3f)' % (t, np.abs(rm['x']).max()), np.abs(rm['x']).max() <= 0.98)
            check('bgm %s 스테레오 폭(좌우 상관 %.3f < 0.99)' % (t, float(np.corrcoef(x, r['xr'])[0, 1])), float(np.corrcoef(x, r['xr'])[0, 1]) < 0.99)
            hashes[t] = hashlib.sha1(x.tobytes()).hexdigest(); vecs[t] = band_vec(x, SB)
            btiles.append(tile(t, x, SB, 640, 190, 'pk %.2f rms %.3f c%dHz bpm %d' % (s['peak'], s['rms'], centroid(x, SB), ti['bpm'])))
        sheet(btiles, 2, os.path.join(SHOTS, 'bgm_sheet.png'))
        check('BGM 8트랙 파형이 모두 다름', len(set(hashes.values())) == len(tracks))
        worst = max(float(np.corrcoef(vecs[a], vecs[b])[0, 1]) for i, a in enumerate(tracks) for b in tracks[i + 1:])
        check('BGM 트랙끼리 음색(스펙트럼)이 충분히 다름(최대 상관 %.3f)' % worst, worst < 0.995, worst)
        bpms = [infos[t]['bpm'] for t in tracks]
        check('지역 6곡 BPM 80~128 · 모두 다름 %s' % bpms[:6], all(80 <= b <= 128 for b in bpms[:6]) and len(set(bpms[:6])) == 6, bpms)
        check('보스곡이 지역곡보다 빠름(%d)' % infos['boss']['bpm'], infos['boss']['bpm'] > max(bpms[:6]))
        keys = [(infos[t]['root'] % 12, infos[t]['sc']) for t in tracks]
        check('트랙마다 조(으뜸음+음계)가 다름', len(set(keys)) == len(keys), keys)
        combo = [(infos[t]['bass'], infos[t]['pad'], infos[t]['arp'], infos[t]['lead']) for t in tracks]
        check('트랙마다 악기 구성(베이스·패드·아르페지오·리드)이 다름', len(set(combo)) == len(combo), combo)
        check('지역 6곡에서 리드 악기가 4종 이상', len({infos[t]['lead'] for t in tracks[:6]}) >= 4)

        # 구성: 인트로(킥·스네어·리드 없음) < A < B 의 에너지, 16마디가 한 바퀴
        print('\n== BGM 구성 · 템포 · 이음매 ==')
        for t in ['field1', 'field3', 'field6', 'boss']:
            ti = infos[t]; bs = ti['barSec']
            r = render(page, {'bgm': t, 'seconds': bs * 16, 'sampleRate': 22050, 'seed': 3})
            x = r['x']; sr2 = 22050
            def bar_rms(a, b2): return rms(x[int(a * bs * sr2):int(b2 * bs * sr2)])
            intro, A, B, A2 = bar_rms(0.2, 2), bar_rms(2, 6), bar_rms(6, 10), bar_rms(10, 14)
            check('%s 인트로(%.3f)는 본 악절 A(%.3f)보다 조용하다' % (t, intro, A), intro < A * 0.85, (intro, A))
            check('%s B 악절(%.3f)이 A(%.3f)보다 같거나 센 에너지' % (t, B, A), B > A * 0.9, (B, A))
            check('%s A′(%.3f) 는 A 와 같은 계열 에너지(0.6~1.6배)' % (t, A2), 0.6 < A2 / A < 1.6)
        # 템포: 네 박 킥 곡(field3, 112bpm) 에서 포락선 자기상관 주기 = 박의 배수
        ti = infos['field3']
        x = render(page, {'bgm': 'field3', 'seconds': 24, 'sampleRate': 22050, 'seed': 3, 'intensity': 0.45})['x']
        lp = np.abs(x[:len(x) // 110 * 110]).reshape(-1, 110).max(1); lp = lp - lp.mean()
        ac = np.correlate(lp, lp, 'full')[len(lp) - 1:]
        lo_i, hi_i = int(0.3 / 0.005), int(1.2 / 0.005)
        pk = (np.argmax(ac[lo_i:hi_i]) + lo_i) * 0.005
        beat = 60 / ti['bpm']
        check('field3 박 주기 ≈ %.3fs 의 배수(측정 %.3f)' % (beat, pk), abs(pk / beat - round(pk / beat)) < 0.1 and pk > 0.3, pk)
        # 루프 이음매: 14마디 위치에서 시작해 A 로 넘어가는 지점
        for t in tracks:
            ti = infos[t]; bs = ti['barSec']; sd = ti['sd']
            r = render(page, {'bgm': t, 'seconds': bs * 6, 'sampleRate': 22050, 'seed': 3, 'bgmPos': 14 * 16})
            x = r['x']; s = stats(x)
            check('bgm %s 이음매: 16마디가 끝나면 인트로(0~31칸)가 아니라 A(32칸~)로 돌아옴(끝 위치 %d)' % (t, r['endPos']), 32 <= r['endPos'] < 32 + 16 * 4 + 20, r['endPos'])
            seam = 2 * bs
            w = int(0.25 * 22050)
            before, after = rms(x[int(seam * 22050) - w:int(seam * 22050)]), rms(x[int(seam * 22050):int(seam * 22050) + w])
            ratio = after / max(before, 1e-9)
            check('bgm %s 이음매 앞뒤 소리 크기가 이어짐(%.3f→%.3f, %.2f배)' % (t, before, after, ratio), 0.3 < ratio < 4.0 and before > 0.01 and after > 0.01, (before, after))
            check('bgm %s 이음매 구간 피크 정상·NaN 없음' % t, s['peak'] <= 0.98 and not s['nan'])
            win = [rms(x[int(i * 22050 * 0.5):int((i + 1) * 22050 * 0.5)]) for i in range(int(bs * 6 / 0.5) - 1)]
            check('bgm %s 이음매 주변 0.5초 창에 끊기는 곳 없음(최소 %.3f)' % (t, min(win)), min(win) > 0.2 * float(np.median(win)), (min(win), float(np.median(win))))

        # 강도: 켜지는 층이 늘수록 소리가 두꺼워진다
        for t in ['field2', 'field5', 'boss']:
            rs = []
            ce = []
            for I in [0, 0.3, 0.6, 1.0]:
                x = render(page, {'bgm': t, 'seconds': 14, 'sampleRate': 22050, 'seed': 3, 'intensity': I, 'bgmPos': 2 * 16 * 4})['x']
                rs.append(rms(x)); ce.append(centroid(x, 22050))
            mono = all(rs[i] <= rs[i + 1] * 1.03 for i in range(3))
            check('%s 강도 0→1 에서 에너지가 늘어남 %s' % (t, [round(v, 3) for v in rs]), mono and rs[3] > rs[0] * 1.15, rs)
            check('%s 강도 1 이 0 보다 음색이 밝다(무게중심 %d→%d Hz)' % (t, ce[0], ce[3]), ce[3] > ce[0] * 1.1, ce)
            check('%s 강도 0 에서도 소리가 난다(패드·베이스)' % t, rs[0] > 0.01, rs[0])

        # ---------------------------------------------------------- 동시 발음 제한(오프라인)
        print('\n== 동시 발음 ==')
        burst = [{'name': n, 'at': 0.05} for n in names]
        r = render(page, {'sfx': burst, 'seconds': 2, 'sampleRate': SR, 'seed': 5, 'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
        check('%d종 동시 발사 → 상한(<=24) 안에서 나머지는 버려짐(재생 %d · 버림 %d)' % (len(names), r['played'], r['dropped']), r['played'] <= 24 and r['dropped'] >= len(names) - 24 and r['played'] >= 10, (r['played'], r['dropped']))
        check('동시 발사해도 피크<=0.98', np.abs(r['x']).max() <= 0.98, np.abs(r['x']).max())
        r = render(page, {'sfx': [{'name': 'skill_fire', 'at': 0.1 + i * 0.002} for i in range(30)] + [{'name': n, 'at': 0.1} for n in ['boss_in', 'levelup']], 'seconds': 1.5})
        check('중요 소리(보스 입장·레벨업)는 스킬이 가득 차도 밀려나지 않음', r['played'] >= 2 and r['played'] <= 24)
        r = render(page, {'sfx': [{'name': 'step', 'at': 0.1 + i * 0.01} for i in range(30)] + [{'name': 'boss_in', 'at': 0.5}], 'seconds': 4})
        check('일반 소리가 아무리 쏟아져도 보스 입장음은 재생됨', r['played'] >= 2, r['played'])


        # ---------------------------------------------------------- 라이브: 제스처 전 무음
        print('\n== 라이브 동작 ==')
        d = page.evaluate('BrjAudio._debug()')
        check('제스처 전: AudioContext 안 만듦', page.evaluate('window.__acCount') == 0 and d['ctxState'] is None, d)
        check('제스처 전: sfx() 는 false(소리 안 냄)', page.evaluate("BrjAudio.sfx('click')") is False)
        page.evaluate("BrjAudio.bgm('field1')")
        d = page.evaluate('BrjAudio._debug()')
        check('제스처 전: bgm() 은 기억만(재생·컨텍스트 없음)', d['want'] == 'field1' and d['track'] is None and page.evaluate('window.__acCount') == 0, d)
        page.click('#b')  # 실제 클릭(사용자 제스처)
        page.wait_for_timeout(500)
        d = page.evaluate('BrjAudio._debug()')
        check('첫 클릭 뒤: 스스로 잠금 해제 · 컨텍스트 running', d['unlocked'] and d['ctxState'] == 'running' and page.evaluate('window.__acCount') == 1, d)
        check('첫 클릭 뒤: 기억해 둔 BGM(field1)이 시작됨', d['track'] == 'field1' and d['timer'], d)
        check('첫 클릭 뒤: sfx() true', page.evaluate("BrjAudio.sfx('click')") is True)
        check('모르는 효과음 이름은 false · 예외 없음', page.evaluate("BrjAudio.sfx('nope')") is False)
        page.wait_for_timeout(1500)
        d2 = page.evaluate('BrjAudio._debug()')
        check('BGM 스케줄러가 실제로 칸을 진행(step %d → %d)' % (d['step'], d2['step']), d2['step'] > d['step'] + 6, (d, d2))
        check('음소거 아닐 때 마스터 게인 = 0.6', abs(d2['masterGain'] - 0.6) < 0.01, d2['masterGain'])

        # 동시 발음(라이브)
        page.wait_for_timeout(2500)  # 앞선 소리 정리
        r = page.evaluate("""()=>{const n=BrjAudio.sfxNames();const before=BrjAudio._debug();let ok=0;for(let k=0;k<3;k++)for(const s of n)if(BrjAudio.sfx(s))ok++;
          const d=BrjAudio._debug();let hit=0;for(let i=0;i<50;i++)if(BrjAudio.sfx('hit'))hit++;return {ok,active:d.active,dropped:d.dropped-before.dropped,hit}}""")
        check('라이브: 한꺼번에 3×전체 호출해도 동시 발음 <= 24 (활성 %d · 허용 %d · 버림 %d)' % (r['active'], r['ok'], r['dropped']), r['active'] <= 24 and r['dropped'] > 20, r)
        check('라이브: 같은 이름 50연타는 한두 번만', r['hit'] <= 1, r['hit'])

        # BGM 전환
        page.evaluate("BrjAudio.bgm('boss')"); page.wait_for_timeout(300)
        check('BGM 전환 field1 → boss', page.evaluate('BrjAudio._debug().track') == 'boss')
        page.evaluate("BrjAudio.bgm('nope')")
        check('모르는 트랙은 무시(boss 유지)', page.evaluate('BrjAudio._debug().track') == 'boss')
        page.evaluate("BrjAudio.bgm('field3')"); page.wait_for_timeout(200)
        check('BGM 전환 boss → field3', page.evaluate('BrjAudio._debug().track') == 'field3')

        # 강도(라이브)
        page.evaluate("BrjAudio.setIntensity(0.1)"); page.wait_for_timeout(1200)
        l0 = page.evaluate('BrjAudio._debug().layers')
        page.evaluate("BrjAudio.setIntensity(1)"); page.wait_for_timeout(1500)
        l1 = page.evaluate('BrjAudio._debug().layers')
        check('라이브 강도: 0.1 에서는 위층(킥·아르페지오·리드·심벌)이 꺼지고 1 에서 모두 켜짐', l0[3] < 0.2 and l0[5] < 0.2 and l0[6] < 0.2 and all(v > 0.9 for v in l1), (l0, l1))
        check('라이브 강도: state().intensity 반영 · 범위 보정', page.evaluate("BrjAudio.setIntensity(7)") == 1 and page.evaluate("BrjAudio.state().intensity") == 1 and page.evaluate("BrjAudio.setIntensity('x')") == 1)
        page.evaluate("BrjAudio.setIntensity(0.9)")

        # onChange
        page.evaluate("window.__ch=[];window.__off=BrjAudio.onChange(s=>__ch.push(s));BrjAudio.setBgm(0.5);BrjAudio.setSfx(0.7);BrjAudio.setMaster(0.45);")
        ch = page.evaluate('window.__ch')
        check('onChange: 볼륨 변경 3번 통지', len(ch) == 3 and ch[-1]['master'] == 0.45 and ch[0]['bgm'] == 0.5, ch)
        page.evaluate("__off();BrjAudio.setBgm(0.4)")
        check('onChange: 해제 뒤엔 통지 없음', len(page.evaluate('window.__ch')) == 3)
        page.evaluate("BrjAudio.setMaster(99);BrjAudio.setSfx(-3);BrjAudio.setBgm('x')")
        st = page.evaluate('BrjAudio.state()')
        check('볼륨 범위 밖/이상한 값은 0~1 로 보정·무시', st['master'] == 1 and st['sfx'] == 0 and st['bgm'] == 0.4, st)
        page.evaluate("BrjAudio.setMaster(0.45);BrjAudio.setSfx(0.7);BrjAudio.setBgm(0.4)")

        # 탭 숨김
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(400)
        d = page.evaluate('BrjAudio._debug()')
        check('탭 숨김: 컨텍스트 suspended · 스케줄러 멈춤', d['ctxState'] == 'suspended' and d['timer'] is False, d)
        before = page.evaluate('BrjAudio._debug().played')
        check('탭 숨김: sfx() 는 false · 재생 수 그대로', page.evaluate("BrjAudio.sfx('coin')") is False and page.evaluate('BrjAudio._debug().played') == before)
        t_a = page.evaluate('BrjAudio._debug().time'); page.wait_for_timeout(500)
        check('탭 숨김: 오디오 시계가 멈춰 있음', page.evaluate('BrjAudio._debug().time') == t_a)
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(700)
        d = page.evaluate('BrjAudio._debug()')
        check('탭 복귀: running · 스케줄러 재개 · 같은 트랙(field3) 계속', d['ctxState'] == 'running' and d['timer'] and d['track'] == 'field3', d)
        s0 = d['step']; page.wait_for_timeout(1000)
        check('탭 복귀: 칸 진행 재개', page.evaluate('BrjAudio._debug().step') > s0 + 4)
        check('탭 복귀: sfx() true', page.evaluate("BrjAudio.sfx('coin')") is True)

        # 음소거
        page.evaluate("BrjAudio.muted(true)"); page.wait_for_timeout(400)
        d = page.evaluate('BrjAudio._debug()')
        check('음소거: muted()==true · 컨텍스트 suspended · 스케줄러 멈춤 · sfx false',
              page.evaluate('BrjAudio.muted()') is True and d['ctxState'] == 'suspended' and d['timer'] is False and page.evaluate("BrjAudio.sfx('coin')") is False, d)
        saved = page.evaluate("localStorage.getItem('brjhunt_audio_v1')")
        check('음소거·볼륨이 localStorage 에 저장됨', json.loads(saved) == {'master': 0.45, 'sfx': 0.7, 'bgm': 0.4, 'muted': True}, saved)
        page.evaluate("BrjAudio.bgm('field5')")
        page.evaluate("BrjAudio.muted('toggle')"); page.wait_for_timeout(800)
        d = page.evaluate('BrjAudio._debug()')
        check('음소거 해제(toggle): running · 음소거 중 요청한 BGM(field5)이 시작', d['ctxState'] == 'running' and page.evaluate('BrjAudio.muted()') is False and d['track'] == 'field5', d)

        # 새로고침 뒤 저장값 복원(여전히 첫 제스처 전엔 무음)
        page.evaluate("BrjAudio.muted(true)")
        page.reload(); page.evaluate(B64)
        st = page.evaluate('BrjAudio.state()')
        check('새로고침: 볼륨·음소거 복원', st['master'] == 0.45 and st['sfx'] == 0.7 and st['bgm'] == 0.4 and st['muted'] is True and not st['unlocked'], st)
        page.click('#b'); page.wait_for_timeout(400)
        d = page.evaluate('BrjAudio._debug()')
        check('저장된 음소거 상태에서 첫 클릭 → 잠금은 풀리되 소리는 안 남', d['unlocked'] and d['ctxState'] == 'suspended' and page.evaluate("BrjAudio.sfx('click')") is False, d)
        page.evaluate("BrjAudio.muted(false)"); page.wait_for_timeout(400)
        check('음소거 풀면 소리 남', page.evaluate("BrjAudio.sfx('click')") is True)
        check('페이지 오류·콘솔 오류 없음', not errs, errs)
        ctx.close()

        # ---------------------------------------------------------- localStorage 문제
        print('\n== localStorage 막힘/깨짐 ==')
        def fresh(init):
            c = br.new_context(); c.add_init_script(init); pg = c.new_page(); er = []
            pg.on('pageerror', lambda e: er.append(str(e))); pg.goto(URL); return c, pg, er
        # (1) window.localStorage 접근 자체가 던짐
        c, pg, er = fresh("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('denied','SecurityError')}})")
        st = pg.evaluate('BrjAudio.state()')
        check('localStorage 접근 거부: 기본값으로 로드', st['master'] == 0.6 and st['bgm'] == 0.35 and st['muted'] is False, st)
        pg.evaluate("BrjAudio.setMaster(0.2);BrjAudio.muted(true);BrjAudio.muted(false)")
        check('localStorage 접근 거부: 설정 변경은 메모리에서 정상(저장만 건너뜀)', pg.evaluate('BrjAudio.state().master') == 0.2)
        pg.click('#b'); pg.wait_for_timeout(300)
        check('localStorage 접근 거부: 소리는 그대로 남', pg.evaluate("BrjAudio.sfx('click')") is True and pg.evaluate('BrjAudio._debug().ctxState') == 'running')
        check('localStorage 접근 거부: 오류 없음', not er, er); c.close()
        # (2) setItem 이 용량 초과로 던짐
        c, pg, er = fresh("Storage.prototype.setItem=function(){throw new DOMException('full','QuotaExceededError')}")
        pg.evaluate("BrjAudio.setBgm(0.9);BrjAudio.muted(true)")
        check('저장 실패(용량): 예외 없이 상태 반영', pg.evaluate('BrjAudio.state().bgm') == 0.9 and pg.evaluate('BrjAudio.muted()') is True)
        check('저장 실패: 오류 없음', not er, er); c.close()
        # (3) 깨진 JSON / 이상한 값
        for raw, exp, label in [('{not json', dict(master=0.6, sfx=0.8, bgm=0.35, muted=False), '깨진 JSON'),
                                ('{"master":5,"sfx":"x","bgm":-1,"muted":"yes"}', dict(master=1, sfx=0.8, bgm=0, muted=False), '범위 밖·문자열 값'),
                                ('null', dict(master=0.6, sfx=0.8, bgm=0.35, muted=False), 'null'),
                                ('[1,2]', dict(master=0.6, sfx=0.8, bgm=0.35, muted=False), '배열')]:
            c, pg, er = fresh("localStorage.setItem('brjhunt_audio_v1',%s)" % json.dumps(raw))
            st = pg.evaluate('BrjAudio.state()')
            check('저장값 %s → 안전하게 보정' % label, all(st[k] == v for k, v in exp.items()) and not er, (st, er)); c.close()
        # (4) AudioContext 가 없는 환경
        c, pg, er = fresh("window.AudioContext=undefined;window.webkitAudioContext=undefined")
        pg.click('#b'); pg.wait_for_timeout(200)
        r = pg.evaluate("[BrjAudio.unlock(),BrjAudio.sfx('click'),BrjAudio.bgm('field1'),BrjAudio.state().unlocked]")
        check('AudioContext 미지원: 전부 조용히 무시(예외 없음)', r == [False, False, None, False] and not er, (r, er)); c.close()
        br.close()
    print('\n산출물:', SHOTS)
    print('FAILS: %d' % len(FAILS))
    for f in FAILS:
        print('  -', f)
    sys.exit(1 if FAILS else 0)


main()
