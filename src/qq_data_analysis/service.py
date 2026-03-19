from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents import build_default_agent_registry
from .benshi_pack import build_benshi_analysis_pack
from .compact import dump_compact_json, load_compact_json
from .models import AnalysisJobConfig, AnalysisMaterials, AnalysisRunResult, BenshiAnalysisPack
from .substrate import AnalysisSubstrate
from .interfaces import AnalysisRuntimeInput
from qq_data_process.preprocess_models import (
    PreprocessAnnotation,
    PreprocessDirective,
    PreprocessViewContext,
    ProcessedMessageView,
    ProcessedThreadView,
)
from qq_data_process.preprocess_service import load_preprocess_view


class AnalysisService:
    def __init__(
        self,
        *,
        substrate: AnalysisSubstrate,
        agent_registry: dict[str, object] | None = None,
    ) -> None:
        self.substrate = substrate
        self.agent_registry = agent_registry or build_default_agent_registry()

    @classmethod
    def from_state(
        cls,
        *,
        sqlite_path: Path,
        qdrant_path: Path,
    ) -> "AnalysisService":
        return cls(
            substrate=AnalysisSubstrate(
                sqlite_path=sqlite_path,
                qdrant_path=qdrant_path,
            )
        )

    def run(
        self,
        config: AnalysisJobConfig,
        *,
        analysis_input: AnalysisRuntimeInput | None = None,
    ) -> AnalysisRunResult:
        materials = self.substrate.build_materials(
            config,
            analysis_input=analysis_input,
        )
        if analysis_input is not None:
            materials = _apply_analysis_input_to_materials(materials, analysis_input)
        outputs = []
        warnings = list(materials.warnings)

        for agent_name in config.agent_names:
            agent = self.agent_registry.get(agent_name)
            if agent is None:
                raise RuntimeError(f"Unknown analysis agent: {agent_name}")
            prepared = agent.prepare(materials)
            output = agent.analyze(materials, prepared)
            outputs.append(output)
            warnings.extend(output.warnings)

        summary_report = "\n\n".join(output.human_report for output in outputs)
        compact_payload = {
            "rid": materials.run_id,
            "t": {
                "tt": materials.target.target_type,
                "id": materials.target.display_id,
                "nm": materials.target.display_name,
            },
            "win": {
                "m": materials.chosen_time_window.mode,
                "s": materials.chosen_time_window.start_timestamp_ms,
                "e": materials.chosen_time_window.end_timestamp_ms,
                "si": materials.chosen_time_window.start_timestamp_iso,
                "ei": materials.chosen_time_window.end_timestamp_iso,
                "why": materials.chosen_time_window.rationale,
                "n": materials.chosen_time_window.selected_message_count,
            },
            "ags": [
                {
                    "n": output.agent_name,
                    "v": output.agent_version,
                    "d": output.compact_payload,
                }
                for output in outputs
            ],
        }

        return AnalysisRunResult(
            run_id=materials.run_id,
            target=materials.target,
            chosen_time_window=materials.chosen_time_window,
            agent_outputs=outputs,
            summary_report=summary_report,
            compact_machine_output=dump_compact_json(compact_payload),
            warnings=warnings,
            input_context=dict(materials.input_context),
        )

    def close(self) -> None:
        self.substrate.close()

    def build_materials(
        self,
        config: AnalysisJobConfig,
        *,
        analysis_input: AnalysisRuntimeInput | None = None,
    ) -> AnalysisMaterials:
        materials = self.substrate.build_materials(
            config,
            analysis_input=analysis_input,
        )
        if analysis_input is None:
            return materials
        return _apply_analysis_input_to_materials(materials, analysis_input)

    def build_benshi_pack(
        self,
        config: AnalysisJobConfig,
        *,
        analysis_input: AnalysisRuntimeInput | None = None,
    ) -> BenshiAnalysisPack:
        materials = self.build_materials(
            config,
            analysis_input=analysis_input,
        )
        return build_benshi_analysis_pack(materials)


def load_analysis_input(
    *,
    preprocess_view_path: str | Path | None = None,
    raw_context: AnalysisRuntimeInput | None = None,
    preprocess_view: PreprocessViewContext | None = None,
) -> AnalysisRuntimeInput:
    provided = sum(
        1
        for item in (preprocess_view_path, raw_context, preprocess_view)
        if item is not None
    )
    if provided != 1:
        raise ValueError(
            "Provide exactly one of preprocess_view_path, raw_context, or preprocess_view."
        )
    if preprocess_view is not None:
        return preprocess_view
    if raw_context is not None:
        return raw_context
    assert preprocess_view_path is not None
    return load_preprocess_view(preprocess_view_path)


