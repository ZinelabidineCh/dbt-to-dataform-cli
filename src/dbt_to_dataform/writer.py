"""Filesystem helpers for writing the generated Dataform project."""

from __future__ import annotations

from pathlib import Path


def write_text(path: Path, content: str) -> None:
    # Path.write_text()'s `newline` kwarg only exists from Python 3.10+;
    # this project supports 3.9, so go through open() directly instead.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(content)
