import asyncio
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Final, Optional

import aio_pika
from aio_pika.exceptions import AMQPConnectionError, ChannelInvalidStateError
from aio_pika.patterns import RPC
from packaging.version import Version
from pydantic import PositiveFloat
from servicelib.logging_utils import log_context
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

from .rabbitmq_errors import RemoteMethodNotRegisteredError, RPCNotInitializedError
from .rabbitmq_utils import RPCMethodName, RPCNamespace, RPCNamespacedMethodName

log = logging.getLogger(__name__)


def _connection_close_callback(sender: Any, exc: Optional[BaseException]) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            log.info("Rabbit connection was cancelled")
        else:
            log.error(
                "Rabbit connection closed with exception from %s:%s",
                sender,
                exc,
            )


def _channel_close_callback(_: Any, exc: Optional[BaseException]) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            log.info("Rabbit channel was cancelled")
        else:
            log.error("Rabbit channel closed with exception from %s", exc)


async def _get_connection(
    rabbit_broker: str, connection_name: str
) -> aio_pika.abc.AbstractRobustConnection:
    # NOTE: to show the connection name in the rabbitMQ UI see there
    # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
    #
    url = f"{rabbit_broker}?name={connection_name}_{socket.gethostname()}_{os.getpid()}"
    connection = await aio_pika.connect_robust(
        url, client_properties={"connection_name": connection_name}
    )
    connection.close_callbacks.add(_connection_close_callback)
    return connection


MessageHandler = Callable[[Any], Awaitable[bool]]
Message = str

_MINUTE: Final[int] = 60
_RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S: Final[int] = 15 * _MINUTE


