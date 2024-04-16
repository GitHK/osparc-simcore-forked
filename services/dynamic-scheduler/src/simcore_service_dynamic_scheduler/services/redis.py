from fastapi import FastAPI
from servicelib.redis import RedisClientSDKHealthChecked, RedisClientsManager
from settings_library.redis import RedisDatabase, RedisSettings

REDIS_CLIENTS: set[RedisDatabase] = {RedisDatabase.LOCKS, RedisDatabase.SCHEDULING}


def setup_redis(app: FastAPI) -> None:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS

    async def on_startup() -> None:
        app.state.redis_clients_manager = manager = RedisClientsManager(
            REDIS_CLIENTS, settings
        )
        await manager.setup()

    async def on_shutdown() -> None:
        manager: None | RedisClientsManager = app.state.redis_clients_manager
        if manager:
            await manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(
    app: FastAPI, database: RedisDatabase
) -> RedisClientSDKHealthChecked:
    manager: RedisClientsManager = app.state.redis_clients_manager
    return manager.client(database)
