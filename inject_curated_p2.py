"""
Run this ONCE to inject curated clinical overrides into medisafe.db.
These are well-known interactions that DrugBank stored as UNKNOWN
but are clinically confirmed.

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

build_fuzzy_index()

CURATED = [
    # ── Warfarin interactions (anticoagulant — critical) ──────────────────────
    ("warfarin",       "aspirin",         "HIGH",     "Aspirin inhibits platelet aggregation and may displace warfarin from plasma proteins, significantly increasing bleeding risk."),
    ("warfarin",       "ibuprofen",       "HIGH",     "NSAIDs inhibit platelet function and may increase warfarin plasma levels, raising risk of serious bleeding."),
    ("warfarin",       "naproxen",        "HIGH",     "NSAIDs combined with warfarin significantly increase the risk of GI bleeding and other hemorrhagic events."),
    ("warfarin",       "ciprofloxacin",   "HIGH",     "Ciprofloxacin inhibits CYP1A2 and CYP3A4, increasing warfarin levels and risk of serious bleeding."),
    ("warfarin",       "amiodarone",      "HIGH",     "Amiodarone inhibits CYP2C9 metabolism of warfarin, potentially doubling INR and causing life-threatening bleeding."),
    ("warfarin",       "clarithromycin",  "HIGH",     "Clarithromycin inhibits CYP3A4 and CYP1A2 metabolism of warfarin, significantly increasing INR and bleeding risk."),
    ("warfarin",       "metronidazole",   "HIGH",     "Metronidazole inhibits CYP2C9 metabolism of warfarin, substantially increasing INR and risk of serious bleeding."),
    ("warfarin",       "fluconazole",     "HIGH",     "Fluconazole strongly inhibits CYP2C9, dramatically increasing warfarin levels and bleeding risk."),
    ("warfarin",       "trimethoprim",    "HIGH",     "Trimethoprim inhibits CYP2C9 metabolism of warfarin and may displace it from plasma proteins, increasing bleeding risk."),
    ("warfarin",       "amoxicillin",     "MODERATE", "Amoxicillin disrupts gut flora reducing vitamin K production, potentially enhancing warfarin's anticoagulant effect and increasing bleeding risk."),
    ("warfarin",       "methotrexate",    "HIGH",     "Methotrexate combined with warfarin increases bleeding risk and methotrexate toxicity."),
    # ── Statin interactions (CYP3A4) ─────────────────────────────────────────
    ("atorvastatin",   "clarithromycin",  "HIGH",     "Clarithromycin inhibits CYP3A4, dramatically increasing atorvastatin plasma levels and risk of myopathy and rhabdomyolysis."),
    ("simvastatin",    "clarithromycin",  "HIGH",     "Clarithromycin inhibits CYP3A4 metabolism of simvastatin, raising risk of severe myopathy and rhabdomyolysis."),
    ("atorvastatin",   "grapefruit",      "MODERATE", "Grapefruit inhibits CYP3A4, increasing atorvastatin plasma levels and risk of myopathy."),
    ("simvastatin",    "amlodipine",      "MODERATE", "Amlodipine inhibits CYP3A4 metabolism of simvastatin, increasing statin levels and risk of myopathy."),
    # ── Metformin interactions ────────────────────────────────────────────────
    ("metformin",      "alcohol",         "HIGH",     "Combining metformin with alcohol significantly increases the risk of lactic acidosis, a rare but potentially fatal complication."),
    ("metformin",      "ibuprofen",       "MODERATE", "NSAIDs like ibuprofen reduce renal blood flow, decreasing metformin clearance and increasing risk of lactic acidosis."),
    ("metformin",      "naproxen",        "MODERATE", "NSAIDs reduce renal clearance of metformin, raising plasma levels and increasing risk of lactic acidosis."),
    # ── Serotonin syndrome risk ───────────────────────────────────────────────
    ("fluoxetine",     "tramadol",        "HIGH",     "Fluoxetine inhibits CYP2D6 metabolism of tramadol and combined serotonergic effects increase risk of serotonin syndrome."),
    ("sertraline",     "tramadol",        "HIGH",     "Sertraline combined with tramadol significantly increases risk of serotonin syndrome, a potentially life-threatening condition."),
    # ── Antiplatelet / NSAID combinations ────────────────────────────────────
    ("clopidogrel",    "omeprazole",      "MODERATE", "Omeprazole inhibits CYP2C19 which is required to activate clopidogrel, reducing its antiplatelet efficacy."),
    ("ibuprofen",      "aspirin",         "MODERATE", "Both ibuprofen and aspirin inhibit COX enzymes, increasing risk of GI bleeding and ulcers when combined."),
    # ── Paracetamol / acetaminophen ───────────────────────────────────────────
    ("paracetamol",    "alcohol",         "HIGH",     "Alcohol combined with paracetamol increases risk of severe liver toxicity, especially with chronic alcohol use or overdose."),
    ("acetaminophen",  "alcohol",         "HIGH",     "Alcohol combined with acetaminophen increases risk of severe liver toxicity via CYP2E1-mediated NAPQI production."),
    # ── Cardiac / electrolyte ─────────────────────────────────────────────────
    ("digoxin",        "amiodarone",      "HIGH",     "Amiodarone increases digoxin plasma levels by inhibiting P-glycoprotein, risking digoxin toxicity."),
    ("sildenafil",     "nitrates",        "HIGH",     "Combined use causes severe hypotension due to synergistic vasodilation effects. Contraindicated."),
    ("lithium",        "ibuprofen",       "HIGH",     "NSAIDs reduce renal lithium clearance, leading to lithium toxicity."),
    ("lithium",        "naproxen",        "HIGH",     "NSAIDs reduce renal lithium clearance, leading to lithium toxicity with symptoms including tremor, confusion, and cardiac arrhythmia."),
]


def get_primary_rxcui(drug: str) -> str | None:
    rxcuis = resolve_to_rxcui(drug)
    return rxcuis[0] if rxcuis else None


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")

inserted = 0
updated  = 0
skipped  = 0

print("Injecting curated overrides...\n")

for drug_a, drug_b, severity, description in CURATED:
    ra = get_primary_rxcui(drug_a)
    rb = get_primary_rxcui(drug_b)

    if not ra or not rb:
        print(f"  SKIP (unresolved): {drug_a} + {drug_b} -> ra={ra}, rb={rb}")
        skipped += 1
        continue

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
        print(f"  UPDATED [{existing['severity']} -> {severity}]: {drug_a} + {drug_b}")
        updated += 1
    else:
        conn.execute(
            "INSERT INTO interactions (rxcui_a, rxcui_b, severity, description, source) VALUES (?,?,?,?,?)",
            (ra, rb, severity, description, "curated_override")
        )
        print(f"  INSERTED [{severity}]: {drug_a} + {drug_b}")
        inserted += 1

conn.commit()
conn.close()

print(f"\nDone — {inserted} inserted, {updated} updated, {skipped} skipped")
