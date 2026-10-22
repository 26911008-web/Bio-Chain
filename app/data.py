"""Data dummy penggilingan padi di Sleman (DIY) & Klaten (Jateng) untuk demo Prototype Alpha.

Koordinat = titik sekitar pusat kecamatan + jitter acak (seed tetap). Nama dan stok fiktif.
Lokasi pabrik pirolisis adalah titik ilustrasi, bukan alamat PT Indmira.
"""

import random

DEPOT = {"id": "plant", "name": "Pabrik pirolisis (titik ilustrasi, Sleman)", "lat": -7.745, "lon": 110.362}

KECAMATAN = {
    "Godean": (-7.768, 110.293), "Moyudan": (-7.773, 110.244), "Minggir": (-7.732, 110.245),
    "Seyegan": (-7.722, 110.300), "Mlati": (-7.735, 110.335), "Gamping": (-7.792, 110.326),
    "Sleman": (-7.700, 110.350), "Ngaglik": (-7.710, 110.395), "Kalasan": (-7.763, 110.472),
    "Prambanan": (-7.758, 110.495), "Berbah": (-7.800, 110.445), "Tempel": (-7.653, 110.326),
    "Manisrenggo (Klaten)": (-7.733, 110.525), "Jogonalan (Klaten)": (-7.712, 110.540),
    "Karanganom (Klaten)": (-7.643, 110.640), "Ceper (Klaten)": (-7.672, 110.680),
    "Delanggu (Klaten)": (-7.616, 110.705), "Polanharjo (Klaten)": (-7.590, 110.660),
}


def _build_mills() -> list[dict]:
    rng = random.Random(42)
    mills, n = [], 1
    for kec, (lat, lon) in KECAMATAN.items():
        for _ in range(2):
            mills.append({
                "id": f"M{n:02d}",
                "name": f"Penggilingan #{n:02d} – {kec}",
                "kecamatan": kec,
                "lat": round(lat + rng.uniform(-0.012, 0.012), 5),
                "lon": round(lon + rng.uniform(-0.012, 0.012), 5),
                "stock_ton": round(rng.uniform(0.3, 1.8), 1),
                "grade": rng.choice(["A", "A", "B", "B", "C"]),
            })
            n += 1
    return mills


MILLS = _build_mills()
