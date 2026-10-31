"""Environment-driven settings. Secrets only ever come from env vars (or an untracked .env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    gemini_api_key: str | None = None
    gemini_model_pro: str = "gemini-3.1-pro-preview"
    gemini_model_flash: str = "gemini-3.8-flash"
    gemini_model_tts: str = "gemini-3.8-flash-tts"
    gemini_model_embed: str = "gemini-embedding-2"
    gemini_timeout_s: float = 30.0

    database_url: str | None = None
    var_dir: Path = BACKEND_DIR / "var"
    policy_dir: Path = BACKEND_DIR / "data" / "policy"
    web_dist: Path = REPO_DIR / "web" / "dist"
    public_web_url: str = "http://localhost:8000"

    scheduler_token: str | None = None
    enable_scheduler: bool = True
    scheduler_interval_min: int = 15

    open_meteo_api_key: str | None = None
    open_meteo_historical_url: str = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    open_meteo_customer_url: str = (
        "https://customer-historical-forecast-api.open-meteo.com/v1/forecast"
    )
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_customer_forecast_url: str = "https://customer-api.open-meteo.com/v1/forecast"
    nasa_power_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    sachet_rss_url: str = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
    nominatim_url: str = "https://nominatim.openstreetmap.org/reverse"
    http_user_agent: str = "FasalSaakshi/0.1 (crop-loss evidence; hackathon prototype)"

    run_budget_tool_calls: int = Field(default=12, ge=4)
    run_budget_seconds: float = Field(default=150.0, ge=10)
    run_workers: int = 4
    sse_poll_s: float = 0.4

    @property
    def artifacts_dir(self) -> Path:
        return self.var_dir / "artifacts"

    @property
    def db_url(self) -> str:
        if self.database_url:
            for prefix in ("postgresql://", "postgres://"):
                if self.database_url.startswith(prefix):  # psycopg 3 is the installed driver
                    return "postgresql+psycopg://" + self.database_url[len(prefix):]
            return self.database_url
        return f"sqlite:///{self.var_dir / 'fasalsaakshi.db'}"

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return settings
