from asyncio import Semaphore

from pydantic import NonNegativeInt


class WorkerTracker:
    def __init__(self, max_worker_count: NonNegativeInt) -> None:
        self.max_worker_count = max_worker_count
        self._semaphore = Semaphore(max_worker_count)

    def has_free_slots(self) -> bool:
        return not self._semaphore.locked()

    async def __aenter__(self) -> "WorkerTracker":
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *args):
        self._semaphore.release()
