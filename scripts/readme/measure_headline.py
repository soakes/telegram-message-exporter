#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.67.0", "uharfbuzz==0.56.3"]
# ///
"""Measure Inter text advances as a browser lays them out, for build_readme_hero.py.

Shapes the text with HarfBuzz (kerning included) on Inter's variable font at the given
weight, with opsz following font-optical-sizing:auto (the px size, clamped to 14..32),
and adds CSS letter-spacing after every character. The font is the pinned Inter that
build_readme_hero.py embeds, so the advances match what the hero renders. Run it with
uv, which installs fontTools and uharfbuzz:

    uv run scripts/readme/measure_headline.py 44 800 -1.3 "Deleted" "doesn’t mean gone."

usage: measure_headline.py SIZE WEIGHT LETTER_SPACING "text" ["text" ...]
"""

from __future__ import annotations

import sys

import uharfbuzz as hb
from build_readme_hero import FAMILIES, font_source


def font_bytes() -> bytes:
    name, sha256, _, _ = FAMILIES["sans"]
    return font_source(name, sha256)


def advance(text: str, size: float, weight: float, spacing: float) -> float:
    face = hb.Face(font_bytes())
    font = hb.Font(face)
    font.set_variations({"wght": weight, "opsz": min(max(size, 14), 32)})
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True, "calt": True})
    units = sum(pos.x_advance for pos in buf.glyph_positions)
    return units * size / face.upem + spacing * len(text)


if __name__ == "__main__":
    size, weight, spacing = (float(v) for v in sys.argv[1:4])
    for text in sys.argv[4:]:
        print(f"{advance(text, size, weight, spacing):8.2f}  {text!r}")
