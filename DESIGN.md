# squad.gg DESIGN.md

> One canonical design system for two surfaces — the op.gg-style stats **website** (`index.html`) and the Tkinter desktop **analyzer** (`squad_analyzer.py`, v81.53). The website already owns the identity; this document promotes its `:root` palette into a formal, named token system and teaches the desktop app to speak the same language.
> 웹사이트가 정체성의 원천이다(source of truth). 이 문서는 웹의 `:root` 팔레트를 정식 토큰 체계로 승격시키고, 데스크톱 앱이 동일한 토큰을 따르도록 만든다.

---

## 1. Overview — Visual Theme & Atmosphere / 비주얼 테마

squad.gg is a **dark-first, data-dense esports tracker**. The mood is a deep navy-charcoal command console: near-black surfaces stacked by elevation, hairline borders instead of heavy shadows, calm chrome so that **data pops** (win/lose, tiers, KDA). One scarce chromatic brand accent (periwinkle blue `#5b8cff`) plus a warm gold for honor/achievement. Team identity is blue vs red. Everything else is greyscale ink on stacked surfaces.

- **분위기**: 심해 네이비-차콜 콘솔. 표면은 깊이(elevation)로 쌓고, 그림자 대신 헤어라인 보더로 구분. 크롬(chrome)은 차분하게, 데이터(승패·티어·KDA)는 강하게.
- **Core principle — the dark canvas IS the whitespace.** Separate dense regions by *lifting* them onto the next surface tier, not by adding dividers/boxes. 어두운 캔버스 자체가 여백이다. 영역 구분은 선이 아니라 표면 승급으로.
- **Two surfaces, one token table.** Every value below has a CSS custom-property name AND a Tkinter Python constant name. Define once, consume in both. 하나의 토큰 표가 웹과 데스크톱을 함께 구동한다.
- **This is polish, not redesign.** Keep the existing look; remove the shadow palette (208 desktop literals, ~40 untokenized web hexes) by routing everything through roles.

---

## 2. Colors — Palette & Semantic Roles / 색상 팔레트

