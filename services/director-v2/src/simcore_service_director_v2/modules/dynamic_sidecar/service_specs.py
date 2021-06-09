import json
import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional
from uuid import UUID

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.service_settings import (
    ComposeSpecModel,
    PathsMapping,
    SimcoreService,
    SimcoreServiceSetting,
    SimcoreServiceSettings,
)
from models_library.services import ServiceKeyVersion

from ...api.dependencies.director_v0 import DirectorV0Client
from ...core.settings import DynamicSidecarSettings, ServiceType
from ...models.schemas.constants import DYNAMIC_SIDECAR_SERVICE_PREFIX, UserID
from .utils import unused_port

MATCH_SERVICE_TAG = "${SERVICE_TAG}"
MATCH_IMAGE_START = "${REGISTRY_URL}/"
MATCH_IMAGE_END = f":{MATCH_SERVICE_TAG}"


MAX_ALLOWED_SERVICE_NAME_LENGTH: int = 63


log = logging.getLogger(__name__)


def _strip_service_name(service_name: str) -> str:
    """returns: the maximum allowed service name in docker swarm"""
    return service_name[:MAX_ALLOWED_SERVICE_NAME_LENGTH]


def assemble_service_name(service_prefix: str, node_uuid: NodeID) -> str:
    return _strip_service_name("_".join([service_prefix, str(node_uuid)]))


def extract_service_port_from_compose_start_spec(
    create_service_params: Dict[str, Any]
) -> int:
    return create_service_params["labels"]["service_port"]


async def dyn_proxy_entrypoint_assembly(  # pylint: disable=too-many-arguments
    dynamic_sidecar_settings: DynamicSidecarSettings,
    node_uuid: UUID,
    io_simcore_zone: str,
    dynamic_sidecar_network_name: str,
    dynamic_sidecar_network_id: str,
    service_name: str,
    swarm_network_id: str,
    swarm_network_name: str,
    user_id: UserID,
    project_id: ProjectID,
    dynamic_sidecar_node_id: str,
    request_scheme: str,
    request_dns: str,
) -> Dict[str, Any]:
    """This is the entrypoint to the network and needs to be configured properly"""

    mounts = [
        # docker socket needed to use the docker api
        # TODO: needs to be set as readonly
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    return {
        # TODO: use a pydantic model, make the traefik version a setting, log level, etc...
        "labels": {
            "io.simcore.zone": f"{dynamic_sidecar_settings.traefik_simcore_zone}",
            "swarm_stack_name": dynamic_sidecar_settings.swarm_stack_name,
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.customresponseheaders.Content-Security-Policy": f"frame-ancestors {request_dns}",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.accesscontrolallowmethods": "GET,OPTIONS,PUT,POST,DELETE,PATCH,HEAD",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.accessControlAllowOriginList": f"{request_scheme}://{request_dns}",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.accesscontrolmaxage": "100",
            f"traefik.http.middlewares.{service_name}-security-headers.headers.addvaryheader": "true",
            f"traefik.http.services.{service_name}.loadbalancer.server.port": "80",
            f"traefik.http.routers.{service_name}.entrypoints": "http",
            f"traefik.http.routers.{service_name}.priority": "10",
            f"traefik.http.routers.{service_name}.rule": f"hostregexp(`{node_uuid}.services.{{host:.+}}`)",
            f"traefik.http.routers.{service_name}.middlewares": f"{dynamic_sidecar_settings.swarm_stack_name}_gzip@docker, {service_name}-security-headers",
            "type": ServiceType.DEPENDENCY.value,
            "dynamic_type": "dynamic-sidecar",  # tagged as dynamic service
            "study_id": f"{project_id}",
            "user_id": f"{user_id}",
            "uuid": f"{node_uuid}",  # needed for removal when project is closed
        },
        "name": service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {},
                "Hosts": [],
                "Image": "traefik:v2.2.1",
                "Init": True,
                "Labels": {},
                "Command": [
                    "traefik",
                    "--log.level=DEBUG",
                    "--accesslog=true",
                    "--entryPoints.http.address=:80",
                    "--entryPoints.http.forwardedHeaders.insecure",
                    "--providers.docker.endpoint=unix:///var/run/docker.sock",
                    f"--providers.docker.network={dynamic_sidecar_network_name}",
                    "--providers.docker.exposedByDefault=false",
                    f"--providers.docker.constraints=Label(`io.simcore.zone`, `{io_simcore_zone}`)",
                    # inject basic auth https://doc.traefik.io/traefik/v2.0/middlewares/basicauth/
                    # TODO: attach new auth_url to the service and make it available in the monitor
                ],
                "Mounts": mounts,
            },
            "Placement": {
                "Constraints": [
                    "node.platform.os == linux",  # TODO: ask SAN should this be removed?
                    f"node.id == {dynamic_sidecar_node_id}",
                ]
            },
            "Resources": {  # starts from 100 MB and maxes at 250 MB with 10% max CPU usage
                "Limits": {"MemoryBytes": 262144000, "NanoCPUs": 100000000},
                "Reservations": {"MemoryBytes": 104857600, "NanoCPUs": 100000000},
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
        },
    }


