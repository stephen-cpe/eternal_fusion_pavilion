"""
Pytest fixtures for the EFP backend.

Strategy:
- Route/blueprint integration tests use SQLite in-memory via SQLAlchemy (the
  ORM abstracts the dialect). The app fixture passes the test settings into
  create_app() before Flask-SQLAlchemy and Flask-Session are initialized, so
  tests never connect to PostgreSQL or write filesystem sessions. The psycopg2
  connection pool used by the raw-SQL utils is bypassed by monkeypatching
  get_connection/release_connection, and Flask-Session uses an in-memory
  cachelib store.
- SQLite's Date/Time types reject the ISO strings that PostgreSQL accepts, so
  a before_flush hook coerces those strings before they reach SQLite.
- Utils unit tests use a FakeCursor stub (see tests/fake_db.py) so no real
  database is required.

We use function-scoped app/client fixtures (create_all / drop_all per test) to
avoid SQLite locking issues that arise with a long-lived in-memory connection
shared across tests.
"""
import datetime as dt
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import Date, DateTime, Time, event
from sqlalchemy.orm import Session, object_mapper

# Make `backend/` importable when pytest runs from the backend dir or repo root.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force SQLite-friendly model types for the test session BEFORE importing app.
os.environ["TESTING"] = "true"


@event.listens_for(Session, "before_flush")
def _coerce_iso_temporal_strings(session, flush_context, instances):
    """Coerce ISO date/time strings so SQLite matches PostgreSQL's behaviour."""
    for obj in list(session.new) + list(session.dirty):
        for prop in object_mapper(obj).column_attrs:
            value = getattr(obj, prop.key, None)
            if not isinstance(value, str):
                continue
            column_type = prop.columns[0].type
            if isinstance(column_type, DateTime):
                parsed = dt.datetime.fromisoformat(value)
            elif isinstance(column_type, Date):
                parsed = dt.date.fromisoformat(value)
            elif isinstance(column_type, Time):
                parsed = dt.time.fromisoformat(value)
            else:
                continue
            setattr(obj, prop.key, parsed)


@pytest.fixture()
def app():
    """Create a fresh Flask app + in-memory SQLite DB per test."""
    import cachelib
    from app import create_app
    from database import db

    # Neutralize the psycopg2 pool so it never tries to reach Postgres.
    import database as _database
    _database.connection_pool = None

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "SESSION_TYPE": "cachelib",
        "SESSION_CACHELIB": cachelib.SimpleCache(),
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        assert db.engine.url.get_backend_name() == "sqlite", "Flask tests must never run against PostgreSQL"
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def db_session(app):
    """The SQLAlchemy session, scoped to the app context."""
    from database import db
    return db.session


@pytest.fixture()
def authed_client(client, db_session):
    """A test client with a simulated admin login session.

    Seeds a manager-role admin and logs in via the real /api/admin/login endpoint
    so the session cookie is set, then returns the client for protected routes.
    """
    import bcrypt
    from models import Admin

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode("utf-8")
    admin = Admin(
        username="testadmin",
        password_hash=hashed,
        full_name="Test Admin",
        role="manager",
    )
    db_session.add(admin)
    db_session.commit()

    resp = client.post(
        "/api/admin/login",
        json={"username": "testadmin", "password": "secret"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
    return client


@pytest.fixture()
def seed_data(db_session):
    """Seed minimal reference data (location, room, customer) for reservation tests."""
    from models import Location, Room, Customer

    location = Location(
        code="TST",
        name="Test Location",
        timezone="UTC",
        max_guests_per_slot=120,
        max_reservations_per_slot=30,
    )
    db_session.add(location)
    db_session.commit()

    room = Room(
        location_id=location.id,
        code="TST-R1",
        name="Test Room",
        max_capacity=30,
        is_active=True,
    )
    db_session.add(room)
    db_session.commit()

    customer = Customer(
        name="Test Customer",
        email="test@example.com",
        phone="+1-555-0100",
    )
    db_session.add(customer)
    db_session.commit()

    return {
        "location": location,
        "room": room,
        "customer": customer,
    }


# --------------------------------------------------------------------------- #
# Fake psycopg2 connection patching for routes that use the raw-SQL utils.   #
# --------------------------------------------------------------------------- #
@pytest.fixture()
def fake_conn(monkeypatch):
    """
    Patch database.get_connection / release_connection so route handlers that
    call psycopg2-based utils (validate_reservation_constraints,
    weighted_random_room_selection, check_room_blocks, etc.) get a FakeConnection
    instead of a real Postgres connection.

    The fixture yields a single FakeConnection. Tests pre-queue result sets on it
    (via queue_result_set) before triggering the request; the route will call
    get_connection() and receive this same connection.
    """
    from tests.fake_db import FakeConnection

    conn = FakeConnection()

    def fake_get_connection():
        return conn

    def fake_release_connection(c):
        pass

    import database
    monkeypatch.setattr(database, "get_connection", fake_get_connection)
    monkeypatch.setattr(database, "release_connection", fake_release_connection)
    # Also patch the names re-exported into each route module.
    for mod_name in (
        "routes.reservations",
        "routes.admin_reservations",
        "routes.admin_other",
    ):
        try:
            mod = __import__(mod_name, fromlist=["x"])
            if hasattr(mod, "get_connection"):
                monkeypatch.setattr(mod, "get_connection", fake_get_connection)
            if hasattr(mod, "release_connection"):
                monkeypatch.setattr(mod, "release_connection", fake_release_connection)
        except ImportError:
            pass

    conn.reset()
    return conn