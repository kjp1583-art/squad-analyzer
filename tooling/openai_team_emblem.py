#!/usr/bin/env python3
"""🛡 멸망전 팀 엠블럼 — OpenAI 이미지 API(텍스트→이미지)로 오리지널 e스포츠 엠블럼을 뽑고 초록 배경을 지워 256px WebP 로 저장.
사용: python3 tooling/openai_team_emblem.py gen "<컨셉 영어 문구>" 출력.png     (초록 배경 원본)
      python3 tooling/openai_team_emblem.py cut 원본.png img/teams/<키>.webp     (배경 제거 · 256px)
실제 프로게임단 로고는 쓰지 않는다 — 컨셉(동물·상징)만 준다(상표 문제). 키는 환경에 없고 세션 프록시가 인증을 붙인다."""
import sys, subprocess, json, base64, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
def gen(concept, out):
    prompt = ("An original esports team emblem logo: %s. Bold clean vector-style crest, thick dark outline, strong silhouette, 2-3 colors with a metallic accent, "
              "centered, flat bright green (#00ff00) solid background with no shadow or glow, no text, no letters, no numbers, not based on any existing brand." % concept)
    r = subprocess.run(['curl','-sS','--max-time','100','-X','POST','https://api.openai.com/v1/images/generations','-H','Content-Type: application/json',
        '-d', json.dumps({'model':'gpt-image-2','prompt':prompt,'quality':'low','size':'1024x1024','output_format':'png'})], capture_output=True, text=True)
    try: j = json.loads(r.stdout)
    except Exception: return 'RAW ' + r.stdout[:200] + r.stderr[:200]
    if 'data' not in j: return json.dumps(j)[:300]
    open(out,'wb').write(base64.b64decode(j['data'][0]['b64_json'])); return 'ok'
if __name__ == '__main__':
    if sys.argv[1] == 'gen': print(gen(sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == 'cut':
        import importlib.util
        sp = importlib.util.spec_from_file_location('c', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openai_chick_art.py')); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        m.cut(sys.argv[2], sys.argv[3])
