from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from ..interfaces import AnalyzerContext, DeterministicAnalyzer
from ..models import AnalysisEvidenceRef, DeterministicResult


class AssetRecurrencePreprocessor(DeterministicAnalyzer):
    plugin_id = "asset_recurrence_preprocessor"
    plugin_version = "0.1.0"
    scope_level = "asset"
    supported_modalities = ("image", "gif", "video", "audio", "file", "sticker")
    requires = ()
    produces = ("asset_recurrence_clusters",)

    def run(self, context: AnalyzerContext) -> list[DeterministicResult]:
        assets = list(getattr(context.corpus, "assets", []) or [])
        grouped: dict[str, list[Any]] = defaultdict(list)
        basis_by_key: dict[str, str] = {}

        for asset in assets:
            recurrence_key, basis = _build_recurrence_key(asset)
            if recurrence_key is None or basis is None:
                continue
            grouped[recurrence_key].append(asset)
            basis_by_key[recurrence_key] = basis

        results: list[DeterministicResult] = []
        for recurrence_key, assets in sorted(grouped.items()):
            if len(assets) < 2:
                continue
            basis = basis_by_key[recurrence_key]
            results.append(_cluster_result(recurrence_key=recurrence_key, basis=basis, assets=assets))

        if results:
            return results
        return [
            DeterministicResult(
                plugin_id=self.plugin_id,
                plugin_version=self.plugin_version,
                status="info",
                summary="No conservative asset recurrence clusters were detected.",
                confidence=1.0,
                tags=["recurrence", "asset", "none"],
                verdict="no_clusters",
                details={"asset_count": len(assets)},
            )
        ]


def _build_recurrence_key(asset: Any) -> tuple[str | None, str | None]:
    asset_type = str(getattr(asset, "asset_type", "") or "").strip().lower()
    file_name = (getattr(asset, "file_name", None) or "").strip().lower()
    digest = (getattr(asset, "digest", None) or "").strip().lower()
    exported_rel_path = (getattr(asset, "exported_rel_path", None) or "").strip().lower()
    source_path = (getattr(asset, "source_path", None) or "").strip().lower()

    if digest and file_name:
        return (f"digest_file:{asset_type}:{digest}:{file_name}", "digest+file_name")
    if digest:
        return (f"digest:{asset_type}:{digest}", "digest")
    if exported_rel_path and file_name:
        return (f"exported_rel_path:{asset_type}:{exported_rel_path}:{file_name}", "exported_rel_path+file_name")
    if source_path and file_name:
        return (f"source_path:{asset_type}:{source_path}:{file_name}", "source_path+file_name")
    if file_name:
        return (f"file_name:{asset_type}:{file_name}", "file_name_only")
    return (None, None)


def _cluster_result(*, recurrence_key: str, basis: str, assets: Iterable[Any]) -> DeterministicResult:
    asset_list = list(assets)
    first = asset_list[0]
    confidence = _basis_confidence(basis)
    message_ids = [asset.message_id for asset in asset_list if getattr(asset, "message_id", None)]
    asset_ids = [asset.asset_id for asset in asset_list if getattr(asset, "asset_id", None)]
    resource_states = Counter(
        str(getattr(asset, "resource_state", None) or "unknown") for asset in asset_list
    )
    statuses = Counter(
        str(getattr(asset, "materialization_status", None) or "unknown") for asset in asset_list
    )
    distinct_chat_ids = sorted(
        {
            str(getattr(asset.lineage, "source_chat_id", None) or getattr(asset.lineage, "export_chat_id", None))
            for asset in asset_list
            if getattr(asset, "lineage", None) is not None
            and (getattr(asset.lineage, "source_chat_id", None) or getattr(asset.lineage, "export_chat_id", None))
        }
    )

    return DeterministicResult(
        plugin_id=AssetRecurrencePreprocessor.plugin_id,
        plugin_version=AssetRecurrencePreprocessor.plugin_version,
        status="resolved",
        summary=f"Detected {len(asset_list)} conservative recurrence occurrences for {first.file_name or first.asset_id}.",
        confidence=confidence,
        tags=["preprocess", "asset_recurrence", basis],
        verdict="clustered",
        details={
            "recurrence_key": recurrence_key,
            "basis": basis,
            "operation_type": "group",
            "scope_level": "asset",
            "view_kind": "repost_view",
            "asset_type": first.asset_type,
            "file_name": first.file_name,
            "occurrence_count": len(asset_list),
            "asset_ids": asset_ids,
            "message_ids": message_ids,
            "distinct_chat_ids": distinct_chat_ids,
            "resource_state_counts": dict(resource_states),
            "materialization_status_counts": dict(statuses),
            "exported_rel_paths": sorted(
                {
                    str(getattr(asset, "exported_rel_path", None))
                    for asset in asset_list
                    if getattr(asset, "exported_rel_path", None)
                }
            ),
            "source_paths": sorted(
                {
                    str(getattr(asset, "source_path", None))
                    for asset in asset_list
                    if getattr(asset, "source_path", None)
                }
            ),
            "digests": sorted(
                {
                    str(getattr(asset, "digest", None))
                    for asset in asset_list
                    if getattr(asset, "digest", None)
                }
            ),
            "source_asset_keys": sorted(
                {
                    str(getattr(asset.lineage, "source_asset_key", None))
                    for asset in asset_list
                    if getattr(asset, "lineage", None) is not None and getattr(asset.lineage, "source_asset_key", None)
                }
            ),
        },
        evidence_refs=[
            AnalysisEvidenceRef(
                kind="asset",
                asset_id=asset.asset_id,
                message_id=asset.message_id,
                note=(
                    f"basis={basis}; resource_state={getattr(asset, 'resource_state', None)}; "
                    f"materialization={getattr(asset, 'materialization_status', None)}"
                ),
            )
            for asset in asset_list[:16]
        ],
        notes=[
            "This preprocessor only reports clusters when the recurrence key is conservative.",
            "The result is derived metadata and does not rewrite any source asset records.",
        ],
    )


def _basis_confidence(basis: str) -> float:
    if basis == "digest+file_name":
        return 0.98
    if basis == "digest":
        return 0.95
    if basis in {"exported_rel_path+file_name", "source_path+file_name"}:
        return 0.82
    if basis == "file_name_only":
        return 0.45
    return 0.25
