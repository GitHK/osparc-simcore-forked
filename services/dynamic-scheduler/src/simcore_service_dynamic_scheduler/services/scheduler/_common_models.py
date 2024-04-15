from typing import Any, TypeAlias

from pydantic import BaseModel

TaskUID: TypeAlias = str  # Unique identifier provided by th MemoryManager


class TaskResultSuccess(BaseModel):
    value: Any


class TaskResultError(BaseModel):
    error: str
    str_traceback: str


class TaskResultCancelledError(BaseModel):
    ...


TaskExecutionResult: TypeAlias = (
    TaskResultSuccess | TaskResultError | TaskResultCancelledError
)
