"""DB SQLite lama (sebelum migrasi 016) masih memakai CHECK ck_fpay_net tanpa dp_rp → pelunasan ber-DP ditolak."""
from sqlalchemy import create_engine, text

from app.migrations import _sqlite_refresh_checks


def _make(tmp_path, rows):
    eng = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE farmer_payments (id INTEGER PRIMARY KEY, gross_rp NUMERIC, tax_rp NUMERIC, "
                       "dp_rp NUMERIC DEFAULT 0, net_rp NUMERIC, CONSTRAINT ck_fpay_net CHECK (net_rp = gross_rp - tax_rp))"))
        for r in rows:
            c.execute(text("INSERT INTO farmer_payments (gross_rp, tax_rp, dp_rp, net_rp) VALUES (:g, :t, :d, :n)"), r)
    return eng


def test_old_check_is_upgraded_and_enforced(tmp_path):
    eng = _make(tmp_path, [{"g": 1000, "t": 0, "d": 0, "n": 1000}])
    with eng.begin() as c:
        added = []
        _sqlite_refresh_checks(c, added)
        assert added == ["farmer_payments:CHECK (net_rp = gross_rp - tax_rp - dp_rp)"]
    with eng.begin() as c:
        c.execute(text("INSERT INTO farmer_payments (gross_rp, tax_rp, dp_rp, net_rp) VALUES (1000, 10, 50, 940)"))
        assert c.execute(text("PRAGMA integrity_check")).scalar() == "ok"
    with eng.connect() as c:
        try:
            c.execute(text("INSERT INTO farmer_payments (gross_rp, tax_rp, dp_rp, net_rp) VALUES (1000, 10, 50, 990)"))
            raise AssertionError("CHECK baru harus menolak net yang tidak memotong DP")
        except Exception as e:
            assert "ck_fpay_net" in str(e) or "CHECK" in str(e)
        added = []
        _sqlite_refresh_checks(c, added)   # idempoten
        assert added == []


def test_skipped_when_old_rows_violate(tmp_path):
    eng = _make(tmp_path, [{"g": 1000, "t": 0, "d": 50, "n": 1000}])   # baris lama: DP tidak dipotong
    with eng.begin() as c:
        added = []
        _sqlite_refresh_checks(c, added)
        assert added == []