def _parse_mount_settings(settings: List[Dict]) -> List[Dict]:
    mounts = list()
    for s in settings:
        log.debug("Retrieved mount settings %s", s)
        mount = dict()
        mount["ReadOnly"] = True
        if "ReadOnly" in s and s["ReadOnly"] in ["false", "False", False]:
            mount["ReadOnly"] = False

        for field in ["Source", "Target", "Type"]:
            if field in s:
                mount[field] = s[field]
            else:
                log.warning(
                    "Mount settings have wrong format. Required keys [Source, Target, Type]"
                )
                continue

        log.debug("Append mount settings %s", mount)
        mounts.append(mount)

    return mounts


def _parse_env_settings(settings: List[str]) -> Dict:
    envs = dict()
    for s in settings:
        log.debug("Retrieved env settings %s", s)
        if "=" in s:
            parts = s.split("=")
            if len(parts) == 2:
                # will be forwarded to dynamic-sidecar spawned containers
                envs[f"FORWARD_ENV_{parts[0]}"] = parts[1]

        log.debug("Parsed env settings %s", s)

    return envs


# pylint: disable=too-many-branches
def _inject_settings_to_create_service_params(
    labels_service_settings: SimcoreServiceSettings,
    create_service_params: Dict[str, Any],
) -> None:
    for param in labels_service_settings:
        param: SimcoreServiceSetting = param
        # NOTE: the below capitalize addresses a bug in a lot of already in use services
        # where Resources was written in lower case
        if param.setting_type.capitalize() == "Resources":
            # python-API compatible for backward compatibility
            if "mem_limit" in param.value:
                create_service_params["task_template"]["Resources"]["Limits"][
                    "MemoryBytes"
                ] = param.value["mem_limit"]
            if "cpu_limit" in param.value:
                create_service_params["task_template"]["Resources"]["Limits"][
                    "NanoCPUs"
                ] = param.value["cpu_limit"]
            if "mem_reservation" in param.value:
                create_service_params["task_template"]["Resources"]["Reservations"][
                    "MemoryBytes"
                ] = param.value["mem_reservation"]
            if "cpu_reservation" in param.value:
                create_service_params["task_template"]["Resources"]["Reservations"][
                    "NanoCPUs"
                ] = param.value["cpu_reservation"]
            # REST-API compatible
            if "Limits" in param.value or "Reservations" in param.value:
                create_service_params["task_template"]["Resources"].update(param.value)

        # publishing port on the ingress network.
        elif param.name == "ports" and param.setting_type == "int":  # backward comp
            create_service_params["labels"]["port"] = create_service_params["labels"][
                "service_port"
            ] = str(param.value)
        # REST-API compatible
        elif param.setting_type == "EndpointSpec":
            if "Ports" in param.value:
                if (
                    isinstance(param.value["Ports"], list)
                    and "TargetPort" in param.value["Ports"][0]
                ):
                    create_service_params["labels"]["port"] = create_service_params[
                        "labels"
                    ]["service_port"] = str(param.value["Ports"][0]["TargetPort"])

        # placement constraints
        elif param.name == "constraints":  # python-API compatible
            create_service_params["task_template"]["Placement"][
                "Constraints"
            ] += param.value
        elif param.setting_type == "Constraints":  # REST-API compatible
            create_service_params["task_template"]["Placement"][
                "Constraints"
            ] += param.value
        elif param.name == "env":
            log.debug("Found env parameter %s", param.value)
            env_settings = _parse_env_settings(param.value)
            if env_settings:
                create_service_params["task_template"]["ContainerSpec"]["Env"].update(
                    env_settings
                )
        elif param.name == "mount":
            log.debug("Found mount parameter %s", param.value)
            mount_settings: List[Dict] = _parse_mount_settings(param.value)
            if mount_settings:
                create_service_params["task_template"]["ContainerSpec"][
                    "Mounts"
                ].extend(mount_settings)

    container_spec = create_service_params["task_template"]["ContainerSpec"]
    # set labels for CPU and Memory limits
    container_spec["Labels"]["nano_cpus_limit"] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["NanoCPUs"]
    )
    container_spec["Labels"]["mem_limit"] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )


