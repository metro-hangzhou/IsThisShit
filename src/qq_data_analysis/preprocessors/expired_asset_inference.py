from __future__ import annotations

from hashlib import sha1
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, Field

from qq_data_process.preprocess_models import (
    PreprocessAnnotation,
    PreprocessPluginProvenance,
    ProcessedAssetView,
)

from .context_budget import ContextBudgetConfig, ContextBudgetManager

ResourceState = Literal[
    "available",
    "missing",
    "expired",
    "placeholder",
    "unsupported",
]
CorpusLineage = Any

FOCUS_RESOURCE_STATES: set[ResourceState] = {"expired", "missing", "placeholder"}
RequestKind = Literal[
    "initial_window",
    "same_asset",
    "forward_full_bundle",
    "same_sender",
]
FinalStatus = Literal["resolved", "uncertain", "unrecoverable", "info"]


class AnalysisEvidenceRef(BaseModel):
    kind: Literal["message", "asset", "forward_bundle", "annotation"] = "message"
    message_id: str | None = None
    asset_id: str | None = None
    segment_id: str | None = None
    note: str | None = None


class ContextRequest(BaseModel):
    before_messages: int = 0
    after_messages: int = 0
    same_sender_window: int = 0
    same_asset_occurrences: bool = False
    forward_full_bundle: bool = False
    max_additional_messages: int = 0
    notes: str | None = None


class AgentAnalysisResult(BaseModel):
    status: FinalStatus
    confidence: float = 0.0
    need_more_context_to_analysis: bool = False
    requested_context: ContextRequest | None = None
    hypothesis: str | None = None
    evidence_refs: list[AnalysisEvidenceRef] = Field(default_factory=list)
    recommended_followups: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ContextRoundTrace(BaseModel):
    round_index: int
    request_kind: RequestKind
    requested_context: ContextRequest
    granted: bool
    context_message_ids: list[str] = Field(default_factory=list)
    context_asset_ids: list[str] = Field(default_factory=list)
    budget_before: dict[str, Any] = Field(default_factory=dict)
    budget_after: dict[str, Any] = Field(default_factory=dict)
    signal_summary: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class ExpiredAssetInferenceRecord(BaseModel):
    asset_view: ProcessedAssetView
    annotation: PreprocessAnnotation
    agent_result: AgentAnalysisResult
    source_message_ids: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[AnalysisEvidenceRef] = Field(default_factory=list)
    budget_snapshot: dict[str, Any] = Field(default_factory=dict)


