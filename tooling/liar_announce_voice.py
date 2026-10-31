#!/usr/bin/env python3
"""🎙 라이어 게임 「그는 라이어가… 맞습니다/아닙니다」 발표 음성 만들기
OpenAI 음성 합성(POST https://api.openai.com/v1/audio/speech) 으로 세 조각을 뽑고 → ffmpeg 로 음성 변조(음정↓·느리게·링모듈레이터·비트크러셔·코러스·동굴 메아리) → audio/liar_*.ogg
  python3 tooling/liar_announce_voice.py            # 세 조각 모두 새로 만든다
  python3 tooling/liar_announce_voice.py --effects-only 입력.wav 출력.ogg   # 변조 단계만(합성 음성 없이 시험할 때)
키는 환경에 없다 — 세션 프록시가 api.openai.com 호출에 인증을 붙인다(코드·저장소에 키를 쓰지 않는다).
2026-10-31 첫 실행 때 크레딧 소진(429 credit_balance_exhausted) 으로 못 만들었다 → 화면은 파일이 없으면 브라우저 음성(speechSynthesis)+합성 저음으로 대신한다.
조각: seg1 「그는 라이어가…」 · yes 「맞습니다.」 · no 「아닙니다.」 (각 ≤50KB, 합계 ≤200KB). 길이는 화면이 읽어 타이핑 속도를 맞춘다(liar.html 의 ANN 상수)."""
import json, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'audio')
PIECES = {'seg1': '그는 라이어가', 'yes': '맞습니다.', 'no': '아닙니다.'}
INSTR = ('한국어로 말한다. 아주 낮고 굵은 남자 목소리, 게임쇼 진행자가 긴장감을 쥐어짜며 천천히, 한 음절씩 힘을 주어 발표하는 말투. '
         'Speak Korean in a very deep, gravelly, slow, ominous male announcer voice with dramatic pauses.')
# 음정 -5반음(×0.749) · 템포는 원래의 0.9배로 느리게 → asetrate 로 음정을 내리고 atempo 로 길이를 맞춘다
PITCH = 0.749; TEMPO = 0.90 / PITCH
FX = (f'asetrate=44100*{PITCH},aresample=44100,atempo={TEMPO:.3f},'
      'acrusher=bits=11:mode=lin:aa=1:mix=0.35,'                      # 비트크러시(거친 질감)
      'chorus=0.6:0.9:50|63:0.4|0.32:0.25|0.4:2|1.3,'                 # 코러스(겹친 목소리)
      'aecho=0.8:0.85:70|140|280:0.35|0.25|0.15,'                      # 동굴 메아리
      'lowpass=f=5200,highpass=f=70,alimiter=limit=0.89:level=disabled')
def tts(text, out_wav):
    body = json.dumps({'model': 'gpt-4o-mini-tts', 'voice': 'onyx', 'input': text, 'instructions': INSTR, 'response_format': 'wav'})
    for att in range(4):
        r = subprocess.run(['curl', '-sS', '--max-time', '90', '-X', 'POST', 'https://api.openai.com/v1/audio/speech', '-H', 'Content-Type: application/json', '-d', body, '-o', out_wav, '-w', '%{http_code}'], capture_output=True, text=True)
        if r.stdout.strip() == '200': return True
        msg = open(out_wav, 'rb').read(300).decode('utf8', 'ignore') if os.path.exists(out_wav) else ''
        print('TTS 실패', r.stdout, msg.replace('\n', ' ')[:200], file=sys.stderr)
        if 'credit' in msg or 'insufficient' in msg: return False
        time.sleep(6 * (att + 1))
    return False
def effects(src, dst):
    # 링모듈레이터: 원음 70% + (원음 × 55Hz 사인) 30% → 로봇 같은 떨림. 앞뒤 정적 정리 후 mono 22.05kHz ogg
    fc = ('[0:a]aformat=sample_rates=44100:channel_layouts=mono,silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=1:stop_threshold=-45dB:stop_duration=0.3,asplit[d][r];'
          '[r]asetrate=44100,volume=1[r1];aevalsrc=sin(2*PI*55*t):s=44100:d=6[m];[r1][m]amultiply,volume=0.9[rm];'
          '[d][rm]amix=inputs=2:weights=0.7 0.3:normalize=0,' + FX + ',aresample=22050,apad=pad_dur=0.25,volume=1.1')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-filter_complex', fc, '-ac', '1', '-c:a', 'libvorbis', '-q:a', '2', dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print(r.stderr[-400:], file=sys.stderr); return False
    return True
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--effects-only':
        sys.exit(0 if effects(sys.argv[2], sys.argv[3]) else 1)
    os.makedirs(OUT, exist_ok=True); ok = True; total = 0
    for k, text in PIECES.items():
        raw = os.path.join('/tmp', f'liar_{k}_raw.wav'); dst = os.path.join(OUT, f'liar_{k}.ogg')
        if not tts(text, raw): ok = False; continue
        if not effects(raw, dst): ok = False; continue
        sz = os.path.getsize(dst); total += sz; print(k, text, sz, 'bytes')
        if sz > 50 * 1024: print('경고: 50KB 초과', k, file=sys.stderr)
    print('합계', total, 'bytes'); sys.exit(0 if ok else 1)
