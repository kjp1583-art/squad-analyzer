#!/usr/bin/env python3
"""🐤 P-6 클랜원 캐릭터 그림 뽑기 — 기본 브장신 + 시그니처 소품(이미지 편집 API).

기획: tooling/improve/ideas/P-6-brj-survivors.md 「클랜원 캐릭터 그림 — 방식 2」
원리: 기본 몸(img/brjang/parts/body/front.png)을 참조로 **편집** 요청 → 원본 병아리는 그대로, 소품만 더한 전신 PNG.
      새로 그리게 하면 얼굴·비율이 매번 달라져 brj_part.extract_layer 로 파츠화할 수 없다.

  python3 tooling/p6_chars.py gen   --out p6_gen [--only jjg,mms] [--n 2] [--model gpt-image-2]
  python3 tooling/p6_chars.py check --out p6_gen            # 실루엣·투명 배경 리포트 + sheet.png(후보 한 장에 모아 보기)
  python3 tooling/p6_chars.py gen --dry                      # 요청 내용만 출력(네트워크 없음)

키: 환경변수 OPENAI_API_KEY (또는 openai_api). 코드·저장소·채팅에 키를 넣지 않는다.
표준 라이브러리 + Pillow 만 쓴다(봇 호스트와 같은 조건).
"""
import os, sys, io, json, time, base64, argparse, uuid, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "img", "brjang", "parts", "body", "front.png")
API = "https://api.openai.com/v1/images/edits"
_REJECTED = set()            # 모델이 한 번 거절한 선택 파라미터 — 다음 캐릭터부터는 처음부터 뺀다

COMMON = (
    'This is an EDIT of the attached image, not a new drawing. The attached image is "Brjangsin", a chubby '
    "pastel-yellow chick mascot: big round head, tiny dark eyes with short straight brows, small orange beak, pink "
    "cheek blush, stubby wings as arms, orange feet. Flat cel-shaded sticker style, uniform thick dark-navy outline, "
    "two-tone shading, no texture.\n"
    "Keep the character EXACTLY as it is: same pose, same camera, same size and same position on the 1024x1024 "
    "canvas, same line weight, same palette, same face unless the item text says otherwise. Change nothing except "
    "adding what the item text describes. Draw the item in the same sticker style (dark-navy outline, flat two-tone "
    "shading), attached naturally (held in a wing or worn), never floating at random, and never covering the eyes.\n"
    "Output: straight front view, full body, one character, fully transparent background (no floor, no shadow, "
    "no scenery, no frame), no text or letters unless the item text asks for them.\n"
)

# 키는 lab/P-6.html CHARS 의 k 와 같다. 소품 출처는 봇 BRJ_GEAR·BRJ_CAMEOS(기획서 표)
CHARS = [
    ("jjg", "집중겜", "치속크라켄",
     "ITEM: the wing on the viewer's RIGHT side grips a short fantasy sword whose blade is a curling teal-blue kraken "
     "tentacle with a row of small cream suction cups along one edge, with a small gold crossguard and grip. The blade "
     "points up and outward diagonally beside the head. Keep the calm, focused deadpan face."),
    ("mms", "망무새", "난 망했어",
     "ITEM: change only the expression to teary and gloomy — glossy eyes with one small light-blue tear drop under "
     "each eye, brows tilted into a worried slant (inner ends raised); beak, blush and head shape unchanged. Plus a "
     "small dark-grey storm cloud with three or four falling light-blue raindrops floating just above the top of the "
     "head (close to the head, not covering it)."),
    ("hrb", "조선제일하리보", "다대포 서핑보드",
     "ITEM: a tall sky-blue surfboard with one white stripe down its center and a small orange fin, standing upright "
     "and tucked under the wing on the viewer's LEFT side; its bottom rests beside the feet and its top reaches about "
     "eye height. The face and belly stay fully visible."),
    ("kcj", "칼챔중증환자", "방패의 미학",
     "ITEM: a large kite-shaped knight shield (steel-grey rim, deep-blue face, simple gold cross emblem) held in the "
     "wing on the viewer's LEFT side, covering only the left edge of the body from shoulder to feet; the face and "
     "the rest of the body stay visible."),
    ("amd", "앙앵모르딱", "팀원과싸우지말자",
     "ITEM: a protest picket sign — a white rectangular board on a light-wood stick, held upright in the wing on the "
     "viewer's RIGHT side, the board raised beside the head. On the board, bold black hand-lettered Korean text in "
     "two lines: first line 팀원과 , second line 싸우지말자 . Spell the Korean exactly; no other text."),
    ("ildj", "일단즐겨", "재물획득의 비약",
     "ITEM: a round-bottomed glass potion flask with a cork stopper, filled with glowing golden liquid and a few tiny "
     "sparkles, held up in the wing on the viewer's RIGHT side at chest height. Keep the deadpan face."),
    ("kyo", "김야옹", "버거킹 쿠폰 · 고양이 귀",
     "ITEM: two small triangular cat ears on top of the head (same pastel yellow as the head, pink inner ear, same "
     "navy outline), and a cheeseburger (sesame bun, lettuce, cheese, beef patty) held in the wing on the viewer's "
     "RIGHT side at belly height."),
    ("ddmj", "단단묵직", "디펜더",
     "ITEM: a rounded steel knight helmet sitting on top of the head with its rim just above the brows (brows and "
     "eyes fully visible), and a rectangular shield made of red bricks with grey mortar lines held in the wing on "
     "the viewer's LEFT side, covering only the left edge of the body."),
]