class ExpiredAssetInferencePreprocessor:
    plugin_id = "expired_asset_inference_preprocessor"
    plugin_version = "0.2.0"
    scope_level = "asset"
    requires = ()
    produces = ("expired_asset_context_view", "expired_asset_annotations")
    supported_modalities = (
        "image",
        "gif",
        "video",
        "audio",
        "file",
        "forward_bundle",
        "text",
    )

    def __init__(
        self,
        *,
        budget: ContextBudgetConfig | None = None,
        default_before_messages: int = 4,
        default_after_messages: int = 4,
        default_same_sender_window: int = 4,
        min_resolved_signal_chars: int = 80,
        min_uncertain_signal_chars: int = 20,
    ) -> None:
        self.budget = budget or ContextBudgetConfig()
        self.default_before_messages = max(default_before_messages, 0)
        self.default_after_messages = max(default_after_messages, 0)
        self.default_same_sender_window = max(default_same_sender_window, 0)
        self.min_resolved_signal_chars = max(min_resolved_signal_chars, 1)
        self.min_uncertain_signal_chars = max(min_uncertain_signal_chars, 1)

    def run(self, context: Any) -> list[ExpiredAssetInferenceRecord]:
        assets = list(_assets_from_context(context))
        messages = list(_messages_from_context(context))
        if not assets:
            return [self._info_record(context, "No assets available for expired asset inference.")]

        metadata = _context_metadata(context)
        focus_asset_ids = _string_list(metadata.get("focus_asset_ids") or metadata.get("asset_ids"))
        focus_id_set = set(focus_asset_ids)
        candidates = [
            asset
            for asset in assets
            if _resource_state(asset) in FOCUS_RESOURCE_STATES
            and (not focus_id_set or _asset_id(asset) in focus_id_set)
        ]
        if not candidates:
            return [
                self._info_record(
                    context,
                    "No expired, missing, or placeholder assets matched the current preprocessing scope.",
                )
            ]

        view_id = str(getattr(context, "run_id", "") or metadata.get("view_id") or "expired_asset_context")
        records: list[ExpiredAssetInferenceRecord] = []
        for asset in candidates:
            budget = ContextBudgetManager(self.budget)
            records.append(
                self._build_record(
                    context=context,
                    asset=asset,
                    messages=messages,
                    assets=assets,
                    view_id=view_id,
                    budget=budget,
                )
            )
        return records

    def _build_record(
        self,
        *,
        context: Any,
        asset: Any,
        messages: Sequence[Any],
        assets: Sequence[Any],
        view_id: str,
        budget: ContextBudgetManager,
    ) -> ExpiredAssetInferenceRecord:
        source_message = _message_by_id(messages).get(_message_id_from_asset(asset))
        same_asset_occurrences = _collect_same_asset_occurrences(assets, asset)
        base_evidence = _base_evidence(asset, source_message)

        if source_message is None:
            return self._finalize_record(
                context=context,
                asset=asset,
                view_id=view_id,
                status="unrecoverable",
                confidence=0.0,
                hypothesis_text=None,
                decision_summary="The source message for this degraded asset was unavailable, so no contextual inference could be attempted.",
                evidence_refs=base_evidence,
                source_message_ids=[],
                source_asset_ids=_unique_ids([_asset_id(asset)]),
                budget_snapshot=budget.snapshot().model_dump(),
                round_traces=[],
                signal_summary={"reason": "source_message_missing"},
                same_asset_occurrences=same_asset_occurrences,
            )

        round_traces: list[ContextRoundTrace] = []
        aggregate_messages: dict[str, dict[str, str | None]] = {}
        aggregate_asset_ids: set[str] = {_asset_id(asset)} if _asset_id(asset) else set()
        final_status: FinalStatus = "unrecoverable"
        final_confidence = 0.0
        final_hypothesis: str | None = None
        final_signal_summary: dict[str, Any] = {"reason": "no_rounds_executed"}
        final_decision = "No context rounds were executed."

        for round_index, (request_kind, request) in enumerate(self._build_round_plan(), start=1):
            budget_before = budget.snapshot().model_dump()
            context_messages, context_asset_ids, note = self._collect_requested_context(
                asset=asset,
                source_message=source_message,
                messages=messages,
                same_asset_occurrences=same_asset_occurrences,
                request_kind=request_kind,
                request=request,
            )
            new_messages = {
                row["message_id"]: row
                for row in context_messages
                if row.get("message_id") and row["message_id"] not in aggregate_messages
            }
            new_asset_ids = [
                asset_id
                for asset_id in context_asset_ids
                if asset_id and asset_id not in aggregate_asset_ids
            ]
            granted = budget.consume(
                round_cost=1,
                message_cost=len(new_messages),
                asset_ref_cost=len(new_asset_ids),
            )
            if granted:
                aggregate_messages.update(new_messages)
                aggregate_asset_ids.update(new_asset_ids)

            signal_summary = _evaluate_signal_strength(
                asset=asset,
                source_message=source_message,
                aggregate_messages=aggregate_messages,
                same_asset_occurrences=same_asset_occurrences,
                min_resolved_signal_chars=self.min_resolved_signal_chars,
                min_uncertain_signal_chars=self.min_uncertain_signal_chars,
            )
            budget_after = budget.snapshot().model_dump()
            round_traces.append(
                ContextRoundTrace(
                    round_index=round_index,
                    request_kind=request_kind,
                    requested_context=request,
                    granted=granted,
                    context_message_ids=sorted(new_messages),
                    context_asset_ids=sorted(new_asset_ids),
                    budget_before=budget_before,
                    budget_after=budget_after,
                    signal_summary=signal_summary,
                    note=note,
                )
            )

            if not granted:
                final_status = "uncertain" if aggregate_messages else "unrecoverable"
                final_confidence = max(signal_summary.get("confidence", 0.0), 0.2 if aggregate_messages else 0.0)
                final_hypothesis = signal_summary.get("hypothesis_text")
                final_signal_summary = signal_summary | {
                    "budget_exhausted": True,
                    "exhaustion_reasons": budget_after.get("exhaustion_reasons", []),
                }
                final_decision = (
                    "Context request loop terminated because the configured budget was exhausted "
                    "before the requested context could be admitted."
                )
                break

            status = str(signal_summary.get("status") or "unrecoverable")
            final_status = status if status in {"resolved", "uncertain", "unrecoverable"} else "unrecoverable"
            final_confidence = float(signal_summary.get("confidence", 0.0))
            final_hypothesis = signal_summary.get("hypothesis_text")
            final_signal_summary = signal_summary

            if final_status == "resolved":
                final_decision = (
                    "The loop collected enough textual and structural context to produce a context-supported "
                    "inference about the degraded asset without claiming direct media access."
                )
                break
            if final_status == "uncertain":
                final_decision = (
                    "The loop collected partial contextual evidence, but it remained insufficient for a strong "
                    "content inference."
                )
                continue

            final_decision = "Current round added no usable evidence for contextual inference."
            if budget.snapshot().exhausted:
                final_status = "uncertain" if aggregate_messages else "unrecoverable"
                final_confidence = max(final_confidence, 0.2 if aggregate_messages else 0.0)
                final_decision = (
                    "The loop exhausted its remaining budget before building enough evidence to move beyond a weak inference."
                )
                break

        if final_status == "unrecoverable" and aggregate_messages:
            final_status = "uncertain"
            final_confidence = max(final_confidence, 0.2)
            final_decision = "Context loop finished all configured rounds but remained below the resolved threshold."

        source_message_ids = _unique_ids([_message_id(source_message), *aggregate_messages.keys()])
        source_asset_ids = _unique_ids([_asset_id(asset), *aggregate_asset_ids])
        return self._finalize_record(
            context=context,
            asset=asset,
            view_id=view_id,
            status=final_status,
            confidence=final_confidence,
            hypothesis_text=final_hypothesis,
            decision_summary=final_decision,
            evidence_refs=base_evidence + _context_evidence_refs(aggregate_messages, aggregate_asset_ids),
            source_message_ids=source_message_ids,
            source_asset_ids=source_asset_ids,
            budget_snapshot=budget.snapshot().model_dump(),
            round_traces=round_traces,
            signal_summary=self._final_summary(
                asset=asset,
                same_asset_occurrences=same_asset_occurrences,
                aggregate_messages=aggregate_messages,
                final_signal_summary=final_signal_summary,
            ),
            same_asset_occurrences=same_asset_occurrences,
        )

    def _build_round_plan(self) -> list[tuple[RequestKind, ContextRequest]]:
        return [
            (
                "initial_window",
                ContextRequest(
                    before_messages=self.default_before_messages,
                    after_messages=self.default_after_messages,
                    max_additional_messages=self.default_before_messages + self.default_after_messages + 1,
                    notes="Collect the immediate message neighborhood first.",
                ),
            ),
            (
                "same_asset",
                ContextRequest(
                    same_asset_occurrences=True,
                    max_additional_messages=16,
                    notes="Collect repeated occurrences of the same degraded asset.",
                ),
            ),
            (
                "forward_full_bundle",
                ContextRequest(
                    forward_full_bundle=True,
                    max_additional_messages=20,
                    notes="Expand the enclosing forward bundle when available.",
                ),
            ),
            (
                "same_sender",
                ContextRequest(
                    same_sender_window=self.default_same_sender_window,
                    max_additional_messages=(self.default_same_sender_window * 2) + 1,
                    notes="Use nearby messages from the same sender as final contextual support.",
                ),
            ),
        ]

    def _collect_requested_context(
        self,
        *,
        asset: Any,
        source_message: Any,
        messages: Sequence[Any],
        same_asset_occurrences: Sequence[Any],
        request_kind: RequestKind,
        request: ContextRequest,
    ) -> tuple[list[dict[str, str | None]], list[str], str]:
        rows: list[dict[str, str | None]] = []
        asset_ids: list[str] = []
        note = request.notes or ""

        if request_kind == "initial_window":
            rows.extend(
                _slice_message_window(
                    messages,
                    anchor_message_id=_message_id(source_message),
                    before=request.before_messages,
                    after=request.after_messages,
                )
            )
        elif request_kind == "same_asset":
            rows.extend(
                _collect_messages_by_ids(
                    messages,
                    [_message_id_from_asset(item) for item in same_asset_occurrences],
                )
            )
            asset_ids.extend(_asset_id(item) for item in same_asset_occurrences if _asset_id(item))
        elif request_kind == "forward_full_bundle":
            rows.extend(_extract_forward_context_rows(source_message))
        elif request_kind == "same_sender":
            rows.extend(
                _slice_same_sender_window(
                    messages,
                    anchor_message=source_message,
                    radius=request.same_sender_window,
                )
            )

        max_messages = max(request.max_additional_messages, 0)
        if max_messages:
            rows = rows[:max_messages]
        return rows, _unique_ids(asset_ids), note

    def _finalize_record(
        self,
        *,
        context: Any,
        asset: Any,
        view_id: str,
        status: FinalStatus,
        confidence: float,
        hypothesis_text: str | None,
        decision_summary: str,
        evidence_refs: list[AnalysisEvidenceRef],
        source_message_ids: list[str],
        source_asset_ids: list[str],
        budget_snapshot: dict[str, Any],
        round_traces: Sequence[ContextRoundTrace],
        signal_summary: dict[str, Any],
        same_asset_occurrences: Sequence[Any],
    ) -> ExpiredAssetInferenceRecord:
        lineage = _lineage_for_asset(context=context, asset=asset)
        provenance = PreprocessPluginProvenance(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            build_profile="expired_asset_context_view",
        )
        asset_id = _asset_id(asset)
        asset_view = ProcessedAssetView(
            processed_asset_id=_make_id("processed_asset", view_id, asset_id, status),
            view_id=view_id,
            asset_id=asset_id,
            message_id=_message_id_from_asset(asset),
            asset_type=_string_or_none(_asset_type(asset)) or "file",
            resource_state=_resource_state(asset),
            file_name=_string_or_none(_asset_file_name(asset)),
            source_message_ids=source_message_ids,
            source_asset_ids=source_asset_ids,
            operation_type="infer",
            delivery_profile="raw_plus_processed",
            caption=hypothesis_text if status == "resolved" else None,
            summary=_asset_summary(asset, status=status, hypothesis_text=hypothesis_text),
            decision_summary=decision_summary,
            confidence=confidence,
            labels=[
                "expired_asset_inference",
                f"status:{status}",
                f"resource_state:{_resource_state(asset)}",
            ],
            annotations=[],
            metadata={
                "status": status,
                "hypothesis_text": hypothesis_text,
                "same_asset_occurrence_ids": [_asset_id(item) for item in same_asset_occurrences if _asset_id(item)],
                "round_traces": [item.model_dump(mode="json") for item in round_traces],
                "budget_snapshot": budget_snapshot,
                "signal_summary": signal_summary,
                "evidence_refs": [item.model_dump(mode="json") for item in evidence_refs],
                "context_policy": "contextual_inference_only",
            },
            lineage=lineage,
            provenance=provenance,
        )
        annotation = PreprocessAnnotation(
            annotation_id=_make_id("annotation", view_id, asset_id, status),
            operation_type="infer",
            scope_level="asset",
            label=self.plugin_id,
            summary=asset_view.summary or decision_summary,
            decision_summary=decision_summary,
            confidence=confidence,
            source_message_ids=source_message_ids,
            source_asset_ids=source_asset_ids,
            target_ids=[asset_view.processed_asset_id] if asset_view.processed_asset_id else [],
            tags=list(asset_view.labels),
            metadata={
                "status": status,
                "budget_snapshot": budget_snapshot,
                "signal_summary": signal_summary,
                "hypothesis_text": hypothesis_text,
                "round_traces": [item.model_dump(mode="json") for item in round_traces],
                "same_asset_occurrence_ids": [_asset_id(item) for item in same_asset_occurrences if _asset_id(item)],
            },
            lineage=lineage,
            provenance=provenance,
        )
        asset_view.annotations = [annotation]
        agent_result = AgentAnalysisResult(
            status=status,
            confidence=confidence,
            need_more_context_to_analysis=False,
            requested_context=None,
            hypothesis=hypothesis_text,
            evidence_refs=evidence_refs,
            recommended_followups=_followups_for_status(status),
            details={
                "decision_summary": decision_summary,
                "round_traces": [item.model_dump(mode="json") for item in round_traces],
                "budget_snapshot": budget_snapshot,
                "signal_summary": signal_summary,
                "contextual_only": True,
            },
        )
        return ExpiredAssetInferenceRecord(
            asset_view=asset_view,
            annotation=annotation,
            agent_result=agent_result,
            source_message_ids=source_message_ids,
            source_asset_ids=source_asset_ids,
            evidence_refs=evidence_refs,
            budget_snapshot=budget_snapshot,
        )

    def _info_record(self, context: Any, summary: str) -> ExpiredAssetInferenceRecord:
        lineage = _context_lineage(context)
        provenance = PreprocessPluginProvenance(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            build_profile="expired_asset_context_view",
        )
        annotation = PreprocessAnnotation(
            annotation_id=_make_id("annotation", getattr(context, "run_id", None), "info"),
            operation_type="annotate",
            scope_level="asset",
            label=self.plugin_id,
            summary=summary,
            decision_summary=summary,
            confidence=1.0,
            tags=["expired_asset_inference", "info"],
            metadata={"status": "info"},
            lineage=lineage,
            provenance=provenance,
        )
        asset_view = ProcessedAssetView(
            processed_asset_id=_make_id("processed_asset", getattr(context, "run_id", None), "info"),
            view_id=str(getattr(context, "run_id", "") or "expired_asset_context"),
            asset_id=None,
            message_id=None,
            asset_type="file",
            resource_state="unsupported",
            operation_type="annotate",
            delivery_profile="raw_plus_processed",
            summary=summary,
            decision_summary=summary,
            confidence=1.0,
            labels=["expired_asset_inference", "info"],
            annotations=[annotation],
            metadata={"status": "info"},
            lineage=lineage,
            provenance=provenance,
        )
        return ExpiredAssetInferenceRecord(
            asset_view=asset_view,
            annotation=annotation,
            agent_result=AgentAnalysisResult(
                status="info",
                confidence=1.0,
                hypothesis=None,
                details={"decision_summary": summary},
            ),
            budget_snapshot=ContextBudgetManager(self.budget).snapshot().model_dump(),
        )

    def _final_summary(
        self,
        *,
        asset: Any,
        same_asset_occurrences: Sequence[Any],
        aggregate_messages: Mapping[str, Mapping[str, str | None]],
        final_signal_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "asset_id": _asset_id(asset),
            "file_name": _asset_file_name(asset),
            "resource_state": _resource_state(asset),
            "same_asset_occurrence_count": len(
                {
                    message_id
                    for message_id in (_message_id_from_asset(item) for item in same_asset_occurrences)
                    if message_id
                }
            ),
            "context_message_count": len(aggregate_messages),
            "signal": dict(final_signal_summary),
        }


