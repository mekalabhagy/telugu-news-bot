"""Render a 1080x1350 (4:5) Telugu news card as JPEG.

All artwork is generated here (gradients + shapes); no outlet photos are used.
Telugu text is shaped with Raqm, so conjuncts render correctly. Latin letters
and digits come from Noto Sans because the Telugu font has no Latin glyphs.
"""
import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import CHANNEL_HANDLE, CHANNEL_NAME, ROOT

W, H = 1080, 1350
FONT_DIR = ROOT / "fonts"

# category -> (gradient top, gradient bottom, accent, Telugu label)
PAL = {
    "politics":      ((20, 24, 60), (70, 25, 80), (255, 196, 0), "రాజకీయం"),
    "india":         ((12, 40, 70), (20, 80, 90), (255, 153, 51), "భారత్"),
    "world":         ((15, 25, 45), (35, 60, 110), (80, 200, 255), "ప్రపంచం"),
    "business":      ((10, 45, 40), (20, 85, 60), (120, 235, 150), "వ్యాపారం"),
    "tech":          ((25, 20, 70), (50, 40, 140), (120, 180, 255), "టెక్నాలజీ"),
    "sports":        ((70, 20, 20), (140, 40, 30), (255, 214, 10), "క్రీడలు"),
    "entertainment": ((70, 20, 70), (140, 30, 100), (255, 140, 200), "సినిమా"),
    "science":       ((10, 40, 60), (20, 90, 120), (150, 240, 220), "సైన్స్"),
    "local":         ((60, 30, 15), (130, 60, 25), (255, 200, 90), "స్థానికం"),
    "general":       ((25, 30, 50), (55, 65, 100), (255, 200, 60), "వార్తలు"),
}

_cache = {}


def _font(kind, weight, size):
    key = (kind, weight, size)
    if key not in _cache:
        name = "NotoSansTelugu" if kind == "te" else "NotoSans"
        _cache[key] = ImageFont.truetype(
            str(FONT_DIR / f"{name}-{weight}.ttf"), size, layout_engine=ImageFont.Layout.RAQM
        )
    return _cache[key]


def _is_te(ch):
    o = ord(ch)
    return 0x0C00 <= o <= 0x0C7F or o in (0x200C, 0x200D)


def _runs(text):
    """Split into (kind, text) runs; spaces stay with the preceding run."""
    out, cur, kind = [], "", None
    for ch in text:
        k = kind or "latin" if ch == " " else ("te" if _is_te(ch) else "latin")
        if kind is None:
            kind = k
        if k != kind and cur:
            out.append((kind, cur))
            cur, kind = "", k
        cur += ch
    if cur:
        out.append((kind or "latin", cur))
    return out


_SUBS = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "₹": "రూ."}


def clean(text):
    for a, b in _SUBS.items():
        text = text.replace(a, b)
    return " ".join(text.split())


def measure(text, size, weight):
    return sum(_font(k, weight, size).getlength(t) for k, t in _runs(text))


def draw_text(d, x, baseline, text, size, weight, fill, align="left"):
    w = measure(text, size, weight)
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    for kind, t in _runs(text):
        f = _font(kind, weight, size)
        d.text((x, baseline), t, font=f, fill=fill, anchor="ls")
        x += f.getlength(t)
    return w


def wrap(text, size, weight, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if measure(trial, size, weight) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _gradient(top, bottom):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.convert("RGBA")


def render_card(card: dict, out_path: Path, source_line: str = "", demo: bool = False) -> Path:
    top, bottom, accent, label = PAL.get(card.get("category", "general"), PAL["general"])
    img = _gradient(top, bottom)

    # decorative shapes
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((560, -260, 1300, 480), fill=(*accent, 34))
    od.ellipse((-300, 760, 380, 1440), fill=(255, 255, 255, 16))
    od.polygon([(0, 1040), (W, 900), (W, 1010), (0, 1150)], fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img, ov)

    # header + footer bands
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bd.rectangle((0, 0, W, 150), fill=(0, 0, 0, 95))
    bd.rectangle((0, 1190, W, H), fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, band)
    d = ImageDraw.Draw(img)

    # header: logo disc, channel name, date
    d.ellipse((40, 35, 120, 115), fill=accent)
    draw_text(d, 80, 91, "తె", 40, 800, top, "center")
    name_size = 44
    while measure(CHANNEL_NAME, name_size, 700) > 560 and name_size > 28:
        name_size -= 2
    draw_text(d, 142, 90, CHANNEL_NAME, name_size, 700, (255, 255, 255))
    draw_text(d, W - 50, 88, dt.datetime.now().strftime("%d %b %Y"), 28, 400, (220, 225, 240), "right")

    # category chip
    chip_w = int(measure(label, 34, 700)) + 64
    d.rounded_rectangle((60, 200, 60 + chip_w, 266), radius=33, fill=accent)
    draw_text(d, 60 + chip_w / 2, 245, label, 34, 700, top, "center")
    if demo:
        d.rounded_rectangle((W - 330, 200, W - 60, 266), radius=33, outline=(255, 255, 255), width=3)
        draw_text(d, W - 195, 245, "DEMO SAMPLE", 28, 700, (255, 255, 255), "center")

    # headline: largest size that fits in 5 lines
    headline = clean(card["headline_te"])
    x0, max_w = 100, W - 100 - 60
    for size in (80, 74, 68, 62, 56, 50):
        lines = wrap(headline, size, 800, max_w)
        if len(lines) <= 5:
            break
    lh = int(size * 1.6)
    y = 380
    first = y
    for ln in lines:
        draw_text(d, x0, y, ln, size, 800, (255, 255, 255))
        y += lh
    d.rounded_rectangle((60, first - int(size * 0.95), 72, y - lh + int(size * 0.5)), radius=6, fill=accent)

    # summary: shrink until it fits above the footer
    summary = clean(card["summary_te"])
    s_top = y + 20
    s_limit = 1150
    for ssize in (40, 37, 34, 31, 28):
        slines = wrap(summary, ssize, 400, W - 120)
        slh = int(ssize * 1.65)
        if s_top + len(slines) * slh <= s_limit:
            break
    else:
        slines = slines[: max(1, (s_limit - s_top) // slh)]
        slines[-1] = slines[-1].rstrip(" ,.") + "..."
    sy = s_top
    for ln in slines:
        draw_text(d, 60, sy, ln, ssize, 400, (228, 233, 246))
        sy += slh

    # footer: source credit, handle, AI disclosure
    src = clean(source_line) if source_line else ""
    if src:
        draw_text(d, 60, 1262, f"మూలం: {src}", 32, 700, (255, 255, 255))
    draw_text(d, W - 60, 1262, CHANNEL_HANDLE, 32, 700, accent, "right")
    draw_text(d, 60, 1318, "AI సహాయంతో రూపొందించబడింది", 24, 400, (190, 198, 220))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Instagram's API accepts JPEG only for image posts
    img.convert("RGB").save(out_path, "JPEG", quality=93, optimize=True)
    return out_path
