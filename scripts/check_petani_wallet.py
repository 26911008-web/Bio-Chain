import sqlite3

conn = sqlite3.connect("biochain.db")
c = conn.cursor()
row = c.execute("SELECT id, username, full_name FROM users WHERE username = 'petani_sugeng'").fetchone()
print("Petani Sugeng:", row)
uid = row[0]

ledger = c.execute("SELECT id, delta_kg, balance_after_kg, event_type, notes FROM biochar_ledger WHERE farmer_id = ?", (uid,)).fetchall()
print("Biochar ledger:", ledger)

redemptions = c.execute("SELECT id, kg, status, pickup_point FROM biochar_redemptions WHERE farmer_id = ?", (uid,)).fetchall()
print("Redemptions:", redemptions)

requests = c.execute("SELECT id, request_code, requested_kg, status FROM biochar_requests WHERE farmer_id = ?", (uid,)).fetchall()
print("Biochar requests:", requests)

circ_requests = c.execute("SELECT id, request_code, requested_kg, status FROM biochar_circular_requests WHERE farmer_id = ?", (uid,)).fetchall()
print("Biochar circular requests:", circ_requests)

conn.close()
