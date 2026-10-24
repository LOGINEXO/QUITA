from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.models import ApiProvider, Base, Customer, Lead, VehicleConsultation
from app.db.session import normalize_database_url


def test_normalizes_render_postgres_scheme_for_psycopg3() -> None:
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"


def test_schema_creates_core_tables_and_indexes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert {
        "customers",
        "leads",
        "vehicle_consultations",
        "api_providers",
        "audit_events",
    }.issubset(set(inspector.get_table_names()))
    assert "ix_vehicle_consultations_plate_created_at" in {
        index["name"] for index in inspector.get_indexes("vehicle_consultations")
    }


def test_customer_lead_consultation_relationships() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        customer = Customer(full_name="Cliente de teste", email="teste@example.com")
        lead = Lead(customer=customer, status="new", source="site")
        consultation = VehicleConsultation(lead=lead, plate="ABC1D23", status="pending")
        session.add(consultation)
        session.commit()
        assert consultation.id is not None
        assert consultation.lead.customer.full_name == "Cliente de teste"


def test_provider_schema_references_secret_instead_of_storing_plaintext() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        provider = ApiProvider(
            id="primary",
            name="Provedor primário",
            base_url="https://api.example.test",
            capabilities=["vehicle_reference"],
            secret_ref="env:QUITA_PROVIDER_PRIMARY_KEY",
        )
        session.add(provider)
        session.commit()
        assert provider.secret_ref == "env:QUITA_PROVIDER_PRIMARY_KEY"
        assert not hasattr(provider, "api_key")
