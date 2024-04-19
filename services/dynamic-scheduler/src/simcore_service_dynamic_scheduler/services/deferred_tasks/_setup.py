from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client
from ._deferred_manager import DeferredManager


def setup_deferred_tasks(app: FastAPI) -> None:
    rabbit_settings: RabbitSettings = app.state.settings.DYNAMIC_SCHEDULER_RABBITMQ

    async def on_startup() -> None:
        app.state.deferred_manager = deferred_manager = DeferredManager(
            rabbit_settings,
            get_redis_client(app, RedisDatabase.DEFERRED_TASKS),
            globals_for_start_context={"app": app},
        )
        await deferred_manager.setup()

    async def on_shutdown() -> None:
        deferred_manager: DeferredManager = app.state.deferred_manager
        await deferred_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
