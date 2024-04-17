# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from faststream.broker.wrapper import HandlerCallWrapper
from faststream.exceptions import NackMessage, RejectMessage
from faststream.rabbit import (
    RabbitBroker,
    RabbitExchange,
    RabbitRouter,
    TestRabbitBroker,
)
from pydantic import NonNegativeFloat
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_scheduler.services.scheduler._utils import (
    stop_retry_for_unintended_errors,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    disable_redis_setup: None,
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def rabbit_router() -> RabbitRouter:
    return RabbitRouter()


@pytest.fixture
def rabbit_broker(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitBroker:
    return RabbitBroker(rabbit_service.dsn)


@pytest.fixture
async def get_test_broker(
    rabbit_broker: RabbitBroker, rabbit_router: RabbitRouter
) -> Callable[[], AbstractAsyncContextManager[RabbitBroker]]:
    @asynccontextmanager
    async def _() -> AsyncIterator[RabbitBroker]:
        rabbit_broker.include_router(rabbit_router)

        async with TestRabbitBroker(rabbit_broker, with_real=True) as test_broker:
            yield test_broker

    return _


@pytest.fixture
def rabbit_exchange() -> RabbitExchange:
    return RabbitExchange("test_exchange")


async def _get_call_count(
    handler: HandlerCallWrapper, *, wait_for: NonNegativeFloat = 0.1
) -> int:
    await asyncio.sleep(wait_for)
    assert handler.mock
    return len(handler.mock.call_args_list)


async def test_handler_called_as_expected(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(queue="print_message_no_deco", exchange=rabbit_exchange)
    async def print_message_no_deco(some_value: int) -> None:
        print(some_value)

    @rabbit_broker.subscriber(queue="print_message_with_deco", exchange=rabbit_exchange)
    @stop_retry_for_unintended_errors
    async def print_message_with_deco(some_value: int) -> None:
        print(some_value)

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            24, queue="print_message_no_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(print_message_no_deco) == 1

        await test_broker.publish(
            42, queue="print_message_with_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(print_message_with_deco) == 1


async def test_handler_nacks_message(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="nacked_message_no_deco", exchange=rabbit_exchange, retry=True
    )
    async def nacked_message_no_deco(msg: str) -> None:
        raise NackMessage

    @rabbit_broker.subscriber(
        queue="nacked_message_with_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def nacked_message_with_deco(msg: str) -> None:
        raise NackMessage

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="nacked_message_no_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(nacked_message_no_deco) > 10

        await test_broker.publish(
            "", queue="nacked_message_with_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(nacked_message_with_deco) > 10


async def test_handler_rejects_message(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="rejected_message_no_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def rejected_message_no_deco(msg: str) -> None:
        raise RejectMessage

    @rabbit_broker.subscriber(
        queue="rejected_message_with_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def rejected_message_with_deco(msg: str) -> None:
        raise RejectMessage

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="rejected_message_no_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(rejected_message_no_deco) == 1

        await test_broker.publish(
            "", queue="rejected_message_with_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(rejected_message_with_deco) == 1


async def test_handler_unintended_error(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="unintended_error_no_deco", exchange=rabbit_exchange, retry=True
    )
    async def unintended_error_no_deco(msg: str) -> None:
        msg = "this was an unexpected error"
        raise RuntimeError(msg)

    @rabbit_broker.subscriber(
        queue="unintended_error_with_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def unintended_error_with_deco(msg: str) -> None:
        msg = "this was an unexpected error"
        raise RuntimeError(msg)

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="unintended_error_no_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(unintended_error_no_deco) > 10

        await test_broker.publish(
            "", queue="unintended_error_with_deco", exchange=rabbit_exchange
        )
        assert await _get_call_count(unintended_error_with_deco) == 1
