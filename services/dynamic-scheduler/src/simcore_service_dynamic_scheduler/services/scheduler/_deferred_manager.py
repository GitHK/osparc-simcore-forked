import logging
from collections.abc import Awaitable, Callable
from enum import auto
from typing import Any

from faststream.exceptions import NackMessage
from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitRouter
from models_library.utils.enums import StrAutoEnum
from pydantic import NonNegativeInt
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDKHealthChecked
from settings_library.rabbit import RabbitSettings

from ._base_deferred_handler import (
    BaseDeferredHandler,
    FullStartContext,
    UserStartContext,
)
from ._base_memory_manager import BaseMemoryManager
from ._models import (
    ClassUniqueReference,
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)
from ._redis_memory_manager import RedisMemoryManager
from ._task_schedule import TaskSchedule, TaskState
from ._utils import stop_retry_for_unintended_errors
from ._worker_tracker import WorkerTracker

_logger = logging.getLogger(__name__)


class _FastStreamRabbitQueue(StrAutoEnum):
    SCHEDULED = auto()
    SUBMIT_TASK = auto()
    WORKER = auto()

    TASK_RESULT = auto()
    RETRY_PROCESS = auto()

    FINISHED_WITH_ERROR = auto()
    DEFERRED_RESULT = auto()


class _PatchStartDeferred:
    def __init__(
        self,
        *,
        class_unique_reference: ClassUniqueReference,
        handler_to_invoke: Callable[..., Awaitable[UserStartContext]],
        manager_schedule_deferred: Callable[
            [ClassUniqueReference, UserStartContext], Awaitable[None]
        ],
    ):
        self.class_unique_reference = class_unique_reference
        self.handler_to_invoke = handler_to_invoke
        self.manager_schedule_deferred = manager_schedule_deferred

    async def __call__(self, **kwargs) -> None:
        result: UserStartContext = await self.handler_to_invoke(**kwargs)
        await self.manager_schedule_deferred(self.class_unique_reference, result)


