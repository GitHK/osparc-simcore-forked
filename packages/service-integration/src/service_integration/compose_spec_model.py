# generated by datamodel-codegen:
#   filename:  compose-spec.json
#   timestamp: 2021-11-12T17:03:07+00:00

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Extra, Field, conint, constr

# port number range
# "format": "ports"
PortInt = conint(gt=0, lt=65535)
# TODO: format "duration" https://schema.org/Duration
# TODO: format "expose"


class Config1(BaseModel):
    class Config:
        extra = Extra.forbid

    source: Optional[str] = None
    target: Optional[str] = None
    uid: Optional[str] = None
    gid: Optional[str] = None
    mode: Optional[float] = None


class CredentialSpec(BaseModel):
    class Config:
        extra = Extra.forbid

    config: Optional[str] = None
    file: Optional[str] = None
    registry: Optional[str] = None


class Condition(Enum):
    service_started = "service_started"
    service_healthy = "service_healthy"
    service_completed_successfully = "service_completed_successfully"


class DependsOn(BaseModel):
    class Config:
        extra = Extra.forbid

    condition: Condition


class Extend(BaseModel):
    class Config:
        extra = Extra.forbid

    service: str
    file: Optional[str] = None


class Logging(BaseModel):
    class Config:
        extra = Extra.forbid

    driver: Optional[str] = None
    options: Optional[Dict[constr(regex=r"^.+$"), Optional[Union[str, float]]]] = None


class Port(BaseModel):
    class Config:
        extra = Extra.forbid

    mode: Optional[str] = None
    host_ip: Optional[str] = None
    target: Optional[int] = None
    published: Optional[int] = None
    protocol: Optional[str] = None


class PullPolicy(Enum):
    always = "always"
    never = "never"
    if_not_present = "if_not_present"
    build = "build"
    missing = "missing"


class Secret1(BaseModel):
    class Config:
        extra = Extra.forbid

    source: Optional[str] = None
    target: Optional[str] = None
    uid: Optional[str] = None
    gid: Optional[str] = None
    mode: Optional[float] = None


class Ulimit(BaseModel):
    class Config:
        extra = Extra.forbid

    hard: int
    soft: int


class Bind(BaseModel):
    class Config:
        extra = Extra.forbid

    propagation: Optional[str] = None
    create_host_path: Optional[bool] = None


class Volume2(BaseModel):
    class Config:
        extra = Extra.forbid

    nocopy: Optional[bool] = None


class Tmpfs(BaseModel):
    class Config:
        extra = Extra.forbid

    size: Optional[Union[conint(ge=0), str]] = None


class Volume1(BaseModel):
    class Config:
        extra = Extra.forbid

    type: str
    source: Optional[str] = None
    target: Optional[str] = None
    read_only: Optional[bool] = None
    consistency: Optional[str] = None
    bind: Optional[Bind] = None
    volume: Optional[Volume2] = None
    tmpfs: Optional[Tmpfs] = None


class Healthcheck(BaseModel):
    class Config:
        extra = Extra.forbid

    disable: Optional[bool] = None
    interval: Optional[str] = None
    retries: Optional[float] = None
    test: Optional[Union[str, List[str]]] = None
    timeout: Optional[str] = None
    start_period: Optional[str] = None


class Order(Enum):
    start_first = "start-first"
    stop_first = "stop-first"


class RollbackConfig(BaseModel):
    class Config:
        extra = Extra.forbid

    parallelism: Optional[int] = None
    delay: Optional[str] = None
    failure_action: Optional[str] = None
    monitor: Optional[str] = None
    max_failure_ratio: Optional[float] = None
    order: Optional[Order] = None


class Order1(Enum):
    start_first = "start-first"
    stop_first = "stop-first"


class UpdateConfig(BaseModel):
    class Config:
        extra = Extra.forbid

    parallelism: Optional[int] = None
    delay: Optional[str] = None
    failure_action: Optional[str] = None
    monitor: Optional[str] = None
    max_failure_ratio: Optional[float] = None
    order: Optional[Order1] = None


class Limits(BaseModel):
    class Config:
        extra = Extra.forbid

    cpus: Optional[Union[float, str]] = None
    memory: Optional[str] = None


class RestartPolicy(BaseModel):
    class Config:
        extra = Extra.forbid

    condition: Optional[str] = None
    delay: Optional[str] = None
    max_attempts: Optional[int] = None
    window: Optional[str] = None


class Preference(BaseModel):
    class Config:
        extra = Extra.forbid

    spread: Optional[str] = None


class Placement(BaseModel):
    class Config:
        extra = Extra.forbid

    constraints: Optional[List[str]] = None
    preferences: Optional[List[Preference]] = None
    max_replicas_per_node: Optional[int] = None


class DiscreteResourceSpec(BaseModel):
    class Config:
        extra = Extra.forbid

    kind: Optional[str] = None
    value: Optional[float] = None


