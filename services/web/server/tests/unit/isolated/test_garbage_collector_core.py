# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientSession, web
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
from pytest_mock import MockerFixture
from simcore_service_webserver.garbage_collector_core import (
    _remove_single_service_if_orphan,
    remove_orphaned_services,
)
from yarl import URL


@pytest.fixture
def mock_registry(faker: Faker) -> AsyncMock:
    registry = AsyncMock()
    registry.get_all_resource_keys = AsyncMock(return_value=("test_alive_key", None))
    registry.get_resources = AsyncMock(return_value={"project_id": faker.uuid4()})
    return registry


@pytest.fixture
def mock_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_get_workbench_node_ids_from_project_uuid(
    mocker: MockerFixture, faker: Faker
) -> None:
    mocker.patch(
        "simcore_service_webserver.garbage_collector_core.get_workbench_node_ids_from_project_uuid",
        return_value={faker.uuid4(), faker.uuid4(), faker.uuid4()},
    )


@pytest.fixture
def mock_list_dynamic_services(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.garbage_collector_core.director_v2_api.list_dynamic_services",
        autospec=True,
    )


async def test_regression_remove_orphaned_services_node_ids_unhashable_type_set(
    mock_get_workbench_node_ids_from_project_uuid: None,
    mock_list_dynamic_services: None,
    mock_registry: AsyncMock,
    mock_app: AsyncMock,
):
    await remove_orphaned_services(mock_registry, mock_app)


async def test_regression_project_id_recovered_from_the_wrong_data_structure(
    faker: Faker, mocker: MockerFixture
):
    # tests that KeyError is not raised

    base_module = "simcore_service_webserver.garbage_collector_core"
    mocker.patch(
        f"{base_module}.is_node_id_present_in_any_project_workbench",
        autospec=True,
        return_value=True,
    )
    mocker.patch(
        f"{base_module}.ProjectDBAPI.get_from_app_context",
        autospec=True,
        return_value=AsyncMock(),
    )
    mocker.patch(f"{base_module}.director_v2_api.stop_dynamic_service", autospec=True)

    await _remove_single_service_if_orphan(
        app=AsyncMock(),
        interactive_service={
            "service_host": "host",
            "service_uuid": faker.uuid4(),
            "user_id": 1,
            "project_id": faker.uuid4(),
        },
        currently_opened_projects_node_ids={},
    )


async def test_remove_single_service_if_orphan_service_is_waiting_manual_intervention(
    faker: Faker,
    mocker: MockerFixture,
    aioresponses_mocker: AioResponsesMock,
):

    base_module = "simcore_service_webserver.garbage_collector_core"
    mocker.patch(
        f"{base_module}.is_node_id_present_in_any_project_workbench",
        autospec=True,
        return_value=True,
    )
    mocker.patch(
        f"{base_module}.ProjectDBAPI.get_from_app_context",
        autospec=True,
        return_value=AsyncMock(),
    )

    # mock settings
    mocked_settings = AsyncMock()
    mocked_settings.base_url = URL("http://director-v2:8000/v2")
    mocked_settings.DIRECTOR_V2_STOP_SERVICE_TIMEOUT = 10
    mocker.patch(
        "simcore_service_webserver.director_v2_core_dynamic_services.get_plugin_settings",
        autospec=True,
        return_value=mocked_settings,
    )

    mocker.patch(
        "simcore_service_webserver.director_v2_core_base.get_client_session",
        autospec=True,
        return_value=ClientSession(),
    )

    aioresponses_mocker.delete(
        re.compile(r"^http://[a-z\-_]*director-v2:[0-9]+/v2/dynamic_services.*$"),
        status=web.HTTPBadRequest.status_code,
        payload={"code": "waiting_for_intervention"},
        repeat=True,
    )

    await _remove_single_service_if_orphan(
        app=AsyncMock(),
        interactive_service={
            "service_host": "host",
            "service_uuid": faker.uuid4(),
            "user_id": 1,
            "project_id": faker.uuid4(),
        },
        currently_opened_projects_node_ids={},
    )
