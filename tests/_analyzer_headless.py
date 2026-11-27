# -*- coding: utf-8 -*-
"""desktop/squad_analyzer.py 를 '창 없이' import 하기 위한 헬퍼 (테스트·벤치 전용).

분석기는 Windows 전용 import(tkinter/winreg)와 모듈 로드 시 ddragon 조회를 한다.
CI·개발 노트북(Linux)에도 tkinter·winreg 가 없으므로 가짜 모듈을 sys.modules 에 꽂아
**함수만** 꺼내 쓴다(위젯은 만들지 않는다 — 이 저장소의 다른 데스크톱 테스트와 같은 방침).

    from _analyzer_headless import load_analyzer          # tests/ 를 sys.path 에 둔 뒤
    S = load_analyzer()

Windows 에서는 진짜 tkinter/winreg 를 그대로 쓴다(가짜로 덮지 않는다).
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.join(os.path.dirname(HERE), "desktop")


class _Any:
    """Tk 위젯 대역 — 어떤 메서드/속성을 불러도 None 을 돌려주고, 자기 자신은 호출 가능."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def __call__(self, *a, **k):
        return None


def _fake_tkinter():
    tk = types.ModuleType("tkinter")
    for n in ("Tk", "Frame", "Label", "Button", "Canvas", "Toplevel", "StringVar", "IntVar",
              "BooleanVar", "DoubleVar", "PhotoImage", "Menu", "Text", "Entry", "Listbox",
              "Scrollbar", "Checkbutton", "Radiobutton", "Spinbox", "PanedWindow", "LabelFrame",
              "OptionMenu", "Widget", "Misc", "Place", "Pack", "Grid"):
        setattr(tk, n, _Any)
    tk.TclError = Exception
    tk.END = "end"
    tk.NORMAL = "normal"
    tk.DISABLED = "disabled"

    font = types.ModuleType("tkinter.font")
    font.Font = _Any
    font.nametofont = lambda *a, **k: _Any()
    font.families = lambda *a, **k: []
    tk.font = font

    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Style", "Frame", "Label", "Button", "Combobox", "Treeview", "Notebook",
              "Checkbutton", "Scrollbar", "Progressbar", "Entry", "Separator"):
        setattr(ttk, n, _Any)
    tk.ttk = ttk

    st = types.ModuleType("tkinter.scrolledtext")
    st.ScrolledText = _Any
    tk.scrolledtext = st

    mb = types.ModuleType("tkinter.messagebox")
    for n in ("showinfo", "showerror", "showwarning", "askyesno", "askokcancel"):
        setattr(mb, n, lambda *a, **k: True)
    tk.messagebox = mb

    fd = types.ModuleType("tkinter.filedialog")
    for n in ("askopenfilename", "asksaveasfilename", "askdirectory"):
        setattr(fd, n, lambda *a, **k: "")
    tk.filedialog = fd

    for name, mod in (("tkinter", tk), ("tkinter.font", font), ("tkinter.ttk", ttk),
                      ("tkinter.scrolledtext", st), ("tkinter.messagebox", mb),
                      ("tkinter.filedialog", fd)):
        sys.modules.setdefault(name, mod)
    return tk


def _fake_winreg():
    wr = types.ModuleType("winreg")
    wr.HKEY_CURRENT_USER, wr.HKEY_LOCAL_MACHINE = 1, 2
    wr.KEY_READ, wr.KEY_WRITE, wr.REG_SZ, wr.REG_DWORD = 1, 2, 1, 4
    for n in ("OpenKey", "CreateKey", "CloseKey", "SetValueEx"):
        setattr(wr, n, lambda *a, **k: None)
    wr.QueryValueEx = lambda *a, **k: ("", 0)
    wr.DeleteValue = lambda *a, **k: None
    return wr


def _fake_oauth2client():
    o = types.ModuleType("oauth2client")
    sa = types.ModuleType("oauth2client.service_account")

    class _Creds:
        @staticmethod
        def from_json_keyfile_name(*a, **k):
            return _Creds()

        @staticmethod
        def from_json_keyfile_dict(*a, **k):
            return _Creds()

    sa.ServiceAccountCredentials = _Creds
    o.service_account = sa
    return o, sa


