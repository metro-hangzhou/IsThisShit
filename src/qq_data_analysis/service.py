from __future__ import annotations

from pathlib import Path

from .agents import build_default_agent_registry
from .compact import dump_compact_json
from .models import AnalysisJobConfig, AnalysisRunResult
from .substrate import AnalysisSubstrate


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

    def run(self, config: AnalysisJobConfig) -> AnalysisRunResult:
        materials = self.substrate.build_materials(config)
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
        )

    def close(self) -> None:
        self.substrate.close()
