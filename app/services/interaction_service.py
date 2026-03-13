"""
Interaction engine — strictly deterministic.

RXCUI resolution strategy:
  1. Resolver → RXCUIs (handles brands, combos, fuzzy)
  2. drug_alias exact lookup for the drug name
  3. Profile RXCUI — looked up directly from drug_profiles table by name
     This is the key fix: interactions are stored under the canonical
     profile RXCUI (e.g. paracetamol=161), not product RXCUIs.
"""
import logging
from app.db.database import get_db
from app.db.queries import query_interaction, query_drug_profile_by_rxcui
from app.services.resolver_service import resolve_to_rxcui
from app.utils.text_utils import normalise

log = logging.getLogger(__name__)

SEVERITY_RANK = {"HIGH": 3, "MODERATE": 2, "LOW": 1, "UNKNOWN": 0}


def _rank(severity: str) -> int:
    return SEVERITY_RANK.get(severity, 0)


def _get_profile_rxcui(name: str) -> str | None:
    """
    Look up the canonical profile RXCUI directly from drug_profiles.
    This is the RXCUI that the interactions table uses.
    e.g. 'paracetamol' → '161', 'acetaminophen' → '2734621'
    """
    db = get_db()
    # Try exact name first
    row = db.execute(
        "SELECT rxcui FROM drug_profiles WHERE LOWER(name)=LOWER(?) AND rxcui IS NOT NULL LIMIT 1",
        (name,)
    ).fetchone()
    if row:
        return row["rxcui"]
    # Try LIKE match
    row = db.execute(
        "SELECT rxcui FROM drug_profiles WHERE LOWER(name) LIKE LOWER(?) AND rxcui IS NOT NULL LIMIT 1",
        (f"%{name}%",)
    ).fetchone()
    return row["rxcui"] if row else None


def _get_all_rxcuis(drug: str) -> list[str]:
    """
    Returns all RXCUIs for a drug, prioritising canonical profile RXCUIs.
    Fast — no recursive alias walking.
    """
    name = drug.strip().lower()
    norm = normalise(name)
    db   = get_db()
    results = []

    def _add(rxcui: str):
        if rxcui and rxcui not in results:
            results.append(rxcui)

    # 1. Resolver result (handles brands, combos, fuzzy)
    for rxcui in resolve_to_rxcui(drug):
        _add(rxcui)

    # 2. drug_alias exact lookup
    for lookup in set([name, norm]):
        if not lookup:
            continue
        rows = db.execute(
            "SELECT DISTINCT rxcui FROM drug_alias WHERE alias=? LIMIT 10", (lookup,)
        ).fetchall()
        for r in rows:
            _add(r["rxcui"])

    # 3. Profile RXCUI for the input name directly
    profile_rxcui = _get_profile_rxcui(name)
    if profile_rxcui:
        _add(profile_rxcui)

    # 4. For brand names: resolve to generic name via drug_alias,
    #    then get THAT generic's profile RXCUI
    # e.g. dolo 650 → alias lookup → 'paracetamol' → profile rxcui 161
    for rxcui in list(results[:5]):   # only first 5 to stay fast
        alias_rows = db.execute(
            "SELECT DISTINCT alias FROM drug_alias WHERE rxcui=? LIMIT 5", (rxcui,)
        ).fetchall()
        for ar in alias_rows:
            alias = ar["alias"]
            if len(alias) > 3 and " " not in alias:   # only simple generic names
                p_rxcui = _get_profile_rxcui(alias)
                if p_rxcui:
                    _add(p_rxcui)

    return results


def check_interaction(drug1: str, drug2: str) -> dict:
    rxcuis1 = _get_all_rxcuis(drug1)
    rxcuis2 = _get_all_rxcuis(drug2)

    resolved1 = _get_display_name(rxcuis1, drug1)
    resolved2 = _get_display_name(rxcuis2, drug2)

    if not rxcuis1 or not rxcuis2:
        return {
            "resolved1": resolved1,
            "resolved2": resolved2,
            "severity": "NOT_FOUND",
            "description": _not_found_msg(rxcuis1, drug1, rxcuis2, drug2),
            "source": None,
            "rxcuis1": rxcuis1,
            "rxcuis2": rxcuis2,
        }

    # Check all pairs — take worst severity, early exit on HIGH
    best: dict | None = None
    for r1 in rxcuis1:
        for r2 in rxcuis2:
            row = query_interaction(r1, r2)
            if row and _rank(row["severity"]) > _rank((best or {}).get("severity", "")):
                best = row
            if best and best["severity"] == "HIGH":
                break
        if best and best["severity"] == "HIGH":
            break

    if best:
        return {
            "resolved1": resolved1,
            "resolved2": resolved2,
            "severity": best["severity"],
            "description": best.get("description"),
            "source": best.get("source", "database"),
            "rxcuis1": rxcuis1,
            "rxcuis2": rxcuis2,
        }

    return {
        "resolved1": resolved1,
        "resolved2": resolved2,
        "severity": "UNKNOWN",
        "description": None,
        "source": None,
        "rxcuis1": rxcuis1,
        "rxcuis2": rxcuis2,
    }


def _get_display_name(rxcuis: list[str], fallback: str) -> str | None:
    if not rxcuis:
        return None
    for rxcui in rxcuis[:5]:
        profile = query_drug_profile_by_rxcui(rxcui)
        if profile:
            return profile["name"]
    return fallback


def _not_found_msg(r1, d1, r2, d2) -> str:
    if not r1 and not r2:
        return f"Could not resolve '{d1}' or '{d2}' in the drug database."
    if not r1:
        return f"Could not resolve '{d1}' in the drug database."
    return f"Could not resolve '{d2}' in the drug database."