def _base_evidence(asset: Any, message: Any | None) -> list[AnalysisEvidenceRef]:
    refs = [
        AnalysisEvidenceRef(
            kind="asset",
            asset_id=_asset_id(asset),
            message_id=_message_id_from_asset(asset),
            note=f"resource_state={_resource_state(asset)}; asset_type={_asset_type(asset)}",
        )
    ]
    if message is not None:
        refs.append(
            AnalysisEvidenceRef(
                kind="message",
                message_id=_message_id(message),
                note="source_message",
            )
        )
    return refs


def _context_evidence_refs(
    aggregate_messages: Mapping[str, Mapping[str, str | None]],
    aggregate_asset_ids: Iterable[str],
) -> list[AnalysisEvidenceRef]:
    refs = [
        AnalysisEvidenceRef(kind="message", message_id=message_id, note="context_message")
        for message_id in list(aggregate_messages)[:24]
    ]
    refs.extend(
        AnalysisEvidenceRef(kind="asset", asset_id=asset_id, note="same_asset_occurrence")
        for asset_id in list(dict.fromkeys(item for item in aggregate_asset_ids if item))[:16]
    )
    return refs


def _evaluate_signal_strength(
    *,
    asset: Any,
    source_message: Any,
    aggregate_messages: Mapping[str, Mapping[str, str | None]],
    same_asset_occurrences: Sequence[Any],
    min_resolved_signal_chars: int,
    min_uncertain_signal_chars: int,
) -> dict[str, Any]:
    textual_snippets: list[str] = []
    source_text = _message_text(source_message)
    if _is_nontrivial_text(source_text):
        textual_snippets.append(source_text)
    for row in aggregate_messages.values():
        text = row.get("text_content") or row.get("summary") or row.get("content")
        if _is_nontrivial_text(text):
            textual_snippets.append(str(text).strip())
    unique_snippets = _dedupe_preserve_order(textual_snippets)
    recurrence_hint_count = len(
        {
            message_id
            for message_id in (_message_id_from_asset(item) for item in same_asset_occurrences)
            if message_id
        }
    )
    explicit_chars = sum(len(item) for item in unique_snippets)
    hypothesis_text = _compose_hypothesis(
        asset=asset,
        source_message=source_message,
        snippets=unique_snippets,
        recurrence_hint_count=recurrence_hint_count,
    )
    if explicit_chars >= min_resolved_signal_chars and len(unique_snippets) >= 2:
        return {
            "status": "resolved",
            "confidence": 0.72,
            "explicit_chars": explicit_chars,
            "snippet_count": len(unique_snippets),
            "recurrence_hint_count": recurrence_hint_count,
            "hypothesis_text": hypothesis_text,
            "reason": "sufficient_contextual_signal",
        }
    if explicit_chars >= min_uncertain_signal_chars or recurrence_hint_count >= 2:
        return {
            "status": "uncertain",
            "confidence": 0.38,
            "explicit_chars": explicit_chars,
            "snippet_count": len(unique_snippets),
            "recurrence_hint_count": recurrence_hint_count,
            "hypothesis_text": hypothesis_text,
            "reason": "partial_contextual_signal",
        }
    return {
        "status": "unrecoverable",
        "confidence": 0.0,
        "explicit_chars": explicit_chars,
        "snippet_count": len(unique_snippets),
        "recurrence_hint_count": recurrence_hint_count,
        "hypothesis_text": None,
        "reason": "insufficient_contextual_signal",
    }


