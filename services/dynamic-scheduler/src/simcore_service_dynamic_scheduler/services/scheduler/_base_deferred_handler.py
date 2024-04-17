from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar

from pydantic import NonNegativeInt

from ._models import ClassUniqueReference, TaskResultError

ResultType = TypeVar("ResultType")
UserStartContext: TypeAlias = dict[str, Any]
FullStartContext: TypeAlias = dict[str, Any]


class BaseDeferredHandler(ABC, Generic[ResultType]):
    """Basis for scheduling code that can be ran distributed

    # TODO: writeup usage

    # TODO: add a note to why there is no context manager!
    """

    SUBCLASSES: ClassVar[list[type["BaseDeferredHandler"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDeferredHandler.SUBCLASSES.append(cls)

    @classmethod
    def get_class_unique_reference(cls) -> ClassUniqueReference:
        """returns a unique reference for this class based on the module where it was defined"""
        return f"{cls.__module__}.{cls.__name__}"

    @classmethod
    def get_retries(cls) -> NonNegativeInt:
        """if ``run_deferred`` raises an error other than CancelledError this
        is the maximum number of retries allowed
        """
        return 1

    @classmethod
    @abstractmethod
    async def get_timeout(cls) -> timedelta:
        """return the timeout for the execution of `run_deferred`.
        If `run_deferred` does not finish executing in time a timeout exception will be raised
        """

    @classmethod
    @abstractmethod
    async def start_deferred(cls, **kwargs) -> UserStartContext:
        """
        helper function to be overwritten by the user and generates
        the data passed to run_deferred.

        Inside ``**kwargs`` the ``globals_for_start_context`` are also injected in addition
        to any user provided fields when invoked form the subclass.

        hast to returns: a context context object used during ``run_deferred`` and
            to process the result inside ``deferred_result``
        """

    @classmethod
    @abstractmethod
    async def run_deferred(cls, start_context: FullStartContext) -> ResultType:
        """Code to be run in the background"""

    @classmethod
    @abstractmethod
    async def on_deferred_result(
        cls, result: ResultType, start_context: FullStartContext
    ) -> None:
        """Called in case `run_deferred` ended and provided a successful result"""

    @classmethod
    async def on_finished_with_error(
        cls, error: TaskResultError, start_context: FullStartContext
    ) -> None:
        """
        NOTE: by design this doe nothing.
        Can be overwritten by the user to react to an error. In most cases this is not required.
        """
