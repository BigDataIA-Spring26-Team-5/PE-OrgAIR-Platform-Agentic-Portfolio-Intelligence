from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None


@lru_cache(maxsize=1)
def api_base_url() -> str:
    """Return the FastAPI base URL, preferring values from `pe-org-air-platform/.env`.

    Supported env vars:
      - API_BASE_URL
      - FASTAPI_URL (legacy)
    """
    project_root = Path(__file__).resolve().parents[2]  # .../pe-org-air-platform
    if load_dotenv is not None:
        try:
            load_dotenv(project_root / ".env")
        except Exception:
            pass

    url = (
        os.getenv("API_BASE_URL")
        or os.getenv("FASTAPI_URL")
        or "http://localhost:8000"
    )
    return str(url).rstrip("/")

