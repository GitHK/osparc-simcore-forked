# pylint:disable=redefined-outer-name

import asyncio
from asyncio import Queue
from collections.abc import AsyncIterable, Awaitable, Callable, Coroutine
from datetime import timedelta
from time import time

import pytest
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather
from simcore_service_dynamic_scheduler.services.scheduler._common_models import (
    TaskExecutionResult,
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)
from simcore_service_dynamic_scheduler.services.scheduler._worker_pool import WorkerPool
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture
async def get_worker_pool() -> AsyncIterable[
    Callable[
        [NonNegativeInt, Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]],
        Awaitable[WorkerPool],
    ]
]:
    created_pools: list[WorkerPool] = []

    async def _(
        max_workers: NonNegativeInt,
        worker_result_callback: Callable[
            [TaskUID, TaskExecutionResult], Awaitable[None]
        ],
    ) -> WorkerPool:
        pool = WorkerPool(max_workers, worker_result_callback)
        await pool.setup()
        created_pools.append(pool)
        return pool

    yield _

    for pool in created_pools:
        await pool.shutdown()


@pytest.fixture
def task_finished_results() -> dict[TaskUID, TaskExecutionResult]:
    return {}


@pytest.fixture
def task_finished_callable(
    task_finished_results: dict[TaskUID, TaskExecutionResult]
) -> Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]:
    async def _task_finished_callback(
        task_uid: TaskUID, result: TaskExecutionResult
    ) -> None:
        task_finished_results[task_uid] = result

    return _task_finished_callback


async def _wait_for_result(
    task_finished_results: dict[TaskUID, TaskExecutionResult],
    *,
    task_uid: TaskUID,
    stop_after: NonNegativeInt = 1,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(stop_after),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert task_uid in task_finished_results


async def test_worker_pool_with_ok_result(
    get_worker_pool: Callable[
        [NonNegativeInt, Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]],
        Awaitable[WorkerPool],
    ],
    task_finished_callable: Callable[[TaskUID, TaskExecutionResult], Awaitable[None]],
    task_finished_results: dict[TaskUID, TaskExecutionResult],
):
    worker_pool: WorkerPool = await get_worker_pool(1, task_finished_callable)

    async def _job_ok(to_add: int) -> int:
        return to_add + 2

    await worker_pool.submit("job", _job_ok(40), timedelta(seconds=1))
    await _wait_for_result(task_finished_results, task_uid="job")
    assert task_finished_results["job"] == TaskResultSuccess(value=42)


async def test_worker_pool_with_timed_out_result(
    get_worker_pool: Callable[
        [NonNegativeInt, Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]],
        Awaitable[WorkerPool],
    ],
    task_finished_callable: Callable[[TaskUID, TaskExecutionResult], Awaitable[None]],
    task_finished_results: dict[TaskUID, TaskExecutionResult],
):
    worker_pool: WorkerPool = await get_worker_pool(1, task_finished_callable)

    async def _sleep_for_very_long_time() -> None:
        await asyncio.sleep(1e6)

    await worker_pool.submit("job", _sleep_for_very_long_time(), timedelta(seconds=0.1))
    await _wait_for_result(task_finished_results, task_uid="job")
    assert isinstance(task_finished_results["job"], TaskResultError)
    assert "asyncio.exceptions.TimeoutError" in task_finished_results["job"].error


async def test_worker_pool_with_code_raising_error(
    get_worker_pool: Callable[
        [NonNegativeInt, Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]],
        Awaitable[WorkerPool],
    ],
    task_finished_callable: Callable[[TaskUID, TaskExecutionResult], Awaitable[None]],
    task_finished_results: dict[TaskUID, TaskExecutionResult],
):
    worker_pool: WorkerPool = await get_worker_pool(1, task_finished_callable)

    async def _raises_error() -> None:
        msg = "failing as expected"
        raise RuntimeError(msg)

    await worker_pool.submit("job", _raises_error(), timedelta(seconds=0.1))
    await _wait_for_result(task_finished_results, task_uid="job")
    assert isinstance(task_finished_results["job"], TaskResultError)
    assert (
        task_finished_results["job"].error
        == "builtins.RuntimeError: failing as expected"
    )


async def test_worker_pool_with_timed_task_that_is_cancelled(
    get_worker_pool: Callable[
        [NonNegativeInt, Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]],
        Awaitable[WorkerPool],
    ],
    task_finished_callable: Callable[[TaskUID, TaskExecutionResult], Awaitable[None]],
    task_finished_results: dict[TaskUID, TaskExecutionResult],
):
    worker_pool: WorkerPool = await get_worker_pool(1, task_finished_callable)

    async def _sleep_for_very_long_time() -> None:
        await asyncio.sleep(1e6)

    await worker_pool.submit("job", _sleep_for_very_long_time(), timedelta(seconds=100))
    await worker_pool.cancel_task("job")
    await _wait_for_result(task_finished_results, task_uid="job")

    assert isinstance(task_finished_results["job"], TaskResultCancelledError)


@pytest.mark.parametrize("jobs_in_queue", [1, 10])
@pytest.mark.parametrize("workers", [1, 2, 10])
async def test_worker_poll_workflow(
    get_worker_pool: Callable[
        [NonNegativeInt, Callable[[TaskUID, TaskExecutionResult], Awaitable[None]]],
        Awaitable[WorkerPool],
    ],
    task_finished_callable: Callable[[TaskUID, TaskExecutionResult], Awaitable[None]],
    task_finished_results: dict[TaskUID, TaskExecutionResult],
    jobs_in_queue: int,
    workers: int,
):
    async def _sleeping_worker() -> None:
        await asyncio.sleep(0.1)

    started_jobs: set[TaskUID] = set()

    queue: Queue[tuple[str, Coroutine]] = Queue()

    start = time()

    for i in range(jobs_in_queue):
        task_uid = f"job{i}"
        await queue.put((task_uid, _sleeping_worker()))
        started_jobs.add(task_uid)

    worker_pool: WorkerPool = await get_worker_pool(workers, task_finished_callable)

    # Consume jobs from external queue by removing an element only when workers are available
    for _ in range(jobs_in_queue):
        await worker_pool.wait_for_free_worker(poll_period=0.01)
        tak_uid, coroutine = await queue.get()
        await worker_pool.submit(tak_uid, coroutine, timeout=timedelta(seconds=1))

    # wait for tasks to be finished
    await logged_gather(
        *(
            _wait_for_result(task_finished_results, task_uid=task_uid)
            for task_uid in started_jobs
        )
    )

    elapsed = time() - start
    assert elapsed >= 0.1 * (jobs_in_queue / workers)
