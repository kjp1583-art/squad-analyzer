# -*- coding: utf-8 -*-
"""tooling/fix_pack_minutes.py 시험 — 가짜 시트(실제 시트·접속 없음)로 판정과 쓰기 경로를 확인한다. 실제 시트를 고치는 도구라 쓰기 쪽을 꼼꼼히 본다.
  A. plan_tab: 망가진 판은 10행 전부 같은 m 으로 · 정상 판(옛 서식 포함)은 손대지 않음 · 애매한 판(행 부족·cs÷m 불일치·범위 밖·cs 0)은 보류 · 다시 돌려도 더 고칠 게 없음(멱등)
  B. rewrite_m: m 토큰 하나만 바꾼다(다른 토큰·m 비슷한 이름 그대로)
  C. main() 쓰기 경로(가짜 gspread): 미리보기는 안 쓴다 · APPLY=1 이면 지표 칸만 쓴다 · 그 사이 값이 바뀐 행은 건너뛴다 · 쓴 뒤 검증 실패면 비정상 종료
  D. 실제 사고 5판의 모양(분당 CS 가 m 칸에 든 팩)으로 게임 시간 26.7 등으로 돌아온다
사용: python3 tests/fix_pack_minutes_test.py
"""
import base64, importlib.util, io, os, sys, tempfile, types, unittest, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location('fpm', os.path.join(HERE, '..', 'tooling', 'fix_pack_minutes.py'))
F = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(F)

HEAD = ['게임ID', '날짜', '소환사명', 'PUUID', '진영', '포지션', '챔피언', '밴', '결과', '매치평가', '패치버전', 'KDA', '점수', '딜량', '아이템', '주룬', '보조룬', '스펠', '지표']
CS = [176, 158, 189, 220, 23, 166, 159, 166, 252, 23]   # 실제 사고 판 모양(서폿 둘이 cs 23)


def row(gid, i, pack, date='2026-09-19 22:16'):
    return [gid, date, 'n%d' % i, 'p%d' % i, '블루팀' if i < 5 else '레드팀', '탑', '챔', '', '승리', '', 'v16.20', '1/1/1', 10.0, 10000.0, '', '', '', '', pack]


def good_pack(cs, m=28.9, vs=True):
    return 'g8000|cs%d|m%.1f|kp50%s|cw2|wp10|wk2|dt20000' % (cs, m, '|vs20' if vs else '')


def bad_pack(cs, M):
    return 'g8000|cs%d|m%.2f|kp50.0|cw2|wp10|wk2|dt20000' % (cs, cs / M)


def bad_game(gid, M, css=CS, date='2026-09-19 22:16'):
    return [row(gid, i, bad_pack(c, M), date) for i, c in enumerate(css)]


def good_game(gid, M=28.9, vs=True):
    # CS 는 게임 시간에 맞춰 줄인다(15.3분에 252 CS 는 분당 16.5 — 현실에 없는 값이라 일부러 후보가 돼 버린다)
    return [row(gid, i, good_pack(int(c * min(1.0, M / 28.9)), M, vs)) for i, c in enumerate(CS)]


