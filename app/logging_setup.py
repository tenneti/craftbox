"""Structured (JSON-lines) logging to stderr and a rotating file inside the Craftbox data directory."""
import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone

LOGGER_NAME = "craftbox"


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure(log_dir=None):
    """Idempotent. Pass log_dir=None to log to stderr only (used by tests)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(os.environ.get("CRAFTBOX_LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = JsonFormatter()
    handlers = [logging.StreamHandler()]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(
            log_dir / "craftbox.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def log(event, level="info", **fields):
    getattr(logging.getLogger(LOGGER_NAME), level)(event, extra={"fields": fields})
