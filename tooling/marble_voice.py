#!/usr/bin/env python3
"""🎙 여행마블 성우 더빙 클립 만들기 — OpenAI TTS(gpt-4o-mini-tts)로 밝고 활기찬 한국어 음성을 미리 뽑아 meongnyang-cafe/audio/marble/*.mp3 로 저장한다.
사용: python3 tooling/marble_voice.py [--only 접두사] [--force]
 · 키는 환경에 없다 — 세션 프록시가 api.openai.com 호출에 인증을 붙여 준다(CLAUDE.md 「그림」 절과 같다).
 · 칸 이름·카드 목록은 tooling/marble_voice_data.json (marble/index.html 의 TILES·CARDS 에서 뽑은 것). 칸/카드를 바꾸면 그 파일도 갱신.
 · 뽑은 클립은 받아쓰기(gpt-4o-mini-transcribe)로 되읽어 원문과 비슷한지 보고, 다르면 최대 6번 다시 뽑는다.
 · 게임은 이 클립들을 이어 붙여 말한다(marble/index.html 의 VOICE). 클립이 없으면 브라우저 기본 음성으로 대신한다."""
import sys, os, json, subprocess, re, difflib
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'meongnyang-cafe', 'audio', 'marble')
VOICE = 'shimmer'
BASE = ("Voice: a bright, bubbly, youthful Korean voice actress dubbing a cute animated mobile game for a couple. Very expressive, lively and smiley, quick and bouncy pacing, "
        "pitch slightly high, never flat or robotic. Pronounce the Korean words clearly and naturally. Mood: ")
MOOD = {
    'hype': 'excited and energetic, like announcing a fun surprise',
    'cute': 'sweet, playful and affectionate, with a little giggle in the voice',
    'sad': 'comically disappointed and whiny in a cute way, a little "aww"',
    'ask': 'curious and teasing, rising intonation like asking a friend a fun question',
    'win': 'overjoyed, celebrating loudly with big happy energy',
    'plain': 'cheerful and friendly, clear and quick',
}
def ko_num(n):
    d = '일이삼사오육칠팔구'; s = ''
    for v, u in ((1000, '천'), (100, '백'), (10, '십')):
        q, n = divmod(n, v)
        if q: s += ('' if q == 1 else d[q - 1]) + u
    if n: s += d[n - 1]
    return s
def clips():
    data = json.load(open(os.path.join(ROOT, 'tooling', 'marble_voice_data.json'), encoding='utf-8')); c = {}
    seen = set()
    for t in data['tiles']:
        if t['k'] in seen: continue
        seen.add(t['k']); txt = {'출발': '여기는 출발 칸이에요! 여행 시작!', '황금열쇠': '황금열쇠를 뽑아요!', '푸꾸옥': '푸꾸옥 섬에 도착!', '호안끼엠': '호안끼엠 호수에 도착!', '호이안': '베트남 호이안에 도착!', '미케비치': '미케 비치에 도착!', '협재해변': '협재 해변에 도착!'}.get(t['n'], t['n'] + '에 도착!'); c['t_' + t['k']] = (txt, 'hype', txt)
    F = {
        'f_pass': ('출발 지나기! 월급 이백 코인!', 'hype'),
        'f_own': ('내 땅이에요~ 좋아!', 'cute'), 'f_rent': ('통행료', 'plain'), 'f_pay': ('내요~ 아야!', 'sad'), 'f_get': ('받아요! 신난다!', 'hype'),
        'f_buy': ('구입 완료!', 'hype'), 'f_inn': ('숙소 완성!', 'hype'), 'f_hotel': ('호텔 완성! 대박!', 'win'),
        'f_jail': ('무인도에 도착! 두 턴 쉬어요~', 'cute'), 'f_air': ('공항! 다음 턴에 날아가요!', 'hype'), 'f_cafe': ('카페에서 쉬어가요~ 플러스 백!', 'cute'),
        'f_fine': ('벌금 백!', 'sad'), 'f_fly': ('날아가요! 슝~', 'hype'),
        'f_turn': ('내 차례! 주사위를 굴려요!', 'hype'), 'f_turnjail': ('무인도예요! 벌금을 내거나, 더블에 도전해요!', 'ask'), 'f_turnfly': ('공항 이동! 가고 싶은 칸을 눌러요!', 'hype'),
        'f_win': ('승리! 축하해요!', 'win'), 'f_lose': ('아쉬워요~ 다음엔 이길 거예요!', 'sad'), 'f_draw': ('무승부! 우리 둘 다 최고!', 'cute'),
        'f_opp': ('상대는,', 'plain'), 'f_com': ('컴퓨터는,', 'plain'),
    }
    for k, (t, m) in F.items(): c[k] = (t, m, t)
    for n in range(2, 13): c['d_%d' % n] = ('합계 %s!' % ko_num(n), 'hype', '합계' + ko_num(n))
    for n in data['rents']: c['r_%d' % n] = ('통행료 %s 코인' % ko_num(n), 'plain', '통행료' + ko_num(n) + '코인')
    for n in data['prices']: c['p_%d' % n] = ('땅값은 %s 코인, 살까요?' % ko_num(n), 'ask', '땅값은' + ko_num(n) + '코인살까요')
    for n in data['ups']:
        c['u0_%d' % n] = ('숙소를 지을까요? 비용은 %s 코인!' % ko_num(n), 'ask', '숙소를지을까요비용은' + ko_num(n) + '코인')
        c['u1_%d' % n] = ('호텔을 지을까요? 비용은 %s 코인!' % ko_num(n), 'ask', '호텔을지을까요비용은' + ko_num(n) + '코인')
    for cd in data['cards']:
        t = re.sub(r'[ㅋㅎㅠㅜ]+', '', re.sub(r'[^\w\s.,!?~\'"()+\-]', ' ', cd['t'], flags=re.U)).strip()
        t = re.sub(r'\s+', ' ', t); c['c_%d' % cd['i']] = (t, {'good': 'hype', 'bad': 'sad', 'move': 'hype', 'jail': 'cute', 'skip': 'cute'}[cd['g']], t)
    return c
