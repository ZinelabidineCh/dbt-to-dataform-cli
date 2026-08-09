"""Shared warning type used by every converter to flag things that need a
manual review pass instead of being silently dropped or guessed at."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConversionWarning:
    message: str
    snippet: str = ""
