# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# This import is crucial to register the models with SQLAlchemy's Base
from app.models import client as client_model

# --- Test Database Setup ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables once for the entire test session
Base.metadata.create_all(bind=engine)

@pytest.fixture()
def session():
    """Create a new database session for a test, within a transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)

    try:
        yield db
    finally:
        transaction.rollback()
        db.close()
        connection.close()


@pytest.fixture()
def client(session):
    """Provide a TestClient that uses the test database session."""
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]


@pytest.fixture
def patch_rabbitmq(monkeypatch):
    """Mock for publish_message of RabbitMQ."""
    async def fake_publish_message(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.infra.events.rabbitmq.RabbitMQ.publish_message", fake_publish_message
    )