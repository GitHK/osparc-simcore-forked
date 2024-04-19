# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from collections.abc import AsyncIterable
from datetime import timedelta

import pytest
from fastapi import FastAPI
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.redis import RedisClientSDKHealthChecked
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_dynamic_scheduler.services.redis import get_redis_client
from simcore_service_dynamic_scheduler.services.scheduler._models import TaskUID
from simcore_service_dynamic_scheduler.services.scheduler._redis_memory_manager import (
    RedisMemoryManager,
)
from simcore_service_dynamic_scheduler.services.scheduler._task_schedule import (
    TaskSchedule,
    TaskState,
)

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def scheduling_redis_sdk(
    app: FastAPI,
) -> AsyncIterable[RedisClientSDKHealthChecked]:
    redis_sdk = get_redis_client(app, RedisDatabase.DEFERRED_TASKS)
    await redis_sdk.redis.flushall()
    yield redis_sdk
    await redis_sdk.redis.flushall()


@pytest.fixture
def task_schedule() -> TaskSchedule:
    return parse_obj_as(
        TaskSchedule,
        {
            "timeout": timedelta(seconds=1),
            "remaining_retries": 1,
            "class_unique_reference": "mock",
            "user_start_context": {},
            "state": TaskState.SCHEDULED,
            "result": None,
        },
    )


async def test_memory_manager_workflow(
    scheduling_redis_sdk: RedisClientSDKHealthChecked, task_schedule: TaskSchedule
):
    memory_manager = RedisMemoryManager(scheduling_redis_sdk)

    task_uid: TaskUID = await memory_manager.get_task_unique_identifier()

    assert await memory_manager.get(task_uid) is None

    await memory_manager.save(task_uid, task_schedule)
    assert await memory_manager.get(task_uid) == task_schedule

    await memory_manager.remove(task_uid)
    assert await memory_manager.get(task_uid) is None


@pytest.mark.parametrize("count", [0, 1, 10, 100, 1000])
async def test_memory_manager_list_all_entries(
    scheduling_redis_sdk: RedisClientSDKHealthChecked,
    task_schedule: TaskSchedule,
    count: int,
):
    memory_manager = RedisMemoryManager(scheduling_redis_sdk)

    async def _make_entry() -> None:
        task_uid = await memory_manager.get_task_unique_identifier()
        await memory_manager.save(task_uid, task_schedule)

    await logged_gather(*(_make_entry() for _ in range(count)))

    entries = await memory_manager.list_all()
    assert len(entries) == count
    assert entries == [task_schedule for _ in range(count)]
