#!/usr/bin/env python3
"""Convenience wrapper for running the exporter without installation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# pylint: disable=wrong-import-position
from telegram_message_exporter.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
