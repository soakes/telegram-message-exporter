#!/usr/bin/env python3
"""Bump VERSION file (patch/minor/major/custom)."""

from __future__ import annotations

import argparse
from pathlib import Path

VERSION_PATH = Path(__file__).resolve().parents[2] / "VERSION"


def parse_version(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Version must be in MAJOR.MINOR.PATCH format")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def format_version(version: tuple[int, int, int]) -> str:
    return f"{version[0]}.{version[1]}.{version[2]}"


def bump(version: tuple[int, int, int], kind: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if kind == "major":
        return major + 1, 0, 0
    if kind == "minor":
        return major, minor + 1, 0
    if kind == "patch":
        return major, minor, patch + 1
    raise ValueError("Unknown bump kind")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump VERSION file")
    parser.add_argument(
        "kind",
        nargs="?",
        choices=["patch", "minor", "major"],
        help="Bump type (patch/minor/major)",
    )
    parser.add_argument(
        "--set",
        dest="set_version",
        help="Set an explicit version (e.g. 1.2.3)",
    )
    args = parser.parse_args()

    current_raw = VERSION_PATH.read_text(encoding="utf-8").strip()
    current = parse_version(current_raw)

    if args.set_version:
        new_version = parse_version(args.set_version)
    elif args.kind:
        new_version = bump(current, args.kind)
    else:
        raise SystemExit("Provide a bump kind (patch/minor/major) or --set X.Y.Z")

    VERSION_PATH.write_text(format_version(new_version) + "\n", encoding="utf-8")
    print(f"Version updated: {current_raw} -> {format_version(new_version)}")


if __name__ == "__main__":
    main()
