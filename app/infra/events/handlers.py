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


def _get_service(db: Session) -> CustomerService:
    """Instancie un CustomerService câblé avec RabbitMQ."""
    from app.infra.events.rabbitmq import rabbitmq
    return CustomerService(db, mq=rabbitmq)


# --------------------------
# Handlers
# --------------------------

async def handle_order_created(payload: dict, db: Session) -> None:
    """
    Quand une commande est créée : vérifie que le customer existe.
    -> publie order.customer_validated OU order.rejected.
    """
    svc = _get_service(db)
    order_id = payload.get("order_id")
    customer_id = payload.get("customer_id")
    order_date = _parse_iso(payload.get("created_at"))

    if not customer_id:
        logger.warning("[order.created] commande %s sans customer_id -> rejet", order_id)
        await svc.mq.publish_message("order.rejected", {
            "order_id": order_id,
            "reason": "Missing customer_id"
        })
        return

    try:
        customer = svc.get(customer_id)
        if order_date:
            customer.last_order_date = order_date
        db.commit()

        await svc.mq.publish_message("order.customer_validated", {
            "order_id": order_id,
            "customer_id": customer_id
        })
        logger.info("[order.created] commande %s validée pour customer %s", order_id, customer_id)

    except NotFoundError:
        db.rollback()
        logger.warning("[order.created] client %s introuvable pour commande %s -> rejet",
                       customer_id, order_id)
        await svc.mq.publish_message("order.rejected", {
            "order_id": order_id,
            "reason": f"Customer {customer_id} not found"
        })


async def handle_order_confirmed(payload: dict, db: Session) -> None:
    """
    Quand le stock est confirmé (par product-api).
    -> Customer-api peut mettre à jour ses stats, mais ne rejette jamais.
    """
    svc = _get_service(db)
    order_id = payload.get("order_id")
    customer_id = payload.get("customer_id")
    order_date = _parse_iso(payload.get("created_at"))

    if not order_id:
        logger.warning("[order.confirmed] payload sans order_id -> ignoré")
        return

    if not customer_id:
        # On log seulement, pas de rejet (sinon boucle infinie)
        logger.warning("[order.confirmed] commande %s sans customer_id -> ignoré", order_id)
        return

    try:
        customer = svc.get(customer_id)
        customer.orders_count = (customer.orders_count or 0) + 1
        customer.last_order_date = order_date or datetime.utcnow()
        db.commit()
        logger.info("[order.confirmed] commande %s enregistrée pour customer %s", order_id, customer_id)

    except NotFoundError:
        db.rollback()
        logger.warning("[order.confirmed] client %s introuvable (ignorer, pas de rejet)", customer_id)


async def handle_order_rejected(payload: dict, db: Session) -> None:
    """
    Quand une commande est rejetée (client invalide ou stock insuffisant).
    -> Customer-api logge uniquement, pas de republie.
    """
    order_id = payload.get("order_id")
    reason = payload.get("reason", "Unknown")
    customer_id = payload.get("customer_id")

    logger.info("[order.rejected] commande %s rejetée (reason=%s, customer=%s)",
                order_id, reason, customer_id)


async def handle_order_cancelled(payload: dict, db: Session) -> None:
    svc = _get_service(db)
    order_id = payload.get("order_id")
    customer_id = payload.get("customer_id")

    if not customer_id:
        logger.warning("[order.cancelled] commande %s sans customer_id", order_id)
        return

    try:
        customer = svc.get(customer_id)
        if (customer.orders_count or 0) > 0:
            customer.orders_count -= 1
        db.commit()
        logger.info("[order.cancelled] commande %s annulée pour customer %s", order_id, customer_id)
    except NotFoundError:
        db.rollback()
        logger.warning("[order.cancelled] client %s introuvable", customer_id)


async def handle_order_deleted(payload: dict, db: Session) -> None:
    svc = _get_service(db)
    order_id = payload.get("order_id")
    customer_id = payload.get("customer_id")

    if not customer_id:
        logger.warning("[order.deleted] commande %s sans customer_id", order_id)
        return

    try:
        customer = svc.get(customer_id)
        if (customer.orders_count or 0) > 0:
            customer.orders_count -= 1
        db.commit()
        logger.info("[order.deleted] commande %s supprimée pour customer %s", order_id, customer_id)
    except NotFoundError:
        db.rollback()
        logger.warning("[order.deleted] client %s introuvable", customer_id)
