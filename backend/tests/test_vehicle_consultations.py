from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import vehicle_consultations as vehicle_api
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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


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
    response = client.get("/admin/consultations/vehicle")
    assert response.status_code == 401
