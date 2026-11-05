#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.67.0", "brotli==1.2.0"]
# ///
"""Build the animated README hero, assets/telegram-message-exporter-readme-hero.svg.

The banner follows the soakes/cv README hero, like the netspeedy CLI ones: the unlocked
chat bubble mark, a two-line headline, a short body and a meta row on the left, and a
generated scene on the right. The scene is a recovery run. A read head steps down a
stack of encrypted cache pages drawn as byte noise, and each chunk it lifts resolves
into a chat bubble that settles left or right in the transcript. As each new one lands,
the oldest is filed into the html, md and csv exports.

Edit the copy, layout or timing here and run `make readme-hero` rather than editing the
generated SVG. The same run writes the GitHub social card. The headline is positioned
from measured advances (see ADVANCE); if you change its words, measure them again with
measure_headline.py. Inter and JetBrains Mono (SIL Open Font License 1.1) are the Google
Fonts builds, kept on assets.netspeedy.io and pinned by checksum in FAMILIES. They're
subset here to the characters the finished SVG renders and embedded, so the hero renders
the same on every platform, and because fontTools is pinned too, a rebuild gives the
same bytes. It runs under `uv run`, which installs that fontTools, and the first run
needs network access to download the fonts.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import random
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "assets" / "telegram-message-exporter-readme-hero.svg"
# assets.netspeedy.io's Cloudflare zone turns away urllib's default user agent.
USER_AGENT = "netspeedy-readme-hero"

# The palette: mint for what's been recovered, violet for what's still encrypted, and
# the same inks and amber as the netspeedy and cv heroes so the banners read as one
# family. The blue Telegram uses is left out on purpose: this is an unofficial tool.
BG = "#060B13"
INK = "#F1F5FA"
INK_2 = "#B5C0CD"
INK_3 = "#808D9E"
MINT = "#3DDBA4"
MINT_2 = "#A8F2D4"
MINT_3 = "#0E9F74"
VIOLET = "#9B7BFF"
VIOLET_2 = "#CDBDFF"
AMBER = "#F5B841"
PEACH = "#FF9F6B"

# Fonts: css class -> (source font, its sha256, weight range, embedded family name). The
# sources are the Google Fonts builds of Inter 4.001 and JetBrains Mono 2.211, kept on
# assets.netspeedy.io and cached after the first download. A new version goes up there
# under a new filename, so these files never change.
FONT_HOST = "https://assets.netspeedy.io/versioned/fonts"
FONT_CACHE = Path.home() / ".cache" / "netspeedy-fonts"
FAMILIES = {
    "sans": (
        "inter-opsz-wght.4.001.ttf",
        "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031",
        "400 800",
        "Hero Sans",
    ),
    "mono": (
        "jetbrains-mono-wght.2.211.ttf",
        "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda",
        "400 700",
        "Hero Mono",
    ),
}
FONT_CSS = (
    ".sans{font-family:'Hero Sans',-apple-system,'Segoe UI','Helvetica Neue',Arial,"
    "sans-serif;font-optical-sizing:auto;}"
    ".mono{font-family:'Hero Mono','SF Mono',Menlo,Consolas,monospace;}"
)
TWINKLE_CSS = (
    ".tw{animation:tw 5.2s ease-in-out infinite;transform-box:fill-box;"
    "transform-origin:center}"
    ".tw1{animation-duration:6.4s}.tw2{animation-duration:4.6s}.tw3{animation-duration:7.3s}"
    "@keyframes tw{0%,100%{opacity:.85}50%{opacity:.15}}"
)

# Starfield: seeded, so rebuilding gives the same sky. No star sits behind the copy.
STAR_SEED = 11
STARS = 110
TWINKLING = 16
COPY_BOX = (36, 30, 520, 340)

# Headline advances in px, measured by measure_headline.py on Inter 800 at 44px (opsz
# 32, letter-spacing -1.3). The swash and the gradients are placed from these.
ADVANCE = {
    "": 0.0,
    "Deleted": 152.81,
    "Deleted from Telegram": 446.04,
    "doesn’t mean gone.": 382.38,
}


# Fonts


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def font_source(name: str, sha256: str) -> bytes:
    """A pinned source font from FONT_HOST, checked against its sha256 and cached."""
    cached = FONT_CACHE / name
    if cached.exists():
        data = cached.read_bytes()
        if hashlib.sha256(data).hexdigest() == sha256:
            return data
    data = fetch(f"{FONT_HOST}/{name}")
    if hashlib.sha256(data).hexdigest() != sha256:
        raise SystemExit(f"{FONT_HOST}/{name} doesn't match its pinned sha256")
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def subset_font(source: bytes, text: str) -> bytes:
    """The variable font cut down to the given characters, as woff2.

    Every axis is kept: trimming them with fontTools' instancer moved the headline's
    pixels. The source's head timestamp is kept too, so the same text always gives the
    same bytes.
    """
    font = TTFont(io.BytesIO(source), recalcTimestamp=False)
    options = subset.Options()
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    font.flavor = "woff2"
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def collect_chars(svg: str) -> dict[str, set[str]]:
    """Characters rendered by each font class, inherited through groups."""
    chars: dict[str, set[str]] = {name: set() for name in FAMILIES}

    def family_of(element: ET.Element, inherited: str | None) -> str | None:
        for cls in (element.get("class") or "").split():
            if cls in FAMILIES:
                return cls
        return inherited

    def walk(element: ET.Element, inherited: str | None, in_text: bool) -> None:
        tag = element.tag.split("}")[-1]
        family = family_of(element, inherited)
        if tag in ("style", "title", "desc", "script"):
            return
        is_text = in_text or tag in ("text", "tspan", "textPath")
        if is_text and tag in ("text", "tspan", "textPath") and element.text:
            if family is None:
                raise SystemExit(f"text without a font class: {element.text!r}")
            chars[family].update(element.text)
        for child in element:
            walk(child, family, is_text)
            if is_text and child.tail and child.tail.strip():
                chars[family or "sans"].update(child.tail)

    walk(ET.fromstring(svg), None, False)
    return chars


def font_faces(svg: str) -> str:
    """One @font-face per family, subset to exactly the characters the SVG renders."""
    chars = collect_chars(svg)
    faces = []
    for cls, (name, sha256, weights, local) in FAMILIES.items():
        used = chars[cls]
        if not used:
            continue
        text = "".join(sorted((used - set("\n\t\r")) | {" "}))
        data = base64.b64encode(subset_font(font_source(name, sha256), text)).decode()
        faces.append(
            f"@font-face{{font-family:'{local}';font-weight:{weights};"
            f"font-style:normal;src:url(data:font/woff2;base64,{data}) "
            "format('woff2');}"
        )
    return "".join(faces)


# Small helpers


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(value: float) -> str:
    """One decimal place, without a trailing .0."""
    text = f"{value:.1f}"
    text = text[:-2] if text.endswith(".0") else text
    return "0" if text == "-0" else text


def pct(fraction: float) -> str:
    """A keyframe offset, to two decimal places."""
    text = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def mono_width(chars: int, size: float, spacing: float = 0.0) -> float:
    """JetBrains Mono advances exactly 0.6 em; letter-spacing applies per glyph."""
    return chars * (size * 0.6 + spacing)


def gradient(kind: str, attrs: str, stops: list[tuple[str, str, str]]) -> list[str]:
    lines = [f"    <{kind} {attrs}>"]
    for offset, colour, opacity in stops:
        alpha = f' stop-opacity="{opacity}"' if opacity else ""
        lines.append(f'      <stop offset="{offset}" stop-color="{colour}"{alpha} />')
    return [*lines, f"    </{kind}>"]


def dot_paths(
    points: list[tuple[float, float, int]],
    styles: dict[int, tuple[float, float]],
    colour: str,
) -> str:
    """Dots grouped by band, each band one path of round-capped stubs."""
    paths = []
    for band, (opacity, width) in styles.items():
        pts = sorted(
            ((x, y) for x, y, b in points if b == band),
            key=lambda p: (round(p[1]), p[0]),
        )
        if not pts:
            continue
        moves = []
        px = py = 0.0
        for x, y in pts:
            # "h.01", not "h0": some renderers drop zero-length subpaths.
            moves.append(f"m{num(x - px)} {num(y - py)}h.01")
            px, py = x + 0.01, y
        paths.append(
            f'<path d="M0 0{"".join(moves)}" fill="none" stroke="{colour}" '
            f'stroke-opacity="{opacity}" stroke-width="{width}" stroke-linecap="round" '
            "/>"
        )
    return "".join(paths)


def byte_noise(
    rng: random.Random, x0: float, y0: float, columns: int, rows: int
) -> list[tuple[float, float, int]]:
    """Dots in pairs, one pair per byte, each byte at a random brightness band."""
    points = []
    for row in range(rows):
        for col in range(columns):
            band = rng.choice((0, 0, 1, 1, 2, 3))
            x, y = x0 + col * BYTE_PITCH, y0 + row * ROW_PITCH
            points += [(x, y, band), (x + PAIR_GAP, y, band)]
    return points


def chip_width(label: str, size: float = 10.5, spacing: float = 1.2) -> float:
    return mono_width(len(label), size, spacing) - spacing + 16


def chip(x: float, y: float, label: str, colour: str) -> str:
    """A mono label in a small outlined box; (x, y) is the box's top-left corner."""
    width = chip_width(label)
    return (
        f'<g><rect x="{num(x)}" y="{num(y)}" width="{num(width)}" height="20" rx="4" '
        f'fill="#0A0F18" fill-opacity="0.9" stroke="{colour}" stroke-opacity="0.4" />'
        f'<text class="mono" x="{num(x + width / 2)}" y="{num(y + 13.8)}" '
        f'text-anchor="middle" font-size="10.5" letter-spacing="1.2" fill="{colour}">'
        f"{esc(label)}</text></g>"
    )


