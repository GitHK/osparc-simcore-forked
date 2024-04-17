from typing import Any, TypeAlias

from pydantic import BaseModel

TaskUID: TypeAlias = str  # Unique identifier provided by th MemoryManager
ClassUniqueReference: TypeAlias = str


class TaskResultSuccess(BaseModel):
    value: Any


class TaskResultError(BaseModel):
    # serializes an error form the worker: PC we need to talk on how to do this a bit better
    error: str
    str_traceback: str


class TaskResultCancelledError(BaseModel):
    ...


TaskExecutionResult: TypeAlias = (
    TaskResultSuccess | TaskResultError | TaskResultCancelledError
)
