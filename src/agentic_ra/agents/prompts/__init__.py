"""Plain-markdown prompt template loader. Templates live as .md files
beside this module so prompts are diffable and reviewable on their own."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> str:
    path = _DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt template not found: {name}")
    return path.read_text(encoding="utf-8").strip()
