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
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_scheduler.services.scheduler._utils import (
    stop_retry_for_unintended_errors,
)
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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


async def assert_called_with(
    handler: HandlerCallWrapper,
    *args,
    stop_after: NonNegativeInt = 1,
):
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(stop_after),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert handler.mock
            handler.mock.assert_called_once_with(*args)


async def test_handler_called_as_expected(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(queue="print_message", exchange=rabbit_exchange)
    async def print_message(some_value: int) -> None:
        print(some_value)

    async with get_test_broker() as test_broker:
        await test_broker.publish(23, queue="print_message", exchange=rabbit_exchange)
        await assert_called_with(print_message, 23)


async def test_handler_with_retries(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="test_nacked_message", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def nacked_message(msg: str) -> None:
        raise NackMessage

    @rabbit_broker.subscriber(
        queue="test_rejected_message", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def rejected_message(msg: str) -> None:
        raise RejectMessage

    @rabbit_broker.subscriber(
        queue="test_message_no_error", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def test_message_no_error(msg: str) -> None:
        print("ok")

    @rabbit_broker.subscriber(
        queue="test_message_raises_user_exception", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def test_message_raises_user_exception(msg: str) -> None:
        msg = "this was an unexpected error"
        raise RuntimeError(msg)

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="test_nacked_message", exchange=rabbit_exchange
        )
        await asyncio.sleep(0.1)
        assert nacked_message.mock
        assert len(nacked_message.mock.call_args_list) > 10

        await test_broker.publish(
            "", queue="test_rejected_message", exchange=rabbit_exchange
        )
        await asyncio.sleep(0.1)
        assert rejected_message.mock
        assert len(rejected_message.mock.call_args_list) == 1

        await test_broker.publish(
            "", queue="test_message_no_error", exchange=rabbit_exchange
        )
        await asyncio.sleep(0.1)
        assert test_message_no_error.mock
        assert len(test_message_no_error.mock.call_args_list) == 1

        await test_broker.publish(
            "", queue="test_message_raises_user_exception", exchange=rabbit_exchange
        )
        await asyncio.sleep(0.1)
        assert test_message_raises_user_exception.mock
        assert len(test_message_raises_user_exception.mock.call_args_list) == 1


# TODO: split this test and add each individual without case
