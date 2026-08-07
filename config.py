from decouple import Config, RepositoryEnv

config = Config(RepositoryEnv(".env"))

# --- Logging (app.logger.setup.init_logging / get_logger) ---
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOG_DIR = config("LOG_DIR", default="./logs")
LOG_TO_FILE = config("LOG_TO_FILE", cast=bool, default=True)
LOG_USE_RICH = config("LOG_USE_RICH", cast=bool, default=False)
LOG_FORMAT = config(
    "LOG_FORMAT",
    default="%(asctime)s | %(levelname)-8s | %(message)s",
)
LOG_MIDDLEWARE_DEBUG = config("LOG_MIDDLEWARE_DEBUG", cast=bool, default=False)
LOG_HANDLER_EVENTS = config("LOG_HANDLER_EVENTS", cast=bool, default=False)
LOG_APP_MAX_BYTES = config("LOG_APP_MAX_BYTES", cast=int, default=5 * 1024 * 1024)
LOG_APP_BACKUP_COUNT = config("LOG_APP_BACKUP_COUNT", cast=int, default=5)
LOG_ERROR_MAX_BYTES = config("LOG_ERROR_MAX_BYTES", cast=int, default=2 * 1024 * 1024)
LOG_ERROR_BACKUP_COUNT = config("LOG_ERROR_BACKUP_COUNT", cast=int, default=3)


def optional_int(value: str) -> int | None:
    """Cast to int or return None if empty/whitespace"""
    if not value or not value.strip():
        return None
    return int(value)


API_ID = config("API_ID")
API_HASH = config("API_HASH")
BOT_TOKEN = config("BOT_TOKEN")
TELETHON_SESSION_PATH = config("TELETHON_SESSION_PATH", default="KenzoSession")
ADMIN_ID: list = config("ADMIN_ID", cast=lambda v: [int(i) for i in v.split(",")])
LOG_CHANNEL = config("LOG_CHANNEL", cast=optional_int, default=None)
SQLALCHEMY_DATABASE_URL = config("SQLALCHEMY_DATABASE_URL")
FAST_API_PORT = config("FASTAPI_PORT", cast=optional_int, default=None)
BOT_TAG = config("BOT_TAG", default="")
ADMIN_ID_TAG = config("ADMIN_ID_TAG", default="")
CHANNEL_ID_TAG = config("CHANNEL_ID_TAG", default="")
TUTORIAL_HELP_LINKS = config("TUTORIAL_HELP_LINKS", default="https://t.me/")
DISABLE_UPTIME_BUTTONS = config("DISABLE_UPTIME_BUTTONS", cast=bool, default=True)
LINK_UPTIME_BUTTONS = config("LINK_UPTIME_BUTTONS", default="https://t.me/")
# TRON network: empty = mainnet; "nile" or "shasta" for testnets
TRX_TESTNET_MODE = config("TRX_TESTNET_MODE", default=None)
# TON network: empty = mainnet; "testnet" for TON Testnet
TON_TESTNET_MODE = config("TON_TESTNET_MODE", default=None)

GITHUB_TOKEN = config("GITHUB_TOKEN", default="")

# Enable or disable FastAPI based on port configuration
ENABLE_FASTAPI = FAST_API_PORT is not None

# --- Redis (conversation state, locks, callback payloads, optional cache) ---
REDIS_URL = config("REDIS_URL", default="redis://localhost:6161")
# Shared Redis across bots: set e.g. pasarguard:mainbot; empty = sha256(BOT_TOKEN) fallback
REDIS_NAMESPACE_PREFIX = config("REDIS_NAMESPACE_PREFIX", default="pasarguardbot:mainbot").strip()
REDIS_RETRY_INTERVAL_SECONDS = config("REDIS_RETRY_INTERVAL_SECONDS", cast=float, default=10.0)
REDIS_SOCKET_CONNECT_TIMEOUT = config("REDIS_SOCKET_CONNECT_TIMEOUT", cast=float, default=2.0)
# 0 disables read timeout (required for shared client + BRPOP). Connect timeout still applies.
REDIS_SOCKET_TIMEOUT = config("REDIS_SOCKET_TIMEOUT", cast=float, default=0.0)
REDIS_HEALTH_CHECK_INTERVAL = config("REDIS_HEALTH_CHECK_INTERVAL", cast=int, default=30)
STATE_TTL_SECONDS = config("STATE_TTL_SECONDS", cast=int, default=86400)
LOCK_TTL_SECONDS = config("LOCK_TTL_SECONDS", cast=int, default=300)
CALLBACK_TTL_SECONDS = config("CALLBACK_TTL_SECONDS", cast=int, default=3600)

# --- SQLAlchemy pool (non-SQLite) ---
SQLALCHEMY_POOL_SIZE = config("SQLALCHEMY_POOL_SIZE", cast=int, default=20)
SQLALCHEMY_MAX_OVERFLOW = config("SQLALCHEMY_MAX_OVERFLOW", cast=int, default=30)
SQLALCHEMY_POOL_TIMEOUT = config("SQLALCHEMY_POOL_TIMEOUT", cast=int, default=30)
