from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Attendance API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://attendance:attendance@localhost:5432/attendance"

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 8

    admin_email: str = "admin@example.com"
    admin_password: str = ""
    admin_full_name: str = "Administrator"

    allow_self_registration: bool = False

    upload_dir: Path = Path("uploads")
    max_upload_mb: int = 5
    max_image_px: int = 1600

    default_check_in_lead_minutes: int = 15
    default_late_after_minutes: int = 10

    cors_origins: list[str] = ["http://localhost:5173"]

    # OCR import of paper attendance lists
    tesseract_cmd: str | None = None  # auto-detected when unset
    ocr_lang: str = "eng"
    ocr_match_threshold: float = 70  # >= : matched, pre-selected
    ocr_review_threshold: float = 55  # >= : suggested, pre-selected but flagged for review
    # Optional Azure OpenAI vision engine (deployment of a vision-capable chat model)
    azure_openai_endpoint: str | None = None  # https://<resource>.openai.azure.com
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"

    @model_validator(mode="after")
    def reject_production_defaults(self):
        if not self.jwt_secret or not self.admin_password:
            raise ValueError("JWT_SECRET and ADMIN_PASSWORD must be configured")
        if self.app_env == "production" and (
            self.jwt_secret in ("", "change-me-in-production", "replace-with-a-long-random-string")
            or len(self.jwt_secret) < 32
            or self.admin_password in ("", "admin12345")
            or "attendance:attendance@" in self.database_url
        ):
            raise ValueError("Production requires non-default JWT, admin and database credentials")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