class GenericResource(BaseModel):
    class Config:
        extra = Extra.forbid

    discrete_resource_spec: Optional[DiscreteResourceSpec] = None


class GenericResources(BaseModel):
    __root__: List[GenericResource]


class ConfigItem(BaseModel):
    class Config:
        extra = Extra.forbid

    subnet: Optional[str] = None
    ip_range: Optional[str] = None
    gateway: Optional[str] = None
    aux_addresses: Optional[Dict[constr(regex=r"^.+$"), str]] = None


class Ipam(BaseModel):
    class Config:
        extra = Extra.forbid

    driver: Optional[str] = None
    config: Optional[List[ConfigItem]] = None
    options: Optional[Dict[constr(regex=r"^.+$"), str]] = None


class External(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = None


class External1(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = None


class External2(BaseModel):
    name: Optional[str] = None


class External3(BaseModel):
    name: Optional[str] = None


class ListOfStrings(BaseModel):
    __root__: List[str]


class ListOrDict(BaseModel):
    __root__: Union[
        Dict[constr(regex=r".+"), Optional[Union[str, float, bool]]], List[str]
    ]


class BlkioLimit(BaseModel):
    class Config:
        extra = Extra.forbid

    path: Optional[str] = None
    rate: Optional[Union[int, str]] = None


class BlkioWeight(BaseModel):
    class Config:
        extra = Extra.forbid

    path: Optional[str] = None
    weight: Optional[int] = None


class Constraints(BaseModel):
    __root__: Any


class BuildItem(BaseModel):
    class Config:
        extra = Extra.forbid

    context: Optional[str] = None
    dockerfile: Optional[str] = None
    args: Optional[ListOrDict] = None
    labels: Optional[ListOrDict] = None
    cache_from: Optional[List[str]] = None
    network: Optional[str] = None
    target: Optional[str] = None
    shm_size: Optional[Union[int, str]] = None
    extra_hosts: Optional[ListOrDict] = None
    isolation: Optional[str] = None


class BlkioConfig(BaseModel):
    class Config:
        extra = Extra.forbid

    device_read_bps: Optional[List[BlkioLimit]] = None
    device_read_iops: Optional[List[BlkioLimit]] = None
    device_write_bps: Optional[List[BlkioLimit]] = None
    device_write_iops: Optional[List[BlkioLimit]] = None
    weight: Optional[int] = None
    weight_device: Optional[List[BlkioWeight]] = None


class Network1(BaseModel):
    class Config:
        extra = Extra.forbid

    aliases: Optional[ListOfStrings] = None
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    link_local_ips: Optional[ListOfStrings] = None
    priority: Optional[float] = None


class Device(BaseModel):
    class Config:
        extra = Extra.forbid

    capabilities: Optional[ListOfStrings] = None
    count: Optional[Union[str, int]] = None
    device_ids: Optional[ListOfStrings] = None
    driver: Optional[str] = None
    options: Optional[ListOrDict] = None


class Devices(BaseModel):
    __root__: List[Device]


class Network(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = None
    driver: Optional[str] = None
    driver_opts: Optional[Dict[constr(regex=r"^.+$"), Union[str, float]]] = None
    ipam: Optional[Ipam] = None
    external: Optional[External] = None
    internal: Optional[bool] = None
    enable_ipv6: Optional[bool] = None
    attachable: Optional[bool] = None
    labels: Optional[ListOrDict] = None


class Volume(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = None
    driver: Optional[str] = None
    driver_opts: Optional[Dict[constr(regex=r"^.+$"), Union[str, float]]] = None
    external: Optional[External1] = None
    labels: Optional[ListOrDict] = None


class Secret(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = None
    file: Optional[str] = None
    external: Optional[External2] = None
    labels: Optional[ListOrDict] = None
    driver: Optional[str] = None
    driver_opts: Optional[Dict[constr(regex=r"^.+$"), Union[str, float]]] = None
    template_driver: Optional[str] = None


class Config(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = None
    file: Optional[str] = None
    external: Optional[External3] = None
    labels: Optional[ListOrDict] = None
    template_driver: Optional[str] = None


class StringOrList(BaseModel):
    __root__: Union[str, ListOfStrings]


class Reservations(BaseModel):
    class Config:
        extra = Extra.forbid

    cpus: Optional[Union[float, str]] = None
    memory: Optional[str] = None
    generic_resources: Optional[GenericResources] = None
    devices: Optional[Devices] = None


class Resources(BaseModel):
    class Config:
        extra = Extra.forbid

    limits: Optional[Limits] = None
    reservations: Optional[Reservations] = None


class Deployment(BaseModel):
    class Config:
        extra = Extra.forbid

    mode: Optional[str] = None
    endpoint_mode: Optional[str] = None
    replicas: Optional[int] = None
    labels: Optional[ListOrDict] = None
    rollback_config: Optional[RollbackConfig] = None
    update_config: Optional[UpdateConfig] = None
    resources: Optional[Resources] = None
    restart_policy: Optional[RestartPolicy] = None
    placement: Optional[Placement] = None


class Service(BaseModel):
    class Config:
        extra = Extra.forbid

    deploy: Optional[Deployment] = None
    build: Optional[Union[str, BuildItem]] = None
    blkio_config: Optional[BlkioConfig] = None
    cap_add: Optional[List[str]] = None
    cap_drop: Optional[List[str]] = None
    cgroup_parent: Optional[str] = None
    command: Optional[Union[str, List[str]]] = None
    configs: Optional[List[Union[str, Config1]]] = None
    container_name: Optional[str] = None
    cpu_count: Optional[conint(ge=0)] = None
    cpu_percent: Optional[conint(ge=0, le=100)] = None
    cpu_shares: Optional[Union[float, str]] = None
    cpu_quota: Optional[Union[float, str]] = None
    cpu_period: Optional[Union[float, str]] = None
    cpu_rt_period: Optional[Union[float, str]] = None
    cpu_rt_runtime: Optional[Union[float, str]] = None
    cpus: Optional[Union[float, str]] = None
    cpuset: Optional[str] = None
    credential_spec: Optional[CredentialSpec] = None
    depends_on: Optional[
        Union[ListOfStrings, Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), DependsOn]]
    ] = None
    device_cgroup_rules: Optional[ListOfStrings] = None
    devices: Optional[List[str]] = None
    dns: Optional[StringOrList] = None
    dns_opt: Optional[List[str]] = None
    dns_search: Optional[StringOrList] = None
    domainname: Optional[str] = None
    entrypoint: Optional[Union[str, List[str]]] = None
    env_file: Optional[StringOrList] = None
    environment: Optional[ListOrDict] = None
    expose: Optional[List[Union[str, float]]] = None
    extends: Optional[Union[str, Extend]] = None
    external_links: Optional[List[str]] = None
    extra_hosts: Optional[ListOrDict] = None
    group_add: Optional[List[Union[str, float]]] = None
    healthcheck: Optional[Healthcheck] = None
    hostname: Optional[str] = None
    image: Optional[str] = None
    init: Optional[bool] = None
    ipc: Optional[str] = None
    isolation: Optional[str] = None
    labels: Optional[ListOrDict] = None
    links: Optional[List[str]] = None
    logging: Optional[Logging] = None
    mac_address: Optional[str] = None
    mem_limit: Optional[Union[float, str]] = None
    mem_reservation: Optional[Union[str, int]] = None
    mem_swappiness: Optional[int] = None
    memswap_limit: Optional[Union[float, str]] = None
    network_mode: Optional[str] = None
    networks: Optional[
        Union[
            ListOfStrings, Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), Optional[Network1]]
        ]
    ] = None
    oom_kill_disable: Optional[bool] = None
    oom_score_adj: Optional[conint(ge=-1000, le=1000)] = None
    pid: Optional[Optional[str]] = None
    pids_limit: Optional[Union[float, str]] = None
    platform: Optional[str] = None
    ports: Optional[List[Union[PortInt, str, Port]]] = None
    privileged: Optional[bool] = None
    profiles: Optional[ListOfStrings] = None
    pull_policy: Optional[PullPolicy] = None
    read_only: Optional[bool] = None
    restart: Optional[str] = None
    runtime: Optional[str] = None
    scale: Optional[int] = None
    security_opt: Optional[List[str]] = None
    shm_size: Optional[Union[float, str]] = None
    secrets: Optional[List[Union[str, Secret1]]] = None
    sysctls: Optional[ListOrDict] = None
    stdin_open: Optional[bool] = None
    stop_grace_period: Optional[str] = None
    stop_signal: Optional[str] = None
    storage_opt: Optional[Dict[str, Any]] = None
    tmpfs: Optional[StringOrList] = None
    tty: Optional[bool] = None
    ulimits: Optional[Dict[constr(regex=r"^[a-z]+$"), Union[int, Ulimit]]] = None
    user: Optional[str] = None
    userns_mode: Optional[str] = None
    volumes: Optional[List[Union[str, Volume1]]] = None
    volumes_from: Optional[List[str]] = None
    working_dir: Optional[str] = None


class ComposeSpecification(BaseModel):
    class Config:
        extra = Extra.forbid

    version: Optional[str] = Field(
        None,
        description="Version of the Compose specification used. Tools not implementing required version MUST reject the configuration file.",
    )
    services: Optional[Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), Service]] = None
    networks: Optional[Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), Network]] = None
    volumes: Optional[Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), Volume]] = None
    secrets: Optional[Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), Secret]] = None
    configs: Optional[Dict[constr(regex=r"^[a-zA-Z0-9._-]+$"), Config]] = None


# TODO: dump this spec version
