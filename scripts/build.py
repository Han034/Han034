"""Builds the profile README cards in assets/ from the calm-ui tokens.

SVG text never wraps on its own, so every line is measured and wrapped here.
Run: python scripts/build.py  (writes <name>.svg for dark and <name>-light.svg for light)
"""
import pathlib
import re
import urllib.request
from html import escape

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets"
W = 840          # card width; README scales it to 100%
PAD = 32         # --s-8
INNER = W - 2 * PAD
FONT = "Inter, 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"

def oklch(l, c, h):
    """oklch -> (r, g, b) 0-255, clipped to sRGB."""
    import math
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_, m_, s_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3, (l - 0.1055613458 * a - 0.0638541728 * b) ** 3, (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    enc = lambda x: 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return tuple(round(min(1, max(0, enc(x))) * 255) for x in lin)

def hx(rgb):
    return "#%02x%02x%02x" % rgb

def rgba(rgb, a):
    return "rgba(%d,%d,%d,%s)" % (*rgb, a)

# calm-ui tint, kept light: every surface and the ink share one hue family (the brand violet)
# at low chroma. The card sits one tone above GitHub's own page, which plays --c-page here.
HUE = 285
_ink_d, _ink_l = oklch(0.97, 0.01, HUE), oklch(0.2, 0.025, HUE)
THEMES = {
    "": {  # dark
        "card": hx(oklch(0.215, 0.022, HUE)), "raised": hx(oklch(0.285, 0.032, HUE)), "sunken": hx(oklch(0.17, 0.018, HUE)),
        "line": rgba(_ink_d, .07),
        "ink": hx(_ink_d), "ink2": rgba(_ink_d, .62), "ink3": rgba(_ink_d, .38),
        "accent": hx(_ink_d), "on_accent": hx(oklch(0.2, 0.03, HUE)),
        "pos": "#3ddc84", "brand": "#7b61ff", "pos_rgb": (61, 220, 132), "empty_rgb": oklch(0.275, 0.028, HUE), "wave": "#c9f7da",
    },
    "-light": {
        "card": hx(oklch(0.965, 0.012, HUE)), "raised": hx(oklch(0.995, 0.004, HUE)), "sunken": hx(oklch(0.91, 0.016, HUE)),
        "line": rgba(_ink_l, .08),
        "ink": hx(_ink_l), "ink2": rgba(_ink_l, .62), "ink3": rgba(_ink_l, .4),
        "accent": hx(_ink_l), "on_accent": hx(oklch(0.985, 0.006, HUE)),
        "pos": "#13a45b", "brand": "#7b61ff", "pos_rgb": (19, 164, 91), "empty_rgb": oklch(0.915, 0.016, HUE), "wave": "#0b7a42",
    },
}

# ---------- text measuring (Inter / SF / Segoe are close enough; widths are kept generous) ----------
def _cw(c):
    if c in "ijlI.,:;|!'`": return 0.27
    if c in "frt()[]/-": return 0.36
    if c == " ": return 0.28
    if c in "mwMW": return 0.86
    if c in "·•": return 0.34
    if c.isdigit(): return 0.58
    if c.isupper(): return 0.68
    return 0.55

def text_w(s, size, weight=400, tracking=0.0):
    k = 1.07 if weight >= 600 else 1.0
    return sum(_cw(c) for c in s) * size * k + tracking * len(s)

def wrap(words, size, width, weight=400):
    """words: list of (word, bold). Returns list of lines, each a list of (word, bold)."""
    lines, cur, cur_w = [], [], 0.0
    for w, b in words:
        ww = text_w(w, size, 600 if b else weight)
        sp = text_w(" ", size) if cur else 0
        if cur and cur_w + sp + ww > width:
            lines.append(cur); cur, cur_w = [], 0.0; sp = 0
        cur.append((w, b)); cur_w += sp + ww
    if cur: lines.append(cur)
    return lines

def rich(s):
    """'plain **bold** plain' -> [(word, bold)]"""
    out, prev = [], " "
    for i, part in enumerate(s.split("**")):
        bold = i % 2 == 1
        words = part.split()
        if out and words and not part[0].isspace() and not prev[-1:].isspace():   # "**Microsoft**," keeps the comma attached
            out[-1] = (out[-1][0] + words.pop(0), out[-1][1])
        out += [(w, bold) for w in words]
        prev = part
    return out

def t(x, y, s, size, fill, weight=400, anchor="start", tracking=None, upper=False):
    ls = f' letter-spacing="{tracking}"' if tracking is not None else ""
    s = s.upper() if upper else s
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{ls}>{escape(s)}</text>')

def rich_line(x, y, line, size, fill, bold_fill):
    spans, first = [], True
    for w, b in line:
        sep = "" if first else " "
        first = False
        if b: spans.append(f'<tspan fill="{bold_fill}" font-weight="600">{escape(sep + w)}</tspan>')
        else: spans.append(escape(sep + w))
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" fill="{fill}" '
            f'xml:space="preserve">{"".join(spans)}</text>')

