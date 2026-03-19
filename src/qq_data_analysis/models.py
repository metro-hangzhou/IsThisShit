from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from qq_data_process.models import IdentityMode

AnalysisTargetType = Literal["group", "friend"]
AnalysisTimeScopeMode = Literal["manual", "auto_adaptive"]
AnalysisOutputMode = Literal["human", "compact", "both"]
AnalysisLlmTriggerMode = Literal["direct_report"]
MediaEvidenceState = Literal["observed", "missing", "inferred", "unknown"]
MediaConfidenceLabel = Literal["direct", "context_only", "unknown"]
MediaHypothesisConfidenceBand = Literal["low", "medium", "high"]


class AnalysisTarget(BaseModel):
    target_type: AnalysisTargetType
    target_id: str
    run_id: str | None = None


class AnalysisTimeScope(BaseModel):
    mode: AnalysisTimeScopeMode = "auto_adaptive"
    start_timestamp_ms: int | None = None
    end_timestamp_ms: int | None = None
    auto_window_ms: int = 24 * 60 * 60 * 1000
    session_gap_ms: int = 30 * 60 * 1000
    min_messages_for_auto: int = 8

    @model_validator(mode="after")
    def _validate_and_normalize(self) -> "AnalysisTimeScope":
        if self.mode == "manual":
            if self.start_timestamp_ms is None or self.end_timestamp_ms is None:
                raise ValueError(
                    "Manual analysis time scope requires both start_timestamp_ms and "
                    "end_timestamp_ms."
                )
            if self.start_timestamp_ms > self.end_timestamp_ms:
                self.start_timestamp_ms, self.end_timestamp_ms = (
                    self.end_timestamp_ms,
                    self.start_timestamp_ms,
                )
        return self


class AnalysisJobConfig(BaseModel):
    target: AnalysisTarget
    time_scope: AnalysisTimeScope = Field(default_factory=AnalysisTimeScope)
    projection_mode: IdentityMode = "alias"
    danger_allow_raw_identity_output: bool = False
    output_mode: AnalysisOutputMode = "both"
    llm_trigger_mode: AnalysisLlmTriggerMode = "direct_report"
    llm_enabled: bool = False
    agent_names: list[str] = Field(
        default_factory=lambda: ["base_stats", "content_composition"]
    )
    max_candidate_events: int = 5
    max_people: int = 5
    max_evidence_items: int = 8
    max_theme_queries: int = 3


class AnalysisEvidenceItem(BaseModel):
    message_uid: str
    timestamp_iso: str
    sender_id: str
    sender_name: str | None = None
    content: str
    reason: str
    tags: list[str] = Field(default_factory=list)


class AnalysisEvidenceRef(BaseModel):
    kind: Literal["message", "asset", "thread", "forward_bundle", "annotation"] = "message"
    message_id: str | None = None
    asset_id: str | None = None
    thread_id: str | None = None
    segment_id: str | None = None
    note: str | None = None


class AnalysisTagSummary(BaseModel):
    tag: str
    count: int
    rate: float
    open_notes: list[str] = Field(default_factory=list)
    evidence_message_uids: list[str] = Field(default_factory=list)


class ParticipantProfile(BaseModel):
    sender_id: str
    sender_name: str | None = None
    message_count: int
    tag_counts: dict[str, int] = Field(default_factory=dict)
    open_notes: list[str] = Field(default_factory=list)
    evidence: list[AnalysisEvidenceItem] = Field(default_factory=list)


class CandidateEvent(BaseModel):
    event_id: str
    start_timestamp_ms: int
    end_timestamp_ms: int
    start_timestamp_iso: str
    end_timestamp_iso: str
    message_count: int
    participant_count: int
    dominant_tags: list[str] = Field(default_factory=list)
    summary: str
    evidence: list[AnalysisEvidenceItem] = Field(default_factory=list)


