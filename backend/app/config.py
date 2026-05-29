"""Centralised, environment-driven configuration.

All settings are overridable via environment variables prefixed with ``SIS_``
or via a local ``.env`` file (see ``.env.example``).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API server ---
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./store_intelligence.db"

    # --- Streaming ---
    stream_backend: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"
    stream_name: str = "sis.events"

    # --- Detection / tracking pipeline ---
    detector_backend: str = "auto"  # "auto" | "yolo" | "simulator"
    yolo_model: str = "yolov8n.pt"
    yolo_conf: float = 0.35
    video_source: str = ""
    camera_id: str = "cam-01"
    process_fps: float = 8.0
    sim_people: int = 18
    sim_speed: float = 1.0

    # --- Analytics / anomaly thresholds ---
    anomaly_zscore: float = 3.0
    queue_alert_len: int = 6
    dwell_alert_sec: float = 180.0
    occupancy_alert: int = 40

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
