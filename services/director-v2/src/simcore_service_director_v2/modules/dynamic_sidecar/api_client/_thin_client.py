from fastapi import FastAPI, status
from httpx import AsyncClient, Timeout, Response
from ._base_client import BaseHThinClient, retry_on_errors, expect_status
from ....core.settings import DynamicSidecarSettings
import logging
from pydantic import AnyHttpUrl
from typing import Optional, Any
import json

logger = logging.getLogger(__name__)


class ThinDynamicSidecarClient(BaseHThinClient):
    API_VERSION = "v1"

    def __init__(self, app: FastAPI):
        settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )

        self._client = AsyncClient(
            timeout=Timeout(
                settings.DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT,
                connect=settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
            )
        )
        self._request_max_retries: int = (
            settings.DYNAMIC_SIDECAR_API_CLIENT_REQUEST_MAX_RETRIES
        )

        # timeouts
        self._health_request_timeout = Timeout(1.0, connect=1.0)
        self._save_restore_timeout = Timeout(
            settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            connect=settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )
        self._restart_containers_timeout = Timeout(
            settings.DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT,
            connect=settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )
        self._attach_detach_network_timeout = Timeout(
            settings.DYNAMIC_SIDECAR_PROJECT_NETWORKS_ATTACH_DETACH_S,
            connect=settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )

    def _get_url(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        postfix: str,
        no_api_version: bool = False,
    ) -> str:
        """formats and returns an url for the request"""
        api_version = "" if no_api_version else f"/{self.API_VERSION}"
        return f"{dynamic_sidecar_endpoint}{api_version}{postfix}"

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def get_health(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/health", no_api_version=True)
        return await self._client.get(url, timeout=self._health_request_timeout)

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def get_containers(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, only_status: bool
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers")
        return await self._client.get(url, params=dict(only_status=only_status))

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, compose_spec: str
    ) -> Response:
        # NOTE: this sometimes takes longer that the default timeout, maybe raise timeout here as well!
        url = self._get_url(dynamic_sidecar_endpoint, "/containers")
        return await self._client.post(url, data=compose_spec)

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def post_containers_down(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers:down")
        return await self._client.post(url)

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_state_save(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/state:save")
        return await self._client.post(url, timeout=self._save_restore_timeout)

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_state_restore(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/state:restore")
        return await self._client.post(url, timeout=self._save_restore_timeout)

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def post_containers_ports_inputs_pull(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        port_keys: Optional[list[str]] = None,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/ports/inputs:pull")
        port_keys = [] if port_keys is None else port_keys
        return await self._client.post(
            url, json=port_keys, timeout=self._save_restore_timeout
        )

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def patch_containers_directory_watcher(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, is_enabled: bool
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/directory-watcher")
        return await self._client.patch(url, json=dict(is_enabled=is_enabled))

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_ports_outputs_dirs(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, outputs_labels: dict[str, Any]
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/ports/outputs/dirs")
        return await self._client.post(url, json=dict(outputs_labels=outputs_labels))

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def post_containers_ports_outputs_pull(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        port_keys: Optional[list[str]] = None,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/ports/outputs:pull")
        return await self._client.post(
            url, json=port_keys, timeout=self._save_restore_timeout
        )

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_ports_outputs_push(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        port_keys: Optional[list[str]] = None,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers/ports/outputs:push")
        return await self._client.post(
            url, json=port_keys, timeout=self._save_restore_timeout
        )

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def get_containers_name(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, dynamic_sidecar_network_name: str
    ) -> Response:
        filters = json.dumps({"network": dynamic_sidecar_network_name})
        url = self._get_url(
            dynamic_sidecar_endpoint, f"/containers/name?filters={filters}"
        )
        return await self._client.get(url=url)

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_restart(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "/containers:restart")
        return await self._client.post(url, timeout=self._restart_containers_timeout)

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_networks_attach(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        container_id: str,
        network_id: str,
        network_aliases: list[str],
    ) -> Response:
        url = self._get_url(
            dynamic_sidecar_endpoint, f"/containers/{container_id}/networks:attach"
        )
        return await self._client.post(
            url,
            json=dict(network_id=network_id, network_aliases=network_aliases),
            timeout=self._attach_detach_network_timeout,
        )

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_networks_detach(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        container_id: str,
        network_id: str,
    ) -> Response:
        url = self._get_url(
            dynamic_sidecar_endpoint, f"/containers/{container_id}/networks:detach"
        )
        return await self._client.post(
            url,
            json=dict(network_id=network_id),
            timeout=self._attach_detach_network_timeout,
        )
