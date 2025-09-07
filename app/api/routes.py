from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool

from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.repositories.client import create_client, get_client, get_clients, update_client, delete_client
from app.core.database import SessionLocal
from app.core.logger import logger
from app.core.rabbitmq import rabbitmq
from app.security.security import require_read, require_write

router = APIRouter(prefix="/customers", tags=["Customers"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_write)])
async def create_customer(client_data: ClientCreate, db: Session = Depends(get_db)):
    new_client = await run_in_threadpool(create_client, db, client_data)
    try:
        await rabbitmq.publish_message("customer.created", {
            "id": new_client.id, "name": new_client.name
        })
    except Exception as e:
        logger.error(f"[events] publish failed: {e}")
    return new_client

@router.get("/", response_model=list[ClientOut], dependencies=[Depends(require_read)])
async def list_customers(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return await run_in_threadpool(get_clients, db, skip, limit)

@router.get("/{customer_id}", response_model=ClientOut, dependencies=[Depends(require_read)])
async def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = await run_in_threadpool(get_client, db, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c

@router.put("/{customer_id}", response_model=ClientOut, dependencies=[Depends(require_write)])
async def update_customer(customer_id: int, updates: ClientUpdate, db: Session = Depends(get_db)):
    c = await run_in_threadpool(update_client, db, customer_id, updates)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        await rabbitmq.publish_message("customer.updated", {
            "id": c.id, "status": getattr(c, "status", None)
        })
    except Exception as e:
        logger.error(f"[events] publish failed: {e}")
    return c

@router.delete("/{customer_id}", response_model=dict, dependencies=[Depends(require_write)])
async def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    ok = await run_in_threadpool(delete_client, db, customer_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        await rabbitmq.publish_message("customer.deleted", {"id": customer_id})
    except Exception as e:
        logger.error(f"[events] publish failed: {e}")
    return {"detail": "Customer deleted successfully"}