def chip(x, y, label, c, h=26, size=11.5, fill=None, ink=None):
    w = text_w(label, size, 600) + 22
    s = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="{fill or c["raised"]}"/>'
         + t(x + w / 2, y + h / 2 + size * 0.36, label, size, ink or c["ink"], 600, "middle"))
    return s, w

def chips_flow(x, y, labels, width, c, gap=6, row_gap=8, h=26):
    out, cx, cy = [], x, y
    for lab in labels:
        w = text_w(lab, 11.5, 600) + 22
        if cx > x and cx + w > x + width:
            cx, cy = x, cy + h + row_gap
        s, w = chip(cx, cy, lab, c, h)
        out.append(s); cx += w + gap
    return "".join(out), cy + h - y

def svg(h, body, c, w=W, title=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img">'
            f'<title>{escape(title)}</title>'
            f'<rect width="{w}" height="{h}" rx="24" fill="{c["card"]}"/>{body}</svg>\n')

def section_head(y, label, title, c):
    """cu-label + cu-title. Returns svg, next y."""
    return (t(PAD, y + 10, label, 10.5, c["ink3"], 600, tracking=0.84, upper=True)
            + t(PAD, y + 40, title, 22, c["ink"], 700, tracking=-0.33)), y + 58

# ---------- icons (calm-ui: 24 grid, 2px stroke, round caps) ----------
def icon(kind, x, y, color, s=16):
    k = s / 24
    g = f'<g transform="translate({x},{y}) scale({k})" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    paths = {
        "mail": '<path d="M4 6h16v12H4zM4 7l8 6 8-6"/>',
        "arrow": '<path d="M7 17 17 7M9 7h8v8"/>',
        "in": '<rect x="3.5" y="3.5" width="17" height="17" rx="4"/><path d="M8 10.5V16M8 7.6v.01M12 16v-3.2c0-1.5 1-2.4 2.2-2.4s2 .9 2 2.4V16M12 10.5V16"/>',
        "gh": '<path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
    }
    return g + paths[kind] + "</g>"

# ---------- cards ----------
def header(c):
    b = []
    # cu-live
    live = "Available for ventures & advisory"
    lw = text_w(live, 11.5, 600) + 31
    b.append(f'<rect x="{PAD}" y="{PAD}" width="{lw:.1f}" height="24" rx="12" fill="{c["raised"]}"/>')
    b.append(f'<circle cx="{PAD + 12}" cy="{PAD + 12}" r="3" fill="{c["pos"]}">'
             '<animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    b.append(t(PAD + 22, PAD + 16.2, live, 11.5, c["ink2"], 600))
    # name + role
    b.append(t(PAD, 118, "Mehmet Emin Becek", 44, c["ink"], 700, tracking=-1.5))
    b.append(t(PAD, 148, "Full-Stack Software Engineer · AI Systems Architect", 15, c["ink2"]))
    row, _ = chips_flow(PAD, 174, ["Co-Founder, Force Studio", "Ex-Microsoft", "Computer Engineer"], INNER, c)
    b.append(row)
    return svg(174 + 26 + PAD, "".join(b), c, title="Mehmet Emin Becek — Full-Stack Software Engineer & AI Systems Architect")

def button(kind, label, primary, c):
    size, h = 13.5, 36
    tw = text_w(label, size, 600)
    w = 16 + 16 + 8 + tw + 8 + 14 + 16
    bg, fg = (c["accent"], c["on_accent"]) if primary else (c["raised"], c["ink"])
    arrow = c["on_accent"] if primary else c["ink3"]
    b = (f'<rect width="{w:.1f}" height="{h}" rx="18" fill="{bg}"/>'
         + icon(kind, 16, 10, fg)
         + t(40, 22.6, label, size, fg, 600)
         + icon("arrow", 40 + tw + 8, 11, arrow, 14))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h}" viewBox="0 0 {w:.1f} {h}" fill="none" role="img">'
            f'<title>{escape(label)}</title>{b}</svg>\n')