def _assemble_key(service_key: str, service_tag: str) -> str:
    return f"{service_key}:{service_tag}"


async def _extract_osparc_involved_service_labels(
    director_v0_client: DirectorV0Client,
    service_key: str,
    service_tag: str,
    service_labels: SimcoreService,
) -> Dict[str, SimcoreService]:
    """
    Returns all the involved oSPARC services from the provided service labels.

    If the service contains a compose-spec that will also be parsed for images.
    Searches for images like the following in the spec:
    - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:${SERVICE_TAG}`
    - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:1.2.3` where `1.2.3` is a hardcoded tag
    """

    # initialize with existing labels
    # stores labels mapped by image_name service:tag
    docker_image_name_by_services: Dict[str, SimcoreService] = {
        _assemble_key(service_key=service_key, service_tag=service_tag): service_labels
    }
    if service_labels.compose_spec is None:
        return docker_image_name_by_services

    # maps form image_name to compose_spec key
    reverse_mapping: Dict[str, str] = {}

    compose_spec_services = service_labels.compose_spec.get("services", {})
    for compose_service_key, service_data in compose_spec_services.items():
        image = service_data.get("image", None)
        if image is None:
            continue

        # if image dose not have this format skip:
        # - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:${SERVICE_TAG}`
        # - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:1.2.3` a hardcoded tag
        if not image.startswith(MATCH_IMAGE_START) or ":" not in image:
            continue
        if not image.startswith(MATCH_IMAGE_START) or not image.endswith(
            MATCH_IMAGE_END
        ):
            continue

        # strips `${REGISTRY_URL}/`; replaces `${SERVICE_TAG}` with `service_tag`
        osparc_image_key = image.replace(MATCH_SERVICE_TAG, service_tag).replace(
            MATCH_IMAGE_START, ""
        )
        current_service_key, current_service_tag = osparc_image_key.split(":")
        involved_key = _assemble_key(
            service_key=current_service_key, service_tag=current_service_tag
        )
        reverse_mapping[involved_key] = compose_service_key

        # if the labels already existed no need to fetch them again
        if involved_key in docker_image_name_by_services:
            continue

        docker_image_name_by_services[
            involved_key
        ] = await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(
                key=current_service_key, version=current_service_tag
            )
        )

    # remaps from image_name as key to compose_spec key
    compose_spec_mapped_labels = {
        reverse_mapping[k]: v for k, v in docker_image_name_by_services.items()
    }
    return compose_spec_mapped_labels


def _add_compose_destination_container_to_settings_entries(
    settings: SimcoreServiceSettings, destination_container: str
) -> List[SimcoreServiceSetting]:
    def _inject_destination_container(
        item: SimcoreServiceSetting,
    ) -> SimcoreServiceSetting:
        # pylint: disable=protected-access
        item._destination_container = destination_container
        return item

    return [_inject_destination_container(x) for x in settings]


