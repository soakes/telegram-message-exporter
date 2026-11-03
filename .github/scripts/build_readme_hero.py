#!/usr/bin/env python3
"""Build the animated README hero from readme-hero.template.svg.

The terminal session below types itself out on a loop. Each line's typing time
is derived from its length, so edit SESSION and rerun rather than editing the
generated SVG. Inter and JetBrains Mono (SIL Open Font License 1.1) are fetched
from Google Fonts, subset to the characters used, and embedded, so the hero
renders the same on every platform. Needs network access.
"""

from __future__ import annotations

import base64
import re
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("readme-hero.template.svg")
OUTPUT = ROOT / "assets" / "telegram-message-exporter-readme-hero.svg"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Terminal geometry. JetBrains Mono advances exactly 0.6 em per character.
FONT_SIZE = 11.5
CHAR_W = FONT_SIZE * 0.6
LINE_H = 16.5
GAP = 6
X0 = 570.0
PROMPT_W = 2 * CHAR_W
Y0 = 92.0
TYPING_CPS = 52.0
LOOP_S = 16.0
TERMINAL_BG = "#090E1A"

BIN = "#60A5FA"
FLAG = "#7C89A6"
ARG = "#C8D1E2"
OUT = "#C8D1E2"
DIM = "#7C89A6"
BRIGHT = "#E2E8F0"
STEP = {
    "discover": "#22D3EE",
    "decrypt": "#34D399",
    "list-peers": "#A78BFA",
    "export": "#F59E0B",
}

Segment = tuple[str, str, bool]

# (kind, segments, gap before). "cmd" lines get a prompt and are typed, "cont"
# lines are typed continuations, "out" lines appear as printed output. Output
# text matches what telegram-exporter prints; paths are shortened to fit.
SESSION: list[tuple[str, list[Segment], float]] = [
    (
        "cmd",
        [("telegram-exporter", BIN, True), (" discover", STEP["discover"], True)],
        0,
    ),
    (
        "out",
        [
            ("Encrypted key: ", DIM, False),
            ("~/Library/Group Containers/…/stable/.tempkeyEncrypted", OUT, False),
        ],
        0,
    ),
    ("out", [("Account 1: ", DIM, False), ("account-123456", OUT, False)], 0),
    (
        "cmd",
        [
            ("telegram-exporter", BIN, True),
            (" decrypt", STEP["decrypt"], True),
            (" --key ", FLAG, False),
            ('"$STABLE/.tempkeyEncrypted"', ARG, False),
            (" \\", FLAG, False),
        ],
        GAP,
    ),
    (
        "cont",
        [
            ("  --db ", FLAG, False),
            ('"$STABLE/account-123456/postbox/db/db_sqlite"', ARG, False),
            (" \\", FLAG, False),
        ],
        0,
    ),
    ("cont", [("  --out ", FLAG, False), ("recovery/plaintext.db", ARG, False)], 0),
    (
        "out",
        [("Decrypted DB written to recovery/plaintext.db (48.21 MB)", BRIGHT, False)],
        0,
    ),
    (
        "cmd",
        [
            ("telegram-exporter", BIN, True),
            (" list-peers", STEP["list-peers"], True),
            (" --db ", FLAG, False),
            ("recovery/plaintext.db", ARG, False),
            (" --search ", FLAG, False),
            ("Alex", ARG, False),
        ],
        GAP,
    ),
    ("out", [("Possible peers:", DIM, False)], 0),
    (
        "out",
        [
            ("  123456789", "#FBBF24", False),
            ("  Alex Example", BRIGHT, False),
            ("  (table=t2)", "#56627C", False),
        ],
        0,
    ),
    (
        "cmd",
        [
            ("telegram-exporter", BIN, True),
            (" export", STEP["export"], True),
            (" --db ", FLAG, False),
            ("recovery/plaintext.db", ARG, False),
            (" --peer-id ", FLAG, False),
            ("123456789", ARG, False),
            (" \\", FLAG, False),
        ],
        GAP,
    ),
    (
        "cont",
        [
            ("  --format ", FLAG, False),
            ("html", ARG, False),
            (" --out ", FLAG, False),
            ("recovery/alex.html", ARG, False),
        ],
        0,
    ),
    ("out", [("Exported 418 messages to recovery/alex.html", BRIGHT, False)], 0),
]


