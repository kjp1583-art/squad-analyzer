#!/usr/bin/env python3
"""비주얼노벨 「스콰드 생존게임」 BGM 7곡을 코드로 작곡·렌더한다(오리지널, 시드 고정 → 항상 같은 결과).
사용: python3 tooling/novel_music.py [곡이름 ...]   (없으면 전부)  →  audio/novel/bgm_*.mp3
악기: 플럭(기타 느낌)·피아노·뮤직박스(가산합성+감쇠) / 현악 패드·첼로(디튠 톱니파+저역통과+느린 어택) /
      심장박동 킥·브러시 스네어·하이햇·타악 / 리버브(합성 잔향 IR 컨볼루션).
루프: 곡 본체 N초는 '주기적'으로 렌더(끝 잔향을 처음에 겹침). 파일은 본체 + LOOPX 초(본체 처음 LOOPX 초와 같은 내용)이며
      재생기가 본체 끝에서 다음 인스턴스를 시작해 LOOPX 초 동안 선형 크로스페이드하면 이음매가 수학적으로 이어진다."""
import sys, os, numpy as np
from scipy import signal
import lameenc

SR = 32000
LOOPX = 1.5
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'audio', 'novel')
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

def m(n):
    """'C#4' → midi"""
    p = NOTE[n[0]]; i = 1
    while n[i] in '#b':
        p += 1 if n[i] == '#' else -1; i += 1
    return 12 * (int(n[i:]) + 1) + p
def hz(x): return 440.0 * 2 ** ((x - 69) / 12)

# ---------------------------------------------------------------- 믹서
class Mix:
    def __init__(self, secs, tail=6.0):
        self.N = int(secs * SR); self.T = int(tail * SR); n = self.N + self.T
        self.dry = np.zeros((2, n)); self.wet = np.zeros((2, n))
    def add(self, sig, t, pan=0.0, gain=1.0, send=0.25):
        i = int(t * SR); sig = sig[:max(0, self.N + self.T - i)]
        if i < 0 or len(sig) == 0: return
        a = (pan + 1) * np.pi / 4; l, r = np.cos(a) * gain, np.sin(a) * gain
        for ch, g in ((0, l), (1, r)):
            self.dry[ch, i:i + len(sig)] += sig * g
            self.wet[ch, i:i + len(sig)] += sig * g * send
    def addst(self, sl, sr_, t, gain=1.0, send=0.25):
        """좌우가 이미 갈라진 신호(디튠 패드 등)"""
        i = int(t * SR); n = min(len(sl), self.N + self.T - i)
        if n <= 0: return
        self.dry[0, i:i + n] += sl[:n] * gain; self.dry[1, i:i + n] += sr_[:n] * gain
        self.wet[0, i:i + n] += sl[:n] * gain * send; self.wet[1, i:i + n] += sr_[:n] * gain * send

def reverb_ir(rt, seed, damp=3500):
    rng = np.random.default_rng(seed); n = int(rt * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((2, n)) * np.exp(-6.9 * t / rt)
    sos = signal.butter(2, damp, 'low', fs=SR, output='sos')
    ir = signal.sosfilt(sos, ir, axis=1)
    ir[:, :int(.012 * SR)] *= np.linspace(0, 1, int(.012 * SR))   # 약간의 프리딜레이 느낌
    ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
    return ir

def finish(mix, rt=2.4, wetmix=0.5, rms_db=-20.0, ceil_db=-1.5, damp=3500, seed=7):
    ir = reverb_ir(rt, seed, damp)
    wl = signal.fftconvolve(mix.wet[0], ir[0])[:mix.N + mix.T]
    wr = signal.fftconvolve(mix.wet[1], ir[1])[:mix.N + mix.T]
    out = mix.dry + np.stack([wl, wr]) * wetmix
    # 꼬리를 처음에 접어 넣어 주기적으로
    body = out[:, :mix.N].copy(); tail = out[:, mix.N:]
    k = min(tail.shape[1], mix.N); body[:, :k] += tail[:, :k]
    # 고역 필터(저역 웅웅 정리) + 레벨
    sos = signal.butter(2, 28, 'high', fs=SR, output='sos'); body = signal.sosfilt(sos, body, axis=1)
    # 필터 시동 잔향이 이음매에 남지 않도록 한 번 더 이어 붙여 정상 상태에서 자른다
    big = signal.sosfilt(sos, np.concatenate([out[:, :mix.N] * 0 + body] * 2, axis=1), axis=1)
    body = big[:, mix.N:]
    rms = np.sqrt((body ** 2).mean()); body *= 10 ** (rms_db / 20) / rms
    ceil = 10 ** (ceil_db / 20)
    # 부드러운 리미터(tanh) 후 최종 천장
    body = np.tanh(body / ceil * 0.9) * ceil / np.tanh(0.9) * 0.98
    pk = np.abs(body).max()
    if pk > ceil: body *= ceil / pk
    return body

# ---------------------------------------------------------------- 악기
def tt(d): return np.arange(int(d * SR)) / SR
def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, min(f, SR * .45), 'low', fs=SR, output='sos'), x)
def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'high', fs=SR, output='sos'), x)

