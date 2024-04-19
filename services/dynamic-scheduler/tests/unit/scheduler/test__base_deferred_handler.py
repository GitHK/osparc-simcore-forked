# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import timedelta
from enum import auto
from typing import Any
from unittest.mock import Mock

import pytest
from models_library.utils.enums import StrAutoEnum
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.redis import RedisClientSDKHealthChecked
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_dynamic_scheduler.services.scheduler._base_deferred_handler import (
    BaseDeferredHandler,
    FullStartContext,
    UserStartContext,
)
from simcore_service_dynamic_scheduler.services.scheduler._deferred_manager import (
    DeferredManager,
)
from simcore_service_dynamic_scheduler.services.scheduler._models import (
    TaskResultError,
    TaskUID,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


class MockKeys(StrAutoEnum):
    START_DEFERRED = auto()
    ON_DEFERRED_CREATED = auto()
    RUN_DEFERRED = auto()
    ON_DEFERRED_RESULT = auto()
    ON_FINISHED_WITH_ERROR = auto()


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def redis_sdk(
    redis_service: RedisSettings,
) -> AsyncIterable[RedisClientSDKHealthChecked]:
    sdk = RedisClientSDKHealthChecked(
        redis_service.build_redis_dsn(RedisDatabase.SCHEDULING)
    )
    await sdk.setup()
    yield sdk
    await sdk.shutdown()


@pytest.fixture
def mocked_deferred_globals() -> dict[str, Any]:
    return {f"global_{i}": Mock for i in range(5)}


@pytest.fixture
async def deferred_manager(
    rabbit_service: RabbitSettings,
    redis_sdk: RedisClientSDKHealthChecked,
    mocked_deferred_globals: dict[str, Any],
) -> AsyncIterable[DeferredManager]:
    manager = DeferredManager(
        rabbit_service, redis_sdk, globals_for_start_context=mocked_deferred_globals
    )

    await manager.setup()
    yield manager
    await manager.shutdown()


@pytest.fixture
async def get_mocked_deferred_handler(
    deferred_manager: DeferredManager,
) -> Callable[
    [int, timedelta, Callable[[], Awaitable[dict]]],
    tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
]:
    def _(
        retry_count: int,
        timeout: timedelta,
        run_deferred: Callable[[], Awaitable[dict]],
    ) -> tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]]:
        mocks: dict[MockKeys, Mock] = {k: Mock() for k in MockKeys}

        class ObservableDeferredHandler(BaseDeferredHandler[dict]):
            @classmethod
            def get_retries(cls) -> int:
                return retry_count

            @classmethod
            async def get_timeout(cls) -> timedelta:
                return timeout

            @classmethod
            async def start_deferred(cls, **kwargs) -> UserStartContext:
                mocks[MockKeys.START_DEFERRED](kwargs)
                return {**kwargs}

            @classmethod
            async def on_deferred_created(cls, task_uid: TaskUID) -> None:
                mocks[MockKeys.ON_DEFERRED_CREATED](task_uid)

            @classmethod
            async def run_deferred(cls, **start_context: FullStartContext) -> dict:
                result = await run_deferred()
                mocks[MockKeys.RUN_DEFERRED](start_context)
                return result

            @classmethod
            async def on_deferred_result(
                cls, result: dict, start_context: FullStartContext
            ) -> None:
                mocks[MockKeys.ON_DEFERRED_RESULT](result, start_context)

            @classmethod
            async def on_finished_with_error(
                cls, error: TaskResultError, start_context: FullStartContext
            ) -> None:
                mocks[MockKeys.ON_FINISHED_WITH_ERROR](error, start_context)

        deferred_manager.register_based_deferred_handlers()

        return mocks, ObservableDeferredHandler

    return _


async def _assert_key(
    mocks: dict[MockKeys, Mock],
    *,
    key: MockKeys,
    count: NonNegativeInt,
    timeout: float = 5,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert len(mocks[key].call_args_list) == count


async def test_deferred_manager_result_ok(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[], Awaitable[dict]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ]
):
    async def _run_deferred_ok() -> dict:
        return {}

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        1, timedelta(seconds=1), _run_deferred_ok
    )

    await mocked_deferred_handler.start_deferred(key="an_arg")

    await _assert_key(mocks, key=MockKeys.START_DEFERRED, count=1)
    await _assert_key(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)
    await _assert_key(mocks, key=MockKeys.RUN_DEFERRED, count=1)
    await _assert_key(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=1)
    await _assert_key(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=0)


async def test_deferred_manager_raised_error(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[], Awaitable[dict]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ]
):
    async def _run_deferred_raises() -> dict:
        msg = "expected error"
        raise RuntimeError(msg)

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        1, timedelta(seconds=1), _run_deferred_raises
    )

    await mocked_deferred_handler.start_deferred(key="an_arg")

    await _assert_key(mocks, key=MockKeys.START_DEFERRED, count=1)
    await _assert_key(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)

    await _assert_key(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=1)
    await _assert_key(mocks, key=MockKeys.RUN_DEFERRED, count=0)
    await _assert_key(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=0)


# TODO: TESTS WE ABSOLUTELEY NEED:
# -> run the entire DeferredManager in a process and KILL the process while running a long task in the pool
# -> a new process should pick this task up and finish it

# TODO: test do not retry if task is cancelled

# TODO: try to some tests to figure out if the handlers require retrying


# TODO add a test for instancing DeferredManager anc chache the exchange_global_unique_name
