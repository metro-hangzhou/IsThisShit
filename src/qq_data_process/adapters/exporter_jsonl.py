from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Callable

from ..models import CanonicalAssetRecord, CanonicalMessageRecord, ImportedChatBundle
from ..runtime_control import maybe_cooperative_yield
from ..utils import make_asset_id, make_message_uid


class ExporterJsonlAdapter:
    source_type = "exporter_jsonl"

    def load(
        self,
        source_path: Path,
        *,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> ImportedChatBundle:
        messages: list[CanonicalMessageRecord] = []
        manifest_asset_index = self._load_manifest_asset_index(source_path)
        with source_path.open("r", encoding="utf-8") as handle:
            for ordinal, line in enumerate(handle):
                if not line.strip():
                    continue
                payload = json.loads(line)
                message_uid = make_message_uid(
                    source_type=self.source_type,
                    chat_type=payload["chat_type"],
                    chat_id=payload["chat_id"],
                    message_id=payload.get("message_id"),
                    message_seq=payload.get("message_seq"),
                    timestamp_ms=int(payload["timestamp_ms"]),
                    sender_id_raw=payload["sender_id"],
                    ordinal=ordinal,
                )
                messages.append(
                    CanonicalMessageRecord(
                        message_uid=message_uid,
                        import_source="exporter_jsonl",
                        fidelity="high",
                        chat_type=payload["chat_type"],
                        chat_id=payload["chat_id"],
                        chat_name=payload.get("chat_name"),
                        sender_id_raw=payload["sender_id"],
                        sender_name_raw=payload.get("sender_name"),
                        message_id=payload.get("message_id"),
                        message_seq=payload.get("message_seq"),
                        timestamp_ms=int(payload["timestamp_ms"]),
                        timestamp_iso=payload["timestamp_iso"],
                        content=payload.get("content", ""),
                        text_content=payload.get("text_content", ""),
                        assets=self._extract_assets(
                            message_uid=message_uid,
                            payload=payload,
                            manifest_asset_index=manifest_asset_index,
                        ),
                        extra={"source_payload": self._compact_source_payload(payload)},
                    )
                )
                maybe_cooperative_yield(ordinal + 1)
                if progress_callback is not None and (ordinal + 1) % 1000 == 0:
                    progress_callback(
                        {
                            "phase": "load_parse",
                            "current": ordinal + 1,
                            "total": 0,
                            "message": f"Parsed {(ordinal + 1)} JSONL messages",
                        }
                    )

        if not messages:
            raise ValueError(f"No messages found in exporter JSONL: {source_path}")

        first = messages[0]
        return ImportedChatBundle(
            source_type="exporter_jsonl",
            fidelity="high",
            source_path=source_path,
            chat_type=first.chat_type,
            chat_id=first.chat_id,
            chat_name=first.chat_name,
            messages=messages,
        )

    def _load_manifest_asset_index(
        self, source_path: Path
    ) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
        manifest_path = source_path.with_suffix("").with_suffix(".manifest.json")
        if not manifest_path.exists():
            return {}
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        output: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(
            list
        )
        for item in payload.get("assets", []):
            output[self._manifest_key(item)].append(item)
        return dict(output)

    def _extract_assets(
        self,
        *,
        message_uid: str,
        payload: dict,
        manifest_asset_index: dict[tuple[str, str, str, str], list[dict[str, Any]]],
    ) -> list[CanonicalAssetRecord]:
        assets: list[CanonicalAssetRecord] = []
        for index, segment in enumerate(payload.get("segments", [])):
            segment_type = segment.get("type")
            if segment_type not in {"image", "file", "video"}:
                continue
            file_name = segment.get("file_name")
            manifest_asset = self._pop_manifest_asset(
                payload=payload,
                segment_type=segment_type,
                file_name=file_name,
                manifest_asset_index=manifest_asset_index,
            )
            extra = dict(segment.get("extra", {}))
            path = segment.get("path")
            if manifest_asset is not None:
                materialized = manifest_asset.get("status") in {"copied", "reused"}
                extra.update(
                    {
                        "materialized": materialized,
                        "materialization_status": manifest_asset.get("status"),
                        "materialization_resolver": manifest_asset.get("resolver"),
                        "materialization_exported_rel_path": manifest_asset.get(
                            "exported_rel_path"
                        ),
                        "materialization_note": manifest_asset.get("note"),
                        "materialization_asset_role": manifest_asset.get("asset_role"),
                        "materialization_source_path": manifest_asset.get(
                            "source_path"
                        ),
                        "materialization_resolved_source_path": manifest_asset.get(
                            "resolved_source_path"
                        ),
                        "materialization_timestamp_iso": manifest_asset.get(
                            "timestamp_iso"
                        ),
                    }
                )
                path = (
                    path
                    or manifest_asset.get("resolved_source_path")
                    or manifest_asset.get("source_path")
                )
            assets.append(
                CanonicalAssetRecord(
                    asset_id=make_asset_id(message_uid, segment_type, file_name, index),
                    message_uid=message_uid,
                    asset_type=segment_type,
                    file_name=file_name,
                    path=path,
                    md5=segment.get("md5"),
                    extra=extra,
                )
            )
        return assets

    def _pop_manifest_asset(
        self,
        *,
        payload: dict[str, Any],
        segment_type: str,
        file_name: str | None,
        manifest_asset_index: dict[tuple[str, str, str, str], list[dict[str, Any]]],
    ) -> dict[str, Any] | None:
        if not manifest_asset_index:
            return None
        file_key = str(file_name or "")
        message_id = str(payload.get("message_id") or "")
        message_seq = str(payload.get("message_seq") or "")
        for key in (
            (message_id, message_seq, segment_type, file_key),
            (message_id, "", segment_type, file_key),
            ("", message_seq, segment_type, file_key),
        ):
            bucket = manifest_asset_index.get(key)
            if bucket:
                return bucket.pop(0)
        return None

    def _manifest_key(self, asset: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(asset.get("message_id") or ""),
            str(asset.get("message_seq") or ""),
            str(asset.get("asset_type") or "unknown"),
            str(asset.get("file_name") or ""),
        )

    def _compact_source_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        segments = payload.get("segments", []) or []
        compact_segments = []
        for segment in segments:
            compact = self._compact_segment(segment)
            if compact is not None:
                compact_segments.append(compact)
        return {
            "reply_to": payload.get("reply_to"),
            "segments": compact_segments,
        }

    def _compact_segment(self, segment: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(segment, dict):
            return None
        segment_type = str(segment.get("type") or "")
        if not segment_type:
            return None
        compact: dict[str, Any] = {"type": segment_type}
        extra = segment.get("extra") or {}
        children = extra.get("children")
        if not isinstance(children, list):
            children = self._compact_forward_messages(extra.get("forward_messages"))
        if children:
            compact["children"] = children
        forward_depth = extra.get("forward_depth")
        if isinstance(forward_depth, int) and forward_depth > 0:
            compact["forward_depth"] = forward_depth
        return compact

    def _compact_forward_messages(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        compact_nodes: list[dict[str, Any]] = []
        for node in value:
            if not isinstance(node, dict):
                continue
            node_segments = []
            for segment in node.get("segments") or []:
                compact = self._compact_segment(segment)
                if compact is not None:
                    node_segments.append(compact)
            if node_segments:
                compact_nodes.append({"segments": node_segments})
        return compact_nodes
