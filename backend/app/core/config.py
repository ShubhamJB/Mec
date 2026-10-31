from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    # Fernet key used only for roadside request contact/location snapshots.
    # Generate with Fernet.generate_key() and keep the key stable/backed up.
    ROADSIDE_DATA_KEY: str = ""
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/find_your_mechanic"
    SYNC_DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:password@localhost:5432/find_your_mechanic"
    )

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Email ─────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "no-reply@findyourmechanic.com"
    EMAIL_FROM_NAME: str = "Find Your Mechanic"

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_PROVIDER: Literal["stub", "local", "s3", "gcs", "cloudinary"] = "stub"
    UPLOAD_DIR: str = "uploads"
    MEDIA_URL_PREFIX: str = "/api/v1/media"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-southeast-1"
    S3_BUCKET: str = "find-your-mechanic-photos"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_ANALYTICS: str = "30/minute"
    RATE_LIMIT_ROADSIDE: str = "5/hour"

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Photos ────────────────────────────────────────────────────────────────
    MAX_PHOTOS_PER_GARAGE: int = 10
    MAX_PHOTO_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    ALLOWED_PHOTO_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]


settings = Settings()
