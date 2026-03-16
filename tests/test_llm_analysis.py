from __future__ import annotations

from pathlib import Path
import shutil

from qq_data_analysis import AnalysisJobConfig, AnalysisSubstrate, AnalysisTarget
from qq_data_analysis.llm_agent import (
    DeepSeekRuntimeConfig,
    DenseSlicePlan,
    GroundedLlmAgent,
    LlmResponseBundle,
    LlmUsageSnapshot,
    load_deepseek_runtime_config,
    load_openai_compatible_runtime_config,
)
from qq_data_process import (
    ChunkPolicySpec,
    DeterministicEmbeddingProvider,
    EmbeddingPolicy,
    PreprocessJobConfig,
    PreprocessService,
)


class _FakeClient:
    def __init__(self) -> None:
        self.config = DeepSeekRuntimeConfig(api_key="fake-key")

    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> LlmResponseBundle:
        assert system_prompt
        assert user_prompt
        assert max_output_tokens == 256
        first_message_uid = "msg_1"
        for line in user_prompt.splitlines():
            if line.startswith("mid="):
                first_message_uid = line.split("|", 1)[0].split("=", 1)[1].strip()
                break
        return LlmResponseBundle(
            parsed_payload={
                "sm": "测试摘要",
                "tp": ["技术闲聊", "图片互动"],
                "bh": ["图文混合", "短句接话"],
                "pp": [
                    {
                        "sid": "user_a",
                        "role": "高频参与者",
                        "why": "多次接话",
                        "e": [first_message_uid],
                    }
                ],
                "ev": [{"id": first_message_uid, "why": "作为样例证据"}],
                "nt": ["这是一条测试备注"],
                "lim": ["仅基于局部窗口"],
            },
            raw_text='{"sm":"测试摘要"}',
            reasoning_text="internal reasoning",
            finish_reason="stop",
            usage=LlmUsageSnapshot(
                prompt_tokens=321,
                completion_tokens=123,
                total_tokens=444,
                reasoning_tokens=12,
                cached_tokens=0,
            ),
            raw_response={"usage": {"prompt_tokens": 321}},
        )


def _build_analysis_state(tmp_name: str) -> tuple[Path, Path]:
    tmp_path = Path(".tmp") / tmp_name
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=Path("tests/fixtures/analysis_seed.jsonl"),
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        chunk_policy_specs=[
            ChunkPolicySpec(
                name="hybrid",
                params={"gap_seconds": 900, "max_messages": 5, "overlap": 1},
            )
        ],
    )
    result = service.run(config)
    return result.sqlite_path, result.qdrant_location


def test_llm_agent_prepare_selects_dense_slice_under_budget() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_llm_agent_prepare")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    agent = GroundedLlmAgent(
        client=_FakeClient(),
        max_messages=6,
        max_input_tokens=800,
        max_output_tokens=256,
    )
    plan = agent.prepare(materials)

    assert isinstance(plan, DenseSlicePlan)
    assert len(plan.selected_messages) <= 6
    assert plan.estimated_input_tokens <= 800
    assert plan.selected_start_iso <= plan.selected_end_iso


def test_llm_agent_analyze_returns_compact_payload_and_usage() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_llm_agent_analyze")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
        agent = GroundedLlmAgent(
            client=_FakeClient(),
            max_messages=6,
            max_input_tokens=800,
            max_output_tokens=256,
        )
        plan = agent.prepare(materials)
        output = agent.analyze(materials, plan)
    finally:
        substrate.close()

    assert output.agent_name == "grounded_llm"
    assert output.compact_payload["usage"]["total"] == 444
    assert output.evidence
    assert "测试摘要" in output.human_report


def test_load_deepseek_runtime_config_rejects_placeholder_key() -> None:
    tmp_path = Path(".tmp") / "test_llm_runtime_config"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "llm.local.json"
    config_path.write_text(
        """
{
  "deepseek": {
    "api_key": "PASTE_YOUR_DEEPSEEK_API_KEY_HERE"
  }
}
""".strip(),
        encoding="utf-8",
    )

    try:
        load_deepseek_runtime_config(config_path)
    except RuntimeError as exc:
        assert "placeholder" in str(exc)
    else:
        raise AssertionError("Expected placeholder config to be rejected.")


def test_load_openai_compatible_runtime_config_reads_custom_provider_block() -> None:
    tmp_path = Path(".tmp") / "test_openai_runtime_config"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "llm.local.json"
    config_path.write_text(
        """
{
  "openai_compatible": {
    "api_key": "fake-key",
    "base_url": "http://127.0.0.1:8317/v1",
    "model": "gpt-5.4"
  }
}
""".strip(),
        encoding="utf-8",
    )

    runtime = load_openai_compatible_runtime_config(config_path)

    assert runtime.base_url == "http://127.0.0.1:8317/v1"
    assert runtime.model == "gpt-5.4"
