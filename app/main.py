# app/main.py

from fastapi import FastAPI
from app.api.routes import router as api_router
from app.core.logger import logger
from app.core.database import Base, engine
from app.models.client import Client
from app.core.rabbitmq import rabbitmq 

app = FastAPI(
    title="Customer API",
    version="1.0.0"
)

@app.on_event("startup")
async def startup():
    logger.info("Lancement de Customer API")
    Base.metadata.create_all(bind=engine)
    await rabbitmq.connect() 


@app.on_event("shutdown")
async def shutdown():
    logger.info("Arrêt de Customer API")
    await rabbitmq.disconnect() 
    
# inclusion des routes
app.include_router(api_router, prefix="/api")
