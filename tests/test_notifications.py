"""Test notifikasi perubahan transaksi biomassa lintas persona dan pengelompokan berdasarkan status."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from tests.conftest import demo_headers
from app.models.notification import NotificationStatusGroup


@pytest.mark.asyncio
async def test_notifications_all_personas():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test login & retrieve notifications for all 6 personas
        roles = ["petani", "pengepul", "driver", "pabrik", "auditor", "admin"]
        
        for role in roles:
            # Login
            res_login = await client.post("/api/v1/auth/login", json={
                "identifier": f"{role}_sugeng" if role == "petani" else (
                    f"pengepul_sleman" if role == "pengepul" else (
                        f"sopir_budi" if role == "driver" else (
                            f"pabrik_indmira" if role == "pabrik" else (
                                f"auditor_esg" if role == "auditor" else "admin"
                            )
                        )
                    )
                ),
                "password": f"sekam123" if role == "petani" else (
                    f"kud2026" if role == "pengepul" else (
                        f"truk2026" if role == "driver" else (
                            f"pabrik2026" if role == "pabrik" else (
                                f"audit2026" if role == "auditor" else "admin2026"
                            )
                        )
                    )
                )
            })
            assert res_login.status_code == 200, f"Login failed for {role}: {res_login.text}"
            token = res_login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Get summary
            res_summary = await client.get("/api/v1/notifications/summary", headers=headers)
            assert res_summary.status_code == 200
            sum_data = res_summary.json()
            assert "unread_count" in sum_data
            assert "counts_by_group" in sum_data
            assert "group_meta" in sum_data
            for group_key in ["PENDING_ACTION", "IN_PROGRESS", "COMPLETED", "ALERT_DISCREPANCY"]:
                assert group_key in sum_data["counts_by_group"]
                assert group_key in sum_data["group_meta"]

            # 2. Get full list with grouped items
            res_list = await client.get("/api/v1/notifications/", headers=headers)
            assert res_list.status_code == 200
            list_data = res_list.json()
            assert "grouped_items" in list_data
            assert "items" in list_data
            assert len(list_data["items"]) > 0

            # Verifikasi 4 grup status tersedia dalam grouped_items
            for group_key in ["PENDING_ACTION", "IN_PROGRESS", "COMPLETED", "ALERT_DISCREPANCY"]:
                assert group_key in list_data["grouped_items"]
                assert isinstance(list_data["grouped_items"][group_key], list)

            # 3. Filter by status_group query param
            for test_grp in ["PENDING_ACTION", "IN_PROGRESS", "COMPLETED", "ALERT_DISCREPANCY"]:
                res_filtered = await client.get(f"/api/v1/notifications/?status_group={test_grp}", headers=headers)
                assert res_filtered.status_code == 200
                filt_data = res_filtered.json()
                for item in filt_data["items"]:
                    assert item["status_group"] == test_grp

            # 4. Mark single notification as read
            first_notif = list_data["items"][0]
            notif_id = first_notif["id"]
            res_read = await client.post(f"/api/v1/notifications/{notif_id}/read", headers=headers)
            assert res_read.status_code == 200
            assert res_read.json()["is_read"] is True

            # 5. Mark all as read
            res_read_all = await client.post("/api/v1/notifications/read-all", headers=headers)
            assert res_read_all.status_code == 200
            assert "marked_read_count" in res_read_all.json()
