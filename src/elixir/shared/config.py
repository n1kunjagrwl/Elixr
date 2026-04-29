from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/elixir"

    # Security
    jwt_secret: str = "change-me-in-production-use-at-least-32-chars"
    encryption_key: str = "change-me-32-bytes-hex-encoded-00"  # 32-byte hex

    # Temporal
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "elixir-main"
    temporal_tls: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_service_sid: str = ""

    # External APIs
    eodhd_api_key: str = ""
    coingecko_api_key: str = ""
    twelve_data_api_key: str = ""
    metals_api_key: str = ""
    exchangerate_api_key: str = ""

    # DB pool settings
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800
    db_pool_timeout: int = 30
    db_statement_timeout_ms: int = 30000

    # OTP config
    otp_expiry_seconds: int = 60
    otp_max_attempts: int = 3
    otp_lockout_minutes: int = 5
    otp_rate_limit_count: int = 3
    otp_rate_limit_window_minutes: int = 15

    # Token expiry
    access_token_expiry_minutes: int = 15
    refresh_token_expiry_days: int = 7

    # Cookie security — set False when running over plain HTTP (local Docker, no TLS)
    cookie_secure: bool = True

    # Outbox
    outbox_poll_interval_seconds: int = 2