def _key():
    k = os.environ.get("OPENAI_API_KEY") or os.environ.get("openai_api")
    if not k: sys.exit("OPENAI_API_KEY(또는 openai_api) 환경변수가 없어요 — 작업 환경 설정에 넣어 주세요.")
    return k


def _multipart(fields, files):
    b = "----p6" + uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fn, data, ctype) in files:
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {ctype}\r\n\r\n'.encode())
        out.write(data); out.write(b"\r\n")
    out.write(f"--{b}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={b}"


def edit(prompt, base_png, model, n, quality, fidelity=True, timeout=300):
    """이미지 편집 요청 → PNG bytes 목록. 모델이 모르는 선택 파라미터(400 · error.param)는 빼고 한 번 더."""
    fields = {"model": model, "prompt": prompt, "n": str(n), "size": "1024x1024", "quality": quality,
              "background": "transparent", "output_format": "png"}
    if fidelity: fields["input_fidelity"] = "high"
    for p in _REJECTED: fields.pop(p, None)
    for _ in range(4):
        body, ctype = _multipart(fields, [("image[]", ("front.png", base_png, "image/png"))])
        req = urllib.request.Request(API, data=body, method="POST",
                                     headers={"Authorization": f"Bearer {_key()}", "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: d = json.load(r)
            return [base64.b64decode(x["b64_json"]) for x in d.get("data", []) if x.get("b64_json")]
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            try: err = json.loads(txt).get("error") or {}
            except ValueError: err = {}
            p = err.get("param") or ""
            p = p[:-2] if p.endswith("[]") else p
            if e.code == 400 and p in fields and p in ("input_fidelity", "background", "output_format", "quality"):
                print(f"  · {model} 가 '{p}' 를 안 받아서 빼고 다시", flush=True); fields.pop(p); _REJECTED.add(p); continue
            if e.code in (429, 500, 502, 503): print(f"  · {e.code} — 20초 뒤 다시", flush=True); time.sleep(20); continue
            raise SystemExit(f"API {e.code}: {err.get('message') or txt[:400]}")
    raise SystemExit("재시도 초과")


def cmd_gen(a):
    with open(BASE, "rb") as f: base = f.read()
    only = set(filter(None, (a.only or "").split(",")))
    os.makedirs(a.out, exist_ok=True)
    for k, nm, prop, item in CHARS:
        if only and k not in only: continue
        prompt = COMMON + "\n" + item
        if a.dry: print(f"== {k} {nm} ({prop})\n{prompt}\n"); continue
        print(f"🎨 {k} {nm} — {prop} × {a.n}", flush=True)
        pngs = edit(prompt, base, a.model, a.n, a.quality, fidelity=not a.no_fidelity)
        start = len([x for x in os.listdir(a.out) if x.startswith(k + "_") and x.endswith(".png")])
        for i, png in enumerate(pngs):
            p = os.path.join(a.out, f"{k}_{start + i + 1}.png")
            with open(p, "wb") as f: f.write(png)
            print("  →", p, flush=True)
        with open(os.path.join(a.out, "prompts.json"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": k, "model": a.model, "prompt": prompt}, ensure_ascii=False) + "\n")


def _report(png_bytes, base_bytes):
    """brj_part.extract_layer(장신구 슬롯) 리포트 + 투명 배경 여부."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from brj_part import extract_layer
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    a = im.getchannel("A"); w, h = im.size
    corners = [a.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    clear = a.point(lambda v: 255 if v < 16 else 0).histogram()[255] / (w * h)
    layer, rep = extract_layer(png_bytes, base_bytes, "a")
    rep["transparent_bg"] = max(corners) < 16 and clear > 0.3
    rep["clear_ratio"] = round(clear, 3)
    if not rep["transparent_bg"]: rep["warn"].append("배경이 투명하지 않음 — 키잉으로 처리됐지만 테두리 확인 필요")
    return layer, rep


def cmd_check(a):
    from PIL import Image, ImageDraw, ImageFont
    with open(BASE, "rb") as f: base = f.read()
    names = {k: (nm, prop) for k, nm, prop, _ in CHARS}
    files = sorted(x for x in os.listdir(a.out) if x.endswith(".png") and x.split("_")[0] in names and not x.endswith("_layer.png"))
    reps = {}
    for fn in files:
        with open(os.path.join(a.out, fn), "rb") as f: g = f.read()
        layer, rep = _report(g, base)
        with open(os.path.join(a.out, fn[:-4] + "_layer.png"), "wb") as f: f.write(layer)
        reps[fn] = rep
        print(f"{fn:14s} cover {rep['cover']:.3f} iou {rep['iou']:.3f} area {rep['area']:.3f} 투명 {'O' if rep['transparent_bg'] else 'X'}"
              + ("  ⚠ " + " / ".join(rep["warn"]) if rep["warn"] else ""))
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f: json.dump(reps, f, ensure_ascii=False, indent=1)
    # 한 장에 모아 보기 — 체커보드 위(투명 확인용), 맨 앞은 기본 몸
    cells = [("base", "기본 브장신", Image.open(BASE).convert("RGBA"))] + \
            [(fn, f"{names[fn.split('_')[0]][0]} · {fn[:-4]}", Image.open(os.path.join(a.out, fn)).convert("RGBA")) for fn in files]
    S, cols = 256, min(6, max(1, len(cells)))
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * S, rows * (S + 28)), "#ffffff")
    chk = Image.new("RGB", (S, S), "#ffffff"); d = ImageDraw.Draw(chk)
    for y in range(0, S, 16):
        for x in range(0, S, 16):
            if (x // 16 + y // 16) % 2: d.rectangle([x, y, x + 15, y + 15], fill="#e6e6e6")
    font = None
    for fp in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
               "C:/Windows/Fonts/malgun.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc"):
        try: font = ImageFont.truetype(fp, 15); break
        except OSError: pass
    font = font or ImageFont.load_default()
    dr = ImageDraw.Draw(sheet)
    for i, (fn, label, im) in enumerate(cells):
        x, y = (i % cols) * S, (i // cols) * (S + 28)
        sheet.paste(chk, (x, y)); sheet.paste(im.resize((S, S), Image.LANCZOS), (x, y), im.resize((S, S), Image.LANCZOS))
        r = reps.get(fn)
        tag = "" if not r else f" · {r['cover']:.2f}" + (" (!)" if r["warn"] else "")
        dr.text((x + 6, y + S + 5), label + tag, fill="#222222", font=font)
    sp = os.path.join(a.out, "sheet.png"); sheet.save(sp); print("📋", sp)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen"); g.add_argument("--out", default="p6_gen"); g.add_argument("--only"); g.add_argument("--n", type=int, default=2)
    g.add_argument("--model", default="gpt-image-2"); g.add_argument("--quality", default="high")
    g.add_argument("--no-fidelity", action="store_true", help="input_fidelity=high 를 보내지 않는다"); g.add_argument("--dry", action="store_true")
    c = sub.add_parser("check"); c.add_argument("--out", default="p6_gen")
    a = ap.parse_args()
    {"gen": cmd_gen, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
