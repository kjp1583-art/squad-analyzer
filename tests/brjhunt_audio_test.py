#!/usr/bin/env python3.13
"""brjhunt_audio.js 시험(Playwright + OfflineAudioContext). 사용:
  CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome python3.13 tests/brjhunt_audio_test.py [--shots 폴더]

소리를 귀로 들을 수는 없으니 **파형을 숫자로** 본다:
  - 효과음 26종 · BGM 8트랙을 OfflineAudioContext 로 렌더 → 무음 아님 · 피크 <= 0.98(기본 볼륨, 그리고 마스터/효과음/BGM 1.0 최대 볼륨)
    · 직류 오프셋 없음 · NaN 없음 · 길이 · 꼬리가 끝에서 잘리지 않음 · BGM 은 2초 구간마다 소리가 있고 8마디 루프 이음매도 멀쩡
  - 파형 + 스펙트로그램을 PNG 로 저장(눈으로 확인용): <shots>/sfx_sheet.png, bgm_sheet.png
  - 라이브 동작: 제스처 전 무음(AudioContext 도 안 만듦) · 탭 숨김 정지/복귀 · 음소거 · 동시 발음 제한 · 볼륨 저장 ·
    localStorage 막힘/깨진 값에서도 동작 · BGM 전환 · onChange"""