@dataclass
class RabbitMQClient:
    client_name: str
    settings: RabbitSettings
    _connection_pool: Optional[aio_pika.pool.Pool] = field(init=False, default=None)
    _channel_pool: Optional[aio_pika.pool.Pool] = field(init=False, default=None)

    _rpc_connection: Optional[aio_pika.RobustConnection] = None
    _rpc_channel: Optional[aio_pika.RobustChannel] = None
    _rpc: Optional[RPC] = None

    def __post_init__(self):
        # recommendations are 1 connection per process
        self._connection_pool = aio_pika.pool.Pool(
            _get_connection, self.settings.dsn, self.client_name, max_size=1
        )
        # channels are not thread safe, what about python?
        self._channel_pool = aio_pika.pool.Pool(self._get_channel, max_size=10)

    async def rpc_initialize(self) -> None:
        self._rpc_connection = await aio_pika.connect_robust(
            self.settings.dsn,
            client_properties={
                "connection_name": f"{self.client_name}.rpc.{socket.gethostname()}"
            },
        )
        self._rpc_channel = await self._rpc_connection.channel()

        if Version(aio_pika.__version__) >= Version("9.0.4"):
            log.warning(
                "When all libraries have `aio_pika>=9.0.4` use:"
                "`self._rpc = RPC(self._rpc_channel, host_exceptions=True)`"
                "on the line below"
            )
        self._rpc = RPC(self._rpc_channel)
        await self._rpc.initialize()

    async def close(self) -> None:
        with log_context(log, logging.INFO, msg="Closing connection to RabbitMQ"):
            assert self._channel_pool  # nosec
            await self._channel_pool.close()
            assert self._connection_pool  # nosec
            await self._connection_pool.close()

            # rpc is not always initialized
            if self._rpc is not None:
                await self._rpc.close()
            if self._rpc_channel is not None:
                await self._rpc_channel.close()
            if self._rpc_connection is not None:
                await self._rpc_connection.close()

    async def _get_channel(self) -> aio_pika.abc.AbstractChannel:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            connection: aio_pika.RobustConnection
            channel = await connection.channel()
            channel.close_callbacks.add(_channel_close_callback)
            return channel

    async def ping(self) -> bool:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            connection: aio_pika.RobustConnection
            return connection.connected.is_set()

    async def subscribe(
        self,
        exchange_name: str,
        message_handler: MessageHandler,
        *,
        exclusive_queue: bool = True,
    ) -> None:
        """subscribe to exchange_name calling message_handler for every incoming message
        - exclusive_queue: True means that every instance of this application will receive the incoming messages
        - exclusive_queue: False means that only one instance of this application will reveice the incoming message
        """
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            _DEFAULT_PREFETCH_VALUE = 10  # this value is set to the default for now
            await channel.set_qos(_DEFAULT_PREFETCH_VALUE)

            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
            )

            # NOTE: durable=True makes the queue persistent between RabbitMQ restarts/crashes
            # consumer/publisher must set the same configuration for same queue
            # exclusive means that the queue is only available for THIS very client
            # and will be deleted when the client disconnects
            queue_parameters = {
                "durable": True,
                "exclusive": exclusive_queue,
                "arguments": {"x-message-ttl": _RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S},
            }
            if not exclusive_queue:
                # NOTE: setting a name will ensure multiple instance will take their data here
                queue_parameters |= {"name": exchange_name}
            queue = await channel.declare_queue(**queue_parameters)
            await queue.bind(exchange)

            async def _on_message(
                message: aio_pika.abc.AbstractIncomingMessage,
            ) -> None:
                async with message.process(requeue=True):
                    with log_context(
                        log, logging.DEBUG, msg=f"Message received {message}"
                    ):
                        if not await message_handler(message.body):
                            await message.nack()

            await queue.consume(_on_message)

    async def publish(self, exchange_name: str, message: Message) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
            )
            await exchange.publish(
                aio_pika.Message(message.encode()),
                routing_key="",
            )

    async def rpc_request(
        self,
        namespace: RPCNamespace,
        method_name: RPCMethodName,
        *,
        timeout_s_method: PositiveFloat = 5,
        timeout_s_connection_error: PositiveFloat = 60,
        **kwargs: dict[str, Any],
    ) -> Any:
        """
        Call a remote registered `handler` by providing it's `namespace`, `method_name`
        and `kwargs` containing the key value arguments expected by the remote `handler`.

        param: `timeout_s` amount of seconds to wait for a reply from the remote handler
            invoked via `method_name`
        param: `timeout_s_connection_error` amount of seconds to wait for rabbit to
            be available again in case there was a connection error

        :raises asyncio.TimeoutError: when message expired
        :raises CancelledError: when called :func:`RPC.cancel`
        :raises RuntimeError: internal error
        :raises RemoteMethodNotRegisteredError: when no handler was registered to the
            `namespaced_method_name`
        """

        if not self._rpc:
            raise RPCNotInitializedError()

        namespaced_method_name = RPCNamespacedMethodName.from_namespace_and_method(
            namespace, method_name
        )
        try:
            async for attempt in AsyncRetrying(
                wait=wait_random(2),
                stop=stop_after_delay(timeout_s_connection_error),
                retry=retry_if_exception_type(
                    (AMQPConnectionError, ChannelInvalidStateError)
                ),
                before_sleep=before_sleep_log(log, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    queue_expiration_timeout = timeout_s_method
                    awaitable = self._rpc.call(
                        namespaced_method_name,
                        expiration=queue_expiration_timeout,
                        kwargs=kwargs,
                    )
                    return await asyncio.wait_for(awaitable, timeout=timeout_s_method)
        except aio_pika.MessageProcessError as e:
            if e.args[0] == "Message has been returned":
                raise RemoteMethodNotRegisteredError(
                    method_name=namespaced_method_name, incoming_message=e.args[1]
                ) from e
            raise e

    async def rpc_register_handler(
        self, namespace: RPCNamespace, method_name: RPCMethodName, handler: Awaitable
    ) -> None:
        """
        Bind a local `handler` to a `namespace` and `method_name`.
        The handler can be remotely called by providing the `namespace` and `method_name`

        NOTE: method_name could be computed from the handler, but by design, it is
        left to the caller to do so.
        """

        if self._rpc is None:
            raise RPCNotInitializedError()

        namespaced_method_name = RPCNamespacedMethodName.from_namespace_and_method(
            namespace, method_name
        )
        log.info(
            "RPC registered handler '%s' to queue '%s'", handler, namespaced_method_name
        )
        await self._rpc.register(
            namespaced_method_name,
            handler,
            auto_delete=True,
        )

    async def rpc_unregister_handler(self, handler: Awaitable) -> None:
        """Unbind a locally added `handler`"""

        if self._rpc is None:
            raise RPCNotInitializedError()

        await self._rpc.unregister(handler)
