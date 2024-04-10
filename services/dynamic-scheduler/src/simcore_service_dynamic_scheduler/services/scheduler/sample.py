from ._base import BaseDeferredExecution


class HelloJohn(BaseDeferredExecution):
    @staticmethod
    async def deferred_execution(name: str, user_id: int) -> str:
        return f"Hi {name}@{user_id}!"

    @staticmethod
    async def result_handler(result: str) -> None:
        print(f"Got: {result}")