class DeferredManager:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        scheduler_redis_sdk: RedisClientSDKHealthChecked,
        *,
        exchange_global_unique_name: str,
        globals_for_start_context: dict[str, Any],
        max_workers: NonNegativeInt = 100,
    ) -> None:

        self._memory_manager: BaseMemoryManager = RedisMemoryManager(
            scheduler_redis_sdk
        )

        self._worker_tracker = WorkerTracker(max_workers)

        self.globals_for_start_context = globals_for_start_context

        self._patched_deferred_handlers: dict[
            ClassUniqueReference, type[BaseDeferredHandler]
        ] = {}

        self.broker = RabbitBroker(rabbit_settings.dsn)
        self.router = RabbitRouter()
        self.exchange = RabbitExchange(exchange_global_unique_name)

    def register_based_deferred_handlers(self) -> None:
        """Allows subclasses of ``BaseDeferredHandler`` to be scheduled.

        NOTE: If a new subclass of ``BaseDeferredHandler`` was defined after
        the call to ``Scheduler.setup()`` this should be called to allow for
        scheduling.
        """
        for subclass in BaseDeferredHandler.SUBCLASSES:
            class_unique_reference: ClassUniqueReference = (
                subclass.get_class_unique_reference()
            )
            if class_unique_reference in self._patched_deferred_handlers:
                _logger.debug("Already patched handler for %s", class_unique_reference)
                continue

            _logger.debug("Patching handler for %s", class_unique_reference)
            subclass.start_deferred = _PatchStartDeferred(
                class_unique_reference=class_unique_reference,
                handler_to_invoke=subclass.start_deferred,
                manager_schedule_deferred=self.__schedule_deferred,
            )
            self._patched_deferred_handlers[class_unique_reference] = subclass

            # checks
            retries = subclass.get_retries()
            if retries < 1:
                msg = f"Must provide at least 1 retry for {class_unique_reference} for {subclass}, not {retries=}"
                raise ValueError(msg)

    def __get_subclass(
        self, class_unique_reference: ClassUniqueReference
    ) -> type[BaseDeferredHandler]:
        return self._patched_deferred_handlers[class_unique_reference]

    async def __schedule_deferred(
        self,
        class_unique_reference: ClassUniqueReference,
        user_start_context: UserStartContext,
    ) -> None:
        """Assembles TaskSchedule stores it and starts the scheduling chain"""
        # NOTE: this is used internally but triggered by when calling `BaseDeferredHandler.start_deferred`

        _logger.debug(
            "Scheduling '%s' with payload '%s'",
            class_unique_reference,
            user_start_context,
        )

        task_uid = await self._memory_manager.get_task_unique_identifier()
        subclass = self.__get_subclass(class_unique_reference)
        task_schedule = TaskSchedule(
            timeout=await subclass.get_timeout(),
            remaining_retries=subclass.get_retries(),
            class_unique_reference=class_unique_reference,
            user_start_context=user_start_context,
            state=TaskState.SCHEDULED,
        )

        await self._memory_manager.save(task_uid, task_schedule)
        _logger.debug("Scheduled task '%s' with entry: %s", task_uid, task_schedule)

        await self.broker.publish(
            task_uid,
            queue=_FastStreamRabbitQueue.SCHEDULED,
            exchange=self.exchange,
        )

    async def __get_task_schedule(
        self, task_uid: TaskUID, *, expected_state: TaskState
    ) -> TaskSchedule:
        task_schedule = await self._memory_manager.get(task_uid)

        if task_schedule is None:
            msg = f"Could not fond a task_schedule for '{task_uid}'"
            raise RuntimeError(msg)
        if task_schedule.state != expected_state:
            msg = f"Detected unexpected state '{task_schedule.state}', should be: '{expected_state}'"
            raise RuntimeError(msg)

        return task_schedule

    def __get_start_context(self, task_schedule: TaskSchedule) -> FullStartContext:
        return {
            **self.globals_for_start_context,
            **task_schedule.user_start_context,
        }

    @stop_retry_for_unintended_errors
    async def _fs_handle_scheduled(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _logger.debug(
            "Handling state '%s' for task_uid '%s'", TaskState.SCHEDULED, task_uid
        )

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.SCHEDULED
        )

        task_schedule.state = TaskState.SUBMIT_TASK
        await self._memory_manager.save(task_uid, task_schedule)

        await self.broker.publish(
            task_uid,
            queue=_FastStreamRabbitQueue.SUBMIT_TASK,
            exchange=self.exchange,
        )

    @stop_retry_for_unintended_errors
    async def _fs_handle_submit_task(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _logger.debug(
            "Handling state '%s' for task_uid '%s'", TaskState.SUBMIT_TASK, task_uid
        )

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.SUBMIT_TASK
        )
        task_schedule.remaining_retries -= 1
        task_schedule.state = TaskState.WORKER
        await self._memory_manager.save(task_uid, task_schedule)

        await self.broker.publish(
            task_uid,
            queue=_FastStreamRabbitQueue.WORKER,
            exchange=self.exchange,
        )

    @stop_retry_for_unintended_errors
    async def _fs_handle_worker(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _logger.debug(
            "Handling state '%s' for task_uid '%s'",
            TaskState.WORKER,
            task_uid,
        )

        if not self._worker_tracker.has_free_slots():
            # NOTE: puts the message back in rabbit for redelivery since this pool is currently busy
            _logger.debug(
                "All workers in pool are busy, requeuing job for %s", task_uid
            )
            raise NackMessage

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.WORKER
        )

        async with self._worker_tracker:
            with log_context(
                _logger,
                logging.DEBUG,
                "Worker handling task_uid '%s' for %s",
                task_uid,
                task_schedule,
            ):
                subclass = self.__get_subclass(task_schedule.class_unique_reference)
                start_context = self.__get_start_context(task_schedule)
                worker_result = await subclass.run_deferred(start_context)

        _logger.debug("Handling worker result for for task_uid '%s'", task_uid)

        task_schedule.result = worker_result
        # update based on result type
        if isinstance(worker_result, TaskResultSuccess):
            task_schedule.state = TaskState.DEFERRED_RESULT
        elif isinstance(worker_result, TaskResultError):
            if task_schedule.remaining_retries > 0:
                task_schedule.state = TaskState.RETRY_PROCESS
            else:
                task_schedule.state = TaskState.FINISHED_WITH_ERROR
        elif isinstance(worker_result, TaskResultCancelledError):
            task_schedule.state = TaskState.FINISHED_WITH_ERROR

        await self._memory_manager.save(task_uid, task_schedule)

        # publish to correct channel
        queue_name: _FastStreamRabbitQueue | None = None
        match task_schedule.state:
            case TaskState.RETRY_PROCESS:
                queue_name = _FastStreamRabbitQueue.RETRY_PROCESS
            case TaskState.FINISHED_WITH_ERROR:
                queue_name = _FastStreamRabbitQueue.FINISHED_WITH_ERROR
            case TaskState.DEFERRED_RESULT:
                queue_name = _FastStreamRabbitQueue.DEFERRED_RESULT

        if queue_name is None:
            msg = (
                f"unexpected, did not find a queue for task_state={task_schedule.state}"
            )
            raise RuntimeError(msg)

        await self.broker.publish(task_uid, queue=queue_name, exchange=self.exchange)

    @stop_retry_for_unintended_errors
    async def _fs_handle_retry_process(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _logger.debug(
            "Handling state '%s' for task_uid '%s'", TaskState.RETRY_PROCESS, task_uid
        )

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.RETRY_PROCESS
        )
        task_schedule.state = TaskState.SUBMIT_TASK
        await self._memory_manager.save(task_uid, task_schedule)

        await self.broker.publish(
            task_uid, queue=_FastStreamRabbitQueue.SUBMIT_TASK, exchange=self.exchange
        )

    async def __remove_task(self, task_uid: TaskUID) -> None:
        _logger.debug("Removing task %s", task_uid)
        await self._memory_manager.remove(task_uid)

    @stop_retry_for_unintended_errors
    async def _fs_handle_finished_with_error(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _logger.debug(
            "Handling state '%s' for task_uid '%s'",
            TaskState.FINISHED_WITH_ERROR,
            task_uid,
        )

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.FINISHED_WITH_ERROR
        )
        if not isinstance(
            task_schedule.result, TaskResultError | TaskResultCancelledError
        ):
            msg = (
                f"Received unexpected result '{task_schedule.result}' was expecting an "
                f"instance of: {TaskResultError.__name__} | {TaskResultCancelledError.__name__}"
            )
            raise TypeError(msg)

        if isinstance(task_schedule.result, TaskResultError):
            _logger.error(
                "Finished task_uid '%s' with error: %s",
                task_uid,
                task_schedule.result.format_error(),
            )
            subclass = self.__get_subclass(task_schedule.class_unique_reference)
            start_context = self.__get_start_context(task_schedule)
            await subclass.on_finished_with_error(task_schedule.result, start_context)

        await self.__remove_task(task_uid)

    @stop_retry_for_unintended_errors
    async def _fs_handle_deferred_result(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _logger.debug(
            "Handling state '%s' for task_uid '%s'", TaskState.DEFERRED_RESULT, task_uid
        )

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.DEFERRED_RESULT
        )
        if not isinstance(task_schedule.result, TaskResultSuccess):
            msg = (
                f"Received unexpected result '{task_schedule.result}' was expecting an "
                f"instance of {TaskResultSuccess.__name__}"
            )
            raise TypeError(msg)

        subclass = self.__get_subclass(task_schedule.class_unique_reference)
        start_context = self.__get_start_context(task_schedule)
        await subclass.on_deferred_result(task_schedule.result.value, start_context)

        await self.__remove_task(task_uid)

    def _register_subscribers(self) -> None:
        """
        Registers subscribers at runtime instead of import time.
        Enables for code reuse.
        """

        self._fs_handle_scheduled = self.router.subscriber(
            queue=_FastStreamRabbitQueue.SCHEDULED, exchange=self.exchange
        )(self._fs_handle_scheduled)

        self._fs_handle_submit_task = self.router.subscriber(
            queue=_FastStreamRabbitQueue.SUBMIT_TASK, exchange=self.exchange
        )(self._fs_handle_submit_task)

        self._fs_handle_worker = self.router.subscriber(
            queue=_FastStreamRabbitQueue.WORKER,
            exchange=self.exchange,
            retry=True,
        )(self._fs_handle_worker)

        self._fs_handle_retry_process = self.router.subscriber(
            queue=_FastStreamRabbitQueue.RETRY_PROCESS, exchange=self.exchange
        )(self._fs_handle_retry_process)

        self._fs_handle_finished_with_error = self.router.subscriber(
            queue=_FastStreamRabbitQueue.FINISHED_WITH_ERROR, exchange=self.exchange
        )(self._fs_handle_finished_with_error)

        self._fs_handle_deferred_result = self.router.subscriber(
            queue=_FastStreamRabbitQueue.DEFERRED_RESULT, exchange=self.exchange
        )(self._fs_handle_deferred_result)

    async def start(self) -> None:
        self._register_subscribers()
        self.broker.include_router(self.router)

        self.register_based_deferred_handlers()

        await self.broker.start()

    async def stop(self) -> None:
        await self.broker.close()


# TESTS WE ABSOLUTELEY NEED:
# -> run the entire DeferredManager in a process and KILL the process while running a long task in the pool
# -> a new process should pick this task up and finish it