def _merge_resources_in_settings(
    settings: Deque[SimcoreServiceSetting],
) -> Deque[SimcoreServiceSetting]:
    """All oSPARC services which have defined resource requirements will be added"""
    result: Deque[SimcoreServiceSetting] = deque()
    resources_entries: Deque[SimcoreServiceSetting] = deque()

    log.debug("merging settings %s", settings)

    for entry in settings:
        entry: SimcoreServiceSetting = entry
        if entry.name == "Resources" and entry.setting_type == "Resources":
            resources_entries.append(entry)
        else:
            result.append(entry)

    if len(resources_entries) <= 1:
        return settings

    # merge all resources
    empty_resource_entry: SimcoreServiceSetting = SimcoreServiceSetting(
        name="Resources",
        setting_type="Resources",
        value={
            "Limits": {"NanoCPUs": 0, "MemoryBytes": 0},
            "Reservations": {
                "NanoCPUs": 0,
                "MemoryBytes": 0,
                "GenericResources": [],
            },
        },
    )

    for resource_entry in resources_entries:
        resource_entry: SimcoreServiceSetting = resource_entry
        limits = resource_entry.value.get("Limits", {})
        empty_resource_entry.value["Limits"]["NanoCPUs"] += limits.get("NanoCPUs", 0)
        empty_resource_entry.value["Limits"]["MemoryBytes"] += limits.get(
            "MemoryBytes", 0
        )

        reservations = resource_entry.value.get("Reservations", {})
        empty_resource_entry.value["Reservations"]["NanoCPUs"] = reservations.get(
            "NanoCPUs", 0
        )
        empty_resource_entry.value["Reservations"]["MemoryBytes"] = reservations.get(
            "MemoryBytes", 0
        )
        empty_resource_entry.value["Reservations"]["GenericResources"] = []
        # put all generic resources together without looking for duplicates
        empty_resource_entry.value["Reservations"]["GenericResources"].extend(
            reservations.get("GenericResources", [])
        )

    result.append(empty_resource_entry)

    return result


def _inject_target_service_into_env_vars(
    settings: Deque[SimcoreServiceSetting],
) -> Deque[SimcoreServiceSetting]:
    """NOTE: this method will modify settings in place"""

    def _forma_env_var(env_var: str, destination_container: str) -> str:
        var_name, var_payload = env_var.split("=")
        json_encoded = json.dumps(
            dict(destination_container=destination_container, env_var=var_payload)
        )
        return f"{var_name}={json_encoded}"

    for entry in settings:
        entry: SimcoreServiceSetting = entry
        if entry.name == "env" and entry.setting_type == "string":
            # process entry
            list_of_env_vars = entry.value if entry.value else []

            # pylint: disable=protected-access
            destination_container = entry._destination_container

            # transforms settings defined environment variables
            # from `ENV_VAR=PAYLOAD`
            # to   `ENV_VAR={"destination_container": "destination_container", "env_var": "PAYLOAD"}`
            entry.value = [
                _forma_env_var(x, destination_container) for x in list_of_env_vars
            ]

    return settings


async def merge_settings_before_use(
    director_v0_client: DirectorV0Client, service_key: str, service_tag: str
) -> SimcoreServiceSettings:

    simcore_service: SimcoreService = await director_v0_client.get_service_labels(
        service=ServiceKeyVersion(key=service_key, version=service_tag)
    )
    log.info("image=%s, tag=%s, labels=%s", service_key, service_tag, simcore_service)

    # paths_mapping express how to map dynamic-sidecar paths to the compose-spec volumes
    # where the service expects to find its certain folders

    labels_for_involved_services: Dict[
        str, SimcoreService
    ] = await _extract_osparc_involved_service_labels(
        director_v0_client=director_v0_client,
        service_key=service_key,
        service_tag=service_tag,
        service_labels=simcore_service,
    )
    logging.info("labels_for_involved_services=%s", labels_for_involved_services)

    # merge the settings from the all the involved services
    settings: Deque[SimcoreServiceSetting] = deque()  # TODO: fix typing here
    for compose_spec_key, service_labels in labels_for_involved_services.items():
        service_settings: SimcoreServiceSettings = service_labels.settings

        settings.extend(
            # inject compose spec key, used to target container specific services
            _add_compose_destination_container_to_settings_entries(
                settings=service_settings, destination_container=compose_spec_key
            )
        )

    settings = _merge_resources_in_settings(settings)
    settings = _inject_target_service_into_env_vars(settings)

    return SimcoreServiceSettings.parse_obj(settings)