def run_analysis(
    config: AnalysisJobConfig,
    *,
    service: AnalysisService | None = None,
    sqlite_path: Path | None = None,
    qdrant_path: Path | None = None,
    analysis_input: AnalysisRuntimeInput | None = None,
) -> AnalysisRunResult:
    resolved_service = service
    if resolved_service is None:
        if sqlite_path is None or qdrant_path is None:
            raise ValueError(
                "Provide an AnalysisService instance or both sqlite_path and qdrant_path."
            )
        resolved_service = AnalysisService.from_state(
            sqlite_path=sqlite_path,
            qdrant_path=qdrant_path,
        )
    result = resolved_service.run(config, analysis_input=analysis_input)
    if analysis_input is None:
        return result
    return _decorate_result_with_input_metadata(result, analysis_input)


def build_benshi_pack(
    config: AnalysisJobConfig,
    *,
    service: AnalysisService | None = None,
    sqlite_path: Path | None = None,
    qdrant_path: Path | None = None,
    analysis_input: AnalysisRuntimeInput | None = None,
) -> BenshiAnalysisPack:
    resolved_service = service
    if resolved_service is None:
        if sqlite_path is None or qdrant_path is None:
            raise ValueError(
                "Provide an AnalysisService instance or both sqlite_path and qdrant_path."
            )
        resolved_service = AnalysisService.from_state(
            sqlite_path=sqlite_path,
            qdrant_path=qdrant_path,
        )
    return resolved_service.build_benshi_pack(
        config,
        analysis_input=analysis_input,
    )


def _decorate_result_with_input_metadata(
    result: AnalysisRunResult,
    analysis_input: AnalysisRuntimeInput,
) -> AnalysisRunResult:
    input_payload = _analysis_input_payload(analysis_input)
    merged_input_context = {
        **(result.input_context or {}),
        "analysis_input": input_payload,
    }
    warnings = list(result.warnings)
    input_warning = (
        "analysis_input="
        f"{input_payload['input_kind']}:{input_payload.get('context_id') or input_payload.get('corpus_id')}"
    )
    if input_warning not in warnings:
        warnings.append(input_warning)
    compact_payload = load_compact_json(result.compact_machine_output)
    compact_payload["input_context"] = merged_input_context
    return result.model_copy(
        update={
            "warnings": warnings,
            "compact_machine_output": dump_compact_json(compact_payload),
            "input_context": merged_input_context,
        }
    )


def _apply_analysis_input_to_materials(materials: Any, analysis_input: AnalysisRuntimeInput) -> Any:
    input_payload = _analysis_input_payload(analysis_input)
    warnings = list(materials.warnings)
    warnings.append(
        "analysis_input="
        f"{input_payload['input_kind']}:{input_payload.get('context_id') or input_payload.get('corpus_id')}"
    )
    merged_input_context = {
        **(materials.input_context or {}),
        **input_payload,
    }
    updated = materials.model_copy(
        update={
            "warnings": warnings,
            "input_context": merged_input_context,
        },
        deep=True,
    )
    if isinstance(analysis_input, PreprocessViewContext):
        _validate_preprocess_target(updated, analysis_input)
        return _overlay_preprocess_view(updated, analysis_input)
    return updated


def _validate_preprocess_target(materials: Any, preprocess_view: PreprocessViewContext) -> None:
    manifest = preprocess_view.manifest
    expected_chat_type = "group" if materials.target.target_type == "group" else "friend"
    expected_chat_id = str(materials.target.display_id)
    candidate_ids = {
        str(expected_chat_id),
        str(materials.target.alias_id),
        str(materials.target.raw_id),
    }
    if str(manifest.chat_type) != str(expected_chat_type):
        raise RuntimeError(
            "Preprocess view target type does not match analysis target: "
            f"{manifest.chat_type!r} != {expected_chat_type!r}"
        )
    if str(manifest.chat_id) not in candidate_ids:
        raise RuntimeError(
            "Preprocess view chat id does not match analysis target: "
            f"{manifest.chat_id!r} not in {sorted(candidate_ids)!r}"
        )