class A(unittest.TestCase):
    def test_fix_and_leave(self):
        vals = [HEAD] + good_game('#1', 26.5, vs=False) + bad_game('#2', 26.67) + good_game('#3') + bad_game('#4', 31.43, [170, 164, 188, 251, 44, 232, 220, 232, 209, 63])
        fixes, held, ng = F.plan_tab(vals)
        self.assertEqual(ng, 4)
        self.assertEqual(sorted(f['game'] for f in fixes), ['#2', '#4'])
        self.assertEqual(held, [])
        f2 = next(f for f in fixes if f['game'] == '#2')
        self.assertEqual(f2['m'], 26.7)
        self.assertEqual(len(f2['rows']), 10)
        self.assertEqual({r['row'] for r in f2['rows']}, set(range(12, 22)))   # 머리글 1 + #1 의 10행 → #2 는 12~21행
        for r in f2['rows']:
            self.assertIn('|m26.7|', r['new'])
            self.assertEqual(r['old'].replace(r['old'].split('|')[2], 'X'), r['new'].replace('m26.7', 'X'))   # m 토큰만 다르다
        f4 = next(f for f in fixes if f['game'] == '#4')
        self.assertEqual(f4['m'], 31.4)

    def test_idempotent(self):
        vals = [HEAD] + bad_game('#2', 26.67)
        fixes, _h, _n = F.plan_tab(vals)
        for f in fixes:
            for r in f['rows']: vals[r['row'] - 1][-1] = r['new']
        fixes2, held2, _ = F.plan_tab(vals)
        self.assertEqual((fixes2, held2), ([], []))

    def test_held(self):
        # 행 부족(7개)
        v = [HEAD] + bad_game('#a', 26.67)[:7]
        f, h, _ = F.plan_tab(v); self.assertEqual((f, [x[0] for x in h]), ([], ['#a']))
        # cs÷m 이 행마다 다름 — 한 행의 m 만 정상 값(진짜 게임 시간이 아님)
        g = bad_game('#b', 26.67); g[3][-1] = good_pack(220, 12.0)
        f, h, _ = F.plan_tab([HEAD] + g); self.assertEqual([x[0] for x in h], ['#b']); self.assertEqual(f, [])
        # 게임 시간이 범위 밖(cs÷m = 120)
        g = bad_game('#c', 120.0); f, h, _ = F.plan_tab([HEAD] + g); self.assertEqual([x[0] for x in h], ['#c']); self.assertEqual(f, [])
        # cs 가 0 인 행
        g = bad_game('#d', 26.67); g[4][-1] = 'g8000|cs0|m0.5|kp50.0|dt20000'
        f, h, _ = F.plan_tab([HEAD] + g); self.assertEqual([x[0] for x in h], ['#d']); self.assertEqual(f, [])
        # 서폿 행의 cs÷m 이 게임 시간과 크게 다름(±3% 밖)
        g = bad_game('#e', 26.67); g[4][-1] = bad_pack(23, 10.0)
        f, h, _ = F.plan_tab([HEAD] + g); self.assertEqual([x[0] for x in h], ['#e']); self.assertEqual(f, [])

    def test_normal_never_candidate(self):
        # 정상 행만 있으면 후보도 아니다(보류 목록에도 안 뜬다)
        f, h, n = F.plan_tab([HEAD] + good_game('#1') + good_game('#2', 15.3) + good_game('#3', 52.0, vs=False))
        self.assertEqual((f, h, n), ([], [], 3))

    def test_ignores_waiting_and_blank(self):
        g = good_game('#1'); g[0][-1] = '기록 대기'; g[1][-1] = ''
        f, h, n = F.plan_tab([HEAD] + g)
        self.assertEqual((f, h), ([], []))


class B(unittest.TestCase):
    def test_rewrite(self):
        self.assertEqual(F.rewrite_m('g1|cs23|m0.86|kp55.0|mx12', 26.74), 'g1|cs23|m26.7|kp55.0|mx12')
        self.assertIsNone(F.rewrite_m('g1|cs23|kp55.0', 26.7))          # m 토큰이 없으면 못 고친다(None)
        self.assertIsNone(F.rewrite_m('g1|m1.0|m2.0', 26.7))            # 둘이면 못 고친다


class FakeWS:
    def __init__(self, vals): self.vals = [list(r) for r in vals]; self.writes = []
    def get_all_values(self): return [[str(c) for c in r] for r in self.vals]
    def col_values(self, c): return [str(r[c - 1]) if c - 1 < len(r) else '' for r in self.vals]
    def update_cells(self, cells, value_input_option=None):
        for cell in cells:
            self.vals[cell.row - 1][cell.col - 1] = cell.value; self.writes.append((cell.row, cell.col, cell.value))
        self.opt = value_input_option


