"""
Drug name resolver — mirrors the notebook's resolve_to_rxcui() exactly.

Resolution priority:
  1. Combo map  (india_combos.json)  → returns list of RXCUIs for each ingredient
  2. drug_alias table               → exact & normalised
  3. brand_resolver table           → exact & normalised
  4. Fuzzy match on brand_resolver  → last resort (rapidfuzz WRatio ≥ 88)

Fuzzy index is built ONCE at startup from the brand_resolver table.
"""
import json
import logging
from functools import lru_cache
from rapidfuzz import process as rf_process, fuzz

from app.config import INDIA_COMBOS_PATH, FUZZY_CUTOFF
from app.db.queries import query_alias, query_brand_resolver, query_all_brand_keys
from app.utils.text_utils import normalise, brand_root

log = logging.getLogger(__name__)

# ── Loaded once at import time ─────────────────────────────────────────────────
def _load_combo_map() -> dict[str, list[str]]:
    try:
        with open(INDIA_COMBOS_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning("india_combos.json not found — combo resolution disabled")
        return {}

_COMBO_MAP: dict[str, list[str]] = _load_combo_map()
_FUZZY_KEYS: list[str] = []   # populated in build_fuzzy_index()


def build_fuzzy_index() -> int:
    """Call once at FastAPI startup. Loads all brand_resolver keys into RAM."""
    global _FUZZY_KEYS
    _FUZZY_KEYS = query_all_brand_keys()
    log.info(f"Fuzzy index built: {len(_FUZZY_KEYS):,} keys")
    return len(_FUZZY_KEYS)


def fuzzy_index_size() -> int:
    return len(_FUZZY_KEYS)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _alias_lookup(name: str) -> str | None:
    rxcui = query_alias(name)
    if not rxcui:
        norm = normalise(name)
        if norm and norm != name:
            rxcui = query_alias(norm)
    return rxcui


def _brand_lookup(name: str) -> str | None:
    rxcui = query_brand_resolver(name)
    if not rxcui:
        norm = normalise(name)
        if norm and norm != name:
            rxcui = query_brand_resolver(norm)
    return rxcui


def _fuzzy_lookup(name: str) -> str | None:
    if not _FUZZY_KEYS:
        return None
    match = rf_process.extractOne(
        name, _FUZZY_KEYS, scorer=fuzz.WRatio, score_cutoff=FUZZY_CUTOFF
    )
    if not match:
        return None
    best_key = match[0]
    return query_brand_resolver(best_key)


# ── Public API ─────────────────────────────────────────────────────────────────

def resolve_to_rxcui(name: str) -> list[str]:
    """
    Returns a list of RXCUIs.
    - Single-ingredient drugs  → [rxcui]
    - Combo brand (combiflam)  → [rxcui_ibuprofen, rxcui_paracetamol]
    - Not found                → []
    """
    name_lower = name.strip().lower()
    norm = normalise(name_lower)

    # 1. Combo map
    combo_key = None
    if name_lower in _COMBO_MAP:
        combo_key = name_lower
    elif norm in _COMBO_MAP:
        combo_key = norm
    else:
        root = brand_root(name_lower)
        if root and root in _COMBO_MAP:
            combo_key = root

    if combo_key:
        results = []
        for ingredient in _COMBO_MAP[combo_key]:
            rxcui = _alias_lookup(ingredient) or _brand_lookup(ingredient)
            if rxcui and rxcui not in results:
                results.append(rxcui)
        if results:
            return results

    # 2. drug_alias (exact then normalised)
    rxcui = _alias_lookup(name_lower)
    if rxcui:
        return [rxcui]

    # 3. brand_resolver (exact then normalised)
    rxcui = _brand_lookup(name_lower)
    if rxcui:
        return [rxcui]

    # 4. Fuzzy — last resort
    rxcui = _fuzzy_lookup(name_lower)
    if rxcui:
        return [rxcui]

    return []


def resolve_display_name(name: str, rxcuis: list[str]) -> str | None:
    """Return canonical drug name for display, or None if unresolved."""
    if not rxcuis:
        return None
    return rxcuis[0]   # caller can enrich via drug profile lookup
