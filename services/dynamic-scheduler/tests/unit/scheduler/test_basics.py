# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from faststream.broker.wrapper import HandlerCallWrapper
from faststream.redis import RedisBroker, TestRedisBroker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.scheduler import _base
from simcore_service_dynamic_scheduler.services.scheduler.sample import HelloJohn
from simcore_service_dynamic_scheduler.services.scheduler.setup import get_broker
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "redis",
]


def test_preconditions():
    assert _base._BASE_DEFER_EXECUTION_NAME == _base.BaseDeferredExecution.__name__
    assert (
        _base._LIST_DEFERRED_EXECUTION
        == _base.BaseDeferredExecution.deferred_execution.__name__
    )
    assert (
        _base._LIST_RESPONSE_HANDLER
        == _base.BaseDeferredExecution.result_handler.__name__
    )


async def _assert_received(handler: HandlerCallWrapper, called_with: Any) -> None:
    assert handler.mock
    async for attempt in AsyncRetrying(wait=wait_fixed(0.1), stop=stop_after_delay(1)):
        with attempt:
            handler.mock.assert_called_with(called_with)


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def test_broker(app: FastAPI) -> AsyncIterator[RedisBroker]:
    async with TestRedisBroker(get_broker(app), with_real=True) as test_broker:
        yield test_broker


async def test_something(test_broker: RedisBroker):
    name = "John"
    user_id = 1

    assert isinstance(HelloJohn.deferred_execution, HandlerCallWrapper)
    assert isinstance(HelloJohn.result_handler, HandlerCallWrapper)

    await HelloJohn.send_emit_request(test_broker, name=name, user_id=user_id)

    await _assert_received(
        HelloJohn.deferred_execution, {"name": name, "user_id": user_id}
    )
    await _assert_received(HelloJohn.result_handler, f"Hi {name}@{user_id}!")


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
