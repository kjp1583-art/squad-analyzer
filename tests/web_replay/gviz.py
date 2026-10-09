# -*- coding: utf-8 -*-
"""구글 시트(gviz) 응답을 흉내 낸다 — xlsx 스냅샷 -> gviz JSON, 그리고 gviz 응답 문자열 만들기.

웹(index.html)은 시트를 `.../gviz/tq?gid=…|sheet=…&headers=…&tqx=out:json[;responseHandler:콜백]` 로 읽는다.
실제 gviz 와 같게 맞춘 규칙(2026-10-09 실제 응답과 칸 단위로 대조해 확인):
  · 열 종류 = 그 열에서 가장 많은 값의 종류(string / number / date / datetime / boolean). 동률이면 string.
  · 종류가 다른 칸은 비운다(null) — 예: 숫자 열 안의 '24.7' 문자열은 null.
    단, 문자열 열 안의 날짜 칸은 칸 서식대로 글자로 나온다("yy/m/d" -> "11/6/27").
  · 숫자 칸 = {"v":75.0,"f":"75"} (f 는 서식 적용 글자) · 날짜 칸 = {"v":"Date(2026,9,5)","f":"2026-10-05"}
  · 빈 문자열·빈 칸 = null
"""
import datetime as _dt
import json
import re

CB_PREFIX = "/*O_o*/\n"


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------- 엑셀 서식 -> 글자 ----------
def _tokens(fmt):
    return re.findall(r'yyyy|yy|mmmm|mmm|mm|m|dd|d|hh|h|ss|s|AM/PM|am/pm|"[^"]*"|\\.|.', fmt, flags=re.I)


def fmt_datetime(v, fmt):
    """엑셀 날짜 서식(yyyy-mm-dd h:mm 등)으로 글자를 만든다. 'm' 은 h 뒤·s 앞이면 '분'."""
    if isinstance(v, _dt.date) and not isinstance(v, _dt.datetime):
        v = _dt.datetime(v.year, v.month, v.day)
    toks = _tokens(fmt or "yyyy-mm-dd")
    low = [t.lower() for t in toks]
    out = []
    for i, t in enumerate(low):
        if t in ("m", "mm", "mmm", "mmmm"):
            prev = next((x for x in reversed(low[:i]) if x in ("h", "hh", "ss", "s", "yyyy", "yy", "dd", "d", "m", "mm")), "")
            nxt = next((x for x in low[i + 1:] if x in ("s", "ss", "h", "hh", "yyyy", "yy", "dd", "d")), "")
            minute = prev in ("h", "hh") or nxt in ("s", "ss")
            if minute: out.append(f"{v.minute:02d}" if t == "mm" else str(v.minute))
            else: out.append(f"{v.month:02d}" if t == "mm" else str(v.month))
        elif t == "yyyy": out.append(f"{v.year:04d}")
        elif t == "yy": out.append(f"{v.year % 100:02d}")
        elif t == "dd": out.append(f"{v.day:02d}")
        elif t == "d": out.append(str(v.day))
        elif t == "hh": out.append(f"{v.hour:02d}")
        elif t == "h": out.append(str(v.hour))
        elif t == "ss": out.append(f"{v.second:02d}")
        elif t == "s": out.append(str(v.second))
        elif toks[i].startswith('"'): out.append(toks[i][1:-1])
        elif toks[i].startswith("\\"): out.append(toks[i][1:])
        else: out.append(toks[i])
    return "".join(out)


def fmt_number(v, pattern):
    """숫자 서식 글자 — General / 0 / 0.0 / #,##0 정도만 쓴다(그 밖에는 General)."""
    if isinstance(v, bool): return "TRUE" if v else "FALSE"
    p = (pattern or "General").strip()
    if p == "General" or not re.fullmatch(r"[#0,]*(\.0+)?", p):
        return _general(v)
    dec = len(p.split(".")[1]) if "." in p else 0
    s = f"{v:,.{dec}f}" if "," in p else f"{v:.{dec}f}"
    return s


def _general(v):
    if isinstance(v, int) or (isinstance(v, float) and v == int(v) and abs(v) < 1e15):
        return str(int(v))
    return ("%.15g" % v)


# ---------- 칸 분류 ----------
def _kind(v, fmt):
    if v is None: return None
    if isinstance(v, str): return "string" if v != "" else None
    if isinstance(v, bool): return "boolean"
    if isinstance(v, (int, float)): return "number"
    if isinstance(v, _dt.datetime):
        return "datetime" if (v.hour or v.minute or v.second or re.search(r"h|s", fmt or "", re.I)) else "date"
    if isinstance(v, _dt.date): return "date"
    if isinstance(v, _dt.time): return "timeofday"
    return "string"


def _date_v(v, kind):
    if kind == "date": return f"Date({v.year},{v.month - 1},{v.day})"
    return f"Date({v.year},{v.month - 1},{v.day},{v.hour},{v.minute},{v.second})"


