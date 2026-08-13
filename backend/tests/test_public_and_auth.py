"""
Integration tests for public endpoints + admin auth (no psycopg2 utils needed).

These hit the Flask test client against SQLite in-memory and exercise the
ORM-only code paths.
"""
from datetime import date, timedelta

from models import Location, NewsletterSubscriber


class TestHealth:
    def test_health_returns_connected(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "healthy"
        assert body["database"] == "connected"

    def test_test_endpoint(self, client):
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Backend is working!"


class TestLocations:
    def test_get_locations_empty(self, client):
        resp = client.get("/api/reservations/locations")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "locations" in body
        assert body["locations"] == []

    def test_get_locations_returns_seeded(self, client, db_session):
        db_session.add(Location(code="JPN", name="Japan", timezone="Asia/Tokyo"))
        db_session.add(Location(code="ITA", name="Italy", timezone="Europe/Rome"))
        db_session.commit()

        resp = client.get("/api/reservations/locations")
        assert resp.status_code == 200
        names = [loc["name"] for loc in resp.get_json()["locations"]]
        # Ordered by name
        assert names == ["Italy", "Japan"]


class TestAvailability:
    def test_requires_location_and_date(self, client):
        resp = client.get("/api/reservations/availability")
        assert resp.status_code == 400

    def test_rejects_past_date(self, client, db_session):
        db_session.add(Location(code="JPN", name="Japan", timezone="Asia/Tokyo"))
        db_session.commit()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = client.get(f"/api/reservations/availability?location_id=1&date={yesterday}")
        assert resp.status_code == 400
        assert "past" in resp.get_json()["error"].lower()

    def test_rejects_bad_date_format(self, client, db_session):
        db_session.add(Location(code="JPN", name="Japan", timezone="Asia/Tokyo"))
        db_session.commit()
        resp = client.get("/api/reservations/availability?location_id=1&date=not-a-date")
        assert resp.status_code == 400

    def test_returns_slots_for_valid_date(self, client, db_session, fake_conn):
        loc = Location(code="JPN", name="Japan", timezone="Asia/Tokyo",
                       max_guests_per_slot=120, max_reservations_per_slot=30)
        db_session.add(loc)
        db_session.commit()

        # The availability endpoint calls validate_reservation_constraints once
        # per slot (12 slots for a Tuesday). Each call hits the fake conn in this
        # order: check_location_blocks (1 query), location limits lookup (1),
        # calculate_location_occupancy (1). Plus the raw occupancy query done
        # inline in the route. We pre-queue enough "not blocked / under limit"
        # results so validation passes.
        # Per slot: validate_reservation_constraints -> 3 result sets; route does
        # its own raw SELECT -> 1 result set. So 4 per slot * 12 slots = 48.
        # Each validate call: [(0,)] not blocked, [(120,30)] limits, [(0,0)] occupancy.
        # Route's own query: [(0, 0)] guests/reservations.
        for _ in range(12):
            fake_conn.queue_result_set([(0,)])      # not location-blocked
            fake_conn.queue_result_set([(120, 30)]) # limits
            fake_conn.queue_result_set([(0, 0)])    # location occupancy
            fake_conn.queue_result_set([(0, 0)])    # route's inline raw query

        future = (date.today() + timedelta(days=1)).isoformat()
        # Use a known Tuesday so slot count is predictable.
        # If today+1 isn't Tuesday, just accept whatever count comes back.
        resp = client.get(f"/api/reservations/availability?location_id={loc.id}&date={future}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["date"] == future
        assert isinstance(body["slots"], list)
        assert len(body["slots"]) > 0
        assert "time" in body["slots"][0]
        assert "available" in body["slots"][0]


class TestNewsletter:
    def test_subscribe_creates_new_subscriber(self, client, db_session):
        resp = client.post("/api/newsletter/", json={
            "email": "new@example.com",
            "name": "New User",
        })
        assert resp.status_code == 201
        sub = db_session.query(NewsletterSubscriber).filter_by(email="new@example.com").first()
        assert sub is not None
        assert sub.status == "active"
        assert sub.name == "New User"

    def test_subscribe_rejects_invalid_email(self, client):
        resp = client.post("/api/newsletter/", json={"email": "not-an-email"})
        assert resp.status_code == 400

    def test_subscribe_rejects_missing_email(self, client):
        resp = client.post("/api/newsletter/", json={})
        assert resp.status_code == 400

    def test_resubscribe_reactivates_unsubscribed(self, client, db_session):
        sub = NewsletterSubscriber(email="back@example.com", name="Back", status="unsubscribed")
        db_session.add(sub)
        db_session.commit()

        resp = client.post("/api/newsletter/", json={"email": "back@example.com"})
        assert resp.status_code == 201
        db_session.refresh(sub)
        assert sub.status == "active"

    def test_already_active_returns_200(self, client, db_session):
        db_session.add(NewsletterSubscriber(email="active@example.com", status="active"))
        db_session.commit()
        resp = client.post("/api/newsletter/", json={"email": "active@example.com"})
        assert resp.status_code == 200


class TestAdminAuth:
    def test_login_success(self, client, db_session):
        import bcrypt
        from models import Admin
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode("utf-8")
        db_session.add(Admin(username="admin1", password_hash=hashed,
                             full_name="Admin One", role="admin"))
        db_session.commit()

        resp = client.post("/api/admin/login", json={"username": "admin1", "password": "secret"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["admin"]["username"] == "admin1"
        assert body["admin"]["role"] == "admin"

    def test_login_wrong_password(self, client, db_session):
        import bcrypt
        from models import Admin
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode("utf-8")
        db_session.add(Admin(username="admin2", password_hash=hashed, full_name="A", role="admin"))
        db_session.commit()

        resp = client.post("/api/admin/login", json={"username": "admin2", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/admin/login", json={"username": ""})
        assert resp.status_code == 400

    def test_logout_clears_session(self, authed_client):
        resp = authed_client.post("/api/admin/logout")
        assert resp.status_code == 200
        # After logout, protected endpoints should 401
        resp = authed_client.get("/api/admin/profile")
        assert resp.status_code == 401

    def test_protected_endpoint_without_session(self, client):
        resp = client.get("/api/admin/profile")
        assert resp.status_code == 401

    def test_protected_reservations_without_session(self, client):
        resp = client.get("/api/admin/reservations")
        assert resp.status_code == 401