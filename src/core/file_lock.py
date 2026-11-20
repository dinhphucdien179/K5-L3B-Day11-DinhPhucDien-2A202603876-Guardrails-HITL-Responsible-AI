"""Khóa file độc quyền chạy được trên cả Linux/macOS (fcntl) và Windows (msvcrt).

Dùng cho các file JSON ghi chung giữa nhiều tiến trình: bộ đếm ``api_usage.json``
và kho duyệt HITL ``hitl_approvals.json``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_lock(lock_path: str | Path):
    """Giữ khóa độc quyền trên ``lock_path`` cho tới khi thoát khối ``with``."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            # LK_LOCK tự thử lại trong khoảng 10 giây trước khi báo lỗi.
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
