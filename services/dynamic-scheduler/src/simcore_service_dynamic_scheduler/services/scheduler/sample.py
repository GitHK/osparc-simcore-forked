from ._base import BaseDeferredExecution


class HelloJohn(BaseDeferredExecution):
    @classmethod
    async def deferred_execution(cls, name: str, user_id: int) -> str:
        return f"Hi {name}@{user_id}!"

    @classmethod
    async def result_handler(cls, result: str) -> None:
        print(f"Got: {result}")
