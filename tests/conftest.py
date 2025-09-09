# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db


# --------------------------------------------------------------------
# DB SQLite en mémoire pour les tests
# --------------------------------------------------------------------
# connect_args est nécessaire pour SQLite en mode multi-thread (utilisé par FastAPI)
engine = create_engine("sqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Créer et détruire les tables pour toute la session de tests"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    """Fournit une session DB propre pour chaque test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------
# Patcher RabbitMQ pour ne rien envoyer pendant les tests
# --------------------------------------------------------------------
@pytest.fixture
def patch_rabbitmq(monkeypatch):
    """Mock pour publish_message de RabbitMQ."""
    async def fake_publish_message(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.infra.events.rabbitmq.RabbitMQ.publish_message", fake_publish_message
    )


# --------------------------------------------------------------------
# Fournir un client FastAPI avec la DB de test
# --------------------------------------------------------------------
@pytest.fixture
def client(session):
    """Client API pour les tests d'intégration."""
    # Override get_db pour injecter notre session SQLite in-memory
    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