async def dynamic_sidecar_assembly(  # pylint: disable=too-many-arguments
    dynamic_sidecar_settings: DynamicSidecarSettings,
    io_simcore_zone: str,
    dynamic_sidecar_network_name: str,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    dynamic_sidecar_name: str,
    user_id: UserID,
    node_uuid: UUID,
    service_key: str,
    service_tag: str,
    paths_mapping: PathsMapping,
    compose_spec: ComposeSpecModel,
    target_container: Optional[str],
    project_id: ProjectID,
    settings: SimcoreServiceSettings,
) -> Dict[str, Any]:
    """This service contains the dynamic-sidecar which will spawn the dynamic service itself"""
    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    endpint_spec = {}

    if dynamic_sidecar_settings.mount_path_dev is not None:
        dynamic_sidecar_path = dynamic_sidecar_settings.mount_path_dev
        if dynamic_sidecar_path is None:
            log.warning(
                (
                    "Could not mount the sources for the dynamic-sidecar, please "
                    "provide env var named DEV_SIMCORE_DYNAMIC_SIDECAR_PATH"
                )
            )
        else:
            mounts.append(
                {
                    "Source": str(dynamic_sidecar_path),
                    "Target": "/devel/services/dynamic-sidecar",
                    "Type": "bind",
                }
            )
            packages_path = (
                dynamic_sidecar_settings.mount_path_dev / ".." / ".." / "packages"
            )
            mounts.append(
                {
                    "Source": str(packages_path),
                    "Target": "/devel/packages",
                    "Type": "bind",
                }
            )
    # expose this service on an empty port
    if dynamic_sidecar_settings.mount_path_dev:
        endpint_spec["Ports"] = [
            {
                "Protocol": "tcp",
                # TODO: letting it empty is enough for the swarm to generate one
                "PublishedPort": unused_port(),
                "TargetPort": dynamic_sidecar_settings.port,
            }
        ]

    # used for the container name to avoid collisions for started containers on the same node
    compose_namespace = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_uuid}"

    create_service_params = {
        # TODO: we might want to have the dynamic-sidecar in the internal registry instead of dockerhub?
        # "auth": {"password": "adminadmin", "username": "admin"},   # maybe not needed together with registry
        "endpoint_spec": endpint_spec,
        "labels": {
            # TODO: let's use a pydantic model with descriptions
            "io.simcore.zone": io_simcore_zone,
            "port": f"{dynamic_sidecar_settings.port}",
            "study_id": f"{project_id}",
            "traefik.docker.network": dynamic_sidecar_network_name,  # also used for monitoring
            "traefik.enable": "true",
            f"traefik.http.routers.{dynamic_sidecar_name}.entrypoints": "http",
            f"traefik.http.routers.{dynamic_sidecar_name}.priority": "10",
            f"traefik.http.routers.{dynamic_sidecar_name}.rule": "PathPrefix(`/`)",
            f"traefik.http.services.{dynamic_sidecar_name}.loadbalancer.server.port": f"{dynamic_sidecar_settings.port}",
            "type": ServiceType.MAIN.value,  # required to be listed as an interactive service and be properly cleaned up
            "user_id": f"{user_id}",
            # the following are used for monitoring
            "uuid": f"{node_uuid}",  # also needed for removal when project is closed
            "swarm_stack_name": dynamic_sidecar_settings.swarm_stack_name,
            "service_key": service_key,
            "service_tag": service_tag,
            "paths_mapping": paths_mapping.json(),
            "compose_spec": json.dumps(compose_spec),
            "target_container": target_container,
        },
        "name": dynamic_sidecar_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "SIMCORE_HOST_NAME": dynamic_sidecar_name,
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
                },
                "Hosts": [],
                "Image": dynamic_sidecar_settings.image,
                "Init": True,
                "Labels": {},
                "Mounts": mounts,
            },
            "Placement": {"Constraints": []},
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
            # this will get overwritten
            "Resources": {
                "Limits": {"NanoCPUs": 2 * pow(10, 9), "MemoryBytes": 1 * pow(1024, 3)},
                "Reservations": {
                    "NanoCPUs": 1 * pow(10, 8),
                    "MemoryBytes": 500 * pow(1024, 2),
                },
            },
        },
    }

    _inject_settings_to_create_service_params(
        labels_service_settings=settings,
        create_service_params=create_service_params,
    )

    return create_service_params
