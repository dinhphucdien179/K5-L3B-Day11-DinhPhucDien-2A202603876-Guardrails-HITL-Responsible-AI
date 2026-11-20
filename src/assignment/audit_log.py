"""
Assignment 11 — Audit Log.

Ghi lại mọi lượt hỏi/đáp để điều tra sau này. Lớp này không bao giờ tự chặn request
và cũng không được làm hỏng pipeline: dữ liệu thiếu cặp vẫn được ghi kèm ghi chú
thay vì ném exception. Nội dung được che PII/secret trước khi lưu.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path


def default_audit_log_path() -> str:
    """Always resolve to <repo>/outputs/… (safe when cwd is src/)."""
    repo_root = Path(__file__).resolve().parents[2]
    return str(repo_root / "outputs" / "audit_log.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(text) -> str | None:
    """Che PII/secret bằng chính bộ lọc output của Blue trước khi ghi xuống đĩa."""
    if text is None:
        return None
    from guardrails.output_guardrails import content_filter

    return content_filter(str(text))["redacted"]


class AuditLogPlugin:
    """Audit log độc lập framework; input và output được ghép theo ``request_id``."""

    def __init__(self):
        self.name = "audit_log"
        self.logs: list[dict] = []
        self._open: dict[str, tuple[float, dict]] = {}

    def record_input(self, *, user_id: str, text: str, request_id: str | None = None):
        """Lưu input + thời điểm bắt đầu, khóa theo request_id (hoặc user_id nếu không có)."""
        key = request_id or user_id
        if key in self._open:
            # Request cũ chưa có output: ghi lại là chưa hoàn tất rồi mở request mới.
            _, stale = self._open.pop(key)
            stale.update(output=None, blocked=None, layer=None, completed_at=None,
                         latency_ms=None, note="no output recorded")
            self.logs.append(stale)
        self._open[key] = (time.monotonic(), {
            "request_id": key,
            "user_id": sanitize(user_id),
            "input": sanitize(text),
            "started_at": utc_now_iso(),
        })

    def record_output(
        self,
        *,
        user_id: str,
        text: str,
        blocked: bool = False,
        layer: str | None = None,
        request_id: str | None = None,
    ):
        """Ghép output với input tương ứng, tính latency rồi thêm vào ``self.logs``."""
        key = request_id or user_id
        opened = self._open.pop(key, None)
        if opened is None:
            started, row = None, {
                "request_id": key,
                "user_id": sanitize(user_id),
                "input": None,
                "started_at": None,
                "note": "output without matching input",
            }
        else:
            started, row = opened
        row.update(
            output=sanitize(text),
            blocked=bool(blocked),
            layer=layer,
            completed_at=utc_now_iso(),
            latency_ms=None if started is None else max(0.0, (time.monotonic() - started) * 1000),
        )
        self.logs.append(row)

    def export_json(self, filepath: str | None = None) -> Path:
        """Ghi toàn bộ log (JSON array) vào ``<repo>/outputs/audit_log.json`` mặc định."""
        path = Path(filepath or default_audit_log_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.logs, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