def _compose_hypothesis(
    *,
    asset: Any,
    source_message: Any,
    snippets: Sequence[str],
    recurrence_hint_count: int,
) -> str | None:
    if not snippets:
        return None
    sender = _string_or_none(getattr(source_message, "sender_name", None)) or _string_or_none(
        getattr(source_message, "sender_id", None)
    )
    file_name = _string_or_none(_asset_file_name(asset))
    snippet_preview = " / ".join(snippets[:3])
    parts = [
        "Context-supported inference only.",
        f"sender={sender}" if sender else None,
        f"file_name={file_name}" if file_name else None,
        f"same_asset_occurrences={recurrence_hint_count}" if recurrence_hint_count else None,
        f"context={snippet_preview}",
    ]
    text = "; ".join(part for part in parts if part)
    return text or None


def _followups_for_status(status: FinalStatus) -> list[str]:
    if status == "resolved":
        return [
            "Treat the caption as a context-supported inference, not direct media observation.",
            "Prefer raw_plus_processed delivery when downstream analysis needs evidence traceability.",
        ]
    if status == "uncertain":
        return [
            "Keep the degraded asset in the corpus as an uncertain evidence node.",
            "Use surrounding messages and recurrence clusters for downstream weighting instead of assuming content certainty.",
        ]
    if status == "unrecoverable":
        return [
            "Do not fabricate the missing media body.",
            "Fall back to structural signals only when this asset participates in downstream analysis.",
        ]
    return []


