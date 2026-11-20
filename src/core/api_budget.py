"""Persistent, process-safe budget. No prompts, responses or credentials stored.

Chỉ bật khi ``LAB_LIVE_API=1``. ``src/main.py`` đặt giá trị này mặc định cho các
lần chạy thật; người chấm muốn replay mà không bị giới hạn thì đặt ``LAB_LIVE_API=0``.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from core.file_lock import exclusive_lock


class BudgetExceeded(RuntimeError):
    pass


def safe_error(exc: Exception) -> str:
    # Provider exception strings can contain keys, headers or request bodies.
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    status = str(status) if status is not None else ""
    return type(exc).__name__ + (f" (status={status})" if re.fullmatch(r"\d{3}", status) else "")


class ApiBudget:
    def __init__(self, path: str | Path | None = None, limit: int = 100):
        self.path = Path(path) if path else Path(__file__).resolve().parents[2] / "outputs/api_usage.json"
        self.limit = min(int(limit), 100)
        if self.limit < 1:
            raise ValueError("budget must be between 1 and 100")

    def consume(self, *, provider: str, model: str, purpose: str) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_lock(self.path.with_suffix(".lock")):
            data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"limit": self.limit, "used": 0, "calls": []}
            limit = min(self.limit, int(data["limit"]))
            if data["used"] >= limit:
                raise BudgetExceeded(f"Model API budget exhausted ({limit} requests)")
            data["used"] += 1
            data["limit"] = limit
            data["calls"].append({"number": data["used"], "provider": provider, "model": model, "purpose": purpose,
                                  "timestamp": datetime.now(timezone.utc).isoformat()})
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(temp, self.path)
            return data["used"]


def model_budget() -> ApiBudget | None:
    # Test runners with fake clients never activate metering or create artifacts.
    return ApiBudget() if os.environ.get("LAB_LIVE_API") == "1" else None