def table_from_rows(rows, fmts=None, headers=1):
    """rows: 2차원 리스트(값만) · fmts: 같은 모양의 서식 글자(없으면 None) -> gviz table dict.
    headers=1 이면 첫 행이 열 이름, 0 이면 첫 행도 데이터(열 이름은 빈칸)."""
    rows = [list(r) for r in rows]
    # 뒤쪽 빈 행 정리
    def empty_row(r): return all(c is None or c == "" for c in r)
    while rows and empty_row(rows[-1]): rows.pop()
    ncol = max((len(r) for r in rows), default=0)
    # 뒤쪽 빈 열 정리(머리글도 비고 값도 비면 뺀다)
    def col_used(j): return any((j < len(r) and r[j] not in (None, "")) for r in rows)
    while ncol and not col_used(ncol - 1): ncol -= 1
    rows = [r + [None] * (ncol - len(r)) for r in rows]
    fm = [list(f) + [None] * (ncol - len(f)) for f in fmts] if fmts else [[None] * ncol for _ in rows]
    if headers:
        head, body, bfm = rows[:1], rows[1:], fm[1:]
        labels = [("" if c is None else str(c)) for c in (head[0] if head else [None] * ncol)]
    else:
        body, bfm, labels = rows, fm, [""] * ncol
    cols, kinds = [], []
    for j in range(ncol):
        cnt = {}
        for r, f in zip(body, bfm):
            k = _kind(r[j], f[j])
            if k: cnt[k] = cnt.get(k, 0) + 1
        if cnt:
            best = max(cnt.values())
            top = [k for k, n in cnt.items() if n == best]
            kind = "string" if "string" in top else top[0]
        else:
            kind = "string"
        kinds.append(kind)
        col = {"id": col_letter(j), "label": labels[j], "type": kind}
        if kind == "number":
            pat = next((f[j] for r, f in zip(body, bfm) if isinstance(r[j], (int, float)) and not isinstance(r[j], bool)), None)
            col["pattern"] = pat or "General"
        elif kind in ("date", "datetime"):
            pat = next((f[j] for r, f in zip(body, bfm) if isinstance(r[j], (_dt.date, _dt.datetime))), None)
            col["pattern"] = pat or ("yyyy-mm-dd" if kind == "date" else "yyyy-mm-dd h:mm:ss")
        cols.append(col)
    out_rows = []
    for r, f in zip(body, bfm):
        cells = []
        for j in range(ncol):
            v, fmt, kind = r[j], f[j], kinds[j]
            k = _kind(v, fmt)
            if k is None: cells.append(None); continue
            if kind == "string":
                if k == "string": cells.append({"v": v})
                elif k in ("date", "datetime"): cells.append({"v": fmt_datetime(v, fmt)})   # 문자열 열 안의 날짜 -> 서식 글자
                elif k == "number": cells.append({"v": fmt_number(v, fmt)})
                elif k == "boolean": cells.append({"v": "TRUE" if v else "FALSE"})
                else: cells.append({"v": str(v)})
            elif kind == "number":
                cells.append({"v": float(v), "f": fmt_number(v, fmt)} if k == "number" else None)
            elif kind in ("date", "datetime"):
                cells.append({"v": _date_v(v, kind), "f": fmt_datetime(v, fmt)} if k in ("date", "datetime") else None)
            elif kind == "boolean":
                cells.append({"v": bool(v), "f": "TRUE" if v else "FALSE"} if k == "boolean" else None)
            else:
                cells.append(None)
        out_rows.append({"c": cells})
    return {"version": "0.6", "reqId": "0", "status": "ok", "table": {"cols": cols, "rows": out_rows}}


def empty_table():
    return {"version": "0.6", "reqId": "0", "status": "ok", "table": {"cols": [], "rows": []}}


def error_table(msg="탭이 없습니다"):
    return {"version": "0.6", "reqId": "0", "status": "error",
            "errors": [{"reason": "invalid_query", "message": "INVALID_QUERY", "detailed_message": msg}]}


# ---------- 읽기 ----------
def load_xlsx(path, only=None):
    """xlsx -> {탭이름: (rows, fmts)}. rows 는 값, fmts 는 칸 서식 글자. only 로 탭을 줄일 수 있다."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    tabs = {}
    for ws in wb.worksheets:
        if only and ws.title not in only: continue
        rows, fmts = [], []
        for row in ws.iter_rows():
            rows.append([c.value for c in row])
            fmts.append([c.number_format for c in row])
        tabs[ws.title] = (rows, fmts)
    return tabs


def parse_response_text(text):
    """실제 gviz 응답 글자(/*O_o*/ … setResponse({…});) -> dict"""
    i, j = text.index("("), text.rindex(")")
    return json.loads(text[i + 1:j])


def load_gviz_dir(path):
    """<탭이름>.txt(실제 gviz 응답을 그대로 저장한 것) 폴더 -> {탭이름: dict}"""
    import os
    out = {}
    for fn in os.listdir(path):
        if fn.endswith(".txt") and not fn.startswith("gid_"):
            with open(os.path.join(path, fn), encoding="utf-8") as f:
                out[fn[:-4]] = parse_response_text(f.read())
    return out


def render(resp, callback=None):
    """dict -> 응답 글자. callback 이 있으면 JSONP(responseHandler), 없으면 setResponse."""
    body = json.dumps(resp, ensure_ascii=False, separators=(",", ":"))
    fn = callback or "google.visualization.Query.setResponse"
    return f"{CB_PREFIX}{fn}({body});"