def _collect_same_asset_occurrences(assets: Sequence[Any], asset: Any) -> list[Any]:
    target_file_name = (_asset_file_name(asset) or "").strip().lower()
    target_digest = (_string_or_none(getattr(asset, "digest", None)) or "").strip().lower()
    target_exported_rel_path = (_string_or_none(getattr(asset, "exported_rel_path", None)) or "").strip().lower()
    target_source_path = (_string_or_none(getattr(asset, "source_path", None)) or "").strip().lower()
    target_type = (_asset_type(asset) or "").strip().lower()

    matches: list[Any] = []
    for candidate in assets:
        if (_asset_type(candidate) or "").strip().lower() != target_type:
            continue
        if target_digest and (_string_or_none(getattr(candidate, "digest", None)) or "").strip().lower() == target_digest:
            matches.append(candidate)
            continue
        candidate_file_name = (_asset_file_name(candidate) or "").strip().lower()
        if target_file_name and candidate_file_name and candidate_file_name == target_file_name:
            matches.append(candidate)
            continue
        if target_exported_rel_path and (_string_or_none(getattr(candidate, "exported_rel_path", None)) or "").strip().lower() == target_exported_rel_path:
            matches.append(candidate)
            continue
        if target_source_path and (_string_or_none(getattr(candidate, "source_path", None)) or "").strip().lower() == target_source_path:
            matches.append(candidate)

    seen: set[str] = set()
    unique: list[Any] = []
    for item in matches:
        key = _asset_id(item) or f"{_message_id_from_asset(item)}:{_asset_file_name(item)}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _slice_message_window(
    messages: Sequence[Any],
    *,
    anchor_message_id: str | None,
    before: int,
    after: int,
) -> list[dict[str, str | None]]:
    if not anchor_message_id:
        return []
    ordered = list(messages)
    anchor_index = next((index for index, item in enumerate(ordered) if _message_id(item) == anchor_message_id), None)
    if anchor_index is None:
        return []
    start = max(anchor_index - max(before, 0), 0)
    end = min(anchor_index + max(after, 0) + 1, len(ordered))
    return [_message_row(item) for item in ordered[start:end]]


