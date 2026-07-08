from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sam_platform"

    # JWT
    secret_key: str = "change-me-to-a-random-secret-key-in-production"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Storage (PDFs)
    storage_backend: str = "local"
    pdf_storage_path: str = "/app/data/pdfs"
    max_upload_size_mb: int = 50
    max_files_per_upload: int = 15

    # Storage (Compendios / S3-compatible)
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "compendiums"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = True
    s3_public_url_prefix: str = ""  # opcional: CDN o URL pública fija

    # CORS
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Auth cookies (httpOnly)
    # En producción con subdominios (api.astreo.space, app.astreo.space, ...),
    # usar cookie_domain=".astreo.space" para compartir la cookie entre subdominios.
    # En desarrollo (localhost) dejar cookie_domain vacío (None) y secure=False.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # "lax" permite navegación cross-site controlada
    cookie_domain: str | None = None

    # App
    debug: bool = False


settings = Settings()