USER = "Han034"

def fetch_contributions():
    """GitHub's public contribution calendar -> (levels[row][col], total). None when offline."""
    try:
        req = urllib.request.Request(f"https://github.com/users/{USER}/contributions", headers={"User-Agent": "profile-build"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
    except OSError:
        return None
    cells = re.findall(r'id="contribution-day-component-(\d)-(\d+)" data-level="(\d)"', html)
    total = re.search(r"([\d,]+)\s+contributions?\s+in the last year", html)
    if not cells:
        return None
    cols = max(int(c) for _, c, _ in cells) + 1
    grid = [[None] * cols for _ in range(7)]
    for r, c, lv in cells:
        grid[int(r)][int(c)] = int(lv)
    return grid, (total.group(1) if total else "")

def mix(a, b, k):
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * k) for i in range(3))

# the wave: each cell lights up as a pulse passes through it, column by column,
# with a short trail behind the head. Busier days glow brighter.
WAVE_PEAKS = [0.22, 0.5, 0.65, 0.8, 0.95]
WAVE_CSS = "".join(
    f"@keyframes f{i}{{0%{{opacity:0}}3%{{opacity:{p}}}16%{{opacity:0}}100%{{opacity:0}}}}.w{i}{{animation:f{i} 7s linear infinite both}}"
    for i, p in enumerate(WAVE_PEAKS)
) + "@media (prefers-reduced-motion:reduce){[class^=w]{animation:none}}"

def activity(c, data):
    grid, total = data
    cols, gap = len(grid[0]), 3
    cell = (INNER - (cols - 1) * gap) / cols
    levels = [mix(c["empty_rgb"], c["pos_rgb"], k) for k in (0, 0.3, 0.5, 0.75, 1)]   # GitHub's five levels
    b = [f"<style>{WAVE_CSS}</style>",
         t(PAD, PAD + 10, "Contributions", 10.5, c["ink3"], 600, tracking=0.84, upper=True)]
    if total:
        b.append(t(W - PAD, PAD + 10, f"{total} in the last year", 12, c["ink2"], 500, "end"))
    top = PAD + 30
    base, wave = [], []
    for col in range(cols):
        for r in range(7):
            lv = grid[r][col]
            if lv is None:           # days after today
                continue
            x, y = PAD + col * (cell + gap), top + r * (cell + gap)
            geo = f'x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="3"'
            base.append(f'<rect {geo} fill="{levels[lv]}"/>')
            delay = col * 0.08 + r * 0.035
            wave.append(f'<rect {geo} class="w{lv}" opacity="0" style="animation-delay:{delay:.3f}s"/>')
    b += base
    b.append(f'<g fill="{c["wave"]}">{"".join(wave)}</g>')
    h = top + 7 * (cell + gap) - gap + PAD
    return svg(round(h), "".join(b), c, title="Contributions")

OVERVIEW = [
    "Computer Engineer combining deep full-stack engineering with venture architecture.",
    "Delivered scalable systems at **Microsoft** (.NET, Azure AI, microservices) and fintech platforms at **ParamTech**. "
    "Currently co-founding **Force Studio**, building autonomous AI agent workflows and interactive 3D web systems.",
]
FOCUS = ["Autonomous AI agents", "Distributed .NET systems", "Spatial & 3D web", "Venture advisory"]

def overview(c):
    b, y = section_head(PAD, "Overview", "Systems engineering & venture architecture", c)
    b = [b]
    for para in OVERVIEW:
        for line in wrap(rich(para), 14, INNER):
            y += 22
            b.append(rich_line(PAD, y, line, 14, c["ink2"], c["ink"]))
        y += 8
    y += 12
    row, hh = chips_flow(PAD, y, FOCUS, INNER, c)
    b.append(row)
    return svg(y + hh + PAD, "".join(b), c, title="Overview")

