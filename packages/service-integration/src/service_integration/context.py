"""
Application level settings which are pulled in and 
share with all subcommands.

These settings have a default value, can be passed
via environment variables and are overwritable via 
cli option.
"""

from pydantic import BaseSettings, Field, Extra, SecretStr


class IntegrationContext(BaseSettings):
    REGISTRY_NAME: str = Field(
        "", description="name of the registry to use for images, default is Docker Hub"
    )

    class Config:
        case_sensitive = False
        extra = Extra.forbid
        validate_all = True
        json_encoders = {SecretStr: lambda v: v.get_secret_value()}
