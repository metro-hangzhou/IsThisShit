from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..interfaces import AnalyzerContext, DeterministicAnalyzer
from ..models import AnalysisEvidenceRef, DeterministicResult


class ForwardBundleExpander(DeterministicAnalyzer):
    plugin_id = "forward_bundle_expander"
    plugin_version = "0.1.0"
    scope_level = "thread"
    supported_modalities = ("forward_bundle", "text", "image", "video", "file")
    requires = ()
    produces = ("forward_bundle_expansions",)

    def run(self, context: AnalyzerContext) -> list[DeterministicResult]:
        results: list[DeterministicResult] = []
        for message in context.corpus.messages:
            for segment in message.segments:
                if segment.type != "forward":
                    continue
                expansion = _build_forward_expansion(message=message, segment=segment)
                if expansion is None:
                    continue
                results.append(expansion)

        if results:
            return results
        return [
            DeterministicResult(
                plugin_id=self.plugin_id,
                plugin_version=self.plugin_version,
                status="info",
                summary="No forward bundles with expandable structure were found.",
                confidence=1.0,
                tags=["preprocess", "forward", "none"],
                verdict="no_forwards",
                details={"message_count": len(context.corpus.messages)},
            )
        ]


def _build_forward_expansion(*, message: Any, segment: Any) -> DeterministicResult | None:
    extra = getattr(segment, "extra", None) or {}
    preview_lines = [str(item) for item in (extra.get("preview_lines") or []) if str(item).strip()]
    preview_text = _string_or_none(extra.get("preview_text"))
    detailed_text = _string_or_none(extra.get("detailed_text"))
    forward_messages = extra.get("forward_messages") or []
    if not preview_lines and not preview_text and not detailed_text:
        preview_lines, preview_text, detailed_text = _preview_from_message_content(message)
    if not forward_messages:
        forward_messages = _forward_messages_from_children(extra.get("children"))
    if not preview_lines and not preview_text and not detailed_text and not forward_messages:
        return None

    inner_messages = [_compact_forward_message(item, index=index) for index, item in enumerate(forward_messages) if isinstance(item, Mapping)]
    inner_asset_refs = []
    for inner in inner_messages:
        inner_asset_refs.extend(inner["asset_refs"])

    evidence_refs = [
        AnalysisEvidenceRef(
            kind="message",
            message_id=message.message_id,
            segment_id=_segment_id(segment),
            note="outer_forward_message",
        )
    ]
    evidence_refs.extend(
        AnalysisEvidenceRef(
            kind="asset",
            message_id=message.message_id,
            segment_id=_segment_id(segment),
            note=f"inner_forward_asset:{asset_ref['asset_type']}:{asset_ref.get('file_name') or asset_ref.get('token') or ''}",
        )
        for asset_ref in inner_asset_refs[:12]
    )

    confidence = 0.9 if inner_messages else 0.45
    return DeterministicResult(
        plugin_id=ForwardBundleExpander.plugin_id,
        plugin_version=ForwardBundleExpander.plugin_version,
        status="resolved",
        summary=f"Expanded forward bundle on message {message.message_id or message.message_seq} into {len(inner_messages)} inner messages.",
        confidence=confidence,
        tags=["preprocess", "forward", "expanded" if inner_messages else "preview_only"],
        verdict="expanded" if inner_messages else "preview_only",
        details={
            "outer_message_id": message.message_id,
            "outer_message_seq": message.message_seq,
            "segment_id": _segment_id(segment),
            "operation_type": "annotate",
            "scope_level": "thread",
            "view_kind": "expired_asset_context_view" if inner_asset_refs else "processed_view",
            "segment_summary": segment.summary,
            "preview_lines": preview_lines,
            "preview_text": preview_text,
            "detailed_text": detailed_text,
            "forward_meta": {
                "res_id": _string_or_none(extra.get("res_id")),
                "file_name": _string_or_none(extra.get("file_name")),
                "source_name": _string_or_none(extra.get("source_name")),
                "summary_text": _string_or_none(extra.get("summary_text")),
                "forwarded_count": extra.get("forwarded_count"),
                "forward_depth": extra.get("forward_depth"),
            },
            "inner_message_count": len(inner_messages),
            "inner_messages": inner_messages,
            "inner_asset_refs": inner_asset_refs,
            "source_refs": {
                "source_message_id": getattr(message.lineage, "source_message_id", None)
                if getattr(message, "lineage", None) is not None
                else None,
                "source_message_seq": getattr(message.lineage, "source_message_seq", None)
                if getattr(message, "lineage", None) is not None
                else None,
            },
        },
        evidence_refs=evidence_refs,
        notes=[
            "This plugin only derives an explicit forward view; it does not rewrite the original message content.",
            "When inner forward messages are absent, preview lines/text are preserved as low-confidence fallback context.",
        ],
    )


