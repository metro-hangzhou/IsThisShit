from __future__ import annotations

from collections import Counter
from typing import Literal

from .models import ExportBundleResult, NormalizedMessage, NormalizedSegment, NormalizedSnapshot

ExportProfile = Literal["all", "only_text", "text_image", "text_image_emoji"]

CONTENT_SEGMENT_ORDER: tuple[str, ...] = (
    "text",
    "system",
    "share",
    "forward",
    "image",
    "video",
    "speech",
    "file",
    "emoji",
    "sticker",
    "reply",
    "unsupported",
)

ASSET_TYPE_ORDER: tuple[str, ...] = (
    "image",
    "video",
    "speech",
    "file",
    "sticker.static",
    "sticker.dynamic",
    "sticker",
)

PROFILE_SEGMENT_TYPES: dict[ExportProfile, set[str] | None] = {
    "all": None,
    "only_text": {"text", "system", "share", "forward"},
    "text_image": {"text", "system", "share", "forward", "image"},
    "text_image_emoji": {"text", "system", "share", "forward", "image", "emoji", "sticker"},
}


def apply_export_profile(snapshot: NormalizedSnapshot, profile: ExportProfile) -> NormalizedSnapshot:
    allowed = PROFILE_SEGMENT_TYPES[profile]
    if allowed is None:
        return snapshot

    source_message_count = len(snapshot.messages)
    filtered_messages: list[NormalizedMessage] = []
    dropped_messages = 0
    for message in snapshot.messages:
        segments = [segment.model_copy(deep=True) for segment in message.segments if segment.type in allowed]
        rebuilt = _rebuild_message(message, segments)
        if rebuilt is None:
            dropped_messages += 1
            continue
        filtered_messages.append(rebuilt)

    metadata = dict(snapshot.metadata)
    metadata["export_profile"] = profile
    metadata["source_message_count"] = source_message_count
    metadata["dropped_message_count"] = dropped_messages
    metadata["kept_message_count"] = len(filtered_messages)
    return snapshot.model_copy(update={"messages": filtered_messages, "metadata": metadata})


def trim_snapshot_to_last_messages(
    snapshot: NormalizedSnapshot,
    *,
    data_count: int | None,
):
    if data_count is None or data_count <= 0:
        return snapshot
    messages = list(snapshot.messages)
    trimmed_messages = messages[-data_count:]
    metadata = dict(snapshot.metadata)
    metadata["requested_data_count"] = data_count
    metadata["source_message_count"] = len(messages)
    metadata["trimmed_message_count"] = len(trimmed_messages)
    return snapshot.model_copy(update={"messages": trimmed_messages, "metadata": metadata})


def build_export_content_summary(
    snapshot: NormalizedSnapshot,
    bundle: ExportBundleResult,
    *,
    profile: ExportProfile,
) -> dict[str, object]:
    segment_counts = Counter()
    expected_assets = Counter()
    actual_assets = Counter()
    missing_assets = Counter()
    error_assets = Counter()
    missing_breakdown = Counter()

    for message in snapshot.messages:
        for segment in message.segments:
            segment_counts[segment.type] += 1
            for asset_key in _collect_segment_asset_keys(segment):
                expected_assets[asset_key] += 1

    for asset in bundle.assets:
        key = _asset_key(asset.asset_type, asset.asset_role)
        if asset.status in {"copied", "reused"}:
            actual_assets[key] += 1
        elif asset.status == "missing":
            missing_assets[key] += 1
            missing_breakdown[str(asset.resolver or "missing")] += 1
        elif asset.status == "error":
            error_assets[key] += 1

    for segment_type in CONTENT_SEGMENT_ORDER:
        segment_counts.setdefault(segment_type, 0)
    for asset_key in ASSET_TYPE_ORDER:
        expected_assets.setdefault(asset_key, 0)
        actual_assets.setdefault(asset_key, 0)
        missing_assets.setdefault(asset_key, 0)
        error_assets.setdefault(asset_key, 0)

    oldest_timestamp_iso = snapshot.messages[0].timestamp_iso if snapshot.messages else None
    latest_timestamp_iso = snapshot.messages[-1].timestamp_iso if snapshot.messages else None

    return {
        "profile": profile,
        "message_count": len(snapshot.messages),
        "source_message_count": int(snapshot.metadata.get("source_message_count") or len(snapshot.messages)),
        "requested_data_count": snapshot.metadata.get("requested_data_count"),
        "oldest_timestamp_iso": oldest_timestamp_iso,
        "latest_timestamp_iso": latest_timestamp_iso,
        "segment_counts": {key: int(segment_counts[key]) for key in CONTENT_SEGMENT_ORDER},
        "expected_assets": {key: int(expected_assets[key]) for key in ASSET_TYPE_ORDER},
        "actual_assets": {key: int(actual_assets[key]) for key in ASSET_TYPE_ORDER},
        "missing_assets": {key: int(missing_assets[key]) for key in ASSET_TYPE_ORDER},
        "error_assets": {key: int(error_assets[key]) for key in ASSET_TYPE_ORDER},
        "missing_breakdown": dict(sorted((str(key), int(value)) for key, value in missing_breakdown.items())),
    }