# Shared card


def starfield(
    free: list[tuple[float, float, float, float]],
) -> tuple[list[str], list[str]]:
    """Background gradient and nebula defs, plus the body: glows and seeded stars."""
    rng = random.Random(STAR_SEED)
    stars = []
    tries = 0
    while len(stars) < STARS and tries < STARS * 50:
        tries += 1
        x, y = rng.uniform(8, 1192), rng.uniform(8, 392)
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in free):
            continue
        radius = rng.choice([0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15])
        stars.append((x, y, radius, rng.uniform(0.18, 0.6)))
    twinkling = [
        f'<circle class="tw tw{i % 4}" cx="{num(x)}" cy="{num(y)}" r="{num(r + 0.25)}" '
        f'fill="#DDF2FF" opacity="{o + 0.25:.2f}" '
        f'style="animation-delay:-{rng.uniform(0, 6):.1f}s" />'
        for i, (x, y, r, o) in enumerate(stars[:TWINKLING])
    ]
    plain = "".join(
        f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(r)}" opacity="{o:.2f}" />'
        for x, y, r, o in stars[TWINKLING:]
    )
    defs = [
        '    <linearGradient id="spaceBg" x1="0" y1="0" x2="0.35" y2="1">',
        '      <stop offset="0" stop-color="#081020" />',
        f'      <stop offset="0.55" stop-color="{BG}" />',
        '      <stop offset="1" stop-color="#0B1424" />',
        "    </linearGradient>",
        *gradient(
            "radialGradient",
            'id="nebViolet" cx="0.5" cy="0.5" r="0.5"',
            [("0", VIOLET, "0.26"), ("1", VIOLET, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="nebIndigo" cx="0.5" cy="0.5" r="0.5"',
            [("0", "#3B4BB8", "0.3"), ("1", "#3B4BB8", "0")],
        ),
    ]
    body = [
        '    <rect width="1200" height="400" fill="url(#spaceBg)" />',
        '    <ellipse cx="190" cy="-30" rx="520" ry="260" fill="url(#nebIndigo)" />',
        '    <ellipse cx="900" cy="430" rx="560" ry="300" fill="url(#nebViolet)" '
        'opacity="0.5" />',
        f'    <g fill="#CFE6FF">{plain}</g>',
        f'    <g>{"".join(twinkling)}</g>',
    ]
    return defs, body


# The mark: a chat bubble in the mint-violet-amber gradient, with the open shackle of a
# padlock rising out of it and three dots inside, on a dark tile. It's this project's
# own, so it stays clear of Telegram's paper plane and its blue.
MARK_BUBBLE = (
    "M20 24H44A10 10 0 0 1 54 34V40A10 10 0 0 1 44 50H25L16 56.5V48.6"
    "A10 10 0 0 1 10 40V34A10 10 0 0 1 20 24Z"
)
MARK_SHACKLE = "M24 24V17A8.5 8.5 0 0 1 40.4 13.8"
MARK_DOTS = "M23.5 37h.01M32 37h.01M40.5 37h.01"
MARK_INK = "#F5F8FC"
MARK_STOPS = [("0", MINT), ("0.55", VIOLET), ("1", AMBER)]
MARK_GRADIENT = 'x1="10" y1="12" x2="54" y2="56" gradientUnits="userSpaceOnUse"'
TILE = "#0B1018"


def mark_symbols() -> list[str]:
    """The mark, without its tile."""
    return [
        *gradient(
            "linearGradient",
            f'id="markStroke" {MARK_GRADIENT}',
            [(offset, colour, "") for offset, colour in MARK_STOPS],
        ),
        '    <symbol id="mark" viewBox="0 0 64 64">',
        f'      <path d="{MARK_BUBBLE}" fill="none" stroke="url(#markStroke)" '
        'stroke-width="4" stroke-linejoin="round" />',
        f'      <path d="{MARK_SHACKLE}" fill="none" stroke="{MARK_INK}" '
        'stroke-width="4" stroke-linecap="round" />',
        f'      <path d="{MARK_DOTS}" fill="none" stroke="{MARK_INK}" '
        'stroke-width="5" stroke-linecap="round" />',
        "    </symbol>",
    ]


def lockup() -> list[str]:
    return [
        f'  <rect x="48.5" y="38.5" width="33" height="33" rx="8" fill="{TILE}" '
        'stroke="#3B4A5F" stroke-width="1.2" />',
        '  <use href="#mark" x="49" y="39" width="32" height="32" />',
        f'  <text class="sans" x="94" y="52.5" font-size="15" font-weight="600" '
        f'fill="{INK}">telegram-message-exporter</text>',
        f'  <text class="sans" x="94" y="69.5" font-size="12" fill="{INK_3}">'
        "soakes · unofficial, offline chat recovery for macOS</text>",
    ]


def headline(
    prefix: str, word: str, suffix: str, second: str
) -> tuple[list[str], list[str]]:
    """Two lines at 44px, the first with a highlighted word and an amber swash."""
    x = 46.0
    first = prefix + word + suffix
    start = x + ADVANCE[prefix]
    end = start + ADVANCE[word.rstrip(",.")]
    defs = [
        *gradient(
            "linearGradient",
            f'id="titleWhite" gradientUnits="userSpaceOnUse" x1="{num(x)}" y1="0" '
            f'x2="{num(x + ADVANCE[first])}" y2="0"',
            [("0", "#FFFFFF", ""), ("1", "#DCE6FF", "")],
        ),
        *gradient(
            "linearGradient",
            f'id="hl" gradientUnits="userSpaceOnUse" x1="{num(start)}" y1="0" '
            f'x2="{num(end)}" y2="0"',
            [("0", MINT_2, ""), ("0.5", "#F4F7FA", ""), ("1", AMBER, "")],
        ),
        *gradient(
            "linearGradient",
            f'id="titleBrand" gradientUnits="userSpaceOnUse" x1="{num(x)}" y1="0" '
            f'x2="{num(x + ADVANCE[second])}" y2="0"',
            [("0", MINT, ""), ("0.55", VIOLET_2, ""), ("1", PEACH, "")],
        ),
        *gradient(
            "linearGradient",
            'id="uline" x1="0" y1="0" x2="1" y2="0"',
            [("0", AMBER, "0.35"), ("0.5", AMBER, ""), ("1", AMBER, "0.5")],
        ),
    ]
    span = end - start
    els = [
        f'  <text class="sans" x="{num(x)}" y="160" font-size="44" font-weight="800" '
        'letter-spacing="-1.3" xml:space="preserve">'
        f'<tspan fill="url(#titleWhite)">{esc(prefix)}</tspan>'
        f'<tspan fill="url(#hl)">{esc(word)}</tspan>'
        f'<tspan fill="url(#titleWhite)">{esc(suffix)}</tspan></text>',
        f'  <path d="M{num(start + 2)} 172.5q{num(span * 0.5)} -6.5 {num(span - 6)} '
        '-1.5" '
        'fill="none" stroke="url(#uline)" stroke-width="2.6" stroke-linecap="round" />',
        f'  <text class="sans" x="{num(x)}" y="212" font-size="44" font-weight="800" '
        f'letter-spacing="-1.3" fill="url(#titleBrand)">{esc(second)}</text>',
    ]
    return defs, els


def body(lines: list[list[tuple[str, bool]]]) -> list[str]:
    out = [
        f'  <text class="sans" font-size="15.5" fill="{INK_2}" xml:space="preserve">'
    ]
    for i, segments in enumerate(lines):
        spans = "".join(
            (
                '<tspan class="mono" font-size="14" '
                f'fill="{MINT_2}">{esc(text)}</tspan>'
                if mono
                else esc(text)
            )
            for text, mono in segments
        )
        out.append(f'    <tspan x="48" y="{254 + 23 * i}">{spans}</tspan>')
    out.append("  </text>")
    return out


def meta_row(labels: list[str]) -> str:
    x = 48.0
    parts = []
    for i, label in enumerate(labels):
        if i:
            parts.append(
                f'<circle cx="{num(x + 9)}" cy="318.3" r="2.1" fill="{AMBER}" />'
            )
            x += 19
        parts.append(f'<text x="{num(x)}" y="322">{esc(label)}</text>')
        x += mono_width(len(label), 11.5, 1.5)
    return (
        f'  <g class="mono" font-size="11.5" letter-spacing="1.5" fill="{INK_3}">'
        f'{"".join(parts)}</g>'
    )


# Scene: recovery

# Byte noise: a dot pair per byte, so the pages read as hex rather than as a texture.
BYTE_PITCH = 13.0
PAIR_GAP = 4.2
ROW_PITCH = 6.5
NOISE_SEED = 29

# The transcript. Each bubble is (side, width, lines), where lines is 1, 2 or "photo",
# an attachment that was still in the media cache. There are as many bubbles as steps in
# the loop: one lands each step and the oldest is filed, so the column never runs dry.
BUBBLES = [
    ("in", 124, 1),
    ("out", 98, 1),
    ("in", 152, 2),
    ("out", 126, "photo"),
    ("in", 86, 1),
    ("out", 144, 2),
    ("in", 112, 1),
]
HEIGHT = {1: 24, 2: 38, "photo": 60}
STEPS = len(BUBBLES)
STEP = 1.8  # seconds per bubble
LOOP = STEPS * STEP
# Reduced motion, and the social card, show this moment: the step bubble 5 lands on,
# part of the way through, with that bubble still encrypted on its way from the page.
REST_STEP = 5
REST_U = 0.4

# The encrypted pages: the front sheet and the noise area on it.
PAGE_X, PAGE_Y, PAGE_W, PAGE_H = 604.0, 112.0, 114.0, 190.0
NOISE_TOP, NOISE_BOTTOM = 146.0, 292.0
BAND = (NOISE_BOTTOM - NOISE_TOP + 4) / STEPS

# The transcript column, and where the oldest bubble leaves it for the exports.
COL_L, COL_R, COL_BOTTOM, GAP = 758.0, 944.0, 306.0, 8.0
EXIT_X, EXIT_Y = 982.0, 50.0
# Within each step: when the filed bubble reaches the rail, and when its packet has run
# the length of it.
FILED, RUN_END = 0.48, 0.88

# The exports: three documents, one per format.
DOC_X, DOC_W, DOC_H = 1004.0, 158.0, 58.0
DOCS = [
    ("chat.html", AMBER, 76.0),
    ("chat.md", MINT, 150.0),
    ("chat.csv", VIOLET_2, 224.0),
]


def bubble_height(k: int) -> float:
    return HEIGHT[BUBBLES[k % STEPS][2]]


def settled_x(k: int) -> float:
    side, width, _ = BUBBLES[k]
    return COL_L + width / 2 if side == "in" else COL_R - width / 2


def depth_y(k: int, depth: int) -> float:
    """Centre of bubble k with `depth` newer bubbles stacked below it."""
    below = sum(bubble_height(k + i) + GAP for i in range(1, depth + 1))
    return COL_BOTTOM - below - bubble_height(k) / 2


def band_y(k: int) -> float:
    return NOISE_TOP - 4 + BAND * (k + 0.5)


def bubble_frames(k: int) -> list[tuple[float, float, float, float, float, str]]:
    """Keyframes for bubble k over its own loop: (offset, x, y, scale, opacity, easing).

    Step 0 lifts it off the page and brings it to the bottom of the column, steps 1 to
    STEPS - 2 move it up as newer bubbles land, and the last step files it.
    """
    start = (PAGE_X + PAGE_W * 0.56, band_y(k))
    entry = (settled_x(k), depth_y(k, 0))
    # Two thirds of the way at the ease-in/ease-out join keeps the speed continuous.
    mid = tuple(a + (b - a) * 2 / 3 for a, b in zip(start, entry, strict=True))
    n = STEPS
    frames = [
        (0, *start, 0.45, 0, "linear"),
        (0.08 / n, *start, 0.45, 1, "ease-in"),
        (REST_U / n, *mid, 0.82, 1, "ease-out"),
        (0.56 / n, *entry, 1, 1, "ease-in-out"),
    ]
    for j in range(1, n - 1):
        x, y = settled_x(k), depth_y(k, j - 1)
        frames.append((j / n, x, y, 1, 1, "ease-in-out"))
        frames.append(((j + 0.3) / n, x, depth_y(k, j), 1, 1, "ease-in-out"))
    # Filing: it rises with the rest, then shrinks into the head of the rail.
    last = n - 1
    x = settled_x(k)
    frames.append((last / n, x, depth_y(k, n - 2), 1, 1, "ease-in-out"))
    frames.append(((last + 0.3) / n, x, depth_y(k, n - 1), 0.7, 0.85, "ease-in"))
    frames.append(((last + FILED) / n, EXIT_X, EXIT_Y, 0.08, 0, "linear"))
    frames.append((1, EXIT_X, EXIT_Y, 0.08, 0, "linear"))
    return frames


def rest_state(k: int) -> tuple[float, float, float, float, bool]:
    """Where bubble k sits in the rest frame: x, y, scale, opacity, still encrypted."""
    step = (REST_STEP - k) % STEPS
    if step == 0:
        _, x, y, scale, opacity, _ = bubble_frames(k)[2]
        return x, y, scale, opacity, True
    if step == STEPS - 1:
        return EXIT_X, EXIT_Y, 0.08, 0, False
    return settled_x(k), depth_y(k, step), 1, 1, False


def bubble_shape(width: float, height: float, side: str) -> str:
    """A rounded bubble centred on the origin, its tail at the bottom on its side."""
    x0, y0, x1, y1 = -width / 2, -height / 2, width / 2, height / 2
    r = min(10.0, height / 2)
    if side == "in":
        return (
            f"M{num(x0 + r)} {num(y0)}H{num(x1 - r)}A{num(r)} {num(r)} 0 0 1 {num(x1)} "
            f"{num(y0 + r)}V{num(y1 - r)}"
            f"A{num(r)} {num(r)} 0 0 1 {num(x1 - r)} {num(y1)}"
            f"H{num(x0 + 9)}Q{num(x0 + 2)} {num(y1)} {num(x0 - 4)} {num(y1 + 2.5)}"
            f"Q{num(x0)} {num(y1 - 2)} {num(x0)} {num(y1 - 8)}V{num(y0 + r)}"
            f"A{num(r)} {num(r)} 0 0 1 {num(x0 + r)} {num(y0)}Z"
        )
    return (
        f"M{num(x1 - r)} {num(y0)}H{num(x0 + r)}A{num(r)} {num(r)} 0 0 0 {num(x0)} "
        f"{num(y0 + r)}V{num(y1 - r)}A{num(r)} {num(r)} 0 0 0 {num(x0 + r)} {num(y1)}"
        f"H{num(x1 - 9)}Q{num(x1 - 2)} {num(y1)} {num(x1 + 4)} {num(y1 + 2.5)}"
        f"Q{num(x1)} {num(y1 - 2)} {num(x1)} {num(y1 - 8)}V{num(y0 + r)}"
        f"A{num(r)} {num(r)} 0 0 0 {num(x1 - r)} {num(y0)}Z"
    )


def bubble_text(width: float, lines: int | str, side: str, rng: random.Random) -> str:
    """Message text as rounded bars: the transcript is shown, never invented."""
    colour, opacity = (INK_2, 0.5) if side == "in" else (MINT_2, 0.62)
    x0 = -width / 2 + 11
    room = width - 22
    if lines == "photo":
        return ""
    rows = [0.0] if lines == 1 else [-6.5, 6.5]
    lengths = [room * rng.uniform(0.72, 0.96)] + [room * rng.uniform(0.42, 0.62)]
    d = "".join(
        f"M{num(x0)} {num(y)}h{num(length)}"
        for y, length in zip(rows, lengths, strict=False)
    )
    return (
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-opacity="{opacity}" '
        'stroke-width="4" stroke-linecap="round" />'
    )


def photo(width: float, height: float) -> str:
    """A cached image attachment: a small landscape inset in the bubble."""
    x0, y0 = -width / 2 + 4, -height / 2 + 4
    w, h = width - 8, height - 8
    ground = y0 + h
    ridge = (
        f"M{num(x0)} {num(ground)}L{num(x0 + w * 0.3)} {num(ground - h * 0.52)}"
        f"L{num(x0 + w * 0.46)} {num(ground - h * 0.3)}"
        f"L{num(x0 + w * 0.68)} {num(ground - h * 0.66)}"
        f"L{num(x0 + w)} {num(ground - h * 0.22)}V{num(ground)}Z"
    )
    return (
        f'<rect x="{num(x0)}" y="{num(y0)}" width="{num(w)}" height="{num(h)}" rx="7" '
        'fill="url(#photo)" />'
        f'<g clip-path="url(#photoClip)"><path d="{ridge}" fill="{MINT_3}" '
        'fill-opacity="0.55" />'
        f'<circle cx="{num(x0 + w * 0.22)}" cy="{num(y0 + h * 0.3)}" r="5" '
        f'fill="{AMBER}" fill-opacity="0.85" /></g>'
    )


def bubbles(rng: random.Random) -> tuple[str, str]:
    """The transcript bubbles, each with an encrypted face and a recovered one."""
    css = []
    els = []
    for k, (side, width, lines) in enumerate(BUBBLES):
        height = bubble_height(k)
        frames = bubble_frames(k)
        steps = "".join(
            f"{pct(offset)}{{transform:translate({num(x)}px,{num(y)}px) scale({scale});"
            f"opacity:{opacity};animation-timing-function:{easing}}}"
            for offset, x, y, scale, opacity, easing in frames
        )
        # Bubble k lands on step k, so at 0s it is STEPS - k steps into its own loop.
        delay = k * STEP - LOOP if k else 0.0
        css.append(
            f"@keyframes b{k}{{{steps}}}"
            f".b{k}{{animation:b{k} {LOOP:.1f}s {delay:.1f}s infinite}}"
            f".b{k} .bn{{animation:bn {LOOP:.1f}s linear {delay:.1f}s infinite}}"
            f".b{k} .bc{{animation:bc {LOOP:.1f}s linear {delay:.1f}s infinite}}"
        )
        x, y, scale, opacity, encrypted = rest_state(k)
        transform = f"translate({num(x)} {num(y)})" + (
            f" scale({scale})" if scale != 1 else ""
        )
        shape = bubble_shape(width, height, side)
        if side == "in":
            fill, stroke, stroke_opacity = "#111A27", INK_3, 0.34
        else:
            fill, stroke, stroke_opacity = "#0C251E", MINT, 0.5
        content = (
            photo(width, height)
            if lines == "photo"
            else bubble_text(width, lines, side, rng)
        )
        els.append(
            f'<g class="b{k}" transform="{transform}" opacity="{opacity}">'
            f'<g class="bn" opacity="{1 if encrypted else 0}">'
            f'<rect x="{num(-width / 2)}" y="{num(-height / 2)}" width="{width}" '
            f'height="{height}" rx="7" fill="#0A1020" stroke="{VIOLET}" '
            'stroke-opacity="0.5" />'
            f'<rect x="{num(-width / 2)}" y="{num(-height / 2)}" width="{width}" '
            f'height="{height}" rx="7" fill="url(#bytes)" /></g>'
            f'<g class="bc" opacity="{0 if encrypted else 1}">'
            f'<path d="{shape}" fill="{fill}" stroke="{stroke}" '
            f'stroke-opacity="{stroke_opacity}" stroke-width="1.2" />{content}</g></g>'
        )
    n = STEPS
    css.append(
        f"@keyframes bn{{0%,{pct(0.56 / n)}{{opacity:1}}"
        f"{pct(0.8 / n)},100%{{opacity:0}}}}"
        f"@keyframes bc{{0%,{pct(0.56 / n)}{{opacity:0}}"
        f"{pct(0.8 / n)},100%{{opacity:1}}}}"
    )
    return "".join(css), "".join(els)


def pages(rng: random.Random) -> tuple[str, str]:
    """The stack of encrypted cache pages, and the read head stepping down them."""
    sheets = "".join(
        f'<rect x="{num(PAGE_X - dx)}" y="{num(PAGE_Y - dx)}" width="{PAGE_W}" '
        f'height="{PAGE_H}" rx="7" fill="#0A1020" stroke="{VIOLET}" '
        f'stroke-opacity="{opacity}" />'
        for dx, opacity in ((14, 0.18), (7, 0.3))
    )
    front = (
        f'<rect x="{PAGE_X}" y="{PAGE_Y}" width="{PAGE_W}" height="{PAGE_H}" rx="7" '
        f'fill="url(#page)" stroke="{VIOLET}" stroke-opacity="0.55" '
        'stroke-width="1.2" />'
    )
    header = (
        f'<text class="mono" x="{num(PAGE_X + 12)}" y="{num(PAGE_Y + 21)}" '
        f'font-size="10.5" letter-spacing="0.4" fill="{VIOLET_2}">db_sqlite</text>'
        f'<path d="M{num(PAGE_X + 12)} {num(PAGE_Y + 30.5)}'
        f'H{num(PAGE_X + PAGE_W - 12)}" stroke="{VIOLET}" stroke-opacity="0.3" />'
    )
    lx, ly = PAGE_X + PAGE_W - 21, PAGE_Y + 13
    lock = (
        f'<rect x="{num(lx)}" y="{num(ly + 4)}" width="9" height="7" rx="1.6" '
        f'fill="{VIOLET_2}" fill-opacity="0.85" />'
        f'<path d="M{num(lx + 2)} {num(ly + 4)}V{num(ly + 2.2)}a2.5 2.5 0 0 1 5 0'
        f'V{num(ly + 4)}" fill="none" stroke="{VIOLET_2}" stroke-width="1.4" />'
    )
    columns = 7
    span = (columns - 1) * BYTE_PITCH + PAIR_GAP
    x0 = PAGE_X + (PAGE_W - span) / 2
    rows = int((NOISE_BOTTOM - NOISE_TOP) / ROW_PITCH) + 1
    noise = dot_paths(
        byte_noise(rng, x0, NOISE_TOP, columns, rows),
        {0: (0.16, 1.5), 1: (0.32, 1.6), 2: (0.52, 1.7), 3: (0.78, 1.8)},
        VIOLET_2,
    )
    # The read head moves to the next band at the start of every step, where the next
    # chunk lifts off.
    head_steps = []
    for k in range(STEPS):
        head_steps.append(
            f"{pct(k / STEPS)}{{transform:translateY({num(BAND * (k - 1))}px)}}"
        )
        head_steps.append(
            f"{pct((k + 0.1) / STEPS)}{{transform:translateY({num(BAND * k)}px)}}"
        )
    head_steps[0] = f"0%{{transform:translateY({num(BAND * (STEPS - 1))}px)}}"
    head_steps.append(f"100%{{transform:translateY({num(BAND * (STEPS - 1))}px)}}")
    css = (
        f".rh{{animation:rh {LOOP:.1f}s ease-in-out infinite}}"
        f"@keyframes rh{{{''.join(head_steps)}}}"
    )
    hy = NOISE_TOP - 4
    head = (
        f'<g class="rh" transform="translate(0 {num(BAND * REST_STEP)})">'
        f'<rect x="{num(PAGE_X + 5)}" y="{num(hy)}" width="{num(PAGE_W - 10)}" '
        f'height="{num(BAND)}" rx="4" fill="{MINT}" fill-opacity="0.13" '
        f'stroke="{MINT}" stroke-opacity="0.55" />'
        f'<path d="M{num(PAGE_X - 3)} {num(hy + BAND / 2)}h5'
        f'M{num(PAGE_X + PAGE_W - 2)} {num(hy + BAND / 2)}h5" stroke="{MINT}" '
        'stroke-width="2" stroke-linecap="round" />'
        "</g>"
    )
    return css, sheets + front + header + lock + noise + head


def doc_shape(x: float, y: float) -> str:
    """A document with its top-right corner folded."""
    w, h, r, fold = DOC_W, DOC_H, 8, 13
    return (
        f"M{num(x + r)} {num(y)}H{num(x + w - fold)}L{num(x + w)} {num(y + fold)}"
        f"V{num(y + h - r)}A{r} {r} 0 0 1 {num(x + w - r)} {num(y + h)}H{num(x + r)}"
        f"A{r} {r} 0 0 1 {num(x)} {num(y + h - r)}V{num(y + r)}A{r} {r} 0 0 1 "
        f"{num(x + r)} {num(y)}Z"
    )


def doc_preview(kind: str, x: float, y: float, colour: str) -> str:
    """A glimpse of each format: styled bubbles, Markdown lines, or a grid of cells."""
    left, top = x + 12, y + 31
    if kind == "chat.html":
        return (
            f'<rect x="{num(left)}" y="{num(top)}" width="60" height="9" rx="4.5" '
            f'fill="{INK_3}" fill-opacity="0.35" />'
            f'<rect x="{num(x + DOC_W - 12 - 50)}" y="{num(top + 12)}" width="50" '
            f'height="9" rx="4.5" fill="{colour}" fill-opacity="0.4" />'
        )
    if kind == "chat.md":
        return (
            f'<path d="M{num(left)} {num(top + 3)}h7M{num(left)} {num(top + 15)}h2" '
            f'stroke="{colour}" stroke-width="3" stroke-linecap="round" />'
            f'<path d="M{num(left + 14)} {num(top + 3)}h66M{num(left + 10)} '
            f'{num(top + 15)}h96" stroke="{INK_3}" stroke-opacity="0.55" '
            'stroke-width="3" stroke-linecap="round" />'
        )
    cells = []
    widths = (30, 54, 46)
    for row in range(2):
        cx = left
        for col, width in enumerate(widths):
            cells.append(
                f"M{num(cx)} {num(top + 3 + row * 12)}"
                f"h{num(width - 10 - row * 4 * col)}"
            )
            cx += width + 2
    seps = "".join(
        f"M{num(left + sum(widths[: i + 1]) + 2 * i - 4)} {num(top - 2)}v20"
        for i in range(2)
    )
    return (
        f'<path d="{"".join(cells)}" stroke="{INK_3}" stroke-opacity="0.55" '
        'stroke-width="3" stroke-linecap="round" />'
        f'<path d="{seps}" stroke="{colour}" stroke-opacity="0.5" />'
    )


def exports() -> tuple[str, str]:
    """The three export formats, and the line that files each bubble into them."""
    mids = [y + DOC_H / 2 for _, _, y in DOCS]
    spine = f"M{num(EXIT_X)} {num(EXIT_Y)}V{num(mids[-1])}"
    stubs = "".join(f"M{num(EXIT_X)} {num(m)}H{num(DOC_X)}" for m in mids)
    length = mids[-1] - EXIT_Y
    rail = (
        f'<path d="{spine}{stubs}" fill="none" stroke="{INK_3}" stroke-opacity="0.4" '
        'stroke-width="1.2" />'
        f'<circle cx="{num(EXIT_X)}" cy="{num(EXIT_Y)}" r="4" fill="#0A1220" '
        f'stroke="{MINT}" stroke-opacity="0.8" stroke-width="1.4" />'
        f'<circle class="ping" cx="{num(EXIT_X)}" cy="{num(EXIT_Y)}" r="4" fill="none" '
        f'stroke="{MINT_2}" stroke-width="1.1" '
        f'style="animation-delay:{FILED * STEP - STEP:.2f}s" />'
    )
    # A packet runs down the rail each step, once the oldest bubble has been filed. The
    # rest frame has it between the first two exports.
    leave, done = FILED, RUN_END
    packet_rest = 10 - ((mids[0] + mids[1]) / 2 - EXIT_Y + 5)
    packet = (
        f'<path class="pk" d="{spine}" fill="none" stroke="{MINT_2}" stroke-width="3" '
        f'stroke-linecap="round" stroke-dasharray="10 {num(length + 40)}" '
        f'stroke-dashoffset="{num(packet_rest)}" />'
    )
    css = [
        f".pk{{animation:pk {STEP}s linear infinite}}"
        f"@keyframes pk{{0%,{pct(leave)}{{stroke-dashoffset:10}}"
        f"{pct(done)},100%{{stroke-dashoffset:{num(-length)}}}}}"
        ".ping{transform-box:fill-box;transform-origin:center;opacity:0;"
        f"animation:ping {STEP}s ease-out infinite}}"
        "@keyframes ping{0%{opacity:.9;transform:scale(1)}30%{opacity:0;"
        "transform:scale(3.6)}100%{opacity:0;transform:scale(3.6)}}"
        f".fl{{opacity:0;animation:fl {STEP}s ease-out infinite}}"
        "@keyframes fl{0%{opacity:.9}40%{opacity:0}100%{opacity:0}}"
    ]
    els = []
    for (kind, colour, y), mid in zip(DOCS, mids, strict=True):
        reach = leave + (done - leave) * (mid - EXIT_Y) / (length + 10)
        delay = reach * STEP - STEP
        shape = doc_shape(DOC_X, y)
        els.append(
            f'<path d="{shape}" fill="#0A1220" stroke="{colour}" stroke-opacity="0.4" '
            'stroke-width="1.2" />'
            f'<path d="M{num(DOC_X + DOC_W - 13)} {num(y)}V{num(y + 9)}q0 4 4 4'
            f'H{num(DOC_X + DOC_W)}" fill="none" stroke="{colour}" '
            'stroke-opacity="0.4" stroke-width="1.2" />'
            f'<path class="fl" d="{shape}" fill="none" stroke="{colour}" '
            f'stroke-width="1.6" style="animation-delay:{delay:.2f}s" />'
            f'<text class="mono" x="{num(DOC_X + 12)}" y="{num(y + 20)}" '
            f'font-size="11" letter-spacing="0.4" fill="{colour}">{kind}</text>'
            + doc_preview(kind, DOC_X, y, colour)
            + f'<circle class="ping" cx="{num(DOC_X)}" cy="{num(mid)}" r="2.6" '
            f'fill="none" stroke="{colour}" stroke-width="1.1" '
            f'style="animation-delay:{delay:.2f}s" />'
            f'<circle cx="{num(DOC_X)}" cy="{num(mid)}" r="2.2" fill="{colour}" />'
        )
    return "".join(css), rail + packet + "".join(els)


def scene_recovery() -> (
    tuple[list[str], str, str, list[tuple[float, float, float, float]]]
):
    """Encrypted cache pages resolving into chat bubbles, filed into three exports."""
    rng = random.Random(NOISE_SEED)
    page_css, page_els = pages(rng)
    bubble_css, bubble_els = bubbles(rng)
    export_css, export_els = exports()
    pattern_dots = dot_paths(
        byte_noise(rng, 3, 3.25, 4, 4),
        {0: (0.2, 1.5), 1: (0.38, 1.6), 2: (0.58, 1.7), 3: (0.85, 1.8)},
        VIOLET_2,
    )
    photo_w, photo_h = next(
        (w - 8, HEIGHT[lines] - 8) for _, w, lines in BUBBLES if lines == "photo"
    )
    labels = "".join(
        f'<text class="mono" x="{num(x)}" y="340" text-anchor="middle" '
        f'font-size="10.5" letter-spacing="2" fill="{colour}">{name}</text>'
        for x, name, colour in (
            (PAGE_X + PAGE_W / 2 - 7, "ENCRYPTED COPY", VIOLET_2),
            ((COL_L + COL_R) / 2, "RECOVERED", MINT),
            (DOC_X + DOC_W / 2, "EXPORTED", AMBER),
        )
    )
    defs = [
        *gradient(
            "radialGradient",
            'id="aura" cx="0.5" cy="0.5" r="0.5"',
            [("0", MINT_3, "0.2"), ("0.6", VIOLET, "0.06"), ("1", VIOLET, "0")],
        ),
        *gradient(
            "linearGradient",
            'id="page" x1="0" y1="0" x2="0" y2="1"',
            [("0", "#0D1428", ""), ("1", "#090E1C", "")],
        ),
        *gradient(
            "linearGradient",
            'id="photo" x1="0" y1="0" x2="1" y2="1"',
            [("0", "#16324A", ""), ("1", "#2B2350", "")],
        ),
        f'    <clipPath id="photoClip"><rect x="{num(-photo_w / 2)}" '
        f'y="{num(-photo_h / 2)}" width="{photo_w}" height="{photo_h}" rx="7" />'
        "</clipPath>",
        '    <pattern id="bytes" width="52" height="26" patternUnits="userSpaceOnUse">'
        f"{pattern_dots}</pattern>",
    ]
    css = page_css + bubble_css + export_css
    scene = "".join(
        [
            '<ellipse cx="880" cy="196" rx="340" ry="210" fill="url(#aura)" />',
            page_els,
            export_els,
            bubble_els,
            labels,
        ]
    )
    return defs, css, scene, [(575, 40, 1180, 360)]


# Copy

CARD = {
    "title": "telegram-message-exporter - deleted from Telegram doesn’t mean gone",
    "desc": (
        "A stack of encrypted cache pages drawn as byte noise. A read head steps down "
        "them, and each chunk it lifts resolves into a chat bubble that settles left "
        "or "
        "right in a transcript, while the oldest bubble is filed into html, md and csv "
        "exports."
    ),
    "headline": ("", "Deleted", " from Telegram", "doesn’t mean gone."),
    "body": [
        [
            ("Decrypts a copy of the ", False),
            ("db_sqlite", True),
            (" cache, fully offline,", False),
        ],
        [
            ("and exports chats as ", False),
            ("html", True),
            (", ", False),
            ("md", True),
            (" or ", False),
            ("csv", True),
            (" with cached media.", False),
        ],
    ],
    "meta": ["DISCOVER", "DECRYPT", "DECODE", "EXPORT"],
    "scene": scene_recovery,
}


def build_svg(spec: dict = CARD) -> str:
    scene_defs, scene_css, scene, free = spec["scene"]()
    star_defs, star_body = starfield([COPY_BOX, *free])
    head_defs, head_els = headline(*spec["headline"])
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400" width="960" '
        'height="320" role="img" aria-labelledby="title desc">',
        f'  <title id="title">{esc(spec["title"])}</title>',
        f'  <desc id="desc">{esc(spec["desc"])}</desc>',
        "",
        "  <defs>",
        "    <style>",
        "      /* Inter and JetBrains Mono, SIL Open Font License 1.1, subset to the "
        "glyphs used here. */",
        "      __FONT_FACES__",
        f"      {FONT_CSS}",
        f"      {TWINKLE_CSS}",
        f"      {scene_css}",
        "      @media (prefers-reduced-motion: reduce){",
        "        *{animation:none !important}",
        "      }",
        "    </style>",
        *star_defs,
        *mark_symbols(),
        *head_defs,
        *scene_defs,
        '    <clipPath id="frame"><rect x="1" y="1" width="1198" height="398" rx="20" '
        "/>"
        "</clipPath>",
        "  </defs>",
        "",
        '  <g clip-path="url(#frame)">',
        *star_body,
        f"    {scene}",
        "  </g>",
        '  <rect x="0.75" y="0.75" width="1198.5" height="398.5" rx="20" fill="none" '
        'stroke="#1A2638" stroke-width="1.5" />',
        "",
        "  <!-- Left: brand and headline -->",
        *lockup(),
        "",
        *head_els,
        *body(spec["body"]),
        meta_row(spec["meta"]),
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


# Social card

# The GitHub social preview is the hero recomposed for 1280x640 and frozen at its rest
# frame. GitHub has no API for it, so it's uploaded by hand under Settings > General >
# Social preview.
REPO = "soakes/telegram-message-exporter"
SOCIAL_CARD = ROOT / "assets" / "telegram-message-exporter-social-card.png"
SVG_NS = "http://www.w3.org/2000/svg"
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def build_social_svg(hero: str, width: int, height: int) -> str:
    """The hero's copy column on the left and its scene on the right, scaled up."""
    ET.register_namespace("", SVG_NS)
    root = ET.fromstring(hero)

    def tag(name: str) -> str:
        return f"{{{SVG_NS}}}{name}"

    children = list(root)
    defs = root.find(tag("defs"))
    style = defs.find(tag("style"))
    style.text = (style.text or "") + "  *{animation:none !important}\n    "
    frame = next(c for c in children if c.get("clip-path") == "url(#frame)")
    # Everything after the clipped group, bar the frame's outline, is the copy column.
    copy_els = [
        c
        for c in children[children.index(frame) + 1 :]
        if not (c.tag == tag("rect") and c.get("fill") == "none")
    ]
    background = list(frame)
    nebulae = [c for c in background[1:3] if c.tag == tag("ellipse")]
    scene_els = background[
        5:
    ]  # after the base, the two nebulae and the two star groups

    s_copy, s_scene, margin = 1.2, 1.0, 60
    card = ET.Element(
        tag("svg"),
        {
            "viewBox": f"0 0 {width} {height}",
            "width": str(width),
            "height": str(height),
            "role": "img",
            "aria-labelledby": "title desc",
        },
    )
    card.extend([root.find(tag("title")), root.find(tag("desc")), defs])
    ET.SubElement(
        card,
        tag("rect"),
        {"width": str(width), "height": str(height), "fill": "url(#spaceBg)"},
    )
    glow = ET.SubElement(
        card, tag("g"), {"transform": f"scale({width / 1200:.4f} {height / 400:.4f})"}
    )
    glow.extend(nebulae)
    rng = random.Random(STAR_SEED)
    stars = ET.SubElement(card, tag("g"), {"fill": "#CFE6FF"})
    placed = 0
    while placed < 150:
        x, y = rng.uniform(6, width - 6), rng.uniform(6, height - 6)
        if 40 <= x <= 680 and 110 <= y <= 530:  # keep the copy column clear
            continue
        placed += 1
        radius = rng.choice([0.6, 0.7, 0.8, 0.9, 1.0, 1.2])
        opacity = f"{rng.uniform(0.2, 0.65):.2f}"
        ET.SubElement(
            stars,
            tag("circle"),
            {"cx": num(x), "cy": num(y), "r": num(radius), "opacity": opacity},
        )
    # The exports' right edge sits a margin in from the card's, which leaves the
    # headline room.
    scene_x = width - 44 - (DOC_X + DOC_W) * s_scene
    scene_y = (height - 400 * s_scene) / 2 + 6
    scene = ET.SubElement(
        card,
        tag("g"),
        {"transform": f"translate({num(scene_x)} {num(scene_y)}) scale({s_scene})"},
    )
    scene.extend(scene_els)
    copy_x = margin - 46 * s_copy
    copy_y = (height - 300 * s_copy) / 2 - 30 * s_copy - 8
    column = ET.SubElement(
        card,
        tag("g"),
        {"transform": f"translate({num(copy_x)} {num(copy_y)}) scale({s_copy})"},
    )
    column.extend(copy_els)
    footer = ET.SubElement(
        card,
        tag("text"),
        {
            "class": "mono",
            "x": str(margin),
            "y": str(height - 44),
            "font-size": "15",
            "letter-spacing": "1.5",
            "fill": INK_3,
        },
    )
    footer.text = f"github.com/{REPO}"
    return ET.tostring(card, encoding="unicode") + "\n"


def render_png(svg_path: Path, png_path: Path, width: int, height: int) -> None:
    """Screenshot an SVG in headless Chrome, which renders the embedded fonts."""
    chrome = os.environ.get("CHROME") or next(
        (c for c in CHROME_CANDIDATES if Path(c).exists() or shutil.which(c)), None
    )
    if not chrome:
        raise SystemExit(
            "the social card needs Chrome or Chromium to render; set CHROME"
        )
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--user-data-dir={profile}",
                f"--window-size={width},{height}",
                f"--screenshot={png_path}",
                svg_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )


def write_social_card(hero: str) -> None:
    width, height = 1280, 640
    svg = build_social_svg(hero, width, height)
    svg = svg.replace("__FONT_FACES__", font_faces(svg))
    ET.fromstring(svg)
    SOCIAL_CARD.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / "card.svg"
        svg_path.write_text(svg, encoding="utf-8")
        render_png(svg_path, SOCIAL_CARD, width, height)
    print(f"Wrote {SOCIAL_CARD.relative_to(ROOT)} ({width}x{height})")


def main() -> None:
    hero = build_svg()
    svg = hero.replace("__FONT_FACES__", font_faces(hero))
    if "http://" in svg.replace("http://www.w3.org/2000/svg", "") or "https://" in svg:
        raise SystemExit("external reference found in the hero SVG")
    ET.fromstring(svg)  # well-formed, or this raises
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(svg.encode()) / 1024:.1f} KiB)")
    write_social_card(hero)


if __name__ == "__main__":
    main()