class C(unittest.TestCase):
    def run_main(self, ws, apply, hook=None, extra_tabs=()):
        class Cell:
            def __init__(s, row, col, value): s.row, s.col, s.value = row, col, value
        ws.title = 'CLASSIC_NORMAL'
        class SS:
            def worksheets(s): return [ws]        # 다른 탭(KIWI_KIWI · LOL_CLASSIC)은 없는 상황 — 재시도 대기 없이 건너뛰어야 한다
        gs = types.ModuleType('gspread'); gs.Cell = Cell
        gs.authorize = lambda creds: types.SimpleNamespace(open_by_key=lambda key: SS())
        oc = types.ModuleType('oauth2client'); sa = types.ModuleType('oauth2client.service_account')
        sa.ServiceAccountCredentials = types.SimpleNamespace(from_json_keyfile_name=lambda p, s: object())
        old_mods = {k: sys.modules.get(k) for k in ('gspread', 'oauth2client', 'oauth2client.service_account')}
        sys.modules.update({'gspread': gs, 'oauth2client': oc, 'oauth2client.service_account': sa})
        old_env = {k: os.environ.get(k) for k in ('CREDENTIALS_JSON_B64', 'APPLY')}
        os.environ['CREDENTIALS_JSON_B64'] = base64.b64encode(b'{}').decode(); os.environ['APPLY'] = '1' if apply else '0'
        old_cwd = os.getcwd(); tmp = tempfile.mkdtemp(); os.chdir(tmp)
        old_argv = sys.argv; sys.argv = ['fix_pack_minutes.py']
        if hook: hook(ws)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = F.main()
        finally:
            os.chdir(old_cwd); sys.argv = old_argv
            for k, v in old_mods.items():
                if v is None: sys.modules.pop(k, None)
                else: sys.modules[k] = v
            for k, v in old_env.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v
        return rc, out.getvalue()

    def sheet(self):
        return [HEAD] + good_game('#1') + bad_game('#2', 26.67) + good_game('#3')

    def test_preview_does_not_write(self):
        ws = FakeWS(self.sheet())
        rc, out = self.run_main(ws, apply=False)
        self.assertEqual(rc, 0); self.assertEqual(ws.writes, [])
        self.assertIn('수정 대상 — 10행', out); self.assertIn('APPLY=1', out); self.assertIn('BACKUP_JSON', out)

    def test_apply_writes_only_metric_cells(self):
        ws = FakeWS(self.sheet()); before = [list(r) for r in ws.vals]
        rc, out = self.run_main(ws, apply=True)
        self.assertEqual(rc, 0); self.assertEqual(len(ws.writes), 10)
        self.assertTrue(all(col == len(HEAD) for _r, col, _v in ws.writes))                 # 지표 칸(마지막 열)만
        changed = [(i, j) for i, (a, b) in enumerate(zip(before, ws.vals)) for j, (x, y) in enumerate(zip(a, b)) if x != y]
        self.assertEqual(sorted({j for _i, j in changed}), [len(HEAD) - 1])
        self.assertEqual(len(changed), 10)
        self.assertEqual(ws.opt, 'RAW')
        self.assertIn('수정 완료 — 10행', out)
        rc2, out2 = self.run_main(ws, apply=True)                                           # 다시 돌려도 더 안 고친다
        self.assertEqual(rc2, 0); self.assertIn('고칠 행 없음', out2); self.assertEqual(len(ws.writes), 10)

    def test_skips_rows_changed_meanwhile(self):
        ws = FakeWS(self.sheet())
        changed_row = 13
        def hook(w):   # 계획을 세운 뒤(get_all_values) 다른 사람이 한 칸을 고친 상황 — col_values 가 다른 값을 돌려준다
            orig = w.col_values
            state = {'n': 0}
            def cv(c):
                state['n'] += 1
                v = orig(c)
                if state['n'] == 1: v[changed_row - 1] = 'g1|cs1|m9.9'   # 쓰기 전 재확인에서 값이 다르게 보임
                return v
            w.col_values = cv
        rc, out = self.run_main(ws, apply=True, hook=hook)
        self.assertEqual(rc, 0)
        self.assertEqual(len(ws.writes), 9)
        self.assertNotIn(changed_row, [r for r, _c, _v in ws.writes])
        self.assertIn('값이 계획 때와 달라 건너뜀', out)

    def test_verification_failure_exits_nonzero(self):
        ws = FakeWS(self.sheet())
        orig = ws.update_cells
        def bad_update(cells, value_input_option=None):   # 쓴 것처럼 하지만 한 칸을 안 바꿔 둔다
            orig(cells[:-1], value_input_option)
        ws.update_cells = bad_update
        rc, out = self.run_main(ws, apply=True)
        self.assertEqual(rc, 2); self.assertIn('검증 실패', out)


class D(unittest.TestCase):
    def test_incident_shapes(self):
        # 실제 사고 5판의 cs 와 게임 시간(분): 26.67 · 24.2 · 31.43 · 37.42 · 35.42
        cases = {'#8387155519': (26.67, CS, 26.7), '#8387222960': (24.2, [137, 156, 203, 209, 28, 163, 143, 185, 250, 17], 24.2),
                 '#8387316403': (31.43, [170, 164, 188, 251, 44, 232, 220, 232, 209, 63], 31.4), '#8390902575': (37.42, [276, 196, 275, 358, 47, 263, 268, 324, 332, 37], 37.4),
                 '#8391010034': (35.42, [311, 239, 236, 310, 39, 326, 252, 221, 316, 30], 35.4)}
        vals = [HEAD]
        for gid, (M, css, _w) in cases.items(): vals += bad_game(gid, M, css)
        fixes, held, ng = F.plan_tab(vals)
        self.assertEqual((len(fixes), held, ng), (5, [], 5))
        for f in fixes: self.assertEqual(f['m'], cases[f['game']][2], f['game'])
        self.assertEqual(sum(len(f['rows']) for f in fixes), 50)


if __name__ == '__main__':
    unittest.main(verbosity=2)
