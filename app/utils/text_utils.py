"""
Text normalization utilities ported directly from the pipeline notebook.
These must stay consistent with how the DB was built.
"""
import re

DOSE_PATTERN = re.compile(
    r"\b\d+\.?\d*\s*"
    r"(mg|mcg|ug|\u00b5g|g|ml|l|iu|units?|mmol|meq|%|w/v|v/v|m/m|w/w)\b",
    re.IGNORECASE,
)

FORM_WORDS = {
    "tablet", "tablets", "capsule", "capsules", "injection", "syrup",
    "suspension", "cream", "gel", "drops", "spray", "inhaler", "patch",
    "solution", "ointment", "lotion", "powder", "granules", "sachet",
    "suppository", "infusion", "softgel", "sr", "xr", "er", "mr", "od",
    "forte", "plus", "advance", "rapid", "junior", "duo", "oral", "topical",
    "extended", "release", "film", "coated", "chewable", "effervescent",
}

BRAND_SUFFIX_WORDS = {
    "plus", "ds", "sp", "forte", "max", "od", "sr", "xr", "er", "mr", "cr",
    "la", "advance", "rapid", "junior", "duo", "kid", "kids", "infant",
    "pediatric", "new", "neo", "extra", "super", "ultra", "mega", "gold",
    "silver", "lc", "ls", "dc", "fx", "px", "dx",
} | set("abcdefghijklmnopqrstuvwxyz")

BRAND_ROOT_MIN_LEN = 3


def normalise(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = DOSE_PATTERN.sub("", text)
    words = [w for w in text.split() if w not in FORM_WORDS and re.search(r"[a-z]", w)]
    return " ".join(words).strip()


def brand_root(brand_name: str) -> str | None:
    tokens = brand_name.strip().lower().split()
    if len(tokens) < 2:
        return None
    while len(tokens) > 1 and tokens[-1] in BRAND_SUFFIX_WORDS:
        tokens.pop()
    root = " ".join(tokens)
    if len(root) < BRAND_ROOT_MIN_LEN or root == brand_name.strip().lower():
        return None
    return root