def pluck(f, d=1.6, bright=1.0):
    """어쿠스틱 기타 느낌: 배음마다 다른 감쇠 + 짧은 피크 노이즈"""
    t = tt(d); x = np.zeros_like(t)
    for k in range(1, 14):
        if f * k > 9000: break
        amp = (1.0 / k ** 1.1) * (bright if k > 3 else 1.0)
        x += amp * np.sin(2 * np.pi * f * k * (1 + 0.0004 * k * k) * t + k) * np.exp(-t * (2.2 + 1.3 * k) / (d * .55))
    nz = np.random.default_rng(int(f * 10) & 0xffff).standard_normal(len(t)) * np.exp(-t * 90)
    x += lp(nz, 3000) * .15
    x *= np.minimum(1, t * 600) * np.exp(-t * 0.3)
    return x * .5

def piano(f, d=3.0, vel=1.0):
    t = tt(d); x = np.zeros_like(t)
    for k in range(1, 12):
        fk = f * k * (1 + 0.00035 * k * k)
        if fk > 8500: break
        x += (1.0 / k ** 1.25) * np.sin(2 * np.pi * fk * t + k * .7) * np.exp(-t * (0.9 + 0.55 * k) * (1.3 if f > 500 else 0.8))
    x += 0.35 * np.sin(2 * np.pi * f * 1.002 * t) * np.exp(-t * 0.9)          # 약간 어긋난 줄(코러스)
    h = np.random.default_rng(int(f) & 0xffff).standard_normal(len(t)) * np.exp(-t * 220)
    x += lp(h, 2500) * .08 * vel                                              # 해머
    x *= np.minimum(1, t * 900)
    return x * .55 * vel

def musicbox(f, d=2.4):
    t = tt(d); x = np.zeros_like(t)
    for r, a, dec in ((1, 1.0, 1.6), (2.0, .25, 3.0), (4.0, .22, 5.0), (5.4, .12, 6.5), (7.1, .07, 8.0)):
        if f * r < 9500:
            x += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * dec)
    x *= np.minimum(1, t * 1500)
    return x * .5

def pad(f, d, att=1.2, rel=1.5, cut=1800, voices=4, spread=0.12, vib=0.003, seed=0, saw_mix=1.0):
    """현악 패드: 디튠 톱니파 + 저역통과 + 느린 어택/릴리즈. (좌, 우) 반환"""
    n = int((d + rel) * SR); t = np.arange(n) / SR; rng = np.random.default_rng(seed + int(f))
    outs = [np.zeros(n), np.zeros(n)]
    for v in range(voices):
        det = (v - (voices - 1) / 2) * spread / max(1, voices - 1) * 2 + rng.uniform(-.03, .03)
        fi = f * 2 ** (det / 12) * (1 + vib * np.sin(2 * np.pi * (4.8 + .4 * v) * t + rng.uniform(0, 6)))
        ph = 2 * np.pi * np.cumsum(fi) / SR
        w = signal.sawtooth(ph) * saw_mix + np.sin(ph) * (1 - saw_mix)
        outs[v % 2] += w / voices * 2
    env = np.minimum(1, t / att) ** 1.6
    env = env * np.where(t < d, 1.0, np.exp(-(t - d) / (rel / 4.5)))
    return [lp(o, cut) * env * .35 for o in outs]

def cello(f, d, att=.25, rel=.5, cut=1100):
    n = int((d + rel) * SR); t = np.arange(n) / SR
    fi = f * (1 + 0.0035 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / .6))
    ph = 2 * np.pi * np.cumsum(fi) / SR
    x = signal.sawtooth(ph) * .8 + signal.square(ph + 1) * .25 + np.sin(ph) * .5
    env = np.minimum(1, t / att) * np.where(t < d, 1.0, np.exp(-(t - d) / (rel / 4.5)))
    return lp(x, cut, 3) * env * .45

