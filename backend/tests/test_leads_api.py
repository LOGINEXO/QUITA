from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.providers import require_admin
from app.config import settings
from app.db.models import Base
from app.db.session import get_db
from app.main import app

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)


def override_get_db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


client = TestClient(app)


def configure_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "admin@example.com")
    monkeypatch.setattr(settings, "admin_password", "a-long-test-password")
    monkeypatch.setattr(settings, "admin_token_secret", "test-secret-that-is-at-least-32-characters-long")
    monkeypatch.setattr(settings, "admin_token_ttl_minutes", 30)


def setup_function():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def teardown_function():
    app.dependency_overrides.pop(get_db, None)


def test_public_lead_capture_normalizes_contact_data():
    response = client.post(
        "/leads",
        json={
            "full_name": "  Maria   Silva ",
            "email": " MARIA@EXAMPLE.COM ",
            "phone": "(11) 99999-0000",
            "postal_code": "12.345-678",
            "source": "landing-page",
            "privacy_consent": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "new"
    assert body["id"] > 0


def test_public_lead_capture_requires_contact_and_consent():
    no_contact = client.post(
        "/leads",
        json={"full_name": "Maria Silva", "privacy_consent": True},
    )
    assert no_contact.status_code == 422

    no_consent = client.post(
        "/leads",
        json={"full_name": "Maria Silva", "phone": "11999990000", "privacy_consent": False},
    )
    assert no_consent.status_code == 422


def test_admin_can_list_filter_and_update_leads(monkeypatch):
    configure_admin(monkeypatch)
    created = client.post(
        "/leads",
        json={
            "full_name": "João Souza",
            "phone": "21999990000",
            "privacy_consent": True,
        },
    )
    lead_id = created.json()["id"]
    login = client.post(
        "/auth/admin/login",
        json={"email": "admin@example.com", "password": "a-long-test-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = client.get("/admin/leads?status=new", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["customer_name"] == "João Souza"

    updated = client.patch(
        f"/admin/leads/{lead_id}",
        headers=headers,
        json={"status": "contacted", "notes": "Contato inicial realizado"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"
    assert updated.json()["notes"] == "Contato inicial realizado"


def test_admin_lead_list_requires_authentication(monkeypatch):
    configure_admin(monkeypatch)
    response = client.get("/admin/leads")
    assert response.status_code == 401
