from typing import Final
from uuid import uuid4

from servicelib.redis import RedisClientSDKHealthChecked
from servicelib.utils import logged_gather
from simcore_service_dynamic_scheduler.services.scheduler._models import TaskUID
from simcore_service_dynamic_scheduler.services.scheduler._task_schedule import (
    TaskSchedule,
)

from ._base_memory_manager import BaseMemoryManager

_MEMORY_MANAGER_PREFIX: Final[str] = "mm:"


def _get_key(task_uid: TaskUID) -> str:
    return f"{_MEMORY_MANAGER_PREFIX}{task_uid}"


class RedisMemoryManager(BaseMemoryManager):
    def __init__(self, redis_sdk: RedisClientSDKHealthChecked) -> None:
        self.redis_sdk = redis_sdk

    async def get_task_unique_identifier(self) -> TaskUID:
        candidate_already_exists = True
        while candidate_already_exists:
            candidate = f"{uuid4()}"
            candidate_already_exists = (
                await self.redis_sdk.redis.get(_get_key(candidate)) is not None
            )
        return TaskUID(candidate)

    async def _get_raw(self, redis_key: str) -> TaskSchedule | None:
        found_data = await self.redis_sdk.redis.get(redis_key)
        return None if found_data is None else TaskSchedule.parse_raw(found_data)

    async def get(self, task_uid: TaskUID) -> TaskSchedule | None:
        return await self._get_raw(_get_key(task_uid))

    async def save(self, task_uid: TaskUID, task_schedule: TaskSchedule) -> None:
        await self.redis_sdk.redis.set(_get_key(task_uid), task_schedule.json())

    async def remove(self, task_uid: TaskUID) -> None:
        await self.redis_sdk.redis.delete(_get_key(task_uid))

    async def list_all(self) -> list[TaskSchedule]:
        return await logged_gather(
            *[
                self._get_raw(x)
                async for x in self.redis_sdk.redis.scan_iter(
                    match=f"{_MEMORY_MANAGER_PREFIX}*"
                )
            ],
            max_concurrency=10,
        )
