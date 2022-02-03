# pylint:disable=redefined-outer-name,unused-argument,too-many-arguments
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Final, Iterator, Set

import aioboto3
import aiopg
import aiopg.sa
import aioredis
import pytest
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from models_library.settings.redis import RedisConfig
from utils import API_PREFIX, get_exported_projects, login_user_and_import_study
from yarl import URL

log = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "catalog",
    "dask-scheduler",
    "director-v2",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]
pytest_simcore_ops_services_selection = ["minio", "adminer"]

S3_DATA_REMOVAL_SECONDS: Final[int] = 2

# FIXTURES


@pytest.fixture(autouse=True)
def __drop_and_recreate_postgres__(
    database_from_template_before_each_function,
) -> Iterator[None]:
    yield


@pytest.fixture(autouse=True)
async def __delete_all_redis_keys__(redis_service: RedisConfig):
    client = await aioredis.create_redis_pool(redis_service.dsn, encoding="utf-8")
    await client.flushall()
    client.close()
    await client.wait_closed()

    yield
    # do nothing on teadown


@pytest.fixture
async def remove_previous_projects() -> None:
    pass


# UTILS


async def _fetch_stored_files(
    minio_config: Dict[str, Any], project_id: ProjectID
) -> Set[str]:

    s3_config: Dict[str, str] = minio_config["client"]

    def _endpoint_url() -> str:
        protocol = "https" if s3_config["secure"] else "http"
        return f"{protocol}://{s3_config['endpoint']}"

    session = aioboto3.Session(
        aws_access_key_id=s3_config["access_key"],
        aws_secret_access_key=s3_config["secret_key"],
    )

    results: Set[str] = set()

    async with session.resource("s3", endpoint_url=_endpoint_url()) as s3:
        bucket = await s3.Bucket(minio_config["bucket_name"])
        async for s3_object in bucket.objects.all():
            key_path = f"{project_id}/"
            if s3_object.key.startswith(key_path):
                results.add(s3_object.key)

    return results


# TESTS


@pytest.mark.parametrize(
    "export_version", get_exported_projects(), ids=(lambda p: p.name)
)
async def test_s3_cleanup_after_removal(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    redis_client: aioredis.Redis,
    export_version: Path,
    docker_registry: str,
    simcore_services_ready: None,
    minio_config: Dict[str, Any],
):

    imported_project_uuid, _ = await login_user_and_import_study(client, export_version)

    async def _files_in_s3() -> Set[str]:
        return await _fetch_stored_files(
            minio_config=minio_config, project_id=imported_project_uuid
        )

    # files should be present in S3 after import
    assert len(await _files_in_s3()) > 0

    url_delete = client.app.router["delete_project"].url_for(
        project_id=str(imported_project_uuid)
    )
    assert url_delete == URL(API_PREFIX + f"/projects/{imported_project_uuid}")
    async with await client.delete(f"{url_delete}", timeout=10) as export_response:
        assert export_response.status == 204, await export_response.text()

    # give it some time to make sure data was removed
    await asyncio.sleep(S3_DATA_REMOVAL_SECONDS)

    # files from S3 should have been removed
    assert await _files_in_s3() == set()
