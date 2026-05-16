from __future__ import annotations

import sys


def info(message: str) -> None:
    print(f"[dzfactory] {message}")


def warn(message: str) -> None:
    print(f"[dzfactory][warn] {message}", file=sys.stderr)


def error(message: str) -> None:
    print(f"[dzfactory][error] {message}", file=sys.stderr)
