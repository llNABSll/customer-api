# tests/conftest.py
from __future__ import annotations

import os
import types
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1) Avant tout import d'app.core.database, assure un port valide pour l'URL Postgres
#    (sinon SQLAlchemy crashe en parsant "None")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "postgres")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")  # <— le plus important
# (optionnel) si ton module supporte DATABASE_URL directement, on le mette quand même :
# os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # 1) Forcer SQLite pour éviter Postgres pendant les tests
    os.environ["SQLALCHEMY_DATABASE_URL"] = "sqlite:///./test.db"

    # 2) Importer le module après avoir posé la variable d’env
    import app.core.database as dbmod
    from app.core.database import Base  # contient le metadata
    import app.models.client  # s'assure que les modèles sont enregistrés sur Base

    # 3) Recréer l’engine et la Session sur SQLite (fichier local)
    engine = create_engine(
        os.environ["SQLALCHEMY_DATABASE_URL"],
        connect_args={"check_same_thread": False},  # pour SQLite + threads
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 4) Remplacer dans le module pour tout le code de l’app
    dbmod.engine = engine
    dbmod.SessionLocal = TestingSessionLocal

    # 5) (Re)créer le schéma pour les tests
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield
    # Optionnel : nettoyer après les tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def mock_rabbitmq(monkeypatch):
    """
    Mock RabbitMQ pour chaque test.
    - Tolère l'absence de publish_topic (legacy fanout).
    - Capture toutes les publications dans rmod._published_events.
    """
    import app.core.rabbitmq as rmod
    published = []

    async def _noop(*args, **kwargs):
        return None

    async def _fake_publish(exchange_name, message):
        published.append(("fanout", exchange_name, None, message))

    async def _fake_publish_topic(exchange_name, routing_key, message):
        published.append(("topic", exchange_name, routing_key, message))

    monkeypatch.setattr(rmod.rabbitmq, "connect", _noop, raising=False)
    monkeypatch.setattr(rmod.rabbitmq, "disconnect", _noop, raising=False)
    monkeypatch.setattr(rmod.rabbitmq, "publish", _fake_publish, raising=False)

    if not hasattr(rmod.rabbitmq, "publish_topic"):
        rmod.rabbitmq.publish_topic = types.MethodType(_fake_publish_topic, rmod.rabbitmq)
    else:
        monkeypatch.setattr(rmod.rabbitmq, "publish_topic", _fake_publish_topic, raising=False)

    rmod._published_events = published
    yield


@pytest.fixture()
def client(setup_test_db):
    """
    Crée le TestClient APRES patch DB & mocks.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
