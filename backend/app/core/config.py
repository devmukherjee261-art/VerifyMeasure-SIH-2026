import os
from pathlib import Path

# Base directory of the backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

_TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


# Runtime environment: "development" (default) or "production".
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# In production, secrets and connection strings must come from the real process
# environment (systemd unit, container env, PaaS dashboard). The local .env file
# is a development convenience and is deliberately ignored so that a stale
# developer file can never silently supply production credentials.
if not IS_PRODUCTION:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Do not overwrite if already set in environment
                    if key not in os.environ:
                        os.environ[key] = value


def _split_origins(raw: str) -> list[str]:
    """Parse a comma/whitespace separated origin list, dropping empties."""
    return [item.strip().rstrip("/") for item in raw.replace(",", " ").split() if item.strip()]


class Settings:
    PROJECT_NAME: str = "SIH26036 Legal Metrology Verification System"
    API_V1_STR: str = "/api/v1"

    ENVIRONMENT: str = ENVIRONMENT
    IS_PRODUCTION: bool = IS_PRODUCTION

    # Debug / reload switches. Both must be off in production; the production
    # startup command in DEPLOY.md also passes --no-reload so the flag here and
    # the uvicorn flag cannot disagree.
    DEBUG: bool = _env_flag("DEBUG", default=not IS_PRODUCTION)
    RELOAD: bool = _env_flag("RELOAD", default=not IS_PRODUCTION)

    # Database Configuration from environment
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "CHANGE_ME")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "sih_2026")

    # Prefer explicit DATABASE_URL if provided, otherwise assemble from parts.
    # In production DATABASE_URL is required: a missing value must fail fast
    # rather than fall back to a localhost development database.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        ""
        if IS_PRODUCTION
        else f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
    )

    # Public verification host URL for QR codes
    FRONTEND_URL: str = os.getenv(
        "FRONTEND_URL", "" if IS_PRODUCTION else "http://localhost:5500"
    ).rstrip("/")
    BACKEND_URL: str = os.getenv(
        "BACKEND_URL", "" if IS_PRODUCTION else "http://127.0.0.1:8000"
    ).rstrip("/")

    # Canonical public verification page used for QR codes printed on
    # certificates. Falls back to FRONTEND_URL so a single variable is enough
    # for most deployments.
    PUBLIC_VERIFICATION_URL: str = os.getenv("PUBLIC_VERIFICATION_URL", "").rstrip("/")

    # Explicit CORS allowlist. Never "*" in production: the API is credentialed
    # (Bearer tokens), so a wildcard origin would be both rejected by browsers
    # and unsafe.
    CORS_ALLOWED_ORIGINS: list[str] = _split_origins(os.getenv("CORS_ALLOWED_ORIGINS", ""))

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    ADMIN_BOOTSTRAP_TOKEN: str = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")

    def verification_base_url(self) -> str:
        """Base URL that printed QR codes must resolve against."""
        return self.PUBLIC_VERIFICATION_URL or self.FRONTEND_URL

    def validate(self) -> None:
        """Fail fast on a production misconfiguration."""
        if not IS_PRODUCTION:
            return

        problems = []
        if not self.DATABASE_URL:
            problems.append("DATABASE_URL is required in production")
        elif not self.DATABASE_URL.startswith(("postgresql://", "postgres://")):
            problems.append("DATABASE_URL must be a PostgreSQL connection string")
        elif "@localhost" in self.DATABASE_URL or "@127.0.0.1" in self.DATABASE_URL:
            problems.append("DATABASE_URL must not point at localhost in production")

        if len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY must be set and at least 32 characters")

        if not self.FRONTEND_URL:
            problems.append("FRONTEND_URL is required in production")
        elif not self.FRONTEND_URL.startswith("https://"):
            problems.append("FRONTEND_URL must be an https:// URL in production")

        if not self.CORS_ALLOWED_ORIGINS:
            problems.append("CORS_ALLOWED_ORIGINS is required in production")
        if "*" in self.CORS_ALLOWED_ORIGINS:
            problems.append('CORS_ALLOWED_ORIGINS must not contain "*" in production')

        if self.DEBUG:
            problems.append("DEBUG must be false in production")
        if self.RELOAD:
            problems.append("RELOAD must be false in production")

        if problems:
            raise RuntimeError(
                "Invalid production configuration:\n  - " + "\n  - ".join(problems)
            )


settings = Settings()
settings.validate()
