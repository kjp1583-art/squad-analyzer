#!/usr/bin/env python3
"""장편 원고를 화면 없이 돌려서 모든 엔딩에 가는 선택 경로를 찾는다.
결정: 단서 줍기(줍는다/안 줍는다) · 선택지 번호 · 퍼즐(성공/실패, 투표는 후보 번호) · 시간초과.
사용: python3 tests/novel_sim.py [--out paths.json]"""
import sys, os, json, glob, time
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'tooling'))
import novel_build as nb

def load(src=None):
    d = os.path.join(ROOT, 'data', 'novel', 'ch')
    files = sorted(glob.glob(os.path.join(d, 'ch_*.txt')), key=nb.file_key) if not src else [src]
    story, ctx, per = nb.build(files)
    return story, ctx

def ev(cs, V, clues):
    for n, op, x, neg in cs:
        v = len(clues) if n == 'clues' else V.get(n, 1 if n in clues else 0)
        if op == 'flag': r = v > 0; r = (not r) if neg else r
        else: r = {'>=': v >= x, '<=': v <= x, '>': v > x, '<': v < x, '==': v == x, '!=': v != x}[op]
        if not r: return False
    return True

def acts(a, V, lab):
    pc = None
    for x in a:
        if x[0] == 'set': V[x[1]] = x[2]
        elif x[0] == 'add': V[x[1]] = V.get(x[1], 0) + x[2]
        elif x[0] == 'goto': pc = lab[x[1]]
    return pc

def advance(story, pc, V, clues, stats):
    """결정이 필요한 곳(또는 엔딩)까지 진행. -> (kind, pc, payload)"""
    ops = story['ops']; lab = story['labels']; n = 0
    while True:
        n += 1
        if n > 20000: return ('loop', pc, None)
        if pc >= len(ops): return ('fall', pc, None)
        op = ops[pc]; k = op['o']
        if 'pcs' in stats: stats['pcs'].add(pc)
        if k in ('say', 'nar', 'tho'): stats['lines'] += 1; pc += 1
        elif k == 'set': V[op['k']] = op['v']; pc += 1
        elif k == 'unset': V[op['k']] = 0; pc += 1
        elif k == 'add': V[op['k']] = V.get(op['k'], 0) + op['v']; pc += 1
        elif k == 'jf': pc = pc + 1 if ev(op['c'], V, clues) else op['to']
        elif k == 'jmp': pc = op['to']
        elif k == 'goto': pc = lab[op['l']]
        elif k == 'clue':
            if op['id'] in clues: pc += 1
            else: return ('clue', pc, op['id'])
        elif k == 'choice': return ('choice', pc, [i for i, o in enumerate(op['opts']) if ev(o['c'], V, clues)])
        elif k == 'puz': return ('puz', pc, op)
        elif k == 'end': return ('end', pc, op['id'])
        else: pc += 1

def options(story, kind, pc, payload, V, clues):
    op = story['ops'][pc]
    if kind == 'clue': return [True] if os.environ.get('SIM_ALLCLUE') else [True, False]
    if kind == 'choice':
        o = [('c', i) for i in payload]
        if op['to']: o.append(('timeout', 0))
        return o
    if kind == 'puz':
        d = op['d']
        if op['type'] == 'vote':
            r = [('v', i) for i in range(len(d['cands']))]
            if d.get('refuse') and ev(d['refuse']['c'], V, clues): r.append(('v', len(d['cands'])))
            return r
        return [('p', 'ok'), ('p', 'fail')] if 'fail' in d else [('p', 'ok')]

def apply(story, kind, pc, payload, dec, V, clues):
    ops = story['ops']; lab = story['labels']; op = ops[pc]
    if kind == 'clue':
        if dec: clues.add(payload)
        return pc + 1
    if kind == 'choice':
        if dec[0] == 'timeout': return lab[op['to']]
        j = acts(op['opts'][dec[1]]['a'], V, lab); return pc + 1 if j is None else j
    d = op['d']
    if op['type'] == 'vote':
        a = d['cands'][dec[1]]['do'] if dec[1] < len(d['cands']) else d['refuse']['do']
    else: a = d['ok'] if dec[1] == 'ok' else d.get('fail', [])
    j = acts(a, V, lab); return pc + 1 if j is None else j

def relevant(story):
    rv = set(); ids = set()
    def cs(c):
        for n, *_ in c: rv.add(n)
    for op in story['ops']:
        k = op['o']
        if k == 'jf': cs(op['c'])
        elif k == 'choice':
            for o in op['opts']: cs(o['c'])
        elif k == 'puz':
            d = op['d']
            for h in d.get('hints', []):
                cs(h['c']); rv.update(h.get('any', []))
            if d.get('refuse'): cs(d['refuse']['c'])
            if isinstance(d.get('hint'), dict): cs(d['hint']['c'])
        if k == 'clue': ids.add(op['id'])
    return rv, ids

def search(story, limit=40_000_000, want=None):
    RV, CID = relevant(story)
    def skey(pc, V, clues):
        return (pc, tuple(sorted((k, min(v, 9)) for k, v in V.items() if k in RV)), tuple(sorted(c for c in clues if c in RV)), len(clues) if 'clues' in RV else 0)
    ends = {e['id'] for e in story['endings']}; want = set(want or ends); found = {}
    seen = set(); t0 = time.time()
    # DFS, 선호 순서: 줍기 > 첫 선택 ... (여러 방문 순서를 섞어서 시도)
    import random
    for attempt in range(40):
        rnd = random.Random(attempt); stack = []
        V0, c0 = {}, set(); st = {'lines': 0}
        k, pc, pl = advance(story, 0, V0, c0, st)
        stack.append((k, pc, pl, V0, c0, [], st['lines']))
        steps = 0
        while stack and steps < limit // 40 and want - set(found):
            k, pc, pl, V, clues, path, lines = stack.pop(); steps += 1
            if k == 'end':
                if pl not in found: found[pl] = (path, lines)
                continue
            if k in ('loop', 'fall'): continue
            key = skey(pc, V, clues)
            if key in seen: continue
            seen.add(key)
            opts = options(story, k, pc, pl, V, clues)
            if attempt: rnd.shuffle(opts)
            for dec in reversed(opts):
                V2 = dict(V); c2 = set(clues); npc = apply(story, k, pc, pl, dec, V2, c2)
                st = {'lines': 0}; k2, pc2, pl2 = advance(story, npc, V2, c2, st)
                stack.append((k2, pc2, pl2, V2, c2, path + [(k, pc, dec if not isinstance(dec, tuple) else list(dec))], lines + st['lines']))
        if not (want - set(found)): break
    return found, len(seen), time.time() - t0

if __name__ == '__main__':
    story, ctx = load()
    for e in ctx.errors: print('오류', e)
    found, n, dt = search(story, limit=40_000_000)
    print('방문한 상태 %d개 · %.1f초' % (n, dt))
    for e in story['endings']:
        f = found.get(e['id'])
        print('엔딩 %-5s %s' % (e['id'], ('도달 · 결정 %d번 · 줄 %d' % (len(f[0]), f[1])) if f else '★ 도달 못 함'))
    if '--out' in sys.argv:
        json.dump({k: v[0] for k, v in found.items()}, open(sys.argv[sys.argv.index('--out') + 1], 'w'), ensure_ascii=False)
