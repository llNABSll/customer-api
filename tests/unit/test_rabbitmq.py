import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infra.events.rabbitmq import RabbitMQ, start_consumer
import aio_pika

@pytest.mark.asyncio
@patch("app.infra.events.rabbitmq.aio_pika.connect_robust")
async def test_rabbitmq_connect(mock_connect_robust):
    """Test the connect method of RabbitMQ."""
    # Arrange
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_connect_robust.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_exchange.return_value = mock_exchange

    rabbitmq = RabbitMQ()

    # Act
    await rabbitmq.connect()

    # Assert
    mock_connect_robust.assert_called_once_with(rabbitmq.url)
    mock_connection.channel.assert_called_once()
    mock_channel.declare_exchange.assert_called_once_with(
        rabbitmq.exchange_name, rabbitmq.exchange_type, durable=True
    )
    assert rabbitmq.connection == mock_connection
    assert rabbitmq.channel == mock_channel
    assert rabbitmq.exchange == mock_exchange

@pytest.mark.asyncio
async def test_rabbitmq_disconnect():
    """Test the disconnect method of RabbitMQ."""
    # Arrange
    rabbitmq = RabbitMQ()
    rabbitmq.connection = AsyncMock()
    rabbitmq.channel = AsyncMock()
    rabbitmq.connection.is_closed = False
    rabbitmq.channel.is_closed = False

    # Act
    await rabbitmq.disconnect()

    # Assert
    rabbitmq.channel.close.assert_called_once()
    rabbitmq.connection.close.assert_called_once()

@pytest.mark.asyncio
async def test_rabbitmq_disconnect_exception():
    """Test exception handling in disconnect."""
    # Arrange
    rabbitmq = RabbitMQ()
    rabbitmq.connection = AsyncMock()
    rabbitmq.channel = AsyncMock()
    rabbitmq.connection.is_closed = False
    rabbitmq.channel.is_closed = False
    rabbitmq.channel.close.side_effect = Exception("Test Exception")
    rabbitmq.connection.close.side_effect = Exception("Test Exception")

    # Act
    await rabbitmq.disconnect()

    # Assert
    rabbitmq.channel.close.assert_called_once()
    rabbitmq.connection.close.assert_called_once()

@pytest.mark.asyncio
async def test_rabbitmq_publish_message_topic():
    """Test the publish_message method of RabbitMQ with a topic exchange."""
    # Arrange
    rabbitmq = RabbitMQ()
    rabbitmq.exchange = AsyncMock()
    rabbitmq.exchange_type = aio_pika.ExchangeType.TOPIC

    routing_key = "test.key"
    message_data = {"key": "value"}

    # Act
    await rabbitmq.publish_message(routing_key, message_data)

    # Assert
    rabbitmq.exchange.publish.assert_called_once()

@pytest.mark.asyncio
async def test_rabbitmq_publish_message_fanout():
    """Test the publish_message method of RabbitMQ with a fanout exchange."""
    # Arrange
    rabbitmq = RabbitMQ()
    rabbitmq.exchange = AsyncMock()
    rabbitmq.exchange_type = aio_pika.ExchangeType.FANOUT

    routing_key = "test.key"
    message_data = {"key": "value"}

    # Act
    await rabbitmq.publish_message(routing_key, message_data)

    # Assert
    rabbitmq.exchange.publish.assert_called_once()
    assert rabbitmq.exchange.publish.call_args[1]["routing_key"] == ""

@pytest.mark.asyncio
async def test_rabbitmq_publish_message_no_exchange():
    """Test that publish_message does not publish if exchange is not available."""
    # Arrange
    rabbitmq = RabbitMQ()
    rabbitmq.exchange = None

    # Act
    await rabbitmq.publish_message("some.key", {"data": "value"})

    # Assert
    pass

@pytest.mark.asyncio
async def test_rabbitmq_publish_message_exception():
    """Test exception handling in publish_message."""
    rabbitmq = RabbitMQ()
    rabbitmq.exchange = AsyncMock()
    rabbitmq.exchange.publish.side_effect = Exception("Test Exception")

    await rabbitmq.publish_message("some.key", {"data": "value"})

# ... (tout le reste de ton fichier inchangé au-dessus)

class StopConsumer(Exception):
    pass

@pytest.mark.asyncio
async def test_start_consumer_topic():
    """Test the start_consumer function with a topic exchange."""
    # Arrange
    connection = AsyncMock()
    exchange = AsyncMock()
    exchange.name = "test_exchange"
    exchange_type = aio_pika.ExchangeType.TOPIC
    queue_name = "test_queue"
    patterns = ["pattern1", "pattern2"]

    # 🔁 Le consumer n'élève pas les erreurs, donc on ne met PAS de side_effect ici
    handler = AsyncMock()

    channel = AsyncMock()
    connection.channel.return_value = channel

    queue = AsyncMock()
    channel.declare_queue.return_value = queue

    message = AsyncMock()
    message.routing_key = "pattern1"
    message.body = b'{"key": "value"}'

    # --- iterator async (context manager) ---
    async def async_iterator(items):
        for item in items:
            yield item

    iterator = async_iterator([message])

    # ✅ queue.iterator() est un context manager async
    queue.iterator = MagicMock()
    queue.iterator.return_value.__aenter__ = AsyncMock(return_value=iterator)
    queue.iterator.return_value.__aexit__ = AsyncMock(return_value=None)

    # ✅ message.process() est un context manager async
    message.process = MagicMock()
    message.process.return_value.__aenter__ = AsyncMock(return_value=message)
    message.process.return_value.__aexit__ = AsyncMock(return_value=None)

    # Act — pas d'exception attendue
    await start_consumer(connection, exchange, exchange_type, queue_name, patterns, handler)

    # Assert
    channel.set_qos.assert_called_once_with(prefetch_count=16)
    channel.declare_queue.assert_called_once_with(queue_name, durable=True, auto_delete=False)
    assert queue.bind.call_count == len(patterns)
    handler.assert_called_once_with({"key": "value"}, "pattern1")
