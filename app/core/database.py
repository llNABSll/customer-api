from __future__ import annotations

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


# --- Base déclarative ---
class Base(DeclarativeBase):
    """Base pour tous les modèles SQLAlchemy."""


# --- Engine SQLAlchemy ---
engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    echo=getattr(settings, "DB_ECHO", False),
)

# --- Session factory ---
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def init_db() -> None:
    """
    Enregistre tous les modèles et crée les tables manquantes.
    IMPORTANT: il faut que les modules de modèles soient importés
    avant d'appeler Base.metadata.create_all().
    """
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("DB init: tables ensured")


# --- Dépendance FastAPI pour obtenir une session ---
def get_db():
    db = SessionLocal()
    logger.debug("db session opened")
    try:
        yield db
    except Exception:
        try:
            db.rollback()
            logger.exception("db session rolled back due to exception")
        except Exception:
            logger.exception("db rollback failed")
        raise
    finally:
        try:
            db.close()
            logger.debug("db session closed")
        except Exception:
            logger.exception("db session close failed")