def bass(f, d=.5):
    t = tt(d); x = np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    return x * np.minimum(1, t * 400) * np.exp(-t * 3.2 / d * 1.2) * .7

def kick(d=.35, f0=95, f1=42, vol=1.0):
    t = tt(d); fr = f1 + (f0 - f1) * np.exp(-t * 28)
    x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 11)
    return x * np.minimum(1, t * 800) * vol

def heart(vol=1.0):
    """심장박동: 쿵-쿵(둘째 박은 작고 늦게)"""
    a = kick(.32, 70, 38, 1.0); b = kick(.28, 62, 36, .65)
    out = np.zeros(int(.6 * SR)); out[:len(a)] += a; j = int(.22 * SR); out[j:j + len(b)] += b[:len(out) - j]
    return lp(out, 220) * vol

def brush(d=.22, vol=1.0):
    t = tt(d); nz = np.random.default_rng(3).standard_normal(len(t))
    x = hp(lp(nz, 6500), 1500) * np.minimum(1, t / .03) * np.exp(-t * 14)
    return x * vol * .5

def hat(d=.06, vol=1.0, seed=1):
    t = tt(d); nz = np.random.default_rng(seed).standard_normal(len(t))
    return hp(nz, 6000) * np.exp(-t * 70) * vol * .35

def snare(d=.25, vol=1.0):
    t = tt(d); nz = np.random.default_rng(5).standard_normal(len(t))
    x = hp(lp(nz, 7000), 800) * np.exp(-t * 18) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28) * .6
    return x * vol * .55

def taiko(d=.7, f=70, vol=1.0):
    t = tt(d); fr = f * (1 + 1.1 * np.exp(-t * 25))
    x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 6.5)
    nz = lp(np.random.default_rng(9).standard_normal(len(t)), 900) * np.exp(-t * 40) * .5
    return (x + nz) * vol * np.minimum(1, t * 800)

def riser(d, f0=300, f1=3000, vol=1.0):
    t = tt(d); nz = np.random.default_rng(11).standard_normal(len(t))
    out = np.zeros_like(nz); step = SR // 20
    for i in range(0, len(t), step):
        fc = f0 * (f1 / f0) ** (i / len(t))
        seg = nz[i:i + step]
        out[i:i + step] = seg
    x = hp(lp(out, f1), f0) * (t / d) ** 2.2
    return x * vol * .25

def whistle(f0, f1, d, vol=1.0):
    """아주 높은 유령 글리산도(불안한 쪽 장식)"""
    t = tt(d); fr = f0 * (f1 / f0) ** (t / d)
    x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.sin(np.pi * t / d) ** 2
    return x * vol * .12

# ---------------------------------------------------------------- 작곡 도구
def chord(root, q):
    iv = {'M': (0, 4, 7), 'm': (0, 3, 7), 'M7': (0, 4, 7, 11), 'm7': (0, 3, 7, 10), '7': (0, 4, 7, 10),
          'sus': (0, 5, 7), 'dim': (0, 3, 6), 'cl': (0, 1, 2, 3), 'm9': (0, 3, 7, 10, 14), 'add9': (0, 4, 7, 14),
          'M6': (0, 4, 7, 9)}[q]
    r = m(root)
    return [r + i for i in iv]

def voiced(ch, octv=0):
    """코드 음 반복해 위로 쌓은 배열(아르페지오 인덱스용)"""
    out = []
    for o in range(3):
        out += [x + 12 * o + 12 * octv for x in ch[:3]]
    return out

def swing(t, amt=0.0): return t

