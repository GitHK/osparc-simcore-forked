from typing import Final

from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client
from ._deferred_manager import DeferredManager

_EXCHANGE_GLOBAL_UNIQUE_NAME: Final[str] = "DYNAMIC_SCHEDULER_DEFERRED_MANAGER"


def setup_scheduler(app: FastAPI) -> None:
    rabbit_settings: RabbitSettings = app.state.settings.DYNAMIC_SCHEDULER_RABBITMQ

    async def on_startup() -> None:
        app.state.deferred_manager = deferred_manager = DeferredManager(
            rabbit_settings,
            get_redis_client(app, RedisDatabase.SCHEDULING),
            exchange_global_unique_name=_EXCHANGE_GLOBAL_UNIQUE_NAME,
            globals_for_start_context={"app": app},
        )
        await deferred_manager.start()

    async def on_shutdown() -> None:
        deferred_manager: DeferredManager = app.state.deferred_manager
        await deferred_manager.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
