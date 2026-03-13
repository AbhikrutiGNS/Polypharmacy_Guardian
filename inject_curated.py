"""
Run this ONCE to inject curated clinical overrides into medisafe.db.
These are well-known interactions that DrugBank stored as UNKNOWN
but are clinically confirmed as HIGH or MODERATE severity.

Usage:
    python inject_curated.py
"""
import sqlite3
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from app.config import DB_PATH
from app.services.resolver_service import build_fuzzy_index, resolve_to_rxcui
from app.utils.text_utils import normalise

build_fuzzy_index()

# (drug_a, drug_b, severity, description)
CURATED = [
    ("warfarin",      "aspirin",         "HIGH",     "Aspirin inhibits platelet aggregation and may displace warfarin from plasma proteins, significantly increasing bleeding risk."),
    ("warfarin",      "ibuprofen",       "HIGH",     "NSAIDs inhibit platelet function and may increase warfarin plasma levels, raising risk of serious bleeding."),
    ("warfarin",      "naproxen",        "HIGH",     "NSAIDs combined with warfarin significantly increase the risk of GI bleeding and other hemorrhagic events."),
    ("metformin",     "alcohol",         "HIGH",     "Alcohol increases the risk of lactic acidosis in patients taking metformin, a potentially fatal complication."),
    ("atorvastatin",  "clarithromycin",  "HIGH",     "Clarithromycin inhibits CYP3A4, dramatically increasing atorvastatin plasma levels and risk of myopathy and rhabdomyolysis."),
    ("simvastatin",   "clarithromycin",  "HIGH",     "Clarithromycin inhibits CYP3A4 metabolism of simvastatin, raising risk of severe myopathy and rhabdomyolysis."),
    ("clopidogrel",   "omeprazole",      "MODERATE", "Omeprazole inhibits CYP2C19 which is required to activate clopidogrel, reducing its antiplatelet efficacy."),
    ("ssri",          "tramadol",        "HIGH",     "Combining SSRIs with tramadol increases risk of serotonin syndrome, a potentially life-threatening condition."),
    ("fluoxetine",    "tramadol",        "HIGH",     "Fluoxetine inhibits CYP2D6 metabolism of tramadol and combined serotonergic effects increase risk of serotonin syndrome."),
    ("ciprofloxacin", "warfarin",        "HIGH",     "Ciprofloxacin inhibits CYP1A2 and CYP3A4, increasing warfarin levels and risk of serious bleeding."),
    ("amiodarone",    "warfarin",        "HIGH",     "Amiodarone inhibits CYP2C9 metabolism of warfarin, potentially doubling INR and causing life-threatening bleeding."),
    ("methotrexate",  "aspirin",         "HIGH",     "Aspirin reduces renal clearance of methotrexate, increasing its toxicity risk significantly."),
    ("lithium",       "ibuprofen",       "HIGH",     "NSAIDs reduce renal lithium clearance, leading to lithium toxicity."),
    ("digoxin",       "amiodarone",      "HIGH",     "Amiodarone increases digoxin plasma levels by inhibiting P-glycoprotein, risking digoxin toxicity."),
    ("sildenafil",    "nitrates",        "HIGH",     "Combined use causes severe hypotension due to synergistic vasodilation effects. Contraindicated."),
]


def get_primary_rxcui(drug: str) -> str | None:
    rxcuis = resolve_to_rxcui(drug)
    return rxcuis[0] if rxcuis else None


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")

inserted = 0
updated = 0
skipped = 0

print("Injecting curated overrides...\n")

for drug_a, drug_b, severity, description in CURATED:
    ra = get_primary_rxcui(drug_a)
    rb = get_primary_rxcui(drug_b)

    if not ra or not rb:
        print(f"  SKIP (unresolved): {drug_a} + {drug_b} → ra={ra}, rb={rb}")
        skipped += 1
        continue

    # Always store with smaller RXCUI first (consistent with pipeline)
    if ra > rb:
        ra, rb = rb, ra

    existing = conn.execute(
        "SELECT id, severity FROM interactions WHERE rxcui_a=? AND rxcui_b=?",
        (ra, rb)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE interactions SET severity=?, description=?, source=? WHERE rxcui_a=? AND rxcui_b=?",
            (severity, description, "curated_override", ra, rb)
        )
        print(f"  UPDATED [{existing['severity']} → {severity}]: {drug_a} + {drug_b} ({ra}, {rb})")
        updated += 1
    else:
        conn.execute(
            "INSERT INTO interactions (rxcui_a, rxcui_b, severity, description, source) VALUES (?,?,?,?,?)",
            (ra, rb, severity, description, "curated_override")
        )
        print(f"  INSERTED [{severity}]: {drug_a} + {drug_b} ({ra}, {rb})")
        inserted += 1

conn.commit()
conn.close()

print(f"\nDone — {inserted} inserted, {updated} updated, {skipped} skipped")