# ===================================================================== 1. bright
def song_bright():
    bpm = 120; B = 60 / bpm; bars = 40; mix = Mix(bars * 4 * B)
    prog = [('C', 'M'), ('G', 'M'), ('A', 'm'), ('F', 'M'), ('C', 'M'), ('G', 'M'), ('F', 'M'), ('G', 'sus')]
    mel = [  # 8마디 선율(박, 음, 길이)
        [(0, 'E5', 1), (1, 'G5', .5), (1.5, 'A5', .5), (2, 'G5', 1.5), (3.5, 'E5', .5)],
        [(0, 'D5', 1), (1, 'E5', .5), (1.5, 'D5', .5), (2, 'B4', 2)],
        [(0, 'C5', 1), (1, 'E5', 1), (2, 'A5', 1.5), (3.5, 'G5', .5)],
        [(0, 'A5', 1), (1, 'G5', 1), (2, 'F5', 1), (3, 'E5', 1)],
        [(0, 'E5', 1), (1, 'G5', .5), (1.5, 'C6', .5), (2, 'B5', 1.5), (3.5, 'G5', .5)],
        [(0, 'A5', 1), (1, 'G5', 1), (2, 'D5', 2)],
        [(0, 'F5', 1), (1, 'A5', 1), (2, 'C6', 1.5), (3.5, 'A5', .5)],
        [(0, 'B5', 1.5), (1.5, 'A5', .5), (2, 'G5', 1.5), (3.5, 'D5', .5)],
    ]
    pat = [0, 2, 1, 2, 3, 2, 1, 2]
    for b in range(bars):
        t0 = b * 4 * B; cy = b // 8; k = b % 8; root, q = prog[k]; ch = chord(root + '3', q)
        off = (cy == 3 and k in (6,))          # 어긋난 화음: F → Fm(Ab)
        if off: ch = chord('F3', 'm')
        v = voiced(ch)
        sec = 0 if b < 8 else (1 if b < 32 else 2)
        for i, ix in enumerate(pat):          # 8분 아르페지오 플럭
            note = v[ix + (3 if ix == 3 else 0)]
            mix.add(pluck(hz(note + 12), 1.2), t0 + i * B / 2 + (0.012 if i % 2 else 0), pan=-.35, gain=.55, send=.2)
        if sec >= 1:                           # 스트럼 느낌(엇박 코드)
            for bt in (1.5, 3.5):
                for j, nn in enumerate(ch[:3] + [ch[0] + 12]):
                    mix.add(pluck(hz(nn + 12), .9, .8), t0 + bt * B + j * .012, pan=.4, gain=.3, send=.2)
        bn = m(root + '2')
        for bt, dur, g in ((0, 1.2, 1), (2, 1, .8), (3.5, .5, .55)):
            mix.add(bass(hz(bn), dur * B), t0 + bt * B, 0, g * .8, .05)
        # 리듬: 부드러운 킥 1·3, 브러시 2·4, 하이햇 8분
        if sec >= 1 or b >= 4:
            for bt in (0, 2): mix.add(kick(.3, 90, 50), t0 + bt * B, 0, .55, 0)
            for bt in (1, 3): mix.add(brush(), t0 + bt * B, .1, .6, .15)
        if b >= 4:
            for i in range(8): mix.add(hat(vol=.5 if i % 2 else .8, seed=i), t0 + i * B / 2, .25, .5, .1)
        if sec >= 1:                           # 피아노 선율
            for bt, nn, dd in mel[k]:
                n2 = m(nn)
                if cy == 3 and k == 2 and nn == 'E5': n2 -= 1     # 살짝 어긋난 음(Eb)
                if cy == 4: n2 += 0
                mix.add(piano(hz(n2), 2.0 * dd + .6), t0 + bt * B, .15, .62, .3)
        if sec == 2 or (b % 8 in (4, 5, 6, 7) and sec == 1):   # 가벼운 패드
            l, r_ = pad(hz(ch[1] + 12), 4 * B, 1.0, 1.0, 1400, 3, .1, seed=b)
            mix.addst(l, r_, t0, .22, .3)
        if b < 8 and k in (0, 4):                # 인트로 글리터(뮤직박스)
            for i, nn in enumerate(('G5', 'C6', 'E6')): mix.add(musicbox(hz(m(nn))), t0 + (1 + i * .5) * B, .3, .35, .4)
    return finish(mix, 1.9, .42, -19.5), bars * 4 * B

