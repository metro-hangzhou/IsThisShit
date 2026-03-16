from __future__ import annotations

from typing import Any, Protocol

from .models import AnalysisAgentOutput, AnalysisMaterials


class AnalysisAgent(Protocol):
    agent_name: str
    agent_version: str

    def prepare(self, materials: AnalysisMaterials) -> Any: ...

    def analyze(
        self, materials: AnalysisMaterials, prepared: Any
    ) -> AnalysisAgentOutput: ...

    def serialize_result(self, output: AnalysisAgentOutput) -> dict[str, Any]: ...
