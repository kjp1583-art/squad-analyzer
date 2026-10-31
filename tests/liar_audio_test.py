#!/usr/bin/env python3
"""라이어 게임 소리 점검 — liar_audio.js 를 OfflineAudioContext 로 그대로 렌더해 파형을 숫자로 본다.
무음 · 클리핑 · 직류 · NaN · 이음매(트랙 전환 때 끊김/튐) · 효과음 길이를 확인한다. (귀로 듣는 시험은 아니다 — 파형이 멀쩡한지만 본다)
사용: CHROME=... python3.13 tests/liar_audio_test.py"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CHROME = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f' {info}'))
    if not cond: fails.append(name)
JS = """
async (spec) => {
  const r = await LiarAudio._render(spec); const d = r.data, n = d.length, sr = r.sr;
  let nan = 0, pk = 0, sum = 0, ss = 0, clip = 0, jump = 0, jumpAt = 0;
  for (let i = 0; i < n; i++) { const x = d[i]; if (!isFinite(x)) { nan++; continue; } const a = Math.abs(x); if (a > pk) pk = a; if (a >= 0.99) clip++; sum += x; ss += x * x; if (i) { const j = Math.abs(x - d[i - 1]); if (j > jump) { jump = j; jumpAt = i / sr; } } }
  const win = Math.floor(sr * 0.1), rms = []; for (let s = 0; s + win <= n; s += win) { let q = 0; for (let i = s; i < s + win; i++) q += d[i] * d[i]; rms.push(Math.sqrt(q / win)); }
  return { nan, peak: pk, dc: sum / n, rms: Math.sqrt(ss / n), clip, jump, jumpAt, win: rms, sr, n };
}
"""
async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path=CHROME); pg = await br.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('file://' + os.path.join(ROOT, 'tests', 'liar_audio_blank.html'))
        tracks = await pg.evaluate('LiarAudio.trackNames()'); sfxs = await pg.evaluate('LiarAudio.sfxNames()')
        check('트랙 9종 · 효과음 15종 이상', len(tracks) >= 9 and len(sfxs) >= 15, (tracks, sfxs))
        for tr in tracks:
            for tn in ((0, 1) if tr in ('discuss', 'vote') else (0,)):
                m = await pg.evaluate(JS, {'dur': 14, 'tracks': [[tr, 0]], 'tension': tn})
                tag = f'BGM {tr}' + (f' 긴장 {tn}' if tr in ('discuss', 'vote') else '')
                quiet = sum(1 for v in m['win'][20:] if v < 1e-4) / max(1, len(m['win'][20:]))
                check(f'{tag}: NaN 없음·클리핑 없음(피크 {m["peak"]:.2f})', m['nan'] == 0 and m['peak'] < 0.99 and m['clip'] == 0, m)
                check(f'{tag}: 무음 아님(rms {m["rms"]:.4f}) · 직류 없음(dc {m["dc"]:.5f}) · 끊긴 구간 {quiet:.0%}', 0.002 < m['rms'] < 0.5 and abs(m['dc']) < 0.01 and quiet < 0.2, m['rms'])
        # 이음매: 트랙 전환 크로스페이드(6초에 전환) — 전환 앞뒤로 갑자기 조용해지거나 튀지 않는지
        pairs = [('lobby', 'reveal'), ('reveal', 'hints'), ('hints', 'discuss'), ('discuss', 'vote'), ('vote', 'result'), ('result', 'win'), ('result', 'lose'), ('guess', 'result')]
        for a, b in pairs:
            m = await pg.evaluate(JS, {'dur': 14, 'tracks': [[a, 0], [b, 6]], 'tension': 0.5})
            w = m['win']; seam = w[54:78]; ref = sum(w[20:50]) / 30
            gap = min(seam) / max(ref, 1e-9)
            check(f'이음매 {a}→{b}: 전환 구간이 끊기지 않는다(최소 rms/평소 {gap:.2f}) · 튐 {m["jump"]:.3f}', gap > 0.25 and m['jump'] < 0.25 and m['nan'] == 0 and m['peak'] < 0.99, (gap, m['jump'], m['jumpAt']))
        for s in sfxs:
            m = await pg.evaluate(JS, {'dur': 4, 'sfx': [[s, 0.2]], 'tracks': []})
            if s == 'silence': check('효과음 silence: (BGM 덕킹 전용 — 단독으론 무음이 정상)', m['nan'] == 0); continue
            tail = sum(m['win'][-5:]) / 5
            check(f'효과음 {s}: 소리가 난다(피크 {m["peak"]:.2f}) · 클리핑·NaN·직류 없음 · 끝에 잘린 소리 없음', m['nan'] == 0 and 0.01 < m['peak'] < 0.99 and m['clip'] == 0 and abs(m['dc']) < 0.01 and tail < 0.01, m['peak'])
        # 덕킹(정적) — hitLiar 뒤 BGM 이 눈에 띄게 줄었다가 돌아온다
        m = await pg.evaluate(JS, {'dur': 9, 'tracks': [['result', 0]], 'sfx': [['hitLiar', 4]], 'tension': 0})
        w = m['win']; before = sum(w[25:38]) / 13; during = sum(w[50:58]) / 8; after = sum(w[80:89]) / 9
        check(f'정적: 라이어 공개 직후 BGM 이 줄었다 돌아온다(전 {before:.4f} · 중 {during:.4f} · 후 {after:.4f})', during < before * 0.7 and after > during, (before, during, after))
        check('페이지 오류 없음', not errs, errs[:3])
        await br.close()
    print('\n' + ('ALL PASS' if not fails else f'FAILED {len(fails)}: {fails}')); sys.exit(1 if fails else 0)
asyncio.run(main())
