#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G4 판정 래퍼 (2026-10-08) — 시뮬 이식 뒤에도 「5조합 × 900초 예외 0 · 무기 전종 사용」이 되는가.

본체는 Node(build_sim.js · mp_run.js · cover.js)이고 이 파일은 그것들을 차례로 불러 종료코드로 판정하는 편의 래퍼다.
파이썬 없는 서버(VPS)에서는 이 파일 없이 Node 명령을 직접 부르면 된다(README 참고).

사용:
  python3 tests/raid/g4_test.py                    # 기본: 5조합 + 보강 조합 × 900초 + 무기 전종(보통/각성) — 공용 기계 부하에 따라 20분~1시간
  python3 tests/raid/g4_test.py --quick            # 조합 1개 120초 + 무기 확인 60초(CI 점검용)
  python3 tests/raid/g4_test.py --secs 300 --combo "brj,jjg,mms,hrb"   # 조합을 직접(여러 번 쓸 수 있음)
  python3 tests/raid/g4_test.py --lint             # ESLint no-undef 게이트도(전역 eslint 필요)
  python3 tests/raid/g4_test.py --determinism      # 같은 시드로 두 번 돌려 판이 같은지
  옵션: --src survivors.html  --jobs N  --seed N  --timeout 초  --out 결과.json  --strict-keys  --no-cover

