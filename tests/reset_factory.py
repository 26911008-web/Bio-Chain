import sqlite3

def reset():
    con = sqlite3.connect('biochain.db')
    cur = con.cursor()
    # Pastikan loading ramps terisi baseline
    cur.execute("DELETE FROM loading_ramps")
    cur.execute("""INSERT INTO loading_ramps 
        (id, ramp_code, name, biomass_type, max_capacity_kg, current_stock_kg, aggregate_mc, aggregate_ash, aggregate_lhv_kcal, is_active)
        VALUES 
        (1, 'RAMP-01', 'Ramp Biomassa 01 (Granular/Sekam)', 'sekam_padi', 60000.0, 15000.0, 13.5, 17.0, 3450.0, 1),
        (2, 'RAMP-02', 'Ramp Biomassa 02 (Cacah/Tongkol)', 'tongkol_jagung', 45000.0, 8000.0, 14.0, 2.5, 4100.0, 1),
        (3, 'RAMP-03', 'Ramp Biomassa 03 (Serbuk Kayu)', 'serbuk_sengon', 40000.0, 5000.0, 28.0, 1.5, 3800.0, 1),
        (4, 'RAMP-04', 'Ramp Biomassa 04 (Cangkang/Tempurung)', 'tempurung_kelapa', 50000.0, 12000.0, 10.5, 2.0, 4600.0, 1)
    """)
    # Pastikan tidak ada overdue block di factory_invoices untuk user 2
    cur.execute("UPDATE factory_invoices SET is_overdue=0 WHERE mill_id=2")
    con.commit()
    print("Factory fixture reset complete.")

if __name__ == '__main__':
    reset()
