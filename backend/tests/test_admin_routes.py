"""
Integration tests for the protected admin endpoints. Uses the authed_client
fixture (logged in as a manager-role admin) and the fake_conn fixture for routes
that delegate to the psycopg2-based room-assignment utils.
"""
from datetime import date, timedelta

from models import Reservation, Customer, ReservationBlock, AuditLog


# --------------------------------------------------------------------------- #
# Profile                                                                      #
# --------------------------------------------------------------------------- #
class TestProfile:
    def test_get_profile(self, authed_client):
        resp = authed_client.get("/api/admin/profile")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["username"] == "testadmin"
        assert body["fullName"] == "Test Admin"
        assert body["role"] == "manager"

    def test_update_name(self, authed_client):
        resp = authed_client.put("/api/admin/profile/name", json={"fullName": "New Name"})
        assert resp.status_code == 200
        # Verify the change persisted
        resp = authed_client.get("/api/admin/profile")
        assert resp.get_json()["fullName"] == "New Name"

    def test_update_name_rejects_empty(self, authed_client):
        resp = authed_client.put("/api/admin/profile/name", json={"fullName": ""})
        assert resp.status_code == 400

    def test_update_password_success(self, authed_client):
        resp = authed_client.put("/api/admin/profile/password", json={
            "currentPassword": "secret",
            "newPassword": "newsecret",
            "confirmPassword": "newsecret",
        })
        assert resp.status_code == 200

    def test_update_password_wrong_current(self, authed_client):
        resp = authed_client.put("/api/admin/profile/password", json={
            "currentPassword": "wrong",
            "newPassword": "newsecret",
            "confirmPassword": "newsecret",
        })
        assert resp.status_code == 400

    def test_update_password_mismatch(self, authed_client):
        resp = authed_client.put("/api/admin/profile/password", json={
            "currentPassword": "secret",
            "newPassword": "newsecret",
            "confirmPassword": "different",
        })
        assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# Reservations (admin)                                                        #
