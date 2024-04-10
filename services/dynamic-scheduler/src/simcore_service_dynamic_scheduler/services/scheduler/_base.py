# How do I run checks at regular intervals in the future?
#   - check at regular intervals, start when the time has arrived
#   - only schedule a new task if current task finished else skip this run and bump the timer
#   - this way we can aggressively schedule every 0.1 seconds a task that takes 10 seconds to run
#   - keeps track of this in Redis with a Desired state (and Current state) pattern

# How do I run a task get it's results and then do something else
#   - handler with code that I want to execute deferred
#   - logic to handle the result
#   - apply retry logic when the result is received (retry x times give up after x times etc...)
#   - keeps track of this in Redis with a Desired state (and Current state) pattern

import logging
from abc import abstractmethod
from typing import Any, Final

from faststream.redis import RedisBroker, RedisRouter

_logger = logging.getLogger(__name__)

router = RedisRouter()

# create utility to apply router with corerct preofix and more form the original function so they are unique and we can decorate

# wrap below into a class and have everything available?
# how do we dynamically register this?

_BASE_DEFER_EXECUTION_NAME: Final[str] = "BaseDeferredExecution"
_LIST_DEFERRED_EXECUTION: Final[str] = "deferred_execution"
_LIST_RESPONSE_HANDLER: Final[str] = "result_handler"


class DeferredExecutionMeta(type):
    def __new__(cls, name, bases, dct):
        # Create the class
        cls_instance = super().__new__(cls, name, bases, dct)

        # Register the subscribers and publishers
        cls_instance._register_subscribers_and_publishers()

        return cls_instance


class BaseDeferredExecution(metaclass=DeferredExecutionMeta):  # type: ignore
    @classmethod
    def _get_delivery_config(cls, handler_name: str) -> dict[str, Any]:
        # NOTE: configure how to deliver subscribers and publishers
        # also adds the prefix of the current module
        return {"list": f"{cls.__module__}.{cls.__name__}.{handler_name}"}

    @classmethod
    def _register_subscribers_and_publishers(cls) -> None:
        # This will be called automatically when a subclass is created

        if cls.__name__ == _BASE_DEFER_EXECUTION_NAME:
            _logger.debug("Skip handlers registration for %s", cls.__name__)
            return

        _logger.debug("Registering handlers for %s", cls.__name__)

        cls.deferred_execution = router.subscriber(
            **cls._get_delivery_config(_LIST_DEFERRED_EXECUTION)
        )(
            router.publisher(**cls._get_delivery_config(_LIST_RESPONSE_HANDLER))(
                cls.deferred_execution
            )
        )

        cls.result_handler = router.subscriber(
            **cls._get_delivery_config(_LIST_RESPONSE_HANDLER)
        )(cls.result_handler)

    @classmethod
    async def send_emit_request(cls, broker: RedisBroker, **kwargs) -> None:
        await broker.publish(
            kwargs, **cls._get_delivery_config(_LIST_DEFERRED_EXECUTION)
        )

    @staticmethod
    @abstractmethod
    async def deferred_execution(*args, **kwargs) -> Any:
        # TODO add proper types for the result type and the request type via GENERICS
        pass

    @staticmethod
    @abstractmethod
    async def result_handler(result: Any) -> None:
        # TODO add proper types for the result type and the request type via GENERICS
        pass
