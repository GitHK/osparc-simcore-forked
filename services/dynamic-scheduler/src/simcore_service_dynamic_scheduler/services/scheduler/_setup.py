from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client
from ._base import Scheduler


def setup_scheduler(app: FastAPI) -> None:
    rabbit_settings: RabbitSettings = app.state.settings.DYNAMIC_SCHEDULER_RABBITMQ

    async def on_startup() -> None:
        app.state.scheduler = scheduler = Scheduler(
            rabbit_settings, get_redis_client(app, RedisDatabase.SCHEDULING)
        )
        await scheduler.start()

    async def on_shutdown() -> None:
        scheduler: Scheduler = app.state.scheduler
        await scheduler.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
