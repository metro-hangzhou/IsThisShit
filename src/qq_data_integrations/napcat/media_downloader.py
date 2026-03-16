from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath
from time import monotonic
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .fast_history_client import (
    NapCatFastHistoryClient,
    NapCatFastHistoryError,
    NapCatFastHistoryTimeoutError,
    NapCatFastHistoryUnavailable,
)
from .http_client import NapCatApiError, NapCatApiTimeoutError, NapCatHttpClient


class NapCatMediaDownloader:
    OLD_CONTEXT_BUCKET_MIN_AGE_DAYS = 120
    OLD_CONTEXT_BUCKET_FAILURE_LIMIT = 5
    SHARED_MISS_CACHE_MIN_AGE_DAYS = 30
    PREFETCH_BATCH_SIZE = 200
    FORWARD_TARGET_DOWNLOAD_TIMEOUT_MS = 20_000
    DIRECT_FILE_ID_TIMEOUT_S = 12.0
    PUBLIC_TOKEN_ACTION_TIMEOUT_S = 12.0
    CONTEXT_ROUTE_TIMEOUT_S = 12.0
    FORWARD_CONTEXT_TIMEOUT_S = 12.0
    FORWARD_TARGET_HTTP_TIMEOUT_S = 25.0
    SLOW_REMOTE_SUBSTEP_WARN_S = 3.0

    def __init__(
        self,
        client: NapCatHttpClient,
        *,
        fast_client: NapCatFastHistoryClient | None = None,
        remote_cache_dir: Path | None = None,
        remote_base_url: str | None = None,
        use_system_proxy: bool = False,
        remote_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = client
        self._fast_client = fast_client
        self._logger = logging.getLogger(__name__)
        self._fast_context_route_disabled = False
        self._old_context_failure_buckets: dict[tuple[str, str], int] = {}
        self._old_context_skip_logged: set[tuple[str, str]] = set()
        self._old_context_expired_buckets: set[tuple[str, str]] = set()
        self._remote_cache_dir = remote_cache_dir
        self._prefetched_media: dict[tuple[Any, ...], tuple[Path | None, str | None]] = {}
        self._prefetched_media_payloads: dict[tuple[Any, ...], dict[str, Any] | None] = {}
        self._prefetched_forward_media: dict[tuple[Any, ...], tuple[Path | None, str | None]] = {}
        self._prefetched_forward_media_payloads: dict[tuple[Any, ...], dict[str, Any] | None] = {}
        self._shared_media_outcomes: dict[tuple[Any, ...], tuple[Path | None, str | None]] = {}
        self._remote_base_url = (
            remote_base_url
            or getattr(client, "_base_url", None)
            or getattr(fast_client, "_base_url", None)
        )
        self._remote_client = httpx.Client(
            timeout=30.0,
            transport=remote_transport,
            trust_env=use_system_proxy,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._remote_client.close()

    def cleanup_remote_cache(self) -> dict[str, Any]:
        self._reset_transient_export_state()
        cache_root = self._remote_cache_dir
        stats: dict[str, Any] = {
            "cache_root": str(cache_root) if cache_root is not None else None,
            "removed_files": 0,
            "removed_dirs": 0,
            "freed_bytes": 0,
            "cleared_memory_state": True,
            "cache_cleared": False,
        }
        if cache_root is None:
            stats["skipped_reason"] = "cache_disabled"
            return stats
        if not cache_root.exists():
            stats["skipped_reason"] = "cache_missing"
            return stats

        for path in cache_root.rglob("*"):
            try:
                if path.is_file():
                    stats["removed_files"] += 1
                    stats["freed_bytes"] += path.stat().st_size
                elif path.is_dir():
                    stats["removed_dirs"] += 1
            except OSError:
                continue

        try:
            shutil.rmtree(cache_root)
            cache_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            stats["cleanup_error"] = str(exc)
            self._logger.warning(
                "media_download_cache_cleanup_failed cache_root=%s detail=%s",
                cache_root,
                exc,
            )
            return stats

        stats["cache_cleared"] = True
        return stats

    def _reset_transient_export_state(self) -> None:
        self._prefetched_media.clear()
        self._prefetched_media_payloads.clear()
        self._prefetched_forward_media.clear()
        self._prefetched_forward_media_payloads.clear()
        self._shared_media_outcomes.clear()
        self._old_context_failure_buckets.clear()
        self._old_context_skip_logged.clear()
        self._old_context_expired_buckets.clear()

    def prepare_for_export(
        self,
        requests: list[dict[str, Any]],
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if self._fast_client is None or not requests:
            return
        batch_items: list[tuple[dict[str, Any], dict[str, Any]]] = []
        seen: set[tuple[Any, ...]] = set()
        for request in requests:
            hint = self._request_hint(request)
            if not self._has_context_hint(hint):
                continue
            if self._has_forward_parent_hint(hint):
                continue
            old_bucket = self._old_context_bucket(
                str(request.get("asset_type") or "").strip(),
                request,
            )
            stale_local = self._resolve_from_stale_local_neighbors(request)
            if stale_local != (None, None):
                key = self._request_key(request)
                self._prefetched_media[key] = stale_local
                self._prefetched_media_payloads[key] = None
                self._remember_shared_outcome(self._shared_request_key(request), request, stale_local)
                continue
            if self._should_skip_old_bucket(old_bucket):
                continue
            key = self._request_key(request)
            if key in self._prefetched_media or key in seen:
                continue
            seen.add(key)
            item = {
                "message_id_raw": str(hint["message_id_raw"]),
                "element_id": str(hint["element_id"]),
                "peer_uid": str(hint["peer_uid"]),
                "chat_type_raw": int(hint["chat_type_raw"]),
                "asset_type": str(request.get("asset_type") or "").strip() or None,
                "asset_role": str(request.get("asset_role") or "").strip() or None,
            }
            batch_items.append((request, {k: v for k, v in item.items() if v not in {None, ""}}))
        if not batch_items:
            return
        batch_size = max(1, int(self.PREFETCH_BATCH_SIZE))
        chunk_count = (len(batch_items) + batch_size - 1) // batch_size
        for chunk_index, start in enumerate(range(0, len(batch_items), batch_size), start=1):
            chunk = batch_items[start : start + batch_size]
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "prefetch_media_chunk",
                        "stage": "start",
                        "chunk_index": chunk_index,
                        "chunk_count": chunk_count,
                        "request_count": len(chunk),
                        "request_offset": start,
                    }
                )
            try:
                payload = self._fast_client.hydrate_media_batch([item for _request, item in chunk])
            except NapCatFastHistoryUnavailable as exc:
                self._fast_context_route_disabled = True
                self._logger.info(
                    "fast_context_hydration_unavailable during batch prefetch; disabling /hydrate-media for this process. detail=%s",
                    exc,
                )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "phase": "prefetch_media_chunk",
                            "stage": "error",
                            "chunk_index": chunk_index,
                            "chunk_count": chunk_count,
                            "request_count": len(chunk),
                            "request_offset": start,
                            "error": str(exc),
                            "reason": "route_unavailable",
                        }
                    )
                return
            except Exception as exc:
                if progress_callback is not None:
                    progress_callback(
                        {
                            "phase": "prefetch_media_chunk",
                            "stage": "error",
                            "chunk_index": chunk_index,
                            "chunk_count": chunk_count,
                            "request_count": len(chunk),
                            "request_offset": start,
                            "error": str(exc),
                            "reason": "chunk_failed",
                        }
                    )
                continue
            items = payload.get("items") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                if progress_callback is not None:
                    progress_callback(
                        {
                            "phase": "prefetch_media_chunk",
                            "stage": "error",
                            "chunk_index": chunk_index,
                            "chunk_count": chunk_count,
                            "request_count": len(chunk),
                            "request_offset": start,
                            "reason": "invalid_response",
                        }
                    )
                continue
            hydrated_count = 0
            for idx, (request, batch_request) in enumerate(chunk):
                request_key = self._request_key(request)
                batch_key = self._batch_request_key(batch_request)
                result = items[idx] if idx < len(items) else None
                if not isinstance(result, dict):
                    for key in {request_key, batch_key}:
                        self._prefetched_media[key] = (None, None)
                        self._prefetched_media_payloads[key] = None
                    continue
                if result.get("ok") is False:
                    for key in {request_key, batch_key}:
                        self._prefetched_media[key] = (None, None)
                        self._prefetched_media_payloads[key] = None
                    continue
                data = result.get("data") if isinstance(result.get("data"), dict) else result
                resolved, resolver = self._resolve_from_fast_payload(data)
                for key in {request_key, batch_key}:
                    self._prefetched_media[key] = (resolved, resolver)
                    self._prefetched_media_payloads[key] = data if isinstance(data, dict) else None
                hydrated_count += 1
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "prefetch_media_chunk",
                        "stage": "done",
                        "chunk_index": chunk_index,
                        "chunk_count": chunk_count,
                        "request_count": len(chunk),
                        "request_offset": start,
                        "hydrated_count": hydrated_count,
                    }
                )

    def resolve_for_export(
        self,
        request: dict[str, Any],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None]:
        hint = self._request_hint(request)
        asset_type = str(request.get("asset_type") or "").strip()
        asset_role = str(request.get("asset_role") or "").strip() or None
        file_name = str(request.get("file_name") or "").strip() or None
        shared_key = self._shared_request_key(request)
        old_bucket = self._old_context_bucket(asset_type, request)
        if shared_key is not None:
            shared = self._shared_media_outcomes.get(shared_key)
            if shared is not None:
                return shared
        stale_local_fallback = self._resolve_from_stale_local_neighbors(request)
        if stale_local_fallback != (None, None):
            return self._remember_shared_outcome(shared_key, request, stale_local_fallback)
        hinted_local = self._resolve_from_hint_local_path(hint)
        if hinted_local != (None, None):
            return self._remember_shared_outcome(shared_key, request, hinted_local)
        key = self._request_key(request)
        prefetched = self._prefetched_media.get(key)
        if prefetched is not None:
            payload = self._prefetched_media_payloads.get(key)
            if prefetched != (None, None):
                self._note_old_bucket_success(old_bucket)
                return self._remember_shared_outcome(shared_key, request, prefetched)
            if isinstance(payload, dict):
                fast_resolved = self._resolve_from_fast_payload(payload)
                if fast_resolved != (None, None):
                    self._note_old_bucket_success(old_bucket)
                    return self._remember_shared_outcome(shared_key, request, fast_resolved)
                if self._should_skip_old_bucket(old_bucket):
                    return self._remember_shared_outcome(
                        shared_key,
                        request,
                        (None, self._missing_bucket_resolver(old_bucket)),
                    )
                public_resolved = self._resolve_from_public_token(
                    payload,
                    old_bucket=old_bucket,
                    expired_candidate=self._should_share_missing_outcome(request),
                    request=request,
                    trace_callback=trace_callback,
                )
                if public_resolved not in {None, (None, None)}:
                    resolved_path, resolver = public_resolved
                    if resolved_path is not None:
                        self._note_old_bucket_success(old_bucket)
                    elif resolver == "qq_expired_after_napcat":
                        self._note_old_bucket_expired_like(old_bucket)
                    return self._remember_shared_outcome(shared_key, request, public_resolved)
                classified_missing = self._classify_missing_from_payload(
                    payload,
                    old_bucket=old_bucket,
                    expired_candidate=self._should_share_missing_outcome(request),
                )
                if classified_missing is not None:
                    self._note_old_bucket_expired_like(old_bucket)
                    return self._remember_shared_outcome(shared_key, request, (None, classified_missing))
                fresh_retry = self._resolve_via_fresh_public_retry(
                    request,
                    trace_callback=trace_callback,
                )
                if fresh_retry not in {None, (None, None)}:
                    resolved_path, resolver = fresh_retry
                    if resolved_path is not None:
                        self._note_old_bucket_success(old_bucket)
                    elif resolver == "qq_expired_after_napcat":
                        self._note_old_bucket_expired_like(old_bucket)
                    return self._remember_shared_outcome(shared_key, request, fresh_retry)
                self._note_old_bucket_failure(old_bucket)
            if asset_type == "sticker":
                sticker_remote = self._resolve_from_sticker_remote_url(
                    hint,
                    asset_role=asset_role,
                    file_name=file_name,
                )
                if sticker_remote != (None, None):
                    return self._remember_shared_outcome(shared_key, request, sticker_remote)
            return self._remember_shared_outcome(shared_key, request, prefetched)
        if self._has_forward_parent_hint(hint):
            request_forward_url = self._resolve_from_forward_remote_url(
                {
                    "asset_type": asset_type,
                    "file_name": file_name,
                    "remote_url": hint.get("remote_url"),
                    "url": hint.get("url"),
                }
            )
            if request_forward_url != (None, None):
                return self._remember_shared_outcome(shared_key, request, request_forward_url)
            if asset_type == "image":
                classified_forward_missing = self._classify_forward_missing(request)
                if classified_forward_missing is not None:
                    return self._remember_shared_outcome(shared_key, request, (None, classified_forward_missing))
            direct_forward_file_id = None
            if asset_type == "file":
                direct_forward_file_id = self._resolve_via_direct_file_id(
                    request,
                    trace_callback=trace_callback,
                )
                if direct_forward_file_id not in {None, (None, None)}:
                    return self._remember_shared_outcome(shared_key, request, direct_forward_file_id)
            passive_forward_resolved = self._download_via_forward_context(
                request,
                materialize=False,
                trace_callback=trace_callback,
            )
            if passive_forward_resolved not in {None, (None, None)}:
                return self._remember_shared_outcome(shared_key, request, passive_forward_resolved)
            forward_payload = self._prefetched_forward_media_payloads.get(key)
            if isinstance(forward_payload, dict):
                public_resolved = self._resolve_from_public_token(
                    forward_payload,
                    request=request,
                    trace_callback=trace_callback,
                )
                if public_resolved not in {None, (None, None)}:
                    return self._remember_shared_outcome(shared_key, request, public_resolved)
            if asset_type in {"video", "file"}:
                targeted_forward_download = self._download_via_forward_context(
                    request,
                    materialize=True,
                    trace_callback=trace_callback,
                )
                if targeted_forward_download not in {None, (None, None)}:
                    return self._remember_shared_outcome(shared_key, request, targeted_forward_download)
            if asset_type != "file":
                direct_forward_file_id = self._resolve_via_direct_file_id(
                    request,
                    trace_callback=trace_callback,
                )
                if direct_forward_file_id not in {None, (None, None)}:
                    return self._remember_shared_outcome(shared_key, request, direct_forward_file_id)
        context_resolved = None
        if not self._has_forward_parent_hint(hint):
            context_resolved = self._resolve_via_context_only(
                request,
                trace_callback=trace_callback,
            )
        if context_resolved not in {None, (None, None)}:
            return self._remember_shared_outcome(shared_key, request, context_resolved)
        direct_file_id_resolved = None
        if not self._has_forward_parent_hint(hint):
            direct_file_id_resolved = self._resolve_via_direct_file_id(
                request,
                trace_callback=trace_callback,
            )
        if direct_file_id_resolved not in {None, (None, None)}:
            return self._remember_shared_outcome(shared_key, request, direct_file_id_resolved)
        if asset_type == "image" and not self._has_forward_parent_hint(hint):
            fresh_public_retry = self._resolve_via_fresh_public_retry(
                request,
                trace_callback=trace_callback,
            )
            if fresh_public_retry not in {None, (None, None)}:
                resolved_path, resolver = fresh_public_retry
                if resolved_path is not None:
                    self._note_old_bucket_success(old_bucket)
                elif resolver == "qq_expired_after_napcat":
                    self._note_old_bucket_expired_like(old_bucket)
                return self._remember_shared_outcome(shared_key, request, fresh_public_retry)
        if asset_type == "sticker":
            sticker_remote = self._resolve_from_sticker_remote_url(
                hint,
                asset_role=asset_role,
                file_name=file_name,
            )
            if sticker_remote != (None, None):
                return self._remember_shared_outcome(shared_key, request, sticker_remote)
        return self._remember_shared_outcome(
            shared_key,
            request,
            context_resolved if context_resolved is not None else (None, None),
        )

    def download_for_export(self, request: dict[str, Any]) -> Path | None:
        asset_type = str(request.get("asset_type") or "").strip()
        asset_role = str(request.get("asset_role") or "").strip() or None
        file_name = str(request.get("file_name") or "").strip()
        hint = request.get("download_hint")
        if not isinstance(hint, dict):
            hint = {}
        file_id = str(hint.get("file_id") or "").strip()

        if asset_type not in {"image", "file", "speech", "video", "sticker"}:
            return None
        if not file_id and not file_name:
            if not self._has_context_hint(hint):
                return None

        if asset_type == "sticker":
            result = self._download_remote_sticker(hint, asset_role=asset_role, file_name=file_name or None)
            if result is None:
                return None
            path = Path(result)
            if not path.exists() or not path.is_file():
                return None
            return path.resolve()

        attempted_context_hydration = False
        old_bucket = self._old_context_bucket(asset_type, request)
        skip_old_context = (
            old_bucket is not None
            and self._old_context_failure_buckets.get(old_bucket, 0)
            >= self.OLD_CONTEXT_BUCKET_FAILURE_LIMIT
        )
        if skip_old_context:
            attempted_context_hydration = True
            result = None
            if old_bucket not in self._old_context_skip_logged:
                self._old_context_skip_logged.add(old_bucket)
                self._logger.info(
                    "skip_context_hydration_for_old_assets bucket=%s failures=%s",
                    "/".join(old_bucket),
                    self._old_context_failure_buckets.get(old_bucket, 0),
                )
        else:
            context_payload = self._download_via_context(hint, asset_type=asset_type, asset_role=asset_role)
            if context_payload is not None:
                public_resolved = self._resolve_from_public_token(context_payload)
                context_resolved, _context_resolver = public_resolved or self._resolve_from_fast_payload(context_payload)
                result = str(context_resolved) if context_resolved is not None else None
                attempted_context_hydration = True
                if old_bucket is not None:
                    self._old_context_failure_buckets.pop(old_bucket, None)
                    self._old_context_skip_logged.discard(old_bucket)
            else:
                result = None
                attempted_context_hydration = self._has_context_hint(hint)
                if attempted_context_hydration and old_bucket is not None:
                    self._old_context_failure_buckets[old_bucket] = self._old_context_failure_buckets.get(old_bucket, 0) + 1

        if result is None and not attempted_context_hydration:
            result = self._download(asset_type, file_id=file_id or None, file_name=file_name or None)
        if result is None:
            result = self._download_remote_media(
                asset_type=asset_type,
                file_name=file_name or None,
                hint=hint,
            )
        if result is None:
            return None
        path = Path(result)
        if not path.exists() or not path.is_file():
            return None
        return path.resolve()

    def resolve_via_context_route(
        self,
        request: dict[str, Any],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None]:
        payload = self._context_payload_for_request(request)
        if payload is None:
            return None, None
        return self._resolve_from_fast_payload(payload)

    def resolve_via_public_token_route(
        self,
        request: dict[str, Any],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None]:
        payload = self._context_payload_for_request(request)
        if payload is None:
            return None, None
        resolved = self._resolve_from_public_token(
            payload,
            old_bucket=self._old_context_bucket(str(request.get("asset_type") or "").strip(), request),
            request=request,
            trace_callback=trace_callback,
        )
        if resolved in {None, (None, None)}:
            return None, None
        return resolved

    def _emit_asset_substep_trace(
        self,
        trace_callback: Callable[[dict[str, Any]], None] | None,
        request: dict[str, Any],
        *,
        stage: str,
        substep: str,
        timeout_s: float | None = None,
        status: str | None = None,
        elapsed_s: float | None = None,
        detail: str | None = None,
    ) -> None:
        if trace_callback is None:
            return
        hint = self._request_hint(request)
        forward_parent = hint.get("_forward_parent") if isinstance(hint.get("_forward_parent"), dict) else {}
        payload: dict[str, Any] = {
            "phase": "materialize_asset_substep",
            "stage": stage,
            "substep": substep,
            "asset_type": str(request.get("asset_type") or "").strip(),
            "asset_role": str(request.get("asset_role") or "").strip() or None,
            "file_name": str(request.get("file_name") or "").strip() or None,
            "message_id_raw": hint.get("message_id_raw"),
            "element_id": hint.get("element_id"),
            "hint_file_id": hint.get("file_id"),
            "hint_url": hint.get("url"),
            "forward_parent_message_id_raw": forward_parent.get("message_id_raw"),
            "forward_parent_element_id": forward_parent.get("element_id"),
        }
        if timeout_s is not None:
            payload["timeout_s"] = timeout_s
            payload["timeout_ms"] = int(round(timeout_s * 1000))
        if status:
            payload["status"] = status
        if elapsed_s is not None:
            payload["elapsed_s"] = round(elapsed_s, 4)
            payload["elapsed_ms"] = int(round(elapsed_s * 1000))
        if detail:
            payload["detail"] = detail
        trace_callback(payload)

    def _log_remote_substep_outcome(
        self,
        *,
        request: dict[str, Any],
        substep: str,
        status: str,
        timeout_s: float | None = None,
        elapsed_s: float | None = None,
        detail: str | None = None,
    ) -> None:
        asset_type = str(request.get("asset_type") or "").strip()
        file_name = str(request.get("file_name") or "").strip() or "-"
        hint = self._request_hint(request)
        forward_parent = hint.get("_forward_parent") if isinstance(hint.get("_forward_parent"), dict) else {}
        fields = [
            f"substep={substep}",
            f"status={status}",
            f"asset_type={asset_type or '-'}",
            f"file_name={file_name}",
        ]
        if timeout_s is not None:
            fields.append(f"timeout_s={timeout_s:.1f}")
        if elapsed_s is not None:
            fields.append(f"elapsed_s={elapsed_s:.3f}")
        if hint.get("message_id_raw"):
            fields.append(f"message_id_raw={hint.get('message_id_raw')}")
        if hint.get("element_id"):
            fields.append(f"element_id={hint.get('element_id')}")
        if forward_parent.get("message_id_raw"):
            fields.append(f"forward_parent_message_id_raw={forward_parent.get('message_id_raw')}")
        if detail:
            fields.append(f"detail={detail}")
        message = "media_resolution_substep " + " ".join(fields)
        if status == "timeout":
            self._logger.warning(message)
            return
        if elapsed_s is not None and elapsed_s >= self.SLOW_REMOTE_SUBSTEP_WARN_S:
            self._logger.info(message)

    def _resolve_via_context_only(
        self,
        request: dict[str, Any],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None] | None:
        hint = self._request_hint(request)
        if not self._has_context_hint(hint):
            return None
        asset_type = str(request.get("asset_type") or "").strip()
        asset_role = str(request.get("asset_role") or "").strip() or None
        old_bucket = self._old_context_bucket(asset_type, request)
        if self._should_skip_old_bucket(old_bucket):
            return None, self._missing_bucket_resolver(old_bucket)
        payload = self._download_via_context(
            hint,
            asset_type=asset_type,
            asset_role=asset_role,
            request=request,
            trace_callback=trace_callback,
        )
        if payload is None:
            self._note_old_bucket_failure(old_bucket)
            return None, self._missing_bucket_resolver(old_bucket)
        public_resolved = self._resolve_from_public_token(
            payload,
            old_bucket=old_bucket,
            expired_candidate=self._should_share_missing_outcome(request),
            request=request,
            trace_callback=trace_callback,
        )
        if public_resolved not in {None, (None, None)}:
            resolved_path, resolver = public_resolved
            if resolved_path is not None:
                self._note_old_bucket_success(old_bucket)
            elif resolver == "qq_expired_after_napcat":
                self._note_old_bucket_expired_like(old_bucket)
            return public_resolved
        fast_resolved = self._resolve_from_fast_payload(payload)
        if fast_resolved != (None, None):
            self._note_old_bucket_success(old_bucket)
            return fast_resolved
        classified_missing = self._classify_missing_from_payload(
            payload,
            old_bucket=old_bucket,
            expired_candidate=self._should_share_missing_outcome(request),
        )
        if classified_missing is not None:
            self._note_old_bucket_expired_like(old_bucket)
            return None, classified_missing
        self._note_old_bucket_failure(old_bucket)
        return None, self._missing_bucket_resolver(old_bucket)

    def _context_payload_for_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        hint = self._request_hint(request)
        if self._has_forward_parent_hint(hint):
            key = self._request_key(request)
            prefetched_payload = self._prefetched_forward_media_payloads.get(key)
            if isinstance(prefetched_payload, dict):
                return prefetched_payload
            _ = self._download_via_forward_context(request)
            forward_payload = self._prefetched_forward_media_payloads.get(key)
            return forward_payload if isinstance(forward_payload, dict) else None
        asset_type = str(request.get("asset_type") or "").strip()
        asset_role = str(request.get("asset_role") or "").strip() or None
        return self._download_via_context(hint, asset_type=asset_type, asset_role=asset_role)

    def _resolve_via_fresh_public_retry(
        self,
        request: dict[str, Any],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None] | None:
        asset_type = str(request.get("asset_type") or "").strip()
        if asset_type != "image":
            return None
        old_bucket = self._old_context_bucket(asset_type, request)
        if old_bucket is not None:
            return None
        hint = self._request_hint(request)
        if not self._has_context_hint(hint) or self._has_forward_parent_hint(hint):
            return None
        asset_role = str(request.get("asset_role") or "").strip() or None
        payload = self._download_via_context(
            hint,
            asset_type=asset_type,
            asset_role=asset_role,
            request=request,
            trace_callback=trace_callback,
        )
        if payload is None:
            return None
        public_resolved = self._resolve_from_public_token(
            payload,
            old_bucket=old_bucket,
            request=request,
            trace_callback=trace_callback,
        )
        if public_resolved not in {None, (None, None)}:
            return public_resolved
        fast_resolved = self._resolve_from_fast_payload(payload)
        if fast_resolved != (None, None):
            return fast_resolved
        return None

    def _resolve_via_direct_file_id(
        self,
        request: dict[str, Any],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None] | None:
        asset_type = str(request.get("asset_type") or "").strip()
        if asset_type not in {"file", "video"}:
            return None
        hint = self._request_hint(request)
        file_id = str(hint.get("file_id") or "").strip()
        if not file_id or not file_id.startswith("/"):
            return None
        timeout_s = self.DIRECT_FILE_ID_TIMEOUT_S
        self._emit_asset_substep_trace(
            trace_callback,
            request,
            stage="start",
            substep="direct_file_id_get_file",
            timeout_s=timeout_s,
        )
        started = monotonic()
        try:
            # NapCat GetFileBase treats `file` as authoritative and only falls back
            # to `file_id` when `file` is empty. Passing both can accidentally turn
            # an exact file-id lookup into a loose name-based search.
            payload = self._client.get_file(file_id=file_id, timeout=timeout_s)
        except NapCatApiTimeoutError as exc:
            elapsed_s = monotonic() - started
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep="direct_file_id_get_file",
                timeout_s=timeout_s,
                status="timeout",
                elapsed_s=elapsed_s,
                detail=str(exc),
            )
            self._log_remote_substep_outcome(
                request=request,
                substep="direct_file_id_get_file",
                status="timeout",
                timeout_s=timeout_s,
                elapsed_s=elapsed_s,
                detail=str(exc),
            )
            return None
        except NapCatApiError as exc:
            elapsed_s = monotonic() - started
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep="direct_file_id_get_file",
                timeout_s=timeout_s,
                status="error",
                elapsed_s=elapsed_s,
                detail=str(exc),
            )
            return None
        elapsed_s = monotonic() - started
        self._emit_asset_substep_trace(
            trace_callback,
            request,
            stage="done",
            substep="direct_file_id_get_file",
            timeout_s=timeout_s,
            status="ok",
            elapsed_s=elapsed_s,
        )
        self._log_remote_substep_outcome(
            request=request,
            substep="direct_file_id_get_file",
            status="ok",
            timeout_s=timeout_s,
            elapsed_s=elapsed_s,
        )
        resolved = self._resolved_path_from_payload(payload if isinstance(payload, dict) else None)
        if resolved is not None:
            return resolved, "napcat_segment_file_id_get_file"
        remote_downloaded = self._resolve_remote_from_public_payload(
            {
                "asset_type": asset_type,
                "file_name": str(request.get("file_name") or "").strip() or None,
            },
            payload if isinstance(payload, dict) else None,
            action="get_file",
        )
        if remote_downloaded is not None:
            return remote_downloaded, "napcat_segment_file_id_get_file_remote_url"
        return None

    def _download_via_forward_context(
        self,
        request: dict[str, Any],
        *,
        materialize: bool = False,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None] | None:
        if self._fast_client is None or self._fast_context_route_disabled:
            return None
        hint = self._request_hint(request)
        parent = hint.get("_forward_parent")
        if not isinstance(parent, dict) or not self._has_context_hint(parent):
            return None
        parent_element_id = str(parent.get("element_id") or "").strip()
        if not parent_element_id:
            return None
        key = self._request_key(request)
        prefetched = self._prefetched_forward_media.get(key)
        prefetched_payload = self._prefetched_forward_media_payloads.get(key)
        if prefetched is not None and not materialize:
            return prefetched
        if (
            materialize
            and prefetched is not None
            and isinstance(prefetched_payload, dict)
            and str(prefetched_payload.get("_forward_targeted_mode") or "").strip().lower()
            in {"single_target_download", "hydrated"}
        ):
            return prefetched
        timeout_s = (
            self.FORWARD_TARGET_HTTP_TIMEOUT_S if materialize else self.FORWARD_CONTEXT_TIMEOUT_S
        )
        substep = "forward_context_materialize" if materialize else "forward_context_metadata"
        self._emit_asset_substep_trace(
            trace_callback,
            request,
            stage="start",
            substep=substep,
            timeout_s=timeout_s,
        )
        started = monotonic()
        try:
            payload = self._fast_client.hydrate_forward_media(
                message_id_raw=str(parent["message_id_raw"]),
                element_id=parent_element_id,
                peer_uid=str(parent["peer_uid"]),
                chat_type_raw=int(parent["chat_type_raw"]),
                asset_type=str(request.get("asset_type") or "").strip() or None,
                asset_role=str(request.get("asset_role") or "").strip() or None,
                file_name=str(request.get("file_name") or "").strip() or None,
                md5=str(request.get("md5") or "").strip() or None,
                file_id=str(hint.get("file_id") or "").strip() or None,
                url=str(hint.get("remote_url") or hint.get("url") or "").strip() or None,
                materialize=materialize,
                download_timeout_ms=(
                    self.FORWARD_TARGET_DOWNLOAD_TIMEOUT_MS if materialize else None
                ),
                timeout=timeout_s,
            )
        except NapCatFastHistoryUnavailable as exc:
            elapsed_s = monotonic() - started
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep=substep,
                timeout_s=timeout_s,
                status="unavailable",
                elapsed_s=elapsed_s,
                detail=str(exc),
            )
            self._fast_context_route_disabled = True
            self._logger.info(
                "fast_forward_hydration_unavailable; disabling fast forward hydration for this process. detail=%s",
                exc,
            )
            self._prefetched_forward_media[key] = (None, None)
            self._prefetched_forward_media_payloads[key] = None
            return None
        except NapCatFastHistoryTimeoutError as exc:
            elapsed_s = monotonic() - started
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep=substep,
                timeout_s=timeout_s,
                status="timeout",
                elapsed_s=elapsed_s,
                detail=str(exc),
            )
            self._log_remote_substep_outcome(
                request=request,
                substep=substep,
                status="timeout",
                timeout_s=timeout_s,
                elapsed_s=elapsed_s,
                detail=str(exc),
            )
            self._prefetched_forward_media[key] = (None, None)
            self._prefetched_forward_media_payloads[key] = None
            return None
        except Exception:
            elapsed_s = monotonic() - started
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep=substep,
                timeout_s=timeout_s,
                status="error",
                elapsed_s=elapsed_s,
            )
            self._prefetched_forward_media[key] = (None, None)
            self._prefetched_forward_media_payloads[key] = None
            return None
        elapsed_s = monotonic() - started
        self._emit_asset_substep_trace(
            trace_callback,
            request,
            stage="done",
            substep=substep,
            timeout_s=timeout_s,
            status="ok",
            elapsed_s=elapsed_s,
        )
        self._log_remote_substep_outcome(
            request=request,
            substep=substep,
            status="ok",
            timeout_s=timeout_s,
            elapsed_s=elapsed_s,
        )
        assets = payload.get("assets") if isinstance(payload, dict) else None
        matched, matched_payload = self._pick_forward_asset_match(
            request,
            assets if isinstance(assets, list) else [],
            trace_callback=trace_callback,
        )
        if isinstance(matched_payload, dict) and isinstance(payload, dict):
            enriched_payload = dict(matched_payload)
            enriched_payload["_forward_targeted_mode"] = str(payload.get("targeted_mode") or "").strip()
            matched_payload = enriched_payload
        self._prefetched_forward_media[key] = matched
        self._prefetched_forward_media_payloads[key] = matched_payload
        return matched

    def _download_via_context(
        self,
        hint: dict[str, Any],
        *,
        asset_type: str,
        asset_role: str | None,
        request: dict[str, Any] | None = None,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any] | None:
        if self._fast_client is None or self._fast_context_route_disabled or not self._has_context_hint(hint):
            return None
        timeout_s = self.CONTEXT_ROUTE_TIMEOUT_S
        if request is not None:
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="start",
                substep="context_hydration",
                timeout_s=timeout_s,
            )
        started = monotonic()
        try:
            data = self._fast_client.hydrate_media(
                message_id_raw=str(hint["message_id_raw"]),
                element_id=str(hint["element_id"]),
                peer_uid=str(hint["peer_uid"]),
                chat_type_raw=int(hint["chat_type_raw"]),
                asset_type=asset_type,
                asset_role=asset_role,
                timeout=timeout_s,
            )
        except NapCatFastHistoryUnavailable as exc:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep="context_hydration",
                    timeout_s=timeout_s,
                    status="unavailable",
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
            self._fast_context_route_disabled = True
            self._logger.info(
                "fast_context_hydration_unavailable; disabling /hydrate-media for this process and "
                "falling back to local/public recovery. A NapCat restart may be required. detail=%s",
                exc,
            )
            return None
        except NapCatFastHistoryTimeoutError as exc:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep="context_hydration",
                    timeout_s=timeout_s,
                    status="timeout",
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
                self._log_remote_substep_outcome(
                    request=request,
                    substep="context_hydration",
                    status="timeout",
                    timeout_s=timeout_s,
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
            return None
        except (NapCatFastHistoryError, ValueError, TypeError):
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep="context_hydration",
                    timeout_s=timeout_s,
                    status="error",
                    elapsed_s=elapsed_s,
                )
            return None
        except Exception:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep="context_hydration",
                    timeout_s=timeout_s,
                    status="error",
                    elapsed_s=elapsed_s,
                )
            return None
        elapsed_s = monotonic() - started
        if request is not None:
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep="context_hydration",
                timeout_s=timeout_s,
                status="ok",
                elapsed_s=elapsed_s,
            )
            self._log_remote_substep_outcome(
                request=request,
                substep="context_hydration",
                status="ok",
                timeout_s=timeout_s,
                elapsed_s=elapsed_s,
            )
        return data if isinstance(data, dict) else None

    def _pick_forward_asset_match(
        self,
        request: dict[str, Any],
        assets: list[dict[str, Any]],
        *,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[tuple[Path | None, str | None], dict[str, Any] | None]:
        asset_type = str(request.get("asset_type") or "").strip()
        asset_role = str(request.get("asset_role") or "").strip() or None
        hint = self._request_hint(request)
        file_name = str(request.get("file_name") or "").strip().lower()
        md5 = str(request.get("md5") or "").strip().lower()
        file_id = str(hint.get("file_id") or "").strip()
        request_url = self._normalized_match_url(
            hint.get("remote_url") or hint.get("url")
        )
        request_stem = self._normalized_file_stem(file_name)
        best_match: dict[str, Any] | None = None
        best_score = -1
        best_rank = (-1, -1, -1, -1)
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if str(asset.get("asset_type") or "").strip() != asset_type:
                continue
            if asset_role and str(asset.get("asset_role") or "").strip() != asset_role:
                continue
            asset_file_name = str(asset.get("file_name") or "").strip().lower()
            asset_md5 = str(asset.get("md5") or "").strip().lower()
            asset_file_id = str(asset.get("file_id") or "").strip()
            asset_url = self._normalized_match_url(
                asset.get("remote_url") or asset.get("url")
            )
            asset_stem = self._normalized_file_stem(asset_file_name)
            score = 0
            if md5 and asset_md5 and asset_md5 == md5:
                score += 100
            if file_id and asset_file_id and asset_file_id == file_id:
                score += 90
            if request_url and asset_url and asset_url == request_url:
                score += 70
            if file_name and asset_file_name and asset_file_name == file_name:
                score += 50
            if request_stem and asset_stem and asset_stem == request_stem:
                score += 20
            if score <= 0:
                continue
            rank = (
                1 if str(asset.get("public_file_token") or "").strip() else 0,
                1 if self._resolved_path_from_payload(asset) is not None else 0,
                len(asset_file_name or ""),
                score,
            )
            if score > best_score or (score == best_score and rank > best_rank):
                best_score = score
                best_rank = rank
                best_match = asset
        if best_match is None:
            return (None, None), None
        resolved = self._resolve_from_public_token(
            best_match,
            request=request,
            trace_callback=trace_callback,
        )
        if resolved is None:
            resolved = self._resolve_from_fast_payload(
                best_match,
                default_resolver="napcat_forward_hydrated",
            )
        if resolved == (None, None):
            resolved = self._resolve_from_forward_remote_url(best_match)
        return resolved, best_match

    def _download(self, asset_type: str, *, file_id: str | None, file_name: str | None) -> str | None:
        try:
            if asset_type == "image":
                data = self._client.get_image(
                    file_id=file_id,
                    file=file_name,
                    timeout=self.PUBLIC_TOKEN_ACTION_TIMEOUT_S,
                )
            elif asset_type == "speech":
                data = self._client.get_record(
                    file_id=file_id,
                    file=file_name,
                    timeout=self.PUBLIC_TOKEN_ACTION_TIMEOUT_S,
                )
            elif asset_type == "sticker":
                return None
            else:
                data = self._client.get_file(
                    file_id=file_id,
                    file=file_name,
                    timeout=self.PUBLIC_TOKEN_ACTION_TIMEOUT_S,
                )
        except NapCatApiError:
            return None
        path = data.get("file") or data.get("url")
        return str(path) if path else None

    def _call_public_action_with_token(
        self,
        action: str,
        token: str,
        *,
        file_name: str | None = None,
        request: dict[str, Any] | None = None,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any] | None:
        normalized_action = str(action or "").strip().lower()
        if not normalized_action or not token:
            return None
        timeout_s = self.PUBLIC_TOKEN_ACTION_TIMEOUT_S

        primary_substep = f"public_token_{normalized_action}"
        if request is not None:
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="start",
                substep=primary_substep,
                timeout_s=timeout_s,
            )
        started = monotonic()
        try:
            if normalized_action == "get_image":
                payload = self._client.get_image(file=token, timeout=timeout_s)
            elif normalized_action == "get_file":
                payload = self._client.get_file(file=token, timeout=timeout_s)
            elif normalized_action == "get_record":
                payload = self._client.get_record(file=token, out_format="mp3", timeout=timeout_s)
            else:
                return None
        except NapCatApiTimeoutError as exc:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep=primary_substep,
                    timeout_s=timeout_s,
                    status="timeout",
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
                self._log_remote_substep_outcome(
                    request=request,
                    substep=primary_substep,
                    status="timeout",
                    timeout_s=timeout_s,
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
            return None
        except NapCatApiError as exc:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep=primary_substep,
                    timeout_s=timeout_s,
                    status="error",
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
            pass
        else:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep=primary_substep,
                    timeout_s=timeout_s,
                    status="ok",
                    elapsed_s=elapsed_s,
                )
                self._log_remote_substep_outcome(
                    request=request,
                    substep=primary_substep,
                    status="ok",
                    timeout_s=timeout_s,
                    elapsed_s=elapsed_s,
                )
            return payload

        # Compatibility fallback for runtimes that still expect `file_id`.
        fallback_substep = f"{primary_substep}_fallback"
        if request is not None:
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="start",
                substep=fallback_substep,
                timeout_s=timeout_s,
            )
        started = monotonic()
        try:
            if normalized_action == "get_image":
                payload = self._client.get_image(file_id=token, timeout=timeout_s)
            elif normalized_action == "get_file":
                payload = self._client.get_file(file_id=token, timeout=timeout_s)
            elif normalized_action == "get_record":
                payload = self._client.get_record(file_id=token, out_format="mp3", timeout=timeout_s)
            else:
                return None
        except NapCatApiTimeoutError as exc:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep=fallback_substep,
                    timeout_s=timeout_s,
                    status="timeout",
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
                self._log_remote_substep_outcome(
                    request=request,
                    substep=fallback_substep,
                    status="timeout",
                    timeout_s=timeout_s,
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
            return None
        except NapCatApiError as exc:
            elapsed_s = monotonic() - started
            if request is not None:
                self._emit_asset_substep_trace(
                    trace_callback,
                    request,
                    stage="done",
                    substep=fallback_substep,
                    timeout_s=timeout_s,
                    status="error",
                    elapsed_s=elapsed_s,
                    detail=str(exc),
                )
            return None
        elapsed_s = monotonic() - started
        if request is not None:
            self._emit_asset_substep_trace(
                trace_callback,
                request,
                stage="done",
                substep=fallback_substep,
                timeout_s=timeout_s,
                status="ok",
                elapsed_s=elapsed_s,
            )
            self._log_remote_substep_outcome(
                request=request,
                substep=fallback_substep,
                status="ok",
                timeout_s=timeout_s,
                elapsed_s=elapsed_s,
            )
        return payload

    def _resolve_from_fast_payload(
        self,
        data: dict[str, Any] | None,
        *,
        default_resolver: str = "napcat_context_hydrated",
    ) -> tuple[Path | None, str | None]:
        resolved = self._resolved_path_from_payload(data)
        if resolved is None:
            return None, None
        return resolved, default_resolver

    def _resolve_from_public_token(
        self,
        data: dict[str, Any] | None,
        *,
        old_bucket: tuple[str, str] | None = None,
        expired_candidate: bool = False,
        request: dict[str, Any] | None = None,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None] | None:
        if not isinstance(data, dict):
            return None
        if str(data.get("asset_type") or "").strip() == "sticker":
            return None
        action = str(data.get("public_action") or "").strip().lower()
        token = str(data.get("public_file_token") or "").strip()
        if not action or not token:
            return None
        payload = self._call_public_action_with_token(
            action,
            token,
            file_name=str(data.get("file_name") or "").strip() or None,
            request=request,
            trace_callback=trace_callback,
        )
        if payload is None:
            return None
        resolved = self._resolved_path_from_payload(payload if isinstance(payload, dict) else None)
        if resolved is not None:
            return resolved, f"napcat_public_token_{action}"
        remote_downloaded = self._resolve_remote_from_public_payload(
            data,
            payload if isinstance(payload, dict) else None,
            action=action,
        )
        if remote_downloaded is not None:
            return remote_downloaded, f"napcat_public_token_{action}_remote_url"
        classified_missing = self._classify_missing_from_public_payload(
            payload if isinstance(payload, dict) else None,
            old_bucket=old_bucket,
            expired_candidate=expired_candidate,
        )
        if classified_missing is not None:
            return None, classified_missing
        return None

    def _remember_shared_outcome(
        self,
        shared_key: tuple[Any, ...] | None,
        request: dict[str, Any],
        result: tuple[Path | None, str | None],
    ) -> tuple[Path | None, str | None]:
        if shared_key is None:
            return result
        resolved_path, _resolver = result
        if resolved_path is not None or self._should_share_missing_outcome(request):
            self._shared_media_outcomes[shared_key] = result
        return result

    def _should_share_missing_outcome(self, request: dict[str, Any]) -> bool:
        hint = self._request_hint(request)
        asset_type = str(request.get("asset_type") or "").strip()
        if self._has_forward_parent_hint(hint) and asset_type in {"file", "video"}:
            return True
        raw_timestamp = request.get("timestamp_ms")
        if not isinstance(raw_timestamp, (int, float)):
            return False
        try:
            asset_dt = datetime.fromtimestamp(float(raw_timestamp) / 1000.0, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return False
        return datetime.now(timezone.utc) - asset_dt >= timedelta(days=self.SHARED_MISS_CACHE_MIN_AGE_DAYS)

    def _shared_request_key(self, request: dict[str, Any]) -> tuple[Any, ...] | None:
        hint = self._request_hint(request)
        file_name = str(request.get("file_name") or "").strip().lower()
        md5 = str(request.get("md5") or "").strip().lower()
        source_leaf = ""
        source_path = str(request.get("source_path") or "").strip()
        if source_path:
            source_leaf = PureWindowsPath(source_path).name.strip().lower()
        file_id = str(hint.get("file_id") or "").strip()
        remote_url = self._normalized_match_url(hint.get("remote_url") or hint.get("url"))
        if not any([file_name, md5, source_leaf, file_id, remote_url]):
            return None
        return (
            str(request.get("asset_type") or "").strip(),
            str(request.get("asset_role") or "").strip(),
            file_name,
            md5,
            source_leaf,
            file_id,
            remote_url,
        )

    def _resolve_from_stale_local_neighbors(
        self,
        request: dict[str, Any],
    ) -> tuple[Path | None, str | None]:
        asset_type = str(request.get("asset_type") or "").strip()
        if asset_type != "image":
            return None, None
        source_path = str(request.get("source_path") or "").strip()
        if not source_path:
            return None, None
        fallback = self._find_stale_image_neighbor(source_path)
        if fallback is None:
            return None, None
        return fallback, "stale_source_neighbor"

    def _resolve_from_hint_local_path(
        self,
        hint: dict[str, Any] | None,
    ) -> tuple[Path | None, str | None]:
        if not isinstance(hint, dict):
            return None, None
        for key in ("file", "path", "url"):
            resolved = self._resolved_path_from_payload({key: hint.get(key)})
            if resolved is not None:
                return resolved, "hint_local_path"
        return None, None

    def _find_stale_image_neighbor(self, source_path: str) -> Path | None:
        source = Path(source_path)
        if source.exists() and source.is_file():
            return source.resolve()
        parts = list(PureWindowsPath(source_path).parts)
        lowered = [part.casefold() for part in parts]
        if "nt_qq" not in lowered or "nt_data" not in lowered:
            return None
        parent = source.parent
        parent_name = parent.name.casefold()
        if parent_name not in {"ori", "oritemp", "thumb"}:
            return None
        stem = self._strip_thumb_suffix(source.stem)
        if not stem:
            return None
        base_dir = parent.parent
        matches: list[Path] = []
        for sibling_name in ("Ori", "OriTemp", "Thumb"):
            sibling_dir = base_dir / sibling_name
            if not sibling_dir.exists() or not sibling_dir.is_dir():
                continue
            match = self._find_image_candidate_in_directory(sibling_dir, stem=stem)
            if match is not None:
                matches.append(match)
        if not matches:
            return None
        unique_matches = {match.resolve(): None for match in matches}
        return sorted(unique_matches, key=self._neighbor_candidate_priority)[0]

    @staticmethod
    def _strip_thumb_suffix(value: str) -> str:
        lowered = value.casefold()
        if lowered.endswith("_720"):
            return value[:-4]
        if lowered.endswith("_0"):
            return value[:-2]
        return value

    @staticmethod
    def _find_image_candidate_in_directory(directory: Path, *, stem: str) -> Path | None:
        candidates: list[Path] = []
        direct = directory / stem
        if direct.exists() and direct.is_file() and direct.stat().st_size > 0:
            candidates.append(direct.resolve())
        for pattern in (f"{stem}.*", f"{stem}_*.*", f"{stem}_*"):
            for candidate in directory.glob(pattern):
                if not candidate.is_file():
                    continue
                if candidate.stat().st_size <= 0:
                    continue
                if not NapCatMediaDownloader._image_extension_allowed(candidate):
                    continue
                candidates.append(candidate.resolve())
        if not candidates:
            return None
        unique_candidates = {candidate.resolve(): None for candidate in candidates}
        return sorted(unique_candidates, key=NapCatMediaDownloader._neighbor_candidate_priority)[0]

    @staticmethod
    def _image_extension_allowed(path: Path) -> bool:
        suffix = path.suffix.casefold()
        return suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"} or suffix == ""

    @staticmethod
    def _neighbor_candidate_priority(path: Path) -> tuple[int, int, int, int, str]:
        parent_rank = {"ori": 0, "oritemp": 1, "thumb": 2}.get(path.parent.name.casefold(), 99)
        suffix_rank = {
            ".gif": 0,
            ".webp": 1,
            ".png": 2,
            ".jpg": 3,
            ".jpeg": 4,
            ".bmp": 5,
            "": 6,
        }.get(path.suffix.casefold(), 99)
        stem = path.stem if path.suffix else path.name
        match = re.search(r"_(\d+)$", stem)
        has_variant = 1 if match else 0
        variant_rank = -int(match.group(1)) if match else 0
        return (parent_rank, suffix_rank, has_variant, variant_rank, str(path))

    @staticmethod
    def _normalized_file_stem(value: object) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        return Path(text).stem.strip().lower()

    @staticmethod
    def _normalized_match_url(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        if parsed.scheme and parsed.netloc:
            return parsed._replace(
                scheme=parsed.scheme.lower(),
                netloc=parsed.netloc.lower(),
                fragment="",
            ).geturl()
        return text.lower()

    @staticmethod
    def _resolved_path_from_payload(data: dict[str, Any] | None) -> Path | None:
        if not isinstance(data, dict):
            return None
        value = data.get("file") or data.get("url")
        if not value:
            return None
        path = Path(str(value))
        if not path.exists() or not path.is_file():
            return None
        return path.resolve()

    def _resolve_from_forward_remote_url(
        self,
        data: dict[str, Any] | None,
    ) -> tuple[Path | None, str | None]:
        if not isinstance(data, dict):
            return None, None
        asset_type = str(data.get("asset_type") or "").strip()
        if asset_type not in {"image", "file", "speech", "video"}:
            return None, None
        resolved = self._download_remote_media(
            asset_type=asset_type,
            file_name=str(data.get("file_name") or "").strip() or None,
            hint={
                "url": data.get("remote_url") or data.get("url"),
            },
        )
        if resolved is None:
            return None, None
        path = Path(resolved)
        if not path.exists() or not path.is_file():
            return None, None
        return path.resolve(), "napcat_forward_remote_url"

    def _resolve_from_sticker_remote_url(
        self,
        hint: dict[str, Any] | None,
        *,
        asset_role: str | None,
        file_name: str | None,
    ) -> tuple[Path | None, str | None]:
        if not isinstance(hint, dict):
            return None, None
        resolved = self._download_remote_sticker(
            hint,
            asset_role=asset_role,
            file_name=file_name,
        )
        if resolved is None:
            return None, None
        path = Path(resolved)
        if not path.exists() or not path.is_file():
            return None, None
        return path.resolve(), "sticker_remote_download"

    def _resolve_remote_from_public_payload(
        self,
        request_data: dict[str, Any],
        payload: dict[str, Any] | None,
        *,
        action: str,
    ) -> Path | None:
        if not isinstance(payload, dict):
            return None
        asset_type = str(request_data.get("asset_type") or "").strip()
        if asset_type not in {"image", "file", "video"}:
            return None
        remote_url = str(payload.get("url") or "").strip()
        if not remote_url:
            return None
        file_name = (
            str(payload.get("file_name") or "").strip()
            or str(request_data.get("file_name") or "").strip()
            or None
        )
        resolved = self._download_remote_media(
            asset_type=asset_type,
            file_name=file_name,
            hint={"url": remote_url},
        )
        if resolved is None:
            return None
        path = Path(resolved)
        if not path.exists() or not path.is_file():
            return None
        return path.resolve()

    def _download_remote_sticker(
        self,
        hint: dict[str, Any],
        *,
        asset_role: str | None,
        file_name: str | None,
    ) -> str | None:
        remote_url = str(hint.get("remote_url") or "").strip()
        remote_file_name = str(hint.get("remote_file_name") or "").strip()
        if not remote_url or self._remote_cache_dir is None:
            return None

        cache_root = self._remote_cache_dir / "remote_stickers"
        native_name = remote_file_name or file_name or "sticker.gif"
        role_folder = "dynamic" if asset_role == "dynamic" else "static"
        native_path = cache_root / role_folder / native_name
        try:
            native_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        if not native_path.exists() or not native_path.is_file() or native_path.stat().st_size <= 0:
            payload = self._download_remote_payload(remote_url)
            if payload is None:
                return None
            if not self._write_bytes(native_path, payload):
                return None
        return str(native_path)

    def _download_remote_payload(self, remote_url: str) -> bytes | None:
        resolved_url = self._resolve_remote_url(remote_url)
        if not resolved_url:
            return None
        try:
            response = self._remote_client.get(resolved_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        payload = response.content
        return payload if payload else None

    def _download_remote_media(
        self,
        *,
        asset_type: str,
        file_name: str | None,
        hint: dict[str, Any],
    ) -> str | None:
        remote_url = str(hint.get("url") or "").strip()
        if not remote_url or self._remote_cache_dir is None:
            return None

        remote_name = self._remote_file_name(remote_url, file_name=file_name)
        if not remote_name:
            return None
        cache_root = self._remote_cache_dir / "remote_media" / asset_type
        target_path = cache_root / remote_name
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        if not target_path.exists() or not target_path.is_file() or target_path.stat().st_size <= 0:
            payload = self._download_remote_payload(remote_url)
            if payload is None:
                return None
            if not self._write_bytes(target_path, payload):
                return None
        return str(target_path)

    def _should_skip_old_bucket(self, old_bucket: tuple[str, str] | None) -> bool:
        if old_bucket is None:
            return False
        if old_bucket in self._old_context_expired_buckets:
            if old_bucket not in self._old_context_skip_logged:
                self._old_context_skip_logged.add(old_bucket)
                self._logger.info(
                    "skip_context_hydration_for_expired_assets bucket=%s",
                    "/".join(old_bucket),
                )
            return True
        failures = self._old_context_failure_buckets.get(old_bucket, 0)
        if failures < self.OLD_CONTEXT_BUCKET_FAILURE_LIMIT:
            return False
        if old_bucket not in self._old_context_skip_logged:
            self._old_context_skip_logged.add(old_bucket)
            self._logger.info(
                "skip_context_hydration_for_old_assets bucket=%s failures=%s",
                "/".join(old_bucket),
                failures,
            )
        return True

    def _note_old_bucket_failure(self, old_bucket: tuple[str, str] | None) -> None:
        if old_bucket is None:
            return
        self._old_context_failure_buckets[old_bucket] = (
            self._old_context_failure_buckets.get(old_bucket, 0) + 1
        )

    def _note_old_bucket_success(self, old_bucket: tuple[str, str] | None) -> None:
        if old_bucket is None:
            return
        self._old_context_expired_buckets.discard(old_bucket)
        self._old_context_failure_buckets.pop(old_bucket, None)
        self._old_context_skip_logged.discard(old_bucket)

    def _note_old_bucket_expired_like(self, old_bucket: tuple[str, str] | None) -> None:
        if old_bucket is None:
            return
        self._old_context_expired_buckets.add(old_bucket)
        self._old_context_failure_buckets[old_bucket] = self.OLD_CONTEXT_BUCKET_FAILURE_LIMIT
        self._old_context_skip_logged.discard(old_bucket)

    def _missing_bucket_resolver(self, old_bucket: tuple[str, str] | None) -> str | None:
        if old_bucket is not None and old_bucket in self._old_context_expired_buckets:
            return "qq_expired_after_napcat"
        return None

    def _classify_missing_from_payload(
        self,
        data: dict[str, Any] | None,
        *,
        old_bucket: tuple[str, str] | None,
        expired_candidate: bool = False,
    ) -> str | None:
        if old_bucket is None and not expired_candidate:
            return None
        if not isinstance(data, dict):
            return None
        if self._resolved_path_from_payload(data) is not None:
            return None
        action = str(data.get("public_action") or "").strip().lower()
        token = str(data.get("public_file_token") or "").strip()
        if not action or not token:
            return None
        remote_url = str(data.get("remote_url") or data.get("url") or "").strip()
        if not remote_url:
            return None
        resolved_url = self._resolve_remote_url(remote_url)
        if not resolved_url:
            return None
        parsed = urlparse(resolved_url)
        if parsed.scheme not in {"http", "https"}:
            return None
        host = parsed.netloc.lower()
        if "multimedia.nt.qq.com.cn" not in host and "gchat.qpic.cn" not in host:
            return None
        return "qq_expired_after_napcat"

    def _classify_missing_from_public_payload(
        self,
        data: dict[str, Any] | None,
        *,
        old_bucket: tuple[str, str] | None,
        expired_candidate: bool = False,
    ) -> str | None:
        if old_bucket is None and not expired_candidate:
            return None
        if not isinstance(data, dict):
            return None
        if self._resolved_path_from_payload(data) is not None:
            return None
        remote_url = str(data.get("url") or "").strip()
        if not remote_url:
            return None
        resolved_url = self._resolve_remote_url(remote_url)
        if not resolved_url:
            return None
        parsed = urlparse(resolved_url)
        if parsed.scheme not in {"http", "https"}:
            return None
        host = parsed.netloc.lower()
        if "multimedia.nt.qq.com.cn" not in host and "gchat.qpic.cn" not in host:
            return None
        return "qq_expired_after_napcat"

    def _classify_forward_missing(self, request: dict[str, Any]) -> str | None:
        if str(request.get("asset_type") or "").strip() != "image":
            return None
        hint = self._request_hint(request)
        if not self._has_forward_parent_hint(hint):
            return None
        source_path = str(request.get("source_path") or "").strip()
        if source_path:
            return None
        if not self._should_share_missing_outcome(request):
            return None
        return "qq_expired_after_napcat"

    @staticmethod
    def _old_context_bucket(asset_type: str, request: dict[str, Any]) -> tuple[str, str] | None:
        if asset_type not in {"image", "file", "video", "speech"}:
            return None
        raw_timestamp = request.get("timestamp_ms")
        if not isinstance(raw_timestamp, (int, float)):
            return None
        try:
            asset_dt = datetime.fromtimestamp(float(raw_timestamp) / 1000.0, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        if datetime.now(timezone.utc) - asset_dt < timedelta(
            days=NapCatMediaDownloader.OLD_CONTEXT_BUCKET_MIN_AGE_DAYS
        ):
            return None
        return asset_type, asset_dt.strftime("%Y-%m")

    @staticmethod
    def _write_bytes(target_path: Path, payload: bytes) -> bool:
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        try:
            temp_path.write_bytes(payload)
            temp_path.replace(target_path)
        except OSError:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        return True

    @staticmethod
    def _has_context_hint(hint: dict[str, Any]) -> bool:
        required = ("message_id_raw", "element_id", "peer_uid", "chat_type_raw")
        return all(str(hint.get(key) or "").strip() for key in required)

    @staticmethod
    def _has_forward_parent_hint(hint: dict[str, Any]) -> bool:
        parent = hint.get("_forward_parent")
        if not isinstance(parent, dict):
            return False
        return NapCatMediaDownloader._has_context_hint(parent)

    @staticmethod
    def _request_hint(request: dict[str, Any]) -> dict[str, Any]:
        hint = request.get("download_hint")
        return hint if isinstance(hint, dict) else {}

    @staticmethod
    def _request_key(request: dict[str, Any]) -> tuple[Any, ...]:
        hint = NapCatMediaDownloader._request_hint(request)
        parent = hint.get("_forward_parent") if isinstance(hint.get("_forward_parent"), dict) else {}
        return (
            str(request.get("asset_type") or "").strip(),
            str(request.get("asset_role") or "").strip(),
            str(request.get("file_name") or "").strip().lower(),
            str(request.get("md5") or "").strip().lower(),
            str(hint.get("message_id_raw") or "").strip(),
            str(hint.get("element_id") or "").strip(),
            str(hint.get("peer_uid") or "").strip(),
            str(hint.get("chat_type_raw") or "").strip(),
            str(parent.get("message_id_raw") or "").strip(),
            str(parent.get("element_id") or "").strip(),
            str(parent.get("peer_uid") or "").strip(),
            str(parent.get("chat_type_raw") or "").strip(),
        )

    @staticmethod
    def _batch_request_key(request: dict[str, Any]) -> tuple[Any, ...]:
        return (
            str(request.get("asset_type") or "").strip(),
            str(request.get("asset_role") or "").strip(),
            "",
            "",
            str(request.get("message_id_raw") or "").strip(),
            str(request.get("element_id") or "").strip(),
            str(request.get("peer_uid") or "").strip(),
            str(request.get("chat_type_raw") or "").strip(),
            "",
            "",
            "",
            "",
        )

    @staticmethod
    def _remote_file_name(remote_url: str, *, file_name: str | None) -> str | None:
        parsed = urlparse(remote_url)
        remote_leaf = Path(parsed.path).name.strip()
        if file_name:
            return file_name
        if remote_leaf:
            return remote_leaf
        return None

    def _resolve_remote_url(self, remote_url: str) -> str | None:
        candidate = str(remote_url or "").strip()
        if not candidate:
            return None
        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            return candidate
        if not self._remote_base_url:
            return None
        return urljoin(self._remote_base_url.rstrip("/") + "/", candidate.lstrip("/"))
