from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Callable

import httpx

from qq_data_core.models import EXPORT_TIMEZONE, ExportRequest, SourceChatSnapshot

from .fast_history_client import (
    FAST_HISTORY_BULK_SAFE_DATA_COUNT,
    FAST_HISTORY_MAX_PAGE_SIZE,
    NapCatFastHistoryClient,
    NapCatFastHistoryError,
    NapCatFastHistoryUnavailable,
)
from .http_client import NapCatApiError, NapCatApiTimeoutError, NapCatHttpClient
from .models import ChatHistoryBounds

HistoryProgressCallback = Callable[[dict[str, Any]], None]

MIN_HISTORY_PAGE_SIZE = 50
SLOW_HISTORY_PAGE_SECONDS = 3.0
FAST_PLUGIN_SLOW_HISTORY_PAGE_SECONDS = 1.5
FAST_HISTORY_PAGE_SECONDS = 0.75
FAST_HISTORY_RECOVERY_STEP = 50
MAX_HISTORY_TIMEOUT_RETRIES = 3
FORWARD_ELEMENT_TYPE = 16
SPARSE_TAIL_FORWARD_HYDRATE_MIN_WINDOW_MESSAGES = 100
SPARSE_TAIL_FORWARD_HYDRATE_MAX_FORWARD_REFS = 2