def pct(seconds: float) -> str:
    return f"{min(max(seconds / LOOP_S * 100, 0), 100):.3f}%"


def text_element(x: float, y: float, segments: list[Segment], cls: str = "") -> str:
    bold_attr = ' font-weight="700"'
    spans = "".join(
        f'<tspan fill="{colour}"{bold_attr if bold else ""}>'
        f"{escape(text, quote=False)}</tspan>"
        for text, colour, bold in segments
    )
    classes = f"mono {cls}".strip()
    return (
        f'<text class="{classes}" x="{x:.2f}" y="{y:.2f}" font-size="{FONT_SIZE}" '
        f'xml:space="preserve">{spans}</text>'
    )


def chevron(x: float, y: float, cls: str = "") -> str:
    # Drawn, so the prompt never depends on a font having U+276F.
    attr = f' class="{cls}"' if cls else ""
    return (
        f'<path{attr} d="M{x + 0.5:.2f} {y - 8.4:.2f}l4.2 4.2-4.2 4.2" fill="none" '
        'stroke="#34D399" stroke-width="1.9" stroke-linecap="round" '
        'stroke-linejoin="round" />'
    )


def appear(name: str, at: float) -> str:
    return (
        f".{name}{{animation:{name} {LOOP_S}s infinite}}"
        f"@keyframes {name}{{0%{{opacity:0;animation-timing-function:step-end}}"
        f"{pct(at)}{{opacity:1}}100%{{opacity:1}}}}"
    )


def typed(index: int, x: float, y: float, chars: int, start: float) -> tuple[str, str]:
    """Return CSS and elements that type `chars` characters from `start`."""
    width = chars * CHAR_W
    end = start + chars / TYPING_CPS
    shift = f"translateX({width:.2f}px)"
    # A background-coloured cover slides right one character at a time. At rest
    # (no animation) it sits beyond the text, so the line stays readable.
    css = [
        f".cv{index}{{transform:{shift};animation:cv{index} {LOOP_S}s infinite}}"
        f"@keyframes cv{index}{{0%{{transform:translateX(0);"
        "animation-timing-function:step-end}"
        f"{pct(start)}{{transform:translateX(0);"
        f"animation-timing-function:steps({chars},end)}}"
        f"{pct(end)}{{transform:{shift}}}100%{{transform:{shift}}}}}",
        f".cu{index}{{opacity:0;animation:cu{index} {LOOP_S}s infinite}}"
        f"@keyframes cu{index}{{0%{{opacity:0;transform:translateX(0);"
        "animation-timing-function:step-end}"
        f"{pct(start)}{{opacity:1;transform:translateX(0);"
        f"animation-timing-function:steps({chars},end)}}"
        f"{pct(end)}{{opacity:1;transform:{shift};animation-timing-function:step-end}}"
        f"{pct(end + 0.12)}{{opacity:0;transform:{shift}}}"
        f"100%{{opacity:0;transform:{shift}}}}}",
    ]
    elements = [
        f'<rect class="cv{index}" x="{x:.2f}" y="{y - 12:.2f}" '
        f'width="{width + CHAR_W:.2f}" height="{LINE_H:.2f}" fill="{TERMINAL_BG}" />',
        f'<rect class="cu{index}" x="{x:.2f}" y="{y - 10.5:.2f}" '
        f'width="{CHAR_W:.2f}" height="13.5" rx="1" fill="{BRIGHT}" '
        'fill-opacity="0.85" />',
    ]
    return "".join(css), "".join(elements)


