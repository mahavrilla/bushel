"""Pure, dependency-free normalization of ingredient names for dedup lookups."""

import re

_PUNCT = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")


def _singularize(word: str) -> str:
    """Crude English singularizer — enough for ingredient names."""
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("ses") or word.endswith("xes") or word.endswith("zes"):
        return word[:-2]
    if word.endswith("oes") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def normalize_name(raw: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, singularize each word."""
    text = raw.lower()
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return " ".join(_singularize(w) for w in text.split())