# ===================================================================== 2. uneasy
def song_uneasy():
    bpm = 96; B = 60 / bpm; bars = 32; mix = Mix(bars * 4 * B)
    cycles = [
        [('C', 'M'), ('E', 'm'), ('F', 'M7'), ('F', 'm')],
        [('C', 'M'), ('A', 'm'), ('F', 'M7'), ('F', 'm')],
        [('A', 'm'), ('F', 'M7'), ('D', 'm'), ('E', '7')],
        [('A', 'm'), ('F', 'M7'), ('D', 'm'), ('F', 'm')],
    ]
    motif = [(0, 2), (1, 1), (1.5, 2), (2.5, 4), (3.5, 3)]       # 박, 화음 음 인덱스(위 옥타브까지)
    for b in range(bars):
        t0 = b * 4 * B; cy = b // 4 % 4; k = b % 4; blk = b // 8
        root, q = cycles[b // 8][b % 4] if b // 8 < 4 else cycles[3][b % 4]
        ch = chord(root + '3', q); v = voiced(ch, 1)
        minor = blk >= 2
        # 뮤직박스 선율(모티프; 후반으로 갈수록 음이 낮아지고 단조 느낌)
        for bt, ix in motif:
            nn = v[ix + (1 if bt == 2.5 else 0)] + (12 if blk < 2 else 0)
            if blk == 3 and b % 4 == 3: nn -= 1
            mix.add(musicbox(hz(nn)), t0 + bt * B, -.2 + .1 * ix % .4, .55, .45)
        if b % 2 == 1 and b >= 4:               # 대위 아르페지오(느리게 퍼지는 음)
            for i, ix in enumerate((0, 1, 2, 4)):
                mix.add(musicbox(hz(v[ix] + 12)), t0 + (.5 + i * .5) * B, .35, .22, .4)
        l, r_ = pad(hz(chord(root + '2', q)[0] + 12), 4 * B, 1.8, 1.8, 700 if blk < 2 else 520, 4, .16, seed=b)
        mix.addst(l, r_, t0, .5, .35)
        l, r_ = pad(hz(ch[1]), 4 * B, 2.0, 1.8, 900, 3, .14, seed=b + 90)
        mix.addst(l, r_, t0, .28 if blk < 2 else .34, .4)
        if blk >= 1: mix.add(cello(hz(m(root + '2')), 3.2 * B, .4, 1.0), t0, -.15, .55 if blk >= 2 else .4, .25)
        if blk >= 2 and b % 2 == 0: mix.add(heart(.45 if blk == 2 else .6), t0, 0, .6, .1)
        if blk >= 2 and b % 4 == 3: mix.add(whistle(1700, 2300, 3, 1), t0 + .5, .5, .5, .6)
    return finish(mix, 2.8, .5, -21), bars * 4 * B

# ===================================================================== 3. dread
def song_dread():
    bpm = 60; B = 1.0; bars = 20; mix = Mix(bars * 4 * B, 7)
    rng = np.random.default_rng(33)
    for b in range(bars):
        t0 = b * 4 * B
        base = 'D'
        # 낮은 현 지속음 + 불협화 클러스터
        for nn, g in (('D2', .8), ('A2', .45)):
            mix.add(cello(hz(m(nn)), 4.4 * B, 1.5, 1.2, 600), t0 - .2, -.1, g, .3)
        cl = [('D3', 0), ('Eb3', 0), ('E3', 0)] if b % 4 in (0, 1) else [('D3', 0), ('C#3', 0), ('Eb3', 0)]
        for j, (nn, _) in enumerate(cl):
            l, r_ = pad(hz(m(nn)), 4 * B, 2.0, 2.0, 520 + 70 * (b % 5), 3, .3, seed=b * 5 + j)
            mix.addst(l, r_, t0, .28 + .02 * (b >= 10), .45)
        if b >= 2:
            for bt in (0, 1.1 * 1.0 + 0.0):   # 느린 심장박동(1.2초 간격)
                pass
            for i in range(3):
                mix.add(heart(.55 + .01 * b), t0 + i * 1.33, 0, .65, .08)
        # 저음 모티프(첼로): D - Eb - D - C#
        if b % 4 == 2:
            for i, nn in enumerate(('D3', 'Eb3', 'D3', 'C#3')):
                mix.add(cello(hz(m(nn)), 1.5, .3, .8, 700), t0 + i * 1.0, .15, .5, .3)
        if b % 5 == 3: mix.add(whistle(2400, 1800, 3.5, 1), t0 + .5, rng.uniform(-.7, .7), 1, .6)
        if b % 6 == 4:  # 먼 곳의 낮은 두드림
            mix.add(taiko(1.0, 55, .5), t0 + 2.5, 0, .5, .4)
        if b >= 12:  # 후반: 높은 불협화 현
            for nn in ('Ab4', 'A4'):
                l, r_ = pad(hz(m(nn)), 4 * B, 2.5, 2.0, 1500, 3, .25, seed=b)
                mix.addst(l, r_, t0, .09, .6)
    return finish(mix, 4.2, .6, -22, damp=2800), bars * 4 * B

# ===================================================================== 4. tension
def song_tension():
    bpm = 108; B = 60 / bpm; bars = 36; mix = Mix(bars * 4 * B)
    prog = [('E', 'm'), ('C', 'M'), ('A', 'm'), ('B', '7')]
    for b in range(bars):
        t0 = b * 4 * B; k = b % 4; root, q = prog[k]; ch = chord(root + '3', q); sec = b // 12
        # 규칙적 맥박: 8분 저음 현 피치카토 (모든 마디, 구간이 오를수록 세게)
        bn = m(root + '2')
        for i in range(8):
            ac = 1.0 if i % 4 == 0 else .55
            mix.add(bass(hz(bn), .3) + pluck(hz(bn + 12), .3, .5) * .25, t0 + i * B / 2, -.1, .7 * ac, .12)
        # 아르페지오: 구간 따라 음역이 오르고 16분으로 촘촘해짐
        v = voiced(ch, 1 + (sec >= 1)); steps = 8 if sec == 0 else 16
        up = [0, 1, 2, 1, 2, 3, 4, 3, 4, 5, 6, 5, 6, 7, 8, 7]
        for i in range(steps):
            ix = up[i % 16] if sec else [0, 1, 2, 3, 2, 1, 2, 3][i]
            if sec == 2: ix = (ix + b % 4) % 9
            nn = v[ix % len(v)] + 12 * (sec == 2)
            mix.add(pluck(hz(nn), .5, 1.0), t0 + i * 4 * B / steps, .3 + .2 * np.sin(i), .3 + .05 * sec, .25)
        # 중저음 스트링
        l, r_ = pad(hz(ch[0] + 12), 4 * B, .9, .8, 1200 + 500 * sec, 4, .14, seed=b)
        mix.addst(l, r_, t0, .32 + .08 * sec, .3)
        if sec >= 1:
            l, r_ = pad(hz(ch[2] + 12), 4 * B, .6, .8, 1500 + 400 * sec, 3, .12, seed=b + 1)
            mix.addst(l, r_, t0, .22 + .07 * sec, .3)
        # 시계 같은 하이햇 + 심장 킥(1박·3박)
        for i in range(4): mix.add(hat(.04, .6 + .1 * sec, i), t0 + (i + .5) * B, .35, .45, .1)
        if sec >= 1:
            for bt in (0, 1, 2, 3): mix.add(kick(.28, 80, 45), t0 + bt * B, 0, .38 + .1 * (sec - 1), 0)
        else:
            for bt in (0, 2): mix.add(kick(.28, 80, 45), t0 + bt * B, 0, .4, 0)
        if sec == 2 and k == 3:                    # 마지막 구간 마디마다 올라가는 라이저
            mix.add(riser(4 * B * .9, 400, 4000), t0, 0, .7, .3)
        if sec >= 1 and k in (0, 2): mix.add(snare(.2, .5), t0 + 3.5 * B, .1, .5, .2)
    return finish(mix, 2.2, .4, -19), bars * 4 * B

# ===================================================================== 5. climax
def song_climax():
    bpm = 140; B = 60 / bpm; bars = 44; mix = Mix(bars * 4 * B)
    prog = [('D', 'm'), ('D', 'm'), ('Bb', 'M'), ('Bb', 'M'), ('G', 'm'), ('G', 'm'), ('A', '7'), ('A', '7')]
    for b in range(bars):
        t0 = b * 4 * B; k = b % 8; root, q = prog[k]; ch = chord(root + '3', q)
        sec = 0 if b < 8 else (1 if b < 24 else (2 if b < 40 else 3))
        bn = m(root + '2')
        # 빠른 맥박 킥(4분) + 8분 베이스 + 타악
        for bt in range(4): mix.add(kick(.3, 100, 45), t0 + bt * B, 0, .75 if bt % 2 == 0 else .55, 0)
        for i in range(8): mix.add(bass(hz(bn), .25), t0 + i * B / 2, 0, .6, .05)
        if sec >= 1:
            for bt in (1, 3): mix.add(snare(.25, 1), t0 + bt * B, .05, .7, .25)
            for i in range(8): mix.add(hat(.05, .6, i), t0 + (i + .5) * B / 2 * 1, .3, .5, .1)
        if sec >= 2:
            for bt in (0, 2.5): mix.add(taiko(.9, 62, 1), t0 + bt * B, 0, .85, .35)
        if k == 7 and sec >= 1:                    # 필인
            for i in range(4): mix.add(snare(.15, .8), t0 + (3 + i * .25) * B, .05, .55, .2)
        # 상승 스트링: 구간마다 한 칸씩 올라가는 보이싱
        top = 12 * (1 + (sec >= 1)) + (7 if sec >= 3 else 0)
        for j, nn in enumerate(ch[:3]):
            l, r_ = pad(hz(nn + 12 + (12 if sec >= 2 and j == 2 else 0)), 4 * B, .35, .5, 1500 + 700 * sec, 4, .18, seed=b * 3 + j)
            mix.addst(l, r_, t0, .34 + .06 * sec, .3)
        # 스타카토 현 아르페지오
        if sec >= 1:
            v = voiced(ch, 1)
            for i in range(8):
                mix.add(pluck(hz(v[[0, 1, 2, 3, 2, 1, 4, 2][i]] + 12), .3, 1.4), t0 + i * B / 2, -.3 + .1 * (i % 5), .35, .2)
        # 선율: 상승하는 호령
        if sec >= 2:
            mel = {'D': 'A4', 'Bb': 'F5', 'G': 'D5', 'A': 'E5'}[root]
            for bt, off in ((0, 0), (1.5, 2), (2.5, 3)):
                mix.add(cello(hz(m(mel) + off * (sec - 1)), 1.4 * B, .05, .3, 2500), t0 + bt * B, .2, .45, .25)
        if k == 6 and sec in (1, 2): mix.add(riser(8 * B * .95, 300, 5000), t0, 0, .8, .3)
        if b == 0: mix.add(taiko(1.4, 55, 1), t0, 0, .9, .5)
    return finish(mix, 1.8, .33, -16.5, ceil_db=-1.2), bars * 4 * B

# ===================================================================== 6. sorrow
def song_sorrow():
    bpm = 66; B = 60 / bpm; bars = 24; mix = Mix(bars * 4 * B, 7)
    prog = [('A', 'm'), ('F', 'M7'), ('C', 'M'), ('G', 'M'), ('D', 'm'), ('A', 'm'), ('E', '7'), ('A', 'm')]
    mel = [
        [(0, 'E5', 2), (2, 'C5', 1), (3, 'D5', 1)],
        [(0, 'C5', 2.5), (3, 'A4', 1)],
        [(0, 'G4', 1), (1, 'E5', 1.5), (3, 'D5', 1)],
        [(0, 'B4', 3), (3, 'D5', 1)],
        [(0, 'F5', 2), (2, 'E5', 1), (3, 'D5', 1)],
        [(0, 'E5', 1.5), (1.5, 'C5', 1.5), (3, 'A4', 1)],
        [(0, 'G#4', 2), (2, 'B4', 1), (3, 'E5', 1)],
        [(0, 'A4', 4)],
    ]
    for b in range(bars):
        t0 = b * 4 * B; k = b % 8; root, q = prog[k]; ch = chord(root + '3', q); sec = b // 8
        v = voiced(ch)
        # 쓸쓸한 피아노 아르페지오(느린 6연)
        for i, ix in enumerate([0, 1, 2, 4, 2, 1]):
            if sec == 0 and b < 2 and i > 3: continue
            mix.add(piano(hz(v[ix] + 12), 3.2, .75), t0 + i * 4 * B / 6 + (i % 2) * .01, -.15, .6, .45)
        if sec >= 1 or b >= 2:
            for bt, nn, dd in mel[k]:
                mix.add(piano(hz(m(nn) + (12 if sec == 2 else 0)), 3.5 + dd, 1.0), t0 + bt * B, .2, .62, .5)
        l, r_ = pad(hz(ch[1] + 12), 4 * B, 1.8, 2.0, 1000, 4, .15, seed=b)
        mix.addst(l, r_, t0, .3 + .05 * sec, .45)
        mix.add(cello(hz(m(root + '2')), 3.6 * B, .6, 1.2, 800), t0, -.1, .55 + .05 * (sec == 1), .3)
        if sec >= 1: mix.add(cello(hz(m(root + '3')), 3.4 * B, .9, 1.2, 1200), t0 + .5 * B, .25, .35, .35)
    return finish(mix, 4.0, .55, -22, damp=3000), bars * 4 * B

# ===================================================================== 7. hope
def song_hope():
    bpm = 72; B = 60 / bpm; bars = 24; mix = Mix(bars * 4 * B, 6)
    cyc = [
        [('E', 'm'), ('C', 'M'), ('G', 'M'), ('D', 'M')],      # 마이너로 시작
        [('G', 'M'), ('D', 'M'), ('E', 'm'), ('C', 'add9')],   # 장조로 밝아짐
        [('C', 'M7'), ('G', 'M'), ('A', 'm7'), ('D', 'sus')],  # 따뜻하게 열림
        [('G', 'M'), ('D', 'M'), ('C', 'M7'), ('G', 'M')],
        [('G', 'M'), ('D', 'M'), ('C', 'M7'), ('G', 'M')],
        [('E', 'm'), ('C', 'M7'), ('G', 'M'), ('G', 'M')],
    ]
    mel = {
        'E': [(0, 'B4', 2), (2, 'G4', 1), (3, 'B4', 1)],
        'C': [(0, 'C5', 2), (2, 'E5', 2)],
        'G': [(0, 'D5', 1.5), (1.5, 'G5', 1.5), (3, 'B5', 1)],
        'D': [(0, 'A5', 2), (2, 'F#5', 1), (3, 'D5', 1)],
        'A': [(0, 'C5', 1), (1, 'E5', 1), (2, 'G5', 2)],
    }
    for b in range(bars):
        t0 = b * 4 * B; blk = b // 4; root, q = cyc[blk][b % 4]; ch = chord(root + '3', q)
        v = voiced(ch)
        bright = blk >= 1
        for i, ix in enumerate([0, 1, 2, 1, 3, 2, 1, 2]):
            mix.add(piano(hz(v[ix] + 12), 2.6, .7), t0 + i * B / 2, -.2, .5, .4)
        if blk >= 1:
            for bt, nn, dd in mel.get(root, mel['G']):
                nn2 = m(nn) + (12 if blk >= 3 and root in ('G', 'D') and bt == 0 else 0)
                mix.add(piano(hz(nn2), 3 + dd, 1.0), t0 + bt * B, .25, .6, .45)
        att = 2.2 - .3 * blk
        for j, nn in enumerate(ch[:3]):
            l, r_ = pad(hz(nn + 12 + (12 if (blk >= 3 and j == 2) else 0)), 4 * B, att, 1.8, 1100 + 450 * blk, 4, .12, seed=b * 3 + j)
            mix.addst(l, r_, t0, .2 + .035 * blk, .4)
        mix.add(cello(hz(m(root + '2')), 3.6 * B, .5, 1.0, 900), t0, -.1, .5, .3)
        if blk >= 2:
            for i, nn in enumerate(('D6', 'G6', 'B6')[:3]):
                mix.add(musicbox(hz(m(nn))), t0 + (2 + i * .5) * B, .35, .2, .5)
        if blk >= 3 and b % 2 == 0: mix.add(brush(.3, .5), t0 + 2 * B, .1, .4, .3)
    return finish(mix, 3.6, .5, -21, damp=4000), bars * 4 * B

SONGS = {'bgm_bright': song_bright, 'bgm_uneasy': song_uneasy, 'bgm_dread': song_dread, 'bgm_tension': song_tension,
         'bgm_climax': song_climax, 'bgm_sorrow': song_sorrow, 'bgm_hope': song_hope}

def encode(x, path, kbps=80):
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    e = lameenc.Encoder(); e.set_bit_rate(kbps); e.set_in_sample_rate(SR); e.set_channels(2); e.set_quality(2)
    data = e.encode(np.ascontiguousarray(pcm.T).tobytes()) + e.flush()
    open(path, 'wb').write(data)
    return len(data)

def render(name, outdir=OUT):
    np.random.seed(7)
    body, dur = SONGS[name]()
    x = np.concatenate([body, body[:, :int(LOOPX * SR)]], axis=1)    # 본체 + 처음 LOOPX 초(주기 연장)
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, name + '.mp3'); n = encode(x, p)
    return body, dur, n