def build_session() -> tuple[str, str]:
    css: list[str] = []
    elements: list[str] = []
    clock = 0.6
    y = Y0
    for index, (kind, segments, gap) in enumerate(SESSION, start=1):
        y += gap
        chars = sum(len(text) for text, _, _ in segments)
        if kind == "out":
            clock += 0.22
            css.append(appear(f"ou{index}", clock))
            elements.append(text_element(X0, y, segments, f"ou{index}"))
            clock += 0.05
        else:
            if kind == "cmd":
                clock += 0.45 if index > 1 else 0
                x = X0 + PROMPT_W
                css.append(appear(f"pr{index}", clock - 0.35))
                elements.append(chevron(X0, y, f"pr{index}"))
            else:
                clock += 0.12
                x = X0
            elements.append(text_element(x, y, segments))
            line_css, line_elements = typed(index, x, y, chars, clock)
            css.append(line_css)
            elements.append(line_elements)
            clock += chars / TYPING_CPS
        y += LINE_H

    y += GAP
    clock += 0.45
    if clock > LOOP_S * 0.8:
        raise SystemExit(f"session runs to {clock:.2f}s; lengthen LOOP_S")
    css.append(appear("fin", clock))
    css.append(
        ".blink{animation:blink 1.06s step-end infinite}"
        "@keyframes blink{0%{opacity:1}50%{opacity:0}100%{opacity:1}}"
        f".screen{{animation:screen {LOOP_S}s infinite}}"
        "@keyframes screen{0%{opacity:1}95.5%{opacity:1}98.5%{opacity:0}"
        "100%{opacity:0}}"
    )
    elements.append(
        f'<g class="fin">{chevron(X0, y)}<rect class="blink" x="{X0 + PROMPT_W:.2f}" '
        f'y="{y - 10.5:.2f}" width="{CHAR_W:.2f}" height="13.5" rx="1" '
        f'fill="{BRIGHT}" fill-opacity="0.85" /></g>'
    )
    return "\n      ".join(css), "\n      ".join(elements)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def font_faces(svg: str) -> str:
    """Embed one subset per font family, covering the characters in the SVG."""
    chars: dict[str, set[str]] = {"sans": set(), "mono": set()}
    for cls, body in re.findall(
        r'<text class="(sans|mono)[^"]*"[^>]*>(.*?)</text>', svg, re.S
    ):
        plain = re.sub(r"<[^>]+>", "", body)
        for entity, char in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
            plain = plain.replace(entity, char)
        chars[cls].update(plain)

    faces = []
    for family, local, weights, cls in (
        ("Inter", "Hero Sans", "400;600;700;800", "sans"),
        ("JetBrains Mono", "Hero Mono", "400;700", "mono"),
    ):
        query = urllib.parse.urlencode(
            {
                "family": f"{family}:wght@{weights}",
                "text": "".join(sorted(chars[cls])),
                "display": "block",
            }
        )
        css = fetch(f"https://fonts.googleapis.com/css2?{query}").decode()
        # Google serves one variable file for every weight; embed it once.
        by_url: dict[str, list[int]] = {}
        for weight, url in re.findall(
            r"font-weight:\s*(\d+);.*?src:\s*url\(([^)]+)\)", css, re.S
        ):
            by_url.setdefault(url, []).append(int(weight))
        for url, found in by_url.items():
            data = base64.b64encode(fetch(url)).decode()
            weight = f"{min(found)} {max(found)}"
            faces.append(
                f"@font-face{{font-family:'{local}';font-weight:{weight};"
                f"font-style:normal;src:url(data:font/woff2;base64,{data}) "
                "format('woff2');}"
            )
    return "\n      ".join(faces)


def main() -> None:
    session_css, session_elements = build_session()
    svg = TEMPLATE.read_text(encoding="utf-8")
    svg = svg.replace("__SESSION_CSS__", session_css)
    svg = svg.replace("__SESSION__", session_elements)
    svg = svg.replace("__FONT_FACES__", font_faces(svg))
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(svg) // 1024} KiB)")


if __name__ == "__main__":
    main()