def _slice_same_sender_window(
    messages: Sequence[Any],
    *,
    anchor_message: Any,
    radius: int,
) -> list[dict[str, str | None]]:
    anchor_sender = _string_or_none(getattr(anchor_message, "sender_id", None)) or _string_or_none(
        getattr(anchor_message, "sender_name", None)
    )
    if not anchor_sender:
        return []
    ordered = list(messages)
    try:
        anchor_index = next(index for index, item in enumerate(ordered) if _message_id(item) == _message_id(anchor_message))
    except StopIteration:
        return []
    start = max(anchor_index - max(radius, 0), 0)
    end = min(anchor_index + max(radius, 0) + 1, len(ordered))
    rows: list[dict[str, str | None]] = []
    for item in ordered[start:end]:
        sender = _string_or_none(getattr(item, "sender_id", None)) or _string_or_none(getattr(item, "sender_name", None))
        if sender == anchor_sender:
            rows.append(_message_row(item))
    return rows


def _collect_messages_by_ids(messages: Sequence[Any], message_ids: Sequence[str | None]) -> list[dict[str, str | None]]:
    target_ids = {item for item in message_ids if item}
    if not target_ids:
        return []
    by_id = _message_by_id(messages)
    return [_message_row(by_id[message_id]) for message_id in target_ids if message_id in by_id]