The **web `:root` values are canonical.** Desktop reconciles onto them. Each row: Role → CSS var → Tkinter constant → hex → usage. (Hex values are the real audited web tokens; the desktop's stray accents are *mapped onto* these roles in §2.4.)

### 2.1 Surface ladder (배경 표면 사다리)
Name by depth, not by color. Never use pure `#000000` as canvas — reserve black only for overlay/scrim.

| Role | CSS var | Tkinter const | Hex | Use |
|---|---|---|---|---|
| canvas (deepest app bg) | `--bg` | `BG` | `#11131a` | app/window background, header gradient bottom |
| surface-1 (recessed input) | `--bg2` | `BG_INPUT` | `#171a23` | inputs, track bases, badge wells, listbox |
| surface-2 (primary card) | `--card` | `BG_CARD` | `#1b1f2b` | cards, panels, modal bodies, ring inner |
| surface-3 (raised/active) | `--card2` | `BG_RAISED` | `#212636` | search box, suggest, hover rows, active chips |
| overlay scrim | `--scrim` | `SCRIM` | `#000000` @ ~55% | modal backdrops only |

> Desktop reconciliation: `#121315`→`--bg`, `#1a1c1f`→(new `--bar` = alias of `--card`, see note), `#161719`/`#191b22`/`#0f1115`→`--bg2`, `#1e2124`/`#1e2228`→`--card`. Collapse the near-black triplet to `--bg`.
> Note: the desktop's `#1a1c1f` bar sits *between* `--bg` and `--card`; keep it as a single **`--bar` / `BG_BAR` = `#171a23`** (reuse surface-1) so header bars read as recessed chrome.

### 2.2 Ink hierarchy (텍스트 잉크 4단계)
| Role | CSS var | Tkinter const | Hex | Use |
|---|---|---|---|---|
| ink (primary) | `--txt` | `TEXT` | `#e7eaf3` | player names, headings, numbers |
| ink-muted (secondary) | `--sub` | `TEXT_SUB` | `#9aa3b8` | labels, table `th`, sub-rows |
| ink-subtle (tertiary) | `--mut` | `TEXT_MUT` | `#717a91` | timestamps, hints, meta |
| ink-on-accent | `--on-accent` | `TEXT_ON` | `#0e1017` | text on gold/blue solid fills |

> Collapse the desktop's **ten+ greys** (`#a0a8b5`, `#8a93a0`, `#9aa3b8`, `#bdc3c7`, `#7f8c8d`, `#e6e9ee`, `#dfe4ee`, `#a9b3c2`, `#c2a9a9`) → `--sub` or `--mut`. `#ffffff` fg → `--txt` (`#e7eaf3`) except on solid accent fills, which use `--on-accent`.

### 2.3 Borders (헤어라인 보더 — depth carrier)
Depth on dark is carried by the surface ladder **plus 1px hairlines**, not drop shadows.

| Role | CSS var | Tkinter const | Hex | Use |
|---|---|---|---|---|
| hairline | `--line` | `LINE` | `#2a3042` | all card/row/table/input borders |
| hairline-strong | `--line-2` | `LINE_STRONG` | `#3a4056` | emphasis borders, focused card edge |

> Retire desktop parallel borders `#33405c`, `#2b3444`, `#8a94a8` → `--line` (or `--line-2` for emphasis). In Tkinter, render via `highlightbackground=LINE, highlightthickness=1, relief='flat', bd=0`.

### 2.4 Brand + semantic status (브랜드 + 시맨틱)
One scarce brand accent. Win/lose/tier are a **separate status set**, not UI accents.

| Role | CSS var | Tkinter const | Hex | Use |
|---|---|---|---|---|
| brand accent | `--accent` | `ACCENT` | `#5b8cff` | logo, primary CTA, focus ring, links, active tab |
| accent-hover | `--accent-h` | `ACCENT_H` | `#7ba0ff` | hover on brand controls |
| win / team-blue | `--win` (`--blue`) | `WIN` / `TEAM_BLUE` | `#3a73e8` | win result, blue team, wr fill |
| win-bg | `--blue-bg` | `TEAM_BLUE_BG` | `#16243f` | blue team header wash, win gradient |
| win-tint (text) | `--blue-tint` | `TEAM_BLUE_FG` | `#9cc0ff` | blue-team lineup/head text |
| lose / team-red | `--lose` (`--red`) | `LOSE` / `TEAM_RED` | `#e84057` | lose result, red team |
| lose-bg | `--red-bg` | `TEAM_RED_BG` | `#3a1c25` | red team header wash, lose gradient |
| lose-tint (text) | `--red-tint` | `TEAM_RED_FG` | `#ff9aa8` | red-team lineup/head text |
| gold (honor) | `--gold` | `GOLD` | `#e0a437` | Hall of Fame, MVP text, tier gold, titles |
| success | `--green` | `SUCCESS` | `#2bb177` | download, status OK, positive synergy |
| warn | `--warn` | `WARN` | `#e8930c` | pending/queue, caution (champ tier ct2) |
| info/cyan (ACE) | `--cyan` | `INFO` | `#39c7d6` | ACE badge, secondary highlight |
| purple (support) | `--purple` | `PURPLE` | `#8a5cd6` | 서폿 role, mythic-tier stop |

**Role colors** (탑/정글/미드/원딜/서폿) — promote out of JS `POS_COLOR` into `:root` and mirror in Tkinter:
`--pos-top #c9482f` · `--pos-jg #2f9d57` · `--pos-mid #3a73e8`(=`--win`) · `--pos-adc #d9a13a` · `--pos-sup #8a5cd6`(=`--purple`).

**Desktop stray-accent → role mapping (the parity fix):**
| Stray desktop hex | Was used for | Now maps to |
|---|---|---|
| `#1abc9c` teal | squad.gg buttons | `--accent` (brand) or `--green` if "go" |
| `#2c3e50`/`#2c374e` navy | settings/copy buttons | `--card2` bg + `--sub` fg (neutral) |
| `#b33939`/`#c0392b`/`#8c1c1c` reds | HOF / delete / multi | `--lose` (danger) |
| `#f39c12`/`#e67e22`/`#d35400`/`#b8641f` oranges | ad/op.gg/banpick/tourney | `--warn` (or `--gold` for honor) |
| `#7d5f99`/`#5e4677` purple | 내부티어 buttons | `--purple` |
| `#2980b9`/`#4a6984`/`#5dade2`/`#85c1e9` blues | various buttons/heads | `--win`/`--blue-tint` |
| `#4E6548` olive | close buttons | `--card2` neutral ghost |
| `#f1c40f`/`#ffd24a` yellows | MVP/title badges | `--gold` |
| `#ec7063`/`#ff4757` salmon/bright red | team titles/warnings | `--lose`/`--red-tint` |
| `#1f2633`/`#331f1f` team panels | blue/red panel bg | `--blue-bg`/`--red-bg` |

Result: **retire ~25 stray hexes**, converge on ~18 roles shared with web.

---

## 3. Typography — Hierarchy / 타이포그래피

- **Web font stack:** `"Pretendard","Apple SD Gothic Neo","Segoe UI",Roboto,sans-serif` (unchanged).
- **Desktop font:** `Malgun Gothic` (Windows Korean-safe) — the practical equivalent; one `Consolas` exception for the invite/numeric code entry.
- **Weights:** 400 body · 600 labels/tabs · 700 buttons/headings · 800 numbers/badges. Cap display at 700 (data UI, not marketing).
- **Numeric rule:** route KDA / CS / damage / rank columns through a **mono/tabular** treatment so digits align. Web: add `font-variant-numeric: tabular-nums`. Desktop: use `Consolas` for numeric table cells.

### Type scale (collapse the web's ~16 ad-hoc sizes + half-pixel steps to 8 tokens)
| Token | CSS var | Tkinter const | px / pt | Weight | Use |
|---|---|---|---|---|---|
| 2xs | `--fs-2xs` | `FS_2XS` | 11 | 600 | ad labels, dlver |
| xs | `--fs-xs` | `FS_XS` | 12 | 400/600 | badges, op-badge, meta |
| sm | `--fs-sm` | `FS_SM` | 13 | 400 | **workhorse** small (was 12.5/13.5) |
| base | `--fs-base` | `FS_BASE` | 15 / 11pt | 400 | body, table cells |
| md | `--fs-md` | `FS_MD` | 16 / 12pt | 700 | card `h2`, panel `h3` |
| lg | `--fs-lg` | `FS_LG` | 18 / 13pt | 700 | ring value, achievement, HOF row |
| xl | `--fs-xl` | `FS_XL` | 22 / 16pt | 800 | logo, profile name |
| 2xl | `--fs-2xl` | `FS_2XL` | 24 / 20pt | 800 | stat numbers, main title |

> **Kill the half-pixel steps** (11.5/12.5/13.5/14.5). Map each component's old size to the nearest token. Desktop: define `FONTS` dict once (`TITLE=(Malgun Gothic,20,'bold')`, `H1=(…,16,'bold')`, `H2=(…,13,'bold')`, `BODY=(…,11)`, `SMALL=(…,10)`, `NUM=('Consolas',11)`) and stop re-inlining tuples in modals (modal headers currently drift 14/15/16 → all become `H1`).

---

## 4. Layout & Spacing / 레이아웃 · 간격

**4px-base spacing scale** — shared numbers feed CSS px AND Tkinter `padx/pady/ipadx` for pixel parity.

| Token | CSS var | Tkinter const | px |
|---|---|---|---|
| xxs | `--sp-1` | `SP_1` | 4 |
| xs | `--sp-2` | `SP_2` | 8 |
| sm | `--sp-3` | `SP_3` | 12 |
| md | `--sp-4` | `SP_4` | 16 |
| lg | `--sp-6` | `SP_6` | 24 |
| xl | `--sp-8` | `SP_8` | 32 |

> Refactor the web's ad-hoc paddings (`7 9 11 13 18 22`) and desktop's per-widget `padx/pady` onto these. Odd values round to nearest step.

**Web layout:** ~1280–1400px max container; 3-column dashboard (`.home3`) → 2-up → 1-up. Fixed ad rails collapse first on narrow viewports.
**Desktop window sizing:** DPI-aware (`SetProcessDpiAwareness(1)`, already present). Main board is fixed-ish; modals (`Toplevel`) should use consistent `SP_4` outer padding and `SP_3` between rows. Header bar height driven by `H1` + `SP_3` vertical padding.

**Separation by lift, not lines:** nested stat panels sit on `--card` inside a `--bg` region; expanded/hover rows lift to `--card2`. Reserve explicit `--line` dividers for tables.

---

## 5. Elevation & Depth / 깊이 · 그림자

Dark mode: **hairline + surface lift first, shadows sparingly.**

| Level | Meaning | Web treatment | Tkinter treatment |
|---|---|---|---|
| E0 | flat inline | no border | plain frame |
| E1 | card/panel | `--card` + 1px `--line` | `bg=BG_CARD` + `highlightbackground=LINE, highlightthickness=1` ✅ |
| E2 | hover/active row | lift to `--card2` + 1px `--line` | `bg=BG_RAISED` (via bind) ✅ |
| E3 | dropdown/suggest | `--card2` + `--line-2` + `--sh-2` | `bg=BG_RAISED`, no shadow ⚠️ |
| E4 | modal/store card | `--card` + `--sh-3` + inset hairline | flat + `--line-2` border only ⚠️ |
| focus | keyboard focus | `0 0 0 2px var(--accent)` @ ~50% | `highlightcolor=ACCENT, highlightthickness=2` (partial) ⚠️ |

**Shadow scale (web only):**
- `--sh-1` `0 1px 2px #00000040` — resting cards
- `--sh-2` `0 4px 12px -2px #00000059` — dropdowns, hover lift
- `--sh-3` `0 12px 28px -6px #00000073` — store promo cards, modals

> ⚠️ **Tkinter cannot render `box-shadow`, gradients, blur, or rounded corners on native widgets.** E3/E4 shadows and all radii degrade to **flat rectangles with hairline borders**. This is expected and documented — do not attempt to fake shadows on classic `tk` widgets. (Rounded corners require Canvas-drawn or pre-rendered 9-slice PNGs; treat radius as web-only unless a card is important enough to warrant a PNG.)

---

## 6. Shapes — Radius / 모서리 반경 (web-only token)

Collapse the web's 2–20px ad-hoc radii to 4 tokens. Data-dense = stay tight.

| Token | CSS var | px | Use |
|---|---|---|---|
| sm | `--r-sm` | 6 | badges, chips, inputs, small marks |
| md | `--r-md` | 8 | cards inner, buttons, tabs |
| lg | `--r-lg` | 12 | containers, panels, match cards |
| pill | `--r-pill` | 999 | fully-round chips, ring, achievement pills |

> Tkinter: radius is **not applicable** to native widgets — omit. Document as web-only.

---

## 7. Components / 컴포넌트 규칙 (both surfaces)

**Buttons**
- *Primary CTA*: `--accent` bg, `--on-accent` text, hover `--accent-h`. Desktop: `bg=ACCENT, fg=TEXT_ON, activebackground=ACCENT_H`.
- *Ghost/neutral*: `--card2` bg, `--sub` text, 1px `--line`, hover `--card2`→lighter/`--line-2` border. Desktop: `bg=BG_RAISED, fg=TEXT_SUB, activebackground=BG_CARD`.
- *Gold/honor* (HOF, MVP): `--gold` bg, `--on-accent` text. *Success/go*: `--green`. *Danger* (delete): `--lose` bg, `--txt`, `activebackground` darker.
- **Every button gets an `activebackground`** (desktop currently: only 3 of ~9 do). Route all through a factory (§desktop_migration).

**Cards / panels** — E1: surface-2 + hairline. Header row uses `--md`/`H1`, body `--base`/`BODY`. Hover interactive cards → E2.

**Badges** — MVP: `--gold` text on `#3a2f12`-tint bg (tokenize as `--gold-bg`). ACE: `--cyan` on `#0e2b33` (`--cyan-bg`). 역적/bad: `--lose` on `--red-bg`. Radius `--r-sm`, size `--fs-xs`, weight 800. Desktop: same colors, flat rect.

**Tiers** — t0 mythic gradient `--purple`→pink (web only; desktop = solid `--purple`), t1 `--lose`, t2 `--win`, t3 `--gold`. Champ-tier ramp ct1–ct5 → `--lose`/`--warn`/`--info`/`--sub`/`--mut`.

**Tables / rows** — `th` = `--sub` `--fs-sm`; cells `--txt` `--fs-base`; numeric cells tabular/`Consolas`. Row hover → `--card2` (E2). Border `--line`.

**Inputs** — `--bg2` bg, `--txt` text, 1px `--line`, focus → `--accent` border + focus ring. Desktop: `bg=BG_INPUT, fg=TEXT, insertbackground=TEXT, highlightbackground=LINE, highlightcolor=ACCENT`.

**Modal windows** (desktop `Toplevel` ×6) — `configure(bg=BG)`, top bar `bg=BG_BAR`, title `GOLD`/`H1`, body cards E1, close button = ghost/neutral (not olive). Consistent `SP_4` padding. Web modals/dropdowns get `--sh-2/-3`.

**Team panels** — blue: `--blue-bg` header, `--blue-tint` text; red: `--red-bg` header, `--red-tint` text. Identical on both surfaces.

---

## 8. Do's and Don'ts / 가이드레일

**Do**
- ✅ Reserve `--accent`/`ACCENT` (#5b8cff) for brand mark, primary CTA, focus ring, links — nothing else.
- ✅ Carry depth with the surface ladder + 1px `--line` hairlines. 표면 승급 + 헤어라인으로 깊이 표현.
- ✅ Route every color through a role token; both surfaces read from one table.
- ✅ Give every interactive control a visible focus ring (web `:focus-visible`; desktop `highlightcolor=ACCENT`).
- ✅ Set all numeric columns in tabular/mono so digits align.
- ✅ Keep win=`--win`, lose=`--lose` end-to-end (fix stray `#c84057`, `#ec7063`, `#ff4757`).

**Don't**
- ❌ Don't use pure `#000000` as canvas — anchor on `--bg` #11131a; black is scrim-only.
- ❌ Don't introduce a second chromatic brand accent, and don't reintroduce the flat-UI/Bootstrap palette (teal `#1abc9c`, navy `#2c3e50`, orange `#f39c12`, purple `#7d5f99`) — map them to roles.
- ❌ Don't re-type a token's hex as a literal (web: `#5b8cff`/`#3a73e8`/`#e84057` inline; desktop: 208 literals). Use `var()` / the COLORS dict.
- ❌ Don't spawn a new grey/gold — there is ONE `--sub`, ONE `--mut`, ONE `--gold`.
- ❌ Don't fake shadows/gradients/rounded corners on native Tkinter widgets — accept flat + hairline.
- ❌ Don't re-inline font tuples in modals — use the FONTS dict.

---

## 9. Responsive & Window Behavior / 반응형

- **Web:** ~1400px max; 3-up dashboard → 2-up (tablet) → 1-up (mobile). Fixed ad rails hide first. Tables scroll inside `overflow-x:auto`; body never scrolls horizontally.
- **Desktop:** DPI-aware; main board fixed layout, modals size to content with `SP_4` padding. No fluid breakpoints (native app) — but font/spacing tokens keep proportions consistent across DPI.

---

## 10. Agent Prompt Guide / 에이전트 작업 지침

When editing either surface, work like this:
1. **Pick the surface tier first.** Decide whether a region lives on `--bg`, `--card`, or `--card2` before styling anything.
2. **One component at a time**, and **always cite tokens by name** ("`--card` + 1px `--line`", never a raw hex).
3. **Default body to weight 400**; treat `--accent` as scarce; keep win/lose/tier as status, not accent.
4. **Never invent a color** — if you need one, it already exists as a role; find it in §2. If it truly doesn't, add ONE new role to the token table, not an inline literal.
5. **Web and desktop must stay in sync** — a color change edits the shared token table, then both `:root` (CSS) and `theme.py` (Python) pick it up.
6. **Copy-paste starter:** *"Restyle `<component>` in `<index.html | squad_analyzer.py>`. Use only tokens from DESIGN.md §2–6. Surface tier: `<--bg|--card|--card2>`. Buttons via the button factory / button role classes. Add focus ring. Do not introduce new hex literals."*
