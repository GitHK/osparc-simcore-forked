import asyncio
import os
from typing import Any, Dict, Optional, Union

import aiodocker
import httpx
import requests
from async_timeout import timeout
from fastapi import FastAPI
from models_library.projects import Node
from pydantic import PositiveInt
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

SERVICE_WAS_CREATED_BY_DIRECTOR_V2 = 20
SERVICES_ARE_READY_TIMEOUT = 10 * 60
SEPARATOR = "=" * 50


def is_legacy(node_data: Node) -> bool:
    return node_data.label == "LEGACY"


def get_director_v0_patched_url(url: URL) -> URL:
    return URL(str(url).replace("127.0.0.1", "172.17.0.1"))


async def ensure_network_cleanup(
    docker_client: aiodocker.Docker, project_id: str
) -> None:
    network_names = {x["Name"] for x in await docker_client.networks.list()}

    for network_name in network_names:
        if project_id in network_name:
            network = await docker_client.networks.get(network_name)
            try:
                # if there is an error this cleansup the environament
                # useful for development, avoids leaving too many
                # hanging networks
                delete_result = await network.delete()
                assert delete_result is True
            except aiodocker.exceptions.DockerError as e:
                # if the tests succeeds the network will not exists
                str_error = str(e)
                assert "network" in str_error
                assert "not found" in str_error


async def patch_dynamic_service_url(app: FastAPI, node_uuid: str) -> str:
    """
    Normally director-v2 talks via docker-netwoks with the dynamic-sidecar.
    Since the director-v2 was started outside docker and is not
    running in a container, the service port needs to be exposed and the
    url needs to be changed to 172.17.0.1 (docker localhost)

    returns: the local endpoint
    """
    service_name = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_uuid}"
    port = None

    async with aiodocker.Docker() as docker_client:
        async with timeout(SERVICE_WAS_CREATED_BY_DIRECTOR_V2):
            # it takes a bit of time for the port to be auto generated
            # keep trying until it is there
            while port is None:
                services = await docker_client.services.list()
                for service in services:
                    if service["Spec"]["Name"] == service_name:
                        ports = service["Endpoint"].get("Ports", [])
                        if len(ports) == 1:
                            port = ports[0]["PublishedPort"]
                            break

                await asyncio.sleep(1)

    # patch the endppoint inside the scheduler
    scheduler: DynamicSidecarsScheduler = app.state.dynamic_sidecar_scheduler
    endpoint: Optional[str] = None
    async with scheduler._lock:  # pylint: disable=protected-access
        for entry in scheduler._to_observe.values():  # pylint: disable=protected-access
            if entry.scheduler_data.service_name == service_name:
                entry.scheduler_data.dynamic_sidecar.hostname = "172.17.0.1"
                entry.scheduler_data.dynamic_sidecar.port = port

                endpoint = entry.scheduler_data.dynamic_sidecar.endpoint
                assert endpoint == f"http://172.17.0.1:{port}"
                break

    assert endpoint is not None
    return endpoint


async def handle_307_if_required(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, result: httpx.Response
) -> Union[httpx.Response, requests.Response]:
    def _debug_print(
        result: Union[httpx.Response, requests.Response], heading_text: str
    ) -> None:
        print(
            (
                f"{heading_text}\n>>>\n{result.request.method}\n"
                f"{result.request.url}\n{result.request.headers}\n"
                f"<<<\n{result.status_code}\n{result.headers}\n{result.text}\n"
            )
        )

    if result.next_request is not None:
        _debug_print(result, "REDIRECTING[1/2] DV2")

        # replace url endpoint for director-v0 in redirect
        result.next_request.url = httpx.URL(
            str(result.next_request.url).replace(
                "http://director:8080", str(director_v0_url)
            )
        )

        # when both director-v0 and director-v2 were running in containers
        # it was possible to use httpx for GET requests as well
        # since director-v2 is now started on the host directly,
        # a 405 Method Not Allowed is returned
        # using requests is workaround for the issue
        if result.request.method == "GET":
            redirect_result = requests.get(str(result.next_request.url))
        else:
            redirect_result = await director_v2_client.send(result.next_request)

        _debug_print(redirect_result, "REDIRECTING[2/2] DV0")

        return redirect_result

    return result


async def assert_start_service(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    user_id: int,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    basepath: Optional[str],
) -> None:
    data = dict(
        user_id=user_id,
        project_id=project_id,
        service_key=service_key,
        service_version=service_version,
        service_uuid=service_uuid,
        basepath=basepath,
    )
    headers = {
        "x-dynamic-sidecar-request-dns": director_v2_client.base_url.host,
        "x-dynamic-sidecar-request-scheme": director_v2_client.base_url.scheme,
    }

    result = await director_v2_client.post(
        "/dynamic_services", json=data, headers=headers, allow_redirects=False
    )
    result = await handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 201, result.text


async def get_service_data(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    service_uuid: str,
    node_data: Node,
) -> Dict[str, Any]:
    result = await director_v2_client.get(
        f"/dynamic_services/{service_uuid}", allow_redirects=False
    )
    result = await handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 200, result.text

    payload = result.json()
    data = payload["data"] if is_legacy(node_data) else payload
    return data