def _extract_forward_context_rows(message: Any) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    for segment in getattr(message, "segments", []) or []:
        if _string_or_none(getattr(segment, "type", None)) != "forward":
            continue
        extra = getattr(segment, "extra", None) or {}
        preview_lines = [str(item).strip() for item in (extra.get("preview_lines") or []) if str(item).strip()]
        for line in preview_lines:
            rows.append(
                {
                    "message_id": _message_id(message),
                    "sender_name": _string_or_none(getattr(message, "sender_name", None)),
                    "timestamp_iso": _string_or_none(getattr(message, "timestamp_iso", None)),
                    "text_content": line,
                    "summary": "forward_preview_line",
                    "content": line,
                }
            )
        detailed_text = _string_or_none(extra.get("detailed_text"))
        if detailed_text:
            rows.append(
                {
                    "message_id": _message_id(message),
                    "sender_name": _string_or_none(getattr(message, "sender_name", None)),
                    "timestamp_iso": _string_or_none(getattr(message, "timestamp_iso", None)),
                    "text_content": detailed_text,
                    "summary": "forward_detailed_text",
                    "content": detailed_text,
                }
            )
        for item in extra.get("forward_messages") or []:
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    "message_id": _string_or_none(item.get("message_id")) or _message_id(message),
                    "sender_name": _string_or_none(item.get("sender_name")),
                    "timestamp_iso": _string_or_none(item.get("timestamp_iso")),
                    "text_content": _string_or_none(item.get("text_content")) or _string_or_none(item.get("content")),
                    "summary": "forward_inner_message",
                    "content": _string_or_none(item.get("content")) or _string_or_none(item.get("text_content")),
                }
            )
    return [row for row in rows if _is_nontrivial_text(row.get("text_content"))]


