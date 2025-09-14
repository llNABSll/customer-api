import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.client_service import CustomerService, NotFoundError

logger = logging.getLogger(__name__)

def _parse_iso(dt: str | None) -> datetime | None:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:
        return None

# ----- ORDER CREATED -----
async def handle_order_created(payload: dict, db: Session):
    """
    Commande créée (statut PENDING) :
    - Met à jour last_order_date si fourni
    - Pas d’incrément sur orders_count (ça reste à la confirmation)
    """
    svc = CustomerService(db, mq=None)
    customer_id = payload.get("customer_id")
    order_date = _parse_iso(payload.get("created_at"))

    if not customer_id:
        logger.warning("order.created sans customer_id")
        return

    try:
        customer = svc.get(customer_id)
        if order_date:
            customer.last_order_date = order_date
        db.commit()
        logger.info("[customer-api] order.created reçu pour client %s", customer_id)
    except NotFoundError:
        logger.warning("[customer-api] client %s non trouvé pour order.created", customer_id)


# ----- ORDER CONFIRMED -----
async def handle_order_confirmed(payload: dict, db: Session):
    """
    Commande confirmée :
    - Incrémente orders_count
    - Met à jour last_order_date à la date commande ou maintenant
    """
    svc = CustomerService(db, mq=None)
    customer_id = payload.get("customer_id")
    order_date = _parse_iso(payload.get("created_at"))

    if not customer_id:
        logger.warning("order.confirmed sans customer_id")
        return

    try:
        customer = svc.get(customer_id)
        customer.orders_count = (customer.orders_count or 0) + 1
        customer.last_order_date = order_date or datetime.utcnow()
        db.commit()
        logger.info("[customer-api] Orders_count++ et last_order_date MAJ pour client %s", customer_id)
    except NotFoundError:
        logger.warning("[customer-api] client %s non trouvé pour order.confirmed", customer_id)

# ----- ORDER REJECTED -----
async def handle_order_rejected(payload: dict, db: Session):
    """
    Commande rejetée :
    - Pas d’incrément. On log l’événement.
    """
    customer_id = payload.get("customer_id")
    if not customer_id:
        logger.warning("order.rejected sans customer_id")
        return
    logger.info("[customer-api] order.rejected reçu pour client %s", customer_id)

# ----- ORDER CANCELLED -----
async def handle_order_cancelled(payload: dict, db: Session):
    """
    Commande annulée :
    - Décrémente orders_count si > 0
    """
    svc = CustomerService(db, mq=None)
    customer_id = payload.get("customer_id")

    if not customer_id:
        logger.warning("order.cancelled sans customer_id")
        return

    try:
        customer = svc.get(customer_id)
        if (customer.orders_count or 0) > 0:
            customer.orders_count -= 1
        db.commit()
        logger.info("[customer-api] Orders_count-- pour client %s", customer_id)
    except NotFoundError:
        logger.warning("[customer-api] client %s non trouvé pour order.cancelled", customer_id)

# ----- ORDER DELETED -----
async def handle_order_deleted(payload: dict, db: Session):
    """
    Commande supprimée :
    - Décrémente orders_count si > 0
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
        logger.info("[customer-api] Orders_count-- pour client %s", customer_id)
    except NotFoundError:
        logger.warning("[customer-api] client %s non trouvé pour order.deleted", customer_id)