async def _get_service_state(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    service_uuid: str,
    node_data: Node,
) -> str:
    data = await get_service_data(
        director_v2_client, director_v0_url, service_uuid, node_data
    )
    print("STATUS_RESULT", node_data.label, data["service_state"])
    return data["service_state"]


async def assert_all_services_running(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    workbench: Dict[str, Node],
) -> None:
    async with timeout(SERVICES_ARE_READY_TIMEOUT):
        not_all_services_running = True

        while not_all_services_running:
            service_states = await asyncio.gather(
                *(
                    _get_service_state(
                        director_v2_client=director_v2_client,
                        director_v0_url=director_v0_url,
                        service_uuid=dynamic_service_uuid,
                        node_data=node_data,
                    )
                    for dynamic_service_uuid, node_data in workbench.items()
                )
            )

            # check that no service has failed
            for service_state in service_states:
                assert service_state != "failed"

            are_services_running = [x == "running" for x in service_states]
            not_all_services_running = not all(are_services_running)
            # let the services boot
            await asyncio.sleep(1.0)


async def assert_retrieve_service(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, service_uuid: str
) -> None:
    headers = {
        "x-dynamic-sidecar-request-dns": director_v2_client.base_url.host,
        "x-dynamic-sidecar-request-scheme": director_v2_client.base_url.scheme,
    }

    result = await director_v2_client.post(
        f"/dynamic_services/{service_uuid}:retrieve",
        json=dict(port_keys=[]),
        headers=headers,
        allow_redirects=False,
    )
    result = await handle_307_if_required(director_v2_client, director_v0_url, result)

    assert result.status_code == 200, result.text
    json_result = result.json()
    print(f"{service_uuid}:retrieve result ", json_result)

    size_bytes = json_result["data"]["size_bytes"]
    assert size_bytes > 0
    assert type(size_bytes) == int


async def assert_stop_service(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, service_uuid: str
) -> None:
    result = await director_v2_client.delete(
        f"/dynamic_services/{service_uuid}", allow_redirects=False
    )
    result = await handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 204
    assert result.text == ""


def _run_command(command: str) -> str:
    # using asyncio.create_subprocess_shell is slower
    # and sometimes ir randomly hangs forever

    print(f"Running: '{command}'")
    command_result = os.popen(command).read()
    print(command_result)
    return command_result


async def port_forward_service(  # pylint: disable=redefined-outer-name
    service_name: str, is_legacy: bool, internal_port: PositiveInt
) -> PositiveInt:
    """Updates the service configuration and makes it so it can be used"""
    # By updating the service spec the container will be recreated.
    # It works in this case, since we do not care about the internal
    # state of the application
    target_service = service_name

    if is_legacy:
        # Legacy services are started --endpoint-mode dnsrr, it needs to
        # be changed to vip otherwise the port forward will not work
        result = _run_command(
            f"docker service update {service_name} --endpoint-mode=vip"
        )
        assert "verify: Service converged" in result
    else:
        # For a non legacy service, the service_name points to the dynamic-sidecar,
        # but traffic is handeled by the proxy,
        target_service = service_name.replace(
            DYNAMIC_SIDECAR_SERVICE_PREFIX, DYNAMIC_PROXY_SERVICE_PREFIX
        )
        # The default prot for the proxy is 80
        internal_port = 80

    # Finally forward the port on a random assigned port.
    result = _run_command(
        f"docker service update {target_service} --publish-add :{internal_port}"
    )
    assert "verify: Service converged" in result

    # inspect service and fetch the port
    async with aiodocker.Docker() as docker_client:
        service_details = await docker_client.services.inspect(target_service)
        ports = service_details["Endpoint"]["Ports"]

        assert len(ports) == 1, service_details
        exposed_port = ports[0]["PublishedPort"]
        return exposed_port


async def assert_service_is_available(  # pylint: disable=redefined-outer-name
    exposed_port: PositiveInt, is_legacy: bool, service_uuid: str
) -> None:
    service_address = (
        f"http://172.17.0.1:{exposed_port}/x/{service_uuid}"
        if is_legacy
        else f"http://172.17.0.1:{exposed_port}"
    )
    print(f"checking service @ {service_address}")

    async for attempt in AsyncRetrying(
        wait=wait_fixed(1.5), stop=stop_after_attempt(60), reraise=True
    ):
        with attempt:
            async with httpx.AsyncClient() as client:
                response = await client.get(service_address)
                print(f"{SEPARATOR}\nAttempt={attempt.retry_state.attempt_number}")
                print(
                    f"Body:\n{response.text}\nHeaders={response.headers}\n{SEPARATOR}"
                )
                assert response.status_code == 200, response.text


async def assert_services_reply_200(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    workbench: Dict[str, Node],
) -> None:
    for service_uuid, node_data in workbench.items():
        service_data = await get_service_data(
            director_v2_client=director_v2_client,
            director_v0_url=director_v0_url,
            service_uuid=service_uuid,
            node_data=node_data,
        )
        print(
            "Checking running service availability",
            service_uuid,
            node_data,
            service_data,
        )
        exposed_port = await port_forward_service(
            service_name=service_data["service_host"],
            is_legacy=is_legacy(node_data),
            internal_port=service_data["service_port"],
        )

        await assert_service_is_available(
            exposed_port=exposed_port,
            is_legacy=is_legacy(node_data),
            service_uuid=service_uuid,
        )