class AnalysisStatsSnapshot(BaseModel):
    message_count: int
    sender_count: int
    asset_count: int
    image_message_count: int
    forward_message_count: int
    reply_message_count: int
    emoji_message_count: int
    low_information_count: int
    image_ratio: float
    forward_ratio: float
    reply_ratio: float
    emoji_ratio: float
    low_information_ratio: float
    hourly_distribution: dict[str, int] = Field(default_factory=dict)
    daily_distribution: dict[str, int] = Field(default_factory=dict)


class AnalysisMessageFeatures(BaseModel):
    image_count: int = 0
    file_count: int = 0
    emoji_count: int = 0
    share_marker_count: int = 0
    system_marker_count: int = 0
    missing_media_count: int = 0
    has_reply: bool = False
    has_forward: bool = False
    forward_depth: int = 0
    low_information: bool = False
    repeated_noise: bool = False
    unsupported_count: int = 0
    message_tags: list[str] = Field(default_factory=list)


class AnalysisMessageRecord(BaseModel):
    message_uid: str
    run_id: str
    chat_type: str
    chat_id: str
    chat_name: str | None = None
    sender_id: str
    sender_name: str | None = None
    timestamp_ms: int
    timestamp_iso: str
    message_id: str | None = None
    message_seq: str | None = None
    content: str
    text_content: str
    assets: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
    features: AnalysisMessageFeatures = Field(default_factory=AnalysisMessageFeatures)


class ResolvedAnalysisTarget(BaseModel):
    target_type: AnalysisTargetType
    raw_id: str
    alias_id: str
    display_id: str
    display_name: str | None = None
    run_id: str


class ResolvedTimeWindow(BaseModel):
    mode: AnalysisTimeScopeMode
    start_timestamp_ms: int
    end_timestamp_ms: int
    start_timestamp_iso: str
    end_timestamp_iso: str
    rationale: str
    selected_message_count: int


class AnalysisMaterials(BaseModel):
    run_id: str
    target: ResolvedAnalysisTarget
    chosen_time_window: ResolvedTimeWindow
    messages: list[AnalysisMessageRecord] = Field(default_factory=list)
    stats: AnalysisStatsSnapshot
    manifest_media_coverage: MediaCoverageSummary | None = None
    tag_summaries: list[AnalysisTagSummary] = Field(default_factory=list)
    candidate_events: list[CandidateEvent] = Field(default_factory=list)
    participant_profiles: list[ParticipantProfile] = Field(default_factory=list)
    theme_queries: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    input_context: dict[str, Any] = Field(default_factory=dict)


