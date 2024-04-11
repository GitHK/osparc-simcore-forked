# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import call

import pytest
from fastapi import FastAPI
from faststream.broker.wrapper import HandlerCallWrapper
from faststream.redis import RedisBroker, TestRedisBroker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.redis import RedisClientSDK
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_dynamic_scheduler.services.scheduler import (
    BaseDeferredExecution,
    _base,
)
from simcore_service_dynamic_scheduler.services.scheduler._setup import get_broker
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "redis",
]


def test_constants_did_not_change_accidentally():
    # pylint:disable=protected-access
    assert (
        _base.BaseDeferredExecution.__name__
        == _base._BASE_DEFER_EXECUTION_NAME  # noqa: SLF001
    )
    assert (
        _base.BaseDeferredExecution.run_deferred.__name__
        == _base._LIST_DEFERRED_EXECUTION  # noqa: SLF001
    )
    assert (
        _base.BaseDeferredExecution.deferred_result.__name__
        == _base._LIST_RESPONSE_HANDLER  # noqa: SLF001
    )


async def _assert_received(
    handler: HandlerCallWrapper,
    *,
    called_with: Any,
    call_count: int = 1,
    timeout_s: float = 1,
) -> None:
    assert handler.mock
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_delay(timeout_s)
    ):
        with attempt:
            assert len(handler.mock.call_args_list) == call_count
            assert handler.mock.call_args_list == [
                call(called_with) for _ in range(call_count)
            ]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def redis_cleanup(app: FastAPI) -> AsyncIterator[None]:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS
    redis_client_sdk = RedisClientSDK(
        settings.build_redis_dsn(RedisDatabase.SCHEDULING)
    )
    await redis_client_sdk.redis.flushdb()
    yield
    await redis_client_sdk.redis.flushdb()


@pytest.fixture
async def test_broker(app: FastAPI) -> AsyncIterator[RedisBroker]:
    async with TestRedisBroker(get_broker(app), with_real=True) as test_broker:
        yield test_broker


# NOTE: classes are defined in outer scope to allow broker
# to register routers with the correct configuration
class SimpleDeferred(BaseDeferredExecution):
    @classmethod
    async def run_deferred(cls, name: str, user_id: int) -> str:
        # this executes remotely
        return f"Hi {name}@{user_id}!"

    @classmethod
    async def deferred_result(cls, value: str) -> None:
        # value contains the return value of deferred_execution
        print(f"Got: {value}")


async def test_message_delivery_works_as_intended(test_broker: RedisBroker):
    assert isinstance(SimpleDeferred.run_deferred, HandlerCallWrapper)
    assert isinstance(SimpleDeferred.deferred_result, HandlerCallWrapper)

    name = "John"
    user_id = 1

    # NOTE: provided arguments must match deferred_execution signature
    await SimpleDeferred.start_deferred(test_broker, name=name, user_id=user_id)

    await _assert_received(
        SimpleDeferred.run_deferred, called_with={"name": name, "user_id": user_id}
    )
    await _assert_received(
        SimpleDeferred.deferred_result, called_with=f"Hi {name}@{user_id}!"
    )


class WaitingDeferred(BaseDeferredExecution):
    @classmethod
    async def run_deferred(cls, *args, **kwargs) -> bool:
        await asyncio.sleep(0.1)
        return True

    @classmethod
    async def deferred_result(cls, value: bool) -> None:
        assert value is True


async def test_runt_lots_of_multiple_delayed_messages(test_broker: RedisBroker):
    assert isinstance(WaitingDeferred.run_deferred, HandlerCallWrapper)
    assert isinstance(WaitingDeferred.deferred_result, HandlerCallWrapper)

    count = 10

    await logged_gather(
        *[WaitingDeferred.start_deferred(test_broker) for _ in range(count)]
    )

    await _assert_received(
        WaitingDeferred.run_deferred, called_with={}, call_count=count, timeout_s=10
    )
    await _assert_received(
        WaitingDeferred.deferred_result, called_with=True, call_count=count
    )
    # Why are there too many requests inside? what is happening here?

    # TODO: measure timings?
    # rewrite tests to be agnostic form the mocks fo the base. have the handler trigger som mocks that we check


# want a test to figure out hwo to deal with tasks

# -> schedule them at x time in the future
# -> wait for the result and check what it reports

# -> kill the worker while it's trying to fetch the status of the service and schedule more stuff?
#       - killing every 200ms and try to figure out what happens or not


# TEST 1. Multiple instances process the same queue
# -> check that we can subscribe multiple Processes to the same broker on the same lists and see how it works

# TEST 2. Run 1000 requests to a handler that takes 0.1 seconds
# -> check that it does nto take too long to process (max 1 order of magnitude more?)

# TEST to see if messages are requeued dequeued etc..
# -> fetch message and kill the consumer process
# -> see if someone else handles the message!