def _overlay_preprocess_view(materials: Any, preprocess_view: PreprocessViewContext) -> Any:
    message_by_uid = {message.message_uid: message for message in materials.messages}
    message_by_message_id = {
        str(message.message_id): message
        for message in materials.messages
        if message.message_id is not None
    }
    annotations_by_message_id = _annotations_by_message_id(preprocess_view.annotations)
    thread_views_by_message_id = _thread_views_by_message_id(preprocess_view.thread_views)
    touched = 0

    for view in preprocess_view.message_views:
        message = _resolve_target_message(
            view=view,
            message_by_uid=message_by_uid,
            message_by_message_id=message_by_message_id,
        )
        if message is None:
            continue
        preprocess_payload = _merge_preprocess_payload(
            current=message.extra.get("preprocess"),
            view=view,
            annotations=annotations_by_message_id.get(str(view.message_id or ""), []),
            thread_views=thread_views_by_message_id.get(str(view.message_id or ""), []),
        )
        extra = dict(message.extra)
        extra["delivery_profile"] = preprocess_view.manifest.delivery_profile
        extra["preprocess_view_id"] = preprocess_view.manifest.view_id
        extra["preprocess"] = preprocess_payload
        extra["preprocess_labels"] = list(preprocess_payload.get("labels") or [])
        extra["source_message_ids"] = list(preprocess_payload.get("source_message_ids") or [])
        extra["source_thread_ids"] = list(preprocess_payload.get("source_thread_ids") or [])
        if preprocess_payload.get("raw_text") is not None:
            extra["raw_text"] = preprocess_payload["raw_text"]
        if preprocess_payload.get("processed_text"):
            extra["processed_text"] = preprocess_payload["processed_text"]
        if preprocess_payload.get("decision_summary"):
            extra["decision_summary"] = preprocess_payload["decision_summary"]
        updated_message = message.model_copy(update={"extra": extra}, deep=True)
        _replace_material_message(materials, updated_message)
        message_by_uid[updated_message.message_uid] = updated_message
        if updated_message.message_id is not None:
            message_by_message_id[str(updated_message.message_id)] = updated_message
        touched += 1

    input_context = dict(materials.input_context)
    input_context["preprocess_overlay"] = {
        "view_id": preprocess_view.manifest.view_id,
        "delivery_profile": preprocess_view.manifest.delivery_profile,
        "processed_message_view_count": len(preprocess_view.message_views),
        "processed_thread_view_count": len(preprocess_view.thread_views),
        "processed_asset_view_count": len(preprocess_view.asset_views),
        "annotation_count": len(preprocess_view.annotations),
        "overlayed_message_count": touched,
        "directive": _directive_payload(
            preprocess_view.directive or preprocess_view.manifest.directive
        ),
        "top_annotation_labels": _top_annotation_labels(preprocess_view.annotations),
    }
    warnings = list(materials.warnings)
    warnings.append(
        "Applied preprocess overlay "
        f"{preprocess_view.manifest.view_id} "
        f"({preprocess_view.manifest.delivery_profile}) to {touched} messages."
    )
    return materials.model_copy(
        update={
            "warnings": warnings,
            "input_context": input_context,
        },
        deep=True,
    )


def _replace_material_message(materials: Any, replacement: Any) -> None:
    for index, message in enumerate(materials.messages):
        if message.message_uid == replacement.message_uid:
            materials.messages[index] = replacement
            return


def _resolve_target_message(
    *,
    view: ProcessedMessageView,
    message_by_uid: dict[str, Any],
    message_by_message_id: dict[str, Any],
) -> Any | None:
    if view.message_id is not None:
        matched = message_by_message_id.get(str(view.message_id))
        if matched is not None:
            return matched
    for source_id in view.source_message_ids:
        matched = message_by_uid.get(str(source_id)) or message_by_message_id.get(str(source_id))
        if matched is not None:
            return matched
    return None


def _annotations_by_message_id(
    annotations: list[PreprocessAnnotation],
) -> dict[str, list[PreprocessAnnotation]]:
    grouped: dict[str, list[PreprocessAnnotation]] = {}
    for annotation in annotations:
        for message_id in annotation.source_message_ids:
            grouped.setdefault(str(message_id), []).append(annotation)
    return grouped


def _thread_views_by_message_id(
    thread_views: list[ProcessedThreadView],
) -> dict[str, list[ProcessedThreadView]]:
    grouped: dict[str, list[ProcessedThreadView]] = {}
    for view in thread_views:
        for message_id in view.source_message_ids:
            grouped.setdefault(str(message_id), []).append(view)
    return grouped


