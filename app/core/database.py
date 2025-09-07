# app/core/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def _build_database_url() -> str:
    """
    1) Si DATABASE_URL est défini, on l'utilise tel quel.
    2) Sinon, on tente de construire l'URL Postgres via les variables POSTGRES_*.
    3) Si rien n'est exploitable, on retombe sur SQLite local (utile en dev/tests).
    """
    # 1) URL directe
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url

    # 2) Construction depuis POSTGRES_*
    user = os.getenv("POSTGRES_USER") or ""
    password = os.getenv("POSTGRES_PASSWORD") or ""
    db = os.getenv("POSTGRES_DB") or ""
    host = os.getenv("POSTGRES_SERVER") or "localhost"
    port = os.getenv("POSTGRES_PORT") or "5432"

    # Si on a au moins une base, on tente Postgres
    if db:
        auth = f"{user}:{password}@" if user or password else ""
        hostport = f"{host}:{port}" if port else host
        return f"postgresql://{auth}{hostport}/{db}"

    # 3) Fallback sûr
    return "sqlite:///./app.db"

DATABASE_URL = _build_database_url()

# Pour SQLite, il faut check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Dépendance FastAPI — indispensable pour que les tests puissent monkeypatcher SessionLocal
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

__all__ = ["Base", "engine", "SessionLocal", "get_db"]
 