종료코드: 0 통과 · 1 예외(어느 조합이든) · 2 빌드(앵커) 실패 · 3 린트 실패 · 4 기준 미달(판 일찍 끝남·무기 미사용·값 이상·결정성 어긋남) · 5 환경 문제(node/eslint 없음, 시간 초과) · 64 옵션 오류
"""
import argparse, concurrent.futures as cf, json, os, random, shutil, subprocess, sys, time, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
NODE = shutil.which('node')

# 스크래치 runall.sh 의 5조합(R2 스파이크 재현용). 캐릭터가 늘면 아래 「보강 조합」이 빠진 캐릭터를 채운다.
ORIGINAL_COMBOS = ['brj,jjg,mms,hrb', 'ssu,amd,ildj,kyo', 'ddmj,psg,sr,ddo', 'tw,yumi,eom,yj', 'bgb,brj,psg,sr']
# 보강 조합에서 빈자리를 채우는 순서(스크래치에서 가장 무거웠던 조합의 캐릭터들 — 부하가 큰 쪽으로 보강)
PAD = ['eom', 'yj', 'tw', 'yumi', 'sr', 'ddo']
KNOWN_LINT = {'DOMMatrix'}   # 알려진 항목: try/catch 안에서 쓰는 브라우저 전용 API(설계서 §4.0 「DOMMatrix 1건」)


def uptime_s():
    try:
        return open('/proc/loadavg').read().split()[:3]
    except Exception:
        try:
            return ['%.2f' % v for v in os.getloadavg()]
        except Exception:
            return []


def sh(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 'timeout', (e.stdout or b'').decode('utf8', 'replace') if isinstance(e.stdout, bytes) else (e.stdout or ''), '시간 초과 %ds' % timeout, time.time() - t0


def last_json(out):
    for line in reversed((out or '').strip().splitlines()):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except Exception:
                pass
    return None


def node_cmd(script, *args):
    return [NODE, os.path.join(HERE, script)] + [str(a) for a in args]


def main():
    ap = argparse.ArgumentParser(description='G4 판정(시뮬 이식 뒤 5조합 × 900초 예외 0 · 무기 전종 사용)')
    ap.add_argument('--quick', action='store_true', help='조합 1개 120초 + 무기 확인 60초')
    ap.add_argument('--secs', type=float, default=None, help='조합당 게임 시간(초, 기본 900 · --quick 이면 120)')
    ap.add_argument('--combo', action='append', default=None, help='조합 "a,b,c,d" (여러 번 쓸 수 있음 · 쓰면 기본 조합 대신)')
    ap.add_argument('--no-extra', action='store_true', help='빠진 캐릭터를 채우는 보강 조합을 넣지 않는다')
    ap.add_argument('--no-cover', action='store_true', help='무기 전종 확인을 건너뛴다')
    ap.add_argument('--lint', action='store_true', help='ESLint no-undef 게이트(sim.js·sim_mp.js)')
    ap.add_argument('--determinism', action='store_true', help='같은 시드로 두 번 돌려 상태 해시가 같은지(120초)')
    ap.add_argument('--strict-keys', action='store_true', help='PKS/WORLD 에 분류 안 된 S 필드가 있으면 실패')
    ap.add_argument('--src', default=None, help='입력 survivors.html (기본: 이 워크트리 것)')
    ap.add_argument('--seed', type=int, default=None, help='기본 시드(조합마다 +i). 없으면 무작위로 정하고 결과에 적는다')
    ap.add_argument('--jobs', type=int, default=1, help='동시에 돌릴 조합 수(기본 1 — 공용 기계에서는 올리지 말 것)')
    ap.add_argument('--timeout', type=int, default=3600, help='조합 하나의 제한 시간(초). 넘으면 한 번만 두 배로 다시 한다')
    ap.add_argument('--out', default=None, help='결과 JSON 경로')
    a = ap.parse_args()
    if not NODE:
        print('node 를 찾을 수 없습니다(Node 22 필요)'); return 5
    secs = a.secs if a.secs else (120 if a.quick else 900)
    cover_secs = 60 if a.quick else 240
    src_args = ['--src', a.src] if a.src else []
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    report = {'v': 1, 'kind': 'g4', 'started_at': started, 'secs': secs, 'quick': a.quick, 'node': None, 'loadavg_start': uptime_s(), 'steps': {}}
    print('[g4] 시작 %s · load %s · 조합당 %g초' % (started, ' '.join(report['loadavg_start']), secs))

    rc, out, err, dt = sh([NODE, '--version'], 20)
    report['node'] = (out or '').strip()

    # 1) 빌드(앵커 검사 + 로드 시험)
    cmd = node_cmd('build_sim.js', *src_args)
    rc, out, err, dt = sh(cmd, 300)
    print(out.strip())
    if err.strip(): print(err.strip())
    report['steps']['build'] = {'rc': rc, 'secs': round(dt, 1)}
    if rc != 0:
        print('FAIL 빌드 — 종료코드 %s (2=앵커 어긋남, 3=로드 시험 실패)' % rc)
        finish(a, report, 2); return 2
    try:   # build_sim 은 --src 를 줘도 기본 폴더(.build)에 쓴다
        mf = json.load(open(os.path.join(HERE, '.build', 'manifest.json'), encoding='utf8'))
    except Exception:
        mf = None
    keys_warn = []
    if mf and mf.get('verify'):
        keys_warn = mf['verify'].get('warns', [])
        report['steps']['build']['unclassified_keys'] = (mf['verify'].get('classify') or {}).get('unclassified')
    if a.strict_keys and keys_warn:
        print('FAIL --strict-keys: ' + ' / '.join(keys_warn)); finish(a, report, 4); return 4

    # 2) 현재 캐릭터·무기 목록 확인
    rc, out, err, dt = sh(node_cmd('mp_run.js', '--list', *src_args), 120)
    info = last_json(out)
    if rc != 0 or not info:
        print('FAIL 목록 조회 실패 rc=%s %s' % (rc, err[-300:])); finish(a, report, 1); return 1
    chars, weapons = info['chars'], info['weapons']
    original_combos = info.get('default_combos') or ORIGINAL_COMBOS   # 단일 출처는 mp_run.js 의 DEFAULT_COMBOS
    pad = info.get('pad') or PAD
    report['survivors_sha256'] = info['survivors_sha256']
    report['chars'] = chars; report['weapons_now'] = len(weapons)
    print('[g4] 캐릭터 %d명 · 무기 %d종 · survivors sha256 %s…' % (len(chars), len(weapons), info['survivors_sha256'][:12]))

    # 3) 조합 정하기
    combos = list(a.combo) if a.combo else (original_combos[:1] if a.quick else list(original_combos))
    bad = [(c, k) for c in combos for k in c.split(',') if k not in chars]
    if bad:
        print('FAIL 조합에 CHARS 에 없는 캐릭터 키가 있습니다: ' + ', '.join('%s 의 %s' % b for b in bad) + ' — 이름이 바뀌었거나 삭제됐습니다. g4_test.py 의 조합을 고치세요.')
        finish(a, report, 4); return 4
    for c in combos:
        if len(c.split(',')) != 4:
            print('FAIL 조합은 캐릭터 4명이어야 합니다: ' + c); return 64
    extra = []
    if not a.no_extra and not a.combo and not a.quick:
        covered = {k for c in combos for k in c.split(',')}
        todo = [k for k in chars if k not in covered]
        while todo:
            grp = todo[:4]; todo = todo[4:]
            for p in pad:
                if len(grp) >= 4: break
                if p in chars and p not in grp: grp.append(p)
            extra.append(','.join(grp)); combos.append(extra[-1])
    covered = {k for c in combos for k in c.split(',')}
    uncovered = [k for k in chars if k not in covered]
    report['combos'] = combos; report['extra_combos'] = extra; report['chars_uncovered'] = uncovered
    if extra: print('[g4] 보강 조합 %s — 기본 5조합에 없던 캐릭터(%s)를 넣었습니다' % (extra, ','.join(k for e in extra for k in e.split(',') if k in chars and k not in {x for c in original_combos for x in c.split(',')})))
    show_unc = uncovered and not a.combo and not a.quick   # 일부러 조합을 고르거나 빠른 점검일 땐 알릴 필요가 없다
    print('[g4] 조합 %d개: %s%s' % (len(combos), ' | '.join(combos), (' · 어느 조합에도 안 든 캐릭터: ' + ','.join(uncovered)) if show_unc else ''))

    # 4) 조합 실행
    base_seed = a.seed if a.seed is not None else random.randrange(1, 1 << 30)
    report['base_seed'] = base_seed

    def one(i, combo):
        seed = base_seed + i
        timeout = a.timeout
        for attempt in (1, 2):
            rc, out, err, dt = sh(node_cmd('mp_run.js', '--combo', combo, '--secs', secs, '--seed', seed, '--cpu', '--json', *src_args), timeout)
            if rc != 'timeout':
                break
            timeout *= 2   # 공용 기계가 느린 탓일 수 있어 한 번만 두 배로 다시 한다
        r = last_json(out) or {}
        return {'combo': combo, 'seed': seed, 'rc': rc, 'secs_wall': round(dt, 1), 'attempt': attempt, 'result': r, 'stderr': (err or '')[-600:]}

    runs = []
    with cf.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        futs = [ex.submit(one, i, c) for i, c in enumerate(combos)]
        for f in futs:
            r = f.result(); runs.append(r)
            res = r['result']; ok = (r['rc'] == 0 and res.get('ok'))
            print('[g4] %-4s %-20s seed %-10s rc=%s wall %6.1fs · ticks %s · ms/tick %s · S.t %s · maxE %s · load %s' % (
                'PASS' if ok else 'FAIL', r['combo'], r['seed'], r['rc'], r['secs_wall'], res.get('ticks'), res.get('ms_per_tick'), res.get('game_s'), res.get('max_enemies'), ' '.join(uptime_s())))
            if not ok:
                if res.get('error'): print('      예외 t=%ss: %s' % (res['error'].get('at_game_s'), res['error'].get('stack')))
                for k in ('ended_early', 'stuck', 'nonfinite'):
                    if res.get(k): print('      %s: %s' % (k, res[k]))
                if r['rc'] == 'timeout' or not res: print('      %s' % r['stderr'])
    report['runs'] = runs

    # 5) 무기 전종
    cover = []
    if not a.no_cover:
        for evo in (False, True):
            cmd = node_cmd('cover.js', '--secs', cover_secs, '--json', '--seed', base_seed + 100 + int(evo), *src_args) + (['--evo'] if evo else [])
            rc, out, err, dt = sh(cmd, a.timeout)
            r = last_json(out) or {}
            cover.append({'evo': evo, 'rc': rc, 'secs_wall': round(dt, 1), 'result': r, 'stderr': (err or '')[-400:]})
            ok = rc == 0 and r.get('ok')
            print('[g4] %-4s 무기 전종(%s) %s/%s 사용 · 1차에서 빠진 것 %s → 2차에서 확인 %s · 끝내 못 본 것 %s · wall %.1fs' % (
                'PASS' if ok else 'FAIL', '각성' if evo else '보통', len(r.get('used', [])), r.get('weapons_now'),
                ','.join(r.get('first_pass_missing', [])) or '없음', ','.join(r.get('second_pass_recovered', [])) or '-', ','.join(r.get('missing', [])) or '없음', dt))
            if r.get('added') or r.get('removed'):
                print('      옛 39종 목록과 달라진 점 — 추가: %s · 삭제: %s' % (','.join(r.get('added', [])) or '없음', ','.join(r.get('removed', [])) or '없음'))
        report['cover'] = cover

    # 6) 결정성(선택)
    det = None
    if a.determinism:
        hs = []
        for _ in range(2):
            rc, out, err, dt = sh(node_cmd('mp_run.js', '--combo', combos[0], '--secs', 120, '--seed', 4242, '--json', *src_args), a.timeout)
            hs.append((last_json(out) or {}).get('hashes'))
        det = {'same': bool(hs[0]) and hs[0] == hs[1], 'a': hs[0], 'b': hs[1]}
        print('[g4] %-4s 결정성: 같은 시드 두 번 → 해시 %s' % ('PASS' if det['same'] else 'FAIL', '같음' if det['same'] else '다름 %s vs %s' % (hs[0], hs[1])))
        report['determinism'] = det

    # 7) 린트(선택)
    lint = None
    if a.lint:
        lint = run_lint(src_args)
        report['lint'] = lint

    # 판정
    code = 0
    if any(r['result'].get('error') for r in runs): code = 1
    elif any(r['rc'] == 'timeout' for r in runs): code = 5
    elif any(not (r['rc'] == 0 and r['result'].get('ok')) for r in runs): code = 4
    if code == 0 and any(not (c['rc'] == 0 and c['result'].get('ok')) for c in cover):
        code = 1 if any(c['result'].get('error') for c in cover) else (5 if any(c['rc'] == 'timeout' for c in cover) else 4)
    if code == 0 and det is not None and not det['same']: code = 4
    if code == 0 and lint is not None and not lint['ok']: code = 5 if lint.get('env') else 3
    if code == 0 and uncovered and not a.combo and not a.quick: print('[g4] 참고: 어느 조합에도 안 든 캐릭터 %s' % ','.join(uncovered))
    report['loadavg_end'] = uptime_s()
    n_ok = sum(1 for r in runs if r['rc'] == 0 and r['result'].get('ok'))
    print('[g4] 요약: 조합 %d/%d 통과 · 종료 load %s · 종료코드 %d' % (n_ok, len(runs), ' '.join(report['loadavg_end']), code))
    print('G4 ' + ('PASS' if code == 0 else 'FAIL'))
    finish(a, report, code)
    return code


def run_lint(src_args):
    """ESLint no-undef — sim.js(훅 꽂은 솔로)와 sim_mp.js(4액터 패치 사본) 둘 다. 알려진 항목(KNOWN_LINT)은 허용."""
    eslint = shutil.which('eslint')
    cmd0 = [eslint] if eslint else (['npx', '--no-install', 'eslint'] if shutil.which('npx') else None)
    if not cmd0:
        print('[g4] FAIL 린트: eslint 가 없습니다(전역 설치 또는 npx 필요)'); return {'ok': False, 'env': True, 'why': 'eslint 없음'}
    bdir = os.path.join(HERE, '.build')
    if src_args:
        print('[g4] 참고: --src 를 쓰면 린트는 기본 .build 폴더의 사본을 봅니다(build_sim 이 같은 폴더에 만들었는지 확인)')
    cmd = cmd0 + ['--no-config-lookup', '-c', os.path.join(HERE, 'eslint.sim.config.js'), '-f', 'json',
                  os.path.join(bdir, 'sim.js'), os.path.join(bdir, 'sim_mp.js')]
    rc, out, err, dt = sh(cmd, 300)
    try:
        res = json.loads(out)
    except Exception:
        print('[g4] FAIL 린트: eslint 출력을 읽지 못했습니다 rc=%s %s' % (rc, (err or out)[-300:])); return {'ok': False, 'env': True, 'why': 'eslint 출력 이상'}
    found = {}
    for f in res:
        for m in f['messages']:
            if m.get('fatal'):
                name = '<구문 오류>'
            elif m.get('ruleId') == 'no-undef':
                name = m['message'].split("'")[1] if "'" in m['message'] else m['message']
            else:
                continue
            found.setdefault(os.path.basename(f['filePath']), []).append({'name': name, 'line': m.get('line'), 'message': m['message']})
    new = {fn: [x for x in lst if x['name'] not in KNOWN_LINT] for fn, lst in found.items()}
    new = {fn: lst for fn, lst in new.items() if lst}
    known_n = sum(1 for lst in found.values() for x in lst if x['name'] in KNOWN_LINT)
    ok = not new
    print('[g4] %-4s 린트 no-undef: 알려진 항목 %d건(%s) · 새 항목 %s' % ('PASS' if ok else 'FAIL', known_n, ','.join(sorted(KNOWN_LINT)), json.dumps(new, ensure_ascii=False) if new else '없음'))
    return {'ok': ok, 'known': known_n, 'new': new, 'secs': round(dt, 1)}


def finish(a, report, code):
    report['exit'] = code
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(report, open(a.out, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        print('[g4] 결과 저장: ' + a.out)


if __name__ == '__main__':
    sys.exit(main())
