from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./nanosphere.db"
    JWT_SECRET: str = "change-me-to-a-long-random-string-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 10
    # Limited free-course offer: enrollments are free before this ISO timestamp,
    # paid (mock checkout) afterwards. Change to extend/end the offer.
    FREE_OFFER_ENDS_AT: str = "2026-10-31T00:00:00+00:00"
    # Admin: comma-separated emails that always get is_admin on signup/login.
    ADMIN_EMAILS: str = "admin@nanosphere.io"
    # Dev mailbox: when true, verification codes can be fetched via
    # GET /auth/dev-inbox (local demo delivery). Production uses SMTP.
    DEV_MAILBOX: bool = True
    # External research lookup (Semantic Scholar). Empty disables live lookup.
    RESEARCH_API_URL: str = "https://api.semanticscholar.org/graph/v1/paper/search"
    # Outbound email (verification + reset codes). Empty SMTP_HOST = demo
    # mode: codes surface in-app instead of by email. For Gmail, use an
    # App Password (Google Account > Security > 2-Step Verification).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "NanoSphere <noreply@nanosphere.io>"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def cors_origins() -> list[str]:
    return [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
