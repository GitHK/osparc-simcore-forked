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
from typing import Any, ClassVar, Final, Protocol, TypeAlias

from faststream.broker.wrapper import HandlerCallWrapper
from faststream.redis import RedisBroker, RedisRouter

_logger = logging.getLogger(__name__)

router = RedisRouter()


_BASE_DEFER_EXECUTION_NAME: Final[str] = "BaseDeferredExecution"
_LIST_DEFERRED_EXECUTION: Final[str] = "run_deferred"
_LIST_RESPONSE_HANDLER: Final[str] = "deferred_result"


class _RegisterProtocol(Protocol):
    def _register_subscribers_and_publishers(self) -> None:
        pass


class _RouterRegistrationMeta(type, _RegisterProtocol):
    def __new__(cls, name, bases, dct):
        cls_instance = super().__new__(cls, name, bases, dct)
        cls_instance._register_subscribers_and_publishers()  # noqa: SLF001
        return cls_instance


_HandlerName: TypeAlias = str
ClassUniqueReference: TypeAlias = str


class BaseDeferredExecution(metaclass=_RouterRegistrationMeta):
    REGISTERED_HANDLERS: ClassVar[
        dict[ClassUniqueReference, dict[_HandlerName, HandlerCallWrapper]]
    ] = {}

    @classmethod
    def get_class_unique_reference(cls) -> ClassUniqueReference:
        return f"{cls.__module__}.{cls.__name__}"

    @classmethod
    def __track_handler(cls, handler: HandlerCallWrapper, name: str) -> None:
        """keeps track of handlers registered for each subclass of this class"""
        class_path = cls.get_class_unique_reference()
        if class_path not in cls.REGISTERED_HANDLERS:
            cls.REGISTERED_HANDLERS[class_path] = {}
        cls.REGISTERED_HANDLERS[class_path][name] = handler

    @classmethod
    def __get_delivery_config(cls, handler_name: _HandlerName) -> dict[str, Any]:
        # NOTE: specify the delivery method used in publishers and subscribers
        # for Redis, in this case ListSub is used
        return {"list": f"{cls.get_class_unique_reference()}.{handler_name}"}

    @classmethod
    def _register_subscribers_and_publishers(cls) -> None:
        """Method is called automatically when a subclass is loaded

        Automatically subscribes to the router which is going to be used
        by the broker.

        Keeps track of all created handlers by

        """

        if cls.__name__ == _BASE_DEFER_EXECUTION_NAME:
            _logger.debug("Skip handlers registration for %s", cls.__name__)
            return

        _logger.debug("Registering handlers for %s", cls.__name__)

        @router.subscriber(**cls.__get_delivery_config(_LIST_DEFERRED_EXECUTION))
        @router.publisher(**cls.__get_delivery_config(_LIST_RESPONSE_HANDLER))
        async def __run_deferred(*args, **kwargs) -> Any:
            return await cls.run_deferred(*args, **kwargs)

        cls.__track_handler(__run_deferred, "run_deferred")

        @router.subscriber(**cls.__get_delivery_config(_LIST_RESPONSE_HANDLER))
        async def __deferred_result(value: Any) -> None:
            return await cls.deferred_result(value)

        cls.__track_handler(__deferred_result, "deferred_result")

    @classmethod
    async def start_deferred(cls, broker: RedisBroker, **kwargs) -> None:
        await broker.publish(
            kwargs, **cls.__get_delivery_config(_LIST_DEFERRED_EXECUTION)
        )

    @classmethod
    @abstractmethod
    async def run_deferred(cls, *args, **kwargs) -> Any:
        msg = f"make sure '{cls.get_class_unique_reference()}' implements this method"
        raise NotImplementedError(msg)

    @classmethod
    @abstractmethod
    async def deferred_result(cls, value: Any) -> None:
        msg = f"make sure '{cls.get_class_unique_reference()}' implements this method"
        raise NotImplementedError(msg)
