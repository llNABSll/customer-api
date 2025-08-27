# app/core/rabbitmq.py
import os
import json
import logging
import asyncio
import aio_pika

logger = logging.getLogger("RABBITMQ")
logging.basicConfig(level=logging.INFO)

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

class RabbitMQ:
    def __init__(self):
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.abc.AbstractChannel | None = None

    async def connect(self):
        if not RABBITMQ_URL:
            logger.warning("RABBITMQ_URL non défini, RabbitMQ désactivé.")
            return
        try:
            self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self.channel = await self.connection.channel(publisher_confirms=True)
            logger.info("Connecté à RabbitMQ")
        except Exception as e:
            logger.error(f"Échec connexion RabbitMQ: {e}")

    async def disconnect(self):
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            logger.info("Déconnecté de RabbitMQ")
        except Exception as e:
            logger.error(f"Erreur fermeture RabbitMQ: {e}")

    async def send(self, queue_name: str, message: dict | str):
        """Envoi direct dans une file (point-to-point)."""
        if not self.channel:
            logger.error("Canal RabbitMQ indisponible")
            return
        payload = message if isinstance(message, str) else json.dumps(message)
        queue = await self.channel.declare_queue(queue_name, durable=True)
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=payload.encode("utf-8")),
            routing_key=queue.name,
        )
        logger.info(f"[send] -> queue={queue_name} payload={payload}")

    async def publish(self, exchange_name: str, message: dict | str):
        """Publication en fanout (broadcast)."""
        if not self.channel:
            logger.error("Canal RabbitMQ indisponible")
            return
        payload = message if isinstance(message, str) else json.dumps(message)
        exchange = await self.channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )

        msg = aio_pika.Message(
            body=payload.encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        
        await exchange.publish(aio_pika.Message(body=payload.encode("utf-8")), routing_key="")
        logger.info(f"[publish] -> exchange={exchange_name} payload={payload}")

    async def subscribe(self, exchange_name: str, callback):
        """Souscription fanout (optionnel)."""
        if not self.channel:
            logger.error("Canal RabbitMQ indisponible")
            return
        exchange = await self.channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        queue = await self.channel.declare_queue(exclusive=True)
        await queue.bind(exchange)
        await queue.consume(callback)

    # Petit helper utilisable depuis des endpoints sync
    def publish_async(self, exchange_name: str, message: dict | str):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(exchange_name, message))
        except RuntimeError:
            # pas de loop (ex: contexte sync pur), on en crée une
            asyncio.run(self.publish(exchange_name, message))

rabbitmq = RabbitMQ()
