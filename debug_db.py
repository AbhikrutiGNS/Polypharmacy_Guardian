import sqlite3
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from app.config import DB_PATH
from app.utils.text_utils import normalise
from app.services.resolver_service import build_fuzzy_index, resolve_to_rxcui

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Step 1: build fuzzy index
build_fuzzy_index()

# Step 2: resolve both drugs
r1 = resolve_to_rxcui("warfarin")
r2 = resolve_to_rxcui("aspirin")
print(f"warfarin  RXCUIs: {r1}")
print(f"aspirin   RXCUIs: {r2}")

# Step 3: check interaction table directly
if r1 and r2:
    for a in r1:
        for b in r2:
            row = conn.execute(
                "SELECT severity, description FROM interactions WHERE (rxcui_a=? AND rxcui_b=?) OR (rxcui_a=? AND rxcui_b=?) LIMIT 1",
                (a, b, b, a)
            ).fetchone()
            print(f"DB lookup ({a}, {b}): {dict(row) if row else 'NOT FOUND'}")

# Step 4: check if warfarin exists in alias table
print("\n--- drug_alias for warfarin ---")
rows = conn.execute("SELECT alias, rxcui FROM drug_alias WHERE alias LIKE '%warfarin%' LIMIT 5").fetchall()
for r in rows:
    print(dict(r))

print("\n--- drug_alias for aspirin ---")
rows = conn.execute("SELECT alias, rxcui FROM drug_alias WHERE alias LIKE '%aspirin%' LIMIT 5").fetchall()
for r in rows:
    print(dict(r))

# Step 5: check interactions table sample for those RXCUIs
if r1:
    print(f"\n--- interactions sample for rxcui {r1[0]} ---")
    rows = conn.execute(
        "SELECT rxcui_a, rxcui_b, severity FROM interactions WHERE rxcui_a=? OR rxcui_b=? LIMIT 5",
        (r1[0], r1[0])
    ).fetchall()
    for r in rows:
        print(dict(r))