import base64, hashlib, json, os, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else tempfile.mkdtemp(prefix='brjaudio_')
os.makedirs(SHOTS, exist_ok=True)
JS = os.path.join(ROOT, 'brjhunt_audio.js')
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
    r = page.evaluate("""async (o)=>{const r=await BrjAudio._render(o);return {b:__b64(r.data),played:r.played,dropped:r.dropped,sr:r.sampleRate}}""", opt)
    r['x'] = np.frombuffer(base64.b64decode(r['b']), dtype=np.float32).copy()
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
        need_sfx = ['hit', 'crit', 'kill', 'coin', 'levelup', 'boss_in', 'boss_win', 'boss_lose', 'click', 'tab', 'error', 'summon', 'summon_rare',
                    'enhance_ok', 'enhance_fail', 'awaken'] + ['skill_' + s for s in 'slash peck spin bomb thunder fire egg shield shrimp storm'.split()]
        need_bgm = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'boss', 'menu']
        check('계약의 효과음 이름 26종 전부', sorted(names) == sorted(need_sfx), set(need_sfx) ^ set(names))
        check('계약의 BGM 트랙 8종 전부', sorted(tracks) == sorted(need_bgm), tracks)
        check('전역 API 모양', page.evaluate("['unlock','sfx','bgm','setMaster','setSfx','setBgm','muted','state','onChange'].every(k=>typeof BrjAudio[k]==='function')"))
        st = page.evaluate('BrjAudio.state()')
        check('기본 볼륨 마스터 0.6 · BGM 0.35 · 음소거 아님', st['master'] == 0.6 and st['bgm'] == 0.35 and st['muted'] is False, st)

        # ---------------------------------------------------------- 효과음 파형
        print('\n== 효과음 렌더 ==')
        SR = 44100
        tiles = []
        sfx_wavs = {}
        for n in names:
            dur = page.evaluate('BrjAudio._sfxDur(%s)' % json.dumps(n))
            secs = dur + 0.5
            r = render(page, {'sfx': [{'name': n, 'at': 0.02}], 'seconds': secs, 'sampleRate': SR, 'seed': 7})
            x = r['x']; s = stats(x)
            sfx_wavs[n] = x
            check('sfx %s 길이 %.2fs' % (n, secs), abs(len(x) - int(np.ceil(SR * secs))) <= 1 and r['played'] == 1)
            check('sfx %s 무음 아님(피크 %.2f)' % (n, s['peak']), s['peak'] >= 0.05 and s['rms'] > 0.004, s)
            check('sfx %s 클리핑 없음 피크<=0.98' % n, s['peak'] <= 0.98 and s['clip'] == 0 and not s['nan'], s)
            act = x[:int((dur + 0.1) * SR)]
            check('sfx %s 직류 없음(|평균| %.4f)' % (n, abs(act.mean())), abs(act.mean()) < 0.01, act.mean())
            check('sfx %s 시작 클릭 없음' % n, abs(float(x[0])) < 0.03)
            tail = np.abs(x[-int(0.05 * SR):]).max()
            check('sfx %s 꼬리가 끝에서 잘리지 않음(%.4f)' % (n, tail), tail < 0.02, tail)
            # 최대 볼륨
            rm = render(page, {'sfx': [{'name': n, 'at': 0.02}], 'seconds': secs, 'sampleRate': SR, 'seed': 7,
                               'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
            check('sfx %s 최대 볼륨에서도 피크<=0.98 (%.3f)' % (n, np.abs(rm['x']).max()), np.abs(rm['x']).max() <= 0.98)
            tiles.append(tile(n, x, SR, 300, 150, 'pk %.2f c%dHz' % (s['peak'], centroid(act, SR))))
        sheet(tiles, 4, os.path.join(SHOTS, 'sfx_sheet.png'))
        # 같은 이름 반복은 음높이가 조금씩 달라야(무작위 폭) · 서로 다른 효과음은 서로 다른 파형이어야
        hs = {hashlib.sha1(v.tobytes()).hexdigest() for v in sfx_wavs.values()}
        check('효과음 26종 파형이 모두 서로 다름', len(hs) == len(sfx_wavs))
        a = render(page, {'sfx': [{'name': 'hit', 'at': 0.02}], 'seconds': 0.3, 'seed': 1})['x']
        b = render(page, {'sfx': [{'name': 'hit', 'at': 0.02}], 'seconds': 0.3, 'seed': 2})['x']
        c = render(page, {'sfx': [{'name': 'hit', 'at': 0.02}], 'seconds': 0.3, 'seed': 1})['x']
        check('같은 시드는 같은 파형 · 다른 시드는 다른 파형(타격음 변주)', np.array_equal(a, c) and not np.array_equal(a, b))
        lo = render(page, {'sfx': [{'name': 'coin', 'at': 0.02, 'rate': 0.5}], 'seconds': 0.5})['x']
        hi = render(page, {'sfx': [{'name': 'coin', 'at': 0.02, 'rate': 2}], 'seconds': 0.5})['x']
        check('rate 옵션이 음높이를 바꾼다(코인 0.5x < 2x)', centroid(lo, SR) < centroid(hi, SR) * 0.7, (centroid(lo, SR), centroid(hi, SR)))
        q = render(page, {'sfx': [{'name': 'coin', 'at': 0.02, 'vol': 0.25}], 'seconds': 0.5})['x']
        full = sfx_wavs['coin']
        check('vol 옵션이 음량을 바꾼다', 0.1 < np.abs(q).max() / np.abs(full).max() < 0.6, np.abs(q).max() / np.abs(full).max())

        # ---------------------------------------------------------- BGM 파형
        print('\n== BGM 렌더(8초) ==')
        btiles = []; vecs = {}; hashes = {}
        for t in tracks:
            r = render(page, {'bgm': t, 'seconds': 8, 'sampleRate': SR, 'seed': 3})
            x = r['x']; s = stats(x)
            check('bgm %s 길이 8초' % t, len(x) == SR * 8)
            check('bgm %s 무음 아님(피크 %.2f · rms %.3f)' % (t, s['peak'], s['rms']), s['peak'] >= 0.05 and s['rms'] >= 0.01, s)
            check('bgm %s 피크<=0.98 · NaN 없음' % t, s['peak'] <= 0.98 and s['clip'] == 0 and not s['nan'], s)
            check('bgm %s 직류 없음(%.4f)' % (t, s['dc']), abs(s['dc']) < 0.01, s['dc'])
            segs = [float(np.sqrt(np.mean(x[i * 2 * SR:(i + 1) * 2 * SR].astype(np.float64) ** 2))) for i in range(4)]
            check('bgm %s 2초 구간마다 소리가 있다 %s' % (t, [round(v, 3) for v in segs]), min(segs) > 0.004, segs)
            rm = render(page, {'bgm': t, 'seconds': 8, 'sampleRate': SR, 'seed': 3, 'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
            check('bgm %s 최대 볼륨 피크<=0.98 (%.3f)' % (t, np.abs(rm['x']).max()), np.abs(rm['x']).max() <= 0.98)
            hashes[t] = hashlib.sha1(x.tobytes()).hexdigest(); vecs[t] = band_vec(x, SR)
            btiles.append(tile(t, x, SR, 640, 200, 'pk %.2f rms %.3f c%dHz' % (s['peak'], s['rms'], centroid(x, SR))))
        sheet(btiles, 2, os.path.join(SHOTS, 'bgm_sheet.png'))
        check('BGM 8트랙 파형이 모두 다름', len(set(hashes.values())) == len(tracks))
        worst = max(float(np.corrcoef(vecs[a], vecs[b])[0, 1]) for i, a in enumerate(tracks) for b in tracks[i + 1:])
        check('BGM 트랙끼리 음색(스펙트럼)이 충분히 다름(최대 상관 %.3f)' % worst, worst < 0.995, worst)
        # 8마디 루프를 한 바퀴 이상(이음매에서 끊기거나 터지지 않는지)
        for t in tracks:
            bpm = page.evaluate('({field1:108,field2:120,field3:100,field4:128,field5:124,field6:140,boss:156,menu:84})[%s]' % json.dumps(t))
            loop_s = 8 * 4 * 60.0 / bpm
            r = render(page, {'bgm': t, 'seconds': loop_s + 3, 'sampleRate': 22050, 'seed': 3})
            x = r['x']; s = stats(x)
            tail = x[int((loop_s - 0.5) * 22050):int((loop_s + 2.5) * 22050)]
            check('bgm %s 루프 이음매(%.1fs) 앞뒤로 소리 이어짐·피크 정상' % (t, loop_s), s['peak'] <= 0.98 and not s['nan'] and np.sqrt(np.mean(tail ** 2)) > 0.01, s)
        # 템포가 맞는지: 박(kick 간격) 추정 — field4(4분음표마다 킥) 에서 포락선 자기상관 최대 주기 ≈ 60/128*(2~4)
        x = render(page, {'bgm': 'field4', 'seconds': 8, 'sampleRate': 22050, 'seed': 3})['x']
        lp = np.abs(x[:len(x) // 110 * 110]).reshape(-1, 110).max(1)  # 5ms 해상도
        lp = lp - lp.mean()
        ac = np.correlate(lp, lp, 'full')[len(lp) - 1:]
        lo_i, hi_i = int(0.3 / 0.005), int(1.0 / 0.005)
        per = (np.argmax(ac[lo_i:hi_i]) + lo_i) * 0.005
        beat = 60 / 128
        check('field4 박 주기 ≈ %.3fs 의 배수(측정 %.3f)' % (beat, per), min(abs(per / beat - round(per / beat)), 9) < 0.08 and per > 0.3, per)

        # ---------------------------------------------------------- 동시 발음 제한(오프라인)
        print('\n== 동시 발음 ==')
        burst = [{'name': n, 'at': 0.05} for n in names]
        r = render(page, {'sfx': burst, 'seconds': 2, 'sampleRate': SR, 'seed': 5, 'levels': {'master': 1, 'sfx': 1, 'bgm': 1, 'muted': False}})
        check('26종 동시 발사 → 상한(<=24) 안에서 일부는 버려짐(재생 %d · 버림 %d)' % (r['played'], r['dropped']), r['played'] <= 24 and r['dropped'] >= 2 and r['played'] >= 10, (r['played'], r['dropped']))
        check('동시 발사해도 피크<=0.98', np.abs(r['x']).max() <= 0.98, np.abs(r['x']).max())
        r = render(page, {'sfx': [{'name': 'hit', 'at': 0.5 + i * 0.001} for i in range(40)], 'seconds': 1.5})
        check('같은 효과음 40연타(1ms 간격) → 최소 간격으로 솎음(재생 %d)' % r['played'], r['played'] <= 2, r['played'])
        r = render(page, {'sfx': [{'name': 'hit', 'at': 0.1 + i * 0.1} for i in range(10)], 'seconds': 1.6})
        check('0.1초 간격 타격 10번은 전부 재생', r['played'] == 10 and r['dropped'] == 0, (r['played'], r['dropped']))
        # 분당 100마리: 초당 1.7회 kill+hit+coin 이 쌓여도 안 막힘
        ev = []
        for i in range(60):
            t0 = 0.1 + i * 0.6
            ev += [{'name': 'hit', 'at': t0}, {'name': 'kill', 'at': t0 + 0.15}, {'name': 'coin', 'at': t0 + 0.3}]
        r = render(page, {'sfx': ev, 'seconds': 37, 'sampleRate': 22050})
        check('분당 100마리 수준(60킬/36초) 연출에서 전부 재생(%d/%d)' % (r['played'], len(ev)), r['played'] == len(ev), (r['played'], r['dropped']))

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
        check('BGM 스케줄러가 실제로 칸을 진행(step %d → %d)' % (d['step'], d2['step']), d2['step'] > d['step'] + 8, (d, d2))
        check('음소거 아닐 때 마스터 게인 = 0.6', abs(d2['masterGain'] - 0.6) < 0.01, d2['masterGain'])

        # 동시 발음(라이브)
        page.wait_for_timeout(2500)  # 앞선 소리 정리
        r = page.evaluate("""()=>{const n=BrjAudio.sfxNames();const before=BrjAudio._debug();let ok=0;for(let k=0;k<3;k++)for(const s of n)if(BrjAudio.sfx(s))ok++;
          const d=BrjAudio._debug();let hit=0;for(let i=0;i<50;i++)if(BrjAudio.sfx('hit'))hit++;return {ok,active:d.active,dropped:d.dropped-before.dropped,hit}}""")
        check('라이브: 한꺼번에 78번 호출해도 동시 발음 <= 24 (활성 %d · 허용 %d · 버림 %d)' % (r['active'], r['ok'], r['dropped']), r['active'] <= 24 and r['dropped'] > 20, r)
        check('라이브: 같은 이름 50연타는 한두 번만', r['hit'] <= 1, r['hit'])

        # BGM 전환
        page.evaluate("BrjAudio.bgm('boss')"); page.wait_for_timeout(300)
        check('BGM 전환 field1 → boss', page.evaluate('BrjAudio._debug().track') == 'boss')
        page.evaluate("BrjAudio.bgm('nope')")
        check('모르는 트랙은 무시(boss 유지)', page.evaluate('BrjAudio._debug().track') == 'boss')
        page.evaluate("BrjAudio.bgm('field3')"); page.wait_for_timeout(200)
        check('BGM 전환 boss → field3', page.evaluate('BrjAudio._debug().track') == 'field3')

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
