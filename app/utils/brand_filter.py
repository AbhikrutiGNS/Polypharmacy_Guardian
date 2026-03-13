"""
Filters garbage product descriptions out of brand_names lists.
DrugBank product names include store-brand descriptions like
"healthy accents pain relief" which are not real brand names.
"""
import re

# Common English words that appear in product descriptions but not real brand names
_JUNK_WORDS = {
    "pain", "relief", "cold", "flu", "fever", "day", "night", "time",
    "severe", "extra", "strength", "children", "childrens", "infant",
    "infants", "adult", "adults", "health", "healthy", "accents",
    "parents", "choice", "equaline", "daytime", "nighttime", "sinus",
    "pressure", "medication", "multi", "symptom", "regular", "maximum",
    "formula", "original", "advanced", "rapid", "instant", "fast",
    "acting", "release", "coated", "generic", "store", "brand",
    "complete", "total", "plus", "care", "wellness", "family",
}

_MAX_WORDS = 3       # real brand names are rarely more than 3 words
_MIN_LEN   = 2       # skip single-char entries
_MAX_LEN   = 30      # skip very long descriptions


def is_real_brand_name(name: str) -> bool:
    """Returns True if name looks like a real brand name."""
    if not name or not isinstance(name, str):
        return False

    name = name.strip()

    if len(name) < _MIN_LEN or len(name) > _MAX_LEN:
        return False

    # Skip if too many words (product descriptions are long)
    words = name.lower().split()
    if len(words) > _MAX_WORDS:
        return False

    # Skip if majority of words are junk English words
    junk_count = sum(1 for w in words if w in _JUNK_WORDS)
    if junk_count >= len(words):
        return False

    # Skip pure numeric or dosage strings
    if re.match(r'^[\d\s\.\-mgmcg%]+$', name, re.I):
        return False

    return True


def filter_brand_names(names: list[str]) -> list[str]:
    """Filter a list of brand names, keeping only real ones."""
    return [n for n in names if is_real_brand_name(n)]
