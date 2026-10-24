from fastapi.testclient import TestClient

from app.api.admin_auth import verify_admin_token
from app.config import settings
from app.main import app

client = TestClient(app)


def configure_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "usernovapagina@gmail.com")
    monkeypatch.setattr(settings, "admin_password", "test-password-that-is-long")
    monkeypatch.setattr(settings, "admin_token_secret", "test-secret-that-is-at-least-32-characters-long")
    monkeypatch.setattr(settings, "admin_token_ttl_minutes", 30)


def test_admin_login_requires_server_configuration(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "")
    monkeypatch.setattr(settings, "admin_token_secret", "")
    response = client.post(
        "/auth/admin/login",
        json={"email": "usernovapagina@gmail.com", "password": "any-password"},
    )
    assert response.status_code == 503


def test_admin_can_login_and_read_identity(monkeypatch):
    configure_admin(monkeypatch)
    response = client.post(
        "/auth/admin/login",
        json={
            "email": "USERNOVAPAGINA@gmail.com",
            "password": "test-password-that-is-long",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["access_token"]

    identity = client.get(
        "/auth/admin/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert identity.status_code == 200
    assert identity.json() == {"email": "usernovapagina@gmail.com", "role": "admin"}


def test_admin_login_rejects_wrong_credentials(monkeypatch):
    configure_admin(monkeypatch)
    response = client.post(
        "/auth/admin/login",
        json={"email": "someone@example.com", "password": "test-password-that-is-long"},
    )
    assert response.status_code == 401


def test_admin_identity_rejects_invalid_token(monkeypatch):
    configure_admin(monkeypatch)
    response = client.get(
        "/auth/admin/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


def test_provider_management_accepts_admin_bearer_token(monkeypatch):
    configure_admin(monkeypatch)
    login = client.post(
        "/auth/admin/login",
        json={
            "email": "usernovapagina@gmail.com",
            "password": "test-password-that-is-long",
        },
    )
    token = login.json()["access_token"]
    # A successful auth passes the route's security dependency; the DB may be
    # unavailable in unit tests, so only assert that auth is not rejected.
    response = client.get(
        "/admin/providers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code != 401
    assert response.status_code != 503
