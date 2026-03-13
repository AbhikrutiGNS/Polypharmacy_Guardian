import sqlite3
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from app.config import DB_PATH
from app.services.resolver_service import build_fuzzy_index
from app.services.interaction_service import _get_all_rxcuis

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

build_fuzzy_index()

r1 = _get_all_rxcuis("warfarin")
r2 = _get_all_rxcuis("aspirin")

print(f"warfarin  ALL RXCUIs ({len(r1)}): {r1}")
print(f"aspirin   ALL RXCUIs ({len(r2)}): {r2}")

# Check every combination
print("\n--- Checking all RXCUI pairs ---")
found = False
for a in r1:
    for b in r2:
        row = conn.execute(
            "SELECT rxcui_a, rxcui_b, severity FROM interactions WHERE (rxcui_a=? AND rxcui_b=?) OR (rxcui_a=? AND rxcui_b=?) LIMIT 1",
            (a, b, b, a)
        ).fetchone()
        if row:
            print(f"FOUND: ({a}, {b}) -> {dict(row)}")
            found = True

if not found:
    print("No interaction found for any pair.")

# Show what interactions exist for warfarin RXCUIs
print(f"\n--- All interactions involving warfarin RXCUIs ---")
for rxcui in r1[:5]:
    rows = conn.execute(
        "SELECT rxcui_a, rxcui_b, severity FROM interactions WHERE rxcui_a=? OR rxcui_b=? LIMIT 3",
        (rxcui, rxcui)
    ).fetchall()
    if rows:
        print(f"  rxcui {rxcui}: {[dict(r) for r in rows]}")

# Check if aspirin RXCUI 1191 is in interactions at all
print("\n--- Does rxcui 1191 (aspirin) appear in interactions? ---")
row = conn.execute(
    "SELECT COUNT(*) as cnt FROM interactions WHERE rxcui_a='1191' OR rxcui_b='1191'"
).fetchone()
print(f"  Count: {row['cnt']}")

# Check warfarin 11289 specifically with aspirin 1191
print("\n--- Direct check: 11289 vs 1191 ---")
row = conn.execute(
    "SELECT * FROM interactions WHERE (rxcui_a='11289' AND rxcui_b='1191') OR (rxcui_a='1191' AND rxcui_b='11289')"
).fetchone()
print(f"  Result: {dict(row) if row else 'NOT FOUND'}")

# What are the actual aspirin RXCUIs in the interactions table?
print("\n--- RXCUIs containing 'aspirin' in drug_alias that appear in interactions ---")
aspirin_rxcuis = conn.execute(
    "SELECT DISTINCT rxcui FROM drug_alias WHERE alias LIKE '%aspirin%'"
).fetchall()
for r in aspirin_rxcuis[:20]:
    rxcui = r['rxcui']
    cnt = conn.execute(
        "SELECT COUNT(*) as cnt FROM interactions WHERE rxcui_a=? OR rxcui_b=?",
        (rxcui, rxcui)
    ).fetchone()['cnt']
    if cnt > 0:
        print(f"  rxcui {rxcui}: {cnt} interactions")
