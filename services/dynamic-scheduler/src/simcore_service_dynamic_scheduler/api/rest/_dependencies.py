from fastapi import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.redis import RedisClientSDKHealthChecked
from simcore_service_dynamic_scheduler.services.redis import (
    REDIS_CLIENTS,
    get_redis_client,
)

from ...services.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_server

assert get_app  # nosec
assert get_reverse_url_mapper  # nosec


def get_rabbitmq_client_from_request(request: Request) -> RabbitMQClient:
    return get_rabbitmq_client(request.app)


def get_rabbitmq_rpc_server_from_request(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_server(request.app)


def get_redis_clients_from_request(
    request: Request,
) -> list[RedisClientSDKHealthChecked]:
    return [get_redis_client(request.app, x) for x in REDIS_CLIENTS]


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
