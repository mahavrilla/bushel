"""Pure, dependency-free normalization of ingredient names for dedup lookups."""

import re

_APOS = re.compile(r"['']")
_PUNCT = re.compile(r"[^a-z0-9\s]")


def _singularize(word: str) -> str:
    """Crude English singularizer — enough for ingredient names."""
    # Latin/Greek and other stems that look plural but are singular.
    if word.endswith(("us", "is", "ss")):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ses", "xes", "zes")):
        return word[:-2]
    if word.endswith("oes") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and len(word) > 1:
        return word[:-1]
    return word


def normalize_name(raw: str) -> str:
    """Lowercase, drop apostrophes, strip punctuation, collapse whitespace, singularize."""
    if not raw:
        return ""
    text = raw.lower()
    text = _APOS.sub("", text)
    text = _PUNCT.sub(" ", text)
    return " ".join(_singularize(w) for w in text.split() if len(w) > 1)
