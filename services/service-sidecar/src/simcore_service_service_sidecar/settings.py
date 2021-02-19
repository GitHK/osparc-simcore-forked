import logging
from typing import Optional

from pydantic import BaseSettings, Field, PositiveInt, validator

from models_library.basic_types import BootModeEnum, PortInt


class ServiceSidecarSettings(BaseSettings):
    @classmethod
    def create(cls, **settings_kwargs) -> "ServiceSidecarSettings":
        return cls(
            **settings_kwargs,
        )

    boot_mode: Optional[BootModeEnum] = Field(
        ...,
        description="boot mode helps determine if in development mode or normal operation",
        env="SC_BOOT_MODE",
    )

    # LOGGING
    log_level_name: str = Field("DEBUG", env="LOG_LEVEL")

    @validator("log_level_name")
    @classmethod
    def match_logging_level(cls, v) -> str:
        try:
            getattr(logging, v.upper())
        except AttributeError as err:
            raise ValueError(f"{v.upper()} is not a valid level") from err
        return v.upper()

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = Field(
        "0.0.0.0", description="host where to bind the application on which to serve"
    )
    port: PortInt = Field(
        8000, description="port where the server will be currently serving"
    )

    compose_namespace: str = Field(
        ...,
        description=(
            "To avoid collisions when scheduling on the same node, this "
            "will be compsoed by the project_uuid and node_uuid."
        ),
    )

    max_combined_container_name_length: PositiveInt = Field(
        255, description="the container name will be limited to 255 chars"
    )

    stop_and_remove_timeout: PositiveInt = Field(
        5,
        description=(
            "When receiving SIGTERM the process has 10 seconds to cleanup its children "
            "forcing our children to stop in 5 seconds in all cases"
        ),
    )

    debug: bool = Field(
        False,
        description="If set to True the application will boot into debug mode",
        env="DEBUG",
    )

    remote_debug_port: PortInt = Field(
        3000, description="ptsvd remote debugger starting port"
    )

    docker_compose_down_timeout: PositiveInt = Field(
        ..., description="used during shutdown when containers swapend will be removed"
    )

    @property
    def is_development_mode(self):
        """If in development mode this will be True"""
        return self.boot_mode == BootModeEnum.DEVELOPMENT

    @property
    def loglevel(self) -> int:
        return getattr(logging, self.log_level_name)

    class Config:
        case_sensitive = False
        env_prefix = "SERVICE_SIDECAR_"