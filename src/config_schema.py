from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, FilePath, SecretStr


class SettingBaseModel(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")


class Accounts(SettingBaseModel):
    """InNoHassle Accounts integration settings"""

    api_url: str = "https://api.innohassle.ru/accounts/v0/"
    "URL of the Accounts API"
    api_jwt_token: SecretStr
    "JWT token for accessing the Accounts API as a service"


class Mongo(SettingBaseModel):
    """MongoDB settings"""

    uri: SecretStr
    "MongoDB database connection URI"


class Google(SettingBaseModel):
    """Google API settings (OAuth + optional Drive folder)"""

    oauth_client_secret_file: FilePath | None = None
    "Path to Google OAuth client_secret.json (Desktop app) for user OAuth"
    oauth_token_file: Path | None = None
    "Path to Google OAuth token.json (stores refresh token)"
    drive_folder_id: str | None = None
    "Google Drive folder ID where new files will be created (optional)"


class Settings(SettingBaseModel):
    """Settings for the application."""

    model_config = ConfigDict(validate_default=True)

    schema_: str = Field(None, alias="$schema")  # type: ignore
    app_root_path: str = ""
    'Prefix for the API path (e.g. "/api/v0")'
    cors_allow_origin_regex: str = ".*"
    "Allowed origins for CORS: from which domains requests to the API are allowed. Specify as a regex: `https://.*.innohassle.ru`"
    accounts: Accounts
    "InNoHassle Accounts integration settings"
    mongo: Mongo
    "MongoDB settings"
    innohassle_url: str = "https://innohassle.ru"
    "URL of the InNoHassle to use for links"
    base_url: str = "https://innohassle.ru"
    "Base URL for generating join links"
    google_service_account_file: FilePath = Path("inh-plugin.json")
    "Path to the Google service account file with credentials"
    google: Google = Google()
    "Google API settings (OAuth + Drive)"

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        with open(path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        return cls.model_validate(yaml_config)

    @classmethod
    def save_schema(cls, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            schema = {
                "$schema": "https://json-schema.org/draft-07/schema",
                **cls.model_json_schema(),
            }
            yaml.dump(schema, f, sort_keys=False)
