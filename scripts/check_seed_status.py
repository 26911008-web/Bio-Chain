import asyncio
import sqlite3
from pathlib import Path

db_path = Path("biochain.db")
if not db_path.exists():
    print("Database biochain.db does not exist!")
    exit(1)

conn = sqlite3.connect("biochain.db")
cursor = conn.cursor()

print("--- USERS IN DB ---")
for row in cursor.execute("SELECT id, username, role, full_name, phone FROM users").fetchall():
    print(f"ID: {row[0]} | User: {row[1]} | Role: {row[2]} | Name: {row[3]}")

print("\n--- MASTER BIOMASS PARAMETERS ---")
try:
    for row in cursor.execute("SELECT code, name, moisture_typ_pct, bulk_density_kg_m3 FROM biomass_parameters").fetchall():
        print(f"Code: {row[0]} | Name: {row[1]} | MC: {row[2]}% | BD: {row[3]} kg/m3")
except Exception as e:
    print("Biomass parameters error:", e)

conn.close()