def format_export_content_summary(summary: dict[str, object]) -> list[str]:
    content_counts = summary.get("segment_counts") or {}
    expected_assets = summary.get("expected_assets") or {}
    actual_assets = summary.get("actual_assets") or {}
    missing_assets = summary.get("missing_assets") or {}
    error_assets = summary.get("error_assets") or {}
    missing_breakdown = summary.get("missing_breakdown") or {}

    lines = [
        "export_summary:",
        (
            f"  profile={summary['profile']} "
            f"msgs={summary['message_count']} "
            f"source_msgs={summary['source_message_count']} "
            f"requested_data_count={summary.get('requested_data_count') or '-'}"
        ),
    ]
    if summary.get("oldest_timestamp_iso") and summary.get("latest_timestamp_iso"):
        lines.append(
            f"  time_range={summary['oldest_timestamp_iso']} -> {summary['latest_timestamp_iso']}"
        )
    lines.append(
        "  content_export=["
        + ", ".join(
            f"{key}:{int(content_counts.get(key, 0))}/{int(content_counts.get(key, 0))}"
            for key in CONTENT_SEGMENT_ORDER
        )
        + "]"
    )
    lines.append(
        "  asset_materialization=["
        + ", ".join(
            (
                f"{key}:{int(actual_assets.get(key, 0))}/{int(expected_assets.get(key, 0))}"
                f" miss={int(missing_assets.get(key, 0))}"
                f" err={int(error_assets.get(key, 0))}"
            )
            for key in ASSET_TYPE_ORDER
        )
        + "]"
    )
    if missing_breakdown:
        lines.append(
            "  missing_breakdown=["
            + ", ".join(
                f"{key}:{int(value)}"
                for key, value in missing_breakdown.items()
            )
            + "]"
        )
    return lines


def format_missing_breakdown_compact(summary: dict[str, object]) -> str:
    missing_breakdown = summary.get("missing_breakdown") or {}
    if not missing_breakdown:
        return "-"
    return ", ".join(
        f"{key}:{int(value)}"
        for key, value in missing_breakdown.items()
    )


def format_export_content_summary_compact(summary: dict[str, object]) -> str:
    message_count = summary.get("message_count")
    source_message_count = summary.get("source_message_count")
    requested_data_count = summary.get("requested_data_count") or "-"
    segment_counts = summary.get("segment_counts") or {}
    expected_assets = summary.get("expected_assets") or {}
    actual_assets = summary.get("actual_assets") or {}
    missing_assets = summary.get("missing_assets") or {}
    error_assets = summary.get("error_assets") or {}
    missing_breakdown = summary.get("missing_breakdown") or {}

    segment_type_count = len(segment_counts)
    expected_total = sum(int(value) for value in expected_assets.values())
    actual_total = sum(int(value) for value in actual_assets.values())
    missing_total = sum(int(value) for value in missing_assets.values())
    error_total = sum(int(value) for value in error_assets.values())
    expired_total = int(missing_breakdown.get("qq_expired_after_napcat") or 0)

    return (
        "summary "
        f"profile={summary['profile']} "
        f"msgs={message_count}/{source_message_count} "
        f"req={requested_data_count} "
        f"segment_types={segment_type_count} "
        f"assets={actual_total}/{expected_total} "
        f"missing={missing_total} "
        f"expired={expired_total} "
        f"errors={error_total}"
    )


def format_watch_export_result_summary(summary: dict[str, object]) -> str:
    message_count = summary.get("message_count")
    source_message_count = summary.get("source_message_count")
    requested_data_count = summary.get("requested_data_count") or "-"
    expected_assets = summary.get("expected_assets") or {}
    actual_assets = summary.get("actual_assets") or {}
    missing_assets = summary.get("missing_assets") or {}
    missing_breakdown = summary.get("missing_breakdown") or {}

    expected_total = sum(int(value) for value in expected_assets.values())
    actual_total = sum(int(value) for value in actual_assets.values())
    missing_total = sum(int(value) for value in missing_assets.values())
    expired_total = int(missing_breakdown.get("qq_expired_after_napcat") or 0)

    return (
        f"m={message_count}/{source_message_count} "
        f"req={requested_data_count} "
        f"a={actual_total}/{expected_total} "
        f"miss={missing_total} "
        f"expired={expired_total}"
    )


