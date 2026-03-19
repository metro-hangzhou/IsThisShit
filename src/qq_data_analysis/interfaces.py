from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, TypeAlias

from qq_data_process.preprocess_models import PreprocessViewContext

from .models import AnalysisAgentOutput, AnalysisMaterials, DeterministicResult


class AnalysisAgent(Protocol):
    agent_name: str
    agent_version: str

    def prepare(self, materials: AnalysisMaterials) -> Any: ...

    def analyze(
        self, materials: AnalysisMaterials, prepared: Any
    ) -> AnalysisAgentOutput: ...

    def serialize_result(self, output: AnalysisAgentOutput) -> dict[str, Any]: ...


class AnalyzerContext(Protocol):
    corpus: Any
    run_id: str
    run_dir: Any
    options: Mapping[str, Any]


class DeterministicAnalyzer(Protocol):
    plugin_id: str
    plugin_version: str
    scope_level: str
    requires: tuple[str, ...] | list[str]
    produces: tuple[str, ...] | list[str]
    supported_modalities: tuple[str, ...] | list[str]

    def run(self, context: AnalyzerContext) -> list[DeterministicResult]: ...


class RawAnalysisInput(Protocol):
    context_id: str
    chat_id: str | None
    metadata: Mapping[str, Any]
    lineage: Any
    provenance: Any
    source_path: str | Path | None
    source_type: str | None


class PreprocessAnalysisInput(Protocol):
    context_id: str
    manifest: Any
    metadata: Mapping[str, Any]
    lineage: Any
    provenance: Any
    message_views: list[Any]
    thread_views: list[Any]
    asset_views: list[Any]
    annotations: list[Any]


AnalysisRuntimeInput: TypeAlias = RawAnalysisInput | PreprocessViewContext
