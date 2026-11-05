"""Runtime configuration, read from environment variables. Craftbox is isolated from Dreambox:
its own port, its own data directory (database, logs) and its own virtual environment."""
import os
from pathlib import Path

VERSION = "0.3.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8099
DREAMBOX_PORT = 8000  # reserved: Craftbox refuses to use it
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_BODY_BYTES = 1_000_000

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    pass


def data_dir() -> Path:
    return Path(os.environ.get("CRAFTBOX_DATA_DIR") or PROJECT_ROOT / "data").resolve()


def host() -> str:
    value = os.environ.get("CRAFTBOX_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    if value not in LOOPBACK_HOSTS and os.environ.get("CRAFTBOX_ALLOW_REMOTE") != "1":
        raise ConfigError(
            f"CRAFTBOX_HOST={value!r} would expose Craftbox to the network. Craftbox has no "
            "authentication; only loopback hosts are allowed (set CRAFTBOX_ALLOW_REMOTE=1 to override)."
        )
    return value


def port() -> int:
    raw = os.environ.get("CRAFTBOX_PORT", str(DEFAULT_PORT)).strip() or str(DEFAULT_PORT)
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"CRAFTBOX_PORT={raw!r} is not a number") from None
    if not 1024 <= value <= 65535:
        raise ConfigError(f"CRAFTBOX_PORT={value} must be between 1024 and 65535")
    if value == DREAMBOX_PORT:
        raise ConfigError(f"CRAFTBOX_PORT={value} is reserved for Dreambox; Craftbox will not use it")
    return value
