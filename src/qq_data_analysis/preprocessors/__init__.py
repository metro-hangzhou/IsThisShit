from __future__ import annotations

from typing import Any

__all__ = [
    "ThreadCompactionPreprocessor",
    "TopicWindowBuilder",
    "AssetRecurrencePreprocessor",
    "ForwardBundleExpander",
    "ExpiredAssetInferencePreprocessor",
    "ContextFilterPreprocessor",
    "available_preprocessor_factories",
    "build_preprocessor_plugins",
]


try:
    from .thread_compaction import ThreadCompactionPreprocessor
except Exception:
    ThreadCompactionPreprocessor = None  # type: ignore[assignment]

try:
    from .topic_windows import TopicWindowBuilder
except Exception:
    TopicWindowBuilder = None  # type: ignore[assignment]

try:
    from .asset_recurrence import AssetRecurrencePreprocessor
except Exception:
    AssetRecurrencePreprocessor = None  # type: ignore[assignment]

try:
    from .forward_expansion import ForwardBundleExpander
except Exception:
    ForwardBundleExpander = None  # type: ignore[assignment]

try:
    from .expired_asset_inference import ExpiredAssetInferencePreprocessor
except Exception:
    ExpiredAssetInferencePreprocessor = None  # type: ignore[assignment]

try:
    from .context_filter import ContextFilterPreprocessor
except Exception:
    ContextFilterPreprocessor = None  # type: ignore[assignment]


def available_preprocessor_factories() -> dict[str, type[Any]]:
    factories: dict[str, type[Any]] = {}
    for candidate in (
        ContextFilterPreprocessor,
        TopicWindowBuilder,
        ThreadCompactionPreprocessor,
        AssetRecurrencePreprocessor,
        ForwardBundleExpander,
        ExpiredAssetInferencePreprocessor,
    ):
        if candidate is None:
            continue
        plugin_id = getattr(candidate, "plugin_id", None)
        if plugin_id:
            factories[str(plugin_id)] = candidate
    return factories


def build_preprocessor_plugins(plugin_ids: list[str] | tuple[str, ...]) -> list[object]:
    factories = available_preprocessor_factories()
    instances: list[object] = []
    for plugin_id in plugin_ids:
        try:
            factory = factories[plugin_id]
        except KeyError as exc:
            raise KeyError(f"Unknown preprocessor plugin: {plugin_id}") from exc
        instances.append(factory())
    return instances