def _message_row(item: Any) -> dict[str, str | None]:
    return {
        "message_id": _message_id(item),
        "sender_name": _string_or_none(getattr(item, "sender_name", None)),
        "timestamp_iso": _string_or_none(getattr(item, "timestamp_iso", None)),
        "text_content": _message_text(item),
        "summary": None,
        "content": _string_or_none(getattr(item, "content", None)),
    }


def _lineage_for_asset(*, context: Any, asset: Any) -> CorpusLineage | None:
    lineage = getattr(asset, "lineage", None)
    if lineage is not None:
        return lineage
    return _context_lineage(context)


def _context_lineage(context: Any) -> CorpusLineage | None:
    lineage = getattr(context, "lineage", None)
    if lineage is not None:
        return lineage
    manifest = getattr(context, "manifest", None)
    if manifest is not None:
        return getattr(manifest, "lineage", None)
    return None


def _make_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None and str(part) != "")
    token = raw or prefix
    return f"{prefix}_{sha1(token.encode('utf-8')).hexdigest()[:12]}"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _is_nontrivial_text(value: Any) -> bool:
    text = _string_or_none(value)
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"[image]", "[video]", "[file]", "[speech]"}:
        return False
    return len(text) >= 4


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in values:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _assets_from_context(context: Any) -> Sequence[Any]:
    direct = getattr(context, "assets", None)
    if direct is not None:
        return direct
    corpus = getattr(context, "corpus", None)
    if corpus is not None:
        nested = getattr(corpus, "assets", None)
        if nested is not None:
            return nested
    return []


def _messages_from_context(context: Any) -> Sequence[Any]:
    direct = getattr(context, "messages", None)
    if direct is not None:
        return direct
    corpus = getattr(context, "corpus", None)
    if corpus is not None:
        nested = getattr(corpus, "messages", None)
        if nested is not None:
            return nested
    return []


def _context_metadata(context: Any) -> dict[str, Any]:
    metadata = getattr(context, "metadata", None)
    if isinstance(metadata, Mapping):
        return dict(metadata)
    manifest = getattr(context, "manifest", None)
    if manifest is not None and isinstance(getattr(manifest, "metadata", None), Mapping):
        return dict(getattr(manifest, "metadata"))
    return {}


def _message_by_id(messages: Sequence[Any]) -> dict[str, Any]:
    return {
        message_id: item
        for item in messages
        if (message_id := _message_id(item))
    }


def _message_id(item: Any) -> str | None:
    return _string_or_none(getattr(item, "message_id", None)) or (
        f"seq:{value}" if (value := _string_or_none(getattr(item, "message_seq", None))) else None
    )


def _message_id_from_asset(asset: Any) -> str | None:
    return _string_or_none(getattr(asset, "message_id", None)) or _string_or_none(
        getattr(asset, "message_uid", None)
    )


def _asset_id(asset: Any) -> str | None:
    return _string_or_none(getattr(asset, "asset_id", None))


def _asset_type(asset: Any) -> str | None:
    return _string_or_none(getattr(asset, "asset_type", None))


def _resource_state(asset: Any) -> ResourceState:
    value = _string_or_none(getattr(asset, "resource_state", None))
    if value in FOCUS_RESOURCE_STATES or value in {"available", "unsupported"}:
        return value  # type: ignore[return-value]
    return "unsupported"


def _asset_file_name(asset: Any) -> str | None:
    return _string_or_none(getattr(asset, "file_name", None))


def _message_text(message: Any) -> str | None:
    return _string_or_none(getattr(message, "text_content", None)) or _string_or_none(
        getattr(message, "content", None)
    )


def _unique_ids(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in values:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _asset_summary(asset: Any, *, status: FinalStatus, hypothesis_text: str | None) -> str:
    file_name = _asset_file_name(asset) or _asset_id(asset) or "unknown_asset"
    if status == "resolved" and hypothesis_text:
        return (
            f"Context-supported inference available for degraded asset {file_name}. "
            "This summary is derived from surrounding messages and structural evidence only."
        )
    if status == "uncertain":
        return (
            f"Only partial context was available for degraded asset {file_name}; keep it as an uncertain evidence node."
        )
    if status == "unrecoverable":
        return (
            f"No reliable contextual inference could be built for degraded asset {file_name} within the configured budget."
        )
    return f"Expired asset inference info: {file_name}."