def _rebuild_message(message: NormalizedMessage, segments: list[NormalizedSegment]) -> NormalizedMessage | None:
    if not segments:
        return None

    content_parts: list[str] = []
    text_parts: list[str] = []
    image_file_names: list[str] = []
    uploaded_file_names: list[str] = []
    emoji_tokens: list[str] = []

    for segment in segments:
        token = _segment_content_token(segment)
        if token:
            content_parts.append(token)
        text_value = _segment_text_value(segment)
        if text_value:
            text_parts.append(text_value)
        if segment.type == "image" and segment.file_name:
            image_file_names.append(segment.file_name)
        if segment.type == "file" and segment.file_name:
            uploaded_file_names.append(segment.file_name)
        if segment.type in {"emoji", "sticker"} and (segment.token or token):
            emoji_tokens.append(segment.token or token)

    content = " ".join(part for part in content_parts if part).strip()
    if not content:
        return None
    text_content = "".join(text_parts).strip()
    return message.model_copy(
        update={
            "segments": segments,
            "content": content,
            "text_content": text_content,
            "image_file_names": image_file_names,
            "uploaded_file_names": uploaded_file_names,
            "emoji_tokens": emoji_tokens,
        }
    )


def _segment_content_token(segment: NormalizedSegment) -> str:
    if segment.type == "text":
        return segment.text or ""
    if segment.type == "system":
        return segment.text or segment.summary or segment.token or "[system message]"
    if segment.token:
        return segment.token
    if segment.type == "image":
        return f"[image:{segment.file_name or 'image.jpg'}]"
    if segment.type == "file":
        return f"[uploaded_file_name:{segment.file_name or 'uploaded_file'}]"
    if segment.type == "speech":
        return "[speech audio]"
    if segment.type == "video":
        return f"[video:{segment.file_name or 'video'}]"
    if segment.type == "emoji":
        return f"[emoji:id={segment.emoji_id or '?'}]"
    if segment.type == "sticker":
        return segment.summary or "[sticker]"
    if segment.type == "forward":
        preview_text = _segment_text_value(segment)
        return " ".join(part for part in [FORWARD_FALLBACK_TOKEN, preview_text] if part).strip()
    if segment.type == "share":
        summary = _segment_text_value(segment)
        token = f"[share:{segment.summary or '分享卡片'}]"
        return " ".join(part for part in [token, summary] if part).strip()
    if segment.type == "unsupported":
        return segment.token or "[unsupported]"
    return ""


FORWARD_FALLBACK_TOKEN = "[forward message]"


def _segment_text_value(segment: NormalizedSegment) -> str:
    if segment.type in {"text", "system"}:
        return (segment.text or "").strip()
    if segment.type == "forward":
        return str(segment.extra.get("preview_text") or segment.summary or "").strip()
    if segment.type == "share":
        parts = [
            segment.summary,
            str(segment.extra.get("desc") or "").strip() or None,
            str(segment.extra.get("tag") or "").strip() or None,
        ]
        return " ".join(part for part in parts if part).strip()
    return ""


def _segment_asset_keys(segment: NormalizedSegment) -> list[str]:
    if segment.type == "image":
        return ["image"]
    if segment.type == "file":
        return ["file"]
    if segment.type == "speech":
        return ["speech"]
    if segment.type == "video":
        return ["video"]
    if segment.type == "sticker":
        keys: list[str] = []
        static_path = str(segment.extra.get("static_path") or "").strip()
        dynamic_path = str(segment.extra.get("dynamic_path") or "").strip()
        if static_path:
            keys.append("sticker.static")
        if dynamic_path:
            keys.append("sticker.dynamic")
        if segment.path:
            keys.append("sticker")
        return keys
    return []


def _collect_segment_asset_keys(segment: NormalizedSegment) -> list[str]:
    keys = list(_segment_asset_keys(segment))
    if segment.type != "forward":
        return keys

    forward_messages = segment.extra.get("forward_messages")
    if not isinstance(forward_messages, list):
        return keys

    for forwarded in forward_messages:
        if not isinstance(forwarded, dict):
            continue
        for child in forwarded.get("segments") or []:
            try:
                normalized_child = (
                    child if isinstance(child, NormalizedSegment) else NormalizedSegment.model_validate(child)
                )
            except Exception:
                continue
            keys.extend(_collect_segment_asset_keys(normalized_child))
    return keys


def _asset_key(asset_type: str, asset_role: str | None) -> str:
    if asset_role:
        return f"{asset_type}.{asset_role}"
    return asset_type


def _format_counter(value: object) -> str:
    counter = value if isinstance(value, dict) else {}
    if not counter:
        return "-"
    return ", ".join(f"{key}={counter[key]}" for key in sorted(counter))
