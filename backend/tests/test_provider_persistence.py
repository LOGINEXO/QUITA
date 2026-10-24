from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import ApiProvider, Base
from app.providers.models import ProviderCapability, ProviderConfig
from app.providers.persistence import PersistentProviderStore, secret_environment_name


def make_store():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return PersistentProviderStore(factory), factory


def test_provider_survives_store_recreation_and_preserves_priority():
    store, factory = make_store()
    config = ProviderConfig(
        id="primary-api",
        name="Principal",
        base_url="https://primary.example",
        capabilities={ProviderCapability.VEHICLE_REFERENCE},
        priority=2,
        enabled=True,
    )
    store.save_config(config)

    # Simula uma nova instância da camada de aplicação após reinicialização.
    restarted_store = PersistentProviderStore(factory)
    loaded = restarted_store.get_config("primary-api")
    assert loaded is not None
    assert loaded.name == "Principal"
    assert loaded.priority == 2
    assert loaded.capabilities == {ProviderCapability.VEHICLE_REFERENCE}


def test_api_secret_is_only_referenced_not_stored_in_database():
    store, factory = make_store()
    config = ProviderConfig(
        id="partner-1",
        name="Parceiro",
        base_url="https://partner.example",
        capabilities={ProviderCapability.DEBTS},
    )
    store.save_config(config)
    with factory() as session:
        row = session.scalar(select(ApiProvider).where(ApiProvider.id == "partner-1"))
        assert row is not None
        assert row.secret_ref == "env:QUITA_PROVIDER_PARTNER_1_API_KEY"
        assert not hasattr(row, "api_key")


def test_secret_environment_name_is_stable_and_sanitized():
    assert secret_environment_name("partner-1") == "QUITA_PROVIDER_PARTNER_1_API_KEY"


def test_delete_provider_persists():
    store, _ = make_store()
    store.save_config(
        ProviderConfig(
            id="remove-me",
            name="Temporário",
            base_url="https://remove.example",
            capabilities={ProviderCapability.DEBTS},
        )
    )
    assert store.delete_config("remove-me") is True
    assert store.get_config("remove-me") is None
    assert store.delete_config("remove-me") is False
