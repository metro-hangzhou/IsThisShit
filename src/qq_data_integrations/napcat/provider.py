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
        self._known_unavailable_forward_ids: set[str] = set()
        self._known_unavailable_history_keys: set[str] = set()
        self._disable_parse_mult_forward_hydration = False
        self._known_forward_history_failures = 0

    def reset_export_state(self) -> None:
        self._fast_available = None
        self._fast_tail_bulk_available = None
        self._known_unavailable_forward_ids.clear()
        self._known_unavailable_history_keys.clear()
        self._disable_parse_mult_forward_hydration = False
        self._known_forward_history_failures = 0

    def fetch_snapshot(self, request: ExportRequest) -> SourceChatSnapshot:
        return self.fetch_snapshot_before(
            request,
            before_message_seq=None,
            count=request.limit,
            include_forward_details=True,
        )

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
                self._hydrate_fast_history_tail_forwards_bulk(
                    request,
                    selected_messages,
                    page_size=bulk_page_size,
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
                return self._finalize_snapshot(snapshot, progress_callback=progress_callback)

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
            )
            next_anchor = _history_anchor(page_messages[0])
            if not next_anchor or next_anchor in seen_anchors:
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
        return self._finalize_snapshot(snapshot, progress_callback=progress_callback)

    def fetch_snapshot_before(
        self,
        request: ExportRequest,
        *,
        before_message_seq: str | None,
        count: int | None = None,
        include_forward_details: bool = True,
    ) -> SourceChatSnapshot:
        requested_count = count or request.limit or 20
        reverse_order = before_message_seq not in {None, "", "0"}
        payload: Any
        source = "napcat_http"
        fast_payload = self._fetch_fast_history(
            request,
            before_message_id=before_message_seq,
            count=requested_count,
            reverse_order=reverse_order,
        )
        if fast_payload is not None:
            payload = fast_payload
            source = "napcat_fast_history"
        elif request.chat_type == "group":
            payload = self._client.get_group_msg_history(
                request.chat_id,
                message_seq=before_message_seq,
                count=requested_count,
                reverse_order=reverse_order,
            )
        else:
            payload = self._client.get_friend_msg_history(
                request.chat_id,
                message_seq=before_message_seq,
                count=requested_count,
                reverse_order=reverse_order,
            )

        messages = _sorted_messages(self._extract_messages(payload))
        if source == "napcat_fast_history":
            self._hydrate_fast_history_page_forwards(
                request,
                messages,
                before_message_seq=before_message_seq,
                count=requested_count,
                reverse_order=reverse_order,
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
            return self._finalize_snapshot(snapshot)
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

        if need_final and not need_earliest:
            latest_snapshot = self.fetch_snapshot_before(
                request, before_message_seq=None, count=1
            )
            latest_messages = self._extract_messages(latest_snapshot.messages)
            return ChatHistoryBounds(
                final_content_at=_message_datetime(latest_messages[-1])
                if latest_messages
                else None,
            )

        anchor: str | None = None
        earliest_content_at: datetime | None = None
        final_content_at: datetime | None = None
        pages_scanned = 0
        seen_anchors: set[str] = set()
        current_page_size = self._normalize_requested_page_size(page_size)
        effective_base_page_size = current_page_size
        fast_page_streak = 0
        history_source: str | None = None
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
                break
            pages_scanned += 1
            history_source = str(
                page_metrics.get("history_source") or history_source or ""
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
            )
            next_anchor = _history_anchor(messages[0])
            if not need_earliest or not next_anchor or next_anchor in seen_anchors:
                break
            seen_anchors.add(next_anchor)
            anchor = next_anchor

        return ChatHistoryBounds(
            earliest_content_at=earliest_content_at,
            final_content_at=final_content_at,
        )

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
                break
            pages_scanned += 1
            history_source = str(
                page_metrics.get("history_source") or history_source or ""
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
            )

            next_anchor = _history_anchor(page_messages[0])
            if (
                oldest_dt <= lower_bound
                or newest_dt < lower_bound
                or not next_anchor
                or next_anchor in seen_anchors
            ):
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
        return self._finalize_snapshot(snapshot, progress_callback=progress_callback)

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
                break
            pages_scanned += 1
            history_source = str(
                page_metrics.get("history_source") or history_source or ""
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
            )
            next_anchor = _history_anchor(page_messages[0])
            if (
                newest_dt < lower_bound
                or not next_anchor
                or next_anchor in seen_anchors
            ):
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
        return self._finalize_snapshot(snapshot, progress_callback=progress_callback)

    def fetch_full_snapshot(
        self,
        request: ExportRequest,
        *,
        page_size: int = 100,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> SourceChatSnapshot:
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
                break
            pages_scanned += 1
            history_source = str(
                page_metrics.get("history_source") or history_source or ""
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
            )
            next_anchor = _history_anchor(page_messages[0])
            if not next_anchor or next_anchor in seen_anchors:
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
        return self._finalize_snapshot(snapshot, progress_callback=progress_callback)

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
                requested_count = next_count
                continue

            page_duration_s = perf_counter() - started
            page_messages = self._extract_messages(snapshot.messages)
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
        source = str(snapshot.metadata.get("source") or "").strip()
        enriched_count, structure_unavailable_count = self._enrich_forward_details(
            snapshot.messages,
            chat_type=snapshot.chat_type,
            chat_id=snapshot.chat_id,
            skip_history_retry=source.startswith("napcat_fast_history"),
            progress_callback=progress_callback,
        )
        if enriched_count <= 0 and structure_unavailable_count <= 0:
            return snapshot
        metadata = dict(snapshot.metadata)
        if enriched_count > 0:
            metadata["forward_detail_count"] = enriched_count
        if structure_unavailable_count > 0:
            metadata["forward_structure_unavailable_count"] = structure_unavailable_count
        return snapshot.model_copy(update={"metadata": metadata})

    def _enrich_forward_details(
        self,
        messages: list[dict[str, Any]],
        *,
        chat_type: str,
        chat_id: str,
        skip_history_retry: bool = False,
        progress_callback: HistoryProgressCallback | None = None,
    ) -> tuple[int, int]:
        cache: dict[str, list[dict[str, Any]] | None] = {}
        parse_mult_cache: dict[str, bool] = {}
        skip_forward_msg_fallback = False
        history_retry_known_failures = 0
        structure_unavailable = 0
        already_resolved = sum(
            1
            for message in messages
            if self._message_has_resolved_forward_content(message)
        )
        targets = list(self._iter_forward_targets(messages))
        total_targets = already_resolved + len(targets)
        if total_targets <= 0:
            return 0, 0

        processed = already_resolved
        enriched = already_resolved
        for target in targets:
            processed += 1
            message_key = str(
                target.get("message_seq") or target.get("message_id") or ""
            )
            if (
                not skip_history_retry
                and not self._disable_parse_mult_forward_hydration
                and message_key
                and message_key not in parse_mult_cache
            ):
                if message_key in self._known_unavailable_history_keys:
                    parse_mult_cache[message_key] = False
                    if self._mark_forward_target_unavailable(
                        target,
                        reason="forward_structure_unavailable_via_history",
                    ):
                        structure_unavailable += 1
                    history_retry_known_failures += 1
                    if history_retry_known_failures >= 3:
                        skip_history_retry = True
                    self._known_forward_history_failures += 1
                    if self._known_forward_history_failures >= 3:
                        self._disable_parse_mult_forward_hydration = True
                else:
                    hydrated_via_history, known_history_unavailable = self._hydrate_forward_message_via_history(
                        target["message"],
                        chat_type=chat_type,
                        chat_id=chat_id,
                    )
                    parse_mult_cache[message_key] = hydrated_via_history
                    if known_history_unavailable:
                        self._known_unavailable_history_keys.add(message_key)
                        if self._mark_forward_target_unavailable(
                            target,
                            reason="forward_structure_unavailable_via_history",
                        ):
                            structure_unavailable += 1
                        history_retry_known_failures += 1
                        self._known_forward_history_failures += 1
                        if history_retry_known_failures >= 3:
                            skip_history_retry = True
                        if self._known_forward_history_failures >= 3:
                            self._disable_parse_mult_forward_hydration = True
                    elif hydrated_via_history:
                        self._known_forward_history_failures = 0
                if parse_mult_cache[message_key]:
                    enriched += 1
            if parse_mult_cache.get(message_key):
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

            forward_id = target["forward_id"]
            if forward_id in self._known_unavailable_forward_ids:
                cache[forward_id] = None
                recovered_via_history = False
                if message_key and not self._disable_parse_mult_forward_hydration:
                    hydrated_via_history, known_history_unavailable = self._hydrate_forward_message_via_history(
                        target["message"],
                        chat_type=chat_type,
                        chat_id=chat_id,
                    )
                    parse_mult_cache[message_key] = hydrated_via_history
                    if hydrated_via_history:
                        enriched += 1
                        cache[forward_id] = []
                        recovered_via_history = True
                    elif known_history_unavailable and self._mark_forward_target_unavailable(
                        target,
                        reason="forward_structure_unavailable_via_history",
                    ):
                        structure_unavailable += 1
                elif self._mark_forward_target_unavailable(
                    target,
                    reason="forward_structure_unavailable_via_get_forward_msg",
                ):
                    structure_unavailable += 1
                if not recovered_via_history:
                    skip_forward_msg_fallback = True
            if skip_forward_msg_fallback and forward_id not in cache:
                cache[forward_id] = None
            if forward_id not in cache:
                try:
                    response = self._client.get_forward_msg(forward_id)
                except (NapCatApiError, httpx.HTTPError) as exc:
                    cache[forward_id] = None
                    if self._is_known_forward_detail_unavailable(exc):
                        self._known_unavailable_forward_ids.add(forward_id)
                        recovered_via_history = False
                        if (
                            message_key
                            and not self._disable_parse_mult_forward_hydration
                        ):
                            hydrated_via_history, known_history_unavailable = self._hydrate_forward_message_via_history(
                                target["message"],
                                chat_type=chat_type,
                                chat_id=chat_id,
                            )
                            parse_mult_cache[message_key] = hydrated_via_history
                            if hydrated_via_history:
                                enriched += 1
                                cache[forward_id] = []
                                recovered_via_history = True
                            elif known_history_unavailable and self._mark_forward_target_unavailable(
                                target,
                                reason="forward_structure_unavailable_via_history",
                            ):
                                structure_unavailable += 1
                        elif self._mark_forward_target_unavailable(
                            target,
                            reason="forward_structure_unavailable_via_get_forward_msg",
                        ):
                            structure_unavailable += 1
                        if not recovered_via_history:
                            skip_forward_msg_fallback = True
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

    def _is_known_forward_detail_unavailable(self, exc: Exception) -> bool:
        if not isinstance(exc, NapCatApiError):
            return False
        message = str(exc).strip().lower()
        if not message:
            return False
        needles = (
            "找不到相关的聊天记录",
            "protocolfallbacklogic",
            "消息已过期",
            "内层消息",
            "unexpected end of file",
        )
        return any(needle in message for needle in needles)

    def _hydrate_forward_message_via_history(
        self,
        message: dict[str, Any],
        *,
        chat_type: str,
        chat_id: str,
    ) -> tuple[bool, bool]:
        raw_message = _message_raw(message)
        message_seq = str(
            message.get("message_seq")
            or message.get("messageSeq")
            or raw_message.get("msgSeq")
            or ""
        ).strip()
        if not message_seq:
            return False, False
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
            return False, self._is_known_forward_history_unavailable(exc)

        candidate = self._match_message_by_seq(payload, message_seq)
        if candidate is None:
            return False, False
        onebot_segments = candidate.get("message")
        if not isinstance(onebot_segments, list) or not onebot_segments:
            return False, False
        forward_segments = [
            segment
            for segment in onebot_segments
            if isinstance(segment, dict) and segment.get("type") == "forward"
        ]
        if not forward_segments:
            return False, False
        if not any(
            (segment.get("data") or {}).get("content") for segment in forward_segments
        ):
            return False, False
        message["message"] = onebot_segments
        if candidate.get("raw_message") not in {None, ""}:
            message["raw_message"] = candidate.get("raw_message")
        message["message_format"] = candidate.get("message_format") or "array"
        return True, False

    def _is_known_forward_history_unavailable(self, exc: Exception) -> bool:
        if not isinstance(exc, NapCatApiError):
            return False
        message = str(exc).strip().lower()
        if not message:
            return False
        needles = (
            "消息不存在",
            "消息已过期",
            "旧版客户端",
            "unexpected end of file",
            "找不到相关的聊天记录",
        )
        return any(needle in message for needle in needles)

    def _match_message_by_seq(
        self,
        payload: Any,
        message_seq: str,
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
            return messages[0]
        return None

    def _hydrate_fast_history_page_forwards(
        self,
        request: ExportRequest,
        messages: list[dict[str, Any]],
        *,
        before_message_seq: str | None,
        count: int,
        reverse_order: bool,
    ) -> int:
        if self._disable_parse_mult_forward_hydration:
            return 0
        forward_message_ids = {
            str(
                message.get("message_id")
                or message.get("messageId")
                or _message_raw(message).get("msgId")
                or ""
            ).strip()
            for message in messages
            if self._message_has_forward_reference(message)
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
        for message in messages:
            raw_message = _message_raw(message)
            message_id = str(
                message.get("message_id")
                or message.get("messageId")
                or raw_message.get("msgId")
                or ""
            ).strip()
            public_message = public_forward_map.get(message_id)
            if public_message is None:
                continue
            message["message"] = public_message.get("message") or []
            if public_message.get("raw_message") not in {None, ""}:
                message["raw_message"] = public_message.get("raw_message")
            message["message_format"] = public_message.get("message_format") or "array"
            hydrated += 1
        return hydrated

    def _hydrate_fast_history_tail_forwards_bulk(
        self,
        request: ExportRequest,
        messages: list[dict[str, Any]],
        *,
        page_size: int,
    ) -> int:
        if not messages:
            return 0
        hydrated = 0
        anchor: str | None = None
        reverse_order = False
        end = len(messages)
        effective_page_size = max(1, page_size)
        while end > 0:
            start = max(0, end - effective_page_size)
            window = messages[start:end]
            if not window:
                break
            hydrated += self._hydrate_fast_history_page_forwards(
                request,
                window,
                before_message_seq=anchor,
                count=len(window),
                reverse_order=reverse_order,
            )
            oldest_anchor = _history_anchor(window[0])
            if not oldest_anchor:
                break
            anchor = oldest_anchor
            reverse_order = True
            end = start
        return hydrated

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
                    return None
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
                    anchor=anchor,
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
            return None
        pages_scanned += 1
        oldest_dt = _message_datetime(page_messages[0])
        newest_dt = _message_datetime(page_messages[-1])
        added = 0
        for message in reversed(page_messages):
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
            return max(MIN_HISTORY_PAGE_SIZE, current_page_size // 2), 0

        if (
            current_page_size < base_page_size
            and page_duration_s <= FAST_HISTORY_PAGE_SECONDS
            and page_message_count >= max(1, int(current_page_size * 0.9))
        ):
            fast_page_streak += 1
            if fast_page_streak >= 2:
                return min(
                    base_page_size, current_page_size + FAST_HISTORY_RECOVERY_STEP
                ), 0
            return current_page_size, fast_page_streak

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
    left = str(existing or "").strip()
    right = str(new or "").strip()
    if not left:
        return right
    if not right or right == left:
        return left
    return f"{left}+{right}"
