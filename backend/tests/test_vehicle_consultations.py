from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.api import vehicle_consultations as vehicle_api
from app.config import settings
from app.db.models import Base
from app.db.session import get_db
from app.main import app
from app.integrations.buscafipe import BuscaFipeError

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


@pytest.fixture(autouse=True)
def isolate_test_dependencies(monkeypatch):
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-key")
    monkeypatch.setattr(settings, "admin_token_secret", "test-secret-that-is-at-least-32-characters-long")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def test_vehicle_consultation_persists_success(monkeypatch):
    async def fake_plate(plate):
        assert plate == "ABC1D23"
        return {"marca": "FIAT", "modelo": "ARGO"}

    monkeypatch.setattr(vehicle_api.buscafipe_client, "plate", fake_plate)
    response = client.post("/consultations/vehicle", json={"plate": "abc-1d23"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["result"]["modelo"] == "ARGO"
    assert body["completed_at"] is not None


def test_vehicle_consultation_records_provider_unavailable(monkeypatch):
    async def fake_plate(plate):
        raise BuscaFipeError("provider unavailable")

    monkeypatch.setattr(vehicle_api.buscafipe_client, "plate", fake_plate)
    response = client.post("/consultations/vehicle", json={"plate": "ABC1D23"})
    assert response.status_code == 201
    assert response.json()["status"] == "unavailable"
    assert response.json()["result"] is None
    assert response.json()["error_code"] == "provider_unavailable"


def test_vehicle_consultation_rejects_invalid_plate_without_provider_call(monkeypatch):
    async def fake_plate(plate):
        raise AssertionError("Provider must not be called for invalid plates")

    monkeypatch.setattr(vehicle_api.buscafipe_client, "plate", fake_plate)
    response = client.post("/consultations/vehicle", json={"plate": "NOTAPLATE"})
    assert response.status_code == 422


def test_admin_vehicle_consultation_list_requires_authentication():
    response = client.get("/admin/consultations/vehicle", headers={"X-Admin-Api-Key": "wrong-key"})
    assert response.status_code == 401
