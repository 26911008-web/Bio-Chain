import json
import sqlite3
from datetime import datetime, timezone

from app.params import DEFS

DEFAULT_PRICES = {
    "sekam_padi": 500.0,
    "tongkol_jagung": 450.0,
    "ampas_tebu": 300.0,
    "serbuk_sengon": 400.0,
    "tempurung_kelapa": 1800.0,
    "sabut_kelapa": 350.0,
    "serbuk_karet": 420.0,
}

print("Populating all parameters and prices in biochain.db...")
conn = sqlite3.connect("biochain.db")
cur = conn.cursor()

# 1. Update biomass_parameters base_price_per_kg
for code, price in DEFAULT_PRICES.items():
    cur.execute("UPDATE biomass_parameters SET base_price_per_kg = ? WHERE code = ?", (price, code))
    print(f"Biomass {code} -> Rp {price}/kg (rows affected: {cur.rowcount})")

# 2. Populate system_parameters
now_iso = datetime.now(timezone.utc).isoformat()
count_inserted = 0
count_updated = 0

for d in DEFS:
    val_json = json.dumps(d.default)
    cur.execute("SELECT key FROM system_parameters WHERE key = ?", (d.key,))
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE system_parameters SET value = ?, updated_at = ? WHERE key = ?", (val_json, now_iso, d.key))
        count_updated += 1
    else:
        cur.execute("INSERT INTO system_parameters (key, value, updated_at) VALUES (?, ?, ?)", (d.key, val_json, now_iso))
        count_inserted += 1

conn.commit()
print(f"system_parameters populated: {count_inserted} inserted, {count_updated} updated, total {len(DEFS)} parameters.")

# Check results
cur.execute("SELECT COUNT(*) FROM system_parameters")
print(f"Total system_parameters in DB: {cur.fetchone()[0]}")

cur.execute("SELECT code, name, base_price_per_kg FROM biomass_parameters")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} -> Rp {row[2]}/kg")

conn.close()
print("Done!")