def report(name, body, dur, n):
    mono = body.mean(0); w = SR * 2
    r = [20 * np.log10(np.sqrt((mono[i:i + w] ** 2).mean()) + 1e-9) for i in range(0, len(mono) - w + 1, w)]
    sp = np.abs(np.fft.rfft(mono)); fr = np.fft.rfftfreq(len(mono), 1 / SR)
    d = np.abs(np.diff(mono)); seam = abs(mono[0] - mono[-1])
    print('%-12s 본체 %.1fs 파일 %.1fs %d KB | 피크 %.2f dBFS RMS %.1f dB | 2초창 RMS 최소 %.1f 최대 %.1f | 무게중심 %.0f Hz | 이음매 단차 %.4f (99.9%%분위 %.4f) | 좌우차 %.2f' % (
        name, dur, dur + LOOPX, n / 1024, 20 * np.log10(np.abs(body).max()), 20 * np.log10(np.sqrt((body ** 2).mean())),
        min(r), max(r), (sp * fr).sum() / sp.sum(), seam, np.quantile(d, .999), np.abs(body[0] - body[1]).mean() / (np.abs(body).mean() + 1e-9)))

if __name__ == '__main__':
    names = sys.argv[1:] or list(SONGS)
    for nm in names:
        body, dur, n = render(nm); report(nm, body, dur, n)
