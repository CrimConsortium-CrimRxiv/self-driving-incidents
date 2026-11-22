"""Shared helpers: config loading, logging, text normalisation, keyword matching."""
from __future__ import annotations

import logging
import re
import string
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("sdi")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_PUNCT = re.compile(f"[{re.escape(string.punctuation)}\u2018\u2019\u201c\u201d\u2013\u2014\u2026]")


def strip_source_suffix(title: str, source: str | None = None) -> str:
    """Remove the trailing ' - Source Name' that Google News appends."""
    title = (title or "").strip()
    if source:
        for sep in (" - ", " \u2013 ", " \u2014 ", " | "):
            suffix = sep + source.strip()
            if title.endswith(suffix):
                return _drop_pipe_tail(title[: -len(suffix)].strip().rstrip("-\u2013\u2014| ").strip())
    if " - " in title and source is not None and len(title.rsplit(" - ", 1)[1]) <= 40:
        title = title.rsplit(" - ", 1)[0]
    return _drop_pipe_tail(title.strip())


def _drop_pipe_tail(title: str) -> str:
    """Drop "| Tap to know more | Inshorts"-style tails."""
    if " | " in title and len(title.split(" | ", 1)[0]) >= 30:
        title = title.split(" | ", 1)[0]
    return title.strip()


def normalize_title(title: str, source: str | None = None) -> str:
    t = strip_source_suffix(title, source).lower()
    t = _PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


_SUFFIXES = r"(?:s|es|ed|d|ing|ly|ity|ities)?"


def word_pattern(words: list[str]) -> re.Pattern:
    """Whole-word matcher that also accepts simple endings ("crashes", "crashed")."""
    parts = []
    for w in words:
        w = w.strip().lower()
        if not w:
            continue
        tokens = [re.escape(t) for t in re.split(r"[\s-]+", w) if t]
        parts.append(r"[\s-]*".join(tokens))
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(parts) + r")" + _SUFFIXES + r"(?![a-z0-9])", re.I)


def norm_for_match(text: str) -> str:
    """Lower-case, straighten quotes/dashes and collapse spaces, for checking quotations."""
    t = (text or "").lower()
    t = t.translate(str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                                   "\u2013": "-", "\u2014": "-", "\u00a0": " "}))
    t = re.sub(r"[\"'`]", "", t)
    return re.sub(r"\s+", " ", t).strip()