class AnalysisAgentOutput(BaseModel):
    agent_name: str
    agent_version: str
    human_report: str
    compact_payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[AnalysisEvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DeterministicResult(BaseModel):
    plugin_id: str
    plugin_version: str
    status: Literal["resolved", "uncertain", "unrecoverable", "info"] = "resolved"
    summary: str
    confidence: float = 0.0
    modality_targets: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[AnalysisEvidenceRef] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    verdict: str | None = None
    notes: list[str] = Field(default_factory=list)


class AnalysisRunResult(BaseModel):
    run_id: str
    target: ResolvedAnalysisTarget
    chosen_time_window: ResolvedTimeWindow
    agent_outputs: list[AnalysisAgentOutput] = Field(default_factory=list)
    summary_report: str
    compact_machine_output: str
    warnings: list[str] = Field(default_factory=list)
    input_context: dict[str, Any] = Field(default_factory=dict)


class AnalysisPackMessageSample(BaseModel):
    message_uid: str
    timestamp_iso: str
    sender_id: str
    sender_name: str | None = None
    content: str
    tags: list[str] = Field(default_factory=list)


class MediaCoverageSummary(BaseModel):
    total_image_references: int = 0
    total_file_references: int = 0
    total_sticker_references: int = 0
    total_video_references: int = 0
    total_speech_references: int = 0
    missing_image_count: int = 0
    missing_file_count: int = 0
    missing_sticker_count: int = 0
    missing_video_count: int = 0
    missing_speech_count: int = 0
    image_missing_ratio: float = 0.0
    file_missing_ratio: float = 0.0
    sticker_missing_ratio: float = 0.0
    video_missing_ratio: float = 0.0
    speech_missing_ratio: float = 0.0
    overall_media_missing_ratio: float = 0.0
    media_availability_flags: dict[str, bool] = Field(default_factory=dict)


class MediaEvidenceScaffoldItem(BaseModel):
    asset_type: str
    state: MediaEvidenceState
    confidence_label: MediaConfidenceLabel
    confidence_score: float = 0.0
    confidence_band: MediaHypothesisConfidenceBand | None = None
    source_message_uid: str | None = None
    source_timestamp_iso: str | None = None
    source_sender_id: str | None = None
    context_excerpt: str | None = None
    hypothesis_kind: str | None = None
    hypothesis_text: str | None = None
    support_message_uids: list[str] = Field(default_factory=list)
    reference_message_uids: list[str] = Field(default_factory=list)
    support_signals: list[str] = Field(default_factory=list)
    contradiction_signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MediaInferenceScaffold(BaseModel):
    observed: list[MediaEvidenceScaffoldItem] = Field(default_factory=list)
    missing: list[MediaEvidenceScaffoldItem] = Field(default_factory=list)
    inferred: list[MediaEvidenceScaffoldItem] = Field(default_factory=list)
    unknown: list[MediaEvidenceScaffoldItem] = Field(default_factory=list)
    future_reference_pool_message_uids: list[str] = Field(default_factory=list)


class ImageCaptionSample(BaseModel):
    cluster_id: str | None = None
    cluster_kind: str | None = None
    message_uid: str
    timestamp_iso: str
    sender_id: str
    sender_name: str | None = None
    file_name: str | None = None
    resolved_path: str
    context_excerpt: str = ""
    caption: str
    model_name: str


class AnalysisPack(BaseModel):
    run_id: str
    target: ResolvedAnalysisTarget
    chosen_time_window: ResolvedTimeWindow
    pack_summary: str
    stats: AnalysisStatsSnapshot
    tag_summaries: list[AnalysisTagSummary] = Field(default_factory=list)
    candidate_events: list[CandidateEvent] = Field(default_factory=list)
    participant_profiles: list[ParticipantProfile] = Field(default_factory=list)
    representative_messages: list[AnalysisPackMessageSample] = Field(
        default_factory=list
    )
    special_content_types: dict[str, int] = Field(default_factory=dict)
    retrieval_snippets: list[str] = Field(default_factory=list)
    message_reference_pool: list[AnalysisEvidenceItem] = Field(default_factory=list)
    media_coverage: MediaCoverageSummary = Field(default_factory=MediaCoverageSummary)
    media_inference_scaffold: MediaInferenceScaffold = Field(
        default_factory=MediaInferenceScaffold
    )
    image_caption_samples: list[ImageCaptionSample] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BenshiSelectedMessage(BaseModel):
    message_uid: str
    timestamp_iso: str
    sender_id: str
    sender_name: str | None = None
    message_id: str | None = None
    message_seq: str | None = None
    content: str
    text_content: str
    processed_text: str | None = None
    decision_summary: str | None = None
    delivery_profile: str = "raw_only"
    preprocess_labels: list[str] = Field(default_factory=list)
    source_message_ids: list[str] = Field(default_factory=list)
    source_thread_ids: list[str] = Field(default_factory=list)
    asset_count: int = 0
    asset_types: list[str] = Field(default_factory=list)
    has_forward: bool = False
    forward_depth: int = 0
    missing_media_count: int = 0
    message_tags: list[str] = Field(default_factory=list)


class BenshiForwardSummary(BaseModel):
    summary_id: str
    outer_message_uid: str | None = None
    outer_message_id: str | None = None
    outer_timestamp_iso: str | None = None
    outer_sender_id: str | None = None
    outer_sender_name: str | None = None
    preview_text: str | None = None
    detailed_text: str | None = None
    preview_lines: list[str] = Field(default_factory=list)
    segment_summary: str | None = None
    inner_message_count: int = 0
    inner_asset_count: int = 0
    inner_asset_type_counts: dict[str, int] = Field(default_factory=dict)
    forward_depth_hint: int | None = None
    evidence_message_uids: list[str] = Field(default_factory=list)


class BenshiRecurrenceSummary(BaseModel):
    summary_id: str
    recurrence_key: str
    basis: str
    asset_type: str
    file_name: str | None = None
    occurrence_count: int = 0
    distinct_chat_ids: list[str] = Field(default_factory=list)
    resource_state_counts: dict[str, int] = Field(default_factory=dict)
    materialization_status_counts: dict[str, int] = Field(default_factory=dict)
    exported_rel_paths: list[str] = Field(default_factory=list)
    evidence_message_ids: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class BenshiParticipantRoleCandidate(BaseModel):
    sender_id: str
    sender_name: str | None = None
    message_count: int
    forward_message_count: int = 0
    asset_message_count: int = 0
    reply_message_count: int = 0
    missing_media_message_count: int = 0
    candidate_roles: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    evidence_message_uids: list[str] = Field(default_factory=list)


class BenshiAssetSummary(BaseModel):
    asset_type: str
    reference_count: int = 0
    message_count: int = 0
    materialized_count: int = 0
    missing_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    top_file_names: list[str] = Field(default_factory=list)
    representative_asset_ids: list[str] = Field(default_factory=list)


class BenshiImageClusterSummary(BaseModel):
    cluster_id: str
    cluster_kind: str
    member_count: int = 0
    reference_count: int = 0
    distinct_message_count: int = 0
    representative_message_uid: str | None = None
    representative_timestamp_iso: str | None = None
    representative_file_name: str | None = None
    representative_context_excerpt: str | None = None
    file_name_examples: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    evidence_message_uids: list[str] = Field(default_factory=list)


class BenshiMissingMediaGap(BaseModel):
    gap_id: str
    message_uid: str
    message_id: str | None = None
    timestamp_iso: str
    sender_id: str
    sender_name: str | None = None
    asset_id: str | None = None
    asset_type: str
    file_name: str | None = None
    status: str | None = None
    resolver: str | None = None
    exported_rel_path: str | None = None
    context_excerpt: str | None = None
    reason: str | None = None


class BenshiPreprocessOverlayItem(BaseModel):
    message_uid: str
    delivery_profile: str = "raw_only"
    processed_text: str | None = None
    decision_summary: str | None = None
    labels: list[str] = Field(default_factory=list)
    source_message_ids: list[str] = Field(default_factory=list)


class BenshiPreprocessOverlaySummary(BaseModel):
    view_id: str | None = None
    delivery_profile: str | None = None
    overlayed_message_count: int = 0
    processed_message_view_count: int = 0
    processed_thread_view_count: int = 0
    processed_asset_view_count: int = 0
    annotation_count: int = 0
    source_linked_message_count: int = 0
    directive_id: str | None = None
    directive_title: str | None = None
    relevance_policy: str | None = None
    top_labels: dict[str, int] = Field(default_factory=dict)
    representative_items: list[BenshiPreprocessOverlayItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BenshiForwardAggregateSummary(BaseModel):
    forward_message_count: int = 0
    nested_forward_count: int = 0
    expanded_bundle_count: int = 0
    expanded_inner_message_count: int = 0
    expanded_inner_asset_count: int = 0
    top_asset_type_counts: dict[str, int] = Field(default_factory=dict)
    representative_forward_ids: list[str] = Field(default_factory=list)


class BenshiRecurrenceAggregateSummary(BaseModel):
    repeated_transport_count: int = 0
    repeated_asset_cluster_count: int = 0
    top_basis_counts: dict[str, int] = Field(default_factory=dict)
    top_asset_type_counts: dict[str, int] = Field(default_factory=dict)
    high_recurrence_keys: list[str] = Field(default_factory=list)


class BenshiAssetAggregateSummary(BaseModel):
    total_asset_reference_count: int = 0
    materialized_asset_count: int = 0
    missing_asset_count: int = 0
    asset_type_reference_counts: dict[str, int] = Field(default_factory=dict)
    asset_type_missing_counts: dict[str, int] = Field(default_factory=dict)
    asset_type_materialized_counts: dict[str, int] = Field(default_factory=dict)
    top_file_names: list[str] = Field(default_factory=list)


class BenshiShiComponentSummary(BaseModel):
    component_label: str
    component_family: str
    score: float = 0.0
    evidence_basis: list[str] = Field(default_factory=list)
    evidence_message_uids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BenshiShiDescriptionProfile(BaseModel):
    base_definition: str | None = None
    description_strategy: str | None = None
    description_axes: list[str] = Field(default_factory=list)
    descriptive_tags: list[str] = Field(default_factory=list)
    good_description_patterns: list[str] = Field(default_factory=list)
    bad_description_patterns: list[str] = Field(default_factory=list)
    taboo_or_risk_notes: list[str] = Field(default_factory=list)
    example_descriptors: list[str] = Field(default_factory=list)


class BenshiAnalysisPack(BaseModel):
    run_id: str
    target: ResolvedAnalysisTarget
    chosen_time_window: ResolvedTimeWindow
    pack_summary: str
    stats: AnalysisStatsSnapshot
    selected_messages: list[BenshiSelectedMessage] = Field(default_factory=list)
    forward_summary: BenshiForwardAggregateSummary = Field(
        default_factory=BenshiForwardAggregateSummary
    )
    forward_summaries: list[BenshiForwardSummary] = Field(default_factory=list)
    recurrence_summary: BenshiRecurrenceAggregateSummary = Field(
        default_factory=BenshiRecurrenceAggregateSummary
    )
    recurrence_summaries: list[BenshiRecurrenceSummary] = Field(default_factory=list)
    participant_role_candidates: list[BenshiParticipantRoleCandidate] = Field(default_factory=list)
    asset_summary: BenshiAssetAggregateSummary = Field(default_factory=BenshiAssetAggregateSummary)
    asset_summaries: list[BenshiAssetSummary] = Field(default_factory=list)
    shi_component_summaries: list[BenshiShiComponentSummary] = Field(default_factory=list)
    shi_description_profile: BenshiShiDescriptionProfile | None = None
    image_cluster_summaries: list[BenshiImageClusterSummary] = Field(default_factory=list)
    missing_media_gaps: list[BenshiMissingMediaGap] = Field(default_factory=list)
    image_caption_samples: list[ImageCaptionSample] = Field(default_factory=list)
    preprocess_overlay_summary: BenshiPreprocessOverlaySummary | None = None
    warnings: list[str] = Field(default_factory=list)


class LlmAnalysisJobConfig(BaseModel):
    prompt_version: str = "window_report_v1"
    max_candidate_events: int = 5
    max_people: int = 5
    max_representative_messages: int = 40
    max_reference_messages: int = 64
    include_retrieval_snippets: bool = False
    max_retrieval_snippets: int = 4
    enable_text_gap_inference: bool = True
    text_gap_context_radius: int = 2
    max_text_gap_hypotheses: int = 12
    max_input_tokens: int = 16000
    max_output_tokens: int = 2200


class LlmUsageRecord(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0


class LlmRunArtifactSet(BaseModel):
    analysis_pack_path: str
    llm_run_meta_path: str
    report_path: str
    usage_path: str
    prompt_path: str


class LlmAnalysisResult(BaseModel):
    pack: AnalysisPack
    prompt_version: str
    provider_name: str
    model_name: str
    report_body: str
    usage: LlmUsageRecord
    warnings: list[str] = Field(default_factory=list)
    artifacts: LlmRunArtifactSet | None = None
