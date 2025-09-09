from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, init_db
from app.infra.events.rabbitmq import rabbitmq, start_consumer 

# Logging
try:
    from app.core.logging import setup_logging, access_log_middleware 
    setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)
    def access_log_middleware(request, call_next):
        return call_next(request)

logger = logging.getLogger("customer-api")

# Prometheus
REQUEST_COUNT = Counter("http_requests_total", "Total des requêtes HTTP", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Latence des requêtes HTTP", ["method", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB connectivity + schema
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("database connection OK")
    except Exception:
        logger.exception("database connectivity check failed")

    try:
        init_db()
    except Exception:
        logger.exception("database init failed")

    # RabbitMQ (connect + consumer)
    try:
        await rabbitmq.connect()

        async def on_event(payload: dict, rk: str):
            logger.info("[customer-api] received %s: %s", rk, payload)

        asyncio.create_task(
            start_consumer(
                rabbitmq.connection,
                rabbitmq.exchange,
                rabbitmq.exchange_type,
                queue_name="q-customer",
                patterns=["product.#", "order.#"],  # écoute product + order
                handler=on_event,
            )
        )
    except Exception:
        logger.exception("RabbitMQ startup failed")

    yield

    try:
        await rabbitmq.disconnect()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", ""),
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
    openapi_url="/openapi.json" if settings.ENV != "prod" else None,
)

# Access log
app.middleware("http")(access_log_middleware)


# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start

    path = request.url.path
    parts = [p for p in path.split("/") if p]
    if "customers" in parts:
        idx = parts.index("customers")
        if len(parts) > idx + 1:
            path = "/customers/{id}"
        else:
            path = "/customers"

    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


# CORS
allow_methods = ["*"] if settings.CORS_ALLOW_METHODS == "*" else [m.strip() for m in settings.CORS_ALLOW_METHODS.split(",") if m.strip()]
allow_headers = ["*"] if settings.CORS_ALLOW_HEADERS == "*" else [h.strip() for h in settings.CORS_ALLOW_HEADERS.split(",") if h.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)

# Tech endpoints
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# Router métier
from app.api.routes import router as customer_router  
app.include_router(customer_router)