TOOLKIT = [
    ("Backend & Cloud", ["C#", ".NET 9", "ASP.NET Core", "Node.js", "Python", "Microsoft Azure", "Docker"]),
    ("Data & Messaging", ["PostgreSQL", "Redis", "RabbitMQ", "Apache Kafka", "Elasticsearch"]),
    ("Frontend & 3D", ["React", "Next.js", "TypeScript", "Tailwind CSS", "Three.js", "Babylon.js", "Electron"]),
    ("AI & Automation", ["Autonomous agents", "n8n", "Azure AI", "ML.NET", "LLM integrations", "CI/CD"]),
]

def toolkit(c):
    head, y = section_head(PAD, "Toolkit", "Core technologies", c)
    b = [head]
    y += 6
    label_w = 150
    for i, (label, items) in enumerate(TOOLKIT):
        y += 14
        if i: b.append(f'<line x1="{PAD}" y1="{y - 14}" x2="{W - PAD}" y2="{y - 14}" stroke="{c["line"]}"/>')
        row, hh = chips_flow(PAD + label_w, y, items, INNER - label_w, c)
        b.append(t(PAD, y + 17, label, 10.5, c["ink3"], 600, tracking=0.84, upper=True))
        b.append(row)
        y += hh
    return svg(y + PAD, "".join(b), c, title="Toolkit")

VENTURES = [
    ("Fagency", "Autonomous agency OS", "Uçtan uca ajans süreçlerini otonomlaştıran yapay zeka operasyon platformu.", "AI Agents · n8n · Next.js"),
    ("KariyerAI", "AI career intelligence", "İş arayanlar için ücretsiz CV analizi ve mülakat optimizasyon platformu.", "LLMs · React · FastAPI"),
    ("VidAI", "Automated video production", "Senaryodan montaja yapay zeka destekli video üretim hattı.", "AI/ML · Python · Azure"),
    ("Screen Pet", "Spatial desktop companion", "Kullanıcı ile masaüstünde etkileşime geçen interaktif sanal asistan.", "Electron · Three.js"),
    ("LFG", "Gamer matchmaking", "Oyuncuların seviye ve tarzlarına göre takım kurduğu mobil ekosistem.", "React Native · WebSockets"),
]

def ventures(c):
    head, y = section_head(PAD, "Ventures", "Selected products", c)
    b = [head]
    y += 6
    tag_w = 190
    text_x = PAD + 32 + 14
    text_wd = INNER - 46 - tag_w - 16
    for i, (name, tagline, desc, tags) in enumerate(VENTURES):
        y += 14
        if i: b.append(f'<line x1="{PAD}" y1="{y - 14}" x2="{W - PAD}" y2="{y - 14}" stroke="{c["line"]}"/>')
        b.append(f'<circle cx="{PAD + 16}" cy="{y + 16}" r="16" fill="{c["raised"]}"/>')
        b.append(t(PAD + 16, y + 20.5, name[0], 13, c["ink2"], 700, "middle"))
        b.append(f'<text x="{text_x}" y="{y + 12:.1f}" font-family="{FONT}" font-size="13.5" font-weight="600" fill="{c["ink"]}">'
                 f'{escape(name)}<tspan fill="{c["ink3"]}" font-weight="500">{escape("  ·  " + tagline)}</tspan></text>')
        ly = y + 12
        for line in wrap(rich(desc), 12.5, text_wd):
            ly += 19
            b.append(rich_line(text_x, ly, line, 12.5, c["ink2"], c["ink"]))
        b.append(t(W - PAD, y + 12, tags, 12, c["ink3"], 500, "end"))
        y = max(ly, y + 32) + 6
    return svg(y + PAD - 6, "".join(b), c, title="Ventures")

def main():
    data = fetch_contributions()
    if data is None:
        print("contribution calendar unreachable, keeping the current activity cards")
    for suffix, c in THEMES.items():
        files = {
            "header": header(c), "card-overview": overview(c),
            "card-toolkit": toolkit(c), "card-ventures": ventures(c),
            "btn-linkedin": button("in", "LinkedIn", True, c),
            "btn-email": button("mail", "E-mail", False, c),
            "btn-github": button("gh", "GitHub", False, c),
        }
        if data:
            files["activity"] = activity(c, data)
        for name, s in files.items():
            (OUT / f"{name}{suffix}.svg").write_text(s, encoding="utf-8")
    print("built", OUT)

if __name__ == "__main__":
    main()
