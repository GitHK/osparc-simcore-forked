from fastapi import FastAPI
from faststream.redis import RedisBroker
from settings_library.redis import RedisDatabase, RedisSettings

from ._base import router


def setup_scheduler(app: FastAPI) -> None:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS

    async def on_startup() -> None:
        scheduling_dsn = settings.build_redis_dsn(RedisDatabase.SCHEDULING)

        app.state.fast_stream_broker = broker = RedisBroker(scheduling_dsn)
        broker.include_router(router)
        await broker.start()

    async def on_shutdown() -> None:
        broker: RedisBroker = app.state.fast_stream_broker
        await broker.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_broker(app: FastAPI) -> RedisBroker:
    return app.state.fast_stream_broker
