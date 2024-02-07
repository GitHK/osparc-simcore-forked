import asyncio
import secrets

import typer
from aiodocker.docker import Docker


async def get_running_container_ids(service_name):
    async with Docker() as docker:
        tasks = await docker.tasks.list(filters={"name": service_name})
        return [
            task["Status"]["ContainerStatus"]["ContainerID"]
            for task in tasks
            if task["Status"]["State"] == "running"
        ]


async def stop_container(container_id):
    async with Docker() as docker:
        container = await docker.containers.get(container_id)
        await container.stop()


async def main(service_name: str, replicas: int, sleep_min: int, sleep_max: int):
    while True:
        running_container_ids = await get_running_container_ids(service_name)

        if len(running_container_ids) >= replicas:
            container_to_stop = secrets.choice(running_container_ids)
            print(f"Stopping container: {container_to_stop}")  # noqa: T201
            await stop_container(container_to_stop)

        sleep_duration = sleep_min + secrets.randbelow(sleep_max - sleep_min + 1)
        print(  # noqa: T201
            f"Waiting for {sleep_duration} s before the next iteration..."
        )
        await asyncio.sleep(sleep_duration)


app = typer.Typer()


@app.command()
def run_service_killer(
    service_name: str = typer.Argument(..., help="name of the service"),
    replicas: int = typer.Argument(..., help="service running replicas"),
    sleep_min: int = typer.Argument(10, help="min amount to sleep"),
    sleep_max: int = typer.Argument(10, help="max amount to sleep"),
):
    if sleep_min > sleep_max:
        msg = f"Constraint not respected {sleep_min=} <= {sleep_max}"
        raise ValueError(msg)

    typer.echo(f"Starting service killer for service: {service_name}")
    asyncio.run(main(service_name, replicas, sleep_min, sleep_max))


if __name__ == "__main__":
    app()
