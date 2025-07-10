# app/main.py

from fastapi import FastAPI
from app.api.routes import router as api_router
from app.core.logger import logger
from app.core.database import Base, engine
from app.models.client import Client

app = FastAPI(
    title="Customer API",
    version="1.0.0"
)

@app.on_event("startup")
async def startup():
    logger.info("Lancement de Customer API")
    Base.metadata.create_all(bind=engine)


@app.on_event("shutdown")
async def shutdown():
    logger.info("Arrêt de Customer API")

# inclusion des routes
app.include_router(api_router, prefix="/api")
