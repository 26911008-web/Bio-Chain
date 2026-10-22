import sqlite3, datetime

def reset():
    con = sqlite3.connect('biochain.db')
    cur = con.cursor()
    cur.execute("UPDATE routes SET status='planned' WHERE id=50")
    cur.execute("UPDATE route_stops SET stop_status='pending', fail_reason=NULL, qr_scanned=0 WHERE route_id=50")
    cur.execute("UPDATE harvests SET status='verified' WHERE id IN (2, 579)")
    cur.execute("DELETE FROM biochar_distributions WHERE dispatch_code='DSP-BACKHAUL-01'")
    cur.execute("""INSERT INTO biochar_distributions (
        dispatch_code, factory_id, collector_id, driver_id, route_id,
        vehicle_plate, total_bags, total_weight_kg, volume_m3,
        loading_instructions, qr_dispatch_token, status, created_at
    ) VALUES ('DSP-BACKHAUL-01', 2, 3, 4, 50, 'AB 1234 CD', 20, 500.0, 1.2,
        'Muatan balik biochar mutu A untuk Kelompok Tani Sleman', 'QR-DSP-BH-01', 'DISPATCHED', ?)""",
        (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
    con.commit()
    print("Driver fixture successfully reset.")

if __name__ == '__main__':
    reset()
