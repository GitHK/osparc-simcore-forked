import asyncio

from simcore_service_dynamic_scheduler.services.scheduler._worker_tracker import (
    WorkerTracker,
)


async def _worker(tracker: WorkerTracker) -> None:
    async with tracker:
        await asyncio.sleep(1)


async def test_worker_tracker_full():
    tracker_size = 2
    tracker = WorkerTracker(tracker_size)

    tasks = [asyncio.create_task(_worker(tracker)) for _ in range(tracker_size)]
    # context switch to allow tasks to be picked up
    await asyncio.sleep(0.01)

    assert tracker.has_free_slots() is False
    await asyncio.gather(*tasks)
    assert tracker.has_free_slots() is True


async def test_worker_tracker_filling_up_gradually():
    tracker_size = 10
    tracker = WorkerTracker(tracker_size)

    tasks = []
    for _ in range(tracker_size):
        assert tracker.has_free_slots() is True

        tasks.append(asyncio.create_task(_worker(tracker)))
        # context switch to allow task to be picked up
        await asyncio.sleep(0.01)

    assert tracker.has_free_slots() is False
    await asyncio.gather(*tasks)
    assert tracker.has_free_slots() is True
