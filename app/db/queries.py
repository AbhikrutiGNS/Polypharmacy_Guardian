"""
All raw SQL queries. No business logic here.
"""
from app.db.database import get_db


# ── Resolver queries ──────────────────────────────────────────────────────────

def query_alias(alias: str) -> str | None:
    row = get_db().execute(
        "SELECT rxcui FROM drug_alias WHERE alias=? LIMIT 1", (alias,)
    ).fetchone()
    return row["rxcui"] if row else None


def query_brand_resolver(input_name: str) -> str | None:
    row = get_db().execute(
        "SELECT rxcui FROM brand_resolver WHERE input_name=? LIMIT 1", (input_name,)
    ).fetchone()
    return row["rxcui"] if row else None


def query_all_brand_keys() -> list[str]:
    rows = get_db().execute("SELECT input_name FROM brand_resolver").fetchall()
    return [r["input_name"] for r in rows]


# ── Interaction queries ───────────────────────────────────────────────────────

def query_interaction(rxcui_a: str, rxcui_b: str) -> dict | None:
    row = get_db().execute(
        """
        SELECT severity, description, source
        FROM interactions
        WHERE (rxcui_a=? AND rxcui_b=?) OR (rxcui_a=? AND rxcui_b=?)
        LIMIT 1
        """,
        (rxcui_a, rxcui_b, rxcui_b, rxcui_a),
    ).fetchone()
    return dict(row) if row else None


# ── Drug profile queries ──────────────────────────────────────────────────────

def query_drug_profile_by_name(name: str) -> dict | None:
    row = get_db().execute(
        """
        SELECT name, rxcui, drug_class, description, indication,
               mechanism, side_effects, pharmacology, dosage, brand_names
        FROM drug_profiles
        WHERE LOWER(name)=LOWER(?)
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    return dict(row) if row else None


def query_drug_profile_by_rxcui(rxcui: str) -> dict | None:
    row = get_db().execute(
        """
        SELECT name, rxcui, drug_class, description, indication,
               mechanism, side_effects, pharmacology, dosage, brand_names
        FROM drug_profiles
        WHERE rxcui=?
        LIMIT 1
        """,
        (rxcui,),
    ).fetchone()
    return dict(row) if row else None


def query_drug_profile_fuzzy(name: str) -> dict | None:
    row = get_db().execute(
        """
        SELECT name, rxcui, drug_class, description, indication,
               mechanism, side_effects, pharmacology, dosage, brand_names
        FROM drug_profiles
        WHERE LOWER(name) LIKE LOWER(?)
        LIMIT 1
        """,
        (f"%{name}%",),
    ).fetchone()
    return dict(row) if row else None


# ── RAG queries ───────────────────────────────────────────────────────────────

def query_rag_chunks(drug1_rxcui: str, drug2_rxcui: str, limit: int = 6) -> list[str]:
    rows = get_db().execute(
        """
        SELECT chunk_text FROM rag_chunks
        WHERE rxcui IN (?, ?)
        ORDER BY topic DESC
        LIMIT ?
        """,
        (drug1_rxcui, drug2_rxcui, limit),
    ).fetchall()
    return [r["chunk_text"] for r in rows]


def query_rag_chunks_by_name(drug1: str, drug2: str, limit: int = 6) -> list[str]:
    rows = get_db().execute(
        """
        SELECT chunk_text FROM rag_chunks
        WHERE LOWER(drug_name) LIKE LOWER(?)
           OR LOWER(drug_name) LIKE LOWER(?)
        ORDER BY topic DESC
        LIMIT ?
        """,
        (f"%{drug1}%", f"%{drug2}%", limit),
    ).fetchall()
    return [r["chunk_text"] for r in rows]
