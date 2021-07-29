from functools import cached_property
from typing import Dict, Optional

from pydantic import Field, SecretStr, validator

from .base import BaseCustomSettings


class RegistrySettings(BaseCustomSettings):

    REGISTRY_AUTH: bool = Field(..., description="do registry authentication")
    REGISTRY_PATH: Optional[str] = Field(
        None, description="development mode only, in case a local registry is used"
    )
    # NOTE: name is missleading, http or https protocol are not included
    REGISTRY_URL: str = Field("", description="address to the docker registry")

    REGISTRY_USER: str = Field(
        ..., description="username to access the docker registry"
    )
    REGISTRY_PW: SecretStr = Field(
        ..., description="password to access the docker registry"
    )
    REGISTRY_SSL: bool = Field(..., description="access to registry through ssl")

    @validator("REGISTRY_PATH", pre=True)
    @classmethod
    def escape_none_string(cls, v) -> Optional[str]:
        return None if v == "None" else v

    @cached_property
    def resolved_registry_url(self) -> str:
        return self.REGISTRY_PATH or self.REGISTRY_URL

    @cached_property
    def api_url(self) -> str:
        return f"{self.REGISTRY_URL}/v2"

    @cached_property
    def dynamic_sidecar_env_vars(self) -> Dict[str, str]:
        return {
            "REGISTRY_AUTH": str(self.REGISTRY_AUTH),
            "REGISTRY_PATH": str(self.REGISTRY_PATH),
            "REGISTRY_URL": str(self.REGISTRY_URL),
            "REGISTRY_USER": str(self.REGISTRY_USER),
            "REGISTRY_PW": str(self.REGISTRY_PW.get_secret_value()),
            "REGISTRY_SSL": str(self.REGISTRY_SSL),
        }
