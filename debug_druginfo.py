import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from app.config import DB_PATH
from app.services.resolver_service import build_fuzzy_index, resolve_to_rxcui

build_fuzzy_index()
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Step 1: what does dolo 650 resolve to?
rxcuis = resolve_to_rxcui("dolo 650")
print(f"dolo 650 RXCUIs: {rxcuis}")

# Step 2: what profile exists for those RXCUIs?
for rxcui in rxcuis:
    row = conn.execute("SELECT name, rxcui FROM drug_profiles WHERE rxcui=? LIMIT 1", (rxcui,)).fetchone()
    print(f"  Profile for rxcui {rxcui}: {dict(row) if row else 'NOT FOUND'}")

# Step 3: check what paracetamol RXCUI is in drug_profiles
rows = conn.execute("SELECT name, rxcui FROM drug_profiles WHERE name LIKE '%paracetamol%' LIMIT 5").fetchall()
print(f"\nParacetamol profiles: {[dict(r) for r in rows]}")

# Step 4: what RXCUI does paracetamol alias map to?
rows = conn.execute("SELECT alias, rxcui FROM drug_alias WHERE alias='paracetamol' LIMIT 3").fetchall()
print(f"paracetamol alias: {[dict(r) for r in rows]}")