def _compact_forward_message(item: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    segments = [segment for segment in (item.get("segments") or []) if isinstance(segment, Mapping)]
    asset_refs = []
    for segment in segments:
        segment_type = str(segment.get("type") or "").strip()
        if segment_type not in {"image", "video", "file", "speech", "sticker", "emoji"}:
            continue
        asset_refs.append(
            {
                "asset_type": segment_type,
                "file_name": _string_or_none(segment.get("file_name")),
                "token": _string_or_none(segment.get("token")),
                "summary": _string_or_none(segment.get("summary")),
                "md5": _string_or_none(segment.get("md5")),
                "path": _string_or_none(segment.get("path")),
            }
        )

    return {
        "index": index,
        "sender_id": _string_or_none(item.get("sender_id")),
        "sender_name": _string_or_none(item.get("sender_name")),
        "content": _string_or_none(item.get("content")),
        "text_content": _string_or_none(item.get("text_content")),
        "reply_to": dict(item.get("reply_to") or {}) if isinstance(item.get("reply_to"), Mapping) else None,
        "asset_refs": asset_refs,
        "segment_types": [str(segment.get("type") or "") for segment in segments],
    }


def _preview_from_message_content(message: Any) -> tuple[list[str], str | None, str | None]:
    content = _string_or_none(getattr(message, "content", None))
    if not content:
        return [], None, None
    if content.startswith("[forward message] "):
        content = content[len("[forward message] ") :]
    detailed_text = content or None
    preview_lines = [line.strip() for line in content.splitlines() if line.strip()]
    preview_text = preview_lines[0] if preview_lines else detailed_text
    return preview_lines, preview_text, detailed_text


def _forward_messages_from_children(children: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(children, list):
        return output
    for index, child in enumerate(children):
        if not isinstance(child, Mapping):
            continue
        output.append(_forward_child_to_message(child, index=index))
    return output


def _forward_child_to_message(item: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    segments = [segment for segment in (item.get("segments") or []) if isinstance(segment, Mapping)]
    children = [child for child in (item.get("children") or []) if isinstance(child, Mapping)]
    asset_refs = []
    segment_types: list[str] = []
    for segment in segments:
        segment_type = str(segment.get("type") or "").strip()
        if not segment_type:
            continue
        segment_types.append(segment_type)
        if segment_type in {"image", "video", "file", "speech", "sticker", "emoji"}:
            asset_refs.append(
                {
                    "asset_type": segment_type,
                    "file_name": _string_or_none(segment.get("file_name")),
                    "token": _string_or_none(segment.get("token")),
                    "summary": _string_or_none(segment.get("summary")),
                    "md5": _string_or_none(segment.get("md5")),
                    "path": _string_or_none(segment.get("path")),
                }
            )
    text_value = _string_or_none(item.get("text_content")) or _string_or_none(item.get("content"))
    if not text_value and children:
        nested = _forward_messages_from_children(children)
        child_texts = [
            _string_or_none(child.get("text_content")) or _string_or_none(child.get("content"))
            for child in nested
        ]
        child_texts = [text for text in child_texts if text]
        text_value = " / ".join(child_texts[:6]) if child_texts else None
        if not asset_refs:
            for child in nested:
                asset_refs.extend(child.get("asset_refs") or [])
        if not segment_types:
            for child in nested:
                segment_types.extend(child.get("segment_types") or [])
    return {
        "index": index,
        "sender_id": _string_or_none(item.get("sender_id")),
        "sender_name": _string_or_none(item.get("sender_name")),
        "content": text_value,
        "text_content": text_value,
        "reply_to": dict(item.get("reply_to") or {}) if isinstance(item.get("reply_to"), Mapping) else None,
        "asset_refs": asset_refs,
        "segment_types": segment_types,
    }


def _segment_id(segment: Any) -> str | None:
    return _string_or_none(getattr(segment, "segment_id", None)) or _string_or_none((getattr(segment, "extra", None) or {}).get("segment_id"))


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
