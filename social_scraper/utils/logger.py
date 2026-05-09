"""
logger.py — Structured logger with file + console output and per-agent log files.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_loggers: dict[str, logging.Logger] = {}


def _make_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(_make_formatter())
    logger.addHandler(ch)

    # File handler — one file per agent per day
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{name}_{date_str}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_make_formatter())
    logger.addHandler(fh)

    _loggers[name] = logger
    return logger


class ActivityLog:
    """Append-only activity log for agent operations (saved as JSONL)."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(agent_name)
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.activity_file = LOG_DIR / f"{agent_name}_activity_{date_str}.jsonl"

    def log(self, action: str, platform: str = "", status: str = "ok", details: dict | None = None):
        import json
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "agent": self.agent_name,
            "action": action,
            "platform": platform,
            "status": status,
            **(details or {}),
        }
        with open(self.activity_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        level = logging.ERROR if status == "error" else logging.INFO
        self.logger.log(level, f"[{platform}] {action} — {status}")
        return entry
