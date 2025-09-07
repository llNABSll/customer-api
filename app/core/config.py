from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

class Settings:
    """
    Parité Product/Order:
    - DB: DATABASE_URL sinon CUSTOMER_POSTGRES_* / POSTGRES_* / sinon SQLite.
    - Sécurité: KEYCLOAK_ISSUER + KEYCLOAK_JWKS_URL.
    - Rôles: CUSTOMER_ROLE_* > ROLE_* > défauts.
    - RabbitMQ, Logs, CORS: mêmes clés que Product/Order.
    """
    def __init__(self) -> None:
        # Meta
        self.ENV = os.getenv("ENV", "dev")
        self.APP_NAME = os.getenv("APP_NAME", "customer-api")
        self.APP_TITLE = os.getenv("APP_TITLE", "Customer API - PayeTonKawa")
        self.APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
        self.APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "API Clients CRUD")

        # DB
        self.DATABASE_URL = os.getenv("DATABASE_URL") or self._compose_db_url()
        self.DB_ECHO = _get_bool("DB_ECHO", False)

        # Keycloak
        self.KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER")
        self.KEYCLOAK_JWKS_URL = os.getenv("KEYCLOAK_JWKS_URL") or (
            f"{self.KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
            if self.KEYCLOAK_ISSUER else None
        )

        # Rôles
        self.ROLE_READ  = os.getenv("CUSTOMER_ROLE_READ")  or os.getenv("ROLE_READ",  "customer:read")
        self.ROLE_WRITE = os.getenv("CUSTOMER_ROLE_WRITE") or os.getenv("ROLE_WRITE", "customer:write")

        # RabbitMQ (topic unique 'events')
        # -> essaie RABBITMQ_URL sinon CUSTOMER_RABBITMQ_URL (compat)
        self.RABBITMQ_URL = os.getenv("RABBITMQ_URL") or os.getenv("CUSTOMER_RABBITMQ_URL")
        self.RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "events")
        self.RABBITMQ_EXCHANGE_TYPE = os.getenv("RABBITMQ_EXCHANGE_TYPE", "topic")

        # Logs
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        self.LOG_FILE = os.getenv("LOG_FILE", "app.log")
        self.LOG_ACCESS_FILE = os.getenv("LOG_ACCESS_FILE", "access.log")
        self.LOG_MAX_BYTES = _get_int("LOG_MAX_BYTES", 10 * 1024 * 1024)
        self.LOG_BACKUP_COUNT = _get_int("LOG_BACKUP_COUNT", 5)
        self.LOG_ENABLE_CONSOLE = _get_bool("LOG_ENABLE_CONSOLE", True)

        # CORS
        self.CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")]
        self.CORS_ALLOW_CREDENTIALS = _get_bool("CORS_ALLOW_CREDENTIALS", True)
        self.CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "*")
        self.CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*")

    def _compose_db_url(self) -> str:
        # 1) CUSTOMER_POSTGRES_*
        pg_host = os.getenv("CUSTOMER_POSTGRES_HOST", "customer-db")
        pg_db   = os.getenv("CUSTOMER_POSTGRES_DB")
        pg_user = os.getenv("CUSTOMER_POSTGRES_USER")
        pg_pwd  = os.getenv("CUSTOMER_POSTGRES_PASSWORD", "")
        pg_port = os.getenv("CUSTOMER_POSTGRES_PORT", os.getenv("POSTGRES_PORT", "5432"))

        # 2) POSTGRES_* génériques si absent
        if not (pg_host and pg_db and pg_user):
            pg_host = os.getenv("POSTGRES_HOST", pg_host)
            pg_db   = os.getenv("POSTGRES_DB",   pg_db)
            pg_user = os.getenv("POSTGRES_USER", pg_user)
            pg_pwd  = os.getenv("POSTGRES_PASSWORD", pg_pwd)
            pg_port = os.getenv("POSTGRES_PORT", pg_port)

        if pg_host and pg_db and pg_user:
            return f"postgresql+psycopg2://{pg_user}:{pg_pwd}@{pg_host}:{pg_port}/{pg_db}"

        # 3) SQLite fallback
        sqlite_path = os.getenv("SQLITE_PATH", "data/app.db")
        path = Path(sqlite_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"

settings = Settings()
