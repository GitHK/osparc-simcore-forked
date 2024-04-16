import asyncio
import traceback
from asyncio import CancelledError, Queue, Semaphore, Task
from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from typing import Any

from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.background_task import cancel_task
from servicelib.utils import logged_gather

from ._models import (
    TaskExecutionResult,
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)


def _format_exception(e: BaseException) -> str:
    return f"{e.__class__.__module__}.{e.__class__.__name__}: {e}"


def _get_str_traceback(e: BaseException) -> str:
    return "".join(traceback.format_tb(e.__traceback__))


class WorkerPool:
    """
    A worker pool with functionality to monitor worker usage.
    Can be used in two configuration:
    - classic worker pool: submit jobs and workers will pick them up
        when they are free
    - only when workers are free: call `wait_for_free_worker` and it will
        return when a background worker is available to pick up the next job
    """

    def __init__(
        self,
        max_workers: NonNegativeInt,
        worker_result_callback: Callable[
            [TaskUID, TaskExecutionResult], Awaitable[None]
        ],
    ) -> None:
        self.max_workers = max_workers
        self._worker_result_callback = worker_result_callback
        self._workers: list[Task] = []

        self._semaphore: Semaphore = Semaphore(self.max_workers)

        self._submitted_awaitables: Queue[
            tuple[TaskUID, Coroutine, timedelta]
        ] = Queue()

        self._running_tasks: dict[TaskUID, Task] = {}

    async def wait_for_free_worker(
        self, *, poll_period: NonNegativeFloat = 0.1
    ) -> None:
        """Blocks until a worker is available."""
        while self._semaphore.locked():
            await asyncio.sleep(poll_period)

    async def submit(
        self, task_uid: TaskUID, coroutine: Coroutine, timeout: timedelta
    ) -> None:
        """Enqueue a job to be picked up by the workers"""
        await self._submitted_awaitables.put((task_uid, coroutine, timeout))
        # context switch to allow tasks to be picked up and
        # ``wait_for_free_worker`` to block when called
        await asyncio.sleep(0)

    async def cancel_task(self, task_uid: TaskUID) -> None:
        """cancels running task"""
        if task_uid in self._running_tasks:
            await cancel_task(self._running_tasks[task_uid], timeout=1)

    async def _get_task_with_timeout(
        self, coroutine: Coroutine, *, timeout: timedelta
    ) -> Any:
        return await asyncio.wait_for(coroutine, timeout=timeout.total_seconds())

    async def _worker(self) -> None:
        while True:
            task_uid, coroutine, timeout = await self._submitted_awaitables.get()
            async with self._semaphore:
                self._running_tasks[task_uid] = task = asyncio.create_task(
                    self._get_task_with_timeout(coroutine, timeout=timeout)
                )

                try:
                    result = await task
                    await self._worker_result_callback(
                        task_uid, TaskResultSuccess(value=result)
                    )
                except CancelledError:
                    await self._worker_result_callback(
                        task_uid, TaskResultCancelledError()
                    )
                except Exception as e:  # pylint:disable=broad-exception-caught
                    await self._worker_result_callback(
                        task_uid,
                        TaskResultError(
                            error=_format_exception(e),
                            str_traceback=_get_str_traceback(e),
                        ),
                    )
                finally:
                    del self._running_tasks[task_uid]

    async def setup(self) -> None:
        self._workers = [
            asyncio.create_task(self._worker(), name=f"{self.__class__}-worker-{i}")
            for i in range(self.max_workers)
        ]

    async def shutdown(self) -> None:
        await logged_gather(*(cancel_task(task, timeout=5) for task in self._workers))

    async def __aenter__(self) -> "WorkerPool":
        await self.setup()
        return self

    async def __aexit__(self, *args):
        await self.shutdown()
