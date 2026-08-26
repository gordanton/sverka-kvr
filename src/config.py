"""Загрузка настроек Proxy API из .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def get_proxy_config() -> dict[str, str]:
    return {
        "api_key": os.getenv("PROXY_API_KEY", "").strip(),
        "base_url": os.getenv("PROXY_BASE_URL", "").strip().rstrip("/"),
        "model": os.getenv("PROXY_MODEL", "").strip() or "gpt-4o-mini",
    }


def proxy_ready() -> bool:
    cfg = get_proxy_config()
    return bool(cfg["api_key"] and cfg["base_url"])