def _merge_preprocess_payload(
    *,
    current: Any,
    view: ProcessedMessageView,
    annotations: list[PreprocessAnnotation],
    thread_views: list[ProcessedThreadView],
) -> dict[str, Any]:
    current_payload = dict(current) if isinstance(current, dict) else {}
    thread_view_summaries = [
        {
            "processed_thread_id": item.processed_thread_id,
            "thread_id": item.thread_id,
            "summary": item.summary,
            "decision_summary": item.decision_summary,
            "delivery_profile": item.delivery_profile,
            "labels": list(item.labels),
            "source_message_ids": list(item.source_message_ids),
            "source_asset_ids": list(item.source_asset_ids),
            "metadata": _json_ready(item.metadata),
            "source_thread_ids": list(item.annotations[0].source_thread_ids)
            if item.annotations
            else [],
        }
        for item in thread_views
    ]
    annotation_summaries = [
        {
            "annotation_id": item.annotation_id,
            "label": item.label,
            "summary": item.summary,
            "decision_summary": item.decision_summary,
            "confidence": item.confidence,
            "source_message_ids": list(item.source_message_ids),
            "source_asset_ids": list(item.source_asset_ids),
            "source_thread_ids": list(item.source_thread_ids),
            "target_ids": list(item.target_ids),
            "tags": list(item.tags),
            "metadata": _json_ready(item.metadata),
        }
        for item in annotations
    ]
    payload = {
        **current_payload,
        "view_id": view.view_id,
        "processed_message_id": view.processed_message_id,
        "delivery_profile": view.delivery_profile,
        "operation_type": view.operation_type,
        "raw_text": view.raw_text,
        "processed_text": view.processed_text,
        "summary": view.summary,
        "decision_summary": view.decision_summary,
        "confidence": view.confidence,
        "suppressed": view.suppressed,
        "labels": list(view.labels),
        "metadata": _json_ready(view.metadata),
        "source_message_ids": list(view.source_message_ids),
        "source_asset_ids": list(view.source_asset_ids),
        "annotations": annotation_summaries,
        "thread_views": thread_view_summaries,
    }
    return payload


def _analysis_input_payload(analysis_input: AnalysisRuntimeInput) -> dict[str, Any]:
    manifest = getattr(analysis_input, "manifest", None)
    if manifest is not None and hasattr(manifest, "view_id"):
        return {
            "input_kind": "preprocess_view",
            "view_id": getattr(manifest, "view_id", None),
            "context_id": getattr(analysis_input, "context_id", None),
            "corpus_id": getattr(manifest, "corpus_id", None),
            "delivery_profile": getattr(manifest, "delivery_profile", None),
            "processed_message_count": len(getattr(analysis_input, "message_views", []) or []),
            "processed_thread_count": len(getattr(analysis_input, "thread_views", []) or []),
            "processed_asset_count": len(getattr(analysis_input, "asset_views", []) or []),
            "annotation_count": len(getattr(analysis_input, "annotations", []) or []),
            "directive": _directive_payload(
                getattr(analysis_input, "directive", None)
                or getattr(manifest, "directive", None)
            ),
            "lineage": _json_ready(
                getattr(analysis_input, "lineage", None) or getattr(manifest, "lineage", None)
            ),
            "provenance": _json_ready(
                getattr(analysis_input, "provenance", None) or getattr(manifest, "provenance", None)
            ),
            "metadata": _json_ready(getattr(analysis_input, "metadata", None) or {}),
        }
    return {
        "input_kind": "raw_corpus",
        "context_id": getattr(analysis_input, "context_id", None),
        "corpus_id": getattr(manifest, "corpus_id", None) or getattr(analysis_input, "chat_id", None),
        "lineage": _json_ready(
            getattr(analysis_input, "lineage", None)
            or getattr(manifest, "lineage", None)
            or {
                "source_chat_id": getattr(analysis_input, "chat_id", None),
            }
        ),
        "provenance": _json_ready(
            getattr(analysis_input, "provenance", None)
            or getattr(manifest, "provenance", None)
            or {
                "source_type": getattr(analysis_input, "source_type", None),
                "source_path": str(getattr(analysis_input, "source_path", "")) or None,
            }
        ),
        "metadata": _json_ready(getattr(analysis_input, "metadata", None) or {}),
    }


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _json_ready(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def _directive_payload(
    directive: PreprocessDirective | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if directive is None:
        return None
    if isinstance(directive, PreprocessDirective):
        return _json_ready(directive.model_dump(mode="json"))
    if isinstance(directive, dict):
        return _json_ready(dict(directive))
    return None


def _top_annotation_labels(annotations: list[PreprocessAnnotation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for annotation in annotations:
        label = str(annotation.label or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8])