def install_stubs():
    """없는 플랫폼 모듈만 가짜로 채운다(있는 건 그대로)."""
    if os.name != "nt":
        if "tkinter" not in sys.modules:
            try:
                import tkinter  # noqa: F401
            except Exception:
                _fake_tkinter()
        try:
            import winreg  # noqa: F401
        except Exception:
            sys.modules["winreg"] = _fake_winreg()
    try:
        import oauth2client.service_account  # noqa: F401
    except Exception:
        o, sa = _fake_oauth2client()
        sys.modules.setdefault("oauth2client", o)
        sys.modules.setdefault("oauth2client.service_account", sa)


_CACHE = {}


def load_analyzer(setup=None):
    """squad_analyzer 모듈을 1회 로드해 재사용. setup(S) 로 네트워크 의존을 미리 끊을 수 있다."""
    if "squad_analyzer" in _CACHE:
        return _CACHE["squad_analyzer"]
    install_stubs()
    if DESKTOP not in sys.path:
        sys.path.insert(0, DESKTOP)
    import squad_analyzer as S
    if setup:
        setup(S)
    _CACHE["squad_analyzer"] = S
    return S


# ── 합성 시트(실측 규모: 협곡 27,376행) ────────────────────────────────────────
CN_HEADERS = ["게임ID", "PUUID", "챔피언", "결과", "소환사명", "포지션", "진영", "밴",
              "매치평가", "KDA", "지표", "날짜", "점수", "패치버전", "팀", "라인상대",
              "CS", "시야", "딜량", "받은딜량", "골드", "아이템", "스펠", "주룬", "보조룬"]
PLAYERS = 10


def synthetic_rows(n_rows=27376, seed=83, headers=None, players=PLAYERS, days=420):
    """CLASSIC_NORMAL 모양의 합성 행 — 실제와 같은 '중복 구조'(같은 판 10행·같은 소환사명 반복)."""
    import random
    rnd = random.Random(seed)
    h = list(headers or CN_HEADERS)
    pos = ["탑", "정글", "미드", "원딜", "서폿"]
    champs = [f"챔프{i}" for i in range(1, 161)]
    names = [f"클랜원{i}#KR1" for i in range(1, 156)]
    pus = [f"pu-{i:04d}-{'ab' * 18}" for i in range(1, 156)]
    n_games = max(1, n_rows // players)
    rows = [h]
    for g in range(n_games):
        gid = f"KR_{7000000000 + g}"
        d = days - int(days * g / max(1, n_games))
        date = f"2026-{(d // 31) + 1:02d}-{(d % 28) + 1:02d} 21:{g % 60:02d}"
        patch = rnd.choice(["83.60", "83.65", "83.68", "83.71"])
        # 실제 협곡 기록처럼 '한 판 = 서로 다른 10명'(같은 판에 같은 사람이 두 번 나오지 않는다)
        lineup = rnd.sample(range(len(names)), min(players, len(names)))
        for k, i in enumerate(lineup):
            rows.append([
                gid, pus[i], rnd.choice(champs), rnd.choice(["승리", "패배"]), names[i],
                pos[k % 5], "블루팀" if k < 5 else "레드팀",
                rnd.choice(["밴 없음"] * 6 + champs[:40]),
                rnd.choice(["", "MVP", "ACE", "평범"]),
                f"{rnd.randrange(1, 16)}/{rnd.randrange(0, 12)}/{rnd.randrange(0, 25)}",
                f"cs{rnd.randrange(40, 320)}m{rnd.randrange(18, 40)}vs{rnd.randrange(10, 90)}",
                date, str(rnd.randrange(0, 100)), patch, "",
                rnd.choice(champs), str(rnd.randrange(50, 400)),
                str(rnd.randrange(5, 60)), str(rnd.randrange(3000, 40000)),
                str(rnd.randrange(3000, 40000)), str(rnd.randrange(4000, 25000)),
                "|".join(str(rnd.randrange(1000, 60000)) for _ in range(7)),
                "Flash|Teleport", "정밀", "결의",
            ])
    return rows
