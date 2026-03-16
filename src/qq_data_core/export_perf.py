from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from .models import EXPORT_TIMEZONE

MATERIALIZE_STEP_TRACE_SAMPLE_INTERVAL = 100
MATERIALIZE_SLOW_STEP_WARN_S = 5.0


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(EXPORT_TIMEZONE).isoformat()
    return str(value)


class ExportPerfTraceWriter:
    def __init__(
        self,
        state_dir: Path,
        *,
        chat_type: str,
        chat_id: str,
        mode: str,
    ) -> None:
        self._lock = Lock()
        export_perf_dir = state_dir / "export_perf"
        export_perf_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(EXPORT_TIMEZONE).strftime("%Y%m%d_%H%M%S")
        self.path = export_perf_dir / f"{mode}_{chat_type}_{chat_id}_{stamp}.jsonl"
        self._handle = self.path.open("a", encoding="utf-8", newline="\n")
        self._started_at = datetime.now(EXPORT_TIMEZONE)
        self._pages_scanned = 0
        self._retry_events = 0
        self._page_time_sum = 0.0
        self._slowest_page_s = 0.0
        self._last_record_count = 0
        self._materialize_step_count = 0
        self._materialize_step_time_sum = 0.0
        self._slowest_materialize_step_s = 0.0
        self._slowest_materialize_step: dict[str, Any] | None = None
        self._closed = False

    def write_event(self, kind: str, payload: dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.now(EXPORT_TIMEZONE),
            "kind": kind,
            **payload,
        }
        with self._lock:
            if self._closed:
                return
            self._observe_event(kind, payload)
            if not self._should_persist_event(kind, payload):
                return
            self._handle.write(
                json.dumps(
                    event,
                    ensure_ascii=False,
                    default=_json_default,
                )
                + "\n"
            )
            if self._should_flush_event(kind, payload):
                self._handle.flush()

    def _observe_event(self, kind: str, payload: dict[str, Any]) -> None:
        if kind in {"bounds_scan", "interval_scan", "interval_tail_scan", "tail_scan", "full_scan"}:
            self._pages_scanned = max(self._pages_scanned, int(payload.get("pages_scanned") or 0))
            page_duration_s = float(payload.get("page_duration_s") or 0.0)
            self._page_time_sum += page_duration_s
            self._slowest_page_s = max(self._slowest_page_s, page_duration_s)
            self._last_record_count = max(
                self._last_record_count,
                int(payload.get("collected_messages") or payload.get("matched_messages") or 0),
            )
            return
        if kind == "page_retry":
            self._retry_events += 1
            return
        if kind == "materialize_asset_step" and str(payload.get("stage") or "") == "done":
            step_elapsed_s = float(payload.get("step_elapsed_s") or 0.0)
            self._materialize_step_count += 1
            self._materialize_step_time_sum += step_elapsed_s
            if step_elapsed_s >= self._slowest_materialize_step_s:
                self._slowest_materialize_step_s = step_elapsed_s
                self._slowest_materialize_step = {
                    "current": int(payload.get("current") or 0),
                    "asset_type": payload.get("asset_type"),
                    "asset_role": payload.get("asset_role"),
                    "file_name": payload.get("file_name"),
                    "status": payload.get("status"),
                    "resolver": payload.get("resolver"),
                    "missing_kind": payload.get("missing_kind"),
                    "resolved_source_path": payload.get("resolved_source_path"),
                }

    def _should_persist_event(self, kind: str, payload: dict[str, Any]) -> bool:
        if kind != "materialize_asset_step":
            return True
        stage = str(payload.get("stage") or "")
        current = int(payload.get("current") or 0)
        total = int(payload.get("total") or 0)
        step_elapsed_s = float(payload.get("step_elapsed_s") or 0.0)
        sampled = (
            current in {1, total}
            or (current > 0 and current % MATERIALIZE_STEP_TRACE_SAMPLE_INTERVAL == 0)
        )
        if stage == "done":
            return sampled or step_elapsed_s >= MATERIALIZE_SLOW_STEP_WARN_S
        return sampled

    def _should_flush_event(self, kind: str, payload: dict[str, Any]) -> bool:
        if kind != "materialize_asset_step":
            return True
        step_elapsed_s = float(payload.get("step_elapsed_s") or 0.0)
        return step_elapsed_s >= MATERIALIZE_SLOW_STEP_WARN_S

    def build_summary(self, *, record_count: int | None = None) -> dict[str, Any]:
        with self._lock:
            elapsed_s = (datetime.now(EXPORT_TIMEZONE) - self._started_at).total_seconds()
            average_page_s = self._page_time_sum / self._pages_scanned if self._pages_scanned else 0.0
            average_materialize_step_s = (
                self._materialize_step_time_sum / self._materialize_step_count
                if self._materialize_step_count
                else 0.0
            )
            return {
                "started_at": self._started_at.isoformat(),
                "elapsed_s": round(elapsed_s, 3),
                "pages_scanned": self._pages_scanned,
                "retry_events": self._retry_events,
                "average_page_s": round(average_page_s, 4),
                "slowest_page_s": round(self._slowest_page_s, 4),
                "materialize_step_count": self._materialize_step_count,
                "average_materialize_step_s": round(average_materialize_step_s, 4),
                "slowest_materialize_step_s": round(self._slowest_materialize_step_s, 4),
                "slowest_materialize_step": self._slowest_materialize_step,
                "record_count": self._last_record_count if record_count is None else record_count,
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._handle.close()
