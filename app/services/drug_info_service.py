"""
Drug info service — resolves brand/Indian name and returns full drug profile.
"""
import json
import logging
from app.services.resolver_service import resolve_to_rxcui
from app.db.database import get_db
from app.db.queries import (
    query_drug_profile_by_rxcui,
    query_drug_profile_by_name,
    query_drug_profile_fuzzy,
)
from app.utils.brand_filter import filter_brand_names

log = logging.getLogger(__name__)


def _find_profile_via_alias_walk(rxcuis: list[str]) -> dict | None:
    db = get_db()
    for rxcui in rxcuis:
        rows = db.execute(
            "SELECT alias FROM drug_alias WHERE rxcui=? LIMIT 20", (rxcui,)
        ).fetchall()
        for row in rows:
            alias = row["alias"]
            profile = query_drug_profile_by_name(alias)
            if profile:
                return profile
            alias_rxcui_rows = db.execute(
                "SELECT rxcui FROM drug_alias WHERE alias=? LIMIT 5", (alias,)
            ).fetchall()
            for ar in alias_rxcui_rows:
                profile = query_drug_profile_by_rxcui(ar["rxcui"])
                if profile:
                    return profile
    return None


def _get_all_synonyms(profile_name: str, all_rxcuis: list[str]) -> list[str]:
    """
    Get all known name synonyms for a drug by collecting aliases
    from drug_alias table for all known RXCUIs.
    e.g. acetaminophen → also finds 'paracetamol', 'tylenol' etc.
    """
    db = get_db()
    synonyms = set()
    synonyms.add(profile_name.lower())

    for rxcui in all_rxcuis:
        rows = db.execute(
            "SELECT DISTINCT alias FROM drug_alias WHERE rxcui=? LIMIT 30", (rxcui,)
        ).fetchall()
        for r in rows:
            if r["alias"]:
                synonyms.add(r["alias"].lower().strip())

    return list(synonyms)


def _get_brand_names(profile_name: str, all_rxcuis: list[str]) -> list[str]:
    """
    Collect brand names from brand_resolver using:
      1. All known RXCUIs for the drug
      2. All known synonyms/aliases (catches paracetamol ↔ acetaminophen gap)
    Indian brands returned first.
    """
    db = get_db()
    seen = set()
    indian = []
    us = []

    def _add(name: str, region: str):
        key = name.lower().strip()
        if key and key not in seen:
            seen.add(key)
            if region in ("IN", "INN"):
                indian.append(name)
            else:
                us.append(name)

    # Strategy 1: lookup by all known RXCUIs
    for rxcui in all_rxcuis:
        rows = db.execute(
            "SELECT input_name, region FROM brand_resolver WHERE rxcui=? LIMIT 20",
            (rxcui,)
        ).fetchall()
        for r in rows:
            _add(r["input_name"], r["region"])

    # Strategy 2: lookup by all synonyms
    # e.g. acetaminophen profile → also search brand_resolver for 'paracetamol'
    synonyms = _get_all_synonyms(profile_name, all_rxcuis)
    for synonym in synonyms:
        # Find all RXCUIs associated with this synonym in brand_resolver
        rxcui_rows = db.execute(
            "SELECT DISTINCT rxcui FROM brand_resolver WHERE input_name=?",
            (synonym,)
        ).fetchall()
        for rr in rxcui_rows:
            brand_rows = db.execute(
                "SELECT input_name, region FROM brand_resolver WHERE rxcui=? LIMIT 20",
                (rr["rxcui"],)
            ).fetchall()
            for r in brand_rows:
                _add(r["input_name"], r["region"])

    return (indian + us)[:20]


def get_drug_info(drug: str) -> dict | None:
    rxcuis = resolve_to_rxcui(drug)
    profile = None

    # 1. Direct RXCUI → profile
    if rxcuis:
        for rxcui in rxcuis:
            profile = query_drug_profile_by_rxcui(rxcui)
            if profile:
                break

    # 2. Walk alias table to find generic profile
    if not profile and rxcuis:
        profile = _find_profile_via_alias_walk(rxcuis)

    # 3. Exact name match
    if not profile:
        profile = query_drug_profile_by_name(drug.lower().strip())

    # 4. Fuzzy name match
    if not profile:
        profile = query_drug_profile_fuzzy(drug.lower().strip())

    if not profile:
        return None

    # Collect all RXCUIs
    all_rxcuis = list(rxcuis)
    profile_rxcui = profile.get("rxcui")
    if profile_rxcui and profile_rxcui not in all_rxcuis:
        all_rxcuis.insert(0, profile_rxcui)

    # Get brand names — Indian first, then US
    brand_names = _get_brand_names(profile["name"], all_rxcuis)

    # Fallback to filtered DrugBank brand_names if still empty
    if not brand_names:
        raw = profile.get("brand_names") or "[]"
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                raw = [raw]
        brand_names = filter_brand_names(raw)

    return {
        "name":         profile["name"],
        "rxcui":        profile_rxcui,
        "drug_class":   profile.get("drug_class") or None,
        "description":  profile.get("description") or None,
        "indication":   profile.get("indication") or None,
        "mechanism":    profile.get("mechanism") or None,
        "side_effects": profile.get("side_effects") or None,
        "pharmacology": profile.get("pharmacology") or None,
        "dosage":       profile.get("dosage") or None,
        "brand_names":  brand_names,
    }