# --------------------------------------------------------------------------- #
class TestAdminReservations:
    def test_list_reservations_empty(self, authed_client):
        resp = authed_client.get("/api/admin/reservations")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_requires_auth(self, client):
        resp = client.get("/api/admin/reservations")
        assert resp.status_code == 401

    def test_filter_by_date(self, authed_client, db_session, seed_data):
        future = (date.today() + timedelta(days=2)).isoformat()
        r = Reservation(
            reservation_number="TST-AAA01",
            customer_id=seed_data["customer"].id,
            location_id=seed_data["location"].id,
            room_id=seed_data["room"].id,
            date=future,
            time="19:00",
            duration_minutes=60,
            party_size=4,
            status="confirmed",
        )
        db_session.add(r)
        db_session.commit()

        resp = authed_client.get(f"/api/admin/reservations?date={future}")
        assert resp.status_code == 200
        rows = resp.get_json()
        assert len(rows) == 1
        assert rows[0]["reservation_number"] == "TST-AAA01"

    def test_search_by_name(self, authed_client, db_session, seed_data):
        future = (date.today() + timedelta(days=3)).isoformat()
        cust = Customer(name="Unique Searchable", email="search@example.com")
        db_session.add(cust)
        db_session.commit()
        r = Reservation(
            reservation_number="TST-SRCH1",
            customer_id=cust.id,
            location_id=seed_data["location"].id,
            room_id=seed_data["room"].id,
            date=future,
            time="19:00",
            duration_minutes=60,
            party_size=2,
            status="confirmed",
        )
        db_session.add(r)
        db_session.commit()

        resp = authed_client.get("/api/admin/reservations?search=Searchable")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_update_status(self, authed_client, db_session, seed_data):
        r = Reservation(
            reservation_number="TST-STS01",
            customer_id=seed_data["customer"].id,
            location_id=seed_data["location"].id,
            room_id=seed_data["room"].id,
            date=date.today() + timedelta(days=4),
            time="19:00",
            duration_minutes=60,
            party_size=2,
            status="confirmed",
        )
        db_session.add(r)
        db_session.commit()

        resp = authed_client.put(
            f"/api/admin/reservations/{r.id}/status", json={"status": "cancelled"}
        )
        assert resp.status_code == 200
        db_session.refresh(r)
        assert r.status == "cancelled"

    def test_update_status_invalid_value(self, authed_client, db_session, seed_data):
        r = Reservation(
            reservation_number="TST-STS02",
            customer_id=seed_data["customer"].id,
            location_id=seed_data["location"].id,
            room_id=seed_data["room"].id,
            date=date.today() + timedelta(days=5),
            time="19:00",
            duration_minutes=60,
            party_size=2,
            status="confirmed",
        )
        db_session.add(r)
        db_session.commit()

        resp = authed_client.put(
            f"/api/admin/reservations/{r.id}/status", json={"status": "bogus"}
        )
        assert resp.status_code == 400

    def test_update_status_not_found(self, authed_client):
        resp = authed_client.put("/api/admin/reservations/99999/status", json={"status": "cancelled"})
        assert resp.status_code == 404

    def test_delete_reservation(self, authed_client, db_session, seed_data):
        r = Reservation(
            reservation_number="TST-DEL01",
            customer_id=seed_data["customer"].id,
            location_id=seed_data["location"].id,
            room_id=seed_data["room"].id,
            date=date.today() + timedelta(days=6),
            time="19:00",
            duration_minutes=60,
            party_size=2,
            status="confirmed",
        )
        db_session.add(r)
        db_session.commit()
        rid = r.id

        resp = authed_client.delete(f"/api/admin/reservations/{rid}")
        assert resp.status_code == 200
        assert db_session.get(Reservation, rid) is None

    def test_delete_not_found(self, authed_client):
        resp = authed_client.delete("/api/admin/reservations/99999")
        assert resp.status_code == 404

    def test_create_admin_reservation(self, authed_client, seed_data, fake_conn):
        """
        Create a reservation via the admin endpoint. The route uses the psycopg2
        utils (validate_reservation_constraints + weighted_random_room_selection),
        so we pre-queue fake DB results that make validation pass and return a
        candidate room.
        """
        future = (date.today() + timedelta(days=7)).isoformat()
        loc = seed_data["location"]
        room = seed_data["room"]

        # validate_reservation_constraints sequence:
        #   1) check_location_blocks -> not blocked
        fake_conn.queue_result_set([(0,)])
        #   2) location limits lookup -> (120, 30)
        fake_conn.queue_result_set([(120, 30)])
        #   3) calculate_location_occupancy -> (0, 0)
        fake_conn.queue_result_set([(0, 0)])
        # weighted_random_room_selection:
        #   4) get_candidate_rooms -> one room row
        fake_conn.queue_result_set([(room.id, room.code, room.name, room.max_capacity)])
        #   5) check_room_blocks('hard') for the candidate -> not blocked
        fake_conn.queue_result_set([(0,)])
        #   6) calculate_room_occupancy for the candidate -> 0
        fake_conn.queue_result_set([(0,)])
        #   7) reservation_count for the candidate -> 0
        fake_conn.queue_result_set([(0,)])
        #   8) check_room_blocks('soft') on the chosen room -> not blocked
        fake_conn.queue_result_set([(0,)])

        resp = authed_client.post("/api/admin/reservations/create", json={
            "location_id": loc.id,
            "date": future,
            "time": "19:00",
            "party_size": 4,
            "customer_name": "Jane Doe",
            "customer_email": "jane@example.com",
            "customer_phone": "+1-555-0123",
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert "reservation_number" in body
        assert body["reservation_number"].startswith("TST-")

    def test_create_admin_rejects_party_over_30(self, authed_client, seed_data):
        future = (date.today() + timedelta(days=8)).isoformat()
        resp = authed_client.post("/api/admin/reservations/create", json={
            "location_id": seed_data["location"].id,
            "date": future,
            "time": "19:00",
            "party_size": 50,
            "customer_name": "Big Group",
            "customer_email": "big@example.com",
        })
        assert resp.status_code == 400
        assert "1 and 30" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# Blocks                                                                       #
# --------------------------------------------------------------------------- #
class TestBlocks:
    def test_list_blocks_empty(self, authed_client):
        resp = authed_client.get("/api/admin/blocks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_block(self, authed_client, seed_data):
        resp = authed_client.post("/api/admin/blocks", json={
            "location_id": seed_data["location"].id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-01",
            "start_time": "17:00",
            "end_time": "23:00",
            "block_type": "hard",
            "reason": "Private event",
        })
        assert resp.status_code == 201
        assert "id" in resp.get_json()

    def test_create_block_rejects_bad_type(self, authed_client, seed_data):
        resp = authed_client.post("/api/admin/blocks", json={
            "location_id": seed_data["location"].id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-01",
            "start_time": "17:00",
            "end_time": "23:00",
            "block_type": "invalid",
        })
        assert resp.status_code == 400

    def test_create_block_missing_fields(self, authed_client):
        resp = authed_client.post("/api/admin/blocks", json={"location_id": 1})
        assert resp.status_code == 400

    def test_delete_block(self, authed_client, db_session, seed_data):
        b = ReservationBlock(
            location_id=seed_data["location"].id,
            room_id=None,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            start_time="17:00",
            end_time="23:00",
            block_type="soft",
        )
        db_session.add(b)
        db_session.commit()

        resp = authed_client.delete(f"/api/admin/blocks/{b.id}")
        assert resp.status_code == 200
        assert db_session.get(ReservationBlock, b.id) is None

    def test_delete_block_not_found(self, authed_client):
        resp = authed_client.delete("/api/admin/blocks/99999")
        assert resp.status_code == 404

    def test_list_blocks_filters_by_location(self, authed_client, db_session, seed_data):
        # Add a second location so we can verify the filter excludes it.
        from models import Location
        loc2 = Location(code="OTR", name="Other", timezone="UTC")
        db_session.add(loc2)
        db_session.commit()

        b1 = ReservationBlock(
            location_id=seed_data["location"].id,
            room_id=None,
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 1),
            start_time="17:00", end_time="23:00", block_type="hard",
        )
        b2 = ReservationBlock(
            location_id=loc2.id,
            room_id=None,
            start_date=date(2026, 9, 2), end_date=date(2026, 9, 2),
            start_time="17:00", end_time="21:00", block_type="soft",
        )
        db_session.add_all([b1, b2])
        db_session.commit()

        resp = authed_client.get(f"/api/admin/blocks?location_id={seed_data['location'].id}")
        assert resp.status_code == 200
        rows = resp.get_json()
        assert len(rows) == 1
        assert rows[0]["location_id"] == seed_data["location"].id


# --------------------------------------------------------------------------- #
# Customers & Subscribers                                                     #
# --------------------------------------------------------------------------- #
class TestCustomers:
    def test_list_customers(self, authed_client, seed_data):
        resp = authed_client.get("/api/admin/customers")
        assert resp.status_code == 200
        rows = resp.get_json()
        assert any(c["email"] == "test@example.com" for c in rows)

    def test_update_customer(self, authed_client, db_session, seed_data):
        cust = seed_data["customer"]
        resp = authed_client.put(f"/api/admin/customers/{cust.id}", json={
            "name": "Renamed",
            "email": "renamed@example.com",
            "phone": "+1-555-9999",
            "newsletter_signup": True,
        })
        assert resp.status_code == 200
        db_session.refresh(cust)
        assert cust.name == "Renamed"
        assert cust.email == "renamed@example.com"

    def test_update_customer_email_conflict(self, authed_client, db_session, seed_data):
        other = Customer(name="Other", email="other@example.com")
        db_session.add(other)
        db_session.commit()

        resp = authed_client.put(f"/api/admin/customers/{seed_data['customer'].id}", json={
            "name": "Test Customer",
            "email": "other@example.com",
        })
        assert resp.status_code == 409

    def test_update_customer_not_found(self, authed_client):
        resp = authed_client.put("/api/admin/customers/99999", json={
            "name": "X", "email": "x@example.com",
        })
        assert resp.status_code == 404

    def test_list_subscribers(self, authed_client, db_session):
        from models import NewsletterSubscriber
        db_session.add(NewsletterSubscriber(email="sub@example.com", status="active"))
        db_session.commit()
        resp = authed_client.get("/api/admin/subscribers")
        assert resp.status_code == 200
        assert any(s["email"] == "sub@example.com" for s in resp.get_json())


# --------------------------------------------------------------------------- #
# Audit log                                                                    #
# --------------------------------------------------------------------------- #
class TestAuditLog:
    def test_get_audit_log_empty(self, authed_client):
        resp = authed_client.get("/api/admin/audit-log")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_audit_log_has_entry_after_block_create(self, authed_client, db_session, seed_data):
        # Create a block (which logs), then check the audit log.
        resp = authed_client.post("/api/admin/blocks", json={
            "location_id": seed_data["location"].id,
            "start_date": "2026-09-01", "end_date": "2026-09-01",
            "start_time": "17:00", "end_time": "23:00",
            "block_type": "hard", "reason": "test",
        })
        assert resp.status_code == 201

        resp = authed_client.get("/api/admin/audit-log")
        entries = resp.get_json()
        assert any(e["action"] == "create_block" for e in entries)

    def test_audit_log_limit_param(self, authed_client, db_session):
        for i in range(5):
            db_session.add(AuditLog(
                admin_id=None, action="create_block", entity_type="block", entity_id=i,
            ))
        db_session.commit()
        resp = authed_client.get("/api/admin/audit-log?limit=2")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2


# --------------------------------------------------------------------------- #
# Rooms & Dashboard                                                            #
# --------------------------------------------------------------------------- #
class TestRoomsAndDashboard:
    def test_get_rooms_requires_location(self, authed_client):
        resp = authed_client.get("/api/admin/rooms")
        assert resp.status_code == 400

    def test_get_rooms(self, authed_client, seed_data):
        resp = authed_client.get(f"/api/admin/rooms?location_id={seed_data['location'].id}")
        assert resp.status_code == 200
        rows = resp.get_json()
        assert len(rows) == 1
        assert rows[0]["code"] == "TST-R1"

    def test_dashboard_requires_params(self, authed_client):
        resp = authed_client.get("/api/admin/dashboard/stats")
        assert resp.status_code == 400

    def test_dashboard_not_found_location(self, authed_client):
        future = (date.today() + timedelta(days=1)).isoformat()
        resp = authed_client.get(f"/api/admin/dashboard/stats?location_id=999&date={future}")
        assert resp.status_code == 404

    def test_dashboard_returns_structure(self, authed_client, seed_data):
        future = (date.today() + timedelta(days=1)).isoformat()
        resp = authed_client.get(
            f"/api/admin/dashboard/stats?location_id={seed_data['location'].id}&date={future}"
        )
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ("location", "date", "time_slots", "room_heatmap", "location_stats", "reservations"):
            assert key in body
        assert body["location"]["code"] == "TST"
        assert isinstance(body["room_heatmap"], list)
        assert isinstance(body["location_stats"], dict)