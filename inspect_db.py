import sqlite3
import sys
sys.path.insert(0, '.') 
from dotenv import load_dotenv
load_dotenv()

from app.config import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("=" * 60)
print("TABLE ROW COUNTS")
print("=" * 60)
for t in ['drug_alias', 'brand_resolver', 'drug_profiles', 'interactions', 'rag_chunks']:
    n = conn.execute(f"SELECT COUNT(*) as cnt FROM {t}").fetchone()['cnt']
    print(f"  {t:25s}: {n:>12,}")

print("\n" + "=" * 60)
print("BRAND_RESOLVER — region breakdown")
print("=" * 60)
rows = conn.execute("SELECT region, COUNT(*) as cnt FROM brand_resolver GROUP BY region ORDER BY cnt DESC").fetchall()
for r in rows:
    print(f"  region={r['region']:10s}: {r['cnt']:,}")

print("\n" + "=" * 60)
print("BRAND_RESOLVER — sample IN brands")
print("=" * 60)
rows = conn.execute("SELECT input_name, rxcui, region FROM brand_resolver WHERE region='IN' LIMIT 20").fetchall()
for r in rows: print(f"  {dict(r)}")

print("\n" + "=" * 60)
print("BRAND_RESOLVER — dolo / crocin / paracetamol")
print("=" * 60)
for term in ['dolo', 'crocin', 'paracetamol', 'calpol', 'tylenol']:
    rows = conn.execute("SELECT input_name, rxcui, region FROM brand_resolver WHERE input_name LIKE ? LIMIT 5", (f'%{term}%',)).fetchall()
    print(f"\n  '{term}':")
    for r in rows: print(f"    {dict(r)}")

print("\n" + "=" * 60)
print("DRUG_PROFILES — paracetamol / acetaminophen")
print("=" * 60)
for term in ['paracetamol', 'acetaminophen']:
    rows = conn.execute("SELECT name, rxcui, drug_class, brand_names FROM drug_profiles WHERE name LIKE ? LIMIT 3", (f'%{term}%',)).fetchall()
    print(f"\n  '{term}':")
    for r in rows:
        d = dict(r)
        d['brand_names'] = d['brand_names'][:100] if d['brand_names'] else None
        print(f"    {d}")

print("\n" + "=" * 60)
print("DRUG_ALIAS — paracetamol")
print("=" * 60)
rows = conn.execute("SELECT alias, rxcui FROM drug_alias WHERE alias='paracetamol'").fetchall()
for r in rows: print(f"  {dict(r)}")

print("\n" + "=" * 60)
print("INTERACTIONS — severity breakdown")
print("=" * 60)
rows = conn.execute("SELECT severity, COUNT(*) as cnt FROM interactions GROUP BY severity ORDER BY cnt DESC").fetchall()
for r in rows: print(f"  {dict(r)}")

conn.close()
