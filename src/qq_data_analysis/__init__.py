from __future__ import annotations

from .llm_agent import (
    DeepSeekAnalysisClient,
    DeepSeekRuntimeConfig,
    DenseSlicePlan,
    GroundedLlmAgent,
    LlmUsageSnapshot,
    MultimodalInputImage,
    MultimodalLlmClient,
    MultimodalSmokePack,
    OpenAICompatibleAnalysisClient,
    OpenAICompatibleRuntimeConfig,
    load_deepseek_runtime_config,
    load_multimodal_client,
    load_multimodal_runtime_config,
    load_multimodal_smoke_pack,
    load_openai_compatible_runtime_config,
)

__all__ = [
    "DeepSeekAnalysisClient",
    "DeepSeekRuntimeConfig",
    "DenseSlicePlan",
    "GroundedLlmAgent",
    "LlmUsageSnapshot",
    "MultimodalInputImage",
    "MultimodalLlmClient",
    "MultimodalSmokePack",
    "OpenAICompatibleAnalysisClient",
    "OpenAICompatibleRuntimeConfig",
    "load_deepseek_runtime_config",
    "load_multimodal_client",
    "load_multimodal_runtime_config",
    "load_multimodal_smoke_pack",
    "load_openai_compatible_runtime_config",
]

try:
    from .benshi_agent import BenshiMasterAgent
    from .benshi_llm_agent import BenshiMasterLlmAgent
    from .benshi_pack import BenshiAnalysisPackBuilder, build_benshi_analysis_pack
    from .agents import BaseStatsAgent, ContentCompositionAgent, build_default_agent_registry
    from .compact import dump_compact_json, expand_compact_analysis, load_compact_json
    from .interfaces import AnalysisAgent
    from .llm_window import (
        WholeWindowLlmAnalyzer,
        WholeWindowPackBuilder,
        WindowReportPlan,
        load_saved_analysis_pack,
        load_text_analysis_client,
        save_llm_analysis_result,
    )
    from .models import (
        AnalysisAgentOutput,
        AnalysisEvidenceItem,
        AnalysisJobConfig,
        AnalysisPack,
        AnalysisPackMessageSample,
        AnalysisMaterials,
        AnalysisMessageRecord,
        AnalysisRunResult,
        AnalysisStatsSnapshot,
        AnalysisTarget,
        AnalysisTimeScope,
        LlmAnalysisJobConfig,
        LlmAnalysisResult,
        LlmRunArtifactSet,
        LlmUsageRecord,
        BenshiAnalysisPack,
        BenshiForwardAggregateSummary,
        BenshiRecurrenceAggregateSummary,
        BenshiAssetAggregateSummary,
    )
    from .service import AnalysisService
    from .substrate import AnalysisSubstrate
except ImportError:  # pragma: no cover - degraded import mode for smoke/runtime tools
    pass
else:
    __all__.extend(
        [
            "AnalysisAgent",
            "AnalysisAgentOutput",
            "AnalysisEvidenceItem",
            "AnalysisJobConfig",
            "AnalysisPack",
            "AnalysisPackMessageSample",
            "AnalysisMaterials",
            "AnalysisMessageRecord",
            "AnalysisRunResult",
            "AnalysisService",
            "AnalysisStatsSnapshot",
            "AnalysisSubstrate",
            "AnalysisTarget",
            "AnalysisTimeScope",
            "BenshiAnalysisPack",
            "BenshiAnalysisPackBuilder",
            "BenshiAssetAggregateSummary",
            "BenshiForwardAggregateSummary",
            "BenshiMasterAgent",
            "BenshiMasterLlmAgent",
            "BenshiRecurrenceAggregateSummary",
            "BaseStatsAgent",
            "ContentCompositionAgent",
            "build_default_agent_registry",
            "build_benshi_analysis_pack",
            "dump_compact_json",
            "expand_compact_analysis",
            "load_compact_json",
            "LlmAnalysisJobConfig",
            "LlmAnalysisResult",
            "LlmRunArtifactSet",
            "LlmUsageRecord",
            "WholeWindowLlmAnalyzer",
            "WholeWindowPackBuilder",
            "WindowReportPlan",
            "load_saved_analysis_pack",
            "load_text_analysis_client",
            "save_llm_analysis_result",
        ]
    )