class NapCatHistoryProvider:
    def __init__(
        self,
        client: NapCatHttpClient,
        *,
        fast_client: NapCatFastHistoryClient | None = None,
        fast_mode: str = "auto",
    ) -> None:
        self._client = client
        self._fast_client = fast_client
        self._fast_mode = fast_mode
        self._fast_available: bool | None = None
        self._fast_tail_bulk_available: bool | None = None
        self._fast_forward_detail_available: bool | None = None
        self._known_unavailable_forward_ids: dict[str, str] = {}
        self._known_unavailable_history_keys: dict[str, str] = {}
        self._forward_history_probe_outcomes: dict[str, dict[str, Any]] = {}

    def reset_export_state(self) -> None:
        self._fast_available = None
        self._fast_tail_bulk_available = None
        self._fast_forward_detail_available = None
        self._known_unavailable_forward_ids.clear()
        self._known_unavailable_history_keys.clear()
        self._forward_history_probe_outcomes.clear()

    @staticmethod
    def _forward_message_key(message: dict[str, Any]) -> str:
        raw_message = _message_raw(message)
        return str(
            message.get("message_seq")
            or message.get("messageSeq")
            or message.get("message_id")
            or message.get("messageId")
            or raw_message.get("msgSeq")
            or raw_message.get("msgId")
            or ""
        ).strip()

    def _record_forward_history_probe_outcome(
        self,
        message: dict[str, Any],
        *,
        has_content: bool,
        route: str,
        terminal_reason: str | None = None,
    ) -> dict[str, Any] | None:
        message_key = self._forward_message_key(message)
        if not message_key:
            return None
        outcome = {
            "attempted": True,
            "has_content": bool(has_content),
            "terminal_reason": terminal_reason,
            "route": route,
        }
        self._forward_history_probe_outcomes[message_key] = outcome
        return outcome

    def _get_forward_history_probe_outcome(
        self,
        message_key: str,
    ) -> dict[str, Any] | None:
        if not message_key:
            return None
        outcome = self._forward_history_probe_outcomes.get(message_key)
        if outcome is not None:
            return outcome
        known_history_unavailable = self._known_unavailable_history_keys.get(message_key)
        if not known_history_unavailable:
            return None
        outcome = {
            "attempted": True,
            "has_content": False,
            "terminal_reason": known_history_unavailable,
            "route": "known_history_unavailable",
        }
        self._forward_history_probe_outcomes[message_key] = outcome
        return outcome

    def _emit_progress(
        self,
        progress_callback: HistoryProgressCallback | None,
        payload: dict[str, Any],
    ) -> None:
        if progress_callback is not None:
            progress_callback(payload)

    def _emit_pipeline_stage(
        self,
        progress_callback: HistoryProgressCallback | None,
        *,
        stage: str,
        status: str,
        elapsed_s: float | None = None,
        **payload: Any,
    ) -> None:
        event: dict[str, Any] = {
            "phase": "pipeline_stage",
            "stage": stage,
            "status": status,
            **payload,
        }
        if elapsed_s is not None:
            event["elapsed_s"] = round(elapsed_s, 4)
            event["elapsed_ms"] = int(round(elapsed_s * 1000))
        self._emit_progress(progress_callback, event)

    def _emit_scan_summary(
        self,
        progress_callback: HistoryProgressCallback | None,
        *,
        scan_phase: str,
        elapsed_s: float,
        exit_reason: str,
        **payload: Any,
    ) -> None:
        self._emit_progress(
            progress_callback,
            {
                "phase": "scan_summary",
                "scan_phase": scan_phase,
                "elapsed_s": round(elapsed_s, 4),
                "elapsed_ms": int(round(elapsed_s * 1000)),
                "exit_reason": exit_reason,
                **payload,
            },
        )

    def fetch_snapshot(
        self,
        request: ExportRequest,
        *,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        started = perf_counter()
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot",
            status="start",
            requested_count=request.limit,
        )
        snapshot = self.fetch_snapshot_before(
            request,
            before_message_seq=None,
            count=request.limit,
            include_forward_details=True,
            progress_callback=progress_callback,
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot",
            status="done",
            elapsed_s=perf_counter() - started,
            requested_count=request.limit,
            message_count=len(snapshot.messages),
            history_source=snapshot.metadata.get("source"),
        )
        return snapshot

    def fetch_snapshot_tail(
        self,
        request: ExportRequest,
        *,
        data_count: int,
        page_size: int = 100,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        if data_count <= 0:
            raise ValueError("data_count must be positive for tail export.")

        started = perf_counter()
        effective_base_page_size = self._normalize_requested_page_size(page_size)
        anchor: str | None = None
        selected_messages: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        pages_scanned = 0
        seen_anchors: set[str] = set()
        current_page_size = effective_base_page_size
        fast_page_streak = 0
        history_source: str | None = None
        bulk_tail_metadata: dict[str, Any] | None = None
        exit_reason = "completed"
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_tail",
            status="start",
            requested_data_count=data_count,
            page_size=effective_base_page_size,
        )

        bulk_state = self._collect_fast_history_tail_bulk(
            request,
            data_count=data_count,
            page_size=effective_base_page_size,
            progress_callback=progress_callback,
        )
        if bulk_state is not None:
            selected_messages = bulk_state["messages"]
            seen_keys = bulk_state["seen_keys"]
            pages_scanned = int(bulk_state["pages_scanned"])
            history_source = str(bulk_state["history_source"] or "")
            bulk_tail_metadata = {
                "bulk_duration_s": bulk_state["bulk_duration_s"],
                "bulk_chunks": bulk_state["bulk_chunks"],
                "bulk_chunk_limit": bulk_state["bulk_chunk_limit"],
                "bulk_partial_fallback": bulk_state["partial_fallback"],
                "pages_scanned": pages_scanned,
            }
            bulk_page_size = int(bulk_state["page_size"] or effective_base_page_size)
            anchor = bulk_state["next_anchor"]
            if anchor:
                seen_anchors.add(anchor)
            if bool(bulk_state["completed"]):
                forward_hydrate_started = perf_counter()
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.tail_forward_hydrate",
                    status="start",
                    message_count=len(selected_messages),
                    page_size=bulk_page_size,
                    history_source=history_source or "napcat_fast_history_bulk",
                )
                hydrated_forward_count = self._hydrate_fast_history_tail_forwards_bulk(
                    request,
                    selected_messages,
                    page_size=bulk_page_size,
                    progress_callback=progress_callback,
                )
                forward_hydrate_s = perf_counter() - forward_hydrate_started
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.tail_forward_hydrate",
                    status="done",
                    elapsed_s=forward_hydrate_s,
                    message_count=len(selected_messages),
                    hydrated_forward_count=hydrated_forward_count,
                    page_size=bulk_page_size,
                    history_source=history_source or "napcat_fast_history_bulk",
                )
                selected_messages.sort(
                    key=lambda item: (_message_datetime(item), _message_sort_key(item))
                )
                metadata = {
                    "source": history_source or "napcat_fast_history_bulk",
                    "page_size": bulk_page_size,
                    "requested_data_count": data_count,
                    "interval_mode": "latest_tail",
                    "pages_scanned": pages_scanned,
                    **bulk_tail_metadata,
                }
                snapshot = SourceChatSnapshot(
                    chat_type=request.chat_type,
                    chat_id=request.chat_id,
                    chat_name=request.chat_name,
                    exported_at=datetime.now(EXPORT_TIMEZONE),
                    metadata=metadata,
                    messages=selected_messages,
                )
                finalized = self._finalize_snapshot(snapshot, progress_callback=progress_callback)
                elapsed_s = perf_counter() - started
                self._emit_scan_summary(
                    progress_callback,
                    scan_phase="tail_scan",
                    elapsed_s=elapsed_s,
                    exit_reason="bulk_completed",
                    pages_scanned=pages_scanned,
                    matched_messages=len(selected_messages),
                    requested_data_count=data_count,
                    history_source=history_source or "napcat_fast_history_bulk",
                    bulk_chunks=int(bulk_tail_metadata.get("bulk_chunks") or 0) if bulk_tail_metadata else 0,
                    bulk_duration_s=float(bulk_tail_metadata.get("bulk_duration_s") or 0.0) if bulk_tail_metadata else 0.0,
                    forward_hydrate_s=round(forward_hydrate_s, 4),
                )
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fetch_snapshot_tail",
                    status="done",
                    elapsed_s=elapsed_s,
                    requested_data_count=data_count,
                    pages_scanned=pages_scanned,
                    message_count=len(selected_messages),
                    history_source=history_source or "napcat_fast_history_bulk",
                    exit_reason="bulk_completed",
                )
                return finalized

        while len(selected_messages) < data_count:
            snapshot, page_metrics = self._fetch_history_page(
                request,
                before_message_seq=anchor,
                count=current_page_size,
                progress_callback=progress_callback,
                phase="page_retry",
                mode="tail_scan",
            )
            page_messages = self._extract_messages(snapshot.messages)
            if not page_messages:
                exit_reason = "empty_page"
                break
            pages_scanned += 1
            history_source = _merge_history_source(
                history_source,
                str(page_metrics.get("history_source") or ""),
            )

            oldest_dt = _message_datetime(page_messages[0])
            newest_dt = _message_datetime(page_messages[-1])
            for message in reversed(page_messages):
                dedupe_key = _message_key(message)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                selected_messages.append(message)
                if len(selected_messages) >= data_count:
                    break
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "tail_scan",
                        "pages_scanned": pages_scanned,
                        "matched_messages": len(selected_messages),
                        "requested_data_count": data_count,
                        "oldest_content_at": oldest_dt,
                        "newest_content_at": newest_dt,
                        "anchor": _history_anchor(page_messages[0]),
                        **page_metrics,
                    }
                )
            current_page_size, fast_page_streak = self._adapt_page_size(
                base_page_size=effective_base_page_size,
                current_page_size=current_page_size,
                page_message_count=len(page_messages),
                page_duration_s=page_metrics["page_duration_s"],
                fast_page_streak=fast_page_streak,
                history_source=str(page_metrics.get("history_source") or ""),
                progress_callback=progress_callback,
                mode="tail_scan",
            )
            next_anchor = _history_anchor(page_messages[0])
            if not next_anchor:
                exit_reason = "missing_anchor"
                break
            if next_anchor in seen_anchors:
                exit_reason = "anchor_loop"
                break
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        selected_messages.sort(
            key=lambda item: (_message_datetime(item), _message_sort_key(item))
        )
        self._hydrate_fast_history_tail_forwards_bulk(
            request,
            selected_messages,
            page_size=effective_base_page_size,
            progress_callback=progress_callback,
        )
        if bulk_tail_metadata is not None:
            bulk_tail_metadata = {
                **bulk_tail_metadata,
                "pages_scanned": pages_scanned,
            }
        snapshot = SourceChatSnapshot(
            chat_type=request.chat_type,
            chat_id=request.chat_id,
            chat_name=request.chat_name,
            exported_at=datetime.now(EXPORT_TIMEZONE),
            metadata={
                "source": history_source or "napcat_http",
                "page_size": effective_base_page_size,
                "requested_data_count": data_count,
                "interval_mode": "latest_tail",
                **(bulk_tail_metadata or {}),
            },
            messages=selected_messages,
        )
        finalized = self._finalize_snapshot(snapshot, progress_callback=progress_callback)
        elapsed_s = perf_counter() - started
        if len(selected_messages) >= data_count:
            exit_reason = "target_reached"
        self._emit_scan_summary(
            progress_callback,
            scan_phase="tail_scan",
            elapsed_s=elapsed_s,
            exit_reason=exit_reason,
            pages_scanned=pages_scanned,
            matched_messages=len(selected_messages),
            requested_data_count=data_count,
            history_source=history_source or "napcat_http",
            bulk_chunks=int(bulk_tail_metadata.get("bulk_chunks") or 0) if bulk_tail_metadata else 0,
            bulk_duration_s=float(bulk_tail_metadata.get("bulk_duration_s") or 0.0) if bulk_tail_metadata else 0.0,
            bulk_partial_fallback=bool((bulk_tail_metadata or {}).get("bulk_partial_fallback")),
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_tail",
            status="done",
            elapsed_s=elapsed_s,
            requested_data_count=data_count,
            pages_scanned=pages_scanned,
            message_count=len(selected_messages),
            history_source=history_source or "napcat_http",
            exit_reason=exit_reason,
        )
        return finalized

    def fetch_snapshot_before(
        self,
        request: ExportRequest,
        *,
        before_message_seq: str | None,
        count: int | None = None,
        include_forward_details: bool = True,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        requested_count = count or request.limit or 20
        reverse_order = before_message_seq not in {None, "", "0"}
        payload: Any
        source = "napcat_http"
        started = perf_counter()
        fast_fetch_s = 0.0
        http_fetch_s = 0.0
        extract_sort_s = 0.0
        fast_forward_hydrate_s = 0.0
        finalize_s = 0.0
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_before",
            status="start",
            before_message_seq=before_message_seq,
            requested_count=requested_count,
            reverse_order=reverse_order,
            include_forward_details=include_forward_details,
        )
        fast_started = perf_counter()
        fast_payload = self._fetch_fast_history(
            request,
            before_message_id=before_message_seq,
            count=requested_count,
            reverse_order=reverse_order,
        )
        fast_fetch_s = perf_counter() - fast_started
        if fast_payload is not None:
            payload = fast_payload
            source = "napcat_fast_history"
        elif request.chat_type == "group":
            http_started = perf_counter()
            payload = self._client.get_group_msg_history(
                request.chat_id,
                message_seq=before_message_seq,
                count=requested_count,
                reverse_order=reverse_order,
            )
            http_fetch_s = perf_counter() - http_started
        else:
            http_started = perf_counter()
            payload = self._client.get_friend_msg_history(
                request.chat_id,
                message_seq=before_message_seq,
                count=requested_count,
                reverse_order=reverse_order,
            )
            http_fetch_s = perf_counter() - http_started

        extract_started = perf_counter()
        messages = _sorted_messages(self._extract_messages(payload))
        extract_sort_s = perf_counter() - extract_started
        if source == "napcat_fast_history":
            hydrate_started = perf_counter()
            self._emit_pipeline_stage(
                progress_callback,
                stage="provider.fast_forward_hydrate",
                status="start",
                message_count=len(messages),
                requested_count=requested_count,
                before_message_seq=before_message_seq,
            )
            hydrated_forward_count = self._hydrate_fast_history_page_forwards(
                request,
                messages,
                before_message_seq=before_message_seq,
                count=requested_count,
                reverse_order=reverse_order,
            )
            fast_forward_hydrate_s = perf_counter() - hydrate_started
            self._emit_pipeline_stage(
                progress_callback,
                stage="provider.fast_forward_hydrate",
                status="done",
                elapsed_s=fast_forward_hydrate_s,
                message_count=len(messages),
                requested_count=requested_count,
                before_message_seq=before_message_seq,
                hydrated_forward_count=hydrated_forward_count,
            )
        snapshot = SourceChatSnapshot(
            chat_type=request.chat_type,
            chat_id=request.chat_id,
            chat_name=request.chat_name,
            exported_at=datetime.now(EXPORT_TIMEZONE),
            metadata={
                "source": source,
                "requested_count": requested_count,
                "before_message_seq": before_message_seq,
                "reverse_order": reverse_order,
            },
            messages=messages,
        )
        if include_forward_details:
            finalize_started = perf_counter()
            snapshot = self._finalize_snapshot(snapshot, progress_callback=progress_callback)
            finalize_s = perf_counter() - finalize_started
        total_elapsed_s = perf_counter() - started
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_before",
            status="done",
            elapsed_s=total_elapsed_s,
            before_message_seq=before_message_seq,
            requested_count=requested_count,
            reverse_order=reverse_order,
            include_forward_details=include_forward_details,
            history_source=source,
            message_count=len(messages),
            fast_fetch_s=round(fast_fetch_s, 4),
            http_fetch_s=round(http_fetch_s, 4),
            extract_sort_s=round(extract_sort_s, 4),
            fast_forward_hydrate_s=round(fast_forward_hydrate_s, 4),
            finalize_s=round(finalize_s, 4),
        )
        return snapshot

    def get_history_bounds(
        self,
        request: ExportRequest,
        *,
        page_size: int = 100,
        need_earliest: bool = True,
        need_final: bool = True,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> ChatHistoryBounds:
        if not need_earliest and not need_final:
            return ChatHistoryBounds()

        started = perf_counter()
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.get_history_bounds",
            status="start",
            need_earliest=need_earliest,
            need_final=need_final,
            page_size=page_size,
        )
        if need_final and not need_earliest:
            latest_snapshot = self.fetch_snapshot_before(
                request, before_message_seq=None, count=1, progress_callback=progress_callback
            )
            latest_messages = self._extract_messages(latest_snapshot.messages)
            bounds = ChatHistoryBounds(
                final_content_at=_message_datetime(latest_messages[-1])
                if latest_messages
                else None,
            )
            elapsed_s = perf_counter() - started
            self._emit_scan_summary(
                progress_callback,
                scan_phase="bounds_scan",
                elapsed_s=elapsed_s,
                exit_reason="final_only",
                pages_scanned=1 if latest_messages else 0,
                history_source=str(latest_snapshot.metadata.get("source") or ""),
                earliest_content_at=None,
                final_content_at=bounds.final_content_at,
            )
            self._emit_pipeline_stage(
                progress_callback,
                stage="provider.get_history_bounds",
                status="done",
                elapsed_s=elapsed_s,
                need_earliest=need_earliest,
                need_final=need_final,
                pages_scanned=1 if latest_messages else 0,
                exit_reason="final_only",
            )
            return bounds

        anchor: str | None = None
        earliest_content_at: datetime | None = None
        final_content_at: datetime | None = None
        pages_scanned = 0
        seen_anchors: set[str] = set()
        current_page_size = self._normalize_requested_page_size(page_size)
        effective_base_page_size = current_page_size
        fast_page_streak = 0
        history_source: str | None = None
        exit_reason = "completed"
        while True:
            snapshot, page_metrics = self._fetch_history_page(
                request,
                before_message_seq=anchor,
                count=current_page_size,
                progress_callback=progress_callback,
                phase="page_retry",
                mode="bounds_scan",
            )
            messages = self._extract_messages(snapshot.messages)
            if not messages:
                exit_reason = "empty_page"
                break
            pages_scanned += 1
            history_source = _merge_history_source(
                history_source,
                str(page_metrics.get("history_source") or ""),
            )
            if need_final and final_content_at is None:
                final_content_at = _message_datetime(messages[-1])
            if need_earliest:
                earliest_content_at = _message_datetime(messages[0])
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "bounds_scan",
                        "pages_scanned": pages_scanned,
                        "earliest_content_at": earliest_content_at,
                        "final_content_at": final_content_at,
                        "anchor": _history_anchor(messages[0]),
                        **page_metrics,
                    }
                )
            current_page_size, fast_page_streak = self._adapt_page_size(
                base_page_size=effective_base_page_size,
                current_page_size=current_page_size,
                page_message_count=len(messages),
                page_duration_s=page_metrics["page_duration_s"],
                fast_page_streak=fast_page_streak,
                history_source=str(page_metrics.get("history_source") or ""),
                progress_callback=progress_callback,
                mode="bounds_scan",
            )
            next_anchor = _history_anchor(messages[0])
            if not need_earliest:
                exit_reason = "final_found"
                break
            if not next_anchor:
                exit_reason = "missing_anchor"
                break
            if next_anchor in seen_anchors:
                exit_reason = "anchor_loop"
                break
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        bounds = ChatHistoryBounds(
            earliest_content_at=earliest_content_at,
            final_content_at=final_content_at,
        )
        elapsed_s = perf_counter() - started
        self._emit_scan_summary(
            progress_callback,
            scan_phase="bounds_scan",
            elapsed_s=elapsed_s,
            exit_reason=exit_reason,
            pages_scanned=pages_scanned,
            history_source=history_source or "napcat_http",
            earliest_content_at=earliest_content_at,
            final_content_at=final_content_at,
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.get_history_bounds",
            status="done",
            elapsed_s=elapsed_s,
            need_earliest=need_earliest,
            need_final=need_final,
            pages_scanned=pages_scanned,
            history_source=history_source or "napcat_http",
            exit_reason=exit_reason,
        )
        return bounds

    def fetch_snapshot_between(
        self,
        request: ExportRequest,
        *,
        page_size: int = 100,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        if request.since is None or request.until is None:
            raise ValueError(
                "ExportRequest.since and ExportRequest.until are required for interval export."
            )

        started = perf_counter()
        lower_bound = min(request.since, request.until).astimezone(EXPORT_TIMEZONE)
        upper_bound = max(request.since, request.until).astimezone(EXPORT_TIMEZONE)
        anchor: str | None = None
        selected_messages: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        pages_scanned = 0
        seen_anchors: set[str] = set()
        current_page_size = self._normalize_requested_page_size(page_size)
        effective_base_page_size = current_page_size
        fast_page_streak = 0
        history_source: str | None = None
        exit_reason = "completed"
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_between",
            status="start",
            since=lower_bound.isoformat(),
            until=upper_bound.isoformat(),
            page_size=effective_base_page_size,
        )

        while True:
            snapshot, page_metrics = self._fetch_history_page(
                request,
                before_message_seq=anchor,
                count=current_page_size,
                progress_callback=progress_callback,
                phase="page_retry",
                mode="interval_scan",
            )
            page_messages = self._extract_messages(snapshot.messages)
            if not page_messages:
                exit_reason = "empty_page"
                break
            pages_scanned += 1
            history_source = _merge_history_source(
                history_source,
                str(page_metrics.get("history_source") or ""),
            )

            oldest_dt = _message_datetime(page_messages[0])
            newest_dt = _message_datetime(page_messages[-1])
            for message in page_messages:
                message_dt = _message_datetime(message)
                if lower_bound <= message_dt <= upper_bound:
                    dedupe_key = _message_key(message)
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)
                    selected_messages.append(message)
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "interval_scan",
                        "pages_scanned": pages_scanned,
                        "matched_messages": len(selected_messages),
                        "oldest_content_at": oldest_dt,
                        "newest_content_at": newest_dt,
                        "anchor": _history_anchor(page_messages[0]),
                        **page_metrics,
                    }
                )
            current_page_size, fast_page_streak = self._adapt_page_size(
                base_page_size=effective_base_page_size,
                current_page_size=current_page_size,
                page_message_count=len(page_messages),
                page_duration_s=page_metrics["page_duration_s"],
                fast_page_streak=fast_page_streak,
                history_source=str(page_metrics.get("history_source") or ""),
                progress_callback=progress_callback,
                mode="interval_scan",
            )

            next_anchor = _history_anchor(page_messages[0])
            if oldest_dt <= lower_bound or newest_dt < lower_bound:
                exit_reason = "crossed_lower_bound"
                break
            if not next_anchor:
                exit_reason = "missing_anchor"
                break
            if next_anchor in seen_anchors:
                exit_reason = "anchor_loop"
                break
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        selected_messages.sort(
            key=lambda item: (_message_datetime(item), _message_sort_key(item))
        )
        snapshot = SourceChatSnapshot(
            chat_type=request.chat_type,
            chat_id=request.chat_id,
            chat_name=request.chat_name,
            exported_at=datetime.now(EXPORT_TIMEZONE),
            metadata={
                "source": history_source or "napcat_http",
                "since": lower_bound.isoformat(),
                "until": upper_bound.isoformat(),
                "page_size": effective_base_page_size,
            },
            messages=selected_messages,
        )
        finalized = self._finalize_snapshot(snapshot, progress_callback=progress_callback)
        elapsed_s = perf_counter() - started
        self._emit_scan_summary(
            progress_callback,
            scan_phase="interval_scan",
            elapsed_s=elapsed_s,
            exit_reason=exit_reason,
            pages_scanned=pages_scanned,
            matched_messages=len(selected_messages),
            history_source=history_source or "napcat_http",
            since=lower_bound.isoformat(),
            until=upper_bound.isoformat(),
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_between",
            status="done",
            elapsed_s=elapsed_s,
            pages_scanned=pages_scanned,
            message_count=len(selected_messages),
            history_source=history_source or "napcat_http",
            exit_reason=exit_reason,
        )
        return finalized

    def fetch_snapshot_tail_between(
        self,
        request: ExportRequest,
        *,
        data_count: int,
        page_size: int = 100,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        if request.since is None or request.until is None:
            raise ValueError(
                "ExportRequest.since and ExportRequest.until are required for interval export."
            )
        if data_count <= 0:
            raise ValueError("data_count must be positive for tail interval export.")

        started = perf_counter()
        lower_bound = min(request.since, request.until).astimezone(EXPORT_TIMEZONE)
        upper_bound = max(request.since, request.until).astimezone(EXPORT_TIMEZONE)
        anchor: str | None = None
        selected_messages: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        pages_scanned = 0
        seen_anchors: set[str] = set()
        current_page_size = self._normalize_requested_page_size(page_size)
        effective_base_page_size = current_page_size
        fast_page_streak = 0
        history_source: str | None = None
        exit_reason = "completed"
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_tail_between",
            status="start",
            since=lower_bound.isoformat(),
            until=upper_bound.isoformat(),
            requested_data_count=data_count,
            page_size=effective_base_page_size,
        )

        while len(selected_messages) < data_count:
            snapshot, page_metrics = self._fetch_history_page(
                request,
                before_message_seq=anchor,
                count=current_page_size,
                progress_callback=progress_callback,
                phase="page_retry",
                mode="interval_tail_scan",
            )
            page_messages = self._extract_messages(snapshot.messages)
            if not page_messages:
                exit_reason = "empty_page"
                break
            pages_scanned += 1
            history_source = _merge_history_source(
                history_source,
                str(page_metrics.get("history_source") or ""),
            )

            oldest_dt = _message_datetime(page_messages[0])
            newest_dt = _message_datetime(page_messages[-1])
            for message in reversed(page_messages):
                message_dt = _message_datetime(message)
                if message_dt > upper_bound:
                    continue
                if message_dt < lower_bound:
                    break
                dedupe_key = _message_key(message)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                selected_messages.append(message)
                if len(selected_messages) >= data_count:
                    break
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "interval_tail_scan",
                        "pages_scanned": pages_scanned,
                        "matched_messages": len(selected_messages),
                        "requested_data_count": data_count,
                        "oldest_content_at": oldest_dt,
                        "newest_content_at": newest_dt,
                        "anchor": _history_anchor(page_messages[0]),
                        **page_metrics,
                    }
                )
            current_page_size, fast_page_streak = self._adapt_page_size(
                base_page_size=effective_base_page_size,
                current_page_size=current_page_size,
                page_message_count=len(page_messages),
                page_duration_s=page_metrics["page_duration_s"],
                fast_page_streak=fast_page_streak,
                history_source=str(page_metrics.get("history_source") or ""),
                progress_callback=progress_callback,
                mode="interval_tail_scan",
            )
            next_anchor = _history_anchor(page_messages[0])
            if newest_dt < lower_bound:
                exit_reason = "crossed_lower_bound"
                break
            if not next_anchor:
                exit_reason = "missing_anchor"
                break
            if next_anchor in seen_anchors:
                exit_reason = "anchor_loop"
                break
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        selected_messages.sort(
            key=lambda item: (_message_datetime(item), _message_sort_key(item))
        )
        snapshot = SourceChatSnapshot(
            chat_type=request.chat_type,
            chat_id=request.chat_id,
            chat_name=request.chat_name,
            exported_at=datetime.now(EXPORT_TIMEZONE),
            metadata={
                "source": history_source or "napcat_http",
                "since": lower_bound.isoformat(),
                "until": upper_bound.isoformat(),
                "page_size": effective_base_page_size,
                "requested_data_count": data_count,
                "interval_mode": "closed_tail",
            },
            messages=selected_messages,
        )
        finalized = self._finalize_snapshot(snapshot, progress_callback=progress_callback)
        elapsed_s = perf_counter() - started
        if len(selected_messages) >= data_count:
            exit_reason = "target_reached"
        self._emit_scan_summary(
            progress_callback,
            scan_phase="interval_tail_scan",
            elapsed_s=elapsed_s,
            exit_reason=exit_reason,
            pages_scanned=pages_scanned,
            matched_messages=len(selected_messages),
            requested_data_count=data_count,
            history_source=history_source or "napcat_http",
            since=lower_bound.isoformat(),
            until=upper_bound.isoformat(),
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_snapshot_tail_between",
            status="done",
            elapsed_s=elapsed_s,
            pages_scanned=pages_scanned,
            message_count=len(selected_messages),
            history_source=history_source or "napcat_http",
            exit_reason=exit_reason,
        )
        return finalized

    def fetch_full_snapshot(
        self,
        request: ExportRequest,
        *,
        page_size: int = 100,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        started = perf_counter()
        anchor: str | None = None
        collected_messages: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        pages_scanned = 0
        earliest_content_at: datetime | None = None
        final_content_at: datetime | None = None
        seen_anchors: set[str] = set()
        current_page_size = self._normalize_requested_page_size(page_size)
        effective_base_page_size = current_page_size
        fast_page_streak = 0
        history_source: str | None = None
        exit_reason = "completed"
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_full_snapshot",
            status="start",
            page_size=effective_base_page_size,
        )

        bulk_state = self._collect_fast_history_full_bulk(
            request,
            page_size=effective_base_page_size,
            progress_callback=progress_callback,
        )
        if bulk_state is not None:
            collected_messages = list(bulk_state["messages"])
            seen_keys = set(str(item) for item in bulk_state["seen_keys"])
            pages_scanned = int(bulk_state["pages_scanned"])
            history_source = str(bulk_state["history_source"] or history_source or "")
            earliest_content_at = bulk_state.get("earliest_content_at")
            final_content_at = bulk_state.get("final_content_at")
            anchor = str(bulk_state.get("next_anchor") or "").strip() or None
            if anchor:
                seen_anchors.add(anchor)
            if bulk_state["completed"]:
                exit_reason = "bulk_completed"
                collected_messages.sort(
                    key=lambda item: (_message_datetime(item), _message_sort_key(item))
                )
                snapshot = SourceChatSnapshot(
                    chat_type=request.chat_type,
                    chat_id=request.chat_id,
                    chat_name=request.chat_name,
                    exported_at=datetime.now(EXPORT_TIMEZONE),
                    metadata={
                        "source": history_source or "napcat_http",
                        "page_size": effective_base_page_size,
                        "resolved_since": earliest_content_at.isoformat()
                        if earliest_content_at
                        else None,
                        "resolved_until": final_content_at.isoformat()
                        if final_content_at
                        else None,
                        "interval_mode": "closed",
                        "full_history": True,
                    },
                    messages=collected_messages,
                )
                finalized = self._finalize_snapshot(
                    snapshot, progress_callback=progress_callback
                )
                elapsed_s = perf_counter() - started
                self._emit_scan_summary(
                    progress_callback,
                    scan_phase="full_scan",
                    elapsed_s=elapsed_s,
                    exit_reason=exit_reason,
                    pages_scanned=pages_scanned,
                    collected_messages=len(collected_messages),
                    history_source=history_source or "napcat_http",
                    earliest_content_at=earliest_content_at,
                    final_content_at=final_content_at,
                )
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fetch_full_snapshot",
                    status="done",
                    elapsed_s=elapsed_s,
                    pages_scanned=pages_scanned,
                    message_count=len(collected_messages),
                    history_source=history_source or "napcat_http",
                    exit_reason=exit_reason,
                )
                return finalized
            if bulk_state.get("partial_fallback"):
                exit_reason = "bulk_partial_fallback"

        while True:
            snapshot, page_metrics = self._fetch_history_page(
                request,
                before_message_seq=anchor,
                count=current_page_size,
                progress_callback=progress_callback,
                phase="page_retry",
                mode="full_scan",
            )
            page_messages = self._extract_messages(snapshot.messages)
            if not page_messages:
                exit_reason = "empty_page"
                break
            pages_scanned += 1
            history_source = _merge_history_source(
                history_source,
                str(page_metrics.get("history_source") or ""),
            )
            if final_content_at is None:
                final_content_at = _message_datetime(page_messages[-1])
            earliest_content_at = _message_datetime(page_messages[0])
            for message in page_messages:
                dedupe_key = _message_key(message)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                collected_messages.append(message)
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "full_scan",
                        "pages_scanned": pages_scanned,
                        "collected_messages": len(collected_messages),
                        "earliest_content_at": earliest_content_at,
                        "final_content_at": final_content_at,
                        "anchor": _history_anchor(page_messages[0]),
                        **page_metrics,
                    }
                )
            current_page_size, fast_page_streak = self._adapt_page_size(
                base_page_size=effective_base_page_size,
                current_page_size=current_page_size,
                page_message_count=len(page_messages),
                page_duration_s=page_metrics["page_duration_s"],
                fast_page_streak=fast_page_streak,
                history_source=str(page_metrics.get("history_source") or ""),
                progress_callback=progress_callback,
                mode="full_scan",
            )
            next_anchor = _history_anchor(page_messages[0])
            if not next_anchor:
                exit_reason = "missing_anchor"
                break
            if next_anchor in seen_anchors:
                exit_reason = "anchor_loop"
                break
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        collected_messages.sort(
            key=lambda item: (_message_datetime(item), _message_sort_key(item))
        )
        snapshot = SourceChatSnapshot(
            chat_type=request.chat_type,
            chat_id=request.chat_id,
            chat_name=request.chat_name,
            exported_at=datetime.now(EXPORT_TIMEZONE),
            metadata={
                "source": history_source or "napcat_http",
                "page_size": effective_base_page_size,
                "resolved_since": earliest_content_at.isoformat()
                if earliest_content_at
                else None,
                "resolved_until": final_content_at.isoformat()
                if final_content_at
                else None,
                "interval_mode": "closed",
                "full_history": True,
            },
            messages=collected_messages,
        )
        finalized = self._finalize_snapshot(snapshot, progress_callback=progress_callback)
        elapsed_s = perf_counter() - started
        self._emit_scan_summary(
            progress_callback,
            scan_phase="full_scan",
            elapsed_s=elapsed_s,
            exit_reason=exit_reason,
            pages_scanned=pages_scanned,
            collected_messages=len(collected_messages),
            history_source=history_source or "napcat_http",
            earliest_content_at=earliest_content_at,
            final_content_at=final_content_at,
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fetch_full_snapshot",
            status="done",
            elapsed_s=elapsed_s,
            pages_scanned=pages_scanned,
            message_count=len(collected_messages),
            history_source=history_source or "napcat_http",
            exit_reason=exit_reason,
        )
        return finalized

    def _collect_fast_history_full_bulk(
        self,
        request: ExportRequest,
        *,
        page_size: int,
        progress_callback: HistoryProgressCallback | None,
    ) -> dict[str, Any] | None:
        if self._fast_client is None or self._fast_mode == "off":
            return None
        chunk_limit = FAST_HISTORY_BULK_SAFE_DATA_COUNT
        anchor: str | None = None
        seen_keys: set[str] = set()
        seen_anchors: set[str] = set()
        collected_messages: list[dict[str, Any]] = []
        pages_scanned = 0
        chunk_count = 0
        total_started = perf_counter()
        final_content_at: datetime | None = None
        earliest_content_at: datetime | None = None
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fast_full_bulk",
            status="start",
            page_size=page_size,
            chunk_limit=chunk_limit,
        )

        while True:
            chunk_started = perf_counter()
            payload = self._fetch_fast_history_tail_bulk(
                request,
                data_count=chunk_limit,
                page_size=page_size,
                anchor_message_id=anchor,
            )
            if payload is None:
                if chunk_count <= 0:
                    self._emit_pipeline_stage(
                        progress_callback,
                        stage="provider.fast_full_bulk",
                        status="done",
                        elapsed_s=perf_counter() - total_started,
                        pages_scanned=pages_scanned,
                        bulk_chunks=chunk_count,
                        exit_reason="unavailable_initial",
                    )
                    return None
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fast_full_bulk",
                    status="done",
                    elapsed_s=perf_counter() - total_started,
                    pages_scanned=pages_scanned,
                    bulk_chunks=chunk_count,
                    exit_reason="partial_fallback",
                )
                return {
                    "messages": collected_messages,
                    "seen_keys": seen_keys,
                    "next_anchor": anchor,
                    "pages_scanned": pages_scanned,
                    "completed": False,
                    "history_source": "napcat_fast_history_bulk",
                    "bulk_duration_s": round(perf_counter() - total_started, 4),
                    "bulk_chunks": chunk_count,
                    "bulk_chunk_limit": chunk_limit,
                    "partial_fallback": True,
                    "page_size": page_size,
                    "earliest_content_at": earliest_content_at,
                    "final_content_at": final_content_at,
                }

            chunk_count += 1
            chunk_duration_s = round(perf_counter() - chunk_started, 4)
            chunk_messages = _sorted_messages(self._extract_messages(payload.get("messages")))
            pages_scanned += int(payload.get("pages_scanned") or 0)
            if chunk_messages and final_content_at is None:
                final_content_at = _message_datetime(chunk_messages[-1])
            if chunk_messages:
                earliest_content_at = _message_datetime(chunk_messages[0])
            added = 0
            for message in chunk_messages:
                dedupe_key = _message_key(message)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                collected_messages.append(message)
                added += 1

            oldest_dt = _message_datetime(chunk_messages[0]) if chunk_messages else None
            newest_dt = _message_datetime(chunk_messages[-1]) if chunk_messages else None
            next_anchor = (
                str(payload.get("next_anchor") or "").strip()
                or (_history_anchor(chunk_messages[0]) if chunk_messages else None)
            )
            exhausted = bool(payload.get("exhausted"))
            total_duration_s = round(perf_counter() - total_started, 4)
            self._emit_progress(
                progress_callback,
                {
                    "phase": "history_page_done",
                    "mode": "full_scan",
                    "history_source": "napcat_fast_history_bulk",
                    "status": "done",
                    "page_duration_s": chunk_duration_s,
                    "page_message_count": len(chunk_messages),
                    "page_size": int(payload.get("page_size") or page_size),
                    "requested_count": chunk_limit,
                    "retry_count": 0,
                    "chunk_index": chunk_count,
                    "chunk_added": added,
                    "pages_scanned": pages_scanned,
                    "next_anchor": next_anchor,
                    "oldest_content_at": oldest_dt,
                    "newest_content_at": newest_dt,
                },
            )
            self._emit_progress(
                progress_callback,
                {
                    "phase": "tail_bulk_chunk",
                    "mode": "full_scan",
                    "status": "done",
                    "chunk_index": chunk_count,
                    "chunk_target": chunk_limit,
                    "chunk_added": added,
                    "chunk_messages": len(chunk_messages),
                    "chunk_duration_s": chunk_duration_s,
                    "total_duration_s": total_duration_s,
                    "pages_scanned": pages_scanned,
                    "next_anchor": next_anchor,
                    "exhausted": exhausted,
                    "requested_data_count": len(collected_messages),
                },
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "full_scan",
                        "pages_scanned": pages_scanned,
                        "collected_messages": len(collected_messages),
                        "earliest_content_at": earliest_content_at,
                        "final_content_at": final_content_at,
                        "anchor": next_anchor,
                        "history_source": "napcat_fast_history_bulk",
                        "page_duration_s": chunk_duration_s,
                        "bulk_duration_s": total_duration_s,
                        "page_size": int(payload.get("page_size") or page_size),
                        "page_message_count": len(chunk_messages),
                        "retry_count": 0,
                        "bulk_chunks": chunk_count,
                        "bulk_chunk_limit": chunk_limit,
                    }
                )

            if exhausted:
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fast_full_bulk",
                    status="done",
                    elapsed_s=perf_counter() - total_started,
                    pages_scanned=pages_scanned,
                    bulk_chunks=chunk_count,
                    message_count=len(collected_messages),
                    exit_reason="exhausted",
                )
                return {
                    "messages": collected_messages,
                    "seen_keys": seen_keys,
                    "next_anchor": next_anchor,
                    "pages_scanned": pages_scanned,
                    "completed": True,
                    "history_source": "napcat_fast_history_bulk",
                    "bulk_duration_s": total_duration_s,
                    "bulk_chunks": chunk_count,
                    "bulk_chunk_limit": chunk_limit,
                    "partial_fallback": False,
                    "page_size": int(payload.get("page_size") or page_size),
                    "earliest_content_at": earliest_content_at,
                    "final_content_at": final_content_at,
                }

            if not next_anchor or next_anchor in seen_anchors or added <= 0:
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fast_full_bulk",
                    status="done",
                    elapsed_s=perf_counter() - total_started,
                    pages_scanned=pages_scanned,
                    bulk_chunks=chunk_count,
                    message_count=len(collected_messages),
                    exit_reason="boundary_stall",
                )
                return {
                    "messages": collected_messages,
                    "seen_keys": seen_keys,
                    "next_anchor": anchor,
                    "pages_scanned": pages_scanned,
                    "completed": False,
                    "history_source": "napcat_fast_history_bulk",
                    "bulk_duration_s": total_duration_s,
                    "bulk_chunks": chunk_count,
                    "bulk_chunk_limit": chunk_limit,
                    "partial_fallback": True,
                    "page_size": int(payload.get("page_size") or page_size),
                    "earliest_content_at": earliest_content_at,
                    "final_content_at": final_content_at,
                }

            seen_anchors.add(next_anchor)
            anchor = next_anchor

    def _extract_messages(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("messages", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _fetch_history_page(
        self,
        request: ExportRequest,
        *,
        before_message_seq: str | None,
        count: int,
        progress_callback: HistoryProgressCallback | None,
        phase: str,
        mode: str,
    ) -> tuple[SourceChatSnapshot, dict[str, Any]]:
        attempts = 0
        requested_count = max(MIN_HISTORY_PAGE_SIZE, count)
        while True:
            attempts += 1
            started = perf_counter()
            try:
                snapshot = self.fetch_snapshot_before(
                    request,
                    before_message_seq=before_message_seq,
                    count=requested_count,
                    include_forward_details=False,
                    progress_callback=progress_callback,
                )
            except (httpx.ReadTimeout, NapCatApiTimeoutError):
                next_count = max(MIN_HISTORY_PAGE_SIZE, requested_count // 2)
                if (
                    requested_count == MIN_HISTORY_PAGE_SIZE
                    or attempts >= MAX_HISTORY_TIMEOUT_RETRIES
                ):
                    raise
                if progress_callback is not None:
                    progress_callback(
                        {
                            "phase": phase,
                            "mode": mode,
                            "reason": "read_timeout",
                            "before_message_seq": before_message_seq,
                            "requested_count": requested_count,
                            "next_page_size": next_count,
                            "retry_count": attempts,
                        }
                    )
                    progress_callback(
                        {
                            "phase": "history_page_done",
                            "mode": mode,
                            "before_message_seq": before_message_seq,
                            "requested_count": requested_count,
                            "history_source": "timeout",
                            "page_duration_s": round(perf_counter() - started, 4),
                            "page_message_count": 0,
                            "retry_count": attempts,
                            "status": "retry",
                        }
                    )
                requested_count = next_count
                continue

            page_duration_s = perf_counter() - started
            page_messages = self._extract_messages(snapshot.messages)
            self._emit_progress(
                progress_callback,
                {
                    "phase": "history_page_done",
                    "mode": mode,
                    "before_message_seq": before_message_seq,
                    "requested_count": requested_count,
                    "history_source": snapshot.metadata.get("source"),
                    "page_duration_s": round(page_duration_s, 4),
                    "page_message_count": len(page_messages),
                    "retry_count": attempts - 1,
                    "status": "done",
                    "page_oldest_content_at": _message_datetime(page_messages[0]) if page_messages else None,
                    "page_newest_content_at": _message_datetime(page_messages[-1]) if page_messages else None,
                    "page_anchor": _history_anchor(page_messages[0]) if page_messages else None,
                },
            )
            return (
                snapshot,
                {
                    "history_source": snapshot.metadata.get("source"),
                    "page_duration_s": round(page_duration_s, 4),
                    "page_size": requested_count,
                    "page_message_count": len(page_messages),
                    "retry_count": attempts - 1,
                },
            )

    def _finalize_snapshot(
        self,
        snapshot: SourceChatSnapshot,
        *,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
        started = perf_counter()
        source = str(snapshot.metadata.get("source") or "").strip()
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.finalize_snapshot",
            status="start",
            history_source=source or "napcat_http",
            message_count=len(snapshot.messages),
        )
        enriched_count, structure_unavailable_count = self._enrich_forward_details(
            snapshot.messages,
            chat_type=snapshot.chat_type,
            chat_id=snapshot.chat_id,
            skip_history_retry=False,
            progress_callback=progress_callback,
        )
        if enriched_count <= 0 and structure_unavailable_count <= 0:
            self._emit_pipeline_stage(
                progress_callback,
                stage="provider.finalize_snapshot",
                status="done",
                elapsed_s=perf_counter() - started,
                history_source=source or "napcat_http",
                message_count=len(snapshot.messages),
                forward_detail_count=0,
                forward_structure_unavailable_count=0,
            )
            return snapshot
        metadata = dict(snapshot.metadata)
        if enriched_count > 0:
            metadata["forward_detail_count"] = enriched_count
        if structure_unavailable_count > 0:
            metadata["forward_structure_unavailable_count"] = structure_unavailable_count
        finalized = snapshot.model_copy(update={"metadata": metadata})
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.finalize_snapshot",
            status="done",
            elapsed_s=perf_counter() - started,
            history_source=source or "napcat_http",
            message_count=len(snapshot.messages),
            forward_detail_count=enriched_count,
            forward_structure_unavailable_count=structure_unavailable_count,
        )
        return finalized

    def _enrich_forward_details(
        self,
        messages: list[dict[str, Any]],
        *,
        chat_type: str,
        chat_id: str,
        skip_history_retry: bool = False,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> tuple[int, int]:
        started = perf_counter()
        cache: dict[str, list[dict[str, Any]] | None] = {}
        parse_mult_cache: dict[str, dict[str, Any] | None] = {}
        structure_unavailable = 0
        history_retry_calls = 0
        history_retry_hits = 0
        fast_plugin_calls = 0
        fast_plugin_hits = 0
        known_fast_plugin_unavailable_hits = 0
        get_forward_msg_calls = 0
        get_forward_msg_hits = 0
        known_history_unavailable_hits = 0
        known_forward_unavailable_hits = 0
        cache_hits = 0
        already_resolved = sum(
            1
            for message in messages
            if self._message_has_resolved_forward_content(message)
        )
        targets = list(self._iter_forward_targets(messages))
        total_targets = already_resolved + len(targets)
        if total_targets <= 0:
            return 0, 0

        def _history_outcome(message_key: str) -> dict[str, Any] | None:
            if not message_key:
                return None
            if (
                message_key not in parse_mult_cache
                or parse_mult_cache[message_key] is None
            ):
                parse_mult_cache[message_key] = self._get_forward_history_probe_outcome(
                    message_key
                )
            return parse_mult_cache[message_key]

        processed = already_resolved
        enriched = already_resolved
        for target in targets:
            processed += 1
            attach = target.get("attach")
            if isinstance(attach, dict) and str(
                attach.get("_qq_data_forward_unavailable_reason") or ""
            ).strip():
                if progress_callback is not None and (
                    processed == total_targets or processed % 10 == 0
                ):
                    progress_callback(
                        {
                            "phase": "forward_expand",
                            "processed_forwards": processed,
                            "total_forwards": total_targets,
                            "resolved_forwards": enriched,
                        }
                    )
                continue

            message_key = self._forward_message_key(target["message"])
            forward_id = target["forward_id"]
            history_outcome = _history_outcome(message_key)
            if forward_id in cache:
                cache_hits += 1
                resolved_messages = cache.get(forward_id)
                if resolved_messages:
                    target["attach"][target["key"]] = resolved_messages
                    enriched += 1
                if progress_callback is not None and (
                    processed == total_targets or processed % 10 == 0
                ):
                    progress_callback(
                        {
                            "phase": "forward_expand",
                            "processed_forwards": processed,
                            "total_forwards": total_targets,
                            "resolved_forwards": enriched,
                        }
                    )
                continue

            fast_plugin_messages: list[dict[str, Any]] | None = None
            fast_plugin_reason: str | None = None
            if not skip_history_retry:
                fast_plugin_calls += 1
                fast_plugin_messages, fast_plugin_reason = (
                    self._hydrate_forward_message_via_fast_plugin(target)
                )
                if fast_plugin_messages:
                    fast_plugin_hits += 1
                    cache[forward_id] = fast_plugin_messages
                    target["attach"][target["key"]] = fast_plugin_messages
                    enriched += 1
                    if progress_callback is not None and (
                        processed == total_targets or processed % 10 == 0
                    ):
                        progress_callback(
                            {
                                "phase": "forward_expand",
                                "processed_forwards": processed,
                                "total_forwards": total_targets,
                                "resolved_forwards": enriched,
                            }
                        )
                    continue
                if fast_plugin_reason:
                    known_fast_plugin_unavailable_hits += 1

            if (
                not skip_history_retry
                and message_key
                and history_outcome is None
            ):
                history_retry_calls += 1
                hydrated_via_history, known_history_unavailable = (
                    self._hydrate_forward_message_via_history(
                        target["message"],
                        chat_type=chat_type,
                        chat_id=chat_id,
                    )
                )
                history_outcome = _history_outcome(message_key)
                if hydrated_via_history:
                    history_retry_hits += 1
                elif known_history_unavailable:
                    known_history_unavailable_hits += 1
                if history_outcome and history_outcome.get("has_content"):
                    enriched += 1
            elif (
                history_outcome is not None
                and history_outcome.get("route") == "known_history_unavailable"
            ):
                known_history_unavailable_hits += 1
            if history_outcome and history_outcome.get("has_content"):
                if progress_callback is not None and (
                    processed == total_targets or processed % 10 == 0
                ):
                    progress_callback(
                        {
                            "phase": "forward_expand",
                            "processed_forwards": processed,
                            "total_forwards": total_targets,
                            "resolved_forwards": enriched,
                        }
                    )
                continue

            if forward_id in self._known_unavailable_forward_ids:
                known_forward_unavailable_hits += 1
                cache[forward_id] = None
                recovered_via_history = False
                if history_outcome and history_outcome.get("attempted"):
                    if self._mark_forward_target_unavailable(
                        target,
                        reason=str(
                            history_outcome.get("terminal_reason")
                            or self._known_unavailable_forward_ids[forward_id]
                            or "forward_structure_unavailable_via_get_forward_msg"
                        ),
                    ):
                        structure_unavailable += 1
                elif message_key:
                    history_retry_calls += 1
                    hydrated_via_history, known_history_unavailable = (
                        self._hydrate_forward_message_via_history(
                            target["message"],
                            chat_type=chat_type,
                            chat_id=chat_id,
                        )
                    )
                    history_outcome = _history_outcome(message_key)
                    if hydrated_via_history:
                        history_retry_hits += 1
                        enriched += 1
                        cache[forward_id] = []
                        recovered_via_history = True
                    elif self._mark_forward_target_unavailable(
                        target,
                        reason=str(
                            (history_outcome or {}).get("terminal_reason")
                            or known_history_unavailable
                            or self._known_unavailable_forward_ids[forward_id]
                            or "forward_structure_unavailable_via_get_forward_msg"
                        ),
                    ):
                        structure_unavailable += 1
                elif self._mark_forward_target_unavailable(
                    target,
                    reason=self._known_unavailable_forward_ids[forward_id]
                    or "forward_structure_unavailable_via_get_forward_msg",
                ):
                    structure_unavailable += 1
            if forward_id not in cache:
                get_forward_msg_calls += 1
                try:
                    response = self._client.get_forward_msg(forward_id)
                except (NapCatApiError, httpx.HTTPError) as exc:
                    cache[forward_id] = None
                    known_forward_unavailable = self._known_forward_detail_unavailable_reason(exc)
                    if known_forward_unavailable:
                        self._known_unavailable_forward_ids[forward_id] = known_forward_unavailable
                        recovered_via_history = False
                        if history_outcome and history_outcome.get("attempted"):
                            if self._mark_forward_target_unavailable(
                                target,
                                reason=str(
                                    history_outcome.get("terminal_reason")
                                    or known_forward_unavailable
                                ),
                            ):
                                structure_unavailable += 1
                        elif message_key:
                            history_retry_calls += 1
                            hydrated_via_history, known_history_unavailable = (
                                self._hydrate_forward_message_via_history(
                                    target["message"],
                                    chat_type=chat_type,
                                    chat_id=chat_id,
                                )
                            )
                            history_outcome = _history_outcome(message_key)
                            if hydrated_via_history:
                                history_retry_hits += 1
                                enriched += 1
                                cache[forward_id] = []
                                recovered_via_history = True
                            elif self._mark_forward_target_unavailable(
                                target,
                                reason=str(
                                    (history_outcome or {}).get("terminal_reason")
                                    or known_history_unavailable
                                    or known_forward_unavailable
                                ),
                            ):
                                structure_unavailable += 1
                        elif self._mark_forward_target_unavailable(
                            target,
                            reason=known_forward_unavailable,
                        ):
                            structure_unavailable += 1
                else:
                    payload = (
                        response
                        if isinstance(response, dict)
                        else {"messages": response}
                    )
                    value = payload.get("messages")
                    cache[forward_id] = (
                        [item for item in value if isinstance(item, dict)]
                        if isinstance(value, list)
                        else None
                    )
                    if cache[forward_id]:
                        get_forward_msg_hits += 1
            resolved_messages = cache.get(forward_id)
            if resolved_messages:
                target["attach"][target["key"]] = resolved_messages
                enriched += 1
            if progress_callback is not None and (
                processed == total_targets or processed % 10 == 0
            ):
                progress_callback(
                    {
                        "phase": "forward_expand",
                        "processed_forwards": processed,
                        "total_forwards": total_targets,
                        "resolved_forwards": enriched,
                    }
                )
        self._emit_progress(
            progress_callback,
            {
                "phase": "forward_expand_summary",
                "elapsed_s": round(perf_counter() - started, 4),
                "total_forwards": total_targets,
                "processed_forwards": processed,
                "resolved_forwards": enriched,
                "already_resolved": already_resolved,
                "structure_unavailable_count": structure_unavailable,
                "fast_plugin_calls": fast_plugin_calls,
                "fast_plugin_hits": fast_plugin_hits,
                "known_fast_plugin_unavailable_hits": known_fast_plugin_unavailable_hits,
                "history_retry_calls": history_retry_calls,
                "history_retry_hits": history_retry_hits,
                "get_forward_msg_calls": get_forward_msg_calls,
                "get_forward_msg_hits": get_forward_msg_hits,
                "known_history_unavailable_hits": known_history_unavailable_hits,
                "known_forward_unavailable_hits": known_forward_unavailable_hits,
                "cache_hits": cache_hits,
            },
        )
        return enriched, structure_unavailable

    @staticmethod
    def _mark_forward_target_unavailable(
        target: dict[str, Any],
        *,
        reason: str,
    ) -> bool:
        attach = target.get("attach")
        if not isinstance(attach, dict):
            return False
        if str(attach.get("_qq_data_forward_unavailable_reason") or "").strip():
            return False
        attach["_qq_data_forward_unavailable_reason"] = reason
        return True

    def _known_forward_detail_unavailable_reason(self, exc: Exception) -> str | None:
        if not isinstance(exc, NapCatApiError):
            return None
        message = str(exc).strip().lower()
        if not message:
            return None
        if "unexpected end of file" in message:
            return "forward_structure_unavailable_unexpected_eof"
        if "protocolfallbacklogic" in message or "找不到相关的聊天记录" in message:
            return "forward_structure_unavailable_protocol_fallback"
        if "消息已过期" in message:
            return "forward_structure_unavailable_expired"
        if "内层消息" in message:
            return "forward_structure_unavailable_inner_message"
        return None

    def _hydrate_forward_message_via_fast_plugin(
        self,
        target: dict[str, Any],
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        if self._fast_client is None or self._fast_mode == "off":
            return None, None
        hydrate_forward_detail = getattr(self._fast_client, "hydrate_forward_detail", None)
        if not callable(hydrate_forward_detail):
            return None, None
        if self._fast_forward_detail_available is False and self._fast_mode != "force":
            return None, "forward_structure_unavailable_fast_plugin_route"

        message = target.get("message")
        if not isinstance(message, dict):
            return None, None
        raw_message = _message_raw(message)
        message_id_raw = str(
            target.get("message_id")
            or message.get("message_id")
            or message.get("messageId")
            or raw_message.get("msgId")
            or ""
        ).strip()
        element_id = str(target.get("element_id") or "").strip()
        peer_uid = str(raw_message.get("peerUid") or "").strip()
        chat_type_raw = raw_message.get("chatType")
        if (
            not message_id_raw
            or not element_id
            or not peer_uid
            or chat_type_raw in {None, ""}
        ):
            return None, None

        try:
            payload = hydrate_forward_detail(
                message_id_raw=message_id_raw,
                element_id=element_id,
                peer_uid=peer_uid,
                chat_type_raw=chat_type_raw,
            )
        except NapCatFastHistoryUnavailable:
            if self._fast_mode == "force":
                raise
            self._fast_forward_detail_available = False
            return None, "forward_structure_unavailable_fast_plugin_route"
        except NapCatFastHistoryError:
            if self._fast_mode == "force":
                raise
            return None, None
        except httpx.HTTPError:
            return None, None

        self._fast_available = True
        self._fast_forward_detail_available = True
        nested_messages = self._extract_messages(payload)
        if not nested_messages:
            return None, None
        return nested_messages, None

    def _hydrate_forward_message_via_history(
        self,
        message: dict[str, Any],
        *,
        chat_type: str,
        chat_id: str,
    ) -> tuple[bool, str | None]:
        raw_message = _message_raw(message)
        message_seq = str(
            message.get("message_seq")
            or message.get("messageSeq")
            or raw_message.get("msgSeq")
            or ""
        ).strip()
        if not message_seq:
            return False, None
        try:
            if chat_type == "group":
                payload = self._client.get_group_msg_history(
                    chat_id,
                    message_seq=message_seq,
                    count=1,
                    reverse_order=True,
                    parse_mult_msg=True,
                )
            else:
                payload = self._client.get_friend_msg_history(
                    chat_id,
                    message_seq=message_seq,
                    count=1,
                    reverse_order=True,
                    parse_mult_msg=True,
                )
        except (NapCatApiError, httpx.HTTPError) as exc:
            known_unavailable = self._known_forward_history_unavailable_reason(exc)
            self._record_forward_history_probe_outcome(
                message,
                has_content=False,
                route="history_retry",
                terminal_reason=known_unavailable,
            )
            return False, known_unavailable

        candidate = self._match_message_by_seq(payload, message_seq, target_message=message)
        if candidate is None:
            self._record_forward_history_probe_outcome(
                message,
                has_content=False,
                route="history_retry",
            )
            return False, None
        onebot_segments = candidate.get("message")
        if not isinstance(onebot_segments, list) or not onebot_segments:
            self._record_forward_history_probe_outcome(
                message,
                has_content=False,
                route="history_retry",
            )
            return False, None
        forward_segments = [
            segment
            for segment in onebot_segments
            if isinstance(segment, dict) and segment.get("type") == "forward"
        ]
        if not forward_segments:
            self._record_forward_history_probe_outcome(
                message,
                has_content=False,
                route="history_retry",
            )
            return False, None
        if not any(
            (segment.get("data") or {}).get("content") for segment in forward_segments
        ):
            self._record_forward_history_probe_outcome(
                message,
                has_content=False,
                route="history_retry",
            )
            return False, None
        message["message"] = onebot_segments
        if candidate.get("raw_message") not in {None, ""}:
            message["raw_message"] = candidate.get("raw_message")
        message["message_format"] = candidate.get("message_format") or "array"
        self._record_forward_history_probe_outcome(
            message,
            has_content=True,
            route="history_retry",
        )
        return True, None

    def _known_forward_history_unavailable_reason(self, exc: Exception) -> str | None:
        if not isinstance(exc, NapCatApiError):
            return None
        message = str(exc).strip().lower()
        if not message:
            return None
        if "旧版客户端" in message:
            return "forward_structure_unavailable_old_client"
        if "unexpected end of file" in message:
            return "forward_structure_unavailable_unexpected_eof"
        if "消息不存在" in message or "找不到相关的聊天记录" in message:
            return "forward_structure_unavailable_history_missing"
        if "消息已过期" in message:
            return "forward_structure_unavailable_history_expired"
        return None

    def _match_message_by_seq(
        self,
        payload: Any,
        message_seq: str,
        *,
        target_message: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        messages = self._extract_messages(payload)
        if not messages:
            return None
        for item in messages:
            if not isinstance(item, dict):
                continue
            raw_message = _message_raw(item)
            item_keys = {
                str(item.get("message_seq") or "").strip(),
                str(item.get("messageSeq") or "").strip(),
                str(item.get("real_seq") or "").strip(),
                str(item.get("realSeq") or "").strip(),
                str(raw_message.get("msgSeq") or "").strip(),
            }
            if message_seq in item_keys:
                return item
        if len(messages) == 1:
            only = messages[0]
            if not isinstance(only, dict):
                return None
            if self._message_identity_matches_target(only, target_message):
                return only
        return None

    def _message_identity_matches_target(
        self,
        candidate: dict[str, Any] | None,
        target_message: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(candidate, dict) or not isinstance(target_message, dict):
            return False
        candidate_ids = self._message_identity_keys(candidate)
        target_ids = self._message_identity_keys(target_message)
        if candidate_ids and target_ids and candidate_ids.intersection(target_ids):
            return True
        return False

    @staticmethod
    def _message_identity_keys(message: dict[str, Any]) -> set[str]:
        raw_message = _message_raw(message)
        keys = {
            str(message.get("message_id") or "").strip(),
            str(message.get("messageId") or "").strip(),
            str(raw_message.get("msgId") or "").strip(),
        }
        keys.discard("")
        return keys

    def _hydrate_fast_history_page_forwards(
        self,
        request: ExportRequest,
        messages: list[dict[str, Any]],
        *,
        before_message_seq: str | None,
        count: int,
        reverse_order: bool,
    ) -> int:
        forward_messages = [
            message
            for message in messages
            if self._message_has_forward_reference(message)
            and not self._message_has_resolved_forward_content(message)
        ]
        forward_message_ids = {
            str(
                message.get("message_id")
                or message.get("messageId")
                or _message_raw(message).get("msgId")
                or ""
            ).strip()
            for message in forward_messages
        }
        forward_message_ids.discard("")
        if not forward_message_ids:
            return 0
        try:
            if request.chat_type == "group":
                payload = self._client.get_group_msg_history(
                    request.chat_id,
                    message_seq=before_message_seq,
                    count=count,
                    reverse_order=reverse_order,
                    parse_mult_msg=True,
                )
            else:
                payload = self._client.get_friend_msg_history(
                    request.chat_id,
                    message_seq=before_message_seq,
                    count=count,
                    reverse_order=reverse_order,
                    parse_mult_msg=True,
                )
        except (NapCatApiError, httpx.HTTPError):
            return 0

        public_forward_map: dict[str, dict[str, Any]] = {}
        for public_message in self._extract_messages(payload):
            for segment in public_message.get("message") or []:
                if not isinstance(segment, dict) or segment.get("type") != "forward":
                    continue
                data = segment.get("data") or {}
                forward_id = str(data.get("id") or data.get("resid") or "").strip()
                if forward_id and data.get("content"):
                    public_forward_map[forward_id] = public_message

        hydrated = 0
        for message in forward_messages:
            raw_message = _message_raw(message)
            message_id = str(
                message.get("message_id")
                or message.get("messageId")
                or raw_message.get("msgId")
                or ""
            ).strip()
            public_message = public_forward_map.get(message_id)
            if public_message is None:
                message_seq = str(
                    message.get("message_seq")
                    or message.get("messageSeq")
                    or raw_message.get("msgSeq")
                    or ""
                ).strip()
                matched_public_message = (
                    self._match_message_by_seq(
                        payload,
                        message_seq,
                        target_message=message,
                    )
                    if message_seq
                    else None
                )
                if matched_public_message is not None:
                    self._record_forward_history_probe_outcome(
                        message,
                        has_content=False,
                        route="bulk_parse_mult",
                    )
                continue
            message["message"] = public_message.get("message") or []
            if public_message.get("raw_message") not in {None, ""}:
                message["raw_message"] = public_message.get("raw_message")
            message["message_format"] = public_message.get("message_format") or "array"
            self._record_forward_history_probe_outcome(
                message,
                has_content=True,
                route="bulk_parse_mult",
            )
            hydrated += 1
        return hydrated

    def _hydrate_sparse_tail_forward_messages(
        self,
        request: ExportRequest,
        forward_messages: list[dict[str, Any]],
    ) -> tuple[int, int]:
        hydrated = 0
        history_calls = 0
        for message in forward_messages:
            history_calls += 1
            hydrated_now, _known_unavailable = self._hydrate_forward_message_via_history(
                message,
                chat_type=request.chat_type,
                chat_id=request.chat_id,
            )
            if hydrated_now:
                hydrated += 1
        return hydrated, history_calls

    def _hydrate_fast_history_tail_forwards_bulk(
        self,
        request: ExportRequest,
        messages: list[dict[str, Any]],
        *,
        page_size: int,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> int:
        if not messages:
            return 0
        hydrated = 0
        anchor: str | None = None
        reverse_order = False
        end = len(messages)
        effective_page_size = max(1, page_size)
        window_index = 0
        while end > 0:
            start = max(0, end - effective_page_size)
            window = messages[start:end]
            if not window:
                break
            window_index += 1
            forward_messages = [
                message for message in window if self._message_has_forward_reference(message)
            ]
            resolved_forward_messages = [
                message
                for message in forward_messages
                if self._message_has_resolved_forward_content(message)
            ]
            unresolved_forward_messages = [
                message
                for message in forward_messages
                if not self._message_has_resolved_forward_content(message)
            ]
            forward_ref_count = len(forward_messages)
            resolved_forward_ref_count = len(resolved_forward_messages)
            unresolved_forward_ref_count = len(unresolved_forward_messages)
            oldest_message = window[0]
            newest_message = window[-1]
            oldest_dt = _message_datetime(oldest_message)
            newest_dt = _message_datetime(newest_message)
            window_started = perf_counter()
            strategy = "bulk_parse_mult_window"
            history_calls = 1 if unresolved_forward_ref_count > 0 else 0
            if self._should_use_sparse_tail_forward_hydrate(
                window_message_count=len(window),
                forward_ref_count=unresolved_forward_ref_count,
            ):
                strategy = "history_retry_sparse_forward"
                hydrated_in_window, history_calls = self._hydrate_sparse_tail_forward_messages(
                    request,
                    unresolved_forward_messages,
                )
            else:
                hydrated_in_window = self._hydrate_fast_history_page_forwards(
                    request,
                    window,
                    before_message_seq=anchor,
                    count=len(window),
                    reverse_order=reverse_order,
                )
            hydrated += hydrated_in_window
            window_elapsed_s = perf_counter() - window_started
            self._emit_progress(
                progress_callback,
                {
                    "phase": "tail_forward_hydrate_window",
                    "status": "done",
                    "window_index": window_index,
                    "window_message_count": len(window),
                    "forward_ref_count": forward_ref_count,
                    "resolved_forward_ref_count": resolved_forward_ref_count,
                    "unresolved_forward_ref_count": unresolved_forward_ref_count,
                    "hydrated_count": hydrated_in_window,
                    "strategy": strategy,
                    "history_calls": history_calls,
                    "before_message_seq": anchor,
                    "reverse_order": reverse_order,
                    "oldest_message_id": oldest_message.get("message_id")
                    or oldest_message.get("messageId")
                    or _message_raw(oldest_message).get("msgId"),
                    "oldest_message_seq": oldest_message.get("message_seq")
                    or oldest_message.get("messageSeq")
                    or _message_raw(oldest_message).get("msgSeq"),
                    "newest_message_id": newest_message.get("message_id")
                    or newest_message.get("messageId")
                    or _message_raw(newest_message).get("msgId"),
                    "newest_message_seq": newest_message.get("message_seq")
                    or newest_message.get("messageSeq")
                    or _message_raw(newest_message).get("msgSeq"),
                    "oldest_timestamp_iso": oldest_message.get("timestamp_iso")
                    or oldest_dt.isoformat(),
                    "newest_timestamp_iso": newest_message.get("timestamp_iso")
                    or newest_dt.isoformat(),
                    "elapsed_s": round(window_elapsed_s, 4),
                    "elapsed_ms": int(round(window_elapsed_s * 1000)),
                },
            )
            oldest_anchor = _history_anchor(window[0])
            if not oldest_anchor:
                break
            anchor = oldest_anchor
            reverse_order = True
            end = start
        return hydrated

    @staticmethod
    def _should_use_sparse_tail_forward_hydrate(
        *,
        window_message_count: int,
        forward_ref_count: int,
    ) -> bool:
        if forward_ref_count <= 0:
            return False
        if window_message_count < SPARSE_TAIL_FORWARD_HYDRATE_MIN_WINDOW_MESSAGES:
            return False
        return forward_ref_count <= SPARSE_TAIL_FORWARD_HYDRATE_MAX_FORWARD_REFS

    @staticmethod
    def _trim_sparse_tail_forward_window(
        window: list[dict[str, Any]],
        forward_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not window or not forward_messages:
            return window
        first_forward = forward_messages[0]
        try:
            first_index = window.index(first_forward)
        except ValueError:
            return window
        trimmed_window = window[first_index:]
        return trimmed_window or window

    def _message_has_forward_reference(self, message: dict[str, Any]) -> bool:
        raw_message = _message_raw(message)
        elements = raw_message.get("elements")
        if not isinstance(elements, list):
            return False
        return any(
            isinstance(element, dict)
            and int(element.get("elementType") or 0) == FORWARD_ELEMENT_TYPE
            for element in elements
        )

    def _message_has_resolved_forward_content(self, message: dict[str, Any]) -> bool:
        onebot_segments = message.get("message")
        if not isinstance(onebot_segments, list):
            return False
        for segment in onebot_segments:
            if not isinstance(segment, dict) or segment.get("type") != "forward":
                continue
            if (segment.get("data") or {}).get("content"):
                return True
        return False

    def _iter_forward_targets(
        self,
        messages: list[dict[str, Any]],
    ):
        for message in messages:
            resolved_forward = self._message_has_resolved_forward_content(message)
            raw_message = _message_raw(message)
            elements = raw_message.get("elements")
            if isinstance(elements, list) and not resolved_forward:
                for element in elements:
                    if not isinstance(element, dict):
                        continue
                    if int(element.get("elementType") or 0) != FORWARD_ELEMENT_TYPE:
                        continue
                    forward = element.get("multiForwardMsgElement") or {}
                    forward_id = str(forward.get("resId") or "").strip()
                    if not forward_id or forward.get("messages"):
                        continue
                    yield {
                        "message": message,
                        "message_seq": message.get("message_seq")
                        or message.get("messageSeq")
                        or raw_message.get("msgSeq"),
                        "message_id": message.get("message_id")
                        or message.get("messageId")
                        or raw_message.get("msgId"),
                        "forward_id": forward_id,
                        "element_id": str(element.get("elementId") or "").strip() or None,
                        "attach": forward,
                        "key": "messages",
                    }

            onebot_segments = message.get("message")
            if isinstance(onebot_segments, list):
                for segment in onebot_segments:
                    if (
                        not isinstance(segment, dict)
                        or segment.get("type") != "forward"
                    ):
                        continue
                    data = segment.get("data") or {}
                    forward_id = str(data.get("id") or data.get("resid") or "").strip()
                    if not forward_id or data.get("content"):
                        continue
                    yield {
                        "message": message,
                        "message_seq": message.get("message_seq")
                        or message.get("messageSeq")
                        or raw_message.get("msgSeq"),
                        "message_id": message.get("message_id")
                        or message.get("messageId")
                        or raw_message.get("msgId"),
                        "forward_id": forward_id,
                        "element_id": str(data.get("element_id") or "").strip() or None,
                        "attach": data,
                        "key": "content",
                    }

    def _fetch_fast_history(
        self,
        request: ExportRequest,
        *,
        before_message_id: str | None,
        count: int,
        reverse_order: bool,
    ) -> Any | None:
        if self._fast_client is None or self._fast_mode == "off":
            return None
        if self._fast_available is False and self._fast_mode != "force":
            return None
        try:
            payload = self._fast_client.get_history(
                request.chat_type,
                request.chat_id,
                message_id=before_message_id,
                count=count,
                reverse_order=reverse_order,
            )
        except NapCatFastHistoryError:
            if self._fast_mode == "force":
                raise
            self._fast_available = False
            return None
        self._fast_available = True
        return payload

    def _fetch_fast_history_tail_bulk(
        self,
        request: ExportRequest,
        *,
        data_count: int,
        page_size: int,
        anchor_message_id: str | None = None,
    ) -> Any | None:
        if self._fast_client is None or self._fast_mode == "off":
            return None
        get_history_tail_bulk = getattr(self._fast_client, "get_history_tail_bulk", None)
        if not callable(get_history_tail_bulk):
            return None
        if self._fast_tail_bulk_available is False and self._fast_mode != "force":
            return None
        try:
            payload = get_history_tail_bulk(
                request.chat_type,
                request.chat_id,
                data_count=data_count,
                page_size=page_size,
                anchor_message_id=anchor_message_id,
            )
        except NapCatFastHistoryError:
            if self._fast_mode == "force":
                raise
            self._fast_tail_bulk_available = False
            return None
        self._fast_available = True
        self._fast_tail_bulk_available = True
        return payload

    def _collect_fast_history_tail_bulk(
        self,
        request: ExportRequest,
        *,
        data_count: int,
        page_size: int,
        progress_callback: HistoryProgressCallback | None,
    ) -> dict[str, Any] | None:
        chunk_limit = self._normalize_requested_bulk_data_count(data_count)
        anchor: str | None = None
        seen_keys: set[str] = set()
        seen_anchors: set[str] = set()
        collected_messages: list[dict[str, Any]] = []
        pages_scanned = 0
        chunk_count = 0
        total_started = perf_counter()
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fast_tail_bulk",
            status="start",
            requested_data_count=data_count,
            page_size=page_size,
            chunk_limit=chunk_limit,
        )

        while len(collected_messages) < data_count:
            remaining = data_count - len(collected_messages)
            chunk_target = min(remaining, chunk_limit)
            chunk_started = perf_counter()
            payload = self._fetch_fast_history_tail_bulk(
                request,
                data_count=chunk_target,
                page_size=page_size,
                anchor_message_id=anchor,
            )
            if payload is None:
                if chunk_count <= 0:
                    self._emit_pipeline_stage(
                        progress_callback,
                        stage="provider.fast_tail_bulk",
                        status="done",
                        elapsed_s=perf_counter() - total_started,
                        requested_data_count=data_count,
                        pages_scanned=pages_scanned,
                        bulk_chunks=chunk_count,
                        exit_reason="unavailable_initial",
                    )
                    return None
                self._emit_progress(
                    progress_callback,
                    {
                        "phase": "tail_bulk_summary",
                        "status": "fallback",
                        "requested_data_count": data_count,
                        "pages_scanned": pages_scanned,
                        "bulk_chunks": chunk_count,
                        "bulk_chunk_limit": chunk_limit,
                        "elapsed_s": round(perf_counter() - total_started, 4),
                        "exit_reason": "bulk_route_unavailable_after_partial",
                    },
                )
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fast_tail_bulk",
                    status="done",
                    elapsed_s=perf_counter() - total_started,
                    requested_data_count=data_count,
                    pages_scanned=pages_scanned,
                    bulk_chunks=chunk_count,
                    exit_reason="partial_fallback",
                )
                return {
                    "messages": collected_messages,
                    "seen_keys": seen_keys,
                    "next_anchor": anchor,
                    "pages_scanned": pages_scanned,
                    "completed": False,
                    "history_source": "napcat_fast_history_bulk",
                    "bulk_duration_s": round(perf_counter() - total_started, 4),
                    "bulk_chunks": chunk_count,
                    "bulk_chunk_limit": chunk_limit,
                    "partial_fallback": True,
                    "page_size": page_size,
                }

            chunk_count += 1
            chunk_duration_s = round(perf_counter() - chunk_started, 4)
            chunk_messages = _sorted_messages(self._extract_messages(payload.get("messages")))
            pages_scanned += int(payload.get("pages_scanned") or 0)
            added = 0
            for message in chunk_messages:
                dedupe_key = _message_key(message)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                collected_messages.append(message)
                added += 1
                if len(collected_messages) >= data_count:
                    break

            oldest_dt = _message_datetime(chunk_messages[0]) if chunk_messages else None
            newest_dt = _message_datetime(chunk_messages[-1]) if chunk_messages else None
            next_anchor = (
                str(payload.get("next_anchor") or "").strip()
                or (_history_anchor(chunk_messages[0]) if chunk_messages else None)
            )
            exhausted = bool(payload.get("exhausted"))
            total_duration_s = round(perf_counter() - total_started, 4)
            self._emit_progress(
                progress_callback,
                {
                    "phase": "history_page_done",
                    "mode": "tail_scan",
                    "history_source": "napcat_fast_history_bulk",
                    "status": "done",
                    "page_duration_s": chunk_duration_s,
                    "page_message_count": len(chunk_messages),
                    "page_size": int(payload.get("page_size") or page_size),
                    "requested_count": chunk_target,
                    "retry_count": 0,
                    "chunk_index": chunk_count,
                    "chunk_added": added,
                    "pages_scanned": pages_scanned,
                    "next_anchor": next_anchor,
                    "oldest_content_at": oldest_dt,
                    "newest_content_at": newest_dt,
                },
            )
            self._emit_progress(
                progress_callback,
                {
                    "phase": "tail_bulk_chunk",
                    "status": "done",
                    "chunk_index": chunk_count,
                    "chunk_target": chunk_target,
                    "chunk_added": added,
                    "chunk_messages": len(chunk_messages),
                    "chunk_duration_s": chunk_duration_s,
                    "total_duration_s": total_duration_s,
                    "pages_scanned": pages_scanned,
                    "next_anchor": next_anchor,
                    "exhausted": exhausted,
                    "requested_data_count": data_count,
                },
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "tail_scan",
                        "pages_scanned": pages_scanned,
                        "matched_messages": len(collected_messages),
                        "requested_data_count": data_count,
                        "oldest_content_at": oldest_dt,
                        "newest_content_at": newest_dt,
                        "anchor": next_anchor,
                        "history_source": "napcat_fast_history_bulk",
                        "page_duration_s": chunk_duration_s,
                        "bulk_duration_s": total_duration_s,
                        "page_size": int(payload.get("page_size") or page_size),
                        "page_message_count": len(chunk_messages),
                        "retry_count": 0,
                        "bulk_chunks": chunk_count,
                        "bulk_chunk_limit": chunk_limit,
                        "bulk_chunk_target": chunk_target,
                    }
                )

            if len(collected_messages) >= data_count or exhausted:
                self._emit_progress(
                    progress_callback,
                    {
                        "phase": "tail_bulk_summary",
                        "status": "done",
                        "requested_data_count": data_count,
                        "pages_scanned": pages_scanned,
                        "bulk_chunks": chunk_count,
                        "bulk_chunk_limit": chunk_limit,
                        "elapsed_s": total_duration_s,
                        "exit_reason": "target_reached" if len(collected_messages) >= data_count else "exhausted",
                    },
                )
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fast_tail_bulk",
                    status="done",
                    elapsed_s=perf_counter() - total_started,
                    requested_data_count=data_count,
                    pages_scanned=pages_scanned,
                    bulk_chunks=chunk_count,
                    exit_reason="target_reached" if len(collected_messages) >= data_count else "exhausted",
                )
                return {
                    "messages": collected_messages,
                    "seen_keys": seen_keys,
                    "next_anchor": next_anchor,
                    "pages_scanned": pages_scanned,
                    "completed": True,
                    "history_source": "napcat_fast_history_bulk",
                    "bulk_duration_s": total_duration_s,
                    "bulk_chunks": chunk_count,
                    "bulk_chunk_limit": chunk_limit,
                    "partial_fallback": False,
                    "page_size": int(payload.get("page_size") or page_size),
                }
            if not next_anchor or next_anchor in seen_anchors or added <= 0:
                remaining = data_count - len(collected_messages)
                bridged = self._try_fast_history_tail_boundary_bridge(
                    request,
                    anchor=next_anchor or anchor,
                    data_count=data_count,
                    remaining=remaining,
                    page_size=page_size,
                    seen_keys=seen_keys,
                    collected_messages=collected_messages,
                    pages_scanned=pages_scanned,
                    progress_callback=progress_callback,
                )
                if bridged is not None:
                    pages_scanned = int(bridged["pages_scanned"])
                    if bridged["completed"]:
                        self._emit_progress(
                            progress_callback,
                            {
                                "phase": "tail_bulk_summary",
                                "status": "done",
                                "requested_data_count": data_count,
                                "pages_scanned": pages_scanned,
                                "bulk_chunks": chunk_count,
                                "bulk_chunk_limit": chunk_limit,
                                "elapsed_s": round(perf_counter() - total_started, 4),
                                "exit_reason": "boundary_bridge_completed",
                            },
                        )
                        self._emit_pipeline_stage(
                            progress_callback,
                            stage="provider.fast_tail_bulk",
                            status="done",
                            elapsed_s=perf_counter() - total_started,
                            requested_data_count=data_count,
                            pages_scanned=pages_scanned,
                            bulk_chunks=chunk_count,
                            exit_reason="boundary_bridge_completed",
                        )
                        return {
                            "messages": collected_messages,
                            "seen_keys": seen_keys,
                            "next_anchor": bridged["next_anchor"],
                            "pages_scanned": pages_scanned,
                            "completed": True,
                            "history_source": _merge_history_source(
                                "napcat_fast_history_bulk",
                                str(bridged["history_source"] or ""),
                            ),
                            "bulk_duration_s": round(perf_counter() - total_started, 4),
                            "bulk_chunks": chunk_count,
                            "bulk_chunk_limit": chunk_limit,
                            "partial_fallback": False,
                            "page_size": int(bridged["page_size"] or page_size),
                        }
                    bridge_next_anchor = str(bridged["next_anchor"] or "").strip() or None
                    if bridge_next_anchor and bridge_next_anchor not in seen_anchors:
                        seen_anchors.add(bridge_next_anchor)
                        anchor = bridge_next_anchor
                        continue
                self._emit_progress(
                    progress_callback,
                    {
                        "phase": "tail_bulk_summary",
                        "status": "fallback",
                        "requested_data_count": data_count,
                        "pages_scanned": pages_scanned,
                        "bulk_chunks": chunk_count,
                        "bulk_chunk_limit": chunk_limit,
                        "elapsed_s": total_duration_s,
                        "exit_reason": "boundary_stall",
                    },
                )
                self._emit_pipeline_stage(
                    progress_callback,
                    stage="provider.fast_tail_bulk",
                    status="done",
                    elapsed_s=perf_counter() - total_started,
                    requested_data_count=data_count,
                    pages_scanned=pages_scanned,
                    bulk_chunks=chunk_count,
                    exit_reason="boundary_stall",
                )
                return {
                    "messages": collected_messages,
                    "seen_keys": seen_keys,
                    "next_anchor": anchor,
                    "pages_scanned": pages_scanned,
                    "completed": False,
                    "history_source": "napcat_fast_history_bulk",
                    "bulk_duration_s": total_duration_s,
                    "bulk_chunks": chunk_count,
                    "bulk_chunk_limit": chunk_limit,
                    "partial_fallback": True,
                    "page_size": int(payload.get("page_size") or page_size),
                }
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        self._emit_progress(
            progress_callback,
            {
                "phase": "tail_bulk_summary",
                "status": "done",
                "requested_data_count": data_count,
                "pages_scanned": pages_scanned,
                "bulk_chunks": chunk_count,
                "bulk_chunk_limit": chunk_limit,
                "elapsed_s": round(perf_counter() - total_started, 4),
                "exit_reason": "loop_completed",
            },
        )
        self._emit_pipeline_stage(
            progress_callback,
            stage="provider.fast_tail_bulk",
            status="done",
            elapsed_s=perf_counter() - total_started,
            requested_data_count=data_count,
            pages_scanned=pages_scanned,
            bulk_chunks=chunk_count,
            exit_reason="loop_completed",
        )
        return {
            "messages": collected_messages,
            "seen_keys": seen_keys,
            "next_anchor": anchor,
            "pages_scanned": pages_scanned,
            "completed": True,
            "history_source": "napcat_fast_history_bulk",
            "bulk_duration_s": round(perf_counter() - total_started, 4),
            "bulk_chunks": chunk_count,
            "bulk_chunk_limit": chunk_limit,
            "partial_fallback": False,
            "page_size": page_size,
        }

    def _try_fast_history_tail_boundary_bridge(
        self,
        request: ExportRequest,
        *,
        anchor: str | None,
        data_count: int,
        remaining: int,
        page_size: int,
        seen_keys: set[str],
        collected_messages: list[dict[str, Any]],
        pages_scanned: int,
        progress_callback: HistoryProgressCallback | None,
    ) -> dict[str, Any] | None:
        if not anchor or remaining <= 0:
            return None
        bridge_count = max(1, min(page_size, remaining))
        started = perf_counter()
        self._emit_progress(
            progress_callback,
            {
                "phase": "tail_boundary_bridge",
                "status": "start",
                "anchor": anchor,
                "remaining": remaining,
                "bridge_count": bridge_count,
                "pages_scanned": pages_scanned,
            },
        )
        snapshot, page_metrics = self._fetch_history_page(
            request,
            before_message_seq=anchor,
            count=bridge_count,
            progress_callback=progress_callback,
            phase="page_retry",
            mode="tail_boundary_bridge",
        )
        page_messages = self._extract_messages(snapshot.messages)
        if not page_messages:
            self._emit_progress(
                progress_callback,
                {
                    "phase": "tail_boundary_bridge",
                    "status": "empty",
                    "anchor": anchor,
                    "remaining": remaining,
                    "bridge_count": bridge_count,
                    "pages_scanned": pages_scanned,
                    "elapsed_s": round(perf_counter() - started, 4),
                },
            )
            return None
        pages_scanned += 1
        oldest_dt = _message_datetime(page_messages[0])
        newest_dt = _message_datetime(page_messages[-1])
        added = 0
        for message in reversed(page_messages):
            if len(collected_messages) >= data_count:
                break
            dedupe_key = _message_key(message)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            collected_messages.append(message)
            added += 1
        next_anchor = _history_anchor(page_messages[0])
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "tail_scan",
                    "mode": "tail_boundary_bridge",
                    "pages_scanned": pages_scanned,
                    "matched_messages": len(collected_messages),
                    "requested_data_count": data_count,
                    "oldest_content_at": oldest_dt,
                    "newest_content_at": newest_dt,
                    "anchor": next_anchor,
                    **page_metrics,
                }
            )
        self._emit_progress(
            progress_callback,
            {
                "phase": "tail_boundary_bridge",
                "status": "done",
                "anchor": anchor,
                "remaining": remaining,
                "bridge_count": bridge_count,
                "pages_scanned": pages_scanned,
                "added": added,
                "next_anchor": next_anchor,
                "elapsed_s": round(perf_counter() - started, 4),
                "history_source": snapshot.metadata.get("source"),
                "page_duration_s": page_metrics.get("page_duration_s"),
            },
        )
        if added <= 0:
            return None
        return {
            "added": added,
            "pages_scanned": pages_scanned,
            "next_anchor": next_anchor,
            "history_source": snapshot.metadata.get("source"),
            "page_size": page_metrics.get("page_size"),
            "completed": len(collected_messages) >= data_count,
        }

    def _adapt_page_size(
        self,
        *,
        base_page_size: int,
        current_page_size: int,
        page_message_count: int,
        page_duration_s: float,
        fast_page_streak: int,
        history_source: str,
        progress_callback: HistoryProgressCallback | None = None,
        mode: str | None = None,
    ) -> tuple[int, int]:
        slow_page_threshold_s = (
            FAST_PLUGIN_SLOW_HISTORY_PAGE_SECONDS
            if history_source == "napcat_fast_history"
            else SLOW_HISTORY_PAGE_SECONDS
        )
        if (
            current_page_size > MIN_HISTORY_PAGE_SIZE
            and page_duration_s >= slow_page_threshold_s
        ):
            new_page_size = max(MIN_HISTORY_PAGE_SIZE, current_page_size // 2)
            self._emit_progress(
                progress_callback,
                {
                    "phase": "page_size_adapt",
                    "mode": mode,
                    "history_source": history_source,
                    "old_page_size": current_page_size,
                    "new_page_size": new_page_size,
                    "page_duration_s": round(page_duration_s, 4),
                    "page_message_count": page_message_count,
                    "fast_page_streak": fast_page_streak,
                    "decision": "shrink",
                },
            )
            return new_page_size, 0

        if (
            current_page_size < base_page_size
            and page_duration_s <= FAST_HISTORY_PAGE_SECONDS
            and page_message_count >= max(1, int(current_page_size * 0.9))
        ):
            fast_page_streak += 1
            if fast_page_streak >= 2:
                new_page_size = min(
                    base_page_size, current_page_size + FAST_HISTORY_RECOVERY_STEP
                )
                self._emit_progress(
                    progress_callback,
                    {
                        "phase": "page_size_adapt",
                        "mode": mode,
                        "history_source": history_source,
                        "old_page_size": current_page_size,
                        "new_page_size": new_page_size,
                        "page_duration_s": round(page_duration_s, 4),
                        "page_message_count": page_message_count,
                        "fast_page_streak": fast_page_streak,
                        "decision": "recover",
                    },
                )
                return new_page_size, 0
            return current_page_size, fast_page_streak

        self._emit_progress(
            progress_callback,
            {
                "phase": "page_size_adapt",
                "mode": mode,
                "history_source": history_source,
                "old_page_size": current_page_size,
                "new_page_size": current_page_size,
                "page_duration_s": round(page_duration_s, 4),
                "page_message_count": page_message_count,
                "fast_page_streak": fast_page_streak,
                "decision": "hold",
            },
        )
        return current_page_size, 0

    def _normalize_requested_page_size(self, page_size: int) -> int:
        normalized = max(MIN_HISTORY_PAGE_SIZE, page_size)
        if self._fast_client is not None and self._fast_mode != "off":
            normalized = min(normalized, FAST_HISTORY_MAX_PAGE_SIZE)
        return normalized

    def _normalize_requested_bulk_data_count(self, data_count: int) -> int:
        return max(1, min(int(data_count), FAST_HISTORY_BULK_SAFE_DATA_COUNT))


def _message_datetime(message: dict[str, Any]) -> datetime:
    timestamp = int(message.get("time") or 0)
    if timestamp <= 0:
        return datetime.fromtimestamp(0, tz=EXPORT_TIMEZONE)
    return datetime.fromtimestamp(timestamp, tz=EXPORT_TIMEZONE)


def _safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _message_raw(message: dict[str, Any]) -> dict[str, Any]:
    raw_message = message.get("rawMessage")
    if isinstance(raw_message, dict):
        return raw_message
    raw_message = message.get("raw_message")
    if isinstance(raw_message, dict):
        return raw_message
    return {}


def _message_sender(message: dict[str, Any]) -> dict[str, Any]:
    return _safe_mapping(message.get("sender"))


def _history_anchor(message: dict[str, Any]) -> str | None:
    raw_message = _message_raw(message)
    value = (
        message.get("anchor_message_id")
        or message.get("message_seq")
        or message.get("message_id")
        or message.get("messageId")
        or raw_message.get("msgId")
    )
    text = str(value or "").strip()
    return text or None


def _message_key(message: dict[str, Any]) -> str:
    raw_message = _message_raw(message)
    sender = _message_sender(message)
    return "|".join(
        [
            str(
                message.get("message_seq")
                or message.get("messageSeq")
                or raw_message.get("msgSeq")
                or ""
            ),
            str(
                message.get("message_id")
                or message.get("messageId")
                or raw_message.get("msgId")
                or ""
            ),
            str(message.get("time") or ""),
            str(
                message.get("user_id")
                or message.get("sender_id")
                or sender.get("uin")
                or raw_message.get("senderUin")
                or ""
            ),
        ]
    )


def _message_sort_key(message: dict[str, Any]) -> str:
    raw_message = _message_raw(message)
    return str(
        message.get("message_seq")
        or message.get("message_id")
        or message.get("messageId")
        or raw_message.get("msgSeq")
        or raw_message.get("msgId")
        or ""
    )


def _sorted_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        messages, key=lambda item: (_message_datetime(item), _message_sort_key(item))
    )


def _merge_history_source(existing: str | None, new: str | None) -> str:
    parts: list[str] = []
    for raw in (existing, new):
        text = str(raw or "").strip()
        if not text:
            continue
        for item in text.split("+"):
            name = item.strip()
            if name and name not in parts:
                parts.append(name)
    return "+".join(parts)
