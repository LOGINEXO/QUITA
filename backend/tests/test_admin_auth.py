from fastapi.testclient import TestClient

from app.api.admin_auth import SESSION_COOKIE
from app.config import settings
from app.main import app

EMAIL = "usernovapagina@gmail.com"
PASSWORD = "test-password-that-is-long"


def configure_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", EMAIL)
    monkeypatch.setattr(settings, "admin_password", PASSWORD)
    monkeypatch.setattr(settings, "admin_cookie_secure", False)


def test_admin_login_requires_server_password_configuration(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "")
    with TestClient(app) as client:
        response = client.post(
            "/auth/admin/login",
            json={"email": EMAIL, "password": "any-password"},
        )
    assert response.status_code == 503
    assert "QUITA_ADMIN_PASSWORD" in response.json()["detail"]


def test_admin_login_sets_http_only_session_cookie_and_me_works(monkeypatch):
    configure_admin(monkeypatch)
    async def create_session(email):
        assert email == EMAIL
        return "fake-session-id"

    async def get_session(session_id):
        assert session_id == "fake-session-id"
        return EMAIL

    monkeypatch.setattr("app.api.admin_auth.create_admin_session", create_session)
    monkeypatch.setattr("app.api.admin_auth.get_admin_session_email", get_session)

    with TestClient(app) as client:
        response = client.post(
            "/auth/admin/login",
            json={"email": EMAIL.upper(), "password": PASSWORD},
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {"email": EMAIL, "role": "admin", "expires_in": 1800}
        assert "access_token" not in body
        assert client.cookies.get(SESSION_COOKIE) == "fake-session-id"
        cookie_header = response.headers["set-cookie"].lower()
        assert "httponly" in cookie_header
        assert "samesite=lax" in cookie_header

        identity = client.get("/auth/admin/me")
        assert identity.status_code == 200
        assert identity.json() == {"email": EMAIL, "role": "admin"}


def test_admin_login_rejects_wrong_credentials(monkeypatch):
    configure_admin(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/auth/admin/login",
            json={"email": "someone@example.com", "password": PASSWORD},
        )
    assert response.status_code == 401


def test_admin_identity_rejects_missing_session():
    with TestClient(app) as client:
        response = client.get("/auth/admin/me")
    assert response.status_code == 401


def test_admin_identity_rejects_unknown_session(monkeypatch):
    configure_admin(monkeypatch)

    async def get_session(_session_id):
        return None

    monkeypatch.setattr("app.api.admin_auth.get_admin_session_email", get_session)
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE, "not-a-valid-session")
        response = client.get("/auth/admin/me")
    assert response.status_code == 401


def test_logout_deletes_session_and_clears_cookie(monkeypatch):
    configure_admin(monkeypatch)
    deleted = []

    async def delete_session(session_id):
        deleted.append(session_id)

    monkeypatch.setattr("app.api.admin_auth.delete_admin_session", delete_session)
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE, "fake-session-id")
        response = client.post("/auth/admin/logout")
    assert response.status_code == 200
    assert response.json() == {"logged_out": True}
    assert deleted == ["fake-session-id"]
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_provider_admin_routes_require_browser_session(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setattr("app.api.providers.store.list_configs", lambda: [])

    async def get_session(session_id):
        return EMAIL if session_id == "valid-session-id" else None

    monkeypatch.setattr("app.api.admin_auth.get_admin_session_email", get_session)
    with TestClient(app) as client:
        denied = client.get("/admin/providers")
        assert denied.status_code == 401

        client.cookies.set(SESSION_COOKIE, "valid-session-id")
        allowed = client.get("/admin/providers")
        assert allowed.status_code == 200
