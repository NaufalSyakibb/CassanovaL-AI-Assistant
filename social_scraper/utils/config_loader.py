"""
config_loader.py — Load and validate config.json, expose typed accessors.
"""
import json
import os
from pathlib import Path
from typing import Any

_CONFIG: dict = {}
_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config(path: str | Path | None = None) -> dict:
    global _CONFIG
    cfg_path = Path(path) if path else _CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        _CONFIG = json.load(f)
    return _CONFIG


def get(key: str, default: Any = None) -> Any:
    if not _CONFIG:
        load_config()
    keys = key.split(".")
    val = _CONFIG
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, default)
        else:
            return default
    return val


def get_proxies() -> list[str]:
    proxies = get("proxies", [])
    # Filter out placeholder values
    return [p for p in proxies if "proxy1" not in p and "proxy2" not in p]


def get_user_agents() -> list[str]:
    return get("user_agents", [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ])


def get_api_key(service: str) -> str:
    key = get(f"api_keys.{service}", "")
    if key.startswith("YOUR_"):
        return ""
    return key


def get_scraping_config() -> dict:
    return get("scraping", {
        "delay_min": 2,
        "delay_max": 10,
        "max_retries": 3,
        "retry_delay": 5,
        "timeout": 30,
        "max_results_per_platform": 50,
    })


def get_platform_config(platform: str) -> dict:
    return get(f"platforms.{platform}", {"enabled": False, "priority": "low"})


def is_platform_enabled(platform: str) -> bool:
    return get_platform_config(platform).get("enabled", False)


# Auto-load on import
try:
    load_config()
except FileNotFoundError:
    pass
