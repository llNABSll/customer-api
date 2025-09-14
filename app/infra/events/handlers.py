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


async def handle_order_created(payload: dict, db: Session) -> None:
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
    except NotFoundError:
        logger.warning("client %s non trouvé pour order.created", customer_id)


async def handle_order_confirmed(payload: dict, db: Session) -> None:
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
    except NotFoundError:
        logger.warning("client %s non trouvé pour order.confirmed", customer_id)


async def handle_order_rejected(payload: dict, db: Session) -> None:
    customer_id = payload.get("customer_id")
    if not customer_id:
        logger.warning("order.rejected sans customer_id")
        return
    logger.info("order.rejected reçu pour client %s", customer_id)


async def handle_order_cancelled(payload: dict, db: Session) -> None:
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
    except NotFoundError:
        logger.warning("client %s non trouvé pour order.cancelled", customer_id)


async def handle_order_deleted(payload: dict, db: Session) -> None:
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
    except NotFoundError:
        logger.warning("client %s non trouvé pour order.deleted", customer_id)