def tts(text, mood, out):
    body = {'model': 'gpt-4o-mini-tts', 'voice': VOICE, 'input': text, 'instructions': BASE + MOOD[mood], 'response_format': 'mp3'}
    r = subprocess.run(['curl', '-sS', '--max-time', '70', '-X', 'POST', 'https://api.openai.com/v1/audio/speech', '-H', 'Content-Type: application/json', '-d', json.dumps(body), '-o', out, '-w', '%{http_code}'], capture_output=True, text=True)
    return r.stdout.strip() == '200' and os.path.getsize(out) > 1000
def stt(f):
    r = subprocess.run(['curl', '-sS', '--max-time', '70', '-X', 'POST', 'https://api.openai.com/v1/audio/transcriptions', '-F', 'model=gpt-4o-transcribe', '-F', 'language=ko', '-F', 'file=@' + f], capture_output=True, text=True)
    try: return json.loads(r.stdout)['text']
    except Exception: return ''
norm = lambda s: re.sub(r'[^가-힣a-z]', '', re.sub(r'\d+', lambda m: ko_num(int(m.group())) if int(m.group()) < 10000 else '', s.lower()))
def sim(a, b):
    a, b = norm(a), norm(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0
def trim(src, dst):
    af = 'silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-af', af, '-ac', '1', '-ar', '24000', '-b:a', '56k', dst], check=True)
def make(item):
    key, (text, mood, check) = item; dst = os.path.join(OUT, key + '.mp3'); tmp = dst + '.raw.mp3'; best = (-1, None)
    for attempt in range(6):
        if not tts(text, mood, tmp): continue
        s = sim(stt(tmp), check) if mood != 'plain' or True else 1
        if key.startswith('a_') or key.startswith('d_') or key.startswith('f_landprice'): pass
        if s > best[0]: best = (s, open(tmp, 'rb').read())
        if s >= .75: break
    if best[1] is None: return key, 'FAIL', 0
    open(tmp, 'wb').write(best[1]); trim(tmp, dst); os.remove(tmp); return key, 'ok', round(best[0], 2)
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True); args = sys.argv[1:]; only = args[args.index('--only') + 1] if '--only' in args else ''; force = '--force' in args
    todo = [(k, v) for k, v in clips().items() if k.startswith(only) and (force or not os.path.exists(os.path.join(OUT, k + '.mp3')))]
    print(len(todo), 'clips', flush=True); low = []
    with ThreadPoolExecutor(4) as ex:
        for k, st, s in ex.map(make, todo):
            print(k, st, s, flush=True)
            if st != 'ok' or s < .7: low.append((k, st, s))
    print('LOW', low)
