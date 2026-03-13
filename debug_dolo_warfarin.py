import sqlite3
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from app.config import DB_PATH
from app.services.resolver_service import build_fuzzy_index, resolve_to_rxcui
from app.services.interaction_service import _get_all_rxcuis
from app.utils.text_utils import normalise

build_fuzzy_index()
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# What does dolo 650 resolve to?
r1 = _get_all_rxcuis("dolo 650")
r2 = _get_all_rxcuis("warfarin")
print(f"dolo 650 ALL RXCUIs ({len(r1)}): {r1[:10]}")
print(f"warfarin ALL RXCUIs ({len(r2)}): {r2[:5]}")

# Does any pair have a hit?
print("\n--- Checking all pairs ---")
found = False
for a in r1:
    for b in r2:
        row = conn.execute(
            "SELECT rxcui_a, rxcui_b, severity, source FROM interactions WHERE (rxcui_a=? AND rxcui_b=?) OR (rxcui_a=? AND rxcui_b=?) LIMIT 1",
            (a, b, b, a)
        ).fetchone()
        if row:
            print(f"FOUND: ({a}, {b}) -> {dict(row)}")
            found = True
            break
    if found:
        break

if not found:
    print("NOT FOUND for any pair")

# What RXCUI is paracetamol under in interactions table?
print("\n--- paracetamol/acetaminophen in interactions ---")
for name in ['paracetamol', 'acetaminophen']:
    rxcuis = resolve_to_rxcui(name)
    print(f"\n{name} resolves to: {rxcuis[:5]}")
    for rxcui in rxcuis[:5]:
        cnt = conn.execute(
            "SELECT COUNT(*) as cnt FROM interactions WHERE rxcui_a=? OR rxcui_b=?",
            (rxcui, rxcui)
        ).fetchone()['cnt']
        if cnt > 0:
            print(f"  rxcui {rxcui}: {cnt} interactions in DB")

# Check the known dolo+warfarin interaction from notebook (LOW)
print("\n--- Direct RXCUI lookup: paracetamol(161) + warfarin(11289) ---")
row = conn.execute(
    "SELECT * FROM interactions WHERE (rxcui_a='161' AND rxcui_b='11289') OR (rxcui_a='11289' AND rxcui_b='161')"
).fetchone()
print(dict(row) if row else "NOT FOUND")
