# app/infra/events/handlers.py

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.client_service import CustomerService, NotFoundError

logger = logging.getLogger(__name__)


# ----- ORDER CREATED -----
async def handle_order_created(payload: dict, db: Session):
    """
    Quand une commande est créée :
    - incrémente le compteur de commandes du client
    - met à jour la date du dernier achat
    """
    svc = CustomerService(db, mq=None)
    customer_id = payload.get("customer_id")
    order_date = payload.get("created_at")

    if not customer_id:
        logger.warning("order.created sans customer_id")
        return

    try:
        customer = svc.get(customer_id)
        # incrément + update
        customer.orders_count = (customer.orders_count or 0) + 1
        if order_date:
            customer.last_order_date = datetime.fromisoformat(order_date)
        db.commit()
        logger.info(f"[customer-api] Orders_count++ et last_order_date MAJ pour client {customer_id}")
    except NotFoundError:
        logger.warning(f"[customer-api] client {customer_id} non trouvé pour order.created")


# ----- ORDER DELETED -----
async def handle_order_deleted(payload: dict, db: Session):
    """
    Quand une commande est supprimée :
    - décrémente le compteur de commandes du client (si > 0)
    """
    svc = CustomerService(db, mq=None)
    customer_id = payload.get("customer_id")

    if not customer_id:
        logger.warning("order.deleted sans customer_id")
        return

    try:
        customer = svc.get(customer_id)
        if (customer.orders_count or 0) > 0:
            customer.orders_count -= 1
        db.commit()
        logger.info(f"[customer-api] Orders_count-- pour client {customer_id}")
    except NotFoundError:
        logger.warning(f"[customer-api] client {customer_id} non trouvé pour order.deleted")
